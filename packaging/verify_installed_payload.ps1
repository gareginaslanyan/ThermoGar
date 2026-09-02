#requires -Version 5.1
$RawCliArguments = @($args)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Write-CompactJsonAndExit {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Object, [Parameter(Mandatory = $true)][int]$Code)
    $json = $Object | ConvertTo-Json -Compress -Depth 8
    [Console]::Out.Write($json)
    exit $Code
}

function Stop-Verification {
    param([int]$Code, [string]$Status, [string]$Detail)
    Write-CompactJsonAndExit -Object ([ordered]@{ schema = 1; status = $Status; detail_code = $Detail }) -Code $Code
}

function Get-NormalAbsolutePath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path) -or -not [System.IO.Path]::IsPathRooted($Path)) {
        throw 'PATH_NOT_ABSOLUTE'
    }
    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
    if ($full.IndexOf([char]0) -ge 0) { throw 'PATH_NUL' }
    return $full
}

function Get-Sha256Hex {
    param([byte[]]$Bytes)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try {
        return -join ($algorithm.ComputeHash($Bytes) | ForEach-Object { $_.ToString('X2') })
    } finally {
        $algorithm.Dispose()
    }
}

function Assert-PlainAncestors {
    param([string]$Path, [bool]$RequireLeaf)
    $full = Get-NormalAbsolutePath $Path
    $leaf = if ($RequireLeaf) { $full } else { Split-Path -Parent $full }
    $cursor = $leaf
    while (-not [string]::IsNullOrEmpty($cursor)) {
        if (-not (Test-Path -LiteralPath $cursor)) { throw 'ANCESTOR_MISSING' }
        $item = Get-Item -LiteralPath $cursor -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'REPARSE_POINT' }
        $parent = Split-Path -Parent $cursor
        if ([string]::Equals($parent, $cursor, [System.StringComparison]::OrdinalIgnoreCase)) { break }
        $cursor = $parent
    }
    return $full
}

function Read-StableBytes {
    param([string]$Path, [long]$ExpectedBytes = -1)
    $full = Assert-PlainAncestors -Path $Path -RequireLeaf $true
    $item = Get-Item -LiteralPath $full -Force
    if (-not ($item -is [System.IO.FileInfo]) -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'NOT_PLAIN_FILE'
    }
    $alternateStreams = @(Get-Item -LiteralPath $full -Stream * -ErrorAction Stop | Where-Object { $_.Stream -cne ':$DATA' })
    if ($alternateStreams.Count -ne 0) { throw 'ALTERNATE_DATA_STREAM' }
    if ($ExpectedBytes -ge 0 -and $item.Length -ne $ExpectedBytes) { throw 'BYTE_COUNT_MISMATCH' }
    $first = [System.IO.File]::ReadAllBytes($full)
    $firstHash = Get-Sha256Hex $first
    $second = [System.IO.File]::ReadAllBytes($full)
    $secondHash = Get-Sha256Hex $second
    if ($first.LongLength -ne $second.LongLength -or $firstHash -cne $secondHash) { throw 'UNSTABLE_FILE' }
    return [pscustomobject]@{ Bytes = $first; Length = $first.LongLength; Sha256 = $firstHash }
}

