$InvocationArguments = if (Test-Path variable:script:ThermoGarP3Arguments) { [object[]]$script:ThermoGarP3Arguments } else { [object[]]@($args) }
$Role = if (Test-Path variable:script:ThermoGarP3Role) { [string]$script:ThermoGarP3Role } else { 'VERIFY' }
$WrapperCommandPath = if (Test-Path variable:script:ThermoGarP3CommandPath) { [string]$script:ThermoGarP3CommandPath } else { $PSCommandPath }

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$InformationPreference = 'SilentlyContinue'
$VerbosePreference = 'SilentlyContinue'
$DebugPreference = 'SilentlyContinue'
$WarningPreference = 'SilentlyContinue'

$script:P3Invariant = [Globalization.CultureInfo]::InvariantCulture
$script:P3Utf8 = [Text.UTF8Encoding]::new($false, $true)
$script:P3Role = $Role
$script:P3CommandPath = $WrapperCommandPath
$script:P3P0Root = '42455F51E284BAD35F5BFD4971F5099889A2A0D4518FFB95310FC5C400461F7F'
$script:P3RuntimeCount = [int64]15003
$script:P3RuntimeBytes = [int64]575844438
$script:P3RuntimeRoot = '58F81C014DF3C3E8AA6F85517BCEE4263C0AE751365B53CA0ED197964538121C'
$script:P3RuntimeManifestSha = '76A87C3770F250A9044F3660218BE905EC27FD427C5861A0C5D58AC75B4D2761'
$script:P3LegacyNoticeCount = [int64]131
$script:P3LegacyNoticeRoot = 'DAFF95A316054B509313B3F2BF296C38F00FC7EDAD1CC1C4D27DB0C4FD9B9266'
$script:P3NoticeCount = [int64]147
$script:P3NoticeBytes = [int64]767009
$script:P3NativeReceiptSha = '1E1D080B48D1A280006025AC9CF64AD1BB536C54329FEFB56175940190324552'
$script:P3NativeRoot = 'A08EC90744637E0CFE3F7E72D8F4564F58D37C190704B660F4267AF02616604C'
$script:P3P1aReceiptSha = '255FD7DB4613E646E158713639EA83353D81F2283CD3E775093DB6189997209B'
$script:P3StagePayloadSha = '61DE75ECC631442788CBBBABF4D91BA401B01791741D3ECB4F5620CB21AC5D3E'
$script:P3VerifyStageSha = '87BC14D8EC220FA9ED99593C7C4D0D601F0658BAA1A6A815AA6AD77CBC6B09EE'
$script:P3NativeScriptSha = '502963F6669E109C51CAD2C1427B4751C049E37E8423CE9C6DE49768059657F1'
$script:P3TrustProducerSha = '762ABCDA551B6BE81B2728D5814E14EA0FB18B5ABC249E12DCD739D04CE779C0'
$script:P3TrustVerifierSha = 'B6FDCA5AFAC6E365818C127DB51DBE8E38824B6A60E84818998BDA3544DDBF79'
$script:P3HelperPins = [ordered]@{
    'launcher.pyw' = @([int64]65359, 'B45DAD87139667604E3C3F4AD8F0D2307E2B0D2C86D220736286498F3389FE0A')
    'stop.pyw' = @([int64]7430, 'AA2087AFF494FF007E4C12CFE0949BB62384A2251883D51765EA3D424D70A286')
    'healthcheck.py' = @([int64]38059, 'ABCDE7BDEFC84DE9E91CA62D6A64F07129B1796C298C4AD4BB9ECC894B9CDB67')
}
$script:P3ProductVersionBytes = [int64]586
$script:P3ProductVersionSha = '5FFD94AD3CC5A471211A8CC718540E5267D4F9DFA5E345035FBD5780587DF54D'
$script:P3ProductVersionText = '{"schema":1,"version":1,"display_name":"ThermoGar","description":"ThermoGar Research Desktop — RESEARCH SOFTWARE — NO EXPERIMENTAL VALIDATION","display_version":"0.2.0-ne02","vi_product_version":"0.2.0.0","app_stage":"SWR-NE02","release_policy_sha256":"E818F1AAA03B2218856E8F75EAD1D864C612B35F7528A7CC98EF6607288B2290","icon_source_png_bytes":435278,"icon_source_png_sha256":"FBC129AE038355C560FF5AACC84647250C89E2C909CDAED821BE73395FC4C8D4","icon_bytes":46084,"icon_sha256":"7D685F896D6BE7D3DB0E16E1B024F58B270F9C48F88C45002CFB2B6C56F38039","icon_sizes":[16,20,24,32,40,48,64,256]}'
$script:P3ReleasePolicyBytes = [int64]20419
$script:P3ReleasePolicySha = 'E818F1AAA03B2218856E8F75EAD1D864C612B35F7528A7CC98EF6607288B2290'
$script:P3IconBytes = [int64]46084
$script:P3IconSha = '7D685F896D6BE7D3DB0E16E1B024F58B270F9C48F88C45002CFB2B6C56F38039'
$script:P3BaseFileCount = [int64]15041
$script:P3BaseDirectoryCount = [int64]1462
$script:P3ExecutionCount = [int64]15035
$script:P3PayloadCount = [int64]15045
$script:P3FinalFileCount = [int64]15047
$script:P3FinalDirectoryCount = [int64]1464

function Stop-P3 {
    param([int]$Code, [string]$Detail)
    if ($Detail -cnotmatch '^[A-Z0-9_]{1,64}$') { $Detail = 'INTERNAL_CONTRACT' }
    $errorObject = [InvalidOperationException]::new($Detail)
    $errorObject.Data['P3Exit'] = $Code
    $errorObject.Data['P3Detail'] = $Detail
    throw $errorObject
}

function Emit-P3Failure {
    param([int]$Code, [string]$Detail)
    if ($Code -lt 2 -or $Code -gt 9) { $Code = 9; $Detail = 'INTERNAL_ERROR' }
    if ($script:P3Role -ceq 'VERIFY') {
        $statuses = @('','','USAGE','PIN_INVALID','TRUST_INVALID','STAGE_INVALID','SBOM_INVALID','NOTICES_INVALID','DISTRIBUTION_INVALID','INTERNAL_ERROR')
    } else {
        $statuses = @('','','USAGE','INPUT_INVALID','TRUST_INVALID','STAGE_INVALID','SOURCE_INVALID','SERIALIZATION_INVALID','IO_CONFLICT','INTERNAL_ERROR')
    }
    [Console]::Out.Write('{"schema":1,"status":"' + $statuses[$Code] + '","detail_code":"' + $Detail + '"}')
    exit $Code
}

function Assert-P3Sha {
    param([string]$Value, [string]$Detail = 'SHA_INVALID', [int]$Code = 3)
    if ($Value -cnotmatch '^[A-F0-9]{64}$') { Stop-P3 $Code $Detail }
}

function Get-P3HashBytes {
    param([byte[]]$Bytes)
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes))
}

function Get-P3CanonicalInt64 {
    param([string]$Value, [string]$Detail = 'INTEGER_INVALID')
    if ($Value -cnotmatch '^(0|[1-9][0-9]*)$') { Stop-P3 2 $Detail }
    $number = [int64]0
    if (-not [int64]::TryParse($Value, [Globalization.NumberStyles]::None, $script:P3Invariant, [ref]$number)) { Stop-P3 2 $Detail }
    return $number
}

function Get-P3InvocationMap {
    param([object[]]$Tokens, [string[]]$Allowed)
    if ($null -eq $Tokens) { $Tokens = [object[]]@() }
    if ($Tokens.Count -ne ($Allowed.Count * 2)) { Stop-P3 2 'ARGUMENT_COUNT' }
    $allowedSet = [Collections.Generic.HashSet[string]]::new($Allowed, [StringComparer]::Ordinal)
    $result = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    for ($index = 0; $index -lt $Tokens.Count; $index += 2) {
        $label = [string]$Tokens[$index]
        if (-not $label.StartsWith('-', [StringComparison]::Ordinal) -or $label.Length -lt 2) { Stop-P3 2 'POSITIONAL_ARGUMENT' }
        $name = $label.Substring(1)
        if (-not $allowedSet.Contains($name) -or -not $result.TryAdd($name, [string]$Tokens[$index + 1])) { Stop-P3 2 'UNKNOWN_ARGUMENT' }
    }
    foreach ($name in $Allowed) { if ([string]::IsNullOrEmpty($result[$name])) { Stop-P3 2 'EMPTY_ARGUMENT' } }
    return $result
}

