#requires -Version 5.1
<#
.SYNOPSIS
  Stages the ThermoGar payload tree for the NSIS installer.

.DESCRIPTION
  Copies an allowlisted subset of the repository plus the bundled CPython runtime
  into a staging directory, then writes manifests/payload-manifest.json listing
  every staged file with its size and SHA-256.

  No trust manifests, no receipts, no SBOM, no expected-hash gates. The manifest
  is descriptive output, not an input gate.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot,
    [string]$RuntimeSource,
    [string]$StageRoot,
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if (-not $RepoRoot)      { $RepoRoot = Split-Path -Parent $PSScriptRoot }
if (-not $RuntimeSource) {
    # The runtime lives in the main checkout; a git worktree does not carry it.
    $candidates = @(
        (Join-Path $RepoRoot 'ThermoGar-Installer-Assets\runtime-clean-3119'),
        'C:\Users\gareg\Desktop\ThermoGar\ThermoGar-Installer-Assets\runtime-clean-3119'
    )
    $RuntimeSource = $candidates | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'python.exe') } | Select-Object -First 1
    if (-not $RuntimeSource) { throw "RUNTIME_SOURCE_NOT_FOUND: tried $($candidates -join '; ')" }
}
if (-not $StageRoot)     { $StageRoot = Join-Path $RepoRoot 'dist\stage' }

