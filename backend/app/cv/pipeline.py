"""Classical-CV detection of individual graphic elements on a scanned page.

Tuned for high-contrast printed material (engravings, line art, halftones) on
paper: illumination-flattened binarization, then morphological stroke bridging
so a single element's hatching and detached strokes become one blob. The
bridging dilation radius (`merge_radius`) is the knob that decides what counts
as "one element" — larger values merge near neighbors, smaller values split.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from ..schemas import DetectParams
from ..store import new_id


@dataclass
class Blob:
    contour: np.ndarray  # outline snug to the ink (page coords), (N, 1, 2) int32
    bbox: tuple[int, int, int, int]  # tight bbox of the actual ink pixels


def normalize_illumination(gray: np.ndarray) -> np.ndarray:
    """Divide out the paper background so tint/stains become uniform white."""
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (51, 51))
    background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    return cv2.divide(gray, background, scale=255)


def binarize(norm: np.ndarray, params: DetectParams) -> np.ndarray:
    """Ink -> 255, paper -> 0."""
    if params.mode == "otsu":
        _, binary = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        return binary
    block_size = params.block_size | 1  # must be odd
    return cv2.adaptiveThreshold(
        norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block_size, params.c
    )


def effective_merge_radius(params: DetectParams, width: int) -> int:
    if params.merge_radius > 0:
        return params.merge_radius
    # ~6px at 1200px-wide scans, scaled linearly, clamped to something sane.
    return int(np.clip(round(width * 6 / 1200), 2, 30))


_KERNEL3 = np.ones((3, 3), np.uint8)
_KERNEL5 = np.ones((5, 5), np.uint8)


def _bridge_strokes(binary: np.ndarray, merge_radius: int) -> tuple[np.ndarray, int]:
    """Despeckle, then dilate so strokes of one element connect into one blob.

    Returns the bridged image and the number of dilation iterations used, so
    callers can erode back by the same amount (giving a morphological closing).
    """
    opened = cv2.morphologyEx(binary, cv2.MORPH_OPEN, _KERNEL3)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, _KERNEL5, iterations=2)
    dilate_iters = max(1, merge_radius // 2)
    return cv2.dilate(closed, _KERNEL3, iterations=dilate_iters), dilate_iters


def _confidence(contour: np.ndarray, area: float, page_area: float) -> float:
    hull = cv2.convexHull(contour)
    hull_area = max(cv2.contourArea(hull), 1.0)
    solidity = cv2.contourArea(contour) / hull_area
    # Mid-sized, reasonably solid blobs score highest; informational only.
    size_score = float(np.clip(area / (page_area * 0.001), 0.0, 1.0))
    return round(float(np.clip(0.3 + 0.4 * solidity + 0.3 * size_score, 0.0, 1.0)), 3)


def contour_to_polygon(contour: np.ndarray) -> list[list[float]]:
    epsilon = 0.002 * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    polygon = [[float(p[0][0]), float(p[0][1])] for p in approx]
    if len(polygon) < 3:  # degenerate after simplification; fall back to raw contour
        polygon = [[float(p[0][0]), float(p[0][1])] for p in contour]
    return polygon


def detect_blobs(
    bgr: np.ndarray, params: DetectParams, roi_mask: np.ndarray | None = None
) -> list[Blob]:
    """Full pipeline up to (but not including) region-dict emission.

    roi_mask, if given, restricts detection to a region of the page (used by split).
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    norm = normalize_illumination(gray)
    binary = binarize(norm, params)
    if roi_mask is not None:
        binary = cv2.bitwise_and(binary, roi_mask)

    h, w = gray.shape
    merge_radius = effective_merge_radius(params, w)
    bridged, dilate_iters = _bridge_strokes(binary, merge_radius)

    contours, _ = cv2.findContours(bridged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    page_area = float(h * w)
    min_area = params.min_area_frac * page_area
    max_area = params.max_area_frac * page_area

    blobs: list[Blob] = []
    for contour in contours:
        bx, by, bw, bh = cv2.boundingRect(contour)
        if bw * bh < min_area or bw * bh > max_area:
            continue

        # Work in a padded crop around the bridged blob for efficiency.
        pad = 2
        x0, y0 = max(0, bx - pad), max(0, by - pad)
        x1, y1 = min(w, bx + bw + pad), min(h, by + bh + pad)
        shifted = contour - np.array([x0, y0])

        blob_mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.drawContours(blob_mask, [shifted], -1, 255, thickness=cv2.FILLED)

        # Tight bbox from the actual ink pixels inside this blob.
        ink = cv2.bitwise_and(binary[y0:y1, x0:x1], blob_mask)
        ys, xs = np.nonzero(ink)
        if len(xs) == 0:
            continue
        tx0, ty0 = int(xs.min()), int(ys.min())
        tw, th = int(xs.max()) - tx0 + 1, int(ys.max()) - ty0 + 1
        if tw * th < min_area * 0.5 or tw * th > max_area:
            continue

        # Erode the bridged blob back by the dilation amount: the result is the
        # morphological closing of the ink — connected across small gaps but
        # snug to the element, so the outline doesn't invade neighbors.
        outline = cv2.erode(blob_mask, _KERNEL3, iterations=dilate_iters)
        outline = cv2.bitwise_or(outline, ink)  # never lose thin ink to erosion
        outline = cv2.morphologyEx(outline, cv2.MORPH_CLOSE, _KERNEL5)
        outline_contours, _ = cv2.findContours(outline, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not outline_contours:
            continue
        outline_contour = max(outline_contours, key=cv2.contourArea) + np.array([x0, y0])

        blobs.append(
            Blob(contour=outline_contour, bbox=(x0 + tx0, y0 + ty0, tw, th))
        )

    return blobs


def detect_regions(
    bgr: np.ndarray, params: DetectParams, roi_mask: np.ndarray | None = None
) -> list[dict]:
    h, w = bgr.shape[:2]
    page_area = float(h * w)
    blobs = detect_blobs(bgr, params, roi_mask)
    blobs.sort(key=lambda b: (b.bbox[1], b.bbox[0]))  # reading order-ish

    regions = []
    for i, blob in enumerate(blobs):
        x, y, bw, bh = blob.bbox
        confidence = _confidence(blob.contour, float(bw * bh), page_area)
        regions.append(
            {
                "id": new_id("r"),
                "bbox": [int(x), int(y), int(bw), int(bh)],
                "polygon": contour_to_polygon(blob.contour),
                "source": "auto",
                "confidence": confidence,
                "enabled": True,
                "label": f"element-{i + 1:02d}",
                "has_mask": False,
                "status": _auto_status(confidence, (x, y, bw, bh), (h, w)),
                "qc_issues": [],
            }
        )
    return regions


def _auto_status(
    confidence: float, bbox: tuple[int, int, int, int], shape: tuple[int, int]
) -> str:
    """Flag suspicious regions so review can jump straight to them."""
    x, y, bw, bh = bbox
    h, w = shape
    touches_border = x <= 2 or y <= 2 or x + bw >= w - 2 or y + bh >= h - 2
    very_large = bw * bh > 0.25 * h * w  # likely several designs merged
    if confidence < 0.55 or touches_border or very_large:
        return "flagged"
    return "provisional"
