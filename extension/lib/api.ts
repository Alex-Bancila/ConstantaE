import { t } from './i18n';
import { mockAnalysis } from './mock';
import type { AnalysisResponse, PageData } from './types';

export const API_URL = import.meta.env.WXT_API_URL ?? 'http://localhost:8000';
const USE_MOCK = import.meta.env.WXT_USE_MOCK === 'true';

export async function analyzePage(page: PageData): Promise<AnalysisResponse> {
  if (USE_MOCK) return mockAnalysis(page);
  return request<AnalysisResponse>('/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(page),
  });
}

export async function getAnalysis(analysisId: string): Promise<AnalysisResponse> {
  if (USE_MOCK) throw new Error(t('errorMockPending'));
  return request<AnalysisResponse>(`/analyze/${encodeURIComponent(analysisId)}`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error(t('errorBackendUnreachable', API_URL));
  }
  if (!response.ok) throw new Error(t('errorBackendHttp', [String(response.status), path]));
  return (await response.json()) as T;
}
