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

  // Use the extension's messages so the same selectors work in Romanian and English.
  const labels = await popup.evaluate(() => ({
    analysisMode: chrome.i18n.getMessage('analysisMode'),
    analyzeCurrentPage: chrome.i18n.getMessage('analyzeCurrentPage'),
    analysisOverview: chrome.i18n.getMessage('analysisOverview'),
    tabImages: chrome.i18n.getMessage('tabImages'),
    tabSeller: chrome.i18n.getMessage('tabSeller'),
    tabLegal: chrome.i18n.getMessage('tabLegal'),
    imageAnalysis: chrome.i18n.getMessage('imageAnalysis'),
    sellerTrustCheck: chrome.i18n.getMessage('sellerTrustCheck'),
    legalReport: chrome.i18n.getMessage('legalReport'),
    openLegislation: chrome.i18n.getMessage('openLegislation'),
  }));

  await popup.getByRole('combobox', { name: labels.analysisMode, exact: true }).selectOption('live');
  await popup.getByRole('button', { name: labels.analyzeCurrentPage, exact: true }).click();
  await popup.getByRole('heading', { name: labels.analysisOverview, exact: true }).waitFor({ timeout: 75_000 });

  await popup.getByRole('tab', { name: labels.tabImages, exact: true }).click();
  const imagesPanel = popup.getByRole('tabpanel', { name: labels.tabImages, exact: true });
  await imagesPanel.getByRole('heading', { name: labels.imageAnalysis, exact: true }).waitFor();
  assert.equal(await imagesPanel.getByRole('img').count(), 2, 'expected two analyzed product images');

  await popup.getByRole('tab', { name: labels.tabSeller, exact: true }).click();
  const sellerPanel = popup.getByRole('tabpanel', { name: labels.tabSeller, exact: true });
  await sellerPanel.getByRole('heading', { name: labels.sellerTrustCheck, exact: true }).waitFor();
  await sellerPanel.getByText(/^\d+(?:[.,]\d+)?\/100$/).waitFor();

  await popup.getByRole('tab', { name: labels.tabLegal, exact: true }).click();
  const legalPanel = popup.getByRole('tabpanel', { name: labels.tabLegal, exact: true });
  await legalPanel.getByRole('heading', { name: labels.legalReport, exact: true }).waitFor();
  await legalPanel.getByRole('link', { name: labels.openLegislation, exact: true }).first().waitFor();
  await popup.screenshot({ path: path.join(screenshots, 'popup.png'), fullPage: true });

  await shop.waitForFunction(() =>
    document.getElementById('constantae-badges')?.shadowRoot?.children.length === 2,
  );
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