function Assert-P3RelativePath {
    param([string]$Path, [int]$Code = 5, [string]$Detail = 'PATH_INVALID')
    if ([string]::IsNullOrEmpty($Path) -or $Path.Length -gt 2048 -or $Path.StartsWith('/') -or $Path.EndsWith('/') -or $Path.Contains('//') -or $Path.Contains('\') -or $Path.Contains(':') -or $Path.Contains('|') -or $Path -cmatch '[\x00-\x1F\x7F]') { Stop-P3 $Code $Detail }
    if ($Path.Normalize([Text.NormalizationForm]::FormC) -cne $Path) { Stop-P3 $Code $Detail }
    foreach ($part in $Path.Split('/')) { if ($part -ceq '.' -or $part -ceq '..' -or $part.EndsWith('.') -or $part.EndsWith(' ')) { Stop-P3 $Code $Detail } }
}

function Test-P3Reparse {
    param([IO.FileSystemInfo]$Item)
    return [bool]($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)
}

function Assert-P3PlainDirectoryInfo {
    param([IO.DirectoryInfo]$Item, [int]$Code = 5, [string]$Detail = 'DIRECTORY_INVALID')
    try{$Item.Refresh()}catch{Stop-P3 $Code $Detail}
    if (-not $Item.Exists -or (Test-P3Reparse $Item)) { Stop-P3 $Code $Detail }
}

function Assert-P3PlainFileInfo {
    param([IO.FileInfo]$Item, [int]$Code = 5, [string]$Detail = 'FILE_INVALID')
    try{$Item.Refresh()}catch{Stop-P3 $Code $Detail}
    if (-not $Item.Exists -or (Test-P3Reparse $Item)) { Stop-P3 $Code $Detail }
}

function Assert-P3AbsoluteDirectory {
    param([string]$Path, [int]$Code = 3, [string]$Detail = 'ROOT_INVALID')
    if ([string]::IsNullOrWhiteSpace($Path) -or $Path.StartsWith('\\', [StringComparison]::Ordinal) -or [Management.Automation.WildcardPattern]::ContainsWildcardCharacters($Path) -or -not [IO.Path]::IsPathFullyQualified($Path)) { Stop-P3 $Code $Detail }
    try{$full = [IO.Path]::GetFullPath($Path)}catch{Stop-P3 $Code $Detail}
    if ($full -cne $Path -or $full -ceq [IO.Path]::GetPathRoot($full)) { Stop-P3 $Code $Detail }
    $root = [IO.Path]::GetPathRoot($full)
    $current = [IO.DirectoryInfo]::new($root)
    Assert-P3PlainDirectoryInfo $current $Code $Detail
    foreach ($segment in $full.Substring($root.Length).Split([IO.Path]::DirectorySeparatorChar)) {
        if ([string]::IsNullOrEmpty($segment)) { continue }
        try { $children = @($current.EnumerateFileSystemInfos()) } catch { Stop-P3 $Code $Detail }
        $matches = @($children | Where-Object { $_.Name.Equals($segment, [StringComparison]::OrdinalIgnoreCase) })
        if ($matches.Count -ne 1 -or $matches[0].Name -cne $segment -or $matches[0] -isnot [IO.DirectoryInfo]) { Stop-P3 $Code $Detail }
        $current = [IO.DirectoryInfo]$matches[0]
        Assert-P3PlainDirectoryInfo $current $Code $Detail
    }
    return $current.FullName
}

function Assert-P3AbsoluteFile {
    param([string]$Path, [int]$Code = 3, [string]$Detail = 'SOURCE_PATH_INVALID')
    if ([string]::IsNullOrWhiteSpace($Path) -or $Path.StartsWith('\\', [StringComparison]::Ordinal) -or [Management.Automation.WildcardPattern]::ContainsWildcardCharacters($Path) -or -not [IO.Path]::IsPathFullyQualified($Path)) { Stop-P3 $Code $Detail }
    try{$full = [IO.Path]::GetFullPath($Path)}catch{Stop-P3 $Code $Detail}
    if ($full -cne $Path) { Stop-P3 $Code $Detail }
    $parent = Assert-P3AbsoluteDirectory ([IO.Path]::GetDirectoryName($full)) $Code $Detail
    try { $children = @(([IO.DirectoryInfo]::new($parent)).EnumerateFileSystemInfos()) } catch { Stop-P3 $Code $Detail }
    $matches = @($children | Where-Object { $_.Name.Equals([IO.Path]::GetFileName($full), [StringComparison]::OrdinalIgnoreCase) })
    if ($matches.Count -ne 1 -or $matches[0].Name -cne [IO.Path]::GetFileName($full) -or $matches[0] -isnot [IO.FileInfo]) { Stop-P3 $Code $Detail }
    Assert-P3PlainFileInfo ([IO.FileInfo]$matches[0]) $Code $Detail
    return ([IO.FileInfo]$matches[0]).FullName
}

function Resolve-P3ExactFile {
    param([string]$Root, [string]$Relative, [int]$Code = 5, [string]$Detail = 'STAGE_PATH_INVALID')
    Assert-P3RelativePath $Relative $Code $Detail
    $parts = $Relative.Split('/')
    $current = [IO.DirectoryInfo]::new($Root)
    for ($index = 0; $index -lt $parts.Count; $index++) {
        try { $children = @($current.EnumerateFileSystemInfos()) } catch { Stop-P3 $Code $Detail }
        $matches = @($children | Where-Object { $_.Name.Equals($parts[$index], [StringComparison]::OrdinalIgnoreCase) })
        if ($matches.Count -ne 1 -or $matches[0].Name -cne $parts[$index]) { Stop-P3 $Code $Detail }
        if ($index -lt ($parts.Count - 1)) {
            if ($matches[0] -isnot [IO.DirectoryInfo]) { Stop-P3 $Code $Detail }
            $current = [IO.DirectoryInfo]$matches[0]
            Assert-P3PlainDirectoryInfo $current $Code $Detail
        } else {
            if ($matches[0] -isnot [IO.FileInfo]) { Stop-P3 $Code $Detail }
            Assert-P3PlainFileInfo ([IO.FileInfo]$matches[0]) $Code $Detail
            return ([IO.FileInfo]$matches[0]).FullName
        }
    }
    Stop-P3 $Code $Detail
}

function Initialize-P3NativeTypes {
    if($null-ne('ThermoGar.P3FileInfo'-as[type])){return}
    $null=Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;
namespace ThermoGar {
  [StructLayout(LayoutKind.Sequential)] public struct P3FileInfo {
    public uint FileAttributes; public System.Runtime.InteropServices.ComTypes.FILETIME CreationTime;
    public System.Runtime.InteropServices.ComTypes.FILETIME LastAccessTime; public System.Runtime.InteropServices.ComTypes.FILETIME LastWriteTime;
    public uint VolumeSerialNumber; public uint FileSizeHigh; public uint FileSizeLow; public uint NumberOfLinks; public uint FileIndexHigh; public uint FileIndexLow;
  }
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] public struct P3StreamData {
    public long StreamSize; [MarshalAs(UnmanagedType.ByValTStr, SizeConst=296)] public string StreamName;
  }
  public static class P3Native {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern bool CreateDirectoryW(string path, IntPtr securityAttributes);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool GetFileInformationByHandle(SafeFileHandle h, out P3FileInfo info);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern uint GetFinalPathNameByHandle(SafeFileHandle h, StringBuilder path, uint length, uint flags);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern IntPtr FindFirstStreamW(string name, int level, out P3StreamData data, uint flags);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern bool FindNextStreamW(IntPtr handle, out P3StreamData data);
    [DllImport("kernel32.dll", SetLastError=true)] public static extern bool FindClose(IntPtr handle);
  }
}
'@
}

function Get-P3HandleIdentity {
    param([IO.FileStream]$Stream,[int]$Code,[string]$Detail)
    $info=[ThermoGar.P3FileInfo]::new();if(-not[ThermoGar.P3Native]::GetFileInformationByHandle($Stream.SafeFileHandle,[ref]$info)-or$info.NumberOfLinks-ne1){Stop-P3 $Code $Detail}
    $buffer=[Text.StringBuilder]::new(32768);$length=[ThermoGar.P3Native]::GetFinalPathNameByHandle($Stream.SafeFileHandle,$buffer,[uint32]$buffer.Capacity,[uint32]0);if($length-eq0-or$length-ge$buffer.Capacity){Stop-P3 $Code $Detail};$path=$buffer.ToString();if($path.StartsWith('\\?\UNC\',[StringComparison]::OrdinalIgnoreCase)){$path='\\'+$path.Substring(8)}elseif($path.StartsWith('\\?\',[StringComparison]::OrdinalIgnoreCase)){$path=$path.Substring(4)}
    return [pscustomobject]@{Key=('{0:X8}:{1:X8}{2:X8}'-f$info.VolumeSerialNumber,$info.FileIndexHigh,$info.FileIndexLow);Path=[IO.Path]::GetFullPath($path)}
}

function Assert-P3NoAlternateStreams {
    param([string]$Path,[int]$Code,[string]$Detail)
    $data=[ThermoGar.P3StreamData]::new();$handle=[ThermoGar.P3Native]::FindFirstStreamW($Path,0,[ref]$data,[uint32]0);if($handle-eq[IntPtr]::new(-1)){Stop-P3 $Code $Detail}
    try{$count=0;do{$count++;if($data.StreamName-cne'::$DATA'){Stop-P3 $Code $Detail};$next=[ThermoGar.P3StreamData]::new();$more=[ThermoGar.P3Native]::FindNextStreamW($handle,[ref]$next);if($more){$data=$next}}while($more);if([Runtime.InteropServices.Marshal]::GetLastWin32Error()-ne38-or$count-ne1){Stop-P3 $Code $Detail}}finally{$null=[ThermoGar.P3Native]::FindClose($handle)}
}

function Get-P3StableFile {
    param([string]$Path, [int]$Code = 5, [string]$Detail = 'FILE_UNSTABLE', [int64]$Maximum = [int64]::MaxValue, [bool]$IncludeRaw = $true)
    try{
    Initialize-P3NativeTypes
    $file = [IO.FileInfo]::new($Path)
    Assert-P3PlainFileInfo $file $Code $Detail
    Assert-P3NoAlternateStreams $file.FullName $Code $Detail
    if ($file.Length -gt $Maximum) { Stop-P3 $Code $Detail }
    $beforeLength = $file.Length
    $beforeTicks = $file.LastWriteTimeUtc.Ticks
    $firstRaw = $null
    $stream = [IO.FileStream]::new($file.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $firstIdentity=Get-P3HandleIdentity $stream $Code $Detail;if(-not$firstIdentity.Path.Equals($file.FullName,[StringComparison]::OrdinalIgnoreCase)){Stop-P3 $Code $Detail}
        if ($IncludeRaw) {
            $memory = [IO.MemoryStream]::new()
            try { $stream.CopyTo($memory); $firstRaw = $memory.ToArray() } finally { $memory.Dispose() }
            $firstSha = Get-P3HashBytes $firstRaw
        } else {
            $firstSha = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($stream))
        }
    } finally { $stream.Dispose() }
    $middle = [IO.FileInfo]::new($file.FullName); Assert-P3PlainFileInfo $middle $Code $Detail
    $stream2 = [IO.FileStream]::new($file.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try { $secondIdentity=Get-P3HandleIdentity $stream2 $Code $Detail;if(-not$secondIdentity.Path.Equals($file.FullName,[StringComparison]::OrdinalIgnoreCase)){Stop-P3 $Code $Detail};$secondSha = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($stream2)) } finally { $stream2.Dispose() }
    $after = [IO.FileInfo]::new($file.FullName); Assert-P3PlainFileInfo $after $Code $Detail
    Assert-P3NoAlternateStreams $file.FullName $Code $Detail
    if ($beforeLength -ne $middle.Length -or $beforeLength -ne $after.Length -or $beforeTicks -ne $middle.LastWriteTimeUtc.Ticks -or $beforeTicks -ne $after.LastWriteTimeUtc.Ticks -or $firstSha -cne $secondSha-or$firstIdentity.Key-cne$secondIdentity.Key) { Stop-P3 $Code $Detail }
    if ($IncludeRaw -and $firstRaw.LongLength -ne $beforeLength) { Stop-P3 $Code $Detail }
    return [pscustomobject]@{ Path=$file.FullName; Bytes=[int64]$beforeLength; Sha256=$firstSha; Raw=$firstRaw }
    }catch{
        $current=$_.Exception;while($null-ne$current){if($current.Data.Contains('P3Exit')){throw};$current=$current.InnerException}
        Stop-P3 $Code $Detail
    }
}

function Get-P3Utf8Snapshot {
    param([string]$Path, [int]$Code, [string]$Detail, [int64]$Maximum)
    $snapshot = Get-P3StableFile $Path $Code $Detail $Maximum $true
    if ($snapshot.Raw.Length -ge 3 -and $snapshot.Raw[0] -eq 0xEF -and $snapshot.Raw[1] -eq 0xBB -and $snapshot.Raw[2] -eq 0xBF) { Stop-P3 $Code $Detail }
    try { $text = $script:P3Utf8.GetString($snapshot.Raw) } catch { Stop-P3 $Code $Detail }
    if ($text.EndsWith("`r") -or $text.EndsWith("`n")) { Stop-P3 $Code $Detail }
    Add-Member -InputObject $snapshot -NotePropertyName Text -NotePropertyValue $text
    return $snapshot
}

function Quote-P3Json {
    param([AllowEmptyString()][string]$Value)
    $builder = [Text.StringBuilder]::new(); $null = $builder.Append('"')
    foreach ($character in $Value.ToCharArray()) {
        $number = [int][char]$character
        switch ($number) {
            8 { $null=$builder.Append('\b') }
            9 { $null=$builder.Append('\t') }
            10 { $null=$builder.Append('\n') }
            12 { $null=$builder.Append('\f') }
            13 { $null=$builder.Append('\r') }
            34 { $null=$builder.Append('\"') }
            92 { $null=$builder.Append('\\') }
            default { if ($number -lt 32) { $null=$builder.Append('\u'+$number.ToString('X4',$script:P3Invariant)) } else { $null=$builder.Append($character) } }
        }
    }
    $null=$builder.Append('"'); return $builder.ToString()
}

function Quote-P3RuntimeInputJson {
    param([AllowEmptyString()][string]$Value)
    return (Quote-P3Json $Value).Replace('+','\u002B')
}

function Open-P3Json {
    param([string]$Text, [int]$Code, [string]$Detail)
    $options = [Text.Json.JsonDocumentOptions]::new(); $options.AllowTrailingCommas=$false; $options.CommentHandling=[Text.Json.JsonCommentHandling]::Disallow; $options.MaxDepth=64
    try { return [Text.Json.JsonDocument]::Parse($Text,$options) } catch { Stop-P3 $Code $Detail }
}

function Assert-P3JsonDocument {
    param([string]$Text,[int]$Code,[string]$Detail)
    $document=Open-P3Json $Text $Code $Detail
    try{if($document.RootElement.ValueKind-ne[Text.Json.JsonValueKind]::Object){Stop-P3 $Code $Detail}}finally{$document.Dispose()}
}

function Assert-P3JsonKeys {
    param([Text.Json.JsonElement]$Object, [string[]]$Expected, [int]$Code, [string]$Detail)
    if ($Object.ValueKind -ne [Text.Json.JsonValueKind]::Object) { Stop-P3 $Code $Detail }
    $actual = [Collections.Generic.List[string]]::new(); $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach($property in $Object.EnumerateObject()){ if(-not$seen.Add($property.Name)){Stop-P3 $Code $Detail};$actual.Add($property.Name) }
    if($actual.Count-ne$Expected.Count){Stop-P3 $Code $Detail}
    for($i=0;$i-lt$Expected.Count;$i++){if($actual[$i]-cne$Expected[$i]){Stop-P3 $Code $Detail}}
}

function Get-P3Property {
    param([Text.Json.JsonElement]$Object,[string]$Name,[int]$Code,[string]$Detail)
    $value=[Text.Json.JsonElement]::new();if(-not$Object.TryGetProperty($Name,[ref]$value)){Stop-P3 $Code $Detail};return $value
}

function Get-P3JsonString {
    param([Text.Json.JsonElement]$Object,[string]$Name,[int]$Code,[string]$Detail)
    $value=Get-P3Property $Object $Name $Code $Detail;if($value.ValueKind-ne[Text.Json.JsonValueKind]::String){Stop-P3 $Code $Detail};return $value.GetString()
}

function Get-P3JsonInt {
    param([Text.Json.JsonElement]$Object,[string]$Name,[int]$Code,[string]$Detail)
    $value=Get-P3Property $Object $Name $Code $Detail;if($value.ValueKind-ne[Text.Json.JsonValueKind]::Number){Stop-P3 $Code $Detail};$number=[int64]0
    if(-not$value.TryGetInt64([ref]$number)-or$value.GetRawText()-cne$number.ToString($script:P3Invariant)-or$number-lt0){Stop-P3 $Code $Detail};return $number
}

function Get-P3JsonBool {
    param([Text.Json.JsonElement]$Object,[string]$Name,[int]$Code,[string]$Detail)
    $value=Get-P3Property $Object $Name $Code $Detail;if($value.ValueKind-eq[Text.Json.JsonValueKind]::True){return $true};if($value.ValueKind-eq[Text.Json.JsonValueKind]::False){return $false};Stop-P3 $Code $Detail
}

function Get-P3RowRoot {
    param([object[]]$Rows)
    $texts=[Collections.Generic.List[string]]::new();foreach($row in $Rows){$texts.Add($row.Path+'|'+([int64]$row.Bytes).ToString($script:P3Invariant)+'|'+$row.Sha256)}
    return Get-P3HashBytes ($script:P3Utf8.GetBytes(($texts -join "`r`n")))
}

function Get-P3ExpectedDirectories {
    param([string[]]$Paths)
    $set=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach($path in $Paths){$slash=$path.LastIndexOf('/');while($slash-gt0){$parent=$path.Substring(0,$slash);$null=$set.Add($parent);$slash=$parent.LastIndexOf('/')}}
    $array=[string[]]@($set);[Array]::Sort($array,[StringComparer]::Ordinal);return $array
}

function Get-P3Tree {
    param([string]$Root)
    $rows=[Collections.Generic.List[object]]::new();$dirs=[Collections.Generic.List[string]]::new();$fold=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $queue=[Collections.Generic.Queue[object]]::new();$queue.Enqueue([pscustomobject]@{Directory=[IO.DirectoryInfo]::new($Root);Relative=''})
    while($queue.Count-gt0){$node=$queue.Dequeue();Assert-P3PlainDirectoryInfo $node.Directory 5 'STAGE_REPARSE'
        try{$children=@($node.Directory.EnumerateFileSystemInfos())}catch{Stop-P3 5 'STAGE_ENUMERATION_FAILED'};$names=[string[]]@($children|ForEach-Object{$_.Name});[Array]::Sort($names,[StringComparer]::Ordinal)
        foreach($name in $names){$matches=@($children|Where-Object{$_.Name-ceq$name});if($matches.Count-ne1){Stop-P3 5 'STAGE_COLLISION'};$item=$matches[0]
            if(Test-P3Reparse $item){Stop-P3 5 'STAGE_REPARSE'};$relative=if($node.Relative-ceq''){$item.Name}else{$node.Relative+'/'+$item.Name};Assert-P3RelativePath $relative 5 'STAGE_PATH_INVALID'
            if(-not$fold.Add($relative)){Stop-P3 5 'STAGE_COLLISION'}
            if($item-is[IO.DirectoryInfo]){$dirs.Add($relative);$queue.Enqueue([pscustomobject]@{Directory=[IO.DirectoryInfo]$item;Relative=$relative})}
            elseif($item-is[IO.FileInfo]){$pin=Get-P3StableFile $item.FullName 5 'STAGE_FILE_UNSTABLE' ([int64]::MaxValue) $false;$rows.Add([pscustomobject]@{Path=$relative;Bytes=$pin.Bytes;Sha256=$pin.Sha256})}
            else{Stop-P3 5 'STAGE_NONREGULAR'}
        }
    }
    $rowArray=$rows.ToArray();[Array]::Sort($rowArray,[Collections.Generic.Comparer[object]]::Create([Comparison[object]]{param($a,$b)[StringComparer]::Ordinal.Compare($a.Path,$b.Path)}))
    $dirArray=$dirs.ToArray();[Array]::Sort($dirArray,[StringComparer]::Ordinal);return [pscustomobject]@{Rows=$rowArray;Directories=$dirArray}
}

function Assert-P3ExactDirectories {
    param([string[]]$Actual,[object[]]$Rows)
    $paths=[string[]]@($Rows|ForEach-Object{$_.Path});$expected=Get-P3ExpectedDirectories $paths
    if($Actual.Count-ne$expected.Count){Stop-P3 5 'DIRECTORY_COUNT'}
    for($i=0;$i-lt$expected.Count;$i++){if($Actual[$i]-cne$expected[$i]){Stop-P3 5 'DIRECTORY_MEMBERSHIP'}}
}

function Assert-P3NoForbiddenRows {
    param([object[]]$BaseRows,[Collections.Generic.Dictionary[string,object]]$RuntimeRows)
    $forbidden=[Collections.Generic.HashSet[string]]::new([string[]]@('.cache','cache','caches','tmp','temp','log','logs','backup','backups','.venv','venv','work','reports','report','notebooks','notebook','user_data','checkout','build','installer','installers','archive','archives'),[StringComparer]::OrdinalIgnoreCase)
    foreach($row in $BaseRows){
        $runtimeRow=$null;$isRuntime=$RuntimeRows.TryGetValue($row.Path,[ref]$runtimeRow);if($isRuntime){$isRuntime=$runtimeRow.Bytes-eq$row.Bytes-and$runtimeRow.Sha256-ceq$row.Sha256}
        $parts=$row.Path.Split('/')
        foreach($part in $parts){if($part.Equals('__pycache__',[StringComparison]::OrdinalIgnoreCase)){Stop-P3 5 'FORBIDDEN_PATH'};if(-not$isRuntime-and($forbidden.Contains($part)-or$part.Equals('test',[StringComparison]::OrdinalIgnoreCase)-or$part.Equals('tests',[StringComparison]::OrdinalIgnoreCase)-or$part.Equals('testing',[StringComparison]::OrdinalIgnoreCase)-or$part.Equals('template',[StringComparison]::OrdinalIgnoreCase)-or$part.Equals('templates',[StringComparison]::OrdinalIgnoreCase))){Stop-P3 5 'FORBIDDEN_PATH'}}
        $extension=[IO.Path]::GetExtension($row.Path);if($extension.Equals('.pyc',[StringComparison]::OrdinalIgnoreCase)-or$extension.Equals('.pyo',[StringComparison]::OrdinalIgnoreCase)){Stop-P3 5 'FORBIDDEN_PATH'}
    }
}

function Publish-P3CreateNew {
    param([string]$Path,[byte[]]$Bytes)
    if([IO.File]::Exists($Path)-or[IO.Directory]::Exists($Path)){Stop-P3 8 'OUTPUT_COLLISION'}
    $stream=$null
    try{$stream=[IO.FileStream]::new($Path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);$stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true)}catch{if($null-ne$stream){$stream.Dispose();$stream=$null};Stop-P3 8 'OUTPUT_WRITE'}finally{if($null-ne$stream){$stream.Dispose()}}
    $pin=Get-P3StableFile $Path 8 'OUTPUT_VERIFY' ([int64]$Bytes.LongLength) $false;if($pin.Bytes-ne$Bytes.LongLength-or$pin.Sha256-cne(Get-P3HashBytes $Bytes)){Stop-P3 8 'OUTPUT_VERIFY'}
    return $pin
}

function New-P3Directory {
    param([string]$Parent,[string]$Name)
    Assert-P3RelativePath $Name 8 'DIRECTORY_CREATE';if($Name.Contains('/')){Stop-P3 8 'DIRECTORY_CREATE'}
    try{$parentFull=[IO.Path]::GetFullPath($Parent);$child=[IO.Path]::GetFullPath([IO.Path]::Combine($parentFull,$Name))}catch{Stop-P3 8 'DIRECTORY_CREATE'}
    if($child-cne[IO.Path]::Combine($parentFull,$Name)){Stop-P3 8 'DIRECTORY_CREATE'}
    Initialize-P3NativeTypes
    try{$created=[ThermoGar.P3Native]::CreateDirectoryW($child,[IntPtr]::Zero)}catch{Stop-P3 8 'DIRECTORY_CREATE'}
    if(-not$created){$error=[Runtime.InteropServices.Marshal]::GetLastWin32Error();if($error-eq80-or$error-eq183){Stop-P3 8 'DIRECTORY_COLLISION'};Stop-P3 8 'DIRECTORY_CREATE'}
    $directory=[IO.DirectoryInfo]::new($child);Assert-P3PlainDirectoryInfo $directory 8 'DIRECTORY_CREATE';if($directory.FullName-cne$child){Stop-P3 8 'DIRECTORY_CREATE'};return $directory.FullName
}

function Read-P3ContentManifest {
    param([object]$Snapshot,[string]$Kind)
    $code=if($Kind-ceq'runtime'){4}else{4};$detail=if($Kind-ceq'runtime'){'RUNTIME_MANIFEST_INVALID'}else{'PROJECT_MANIFEST_INVALID'}
    $document=Open-P3Json $Snapshot.Text $code $detail
    try{
        $root=$document.RootElement
        $keys=if($Kind-ceq'runtime'){@('schema','version','algorithm','namespace','rows','row_count','total_bytes','dist_info_count','notice_paths','notice_path_count','notice_path_root_sha256','runtime_root_sha256','producer_sha256')}else{@('schema','version','algorithm','namespace','rows','row_count','total_bytes','project_root_sha256','producer_sha256')}
        Assert-P3JsonKeys $root $keys $code $detail
        if((Get-P3JsonInt $root 'schema' $code $detail)-ne1-or(Get-P3JsonInt $root 'version' $code $detail)-ne1-or(Get-P3JsonString $root 'algorithm' $code $detail)-cne'SHA-256'-or(Get-P3JsonString $root 'namespace' $code $detail)-cne'stage-root'){Stop-P3 $code $detail}
        $rowsElement=Get-P3Property $root 'rows' $code $detail;if($rowsElement.ValueKind-ne[Text.Json.JsonValueKind]::Array){Stop-P3 $code $detail}
        $rows=[Collections.Generic.List[object]]::new();$exact=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal);$fold=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase);$previous=$null;$total=[int64]0;$rowJson=[Collections.Generic.List[string]]::new()
        foreach($element in $rowsElement.EnumerateArray()){
            Assert-P3JsonKeys $element @('path','bytes','sha256') $code $detail;$path=Get-P3JsonString $element 'path' $code $detail;$bytes=Get-P3JsonInt $element 'bytes' $code $detail;$sha=Get-P3JsonString $element 'sha256' $code $detail
            Assert-P3RelativePath $path $code $detail;Assert-P3Sha $sha $detail $code
            if(-not$exact.Add($path)-or-not$fold.Add($path)-or($null-ne$previous-and[StringComparer]::Ordinal.Compare($previous,$path)-ge0)){Stop-P3 $code $detail}
            if($total-gt([int64]::MaxValue-$bytes)){Stop-P3 $code $detail};$total+=$bytes;$row=[pscustomobject]@{Path=$path;Bytes=$bytes;Sha256=$sha};$rows.Add($row);$quotedPath=if($Kind-ceq'runtime'){Quote-P3RuntimeInputJson $path}else{Quote-P3Json $path};$rowJson.Add('{"path":'+$quotedPath+',"bytes":'+$bytes.ToString($script:P3Invariant)+',"sha256":"'+$sha+'"}');$previous=$path
        }
        $declaredCount=Get-P3JsonInt $root 'row_count' $code $detail;$declaredBytes=Get-P3JsonInt $root 'total_bytes' $code $detail
        if($declaredCount-ne$rows.Count-or$declaredBytes-ne$total){Stop-P3 $code $detail}
        if($Kind-ceq'runtime'){
            $distCount=Get-P3JsonInt $root 'dist_info_count' $code $detail;$noticeElement=Get-P3Property $root 'notice_paths' $code $detail;if($noticeElement.ValueKind-ne[Text.Json.JsonValueKind]::Array){Stop-P3 $code $detail}
            $noticePaths=[Collections.Generic.List[string]]::new();$noticeJson=[Collections.Generic.List[string]]::new();$noticePrevious=$null
            foreach($item in $noticeElement.EnumerateArray()){if($item.ValueKind-ne[Text.Json.JsonValueKind]::String){Stop-P3 $code $detail};$path=$item.GetString();Assert-P3RelativePath $path $code $detail;if($null-ne$noticePrevious-and[StringComparer]::Ordinal.Compare($noticePrevious,$path)-ge0){Stop-P3 $code $detail};if(-not$exact.Contains($path)){Stop-P3 $code $detail};$noticePaths.Add($path);$noticeJson.Add((Quote-P3RuntimeInputJson $path));$noticePrevious=$path}
            $noticeCount=Get-P3JsonInt $root 'notice_path_count' $code $detail;$noticeRoot=Get-P3JsonString $root 'notice_path_root_sha256' $code $detail;$contentRoot=Get-P3JsonString $root 'runtime_root_sha256' $code $detail;$producer=Get-P3JsonString $root 'producer_sha256' $code $detail
            foreach($sha in @($noticeRoot,$contentRoot,$producer)){Assert-P3Sha $sha $detail $code}
            $noticeRootActual=Get-P3HashBytes ($script:P3Utf8.GetBytes(($noticePaths.ToArray()-join"`r`n")))
            if($declaredCount-ne$script:P3RuntimeCount-or$declaredBytes-ne$script:P3RuntimeBytes-or$distCount-ne99-or$noticeCount-ne$script:P3LegacyNoticeCount-or$noticePaths.Count-ne$script:P3LegacyNoticeCount-or$noticeRoot-cne$script:P3LegacyNoticeRoot-or$noticeRootActual-cne$noticeRoot-or$contentRoot-cne$script:P3RuntimeRoot-or$producer-cne$script:P3StagePayloadSha-or(Get-P3RowRoot $rows.ToArray())-cne$contentRoot){Stop-P3 $code $detail}
            $canonical='{"schema":1,"version":1,"algorithm":"SHA-256","namespace":"stage-root","rows":['+($rowJson.ToArray()-join',')+'],"row_count":15003,"total_bytes":575844438,"dist_info_count":99,"notice_paths":['+($noticeJson.ToArray()-join',')+'],"notice_path_count":131,"notice_path_root_sha256":"'+$noticeRoot+'","runtime_root_sha256":"'+$contentRoot+'","producer_sha256":"'+$producer+'"}'
            if($Snapshot.Text-cne$canonical){Stop-P3 $code $detail}
            $rowArray=$rows.ToArray();$rowMap=Get-P3RowMap -Rows $rowArray -Code $code -Detail $detail;$noticeArray=$noticePaths.ToArray()
            return [pscustomobject]@{Rows=$rowArray;RowMap=$rowMap;Paths=$exact;NoticePaths=$noticeArray;Root=$contentRoot;Count=$declaredCount;Bytes=$declaredBytes;Snapshot=$Snapshot}
        }else{
            $contentRoot=Get-P3JsonString $root 'project_root_sha256' $code $detail;$producer=Get-P3JsonString $root 'producer_sha256' $code $detail;Assert-P3Sha $contentRoot $detail $code;Assert-P3Sha $producer $detail $code
            if($declaredCount-ne29-or$declaredBytes-ne2674489-or$contentRoot-cne$script:P3P0Root-or$producer-cne$script:P3StagePayloadSha-or(Get-P3RowRoot $rows.ToArray())-cne$contentRoot){Stop-P3 $code $detail}
            $canonical='{"schema":1,"version":1,"algorithm":"SHA-256","namespace":"stage-root","rows":['+($rowJson.ToArray()-join',')+'],"row_count":29,"total_bytes":2674489,"project_root_sha256":"'+$contentRoot+'","producer_sha256":"'+$producer+'"}'
            if($Snapshot.Text-cne$canonical){Stop-P3 $code $detail}
            Assert-P3CriticalProjectRows $rows.ToArray()
            $rowArray=$rows.ToArray();$rowMap=Get-P3RowMap -Rows $rowArray -Code $code -Detail $detail
            return [pscustomobject]@{Rows=$rowArray;RowMap=$rowMap;Paths=$exact;Root=$contentRoot;Count=$declaredCount;Bytes=$declaredBytes;Snapshot=$Snapshot}
        }
    }finally{$document.Dispose()}
}

