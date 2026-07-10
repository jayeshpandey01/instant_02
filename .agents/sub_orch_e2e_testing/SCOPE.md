# Scope: ReClip E2E Testing Suite (Tiers 1-4)

## Architecture
- **Vite React Frontend SPA**: Lives in `frontend/`, talks to the Flask API.
- **Flask Backend API**: Runs on port 8899, provides `/api/control/*` and `/api/download/*` / `/api/cobalt`.
- **E2E Playwright Harness**: Mocking all `/api/*` endpoints via Playwright's `page.route` network interception. This isolates the React dashboard from actual python backend and docker-compose containers, allowing robust offline execution on the user's local PC.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Test Plan & Setup | Create plan.md, context.md, and TEST_INFRA.md containing feature inventory and test strategy | None | IN_PROGRESS |
| 2 | Playwright Setup | Configure Playwright in package.json and vite/playwright config | M1 | PLANNED |
| 3 | Tier 1 Tests: Feature Coverage | Implement >= 20 happy-path tests covering the 4 core features in isolation | M2 | PLANNED |
| 4 | Tier 2 Tests: Boundary & Error Cases | Implement >= 20 boundary and error/failure tests for API failures, empty inputs, edge cases | M3 | PLANNED |
| 5 | Tier 3 Tests: Cross-Feature Combinations | Implement >= 4 tests checking interactions between features (e.g. cookie settings and server action combinations) | M4 | PLANNED |
| 6 | Tier 4 Tests: Real-World Workloads | Implement >= 5 end-to-end user workflows (e.g., initial setup, docker unavailable fallback, log monitoring, settings configuration) | M5 | PLANNED |
| 7 | Verification & TEST_READY.md | Run the test suite, ensure all tests pass, and generate TEST_READY.md at project root | M6 | PLANNED |

## Interface Contracts
### Frontend ↔ Backend (Flask API)
- `/api/control/status` (GET): Returns `{ "docker_installed": bool, "status": "online" | "offline", "containers": [...], "tunnel_url": "..." }`
- `/api/control/action` (POST): Accepts JSON `{ "action": "start" | "stop" | "rebuild" }`. Returns `{ "status": "success" }` or error.
- `/api/control/stats` (GET): Returns CPU/Memory stats.
- `/api/control/logs` (GET): Returns `{ "logs": "..." }`. Accepts optional query param `?service=<name>`.
- `/api/control/cookie-status` (GET): Returns active cookies state: `{ "YOUTUBE_COOKIES": bool, "INSTAGRAM_COOKIES": bool, ... }`.
- `/api/control/cookies` (POST): Body `{ "service": "...", "cookies": "..." }`. Returns `{ "status": "success" }` or error.
- `/api/control/cookies/<service>` (DELETE): Clears cookies for service. Returns `{ "status": "success" }` or error.
- `/api/control/usage-stats` (GET): Returns `{ "total_requests": int, "successful_requests": int, "failed_requests": int, "platforms": { "youtube": int, ... } }`.
