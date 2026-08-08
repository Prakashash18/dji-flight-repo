import os
import uuid
import time
import datetime
import math
import threading
import cv2
from ultralytics import YOLO
from typing import Optional

import numpy as np

from georeferencing import TelemetryInterpolator, georeference_box
from config import settings
import sahi_engine
from model_source import resolve_model_path
from parallel_inference import SahiInferencePool, plan_execution, run_serial
# supabase_client and gcs_client are dynamically imported inside functions to avoid circular import issues
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from concurrent.futures.process import BrokenProcessPool

# Longest a single frame may occupy the pool. Generous next to the ~2s a 4K
# frame takes on an accelerator, so only a genuinely wedged worker trips it.
FRAME_TIMEOUT_S = int(os.getenv("FRAME_TIMEOUT_S", "180"))
from collections import deque

# Thread pool for asynchronous crop uploads and Supabase writes
db_upload_executor = ThreadPoolExecutor(max_workers=4)

# --- Annotated frames -------------------------------------------------------
# Sending the raw video and the boxes separately means the phone has to line the
# two up in time, and it cannot: the detector emits one frame per second of
# footage while the video plays continuously, so a box computed at t=12.0 gets
# painted over the frame at t=12.4 — by which point the drone has moved and the
# box sits beside the litter rather than on it. No amount of playback-rate
# control fixes that, because the intermediate frames were never analysed.
#
# So the frame the detector actually looked at is published with its boxes
# already drawn on it. The box cannot drift from its own frame.
FRAMES_DIR = os.path.join(os.path.dirname(__file__), "frame_cache")

# Matches the phone's own palette so the burned-in boxes and the class chips in
# the app are the same colour. Stored BGR, which is the order OpenCV draws in.
LANE_BGR = {
    "teal":   (119, 133, 18),
    "amber":  (20, 106, 184),
    "violet": (158, 78, 107),
    "coral":  (106, 68, 214),
    "ink":    (128, 142, 154),
}
CLASS_LANE = {
    "Plastic": "teal", "Soft Plastic": "teal",
    "Metal": "amber", "Paper pack": "amber", "Paper-Cardboard": "amber",
    "Glass": "coral", "Clothing": "violet",
    "Miscellaneous Litter": "ink",
}
# A phone screen is ~400px wide; 960 keeps small litter legible when the viewer
# pinches in without paying for 4K over a shared uplink.
ANNOTATED_WIDTH = 960
ANNOTATED_QUALITY = 72
LABEL_FONT = cv2.FONT_HERSHEY_DUPLEX


def write_annotated_frame(task_id: str, frame, detections: list, time_ms: float) -> Optional[dict]:
    """
    Draw this frame's detections onto the frame and publish it as a JPEG.

    Returns the frame record the live feed hands to the phone, or None if the
    frame could not be written (a full disk must not take the run down).
    """
    try:
        h, w = frame.shape[:2]
        if not w or not h:
            return None
        scale = min(1.0, ANNOTATED_WIDTH / float(w))
        out = cv2.resize(frame, (int(w * scale), int(h * scale)),
                         interpolation=cv2.INTER_AREA) if scale < 1.0 else frame.copy()

        oh, ow = out.shape[:2]
        # This image is displayed about 375px wide on a phone, so everything
        # drawn here is seen at roughly 0.4x. Stroke weight and type size are
        # set against the output width and then deliberately over-scaled, or
        # they arrive on screen too fine to read.
        thickness = max(3, int(round(ow / 240)))
        label_scale = max(1.0, ow / 760.0)
        label_weight = max(2, int(round(ow / 640)))

        for det in detections:
            colour = LANE_BGR.get(CLASS_LANE.get(det.get("class_name"), "ink"), LANE_BGR["ink"])
            x1 = int(round(det["x1"] * scale)); y1 = int(round(det["y1"] * scale))
            x2 = int(round(det["x2"] * scale)); y2 = int(round(det["y2"] * scale))
            # A bottle from 30m up can be six pixels across — grow the box to a
            # size a human eye can actually land on, centred on the detection.
            if x2 - x1 < 22:
                cx = (x1 + x2) // 2; x1, x2 = cx - 11, cx + 11
            if y2 - y1 < 22:
                cy = (y1 + y2) // 2; y1, y2 = cy - 11, cy + 11
            x1 = max(0, min(ow - 1, x1)); x2 = max(0, min(ow - 1, x2))
            y1 = max(0, min(oh - 1, y1)); y2 = max(0, min(oh - 1, y2))
            cv2.rectangle(out, (x1, y1), (x2, y2), colour, thickness, lineType=cv2.LINE_AA)

            name = det.get("class_name") or ""
            if not name:
                continue
            (tw, th), base = cv2.getTextSize(name, LABEL_FONT, label_scale, label_weight)
            # Sit the chip above the box, or below it when the box is near the
            # top edge and the label would be clipped off the frame.
            ly = y1 - max(6, thickness)
            if ly - th - 6 < 0:
                ly = min(oh - 4, y2 + th + max(8, thickness))
            lx = max(0, min(x1, ow - tw - 8))
            # Filled chip in the class colour: white-on-sand is unreadable, and
            # this is the same colour the app uses for the class elsewhere.
            cv2.rectangle(out, (lx - 4, ly - th - 6), (lx + tw + 6, ly + base - 1),
                          colour, -1, lineType=cv2.LINE_AA)
            cv2.putText(out, name, (lx, ly - 3), LABEL_FONT, label_scale,
                        (255, 255, 255), label_weight, cv2.LINE_AA)

        task_dir = os.path.join(FRAMES_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)
        name = f"{int(round(time_ms)):08d}.jpg"
        path = os.path.join(task_dir, name)
        ok, buf = cv2.imencode(".jpg", out, [int(cv2.IMWRITE_JPEG_QUALITY), ANNOTATED_QUALITY])
        if not ok:
            return None
        with open(path, "wb") as f:
            f.write(buf.tobytes())

        return {
            "t": round(time_ms / 1000.0, 2),
            "url": f"/api/frames/{task_id}/{name}",
            "n": len(detections),
            "w": ow,
            "h": oh,
        }
    except Exception as e:
        print(f"⚠️ Annotated frame write failed at {time_ms/1000:.1f}s: {e}")
        return None

