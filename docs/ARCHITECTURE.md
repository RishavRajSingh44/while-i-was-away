# ADR 001: one local process, inspectable evidence

Status: accepted, 2026-10-24.

Use React, TypeScript and Vite for the interface; Python 3.11+ and FastAPI for a loopback-only API; SQLite with explicit migrations for application state. The production backend serves the built client. A single persistent worker drains SQLite jobs. No Docker, broker, cloud inference or telemetry is required.

Git and GitHub collectors produce bounded evidence using argument-array subprocesses. Git reads cannot mutate worktrees; fetching is a separate explicit action. gh owns credentials. Selected Codex, Claude, manual and Entire checkpoint adapters return normalized messages and original excerpts. Entire reads selected local checkpoint refs and safe Git blobs without hooks or a mandatory CLI installation. Preview is separate from import and mismatches require a decision. Cached remote information carries timestamps and errors.

Snapshots are immutable observations. Briefings cite a snapshot. Acknowledgment is an explicit user action; collection, regeneration and failed jobs do not move that checkpoint. Repositories and worktrees retain distinct paths. SQLite foreign keys cascade only application records on deletion.

Ollama on loopback receives redacted evidence as untrusted data, performs structured extraction in bounded chunks, then synthesizes a validated briefing. Gemma 3 4B is the configurable default. Every model factual claim must cite an existing evidence ID; free-form model prose is labeled interpretation/suggestion, while application-formatted Git and PR fields receive verified labels. Reported tests remain historical claims. Citation validation proves source existence, not semantic truth; users can inspect excerpts.

Security boundaries: exact loopback Host and Origin checks, explicit JSON/custom-header mutations, no wildcard CORS, subprocess time/output limits, no shell interpolation, selected paths and symlink limits, bounded imports/diffs, exclusion of likely secret files, redaction before persistence and export. The application never runs model commands or repository tests. Same-user malware and compromised local processes are outside this boundary.

The public Render-ready demo is a separate static Vite build using original synthetic JSON fixtures in browser memory. It has no API or local repository access and labels its briefing as precomputed. The real local app continues to serve its built UI from FastAPI.

Rejected: distributed queues, mandatory Entire installation, hosted filesystem access, automatic home-directory session discovery, cloud fallback, automatic Git fetch, arbitrary agent-command execution. Legacy Entire branch storage and compressed/chunked transcripts remain unsupported until source contracts and fixtures are added.