function Get-P3RowMap {
    param([object[]]$Rows,[int]$Code,[string]$Detail)
    $map=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal);foreach($row in $Rows){if(-not$map.TryAdd($row.Path,$row)){Stop-P3 $Code $Detail}};return $map
}

function Assert-P3CriticalProjectRows {
    param([object[]]$Rows)
    $pins=[ordered]@{
        'app/ThermoGar_app.py'=@([int64]430274,'7008975720C0EBFDF2D087BCAFE235437D17EC41BC75ED7202B0EBFD8D16A931')
        'app/thermogar_release_policy.py'=@($script:P3ReleasePolicyBytes,$script:P3ReleasePolicySha)
        'databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb'=@([int64]351241,'F9BDF21D434FBE78B5EF3F7F2DE69763FA40B81335CDC58889907D41C80CD717')
        'databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.passport.json'=@([int64]12393,'C818F3132840304EA38017CB7419790A290A1CA2E949B01E8954931AC8F17491')
        'databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb'=@([int64]568690,'236EC4D9B0540DE04E4E6305FAA208672F31FBDF45B2AE84E92F80BD98053612')
        'databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb'=@([int64]466074,'1882D841A337063E0585D261C690AE7E565838234E231E21B8541A5CB0DBA391')
        'databases/physical/original/physical_data_v103.pdb'=@([int64]28102,'4CF81C992B57263C50B370EA47EB0D5BB4F622CF23C18479BAB54267762F20BD')
    }
    $map=Get-P3RowMap $Rows 4 'PROJECT_MANIFEST_INVALID';foreach($path in $pins.Keys){if(-not$map.ContainsKey($path)-or$map[$path].Bytes-ne[long]$pins[$path][0]-or$map[$path].Sha256-cne[string]$pins[$path][1]){Stop-P3 4 'PROJECT_MANIFEST_INVALID'}}
}

function Assert-P3ReleasePolicy {
    param([string]$Stage)
    $snapshot=Get-P3StableFile (Resolve-P3ExactFile $Stage 'app/thermogar_release_policy.py' 4 'RELEASE_POLICY_INVALID') 4 'RELEASE_POLICY_INVALID' 65536 $true
    if($snapshot.Bytes-ne$script:P3ReleasePolicyBytes-or$snapshot.Sha256-cne$script:P3ReleasePolicySha){Stop-P3 4 'RELEASE_POLICY_INVALID'}
    try{$text=$script:P3Utf8.GetString($snapshot.Raw)}catch{Stop-P3 4 'RELEASE_POLICY_INVALID'}
    $assignments=[Text.RegularExpressions.Regex]::Matches($text,'(?m)^APP_(?:STAGE|VERSION)\b[^\r\n]*$')
    if($assignments.Count-ne2-or$assignments[0].Value-cne'APP_STAGE: Final = "SWR-NE02"'-or$assignments[1].Value-cne'APP_VERSION: Final = "0.2.0-ne02"'){Stop-P3 4 'RELEASE_POLICY_INVALID'}
}

