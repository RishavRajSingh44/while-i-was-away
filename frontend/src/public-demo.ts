import type { Health, Job, Overview, Repository, Settings } from './types';

export type DemoData = { repository: Repository; overview: Overview; health: Health; settings: Settings };
let dataPromise: Promise<DemoData> | undefined;
let pendingJob: Job | null = null;

async function data() {
  dataPromise ??= fetch(`${import.meta.env.BASE_URL}demo-data.json`).then(async response => {
    if (!response.ok) throw new Error('The public demo fixture could not be loaded.');
    const fixture = await response.json() as DemoData;
    if (!fixture.repository.demo || !fixture.overview.briefing?.demo) throw new Error('Public demo requires explicitly synthetic data.');
    return fixture;
  });
  return dataPromise;
}

export function redactDemoText(text: string): string {
  return text.replace(/\b(?:gh[pousr]_[A-Za-z0-9_]{16,}|github_pat_[A-Za-z0-9_]{16,}|sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16})\b/g, '[REDACTED]')
    .replace(/((?:api[_-]?key|token|password|secret)\s*[:=]\s*)[^\s,;]+/gi, '$1[REDACTED]')
    .replace(/-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----/g, '[REDACTED PRIVATE KEY]');
}

export async function demoApi<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const fixture = await data();
  const input = (body || {}) as Record<string, unknown>;
  const repoPath = `/repos/${fixture.repository.id}`;
  let result: unknown;
  if (method === 'GET' && path === '/repos') result = [fixture.repository];
  else if (method === 'GET' && path === '/settings') result = fixture.settings;
  else if (method === 'GET' && path === '/health') result = fixture.health;
  else if (method === 'POST' && path === '/demo') result = fixture.repository;
  else if (method === 'GET' && path === `${repoPath}/overview`) result = fixture.overview;
  else if (method === 'GET' && path === `${repoPath}/history`) result = fixture.overview.history;
  else if (method === 'POST' && path === `${repoPath}/briefings`) {
    pendingJob = { id: crypto.randomUUID(), repo_id: fixture.repository.id, status: 'queued', stage: 'Replaying precomputed synthetic results · no inference', progress: 0, error: null, briefing_id: null, created_at: fixture.repository.created_at, attempts: 1 };
    fixture.overview.jobs = [pendingJob];
    result = pendingJob;
  } else if (method === 'GET' && pendingJob && path === `/jobs/${pendingJob.id}`) {
    if (pendingJob.status === 'queued') {
      const briefing = { ...fixture.overview.briefing!, id: `public-${pendingJob.id}`, snapshot_id: `snapshot-${pendingJob.id}` };
      fixture.overview.briefing = briefing;
      fixture.overview.history.unshift(briefing);
      if (fixture.overview.snapshot) fixture.overview.snapshot.id = briefing.snapshot_id;
      pendingJob = { ...pendingJob, status: 'completed', stage: 'Synthetic replay complete', progress: 100, briefing_id: briefing.id };
      fixture.overview.jobs = [pendingJob];
    }
    result = pendingJob;
  } else if (method === 'POST' && pendingJob && path === `/jobs/${pendingJob.id}/cancel`) {
    pendingJob = { ...pendingJob, status: 'cancelled', stage: 'Replay cancelled' }; fixture.overview.jobs = [pendingJob]; result = pendingJob;
  } else if (path.startsWith('/briefings/')) {
    const [, , id, action] = path.split('/');
    const briefing = fixture.overview.history.find(item => item.id === id) || (fixture.overview.briefing?.id === id ? fixture.overview.briefing : undefined);
    if (!briefing) throw new Error('This synthetic briefing is no longer available.');
    if (method === 'GET' && !action) result = briefing;
    else if (method === 'GET' && action === 'export') result = redactDemoText(briefing.handoff);
    else if (method === 'PUT' && action === 'handoff' && typeof input.text === 'string') {
      briefing.handoff = redactDemoText(input.text);
      if (fixture.overview.briefing?.id === id) fixture.overview.briefing.handoff = briefing.handoff;
      result = { text: briefing.handoff };
    } else if (method === 'POST' && action === 'acknowledge') {
      fixture.repository.acknowledged_snapshot_id = briefing.snapshot_id;
      fixture.overview.repository = fixture.repository;
      result = fixture.repository;
    }
  }
  if (result === undefined) throw new Error('This action requires the local app. The public demo cannot read files, contact GitHub, or run a model.');
  return structuredClone(result) as T;
}

export async function demoExport(id: string): Promise<string> { return demoApi<string>(`/briefings/${id}/export`); }
