# SEO Screaming Link Building

First-party crawler for sites you own. Map internal links, click depth, sitemap orphans, on-page SEO issues, and multilingual gaps — all on your machine.

**By [stivmartinez.com](https://stivmartinez.com)** · open-source under MIT.

It does **not** collect off-site backlinks.

**Use at your own risk.** Built for internal / first-party audits. See [Caveats & disclaimer](#caveats--disclaimer).

- **Non-technical / double-click:** see [Desktop app](#desktop-app-for-non-technical-users)
- **Developers:** see [Quick start](#quick-start-development) or [Docker](#docker-local-single-url)

## Features

- Seed-URL crawl with host allowlist (`www` / non-`www` included automatically)
- Respects `robots.txt` and crawl-delay; identifies as `SEOScreamingLinkBuilding/1.0 (+https://stivmartinez.com)`
- Sitemap discovery (robots, `/sitemap.xml`, nested indexes)
- On-page signals: title, meta description, H1, canonical, robots meta, word count, redirects, indexability
- Link graph: inbound / outbound counts and click depth from the seed
- Sitemap orphans (listed in the sitemap, zero internal inbound links)
- Issue lists: broken URLs, redirects, missing title/H1, noindex, duplicate titles
- Multilingual: hreflang, path-prefix languages, translation groups, missing locales, thin-content gaps
- Workspace UI with filters and CSV export (pages)
- Crawl options for sitemap discovery and language modes (auto / off / path / hreflang)

## Requirements

| Tool | Version |
|------|---------|
| Python | 3.11+ |
| Node.js | 20+ (for the UI; also used when packaging the desktop app) |
| Docker | optional (Compose one-command run) |

No Redis, Postgres, or external APIs. Data lives in a local SQLite file.

## Desktop app (for non-technical users)

The desktop build wraps the same app in a native window ([pywebview](https://pywebview.flowrl.com/)) so people can double-click instead of running terminals.

**Run from source (dev machine):**

```bash
chmod +x scripts/run-desktop.sh
./scripts/run-desktop.sh
```

This builds the UI if needed, starts the API on `127.0.0.1` only, and opens a desktop window. Crawl data is stored in the OS app-data folder:

| OS | Data directory |
|----|----------------|
| macOS | `~/Library/Application Support/SEOScreamingLinkBuilding/` |
| Windows | `%APPDATA%\SEOScreamingLinkBuilding\` |
| Linux | `~/.local/share/SEOScreamingLinkBuilding/` |

**Build an installable app:**

```bash
chmod +x scripts/build-desktop.sh
./scripts/build-desktop.sh
```

- macOS: `dist/SEO Screaming Link Building.app`
- Windows / Linux: `dist/SEOScreamingLinkBuilding/`

Gatekeeper / SmartScreen may warn until you code-sign the binary. The API has no authentication — the desktop app binds to localhost only on purpose.

Smoke-test without a GUI:

```bash
./scripts/run-desktop.sh --server-only
```

## Quick start (development)

Two processes: API on port `8000`, Vite UI on port `5173` (proxies `/api`).

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Start a crawl with a seed URL you own.

Health check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

## Docker (local, single URL)

Builds the UI into the API image and serves everything on port `8000`:

```bash
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000). Crawl data is stored in the `crawler-data` volume.

Stop with `Ctrl+C`, or `docker compose down`. Add `-v` to remove the volume and wipe stored crawls.

## Configuration

Optional settings use the `CRAWLER_` prefix. Copy [`.env.example`](.env.example) to `backend/.env` or export them in your shell.

| Variable | Default | Description |
|----------|---------|-------------|
| `CRAWLER_DATABASE_URL` | SQLite under `backend/data/crawler.db` | SQLAlchemy async URL |
| `CRAWLER_USER_AGENT` | `SEOScreamingLinkBuilding/1.0 (+https://stivmartinez.com; …)` | Outbound User-Agent |
| `CRAWLER_REQUEST_TIMEOUT` | `15.0` | Per-request timeout (seconds) |
| `CRAWLER_MAX_RESPONSE_BYTES` | `5000000` | Max response body size |
| `CRAWLER_DEFAULT_CONCURRENCY` | `4` | Default parallel fetches (1–16 in UI) |
| `CRAWLER_DEFAULT_DELAY_SECONDS` | `0.25` | Default delay between requests |
| `CRAWLER_DEFAULT_MAX_PAGES` | `10000` | Default page cap |
| `CRAWLER_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed origins |
| `CRAWLER_DATA_DIR` | `backend/data` | Directory for SQLite (desktop sets the OS app-data path) |
| `CRAWLER_STATIC_DIR` | auto (`backend/static` or `frontend/dist`) | Built UI folder served by the API |

Per-crawl concurrency, delay, and max pages are set in the UI when you start a crawl.

## Project layout

```
├── backend/
│   ├── app/
│   │   ├── api/          # HTTP routes and CSV/ZIP export
│   │   ├── analysis/     # SEO issues and language reports
│   │   ├── crawler/      # Fetch, parse, robots, sitemap, normalize
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── main.py       # FastAPI entry (serves UI when static build exists)
│   │   ├── models.py
│   │   └── schemas.py
│   ├── data/             # SQLite DB (gitignored)
│   ├── tests/
│   └── requirements.txt
├── frontend/             # React + Vite UI
├── desktop/              # Native window launcher (pywebview)
├── scripts/              # run-desktop.sh, build-desktop.sh
├── docker-compose.yml
├── Dockerfile
└── LICENSE
```

## Production-style local run (no Docker)

Build the UI and let FastAPI serve it from one process:

```bash
cd frontend && npm install && npm run build && cd ..
mkdir -p backend/static && cp -R frontend/dist/* backend/static/

cd backend
source .venv/bin/activate
pip install -r requirements.txt
export CRAWLER_CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Tests

```bash
cd backend
source .venv/bin/activate
python -m unittest discover -s tests
```

## Caveats & disclaimer

This project was built for **internal use**: auditing sites you own or are explicitly authorized to crawl. It is provided as open-source software **as-is**, with no warranty.

**You are solely responsible** for how you use it. By running this tool you agree that the authors and contributors ([stivmartinez.com](https://stivmartinez.com)) are **not liable** for blocks, bans, legal claims, data loss, downtime, security incidents, or any other damages arising from its use.

### Intended use

- Crawl **your own** properties (or sites where you have written permission).
- Run it **locally** or self-hosted on infrastructure you control.
- Keep concurrency and delay polite; respect `robots.txt` and site terms.

### Not intended for

- Scraping or bulk crawling **third-party / external** sites without permission.
- Circumventing bot protection, rate limits, paywalls, or access controls.
- Exposing the API on the public internet (there is **no authentication**).

### Risks if you crawl external sites

- Your IP may be **rate-limited, challenged, or blocked**.
- Aggressive settings can look like abuse and may violate the target’s terms of service or local law.
- Incomplete or misleading results (HTML-only crawl; no JS rendering).
- You may trigger alerts on WAF / CDN / hosting providers.

If you choose to crawl anything beyond first-party sites, you do so **entirely at your own risk**.

### Technical limits

- **HTTP HTML only.** No headless browser — JavaScript-rendered pages are incomplete.
- **Local / desktop / self-hosted.** Do not expose the unauthenticated API publicly. The desktop app binds to `127.0.0.1` only.
- **In-process crawls.** Stopping the server (or closing the desktop window) cancels running crawls; there is no separate worker queue.
- **SQLite.** Fine for single-user local use; keep `backend/data/` out of version control.
- **No support obligation.** Issues and PRs are welcome; responses are best-effort.

## API sketch

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/health` | Liveness |
| `GET` | `/api/crawls` | List crawls |
| `POST` | `/api/crawls` | Start a crawl |
| `GET` | `/api/crawls/{id}` | Crawl status |
| `POST` | `/api/crawls/{id}/cancel` | Cancel |
| `DELETE` | `/api/crawls/{id}` | Delete crawl |
| `DELETE` | `/api/sites/{id}` | Delete site and its crawls |
| `GET` | `/api/crawls/{id}/pages` | Page list |
| `GET` | `/api/crawls/{id}/graph` | Site graph |
| `GET` | `/api/crawls/{id}/orphans` | Orphans |
| `GET` | `/api/crawls/{id}/issues` | Issues |
| `GET` | `/api/crawls/{id}/languages` | Language report |

Interactive docs while the API is running: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Author

Created by **Stiven Martinez** — [stivmartinez.com](https://stivmartinez.com)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) — Copyright (c) Stiven Martinez / [stivmartinez.com](https://stivmartinez.com). Software is provided “as is”, without warranty. See [Caveats & disclaimer](#caveats--disclaimer).
