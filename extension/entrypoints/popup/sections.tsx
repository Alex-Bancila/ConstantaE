import { useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { aiRisk, percent } from '@/lib/risk';
import type { AnalysisResponse, ImageResult, LegalReport, TrustReport } from '@/lib/types';

type IconName = 'shield' | 'image' | 'check' | 'warning' | 'scale' | 'arrow' | 'refresh' | 'loader' | 'scan';

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    shield: <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-4"/></>,
    image: <><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></>,
    check: <><path d="m5 12 4 4L19 6"/></>,
    warning: <><path d="m10.3 3.8-8.1 14A2 2 0 0 0 3.9 21h16.2a2 2 0 0 0 1.7-3.2l-8.1-14a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></>,
    scale: <><path d="M12 3v18M5 7h14M5 7l-3 6a4 4 0 0 0 6 0L5 7Zm14 0-3 6a4 4 0 0 0 6 0l-3-6ZM7 21h10"/></>,
    arrow: <><path d="M15 3h6v6M10 14 21 3"/><path d="M21 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6"/></>,
    refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5 9a8 8 0 0 1 14-2l1 5M4 12l1 5a8 8 0 0 0 14-2"/></>,
    loader: <><path d="M12 2a10 10 0 0 1 10 10"/></>,
    scan: <><path d="M7 3H5a2 2 0 0 0-2 2v2m14-4h2a2 2 0 0 1 2 2v2M3 17v2a2 2 0 0 0 2 2h2m10 0h2a2 2 0 0 0 2-2v-2"/><circle cx="12" cy="12" r="3"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

function scoreColor(score: number) {
  if (score < 50) return 'score-low';
  if (score < 75) return 'score-caution';
  return 'score-good';
}

function citationUrl(link: unknown): string | null {
  if (typeof link !== 'string') return null;
  try {
    const parsed = new URL(link);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : null;
  } catch {
    return null;
  }
}

export function ImagesSection({ images }: { images: ImageResult[] }) {
  return (
    <section className="report-section" aria-labelledby="image-heading">
      <div className="section-heading flex items-baseline justify-between gap-3">
        <h3 className="section-title" id="image-heading">Image analysis</h3>
        <span className="section-count">{images.length} {images.length === 1 ? 'image' : 'images'}</span>
      </div>
      {!images.length ? (
        <p className="muted">No images were returned for this listing.</p>
      ) : (
        <div className="space-y-3">
          {images.map((item, index) => {
            const probability = Math.max(0, Math.min(1, item.aiProbability));
            const risk = aiRisk(probability);
            const estimate = percent(probability);
            return (
              <div className="image-row flex items-start gap-3" key={`${item.url}-${index}`}>
                <div className="image-thumbnail relative flex shrink-0 items-center justify-center overflow-hidden">
                  <Icon name="image" size={20}/>
                  {item.url && <img className="absolute inset-0 h-full w-full object-cover" src={item.url} alt={`Product image ${index + 1}`} loading="lazy" onError={(event) => { event.currentTarget.style.display = 'none'; }}/>}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="image-label">Product image {index + 1}</p>
                    <p className={`image-probability ${risk === 'high' ? 'score-low' : risk === 'medium' ? 'score-caution' : 'muted'}`}>{estimate}</p>
                  </div>
                  <p className="image-description">AI likelihood</p>
                  <div className="probability-track" aria-hidden="true"><div className={`probability-fill probability-${risk}`} style={{ width: estimate }}/></div>
                  {item.signals.length > 0 && <p className="image-signals">{item.signals.join(' · ')}</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <p className="section-note">AI scores are estimates, not proof an image was generated artificially.</p>
    </section>
  );
}

export function TrustSection({ trust }: { trust: TrustReport | null }) {
  return (
    <section className="report-section" aria-labelledby="trust-heading">
      <div className="section-heading flex items-baseline justify-between gap-3">
        <h3 className="section-title" id="trust-heading">Seller trust check</h3>
        {trust && <span className={`trust-score ${scoreColor(trust.score)}`}>{trust.score}/100</span>}
      </div>
      {!trust ? <p className="muted">No trust assessment available.</p> : (
        <>
          <p className="trust-description">Indicative trust score. Not a safety guarantee.</p>
          <div className="space-y-3">
            {trust.checks.length === 0 ? <p className="muted">No trust checks were returned.</p> : trust.checks.map((check) => (
              <div key={check.id} className="flex items-start gap-2">
                <span className={`trust-check-icon shrink-0 ${check.passed ? 'score-good' : 'score-caution'}`}><Icon name={check.passed ? 'check' : 'warning'} size={16}/></span>
                <p><span className="sr-only">{check.passed ? 'Passed: ' : 'Needs review: '}</span>{check.message}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

export function LegalSection({ legal }: { legal: LegalReport | null }) {
  return (
    <section className="report-section" aria-labelledby="legal-heading">
      <h3 className="section-title" id="legal-heading">Legal report</h3>
      {!legal ? <p className="muted">No legal report available yet.</p> : (
        <>
          <p>{legal.summary}</p>
          <div className="citations space-y-4">
            {legal.citations.length === 0 ? <p className="muted">No verified citations returned.</p> : legal.citations.map((citation, index) => {
              const link = citationUrl(citation.link);
              return (
                <div key={`${citation.law}-${citation.article}-${index}`} className="citation">
                  <p className="citation-heading">{citation.law}{' '}<span className="citation-article">{citation.article}</span></p>
                  <p className="citation-text">{citation.text}</p>
                  {link && <a className="citation-link inline-flex items-center gap-2" href={link} target="_blank" rel="noopener noreferrer">Open legislation <Icon name="arrow" size={14}/></a>}
                </div>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}

const resultTabs = [
  { id: 'images', label: 'Images' },
  { id: 'seller', label: 'Seller' },
  { id: 'legal', label: 'Legal' },
] as const;

export function AnalysisResults({ analysis }: { analysis: AnalysisResponse }) {
  const [activeTab, setActiveTab] = useState<typeof resultTabs[number]['id']>('images');
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const images = analysis.images ?? [];
  const highestProbability = images.length ? images.reduce((highest, image) => (
    Math.max(highest, Math.round(Math.max(0, Math.min(1, image.aiProbability)) * 100))
  ), 0) : null;

  function navigateTabs(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    let next: number;
    switch (event.key) {
      case 'ArrowRight': next = (index + 1) % resultTabs.length; break;
      case 'ArrowLeft': next = (index + resultTabs.length - 1) % resultTabs.length; break;
      case 'Home': next = 0; break;
      case 'End': next = resultTabs.length - 1; break;
      default: return;
    }
    const nextTab = resultTabs[next];
    if (!nextTab) return;
    event.preventDefault();
    setActiveTab(nextTab.id);
    tabRefs.current[next]?.focus();
  }

  return (
    <section className="analysis-results" aria-labelledby="overview-heading">
      <div className="overview-heading flex items-center justify-between gap-3">
        <h2 id="overview-heading">Analysis overview</h2>
        <p className="completion-status flex items-center gap-1" role="status"><Icon name="check" size={14}/>Complete</p>
      </div>
      <dl className="overview-metrics grid grid-cols-3 gap-3">
        <div><dt>Highest AI estimate</dt><dd>{highestProbability == null ? 'N/A' : `${highestProbability}%`}</dd></div>
        <div><dt>Seller score</dt><dd>{analysis.trust ? `${analysis.trust.score}/100` : 'N/A'}</dd></div>
        <div><dt>Legal sources</dt><dd>{analysis.legal ? analysis.legal.citations.length : 'N/A'}</dd></div>
      </dl>
      <div className="results-tabs grid grid-cols-3 gap-1" role="tablist" aria-label="Analysis results">
        {resultTabs.map((tab, index) => (
          <button
            key={tab.id}
            ref={(element) => { tabRefs.current[index] = element; }}
            type="button"
            role="tab"
            id={`result-tab-${tab.id}`}
            aria-controls={`result-panel-${tab.id}`}
            aria-selected={activeTab === tab.id}
            tabIndex={activeTab === tab.id ? 0 : -1}
            className="result-tab"
            onClick={() => setActiveTab(tab.id)}
            onKeyDown={(event) => navigateTabs(event, index)}
          >{tab.label}</button>
        ))}
      </div>
      <div className="result-panel" role="tabpanel" id="result-panel-images" aria-labelledby="result-tab-images" tabIndex={0} hidden={activeTab !== 'images'}>
        <ImagesSection images={analysis.images}/>
      </div>
      <div className="result-panel" role="tabpanel" id="result-panel-seller" aria-labelledby="result-tab-seller" tabIndex={0} hidden={activeTab !== 'seller'}>
        <TrustSection trust={analysis.trust}/>
      </div>
      <div className="result-panel" role="tabpanel" id="result-panel-legal" aria-labelledby="result-tab-legal" tabIndex={0} hidden={activeTab !== 'legal'}>
        <LegalSection legal={analysis.legal}/>
      </div>
    </section>
  );
}
