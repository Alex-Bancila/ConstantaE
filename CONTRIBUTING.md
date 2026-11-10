# Contributing

## Workflow

1. Pick or create an issue, and assign it to yourself.
2. Create a branch from `main`, named `<area>/<short-description>`:
   `backend/cui-check`, `ai/rag-ingestion`, `extension/popup-loading`, `qa/e2e-olx`.
   Areas: `backend`, `ai`, `extension`, `qa`, `devops`, `docs`.
3. Commit often, with short messages that say what changed: "Add CUI check digit
   validation", not "fix" or "changes".
4. Open a pull request into `main` and fill in the template.
5. Get **one approval**, ideally from someone in another area, so knowledge spreads.
6. Merge it yourself once it's approved. Never push straight to `main`.

Keep pull requests small: one task, ideally under 400 changed lines. Review others'
pull requests within 48 hours.

## Before you open a pull request

Backend (from `backend/`):

```bash
ruff check .
ruff format .
pytest
```

Extension (from `extension/`):

```bash
npm run compile
npm run build
```

## Definition of Done

A task is done when:

- the pull request is reviewed and approved;
- the checks above pass;
- new logic has tests;
- the README or docs are updated if you changed how something is run or used;
- the acceptance criteria in the issue are met;
- for AI changes: the accuracy on the test set did not drop.

## Changing the API contract

The extension and the backend must agree on the data they exchange. If you change a
field, update **all four** in the same pull request and tell the team:

1. [`backend/app/schemas.py`](backend/app/schemas.py)
2. [`extension/lib/types.ts`](extension/lib/types.ts)
3. [`shared/`](shared) example files (a backend test checks they match the schemas)
4. [`docs/api-contract.md`](docs/api-contract.md)

## Secrets

The repository is **public**. Never commit `.env` files, API keys or passwords.
Put them in your local `.env`, which git ignores, and add the variable name (without
the value) to `.env.example`.

## TODOs

Mark unfinished work with your name, e.g. `# TODO(David): validate the check digit`,
so everyone knows who to ask.
