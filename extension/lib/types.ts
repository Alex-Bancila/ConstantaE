// The API contract with the backend. Keep in sync with backend/app/schemas.py,
// docs/api-contract.md and shared/*.json.

export interface Seller {
  name: string | null;
  cui: string | null;
}

export interface LegalLinks {
  anpc: boolean;
  sol: boolean;
}

/** What the content script extracts from a product page. */
export interface PageData {
  url: string;
  site: string | null;
  title: string | null;
  price: number | null;
  currency: string | null;
  images: string[];
  seller: Seller;
  legalLinks: LegalLinks;
  hasReturnPolicy: boolean;
}

export interface ImageResult {
  url: string;
  /** 0 = surely a real photo, 1 = surely AI-generated. */
  aiProbability: number;
  signals: string[];
}

export interface TrustCheck {
  id: string;
  passed: boolean;
  message: string;
}

export interface TrustReport {
  /** 0-100, higher is more trustworthy. */
  score: number;
  checks: TrustCheck[];
}

export interface Citation {
  law: string;
  article: string;
  text: string;
  link: string;
}

export interface LegalReport {
  summary: string;
  citations: Citation[];
}

export type AnalysisStatus = 'pending' | 'done' | 'failed';

export interface AnalysisResponse {
  analysisId: string;
  status: AnalysisStatus;
  images: ImageResult[];
  trust: TrustReport | null;
  legal: LegalReport | null;
}
