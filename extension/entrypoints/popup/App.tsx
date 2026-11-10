import { useEffect, useState } from 'react';
import { errorMessage, sendToBackground, sendToTab } from '@/lib/messages';
import type { AnalysisResponse, PageData } from '@/lib/types';
import { ImagesSection, LegalSection, TrustSection } from './sections';

// The popup (owner: Filip): reads the page, asks the backend, shows the results.

type State =
  | { kind: 'loading'; step: string }
  | { kind: 'error'; message: string }
  | { kind: 'done'; result: AnalysisResponse };

const POLL_INTERVAL_MS = 1000;
const MAX_POLLS = 60;

export default function App() {
  const [state, setState] = useState<State>({ kind: 'loading', step: 'Reading the page…' });

  useEffect(() => {
    analyzeActiveTab(setState).catch((error: unknown) =>
      setState({ kind: 'error', message: errorMessage(error) }),
    );
  }, []);

  return (
    <main className="w-[400px] space-y-4 bg-white p-4 text-sm text-slate-800">
      <h1 className="text-lg font-semibold">ConstantaE</h1>

      {state.kind === 'loading' && <p className="text-slate-500">{state.step}</p>}
      {state.kind === 'error' && <p className="text-red-700">{state.message}</p>}
      {state.kind === 'done' && (
        <>
          <ImagesSection images={state.result.images} />
          {state.result.trust && <TrustSection trust={state.result.trust} />}
          {state.result.legal && <LegalSection legal={state.result.legal} />}
        </>
      )}

      <footer className="border-t border-slate-200 pt-2 text-xs text-slate-500">
        This is not legal advice.
      </footer>
    </main>
  );
}

async function analyzeActiveTab(setState: (state: State) => void): Promise<void> {
  const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
  if (tab?.id === undefined) throw new Error('No active tab.');
  const tabId = tab.id;

  let page: PageData;
  try {
    page = await sendToTab<PageData>(tabId, { type: 'EXTRACT_PAGE' });
  } catch {
    throw new Error('Open a product page on a supported site (OLX, eMAG) and try again.');
  }

  setState({ kind: 'loading', step: 'Analyzing…' });
  let result = await sendToBackground<AnalysisResponse>({ type: 'ANALYZE', page });
  for (let polls = 0; result.status === 'pending' && polls < MAX_POLLS; polls++) {
    await sleep(POLL_INTERVAL_MS);
    result = await sendToBackground<AnalysisResponse>({
      type: 'GET_ANALYSIS',
      analysisId: result.analysisId,
    });
  }
  if (result.status === 'pending') throw new Error('The analysis is taking too long. Try again.');
  if (result.status === 'failed') throw new Error('The analysis failed.');

  setState({ kind: 'done', result });
  await sendToTab(tabId, { type: 'SHOW_BADGES', images: result.images }).catch(() => undefined);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
