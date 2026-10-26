"""Explicit synthetic workspace. Never used as fallback for real integrations."""
from .db import now
from .inference import KEYS, TITLES, make_handoff


def demo_snapshot(repo_id, snapshot_id):
    stamp = "2026-10-23T16:20:00+00:00"
    evidence = [
        {"id": "demo-git", "kind": "git", "title": "Working tree at your stopping point", "body": "Branch fix/cache-invalidation at 7e91c4a. Staged: src/cache.ts. Unstaged: tests/cache.test.ts. Untracked filename: notes/repro.md. The diff replaces a shared cache key with a workspace-scoped key. No untracked file contents collected.", "source": "Synthetic Git fixture", "timestamp": stamp, "trust": "verified"},
        {"id": "demo-session", "kind": "session", "title": "Last coding session · cache invalidation", "body": "USER: Fix stale task lists when switching workspaces. Keep the public cache API unchanged.\nASSISTANT: A shared cache key causes workspace data to leak between views. The workspace-scoped key is implemented. I ran the old unit suite and it passed at that time. The switching-workspaces regression test is still unfinished.\nUSER: Do not repeat the global cache-clear approach; it breaks offline reads. Finish the regression test before changing anything else.", "source": "Synthetic agent conversation", "timestamp": stamp, "trust": "agent-reported"},
        {"id": "demo-base", "kind": "git", "title": "Main changed while you were away", "body": "Synthetic base branch moved from 42ad007 to b80cf19. src/storage.ts gained a storage schema version check. Review this change before rebasing the cache work.", "source": "Synthetic base comparison", "timestamp": "2026-10-24T08:10:00+00:00", "trust": "verified"},
    ]
    prs = []
    specs = [
        (42, "Scope cached task lists to the active workspace", "open", "fix/cache-invalidation", "CHANGES_REQUESTED", "Add a regression test that switches workspaces offline.", "FAILURE"),
        (43, "Add keyboard shortcuts to the task palette", "draft", "feat/keyboard-shortcuts", "REVIEW_REQUIRED", "Draft: waiting on focus-management coverage.", "PENDING"),
        (38, "Keep local task edits when reconnecting", "merged", "fix/offline-edits", "APPROVED", "Merged after the reconnect regression passed.", "SUCCESS"),
        (35, "Replace local storage with a remote-only cache", "closed", "experiment/remote-cache", "REVIEW_REQUIRED", "Closed without merge: offline support is a requirement.", "UNKNOWN"),
    ]
    for number, title, state, branch, review, body, check in specs:
        evidence_id = f"demo-pr-{number}"
        url = f"https://github.com/example/while-away-demo/pull/{number}"
        evidence.append({"id": evidence_id, "kind": "github", "title": f"PR #{number} · {state}", "body": f"SYNTHETIC PR #{number}: {title}. State: {state}. Review: {review}. CI: {check}. Reviewer: {body}", "source": "Synthetic GitHub fixture (links are illustrative)", "timestamp": stamp, "trust": "verified"})
        prs.append({"number": number, "title": title, "url": url, "state": state, "head_branch": branch, "base_branch": "main", "updated_at": stamp,
                    "review_state": review, "mergeability": "UNKNOWN" if state != "open" else "MERGEABLE", "checks": [{"name": "regression / cache", "status": "COMPLETED" if check != "PENDING" else "IN_PROGRESS", "conclusion": check}],
                    "reviews": [{"author": "demo-reviewer", "state": review, "body": body, "submitted_at": stamp}], "comments": [], "matches_branch": number == 42,
                    "changes": ["Review requested a regression test"] if number == 42 else [f"Now {state}"], "evidence_id": evidence_id})
    return {"id": snapshot_id, "repo_id": repo_id, "created_at": now(), "since": "2026-10-23T00:00:00+00:00",
            "git": {"root": "demo://northstar", "branch": "fix/cache-invalidation", "head": "7e91c4a", "upstream": "origin/fix/cache-invalidation", "remotes": [{"name": "origin", "url": "https://github.com/example/while-away-demo.git"}],
                    "worktrees": [{"path": "demo://northstar", "head": "7e91c4a", "branch": "fix/cache-invalidation"}], "staged": ["src/cache.ts"], "unstaged": ["tests/cache.test.ts"], "untracked": ["notes/repro.md"],
                    "commits": [{"sha": "7e91c4a", "author": "Demo developer", "timestamp": stamp, "subject": "Scope cache keys by workspace"}], "diff": "- const key = 'tasks';\n+ const key = `tasks:${workspaceId}`;", "base_branch": "main", "base_head": "b80cf19", "base_changes": ["src/storage.ts"], "warnings": [], "evidence": evidence[:1] + evidence[2:3]},
            "github": {"prs": prs, "synced_at": stamp, "offline": True, "error": None, "user": "demo-developer", "evidence": evidence[3:], "warnings": ["Synthetic cached PRs; illustrative links do not point to real PRs."]},
            "evidence": evidence, "warnings": ["DEMO: every repository, conversation, PR and check is synthetic. No model or credentials were used."]}


def demo_session():
    return {"id": "demo-session", "title": "Fix workspace cache invalidation", "adapter": "manual", "source": "Synthetic demonstration", "repo_path": "demo://northstar", "branch": "fix/cache-invalidation", "created_at": "2026-10-23T16:20:00+00:00",
            "messages": [{"role": "user", "text": "Finish the workspace-switch regression. Keep the cache API unchanged. Avoid global cache clearing; offline reads must continue working.", "timestamp": "2026-10-23T16:20:00+00:00"},
                         {"role": "assistant", "text": "Workspace-scoped keys are staged. The earlier suite passed then; the new regression is unfinished.", "timestamp": "2026-10-23T16:21:00+00:00"}], "warnings": ["Synthetic transcript; no real agent session imported."], "match": "matched", "evidence": []}


def demo_briefing(repo, snapshot, briefing_id):
    content = [
        [("Fixing stale task lists when switching workspaces, while keeping offline reads and the public cache API intact.", "agent-reported", ["demo-session"])],
        [("The workspace-scoped cache key is staged. The regression test still has uncommitted edits.", "verified", ["demo-git"]), ("Your agent reported that an earlier test run passed. The switching-workspaces regression was unfinished.", "agent-reported", ["demo-session"])],
        [("PR #38 merged, #43 remains a draft, and #35 closed without merging.", "verified", ["demo-pr-38", "demo-pr-43", "demo-pr-35"]), ("Main gained a storage schema version check in src/storage.ts.", "verified", ["demo-base"])],
        [("PR #42 is open with changes requested. The reviewer asked for an offline workspace-switching regression test; its cache check is failing.", "verified", ["demo-pr-42"])],
        [("Finish the workspace-switch regression in tests/cache.test.ts, then review the storage schema change before rebasing.", "suggestion", ["demo-git", "demo-pr-42", "demo-base"])],
    ]
    sections = [{"key": key, "title": title, "claims": [{"text": text, "kind": kind, "evidence_ids": ids} for text, kind, ids in claims]} for key, title, claims in zip(KEYS, TITLES, content)]
    return {"id": briefing_id, "repo_id": repo["id"], "snapshot_id": snapshot["id"], "created_at": now(), "model": "Synthetic demo · no inference", "demo": True, "sections": sections,
            "handoff": make_handoff(repo, snapshot, sections, snapshot["evidence"]), "evidence": snapshot["evidence"], "warnings": snapshot["warnings"]}
