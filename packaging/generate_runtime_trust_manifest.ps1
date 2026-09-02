$InvocationArguments = [object[]]@($args)
$WrapperCommandPath = $PSCommandPath

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$InformationPreference = 'SilentlyContinue'
$VerbosePreference = 'SilentlyContinue'
$DebugPreference = 'SilentlyContinue'

$script:RTInvariant = [Globalization.CultureInfo]::InvariantCulture
$script:RTStrictUtf8 = [Text.UTF8Encoding]::new($false, $true)
$script:RTP0Root = '42455F51E284BAD35F5BFD4971F5099889A2A0D4518FFB95310FC5C400461F7F'
$script:RTRuntimeFileCount = [int64]15003
$script:RTRuntimeTotalBytes = [int64]575844438
$script:RTRuntimeRoot = '58F81C014DF3C3E8AA6F85517BCEE4263C0AE751365B53CA0ED197964538121C'
$script:RTNativeRoot = 'A08EC90744637E0CFE3F7E72D8F4564F58D37C190704B660F4267AF02616604C'
$script:RTStageContentRoot = '06E8916AEE3BA5EBEF6CF9EBDB4B2B203B90C7A8A01B09645861B071FAD7DD57'
$script:RTP1AStageReceiptSha = '255FD7DB4613E646E158713639EA83353D81F2283CD3E775093DB6189997209B'
$script:RTNoticeRoot = 'DAFF95A316054B509313B3F2BF296C38F00FC7EDAD1CC1C4D27DB0C4FD9B9266'
$script:RTMetadataPins = [ordered]@{
    'manifests/project-source-manifest.json' = @([int64]4226, '7A633DEDD035BF992B1A88381123799AD0CCC991996A8AF43724620108D27874')
    'manifests/runtime-input-manifest.json' = @([int64]2453896, '76A87C3770F250A9044F3660218BE905EC27FD427C5861A0C5D58AC75B4D2761')
    'manifests/native-closure-receipt.json' = @([int64]774156, '1E1D080B48D1A280006025AC9CF64AD1BB536C54329FEFB56175940190324552')
    'manifests/p1a-stage-receipt.json' = @([int64]1315, $script:RTP1AStageReceiptSha)
}
$script:RTScriptPins = [ordered]@{
    'stage_payload.ps1' = @([int64]42249, '61DE75ECC631442788CBBBABF4D91BA401B01791741D3ECB4F5620CB21AC5D3E')
    'verify_stage.ps1' = @([int64]69784, '87BC14D8EC220FA9ED99593C7C4D0D601F0658BAA1A6A815AA6AD77CBC6B09EE')
    'verify_native_closure.ps1' = @([int64]51537, '502963F6669E109C51CAD2C1427B4751C049E37E8423CE9C6DE49768059657F1')
}
$script:RTHelperPins = [ordered]@{
    'launcher.pyw' = @([int64]65359, 'B45DAD87139667604E3C3F4AD8F0D2307E2B0D2C86D220736286498F3389FE0A')
    'stop.pyw' = @([int64]7430, 'AA2087AFF494FF007E4C12CFE0949BB62384A2251883D51765EA3D424D70A286')
    'healthcheck.py' = @([int64]38059, 'ABCDE7BDEFC84DE9E91CA62D6A64F07129B1796C298C4AD4BB9ECC894B9CDB67')
}
$script:RTTrustManifestRelative = 'manifests/runtime-trust-manifest.json'
$script:RTTrustReceiptRelative = 'manifests/runtime-trust-manifest.receipt.json'

function Stop-RuntimeTrust {
    param([int]$Code, [string]$Message)
    $errorObject = [InvalidOperationException]::new($Message)
    $errorObject.Data['RuntimeTrustExit'] = $Code
    throw $errorObject
}

function Initialize-RuntimeTrustNativeTypes {
    if ($null -ne ('ThermoGar.RuntimeTrustFileInfo' -as [type])) {
        return
    }
    $null = Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;
namespace ThermoGar {
    [StructLayout(LayoutKind.Sequential)]
    public struct RuntimeTrustFileInfo {
        public uint FileAttributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME CreationTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastAccessTime;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWriteTime;
        public uint VolumeSerialNumber;
        public uint FileSizeHigh;
        public uint FileSizeLow;
        public uint NumberOfLinks;
        public uint FileIndexHigh;
        public uint FileIndexLow;
    }
    public static class RuntimeTrustNative {
        [DllImport("kernel32.dll", SetLastError=true)]
        public static extern bool GetFileInformationByHandle(
            SafeFileHandle handle, out RuntimeTrustFileInfo info);
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        public static extern uint GetFinalPathNameByHandle(
            SafeFileHandle handle, StringBuilder path, uint pathLength, uint flags);
    }
}
'@
}

function Assert-RuntimeTrustSha {
    param([string]$Value, [string]$Name, [int]$Code = 3)
    if ($Value -cnotmatch '^[A-F0-9]{64}$') {
        Stop-RuntimeTrust $Code "invalid SHA $Name"
    }
}

function Get-RuntimeTrustHash {
    param([byte[]]$Bytes)
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes))
}

function Test-RuntimeTrustReparse {
    param([IO.FileSystemInfo]$Item)
    return [bool]($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)
}

function Assert-RuntimeTrustPlainDirectoryInfo {
    param([IO.DirectoryInfo]$Item, [string]$Label, [int]$Code = 4)
    $Item.Refresh()
    if (-not $Item.Exists -or (Test-RuntimeTrustReparse $Item)) {
        Stop-RuntimeTrust $Code "$Label is not a plain directory"
    }
}

function Assert-RuntimeTrustPlainFileInfo {
    param([IO.FileInfo]$Item, [string]$Label, [int]$Code = 4)
    $Item.Refresh()
    if (-not $Item.Exists -or (Test-RuntimeTrustReparse $Item)) {
        Stop-RuntimeTrust $Code "$Label is not a plain file"
    }
}

function Get-RuntimeTrustInvocationMap {
    param([object[]]$Tokens, [string[]]$Allowed)
    if ($Tokens.Count -ne ($Allowed.Count * 2)) {
        Stop-RuntimeTrust 2 'wrong argument count'
    }
    $allowedSet = [Collections.Generic.HashSet[string]]::new($Allowed, [StringComparer]::Ordinal)
    $result = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    for ($index = 0; $index -lt $Tokens.Count; $index += 2) {
        $label = [string]$Tokens[$index]
        if (-not $label.StartsWith('-', [StringComparison]::Ordinal) -or $label.Length -lt 2) {
            Stop-RuntimeTrust 2 'positional argument'
        }
        $name = $label.Substring(1)
        if ((-not $allowedSet.Contains($name)) -or (-not $result.TryAdd($name, [string]$Tokens[$index + 1]))) {
            Stop-RuntimeTrust 2 'unknown or duplicate argument'
        }
    }
    return $result
}

