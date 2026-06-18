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
    
    # SEA-LION API Configuration (Southeast Asian translation model)
    SEA_LION_API_KEY: str = os.getenv("SEA_LION_API_KEY", "")
    SEA_LION_API_URL: str = os.getenv("SEA_LION_API_URL", "https://api.sea-lion.ai/v1")
    
    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

settings = Settings()

# Basic validation warnings
if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
    print("⚠️ [Warning] SUPABASE_URL or SUPABASE_KEY is missing. Database operations will fail unless mocked.")
if not settings.SEA_LION_API_KEY:
    print("⚠️ [Warning] SEA_LION_API_KEY is missing. Translations will use local fallback mocks.")
