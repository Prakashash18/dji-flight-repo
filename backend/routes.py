from fastapi import APIRouter, Form, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import multiprocessing
import datetime
import json
import re
import os

from config import settings
from model_source import list_available_models
from sealion import SeaLionClient

# Setup Jinja2 templates folder
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# --- Storage -----------------------------------------------------------------
# Everything a patrol produces now lives on this machine: crops in
# CROP_CACHE_DIR, annotated frames in frame_cache, the finished mission in
# mission_store. One flight runs at a time and the audience only ever needs the
# current one or the last one, so a database on another continent bought nothing
# and cost a great deal — a round trip per detection, `Server disconnected`
# under load, thumbnails 502'ing and phones retrying them in a loop.
#
# The clients stay None so the `if supabase_client:` guards throughout simply
# skip. Set USE_CLOUD_STORAGE=1 to put the old behaviour back, if a future
# deployment genuinely needs shared state across machines.
USE_CLOUD_STORAGE = os.environ.get("USE_CLOUD_STORAGE", "").lower() in ("1", "true", "yes")

supabase_client = None
gcs_client = None

if not USE_CLOUD_STORAGE:
    # Only the server says this. Inference workers are spawned, so they re-import
    # this module and would each repeat the banner mid-run — eight copies of it
    # scrolling past while a patrol is being processed.
    if multiprocessing.current_process().name == "MainProcess":
        print("💾 [FastAPI] Local storage mode: crops, frames and the last mission "
              "are kept on this machine. No Supabase or GCS.")
else:
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            from supabase import create_client, Client
            supabase_client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            print("🔌 [FastAPI] Supabase client initialized successfully.")
        except Exception as e:
            print(f"⚠️ [FastAPI] Failed to initialize Supabase client: {e}. Falling back to In-Memory DB.")
    else:
        print("ℹ️ [FastAPI] Supabase credentials missing. Running in In-Memory Mock DB mode.")

    try:
        from google.cloud import storage
        gcs_client = storage.Client()
        print("🔌 [FastAPI] Google Cloud Storage client initialized successfully.")
    except Exception as e:
        print(f"⚠️ [FastAPI] Failed to initialize GCS client: {e}. Signed URL generation will fail.")

router = APIRouter()
sealion = SeaLionClient()

# --- Upload handling ---
# A DJI flight is routinely 1-3 GB. Reading one with `await upload.read()` pulls
# the whole thing into a single bytes object: a 2.3 GB clip took the server from
# 308 MB to 3.0 GB resident, which on a laptop means swap thrash that looks
# exactly like a hang. Copy it through in chunks instead — Starlette has already
# spooled it to a temp file, so this is a disk-to-disk copy at flat memory.
UPLOAD_CHUNK_BYTES = 4 * 1024 * 1024


async def stream_upload_to(upload: UploadFile, dest_path: str) -> int:
    """Copy an upload to `dest_path` without holding it in memory."""
    total = 0
    await upload.seek(0)
    with open(dest_path, "wb") as f:
        while True:
            chunk = await upload.read(UPLOAD_CHUNK_BYTES)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    return total


def safe_upload_name(filename: Optional[str]) -> str:
    """
    Reduce a client-supplied filename to a bare, harmless basename.

    The name is only kept to make temp files recognisable, but it lands in a
    path — so `../../` or a leading slash from a crafted multipart part must not
    survive. Anything outside a conservative charset is dropped.
    """
    base = os.path.basename(str(filename or "")).strip()
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base).lstrip(".")
    return base[:100] or "upload"

# --- In-Memory Mock Database ---
MOCK_PINS = []
MOCK_ZONES = []
MOCK_ALERTS = []

# --- Request/Response Models ---
class ZoneCreate(BaseModel):
    name: str
    boundary_geojson: Dict[str, Any]  # GeoJSON Polygon coordinates
    created_by: Optional[str] = None
    assigned_to: Optional[str] = None

class AlertBroadcast(BaseModel):
    title: str
    message: str

# Helper to upload files to Google Cloud Storage or Mock URL
async def upload_litter_image(filename: str, file_bytes: bytes) -> str:
    if gcs_client:
        try:
            bucket_name = settings.GCS_BUCKET_NAME
            # Generate unique filename
            unique_filename = f"detections/{uuid.uuid4()}_{filename}"
            bucket = gcs_client.bucket(bucket_name)
            blob = bucket.blob(unique_filename)
            blob.upload_from_string(file_bytes, content_type="image/jpeg")
            
            # GCS public URL format
            public_url = f"https://storage.googleapis.com/{bucket_name}/{unique_filename}"
            return public_url
        except Exception as e:
            print(f"⚠️ GCS Storage Upload failed: {e}. Defaulting to mock local link.")
            
    # Mock fallback link
    return f"https://mock-storage.local/litter-images/{uuid.uuid4()}_{filename}"

# --- Endpoints ---

# 1. Litter Pins Ingestion
@router.post("/pins", status_code=201)
async def create_pin(
    latitude: float = Form(...),
    longitude: float = Form(...),
    confidence: float = Form(...),
    image: UploadFile = File(...)
):
    """
    Ingest a newly detected litter pin from the drone processing station.
    Accepts latitude, longitude, confidence score, and raw JPEG image.
    """
    image_bytes = await image.read()
    image_url = await upload_litter_image(image.filename, image_bytes)
    
    pin_id = str(uuid.uuid4())
    pin_data = {
        "id": pin_id,
        "latitude": latitude,
        "longitude": longitude,
        "confidence": confidence,
        "image_url": image_url,
        "status": "detected",
        "detected_at": datetime.datetime.utcnow().isoformat()
    }
    
    if supabase_client:
        try:
            # Insert into database (PostGIS geometry field is auto-computed via SQL trigger)
            res = supabase_client.table("litter_pins").insert(pin_data).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            print(f"⚠️ Supabase DB error during pin insert: {e}. Writing to In-Memory DB instead.")
            
    # Fallback to in-memory store
    MOCK_PINS.append(pin_data)
    return pin_data

@router.get("/pins")
async def get_pins():
    """
    Returns list of all active and resolved litter pins.
    """
    if supabase_client:
        try:
            res = supabase_client.table("litter_pins").select("*").order("detected_at", desc=True).execute()
            return res.data
        except Exception as e:
            print(f"⚠️ Supabase DB query error: {e}")
            
    return MOCK_PINS


# 1.1. Missions API
@router.get("/missions")
async def get_missions():
    """
    Returns list of all patrol missions.
    """
    if supabase_client:
        try:
            res = supabase_client.table("missions").select("*").order("mission_date", desc=True).execute()
            return res.data
        except Exception as e:
            print(f"⚠️ Supabase missions query error: {e}")
    return []

