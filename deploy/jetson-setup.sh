#!/usr/bin/env bash
# Set up Coastal Patrol on a Jetson Orin Nano running JetPack 6.x.
# Run from the repo root ON THE JETSON:  ./deploy/jetson-setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

say() { printf "\n\033[1m==> %s\033[0m\n" "$1"; }
warn() { printf "\033[33m    !! %s\033[0m\n" "$1"; }

say "Checking this is actually a Jetson"
if [ ! -f /etc/nv_tegra_release ]; then
  warn "No /etc/nv_tegra_release — this does not look like a JetPack image."
  warn "Continuing, but the CUDA torch install below will not work."
else
  head -1 /etc/nv_tegra_release
fi
python3 -c "import sys; print(f'    python {sys.version.split()[0]}')"

say "System packages (OpenCV with CUDA+GStreamer comes from JetPack, not pip)"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip python3-opencv libopenblas-dev

say "Creating the venv with --system-site-packages"
# This is the whole point: it lets the venv see JetPack's CUDA-enabled cv2 and
# the NVIDIA torch build, instead of pulling CPU-only wheels from PyPI.
cd "$ROOT/backend"
[ -d venv ] || python3 -m venv --system-site-packages venv
PY="$ROOT/backend/venv/bin/python"
"$PY" -m pip install -qq --upgrade pip

say "PyTorch"
if "$PY" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
  "$PY" -c "import torch; print(f'    torch {torch.__version__}, CUDA available')"
else
  warn "No CUDA-capable torch visible in the venv."
  warn "Install NVIDIA's JetPack wheel for your L4T version, then re-run this:"
  warn "  https://developer.download.nvidia.com/compute/redist/jp/"
  warn "Do NOT 'pip install torch' — PyPI's aarch64 wheel is CPU-only and the"
  warn "app will start, report no GPU, and run ~20x slower with no error."
fi

say "Python dependencies (torch/opencv deliberately excluded)"
"$PY" -m pip install -qq -r "$ROOT/deploy/requirements-jetson.txt"
# --no-deps so ultralytics cannot replace the JetPack torch with a CPU wheel.
"$PY" -m pip install -qq --no-deps ultralytics
"$PY" -m pip install -qq "pillow>=10" "pyyaml>=6" "requests>=2.31" "scipy>=1.10" "tqdm>=4" "psutil>=5.9"

say "Verifying the pieces the pipeline actually needs"
# `|| VERIFY=$?` matters: under `set -e` a non-zero exit here would abort the
# script before the summary below ever printed, hiding the very diagnosis the
# check exists to produce.
VERIFY=0
"$PY" - <<'EOF' || VERIFY=$?
import importlib, sys
ok = True
try:
    import torch
    cuda = torch.cuda.is_available()
    print(f"    torch {torch.__version__:<12} cuda={cuda}")
    if not cuda:
        print("    !! CPU-only torch: SAHI will be ~20x slower. Fix before the event.")
        ok = False
except Exception as e:
    print(f"    !! torch missing: {e}"); ok = False

try:
    import re as _re
    import cv2
    info = cv2.getBuildInformation()

    def _built(label):
        # Build info is whitespace-aligned and the alignment shifts between
        # OpenCV builds, so match the label and read its value, don't match a
        # fixed-width string.
        m = _re.search(rf"^\s*{label}\s*:\s*(\S+)", info, _re.MULTILINE)
        return bool(m) and m.group(1).upper().startswith("YES")

    gst = _built("GStreamer")
    print(f"    cv2   {cv2.__version__:<12} CUDA={_built('NVIDIA CUDA')} GStreamer={gst}")
    if not gst:
        print("    !! No GStreamer: 4K H.265 decodes on the CPU (NVDEC unused).")
        print("       Likely cause: pip's opencv-python is shadowing JetPack's build.")
        print("       Check with:  python -c \"import cv2; print(cv2.__file__)\"")
except Exception as e:
    print(f"    !! cv2 missing: {e}"); ok = False

for m in ("ultralytics", "sahi", "fastapi", "supabase"):
    try:
        importlib.import_module(m); print(f"    {m}: ok")
    except Exception as e:
        print(f"    !! {m}: {e}"); ok = False
sys.exit(0 if ok else 1)
EOF
VERIFY=$?

say "Runtime files that are gitignored and must be present"
for p in .env models static/sample.mp4 static/sample.srt; do
  if [ -e "$ROOT/backend/$p" ]; then echo "    ok      backend/$p"
  else echo "    MISSING backend/$p"; fi
done
"$PY" -m model_source list 2>/dev/null || warn "No models installed — see 'python -m model_source install'."

say "Power and thermals"
# 25W unlocks the 'Super' clocks. Without it the Orin Nano runs at 15W and the
# inference numbers you measured will not be the ones you get on the day.
sudo nvpmodel -q 2>/dev/null || true
warn "For the event: sudo nvpmodel -m 2 && sudo jetson_clocks   (25W MAXN Super)"

say "Done"
if [ "$VERIFY" -ne 0 ]; then
  warn "Verification reported problems above — fix those before relying on this."
  exit 1
fi
echo "    Start with:  cd backend && HOST=0.0.0.0 ./venv/bin/python main.py"
