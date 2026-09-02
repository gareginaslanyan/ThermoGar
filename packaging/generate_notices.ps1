#requires -Version 5.1
<#
.SYNOPSIS
  Writes THIRD_PARTY_NOTICES.txt from the bundled runtime's dist-info metadata.

.DESCRIPTION
  Walks runtime\Lib\site-packages\*.dist-info, reads Name/Version/License from
  METADATA and appends the licence text found in LICENSE* files, then adds a
  hand-written section for the MatCalc open thermodynamic databases shipped
  under databases\.

  build_installer.ps1 calls this so the notices file cannot drift out of the
  payload; it can also be run on its own after a runtime change.
#>
[CmdletBinding()]
param(
    [string]$RepoRoot,
    [string]$RuntimeSource,
    [string]$OutputPath,
    [switch]$Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent $PSScriptRoot }
$RepoRoot = [IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')

if (-not $RuntimeSource) {
    $candidates = @(
        (Join-Path $RepoRoot 'ThermoGar-Installer-Assets\runtime-clean-3119'),
        'C:\Users\gareg\Desktop\ThermoGar\ThermoGar-Installer-Assets\runtime-clean-3119'
    )
    $RuntimeSource = $candidates | Where-Object { Test-Path -LiteralPath (Join-Path $_ 'python.exe') } | Select-Object -First 1
    if (-not $RuntimeSource) { throw "RUNTIME_SOURCE_NOT_FOUND: tried $($candidates -join '; ')" }
}
if (-not $OutputPath) { $OutputPath = Join-Path $RepoRoot 'THIRD_PARTY_NOTICES.txt' }

$sitePackages = Join-Path $RuntimeSource 'Lib\site-packages'
if (-not (Test-Path -LiteralPath $sitePackages)) { throw "SITE_PACKAGES_MISSING: $sitePackages" }

function Get-MetadataField {
    param([string[]]$Lines, [string]$Field)
    foreach ($line in $Lines) {
        if ($line -match "^$Field\s*:\s*(.+)$") { return $Matches[1].Trim() }
        if ($line -eq '') { break }   # headers end at the first blank line
    }
    return ''
}

$builder = New-Object System.Text.StringBuilder
$null = $builder.AppendLine('THIRD-PARTY NOTICES FOR THERMOGAR')
$null = $builder.AppendLine('=================================')
$null = $builder.AppendLine()
$null = $builder.AppendLine('ThermoGar ships a CPython 3.11.9 runtime together with the third-party')
$null = $builder.AppendLine('packages listed below. Each package remains under its own licence; the')
$null = $builder.AppendLine('licence text is reproduced where the package supplies one.')
$null = $builder.AppendLine()
$null = $builder.AppendLine("Generated: $((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd'))")
$null = $builder.AppendLine()

$distInfos = @(Get-ChildItem -LiteralPath $sitePackages -Directory -Filter '*.dist-info' | Sort-Object Name)
if (-not $Quiet) { Write-Host "  reading $($distInfos.Count) dist-info directories" }

$packageCount = 0
foreach ($distInfo in $distInfos) {
    $metadataPath = Join-Path $distInfo.FullName 'METADATA'
    if (-not (Test-Path -LiteralPath $metadataPath)) { continue }
    $lines = @(Get-Content -LiteralPath $metadataPath -Encoding UTF8 -ErrorAction SilentlyContinue)
    if (-not $lines) { continue }

    $name = Get-MetadataField -Lines $lines -Field 'Name'
    $version = Get-MetadataField -Lines $lines -Field 'Version'
    $license = Get-MetadataField -Lines $lines -Field 'License'
    if (-not $license) {
        $classifier = $lines | Where-Object { $_ -match '^Classifier:\s*License ::' } | Select-Object -First 1
        if ($classifier) { $license = ($classifier -replace '^Classifier:\s*License ::\s*', '').Trim() }
    }
    if (-not $name) { $name = $distInfo.Name }
    if (-not $license) { $license = 'see licence text below or the package homepage' }

    $null = $builder.AppendLine(('-' * 72))
    $null = $builder.AppendLine("$name $version")
    $null = $builder.AppendLine("License: $license")
    $null = $builder.AppendLine()

    $licenseFiles = @(Get-ChildItem -LiteralPath $distInfo.FullName -File -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^(LICEN[CS]E|COPYING|NOTICE)' } | Sort-Object FullName)
    foreach ($licenseFile in $licenseFiles) {
        $text = Get-Content -LiteralPath $licenseFile.FullName -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
        if (-not $text) { continue }
        $null = $builder.AppendLine("  [$($licenseFile.Name)]")
        $null = $builder.AppendLine($text.TrimEnd())
        $null = $builder.AppendLine()
    }
    $packageCount++
}

$null = $builder.AppendLine(('=' * 72))
$null = $builder.AppendLine('THERMODYNAMIC DATABASES')
$null = $builder.AppendLine(('=' * 72))
$null = $builder.AppendLine()
$null = $builder.AppendLine('ThermoGar bundles converted copies of the MatCalc open thermodynamic and')
$null = $builder.AppendLine('mobility databases:')
$null = $builder.AppendLine()
$null = $builder.AppendLine('  mc_ni  (nickel alloys)     databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb')
$null = $builder.AppendLine('  mc_al  (aluminium alloys)  databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb')
$null = $builder.AppendLine('  mc_fe  (steels)            databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb')
$null = $builder.AppendLine()
$null = $builder.AppendLine('These are the freely distributed MatCalc "open databases" published by the')
$null = $builder.AppendLine('MatCalc development team (Institute of Materials Science and Technology,')
$null = $builder.AppendLine('TU Wien) for non-commercial research and teaching use. The files shipped')
$null = $builder.AppendLine('here are format conversions of the upstream TDB releases: parameter values')
$null = $builder.AppendLine('are unchanged, only the file syntax was normalised for pycalphad. The')
$null = $builder.AppendLine('licence and attribution headers of the upstream releases are preserved')
$null = $builder.AppendLine('verbatim inside each converted .tdb file - those headers are the')
$null = $builder.AppendLine('authoritative terms. Consult the MatCalc project about commercial use.')
$null = $builder.AppendLine()
$null = $builder.AppendLine('The physical-property database (databases/physical/original/physical_data_v103.pdb)')
$null = $builder.AppendLine('is compiled from published elemental property data; see PHYSICAL_DATA_README.md')
$null = $builder.AppendLine('and SOURCES.txt for the reference list.')
$null = $builder.AppendLine()

[IO.File]::WriteAllText($OutputPath, $builder.ToString(), [Text.UTF8Encoding]::new($false))
if (-not $Quiet) {
    Write-Host ("  wrote {0} ({1} packages, {2:N0} bytes)" -f $OutputPath, $packageCount, (Get-Item -LiteralPath $OutputPath).Length)
}

[pscustomobject]@{ OutputPath = $OutputPath; PackageCount = $packageCount }
