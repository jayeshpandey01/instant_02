# Explorer Handoff Report — ReClip Codebase Audit and Test Plan

## 1. Observation
We have audited the ReClip codebase located at `c:\Users\jayes\OneDrive\Desktop\reclip`. Below are the file structure, dependencies, and detailed observations of the bugs, race conditions, and architectural issues found in the code.

### File Structure & Entry Points
*   **Backend Entry Point:** `app.py` initializes the Flask app, configures static/template directories, registers blueprints, and acts as the catch-all for the SPA.
*   **Desktop Wrapper:** `desktop_app.py` spins up Flask in a daemon thread, polls for availability, and initializes the `pywebview` window.
*   **Core Modules (`src/`):**
    *   `src/config.py`: Loads configuration, parses `.env` files.
    *   `src/metrics.py`: Manages request success/failure metrics inside `usage_metrics.json`.
    *   `src/downloader.py`: Integrates `yt-dlp` and `ffmpeg`/`ffprobe` to download, merge, and transcode media.
    *   `src/routes/api.py`: Blueprint for download/stream endpoints (`/api/cobalt`, `/api/download`, `/api/stream`, `/api/cookie-files`).
    *   `src/routes/control.py`: Blueprint for Docker container controls (`/api/control/action`, `/api/control/status`, `/api/control/stats`, `/api/control/logs`, `/api/control/cookie-status`, `/api/control/usage-stats`, `/api/control/cookies`).
*   **Frontend SPA (`frontend/`):** Vite-bundled React app. Entry point is `frontend/src/main.jsx`, main component is `frontend/src/App.jsx`. Output assets compile to `frontend/dist`.
*   **External Service Configuration:** `docker-compose.yml` defines `cobalt-api` (local cobalt instance) and `cloudflare-tunnel` (pointing back to host Flask server).

### Dependencies
*   **Python:** `flask`, `requests`, `yt-dlp`, `pywebview`, `flask-cors`.
*   **Node.js:** `react`, `react-dom`, `lucide-react`, and dev tools (`vite`, `tailwindcss`, `eslint`).

---

### Verbatim Bugs and Issues Identified
We observed 10 critical issues in the codebase:

#### Bug 1: Compose down without project name in desktop app close hook
*   **Location:** `desktop_app.py`, lines 75-88
*   **Code:**
    ```python
    def on_window_closing():
        print("Window closing — sending docker compose down...")
        try:
            subprocess.Popen(
                ["docker", "compose", "down"],
                cwd=BASE_DIR,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
    ```
*   **Issue:** The Flask routes in `control.py` manage containers using the explicit project name `-p reclip` (e.g. `docker compose -p reclip up -d`). However, `on_window_closing` calls `docker compose down` without `-p reclip`. Docker Compose defaults to using the parent folder name (which is a random temp folder like `_MEIxxxxx` when compiled). Consequently, it fails to locate or shut down the active `reclip` containers.

#### Bug 2: Asynchronous compose shutdown triggers premature process termination
*   **Location:** `desktop_app.py`, lines 83-88
*   **Code:**
    ```python
    subprocess.Popen(
        ["docker", "compose", "down"],
        ...
    )
    ```
*   **Issue:** `subprocess.Popen` starts `docker compose down` asynchronously and returns immediately. Since PyWebView's event loop closes right after the handler returns, the Python main process exits. This terminates the spawned compose command prematurely before it can stop the containers.

#### Bug 3: Metrics request tracking is bypassed on fallback routes
*   **Location:** `src/routes/api.py`, lines 119-123 and 139-143
*   **Code:**
    ```python
    if video_url:
        ...
        return jsonify({
            "status": "tunnel",
            "url": video_url,
            "filename": filename
        }), 200
    ```
*   **Issue:** In `/api/cobalt`, if the Cobalt service fails or rate-limits and the route triggers the `yt_dlp` or Instagram image fallbacks, it returns early with status 200. However, `track_request(target_url, success=True)` is only called at the end of the route (lines 149-150), completely bypassing tracking for all fallback downloads.

#### Bug 4: `youtu.be` links bypass configured YouTube cookies
*   **Location:** `src/downloader.py`, lines 206-214
*   **Code:**
    ```python
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    parts = netloc.split(".")
    if len(parts) >= 2:
        base_domain = ".".join(parts[-2:])
    else:
        base_domain = netloc
    
    domain_name = base_domain.replace("www.", "").split(".")[0]
    ```
*   **Issue:** For short YouTube URLs (e.g., `https://youtu.be/xxxx`), `base_domain` evaluates to `youtu.be`, causing `domain_name` to be `"youtu"`. The downloader then looks for `"YOUTU_COOKIES"` in environment variables and `"youtu_cookies.txt"` in the local folder. Since the user configures cookies for `"youtube"`, short URLs fail to load cookies.

#### Bug 5: Quoted `.env` values containing space-hash split mid-string
*   **Location:** `src/config.py`, lines 48-49
*   **Code:**
    ```python
    if " #" in line:
        line = line[:line.index(" #")].strip()
    ```
