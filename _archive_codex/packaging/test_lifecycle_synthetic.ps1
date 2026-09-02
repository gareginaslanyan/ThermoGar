$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$WarningPreference = 'SilentlyContinue'
$InformationPreference = 'SilentlyContinue'
$VerbosePreference = 'SilentlyContinue'
$DebugPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

$script:Invariant = [Globalization.CultureInfo]::InvariantCulture
$script:Utf8 = [Text.UTF8Encoding]::new($false, $true)
$script:Allowed = @(
    'StageRoot',
    'ExpectedP0Root',
    'ExpectedRuntimeFileCount',
    'ExpectedRuntimeTotalBytes',
    'ExpectedRuntimeRootSha256',
    'ExpectedNativeClosureRootSha256',
    'ExpectedP1AStageReceiptSha256',
    'ExpectedLauncherSha256',
    'ExpectedStopSha256',
    'ExpectedHealthcheckSha256',
    'ExpectedProducerSha256',
    'ExpectedVerifierSha256'
)
$script:Frozen = [ordered]@{
    ExpectedP0Root = '42455F51E284BAD35F5BFD4971F5099889A2A0D4518FFB95310FC5C400461F7F'
    ExpectedRuntimeFileCount = '15003'
    ExpectedRuntimeTotalBytes = '575844438'
    ExpectedRuntimeRootSha256 = '58F81C014DF3C3E8AA6F85517BCEE4263C0AE751365B53CA0ED197964538121C'
    ExpectedNativeClosureRootSha256 = 'A08EC90744637E0CFE3F7E72D8F4564F58D37C190704B660F4267AF02616604C'
    ExpectedP1AStageReceiptSha256 = '255FD7DB4613E646E158713639EA83353D81F2283CD3E775093DB6189997209B'
    ExpectedLauncherSha256 = 'B45DAD87139667604E3C3F4AD8F0D2307E2B0D2C86D220736286498F3389FE0A'
    ExpectedStopSha256 = 'AA2087AFF494FF007E4C12CFE0949BB62384A2251883D51765EA3D424D70A286'
    ExpectedHealthcheckSha256 = 'ABCDE7BDEFC84DE9E91CA62D6A64F07129B1796C298C4AD4BB9ECC894B9CDB67'
    ExpectedProducerSha256 = '762ABCDA551B6BE81B2728D5814E14EA0FB18B5ABC249E12DCD739D04CE779C0'
    ExpectedVerifierSha256 = 'B6FDCA5AFAC6E365818C127DB51DBE8E38824B6A60E84818998BDA3544DDBF79'
}
$script:FailureNames = @('','','USAGE','INPUT_INVALID','RUNTIME_TRUST_INVALID','HELPER_IDENTITY_INVALID','PREDICATE_FAILURE','OUTPUT_SCHEMA_MISMATCH','TIMEOUT','INTERNAL_ERROR')
$script:Cases = @(
    'normal_start_stop',
    'lock_contention_prepublication',
    'lock_contention_running',
    'malformed_record_rejected',
    'oversized_record_rejected',
    'reparse_record_rejected',
    'record_missing_noop',
    'record_changed_before_mutation',
    'live_record_fail_closed',
    'uncertain_record_fail_closed',
    'stale_record_recovery',
    'counterfeit_record_rejected',
    'continuous_reader_publish',
    'continuous_reader_rotate',
    'continuous_reader_clear',
    'control_ui_race_before_publish',
    'control_credential_mismatch_rejected',
    'supervisor_pid_mismatch_rejected',
    'child_pid_mismatch_rejected',
    'supervisor_creation_mismatch_rejected',
    'child_creation_mismatch_rejected',
    'supervisor_image_path_mismatch_rejected',
    'child_image_path_mismatch_rejected',
    'supervisor_sha_mismatch_rejected',
    'child_sha_mismatch_rejected',
    'tcp_owner_mismatch_rejected',
    'set_job_information_failure',
    'assign_job_failure',
    'preassignment_cleanup_wait_timeout',
    'create_process_failure',
    'job_membership_resume',
    'prepublication_exact_proof',
    'child_crash_cleanup',
    'controller_crash_cleanup',
    'job_descendant_cleanup',
    'unrelated_process_survives',
    'stale_two_crash_recovery',
    'stop_timeout',
    'localappdata_exact_environment',
    'installroot_immutable',
    'program_files_no_pyc',
    'startup_no_retry',
    'ui_port_zero_discovery',
    'ui_wildcard_rejected',
    'ui_foreign_owner_rejected',
    'control_loopback_exclusive',
    'strict_http_method',
    'strict_http_path',
    'strict_http_authorization',
    'strict_http_host_wrong',
    'strict_http_host_missing',
    'strict_http_authorization_missing',
    'strict_http_authorization_malformed',
    'strict_http_duplicate_authorization',
    'strict_http_malformed_header',
    'strict_http_content_length_invalid',
    'strict_http_content_length_conflicting',
    'strict_http_trailing_bytes',
    'strict_http_version',
    'strict_http_duplicate_header',
    'strict_http_body_rejected',
    'strict_http_transfer_encoding',
    'strict_http_oversized',
    'strict_http_stopping',
    'strict_http_stop_accepted',
    'control_health_gate',
    'streamlit_health_gate',
    'streamlit_script_health_gate',
    'pid_reuse_rejected',
    'process_access_denied_uncertain',
    'tcp_wildcard_rejected',
    'tcp_public_rejected',
    'tcp_duplicate_rejected',
    'job_pid_list_exact',
    'stop_record_absence_probe_one',
    'stop_exact_handle_death',
    'stop_listener_absence',
    'stop_record_absence_probe_two',
    'stop_complete_proof',
    'stop_changed_record_retained',
    'stop_identity_uncertainty_retained',
    'stop_deadline_5000ms',
    'observer_request_deadline_3000ms',
    'no_product_or_science_import',
    'health_forced_exit_2',
    'health_forced_exit_3',
    'health_forced_exit_4',
    'health_forced_exit_5',
    'health_forced_exit_6',
    'health_forced_exit_7',
    'health_forced_exit_8',
    'health_forced_exit_9',
    'stop_forced_exit_2',
    'stop_forced_exit_3',
    'stop_forced_exit_4',
    'stop_forced_exit_5',
    'stop_forced_exit_6',
    'stop_forced_exit_7',
    'stop_forced_exit_8',
    'stop_forced_exit_9'
)

function Exit-CanonicalFailure {
    param([int]$Code)
    if ($Code -lt 2 -or $Code -gt 9) { $Code = 9 }
    [Console]::Out.Write('{"schema":1,"status":"' + $script:FailureNames[$Code] + '","detail_code":' + $Code.ToString($script:Invariant) + '}')
    exit $Code
}

function Get-InvocationMap {
    param([object[]]$Tokens)
    if ($Tokens.Count -ne 24) { Exit-CanonicalFailure 2 }
    $map = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
    for ($index = 0; $index -lt $Tokens.Count; $index += 2) {
        $nameToken = $Tokens[$index]
        $valueToken = $Tokens[$index + 1]
        if ($nameToken -isnot [string] -or $valueToken -isnot [string]) { Exit-CanonicalFailure 2 }
        $nameText = [string]$nameToken
        $valueText = [string]$valueToken
        if (-not $nameText.StartsWith('-', [StringComparison]::Ordinal) -or $nameText.Length -lt 2) { Exit-CanonicalFailure 2 }
        $name = $nameText.Substring(1)
        if (-not ($script:Allowed -ccontains $name) -or $map.ContainsKey($name) -or [string]::IsNullOrEmpty($valueText)) { Exit-CanonicalFailure 2 }
        $map.Add($name, $valueText)
    }
    foreach ($name in $script:Allowed) { if (-not $map.ContainsKey($name)) { Exit-CanonicalFailure 2 } }
    return $map
}

function Get-Sha256 {
    param([byte[]]$Bytes)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return ([Convert]::ToHexString($algorithm.ComputeHash($Bytes))) } finally { $algorithm.Dispose() }
}

function Read-AllExact {
    param([IO.FileStream]$Stream, [int64]$Maximum)
    if ($Stream.Length -lt 0 -or $Stream.Length -gt $Maximum) { throw 'file bounds' }
    $Stream.Position = 0
    $bytes = [byte[]]::new([int]$Stream.Length)
    $offset = 0
    while ($offset -lt $bytes.Length) {
        $count = $Stream.Read($bytes, $offset, $bytes.Length - $offset)
        if ($count -le 0) { throw 'short read' }
        $offset += $count
    }
    return $bytes
}

function Open-PinnedFile {
    param([string]$Path, [string]$ExpectedSha, [int64]$Maximum = 1048576)
    $full = [IO.Path]::GetFullPath($Path)
    if ($full -cne $Path -or -not [IO.Path]::IsPathFullyQualified($Path)) { throw 'noncanonical file path' }
    $stream = [IO.File]::Open($full, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $bytes = Read-AllExact $stream $Maximum
        $sha = Get-Sha256 $bytes
        if ($sha -cne $ExpectedSha) { throw 'file identity' }
        return [pscustomobject]@{Path=$full;Stream=$stream;Bytes=$bytes;Sha256=$sha;Length=[int64]$bytes.Length}
    } catch {
        $stream.Dispose()
        throw
    }
}

function Assert-PinnedFile {
    param([object]$Pinned)
    if ($Pinned.Stream.Length -ne $Pinned.Length) { throw 'held length changed' }
    $bytes = Read-AllExact $Pinned.Stream 1048576
    if ((Get-Sha256 $bytes) -cne $Pinned.Sha256) { throw 'held bytes changed' }
}