function Read-P3TrustManifest {
    param([object]$Snapshot,[Collections.Generic.Dictionary[string,string]]$P)
    $document=Open-P3Json $Snapshot.Text 4 'TRUST_MANIFEST_INVALID'
    try{$root=$document.RootElement;Assert-P3JsonKeys $root @('schema','version','algorithm','p0_root_sha256','runtime_input_root_sha256','native_closure_root_sha256','rows','execution_root_sha256') 4 'TRUST_MANIFEST_INVALID'
        if((Get-P3JsonInt $root 'schema' 4 'TRUST_MANIFEST_INVALID')-ne1-or(Get-P3JsonInt $root 'version' 4 'TRUST_MANIFEST_INVALID')-ne1-or(Get-P3JsonString $root 'algorithm' 4 'TRUST_MANIFEST_INVALID')-cne'SHA-256'-or(Get-P3JsonString $root 'p0_root_sha256' 4 'TRUST_MANIFEST_INVALID')-cne$script:P3P0Root-or(Get-P3JsonString $root 'runtime_input_root_sha256' 4 'TRUST_MANIFEST_INVALID')-cne$script:P3RuntimeRoot-or(Get-P3JsonString $root 'native_closure_root_sha256' 4 'TRUST_MANIFEST_INVALID')-cne$script:P3NativeRoot){Stop-P3 4 'TRUST_MANIFEST_INVALID'}
        $elements=Get-P3Property $root 'rows' 4 'TRUST_MANIFEST_INVALID';if($elements.ValueKind-ne[Text.Json.JsonValueKind]::Array){Stop-P3 4 'TRUST_MANIFEST_INVALID'}
        $rows=[Collections.Generic.List[object]]::new();$json=[Collections.Generic.List[string]]::new();$fold=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase);$previous=$null
        foreach($element in $elements.EnumerateArray()){Assert-P3JsonKeys $element @('path','bytes','sha256') 4 'TRUST_MANIFEST_INVALID';$path=Get-P3JsonString $element 'path' 4 'TRUST_MANIFEST_INVALID';$bytes=Get-P3JsonInt $element 'bytes' 4 'TRUST_MANIFEST_INVALID';$sha=Get-P3JsonString $element 'sha256' 4 'TRUST_MANIFEST_INVALID';Assert-P3RelativePath $path 4 'TRUST_MANIFEST_INVALID';Assert-P3Sha $sha 'TRUST_MANIFEST_INVALID' 4;if(-not$fold.Add($path)-or($null-ne$previous-and[StringComparer]::Ordinal.Compare($previous,$path)-ge0)){Stop-P3 4 'TRUST_MANIFEST_INVALID'};$rows.Add([pscustomobject]@{Path=$path;Bytes=$bytes;Sha256=$sha});$json.Add('{"path":'+(Quote-P3Json $path)+',"bytes":'+$bytes.ToString($script:P3Invariant)+',"sha256":"'+$sha+'"}');$previous=$path}
        $executionRoot=Get-P3JsonString $root 'execution_root_sha256' 4 'TRUST_MANIFEST_INVALID';Assert-P3Sha $executionRoot 'TRUST_MANIFEST_INVALID' 4
        if($rows.Count-ne$script:P3ExecutionCount-or(Get-P3RowRoot $rows.ToArray())-cne$executionRoot-or$executionRoot-cne$P['ExpectedRuntimeTrustExecutionRootSha256']){Stop-P3 4 'TRUST_MANIFEST_INVALID'}
        $canonical='{"schema":1,"version":1,"algorithm":"SHA-256","p0_root_sha256":"'+$script:P3P0Root+'","runtime_input_root_sha256":"'+$script:P3RuntimeRoot+'","native_closure_root_sha256":"'+$script:P3NativeRoot+'","rows":['+($json.ToArray()-join',')+'],"execution_root_sha256":"'+$executionRoot+'"}'
        if($Snapshot.Text-cne$canonical){Stop-P3 4 'TRUST_MANIFEST_INVALID'}
        $map=Get-P3RowMap $rows.ToArray() 4 'TRUST_MANIFEST_INVALID';foreach($name in $script:P3HelperPins.Keys){if(-not$map.ContainsKey($name)-or$map[$name].Bytes-ne[long]$script:P3HelperPins[$name][0]-or$map[$name].Sha256-cne[string]$script:P3HelperPins[$name][1]){Stop-P3 4 'TRUST_HELPER_INVALID'}}
        $rowArray=$rows.ToArray()
        return [pscustomobject]@{Rows=$rowArray;Map=$map;Root=$executionRoot;Snapshot=$Snapshot}
    }finally{$document.Dispose()}
}

function Read-P3TrustReceipt {
    param([object]$Snapshot,[object]$Manifest,[Collections.Generic.Dictionary[string,string]]$P)
    $document=Open-P3Json $Snapshot.Text 4 'TRUST_RECEIPT_INVALID'
    try{$root=$document.RootElement;Assert-P3JsonKeys $root @('schema','version','algorithm','manifest_sha256','execution_root_sha256','row_count','total_bytes','producer_sha256','verifier_sha256') 4 'TRUST_RECEIPT_INVALID'
        $manifestSha=Get-P3JsonString $root 'manifest_sha256' 4 'TRUST_RECEIPT_INVALID';$executionRoot=Get-P3JsonString $root 'execution_root_sha256' 4 'TRUST_RECEIPT_INVALID';$rowCount=Get-P3JsonInt $root 'row_count' 4 'TRUST_RECEIPT_INVALID';$total=Get-P3JsonInt $root 'total_bytes' 4 'TRUST_RECEIPT_INVALID';$producer=Get-P3JsonString $root 'producer_sha256' 4 'TRUST_RECEIPT_INVALID';$verifier=Get-P3JsonString $root 'verifier_sha256' 4 'TRUST_RECEIPT_INVALID'
        $sum=[int64]0;foreach($row in $Manifest.Rows){if($sum-gt([int64]::MaxValue-$row.Bytes)){Stop-P3 4 'TRUST_RECEIPT_INVALID'};$sum+=$row.Bytes}
        if((Get-P3JsonInt $root 'schema' 4 'TRUST_RECEIPT_INVALID')-ne1-or(Get-P3JsonInt $root 'version' 4 'TRUST_RECEIPT_INVALID')-ne1-or(Get-P3JsonString $root 'algorithm' 4 'TRUST_RECEIPT_INVALID')-cne'SHA-256'-or$manifestSha-cne$Manifest.Snapshot.Sha256-or$manifestSha-cne$P['ExpectedRuntimeTrustManifestSha256']-or$executionRoot-cne$Manifest.Root-or$rowCount-ne$script:P3ExecutionCount-or$rowCount-ne(Get-P3CanonicalInt64 $P['ExpectedRuntimeTrustExecutionRowCount'])-or$total-ne$sum-or$producer-cne$script:P3TrustProducerSha-or$verifier-cne$script:P3TrustVerifierSha){Stop-P3 4 'TRUST_RECEIPT_INVALID'}
        $canonical='{"schema":1,"version":1,"algorithm":"SHA-256","manifest_sha256":"'+$manifestSha+'","execution_root_sha256":"'+$executionRoot+'","row_count":'+$rowCount.ToString($script:P3Invariant)+',"total_bytes":'+$total.ToString($script:P3Invariant)+',"producer_sha256":"'+$producer+'","verifier_sha256":"'+$verifier+'"}'
        if($Snapshot.Text-cne$canonical){Stop-P3 4 'TRUST_RECEIPT_INVALID'};return [pscustomobject]@{Total=$total;Snapshot=$Snapshot}
    }finally{$document.Dispose()}
}

function Assert-P3AncestorReceipts {
    param([string]$Stage,[Collections.Generic.Dictionary[string,string]]$P,[object]$Project,[object]$Runtime)
    $native=Get-P3Utf8Snapshot (Resolve-P3ExactFile $Stage 'manifests/native-closure-receipt.json' 4 'NATIVE_RECEIPT_INVALID') 4 'NATIVE_RECEIPT_INVALID' 2097152
    if($native.Sha256-cne$script:P3NativeReceiptSha-or$native.Sha256-cne$P['ExpectedNativeReceiptSha256']){Stop-P3 4 'NATIVE_RECEIPT_INVALID'}
    $nativeDoc=Open-P3Json $native.Text 4 'NATIVE_RECEIPT_INVALID';try{$root=$nativeDoc.RootElement;if((Get-P3JsonString $root 'runtime_input_manifest_sha256' 4 'NATIVE_RECEIPT_INVALID')-cne$Runtime.Snapshot.Sha256-or(Get-P3JsonInt $root 'row_count' 4 'NATIVE_RECEIPT_INVALID')-ne3142-or(Get-P3JsonInt $root 'total_bytes' 4 'NATIVE_RECEIPT_INVALID')-ne3224678344-or(Get-P3JsonString $root 'native_closure_root_sha256' 4 'NATIVE_RECEIPT_INVALID')-cne$script:P3NativeRoot-or(Get-P3JsonString $root 'producer_sha256' 4 'NATIVE_RECEIPT_INVALID')-cne$script:P3NativeScriptSha-or(Get-P3JsonString $root 'verifier_sha256' 4 'NATIVE_RECEIPT_INVALID')-cne$script:P3NativeScriptSha){Stop-P3 4 'NATIVE_RECEIPT_INVALID'}}finally{$nativeDoc.Dispose()}
    $p1a=Get-P3Utf8Snapshot (Resolve-P3ExactFile $Stage 'manifests/p1a-stage-receipt.json' 4 'P1A_RECEIPT_INVALID') 4 'P1A_RECEIPT_INVALID' 65536
    if($p1a.Sha256-cne$script:P3P1aReceiptSha-or$p1a.Sha256-cne$P['ExpectedP1aStageReceiptSha256']){Stop-P3 4 'P1A_RECEIPT_INVALID'}
    $p1aDoc=Open-P3Json $p1a.Text 4 'P1A_RECEIPT_INVALID';try{$root=$p1aDoc.RootElement;if((Get-P3JsonString $root 'project_manifest_sha256' 4 'P1A_RECEIPT_INVALID')-cne$Project.Snapshot.Sha256-or(Get-P3JsonString $root 'runtime_manifest_sha256' 4 'P1A_RECEIPT_INVALID')-cne$Runtime.Snapshot.Sha256-or(Get-P3JsonString $root 'native_receipt_sha256' 4 'P1A_RECEIPT_INVALID')-cne$native.Sha256-or(Get-P3JsonString $root 'project_root_sha256' 4 'P1A_RECEIPT_INVALID')-cne$script:P3P0Root-or(Get-P3JsonString $root 'runtime_root_sha256' 4 'P1A_RECEIPT_INVALID')-cne$script:P3RuntimeRoot-or(Get-P3JsonString $root 'native_closure_root_sha256' 4 'P1A_RECEIPT_INVALID')-cne$script:P3NativeRoot-or(Get-P3JsonString $root 'stage_payload_sha256' 4 'P1A_RECEIPT_INVALID')-cne$script:P3StagePayloadSha-or(Get-P3JsonString $root 'verify_stage_sha256' 4 'P1A_RECEIPT_INVALID')-cne$script:P3VerifyStageSha-or(Get-P3JsonString $root 'native_script_sha256' 4 'P1A_RECEIPT_INVALID')-cne$script:P3NativeScriptSha){Stop-P3 4 'P1A_RECEIPT_INVALID'}}finally{$p1aDoc.Dispose()}
    return [pscustomobject]@{Native=$native;P1a=$p1a}
}

function Get-P3NormalizedDistributionName {
    param([string]$Name)
    if([string]::IsNullOrEmpty($Name)-or$Name-cnotmatch'^[A-Za-z0-9._-]+$'){Stop-P3 6 'METADATA_NAME_INVALID'}
    $normalized=[Text.RegularExpressions.Regex]::Replace($Name.ToLowerInvariant(),'[-_.]+','-')
    if([string]::IsNullOrEmpty($normalized)-or$normalized-cnotmatch'^[a-z0-9]+(?:-[a-z0-9]+)*$'){Stop-P3 6 'METADATA_NAME_INVALID'}
    return $normalized
}

function Read-P3MetadataHeaders {
    param([byte[]]$Raw)
    try{$text=$script:P3Utf8.GetString($Raw)}catch{Stop-P3 6 'METADATA_UTF8_INVALID'}
    $text=$text.Replace("`r`n","`n");if($text.Contains("`r")){Stop-P3 6 'METADATA_LINE_ENDING'}
    $headers=[Collections.Generic.List[object]]::new();$currentName=$null;$currentValue=$null
    foreach($line in $text.Split("`n")){
        if($line-ceq''){
            if($null-ne$currentName){$headers.Add([pscustomobject]@{Name=$currentName;Value=$currentValue.Trim([char[]]@(' ',"`t"))});$currentName=$null;$currentValue=$null}
            break
        }
        if($line.StartsWith(' ')-or$line.StartsWith("`t")){
            if($null-eq$currentName){Stop-P3 6 'METADATA_HEADER_INVALID'};$currentValue+=' '+$line.TrimStart([char[]]@(' ',"`t"));continue
        }
        if($null-ne$currentName){$headers.Add([pscustomobject]@{Name=$currentName;Value=$currentValue.Trim([char[]]@(' ',"`t"))})}
        $colon=$line.IndexOf(':');if($colon-le0){Stop-P3 6 'METADATA_HEADER_INVALID'};$currentName=$line.Substring(0,$colon)
        if($currentName-cnotmatch'^[!-9;-~]+$'){Stop-P3 6 'METADATA_HEADER_INVALID'};$currentValue=$line.Substring($colon+1)
    }
    if($null-ne$currentName){$headers.Add([pscustomobject]@{Name=$currentName;Value=$currentValue.Trim([char[]]@(' ',"`t"))})}
    $headerArray=$headers.ToArray();return $headerArray
}

function Get-P3HeaderValues {
    param([object[]]$Headers,[string]$Name)
    return ,([string[]]@($Headers|Where-Object{$_.Name.Equals($Name,[StringComparison]::OrdinalIgnoreCase)}|ForEach-Object{$_.Value}))
}

function Get-P3LicenseDeclaredMap {
    $pairs=@(
        @('altair','NOASSERTION'),@('annotated-types','MIT'),@('anyio','MIT'),@('attrs','MIT'),@('blinker','NOASSERTION'),@('bokeh','BSD-3-Clause'),@('cerberus','NOASSERTION'),@('certifi','MPL-2.0'),@('charset-normalizer','MIT'),@('click','BSD-3-Clause'),@('cloudpickle','BSD-3-Clause'),@('colorama','NOASSERTION'),@('contourpy','NOASSERTION'),@('corner','NOASSERTION'),@('coverage','Apache-2.0'),@('cycler','NOASSERTION'),@('dask','BSD-3-Clause'),@('distributed','BSD-3-Clause'),@('emcee','MIT'),@('espei','MIT'),@('et-xmlfile','MIT'),@('flexcache','NOASSERTION'),@('flexparser','BSD-3-Clause'),@('fonttools','MIT'),@('fsspec','BSD-3-Clause'),@('h11','MIT'),@('httptools','MIT'),@('idna','BSD-3-Clause'),@('importlib-metadata','Apache-2.0'),@('iniconfig','MIT'),@('itsdangerous','NOASSERTION'),@('jinja2','NOASSERTION'),@('joblib','BSD-3-Clause'),@('jsonschema-specifications','MIT'),@('jsonschema','MIT'),@('kawin','MIT'),@('kiwisolver','NOASSERTION'),@('locket','BSD-2-Clause'),@('lz4','NOASSERTION'),@('markupsafe','BSD-3-Clause'),@('matplotlib','NOASSERTION'),@('msgpack','Apache-2.0'),@('narwhals','MIT'),@('numpy','BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0'),@('openpyxl','MIT'),@('packaging','Apache-2.0 OR BSD-2-Clause'),@('pandas','NOASSERTION'),@('partd','NOASSERTION'),@('pillow','MIT-CMU'),@('pint','NOASSERTION'),@('pip','MIT'),@('platformdirs','MIT'),@('pluggy','MIT'),@('protobuf','NOASSERTION'),@('psutil','BSD-3-Clause'),@('pyarrow','Apache-2.0'),@('pycalphad','MIT'),@('pydantic-core','MIT'),@('pydantic','MIT'),@('pydeck','NOASSERTION'),@('pygments','BSD-2-Clause'),@('pyparsing','MIT'),@('pytest-cov','MIT'),@('pytest','MIT'),@('python-dateutil','NOASSERTION'),@('python-multipart','Apache-2.0'),@('pyyaml','MIT'),@('referencing','MIT'),@('requests','Apache-2.0'),@('rpds-py','MIT'),@('runtype','MIT'),@('scheil','MIT'),@('scikit-learn','BSD-3-Clause'),@('scipy','NOASSERTION'),@('setuptools-scm','MIT'),@('setuptools','NOASSERTION'),@('six','MIT'),@('sortedcontainers','NOASSERTION'),@('starlette','BSD-3-Clause'),@('streamlit','Apache-2.0'),@('symengine','MIT'),@('tblib','BSD-2-Clause'),@('threadpoolctl','BSD-3-Clause'),@('tinydb','MIT'),@('toml','MIT'),@('toolz','BSD-3-Clause'),@('tornado','Apache-2.0'),@('typing-extensions','PSF-2.0'),@('typing-inspection','MIT'),@('tzdata','Apache-2.0'),@('urllib3','MIT'),@('uvicorn','BSD-3-Clause'),@('vcs-versioning','MIT'),@('watchdog','Apache-2.0'),@('websockets','BSD-3-Clause'),@('xarray','Apache-2.0'),@('xyzservices','BSD-3-Clause'),@('zict','NOASSERTION'),@('zipp','MIT')
    )
    $map=[Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal);foreach($pair in $pairs){if(-not$map.TryAdd($pair[0],$pair[1])){Stop-P3 9 'LICENSE_MAP_INVALID'}};if($map.Count-ne99){Stop-P3 9 'LICENSE_MAP_INVALID'};return $map
}

