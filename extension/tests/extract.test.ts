import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import test, { describe } from 'node:test';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';
import { extractPage, parsePriceText } from '../lib/extract.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const qaPagesDir = path.resolve(__dirname, '../../qa/pages');

function loadDocument(relPath: string, url: string): Document {
  const filePath = path.join(qaPagesDir, relPath);
  const html = readFileSync(filePath, 'utf-8');
  const dom = new JSDOM(html, { url });
  return dom.window.document;
}

describe('OLX listing extraction', () => {
  test('extracts title, price, currency, and all photos for OLX phone listing', () => {
    const url = 'https://www.olx.ro/d/oferta/iphone-15-pro-max-256gb-titanium-sigilat-IDphone.html';
    const doc = loadDocument('olx-phone/product.html', url);
    const data = extractPage(doc, url);

    assert.equal(data.site, 'olx');
    assert.equal(data.title, 'iPhone 15 Pro Max 256GB Titanium Sigilat');
    assert.equal(data.price, 4800);
    assert.equal(data.currency, 'RON');
    assert.equal(data.images.length, 4);
    assert.ok(data.images[0]?.includes('phone-img1.jpg'));
    assert.ok(data.images[1]?.includes('phone-img2.jpg'));
    assert.ok(data.images[2]?.includes('phone-img3.jpg'));
    assert.ok(data.images[3]?.includes('phone-img4.jpg'));
  });

  test('extracts title, price in EUR, and all photos for OLX car listing', () => {
    const url = 'https://www.olx.ro/d/oferta/volkswagen-golf-7-2-0-tdi-dsg-highline-IDcar.html';
    const doc = loadDocument('olx-car/product.html', url);
    const data = extractPage(doc, url);

    assert.equal(data.site, 'olx');
    assert.equal(data.title, 'Volkswagen Golf 7 2.0 TDI DSG Highline');
    assert.equal(data.price, 8500);
    assert.equal(data.currency, 'EUR');
    assert.equal(data.images.length, 3);
    assert.ok(data.images[0]?.includes('car-img1.jpg'));
    assert.ok(data.images[1]?.includes('car-img2.jpg'));
    assert.ok(data.images[2]?.includes('car-img3.jpg'));
  });

  test('extracts title via ad_title selector when og:title is missing, decimal price, and all photos for OLX furniture listing', () => {
    const url = 'https://www.olx.ro/d/oferta/canapea-extensibila-3-locuri-cu-lada-depozitare-IDfurniture.html';
    const doc = loadDocument('olx-furniture/product.html', url);
    const data = extractPage(doc, url);

    assert.equal(data.site, 'olx');
    assert.equal(data.title, 'Canapea extensibila 3 locuri cu lada depozitare');
    assert.equal(data.price, 1250.5);
    assert.equal(data.currency, 'RON');
    assert.equal(data.images.length, 3);
    assert.ok(data.images[0]?.includes('furniture-img1.jpg'));
    assert.ok(data.images[1]?.includes('furniture-img2.jpg'));
    assert.ok(data.images[2]?.includes('furniture-img3.jpg'));
  });

  test('extracts OLX listing properly when served from localhost during testing', () => {
    const url = 'http://localhost:8001/olx-phone/product.html';
    const doc = loadDocument('olx-phone/product.html', url);
    const data = extractPage(doc, url);

    assert.equal(data.site, 'olx');
    assert.equal(data.title, 'iPhone 15 Pro Max 256GB Titanium Sigilat');
    assert.equal(data.price, 4800);
    assert.equal(data.currency, 'RON');
    assert.equal(data.images.length, 4);
  });

  test('detects OLX listing from DOM even if served at root on localhost', () => {
    const url = 'http://localhost:8001/product.html';
    const doc = loadDocument('olx-phone/product.html', url);
    const data = extractPage(doc, url);

    assert.equal(data.site, 'olx');
    assert.equal(data.title, 'iPhone 15 Pro Max 256GB Titanium Sigilat');
    assert.equal(data.price, 4800);
    assert.equal(data.currency, 'RON');
    assert.equal(data.images.length, 4);
  });

  test('preserves generic JSON-LD extraction on standard e-commerce pages', () => {
    const url = 'http://localhost:8001/product.html';
    const doc = loadDocument('sample/product.html', url);
    const data = extractPage(doc, url);

    assert.equal(data.title, 'iPhone 15 Pro, sigilat');
    assert.equal(data.price, 1200);
    assert.equal(data.currency, 'RON');
    assert.equal(data.images.length, 2);
    assert.equal(data.legalLinks.sol, true);
    assert.equal(data.legalLinks.anpc, false);
  });
});

