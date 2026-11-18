# Demo Page: Listing with AI Photos

An offline test page representing an e-commerce boutique (*Luminaria Studio*) selling a levitating ambient crystal lamp, where the seller is a legally registered company complying with basic disclosures, but **the product photographs are synthetically generated (AI)**.

## How to serve offline

```bash
# Option A: Serve directly from this folder
python -m http.server 8001 --directory qa/pages/ai-photos

# Option B: Serve from qa/pages/
python -m http.server 8001 --directory qa/pages
# Then open http://localhost:8001/ai-photos/product.html
```

Open: `http://localhost:8001/product.html`

## Expected results

| Area | Expected Result | Why |
|---|---|---|
| **AI Images** | **HIGH risk** (red badges, AI score > 0.85) | The images exhibit diffusion texture smoothness, impossible multi-directional light caustics, and warped perspective geometry characteristic of generative diffusion models. |
| **Seller Trust** | **Score: 100/100** (80/100 when served on plain HTTP `localhost`) | The seller is a registered Romanian SRL (CUI RO41298451), provides working ANPC and SOL links, and provides a 14-day return policy. |
| **Consumer Rights** | Warning on product conformity & misleading practices | While the statutory 14-day withdrawal right applies (OUG 34/2014 Art. 9), synthetic images that mislead consumers regarding real-life finish or dimensions violate OUG 34/2014 Art. 6 and Legea 363/2007 (misleading commercial practices). |

## Assets

- `photo1.svg`: AI-rendered floating crystal orb with impossible internal galaxy refraction and glow caustics.
- `photo2.svg`: AI-rendered room scene with perspective inconsistencies and synthetic lighting artifacts.
- `expected.json`: Machine-readable contract test data.
