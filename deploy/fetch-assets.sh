#!/usr/bin/env bash
# Pull the big files a fresh pod needs. Run once after cloning, from the repo root:
#     ./deploy/fetch-assets.sh
#
# The repo itself is ~4 MB of code. The weights and the sample footage are 90%
# of a cold start, so they live off-repo and are fetched here instead. Anything
# already on disk is left alone, so this is safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

# shellcheck source=/dev/null
source "$ROOT/deploy/assets.env"

PY="${PYTHON:-$ROOT/backend/venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"

say()  { printf "\n\033[1m==> %s\033[0m\n" "$1"; }
warn() { printf "\033[33m    !! %s\033[0m\n" "$1"; }

say "Weights"
if [ -f "$ROOT/backend/models/$MODEL_NAME" ]; then
  echo "    already present: backend/models/$MODEL_NAME"
else
  # model_source handles Drive's confirm token and verifies the file is a real
  # torch archive rather than the HTML quota page Drive hands back when throttled.
  ( cd "$ROOT/backend" && "$PY" -m model_source install "$MODEL_URL" "$MODEL_NAME" )
fi
( cd "$ROOT/backend" && "$PY" -m model_source list )

say "Sample footage"
SAMPLE="$ROOT/backend/static/sample.mp4"
if [ -f "$SAMPLE" ]; then
  echo "    already present: backend/static/sample.mp4 ($(du -h "$SAMPLE" | cut -f1))"
elif [ -z "${SAMPLE_URL:-}" ] || [[ "$SAMPLE_URL" == *REPLACE_WITH_YOUR* ]]; then
  warn "SAMPLE_URL not set in deploy/assets.env — skipping."
  warn "The pod will start, but 'Run this sample' will 404 until you upload a video."
else
  echo "    downloading (~486 MB)…"
  "$PY" - "$SAMPLE_URL" "$SAMPLE" <<'EOF'
import sys, os
url, dest = sys.argv[1], sys.argv[2]
os.makedirs(os.path.dirname(dest), exist_ok=True)
tmp = dest + ".part"
if "drive.google.com" in url:
    import gdown, inspect
    kwargs = {"output": tmp, "quiet": False}
    if "fuzzy" in inspect.signature(gdown.download).parameters:
        kwargs["fuzzy"] = True
    gdown.download(url, **kwargs)
else:
    import requests
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)

# Drive answers a throttled request with an HTML page, not the file. Catch that
# here rather than letting OpenCV fail on it much later with a useless error.
size = os.path.getsize(tmp)
with open(tmp, "rb") as f:
    head = f.read(512).lstrip()
if size < 1_000_000 or head[:1] == b"<":
    os.remove(tmp)
    sys.exit(f"Download is not a video ({size} bytes). Drive likely returned a "
             f"quota page — host the .mp4 somewhere with a plain HTTP URL.")
os.replace(tmp, dest)
print(f"  saved {size/1048576:.0f} MB -> {dest}")
EOF
fi

say "Ready"
for p in backend/models backend/static/sample.mp4 backend/static/sample.srt backend/.env; do
  if [ -e "$ROOT/$p" ]; then echo "    ok      $p"; else echo "    MISSING $p"; fi
done
[ -f "$ROOT/backend/.env" ] || warn "backend/.env is secrets — set it from RunPod's env vars, not from Drive."
