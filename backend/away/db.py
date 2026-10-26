import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .security import clean


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier():
    return uuid.uuid4().hex


def encode(value):
    return json.dumps(clean(value), ensure_ascii=True, separators=(",", ":"))


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise RuntimeError("Database is newer than this application; restore a compatible backup")
            if version == 0:
                db.executescript((Path(__file__).parent / "migrations/001_initial.sql").read_text())
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA secure_delete=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def rows(self, sql, args=()):
        with self.connect() as db:
            return [dict(row) for row in db.execute(sql, args)]

    def one(self, sql, args=()):
        rows = self.rows(sql, args)
        return rows[0] if rows else None

    def execute(self, sql, args=()):
        with self.connect() as db:
            return db.execute(sql, args).rowcount

    def repo(self, repo_id):
        item = self.one("SELECT * FROM repositories WHERE id=?", (repo_id,))
        if not item:
            raise LookupError("Repository not found")
        item["demo"] = bool(item["demo"])
        return item

    def document(self, table, item_id):
        if table not in {"snapshots", "briefings"}:
            raise ValueError("Invalid document table")
        item = self.one(f"SELECT data FROM {table} WHERE id=?", (item_id,))
        if not item:
            raise LookupError("Record not found")
        return json.loads(item["data"])

    def latest(self, table, repo_id):
        if table not in {"snapshots", "briefings"}:
            raise ValueError("Invalid document table")
        item = self.one(f"SELECT data FROM {table} WHERE repo_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1", (repo_id,))
        return json.loads(item["data"]) if item else None

    def sessions(self, repo_id):
        return [json.loads(row["data"]) for row in self.rows("SELECT data FROM sessions WHERE repo_id=? ORDER BY rowid", (repo_id,))]

    def cache(self, repo_id):
        row = self.one("SELECT data FROM github_cache WHERE repo_id=?", (repo_id,))
        return json.loads(row["data"]) if row else None

    def settings(self):
        defaults = {"model": "gemma3:4b", "exclusions": [".env*", "*.pem", "*.key", "*credentials*", "*secret*", "package-lock.json", "node_modules/*"]}
        defaults.update({row["key"]: json.loads(row["value"]) for row in self.rows("SELECT * FROM settings")})
        return defaults

    def job(self, job_id):
        row = self.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not row:
            raise LookupError("Job not found")
        row.pop("request")
        return row

    def recover(self):
        self.execute("UPDATE jobs SET status='queued',stage='Recovered after interruption',progress=0 WHERE status='running' AND attempts<2")
        self.execute("UPDATE jobs SET status='failed',stage='Interrupted',error='Repeated interruption; generate a new briefing' WHERE status='running'")

    def claim(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='running',stage='Collecting local evidence',attempts=attempts+1 WHERE id=?", (row["id"],))
            return dict(row)
