import assert from 'node:assert/strict';
import { existsSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import test, { after, before } from 'node:test';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const here = path.dirname(fileURLToPath(import.meta.url));
const extensionDir = path.resolve(here, '../../extension/.output/chrome-mv3');
const screenshots = path.join(here, 'screenshots');
const baseUrl = process.env.BASE_URL || 'http://localhost:8001';

mkdirSync(screenshots, { recursive: true });

const DEMO_PAGES = [
  {
    id: 'legitimate-shop',
    name: 'Legitimate shop (eMAG style)',
    url: `${baseUrl}/legitimate-shop/product.html`,
    expectedBadges: 3,
  },
  {
    id: 'ai-photos',
    name: 'Listing with AI photos',
    url: `${baseUrl}/ai-photos/product.html`,
    expectedBadges: 2,
  },
  {
    id: 'suspicious-seller',
    name: 'Suspicious seller (fake iPhone)',
    url: `${baseUrl}/suspicious-seller/product.html`,
    expectedBadges: 1,
  },
  {
    id: 'marketplace-individual',
    name: 'Marketplace individual seller (OLX style)',
    url: `${baseUrl}/marketplace-individual/product.html`,
    expectedBadges: 2,
  },
  {
    id: 'sample',
    name: 'Starter sample page',
    url: `${baseUrl}/sample/product.html`,
    expectedBadges: 2,
  },
];

const selectedPageId = process.env.TEST_PAGE;
const pagesToTest = selectedPageId
  ? DEMO_PAGES.filter((p) => p.id === selectedPageId)
  : DEMO_PAGES;

if (pagesToTest.length === 0) {
  throw new Error(`Unknown TEST_PAGE: ${selectedPageId}. Available: ${DEMO_PAGES.map((p) => p.id).join(', ')}`);
}

let context;
let extensionId;

before(async () => {
  if (!existsSync(extensionDir)) {
    throw new Error(
      `Extension build not found at ${extensionDir}. Run 'npm run build' inside extension/ before running tests.`
    );
  }

  context = await chromium.launchPersistentContext('', {
    channel: 'chromium',
    executablePath: process.env.CHROME_PATH,
    args: [`--disable-extensions-except=${extensionDir}`, `--load-extension=${extensionDir}`],
  });

  const [existingWorker] = context.serviceWorkers();
  const worker = existingWorker ?? (await context.waitForEvent('serviceworker', { timeout: 15_000 }));
  extensionId = new URL(worker.url()).host;
});

after(async () => {
  if (context) {
    await context.close();
  }
});

for (const page of pagesToTest) {
  test(`${page.name} (${page.id})`, async () => {
    const shop = await context.newPage();
    const popup = await context.newPage();

    try {
      let targetUrl = page.url;
      try {
        await shop.goto(targetUrl, { waitUntil: 'load', timeout: 15_000 });
      } catch (err) {
        if (page.id === 'sample') {
          targetUrl = `${baseUrl}/product.html`;
          await shop.goto(targetUrl, { waitUntil: 'load', timeout: 15_000 });
        } else {
          throw err;
        }
      }

      await popup.addInitScript((url) => {
        const query = chrome.tabs.query.bind(chrome.tabs);
        chrome.tabs.query = () => query({ url: `${new URL(url).origin}/*` });
      }, targetUrl);

      await popup.setViewportSize({ width: 432, height: 900 });
      await popup.goto(`chrome-extension://${extensionId}/popup.html`);

      for (const section of ['AI-generated images', 'Seller trust', 'Your rights']) {
        await popup.getByText(section).waitFor({ timeout: 15_000 });
      }

      await popup.screenshot({
        path: path.join(screenshots, `${page.id}-popup.png`),
        fullPage: true,
      });

      const badges = await shop.evaluate(() =>
        [...(document.getElementById('constantae-badges')?.shadowRoot?.children ?? [])].map(
          (badge) => badge.textContent,
        ),
      );

      assert.equal(
        badges.length,
        page.expectedBadges,
        `[${page.id}] expected ${page.expectedBadges} badges, got ${JSON.stringify(badges)}`
      );

      for (const badge of badges) {
        assert.match(badge, /^AI \d+%/, `[${page.id}] expected AI percentage badge format, got: ${badge}`);
      }

      await shop.bringToFront();
      await shop.screenshot({ path: path.join(screenshots, `${page.id}-page.png`) });
    } finally {
      await popup.close();
      await shop.close();
    }
  });
}