@router.post("/missions", status_code=201)
async def create_mission(title: str = Form(...), description: Optional[str] = Form(None), mission_date: Optional[str] = Form(None)):
    """
    Manually create a new patrol mission.
    """
    m_date = mission_date if mission_date else datetime.datetime.utcnow().isoformat()
    mission_data = {
        "title": title,
        "description": description,
        "mission_date": m_date
    }
    if supabase_client:
        try:
            res = supabase_client.table("missions").insert(mission_data).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            print(f"⚠️ Supabase missions insert error: {e}")
    
    # Fallback/mock creation response
    mission_data["id"] = str(uuid.uuid4())
    return mission_data

# 1.2. Profiles / Onboarding API
@router.get("/profiles")
async def get_profiles():
    """
    Returns list of all registered patrollers / profiles.
    """
    if supabase_client:
        try:
            res = supabase_client.table("profiles").select("*").order("name").execute()
            return res.data
        except Exception as e:
            print(f"⚠️ Supabase profiles query error: {e}")
    return []

@router.post("/profiles", status_code=201)
async def onboard_profile(name: str = Form(...), role: str = Form(...), preferred_language: str = Form("en")):
    """
    Onboards a new profile/volunteer directly.
    """
    profile_data = {
        "name": name,
        "role": role,
        "preferred_language": preferred_language,
        "updated_at": datetime.datetime.utcnow().isoformat()
    }
    if supabase_client:
        try:
            res = supabase_client.table("profiles").insert(profile_data).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            print(f"⚠️ Supabase profiles insert error: {e}")
            
    profile_data["id"] = str(uuid.uuid4())
    return profile_data


# 2. Cleanup Zones
@router.post("/zones", status_code=201)
async def create_zone(zone: ZoneCreate):
    """
    Create a new beach cleanup zone assignment.
    """
    zone_id = str(uuid.uuid4())
    zone_data = {
        "id": zone_id,
        "name": zone.name,
        "boundary_geojson": zone.boundary_geojson,
        "assigned_to": zone.assigned_to,
        "status": "pending",
        "created_by": zone.created_by,
        "created_at": datetime.datetime.utcnow().isoformat()
    }
    
    if supabase_client:
        try:
            res = supabase_client.table("cleanup_zones").insert(zone_data).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            print(f"⚠️ Supabase DB error during zone insert: {e}")
            
    MOCK_ZONES.append(zone_data)
    return zone_data

@router.get("/zones")
async def get_zones():
    """
    Retrieve all cleanup zones.
    """
    if supabase_client:
        try:
            res = supabase_client.table("cleanup_zones").select("*").execute()
            return res.data
        except Exception as e:
            print(f"⚠️ Supabase DB query error: {e}")
            
    return MOCK_ZONES

# 3. Multilingual Alerts (SEA-LION Integration)
@router.post("/alerts/broadcast", status_code=201)
async def broadcast_alert(broadcast: AlertBroadcast, background_tasks: BackgroundTasks):
    """
    Broadcasts an announcement. Automatically translates it into Southeast Asian languages
    (Thai, Tagalog, Indonesian, Malay, Tamil) via the SEA-LION API and writes translations to DB.
    """
    alert_id = str(uuid.uuid4())
    alert_data = {
        "id": alert_id,
        "title": broadcast.title,
        "message": broadcast.message,
        "translations": {},
        "created_at": datetime.datetime.utcnow().isoformat()
    }
    
    # Process translations asynchronously or synchronously for immediate response
    # We will compute them synchronously/sequentially here for simplicity, or in background tasks.
    # To provide instant API feedback, let's pre-populate translations and store them.
    supported_langs = ["th", "id", "tl", "ms", "ta"]
    translations = {}
    
    for lang in supported_langs:
        try:
            translated_text = await sealion.translate_text(broadcast.message, lang)
            translations[lang] = translated_text
        except Exception as e:
            print(f"⚠️ Translation failed for lang {lang}: {e}")
            translations[lang] = f"[{lang.upper()}] {broadcast.message}"
            
    alert_data["translations"] = translations
    
    if supabase_client:
        try:
            res = supabase_client.table("alerts").insert(alert_data).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            print(f"⚠️ Supabase DB error during alert insert: {e}")
            
    MOCK_ALERTS.append(alert_data)
    return alert_data

@router.get("/alerts")
async def get_alerts():
    """
    Fetch all broadcast alerts.
    """
    if supabase_client:
        try:
            res = supabase_client.table("alerts").select("*").execute()
            return res.data
        except Exception as e:
            print(f"⚠️ Supabase DB query error: {e}")
            
    return MOCK_ALERTS

# --- Georeferencing Web Dashboard & API ---

@router.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """
    Serves the flight processing dashboard.
    """
    return templates.TemplateResponse(request, "dashboard.html", {
        "available_models": list_available_models(),
        "default_model_name": settings.DEFAULT_MODEL_NAME,
        "sample_video_url": settings.SAMPLE_VIDEO_URL,
        "sample_telemetry_url": settings.SAMPLE_TELEMETRY_URL,
        "sample_poster_url": settings.SAMPLE_POSTER_URL,
        "sample_preview_url": settings.SAMPLE_PREVIEW_URL,
        "sample_location_label": settings.SAMPLE_LOCATION_LABEL,
        "map_default_lat": settings.MAP_DEFAULT_LAT,
        "map_default_lng": settings.MAP_DEFAULT_LNG,
        "map_default_zoom": settings.MAP_DEFAULT_ZOOM,
    })

# --- Public mobile demo -----------------------------------------------------

def _resolve_demo_mission() -> Optional[dict]:
    """
    Finds the mission the public demo should replay.

    Prefers an explicitly pinned DEMO_MISSION_ID so the scan-to-try experience
    never changes under visitors' feet; otherwise falls back to the most recent
    mission titled "DEMO ...", and finally to the most recent one that actually
    produced detections.
    """
    if not supabase_client:
        return None

    def _load(mission_id: str) -> Optional[dict]:
        try:
            res = supabase_client.table("missions").select("id,title,mission_date,description") \
                .eq("id", mission_id).execute()
            return res.data[0] if res.data else None
        except Exception:
            return None

    if settings.DEMO_MISSION_ID:
        row = _load(settings.DEMO_MISSION_ID)
        if row:
            return row

    try:
        res = supabase_client.table("missions").select("id,title,mission_date,description") \
            .order("mission_date", desc=True).limit(40).execute()
    except Exception as e:
        print(f"⚠️ Demo mission lookup failed: {e}")
        return None

    rows = res.data or []
    preferred = [r for r in rows if (r.get("title") or "").upper().startswith("DEMO")]
    for row in preferred + rows:
        desc = row.get("description")
        if not desc:
            continue
        try:
            task = json.loads(desc)
        except (TypeError, ValueError):
            continue
        if isinstance(task, dict) and task.get("detections"):
            return row
    return None


