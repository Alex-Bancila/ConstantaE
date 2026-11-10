# QA (owner: Ovidiu)

| Folder | What goes in it |
|---|---|
| `pages/` | Product pages saved offline, so the demo doesn't break when a listing disappears. `pages/sample/` is a fake page to start with |
| `images/real/`, `images/ai/` | Labeled images for measuring the AI detector's accuracy |
| `e2e/` | End-to-end tests that load the built extension into Chromium |

The repository is public: only commit pages and images you are allowed to publish
(your own photos, AI images you generated, or openly licensed ones). Keep the rest in
the team's shared drive.

## Sample page

```bash
python -m http.server 8001 --directory qa/pages/sample
```

Then open http://localhost:8001/product.html. The extension runs on `localhost`, so
any page served this way can be tested.

## End-to-end smoke test

Needs the backend running on port 8000, the sample page on port 8001 and a fresh
`npm run build` of the extension. Then, from `qa/e2e/`:

```bash
npm install
npx playwright install chromium
npm test
```

It loads the extension, opens the sample page and the popup, checks that all three
result sections and both badges appear, and saves screenshots in `qa/e2e/screenshots/`.
