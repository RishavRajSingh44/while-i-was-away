# Integration contract v1

All routes `/api`; JSON direct objects/arrays. Errors `{detail: string}`. Mutations require `Content-Type: application/json`, header `X-Away-Client: 1`; same-origin only. Frontend Vite proxies `/api` to 127.0.0.1:8765. Production same backend port. IDs are strings. Dates UTC ISO strings. The server binds loopback. One repository per briefing.

## Types

Repository: `{id,name,path,demo:boolean,created_at,acknowledged_snapshot_id:string|null}`.
Evidence: `{id,kind,title,body,source,timestamp:string|null,trust:'verified'|'agent-reported'|'user-provided',url?:string,metadata?:object}`. Body plain text, never HTML. Source is a descriptive path/reference, not an executable URL.
GitContext: `{root,branch:string|null,head:string|null,upstream:string|null,remotes:[{name,url}],worktrees:[{path,head,branch}],staged:string[],unstaged:string[],untracked:string[],commits:[{sha,author,timestamp,subject}],diff:string,base_branch:string|null,base_head:string|null,base_changes:string[],warnings:string[],evidence:Evidence[]}`.
PR: `{number,title,url,state:'open'|'draft'|'merged'|'closed',head_branch,head_sha:string|null,base_branch,updated_at,review_state,mergeability,checks:[{name,status,conclusion}],reviews:[{author,state,body,submitted_at}],comments:[{author,body,created_at,url}],matches_branch:boolean,changes:string[],evidence_id}`.
GitHub: `{prs:PR[],synced_at:string|null,offline:boolean,error:string|null,user:string|null,evidence:Evidence[],warnings:string[]}`.
Session: `{id,title,adapter,source,repo_path:string|null,branch:string|null,created_at:string|null,messages:[{role,text,timestamp:string|null}],warnings:string[],match:'matched'|'unknown'|'mismatch',evidence:Evidence[],associated_prs?:[{number,title,url,evidence_id}]}`. Associated PRs require an exact Entire linked code commit SHA matching the PR's authoritative current head SHA.
Snapshot: `{id,repo_id,created_at,since,git:GitContext,github:GitHub,evidence:Evidence[],warnings:string[]}`.
Claim: `{text,kind:'verified'|'agent-reported'|'suggestion'|'unknown',evidence_ids:string[]}`.
Briefing: `{id,repo_id,snapshot_id,created_at,model,demo:boolean,sections:[{key:'working_on'|'stopped_at'|'changed'|'attention'|'next_step',title,claims:Claim[]}],handoff:string,evidence:Evidence[],warnings:string[]}`.
Job: `{id,repo_id,status:'queued'|'running'|'completed'|'failed'|'cancelled',stage,progress:number,error:string|null,briefing_id:string|null,created_at,attempts:number}`.
Health: `{git:{ok,message},github:{ok,message,user?:string},ollama:{ok,message,models:[{name,size}]},version}`.

## Routes

- GET `/health` → Health; GET `/settings` → `{model,exclusions:string[]}`; PUT `/settings` body same → saved. Model chosen only from installed local models; no auto download.
- GET `/repos` → Repository[]; POST `/repos` `{path}` → Repository; DELETE `/repos/{id}` `{}` → `{ok:true}` deletes app data only.
- POST `/demo` `{}` → Repository (idempotent, synthetic seed).
- GET `/repos/{id}/overview` → `{repository,snapshot:Snapshot|null,briefing:Briefing|null,sessions:Session[],jobs:Job[],history:Briefing[]}`.
- POST `/repos/{id}/collect` `{window:'24h'|'7d'|'custom'|'acknowledged',since?:string}` → Snapshot, local Git plus cached GitHub only.
- POST `/repos/{id}/sync` `{}` → GitHub, explicit remote request; errors return visibly stale cached payload when present.
- POST `/repos/{id}/fetch` `{}` → `{ok:true,message}` explicit Git fetch, never automatic.
- POST `/repos/{id}/briefings` `{model?:string,window:'24h'|'7d'|'custom'|'acknowledged',since?:string}` → Job. Collects local snapshot, cached GitHub, selected imported sessions. Demo uses fixture synthesis only and is labeled.
- GET `/jobs/{id}` → Job; POST `/jobs/{id}/cancel` `{}` → Job.
- GET `/repos/{id}/history` → Briefing[]; GET `/briefings/{id}` → Briefing; POST `/briefings/{id}/acknowledge` `{}` → Repository. Only this route advances checkpoint.
- PUT `/briefings/{id}/handoff` `{text}` → `{text}` redacted; GET `/briefings/{id}/export` → Markdown text attachment.
- POST `/repos/{id}/sessions/preview` `{path?:string,text?:string,format:'auto'|'manual'|'codex'|'claude',title?:string}` → `{candidates:Session[],warnings:string[]}`. Explicit selection, no global scanning. Directory preview limited. Preview does not persist.
- POST `/repos/{id}/sessions/import` same + `{confirm_mismatch?:boolean}` → Session[]. Reparse selected input, mismatch requires explicit confirmation.
- DELETE `/repos/{id}/sessions/{session_id}` `{}` → `{ok:true}`.
- DELETE `/data` `{confirm:'DELETE'}` → `{ok:true}` deletes all app data only.

## Python integration adapters (no database imports)

`git_context.collect_git(path: str, since: str, previous: dict|None = None, exclusions: list[str]|None = None) -> dict` returns GitContext; `discover_repo(path) -> dict` returns root/name plus metadata; `fetch_refs(path) -> None`. Raise ValueError for invalid input and RuntimeError for integration failures, with sanitized messages.
`github.github_health() -> dict` returns ok/message/user; `sync_github(root: str, branch: str|None, previous: dict|None = None) -> dict` returns GitHub. It must return prior cache marked offline on failure, not silently substitute empty success. Uses gh github.com only.
`sessions.preview_sessions(path: str|None, text: str|None, format: str, repo_path: str, title: str|None = None) -> dict` → candidates/warnings. Read selected root only, no symlink traversal, bounds 2MB/file and 50 files. Manual JSON accepted documented messages array; unsupported shapes visible.

Shared utility primary supplies: `security.redact(text: str)->str`; adapters may import. Evidence IDs should be deterministic SHA256-derived with kind prefix, not Python hash(). Files are redacted before returned/persisted. Main server normalizes all JSON through final redaction too.
