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
    # Kept so the phone's warm-up rail still has real stage labels after a
    # restart, rather than falling back to raw keys.
    "stages",
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


def _prune_generations(parent: str, keep_task_id: Optional[str], keep: int = 2) -> int:
    """
    Keep the newest `keep` mission folders under `parent`, plus the live one.

    Deleting the previous patrol the moment a new one starts is too eager: a
    phone still showing the finished flight goes on requesting its crops and
    frames for as long as someone is looking at it, and every one of those became
    a miss. Keeping one generation back means the handover is invisible — the old
    run stays readable until it has been replaced twice over.
    """
    if not os.path.isdir(parent):
        return 0
    entries = []
    for name in os.listdir(parent):
        path = os.path.join(parent, name)
        if not os.path.isdir(path) or name == keep_task_id:
            continue
        try:
            entries.append((os.path.getmtime(path), path))
        except OSError:
            continue
    entries.sort(reverse=True)          # newest first
    removed = 0
    for _mtime, path in entries[keep - 1:]:
        shutil.rmtree(path, ignore_errors=True)
        removed += 1
    return removed


def purge_previous(keep_task_id: Optional[str] = None) -> None:
    """
    Retire patrols older than the one just finished.

    The stored mission file is left alone — it is overwritten by the new run and
    is what a restart falls back to, so removing it here would blank the phone
    view for the whole warm-up.
    """
    from routes import CROP_CACHE_DIR
    from processing_task import FRAMES_DIR

    n = 0
    try:
        n += _prune_generations(FRAMES_DIR, keep_task_id)
    except Exception as e:
        print(f"⚠️ Could not retire old frames: {e}")
    try:
        n += _prune_generations(os.path.join(CROP_CACHE_DIR, "detections"), keep_task_id)
    except Exception as e:
        print(f"⚠️ Could not retire old crops: {e}")
    if n:
        print(f"🧹 Retired {n} folder(s) from patrols older than the last one.")


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
