import type { PageData } from './types';

/**
 * Reads the product data from the current page (owner: Ștefana).
 *
 * Starts with sources many shops share: schema.org Product data in JSON-LD and
 * Open Graph meta tags, then falls back to site-specific selectors where the
 * generic data is missing.
 */
export function extractPage(doc: Document, url: string): PageData {
  const site = detectSite(url, doc);
  const product = findJsonLdProduct(doc);
  const offer = toList(product?.offers).find(isObject);

  // 1. Title: generic JSON-LD -> generic og:title -> site-specific selector -> doc.title
  const title =
    asString(product?.name) ??
    meta(doc, 'og:title') ??
    (site === 'olx' ? olxTitle(doc) : site === 'emag' ? emagTitle(doc) : null) ??
    (doc.title || null);

  // 2. Price & Currency: generic JSON-LD offer -> generic Open Graph -> site-specific selector
  let price = toNumber(offer?.price ?? meta(doc, 'product:price:amount'));
  let currency = asString(offer?.priceCurrency) ?? meta(doc, 'product:price:currency');

  if (price === null || currency === null) {
    if (site === 'olx') {
      const olx = olxPrice(doc);
      if (price === null) price = olx.price;
      if (currency === null) currency = olx.currency;
    } else if (site === 'emag') {
      const emag = emagPrice(doc);
      if (price === null) price = emag.price;
      if (currency === null) currency = emag.currency;
    }
  }

  // 3. Images: generic JSON-LD image list (when multiple) -> site-specific gallery -> og:image / largeImages
  const jsonLdImages = imageUrls(product?.image);
  let images: string[];
  if (jsonLdImages.length > 1) {
    images = jsonLdImages;
  } else if (site === 'olx') {
    const olxImgs = olxImages(doc);
    images = olxImgs.length > 0 ? olxImgs : unique([...jsonLdImages, ...optional(meta(doc, 'og:image'))]);
  } else if (site === 'emag') {
    const emagImgs = emagImages(doc);
    images = emagImgs.length > 0 ? emagImgs : unique([...jsonLdImages, ...optional(meta(doc, 'og:image'))]);
  } else {
    images = unique([...jsonLdImages, ...optional(meta(doc, 'og:image'))]);
  }

  if (images.length === 0) {
    images = largeImages(doc);
  }

  // 4. Seller: name (OLX person/company or eMAG vendor) and CUI
  let sellerName: string | null = null;
  if (site === 'olx') {
    sellerName = extractOlxSellerName(doc);
  } else if (site === 'emag') {
    sellerName = extractEmagSellerName(doc, offer);
  } else {
    const s = offer?.seller;
    if (isObject(s) && isString(s.name)) {
      sellerName = s.name.trim();
    }
  }

  const cui = extractCui(doc.body?.textContent ?? '');

  return {
    url,
    site,
    title,
    price,
    currency,
    images: images.map((src) => absolute(src, doc)),
    seller: { name: sellerName, cui },
    legalLinks: {
      anpc: hasLinkTo(doc, 'anpc.ro'),
      sol: hasLinkTo(doc, 'ec.europa.eu/consumers/odr'),
    },
    hasReturnPolicy: detectReturnPolicy(doc),
  };
}

export function detectReturnPolicy(doc: Document): boolean {
  const returnRegex = /politica\s+de\s+retur|drept(?:ul)?\s+de\s+retragere|\bretur\b|returnar/i;

  for (const link of doc.links) {
    const href = (link.href || link.getAttribute('href') || '').toLowerCase();
    const text = (link.textContent || '').trim();

    if (href.includes('retur') || href.includes('retragere') || href.includes('return')) {
      return true;
    }
    if (returnRegex.test(text)) {
      return true;
    }
  }

  const bodyText = doc.body?.textContent ?? '';
  return returnRegex.test(bodyText);
}

export function extractCui(text: string): string | null {
  const match = text.match(
    /(?:cod\s+unic\s+de\s+[iî]nregistrare|cod\s+fiscal|c\.?u\.?i\.?|c\.?i\.?f\.?)[:\s\-]+((?:RO\s*)?\d{2,10})\b/i,
  );
  if (!match || !match[1]) return null;
  return match[1].replace(/\s+/g, '').toUpperCase();
}

function extractOlxSellerName(doc: Document): string | null {
  const userCard = doc.querySelector<HTMLElement>(
    '[data-testid="user-profile-link"], [data-cy="seller-card"], [data-testid="seller-card"], [data-testid="ad-contact-profile-card"]',
  );
  if (userCard) {
    const heading = userCard.querySelector<HTMLElement>('h1, h2, h3, h4, h5, [class*="name"]');
    const name = (heading?.textContent || userCard.textContent)?.trim();
    if (name) return name;
  }
  const userLink = doc.querySelector<HTMLElement>('a[href*="/d/user/"], a[href*="/oferte/user/"]');
  return userLink?.textContent?.trim() || null;
}

