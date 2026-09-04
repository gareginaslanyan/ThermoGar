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
    8. upgrade over an existing install: install -> start -> stop -> install the
       same version silently over the top -> start -> health OK -> stop ->
       uninstall, with a user project file written into
       %LOCALAPPDATA%\ThermoGar\workspace\projects before the upgrade and
       checked byte for byte after it and after the uninstall

  The five install/uninstall operations are elevated, everything else is not.
  They all go through one helper process that this script starts for itself with
  Start-Process -Verb RunAs, so a full run raises a single UAC prompt instead of
  five. If the helper cannot be started or does not come up, the run falls back
  to elevating each operation on its own and asks five times as before.
  Per-step PASS/FAIL goes to stdout and to dist\smoke-<timestamp>.json; the exit
  code is 0 only when every step passed.

.EXAMPLE
  .\packaging\smoke_installed.ps1
  .\packaging\smoke_installed.ps1 -InstallerPath dist\ThermoGar-0.3.0-win64.exe
#>
[CmdletBinding()]
param(
    [string]$InstallerPath,
    [string]$RepoRoot,
    [string]$InstallRoot = "$env:ProgramFiles\ThermoGar",
    # Cold start imports pycalphad, starts Streamlit and runs the app script
    # once before the launcher will publish a run record. Measured at ~17 s for
    # the script alone on a warm cache; the launcher's own discovery budget is
    # 240 s, so this has to be larger than that or a slow first start reads as
    # a failure that is really just a timeout.
    [int]$HealthTimeoutSeconds = 300,
    # Leave the product installed after the run (skips step 7).
    [switch]$SkipUninstall,
    # Internal: this script re-invokes itself elevated in this mode to serve as
    # the install/uninstall helper. Not meant to be passed by hand.
    [switch]$ElevatedAgent,
    [string]$AgentDir
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

# --- One UAC prompt per run --------------------------------------------------
# Five elevated operations used to mean five prompts. Instead the unelevated
# script starts one copy of itself with -Verb RunAs (-ElevatedAgent) and posts
# work to it through a queue directory.
#
# The helper never takes a program to run from the queue. Both commands it can
# execute are pinned on its own command line when it starts - the installer this
# run was invoked with, and $InstallRoot\Uninstall.exe - and a queue file only
# names which of the two to run. So a file dropped into the queue directory by
# anything else running as this user still cannot make the elevated process
# launch a program of its choosing.
function Write-AgentJson {
    param([string]$Path, $Value)
    # Written aside and renamed: the reader must never see half a file.
    $temporary = "$Path.partial"
    [IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 4 -Compress), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Invoke-ElevatedAgentLoop {
    param([string]$Dir, [string]$Installer, [string]$Root, [int]$IdleTimeoutSeconds = 1800)
    if (-not (Test-Path -LiteralPath $Dir)) { New-Item -ItemType Directory -Path $Dir -Force | Out-Null }
    Write-AgentJson -Path (Join-Path $Dir 'ready.json') -Value ([ordered]@{
        pid = $PID; installer = $Installer; install_root = $Root
    })
    $idleDeadline = (Get-Date).AddSeconds($IdleTimeoutSeconds)
    while ((Get-Date) -lt $idleDeadline) {
        if (Test-Path -LiteralPath (Join-Path $Dir 'stop')) { break }
        $request = @(Get-ChildItem -LiteralPath $Dir -Filter 'cmd-*.json' -File -ErrorAction SilentlyContinue |
            Sort-Object Name) | Select-Object -First 1
        if (-not $request) { Start-Sleep -Milliseconds 200; continue }
        $sequence = $request.BaseName -replace '^cmd-', ''
        $operation = ''
        try { $operation = [string]((Get-Content -LiteralPath $request.FullName -Raw | ConvertFrom-Json).op) }
        catch { $operation = '' }
        Remove-Item -LiteralPath $request.FullName -Force -ErrorAction SilentlyContinue
        $exitCode = -1
        $failure = ''
        try {
            switch ($operation) {
                'install' {
                    $exitCode = (Start-Process -FilePath $Installer -ArgumentList '/S' -PassThru -Wait).ExitCode
                }
                'uninstall' {
                    $uninstaller = Join-Path $Root 'Uninstall.exe'
                    if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
                        throw "UNINSTALLER_MISSING: $uninstaller"
                    }
                    $exitCode = (Start-Process -FilePath $uninstaller -ArgumentList '/S' -PassThru -Wait).ExitCode
                }
                default { throw "UNKNOWN_OPERATION: '$operation'" }
            }
        }
        catch { $failure = $_.Exception.Message }
        Write-AgentJson -Path (Join-Path $Dir "res-$sequence.json") -Value ([ordered]@{
            op = $operation; exit = $exitCode; error = $failure
        })
        $idleDeadline = (Get-Date).AddSeconds($IdleTimeoutSeconds)
    }
}

if ($ElevatedAgent) {
    if (-not $AgentDir) { throw 'AGENT_DIR_REQUIRED' }
    Invoke-ElevatedAgentLoop -Dir $AgentDir -Installer $InstallerPath -Root $InstallRoot
    exit 0
}

$script:AgentDir = $null
$script:AgentProcess = $null
$script:AgentSequence = 0

$UninstallKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\ThermoGar'
$ShortcutPath = Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs\ThermoGar\ThermoGar.lnk'
$LocalAppState = Join-Path $env:LOCALAPPDATA 'ThermoGar'
$WorkDir = Join-Path ([IO.Path]::GetTempPath()) ("thermogar-smoke-" + [Guid]::NewGuid().ToString('N').Substring(0, 8))

$Results = New-Object System.Collections.Generic.List[object]
$script:Failed = $false

# Reset by Add-Result, so each step reports its own wall clock. Step 1 is how
# long a silent install takes on this machine.
$script:StepClock = Get-Date

function Add-Result {
    param([int]$Step, [string]$Name, [bool]$Pass, [string]$Detail = '')
    $status = if ($Pass) { 'PASS' } else { 'FAIL' }
    if (-not $Pass) { $script:Failed = $true }
    $seconds = [math]::Round(((Get-Date) - $script:StepClock).TotalSeconds, 1)
    $script:StepClock = Get-Date
    $Results.Add([ordered]@{ step = $Step; name = $Name; status = $status; seconds = $seconds; detail = $Detail })
    $colour = if ($Pass) { 'Green' } else { 'Red' }
    Write-Host ("[{0}] step {1}: {2} ({3}s)" -f $status, $Step, $Name, $seconds) -ForegroundColor $colour
    if ($Detail) { Write-Host "        $Detail" }
}

function Invoke-AgentOperation {
    param([string]$Operation, [int]$TimeoutSeconds = 900)
    $script:AgentSequence++
    $sequence = '{0:d3}' -f $script:AgentSequence
    $resultPath = Join-Path $script:AgentDir "res-$sequence.json"
    Write-AgentJson -Path (Join-Path $script:AgentDir "cmd-$sequence.json") -Value ([ordered]@{ op = $Operation })
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $resultPath) {
            $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
            Remove-Item -LiteralPath $resultPath -Force -ErrorAction SilentlyContinue
            if ($result.error) { throw "ELEVATED_${Operation}_FAILED: $($result.error)" }
            return [int]$result.exit
        }
        if ($script:AgentProcess -and $script:AgentProcess.HasExited) {
            throw "ELEVATED_HELPER_EXITED: $($script:AgentProcess.ExitCode)"
        }
        Start-Sleep -Milliseconds 200
    }
    throw "ELEVATED_${Operation}_TIMEOUT: no answer after ${TimeoutSeconds}s"
}

