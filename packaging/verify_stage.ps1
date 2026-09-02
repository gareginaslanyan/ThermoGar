$InvocationArguments = [object[]]@($args)
$StageRoot = ''
$ExpectedP0Root = ''
$ExpectedRuntimeFileCount = ''
$ExpectedRuntimeTotalBytes = ''
$ExpectedRuntimeDistInfoCount = ''
$ExpectedRuntimeNoticePathCount = ''
$ExpectedRuntimeNoticePathRoot = ''
$Phase = ''

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$InformationPreference = 'SilentlyContinue'
$VerbosePreference = 'SilentlyContinue'
$DebugPreference = 'SilentlyContinue'

$P0Root = '42455F51E284BAD35F5BFD4971F5099889A2A0D4518FFB95310FC5C400461F7F'
$P0FileCount = [int64]29
$P0TotalBytes = [int64]2674489
$RuntimeFileCount = [int64]15003
$RuntimeTotalBytes = [int64]575844438
$RuntimeDistInfoCount = [int64]99
$RuntimeNoticeCount = [int64]131
$RuntimeNoticeRoot = 'DAFF95A316054B509313B3F2BF296C38F00FC7EDAD1CC1C4D27DB0C4FD9B9266'
$RuntimeContentRootSha256 = '58F81C014DF3C3E8AA6F85517BCEE4263C0AE751365B53CA0ED197964538121C'
$StageContentFileCount = [int64]15032
$StageContentTotalBytes = [int64]578518927
$ProjectManifestPath = 'manifests/project-source-manifest.json'
$RuntimeManifestPath = 'manifests/runtime-input-manifest.json'
$NativeReceiptPath = 'manifests/native-closure-receipt.json'
$StageReceiptPath = 'manifests/p1a-stage-receipt.json'
$StrictUtf8 = [Text.UTF8Encoding]::new($false, $true)
$Invariant = [Globalization.CultureInfo]::InvariantCulture
$SystemImports = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
foreach ($name in @(
    'advapi32.dll','bcrypt.dll','bcryptprimitives.dll','cabinet.dll','cfgmgr32.dll','combase.dll','comctl32.dll','comdlg32.dll',
    'crypt32.dll','dbghelp.dll','dnsapi.dll','dwmapi.dll','gdi32.dll','gdi32full.dll','imm32.dll','iphlpapi.dll','kernel32.dll',
    'kernelbase.dll','mpr.dll','msi.dll','msvcrt.dll','mswsock.dll','ncrypt.dll','netapi32.dll','ntdll.dll','ole32.dll','oleaut32.dll',
    'opengl32.dll','pdh.dll','powrprof.dll','psapi.dll','rasapi32.dll','rpcrt4.dll','schannel.dll','secur32.dll','sechost.dll','setupapi.dll',
    'shell32.dll','shlwapi.dll','ucrtbase.dll','user32.dll','userenv.dll','version.dll','wevtapi.dll','winhttp.dll','wininet.dll',
    'webservices.dll','winmm.dll','winspool.drv','wintrust.dll','ws2_32.dll','wsock32.dll','wtsapi32.dll')) { $null = $SystemImports.Add($name) }

$PinnedOwnerDirectories = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
$PinnedOwnerDirectories.Add('numpy','runtime/Lib/site-packages/numpy.libs')
$PinnedOwnerDirectories.Add('pandas','runtime/Lib/site-packages/pandas.libs')
$PinnedOwnerDirectories.Add('scipy','runtime/Lib/site-packages/scipy.libs')
$PinnedOwnerDirectories.Add('pyarrow','runtime/Lib/site-packages/pyarrow.libs')
$PinnedOwnerDirectories.Add('sklearn','runtime/Lib/site-packages/sklearn/.libs')

$ForeignToolImages = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
foreach ($entry in @(
    [pscustomobject]@{Path='runtime/Lib/site-packages/pip/_vendor/distlib/t32.exe';Machine=[uint16]0x014C;Bytes=[int64]97792;Sha256='6B4195E640A85AC32EB6F9628822A622057DF1E459DF7C17A12F97AEABC9415B'},
    [pscustomobject]@{Path='runtime/Lib/site-packages/pip/_vendor/distlib/t64-arm.exe';Machine=[uint16]0xAA64;Bytes=[int64]182784;Sha256='EBC4C06B7D95E74E315419EE7E88E1D0F71E9E9477538C00A93A9FF8C66A6CFC'},
    [pscustomobject]@{Path='runtime/Lib/site-packages/pip/_vendor/distlib/w32.exe';Machine=[uint16]0x014C;Bytes=[int64]91648;Sha256='47872CC77F8E18CF642F868F23340A468E537E64521D9A3A416C8B84384D064B'},
    [pscustomobject]@{Path='runtime/Lib/site-packages/pip/_vendor/distlib/w64-arm.exe';Machine=[uint16]0xAA64;Bytes=[int64]168448;Sha256='C5DC9884A8F458371550E09BD396E5418BF375820A31B9899F6499BF391C7B2E'},
    [pscustomobject]@{Path='runtime/Lib/site-packages/setuptools/cli-32.exe';Machine=[uint16]0x014C;Bytes=[int64]65536;Sha256='75F12EA2F30D9C0D872DADE345F30F562E6D93847B6A509BA53BEEC6D0B2C346'},
    [pscustomobject]@{Path='runtime/Lib/site-packages/setuptools/cli-arm64.exe';Machine=[uint16]0xAA64;Bytes=[int64]137216;Sha256='A3D6A6C68C2E759F7C36F35687F6B60D163C2E1A0846A4C07A4C4006A96D88C7'},
    [pscustomobject]@{Path='runtime/Lib/site-packages/setuptools/cli.exe';Machine=[uint16]0x014C;Bytes=[int64]65536;Sha256='75F12EA2F30D9C0D872DADE345F30F562E6D93847B6A509BA53BEEC6D0B2C346'},
    [pscustomobject]@{Path='runtime/Lib/site-packages/setuptools/gui-32.exe';Machine=[uint16]0x014C;Bytes=[int64]65536;Sha256='5C1AF46C7300E87A73DACF6CF41CE397E3F05DF6BD9C7E227B4AC59F85769160'},
    [pscustomobject]@{Path='runtime/Lib/site-packages/setuptools/gui-arm64.exe';Machine=[uint16]0xAA64;Bytes=[int64]137728;Sha256='4C416738A0E2FA6AB766CCF1A9B0A80974E733F9615168DD22A069AFA7D5B38D'},
    [pscustomobject]@{Path='runtime/Lib/site-packages/setuptools/gui.exe';Machine=[uint16]0x014C;Bytes=[int64]65536;Sha256='5C1AF46C7300E87A73DACF6CF41CE397E3F05DF6BD9C7E227B4AC59F85769160'}
)) { $ForeignToolImages.Add($entry.Path,$entry) }

