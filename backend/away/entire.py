"""Read selected, local Entire checkpoint refs without invoking Entire or fetching."""
from __future__ import annotations

from contextvars import ContextVar
import hashlib
import json
import re
import time
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from .git_context import _git as _raw_git, discover_repo
from .security import redact

CHECKPOINT_ID = re.compile(r"(?:[0-9a-f]{12}|[0-7][0-9A-HJKMNP-TV-Z]{25})", re.IGNORECASE)
SHA = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
PREFIX = "refs/entire/checkpoints/"
MAX_CHECKPOINTS = 20
MAX_BLOB = 2_000_000
READ_DEADLINE: ContextVar[float | None] = ContextVar("entire_read_deadline", default=None)


def _git(root: str, *args: str) -> str:
    deadline = READ_DEADLINE.get()
    remaining = deadline - time.monotonic() if deadline else 20
    if remaining <= 0:
        raise RuntimeError("Entire local read exceeded its 45-second time budget.")
    return _raw_git(root, *args, timeout=min(20, remaining))


def _optional(root: str, *args: str) -> str | None:
    try:
        return _git(root, *args).strip() or None
    except RuntimeError:
        return None


def _selector(root: str, checkpoint: str, slot: str) -> str:
    return "entire:" + quote(root, safe="/") + "?" + urlencode({"checkpoint": checkpoint, "session": slot})


def _selection(path: str) -> tuple[str, str | None, str | None]:
    if not path.startswith("entire:"):
        return discover_repo(path)["root"], None, None
    from urllib.parse import unquote
    parsed = urlsplit(path)
    query = parse_qs(parsed.query, strict_parsing=True)
    if parsed.netloc or parsed.fragment or set(query) != {"checkpoint", "session"} or any(len(value) != 1 for value in query.values()):
        raise ValueError("Invalid Entire checkpoint selector.")
    checkpoint, slot = query["checkpoint"][0], query["session"][0]
    if not CHECKPOINT_ID.fullmatch(checkpoint) or not re.fullmatch(r"[1-9][0-9]{0,2}", slot):
        raise ValueError("Invalid Entire checkpoint ID or session slot.")
    root = discover_repo(unquote(parsed.path))["root"]
    return root, checkpoint, slot


def _refs(root: str, checkpoint: str | None) -> tuple[list[tuple[str, str, str]], list[str]]:
    pattern = f"{PREFIX}*/{checkpoint}" if checkpoint else PREFIX
    output = _git(root, "for-each-ref", f"--count={MAX_CHECKPOINTS + 1}", "--sort=-committerdate", "--format=%(refname)%00%(objectname)", pattern)
    refs, warnings = [], []
    for line in output.splitlines():
        ref, _, sha = line.partition("\0")
        suffix = ref.removeprefix(PREFIX).split("/")
        if not ref.startswith(PREFIX) or len(suffix) != 2 or not CHECKPOINT_ID.fullmatch(suffix[-1]) or suffix[0].lower() != suffix[-1][-2:].lower() or not SHA.fullmatch(sha):
            warnings.append("Skipped a malformed Entire checkpoint ref.")
            continue
        refs.append((suffix[-1], ref, sha))
    if len(refs) > MAX_CHECKPOINTS:
        warnings.append("Entire preview is limited to the 20 newest local checkpoint refs.")
    if not refs:
        warnings.append("No supported local Entire checkpoint refs found. This adapter reads refs/entire/checkpoints/<last-two-ID-characters>/<ID>; it never fetches or enables Entire.")
        if _optional(root, "rev-parse", "--verify", "refs/heads/entire/checkpoints/v1"):
            warnings.append("Legacy entire/checkpoints/v1 branch storage is not supported by this adapter; update/export through Entire yourself or use manual transcript import.")
    return refs[:MAX_CHECKPOINTS], warnings


def _blob(root: str, tree: str, path: str, *, optional: bool = False) -> str | None:
    if PurePosixPath(path).is_absolute() or any(part in (".", "..") for part in path.split("/")) or "\0" in path:
        raise ValueError("Unsafe checkpoint blob path.")
    listing = _git(root, "--literal-pathspecs", "ls-tree", "-z", tree, "--", path)
    if not listing:
        if optional:
            return None
        raise ValueError(f"Checkpoint file is unavailable: {path}")
    header, separator, name = listing.rstrip("\0").partition("\t")
    fields = header.split(" ")
    if not separator or name != path or len(fields) != 3 or fields[0] not in ("100644", "100755") or fields[1] != "blob" or not SHA.fullmatch(fields[2]):
        raise ValueError("Checkpoint source is not a regular Git blob.")
    size = int(_git(root, "cat-file", "-s", fields[2]).strip())
    if size > MAX_BLOB:
        raise ValueError("Checkpoint blob exceeds the 2 MB import limit.")
    return _git(root, "cat-file", "blob", fields[2])


