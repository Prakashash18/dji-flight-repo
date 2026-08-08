"""
Multi-core SAHI inference pool.

SAHI multiplies the work per frame by the tile count, so a serial loop is far too
slow for a full patrol video. Frames are independent, which makes frame-level
parallelism the clean split: a pool of worker processes each holds its own
detection model and chews through whole frames, saturating every physical core.

The per-frame inference itself lives in `sahi_engine`, which runs the upstream
SAHI library when it is installed and falls back to our own slicer otherwise.
This module owns only the parallelism, not the detection strategy.

Frames cross the process boundary as JPEG bytes rather than raw arrays — a 4K
frame is ~25MB raw but ~400KB encoded, and pickling the raw array costs more than
the encode/decode round trip.

Note this deliberately gives up Bot-SORT tracking, which needs strictly sequential
frame state. The caller's spatial clustering (same class within a few metres)
handles de-duplication instead, and is in fact more robust across a patrol pass
where the drone revisits the same ground.
"""

import os
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional

import cv2
import numpy as np

import sahi_engine

# Per-worker globals, populated once by the pool initializer.
_WORKER_MODEL = None
_WORKER_CONFIG: Dict = {}
_WORKER_BACKEND: str = sahi_engine.BACKEND_BUILTIN


def detect_device() -> str:
    """
    Picks the fastest available inference backend: cuda > mps > cpu.

    Apple Silicon reports MPS, which for this workload measured ~3x faster than
    saturating every CPU core (see plan_execution for the numbers).
    """
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def plan_execution(requested_workers: Optional[int] = None, device: Optional[str] = None):
    """
    Chooses device, worker count and tile batch size together.

    These three settings are not independent, and the right answer differs sharply
    by backend. Benchmarked on an M1 Pro (10 cores) over 8 frames of 4K footage at
    32 tiles per frame, all configurations returning identical detections:

        cpu, 9 workers, batch 4   4.61 s/frame
        cpu, 6 workers, batch 4   2.82 s/frame
        cpu, 8 workers, batch 2   2.08 s/frame   <- best CPU
        mps, 1 worker,  batch 16  1.25 s/frame
        mps, 2 workers, batch 16  1.13 s/frame   <- best overall

    The lesson is that a GPU is one shared resource: piling on processes only adds
    contention, so an accelerator gets a small pool sized to keep it fed while the
    parent decodes and georeferences. CPU-only machines do want one process per
    core, but with small batches — large batches there blow the cache and measured
    twice as slow.

    Returns (device, workers, batch_size).
    """
    device = device or detect_device()
    cores = os.cpu_count() or 4

    if device in ("mps", "cuda"):
        # The accelerator is the bottleneck; a couple of feeder processes is plenty.
        workers = requested_workers if (requested_workers and requested_workers > 0) else 2
        workers = max(1, min(workers, 4))
        return device, workers, 16

    # CPU: one process per core, leaving headroom for the server and reader thread.
    workers = requested_workers if (requested_workers and requested_workers > 0) else max(1, cores - 2)
    workers = max(1, min(workers, cores * 2))
    return device, workers, 2


def resolve_worker_count(requested: Optional[int] = None) -> int:
    """Worker count alone, for callers that only need to report it."""
    return plan_execution(requested)[1]


def _init_worker(model_path: str, config: Dict):
    """
    Pool initializer: loads the detection model once per process.

    Each worker is pinned to a single compute thread. Without this, every worker
    spawns its own full-width intra-op thread pool and N workers produce N x cores
    threads that thrash the scheduler — measured at ~5x slower per inference with
    9 workers. Parallelism belongs at the process level here, not inside torch.

    The thread caps must be environment variables set BEFORE torch is imported:
    torch.set_num_threads() alone is not enough, because the underlying OpenMP /
    Accelerate pools are sized at import time and ignore the later call.
    """
    global _WORKER_MODEL, _WORKER_CONFIG, _WORKER_BACKEND

    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[var] = "1"

    try:
        import torch
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
    except Exception:
        pass

    # OpenCV over-subscribes the same way with its own thread pool.
    try:
        cv2.setNumThreads(1)
    except Exception:
        pass

    # sahi_engine picks the SAHI library when it is installed and falls back to
    # a plain Ultralytics model driven by our own slicer otherwise. Device
    # placement is handled inside the loader for both paths.
    _WORKER_MODEL, _WORKER_BACKEND = sahi_engine.load_model(model_path, config)
    _WORKER_CONFIG = config


