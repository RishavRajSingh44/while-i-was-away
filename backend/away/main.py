import asyncio
import json
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.staticfiles import StaticFiles

from .db import Database, encode, identifier, now
from .demo import demo_briefing, demo_session, demo_snapshot
from .git_context import discover_repo, fetch_refs
from .github import github_health, sync_github
from .inference import Ollama
from .jobs import Worker
from .security import LocalBoundary, clean, redact
from .service import associate_sessions, collect, save_briefing, save_snapshot, window_start
from .sessions import preview_sessions

ROOT = Path(__file__).resolve().parents[2]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RepoInput(Input):
    path: str = Field(min_length=1, max_length=4096)


class BriefingInput(Input):
    window: Literal["24h", "7d", "custom", "acknowledged"] = "24h"
    since: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=200)


class SessionInput(Input):
    path: str | None = Field(default=None, max_length=4096)
    text: str | None = Field(default=None, max_length=2_000_000)
    format: Literal["auto", "manual", "codex", "claude", "entire"] = "auto"
    title: str | None = Field(default=None, max_length=200)
    confirm_mismatch: bool = False


class SettingsInput(Input):
    model: str = Field(min_length=1, max_length=200)
    exclusions: list[str] = Field(max_length=50)


class HandoffInput(Input):
    text: str = Field(max_length=250_000)


class DeleteInput(Input):
    confirm: Literal["DELETE"]


