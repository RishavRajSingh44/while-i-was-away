import json

import pytest

from away.db import Database, encode, now
from away.inference import Ollama
from away.jobs import Worker
from away.service import associate_sessions, window_start


@pytest.fixture
def db(tmp_path):
    db = Database(tmp_path / "away.sqlite")
    db.execute("INSERT INTO repositories(id,name,path,demo,created_at) VALUES(?,?,?,?,?)", ("repo", "Demo", "demo://northstar", 1, now()))
    return db


def enqueue(db, job_id="job", status="queued", attempts=0):
    db.execute("INSERT INTO jobs(id,repo_id,status,stage,created_at,request,attempts) VALUES(?,?,?,?,?,?,?)", (job_id, "repo", status, "Waiting", now(), encode({"window": "24h"}), attempts))


async def test_persistent_queue_completes_without_advancing_checkpoint(db):
    enqueue(db)
    worker = Worker(db, Ollama())
    job = db.claim()
    assert db.claim() is None
    await worker.run_one(job)
    assert db.job("job")["status"] == "completed"
    assert db.job("job")["attempts"] == 1
    assert db.repo("repo")["acknowledged_snapshot_id"] is None
    assert db.latest("briefings", "repo")["demo"]


async def test_cancellation_cannot_publish_briefing(db):
    enqueue(db)
    job = db.claim()
    db.execute("UPDATE jobs SET status='cancelled' WHERE id='job'")
    await Worker(db, Ollama()).run_one(job)
    assert db.job("job")["status"] == "cancelled"
    assert db.latest("briefings", "repo") is None


def test_restart_recovery_is_bounded_and_cancelled_jobs_stay_cancelled(db):
    enqueue(db, "recover", "running", 1)
    enqueue(db, "exhausted", "running", 2)
    enqueue(db, "cancelled", "cancelled", 1)
    reopened = Database(db.path)
    reopened.recover()
    assert reopened.job("recover")["status"] == "queued"
    assert reopened.job("exhausted")["status"] == "failed"
    assert reopened.job("cancelled")["status"] == "cancelled"
    assert json.loads(reopened.one("SELECT request FROM jobs WHERE id='recover'")["request"])["window"] == "24h"


def test_windows_use_acknowledged_snapshot_not_generation_time():
    assert window_start({"window": "acknowledged"}, {"created_at": "2026-10-01T00:00:00+00:00"}) == "2026-10-01T00:00:00+00:00"
    assert window_start({"window": "custom", "since": "2026-10-01"}, None) == "2026-10-01T00:00:00+00:00"
    with pytest.raises(ValueError):
        window_start({"window": "custom", "since": "bad-date"}, None)


def test_entire_pr_association_requires_exact_code_commit_head():
    sha = "a" * 40
    session = {"checkpoint": {"commit_links": [{"sha": sha}]}}
    prs = [{"number": 42, "title": "Fix cache", "url": "https://github.com/example/repo/pull/42", "evidence_id": "pr-42", "head_sha": sha},
           {"number": 43, "title": "Same branch but older head", "url": "https://github.com/example/repo/pull/43", "evidence_id": "pr-43", "head_sha": "b" * 40}]
    assert [item["number"] for item in associate_sessions([session], prs)[0]["associated_prs"]] == [42]
    assert associate_sessions([{"branch": "same-name"}], prs)[0]["associated_prs"] == []