# Supabase Storage bucket holding detection crops (see README setup step 3).
SUPABASE_IMAGE_BUCKET = "litter-images"


def plan_crop_destination(bucket_name: str):
    """
    Where a detection crop lives, as (backend, object_path, url).

    Always this machine. Crops used to go to GCS or Supabase Storage and the
    served URL pointed back out at them, so displaying a thumbnail meant a round
    trip to another continent — which failed often enough under a run's write
    load that most pins showed no image. The bytes are produced here; they stay
    here, and `/api/crops` serves them off disk.
    """
    object_path = f"detections/{uuid.uuid4()}_detection.jpg"
    return "local", object_path, f"/api/crops/{object_path}"


def cache_crop_locally(object_path: Optional[str], jpeg_bytes: Optional[bytes]) -> bool:
    """
    Keep a copy of the crop on this machine, under the same path /api/crops serves.

    The bytes are already in hand here, yet the served URL pointed at object
    storage — so displaying a thumbnail meant a round trip back out to Supabase.
    When that call fails the endpoint returns 502, the phone shows "no image" and
    then retries the same crop forever, which is what made the app crawl. Writing
    the copy now means the common path never leaves the box.
    """
    if not (object_path and jpeg_bytes):
        return False
    try:
        from routes import CROP_CACHE_DIR
        dest = os.path.join(CROP_CACHE_DIR, object_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + ".part"
        with open(tmp, "wb") as f:
            f.write(jpeg_bytes)
        os.replace(tmp, dest)          # atomic: a reader never sees a half file
        return True
    except Exception as e:
        print(f"⚠️ Could not cache crop locally: {e}")
        return False


def upload_crop(backend: Optional[str], bucket_name: str, object_path: Optional[str],
                jpeg_bytes: Optional[bytes]) -> bool:
    """Store one detection crop. Local disk is the only backend now."""
    return cache_crop_locally(object_path, jpeg_bytes)


def upload_and_save_pin_task(bucket_name: str, unique_filename: Optional[str], jpeg_bytes: Optional[bytes], pin_data: dict, is_update: bool = False, storage_backend: Optional[str] = None):
    """
    Write one detection crop to disk.

    The pin row itself is no longer sent anywhere: the live feed, the dashboard
    and the export all read the in-memory task, and the finished patrol is saved
    to disk when the run ends. The database insert that used to live here was
    pure overhead — one round trip per detection, several hundred per flight,
    for data nothing read back.
    """
    upload_crop(storage_backend, bucket_name, unique_filename, jpeg_bytes)

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the distance in meters between two GPS coordinates using the Haversine formula."""
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

# In-memory store for background task statuses
PROCESSING_TASKS = {}

# The pipeline stages surfaced to the dashboard, in execution order. The Live
# Monitor moves a spotlight along these, expanding one at a time.
#
# Labels are deliberately plain English: the audience for this screen is
# volunteers and agency staff, not the people who wrote the detector. Where a
# stage has a real technical name worth crediting, it goes in `tag` — shown as a
# small badge beside the plain title rather than as the title itself.
PIPELINE_STAGES = [
    {"key": "ingest", "label": "Reading the flight video",
     "detail": "Opening the drone footage and checking how many frames there are to review.",
     "tag": None},
    {"key": "telemetry", "label": "Matching the GPS trail",
     "detail": "Lining up every frame with where the drone was, so a find can be placed on a map.",
     "tag": None},
    {"key": "weights", "label": "Fetching the litter model",
     "detail": "Downloading the trained model that knows what beach litter looks like from the air.",
     "tag": None},
    {"key": "model", "label": "Waking up the detectors",
     "detail": "Loading that model onto every available processor so frames can be shared out.",
     "tag": None},
    {"key": "slicing", "label": "Zooming into every corner",
     "detail": "A bottle from 40m up is only a few pixels wide. Each frame is split into "
               "overlapping close-ups so small litter is examined at full detail instead of "
               "being shrunk away.",
     "tag": "SAHI"},
    {"key": "inference", "label": "Scanning for litter",
     "detail": "Checking every close-up for litter, then merging the overlaps so one bottle "
               "is counted once rather than three times.",
     "tag": "SAHI"},
    {"key": "georeference", "label": "Pinning finds to the map",
     "detail": "Turning each find's position in the frame into a real latitude and longitude "
               "on the beach.",
     "tag": None},
    {"key": "publish", "label": "Alerting volunteers",
     "detail": "Sending each pin to the volunteer app so cleanup crews see it straight away.",
     "tag": None},
    {"key": "export", "label": "Preparing the agency report",
     "detail": "Packaging the findings as a spreadsheet, a map layer and a PDF for NEA and "
               "municipal waste teams.",
     "tag": None},
]


def build_initial_stages():
    """Fresh stage list for a new task, all pending."""
    return [
        {"key": s["key"], "label": s["label"], "detail": s["detail"],
         "tag": s["tag"], "status": "pending", "metric": None}
        for s in PIPELINE_STAGES
    ]


def set_stage(task_id: str, key: str, status: str, detail: Optional[str] = None,
              metric: Optional[str] = None):
    """
    Marks a pipeline stage as pending / active / completed / failed.

    Every earlier stage is implicitly completed when a later one goes active, so
    the UI never shows a gap if a stage finishes too fast to observe.
    """
    task = PROCESSING_TASKS.get(task_id)
    if not task:
        return

    stages = task.get("stages", [])
    index = next((i for i, s in enumerate(stages) if s["key"] == key), None)
    if index is None:
        return

    if status == "active":
        for earlier in stages[:index]:
            if earlier["status"] in ("pending", "active"):
                earlier["status"] = "completed"

    stages[index]["status"] = status
    if detail is not None:
        stages[index]["detail"] = detail
    if metric is not None:
        stages[index]["metric"] = metric


def add_log(task_id: str, message: str):
    """Utility to append timestamped logs to task log list."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    if task_id in PROCESSING_TASKS:
        PROCESSING_TASKS[task_id]["console_logs"].append(log_line)
        print(f"[Task {task_id}] {message}")

def persist_task_status_to_db(task_id: str, mission_id: Optional[str]):
    """
    Snapshot the run to disk so it survives a restart.

    Used to update a `description` column in Supabase every few seconds with the
    whole task serialised — a large write to another continent on a timer. The
    same snapshot now goes to a local file, which is what the phone view falls
    back to when nothing is running.
    """
    task = PROCESSING_TASKS.get(task_id)
    if not task:
        return
    import local_store
    local_store.save_mission(task)

def start_processing_task(video_path: str, telemetry_path: str, model_path: str, interval_ms: int = 1000,
                          min_confidence: float = 0.35, mission_id: Optional[str] = None,
                          supabase_video_path: Optional[str] = None, gcs_video_path: Optional[str] = None,
                          sahi_enabled: bool = True, slice_size: int = 512, overlap_ratio: float = 0.2,
                          workers: Optional[int] = None, include_full_frame: bool = True) -> str:
    """Creates a new task and launches the processing thread."""
    task_id = mission_id if mission_id else str(uuid.uuid4())

    # One patrol at a time. Clear the previous run's stored mission, annotated
    # frames and crops before this one starts, so the audience never sees two
    # flights mixed together and the caches do not grow for the life of the box.
    import local_store
    before_mb = local_store.disk_usage_mb()
    local_store.purge_previous(keep_task_id=task_id)
    PROCESSING_TASKS.clear()
    if before_mb:
        print(f"🧹 Cleared the previous patrol ({before_mb} MB).")

    device, resolved_workers, batch_size = plan_execution(workers)
    PROCESSING_TASKS[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress_percent": 0,
        "current_time_s": 0.0,
        "duration_s": 0.0,
        "console_logs": [],
        "detections": [],
        # Frames with their boxes already drawn on, newest last. The phone plays
        # these instead of the raw video, so a box can never drift off its frame.
        "frames": [],
        "clusters": [],
        "flight_path": [],
        # Filled from telemetry once parsed; drives the altitude readout on both
        # the operator dashboard and the public phone view.
        "altitude": None,
        "stages": build_initial_stages(),
        "sahi": {
            "enabled": sahi_enabled,
            "slice_size": slice_size,
            "overlap_ratio": overlap_ratio,
            "workers": resolved_workers,
            "device": device,
            "batch_size": batch_size,
            "cpu_cores": os.cpu_count() or 0,
            # Which slicing implementation is actually running: the upstream SAHI
            # library, or our built-in fallback slicer.
            "backend": sahi_engine.BACKEND_SAHI if sahi_engine.SAHI_AVAILABLE else sahi_engine.BACKEND_BUILTIN,
            "backend_label": sahi_engine.backend_status()["label"],
            "include_full_frame": include_full_frame,
            "tiles_per_frame": 0,
            "tiles_processed": 0,
            "frames_processed": 0,
            "frames_total": 0,
            "frames_per_second": 0.0,
            "raw_detections": 0,
            "detections_placed": 0,
            "merged_detections": 0,
        },
        "error": None
    }

    # Launch worker thread
    thread = threading.Thread(
        target=video_processing_worker,
        args=(task_id, video_path, telemetry_path, model_path, interval_ms, min_confidence, mission_id,
              supabase_video_path, gcs_video_path, sahi_enabled, slice_size, overlap_ratio, resolved_workers,
              device, batch_size, include_full_frame),
        daemon=True
    )
    thread.start()
    return task_id

def handle_frame_detections(task_id: str, mission_id: Optional[str], detections: list, frame,
                            current_time_ms: float, interpolator) -> int:
    """
    Georeferences one frame's merged detections and publishes them.

    Runs in the parent process after SAHI inference returns, so all database and
    storage writes stay on one connection pool. Detections arriving here have
    already been NMS-merged across tiles, so each one is a distinct physical
    object within this frame; cross-frame de-duplication is the clustering below.

    Returns the number of detections recorded.
    """
    from routes import supabase_client, gcs_client

    if not detections:
        return 0

    frame_height, frame_width = frame.shape[:2]
    drone_state = interpolator.get_location(current_time_ms)
    recorded = 0

    for det in detections:
        class_name = det["class_name"]
        conf = det["confidence"]
        x1, y1, x2, y2 = int(det["x1"]), int(det["y1"]), int(det["x2"]), int(det["y2"])
        x_center = (x1 + x2) / 2
        y_center = (y1 + y2) / 2

        # Project the pixel location onto the ground using drone pose.
        target_lat, target_lon = georeference_box(
            x_center=x_center,
            y_center=y_center,
            frame_width=frame_width,
            frame_height=frame_height,
            drone_lat=drone_state["latitude"],
            drone_lon=drone_state["longitude"],
            drone_alt=drone_state["altitude"],
            drone_heading=drone_state["heading"],
            fov_degrees=59.0
        )

        # Cross-frame de-duplication by spatial proximity. Frame-parallel inference
        # rules out Bot-SORT track IDs, so proximity is the sole association key —
        # it also correctly merges revisits of the same litter on a later pass.
        matching_cluster = None
        for cluster in PROCESSING_TASKS[task_id].get("clusters", []):
            if cluster["class"] == class_name:
                dist = haversine_distance(target_lat, target_lon, cluster["avg_latitude"], cluster["avg_longitude"])
                if dist <= 3.0:
                    matching_cluster = cluster
                    break

        # Crop the detected object out of the frame for the volunteer's photo.
        crop_y1, crop_y2 = max(0, y1), min(frame_height, y2)
        crop_x1, crop_x2 = max(0, x1), min(frame_width, x2)
        crop_img = frame[crop_y1:crop_y2, crop_x1:crop_x2]
        if crop_img.size == 0:
            continue

        _, jpeg_buffer = cv2.imencode('.jpg', crop_img)
        jpeg_bytes = jpeg_buffer.tobytes()
        bucket_name = settings.GCS_BUCKET_NAME

        if matching_cluster:
            sighting = {
                "timestamp_s": current_time_ms / 1000,
                "latitude": target_lat,
                "longitude": target_lon,
                "confidence": conf
            }
            matching_cluster["sightings"].append(sighting)

            # Averaging every sighting tightens the GPS estimate as evidence accrues.
            n = len(matching_cluster["sightings"])
            matching_cluster["avg_latitude"] = sum(s["latitude"] for s in matching_cluster["sightings"]) / n
            matching_cluster["avg_longitude"] = sum(s["longitude"] for s in matching_cluster["sightings"]) / n

            should_upload_new_crop = conf > matching_cluster["max_confidence"]
            unique_filename = None
            upload_jpeg_bytes = None

            crop_backend = None
            if should_upload_new_crop:
                crop_backend, unique_filename, image_url = plan_crop_destination(bucket_name)
                matching_cluster["max_confidence"] = conf
                matching_cluster["image_url"] = image_url
                upload_jpeg_bytes = jpeg_bytes
            else:
                image_url = matching_cluster["image_url"]

            pin_id = matching_cluster["db_pin_id"]
            pin_data = {
                "id": pin_id,
                "latitude": matching_cluster["avg_latitude"],
                "longitude": matching_cluster["avg_longitude"],
                "confidence": matching_cluster["max_confidence"],
                "image_url": matching_cluster["image_url"]
            }

            db_upload_executor.submit(
                upload_and_save_pin_task, bucket_name, unique_filename, upload_jpeg_bytes,
                pin_data, True, crop_backend
            )

            update_msg = (f"🔄 Refined cluster for {class_name} (now {n} sightings). "
                          f"Approx GPS: ({matching_cluster['avg_latitude']:.6f}, {matching_cluster['avg_longitude']:.6f})")
            update_msg += " [Database Updated -> Real-time Pushed to Mobile Client]" if supabase_client else " [Mock Fallback]"
            add_log(task_id, update_msg)
        else:
            crop_backend, unique_filename, image_url = plan_crop_destination(bucket_name)

            pin_id = str(uuid.uuid4())
            pin_data = {
                "id": pin_id,
                "latitude": target_lat,
                "longitude": target_lon,
                "confidence": conf,
                "image_url": image_url,
                "status": "detected",
                "detected_at": datetime.datetime.utcnow().isoformat()
            }
            if mission_id:
                pin_data["mission_id"] = mission_id

            db_upload_executor.submit(
                upload_and_save_pin_task, bucket_name, unique_filename, jpeg_bytes,
                pin_data, False, crop_backend
            )

            PROCESSING_TASKS[task_id].setdefault("clusters", []).append({
                "id": pin_id,
                "db_pin_id": pin_id,
                "track_id": None,
                "class": class_name,
                "avg_latitude": target_lat,
                "avg_longitude": target_lon,
                "max_confidence": conf,
                "image_url": image_url,
                "sightings": [{
                    "timestamp_s": current_time_ms / 1000,
                    "latitude": target_lat,
                    "longitude": target_lon,
                    "confidence": conf
                }]
            })

            tile_evidence = det.get("merged_from", 1)
            det_msg = (f"🚨 Detected {class_name} ({conf:.2%}) at {current_time_ms/1000:.1f}s "
                       f"across {tile_evidence} tile hit(s). GPS: ({target_lat:.6f}, {target_lon:.6f})")
            det_msg += " [Saved to Database -> Real-time Pushed to Mobile Client]" if supabase_client else " [Mock Fallback]"
            add_log(task_id, det_msg)

        # Normalised box (0-1) alongside the GPS fix, so a player can draw the
        # detection back onto the footage at any resolution — the mobile replay
        # shows real boxes on the real frame rather than a re-enactment.
        PROCESSING_TASKS[task_id]["detections"].append({
            "id": pin_id,
            "timestamp_s": current_time_ms / 1000,
            "class": class_name,
            "confidence": conf,
            "latitude": target_lat,
            "longitude": target_lon,
            "image_url": image_url,
            "tile_hits": det.get("merged_from", 1),
            "box": [
                round(max(0.0, min(1.0, det["x1"] / frame_width)), 5),
                round(max(0.0, min(1.0, det["y1"] / frame_height)), 5),
                round(max(0.0, min(1.0, det["x2"] / frame_width)), 5),
                round(max(0.0, min(1.0, det["y2"] / frame_height)), 5),
            ],
        })
        recorded += 1

    return recorded


def video_processing_worker(task_id: str, video_path: str, telemetry_path: str, model_path: str, interval_ms: int, min_confidence: float, mission_id: Optional[str] = None, supabase_video_path: Optional[str] = None, gcs_video_path: Optional[str] = None, sahi_enabled: bool = True, slice_size: int = 512, overlap_ratio: float = 0.2, workers: Optional[int] = None, device: str = "cpu", batch_size: int = 4, include_full_frame: bool = True):
    """Background worker that executes SAHI-tiled YOLO inference and georeferencing."""
    from routes import supabase_client, gcs_client
    PROCESSING_TASKS[task_id]["status"] = "processing"
    sahi_state = PROCESSING_TASKS[task_id]["sahi"]

    add_log(task_id, "🚀 Starting SAHI multi-core processing pipeline...")
    add_log(task_id, f"   Model: {os.path.basename(model_path)}")
    add_log(task_id, f"   Sampling Interval: {interval_ms}ms")
    add_log(task_id, f"   Confidence Threshold: {min_confidence:.2f}")
    add_log(task_id, f"   SAHI: {'ENABLED' if sahi_enabled else 'disabled'} "
                     f"(tile {slice_size}px, overlap {int(overlap_ratio * 100)}%, "
                     f"full-frame pass {'on' if include_full_frame else 'off'})")
    add_log(task_id, f"   Slicing backend: {sahi_state['backend_label']}")
    if not sahi_engine.SAHI_AVAILABLE and sahi_enabled:
        add_log(task_id, "⚠️  The `sahi` package is not installed — falling back to the built-in "
                         "slicer. Install it with `pip install sahi` to match the tuned Colab results.")
    device_label = {"mps": "Apple Silicon GPU (MPS)", "cuda": "NVIDIA GPU (CUDA)"}.get(device, "CPU")
    add_log(task_id, f"   Compute device: {device_label} | Workers: {workers} | Tile batch: {batch_size}")
    add_log(task_id, f"   CPU cores detected: {os.cpu_count()}")
    set_stage(task_id, "ingest", "active")
    persist_task_status_to_db(task_id, mission_id)

    pool = None
    serial_infer = None
    cap = None

    try:
        # 1. Load flight telemetry
        set_stage(task_id, "telemetry", "active")
        add_log(task_id, "📍 Parsing flight log telemetry...")
        interpolator = TelemetryInterpolator()
        if telemetry_path.lower().endswith('.srt'):
            interpolator.load_from_srt(telemetry_path)
        else:
            interpolator.load_from_csv(telemetry_path)

        add_log(task_id, f"✅ Telemetry loaded. Total logs: {len(interpolator.telemetry_data)}")

        # Which altitude the projection maths will use decides how far detections
        # land from the drone, so never leave it implicit.
        td = interpolator.telemetry_data
        if td is not None and not td.empty and "altitude" in td:
            alt_lo, alt_hi = float(td["altitude"].min()), float(td["altitude"].max())
            note = ""
            if "rel_altitude" in td and "abs_altitude" in td:
                rel_hi = float(td["rel_altitude"].max())
                if abs(alt_hi - rel_hi) > 0.01:
                    note = (f" (height above takeoff was only {rel_hi:.1f}m — too low to have "
                            f"produced survey footage, so height above sea level is used)")
            # Surfaced to both dashboards: altitude is what sets the ground
            # footprint, so it is the number that explains the detections.
            PROCESSING_TASKS[task_id]["altitude"] = {
                "min": round(alt_lo, 1),
                "max": round(alt_hi, 1),
                "avg": round(float(td["altitude"].mean()), 1),
                "source": "above sea level" if note else "above takeoff",
            }
            add_log(task_id, f"📏 Flight altitude: {alt_lo:.1f}–{alt_hi:.1f}m{note}")
            if alt_hi < 5:
                add_log(task_id, "⚠️  That altitude looks too low for aerial survey — detections will "
                                 "be placed very close to the drone. Set TELEMETRY_ALTITUDE_SOURCE if wrong.")
        set_stage(task_id, "telemetry", "completed",
                  metric=f"{len(interpolator.telemetry_data)} GPS fixes")

        # Capture full flight path for the dashboard map
        flight_path = []
        if interpolator.telemetry_data is not None and not interpolator.telemetry_data.empty:
            for _, row in interpolator.telemetry_data.iterrows():
                flight_path.append({
                    "lat": float(row['latitude']),
                    "lng": float(row['longitude']),
                    "alt": float(row['altitude']),
                    "heading": float(row['heading'])
                })
        PROCESSING_TASKS[task_id]["flight_path"] = flight_path
        persist_task_status_to_db(task_id, mission_id)

        # 1b. Resolve the weights. The operator may point at a bundled file, an
        # uploaded .pt, or a Google Drive / URL checkpoint that has to be fetched
        # and cached before any worker can load it.
        set_stage(task_id, "weights", "active")
        add_log(task_id, "🎯 Resolving detection weights...")
        try:
            model_path = resolve_model_path(model_path, log=lambda m: add_log(task_id, f"   {m}"))
        except ValueError as weights_err:
            set_stage(task_id, "weights", "failed", detail=str(weights_err))
            raise
        weights_size_mb = os.path.getsize(model_path) / 1e6 if os.path.exists(model_path) else 0
        add_log(task_id, f"✅ Weights ready: {os.path.basename(model_path)}"
                         + (f" ({weights_size_mb:.1f}MB)" if weights_size_mb else ""))
        set_stage(task_id, "weights", "completed",
                  metric=f"{weights_size_mb:.0f}MB" if weights_size_mb else "ready")
        persist_task_status_to_db(task_id, mission_id)

        # 2. Open the video first so slicing geometry can be derived from real dimensions
        set_stage(task_id, "model", "active")
        add_log(task_id, "🎬 Opening flight video...")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Failed to open video file at: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_ms = (total_frames / fps) * 1000 if fps > 0 else 0

        add_log(task_id, f"🎥 Video: {frame_width}x{frame_height}, {total_frames} frames, "
                         f"{fps:.2f} FPS, {int(duration_ms/1000)}s duration.")

        frame_step = max(1, round((interval_ms / 1000.0) * fps))
        frames_to_process = max(1, math.ceil(total_frames / frame_step)) if total_frames > 0 else 0
        add_log(task_id, f"📊 Frame step: {frame_step} → {frames_to_process} frames queued for inference.")

        # 3. Plan the SAHI tile decomposition
        set_stage(task_id, "slicing", "active")
        if sahi_enabled:
            # Ask the active backend for the grid so the figure shown is the real
            # workload rather than an approximation of it.
            tiles_per_frame = sahi_engine.sahi_tile_count(
                frame_width, frame_height, slice_size, slice_size, overlap_ratio
            )
            add_log(task_id, f"🔲 SAHI decomposition: each {frame_width}x{frame_height} frame → "
                             f"{tiles_per_frame} overlapping {slice_size}px tiles "
                             f"({int(overlap_ratio * 100)}% overlap).")
            add_log(task_id, f"   Small objects are inspected at native resolution instead of being "
                             f"downscaled away — this is what makes bottle-sized litter detectable from altitude.")
        else:
            tiles_per_frame = 1
            add_log(task_id, "🔲 SAHI disabled — running standard whole-frame inference.")

        sahi_state["tiles_per_frame"] = tiles_per_frame
        sahi_state["frames_total"] = frames_to_process
        set_stage(task_id, "slicing", "completed",
                  metric=f"{tiles_per_frame} tiles/frame")
        persist_task_status_to_db(task_id, mission_id)

        # 4. Spin up the inference pool — one YOLO model per core
        infer_config = {
            "min_confidence": min_confidence,
            "slice_width": slice_size,
            "slice_height": slice_size,
            "overlap_ratio": overlap_ratio,
            "include_full_frame": include_full_frame,
            "batch_size": batch_size,
            "iou_threshold": 0.4,
            "device": device,
            "sahi_enabled": sahi_enabled,
        }
        if not sahi_enabled:
            # A slice larger than the frame collapses the grid to a single
            # whole-frame tile, so the same code path serves both modes.
            infer_config["slice_width"] = max(frame_width, 1) * 2
            infer_config["slice_height"] = max(frame_height, 1) * 2
            infer_config["include_full_frame"] = False

        add_log(task_id, f"🧠 Loading detection weights across {workers} worker process(es) on {device_label}...")
        set_stage(task_id, "model", "active",
                  detail=f"Loading the model onto {workers} processor{'s' if workers != 1 else ''} "
                         f"so frames can be checked in parallel.")

        try:
            pool = SahiInferencePool(model_path, infer_config, workers=workers).__enter__()
            add_log(task_id, f"✅ Inference pool online: {workers} worker(s) on {device_label}.")
        except Exception as pool_err:
            # Never fail a mission because the sandbox forbids spawning processes.
            add_log(task_id, f"⚠️ Could not start worker pool ({pool_err}). Falling back to single process.")
            serial_infer = run_serial(model_path, infer_config)
            workers = 1
            sahi_state["workers"] = 1

        set_stage(task_id, "model", "completed", metric=f"{workers}x on {device.upper()}")
        set_stage(task_id, "inference", "active")
        persist_task_status_to_db(task_id, mission_id)

        # 5. Read → infer → georeference.
        #
        # The reader thread stays ahead of the pool by keeping `max_inflight`
        # frames queued, so no core ever idles waiting on video decode. Results
        # are consumed in submission order, which keeps the terminal log, the map
        # and the cluster averaging in true chronological order.
        max_inflight = max(2, workers * 2)
        inflight = deque()

        frame_idx = 0
        detections_count = 0
        raw_detection_count = 0
        frames_done = 0
        tiles_done = 0
        start_time = time.time()
        last_persist = 0.0

        # persist_task_status_to_db serialises the whole task — logs, every
        # detection, every cluster and the full flight path — into one row. SAHI
        # pushes detection counts high enough that doing this per frame becomes a
        # multi-megabyte write per frame, so it is throttled. The dashboard polls
        # the in-memory task once a second and is unaffected; this only paces the
        # database mirror used for reload-after-restart.
        PERSIST_INTERVAL_S = 3.0

        def degrade_to_serial(reason: str):
            """
            Abandons the worker pool and finishes the survey in-process.

            A pool can die mid-run (a worker OOMs, the GPU context is lost, the
            sandbox refuses a respawn). Losing the remaining frames of a patrol is
            far worse than finishing them slowly, so the run continues single-process
            rather than failing the mission.
            """
            nonlocal pool, serial_infer, workers
            add_log(task_id, f"⚠️ Inference pool lost ({reason}). Falling back to single-process mode.")
            try:
                if pool:
                    pool.__exit__(None, None, None)
            except Exception:
                pass
            pool = None
            inflight.clear()
            serial_infer = run_serial(model_path, infer_config)
            workers = 1
            sahi_state["workers"] = 1

        def drain_one():
            """Pops the oldest in-flight frame and publishes its detections."""
            nonlocal detections_count, raw_detection_count, frames_done, tiles_done, last_persist

            # `frame_source` is JPEG bytes from the pool path, or the already
            # decoded frame from the in-process path.
            future, frame_source, time_ms = inflight.popleft()
            if hasattr(future, "result"):
                # Bounded wait. Two missions running at once each build their own
                # accelerator pool, and the contention can wedge a worker so the
                # future never resolves — which used to hang the mission forever,
                # leaving the UI spinning and temp files uncleaned. A frame is
                # worth at most FRAME_TIMEOUT_S; past that, drop it and continue.
                try:
                    result = future.result(timeout=FRAME_TIMEOUT_S)
                except FuturesTimeout:
                    future.cancel()
                    result = {"frame_index": -1, "time_ms": time_ms, "detections": [],
                              "tile_count": 0, "backend": None,
                              "error": f"timed out after {FRAME_TIMEOUT_S}s"}
            else:
                result = future

            if result.get("error"):
                add_log(task_id, f"⚠️ Frame at {time_ms/1000:.1f}s failed inference: {result['error']}")

            frames_done += 1
            tiles_done += result.get("tile_count", 0)

            # Workers report which slicing backend actually loaded the weights. It
            # can differ from the parent's guess if SAHI failed to load them there,
            # so trust the worker and correct the dashboard on the first frame.
            worker_backend = result.get("backend")
            if worker_backend and worker_backend != sahi_state.get("backend"):
                sahi_state["backend"] = worker_backend
                sahi_state["backend_label"] = sahi_engine.BACKEND_LABELS.get(worker_backend, worker_backend)
                add_log(task_id, f"ℹ️  Slicing backend in use: {sahi_state['backend_label']}")

            detections = result.get("detections", [])
            raw_detection_count += sum(d.get("merged_from", 1) for d in detections)

            if detections:
                # Only pay the decode cost when there is something to crop.
                frame = (frame_source if isinstance(frame_source, np.ndarray)
                         else cv2.imdecode(np.frombuffer(frame_source, dtype=np.uint8), cv2.IMREAD_COLOR))
                if frame is not None:
                    set_stage(task_id, "georeference", "active")
                    detections_count += handle_frame_detections(
                        task_id, mission_id, detections, frame, time_ms, interpolator
                    )
                    # Publish the analysed frame with its boxes burned in. Done
                    # here, where the decoded frame and its detections are both
                    # in hand, so no second decode is needed.
                    shot = write_annotated_frame(task_id, frame, detections, time_ms)
                    if shot:
                        PROCESSING_TASKS[task_id]["frames"].append(shot)
                    set_stage(task_id, "publish", "active",
                              metric=f"{len(PROCESSING_TASKS[task_id]['clusters'])} pins live")

            # Progress and live throughput stats for the dashboard
            elapsed = max(1e-6, time.time() - start_time)
            sahi_state["frames_processed"] = frames_done
            sahi_state["tiles_processed"] = tiles_done
            sahi_state["frames_per_second"] = round(frames_done / elapsed, 2)
            sahi_state["raw_detections"] = raw_detection_count
            sahi_state["detections_placed"] = detections_count
            # Distinct physical objects after cross-frame clustering — this is the
            # number that matters operationally (one pin per piece of litter).
            sahi_state["merged_detections"] = len(PROCESSING_TASKS[task_id]["clusters"])

            progress = min(99, int((frames_done / frames_to_process) * 100)) if frames_to_process else 0
            PROCESSING_TASKS[task_id]["progress_percent"] = progress
            PROCESSING_TASKS[task_id]["current_time_s"] = round(time_ms / 1000, 1)
            PROCESSING_TASKS[task_id]["duration_s"] = round(duration_ms / 1000, 1)

            now = time.time()
            if now - last_persist >= PERSIST_INTERVAL_S:
                last_persist = now
                db_upload_executor.submit(persist_task_status_to_db, task_id, mission_id)

        while True:
            # Only the sampled frames are decoded. grab() advances the demuxer
            # without running the (expensive at 4K) decode, which is the difference
            # between touching ~4% of frames and all of them.
            if frame_idx % frame_step != 0:
                if not cap.grab():
                    break
                frame_idx += 1
                continue

            success, frame = cap.read()
            if not success:
                break

            current_time_ms = (frame_idx / fps) * 1000 if fps > 0 else 0.0

            if pool:
                try:
                    jpeg_bytes = pool.encode_frame(frame)
                    future = pool.submit_jpeg(frame_idx, current_time_ms, jpeg_bytes)
                    inflight.append((future, jpeg_bytes, current_time_ms))

                    # Backpressure: keep the queue deep enough to saturate the pool
                    # but bounded so encoded frames cannot pile up in memory.
                    while len(inflight) >= max_inflight:
                        drain_one()
                except BrokenProcessPool as e:
                    degrade_to_serial(str(e))

            if not pool:
                # No process boundary, so keep the decoded frame for cropping
                # instead of paying an encode/decode round trip.
                result = serial_infer(frame_idx, current_time_ms, frame)
                inflight.append((result, frame, current_time_ms))
                drain_one()

            frame_idx += 1

        # Drain whatever is still in flight
        while inflight:
            try:
                drain_one()
            except BrokenProcessPool as e:
                # Anything still queued when the pool dies is unrecoverable; the
                # frames already published stand, and the survey still completes.
                add_log(task_id, f"⚠️ Discarded {len(inflight)} in-flight frame(s): {e}")
                inflight.clear()

        # cap and pool are released by the finally block, which covers the error
        # paths too.
        elapsed_total = time.time() - start_time
        set_stage(task_id, "inference", "completed",
                  metric=f"{tiles_done} tiles in {elapsed_total:.1f}s")
        set_stage(task_id, "georeference", "completed",
                  metric=f"{detections_count} detections placed")
        set_stage(task_id, "publish", "completed",
                  metric=f"{len(PROCESSING_TASKS[task_id]['clusters'])} pins published")
        set_stage(task_id, "export", "completed", metric="CSV · GeoJSON · PDF")

        PROCESSING_TASKS[task_id]["progress_percent"] = 100
        PROCESSING_TASKS[task_id]["current_time_s"] = round(duration_ms / 1000, 1)
        PROCESSING_TASKS[task_id]["status"] = "completed"

        unique_pins = len(PROCESSING_TASKS[task_id]["clusters"])
        add_log(task_id, f"🏁 Processing complete in {elapsed_total:.1f}s.")
        add_log(task_id, f"   Frames analysed: {frames_done} | Tiles inferred: {tiles_done} "
                         f"| Throughput: {sahi_state['frames_per_second']} frames/s "
                         f"on {workers} worker(s) / {device_label}")
        add_log(task_id, f"   Raw tile hits: {raw_detection_count} → merged into {unique_pins} unique litter pins.")
        add_log(task_id, "📤 Evidence package ready for government agency export (CSV / GeoJSON / PDF).")
        persist_task_status_to_db(task_id, mission_id)

    except Exception as e:
        PROCESSING_TASKS[task_id]["status"] = "failed"
        PROCESSING_TASKS[task_id]["error"] = str(e)
        add_log(task_id, f"❌ Task failed with error: {e}")
        persist_task_status_to_db(task_id, mission_id)
    finally:
        # Release the worker pool and video handle on every exit path. Without this
        # a failed survey orphans one process per worker — each holding a loaded
        # YOLO model — and leaks the capture file descriptor for the life of the
        # server, so repeated failures exhaust memory and fds.
        try:
            if pool:
                pool.__exit__(None, None, None)
        except Exception as pool_close_err:
            print(f"Failed to shut down inference pool: {pool_close_err}")
        try:
            if cap is not None:
                cap.release()
        except Exception as cap_close_err:
            print(f"Failed to release video capture: {cap_close_err}")

        # 4. Cleanup temporary files
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(telemetry_path):
                os.remove(telemetry_path)
            if model_path and "temp_uploads" in model_path and os.path.exists(model_path):
                os.remove(model_path)
            add_log(task_id, "🧹 Temporary files cleaned up.")
            
            # Clean up video file from GCS if uploaded there
            if gcs_video_path:
                add_log(task_id, f"🧹 Cleaning up uploaded video from GCS: {gcs_video_path}...")
                try:
                    if gcs_client:
                        bucket = gcs_client.bucket(settings.GCS_BUCKET_NAME)
                        blob = bucket.blob(gcs_video_path)
                        blob.delete()
                        add_log(task_id, "✅ GCS video file cleaned up.")
                except Exception as store_del_err:
                    add_log(task_id, f"⚠️ Failed to remove video from GCS: {store_del_err}")
            
            # Clean up video file from Supabase Storage if uploaded there
            if supabase_video_path:
                add_log(task_id, f"🧹 Cleaning up uploaded video from storage: {supabase_video_path}...")
                try:
                    if supabase_client:
                        supabase_client.storage.from_("litter-images").remove([supabase_video_path])
                        add_log(task_id, "✅ Storage video file cleaned up.")
                except Exception as store_del_err:
                    add_log(task_id, f"⚠️ Failed to remove video from storage: {store_del_err}")
        except Exception as cleanup_err:
            print(f"Failed to cleanup temp files: {cleanup_err}")
