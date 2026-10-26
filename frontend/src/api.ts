import { demoApi, demoExport } from './public-demo';

export const publicDemo = import.meta.env.VITE_PUBLIC_DEMO === 'true';

export async function api<T>(path: string, method = 'GET', body?: unknown, signal?: AbortSignal): Promise<T> {
  if (publicDemo) return demoApi<T>(path, method, body);
  const response = await fetch(`/api${path}`, {
    method, signal,
    headers: method === 'GET' ? {} : { 'Content-Type': 'application/json', 'X-Away-Client': '1' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: `Request failed (${response.status}).` }));
    throw new Error(typeof error.detail === 'string' ? error.detail : `Request failed (${response.status}). Check your input.`);
  }
  return response.json() as Promise<T>;
}

export async function exportHandoff(id: string): Promise<Blob> {
  if (publicDemo) return new Blob([await demoExport(id)], { type: 'text/markdown' });
  const response = await fetch(`/api/briefings/${id}/export`);
  if (!response.ok) throw new Error('Export failed. Your edits are saved; try again.');
  return response.blob();
}

export function externalUrl(value?: string): string | undefined {
  if (!value) return;
  try { const url = new URL(value); if (url.protocol === 'https:' || url.protocol === 'http:') return url.href; } catch { /* Untrusted sources are displayed as text. */ }
}

export function dateLabel(value: string | null | undefined): string {
  if (!value) return 'Not available';
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? 'Unknown date' : date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}
