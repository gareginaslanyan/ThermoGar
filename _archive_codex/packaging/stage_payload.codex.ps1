$InvocationArguments = [object[]]@($args)
$ProjectRoot = ''
$RuntimeSourceRoot = ''
$StageRoot = ''
$PolicyPath = ''
$ExpectedP0Root = ''
$ExpectedRuntimeFileCount = ''
$ExpectedRuntimeTotalBytes = ''
$ExpectedRuntimeDistInfoCount = ''
$ExpectedRuntimeNoticePathCount = ''
$ExpectedRuntimeNoticePathRoot = ''

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$InformationPreference = 'SilentlyContinue'
$VerbosePreference = 'SilentlyContinue'
$DebugPreference = 'SilentlyContinue'

$P0Root = '42455F51E284BAD35F5BFD4971F5099889A2A0D4518FFB95310FC5C400461F7F'
$P0FileCount = [int64]29
$P0TotalBytes = [int64]2674489
$RuntimeLiteralRoot = 'C:\Users\gareg\Documents\Codex\ThermoGar-Installer-Assets\runtime-clean-3119'
$RuntimeFileCount = [int64]15003
$RuntimeTotalBytes = [int64]575844438
$RuntimeDistInfoCount = [int64]99
$RuntimeNoticeCount = [int64]131
$RuntimeNoticeRoot = 'DAFF95A316054B509313B3F2BF296C38F00FC7EDAD1CC1C4D27DB0C4FD9B9266'
$RuntimeContentRootSha256 = '58F81C014DF3C3E8AA6F85517BCEE4263C0AE751365B53CA0ED197964538121C'
$StageContentFileCount = [int64]15032
$StageContentTotalBytes = [int64]578518927
$PolicyBytes = [int64]5630
$PolicySha256 = '3108686622C0D116653BC10E137ADF895F979E4960ECBA1FE4A3A2D580C436F5'
$PolicyVerifierBytes = [int64]16579
$PolicyVerifierSha256 = '01819A25BEB6D367E4F5DE87522F14A466B87F1250D4B68712A4EE72BCD99528'
$StrictUtf8 = [Text.UTF8Encoding]::new($false, $true)
$Invariant = [Globalization.CultureInfo]::InvariantCulture

if ($null -eq ('ThermoGar.P1AStageNative' -as [type])) {
    $null = Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;
namespace ThermoGar {
    [StructLayout(LayoutKind.Sequential)]
    public struct P1AStageFileInfo {
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
    public static class P1AStageNative {
        [DllImport("kernel32.dll", SetLastError=true)]
        public static extern bool GetFileInformationByHandle(
            SafeFileHandle handle, out P1AStageFileInfo info);

        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        public static extern SafeFileHandle CreateFileW(
            string fileName, uint desiredAccess, uint shareMode,
            IntPtr securityAttributes, uint creationDisposition,
            uint flagsAndAttributes, IntPtr templateFile);

        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        public static extern uint GetFinalPathNameByHandleW(
            SafeFileHandle handle, StringBuilder path,
            uint pathLength, uint flags);

        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        public static extern bool CreateDirectoryW(
            string path, IntPtr securityAttributes);
    }
}
'@
}

$CreatedStageDirectories = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)

function Stop-P1A {
    param([int]$Code, [string]$Message)
    $exception = [InvalidOperationException]::new($Message)
    $exception.Data['P1AExit'] = $Code
    throw $exception
}

function Get-ExactInvocationMap {
    param([object[]]$Tokens, [string[]]$AllowedNames)
    if ($Tokens.Count -ne ($AllowedNames.Count * 2)) { Stop-P1A 2 'wrong argument count' }
    $allowed = [Collections.Generic.HashSet[string]]::new($AllowedNames, [StringComparer]::Ordinal)
    $values = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    for ($index = 0; $index -lt $Tokens.Count; $index += 2) {
        $label = [string]$Tokens[$index]
        if (-not $label.StartsWith('-', [StringComparison]::Ordinal) -or $label.Length -lt 2) { Stop-P1A 2 'positional argument rejected' }
        $name = $label.Substring(1)
        if (-not $allowed.Contains($name) -or -not $values.TryAdd($name, [string]$Tokens[$index + 1])) { Stop-P1A 2 'unknown or duplicate argument' }
    }
    return $values
}

function Get-CanonicalInt64Argument {
    param([string]$Value, [string]$Name)
    if ([string]::IsNullOrEmpty($Value) -or $Value -cnotmatch '^(0|[1-9][0-9]*)$') {
        Stop-P1A 2 "invalid numeric argument $Name"
    }
    $parsed = [int64]0
    if (-not [int64]::TryParse($Value, [Globalization.NumberStyles]::None, $Invariant, [ref]$parsed)) {
        Stop-P1A 2 "invalid numeric argument $Name"
    }
    return $parsed
}

function Assert-Sha256 {
    param([string]$Value, [string]$Name, [int]$Code = 3)
    if ($Value -cnotmatch '^[A-F0-9]{64}$') { Stop-P1A $Code "invalid SHA-256 $Name" }
}

function Test-Reparse {
    param([IO.FileSystemInfo]$Item)
    return [bool]($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)
}

function Assert-PlainDirectoryInfo {
    param([IO.DirectoryInfo]$Item, [string]$Label, [int]$Code = 3)
    $Item.Refresh()
    if (-not $Item.Exists -or (Test-Reparse $Item)) { Stop-P1A $Code "$Label is not a plain directory" }
}

function Assert-PlainFileInfo {
    param([IO.FileInfo]$Item, [string]$Label, [int]$Code = 3)
    $Item.Refresh()
    if (-not $Item.Exists -or (Test-Reparse $Item)) { Stop-P1A $Code "$Label is not a plain regular file" }
}

