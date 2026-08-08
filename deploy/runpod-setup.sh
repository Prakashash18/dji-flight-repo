#!/usr/bin/env bash
# Set up Coastal Patrol on a RunPod pod. Run from the repo root:
#     ./deploy/runpod-setup.sh
#
# Order matters here. The GPU is proved to run real kernels FIRST, before any
# time is spent installing on top of it — on a Blackwell card under a mismatched
# torch you want to know in 30 seconds, not after a ten-minute pip install.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

say()  { printf "\n\033[1m==> %s\033[0m\n" "$1"; }
warn() { printf "\033[33m    !! %s\033[0m\n" "$1"; }

say "Step 1 — does this GPU actually run kernels?"
if ! PYTHON=python3 ./deploy/gpu-check.sh; then
  warn "Stopping. Installing on a GPU that cannot run kernels wastes your time"
  warn "and hides the real problem behind a pile of unrelated output."
  warn "Redeploy on a template whose CUDA matches the card, or pick a"
  warn "pre-Blackwell GPU (A40, L40S, A5000) and run this again."
  exit 1
fi

say "Step 2 — venv that REUSES the image's torch"
cd "$ROOT/backend"
[ -d venv ] || python3 -m venv --system-site-packages venv
PY="$ROOT/backend/venv/bin/python"
"$PY" -m pip install -qq --upgrade pip

# Record what we must not lose, so we can prove later that pip did not swap it.
TORCH_BEFORE="$("$PY" -c 'import torch; print(torch.__version__, torch.version.cuda)')"
echo "    torch in the image: $TORCH_BEFORE"

say "Step 3 — dependencies (torch deliberately excluded)"
"$PY" -m pip install -qq -r "$ROOT/deploy/requirements-runpod.txt"
# --no-deps: ultralytics resolves its own torch otherwise, and a generic PyPI
# wheel has no sm_120 kernels. Its remaining deps are installed explicitly.
"$PY" -m pip install -qq --no-deps ultralytics
"$PY" -m pip install -qq "pillow>=10" "pyyaml>=6" "requests>=2.31" "scipy>=1.10" \
                        "tqdm>=4" "psutil>=5.9" "matplotlib>=3.7" "seaborn>=0.12" "py-cpuinfo"

say "Step 4 — did pip quietly replace torch?"
TORCH_AFTER="$("$PY" -c 'import torch; print(torch.__version__, torch.version.cuda)')"
echo "    before: $TORCH_BEFORE"
echo "    after : $TORCH_AFTER"
if [ "$TORCH_BEFORE" != "$TORCH_AFTER" ]; then
  warn "torch CHANGED during install — the CUDA build you booted with is gone."
  warn "Reinstall the image's build, or redeploy the pod and install with"
  warn "--no-deps more aggressively."
  exit 1
fi

say "Step 5 — re-prove the GPU with the final environment"
PYTHON="$PY" ./deploy/gpu-check.sh || {
  warn "The GPU passed in step 1 but fails now. Something in the install"
  warn "displaced a CUDA library. Redeploy and re-run."
  exit 1
}

say "Step 6 — imports the pipeline needs"
"$PY" - <<'EOF'
import importlib, sys
bad = []
for m in ("cv2", "ultralytics", "sahi", "fastapi", "supabase", "pandas", "reportlab", "qrcode"):
    try:
        importlib.import_module(m)
        print(f"    {m}: ok")
    except Exception as e:
        print(f"    !! {m}: {e}"); bad.append(m)
sys.exit(1 if bad else 0)
EOF

say "Step 7 — runtime files"
for p in .env models static/sample.mp4 static/sample.srt; do
  if [ -e "$ROOT/backend/$p" ]; then echo "    ok      backend/$p"
  else echo "    MISSING backend/$p"; fi
done
[ -f "$ROOT/backend/.env" ] || warn "Write backend/.env from your RunPod env vars — see deploy/RUNPOD.md."
[ -d "$ROOT/backend/models" ] || warn "Run ./deploy/fetch-assets.sh to pull the weights and sample footage."

say "Ready"
echo "    cd backend && HOST=0.0.0.0 ./venv/bin/python main.py"
echo
echo "    Then run the bundled sample once and read the real throughput off the"
echo "    'inference' stage. On an M-series Mac it is 2760 tiles in 74.8s."
