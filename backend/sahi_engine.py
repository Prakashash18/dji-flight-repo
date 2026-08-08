"""
SAHI inference kernel, backed by the upstream `sahi` package.

The pipeline originally sliced frames with our own `sahi_slicer` implementation.
This module runs the same job through the real SAHI library instead, using the
exact `get_sliced_prediction` call that was validated on this footage in Colab,
so detection quality in the portal matches what was tuned offline:

    get_sliced_prediction(
        rgb, model,
        slice_height=..., slice_width=...,
        overlap_height_ratio=..., overlap_width_ratio=...,
        perform_standard_pred=True,
        batch_size=8,
    )

SAHI brings its own merge step (GREEDYNMM over IOS by default), which is what
makes the difference on tile-edge duplicates that plain IoU NMS under-merges.

`sahi_slicer` is kept as an automatic fallback: if the package is missing in a
deployment image, missions still run rather than failing outright. Which backend
is live is reported to the dashboard, never silently swapped.

This module is import-safe in worker processes: it holds no model state.
"""

import inspect
from typing import Dict, List, Optional, Tuple

# The upstream library is optional at import time so a deployment without it
# still boots; the caller checks SAHI_AVAILABLE and reports the active backend.
try:
    from sahi import AutoDetectionModel  # noqa: F401
    from sahi.predict import get_sliced_prediction  # noqa: F401

    SAHI_AVAILABLE = True
    SAHI_IMPORT_ERROR = None
except Exception as e:  # pragma: no cover - depends on deployment image
    SAHI_AVAILABLE = False
    SAHI_IMPORT_ERROR = str(e)


BACKEND_SAHI = "sahi"
BACKEND_BUILTIN = "builtin"

BACKEND_LABELS = {
    BACKEND_SAHI: "SAHI library (get_sliced_prediction)",
    BACKEND_BUILTIN: "Built-in slicer (sahi_slicer.py)",
}


def normalize_device(device: Optional[str]) -> str:
    """Maps our short device names onto what SAHI/torch expect."""
    if not device:
        return "cpu"
    if device == "cuda":
        return "cuda:0"
    return device


def sahi_tile_count(
    frame_width: int,
    frame_height: int,
    slice_width: int,
    slice_height: int,
    overlap_ratio: float,
) -> int:
    """
    Number of tiles SAHI will cut a frame into.

    Uses SAHI's own `get_slice_bboxes` so the figure the dashboard shows is the
    real workload, not an approximation of it. Falls back to our slicer's grid
    when the library is absent.
    """
    if SAHI_AVAILABLE:
        try:
            from sahi.slicing import get_slice_bboxes

            return len(get_slice_bboxes(
                image_height=frame_height,
                image_width=frame_width,
                slice_height=slice_height,
                slice_width=slice_width,
                overlap_height_ratio=overlap_ratio,
                overlap_width_ratio=overlap_ratio,
            ))
        except Exception:
            pass

    from sahi_slicer import estimate_tile_count

    return estimate_tile_count(frame_width, frame_height, slice_width, slice_height, overlap_ratio)


def load_model(model_path: str, config: Dict) -> Tuple[object, str]:
    """
    Loads the detection model for one worker process.

    Returns (model, backend). `backend` is BACKEND_SAHI when the SAHI library
    loaded the weights, or BACKEND_BUILTIN when we fell back to a plain
    Ultralytics model driven by our own slicer.
    """
    device = normalize_device(config.get("device"))
    confidence = config.get("min_confidence", 0.35)

    if SAHI_AVAILABLE and config.get("sahi_enabled", True):
        # "ultralytics" covers YOLOv8 / YOLO11 / YOLO26; older SAHI releases only
        # register the "yolov8" alias for the same wrapper.
        last_error = None
        for model_type in ("ultralytics", "yolov8"):
            try:
                model = AutoDetectionModel.from_pretrained(
                    model_type=model_type,
                    model_path=model_path,
                    confidence_threshold=confidence,
                    device=device,
                )
                return model, BACKEND_SAHI
            except Exception as e:  # noqa: PERF203 - two-shot fallback by design
                last_error = e
        print(f"⚠️ SAHI could not load the weights ({last_error}); using the built-in slicer.")

    from ultralytics import YOLO

    model = YOLO(model_path)
    if device and device != "cpu":
        try:
            model.to(device)
        except Exception as e:
            print(f"⚠️ Worker could not move model to '{device}': {e}")
    return model, BACKEND_BUILTIN


def _supports_batch_size() -> bool:
    """Older SAHI releases have no batch_size parameter."""
    try:
        return "batch_size" in inspect.signature(get_sliced_prediction).parameters
    except (TypeError, ValueError):
        return False


def _predict_sahi(model, frame, config: Dict) -> Tuple[List[Dict], int]:
    """Runs the validated SAHI sliced-inference call over one BGR frame."""
    import cv2

    # SAHI expects RGB; OpenCV hands us BGR.
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    slice_width = config.get("slice_width", 512)
    slice_height = config.get("slice_height", 512)
    overlap_ratio = config.get("overlap_ratio", 0.2)

    kwargs = {
        "slice_height": slice_height,
        "slice_width": slice_width,
        "overlap_height_ratio": overlap_ratio,
        "overlap_width_ratio": overlap_ratio,
        "perform_standard_pred": config.get("include_full_frame", True),
        "verbose": 0,
    }
    if _supports_batch_size():
        kwargs["batch_size"] = config.get("batch_size", 8)

    result = get_sliced_prediction(rgb, model, **kwargs)

    detections: List[Dict] = []
    for prediction in result.object_prediction_list:
        x1, y1, x2, y2 = (float(v) for v in prediction.bbox.to_xyxy())
        detections.append({
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "confidence": float(prediction.score.value),
            "class_id": int(prediction.category.id),
            "class_name": prediction.category.name,
            # SAHI merges internally and does not expose how many tile hits backed
            # a box; downstream treats a missing count as a single hit.
            "merged_from": 1,
        })

    frame_height, frame_width = frame.shape[:2]
    tile_count = sahi_tile_count(frame_width, frame_height, slice_width, slice_height, overlap_ratio)
    return detections, tile_count


def predict(model, backend: str, frame, config: Dict) -> Tuple[List[Dict], int]:
    """
    Runs sliced inference over one frame.

    Returns (detections, tile_count) — the same shape the built-in slicer
    returns, so callers are identical across backends.
    """
    if backend == BACKEND_SAHI:
        return _predict_sahi(model, frame, config)

    from sahi_slicer import sliced_predict

    return sliced_predict(
        model,
        frame,
        min_confidence=config.get("min_confidence", 0.35),
        slice_width=config.get("slice_width", 512),
        slice_height=config.get("slice_height", 512),
        overlap_ratio=config.get("overlap_ratio", 0.2),
        include_full_frame=config.get("include_full_frame", True),
        batch_size=config.get("batch_size", 8),
        iou_threshold=config.get("iou_threshold", 0.4),
    )


def backend_status() -> Dict:
    """Describes the available backend, for startup logging and the dashboard."""
    return {
        "sahi_available": SAHI_AVAILABLE,
        "import_error": SAHI_IMPORT_ERROR,
        "label": BACKEND_LABELS[BACKEND_SAHI if SAHI_AVAILABLE else BACKEND_BUILTIN],
    }
