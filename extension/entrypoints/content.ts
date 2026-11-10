import { drawBadges } from '@/lib/badges';
import { extractPage } from '@/lib/extract';
import { type Message, reply } from '@/lib/messages';

// Runs inside the shop's page (owner: Ștefana).
export default defineContentScript({
  // localhost is for the saved test pages in qa/pages.
  matches: ['*://*.olx.ro/*', '*://*.emag.ro/*', '*://localhost/*'],
  main() {
    browser.runtime.onMessage.addListener((message: Message, _sender, sendResponse) => {
      switch (message.type) {
        case 'EXTRACT_PAGE':
          void reply(() => extractPage(document, location.href), sendResponse);
          return true;
        case 'SHOW_BADGES':
          void reply(() => drawBadges(message.images), sendResponse);
          return true;
        default:
          return false;
      }
    });
  },
});
