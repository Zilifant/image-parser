from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import config
from ..schemas import FsEntry

router = APIRouter(prefix="/fs", tags=["fs"])


@router.get("/list")
def list_dir(path: str | None = None) -> dict:
    directory = Path(path).expanduser() if path else config.FS_ROOT
    if not directory.is_absolute():
        raise HTTPException(400, "path must be absolute")
    if not directory.is_dir():
        raise HTTPException(404, f"not a directory: {directory}")

    entries: list[FsEntry] = []
    try:
        children = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        raise HTTPException(403, f"permission denied: {directory}")
    for child in children:
        if child.name.startswith("."):
            continue
        is_dir = child.is_dir()
        is_image = child.suffix.lower() in config.IMAGE_EXTENSIONS
        if not is_dir and not is_image:
            continue
        entries.append(FsEntry(name=child.name, path=str(child), is_dir=is_dir, is_image=is_image))

    parent = str(directory.parent) if directory != directory.parent else None
    return {"path": str(directory), "parent": parent, "entries": entries}