function Assert-Input {
    param([Collections.Generic.Dictionary[string,string]]$Map)
    foreach ($entry in $script:Frozen.GetEnumerator()) {
        if ($Map[$entry.Key] -cne [string]$entry.Value) { Exit-CanonicalFailure 3 }
    }
    foreach ($name in @('ExpectedRuntimeFileCount','ExpectedRuntimeTotalBytes')) {
        $text = $Map[$name]
        if ($text -cnotmatch '^(0|[1-9][0-9]*)$') { Exit-CanonicalFailure 3 }
        $value = [int64]0
        if (-not [int64]::TryParse($text, [Globalization.NumberStyles]::None, $script:Invariant, [ref]$value) -or $value -lt 0) { Exit-CanonicalFailure 3 }
    }
    foreach ($name in $script:Allowed) {
        if ($name -like 'Expected*Sha256' -or $name -eq 'ExpectedP0Root') {
            if ($Map[$name] -cnotmatch '^[0-9A-F]{64}$') { Exit-CanonicalFailure 3 }
        }
    }
    $stage = $Map['StageRoot']
    try { $full = [IO.Path]::GetFullPath($stage) } catch { Exit-CanonicalFailure 3 }
    if ($stage -cne $full -or -not [IO.Path]::IsPathFullyQualified($stage) -or -not [IO.Directory]::Exists($stage)) { Exit-CanonicalFailure 3 }
    if ($stage.StartsWith('\\', [StringComparison]::Ordinal)) { Exit-CanonicalFailure 3 }
    $drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($stage))
    if (-not $drive.IsReady -or $drive.DriveType -ne [IO.DriveType]::Fixed) { Exit-CanonicalFailure 3 }
    $cursor = [IO.DirectoryInfo]::new($stage)
    while ($null -ne $cursor) {
        if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { Exit-CanonicalFailure 3 }
        $cursor = $cursor.Parent
    }
    return $full
}

function Resolve-SourceRoot {
    $candidate = [IO.Path]::GetFullPath($PSScriptRoot)
    if ($candidate -cne $PSScriptRoot) { throw 'source root is not canonical' }
    foreach ($name in @(
        'launcher.pyw', 'stop.pyw', 'healthcheck.py',
        'generate_runtime_trust_manifest.ps1', 'verify_runtime_trust_manifest.ps1'
    )) {
        $path = [IO.Path]::Combine($candidate, $name)
        if (-not [IO.File]::Exists($path)) { throw 'source helper absent beside accepted script' }
    }
    return $candidate
}

function Invoke-Bounded {
    param([string]$FileName, [string[]]$Arguments, [string]$WorkingDirectory, [Collections.Generic.Dictionary[string,string]]$Environment, [int]$TimeoutMilliseconds)
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $FileName
    $start.WorkingDirectory = $WorkingDirectory
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($argument in $Arguments) { [void]$start.ArgumentList.Add($argument) }
    $start.Environment.Clear()
    foreach ($pair in $Environment.GetEnumerator()) { $start.Environment[$pair.Key] = $pair.Value }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $start
    $clock = [Diagnostics.Stopwatch]::StartNew()
    try {
        if (-not $process.Start()) { throw 'process start' }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutMilliseconds)) {
            try { $process.Kill($true) } catch {}
            [void]$process.WaitForExit(1000)
            return [pscustomobject]@{TimedOut=$true;ExitCode=8;Stdout='';Stderr='';DurationMs=[int][Math]::Min([int]::MaxValue, $clock.ElapsedMilliseconds)}
        }
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        return [pscustomobject]@{TimedOut=$false;ExitCode=[int]$process.ExitCode;Stdout=$stdout;Stderr=$stderr;DurationMs=[int][Math]::Min([int]::MaxValue, $clock.ElapsedMilliseconds)}
    } finally {
        $clock.Stop()
        $process.Dispose()
    }
}

function New-CleanEnvironment {
    param([string]$FixtureRoot)
    $environment = [Collections.Generic.Dictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($name in @('SystemRoot','WINDIR','ComSpec','PATHEXT')) {
        $value = [Environment]::GetEnvironmentVariable($name)
        if (-not [string]::IsNullOrEmpty($value)) { $environment[$name] = $value }
    }
    $environment['LOCALAPPDATA'] = $FixtureRoot
    $environment['USERPROFILE'] = $FixtureRoot
    $environment['TEMP'] = $FixtureRoot
    $environment['TMP'] = $FixtureRoot
    $environment['PYTHONDONTWRITEBYTECODE'] = '1'
    $environment['PYTHONNOUSERSITE'] = '1'
    return $environment
}

function Assert-UnderOwnedRoot {
    param([string]$Root, [string]$Candidate)
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $candidateFull = [IO.Path]::GetFullPath($Candidate)
    if (-not $candidateFull.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) { throw 'cleanup escaped fixture' }
}

function Remove-OwnedChildrenExact {
    param([string]$Root, [string]$Current)
    foreach ($entry in [IO.Directory]::EnumerateFileSystemEntries($Current)) {
        Assert-UnderOwnedRoot $Root $entry
        $attributes = [IO.File]::GetAttributes($entry)
        if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'fixture reparse' }
        if (($attributes -band [IO.FileAttributes]::Directory) -ne 0) {
            Remove-OwnedChildrenExact $Root $entry
            [IO.Directory]::Delete($entry, $false)
        } else {
            [IO.File]::Delete($entry)
        }
    }
}

function Remove-OwnedFixture {
    param([string]$Root, [IO.FileStream]$Authority, [byte[]]$AuthorityBytes)
    $authorityPath = [IO.Path]::Combine($Root, '.authority')
    $Authority.Position = 0
    $current = Read-AllExact $Authority 128
    if ((Get-Sha256 $current) -cne (Get-Sha256 $AuthorityBytes)) { throw 'fixture authority changed' }
    $Authority.Dispose()
    Remove-OwnedChildrenExact $Root $Root
    [IO.Directory]::Delete($Root, $false)
}

$script:Worker = @'
import contextlib
import ast
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import pathlib
import re
import sys
import threading
import time
import types

PASS = '{"schema":1,"status":"SYNTHETIC_CASE_PASSED","case":%s}'

def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module

def require(value, detail):
    if not value:
        raise AssertionError(detail)

def must_raise(call, kinds=(Exception,)):
    try:
        call()
    except kinds:
        return
    raise AssertionError('required rejection absent')

class CaptureStdout:
    def __init__(self):
        self.buffer = io.BytesIO()
    def write(self, text):
        raw = text.encode('utf-8', 'strict')
        self.buffer.write(raw)
        return len(text)
    def flush(self):
        return None

def capture(call):
    stdout = CaptureStdout()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = call()
    return code, stdout.buffer.getvalue(), stderr.getvalue()

@contextlib.contextmanager
def patched(*items):
    saved = []
    try:
        for owner, name, value in items:
            saved.append((owner, name, getattr(owner, name)))
            setattr(owner, name, value)
        yield
    finally:
        for owner, name, value in reversed(saved):
            setattr(owner, name, value)

def observer_expected(code):
    names = ('','','USAGE','RUNTIME_TRUST_INVALID','NO_RUN','RECORD_INVALID','IDENTITY_MISMATCH','ENDPOINT_REJECTED','TIMEOUT','INTERNAL_ERROR')
    return ('{"schema":1,"status":"' + names[code] + '","detail_code":' + str(code) + '}').encode('utf-8')

def observer_injections(common, code, role, trace):
    trust = {'held_handles': []}
    record = {'schema': 1, 'control_port': 41001, 'ui_port': 41002}
    processes = {'supervisor': {'handle': None}, 'child': {'handle': None}}
    def trust_call(_caller, _role):
        trace.append(('trust', _role))
        require(_role == role, 'observer role binding')
        if code == 3:
            raise ValueError('injected trust failure')
        return trust
    def read_call(_state, _trust):
        trace.append(('record', role))
        if code in (4, 5):
            raise common.ObserverError(code, 'injected record failure')
        return b'{}', record
    def identity_call(_record, _trust):
        trace.append(('identity', role))
        if code == 6:
            raise common.ObserverError(6, 'injected identity failure')
        return processes
    def request_call(_record, _role, _deadline):
        trace.append(('request', _role))
        require(_role == role, 'request role binding')
        if code in (7, 8):
            raise common.ObserverError(code, 'injected endpoint failure')
        return {'schema': 1}
    def state_call():
        trace.append(('state', role))
        if code == 9:
            raise RuntimeError('injected uncertainty')
        return 'synthetic-state'
    return (
        (common, '_validate_trust', trust_call),
        (common, '_state_root', state_call),
        (common, '_read_record', read_call),
        (common, '_validate_identities', identity_call),
        (common, '_require_processes_live', lambda _processes: None),
        (common, '_request', request_call),
        (common, '_stopped', lambda *_args: True),
    )

def health_observer_exit(health, code, caller):
    trace = []
    argv = [str(caller), '--json'] if code != 2 else [str(caller)]
    changes = ((health.sys, 'argv', argv),) + observer_injections(health, code, 'health', trace)
    with patched(*changes):
        result = capture(lambda: health.run_observer('health', str(caller)))
    if code >= 4:
        require(trace and all(item[1] == 'health' for item in trace), 'health common seam absent')
    return result

def stop_observer_exit(stop, health, code, caller):
    argv = [str(caller), '--json'] if code != 2 else [str(caller)]
    trace = []
    def load_common():
        if code == 3:
            raise ValueError('injected common trust failure')
        return health, []
    changes = ((stop.sys, 'argv', argv), (stop, '_load_common', load_common))
    if code >= 4:
        changes = changes + observer_injections(health, code, 'stop', trace)
    with patched(*changes):
        result = capture(stop._run)
    if code >= 4:
        require(trace and all(item[1] == 'stop' for item in trace), 'stop common seam absent')
    return result

