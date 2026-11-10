import mock from '../../shared/mock-analysis.json';
import type { AnalysisResponse, PageData } from './types';

/** The shared mock response, using the page's real image URLs so badges land on real images. */
export function mockAnalysis(page: PageData): AnalysisResponse {
  const data = mock as AnalysisResponse;
  return {
    ...data,
    images: page.images.map((url, index) => ({
      ...data.images[index % data.images.length]!,
      url,
    })),
  };
}
