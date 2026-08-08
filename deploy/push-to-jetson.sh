#!/usr/bin/env bash
# Copy Coastal Patrol to the Jetson.
#
# Run from the repo root on the Mac:
#     ./deploy/push-to-jetson.sh nano@192.168.1.50
#
# A `git clone` on its own gives you a broken install: the model weights, the
# sample footage and .env are all gitignored, and they are exactly the three
# things the app cannot start without. This copies the working tree instead,
# minus the parts that must not travel (venv is x86/Apple-built, and the caches
# are regenerated on demand).
set -euo pipefail

TARGET="${1:-}"
DEST="${2:-~/coastal-patrol}"

if [ -z "$TARGET" ]; then
  echo "usage: $0 user@jetson-host [remote-path]" >&2
  exit 1
fi

cd "$(dirname "$0")/.."

echo "==> Copying to $TARGET:$DEST"
rsync -avh --progress \
  --exclude '.git/' \
  --exclude 'venv/' --exclude '.venv/' --exclude 'backend/venv/' \
  --exclude '__pycache__/' --exclude '*.pyc' \
  --exclude 'node_modules/' --exclude 'mobile/' \
  --exclude 'backend/temp_uploads/' \
  --exclude 'backend/frame_cache/' \
  --exclude 'backend/tile_cache/' \
  --exclude 'backend/crop_cache/' \
  --exclude 'backend/model_cache/' \
  --exclude '.DS_Store' \
  ./ "$TARGET:$DEST/"

# .env and the weights are gitignored, so rsync above carries them only because
# it works off the working tree. Say so plainly — a silent miss here surfaces as
# "Unknown model" or a blank dashboard much later.
echo
echo "==> Checking the three things a clone would have missed"
ssh "$TARGET" "cd $DEST && \
  for p in backend/.env backend/models backend/static/sample.mp4; do \
    if [ -e \"\$p\" ]; then echo \"  ok      \$p\"; else echo \"  MISSING \$p\"; fi; \
  done"

echo
echo "Next, on the Jetson:"
echo "    cd $DEST && ./deploy/jetson-setup.sh"