class Flag:
    def __init__(self, value=False):
        self.value = value
    def is_set(self):
        return self.value

class SequenceFlag:
    def __init__(self, values):
        self.values = list(values)
        self.last = self.values[-1]
    def is_set(self):
        if self.values:
            self.last = self.values.pop(0)
        return self.last

class StopSignal:
    def __init__(self, value):
        self.value = value
    def wait(self, _timeout):
        return self.value

class FakeListener:
    def __init__(self, calls):
        self.calls = calls
    def getsockname(self):
        return ('127.0.0.1', 41001)
    def close(self):
        self.calls.append('listener.close')

class FakeServer:
    def __init__(self, calls, mode):
        self.calls = calls
        self.mode = mode
        self.ready = types.SimpleNamespace(set=lambda: calls.append('server.ready'))
        self.failed = SequenceFlag((False, True)) if mode == 'controller_crash' else Flag(False)
        self.stopping = Flag(False)
        self.stop_requested = StopSignal(mode not in ('child_crash', 'controller_crash'))
    def start(self): self.calls.append('server.start')
    def verify_ready(self): self.calls.append('server.verify_ready')
    def close(self): self.calls.append('server.close')

class KernelProxy:
    def __init__(self, base, **overrides):
        self._base = base
        self._overrides = overrides
    def __getattr__(self, name):
        if name in self._overrides:
            return self._overrides[name]
        return getattr(self._base, name)

def launcher_run_model(launcher, stage, fixture, mode):
    calls = []
    captured = {}
    metadata = {}
    own = {'path': str(stage / 'launcher.pyw'), 'handle': 101}
    critical = {
        'launcher.pyw': own,
        'runtime/pythonw.exe': {'path': str(stage / 'runtime' / 'pythonw.exe')},
        'runtime/python.exe': {'path': str(stage / 'runtime' / 'python.exe')},
    }
    trust = {'manifest_sha256': 'A' * 64, 'critical': critical, 'held_handles': []}
    info = types.SimpleNamespace(hProcess=303, hThread=304, dwProcessId=222)
    paths = launcher._state_paths()
    expected_state = (fixture / 'ThermoGar').resolve()
    require(pathlib.Path(paths['state']).resolve() == expected_state, 'state escaped LocalAppData')
    require(not pathlib.Path(paths['state']).resolve().is_relative_to(stage.resolve()), 'state substituted Stage')
    original_open_lock = launcher._open_lock
    original_recover = launcher._recover_stale
    original_publish = launcher._publish_record
    original_clear = launcher._clear_record_exact
    original_close = launcher._close_handle
    held_lock = None
    running_raw = None
    if mode in ('lock_pre', 'lock_running'):
        held_lock = original_open_lock(paths['lock'])
        metadata['holder_open'] = True
        if mode == 'lock_running':
            running_raw = original_publish(paths['record'], paths['state'], valid_record(stage))
            metadata['running_record_before'] = pathlib.Path(paths['record']).read_bytes() == running_raw
    def identity(handle, _expected=None):
        if handle == 303:
            return {'creation': '22', 'path': os.path.normcase(os.path.abspath(stage / 'runtime' / 'python.exe')), 'sha256': 'C' * 64}
        return {'creation': '11', 'path': os.path.normcase(os.path.abspath(stage / 'runtime' / 'pythonw.exe')), 'sha256': 'B' * 64}
    opened_lock = [None]
    def open_lock(_path):
        calls.append('open_lock')
        opened_lock[0] = original_open_lock(_path)
        return opened_lock[0]
    def recover(*args):
        calls.append('recover_stale')
        return original_recover(*args)
    def create_child(_root, env):
        calls.append('create_child')
        captured.update(env)
        return info
    def publish(*args):
        calls.append('publish')
        raw = original_publish(*args)
        metadata['published_raw'] = raw
        metadata['published_present'] = pathlib.Path(args[0]).read_bytes() == raw
        return raw
    def cleanup(_job, _child, _child_pid, _supervisor_pid, _ui, _control, record_path, state_root, record_raw):
        calls.append('cleanup')
        if record_path is not None and record_raw is not None:
            original_clear(record_path, state_root, record_raw)
            calls.append('record_clear')
            metadata['record_absent_after_clear'] = not os.path.lexists(record_path)
    def precleanup(_handle): calls.append('preassignment_cleanup')
    def server_factory(*_args):
        calls.append('server.construct')
        return FakeServer(calls, mode)
    kernel = KernelProxy(
        launcher.kernel32,
        GetCurrentProcessId=lambda: 111,
        GetCurrentProcess=lambda: 11,
        AssignProcessToJobObject=lambda _job, _handle: mode != 'assign_fail',
        WaitForSingleObject=lambda _handle, _timeout: launcher.WAIT_OBJECT_0 if mode == 'child_crash' else launcher.WAIT_TIMEOUT,
    )
    def discover(*_args):
        calls.append('discover_ui')
        if mode == 'startup_failure':
            raise launcher.LauncherError(8, 'injected discovery failure')
        return 41002
    def close_handle(handle):
        if handle is not None and handle == opened_lock[0]:
            calls.append('lock.close')
            return original_close(handle)
        if handle not in (None, 11, 101, 303, 304, 404):
            return original_close(handle)
    changes = (
        (launcher.sys, 'argv', [str(stage / 'launcher.pyw')]),
        (launcher, 'kernel32', kernel),
        (launcher, '_open_held_file', lambda *_args: own),
        (launcher, '_validate_trust', lambda _root: trust),
        (launcher, '_same_file_authority', lambda _left, _right: True),
        (launcher, '_process_identity_from_handle', identity),
        (launcher, '_state_paths', launcher._state_paths),
        (launcher, '_open_lock', open_lock),
        (launcher, '_recover_stale', recover),
        (launcher, '_bind_control', lambda: (calls.append('bind_control') or FakeListener(calls))),
        (launcher, '_tcp_listeners', lambda: [('127.0.0.1', 41001, 111)]),
        (launcher, '_has_only_owned_listener', lambda *_args: True),
        (launcher, '_create_job', lambda: (calls.append('create_job') or 404)),
        (launcher, '_create_child', create_child),
        (launcher, '_verify_assignment_and_resume', lambda *_args: calls.append('assign_resume_proof')),
        (launcher, '_discover_ui', discover),
        (launcher, '_assert_prepublication', lambda *_args: calls.append('prepublication_proof')),
        (launcher, '_publish_record', publish),
        (launcher, 'ControlServer', server_factory),
        (launcher, '_cleanup', cleanup),
        (launcher, '_preassignment_cleanup', precleanup),
        (launcher, '_close_handle', close_handle),
        (launcher, '_win_error', lambda code, detail: launcher.LauncherError(code, detail)),
    )
    try:
        with patched(*changes):
            result = launcher._run()
    finally:
        if held_lock is not None:
            original_close(held_lock)
            metadata['holder_closed'] = True
        if running_raw is not None:
            require(pathlib.Path(paths['record']).read_bytes() == running_raw, 'RUNNING record changed after contention')
            original_clear(paths['record'], paths['state'], running_raw)
            metadata['running_record_retained'] = True
    return result, calls, captured, paths, metadata

def assert_launcher_run_case(launcher, stage, fixture, case):
    mode = {
        'lock_contention_prepublication': 'lock_pre',
        'lock_contention_running': 'lock_running',
        'assign_job_failure': 'assign_fail',
        'child_crash_cleanup': 'child_crash',
        'controller_crash_cleanup': 'controller_crash',
        'startup_no_retry': 'startup_failure',
    }.get(case, 'normal')
    result, calls, env, paths, metadata = launcher_run_model(launcher, stage, fixture, mode)
    if mode.startswith('lock_'):
        require(result == 10, 'lock exit')
        require(calls == ['open_lock'], 'work occurred after lock failure')
        require(metadata.get('holder_open') and metadata.get('holder_closed'), 'exclusive lock holder absent')
        if mode == 'lock_running':
            require(metadata.get('running_record_before') and metadata.get('running_record_retained'), 'RUNNING authority not retained')
        return
    if mode == 'assign_fail':
        require(result == 9 and calls.count('create_child') == 1, 'assign failure exit')
        require(calls.count('preassignment_cleanup') == 1 and 'publish' not in calls, 'assign failure cleanup')
        return
    if mode in ('child_crash', 'controller_crash'):
        require(result == 9 and calls.count('cleanup') == 1, 'crash reversal')
        require(calls.count('create_child') == 1, 'crash retry')
        require(metadata.get('published_present') and metadata.get('record_absent_after_clear'), 'crash record reversal')
        for operation in ('bind_control','create_job','create_child','assign_resume_proof','publish'):
            require(calls.count(operation) == 1, 'crash caused retry: ' + operation)
        return
    if mode == 'startup_failure':
        require(result == 8 and calls.count('create_child') == 1, 'startup failure/no retry exit')
        for operation in ('bind_control','create_job','create_child','assign_resume_proof','discover_ui'):
            require(calls.count(operation) == 1, 'startup retry: ' + operation)
        require('publish' not in calls and calls.count('cleanup') == 1, 'startup failure published or skipped reversal')
        return
    require(result == 0, 'normal lifecycle exit')
    required = ('open_lock','recover_stale','bind_control','create_job','create_child','assign_resume_proof','discover_ui','server.construct','server.start','server.ready','server.verify_ready','prepublication_proof','publish','server.close','cleanup','record_clear','lock.close')
    positions = [calls.index(item) for item in required]
    require(positions == sorted(positions), 'lifecycle order')
    require(calls.count('create_child') == 1 and calls.count('publish') == 1, 'retry or republish')
    require(metadata.get('published_present') and metadata.get('record_absent_after_clear'), 'normal record publish/clear')
    if case == 'localappdata_exact_environment':
        require(pathlib.Path(paths['state']).resolve() == (fixture / 'ThermoGar').resolve(), 'LocalAppData state')
        require(env.get('THERMOGAR_STATE_ROOT') == paths['state'], 'state env')
        require(env.get('TMP') == paths['tmp'] and env.get('TEMP') == paths['tmp'], 'temp env')
        require(env.get('MPLCONFIGDIR') == paths['mpl'], 'matplotlib env')
        require(env.get('PYTHONDONTWRITEBYTECODE') == '1', 'pyc env')

