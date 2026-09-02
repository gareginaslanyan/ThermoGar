[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ExpectedRoot = '42455F51E284BAD35F5BFD4971F5099889A2A0D4518FFB95310FC5C400461F7F'
$ExpectedRowCount = 29
$ExpectedTotalBytes = [int64]2674489
$ExpectedEntrypoint = 'app/ThermoGar_app.py'
$ExpectedRows = [string[]](@'
.streamlit/config.toml|1753|6F8D7F251505756B6B67ED1DFC03E1846EFC3FA4B2746D84870DC47F828A1AAA
app/ThermoGar_app.py|430274|7008975720C0EBFDF2D087BCAFE235437D17EC41BC75ED7202B0EBFD8D16A931
app/style.css|954|AA562CD0532A6310C9BD0A562353DA460D2BD2CFEFB0E6ECDB81CF1C62AAC397
app/thermogar_database_guard.py|16389|78C432940CAD6E6450987C14903284EADB77BA7C7E961DB374AE0D117FD3374F
app/thermogar_diffusion.py|58369|7386C1F702F9C0C2D1C92C2DAD55817F33010C56497EFF41F5B414147C6971D9
app/thermogar_ne04_domain.py|16077|2220D3D1AE584CF507CAD28EA092F418A187267936E1B137A8D38DE499CF61BD
app/thermogar_palette.py|2568|060D2457701F5EFFB2F74ACAF2537F7B0549AD3FF97900FFEF6C0FD7E5B628D3
app/thermogar_paths.py|27177|1A835474D3E247B8A2E8181627D951B6D5773E5E0CD2863D3EDA299A5B55C2E6
app/thermogar_physical.py|45274|7F7059C35774FC5CC106DE77738D95973B852790272248B806EBBCC2B46ABD5F
app/thermogar_precipitation.py|52617|1E0C4679ED4404EF0FEE93479F34676DEAAE72C87F873955200913E950544619
app/thermogar_properties.py|83448|E6D6AECE5EC5778D98CAEC6568E6158F5CD6033E172F56A58CCC5A0C62B1E73B
app/thermogar_release_policy.py|20419|E818F1AAA03B2218856E8F75EAD1D864C612B35F7528A7CC98EF6607288B2290
app/thermogar_release_ui.py|7619|601746806216A83DF4580354A4641C5A7268E2A713A80026A4F310A07D70DEE0
app/thermogar_restricted_fe_core.py|42515|DF5728FAE6E0760A00E641D13C78AA93570CA4147649853644A6D7BF333E12AB
app/thermogar_secure_io.py|36580|D62479E6B2CCC628C010935BE7D1B137B20B2D3D0D1749682B2F4B294D0428E4
app/thermogar_stage14.py|55052|BBADA4A2938CDE1D1014C5F4035A76B147D405F82A53513F268D6AB888F9AC6E
app/thermogar_verified_artifact.py|2606|9FD5935201514B373A36D86AB1DBC5BFE62133592D0F7A84CB62AB228DB30655
app/thermogar_verified_equilibrium.py|27782|52BB99B27BC032500889F6FA863689D6C85C020D8AD5C99FEAB10881A2D8C7D0
app/thermogar_verified_loaders.py|92357|4186E6A4F9AED53EEEEA36BBB72A0B18FD4326A473948FFC82A3B65C0B7F88B8
app/thermogar_verified_physical.py|23587|B68FA864E9C3878C8154D44CA2D04120A794856C7B96745D57450579D033A6F1
app/thermogar_verified_properties.py|44313|9C9AC7A4A04C6EE39A066802615E73EA0FBE4A69444C721B4567CDF340308D0A
app/thermogar_verified_state.py|52698|45FFD8AFE5539CA21F21EAF17DA4378142BA88F973D8E346818905E539A2DBFC
app/thermogar_workspace.py|91706|2D8B278EE2731917E0C1465CEB8B37EE8EE5C09BDC5E2768136063F67D2CC5E6
configs/ne04_database_domains.json|15855|2D588FE38A0F7C2C746B60E49D0C029A17721665400290233A0A22EC79DB7204
databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb|351241|F9BDF21D434FBE78B5EF3F7F2DE69763FA40B81335CDC58889907D41C80CD717
databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.passport.json|12393|C818F3132840304EA38017CB7419790A290A1CA2E949B01E8954931AC8F17491
databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb|568690|236EC4D9B0540DE04E4E6305FAA208672F31FBDF45B2AE84E92F80BD98053612
databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb|466074|1882D841A337063E0585D261C690AE7E565838234E231E21B8541A5CB0DBA391
databases/physical/original/physical_data_v103.pdb|28102|4CF81C992B57263C50B370EA47EB0D5BB4F622CF23C18479BAB54267762F20BD
'@ -split '\r?\n' | Where-Object { $_ -ne '' })
$ExpectedDeniedClasses = [string[]]@(
    'tools','work','reports','results','notebooks','tests','checkout','.venv*',
    'user_data','cache','templates','__pycache__','*.pyc','*.pyo',
    'alternate-entrypoints','upstream-fe','unpatched-fe','non-mobility-fe','diagnostic-fe'
)

function Stop-P0 { param([Parameter(Mandatory=$true)][string]$Message) throw [InvalidOperationException]::new("P0_POLICY_INVALID: $Message") }
function Get-UpperSha256FromBytes {
    param([Parameter(Mandatory=$true)][byte[]]$Bytes)
    $hasher=[Security.Cryptography.SHA256]::Create()
    try { return -join ($hasher.ComputeHash($Bytes)|ForEach-Object{$_.ToString('X2')}) } finally { $hasher.Dispose() }
}
function Get-UpperSha256FromStream {
    param([Parameter(Mandatory=$true)][IO.Stream]$Stream)
    $hasher=[Security.Cryptography.SHA256]::Create()
    try { return -join ($hasher.ComputeHash($Stream)|ForEach-Object{$_.ToString('X2')}) } finally { $hasher.Dispose() }
}
function Assert-PlainItem {
    param([Parameter(Mandatory=$true)][IO.FileSystemInfo]$Item,[Parameter(Mandatory=$true)][bool]$DirectoryExpected,[Parameter(Mandatory=$true)][string]$Label)
    if([bool]($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)){ Stop-P0 "$Label is a reparse point" }
    if($DirectoryExpected -and $Item -isnot [System.IO.DirectoryInfo]){ Stop-P0 "$Label is not a directory" }
    if(-not $DirectoryExpected -and $Item -isnot [System.IO.FileInfo]){ Stop-P0 "$Label is not a regular file" }
}
function Assert-ExactKeys {
    param([Parameter(Mandatory=$true)]$Object,[Parameter(Mandatory=$true)][string[]]$Expected,[Parameter(Mandatory=$true)][string]$Label)
    $actual=[string[]]@($Object.PSObject.Properties|ForEach-Object{$_.Name});$a=[string[]]$actual.Clone();$e=[string[]]$Expected.Clone()
    [Array]::Sort($a,[StringComparer]::Ordinal);[Array]::Sort($e,[StringComparer]::Ordinal)
    if($a.Count -ne $e.Count){ Stop-P0 "$Label has missing or extra fields" }
    for($i=0;$i -lt $e.Count;$i++){ if($a[$i] -cne $e[$i]){ Stop-P0 "$Label has missing or extra fields" } }
}
function Assert-ExactStringArray {
    param([Parameter(Mandatory=$true)]$Value,[Parameter(Mandatory=$true)][string[]]$Expected,[Parameter(Mandatory=$true)][string]$Label)
    $actual=[string[]]@($Value);if($actual.Count -ne $Expected.Count){ Stop-P0 "$Label has the wrong item count" }
    for($i=0;$i -lt $Expected.Count;$i++){ if($actual[$i] -cne $Expected[$i]){ Stop-P0 "$Label differs at index $i" } }
}
function Assert-NoJsonDuplicates {
    param([Parameter(Mandatory=$true)][Text.Json.JsonElement]$Element,[Parameter(Mandatory=$true)][string]$Location)
    if($Element.ValueKind -eq [Text.Json.JsonValueKind]::Object){
        $seen=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach($property in $Element.EnumerateObject()){
            if(-not $seen.Add($property.Name)){ Stop-P0 "duplicate JSON field $Location.$($property.Name)" }
            Assert-NoJsonDuplicates -Element $property.Value -Location "$Location.$($property.Name)"
        }
    } elseif($Element.ValueKind -eq [Text.Json.JsonValueKind]::Array){
        $i=0;foreach($child in $Element.EnumerateArray()){ Assert-NoJsonDuplicates -Element $child -Location "$Location[$i]";$i++ }
    }
}
function Resolve-PlainSourceFile {
    param([Parameter(Mandatory=$true)][string]$ProjectRoot,[Parameter(Mandatory=$true)][string]$RelativePath)
    if([string]::IsNullOrWhiteSpace($RelativePath)-or $RelativePath.Contains('\')-or $RelativePath.Contains(':')-or $RelativePath.StartsWith('/')-or [Management.Automation.WildcardPattern]::ContainsWildcardCharacters($RelativePath)){ Stop-P0 "invalid literal path $RelativePath" }
    $segments=$RelativePath.Split('/');if($segments.Count -eq 0 -or @($segments|Where-Object{$_ -eq '' -or $_ -eq '.' -or $_ -eq '..'}).Count -ne 0){ Stop-P0 "traversal or empty segment in $RelativePath" }
    $current=$ProjectRoot
    for($i=0;$i -lt $segments.Count;$i++){
        $segment=$segments[$i];$matches=@(Get-ChildItem -LiteralPath $current -Force|Where-Object{$_.Name -ieq $segment})
        if($matches.Count -ne 1 -or $matches[0].Name -cne $segment){ Stop-P0 "missing path, case mismatch, or casefold collision at $RelativePath" }
        $item=$matches[0];Assert-PlainItem -Item $item -DirectoryExpected:($i -lt ($segments.Count-1)) -Label $RelativePath;$current=$item.FullName
    }
    $prefix=$ProjectRoot.TrimEnd([IO.Path]::DirectorySeparatorChar)+[IO.Path]::DirectorySeparatorChar;$full=[IO.Path]::GetFullPath($current)
    if(-not $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){ Stop-P0 "path escapes project root: $RelativePath" };return $full
}

try {
    $scriptItem=Get-Item -LiteralPath $PSCommandPath -Force;Assert-PlainItem -Item $scriptItem -DirectoryExpected:$false -Label 'verifier'
    if($scriptItem.Name -cne 'verify_payload_policy.ps1'){ Stop-P0 'verifier filename is not canonical' }
    $packagingItem=$scriptItem.Directory;Assert-PlainItem -Item $packagingItem -DirectoryExpected:$true -Label 'packaging root'
    if($packagingItem.Name -cne 'packaging'){ Stop-P0 'packaging root is not canonical' }
    $projectItem=$packagingItem.Parent;Assert-PlainItem -Item $projectItem -DirectoryExpected:$true -Label 'project root';$projectRoot=$projectItem.FullName
    $policyPath=Join-Path $packagingItem.FullName 'payload-policy.json';$policyItem=Get-Item -LiteralPath $policyPath -Force;Assert-PlainItem -Item $policyItem -DirectoryExpected:$false -Label 'payload policy'
    if($policyItem.Name -cne 'payload-policy.json'){ Stop-P0 'policy filename is not canonical' }
    $policyBytes=[IO.File]::ReadAllBytes($policyPath)
    if($policyBytes.Count -ge 3 -and $policyBytes[0] -eq 0xEF -and $policyBytes[1] -eq 0xBB -and $policyBytes[2] -eq 0xBF){ Stop-P0 'policy must be UTF-8 without BOM' }
    $strictUtf8=[Text.UTF8Encoding]::new($false,$true);$policyText=$strictUtf8.GetString($policyBytes)
    $options=[Text.Json.JsonDocumentOptions]::new();$options.AllowTrailingCommas=$false;$options.CommentHandling=[Text.Json.JsonCommentHandling]::Disallow;$document=$null
    try{
        $document=[Text.Json.JsonDocument]::Parse($policyText,$options);Assert-NoJsonDuplicates -Element $document.RootElement -Location '$'
        $numericFields=[ordered]@{schema=[int64]1;version=[int64]1;row_count=[int64]29;total_bytes=[int64]2674489}
        foreach($name in $numericFields.Keys){
            $element=[Text.Json.JsonElement]::new();$expected=[int64]$numericFields[$name]
            if(-not $document.RootElement.TryGetProperty($name,[ref]$element) -or $element.ValueKind -ne [Text.Json.JsonValueKind]::Number){ Stop-P0 "top-level numeric token $name is invalid" }
            $value=[int64]0
            if(-not $element.TryGetInt64([ref]$value) -or $value -ne $expected -or $element.GetRawText() -cne $expected.ToString([Globalization.CultureInfo]::InvariantCulture)){ Stop-P0 "top-level numeric token $name is not the exact integer $expected" }
        }
    }finally{if($null -ne $document){$document.Dispose()}}
    $policy=$policyText|ConvertFrom-Json -Depth 50
    Assert-ExactKeys -Object $policy -Expected @('schema','version','algorithm','row_format','root_encoding','automatic_include','entrypoint','material_policy','denied_classes','rows','row_count','total_bytes','root_sha256') -Label 'policy'
    if($policy.schema -ne 1 -or $policy.version -ne 1){ Stop-P0 'schema or version mismatch' }
    if($policy.algorithm -cne 'SHA-256' -or $policy.row_format -cne 'path|bytes|UPPERCASE_SHA256' -or $policy.root_encoding -cne 'UTF-8-no-BOM;CRLF-no-terminal'){ Stop-P0 'algorithm or row serialization mismatch' }
    if($policy.automatic_include -isnot [bool] -or $policy.automatic_include){ Stop-P0 'automatic include must be exactly false' }
    if($policy.entrypoint -cne $ExpectedEntrypoint){ Stop-P0 'the sole entrypoint is not canonical' }
    Assert-ExactKeys -Object $policy.material_policy -Expected @('normal_material_keys','steel_database_key','steel_profile_key','steel_tdb_path','steel_tdb_sha256','steel_passport_path','steel_passport_sha256','excluded_phase','excluded_phase_policy','experimental_qualification','experimental_qualification_blocks_execution') -Label 'material_policy'
    Assert-ExactStringArray -Value $policy.material_policy.normal_material_keys -Expected @('ni','fe','al') -Label 'normal_material_keys'
    if($policy.material_policy.steel_database_key -cne 'fe' -or $policy.material_policy.steel_profile_key -cne 'thermogar_patch' -or $policy.material_policy.steel_tdb_path -cne 'databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb' -or $policy.material_policy.steel_tdb_sha256 -cne '236EC4D9B0540DE04E4E6305FAA208672F31FBDF45B2AE84E92F80BD98053612' -or $policy.material_policy.steel_passport_path -cne 'databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.passport.json' -or $policy.material_policy.steel_passport_sha256 -cne 'C818F3132840304EA38017CB7419790A290A1CA2E949B01E8954931AC8F17491' -or $policy.material_policy.excluded_phase -cne 'C15_LAVES' -or $policy.material_policy.excluded_phase_policy -cne 'excluded-and-rejected-before-side-effects' -or $policy.material_policy.experimental_qualification -cne 'NOT_PERFORMED' -or $policy.material_policy.experimental_qualification_blocks_execution -isnot [bool] -or $policy.material_policy.experimental_qualification_blocks_execution){ Stop-P0 'material policy mismatch' }
    Assert-ExactStringArray -Value $policy.denied_classes -Expected $ExpectedDeniedClasses -Label 'denied_classes'
    if(@($policy.rows).Count -ne $ExpectedRowCount -or $policy.row_count -ne $ExpectedRowCount){ Stop-P0 'row count mismatch' }
    if($policy.total_bytes -ne $ExpectedTotalBytes -or $policy.root_sha256 -cne $ExpectedRoot){ Stop-P0 'declared total or root mismatch' }
    $exact=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal);$fold=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase);$policyRows=[Collections.Generic.List[string]]::new();$policyTotal=[int64]0
    for($i=0;$i -lt $ExpectedRowCount;$i++){
        $row=@($policy.rows)[$i];Assert-ExactKeys -Object $row -Expected @('path','bytes','sha256') -Label "rows[$i]"
        if($row.path -isnot [string] -or $row.sha256 -isnot [string] -or ($row.bytes -isnot [int] -and $row.bytes -isnot [long])){ Stop-P0 "row $i has an invalid type" }
        if($row.bytes -lt 0 -or $row.sha256 -cnotmatch '^[A-F0-9]{64}$'){ Stop-P0 "row $i has invalid bytes or SHA-256" }
        if(-not $exact.Add($row.path)){ Stop-P0 "duplicate path $($row.path)" };if(-not $fold.Add($row.path)){ Stop-P0 "casefold collision $($row.path)" }
        $literal='{0}|{1}|{2}' -f $row.path,([int64]$row.bytes),$row.sha256;if($literal -cne $ExpectedRows[$i]){ Stop-P0 "missing, extra, reordered, or mismatched row at index $i" }
        $policyRows.Add($literal);$policyTotal+=[int64]$row.bytes
    }
    if($policyTotal -ne $ExpectedTotalBytes){ Stop-P0 'policy row byte sum mismatch' }
    $sorted=$policyRows.ToArray();[Array]::Sort($sorted,[StringComparer]::Ordinal);$policyRoot=Get-UpperSha256FromBytes -Bytes $strictUtf8.GetBytes([string]::Join("`r`n",$sorted))
    if($policyRoot -cne $ExpectedRoot){ Stop-P0 'policy root does not reconstruct the accepted root' }
    $observed=[Collections.Generic.List[string]]::new();$observedTotal=[int64]0
    foreach($expectedRow in $ExpectedRows){
        $parts=$expectedRow.Split('|');$relative=$parts[0];$full=Resolve-PlainSourceFile -ProjectRoot $projectRoot -RelativePath $relative;$before=Get-Item -LiteralPath $full -Force;Assert-PlainItem -Item $before -DirectoryExpected:$false -Label $relative
        $beforeLength=[int64]$before.Length;$beforeTicks=$before.LastWriteTimeUtc.Ticks;$stream=[IO.File]::Open($full,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
        try{$length=[int64]$stream.Length;$sha=Get-UpperSha256FromStream -Stream $stream}finally{$stream.Dispose()}
        $after=Get-Item -LiteralPath $full -Force;Assert-PlainItem -Item $after -DirectoryExpected:$false -Label $relative
        if($beforeLength -ne $after.Length -or $beforeTicks -ne $after.LastWriteTimeUtc.Ticks -or $length -ne $after.Length){ Stop-P0 "unstable source snapshot $relative" }
        $literal='{0}|{1}|{2}' -f $relative,$length,$sha;if($literal -cne $expectedRow){ Stop-P0 "source byte/hash mismatch $relative" };$observed.Add($literal);$observedTotal+=$length
    }
    $sortedObserved=$observed.ToArray();[Array]::Sort($sortedObserved,[StringComparer]::Ordinal);$observedRoot=Get-UpperSha256FromBytes -Bytes $strictUtf8.GetBytes([string]::Join("`r`n",$sortedObserved))
    if($observed.Count -ne $ExpectedRowCount -or $observedTotal -ne $ExpectedTotalBytes -or $observedRoot -cne $ExpectedRoot){ Stop-P0 'observed count, byte total, or root mismatch' }
    $result=[ordered]@{schema=1;status='P0_PAYLOAD_POLICY_VERIFIED';row_count=$observed.Count;total_bytes=$observedTotal;root_sha256=$observedRoot;entrypoint=$ExpectedEntrypoint}
    [Console]::Out.WriteLine(($result|ConvertTo-Json -Compress));exit 0
} catch { [Console]::Error.WriteLine($_.Exception.Message);exit 1 }