# --- Satellite tile proxy ---------------------------------------------------
#
# Tiles came straight from Esri, which meant every phone fetched every tile
# internationally. Proxying them onto our own origin lets a CDN cache them close
# to the audience — the first visitor pays for a tile, everyone after hits the
# edge. It also means one flaky third party can no longer blank the map.

# Only these upstreams are reachable. A free-form URL parameter here would be an
# open proxy; an allowlist keeps it a tile cache.
TILE_LAYERS = {
    "sat": ("https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}", "image/jpeg", "jpg"),
    "labels": ("https://a.basemaps.cartocdn.com/rastertiles/voyager_only_labels/"
               "{z}/{x}/{y}.png", "image/png", "png"),
    "dark": ("https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
             "image/png", "png"),
}
TILE_CACHE_DIR = "/tmp/tile_cache" if os.environ.get("K_SERVICE") else \
    os.path.join(os.path.dirname(__file__), "tile_cache")
MAX_TILE_ZOOM = 21


@router.get("/tiles/{layer}/{z}/{x}/{y_ext}")
async def get_tile(layer: str, z: int, x: int, y_ext: str):
    """
    Serves one map tile, fetching and caching it on first request.

    The `y` carries a file extension (`…/33813.jpg`) purely so a CDN in front of
    this treats it as a static image. Cloudflare's default cache keys off the
    extension, and without one every tile came back DYNAMIC — measured — which
    would put the whole basemap through the origin once per phone.
    """
    upstream = TILE_LAYERS.get(layer)
    if not upstream:
        raise HTTPException(status_code=404, detail="Unknown tile layer")
    url_tpl, media, ext = upstream

    y_str = y_ext.rsplit(".", 1)[0] if "." in y_ext else y_ext
    if not y_str.isdigit():
        raise HTTPException(status_code=404, detail="Bad tile coordinate")
    y = int(y_str)

    # Bounds-check before touching disk or the network: without this the path is
    # an unbounded disk filler.
    if not (0 <= z <= MAX_TILE_ZOOM):
        raise HTTPException(status_code=404, detail="Zoom out of range")
    limit = 1 << z
    if not (0 <= x < limit and 0 <= y < limit):
        raise HTTPException(status_code=404, detail="Tile out of range")

    cached = os.path.join(TILE_CACHE_DIR, layer, str(z), str(x), f"{y}.{ext}")
    headers = {"Cache-Control": "public, max-age=31536000, immutable"}

    if os.path.exists(cached):
        return FileResponse(cached, media_type=media, headers=headers)

    import requests
    try:
        r = requests.get(url_tpl.format(z=z, x=x, y=y), timeout=12,
                         headers={"User-Agent": "CoastalPatrol/1.0"})
        r.raise_for_status()
        body = r.content
    except Exception as e:
        # A missing tile should leave a hole in the map, not a 500 page.
        raise HTTPException(status_code=502, detail=f"Tile upstream failed: {e}")

    try:
        os.makedirs(os.path.dirname(cached), exist_ok=True)
        tmp = cached + ".part"
        with open(tmp, "wb") as f:
            f.write(body)
        os.replace(tmp, cached)
    except OSError as e:
        print(f"⚠️ Could not cache tile {layer}/{z}/{x}/{y}: {e}")

    return Response(content=body, media_type=media, headers=headers)


# --- Detection crop proxy ---------------------------------------------------
#
# Crops live in Supabase Storage, which is canonical and what the mobile app
# reads. Serving them to a demo crowd straight from there means every phone
# fetches every thumbnail internationally. This proxies them onto our origin so
# a CDN can cache them, without changing the stored image_url the app relies on.

CROP_CACHE_DIR = "/tmp/crop_cache" if os.environ.get("K_SERVICE") else \
    os.path.join(os.path.dirname(__file__), "crop_cache")
SUPABASE_IMAGE_BUCKET = "litter-images"


def _proxy_crop_url(image_url: Optional[str]) -> Optional[str]:
    """Rewrites a Supabase Storage URL to our cached proxy path."""
    if not image_url or not settings.SUPABASE_URL:
        return image_url
    prefix = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_IMAGE_BUCKET}/"
    if image_url.startswith(prefix):
        return "/api/crops/" + image_url[len(prefix):]
    return image_url


@router.get("/crops/{object_path:path}")
async def get_crop(object_path: str):
    """Serves one detection crop, fetching it from Supabase Storage once."""
    # The path is used on disk, so it must not be allowed to walk out of the
    # cache directory. Only the shapes Supabase actually produces get through.
    if not re.fullmatch(r"[A-Za-z0-9_\-/]+\.(jpg|jpeg|png)", object_path or "") \
            or ".." in object_path:
        raise HTTPException(status_code=404, detail="Bad crop path")

    cached = os.path.join(CROP_CACHE_DIR, object_path)
    headers = {"Cache-Control": "public, max-age=604800"}
    media = "image/png" if object_path.lower().endswith(".png") else "image/jpeg"

    # Read it here rather than handing the path to FileResponse, which opens the
    # file later in the response cycle. Starting a new patrol deletes the old
    # run's crops, and phones still showing the previous mission keep asking for
    # them — so `exists()` could pass and the open could then fail, surfacing as
    # a 500 and a full traceback per request.
    try:
        with open(cached, "rb") as f:
            return Response(content=f.read(), media_type=media, headers=headers)
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"⚠️ Could not read cached crop {object_path}: {e}")

    if not settings.SUPABASE_URL or supabase_client is None:
        # Local-only mode: this crop belonged to a patrol that has been cleared.
        # 404 with a short TTL so the phone stops asking; 500 made it retry.
        return Response(content=b'{"detail":"crop no longer available"}',
                        status_code=404, media_type="application/json",
                        headers={"Cache-Control": "public, max-age=60"})

    import requests
    upstream = (f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/"
                f"{SUPABASE_IMAGE_BUCKET}/{object_path}")
    try:
        r = requests.get(upstream, timeout=15)
        r.raise_for_status()
        body = r.content
    except Exception as e:
        # 404, not 502. A browser treats 502 as a transient server fault and
        # retries the image, so one unreachable crop became an endless stream of
        # requests from every phone at once — the log filled with the same few
        # ids and the app crawled. 404 is cached as "this is not coming" and
        # asked for once. Short max-age so a later upload can still appear.
        print(f"⚠️ Crop {object_path} unavailable upstream: {e}")
        return Response(
            content=b'{"detail":"crop unavailable"}',
            status_code=404,
            media_type="application/json",
            headers={"Cache-Control": "public, max-age=60"},
        )

    try:
        os.makedirs(os.path.dirname(cached), exist_ok=True)
        tmp = cached + ".part"
        with open(tmp, "wb") as f:
            f.write(body)
        os.replace(tmp, cached)
    except OSError as e:
        print(f"⚠️ Could not cache crop {object_path}: {e}")

    return Response(content=body, media_type=media, headers=headers)


