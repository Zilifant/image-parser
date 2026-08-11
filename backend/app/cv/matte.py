"""Turn a region of a scanned page into an alpha-matted RGBA crop.

The page-level detection mask is intentionally coarse; here the crop is
re-thresholded locally (on the illumination-normalized image) inside the
region so fine hatching and halftone dots survive with soft alpha.
"""

import cv2
import numpy as np

from ..schemas import ExportOptions
from .pipeline import normalize_illumination


def rasterize_polygon(polygon: list, shape: tuple[int, int]) -> np.ndarray:
    mask = np.zeros(shape, np.uint8)
    points = np.array([[round(x), round(y)] for x, y in polygon], np.int32)
    cv2.fillPoly(mask, [points], 255)
    return mask


def export_region(
    bgr: np.ndarray,
    bbox: tuple[int, int, int, int],
    region_mask: np.ndarray,
    options: ExportOptions,
) -> np.ndarray:
    """region_mask is full-page sized (255 inside the region). Returns RGBA."""
    h, w = bgr.shape[:2]
    x, y, bw, bh = bbox
    pad = options.padding
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)

    crop = bgr[y0:y1, x0:x1]
    mask_crop = region_mask[y0:y1, x0:x1]

    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    norm = normalize_illumination(gray)

    if options.style == "binary":
        # Hard ink mask, lightly feathered.
        _, ink = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        alpha = cv2.bitwise_and(ink, mask_crop)
        alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    else:
        # "ink": darkness becomes opacity, so halftones fade out naturally.
        alpha = cv2.subtract(np.full_like(norm, 255), norm)
        alpha[mask_crop == 0] = 0

    if options.rgb == "pure_black":
        rgb = np.zeros_like(crop)
    elif options.rgb == "pure_white":
        rgb = np.full_like(crop, 255)
    else:
        rgb = crop

    rgba = cv2.cvtColor(rgb, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = alpha
    return rgba


def clean_page(bgr: np.ndarray, options: ExportOptions) -> np.ndarray:
    """Whole-page cleanup: all ink kept, background transparent.

    Produces the brief's "clean white-on-transparent full-page PNG" (or the
    other rgb modes) without any region segmentation.
    """
    h, w = bgr.shape[:2]
    full = np.full((h, w), 255, np.uint8)
    return export_region(bgr, (0, 0, w, h), full, options.model_copy(update={"padding": 0}))
