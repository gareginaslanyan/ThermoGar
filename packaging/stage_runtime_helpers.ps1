$InvocationArguments = [object[]]@($args)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$InformationPreference = 'SilentlyContinue'
$VerbosePreference = 'SilentlyContinue'
$DebugPreference = 'SilentlyContinue'

$Invariant = [Globalization.CultureInfo]::InvariantCulture
$StrictUtf8 = [Text.UTF8Encoding]::new($false, $true)
$P0Root = '42455F51E284BAD35F5BFD4971F5099889A2A0D4518FFB95310FC5C400461F7F'
$RuntimeFileCount = [int64]15003
$RuntimeTotalBytes = [int64]575844438
$RuntimeRoot = '58F81C014DF3C3E8AA6F85517BCEE4263C0AE751365B53CA0ED197964538121C'
$NativeRoot = 'A08EC90744637E0CFE3F7E72D8F4564F58D37C190704B660F4267AF02616604C'
$StageContentRoot = '06E8916AEE3BA5EBEF6CF9EBDB4B2B203B90C7A8A01B09645861B071FAD7DD57'
$P1AStageReceiptSha = '255FD7DB4613E646E158713639EA83353D81F2283CD3E775093DB6189997209B'
$NoticeRoot = 'DAFF95A316054B509313B3F2BF296C38F00FC7EDAD1CC1C4D27DB0C4FD9B9266'
$MetadataPins = [ordered]@{
    'manifests/project-source-manifest.json' = @([int64]4226, '7A633DEDD035BF992B1A88381123799AD0CCC991996A8AF43724620108D27874')
    'manifests/runtime-input-manifest.json' = @([int64]2453896, '76A87C3770F250A9044F3660218BE905EC27FD427C5861A0C5D58AC75B4D2761')
    'manifests/native-closure-receipt.json' = @([int64]774156, '1E1D080B48D1A280006025AC9CF64AD1BB536C54329FEFB56175940190324552')
    'manifests/p1a-stage-receipt.json' = @([int64]1315, $P1AStageReceiptSha)
}
$ScriptPins = [ordered]@{
    'stage_payload.ps1' = @([int64]42249, '61DE75ECC631442788CBBBABF4D91BA401B01791741D3ECB4F5620CB21AC5D3E')
    'verify_stage.ps1' = @([int64]69784, '87BC14D8EC220FA9ED99593C7C4D0D601F0658BAA1A6A815AA6AD77CBC6B09EE')
    'verify_native_closure.ps1' = @([int64]51537, '502963F6669E109C51CAD2C1427B4751C049E37E8423CE9C6DE49768059657F1')
}
$HelperPins = [ordered]@{
    'launcher.pyw' = @([int64]65359, 'B45DAD87139667604E3C3F4AD8F0D2307E2B0D2C86D220736286498F3389FE0A')
    'stop.pyw' = @([int64]7430, 'AA2087AFF494FF007E4C12CFE0949BB62384A2251883D51765EA3D424D70A286')
    'healthcheck.py' = @([int64]38059, 'ABCDE7BDEFC84DE9E91CA62D6A64F07129B1796C298C4AD4BB9ECC894B9CDB67')
}

