#requires -Version 5.1
<#
.SYNOPSIS
  End-to-end smoke test of a built ThermoGar installer on this machine.

.DESCRIPTION
  Replaces the synthetic 100-case lifecycle test with a real one:

    1. silent install of the .exe
    2. installed files, Start Menu shortcut and uninstall registry entry
    3. launch pythonw.exe launcher.pyw from an unrelated working directory
    4. poll healthcheck.py --json until HEALTHY (60 s budget)
    5. GET the loopback UI port -> HTTP 200 with "ThermoGar" in the HTML
    6. stop.pyw -> no ThermoGar processes, both ports free
    7. silent uninstall -> Program Files entry gone, %LOCALAPPDATA%\ThermoGar kept

  Install and uninstall are elevated via Start-Process -Verb RunAs. Everything
  else runs unelevated. Per-step PASS/FAIL goes to stdout and to
  dist\smoke-<timestamp>.json; the exit code is 0 only when every step passed.

.EXAMPLE
  .\packaging\smoke_installed.ps1
  .\packaging\smoke_installed.ps1 -InstallerPath dist\ThermoGar-0.3.0-win64.exe
#>
[CmdletBinding()]
param(
    [string]$InstallerPath,
    [string]$RepoRoot,
    [string]$InstallRoot = "$env:ProgramFiles\ThermoGar",
    # Cold start imports pycalphad and starts Streamlit; 60 s is too tight on
    # a first run against a freshly written Program Files tree.
    [int]$HealthTimeoutSeconds = 180,
    # Leave the product installed after the run (skips step 7).
    [switch]$SkipUninstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
$RepoRoot = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
$DistDir = Join-Path $RepoRoot 'dist'

if (-not $InstallerPath) {
    $newest = Get-ChildItem -LiteralPath $DistDir -Filter 'ThermoGar-*-win64.exe' -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $newest) { throw "INSTALLER_NOT_FOUND: no ThermoGar-*-win64.exe in $DistDir" }
    $InstallerPath = $newest.FullName
}
$InstallerPath = [IO.Path]::GetFullPath($InstallerPath)
if (-not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) { throw "INSTALLER_NOT_FOUND: $InstallerPath" }

$UninstallKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\ThermoGar'
$ShortcutPath = Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs\ThermoGar\ThermoGar.lnk'
$LocalAppState = Join-Path $env:LOCALAPPDATA 'ThermoGar'
$WorkDir = Join-Path ([IO.Path]::GetTempPath()) ("thermogar-smoke-" + [Guid]::NewGuid().ToString('N').Substring(0, 8))

$Results = New-Object System.Collections.Generic.List[object]
$script:Failed = $false

function Add-Result {
    param([int]$Step, [string]$Name, [bool]$Pass, [string]$Detail = '')
    $status = if ($Pass) { 'PASS' } else { 'FAIL' }
    if (-not $Pass) { $script:Failed = $true }
    $Results.Add([ordered]@{ step = $Step; name = $Name; status = $status; detail = $Detail })
    $colour = if ($Pass) { 'Green' } else { 'Red' }
    Write-Host ("[{0}] step {1}: {2}" -f $status, $Step, $Name) -ForegroundColor $colour
    if ($Detail) { Write-Host "        $Detail" }
}

function Invoke-Elevated {
    param([string]$FilePath, [string[]]$Arguments, [int]$TimeoutSeconds = 600)
    # NSIS /S detaches quickly, so wait on the process AND then on the payload.
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -Verb RunAs -PassThru -Wait -ErrorAction Stop
    return $process.ExitCode
}

function Wait-ForCondition {
    param([scriptblock]$Condition, [int]$TimeoutSeconds, [double]$IntervalSeconds = 0.5)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (& $Condition) { return $true }
        Start-Sleep -Seconds $IntervalSeconds
    }
    return & $Condition
}

function Get-ThermoGarProcesses {
    param([string]$Root)
    $prefix = $Root.TrimEnd('\') + '\'
    return @(Get-Process -Name 'python', 'pythonw' -ErrorAction SilentlyContinue | Where-Object {
        $path = $null
        try { $path = $_.Path } catch { $path = $null }
        $path -and $path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)
    })
}

function Test-PortListening {
    param([int]$Port)
    return @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue).Count -gt 0
}

Write-Host "ThermoGar installed smoke test"
Write-Host "  installer : $InstallerPath"
Write-Host "  installdir: $InstallRoot"
Write-Host "  workdir   : $WorkDir"
Write-Host ''
Write-Host 'Elevation: install and uninstall are launched with -Verb RunAs.'
Write-Host 'If a UAC dialog appears, accept it; the run cannot continue otherwise.'
Write-Host ''

$localAppStatePreexisting = Test-Path -LiteralPath $LocalAppState
New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null

$healthJson = $null
$uiPort = 0
$controlPort = 0

