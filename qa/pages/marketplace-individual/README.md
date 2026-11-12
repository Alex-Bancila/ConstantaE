# Demo Page: Marketplace Individual Seller (Peer-to-Peer / OLX style)

An offline mock of a peer-to-peer (C2C) classifieds listing (*OLX style*) for a second-hand bicycle (*Riverside 500*), posted by a private individual (*Andrei C.*) with authentic smartphone camera photos.

## How to serve offline

```bash
# Option A: Serve directly from this folder
python -m http.server 8001 --directory qa/pages/marketplace-individual

# Option B: Serve from qa/pages/
python -m http.server 8001 --directory qa/pages
# Then open http://localhost:8001/marketplace-individual/product.html
```

Open: `http://localhost:8001/product.html`

## Expected results

| Area | Expected Result | Why |
|---|---|---|
| **AI Images** | **LOW risk** (green badges, AI score < 0.10) | Real photographs captured with a personal smartphone (iPhone 13), with natural outdoor light, perspective, and optical depth. |
| **Seller Trust** | **Low score / Private seller** | The seller is an unregistered private individual (`seller.cui: null`), with no ANPC/SOL links or statutory return policy. |
| **Consumer Rights** | Peer-to-peer advisory report | Clarifies the scope of Romanian consumer law: OUG 34/2014 and ANPC enforce rights only in relations between consumers and professional traders (*profesionisti*). Private sales (C2C) are governed by the Civil Code (*Codul Civil* Art. 1707 - garantia contra viciilor ascunse). |

## Assets

- `photo1.svg`: Daylight outdoor photograph of a hybrid bicycle on pavement.
- `photo2.svg`: Macro close-up of 9-speed cassette and rear derailleur with authentic chain grease/wear.
- `expected.json`: Machine-readable contract test data.