if ($null -eq ('ThermoGar.P1AVerifyStageNative' -as [type])) {
    $null = Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
namespace ThermoGar {
    [StructLayout(LayoutKind.Sequential)]
    public struct P1AVerifyStageFileInfo {
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
    public static class P1AVerifyStageNative {
        [DllImport("kernel32.dll", SetLastError=true)]
        public static extern bool GetFileInformationByHandle(
            SafeFileHandle handle, out P1AVerifyStageFileInfo info);
    }
}
'@
}

function Stop-P1A {
    param([int]$Code, [string]$Message)
    $exception = [InvalidOperationException]::new($Message)
    $exception.Data['P1AExit'] = $Code
    throw $exception
}

function Get-ExactInvocationMap {
    param([object[]]$Tokens,[string[]]$AllowedNames)
    if($Tokens.Count-ne($AllowedNames.Count*2)){Stop-P1A 2 'wrong argument count'}
    $allowed=[Collections.Generic.HashSet[string]]::new($AllowedNames,[StringComparer]::Ordinal)
    $values=[Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    for($index=0;$index-lt$Tokens.Count;$index+=2){$label=[string]$Tokens[$index];if(-not$label.StartsWith('-',[StringComparison]::Ordinal)-or$label.Length-lt2){Stop-P1A 2 'positional argument rejected'};$name=$label.Substring(1);if(-not$allowed.Contains($name)-or-not$values.TryAdd($name,[string]$Tokens[$index+1])){Stop-P1A 2 'unknown or duplicate argument'}}
    return $values
}

function Get-CanonicalInt64Argument {
    param([string]$Value, [string]$Name)
    if ([string]::IsNullOrEmpty($Value) -or $Value -cnotmatch '^(0|[1-9][0-9]*)$') { Stop-P1A 2 "invalid numeric argument $Name" }
    $parsed = [int64]0
    if (-not [int64]::TryParse($Value, [Globalization.NumberStyles]::None, $Invariant, [ref]$parsed)) { Stop-P1A 2 "invalid numeric argument $Name" }
    return $parsed
}

function Add-NonNegativeInt64 {
    param([int64]$Current, [int64]$Addend, [int]$Code, [string]$Message)
    if ($Current -lt 0 -or $Addend -lt 0 -or $Current -gt ([int64]::MaxValue - $Addend)) { Stop-P1A $Code $Message }
    return [int64]($Current + $Addend)
}

function Assert-Sha256 {
    param([string]$Value, [string]$Name, [int]$Code = 4)
    if ($Value -cnotmatch '^[A-F0-9]{64}$') { Stop-P1A $Code "invalid SHA-256 $Name" }
}

function Test-Reparse {
    param([IO.FileSystemInfo]$Item)
    return [bool]($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)
}

function Assert-PlainDirectoryInfo {
    param([IO.DirectoryInfo]$Item, [string]$Label, [int]$Code = 4)
    $Item.Refresh()
    if (-not $Item.Exists -or (Test-Reparse $Item)) { Stop-P1A $Code "$Label is not a plain directory" }
}

function Assert-PlainFileInfo {
    param([IO.FileInfo]$Item, [string]$Label, [int]$Code = 4)
    $Item.Refresh()
    if (-not $Item.Exists -or (Test-Reparse $Item)) { Stop-P1A $Code "$Label is not a plain regular file" }
}

function Assert-AbsoluteExistingDirectory {
    param([string]$Path, [string]$Label)
    if ([string]::IsNullOrWhiteSpace($Path) -or $Path.StartsWith('\\', [StringComparison]::Ordinal) -or
        [Management.Automation.WildcardPattern]::ContainsWildcardCharacters($Path) -or -not [IO.Path]::IsPathFullyQualified($Path)) {
        Stop-P1A 3 "$Label is not canonical absolute"
    }
    $full = [IO.Path]::GetFullPath($Path)
    if ($full -cne $Path -or $full -ceq [IO.Path]::GetPathRoot($full)) { Stop-P1A 3 "$Label is not canonical absolute" }
    $root = [IO.Path]::GetPathRoot($full)
    $current = [IO.DirectoryInfo]::new($root); Assert-PlainDirectoryInfo $current "$Label root" 3
    foreach ($segment in $full.Substring($root.Length).Split([IO.Path]::DirectorySeparatorChar)) {
        if ([string]::IsNullOrEmpty($segment)) { Stop-P1A 3 "$Label contains an empty segment" }
        $matches = @($current.EnumerateFileSystemInfos() | Where-Object { $_.Name.Equals($segment, [StringComparison]::OrdinalIgnoreCase) })
        if ($matches.Count -ne 1 -or $matches[0].Name -cne $segment -or $matches[0] -isnot [IO.DirectoryInfo]) {
            Stop-P1A 3 "$Label has missing, case-aliased, or colliding segment"
        }
        $current = [IO.DirectoryInfo]$matches[0]; Assert-PlainDirectoryInfo $current $Label 3
    }
    return $current.FullName
}

function Assert-StageRelativePath {
    param([string]$Path, [int]$Code = 4)
    if ([string]::IsNullOrEmpty($Path) -or $Path -ceq '-' -or $Path.StartsWith('/') -or $Path.EndsWith('/') -or
        $Path.Contains('//') -or $Path.Contains('\') -or $Path.Contains(':') -or $Path.Contains('|') -or
        $Path -cmatch '[\x00-\x1F\x7F]') { Stop-P1A $Code "invalid stage path $Path" }
    foreach ($segment in $Path.Split('/')) {
        if ([string]::IsNullOrEmpty($segment) -or $segment -ceq '.' -or $segment -ceq '..' -or
            $segment.EndsWith('.') -or $segment.EndsWith(' ')) { Stop-P1A $Code "invalid stage path $Path" }
        $stem = $segment.Split('.')[0].ToUpperInvariant()
        if ($stem -cmatch '^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$') { Stop-P1A $Code "device stage path $Path" }
    }
}

function Get-HandleIdentity {
    param([IO.FileStream]$Stream, [int]$Code)
    $info = [ThermoGar.P1AVerifyStageFileInfo]::new()
    if (-not [ThermoGar.P1AVerifyStageNative]::GetFileInformationByHandle($Stream.SafeFileHandle, [ref]$info)) { Stop-P1A $Code 'cannot obtain file identity' }
    return '{0:X8}:{1:X8}{2:X8}' -f $info.VolumeSerialNumber, $info.FileIndexHigh, $info.FileIndexLow
}

function ConvertTo-UpperSha256 {
    param([byte[]]$Bytes)
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes))
}

function Read-StableFile {
    param([string]$Path, [string]$Label, [int]$Code, [int64]$MaximumBytes = [int64]::MaxValue)
    $before = [IO.FileInfo]::new($Path); Assert-PlainFileInfo $before $Label $Code
    if ($before.Length -gt $MaximumBytes) { Stop-P1A $Code "$Label is oversized" }
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $identity = Get-HandleIdentity $stream $Code
        $memory = [IO.MemoryStream]::new()
        try { $stream.CopyTo($memory); $bytes = $memory.ToArray() } finally { $memory.Dispose() }
        $after = [IO.FileInfo]::new($Path); Assert-PlainFileInfo $after $Label $Code
        if ($before.Length -ne $after.Length -or $before.LastWriteTimeUtc.Ticks -ne $after.LastWriteTimeUtc.Ticks -or
            $stream.Length -ne $bytes.Length -or (Get-HandleIdentity $stream $Code) -cne $identity) { Stop-P1A $Code "unstable read $Label" }
    } finally { $stream.Dispose() }
    return [pscustomobject]@{ Bytes = [int64]$bytes.Length; Sha256 = (ConvertTo-UpperSha256 $bytes); Raw = $bytes }
}

function Read-StableJsonText {
    param([string]$Path, [string]$Label, [int64]$MaximumBytes = 67108864)
    $snapshot = Read-StableFile $Path $Label 4 $MaximumBytes
    if ($snapshot.Raw.Length -ge 3 -and $snapshot.Raw[0] -eq 0xEF -and $snapshot.Raw[1] -eq 0xBB -and $snapshot.Raw[2] -eq 0xBF) { Stop-P1A 4 "$Label has a UTF-8 BOM" }
    try { $text = $StrictUtf8.GetString($snapshot.Raw) } catch { Stop-P1A 4 "$Label is not strict UTF-8" }
    if ($text.EndsWith("`r") -or $text.EndsWith("`n")) { Stop-P1A 4 "$Label has a terminal newline" }
    return [pscustomobject]@{ Bytes = $snapshot.Bytes; Sha256 = $snapshot.Sha256; Text = $text; Raw = $snapshot.Raw }
}

