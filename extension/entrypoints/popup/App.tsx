import { useEffect, useRef, useState } from 'react';
import { browser } from 'wxt/browser';
import examplePage from '../../../shared/example-page.json';
import { errorMessage, sendToBackground, sendToTab } from '@/lib/messages';
import { mockAnalysis } from '@/lib/mock';
import type { AnalysisResponse, PageData } from '@/lib/types';
import { AnalysisResults, Icon } from './sections';

type Mode = 'demo' | 'live';
type State =
  | { kind: 'idle' }
  | { kind: 'loading'; step: string }
  | { kind: 'error'; message: string }
  | { kind: 'done'; result: AnalysisResponse };

const demoPage: PageData = examplePage;
const POLL_INTERVAL_MS = 1000;
const MAX_POLLS = 60;
const USE_MOCK = import.meta.env.WXT_USE_MOCK === 'true';
const UNSUPPORTED_PAGE_MESSAGE =
  'Product information could not be read from this page. Open an OLX or eMAG product listing, or the sample page on localhost, and try again. You can also use Demo mode.';

export default function App() {
  const [mode, setMode] = useState<Mode>('demo');
  const [state, setState] = useState<State>({ kind: 'idle' });
  const [page, setPage] = useState<PageData | null>(demoPage);
  const activeAnalysis = useRef<object | null>(null);

  useEffect(() => () => { activeAnalysis.current = null; }, []);

  async function analyze() {
    if (activeAnalysis.current) return;
    const request = {};
    activeAnalysis.current = request;
    const isCurrent = () => activeAnalysis.current === request;
    setState({ kind: 'loading', step: mode === 'demo' ? 'Loading sample analysis...' : 'Extracting listing data...' });

    try {
      if (mode === 'demo') {
        await sleep(900);
        if (!isCurrent()) return;
        setPage(demoPage);
        setState({ kind: 'done', result: mockAnalysis(demoPage) });
        return;
      }

      const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
      if (!isCurrent()) return;
      if (tab?.id == null) throw new Error('No active browser tab found. Open a product listing or use Demo mode.');
      const tabId = tab.id;

      let extracted: PageData;
      try {
        extracted = await sendToTab<PageData>(tabId, { type: 'EXTRACT_PAGE' });
      } catch {
        throw new Error(UNSUPPORTED_PAGE_MESSAGE);
      }
      if (!isCurrent()) return;
      validatePage(extracted);
      setPage(extracted);
      setState({ kind: 'loading', step: 'Sending data to backend...' });

      let result = await sendToBackground<AnalysisResponse>({ type: 'ANALYZE', page: extracted });
      if (!isCurrent()) return;
      validateAnalysis(result);
      for (let polls = 0; result.status === 'pending' && polls < MAX_POLLS; polls++) {
        setState({ kind: 'loading', step: `Analysis queued · checking results (${polls + 1}/${MAX_POLLS})` });
        await sleep(POLL_INTERVAL_MS);
        if (!isCurrent()) return;
        result = await sendToBackground<AnalysisResponse>({
          type: 'GET_ANALYSIS',
          analysisId: result.analysisId,
        });
        if (!isCurrent()) return;
        validateAnalysis(result);
      }
      if (result.status === 'pending') throw new Error('The analysis is taking too long. Try again.');
      if (result.status === 'failed') throw new Error('The analysis failed. Please try again.');

      setState({ kind: 'done', result });
      // Badge delivery remains best-effort and targets the tab that was extracted.
      await sendToTab(tabId, { type: 'SHOW_BADGES', images: result.images }).catch(() => undefined);
    } catch (error: unknown) {
      if (!isCurrent()) return;
      setState({ kind: 'error', message: errorMessage(error) });
    } finally {
      if (isCurrent()) activeAnalysis.current = null;
    }
  }

  function changeMode(nextMode: Mode) {
    // Invalidate every awaited stage of the previous request, including polling.
    activeAnalysis.current = null;
    setMode(nextMode);
    setState({ kind: 'idle' });
    setPage(nextMode === 'demo' ? demoPage : null);
  }

  return (
    <div className="popup-shell">
      <header className="popup-header flex items-center justify-between gap-3">
        <div className="brand flex items-center gap-2"><span className="brand-mark"><Icon name="scan" size={18}/></span><h1>SafeBuy</h1></div>
        <span className="header-caption">Product review</span>
      </header>
      <main className="popup-main">
        <div className="listing-toolbar flex items-center justify-between gap-3">
          <p className="listing-source">{mode === 'demo' || state.kind === 'done' ? page?.site?.toUpperCase() || 'Unknown site' : 'Current tab'}{mode === 'demo' && <span>Demo listing</span>}</p>
          <select className="mode-selector" aria-label="Analysis mode" value={mode} onChange={(event) => changeMode(event.currentTarget.value as Mode)}>
            <option value="demo">Demo</option>
            <option value="live">Live</option>
          </select>
        </div>
        {page && (mode === 'demo' || state.kind === 'done') && <ProductHeader page={page}/>}
        {state.kind !== 'loading' && <button type="button" className={`button ${state.kind === 'error' ? 'button-secondary' : 'button-primary'}`} onClick={() => void analyze()}><Icon name={state.kind === 'done' ? 'refresh' : 'scan'} size={16}/><span>{state.kind === 'done' ? 'Analyze again' : mode === 'demo' ? 'Run demo analysis' : 'Analyze current product page'}</span></button>}
        <p className="mode-description">{mode === 'demo' ? 'Sample data only. Nothing is sent to the analysis service.' : USE_MOCK ? 'Current page with simulated results. Nothing is sent to the analysis service.' : 'Listing details are sent to the configured analysis service.'}</p>
        {state.kind === 'idle' && <section className="idle-state" aria-label="Ready to analyze"><h2>Ready to analyze</h2><p>Image estimates, seller checks and legal sources appear here after analysis.</p></section>}
        {state.kind === 'loading' && <section className="loading-state flex items-start gap-3" role="status"><span className="loading-icon shrink-0 motion-safe:animate-spin"><Icon name="loader" size={18}/></span><div className="min-w-0"><h2 className="state-title">Analyzing product...</h2><p className="state-detail">{state.step}</p></div></section>}
        {state.kind === 'error' && <section className="error-state" role="alert"><div className="error-heading flex items-center gap-2"><Icon name="warning" size={16}/><h2 className="state-title">Analysis unavailable</h2></div><p className="error-detail">{state.message}</p><button type="button" onClick={() => void analyze()} className="button button-primary retry-button">Try again</button></section>}
        {state.kind === 'done' && <AnalysisResults analysis={state.result}/>}
        <footer className="popup-footer">This is not legal advice. Results require human review.</footer>
      </main>
    </div>
  );
}

