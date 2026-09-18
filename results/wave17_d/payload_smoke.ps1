param([string]$Root = "$env:TEMP\tg-payload-smoke-042")
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
# 17-Д: копия results/wave13_r/p5_nb/payload_smoke.ps1; другое дерево и runtime из архива.
$repo = 'D:\Pets\ThermoGar'
$runtime = 'D:\Pets\ThermoGar_arhiv_2026-09-17\ThermoGar-Installer-Assets\runtime-clean-3119'

Write-Host "staging payload to $Root"
$stage = & (Join-Path $repo 'packaging\stage_payload.ps1') -RepoRoot $repo -StageRoot $Root -RuntimeSource $runtime
Write-Host "  staged $($stage.FileCount) files"

function Get-Procs { $p = $Root.TrimEnd('\') + '\'; @(Get-Process python, pythonw -ErrorAction SilentlyContinue | Where-Object { try { $_.Path -and $_.Path.StartsWith($p, 'OrdinalIgnoreCase') } catch { $false } }) }
Write-Host "  processes before: $((Get-Procs).Count)"
$foreign = Join-Path $env:TEMP ("tg-foreign-" + (Get-Random))
New-Item -ItemType Directory -Path $foreign | Out-Null
$si = New-Object System.Diagnostics.ProcessStartInfo
$si.FileName = Join-Path $Root 'runtime\pythonw.exe'
$si.Arguments = '"' + (Join-Path $Root 'launcher.pyw') + '"'
$si.WorkingDirectory = $foreign
$si.UseShellExecute = $false
$si.CreateNoWindow = $true
$launcher = [System.Diagnostics.Process]::Start($si)
Write-Host "  launcher pid $($launcher.Id), cwd $foreign"
$python = Join-Path $Root 'runtime\python.exe'
$deadline = (Get-Date).AddSeconds(300); $health = $null; $started = Get-Date
while ((Get-Date) -lt $deadline) {
    $raw = & $python (Join-Path $Root 'healthcheck.py') '--json' 2>&1 | Out-String
    try { $j = $raw.Trim() | ConvertFrom-Json; if ($j.status -eq 'HEALTHY') { $health = $j; break } } catch {}
    Start-Sleep -Milliseconds 500
}
$ok = $false
if ($health) {
    Write-Host ("  HEALTHY ui_port={0} control_port={1} after {2:N1}s" -f $health.ui_port, $health.control_port, ((Get-Date) - $started).TotalSeconds)
    $page = Invoke-WebRequest -Uri "http://127.0.0.1:$($health.ui_port)/" -UseBasicParsing -TimeoutSec 20
    $script = Invoke-WebRequest -Uri "http://127.0.0.1:$($health.ui_port)/_stcore/script-health-check" -UseBasicParsing -TimeoutSec 60
    $shell = ([string]$page.Content) -match 'streamlit'
    Write-Host "  GET / -> $($page.StatusCode) ($(([string]$page.Content).Length) bytes, Streamlit shell: $shell); script-health-check -> $($script.StatusCode) '$([string]$script.Content)'"
    $ok = ($page.StatusCode -eq 200) -and $shell -and ($script.StatusCode -eq 200)
} else {
    Write-Host "  NOT HEALTHY: $raw"
}
$stopRaw = & $python (Join-Path $Root 'stop.pyw') '--json' 2>&1 | Out-String
$stopExit = $LASTEXITCODE
Write-Host "  stop exit $stopExit : $($stopRaw.Trim())"
$gone = $false
for ($i = 0; $i -lt 60; $i++) { if ((Get-Procs).Count -eq 0) { $gone = $true; break }; Start-Sleep -Milliseconds 500 }
Write-Host "  processes after stop: $((Get-Procs).Count)"
if ($ok -and $gone -and $stopExit -eq 0) { Write-Host 'PAYLOAD SMOKE OK'; exit 0 } else { Write-Host 'PAYLOAD SMOKE FAIL'; exit 1 }
