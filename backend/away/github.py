"""Authenticated github.com reads through gh, with explicit stale-cache failures."""
from __future__ import annotations

from copy import deepcopy
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import json
import re
import time
from urllib.parse import urlsplit

from .git_context import discover_repo, run_command
from .security import redact

MAX_PRS = 300
MAX_DISCUSSION = 200
SYNC_DEADLINE: ContextVar[float | None] = ContextVar("github_sync_deadline", default=None)
DISCUSSION_FIELDS = "nodes { author { login } body createdAt url } pageInfo { hasNextPage endCursor }"
INLINE_FIELDS = "nodes { author { login } body createdAt url path line } pageInfo { hasNextPage endCursor }"
REVIEW_FIELDS = "nodes { id author { login } state body submittedAt comments(first:10) { " + INLINE_FIELDS + " } } pageInfo { hasNextPage endCursor }"
CHECK_FIELDS = "nodes { ... on CheckRun { name status conclusion } ... on StatusContext { context state } } pageInfo { hasNextPage endCursor }"
PR_FIELDS = f"""id number title url state isDraft mergedAt headRefName headRefOid baseRefName updatedAt reviewDecision mergeable
reviews(first:50) {{ {REVIEW_FIELDS} }} comments(first:50) {{ {DISCUSSION_FIELDS} }}
commits(last:1) {{ nodes {{ commit {{ id statusCheckRollup {{ contexts(first:100) {{ {CHECK_FIELDS} }} }} }} }} }}"""
SEARCH_QUERY = "query($search:String!, $cursor:String) { search(query:$search,type:ISSUE,first:50,after:$cursor) { nodes { ... on PullRequest { " + PR_FIELDS + " } } pageInfo { hasNextPage endCursor } } }"


def _api(endpoint: str, **fields) -> dict:
    deadline = SYNC_DEADLINE.get()
    remaining = deadline - time.monotonic() if deadline else 35
    if remaining <= 0:
        raise RuntimeError("GitHub synchronization exceeded its 120-second time budget; retaining cached data.")
    args = ["gh", "api", "--hostname", "github.com", endpoint]
    for key, value in fields.items():
        if value is not None:
            args.extend(["-f", f"{key}={value}"])
    try:
        data = json.loads(run_command(args, timeout=min(35, remaining)))
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("GitHub returned an unsupported response.")
    if data.get("errors"):
        errors = "; ".join(str(item.get("message", "GraphQL error")) for item in data["errors"] if isinstance(item, dict))
        raise RuntimeError(redact(errors))
    return data


def github_health() -> dict:
    try:
        user = _api("user").get("login")
        if not isinstance(user, str) or not user:
            raise RuntimeError("GitHub did not return an authenticated login.")
        return {"ok": True, "message": f"Authenticated to github.com as {user}.", "user": user}
    except RuntimeError as exc:
        return {"ok": False, "message": redact(f"GitHub unavailable. Run gh auth login if needed. {exc}"), "user": None}


def _repository(root: str) -> str:
    remotes = discover_repo(root)["remotes"]
    remotes.sort(key=lambda item: item["name"] != "origin")
    for remote in remotes:
        url = remote["url"]
        if url.startswith("git@github.com:"):
            path = url.removeprefix("git@github.com:")
        else:
            parsed = urlsplit(url)
            if parsed.hostname != "github.com" or parsed.scheme not in ("https", "ssh"):
                continue
            path = parsed.path.lstrip("/")
        path = path.removesuffix(".git").rstrip("/")
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", path):
            return path
    raise RuntimeError("No github.com remote found in this repository.")


def _discussion(node: dict, field: str, warnings: list[str]) -> list[dict]:
    connection = node.get(field) or {}
    items = list(connection.get("nodes") or [])
    seen = set()
    fields = REVIEW_FIELDS if field == "reviews" else DISCUSSION_FIELDS
    while connection.get("pageInfo", {}).get("hasNextPage") and len(items) < MAX_DISCUSSION:
        cursor = connection["pageInfo"].get("endCursor")
        if not cursor or cursor in seen:
            raise RuntimeError("GitHub pagination cursor did not advance.")
        seen.add(cursor)
        query = "query($id:ID!, $cursor:String!) { node(id:$id) { ... on PullRequest { " + field + "(first:50,after:$cursor) { " + fields + " } } } }"
        response = _api("graphql", query=query, id=node["id"], cursor=cursor)
        connection = response.get("data", {}).get("node", {}).get(field) or {}
        items.extend(connection.get("nodes") or [])
    if connection.get("pageInfo", {}).get("hasNextPage"):
        warnings.append(f"PR #{node['number']} {field} limited to {MAX_DISCUSSION} most recently available entries in the API page sequence.")
    return [item for item in items[:MAX_DISCUSSION] if isinstance(item, dict)]


