#requires -Version 5.1
<#
.SYNOPSIS
  Builds dist\ThermoGar-<version>-win64.exe in one command.

.DESCRIPTION
  Pipeline: stage payload -> payload manifest -> makensis -> SHA-256 -> dist\.

  The Codex trust-manifest, SBOM and evidence-bundle gates are gone; their
  scripts still exist under _archive_codex\packaging\ but nothing calls them.

.EXAMPLE
  .\packaging\build_installer.ps1
  .\packaging\build_installer.ps1 -Version 0.3.1 -KeepStage
#>
[CmdletBinding()]
param(
    # Defaults to display_version from product-version.json.
    [string]$Version,
    # makensis.exe; falls back to the standard install, then to a portable
    # NSIS unpacked under ThermoGar-Installer-Assets\nsis\.
    [string]$NsisPath,
    [string]$RepoRoot,
    [string]$RuntimeSource,
    [string]$OutputDir,
    # Leave dist\stage in place for inspection.
    [switch]$KeepStage
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$started = Get-Date

if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
$RepoRoot = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
if (-not $OutputDir) { $OutputDir = Join-Path $RepoRoot 'dist' }
$OutputDir = [IO.Path]::GetFullPath($OutputDir).TrimEnd('\')

function Resolve-Nsis {
    param([string]$Explicit)
    $candidates = @()
    if ($Explicit) { $candidates += $Explicit }
    $candidates += 'C:\Program Files (x86)\NSIS\makensis.exe'
    $candidates += 'C:\Program Files\NSIS\makensis.exe'
    $candidates += (Join-Path $RepoRoot 'ThermoGar-Installer-Assets\nsis\makensis.exe')
    $candidates += 'C:\Users\gareg\Desktop\ThermoGar\ThermoGar-Installer-Assets\nsis\makensis.exe'
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { return $candidate }
    }
    throw "NSIS_NOT_FOUND: tried $($candidates -join '; ')"
}

# --- Product metadata --------------------------------------------------------
$versionFile = Join-Path $PSScriptRoot 'product-version.json'
if (-not (Test-Path -LiteralPath $versionFile)) { throw "PRODUCT_VERSION_MISSING: $versionFile" }
$product = Get-Content -LiteralPath $versionFile -Raw -Encoding UTF8 | ConvertFrom-Json

if (-not $Version) { $Version = [string]$product.display_version }
if ($Version -notmatch '^[0-9A-Za-z.\-]{1,32}$') { throw "VERSION_INVALID: $Version" }

$viVersion = [string]$product.vi_product_version
if ($Version -ne [string]$product.display_version) {
    # Keep the binary version field consistent with an overridden -Version.
    $numeric = ($Version -split '[^0-9.]')[0].Trim('.')
    $parts = @($numeric -split '\.') + @('0', '0', '0', '0')
    $viVersion = ($parts[0..3] -join '.')
}
if ($viVersion -notmatch '^\d+\.\d+\.\d+\.\d+$') { throw "VI_VERSION_INVALID: $viVersion" }

$iconPath = Join-Path $PSScriptRoot 'assets\ThermoGar.ico'
if (-not (Test-Path -LiteralPath $iconPath)) { throw "ICON_MISSING: $iconPath" }

$nsis = Resolve-Nsis -Explicit $NsisPath
$nsiScript = Join-Path $PSScriptRoot 'ThermoGar.nsi'
if (-not (Test-Path -LiteralPath $nsiScript)) { throw "NSI_MISSING: $nsiScript" }

Write-Host "ThermoGar installer build"
Write-Host "  version : $Version ($viVersion)"
Write-Host "  repo    : $RepoRoot"
Write-Host "  makensis: $nsis"

# --- 1. Third-party notices --------------------------------------------------
$noticesScript = Join-Path $PSScriptRoot 'generate_notices.ps1'
if (Test-Path -LiteralPath $noticesScript) {
    Write-Host 'step 1/5: third-party notices'
    & $noticesScript -RepoRoot $RepoRoot -RuntimeSource $RuntimeSource -Quiet | Out-Null
}

# --- 2. Stage the payload ----------------------------------------------------
Write-Host 'step 2/5: staging payload'
$stageRoot = Join-Path $OutputDir 'stage'
$stageArguments = @{ RepoRoot = $RepoRoot; StageRoot = $stageRoot }
if ($RuntimeSource) { $stageArguments['RuntimeSource'] = $RuntimeSource }
$stage = & (Join-Path $PSScriptRoot 'stage_payload.ps1') @stageArguments
if (-not $stage -or -not $stage.FileCount) { throw 'STAGE_FAILED' }

# --- 3. Compile with makensis ------------------------------------------------
Write-Host 'step 3/5: makensis'
if (-not (Test-Path -LiteralPath $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null }
$outputName = "ThermoGar-$Version-win64.exe"
$outputPath = Join-Path $OutputDir $outputName
if (Test-Path -LiteralPath $outputPath) { Remove-Item -LiteralPath $outputPath -Force }

$logPath = Join-Path $OutputDir 'makensis.log'
$nsisArguments = @(
    '/V3',
    "/DPRODUCT_DISPLAY_NAME=$($product.display_name)",
    "/DPRODUCT_DISPLAY_VERSION=$Version",
    "/DPRODUCT_VI_VERSION=$viVersion",
    "/DPRODUCT_PUBLISHER=$($product.publisher)",
    "/DPRODUCT_DESCRIPTION=$($product.description)",
    "/DPRODUCT_ICON=$iconPath",
    "/DPAYLOAD_DIR=$stageRoot",
    "/DOUTPUT_FILE=$outputPath",
    $nsiScript
)
& $nsis @nsisArguments 2>&1 | Tee-Object -FilePath $logPath
$nsisExit = $LASTEXITCODE
$global:LASTEXITCODE = 0
if ($nsisExit -ne 0) { throw "MAKENSIS_FAILED: exit $nsisExit (see $logPath)" }
if (-not (Test-Path -LiteralPath $outputPath)) { throw "MAKENSIS_NO_OUTPUT: $outputPath" }

# --- 4. Hash the installer ---------------------------------------------------
Write-Host 'step 4/5: hashing installer'
$exeItem = Get-Item -LiteralPath $outputPath
$exeHash = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash

# --- 5. Build summary --------------------------------------------------------
Write-Host 'step 5/5: writing build summary'
$elapsed = (Get-Date) - $started
$summary = [ordered]@{
    schema             = 1
    product            = [string]$product.display_name
    version            = $Version
    vi_product_version = $viVersion
    built_utc          = $started.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    build_seconds      = [math]::Round($elapsed.TotalSeconds, 1)
    nsis               = $nsis
    payload_files      = $stage.FileCount
    payload_bytes      = $stage.TotalBytes
    installer          = $outputName
    installer_bytes    = $exeItem.Length
    installer_sha256   = $exeHash
}
$summaryPath = Join-Path $OutputDir ("ThermoGar-$Version-win64.build.json")
[IO.File]::WriteAllText($summaryPath, ($summary | ConvertTo-Json -Depth 4), [Text.UTF8Encoding]::new($false))

if (-not $KeepStage) {
    Remove-Item -LiteralPath $stageRoot -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host "BUILD OK  $outputPath"
Write-Host ("  payload  : {0} files, {1:N1} MB" -f $stage.FileCount, ($stage.TotalBytes / 1MB))
Write-Host ("  installer: {0:N1} MB" -f ($exeItem.Length / 1MB))
Write-Host "  sha256   : $exeHash"
Write-Host ("  elapsed  : {0:N1} s" -f $elapsed.TotalSeconds)

[pscustomobject]$summary
