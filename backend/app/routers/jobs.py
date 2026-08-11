from fastapi import APIRouter

from .. import jobs
from ..schemas import JobStatus

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatus)
def get_job(job_id: str):
    return jobs.get(job_id).to_dict()
