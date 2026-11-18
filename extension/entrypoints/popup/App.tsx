import { useEffect, useRef, useState } from 'react';
import { browser } from 'wxt/browser';
import { formatNumber, t } from '@/lib/i18n';
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
  t('errorUnsupportedPage');

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
    if (mode === 'live') setPage(null);
    setState({ kind: 'loading', step: mode === 'demo' ? t('loadingSample') : t('extractingListing') });

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
      if (tab?.id == null) throw new Error(t('errorNoActiveTab'));
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
      setState({ kind: 'loading', step: t('sendingData') });

      let result = await sendToBackground<AnalysisResponse>({ type: 'ANALYZE', page: extracted });
      if (!isCurrent()) return;
      validateAnalysis(result);
      for (let polls = 0; result.status === 'pending' && polls < MAX_POLLS; polls++) {
        setState({ kind: 'loading', step: t('analysisQueued', [String(polls + 1), String(MAX_POLLS)]) });
        await sleep(POLL_INTERVAL_MS);
        if (!isCurrent()) return;
        result = await sendToBackground<AnalysisResponse>({
          type: 'GET_ANALYSIS',
          analysisId: result.analysisId,
        });
        if (!isCurrent()) return;
        validateAnalysis(result);
      }
      if (result.status === 'pending') throw new Error(t('errorAnalysisTimeout'));
      if (result.status === 'failed') throw new Error(t('errorAnalysisFailed'));

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
        <span className="header-caption">{t('productReview')}</span>
      </header>
      <main className="popup-main">
        <div className="listing-toolbar flex items-center justify-between gap-3">
          <p className="listing-source">{page ? page.site?.toUpperCase() || t('unknownSite') : t('currentTab')}{mode === 'demo' && <span>{t('demoListing')}</span>}</p>
          <select className="mode-selector" aria-label={t('analysisMode')} value={mode} onChange={(event) => changeMode(event.currentTarget.value as Mode)}>
            <option value="demo">{t('modeDemo')}</option>
            <option value="live">{t('modeLive')}</option>
          </select>
        </div>
        {page && <ProductHeader page={page}/>}
        {state.kind !== 'loading' && state.kind !== 'error' && <button type="button" className="button button-primary" onClick={() => void analyze()}><Icon name={state.kind === 'done' ? 'refresh' : 'scan'} size={16}/><span>{state.kind === 'done' ? t('analyzeAgain') : mode === 'demo' ? t('runDemoAnalysis') : t('analyzeCurrentPage')}</span></button>}
        <p className="mode-description">{mode === 'demo' ? t('demoDescription') : USE_MOCK ? t('liveMockDescription') : t('liveDescription')}</p>
        {state.kind === 'idle' && <section className="idle-state" aria-label={t('readyToAnalyze')}><h2>{t('readyToAnalyze')}</h2><p>{t('readyDescription')}</p></section>}
        {state.kind === 'loading' && <section className="loading-state flex items-start gap-3" role="status"><span className="loading-icon shrink-0 motion-safe:animate-spin"><Icon name="loader" size={18}/></span><div className="min-w-0"><h2 className="state-title">{t('analyzingProduct')}</h2><p className="state-detail">{state.step}</p></div></section>}
        {state.kind === 'error' && <section className="error-state" role="alert"><div className="error-heading flex items-center gap-2"><Icon name="warning" size={16}/><h2 className="state-title">{t('analysisUnavailable')}</h2></div><p className="error-detail">{state.message}</p><button type="button" onClick={() => void analyze()} className="button button-primary retry-button">{t('tryAgain')}</button></section>}
        {state.kind === 'done' && <AnalysisResults analysis={state.result}/>}
        <footer className="popup-footer">{t('legalDisclaimer')}</footer>
      </main>
    </div>
  );
}

function ProductHeader({ page }: { page: PageData }) {
  const price = page.price == null ? t('priceUnavailable') : [formatNumber(page.price), page.currency].filter(Boolean).join(' ');
  return (
    <section className="product-summary" aria-label={t('currentListing')}>
      <h2>{page.title?.trim() ? page.title : t('untitledListing')}</h2>
      <div className="product-details flex items-baseline justify-between gap-2">
        <span className="product-price">{price}</span>
        <p className="product-seller">{page.seller.name?.trim() ? page.seller.name : t('sellerUnknown')}</p>
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
    throw new Error(t('errorInvalidAnalysis'));
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
