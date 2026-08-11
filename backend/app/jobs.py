"""In-process background jobs for batch detect/export.

CV work is CPU-bound; a single worker thread keeps the machine responsive and
jobs simple. Jobs live in memory and die with the process — acceptable for a
local single-user tool.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable

from fastapi import HTTPException

from .store import new_id

_executor = ThreadPoolExecutor(max_workers=1)
_jobs: dict[str, "Job"] = {}
_lock = Lock()


@dataclass
class Job:
    id: str
    kind: str
    status: str = "running"  # running | done | error
    done: int = 0
    total: int = 0
    error: str | None = None
    _lock: Lock = field(default_factory=Lock, repr=False)

    def set_total(self, total: int) -> None:
        with self._lock:
            self.total = total

    def tick(self) -> None:
        with self._lock:
            self.done += 1

    def to_dict(self) -> dict:
        with self._lock:
            return {
                "id": self.id,
                "kind": self.kind,
                "status": self.status,
                "done": self.done,
                "total": self.total,
                "error": self.error,
            }


def submit(kind: str, work: Callable[[Job], None]) -> Job:
    job = Job(id=new_id("j"), kind=kind)
    with _lock:
        _jobs[job.id] = job

    def run() -> None:
        try:
            work(job)
            job.status = "done"
        except Exception as exc:  # surfaced via the status endpoint
            job.status = "error"
            job.error = str(exc)

    _executor.submit(run)
    return job


def get(job_id: str) -> Job:
    with _lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"job {job_id} not found")
    return job
