# Original User Request

## 2026-07-08T05:56:17Z

You are the Adversarial Hardening and Audit Orchestrator (archetype: self).
Your working directory is: c:\Users\jayes\OneDrive\Desktop\reclip\.agents\sub_orch_adversarial_hardening
Your parent conversation ID is: fe5139c2-cd44-4ab6-9814-faf9018a4ac6
Your task is to coordinate the Adversarial Hardening and Forensic Audit phase for ReClip.
Perform the following:
1. Create and maintain SCOPE.md, plan.md, progress.md, and context.md in your working directory.
2. Coordinate Phase 2 of E2E (Tier 5: Adversarial Hardening).
   - Spawn 2 Challenger subagents (teamwork_preview_challenger) to inspect the codebase and existing tests, find gaps/untested paths/edge cases, and write adversarial test cases.
   - If the challengers find gaps or fail, spawn teamwork_preview_worker to address the issues/integrate tests and teamwork_preview_reviewer to review them. Loop until challengers report 100% clean/no remaining gaps or iteration limit is reached.
3. Run the Forensic Audit:
   - Spawn a Forensic Auditor (teamwork_preview_auditor) to perform integrity verification on the codebase.
   - If the auditor reports INTEGRITY VIOLATION, fail the gate and loop back to fix it. Clean verdict is MANDATORY.
4. Synthesize all test results (pytest, Playwright, flake8, eslint, challengers, auditor) into a final handoff.md report.
5. Send a completion message with your handoff.md path to your parent conversation ID.
