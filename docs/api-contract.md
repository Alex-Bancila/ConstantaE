# API contract

The data the extension and the backend exchange. JSON fields use camelCase.

Source of truth in code: [`backend/app/schemas.py`](../backend/app/schemas.py) and
[`extension/lib/types.ts`](../extension/lib/types.ts). Full examples:
[`shared/example-page.json`](../shared/example-page.json) (request) and
[`shared/mock-analysis.json`](../shared/mock-analysis.json) (response).

## `POST /analyze`

Starts an analysis of one product page.

**Request: `PageData`**, what the content script extracted:

| Field | Type | Meaning |
|---|---|---|
| `url` | string | Page address |
| `site` | string \| null | `"olx"`, `"emag"` or the host name |
| `title` | string \| null | Product title |
| `price` | number \| null | Price |
| `currency` | string \| null | e.g. `"RON"` |
| `images` | string[] | Absolute URLs of the product photos |
| `seller.name` | string \| null | Seller or company name |
| `seller.cui` | string \| null | Company registration number, e.g. `"RO12345678"` |
| `legalLinks.anpc` | boolean | Page links to anpc.ro |
| `legalLinks.sol` | boolean | Page links to the EU online dispute resolution (SOL) site |
| `hasReturnPolicy` | boolean | Page shows or links to a return policy |

**Response: `AnalysisResponse`**

| Field | Type | Meaning |
|---|---|---|
| `analysisId` | string | Use it with `GET /analyze/{analysisId}` |
| `status` | `"pending"` \| `"done"` \| `"failed"` | See below |
| `images[]` | `{ url, aiProbability, signals[] }` | `aiProbability`: 0 = real photo, 1 = AI-generated. `signals`: why |
| `trust` | `{ score, checks[] }` \| null | `score` 0-100, higher is better. Each check: `{ id, passed, message }` |
| `legal` | `{ summary, citations[] }` \| null | Each citation: `{ law, article, text, link }` |

## `GET /analyze/{analysisId}`

Returns the same `AnalysisResponse`, or `404` if the id is unknown.

## Pending results

With `ASYNC=false` (the default), `POST /analyze` returns `status: "done"` right away.
With `ASYNC=true`, it returns `status: "pending"` and the AI work runs in the job
queue. The extension then calls `GET /analyze/{analysisId}` every second until the
status is `"done"` or `"failed"`.

## `GET /health`

Returns `{ "status": "ok" }` when the server is up.
