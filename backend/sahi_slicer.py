"""
SAHI (Slicing Aided Hyper Inference) for aerial litter detection.

Drone footage is captured 30-80m above ground, so a plastic bottle occupies only
a handful of pixels in a 4K frame. Feeding the whole frame to YOLO downscales it
to 640x640 and those objects vanish. SAHI instead cuts the frame into overlapping
tiles, runs inference on each tile at native resolution, then maps the boxes back
into full-frame coordinates and merges the duplicates that the overlap produces.

This module is import-safe in worker processes: it holds no model state.
"""

from typing import List, Dict, Tuple, Optional
import math


# --- Slice geometry ---------------------------------------------------------

def compute_slices(
    frame_width: int,
    frame_height: int,
    slice_width: int = 640,
    slice_height: int = 640,
    overlap_ratio: float = 0.2,
) -> List[Tuple[int, int, int, int]]:
    """
    Builds the overlapping tile grid for one frame.

    Returns a list of (x1, y1, x2, y2) tile boxes in frame pixel coordinates.
    Tiles overlap by `overlap_ratio` so an object straddling a cut line is still
    seen whole by at least one tile. The final row/column is clamped back inside
    the frame rather than padded, which keeps every tile the same size for batching.
    """
    if frame_width <= 0 or frame_height <= 0:
        return []

    # A frame smaller than one tile needs no slicing at all.
    if frame_width <= slice_width and frame_height <= slice_height:
        return [(0, 0, frame_width, frame_height)]

    step_x = max(1, int(slice_width * (1.0 - overlap_ratio)))
    step_y = max(1, int(slice_height * (1.0 - overlap_ratio)))

    slices = []
    y = 0
    while y < frame_height:
        x = 0
        y2 = min(y + slice_height, frame_height)
        y1 = max(0, y2 - slice_height)
        while x < frame_width:
            x2 = min(x + slice_width, frame_width)
            x1 = max(0, x2 - slice_width)
            slices.append((x1, y1, x2, y2))
            if x2 >= frame_width:
                break
            x += step_x
        if y2 >= frame_height:
            break
        y += step_y

    # Clamping the trailing tiles can produce exact duplicates; drop them.
    return list(dict.fromkeys(slices))


def estimate_tile_count(
    frame_width: int,
    frame_height: int,
    slice_width: int = 640,
    slice_height: int = 640,
    overlap_ratio: float = 0.2,
) -> int:
    """Tile count for a frame, without materialising the grid (used for UI stats)."""
    return len(compute_slices(frame_width, frame_height, slice_width, slice_height, overlap_ratio))


# --- Box merging ------------------------------------------------------------

def _iou(a: Dict, b: Dict) -> float:
    """Intersection-over-union of two boxes in {x1,y1,x2,y2} form."""
    ix1 = max(a["x1"], b["x1"])
    iy1 = max(a["y1"], b["y1"])
    ix2 = min(a["x2"], b["x2"])
    iy2 = min(a["y2"], b["y2"])

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0

    area_a = max(0.0, a["x2"] - a["x1"]) * max(0.0, a["y2"] - a["y1"])
    area_b = max(0.0, b["x2"] - b["x1"]) * max(0.0, b["y2"] - b["y1"])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _containment(inner: Dict, outer: Dict) -> float:
    """
    Fraction of `inner` that falls inside `outer`.

    IoU alone under-merges in SAHI: the same bottle seen at a tile edge yields a
    clipped box and a whole box whose IoU can sit below threshold even though one
    clearly contains the other. Containment catches those.
    """
    ix1 = max(inner["x1"], outer["x1"])
    iy1 = max(inner["y1"], outer["y1"])
    ix2 = min(inner["x2"], outer["x2"])
    iy2 = min(inner["y2"], outer["y2"])

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_inner = max(0.0, inner["x2"] - inner["x1"]) * max(0.0, inner["y2"] - inner["y1"])
    return inter / area_inner if area_inner > 0 else 0.0


def merge_detections(
    detections: List[Dict],
    iou_threshold: float = 0.4,
    containment_threshold: float = 0.75,
) -> List[Dict]:
    """
    Greedy NMS over detections pooled from every tile of a single frame.

    Detections are dicts with x1,y1,x2,y2,confidence,class_name. Boxes are only
    ever merged with others of the same class. Highest-confidence box wins and
    absorbs its duplicates; the survivor records how many raw tile hits backed it
    up in `merged_from`, which the dashboard surfaces as evidence strength.
    """
    if not detections:
        return []

    ordered = sorted(detections, key=lambda d: d["confidence"], reverse=True)
    kept: List[Dict] = []

    for candidate in ordered:
        duplicate_of = None
        for survivor in kept:
            if survivor["class_name"] != candidate["class_name"]:
                continue
            if (
                _iou(candidate, survivor) >= iou_threshold
                or _containment(candidate, survivor) >= containment_threshold
            ):
                duplicate_of = survivor
                break

        if duplicate_of is None:
            merged = dict(candidate)
            merged["merged_from"] = 1
            kept.append(merged)
        else:
            duplicate_of["merged_from"] = duplicate_of.get("merged_from", 1) + 1

    return kept


# --- Inference --------------------------------------------------------------

def _boxes_to_dicts(result, model_names, offset_x: int = 0, offset_y: int = 0) -> List[Dict]:
    """Converts one Ultralytics result into frame-space detection dicts."""
    out = []
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return out

    for box in boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
        out.append({
            "x1": x1 + offset_x,
            "y1": y1 + offset_y,
            "x2": x2 + offset_x,
            "y2": y2 + offset_y,
            "confidence": conf,
            "class_id": cls_id,
            "class_name": model_names.get(cls_id, str(cls_id)) if isinstance(model_names, dict) else str(cls_id),
        })
    return out


def sliced_predict(
    model,
    frame,
    min_confidence: float = 0.35,
    slice_width: int = 640,
    slice_height: int = 640,
    overlap_ratio: float = 0.2,
    include_full_frame: bool = True,
    batch_size: int = 8,
    iou_threshold: float = 0.4,
) -> Tuple[List[Dict], int]:
    """
    Runs SAHI inference over one frame.

    Tiles are cropped and pushed through the model in batches (Ultralytics accepts
    a list of arrays), then remapped and NMS-merged. When `include_full_frame` is
    set an additional standard pass over the downscaled whole frame runs too — it
    catches large objects that no single tile fully contains, and its boxes merge
    into the tile results naturally.

    Returns (merged_detections, tile_count).
    """
    frame_height, frame_width = frame.shape[:2]
    slices = compute_slices(frame_width, frame_height, slice_width, slice_height, overlap_ratio)

    model_names = getattr(model, "names", {})
    pooled: List[Dict] = []

    # Tiled passes, batched to keep the model busy.
    for start in range(0, len(slices), batch_size):
        chunk = slices[start:start + batch_size]
        crops = [frame[y1:y2, x1:x2] for (x1, y1, x2, y2) in chunk]
        crops = [c for c in crops if c.size > 0]
        if not crops:
            continue

        results = model(crops, conf=min_confidence, verbose=False)
        for (x1, y1, _x2, _y2), result in zip(chunk, results):
            pooled.extend(_boxes_to_dicts(result, model_names, offset_x=x1, offset_y=y1))

    # Full-frame pass for objects too large for a single tile.
    if include_full_frame and len(slices) > 1:
        full_results = model(frame, conf=min_confidence, verbose=False)
        for result in full_results:
            pooled.extend(_boxes_to_dicts(result, model_names))

    return merge_detections(pooled, iou_threshold=iou_threshold), len(slices)
