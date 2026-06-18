import os
import uuid
import time
import datetime
import math
import threading
import cv2
from ultralytics import YOLO
from typing import Optional

from georeferencing import TelemetryInterpolator, georeference_box
from config import settings
# supabase_client and gcs_client are dynamically imported inside functions to avoid circular import issues
from concurrent.futures import ThreadPoolExecutor

# Thread pool for asynchronous GCS uploads and Supabase writes
db_upload_executor = ThreadPoolExecutor(max_workers=4)

def upload_and_save_pin_task(bucket_name: str, unique_filename: Optional[str], jpeg_bytes: Optional[bytes], pin_data: dict, is_update: bool = False):
    """Background task to upload detection crop to GCS and insert/update pin in Supabase."""
    from routes import supabase_client, gcs_client
    # 1. Upload to GCS if image bytes are provided
    if unique_filename and jpeg_bytes and gcs_client:
        try:
            bucket = gcs_client.bucket(bucket_name)
            blob = bucket.blob(unique_filename)
            blob.upload_from_string(jpeg_bytes, content_type="image/jpeg")
        except Exception as e:
            print(f"⚠️ Background GCS upload failed: {e}")
            
    # 2. Save/Update pin in Supabase DB
    if supabase_client:
        try:
            if is_update:
                supabase_client.table("litter_pins").update({
                    "latitude": pin_data["latitude"],
                    "longitude": pin_data["longitude"],
                    "confidence": pin_data["confidence"],
                    "image_url": pin_data["image_url"]
                }).eq("id", pin_data["id"]).execute()
            else:
                supabase_client.table("litter_pins").insert(pin_data).execute()
        except Exception as e:
            print(f"⚠️ Background Supabase database operation failed: {e}")

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

