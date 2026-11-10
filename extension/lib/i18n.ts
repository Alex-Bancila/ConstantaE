import { browser } from 'wxt/browser';
import type messages from '../public/_locales/ro/messages.json';

export type UiLanguage = 'ro' | 'en';
export type MessageKey = keyof typeof messages;

/** Use the browser UI language, independently of the page or preferred website languages. */
export function getUiLanguage(): UiLanguage {
  const language = browser.i18n.getUILanguage().toLowerCase().replaceAll('_', '-');
  return language === 'en' || language.startsWith('en-') ? 'en' : 'ro';
}

/** Native catalogs select English variants or fall back to manifest.default_locale (Romanian). */
export function t(key: MessageKey, substitutions?: string | string[]): string {
  return browser.i18n.getMessage(key, substitutions);
}

export function formatNumber(value: number): string {
  return value.toLocaleString(getUiLanguage() === 'en' ? 'en-US' : 'ro-RO');
}

/** Romanian uses one/few/other; translate the entire count phrase, including "de". */
export function formatImageCount(count: number): string {
  const category = new Intl.PluralRules(getUiLanguage()).select(count);
  const key = category === 'one' ? 'imageCountOne' : category === 'few' ? 'imageCountFew' : 'imageCountOther';
  return t(key, formatNumber(count));
}
