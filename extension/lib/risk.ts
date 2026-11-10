export type AiRisk = 'high' | 'medium' | 'low';

/** Turns an AI probability into a level the UI can colour. */
export function aiRisk(aiProbability: number): AiRisk {
  if (aiProbability >= 0.7) return 'high';
  if (aiProbability >= 0.4) return 'medium';
  return 'low';
}

export function percent(aiProbability: number): string {
  return `${Math.round(aiProbability * 100)}%`;
}