def valid_record(stage):
    return {
        'schema': 1,
        'state': 'RUNNING',
        'runtime_trust_manifest_sha256': 'A' * 64,
        'supervisor_pid': 111,
        'supervisor_creation_filetime': '100',
        'supervisor_image_sha256': 'B' * 64,
        'child_pid': 222,
        'child_creation_filetime': '200',
        'child_image_path': os.path.normcase(os.path.abspath(stage / 'runtime' / 'python.exe')),
        'child_image_sha256': 'C' * 64,
        'control_port': 41001,
        'ui_port': 41002,
        'nonce': 'd' * 64,
        'token': 'e' * 64,
        'published_utc': '2026-08-31T12:00:00.000000Z',
    }

def assert_identity_case(launcher, stage, case):
    record = valid_record(stage)
    target = 'supervisor' if case.startswith('supervisor_') else 'child'
    if case == 'supervisor_pid_mismatch_rejected': record['supervisor_pid'] = 333
    if case == 'child_pid_mismatch_rejected': record['child_pid'] = 444
    if case == 'supervisor_creation_mismatch_rejected': record['supervisor_creation_filetime'] = '301'
    if case in ('child_creation_mismatch_rejected','pid_reuse_rejected'): record['child_creation_filetime'] = '401' if case.startswith('child_') else '999'
    if case == 'supervisor_sha_mismatch_rejected': record['supervisor_image_sha256'] = 'D' * 64
    if case == 'child_sha_mismatch_rejected': record['child_image_sha256'] = 'E' * 64
    expected_path = (str(stage / 'runtime' / 'pythonw.exe') if target == 'supervisor'
                     else str(stage / 'runtime' / 'python.exe'))
    target_pid = record[target + '_pid']
    target_creation = record[target + '_creation_filetime']
    target_sha = record[target + '_image_sha256']
    trace = []
    phase = ['direct']
    closed = []
    def open_process(_access, _inherit, pid):
        trace.append(('OpenProcess', phase[0], pid))
        target_pid_now = record[target + '_pid']
        if pid != target_pid_now and phase[0] == 'record':
            launcher.ctypes.set_last_error(launcher.ERROR_INVALID_PARAMETER)
            return 0
        if case in ('supervisor_pid_mismatch_rejected','child_pid_mismatch_rejected') or case == 'process_access_denied_uncertain':
            error = launcher.ERROR_ACCESS_DENIED if case == 'process_access_denied_uncertain' else launcher.ERROR_INVALID_PARAMETER
            launcher.ctypes.set_last_error(error)
            return 0
        return 10000 + int(pid)
    def process_identity(handle, _expected=None):
        pid = int(handle) - 10000
        trace.append(('identity', phase[0], pid))
        creation = '100' if target == 'supervisor' else '200'
        path = expected_path
        sha = 'B' * 64 if target == 'supervisor' else 'C' * 64
        if case == 'supervisor_image_path_mismatch_rejected': path = str(stage / 'other' / 'pythonw.exe')
        if case == 'child_image_path_mismatch_rejected': path = str(stage / 'other.exe')
        return {'creation': creation, 'path': os.path.normcase(os.path.abspath(path)), 'sha256': sha}
    kernel = KernelProxy(
        launcher.kernel32,
        OpenProcess=open_process,
        WaitForSingleObject=lambda _handle, _timeout: launcher.WAIT_TIMEOUT,
    )
    with patched((launcher, 'kernel32', kernel),
                 (launcher, '_process_identity_from_handle', process_identity),
                 (launcher, '_close_handle', lambda handle: closed.append(handle)),
                 (launcher, '_tcp_listeners', lambda: (trace.append(('tcp', phase[0])) or []))):
        direct = launcher._open_process_identity(target_pid, target_creation, expected_path, target_sha)
        phase[0] = 'record'
        proved_dead = launcher._record_is_proved_dead(record)
    expected = 'UNCERTAIN' if case == 'process_access_denied_uncertain' else 'DEAD'
    require(direct == expected, 'identity comparison result')
    require((not proved_dead) if expected == 'UNCERTAIN' else proved_dead, 'record death authority')
    require(any(item[0] == 'OpenProcess' for item in trace), 'OpenProcess seam absent')
    if case not in ('supervisor_pid_mismatch_rejected','child_pid_mismatch_rejected','process_access_denied_uncertain'):
        require(any(item[0] == 'identity' for item in trace), 'process identity comparison absent')
        require(closed, 'process handle not closed')

def assert_recovery_case(launcher, stage, fixture, case):
    state = fixture / 'ThermoGar'
    runtime = state / 'runtime'
    runtime.mkdir(parents=True)
    record_path = runtime / 'run.json'
    stale_path = runtime / 'run.stale.json'
    paths = {'state': str(state), 'record': str(record_path), 'stale': str(stale_path)}
    record = valid_record(stage)
    if case == 'stale_two_crash_recovery':
        launcher._publish_record(str(stale_path), str(state), record)
    launcher._publish_record(str(record_path), str(state), record)
    raw = launcher._canonical_json(record)
    operations = []
    original_delete = launcher._delete_exact_file
    original_rename = launcher._rename_exact_file
    def delete(path, state_root, expected):
        require(path == str(stale_path) and state_root == str(state) and expected == raw, 'stale delete authority')
        operations.append('delete')
        return original_delete(path, state_root, expected)
    def rename(source, destination, state_root, expected):
        require(source == str(record_path) and destination == str(stale_path), 'stale rename paths')
        require(state_root == str(state) and expected == raw, 'stale rename authority')
        operations.append('rename')
        return original_rename(source, destination, state_root, expected)
    with patched((launcher, '_record_is_proved_dead', lambda _record: True),
                 (launcher, '_delete_exact_file', delete),
                 (launcher, '_rename_exact_file', rename)):
        launcher._recover_stale(paths, str(stage), 'A' * 64)
    expected = ['delete', 'rename'] if case == 'stale_two_crash_recovery' else ['rename']
    require(operations == expected, 'recovery mutation order')
    require(not record_path.exists() and stale_path.read_bytes() == raw, 'real stale mutation result')

def assert_continuous_io(launcher, stage, fixture, case):
    state = fixture / 'ThermoGar' / ('continuous-' + case)
    state.mkdir(parents=True)
    record_path = state / 'run.json'
    stale_path = state / 'run.stale.json'
    record = valid_record(stage)
    raw = launcher._canonical_json(record)
    if case != 'continuous_reader_publish':
        launcher._publish_record(str(record_path), str(state), record)
    first_snapshot = threading.Event()
    mutation_done = threading.Event()
    partial = []
    def reader():
        for phase in range(2):
            for path in (record_path, stale_path):
                try:
                    value = path.read_bytes()
                    if value != raw:
                        partial.append(value)
                except FileNotFoundError:
                    pass
            if phase == 0:
                first_snapshot.set()
                mutation_done.wait(1.0)
    thread = threading.Thread(target=reader)
    thread.start()
    try:
        require(first_snapshot.wait(1.0), 'reader did not reach bounded snapshot')
        if case == 'continuous_reader_publish':
            launcher._publish_record(str(record_path), str(state), record)
        elif case == 'continuous_reader_rotate':
            launcher._rename_exact_file(str(record_path), str(stale_path), str(state), raw)
        else:
            launcher._clear_record_exact(str(record_path), str(state), raw)
    finally:
        mutation_done.set(); thread.join(1.0)
    require(not thread.is_alive() and not partial, 'partial record visibility')
    if case == 'continuous_reader_rotate':
        require(not record_path.exists() and stale_path.read_bytes() == raw, 'held-handle rotate result')

def assert_record_rejection(launcher, stage, fixture, case):
    state = fixture / 'ThermoGar'
    runtime = state / 'runtime'
    runtime.mkdir(parents=True)
    record_path = runtime / 'run.json'
    stale_path = runtime / 'run.stale.json'
    paths = {'state':str(state),'record':str(record_path),'stale':str(stale_path)}
    if case == 'malformed_record_rejected':
        record_path.write_bytes(b'{"schema":1,"schema":1}')
    elif case == 'oversized_record_rejected':
        record_path.write_bytes(b'{' + b' ' * 4097)
    elif case == 'reparse_record_rejected':
        record_path.write_bytes(b'{}')
    elif case == 'counterfeit_record_rejected':
        record = valid_record(stage); record['runtime_trust_manifest_sha256'] = 'F' * 64
        record_path.write_bytes(launcher._canonical_json(record))
    process = []
    mutations = []
    changes = (
        (launcher, '_record_is_proved_dead', lambda _record: process.append('process')),
        (launcher, '_delete_exact_file', lambda *_args: mutations.append('delete')),
        (launcher, '_rename_exact_file', lambda *_args: mutations.append('rename')),
    )
    if case == 'reparse_record_rejected':
        original_stable = launcher._stable_read
        def reject_reparse(path, root, maximum):
            if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(record_path)):
                raise ValueError('injected reparse identity')
            return original_stable(path, root, maximum)
        changes = changes + ((launcher, '_stable_read', reject_reparse),)
    with patched(*changes):
        must_raise(lambda: launcher._recover_stale(paths, str(stage), 'A' * 64), (launcher.LauncherError,))
    require(not process and not mutations, 'invalid record crossed authority boundary')

