# While I Was Away — implementation plan

Integration owner: primary agent. All files live in this separate directory; existing BountyPilot files and data are out of scope. No publication, push, submission or repository mutations during collection.

## Scope and sequence

- [x] Inspect workspace, applicable AGENTS.md, Ponytail 5.3.2 and REA skill. Preserve existing dirty work.
- [x] Research official references, pin versions, verify native transcript contracts and challenge rules.
- [x] Build React/TypeScript/Vite client and FastAPI/SQLite server with an explicit synthetic demo.
- [x] Implement bounded read-only Git collection, explicit snapshots and acknowledgment checkpoints.
- [x] Implement authenticated GitHub synchronization, four PR categories and visible offline cache; live selected repository returned zero authored PRs, so categories were verified with contract fixtures.
- [x] Implement selected-file session preview/import with manual, verified Codex, Claude and Entire adapters.
- [x] Implement local Ollama structured extraction/synthesis, citation validation, persistent queue, cancellation/recovery and cache.
- [x] Integrate editable handoff, evidence drawer, history, repository switcher and deletion controls.
- [x] Verify security boundaries, automated contracts, available live integrations, browser demo and screenshots; Windows/Linux and private native transcripts remain unverified.
- [x] Independently review, resolve findings, finish README, notices, submission draft and validation log.

## Ownership and coordination

Primary: API contract, SQLite/migrations, server routes, security, inference, jobs, demo seed, integration, launch scripts and final documentation.
Integration agent: `backend/away/git_context.py`, `github.py`, `sessions.py` and their focused tests.
Frontend agent: `frontend/`, frontend tests, browser tests and frontend configuration only.
Reference agent: `docs/REFERENCES.md`, `docs/SESSION_FORMATS.md`, `docs/CHALLENGE_RULES.md` and sanitized native-session fixtures. Reassigned to independent review after research.

Shared contract is in API_CONTRACT.md. Agents propose contract changes to the primary before relying on them. No agent edits another owner's files without coordination.

## Plan review before implementation

The proposed stack matches the requested local-first architecture and has no mandatory hosted services. One SQLite database, one worker, and one backend serving the built frontend are sufficient for a single local user. Git and gh are subprocess adapters using argument arrays; Ollama is a loopback HTTP adapter. Imported text is untrusted evidence. Model citations are validated against collected IDs; deterministic facts retain their original source. Generation never advances the acknowledged snapshot.

Critical risks to test: hostile origins, secret persistence, path/symlink boundaries, inaccurate native parser claims, stale GitHub results, queue cancellation races, and model claims exceeding evidence. Demo data must remain visibly synthetic. Application tests never invoke test commands in selected repositories. No test runner feature will execute commands suggested by a model.

## Progress log

- 2026-10-24: Discovered unrelated dirty BountyPilot project; created isolated application directory. Read current Ponytail and review skills. REA directs source research to ordinary source tools; no binary RE workflow needed. Research delegated before implementation.
- 2026-10-26: Resumed after account usage interruption. Core server, evidence model, Gemma inference, demo, Git/GitHub/session adapters and UI are integrated. Independent review found quoted secret redaction and overstated model-verification labels; both received fixes and regression tests. The first real Gemma run exposed a missed latest user direction; a source-citation constraint and prompt revision corrected the next action in a 39.605-second repeat run on Apple arm64 with 48 GiB RAM and Ollama 0.40.5. Evidence is in `docs/evidence/gemma-run.json`. A clean source archive install and both launch modes passed; Entire current-tool compatibility remains experimental.

## Partner strategy and release gates (updated 2026-10-26)

Core reliability gates all partner claims. Gemma 3 4B is the local, configurable default. Entire checkpoint refs are a selected, read-only session source; its adapter has independent tests and never enables hooks. GitHub Actions CI, a public Render-ready static demo, and partner evidence follow the app's passing local checks. Optional integrations remain out of the submission until built and verified.

- [x] **Gemma:** verify 3.4 GB registry listing, 48 GiB hardware, current model terms, install model, perform real local inference over synthetic Git/PR/transcript sources, save output and observed limitations. Live model quality is demonstrated on one synthetic case, not a general benchmark.
- [x] **Entire:** implement selected checkpoint-ref adapter with pinned source contract, synthetic refs, source-linked commit association and read-only checks. Manual/Codex/Claude adapters remain. Entire CLI is not installed, so current-tool compatibility is experimental and there is no real build-session recording claim.
- [x] **GitHub Actions configuration:** workflow includes lint, types, tests, production and static builds and browser tests. Equivalent local checks passed. The first remote run reached the isolated static demo browser step and failed because preview served the wrong directory; the workflow was corrected and awaits a rerun. Current challenge calls the category “Best Use of GitHub Copilot,” although its description mentions Actions; no Copilot use is claimed.
- [x] **Render preparation:** browser-only synthetic demo built and browser-tested with zero `/api` requests, Render Blueprint and deployment guide written. No deployment or domain connection authorized.
- [x] **Evidence and submission:** versions, source links, reproduction, observed results and remaining uncertainty are recorded. Gemma is demonstrated with real local inference; Entire is labelled fixture-tested and experimental. The missed deadline is explicit; no category eligibility is claimed.

Optional ElevenLabs needs credentials/credits and a licensed voice. Optional Sentry needs opt-in telemetry plus demonstrated privacy-safe traces. Optional Temporal needs a tested durable workflow; the existing SQLite queue is not Temporal. These options are excluded from release scope until all core gates pass.

Deadline check at 2026-10-25 18:43:50 UTC (October 26 00:13:50 IST) was before the official close. At 2026-10-26 11:53:39 UTC (5:23:39 PM IST), the closing instant of 06:59 UTC had passed. No entry was submitted. Complete the project without claiming on-time eligibility.
