import { analyzePage, getAnalysis } from '@/lib/api';
import { type Message, reply } from '@/lib/messages';

// All backend calls go through the background worker (owner: Filip). Calls made
// from inside the shop's page would be blocked by the browser's CORS rules.
export default defineBackground(() => {
  browser.runtime.onMessage.addListener((message: Message, _sender, sendResponse) => {
    switch (message.type) {
      case 'ANALYZE':
        void reply(() => analyzePage(message.page), sendResponse);
        return true;
      case 'GET_ANALYSIS':
        void reply(() => getAnalysis(message.analysisId), sendResponse);
        return true;
      default:
        return false;
    }
  });
});
