param(
    [ValidateSet('Start', 'Stop')][string]$Action = 'Start',
    [ValidateRange(1024, 65535)][int]$Port = 8080,
    [string]$PythonPath = '',
    [switch]$Rebuild
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$RuntimeDir = Join-Path $ProjectRoot 'logs\cloud-runtime'
$LogDir = Join-Path $RuntimeDir 'logs'
$StateFile = Join-Path $RuntimeDir 'server.json'
$ServerScript = Join-Path $PSScriptRoot 'serve.py'
$ServerProcess = $null
$OperationLock = $null

function Get-Sha256 {
    param([string]$Path)
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)) }
    finally { $sha.Dispose(); $stream.Dispose() }
}

function Invoke-Logged {
    param([string]$Executable, [string[]]$Arguments, [string]$LogName)
    $log = Join-Path $LogDir $LogName
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Executable @Arguments *> $log
        $result = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    if ($result -ne 0) { throw "Command failed. See $log" }
}

function Get-ManagedProcess {
    if (-not (Test-Path -LiteralPath $StateFile)) { return $null }
    $state = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
    $process = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
    if (-not $process) { return $null }
    if ($process.StartTime.ToUniversalTime().Ticks.ToString() -ne $state.startedUtcTicks) { return $null }
    $details = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.Id)"
    if (-not $details.CommandLine -or -not $details.CommandLine.Contains($ServerScript)) {
        throw 'Saved process identity does not match this deployment. No process was stopped.'
    }
    return $process
}

function Stop-ManagedProcess {
    $managed = Get-ManagedProcess
    if ($managed) {
        Stop-AppProcessTree $managed
        Write-Host 'Previous cloud ERP process stopped.'
    }
    if (Test-Path -LiteralPath $StateFile) { Remove-Item -LiteralPath $StateFile }
}

function Stop-AppProcessTree {
    param($Process)
    # Windows virtual-environment python.exe may launch a second Python process.
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($Process.Id)")
    foreach ($child in $children) {
        if ($child.CommandLine -and $child.CommandLine.Contains($ServerScript)) {
            $childProcess = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
            if ($childProcess) { Stop-AppProcessTree $childProcess }
        }
    }
    $Process.Refresh()
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        $Process.WaitForExit(10000) | Out-Null
    }
}

function Test-PortBindable {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Any, $Port)
    $listener.ExclusiveAddressUse = $true
    try { $listener.Start(); return $true }
    catch { return $false }
    finally { $listener.Stop() }
}

function Find-Python {
    if ($PythonPath) {
        $candidate = (Get-Command $PythonPath -ErrorAction Stop).Source
        $version = & $candidate -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $version -in @('3.11', '3.12')) { return $candidate }
        throw 'PythonPath must point to Python 3.11 or 3.12 (required by pinned backend dependencies).'
    }
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        foreach ($version in @('-3.11', '-3.12')) {
            $previousPreference = $ErrorActionPreference
            try {
                $ErrorActionPreference = 'Continue'
                $candidate = & py.exe $version -c 'import sys; print(sys.executable)' 2>$null
                if ($LASTEXITCODE -eq 0 -and $candidate) { return [string]$candidate }
            } finally { $ErrorActionPreference = $previousPreference }
        }
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) {
        $version = & $command.Source -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $version -in @('3.11', '3.12')) { return $command.Source }
    }
    throw 'Python 3.11/3.12 not found. Install it or pass -PythonPath C:\path\python.exe.'
}

function Get-FrontendFingerprint {
    $frontend = Join-Path $ProjectRoot 'frontend'
    $files = @(Get-ChildItem -LiteralPath (Join-Path $frontend 'src') -File -Recurse)
    foreach ($directory in @((Join-Path $frontend 'public'), (Join-Path $ProjectRoot 'shared\api'))) {
        if (Test-Path -LiteralPath $directory) { $files += @(Get-ChildItem -LiteralPath $directory -File -Recurse) }
    }
    $files += @(Get-ChildItem -LiteralPath $frontend -File -Force |
        Where-Object { $_.Name -match '^(package.*\.json|.*config.*|index\.html|\.env.*)$' })
    $records = @('cloud-build-v1', (& node.exe --version), (& npm.cmd --version))
    foreach ($file in ($files | Sort-Object FullName)) {
        $records += $file.FullName.Substring($ProjectRoot.Length) + ':' + (Get-Sha256 $file.FullName)
    }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes(($records -join "`n")))) }
    finally { $sha.Dispose() }
}

