# QA (owner: Ovidiu)

| Folder | What goes in it |
|---|---|
| `pages/` | Product pages saved offline, so the demo doesn't break when a listing disappears. Contains offline demo pages and expected results |
| `images/real/`, `images/ai/` | Labeled images for measuring the AI detector's accuracy |
| `e2e/` | End-to-end tests that load the built extension into Chromium |

The repository is public: only commit pages and images you are allowed to publish
(your own photos, AI images you generated, or openly licensed ones). Keep the rest in
the team's shared drive.

## Demo Pages (Saved Offline)

The demo pages in `qa/pages/` cover 4 key test scenarios:

1. **`pages/legitimate-shop/`**: Legitimate, fully compliant Romanian e-commerce listing (eMAG style) for an espresso machine (*De'Longhi Magnifica S*). Valid CUI, ANPC/SOL links, 30-day return policy, authentic photos.
2. **`pages/ai-photos/`**: Legitimate seller with synthetic, AI-generated product images (*CrystalGlow Orb*). Tests AI vision detection on photos with high AI probability.
3. **`pages/suspicious-seller/`**: Rogue scam listing (*iPhone 16 Pro Max* replica at 850 RON). Missing CUI, missing ANPC/SOL links, countdown pressure banner, illegal clause waiving return rights.
4. **`pages/marketplace-individual/`**: Peer-to-peer (C2C) classifieds listing (OLX style) for a bicycle. Private individual seller, authentic phone photos, no trader registration.
5. **`pages/sample/`**: Minimal starter page used by the end-to-end smoke test.

### Serving offline with `python -m http.server`

Serve all pages at once:

```bash
python -m http.server 8001 --directory qa/pages
```

Then open [http://localhost:8001/](http://localhost:8001/) for the demo hub, or directly:
- [http://localhost:8001/legitimate-shop/product.html](http://localhost:8001/legitimate-shop/product.html)
- [http://localhost:8001/ai-photos/product.html](http://localhost:8001/ai-photos/product.html)
- [http://localhost:8001/suspicious-seller/product.html](http://localhost:8001/suspicious-seller/product.html)
- [http://localhost:8001/marketplace-individual/product.html](http://localhost:8001/marketplace-individual/product.html)
- [http://localhost:8001/sample/product.html](http://localhost:8001/sample/product.html)

Or serve any individual page directory directly:

```bash
python -m http.server 8001 --directory qa/pages/legitimate-shop
```
Then open http://localhost:8001/product.html.

See [`qa/pages/README.md`](pages/README.md) and each folder's `expected.json` for the written expected results.

## End-to-end test suite

Checks every demo page against its expected results in Chromium with the extension loaded.

Needs:
1. Backend running on port 8000 (`uvicorn app.main:app --reload` from `backend/`)
2. Demo pages server running on port 8001 (`python -m http.server 8001 --directory qa/pages`)
3. Built extension in `extension/.output/chrome-mv3` (`npm run build` from `extension/`)

Run the entire suite with one command:

```bash
cd qa/e2e
npm install
npx playwright install chromium
npm test
```

### What the suite checks for each page

| Test / Demo Page | Expected Badges | Popup Verification | Screenshots Saved |
|---|---|---|---|
| **Legitimate shop** (`legitimate-shop`) | 3 badges (`AI x%`) | All 3 sections ('AI-generated images', 'Seller trust', 'Your rights') | `legitimate-shop-popup.png`, `legitimate-shop-page.png` |
| **AI photos** (`ai-photos`) | 2 badges (`AI x%`) | All 3 sections loaded | `ai-photos-popup.png`, `ai-photos-page.png` |
| **Suspicious seller** (`suspicious-seller`) | 1 badge (`AI x%`) | All 3 sections loaded | `suspicious-seller-popup.png`, `suspicious-seller-page.png` |
| **Marketplace individual** (`marketplace-individual`) | 2 badges (`AI x%`) | All 3 sections loaded | `marketplace-individual-popup.png`, `marketplace-individual-page.png` |
| **Starter sample** (`sample`) | 2 badges (`AI x%`) | All 3 sections loaded | `sample-popup.png`, `sample-page.png` |

To test a single page instead of all:

```bash
TEST_PAGE=legitimate-shop npm test
```
