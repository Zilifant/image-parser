"""Headless CLI for the processing engine — no GUI or server required.

    uv run python -m app.cli scan.png -o ./out
    uv run python -m app.cli ./scans/ -o ./out --profile dense-collages --clean-page

Detects the graphic elements on each input image and writes one transparent
PNG per element (plus, with --clean-page, a whole-page cleaned PNG).
"""

import argparse
import sys
from pathlib import Path

import cv2

from . import config, profiles
from .store import unique_path
from .cv.matte import clean_page, export_region, rasterize_polygon
from .cv.pipeline import detect_regions
from .cv.qc import check_export
from .schemas import DetectParams, ExportOptions


def _collect_inputs(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in inputs:
        path = Path(raw).expanduser()
        if path.is_dir():
            paths += sorted(
                p for p in path.iterdir()
                if p.is_file() and p.suffix.lower() in config.IMAGE_EXTENSIONS
            )
        elif path.is_file():
            paths.append(path)
        else:
            sys.exit(f"error: not found: {path}")
    if not paths:
        sys.exit("error: no input images")
    return paths


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="image-parser", description=__doc__)
    parser.add_argument("inputs", nargs="+", help="image files and/or directories of images")
    parser.add_argument("-o", "--out", required=True, help="output directory")
    parser.add_argument("--profile", help="processing profile name (see /api/profiles)")
    parser.add_argument("--style", choices=["ink", "binary"], help="alpha style")
    parser.add_argument("--rgb", choices=["pure_white", "original", "pure_black"], help="foreground color")
    parser.add_argument("--padding", type=int, help="crop padding in px")
    parser.add_argument("--merge-radius", type=int, help="grouping radius in px (0 = auto)")
    parser.add_argument("--clean-page", action="store_true", help="also write a whole-page cleaned PNG")
    args = parser.parse_args(argv)

    detect_params = DetectParams()
    export_options = ExportOptions()
    if args.profile:
        profile = profiles.get(args.profile)
        detect_params = profile.detect
        export_options = profile.export
    if args.merge_radius is not None:
        detect_params = detect_params.model_copy(update={"merge_radius": args.merge_radius})
    overrides = {
        key: value
        for key, value in (("style", args.style), ("rgb", args.rgb), ("padding", args.padding))
        if value is not None
    }
    if overrides:
        export_options = export_options.model_copy(update=overrides)

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    total_regions = total_flagged = 0
    for path in _collect_inputs(args.inputs):
        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if bgr is None:
            print(f"skip (not decodable): {path}")
            continue
        regions = detect_regions(bgr, detect_params)
        shape = bgr.shape[:2]
        flagged = 0
        for region in regions:
            mask = rasterize_polygon(region["polygon"], shape)
            rgba = export_region(bgr, tuple(region["bbox"]), mask, export_options)
            issues = check_export(rgba, export_options)
            if issues:
                flagged += 1
            target = unique_path(out_dir, f"{path.stem}_{region['label']}", ".png")
            cv2.imwrite(str(target), rgba)
        if args.clean_page:
            target = unique_path(out_dir, f"{path.stem}_clean", ".png")
            cv2.imwrite(str(target), clean_page(bgr, export_options))
        total_regions += len(regions)
        total_flagged += flagged
        print(f"{path.name}: {len(regions)} elements" + (f" ({flagged} with QC issues)" if flagged else ""))

    print(f"done: {total_regions} elements exported to {out_dir}"
          + (f", {total_flagged} with QC issues" if total_flagged else ""))


if __name__ == "__main__":
    main()
