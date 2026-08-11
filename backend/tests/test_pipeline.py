from pathlib import Path

import cv2
import numpy as np
import pytest

from app.cv.matte import clean_page, export_region, rasterize_polygon
from app.cv.pipeline import detect_regions
from app.cv.qc import check_export
from app.schemas import DetectParams, ExportOptions

SAMPLE = Path(__file__).resolve().parent.parent.parent / "assets" / "raw-images" / "eyes-11.png"


@pytest.fixture(scope="module")
def sample_bgr() -> np.ndarray:
    bgr = cv2.imread(str(SAMPLE), cv2.IMREAD_COLOR)
    assert bgr is not None, f"sample image missing: {SAMPLE}"
    return bgr


@pytest.fixture(scope="module")
def regions(sample_bgr) -> list[dict]:
    return detect_regions(sample_bgr, DetectParams())


def test_detects_many_regions(sample_bgr, regions):
    assert 25 <= len(regions) <= 120

    h, w = sample_bgr.shape[:2]
    page_area = h * w
    for region in regions:
        x, y, bw, bh = region["bbox"]
        assert 0 <= x < w and 0 <= y < h
        assert x + bw <= w and y + bh <= h
        assert bw * bh < 0.9 * page_area, "no region should span (almost) the whole page"
        assert len(region["polygon"]) >= 3


def test_region_sizes_sane(sample_bgr, regions):
    h, w = sample_bgr.shape[:2]
    page_area = h * w
    areas = sorted(r["bbox"][2] * r["bbox"][3] for r in regions)
    median = areas[len(areas) // 2]
    assert 0.0005 * page_area <= median <= 0.10 * page_area


def test_matte_alpha(sample_bgr, regions):
    largest = max(regions, key=lambda r: r["bbox"][2] * r["bbox"][3])
    mask = rasterize_polygon(largest["polygon"], sample_bgr.shape[:2])
    rgba = export_region(sample_bgr, tuple(largest["bbox"]), mask, ExportOptions())

    assert rgba.shape[2] == 4
    alpha = rgba[:, :, 3]
    # Padding corners lie outside the polygon -> fully transparent.
    assert alpha[0, 0] == 0 and alpha[-1, -1] == 0 and alpha[0, -1] == 0 and alpha[-1, 0] == 0
    assert (alpha > 200).mean() > 0.05, "expect a solid chunk of opaque ink"


def test_white_on_transparency(sample_bgr, regions):
    """The brief's core transform: artwork white, background transparent."""
    largest = max(regions, key=lambda r: r["bbox"][2] * r["bbox"][3])
    mask = rasterize_polygon(largest["polygon"], sample_bgr.shape[:2])
    options = ExportOptions(rgb="pure_white")
    rgba = export_region(sample_bgr, tuple(largest["bbox"]), mask, options)

    solid = rgba[:, :, 3] > 200
    assert solid.any()
    assert int(rgba[:, :, :3][solid].min()) == 255, "all solid foreground must be pure white"
    assert check_export(rgba, options) == []


def test_clean_page(sample_bgr):
    rgba = clean_page(sample_bgr, ExportOptions(rgb="pure_white"))
    assert rgba.shape[:2] == sample_bgr.shape[:2]
    alpha = rgba[:, :, 3]
    assert (alpha > 200).mean() > 0.02, "plenty of solid ink"
    assert (alpha < 16).mean() > 0.3, "plenty of transparent paper"


def test_qc_catches_empty_export():
    empty = np.zeros((64, 64, 4), np.uint8)
    assert "empty-foreground" in check_export(empty, ExportOptions())


def test_auto_flagging(regions):
    statuses = {region["status"] for region in regions}
    assert statuses <= {"provisional", "flagged"}
    # The dense sample includes at least one suspicious region (e.g. the big
    # central diagram or something near the page border).
    assert any(region["status"] == "flagged" for region in regions)


def test_merge_radius_monotonic(sample_bgr):
    small = detect_regions(sample_bgr, DetectParams(merge_radius=3))
    large = detect_regions(sample_bgr, DetectParams(merge_radius=20))
    assert len(large) <= len(small)