function Resolve-ExactStageFile {
    param([string]$Root, [string]$RelativePath)
    Assert-StageRelativePath $RelativePath 4
    $current = [IO.DirectoryInfo]::new($Root)
    $segments = $RelativePath.Split('/')
    for ($index = 0; $index -lt $segments.Count; $index++) {
        $segment = $segments[$index]
        $matches = @($current.EnumerateFileSystemInfos() | Where-Object { $_.Name.Equals($segment, [StringComparison]::OrdinalIgnoreCase) })
        if ($matches.Count -ne 1 -or $matches[0].Name -cne $segment) { Stop-P1A 4 "missing, case-aliased, or colliding stage path $RelativePath" }
        if ($index -lt $segments.Count - 1) {
            if ($matches[0] -isnot [IO.DirectoryInfo]) { Stop-P1A 4 "non-directory stage parent $RelativePath" }
            $current = [IO.DirectoryInfo]$matches[0]; Assert-PlainDirectoryInfo $current $RelativePath 4
        } else {
            if ($matches[0] -isnot [IO.FileInfo]) { Stop-P1A 4 "stage path is not a file $RelativePath" }
            $file = [IO.FileInfo]$matches[0]; Assert-PlainFileInfo $file $RelativePath 4
            $prefix = $Root.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
            if (-not $file.FullName.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { Stop-P1A 4 "stage path escapes root $RelativePath" }
            return $file.FullName
        }
    }
    Stop-P1A 4 "stage resolution failed $RelativePath"
}

function Assert-NoJsonDuplicates {
    param([Text.Json.JsonElement]$Element, [string]$Location)
    if ($Element.ValueKind -eq [Text.Json.JsonValueKind]::Object) {
        $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach ($property in $Element.EnumerateObject()) {
            if (-not $seen.Add($property.Name)) { Stop-P1A 4 "duplicate JSON property $Location.$($property.Name)" }
            Assert-NoJsonDuplicates $property.Value "$Location.$($property.Name)"
        }
    } elseif ($Element.ValueKind -eq [Text.Json.JsonValueKind]::Array) {
        $index = 0; foreach ($child in $Element.EnumerateArray()) { Assert-NoJsonDuplicates $child "$Location[$index]"; $index++ }
    }
}

function Assert-OrderedJsonKeys {
    param([Text.Json.JsonElement]$Element, [string[]]$Expected, [string]$Location)
    if ($Element.ValueKind -ne [Text.Json.JsonValueKind]::Object) { Stop-P1A 4 "$Location is not an object" }
    $actual = [string[]]@($Element.EnumerateObject() | ForEach-Object { $_.Name })
    if ($actual.Count -ne $Expected.Count) { Stop-P1A 4 "$Location key count mismatch" }
    for ($index = 0; $index -lt $Expected.Count; $index++) { if ($actual[$index] -cne $Expected[$index]) { Stop-P1A 4 "$Location key order mismatch" } }
}

function Get-JsonProperty {
    param([Text.Json.JsonElement]$Element, [string]$Name, [string]$Location)
    $property = [Text.Json.JsonElement]::new()
    if (-not $Element.TryGetProperty($Name, [ref]$property)) { Stop-P1A 4 "$Location.$Name is missing" }
    return $property
}

function Get-CanonicalJsonInt64 {
    param([Text.Json.JsonElement]$Element, [string]$Name, [int64]$Minimum = 0, [int64]$Maximum = [int64]::MaxValue)
    if ($Element.ValueKind -ne [Text.Json.JsonValueKind]::Number) { Stop-P1A 4 "$Name is not a JSON Number" }
    $value = [int64]0
    if (-not $Element.TryGetInt64([ref]$value) -or $value -lt $Minimum -or $value -gt $Maximum) { Stop-P1A 4 "$Name is out of range" }
    $raw = $Element.GetRawText()
    if ($raw -cnotmatch '^(0|[1-9][0-9]*)$' -or $raw -cne $value.ToString($Invariant)) { Stop-P1A 4 "$Name is not canonical decimal" }
    return $value
}

function Get-JsonString {
    param([Text.Json.JsonElement]$Element, [string]$Name)
    if ($Element.ValueKind -ne [Text.Json.JsonValueKind]::String) { Stop-P1A 4 "$Name is not a string" }
    return $Element.GetString()
}

function Open-StrictJsonDocument {
    param([string]$Text)
    $options = [Text.Json.JsonDocumentOptions]::new(); $options.AllowTrailingCommas = $false; $options.CommentHandling = [Text.Json.JsonCommentHandling]::Disallow; $options.MaxDepth = 64
    try { $document = [Text.Json.JsonDocument]::Parse($Text, $options) } catch [Text.Json.JsonException] { Stop-P1A 4 'malformed JSON' }
    Assert-NoJsonDuplicates $document.RootElement '$'
    return $document
}

function Parse-ContentRows {
    param([Text.Json.JsonElement]$RowsElement, [string]$Location, [string]$RequiredPrefix = '')
    if ($RowsElement.ValueKind -ne [Text.Json.JsonValueKind]::Array) { Stop-P1A 4 "$Location is not an array" }
    $rows = [Collections.Generic.List[object]]::new()
    $exact = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    $fold = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $previous = $null; $index = 0
    foreach ($element in $RowsElement.EnumerateArray()) {
        Assert-OrderedJsonKeys $element @('path','bytes','sha256') "$Location[$index]"
        $path = Get-JsonString (Get-JsonProperty $element 'path' "$Location[$index]") "$Location[$index].path"
        $bytes = Get-CanonicalJsonInt64 (Get-JsonProperty $element 'bytes' "$Location[$index]") "$Location[$index].bytes"
        $sha256 = Get-JsonString (Get-JsonProperty $element 'sha256' "$Location[$index]") "$Location[$index].sha256"
        Assert-StageRelativePath $path 4; Assert-Sha256 $sha256 "$Location[$index].sha256" 4
        if (-not [string]::IsNullOrEmpty($RequiredPrefix) -and -not $path.StartsWith($RequiredPrefix, [StringComparison]::Ordinal)) { Stop-P1A 4 "$Location path prefix mismatch" }
        if (-not $exact.Add($path) -or -not $fold.Add($path)) { Stop-P1A 4 "$Location path collision" }
        if ($null -ne $previous -and [StringComparer]::Ordinal.Compare($previous, $path) -ge 0) { Stop-P1A 4 "$Location is not ordinal" }
        $rows.Add([pscustomobject]@{ Path = $path; Bytes = $bytes; Sha256 = $sha256 }); $previous = $path; $index++
    }
    return $rows.ToArray()
}

function Quote-Json { param([string]$Value) return [Text.Json.JsonSerializer]::Serialize([object][string]$Value, [type][string], [Text.Json.JsonSerializerOptions]$null) }

function Build-ContentRowsJson {
    param([object[]]$Rows)
    $parts = [Collections.Generic.List[string]]::new()
    foreach ($row in $Rows) { $parts.Add('{"path":' + (Quote-Json $row.Path) + ',"bytes":' + ([int64]$row.Bytes).ToString($Invariant) + ',"sha256":' + (Quote-Json $row.Sha256) + '}') }
    return [string]::Join(',', $parts)
}

function Get-ContentRoot {
    param([object[]]$Rows)
    $parts = [Collections.Generic.List[string]]::new()
    foreach ($row in $Rows) { $parts.Add(('{0}|{1}|{2}' -f $row.Path, ([int64]$row.Bytes).ToString($Invariant), $row.Sha256)) }
    return ConvertTo-UpperSha256 ($StrictUtf8.GetBytes([string]::Join("`r`n", $parts)))
}

function Build-ProjectManifest {
    param([object[]]$Rows, [string]$Producer)
    return '{"schema":1,"version":1,"algorithm":"SHA-256","namespace":"stage-root","rows":[' + (Build-ContentRowsJson $Rows) +
        '],"row_count":29,"total_bytes":2674489,"project_root_sha256":"' + $P0Root + '","producer_sha256":"' + $Producer + '"}'
}

function Build-RuntimeManifest {
    param([object[]]$Rows, [string[]]$Notices, [string]$RuntimeRoot, [string]$Producer)
    $noticeParts = [Collections.Generic.List[string]]::new(); foreach ($notice in $Notices) { $noticeParts.Add((Quote-Json $notice)) }
    return '{"schema":1,"version":1,"algorithm":"SHA-256","namespace":"stage-root","rows":[' + (Build-ContentRowsJson $Rows) +
        '],"row_count":15003,"total_bytes":575844438,"dist_info_count":99,"notice_paths":[' + [string]::Join(',', $noticeParts) +
        '],"notice_path_count":131,"notice_path_root_sha256":"' + $RuntimeNoticeRoot + '","runtime_root_sha256":"' + $RuntimeRoot +
        '","producer_sha256":"' + $Producer + '"}'
}

function Parse-ProjectManifest {
    param([object]$Snapshot, [string]$StageScriptSha)
    $document = Open-StrictJsonDocument $Snapshot.Text
    try {
        $root = $document.RootElement
        Assert-OrderedJsonKeys $root @('schema','version','algorithm','namespace','rows','row_count','total_bytes','project_root_sha256','producer_sha256') '$project'
        if ((Get-CanonicalJsonInt64 (Get-JsonProperty $root 'schema' '$project') '$project.schema' 1 1) -ne 1 -or
            (Get-CanonicalJsonInt64 (Get-JsonProperty $root 'version' '$project') '$project.version' 1 1) -ne 1) { Stop-P1A 4 'project schema mismatch' }
        if ((Get-JsonString (Get-JsonProperty $root 'algorithm' '$project') '$project.algorithm') -cne 'SHA-256' -or
            (Get-JsonString (Get-JsonProperty $root 'namespace' '$project') '$project.namespace') -cne 'stage-root') { Stop-P1A 4 'project metadata mismatch' }
        $rows = @(Parse-ContentRows (Get-JsonProperty $root 'rows' '$project') '$project.rows')
        $count = Get-CanonicalJsonInt64 (Get-JsonProperty $root 'row_count' '$project') '$project.row_count' 1 ([int64]::MaxValue)
        $total = Get-CanonicalJsonInt64 (Get-JsonProperty $root 'total_bytes' '$project') '$project.total_bytes'
        $declaredRoot = Get-JsonString (Get-JsonProperty $root 'project_root_sha256' '$project') '$project.project_root_sha256'
        $producer = Get-JsonString (Get-JsonProperty $root 'producer_sha256' '$project') '$project.producer_sha256'
        Assert-Sha256 $declaredRoot 'project root'; Assert-Sha256 $producer 'project producer'
        $sum = [int64]0; foreach ($row in $rows) { $sum = Add-NonNegativeInt64 $sum ([int64]$row.Bytes) 4 'project total overflow' }
        if ($count -ne $P0FileCount -or $rows.Count -ne $P0FileCount -or $total -ne $P0TotalBytes -or $sum -ne $P0TotalBytes -or
            $declaredRoot -cne $P0Root -or (Get-ContentRoot $rows) -cne $P0Root -or $producer -cne $StageScriptSha) { Stop-P1A 4 'project manifest invariant mismatch' }
        if ($Snapshot.Text -cne (Build-ProjectManifest $rows $producer)) { Stop-P1A 4 'project manifest is not canonical' }
        return [pscustomobject]@{ Rows = $rows; Root = $declaredRoot; Producer = $producer; Snapshot = $Snapshot }
    } finally { $document.Dispose() }
}

function Get-NoticePaths {
    param([object[]]$Rows)
    $paths = [Collections.Generic.List[string]]::new()
    foreach ($row in $Rows) {
        if ($row.Path.StartsWith('runtime/Lib/site-packages/', [StringComparison]::Ordinal)) {
            $leaf = $row.Path.Substring($row.Path.LastIndexOf('/') + 1)
            if ($leaf -cmatch '^(LICENSE|LICENCE|COPYING|NOTICE|NOTICES|COPYRIGHT|THIRD[-_ ]?PARTY)(\..+)?$') { $paths.Add($row.Path) }
        }
    }
    $result = $paths.ToArray(); [Array]::Sort($result, [StringComparer]::Ordinal); return $result
}

function Get-DistInfoCount {
    param([object[]]$Rows)
    $set = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($row in $Rows) { if ($row.Path -cmatch '^runtime/Lib/site-packages/([^/]+\.dist-info)(?:/.*)?$') { $null = $set.Add($Matches[1]) } }
    return [int64]$set.Count
}

function Parse-RuntimeManifest {
    param([object]$Snapshot, [string]$StageScriptSha)
    $document = Open-StrictJsonDocument $Snapshot.Text
    try {
        $root = $document.RootElement
        Assert-OrderedJsonKeys $root @('schema','version','algorithm','namespace','rows','row_count','total_bytes','dist_info_count','notice_paths','notice_path_count','notice_path_root_sha256','runtime_root_sha256','producer_sha256') '$runtime'
        if ((Get-CanonicalJsonInt64 (Get-JsonProperty $root 'schema' '$runtime') '$runtime.schema' 1 1) -ne 1 -or
            (Get-CanonicalJsonInt64 (Get-JsonProperty $root 'version' '$runtime') '$runtime.version' 1 1) -ne 1) { Stop-P1A 4 'runtime schema mismatch' }
        if ((Get-JsonString (Get-JsonProperty $root 'algorithm' '$runtime') '$runtime.algorithm') -cne 'SHA-256' -or
            (Get-JsonString (Get-JsonProperty $root 'namespace' '$runtime') '$runtime.namespace') -cne 'stage-root') { Stop-P1A 4 'runtime metadata mismatch' }
        $rows = @(Parse-ContentRows (Get-JsonProperty $root 'rows' '$runtime') '$runtime.rows' 'runtime/')
        $count = Get-CanonicalJsonInt64 (Get-JsonProperty $root 'row_count' '$runtime') '$runtime.row_count' 1 ([int64]::MaxValue)
        $total = Get-CanonicalJsonInt64 (Get-JsonProperty $root 'total_bytes' '$runtime') '$runtime.total_bytes'
        $distInfo = Get-CanonicalJsonInt64 (Get-JsonProperty $root 'dist_info_count' '$runtime') '$runtime.dist_info_count' 1 ([int64]::MaxValue)
        $noticeElement = Get-JsonProperty $root 'notice_paths' '$runtime'
        if ($noticeElement.ValueKind -ne [Text.Json.JsonValueKind]::Array) { Stop-P1A 4 'notice_paths is not an array' }
        $notices = [Collections.Generic.List[string]]::new(); $previous = $null; $noticeFold = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        foreach ($item in $noticeElement.EnumerateArray()) {
            $path = Get-JsonString $item '$runtime.notice_paths[]'; Assert-StageRelativePath $path 4
            if (-not $noticeFold.Add($path) -or ($null -ne $previous -and [StringComparer]::Ordinal.Compare($previous, $path) -ge 0)) { Stop-P1A 4 'notice paths collide or are not ordinal' }
            $notices.Add($path); $previous = $path
        }
        $noticeCount = Get-CanonicalJsonInt64 (Get-JsonProperty $root 'notice_path_count' '$runtime') '$runtime.notice_path_count' 1 ([int64]::MaxValue)
        $noticeRoot = Get-JsonString (Get-JsonProperty $root 'notice_path_root_sha256' '$runtime') '$runtime.notice_path_root_sha256'
        $runtimeRoot = Get-JsonString (Get-JsonProperty $root 'runtime_root_sha256' '$runtime') '$runtime.runtime_root_sha256'
        $producer = Get-JsonString (Get-JsonProperty $root 'producer_sha256' '$runtime') '$runtime.producer_sha256'
        foreach ($sha in @($noticeRoot,$runtimeRoot,$producer)) { Assert-Sha256 $sha 'runtime SHA' }
        $sum = [int64]0; foreach ($row in $rows) { $sum = Add-NonNegativeInt64 $sum ([int64]$row.Bytes) 4 'runtime total overflow' }
        $selectedNotices = [string[]]@(Get-NoticePaths $rows); $selectedDistInfo = Get-DistInfoCount $rows
        $selectedNoticeRoot = ConvertTo-UpperSha256 ($StrictUtf8.GetBytes([string]::Join("`r`n", $selectedNotices)))
        if ($count -ne $RuntimeFileCount -or $rows.Count -ne $RuntimeFileCount -or $total -ne $RuntimeTotalBytes -or $sum -ne $RuntimeTotalBytes -or
            $distInfo -ne $RuntimeDistInfoCount -or $selectedDistInfo -ne $RuntimeDistInfoCount -or $noticeCount -ne $RuntimeNoticeCount -or
            $notices.Count -ne $RuntimeNoticeCount -or $noticeRoot -cne $RuntimeNoticeRoot -or $selectedNoticeRoot -cne $RuntimeNoticeRoot -or
            $runtimeRoot -cne $RuntimeContentRootSha256 -or $runtimeRoot -cne (Get-ContentRoot $rows) -or
            $producer -cne $StageScriptSha) { Stop-P1A 4 'runtime manifest invariant mismatch' }
        for ($index=0; $index -lt $notices.Count; $index++) { if ($notices[$index] -cne $selectedNotices[$index]) { Stop-P1A 4 'notice path list mismatch' } }
        if ($Snapshot.Text -cne (Build-RuntimeManifest $rows $notices.ToArray() $runtimeRoot $producer)) { Stop-P1A 4 'runtime manifest is not canonical' }
        return [pscustomobject]@{ Rows=$rows; Root=$runtimeRoot; Producer=$producer; Notices=$notices.ToArray(); Snapshot=$Snapshot }
    } finally { $document.Dispose() }
}

function Get-U16 { param([byte[]]$Bytes,[int64]$Offset) Assert-ByteRange $Bytes $Offset 2; return [BitConverter]::ToUInt16($Bytes,[int]$Offset) }
function Get-U32 { param([byte[]]$Bytes,[int64]$Offset) Assert-ByteRange $Bytes $Offset 4; return [BitConverter]::ToUInt32($Bytes,[int]$Offset) }
function Get-U64 { param([byte[]]$Bytes,[int64]$Offset) Assert-ByteRange $Bytes $Offset 8; return [BitConverter]::ToUInt64($Bytes,[int]$Offset) }
function Assert-ByteRange {
    param([byte[]]$Bytes,[int64]$Offset,[int64]$Length)
    if ($Offset -lt 0 -or $Length -lt 0 -or $Offset -gt $Bytes.LongLength -or $Length -gt ($Bytes.LongLength - $Offset)) {
        Stop-P1A 7 'PE range invalid'
    }
}

function Resolve-CheckedRvaRange {
    param([uint32]$Rva,[uint64]$Length,[object[]]$Sections,[uint32]$SizeOfHeaders,[int64]$FileLength)
    if ($Length -eq 0 -or $FileLength -lt 0) { Stop-P1A 7 'empty or invalid RVA range' }
    $startRva = [uint64]$Rva
    if ($startRva -gt ([uint64]::MaxValue - $Length)) { Stop-P1A 7 'RVA range arithmetic overflow' }
    $endRva = $startRva + $Length
    $rvaSpace = [uint64][uint32]::MaxValue + [uint64]1
    if ($endRva -gt $rvaSpace) { Stop-P1A 7 'RVA range exceeds 32-bit address space' }
    if ($startRva -lt [uint64]$SizeOfHeaders) {
        if ($endRva -gt [uint64]$SizeOfHeaders -or $endRva -gt [uint64]$FileLength) {
            Stop-P1A 7 'RVA range crosses PE header boundary or EOF'
        }
        return [pscustomobject]@{ Offset=[int64]$startRva; EndOffset=[int64]$endRva; RegionStartOffset=[int64]0; RegionEndOffset=[int64]$SizeOfHeaders; RegionKind='HEADER' }
    }
    $matches = [Collections.Generic.List[object]]::new()
    foreach ($section in $Sections) {
        $virtualStart = [uint64]$section.VirtualAddress
        $virtualSpan = [Math]::Max([uint64]$section.VirtualSize,[uint64]$section.RawSize)
        if ($virtualStart -gt ([uint64]::MaxValue - $virtualSpan)) { Stop-P1A 7 'section RVA arithmetic overflow' }
        $virtualEnd = $virtualStart + $virtualSpan
        if ($virtualEnd -gt $rvaSpace) { Stop-P1A 7 'section exceeds 32-bit RVA space' }
        if ($virtualSpan -gt 0 -and $startRva -ge $virtualStart -and $startRva -lt $virtualEnd) {
            $delta = $startRva - $virtualStart
            if ($delta -ge [uint64]$section.RawSize -or $Length -gt ([uint64]$section.RawSize - $delta)) {
                Stop-P1A 7 'RVA range enters virtual-only tail or crosses raw section'
            }
            if ($endRva -gt $virtualEnd) { Stop-P1A 7 'RVA range crosses virtual section' }
            $rawStart = [uint64]$section.RawPointer
            if ($rawStart -gt ([uint64]::MaxValue - $delta)) { Stop-P1A 7 'raw offset arithmetic overflow' }
            $offset = $rawStart + $delta
            if ($offset -gt ([uint64]::MaxValue - $Length)) { Stop-P1A 7 'raw range arithmetic overflow' }
            $endOffset = $offset + $Length
            if ($endOffset -gt [uint64]$FileLength) { Stop-P1A 7 'RVA range extends past EOF' }
            if ($rawStart -gt ([uint64]::MaxValue - [uint64]$section.RawSize)) { Stop-P1A 7 'raw section arithmetic overflow' }
            $regionEnd = $rawStart + [uint64]$section.RawSize
            $matches.Add([pscustomobject]@{ Offset=[int64]$offset; EndOffset=[int64]$endOffset; RegionStartOffset=[int64]$rawStart; RegionEndOffset=[int64]$regionEnd; RegionKind='SECTION' })
        }
    }
    if ($matches.Count -ne 1) { Stop-P1A 7 'RVA range is in a gap or ambiguous section' }
    return $matches[0]
}

function Read-AsciiZ {
    param([byte[]]$Bytes,[uint32]$Rva,[object[]]$Sections,[uint32]$SizeOfHeaders)
    $initial = Resolve-CheckedRvaRange $Rva 1 $Sections $SizeOfHeaders $Bytes.LongLength
    $buffer = [Collections.Generic.List[byte]]::new()
    for ($index = 0; $index -lt 4096; $index++) {
        if ([int64]$index -ge ($initial.RegionEndOffset - $initial.Offset)) { Stop-P1A 7 'PE import name crosses mapped range' }
        $offset = $initial.Offset + [int64]$index
        Assert-ByteRange $Bytes $offset 1
        $value = $Bytes[$offset]
        if ($value -eq 0) {
            if ($buffer.Count -eq 0) { Stop-P1A 7 'empty PE import name' }
            $complete = Resolve-CheckedRvaRange $Rva ([uint64]($index + 1)) $Sections $SizeOfHeaders $Bytes.LongLength
            if ($complete.Offset -ne $initial.Offset -or $complete.RegionStartOffset -ne $initial.RegionStartOffset -or $complete.RegionEndOffset -ne $initial.RegionEndOffset) {
                Stop-P1A 7 'PE import name changed mapped range'
            }
            return [Text.Encoding]::ASCII.GetString($buffer.ToArray())
        }
        if ($value -gt 0x7F) { Stop-P1A 7 'non-ASCII PE import name' }
        $buffer.Add($value)
    }
    Stop-P1A 7 'unterminated PE import name'
}

function Read-ImportDirectory {
    param([byte[]]$Bytes,[uint32]$Rva,[uint32]$Size,[object[]]$Sections,[uint32]$SizeOfHeaders)
    $result = [Collections.Generic.List[string]]::new()
    if ($Rva -eq 0 -and $Size -eq 0) { return $result.ToArray() }
    if ($Rva -eq 0 -or $Size -lt 20) { Stop-P1A 7 'invalid normal import directory' }
    $range = Resolve-CheckedRvaRange $Rva ([uint64]$Size) $Sections $SizeOfHeaders $Bytes.LongLength
    $offset = $range.Offset
    $limit = $range.EndOffset
    $terminated = $false
    for ($index = 0; $index -lt 4096; $index++) {
        $entry = $offset + [int64]$index * 20
        if ($entry + 20 -gt $limit) { Stop-P1A 7 'unterminated normal import directory' }
        $allZero = $true
        for ($word = 0; $word -lt 5; $word++) { if ((Get-U32 $Bytes ($entry + $word * 4)) -ne 0) { $allZero = $false } }
        if ($allZero) { $terminated = $true; break }
        $nameRva = Get-U32 $Bytes ($entry + 12)
        if ($nameRva -eq 0) { Stop-P1A 7 'normal import name RVA missing' }
        $result.Add((Read-AsciiZ $Bytes $nameRva $Sections $SizeOfHeaders))
    }
    if (-not $terminated) { Stop-P1A 7 'normal import descriptor limit' }
    return $result.ToArray()
}

function Read-DelayImportDirectory {
    param([byte[]]$Bytes,[uint32]$Rva,[uint32]$Size,[object[]]$Sections,[uint32]$SizeOfHeaders,[uint64]$ImageBase)
    $result = [Collections.Generic.List[string]]::new()
    if ($Rva -eq 0 -and $Size -eq 0) { return $result.ToArray() }
    if ($Rva -eq 0 -or $Size -lt 32) { Stop-P1A 7 'invalid delay import directory' }
    $range = Resolve-CheckedRvaRange $Rva ([uint64]$Size) $Sections $SizeOfHeaders $Bytes.LongLength
    $offset = $range.Offset
    $limit = $range.EndOffset
    $terminated = $false
    for ($index = 0; $index -lt 4096; $index++) {
        $entry = $offset + [int64]$index * 32
        if ($entry + 32 -gt $limit) { Stop-P1A 7 'unterminated delay import directory' }
        $values = [uint32[]]::new(8); $allZero = $true
        for ($word = 0; $word -lt 8; $word++) { $values[$word] = Get-U32 $Bytes ($entry + $word * 4); if ($values[$word] -ne 0) { $allZero = $false } }
        if ($allZero) { $terminated = $true; break }
        $attributes = $values[0]
        if ($attributes -ne 0 -and $attributes -ne 1) { Stop-P1A 7 'delay import attributes invalid' }
        $nameValue = [uint64]$values[1]
        if ($attributes -eq 1) { $nameRva = [uint32]$nameValue }
        else {
            if ($nameValue -lt $ImageBase -or ($nameValue - $ImageBase) -gt [uint32]::MaxValue) { Stop-P1A 7 'delay import VA invalid' }
            $nameRva = [uint32]($nameValue - $ImageBase)
        }
        if ($nameRva -eq 0) { Stop-P1A 7 'delay import name missing' }
        $result.Add((Read-AsciiZ $Bytes $nameRva $Sections $SizeOfHeaders))
    }
    if (-not $terminated) { Stop-P1A 7 'delay import descriptor limit' }
    return $result.ToArray()
}

function Get-PeImports {
    param([byte[]]$Bytes,[string]$ImporterPath,[int64]$ObservedBytes,[string]$ObservedSha256)
    Assert-ByteRange $Bytes 0 64
    if ((Get-U16 $Bytes 0) -ne 0x5A4D) { Stop-P1A 7 'selected native image lacks MZ' }
    $peOffset = [int64](Get-U32 $Bytes 0x3C); Assert-ByteRange $Bytes $peOffset 24
    if ((Get-U32 $Bytes $peOffset) -ne 0x00004550) { Stop-P1A 7 'selected native image lacks PE' }
    $machine = Get-U16 $Bytes ($peOffset + 4)
    if ($null -ne $ImporterPath -and $ForeignToolImages.ContainsKey($ImporterPath)) {
        $allowed = $ForeignToolImages[$ImporterPath]
        if (-not $ImporterPath.EndsWith('.exe',[StringComparison]::OrdinalIgnoreCase) -or $machine -ne $allowed.Machine -or
            $ObservedBytes -ne $allowed.Bytes -or $ObservedSha256 -cne $allowed.Sha256) { Stop-P1A 7 'foreign tool identity mismatch' }
        return [pscustomobject]@{NORMAL=[string[]]::new(0);DELAY=[string[]]::new(0)}
    }
    if ($machine -ne 0x8664) { Stop-P1A 7 'selected native image is not AMD64' }
    $sectionCount = [int](Get-U16 $Bytes ($peOffset + 6))
    if ($sectionCount -lt 1 -or $sectionCount -gt 96) { Stop-P1A 7 'invalid PE section count' }
    $optionalSize = [int](Get-U16 $Bytes ($peOffset + 20)); $optionalOffset = $peOffset + 24
    if ($optionalSize -lt 112) { Stop-P1A 7 'truncated PE32+ optional header' }
    Assert-ByteRange $Bytes $optionalOffset $optionalSize
    if ((Get-U16 $Bytes $optionalOffset) -ne 0x20B) { Stop-P1A 7 'selected AMD64 image is not PE32+' }
    $directoryBase = $optionalOffset + 112; $directoryCountOffset = $optionalOffset + 108
    $imageBase = Get-U64 $Bytes ($optionalOffset + 24); $sizeOfHeaders = Get-U32 $Bytes ($optionalOffset + 60)
    $directoryCount = Get-U32 $Bytes $directoryCountOffset
    if ($directoryCount -gt 128 -or [uint64]$directoryBase + ([uint64]$directoryCount * 8) -gt [uint64]($optionalOffset + $optionalSize)) {
        Stop-P1A 7 'invalid PE data directories'
    }
    $sectionsOffset = $optionalOffset + $optionalSize; $sectionTableBytes = [int64]$sectionCount * 40
    Assert-ByteRange $Bytes $sectionsOffset $sectionTableBytes
    if ([uint64]$sizeOfHeaders -lt [uint64]($sectionsOffset + $sectionTableBytes) -or [uint64]$sizeOfHeaders -gt [uint64]$Bytes.LongLength) {
        Stop-P1A 7 'invalid SizeOfHeaders'
    }
    $sections = [Collections.Generic.List[object]]::new()
    for ($index = 0; $index -lt $sectionCount; $index++) {
        $entry = $sectionsOffset + $index * 40
        $section = [pscustomobject]@{ VirtualSize=Get-U32 $Bytes ($entry+8); VirtualAddress=Get-U32 $Bytes ($entry+12); RawSize=Get-U32 $Bytes ($entry+16); RawPointer=Get-U32 $Bytes ($entry+20) }
        if ($section.RawSize -gt 0) {
            $rawEnd = [uint64]$section.RawPointer + [uint64]$section.RawSize
            if ([uint64]$section.RawPointer -lt [uint64]$sizeOfHeaders -or $rawEnd -gt [uint64]$Bytes.LongLength) { Stop-P1A 7 'PE section raw range invalid' }
        }
        $sections.Add($section)
    }
    for ($left=0; $left -lt $sections.Count; $left++) {
        for ($right=$left+1; $right -lt $sections.Count; $right++) {
            $a=$sections[$left]; $b=$sections[$right]
            if ($a.RawSize -gt 0 -and $b.RawSize -gt 0) {
                $aStart=[uint64]$a.RawPointer; $aEnd=$aStart+[uint64]$a.RawSize; $bStart=[uint64]$b.RawPointer; $bEnd=$bStart+[uint64]$b.RawSize
                if ($aStart -lt $bEnd -and $bStart -lt $aEnd) { Stop-P1A 7 'overlapping PE raw sections' }
            }
            $aSpan=[Math]::Max([uint64]$a.VirtualSize,[uint64]$a.RawSize); $bSpan=[Math]::Max([uint64]$b.VirtualSize,[uint64]$b.RawSize)
            if ($aSpan -gt 0 -and $bSpan -gt 0) {
                $aStart=[uint64]$a.VirtualAddress; $aEnd=$aStart+$aSpan; $bStart=[uint64]$b.VirtualAddress; $bEnd=$bStart+$bSpan
                if ($aStart -lt $bEnd -and $bStart -lt $aEnd) { Stop-P1A 7 'overlapping PE virtual sections' }
            }
        }
    }
    $importRva=[uint32]0; $importSize=[uint32]0; $delayRva=[uint32]0; $delaySize=[uint32]0
    if ($directoryCount -gt 1) { $importRva=Get-U32 $Bytes ($directoryBase+8); $importSize=Get-U32 $Bytes ($directoryBase+12) }
    if ($directoryCount -gt 13) { $delayRva=Get-U32 $Bytes ($directoryBase+104); $delaySize=Get-U32 $Bytes ($directoryBase+108) }
    return [pscustomobject]@{
        NORMAL = Read-ImportDirectory $Bytes $importRva $importSize $sections.ToArray() $sizeOfHeaders
        DELAY = Read-DelayImportDirectory $Bytes $delayRva $delaySize $sections.ToArray() $sizeOfHeaders $imageBase
    }
}

function Sort-ImportNames {
    param([string[]]$Names)
    if($null-eq$Names){$Names=[string[]]::new(0)}
    $map=[Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal); $keys=[string[]]::new($Names.Count)
    for($index=0;$index-lt$Names.Count;$index++){$lower=$Names[$index].ToLowerInvariant();$key=$lower+"`0"+$Names[$index]+"`0"+$index.ToString('D10',$Invariant);$keys[$index]=$key;$map.Add($key,$Names[$index])}
    [Array]::Sort($keys,[StringComparer]::Ordinal);$result=[Collections.Generic.List[string]]::new();foreach($key in $keys){$result.Add($map[$key])};return $result.ToArray()
}

function Get-NativePathDirectory {
    param([string]$Path)
    $slash=$Path.LastIndexOf('/');if($slash-gt0){return $Path.Substring(0,$slash)};return ''
}

function Select-NativeImportCandidate {
    param([string]$ImporterPath,[string]$ImportName,[object]$CandidateMap)
    if(-not$CandidateMap.ContainsKey($ImportName)-or$CandidateMap[$ImportName].Count-eq0){Stop-P1A 7 'native import unresolved'}
    $candidates=[object[]]@($CandidateMap[$ImportName]);$first=$candidates[0]
    foreach($candidate in $candidates){if([int64]$candidate.Bytes-ne[int64]$first.Bytes-or$candidate.Sha256-cne$first.Sha256){Stop-P1A 7 'native import has byte-different candidates'}}
    $pathMap=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal);$paths=[string[]]::new($candidates.Count)
    for($index=0;$index-lt$candidates.Count;$index++){$path=$candidates[$index].Path;$pathMap.Add($path,$candidates[$index]);$paths[$index]=$path}
    [Array]::Sort($paths,[StringComparer]::Ordinal)
    $importerDirectory=Get-NativePathDirectory $ImporterPath
    foreach($path in $paths){if((Get-NativePathDirectory $path)-ceq$importerDirectory){return $pathMap[$path]}}
    $ownerDirectory=$null;$sitePrefix='runtime/Lib/site-packages/'
    if($ImporterPath.StartsWith($sitePrefix,[StringComparison]::Ordinal)){$remainder=$ImporterPath.Substring($sitePrefix.Length);$slash=$remainder.IndexOf('/');if($slash-gt0){$owner=$remainder.Substring(0,$slash);if($PinnedOwnerDirectories.ContainsKey($owner)){$ownerDirectory=$PinnedOwnerDirectories[$owner]}}}
    if($null-ne$ownerDirectory){foreach($path in $paths){if((Get-NativePathDirectory $path)-ceq$ownerDirectory){return $pathMap[$path]}}}
    foreach($declaredDirectory in @('runtime','runtime/DLLs')){foreach($path in $paths){if((Get-NativePathDirectory $path)-ceq$declaredDirectory){return $pathMap[$path]}}}
    return $pathMap[$paths[0]]
}

