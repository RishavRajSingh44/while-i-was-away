CREATE TABLE repositories (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
    demo INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
    acknowledged_snapshot_id TEXT
);
CREATE TABLE snapshots (
    id TEXT PRIMARY KEY, repo_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL, data TEXT NOT NULL
);
CREATE TABLE sessions (
    id TEXT NOT NULL, repo_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    data TEXT NOT NULL, PRIMARY KEY(repo_id, id)
);
CREATE TABLE github_cache (
    repo_id TEXT PRIMARY KEY REFERENCES repositories(id) ON DELETE CASCADE, data TEXT NOT NULL
);
CREATE TABLE briefings (
    id TEXT PRIMARY KEY, repo_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    snapshot_id TEXT NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL, data TEXT NOT NULL
);
CREATE TABLE jobs (
    id TEXT PRIMARY KEY, repo_id TEXT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    status TEXT NOT NULL, stage TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
    error TEXT, briefing_id TEXT, created_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    request TEXT NOT NULL
);
CREATE INDEX jobs_status ON jobs(status, created_at);
CREATE INDEX briefings_repo ON briefings(repo_id, created_at DESC);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE inference_cache (key TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT NOT NULL);
PRAGMA user_version = 1;
