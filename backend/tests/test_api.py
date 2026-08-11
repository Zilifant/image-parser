import time
from pathlib import Path

import pytest

SAMPLE = Path(__file__).resolve().parent.parent.parent / "assets" / "raw-images" / "eyes-11.png"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def _create_project_with_page(client) -> tuple[str, str]:
    project = client.post("/api/projects", json={"name": "test"}).json()
    with open(SAMPLE, "rb") as f:
        response = client.post(
            f"/api/projects/{project['id']}/pages",
            files=[("files", ("eyes-11.png", f, "image/png"))],
        )
    assert response.status_code == 200, response.text
    return project["id"], response.json()[0]["id"]


def test_full_flow(client):
    project_id, page_id = _create_project_with_page(client)

    response = client.post(f"/api/projects/{project_id}/pages/{page_id}/detect", json={})
    assert response.status_code == 200, response.text
    regions = response.json()
    assert len(regions) >= 25

    # Edit a region's polygon.
    region = regions[0]
    new_polygon = [[10, 10], [100, 10], [100, 100], [10, 100]]
    response = client.patch(
        f"/api/projects/{project_id}/pages/{page_id}/regions/{region['id']}",
        json={"polygon": new_polygon, "label": "edited"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["label"] == "edited"
    assert response.json()["bbox"] == [10, 10, 91, 91]

    # Manual region + merge.
    response = client.post(
        f"/api/projects/{project_id}/pages/{page_id}/regions",
        json={"polygon": [[200, 200], [300, 200], [300, 300], [200, 300]]},
    )
    assert response.status_code == 200, response.text
    manual_id = response.json()["id"]
    response = client.post(
        f"/api/projects/{project_id}/pages/{page_id}/regions/merge",
        json={"region_ids": [region["id"], manual_id]},
    )
    assert response.status_code == 200, response.text

    # Export the page.
    response = client.post(f"/api/projects/{project_id}/pages/{page_id}/export", json={})
    assert response.status_code == 200, response.text
    exports = response.json()["exports"]
    assert len(exports) >= 25

    export = client.get(exports[0]["url"])
    assert export.status_code == 200
    assert export.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_detect_all_job(client, tmp_path):
    project_id, _ = _create_project_with_page(client)
    with open(SAMPLE, "rb") as f:
        client.post(
            f"/api/projects/{project_id}/pages",
            files=[("files", ("eyes-11-copy.png", f, "image/png"))],
        )

    response = client.post(f"/api/projects/{project_id}/detect-all", json={})
    assert response.status_code == 200, response.text
    job_id = response.json()["id"]

    for _ in range(120):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            break
        time.sleep(0.5)
    assert job["status"] == "done", job
    assert job["done"] == 2

    project = client.get(f"/api/projects/{project_id}").json()
    assert all(page["region_count"] >= 25 for page in project["pages"])
