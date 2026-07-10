## 2026-07-08T05:36:06Z
You are teamwork_preview_worker.
Your working directory is: c:\Users\jayes\OneDrive\Desktop\reclip\.agents\worker_implementation
Your task is to implement the 10 bug fixes (Milestone 3) and address the reviewer's feedback for the pytest suite (Milestone 2) to ensure clean test execution and 60%+ code coverage for src/.

Specifically, implement the following:

1. BUG RESOLUTIONS (Milestone 3):
- Bug 1: Project name -p reclip in desktop_app.py window close down hook: use ["docker", "compose", "-p", "reclip", "down"].
- Bug 2: Wait for compose down process before python process exit in desktop_app.py (proc.wait(timeout=15)).
- Bug 3: Call track_request on early return fallback routes in src/routes/api.py.
- Bug 4: Map youtu.be links to "youtube" domain in find_matching_cookie_file (domain_name = "youtube" if it is "youtu") and get_cookie_opts (domain = ".youtube.com" if "youtu.be" in netloc).
- Bug 5: Handle comments containing # inside quoted values in src/config.py load_env (do not strip comments if # is inside single/double quotes).
- Bug 6: Handle non-JSON Cobalt API responses gracefully in src/routes/api.py (wrap response.json() in a try-except block, returning a Cobalt-style error on failure).
- Bug 7: Configure relative API proxy in frontend/vite.config.js (add server: { proxy: { '/api': { target: 'http://127.0.0.1:8899', changeOrigin: true, secure: false } } }).
- Bug 8: Cache docker_installed (30s cache), status, containers, and tunnel_url (5s cache, but do not query docker logs if tunnel_url is already cached), and stats (3s cache) in src/routes/control.py. Clear status cache when /api/control/action is called.
- Bug 9: Atomic JSON metrics writing (write to a temp file in the same directory, then os.replace) in src/metrics.py. Also implement a simple cross-platform file lock (e.g. using exclusive file creation with O_CREAT|O_EXCL) to prevent multi-process write corruption.
- Bug 10: Preserve HTTPException status codes (using e.code) in app.py error handler.

2. REVIEWER FEEDBACK RESOLUTIONS (Milestone 2):
- In src/config.py, check os.environ.get("USER_DIR") and os.environ.get("DOWNLOAD_DIR") before fallback default directories, allowing directory overrides via environment variables.
- In tests/conftest.py, prevent load_env() from running at import time by patching "src.config.load_env" or setting up environment isolation, ensuring that tests do not read from or overwrite settings from the real .env file.
- In tests/test_downloader.py, add unit/integration tests covering the core downloading, post-processing, and fallback functions in src/downloader.py (e.g., run_ytdlp_with_fallback, fallback image scraping, file collection, etc.) to push project code coverage above 60%.

3. VERIFICATION:
- Run pytest with coverage (e.g., .\venv\Scripts\python -m pytest --cov=src tests/) and verify all tests pass and coverage is >= 60%.

Create progress.md and handoff.md in your working directory. Update progress.md with your liveness heartbeat.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
