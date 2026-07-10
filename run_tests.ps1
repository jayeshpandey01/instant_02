# ReClip Local Test Automation Script

$failed = $false

Write-Host "=== Running Pytest ===" -ForegroundColor Cyan
& .\venv\Scripts\python -m pytest --cov=src tests/
if ($LASTEXITCODE -ne 0) {
    Write-Host "Pytest failed with exit code $LASTEXITCODE!" -ForegroundColor Red
    $failed = $true
} else {
    Write-Host "Pytest passed!" -ForegroundColor Green
}

Write-Host "=== Running Playwright E2E Tests ===" -ForegroundColor Cyan
& npx playwright test
if ($LASTEXITCODE -ne 0) {
    Write-Host "Playwright E2E tests failed with exit code $LASTEXITCODE!" -ForegroundColor Red
    $failed = $true
} else {
    Write-Host "Playwright E2E tests passed!" -ForegroundColor Green
}

Write-Host "=== Running Flake8 ===" -ForegroundColor Cyan
& .\venv\Scripts\python -m flake8 src app.py desktop_app.py tests
if ($LASTEXITCODE -ne 0) {
    Write-Host "Flake8 failed with exit code $LASTEXITCODE!" -ForegroundColor Red
    $failed = $true
} else {
    Write-Host "Flake8 passed!" -ForegroundColor Green
}

Write-Host "=== Running ESLint ===" -ForegroundColor Cyan
Push-Location frontend
& npm run lint
if ($LASTEXITCODE -ne 0) {
    Write-Host "ESLint failed with exit code $LASTEXITCODE!" -ForegroundColor Red
    $failed = $true
} else {
    Write-Host "ESLint passed!" -ForegroundColor Green
}
Pop-Location

if ($failed) {
    Write-Host "=== TEST RUN FAILED ===" -ForegroundColor Red
    exit 1
} else {
    Write-Host "=== ALL TESTS PASSED ===" -ForegroundColor Green
    exit 0
}
