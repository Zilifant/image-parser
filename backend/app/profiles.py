"""Named processing profiles: reusable detect/export parameter presets.

Stored in DATA_DIR/profiles.json. Built-in profiles are seeded on first read
and can be tweaked but not deleted.
"""

import json
from pathlib import Path

from fastapi import HTTPException

from . import config
from .schemas import Profile

BUILTINS: list[dict] = [
    {
        "name": "clean-photocopies",
        "builtin": True,
        "detect": {"mode": "otsu", "merge_radius": 0, "min_area_frac": 0.0002},
        "export": {"style": "binary", "rgb": "pure_white", "padding": 4},
    },
    {
        "name": "yellowed-magazines",
        "builtin": True,
        "detect": {"mode": "adaptive", "block_size": 51, "c": 10, "merge_radius": 0},
        "export": {"style": "ink", "rgb": "pure_white", "padding": 4},
    },
    {
        "name": "low-contrast-scans",
        "builtin": True,
        "detect": {"mode": "adaptive", "block_size": 75, "c": 6, "merge_radius": 0},
        "export": {"style": "ink", "rgb": "pure_white", "padding": 4},
    },
    {
        "name": "dense-collages",
        "builtin": True,
        "detect": {"mode": "adaptive", "block_size": 51, "c": 12, "merge_radius": 4, "min_area_frac": 0.0001},
        "export": {"style": "ink", "rgb": "pure_white", "padding": 4},
    },
]


def _path() -> Path:
    return config.DATA_DIR / "profiles.json"


def load_all() -> list[Profile]:
    path = _path()
    stored: list[dict] = []
    if path.exists():
        with open(path) as f:
            stored = json.load(f)
    by_name = {p["name"]: p for p in stored}
    merged = [by_name.pop(b["name"], b) | {"builtin": True} for b in BUILTINS]
    merged += list(by_name.values())
    return [Profile(**p) for p in merged]


def _save_all(profiles: list[Profile]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump([p.model_dump() for p in profiles], f, indent=1)


def get(name: str) -> Profile:
    for profile in load_all():
        if profile.name == name:
            return profile
    raise HTTPException(404, f"profile {name!r} not found")


def upsert(profile: Profile) -> Profile:
    profiles = load_all()
    for existing in profiles:
        if existing.name == profile.name:
            profile.builtin = existing.builtin  # can't un-builtin a builtin
    profiles = [p for p in profiles if p.name != profile.name] + [profile]
    _save_all(profiles)
    return profile


def delete(name: str) -> None:
    profiles = load_all()
    target = next((p for p in profiles if p.name == name), None)
    if target is None:
        raise HTTPException(404, f"profile {name!r} not found")
    if target.builtin:
        raise HTTPException(400, "built-in profiles cannot be deleted")
    _save_all([p for p in profiles if p.name != name])
