import { chromium } from '@playwright/test';
import { copyFile, mkdir, unlink } from 'node:fs/promises';
import { resolve } from 'node:path';
import process from 'node:process';
import { URL } from 'node:url';

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: { dir: resolve('../docs/demo'), size: { width: 1440, height: 900 } },
});
const page = await context.newPage();
const apiRequests = [];
page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api')) apiRequests.push(request.url()); });
try {
  await page.goto(process.env.AWAY_DEMO_URL || 'http://127.0.0.1:4173/');
  await page.getByText('Public demo • precomputed synthetic results • no live inference.').waitFor();
  await page.waitForTimeout(2500);
  await page.locator('.citation').first().click();
  await page.waitForTimeout(2500);
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Pull requests', exact: true }).click();
  await page.waitForTimeout(3500);
  await page.getByRole('button', { name: 'Agent sessions', exact: false }).first().click();
  await page.waitForTimeout(3000);
  await page.getByRole('button', { name: 'Your briefing' }).click();
  await page.getByRole('button', { name: 'Replay demo briefing' }).click();
  await page.getByText('Your briefing is ready. Your acknowledged checkpoint has not changed.').waitFor();
  await page.waitForTimeout(2500);
  await page.getByRole('button', { name: 'Continue with your agent' }).click();
  await page.waitForTimeout(3500);
  await page.getByRole('button', { name: 'Close handoff' }).click();
  await page.waitForTimeout(1000);
  if (apiRequests.length) throw new Error('Public demo made local API requests.');
} finally {
  const video = page.video();
  await context.close();
  if (video) {
    await mkdir(resolve('../docs/demo'), { recursive: true });
    const recording = await video.path();
    await copyFile(recording, resolve('../docs/demo/while-i-was-away-demo.webm'));
    await unlink(recording);
  }
  await browser.close();
}
