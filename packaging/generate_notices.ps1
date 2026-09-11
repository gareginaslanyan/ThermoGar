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
$null = $builder.AppendLine('ThermoGar ships derived copies of the MatCalc open thermodynamic and')
$null = $builder.AppendLine('mobility databases. Upstream author and copyright holder: Erwin')
$null = $builder.AppendLine('Povoden-Karadeniz, Institute of Materials Science and Technology, TU Wien;')
$null = $builder.AppendLine('the steel database is co-authored with Aurelie Jacob.')
$null = $builder.AppendLine()
$null = $builder.AppendLine('Each shipped *_with_mobility.*.tdb is a Derivative Database in the sense of')
$null = $builder.AppendLine('ODbL-1.0. It was produced by converting the upstream TDB to pycalphad syntax')
$null = $builder.AppendLine('and merging the compatible mobility parameters of the matching DDB into it.')
$null = $builder.AppendLine('The derived files are distributed under ODbL-1.0, with the contents under')
$null = $builder.AppendLine('DbCL-1.0, exactly as their sources. No parameter value was substituted.')
$null = $builder.AppendLine()
$null = $builder.AppendLine('  mc_ni  (nickel alloys)     databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb')
$null = $builder.AppendLine('           from mc_ni_v2036.tdb + mc_ni_v2012.ddb')
$null = $builder.AppendLine('  mc_al  (aluminium alloys)  databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb')
$null = $builder.AppendLine('           from mc_al_v2037.tdb + mc_al_v2008.ddb')
$null = $builder.AppendLine('  mc_fe  (steels)            databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb')
$null = $builder.AppendLine('           from mc_fe_v2062.tdb + mc_fe_v2016.ddb, plus compatibility patch')
$null = $builder.AppendLine('           TG-FE-2062-C15-001 (one single G parameter of C15_LAVES disabled,')
$null = $builder.AppendLine('           the original command kept verbatim as a comment)')
$null = $builder.AppendLine()
$null = $builder.AppendLine('The licence and attribution headers of both the upstream TDB and the upstream')
$null = $builder.AppendLine('DDB are preserved verbatim inside each derived .tdb file - those headers are')
$null = $builder.AppendLine('the authoritative terms. File names, SHA-256 sums and the exact provenance of')
$null = $builder.AppendLine('every source are listed in SOURCES.txt; the full licence texts are shipped in')
$null = $builder.AppendLine('licenses/ODbL-1.0.txt and licenses/DbCL-1.0.txt.')
$null = $builder.AppendLine()
$null = $builder.AppendLine('Note on commercial use. Two statements stand side by side here, and both')
$null = $builder.AppendLine('are kept. The database headers state ODbL-1.0 and DbCL-1.0, under which')
$null = $builder.AppendLine('commercial use is allowed. The description of this distribution calls the')
$null = $builder.AppendLine('databases freely distributed for non-commercial research and teaching use.')
$null = $builder.AppendLine('The two do not agree. ThermoGar does not resolve the difference by its own')
$null = $builder.AppendLine('reading of the licence and removes neither wording: consult the MatCalc')
$null = $builder.AppendLine('project about commercial use. See docs/DATABASES.md, section 1.1.')
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
