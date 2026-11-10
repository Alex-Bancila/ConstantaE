// End-to-end smoke test (owner: Ovidiu). See qa/README.md for how to run it.
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
const extensionDir = path.resolve(here, '../../extension/.output/chrome-mv3');
const screenshots = path.join(here, 'screenshots');
const PAGE_URL = 'http://localhost:8001/product.html';

mkdirSync(screenshots, { recursive: true });

const context = await chromium.launchPersistentContext('', {
  channel: 'chromium', // headless Chromium that can load extensions
  executablePath: process.env.CHROME_PATH, // optional: use a Chromium you already have
  args: [`--disable-extensions-except=${extensionDir}`, `--load-extension=${extensionDir}`],
});

try {
  const [existingWorker] = context.serviceWorkers();
  const worker = existingWorker ?? (await context.waitForEvent('serviceworker'));
  const extensionId = new URL(worker.url()).host;

  const shop = await context.newPage();
  await shop.goto(PAGE_URL);

  // Opened as a tab, the popup would analyse its own tab, so point its tab lookup at the shop.
  const popup = await context.newPage();
  await popup.addInitScript((url) => {
    const query = chrome.tabs.query.bind(chrome.tabs);
    chrome.tabs.query = () => query({ url: `${new URL(url).origin}/*` });
  }, PAGE_URL);
  await popup.setViewportSize({ width: 432, height: 900 });
  await popup.goto(`chrome-extension://${extensionId}/popup.html`);

  for (const section of ['AI-generated images', 'Seller trust', 'Your rights']) {
    await popup.getByText(section).waitFor({ timeout: 15_000 });
  }
  await popup.screenshot({ path: path.join(screenshots, 'popup.png'), fullPage: true });

  const badges = await shop.evaluate(() =>
    [...(document.getElementById('constantae-badges')?.shadowRoot?.children ?? [])].map(
      (badge) => badge.textContent,
    ),
  );
  assert.equal(badges.length, 2, `expected 2 badges, got ${JSON.stringify(badges)}`);
  await shop.bringToFront();
  await shop.screenshot({ path: path.join(screenshots, 'page.png') });

  console.log('Smoke test passed. Badges:', badges.join(', '));
} finally {
  await context.close();
}
