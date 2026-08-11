import re
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import jobs, store
from ..cv.matte import export_region, rasterize_polygon
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
    mask = _region_mask(project_id, page_id, page, region)
    rgba = export_region(bgr, tuple(region["bbox"]), mask, options)
    out_dir = store.exports_dir(project_id, page_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{region['id']}.png"
    cv2.imwrite(str(path), rgba)
    return path


def _export_url(project_id: str, page_id: str, region_id: str) -> str:
    return f"/api/projects/{project_id}/pages/{page_id}/exports/{region_id}.png"


@router.post("/projects/{project_id}/pages/{page_id}/regions/{region_id}/export")
def export_single(project_id: str, page_id: str, region_id: str, options: ExportOptions):
    page = store.load_page(project_id, page_id)
    region = store.get_region(page, region_id)
    bgr = store.load_page_image(project_id, page_id)
    _export_one(project_id, page_id, page, bgr, region, options)
    return {"export_url": _export_url(project_id, page_id, region_id)}


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
        exports.append({"region_id": region["id"], "url": _export_url(project_id, page_id, region["id"])})
    return {"exports": exports}


@router.get("/projects/{project_id}/pages/{page_id}/exports/{region_id}.png")
def get_export(project_id: str, page_id: str, region_id: str):
    path = store.exports_dir(project_id, page_id) / f"{region_id}.png"
    if not path.exists():
        raise HTTPException(404, "export not found")
    return FileResponse(path, media_type="image/png")


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
                    target = out_dir / f"{_safe_name(page['name'])}_{_safe_name(region['label'])}.png"
                    target.write_bytes(path.read_bytes())
            job.tick()

    return jobs.submit("export-all", work).to_dict()