function Get-RuntimeTrustCanonicalInt64 {
    param([string]$Value, [string]$Name)
    if ($Value -cnotmatch '^(0|[1-9][0-9]*)$') {
        Stop-RuntimeTrust 2 "invalid integer $Name"
    }
    $parsed = [int64]0
    if (-not [int64]::TryParse($Value, [Globalization.NumberStyles]::None, $script:RTInvariant, [ref]$parsed)) {
        Stop-RuntimeTrust 2 "invalid integer $Name"
    }
    return $parsed
}

function Assert-RuntimeTrustAbsoluteDirectory {
    param([string]$Path, [string]$Label)
    if (
        [string]::IsNullOrWhiteSpace($Path) -or
        $Path.StartsWith('\\', [StringComparison]::Ordinal) -or
        [Management.Automation.WildcardPattern]::ContainsWildcardCharacters($Path) -or
        (-not [IO.Path]::IsPathFullyQualified($Path))
    ) {
        Stop-RuntimeTrust 3 "$Label is not canonical absolute"
    }
    $full = [IO.Path]::GetFullPath($Path)
    if ($full -cne $Path -or $full -ceq [IO.Path]::GetPathRoot($full)) {
        Stop-RuntimeTrust 3 "$Label is not canonical absolute"
    }
    $root = [IO.Path]::GetPathRoot($full)
    $current = [IO.DirectoryInfo]::new($root)
    Assert-RuntimeTrustPlainDirectoryInfo $current "$Label root" 3
    foreach ($segment in $full.Substring($root.Length).Split([IO.Path]::DirectorySeparatorChar)) {
        if ([string]::IsNullOrEmpty($segment)) { continue }
        $matches = @($current.EnumerateFileSystemInfos() | Where-Object {
            $_.Name.Equals($segment, [StringComparison]::OrdinalIgnoreCase)
        })
        if ($matches.Count -ne 1 -or $matches[0].Name -cne $segment -or $matches[0] -isnot [IO.DirectoryInfo]) {
            Stop-RuntimeTrust 3 "$Label path collision"
        }
        $current = [IO.DirectoryInfo]$matches[0]
        Assert-RuntimeTrustPlainDirectoryInfo $current $Label 3
    }
    return $current.FullName
}

