param(
    [string]$DatasetZip = '',
    [int]$Port = 8000,
    [switch]$SkipInstall,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$appRoot = $PSScriptRoot
Set-Location -LiteralPath $appRoot

if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if ($SkipInstall) { throw 'Create .venv and install requirements first, or omit -SkipInstall.' }
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
}
$pythonExe = Join-Path $appRoot '.venv\Scripts\python.exe'
if (-not $SkipInstall) {
    & $pythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    npm install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Node.js 22+ with npm is required.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}
if ($DatasetZip) {
    & $pythonExe -m backend.prepare $DatasetZip
    if ($LASTEXITCODE -ne 0) { throw 'Dataset preparation failed.' }
}
if (-not (Test-Path -LiteralPath 'data\catalog.json')) { throw 'Pass -DatasetZip with the licensed liquid-briefing-data.zip path.' }
if (-not (Test-Path -LiteralPath 'dist\index.html')) { throw 'Run npm run build first, or omit -SkipInstall.' }

# Read simple KEY=VALUE lines without executing configuration as code.
if (Test-Path -LiteralPath '.env') {
    foreach ($line in Get-Content -LiteralPath '.env') {
        if ($line -match '^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$') {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim('"').Trim("'"), 'Process')
        }
    }
}
$workerLog = Join-Path $appRoot 'data\worker.log'
$workerErrorLog = Join-Path $appRoot 'data\worker-error.log'
$workerProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m','backend.worker' -WorkingDirectory $appRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $workerLog -RedirectStandardError $workerErrorLog
$apiProcess = $null
try {
    $url = "http://127.0.0.1:$Port"
    $apiProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m','uvicorn','backend.server:app','--host','127.0.0.1','--port',"$Port" -WorkingDirectory $appRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $appRoot 'data\api.log') -RedirectStandardError (Join-Path $appRoot 'data\api-error.log')
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ($apiProcess.HasExited) { throw 'API server exited. See data\api-error.log.' }
        try {
            $response = Invoke-WebRequest -Uri "$url/api/bootstrap" -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw 'API did not become ready. See data\api-error.log.' }
    Write-Host "ForYouCast demo: $url"
    Write-Host 'Local demo accounts have no passwords. API keys are not needed.'
    Write-Host 'The worker prepares recorded podcasts. Cloud generation uses the saved n8n connection.'
    Write-Host 'Press Ctrl+C to stop both local processes.'
    if (-not $NoBrowser) { Start-Process $url }
    Wait-Process -Id $apiProcess.Id
}
finally {
    if (-not $workerProcess.HasExited) { Stop-Process -Id $workerProcess.Id }
    if ($null -ne $apiProcess -and -not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id }
}
