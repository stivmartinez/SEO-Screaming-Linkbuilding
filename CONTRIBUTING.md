# Contributing

Thanks for helping improve **SEO Screaming Link Building** by [stivmartinez.com](https://stivmartinez.com).

## Setup

Follow the development quick start in the [README](README.md): run the backend with uvicorn and the frontend with Vite.

## Guidelines

- Keep the tool **local-first** and first-party. Do not add telemetry or cloud lock-in by default.
- Prefer small, focused pull requests.
- Match existing code style; avoid drive-by refactors unrelated to your change.
- Add or update tests under `backend/tests` when you change crawl/parse/normalize/language behavior.
- Do not commit `backend/data/`, `.env`, or secrets.

## Checks before opening a PR

```bash
cd backend && python -m unittest discover -s tests
cd frontend && npm run build
# optional desktop smoke test (no GUI):
./scripts/run-desktop.sh --server-only
```

## Scope reminders

- Crawl only sites the operator owns or is authorized to audit.
- The API has no auth — treat network exposure as out of scope unless you are intentionally adding access control.
