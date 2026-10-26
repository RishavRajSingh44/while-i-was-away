import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

test.skip(process.env.AWAY_PUBLIC_DEMO !== '1', 'Run against the static public-demo build with AWAY_PUBLIC_DEMO=1.');

test('public preview makes no local API requests and replays synthetic evidence and handoff', async ({ page }) => {
  const requests: string[] = [];
  const errors: string[] = [];
  page.on('request', request => requests.push(request.url()));
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByText('Public demo • precomputed synthetic results • no live inference.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'A good place to begin.' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Collect local snapshot' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Sync GitHub now' })).toBeDisabled();
  await page.locator('.citation').first().click();
  await expect(page.locator('.evidence-body')).toBeVisible();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Replay demo briefing' }).click();
  await expect(page.getByText('Your briefing is ready. Your acknowledged checkpoint has not changed.')).toBeVisible();
  await page.getByRole('button', { name: 'Continue with your agent' }).click();
  await page.getByLabel('Handoff prompt').fill('Synthetic handoff. token=never-export-this');
  await page.getByRole('button', { name: 'Save edits' }).click();
  await expect(page.getByLabel('Handoff prompt')).toHaveValue('Synthetic handoff. token=[REDACTED]');
  await page.getByRole('button', { name: 'Close handoff' }).click();
  await page.getByRole('button', { name: 'Pull requests', exact: true }).click();
  await expect(page.getByRole('heading', { name: /Closed without merging/ })).toBeVisible();
  await page.getByRole('button', { name: 'Agent sessions', exact: false }).first().click();
  await expect(page.getByRole('button', { name: 'Preview sessions' })).toBeDisabled();
  await page.getByRole('button', { name: 'Overview', exact: true }).click();
  await mkdir('../docs/screenshots', { recursive: true });
  await page.screenshot({ path: '../docs/screenshots/public-demo-overview.png', fullPage: true });
  expect(requests.filter(url => new URL(url).pathname.startsWith('/api'))).toEqual([]);
  expect(errors).toEqual([]);
});
