"""Optional Segment Anything (MobileSAM) backend.

The app must work without this: torch/mobile-sam are an optional dependency
group (`uv sync --extra sam`) and the checkpoint is downloaded separately
(`make download-sam`). Everything here degrades to `is_available() == False`.
"""

from collections import OrderedDict
from threading import Lock

import numpy as np

from .. import config

_lock = Lock()
_predictor = None
# page_id -> embedded flag; the predictor holds one embedding at a time, so we
# track which page it currently has and re-embed on switch (LRU of 1 in
# practice; keep last 2 page ids to avoid thrash logging).
_embedded_page: list[str] = []


def is_available() -> bool:
    if not config.SAM_CHECKPOINT.exists():
        return False
    try:
        import mobile_sam  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def _get_predictor():
    global _predictor
    if _predictor is not None:
        return _predictor
    import torch
    from mobile_sam import SamPredictor, sam_model_registry

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = sam_model_registry["vit_t"](checkpoint=str(config.SAM_CHECKPOINT))
    model.to(device=device)
    model.eval()
    _predictor = SamPredictor(model)
    return _predictor


def predict_mask(
    page_id: str,
    bgr: np.ndarray,
    points: list[tuple[float, float, int]] | None,
    box: tuple[float, float, float, float] | None,
) -> np.ndarray:
    """Returns a uint8 mask (255 = element) the size of the page."""
    with _lock:
        predictor = _get_predictor()
        if not _embedded_page or _embedded_page[-1] != page_id:
            rgb = bgr[:, :, ::-1]
            predictor.set_image(np.ascontiguousarray(rgb))
            _embedded_page.append(page_id)
            del _embedded_page[:-2]

        point_coords = point_labels = sam_box = None
        if points:
            point_coords = np.array([[p[0], p[1]] for p in points])
            point_labels = np.array([p[2] for p in points])
        if box:
            x, y, w, h = box
            sam_box = np.array([x, y, x + w, y + h])

        masks, scores, _ = predictor.predict(
            point_coords=point_coords,
            point_labels=point_labels,
            box=sam_box,
            multimask_output=True,
        )
        best = masks[int(np.argmax(scores))]
        return (best.astype(np.uint8)) * 255
