"""Bounded, read-only Git facts. Fetch is a separate explicit operation."""
from __future__ import annotations

import fnmatch
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import time
from datetime import datetime

from .security import redact

MAX_OUTPUT = 2_000_000
MAX_DIFF = 60_000
DEFAULT_EXCLUSIONS = [".env*", "*.pem", "*.key", "*credentials*", "*secret*", ".ssh", "node_modules", ".git", "vendor", "dist", "build", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"]


def run_command(args: list[str], cwd: str | None = None, timeout: int = 20, limit: int = MAX_OUTPUT) -> str:
    """Spool subprocess output with a byte/deadline cap, including noisy failures."""
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "GH_PROMPT_DISABLED": "1", "GH_HOST": "github.com", "GH_PAGER": "cat", "PAGER": "cat"}
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        try:
            process = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=errors)
        except OSError as exc:
            raise RuntimeError(f"Cannot start {Path(args[0]).name}; check installation and permissions.") from exc
        deadline = time.monotonic() + timeout
        failure = None
        while process.poll() is None:
            if time.monotonic() > deadline:
                failure = "Command timed out."
            if os.fstat(output.fileno()).st_size + os.fstat(errors.fileno()).st_size > limit:
                failure = "Command output exceeds the collection limit."
            if failure:
                process.kill()
                process.wait()
                raise RuntimeError(failure)
            time.sleep(0.02)
        if os.fstat(output.fileno()).st_size + os.fstat(errors.fileno()).st_size > limit:
            raise RuntimeError("Command output exceeds the collection limit.")
        output.seek(0)
        errors.seek(0)
        if process.returncode:
            message = errors.read(min(limit, 2000)).decode("utf-8", "replace").strip()
            raise RuntimeError(redact(message) or f"{Path(args[0]).name} exited with status {process.returncode}.")
        return output.read(limit).decode("utf-8", "replace")


def _git(root: str, *args: str, timeout: int = 20) -> str:
    return run_command(["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-c", "core.pager=cat", "-c", "color.ui=false", "-C", root, *args], timeout=timeout)


def _optional(root: str, *args: str) -> str | None:
    try:
        return _git(root, *args).strip() or None
    except RuntimeError:
        return None


def _evidence(kind: str, title: str, body: str, source: str, timestamp: str | None = None, **metadata) -> dict:
    body, source, title = redact(body), redact(source), redact(title)
    digest = hashlib.sha256(f"{kind}\0{source}\0{body}".encode()).hexdigest()[:20]
    return {"id": f"git-{kind}-{digest}", "kind": kind, "title": title, "body": body, "source": source, "timestamp": timestamp, "trust": "verified", "metadata": metadata}


def _worktrees(root: str) -> list[dict]:
    worktrees, current = [], {}
    for field in _git(root, "worktree", "list", "--porcelain", "-z").split("\0"):
        if not field:
            if current:
                worktrees.append(current)
                current = {}
            continue
        key, _, value = field.partition(" ")
        if key == "worktree":
            current["path"] = value
            current.update(head=None, branch=None)
        elif key == "HEAD":
            current["head"] = value
        elif key == "branch":
            current["branch"] = value.removeprefix("refs/heads/")
    if current:
        worktrees.append(current)
    return worktrees


def discover_repo(path: str) -> dict:
    if not isinstance(path, str) or not path.strip() or "\0" in path:
        raise ValueError("Choose an existing repository directory.")
    selected = Path(path).expanduser().resolve()
    if not selected.is_dir():
        raise ValueError("Repository path must be an existing directory.")
    try:
        root = _git(str(selected), "rev-parse", "--show-toplevel").removesuffix("\n")
    except RuntimeError as exc:
        raise ValueError("This path is not inside a Git working tree.") from exc
    branch = _optional(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    remotes = []
    for name in (_optional(root, "remote") or "").splitlines()[:20]:
        url = _optional(root, "remote", "get-url", name)
        if url:
            # Remote URLs occasionally contain embedded HTTPS credentials.
            from urllib.parse import urlsplit, urlunsplit
            if "://" in url:
                parts = urlsplit(url)
                url = urlunsplit((parts.scheme, parts.hostname or "", parts.path, "", ""))
            remotes.append({"name": name, "url": redact(url)})
    return {"root": root, "name": Path(root).name, "branch": branch, "head": _optional(root, "rev-parse", "--verify", "HEAD"), "upstream": _optional(root, "rev-parse", "--abbrev-ref", "@{upstream}"), "remotes": remotes, "worktrees": _worktrees(root)}


def _excluded(name: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) or any(fnmatch.fnmatch(part, pattern) for part in Path(name).parts) for pattern in patterns)