def create_app(database_path=None, run_worker=True):
    database = Database(database_path or os.environ.get("AWAY_DATABASE", str(ROOT / ".data/away.sqlite")))
    ollama = Ollama()
    worker = Worker(database, ollama)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(worker.run()) if run_worker else None
        yield
        worker.stopping = True
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(title="While I Was Away", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.db = database
    app.state.worker = worker
    app.add_middleware(LocalBoundary, port=int(os.environ.get("AWAY_PORT", "8765")), development=os.environ.get("AWAY_DEV") == "1")

    @app.exception_handler(ValueError)
    async def invalid(_, exc):
        return JSONResponse({"detail": redact(str(exc))}, status_code=400)

    @app.exception_handler(LookupError)
    async def missing(_, exc):
        return JSONResponse({"detail": redact(str(exc))}, status_code=404)

    @app.exception_handler(RuntimeError)
    async def failed(_, exc):
        return JSONResponse({"detail": redact(str(exc))}, status_code=502)

    @app.get("/api/health")
    async def health():
        github, local = await asyncio.gather(asyncio.to_thread(github_health), ollama.health())
        return clean({"git": {"ok": bool(shutil.which("git")), "message": "Git available" if shutil.which("git") else "Install Git"}, "github": github, "ollama": local, "version": "0.1.0"})

    @app.get("/api/settings")
    def settings():
        return database.settings()

    @app.put("/api/settings")
    async def update_settings(body: SettingsInput):
        if any(len(pattern) > 200 or "\x00" in pattern for pattern in body.exclusions):
            raise ValueError("Exclusion patterns must be at most 200 characters")
        await ollama.model_identity(body.model)
        with database.connect() as db:
            for key, value in body.model_dump().items():
                db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, encode(value)))
        return database.settings()

    @app.get("/api/repos")
    def repositories():
        return [database.repo(row["id"]) for row in database.rows("SELECT id FROM repositories ORDER BY created_at")]

    @app.post("/api/repos")
    def add_repository(body: RepoInput):
        discovered = discover_repo(body.path)
        path = discovered["root"]
        existing = database.one("SELECT id FROM repositories WHERE path=?", (path,))
        if existing:
            return database.repo(existing["id"])
        repo_id = identifier()
        database.execute("INSERT INTO repositories(id,name,path,created_at) VALUES(?,?,?,?)", (repo_id, Path(path).name, path, now()))
        return database.repo(repo_id)

    @app.delete("/api/repos/{repo_id}")
    def delete_repository(repo_id: str):
        database.repo(repo_id)
        with database.connect() as db:
            db.execute("DELETE FROM repositories WHERE id=?", (repo_id,))
            # Cache contents may include this repository; clearing all avoids orphaned private evidence.
            db.execute("DELETE FROM inference_cache")
        return {"ok": True}

    @app.post("/api/demo")
    def demo():
        existing = database.one("SELECT id FROM repositories WHERE demo=1")
        if existing:
            return database.repo(existing["id"])
        repo_id = identifier()
        database.execute("INSERT INTO repositories(id,name,path,demo,created_at) VALUES(?,?,?,?,?)", (repo_id, "Northstar", "demo://northstar", 1, now()))
        repository = database.repo(repo_id)
        snapshot = save_snapshot(database, demo_snapshot(repo_id, identifier()))
        save_briefing(database, demo_briefing(repository, snapshot, identifier()))
        session = demo_session()
        database.execute("INSERT INTO sessions(id,repo_id,data) VALUES(?,?,?)", (session["id"], repo_id, encode(session)))
        database.execute("INSERT INTO github_cache(repo_id,data) VALUES(?,?)", (repo_id, encode(snapshot["github"])))
        return repository

    @app.get("/api/repos/{repo_id}/history")
    def history(repo_id: str):
        database.repo(repo_id)
        return [json.loads(row["data"]) for row in database.rows("SELECT data FROM briefings WHERE repo_id=? ORDER BY created_at DESC,rowid DESC LIMIT 100", (repo_id,))]

    @app.get("/api/repos/{repo_id}/overview")
    def overview(repo_id: str):
        repository = database.repo(repo_id)
        snapshot = database.latest("snapshots", repo_id)
        return {"repository": repository, "snapshot": snapshot, "briefing": database.latest("briefings", repo_id), "sessions": associate_sessions(database.sessions(repo_id), (snapshot or {}).get("github", {}).get("prs", [])),
                "jobs": [database.job(row["id"]) for row in database.rows("SELECT id FROM jobs WHERE repo_id=? ORDER BY created_at DESC LIMIT 10", (repo_id,))], "history": history(repo_id)}

    @app.post("/api/repos/{repo_id}/collect")
    def collect_snapshot(repo_id: str, body: BriefingInput):
        return collect(database, repo_id, body.model_dump())

    @app.post("/api/repos/{repo_id}/sync")
    def sync(repo_id: str):
        repository = database.repo(repo_id)
        if repository["demo"]:
            return database.cache(repo_id)
        current = discover_repo(repository["path"])
        result = clean(sync_github(repository["path"], current.get("branch"), database.cache(repo_id)))
        database.execute("INSERT OR REPLACE INTO github_cache(repo_id,data) VALUES(?,?)", (repo_id, encode(result)))
        # Store a new observation so the board updates; previous snapshots remain immutable.
        collect(database, repo_id, {"window": "acknowledged"})
        return result

    @app.post("/api/repos/{repo_id}/fetch")
    def fetch(repo_id: str):
        repository = database.repo(repo_id)
        if repository["demo"]:
            raise ValueError("Demo has no real remote refs to fetch")
        fetch_refs(repository["path"])
        return {"ok": True, "message": "Remote refs fetched. Your working tree was not changed. Collect a new snapshot to compare."}

    @app.post("/api/repos/{repo_id}/briefings")
    def generate(repo_id: str, body: BriefingInput):
        repository = database.repo(repo_id)
        previous = database.document("snapshots", repository["acknowledged_snapshot_id"]) if repository["acknowledged_snapshot_id"] else None
        window_start(body.model_dump(), previous)
        with database.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT id FROM jobs WHERE repo_id=? AND status IN ('queued','running')", (repo_id,)).fetchone()
            if existing:
                job_id = existing["id"]
            else:
                job_id = identifier()
                db.execute("INSERT INTO jobs(id,repo_id,status,stage,created_at,request) VALUES(?,?,?,?,?,?)", (job_id, repo_id, "queued", "Waiting for local worker", now(), encode(body.model_dump())))
        return database.job(job_id)

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        return database.job(job_id)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str):
        database.job(job_id)
        database.execute("UPDATE jobs SET status='cancelled',stage='Cancelled by you' WHERE id=? AND status IN ('queued','running')", (job_id,))
        return database.job(job_id)

    @app.get("/api/briefings/{briefing_id}")
    def briefing(briefing_id: str):
        return database.document("briefings", briefing_id)

    @app.post("/api/briefings/{briefing_id}/acknowledge")
    def acknowledge(briefing_id: str):
        item = database.document("briefings", briefing_id)
        with database.connect() as db:
            current = db.execute("SELECT s.created_at FROM repositories r LEFT JOIN snapshots s ON s.id=r.acknowledged_snapshot_id WHERE r.id=?", (item["repo_id"],)).fetchone()
            timestamp = db.execute("SELECT created_at FROM snapshots WHERE id=?", (item["snapshot_id"],)).fetchone()[0]
            if current and current[0] and current[0] > timestamp:
                raise ValueError("A newer briefing is already acknowledged; checkpoint cannot move backwards")
            db.execute("UPDATE repositories SET acknowledged_snapshot_id=? WHERE id=?", (item["snapshot_id"], item["repo_id"]))
        return database.repo(item["repo_id"])

    @app.put("/api/briefings/{briefing_id}/handoff")
    def edit_handoff(briefing_id: str, body: HandoffInput):
        item = database.document("briefings", briefing_id)
        item["handoff"] = redact(body.text)
        database.execute("UPDATE briefings SET data=? WHERE id=?", (encode(item), briefing_id))
        return {"text": item["handoff"]}

    @app.get("/api/briefings/{briefing_id}/export")
    def export(briefing_id: str):
        item = database.document("briefings", briefing_id)
        return PlainTextResponse(redact(item["handoff"]), media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="while-i-was-away.md"'})

    @app.post("/api/repos/{repo_id}/sessions/preview")
    def preview(repo_id: str, body: SessionInput):
        repository = database.repo(repo_id)
        if bool(body.path) == bool(body.text):
            raise ValueError("Provide either a selected path or pasted text")
        return clean(preview_sessions(body.path, body.text, body.format, repository["path"], body.title))

    @app.post("/api/repos/{repo_id}/sessions/import")
    def import_sessions(repo_id: str, body: SessionInput):
        result = preview(repo_id, body)
        candidates = result["candidates"]
        if not candidates:
            raise ValueError("No supported sessions found; inspect preview warnings")
        if len(candidates) > 1:
            raise ValueError("Import one previewed file at a time to confirm its repository association")
        if any(item["match"] != "matched" for item in candidates) and not body.confirm_mismatch:
            raise HTTPException(status_code=409, detail="Repository association is unknown or mismatched. Confirm this selected session belongs to the repository.")
        with database.connect() as db:
            for session in candidates:
                db.execute("INSERT OR REPLACE INTO sessions(id,repo_id,data) VALUES(?,?,?)", (session["id"], repo_id, encode(session)))
        return candidates

    @app.delete("/api/repos/{repo_id}/sessions/{session_id}")
    def delete_session(repo_id: str, session_id: str):
        database.repo(repo_id)
        database.execute("DELETE FROM sessions WHERE repo_id=? AND id=?", (repo_id, session_id))
        return {"ok": True}

    @app.delete("/api/data")
    def delete_data(body: DeleteInput):
        with database.connect() as db:
            db.execute("DELETE FROM repositories")
            db.execute("DELETE FROM inference_cache")
            db.execute("DELETE FROM settings")
        return {"ok": True}

    dist = ROOT / "frontend/dist"
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/")
    def index():
        if not (dist / "index.html").exists():
            return PlainTextResponse("Frontend not built. Run python scripts/run.py dev, or npm --prefix frontend run build.", status_code=503)
        return FileResponse(dist / "index.html")

    return app


app = create_app()
