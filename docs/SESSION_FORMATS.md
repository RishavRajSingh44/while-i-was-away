# Session format contracts

Native session storage is not a permanent public interchange format. These adapters support a tested subset at the source revisions below; unknown metadata may be skipped with a visible warning. Manual Markdown/text/JSON import is the fallback. The synthetic fixtures were authored for this app from verified field shapes, with invented paths, UUIDs, times, messages and tool outputs. They do not contain real user conversations or copied upstream fixture prose.

## Codex plain JSONL

Pinned [OpenAI source](https://github.com/openai/codex/tree/970111f6cb62cc02fe36a82ea7d71b37a2889c97): `codex-rs/history/src/lib.rs` defines `RolloutLine` with `timestamp`, optional `ordinal`, and flattened item; `history/src/rollout_payload.rs` defines tagged records with `type` and `payload`. The `response_item` variant stores its metadata separately from its message payload.

`protocol/src/protocol.rs` defines `SessionMetaLine` / `SessionMeta`: `id`, `session_id`, `cwd`, `cli_version`, `timestamp`, optional Git metadata and history metadata. The fixture uses `git.branch`, `commit_hash`, and `repository_url` as hints. `protocol/src/models.rs` defines `ResponseItem::Message` with `role`, `content`, and optional phase; text content uses `input_text` or `output_text`. Only visible user/assistant text is a conversation excerpt; reasoning/encrypted payloads and executable tool arguments are not instructions for this app.

Fixture: `tests/fixtures/session-codex.jsonl`. It represents a legacy, self-contained rollout. Compressed `.jsonl.zst`, paginated referenced history, remote sessions, and reconstruction of fork/compaction history are unsupported. A partially readable file must not be described as a complete conversation. The latest `cwd` may be a subdirectory/worktree, not the repository root. Canonical path checks and explicit selection establish association, not filename inference.

## Claude Code plain JSONL

[Official sessions docs](https://code.claude.com/docs/en/sessions) confirm local `.jsonl` storage beneath `~/.claude/projects/`, configurable storage/retention, and plain-text `/export`. They expressly describe native entries as internal and release-dependent. The [hooks reference](https://code.claude.com/docs/en/hooks) exposes `transcript_path` and `cwd`; the app does not install hooks or invoke Claude.

The primary format evidence is [Anthropic SDK source](https://github.com/anthropics/claude-agent-sdk-python/tree/0e89b298e771259378a6cd3734e00d323dff5703), `src/claude_agent_sdk/_internal/sessions.py` and `tests/test_sessions.py`. Their native records use `type`, `uuid`, `parentUuid`, `sessionId`, `message.role` and `message.content`, with path/time/branch hints. Content may be a string or typed blocks. `text` is readable text; `tool_result` is tool evidence, not a human request. `isMeta`, `isCompactSummary`, sidechains and parent links carry semantics that a linear parser must not silently flatten into user intent.

Fixture: `tests/fixtures/session-claude.jsonl`. This is a single chronological parent chain. Branched/rewound sessions need explicit unsupported/partial warnings unless the parser reconstructs the active chain. No encoded folder name is decoded into an authoritative path. Missing path hints require user association; a known mismatched repository must never be silently attached.

## Manual import and hostile contents

Manual formats are this application's own documented contract: Markdown/plain text, or the supported JSON message list/envelope exposed in the import UI. An arbitrary JSON object is not automatically a supported transcript. Malformed records, oversize files, unreadable sources and symlink escape attempts must produce errors or explicit partial warnings.

`tests/fixtures/session-prompt-injection.jsonl` contains intentionally malicious conversational text. Its fake instructions must remain quoted source material; they must never change the synthesis prompt, execute a command, invent evidence, or become verified facts. Historical test output is historical; an assistant completion statement remains an agent-reported claim. All extracted claims retain source evidence identifiers and timestamps when present.

## Entire local checkpoint refs

At pinned [Entire CLI commit `d05c0a1`](https://github.com/entireio/cli/tree/d05c0a14437fdc071ed97655ec41046018bd8d2e), current checkpoint refs have the form `refs/entire/checkpoints/<last-two-ID-characters>/<checkpoint-ID>`. A checkpoint tree contains `metadata.json` and numbered session directories. The importer validates the manifest, reads only regular Git blobs under accepted names, and caps checkpoints, sessions, blob sizes and elapsed time. It reads the supported `full.jsonl` native Codex/Claude transcript through the verified adapters, and can fall back to stored `prompt.txt`/summary with an explicit “last exchange unknown” warning. No hook, fetch, checkout or upload is performed.

The UI previews candidate checkpoints from a selected repository and imports one selected session. A native `cwd` path establishes a match; a locally reachable code commit linked in Entire metadata or an `Entire-Checkpoint` trailer can establish repository association. A metadata import anchor alone establishes reachability, not authorship. Commit IDs, timestamps and trailer links are evidence; agent summaries remain reported claims. A PR link is shown only when an Entire code commit SHA exactly matches GitHub's authoritative current PR head SHA; an older linked commit or same-named branch stays unassociated. The synthetic [Entire tests](../tests/test_entire.py) construct real Git checkpoint refs, verify read-only operation and cover unsafe tree paths, symlinks, unsupported transcripts and missing links. Entire CLI was not installed for this build, so no real personal build session was recorded or published.

Known boundary: older `entire/checkpoints/v1` storage and compressed/chunked raw transcripts need a separately researched adapter. The app shows the unsupported state and retains manual export/import.

Current upstream `main` was checked read-only on October 26 at [`9287126`](https://github.com/entireio/cli/tree/9287126c22fbe20de41954a1010ab9eff24ad074), with latest release `v0.12.2` and MIT license. This adapter remains pinned to the earlier source revision above. The current Entire tool was unavailable locally, so no tool-produced checkpoint was imported. Native Entire compatibility is **experimental** until one passes an actual-tool contract test.

## Maintenance

Before expanding native support, pin the new upstream revision, inspect serialization/parser source, add an original sanitized contract fixture, and add a regression test. Do not claim compatibility solely because a permissive JSON parser accepts a file. Consult REFERENCES.md for licenses; no upstream parser source is bundled.