function Resolve-ExactPlainDirectoryByHandle {
    param([string]$Path, [string]$Label, [int]$Code = 3)
    $fileReadAttributes = [uint32]0x00000080
    $fileShareReadWriteDelete = [uint32]0x00000007
    $openExisting = [uint32]3
    $fileFlagBackupSemantics = [uint32]0x02000000
    $fileFlagOpenReparsePoint = [uint32]0x00200000
    $directoryAttribute = [uint32][IO.FileAttributes]::Directory
    $reparseAttribute = [uint32][IO.FileAttributes]::ReparsePoint
    $handle = [ThermoGar.P1AStageNative]::CreateFileW(
        $Path, $fileReadAttributes, $fileShareReadWriteDelete, [IntPtr]::Zero,
        $openExisting, ($fileFlagBackupSemantics -bor $fileFlagOpenReparsePoint), [IntPtr]::Zero)
    $openError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    if ($null -eq $handle) { throw [InvalidOperationException]::new("$Label native directory handle invariant") }
    try {
        if ($handle.IsInvalid -or $handle.IsClosed) {
            Stop-P1A $Code "$Label directory handle open failed ($openError)"
        }
        $info = [ThermoGar.P1AStageFileInfo]::new()
        $informationOk = [ThermoGar.P1AStageNative]::GetFileInformationByHandle($handle, [ref]$info)
        $informationError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        if (-not $informationOk) { Stop-P1A $Code "$Label directory information failed ($informationError)" }
        if (($info.FileAttributes -band $directoryAttribute) -eq 0 -or
            ($info.FileAttributes -band $reparseAttribute) -ne 0) {
            Stop-P1A $Code "$Label is not a plain directory"
        }
        $builder = [Text.StringBuilder]::new(32768)
        $pathLength = [ThermoGar.P1AStageNative]::GetFinalPathNameByHandleW(
            $handle, $builder, [uint32]$builder.Capacity, [uint32]0)
        $pathError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        if ($pathLength -eq 0 -or $pathLength -ge [uint32]$builder.Capacity -or
            $pathLength -ne [uint32]$builder.Length) {
            Stop-P1A $Code "$Label canonical path query failed ($pathError)"
        }
        $observed = $builder.ToString()
        $dosPrefix = '\\?\'
        if (-not $observed.StartsWith($dosPrefix, [StringComparison]::Ordinal)) {
            Stop-P1A $Code "$Label canonical path is not DOS-qualified"
        }
        if ($observed.StartsWith('\\?\UNC\', [StringComparison]::OrdinalIgnoreCase)) {
            Stop-P1A $Code "$Label canonical path is not a DOS drive path"
        }
        $observed = $observed.Substring($dosPrefix.Length)
        if ($observed -cnotmatch '^[A-Za-z]:\\') { Stop-P1A $Code "$Label canonical path is not a DOS drive path" }
        if ($observed -cne $Path) { Stop-P1A $Code "$Label path casing or identity mismatch" }
        return $observed
    } finally {
        if ($null -ne $handle) { $handle.Dispose() }
    }
}

function Assert-AbsoluteExistingDirectory {
    param([string]$Path, [string]$Label, [int]$Code = 3, [switch]$AllowVolumeRoot)
    if ([string]::IsNullOrWhiteSpace($Path) -or $Path.StartsWith('\\', [StringComparison]::Ordinal) -or
        [Management.Automation.WildcardPattern]::ContainsWildcardCharacters($Path) -or
        -not [IO.Path]::IsPathFullyQualified($Path)) { Stop-P1A $Code "$Label is not canonical absolute" }
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    $isVolumeRoot = $full -ceq $root
    if ($full -cne $Path -or ($isVolumeRoot -and -not $AllowVolumeRoot.IsPresent)) { Stop-P1A $Code "$Label is not canonical absolute" }
    $current = Resolve-ExactPlainDirectoryByHandle $root "$Label root" $Code
    if ($isVolumeRoot) { return $current }
    $tail = $full.Substring($root.Length)
    foreach ($segment in $tail.Split([IO.Path]::DirectorySeparatorChar)) {
        if ([string]::IsNullOrEmpty($segment)) { Stop-P1A $Code "$Label contains an empty segment" }
        $current = Resolve-ExactPlainDirectoryByHandle ([IO.Path]::Combine($current, $segment)) $Label $Code
    }
    return $current
}

function Assert-AbsoluteAbsentStageRoot {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path) -or $Path.StartsWith('\\', [StringComparison]::Ordinal) -or
        [Management.Automation.WildcardPattern]::ContainsWildcardCharacters($Path) -or
        -not [IO.Path]::IsPathFullyQualified($Path)) { Stop-P1A 3 'StageRoot is not canonical absolute' }
    $full = [IO.Path]::GetFullPath($Path)
    if ($full -cne $Path -or $full -ceq [IO.Path]::GetPathRoot($full)) { Stop-P1A 3 'StageRoot is not canonical absolute' }
    if ([IO.Directory]::Exists($full) -or [IO.File]::Exists($full)) { Stop-P1A 8 'StageRoot already exists' }
    $leaf = [IO.Path]::GetFileName($full)
    if ([string]::IsNullOrEmpty($leaf) -or $leaf.EndsWith('.') -or $leaf.EndsWith(' ')) { Stop-P1A 3 'StageRoot leaf is invalid' }
    $parent = [IO.Path]::GetDirectoryName($full)
    $null = Assert-AbsoluteExistingDirectory $parent 'StageRoot parent' 3 -AllowVolumeRoot
    return $full
}

function Test-PathOverlap {
    param([string]$Left, [string]$Right)
    $a = $Left.TrimEnd([IO.Path]::DirectorySeparatorChar)
    $b = $Right.TrimEnd([IO.Path]::DirectorySeparatorChar)
    if ($a.Equals($b, [StringComparison]::OrdinalIgnoreCase)) { return $true }
    $ap = $a + [IO.Path]::DirectorySeparatorChar
    $bp = $b + [IO.Path]::DirectorySeparatorChar
    return $ap.StartsWith($bp, [StringComparison]::OrdinalIgnoreCase) -or $bp.StartsWith($ap, [StringComparison]::OrdinalIgnoreCase)
}

