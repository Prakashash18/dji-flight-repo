"""Resolves YOLO weight specifications into a local .pt file path.

The dashboard lets an operator point at weights in three ways:

* a bundled name shipped next to the backend (``solar_panel.pt``),
* a Google Drive share link (or bare file id), or
* any plain ``http(s)`` URL.

Remote weights are downloaded once into a cache directory and reused for
subsequent missions, so a 100MB checkpoint is not re-fetched on every run.
"""

import hashlib
import inspect
import os
import re
import shutil
import threading
from typing import Callable, Optional

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# The only place weights may be loaded from.
#
# A `.pt` file is pickled Python: torch.load() on one executes whatever it
# contains. So the set of loadable models must never be chosen by an HTTP
# caller. Previously a request could upload a `.pt` or name any URL, which meant
# anyone able to reach /api/process could run code as this process. Now a model
# has to be placed in this directory — an act that requires filesystem access —
# and requests may only pick from what is already there by name.
MODELS_DIR = os.environ.get("MODELS_DIR") or os.path.join(BACKEND_DIR, "models")


def list_available_models() -> list:
    """Every usable checkpoint in the models directory, newest-looking first."""
    try:
        names = [f for f in os.listdir(MODELS_DIR) if f.lower().endswith(".pt")]
    except OSError:
        return []

    out = []
    for name in sorted(names):
        path = os.path.join(MODELS_DIR, name)
        if not os.path.isfile(path):
            continue
        out.append({
            "name": name,
            "label": name[:-3].replace("_", " ").replace("-", " ").title(),
            "size_mb": round(os.path.getsize(path) / 1e6, 1),
        })
    return out


def resolve_local_model(name: str) -> str:
    """
    Maps a model name to its path inside MODELS_DIR, or raises.

    Compares against the real listing rather than trusting the string, so a
    caller cannot escape the directory with `../` or a symlink.
    """
    if not name:
        raise ValueError("No model selected.")

    available = {m["name"] for m in list_available_models()}
    if name not in available:
        raise ValueError(
            f"Unknown model '{os.path.basename(str(name))}'. "
            f"Available: {', '.join(sorted(available)) or 'none installed'}"
        )

    path = os.path.realpath(os.path.join(MODELS_DIR, name))
    if os.path.dirname(path) != os.path.realpath(MODELS_DIR):
        raise ValueError("Model path escapes the models directory.")
    return path

# Cloud Run only grants write access to /tmp; locally we keep the cache beside
# the backend so it survives restarts.
if os.environ.get("K_SERVICE"):
    CACHE_DIR = "/tmp/model_cache"
else:
    CACHE_DIR = os.path.join(BACKEND_DIR, "model_cache")

# Serialises concurrent downloads of the same checkpoint.
_download_lock = threading.Lock()

LogFn = Callable[[str], None]

