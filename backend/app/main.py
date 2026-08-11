from fastapi import APIRouter, FastAPI

from .routers import export, fs, jobs, pages, projects, regions, sam

app = FastAPI(title="image-parser")

api = APIRouter(prefix="/api")
api.include_router(projects.router)
api.include_router(pages.router)
api.include_router(regions.router)
api.include_router(export.router)
api.include_router(jobs.router)
api.include_router(fs.router)
api.include_router(sam.router)


@api.get("/health")
def health():
    return {"ok": True}


app.include_router(api)
