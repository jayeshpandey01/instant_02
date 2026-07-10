## 2026-07-08T05:43:30Z
You are teamwork_preview_worker.
Your working directory is: c:\Users\jayes\OneDrive\Desktop\reclip\.agents\worker_automation
Your task is to implement Milestone 4 (Local automation script run_tests.ps1) and verify that 100% of Tiers 1-4 tests (Playwright E2E and Pytest) pass against the backend.

Tasks:
1. Create the run_tests.ps1 script at the project root c:\Users\jayes\OneDrive\Desktop\reclip\. Ensure it runs:
   - Pytest: .\venv\Scripts\python -m pytest --cov=src tests/
   - Playwright: npx playwright test
   - Flake8: .\venv\Scripts\python -m flake8 src app.py desktop_app.py tests
   - ESLint: cd frontend && npm run lint && cd ..
2. Prepare the environment:
   - Ensure the React frontend is built: cd frontend && npm install && npm run build && cd ..
   - Ensure Playwright and its browser dependencies are installed: npm install && npx playwright install chromium
   - Ensure python linting dependencies are installed in the venv (e.g., pip install flake8, pytest-cov, if they are not already installed).
3. Execute the automated script or run the components manually to verify they all pass:
   - Verify all 49 Playwright E2E tests pass.
   - Verify all pytest tests pass and coverage is >= 60%.
   - Verify flake8 and eslint run cleanly (or resolve any minor lint warnings if they arise).
4. Create progress.md and handoff.md in your working directory. Update progress.md with your liveness heartbeat.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
