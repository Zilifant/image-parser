from fastapi import APIRouter

from ..cv import potrace_backend, sam_backend
from ..schemas import ToolsStatus

router = APIRouter(tags=["tools"])


@router.get("/tools/status", response_model=ToolsStatus)
def tools_status():
    return {"sam": sam_backend.is_available(), "potrace": potrace_backend.is_available()}
