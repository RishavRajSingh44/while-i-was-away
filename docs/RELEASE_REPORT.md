# Local release readiness — October 26, 2026

**Status:** standalone source package prepared and clean-installed locally. The [independent application repository](https://github.com/RishavRajSingh44/while-i-was-away) and [synthetic video](https://player.mux.com/728fJk3p6UEeTYeO9qVt9AOOPg2EOXTw9K01bwt002Faw) are public. No deployment, domain connection or contest submission occurred. The contest entry deadline passed before publication.

## What changed in this pass

- Required Gemma's next-step claim to cite the latest selected user message, revised the prompt to prioritize that direction, and bumped the inference cache prompt version. The first recorded run focused on a failing PR; the new real run recommends finishing the regression requested by the user. Model prose remains interpretation, even with a citation.
- Tested GitHub's actual authenticated GraphQL path against a disposable local repository pointing to an accessible PR-history repository: 23 authored merged PRs normalized successfully. The account had no authored open, draft or closed-unmerged PRs available; those categories remain contract-fixture tested.
- Checked Entire's current public release, source head and MIT license. The adapter is pinned to an earlier source contract and has only synthetic checkpoint-ref tests, so current Entire compatibility is experimental.
- Built an explicit source-only archive, installed both dependency lockfiles from a fresh extraction, passed tests and builds, and started both documented launch modes. Recorded and visually inspected a silent, synthetic-only public-demo video.

## Verification tiers

| Tier | Result |
|---|---|
| Live local | Gemma 3 4B inference on synthetic Git, four synthetic PRs and a synthetic transcript; 39.605 s, cited output saved in [gemma-run.json](evidence/gemma-run.json). Clean extracted development and production servers returned HTTP 200. Authenticated GitHub sync normalized 23 actual merged PRs. |
| Fixture / contract | 73 backend tests, 11 frontend tests, all four PR states and pagination, Codex/Claude formats, Entire refs, queue recovery, security boundaries, handoff and browser demo flows. |
| Experimental | Entire native import has no actual-tool-produced checkpoint test. Codex/Claude native formats have no individually selected, consented real-file check in this release pass. |
| External / unverified | The [corrected GitHub Actions run](https://github.com/RishavRajSingh44/while-i-was-away/actions/runs/40325353605) passed. Render deployment, `.tech` domain, Windows/Linux UI, and general model accuracy/performance remain unverified. |

The new Gemma run cites the latest selected user message for the action. Manual comparison confirms the requested regression and failed global-clear approach appear in that excerpt. It still places the historical goal in “What changed,” even though that citation does not establish an event in the observation window. This is a known semantic limit: evidence IDs prove traceability, not full claim entailment or ideal section placement. Review the briefing and source drawer before acting.

## Isolation and package

This directory is its own nested Git repository. The unrelated BountyPilot parent sees `while-i-was-away/` as an untracked nested directory; no parent commit, licensing or source file was changed for this release. The inner repository was initialized separately. The release tarball has no `.git` directory and can be extracted anywhere.

Run `.venv/bin/python scripts/package_release.py` to create `release/while-i-was-away-0.1.0.tar.gz`. The explicit allowlist includes source, lockfiles, CI, Render configuration, license/notices, synthetic fixtures, screenshots and the silent video. It excludes credentials, personal transcripts, source repositories, SQLite files, virtual environments, `node_modules`, generated bundles and Git history. Before publication, inspect the archive listing and synthetic evidence again; automated redaction is not a substitute for review.

Clean-install commands exercised after extracting the archive into a fresh temporary directory:

```sh
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.lock
npm --prefix frontend ci
.venv/bin/python -m pytest -q
npm --prefix frontend run build
npm --prefix frontend run build:demo
AWAY_PORT=8876 .venv/bin/python scripts/run.py start
AWAY_PORT=8877 .venv/bin/python scripts/run.py dev
```

The two launch commands were run separately. Production served the built `/` and `/api/settings`; development served the Vite `/` and backend `/api/health`, all HTTP 200 on loopback. PyPI access required an approved unsandboxed retry after DNS was blocked; npm installed from the lockfile. No model is bundled in the archive, so a new user must explicitly install Ollama and pull a compatible model for real inference.

## Public release steps remaining

1. Review the archive and article once more; narration remains optional for the silent recording.
2. If a hosted preview is desired, deploy only the static `dist-demo` Render configuration, inspect its network traffic and labels, then add the real URL to the article. Connect a `.tech` domain only if one is available and authorized.
3. Publish the DEV article only when requested. Present it as a completed project inspired by Slow and Steady, with the missed contest deadline plainly stated.
