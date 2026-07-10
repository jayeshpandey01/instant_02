# Context: ReClip E2E Testing

## Environment Details
- **OS**: Windows (user's local PC)
- **Node.js**: Installed (frontend uses Vite, React, package.json exists at root and in frontend/)
- **Python**: Installed (backend Flask app in app.py)
- **Ports**:
  - Main app / server: `http://localhost:8899`
  - Frontend dev (Vite): usually `http://localhost:5173` or similar.

## Project Structure
- `frontend/`: React Vite project
- `tests/e2e/`: Destination for Playwright E2E tests
- `src/`: Backend Flask modules

## Key Constraints
- Mock all `/api/*` endpoints in the browser using Playwright's `page.route` to prevent dependencies on docker-compose, Cloudflare tunnels, or external downloader binaries.
- Avoid writing code directly; delegate execution to `teamwork_preview_worker`.
