# Demo Page: Suspicious Seller (Scam / Rogue Listing)

An offline mock of a rogue online shop / scam listing offering a high-end smartphone (*iPhone 16 Pro Max*) at 850 RON (~88% below market value), employing aggressive urgency tactics, upfront wire transfer demands, missing mandatory Romanian legal identification, and an illegal clause waiving the buyer's return rights.

## How to serve offline

```bash
# Option A: Serve directly from this folder
python -m http.server 8001 --directory qa/pages/suspicious-seller

# Option B: Serve from qa/pages/
python -m http.server 8001 --directory qa/pages
# Then open http://localhost:8001/suspicious-seller/product.html
```

Open: `http://localhost:8001/product.html`

## Expected results

| Area | Expected Result | Why |
|---|---|---|
| **AI Images** | **Counterfeit / Knockoff hardware photo** | The listing uses a photo of an obvious clone/replica phone with non-standard camera module and chassis proportions. |
| **Seller Trust** | **Score: 0/100** (Fails all 5 checks) | Fails HTTPS check, fails CUI check (no company registration), fails ANPC link, fails SOL link, fails return policy (attempts an unlawful no-return policy). |
| **Consumer Rights** | Critical risk report citing OUG 34/2014 & OG 21/1992 | Under OUG 34/2014 Art. 26, any contractual clause excluding or waiving the consumer's 14-day withdrawal right is null and void (*nul de drept*). Failure to disclose company registration and contact details violates Art. 6. |

## Assets

- `photo1.png`: Photograph of fake/replica smartphone with distorted camera layout and non-authentic body styling.
- `expected.json`: Machine-readable contract test data.