function Get-NativeClosure {
    param([string]$Root,[object[]]$RuntimeRows)
    $runtimeMap=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal);foreach($row in $RuntimeRows){$runtimeMap.Add($row.Path,$row)}
    $allowedDirs=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal);$null=$allowedDirs.Add('runtime');$null=$allowedDirs.Add('runtime/DLLs')
    foreach($row in $RuntimeRows){if($row.Path.StartsWith('runtime/Lib/site-packages/',[StringComparison]::Ordinal)-and($row.Path.EndsWith('.dll',[StringComparison]::OrdinalIgnoreCase)-or$row.Path.EndsWith('.pyd',[StringComparison]::OrdinalIgnoreCase))){$slash=$row.Path.LastIndexOf('/');if($slash-gt0){$null=$allowedDirs.Add($row.Path.Substring(0,$slash))}}}
    $candidateMap=[Collections.Generic.Dictionary[string,Collections.Generic.List[object]]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach($row in $RuntimeRows){$slash=$row.Path.LastIndexOf('/');$directory=if($slash-gt0){$row.Path.Substring(0,$slash)}else{''};$leaf=if($slash-ge0){$row.Path.Substring($slash+1)}else{$row.Path};$isDll=$leaf.EndsWith('.dll',[StringComparison]::OrdinalIgnoreCase);$isWinspool=$leaf.Equals('winspool.drv',[StringComparison]::OrdinalIgnoreCase);if(($allowedDirs.Contains($directory)-and$isDll)-or$isWinspool){if(-not$candidateMap.ContainsKey($leaf)){$candidateMap.Add($leaf,[Collections.Generic.List[object]]::new())};$candidateMap[$leaf].Add($row)}}
    $initial=[Collections.Generic.List[string]]::new();foreach($row in $RuntimeRows){if($row.Path.EndsWith('.exe',[StringComparison]::OrdinalIgnoreCase)-or$row.Path.EndsWith('.dll',[StringComparison]::OrdinalIgnoreCase)-or$row.Path.EndsWith('.pyd',[StringComparison]::OrdinalIgnoreCase)){$initial.Add($row.Path)}};$initialArray=$initial.ToArray();[Array]::Sort($initialArray,[StringComparer]::Ordinal)
    $queue=[Collections.Generic.Queue[string]]::new();$seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase);foreach($path in $initialArray){$queue.Enqueue($path);$null=$seen.Add($path)}
    $rows=[Collections.Generic.List[object]]::new();$preimages=[Collections.Generic.List[string]]::new();$total=[int64]0
    while($queue.Count-gt0){$importer=$queue.Dequeue();$expectedImporter=$runtimeMap[$importer];$snapshot=Read-StableFile (Resolve-ExactStageFile $Root $importer) $importer 7;if($snapshot.Bytes-ne$expectedImporter.Bytes-or$snapshot.Sha256-cne$expectedImporter.Sha256){Stop-P1A 7 'native importer identity mismatch'};$imports=Get-PeImports $snapshot.Raw $importer $snapshot.Bytes $snapshot.Sha256;foreach($kind in @('NORMAL','DELAY')){$names=[string[]]@(Sort-ImportNames ([string[]]$imports.$kind));foreach($original in $names){$name=$original.ToLowerInvariant();if($name-cne'winspool.drv'-and$name-cnotmatch'^[a-z0-9][a-z0-9._-]*\.dll$'){Stop-P1A 7 'native import name grammar'};$classification=$null;$resolutionPath=$null;$resolutionBytes=[int64]0;$resolutionSha=$null;$hasStaged=$candidateMap.ContainsKey($name)-and$candidateMap[$name].Count-gt0;if($name-cmatch'^(api|ext)-ms-win-[a-z0-9-]+-l[0-9]+-[0-9]+-[0-9]+\.dll$'){if($hasStaged){Stop-P1A 7 'API set is shadowed by staged file'};$classification='API_SET'}elseif($SystemImports.Contains($name)){if($hasStaged){Stop-P1A 7 'system import is shadowed by staged file'};$classification='SYSTEM'}else{$target=Select-NativeImportCandidate $importer $name $candidateMap;$targetSnapshot=Read-StableFile (Resolve-ExactStageFile $Root $target.Path) $target.Path 7;if($targetSnapshot.Bytes-ne$target.Bytes-or$targetSnapshot.Sha256-cne$target.Sha256){Stop-P1A 7 'native target identity mismatch'};$classification='STAGED';$resolutionPath=$target.Path;$resolutionBytes=[int64]$target.Bytes;$resolutionSha=$target.Sha256;$total=Add-NonNegativeInt64 $total $resolutionBytes 7 'native total overflow';if($seen.Add($target.Path)){$queue.Enqueue($target.Path)}};$row=[pscustomobject]@{ImporterPath=$importer;ImportKind=$kind;ImportName=$name;Classification=$classification;ResolutionKind=$classification;ResolutionPath=$resolutionPath;ResolutionBytes=$resolutionBytes;ResolutionSha256=$resolutionSha};$rows.Add($row);if($classification-ceq'STAGED'){$preimages.Add([string]::Join('|',@($importer,$kind,$name,$classification,$classification,$resolutionPath,$resolutionBytes.ToString($Invariant),$resolutionSha)))}else{$preimages.Add([string]::Join('|',@($importer,$kind,$name,$classification,$classification,'-','-','-')))}}}}
    $rootHash=ConvertTo-UpperSha256 ($StrictUtf8.GetBytes([string]::Join("`r`n",$preimages)))
    return [pscustomobject]@{Rows=$rows.ToArray();RowCount=[int64]$rows.Count;TotalBytes=$total;Root=$rootHash}
}

