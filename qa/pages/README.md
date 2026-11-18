# Demo Offline Test Pages

Offline product pages saved so demo runs and automated tests remain resilient even when live online listings expire or change.

All pages are completely self-contained with offline vector images and structured data (JSON-LD and Open Graph) compatible with the ConstantaE extension content script (`extension/lib/extract.ts`) and backend API contract (`docs/api-contract.md`).

---

## Repository & Shared Drive Policy

> [!IMPORTANT]
> The git repository is public. **Only pages and assets we are legally allowed to publish** (our own graphics, synthetic/AI images, and openly authored content) are committed here.
> 
> Full proprietary dumps, raw captures, and customer data from proprietary external platforms must **not** be committed here and are preserved in the **team's shared drive**.

---

## How to Serve Offline

Serve all pages from the `qa/pages/` root:

```bash
python -m http.server 8001 --directory qa/pages
```

Then navigate to:
- Hub Index: [http://localhost:8001/](http://localhost:8001/)
- Legitimate shop: [http://localhost:8001/legitimate-shop/product.html](http://localhost:8001/legitimate-shop/product.html)
- Listing with AI photos: [http://localhost:8001/ai-photos/product.html](http://localhost:8001/ai-photos/product.html)
- Suspicious seller: [http://localhost:8001/suspicious-seller/product.html](http://localhost:8001/suspicious-seller/product.html)
- Marketplace individual: [http://localhost:8001/marketplace-individual/product.html](http://localhost:8001/marketplace-individual/product.html)
- Original sample: [http://localhost:8001/sample/product.html](http://localhost:8001/sample/product.html)

Or serve any individual directory directly:

```bash
python -m http.server 8001 --directory qa/pages/legitimate-shop
# Open http://localhost:8001/product.html
```

---

## Test Pages Matrix & Expected Results

### 1. Legitimate Shop (`qa/pages/legitimate-shop/`)
- **Concept:** Major Romanian electronics retailer (eMAG style).
- **Product:** *Espressor automat De'Longhi Magnifica S ECAM 22.110.B* (1.549,99 RON).
- **Seller:** Dante International S.A., CUI: `RO14399840`.
- **Expected Results:**
  - **Images (3 images):** LOW AI Risk (< 0.15 probability). Real camera optics, clean angle shots. Green badges.
  - **Trust Score:** 100/100 on HTTPS (80/100 on `http://localhost`).
    - `https`: passed (when served on https)
    - `cui_present`: passed (`RO14399840`)
    - `anpc_link`: passed (`https://anpc.ro/`)
    - `sol_link`: passed (`https://ec.europa.eu/consumers/odr`)
    - `return_policy`: passed (30-day return policy)
  - **Legal Report:** Full compliance. Confirms 14-day statutory right of withdrawal under OUG 34/2014 Art. 9 (contractually extended by shop to 30 days) and pre-contractual identity transparency under Art. 6.

### 2. Listing with AI Photos (`qa/pages/ai-photos/`)
- **Concept:** Boutique lifestyle gadget listing (*Luminaria Studio*).
- **Product:** *Lampa ambientala levitatie magnetica CrystalGlow Orb* (289,00 RON).
- **Seller:** Luminaria Studio SRL, CUI: `RO41298451`.
- **Expected Results:**
  - **Images (2 images):** HIGH AI Risk (> 0.85 probability). Red badges. Diffusion texture smoothing, impossible light caustics, perspective artifacts.
  - **Trust Score:** 100/100 on HTTPS (80/100 on `http://localhost`). The seller is legally registered and provides all links.
  - **Legal Report:** Attention required. Statutory 14-day return under OUG 34/2014 Art. 9 is present, but selling goods depicted via synthetic/AI imagery without explicit disclosure may mislead consumers regarding physical finish, invoking Legea 363/2007 (misleading commercial practices) and OUG 34/2014 Art. 6.

### 3. Suspicious Seller (`qa/pages/suspicious-seller/`)
- **Concept:** Rogue scam online store offering counterfeit/clone luxury smartphones at ~88% discount with high-pressure tactics.
- **Product:** *iPhone 16 Pro Max 256GB Titanium Blue* (850,00 RON vs normal ~6.500 RON).
- **Seller:** "TechOutlet Express Online" (No CUI, no physical registered office, wire transfer only).
- **Expected Results:**
  - **Images (1 image):** Fake/clone iPhone hardware photograph with non-authentic proportions.
  - **Trust Score:** 0/100 (Critical Risk). Fails all 5 trust checks:
    - `https`: failed on localhost
    - `cui_present`: failed (no CUI found)
    - `anpc_link`: failed (no link to anpc.ro)
    - `sol_link`: failed (no link to SOL)
    - `return_policy`: failed (seller explicitly claims no returns allowed)
    - *Suspicious price:* flagged (850 RON is > 85% below market price).
  - **Legal Report:** Multiple severe violations. Under OUG 34/2014 Art. 26, any clause waiving or excluding the statutory 14-day right of withdrawal is null and void (*nul de drept*). Failure to disclose trader identity and address violates Art. 6.

### 4. Marketplace Individual Seller (`qa/pages/marketplace-individual/`)
- **Concept:** Peer-to-peer (C2C) classifieds listing (OLX style).
- **Product:** *Bicicleta trekking Riverside 500 marimea M* (750,00 RON).
- **Seller:** Andrei C. (Persoana fizica).
- **Expected Results:**
  - **Images (2 images):** LOW AI Risk (< 0.10 probability). Authentic daylight smartphone camera photos. Green badges.
  - **Trust Score:** Low score (Private seller; no company registration number or ANPC links).
  - **Legal Report:** Advisory on legal scope: OUG 34/2014 and ANPC rules apply exclusively to B2C contracts (between consumers and professional traders). Peer-to-peer individual sales are governed by the Romanian Civil Code (Art. 1707 - warranty against hidden defects).

---

## Machine-Readable Contracts

Each demo folder contains an `expected.json` file with the exact data contract matching `AnalysisResponse` and `PageData` to enable automated contract testing.
