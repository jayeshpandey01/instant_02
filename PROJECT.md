# Project: ReClip Testing and Hardening

## Architecture
ReClip is a local desktop video/audio downloader server.
- **Frontend SPA**: React (Vite) app under `frontend/` communicating with Flask via API.
- **Backend Server**: Flask application under `app.py` and `src/` (listening on port 8899).
- **Desktop Wrapper**: `desktop_app.py` using PyWebView to wrap the web view in a native window.
- **Docker Compose services**: Cobalt API (port 9000) and Cloudflare Tunnel.
- **Downloader module**: `src/downloader.py` using yt-dlp, ffmpeg/ffprobe.

## Code Layout
```text
reclip/
├── .agents/                    # Agent metadata (plans, reports)
├── src/
├── tests/
│   ├── conftest.py             # pytest setup, mocks, and fixtures
│   ├── test_config.py          # Test suite for config.py
│   ├── test_metrics.py         # Test suite for metrics.py (thread safety)
│   ├── test_downloader.py      # Test suite for downloader.py
│   ├── test_routes.py          # Test suite for routes (api/control)
│   └── e2e/
│       └── dashboard.spec.js   # Playwright E2E tests
├── frontend/
│   ├── src/                    # React frontend application
│   ├── vite.config.js          # Vite config with API proxy
│   └── package.json            # Frontend dependencies
├── app.py                      # Flask main entrypoint
├── desktop_app.py              # PyWebView desktop entrypoint
├── run_tests.ps1               # Local test runner script
└── requirements.txt            # Python dependencies
```

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | E2E Testing Suite | Playwright E2E tests covering React dashboard (Tiers 1-4) | None | DONE |
| 2 | Backend Pytest Suite | Unit/integration tests for Flask routes, config, metrics, downloader | None | DONE |
| 3 | Bug Fixing | Implement the 10 audited bug fixes in backend, frontend, desktop | None | DONE |
| 4 | Local Test Runner | Implement `run_tests.ps1` PowerShell automation script | M1, M2, M3 | DONE |
| 5 | Adversarial Hardening | E2E Tier 5 Challenger testing and Forensic Audit | M4 | PLANNED |

## Interface Contracts
### Frontend ↔ Backend (Flask API)
- `/api/cobalt` (POST): Accepts JSON `{ "url": "..." }`. Returns `{ "status": "tunnel" | "fallback", "url": "...", "filename": "..." }` or `{ "error": "...", "type": "..." }` (500).
- `/api/download` (GET): Accepts `url` and `filename`. Returns a binary stream.
- `/api/stream` (GET): Streams audio/video directly.
- `/api/cookie-files` (GET): Returns list of cookie files.
- `/api/control/status` (GET): Returns `{ "docker_installed": bool, "status": "online" | "offline", "containers": [...], "tunnel_url": "..." }`.
- `/api/control/action` (POST): Accepts JSON `{ "action": "start" | "stop" | "rebuild" }`. Starts/stops/rebuilds docker containers.
- `/api/control/stats` (GET): Returns docker CPU/Memory stats.
- `/api/control/logs` (GET): Returns docker compose logs.
- `/api/control/cookie-status` (GET): Returns active cookies configuration.
- `/api/control/usage-stats` (GET): Returns metrics JSON.
- `/api/control/cookies` (POST/DELETE): Cookie CRUD operations.