function Assert-StageRelativePath {
    param([string]$Path, [int]$Code = 4)
    if ([string]::IsNullOrEmpty($Path) -or $Path.StartsWith('/') -or $Path.EndsWith('/') -or
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
    $info = [ThermoGar.P1AStageFileInfo]::new()
    if (-not [ThermoGar.P1AStageNative]::GetFileInformationByHandle($Stream.SafeFileHandle, [ref]$info)) {
        Stop-P1A $Code 'cannot obtain file identity'
    }
    return '{0:X8}:{1:X8}{2:X8}' -f $info.VolumeSerialNumber, $info.FileIndexHigh, $info.FileIndexLow
}

function ConvertTo-UpperSha256 {
    param([byte[]]$Bytes)
    $hash = [Security.Cryptography.SHA256]::HashData($Bytes)
    return [Convert]::ToHexString($hash)
}

function Get-StableFileHashInfo {
    param([string]$Path, [string]$Label, [int]$Code)
    $before = [IO.FileInfo]::new($Path)
    Assert-PlainFileInfo $before $Label $Code
    $beforeLength = [int64]$before.Length
    $beforeTicks = [int64]$before.LastWriteTimeUtc.Ticks
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $identity = Get-HandleIdentity $stream $Code
        $length = [int64]$stream.Length
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $digest = [Convert]::ToHexString($sha.ComputeHash($stream)) } finally { $sha.Dispose() }
        $after = [IO.FileInfo]::new($Path)
        Assert-PlainFileInfo $after $Label $Code
        if ($length -ne $beforeLength -or $after.Length -ne $beforeLength -or
            $after.LastWriteTimeUtc.Ticks -ne $beforeTicks -or (Get-HandleIdentity $stream $Code) -cne $identity) {
            Stop-P1A $Code "unstable read $Label"
        }
        return [pscustomobject]@{ Bytes = $length; Sha256 = $digest; Identity = $identity; LastWriteTicks = $beforeTicks }
    } finally { $stream.Dispose() }
}

function Read-StableUtf8File {
    param([string]$Path, [string]$Label, [int]$Code, [int64]$MaximumBytes)
    $info = Get-StableFileHashInfo $Path $Label $Code
    if ($info.Bytes -gt $MaximumBytes) { Stop-P1A $Code "$Label is oversized" }
    $before = [IO.FileInfo]::new($Path)
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $identity = Get-HandleIdentity $stream $Code
        $memory = [IO.MemoryStream]::new()
        try { $stream.CopyTo($memory); $bytes = $memory.ToArray() } finally { $memory.Dispose() }
        $after = [IO.FileInfo]::new($Path)
        Assert-PlainFileInfo $after $Label $Code
        if ($before.Length -ne $after.Length -or $before.LastWriteTimeUtc.Ticks -ne $after.LastWriteTimeUtc.Ticks -or
            (Get-HandleIdentity $stream $Code) -cne $identity) { Stop-P1A $Code "unstable read $Label" }
    } finally { $stream.Dispose() }
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        Stop-P1A $Code "$Label has a UTF-8 BOM"
    }
    try { $text = $StrictUtf8.GetString($bytes) } catch { Stop-P1A $Code "$Label is not strict UTF-8" }
    $secondSha = ConvertTo-UpperSha256 $bytes
    if ($secondSha -cne $info.Sha256 -or $bytes.Length -ne $info.Bytes) { Stop-P1A $Code "$Label changed between stable reads" }
    return [pscustomobject]@{ Bytes = [int64]$bytes.Length; Sha256 = $secondSha; Text = $text; Raw = $bytes }
}

