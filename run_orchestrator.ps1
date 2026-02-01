# PowerShell script to run orchestrator from Windows
# This uses Windows kubectl and Windows Python

Write-Host "=== Running Orchestrator from PowerShell ===" -ForegroundColor Cyan
Write-Host ""

# Check if Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "✗ Python not found in PATH" -ForegroundColor Red
    Write-Host "Install Python for Windows or use WSL with Option 1" -ForegroundColor Yellow
    exit 1
}

# Check if uv is available
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "✗ uv not found in PATH" -ForegroundColor Red
    Write-Host "Install uv: https://github.com/astral-sh/uv" -ForegroundColor Yellow
    exit 1
}

# Check kubectl
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    Write-Host "✗ kubectl not found in PATH" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Python found: $(python --version)" -ForegroundColor Green
Write-Host "✓ kubectl found: $(kubectl version --client --short)" -ForegroundColor Green
Write-Host ""

# Set environment variables from .env file
Write-Host "Loading environment variables from .env..." -ForegroundColor Cyan

# Read .env file (simple parser)
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.+)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
        Write-Host "  $name=$value" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "Running orchestrator..." -ForegroundColor Cyan
Write-Host ""

# Run orchestrator
uv run python scripts/run_orchestrated_benchmark.py `
    --spark-jobs 1 `
    --batch-jobs 1 `
    --scale-factor 1 `
    --max-wait-time 600 `
    --output quick_test.json

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Cyan
