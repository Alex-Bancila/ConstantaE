import { browser } from 'wxt/browser';
import type { ImageResult, PageData } from './types';

/** Every message the parts of the extension send each other. */
export type Message =
  | { type: 'EXTRACT_PAGE' } // popup -> content script
  | { type: 'SHOW_BADGES'; images: ImageResult[] } // popup -> content script
  | { type: 'ANALYZE'; page: PageData } // popup -> background
  | { type: 'GET_ANALYSIS'; analysisId: string }; // popup -> background

/** Errors can't cross the message boundary, so replies carry them as data. */
export type Reply<T> = { ok: true; data: T } | { ok: false; error: string };

/** Runs `work` in a message listener and sends its result or error back. */
export async function reply<T>(
  work: () => T | Promise<T>,
  sendResponse: (reply: Reply<T>) => void,
): Promise<void> {
  try {
    sendResponse({ ok: true, data: await work() });
  } catch (error) {
    sendResponse({ ok: false, error: errorMessage(error) });
  }
}

export async function sendToBackground<T>(message: Message): Promise<T> {
  return unwrap<T>(await browser.runtime.sendMessage(message));
}

export async function sendToTab<T>(tabId: number, message: Message): Promise<T> {
  return unwrap<T>(await browser.tabs.sendMessage(tabId, message));
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function unwrap<T>(reply: Reply<T> | undefined): T {
  if (!reply) throw new Error('No reply from the other side of the extension.');
  if (!reply.ok) throw new Error(reply.error);
  return reply.data;
}