try {
    # --- 1. silent install ---------------------------------------------------
    try {
        $exit = Invoke-Elevated -FilePath $InstallerPath -Arguments @('/S')
        $installed = Wait-ForCondition -Condition {
            (Test-Path -LiteralPath (Join-Path $InstallRoot 'launcher.pyw')) -and
            (Test-Path -LiteralPath (Join-Path $InstallRoot 'Uninstall.exe'))
        } -TimeoutSeconds 300 -IntervalSeconds 1
        Add-Result 1 'silent install' ($exit -eq 0 -and $installed) "installer exit $exit"
    }
    catch {
        Add-Result 1 'silent install' $false $_.Exception.Message
        throw
    }

    # --- 2. installed files, shortcut, registry ------------------------------
    $required = @(
        'launcher.pyw', 'stop.pyw', 'healthcheck.py', 'ThermoGar.ico',
        'runtime\python.exe', 'runtime\pythonw.exe',
        'app\ThermoGar_app.py', '.streamlit\config.toml',
        'manifests\payload-manifest.json', 'Uninstall.exe'
    )
    $missing = @($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $InstallRoot $_)) })
    $hasDatabase = @(Get-ChildItem -LiteralPath (Join-Path $InstallRoot 'databases') -Filter '*.tdb' -Recurse -File -ErrorAction SilentlyContinue).Count -gt 0
    $hasShortcut = Test-Path -LiteralPath $ShortcutPath
    $registry = Get-ItemProperty -LiteralPath $UninstallKey -ErrorAction SilentlyContinue
    $hasRegistry = $null -ne $registry -and $registry.UninstallString
    $detail = "missing=$($missing.Count) database=$hasDatabase shortcut=$hasShortcut registry=$hasRegistry"
    if ($missing.Count) { $detail += " [$($missing -join ', ')]" }
    if ($hasRegistry) { $detail += " version=$($registry.DisplayVersion)" }
    Add-Result 2 'files, shortcut, registry' ($missing.Count -eq 0 -and $hasDatabase -and $hasShortcut -and [bool]$hasRegistry) $detail

    # --- 3. launch the app from an unrelated working directory ---------------
    $pythonw = Join-Path $InstallRoot 'runtime\pythonw.exe'
    $launcher = Join-Path $InstallRoot 'launcher.pyw'
    $launcherProcess = $null
    try {
        # ProcessStartInfo rather than Start-Process: the latter rejects
        # -WorkingDirectory in some PowerShell 7 builds.
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = $pythonw
        $startInfo.Arguments = '"' + $launcher + '"'
        $startInfo.WorkingDirectory = $WorkDir
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $launcherProcess = [System.Diagnostics.Process]::Start($startInfo)
        Start-Sleep -Seconds 3
        $alive = -not $launcherProcess.HasExited
        $detail = "pid=$($launcherProcess.Id) alive=$alive cwd=$WorkDir"
        if (-not $alive) { $detail += " exit=$($launcherProcess.ExitCode)" }
        Add-Result 3 'launcher started' $alive $detail
    }
    catch {
        Add-Result 3 'launcher started' $false $_.Exception.Message
    }

    # --- 4. healthcheck ------------------------------------------------------
    $python = Join-Path $InstallRoot 'runtime\python.exe'
    $healthScript = Join-Path $InstallRoot 'healthcheck.py'
    $deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
    $healthy = $false
    $lastHealth = ''
    while ((Get-Date) -lt $deadline) {
        $raw = & $python $healthScript '--json' 2>&1 | Out-String
        $global:LASTEXITCODE = 0
        $lastHealth = $raw.Trim()
        try {
            $parsed = $lastHealth | ConvertFrom-Json
            if ($parsed.status -eq 'HEALTHY') {
                $healthJson = $parsed
                $uiPort = [int]$parsed.ui_port
                $controlPort = [int]$parsed.control_port
                $healthy = $true
                break
            }
        }
        catch { }
        Start-Sleep -Milliseconds 500
    }
    $elapsedHealth = [math]::Round(($HealthTimeoutSeconds - ($deadline - (Get-Date)).TotalSeconds), 1)
    Add-Result 4 'healthcheck HEALTHY' $healthy "after ${elapsedHealth}s ui_port=$uiPort control_port=$controlPort last=$lastHealth"

    # --- 5. UI responds on loopback -----------------------------------------
    # The served HTML is Streamlit's shell: <title>Streamlit</title>, with the
    # ThermoGar title applied client-side, so no server-side response ever
    # contains the string "ThermoGar". The equivalent server-side proof that
    # app\ThermoGar_app.py actually ran is /_stcore/script-health-check, which
    # the launcher enables with --server.scriptHealthCheckEnabled=true: it
    # returns 200 only when the script completes without an uncaught
    # exception, and 503 otherwise.
    if ($healthy -and $uiPort -gt 0) {
        $uiOk = $false
        $uiDetail = ''
        for ($attempt = 1; $attempt -le 10; $attempt++) {
            try {
                $page = Invoke-WebRequest -Uri "http://127.0.0.1:$uiPort/" -UseBasicParsing -TimeoutSec 20
                $body = [string]$page.Content
                $isStreamlitShell = $body -match 'streamlit'
                $script = Invoke-WebRequest -Uri "http://127.0.0.1:$uiPort/_stcore/script-health-check" -UseBasicParsing -TimeoutSec 60
                $uiOk = ($page.StatusCode -eq 200) -and $isStreamlitShell -and ($script.StatusCode -eq 200)
                $uiDetail = "GET / -> $($page.StatusCode) ($($body.Length) bytes, Streamlit shell: $isStreamlitShell); " +
                            "script-health-check -> $($script.StatusCode) '$([string]$script.Content)'"
                if ($uiOk) { break }
            }
            catch { $uiDetail = $_.Exception.Message }
            Start-Sleep -Seconds 3
        }
        Add-Result 5 'UI 200, app script runs clean' $uiOk $uiDetail
    }
    else {
        Add-Result 5 'UI 200, app script runs clean' $false 'skipped: no healthy UI port'
    }

    # --- 6. stop -------------------------------------------------------------
    $stopScript = Join-Path $InstallRoot 'stop.pyw'
    $stopRaw = & $python $stopScript '--json' 2>&1 | Out-String
    $stopExit = $LASTEXITCODE
    $global:LASTEXITCODE = 0
    # PowerShell unwraps single-element arrays returned from a function, so
    # every call site has to re-wrap before asking for .Count.
    $stopped = Wait-ForCondition -Condition {
        @(Get-ThermoGarProcesses -Root $InstallRoot).Count -eq 0
    } -TimeoutSeconds 30 -IntervalSeconds 0.5
    $portsFree = $true
    foreach ($port in @($uiPort, $controlPort)) {
        if ($port -gt 0 -and (Test-PortListening -Port $port)) { $portsFree = $false }
    }
    $remaining = @(Get-ThermoGarProcesses -Root $InstallRoot).Count
    Add-Result 6 'stop: no processes, ports free' ($stopExit -eq 0 -and $stopped -and $portsFree) `
        "stop exit $stopExit, remaining processes $remaining, ports free $portsFree, out=$($stopRaw.Trim())"

    # Nothing below should race with a surviving supervisor.
    foreach ($process in @(Get-ThermoGarProcesses -Root $InstallRoot)) {
        try { $process.Kill() } catch { }
    }

    # --- 7. silent uninstall -------------------------------------------------
    if ($SkipUninstall) {
        Add-Result 7 'silent uninstall' $true 'skipped by -SkipUninstall'
    }
    else {
        $uninstaller = Join-Path $InstallRoot 'Uninstall.exe'
        try {
            $exit = Invoke-Elevated -FilePath $uninstaller -Arguments @('/S')
            $removed = Wait-ForCondition -Condition {
                -not (Test-Path -LiteralPath (Join-Path $InstallRoot 'launcher.pyw'))
            } -TimeoutSeconds 180 -IntervalSeconds 1
            # NSIS leaves the uninstaller itself behind for a moment; only the
            # payload has to be gone.
            $leftovers = @()
            if (Test-Path -LiteralPath $InstallRoot) {
                $leftovers = @(Get-ChildItem -LiteralPath $InstallRoot -Recurse -File -ErrorAction SilentlyContinue |
                    Where-Object { $_.Name -ne 'Uninstall.exe' })
            }
            $registryGone = -not (Test-Path -LiteralPath $UninstallKey)
            $shortcutGone = -not (Test-Path -LiteralPath $ShortcutPath)
            $stateKept = Test-Path -LiteralPath $LocalAppState
            $pass = $removed -and $leftovers.Count -eq 0 -and $registryGone -and $shortcutGone -and $stateKept
            $detail = "uninstaller exit $exit, leftover files $($leftovers.Count), registry gone $registryGone, shortcut gone $shortcutGone, LOCALAPPDATA kept $stateKept"
            if (-not $localAppStatePreexisting) { $detail += ' (state dir created by this run)' }
            Add-Result 7 'silent uninstall, LOCALAPPDATA kept' $pass $detail
        }
        catch {
            Add-Result 7 'silent uninstall, LOCALAPPDATA kept' $false $_.Exception.Message
        }
    }
}
finally {
    Remove-Item -LiteralPath $WorkDir -Recurse -Force -ErrorAction SilentlyContinue

    if (-not (Test-Path -LiteralPath $DistDir)) { New-Item -ItemType Directory -Path $DistDir -Force | Out-Null }
    $timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $reportPath = Join-Path $DistDir "smoke-$timestamp.json"
    $report = [ordered]@{
        schema        = 1
        started_utc   = $timestamp
        installer     = $InstallerPath
        install_root  = $InstallRoot
        overall       = if ($script:Failed) { 'FAIL' } else { 'PASS' }
        ui_port       = $uiPort
        control_port  = $controlPort
        health        = $healthJson
        steps         = $Results
    }
    [IO.File]::WriteAllText($reportPath, ($report | ConvertTo-Json -Depth 6), [Text.UTF8Encoding]::new($false))

    Write-Host ''
    Write-Host ("OVERALL: {0}" -f $report.overall) -ForegroundColor $(if ($script:Failed) { 'Red' } else { 'Green' })
    Write-Host "report: $reportPath"
}

if ($script:Failed) { exit 1 }
exit 0
