"""Filesystem-backed project store.

Layout under DATA_DIR:
    projects/<project_id>/project.json
    projects/<project_id>/pages/<page_id>/original.png
    projects/<project_id>/pages/<page_id>/thumb.jpg
    projects/<project_id>/pages/<page_id>/page.json   <- holds the region list
    projects/<project_id>/pages/<page_id>/masks/<region_id>.png
    projects/<project_id>/pages/<page_id>/exports/<region_id>.png

page.json is the source of truth for regions; JSON writes are atomic.
"""

import json
import os
import re
import secrets
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from fastapi import HTTPException

from . import config

_ID_RE = re.compile(r"[a-z]+_[0-9a-f]{8}")


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


def _check_id(entity_id: str) -> str:
    """IDs are used as path segments; only server-generated shapes are valid.

    This keeps a malformed id (e.g. '..') from ever resolving a delete or
    write to anything but a real entity directory.
    """
    if not _ID_RE.fullmatch(entity_id):
        raise HTTPException(404, f"invalid id: {entity_id!r}")
    return entity_id


def _remove_dir(path: Path) -> None:
    """Move a directory to the OS Trash (recoverable); fall back to permanent
    removal only if the platform/volume has no trash available."""
    try:
        from send2trash import send2trash

        send2trash(str(path))
    except Exception:
        shutil.rmtree(path)


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    """First free path like stem.png, stem-2.png, ... — never overwrites."""
    candidate = directory / f"{stem}{suffix}"
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate


def _write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _read_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------- projects


def project_dir(project_id: str) -> Path:
    return config.PROJECTS_DIR / _check_id(project_id)


def create_project(name: str) -> dict:
    project = {
        "id": new_id("p"),
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "page_ids": [],
    }
    _write_json_atomic(project_dir(project["id"]) / "project.json", project)
    return project


def load_project(project_id: str) -> dict:
    path = project_dir(project_id) / "project.json"
    if not path.exists():
        raise HTTPException(404, f"project {project_id} not found")
    return _read_json(path)


def save_project(project: dict) -> None:
    _write_json_atomic(project_dir(project["id"]) / "project.json", project)


def list_projects() -> list[dict]:
    if not config.PROJECTS_DIR.exists():
        return []
    projects = []
    for entry in sorted(config.PROJECTS_DIR.iterdir()):
        path = entry / "project.json"
        if path.exists():
            projects.append(_read_json(path))
    return projects


def delete_project(project_id: str) -> None:
    directory = project_dir(project_id)
    if not directory.exists():
        raise HTTPException(404, f"project {project_id} not found")
    _remove_dir(directory)


# ---------------------------------------------------------------- pages


def page_dir(project_id: str, page_id: str) -> Path:
    return project_dir(project_id) / "pages" / _check_id(page_id)


def create_page(project_id: str, name: str, bgr: np.ndarray, source_path: str | None) -> dict:
    project = load_project(project_id)
    page_id = new_id("pg")
    directory = page_dir(project_id, page_id)
    directory.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(directory / "original.png"), bgr)

    h, w = bgr.shape[:2]
    scale = config.THUMB_MAX_SIZE / max(w, h)
    if scale < 1:
        thumb = cv2.resize(bgr, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    else:
        thumb = bgr
    cv2.imwrite(str(directory / "thumb.jpg"), thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])

    page = {
        "id": page_id,
        "name": name,
        "width": w,
        "height": h,
        "source_path": source_path,
        "detect_params": {},
        "regions": [],
    }
    save_page(project_id, page)

    project["page_ids"].append(page_id)
    save_project(project)
    return page


def load_page(project_id: str, page_id: str) -> dict:
    path = page_dir(project_id, page_id) / "page.json"
    if not path.exists():
        raise HTTPException(404, f"page {page_id} not found")
    return _read_json(path)


def save_page(project_id: str, page: dict) -> None:
    _write_json_atomic(page_dir(project_id, page["id"]) / "page.json", page)


def delete_page(project_id: str, page_id: str) -> None:
    project = load_project(project_id)
    directory = page_dir(project_id, page_id)
    if not directory.exists():
        raise HTTPException(404, f"page {page_id} not found")
    _remove_dir(directory)
    project["page_ids"] = [pid for pid in project["page_ids"] if pid != page_id]
    save_project(project)


def load_page_image(project_id: str, page_id: str) -> np.ndarray:
    path = page_dir(project_id, page_id) / "original.png"
    if not path.exists():
        raise HTTPException(404, f"image for page {page_id} not found")
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise HTTPException(500, f"could not decode image for page {page_id}")
    return bgr


def page_summary(project_id: str, page: dict) -> dict:
    exports = page_dir(project_id, page["id"]) / "exports"
    export_count = len(list(exports.glob("*.png"))) if exports.exists() else 0
    return {
        "id": page["id"],
        "name": page["name"],
        "width": page["width"],
        "height": page["height"],
        "region_count": len(page["regions"]),
        "export_count": export_count,
    }


# ---------------------------------------------------------------- regions


def get_region(page: dict, region_id: str) -> dict:
    for region in page["regions"]:
        if region["id"] == region_id:
            return region
    raise HTTPException(404, f"region {region_id} not found")


def mask_path(project_id: str, page_id: str, region_id: str) -> Path:
    return page_dir(project_id, page_id) / "masks" / f"{_check_id(region_id)}.png"


def save_mask(project_id: str, page_id: str, region_id: str, mask: np.ndarray) -> None:
    path = mask_path(project_id, page_id, region_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), mask)


def load_mask(project_id: str, page_id: str, region_id: str) -> np.ndarray | None:
    path = mask_path(project_id, page_id, region_id)
    if not path.exists():
        return None
    return cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)


def delete_region_files(project_id: str, page_id: str, region_id: str) -> None:
    for path in (
        mask_path(project_id, page_id, region_id),
        exports_dir(project_id, page_id) / f"{region_id}.png",
    ):
        if path.exists():
            path.unlink()


def exports_dir(project_id: str, page_id: str) -> Path:
    return page_dir(project_id, page_id) / "exports"
