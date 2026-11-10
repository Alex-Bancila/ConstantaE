import type { ReactNode } from 'react';
import { aiRisk, percent } from '@/lib/risk';
import type { ImageResult, LegalReport, TrustReport } from '@/lib/types';

// The three result sections of the popup (owner: Filip).

const RISK_STYLES = {
  high: 'bg-red-100 text-red-800',
  medium: 'bg-orange-100 text-orange-800',
  low: 'bg-green-100 text-green-800',
};

export function ImagesSection({ images }: { images: ImageResult[] }) {
  return (
    <Section title="AI-generated images">
      {images.length === 0 && <p className="text-slate-500">No product images found.</p>}
      <ul className="space-y-2">
        {images.map((image) => (
          <li key={image.url} className="flex items-center gap-3">
            <img src={image.url} alt="" className="size-12 rounded object-cover" />
            <div className="min-w-0 flex-1">
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${RISK_STYLES[aiRisk(image.aiProbability)]}`}
              >
                AI {percent(image.aiProbability)}
              </span>
              <p className="truncate text-xs text-slate-500">{image.signals.join(' · ')}</p>
            </div>
          </li>
        ))}
      </ul>
    </Section>
  );
}

export function TrustSection({ trust }: { trust: TrustReport }) {
  return (
    <Section title={`Seller trust: ${trust.score}/100`}>
      <ul className="space-y-1">
        {trust.checks.map((check) => (
          <li key={check.id} className="flex gap-2">
            <span className={check.passed ? 'text-green-700' : 'text-red-700'}>
              {check.passed ? '✓' : '✗'}
            </span>
            {check.message}
          </li>
        ))}
      </ul>
    </Section>
  );
}

export function LegalSection({ legal }: { legal: LegalReport }) {
  return (
    <Section title="Your rights">
      <p>{legal.summary}</p>
      <ul className="mt-2 space-y-1">
        {legal.citations.map((citation) => (
          <li key={`${citation.law}-${citation.article}`}>
            <details>
              <summary className="cursor-pointer font-medium">
                {citation.law}, {citation.article}
              </summary>
              <p className="mt-1 text-slate-600">{citation.text}</p>
              <a
                href={citation.link}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-blue-700 underline"
              >
                Read the full law
              </a>
            </details>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 p-3">
      <h2 className="mb-2 font-semibold">{title}</h2>
      {children}
    </section>
  );
}
