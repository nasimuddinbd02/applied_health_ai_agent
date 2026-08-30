<#
.SYNOPSIS
    Run the whole City Hospital stack in one shot.

.DESCRIPTION
    Starts Redis, the FastMCP tool server, the FastAPI chat gateway and the
    Next.js frontend as child processes, streams their output into this one
    console with a per-service prefix, and shuts all of them down together on
    Ctrl+C.

    It also does the setup you would otherwise forget: creates backend/.env
    from .env.example, seeds the database on first run, and installs frontend
    dependencies if node_modules is missing.

    The frontend is given NEXT_PUBLIC_API_BASE / NEXT_PUBLIC_WS_BASE matching
    -BackendPort, so the two halves always agree even if .env.local says
    something else (a real environment variable wins over a .env file in Next).

.EXAMPLE
    .\scripts\dev.ps1
    Everything on the default ports: Redis 6379, MCP 8077, API 8000, web 3000.

.EXAMPLE
    .\scripts\dev.ps1 -SeparateWorker
    Runs the agent worker as its own process instead of inside the API, which
    is the production topology (see docs/Design.md §19).

.EXAMPLE
    .\scripts\dev.ps1 -NoFrontend -BackendPort 8001
    Backend only, on a different port.
#>
[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [int]$McpPort = 8077,
    [int]$RedisPort = 6379,

    # Skip individual services.
    [switch]$NoRedis,
    [switch]$NoMcp,
    [switch]$NoFrontend,

    # Run the agent worker as its own process (INLINE_AGENT_WORKER=false).
    [switch]$SeparateWorker,

    # Re-seed the database even if it already exists.
    [switch]$Seed
)

$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$LogDir = Join-Path $Root '.dev-logs'

