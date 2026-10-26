# Submission draft — do not publish without review

Challenge deadline: October 25, 2026, 11:59 PM PDT (October 26, 12:29 PM IST). This project **missed that deadline**; no qualifying entry was submitted. This is a post-contest open-source article draft, not a claim of eligibility. The [specific rules](https://dev.to/page/hacktoberfest-week3-2026-10-19-contest-rules) required a completed new project, a DEV post tagged `hf26challenge`, a demo link/video and a code link. User eligibility has not been verified.

## What I Built

**While I Was Away** helps a developer resume after a break. It reads one selected local repository, explicit GitHub PR sync and selected coding-agent conversations, then asks a local Gemma model for a cited briefing. It tells me where I stopped, what changed, which PRs need attention, and one next action. I can inspect every cited source and edit a handoff prompt before copying it to an agent. Acknowledgment sets the next look-back checkpoint; refreshing never moves it by surprise.

## Demo

[Watch the uploaded synthetic demo](https://player.mux.com/728fJk3p6UEeTYeO9qVt9AOOPg2EOXTw9K01bwt002Faw). The public demo uses original synthetic Git, PR and transcript fixtures and a precomputed synthetic briefing. Its replay is not live inference. The installed local app performs real Git collection, GitHub sync and Gemma synthesis. A [local recording](demo/while-i-was-away-demo.webm), [narration script](DEMO_NARRATION.md), [screenshots](screenshots/) and a [75-second walkthrough](DEMO_SCRIPT.md) are prepared.

## Code

The [public source repository](https://github.com/RishavRajSingh44/while-i-was-away) is MIT licensed; Gemma weights are obtained separately under [Gemma Terms of Use](https://ai.google.dev/gemma/terms). Local setup, tests and limits are in the [README](../README.md).

## How I Built It

The app has a React/TypeScript/Vite interface and a loopback FastAPI backend. SQLite holds snapshots, acknowledgments, selected session imports, a GitHub cache and a recoverable job queue. Git CLI reads a bounded local diff without reading untracked contents; `gh` supplies authenticated PR facts while retaining its own credentials. Selected Codex, Claude, Entire and manual adapters bring forward user goals, decisions, last meaningful exchange and historical agent claims. The Entire adapter reads local checkpoint refs and Git blobs without activating hooks or uploading transcripts. Unsupported layouts produce a warning.

Gemma 3 4B runs through local Ollama. The prompt asks for structured notes and a five-part briefing; the app checks every citation against an existing evidence ID and requires the next step to cite the latest selected user direction. Deterministic Git/PR fields are rendered separately from model interpretation. On an Apple arm64 machine with 48 GiB RAM and Ollama 0.40.5, the latest real `gemma3:4b` run over a temporary synthetic Git repo, four synthetic PRs and synthetic conversation completed in **39.605 seconds**. [The recorded output](evidence/gemma-run.json) includes the model digest and limitations. Its next step followed the latest user direction, but a historical goal appeared under “What changed”; citation validation does not prove every model sentence or section is semantically correct. This is one demonstration, not an average speed or accuracy benchmark.

## Why Does Open Innovation Matter?

Local open-weight inference gives me an inspectable prompt, a swappable model and a briefing path that can work without sending repository code or transcripts to a cloud provider. Cached GitHub data and local Git remain useful offline, with freshness visible. Open components make the collector and citation rules auditable. Gemma is open-weight under model-specific terms; this application's software is MIT licensed. I still need hardware, electricity and time, so I do not call it zero-cost or promise absolute privacy. See [references](REFERENCES.md) for pinned source research and attribution.

## Prize Categories

The product uses Gemma 3 4B centrally. Entire checkpoint import is a first-class optional **experimental** source, tested against synthetic refs but not current Entire tooling. Because the deadline passed without submission, this article does **not claim prize eligibility**. Render has a prepared static demo Blueprint but no deployment URL. GitHub Actions ran remotely, but the first run failed the public-demo browser step; a corrected workflow awaits verification. The contest category is named **Best Use of GitHub Copilot**, and no Copilot contribution is claimed. ElevenLabs, Sentry Agent Tracing, Temporal and `.tech` have no completed evidence and are omitted. [Partner evidence](PARTNER_EVIDENCE.md) separates each verified and unverified integration.

The optional “My Agent Session” and “The Lazy Payoff” sections are omitted: no authorized public agent-session link or measured time-savings study exists. Do not fabricate either, or personal eligibility, user feedback or an on-time published entry.
