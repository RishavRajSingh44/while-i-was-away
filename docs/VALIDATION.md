# Validation record

Observed October 26, 2026 on macOS Apple arm64, 48 GiB RAM, Python 3.11 virtual environment, Node 24.19 bundled runtime for one inspection and local npm/Vite 6.3.5 for builds. All tests use application fixtures or temporary Git repositories; none executes tests inside a user's selected repository.

| Check | Actual result |
|---|---|
| `.venv/bin/python -m pytest -q` | **73 passed, 1 third-party deprecation warning** in 14.71 s from a clean archive extraction. Temporary Git states, worktrees, snapshots, four PR states, pagination, offline fallback, native and Entire imports, exact commit-to-PR association, redaction, endpoint origin, citations, queue cancellation/recovery, handoff and deletion covered. |
| `.venv/bin/ruff check backend tests scripts` | Passed. |
| `npm --prefix frontend run typecheck` | Passed. |
| `npm --prefix frontend run lint` | Passed. |
| `npm --prefix frontend run test` | **11 passed** across 3 files. |
| `npm --prefix frontend run build` and `build:demo` | Both passed on the final code; local and static bundles generated. |
| `npm --prefix frontend run test:e2e` with production local server | **2 passed, 1 public-only skipped.** Covered demo onboarding, citations, editable/exported handoff, all PR categories, sessions, refresh, explicit acknowledgment, history and mobile overflow. Captures in [screenshots](screenshots/). Initial attempt failed because the server had started before `dist/` existed; restarted server with built assets and reran successfully. |
| `AWAY_PUBLIC_DEMO=1 AWAY_E2E_URL=http://127.0.0.1:4183 npm --prefix frontend run test:e2e` against static preview | **1 passed, 2 local-only skipped.** It recorded zero `/api` requests and checked synthetic replay, evidence, handoff redaction and disabled file/remote controls. |
| `.venv/bin/python scripts/verify_model.py gemma3:4b` | **Passed, real Ollama inference** in 39.605 s on temporary synthetic Git, four PR fixtures and a synthetic manual agent transcript. Ollama 0.40.5, `gemma3:4b` digest `68ceab7e468a…`, all five cited sections and handoff in [evidence](evidence/gemma-run.json). The prior run wrongly prioritized PR #42 CI. After requiring the next step to cite the latest selected user direction, this run said to finish the offline regression and avoid global cache clearing, matching that source. The model still placed the historical user goal under “What changed,” although that source does not establish a change during the window; semantic accuracy remains a human review task. |
| `sync_github` against an accessible PR-history repository using a disposable local Git remote | Authenticated read-only sync succeeded with `offline=false`, `error=null`, **23 authored merged PRs**. No PRs or local source were changed. Authenticated searches found **0 open, 0 draft and 0 closed-unmerged authored PRs** across the account; those states and pagination remain fixture-tested, not live-verified. The earlier selected BountyPilot remote returned 0 authored PRs. |
| `ollama list` | Confirmed installed Gemma 3 4B after explicit 3.4 GB download. Earlier Qwen models were present but are not the app default. |
| Entire checkpoint synthetic test | A temporary Git repository with checkpoint refs passed importer tests. Current upstream is MIT-licensed `v0.12.2` / `9287126`; the adapter is pinned to an earlier implementation revision. No Entire executable was installed, so current-tool compatibility remains experimental. No personal build session was read. |
| Clean archive install and launch | Explicit source-only archive extracted in a new temporary directory. `python3.11 -m venv .venv`, locked `pip install`, `npm ci`, 73 backend tests and both frontend builds passed. The production launcher served `/` and `/api/settings` with HTTP 200; development mode served Vite `/` and backend `/api/health` with HTTP 200. |

## Independent review and fixes

The Ponytail review pass identified two concrete release issues. JSON-quoted secret keys such as `{"password":"..."}` were not redacted; `security.redact` now handles quoted/env credential forms and regression tests cover them. Model prose marked `verified` could have cited an unrelated verified source; the final briefing now labels free-form model prose as suggestion/interpretation, while application-generated Git and PR field lines alone receive the verified label. Citations establish traceability, not semantic proof. Reviewer evidence was reproduced in tests. The installed Ponytail review workflow was read and followed.

## Remaining limits and external results

GitHub Actions has not run remotely; there is no authorized public push. Render is prepared but not deployed, and no `.tech` domain or public demo URL exists. Windows/Linux have not been browser tested. Gemma quality has one measured latest synthetic run, not a performance distribution; citations validate source presence and the latest-direction rule, not arbitrary prose entailment. Consented, individually selected real Codex/Claude files were not provided for this release pass, so native formats remain source-and-fixture-tested only. Long/legacy Entire variants remain visibly unsupported. The challenge deadline passed at October 26 06:59 UTC without publication or submission, so this material is not an on-time entry.
