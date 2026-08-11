from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .. import config, store
from ..cv.pipeline import detect_regions
from ..schemas import DetectRequest, FromPathsRequest, Page, PageSummary, Region

router = APIRouter(prefix="/projects/{project_id}/pages", tags=["pages"])


def _decode_upload(data: bytes) -> np.ndarray:
    array = np.frombuffer(data, np.uint8)
    bgr = cv2.imdecode(array, cv2.IMREAD_COLOR)  # flattens alpha, drops ICC
    if bgr is None:
        raise HTTPException(400, "could not decode image")
    return bgr


def _read_local_image(path: Path) -> np.ndarray:
    if not path.is_absolute():
        raise HTTPException(400, f"path must be absolute: {path}")
    if not path.exists():
        raise HTTPException(404, f"file not found: {path}")
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise HTTPException(400, f"could not decode image: {path}")
    return bgr


def _page_response(project_id: str, page: dict) -> dict:
    return {
        **store.page_summary(project_id, page),
        "regions": page["regions"],
        "detect_params": page.get("detect_params") or {},
        "source_path": page.get("source_path"),
    }


@router.post("", response_model=list[PageSummary])
async def upload_pages(project_id: str, files: list[UploadFile]):
    store.load_project(project_id)
    pages = []
    for file in files:
        bgr = _decode_upload(await file.read())
        name = Path(file.filename or "untitled").stem
        page = store.create_page(project_id, name, bgr, source_path=None)
        pages.append(store.page_summary(project_id, page))
    return pages


@router.post("/from-paths", response_model=list[PageSummary])
def pages_from_paths(project_id: str, body: FromPathsRequest):
    store.load_project(project_id)
    paths: list[Path] = []
    if body.dir:
        directory = Path(body.dir)
        if not directory.is_dir():
            raise HTTPException(400, f"not a directory: {directory}")
        paths = sorted(
            p for p in directory.iterdir()
            if p.suffix.lower() in config.IMAGE_EXTENSIONS and p.is_file()
        )
        if not paths:
            raise HTTPException(400, f"no images found in {directory}")
    if body.paths:
        paths += [Path(p) for p in body.paths]
    if not paths:
        raise HTTPException(400, "provide 'paths' or 'dir'")

    pages = []
    for path in paths:
        bgr = _read_local_image(path)
        page = store.create_page(project_id, path.stem, bgr, source_path=str(path))
        pages.append(store.page_summary(project_id, page))
    return pages


@router.get("/{page_id}", response_model=Page)
def get_page(project_id: str, page_id: str):
    return _page_response(project_id, store.load_page(project_id, page_id))


@router.delete("/{page_id}")
def delete_page(project_id: str, page_id: str):
    store.delete_page(project_id, page_id)
    return {"ok": True}


@router.get("/{page_id}/image")
def page_image(project_id: str, page_id: str):
    path = store.page_dir(project_id, page_id) / "original.png"
    if not path.exists():
        raise HTTPException(404, "image not found")
    return FileResponse(path, media_type="image/png")


@router.get("/{page_id}/thumb")
def page_thumb(project_id: str, page_id: str):
    path = store.page_dir(project_id, page_id) / "thumb.jpg"
    if not path.exists():
        raise HTTPException(404, "thumbnail not found")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/{page_id}/detect", response_model=list[Region])
def detect(project_id: str, page_id: str, body: DetectRequest):
    from ..schemas import DetectParams

    page = store.load_page(project_id, page_id)
    bgr = store.load_page_image(project_id, page_id)
    params = body.params or DetectParams(**page.get("detect_params") or {})
    regions = detect_regions(bgr, params)

    # Replace prior auto regions; keep manual/sam/merge ones (and their files).
    removed = [r for r in page["regions"] if r["source"] == "auto"]
    for region in removed:
        store.delete_region_files(project_id, page_id, region["id"])
    kept = [r for r in page["regions"] if r["source"] != "auto"]
    page["regions"] = regions + kept
    page["detect_params"] = params.model_dump()
    store.save_page(project_id, page)
    return page["regions"]
