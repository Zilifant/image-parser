"""Optional Potrace adapter: vectorize a region's binary mask into SVG.

Potrace is an external CLI tool (`brew install potrace`). Like SAM, it is
strictly optional — `is_available()` gates the endpoint and the UI.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

from ..schemas import ExportOptions
from .matte import export_region


def is_available() -> bool:
    return shutil.which("potrace") is not None


def region_to_svg(
    bgr: np.ndarray,
    bbox: tuple[int, int, int, int],
    region_mask: np.ndarray,
    options: ExportOptions,
) -> bytes:
    """Renders the region with a hard (binary) alpha and traces it."""
    hard = options.model_copy(update={"style": "binary"})
    rgba = export_region(bgr, bbox, region_mask, hard)
    ink = (rgba[:, :, 3] > 128).astype(np.uint8) * 255

    with tempfile.TemporaryDirectory() as tmp:
        pgm = Path(tmp) / "mask.pgm"
        svg = Path(tmp) / "mask.svg"
        cv2.imwrite(str(pgm), 255 - ink)  # potrace traces black pixels
        fill = {"pure_white": "#ffffff", "pure_black": "#000000"}.get(options.rgb, "#000000")
        subprocess.run(
            ["potrace", str(pgm), "--svg", "--color", fill, "-o", str(svg)],
            check=True,
            capture_output=True,
        )
        return svg.read_bytes()