def add_log(task_id: str, message: str):
    """Utility to append timestamped logs to task log list."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    if task_id in PROCESSING_TASKS:
        PROCESSING_TASKS[task_id]["console_logs"].append(log_line)
        print(f"[Task {task_id}] {message}")

def persist_task_status_to_db(task_id: str, mission_id: Optional[str]):
    """Saves the current processing task status to the database (mission description)."""
    if not mission_id or task_id not in PROCESSING_TASKS:
        return
        
    from routes import supabase_client
    if supabase_client:
        try:
            import json
            task_data = PROCESSING_TASKS[task_id]
            serialized = json.dumps({
                "task_id": task_data["task_id"],
                "status": task_data["status"],
                "progress_percent": task_data["progress_percent"],
                "current_time_s": task_data["current_time_s"],
                "duration_s": task_data["duration_s"],
                "console_logs": task_data["console_logs"],
                "detections": task_data["detections"],
                "clusters": task_data["clusters"],
                "flight_path": task_data["flight_path"],
                "error": task_data["error"]
            })
            supabase_client.table("missions").update({
                "description": serialized
            }).eq("id", mission_id).execute()
        except Exception as e:
            print(f"⚠️ Failed to persist task status to DB: {e}")

def start_processing_task(video_path: str, telemetry_path: str, model_path: str, interval_ms: int = 1000, min_confidence: float = 0.35, mission_id: Optional[str] = None, supabase_video_path: Optional[str] = None, gcs_video_path: Optional[str] = None) -> str:
    """Creates a new task and launches the processing thread."""
    task_id = mission_id if mission_id else str(uuid.uuid4())
    PROCESSING_TASKS[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress_percent": 0,
        "current_time_s": 0.0,
        "duration_s": 0.0,
        "console_logs": [],
        "detections": [],
        "clusters": [],
        "flight_path": [],
        "error": None
    }
    
    # Launch worker thread
    thread = threading.Thread(
        target=video_processing_worker,
        args=(task_id, video_path, telemetry_path, model_path, interval_ms, min_confidence, mission_id, supabase_video_path, gcs_video_path),
        daemon=True
    )
    thread.start()
    return task_id

def video_processing_worker(task_id: str, video_path: str, telemetry_path: str, model_path: str, interval_ms: int, min_confidence: float, mission_id: Optional[str] = None, supabase_video_path: Optional[str] = None, gcs_video_path: Optional[str] = None):
    """Background worker that executes YOLO inference and georeferencing."""
    from routes import supabase_client, gcs_client
    PROCESSING_TASKS[task_id]["status"] = "processing"
    add_log(task_id, "🚀 Starting video processing worker...")
    add_log(task_id, f"   Model Path: {os.path.basename(model_path)}")
    add_log(task_id, f"   Sampling Interval: {interval_ms}ms")
    add_log(task_id, f"   YOLO Confidence Threshold: {min_confidence:.2f}")
    persist_task_status_to_db(task_id, mission_id)
    
    try:
        # 1. Load flight telemetry
        add_log(task_id, "📍 Parsing flight log telemetry...")
        interpolator = TelemetryInterpolator()
        if telemetry_path.lower().endswith('.srt'):
            interpolator.load_from_srt(telemetry_path)
        else:
            interpolator.load_from_csv(telemetry_path)
            
        add_log(task_id, f"✅ Telemetry loaded. Total logs: {len(interpolator.telemetry_data)}")
        
        # Capture full flight path
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
        
        # 2. Load YOLO model
        add_log(task_id, "🧠 Loading YOLOv8 object detection model...")
        # Resolve to backend root path if necessary
        model = YOLO(model_path)
        add_log(task_id, "✅ YOLOv8 model loaded successfully.")
        persist_task_status_to_db(task_id, mission_id)
        
        # 3. Open Video File
        add_log(task_id, "🎬 Opening flight video...")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Failed to open video file at: {video_path}")
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_ms = (total_frames / fps) * 1000 if fps > 0 else 0
        
        add_log(task_id, f"🎥 Video details: {total_frames} frames, {fps:.2f} FPS, {int(duration_ms/1000)} seconds duration.")
        
        # Calculate frame step based on interval and fps
        frame_step = max(1, round((interval_ms / 1000.0) * fps))
        add_log(task_id, f"📊 Processing frame step: {frame_step} (every {interval_ms}ms at {fps:.2f} FPS)")
        
        frame_idx = 0
        detections_count = 0
        
        while frame_idx < total_frames:
            current_time_ms = (frame_idx / fps) * 1000 if fps > 0 else 0.0
            
            # Check if this frame should be processed
            if frame_idx % frame_step == 0:
                success, frame = cap.read()
                if not success:
                    break
                frame_idx += 1
            else:
                success = cap.grab()
                if not success:
                    break
                frame_idx += 1
                continue
                
            frame_height, frame_width = frame.shape[:2]
            
            # Run YOLOv8 detection with Bot-SORT tracking support
            try:
                # persist=True retains track IDs across frames; tracker="botsort.yaml" is standard
                results = model.track(frame, persist=True, tracker="botsort.yaml", conf=min_confidence, verbose=False)
            except Exception as track_err:
                # Safe fallback if tracking config/modules are unavailable
                print(f"[YOLO Track Fallback] Tracking failed: {track_err}, falling back to model()")
                results = model(frame, conf=min_confidence, verbose=False)
            
            # Get interpolated drone state
            drone_state = interpolator.get_location(current_time_ms)
            
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = model.names[cls_id]
                    
                    # Extract track ID if assigned
                    track_id = None
                    if box.id is not None:
                        track_id = int(box.id[0])
                    
                    # We accept detections that look like litter (or any target if custom)
                    is_target = True  
                    
                    if is_target:
                        # Extract box coordinates (xyxy)
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        x_center = (x1 + x2) / 2
                        y_center = (y1 + y2) / 2
                        
                        # Run Roboflow georeferencing projection math
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
                        
                        # 1. Check for duplicate grouping (clustering)
                        # First try to match by track_id
                        matching_cluster = None
                        if track_id is not None:
                            for cluster in PROCESSING_TASKS[task_id].get("clusters", []):
                                if cluster.get("track_id") == track_id:
                                    matching_cluster = cluster
                                    break
                                    
                        # Second fallback: match by spatial proximity within 3.0 meters
                        if not matching_cluster:
                            for cluster in PROCESSING_TASKS[task_id].get("clusters", []):
                                if cluster["class"] == class_name:
                                    dist = haversine_distance(target_lat, target_lon, cluster["avg_latitude"], cluster["avg_longitude"])
                                    if dist <= 3.0:
                                        matching_cluster = cluster
                                        # Associate track_id with this cluster for future coherence
                                        if track_id is not None:
                                            cluster["track_id"] = track_id
                                        break
                                        
                        # Crop image frame of detected item
                        crop_y1, crop_y2 = max(0, y1), min(frame_height, y2)
                        crop_x1, crop_x2 = max(0, x1), min(frame_width, x2)
                        crop_img = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                        
                        # Encode to JPEG bytes
                        _, jpeg_buffer = cv2.imencode('.jpg', crop_img)
                        jpeg_bytes = jpeg_buffer.tobytes()
                        
                        bucket_name = settings.GCS_BUCKET_NAME
                        
                        if matching_cluster:
                            # Add sighting details to the cluster
                            sighting = {
                                "timestamp_s": current_time_ms / 1000,
                                "latitude": target_lat,
                                "longitude": target_lon,
                                "confidence": conf
                            }
                            matching_cluster["sightings"].append(sighting)
                            
                            # Recalculate average coordinates
                            n = len(matching_cluster["sightings"])
                            sum_lat = sum(s["latitude"] for s in matching_cluster["sightings"])
                            sum_lon = sum(s["longitude"] for s in matching_cluster["sightings"])
                            matching_cluster["avg_latitude"] = sum_lat / n
                            matching_cluster["avg_longitude"] = sum_lon / n
                            
                            should_upload_new_crop = conf > matching_cluster["max_confidence"]
                            unique_filename = None
                            upload_jpeg_bytes = None
                            
                            if should_upload_new_crop:
                                if gcs_client:
                                    unique_filename = f"detections/{uuid.uuid4()}_detection.jpg"
                                    image_url = f"https://storage.googleapis.com/{bucket_name}/{unique_filename}"
                                else:
                                    image_url = f"https://mock-storage.local/litter-images/{uuid.uuid4()}_crop.jpg"
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
                            
                            # Dispatch to thread pool executor
                            db_upload_executor.submit(
                                upload_and_save_pin_task,
                                bucket_name,
                                unique_filename,
                                upload_jpeg_bytes,
                                pin_data,
                                is_update=True
                            )
                            
                            track_desc = f"Track {track_id}" if track_id is not None else "Spatial Cluster"
                            update_msg = f"🔄 Updated {track_desc} for {class_name} (now {n} sightings). Approx GPS: ({matching_cluster['avg_latitude']:.6f}, {matching_cluster['avg_longitude']:.6f})"
                            if supabase_client:
                                update_msg += " [Database Updated -> Real-time Pushed to Mobile Client]"
                            else:
                                update_msg += " [Mock Fallback]"
                            add_log(task_id, update_msg)
                        else:
                            # Generate unique filename for GCS
                            if gcs_client:
                                unique_filename = f"detections/{uuid.uuid4()}_detection.jpg"
                                image_url = f"https://storage.googleapis.com/{bucket_name}/{unique_filename}"
                            else:
                                unique_filename = None
                                image_url = f"https://mock-storage.local/litter-images/{uuid.uuid4()}_crop.jpg"
                                
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
                                
                            # Dispatch GCS upload and Supabase save task to thread pool
                            db_upload_executor.submit(
                                upload_and_save_pin_task,
                                bucket_name,
                                unique_filename,
                                jpeg_bytes,
                                pin_data,
                                is_update=False
                            )
                            
                            new_cluster = {
                                "id": pin_id,
                                "db_pin_id": pin_id,
                                "track_id": track_id,
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
                            }
                            PROCESSING_TASKS[task_id].setdefault("clusters", []).append(new_cluster)
                            
                            track_desc = f"Track {track_id}" if track_id is not None else "New Sighting"
                            det_msg = f"🚨 Detected {track_desc} - {class_name} ({conf:.2%}) at timestamp {current_time_ms/1000:.1f}s. GPS: ({target_lat:.6f}, {target_lon:.6f})"
                            if supabase_client:
                                det_msg += " [Saved to Database -> Real-time Pushed to Mobile Client]"
                            else:
                                det_msg += " [Mock Fallback]"
                            add_log(task_id, det_msg)
                            
                        # Store in task detections list for UI rendering
                        detection_record = {
                            "id": pin_id,
                            "timestamp_s": current_time_ms / 1000,
                            "class": class_name,
                            "confidence": conf,
                            "latitude": target_lat,
                            "longitude": target_lon,
                            "image_url": image_url
                        }
                        PROCESSING_TASKS[task_id]["detections"].append(detection_record)
                        detections_count += 1
                        
            # Update Progress (on every processed frame)
            progress = min(99, int((current_time_ms / duration_ms) * 100)) if duration_ms > 0 else 0
            PROCESSING_TASKS[task_id]["progress_percent"] = progress
            PROCESSING_TASKS[task_id]["current_time_s"] = round(current_time_ms / 1000, 1)
            PROCESSING_TASKS[task_id]["duration_s"] = round(duration_ms / 1000, 1)
            
            # Persist status to database asynchronously via thread pool
            db_upload_executor.submit(persist_task_status_to_db, task_id, mission_id)
            
        cap.release()
        
        # Mark Task complete
        PROCESSING_TASKS[task_id]["progress_percent"] = 100
        PROCESSING_TASKS[task_id]["current_time_s"] = round(duration_ms / 1000, 1)
        PROCESSING_TASKS[task_id]["status"] = "completed"
        add_log(task_id, f"🏁 Processing complete! Identified and uploaded {detections_count} targets.")
        persist_task_status_to_db(task_id, mission_id)
        
    except Exception as e:
        PROCESSING_TASKS[task_id]["status"] = "failed"
        PROCESSING_TASKS[task_id]["error"] = str(e)
        add_log(task_id, f"❌ Task failed with error: {e}")
        persist_task_status_to_db(task_id, mission_id)
    finally:
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