try {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    try {
        $OperationLock = [IO.File]::Open((Join-Path $RuntimeDir 'operation.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    } catch { throw 'Another start/stop operation is running. Wait for it to finish.' }
    if ($Action -eq 'Stop') {
        Stop-ManagedProcess
        Write-Host 'Cloud ERP is stopped. Database and other applications were not stopped.'
        exit 0
    }

    Write-Host '[1/5] Checking configuration and runtimes...'
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'backend\.env'))) {
        throw 'Missing backend\.env. Copy your working database configuration to this file, then start again.'
    }
    $existing = Get-ManagedProcess
    if (-not (Test-PortBindable)) {
        $existingPort = if ($existing) { (Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json).port } else { 0 }
        if (-not $existing -or $existingPort -ne $Port) {
            throw "Port $Port is unavailable. Use -Port 8081 or free the port. No process was stopped."
        }
    }
    $basePython = Find-Python
    if (-not (Get-Command node.exe -ErrorAction SilentlyContinue) -or -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw 'Node.js/npm not found. Reopen this window after installing Node.js.'
    }
    $nodeVersion = & node.exe -p "process.versions.node.split('.')[0]"
    if ($LASTEXITCODE -ne 0 -or [int]$nodeVersion -lt 22) { throw 'Use Node.js 22 or newer for this frontend.' }

    Write-Host '[2/5] Preparing isolated Python dependencies (cached after first run)...'
    $venv = Join-Path $RuntimeDir 'venv'
    $python = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        Invoke-Logged $basePython @('-X', 'utf8', '-m', 'venv', $venv) 'python-environment.log'
    }
    $requirements = Join-Path $ProjectRoot 'backend\requirements.txt'
    $dependencyKey = Get-Sha256 $requirements
    $dependencyMarker = Join-Path $RuntimeDir 'python-dependencies.sha256'
    if ($Rebuild -or -not (Test-Path -LiteralPath $dependencyMarker) -or
            (Get-Content -LiteralPath $dependencyMarker -Raw).Trim() -ne $dependencyKey) {
        Invoke-Logged $python @('-X', 'utf8', '-m', 'pip', 'install', '-r', $requirements) 'python-install.log'
        Set-Content -LiteralPath $dependencyMarker -Value $dependencyKey -Encoding ASCII
    }
    Write-Host '[3/5] Checking database (read-only)...'
    Invoke-Logged $python @('-X', 'utf8', (Join-Path $PSScriptRoot 'check.py')) 'database-check.log'
    Write-Host 'Database connection: PASS.'

    Write-Host '[4/5] Preparing frontend build...'
    $frontend = Join-Path $ProjectRoot 'frontend'
    $buildMarker = Join-Path $RuntimeDir 'frontend.sha256'
    $buildKey = Get-FrontendFingerprint
    if ($Rebuild -or -not (Test-Path -LiteralPath (Join-Path $frontend 'dist\index.html')) -or
            -not (Test-Path -LiteralPath (Join-Path $frontend 'node_modules')) -or
            -not (Test-Path -LiteralPath $buildMarker) -or
            (Get-Content -LiteralPath $buildMarker -Raw).Trim() -ne $buildKey) {
        Push-Location $frontend
        $savedApiBase = $env:VITE_API_BASE_URL
        try {
            $env:VITE_API_BASE_URL = '/api/v1'
            $nodeMarker = Join-Path $RuntimeDir 'node-dependencies.sha256'
            $nodeKey = (Get-Sha256 (Join-Path $frontend 'package.json')) + ':' + $nodeVersion
            $lockfile = Join-Path $frontend 'package-lock.json'
            if (Test-Path -LiteralPath $lockfile) { $nodeKey += ':' + (Get-Sha256 $lockfile) }
            $nodeModules = Join-Path $frontend 'node_modules'
            $usableDependencies = (Test-Path -LiteralPath (Join-Path $nodeModules '.bin\vite.cmd')) -and
                (Test-Path -LiteralPath (Join-Path $nodeModules '.bin\vue-tsc.cmd'))
            $mustInstall = $Rebuild -or -not $usableDependencies -or
                ((Test-Path -LiteralPath $nodeMarker) -and (Get-Content -LiteralPath $nodeMarker -Raw).Trim() -ne $nodeKey)
            if ($mustInstall) {
                if ((Test-Path -LiteralPath $lockfile) -and -not (Test-Path -LiteralPath $nodeModules)) {
                    Invoke-Logged (Get-Command npm.cmd).Source @('ci', '--no-audit', '--no-fund') 'frontend-install.log'
                } else {
                    Invoke-Logged (Get-Command npm.cmd).Source @('install', '--no-audit', '--no-fund') 'frontend-install.log'
                }
                $nodeKey = (Get-Sha256 (Join-Path $frontend 'package.json')) + ':' + $nodeVersion
                $nodeKey += ':' + (Get-Sha256 $lockfile)
                Set-Content -LiteralPath $nodeMarker -Value $nodeKey -Encoding ASCII
            } elseif (-not (Test-Path -LiteralPath $nodeMarker)) {
                Write-Host 'Existing frontend dependencies found; reusing them without disrupting other local processes.'
                Set-Content -LiteralPath $nodeMarker -Value $nodeKey -Encoding ASCII
            }
            Invoke-Logged (Get-Command npm.cmd).Source @('run', 'build') 'frontend-build.log'
        } finally {
            $env:VITE_API_BASE_URL = $savedApiBase
            Pop-Location
        }
        Set-Content -LiteralPath $buildMarker -Value (Get-FrontendFingerprint) -Encoding ASCII
    } else { Write-Host 'Frontend unchanged; reusing build.' }

    Write-Host '[5/5] Starting ERP...'
    Stop-ManagedProcess
    if (-not (Test-PortBindable)) { throw "Port $Port is unavailable. Start with -Port 8081." }
    $arguments = @('-X', 'utf8', $ServerScript, '--port', [string]$Port) | ForEach-Object { '"' + $_ + '"' }
    $ServerProcess = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory (Join-Path $ProjectRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $LogDir 'server.stdout.log') -RedirectStandardError (Join-Path $LogDir 'server.stderr.log')
    @{ pid = $ServerProcess.Id; startedUtcTicks = $ServerProcess.StartTime.ToUniversalTime().Ticks.ToString(); port = $Port } |
        ConvertTo-Json | Set-Content -LiteralPath $StateFile -Encoding UTF8
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        $ServerProcess.Refresh()
        if ($ServerProcess.HasExited) { throw 'ERP exited during startup. See logs\cloud-runtime\logs\server.stderr.log.' }
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 2
            $page = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 2
            if ($health.status -eq 'healthy' -and $page.Headers['Content-Type'] -like 'text/html*') { $ready = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw 'Startup checks timed out. See logs\cloud-runtime\logs\server.stderr.log.' }
    Write-Host "READY: http://localhost:$Port" -ForegroundColor Green
    Write-Host "Remote access: http://<SERVER-PUBLIC-IP>:$Port (allow TCP $Port in Windows Firewall and cloud firewall)."
    Write-Host 'Close this window to leave ERP running. Double-click stop-cloud.cmd to stop it.'
    Write-Host 'Startup checks passed: database, API health, frontend HTML. Business/browser acceptance is separate.'
} catch {
    if ($ServerProcess) {
        try { Stop-ManagedProcess } catch { Write-Host 'Automatic cleanup failed; inspect the saved process state.' }
    }
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    if ($OperationLock) { $OperationLock.Dispose() }
}
