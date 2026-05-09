# Hi-Tech Waste Management E2E Test Runner
# Run this script to execute all tests

param(
    [string]$TestFilter = "",
    [switch]$Ui,
    [switch]$Debug,
    [switch]$Trace,
    [switch]$ApiOnly
)

$env:TEST_API_URL = if ($env:TEST_API_URL) { $env:TEST_API_URL } else { "http://localhost:8000" }
$env:TEST_USERNAME = if ($env:TEST_USERNAME) { $env:TEST_USERNAME } else { "admin@hitechwaste.com.my" }
$env:TEST_PASSWORD = if ($env:TEST_PASSWORD) { $env:TEST_PASSWORD } else { "admin123" }

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Hi-Tech Waste Management E2E Tests" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "API URL: $env:TEST_API_URL"
Write-Host "User: $env:TEST_USERNAME"
Write-Host ""

$args = @()

if ($TestFilter) {
    $args += $TestFilter
}

if ($ApiOnly) {
    $args += "--project=api"
}

if ($Ui) {
    $args += "--ui"
}

if ($Debug) {
    $args += "--debug"
}

if ($Trace) {
    $args += "--trace=on"
}

Write-Host "Running: npx playwright test $args" -ForegroundColor Green
& npx playwright test @args

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✓ All tests passed!" -ForegroundColor Green
} else {
    Write-Host "`n✗ Some tests failed. Check the report above." -ForegroundColor Red
}