def _json(content: str | None) -> dict:
    try:
        value = json.loads(content or "")
    except (ValueError, RecursionError) as exc:
        raise ValueError("Checkpoint metadata must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise ValueError("Checkpoint metadata must be an object.")
    return value


def _path(value, checkpoint: str, *, required_name: str | None = None) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ValueError("Checkpoint session metadata has no supported file path.")
    path = value.lstrip("/")
    legacy = f"{checkpoint[:2]}/{checkpoint[2:]}/"
    if path.startswith(legacy):
        path = path[len(legacy):]
    match = re.fullmatch(r"([1-9][0-9]{0,2})/(metadata\.json|full\.jsonl|transcript\.jsonl|prompt\.txt)", path)
    if not match or (required_name and match[2] != required_name):
        raise ValueError("Unsupported or unsafe Entire session file path.")
    return path, match[1]


def _reachable(root: str, sha: str) -> bool:
    if not isinstance(sha, str) or not SHA.fullmatch(sha) or _optional(root, "cat-file", "-t", sha) != "commit":
        return False
    refs = (_optional(root, "for-each-ref", f"--contains={sha}", "--format=%(refname)", "refs/heads/", "refs/remotes/") or "").splitlines()
    if any("/entire/" not in ref for ref in refs):
        return True
    try:
        _git(root, "merge-base", "--is-ancestor", sha, "HEAD")
        return True
    except RuntimeError:
        return False


def _trailer_links(root: str) -> dict[str, list[str]]:
    refs = (_optional(root, "for-each-ref", "--format=%(refname)", "refs/heads/", "refs/remotes/") or "").splitlines()
    refs = [ref for ref in refs if "/entire/" not in ref][:50]
    if _optional(root, "rev-parse", "--verify", "HEAD"):
        refs.append("HEAD")
    if not refs:
        return {}
    output = _git(root, "log", "--max-count=400", "--format=%H%x00%(trailers:key=Entire-Checkpoint,valueonly,separator=%x1f)%x00", *refs, "--")
    links: dict[str, list[str]] = {}
    for record in output.splitlines():
        parts = record.split("\0")
        if len(parts) != 3 or not SHA.fullmatch(parts[0]):
            continue
        for checkpoint in parts[1].split("\x1f"):
            checkpoint = checkpoint.strip()
            if CHECKPOINT_ID.fullmatch(checkpoint):
                links.setdefault(checkpoint.lower(), []).append(parts[0])
    return links


def _commit_evidence(root: str, checkpoint: str, summary: dict, metadata: dict, trailers: dict) -> list[dict]:
    links = [(sha, "Entire-Checkpoint commit trailer") for sha in trailers.get(checkpoint.lower(), [])]
    for entry in summary.get("linked_commits", []) if isinstance(summary.get("linked_commits"), list) else []:
        if isinstance(entry, dict):
            links.append((entry.get("sha"), "Entire linked_commits metadata (recorded attribution link)"))
    for sha in (metadata.get("commit_sha"), summary.get("commit_sha")):
        if sha:
            links.append((sha, "Entire import anchor (not attribution)"))
    evidence, seen = [], set()
    for sha, relation in links[:50]:
        if not isinstance(sha, str) or sha in seen or not _reachable(root, sha):
            continue
        seen.add(sha)
        fields = _git(root, "show", "--no-patch", "--format=%H%x00%an%x00%aI%x00%s", sha).rstrip("\n").split("\0", 3)
        if len(fields) != 4:
            continue
        body = redact(f"Code commit: {fields[0]}\nAuthor: {fields[1]}\nTimestamp: {fields[2]}\nSubject: {fields[3]}\nCheckpoint: {checkpoint}\nAssociation: {relation}\nThis verifies the recorded link and local commit, not whether agent claims or tests are correct.")
        evidence.append({"id": "entire-commit-" + hashlib.sha256(f"{root}\0{body}".encode()).hexdigest()[:20], "kind": "entire-code-commit", "title": f"Entire checkpoint linked to code commit {sha[:10]}", "body": body, "source": f"{root} · {sha}", "timestamp": fields[2], "trust": "verified", "metadata": {"checkpoint_id": checkpoint, "sha": sha, "association": relation}})
    return evidence


def _transcript(root: str, tree: str, checkpoint: str, paths: dict, metadata: dict, slot: str) -> dict:
    from .sessions import ADAPTERS, _detect
    warnings, parsed = [], None
    raw = paths.get("transcript")
    if raw:
        try:
            name, path_slot = _path(raw, checkpoint, required_name="full.jsonl")
            if path_slot != slot:
                raise ValueError("Transcript path belongs to a different session slot.")
            content = _blob(root, tree, name, optional=True)
            if content:
                adapter = _detect(content, ".jsonl")
                parsed = ADAPTERS[adapter].parse(content)
        except (ValueError, RuntimeError) as exc:
            warnings.append(f"Raw transcript unavailable or unsupported: {redact(str(exc))}")
    if parsed is None:
        parsed = {"messages": [], "repo_path": None, "branch": None, "created_at": None, "warnings": []}
        warnings.append("Full native transcript unavailable; this checkpoint preview contains only its stored prompt/summary. Last exchange is unknown.")
    prompt = paths.get("prompt")
    if prompt:
        try:
            name, path_slot = _path(prompt, checkpoint, required_name="prompt.txt")
            if path_slot != slot:
                raise ValueError("Prompt path belongs to a different session slot.")
            text = _blob(root, tree, name, optional=True)
            if text and not any(message["role"] == "user" for message in parsed["messages"]):
                parsed["messages"].insert(0, {"role": "user", "text": "Stored Entire prompt(s):\n" + text, "timestamp": metadata.get("created_at")})
        except (ValueError, RuntimeError) as exc:
            warnings.append(f"Stored prompt unavailable: {redact(str(exc))}")
    if isinstance(metadata.get("summary"), dict):
        summary_message = {"role": "assistant", "text": "Entire generated checkpoint summary (reported, not independently verified):\n" + json.dumps(metadata["summary"], ensure_ascii=False), "timestamp": metadata.get("created_at")}
        parsed["messages"].insert(1 if parsed["messages"] else 0, summary_message)
    parsed["warnings"].extend(warnings)
    return parsed


def _preview_entire(path: str, repo_path: str, title: str | None = None) -> dict:
    from .sessions import _match, _normalize
    deadline = time.monotonic() + 45
    root, checkpoint_selection, session_selection = _selection(path)
    refs, warnings = _refs(root, checkpoint_selection)
    trailers = _trailer_links(root) if refs else {}
    candidates = []
    for checkpoint, ref, tree in refs:
        if time.monotonic() >= deadline or len(candidates) >= 20:
            warnings.append("Entire preview stopped at its 45-second or 20-session limit. Select a returned checkpoint directly for a focused import.")
            break
        try:
            summary = _json(_blob(root, tree, "metadata.json"))
            if summary.get("checkpoint_id") != checkpoint or not isinstance(summary.get("sessions"), list):
                raise ValueError("Checkpoint ID or sessions manifest does not match the selected ref.")
            if len(summary["sessions"]) > 10:
                warnings.append(f"Checkpoint {checkpoint}: only the first 10 session slots are previewed.")
            for paths in summary["sessions"][:10]:
                if time.monotonic() >= deadline or len(candidates) >= 20:
                    warnings.append("Entire preview stopped at its 45-second or 20-session limit. Select a returned checkpoint directly for a focused import.")
                    break
                try:
                    if not isinstance(paths, dict):
                        raise ValueError("Invalid Entire session manifest entry.")
                    name, slot = _path(paths.get("metadata"), checkpoint, required_name="metadata.json")
                    if session_selection and slot != session_selection:
                        continue
                    metadata = _json(_blob(root, tree, name))
                    if metadata.get("checkpoint_id") != checkpoint or not isinstance(metadata.get("session_id"), str):
                        raise ValueError("Session metadata does not match its checkpoint.")
                    parsed = _transcript(root, tree, checkpoint, paths, metadata, slot)
                    linked = _commit_evidence(root, checkpoint, summary, metadata, trailers)
                    native_match = _match(parsed.get("repo_path"), repo_path)
                    if native_match == "unknown" and linked:
                        parsed["repo_path"] = root
                    elif native_match == "mismatch" and linked and Path(root).resolve() == Path(repo_path).resolve():
                        parsed["warnings"].append("Transcript path differs from this worktree; a locally reachable code commit establishes the repository association.")
                        parsed["repo_path"] = root
                    parsed["branch"] = metadata.get("branch") if isinstance(metadata.get("branch"), str) else parsed.get("branch")
                    parsed["created_at"] = metadata.get("created_at") if isinstance(metadata.get("created_at"), str) else parsed.get("created_at")
                    parsed["warnings"].append("Read from local Entire Git objects only. Transcript/summary statements are historical claims; imported anchors do not prove authorship. Commit trailer scan is limited to 400 commits across 50 code refs.")
                    if not linked:
                        parsed["warnings"].append("No locally reachable code commit association was verified for this checkpoint.")
                    source = _selector(root, checkpoint, slot)
                    session = _normalize(parsed, "entire", source, repo_path, title or f"Entire {checkpoint[:10]} · {metadata['session_id'][:32]}")
                    session["evidence"].extend(linked)
                    session["checkpoint"] = {"id": checkpoint, "ref": ref, "object": tree, "session_id": metadata["session_id"], "agent": metadata.get("agent"), "model": metadata.get("model"), "files_touched": metadata.get("files_touched", []), "commit_links": [item["metadata"] for item in linked]}
                    candidates.append(session)
                except (ValueError, RuntimeError, TypeError) as exc:
                    warnings.append(f"Checkpoint {checkpoint} session: {redact(str(exc))}")
        except (ValueError, RuntimeError, TypeError) as exc:
            warnings.append(f"Checkpoint {checkpoint}: {redact(str(exc))}")
    if session_selection and len(candidates) != 1:
        warnings.append("The selected Entire checkpoint session is missing or unsupported. Preview the repository again.")
    return {"candidates": candidates, "warnings": list(dict.fromkeys(warnings))}


def preview_entire(path: str, repo_path: str, title: str | None = None) -> dict:
    token = READ_DEADLINE.set(time.monotonic() + 45)
    try:
        return _preview_entire(path, repo_path, title)
    finally:
        READ_DEADLINE.reset(token)