def _checks(node: dict, warnings: list[str]) -> list[dict]:
    commits = node.get("commits", {}).get("nodes") or []
    commit = (commits[-1].get("commit") or {}) if commits else {}
    connection = (commit.get("statusCheckRollup") or {}).get("contexts") or {}
    items = list(connection.get("nodes") or [])
    seen = set()
    while connection.get("pageInfo", {}).get("hasNextPage") and len(items) < 300:
        cursor = connection["pageInfo"].get("endCursor")
        if not cursor or cursor in seen:
            raise RuntimeError("GitHub checks pagination cursor did not advance.")
        seen.add(cursor)
        query = "query($id:ID!, $cursor:String!) { node(id:$id) { ... on Commit { statusCheckRollup { contexts(first:100,after:$cursor) { " + CHECK_FIELDS + " } } } } }"
        response = _api("graphql", query=query, id=commit["id"], cursor=cursor)
        connection = ((response.get("data", {}).get("node") or {}).get("statusCheckRollup") or {}).get("contexts") or {}
        items.extend(connection.get("nodes") or [])
    if connection.get("pageInfo", {}).get("hasNextPage"):
        warnings.append(f"PR #{node['number']} checks limited to 300 entries.")
    result = []
    for item in items[:300]:
        if not isinstance(item, dict):
            continue
        if "context" in item:
            result.append({"name": item["context"], "status": "IN_PROGRESS" if item.get("state") in ("PENDING", "EXPECTED") else "COMPLETED", "conclusion": item.get("state")})
        else:
            result.append({"name": item.get("name", "Unnamed check"), "status": item.get("status", "UNKNOWN"), "conclusion": item.get("conclusion")})
    return result


def _inline_comments(reviews: list[dict], number: int, warnings: list[str]) -> list[dict]:
    items = []
    for review in reviews:
        connection = review.get("comments") or {}
        items.extend(connection.get("nodes") or [])
        seen = set()
        while connection.get("pageInfo", {}).get("hasNextPage") and len(items) < MAX_DISCUSSION:
            cursor = connection["pageInfo"].get("endCursor")
            if not cursor or cursor in seen:
                raise RuntimeError("GitHub inline comment pagination cursor did not advance.")
            seen.add(cursor)
            query = "query($id:ID!, $cursor:String!) { node(id:$id) { ... on PullRequestReview { comments(first:50,after:$cursor) { " + INLINE_FIELDS + " } } } }"
            response = _api("graphql", query=query, id=review["id"], cursor=cursor)
            connection = response.get("data", {}).get("node", {}).get("comments") or {}
            items.extend(connection.get("nodes") or [])
        if len(items) >= MAX_DISCUSSION:
            warnings.append(f"PR #{number} inline review comments limited to {MAX_DISCUSSION} entries.")
            break
    return [{"author": (item.get("author") or {}).get("login", "deleted user"), "body": redact(f"{item.get('path', 'file')}:{item.get('line') or '?'} — {item.get('body', '')}")[:6000], "created_at": item.get("createdAt"), "url": item.get("url")} for item in items[:MAX_DISCUSSION] if isinstance(item, dict)]


