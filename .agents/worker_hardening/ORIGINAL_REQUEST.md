## 2026-07-08T11:30:42Z

Your working directory is: c:\Users\jayes\OneDrive\Desktop\reclip\.agents\worker_hardening
Your task is to fix all backend and frontend bugs and vulnerabilities identified in the adversarial gap analysis reports, and ensure all unit, integration, and E2E tests (including the new adversarial tests) pass.

Here is the list of issues you must fix:
Backend (Python):
1. Lock bypass in `src/metrics.py`: If `FileLock` fails to acquire (TimeoutError), do not silently load metrics without a lock and save it. If it times out, raise an exception or handle it cleanly, but do not bypass protection.
2. Absence of Lock in `ensure_ffmpeg()` (`src/downloader.py`): Introduce a threading lock or file lock to prevent concurrent downloads/extractions of ffmpeg/ffprobe zip file.
3. SSRF / Local File Read in `/api/stream` (`src/routes/api.py`): Restrict the `url` parameter. Ensure it only allows http/https schemes, and restrict it to legitimate hostnames or block file://, localhost, 127.0.0.1, etc.
4. Cookie deletion wildcard in `/api/control/cookies/<service>` (`src/routes/control.py`): Ensure `service` doesn't match wildcards (like "." or empty string) that could delete all cookie files. Validate the service string matches a valid alphanumeric name.
5. Cookie path traversal write in `/api/control/cookies` (`src/routes/control.py`): Sanitize and validate `service` parameter. Block path traversal sequences like `..` and `/`.
6. Docker log argument injection in `/api/control/logs` (`src/routes/control.py`): Validate that `service` is a valid service name (alphanumeric and hyphens only, or one of the configured services) and `limit` is a clean integer string. Do not append unsanitized strings directly to subprocess args.
7. Silent metrics reset in `src/metrics.py`: If metrics load fails due to JSON corruption, do not silently overwrite with empty defaults. Rename the corrupted file to a backup name for inspection and raise an error or initialize safely but log it clearly. Ensure the test expectation in `tests/test_adversarial.py` is satisfied or updated to match a safe behavior.
8. Unrestricted CORS in `app.py`: Restrict CORS or only enable it under strict conditions.

Frontend (React) & Desktop:
9. Cookie deletion error silent failure (`frontend/src/App.jsx`): check response.ok and handle non-200 responses, showing an alert alert(`Error: ${response.statusText}`).
10. Logs API 500 error silent blank screen (`frontend/src/App.jsx`): handle non-200 responses and missing logs property in response, and display the error message.
11. Rebuild button 5-minute stuck disabled (`frontend/src/App.jsx`): ensure actionLoading is reset to false when the status is polled or after a short reasonable time, or check if status is already online and reset immediately.
12. WebView port hijack (`desktop_app.py`): if fallback ports are all occupied, do not load the busy port; show an error dialog or exit cleanly.

Verification requirements:
- Run all backend tests (pytest) to make sure they pass: `venv\Scripts\pytest tests/`
- Run E2E Playwright tests to make sure they pass: `npx playwright test`
- Do NOT hardcode test results, create dummy/facade implementations, or bypass tests. All fixes must be genuine.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Write your handoff report handoff.md in your working directory and notify the parent.