def assert_recovery_fail_closed(launcher, stage, fixture, case):
    state = fixture / 'ThermoGar'
    runtime = state / 'runtime'
    runtime.mkdir(parents=True)
    record_path = runtime / 'run.json'
    stale_path = runtime / 'run.stale.json'
    paths = {'state':str(state),'record':str(record_path),'stale':str(stale_path)}
    mutations = []
    if case == 'record_missing_noop':
        with patched((launcher, '_read_record', lambda *_args: (_ for _ in ()).throw(AssertionError('read missing record'))),
                     (launcher, '_delete_exact_file', lambda *_args: mutations.append('delete')),
                     (launcher, '_rename_exact_file', lambda *_args: mutations.append('rename'))):
            launcher._recover_stale(paths, str(stage), 'A' * 64)
        require(not mutations, 'missing record mutated')
        return
    if case == 'record_changed_before_mutation':
        raw = launcher._publish_record(str(record_path), str(state), valid_record(stage))
        original_rename = launcher._rename_exact_file
        def change_then_rename(source, destination, state_root, expected):
            record_path.write_bytes(b'changed-before-mutation')
            mutations.append('rename-attempt')
            return original_rename(source, destination, state_root, expected)
        with patched((launcher, '_record_is_proved_dead', lambda _record: True),
                     (launcher, '_rename_exact_file', change_then_rename)):
            must_raise(lambda: launcher._recover_stale(paths, str(stage), 'A' * 64), (launcher.LauncherError,))
        require(mutations == ['rename-attempt'] and record_path.read_bytes() == b'changed-before-mutation', 'changed authority not retained')
        require(not stale_path.exists() and raw != record_path.read_bytes(), 'changed record rotated')
        return
    record = valid_record(stage)
    launcher._publish_record(str(record_path), str(state), record)
    states = []
    desired = 'LIVE' if case == 'live_record_fail_closed' else 'UNCERTAIN'
    def process(*_args):
        states.append(desired)
        return desired
    with patched((launcher, '_open_process_identity', process),
                 (launcher, '_tcp_listeners', lambda: (_ for _ in ()).throw(AssertionError('TCP reached after live/uncertain process'))),
                 (launcher, '_delete_exact_file', lambda *_args: mutations.append('delete')),
                 (launcher, '_rename_exact_file', lambda *_args: mutations.append('rename'))):
        must_raise(lambda: launcher._recover_stale(paths, str(stage), 'A' * 64), (launcher.LauncherError,))
    require(states and set(states) == {desired}, 'live/uncertain condition not distinct')
    require(not mutations and record_path.exists(), 'live/uncertain record mutated')

def assert_assignment_case(launcher, stage, case):
    if case == 'create_process_failure':
        return
    if case == 'job_membership_resume':
        resumed = []
        def in_job(_process, _job, assigned): assigned._obj.value = 1; return True
        kernel = types.SimpleNamespace(IsProcessInJob=in_job, ResumeThread=lambda handle: (resumed.append(handle) or 1))
        info = types.SimpleNamespace(hProcess=303, hThread=304)
        with patched((launcher, 'kernel32', kernel), (launcher, '_win_error', lambda code, detail: launcher.LauncherError(code, detail))):
            launcher._verify_assignment_and_resume(77, info)
        require(resumed == [304], 'resume count')
        kernel = types.SimpleNamespace(IsProcessInJob=lambda *_args: False, ResumeThread=lambda handle: resumed.append(handle))
        with patched((launcher, 'kernel32', kernel), (launcher, '_win_error', lambda code, detail: launcher.LauncherError(code, detail))):
            must_raise(lambda: launcher._verify_assignment_and_resume(77, info), (launcher.LauncherError,))
        require(resumed == [304], 'resume without membership')
        return
    paths = []
    proof_events = []
    rows = [('127.0.0.1',41002,222),('127.0.0.1',41001,111)]
    proof = {'process_ids': (222,333), 'accounting': (2,2,0), 'child_pid': 222, 'members': []}
    child_identity = {'creation':'100','path':str(stage / 'runtime' / 'python.exe'),'sha256':'A'*64,'bytes':1,'volume':1,'index':1}
    child_authority = {'bytes':1}
    with patched((launcher, '_open_prepublication_job_proof', lambda *_args: (proof_events.append('open') or proof)),
                 (launcher, '_recheck_prepublication_job_proof', lambda *_args: proof_events.append('recheck')),
                 (launcher, '_close_prepublication_job_proof', lambda *_args: proof_events.append('close')),
                 (launcher, '_tcp_listeners', lambda: rows),
                 (launcher, '_http_health', lambda _port, path: (paths.append(path) or True))):
        launcher._assert_prepublication(77, 303, 222, child_identity, child_authority, 111, 41002, 41001)
    require(paths == ['/_stcore/health','/_stcore/script-health-check'], 'prepublication health order')
    require(proof_events == ['open','recheck','close'], 'prepublication Job proof lifecycle')

class GuardReached(Exception):
    pass

def assert_job_case(launcher, case):
    if case == 'set_job_information_failure':
        closed = []
        kernel = types.SimpleNamespace(CreateJobObjectW=lambda *_args: 77, SetInformationJobObject=lambda *_args: False)
        with patched((launcher, 'kernel32', kernel),
                     (launcher, '_close_handle', lambda handle: closed.append(handle)),
                     (launcher, '_win_error', lambda code, detail: launcher.LauncherError(code, detail))):
            must_raise(launcher._create_job, (launcher.LauncherError,))
        require(closed == [77], 'failed Job handle leak')
    elif case == 'preassignment_cleanup_wait_timeout':
        seen = []
        kernel = types.SimpleNamespace(
            TerminateProcess=lambda handle, code: (seen.append(('terminate', handle, code)) or True),
            WaitForSingleObject=lambda handle, timeout: (seen.append(('wait', handle, timeout)) or launcher.WAIT_TIMEOUT),
        )
        with patched((launcher, 'kernel32', kernel), (launcher, '_guard_forever', lambda: (_ for _ in ()).throw(GuardReached()))):
            must_raise(lambda: launcher._preassignment_cleanup(303), (GuardReached,))
        require(seen == [('terminate', 303, 9), ('wait', 303, 5000)], 'preassignment authority/deadline')
    elif case == 'job_pid_list_exact':
        def query(_job, info_class, pointer, _size, returned):
            target = pointer._obj
            target.NumberOfAssignedProcesses = 1
            target.NumberOfProcessIdsInList = 1
            target.ProcessIdList[0] = 222
            returned._obj.value = 1
            return True
        with patched((launcher, 'kernel32', types.SimpleNamespace(QueryInformationJobObject=query))):
            require(launcher._job_process_ids(77) == [222], 'Job PID list')
    else:
        terminated = []
        process_terminated = []
        cleared = []
        guard = []
        observed_ids = []
        sentinel_alive = [True]
        def terminate_process(handle, code):
            process_terminated.append((handle, code))
            if handle == 999:
                sentinel_alive[0] = False
            return True
        kernel = types.SimpleNamespace(
            TerminateJobObject=lambda job, code: (terminated.append((job, code)) or True),
            TerminateProcess=terminate_process,
            WaitForSingleObject=lambda _handle, _timeout: launcher.WAIT_OBJECT_0,
        )
        active = (lambda _job: 0)
        ids = (lambda _job: [])
        listeners = (lambda *_args: True)
        monotonic_values = iter((0.0, 0.0, 6.0))
        monotonic = (lambda: next(monotonic_values, 6.0))
        if case == 'stop_timeout':
            kernel.WaitForSingleObject = lambda _handle, _timeout: launcher.WAIT_TIMEOUT
            active = lambda _job: 1
            ids = lambda _job: [222]
            listeners = lambda *_args: False
        elif case == 'job_descendant_cleanup':
            active_values = iter((2, 0))
            id_values = iter(([222, 333], []))
            active = lambda _job: next(active_values, 0)
            def descendant_ids(_job):
                value = list(next(id_values, [])); observed_ids.append(value); return value
            ids = descendant_ids
        elif case == 'unrelated_process_survives':
            active_values = iter((1, 0))
            id_values = iter(([222], []))
            active = lambda _job: next(active_values, 0)
            def sentinel_ids(_job):
                value = list(next(id_values, [])); observed_ids.append(value); return value
            ids = sentinel_ids
        changes = (
            (launcher, 'kernel32', kernel),
            (launcher, '_job_active', active),
            (launcher, '_job_process_ids', ids),
            (launcher, '_listeners_gone', listeners),
            (launcher, '_clear_record_exact', lambda *_args: cleared.append('clear')),
            (launcher, '_guard_forever', lambda: (guard.append('guard') or (_ for _ in ()).throw(GuardReached()))),
            (launcher.time, 'sleep', lambda _value: None),
        )
        if case == 'stop_timeout':
            changes = changes + ((launcher.time, 'monotonic', monotonic),)
        with patched(*changes):
            if case == 'stop_timeout':
                must_raise(lambda: launcher._cleanup(77, 303, 222, 111, 41002, 41001, 'record', 'state', b'raw'), (GuardReached,))
            else:
                launcher._cleanup(77, 303, 222, 111, 41002, 41001, 'record', 'state', b'raw')
        require(terminated == [(77, 0)], 'TerminateJobObject count')
        if case == 'stop_timeout':
            require(guard == ['guard'] and not cleared, 'uncertain cleanup cleared record')
        else:
            require(cleared == ['clear'] and not guard, 'safe cleanup proof')
            require(not process_terminated, 'cleanup used PID/process termination')
            if case == 'job_descendant_cleanup':
                require(observed_ids == [[222, 333], []], 'descendant was not observed through Job')
            if case == 'unrelated_process_survives':
                require(sentinel_alive[0] and observed_ids == [[222], []] and all(999 not in row for row in observed_ids), 'unrelated sentinel was touched')

