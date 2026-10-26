import { test, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';

test.skip(process.env.AWAY_PUBLIC_DEMO === '1', 'Local application flow; public demo is verified separately.');

test('complete synthetic demo: source traceability, PR groups, editable handoff, acknowledgment and history', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: 'Connections', exact: false }).click();
  await page.getByRole('button', { name: 'Explore the demo' }).click();
  await expect(page.getByRole('heading', { name: 'Pick up the thread.' })).toBeVisible();
  await expect(page.getByText('SYNTHETIC DEMO', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'A good place to begin.' })).toBeVisible();
  await mkdir('../docs/screenshots', { recursive: true });
  await page.screenshot({ path: '../docs/screenshots/demo-overview.png', fullPage: true });

  await page.locator('.citation').first().click();
  await expect(page.getByRole('dialog', { name: /./ }).first()).toBeVisible();
  await expect(page.locator('.evidence-body')).toBeVisible();
  await page.screenshot({ path: '../docs/screenshots/demo-evidence.png' });
  await page.keyboard.press('Escape');
  await expect(page.locator('.evidence-dialog')).not.toBeVisible();

  await page.getByRole('button', { name: 'Continue with your agent' }).click();
  await expect(page.getByLabel('Handoff prompt')).not.toHaveValue('');
  const existing = await page.getByLabel('Handoff prompt').inputValue();
  await page.getByLabel('Handoff prompt').fill(`${existing}\n\nReviewer note: keep the historical test timestamp.`);
  await page.getByRole('button', { name: 'Save edits' }).click();
  await expect(page.getByText('Saved. Likely secrets were redacted. Review before sharing.')).toBeVisible();
  await page.screenshot({ path: '../docs/screenshots/demo-handoff.png' });
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export Markdown' }).click();
  expect((await downloadPromise).suggestedFilename()).toContain('.md');
  await page.getByRole('button', { name: 'Close handoff' }).click();

  await page.getByRole('button', { name: 'Pull requests', exact: true }).click();
  for (const heading of ['Open for review', 'Drafts', 'Merged', 'Closed without merging']) await expect(page.getByRole('heading', { name: new RegExp(heading) })).toBeVisible();
  await page.screenshot({ path: '../docs/screenshots/demo-pull-requests.png', fullPage: true });

  await page.getByRole('button', { name: 'Agent sessions', exact: false }).first().click();
  await expect(page.getByRole('heading', { name: /Imported context/ })).toBeVisible();
  await page.getByRole('button', { name: 'Your briefing' }).click();
  await page.getByRole('button', { name: 'Refresh briefing' }).click();
  await expect(page.getByText('Your briefing is ready. Your acknowledged checkpoint has not changed.')).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'Acknowledge briefing' }).click();
  await expect(page.getByRole('button', { name: 'Acknowledged', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: 'Briefing history' }).click();
  await expect(page.locator('.history-row').first()).toBeVisible();
  await page.locator('.history-row').first().click();
  await expect(page.getByText(/Viewing a historical briefing/)).toBeVisible();
  expect(errors).toEqual([]);
});

test('mobile demo has no horizontal overflow and navigation remains operable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Connections', exact: false }).click();
  await page.getByRole('button', { name: 'Explore the demo' }).click();
  await expect(page.getByRole('heading', { name: 'A good place to begin.' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: '../docs/screenshots/demo-mobile.png', fullPage: true });
  await page.getByRole('button', { name: 'Continue with your agent' }).click();
  await expect(page.getByLabel('Handoff prompt')).toBeVisible();
  await page.getByRole('button', { name: 'Close handoff' }).click();
});