function extractEmagSellerName(doc: Document, offer?: JsonObject): string | null {
  const sellerObj = offer?.seller;
  if (isObject(sellerObj) && isString(sellerObj.name)) {
    return sellerObj.name.trim();
  }

  const vendorLink = doc.querySelector<HTMLElement>(
    '.product-vendor-details a, [data-test="seller-name"], .seller-name, a[href*="/magazin/"], a[href*="/seller/"]',
  );
  if (vendorLink?.textContent?.trim()) {
    return vendorLink.textContent.trim();
  }

  const vendorEl = doc.querySelector<HTMLElement>('.product-vendor-details, [class*="vendor"]');
  if (vendorEl?.textContent) {
    const match = vendorEl.textContent.match(/v[aâ]ndut\s+(?:[sș]i\s+livrat\s+)?de[:\s]+([^,\n<]+)/i);
    if (match && match[1]) {
      return match[1].trim();
    }
  }

  return null;
}

function emagTitle(doc: Document): string | null {
  const element = doc.querySelector<HTMLElement>('h1.page-title, [class*="page-title"], h1');
  const text = element?.textContent?.trim();
  return text || null;
}

function emagPrice(doc: Document): { price: number | null; currency: string | null } {
  const element = doc.querySelector<HTMLElement>('.product-new-price, [data-test="product-price"]');
  if (!element) return { price: null, currency: null };

  const sup = element.querySelector('sup');
  if (sup && sup.textContent) {
    const decimals = sup.textContent.trim();
    const clone = element.cloneNode(true) as HTMLElement;
    clone.querySelector('sup')?.remove();
    const mainText = clone.textContent?.trim() ?? '';
    return parsePriceText(`${mainText.replace(/lei/i, '')},${decimals} Lei`);
  }
  return parsePriceText(element.textContent ?? '');
}

function emagImages(doc: Document): string[] {
  const selectors = [
    '.product-gallery a.product-gallery-image',
    '.product-gallery-thumbnails a',
    '.product-gallery-thumbnails img',
    '.product-gallery img',
    '[data-ph-element="gallery"] img',
  ].join(', ');

  const elements = doc.querySelectorAll<HTMLElement>(selectors);
  const urls: string[] = [];

  for (const el of elements) {
    const tag = el.tagName.toLowerCase();
    if (tag === 'a') {
      const href = el.getAttribute('href') || (el as HTMLAnchorElement).href;
      if (href && /\.(jpe?g|png|webp|avif)/i.test(href)) {
        urls.push(href);
      }
    } else if (tag === 'img') {
      const src =
        el.getAttribute('src') ||
        (el as HTMLImageElement).currentSrc ||
        (el as HTMLImageElement).src ||
        el.getAttribute('data-src');
      if (src && !src.startsWith('data:image/svg')) {
        urls.push(src);
      }
    }
  }

  return unique(urls);
}

function olxTitle(doc: Document): string | null {
  const element = doc.querySelector<HTMLElement>(
    '[data-cy="ad_title"], [data-testid="ad-title"], [data-testid="ad_title"]',
  );
  const text = element?.textContent?.trim();
  return text || null;
}

function olxPrice(doc: Document): { price: number | null; currency: string | null } {
  const element = doc.querySelector<HTMLElement>(
    '[data-testid="ad-price-container"], [data-cy="ad_price"], [data-testid="ad-price"]',
  );
  if (!element) return { price: null, currency: null };
  return parsePriceText(element.textContent ?? '');
}

export function parsePriceText(raw: string): { price: number | null; currency: string | null } {
  const trimmed = raw.trim();
  if (!trimmed) return { price: null, currency: null };

  let currency: string | null = null;
  const lower = trimmed.toLowerCase();
  if (/(\blei\b|\bron\b)/i.test(lower)) {
    currency = 'RON';
  } else if (/(\beur\b|\beuro\b|€)/i.test(lower)) {
    currency = 'EUR';
  } else if (/(\busd\b|\$)/i.test(lower)) {
    currency = 'USD';
  }

  if (/gratuit/i.test(lower)) {
    return { price: 0, currency: currency ?? 'RON' };
  }

  const match = trimmed.match(/([\d\s.,]+)/);
  if (!match || !match[1]) return { price: null, currency };

  let numStr = match[1].trim().replace(/\s+/g, '');

  if (numStr.includes('.') && numStr.includes(',')) {
    numStr = numStr.replace(/\./g, '').replace(',', '.');
  } else if (numStr.includes(',')) {
    const parts = numStr.split(',');
    if (parts.length > 2 || (parts.length === 2 && parts[1]?.length === 3)) {
      numStr = numStr.replace(/,/g, '');
    } else {
      numStr = numStr.replace(',', '.');
    }
  } else if (numStr.includes('.')) {
    const parts = numStr.split('.');
    if (parts.length > 2 || (parts.length === 2 && parts[1]?.length === 3)) {
      numStr = numStr.replace(/\./g, '');
    }
  }

  const price = Number.parseFloat(numStr);
  return {
    price: Number.isFinite(price) ? price : null,
    currency,
  };
}

