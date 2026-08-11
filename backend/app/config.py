import os
from pathlib import Path

# Repo root is two levels up from this file (backend/app/config.py)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = Path(os.environ.get("IMAGE_PARSER_DATA_DIR", REPO_ROOT / "data"))
PROJECTS_DIR = DATA_DIR / "projects"

SAM_CHECKPOINT = Path(
    os.environ.get("IMAGE_PARSER_SAM_CHECKPOINT", REPO_ROOT / "backend" / "models" / "mobile_sam.pt")
)

HOST = os.environ.get("IMAGE_PARSER_HOST", "127.0.0.1")
PORT = int(os.environ.get("IMAGE_PARSER_PORT", "8765"))

# Root for the folder-picker browser; absolute paths outside it are still allowed
# (trusted single-user local tool), this is just the starting point.
FS_ROOT = Path(os.environ.get("IMAGE_PARSER_FS_ROOT", Path.home()))

THUMB_MAX_SIZE = 256

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
