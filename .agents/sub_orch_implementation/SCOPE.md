# Scope: Implementation Track

## Architecture
ReClip is a local desktop video/audio downloader server.
- **Frontend SPA**: React (Vite) app under `frontend/` communicating with Flask via API.
- **Backend Server**: Flask application under `app.py` and `src/` (listening on port 8899).
- **Desktop Wrapper**: `desktop_app.py` using PyWebView to wrap the web view in a native window.
- **Docker Compose services**: Cobalt API (port 9000) and Cloudflare Tunnel.
- **Downloader module**: `src/downloader.py` using yt-dlp, ffmpeg/ffprobe.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 2 | Backend Pytest Suite | pytest suite in tests/ covering routes, downloader, config, metrics (60%+ coverage) | None | DONE |
| 3 | Bug Fixing | Implement the 10 audited bug fixes in backend, frontend, desktop | M2 | DONE |
| 4 | Local Test Runner | Implement `run_tests.ps1` | M2, M3 | DONE |
| 5 | E2E Verification | Ensure 100% of Tiers 1-4 tests pass against backend | M1, M4 | DONE |

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
