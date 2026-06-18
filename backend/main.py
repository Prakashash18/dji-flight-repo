from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from typing import Optional
import uvicorn

import os
from fastapi.staticfiles import StaticFiles

from config import settings
from routes import router as api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend service for Drone Beach Litter Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Mount static files for sample downloads
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Configure CORS to allow React Native mobile clients and processing stations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Router
app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root(accept: Optional[str] = Header(None)):
    if accept and "text/html" in accept:
        return RedirectResponse(url="/api/dashboard")
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
        "sealion_configured": bool(settings.SEA_LION_API_KEY)
    }



if __name__ == '__main__':
    print(f"🚀 Starting {settings.PROJECT_NAME} on http://{settings.HOST}:{settings.PORT}")
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