function Invoke-PinnedPolicyVerifier {
    param([string]$VerifierPath)
    $hostPath = [Environment]::ProcessPath
    $hostBefore = Get-StableFileHashInfo $hostPath 'PowerShell host' 5
    $verifierBefore = Get-StableFileHashInfo $VerifierPath 'payload policy verifier' 5
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $hostPath
    $start.UseShellExecute = $false
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.CreateNoWindow = $true
    foreach ($argument in @('-NoLogo','-NoProfile','-NonInteractive','-File',$VerifierPath)) { $start.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    try {
        if (-not $process.Start()) { Stop-P1A 5 'payload policy verifier did not start' }
        $stdout = $process.StandardOutput.ReadToEnd()
        $stderr = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        $exitCode = $process.ExitCode
    } finally { $process.Dispose() }
    if ($exitCode -ne 0 -or -not [string]::IsNullOrEmpty($stderr)) { Stop-P1A 5 'payload policy verifier rejected or contaminated output' }
    $hostAfter = Get-StableFileHashInfo $hostPath 'PowerShell host' 5
    $verifierAfter = Get-StableFileHashInfo $VerifierPath 'payload policy verifier' 5
    if ($hostBefore.Bytes -ne $hostAfter.Bytes -or $hostBefore.Sha256 -cne $hostAfter.Sha256 -or
        $verifierBefore.Bytes -ne $verifierAfter.Bytes -or $verifierBefore.Sha256 -cne $verifierAfter.Sha256) {
        Stop-P1A 5 'policy verification executable identity changed'
    }
    return $stdout.TrimEnd("`r", "`n")
}

function Resolve-ExactFileUnderRoot {
    param([string]$Root, [string]$RelativePath, [int]$Code)
    Assert-StageRelativePath $RelativePath $Code
    $current = [IO.DirectoryInfo]::new($Root)
    $segments = $RelativePath.Split('/')
    for ($index = 0; $index -lt $segments.Count; $index++) {
        $segment = $segments[$index]
        $matches = @($current.EnumerateFileSystemInfos() | Where-Object { $_.Name.Equals($segment, [StringComparison]::OrdinalIgnoreCase) })
        if ($matches.Count -ne 1 -or $matches[0].Name -cne $segment) { Stop-P1A $Code "missing, case-aliased, or colliding source $RelativePath" }
        if ($index -lt $segments.Count - 1) {
            if ($matches[0] -isnot [IO.DirectoryInfo]) { Stop-P1A $Code "non-directory source parent $RelativePath" }
            $current = [IO.DirectoryInfo]$matches[0]
            Assert-PlainDirectoryInfo $current $RelativePath $Code
        } else {
            if ($matches[0] -isnot [IO.FileInfo]) { Stop-P1A $Code "source is not a file $RelativePath" }
            $file = [IO.FileInfo]$matches[0]
            Assert-PlainFileInfo $file $RelativePath $Code
            $prefix = $Root.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
            if (-not $file.FullName.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { Stop-P1A $Code "source escapes root $RelativePath" }
            return $file.FullName
        }
    }
    Stop-P1A $Code "source resolution failed $RelativePath"
}

function Sort-RowsOrdinal {
    param([object[]]$Rows)
    $map = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
    $paths = [string[]]::new($Rows.Count)
    for ($index = 0; $index -lt $Rows.Count; $index++) { $paths[$index] = $Rows[$index].Path; $map.Add($Rows[$index].Path, $Rows[$index]) }
    [Array]::Sort($paths, [StringComparer]::Ordinal)
    $result = [Collections.Generic.List[object]]::new()
    foreach ($path in $paths) { $result.Add($map[$path]) }
    return $result.ToArray()
}

function Get-RowRoot {
    param([object[]]$Rows)
    $literals = [Collections.Generic.List[string]]::new()
    foreach ($row in $Rows) { $literals.Add(('{0}|{1}|{2}' -f $row.Path, ([int64]$row.Bytes).ToString($Invariant), $row.Sha256)) }
    return ConvertTo-UpperSha256 ($StrictUtf8.GetBytes([string]::Join("`r`n", $literals)))
}

function Get-PathListRoot {
    param([string[]]$Paths)
    return ConvertTo-UpperSha256 ($StrictUtf8.GetBytes([string]::Join("`r`n", $Paths)))
}

function Assert-NoJsonDuplicates {
    param([Text.Json.JsonElement]$Element, [string]$Location, [int]$Code)
    if ($Element.ValueKind -eq [Text.Json.JsonValueKind]::Object) {
        $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach ($property in $Element.EnumerateObject()) {
            if (-not $seen.Add($property.Name)) { Stop-P1A $Code "duplicate JSON property $Location.$($property.Name)" }
            Assert-NoJsonDuplicates $property.Value "$Location.$($property.Name)" $Code
        }
    } elseif ($Element.ValueKind -eq [Text.Json.JsonValueKind]::Array) {
        $index = 0
        foreach ($child in $Element.EnumerateArray()) { Assert-NoJsonDuplicates $child "$Location[$index]" $Code; $index++ }
    }
}

function Get-CanonicalJsonInt64 {
    param([Text.Json.JsonElement]$Element, [string]$Name, [int64]$Minimum, [int64]$Maximum, [int]$Code)
    if ($Element.ValueKind -ne [Text.Json.JsonValueKind]::Number) { Stop-P1A $Code "$Name is not a JSON Number" }
    $value = [int64]0
    if (-not $Element.TryGetInt64([ref]$value) -or $value -lt $Minimum -or $value -gt $Maximum) { Stop-P1A $Code "$Name is out of range" }
    $raw = $Element.GetRawText()
    if ($raw -cnotmatch '^(0|[1-9][0-9]*)$' -or $raw -cne $value.ToString($Invariant)) { Stop-P1A $Code "$Name is not canonical decimal" }
    return $value
}

function Get-PolicyRows {
    param([string]$Text)
    $options = [Text.Json.JsonDocumentOptions]::new()
    $options.AllowTrailingCommas = $false
    $options.CommentHandling = [Text.Json.JsonCommentHandling]::Disallow
    $document = $null
    try {
        $document = [Text.Json.JsonDocument]::Parse($Text, $options)
        Assert-NoJsonDuplicates $document.RootElement '$' 5
        $root = $document.RootElement
        if ($root.ValueKind -ne [Text.Json.JsonValueKind]::Object) { Stop-P1A 5 'policy root is not an object' }
        $rowsElement = [Text.Json.JsonElement]::new()
        if (-not $root.TryGetProperty('rows', [ref]$rowsElement) -or $rowsElement.ValueKind -ne [Text.Json.JsonValueKind]::Array) { Stop-P1A 5 'policy rows are absent' }
        $rows = [Collections.Generic.List[object]]::new()
        $exact = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        $fold = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        $index = 0
        foreach ($element in $rowsElement.EnumerateArray()) {
            if ($element.ValueKind -ne [Text.Json.JsonValueKind]::Object) { Stop-P1A 5 "policy row $index is not an object" }
            $names = @($element.EnumerateObject() | ForEach-Object { $_.Name })
            if ($names.Count -ne 3 -or -not ($names -ccontains 'path') -or -not ($names -ccontains 'bytes') -or -not ($names -ccontains 'sha256')) { Stop-P1A 5 "policy row $index keys mismatch" }
            $pathElement = [Text.Json.JsonElement]::new(); $bytesElement = [Text.Json.JsonElement]::new(); $shaElement = [Text.Json.JsonElement]::new()
            $null = $element.TryGetProperty('path', [ref]$pathElement); $null = $element.TryGetProperty('bytes', [ref]$bytesElement); $null = $element.TryGetProperty('sha256', [ref]$shaElement)
            if ($pathElement.ValueKind -ne [Text.Json.JsonValueKind]::String -or $shaElement.ValueKind -ne [Text.Json.JsonValueKind]::String) { Stop-P1A 5 "policy row $index string type mismatch" }
            $path = $pathElement.GetString(); $sha256 = $shaElement.GetString(); $bytes = Get-CanonicalJsonInt64 $bytesElement "policy.rows[$index].bytes" 0 ([int64]::MaxValue) 5
            Assert-StageRelativePath $path 5; Assert-Sha256 $sha256 "policy.rows[$index].sha256" 5
            if (-not $exact.Add($path) -or -not $fold.Add($path)) { Stop-P1A 5 "policy row path collision $path" }
            $rows.Add([pscustomobject]@{ Path = $path; Bytes = $bytes; Sha256 = $sha256 })
            $index++
        }
        return @(Sort-RowsOrdinal $rows.ToArray())
    } catch [Text.Json.JsonException] { Stop-P1A 5 'policy JSON is malformed' }
    finally { if ($null -ne $document) { $document.Dispose() } }
}

function Get-RuntimeInventory {
    param([string]$Root)
    $rows = [Collections.Generic.List[object]]::new()
    $fold = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $queue = [Collections.Generic.Queue[object]]::new()
    $queue.Enqueue([pscustomobject]@{ Directory = [IO.DirectoryInfo]::new($Root); Relative = '' })
    while ($queue.Count -gt 0) {
        $node = $queue.Dequeue()
        Assert-PlainDirectoryInfo $node.Directory 'runtime directory' 6
        $children = @($node.Directory.EnumerateFileSystemInfos())
        $names = [string[]]@($children | ForEach-Object { $_.Name })
        [Array]::Sort($names, [StringComparer]::Ordinal)
        foreach ($name in $names) {
            $matches = @($children | Where-Object { $_.Name -ceq $name })
            if ($matches.Count -ne 1) { Stop-P1A 6 'runtime directory name collision' }
            $item = $matches[0]
            if (Test-Reparse $item) { Stop-P1A 6 'runtime contains a reparse point' }
            $relative = if ($node.Relative -ceq '') { $item.Name } else { $node.Relative + '/' + $item.Name }
            $stagePath = 'runtime/' + $relative
            Assert-StageRelativePath $stagePath 6
            if ($item -is [IO.DirectoryInfo]) {
                $queue.Enqueue([pscustomobject]@{ Directory = [IO.DirectoryInfo]$item; Relative = $relative })
            } elseif ($item -is [IO.FileInfo]) {
                if (-not $fold.Add($stagePath)) { Stop-P1A 6 "runtime casefold collision $stagePath" }
                if ($stagePath -cmatch '(?i)(^|/)__pycache__(/|$)|\.(pyc|pyo)$') { Stop-P1A 6 "runtime contains forbidden cache bytecode $stagePath" }
                $hash = Get-StableFileHashInfo $item.FullName $stagePath 6
                $rows.Add([pscustomobject]@{ Path = $stagePath; Bytes = $hash.Bytes; Sha256 = $hash.Sha256; Source = $item.FullName })
            } else { Stop-P1A 6 'runtime contains a nonregular item' }
        }
    }
    return @(Sort-RowsOrdinal $rows.ToArray())
}

function Get-NoticePaths {
    param([object[]]$RuntimeRows)
    $paths = [Collections.Generic.List[string]]::new()
    foreach ($row in $RuntimeRows) {
        if ($row.Path.StartsWith('runtime/Lib/site-packages/', [StringComparison]::Ordinal)) {
            $leaf = $row.Path.Substring($row.Path.LastIndexOf('/') + 1)
            if ($leaf -cmatch '^(LICENSE|LICENCE|COPYING|NOTICE|NOTICES|COPYRIGHT|THIRD[-_ ]?PARTY)(\..+)?$') { $paths.Add($row.Path) }
        }
    }
    $array = $paths.ToArray(); [Array]::Sort($array, [StringComparer]::Ordinal)
    return $array
}

function Get-DistInfoCount {
    param([object[]]$RuntimeRows)
    $set = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($row in $RuntimeRows) {
        if ($row.Path -cmatch '^runtime/Lib/site-packages/([^/]+\.dist-info)(?:/.*)?$') { $null = $set.Add($Matches[1]) }
    }
    return [int64]$set.Count
}

function Ensure-StageDirectory {
    param([string]$Root, [string]$RelativeDirectory)
    if ([string]::IsNullOrEmpty($RelativeDirectory)) { return $Root }
    Assert-StageRelativePath $RelativeDirectory 8
    $current = $Root
    foreach ($segment in $RelativeDirectory.Split('/')) {
        $next = [IO.Path]::Combine($current, $segment)
        if ([IO.File]::Exists($next)) { Stop-P1A 8 'destination parent collision' }
        if (-not [IO.Directory]::Exists($next)) {
            if (-not [ThermoGar.P1AStageNative]::CreateDirectoryW($next, [IntPtr]::Zero)) {
                Stop-P1A 8 'destination directory create-new failed'
            }
            if (-not $CreatedStageDirectories.Add($next)) { Stop-P1A 8 'destination directory ownership collision' }
        } elseif (-not $CreatedStageDirectories.Contains($next)) {
            Stop-P1A 8 'destination directory pre-existed this invocation'
        }
        $directory = [IO.DirectoryInfo]::new($next)
        Assert-PlainDirectoryInfo $directory 'stage destination directory' 8
        if ($directory.Name -cne $segment) { Stop-P1A 8 'destination directory casing mismatch' }
        $current = $directory.FullName
    }
    return $current
}

function Copy-StableFileCreateNew {
    param([string]$Source, [string]$Destination, [object]$Expected, [int]$SourceCode)
    if ([IO.File]::Exists($Destination) -or [IO.Directory]::Exists($Destination)) { Stop-P1A 8 'destination collision' }
    $before = [IO.FileInfo]::new($Source); Assert-PlainFileInfo $before $Expected.Path $SourceCode
    $sourceStream = [IO.FileStream]::new($Source, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $destinationStream = $null
    try {
        $sourceIdentity = Get-HandleIdentity $sourceStream $SourceCode
        if ($sourceStream.Length -ne $Expected.Bytes) { Stop-P1A $SourceCode "source length changed $($Expected.Path)" }
        try { $destinationStream = [IO.FileStream]::new($Destination, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None) }
        catch [IO.IOException] { Stop-P1A 8 'destination create-new collision' }
        $incremental = [Security.Cryptography.IncrementalHash]::CreateHash([Security.Cryptography.HashAlgorithmName]::SHA256)
        try {
            $buffer = [byte[]]::new(1048576)
            while (($read = $sourceStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $incremental.AppendData($buffer, 0, $read)
                $destinationStream.Write($buffer, 0, $read)
            }
            $destinationStream.Flush($true)
            $sourceSha = [Convert]::ToHexString($incremental.GetHashAndReset())
        } finally { $incremental.Dispose() }
        $after = [IO.FileInfo]::new($Source); Assert-PlainFileInfo $after $Expected.Path $SourceCode
        if ($after.Length -ne $before.Length -or $after.LastWriteTimeUtc.Ticks -ne $before.LastWriteTimeUtc.Ticks -or
            (Get-HandleIdentity $sourceStream $SourceCode) -cne $sourceIdentity -or $sourceSha -cne $Expected.Sha256) {
            Stop-P1A $SourceCode "unstable or mismatched source $($Expected.Path)"
        }
    } finally {
        if ($null -ne $destinationStream) { $destinationStream.Dispose() }
        $sourceStream.Dispose()
    }
    $destinationInfo = Get-StableFileHashInfo $Destination $Expected.Path 4
    if ($destinationInfo.Bytes -ne $Expected.Bytes -or $destinationInfo.Sha256 -cne $Expected.Sha256) { Stop-P1A 4 "destination mismatch $($Expected.Path)" }
}

function Quote-Json {
    param([string]$Value)
    return [Text.Json.JsonSerializer]::Serialize([object][string]$Value, [type][string], [Text.Json.JsonSerializerOptions]$null)
}

function Build-ContentManifestRowsJson {
    param([object[]]$Rows)
    $items = [Collections.Generic.List[string]]::new()
    foreach ($row in $Rows) {
        $items.Add('{"path":' + (Quote-Json $row.Path) + ',"bytes":' + ([int64]$row.Bytes).ToString($Invariant) + ',"sha256":' + (Quote-Json $row.Sha256) + '}')
    }
    return [string]::Join(',', $items)
}

function Build-ProjectManifest {
    param([object[]]$Rows, [string]$Producer)
    return '{"schema":1,"version":1,"algorithm":"SHA-256","namespace":"stage-root","rows":[' +
        (Build-ContentManifestRowsJson $Rows) + '],"row_count":29,"total_bytes":2674489,"project_root_sha256":"' +
        $P0Root + '","producer_sha256":"' + $Producer + '"}'
}

function Build-RuntimeManifest {
    param([object[]]$Rows, [string[]]$NoticePaths, [string]$RuntimeRoot, [string]$Producer)
    $noticeJson = [Collections.Generic.List[string]]::new()
    foreach ($path in $NoticePaths) { $noticeJson.Add((Quote-Json $path)) }
    return '{"schema":1,"version":1,"algorithm":"SHA-256","namespace":"stage-root","rows":[' +
        (Build-ContentManifestRowsJson $Rows) + '],"row_count":15003,"total_bytes":575844438,"dist_info_count":99,"notice_paths":[' +
        [string]::Join(',', $noticeJson) + '],"notice_path_count":131,"notice_path_root_sha256":"' + $RuntimeNoticeRoot +
        '","runtime_root_sha256":"' + $RuntimeRoot + '","producer_sha256":"' + $Producer + '"}'
}

function Publish-AtomicCreateOnlyUtf8 {
    param([string]$Destination, [string]$Text)
    if ([IO.File]::Exists($Destination) -or [IO.Directory]::Exists($Destination)) { Stop-P1A 8 'metadata destination collision' }
    $directory = [IO.Path]::GetDirectoryName($Destination)
    $temporary = [IO.Path]::Combine($directory, '.' + [IO.Path]::GetFileName($Destination) + '.' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $bytes = $StrictUtf8.GetBytes($Text)
    $stream = $null
    try {
        $stream = [IO.FileStream]::new($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true); $stream.Dispose(); $stream = $null
        [IO.File]::Move($temporary, $Destination, $false)
    } catch [IO.IOException] { Stop-P1A 8 'atomic create-only publication failed' }
    finally { if ($null -ne $stream) { $stream.Dispose() } }
    $observed = Read-StableUtf8File $Destination 'published metadata' 4 ([int64]16777216)
    if ($observed.Text -cne $Text -or $observed.Bytes -ne $bytes.Length) { Stop-P1A 4 'published metadata mismatch' }
}

function Emit-Success {
    param([string]$ProjectHash, [string]$RuntimeHash, [string]$StageHash)
    [Console]::Out.Write('{"schema":1,"status":"P1A_STAGE_CREATED","project_root_sha256":"' + $ProjectHash +
        '","runtime_root_sha256":"' + $RuntimeHash + '","stage_content_root_sha256":"' + $StageHash + '"}')
    exit 0
}

function Emit-Failure {
    param([int]$Code)
    $statuses = @('', '', 'USAGE', 'INPUT_INVALID', 'STAGE_INVALID', 'POLICY_INVALID', 'RUNTIME_INVALID', 'NATIVE_INVALID', 'IO_CONFLICT', 'INTERNAL_ERROR')
    if ($Code -lt 2 -or $Code -gt 9) { $Code = 9 }
    [Console]::Out.Write('{"schema":1,"status":"' + $statuses[$Code] + '","detail_code":' + $Code.ToString($Invariant) + '}')
    exit $Code
}

try {
    $parameters = Get-ExactInvocationMap $InvocationArguments @('ProjectRoot','RuntimeSourceRoot','StageRoot','PolicyPath','ExpectedP0Root','ExpectedRuntimeFileCount','ExpectedRuntimeTotalBytes','ExpectedRuntimeDistInfoCount','ExpectedRuntimeNoticePathCount','ExpectedRuntimeNoticePathRoot')
    $ProjectRoot=$parameters['ProjectRoot'];$RuntimeSourceRoot=$parameters['RuntimeSourceRoot'];$StageRoot=$parameters['StageRoot'];$PolicyPath=$parameters['PolicyPath'];$ExpectedP0Root=$parameters['ExpectedP0Root'];$ExpectedRuntimeFileCount=$parameters['ExpectedRuntimeFileCount'];$ExpectedRuntimeTotalBytes=$parameters['ExpectedRuntimeTotalBytes'];$ExpectedRuntimeDistInfoCount=$parameters['ExpectedRuntimeDistInfoCount'];$ExpectedRuntimeNoticePathCount=$parameters['ExpectedRuntimeNoticePathCount'];$ExpectedRuntimeNoticePathRoot=$parameters['ExpectedRuntimeNoticePathRoot']
    foreach ($required in @($ProjectRoot, $RuntimeSourceRoot, $StageRoot, $PolicyPath, $ExpectedP0Root,
            $ExpectedRuntimeFileCount, $ExpectedRuntimeTotalBytes, $ExpectedRuntimeDistInfoCount,
            $ExpectedRuntimeNoticePathCount, $ExpectedRuntimeNoticePathRoot)) {
        if ([string]::IsNullOrEmpty($required)) { Stop-P1A 2 'missing mandatory parameter' }
    }
    Assert-Sha256 $ExpectedP0Root 'ExpectedP0Root' 2
    Assert-Sha256 $ExpectedRuntimeNoticePathRoot 'ExpectedRuntimeNoticePathRoot' 2
    $expectedFiles = Get-CanonicalInt64Argument $ExpectedRuntimeFileCount 'ExpectedRuntimeFileCount'
    $expectedBytes = Get-CanonicalInt64Argument $ExpectedRuntimeTotalBytes 'ExpectedRuntimeTotalBytes'
    $expectedDistInfo = Get-CanonicalInt64Argument $ExpectedRuntimeDistInfoCount 'ExpectedRuntimeDistInfoCount'
    $expectedNotices = Get-CanonicalInt64Argument $ExpectedRuntimeNoticePathCount 'ExpectedRuntimeNoticePathCount'
    if ($ExpectedP0Root -cne $P0Root -or $expectedFiles -ne $RuntimeFileCount -or $expectedBytes -ne $RuntimeTotalBytes -or
        $expectedDistInfo -ne $RuntimeDistInfoCount -or $expectedNotices -ne $RuntimeNoticeCount -or
        $ExpectedRuntimeNoticePathRoot -cne $RuntimeNoticeRoot) { Stop-P1A 3 'expected input pins mismatch' }

    $stageScriptStart = Get-StableFileHashInfo $PSCommandPath 'stage_payload.ps1' 4

    $project = Assert-AbsoluteExistingDirectory $ProjectRoot 'ProjectRoot' 3
    $runtimeSource = Assert-AbsoluteExistingDirectory $RuntimeSourceRoot 'RuntimeSourceRoot' 3
    $stage = Assert-AbsoluteAbsentStageRoot $StageRoot
    $scriptProjectRoot = [IO.Directory]::GetParent($PSScriptRoot).FullName
    if ($project -cne $scriptProjectRoot -or $runtimeSource -cne $RuntimeLiteralRoot) { Stop-P1A 3 'source roots are not canonical' }
    if ((Test-PathOverlap $stage $project) -or (Test-PathOverlap $stage $runtimeSource) -or (Test-PathOverlap $project $runtimeSource)) {
        Stop-P1A 3 'source and stage roots overlap'
    }

    $canonicalPolicyPath = [IO.Path]::Combine($project, 'packaging', 'payload-policy.json')
    if ([IO.Path]::GetFullPath($PolicyPath) -cne $PolicyPath -or $PolicyPath -cne $canonicalPolicyPath) { Stop-P1A 5 'PolicyPath is not canonical' }
    $policyFile = Resolve-ExactFileUnderRoot $project 'packaging/payload-policy.json' 5
    if ($policyFile -cne $PolicyPath) { Stop-P1A 5 'PolicyPath casing mismatch' }
    $policy = Read-StableUtf8File $policyFile 'payload policy' 5 1048576
    if ($policy.Bytes -ne $PolicyBytes -or $policy.Sha256 -cne $PolicySha256) { Stop-P1A 5 'payload policy identity mismatch' }

    $policyVerifierPath = Resolve-ExactFileUnderRoot $project 'packaging/verify_payload_policy.ps1' 5
    $policyVerifier = Get-StableFileHashInfo $policyVerifierPath 'payload policy verifier' 5
    if ($policyVerifier.Bytes -ne $PolicyVerifierBytes -or $policyVerifier.Sha256 -cne $PolicyVerifierSha256) { Stop-P1A 5 'payload policy verifier identity mismatch' }
    $p0Output = Invoke-PinnedPolicyVerifier $policyVerifierPath
    $expectedP0Output = '{"schema":1,"status":"P0_PAYLOAD_POLICY_VERIFIED","row_count":29,"total_bytes":2674489,"root_sha256":"' + $P0Root + '","entrypoint":"app/ThermoGar_app.py"}'
    if ($p0Output -cne $expectedP0Output) { Stop-P1A 5 'payload policy verifier result mismatch' }

    $projectRows = @(Get-PolicyRows $policy.Text)
    if ($projectRows.Count -ne $P0FileCount) { Stop-P1A 5 'P0 row count mismatch' }
    $projectTotal = [int64]0
    foreach ($row in $projectRows) { $projectTotal += [int64]$row.Bytes }
    if ($projectTotal -ne $P0TotalBytes -or (Get-RowRoot $projectRows) -cne $P0Root) { Stop-P1A 5 'P0 row root mismatch' }

    $projectSources = [Collections.Generic.List[object]]::new()
    foreach ($row in $projectRows) {
        $source = Resolve-ExactFileUnderRoot $project $row.Path 5
        $hash = Get-StableFileHashInfo $source $row.Path 5
        if ($hash.Bytes -ne $row.Bytes -or $hash.Sha256 -cne $row.Sha256) { Stop-P1A 5 "P0 source mismatch $($row.Path)" }
        $projectSources.Add([pscustomobject]@{ Path = $row.Path; Bytes = $row.Bytes; Sha256 = $row.Sha256; Source = $source })
    }

    $runtimeRows = @(Get-RuntimeInventory $runtimeSource)
    $runtimeTotal = [int64]0
    foreach ($row in $runtimeRows) { $runtimeTotal += [int64]$row.Bytes }
    $notices = [string[]]@(Get-NoticePaths $runtimeRows)
    $distInfoCount = Get-DistInfoCount $runtimeRows
    $noticeRoot = Get-PathListRoot $notices
    if ($runtimeRows.Count -ne $RuntimeFileCount -or $runtimeTotal -ne $RuntimeTotalBytes -or
        $distInfoCount -ne $RuntimeDistInfoCount -or $notices.Count -ne $RuntimeNoticeCount -or $noticeRoot -cne $RuntimeNoticeRoot) {
        Stop-P1A 6 'runtime inventory/count/notice evidence mismatch'
    }
    $runtimeRoot = Get-RowRoot $runtimeRows
    if ($runtimeRoot -cne $RuntimeContentRootSha256) { Stop-P1A 6 'runtime content root mismatch' }

    if (-not [ThermoGar.P1AStageNative]::CreateDirectoryW($stage, [IntPtr]::Zero)) { Stop-P1A 8 'StageRoot create-new failed' }
    if (-not $CreatedStageDirectories.Add($stage)) { Stop-P1A 8 'StageRoot ownership collision' }
    $stageInfo = [IO.DirectoryInfo]::new($stage); Assert-PlainDirectoryInfo $stageInfo 'StageRoot' 8
    foreach ($row in $projectSources) {
        $parent = [IO.Path]::GetDirectoryName($row.Path.Replace('/', [IO.Path]::DirectorySeparatorChar))
        $destinationDirectory = Ensure-StageDirectory $stage (($parent -replace '\\', '/'))
        $destination = [IO.Path]::Combine($destinationDirectory, [IO.Path]::GetFileName($row.Path))
        Copy-StableFileCreateNew $row.Source $destination $row 5
    }
    foreach ($row in $runtimeRows) {
        $relativeNative = $row.Path.Replace('/', [IO.Path]::DirectorySeparatorChar)
        $parent = [IO.Path]::GetDirectoryName($relativeNative)
        $destinationDirectory = Ensure-StageDirectory $stage (($parent -replace '\\', '/'))
        $destination = [IO.Path]::Combine($destinationDirectory, [IO.Path]::GetFileName($relativeNative))
        Copy-StableFileCreateNew $row.Source $destination $row 6
    }

    $runtimePostRows = @(Get-RuntimeInventory $runtimeSource)
    if ($runtimePostRows.Count -ne $runtimeRows.Count) { Stop-P1A 6 'runtime membership changed during staging' }
    for ($index = 0; $index -lt $runtimeRows.Count; $index++) {
        if ($runtimePostRows[$index].Path -cne $runtimeRows[$index].Path -or
            $runtimePostRows[$index].Bytes -ne $runtimeRows[$index].Bytes -or
            $runtimePostRows[$index].Sha256 -cne $runtimeRows[$index].Sha256) {
            Stop-P1A 6 'runtime source changed during staging'
        }
    }

    $manifestsDirectory = Ensure-StageDirectory $stage 'manifests'
    $scriptIdentity = Get-StableFileHashInfo $PSCommandPath 'stage_payload.ps1' 4
    if ($scriptIdentity.Bytes -ne $stageScriptStart.Bytes -or $scriptIdentity.Sha256 -cne $stageScriptStart.Sha256) { Stop-P1A 4 'stage script identity changed' }
    $projectManifest = Build-ProjectManifest $projectRows $stageScriptStart.Sha256
    $runtimeManifest = Build-RuntimeManifest $runtimeRows $notices $runtimeRoot $stageScriptStart.Sha256
    Publish-AtomicCreateOnlyUtf8 ([IO.Path]::Combine($manifestsDirectory, 'project-source-manifest.json')) $projectManifest
    Publish-AtomicCreateOnlyUtf8 ([IO.Path]::Combine($manifestsDirectory, 'runtime-input-manifest.json')) $runtimeManifest

    $stageRootPreimage = 'project|29|2674489|' + $P0Root + "`r`n" + 'runtime|15003|575844438|' + $runtimeRoot
    $stageContentRoot = ConvertTo-UpperSha256 ($StrictUtf8.GetBytes($stageRootPreimage))
    $stageScriptEnd = Get-StableFileHashInfo $PSCommandPath 'stage_payload.ps1' 4
    if ($stageScriptEnd.Bytes -ne $stageScriptStart.Bytes -or $stageScriptEnd.Sha256 -cne $stageScriptStart.Sha256) { Stop-P1A 4 'stage script identity changed' }
    Emit-Success $P0Root $runtimeRoot $stageContentRoot
} catch {
    $code = 9
    if ($null -ne $_.Exception -and $_.Exception.Data.Contains('P1AExit')) { $code = [int]$_.Exception.Data['P1AExit'] }
    Emit-Failure $code
}