$RepoRoot      = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
$RuntimeSource = [IO.Path]::GetFullPath($RuntimeSource).TrimEnd('\')
$StageRoot     = [IO.Path]::GetFullPath($StageRoot).TrimEnd('\')

function Write-Step { param([string]$Message) if (-not $Quiet) { Write-Host "  $Message" } }

# --- Payload allowlist -------------------------------------------------------
# Each entry: Source (repo-relative), Dest (stage-relative), Include (filter),
# Recurse.
$PayloadSets = @(
    @{ Source = 'app';                 Dest = 'app';                 Include = '*.py';        Recurse = $false }
    @{ Source = 'app';                 Dest = 'app';                 Include = 'style.css';   Recurse = $false }
    @{ Source = 'configs';             Dest = 'configs';             Include = '*';           Recurse = $true  }
    @{ Source = 'databases\converted'; Dest = 'databases\converted'; Include = '*';           Recurse = $true  }
    @{ Source = 'databases\physical';  Dest = 'databases\physical';  Include = '*';           Recurse = $true  }
    @{ Source = '.streamlit';          Dest = '.streamlit';          Include = 'config.toml'; Recurse = $false }
)

$SingleFiles = @(
    @{ Source = 'packaging\launcher.pyw';   Dest = 'launcher.pyw';               Required = $true  }
    @{ Source = 'packaging\stop.pyw';       Dest = 'stop.pyw';                   Required = $true  }
    @{ Source = 'packaging\healthcheck.py'; Dest = 'healthcheck.py';             Required = $true  }
    @{ Source = 'packaging\assets\ThermoGar.ico'; Dest = 'ThermoGar.ico';        Required = $true  }
    @{ Source = 'README.md';                Dest = 'README.md';                  Required = $false }
    @{ Source = 'USER_GUIDE_THERMOGAR.md';  Dest = 'USER_GUIDE_THERMOGAR.md';    Required = $false }
    @{ Source = 'QUICK_START_THERMOGAR.md'; Dest = 'QUICK_START_THERMOGAR.md';   Required = $false }
    @{ Source = 'THIRD_PARTY_NOTICES.txt';  Dest = 'THIRD_PARTY_NOTICES.txt';    Required = $false }
    @{ Source = 'PHYSICAL_DATA_README.md';  Dest = 'PHYSICAL_DATA_README.md';    Required = $false }
    @{ Source = 'USER_DATA_README.txt';     Dest = 'USER_DATA_README.txt';       Required = $false }
)

# Directory names never staged, at any depth.
$DeniedDirNames = @('__pycache__', '.git', '.pytest_cache', '.ipynb_checkpoints', 'original', 'diagnostic', 'experimental')
# File extensions never staged.
$DeniedExtensions = @('.pyc', '.pyo', '.bak', '.log', '.tmp')
# databases/physical/original is the sole exception to the denied 'original' rule:
# physical_data_v103.pdb lives there and the app loads it.
$DeniedDirExceptions = @('databases\physical\original')

function Test-Denied {
    param([string]$RelativePath)
    $parts = $RelativePath -split '\\'
    for ($i = 0; $i -lt $parts.Length - 1; $i++) {
        if ($DeniedDirNames -contains $parts[$i]) {
            $prefix = ($parts[0..$i] -join '\')
            if ($DeniedDirExceptions -notcontains $prefix) { return $true }
        }
    }
    $extension = [IO.Path]::GetExtension($RelativePath)
    if ($extension -and ($DeniedExtensions -contains $extension.ToLowerInvariant())) { return $true }
    return $false
}

function Copy-PayloadFile {
    param([string]$From, [string]$To)
    $parent = Split-Path -Parent $To
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Copy-Item -LiteralPath $From -Destination $To -Force
}

# --- Reset staging root ------------------------------------------------------
if (Test-Path -LiteralPath $StageRoot) {
    Write-Step "clearing previous stage: $StageRoot"
    Remove-Item -LiteralPath $StageRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $StageRoot -Force | Out-Null

# --- Stage project files -----------------------------------------------------
$stagedCount = 0
foreach ($set in $PayloadSets) {
    $sourceDir = Join-Path $RepoRoot $set.Source
    if (-not (Test-Path -LiteralPath $sourceDir)) { throw "PAYLOAD_SOURCE_MISSING: $($set.Source)" }
    $items = @(Get-ChildItem -LiteralPath $sourceDir -File -Filter $set.Include -Recurse:$set.Recurse -Force)
    foreach ($item in $items) {
        $relativeInSet = $item.FullName.Substring($sourceDir.Length).TrimStart('\')
        $relativeInStage = Join-Path $set.Dest $relativeInSet
        if (Test-Denied $relativeInStage) { continue }
        Copy-PayloadFile -From $item.FullName -To (Join-Path $StageRoot $relativeInStage)
        $stagedCount++
    }
}

foreach ($single in $SingleFiles) {
    $from = Join-Path $RepoRoot $single.Source
    if (-not (Test-Path -LiteralPath $from)) {
        if ($single.Required) { throw "PAYLOAD_SOURCE_MISSING: $($single.Source)" }
        Write-Step "optional file absent, skipped: $($single.Source)"
        continue
    }
    Copy-PayloadFile -From $from -To (Join-Path $StageRoot $single.Dest)
    $stagedCount++
}
Write-Step "project files staged: $stagedCount"

# --- Stage the runtime -------------------------------------------------------
if (-not (Test-Path -LiteralPath (Join-Path $RuntimeSource 'python.exe'))) {
    throw "RUNTIME_SOURCE_INVALID: $RuntimeSource"
}
$runtimeDest = Join-Path $StageRoot 'runtime'
Write-Step "copying runtime from $RuntimeSource"
$robocopyOutput = & robocopy.exe $RuntimeSource $runtimeDest '/E' '/NFL' '/NDL' '/NJH' '/NJS' '/NP' '/R:2' '/W:1' '/XD' '__pycache__' '.git' 2>&1
$robocopyExit = $LASTEXITCODE
$global:LASTEXITCODE = 0
if ($robocopyExit -ge 8) {
    Write-Host ($robocopyOutput | Out-String)
    throw "RUNTIME_COPY_FAILED: robocopy exit $robocopyExit"
}

Get-ChildItem -LiteralPath $runtimeDest -Directory -Filter '__pycache__' -Recurse -Force -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

if (-not (Test-Path -LiteralPath (Join-Path $runtimeDest 'pythonw.exe'))) { throw 'RUNTIME_MISSING_PYTHONW' }

# --- Required-file check (mirrors the launcher's presence check) --------------
$RequiredInStage = @(
    'launcher.pyw', 'stop.pyw', 'healthcheck.py',
    'runtime\python.exe', 'runtime\pythonw.exe',
    'app\ThermoGar_app.py'
)
foreach ($required in $RequiredInStage) {
    if (-not (Test-Path -LiteralPath (Join-Path $StageRoot $required))) {
        throw "STAGE_REQUIRED_MISSING: $required"
    }
}
if (-not @(Get-ChildItem -LiteralPath (Join-Path $StageRoot 'databases\converted') -File -Recurse -Filter '*.tdb' -ErrorAction SilentlyContinue)) {
    throw 'STAGE_REQUIRED_MISSING: databases\converted\*.tdb'
}

# --- Payload manifest --------------------------------------------------------
Write-Step 'hashing staged files'
$manifestDir = Join-Path $StageRoot 'manifests'
New-Item -ItemType Directory -Path $manifestDir -Force | Out-Null

$rows = New-Object System.Collections.Generic.List[object]
$totalBytes = 0L
$sha = [Security.Cryptography.SHA256]::Create()
try {
    $files = Get-ChildItem -LiteralPath $StageRoot -File -Recurse -Force |
        Where-Object { -not $_.FullName.StartsWith($manifestDir, [StringComparison]::OrdinalIgnoreCase) } |
        Sort-Object -Property FullName
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($StageRoot.Length + 1).Replace('\', '/')
        $stream = [IO.File]::OpenRead($file.FullName)
        try { $hash = -join ($sha.ComputeHash($stream) | ForEach-Object { $_.ToString('x2') }) }
        finally { $stream.Dispose() }
        $rows.Add([ordered]@{ path = $relative; bytes = $file.Length; sha256 = $hash })
        $totalBytes += $file.Length
    }
}
finally { $sha.Dispose() }

$manifest = [ordered]@{
    schema        = 1
    algorithm     = 'SHA-256'
    generated_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    file_count    = $rows.Count
    total_bytes   = $totalBytes
    files         = $rows
}
$manifestPath = Join-Path $manifestDir 'payload-manifest.json'
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))

Write-Step ("staged {0} files, {1:N1} MB" -f $rows.Count, ($totalBytes / 1MB))

[pscustomobject]@{
    StageRoot    = $StageRoot
    FileCount    = $rows.Count
    TotalBytes   = $totalBytes
    ManifestPath = $manifestPath
}