def assert_ui_case(launcher, stage, case):
    paths = []
    if case == 'control_loopback_exclusive':
        original_socket = launcher.socket.socket
        events = []
        class SocketProbe:
            def __init__(self, family, kind):
                events.append(('socket', family, kind))
                self.inner = original_socket(family, kind)
            def setsockopt(self, level, option, value):
                events.append(('setsockopt', level, option, value))
                return self.inner.setsockopt(level, option, value)
            def bind(self, address):
                events.append(('bind', address))
                return self.inner.bind(address)
            def __getattr__(self, name): return getattr(self.inner, name)
        with patched((launcher.socket, 'socket', SocketProbe)):
            listener = launcher._bind_control()
        try:
            address, port = listener.getsockname()
            require(address == '127.0.0.1' and 1024 <= port <= 65535, 'control bind')
            require(('socket', launcher.socket.AF_INET, launcher.socket.SOCK_STREAM) in events, 'control socket family')
            require(('setsockopt', launcher.socket.SOL_SOCKET, launcher.socket.SO_EXCLUSIVEADDRUSE, 1) in events, 'exclusive bind option')
            require(('bind', ('127.0.0.1', 0)) in events, 'control did not request port zero')
            require(listener.getsockopt(launcher.socket.SOL_SOCKET, launcher.socket.SO_EXCLUSIVEADDRUSE) == 1, 'exclusive option not active')
        finally:
            listener.close()
        return
    if case == 'ui_port_zero_discovery':
        assert_child_command(launcher, stage)
    rows = [('127.0.0.1', 41002, 222)]
    sequence = [rows, rows, rows]
    if case == 'control_ui_race_before_publish':
        sequence = [rows, [('127.0.0.1', 41003, 222)], []]
    elif case == 'ui_wildcard_rejected':
        sequence = [[('0.0.0.0', 41002, 222)], []]
    elif case == 'ui_foreign_owner_rejected':
        sequence = [[('127.0.0.1', 41002, 333)], []]
    def listeners():
        return sequence.pop(0) if sequence else []
    def health(_port, path):
        paths.append(path)
        if case == 'streamlit_health_gate' and path == '/_stcore/health':
            return False
        if case == 'streamlit_script_health_gate' and path == '/_stcore/script-health-check':
            return False
        return True
    ticks = iter((0.0, 0.0, 0.1, 0.2, 2.0))
    with patched((launcher, '_tcp_listeners', listeners),
                 (launcher, '_http_health', health),
                 (launcher.time, 'sleep', lambda _value: None),
                 (launcher.time, 'monotonic', lambda: next(ticks, 2.0))):
        if case in ('control_ui_race_before_publish','ui_wildcard_rejected','ui_foreign_owner_rejected','streamlit_health_gate','streamlit_script_health_gate'):
            must_raise(lambda: launcher._discover_ui(222, 41001, 1.0), (launcher.LauncherError,))
        else:
            require(launcher._discover_ui(222, 41001, 1.0) == 41002, 'UI discovery')
    if case not in ('ui_wildcard_rejected','ui_foreign_owner_rejected'):
        require('/_stcore/health' in paths, 'health gate not called')
    if case not in ('streamlit_health_gate','ui_wildcard_rejected','ui_foreign_owner_rejected'):
        require('/_stcore/script-health-check' in paths, 'script-health gate not called')

class FakeConnection:
    def __init__(self, raw):
        self.raw = raw
        self.sent = bytearray()
        self.used = False
    def settimeout(self, _value): pass
    def recv(self, _count):
        if self.used:
            return b''
        self.used = True
        return self.raw
    def sendall(self, value): self.sent.extend(value)
    def close(self): pass

def stage_census(stage):
    rows = []
    for root, directories, files in os.walk(stage, topdown=True, followlinks=False):
        directories.sort(key=lambda value: value.encode('utf-8'))
        files.sort(key=lambda value: value.encode('utf-8'))
        for name in tuple(directories):
            path = pathlib.Path(root) / name
            require(not path.is_symlink(), 'Stage directory reparse in census')
        for name in files:
            path = pathlib.Path(root) / name
            require(not path.is_symlink(), 'Stage file reparse in census')
            digest = hashlib.sha256()
            size = 0
            with path.open('rb') as stream:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk: break
                    size += len(chunk); digest.update(chunk)
            relative = path.relative_to(stage).as_posix()
            rows.append((relative, size, digest.hexdigest().upper()))
    rows.sort(key=lambda row: row[0].encode('utf-8'))
    return tuple(rows)

def forbidden_cache_entries(stage):
    found = []
    for root, directories, files in os.walk(stage, topdown=True, followlinks=False):
        for name in directories:
            if name == '__pycache__': found.append((pathlib.Path(root) / name).relative_to(stage).as_posix())
        for name in files:
            if name.casefold().endswith(('.pyc','.pyo')): found.append((pathlib.Path(root) / name).relative_to(stage).as_posix())
    return tuple(sorted(found, key=lambda value: value.encode('utf-8')))

def assert_no_forbidden_source(source):
    forbidden = ('streamlit','pycalphad','matplotlib','thermogar_app','app.thermogar')
    tree = ast.parse(source)
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import): names = [alias.name for alias in node.names]
        if isinstance(node, ast.ImportFrom): names = [node.module or '']
        for name in names:
            require(not any(name == item or name.startswith(item + '.') for item in forbidden), 'forbidden source import: ' + name)
        if isinstance(node, ast.Call):
            dynamic = isinstance(node.func, ast.Name) and node.func.id == '__import__'
            dynamic = dynamic or (isinstance(node.func, ast.Attribute) and node.func.attr == 'import_module')
            if dynamic and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                name = node.args[0].value
                require(not any(name == item or name.startswith(item + '.') for item in forbidden), 'forbidden dynamic import: ' + name)

def assert_http_case(launcher, case):
    server = launcher.ControlServer(None, 'f' * 64, 'a' * 64, 41001)
    server.ready.set()
    method = 'GET'; path = '/thermogar/health'; credential = 'f' * 64
    if case == 'strict_http_method': method = 'PUT'
    if case == 'strict_http_path': path = '/wrong'
    if case in ('strict_http_authorization','control_credential_mismatch_rejected'): credential = '0' * 64
    version = 'HTTP/1.0' if case == 'strict_http_version' else 'HTTP/1.1'
    headers = ['Host: 127.0.0.1:41001','Authorization: Bearer ' + credential,'Content-Length: 0','Connection: close']
    tail = ''
    if case == 'strict_http_host_wrong': headers[0] = 'Host: 127.0.0.1:41099'
    if case == 'strict_http_host_missing': headers = [item for item in headers if not item.startswith('Host:')]
    if case == 'strict_http_authorization_missing': headers = [item for item in headers if not item.startswith('Authorization:')]
    if case == 'strict_http_authorization_malformed': headers[1] = 'Authorization: Basic ' + ('f' * 64)
    if case == 'strict_http_duplicate_authorization': headers.append('Authorization: Bearer ' + ('f' * 64))
    if case == 'strict_http_malformed_header': headers.append('MalformedHeader')
    if case == 'strict_http_content_length_invalid': headers[2] = 'Content-Length: 00'
    if case == 'strict_http_content_length_conflicting': headers.append('Content-Length: 1')
    if case == 'strict_http_trailing_bytes': tail = 'X'
    if case == 'strict_http_duplicate_header': headers.append('Host: 127.0.0.1:41001')
    if case == 'strict_http_body_rejected': headers[2] = 'Content-Length: 1'; tail = 'X'
    if case == 'strict_http_transfer_encoding': headers.append('Transfer-Encoding: chunked')
    if case == 'strict_http_stop_accepted': method = 'POST'; path = '/thermogar/stop'
    raw = (method + ' ' + path + ' ' + version + '\r\n' + '\r\n'.join(headers) + '\r\n\r\n' + tail).encode('ascii')
    if case == 'strict_http_oversized': raw = b'X' * 9000
    if case == 'strict_http_stopping': server.stopping.set()
    connection = FakeConnection(raw)
    server._handle(connection)
    response = bytes(connection.sent)
    if case == 'control_health_gate':
        require(response.startswith(b'HTTP/1.1 200 ') and not server.stop_requested.is_set(), 'health response')
    elif case == 'strict_http_stop_accepted':
        require(response.startswith(b'HTTP/1.1 202 ') and server.stop_requested.is_set(), 'stop response')
    elif case == 'strict_http_stopping':
        require(response.startswith(b'HTTP/1.1 503 ') and not server.stop_requested.is_set(), 'stopping response')
    else:
        require(not response.startswith(b'HTTP/1.1 200 ') and not response.startswith(b'HTTP/1.1 202 '), 'invalid request accepted')
        require(not server.stop_requested.is_set(), 'invalid request stopped controller')

def assert_child_command(launcher, stage):
    captured = {}
    def create(application, command, _pa, _ta, inherit, flags, environment, cwd, _startup, _info):
        environment_text = ''.join(environment)
        captured.update(application=application, command=command.value, inherit=inherit, flags=flags, cwd=cwd,
                        environment=tuple(item for item in environment_text.split('\0') if item))
        return False
    kernel = types.SimpleNamespace(CreateProcessW=create)
    with patched((launcher, 'kernel32', kernel),
                 (launcher, '_win_error', lambda code, detail: launcher.LauncherError(code, detail))):
        must_raise(lambda: launcher._create_child(str(stage), {'PYTHONDONTWRITEBYTECODE':'1'}), (launcher.LauncherError,))
    command = captured['command']
    require(captured['application'] == str(stage / 'runtime' / 'python.exe'), 'child application')
    require(captured['cwd'] == str(stage) and captured['inherit'] is False, 'child CWD/handles')
    require(' -I ' in command and ' -B ' in command and ' -m streamlit run ' in command, 'child isolated command')
    require('--server.address=127.0.0.1' in command and '--server.port=0' in command, 'child network command')
    require('PYTHONDONTWRITEBYTECODE=1' in captured['environment'], 'child no-pyc environment')

