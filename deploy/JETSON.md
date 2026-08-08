# Getting Coastal Patrol onto a Jetson Orin Nano

## Why not just `git clone`

Three things the app cannot start without are gitignored:

| | size | why it's ignored |
|---|---|---|
| `backend/models/` | 42 MB | weights, installed per-machine |
| `backend/static/sample.mp4` | 486 MB | `*.mp4` is ignored |
| `backend/.env` | 4 KB | secrets |

A clone gives you a server that boots and then fails with *"Unknown model"* and a
404 on the sample. Copy the working tree instead.

## 1. Copy it over

From the repo root on the Mac:

```bash
./deploy/push-to-jetson.sh nano@<jetson-ip>
```

**605 MB, 124 files** — venv, caches, `temp_uploads/` and the React Native app
are excluded. The script then checks over SSH that the three gitignored files
actually landed, because a silent miss there only surfaces much later.

## 2. Set it up

On the Jetson:

```bash
cd ~/coastal-patrol && ./deploy/jetson-setup.sh
```

## The two traps this exists to avoid

Both make the app **work but run ~20x slower**, with nothing in the logs saying
why. That is worse than a crash, so the setup script checks for both and exits
non-zero if either is wrong.

**1. PyPI's `torch` for aarch64 is CPU-only.** There is no CUDA in it. Install
NVIDIA's JetPack wheel for your L4T version *first*, from
`https://developer.download.nvidia.com/compute/redist/jp/`. `detect_device()`
prefers CUDA automatically, so once the right torch is present nothing else
needs changing — but with the wrong one, `torch.cuda.is_available()` is False
and SAHI quietly falls back to six CPU cores.

`ultralytics` is installed with `--no-deps` for exactly this reason: left alone,
it will pull the CPU wheel in over the top of your working install.

**2. `pip install opencv-python` shadows JetPack's OpenCV.** JetPack's build has
CUDA and GStreamer; the pip wheel has neither, so 4K H.265 decodes on the CPU.
On this hardware that is a bigger bottleneck than the inference. The venv is
created with `--system-site-packages` so it can see the system build, and
`opencv-python` is absent from `requirements-jetson.txt`.

Verify with `python -c "import cv2; print(cv2.__file__)"` — it should be under
`/usr/lib/python3/dist-packages/`, not inside `venv/`.

## 3. Before the event

```bash
sudo nvpmodel -m 2 && sudo jetson_clocks     # 25W MAXN Super
```

Without this the board sits at 15W and you will not get the throughput you
benchmarked. The Orin Nano dev kit needs its fan running for sustained
inference.

## Settings to change for 8 GB shared memory

`plan_execution()` defaults CUDA to `workers=2, batch_size=16`. That was tuned
on a machine with far more RAM, and on the Jetson CPU and GPU share the same
8 GB.

**Start with `workers=1`** — it is a form field on the dashboard, no code change
needed — and watch memory before trusting 2.

For reference, measured on this Mac after the streaming-upload fix: a 2.3 GB
video peaks at 981 MB resident. Before that fix it peaked at 3017 MB, which on
an 8 GB Jetson with JetPack's ~2 GB baseline plus CUDA worker contexts would
have been an OOM kill.

## Housekeeping

`backend/temp_uploads/` had grown to 2.7 GB of orphaned uploads on the dev
machine — the worker is supposed to delete its inputs and does not always. It is
excluded from the copy, but check it on the Jetson between runs:

```bash
du -sh backend/temp_uploads && rm -f backend/temp_uploads/*
```

`frame_cache/` also grows: ~45 annotated frames per mission at ~45 KB, so about
2 MB per flight. Harmless for an event, worth clearing between them.

## Expected performance

Measured on an M-series Mac with 2 MPS workers, from the pipeline's own counter:

```
2760 tiles in 74.8s   →  36.9 tile-inferences/s, 0.61 frames/s at 4K
```

At 3840×2160 with slice 512 / overlap 0.2 that is **60 tiles per sampled frame**.
Expect the Jetson to land in the same ballpark with a correct CUDA torch, and
meaningfully faster if you export the model to TensorRT
(`yolo export model=beach_litter.pt format=engine half=True`).

**This is an estimate, not a measurement** — I have no Jetson to test on. Run the
bundled sample once on the box and read the real number off the `inference`
stage before you rely on it.
