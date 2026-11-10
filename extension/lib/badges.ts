import { aiRisk, percent } from './risk';
import type { ImageResult } from './types';

/**
 * Draws an "AI x%" badge over each analysed image (owner: Ștefana).
 *
 * The badges live in a Shadow DOM, so the shop's CSS cannot restyle them.
 *
 * TODO(Ștefana):
 * - move the badges when the page scrolls, resizes or lazy-loads images
 * - match images whose URL on the page differs from the extracted one (e.g. og:image)
 */
export function drawBadges(results: ImageResult[]): void {
  document.getElementById(HOST_ID)?.remove();

  const host = document.createElement('div');
  host.id = HOST_ID;
  host.style.cssText = 'position:absolute;top:0;left:0;z-index:2147483647;pointer-events:none;';
  const root = host.attachShadow({ mode: 'open' });

  for (const result of results) {
    for (const img of findImages(result.url)) {
      root.append(createBadge(img, result.aiProbability));
    }
  }
  document.body.append(host);
}

const HOST_ID = 'constantae-badges';

const COLORS = { high: '#c62828', medium: '#ef6c00', low: '#2e7d32' };

function findImages(url: string): HTMLImageElement[] {
  return [...document.images].filter((img) => img.currentSrc === url || img.src === url);
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
    `background:${COLORS[aiRisk(aiProbability)]}`,
  ].join(';');
  return badge;
}
