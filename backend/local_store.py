"""
On-disk home for the most recent patrol.

The project used to keep pins in Supabase and crops in Supabase Storage or GCS.
For a single-operator live demo that bought nothing and cost a great deal: every
detection was a round trip to another continent, and when the connection wobbled
the run filled the log with `Server disconnected`, thumbnails 502'd, and phones
retried the same images in a loop.

One flight runs at a time, and the audience only ever needs the flight happening
now or the one that just finished. That fits on disk. Starting a new patrol
clears the previous one, which also stops `frame_cache` and `crop_cache` growing
without bound — nothing was cleaning them up before.
"""
import json
import os
import shutil
import tempfile
from typing import Any, Dict, Optional

BASE_DIR = os.path.dirname(__file__)
STORE_DIR = os.environ.get("LOCAL_STORE_DIR") or os.path.join(BASE_DIR, "mission_store")
STORE_FILE = os.path.join(STORE_DIR, "last_mission.json")

# Only the parts the phone view and the export actually read. The full task dict
# carries console logs and stage objects that would bloat the file for nothing.
PERSISTED_KEYS = (
    "task_id", "status", "progress_percent", "current_time_s", "duration_s",
    "detections", "clusters", "flight_path", "altitude", "sahi", "frames",
    "mission_title", "location",
)


def save_mission(task: Dict[str, Any]) -> bool:
    """Write the finished patrol out, atomically."""
    if not task:
        return False
    try:
        os.makedirs(STORE_DIR, exist_ok=True)
        payload = {k: task.get(k) for k in PERSISTED_KEYS if k in task}
        payload["saved_at"] = __import__("datetime").datetime.utcnow().isoformat()
        # Write-then-rename: a phone polling mid-write must never read half a file.
        fd, tmp = tempfile.mkstemp(dir=STORE_DIR, suffix=".part")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp, STORE_FILE)
        return True
    except Exception as e:
        print(f"⚠️ Could not save mission locally: {e}")
        return False


def load_mission() -> Optional[Dict[str, Any]]:
    """The last completed patrol, or None on a clean machine."""
    try:
        if not os.path.exists(STORE_FILE):
            return None
        with open(STORE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Could not read the stored mission: {e}")
        return None


def purge_previous(keep_task_id: Optional[str] = None) -> None:
    """
    Drop everything belonging to earlier patrols.

    Called when a new flight starts, so the audience never sees a mix of two
    missions and the caches do not grow for the life of the machine. Frames and
    crops for `keep_task_id` are left alone — that is the run just starting.
    """
    from routes import CROP_CACHE_DIR

    try:
        if os.path.exists(STORE_FILE):
            os.remove(STORE_FILE)
    except OSError as e:
        print(f"⚠️ Could not clear the stored mission: {e}")

    # Annotated frames are per-task directories, so keep only the live one.
    try:
        from processing_task import FRAMES_DIR
        if os.path.isdir(FRAMES_DIR):
            for name in os.listdir(FRAMES_DIR):
                if name == keep_task_id:
                    continue
                shutil.rmtree(os.path.join(FRAMES_DIR, name), ignore_errors=True)
    except Exception as e:
        print(f"⚠️ Could not clear old frames: {e}")

    # Crops are a flat pool with uuid names and no task in the path, so the whole
    # pool goes. The new run repopulates it as it detects.
    try:
        crops = os.path.join(CROP_CACHE_DIR, "detections")
        if os.path.isdir(crops):
            shutil.rmtree(crops, ignore_errors=True)
    except Exception as e:
        print(f"⚠️ Could not clear old crops: {e}")


def disk_usage_mb() -> float:
    """Rough size of everything this store owns, for the housekeeping log line."""
    from routes import CROP_CACHE_DIR
    from processing_task import FRAMES_DIR

    total = 0
    for root_dir in (STORE_DIR, FRAMES_DIR, CROP_CACHE_DIR):
        for root, _dirs, files in os.walk(root_dir):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    return round(total / 1048576, 1)