function Assert-NativeClosureMatchesReceipt {
    param([object]$Computed,[object]$Receipt)
    if($Computed.RowCount-ne$Receipt.RowCount-or$Computed.TotalBytes-ne$Receipt.TotalBytes-or$Computed.Root-cne$Receipt.Root-or$Computed.Rows.Count-ne$Receipt.Rows.Count){Stop-P1A 7 'native receipt differs from independently recomputed closure'}
    for($index=0;$index-lt$Computed.Rows.Count;$index++){
        $left=$Computed.Rows[$index];$right=$Receipt.Rows[$index]
        foreach($field in @('ImporterPath','ImportKind','ImportName','Classification','ResolutionKind','ResolutionPath','ResolutionBytes','ResolutionSha256')){
            if($left.$field -cne $right.$field){Stop-P1A 7 'native receipt row differs from independently recomputed closure'}
        }
    }
}

function Parse-NativeReceipt {
    param([object]$Snapshot, [string]$RuntimeManifestSha, [string]$NativeScriptSha, [Collections.Generic.Dictionary[string,object]]$RuntimeMap)
    $document = Open-StrictJsonDocument $Snapshot.Text
    try {
        $root = $document.RootElement
        Assert-OrderedJsonKeys $root @('schema','version','algorithm','namespace','runtime_input_manifest_sha256','rows','row_count','total_bytes','native_closure_root_sha256','producer_sha256','verifier_sha256') '$native'
        if ((Get-CanonicalJsonInt64 (Get-JsonProperty $root 'schema' '$native') '$native.schema' 1 1) -ne 1 -or
            (Get-CanonicalJsonInt64 (Get-JsonProperty $root 'version' '$native') '$native.version' 1 1) -ne 1) { Stop-P1A 4 'native schema mismatch' }
        if ((Get-JsonString (Get-JsonProperty $root 'algorithm' '$native') '$native.algorithm') -cne 'SHA-256' -or
            (Get-JsonString (Get-JsonProperty $root 'namespace' '$native') '$native.namespace') -cne 'stage-root') { Stop-P1A 4 'native metadata mismatch' }
        $runtimeManifestPin = Get-JsonString (Get-JsonProperty $root 'runtime_input_manifest_sha256' '$native') '$native.runtime_input_manifest_sha256'
        $rowsElement = Get-JsonProperty $root 'rows' '$native'; if ($rowsElement.ValueKind -ne [Text.Json.JsonValueKind]::Array) { Stop-P1A 4 'native rows are not an array' }
        $rows = [Collections.Generic.List[object]]::new(); $preimages = [Collections.Generic.List[string]]::new(); $total = [int64]0; $index=0
        foreach ($element in $rowsElement.EnumerateArray()) {
            Assert-OrderedJsonKeys $element @('importer_path','import_kind','import_name','classification','resolution') ('$native.rows[' + $index.ToString($Invariant) + ']')
            $importer = Get-JsonString (Get-JsonProperty $element 'importer_path' '$native.rows') 'importer_path'; Assert-StageRelativePath $importer 4
            $kind = Get-JsonString (Get-JsonProperty $element 'import_kind' '$native.rows') 'import_kind'; if ($kind -cne 'NORMAL' -and $kind -cne 'DELAY') { Stop-P1A 4 'native import_kind invalid' }
            $name = Get-JsonString (Get-JsonProperty $element 'import_name' '$native.rows') 'import_name'
            if ($name -ceq '-' -or $name.Contains('|') -or ($name -cne 'winspool.drv' -and $name -cnotmatch '^[a-z0-9][a-z0-9._-]*\.dll$')) { Stop-P1A 4 'native import_name invalid' }
            $classification = Get-JsonString (Get-JsonProperty $element 'classification' '$native.rows') 'classification'
            if ($classification -notin @('SYSTEM','API_SET','STAGED','UNRESOLVED') -or $classification -ceq 'UNRESOLVED') { Stop-P1A 4 'native classification invalid' }
            $resolution = Get-JsonProperty $element 'resolution' '$native.rows'
            $resolutionKind = Get-JsonString (Get-JsonProperty $resolution 'kind' '$native.rows.resolution') 'resolution.kind'
            if ($resolutionKind -cne $classification) { Stop-P1A 4 'native resolution kind mismatch' }
            $pathField='-'; $bytesField='-'; $shaField='-'; $resolutionPath=$null; $resolutionBytes=[int64]0; $resolutionSha=$null
            if ($classification -ceq 'SYSTEM' -or $classification -ceq 'API_SET') {
                Assert-OrderedJsonKeys $resolution @('kind') '$native.rows.resolution'
            } else {
                Assert-OrderedJsonKeys $resolution @('kind','path','bytes','sha256') '$native.rows.resolution'
                $resolutionPath = Get-JsonString (Get-JsonProperty $resolution 'path' '$native.rows.resolution') 'resolution.path'; Assert-StageRelativePath $resolutionPath 4
                $resolutionBytes = Get-CanonicalJsonInt64 (Get-JsonProperty $resolution 'bytes' '$native.rows.resolution') 'resolution.bytes'
                $resolutionSha = Get-JsonString (Get-JsonProperty $resolution 'sha256' '$native.rows.resolution') 'resolution.sha256'; Assert-Sha256 $resolutionSha 'resolution.sha256'
                if (-not $RuntimeMap.ContainsKey($resolutionPath)) { Stop-P1A 4 'native resolution is outside runtime manifest' }
                $expected = $RuntimeMap[$resolutionPath]
                if ($expected.Bytes -ne $resolutionBytes -or $expected.Sha256 -cne $resolutionSha) { Stop-P1A 4 'native resolution does not match runtime manifest' }
                $physical = Read-StableFile (Resolve-ExactStageFile $StageRoot $resolutionPath) $resolutionPath 4
                if ($physical.Bytes -ne $resolutionBytes -or $physical.Sha256 -cne $resolutionSha) { Stop-P1A 4 'native resolution physical mismatch' }
                $pathField=$resolutionPath; $bytesField=$resolutionBytes.ToString($Invariant); $shaField=$resolutionSha
                $total = Add-NonNegativeInt64 $total $resolutionBytes 4 'native total overflow'
            }
            $preimages.Add([string]::Join('|',@($importer,$kind,$name,$classification,$resolutionKind,$pathField,$bytesField,$shaField)))
            $rows.Add([pscustomobject]@{ImporterPath=$importer;ImportKind=$kind;ImportName=$name;Classification=$classification;ResolutionKind=$resolutionKind;ResolutionPath=$resolutionPath;ResolutionBytes=$resolutionBytes;ResolutionSha256=$resolutionSha})
            $index++
        }
        $rowCount = Get-CanonicalJsonInt64 (Get-JsonProperty $root 'row_count' '$native') '$native.row_count'
        $declaredTotal = Get-CanonicalJsonInt64 (Get-JsonProperty $root 'total_bytes' '$native') '$native.total_bytes'
        $closureRoot = Get-JsonString (Get-JsonProperty $root 'native_closure_root_sha256' '$native') '$native.native_closure_root_sha256'
        $producer = Get-JsonString (Get-JsonProperty $root 'producer_sha256' '$native') '$native.producer_sha256'
        $verifier = Get-JsonString (Get-JsonProperty $root 'verifier_sha256' '$native') '$native.verifier_sha256'
        foreach ($sha in @($runtimeManifestPin,$closureRoot,$producer,$verifier)) { Assert-Sha256 $sha 'native SHA' }
        $computedRoot = ConvertTo-UpperSha256 ($StrictUtf8.GetBytes([string]::Join("`r`n",$preimages)))
        if ($runtimeManifestPin -cne $RuntimeManifestSha -or $rowCount -ne $rows.Count -or $declaredTotal -ne $total -or
            $closureRoot -cne $computedRoot -or $producer -cne $NativeScriptSha -or $verifier -cne $NativeScriptSha) { Stop-P1A 4 'native receipt invariant mismatch' }
        $canonical = Build-NativeReceipt $runtimeManifestPin $rows.ToArray() $rowCount $total $closureRoot $producer $verifier
        if ($Snapshot.Text -cne $canonical) { Stop-P1A 4 'native receipt is not canonical' }
        return [pscustomobject]@{Rows=$rows.ToArray();RowCount=$rowCount;TotalBytes=$total;Root=$closureRoot;Snapshot=$Snapshot;Producer=$producer;Verifier=$verifier}
    } finally { $document.Dispose() }
}