# Accepts the share, open and direct-download link shapes Drive hands out.
_DRIVE_PATTERNS = [
    re.compile(r"drive\.google\.com/file/d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"drive\.google\.com/open\?id=([A-Za-z0-9_-]{10,})"),
    re.compile(r"drive\.google\.com/uc\?[^ ]*id=([A-Za-z0-9_-]{10,})"),
    re.compile(r"drive\.usercontent\.google\.com/download\?[^ ]*id=([A-Za-z0-9_-]{10,})"),
    re.compile(r"docs\.google\.com/uc\?[^ ]*id=([A-Za-z0-9_-]{10,})"),
]

# A bare Drive file id pasted on its own.
_BARE_ID = re.compile(r"^[A-Za-z0-9_-]{25,}$")


def extract_drive_file_id(spec: str) -> Optional[str]:
    """Returns the Google Drive file id inside ``spec``, or None."""
    spec = spec.strip()
    for pattern in _DRIVE_PATTERNS:
        match = pattern.search(spec)
        if match:
            return match.group(1)
    if _BARE_ID.match(spec):
        return spec
    return None


def is_remote_spec(spec: str) -> bool:
    """True when ``spec`` needs downloading rather than reading off disk."""
    spec = spec.strip()
    return spec.startswith(("http://", "https://")) or extract_drive_file_id(spec) is not None


def _cache_path(key: str, suffix: str = ".pt") -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return os.path.join(CACHE_DIR, f"{digest}{suffix}")


def _download_drive(file_id: str, dest: str, log: LogFn) -> None:
    """Fetches a Drive file, preferring gdown for its confirm-token handling."""
    url = f"https://drive.google.com/uc?id={file_id}"
    try:
        import gdown

        log("⬇️  Downloading weights from Google Drive (gdown)...")
        # `fuzzy` was dropped in gdown 6.x (link parsing became the default), so
        # only pass it to releases that still declare it.
        kwargs = {"quiet": True}
        try:
            if "fuzzy" in inspect.signature(gdown.download).parameters:
                kwargs["fuzzy"] = True
        except (TypeError, ValueError):
            pass

        gdown.download(url, dest, **kwargs)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            return
        raise RuntimeError("gdown produced an empty file")
    except ImportError:
        log("ℹ️  gdown not installed — falling back to a direct Drive request.")
    except Exception as e:
        log(f"⚠️  gdown download failed ({e}). Falling back to a direct Drive request.")

    # Fallback: Drive serves an HTML interstitial for large files and expects the
    # confirm token to be echoed back on a second request.
    import requests

    session = requests.Session()
    endpoint = "https://drive.usercontent.google.com/download"
    response = session.get(endpoint, params={"id": file_id, "export": "download"}, stream=True, timeout=60)

    token = None
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            token = value
    if token is None and "text/html" in response.headers.get("Content-Type", ""):
        match = re.search(r'name="confirm"\s+value="([^"]+)"', response.text)
        if match:
            token = match.group(1)
        else:
            token = "t"

    if token:
        response = session.get(
            endpoint,
            params={"id": file_id, "export": "download", "confirm": token},
            stream=True,
            timeout=60,
        )

    response.raise_for_status()
    _stream_to_file(response, dest, log)


def _download_url(url: str, dest: str, log: LogFn) -> None:
    import requests

    log(f"⬇️  Downloading weights from {url.split('?')[0]} ...")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    _stream_to_file(response, dest, log)


def _stream_to_file(response, dest: str, log: LogFn) -> None:
    total = int(response.headers.get("Content-Length") or 0)
    written = 0
    last_logged = 0
    tmp_dest = dest + ".part"
    with open(tmp_dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 512):
            if not chunk:
                continue
            f.write(chunk)
            written += len(chunk)
            if total:
                percent = int(written / total * 100)
                if percent - last_logged >= 20:
                    log(f"   ...{percent}% ({written / 1e6:.1f}MB / {total / 1e6:.1f}MB)")
                    last_logged = percent
    os.replace(tmp_dest, dest)


def _looks_like_torch_checkpoint(path: str) -> bool:
    """Guards against caching an HTML error page as if it were weights."""
    try:
        if os.path.getsize(path) < 1024:
            return False
        with open(path, "rb") as f:
            head = f.read(4)
        # .pt files are zip archives (PK\x03\x04) or legacy pickles (\x80\x02).
        return head[:2] in (b"PK", b"\x80\x02"[:2]) or head[:1] == b"\x80"
    except OSError:
        return False


def resolve_model_path(spec: str, log: Optional[LogFn] = None) -> str:
    """Turns a weights spec into a readable local ``.pt`` path.

    Raises ``ValueError`` if the weights cannot be produced.
    """
    log = log or (lambda _msg: None)
    spec = (spec or "").strip()
    if not spec:
        raise ValueError("No model weights were specified.")

    # 1. Already a local file (absolute path, or an uploaded temp file).
    if os.path.isfile(spec):
        return spec

    # 2. A file bundled next to the backend, e.g. "solar_panel.pt".
    bundled = os.path.join(BACKEND_DIR, spec)
    if os.path.isfile(bundled):
        return bundled

    # 3. An Ultralytics shorthand ("yolov8n.pt") the library downloads itself.
    if re.match(r"^yolo[a-z0-9._-]*\.pt$", spec, re.IGNORECASE):
        return spec

    # 4. Remote weights — Google Drive or a plain URL.
    if is_remote_spec(spec):
        os.makedirs(CACHE_DIR, exist_ok=True)
        drive_id = extract_drive_file_id(spec)
        cache_key = f"drive:{drive_id}" if drive_id else f"url:{spec}"
        dest = _cache_path(cache_key)

        with _download_lock:
            if os.path.exists(dest) and _looks_like_torch_checkpoint(dest):
                log(f"♻️  Reusing cached weights ({os.path.getsize(dest) / 1e6:.1f}MB) — no download needed.")
                return dest

            try:
                if drive_id:
                    _download_drive(drive_id, dest, log)
                else:
                    _download_url(spec, dest, log)
            except Exception as e:
                if os.path.exists(dest):
                    os.remove(dest)
                raise ValueError(f"Could not download model weights: {e}") from e

            if not _looks_like_torch_checkpoint(dest):
                size = os.path.getsize(dest) if os.path.exists(dest) else 0
                if os.path.exists(dest):
                    os.remove(dest)
                raise ValueError(
                    "The downloaded file is not a PyTorch checkpoint "
                    f"({size} bytes). For Google Drive, make sure the file is shared as "
                    "'Anyone with the link'."
                )

            log(f"✅ Weights ready ({os.path.getsize(dest) / 1e6:.1f}MB) and cached for future runs.")
            return dest

    raise ValueError(
        f"Could not resolve model weights '{spec}'. Provide a bundled filename, "
        "a Google Drive share link, or a direct https URL."
    )


def clear_cache() -> None:
    """Removes every cached checkpoint. Handy from a REPL when weights change."""
    if os.path.isdir(CACHE_DIR):
        shutil.rmtree(CACHE_DIR)


def install_model(spec: str, name: Optional[str] = None) -> str:
    """
    Downloads a checkpoint into the models directory.

    Deliberately not reachable over HTTP. Fetching a URL that a request supplied
    is how the server ends up executing someone else's pickle — and how it ends
    up making requests to whatever internal address a caller names. Installing a
    model is an operator action, run from a shell:

        python -m model_source install <drive-url-or-path> [name.pt]
    """
    os.makedirs(MODELS_DIR, exist_ok=True)
    src = resolve_model_path(spec, log=lambda m: print(f"  {m}"))

    if not name:
        name = os.path.basename(src)
        if not name.endswith(".pt"):
            name += ".pt"
    name = os.path.basename(name)  # never let a path component through

    dest = os.path.join(MODELS_DIR, name)
    if os.path.realpath(src) != os.path.realpath(dest):
        shutil.copyfile(src, dest)
    print(f"✅ installed {name} ({os.path.getsize(dest) / 1e6:.1f}MB) into {MODELS_DIR}")
    return dest


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3 and sys.argv[1] == "install":
        install_model(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif len(sys.argv) >= 2 and sys.argv[1] == "list":
        models = list_available_models()
        print(f"{len(models)} model(s) in {MODELS_DIR}:")
        for m in models:
            print(f"  {m['name']:<28} {m['size_mb']:>7.1f} MB")
    else:
        print(__doc__)
        print("Usage:\n  python -m model_source list"
              "\n  python -m model_source install <drive-url|url|path> [name.pt]")
