$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$FrontendDir = Join-Path $Root "hermina-crawler-fe"
$PythonPath = Join-Path $Root ".venv\Scripts\python.exe"
$NpmPath = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source

if (-not (Test-Path (Join-Path $Root "apps\api\main.py"))) {
    throw "FastAPI backend tidak ditemukan di apps\api\main.py"
}

if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
    throw "Next.js frontend tidak ditemukan di hermina-crawler-fe"
}

if (-not (Test-Path $PythonPath)) {
    throw "Python virtual environment tidak ditemukan di .venv"
}

if (-not $NpmPath) {
    throw "npm.cmd tidak ditemukan. Install Node.js dan pastikan tersedia di PATH."
}

Write-Host "Starting Review System..." -ForegroundColor Green
Write-Host "Backend : http://localhost:8000/api/docs" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
Write-Host "Tekan Ctrl+C untuk stop FE dan BE." -ForegroundColor Yellow
Write-Host ""

$backendJob = Start-Job -Name "hermina-api" -ScriptBlock {
    param($RootPath, $ProjectPython)
    Set-Location $RootPath
    $env:PYTHONUNBUFFERED = "1"
    & $ProjectPython -m uvicorn apps.api.main:app --reload --port 8000 2>&1 | ForEach-Object { $_ }
} -ArgumentList $Root, $PythonPath

$frontendJob = Start-Job -Name "hermina-web" -ScriptBlock {
    param($FrontendPath, $NpmExecutable)
    Set-Location $FrontendPath
    & $NpmExecutable run dev -- --hostname 127.0.0.1 --port 3000 2>&1 | ForEach-Object { $_ }
} -ArgumentList $FrontendDir, $NpmPath

try {
    while ($true) {
        Receive-Job -Job $backendJob, $frontendJob -ErrorAction Continue

        if ($backendJob.State -eq "Failed") {
            Receive-Job -Job $backendJob -ErrorAction Continue
            throw "Backend process gagal. Cek output di atas."
        }

        if ($frontendJob.State -eq "Failed") {
            Receive-Job -Job $frontendJob -ErrorAction Continue
            throw "Frontend process gagal. Cek output di atas."
        }

        if ($backendJob.State -in @("Stopped", "Completed")) {
            Receive-Job -Job $backendJob -ErrorAction Continue
            throw "Backend process berhenti. Cek output di atas."
        }

        if ($frontendJob.State -in @("Stopped", "Completed")) {
            Receive-Job -Job $frontendJob -ErrorAction Continue
            throw "Frontend process berhenti. Cek output di atas."
        }

        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "Stopping dev processes..." -ForegroundColor Yellow
    Stop-Job -Job $backendJob, $frontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob, $frontendJob -Force -ErrorAction SilentlyContinue
}
