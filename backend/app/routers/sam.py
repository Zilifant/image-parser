import cv2
import numpy as np
from fastapi import APIRouter, HTTPException

from .. import store
from ..cv import sam_backend
from ..cv.pipeline import contour_to_polygon
from ..schemas import Region, SamPredictRequest

router = APIRouter(tags=["sam"])


@router.get("/sam/status")
def sam_status():
    available = sam_backend.is_available()
    return {"available": available, "model": "mobile_sam" if available else None}


@router.post("/projects/{project_id}/pages/{page_id}/sam/predict", response_model=Region)
def sam_predict(project_id: str, page_id: str, body: SamPredictRequest):
    if not sam_backend.is_available():
        raise HTTPException(503, "SAM is not available: install the 'sam' extra and download the checkpoint")
    if not body.points and not body.box:
        raise HTTPException(400, "provide 'points' and/or 'box'")

    page = store.load_page(project_id, page_id)
    bgr = store.load_page_image(project_id, page_id)

    points = [(p.x, p.y, p.label) for p in body.points] if body.points else None
    mask = sam_backend.predict_mask(page_id, bgr, points, body.box)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise HTTPException(422, "SAM returned an empty mask")
    contour = max(contours, key=cv2.contourArea)

    region = {
        "id": store.new_id("r"),
        "bbox": list(cv2.boundingRect(contour)),
        "polygon": contour_to_polygon(contour),
        "source": "sam",
        "confidence": 1.0,
        "enabled": True,
        "label": f"sam-{sum(1 for r in page['regions'] if r['source'] == 'sam') + 1:02d}",
        "has_mask": True,
    }
    store.save_mask(project_id, page_id, region["id"], mask)
    page["regions"].append(region)
    store.save_page(project_id, page)
    return region