function Initialize-NativeTypes {
    if ($null -ne ('ThermoGar.P1BHelperFileInfo' -as [type])) {
        return
    }
    $null = Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
namespace ThermoGar {
    [StructLayout(LayoutKind.Sequential)]
    public struct P1BHelperFileInfo {
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
    public static class P1BHelperNative {
        [DllImport("kernel32.dll", SetLastError=true)]
        public static extern bool GetFileInformationByHandle(
            SafeFileHandle handle, out P1BHelperFileInfo info);
    }
}
'@
}

function Stop-P1B { param([int]$Code,[string]$Message) $e=[InvalidOperationException]::new($Message);$e.Data['P1BExit']=$Code;throw $e }
function Assert-Sha { param([string]$Value,[string]$Name,[int]$Code=3) if($Value -cnotmatch '^[A-F0-9]{64}$'){Stop-P1B $Code "invalid SHA $Name"} }
function Test-Reparse { param([IO.FileSystemInfo]$Item) return [bool]($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) }
function Assert-PlainDirectoryInfo { param([IO.DirectoryInfo]$Item,[string]$Label,[int]$Code=4) $Item.Refresh();if(-not$Item.Exists-or(Test-Reparse $Item)){Stop-P1B $Code "$Label is not a plain directory"} }
function Assert-PlainFileInfo { param([IO.FileInfo]$Item,[string]$Label,[int]$Code=4) $Item.Refresh();if(-not$Item.Exists-or(Test-Reparse $Item)){Stop-P1B $Code "$Label is not a plain file"} }

function Get-ExactInvocationMap {
    param([object[]]$Tokens,[string[]]$Allowed)
    if($Tokens.Count-ne($Allowed.Count*2)){Stop-P1B 2 'wrong argument count'}
    $allowedSet=[Collections.Generic.HashSet[string]]::new($Allowed,[StringComparer]::Ordinal)
    $result=[Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    for($i=0;$i-lt$Tokens.Count;$i+=2){$label=[string]$Tokens[$i];if(-not$label.StartsWith('-',[StringComparison]::Ordinal)-or$label.Length-lt2){Stop-P1B 2 'positional argument'};$name=$label.Substring(1);if((-not $allowedSet.Contains($name))-or(-not $result.TryAdd($name,[string]$Tokens[$i+1]))){Stop-P1B 2 'unknown or duplicate argument'}}
    return $result
}

function Get-CanonicalInt64 { param([string]$Value,[string]$Name) if($Value-cnotmatch'^(0|[1-9][0-9]*)$'){Stop-P1B 2 "invalid integer $Name"};$parsed=[int64]0;if(-not[int64]::TryParse($Value,[Globalization.NumberStyles]::None,$Invariant,[ref]$parsed)){Stop-P1B 2 "invalid integer $Name"};return $parsed }

function Assert-AbsoluteDirectory {
    param([string]$Path,[string]$Label)
    if([string]::IsNullOrWhiteSpace($Path)-or$Path.StartsWith('\\',[StringComparison]::Ordinal)-or[Management.Automation.WildcardPattern]::ContainsWildcardCharacters($Path)-or(-not [IO.Path]::IsPathFullyQualified($Path))){Stop-P1B 3 "$Label is not canonical absolute"}
    $full=[IO.Path]::GetFullPath($Path);if($full-cne$Path-or$full-ceq[IO.Path]::GetPathRoot($full)){Stop-P1B 3 "$Label is not canonical absolute"}
    $root=[IO.Path]::GetPathRoot($full);$current=[IO.DirectoryInfo]::new($root);Assert-PlainDirectoryInfo $current "$Label root" 3
    foreach($segment in $full.Substring($root.Length).Split([IO.Path]::DirectorySeparatorChar)){if([string]::IsNullOrEmpty($segment)){continue};$matches=@($current.EnumerateFileSystemInfos()|Where-Object{$_.Name.Equals($segment,[StringComparison]::OrdinalIgnoreCase)});if($matches.Count-ne1-or$matches[0].Name-cne$segment-or$matches[0]-isnot[IO.DirectoryInfo]){Stop-P1B 3 "$Label path collision"};$current=[IO.DirectoryInfo]$matches[0];Assert-PlainDirectoryInfo $current $Label 3}
    return $current.FullName
}

function Assert-RelativePath { param([string]$Path,[int]$Code=4) if([string]::IsNullOrEmpty($Path)-or$Path.StartsWith('/')-or$Path.EndsWith('/')-or$Path.Contains('//')-or$Path.Contains('\')-or$Path.Contains(':')-or$Path.Contains('|')-or$Path-cmatch'[\x00-\x1F\x7F]'){Stop-P1B $Code "invalid relative path $Path"};foreach($part in $Path.Split('/')){if($part-ceq'.'-or$part-ceq'..'-or$part.EndsWith('.')-or$part.EndsWith(' ')){Stop-P1B $Code "invalid relative path $Path"}} }
function Get-HandleIdentity { param([IO.FileStream]$Stream,[int]$Code) $info=[ThermoGar.P1BHelperFileInfo]::new();if(-not[ThermoGar.P1BHelperNative]::GetFileInformationByHandle($Stream.SafeFileHandle,[ref]$info)){Stop-P1B $Code 'file identity failure'};return '{0:X8}:{1:X8}{2:X8}'-f$info.VolumeSerialNumber,$info.FileIndexHigh,$info.FileIndexLow }
function Get-Hash { param([byte[]]$Bytes) return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes)) }

function Read-StableFile {
    param([string]$Path,[string]$Label,[int]$Code=4,[int64]$Maximum=[int64]::MaxValue)
    $before=[IO.FileInfo]::new($Path);Assert-PlainFileInfo $before $Label $Code;if($before.Length-gt$Maximum){Stop-P1B $Code "$Label oversized"}
    $stream=[IO.FileStream]::new($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try{$identity=Get-HandleIdentity $stream $Code;$memory=[IO.MemoryStream]::new();try{$stream.CopyTo($memory);$bytes=$memory.ToArray()}finally{$memory.Dispose()};$after=[IO.FileInfo]::new($Path);Assert-PlainFileInfo $after $Label $Code;if($before.Length-ne$after.Length-or$before.LastWriteTimeUtc.Ticks-ne$after.LastWriteTimeUtc.Ticks-or$stream.Length-ne$bytes.LongLength-or(Get-HandleIdentity $stream $Code)-cne$identity){Stop-P1B $Code "unstable $Label"}}finally{$stream.Dispose()}
    return [pscustomobject]@{Bytes=[int64]$bytes.LongLength;Sha256=(Get-Hash $bytes);Raw=$bytes}
}

function Resolve-ExactFile {
    param([string]$Root,[string]$Relative,[int]$Code=4)
    Assert-RelativePath $Relative $Code;$current=[IO.DirectoryInfo]::new($Root);$parts=$Relative.Split('/')
    for($i=0;$i-lt$parts.Count;$i++){$matches=@($current.EnumerateFileSystemInfos()|Where-Object{$_.Name.Equals($parts[$i],[StringComparison]::OrdinalIgnoreCase)});if($matches.Count-ne1-or$matches[0].Name-cne$parts[$i]){Stop-P1B $Code "path collision $Relative"};if($i-lt$parts.Count-1){if($matches[0]-isnot[IO.DirectoryInfo]){Stop-P1B $Code "parent type $Relative"};$current=[IO.DirectoryInfo]$matches[0];Assert-PlainDirectoryInfo $current $Relative $Code}else{if($matches[0]-isnot[IO.FileInfo]){Stop-P1B $Code "file type $Relative"};$file=[IO.FileInfo]$matches[0];Assert-PlainFileInfo $file $Relative $Code;return $file.FullName}}
    Stop-P1B $Code "unresolved $Relative"
}

function Read-JsonSnapshot { param([string]$Path,[string]$Label,[int64]$Maximum=67108864) $s=Read-StableFile $Path $Label 4 $Maximum;if($s.Raw.Length-ge3-and$s.Raw[0]-eq0xEF-and$s.Raw[1]-eq0xBB-and$s.Raw[2]-eq0xBF){Stop-P1B 4 "$Label BOM"};try{$text=$StrictUtf8.GetString($s.Raw)}catch{Stop-P1B 4 "$Label UTF-8"};if($text.EndsWith("`r")-or$text.EndsWith("`n")){Stop-P1B 4 "$Label newline"};return [pscustomobject]@{Bytes=$s.Bytes;Sha256=$s.Sha256;Raw=$s.Raw;Text=$text} }
function Open-Json { param([string]$Text) $o=[Text.Json.JsonDocumentOptions]::new();$o.AllowTrailingCommas=$false;$o.CommentHandling=[Text.Json.JsonCommentHandling]::Disallow;$o.MaxDepth=64;try{return [Text.Json.JsonDocument]::Parse($Text,$o)}catch{Stop-P1B 4 'malformed JSON'} }
function Json-String { param([Text.Json.JsonElement]$Object,[string]$Name) $v=[Text.Json.JsonElement]::new();if(-not$Object.TryGetProperty($Name,[ref]$v)-or$v.ValueKind-ne[Text.Json.JsonValueKind]::String){Stop-P1B 4 "JSON string $Name"};return $v.GetString() }
function Json-Int { param([Text.Json.JsonElement]$Object,[string]$Name) $v=[Text.Json.JsonElement]::new();if(-not$Object.TryGetProperty($Name,[ref]$v)-or$v.ValueKind-ne[Text.Json.JsonValueKind]::Number){Stop-P1B 4 "JSON integer $Name"};$n=[int64]0;if(-not$v.TryGetInt64([ref]$n)-or$v.GetRawText()-cne$n.ToString($Invariant)-or$n-lt0){Stop-P1B 4 "JSON integer $Name"};return $n }

function Parse-ManifestRows {
    param([object]$Snapshot,[string]$Kind)
    $doc=Open-Json $Snapshot.Text
    try {
        $root=$doc.RootElement
        $rowsElement=[Text.Json.JsonElement]::new()
        if((-not $root.TryGetProperty('rows',[ref]$rowsElement))-or$rowsElement.ValueKind-ne[Text.Json.JsonValueKind]::Array){Stop-P1B 4 "$Kind rows"}
        $rows=[Collections.Generic.List[object]]::new()
        $exact=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        $fold=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        $previous=$null
        $sum=[int64]0
        foreach($row in $rowsElement.EnumerateArray()){
            $path=Json-String $row 'path';$bytes=Json-Int $row 'bytes';$sha=Json-String $row 'sha256'
            Assert-RelativePath $path 4;Assert-Sha $sha "$Kind row" 4
            if((-not $exact.Add($path))-or(-not $fold.Add($path))-or($null-ne$previous-and[StringComparer]::Ordinal.Compare($previous,$path)-ge0)){Stop-P1B 4 "$Kind row order"}
            if($sum-gt([int64]::MaxValue-$bytes)){Stop-P1B 4 "$Kind total"}
            $sum+=$bytes
            $rows.Add([pscustomobject]@{Path=$path;Bytes=$bytes;Sha256=$sha})
            $previous=$path
        }
        $declaredCount=Json-Int $root 'row_count';$declaredTotal=Json-Int $root 'total_bytes'
        if($declaredCount-ne$rows.Count-or$declaredTotal-ne$sum){Stop-P1B 4 "$Kind counts"}
        $properties=[ordered]@{}
        foreach($name in @('project_root_sha256','runtime_root_sha256','producer_sha256','dist_info_count','notice_path_count','notice_path_root_sha256')){
            $value=[Text.Json.JsonElement]::new()
            if($root.TryGetProperty($name,[ref]$value)){
                if($value.ValueKind-eq[Text.Json.JsonValueKind]::String){$properties[$name]=$value.GetString()}
                elseif($value.ValueKind-eq[Text.Json.JsonValueKind]::Number){$properties[$name]=Json-Int $root $name}
                else{Stop-P1B 4 "$Kind property $name"}
            }
        }
        return [pscustomobject]@{Rows=($rows.ToArray());Count=[int64]$rows.Count;Total=$sum;Properties=$properties}
    }
    finally{$doc.Dispose()}
}

function Assert-Anchors {
    param([string]$Stage)
    $result=[ordered]@{}
    foreach($relative in $MetadataPins.Keys){$pin=$MetadataPins[$relative];$snapshot=Read-JsonSnapshot (Resolve-ExactFile $Stage $relative 4) $relative ([int64]$pin[0]);if($snapshot.Bytes-ne[int64]$pin[0]-or$snapshot.Sha256-cne[string]$pin[1]){Stop-P1B 4 "metadata identity $relative"};$result[$relative]=$snapshot}
    foreach($name in $ScriptPins.Keys){$pin=$ScriptPins[$name];$snapshot=Read-StableFile ([IO.Path]::Combine($PSScriptRoot,$name)) $name 4 ([int64]$pin[0]);if($snapshot.Bytes-ne[int64]$pin[0]-or$snapshot.Sha256-cne[string]$pin[1]){Stop-P1B 4 "script identity $name"};$result[$name]=$snapshot}
    $project=Parse-ManifestRows $result['manifests/project-source-manifest.json'] 'project';$runtime=Parse-ManifestRows $result['manifests/runtime-input-manifest.json'] 'runtime'
    if($project.Count-ne29-or$project.Total-ne2674489-or$project.Properties['project_root_sha256']-cne$P0Root-or$project.Properties['producer_sha256']-cne[string]$ScriptPins['stage_payload.ps1'][1]){Stop-P1B 4 'project manifest cross-binding'}
    if($runtime.Count-ne$RuntimeFileCount-or$runtime.Total-ne$RuntimeTotalBytes-or$runtime.Properties['runtime_root_sha256']-cne$RuntimeRoot-or$runtime.Properties['producer_sha256']-cne[string]$ScriptPins['stage_payload.ps1'][1]-or[int64]$runtime.Properties['dist_info_count']-ne99-or[int64]$runtime.Properties['notice_path_count']-ne131-or$runtime.Properties['notice_path_root_sha256']-cne$NoticeRoot){Stop-P1B 4 'runtime manifest cross-binding'}
    $stageDoc=Open-Json $result['manifests/p1a-stage-receipt.json'].Text;try{$sr=$stageDoc.RootElement;if((Json-String $sr 'project_manifest_sha256')-cne[string]$MetadataPins['manifests/project-source-manifest.json'][1]-or(Json-String $sr 'runtime_manifest_sha256')-cne[string]$MetadataPins['manifests/runtime-input-manifest.json'][1]-or(Json-String $sr 'native_receipt_sha256')-cne[string]$MetadataPins['manifests/native-closure-receipt.json'][1]-or(Json-String $sr 'project_root_sha256')-cne$P0Root-or(Json-String $sr 'runtime_root_sha256')-cne$RuntimeRoot-or(Json-String $sr 'native_closure_root_sha256')-cne$NativeRoot-or(Json-Int $sr 'native_row_count')-ne3142-or(Json-Int $sr 'native_total_bytes')-ne3224678344-or(Json-Int $sr 'notice_path_count')-ne131-or(Json-String $sr 'notice_path_root_sha256')-cne$NoticeRoot-or(Json-String $sr 'stage_content_root_sha256')-cne$StageContentRoot-or(Json-Int $sr 'project_row_count')-ne29-or(Json-Int $sr 'project_total_bytes')-ne2674489-or(Json-Int $sr 'runtime_row_count')-ne$RuntimeFileCount-or(Json-Int $sr 'runtime_total_bytes')-ne$RuntimeTotalBytes-or(Json-Int $sr 'stage_content_row_count')-ne15032-or(Json-Int $sr 'stage_content_total_bytes')-ne578518927-or(Json-String $sr 'stage_payload_sha256')-cne[string]$ScriptPins['stage_payload.ps1'][1]-or(Json-String $sr 'verify_stage_sha256')-cne[string]$ScriptPins['verify_stage.ps1'][1]-or(Json-String $sr 'native_script_sha256')-cne[string]$ScriptPins['verify_native_closure.ps1'][1]){Stop-P1B 4 'stage receipt cross-binding'}}finally{$stageDoc.Dispose()}
    $nativeDoc=Open-Json $result['manifests/native-closure-receipt.json'].Text;try{$nr=$nativeDoc.RootElement;if((Json-String $nr 'runtime_input_manifest_sha256')-cne[string]$MetadataPins['manifests/runtime-input-manifest.json'][1]-or(Json-String $nr 'native_closure_root_sha256')-cne$NativeRoot-or(Json-Int $nr 'row_count')-ne3142-or(Json-Int $nr 'total_bytes')-ne3224678344-or(Json-String $nr 'producer_sha256')-cne[string]$ScriptPins['verify_native_closure.ps1'][1]-or(Json-String $nr 'verifier_sha256')-cne[string]$ScriptPins['verify_native_closure.ps1'][1]){Stop-P1B 4 'native receipt cross-binding'}}finally{$nativeDoc.Dispose()}
    return [pscustomobject]@{Project=$project;Runtime=$runtime;Snapshots=$result}
}

function Get-AllEntries {
    param([string]$Root)
    $files=[Collections.Generic.List[string]]::new();$dirs=[Collections.Generic.List[string]]::new();$fold=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase);$queue=[Collections.Generic.Queue[object]]::new();$queue.Enqueue([pscustomobject]@{Directory=[IO.DirectoryInfo]::new($Root);Relative=''})
    while($queue.Count-gt0){$node=$queue.Dequeue();Assert-PlainDirectoryInfo $node.Directory 'stage directory' 6;foreach($item in $node.Directory.EnumerateFileSystemInfos()){$relative=if($node.Relative-ceq''){$item.Name}else{$node.Relative+'/'+$item.Name};Assert-RelativePath $relative 6;if((Test-Reparse $item)-or(-not $fold.Add($relative))){Stop-P1B 6 'stage reparse or collision'};if($item-is[IO.DirectoryInfo]){$dirs.Add($relative);$queue.Enqueue([pscustomobject]@{Directory=[IO.DirectoryInfo]$item;Relative=$relative})}elseif($item-is[IO.FileInfo]){$files.Add($relative)}else{Stop-P1B 6 'stage nonregular item'}}}
    $fa=$files.ToArray();$da=$dirs.ToArray();[Array]::Sort($fa,[StringComparer]::Ordinal);[Array]::Sort($da,[StringComparer]::Ordinal);return [pscustomobject]@{Files=$fa;Directories=$da}
}
function Expected-Directories { param([string[]]$Paths) $set=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal);foreach($path in $Paths){$slash=$path.LastIndexOf('/');while($slash-gt0){$parent=$path.Substring(0,$slash);$null=$set.Add($parent);$slash=$parent.LastIndexOf('/')}};$a=[string[]]@($set);[Array]::Sort($a,[StringComparer]::Ordinal);return $a }
function Assert-EqualPaths { param([string[]]$Actual,[string[]]$Expected) $copy=[string[]]$Expected.Clone();[Array]::Sort($copy,[StringComparer]::Ordinal);if($Actual.Count-ne$copy.Count){Stop-P1B 6 'membership count'};for($i=0;$i-lt$copy.Count;$i++){if($Actual[$i]-cne$copy[$i]){Stop-P1B 6 'membership mismatch'}} }

function Get-BaseExpectedPaths {
    param([object]$Anchors)
    $expected=[Collections.Generic.List[string]]::new()
    foreach($row in $Anchors.Project.Rows){$expected.Add($row.Path)}
    foreach($row in $Anchors.Runtime.Rows){$expected.Add($row.Path)}
    foreach($relative in $MetadataPins.Keys){$expected.Add($relative)}
    return $expected.ToArray()
}

function Assert-BaseMembership {
    param([string]$Stage,[object]$Anchors)
    $expected=Get-BaseExpectedPaths $Anchors
    $entries=Get-AllEntries $Stage
    Assert-EqualPaths $entries.Files $expected
    Assert-EqualPaths $entries.Directories (Expected-Directories $expected)
    if($entries.Files.Count-ne15036-or$entries.Directories.Count-ne1462){Stop-P1B 6 'base membership counts'}
}

function Assert-ExecutionRows {
    param([string]$Stage,[object[]]$Rows)
    foreach($row in $Rows){
        $physical=Read-StableFile (Resolve-ExactFile $Stage $row.Path 6) $row.Path 6 $row.Bytes
        if($physical.Bytes-ne$row.Bytes-or$physical.Sha256-cne$row.Sha256){Stop-P1B 6 "base row $($row.Path)"}
    }
}

function Invoke-NativeVerify {
    param([string]$Stage)
    $hostPath=[Environment]::ProcessPath;$hostBefore=Read-StableFile $hostPath 'PowerShell host' 7 268435456;$script=[IO.Path]::Combine($PSScriptRoot,'verify_native_closure.ps1');$scriptBefore=Read-StableFile $script 'native verifier' 7 67108864
    $psi=[Diagnostics.ProcessStartInfo]::new();$psi.FileName=$hostPath;$psi.UseShellExecute=$false;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.CreateNoWindow=$true
    foreach($arg in @('-NoLogo','-NoProfile','-NonInteractive','-File',$script,'-StageRoot',$Stage,'-Mode','Verify','-ExpectedP0Root',$P0Root,'-ExpectedRuntimeFileCount','15003','-ExpectedRuntimeTotalBytes','575844438','-ExpectedRuntimeDistInfoCount','99','-ExpectedRuntimeNoticePathCount','131','-ExpectedRuntimeNoticePathRoot',$NoticeRoot)){$psi.ArgumentList.Add($arg)}
    $process=[Diagnostics.Process]::new();$process.StartInfo=$psi;try{if(-not$process.Start()){Stop-P1B 7 'native verifier start'};$stdout=$process.StandardOutput.ReadToEnd();$stderr=$process.StandardError.ReadToEnd();$process.WaitForExit();$exit=$process.ExitCode}finally{$process.Dispose()}
    $expected='{"schema":1,"status":"P1A_NATIVE_VERIFIED","native_closure_root_sha256":"'+$NativeRoot+'","native_row_count":3142,"native_total_bytes":3224678344,"stage_content_root_sha256":"'+$StageContentRoot+'"}'
    if($exit-ne0-or-not[string]::IsNullOrEmpty($stderr)-or$stdout-cne$expected){Stop-P1B 7 'native verifier result'}
    $hostAfter=Read-StableFile $hostPath 'PowerShell host' 7 268435456;$scriptAfter=Read-StableFile $script 'native verifier' 7 67108864;if($hostAfter.Bytes-ne$hostBefore.Bytes-or$hostAfter.Sha256-cne$hostBefore.Sha256-or$scriptAfter.Bytes-ne$scriptBefore.Bytes-or$scriptAfter.Sha256-cne$scriptBefore.Sha256){Stop-P1B 7 'native verifier identity changed'}
}

function Read-HelperSources {
    $sources=[ordered]@{}
    foreach($name in $HelperPins.Keys){
        $pin=$HelperPins[$name]
        $source=Read-StableFile ([IO.Path]::Combine($PSScriptRoot,$name)) $name 5 ([int64]$pin[0])
        if($source.Bytes-ne[int64]$pin[0]-or$source.Sha256-cne[string]$pin[1]){Stop-P1B 5 "helper source $Name"}
        $sources[$name]=$source
    }
    return $sources
}

function Assert-HelperDestinationsAbsent {
    param([string]$Stage)
    $root=[IO.DirectoryInfo]::new($Stage)
    foreach($name in $HelperPins.Keys){
        $matches=@($root.EnumerateFileSystemInfos()|Where-Object{$_.Name.Equals($name,[StringComparison]::OrdinalIgnoreCase)})
        if($matches.Count-ne0){Stop-P1B 8 "helper collision $Name"}
    }
}

function Publish-Helper {
    param([string]$Stage,[string]$Name,[object]$Source)
    $pin=$HelperPins[$Name]
    $sourcePath=[IO.Path]::Combine($PSScriptRoot,$Name)
    $destination=[IO.Path]::Combine($Stage,$Name)
    $stream=$null
    try{$stream=[IO.FileStream]::new($destination,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None);$stream.Write($Source.Raw,0,$Source.Raw.Length);$stream.Flush($true)}catch [IO.IOException]{Stop-P1B 8 "helper publish $Name"}finally{if($null-ne$stream){$stream.Dispose()}}
    $observed=Read-StableFile $destination $Name 6 ([int64]$pin[0])
    $sourceAfter=Read-StableFile $sourcePath $Name 5 ([int64]$pin[0])
    if($observed.Bytes-ne$Source.Bytes-or$observed.Sha256-cne$Source.Sha256-or$sourceAfter.Bytes-ne$Source.Bytes-or$sourceAfter.Sha256-cne$Source.Sha256){Stop-P1B 6 "helper destination $Name"}
}

function Emit-Failure { param([int]$Code) $map=@('','','USAGE','INPUT_INVALID','STAGE_INVALID','POLICY_INVALID','RUNTIME_INVALID','NATIVE_INVALID','IO_CONFLICT','INTERNAL_ERROR');if($Code-lt2-or$Code-gt9){$Code=9};[Console]::Out.Write('{"schema":1,"status":"'+$map[$Code]+'","detail_code":'+$Code.ToString($Invariant)+'}');exit $Code }

try {
    $p=Get-ExactInvocationMap $InvocationArguments @('StageRoot','ExpectedP0Root','ExpectedRuntimeFileCount','ExpectedRuntimeTotalBytes','ExpectedRuntimeRootSha256','ExpectedP1AStageReceiptSha256','P1AStageReceiptPath')
    foreach($name in $p.Keys){if([string]::IsNullOrEmpty($p[$name])){Stop-P1B 2 'empty parameter'}}
    Assert-Sha $p['ExpectedP0Root'] 'ExpectedP0Root' 2;Assert-Sha $p['ExpectedRuntimeRootSha256'] 'ExpectedRuntimeRootSha256' 2;Assert-Sha $p['ExpectedP1AStageReceiptSha256'] 'ExpectedP1AStageReceiptSha256' 2
    if($p['ExpectedP0Root']-cne$P0Root-or(Get-CanonicalInt64 $p['ExpectedRuntimeFileCount'] 'ExpectedRuntimeFileCount')-ne$RuntimeFileCount-or(Get-CanonicalInt64 $p['ExpectedRuntimeTotalBytes'] 'ExpectedRuntimeTotalBytes')-ne$RuntimeTotalBytes-or$p['ExpectedRuntimeRootSha256']-cne$RuntimeRoot-or$p['ExpectedP1AStageReceiptSha256']-cne$P1AStageReceiptSha){Stop-P1B 3 'expected pins'}
    Initialize-NativeTypes
    $stage=Assert-AbsoluteDirectory $p['StageRoot'] 'StageRoot';$expectedReceipt=[IO.Path]::Combine($stage,'manifests','p1a-stage-receipt.json');if($p['P1AStageReceiptPath']-cne$expectedReceipt){Stop-P1B 3 'receipt path'}
    $anchors=Assert-Anchors $stage;if($anchors.Snapshots['manifests/p1a-stage-receipt.json'].Sha256-cne$p['ExpectedP1AStageReceiptSha256']){Stop-P1B 4 'receipt pin'}
    Assert-BaseMembership $stage $anchors
    Invoke-NativeVerify $stage
    $anchorsAfterChild=Assert-Anchors $stage
    foreach($relative in $MetadataPins.Keys){if($anchorsAfterChild.Snapshots[$relative].Sha256-cne$anchors.Snapshots[$relative].Sha256){Stop-P1B 4 'anchor changed after child'}}
    Assert-BaseMembership $stage $anchorsAfterChild
    Assert-ExecutionRows $stage (@($anchorsAfterChild.Project.Rows)+@($anchorsAfterChild.Runtime.Rows))
    $helperSources=Read-HelperSources
    Assert-HelperDestinationsAbsent $stage
    foreach($name in @('launcher.pyw','stop.pyw','healthcheck.py')){Publish-Helper $stage $name $helperSources[$name]}
    $expected=[Collections.Generic.List[string]]::new();foreach($row in $anchors.Project.Rows){$expected.Add($row.Path)};foreach($row in $anchors.Runtime.Rows){$expected.Add($row.Path)};foreach($relative in $MetadataPins.Keys){$expected.Add($relative)};foreach($name in $HelperPins.Keys){$expected.Add($name)}
    Assert-ExecutionRows $stage (@($anchors.Project.Rows)+@($anchors.Runtime.Rows))
    foreach($name in $HelperPins.Keys){$pin=$HelperPins[$name];$physical=Read-StableFile (Resolve-ExactFile $stage $name 6) $name 6 ([int64]$pin[0]);if($physical.Bytes-ne[int64]$pin[0]-or$physical.Sha256-cne[string]$pin[1]){Stop-P1B 6 "helper row $name"}}
    $entries=Get-AllEntries $stage;Assert-EqualPaths $entries.Files $expected.ToArray();Assert-EqualPaths $entries.Directories (Expected-Directories $expected.ToArray());if($entries.Files.Count-ne15039-or$entries.Directories.Count-ne1462){Stop-P1B 6 'overlay counts'}
    $null=Assert-Anchors $stage
    [Console]::Out.Write('{"schema":1,"status":"P1B_HELPERS_STAGED","helper_row_count":3,"launcher_sha256":"'+[string]$HelperPins['launcher.pyw'][1]+'","stop_sha256":"'+[string]$HelperPins['stop.pyw'][1]+'","healthcheck_sha256":"'+[string]$HelperPins['healthcheck.py'][1]+'"}');exit 0
} catch {
    $code=9;if($null-ne$_.Exception-and$_.Exception.Data.Contains('P1BExit')){$code=[int]$_.Exception.Data['P1BExit']};Emit-Failure $code
}
