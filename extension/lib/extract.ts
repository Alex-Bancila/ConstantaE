import type { PageData } from './types';

/**
 * Reads the product data from the current page (owner: Ștefana).
 *
 * Starts with sources many shops share: schema.org Product data in JSON-LD and
 * Open Graph meta tags, then falls back to the large images on the page.
 *
 * TODO(Ștefana):
 * - site-specific selectors for OLX and eMAG where the generic data is missing
 * - seller name and CUI (a regex near "CUI", "CIF", "Cod fiscal")
 * - detect a return policy link
 */
export function extractPage(doc: Document, url: string): PageData {
  const product = findJsonLdProduct(doc);
  const offer = toList(product?.offers).find(isObject);
  const images = unique([...imageUrls(product?.image), ...optional(meta(doc, 'og:image'))]);

  return {
    url,
    site: detectSite(url),
    title: asString(product?.name) ?? meta(doc, 'og:title') ?? (doc.title || null),
    price: toNumber(offer?.price ?? meta(doc, 'product:price:amount')),
    currency: asString(offer?.priceCurrency) ?? meta(doc, 'product:price:currency'),
    images: (images.length > 0 ? images : largeImages(doc)).map((src) => absolute(src, doc)),
    seller: { name: null, cui: null },
    legalLinks: {
      anpc: hasLinkTo(doc, 'anpc.ro'),
      sol: hasLinkTo(doc, 'ec.europa.eu/consumers/odr'),
    },
    hasReturnPolicy: false,
  };
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

function detectSite(url: string): string {
  const host = new URL(url).hostname;
  if (host.endsWith('olx.ro')) return 'olx';
  if (host.endsWith('emag.ro')) return 'emag';
  return host;
}

function hasLinkTo(doc: Document, target: string): boolean {
  return [...doc.links].some((link) => link.href.includes(target));
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
