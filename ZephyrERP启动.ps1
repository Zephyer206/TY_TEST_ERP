# Zephyr ERP Launcher
# This script checks direct database access, falls back to SSH when reachable,
# and starts the backend/frontend services.

param(
    [switch]$NoWait,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Configuration - Use script location as project root
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SSHKeyPath = "C:\Users\WIT_User\.ssh\zephyr_codex"
$SSHUser = "Administrator"
$LocalPort = 5432
$BackendPort = 8000
$FrontendPort = 5173
$BindHost = "0.0.0.0"
$UseDirectDatabase = $false

# Resolve OpenSSH explicitly because Git for Windows may provide ssh.exe
# without adding it to the PowerShell PATH.
$SshExe = (Get-Command ssh.exe -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Source)
if (-not $SshExe) {
    $GitSsh = Join-Path ${env:ProgramFiles} "Git\usr\bin\ssh.exe"
    if (Test-Path -LiteralPath $GitSsh) {
        $SshExe = $GitSsh
    }
}

Write-Host "=== Zephyr ERP Launcher ===" -ForegroundColor Cyan
Write-Host ""

# Function: Check if port is listening
function Test-PortListening {
    param([int]$Port)
    try {
        $result = Test-NetConnection -ComputerName 127.0.0.1 -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue -ErrorAction Stop
        return [bool]$result
    } catch {
        return $false
    }
}

# A Windows port can be unavailable even when no process is listening (for
# example, when Hyper-V/WinNAT has reserved an exclusion range). Probe the
# actual bind operation so the launcher can select a usable frontend port.
function Test-PortBindable {
    param([int]$Port)
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    try {
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        $listener.Stop()
    }
}

function Test-HostPort {
    param([string]$HostName, [int]$Port, [int]$TimeoutMs = 3000)
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync($HostName, $Port)
        return $task.Wait($TimeoutMs) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

# Function: Read DATABASE_URL from backend/.env
function Get-DatabaseURL {
    $EnvFile = Join-Path $ProjectRoot "backend\.env"
    if (-not (Test-Path $EnvFile)) {
        throw "backend\.env not found"
    }

    $Content = Get-Content $EnvFile -Raw
    if ($Content -match 'DATABASE_URL=postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)') {
        return @{
            User = $Matches[1]
            Password = $Matches[2]
            Host = $Matches[3]
            Port = $Matches[4]
            Database = $Matches[5]
        }
    }
    throw "Cannot parse DATABASE_URL"
}

# Step 1: Check direct database access, then establish an SSH tunnel only when
# the remote SSH port is reachable.
Write-Host "[1/4] Checking database access / SSH fallback..." -ForegroundColor Yellow

try {
    if (-not $SshExe) {
        Write-Host "  ssh.exe not found; checking direct database access..." -ForegroundColor Yellow
    }
    $DBConfig = Get-DatabaseURL
    $RemoteHost = $DBConfig.Host
    $RemotePort = $DBConfig.Port

    # Direct access can briefly fail while the remote firewall/database service
    # is recovering. Retry before falling back to SSH so a transient blip does
    # not turn into a misleading tunnel timeout.
    $DirectAttempts = 6
    for ($Attempt = 1; $Attempt -le $DirectAttempts; $Attempt++) {
        if (Test-HostPort -HostName $RemoteHost -Port ([int]$RemotePort) -TimeoutMs 3000) {
            $UseDirectDatabase = $true
            Write-Host "  Direct database access is available; SSH tunnel is not required" -ForegroundColor Green
            break
        }
        if ($Attempt -lt $DirectAttempts) {
            Write-Host "  Database check $Attempt/$DirectAttempts failed; retrying..." -ForegroundColor DarkYellow
            Start-Sleep -Seconds 2
        }
    }

    if (-not $UseDirectDatabase -and -not $SshExe) {
        throw "Database is not reachable after $DirectAttempts attempts and ssh.exe is unavailable"
    }

    if (-not $UseDirectDatabase) {
        $SshPortReachable = Test-HostPort -HostName $RemoteHost -Port 22 -TimeoutMs 3000
        if (-not $SshPortReachable) {
            throw "Database direct access is unavailable and SSH port 22 on $RemoteHost is not reachable; check the remote firewall/sshd service"
        }

        # Check if tunnel already exists
        $ExistingTunnel = Get-Process -Name ssh -ErrorAction SilentlyContinue | Where-Object {
            $_.CommandLine -like "*${LocalPort}:*:${RemotePort}*"
        }

        if ($ExistingTunnel) {
            Write-Host "  SSH tunnel already exists, reusing..." -ForegroundColor Green
        } else {
            Write-Host "  Establishing SSH tunnel: 127.0.0.1:$LocalPort -> $RemoteHost`:$RemotePort" -ForegroundColor Cyan

            # Start SSH tunnel in background with bounded connection behavior.
            $SSHArgs = @(
                "-i", $SSHKeyPath,
                "-L", "${LocalPort}:localhost:${RemotePort}",
                "-N",
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=8",
                "-o", "ConnectionAttempts=1",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ServerAliveInterval=60",
                "${SSHUser}@${RemoteHost}"
            )

            $TunnelProcess = Start-Process -FilePath $SshExe -ArgumentList $SSHArgs -WindowStyle Hidden -PassThru

            # Wait for tunnel to be ready, and avoid leaving a failed ssh process behind.
            $Timeout = 12
            $Elapsed = 0
            while (-not (Test-PortListening -Port $LocalPort) -and $Elapsed -lt $Timeout) {
                if ($TunnelProcess.HasExited) { break }
                Start-Sleep -Milliseconds 500
                $Elapsed += 0.5
            }

            if (Test-PortListening -Port $LocalPort) {
                Write-Host "  SSH tunnel established successfully" -ForegroundColor Green
            } else {
                if ($TunnelProcess -and -not $TunnelProcess.HasExited) {
                    Stop-Process -Id $TunnelProcess.Id -Force -ErrorAction SilentlyContinue
                }
                throw "SSH tunnel failed to open local port $LocalPort; verify the remote sshd service, port forwarding, and key authorization"
            }
        }
    }
} catch {
    Write-Host "  Error: $_" -ForegroundColor Red
    exit 1
}

# Step 2: Start backend (uvicorn)
Write-Host ""
Write-Host "[2/4] Starting backend service..." -ForegroundColor Yellow

try {
    # Check if backend is already running
    if (Test-PortListening -Port $BackendPort) {
        Write-Host "  Backend already running (port $BackendPort)" -ForegroundColor Green
    } else {
        # Use the public database endpoint only when it is already reachable;
        # otherwise use the established local SSH tunnel.
        $DbHost = if ($UseDirectDatabase) { $RemoteHost } else { "127.0.0.1" }
        $DbPort = if ($UseDirectDatabase) { $RemotePort } else { $LocalPort }
        $LocalDBUrl = "postgresql+asyncpg://$($DBConfig.User):$($DBConfig.Password)@$DbHost`:$DbPort/$($DBConfig.Database)"

        $BackendPath = Join-Path $ProjectRoot "backend"

        # 优先使用已安装项目依赖的虚拟环境，避免误用缺依赖的系统 Python。
        $ProjectPython = @(
            (Join-Path $BackendPath ".venv\Scripts\python.exe"),
            (Join-Path $BackendPath ".runtime312\Scripts\python.exe")
        ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if ($ProjectPython) {
            $PythonExe = $ProjectPython
        } else {
            # Fallback for a freshly cloned checkout before the local runtime is created.
            $PythonExe = Get-Command python.exe -ErrorAction SilentlyContinue | Where-Object {
                $_.Source -notlike "*WindowsApps*"
            } | Select-Object -First 1 -ExpandProperty Source
        }

        if (-not $PythonExe) {
            throw "Cannot find python.exe"
        }

        # Use .NET ProcessStartInfo to set environment variable
        $BackendPsi = New-Object System.Diagnostics.ProcessStartInfo
        $BackendPsi.FileName = $PythonExe
        $BackendPsi.Arguments = "-m uvicorn app.main:app --host $BindHost --port $BackendPort"
        $BackendPsi.WorkingDirectory = $BackendPath
        $BackendPsi.UseShellExecute = $false
        $BackendPsi.CreateNoWindow = $true

        # ProcessStartInfo already inherits the parent environment. Avoid copying it
        # manually because duplicate Path/PATH entries can prevent startup on Windows.
        $BackendPsi.EnvironmentVariables["DATABASE_URL"] = $LocalDBUrl

        $BackendProcess = [System.Diagnostics.Process]::Start($BackendPsi)

        # Wait for backend to be ready
        Write-Host "  Waiting for backend..." -ForegroundColor Cyan
        $Timeout = 30
        $Elapsed = 0
        $Ready = $false

        while ($Elapsed -lt $Timeout) {
            Start-Sleep -Milliseconds 500
            $Elapsed += 0.5

            if (Test-PortListening -Port $BackendPort) {
                # Check /health endpoint
                try {
                    $Response = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
                    if ($Response.StatusCode -eq 200) {
                        $Ready = $true
                        break
                    }
                } catch {
                    # Continue waiting
                }
            }
        }

        if ($Ready) {
            Write-Host "  Backend started successfully" -ForegroundColor Green
        } else {
            Write-Host "  Warning: Backend timeout, but port is listening" -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "  Error: $_" -ForegroundColor Red
    exit 1
}

# Step 3: Start frontend (npm run dev)
Write-Host ""
Write-Host "[3/4] Starting frontend service..." -ForegroundColor Yellow

try {
    # Check the requested port and any fallback ports for an existing Vite
    # instance. This keeps repeated launcher runs idempotent.
    $RequestedFrontendPort = $FrontendPort
    $RunningFrontendPort = $null
    $ViteProcess = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -eq "node.exe" -and $_.CommandLine -match "frontend.*vite.*--port\s+(\d+)"
    } | Select-Object -First 1
    if ($ViteProcess -and $ViteProcess.CommandLine -match "--port\s+(\d+)") {
        $VitePort = [int]$Matches[1]
        if (Test-PortListening -Port $VitePort) {
            try {
                $FrontendResponse = Invoke-WebRequest -Uri "http://127.0.0.1:$VitePort/" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
                if ($FrontendResponse.StatusCode -eq 200) {
                    $RunningFrontendPort = $VitePort
                }
            } catch {
                # Continue with the normal port scan when the process is stale.
            }
        }
    }
    $ListeningPorts = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalPort)
    for ($CandidatePort = $RequestedFrontendPort; $CandidatePort -le ($RequestedFrontendPort + 100); $CandidatePort++) {
        if ($RunningFrontendPort -or $ListeningPorts -notcontains $CandidatePort) {
            continue
        }
        try {
            $FrontendResponse = Invoke-WebRequest -Uri "http://127.0.0.1:$CandidatePort/" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
            if ($FrontendResponse.StatusCode -eq 200) {
                $RunningFrontendPort = $CandidatePort
                break
            }
        } catch {
            # A listening port that is not the frontend is ignored.
        }
    }

    if ($RunningFrontendPort) {
        $FrontendPort = $RunningFrontendPort
        Write-Host "  Frontend already running (port $FrontendPort)" -ForegroundColor Green
    } else {
        # 5173 is commonly reserved by local virtualization/network services.
        # Pick the first port that can actually be bound, including ports
        # outside a reserved range such as 5173-5272.
        $FrontendPort = $null
        for ($CandidatePort = $RequestedFrontendPort; $CandidatePort -le ($RequestedFrontendPort + 100); $CandidatePort++) {
            if (Test-PortBindable -Port $CandidatePort) {
                $FrontendPort = $CandidatePort
                break
            }
        }
        if (-not $FrontendPort) {
            throw "No available frontend port found in range $RequestedFrontendPort-$($RequestedFrontendPort + 100)"
        }
        if ($FrontendPort -ne $RequestedFrontendPort) {
            Write-Host "  Port $RequestedFrontendPort is unavailable; using frontend port $FrontendPort" -ForegroundColor Yellow
        }

        $FrontendPath = Join-Path $ProjectRoot "frontend"

        # Find real npm.cmd (avoid WindowsApps stub)
        $NpmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue | Where-Object {
            $_.Source -notlike "*WindowsApps*"
        } | Select-Object -First 1 -ExpandProperty Source

        if (-not $NpmCmd) {
            # Try npm without .cmd extension
            $NpmCmd = Get-Command npm -ErrorAction SilentlyContinue | Where-Object {
                $_.Source -notlike "*WindowsApps*"
            } | Select-Object -First 1 -ExpandProperty Source
        }

        if (-not $NpmCmd) {
            throw "Cannot find npm"
        }

        # Use .NET ProcessStartInfo with cmd.exe wrapper for .cmd files
        $FrontendPsi = New-Object System.Diagnostics.ProcessStartInfo
        $FrontendPsi.FileName = $env:ComSpec
        $FrontendPsi.Arguments = "/d /c `"$NpmCmd`" run dev -- --host $BindHost --port $FrontendPort"
        $FrontendPsi.WorkingDirectory = $FrontendPath
        $FrontendPsi.UseShellExecute = $false
        $FrontendPsi.CreateNoWindow = $true

        [System.Diagnostics.Process]::Start($FrontendPsi) | Out-Null

        # Wait for frontend to be ready
        Write-Host "  Waiting for frontend..." -ForegroundColor Cyan
        $Timeout = 30
        $Elapsed = 0

        while (-not (Test-PortListening -Port $FrontendPort) -and $Elapsed -lt $Timeout) {
            Start-Sleep -Milliseconds 500
            $Elapsed += 0.5
        }

        if (Test-PortListening -Port $FrontendPort) {
            Write-Host "  Frontend started successfully" -ForegroundColor Green
        } else {
            throw "Frontend startup timeout"
        }
    }
} catch {
    Write-Host "  Error: $_" -ForegroundColor Red
    exit 1
}

# Step 4: Display status
Write-Host ""
Write-Host "[4/4] Service Status" -ForegroundColor Yellow
Write-Host ""

$BackendStatus = if (Test-PortListening -Port $BackendPort) { "Running" } else { "Stopped" }
$FrontendStatus = if (Test-PortListening -Port $FrontendPort) { "Running" } else { "Stopped" }

Write-Host "  Backend API: http://127.0.0.1:$BackendPort ($BackendStatus)" -ForegroundColor $(if ($BackendStatus -eq "Running") { "Green" } else { "Red" })
Write-Host "  Frontend UI: http://127.0.0.1:$FrontendPort ($FrontendStatus)" -ForegroundColor $(if ($FrontendStatus -eq "Running") { "Green" } else { "Red" })
Write-Host ""

if ($BackendStatus -eq "Running" -and $FrontendStatus -eq "Running") {
    Write-Host "=== Startup Complete! Open the frontend URL in your browser ===" -ForegroundColor Green

    if (-not $NoBrowser) {
        Start-Process "http://127.0.0.1:$FrontendPort"
    }
} else {
    Write-Host "=== Startup Failed - Check error messages above ===" -ForegroundColor Red
    exit 1
}

if (-not $NoWait) {
    Write-Host ""
    Write-Host "Press any key to close this window..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
