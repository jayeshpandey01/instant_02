# Original User Request

## Initial Request — 2026-07-08T10:57:58Z

You are the Implementation Track Orchestrator (archetype: self).
Your working directory is: c:\Users\jayes\OneDrive\Desktop\reclip\.agents\sub_orch_implementation
Your parent conversation ID is: fe5139c2-cd44-4ab6-9814-faf9018a4ac6
Your task is to coordinate the Implementation Track for ReClip.
Perform the following:
1. Create and maintain SCOPE.md, plan.md, progress.md, and context.md in your working directory.
2. Implement Milestone 2: Backend pytest suite in tests/ covering routes, downloader, config, and metrics (with concurrent writes thread safety tests). Mock external dependencies using unittest.mock. Ensure 60%+ coverage for src/.
3. Implement Milestone 3: Audit and implement the 10 bug fixes described in the Explorer's audit:
   - Bug 1: Project name -p reclip in desktop_app.py window close down hook.
   - Bug 2: Wait for compose down process before python process exit in desktop_app.py (wait 15s).
   - Bug 3: Call track_request on early return fallback routes in src/routes/api.py.
   - Bug 4: Map youtu.be links to "youtube" domain in find_matching_cookie_file / get_cookie_opts.
   - Bug 5: Handle comments containing # inside quoted values in src/config.py load_env.
   - Bug 6: Handle non-JSON Cobalt API responses gracefully in src/routes/api.py.
   - Bug 7: Configure relative API proxy in frontend/vite.config.js.
   - Bug 8: Cache docker_installed / tunnel_url and optimize stats polling in src/routes/control.py.
   - Bug 9: Atomic JSON metrics writing (write temp file, os.replace) in src/metrics.py.
   - Bug 10: Preserve HTTPException status codes in app.py error handler.
4. Implement Milestone 4: Local automation script run_tests.ps1 running pytest, playwright, flake8, and eslint.
5. Spawn teamwork_preview_worker to write code/tests and verify. Spawn teamwork_preview_reviewer to review them.
6. Once TEST_READY.md is published, ensure 100% of Tiers 1-4 tests pass against the backend.
7. Send a completion message with handoff.md path to your parent conversation ID.
