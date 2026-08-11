from fastapi import APIRouter

from .. import profiles
from ..schemas import Profile

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=list[Profile])
def list_profiles():
    return profiles.load_all()


@router.put("", response_model=Profile)
def upsert_profile(body: Profile):
    return profiles.upsert(body)


@router.delete("/{name}")
def delete_profile(name: str):
    profiles.delete(name)
    return {"ok": True}
