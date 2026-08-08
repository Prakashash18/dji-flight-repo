import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    PROJECT_NAME: str = "Beach Litter Management API"
    
    # Supabase Configuration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")  # Service role or anon key
    
    # Google Cloud Storage Configuration
    GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "dji-flight-volunteer-app-assets")

    # Default detection weights the dashboard pre-selects. A Google Drive share
    # link or any direct URL; the backend downloads it once and caches it, so
    # swapping models is an env change rather than a code change.
    # Weights are loaded only from backend/models/. Install one with:
    #   python -m model_source install <drive-url> beach_litter.pt
    # The URL below is kept for that command, not for request handling.
    DEFAULT_MODEL_NAME: str = os.getenv("DEFAULT_MODEL_NAME", "beach_litter.pt")
    DEFAULT_MODEL_URL: str = os.getenv(
        "DEFAULT_MODEL_URL",
        "https://drive.google.com/file/d/1Gt03JXACbwrqbo5-uAmdATY6zgUmIhv9/view?usp=sharing",
    )

    # Demo footage offered on step 1. Served from /static locally; point these at
    # a CDN or bucket in production, where shipping a 500MB file in the image is
    # not sensible.
    SAMPLE_VIDEO_URL: str = os.getenv("SAMPLE_VIDEO_URL", "/static/sample.mp4")
    SAMPLE_TELEMETRY_URL: str = os.getenv("SAMPLE_TELEMETRY_URL", "/static/sample.srt")
    SAMPLE_POSTER_URL: str = os.getenv("SAMPLE_POSTER_URL", "/static/sample_poster.jpg")
    # Playback-only proxy (~2MB). The browser never needs the full 4K file: the
    # server runs inference on that copy directly.
    SAMPLE_PREVIEW_URL: str = os.getenv("SAMPLE_PREVIEW_URL", "/static/sample_preview.mp4")

    # The mission the public mobile demo replays. Pinned so the scan-to-try
    # experience is stable rather than showing whatever ran most recently.
    DEMO_MISSION_ID: str = os.getenv("DEMO_MISSION_ID", "")

    # Hostname the operator dashboard is served on. The bare domain redirects
    # visitors to the demo everywhere else, so the audience never lands on the
    # processing station by typing the domain.
    STATION_HOST: str = os.getenv("STATION_HOST", "station.coastalpatrol.app")
    SAMPLE_LOCATION_LABEL: str = os.getenv("SAMPLE_LOCATION_LABEL", "East Coast Park, Singapore")
    # Where the map opens before any telemetry has loaded.
    MAP_DEFAULT_LAT: float = float(os.getenv("MAP_DEFAULT_LAT", "1.3093"))
    MAP_DEFAULT_LNG: float = float(os.getenv("MAP_DEFAULT_LNG", "103.9445"))
    MAP_DEFAULT_ZOOM: int = int(os.getenv("MAP_DEFAULT_ZOOM", "16"))

    # SEA-LION API Configuration (Southeast Asian translation model)
    SEA_LION_API_KEY: str = os.getenv("SEA_LION_API_KEY", "")
    SEA_LION_API_URL: str = os.getenv("SEA_LION_API_URL", "https://api.sea-lion.ai/v1")
    
    # Server configuration
    # Anyone may watch the station; starting a patrol needs this key. Left blank
    # the station stays fully open, which is right on a laptop and wrong on a
    # public URL handed to judges — a stranger pressing Run mid-demo takes the
    # GPU and every watching phone with it.
    STATION_KEY: str = os.getenv("STATION_KEY", "")

    # Footage copied onto the station out-of-band (scp, a mounted volume) and
    # processed without an HTTP upload. Both Cloudflare and RunPod's own proxy
    # cap request bodies around 100 MB, so a 1-3 GB DJI flight cannot reach the
    # station through a browser at all — this is the only path that works for
    # real footage.
    MEDIA_DIR: str = os.getenv("MEDIA_DIR", os.path.join(os.path.dirname(__file__), "media"))

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

settings = Settings()

# Basic validation warnings
if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
    print("⚠️ [Warning] SUPABASE_URL or SUPABASE_KEY is missing. Database operations will fail unless mocked.")
if not settings.SEA_LION_API_KEY:
    print("⚠️ [Warning] SEA_LION_API_KEY is missing. Translations will use local fallback mocks.")
