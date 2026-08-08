#!/usr/bin/env bash
# Prove the GPU actually runs kernels, BEFORE installing anything on top of it.
#
#     ./deploy/gpu-check.sh
#
# `torch.cuda.is_available()` is not the test. On a card whose architecture the
# installed torch was not built for — a Blackwell sm_120 board under a cu124
# build, say — it returns True, reports the right device name, and then throws
# the moment you ask it to compute. Run a real matmul and a real conv.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-python3}"
# Resolve against the script, not the caller's cwd.
[ -x "$HERE/../backend/venv/bin/python" ] && PY="$HERE/../backend/venv/bin/python"

"$PY" - <<'EOF'
import sys

try:
    import torch
except Exception as e:
    sys.exit(f"FAIL  torch will not import: {e}")

print(f"torch      {torch.__version__}")
print(f"built for  CUDA {torch.version.cuda}")
try:
    print(f"kernels    {' '.join(torch.cuda.get_arch_list())}")
except Exception:
    print("kernels    (could not read arch list)")

if not torch.cuda.is_available():
    print("\nFAIL  No CUDA device visible.")
    print("      Everything will run on CPU at roughly 1/20th the speed.")
    sys.exit(1)

name = torch.cuda.get_device_name(0)
cap = torch.cuda.get_device_capability(0)
sm = f"sm_{cap[0]}{cap[1]}"
print(f"device     {name}  ({sm})")

arches = []
try:
    arches = [a for a in torch.cuda.get_arch_list() if a.startswith("sm_")]
except Exception:
    pass
if arches and sm not in arches:
    print(f"\nWARNING  This torch has no {sm} kernels compiled in.")
    print(f"         It may still work via PTX JIT — the tests below decide it.")

# The actual proof. Each of these is a different kernel family, and a mismatched
# build can pass one and fail another.
def probe(label, fn):
    try:
        out = fn()
        torch.cuda.synchronize()
        print(f"  ok    {label}  -> {out}")
        return True
    except Exception as e:
        msg = str(e).split("\n")[0][:120]
        print(f"  FAIL  {label}  -> {type(e).__name__}: {msg}")
        return False

print("\nrunning real kernels:")
ok = True
ok &= probe("matmul   ", lambda: float(
    (torch.randn(512, 512, device="cuda") @ torch.randn(512, 512, device="cuda")).sum()))
ok &= probe("conv2d   ", lambda: tuple(
    torch.nn.Conv2d(3, 16, 3, padding=1).cuda()(torch.randn(1, 3, 64, 64, device="cuda")).shape))
ok &= probe("half prec", lambda: float(
    (torch.randn(256, 256, device="cuda", dtype=torch.float16) @
     torch.randn(256, 256, device="cuda", dtype=torch.float16)).float().sum()))

if not ok:
    print("\nFAIL  The GPU is visible but cannot run these kernels.")
    print("      This torch build does not match this card's architecture.")
    print("      Fix: redeploy on a template whose CUDA matches the GPU, or")
    print("      switch to a pre-Blackwell card (A40, L40S, A5000).")
    sys.exit(1)

print("\nPASS  GPU runs real kernels. Safe to continue.")
EOF
