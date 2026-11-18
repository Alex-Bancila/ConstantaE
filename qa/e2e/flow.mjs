// Runs the whole flow on the demo pages without a browser (owner: David, issue #16).
//
// For each page in qa/pages it reads the page the way the extension does
// (extension/lib/extract.ts), sends the result to POST /analyze and prints what came
// back. When the page has an expected.json, the answer is compared with it.
//
//   node qa/e2e/flow.mjs [page-id ...]
//
// Needs the backend (API_URL, default http://localhost:8000) and the demo pages served
// with `python -m http.server 8001 --directory qa/pages` (BASE_URL, default
// http://localhost:8001). Run `npm ci` in extension/ once first.
// Exits with 1 if any compared page differs from its expected.json.

import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const pagesDir = path.resolve(here, '../pages');
const extensionDir = path.resolve(here, '../../extension');
const apiUrl = process.env.API_URL || 'http://localhost:8000';
const baseUrl = process.env.BASE_URL || 'http://localhost:8001';

const { JSDOM } = createRequire(path.join(extensionDir, 'package.json'))('jsdom');
const { extractPage } = await import(pathToFileURL(path.join(extensionDir, 'lib/extract.ts')));

const DEMO_PAGES = [
  'legitimate-shop',
  'ai-photos',
  'suspicious-seller',
  'marketplace-individual',
  'sample',
];
const ids = process.argv.slice(2).length ? process.argv.slice(2) : DEMO_PAGES;

async function analyze(id) {
  const url = `${baseUrl}/${id}/product.html`;
  const html = readFileSync(path.join(pagesDir, id, 'product.html'), 'utf-8');
  const page = extractPage(new JSDOM(html, { url }).window.document, url);

  const started = Date.now();
  const response = await fetch(`${apiUrl}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(page),
  });
  if (!response.ok) throw new Error(`POST /analyze answered ${response.status}`);
  let result = await response.json();
  // With ASYNC=true the first answer is "pending": poll like the popup does.
  for (let i = 0; result.status === 'pending' && i < 60; i++) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    result = await (await fetch(`${apiUrl}/analyze/${result.analysisId}`)).json();
  }
  return { page, result, seconds: (Date.now() - started) / 1000 };
}

function compare(id, page, result) {
  const file = path.join(pagesDir, id, 'expected.json');
  if (!existsSync(file)) return null;
  const expected = JSON.parse(readFileSync(file, 'utf-8')).expectedAnalysis;
  const problems = [];

  if (result.status !== expected.status) {
    problems.push(`status is ${result.status}, expected ${expected.status}`);
  }
  expected.images.forEach((image, index) => {
    const actual = result.images[index];
    const [low, high] = image.aiProbabilityRange;
    if (!actual) problems.push(`image ${index + 1} missing`);
    else if (actual.aiProbability < low || actual.aiProbability > high) {
      problems.push(
        `image ${index + 1} (${image.url}): AI ${actual.aiProbability.toFixed(2)}, expected ${low}-${high}` +
          (actual.signals.length ? ` [${actual.signals.join('; ')}]` : ''),
      );
    }
  });
  if (result.images.length !== expected.images.length) {
    problems.push(`${result.images.length} images analysed, expected ${expected.images.length}`);
  }

  // The page is served over http://localhost, so the https check fails by design.
  const isHttps = page.url.startsWith('https://');
  for (const [checkId, want] of Object.entries(expected.trust.checks)) {
    const actual = result.trust?.checks.find((check) => check.id === checkId);
    const wanted = checkId === 'https' && !isHttps ? false : want.passed;
    if (!actual) problems.push(`trust check ${checkId} missing`);
    else if (actual.passed !== wanted) {
      problems.push(`trust check ${checkId}: passed=${actual.passed}, expected ${wanted}`);
    }
  }
  // Which articles the summary cites is up to the LLM, so a missing citation is only a
  // note. A missing report is a problem.
  if (!result.legal) problems.push('no legal report');
  else {
    const have = result.legal.citations.map((c) => `${c.law} ${c.article}`);
    for (const c of expected.legal.citations) {
      if (!have.includes(`${c.law} ${c.article}`)) {
        console.log(`  note: legal report does not cite ${c.law} ${c.article}`);
      }
    }
  }  return problems;
}

let failed = false;
for (const id of ids) {
  console.log(`\n=== ${id}`);
  try {
    const { page, result, seconds } = await analyze(id);
    console.log(`${page.title} | ${page.price} ${page.currency} | seller: ${page.seller.name} (${page.seller.cui})`);
    console.log(`took ${seconds.toFixed(1)} s, status ${result.status}`);
    for (const image of result.images) {
      const note = image.signals.length ? `  [${image.signals.join('; ')}]` : '';
      console.log(`  image ${path.basename(image.url)}: AI ${Math.round(image.aiProbability * 100)}%${note}`);
    }
    console.log(`  trust score: ${result.trust?.score ?? 'none'}`);
    for (const check of result.trust?.checks ?? []) {
      console.log(`    ${check.passed ? 'pass' : 'FAIL'} ${check.id}: ${check.message}`);
    }
    console.log(`  legal: ${result.legal ? result.legal.summary.slice(0, 300) : 'none'}`);
    for (const c of result.legal?.citations ?? []) console.log(`    - ${c.law} ${c.article}`);

    const problems = compare(id, page, result);
    if (problems === null) console.log('  (no expected.json to compare with)');
    else if (problems.length === 0) console.log('  MATCHES expected.json');
    else {
      failed = true;
      console.log('  DIFFERS from expected.json:');
      for (const problem of problems) console.log(`    * ${problem}`);
    }
  } catch (error) {
    failed = true;
    console.log(`  ERROR: ${error.message}`);
  }
}
process.exit(failed ? 1 : 0);