def assert_observer_deadline(health, role, caller):
    record = valid_record(pathlib.Path(caller).parent)
    trust = {'held_handles': [], 'manifest_sha256': 'A' * 64}
    processes = {'supervisor': {'handle': 11}, 'child': {'handle': 22}}
    observed = {}
    clock = iter((100.0, 200.0, 200.0, 200.0, 200.0, 200.0)) if role == 'stop' else iter((100.0,))
    def request(_record, observed_role, deadline):
        require(observed_role == role, 'deadline role')
        observed['request_deadline'] = deadline
        return {'schema':1}
    def stopped(_raw, _record, _state, retained, deadline):
        require(retained is processes, 'stop did not retain exact handles')
        observed['stop_deadline'] = deadline
        return True
    changes = (
        (health.sys, 'argv', [str(caller), '--json']),
        (health, '_validate_trust', lambda *_args: trust),
        (health, '_state_root', lambda: 'synthetic-state'),
        (health, '_read_record', lambda *_args: (b'raw', record)),
        (health, '_validate_identities', lambda *_args: processes),
        (health, '_require_processes_live', lambda _processes: None),
        (health, '_request', request),
        (health, '_stopped', stopped),
        (health, '_close_handle', lambda _handle: None),
        (health.time, 'monotonic', lambda: next(clock, 200.0)),
    )
    with patched(*changes):
        actual, output, error = capture(lambda: health.run_observer(role, str(caller)))
    require(actual == 0 and not error and output, 'observer deadline run')
    require(round((observed['request_deadline'] - 100.0) * 1000) == 3000, 'request deadline is not exact 3000ms')
    if role == 'stop':
        require(round((observed['stop_deadline'] - 200.0) * 1000) == 5000, 'post-STOP deadline is not exact 5000ms')

def assert_stop_proof(health, case, caller):
    if case == 'stop_deadline_5000ms':
        assert_observer_deadline(health, 'stop', caller); return
    if case == 'observer_request_deadline_3000ms':
        assert_observer_deadline(health, 'health', caller); return
    if case == 'stop_changed_record_retained':
        held = {'raw': b'changed', 'handle': None}
        with patched((health, '_open_held', lambda *_args: held)):
            must_raise(lambda: health._record_after_stop('record', 'state', b'expected'), (health.ObserverError,))
        return
    if case == 'stop_identity_uncertainty_retained':
        processes = {'supervisor': {'handle': 11}, 'child': {'handle': 22}}
        with patched((health, '_record_after_stop', lambda *_args: 'ABSENT'),
                     (health, '_held_process_state', lambda _authority: 'UNCERTAIN')):
            must_raise(lambda: health._stopped(b'raw', {'control_port':41001,'ui_port':41002}, 'state', processes, time.monotonic() + 1.0), (health.ObserverError,))
        return
    calls = []
    processes = {'supervisor': {'handle': 11}, 'child': {'handle': 22}}
    presence = {
        'stop_record_absence_probe_one': ['SAME'],
        'stop_exact_handle_death': ['ABSENT'],
        'stop_listener_absence': ['ABSENT'],
        'stop_record_absence_probe_two': ['ABSENT', 'SAME'],
        'stop_complete_proof': ['ABSENT', 'ABSENT'],
    }[case]
    def record_after(*_args):
        calls.append('record')
        return presence.pop(0)
    def process_state(authority):
        calls.append(('process', authority['handle']))
        if case == 'stop_exact_handle_death' and authority['handle'] == 11:
            return 'LIVE'
        return 'DEAD'
    def listeners(_code):
        calls.append('listeners')
        if case == 'stop_listener_absence':
            return [('127.0.0.1', 41001, 111)]
        return []
    with patched((health, '_record_after_stop', record_after),
                 (health, '_held_process_state', process_state),
                 (health, '_listeners', listeners)):
        result = health._stopped(b'raw', {'control_port':41001,'ui_port':41002}, 'state', processes, time.monotonic() + 1.0)
    if case == 'stop_record_absence_probe_one':
        require(not result and calls == ['record'], 'first absence probe boundary')
    elif case == 'stop_exact_handle_death':
        require(not result and ('process',11) in calls and ('process',22) in calls and calls.count('record') == 1, 'exact retained-handle death boundary')
    elif case == 'stop_listener_absence':
        require(not result and calls.count('listeners') == 1 and calls.count('record') == 1, 'listener absence boundary')
    elif case == 'stop_record_absence_probe_two':
        require(not result and calls.count('record') == 2 and calls[-1] == 'record', 'second absence probe boundary')
    else:
        require(result and calls.count('record') == 2 and ('process',11) in calls and ('process',22) in calls and 'listeners' in calls, 'complete stop proof')

def main():
    if len(sys.argv) != 7 or sys.argv[1] != '--case' or sys.argv[3] != '--fixture' or sys.argv[5] != '--stage':
        return 2
    case = sys.argv[2]
    fixture = pathlib.Path(sys.argv[4]).resolve()
    stage = pathlib.Path(sys.argv[6]).resolve()
    require(pathlib.Path.cwd().resolve() == fixture, 'cwd')
    require(os.environ.get('LOCALAPPDATA') == str(fixture), 'LocalAppData')
    launcher_path = stage / 'launcher.pyw'
    health_path = stage / 'healthcheck.py'
    stop_path = stage / 'stop.pyw'
    census_before = None
    cache_before = None
    if case in ('installroot_immutable','program_files_no_pyc'):
        census_before = stage_census(stage)
        cache_before = forbidden_cache_entries(stage)
        require(not cache_before, 'pre-existing forbidden cache in InstallRoot')
    launcher_text = launcher_path.read_text(encoding='utf-8')
    health_text = health_path.read_text(encoding='utf-8')
    stop_text = stop_path.read_text(encoding='utf-8')
    before = set(sys.modules)
    launcher = load('thermogar_synthetic_launcher', launcher_path)
    health = load('thermogar_lifecycle_common', health_path)
    stop = load('thermogar_synthetic_stop', stop_path)
    forbidden = ('streamlit','pycalphad','matplotlib','thermogar_app','app.thermogar')
    require(not any(any(name == item or name.startswith(item + '.') for item in forbidden) for name in set(sys.modules) - before), 'forbidden import')
    if case.startswith('health_forced_exit_'):
        code = int(case.rsplit('_', 1)[1])
        actual, output, error = health_observer_exit(health, code, health_path)
        expected = observer_expected(code)
        require(actual == code and output == expected and not error and b'\n' not in output, 'health failure schema')
    elif case.startswith('stop_forced_exit_'):
        code = int(case.rsplit('_', 1)[1])
        actual, output, error = stop_observer_exit(stop, health, code, stop_path)
        expected = observer_expected(code)
        require(actual == code and output == expected and not error and b'\n' not in output, 'stop failure schema')
    elif case in ('malformed_record_rejected','oversized_record_rejected','reparse_record_rejected','counterfeit_record_rejected'):
        assert_record_rejection(launcher, stage, fixture, case)
    elif case in ('record_missing_noop','record_changed_before_mutation','live_record_fail_closed','uncertain_record_fail_closed'):
        assert_recovery_fail_closed(launcher, stage, fixture, case)
    elif case in ('continuous_reader_publish','continuous_reader_rotate','continuous_reader_clear'):
        assert_continuous_io(launcher, stage, fixture, case)
    elif case in ('stale_record_recovery','stale_two_crash_recovery'):
        assert_recovery_case(launcher, stage, fixture, case)
    elif case in ('normal_start_stop','lock_contention_prepublication','lock_contention_running','assign_job_failure','child_crash_cleanup','controller_crash_cleanup','localappdata_exact_environment','startup_no_retry'):
        assert_launcher_run_case(launcher, stage, fixture, case)
    elif case in ('tcp_owner_mismatch_rejected','tcp_wildcard_rejected','tcp_public_rejected','tcp_duplicate_rejected'):
        require(launcher._has_only_owned_listener([('127.0.0.1', 41001, 101)], '127.0.0.1', 41001, 101), 'owned listener')
        rows = {
            'tcp_owner_mismatch_rejected': [('127.0.0.1',41001,909)],
            'tcp_wildcard_rejected': [('0.0.0.0',41001,101)],
            'tcp_public_rejected': [('192.0.2.10',41001,101)],
            'tcp_duplicate_rejected': [('127.0.0.1',41001,101),('127.0.0.1',41001,102)],
        }[case]
        require(not launcher._has_only_owned_listener(rows, '127.0.0.1', 41001, 101), 'row-specific TCP rejection absent')
    elif case in ('supervisor_pid_mismatch_rejected','child_pid_mismatch_rejected','supervisor_creation_mismatch_rejected','child_creation_mismatch_rejected','supervisor_image_path_mismatch_rejected','child_image_path_mismatch_rejected','supervisor_sha_mismatch_rejected','child_sha_mismatch_rejected','pid_reuse_rejected','process_access_denied_uncertain'):
        assert_identity_case(launcher, stage, case)
    elif case in ('set_job_information_failure','preassignment_cleanup_wait_timeout','job_descendant_cleanup','unrelated_process_survives','stop_timeout','job_pid_list_exact'):
        assert_job_case(launcher, case)
    elif case in ('create_process_failure','job_membership_resume','prepublication_exact_proof'):
        if case == 'create_process_failure':
            assert_child_command(launcher, stage)
        else:
            assert_assignment_case(launcher, stage, case)
    elif case in ('control_ui_race_before_publish','ui_port_zero_discovery','ui_wildcard_rejected','ui_foreign_owner_rejected','control_loopback_exclusive','streamlit_health_gate','streamlit_script_health_gate'):
        assert_ui_case(launcher, stage, case)
    elif case in ('control_credential_mismatch_rejected','strict_http_method','strict_http_path','strict_http_authorization','strict_http_host_wrong','strict_http_host_missing','strict_http_authorization_missing','strict_http_authorization_malformed','strict_http_duplicate_authorization','strict_http_malformed_header','strict_http_content_length_invalid','strict_http_content_length_conflicting','strict_http_trailing_bytes','strict_http_version','strict_http_duplicate_header','strict_http_body_rejected','strict_http_transfer_encoding','strict_http_oversized','strict_http_stopping','strict_http_stop_accepted','control_health_gate'):
        assert_http_case(launcher, case)
    elif case in ('installroot_immutable','program_files_no_pyc'):
        assert_child_command(launcher, stage)
    elif case in ('stop_record_absence_probe_one','stop_exact_handle_death','stop_listener_absence','stop_record_absence_probe_two','stop_complete_proof','stop_changed_record_retained','stop_identity_uncertainty_retained','stop_deadline_5000ms','observer_request_deadline_3000ms'):
        assert_stop_proof(health, case, health_path)
    elif case == 'no_product_or_science_import':
        assert_launcher_run_case(launcher, stage, fixture, 'normal_start_stop')
        assert_no_forbidden_source(launcher_text)
    else:
        raise AssertionError('unimplemented executable seam: ' + case)
    require(not any(any(name == item or name.startswith(item + '.') for item in forbidden) for name in sys.modules), 'forbidden import after executable seam')
    if census_before is not None:
        require(stage_census(stage) == census_before, 'InstallRoot changed')
        require(forbidden_cache_entries(stage) == cache_before == (), 'pyc/cache appeared in InstallRoot')
    sys.stdout.write(PASS % json.dumps(case, ensure_ascii=True, separators=(',', ':')))
    return 0