$Services = @()

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
function Write-Step([string]$Message) {
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Warn([string]$Message) {
    Write-Host "  ! $Message" -ForegroundColor Yellow
}

function Test-Port([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if ($async.AsyncWaitHandle.WaitOne(300)) {
            $client.EndConnect($async)
            return $true
        }
        return $false
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Resolve-Python {
    # The repo venv first, then a backend-local one, then whatever is on PATH.
    $candidates = @(
        (Join-Path $Root '.venv\Scripts\python.exe'),
        (Join-Path $Backend '.venv\Scripts\python.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    $onPath = Get-Command python -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    throw "No Python found. Create a virtualenv at .venv and run 'make install'."
}

function Resolve-RedisServer {
    $onPath = Get-Command redis-server -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    # The Windows MSI/zip distributions do not put themselves on PATH.
    $roots = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Redis'),
        'C:\Program Files\Redis',
        'C:\Program Files\Memurai'
    )
    foreach ($base in $roots) {
        if (-not (Test-Path $base)) { continue }
        $found = Get-ChildItem -Path $base -Filter 'redis-server.exe' -Recurse `
            -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

function Start-Service-Process {
    param(
        [string]$Name,
        [string]$Color,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [hashtable]$Environment = @{}
    )

    $stdout = Join-Path $LogDir "$Name.log"
    $stderr = Join-Path $LogDir "$Name.err.log"
    New-Item -ItemType File -Path $stdout -Force | Out-Null
    New-Item -ItemType File -Path $stderr -Force | Out-Null

    # Start-Process inherits this process's environment, so set the overrides
    # around the call and put them back afterwards.
    $saved = @{}
    foreach ($key in $Environment.Keys) {
        $saved[$key] = [Environment]::GetEnvironmentVariable($key)
        [Environment]::SetEnvironmentVariable($key, $Environment[$key])
    }
    try {
        $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList `
            -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    } finally {
        foreach ($key in $Environment.Keys) {
            [Environment]::SetEnvironmentVariable($key, $saved[$key])
        }
    }

    return @{
        Name     = $Name
        Color    = $Color
        Process  = $process
        Out      = New-LogReader $stdout
        Err      = New-LogReader $stderr
        Reported = $false
    }
}

function New-LogReader([string]$Path) {
    $stream = [System.IO.File]::Open(
        $Path, [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite
    )
    return New-Object System.IO.StreamReader($stream)
}

function Write-ServiceLines($Service) {
    foreach ($reader in @($Service.Out, $Service.Err)) {
        while ($true) {
            $line = $reader.ReadLine()
            if ($null -eq $line) { break }
            Write-Host ("[{0}] " -f $Service.Name) -ForegroundColor $Service.Color -NoNewline
            Write-Host $line
        }
    }
}

function Wait-ForPort([int]$Port, [string]$What, [int]$TimeoutSeconds = 60) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $Port) { return $true }
        foreach ($service in $Services) { Write-ServiceLines $service }
        Start-Sleep -Milliseconds 400
    }
    Write-Warn "$What did not come up on port $Port within ${TimeoutSeconds}s."
    return $false
}

function Stop-All {
    Write-Host ''
    Write-Step 'Shutting down...'
    foreach ($service in $Services) {
        if ($service.Process -and -not $service.Process.HasExited) {
            # /T so npm's and uvicorn's child processes go too.
            try {
                Start-Process -FilePath 'taskkill' `
                    -ArgumentList '/PID', $service.Process.Id, '/T', '/F' `
                    -WindowStyle Hidden -Wait
            } catch {
                Write-Warn "Could not stop $($service.Name): $($_.Exception.Message)"
            }
        }
        foreach ($reader in @($service.Out, $service.Err)) {
            if ($reader) { $reader.Dispose() }
        }
    }
    Write-Host 'Stopped.' -ForegroundColor Cyan
}

# --------------------------------------------------------------------------- #
# Preflight
# --------------------------------------------------------------------------- #
Write-Step 'Checking the workspace'

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
Get-ChildItem -Path $LogDir -Filter '*.log' -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

$python = Resolve-Python
Write-Host "    python:   $python"

$backendEnv = Join-Path $Backend '.env'
if (-not (Test-Path $backendEnv)) {
    Copy-Item (Join-Path $Root '.env.example') $backendEnv
    Write-Warn 'Created backend/.env from .env.example. Add a provider API key to use the live agent.'
}

if (-not $NoFrontend) {
    if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) {
        Write-Step 'Installing frontend dependencies (first run, this takes a minute)'
        Push-Location $Frontend
        try { & npm install } finally { Pop-Location }
    }
}

$dbFile = Join-Path $Backend 'database\hospital.db'
if ($Seed -or -not (Test-Path $dbFile)) {
    Write-Step 'Seeding the database'
    Push-Location $Backend
    try { & $python -m app.db.seed } finally { Pop-Location }
}

# --------------------------------------------------------------------------- #
# Start everything
# --------------------------------------------------------------------------- #
try {
    # --- Redis --------------------------------------------------------------
    if (-not $NoRedis) {
        if (Test-Port $RedisPort) {
            Write-Step "Redis already listening on $RedisPort - leaving it alone"
        } else {
            $redis = Resolve-RedisServer
            if ($redis) {
                Write-Step "Starting Redis on $RedisPort"
                $Services += Start-Service-Process -Name 'redis' -Color 'DarkGray' `
                    -FilePath $redis -ArgumentList '--port', "$RedisPort" `
                    -WorkingDirectory $Root
                Wait-ForPort $RedisPort 'Redis' 20 | Out-Null
            } else {
                Write-Warn 'Redis not found. The app will run single-instance with in-process fallbacks.'
            }
        }
    }

    # --- MCP tool server ----------------------------------------------------
    if (-not $NoMcp) {
        if (Test-Port $McpPort) {
            Write-Step "MCP already listening on $McpPort - leaving it alone"
        } else {
            Write-Step "Starting the MCP tool server on $McpPort"
            $Services += Start-Service-Process -Name 'mcp' -Color 'Magenta' `
                -FilePath $python -ArgumentList '-m', 'app.mcp.server' `
                -WorkingDirectory $Backend `
                -Environment @{ MCP_PORT = "$McpPort"; MCP_URL = '' }
            Wait-ForPort $McpPort 'The MCP server' 40 | Out-Null
        }
    }

    # --- Backend ------------------------------------------------------------
    Write-Step "Starting the API + chat gateway on $BackendPort"
    $inlineWorker = 'true'
    if ($SeparateWorker) { $inlineWorker = 'false' }
    $Services += Start-Service-Process -Name 'backend' -Color 'Green' `
        -FilePath $python `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--port', "$BackendPort" `
        -WorkingDirectory $Backend `
        -Environment @{
            SERVER_ID           = 'gateway-1'
            INLINE_AGENT_WORKER = $inlineWorker
            MCP_PORT            = "$McpPort"
            MCP_URL             = ''
        }
    Wait-ForPort $BackendPort 'The backend' 60 | Out-Null

    # --- Agent worker (only when it is not inside the API) ------------------
    if ($SeparateWorker) {
        Write-Step 'Starting the agent worker as its own process'
        $Services += Start-Service-Process -Name 'worker' -Color 'DarkYellow' `
            -FilePath $python -ArgumentList '-m', 'app.workers.agent_worker' `
            -WorkingDirectory $Backend `
            -Environment @{ SERVER_ID = 'worker-1'; MCP_PORT = "$McpPort"; MCP_URL = '' }
    }

    # --- Frontend -----------------------------------------------------------
    if (-not $NoFrontend) {
        Write-Step "Starting the frontend on $FrontendPort"
        $npm = 'npm.cmd'
        if (-not (Get-Command $npm -ErrorAction SilentlyContinue)) { $npm = 'npm' }
        $Services += Start-Service-Process -Name 'frontend' -Color 'Blue' `
            -FilePath $npm -ArgumentList 'run', 'dev', '--', '--port', "$FrontendPort" `
            -WorkingDirectory $Frontend `
            -Environment @{
                NEXT_PUBLIC_API_BASE = "http://localhost:$BackendPort"
                NEXT_PUBLIC_WS_BASE  = "ws://localhost:$BackendPort"
            }
    }

    # --- Ready --------------------------------------------------------------
    Write-Host ''
    Write-Host '  City Hospital is up' -ForegroundColor Green
    if (-not $NoFrontend) {
        Write-Host "    web       http://localhost:$FrontendPort"
    }
    Write-Host "    api       http://localhost:$BackendPort/docs"
    Write-Host "    health    http://localhost:$BackendPort/health"
    Write-Host "    chat ws   ws://localhost:$BackendPort/ws/chat"
    Write-Host "    logs      .dev-logs\"
    Write-Host ''
    Write-Host '  Ctrl+C stops everything.' -ForegroundColor DarkGray
    Write-Host ''

    # --- Pump the logs until every child has exited or Ctrl+C ---------------
    while ($true) {
        $alive = $false
        foreach ($service in $Services) {
            Write-ServiceLines $service
            if (-not $service.Process.HasExited) {
                $alive = $true
            } elseif (-not $service.Reported) {
                $service.Reported = $true
                Write-Warn "$($service.Name) exited with code $($service.Process.ExitCode)."
            }
        }
        if (-not $alive) {
            Write-Warn 'Every service has exited.'
            break
        }
        Start-Sleep -Milliseconds 250
    }
} finally {
    Stop-All
}
