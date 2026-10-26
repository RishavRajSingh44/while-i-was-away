import json
from datetime import datetime, timedelta, timezone

from .db import encode, identifier, now
from .demo import demo_snapshot
from .git_context import collect_git


def window_start(request, previous):
    window = request.get("window", "24h")
    if window == "acknowledged" and previous:
        return previous["created_at"]
    if window == "custom":
        value = request.get("since")
        if not value:
            raise ValueError("Custom windows require a date")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Invalid custom date") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed > datetime.now(timezone.utc):
            raise ValueError("The start date must not be in the future")
        return parsed.astimezone(timezone.utc).isoformat()
    if window not in {"24h", "7d", "acknowledged"}:
        raise ValueError("Unknown collection window")
    return (datetime.now(timezone.utc) - timedelta(days=7 if window == "7d" else 1)).isoformat()


def save_snapshot(db, snapshot):
    db.execute("INSERT INTO snapshots(id,repo_id,created_at,data) VALUES(?,?,?,?)", (snapshot["id"], snapshot["repo_id"], snapshot["created_at"], encode(snapshot)))
    return json.loads(encode(snapshot))


def collect(db, repo_id, request):
    repo = db.repo(repo_id)
    if repo["demo"]:
        return save_snapshot(db, demo_snapshot(repo_id, identifier()))
    previous = db.document("snapshots", repo["acknowledged_snapshot_id"]) if repo["acknowledged_snapshot_id"] else None
    since = window_start(request, previous)
    git = collect_git(repo["path"], since, previous["git"] if previous else None, db.settings()["exclusions"])
    github = db.cache(repo_id) or {"prs": [], "synced_at": None, "offline": True, "error": "GitHub has not been synced", "user": None, "evidence": [], "warnings": []}
    for pr in github["prs"]:
        pr["matches_branch"] = bool(git["branch"] and pr["head_branch"] == git["branch"])
    warnings = list(git["warnings"]) + list(github.get("warnings", []))
    warnings.append("GitHub information is from the local cache. Use Sync GitHub to request current remote data.")
    if request.get("window") == "acknowledged" and not previous:
        warnings.append("No acknowledged checkpoint yet; using the last 24 hours.")
    session_evidence = [item for session in db.sessions(repo_id) for item in session["evidence"]]
    evidence = git["evidence"] + github["evidence"] + session_evidence
    if len(evidence) > 160:
        warnings.append("Evidence limited to 160 records; older imported session records omitted.")
        evidence = evidence[:100] + evidence[-60:]
    evidence = list({item["id"]: item for item in evidence}.values())
    return save_snapshot(db, {"id": identifier(), "repo_id": repo_id, "created_at": now(), "since": since, "git": git, "github": github, "evidence": evidence, "warnings": warnings})


def save_briefing(db, briefing):
    db.execute("INSERT INTO briefings(id,repo_id,snapshot_id,created_at,data) VALUES(?,?,?,?,?)", (briefing["id"], briefing["repo_id"], briefing["snapshot_id"], briefing["created_at"], encode(briefing)))
    return briefing


def associate_sessions(sessions, prs):
    """Only an exact local Entire commit and authoritative PR head hash form a link."""
    for session in sessions:
        links = {item.get("sha") for item in (session.get("checkpoint") or {}).get("commit_links", []) if isinstance(item, dict)}
        session["associated_prs"] = [{"number": pr["number"], "title": pr["title"], "url": pr["url"], "evidence_id": pr["evidence_id"]}
                                     for pr in prs if pr.get("head_sha") and pr["head_sha"] in links]
    return sessions
