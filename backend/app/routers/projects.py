from fastapi import APIRouter

from .. import jobs, store
from ..cv.pipeline import detect_regions
from ..schemas import DetectRequest, JobStatus, Project, ProjectCreate

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_response(project: dict) -> dict:
    pages = []
    for page_id in project["page_ids"]:
        try:
            page = store.load_page(project["id"], page_id)
        except Exception:
            continue
        pages.append(store.page_summary(project["id"], page))
    return {
        "id": project["id"],
        "name": project["name"],
        "created_at": project["created_at"],
        "pages": pages,
    }


@router.get("", response_model=list[Project])
def list_projects():
    return [_project_response(p) for p in store.list_projects()]


@router.post("", response_model=Project)
def create_project(body: ProjectCreate):
    return _project_response(store.create_project(body.name))


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str):
    return _project_response(store.load_project(project_id))


@router.delete("/{project_id}")
def delete_project(project_id: str):
    store.delete_project(project_id)
    return {"ok": True}


@router.post("/{project_id}/detect-all", response_model=JobStatus)
def detect_all(project_id: str, body: DetectRequest):
    project = store.load_project(project_id)
    params = body.params or None
    page_ids = list(project["page_ids"])

    def work(job: jobs.Job) -> None:
        from ..schemas import DetectParams

        job.set_total(len(page_ids))
        for page_id in page_ids:
            page = store.load_page(project_id, page_id)
            bgr = store.load_page_image(project_id, page_id)
            effective = params or DetectParams(**page.get("detect_params") or {})
            regions = detect_regions(bgr, effective)
            kept = [r for r in page["regions"] if r["source"] != "auto"]
            page["regions"] = regions + kept
            page["detect_params"] = effective.model_dump()
            store.save_page(project_id, page)
            job.tick()

    return jobs.submit("detect-all", work).to_dict()