function Convert-ToCanonicalRelativePath {
    param([string]$Root, [string]$Path)
    $prefix = $Root.TrimEnd('\') + '\'
    if (-not $Path.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'PATH_OUTSIDE_ROOT' }
    $relative = $Path.Substring($prefix.Length).Replace('\', '/')
    if ([string]::IsNullOrEmpty($relative) -or $relative.StartsWith('/') -or $relative.EndsWith('/') -or $relative.Contains('//')) {
        throw 'RELATIVE_PATH_GRAMMAR'
    }
    $segments = $relative.Split('/')
    foreach ($segment in $segments) {
        if ($segment -in @('', '.', '..') -or $segment.Contains(':') -or $segment.IndexOfAny([char[]]'<>"|?*') -ge 0) {
            throw 'RELATIVE_PATH_GRAMMAR'
        }
    }
    if ($relative.Normalize([Text.NormalizationForm]::FormC) -cne $relative) { throw 'PATH_NOT_NFC' }
    return $relative
}

function Get-PlainTreeFiles {
    param([string]$Root)
    $stack = [System.Collections.Generic.Stack[string]]::new()
    $stack.Push($Root)
    $rows = [System.Collections.Generic.List[object]]::new()
    while ($stack.Count -gt 0) {
        $directory = $stack.Pop()
        foreach ($entry in [System.IO.Directory]::EnumerateFileSystemEntries($directory)) {
            $attributes = [System.IO.File]::GetAttributes($entry)
            if (($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'TREE_REPARSE_POINT' }
            if (($attributes -band [System.IO.FileAttributes]::Directory) -ne 0) {
                $stack.Push($entry)
            } else {
                $relative = Convert-ToCanonicalRelativePath -Root $Root -Path $entry
                $rows.Add([pscustomobject]@{ Path = $relative; FullPath = $entry })
            }
        }
    }
    return $rows.ToArray()
}

function Get-RootSha256 {
    param([string[]]$Literals)
    $joined = [string]::Join("`r`n", $Literals)
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($joined)
    return Get-Sha256Hex $bytes
}

$InstallRoot = ''
$ExpectedPayloadManifestSha256 = ''
$ExpectedDistributionEvidenceReceiptSha256 = ''
$ExpectedPayloadRowCount = 0
$ExpectedPayloadTotalBytes = 0L
$ExpectedPayloadRootSha256 = ''
$ExpectedProductVersionSha256 = ''
$ExpectedIconSha256 = ''
$AllowInstallerControlFile = $false
$allowedCliNames = @(
    'InstallRoot','ExpectedPayloadManifestSha256','ExpectedDistributionEvidenceReceiptSha256','ExpectedPayloadRowCount',
    'ExpectedPayloadTotalBytes','ExpectedPayloadRootSha256','ExpectedProductVersionSha256','ExpectedIconSha256','AllowInstallerControlFile'
)
$seenCliNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
for ($cliIndex = 0; $cliIndex -lt $RawCliArguments.Count; $cliIndex++) {
    $token = [string]$RawCliArguments[$cliIndex]
    if ($token.Length -lt 2 -or $token[0] -cne '-') { Stop-Verification 2 'USAGE' 'POSITIONAL_ARGUMENT_REJECTED' }
    $name = $token.Substring(1)
    if (-not ($allowedCliNames -ccontains $name)) { Stop-Verification 2 'USAGE' 'UNKNOWN_OR_ABBREVIATED_PARAMETER' }
    if (-not $seenCliNames.Add($name)) { Stop-Verification 2 'USAGE' 'DUPLICATE_PARAMETER' }
    if ($name -ceq 'AllowInstallerControlFile') {
        $AllowInstallerControlFile = $true
        continue
    }
    $cliIndex++
    if ($cliIndex -ge $RawCliArguments.Count) { Stop-Verification 2 'USAGE' ('MISSING_VALUE_' + $name.ToUpperInvariant()) }
    $value = [string]$RawCliArguments[$cliIndex]
    if ($value.StartsWith('-', [System.StringComparison]::Ordinal)) { Stop-Verification 2 'USAGE' ('MISSING_VALUE_' + $name.ToUpperInvariant()) }
    if ($name -ceq 'ExpectedPayloadRowCount') {
        $parsedInt = 0
        if (-not [int]::TryParse($value, [Globalization.NumberStyles]::None, [Globalization.CultureInfo]::InvariantCulture, [ref]$parsedInt) -or
            $parsedInt -lt 1 -or $parsedInt -gt 1000000) { Stop-Verification 2 'USAGE' 'INVALID_EXPECTEDPAYLOADROWCOUNT' }
        $ExpectedPayloadRowCount = $parsedInt
    } elseif ($name -ceq 'ExpectedPayloadTotalBytes') {
        $parsedLong = 0L
        if (-not [long]::TryParse($value, [Globalization.NumberStyles]::None, [Globalization.CultureInfo]::InvariantCulture, [ref]$parsedLong) -or
            $parsedLong -lt 1) { Stop-Verification 2 'USAGE' 'INVALID_EXPECTEDPAYLOADTOTALBYTES' }
        $ExpectedPayloadTotalBytes = $parsedLong
    } else {
        Set-Variable -Name $name -Value $value
    }
}
$requiredCliNames = @(
    'InstallRoot','ExpectedPayloadManifestSha256','ExpectedDistributionEvidenceReceiptSha256','ExpectedPayloadRootSha256',
    'ExpectedProductVersionSha256','ExpectedIconSha256'
)
foreach ($requiredName in $requiredCliNames) {
    if ([string]::IsNullOrWhiteSpace([string](Get-Variable -Name $requiredName -ValueOnly))) {
        Stop-Verification 2 'USAGE' ('MISSING_' + $requiredName.ToUpperInvariant())
    }
}
if ($ExpectedPayloadRowCount -lt 1 -or $ExpectedPayloadTotalBytes -lt 1) { Stop-Verification 2 'USAGE' 'PAYLOAD_PINS_REQUIRED' }
foreach ($hashName in @('ExpectedPayloadManifestSha256','ExpectedDistributionEvidenceReceiptSha256','ExpectedPayloadRootSha256','ExpectedProductVersionSha256','ExpectedIconSha256')) {
    if ([string](Get-Variable -Name $hashName -ValueOnly) -notmatch '^[0-9A-Fa-f]{64}$') {
        Stop-Verification 2 'USAGE' ('INVALID_' + $hashName.ToUpperInvariant())
    }
}

try {
    try {
        $root = Assert-PlainAncestors -Path $InstallRoot -RequireLeaf $true
        $programFiles64 = if (-not [string]::IsNullOrWhiteSpace($env:ProgramW6432)) { $env:ProgramW6432 } else { $env:ProgramFiles }
        $canonical = [System.IO.Path]::GetFullPath((Join-Path $programFiles64 'ThermoGar')).TrimEnd('\')
        $candidate = $canonical + '.new'
        if (-not [string]::Equals($root, $canonical, [System.StringComparison]::OrdinalIgnoreCase) -and
            -not [string]::Equals($root, $candidate, [System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-Verification 3 'INSTALL_ROOT_INVALID' 'ROOT_NOT_CANONICAL'
        }
    } catch {
        Stop-Verification 3 'INSTALL_ROOT_INVALID' 'ROOT_INVALID'
    }

    $manifestPath = Join-Path $root 'manifests\payload-manifest.json'
    $receiptPath = Join-Path $root 'manifests\distribution-evidence-receipt.json'
    try {
        $manifestFile = Read-StableBytes -Path $manifestPath
        if ($manifestFile.Sha256 -cne $ExpectedPayloadManifestSha256.ToUpperInvariant()) { throw 'MANIFEST_SHA' }
        $manifestText = [System.Text.UTF8Encoding]::new($false, $true).GetString($manifestFile.Bytes)
        if ($manifestText.Length -eq 0 -or $manifestText[0] -eq [char]0xFEFF -or $manifestText.EndsWith("`n") -or $manifestText.EndsWith("`r")) { throw 'MANIFEST_ENCODING' }
        $manifest = $manifestText | ConvertFrom-Json
        if ($manifest.schema -ne 1 -or $manifest.version -ne 1 -or $manifest.algorithm -cne 'SHA-256') { throw 'MANIFEST_SCHEMA' }
        if ([int]$manifest.row_count -ne $ExpectedPayloadRowCount -or [long]$manifest.total_bytes -ne $ExpectedPayloadTotalBytes -or
            [string]$manifest.payload_root_sha256 -cne $ExpectedPayloadRootSha256.ToUpperInvariant()) { throw 'MANIFEST_PINS' }
        if ($manifest.rows.Count -ne $ExpectedPayloadRowCount) { throw 'MANIFEST_ROWS' }
    } catch {
        Stop-Verification 4 'PAYLOAD_MANIFEST_INVALID' 'MANIFEST_INVALID'
    }

    $ordinal = [System.StringComparer]::Ordinal
    $ordinalIgnoreCase = [System.StringComparer]::OrdinalIgnoreCase
    $expected = [System.Collections.Generic.Dictionary[string, object]]::new($ordinal)
    $caseMap = [System.Collections.Generic.Dictionary[string, string]]::new($ordinalIgnoreCase)
    $literals = [System.Collections.Generic.List[string]]::new()
    $total = [long]0
    $previous = $null
    try {
        foreach ($row in $manifest.rows) {
            $path = [string]$row.path
            $bytes = [long]$row.bytes
            $sha = ([string]$row.sha256).ToUpperInvariant()
            $segments = $path.Split('/')
            if ($path -notmatch '^[^\\/:*?"<>|]+(?:/[^\\/:*?"<>|]+)*$' -or @($segments | Where-Object { $_ -in @('.', '..') }).Count -ne 0 -or
                $path.Normalize([Text.NormalizationForm]::FormC) -cne $path -or $sha -notmatch '^[0-9A-F]{64}$' -or $bytes -lt 0) { throw 'ROW_GRAMMAR' }
            if ([string]::Equals($path, 'manifests/payload-manifest.json', [System.StringComparison]::OrdinalIgnoreCase) -or
                [string]::Equals($path, 'manifests/distribution-evidence-receipt.json', [System.StringComparison]::OrdinalIgnoreCase) -or
                [string]::Equals($path, 'product-version.json', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'SELF_OR_EXTERNAL_IDENTITY_ROW' }
            if ($null -ne $previous -and $ordinal.Compare($previous, $path) -ge 0) { throw 'ROW_ORDER' }
            if ($expected.ContainsKey($path) -or $caseMap.ContainsKey($path)) { throw 'ROW_DUPLICATE' }
            $expected.Add($path, [pscustomobject]@{ Bytes = $bytes; Sha256 = $sha })
            $caseMap.Add($path, $path)
            $literals.Add("$path|$bytes|$sha")
            $total += $bytes
            $previous = $path
        }
        if ($total -ne $ExpectedPayloadTotalBytes -or (Get-RootSha256 $literals.ToArray()) -cne $ExpectedPayloadRootSha256.ToUpperInvariant()) {
            throw 'ROW_ROOT'
        }
    } catch {
        Stop-Verification 4 'PAYLOAD_MANIFEST_INVALID' 'ROW_SET_INVALID'
    }

    try {
        $receiptFile = Read-StableBytes -Path $receiptPath
        if ($receiptFile.Sha256 -cne $ExpectedDistributionEvidenceReceiptSha256.ToUpperInvariant()) { throw 'RECEIPT_SHA' }
        $receiptText = [System.Text.UTF8Encoding]::new($false, $true).GetString($receiptFile.Bytes)
        if ($receiptText.Length -eq 0 -or $receiptText[0] -eq [char]0xFEFF -or $receiptText.EndsWith("`n") -or $receiptText.EndsWith("`r")) { throw 'RECEIPT_ENCODING' }
        $receipt = $receiptText | ConvertFrom-Json
        if ($receipt.schema -ne 1 -or $receipt.version -ne 1 -or $receipt.algorithm -cne 'SHA-256' -or
            [string]$receipt.payload_manifest_sha256 -cne $ExpectedPayloadManifestSha256.ToUpperInvariant() -or
            [string]$receipt.payload_root_sha256 -cne $ExpectedPayloadRootSha256.ToUpperInvariant() -or
            [int]$receipt.payload_row_count -ne $ExpectedPayloadRowCount -or
            [long]$receipt.payload_total_bytes -ne $ExpectedPayloadTotalBytes -or
            [string]$receipt.product_version_sha256 -cne $ExpectedProductVersionSha256.ToUpperInvariant() -or
            [string]$receipt.icon_sha256 -cne $ExpectedIconSha256.ToUpperInvariant()) { throw 'RECEIPT_PINS' }
    } catch {
        Stop-Verification 6 'DISTRIBUTION_RECEIPT_INVALID' 'RECEIPT_INVALID'
    }

    $actualPaths = [System.Collections.Generic.Dictionary[string, string]]::new($ordinal)
    $actualCaseMap = [System.Collections.Generic.Dictionary[string, string]]::new($ordinalIgnoreCase)
    try {
        foreach ($entry in (Get-PlainTreeFiles -Root $root)) {
            if ($actualCaseMap.ContainsKey($entry.Path)) { throw 'CASE_COLLISION' }
            $actualCaseMap.Add($entry.Path, $entry.Path)
            $actualPaths.Add($entry.Path, $entry.FullPath)
        }
    } catch {
        Stop-Verification 3 'INSTALL_ROOT_INVALID' 'TREE_INVALID'
    }

    $allowedControls = [System.Collections.Generic.HashSet[string]]::new($ordinal)
    [void]$allowedControls.Add('manifests/payload-manifest.json')
    [void]$allowedControls.Add('manifests/distribution-evidence-receipt.json')
    if ($AllowInstallerControlFile) { [void]$allowedControls.Add('uninstall.exe') }

    foreach ($path in $actualPaths.Keys) {
        if (-not $expected.ContainsKey($path) -and -not $allowedControls.Contains($path)) {
            Stop-Verification 8 'UNLISTED_FILE' 'UNLISTED_FILE'
        }
        $segments = $path.Split('/')
        $lowerSegments = @($segments | ForEach-Object { $_.ToLowerInvariant() })
        if ($lowerSegments -contains '__pycache__' -or $path.ToLowerInvariant().EndsWith('.pyc') -or $path.ToLowerInvariant().EndsWith('.pyo') -or
            $lowerSegments -contains 'user_data' -or $lowerSegments -contains 'projects' -or $lowerSegments -contains 'logs' -or
            $lowerSegments -contains 'mplconfig' -or $lowerSegments -contains 'tmp' -or $path -match '(?i)(^|/)run\.(json|lock)$') {
            Stop-Verification 8 'MUTABLE_INSTALL_FILE' 'MUTABLE_PATH'
        }
    }

    foreach ($path in $expected.Keys) {
        if (-not $actualPaths.ContainsKey($path)) { Stop-Verification 5 'PAYLOAD_INVALID' 'PAYLOAD_MEMBER_MISSING' }
        try {
            $row = $expected[$path]
            $file = Read-StableBytes -Path $actualPaths[$path] -ExpectedBytes $row.Bytes
            if ($file.Sha256 -cne $row.Sha256) { throw 'HASH_MISMATCH' }
        } catch {
            Stop-Verification 5 'PAYLOAD_INVALID' 'PAYLOAD_MEMBER_MISMATCH'
        }
    }

    if ($AllowInstallerControlFile) {
        if (-not $actualPaths.ContainsKey('uninstall.exe')) { Stop-Verification 7 'INSTALLER_CONTROL_INVALID' 'UNINSTALLER_MISSING' }
        try {
            $uninstaller = Read-StableBytes -Path $actualPaths['uninstall.exe']
            if ($uninstaller.Length -lt 2 -or $uninstaller.Bytes[0] -ne 0x4D -or $uninstaller.Bytes[1] -ne 0x5A) { throw 'NOT_PE' }
        } catch {
            Stop-Verification 7 'INSTALLER_CONTROL_INVALID' 'UNINSTALLER_INVALID'
        }
    } elseif ($actualPaths.ContainsKey('uninstall.exe')) {
        Stop-Verification 7 'INSTALLER_CONTROL_INVALID' 'UNEXPECTED_UNINSTALLER'
    }

    if ($actualPaths.Count -ne ($expected.Count + $allowedControls.Count)) {
        Stop-Verification 8 'UNLISTED_FILE' 'MEMBERSHIP_COUNT'
    }
    if (-not $expected.ContainsKey('runtime/python.exe') -or -not $expected.ContainsKey('runtime/pythonw.exe') -or
        -not $expected.ContainsKey('launcher.pyw') -or -not $expected.ContainsKey('stop.pyw') -or
        -not $expected.ContainsKey('healthcheck.py') -or -not $expected.ContainsKey('assets/ThermoGar.ico')) {
        Stop-Verification 5 'PAYLOAD_INVALID' 'REQUIRED_MEMBER_MISSING'
    }

    $icon = Read-StableBytes -Path (Join-Path $root 'assets\ThermoGar.ico')
    if ($icon.Sha256 -cne $ExpectedIconSha256.ToUpperInvariant()) {
        Stop-Verification 5 'PAYLOAD_INVALID' 'ICON_MISMATCH'
    }

    Write-CompactJsonAndExit -Object ([ordered]@{
        schema = 1
        status = 'INSTALLED_PAYLOAD_VERIFIED'
        payload_row_count = $ExpectedPayloadRowCount
        payload_root_sha256 = $ExpectedPayloadRootSha256.ToUpperInvariant()
        payload_manifest_sha256 = $ExpectedPayloadManifestSha256.ToUpperInvariant()
        distribution_receipt_sha256 = $ExpectedDistributionEvidenceReceiptSha256.ToUpperInvariant()
    }) -Code 0
} catch {
    Stop-Verification 9 'INTERNAL_ERROR' 'UNEXPECTED_EXCEPTION'
}
