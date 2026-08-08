from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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

# The demo page and the live feed are JSON and HTML, and both compress well:
# a first-load /api/live goes 164KB -> 38KB. That matters when the origin is on
# a shared uplink (a hotel, a venue) and a few hundred phones arrive at once.
# JPEG tiles and crops are already compressed, so the 1KB floor leaves them and
# the small live deltas alone.
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Configure CORS to allow React Native mobile clients and processing stations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def cache_headers(request, call_next):
    """
    Marks responses cacheable so a CDN in front of this actually holds them.

    Nothing was cacheable before, so every phone fetched the video, the fonts and
    the Leaflet bundle from this process — hundreds of identical transfers over a
    single uplink. The vendored assets and the demo video never change during an
    event, and the live feed is worth a couple of seconds of staleness to turn
    hundreds of pollers into a couple of origin requests per second.
    """
    response = await call_next(request)
    path = request.url.path

    if response.status_code >= 400 or "cache-control" in response.headers:
        return response

    if path.startswith("/static/vendor/"):
        # Content-addressed fonts and pinned library versions.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif path.startswith("/static/"):
        # Sample video, poster and telemetry: stable for an event, but not
        # immutable — a new sample should land within the hour.
        response.headers["Cache-Control"] = "public, max-age=3600"
    elif path == "/api/live":
        # Every caught-up watcher sends the same cursor, so they share a cache
        # entry. Two seconds is invisible next to a two-second poll interval.
        response.headers["Cache-Control"] = "public, max-age=2"
    elif path in ("/api/demo", "/api/dashboard"):
        # The HTML is the one thing that must never be stale: it is where every
        # fix ships, and a phone (or a CDN edge) holding yesterday's copy makes a
        # deployed fix look like it never happened. It is 16KB gzipped and the
        # heavy assets it references stay cached, so revalidating costs nothing.
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    elif path.startswith("/api/frames/"):
        # Each analysed frame is written once under a unique timestamp and never
        # changes, so every watcher after the first is served by the edge.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

    return response

# Register API Router
app.include_router(api_router, prefix="/api")

@app.get("/")
def read_root(request: Request, accept: Optional[str] = Header(None)):
    if accept and "text/html" in accept:
        # Which page the bare domain means depends on who is asking. Visitors
        # arrive on the public host and want the demo; the operator reaches the
        # station on its own hostname. Sending everyone to the dashboard would
        # put the processing station in front of the audience.
        host = (request.headers.get("host") or "").split(":")[0].lower()
        station_host = (settings.STATION_HOST or "").lower()
        is_station = station_host and host == station_host
        is_local = host in ("localhost", "127.0.0.1", "0.0.0.0", "")
        target = "/api/dashboard" if (is_station or is_local) else "/api/demo"
        return RedirectResponse(url=target)
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
        "sealion_configured": bool(settings.SEA_LION_API_KEY)
    }



if __name__ == '__main__':
    # Auto-reload watches the source tree and restarts on any change. Useful
    # while developing, actively harmful during a live demo: a single file
    # written into the tree restarts the server mid-flight and drops the
    # in-memory mission every watching phone is polling. Opt in with RELOAD=1.
    use_reload = os.getenv("RELOAD", "").lower() in ("1", "true", "yes")
    print(f"🚀 Starting {settings.PROJECT_NAME} on http://{settings.HOST}:{settings.PORT}"
          f" ({'auto-reload' if use_reload else 'stable'})")
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=use_reload)
