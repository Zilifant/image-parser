import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import store
from ..cv.matte import rasterize_polygon
from ..cv.pipeline import contour_to_polygon, detect_regions
from ..schemas import (
    BrushRequest,
    MergeRequest,
    PolygonCreate,
    Region,
    RegionPatch,
    SetEnabledRequest,
    SplitRequest,
)

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
        "status": "provisional",
        "qc_issues": [],
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
    if body.status is not None:
        region["status"] = body.status
        if body.status == "approved":
            region["qc_issues"] = []
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


@router.post("/set-enabled", response_model=list[Region])
def set_enabled(project_id: str, page_id: str, body: SetEnabledRequest):
    """Bulk-toggle export inclusion; region_ids omitted means every region."""
    page = store.load_page(project_id, page_id)
    targets = set(body.region_ids) if body.region_ids is not None else None
    for region in page["regions"]:
        if targets is None or region["id"] in targets:
            region["enabled"] = body.enabled
    store.save_page(project_id, page)
    return page["regions"]


def _rasterize_stroke(points: list, radius: float, shape: tuple[int, int]) -> np.ndarray:
    stroke = np.zeros(shape, np.uint8)
    r = max(1, round(radius))
    pts = [(round(x), round(y)) for x, y in points]
    for point in pts:
        cv2.circle(stroke, point, r, 255, -1)
    for a, b in zip(pts, pts[1:]):
        cv2.line(stroke, a, b, 255, thickness=2 * r)
    return stroke


@router.post("/brush", response_model=Region)
def brush(project_id: str, page_id: str, body: BrushRequest):
    """Paint a circular-brush stroke to create, expand, or subtract a region.

    The resulting pixel mask becomes authoritative for the region (stored as
    a mask PNG); the polygon is kept as the editable/display outline.
    """
    page = store.load_page(project_id, page_id)
    shape = (page["height"], page["width"])
    stroke = _rasterize_stroke(body.points, body.radius, shape)

    if body.region_id is None:
        if body.mode == "subtract":
            raise HTTPException(400, "select a region to subtract from")
        region = {
            "id": store.new_id("r"),
            "bbox": [0, 0, 1, 1],  # set below
            "polygon": [],
            "source": "manual",
            "confidence": 1.0,
            "enabled": True,
            "label": _next_label(page, "manual"),
            "has_mask": True,
            "status": "provisional",
            "qc_issues": [],
        }
        page["regions"].append(region)
        mask = stroke
    else:
        region = store.get_region(page, body.region_id)
        base = store.load_mask(project_id, page_id, region["id"]) if region.get("has_mask") else None
        if base is None:
            base = rasterize_polygon(region["polygon"], shape)
        if body.mode == "add":
            mask = cv2.bitwise_or(base, stroke)
        else:
            mask = cv2.bitwise_and(base, cv2.bitwise_not(stroke))
        if not mask.any():
            raise HTTPException(409, "that stroke would erase the entire region — delete it instead")
        region["has_mask"] = True

    ys, xs = np.nonzero(mask)
    region["bbox"] = [int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)]
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    region["polygon"] = contour_to_polygon(max(contours, key=cv2.contourArea))
    store.save_mask(project_id, page_id, region["id"], mask)
    store.save_page(project_id, page)
    return region


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
        "status": "provisional",
        "qc_issues": [],
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
