"""Selected-source transcript adapters; native parsers support a documented subset."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Protocol

from .security import redact

MAX_FILE = 2_000_000
MAX_FILES = 50
MAX_TEXT = 120_000
MAX_MESSAGES = 400
SUPPORTED_SUFFIXES = {".jsonl", ".json", ".md", ".txt", ".markdown"}


class SessionAdapter(Protocol):
    name: str

    def parse(self, content: str) -> dict: ...


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces = []
        for part in content:
            if isinstance(part, str):
                pieces.append(part)
            elif isinstance(part, dict):
                if part.get("type") in ("text", "input_text", "output_text") and isinstance(part.get("text"), str):
                    pieces.append(part["text"])
                elif part.get("type") == "tool_use":
                    pieces.append("Historical tool invocation (not independently verified): " + str(part.get("name", "unknown")) + " " + json.dumps(part.get("input", {}), ensure_ascii=False))
                elif part.get("type") == "tool_result":
                    pieces.append("Historical tool output (not a current test result): " + _text(part.get("content", "")))
        return "\n".join(pieces)
    return ""


def _records(content: str) -> tuple[list[dict], list[str]]:
    records, malformed = [], 0
    for line in content.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            if isinstance(record, dict):
                records.append(record)
            else:
                malformed += 1
        except (ValueError, RecursionError):
            malformed += 1
    warnings = [f"Skipped {malformed} malformed or non-object JSONL records."] if malformed else []
    return records, warnings


class ManualAdapter:
    name = "manual"

    def parse(self, content: str) -> dict:
        stripped = content.lstrip()
        if stripped.startswith(("{", "[")):
            try:
                data = json.loads(content)
            except (ValueError, RecursionError) as exc:
                raise ValueError("Manual JSON must be valid JSON with a messages array. Choose text/Markdown for plain transcripts.") from exc
            if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
                raise ValueError('Unsupported manual JSON. Expected {"messages":[{"role":"user","text":"...","timestamp":null}],"repo_path":null,"branch":null}.')
            messages, warnings = [], []
            for entry in data["messages"]:
                if not isinstance(entry, dict) or entry.get("role") not in ("user", "assistant", "tool", "system") or not isinstance(entry.get("text"), str):
                    warnings.append("Skipped a manual message with an unsupported role or missing text.")
                    continue
                messages.append({"role": entry["role"], "text": entry["text"], "timestamp": entry.get("timestamp") if isinstance(entry.get("timestamp"), str) else None})
            return {"messages": messages, "repo_path": data.get("repo_path") if isinstance(data.get("repo_path"), str) else None, "branch": data.get("branch") if isinstance(data.get("branch"), str) else None, "created_at": data.get("created_at") if isinstance(data.get("created_at"), str) else None, "warnings": warnings}
        return {"messages": [{"role": "user", "text": content, "timestamp": None}], "repo_path": None, "branch": None, "created_at": None, "warnings": ["Plain text import: speaker roles and repository association require user review."]}


class CodexAdapter:
    name = "codex"

    def parse(self, content: str) -> dict:
        records, warnings = _records(content)
        metadata_rows = [row for row in records if row.get("type") == "session_meta" and isinstance(row.get("payload"), dict)]
        metadata = metadata_rows[0]["payload"] if metadata_rows else None
        if metadata is None:
            raise ValueError("Unsupported Codex session: missing verified session_meta envelope. Use manual text import.")
        if len(metadata_rows) > 1:
            raise ValueError("Multiple Codex session metadata records found. Select one session file.")
        if any(row.get("type") == "compacted" for row in records) or metadata.get("history") or metadata.get("forked_from_id"):
            warnings.append("Codex compaction, fork or referenced history detected. Only messages stored in this selected file are imported; full history reconstruction is unsupported.")
        messages, events, unknown = [], [], 0
        for row in records:
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            timestamp = row.get("timestamp") if isinstance(row.get("timestamp"), str) else None
            if row.get("type") == "response_item":
                kind = payload.get("type")
                if kind == "message" and payload.get("role") in ("user", "assistant"):
                    text = _text(payload.get("content"))
                    if text:
                        messages.append({"role": payload["role"], "text": text, "timestamp": timestamp})
                elif kind in ("function_call", "custom_tool_call"):
                    messages.append({"role": "tool", "text": "Historical tool invocation (not independently verified): " + str(payload.get("name", "unknown")) + " " + str(payload.get("arguments", payload.get("input", ""))), "timestamp": timestamp})
                elif kind in ("function_call_output", "custom_tool_call_output"):
                    text = _text(payload.get("output"))
                    if text:
                        messages.append({"role": "tool", "text": "Historical tool output (not a current test result): " + text, "timestamp": timestamp})
                elif kind not in ("reasoning", "compaction", "web_search_call"):
                    unknown += 1
            elif row.get("type") == "event_msg" and payload.get("type") in ("user_message", "agent_message") and isinstance(payload.get("message"), str):
                events.append({"role": "user" if payload["type"] == "user_message" else "assistant", "text": payload["message"], "timestamp": timestamp})
        if not messages:
            messages = events
        if unknown:
            warnings.append(f"Skipped {unknown} unsupported Codex response item types.")
        warnings.append("Codex native import supports the documented rollout subset; historical agent and tool statements are reported claims.")
        git = metadata.get("git") if isinstance(metadata.get("git"), dict) else {}
        return {"messages": messages, "repo_path": metadata.get("cwd") if isinstance(metadata.get("cwd"), str) else None, "branch": git.get("branch") if isinstance(git.get("branch"), str) else None, "created_at": metadata.get("timestamp") if isinstance(metadata.get("timestamp"), str) else None, "warnings": warnings}


class ClaudeAdapter:
    name = "claude"

    def parse(self, content: str) -> dict:
        records, warnings = _records(content)
        if any(row.get("isSidechain") for row in records):
            warnings.append("Claude sidechain records were omitted; only the selected main conversation is imported.")
            records = [row for row in records if not row.get("isSidechain")]
        conversational = [row for row in records if row.get("type") in ("user", "assistant") and isinstance(row.get("message"), dict)]
        session_ids = {row["sessionId"] for row in conversational if isinstance(row.get("sessionId"), str)}
        if len(session_ids) > 1:
            raise ValueError("Multiple Claude session IDs found. Select one session file.")
        by_id = {row["uuid"]: row for row in records if isinstance(row.get("uuid"), str)}
        if conversational and isinstance(conversational[-1].get("uuid"), str):
            active, visited, row = [], set(), conversational[-1]
            while row and row.get("uuid") not in visited:
                visited.add(row.get("uuid"))
                active.append(row)
                parent = row.get("parentUuid")
                if parent and parent not in by_id:
                    warnings.append("Claude parent chain is incomplete; earlier context may be unavailable.")
                row = by_id.get(parent)
            records = list(reversed(active))
            if len([row for row in records if row.get("type") in ("user", "assistant")]) < len(conversational):
                warnings.append("Claude fork/rewind detected; only the final recorded conversation branch is imported.")
        elif conversational:
            warnings.append("Claude UUID lineage unavailable; record order is used and fork/rewind support is unknown.")
        messages, metadata = [], None
        for row in records:
            if row.get("type") not in ("user", "assistant") or not isinstance(row.get("message"), dict):
                continue
            if not isinstance(row.get("sessionId"), str) or not isinstance(row.get("cwd"), str):
                warnings.append("Skipped Claude record without verified sessionId/cwd metadata.")
                continue
            metadata = metadata or row
            if row.get("isMeta") or row.get("isCompactSummary"):
                continue
            content = row["message"].get("content")
            text = _text(content)
            role = row["type"]
            if isinstance(content, list) and content and all(isinstance(part, dict) and part.get("type") in ("tool_result", "tool_use") for part in content):
                role = "tool"
            if text:
                messages.append({"role": role, "text": text, "timestamp": row.get("timestamp") if isinstance(row.get("timestamp"), str) else None})
        if metadata is None:
            raise ValueError("Unsupported Claude session: missing verified user/assistant message, sessionId and cwd fields. Import an /export text file instead.")
        warnings.append("Claude JSONL is an internal, version-sensitive format. Only the source-verified user/assistant subset is supported; /export text remains portable.")
        return {"messages": messages, "repo_path": metadata["cwd"], "branch": metadata.get("gitBranch") if isinstance(metadata.get("gitBranch"), str) else None, "created_at": metadata.get("timestamp") if isinstance(metadata.get("timestamp"), str) else None, "warnings": warnings}


ADAPTERS: dict[str, SessionAdapter] = {"manual": ManualAdapter(), "codex": CodexAdapter(), "claude": ClaudeAdapter()}


def _detect(content: str, suffix: str) -> str:
    records, _ = _records(content)
    if any(row.get("type") == "session_meta" for row in records):
        return "codex"
    if any(row.get("type") in ("user", "assistant") and isinstance(row.get("message"), dict) and "sessionId" in row for row in records):
        return "claude"
    if suffix == ".jsonl":
        raise ValueError("Unrecognized native JSONL format. No compatibility is claimed; choose manual text import after converting to text.")
    return "manual"


def _match(path: str | None, repository: str) -> str:
    if not path:
        return "unknown"
    try:
        claimed = Path(path).expanduser().resolve()
        selected = Path(repository).expanduser().resolve()
        return "matched" if claimed == selected or claimed.is_relative_to(selected) else "mismatch"
    except (ValueError, OSError):
        return "unknown"


def _normalize(parsed: dict, adapter: str, source: str, repository: str, title: str | None) -> dict:
    messages = parsed["messages"]
    if not messages:
        raise ValueError("No supported conversation messages were found.")
    warnings = list(dict.fromkeys(parsed["warnings"]))
    if len(messages) > MAX_MESSAGES:
        messages = messages[:10] + messages[-(MAX_MESSAGES - 10):]
        warnings.append("Long session limited to the first 10 and last 390 messages.")
    # Preserve the first goal and latest direction when the selected transcript is long.
    total = sum(len(item["text"]) for item in messages)
    if total > MAX_TEXT:
        first = {**messages[0], "text": messages[0]["text"][:10_000]}
        remaining, latest = MAX_TEXT - len(first["text"]), []
        for item in reversed(messages[1:]):
            if remaining <= 0:
                break
            excerpt = item["text"][-remaining:]
            latest.append({**item, "text": excerpt})
            remaining -= len(excerpt)
        messages = [first, *reversed(latest)]
        warnings.append("Session text limited to 120,000 characters, preserving the first goal and latest messages.")
    messages = [{**item, "text": redact(item["text"])} for item in messages]
    digest = hashlib.sha256(json.dumps([repository, source, adapter, messages], sort_keys=True).encode()).hexdigest()[:24]
    session_id = f"session-{digest}"
    evidence = []
    for index, message in enumerate(messages):
        evidence.append({"id": f"{session_id}-{index}", "kind": "session-message", "title": f"{adapter.title()} · {message['role']} · message {index + 1}", "body": message["text"], "source": redact(source), "timestamp": message["timestamp"], "trust": "user-provided" if message["role"] == "user" else "agent-reported", "metadata": {"session_id": session_id, "role": message["role"], "historical": True}})
    return {"id": session_id, "title": redact(title or next((item["text"].splitlines()[0][:100] for item in messages if item["role"] == "user" and item["text"].strip()), Path(source).name)), "adapter": adapter, "source": redact(source), "repo_path": parsed.get("repo_path"), "branch": parsed.get("branch"), "created_at": parsed.get("created_at"), "messages": messages, "warnings": warnings, "match": _match(parsed.get("repo_path"), repository), "evidence": evidence}


def _read_file(path: Path, boundary: Path | None = None) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    if os.open in os.supports_dir_fd and hasattr(os, "O_NOFOLLOW"):
        # Walk through directory descriptors so swapped parent symlinks cannot escape selection.
        boundary = boundary or path.parent
        expected = boundary.stat(follow_symlinks=False)
        directory = os.open(boundary, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            actual = os.fstat(directory)
            if (expected.st_dev, expected.st_ino) != (actual.st_dev, actual.st_ino):
                raise ValueError("Selected session directory changed during import.")
            for part in path.relative_to(boundary).parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
            descriptor = os.open(path.name, flags, dir_fd=directory)
        finally:
            os.close(directory)
    else:
        # shortcut: Windows lacks POSIX directory-descriptor guards; native imports require POSIX.
        raise ValueError("Native filesystem transcript import requires macOS/Linux; paste text on this platform.")
    with os.fdopen(descriptor, "rb") as handle:
        import stat
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("Session source must be a regular file.")
        content = handle.read(MAX_FILE + 1)
    if len(content) > MAX_FILE:
        raise ValueError("Session files are limited to 2 MB each.")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Session files must be UTF-8 text.") from exc


def preview_sessions(path: str | None, text: str | None, format: str, repo_path: str, title: str | None = None) -> dict:
    if format == "entire":
        if not path or text:
            raise ValueError("Entire import requires an explicitly selected local repository path or previewed checkpoint selector.")
        from .entire import preview_entire
        return preview_entire(path, repo_path, title)
    if format not in ("auto", *ADAPTERS):
        raise ValueError("Unsupported transcript adapter.")
    if bool(path) == bool(text):
        raise ValueError("Select one session file/directory or paste transcript text.")
    candidates, warnings, inputs = [], [], []
    if text:
        if len(text.encode()) > MAX_FILE:
            raise ValueError("Pasted transcripts are limited to 2 MB.")
        inputs.append(("Pasted transcript", text, ""))
    else:
        selected = Path(path).expanduser().absolute()
        if selected.is_symlink() or any(parent.is_symlink() for parent in selected.parents if parent != Path("/")):
            raise ValueError("Choose a real session path; symlink sources are not imported.")
        selected = selected.resolve()
        if not selected.exists():
            raise ValueError("Session source does not exist.")
        if selected.is_dir():
            files, visited, entries, pending = [], 0, 0, [selected]
            while pending:
                directory = pending.pop()
                visited += 1
                try:
                    with os.scandir(directory) as listing:
                        for entry in listing:
                            entries += 1
                            candidate = Path(entry.path)
                            if entry.is_dir(follow_symlinks=False) and not entry.name.startswith("."):
                                pending.append(candidate)
                            elif entry.is_file(follow_symlinks=False) and candidate.suffix.lower() in SUPPORTED_SUFFIXES:
                                files.append(candidate)
                            if len(files) == MAX_FILES or entries >= 5000:
                                break
                except OSError:
                    warnings.append(f"Cannot read selected subdirectory: {redact(str(directory))}")
                if len(files) == MAX_FILES or visited >= 500 or entries >= 5000:
                    warnings.append("Directory preview limited to 50 files, 500 directories and 5,000 entries. Select a narrower directory for more sessions.")
                    break
            files.sort()
        else:
            files = [selected]
        for file in files:
            try:
                inputs.append((str(file), _read_file(file, selected if selected.is_dir() else selected.parent), file.suffix.lower()))
            except (OSError, ValueError) as exc:
                warnings.append(f"{redact(file.name)}: {redact(str(exc))}")
    for source, content, suffix in inputs:
        try:
            adapter = _detect(content, suffix) if format == "auto" else format
            parsed = ADAPTERS[adapter].parse(content)
            candidates.append(_normalize(parsed, adapter, source, repo_path, title))
        except (ValueError, RecursionError) as exc:
            warnings.append(f"{redact(Path(source).name)}: {redact(str(exc))}")
    return {"candidates": candidates, "warnings": warnings}