function olxImages(doc: Document): string[] {
  const elements = doc.querySelectorAll<HTMLImageElement>(
    [
      '[data-testid="swiper-image-wrapper"] img',
      'div[data-cy="adPhotos-swiperSlide"] img',
      'div[data-testid="gallery-image"] img',
      'div[data-cy="adPageGallery"] img',
      '.swiper-slide img',
      '[data-testid="ad-photo"] img',
    ].join(', '),
  );

  const urls: string[] = [];
  for (const img of elements) {
    const src =
      img.getAttribute('src') ||
      img.currentSrc ||
      img.src ||
      img.getAttribute('data-src');
    if (src && !src.startsWith('data:image/svg')) {
      urls.push(src);
    }
  }
  return unique(urls);
}

type JsonObject = Record<string, unknown>;

const MIN_IMAGE_SIZE = 300;
const MAX_FALLBACK_IMAGES = 5;

function findJsonLdProduct(doc: Document): JsonObject | undefined {
  for (const script of doc.querySelectorAll('script[type="application/ld+json"]')) {
    let data: unknown;
    try {
      data = JSON.parse(script.textContent ?? '');
    } catch {
      continue;
    }
    const product = flattenJsonLd(data).find((node) => toList(node['@type']).includes('Product'));
    if (product) return product;
  }
  return undefined;
}

function flattenJsonLd(data: unknown): JsonObject[] {
  if (Array.isArray(data)) return data.flatMap(flattenJsonLd);
  if (!isObject(data)) return [];
  return [data, ...flattenJsonLd(data['@graph'])];
}

/** JSON-LD images can be a URL, a list of URLs or ImageObjects with a `url`. */
function imageUrls(value: unknown): string[] {
  return toList(value)
    .map((image) => (isObject(image) ? image.url : image))
    .filter(isString);
}

function largeImages(doc: Document): string[] {
  return [...doc.images]
    .filter((img) => img.naturalWidth >= MIN_IMAGE_SIZE && img.naturalHeight >= MIN_IMAGE_SIZE)
    .map((img) => img.currentSrc || img.src)
    .slice(0, MAX_FALLBACK_IMAGES);
}

function detectSite(url: string, doc?: Document): string {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname;
    if (host.endsWith('olx.ro') || host === 'olx.ro') return 'olx';
    if (host.endsWith('emag.ro') || host === 'emag.ro') return 'emag';
    if (host === 'localhost' || host === '127.0.0.1') {
      if (parsed.pathname.includes('olx')) return 'olx';
      if (parsed.pathname.includes('emag')) return 'emag';
      if (doc) {
        if (doc.title?.toLowerCase().includes('olx.ro')) return 'olx';
        if (doc.title?.toLowerCase().includes('emag.ro')) return 'emag';
        if (doc.querySelector('[data-cy="ad_title"], [data-testid="ad-price-container"]')) {
          return 'olx';
        }
        if (doc.querySelector('.product-gallery, .product-new-price, .page-title')) {
          return 'emag';
        }
      }
    }
    return host;
  } catch {
    return 'unknown';
  }
}

function hasLinkTo(doc: Document, target: string): boolean {
  return [...doc.links].some((link) => {
    const href = link.href || link.getAttribute('href') || '';
    return href.includes(target);
  });
}

function meta(doc: Document, property: string): string | null {
  const element = doc.querySelector<HTMLMetaElement>(
    `meta[property="${property}"], meta[name="${property}"]`,
  );
  return element?.content || null;
}

function absolute(src: string, doc: Document): string {
  return new URL(src, doc.baseURI).href;
}

function toNumber(value: unknown): number | null {
  const number = typeof value === 'number' ? value : Number.parseFloat(String(value ?? ''));
  return Number.isFinite(number) ? number : null;
}

function toList(value: unknown): unknown[] {
  if (value === undefined || value === null) return [];
  return Array.isArray(value) ? value : [value];
}

function optional<T>(value: T | null): T[] {
  return value === null ? [] : [value];
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}

function asString(value: unknown): string | null {
  return isString(value) ? value : null;
}

function isString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

function isObject(value: unknown): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
