import io
import re
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from .. import jobs, store
from ..cv import potrace_backend
from ..cv.matte import clean_page, export_region, rasterize_polygon
from ..cv.qc import check_export
from ..schemas import BatchExportRequest, ExportOptions, JobStatus, PageExportRequest

router = APIRouter(tags=["export"])


def _region_mask(project_id: str, page_id: str, page: dict, region: dict) -> np.ndarray:
    mask = store.load_mask(project_id, page_id, region["id"]) if region.get("has_mask") else None
    if mask is None:
        mask = rasterize_polygon(region["polygon"], (page["height"], page["width"]))
    return mask


def _export_one(
    project_id: str, page_id: str, page: dict, bgr: np.ndarray, region: dict, options: ExportOptions
) -> Path:
    """Exports one region, runs QC on the result, and records the outcome on
    the region (QC failures route it back to review via 'flagged')."""
    mask = _region_mask(project_id, page_id, page, region)
    rgba = export_region(bgr, tuple(region["bbox"]), mask, options)
    out_dir = store.exports_dir(project_id, page_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{region['id']}.png"
    cv2.imwrite(str(path), rgba)

    issues = check_export(rgba, options)
    region["qc_issues"] = issues
    if issues and region.get("status") != "approved":
        region["status"] = "flagged"
    return path


def _export_url(project_id: str, page_id: str, region_id: str) -> str:
    return f"/api/projects/{project_id}/pages/{page_id}/exports/{region_id}.png"


@router.post("/projects/{project_id}/pages/{page_id}/regions/{region_id}/export")
def export_single(project_id: str, page_id: str, region_id: str, options: ExportOptions):
    page = store.load_page(project_id, page_id)
    region = store.get_region(page, region_id)
    bgr = store.load_page_image(project_id, page_id)
    _export_one(project_id, page_id, page, bgr, region, options)
    store.save_page(project_id, page)
    return {"export_url": _export_url(project_id, page_id, region_id), "qc_issues": region["qc_issues"]}


@router.post("/projects/{project_id}/pages/{page_id}/export")
def export_page(project_id: str, page_id: str, body: PageExportRequest):
    page = store.load_page(project_id, page_id)
    bgr = store.load_page_image(project_id, page_id)
    if body.region_ids is not None:
        regions = [store.get_region(page, rid) for rid in body.region_ids]
    else:
        regions = [r for r in page["regions"] if r["enabled"]]
    if not regions:
        raise HTTPException(400, "no regions to export")
    exports = []
    for region in regions:
        _export_one(project_id, page_id, page, bgr, region, body)
        exports.append(
            {
                "region_id": region["id"],
                "url": _export_url(project_id, page_id, region["id"]),
                "qc_issues": region["qc_issues"],
            }
        )
    store.save_page(project_id, page)
    return {"exports": exports}


@router.get("/projects/{project_id}/pages/{page_id}/exports/{region_id}.png")
def get_export(project_id: str, page_id: str, region_id: str):
    path = store.exports_dir(project_id, page_id) / f"{region_id}.png"
    if not path.exists():
        raise HTTPException(404, "export not found")
    return FileResponse(path, media_type="image/png")


@router.post("/projects/{project_id}/pages/{page_id}/export-clean-page")
def export_clean_page(project_id: str, page_id: str, options: ExportOptions):
    """Whole-page cleanup: every bit of ink kept, background transparent."""
    page = store.load_page(project_id, page_id)
    bgr = store.load_page_image(project_id, page_id)
    rgba = clean_page(bgr, options)
    path = store.page_dir(project_id, page_id) / "clean.png"
    cv2.imwrite(str(path), rgba)
    return {"url": f"/api/projects/{project_id}/pages/{page_id}/clean.png"}


@router.get("/projects/{project_id}/pages/{page_id}/clean.png")
def get_clean_page(project_id: str, page_id: str):
    path = store.page_dir(project_id, page_id) / "clean.png"
    if not path.exists():
        raise HTTPException(404, "clean page not exported yet")
    return FileResponse(path, media_type="image/png")


@router.get("/projects/{project_id}/pages/{page_id}/contact-sheet.png")
def contact_sheet(project_id: str, page_id: str):
    """Numbered grid of this page's exported crops, for quick review."""
    from PIL import Image, ImageDraw

    page = store.load_page(project_id, page_id)
    exports_dir = store.exports_dir(project_id, page_id)
    entries = [
        (region, exports_dir / f"{region['id']}.png")
        for region in page["regions"]
        if (exports_dir / f"{region['id']}.png").exists()
    ]
    if not entries:
        raise HTTPException(404, "no exports yet — export the page first")

    tile, pad = 180, 8
    columns = max(1, min(8, int(np.ceil(np.sqrt(len(entries))))))
    rows = int(np.ceil(len(entries) / columns))
    sheet = Image.new("RGB", (columns * (tile + pad) + pad, rows * (tile + pad + 16) + pad), (72, 76, 84))
    draw = ImageDraw.Draw(sheet)

    for i, (region, path) in enumerate(entries):
        crop = Image.open(path).convert("RGBA")
        crop.thumbnail((tile, tile))
        col, row = i % columns, i // columns
        x = pad + col * (tile + pad)
        y = pad + row * (tile + pad + 16)
        sheet.paste(crop, (x + (tile - crop.width) // 2, y + (tile - crop.height) // 2), crop)
        flag = " ⚑" if region.get("status") == "flagged" else ""
        draw.text((x + 2, y + tile + 2), f"{region['label']}{flag}", fill=(230, 233, 239))

    buffer = io.BytesIO()
    sheet.save(buffer, format="PNG")
    return Response(buffer.getvalue(), media_type="image/png")


@router.post("/projects/{project_id}/pages/{page_id}/regions/{region_id}/export-svg")
def export_svg(project_id: str, page_id: str, region_id: str, options: ExportOptions):
    if not potrace_backend.is_available():
        raise HTTPException(503, "potrace is not installed (brew install potrace)")
    page = store.load_page(project_id, page_id)
    region = store.get_region(page, region_id)
    bgr = store.load_page_image(project_id, page_id)
    mask = _region_mask(project_id, page_id, page, region)
    svg = potrace_backend.region_to_svg(bgr, tuple(region["bbox"]), mask, options)
    out_dir = store.exports_dir(project_id, page_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{region_id}.svg").write_bytes(svg)
    return {"export_url": f"/api/projects/{project_id}/pages/{page_id}/exports/{region_id}.svg"}


@router.get("/projects/{project_id}/pages/{page_id}/exports/{region_id}.svg")
def get_export_svg(project_id: str, page_id: str, region_id: str):
    path = store.exports_dir(project_id, page_id) / f"{region_id}.svg"
    if not path.exists():
        raise HTTPException(404, "SVG export not found")
    return FileResponse(path, media_type="image/svg+xml")


def _safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "element"


@router.post("/projects/{project_id}/export-all", response_model=JobStatus)
def export_all(project_id: str, body: BatchExportRequest):
    project = store.load_project(project_id)
    page_ids = list(project["page_ids"])
    out_dir = Path(body.out_dir).expanduser() if body.out_dir else None
    if out_dir is not None and not out_dir.is_absolute():
        raise HTTPException(400, "out_dir must be an absolute path")
    options = ExportOptions(style=body.style, rgb=body.rgb, padding=body.padding)

    def work(job: jobs.Job) -> None:
        job.set_total(len(page_ids))
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
        for page_id in page_ids:
            page = store.load_page(project_id, page_id)
            bgr = store.load_page_image(project_id, page_id)
            for region in page["regions"]:
                if not region["enabled"]:
                    continue
                path = _export_one(project_id, page_id, page, bgr, region, options)
                if out_dir is not None:
                    # Never overwrite anything in the user's chosen folder.
                    target = store.unique_path(
                        out_dir, f"{_safe_name(page['name'])}_{_safe_name(region['label'])}", ".png"
                    )
                    target.write_bytes(path.read_bytes())
            store.save_page(project_id, page)
            job.tick()

    return jobs.submit("export-all", work).to_dict()
