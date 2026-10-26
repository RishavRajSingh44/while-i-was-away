import asyncio
import json

from .db import encode, identifier, now
from .demo import demo_briefing
from .inference import add_verified_facts, cache_key, make_handoff, synthesize
from .security import redact
from .service import collect


class Worker:
    def __init__(self, db, ollama):
        self.db = db
        self.ollama = ollama
        self.stopping = False

    def cancelled(self, job_id):
        row = self.db.one("SELECT status FROM jobs WHERE id=?", (job_id,))
        return not row or row["status"] == "cancelled" or self.stopping

    def progress(self, job_id, stage, amount):
        self.db.execute("UPDATE jobs SET stage=?,progress=? WHERE id=? AND status='running'", (stage, amount, job_id))

    async def run_one(self, job):
        job_id = job["id"]
        try:
            request = json.loads(job["request"])
            repo = self.db.repo(job["repo_id"])
            snapshot = await asyncio.to_thread(collect, self.db, repo["id"], request)
            if self.cancelled(job_id):
                return
            if repo["demo"]:
                briefing = demo_briefing(repo, snapshot, identifier())
            else:
                model = request.get("model") or self.db.settings()["model"]
                self.progress(job_id, "Checking the installed local model", 15)
                digest = await self.ollama.model_identity(model)
                key = cache_key(snapshot["evidence"], model, digest)
                cached = self.db.one("SELECT data FROM inference_cache WHERE key=?", (key,))
                if cached:
                    result = json.loads(cached["data"])
                    self.progress(job_id, "Reusing a validated evidence/model/prompt cache", 90)
                else:
                    result = await synthesize(self.ollama, model, snapshot["evidence"], lambda: self.cancelled(job_id), lambda stage, amount: self.progress(job_id, stage, amount))
                    if self.cancelled(job_id):
                        return
                    self.db.execute("INSERT OR REPLACE INTO inference_cache(key,data,created_at) VALUES(?,?,?)", (key, encode(result), now()))
                result["sections"] = add_verified_facts(result["sections"], snapshot)
                briefing = {"id": identifier(), "repo_id": repo["id"], "snapshot_id": snapshot["id"], "created_at": now(), "model": model, "model_digest": digest,
                            "demo": False, "sections": result["sections"], "evidence": snapshot["evidence"], "warnings": snapshot["warnings"] + result["warnings"],
                            "handoff": make_handoff(repo, snapshot, result["sections"], snapshot["evidence"])}
            # Cancellation and completion share a transaction; a cancelled job cannot publish.
            with self.db.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                current = connection.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
                if not current or current[0] != "running" or self.stopping:
                    return
                connection.execute("INSERT INTO briefings(id,repo_id,snapshot_id,created_at,data) VALUES(?,?,?,?,?)", (briefing["id"], repo["id"], snapshot["id"], briefing["created_at"], encode(briefing)))
                connection.execute("UPDATE jobs SET status='completed',stage='Briefing ready',progress=100,briefing_id=? WHERE id=?", (briefing["id"], job_id))
        except asyncio.CancelledError:
            if not self.stopping:
                self.db.execute("UPDATE jobs SET status='cancelled',stage='Cancelled' WHERE id=? AND status='running'", (job_id,))
            raise
        except Exception as exc:
            self.db.execute("UPDATE jobs SET status='failed',stage='Could not complete briefing',error=? WHERE id=? AND status='running'", (redact(str(exc))[:1200], job_id))

    async def run(self):
        self.db.recover()
        while not self.stopping:
            job = self.db.claim()
            if job:
                try:
                    await self.run_one(job)
                except asyncio.CancelledError:
                    if self.stopping:
                        break
            else:
                await asyncio.sleep(0.25)
