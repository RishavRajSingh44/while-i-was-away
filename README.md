# While I Was Away

**Close your laptop. Lose the context. Get it back in one briefing.**

While I Was Away is a local developer app that combines read-only Git state, your GitHub PRs, selected coding-agent sessions and a real local Gemma briefing. A briefing shows where you stopped, what changed, what needs attention and one next action. Every source can be opened from its citation. It produces an editable, secret-redacted handoff prompt and Markdown export.

The [synthetic demo](docs/DEMO_SCRIPT.md) needs no GitHub account, repository or model. It is explicitly labeled and never substitutes for a real briefing. A separate [public static demo](docs/RENDER_DEPLOYMENT.md) contains only synthetic precomputed data and cannot access files, GitHub or Ollama.

## Setup (macOS first)

Requirements: Python 3.11+, Node 20.19+ or 22.12+, npm, Git, [GitHub CLI](https://cli.github.com/manual/gh_auth_login) for PR sync, and [Ollama](https://ollama.com/download) for real briefing synthesis. The app works offline with local Git and cached GitHub data. GitHub sync and explicit Git fetch need internet. One process/worker is supported.

From this directory:

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.lock
npm --prefix frontend ci
ollama pull gemma3:4b # user-initiated ~3.4 GB download; Gemma terms apply
.venv/bin/python scripts/run.py dev
```

Open `http://127.0.0.1:5173`. `ollama serve` may be needed if the Ollama desktop service is not running. `gh auth login -h github.com` enables private and authenticated PR data; tokens stay in gh's own configuration.

For a production-style local launch, after setup:

```sh
npm --prefix frontend run build
.venv/bin/python scripts/run.py start
```

Open `http://127.0.0.1:8765`. Both commands bind the API to loopback. The backend serves the built UI. Set `AWAY_DATABASE` to an application-owned SQLite path if desired; do not place it inside a source repository you do not intend to modify. The default is `.data/away.sqlite` here. Keep this file private. The app creates no telemetry by default.

## First briefing

Add a local Git repository path in Connections. Review its branch, remotes, upstream and worktrees. Use Sync GitHub to read your authored PRs through `gh`; it is an explicit online request. Choose an installed local model in Settings. In Agent sessions, preview a selected transcript file/directory or an Entire checkpoint repository, then import the relevant session. Unknown or mismatched repository associations require confirmation. Choose 24 hours, seven days, a custom date, or the last acknowledged snapshot and generate.

The first screen puts **Your next step** above the source evidence. Open citations to inspect file paths, PR states, comments or session excerpts. Open **Continue with your agent** to review and edit the handoff before copying/exporting. Acknowledge a briefing only when you want that observation to become your next checkpoint. Generation, refresh and cancellation do not advance it.

Git collection never checks out, resets, stashes, commits or reads untracked contents. Explicit Fetch remote Git refs is separate from local collection and may contact remotes. The app never runs arbitrary commands from transcripts or model output. It does not execute test commands in selected repositories.

## Architecture and privacy

The React/TypeScript/Vite UI calls a FastAPI server restricted to loopback Host/Origin values. SQLite stores repositories, immutable snapshots, imported selected sessions, GitHub cache, persistent briefing jobs, validated briefings and the acknowledged snapshot ID. A single worker recovers interrupted jobs, retries bounded local model responses, supports cancellation and caches by evidence/model digest/prompt version. Git, `gh`, session text and PR comments are untrusted data. The model receives redacted bounded evidence through local Ollama only. See [architecture](docs/ARCHITECTURE.md) and [formats](docs/SESSION_FORMATS.md).

The default is `gemma3:4b` because its 3.4 GB Ollama build ran on the validation machine. Model selection is configurable to installed local models. No model is downloaded automatically. Gemma uses [its own terms](https://ai.google.dev/gemma/terms); download size is lower than peak runtime memory. On this 48 GiB Apple arm64 machine, the [real synthetic verification](docs/evidence/gemma-run.json) completed in 39.605 seconds under Ollama 0.40.5. This single case does not establish performance on smaller machines or prove every model sentence is correct. Ollama must be on loopback; cloud tagged models are rejected.

Secret matching is best-effort. Check any handoff/export before sharing. Deleting a repository or all app data removes local application records only; source repositories and original transcript files remain. SQLite `secure_delete` is enabled for rows, but file-system snapshots/backups may retain prior data. Use the operating system's disk controls for stronger erasure.

## Troubleshooting and limits

- **No model:** Start Ollama and run `ollama pull gemma3:4b`; select it in Settings. Inference failures show a failed job and preserve prior briefings.
- **GitHub offline/unauthenticated:** Run `gh auth login -h github.com`. The board shows the last synced timestamp and cached/offline state. GitHub may rate-limit or deny repository access. Sync again once connected.
- **Agent format rejected:** Preview the selected source. Native Codex and Claude adapters cover source-and-fixture-tested subsets. Entire is an experimental adapter pinned to a checkpoint format that has not been checked with the current CLI. Use manual Markdown/text/JSON export for unsupported layouts. Entire is optional and is never installed or activated by this app.
- **Empty/unusual repository:** Detached HEAD, shallow history, missing remote, unborn branch and dirty worktree appear with warnings and partial facts.
- **Windows/Linux:** Core Python/Git logic is portable but the interface and process launch were validated on macOS. Windows may need a different Python/npm command or shell environment; native `O_NOFOLLOW` protection differs by OS. Loopback and path behavior should be retested before deployment there.
- **Large input:** Diffs, files, sessions, PR discussions and model chunks have explicit limits. Warnings show truncated coverage. Long Entire compressed/chunked transcripts and older checkpoint storage are not reconstructed.

## Verification and challenge material

Run `.venv/bin/python -m pytest -q`, `.venv/bin/ruff check backend tests scripts`, `npm --prefix frontend run lint`, `typecheck`, `test`, `build` and `test:e2e`. The [validation log](docs/VALIDATION.md) records actual outcomes and external limits. GitHub Actions are configured in [.github/workflows/ci.yml](.github/workflows/ci.yml); inspect the [remote runs](https://github.com/RishavRajSingh44/while-i-was-away/actions) separately from local test results. Research and exact source revisions: [references](docs/REFERENCES.md). Article draft: [docs/DEV_POST_READY.md](docs/DEV_POST_READY.md). The source repository and synthetic video are public; the DEV article has not been published.

For a standalone source archive, run `.venv/bin/python scripts/package_release.py`; the result is `release/while-i-was-away-0.1.0.tar.gz`. It contains only explicitly selected application source, synthetic fixtures, screenshots/video, licenses and documentation; it excludes Git history, databases, virtual environments, dependencies and private transcripts. The [release report](docs/RELEASE_REPORT.md) records the clean extraction/install check. This directory has its own Git repository with no dependency on the unrelated parent project. Its source can be published in its own repository after review and explicit authorization.
