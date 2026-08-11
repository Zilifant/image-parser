import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import store
from ..cv.matte import rasterize_polygon
from ..cv.pipeline import contour_to_polygon, detect_regions
from ..schemas import MergeRequest, PolygonCreate, Region, RegionPatch, SplitRequest

router = APIRouter(prefix="/projects/{project_id}/pages/{page_id}/regions", tags=["regions"])


def _bbox_of_polygon(polygon: list) -> list[int]:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    x0, y0 = int(min(xs)), int(min(ys))
    return [x0, y0, int(max(xs)) - x0 + 1, int(max(ys)) - y0 + 1]


def _next_label(page: dict, prefix: str) -> str:
    existing = {r["label"] for r in page["regions"]}
    i = len(page["regions"]) + 1
    while f"{prefix}-{i:02d}" in existing:
        i += 1
    return f"{prefix}-{i:02d}"


@router.post("", response_model=Region)
def create_region(project_id: str, page_id: str, body: PolygonCreate):
    page = store.load_page(project_id, page_id)
    polygon = [[float(x), float(y)] for x, y in body.polygon]
    region = {
        "id": store.new_id("r"),
        "bbox": _bbox_of_polygon(polygon),
        "polygon": polygon,
        "source": "manual",
        "confidence": 1.0,
        "enabled": True,
        "label": _next_label(page, "manual"),
        "has_mask": False,
    }
    page["regions"].append(region)
    store.save_page(project_id, page)
    return region


@router.patch("/{region_id}", response_model=Region)
def patch_region(project_id: str, page_id: str, region_id: str, body: RegionPatch):
    page = store.load_page(project_id, page_id)
    region = store.get_region(page, region_id)
    if body.polygon is not None:
        if len(body.polygon) < 3:
            raise HTTPException(400, "polygon needs at least 3 points")
        region["polygon"] = [[float(x), float(y)] for x, y in body.polygon]
        region["bbox"] = _bbox_of_polygon(region["polygon"])
        # An edited outline supersedes any stored pixel mask.
        if region.get("has_mask"):
            path = store.mask_path(project_id, page_id, region_id)
            if path.exists():
                path.unlink()
            region["has_mask"] = False
    if body.enabled is not None:
        region["enabled"] = body.enabled
    if body.label is not None:
        region["label"] = body.label
    store.save_page(project_id, page)
    return region


@router.delete("/{region_id}")
def delete_region(project_id: str, page_id: str, region_id: str):
    page = store.load_page(project_id, page_id)
    region = store.get_region(page, region_id)
    page["regions"] = [r for r in page["regions"] if r["id"] != region_id]
    store.delete_region_files(project_id, page_id, region_id)
    store.save_page(project_id, page)
    return {"ok": True}


@router.get("/{region_id}/mask")
def region_mask(project_id: str, page_id: str, region_id: str):
    path = store.mask_path(project_id, page_id, region_id)
    if not path.exists():
        raise HTTPException(404, "no stored mask for this region")
    return FileResponse(path, media_type="image/png")


@router.post("/merge", response_model=Region)
def merge_regions(project_id: str, page_id: str, body: MergeRequest):
    page = store.load_page(project_id, page_id)
    to_merge = [store.get_region(page, rid) for rid in body.region_ids]

    shape = (page["height"], page["width"])
    combined = np.zeros(shape, np.uint8)
    for region in to_merge:
        mask = store.load_mask(project_id, page_id, region["id"]) if region.get("has_mask") else None
        if mask is None:
            mask = rasterize_polygon(region["polygon"], shape)
        combined = cv2.bitwise_or(combined, mask)
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise HTTPException(400, "merge produced an empty mask")
    contour = max(contours, key=cv2.contourArea)

    merged = {
        "id": store.new_id("r"),
        "bbox": list(cv2.boundingRect(contour)),
        "polygon": contour_to_polygon(contour),
        "source": "merge",
        "confidence": 1.0,
        "enabled": True,
        "label": _next_label(page, "merged"),
        "has_mask": len(contours) > 1,  # disjoint parts: polygon alone is lossy
    }
    if merged["has_mask"]:
        store.save_mask(project_id, page_id, merged["id"], combined)

    merged_ids = set(body.region_ids)
    page["regions"] = [r for r in page["regions"] if r["id"] not in merged_ids]
    for rid in merged_ids:
        store.delete_region_files(project_id, page_id, rid)
    page["regions"].append(merged)
    store.save_page(project_id, page)
    return merged


@router.post("/{region_id}/split", response_model=list[Region])
def split_region(project_id: str, page_id: str, region_id: str, body: SplitRequest):
    from ..schemas import DetectParams

    page = store.load_page(project_id, page_id)
    region = store.get_region(page, region_id)
    bgr = store.load_page_image(project_id, page_id)
    shape = (page["height"], page["width"])

    roi = store.load_mask(project_id, page_id, region_id) if region.get("has_mask") else None
    if roi is None:
        roi = rasterize_polygon(region["polygon"], shape)

    from ..cv.pipeline import effective_merge_radius

    base = DetectParams(**page.get("detect_params") or {})
    if body.params is not None:
        params = body.params
    else:
        # Halve the bridging so touching sub-elements come apart.
        radius = effective_merge_radius(base, page["width"])
        params = base.model_copy(update={"merge_radius": max(2, radius // 2)})
    pieces = detect_regions(bgr, params, roi_mask=roi)
    if len(pieces) <= 1:
        raise HTTPException(409, "split found no sub-elements; try lowering merge radius or use manual outlines")

    page["regions"] = [r for r in page["regions"] if r["id"] != region_id]
    store.delete_region_files(project_id, page_id, region_id)
    page["regions"].extend(pieces)
    store.save_page(project_id, page)
    return pieces