def _normalize(node: dict, branch: str | None, old: dict | None, warnings: list[str]) -> tuple[dict, list[dict]]:
    if node.get("state") not in ("OPEN", "CLOSED", "MERGED") or not isinstance(node.get("isDraft"), bool):
        raise RuntimeError("GitHub returned an unsupported PR state; retaining cached information.")
    state = "merged" if node.get("mergedAt") or node.get("state") == "MERGED" else "closed" if node.get("state") == "CLOSED" else "draft" if node.get("isDraft") else "open"
    comments = [{"author": (item.get("author") or {}).get("login", "deleted user"), "body": redact(str(item.get("body", "")))[:6000], "created_at": item.get("createdAt"), "url": item.get("url")} for item in _discussion(node, "comments", warnings)]
    review_nodes = _discussion(node, "reviews", warnings)
    reviews = [{"author": (item.get("author") or {}).get("login", "deleted user"), "state": item.get("state", "UNKNOWN"), "body": redact(str(item.get("body", "")))[:6000], "submitted_at": item.get("submittedAt")} for item in review_nodes]
    comments.extend(_inline_comments(review_nodes, node["number"], warnings))
    result = {"number": node["number"], "title": redact(node.get("title", "")), "url": node.get("url", ""), "state": state, "head_branch": node.get("headRefName"), "head_sha": node.get("headRefOid"), "base_branch": node.get("baseRefName"), "updated_at": node.get("updatedAt"), "review_state": node.get("reviewDecision") or "UNKNOWN", "mergeability": node.get("mergeable") or "UNKNOWN", "checks": _checks(node, warnings), "reviews": reviews, "comments": comments, "matches_branch": bool(branch and branch == node.get("headRefName")), "changes": []}
    if old:
        for key, label in (("state", "State"), ("review_state", "Review decision"), ("mergeability", "Mergeability")):
            if old.get(key) != result[key]:
                result["changes"].append(f"{label}: {old.get(key, 'unknown')} → {result[key]}")
        if old.get("checks") != result["checks"]:
            result["changes"].append("Check results changed since the previous sync.")
        if old.get("reviews") != reviews:
            result["changes"].append("Review activity changed since the previous sync.")
        if old.get("comments") != comments:
            result["changes"].append("Comments changed since the previous sync.")
        if old.get("updated_at") != result["updated_at"] and not result["changes"]:
            result["changes"].append("PR was updated since the previous sync.")
    else:
        result["changes"].append("First observed in this app; earlier changes are unknown.")
    facts = {**result, "reviews": [{key: value for key, value in item.items() if key != "body"} for item in reviews], "comments": [{key: value for key, value in item.items() if key != "body"} for item in comments]}
    body = json.dumps(facts, ensure_ascii=False)
    evidence_id = "github-pr-" + hashlib.sha256(body.encode()).hexdigest()[:20]
    result["evidence_id"] = evidence_id
    evidence = [{"id": evidence_id, "kind": "pull-request", "title": f"PR #{result['number']}: {result['title']}", "body": body, "source": result["url"], "timestamp": result["updated_at"], "trust": "verified", "url": result["url"], "metadata": {"state": state}}]
    if comments or reviews:
        discussion = json.dumps({"reviews": reviews, "comments": comments}, ensure_ascii=False)
        discussion_id = "github-discussion-" + hashlib.sha256(f"{result['url']}\0{discussion}".encode()).hexdigest()[:20]
        evidence.append({"id": discussion_id, "kind": "pull-request-discussion", "title": f"PR #{result['number']} · reviewer statements (unverified)", "body": discussion, "source": result["url"], "timestamp": result["updated_at"], "trust": "user-provided", "url": result["url"], "metadata": {"historical": True, "statements_are_not_test_verification": True}})
    return result, evidence


def sync_github(root: str, branch: str | None, previous: dict | None = None) -> dict:
    token = SYNC_DEADLINE.set(time.monotonic() + 120)
    try:
        user = _api("user").get("login")
        if not isinstance(user, str) or not re.fullmatch(r"[A-Za-z0-9-]+", user):
            raise RuntimeError("GitHub authentication did not return a valid login.")
        repository = _repository(root)
        # Search can silently return zero results for an inaccessible repository.
        accessible = _api(f"repos/{repository}")
        if str(accessible.get("full_name", "")).lower() != repository.lower():
            raise RuntimeError("GitHub did not confirm access to the selected repository.")
        search = f"repo:{repository} is:pr author:{user} sort:updated-desc"
        nodes, cursor, seen, warnings = [], None, set(), []
        while True:
            data = _api("graphql", query=SEARCH_QUERY, search=search, cursor=cursor)
            connection = data.get("data", {}).get("search")
            if not isinstance(connection, dict):
                raise RuntimeError("GitHub returned no PR search data; repository access may be denied.")
            nodes.extend(node for node in connection.get("nodes", []) if isinstance(node, dict) and "number" in node)
            page = connection.get("pageInfo", {})
            if not page.get("hasNextPage"):
                break
            if len(nodes) >= MAX_PRS:
                warnings.append(f"PR results limited to the {MAX_PRS} most recently updated authored PRs.")
                break
            cursor = page.get("endCursor")
            if not cursor or cursor in seen:
                raise RuntimeError("GitHub pagination cursor did not advance.")
            seen.add(cursor)
        old_prs = {item["number"]: item for item in (previous or {}).get("prs", [])}
        prs, evidence = [], []
        for node in nodes[:MAX_PRS]:
            pr, sources = _normalize(node, branch, old_prs.get(node["number"]), warnings)
            prs.append(pr)
            evidence.extend(sources)
        return {"prs": prs, "synced_at": datetime.now(timezone.utc).isoformat(), "offline": False, "error": None, "user": user, "evidence": evidence, "warnings": warnings}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as exc:
        cached = deepcopy(previous) if previous else {"prs": [], "synced_at": None, "user": None, "evidence": [], "warnings": []}
        cached.update(offline=True, error=redact(str(exc)))
        cached["warnings"] = [*cached.get("warnings", []), "GitHub sync failed. Showing cached data." if cached.get("synced_at") else "GitHub sync failed; no cached data is available."]
        for pr in cached["prs"]:
            pr["matches_branch"] = bool(branch and pr.get("head_branch") == branch)
        return cached
    finally:
        SYNC_DEADLINE.reset(token)