describe('eMAG product page extraction', () => {
  test('extracts title, price, currency, all gallery photos, and ANPC/SOL links for eMAG laptop', () => {
    const url = 'https://www.emag.ro/laptop-gaming-lenovo-legion-5-16irx9-IDlaptop/pd/EXAMP1/';
    const doc = loadDocument('emag-laptop/product.html', url);
    const data = extractPage(doc, url);

    assert.equal(data.site, 'emag');
    assert.equal(data.title, 'Laptop Gaming Lenovo Legion 5 16IRX9 cu procesor Intel Core i7');
    assert.equal(data.price, 5499.99);
    assert.equal(data.currency, 'RON');
    assert.equal(data.images.length, 4);
    assert.ok(data.images[0]?.includes('laptop-1.jpg'));
    assert.ok(data.images[1]?.includes('laptop-2.jpg'));
    assert.ok(data.images[2]?.includes('laptop-3.jpg'));
    assert.ok(data.images[3]?.includes('laptop-4.jpg'));
    assert.equal(data.legalLinks.anpc, true);
    assert.equal(data.legalLinks.sol, true);
  });

  test('extracts title, DOM price, currency, all photos, and ANPC-SAL/SOL links for eMAG TV', () => {
    const url = 'https://www.emag.ro/televizor-samsung-55du7172-4k-IDtv/pd/EXAMP2/';
    const doc = loadDocument('emag-tv/product.html', url);
    const data = extractPage(doc, url);

    assert.equal(data.site, 'emag');
    assert.equal(data.title, 'Televizor Samsung LED 55DU7172, 138 cm, 4K Ultra HD');
    assert.equal(data.price, 2199);
    assert.equal(data.currency, 'RON');
    assert.equal(data.images.length, 3);
    assert.ok(data.images[0]?.includes('tv-1.jpg'));
    assert.ok(data.images[1]?.includes('tv-2.jpg'));
    assert.ok(data.images[2]?.includes('tv-3.jpg'));
    assert.equal(data.legalLinks.anpc, true);
    assert.equal(data.legalLinks.sol, true);
  });

  test('extracts title via page-title selector when og:title is missing, sup decimal price, photos and links for eMAG shoes', () => {
    const url = 'https://www.emag.ro/pantofi-sport-puma-smash-v2-IDshoes/pd/EXAMP3/';
    const doc = loadDocument('emag-shoes/product.html', url);
    const data = extractPage(doc, url);

    assert.equal(data.site, 'emag');
    assert.equal(data.title, 'Pantofi sport Puma Smash v2, Unisex, Negru');
    assert.equal(data.price, 189.5);
    assert.equal(data.currency, 'RON');
    assert.equal(data.images.length, 3);
    assert.ok(data.images[0]?.includes('shoes-1.jpg'));
    assert.ok(data.images[1]?.includes('shoes-2.jpg'));
    assert.ok(data.images[2]?.includes('shoes-3.jpg'));
    assert.equal(data.legalLinks.anpc, true);
    assert.equal(data.legalLinks.sol, true);
  });

  test('detects eMAG page when served from localhost during testing', () => {
    const url = 'http://localhost:8001/emag-laptop/product.html';
    const doc = loadDocument('emag-laptop/product.html', url);
    const data = extractPage(doc, url);

    assert.equal(data.site, 'emag');
    assert.equal(data.title, 'Laptop Gaming Lenovo Legion 5 16IRX9 cu procesor Intel Core i7');
    assert.equal(data.price, 5499.99);
    assert.equal(data.currency, 'RON');
    assert.equal(data.images.length, 4);
    assert.equal(data.legalLinks.anpc, true);
    assert.equal(data.legalLinks.sol, true);
  });
});

describe('parsePriceText', () => {
  test('parses romanian formatted prices with thousands separator', () => {
    assert.deepEqual(parsePriceText('4.800 lei'), { price: 4800, currency: 'RON' });
    assert.deepEqual(parsePriceText('1.250,50 lei'), { price: 1250.5, currency: 'RON' });
    assert.deepEqual(parsePriceText('150 lei'), { price: 150, currency: 'RON' });
  });

  test('parses EUR and USD prices', () => {
    assert.deepEqual(parsePriceText('8.500 €'), { price: 8500, currency: 'EUR' });
    assert.deepEqual(parsePriceText('350 EUR'), { price: 350, currency: 'EUR' });
    assert.deepEqual(parsePriceText('$25'), { price: 25, currency: 'USD' });
  });

  test('parses gratuit / free items', () => {
    assert.deepEqual(parsePriceText('Gratuit'), { price: 0, currency: 'RON' });
  });
});
