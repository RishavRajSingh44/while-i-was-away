import { expect, it, vi } from 'vitest';
import { demoApi, demoExport, redactDemoText } from './public-demo';

it('public demo stays in browser memory and refuses filesystem or live integration actions', async () => {
  const repository = { id: 'demo', demo: true, created_at: '2026-10-20T00:00:00Z', acknowledged_snapshot_id: null };
  const briefing = { id: 'brief', demo: true, snapshot_id: 'snap', handoff: 'Resume from the synthetic snapshot.', evidence: [] };
  const request = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ repository, overview: { repository, briefing, snapshot: { id: 'snap' }, jobs: [], history: [briefing], sessions: [] }, health: {}, settings: {} })));
  expect(await demoApi('/repos')).toEqual([repository]);
  for (const path of ['/repos', '/repos/demo/sessions/preview', '/repos/demo/sync', '/repos/demo/fetch', '/data']) {
    await expect(demoApi(path, 'POST', { path: '/private/secret' })).rejects.toThrow('requires the local app');
  }
  const queued = await demoApi<{ id: string; status: string }>('/repos/demo/briefings', 'POST', {});
  expect(queued.status).toBe('queued');
  const finished = await demoApi<{ briefing_id: string; status: string }>(`/jobs/${queued.id}`);
  expect(finished.status).toBe('completed');
  await demoApi(`/briefings/${finished.briefing_id}/handoff`, 'PUT', { text: 'Resume\napi_key=please-do-not-export-this' });
  expect(await demoExport(finished.briefing_id)).toBe('Resume\napi_key=[REDACTED]');
  const saved = await demoApi<{ acknowledged_snapshot_id: string }>(`/briefings/${finished.briefing_id}/acknowledge`, 'POST', {});
  expect(saved.acknowledged_snapshot_id).toBe(`snapshot-${queued.id}`);
  expect(request).toHaveBeenCalledTimes(1);
  expect(request.mock.calls[0][0]).toBe('/demo-data.json');
});

it('redacts common keys and private-key blocks from public-demo handoff edits', () => {
  expect(redactDemoText('ghp_abcdefghijklmnopqrstuvwxyz123456 password=abc\n-----BEGIN PRIVATE KEY-----\nprivate\n-----END PRIVATE KEY-----')).toBe('[REDACTED] password=[REDACTED]\n[REDACTED PRIVATE KEY]');
});
