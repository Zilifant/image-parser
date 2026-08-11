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


def test_review_and_profiles(client):
    project_id, page_id = _create_project_with_page(client)
    regions = client.post(f"/api/projects/{project_id}/pages/{page_id}/detect", json={}).json()

    # Approve a region.
    region_id = regions[0]["id"]
    response = client.patch(
        f"/api/projects/{project_id}/pages/{page_id}/regions/{region_id}",
        json={"status": "approved"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    # Built-in profiles exist; a custom one can be saved and applied.
    profiles = client.get("/api/profiles").json()
    assert any(p["name"] == "dense-collages" and p["builtin"] for p in profiles)
    response = client.put(
        "/api/profiles",
        json={"name": "my-scans", "builtin": False, "detect": {"merge_radius": 9}, "export": {"rgb": "pure_white"}},
    )
    assert response.status_code == 200
    assert any(p["name"] == "my-scans" for p in client.get("/api/profiles").json())

    # Clean full-page export.
    response = client.post(
        f"/api/projects/{project_id}/pages/{page_id}/export-clean-page", json={"rgb": "pure_white"}
    )
    assert response.status_code == 200
    clean = client.get(response.json()["url"])
    assert clean.status_code == 200 and clean.content[:8] == b"\x89PNG\r\n\x1a\n"

    # Contact sheet requires exports, then renders.
    assert client.get(f"/api/projects/{project_id}/pages/{page_id}/contact-sheet.png").status_code == 404
    client.post(f"/api/projects/{project_id}/pages/{page_id}/export", json={})
    sheet = client.get(f"/api/projects/{project_id}/pages/{page_id}/contact-sheet.png")
    assert sheet.status_code == 200 and sheet.content[:8] == b"\x89PNG\r\n\x1a\n"

    # QC results are persisted on regions after export.
    page = client.get(f"/api/projects/{project_id}/pages/{page_id}").json()
    assert all("qc_issues" in region for region in page["regions"])


def test_malformed_ids_cannot_reach_the_filesystem(client, tmp_path):
    """Non-server-generated ids must 404 before any delete/write resolves.

    HTTP clients and browsers normalize '..' out of URLs, so the load-bearing
    guard is store._check_id — exercise it directly for traversal shapes, and
    via the API for ids that survive URL normalization.
    """
    import pytest
    from fastapi import HTTPException

    from app import store

    for bad in ("..", ".", "p_..", "p_xyz", "P_12345678", "pg_1234", ""):
        with pytest.raises(HTTPException):
            store.project_dir(bad)

    project_id, page_id = _create_project_with_page(client)
    assert client.delete("/api/projects/not-a-real-id").status_code == 404
    assert client.delete(f"/api/projects/{project_id}/pages/not-a-real-id").status_code == 404

    # The data dir and the real project are untouched.
    assert (tmp_path / "projects").exists()
    assert client.get(f"/api/projects/{project_id}/pages/{page_id}").status_code == 200


def test_delete_page_removes_it(client):
    project_id, page_id = _create_project_with_page(client)
    assert client.delete(f"/api/projects/{project_id}/pages/{page_id}").status_code == 200
    assert client.get(f"/api/projects/{project_id}/pages/{page_id}").status_code == 404
    assert client.get(f"/api/projects/{project_id}").json()["pages"] == []


def test_batch_export_never_overwrites(client, tmp_path):
    project_id, page_id = _create_project_with_page(client)
    regions = client.post(f"/api/projects/{project_id}/pages/{page_id}/detect", json={}).json()
    out_dir = tmp_path / "batch-out"

    def run_export():
        job_id = client.post(
            f"/api/projects/{project_id}/export-all", json={"out_dir": str(out_dir)}
        ).json()["id"]
        for _ in range(240):
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] != "running":
                return job
            time.sleep(0.25)
        raise AssertionError("export job did not finish")

    assert run_export()["status"] == "done"
    first_run = sorted(p.name for p in out_dir.glob("*.png"))
    assert len(first_run) == len(regions)
    marker = out_dir / first_run[0]
    marker.write_bytes(b"sentinel")  # simulate a pre-existing user file

    assert run_export()["status"] == "done"
    all_files = list(out_dir.glob("*.png"))
    assert len(all_files) == 2 * len(regions), "second run must add files, not replace"
    assert marker.read_bytes() == b"sentinel", "existing files are never overwritten"
    assert any(p.name.endswith("-2.png") for p in all_files)


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
