# Original User Request

## Initial Request — 2026-07-08T05:24:41Z

ReClip is a self-hosted video/audio downloader that runs as a **local desktop server** on the user's laptop. It consists of a Flask (Python) backend, a React (Vite) dashboard frontend, a PyWebView desktop wrapper, and Docker Compose services (Cobalt API + Cloudflare Tunnel). The codebase has undergone extensive bug-fixing (BUG-004 through BUG-047) but currently has **zero automated tests** and no systematic verification. The goal is to make it production-ready for real users by adding comprehensive tests, local test automation scripts, and finding/fixing any remaining bugs.

**Key architecture**: The user's laptop IS the server. No cloud deployment (Vercel/Netlify/CI/CD) is needed. The Flask app runs locally, Docker containers provide the Cobalt API and Cloudflare Tunnel, and the PyWebView desktop app wraps everything into a native window.

Working directory: c:\Users\jayes\OneDrive\Desktop\reclip
Integrity mode: development

## Requirements

### R1. Backend Test Suite (pytest)
Create a comprehensive pytest test suite covering:
- **Flask API routes** (`src/routes/api.py`): `/api/cobalt`, `/api/stream`, `/api/download`, `/api/cookie-files` — test request handling, error responses, fallback chains
- **Control routes** (`src/routes/control.py`): `/api/control/action`, `/api/control/status`, `/api/control/stats`, `/api/control/logs`, `/api/control/cookie-status`, `/api/control/usage-stats`, `/api/control/cookies` — test Docker command execution, JSON parsing, cookie CRUD
- **Downloader module** (`src/downloader.py`, 939 lines): `ensure_ffmpeg`, `get_cookie_opts`, `find_matching_cookie_file`, `run_ytdlp_with_fallback`, `build_video_format_string`, `resolve_instagram_video_format`, `detect_media_type`, `collect_download_files`, `finalize_video_files`, `ensure_video_has_audio`, `manual_merge_video_audio`, `convert_to_ios_compatible_mp4`, `make_friendly_error`, `needs_transcoding`
- **Config module** (`src/config.py`): `load_env` function with `.env` parsing, path resolution for bundled vs dev mode
- **Metrics module** (`src/metrics.py`): `track_request`, `get_metrics`, `get_platform_from_url`, thread-safety of file-based metrics
- Use mocking (unittest.mock) for external dependencies: yt-dlp, Docker CLI, ffmpeg/ffprobe, file system operations, HTTP requests

### R2. End-to-End Tests (Playwright)
Create Playwright E2E tests that verify the full user flow through the React dashboard:
- The dashboard loads and renders correctly at `http://localhost:8899`
- Sidebar navigation works (Utilization, Settings, Console Logs, API Docs tabs)
- Server Start/Stop/Rebuild buttons trigger API calls
- Settings tab: cookie setup, clear, and status display
- Tunnel URL banner appears when containers are running
- Console Logs tab displays and filters logs
- API Docs tab renders endpoint documentation

### R3. Local Test Runner and Automation
Create local scripts that the user can run on their Windows laptop to:
- Run the full pytest suite with coverage reporting
- Run Playwright E2E tests
- Run linting (flake8 for Python, ESLint for React)
- A single "run all checks" master script
- No cloud CI/CD — everything executes locally via command line

### R4. Bug Hunting and Fixing
Systematically audit the codebase to find and fix remaining bugs, focusing on:
- Error handling gaps (uncaught exceptions, missing try/catch blocks)
- Race conditions in the threaded metrics file I/O
- Edge cases in URL parsing, cookie handling, and format resolution
- Desktop app (PyWebView) startup reliability
- Docker control commands on Windows (subprocess handling, path issues)
- Frontend state management issues (React hooks, stale closures, missing cleanup)

## Acceptance Criteria

### Backend Tests
- [ ] pytest test suite exists in a `tests/` directory with clear test organization
- [ ] All Flask API routes have at least 2 test cases each (success + error path)
- [ ] All public functions in `downloader.py` have at least 1 test case
- [ ] `config.py` load_env function tested with mock .env files
- [ ] `metrics.py` thread-safety tested with concurrent writes
- [ ] All tests pass when run via `pytest tests/ -v`
- [ ] Test coverage is reported and exceeds 60% for the `src/` package

### E2E Tests
- [ ] Playwright test file(s) exist in a `tests/e2e/` directory
- [ ] Dashboard loads without console errors
- [ ] All 4 sidebar navigation tabs render their content
- [ ] At least 1 test verifies an API call is triggered by a button click

### Local Automation
- [ ] A `run_tests.ps1` (PowerShell) script exists that runs all checks
- [ ] Running it produces a clear PASS/FAIL summary
- [ ] Script works on Windows 10/11 without manual setup beyond `pip install` and `npm install`

### Bug Fixes
- [ ] Any bugs found are documented with a description and fix
- [ ] No Python import errors when running `python app.py`
- [ ] No React build errors when running `npm run build` in `frontend/`
- [ ] All existing BUG-xxx fixes are preserved (no regressions)
