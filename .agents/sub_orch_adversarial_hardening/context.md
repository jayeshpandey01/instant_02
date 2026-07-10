# Context — Adversarial Hardening and Audit

## System Properties
- **OS**: Windows
- **Workspace**: `c:\Users\jayes\OneDrive\Desktop\reclip`
- **Application Port**: 8899 (Flask backend), 9000 (Cobalt API mock/Docker container)

## Environment
- Python virtual environment is at `venv`
- Frontend React uses Vite and package.json is at `frontend/package.json`
- Test runners: `run_tests.ps1` runs backend and frontend tests.
- Core commands:
  - Python tests: `pytest` or `venv\Scripts\pytest`
  - Playwright: `npx playwright test`
  - Linting: `flake8` and `npm run lint` / `eslint` equivalent in frontend.