function Build-NativeReceipt {
    param([string]$RuntimeManifestSha,[object[]]$Rows,[int64]$RowCount,[int64]$Total,[string]$Root,[string]$Producer,[string]$Verifier)
    $items=[Collections.Generic.List[string]]::new()
    foreach($row in $Rows){
        $resolution = if($row.Classification -ceq 'STAGED'){'{"kind":"STAGED","path":'+(Quote-Json $row.ResolutionPath)+',"bytes":'+$row.ResolutionBytes.ToString($Invariant)+',"sha256":"'+$row.ResolutionSha256+'"}'}else{'{"kind":"'+$row.Classification+'"}'}
        $items.Add('{"importer_path":'+(Quote-Json $row.ImporterPath)+',"import_kind":"'+$row.ImportKind+'","import_name":"'+$row.ImportName+'","classification":"'+$row.Classification+'","resolution":'+$resolution+'}')
    }
    return '{"schema":1,"version":1,"algorithm":"SHA-256","namespace":"stage-root","runtime_input_manifest_sha256":"'+$RuntimeManifestSha+'","rows":['+[string]::Join(',',$items)+'],"row_count":'+$RowCount.ToString($Invariant)+',"total_bytes":'+$Total.ToString($Invariant)+',"native_closure_root_sha256":"'+$Root+'","producer_sha256":"'+$Producer+'","verifier_sha256":"'+$Verifier+'"}'
}

