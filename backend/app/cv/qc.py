"""Automated quality checks on exported crops.

Every export is validated; failing regions are routed back to review by
flagging them (see the export router). Issues are short stable slugs so the
frontend can display/translate them.
"""

import cv2
import numpy as np

from ..schemas import ExportOptions

MIN_DIMENSION = 8
MIN_FOREGROUND_PIXELS = 20
ALPHA_FOREGROUND = 16  # alpha above this counts as foreground
# The soft "ink" style gives faint paper texture a little alpha, so the
# cut-off check only fires on substantial ink at the crop edge.
ALPHA_EDGE = 64


def check_export(rgba: np.ndarray, options: ExportOptions) -> list[str]:
    issues: list[str] = []

    if rgba.ndim != 3 or rgba.shape[2] != 4:
        return ["no-alpha-channel"]

    h, w = rgba.shape[:2]
    if h < MIN_DIMENSION or w < MIN_DIMENSION:
        issues.append("too-small")

    alpha = rgba[:, :, 3]
    foreground = alpha > ALPHA_FOREGROUND
    if int(foreground.sum()) < MIN_FOREGROUND_PIXELS:
        issues.append("empty-foreground")
        return issues

    # Foreground running into the crop edge suggests a cut-off design.
    solid_foreground = alpha > ALPHA_EDGE
    edge = np.zeros_like(solid_foreground)
    edge[0, :] = edge[-1, :] = True
    edge[:, 0] = edge[:, -1] = True
    if bool((solid_foreground & edge).any()):
        issues.append("touches-edge")

    if options.rgb == "pure_white":
        solid = alpha > 200
        if bool(solid.any()) and int(rgba[:, :, :3][solid].min()) < 250:
            issues.append("foreground-not-white")
    elif options.rgb == "pure_black":
        solid = alpha > 200
        if bool(solid.any()) and int(rgba[:, :, :3][solid].max()) > 5:
            issues.append("foreground-not-black")

    return issues


def check_export_file(path: str, options: ExportOptions) -> list[str]:
    rgba = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if rgba is None:
        return ["decode-failed"]
    return check_export(rgba, options)