function Get-P3PackageEvidence {
    param([string]$Stage,[object]$Runtime)
    $metadataRows=@($Runtime.Rows|Where-Object{$_.Path-cmatch'^runtime/Lib/site-packages/[^/]+\.dist-info/METADATA$'})
    if($metadataRows.Count-ne99){Stop-P3 6 'METADATA_COUNT_INVALID'}
    $packages=[Collections.Generic.List[object]]::new();$names=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal);$claimants=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
    foreach($row in $metadataRows){
        $physical=Get-P3StableFile (Resolve-P3ExactFile $Stage $row.Path 6 'METADATA_PATH_INVALID') 6 'METADATA_UNSTABLE' $row.Bytes $true
        if($physical.Bytes-ne$row.Bytes-or$physical.Sha256-cne$row.Sha256){Stop-P3 6 'METADATA_TUPLE_INVALID'}
        $headers=Read-P3MetadataHeaders $physical.Raw;$rawNames=Get-P3HeaderValues $headers 'Name';$versions=Get-P3HeaderValues $headers 'Version';$licenses=Get-P3HeaderValues $headers 'License';$expressions=Get-P3HeaderValues $headers 'License-Expression';$classifiers=Get-P3HeaderValues $headers 'Classifier';$licenseFields=Get-P3HeaderValues $headers 'License-File'
        if($rawNames.Count-ne1-or$versions.Count-ne1-or[string]::IsNullOrEmpty($versions[0])-or$licenses.Count-gt1-or$expressions.Count-gt1){Stop-P3 6 'METADATA_HEADER_INVALID'}
        $normalized=Get-P3NormalizedDistributionName $rawNames[0];if(-not$names.Add($normalized)){Stop-P3 6 'METADATA_DUPLICATE'}
        $directory=$row.Path.Substring(0,$row.Path.LastIndexOf('/'));$licenseRows=[Collections.Generic.List[object]]::new();$licenseSeen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach($field in $licenseFields){
            if([string]::IsNullOrEmpty($field)-or$field.Contains('\')-or$field.StartsWith('/')-or$field.Contains(':')){Stop-P3 6 'LICENSE_FILE_INVALID'}
            $direct=$directory+'/'+$field;$nested=$directory+'/licenses/'+$field;Assert-P3RelativePath $direct 6 'LICENSE_FILE_INVALID';Assert-P3RelativePath $nested 6 'LICENSE_FILE_INVALID'
            $candidates=[Collections.Generic.List[string]]::new();$candidates.Add($direct);if($nested-cne$direct){$candidates.Add($nested)}
            $matches=[Collections.Generic.List[string]]::new();foreach($candidate in $candidates){if($Runtime.RowMap.ContainsKey($candidate)){$matches.Add($candidate)}}
            if($matches.Count-ne1){Stop-P3 6 'LICENSE_FILE_INVALID'};$relative=$matches[0];if(-not$licenseSeen.Add($relative)){Stop-P3 6 'LICENSE_FILE_INVALID'}
            $licenseRow=$Runtime.RowMap[$relative];$licenseRows.Add($licenseRow);if($claimants.ContainsKey($relative)){Stop-P3 6 'LICENSE_FILE_MULTICLAIM'};$claimants.Add($relative,[pscustomobject]@{Name=$normalized;Version=$versions[0]})
        }
        $licenseArray=$licenseRows.ToArray();[Array]::Sort($licenseArray,[Collections.Generic.Comparer[object]]::Create([Comparison[object]]{param($a,$b)[StringComparer]::Ordinal.Compare($a.Path,$b.Path)}))
        $packages.Add([pscustomobject]@{Name=$normalized;Version=$versions[0];Metadata=$row;RawLicense=if($licenses.Count-eq1){$licenses[0]}else{''};RawExpression=if($expressions.Count-eq1){$expressions[0]}else{''};Classifiers=[string[]]$classifiers;LicenseRows=$licenseArray})
    }
    $array=$packages.ToArray();[Array]::Sort($array,[Collections.Generic.Comparer[object]]::Create([Comparison[object]]{param($a,$b)[StringComparer]::Ordinal.Compare($a.Name,$b.Name)}))
    $declared=Get-P3LicenseDeclaredMap;foreach($package in $array){if(-not$declared.ContainsKey($package.Name)){Stop-P3 6 'LICENSE_MAP_MISSING'}};foreach($name in $declared.Keys){if(-not$names.Contains($name)){Stop-P3 6 'LICENSE_MAP_EXTRA'}}
    return [pscustomobject]@{Packages=$array;Claimants=$claimants;Declared=$declared}
}

function Get-P3NoticeEvidence {
    param([string]$Stage,[object]$Runtime,[object]$PackageEvidence,[bool]$IncludeContent=$false)
    $paths=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal);foreach($path in $Runtime.NoticePaths){$null=$paths.Add($path)}
    foreach($package in $PackageEvidence.Packages){foreach($row in $package.LicenseRows){$null=$paths.Add($row.Path)}}
    if(-not$Runtime.RowMap.ContainsKey('runtime/LICENSE.txt')){Stop-P3 6 'PYTHON_LICENSE_MISSING'};$null=$paths.Add('runtime/LICENSE.txt')
    $pathArray=[string[]]@($paths);[Array]::Sort($pathArray,[StringComparer]::Ordinal);if($pathArray.Count-ne$script:P3NoticeCount){Stop-P3 6 'NOTICE_UNION_COUNT'}
    $rows=[Collections.Generic.List[object]]::new();$total=[int64]0;$preimages=[Collections.Generic.List[string]]::new()
    foreach($path in $pathArray){if(-not$Runtime.RowMap.ContainsKey($path)){Stop-P3 6 'NOTICE_ROW_UNMANIFESTED'};$source=$Runtime.RowMap[$path];$package='NOASSERTION';$version='NOASSERTION'
        if($path-ceq'runtime/LICENSE.txt'){$package='python-runtime';$version='3.11.9'}elseif($PackageEvidence.Claimants.ContainsKey($path)){$package=$PackageEvidence.Claimants[$path].Name;$version=$PackageEvidence.Claimants[$path].Version}
        $raw=$null;if($IncludeContent){$snapshot=Get-P3StableFile (Resolve-P3ExactFile $Stage $path 6 'NOTICE_PATH_INVALID') 6 'NOTICE_UNSTABLE' $source.Bytes $true;if($snapshot.Bytes-ne$source.Bytes-or$snapshot.Sha256-cne$source.Sha256){Stop-P3 6 'NOTICE_TUPLE_INVALID'};$raw=$snapshot.Raw}
        if($total-gt([int64]::MaxValue-$source.Bytes)){Stop-P3 6 'NOTICE_BYTES_OVERFLOW'};$total+=$source.Bytes;$preimages.Add($path+'|'+$source.Bytes.ToString($script:P3Invariant)+'|'+$source.Sha256+'|'+$package+'|'+$version);$rows.Add([pscustomobject]@{Path=$path;Bytes=$source.Bytes;Sha256=$source.Sha256;Package=$package;Version=$version;Raw=$raw})
    }
    if($total-ne$script:P3NoticeBytes){Stop-P3 6 'NOTICE_UNION_BYTES'};$root=Get-P3HashBytes ($script:P3Utf8.GetBytes(($preimages.ToArray()-join"`r`n")))
    $rowArray=$rows.ToArray();return [pscustomobject]@{Rows=$rowArray;Count=[int64]$rows.Count;Bytes=$total;Root=$root}
}

function Get-P3PackageByName {
    param([object]$Evidence,[string]$Name)
    foreach($package in $Evidence.Packages){if($package.Name-ceq$Name){return $package}};return $null
}

function Build-P3SbomText {
    param([object]$Runtime,[object]$Trust,[object]$Packages,[object]$Notices,[Collections.Generic.Dictionary[string,string]]$P)
    $comment='{"p0_root_sha256":"'+$script:P3P0Root+'","runtime_manifest_sha256":"'+$Runtime.Snapshot.Sha256+'","runtime_input_root_sha256":"'+$script:P3RuntimeRoot+'","runtime_trust_manifest_sha256":"'+$Trust.Snapshot.Sha256+'","runtime_trust_execution_root_sha256":"'+$Trust.Root+'","metadata_row_count":99,"notice_source_row_count":147,"notice_source_total_bytes":767009,"notice_source_root_sha256":"'+$Notices.Root+'","product_version_sha256":"'+$script:P3ProductVersionSha+'","icon_sha256":"'+$script:P3IconSha+'","generator_sha256":"'+$P['ExpectedGenerateSbomSha256']+'"}'
    $describes=[Collections.Generic.List[string]]::new();$packageJson=[Collections.Generic.List[string]]::new()
    foreach($package in $Packages.Packages){$spdx='SPDXRef-Package-'+$package.Name;$describes.Add((Quote-P3Json $spdx));$licenseJson=[Collections.Generic.List[string]]::new();foreach($row in $package.LicenseRows){$licenseJson.Add('{"path":'+(Quote-P3Json $row.Path)+',"bytes":'+$row.Bytes.ToString($script:P3Invariant)+',"sha256":"'+$row.Sha256+'"}')};$classJson=[Collections.Generic.List[string]]::new();foreach($classifier in $package.Classifiers){$classJson.Add((Quote-P3Json $classifier))}
        $evidence='{"normalized_name":'+(Quote-P3Json $package.Name)+',"metadata":{"path":'+(Quote-P3Json $package.Metadata.Path)+',"bytes":'+$package.Metadata.Bytes.ToString($script:P3Invariant)+',"sha256":"'+$package.Metadata.Sha256+'"},"raw_license":'+(Quote-P3Json $package.RawLicense)+',"raw_license_expression":'+(Quote-P3Json $package.RawExpression)+',"raw_classifiers":['+($classJson.ToArray()-join',')+'],"license_files":['+($licenseJson.ToArray()-join',')+']}'
        $packageJson.Add('{"name":'+(Quote-P3Json $package.Name)+',"SPDXID":"'+$spdx+'","versionInfo":'+(Quote-P3Json $package.Version)+',"downloadLocation":"NOASSERTION","filesAnalyzed":false,"licenseConcluded":"NOASSERTION","licenseDeclared":'+(Quote-P3Json $Packages.Declared[$package.Name])+',"copyrightText":"NOASSERTION","comment":'+(Quote-P3Json $evidence)+'}')
    }
    return '{"spdxVersion":"SPDX-2.3","dataLicense":"CC0-1.0","SPDXID":"SPDXRef-DOCUMENT","name":"ThermoGar-runtime-3.11.9","documentNamespace":"urn:thermogar:spdx:runtime:'+$script:P3RuntimeRoot+':trust:'+$Trust.Root+'","creationInfo":{"created":"'+$P['EvidenceCreatedUtc']+'","creators":["Tool: ThermoGar-P3"]},"comment":'+(Quote-P3Json $comment)+',"documentDescribes":['+($describes.ToArray()-join',')+'],"packages":['+($packageJson.ToArray()-join',')+']}'
}

function Get-P3NormalizedNoticeContent {
    param([byte[]]$Raw)
    $offset=0;if($Raw.Length-ge3-and$Raw[0]-eq0xEF-and$Raw[1]-eq0xBB-and$Raw[2]-eq0xBF){$offset=3}
    $slice=[byte[]]::new($Raw.Length-$offset);if($slice.Length-gt0){[Array]::Copy($Raw,$offset,$slice,0,$slice.Length)}
    try{$text=$script:P3Utf8.GetString($slice)}catch{Stop-P3 6 'NOTICE_UTF8_INVALID'};$text=$text.Replace("`r`n","`n").Replace("`r","`n");return $script:P3Utf8.GetBytes($text)
}

function Build-P3NoticesArtifacts {
    param([object]$NoticeEvidence,[object]$PackageEvidence,[object]$Runtime,[object]$Trust,[Collections.Generic.Dictionary[string,string]]$P)
    $sections=[Collections.Generic.List[string]]::new();$sourceJson=[Collections.Generic.List[string]]::new();$bomPaths=[Collections.Generic.HashSet[string]]::new([string[]]@('runtime/Lib/site-packages/distributed-2026.7.1.dist-info/licenses/LICENSE.txt','runtime/Lib/site-packages/partd-1.4.2.dist-info/LICENSE.txt'),[StringComparer]::Ordinal)
    foreach($row in $NoticeEvidence.Rows){$package=if($row.Package-ceq'NOASSERTION'){$null}else{Get-P3PackageByName $PackageEvidence $row.Package};$rawLicense=if($null-ne$package){$package.RawLicense}else{''};$rawExpression=if($null-ne$package){$package.RawExpression}else{''};$classifierJson=[Collections.Generic.List[string]]::new();if($null-ne$package){foreach($classifier in $package.Classifiers){$classifierJson.Add((Quote-P3Json $classifier))}}
        $hasBom=$row.Raw.Length-ge3-and$row.Raw[0]-eq0xEF-and$row.Raw[1]-eq0xBB-and$row.Raw[2]-eq0xBF;if($hasBom-ne$bomPaths.Contains($row.Path)){Stop-P3 6 'NOTICE_BOM_SET_INVALID'}
        $normalized=Get-P3NormalizedNoticeContent $row.Raw;$content=$script:P3Utf8.GetString($normalized);$section='===== BEGIN NOTICE ====='+"`n"+'package: '+$row.Package+"`n"+'version: '+$row.Version+"`n"+'path: '+$row.Path+"`n"+'bytes: '+$row.Bytes.ToString($script:P3Invariant)+"`n"+'sha256: '+$row.Sha256+"`n"+'raw-license: '+(Quote-P3Json $rawLicense)+"`n"+'raw-license-expression: '+(Quote-P3Json $rawExpression)+"`n"+'raw-classifiers: ['+($classifierJson.ToArray()-join',')+"]`n"+'content-utf8-bytes: '+$normalized.LongLength.ToString($script:P3Invariant)+"`ncontent:`n"+$content
        if($normalized.Length-eq0-or$normalized[$normalized.Length-1]-ne0x0A){$section+="`n"};$section+='===== END NOTICE =====';$sections.Add($section);$sourceJson.Add('{"path":'+(Quote-P3Json $row.Path)+',"bytes":'+$row.Bytes.ToString($script:P3Invariant)+',"sha256":"'+$row.Sha256+'","package":'+(Quote-P3Json $row.Package)+',"version":'+(Quote-P3Json $row.Version)+'}')
    }
    $text=$sections.ToArray()-join"`n`n";$bytes=$script:P3Utf8.GetBytes($text);$sha=Get-P3HashBytes $bytes
    $receipt='{"schema":1,"version":1,"algorithm":"SHA-256","runtime_manifest_sha256":"'+$Runtime.Snapshot.Sha256+'","runtime_input_root_sha256":"'+$script:P3RuntimeRoot+'","runtime_trust_manifest_sha256":"'+$Trust.Snapshot.Sha256+'","runtime_trust_execution_root_sha256":"'+$Trust.Root+'","source_rows":['+($sourceJson.ToArray()-join',')+'],"source_row_count":147,"source_total_bytes":767009,"source_root_sha256":"'+$NoticeEvidence.Root+'","notices_sha256":"'+$sha+'","producer_sha256":"'+$P['ExpectedGenerateNoticesSha256']+'"}'
    $receiptBytes=$script:P3Utf8.GetBytes($receipt);return [pscustomobject]@{Text=$text;Bytes=$bytes;Sha256=$sha;ReceiptText=$receipt;ReceiptBytes=$receiptBytes;ReceiptSha256=(Get-P3HashBytes $receiptBytes)}
}