def collect_git(path: str, since: str, previous: dict | None = None, exclusions: list[str] | None = None) -> dict:
    try:
        parsed = datetime.fromisoformat(since.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise ValueError("The collection window must be an ISO timestamp with a timezone.") from exc
    context = discover_repo(path)
    context.pop("name")
    root = context["root"]
    warnings, staged, unstaged, untracked = [], [], [], []
    records = iter(_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0"))
    for record in records:
        if not record:
            continue
        status, name = record[:2], record[3:]
        if "R" in status or "C" in status:
            next(records, None)  # NUL porcelain places the destination before the original.
        if status == "??":
            untracked.append(name)
        else:
            if status[0] != " ":
                staged.append(name)
            if status[1] != " ":
                unstaged.append(name)
    commits = []
    if context["head"]:
        for line in _git(root, "log", "-n", "80", f"--since={parsed.isoformat()}", "--format=%H%x00%an%x00%aI%x00%s").splitlines():
            fields = line.split("\0", 3)
            if len(fields) == 4:
                commits.append(dict(zip(["sha", "author", "timestamp", "subject"], fields)))
        if len(commits) == 80:
            warnings.append("Recent commits are limited to 80 entries.")
    else:
        warnings.append("This repository has no commits yet.")
    if not context["branch"]:
        warnings.append("Detached HEAD: no current branch name.")
    if _optional(root, "rev-parse", "--is-shallow-repository") == "true":
        warnings.append("Shallow clone: earlier history may be unavailable.")
    patterns = DEFAULT_EXCLUSIONS + (exclusions or [])
    modes = {entry.split("\t", 1)[1]: entry.split(" ", 1)[0] for entry in _git(root, "ls-files", "--stage", "-z").split("\0") if "\t" in entry}
    diff_parts, skipped, size = [], 0, 0
    changed_files = list(dict.fromkeys(staged + unstaged))
    for name in changed_files[:80]:
        local = Path(root) / name
        symlink_path = any((Path(root).joinpath(*Path(name).parts[:index])).is_symlink() for index in range(1, len(Path(name).parts) + 1))
        if _excluded(name, patterns) or modes.get(name) == "120000" or symlink_path or not local.resolve().is_relative_to(Path(root).resolve()):
            skipped += 1
            continue
        for cached in (True, False):
            if name not in (staged if cached else unstaged):
                continue
            try:
                piece = _git(root, "--literal-pathspecs", "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--unified=3", *(["--cached"] if cached else []), "--", name)
            except RuntimeError as exc:
                warnings.append(f"Diff omitted for {redact(name)}: {exc}")
                continue
            remaining = MAX_DIFF - size
            diff_parts.append(("STAGED\n" if cached else "UNSTAGED\n") + piece[:remaining])
            size += min(len(piece), remaining)
            if len(piece) > remaining:
                warnings.append("Diff evidence truncated at 60,000 characters.")
            if size >= MAX_DIFF:
                break
        if size >= MAX_DIFF:
            break
    if skipped:
        warnings.append(f"Diff contents omitted for {skipped} excluded or symlink paths.")
    if len(changed_files) > 80:
        warnings.append("Diff collection limited to 80 changed files.")
    base = _optional(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if not base:
        for candidate in ("origin/main", "origin/master", "main", "master"):
            if _optional(root, "rev-parse", "--verify", f"{candidate}^{{commit}}"):
                base = candidate
                break
    base_head = _optional(root, "rev-parse", "--verify", f"{base}^{{commit}}") if base else None
    previous_git = (previous or {}).get("git", previous or {})
    base_changes = []
    if previous_git.get("base_head") and base_head:
        previous_base = previous_git["base_head"]
        if isinstance(previous_base, str) and len(previous_base) in (40, 64) and all(c in "0123456789abcdef" for c in previous_base):
            try:
                base_changes = [item for item in _git(root, "diff", "--name-only", "-z", previous_base, base_head, "--").split("\0") if item][:500]
            except RuntimeError:
                warnings.append("Previous base revision is unavailable locally; base changes are unknown.")
    elif previous_git and not base_head:
        warnings.append("Base branch unavailable; changes since the snapshot are unknown.")
    context.update(staged=staged, unstaged=unstaged, untracked=untracked, commits=commits, diff=redact("\n".join(diff_parts)), base_branch=base, base_head=base_head, base_changes=base_changes, warnings=warnings)
    summary = f"Root: {root}\nBranch: {context['branch'] or 'detached'}\nHEAD: {context['head'] or 'unborn'}\nUpstream: {context['upstream'] or 'none'}\nStaged: {staged}\nUnstaged: {unstaged}\nUntracked names only: {untracked}\nBase branch: {base or 'unknown'}\nBase changed paths: {base_changes}"
    evidence = [_evidence("working-tree", "Current working tree", summary, root)]
    if context["diff"]:
        evidence.append(_evidence("diff", "Staged and unstaged changes", context["diff"], root))
    evidence.extend(_evidence("commit", item["subject"], f"Commit {item['sha']} by {item['author']} at {item['timestamp']}: {item['subject']}", root, item["timestamp"], sha=item["sha"]) for item in commits)
    context["evidence"] = evidence
    return context


def fetch_refs(path: str) -> None:
    root = discover_repo(path)["root"]
    # Explicit user action only. Never prune, recurse into submodules, or modify working files.
    _git(root, "-c", "protocol.ext.allow=never", "fetch", "--no-recurse-submodules", "--no-write-fetch-head", "--all", timeout=90)
