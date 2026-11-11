import assert from 'node:assert/strict';
import test, { describe } from 'node:test';
import { JSDOM } from 'jsdom';
import { drawBadges, isImageMatch, normalizeImageUrl, urlsMatch } from '../lib/badges.ts';

describe('Image URL matching', () => {
  test('matches exact URLs', () => {
    assert.equal(urlsMatch('https://example.com/img.jpg', 'https://example.com/img.jpg'), true);
  });

  test('matches OLX images with different resize suffixes and subdomains', () => {
    const extracted = 'https://frankfurt.apollo.olxcdn.com/v1/files/abc123xyz/image;s=1000x700';
    const onPage = 'https://apollo.olxcdn.com/v1/files/abc123xyz/image;s=644x461';
    const thumbnail = 'https://apollo.olxcdn.com/v1/files/abc123xyz/image';

    assert.equal(urlsMatch(extracted, onPage), true);
    assert.equal(urlsMatch(extracted, thumbnail), true);
  });

  test('does not match different OLX files', () => {
    const file1 = 'https://apollo.olxcdn.com/v1/files/image111/image;s=1000x700';
    const file2 = 'https://apollo.olxcdn.com/v1/files/image222/image;s=1000x700';
    assert.equal(urlsMatch(file1, file2), false);
  });

  test('matches eMAG images with different size variants or query params', () => {
    const extracted = 'https://s13emagst.akamaized.net/products/123/res_large_photo.jpg';
    const onPage = 'https://s13emagst.akamaized.net/products/123/res_small_photo.jpg';
    const withQuery = 'https://s13emagst.akamaized.net/products/123/res_large_photo.jpg?width=400';

    assert.equal(urlsMatch(extracted, onPage), true);
    assert.equal(urlsMatch(extracted, withQuery), true);
  });

  test('matches candidate from img srcset attribute', () => {
    const dom = new JSDOM(`
      <html>
        <body>
          <img src="small.jpg" srcset="small.jpg 300w, https://example.com/large.jpg 1000w" />
        </body>
      </html>
    `, { url: 'https://example.com/product.html' });

    const img = dom.window.document.querySelector('img')!;
    assert.equal(isImageMatch('https://example.com/large.jpg', img), true);
    assert.equal(isImageMatch('https://example.com/other.jpg', img), false);
  });
});

describe('Badge rendering and non-blocking clicks', () => {
  test('creates shadow root and badge with pointer-events: none', () => {
    const dom = new JSDOM(`
      <!doctype html>
      <html>
        <body>
          <img src="https://example.com/photo.jpg" width="300" height="300" />
        </body>
      </html>
    `, { url: 'https://example.com/product.html' });

    // Polyfill window & document for badges.ts in JSDOM environment
    globalThis.window = dom.window as unknown as Window & typeof globalThis;
    globalThis.document = dom.window.document;
    globalThis.MutationObserver = dom.window.MutationObserver;
    globalThis.MutationObserver = dom.window.MutationObserver;

    drawBadges([
      { url: 'https://example.com/photo.jpg', aiProbability: 0.85, signals: ['fake'] },
    ]);

    const host = document.getElementById('constantae-badges');
    assert.ok(host, 'host element exists');
    assert.ok(host.style.pointerEvents.includes('none'), 'host has pointer-events: none');

    const badge = host.shadowRoot?.children[0] as HTMLElement;
    assert.ok(badge, 'badge element exists in shadow DOM');
    assert.equal(badge.textContent, 'AI 85%');
    assert.ok(badge.style.pointerEvents.includes('none'), 'badge element has pointer-events: none');
  });

  test('attaches badge to lazy-loaded image added dynamically via MutationObserver', async () => {
    const dom = new JSDOM(`
      <!doctype html>
      <html>
        <body>
          <div id="container"></div>
        </body>
      </html>
    `, { url: 'https://example.com/product.html' });

    globalThis.window = dom.window as unknown as Window & typeof globalThis;
    globalThis.document = dom.window.document;
    globalThis.MutationObserver = dom.window.MutationObserver;

    drawBadges([
      { url: 'https://example.com/lazy.jpg', aiProbability: 0.12, signals: [] },
    ]);

    const host = document.getElementById('constantae-badges')!;
    assert.equal(host.shadowRoot?.children.length, 0);

    // Dynamically insert image
    const img = document.createElement('img');
    img.src = 'https://example.com/lazy.jpg';
    document.getElementById('container')!.appendChild(img);

    // Wait for mutation observer tick
    await new Promise((resolve) => setTimeout(resolve, 20));

    assert.equal(host.shadowRoot?.children.length, 1);
    const badge = host.shadowRoot?.children[0] as HTMLElement;
    assert.equal(badge.textContent, 'AI 12%');
  });
});
