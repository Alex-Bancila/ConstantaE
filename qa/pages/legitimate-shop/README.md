# Demo Page: Legitimate Shop (eMAG style)

An offline mock of an authorized, compliant Romanian e-commerce listing for an espresso machine (*De'Longhi Magnifica S*), following the visual layout and legal disclosure standards of major Romanian retailers like eMAG.

## How to serve offline

```bash
# Option A: Serve directly from this folder
python -m http.server 8001 --directory qa/pages/legitimate-shop

# Option B: Serve from qa/pages/
python -m http.server 8001 --directory qa/pages
# Then open http://localhost:8001/legitimate-shop/product.html
```

Open: `http://localhost:8001/product.html`

## Expected results

| Area | Expected Result | Why |
|---|---|---|
| **AI Images** | **LOW risk** (green badges, AI score < 0.15) | Real product photos depicting actual machine features from multiple angles (front, steam wand, bean hopper). |
| **Seller Trust** | **Score: 100/100** (80/100 when served over plain HTTP `localhost`) | Displays valid Romanian company identifier (CUI RO14399840, Dante International S.A.), links to ANPC, links to SOL, and specifies a 30-day return policy. |
| **Consumer Rights** | Fully compliant report | Under OUG 34/2014 Art. 9, consumer has at least 14 days right of withdrawal (extended by shop to 30 days). Pre-contractual trader disclosures comply with Art. 6. |

## Assets

- `photo1.jpg`: Front view showing dual coffee spouts, control dial, espresso cups, and latte glass.
- `photo2.png`: Detail view highlighting manual milk frothing wand.
- `photo3.png`: Detail view showing bean hopper and coffee beans.
- `expected.json`: Machine-readable contract test data.
