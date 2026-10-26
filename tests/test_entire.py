import json
import os
from pathlib import Path
import subprocess

import pytest

from away.sessions import preview_sessions

CHECKPOINT = "01JAPQ3GZP8K7J6H5F4D3S2A1B"


def git(root, *args, text=None):
    env = {**os.environ, "GIT_AUTHOR_NAME": "Synthetic Developer", "GIT_COMMITTER_NAME": "Synthetic Developer", "GIT_AUTHOR_EMAIL": "synthetic@example.invalid", "GIT_COMMITTER_EMAIL": "synthetic@example.invalid"}
    result = subprocess.run(["git", "-C", str(root), *args], input=text, capture_output=True, text=True, check=True, env=env)
    return result.stdout.strip()


def write_blob(root, value):
    return git(root, "hash-object", "-w", "--stdin", text=value)


def make_checkpoint(root, *, agent="codex", anchor=None, legacy_paths=False, raw=True, unsafe_prompt=False, symlink_metadata=False):
    fixture = Path(__file__).parent / "fixtures" / f"session-{agent}.jsonl"
    transcript = fixture.read_text().replace("/synthetic/projects/quiet-queue", str(root))
    metadata = {"checkpoint_id": CHECKPOINT, "session_id": "synthetic-session", "strategy": "manual-commit", "created_at": "2026-10-24T10:00:00Z", "agent": "Codex" if agent == "codex" else "Claude Code", "model": "synthetic-model", "branch": "main", "files_touched": ["retry.py"], "summary": {"intent": "Repair the retry boundary", "outcome": "Still investigating", "learnings": {"repo": ["Keep the public interface"], "code": [], "workflow": []}, "friction": ["First clamp approach failed"], "open_items": ["Inspect negative input before choosing a fix"]}}
    if anchor:
        metadata["commit_sha"] = anchor
    slot_entries = [f"{'120000' if symlink_metadata else '100644'} blob {write_blob(root, json.dumps(metadata))}\tmetadata.json", f"100644 blob {write_blob(root, 'Repair the retry boundary. Keep the public interface.')}\tprompt.txt"]
    if raw:
        slot_entries.append(f"100644 blob {write_blob(root, transcript)}\tfull.jsonl")
    slot_tree = git(root, "mktree", text="\n".join(slot_entries) + "\n")
    prefix = f"/{CHECKPOINT[:2]}/{CHECKPOINT[2:]}/" if legacy_paths else ""
    paths = {"metadata": prefix + "1/metadata.json", "prompt": "../../private.txt" if unsafe_prompt else prefix + "1/prompt.txt"}
    if raw:
        paths["transcript"] = prefix + "1/full.jsonl"
    summary = {"checkpoint_id": CHECKPOINT, "strategy": "manual-commit", "sessions": [paths]}
    tree = git(root, "mktree", text=f"100644 blob {write_blob(root, json.dumps(summary))}\tmetadata.json\n040000 tree {slot_tree}\t1\n")
    checkpoint_commit = git(root, "commit-tree", tree, "-m", "Synthetic Entire checkpoint")
    git(root, "update-ref", f"refs/entire/checkpoints/{CHECKPOINT[-2:]}/{CHECKPOINT}", checkpoint_commit)
    return checkpoint_commit


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "retry.py").write_text("def retry(): return 0\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "Initial synthetic work")
    return tmp_path


@pytest.mark.parametrize("agent", ["codex", "claude"])
def test_entire_ref_original_goal_last_exchange_and_verified_commit_link(repository, agent):
    git(repository, "commit", "--allow-empty", "-m", "Checkpoint-linked synthetic work", "-m", f"Entire-Checkpoint: {CHECKPOINT}")
    code_head = git(repository, "rev-parse", "HEAD")
    checkpoint_object = make_checkpoint(repository, agent=agent, legacy_paths=True)
    before = git(repository, "status", "--porcelain=v1", "-z")
    refs_before = git(repository, "for-each-ref", "--format=%(refname) %(objectname)")
    result = preview_sessions(str(repository), None, "entire", str(repository))
    assert result["warnings"] == []
    session = result["candidates"][0]
    assert session["adapter"] == "entire" and session["match"] == "matched"
    assert session["checkpoint"]["object"] == checkpoint_object
    assert session["messages"][0]["role"] == "user"
    assert "retry" in session["messages"][0]["text"].lower()
    assert any("Keep the public interface" in message["text"] for message in session["messages"])
    assert any("negative" in message["text"].lower() for message in session["messages"])
    commits = [item for item in session["evidence"] if item["kind"] == "entire-code-commit"]
    assert len(commits) == 1 and commits[0]["metadata"]["sha"] == code_head
    assert commits[0]["trust"] == "verified"
    assert all(item["trust"] != "verified" for item in session["evidence"] if item["kind"] == "session-message")
    selected = preview_sessions(session["source"], None, "entire", str(repository))
    assert len(selected["candidates"]) == 1 and selected["candidates"][0]["id"] == session["id"]
    assert git(repository, "status", "--porcelain=v1", "-z") == before
    assert git(repository, "for-each-ref", "--format=%(refname) %(objectname)") == refs_before
    assert not (repository / ".entire").exists()


def test_import_anchor_is_not_attribution_and_missing_transcript_is_explicit(repository):
    make_checkpoint(repository, anchor=git(repository, "rev-parse", "HEAD"), raw=False)
    session = preview_sessions(str(repository), None, "entire", str(repository))["candidates"][0]
    assert session["match"] == "matched"
    assert any("Last exchange is unknown" in warning for warning in session["warnings"])
    commit = next(item for item in session["evidence"] if item["kind"] == "entire-code-commit")
    assert "not attribution" in commit["body"]
    assert session["messages"][0]["role"] == "user"


def test_unreachable_anchor_does_not_establish_association(repository):
    make_checkpoint(repository, anchor="a" * 40, raw=False)
    session = preview_sessions(str(repository), None, "entire", str(repository))["candidates"][0]
    assert session["match"] == "unknown"
    assert not any(item["kind"] == "entire-code-commit" for item in session["evidence"])


def test_unsafe_paths_and_git_symlink_metadata_are_rejected(repository):
    make_checkpoint(repository, unsafe_prompt=True)
    session = preview_sessions(str(repository), None, "entire", str(repository))["candidates"][0]
    assert any("unsafe" in warning.lower() for warning in session["warnings"])
    make_checkpoint(repository, symlink_metadata=True)
    result = preview_sessions(str(repository), None, "entire", str(repository))
    assert result["candidates"] == []
    assert any("regular Git blob" in warning for warning in result["warnings"])


def test_no_refs_and_invalid_selector_do_not_scan_private_sessions(repository):
    result = preview_sessions(str(repository), None, "entire", str(repository))
    assert result["candidates"] == []
    assert any("No supported local Entire" in warning for warning in result["warnings"])
    with pytest.raises(ValueError, match="Invalid Entire"):
        preview_sessions(f"entire:{repository}?checkpoint=../../secrets&session=1", None, "entire", str(repository))
    with pytest.raises(ValueError, match="requires"):
        preview_sessions(None, "some text", "entire", str(repository))