*   **Issue:** If a user places a cookie string or password containing space-hash (e.g. `COOKIE="foo bar #123"`) in their `.env`, `load_env()` truncates the string starting at the space-hash, corrupting the loaded value.

#### Bug 6: Uncaught JSONDecodeError in Cobalt proxy endpoint
*   **Location:** `src/routes/api.py`, line 54
*   **Code:**
    ```python
    json_resp = response.json()
    ```
*   **Issue:** If the Cobalt endpoint returns a non-JSON page (e.g., Nginx 502 error, Cloudflare gateway error), calling `response.json()` raises `requests.exceptions.JSONDecodeError` which bubbles up as a raw HTML 500 error instead of a structured JSON response.

#### Bug 7: React Dev server cannot communicate with backend (Vite configuration)
*   **Location:** `frontend/vite.config.js`
*   **Code:** No proxy settings are configured under `defineConfig()`.
*   **Issue:** Frontend components execute requests to relative paths (e.g., `fetch('/api/control/status')`). When running Vite dev server (`http://localhost:5173`), these API calls resolve to the dev server port and fail with 404, preventing GUI-based development testing.

#### Bug 8: Heavy shell execution polling causes resource exhaustion
*   **Location:** `src/routes/control.py`, lines 88, 98-100, 147-150, and 167-169
*   **Issue:** The frontend calls `/api/control/status` and `/api/control/stats` every 3 seconds unconditionally. This endpoint runs heavy Docker queries (`docker info`, `docker compose ps`, `docker logs`, `docker stats`) as subprocesses. On Windows hosts, spawning multiple processes every 3 seconds results in high CPU spikes.

#### Bug 9: Thread lock in `metrics.py` is vulnerable to write-corruption and multi-process collisions
*   **Location:** `src/metrics.py`, line 31
*   **Code:**
    ```python
    with open(METRICS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    ```
*   **Issue:** If Flask runs in multi-process mode, `threading.Lock()` does not serialize writes. Additionally, opening a file in `"w"` mode immediately truncates it. If a write fails midway (or if the server shuts down), the file becomes empty/corrupted.

#### Bug 10: Flask API error handler hides HTTP status codes
*   **Location:** `app.py`, lines 52-62
*   **Code:**
    ```python
    if req.path.startswith("/api/"):
        return jsonify({
            "error": str(e),
            "type": type(e).__name__
        }), 500
    ```
*   **Issue:** Catching all exceptions and hardcoding `500` intercepts standard HTTP exceptions (like 400 Bad Request, 404 Not Found, 405 Method Not Allowed) and converts them into generic 500 server errors.

---

## 2. Logic Chain
1. **Bug 1 & 2:** Since `docker compose -p reclip` is the name of our compose cluster, running `compose down` on a different directory or without `-p reclip` targets the wrong namespace. Furthermore, because Python exits instantly when pywebview closes, the async `subprocess.Popen` is killed. Thus, containers are orphaned.
2. **Bug 3:** In `src/routes/api.py`, `track_request` is only written at the bottom. The fallback pathways (lines 119 and 139) return early with `200 OK` responses. Hence, they bypass the end of the function, preventing usage stats from logging success.
3. **Bug 4:** Since `youtu.be` uses a separate top-level domain from `youtube.com`, a split-on-dot logic maps `youtu.be` to `youtu`. Mapping it explicitly to `youtube` fixes the cookie matching.
4. **Bug 5:** The config parser does not respect quotes. It strips everything after ` #`. Checking if the hash symbol lies outside quotes prevents truncation of credentials.
5. **Bug 6:** Network errors usually return HTML status pages instead of JSON payloads. Wrapping `response.json()` ensures we return a mock Cobalt error wrapper to the frontend.
6. **Bug 7:** The frontend development server runs on a different port than Flask (5173 vs 8899). Relative requests fail unless redirected via Vite's proxy mechanism.
7. **Bug 8:** Polling stats and status via subprocesses every 3 seconds is heavy. Spawning process handles in Windows takes significant system resources. Restricting polls to the active tab and caching stable details resolves this.
8. **Bug 9:** File-based databases must be written atomically. Writing to a temp file and swapping via `os.replace` eliminates truncation corruption.
9. **Bug 10:** Flask's HTTPExceptions carry correct status codes in `e.code`. Accessing this field ensures standard API conventions are maintained.

---

## 3. Caveats
*   **Docker Requirement:** Tests that check direct Docker commands require Docker CLI to be mockable or present. We assume all integration/unit tests should run in a fully mocked environment to guarantee speed and execution on systems without Docker.
*   **Windows Subprocess:** Subprocess calls require `creationflags=subprocess.CREATE_NO_WINDOW` on Windows to hide popup windows. Mock assertions must verify this specific flag is passed when running on Windows.
*   **CODE_ONLY Environment:** In Code Only mode, tests must mock network calls for ffmpeg/ffprobe zip files and yt-dlp queries.

---

## 4. Conclusion & Plan

We propose the following plan to implement tests and fix audited bugs:

### Phase 1: Test Infrastructure (R1 & R2)
*   **pytest Configuration:** Setup `tests/conftest.py` with mock clients and path fixtures.
*   **Unit & Route Testing:** Implement mocking strategies using `unittest.mock` to mock `yt_dlp.YoutubeDL`, `subprocess.run`, and `requests.post`.
*   **E2E Mock Testing:** Setup Playwright tests under `tests/e2e/`. Use request interception (`page.route`) to mock all Flask endpoints, enabling frontend testing independent of local Docker state.

### Phase 2: Bug Fix Implementation (R4)
1.  **Atomicity in Metrics:** Modify `_save_metrics()` to write to a temp file and call `os.replace`.
2.  **Compose Command Project and Wait:** Update `on_window_closing` to use `-p reclip` and `.wait(timeout=15)`.
3.  **Domain mapping in `find_matching_cookie_file`:** Map `youtu` to `youtube` and `x` to `twitter`.
4.  **Vite Dev Proxy:** Add a proxy block to `vite.config.js`.
5.  **Exception Code preservation:** Modify the Flask error handler in `app.py`.
6.  **Polling optimization:** Cache `docker_installed` and the `tunnel_url`. Limit stats polling to the active `utilization` tab.

---

### Proposed `PROJECT.md` Contents
```markdown
# ReClip Development and Testing Project Layout

## Architecture
ReClip is a single-node desktop utility.
*   **Client App:** PyWebView wrapper + Vite React UI.
*   **Backend Server:** Flask API listening on localhost:8899.
*   **Third-party Integrations:**
    *   Docker Compose: Cobalt Node.js API (port 9000), Cloudflare Quick Tunnel (proxy).
    *   Binaries: Local ffmpeg/ffprobe extracted automatically to system temp.
    *   Resolver: yt-dlp running inline with cookies.

## Code Layout
```text
reclip/
├── .agents/                    # Agent metadata (plans, reports)
├── src/
│   ├── routes/
│   │   ├── api.py              # Download and stream proxy routes
│   │   └── control.py          # DockerCompose controller and statistics
│   ├── config.py               # Environment configuration
│   ├── downloader.py           # Core yt-dlp downloader and ffmpeg post-processor
│   └── metrics.py              # Requests counter and platform usage metrics
├── tests/
│   ├── conftest.py             # pytest setup, mocks, and fixtures
│   ├── test_config.py          # Test suite for configuration parsing
│   ├── test_metrics.py         # Test suite for metrics and thread safety
│   ├── test_downloader.py      # Test suite for yt-dlp extraction and transcoding
│   ├── test_routes.py          # Test suite for Flask routes (API/Control)
│   └── e2e/
│       └── dashboard.spec.js   # Playwright E2E dashboard frontend tests
├── frontend/
│   ├── src/                    # React frontend application
│   ├── vite.config.js          # Vite config (includes dev server API proxy)
│   └── package.json            # React node dependencies
├── app.py                      # Flask main entrypoint
├── desktop_app.py              # Desktop wrapper main entrypoint
├── run_tests.ps1               # PowerShell local test runner script
└── requirements.txt            # Python dependencies
```

## Interface Contracts
1.  **`/api/cobalt` (POST):** Accepts JSON `{ "url": "..." }`. Returns `{ "status": "tunnel", "url": "...", "filename": "..." }`. Falls back to local yt-dlp.
2.  **`/api/download` (GET):** Accepts `?url=...` and optional `?filename=...`. Resolves URL and streams binary stream output back with `Content-Length`.
3.  **`/api/control/status` (GET):** Returns `{ "docker_installed": bool, "status": "online" | "offline", "containers": [...], "tunnel_url": "..." }`.

## Milestones
*   **Milestone 1: Backend Unit and Integration Testing.** Implement all unit tests in `tests/` targeting python files. Reach 60%+ coverage.
*   **Milestone 2: Playwright E2E Dashboard Suite.** Create tests under `tests/e2e/` with mocks for API isolation.
*   **Milestone 3: Bug Resolutions.** Implement the 10 audited fixes.
*   **Milestone 4: Automation Scripting.** Build the PowerShell script `run_tests.ps1`.
```

---

## 5. Verification Method

To verify the test suite, execution, and bug fixes:
1.  **Backend Pytest suite:**
    *   Command: `pytest tests/ -v --cov=src`
    *   Assertion: Expect all tests to pass and package coverage to exceed 60%.
2.  **Playwright E2E suite:**
    *   Commands:
        *   `cd frontend && npm install`
        *   `npm run build`
        *   `npx playwright test`
    *   Assertion: Expect frontend view asserts (e.g. tabs loading, click triggers) to pass.
3.  **Bug fix verification:**
    *   Confirm bundled app shuts down compose: Run Flask, start containers, and close Python window. Run `docker ps` to verify that `cloudflare-tunnel` and `cobalt-api` are fully terminated.
    *   Confirm `youtu.be` cookie loading: Feed `youtu.be` URL to `/api/cookie-files` or download and check trace to confirm youtube cookies are loaded.
