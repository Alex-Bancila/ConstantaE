# Extension

Built with [WXT](https://wxt.dev) (Manifest V3), React, TypeScript and Tailwind.

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | Opens Chrome with the extension loaded; reloads on save |
| `npm run dev:firefox` | The same in Firefox |
| `npm run build` | Production build in `.output/chrome-mv3` |
| `npm run zip` | Packaged `.zip` for sharing or the Chrome Web Store |
| `npm run compile` | Type-check |

Settings live in `.env` (copy `.env.example`): `WXT_API_URL` is the backend address,
and `WXT_USE_MOCK=true` uses the shared mock data instead of the backend.

## Files

| File | What it does | Owner |
|---|---|---|
| `entrypoints/popup/` | The popup: runs the analysis and shows the three sections | Filip |
| `entrypoints/background.ts` | Receives requests from the popup and calls the backend | Filip |
| `lib/api.ts` | Backend calls (and mock mode) | Filip |
| `entrypoints/content.ts` | Runs inside the shop page, answers the popup's requests | Ștefana |
| `lib/extract.ts` | Reads images, price, seller and legal links from the page | Ștefana |
| `lib/badges.ts` | Draws the "AI x%" badges on the photos | Ștefana |
| `lib/types.ts` | The API contract types (keep in sync with the backend) | everyone |
| `lib/messages.ts` | Typed messages between popup, background and content script | everyone |

## How a click flows

1. The popup asks the content script for the page data (`EXTRACT_PAGE`).
2. The popup sends it to the background worker (`ANALYZE`), which calls `POST /analyze`.
3. If the result is `pending`, the popup asks again every second (`GET_ANALYSIS`).
4. The popup shows the results and asks the content script to draw badges (`SHOW_BADGES`).