@router.get("/frames/{task_id}/{name}")
async def get_annotated_frame(task_id: str, name: str):
    """
    One analysed frame with its detection boxes already drawn on.

    Each file is written once and never changes, so it is immutable as far as any
    cache is concerned — which is what lets a few hundred phones share one origin
    fetch per frame instead of each pulling the whole video.
    """
    from processing_task import FRAMES_DIR

    # Both segments land in a filesystem path, so accept only the exact shapes
    # this server generates: a task uuid and a zero-padded millisecond stamp.
    if not re.fullmatch(r"[A-Za-z0-9\-]{8,64}", task_id or "") \
            or not re.fullmatch(r"\d{4,12}\.jpg", name or ""):
        raise HTTPException(status_code=404, detail="Bad frame path")

    path = os.path.realpath(os.path.join(FRAMES_DIR, task_id, name))
    if os.path.dirname(os.path.dirname(path)) != os.path.realpath(FRAMES_DIR):
        raise HTTPException(status_code=404, detail="Bad frame path")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No such frame")

    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})


_ICON_SPRITE_PATH = os.path.join(os.path.dirname(__file__), "static", "vendor", "icons_sprite.svg")


def _icon_sprite() -> str:
    """The ten glyphs the phone demo uses, inlined.

    Phosphor ships ~600KB of icon fonts and CSS for the full set; these ten cost
    4KB as symbols. Inlined rather than linked so there is no second request and
    no cross-document `<use>` quirks.
    """
    try:
        with open(_ICON_SPRITE_PATH, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


@router.get("/demo", response_class=HTMLResponse)
async def serve_mobile_demo(request: Request):
    """Public, phone-first walkthrough of a real patrol. Meant to be scanned."""
    return templates.TemplateResponse(request, "mobile_demo.html", {
        "location": settings.SAMPLE_LOCATION_LABEL,
        "icon_sprite": _icon_sprite(),
        "map_default_lat": settings.MAP_DEFAULT_LAT,
        "map_default_lng": settings.MAP_DEFAULT_LNG,
        "map_default_zoom": settings.MAP_DEFAULT_ZOOM,
    })


@router.get("/demo/qr")
async def demo_qr(request: Request, url: Optional[str] = None):
    """
    QR code pointing at the mobile demo, as an SVG.

    Generated here rather than via an image service so it works on a laptop with
    no internet and never leaks the deployment URL to a third party.
    """
    target = url or str(request.url_for("serve_mobile_demo"))
    try:
        import qrcode
        import qrcode.image.svg

        img = qrcode.make(target, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
        import io

        buf = io.BytesIO()
        img.save(buf)
        return Response(content=buf.getvalue(), media_type="image/svg+xml")
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="QR generation needs the 'qrcode' package: pip install qrcode",
        )


# Derived views of the live task, rebuilt only when the underlying counts move.
# Every watching phone polls the same endpoint, so without this the server
# re-filters the detection list and re-projects every cluster once per request —
# O(watchers x mission size) of pure repeat work at exactly the moment the
# machine is also running inference.
_live_cache: Dict[str, Any] = {"key": None, "detections": [], "pins": []}


def _derive_live_lists(task: dict):
    """Returns (detections, pins), cached against the task's current counts."""
    key = (task.get("task_id"),
           len(task.get("detections") or ()),
           len(task.get("clusters") or ()))
    if _live_cache["key"] != key:
        detections = [dict(d, image_url=_proxy_crop_url(d.get("image_url")))
                      for d in task.get("detections", []) if d.get("box")]
        pins = [{
            "id": c.get("id"),
            "class": c.get("class"),
            "max_confidence": c.get("max_confidence"),
            "avg_latitude": c.get("avg_latitude"),
            "avg_longitude": c.get("avg_longitude"),
            "image_url": _proxy_crop_url(c.get("image_url")),
            "sighting_count": len(c.get("sightings") or []),
        } for c in task.get("clusters", [])]
        _live_cache.update({"key": key, "detections": detections, "pins": pins})
    return _live_cache["detections"], _live_cache["pins"]


# A patrol occupies the station from the moment it is accepted, not from the
# moment inference starts. The task is created "pending" and only turns
# "processing" after telemetry, weights, video open and spawning the worker pool
# — tens of seconds with eight workers. Guards that tested only for "processing"
# left that entire warm-up as an open window, and a second browser could start a
# run straight through it.
ACTIVE_STATUSES = ("pending", "processing")


# A patrol that never leaves "pending" means its worker died before it could
# start — an import failure, an OOM kill, a lost pool. Counting that as busy
# forever would lock the station out with no way back except a restart, so a
# pending task stops holding the lock once it is clearly not coming.
STALE_PENDING_S = 180


def _busy_task(tasks) -> Optional[dict]:
    """The patrol currently occupying the station, if any."""
    import time as _time

    for t in tasks.values():
        status = t.get("status")
        if status == "processing":
            return t
        if status == "pending":
            started = t.get("started_at") or 0
            if not started or (_time.time() - started) < STALE_PENDING_S:
                return t
            print(f"⚠️ Ignoring a patrol stuck pending for "
                  f"{int(_time.time() - started)}s — the station is free again.")
    return None


def _eta_seconds(task: dict) -> Optional[int]:
    """
    Rough seconds remaining for a running patrol.

    Deliberately conservative about when it speaks: below 5% the sample is too
    small and the number jumps around, which reads as the station guessing.
    """
    import time as _time

    if task.get("status") != "processing":
        return None
    pct = task.get("progress_percent") or 0
    started = task.get("started_at")
    if not started or pct < 5:
        return None
    elapsed = _time.time() - started
    if elapsed <= 0:
        return None
    remaining = elapsed * (100.0 - pct) / pct
    return int(max(1, min(remaining, 3600)))


def _active_task() -> Optional[dict]:
    """The mission currently being processed, if any."""
    from processing_task import PROCESSING_TASKS

    running = [t for t in PROCESSING_TASKS.values() if t.get("status") in ACTIVE_STATUSES]
    if running:
        # Newest first, so a fresh flight takes over the crowd's screens.
        return running[-1]

    # Nothing running: the flight that just finished, still in memory.
    finished = [t for t in PROCESSING_TASKS.values() if t.get("detections")]
    if finished:
        return finished[-1]

    # Nothing in memory either — first load after a restart. The last patrol was
    # written to disk when it ended, so the page shows real work rather than an
    # empty screen.
    import local_store
    return local_store.load_mission()


# A crowd scanning the QR at the same moment all request `since=0`, and every
# one of those responses is byte-identical. Serialising the same ~90KB once per
# phone is the whole first-load cost, so the body is cached and replayed.
_firstload_cache: Dict[str, Any] = {"key": None, "body": None}

# How many analysed frames a phone gets when it first joins. Enough to start
# playing immediately without pulling the whole flight down.
FRAME_TAIL = 6


@router.get("/live")
async def get_live_state(since: int = 0, pins_since: int = 0, frames_since: int = 0):
    """
    Compact live state for the public phone view, polled by every watcher.

    `since` / `pins_since` are cursors: a phone sends how many detections and
    pins it already holds and gets back only what is new. During a flight that
    keeps each update to a few hundred bytes, which is what makes a room full of
    phones on shared wifi viable.
    """
    fresh_client = (since == 0 and pins_since == 0 and frames_since == 0)
    task = _active_task()

    # Replay the cached body when a fresh client asks for state that has not
    # moved since it was built. The frame count is part of the key: without it a
    # newly arrived phone would be handed a body from before the latest frames
    # and sit on a stale picture.
    if fresh_client and _firstload_cache["body"] is not None:
        key = (task.get("task_id") if task else None,
               len(task.get("detections") or ()) if task else -1,
               len(task.get("clusters") or ()) if task else -1,
               len(task.get("frames") or ()) if task else -1,
               task.get("progress_percent") if task else None)
        if _firstload_cache["key"] == key:
            return Response(content=_firstload_cache["body"],
                            media_type="application/json")

    # No run this session — replay the pinned demo so the page is never empty.
    if not task:
        try:
            demo = await get_demo_data()
        except HTTPException:
            return {"live": False, "status": "idle", "title": "Waiting for the next flight",
                    "detections": [], "pins": [], "total_detections": 0, "total_pins": 0}
        return {
            "live": False,
            "status": "replay",
            "title": demo["title"],
            "location": demo["location"],
            "progress_percent": 100,
            "stage": {"key": "export", "label": "Patrol complete",
                      "detail": "Showing the most recent completed patrol."},
            "detections": demo["detections"][since:],
            "pins": demo["pins"][pins_since:],
            "total_detections": len(demo["detections"]),
            "total_pins": len(demo["pins"]),
            "video_url": demo["video_url"],
            "poster_url": demo["poster_url"],
            "duration_s": demo["duration_s"],
            "sahi": demo.get("sahi", {}),
            "altitude": demo.get("altitude"),
            "flight_path": demo.get("flight_path", []) if since == 0 else [],
        }

    detections, pins = _derive_live_lists(task)
    stages = task.get("stages", [])
    active = next((s for s in stages if s.get("status") == "active"), None)
    if active is None and stages:
        active = stages[-1]

    payload = {
        "live": task.get("status") in ACTIVE_STATUSES,
        "status": task.get("status"),
        "mission_id": task.get("task_id"),
        "title": "Live patrol",
        "location": settings.SAMPLE_LOCATION_LABEL,
        "progress_percent": task.get("progress_percent", 0),
        # Seconds left, measured rather than assumed: how long this run has
        # actually taken to reach this percentage, extrapolated. None until
        # there is enough progress for the estimate to mean anything — an ETA
        # that swings wildly in the first seconds is worse than none.
        "eta_seconds": _eta_seconds(task),
        "current_time_s": task.get("current_time_s", 0),
        "duration_s": task.get("duration_s", 0),
        "stage": {
            "key": active.get("key") if active else None,
            "label": active.get("label") if active else "Starting up",
            "detail": active.get("detail") if active else "",
            "tag": active.get("tag") if active else None,
            "metric": active.get("metric") if active else None,
        },
        # The whole pipeline, key/label/status only — no `detail`, which is a
        # sentence per stage and would dominate the payload. The phone shows the
        # stages either side of the active one during warm-up, so the audience
        # sees a station working through a sequence rather than a caption that
        # changes for no visible reason. Labels come from here so the two screens
        # cannot drift apart.
        "stages": [{"key": st.get("key"), "label": st.get("label"),
                    "status": st.get("status")} for st in stages],
        # Only the tail the caller has not seen yet.
        "detections": detections[since:],
        "pins": pins[pins_since:],
        # Analysed frames with their boxes already drawn on. Only the newest few
        # are worth sending: a phone joining mid-flight wants to see what is
        # happening now, not replay everything it missed.
        "frames": (task.get("frames") or [])[-FRAME_TAIL:] if frames_since == 0
                  else (task.get("frames") or [])[frames_since:],
        "total_frames": len(task.get("frames") or ()),
        "total_detections": len(detections),
        "total_pins": len(pins),
        "video_url": settings.SAMPLE_PREVIEW_URL,
        "poster_url": settings.SAMPLE_POSTER_URL,
        "sahi": task.get("sahi", {}),
        "altitude": task.get("altitude"),
        # Static for the run, so send it only on a client's first poll — it is
        # otherwise the bulk of an idle update, times every phone in the room.
        "flight_path": task.get("flight_path", [])[::10] if since == 0 else [],
    }

    if fresh_client:
        body = json.dumps(payload).encode()
        _firstload_cache.update({
            "key": (task.get("task_id"), len(task.get("detections") or ()),
                    len(task.get("clusters") or ()), len(task.get("frames") or ()),
                    task.get("progress_percent")),
            "body": body,
        })
        return Response(content=body, media_type="application/json")

    return payload


@router.get("/demo/data")
async def get_demo_data():
    """
    Everything the mobile demo needs, in one request: the replay detections with
    their in-frame boxes, the georeferenced pins, and the flight path.
    """
    row = _resolve_demo_mission()
    if not row:
        raise HTTPException(status_code=404, detail="No completed demo mission is available yet.")

    try:
        task = json.loads(row["description"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=500, detail="Demo mission data is unreadable.")

    detections = [dict(d, image_url=_proxy_crop_url(d.get("image_url")))
                  for d in task.get("detections", []) if d.get("box")]
    detections.sort(key=lambda d: d.get("timestamp_s", 0))

    # Pins ship every sighting they were averaged from, which is most of the
    # payload and none of it is used on a phone beyond the count.
    pins = [{
        "id": c.get("id"),
        "class": c.get("class"),
        "max_confidence": c.get("max_confidence"),
        "avg_latitude": c.get("avg_latitude"),
        "avg_longitude": c.get("avg_longitude"),
        "image_url": _proxy_crop_url(c.get("image_url")),
        "sighting_count": len(c.get("sightings") or []),
    } for c in task.get("clusters", [])]

    return {
        "mission_id": row["id"],
        "title": row.get("title") or "Coastal patrol",
        "location": settings.SAMPLE_LOCATION_LABEL,
        "mission_date": row.get("mission_date"),
        "video_url": settings.SAMPLE_PREVIEW_URL,
        "poster_url": settings.SAMPLE_POSTER_URL,
        "duration_s": task.get("duration_s", 0),
        "detections": detections,
        "pins": pins,
        "flight_path": task.get("flight_path", [])[::10],  # thinned for mobile
        "sahi": task.get("sahi", {}),
        "altitude": task.get("altitude"),
    }


VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".avi", ".m4v")
TELEMETRY_EXTS = (".srt", ".csv", ".txt")


def _media_listing():
    """Footage sitting on the station, ready to process without an upload."""
    d = settings.MEDIA_DIR
    vids, tels = [], []
    if os.path.isdir(d):
        for name in sorted(os.listdir(d)):
            path = os.path.join(d, name)
            if not os.path.isfile(path):
                continue
            low = name.lower()
            entry = {"name": name, "size_mb": round(os.path.getsize(path) / 1048576, 1)}
            if low.endswith(VIDEO_EXTS):
                vids.append(entry)
            elif low.endswith(TELEMETRY_EXTS):
                tels.append(entry)
    return vids, tels


def resolve_media_file(name: str, kind: str) -> str:
    """
    Turn a caller-supplied filename into a real path inside MEDIA_DIR.

    Compared against the actual listing rather than trusted as a string, the
    same way weights are resolved — so neither `../` nor a symlink can point the
    station at a file outside the folder.
    """
    vids, tels = _media_listing()
    allowed = {e["name"] for e in (vids if kind == "video" else tels)}
    if name not in allowed:
        raise HTTPException(status_code=400,
                            detail=f"No such {kind} on the station: {os.path.basename(str(name))}")
    path = os.path.realpath(os.path.join(settings.MEDIA_DIR, name))
    if os.path.dirname(path) != os.path.realpath(settings.MEDIA_DIR):
        raise HTTPException(status_code=400, detail="Path escapes the media directory.")
    return path


@router.get("/station/media")
async def station_media():
    """Footage already on the station, for the no-upload path."""
    vids, tels = _media_listing()
    return {"dir": settings.MEDIA_DIR, "videos": vids, "telemetry": tels}


@router.get("/station/access")
async def station_access(request: Request):
    """
    Whether this browser may start a patrol, and whether the station is free.

    The dashboard asks before letting anyone into the upload and configure
    steps. Filling in a whole wizard only to be refused at the last click is a
    poor way to find out you are a spectator.
    """
    from processing_task import PROCESSING_TASKS

    key_ok = (not settings.STATION_KEY) or \
             request.headers.get("x-station-key", "") == settings.STATION_KEY
    active = _busy_task(PROCESSING_TASKS)
    return {
        "key_required": bool(settings.STATION_KEY),
        "key_ok": key_ok,
        "busy": active is not None,
        "progress_percent": (active or {}).get("progress_percent", 0),
        "eta_seconds": _eta_seconds(active) if active else None,
    }


@router.get("/process/signed-upload-url")
async def get_signed_upload_url(request: Request, filename: str):
    """
    Generates a signed upload URL for uploading large video files directly to Google Cloud Storage.
    """
    # Same gate as /api/process. This is the other way footage gets in, so
    # leaving it open would make the key on the launch endpoint decorative.
    if settings.STATION_KEY and request.headers.get("x-station-key", "") != settings.STATION_KEY:
        raise HTTPException(status_code=403,
                            detail="This station is view-only. Enter the operator key to upload footage.")
    if not gcs_client:
        raise HTTPException(status_code=400, detail="Google Cloud Storage client is not initialized.")
    try:
        bucket_name = settings.GCS_BUCKET_NAME
        unique_filename = f"uploads/{uuid.uuid4()}_{filename}"
        bucket = gcs_client.bucket(bucket_name)
        blob = bucket.blob(unique_filename)
        
        # Resolve service account email for blob signing delegation
        service_account_email = None
        if hasattr(gcs_client, "_credentials") and gcs_client._credentials and hasattr(gcs_client._credentials, "service_account_email"):
            service_account_email = gcs_client._credentials.service_account_email
        
        if not service_account_email or service_account_email == "default":
            try:
                import requests
                metadata_url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"
                headers = {"Metadata-Flavor": "Google"}
                resp = requests.get(metadata_url, headers=headers, timeout=1)
                if resp.status_code == 200:
                    service_account_email = resp.text.strip()
            except Exception:
                pass
                
        if service_account_email == "default":
            service_account_email = None

        kwargs = {
            "version": "v4",
            "expiration": datetime.timedelta(minutes=15),
            "method": "PUT",
            "content_type": "application/octet-stream"
        }
        
        import google.auth.credentials
        signing_creds = gcs_client._credentials
        if signing_creds and not isinstance(signing_creds, google.auth.credentials.Signing) and service_account_email:
            try:
                from google.auth import impersonated_credentials
                print(f"[FastAPI] Creating impersonated credentials for signing: {service_account_email}")
                signing_creds = impersonated_credentials.Credentials(
                    source_credentials=gcs_client._credentials,
                    target_principal=service_account_email,
                    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
            except Exception as e:
                print(f"⚠️ Failed to create impersonated credentials: {e}")

        if signing_creds:
            kwargs["credentials"] = signing_creds
        if service_account_email:
            kwargs["service_account_email"] = service_account_email

        # Generate PUT signed URL
        signed_url = blob.generate_signed_url(**kwargs)
        
        public_url = f"https://storage.googleapis.com/{bucket_name}/{unique_filename}"
        
        return {
            "signed_url": signed_url,
            "public_url": public_url,
            "gcs_video_path": unique_filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate signed upload URL: {str(e)}")

@router.post("/process")
async def process_flight_data(
    request: Request,
    video: Optional[UploadFile] = File(None),
    video_url: Optional[str] = Form(None),
    supabase_video_path: Optional[str] = Form(None),
    gcs_video_path: Optional[str] = Form(None),
    telemetry: Optional[UploadFile] = File(None),
    use_sample: bool = Form(False),
    # Footage already on the station, chosen by name from MEDIA_DIR.
    local_video: Optional[str] = Form(None),
    local_telemetry: Optional[str] = Form(None),
    # Weights are chosen by name from the server's models directory. There is
    # deliberately no upload and no URL: a .pt is pickled Python, so letting a
    # request supply the bytes — or an address to fetch them from — is remote
    # code execution. Install models with `python -m model_source install`.
    model_name: Optional[str] = Form(None),
    interval_ms: int = Form(1000),
    # 0.40 matches the model's mAP and the dashboard slider's default, so a
    # direct API call and a run started from the station behave the same. The
    # station used to send 0.70, which quietly discarded most of the finds.
    min_confidence: float = Form(0.40),
    mission_title: Optional[str] = Form(None),
    mission_date: Optional[str] = Form(None),
    sahi_enabled: bool = Form(True),
    slice_size: int = Form(512),
    overlap_ratio: float = Form(0.2),
    workers: Optional[int] = Form(None),
    include_full_frame: bool = Form(True)
):
    """
    Ingests video and telemetry log and triggers YOLO + georeferencing background task.
    """
    from processing_task import start_processing_task, PROCESSING_TASKS

    # Viewing the station is open; launching is not. The dashboard URL is being
    # handed out alongside the phone demo, so anyone who opens it could otherwise
    # start a patrol on the GPU — including in the middle of a live one.
    if settings.STATION_KEY:
        supplied = request.headers.get("x-station-key", "") if request else ""
        if supplied != settings.STATION_KEY:
            raise HTTPException(
                status_code=403,
                detail="This station is view-only. Enter the operator key to start a patrol.",
            )

    # One patrol at a time, enforced here rather than only in the UI. Two
    # operators on station.coastalpatrol.app can both press Run, and nothing
    # stopped them: both flights would contend for the same GPU, the worker pool
    # can deadlock under it, and every watching phone would jump to whichever
    # started last — mid-story, in front of the audience. The dashboard also
    # hides the button while a run is live, but that is a courtesy; this is the
    # part that holds when two clicks land in the same second.
    active = _busy_task(PROCESSING_TASKS)
    if active:
        done = active.get("progress_percent", 0)
        raise HTTPException(
            status_code=409,
            detail=(f"A patrol is already running ({done}% complete). "
                    f"Wait for it to finish, or open the dashboard to watch it."),
        )

    # Save files temporarily (Cloud Run container environment uses /tmp as writable storage)
    if os.environ.get("K_SERVICE"):
        temp_dir = "/tmp"
    else:
        temp_dir = os.path.join(os.path.dirname(__file__), "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    
    # One-click demo: the bundled East Coast footage already lives on the server,
    # so there is nothing to upload. Copy it into the temp dir first — the worker
    # deletes its inputs when it finishes, which would otherwise consume the
    # shipped sample on the first run.
    if use_sample:
        import shutil
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        sample_video = os.path.join(static_dir, "sample.mp4")
        sample_srt = os.path.join(static_dir, "sample.srt")
        missing = [p for p in (sample_video, sample_srt) if not os.path.exists(p)]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Sample footage is not installed on this server: {', '.join(os.path.basename(m) for m in missing)}"
            )

        video_path = os.path.join(temp_dir, f"sample_{uuid.uuid4()}.mp4")
        telemetry_path = os.path.join(temp_dir, f"sample_{uuid.uuid4()}.srt")
        shutil.copyfile(sample_video, video_path)
        shutil.copyfile(sample_srt, telemetry_path)
        print(f"✅ [FastAPI] Sample run staged from {static_dir}")

    elif local_video:
        # Already on the station: copy it into the temp dir like the sample does,
        # because the worker deletes its inputs when it finishes and must not
        # consume footage the operator put there deliberately.
        import shutil
        src_v = resolve_media_file(local_video, "video")
        if not local_telemetry:
            raise HTTPException(status_code=400,
                                detail="A telemetry file on the station is required alongside the video.")
        src_t = resolve_media_file(local_telemetry, "telemetry")
        video_path = os.path.join(temp_dir, f"local_{uuid.uuid4()}{os.path.splitext(src_v)[1]}")
        telemetry_path = os.path.join(temp_dir, f"local_{uuid.uuid4()}{os.path.splitext(src_t)[1]}")
        shutil.copyfile(src_v, video_path)
        shutil.copyfile(src_t, telemetry_path)
        print(f"✅ [FastAPI] Using footage already on the station: {local_video} + {local_telemetry}")

    elif not video and not video_url and not gcs_video_path:
        raise HTTPException(status_code=400, detail="Either an uploaded video, footage already on the station (local_video), or video_url is required.")

    if use_sample or local_video:
        pass  # paths already staged above
    elif video:
        video_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{safe_upload_name(video.filename)}")
        await stream_upload_to(video, video_path)
    elif gcs_video_path:
        if not gcs_client:
            raise HTTPException(status_code=400, detail="Google Cloud Storage client is not initialized.")
        video_name = gcs_video_path.split("/")[-1]
        video_path = os.path.join(temp_dir, f"downloaded_{uuid.uuid4()}_{video_name}")
        try:
            print(f"[FastAPI] Downloading video from GCS path {gcs_video_path} to {video_path}...")
            bucket = gcs_client.bucket(settings.GCS_BUCKET_NAME)
            blob = bucket.blob(gcs_video_path)
            blob.download_to_filename(video_path)
            print(f"✅ [FastAPI] Video downloaded successfully from GCS. Size: {os.path.getsize(video_path)} bytes.")
        except Exception as e:
            if os.path.exists(video_path):
                os.remove(video_path)
            raise HTTPException(status_code=500, detail=f"Error downloading video from GCS: {str(e)}")
    else:
        # Download video from video_url
        import requests
        video_name = video_url.split("/")[-1].split("?")[0]
        if not video_name or "." not in video_name:
            video_name = "flight_video.mp4"
        video_path = os.path.join(temp_dir, f"downloaded_{uuid.uuid4()}_{video_name}")
        
        try:
            print(f"[FastAPI] Downloading video from {video_url} to {video_path}...")
            response = requests.get(video_url, stream=True)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Failed to download video from URL (HTTP {response.status_code}).")
            with open(video_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"✅ [FastAPI] Video downloaded successfully. Size: {os.path.getsize(video_path)} bytes.")
        except Exception as e:
            if os.path.exists(video_path):
                os.remove(video_path)
            raise HTTPException(status_code=500, detail=f"Error downloading video from URL: {str(e)}")
        
    if not use_sample and not local_video:
        if not telemetry or not telemetry.filename:
            if os.path.exists(video_path):
                os.remove(video_path)
            raise HTTPException(status_code=400, detail="A telemetry log (.srt or .csv) is required.")
        telemetry_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{safe_upload_name(telemetry.filename)}")
        await stream_upload_to(telemetry, telemetry_path)


    # Resolve the weights against the models directory. `resolve_local_model`
    # compares the name to the real listing, so neither a traversal nor a
    # fabricated name can reach torch.load.
    from model_source import resolve_local_model, list_available_models

    chosen = (model_name or settings.DEFAULT_MODEL_NAME or "").strip()
    if not chosen:
        installed = list_available_models()
        chosen = installed[0]["name"] if installed else ""

    try:
        model_path = resolve_local_model(chosen)
    except ValueError as e:
        if os.path.exists(video_path):
            os.remove(video_path)
        if not use_sample and telemetry_path and os.path.exists(telemetry_path):
            os.remove(telemetry_path)
        raise HTTPException(status_code=400, detail=str(e))


    # Create the mission in Supabase
    mission_id = None
    if supabase_client:
        try:
            m_title = mission_title if mission_title else f"Flight Patrol - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
            m_date = mission_date if mission_date else datetime.datetime.utcnow().isoformat()
            
            mission_res = supabase_client.table("missions").insert({
                "title": m_title,
                "mission_date": m_date
            }).execute()
            
            if mission_res.data:
                mission_id = mission_res.data[0]["id"]
                print(f"✅ [FastAPI] Created new mission: {m_title} (ID: {mission_id})")
        except Exception as e:
            print(f"⚠️ [FastAPI] Database Warning: Missions table query failed. Proceeding without mission segregation. Error: {e}")
        
    # Launch background thread
    task_id = start_processing_task(
        video_path=video_path,
        telemetry_path=telemetry_path,
        model_path=model_path,
        interval_ms=interval_ms,
        min_confidence=min_confidence,
        mission_id=mission_id,
        supabase_video_path=supabase_video_path,
        gcs_video_path=gcs_video_path,
        sahi_enabled=sahi_enabled,
        slice_size=slice_size,
        overlap_ratio=overlap_ratio,
        workers=workers,
        include_full_frame=include_full_frame
    )

    return {"task_id": task_id, "status": "pending"}



# --- Government Agency Evidence Export ---

def _load_export_data(mission_id: Optional[str] = None):
    """
    Gathers the detections and mission metadata backing an export.

    Falls back to the in-flight task's clusters when the database is unavailable,
    so an export still works in mock/offline mode during a demo.
    """
    pins: List[Dict[str, Any]] = []
    mission: Dict[str, Any] = {}

    if supabase_client:
        try:
            query = supabase_client.table("litter_pins").select("*")
            if mission_id:
                query = query.eq("mission_id", mission_id)
            res = query.order("detected_at", desc=False).execute()
            pins = res.data or []
        except Exception as e:
            print(f"⚠️ Export pin query failed: {e}")

        if mission_id:
            try:
                m_res = supabase_client.table("missions").select("id,title,mission_date").eq("id", mission_id).execute()
                if m_res.data:
                    mission = m_res.data[0]
            except Exception as e:
                print(f"⚠️ Export mission query failed: {e}")

    if not pins:
        # In-memory fallback: the clusters of the task that owns this mission.
        # These are genuinely that survey's detections, so attributing them to the
        # mission is correct.
        from processing_task import PROCESSING_TASKS
        task = PROCESSING_TASKS.get(mission_id) if mission_id else None
        if task and task.get("clusters"):
            pins = [{
                "id": c["db_pin_id"],
                "latitude": c["avg_latitude"],
                "longitude": c["avg_longitude"],
                "confidence": c["max_confidence"],
                "image_url": c.get("image_url"),
                "status": "detected",
                "detected_at": None,
            } for c in task["clusters"]]
        elif MOCK_PINS and not mission_id:
            # The mock store is only safe for an unscoped export. Pins land there
            # when a database write failed, so they belong to no known mission —
            # stamping them with a specific mission's title and date would put
            # unrelated detections into a document sent to a government agency.
            pins = list(MOCK_PINS)

    return pins, mission


def _export_filename(mission: Dict[str, Any], extension: str) -> str:
    """Builds a descriptive, filesystem-safe download name."""
    raw = mission.get("title") or "beach_litter_survey"
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "" for ch in raw).strip().replace(" ", "_")
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d")
    return f"{safe or 'beach_litter_survey'}_{stamp}.{extension}"


@router.get("/export/summary")
async def export_summary(mission_id: Optional[str] = None):
    """
    Preview of what an export would contain.

    The dashboard calls this to show record counts and survey extent before the
    operator commits to a download.
    """
    from exporters import summarise

    pins, mission = _load_export_data(mission_id)
    stats = summarise(pins)
    stats["mission_title"] = mission.get("title", "Unassigned Patrol")
    stats["mission_date"] = mission.get("mission_date")
    stats["formats"] = ["csv", "geojson", "pdf"]
    return stats


@router.get("/export/{export_format}")
async def export_detections(export_format: str, mission_id: Optional[str] = None):
    """
    Exports mission detections for sharing with government agencies.

    Supported formats: csv (spreadsheet//database ingest), geojson (QGIS, ArcGIS,
    Google Earth), pdf (filed situation report).
    """
    from exporters import build_csv, build_geojson, build_pdf

    export_format = export_format.lower()
    if export_format not in ("csv", "geojson", "pdf"):
        raise HTTPException(status_code=400, detail=f"Unsupported export format '{export_format}'. Use csv, geojson or pdf.")

    pins, mission = _load_export_data(mission_id)
    if not pins:
        raise HTTPException(status_code=404, detail="No detections available to export for this mission.")

    filename = _export_filename(mission, export_format)
    disposition = {"Content-Disposition": f'attachment; filename="{filename}"'}

    if export_format == "csv":
        return Response(content=build_csv(pins, mission), media_type="text/csv", headers=disposition)

    if export_format == "geojson":
        return JSONResponse(
            content=build_geojson(pins, mission),
            media_type="application/geo+json",
            headers=disposition,
        )

    try:
        pdf_bytes = build_pdf(pins, mission)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return Response(content=pdf_bytes, media_type="application/pdf", headers=disposition)


@router.get("/process/status/{task_id}")
async def get_process_status(task_id: str):
    """
    Retrieves the status, console logs, and detections for a specific processing task.
    """
    from processing_task import PROCESSING_TASKS
    if task_id in PROCESSING_TASKS:
        return PROCESSING_TASKS[task_id]
        
    # Fallback: Check if task status is persisted in the Supabase missions table
    if supabase_client:
        try:
            res = supabase_client.table("missions").select("description").eq("id", task_id).execute()
            if res.data and res.data[0].get("description"):
                import json
                desc = res.data[0]["description"]
                try:
                    task_data = json.loads(desc)
                    if isinstance(task_data, dict) and "status" in task_data:
                        return task_data
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"⚠️ Failed to fetch task status from Supabase: {e}")
            
    raise HTTPException(status_code=404, detail="Processing task not found")