function Parse-StageReceipt {
    param([object]$Snapshot,[object]$Project,[object]$Runtime,[object]$Native,[string]$StageScriptSha,[string]$VerifyScriptSha,[string]$NativeScriptSha,[string]$StageContentRoot)
    $document=Open-StrictJsonDocument $Snapshot.Text
    try{
        $root=$document.RootElement
        $keys=@('schema','version','algorithm','project_manifest_sha256','runtime_manifest_sha256','native_receipt_sha256','project_root_sha256','runtime_root_sha256','native_closure_root_sha256','native_row_count','native_total_bytes','notice_path_count','notice_path_root_sha256','stage_content_root_sha256','project_row_count','project_total_bytes','runtime_row_count','runtime_total_bytes','stage_content_row_count','stage_content_total_bytes','stage_payload_sha256','verify_stage_sha256','native_script_sha256')
        Assert-OrderedJsonKeys $root $keys '$stage_receipt'
        if((Get-CanonicalJsonInt64 (Get-JsonProperty $root 'schema' '$stage_receipt') 'schema' 1 1)-ne 1 -or (Get-CanonicalJsonInt64 (Get-JsonProperty $root 'version' '$stage_receipt') 'version' 1 1)-ne 1){Stop-P1A 4 'stage receipt schema mismatch'}
        if((Get-JsonString (Get-JsonProperty $root 'algorithm' '$stage_receipt') 'algorithm') -cne 'SHA-256'){Stop-P1A 4 'stage receipt algorithm mismatch'}
        $values=[ordered]@{}
        foreach($name in @('project_manifest_sha256','runtime_manifest_sha256','native_receipt_sha256','project_root_sha256','runtime_root_sha256','native_closure_root_sha256','notice_path_root_sha256','stage_content_root_sha256','stage_payload_sha256','verify_stage_sha256','native_script_sha256')){$values[$name]=Get-JsonString (Get-JsonProperty $root $name '$stage_receipt') $name;Assert-Sha256 $values[$name] $name}
        foreach($name in @('native_row_count','native_total_bytes','notice_path_count','project_row_count','project_total_bytes','runtime_row_count','runtime_total_bytes','stage_content_row_count','stage_content_total_bytes')){$values[$name]=Get-CanonicalJsonInt64 (Get-JsonProperty $root $name '$stage_receipt') $name}
        if($values.project_manifest_sha256 -cne $Project.Snapshot.Sha256 -or $values.runtime_manifest_sha256 -cne $Runtime.Snapshot.Sha256 -or
            $values.native_receipt_sha256 -cne $Native.Snapshot.Sha256 -or $values.project_root_sha256 -cne $P0Root -or
            $values.runtime_root_sha256 -cne $Runtime.Root -or $values.native_closure_root_sha256 -cne $Native.Root -or
            $values.native_row_count -ne $Native.RowCount -or $values.native_total_bytes -ne $Native.TotalBytes -or
            $values.notice_path_count -ne $RuntimeNoticeCount -or $values.notice_path_root_sha256 -cne $RuntimeNoticeRoot -or
            $values.stage_content_root_sha256 -cne $StageContentRoot -or $values.project_row_count -ne $P0FileCount -or
            $values.project_total_bytes -ne $P0TotalBytes -or $values.runtime_row_count -ne $RuntimeFileCount -or
            $values.runtime_total_bytes -ne $RuntimeTotalBytes -or $values.stage_content_row_count -ne $StageContentFileCount -or
            $values.stage_content_total_bytes -ne $StageContentTotalBytes -or $values.stage_payload_sha256 -cne $StageScriptSha -or
            $values.verify_stage_sha256 -cne $VerifyScriptSha -or $values.native_script_sha256 -cne $NativeScriptSha -or
            $Native.Producer -cne $values.native_script_sha256 -or $Native.Verifier -cne $values.native_script_sha256){Stop-P1A 4 'stage receipt cross-binding mismatch'}
        $canonical=Build-StageReceipt $values
        if($Snapshot.Text -cne $canonical){Stop-P1A 4 'stage receipt is not canonical'}
    }finally{$document.Dispose()}
}

function Build-StageReceipt {
    param([Collections.Specialized.OrderedDictionary]$V)
    return '{"schema":1,"version":1,"algorithm":"SHA-256","project_manifest_sha256":"'+$V.project_manifest_sha256+'","runtime_manifest_sha256":"'+$V.runtime_manifest_sha256+'","native_receipt_sha256":"'+$V.native_receipt_sha256+'","project_root_sha256":"'+$V.project_root_sha256+'","runtime_root_sha256":"'+$V.runtime_root_sha256+'","native_closure_root_sha256":"'+$V.native_closure_root_sha256+'","native_row_count":'+$V.native_row_count.ToString($Invariant)+',"native_total_bytes":'+$V.native_total_bytes.ToString($Invariant)+',"notice_path_count":'+$V.notice_path_count.ToString($Invariant)+',"notice_path_root_sha256":"'+$V.notice_path_root_sha256+'","stage_content_root_sha256":"'+$V.stage_content_root_sha256+'","project_row_count":'+$V.project_row_count.ToString($Invariant)+',"project_total_bytes":'+$V.project_total_bytes.ToString($Invariant)+',"runtime_row_count":'+$V.runtime_row_count.ToString($Invariant)+',"runtime_total_bytes":'+$V.runtime_total_bytes.ToString($Invariant)+',"stage_content_row_count":'+$V.stage_content_row_count.ToString($Invariant)+',"stage_content_total_bytes":'+$V.stage_content_total_bytes.ToString($Invariant)+',"stage_payload_sha256":"'+$V.stage_payload_sha256+'","verify_stage_sha256":"'+$V.verify_stage_sha256+'","native_script_sha256":"'+$V.native_script_sha256+'"}'
}

