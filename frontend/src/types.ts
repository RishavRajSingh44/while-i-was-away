export type Repository = { id: string; name: string; path: string; demo: boolean; created_at: string; acknowledged_snapshot_id: string | null };
export type Evidence = { id: string; kind: string; title: string; body: string; source: string; timestamp: string | null; trust: 'verified' | 'agent-reported' | 'user-provided'; url?: string; metadata?: Record<string, unknown> };
export type GitContext = {
  root: string; branch: string | null; head: string | null; upstream: string | null;
  remotes: { name: string; url: string }[]; worktrees: { path: string; head: string; branch: string }[];
  staged: string[]; unstaged: string[]; untracked: string[];
  commits: { sha: string; author: string; timestamp: string; subject: string }[];
  diff: string; base_branch: string | null; base_head: string | null; base_changes: string[];
  warnings: string[]; evidence: Evidence[];
};
export type PR = {
  number: number; title: string; url: string; state: 'open' | 'draft' | 'merged' | 'closed';
  head_branch: string; head_sha?: string | null; base_branch: string; updated_at: string; review_state: string; mergeability: string;
  checks: { name: string; status: string; conclusion: string }[];
  reviews: { author: string; state: string; body: string; submitted_at: string }[];
  comments: { author: string; body: string; created_at: string; url: string }[];
  matches_branch: boolean; changes: string[]; evidence_id: string;
};
export type GitHub = { prs: PR[]; synced_at: string | null; offline: boolean; error: string | null; user: string | null; evidence: Evidence[]; warnings: string[] };
export type Session = {
  id: string; title: string; adapter: string; source: string; repo_path: string | null;
  branch: string | null; created_at: string | null;
  messages: { role: string; text: string; timestamp: string | null }[];
  warnings: string[]; match: 'matched' | 'unknown' | 'mismatch'; evidence: Evidence[];
  associated_prs?: { number: number; title: string; url: string; evidence_id: string }[];
};
export type Snapshot = { id: string; repo_id: string; created_at: string; since: string; git: GitContext; github: GitHub; evidence: Evidence[]; warnings: string[] };
export type Claim = { text: string; kind: 'verified' | 'agent-reported' | 'suggestion' | 'unknown'; evidence_ids: string[] };
export type Briefing = { id: string; repo_id: string; snapshot_id: string; created_at: string; model: string; demo: boolean; sections: { key: string; title: string; claims: Claim[] }[]; handoff: string; evidence: Evidence[]; warnings: string[] };
export type Job = { id: string; repo_id: string; status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'; stage: string; progress: number; error: string | null; briefing_id: string | null; created_at: string; attempts: number };
export type Health = { git: { ok: boolean; message: string }; github: { ok: boolean; message: string; user?: string }; ollama: { ok: boolean; message: string; models: { name: string; size: number }[] }; version: string };
export type Settings = { model: string; exclusions: string[] };
export type Overview = { repository: Repository; snapshot: Snapshot | null; briefing: Briefing | null; sessions: Session[]; jobs: Job[]; history: Briefing[] };
export type WindowChoice = '24h' | '7d' | 'custom' | 'acknowledged';
