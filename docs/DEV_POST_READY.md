# While I Was Away: a local Gemma briefing for the context I forgot

*Built for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19) theme. I missed the entry deadline, so this is a project write-up, not an eligible contest submission.*

## What I Built

When I reopen a repository after a break, the hard part is remembering the story behind the diff: what I was trying to fix, what reviewers said, whether a PR merged, and which test I meant to write next. **While I Was Away** turns that scattered context into one local briefing.

I choose a repository and, optionally, specific coding-agent sessions. The app reads the Git working tree and recent commits, syncs my PRs through GitHub CLI when I ask it to, and uses a local Gemma model to connect that evidence. The briefing puts **“Your next step”** first. I can open citations, inspect the original excerpts, and edit a continuation prompt before copying or exporting it. Acknowledging a briefing sets the next look-back checkpoint; merely refreshing one does not.

The lazy payoff is qualitative: fewer tabs and less reconstruction before I can resume work. I have not measured time saved, so I am not claiming a speedup.

## Demo

[Watch the 20-second synthetic demo](https://player.mux.com/728fJk3p6UEeTYeO9qVt9AOOPg2EOXTw9K01bwt002Faw). It shows the next-step card, source evidence, four PR states, a selected agent conversation, and the editable handoff.

The public recording is **synthetic and silent**. Its briefing is precomputed; replaying it does not run Gemma or contact GitHub. The installed application does perform real local inference and explicit authenticated GitHub sync.

## Code

The [public standalone repository](https://github.com/RishavRajSingh44/while-i-was-away) contains the MIT-licensed application, setup instructions, tests, synthetic fixtures, and third-party notices. Gemma model weights are obtained separately under [Gemma's terms](https://ai.google.dev/gemma/terms).

## How I Built It

The UI is React, TypeScript, and Vite. A loopback-only FastAPI backend reads local Git state without changing the worktree; GitHub CLI supplies PR status while keeping authentication in `gh`. SQLite stores snapshots, acknowledged checkpoints, cached GitHub facts, imported sessions, and a recoverable briefing queue. Manual, Codex, and Claude transcript adapters require selected sources. A read-only Entire checkpoint adapter is also present, but compatibility with the current Entire CLI is still experimental: I tested synthetic checkpoint refs, not a checkpoint produced by the installed tool.

`gemma3:4b` runs through Ollama on the developer's machine. It extracts bounded context and synthesizes five briefing sections as validated JSON. Every model claim must point to an existing evidence ID, and the next-step claim must cite the latest selected user direction. Deterministic Git and PR fields are kept separate from model interpretation. A real run on a temporary synthetic repository, four synthetic PRs, and a synthetic conversation took **39.605 seconds** on an Apple arm64 machine with 48 GiB RAM. Its suggested action matched the user's last instruction. It also placed a historical goal under “What changed,” a reminder that a valid citation is not proof every sentence or section is right.

Local checks passed: **73 backend tests, 11 frontend tests**, lint, type checks, production builds, and browser flows. Authenticated read-only sync normalized 23 real merged PRs; open, draft, and closed-without-merge states were covered by fixtures because none were available in the authenticated authored history. The [first GitHub Actions run](https://github.com/RishavRajSingh44/while-i-was-away/actions/runs/40324529239) passed application checks but failed the isolated public-demo browser step because the preview command served the wrong directory. I corrected the workflow; its remote rerun is pending.

## Why Does Open Innovation Matter?

The model is a replaceable local component, and the prompts and evidence rules are inspectable. I can analyze local Git and cached GitHub data offline, then run a compatible installed model without sending code or conversations to a cloud inference API by default. That makes the workflow easier to audit and adapt. It does not make the app cost-free or guarantee perfect privacy: hardware, electricity, redaction limits, and the user's own export choices still matter.

Gemma is **open-weight under model-specific terms**; the application code is MIT-licensed software. That distinction matters as much as the technical design.