function Assert-P3Icon {
    param([object]$Snapshot)
    if($Snapshot.Bytes-ne$script:P3IconBytes-or$Snapshot.Sha256-cne$script:P3IconSha-or$Snapshot.Raw.Length-lt6){Stop-P3 3 'ICON_INVALID'}
    $raw=$Snapshot.Raw;if([BitConverter]::ToUInt16($raw,0)-ne0-or[BitConverter]::ToUInt16($raw,2)-ne1-or[BitConverter]::ToUInt16($raw,4)-ne8){Stop-P3 3 'ICON_INVALID'}
    $sizes=@(16,20,24,32,40,48,64,256);$ranges=[Collections.Generic.List[object]]::new()
    for($index=0;$index-lt8;$index++){$offset=6+($index*16);if($offset+16-gt$raw.Length){Stop-P3 3 'ICON_INVALID'};$width=if($raw[$offset]-eq0){256}else{[int]$raw[$offset]};$height=if($raw[$offset+1]-eq0){256}else{[int]$raw[$offset+1]};if($width-ne$sizes[$index]-or$height-ne$sizes[$index]){Stop-P3 3 'ICON_INVALID'};$length=[BitConverter]::ToUInt32($raw,$offset+8);$position=[BitConverter]::ToUInt32($raw,$offset+12);if($length-eq0-or$position-lt134-or([uint64]$position+[uint64]$length)-gt[uint64]$raw.Length){Stop-P3 3 'ICON_INVALID'};$ranges.Add([pscustomobject]@{Start=[uint64]$position;End=[uint64]$position+[uint64]$length})}
    $rangeArray=$ranges.ToArray();[Array]::Sort($rangeArray,[Collections.Generic.Comparer[object]]::Create([Comparison[object]]{param($a,$b)$a.Start.CompareTo($b.Start)}));$previous=[uint64]134;foreach($range in $rangeArray){if($range.Start-lt$previous){Stop-P3 3 'ICON_INVALID'};$previous=$range.End};if($previous-ne[uint64]$raw.Length){Stop-P3 3 'ICON_INVALID'}
}

function Assert-P3ExternalIdentity {
    param([Collections.Generic.Dictionary[string,string]]$P)
    $productPath=Assert-P3AbsoluteFile $P['ProductVersionPath'] 3 'PRODUCT_VERSION_PATH';$product=Get-P3Utf8Snapshot $productPath 3 'PRODUCT_VERSION_INVALID' 65536
    if($productPath-cne[IO.Path]::Combine($PSScriptRoot,'product-version.json')-or$product.Bytes-ne$script:P3ProductVersionBytes-or$product.Sha256-cne$script:P3ProductVersionSha-or$product.Sha256-cne$P['ExpectedProductVersionSha256']-or$product.Text-cne$script:P3ProductVersionText){Stop-P3 3 'PRODUCT_VERSION_INVALID'};Assert-P3JsonDocument $product.Text 3 'PRODUCT_VERSION_INVALID'
    $iconPath=Assert-P3AbsoluteFile $P['IconSourcePath'] 3 'ICON_PATH';$icon=Get-P3StableFile $iconPath 3 'ICON_INVALID' 1048576 $true
    if($iconPath-cne[IO.Path]::Combine($PSScriptRoot,'assets','ThermoGar.ico')-or$icon.Bytes-ne(Get-P3CanonicalInt64 $P['ExpectedIconBytes'])-or$icon.Sha256-cne$P['ExpectedIconSha256']){Stop-P3 3 'ICON_INVALID'};Assert-P3Icon $icon
    return [pscustomobject]@{Product=$product;Icon=$icon}
}

function Assert-P3ExternalIdentityUnchanged {
    param([object]$Before)
    $productPath=Assert-P3AbsoluteFile $Before.Product.Path 3 'PRODUCT_VERSION_CHANGED';if($productPath-cne$Before.Product.Path){Stop-P3 3 'PRODUCT_VERSION_CHANGED'}
    $product=Get-P3Utf8Snapshot $productPath 3 'PRODUCT_VERSION_CHANGED' 65536
    if($product.Bytes-ne$Before.Product.Bytes-or$product.Sha256-cne$Before.Product.Sha256-or$product.Text-cne$Before.Product.Text){Stop-P3 3 'PRODUCT_VERSION_CHANGED'}
    $iconPath=Assert-P3AbsoluteFile $Before.Icon.Path 3 'ICON_CHANGED';if($iconPath-cne$Before.Icon.Path){Stop-P3 3 'ICON_CHANGED'}
    $icon=Get-P3StableFile $iconPath 3 'ICON_CHANGED' 1048576 $true
    if($icon.Bytes-ne$Before.Icon.Bytes-or$icon.Sha256-cne$Before.Icon.Sha256-or-not[Collections.StructuralComparisons]::StructuralEqualityComparer.Equals($icon.Raw,$Before.Icon.Raw)){Stop-P3 3 'ICON_CHANGED'}
    Assert-P3Icon $icon
}

function Assert-P3StageRootUnchanged {
    param([string]$Stage)
    $after=Assert-P3AbsoluteDirectory $Stage 5 'STAGE_ROOT_CHANGED'
    if($after-cne$Stage){Stop-P3 5 'STAGE_ROOT_CHANGED'}
}

function Get-P3ScriptPins {
    param([Collections.Generic.Dictionary[string,string]]$P)
    $map=[ordered]@{'generate_sbom.ps1'='ExpectedGenerateSbomSha256';'generate_notices.ps1'='ExpectedGenerateNoticesSha256';'generate_payload_manifest.ps1'='ExpectedGeneratePayloadManifestSha256';'verify_distribution_evidence.ps1'='ExpectedVerifyDistributionEvidenceSha256'}
    $result=[ordered]@{}
    foreach($name in $map.Keys){$path=Assert-P3AbsoluteFile ([IO.Path]::Combine($PSScriptRoot,$name)) 3 'SCRIPT_PATH_INVALID';$snapshot=Get-P3StableFile $path 3 'SCRIPT_IDENTITY_INVALID' 4194304 $false;if($snapshot.Sha256-cne$P[$map[$name]]){Stop-P3 3 'SCRIPT_IDENTITY_INVALID'};$result[$name]=$snapshot}
    $expectedLeaf=switch($script:P3Role){'SBOM'{'generate_sbom.ps1'}'NOTICES'{'generate_notices.ps1'}'PAYLOAD'{'generate_payload_manifest.ps1'}default{'verify_distribution_evidence.ps1'}}
    if([IO.Path]::GetFullPath($script:P3CommandPath)-cne[IO.Path]::Combine($PSScriptRoot,$expectedLeaf)){Stop-P3 3 'SCRIPT_PATH_INVALID'}
    return $result
}

function Assert-P3ScriptsUnchanged {
    param([Collections.Specialized.OrderedDictionary]$Before)
    foreach($name in $Before.Keys){$path=Assert-P3AbsoluteFile ([IO.Path]::Combine($PSScriptRoot,$name)) 3 'SCRIPT_CHANGED';$after=Get-P3StableFile $path 3 'SCRIPT_CHANGED' 4194304 $false;if($after.Bytes-ne$Before[$name].Bytes-or$after.Sha256-cne$Before[$name].Sha256){Stop-P3 3 'SCRIPT_CHANGED'}}
}

function Get-P3Anchors {
    param([string]$Stage,[Collections.Generic.Dictionary[string,string]]$P)
    $runtimePath=Assert-P3AbsoluteFile $P['RuntimeManifestPath'] 3 'RUNTIME_MANIFEST_PATH';if($runtimePath-cne[IO.Path]::Combine($Stage,'manifests','runtime-input-manifest.json')){Stop-P3 3 'RUNTIME_MANIFEST_PATH'};$runtimeSnapshot=Get-P3Utf8Snapshot $runtimePath 4 'RUNTIME_MANIFEST_INVALID' 4194304;if($runtimeSnapshot.Sha256-cne$script:P3RuntimeManifestSha-or$runtimeSnapshot.Sha256-cne$P['ExpectedRuntimeManifestSha256']){Stop-P3 4 'RUNTIME_MANIFEST_INVALID'};$runtime=Read-P3ContentManifest $runtimeSnapshot 'runtime'
    $projectSnapshot=Get-P3Utf8Snapshot (Resolve-P3ExactFile $Stage 'manifests/project-source-manifest.json' 4 'PROJECT_MANIFEST_INVALID') 4 'PROJECT_MANIFEST_INVALID' 1048576;$project=Read-P3ContentManifest $projectSnapshot 'project'
    Assert-P3ReleasePolicy $Stage
    $receipts=Assert-P3AncestorReceipts $Stage $P $project $runtime
    $trustPath=Assert-P3AbsoluteFile $P['RuntimeTrustManifestPath'] 3 'TRUST_MANIFEST_PATH';if($trustPath-cne[IO.Path]::Combine($Stage,'manifests','runtime-trust-manifest.json')){Stop-P3 3 'TRUST_MANIFEST_PATH'};$trustSnapshot=Get-P3Utf8Snapshot $trustPath 4 'TRUST_MANIFEST_INVALID' 67108864;if($trustSnapshot.Sha256-cne$P['ExpectedRuntimeTrustManifestSha256']){Stop-P3 4 'TRUST_MANIFEST_INVALID'};$trust=Read-P3TrustManifest $trustSnapshot $P
    $trustReceiptPath=Assert-P3AbsoluteFile $P['RuntimeTrustReceiptPath'] 3 'TRUST_RECEIPT_PATH';if($trustReceiptPath-cne[IO.Path]::Combine($Stage,'manifests','runtime-trust-manifest.receipt.json')){Stop-P3 3 'TRUST_RECEIPT_PATH'};$trustReceiptSnapshot=Get-P3Utf8Snapshot $trustReceiptPath 4 'TRUST_RECEIPT_INVALID' 65536;if($trustReceiptSnapshot.Sha256-cne$P['ExpectedRuntimeTrustReceiptSha256']){Stop-P3 4 'TRUST_RECEIPT_INVALID'};$trustReceipt=Read-P3TrustReceipt $trustReceiptSnapshot $trust $P
    return [pscustomobject]@{Runtime=$runtime;Project=$project;Receipts=$receipts;Trust=$trust;TrustReceipt=$trustReceipt}
}

function Get-P3RowsWithout {
    param([object[]]$Rows,[string[]]$Excluded)
    if($null-eq$Excluded){$Excluded=[string[]]@()};$set=[Collections.Generic.HashSet[string]]::new($Excluded,[StringComparer]::Ordinal);$kept=[Collections.Generic.List[object]]::new();foreach($row in $Rows){if(-not$set.Contains($row.Path)){$kept.Add($row)}};$array=$kept.ToArray();return $array
}

function Assert-P3PhaseTree {
    param([object]$Tree,[object]$Anchors,[Collections.Generic.Dictionary[string,string]]$P,[string[]]$ExpectedOutputs)
    if($null-eq$ExpectedOutputs){$ExpectedOutputs=[string[]]@()}
    $outputSet=[Collections.Generic.HashSet[string]]::new($ExpectedOutputs,[StringComparer]::Ordinal);$actualOutput=[Collections.Generic.List[object]]::new();foreach($row in $Tree.Rows){if($outputSet.Contains($row.Path)){$actualOutput.Add($row)}}
    if($actualOutput.Count-ne$ExpectedOutputs.Count){Stop-P3 5 'PHASE_OUTPUT_COUNT'}
    foreach($path in $ExpectedOutputs){if(-not(@($Tree.Rows|Where-Object{$_.Path-ceq$path}).Count-eq1)){Stop-P3 5 'PHASE_OUTPUT_MEMBERSHIP'}}
    $allKnown=@('evidence/sbom.spdx.json','THIRD_PARTY_NOTICES.txt','evidence/notices-receipt.json','assets/ThermoGar.ico','manifests/payload-manifest.json','manifests/distribution-evidence-receipt.json');foreach($row in $Tree.Rows){if($allKnown-contains$row.Path-and-not$outputSet.Contains($row.Path)){Stop-P3 5 'PHASE_OUTPUT_UNEXPECTED'}}
    $base=Get-P3RowsWithout $Tree.Rows $ExpectedOutputs;$baseBytes=[int64]0;foreach($row in $base){if($baseBytes-gt([int64]::MaxValue-$row.Bytes)){Stop-P3 5 'BASE_BYTES_OVERFLOW'};$baseBytes+=$row.Bytes}
    if($base.Count-ne$script:P3BaseFileCount-or$base.Count-ne(Get-P3CanonicalInt64 $P['ExpectedP1bPhysicalFileCount'])-or$baseBytes-ne(Get-P3CanonicalInt64 $P['ExpectedP1bPhysicalTotalBytes'])-or(Get-P3RowRoot $base)-cne$P['ExpectedP1bPhysicalRootSha256']){Stop-P3 5 'P1B_PHYSICAL_INVALID'}
    $baseMap=Get-P3RowMap $base 5 'P1B_PHYSICAL_INVALID';foreach($row in $Anchors.Trust.Rows){if(-not$baseMap.ContainsKey($row.Path)-or$baseMap[$row.Path].Bytes-ne$row.Bytes-or$baseMap[$row.Path].Sha256-cne$row.Sha256){Stop-P3 5 'P1B_EXECUTION_PHYSICAL'}}
    $metadataPins=[ordered]@{'manifests/project-source-manifest.json'=$Anchors.Project.Snapshot;'manifests/runtime-input-manifest.json'=$Anchors.Runtime.Snapshot;'manifests/native-closure-receipt.json'=$Anchors.Receipts.Native;'manifests/p1a-stage-receipt.json'=$Anchors.Receipts.P1a;'manifests/runtime-trust-manifest.json'=$Anchors.Trust.Snapshot;'manifests/runtime-trust-manifest.receipt.json'=$Anchors.TrustReceipt.Snapshot};foreach($path in $metadataPins.Keys){if(-not$baseMap.ContainsKey($path)-or$baseMap[$path].Bytes-ne$metadataPins[$path].Bytes-or$baseMap[$path].Sha256-cne$metadataPins[$path].Sha256){Stop-P3 5 'P1B_METADATA_PHYSICAL'}}
    Assert-P3NoForbiddenRows $base $Anchors.Runtime.RowMap;Assert-P3ExactDirectories $Tree.Directories $Tree.Rows
    $outputArray=$actualOutput.ToArray();return [pscustomobject]@{BaseRows=$base;BaseMap=$baseMap;BaseBytes=$baseBytes;OutputRows=$outputArray}
}