function Start-ElevatedAgent {
    # One UAC prompt. Returns $false if the helper never came up, and the caller
    # then keeps the old behaviour of elevating every operation separately.
    $dir = Join-Path ([IO.Path]::GetTempPath()) ("thermogar-elevated-" + [Guid]::NewGuid().ToString('N').Substring(0, 12))
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $shell = [Diagnostics.Process]::GetCurrentProcess().Path
    # Start-Process joins -ArgumentList with spaces and quotes nothing, so every
    # path has to carry its own quotes: "C:\Program Files\ThermoGar" would
    # otherwise arrive as two arguments. A trailing backslash inside the quotes
    # would escape the closing one, and these are all directories, so it goes.
    $quote = { param([string]$value) '"' + $value.TrimEnd('') + '"' }
    $arguments = @(
        '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-File', (& $quote $PSCommandPath),
        '-ElevatedAgent', '-AgentDir', (& $quote $dir),
        '-InstallerPath', (& $quote $InstallerPath),
        '-InstallRoot', (& $quote $InstallRoot)
    )
    try {
        $script:AgentProcess = Start-Process -FilePath $shell -ArgumentList $arguments -Verb RunAs `
            -WindowStyle Hidden -PassThru -ErrorAction Stop
    }
    catch {
        Write-Host "  elevated helper not started ($($_.Exception.Message)); one UAC prompt per operation." -ForegroundColor Yellow
        $script:AgentProcess = $null
        Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
        return $false
    }
    $ready = Wait-ForCondition -Condition {
        Test-Path -LiteralPath (Join-Path $dir 'ready.json')
    } -TimeoutSeconds 120 -IntervalSeconds 0.5
    if (-not $ready) {
        Write-Host '  elevated helper did not report ready; one UAC prompt per operation.' -ForegroundColor Yellow
        try { if (-not $script:AgentProcess.HasExited) { $script:AgentProcess.Kill() } } catch { }
        $script:AgentProcess = $null
        Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
        return $false
    }
    $script:AgentDir = $dir
    return $true
}

function Stop-ElevatedAgent {
    if ($script:AgentDir) {
        try { [IO.File]::WriteAllText((Join-Path $script:AgentDir 'stop'), '') } catch { }
    }
    if ($script:AgentProcess) {
        try { $script:AgentProcess.WaitForExit(30000) | Out-Null } catch { }
        try { if (-not $script:AgentProcess.HasExited) { $script:AgentProcess.Kill() } } catch { }
        $script:AgentProcess = $null
    }
    if ($script:AgentDir) {
        Remove-Item -LiteralPath $script:AgentDir -Recurse -Force -ErrorAction SilentlyContinue
        $script:AgentDir = $null
    }
}

function Invoke-Elevated {
    param([string]$FilePath, [string[]]$Arguments, [int]$TimeoutSeconds = 900)
    # NSIS /S detaches quickly, so wait on the process AND then on the payload.
    # With the helper up this costs no prompt; without it, one prompt per call.
    if ($script:AgentDir) {
        $operation = ''
        if ($FilePath -eq $InstallerPath) { $operation = 'install' }
        elseif ($FilePath -eq (Join-Path $InstallRoot 'Uninstall.exe')) { $operation = 'uninstall' }
        if ($operation) { return (Invoke-AgentOperation -Operation $operation -TimeoutSeconds $TimeoutSeconds) }
    }
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

# Steps 3, 4 and 6 do this inline against the shared $Results bookkeeping. Step 8
# runs the same three moves twice more, so it uses these instead of repeating the
# bodies; steps 1-7 are left exactly as they were.
function Start-InstalledApp {
    param([string]$Root, [string]$Cwd)
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = Join-Path $Root 'runtime\pythonw.exe'
    $startInfo.Arguments = '"' + (Join-Path $Root 'launcher.pyw') + '"'
    $startInfo.WorkingDirectory = $Cwd
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    return [System.Diagnostics.Process]::Start($startInfo)
}

function Wait-InstalledHealthy {
    param([string]$Root, [int]$TimeoutSeconds)
    $python = Join-Path $Root 'runtime\python.exe'
    $healthScript = Join-Path $Root 'healthcheck.py'
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $raw = & $python $healthScript '--json' 2>&1 | Out-String
        $global:LASTEXITCODE = 0
        try {
            $parsed = $raw.Trim() | ConvertFrom-Json
            if ($parsed.status -eq 'HEALTHY') { return $parsed }
        }
        catch { }
        Start-Sleep -Milliseconds 500
    }
    return $null
}

function Stop-InstalledApp {
    param([string]$Root)
    $python = Join-Path $Root 'runtime\python.exe'
    & $python (Join-Path $Root 'stop.pyw') '--json' 2>&1 | Out-Null
    $exit = $LASTEXITCODE
    $global:LASTEXITCODE = 0
    $gone = Wait-ForCondition -Condition {
        @(Get-ThermoGarProcesses -Root $Root).Count -eq 0
    } -TimeoutSeconds 30 -IntervalSeconds 0.5
    foreach ($process in @(Get-ThermoGarProcesses -Root $Root)) {
        try { $process.Kill() } catch { }
    }
    return [pscustomobject]@{ ExitCode = $exit; Stopped = $gone }
}

Write-Host "ThermoGar installed smoke test"
Write-Host "  installer : $InstallerPath"
Write-Host "  installdir: $InstallRoot"
Write-Host "  workdir   : $WorkDir"
Write-Host ''
Write-Host 'Elevation: the five install/uninstall operations run inside one elevated'
Write-Host 'helper, so expect a single UAC dialog now. Accept it; the run cannot'
Write-Host 'continue otherwise. If the helper does not start, each operation asks'
Write-Host 'for its own confirmation instead.'
$agentUp = Start-ElevatedAgent
Write-Host ("  elevated helper: {0}" -f $(if ($agentUp) { "up, 1 UAC prompt for this run" } else { "unavailable, 5 UAC prompts for this run" }))
Write-Host ''

$localAppStatePreexisting = Test-Path -LiteralPath $LocalAppState
New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null
$script:StepClock = Get-Date

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

    # --- 8. upgrade over an existing install ---------------------------------
    # A whole second lifecycle: install, start, stop, install the same version
    # silently over the top, start, health OK, stop, uninstall. A user project
    # file is written into the workspace before the upgrade and has to come
    # back byte for byte afterwards, and still be there once the product is
    # uninstalled again. Steps 1-7 leave nothing installed, so this starts from
    # the same clean state they did.
    if ($SkipUninstall) {
        Add-Result 8 'upgrade over existing install, user project kept' $true 'skipped by -SkipUninstall'
    }
    else {
        $probeDir = Join-Path $LocalAppState 'workspace\projects'
        $probePath = Join-Path $probeDir 'wave4a-upgrade-probe.thermogar.json'
        $probeBody = '{"schema":1,"name":"wave4a upgrade probe","note":"must survive an upgrade over an existing install"}'
        $upgradeWork = Join-Path ([IO.Path]::GetTempPath()) ("thermogar-upgrade-" + [Guid]::NewGuid().ToString('N').Substring(0, 8))
        $upgradeDetail = New-Object System.Collections.Generic.List[string]
        $upgradePass = $false
        New-Item -ItemType Directory -Path $upgradeWork -Force | Out-Null
        try {
            # 8a. install
            $exitFirst = Invoke-Elevated -FilePath $InstallerPath -Arguments @('/S')
            $installedFirst = Wait-ForCondition -Condition {
                Test-Path -LiteralPath (Join-Path $InstallRoot 'launcher.pyw')
            } -TimeoutSeconds 300 -IntervalSeconds 1
            $upgradeDetail.Add("install exit $exitFirst, files $installedFirst")

            # 8b. start, then stop
            Start-InstalledApp -Root $InstallRoot -Cwd $upgradeWork | Out-Null
            $healthFirst = Wait-InstalledHealthy -Root $InstallRoot -TimeoutSeconds $HealthTimeoutSeconds
            $stopFirst = Stop-InstalledApp -Root $InstallRoot
            $upgradeDetail.Add("start healthy $([bool]$healthFirst), stop exit $($stopFirst.ExitCode) clean $($stopFirst.Stopped)")

            # 8c. the user's project, written before the upgrade
            if (-not (Test-Path -LiteralPath $probeDir)) { New-Item -ItemType Directory -Path $probeDir -Force | Out-Null }
            [IO.File]::WriteAllText($probePath, $probeBody, [Text.UTF8Encoding]::new($false))
            $probeHashBefore = (Get-FileHash -LiteralPath $probePath -Algorithm SHA256).Hash

            # 8d. the same version, installed silently over the top
            $exitUpgrade = Invoke-Elevated -FilePath $InstallerPath -Arguments @('/S')
            $installedUpgrade = Wait-ForCondition -Condition {
                Test-Path -LiteralPath (Join-Path $InstallRoot 'launcher.pyw')
            } -TimeoutSeconds 300 -IntervalSeconds 1
            $upgradeDetail.Add("upgrade install exit $exitUpgrade, files $installedUpgrade")

            # 8e. start again: healthy, and the app script still runs clean
            Start-InstalledApp -Root $InstallRoot -Cwd $upgradeWork | Out-Null
            $healthUpgrade = Wait-InstalledHealthy -Root $InstallRoot -TimeoutSeconds $HealthTimeoutSeconds
            $upgradePort = 0
            if ($healthUpgrade) { $upgradePort = [int]$healthUpgrade.ui_port }
            $upgradeUi = $false
            if ($upgradePort -gt 0) {
                for ($attempt = 1; $attempt -le 10; $attempt++) {
                    try {
                        $upgradePage = Invoke-WebRequest -Uri "http://127.0.0.1:$upgradePort/" -UseBasicParsing -TimeoutSec 20
                        $upgradeCheck = Invoke-WebRequest -Uri "http://127.0.0.1:$upgradePort/_stcore/script-health-check" -UseBasicParsing -TimeoutSec 60
                        $upgradeUi = ($upgradePage.StatusCode -eq 200) -and ($upgradeCheck.StatusCode -eq 200)
                        if ($upgradeUi) { break }
                    }
                    catch { }
                    Start-Sleep -Seconds 3
                }
            }
            $upgradeDetail.Add("restart healthy $([bool]$healthUpgrade) ui_port $upgradePort, UI and script-health-check 200 $upgradeUi")

            # 8f. stop again
            $stopUpgrade = Stop-InstalledApp -Root $InstallRoot
            $upgradeDetail.Add("stop exit $($stopUpgrade.ExitCode) clean $($stopUpgrade.Stopped)")

            # 8g. the project survived the upgrade unchanged
            $probeKept = Test-Path -LiteralPath $probePath
            $probeSame = $false
            if ($probeKept) {
                $probeSame = (Get-FileHash -LiteralPath $probePath -Algorithm SHA256).Hash -eq $probeHashBefore
            }
            $upgradeDetail.Add("project kept across upgrade $probeKept, identical $probeSame")

            # 8h. uninstall, project still there
            $exitRemove = Invoke-Elevated -FilePath (Join-Path $InstallRoot 'Uninstall.exe') -Arguments @('/S')
            $removed = Wait-ForCondition -Condition {
                -not (Test-Path -LiteralPath (Join-Path $InstallRoot 'launcher.pyw'))
            } -TimeoutSeconds 180 -IntervalSeconds 1
            $probeAfterRemove = Test-Path -LiteralPath $probePath
            $upgradeDetail.Add("uninstall exit $exitRemove removed $removed, project kept $probeAfterRemove")

            $upgradePass = ($exitFirst -eq 0) -and $installedFirst -and [bool]$healthFirst -and $stopFirst.Stopped -and
                           ($exitUpgrade -eq 0) -and $installedUpgrade -and [bool]$healthUpgrade -and $upgradeUi -and $stopUpgrade.Stopped -and
                           $probeKept -and $probeSame -and
                           ($exitRemove -eq 0) -and $removed -and $probeAfterRemove
        }
        catch {
            $upgradeDetail.Add("exception: $($_.Exception.Message)")
        }
        finally {
            Remove-Item -LiteralPath $upgradeWork -Recurse -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue
        }
        Add-Result 8 'upgrade over existing install, user project kept' $upgradePass ($upgradeDetail -join '; ')
    }
}
finally {
    Stop-ElevatedAgent
    Remove-Item -LiteralPath $WorkDir -Recurse -Force -ErrorAction SilentlyContinue

    if (-not (Test-Path -LiteralPath $DistDir)) { New-Item -ItemType Directory -Path $DistDir -Force | Out-Null }
    $timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $reportPath = Join-Path $DistDir "smoke-$timestamp.json"
    $report = [ordered]@{
        schema        = 1
        started_utc   = $timestamp
        installer     = $InstallerPath
        install_root  = $InstallRoot
        elevated_helper = $agentUp
        uac_prompts   = if ($agentUp) { 1 } else { 5 }
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