function Assert-RuntimeTrustRelativePath {
    param([string]$Path, [int]$Code = 4)
    if (
        [string]::IsNullOrEmpty($Path) -or $Path.Length -gt 1024 -or
        $Path.StartsWith('/') -or $Path.EndsWith('/') -or $Path.Contains('//') -or
        $Path.Contains('\') -or $Path.Contains(':') -or $Path.Contains('|') -or
        $Path -cmatch '[\x00-\x1F\x7F]'
    ) {
        Stop-RuntimeTrust $Code "invalid relative path $Path"
    }
    foreach ($part in $Path.Split('/')) {
        if ($part -ceq '.' -or $part -ceq '..' -or $part.EndsWith('.') -or $part.EndsWith(' ')) {
            Stop-RuntimeTrust $Code "invalid relative path $Path"
        }
    }
}

function Resolve-RuntimeTrustExactFile {
    param([string]$Root, [string]$Relative, [int]$Code = 4)
    Assert-RuntimeTrustRelativePath $Relative $Code
    $current = [IO.DirectoryInfo]::new($Root)
    $parts = $Relative.Split('/')
    for ($index = 0; $index -lt $parts.Count; $index++) {
        $matches = @($current.EnumerateFileSystemInfos() | Where-Object {
            $_.Name.Equals($parts[$index], [StringComparison]::OrdinalIgnoreCase)
        })
        if ($matches.Count -ne 1 -or $matches[0].Name -cne $parts[$index]) {
            Stop-RuntimeTrust $Code "path collision $Relative"
        }
        if ($index -lt $parts.Count - 1) {
            if ($matches[0] -isnot [IO.DirectoryInfo]) {
                Stop-RuntimeTrust $Code "parent type $Relative"
            }
            $current = [IO.DirectoryInfo]$matches[0]
            Assert-RuntimeTrustPlainDirectoryInfo $current $Relative $Code
        } else {
            if ($matches[0] -isnot [IO.FileInfo]) {
                Stop-RuntimeTrust $Code "file type $Relative"
            }
            $file = [IO.FileInfo]$matches[0]
            Assert-RuntimeTrustPlainFileInfo $file $Relative $Code
            return $file.FullName
        }
    }
    Stop-RuntimeTrust $Code "unresolved $Relative"
}

function Get-RuntimeTrustHandleIdentity {
    param([IO.FileStream]$Stream, [int]$Code)
    $info = [ThermoGar.RuntimeTrustFileInfo]::new()
    if (-not [ThermoGar.RuntimeTrustNative]::GetFileInformationByHandle($Stream.SafeFileHandle, [ref]$info)) {
        Stop-RuntimeTrust $Code 'file identity failure'
    }
    return '{0:X8}:{1:X8}{2:X8}' -f $info.VolumeSerialNumber, $info.FileIndexHigh, $info.FileIndexLow
}

function Get-RuntimeTrustFinalPath {
    param([IO.FileStream]$Stream, [int]$Code)
    $buffer = [Text.StringBuilder]::new(32768)
    $length = [ThermoGar.RuntimeTrustNative]::GetFinalPathNameByHandle($Stream.SafeFileHandle, $buffer, [uint32]$buffer.Capacity, [uint32]0)
    if ($length -eq 0 -or $length -ge $buffer.Capacity) {
        Stop-RuntimeTrust $Code 'final path failure'
    }
    $value = $buffer.ToString()
    if ($value.StartsWith('\\?\UNC\', [StringComparison]::OrdinalIgnoreCase)) {
        return '\\' + $value.Substring(8)
    }
    if ($value.StartsWith('\\?\', [StringComparison]::OrdinalIgnoreCase)) {
        return $value.Substring(4)
    }
    return $value
}

function Read-RuntimeTrustStableFile {
    param(
        [string]$Path,
        [string]$Label,
        [int]$Code = 4,
        [int64]$Maximum = [int64]::MaxValue
    )
    $before = [IO.FileInfo]::new($Path)
    Assert-RuntimeTrustPlainFileInfo $before $Label $Code
    if ($before.Length -gt $Maximum) {
        Stop-RuntimeTrust $Code "$Label oversized"
    }
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $identity = Get-RuntimeTrustHandleIdentity $stream $Code
        $finalPath = [IO.Path]::GetFullPath((Get-RuntimeTrustFinalPath $stream $Code))
        $expectedPath = [IO.Path]::GetFullPath($Path)
        if (-not $finalPath.Equals($expectedPath, [StringComparison]::OrdinalIgnoreCase)) {
            Stop-RuntimeTrust $Code "$Label final path mismatch"
        }
        $memory = [IO.MemoryStream]::new()
        try {
            $stream.CopyTo($memory)
            $bytes = $memory.ToArray()
        } finally {
            $memory.Dispose()
        }
        $after = [IO.FileInfo]::new($Path)
        Assert-RuntimeTrustPlainFileInfo $after $Label $Code
        if (
            $before.Length -ne $after.Length -or
            $before.LastWriteTimeUtc.Ticks -ne $after.LastWriteTimeUtc.Ticks -or
            $stream.Length -ne $bytes.LongLength -or
            (Get-RuntimeTrustHandleIdentity $stream $Code) -cne $identity
        ) {
            Stop-RuntimeTrust $Code "unstable $Label"
        }
    } finally {
        $stream.Dispose()
    }
    return [pscustomobject]@{
        Bytes = [int64]$bytes.LongLength
        Sha256 = Get-RuntimeTrustHash $bytes
        Raw = $bytes
        Identity = $identity
        FinalPath = $finalPath
    }
}

function Open-RuntimeTrustHeldFile {
    param(
        [string]$Path,
        [string]$Label,
        [int]$Code = 5,
        [int64]$Maximum = [int64]::MaxValue
    )
    $before = [IO.FileInfo]::new($Path)
    Assert-RuntimeTrustPlainFileInfo $before $Label $Code
    if ($before.Length -gt $Maximum) {
        Stop-RuntimeTrust $Code "$Label oversized"
    }
    $stream = $null
    try {
        $stream = [IO.FileStream]::new($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
        $identity = Get-RuntimeTrustHandleIdentity $stream $Code
        $finalPath = [IO.Path]::GetFullPath((Get-RuntimeTrustFinalPath $stream $Code))
        $expectedPath = [IO.Path]::GetFullPath($Path)
        if (-not $finalPath.Equals($expectedPath, [StringComparison]::OrdinalIgnoreCase)) {
            Stop-RuntimeTrust $Code "$Label final path mismatch"
        }
        $memory = [IO.MemoryStream]::new()
        try {
            $stream.CopyTo($memory)
            $bytes = $memory.ToArray()
        } finally {
            $memory.Dispose()
        }
        $after = [IO.FileInfo]::new($expectedPath)
        Assert-RuntimeTrustPlainFileInfo $after $Label $Code
        if (
            $before.Length -ne $after.Length -or
            $before.LastWriteTimeUtc.Ticks -ne $after.LastWriteTimeUtc.Ticks -or
            $stream.Length -ne $bytes.LongLength -or
            (Get-RuntimeTrustHandleIdentity $stream $Code) -cne $identity
        ) {
            Stop-RuntimeTrust $Code "unstable $Label"
        }
        return [pscustomobject]@{
            Stream = $stream
            Path = $expectedPath
            Bytes = [int64]$bytes.LongLength
            Sha256 = Get-RuntimeTrustHash $bytes
            Identity = $identity
            FinalPath = $finalPath
            LastWriteTicks = $before.LastWriteTimeUtc.Ticks
        }
    } catch {
        if ($null -ne $stream) {$stream.Dispose()}
        throw
    }
}

function Assert-RuntimeTrustHeldFile {
    param([object]$Held, [string]$Label, [int]$Code = 5)
    try {
        if ($null -eq $Held -or $null -eq $Held.Stream -or -not $Held.Stream.CanRead) {
            Stop-RuntimeTrust $Code "$Label handle closed"
        }
        $Held.Stream.Position = 0
        $memory = [IO.MemoryStream]::new()
        try {
            $Held.Stream.CopyTo($memory)
            $bytes = $memory.ToArray()
        } finally {
            $memory.Dispose()
        }
        $identity = Get-RuntimeTrustHandleIdentity $Held.Stream $Code
        $finalPath = [IO.Path]::GetFullPath((Get-RuntimeTrustFinalPath $Held.Stream $Code))
        if (
            $Held.Stream.Length -ne $Held.Bytes -or
            $bytes.LongLength -ne $Held.Bytes -or
            (Get-RuntimeTrustHash $bytes) -cne $Held.Sha256 -or
            $identity -cne $Held.Identity -or
            -not $finalPath.Equals($Held.FinalPath, [StringComparison]::OrdinalIgnoreCase)
        ) {
            Stop-RuntimeTrust $Code "$Label held identity changed"
        }
        $named = Read-RuntimeTrustStableFile $Held.Path $Label $Code $Held.Bytes
        if (
            $named.Bytes -ne $Held.Bytes -or
            $named.Sha256 -cne $Held.Sha256 -or
            $named.Identity -cne $Held.Identity -or
            -not $named.FinalPath.Equals($Held.FinalPath, [StringComparison]::OrdinalIgnoreCase)
        ) {
            Stop-RuntimeTrust $Code "$Label named identity changed"
        }
    } catch {
        if ($null -ne $_.Exception -and $_.Exception.Data.Contains('RuntimeTrustExit')) {
            throw
        }
        Stop-RuntimeTrust $Code "$Label held validation"
    }
}

function Read-RuntimeTrustJsonSnapshot {
    param([string]$Path, [string]$Label, [int64]$Maximum)
    $snapshot = Read-RuntimeTrustStableFile $Path $Label 4 $Maximum
    if (
        ($snapshot.Raw.Length -ge 3 -and $snapshot.Raw[0] -eq 0xEF -and $snapshot.Raw[1] -eq 0xBB -and $snapshot.Raw[2] -eq 0xBF)
    ) {
        Stop-RuntimeTrust 4 "$Label BOM"
    }
    try {
        $text = $script:RTStrictUtf8.GetString($snapshot.Raw)
    } catch {
        Stop-RuntimeTrust 4 "$Label UTF-8"
    }
    if ($text.EndsWith("`r") -or $text.EndsWith("`n")) {
        Stop-RuntimeTrust 4 "$Label newline"
    }
    return [pscustomobject]@{
        Bytes = $snapshot.Bytes
        Sha256 = $snapshot.Sha256
        Raw = $snapshot.Raw
        Text = $text
        Identity = $snapshot.Identity
    }
}

function Open-RuntimeTrustJson {
    param([string]$Text)
    $options = [Text.Json.JsonDocumentOptions]::new()
    $options.AllowTrailingCommas = $false
    $options.CommentHandling = [Text.Json.JsonCommentHandling]::Disallow
    $options.MaxDepth = 64
    try {
        return [Text.Json.JsonDocument]::Parse($Text, $options)
    } catch {
        Stop-RuntimeTrust 4 'malformed JSON'
    }
}

function Get-RuntimeTrustJsonString {
    param([Text.Json.JsonElement]$Object, [string]$Name)
    $value = [Text.Json.JsonElement]::new()
    if (-not $Object.TryGetProperty($Name, [ref]$value) -or $value.ValueKind -ne [Text.Json.JsonValueKind]::String) {
        Stop-RuntimeTrust 4 "JSON string $Name"
    }
    return $value.GetString()
}

function Get-RuntimeTrustJsonInt {
    param([Text.Json.JsonElement]$Object, [string]$Name)
    $value = [Text.Json.JsonElement]::new()
    if (-not $Object.TryGetProperty($Name, [ref]$value) -or $value.ValueKind -ne [Text.Json.JsonValueKind]::Number) {
        Stop-RuntimeTrust 4 "JSON integer $Name"
    }
    $number = [int64]0
    if (
        -not $value.TryGetInt64([ref]$number) -or
        $value.GetRawText() -cne $number.ToString($script:RTInvariant) -or
        $number -lt 0
    ) {
        Stop-RuntimeTrust 4 "JSON integer $Name"
    }
    return $number
}

function Read-RuntimeTrustManifestRows {
    param([object]$Snapshot, [string]$Kind)
    $document = Open-RuntimeTrustJson $Snapshot.Text
    try {
        $root = $document.RootElement
        $rowsElement = [Text.Json.JsonElement]::new()
        if (-not $root.TryGetProperty('rows', [ref]$rowsElement) -or $rowsElement.ValueKind -ne [Text.Json.JsonValueKind]::Array) {
            Stop-RuntimeTrust 4 "$Kind rows"
        }
        $rows = [Collections.Generic.List[object]]::new()
        $exact = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        $fold = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        $previous = $null
        $sum = [int64]0
        foreach ($row in $rowsElement.EnumerateArray()) {
            $path = Get-RuntimeTrustJsonString $row 'path'
            $bytes = Get-RuntimeTrustJsonInt $row 'bytes'
            $sha = Get-RuntimeTrustJsonString $row 'sha256'
            Assert-RuntimeTrustRelativePath $path 4
            Assert-RuntimeTrustSha $sha "$Kind row" 4
            if (
                (-not $exact.Add($path)) -or (-not $fold.Add($path)) -or
                ($null -ne $previous -and [StringComparer]::Ordinal.Compare($previous, $path) -ge 0)
            ) {
                Stop-RuntimeTrust 4 "$Kind row order"
            }
            if ($sum -gt ([int64]::MaxValue - $bytes)) {
                Stop-RuntimeTrust 4 "$Kind total"
            }
            $sum += $bytes
            $rows.Add([pscustomobject]@{Path=$path;Bytes=$bytes;Sha256=$sha})
            $previous = $path
        }
        $declaredCount = Get-RuntimeTrustJsonInt $root 'row_count'
        $declaredTotal = Get-RuntimeTrustJsonInt $root 'total_bytes'
        if ($declaredCount -ne $rows.Count -or $declaredTotal -ne $sum) {
            Stop-RuntimeTrust 4 "$Kind counts"
        }
        $properties = [ordered]@{}
        foreach ($name in @('project_root_sha256','runtime_root_sha256','producer_sha256','dist_info_count','notice_path_count','notice_path_root_sha256')) {
            $value = [Text.Json.JsonElement]::new()
            if ($root.TryGetProperty($name, [ref]$value)) {
                if ($value.ValueKind -eq [Text.Json.JsonValueKind]::String) {
                    $properties[$name] = $value.GetString()
                } elseif ($value.ValueKind -eq [Text.Json.JsonValueKind]::Number) {
                    $properties[$name] = Get-RuntimeTrustJsonInt $root $name
                } else {
                    Stop-RuntimeTrust 4 "$Kind property $name"
                }
            }
        }
        return [pscustomobject]@{
            Rows = $rows.ToArray()
            Count = [int64]$rows.Count
            Total = $sum
            Properties = $properties
        }
    } finally {
        $document.Dispose()
    }
}

function Assert-RuntimeTrustAnchors {
    param([string]$Stage)
    $snapshots = [ordered]@{}
    foreach ($relative in $script:RTMetadataPins.Keys) {
        $pin = $script:RTMetadataPins[$relative]
        $snapshot = Read-RuntimeTrustJsonSnapshot (Resolve-RuntimeTrustExactFile $Stage $relative 4) $relative ([int64]$pin[0])
        if ($snapshot.Bytes -ne [int64]$pin[0] -or $snapshot.Sha256 -cne [string]$pin[1]) {
            Stop-RuntimeTrust 4 "metadata identity $relative"
        }
        $snapshots[$relative] = $snapshot
    }
    foreach ($name in $script:RTScriptPins.Keys) {
        $pin = $script:RTScriptPins[$name]
        $snapshot = Read-RuntimeTrustStableFile ([IO.Path]::Combine($PSScriptRoot, $name)) $name 4 ([int64]$pin[0])
        if ($snapshot.Bytes -ne [int64]$pin[0] -or $snapshot.Sha256 -cne [string]$pin[1]) {
            Stop-RuntimeTrust 4 "script identity $name"
        }
        $snapshots[$name] = $snapshot
    }
    $project = Read-RuntimeTrustManifestRows $snapshots['manifests/project-source-manifest.json'] 'project'
    $runtime = Read-RuntimeTrustManifestRows $snapshots['manifests/runtime-input-manifest.json'] 'runtime'
    if (
        $project.Count -ne 29 -or $project.Total -ne 2674489 -or
        $project.Properties['project_root_sha256'] -cne $script:RTP0Root -or
        $project.Properties['producer_sha256'] -cne [string]$script:RTScriptPins['stage_payload.ps1'][1]
    ) {
        Stop-RuntimeTrust 4 'project manifest cross-binding'
    }
    if (
        $runtime.Count -ne $script:RTRuntimeFileCount -or $runtime.Total -ne $script:RTRuntimeTotalBytes -or
        $runtime.Properties['runtime_root_sha256'] -cne $script:RTRuntimeRoot -or
        $runtime.Properties['producer_sha256'] -cne [string]$script:RTScriptPins['stage_payload.ps1'][1] -or
        [int64]$runtime.Properties['dist_info_count'] -ne 99 -or
        [int64]$runtime.Properties['notice_path_count'] -ne 131 -or
        $runtime.Properties['notice_path_root_sha256'] -cne $script:RTNoticeRoot
    ) {
        Stop-RuntimeTrust 4 'runtime manifest cross-binding'
    }
    $stageDocument = Open-RuntimeTrustJson $snapshots['manifests/p1a-stage-receipt.json'].Text
    try {
        $stageRoot = $stageDocument.RootElement
        if (
            (Get-RuntimeTrustJsonString $stageRoot 'project_manifest_sha256') -cne [string]$script:RTMetadataPins['manifests/project-source-manifest.json'][1] -or
            (Get-RuntimeTrustJsonString $stageRoot 'runtime_manifest_sha256') -cne [string]$script:RTMetadataPins['manifests/runtime-input-manifest.json'][1] -or
            (Get-RuntimeTrustJsonString $stageRoot 'native_receipt_sha256') -cne [string]$script:RTMetadataPins['manifests/native-closure-receipt.json'][1] -or
            (Get-RuntimeTrustJsonString $stageRoot 'project_root_sha256') -cne $script:RTP0Root -or
            (Get-RuntimeTrustJsonString $stageRoot 'runtime_root_sha256') -cne $script:RTRuntimeRoot -or
            (Get-RuntimeTrustJsonString $stageRoot 'native_closure_root_sha256') -cne $script:RTNativeRoot -or
            (Get-RuntimeTrustJsonInt $stageRoot 'native_row_count') -ne 3142 -or
            (Get-RuntimeTrustJsonInt $stageRoot 'native_total_bytes') -ne 3224678344 -or
            (Get-RuntimeTrustJsonInt $stageRoot 'notice_path_count') -ne 131 -or
            (Get-RuntimeTrustJsonString $stageRoot 'notice_path_root_sha256') -cne $script:RTNoticeRoot -or
            (Get-RuntimeTrustJsonString $stageRoot 'stage_content_root_sha256') -cne $script:RTStageContentRoot -or
            (Get-RuntimeTrustJsonInt $stageRoot 'project_row_count') -ne 29 -or
            (Get-RuntimeTrustJsonInt $stageRoot 'project_total_bytes') -ne 2674489 -or
            (Get-RuntimeTrustJsonInt $stageRoot 'runtime_row_count') -ne $script:RTRuntimeFileCount -or
            (Get-RuntimeTrustJsonInt $stageRoot 'runtime_total_bytes') -ne $script:RTRuntimeTotalBytes -or
            (Get-RuntimeTrustJsonInt $stageRoot 'stage_content_row_count') -ne 15032 -or
            (Get-RuntimeTrustJsonInt $stageRoot 'stage_content_total_bytes') -ne 578518927 -or
            (Get-RuntimeTrustJsonString $stageRoot 'stage_payload_sha256') -cne [string]$script:RTScriptPins['stage_payload.ps1'][1] -or
            (Get-RuntimeTrustJsonString $stageRoot 'verify_stage_sha256') -cne [string]$script:RTScriptPins['verify_stage.ps1'][1] -or
            (Get-RuntimeTrustJsonString $stageRoot 'native_script_sha256') -cne [string]$script:RTScriptPins['verify_native_closure.ps1'][1]
        ) {
            Stop-RuntimeTrust 4 'stage receipt cross-binding'
        }
    } finally {
        $stageDocument.Dispose()
    }
    $nativeDocument = Open-RuntimeTrustJson $snapshots['manifests/native-closure-receipt.json'].Text
    try {
        $nativeRoot = $nativeDocument.RootElement
        if (
            (Get-RuntimeTrustJsonString $nativeRoot 'runtime_input_manifest_sha256') -cne [string]$script:RTMetadataPins['manifests/runtime-input-manifest.json'][1] -or
            (Get-RuntimeTrustJsonString $nativeRoot 'native_closure_root_sha256') -cne $script:RTNativeRoot -or
            (Get-RuntimeTrustJsonInt $nativeRoot 'row_count') -ne 3142 -or
            (Get-RuntimeTrustJsonInt $nativeRoot 'total_bytes') -ne 3224678344 -or
            (Get-RuntimeTrustJsonString $nativeRoot 'producer_sha256') -cne [string]$script:RTScriptPins['verify_native_closure.ps1'][1] -or
            (Get-RuntimeTrustJsonString $nativeRoot 'verifier_sha256') -cne [string]$script:RTScriptPins['verify_native_closure.ps1'][1]
        ) {
            Stop-RuntimeTrust 4 'native receipt cross-binding'
        }
    } finally {
        $nativeDocument.Dispose()
    }
    return [pscustomobject]@{Project=$project;Runtime=$runtime;Snapshots=$snapshots}
}

function Get-RuntimeTrustAllEntries {
    param([string]$Root)
    $files = [Collections.Generic.List[string]]::new()
    $directories = [Collections.Generic.List[string]]::new()
    $fold = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $queue = [Collections.Generic.Queue[object]]::new()
    $queue.Enqueue([pscustomobject]@{Directory=[IO.DirectoryInfo]::new($Root);Relative=''})
    while ($queue.Count -gt 0) {
        $node = $queue.Dequeue()
        Assert-RuntimeTrustPlainDirectoryInfo $node.Directory 'stage directory' 6
        foreach ($item in $node.Directory.EnumerateFileSystemInfos()) {
            $relative = if ($node.Relative -ceq '') {$item.Name} else {$node.Relative + '/' + $item.Name}
            Assert-RuntimeTrustRelativePath $relative 6
            if ((Test-RuntimeTrustReparse $item) -or (-not $fold.Add($relative))) {
                Stop-RuntimeTrust 6 'stage reparse or collision'
            }
            if ($item -is [IO.DirectoryInfo]) {
                $directories.Add($relative)
                $queue.Enqueue([pscustomobject]@{Directory=[IO.DirectoryInfo]$item;Relative=$relative})
            } elseif ($item -is [IO.FileInfo]) {
                $files.Add($relative)
            } else {
                Stop-RuntimeTrust 6 'stage nonregular item'
            }
        }
    }
    $fileArray = $files.ToArray()
    $directoryArray = $directories.ToArray()
    [Array]::Sort($fileArray, [StringComparer]::Ordinal)
    [Array]::Sort($directoryArray, [StringComparer]::Ordinal)
    return [pscustomobject]@{Files=$fileArray;Directories=$directoryArray}
}

function Get-RuntimeTrustExpectedDirectories {
    param([string[]]$Paths)
    $set = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($path in $Paths) {
        $slash = $path.LastIndexOf('/')
        while ($slash -gt 0) {
            $parent = $path.Substring(0, $slash)
            $null = $set.Add($parent)
            $slash = $parent.LastIndexOf('/')
        }
    }
    $array = [string[]]@($set)
    [Array]::Sort($array, [StringComparer]::Ordinal)
    return $array
}

function Assert-RuntimeTrustEqualPaths {
    param([string[]]$Actual, [string[]]$Expected, [int]$Code = 6)
    $copy = [string[]]$Expected.Clone()
    [Array]::Sort($copy, [StringComparer]::Ordinal)
    if ($Actual.Count -ne $copy.Count) {
        Stop-RuntimeTrust $Code 'membership count'
    }
    for ($index = 0; $index -lt $copy.Count; $index++) {
        if ($Actual[$index] -cne $copy[$index]) {
            Stop-RuntimeTrust $Code 'membership mismatch'
        }
    }
}

function Get-RuntimeTrustContentRoot {
    param([object[]]$Rows)
    $literals = [Collections.Generic.List[string]]::new()
    foreach ($row in $Rows) {
        $literals.Add($row.Path + '|' + ([int64]$row.Bytes).ToString($script:RTInvariant) + '|' + $row.Sha256)
    }
    return Get-RuntimeTrustHash ($script:RTStrictUtf8.GetBytes(($literals -join "`r`n")))
}

function Get-RuntimeTrustExecutionRows {
    param([string]$Stage, [object]$Anchors)
    if (
        (Get-RuntimeTrustContentRoot $Anchors.Project.Rows) -cne $script:RTP0Root -or
        (Get-RuntimeTrustContentRoot $Anchors.Runtime.Rows) -cne $script:RTRuntimeRoot
    ) {
        Stop-RuntimeTrust 6 'source content root'
    }
    $map = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
    $fold = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($row in @($Anchors.Project.Rows) + @($Anchors.Runtime.Rows)) {
        if (-not $map.TryAdd($row.Path, $row) -or -not $fold.Add($row.Path)) {
            Stop-RuntimeTrust 6 'execution row collision'
        }
    }
    foreach ($name in $script:RTHelperPins.Keys) {
        $pin = $script:RTHelperPins[$name]
        $row = [pscustomobject]@{Path=$name;Bytes=[int64]$pin[0];Sha256=[string]$pin[1]}
        if (-not $map.TryAdd($name, $row) -or -not $fold.Add($name)) {
            Stop-RuntimeTrust 6 'helper row collision'
        }
    }
    $paths = [string[]]@($map.Keys)
    [Array]::Sort($paths, [StringComparer]::Ordinal)
    $rows = [Collections.Generic.List[object]]::new()
    $total = [int64]0
    foreach ($path in $paths) {
        if ($path -in @($script:RTMetadataPins.Keys) -or $path -ceq $script:RTTrustManifestRelative -or $path -ceq $script:RTTrustReceiptRelative) {
            Stop-RuntimeTrust 6 'metadata self inclusion'
        }
        $row = $map[$path]
        $physical = Read-RuntimeTrustStableFile (Resolve-RuntimeTrustExactFile $Stage $path 6) $path 6 ([int64]$row.Bytes)
        if ($physical.Bytes -ne [int64]$row.Bytes -or $physical.Sha256 -cne [string]$row.Sha256) {
            Stop-RuntimeTrust 6 "physical row $path"
        }
        if ($total -gt ([int64]::MaxValue - [int64]$row.Bytes)) {
            Stop-RuntimeTrust 6 'execution total overflow'
        }
        $total += [int64]$row.Bytes
        $rows.Add($row)
    }
    if ($rows.Count -ne 15035 -or $total -ne 578629775) {
        Stop-RuntimeTrust 6 'execution totals'
    }
    return [pscustomobject]@{
        Rows = $rows.ToArray()
        Paths = $paths
        Count = [int64]$rows.Count
        Total = $total
        Root = Get-RuntimeTrustContentRoot ($rows.ToArray())
    }
}

function Quote-RuntimeTrustJson {
    param([string]$Value)
    $builder = [Text.StringBuilder]::new()
    $null = $builder.Append('"')
    foreach ($character in $Value.ToCharArray()) {
        $number = [int][char]$character
        if ($number -eq 8) {
            $null = $builder.Append('\b')
        } elseif ($number -eq 9) {
            $null = $builder.Append('\t')
        } elseif ($number -eq 10) {
            $null = $builder.Append('\n')
        } elseif ($number -eq 12) {
            $null = $builder.Append('\f')
        } elseif ($number -eq 13) {
            $null = $builder.Append('\r')
        } elseif ($number -eq 34) {
            $null = $builder.Append('\"')
        } elseif ($number -eq 92) {
            $null = $builder.Append('\\')
        } elseif ($number -lt 32) {
            $null = $builder.Append('\u' + $number.ToString('X4', $script:RTInvariant))
        } else {
            $null = $builder.Append($character)
        }
    }
    $null = $builder.Append('"')
    return $builder.ToString()
}

function Get-RuntimeTrustManifestText {
    param([object]$Execution)
    $rowTexts = [Collections.Generic.List[string]]::new()
    foreach ($row in $Execution.Rows) {
        $rowTexts.Add(
            '{"path":' + (Quote-RuntimeTrustJson $row.Path) +
            ',"bytes":' + ([int64]$row.Bytes).ToString($script:RTInvariant) +
            ',"sha256":"' + [string]$row.Sha256 + '"}'
        )
    }
    return (
        '{"schema":1,"version":1,"algorithm":"SHA-256","p0_root_sha256":"' + $script:RTP0Root +
        '","runtime_input_root_sha256":"' + $script:RTRuntimeRoot +
        '","native_closure_root_sha256":"' + $script:RTNativeRoot +
        '","rows":[' + ($rowTexts -join ',') +
        '],"execution_root_sha256":"' + $Execution.Root + '"}'
    )
}

function Get-RuntimeTrustReceiptText {
    param([object]$Execution, [string]$ManifestSha256, [string]$ProducerSha256, [string]$VerifierSha256)
    return (
        '{"schema":1,"version":1,"algorithm":"SHA-256","manifest_sha256":"' + $ManifestSha256 +
        '","execution_root_sha256":"' + $Execution.Root +
        '","row_count":' + ([int64]$Execution.Count).ToString($script:RTInvariant) +
        ',"total_bytes":' + ([int64]$Execution.Total).ToString($script:RTInvariant) +
        ',"producer_sha256":"' + $ProducerSha256 +
        '","verifier_sha256":"' + $VerifierSha256 + '"}'
    )
}

function Get-RuntimeTrustExpectedPaths {
    param([object]$Execution, [bool]$Final)
    $paths = [Collections.Generic.List[string]]::new()
    foreach ($path in $Execution.Paths) {$paths.Add($path)}
    foreach ($path in $script:RTMetadataPins.Keys) {$paths.Add($path)}
    if ($Final) {
        $paths.Add($script:RTTrustManifestRelative)
        $paths.Add($script:RTTrustReceiptRelative)
    }
    return $paths.ToArray()
}

function Assert-RuntimeTrustMembership {
    param([string]$Stage, [object]$Execution, [bool]$Final)
    $expected = Get-RuntimeTrustExpectedPaths $Execution $Final
    $entries = Get-RuntimeTrustAllEntries $Stage
    Assert-RuntimeTrustEqualPaths $entries.Files $expected 6
    Assert-RuntimeTrustEqualPaths $entries.Directories (Get-RuntimeTrustExpectedDirectories $expected) 6
    $expectedFiles = if ($Final) {15041} else {15039}
    if ($entries.Files.Count -ne $expectedFiles -or $entries.Directories.Count -ne 1462) {
        Stop-RuntimeTrust 6 'stage membership counts'
    }
}

function Assert-RuntimeTrustDocuments {
    param(
        [string]$Stage,
        [object]$Execution,
        [string]$ProducerSha256,
        [string]$VerifierSha256
    )
    $expectedManifest = Get-RuntimeTrustManifestText $Execution
    $manifestBytes = $script:RTStrictUtf8.GetBytes($expectedManifest)
    $expectedManifestSha = Get-RuntimeTrustHash $manifestBytes
    $manifest = Read-RuntimeTrustJsonSnapshot (Resolve-RuntimeTrustExactFile $Stage $script:RTTrustManifestRelative 6) $script:RTTrustManifestRelative 67108864
    if ($manifest.Text -cne $expectedManifest -or $manifest.Sha256 -cne $expectedManifestSha) {
        Stop-RuntimeTrust 6 'trust manifest mismatch'
    }
    $expectedReceipt = Get-RuntimeTrustReceiptText $Execution $expectedManifestSha $ProducerSha256 $VerifierSha256
    $receipt = Read-RuntimeTrustJsonSnapshot (Resolve-RuntimeTrustExactFile $Stage $script:RTTrustReceiptRelative 6) $script:RTTrustReceiptRelative 65536
    if ($receipt.Text -cne $expectedReceipt) {
        Stop-RuntimeTrust 6 'trust receipt mismatch'
    }
    return [pscustomobject]@{ManifestSha256=$expectedManifestSha;Manifest=$manifest;Receipt=$receipt}
}

function Publish-RuntimeTrustAtomic {
    param([string]$Destination, [byte[]]$Bytes, [string]$Label)
    if ([IO.File]::Exists($Destination) -or [IO.Directory]::Exists($Destination)) {
        Stop-RuntimeTrust 8 "$Label destination collision"
    }
    $temporary = $Destination + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    $stream = $null
    try {
        $stream = [IO.FileStream]::new($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $stream.Write($Bytes, 0, $Bytes.Length)
        $stream.Flush($true)
    } catch {
        Stop-RuntimeTrust 8 "$Label temporary publish"
    } finally {
        if ($null -ne $stream) {$stream.Dispose()}
    }
    $temporarySnapshot = Read-RuntimeTrustStableFile $temporary "$Label temporary" 8 ([int64]$Bytes.LongLength)
    $expectedSha = Get-RuntimeTrustHash $Bytes
    if ($temporarySnapshot.Bytes -ne $Bytes.LongLength -or $temporarySnapshot.Sha256 -cne $expectedSha) {
        Stop-RuntimeTrust 8 "$Label temporary identity"
    }
    try {
        [IO.File]::Move($temporary, $Destination, $false)
    } catch {
        Stop-RuntimeTrust 8 "$Label final publish"
    }
    $published = Read-RuntimeTrustStableFile $Destination $Label 8 ([int64]$Bytes.LongLength)
    if ($published.Bytes -ne $Bytes.LongLength -or $published.Sha256 -cne $expectedSha) {
        Stop-RuntimeTrust 8 "$Label published identity"
    }
}

function Emit-RuntimeTrustFailure {
    param([int]$Code)
    $map = @('','','USAGE','INPUT_INVALID','STAGE_INVALID','POLICY_INVALID','RUNTIME_INVALID','NATIVE_INVALID','IO_CONFLICT','INTERNAL_ERROR')
    if ($Code -lt 2 -or $Code -gt 9) {$Code = 9}
    [Console]::Out.Write(
        '{"schema":1,"status":"' + $map[$Code] + '","detail_code":' + $Code.ToString($script:RTInvariant) + '}'
    )
    exit $Code
}

function Invoke-RuntimeTrustGenerator {
    param(
        [object[]]$InvocationArguments,
        [string]$CommandPath
    )
    $generatorBefore = $null
    $verifierBefore = $null
    try {
        $allowed = @(
            'StageRoot','ExpectedP0Root','ExpectedRuntimeFileCount','ExpectedRuntimeTotalBytes',
            'ExpectedRuntimeRootSha256','ExpectedNativeClosureRootSha256','ExpectedP1AStageReceiptSha256',
            'ExpectedLauncherSha256','ExpectedStopSha256','ExpectedHealthcheckSha256',
            'ExpectedProducerSha256','ExpectedVerifierSha256'
        )
        $parameters = Get-RuntimeTrustInvocationMap $InvocationArguments $allowed
        foreach ($name in $allowed) {
            if ([string]::IsNullOrEmpty($parameters[$name])) {Stop-RuntimeTrust 2 'empty parameter'}
        }
        foreach ($name in @(
            'ExpectedP0Root','ExpectedRuntimeRootSha256','ExpectedNativeClosureRootSha256',
            'ExpectedP1AStageReceiptSha256','ExpectedLauncherSha256','ExpectedStopSha256',
            'ExpectedHealthcheckSha256','ExpectedProducerSha256','ExpectedVerifierSha256'
        )) {
            Assert-RuntimeTrustSha $parameters[$name] $name 2
        }
        if (
            $parameters['ExpectedP0Root'] -cne $script:RTP0Root -or
            (Get-RuntimeTrustCanonicalInt64 $parameters['ExpectedRuntimeFileCount'] 'ExpectedRuntimeFileCount') -ne $script:RTRuntimeFileCount -or
            (Get-RuntimeTrustCanonicalInt64 $parameters['ExpectedRuntimeTotalBytes'] 'ExpectedRuntimeTotalBytes') -ne $script:RTRuntimeTotalBytes -or
            $parameters['ExpectedRuntimeRootSha256'] -cne $script:RTRuntimeRoot -or
            $parameters['ExpectedNativeClosureRootSha256'] -cne $script:RTNativeRoot -or
            $parameters['ExpectedP1AStageReceiptSha256'] -cne $script:RTP1AStageReceiptSha -or
            $parameters['ExpectedLauncherSha256'] -cne [string]$script:RTHelperPins['launcher.pyw'][1] -or
            $parameters['ExpectedStopSha256'] -cne [string]$script:RTHelperPins['stop.pyw'][1] -or
            $parameters['ExpectedHealthcheckSha256'] -cne [string]$script:RTHelperPins['healthcheck.py'][1]
        ) {
            Stop-RuntimeTrust 3 'expected pins'
        }
        Initialize-RuntimeTrustNativeTypes
        $stage = Assert-RuntimeTrustAbsoluteDirectory $parameters['StageRoot'] 'StageRoot'
        $generatorPath = [IO.Path]::Combine($PSScriptRoot, 'generate_runtime_trust_manifest.ps1')
        $verifierPath = [IO.Path]::Combine($PSScriptRoot, 'verify_runtime_trust_manifest.ps1')
        $expectedCommand = $generatorPath
        if ([IO.Path]::GetFullPath($CommandPath) -cne $expectedCommand) {
            Stop-RuntimeTrust 5 'command path identity'
        }
        $generatorBefore = Open-RuntimeTrustHeldFile $generatorPath 'runtime trust producer' 5 1048576
        $verifierBefore = Open-RuntimeTrustHeldFile $verifierPath 'runtime trust verifier' 5 1048576
        if (
            $generatorBefore.Sha256 -cne $parameters['ExpectedProducerSha256'] -or
            $verifierBefore.Sha256 -cne $parameters['ExpectedVerifierSha256']
        ) {
            Stop-RuntimeTrust 5 'runtime trust script identity'
        }
        $anchors = Assert-RuntimeTrustAnchors $stage
        if ($anchors.Snapshots['manifests/p1a-stage-receipt.json'].Sha256 -cne $parameters['ExpectedP1AStageReceiptSha256']) {
            Stop-RuntimeTrust 4 'P1a receipt identity'
        }
        $execution = Get-RuntimeTrustExecutionRows $stage $anchors
        Assert-RuntimeTrustMembership $stage $execution $false
        $manifestDestination = [IO.Path]::Combine($stage, 'manifests', 'runtime-trust-manifest.json')
        $receiptDestination = [IO.Path]::Combine($stage, 'manifests', 'runtime-trust-manifest.receipt.json')
        if (
            [IO.File]::Exists($manifestDestination) -or [IO.Directory]::Exists($manifestDestination) -or
            [IO.File]::Exists($receiptDestination) -or [IO.Directory]::Exists($receiptDestination)
        ) {
            Stop-RuntimeTrust 8 'trust destination collision'
        }
        $manifestText = Get-RuntimeTrustManifestText $execution
        $manifestBytes = $script:RTStrictUtf8.GetBytes($manifestText)
        $manifestSha = Get-RuntimeTrustHash $manifestBytes
        $receiptText = Get-RuntimeTrustReceiptText $execution $manifestSha $parameters['ExpectedProducerSha256'] $parameters['ExpectedVerifierSha256']
        $receiptBytes = $script:RTStrictUtf8.GetBytes($receiptText)
        Publish-RuntimeTrustAtomic $manifestDestination $manifestBytes 'runtime trust manifest'
        Publish-RuntimeTrustAtomic $receiptDestination $receiptBytes 'runtime trust receipt'
        Assert-RuntimeTrustMembership $stage $execution $true
        $executionAfter = Get-RuntimeTrustExecutionRows $stage $anchors
        if (
            $executionAfter.Root -cne $execution.Root -or
            $executionAfter.Count -ne $execution.Count -or
            $executionAfter.Total -ne $execution.Total
        ) {
            Stop-RuntimeTrust 6 'execution changed'
        }
        $documents = Assert-RuntimeTrustDocuments $stage $executionAfter $parameters['ExpectedProducerSha256'] $parameters['ExpectedVerifierSha256']
        $anchorsAfter = Assert-RuntimeTrustAnchors $stage
        foreach ($relative in $script:RTMetadataPins.Keys) {
            if ($anchorsAfter.Snapshots[$relative].Sha256 -cne $anchors.Snapshots[$relative].Sha256) {
                Stop-RuntimeTrust 4 'anchor changed'
            }
        }
        Assert-RuntimeTrustHeldFile $generatorBefore 'runtime trust producer' 5
        Assert-RuntimeTrustHeldFile $verifierBefore 'runtime trust verifier' 5
        $status = 'P1B_RUNTIME_TRUST_GENERATED'
        [Console]::Out.Write(
            '{"schema":1,"status":"' + $status +
            '","execution_root_sha256":"' + $executionAfter.Root +
            '","manifest_sha256":"' + $documents.ManifestSha256 +
            '","row_count":15035}'
        )
        exit 0
    } catch {
        $code = 9
        if ($null -ne $_.Exception -and $_.Exception.Data.Contains('RuntimeTrustExit')) {
            $code = [int]$_.Exception.Data['RuntimeTrustExit']
        }
        Emit-RuntimeTrustFailure $code
    } finally {
        if ($null -ne $verifierBefore -and $null -ne $verifierBefore.Stream) {
            $verifierBefore.Stream.Dispose()
        }
        if ($null -ne $generatorBefore -and $null -ne $generatorBefore.Stream) {
            $generatorBefore.Stream.Dispose()
        }
    }
}

Invoke-RuntimeTrustGenerator -InvocationArguments $InvocationArguments -CommandPath $WrapperCommandPath