function Get-P3PinnedOutput {
    param([object]$Tree,[string]$Path,[int]$Code,[string]$Detail)
    $rows=@($Tree.Rows|Where-Object{$_.Path-ceq$Path});if($rows.Count-ne1){Stop-P3 $Code $Detail};return $rows[0]
}

function Assert-P3SbomFile {
    param([string]$Stage,[object]$Runtime,[object]$Trust,[object]$Packages,[object]$Notices,[Collections.Generic.Dictionary[string,string]]$P,[string]$ExpectedSha)
    $text=Build-P3SbomText $Runtime $Trust $Packages $Notices $P;$bytes=$script:P3Utf8.GetBytes($text);$sha=Get-P3HashBytes $bytes;if($sha-cne$ExpectedSha){Stop-P3 6 'SBOM_HASH_MISMATCH'};$snapshot=Get-P3Utf8Snapshot (Resolve-P3ExactFile $Stage 'evidence/sbom.spdx.json' 6 'SBOM_INVALID') 6 'SBOM_INVALID' 16777216;if($snapshot.Text-cne$text-or$snapshot.Sha256-cne$sha){Stop-P3 6 'SBOM_INVALID'};Assert-P3JsonDocument $snapshot.Text 6 'SBOM_INVALID';return [pscustomobject]@{Text=$text;Bytes=$bytes;Sha256=$sha;Snapshot=$snapshot}
}

function Assert-P3NoticesFiles {
    param([string]$Stage,[object]$Artifacts,[string]$ExpectedNoticesSha,[string]$ExpectedReceiptSha)
    if($Artifacts.Sha256-cne$ExpectedNoticesSha-or$Artifacts.ReceiptSha256-cne$ExpectedReceiptSha){Stop-P3 7 'NOTICES_HASH_MISMATCH'}
    $notices=Get-P3StableFile (Resolve-P3ExactFile $Stage 'THIRD_PARTY_NOTICES.txt' 7 'NOTICES_INVALID') 7 'NOTICES_INVALID' 16777216 $true;$receipt=Get-P3Utf8Snapshot (Resolve-P3ExactFile $Stage 'evidence/notices-receipt.json' 7 'NOTICES_RECEIPT_INVALID') 7 'NOTICES_RECEIPT_INVALID' 1048576
    if($notices.Sha256-cne$Artifacts.Sha256-or$notices.Bytes-ne$Artifacts.Bytes.LongLength-or-not[Collections.StructuralComparisons]::StructuralEqualityComparer.Equals($notices.Raw,$Artifacts.Bytes)-or$receipt.Text-cne$Artifacts.ReceiptText-or$receipt.Sha256-cne$Artifacts.ReceiptSha256){Stop-P3 7 'NOTICES_INVALID'};Assert-P3JsonDocument $receipt.Text 7 'NOTICES_RECEIPT_INVALID'
    return [pscustomobject]@{Notices=$notices;Receipt=$receipt}
}

function Build-P3PayloadManifestText {
    param([object[]]$Rows,[string]$Root,[Collections.Generic.Dictionary[string,string]]$P)
    $json=[Collections.Generic.List[string]]::new();$total=[int64]0;foreach($row in $Rows){$json.Add('{"path":'+(Quote-P3Json $row.Path)+',"bytes":'+$row.Bytes.ToString($script:P3Invariant)+',"sha256":"'+$row.Sha256+'"}');if($total-gt([int64]::MaxValue-$row.Bytes)){Stop-P3 7 'PAYLOAD_BYTES_OVERFLOW'};$total+=$row.Bytes}
    return [pscustomobject]@{Text='{"schema":1,"version":1,"algorithm":"SHA-256","rows":['+($json.ToArray()-join',')+'],"row_count":'+$Rows.Count.ToString($script:P3Invariant)+',"total_bytes":'+$total.ToString($script:P3Invariant)+',"payload_root_sha256":"'+$Root+'","producer_sha256":"'+$P['ExpectedGeneratePayloadManifestSha256']+'","verifier_sha256":"'+$P['ExpectedVerifyDistributionEvidenceSha256']+'"}';Total=$total}
}

function Build-P3DistributionReceiptText {
    param([string]$PayloadManifestSha,[string]$PayloadRoot,[int64]$PayloadBytes,[string]$SbomSha,[string]$NoticesSha,[string]$NoticesReceiptSha,[object]$Anchors,[Collections.Generic.Dictionary[string,string]]$P)
    return '{"schema":1,"version":1,"algorithm":"SHA-256","evidence_created_utc":"'+$P['EvidenceCreatedUtc']+'","payload_manifest_sha256":"'+$PayloadManifestSha+'","payload_root_sha256":"'+$PayloadRoot+'","payload_row_count":15045,"payload_total_bytes":'+$PayloadBytes.ToString($script:P3Invariant)+',"sbom_sha256":"'+$SbomSha+'","notices_sha256":"'+$NoticesSha+'","notices_receipt_sha256":"'+$NoticesReceiptSha+'","p0_root_sha256":"'+$script:P3P0Root+'","runtime_manifest_sha256":"'+$Anchors.Runtime.Snapshot.Sha256+'","runtime_input_root_sha256":"'+$script:P3RuntimeRoot+'","runtime_file_count":15003,"runtime_total_bytes":575844438,"native_receipt_sha256":"'+$Anchors.Receipts.Native.Sha256+'","native_closure_root_sha256":"'+$script:P3NativeRoot+'","p1a_stage_receipt_sha256":"'+$Anchors.Receipts.P1a.Sha256+'","runtime_trust_manifest_sha256":"'+$Anchors.Trust.Snapshot.Sha256+'","runtime_trust_execution_root_sha256":"'+$Anchors.Trust.Root+'","runtime_trust_receipt_sha256":"'+$Anchors.TrustReceipt.Snapshot.Sha256+'","product_version_sha256":"'+$script:P3ProductVersionSha+'","icon_sha256":"'+$script:P3IconSha+'","sbom_producer_sha256":"'+$P['ExpectedGenerateSbomSha256']+'","notices_producer_sha256":"'+$P['ExpectedGenerateNoticesSha256']+'","payload_producer_sha256":"'+$P['ExpectedGeneratePayloadManifestSha256']+'","distribution_verifier_sha256":"'+$P['ExpectedVerifyDistributionEvidenceSha256']+'"}'
}

function Get-P3Parameters {
    param([object[]]$Arguments)
    if ($null -eq $Arguments) { $Arguments = [object[]]@() }
    $common=@('StageRoot','RuntimeManifestPath','ExpectedRuntimeManifestSha256','ExpectedRuntimeFileCount','ExpectedRuntimeTotalBytes','ExpectedRuntimeRootSha256','ExpectedRuntimeNoticePathCount','ExpectedRuntimeNoticeRootSha256','ExpectedP0RootSha256','ExpectedNativeReceiptSha256','ExpectedNativeClosureRootSha256','ExpectedP1aStageReceiptSha256','RuntimeTrustManifestPath','ExpectedRuntimeTrustManifestSha256','RuntimeTrustReceiptPath','ExpectedRuntimeTrustReceiptSha256','ExpectedRuntimeTrustExecutionRowCount','ExpectedRuntimeTrustExecutionRootSha256','ExpectedP1bPhysicalFileCount','ExpectedP1bPhysicalTotalBytes','ExpectedP1bPhysicalRootSha256','ProductVersionPath','ExpectedProductVersionSha256','IconSourcePath','ExpectedIconBytes','ExpectedIconSha256','ExpectedGenerateSbomSha256','ExpectedGenerateNoticesSha256','ExpectedGeneratePayloadManifestSha256','ExpectedVerifyDistributionEvidenceSha256','EvidenceCreatedUtc')
    $extra=switch($script:P3Role){'SBOM'{@()}'NOTICES'{@('ExpectedSbomSha256')}'PAYLOAD'{@('ExpectedSbomSha256','ExpectedNoticesSha256','ExpectedNoticesReceiptSha256')}default{@('ExpectedSbomSha256','ExpectedNoticesSha256','ExpectedNoticesReceiptSha256','ExpectedPayloadManifestSha256','ExpectedPayloadRowCount','ExpectedPayloadTotalBytes','ExpectedPayloadRootSha256','ExpectedDistributionEvidenceReceiptSha256','ExpectedFinalStageFileCount','ExpectedFinalStageDirectoryCount','ExpectedFinalStageTotalBytes')}}
    return Get-P3InvocationMap $Arguments ([string[]]@($common+$extra))
}

function Assert-P3ParameterPins {
    param([Collections.Generic.Dictionary[string,string]]$P)
    $shaNames=@('ExpectedRuntimeManifestSha256','ExpectedRuntimeRootSha256','ExpectedRuntimeNoticeRootSha256','ExpectedP0RootSha256','ExpectedNativeReceiptSha256','ExpectedNativeClosureRootSha256','ExpectedP1aStageReceiptSha256','ExpectedRuntimeTrustManifestSha256','ExpectedRuntimeTrustReceiptSha256','ExpectedRuntimeTrustExecutionRootSha256','ExpectedP1bPhysicalRootSha256','ExpectedProductVersionSha256','ExpectedIconSha256','ExpectedGenerateSbomSha256','ExpectedGenerateNoticesSha256','ExpectedGeneratePayloadManifestSha256','ExpectedVerifyDistributionEvidenceSha256')
    if($script:P3Role-ne'SBOM'){$shaNames+=@('ExpectedSbomSha256')};if($script:P3Role-in@('PAYLOAD','VERIFY')){$shaNames+=@('ExpectedNoticesSha256','ExpectedNoticesReceiptSha256')};if($script:P3Role-ceq'VERIFY'){$shaNames+=@('ExpectedPayloadManifestSha256','ExpectedPayloadRootSha256','ExpectedDistributionEvidenceReceiptSha256')}
    foreach($name in $shaNames){Assert-P3Sha $P[$name] 'PIN_SHA_INVALID' 2}
    if($P['ExpectedRuntimeManifestSha256']-cne$script:P3RuntimeManifestSha-or(Get-P3CanonicalInt64 $P['ExpectedRuntimeFileCount'])-ne$script:P3RuntimeCount-or(Get-P3CanonicalInt64 $P['ExpectedRuntimeTotalBytes'])-ne$script:P3RuntimeBytes-or$P['ExpectedRuntimeRootSha256']-cne$script:P3RuntimeRoot-or(Get-P3CanonicalInt64 $P['ExpectedRuntimeNoticePathCount'])-ne$script:P3LegacyNoticeCount-or$P['ExpectedRuntimeNoticeRootSha256']-cne$script:P3LegacyNoticeRoot-or$P['ExpectedP0RootSha256']-cne$script:P3P0Root-or$P['ExpectedNativeReceiptSha256']-cne$script:P3NativeReceiptSha-or$P['ExpectedNativeClosureRootSha256']-cne$script:P3NativeRoot-or$P['ExpectedP1aStageReceiptSha256']-cne$script:P3P1aReceiptSha-or(Get-P3CanonicalInt64 $P['ExpectedRuntimeTrustExecutionRowCount'])-ne$script:P3ExecutionCount-or(Get-P3CanonicalInt64 $P['ExpectedP1bPhysicalFileCount'])-ne$script:P3BaseFileCount-or$P['ExpectedProductVersionSha256']-cne$script:P3ProductVersionSha-or(Get-P3CanonicalInt64 $P['ExpectedIconBytes'])-ne$script:P3IconBytes-or$P['ExpectedIconSha256']-cne$script:P3IconSha){Stop-P3 3 'PIN_VALUE_INVALID'}
    $p1bBytes=Get-P3CanonicalInt64 $P['ExpectedP1bPhysicalTotalBytes'];if($p1bBytes-le0){Stop-P3 3 'PIN_VALUE_INVALID'}
    if($P['EvidenceCreatedUtc']-cnotmatch'^\d{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$'){Stop-P3 3 'EVIDENCE_TIME_INVALID'}
    $parsed=[DateTimeOffset]::MinValue;if(-not[DateTimeOffset]::TryParseExact($P['EvidenceCreatedUtc'],'yyyy-MM-ddTHH:mm:ssZ',$script:P3Invariant,[Globalization.DateTimeStyles]::AssumeUniversal,[ref]$parsed)-or$parsed.UtcDateTime.ToString('yyyy-MM-ddTHH:mm:ssZ',$script:P3Invariant)-cne$P['EvidenceCreatedUtc']){Stop-P3 3 'EVIDENCE_TIME_INVALID'}
    if($script:P3Role-ceq'VERIFY'){
        if((Get-P3CanonicalInt64 $P['ExpectedPayloadRowCount'])-ne$script:P3PayloadCount-or(Get-P3CanonicalInt64 $P['ExpectedPayloadTotalBytes'])-le0-or(Get-P3CanonicalInt64 $P['ExpectedFinalStageFileCount'])-ne$script:P3FinalFileCount-or(Get-P3CanonicalInt64 $P['ExpectedFinalStageDirectoryCount'])-ne$script:P3FinalDirectoryCount-or(Get-P3CanonicalInt64 $P['ExpectedFinalStageTotalBytes'])-le0){Stop-P3 3 'PIN_VALUE_INVALID'}
    }
}

function Get-P3TotalBytes {
    param([object[]]$Rows)
    $total=[int64]0;foreach($row in $Rows){if($total-gt([int64]::MaxValue-$row.Bytes)){Stop-P3 8 'TOTAL_BYTES_OVERFLOW'};$total+=$row.Bytes};return $total
}

function Invoke-P3Sbom {
    param([string]$Stage,[object]$Anchors,[object]$Identity,[Collections.Specialized.OrderedDictionary]$Scripts,[Collections.Generic.Dictionary[string,string]]$P)
    $tree=Get-P3Tree $Stage;$null=Assert-P3PhaseTree $tree $Anchors $P @();if($tree.Rows.Count-ne$script:P3BaseFileCount-or$tree.Directories.Count-ne$script:P3BaseDirectoryCount){Stop-P3 5 'BASE_TOPOLOGY_INVALID'}
    $packages=Get-P3PackageEvidence $Stage $Anchors.Runtime;$notices=Get-P3NoticeEvidence $Stage $Anchors.Runtime $packages $true;$text=Build-P3SbomText $Anchors.Runtime $Anchors.Trust $packages $notices $P;Assert-P3JsonDocument $text 7 'SBOM_SERIALIZATION_INVALID';$bytes=$script:P3Utf8.GetBytes($text);$sha=Get-P3HashBytes $bytes
    $evidence=New-P3Directory $Stage 'evidence';$pin=Publish-P3CreateNew ([IO.Path]::Combine($evidence,'sbom.spdx.json')) $bytes;if($pin.Sha256-cne$sha){Stop-P3 8 'OUTPUT_VERIFY'}
    $after=Get-P3Tree $Stage;$null=Assert-P3PhaseTree $after $Anchors $P @('evidence/sbom.spdx.json');if($after.Rows.Count-ne15042-or$after.Directories.Count-ne1463){Stop-P3 5 'SBOM_TOPOLOGY_INVALID'}
    $null=Assert-P3SbomFile $Stage $Anchors.Runtime $Anchors.Trust $packages $notices $P $sha;Assert-P3StageRootUnchanged $Stage;Assert-P3ExternalIdentityUnchanged $Identity;Assert-P3ScriptsUnchanged $Scripts
    [Console]::Out.Write('{"schema":1,"status":"P3_SBOM_GENERATED","package_count":99,"sbom_sha256":"'+$sha+'"}');exit 0
}