function ProductHeader({ page }: { page: PageData }) {
  const price = page.price == null ? 'Price unavailable' : [page.price.toLocaleString('en-US'), page.currency].filter(Boolean).join(' ');
  return (
    <section className="product-summary" aria-label="Current listing">
      <h2>{page.title || 'Untitled listing'}</h2>
      <div className="product-details flex items-baseline justify-between gap-2">
        <span className="product-price">{price}</span>
        <p className="product-seller">{page.seller.name || 'Seller unknown'}</p>
      </div>
    </section>
  );
}

function validatePage(page: PageData): void {
  if (!page || typeof page.url !== 'string' || !page.url.trim()
    || !page.seller || !page.legalLinks
    || ![page.site, page.title, page.currency, page.seller.name, page.seller.cui].every((value) => value === null || typeof value === 'string')
    || (page.price !== null && !Number.isFinite(page.price))
    || !Array.isArray(page.images) || page.images.some((image) => typeof image !== 'string')
    || typeof page.legalLinks.anpc !== 'boolean' || typeof page.legalLinks.sol !== 'boolean'
    || typeof page.hasReturnPolicy !== 'boolean') {
    throw new Error(UNSUPPORTED_PAGE_MESSAGE);
  }
}

function validateAnalysis(data: AnalysisResponse): void {
  if (!data || typeof data.analysisId !== 'string' || !data.analysisId.trim()
    || !['pending', 'done', 'failed'].includes(data.status)
    || !Array.isArray(data.images) || data.images.some((image) => (
      !image || typeof image.url !== 'string' || !Number.isFinite(image.aiProbability)
      || !Array.isArray(image.signals) || image.signals.some((signal) => typeof signal !== 'string')
    ))
    || (data.trust !== null && (!data.trust || !Number.isFinite(data.trust.score) || !Array.isArray(data.trust.checks)
      || data.trust.checks.some((check) => (
        !check || typeof check.id !== 'string' || typeof check.passed !== 'boolean' || typeof check.message !== 'string'
      ))))
    || (data.legal !== null && (!data.legal || typeof data.legal.summary !== 'string' || !Array.isArray(data.legal.citations)
      || data.legal.citations.some((citation) => (
        !citation || typeof citation.law !== 'string' || typeof citation.article !== 'string' || typeof citation.text !== 'string'
      ))))) {
    throw new Error('The backend returned an invalid analysis result. Please try again.');
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
