# E2E Test Infra: ReClip Dashboard

## Test Philosophy
- **Opaque-box, requirement-driven**: Test the system through the React dashboard user interface as an end user would.
- **Isolated execution via mocking**: Intercept and mock all Flask `/api/*` endpoints in the browser using Playwright's `page.route` API. This eliminates dependencies on live docker-compose containers, python environments, yt-dlp, or network tunnels, making the tests fast, reproducible, and runnable in any environment.
- **Systematic Test Tiering**: Test suite is structured into 4 tiers following Category-Partition, Boundary Value Analysis, Pairwise Combinatorial, and Real-World Workload Testing methodologies.

## Feature Inventory
| # | Feature | Source (requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|---------------------|:------:|:------:|:------:|
| 1 | Sidebar Navigation & Views | ORIGINAL_REQUEST R2.1, R2.2, R2.6, R2.7 | 5 | 5 | ✓ |
| 2 | Server Control Operations | ORIGINAL_REQUEST R2.3 | 5 | 5 | ✓ |
| 3 | Cookie Settings (CRUD) | ORIGINAL_REQUEST R2.4 | 5 | 5 | ✓ |
| 4 | Console Logs & API Docs | ORIGINAL_REQUEST R2.5, R2.6, R2.7 | 5 | 5 | ✓ |

## Test Architecture
- **Test Runner**: Playwright (JS/TS), executed via `npx playwright test`.
- **Directory Layout**:
  - `tests/e2e/`: Contains all E2E test files.
  - `tests/e2e/dashboard.spec.js`: Single specification file containing all 49 test cases across Tiers 1-4.
- **Target URL**: The tests target the React dashboard served at `http://localhost:8899` or the dev server. For E2E testing, we serve the frontend static files using a light web server or python dev server and mock the API responses in the Playwright test harness.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Initial Setup | F1, F2, F3 | High |
| 2 | Active Monitoring | F1, F4 | Medium |
| 3 | Error Recovery | F2, F3, F4 | High |
| 4 | Copy & Access | F1, F4 | Medium |
| 5 | Docker Required Block | F1 | Medium |

## Coverage Thresholds
- **Tier 1 (Feature Coverage)**: ≥5 tests per feature (total 20 tests).
- **Tier 2 (Boundary & Corner Cases)**: ≥5 tests per feature (total 20 tests).
- **Tier 3 (Cross-Feature Combinations)**: ≥4 tests verifying pairwise feature interactions.
- **Tier 4 (Real-World Application Scenarios)**: ≥5 tests verifying complex application workloads.
- **Total Minimum**: 49 test cases.