function Invoke-P3Notices {
    param([string]$Stage,[object]$Anchors,[object]$Identity,[Collections.Specialized.OrderedDictionary]$Scripts,[Collections.Generic.Dictionary[string,string]]$P)
    $tree=Get-P3Tree $Stage;$null=Assert-P3PhaseTree $tree $Anchors $P @('evidence/sbom.spdx.json');if($tree.Rows.Count-ne15042-or$tree.Directories.Count-ne1463){Stop-P3 5 'SBOM_TOPOLOGY_INVALID'}
    $packages=Get-P3PackageEvidence $Stage $Anchors.Runtime;$noticeRows=Get-P3NoticeEvidence $Stage $Anchors.Runtime $packages $true;$sbomNoticeRows=Get-P3NoticeEvidence $Stage $Anchors.Runtime $packages $false;$null=Assert-P3SbomFile $Stage $Anchors.Runtime $Anchors.Trust $packages $sbomNoticeRows $P $P['ExpectedSbomSha256'];$artifacts=Build-P3NoticesArtifacts $noticeRows $packages $Anchors.Runtime $Anchors.Trust $P;Assert-P3JsonDocument $artifacts.ReceiptText 7 'NOTICES_SERIALIZATION_INVALID'
    $noticePin=Publish-P3CreateNew ([IO.Path]::Combine($Stage,'THIRD_PARTY_NOTICES.txt')) $artifacts.Bytes;$receiptPin=Publish-P3CreateNew ([IO.Path]::Combine($Stage,'evidence','notices-receipt.json')) $artifacts.ReceiptBytes
    if($noticePin.Sha256-cne$artifacts.Sha256-or$receiptPin.Sha256-cne$artifacts.ReceiptSha256){Stop-P3 8 'OUTPUT_VERIFY'}
    $after=Get-P3Tree $Stage;$null=Assert-P3PhaseTree $after $Anchors $P @('evidence/sbom.spdx.json','THIRD_PARTY_NOTICES.txt','evidence/notices-receipt.json');if($after.Rows.Count-ne15044-or$after.Directories.Count-ne1463){Stop-P3 5 'NOTICES_TOPOLOGY_INVALID'}
    $null=Assert-P3NoticesFiles $Stage $artifacts $artifacts.Sha256 $artifacts.ReceiptSha256;Assert-P3StageRootUnchanged $Stage;Assert-P3ExternalIdentityUnchanged $Identity;Assert-P3ScriptsUnchanged $Scripts
    [Console]::Out.Write('{"schema":1,"status":"P3_NOTICES_GENERATED","source_row_count":147,"notices_sha256":"'+$artifacts.Sha256+'","receipt_sha256":"'+$artifacts.ReceiptSha256+'"}');exit 0
}

function Invoke-P3Payload {
    param([string]$Stage,[object]$Anchors,[object]$Identity,[Collections.Specialized.OrderedDictionary]$Scripts,[Collections.Generic.Dictionary[string,string]]$P)
    $tree=Get-P3Tree $Stage;$null=Assert-P3PhaseTree $tree $Anchors $P @('evidence/sbom.spdx.json','THIRD_PARTY_NOTICES.txt','evidence/notices-receipt.json');if($tree.Rows.Count-ne15044-or$tree.Directories.Count-ne1463){Stop-P3 5 'NOTICES_TOPOLOGY_INVALID'}
    $packages=Get-P3PackageEvidence $Stage $Anchors.Runtime;$noticeRows=Get-P3NoticeEvidence $Stage $Anchors.Runtime $packages $true;$sbomNoticeRows=Get-P3NoticeEvidence $Stage $Anchors.Runtime $packages $false;$null=Assert-P3SbomFile $Stage $Anchors.Runtime $Anchors.Trust $packages $sbomNoticeRows $P $P['ExpectedSbomSha256'];$artifacts=Build-P3NoticesArtifacts $noticeRows $packages $Anchors.Runtime $Anchors.Trust $P;$null=Assert-P3NoticesFiles $Stage $artifacts $P['ExpectedNoticesSha256'] $P['ExpectedNoticesReceiptSha256']
    $assets=New-P3Directory $Stage 'assets';$iconPin=Publish-P3CreateNew ([IO.Path]::Combine($assets,'ThermoGar.ico')) $Identity.Icon.Raw;if($iconPin.Bytes-ne$script:P3IconBytes-or$iconPin.Sha256-cne$script:P3IconSha){Stop-P3 8 'ICON_COPY_INVALID'}
    $payloadTree=Get-P3Tree $Stage;$null=Assert-P3PhaseTree $payloadTree $Anchors $P @('evidence/sbom.spdx.json','THIRD_PARTY_NOTICES.txt','evidence/notices-receipt.json','assets/ThermoGar.ico');if($payloadTree.Rows.Count-ne$script:P3PayloadCount-or$payloadTree.Directories.Count-ne$script:P3FinalDirectoryCount){Stop-P3 5 'PAYLOAD_TOPOLOGY_INVALID'}
    $payloadRoot=Get-P3RowRoot $payloadTree.Rows;$payloadDocument=Build-P3PayloadManifestText $payloadTree.Rows $payloadRoot $P;Assert-P3JsonDocument $payloadDocument.Text 7 'PAYLOAD_SERIALIZATION_INVALID';$payloadBytes=$script:P3Utf8.GetBytes($payloadDocument.Text);$payloadSha=Get-P3HashBytes $payloadBytes
    $payloadPin=Publish-P3CreateNew ([IO.Path]::Combine($Stage,'manifests','payload-manifest.json')) $payloadBytes;if($payloadPin.Sha256-cne$payloadSha){Stop-P3 8 'PAYLOAD_MANIFEST_WRITE'}
    $receiptText=Build-P3DistributionReceiptText $payloadSha $payloadRoot $payloadDocument.Total $P['ExpectedSbomSha256'] $P['ExpectedNoticesSha256'] $P['ExpectedNoticesReceiptSha256'] $Anchors $P;Assert-P3JsonDocument $receiptText 7 'RECEIPT_SERIALIZATION_INVALID';$receiptBytes=$script:P3Utf8.GetBytes($receiptText);$receiptSha=Get-P3HashBytes $receiptBytes;$receiptPin=Publish-P3CreateNew ([IO.Path]::Combine($Stage,'manifests','distribution-evidence-receipt.json')) $receiptBytes;if($receiptPin.Sha256-cne$receiptSha){Stop-P3 8 'DISTRIBUTION_RECEIPT_WRITE'}
    $after=Get-P3Tree $Stage;$null=Assert-P3PhaseTree $after $Anchors $P @('evidence/sbom.spdx.json','THIRD_PARTY_NOTICES.txt','evidence/notices-receipt.json','assets/ThermoGar.ico','manifests/payload-manifest.json','manifests/distribution-evidence-receipt.json');if($after.Rows.Count-ne$script:P3FinalFileCount-or$after.Directories.Count-ne$script:P3FinalDirectoryCount){Stop-P3 5 'FINAL_TOPOLOGY_INVALID'};Assert-P3StageRootUnchanged $Stage;Assert-P3ExternalIdentityUnchanged $Identity;Assert-P3ScriptsUnchanged $Scripts
    [Console]::Out.Write('{"schema":1,"status":"P3_DISTRIBUTION_EVIDENCE_GENERATED","payload_row_count":15045,"payload_root_sha256":"'+$payloadRoot+'","payload_manifest_sha256":"'+$payloadSha+'","distribution_receipt_sha256":"'+$receiptSha+'"}');exit 0
}

function Invoke-P3Verify {
    param([string]$Stage,[object]$Anchors,[object]$Identity,[Collections.Specialized.OrderedDictionary]$Scripts,[Collections.Generic.Dictionary[string,string]]$P)
    $tree=Get-P3Tree $Stage;$phase=Assert-P3PhaseTree $tree $Anchors $P @('evidence/sbom.spdx.json','THIRD_PARTY_NOTICES.txt','evidence/notices-receipt.json','assets/ThermoGar.ico','manifests/payload-manifest.json','manifests/distribution-evidence-receipt.json')
    $finalBytes=Get-P3TotalBytes $tree.Rows;if($tree.Rows.Count-ne$script:P3FinalFileCount-or$tree.Rows.Count-ne(Get-P3CanonicalInt64 $P['ExpectedFinalStageFileCount'])-or$tree.Directories.Count-ne$script:P3FinalDirectoryCount-or$tree.Directories.Count-ne(Get-P3CanonicalInt64 $P['ExpectedFinalStageDirectoryCount'])-or$finalBytes-ne(Get-P3CanonicalInt64 $P['ExpectedFinalStageTotalBytes'])){Stop-P3 5 'FINAL_STAGE_TOTALS'}
    $packages=Get-P3PackageEvidence $Stage $Anchors.Runtime;$noticeRows=Get-P3NoticeEvidence $Stage $Anchors.Runtime $packages $true;$sbomNoticeRows=Get-P3NoticeEvidence $Stage $Anchors.Runtime $packages $false;$sbom=Assert-P3SbomFile $Stage $Anchors.Runtime $Anchors.Trust $packages $sbomNoticeRows $P $P['ExpectedSbomSha256'];$artifacts=Build-P3NoticesArtifacts $noticeRows $packages $Anchors.Runtime $Anchors.Trust $P;$noticeFiles=Assert-P3NoticesFiles $Stage $artifacts $P['ExpectedNoticesSha256'] $P['ExpectedNoticesReceiptSha256']
    $stagedIcon=Get-P3StableFile (Resolve-P3ExactFile $Stage 'assets/ThermoGar.ico' 8 'ICON_STAGE_INVALID') 8 'ICON_STAGE_INVALID' 1048576 $true;if($stagedIcon.Bytes-ne$Identity.Icon.Bytes-or$stagedIcon.Sha256-cne$Identity.Icon.Sha256-or-not[Collections.StructuralComparisons]::StructuralEqualityComparer.Equals($stagedIcon.Raw,$Identity.Icon.Raw)){Stop-P3 8 'ICON_STAGE_INVALID'};Assert-P3Icon $stagedIcon
    $payloadRows=Get-P3RowsWithout $tree.Rows @('manifests/payload-manifest.json','manifests/distribution-evidence-receipt.json');if($payloadRows.Count-ne$script:P3PayloadCount){Stop-P3 8 'PAYLOAD_ROW_COUNT'};$payloadRoot=Get-P3RowRoot $payloadRows;$payloadDocument=Build-P3PayloadManifestText $payloadRows $payloadRoot $P
    if($payloadRoot-cne$P['ExpectedPayloadRootSha256']-or$payloadDocument.Total-ne(Get-P3CanonicalInt64 $P['ExpectedPayloadTotalBytes'])){Stop-P3 8 'PAYLOAD_ROOT_INVALID'}
    $payloadSnapshot=Get-P3Utf8Snapshot (Resolve-P3ExactFile $Stage 'manifests/payload-manifest.json' 8 'PAYLOAD_MANIFEST_INVALID') 8 'PAYLOAD_MANIFEST_INVALID' 67108864;$payloadSha=Get-P3HashBytes ($script:P3Utf8.GetBytes($payloadDocument.Text));if($payloadSnapshot.Text-cne$payloadDocument.Text-or$payloadSnapshot.Sha256-cne$payloadSha-or$payloadSha-cne$P['ExpectedPayloadManifestSha256']){Stop-P3 8 'PAYLOAD_MANIFEST_INVALID'};Assert-P3JsonDocument $payloadSnapshot.Text 8 'PAYLOAD_MANIFEST_INVALID'
    $receiptText=Build-P3DistributionReceiptText $payloadSha $payloadRoot $payloadDocument.Total $sbom.Sha256 $artifacts.Sha256 $artifacts.ReceiptSha256 $Anchors $P;$receiptSnapshot=Get-P3Utf8Snapshot (Resolve-P3ExactFile $Stage 'manifests/distribution-evidence-receipt.json' 8 'DISTRIBUTION_RECEIPT_INVALID') 8 'DISTRIBUTION_RECEIPT_INVALID' 1048576;$receiptSha=Get-P3HashBytes ($script:P3Utf8.GetBytes($receiptText));if($receiptSnapshot.Text-cne$receiptText-or$receiptSnapshot.Sha256-cne$receiptSha-or$receiptSha-cne$P['ExpectedDistributionEvidenceReceiptSha256']){Stop-P3 8 'DISTRIBUTION_RECEIPT_INVALID'};Assert-P3JsonDocument $receiptSnapshot.Text 8 'DISTRIBUTION_RECEIPT_INVALID'
    Assert-P3StageRootUnchanged $Stage;Assert-P3ExternalIdentityUnchanged $Identity;Assert-P3ScriptsUnchanged $Scripts
    [Console]::Out.Write('{"schema":1,"status":"P3_DISTRIBUTION_EVIDENCE_VERIFIED","payload_row_count":15045,"payload_root_sha256":"'+$payloadRoot+'","payload_manifest_sha256":"'+$payloadSha+'","distribution_receipt_sha256":"'+$receiptSha+'","sbom_sha256":"'+$sbom.Sha256+'","notices_sha256":"'+$artifacts.Sha256+'"}');exit 0
}

try{
    if($script:P3Role-notin@('SBOM','NOTICES','PAYLOAD','VERIFY')){Stop-P3 9 'ROLE_INVALID'}
    $parameters=Get-P3Parameters $InvocationArguments;Assert-P3ParameterPins $parameters;$scripts=Get-P3ScriptPins $parameters;$identity=Assert-P3ExternalIdentity $parameters;$stage=Assert-P3AbsoluteDirectory $parameters['StageRoot'] 3 'STAGE_ROOT_INVALID';$anchors=Get-P3Anchors $stage $parameters
    switch($script:P3Role){'SBOM'{Invoke-P3Sbom $stage $anchors $identity $scripts $parameters}'NOTICES'{Invoke-P3Notices $stage $anchors $identity $scripts $parameters}'PAYLOAD'{Invoke-P3Payload $stage $anchors $identity $scripts $parameters}default{Invoke-P3Verify $stage $anchors $identity $scripts $parameters}}
}catch{
    $code=9;$detail='INTERNAL_ERROR';$current=$_.Exception
    while($null-ne$current){if($current.Data.Contains('P3Exit')){$code=[int]$current.Data['P3Exit'];$detail=[string]$current.Data['P3Detail'];break};$current=$current.InnerException}
    Emit-P3Failure $code $detail
}