def _infer_frame(payload: Dict) -> Dict:
    """
    Worker entrypoint: decode one JPEG frame, run SAHI over it, return detections.

    Returns plain dicts (never tensors or Ultralytics objects) so the result
    pickles cheaply back to the parent.
    """
    global _WORKER_MODEL, _WORKER_CONFIG, _WORKER_BACKEND

    frame_index = payload["frame_index"]
    time_ms = payload["time_ms"]

    try:
        buffer = np.frombuffer(payload["jpeg"], dtype=np.uint8)
        frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if frame is None:
            return {"frame_index": frame_index, "time_ms": time_ms, "detections": [], "tile_count": 0,
                    "backend": _WORKER_BACKEND, "error": "frame decode failed"}

        detections, tile_count = sahi_engine.predict(
            _WORKER_MODEL, _WORKER_BACKEND, frame, _WORKER_CONFIG
        )

        return {
            "frame_index": frame_index,
            "time_ms": time_ms,
            "detections": detections,
            "tile_count": tile_count,
            "backend": _WORKER_BACKEND,
            "error": None,
        }
    except Exception as e:
        # A single bad frame must never take down the pool or the mission.
        return {"frame_index": frame_index, "time_ms": time_ms, "detections": [], "tile_count": 0,
                "backend": _WORKER_BACKEND, "error": str(e)}


class SahiInferencePool:
    """
    Context-managed process pool that runs SAHI over frames.

    Usage:
        with SahiInferencePool(model_path, config, workers=9) as pool:
            future = pool.submit(frame_index, time_ms, frame)
            result = future.result()
    """

    def __init__(self, model_path: str, config: Dict, workers: Optional[int] = None,
                 jpeg_quality: int = 92):
        self.model_path = model_path
        self.config = config
        # Resolve against the device this pool was actually configured for, not a
        # fresh detection. Re-detecting would clamp a deliberate CPU plan of 8
        # workers down to the accelerator ceiling of 4 on a machine that has a GPU.
        self.workers = workers if (workers and workers > 0) else \
            plan_execution(None, config.get("device"))[1]
        self.jpeg_quality = jpeg_quality
        self._executor: Optional[ProcessPoolExecutor] = None

    def __enter__(self) -> "SahiInferencePool":
        self._executor = ProcessPoolExecutor(
            max_workers=self.workers,
            initializer=_init_worker,
            initargs=(self.model_path, self.config),
        )
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=exc_type is not None)
            self._executor = None
        return False

    def encode_frame(self, frame) -> bytes:
        """
        JPEG-encodes a frame for transport.

        Exposed separately so the caller can hold the compressed bytes for later
        crop extraction instead of pinning raw 4K arrays in memory while frames
        are in flight.
        """
        ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
        if not ok:
            raise ValueError("Failed to JPEG-encode frame")
        return buffer.tobytes()

    def submit_jpeg(self, frame_index: int, time_ms: float, jpeg_bytes: bytes):
        """Queues an already-encoded frame for inference. Returns a Future."""
        if not self._executor:
            raise RuntimeError("SahiInferencePool used outside its context manager")

        return self._executor.submit(_infer_frame, {
            "frame_index": frame_index,
            "time_ms": time_ms,
            "jpeg": jpeg_bytes,
        })

    def submit(self, frame_index: int, time_ms: float, frame):
        """Encodes a frame and queues it for inference. Returns a Future."""
        return self.submit_jpeg(frame_index, time_ms, self.encode_frame(frame))


def run_serial(model_path: str, config: Dict):
    """
    Single-process fallback used when the pool cannot start.

    Sandboxed or restricted environments sometimes forbid process spawning; a
    slower mission beats a failed one. Returns a callable with the same shape as
    the worker so the caller's loop is unchanged.
    """
    _init_worker(model_path, config)

    def _run(frame_index: int, time_ms: float, frame) -> Dict:
        # In-process there is no boundary to cross, so run SAHI on the frame we
        # already hold. Round-tripping it through JPEG here would encode and decode
        # a 4K frame for nothing, on the path taken precisely because the machine
        # is already degraded.
        try:
            detections, tile_count = sahi_engine.predict(
                _WORKER_MODEL, _WORKER_BACKEND, frame, _WORKER_CONFIG
            )
            return {"frame_index": frame_index, "time_ms": time_ms,
                    "detections": detections, "tile_count": tile_count,
                    "backend": _WORKER_BACKEND, "error": None}
        except Exception as e:
            return {"frame_index": frame_index, "time_ms": time_ms, "detections": [],
                    "tile_count": 0, "backend": _WORKER_BACKEND, "error": str(e)}

    return _run
