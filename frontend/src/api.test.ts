import { describe, expect, it, vi } from 'vitest';
import { api, dateLabel, externalUrl } from './api';

describe('local API boundary', () => {
  it('adds an explicit client header and JSON content type to mutations', async () => {
    const request = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{"ok":true}'));
    await expect(api('/repos/one', 'DELETE', {})).resolves.toEqual({ ok: true });
    expect(request).toHaveBeenCalledWith('/api/repos/one', expect.objectContaining({ method: 'DELETE', headers: { 'Content-Type': 'application/json', 'X-Away-Client': '1' }, body: '{}' }));
  });
  it('preserves the server failure instead of pretending a mutation worked', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{"detail":"Repository association is unknown."}', { status: 409 }));
    await expect(api('/repos/one/sessions/import', 'POST', {})).rejects.toThrow('Repository association is unknown.');
  });
  it('rejects executable, local-file, and malformed evidence links', () => {
    for (const url of ['javascript:alert(1)', 'data:text/html,<script>', 'file:///private/key', 'not a url']) expect(externalUrl(url)).toBeUndefined();
    expect(externalUrl('https://github.com/example/project/pull/1')).toBe('https://github.com/example/project/pull/1');
  });
  it('does not present missing or invalid timestamps as fresh data', () => {
    expect(dateLabel(null)).toBe('Not available');
    expect(dateLabel('invalid')).toBe('Unknown date');
  });
});
