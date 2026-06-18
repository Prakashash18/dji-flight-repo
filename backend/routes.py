from fastapi import APIRouter, Form, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import datetime
import os

from config import settings
from sealion import SeaLionClient

# Setup Jinja2 templates folder
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# Import Supabase client if available
supabase_client = None
if settings.SUPABASE_URL and settings.SUPABASE_KEY:
    try:
        from supabase import create_client, Client
        supabase_client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        print("🔌 [FastAPI] Supabase client initialized successfully.")
    except Exception as e:
        print(f"⚠️ [FastAPI] Failed to initialize Supabase client: {e}. Falling back to In-Memory DB.")
else:
    print("ℹ️ [FastAPI] Supabase credentials missing. Running in In-Memory Mock DB mode.")

# Import Google Cloud Storage client
gcs_client = None
try:
    from google.cloud import storage
    gcs_client = storage.Client()
    print("🔌 [FastAPI] Google Cloud Storage client initialized successfully.")
except Exception as e:
    print(f"⚠️ [FastAPI] Failed to initialize GCS client: {e}. Signed URL generation will fail.")

router = APIRouter()
sealion = SeaLionClient()

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
    return templates.TemplateResponse(request, "dashboard.html")

@router.get("/process/signed-upload-url")
async def get_signed_upload_url(filename: str):
    """
    Generates a signed upload URL for uploading large video files directly to Google Cloud Storage.
    """
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
    video: Optional[UploadFile] = File(None),
    video_url: Optional[str] = Form(None),
    supabase_video_path: Optional[str] = Form(None),
    gcs_video_path: Optional[str] = Form(None),
    telemetry: UploadFile = File(...),
    model_name: Optional[str] = Form("solar_panel.pt"),
    custom_model: Optional[UploadFile] = File(None),
    interval_ms: int = Form(1000),
    min_confidence: float = Form(0.35),
    mission_title: Optional[str] = Form(None),
    mission_date: Optional[str] = Form(None)
):
    """
    Ingests video and telemetry log and triggers YOLO + georeferencing background task.
    """
    from processing_task import start_processing_task
    
    # Save files temporarily (Cloud Run container environment uses /tmp as writable storage)
    if os.environ.get("K_SERVICE"):
        temp_dir = "/tmp"
    else:
        temp_dir = os.path.join(os.path.dirname(__file__), "temp_uploads")
    os.makedirs(temp_dir, exist_ok=True)
    
    if not video and not video_url and not gcs_video_path:
        raise HTTPException(status_code=400, detail="Either video file upload, video_url, or gcs_video_path is required.")
        
    if video:
        video_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{video.filename}")
        with open(video_path, "wb") as f:
            f.write(await video.read())
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
        
    telemetry_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{telemetry.filename}")
    with open(telemetry_path, "wb") as f:
        f.write(await telemetry.read())
        
    # Determine YOLO model path
    model_path = model_name
    if model_name == "custom":
        if custom_model and custom_model.filename:
            if not custom_model.filename.lower().endswith('.pt'):
                if os.path.exists(video_path):
                    os.remove(video_path)
                if os.path.exists(telemetry_path):
                    os.remove(telemetry_path)
                raise HTTPException(status_code=400, detail="Only .pt (PyTorch) model weights files are allowed.")
            custom_model_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{custom_model.filename}")
            with open(custom_model_path, "wb") as f:
                f.write(await custom_model.read())
            model_path = custom_model_path
        else:
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(telemetry_path):
                os.remove(telemetry_path)
            raise HTTPException(status_code=400, detail="Custom model weights file (.pt) is required when custom model option is selected.")
        
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
        gcs_video_path=gcs_video_path
    )
    
    return {"task_id": task_id, "status": "pending"}



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

