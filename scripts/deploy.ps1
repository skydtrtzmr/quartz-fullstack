<#
.SYNOPSIS
  One-command environment preparation for quartz5 production deploy (Windows Server).

.DESCRIPTION
  Run from the package root after extracting. It does three things:
    1) Validate runtime (Node >= 22 / npm)
    2) Install base dependencies (npm ci under quartz5, npm registry only)
    3) Create privilege-free directory junctions for local plugins (reused by the loader)
  It does NOT build the site or start the Go server.

  NOTE: this file is intentionally ASCII-only. Windows PowerShell 5.1 reads .ps1 with
  the system ANSI code page when there is no BOM, which garbles non-ASCII text and can
  break parsing. Keeping it ASCII avoids that entirely.

.PARAMETER Force
  Force re-run of npm ci (skipped by default when node_modules already exists).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\deploy.ps1 -Force
#>
[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$Root = Split-Path -Parent $ScriptDir
Write-Host "[deploy] package root: $Root"

# ---------------------------------------------------------------- 1. validate runtime
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "node not found. Please install Node >= 22." }
if (-not (Get-Command npm  -ErrorAction SilentlyContinue)) { throw "npm not found." }

$nodeVer = (& node -v).Trim()
$major = [int](($nodeVer -replace '^v', '').Split('.')[0])
if ($major -lt 22) { throw "Node too old: $nodeVer (quartz5 requires >= 22)." }
$npmVer = (& npm -v).Trim()
Write-Host "[deploy] runtime: node $nodeVer / npm $npmVer"

# ---------------------------------------------------------------- 2. install base deps
$Quartz5 = Join-Path $Root "quartz5"
if (-not (Test-Path (Join-Path $Quartz5 "package.json")))      { throw "missing quartz5/package.json - package layout is wrong." }
if (-not (Test-Path (Join-Path $Quartz5 "package-lock.json"))) { throw "missing quartz5/package-lock.json - cannot npm ci." }

$NodeModules = Join-Path $Quartz5 "node_modules"
if ($Force -or -not (Test-Path $NodeModules)) {
    Write-Host "[deploy] installing base dependencies (npm ci)..."
    Push-Location $Quartz5
    try {
        $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        & npm ci
        $code = $LASTEXITCODE
        $ErrorActionPreference = $prev
        if ($code -ne 0) { throw "npm ci failed (exit code $code)." }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[deploy] quartz5/node_modules already present - skipping npm ci (use -Force to reinstall)."
}

# ---------------------------------------------------------------- 3. wire local plugins (junction)
$Linker = Join-Path $ScriptDir "setup-local-plugins.mjs"
if (-not (Test-Path $Linker)) { throw "missing scripts/setup-local-plugins.mjs - package layout is wrong." }

if (-not (Test-Path (Join-Path $Root "plugins-local"))) {
    Write-Warning "plugins-local/ not found - skipping local plugin wiring."
} else {
    Write-Host "[deploy] creating junctions for local plugins (no admin required)..."
    $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & node $Linker --link-only
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) { throw "local plugin junction step failed (exit code $code)." }
}

# ---------------------------------------------------------------- 4. done
Write-Host ""
Write-Host "[deploy] environment ready. Next steps (out of scope of this script):"
Write-Host "  Build per domain:"
Write-Host "    cd quartz5"
Write-Host "    npm run quartz -- build -d ../input/<domain> -o ../output/<domain> --settings ../settings/<domain> --sqlite --cacheDir ../cache/<domain>"
Write-Host "  Start the Go server via the existing server workflow."
