import { aiRisk, percent } from './risk.ts';
import type { ImageResult } from './types';

/**
 * Draws an "AI x%" badge over each analysed image (owner: Ștefana).
 *
 * The badges live in a Shadow DOM, so the shop's CSS cannot restyle them.
 * Badges follow images on scroll, window resize, and dynamic/lazy loading,
 * matching image URLs across different resolutions and CDNs without blocking clicks.
 */

const HOST_ID = 'constantae-badges';
const COLORS = { high: '#c62828', medium: '#ef6c00', low: '#2e7d32' };

let teardown: (() => void) | null = null;

export function drawBadges(results: ImageResult[]): void {
  // Clean up any existing listeners, observers, and host
  teardown?.();
  document.getElementById(HOST_ID)?.remove();

  if (results.length === 0) return;

  const host = document.createElement('div');
  host.id = HOST_ID;
  host.style.cssText = 'position:absolute;top:0;left:0;z-index:2147483647;pointer-events:none;';
  const root = host.attachShadow({ mode: 'open' });

  const activeBadges = new Map<HTMLImageElement, HTMLElement>();

  function updatePositions(): void {
    for (const [img, badge] of activeBadges.entries()) {
      if (!document.contains(img)) {
        badge.remove();
        activeBadges.delete(img);
        continue;
      }
      positionBadge(badge, img);
    }
  }

  function scanAndAttach(): void {
    for (const result of results) {
      for (const img of document.images) {
        if (activeBadges.has(img)) continue;
        if (isImageMatch(result.url, img)) {
          const badge = createBadge(img, result.aiProbability);
          activeBadges.set(img, badge);
          root.append(badge);
          positionBadge(badge, img);

          if (!img.complete) {
            img.addEventListener('load', () => positionBadge(badge, img), { once: true });
          }
        }
      }
    }
  }

  // Initial scan & attach
  scanAndAttach();
  document.body.append(host);

  // Position updates on scroll & resize
  const onScrollOrResize = () => {
    updatePositions();
  };

  window.addEventListener('scroll', onScrollOrResize, { passive: true });
  window.addEventListener('resize', onScrollOrResize, { passive: true });

  // Observe DOM for lazy loading, carousel slide transitions, and image changes
  const ObserverClass =
    typeof MutationObserver !== 'undefined'
      ? MutationObserver
      : typeof window !== 'undefined' && 'MutationObserver' in window
        ? window.MutationObserver
        : null;

  let observer: MutationObserver | null = null;
  if (ObserverClass) {
    observer = new ObserverClass(() => {
      scanAndAttach();
      updatePositions();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['src', 'srcset', 'class', 'style'],
    });
  }

  teardown = () => {
    window.removeEventListener('scroll', onScrollOrResize);
    window.removeEventListener('resize', onScrollOrResize);
    observer?.disconnect();
    activeBadges.clear();
    teardown = null;
  };
}

function positionBadge(badge: HTMLElement, img: HTMLImageElement): void {
  const rect = img.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0 || img.offsetParent === null) {
    badge.style.display = 'none';
    return;
  }
  badge.style.display = 'block';
  badge.style.top = `${rect.top + window.scrollY + 8}px`;
  badge.style.left = `${rect.left + window.scrollX + 8}px`;
}

function createBadge(img: HTMLImageElement, aiProbability: number): HTMLElement {
  const rect = img.getBoundingClientRect();
  const badge = document.createElement('div');
  badge.textContent = `AI ${percent(aiProbability)}`;
  badge.style.cssText = [
    'position:absolute',
    `top:${rect.top + window.scrollY + 8}px`,
    `left:${rect.left + window.scrollX + 8}px`,
    'padding:2px 8px',
    'white-space:nowrap',
    'border-radius:999px',
    'font:600 12px/1.6 system-ui, sans-serif',
    'color:#fff',
    'pointer-events:none',
    'user-select:none',
    `background:${COLORS[aiRisk(aiProbability)]}`,
  ].join(';');
  return badge;
}

export function isImageMatch(extractedUrl: string, img: HTMLImageElement): boolean {
  const candidates: string[] = [];
  if (img.currentSrc) candidates.push(img.currentSrc);
  if (img.src) candidates.push(img.src);
  const attrSrc = img.getAttribute('src');
  if (attrSrc) candidates.push(attrSrc);
  const dataSrc = img.getAttribute('data-src');
  if (dataSrc) candidates.push(dataSrc);

  const srcset = img.getAttribute('srcset') || img.srcset;
  if (srcset) {
    const parsed = srcset
      .split(',')
      .map((entry) => entry.trim().split(/\s+/)[0])
      .filter((url): url is string => Boolean(url));
    candidates.push(...parsed);
  }

  for (const candidate of candidates) {
    if (urlsMatch(extractedUrl, candidate)) {
      return true;
    }
  }

  return false;
}

export function urlsMatch(url1: string, url2: string): boolean {
  if (url1 === url2) return true;

  const abs1 = toAbsolute(url1);
  const abs2 = toAbsolute(url2);
  if (abs1 === abs2) return true;

  const olxId1 = extractOlxFileId(abs1);
  const olxId2 = extractOlxFileId(abs2);
  if (olxId1 && olxId2 && olxId1 === olxId2) {
    return true;
  }

  if (normalizeImageUrl(abs1) === normalizeImageUrl(abs2)) {
    return true;
  }

  return false;
}

function extractOlxFileId(url: string): string | null {
  const match = url.match(/\/files\/([^/;]+)/i);
  return match && match[1] ? match[1] : null;
}

export function normalizeImageUrl(url: string, baseURI?: string): string {
  try {
    const base = baseURI ?? (typeof document !== 'undefined' && document.baseURI ? document.baseURI : 'https://localhost/');
    const parsed = new URL(url, base);
    let path = parsed.pathname;

    // OLX resize param e.g. ;s=1000x700
    path = path.replace(/;s=\d+x\d+/i, '');

    // eMAG / Akamai prefixes: res_small_ / res_large_ -> res_
    path = path.replace(/\/res_[a-z0-9_]+?_([a-z0-9_]+\.[a-z0-9]+)$/i, '/res_$1');

    // Remove dimension suffixes like -300x300, _644x461
    path = path.replace(/[-_]\d+x\d+(\.[a-z0-9]+)$/i, '$1');

    return `${parsed.origin}${path}`;
  } catch {
    const withoutQuery = url.split('?')[0] ?? '';
    const withoutHash = withoutQuery.split('#')[0] ?? '';
    let path = withoutHash.replace(/;s=\d+x\d+/i, '');
    path = path.replace(/\/res_[a-z0-9_]+?_([a-z0-9_]+\.[a-z0-9]+)$/i, '/res_$1');
    path = path.replace(/[-_]\d+x\d+(\.[a-z0-9]+)$/i, '$1');
    return path;
  }
}

function toAbsolute(url: string): string {
  try {
    const base = typeof document !== 'undefined' && document.baseURI ? document.baseURI : 'https://localhost/';
    return new URL(url, base).href;
  } catch {
    return url;
  }
}