function Get-AllStageEntries {
    param([string]$Root)
    $files=[Collections.Generic.List[string]]::new();$directories=[Collections.Generic.List[string]]::new();$fold=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase);$queue=[Collections.Generic.Queue[object]]::new();$queue.Enqueue([pscustomobject]@{Directory=[IO.DirectoryInfo]::new($Root);Relative=''})
    while($queue.Count -gt 0){$node=$queue.Dequeue();Assert-PlainDirectoryInfo $node.Directory 'stage directory' 4;$children=@($node.Directory.EnumerateFileSystemInfos());$names=[string[]]@($children|ForEach-Object{$_.Name});[Array]::Sort($names,[StringComparer]::Ordinal);foreach($name in $names){$matches=@($children|Where-Object{$_.Name -ceq $name});if($matches.Count-ne1){Stop-P1A 4 'stage exact-name collision'};$item=$matches[0];if(Test-Reparse $item){Stop-P1A 4 'stage contains reparse point'};$relative=if($node.Relative -ceq ''){$item.Name}else{$node.Relative+'/'+$item.Name};Assert-StageRelativePath $relative 4;if(-not$fold.Add($relative)){Stop-P1A 4 'stage casefold collision'};if($item -is [IO.DirectoryInfo]){$directories.Add($relative);$queue.Enqueue([pscustomobject]@{Directory=[IO.DirectoryInfo]$item;Relative=$relative})}elseif($item -is [IO.FileInfo]){$files.Add($relative)}else{Stop-P1A 4 'stage contains nonregular item'}}}
    $fileArray=$files.ToArray();$directoryArray=$directories.ToArray();[Array]::Sort($fileArray,[StringComparer]::Ordinal);[Array]::Sort($directoryArray,[StringComparer]::Ordinal);return [pscustomobject]@{Files=$fileArray;Directories=$directoryArray}
}

function Assert-ExactStageMembership {
    param([string[]]$Actual,[string[]]$Expected)
    $expectedSorted=[string[]]$Expected.Clone();[Array]::Sort($expectedSorted,[StringComparer]::Ordinal)
    if($Actual.Count -ne $expectedSorted.Count){Stop-P1A 4 'stage membership count mismatch'}
    for($index=0;$index -lt $Actual.Count;$index++){if($Actual[$index] -cne $expectedSorted[$index]){Stop-P1A 4 'stage membership mismatch'}}
}

function Get-ExpectedStageDirectories {
    param([string[]]$Paths)
    $set=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach($path in $Paths){$slash=$path.LastIndexOf('/');while($slash-gt0){$parent=$path.Substring(0,$slash);$null=$set.Add($parent);$slash=$parent.LastIndexOf('/')}}
    $result=[string[]]@($set);[Array]::Sort($result,[StringComparer]::Ordinal);return $result
}

function Emit-Success { param([string]$SelectedPhase,[string]$StageHash) [Console]::Out.Write('{"schema":1,"status":"P1A_STAGE_VERIFIED","phase":"'+$SelectedPhase+'","stage_content_root_sha256":"'+$StageHash+'"}');exit 0 }
function Emit-Failure { param([int]$Code) $statuses=@('','','USAGE','INPUT_INVALID','STAGE_INVALID','POLICY_INVALID','RUNTIME_INVALID','NATIVE_INVALID','IO_CONFLICT','INTERNAL_ERROR');if($Code -lt 2 -or $Code -gt 9){$Code=9};[Console]::Out.Write('{"schema":1,"status":"'+$statuses[$Code]+'","detail_code":'+$Code.ToString($Invariant)+'}');exit $Code }

try{
    $parameters=Get-ExactInvocationMap $InvocationArguments @('StageRoot','ExpectedP0Root','ExpectedRuntimeFileCount','ExpectedRuntimeTotalBytes','ExpectedRuntimeDistInfoCount','ExpectedRuntimeNoticePathCount','ExpectedRuntimeNoticePathRoot','Phase')
    $StageRoot=$parameters['StageRoot'];$ExpectedP0Root=$parameters['ExpectedP0Root'];$ExpectedRuntimeFileCount=$parameters['ExpectedRuntimeFileCount'];$ExpectedRuntimeTotalBytes=$parameters['ExpectedRuntimeTotalBytes'];$ExpectedRuntimeDistInfoCount=$parameters['ExpectedRuntimeDistInfoCount'];$ExpectedRuntimeNoticePathCount=$parameters['ExpectedRuntimeNoticePathCount'];$ExpectedRuntimeNoticePathRoot=$parameters['ExpectedRuntimeNoticePathRoot'];$Phase=$parameters['Phase']
    foreach($required in @($StageRoot,$ExpectedP0Root,$ExpectedRuntimeFileCount,$ExpectedRuntimeTotalBytes,$ExpectedRuntimeDistInfoCount,$ExpectedRuntimeNoticePathCount,$ExpectedRuntimeNoticePathRoot,$Phase)){if([string]::IsNullOrEmpty($required)){Stop-P1A 2 'missing mandatory parameter'}}
    Assert-Sha256 $ExpectedP0Root 'ExpectedP0Root' 2;Assert-Sha256 $ExpectedRuntimeNoticePathRoot 'ExpectedRuntimeNoticePathRoot' 2
    $expectedFiles=Get-CanonicalInt64Argument $ExpectedRuntimeFileCount 'ExpectedRuntimeFileCount';$expectedBytes=Get-CanonicalInt64Argument $ExpectedRuntimeTotalBytes 'ExpectedRuntimeTotalBytes';$expectedDist=Get-CanonicalInt64Argument $ExpectedRuntimeDistInfoCount 'ExpectedRuntimeDistInfoCount';$expectedNotices=Get-CanonicalInt64Argument $ExpectedRuntimeNoticePathCount 'ExpectedRuntimeNoticePathCount'
    if($ExpectedP0Root -cne $P0Root -or $expectedFiles -ne $RuntimeFileCount -or $expectedBytes -ne $RuntimeTotalBytes -or $expectedDist -ne $RuntimeDistInfoCount -or $expectedNotices -ne $RuntimeNoticeCount -or $ExpectedRuntimeNoticePathRoot -cne $RuntimeNoticeRoot){Stop-P1A 3 'expected pins mismatch'}
    if($Phase -cne 'PreNative' -and $Phase -cne 'Final'){Stop-P1A 2 'invalid Phase'}
    $stage=Assert-AbsoluteExistingDirectory $StageRoot 'StageRoot'
    $stageScriptPath=[IO.Path]::Combine($PSScriptRoot,'stage_payload.ps1');$nativeScriptPath=[IO.Path]::Combine($PSScriptRoot,'verify_native_closure.ps1')
    $stageScript=Read-StableFile $stageScriptPath 'stage_payload.ps1' 4 16777216;$verifyScript=Read-StableFile $PSCommandPath 'verify_stage.ps1' 4 16777216;$nativeScript=Read-StableFile $nativeScriptPath 'verify_native_closure.ps1' 4 33554432
    $projectSnapshot=Read-StableJsonText (Resolve-ExactStageFile $stage $ProjectManifestPath) $ProjectManifestPath
    $runtimeSnapshot=Read-StableJsonText (Resolve-ExactStageFile $stage $RuntimeManifestPath) $RuntimeManifestPath
    $project=Parse-ProjectManifest $projectSnapshot $stageScript.Sha256;$runtime=Parse-RuntimeManifest $runtimeSnapshot $stageScript.Sha256
    $runtimeMap=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal);foreach($row in $runtime.Rows){$runtimeMap.Add($row.Path,$row)}
    foreach($row in @($project.Rows)+@($runtime.Rows)){$physical=Read-StableFile (Resolve-ExactStageFile $stage $row.Path) $row.Path 4;if($physical.Bytes -ne $row.Bytes -or $physical.Sha256 -cne $row.Sha256){Stop-P1A 4 "physical content mismatch $($row.Path)"}}
    $stagePreimage='project|29|2674489|'+$P0Root+"`r`n"+'runtime|15003|575844438|'+$runtime.Root;$stageContentRoot=ConvertTo-UpperSha256 ($StrictUtf8.GetBytes($stagePreimage))
    $expectedPaths=[Collections.Generic.List[string]]::new();foreach($row in $project.Rows){$expectedPaths.Add($row.Path)};foreach($row in $runtime.Rows){$expectedPaths.Add($row.Path)};$expectedPaths.Add($ProjectManifestPath);$expectedPaths.Add($RuntimeManifestPath)
    if($Phase -ceq 'Final'){
        $nativeSnapshot=Read-StableJsonText (Resolve-ExactStageFile $stage $NativeReceiptPath) $NativeReceiptPath
        $native=Parse-NativeReceipt $nativeSnapshot $runtimeSnapshot.Sha256 $nativeScript.Sha256 $runtimeMap
        $independentNative=Get-NativeClosure $stage $runtime.Rows
        Assert-NativeClosureMatchesReceipt $independentNative $native
        $stageReceiptSnapshot=Read-StableJsonText (Resolve-ExactStageFile $stage $StageReceiptPath) $StageReceiptPath
        Parse-StageReceipt $stageReceiptSnapshot $project $runtime $native $stageScript.Sha256 $verifyScript.Sha256 $nativeScript.Sha256 $stageContentRoot
        $expectedPaths.Add($NativeReceiptPath);$expectedPaths.Add($StageReceiptPath)
    }
    $actualEntries=Get-AllStageEntries $stage;Assert-ExactStageMembership $actualEntries.Files $expectedPaths.ToArray();Assert-ExactStageMembership $actualEntries.Directories (Get-ExpectedStageDirectories $expectedPaths.ToArray())
    $stageScriptEnd=Read-StableFile $stageScriptPath 'stage_payload.ps1' 4 16777216;$verifyScriptEnd=Read-StableFile $PSCommandPath 'verify_stage.ps1' 4 16777216;$nativeScriptEnd=Read-StableFile $nativeScriptPath 'verify_native_closure.ps1' 4 33554432
    if($stageScriptEnd.Bytes-ne$stageScript.Bytes-or$stageScriptEnd.Sha256-cne$stageScript.Sha256-or$verifyScriptEnd.Bytes-ne$verifyScript.Bytes-or$verifyScriptEnd.Sha256-cne$verifyScript.Sha256-or$nativeScriptEnd.Bytes-ne$nativeScript.Bytes-or$nativeScriptEnd.Sha256-cne$nativeScript.Sha256){Stop-P1A 4 'packaging script identity changed during verification'}
    Emit-Success $Phase $stageContentRoot
}catch{$code=9;if($null -ne $_.Exception -and $_.Exception.Data.Contains('P1AExit')){$code=[int]$_.Exception.Data['P1AExit']};Emit-Failure $code}