try:
    raise SystemExit(main())
except SystemExit:
    raise
except Exception:
    raise SystemExit(6)
'@

$pins = [Collections.Generic.List[object]]::new()
$fixture = $null
$fixtureAuthority = $null
$fixtureAuthorityBytes = $null
try {
    $parameters = Get-InvocationMap $args
    $stageRoot = Assert-Input $parameters
    $sourceRoot = Resolve-SourceRoot
    $sourceFiles = [ordered]@{
        'launcher.pyw' = $parameters['ExpectedLauncherSha256']
        'stop.pyw' = $parameters['ExpectedStopSha256']
        'healthcheck.py' = $parameters['ExpectedHealthcheckSha256']
        'generate_runtime_trust_manifest.ps1' = $parameters['ExpectedProducerSha256']
        'verify_runtime_trust_manifest.ps1' = $parameters['ExpectedVerifierSha256']
    }
    foreach ($entry in $sourceFiles.GetEnumerator()) {
        $pins.Add((Open-PinnedFile ([IO.Path]::Combine($sourceRoot, $entry.Key)) $entry.Value))
    }
    foreach ($entry in @(
        @('launcher.pyw',$parameters['ExpectedLauncherSha256']),
        @('stop.pyw',$parameters['ExpectedStopSha256']),
        @('healthcheck.py',$parameters['ExpectedHealthcheckSha256'])
    )) {
        $pins.Add((Open-PinnedFile ([IO.Path]::Combine($stageRoot, $entry[0])) $entry[1]))
    }
    $hostPath = [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
    $trustArguments = [Collections.Generic.List[string]]::new()
    $trustArguments.Add('-NoLogo'); $trustArguments.Add('-NoProfile'); $trustArguments.Add('-NonInteractive'); $trustArguments.Add('-File')
    $trustArguments.Add([IO.Path]::Combine($sourceRoot, 'verify_runtime_trust_manifest.ps1'))
    foreach ($name in $script:Allowed) { $trustArguments.Add('-' + $name); $trustArguments.Add($parameters[$name]) }
    $trust = Invoke-Bounded $hostPath $trustArguments.ToArray() $sourceRoot (New-CleanEnvironment $sourceRoot) 600000
    if ($trust.TimedOut) { Exit-CanonicalFailure 8 }
    if ($trust.ExitCode -ne 0) {
        if ($trust.ExitCode -eq 5) { Exit-CanonicalFailure 5 }
        Exit-CanonicalFailure 4
    }
    if (-not [string]::IsNullOrEmpty($trust.Stderr) -or $trust.Stdout -cnotmatch '^\{"schema":1,"status":"P1B_RUNTIME_TRUST_VERIFIED","execution_root_sha256":"[0-9A-F]{64}","manifest_sha256":"[0-9A-F]{64}","row_count":15035\}$') { Exit-CanonicalFailure 4 }
    foreach ($pin in $pins) { Assert-PinnedFile $pin }
    $local = [Environment]::GetEnvironmentVariable('LOCALAPPDATA')
    if ([string]::IsNullOrEmpty($local) -or -not [IO.Path]::IsPathFullyQualified($local)) { Exit-CanonicalFailure 3 }
    $parent = [IO.Path]::Combine([IO.Path]::GetFullPath($local), 'ThermoGar', 'test-fixtures')
    [void][IO.Directory]::CreateDirectory($parent)
    $rows = [Collections.Generic.List[object]]::new()
    foreach ($case in $script:Cases) {
        $fixtureId = [Guid]::NewGuid().ToString('D').ToLowerInvariant()
        $fixture = [IO.Path]::Combine($parent, $fixtureId)
        if ([IO.Directory]::Exists($fixture) -or [IO.File]::Exists($fixture)) { Exit-CanonicalFailure 9 }
        [void][IO.Directory]::CreateDirectory($fixture)
        $fixtureAuthorityBytes = $script:Utf8.GetBytes('THERMOGAR-P2-FIXTURE:' + $fixtureId)
        $authorityPath = [IO.Path]::Combine($fixture, '.authority')
        $fixtureAuthority = [IO.File]::Open($authorityPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::Read)
        $fixtureAuthority.Write($fixtureAuthorityBytes, 0, $fixtureAuthorityBytes.Length)
        $fixtureAuthority.Flush($true)
        $workerPath = [IO.Path]::Combine($fixture, 'synthetic_worker.py')
        $workerBytes = $script:Utf8.GetBytes($script:Worker)
        $workerStream = [IO.File]::Open($workerPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
        try { $workerStream.Write($workerBytes, 0, $workerBytes.Length); $workerStream.Flush($true) } finally { $workerStream.Dispose() }
        $python = [IO.Path]::Combine($stageRoot, 'runtime', 'python.exe')
        $command = 'runtime/python.exe -I -B -X utf8 synthetic_worker.py --case ' + $case
        $caseArguments = @('-I','-B','-X','utf8',$workerPath,'--case',$case,'--fixture',$fixture,'--stage',$stageRoot)
        $caseTimeout = if ($case -cin @('installroot_immutable','program_files_no_pyc')) { 120000 } else { 5000 }
        $result = Invoke-Bounded $python $caseArguments $fixture (New-CleanEnvironment $fixture) $caseTimeout
        if ($result.TimedOut) { Exit-CanonicalFailure 8 }
        $expected = '{"schema":1,"status":"SYNTHETIC_CASE_PASSED","case":' + (ConvertTo-Json $case -Compress) + '}'
        if ($result.ExitCode -ne 0) { Exit-CanonicalFailure 6 }
        if (-not [string]::IsNullOrEmpty($result.Stderr) -or $result.Stdout -cne $expected) { Exit-CanonicalFailure 7 }
        if ($result.Stdout -match '(?i)(token|nonce)') { Exit-CanonicalFailure 7 }
        $rows.Add([ordered]@{fixture_id=$fixtureId;case=$case;command=$command;expected_exit=0;actual_exit=[int]$result.ExitCode;duration_ms=[int]$result.DurationMs})
        Remove-OwnedFixture $fixture $fixtureAuthority $fixtureAuthorityBytes
        $fixture = $null; $fixtureAuthority = $null; $fixtureAuthorityBytes = $null
    }
    $trustAfter = Invoke-Bounded $hostPath $trustArguments.ToArray() $sourceRoot (New-CleanEnvironment $sourceRoot) 600000
    if ($trustAfter.TimedOut) { Exit-CanonicalFailure 8 }
    if ($trustAfter.ExitCode -ne 0 -or $trustAfter.Stdout -cne $trust.Stdout -or -not [string]::IsNullOrEmpty($trustAfter.Stderr)) { Exit-CanonicalFailure 4 }
    foreach ($pin in $pins) { Assert-PinnedFile $pin }
    $receipt = [ordered]@{schema=1;status='P2_LIFECYCLE_SYNTHETIC_ACCEPTED';row_count=[int]$rows.Count;rows=$rows.ToArray()}
    [Console]::Out.Write(($receipt | ConvertTo-Json -Compress -Depth 4))
    exit 0
} catch {
    Exit-CanonicalFailure 9
} finally {
    if ($null -ne $fixtureAuthority) { try { $fixtureAuthority.Dispose() } catch {} }
    if ($null -ne $fixture -and [IO.Directory]::Exists($fixture)) {
        try {
            $authority = [IO.File]::Open([IO.Path]::Combine($fixture, '.authority'), [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::Read)
            try { Remove-OwnedFixture $fixture $authority $fixtureAuthorityBytes } catch {}
        } catch {}
    }
    foreach ($pin in $pins) { try { $pin.Stream.Dispose() } catch {} }
}
