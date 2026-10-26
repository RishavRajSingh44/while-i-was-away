import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from away.main import create_app
from away.db import encode

HEADERS = {"X-Away-Client": "1", "Origin": "http://127.0.0.1:8765"}


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "away.sqlite", run_worker=False)
    with TestClient(app, base_url="http://127.0.0.1:8765", headers=HEADERS) as value:
        yield value


def demo(client):
    response = client.post("/api/demo", json={})
    assert response.status_code == 200, response.text
    return response.json()


def test_demo_history_checkpoint_export_and_deletion(client):
    repo = demo(client)
    assert demo(client)["id"] == repo["id"]
    overview = client.get(f"/api/repos/{repo['id']}/overview").json()
    assert repo["demo"] and repo["acknowledged_snapshot_id"] is None
    assert {pr["state"] for pr in overview["snapshot"]["github"]["prs"]} == {"open", "draft", "merged", "closed"}
    briefing = overview["briefing"]
    assert len(briefing["sections"]) == 5
    assert "Synthetic" in briefing["model"]
    assert client.post(f"/api/repos/{repo['id']}/collect", json={"window": "24h"}).status_code == 200
    assert client.get("/api/repos").json()[0]["acknowledged_snapshot_id"] is None
    acknowledged = client.post(f"/api/briefings/{briefing['id']}/acknowledge", json={}).json()
    assert acknowledged["acknowledged_snapshot_id"] == briefing["snapshot_id"]
    handoff = client.get(f"/api/briefings/{briefing['id']}/export")
    for part in ("Repository:", "Branch:", "Snapshot:", "Relevant files", "review feedback", "failed approaches", "Tests and freshness", "demo-session"):
        assert part in handoff.text
    assert "attachment" in handoff.headers["content-disposition"]
    edited = client.put(f"/api/briefings/{briefing['id']}/handoff", json={"text": "Continue safely. password=super-secret-value"}).json()
    assert "super-secret-value" not in edited["text"]
    assert "[REDACTED]" in client.get(f"/api/briefings/{briefing['id']}/export").text
    assert client.request("DELETE", f"/api/repos/{repo['id']}", json={}).status_code == 200
    assert client.get("/api/repos").json() == []
    assert client.get(f"/api/briefings/{briefing['id']}").status_code == 404


@pytest.mark.parametrize("headers", [
    {"host": "attacker.example:8765"}, {"host": "127.0.0.1.attacker.example:8765"},
    {"host": "localhost:9999"}, {"origin": "https://evil.example"}, {"origin": "null"},
    {"sec-fetch-site": "cross-site"}, {"x-away-client": ""},
])
def test_local_endpoint_boundary(client, headers):
    assert client.post("/api/demo", json={}, headers=headers).status_code == 403
    assert client.get("/api/repos").json() == []


def test_form_rejected_and_csp_present(client):
    assert client.post("/api/demo", data={"anything": "1"}).status_code == 403
    response = client.get("/api/repos")
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "access-control-allow-origin" not in response.headers


def test_session_preview_is_nonpersistent_and_association_is_explicit(client, tmp_path):
    repo = demo(client)
    path = f"/api/repos/{repo['id']}/sessions"
    body = {"text": json.dumps({"messages": [{"role": "user", "text": "Fix it; token=not-a-secret-format"}]}), "format": "manual"}
    preview = client.post(path + "/preview", json=body)
    assert preview.status_code == 200
    assert preview.json()["candidates"][0]["match"] == "unknown"
    assert len(client.get(f"/api/repos/{repo['id']}/overview").json()["sessions"]) == 1
    assert client.post(path + "/import", json=body).status_code == 409
    imported = client.post(path + "/import", json=body | {"confirm_mismatch": True})
    assert imported.status_code == 200
    assert len(client.get(f"/api/repos/{repo['id']}/overview").json()["sessions"]) == 2
    assert client.post(path + "/preview", json=body | {"path": str(tmp_path)}).status_code == 400


def test_cancel_is_terminal_and_duplicate_generation_reuses_active_job(client):
    repo = demo(client)
    url = f"/api/repos/{repo['id']}/briefings"
    job = client.post(url, json={}).json()
    assert client.post(url, json={}).json()["id"] == job["id"]
    result = client.post(f"/api/jobs/{job['id']}/cancel", json={}).json()
    assert result["status"] == "cancelled"
    assert client.post(url, json={}).json()["id"] != job["id"]
    assert client.post(url, json={"window": "custom", "since": "2999-01-01"}).status_code == 400


def test_delete_all_requires_literal_confirmation(client):
    demo(client)
    assert client.request("DELETE", "/api/data", json={"confirm": "yes"}).status_code == 422
    assert client.request("DELETE", "/api/data", json={"confirm": "DELETE"}).status_code == 200
    assert client.get("/api/repos").json() == []


def test_no_source_files_removed_with_repository_records(client, tmp_path):
    demo(client)
    marker = tmp_path / "source.txt"
    marker.write_text("Keep me")
    assert client.request("DELETE", "/api/data", json={"confirm": "DELETE"}).status_code == 200
    assert Path(marker).read_text() == "Keep me"


def test_local_collection_preserves_last_github_sync_status(client, tmp_path):
    subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    repo = client.post("/api/repos", json={"path": str(tmp_path)}).json()
    github = {"prs": [], "synced_at": "2026-10-24T00:00:00Z", "offline": False, "error": None, "user": "demo", "evidence": [], "warnings": []}
    client.app.state.db.execute("INSERT INTO github_cache(repo_id,data) VALUES(?,?)", (repo["id"], encode(github)))
    result = client.post(f"/api/repos/{repo['id']}/collect", json={"window": "24h"}).json()
    assert result["github"]["offline"] is False
    assert result["github"]["synced_at"] == github["synced_at"]
    assert any("local cache" in warning for warning in result["warnings"])
