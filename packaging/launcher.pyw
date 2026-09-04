from __future__ import annotations

import ctypes
from ctypes import wintypes
import datetime as _datetime
import hashlib
import http.client
import json
import os
import secrets
import socket
import struct
import subprocess
import sys
import threading
import time


sys.dont_write_bytecode = True

SCHEMA = 1
HELPER_PATHS = {"launcher.pyw", "stop.pyw", "healthcheck.py"}
# Files that must be present for the install to be runnable. Their sizes and
# hashes make up the install identity, so a run record left behind by a
# different build is rejected instead of being trusted.
REQUIRED_FILES = (
    "app/ThermoGar_app.py",
    "healthcheck.py",
    "launcher.pyw",
    "runtime/python.exe",
    "runtime/pythonw.exe",
    "stop.pyw",
)
REQUIRED_DIRECTORIES = (
    "app",
    "configs",
    "databases/converted",
    "databases/physical",
    "runtime",
)
DATABASE_DIR = "databases/converted"
MAX_REQUIRED_BYTES = 64 * 1024 * 1024
# How long shutdown has to prove the child is gone before the supervisor
# refuses to release run.lock. See _cleanup.
CLEANUP_CONFIRM_SECONDS = 60.0
# How long to keep retrying the run-record delete against a concurrent reader.
RECORD_CLEAR_SECONDS = 30.0
# The two Streamlit probes answer on completely different timescales and cannot
# share a socket timeout. /_stcore/health replies as soon as the server is
# listening. /_stcore/script-health-check replies only once ThermoGar_app.py has
# run to completion, which on a cold start means importing pycalphad and binding
# the default database — measured at 16.6 s on a fresh 0.3.0 install, and slower
# on a cold filesystem cache.
SERVER_HEALTH_TIMEOUT = 1.0
SCRIPT_HEALTH_TIMEOUT = 60.0
# Budget for the whole discovery loop, which needs two consecutive good probes.
UI_DISCOVERY_SECONDS = 240.0
RUN_KEYS = (
    "schema",
    "state",
    "install_identity_sha256",
    "supervisor_pid",
    "supervisor_creation_filetime",
    "supervisor_image_sha256",
    "child_pid",
    "child_creation_filetime",
    "child_image_path",
    "child_image_sha256",
    "control_port",
    "ui_port",
    "nonce",
    "token",
    "published_utc",
)
SHA_RE = __import__("re").compile(r"^[0-9A-F]{64}$")
LOWER_HEX_RE = __import__("re").compile(r"^[0-9a-f]{64}$")
DECIMAL_RE = __import__("re").compile(r"^(0|[1-9][0-9]*)$")
RFC3339_RE = __import__("re").compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$")

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_DIRECTORY = 0x10
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
DELETE_ACCESS = 0x00010000
FILE_SHARE_READ = 0x00000001
OPEN_ALWAYS = 4
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_NAME_NORMALIZED = 0x0
VOLUME_NAME_DOS = 0x0
MOVEFILE_WRITE_THROUGH = 0x8
ERROR_SHARING_VIOLATION = 32
ERROR_LOCK_VIOLATION = 33
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
ERROR_INVALID_PARAMETER = 87
ERROR_ACCESS_DENIED = 5
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

CREATE_SUSPENDED = 0x00000004
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NO_WINDOW = 0x08000000
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
JOB_OBJECT_BASIC_PROCESS_ID_LIST = 3
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
MAX_PREPUBLICATION_JOB_PROCESSES = 64
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
STILL_ACTIVE = 259
AF_INET = 2
TCP_TABLE_OWNER_PID_LISTENER = 3
MIB_TCP_STATE_LISTEN = 2


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)


class FILETIME(ctypes.Structure):
    _fields_ = (("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD))


class STARTUPINFOW(ctypes.Structure):
    _fields_ = (
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    )


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    )


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    )


class IO_COUNTERS(ctypes.Structure):
    _fields_ = tuple((name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
    ))


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION_STRUCT(ctypes.Structure):
    _fields_ = (
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    )


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION_STRUCT(ctypes.Structure):
    _fields_ = (
        ("TotalUserTime", ctypes.c_longlong),
        ("TotalKernelTime", ctypes.c_longlong),
        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
        ("TotalPageFaultCount", wintypes.DWORD),
        ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD),
        ("TotalTerminatedProcesses", wintypes.DWORD),
    )


class FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
    _fields_ = (("FileAttributes", wintypes.DWORD), ("ReparseTag", wintypes.DWORD))


class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", FILETIME),
        ("ftLastAccessTime", FILETIME),
        ("ftLastWriteTime", FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    )


class JOB_OBJECT_BASIC_PROCESS_ID_LIST_MAX(ctypes.Structure):
    _fields_ = (
        ("NumberOfAssignedProcesses", wintypes.DWORD),
        ("NumberOfProcessIdsInList", wintypes.DWORD),
        ("ProcessIdList", ctypes.c_size_t * 4096),
    )


class FILE_DISPOSITION_INFO(ctypes.Structure):
    _fields_ = (("DeleteFile", ctypes.c_ubyte),)


class FILE_RENAME_INFO(ctypes.Structure):
    _fields_ = (
        ("ReplaceIfExists", ctypes.c_ubyte),
        ("RootDirectory", wintypes.HANDLE),
        ("FileNameLength", wintypes.DWORD),
        ("FileName", wintypes.WCHAR * 1),
    )


kernel32.CreateFileW.argtypes = (
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
)
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetFileInformationByHandleEx.argtypes = (
    wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
)
kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
kernel32.GetFileInformationByHandle.argtypes = (
    wintypes.HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION),
)
kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
kernel32.GetFinalPathNameByHandleW.argtypes = (
    wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
)
kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
kernel32.ReadFile.argtypes = (
    wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
)
kernel32.ReadFile.restype = wintypes.BOOL
kernel32.SetFileInformationByHandle.argtypes = (
    wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
)
kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
kernel32.SetInformationJobObject.restype = wintypes.BOOL
kernel32.QueryInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
kernel32.QueryInformationJobObject.restype = wintypes.BOOL
kernel32.CreateProcessW.argtypes = (
    wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID,
    wintypes.BOOL, wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
    ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION),
)
kernel32.CreateProcessW.restype = wintypes.BOOL
kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
kernel32.IsProcessInJob.argtypes = (wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL))
kernel32.IsProcessInJob.restype = wintypes.BOOL
kernel32.ResumeThread.argtypes = (wintypes.HANDLE,)
kernel32.ResumeThread.restype = wintypes.DWORD
kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
kernel32.TerminateJobObject.restype = wintypes.BOOL
kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.GetProcessTimes.argtypes = (
    wintypes.HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME),
)
kernel32.GetProcessTimes.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.GetCurrentProcessId.restype = wintypes.DWORD
kernel32.MoveFileExW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
kernel32.MoveFileExW.restype = wintypes.BOOL
kernel32.DeleteFileW.argtypes = (wintypes.LPCWSTR,)
kernel32.DeleteFileW.restype = wintypes.BOOL
iphlpapi.GetExtendedTcpTable.argtypes = (
    wintypes.LPVOID, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
    wintypes.ULONG, ctypes.c_int, wintypes.ULONG,
)
iphlpapi.GetExtendedTcpTable.restype = wintypes.DWORD


class LauncherError(Exception):
    def __init__(self, code: int, detail: str = "") -> None:
        super().__init__(detail)
        self.code = code


def _win_error(code: int, detail: str) -> LauncherError:
    return LauncherError(code, f"{detail}: win32={ctypes.get_last_error()}")


def _close_handle(handle: int | None) -> None:
    if handle not in (None, 0, INVALID_HANDLE_VALUE):
        kernel32.CloseHandle(handle)


def _is_bool_int(value: object) -> bool:
    return isinstance(value, bool) or not isinstance(value, int)


def _pairs_no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _strict_json(raw: bytes, maximum: int, keys: tuple[str, ...] | None = None) -> dict[str, object]:
    if not raw or len(raw) > maximum or raw.startswith(b"\xef\xbb\xbf") or raw.endswith((b"\n", b"\r")):
        raise ValueError("noncanonical JSON framing")
    text = raw.decode("utf-8", "strict")
    value = json.loads(text, object_pairs_hook=_pairs_no_duplicates, parse_constant=lambda _x: (_ for _ in ()).throw(ValueError("JSON constant")))
    if not isinstance(value, dict) or (keys is not None and tuple(value.keys()) != keys):
        raise ValueError("JSON object keys")
    if _canonical_json(value) != raw:
        raise ValueError("noncanonical JSON bytes")
    return value


def _normal_abs(path: os.PathLike[str] | str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(os.fspath(path))))


def _under(root: str, path: str) -> bool:
    try:
        return os.path.commonpath((_normal_abs(root), _normal_abs(path))) == _normal_abs(root)
    except ValueError:
        return False


def _assert_plain_path(path: str, want_directory: bool) -> os.stat_result:
    st = os.lstat(path)
    attrs = int(getattr(st, "st_file_attributes", 0))
    if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError("reparse point")
    if want_directory != os.path.isdir(path):
        raise ValueError("path type")
    return st


def _assert_plain_chain(root: str, path: str, want_directory: bool) -> None:
    root_abs = _normal_abs(root)
    path_abs = _normal_abs(path)
    if not _under(root_abs, path_abs):
        raise ValueError("path escape")
    _assert_plain_path(root_abs, True)
    relative = os.path.relpath(path_abs, root_abs)
    current = root_abs
    if relative != ".":
        parts = relative.split(os.sep)
        for index, part in enumerate(parts):
            current = os.path.join(current, part)
            _assert_plain_path(current, want_directory if index == len(parts) - 1 else True)


def _strip_extended_path(path: str) -> str:
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def _final_path_from_handle(handle: int) -> str:
    capacity = 32768
    buffer = ctypes.create_unicode_buffer(capacity)
    length = kernel32.GetFinalPathNameByHandleW(
        handle, buffer, capacity, FILE_NAME_NORMALIZED | VOLUME_NAME_DOS,
    )
    if length == 0 or length >= capacity:
        raise _win_error(3, "GetFinalPathNameByHandleW")
    return _normal_abs(_strip_extended_path(buffer.value))


def _read_plain_handle(handle: int, maximum: int) -> tuple[bytes, dict[str, object]]:
    info = BY_HANDLE_FILE_INFORMATION()
    if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise _win_error(3, "GetFileInformationByHandle")
    if info.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY):
        raise ValueError("held path is not a plain file")
    size = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
    if size < 0 or size > maximum:
        raise ValueError("file size")
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        request = min(1024 * 1024, remaining)
        buffer = ctypes.create_string_buffer(request)
        received = wintypes.DWORD(0)
        if not kernel32.ReadFile(handle, buffer, request, ctypes.byref(received), None):
            raise _win_error(3, "ReadFile")
        if received.value == 0 or received.value > request:
            raise ValueError("short held read")
        chunks.append(buffer.raw[:received.value])
        remaining -= received.value
    extra = ctypes.create_string_buffer(1)
    received = wintypes.DWORD(0)
    if not kernel32.ReadFile(handle, extra, 1, ctypes.byref(received), None):
        raise _win_error(3, "ReadFile(EOF)")
    if received.value != 0:
        raise ValueError("held file grew")
    raw = b"".join(chunks)
    if len(raw) != size:
        raise ValueError("held read size")
    identity = {
        "volume": int(info.dwVolumeSerialNumber),
        "index": (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
        "bytes": size,
    }
    return raw, identity


def _open_held_file(path: str, maximum: int, root: str | None = None) -> dict[str, object]:
    expected = _normal_abs(path)
    if root is not None and not _under(root, expected):
        raise ValueError("held path escape")
    ctypes.set_last_error(0)
    handle = kernel32.CreateFileW(
        expected, GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise _win_error(3, "CreateFileW(read)")
    try:
        final_path = _final_path_from_handle(handle)
        if final_path != expected or (root is not None and not _under(root, final_path)):
            raise ValueError("held final path mismatch")
        raw, identity = _read_plain_handle(handle, maximum)
        return {
            "handle": handle,
            "path": final_path,
            "raw": raw,
            "sha256": hashlib.sha256(raw).hexdigest().upper(),
            **identity,
        }
    except Exception:
        _close_handle(handle)
        raise


def _stable_read(path: str, root: str, maximum: int) -> tuple[bytes, str]:
    held = _open_held_file(path, maximum, root)
    try:
        return held["raw"], held["sha256"]
    finally:
        _close_handle(held["handle"])


def _same_file_authority(left: dict[str, object], right: dict[str, object]) -> bool:
    return all(left[key] == right[key] for key in ("path", "volume", "index", "bytes", "sha256"))


def _validate_relative(path: object) -> str:
    if not isinstance(path, str) or not path or len(path) > 1024 or "\\" in path or ":" in path or "\x00" in path:
        raise ValueError("relative path")
    parts = path.split("/")
    if any(not part or part in (".", "..") for part in parts):
        raise ValueError("relative path component")
    return path


def _has_database(install_root: str) -> bool:
    root = os.path.join(install_root, *DATABASE_DIR.split("/"))
    for current, _directories, files in os.walk(root):
        del current
        for name in files:
            if name.lower().endswith(".tdb"):
                return True
    return False


def _install_identity(critical: dict[str, dict[str, object]]) -> str:
    literals = [
        f"{relative}|{critical[relative]['bytes']}|{critical[relative]['sha256']}"
        for relative in sorted(critical)
    ]
    return hashlib.sha256("\r\n".join(literals).encode("utf-8")).hexdigest().upper()


def _validate_install(install_root: str) -> dict[str, object]:
    """Confirm the install tree is complete and derive its identity.

    Every required file is held open for the lifetime of the launcher so it
    cannot be swapped underneath a running instance; the identity is the hash
    of their path|bytes|sha256 rows.
    """
    held_handles: list[int] = []
    critical: dict[str, dict[str, object]] = {}
    success = False
    try:
        _assert_plain_path(install_root, True)
        for relative in REQUIRED_DIRECTORIES:
            directory = os.path.join(install_root, *relative.split("/"))
            _assert_plain_chain(install_root, directory, True)
        for relative in REQUIRED_FILES:
            physical = os.path.join(install_root, *relative.split("/"))
            held = _open_held_file(physical, MAX_REQUIRED_BYTES, install_root)
            held_handles.append(held["handle"])
            critical[relative] = {
                key: held[key]
                for key in ("handle", "path", "volume", "index", "bytes", "sha256")
            }
        if not _has_database(install_root):
            raise ValueError("no thermodynamic database in install")
        success = True
        return {
            "identity_sha256": _install_identity(critical),
            "critical": critical,
            "held_handles": held_handles,
        }
    finally:
        if not success:
            for handle in reversed(held_handles):
                _close_handle(handle)


def _ensure_directory(path: str, parent_root: str) -> None:
    if os.path.exists(path):
        _assert_plain_chain(parent_root, path, True)
        return
    parent = os.path.dirname(path)
    _assert_plain_chain(parent_root, parent, True)
    os.mkdir(path)
    _assert_plain_chain(parent_root, path, True)


def _state_paths() -> dict[str, str]:
    local = os.environ.get("LOCALAPPDATA")
    if not local or not os.path.isabs(local):
        raise LauncherError(3, "LOCALAPPDATA")
    local = _normal_abs(local)
    _assert_plain_path(local, True)
    state = os.path.join(local, "ThermoGar")
    runtime = os.path.join(state, "runtime")
    tmp = os.path.join(runtime, "tmp")
    mpl = os.path.join(runtime, "matplotlib")
    logs = os.path.join(state, "logs")
    for path in (state, runtime, tmp, mpl, logs):
        _ensure_directory(path, local)
    return {
        "state": state, "runtime": runtime, "tmp": tmp, "mpl": mpl, "logs": logs,
        "lock": os.path.join(runtime, "run.lock"),
        "record": os.path.join(runtime, "run.json"),
        "stale": os.path.join(runtime, "run.stale.json"),
    }


def _open_lock(path: str) -> int:
    ctypes.set_last_error(0)
    handle = kernel32.CreateFileW(
        path, GENERIC_READ | GENERIC_WRITE, 0, None, OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        error = ctypes.get_last_error()
        if error in (ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION):
            raise LauncherError(10, "lock contention")
        raise _win_error(9, "CreateFileW(run.lock)")
    info = FILE_ATTRIBUTE_TAG_INFO()
    if not kernel32.GetFileInformationByHandleEx(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        _close_handle(handle)
        raise _win_error(9, "GetFileInformationByHandleEx(run.lock)")
    if info.FileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY):
        _close_handle(handle)
        raise LauncherError(5, "run.lock is not a plain file")
    return handle


def _filetime_value(value: FILETIME) -> str:
    return str((int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime))


def _process_identity_from_handle(handle: int, expected_authority: dict[str, object] | None = None) -> dict[str, object]:
    creation = FILETIME(); exit_ft = FILETIME(); kernel = FILETIME(); user = FILETIME()
    if not kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_ft), ctypes.byref(kernel), ctypes.byref(user)):
        raise _win_error(6, "GetProcessTimes")
    capacity = wintypes.DWORD(32768)
    buffer = ctypes.create_unicode_buffer(capacity.value)
    if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(capacity)):
        raise _win_error(6, "QueryFullProcessImageNameW")
    path = _normal_abs(buffer.value)
    root = os.path.dirname(os.path.dirname(path)) if os.path.basename(os.path.dirname(path)).casefold() == "runtime" else os.path.dirname(path)
    maximum = int(expected_authority["bytes"]) if expected_authority is not None else 128 * 1024 * 1024
    image_file = _open_held_file(path, maximum, root)
    try:
        if expected_authority is not None and not _same_file_authority(image_file, expected_authority):
            raise LauncherError(6, "process image authority mismatch")
        return {
            "creation": _filetime_value(creation),
            "path": image_file["path"],
            "sha256": image_file["sha256"],
            "bytes": image_file["bytes"],
            "volume": image_file["volume"],
            "index": image_file["index"],
        }
    finally:
        _close_handle(image_file["handle"])


def _open_process_identity(pid: int, creation: str, image_path: str, image_sha: str) -> str:
    ctypes.set_last_error(0)
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == ERROR_INVALID_PARAMETER:
            return "DEAD"
        if error in (ERROR_ACCESS_DENIED,):
            return "UNCERTAIN"
        return "UNCERTAIN"
    try:
        identity = _process_identity_from_handle(handle)
        if identity["creation"] != creation or identity["path"] != _normal_abs(image_path) or identity["sha256"] != image_sha:
            return "DEAD"
        result = kernel32.WaitForSingleObject(handle, 0)
        if result == WAIT_OBJECT_0:
            return "DEAD"
        if result != WAIT_TIMEOUT:
            return "UNCERTAIN"
        return "LIVE"
    except Exception:
        return "UNCERTAIN"
    finally:
        _close_handle(handle)


def _tcp_listeners() -> list[tuple[str, int, int]]:
    size = wintypes.DWORD(0)
    result = iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), True, AF_INET, TCP_TABLE_OWNER_PID_LISTENER, 0)
    if result not in (0, 122) or size.value < 4 or size.value > 16 * 1024 * 1024:
        raise LauncherError(6, "GetExtendedTcpTable sizing")
    buffer = ctypes.create_string_buffer(size.value)
    result = iphlpapi.GetExtendedTcpTable(buffer, ctypes.byref(size), True, AF_INET, TCP_TABLE_OWNER_PID_LISTENER, 0)
    if result != 0:
        raise LauncherError(6, "GetExtendedTcpTable")
    count = struct.unpack_from("<I", buffer.raw, 0)[0]
    if count > 1_000_000 or 4 + count * 24 > size.value:
        raise LauncherError(6, "TCP table bounds")
    rows: list[tuple[str, int, int]] = []
    for index in range(count):
        state, local_addr, local_port, _remote_addr, _remote_port, pid = struct.unpack_from("<IIIIII", buffer.raw, 4 + index * 24)
        if state != MIB_TCP_STATE_LISTEN:
            continue
        address = socket.inet_ntoa(struct.pack("<I", local_addr))
        port = socket.ntohs(local_port & 0xFFFF)
        rows.append((address, port, pid))
    return rows


def _has_exact_listener(rows: list[tuple[str, int, int]], address: str, port: int, pid: int) -> bool:
    on_port = [row for row in rows if row[1] == port]
    return len(on_port) == 1 and on_port[0] == (address, port, pid)


def _has_only_owned_listener(rows: list[tuple[str, int, int]], address: str, port: int, pid: int) -> bool:
    owned = [row for row in rows if row[2] == pid]
    return len(owned) == 1 and owned[0] == (address, port, pid) and _has_exact_listener(rows, address, port, pid)


def _validate_run_record(
    raw: bytes, install_root: str, current_identity: str, allow_foreign: bool = False,
) -> dict[str, object]:
    value = _strict_json(raw, 4096, RUN_KEYS)
    if type(value["schema"]) is not int or value["schema"] != 1 or value["state"] != "RUNNING":
        raise ValueError("record state")
    if not isinstance(value["install_identity_sha256"], str) or SHA_RE.fullmatch(value["install_identity_sha256"]) is None:
        raise ValueError("record identity SHA")
    # A record written by a different install (an upgrade, or a second copy)
    # is not ours to trust, but it still has to be cleared out of the way --
    # only after its processes are proved dead. Recovery therefore reads it
    # with allow_foreign; everything else demands an exact binding.
    if not allow_foreign and value["install_identity_sha256"] != current_identity:
        raise ValueError("record identity binding")
    for key in ("supervisor_pid", "child_pid", "control_port", "ui_port"):
        if _is_bool_int(value[key]) or value[key] <= 0:
            raise ValueError("record integer")
    if value["control_port"] == value["ui_port"] or not 1024 <= value["control_port"] <= 65535 or not 1024 <= value["ui_port"] <= 65535:
        raise ValueError("record ports")
    for key in ("supervisor_creation_filetime", "child_creation_filetime"):
        if not isinstance(value[key], str) or DECIMAL_RE.fullmatch(value[key]) is None:
            raise ValueError("record creation")
    for key in ("supervisor_image_sha256", "child_image_sha256"):
        if not isinstance(value[key], str) or SHA_RE.fullmatch(value[key]) is None:
            raise ValueError("record image SHA")
    for key in ("nonce", "token"):
        if not isinstance(value[key], str) or LOWER_HEX_RE.fullmatch(value[key]) is None:
            raise ValueError("record secret")
    if not isinstance(value["published_utc"], str) or RFC3339_RE.fullmatch(value["published_utc"]) is None:
        raise ValueError("record time")
    child_path = value["child_image_path"]
    if not isinstance(child_path, str) or _normal_abs(child_path) != child_path:
        raise ValueError("record child path")
    if not allow_foreign:
        expected_child = _normal_abs(os.path.join(install_root, "runtime", "python.exe"))
        if child_path != expected_child:
            raise ValueError("record child path")
    return value


def _record_is_proved_dead(record: dict[str, object]) -> bool:
    supervisor_path = os.path.join(os.path.dirname(record["child_image_path"]), "pythonw.exe")
    supervisor = _open_process_identity(record["supervisor_pid"], record["supervisor_creation_filetime"], supervisor_path, record["supervisor_image_sha256"])
    child = _open_process_identity(record["child_pid"], record["child_creation_filetime"], record["child_image_path"], record["child_image_sha256"])
    if "UNCERTAIN" in (supervisor, child) or "LIVE" in (supervisor, child):
        return False
    listeners = _tcp_listeners()
    for _address, port, _pid in listeners:
        if port in (record["control_port"], record["ui_port"]):
            return False
    return True


def _read_record(
    path: str, state_root: str, install_root: str, current_identity: str, allow_foreign: bool = False,
) -> tuple[bytes, dict[str, object]]:
    raw, _sha = _stable_read(path, state_root, 4096)
    return raw, _validate_run_record(raw, install_root, current_identity, allow_foreign)


def _open_exact_mutation_handle(path: str, state_root: str, expected_raw: bytes) -> int:
    expected_path = _normal_abs(path)
    if not _under(state_root, expected_path):
        raise LauncherError(5, "record path escape")
    ctypes.set_last_error(0)
    handle = kernel32.CreateFileW(
        expected_path, GENERIC_READ | DELETE_ACCESS, 0, None, OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise _win_error(9, "CreateFileW(record mutation)")
    try:
        if _final_path_from_handle(handle) != expected_path:
            raise LauncherError(5, "record final path mismatch")
        raw, _identity = _read_plain_handle(handle, 4096)
        if raw != expected_raw:
            raise LauncherError(9, "record changed before mutation")
        return handle
    except Exception:
        _close_handle(handle)
        raise


def _delete_exact_file(path: str, state_root: str, expected_raw: bytes) -> None:
    handle = _open_exact_mutation_handle(path, state_root, expected_raw)
    try:
        disposition = FILE_DISPOSITION_INFO(1)
        if not kernel32.SetFileInformationByHandle(
            handle, 4, ctypes.byref(disposition), ctypes.sizeof(disposition),
        ):
            raise _win_error(9, "SetFileInformationByHandle(delete)")
    finally:
        _close_handle(handle)
    if os.path.lexists(path):
        raise LauncherError(9, "record delete not durable")


def _rename_exact_file(source: str, destination: str, state_root: str, expected_raw: bytes) -> None:
    destination_path = _normal_abs(destination)
    if not _under(state_root, destination_path) or os.path.lexists(destination_path):
        raise LauncherError(5, "record rename destination")
    handle = _open_exact_mutation_handle(source, state_root, expected_raw)
    try:
        encoded = destination_path.encode("utf-16-le")
        size = FILE_RENAME_INFO.FileName.offset + len(encoded) + ctypes.sizeof(wintypes.WCHAR)
        buffer = ctypes.create_string_buffer(size)
        info = ctypes.cast(buffer, ctypes.POINTER(FILE_RENAME_INFO)).contents
        info.ReplaceIfExists = 0
        info.RootDirectory = None
        info.FileNameLength = len(encoded)
        ctypes.memmove(ctypes.addressof(buffer) + FILE_RENAME_INFO.FileName.offset, encoded, len(encoded))
        if not kernel32.SetFileInformationByHandle(handle, 3, buffer, size):
            raise _win_error(9, "SetFileInformationByHandle(rename)")
    finally:
        _close_handle(handle)
    if os.path.lexists(source):
        raise LauncherError(9, "record source survived rename")
    observed, _sha = _stable_read(destination_path, state_root, 4096)
    if observed != expected_raw:
        raise LauncherError(9, "record rename identity")


def _recover_stale(paths: dict[str, str], install_root: str, current_identity: str) -> None:
    record_path = paths["record"]
    if not os.path.lexists(record_path):
        return
    try:
        raw, record = _read_record(record_path, paths["state"], install_root, current_identity, True)
    except Exception as exc:
        raise LauncherError(5, "existing run record invalid") from exc
    if not _record_is_proved_dead(record):
        raise LauncherError(6, "existing run record live or uncertain")
    stale_path = paths["stale"]
    if os.path.lexists(stale_path):
        try:
            stale_raw, stale = _read_record(stale_path, paths["state"], install_root, current_identity, True)
        except Exception as exc:
            raise LauncherError(5, "existing stale record invalid") from exc
        if not _record_is_proved_dead(stale):
            raise LauncherError(6, "stale slot live or uncertain")
        _delete_exact_file(stale_path, paths["state"], stale_raw)
    _rename_exact_file(record_path, stale_path, paths["state"], raw)


def _create_job() -> int:
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        raise _win_error(9, "CreateJobObjectW")
    limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION_STRUCT()
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
    limits.BasicLimitInformation.ActiveProcessLimit = MAX_PREPUBLICATION_JOB_PROCESSES
    if not kernel32.SetInformationJobObject(handle, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits)):
        _close_handle(handle)
        raise _win_error(9, "SetInformationJobObject")
    return handle


def _environment_block(values: dict[str, str]) -> ctypes.Array[ctypes.c_wchar]:
    items = sorted(values.items(), key=lambda item: item[0].casefold())
    text = "\0".join(f"{key}={value}" for key, value in items) + "\0\0"
    return ctypes.create_unicode_buffer(text)


def _create_child(install_root: str, env: dict[str, str]) -> PROCESS_INFORMATION:
    python = os.path.join(install_root, "runtime", "python.exe")
    app = os.path.join("app", "ThermoGar_app.py")
    # Изоляция собирается по частям вместо "-I". "-I" включает и "-E", а с
    # ним интерпретатор игнорирует PYTHONHASHSEED: у каждого запуска и у
    # каждого воркера пула равновесий оказывалась своя хеш-затравка, от
    # которой зависит порядок обхода множеств строк внутри pycalphad, а
    # значит и последние биты результата. Остаются "-P" (рабочий каталог не
    # попадает в sys.path) и "-s" (без пользовательского site-packages), а
    # роль "-E" выполняет чистка PYTHON*-переменных в _run перед запуском.
    args = [
        python, "-P", "-s", "-B", "-X", "utf8", "-m", "streamlit", "run", app,
        "--server.address=127.0.0.1", "--server.port=0", "--server.headless=true",
        "--server.fileWatcherType=none", "--server.runOnSave=false",
        "--browser.gatherUsageStats=false", "--server.scriptHealthCheckEnabled=true",
    ]
    command = ctypes.create_unicode_buffer(subprocess.list2cmdline(args))
    environment = _environment_block(env)
    startup = STARTUPINFOW(); startup.cb = ctypes.sizeof(startup)
    info = PROCESS_INFORMATION()
    if not kernel32.CreateProcessW(
        python, command, None, None, False,
        CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW,
        environment, install_root, ctypes.byref(startup), ctypes.byref(info),
    ):
        raise _win_error(9, "CreateProcessW")
    return info


def _verify_assignment_and_resume(job: int, info: PROCESS_INFORMATION) -> None:
    assigned = wintypes.BOOL(False)
    if not kernel32.IsProcessInJob(info.hProcess, job, ctypes.byref(assigned)) or not assigned.value:
        raise _win_error(9, "IsProcessInJob")
    previous = kernel32.ResumeThread(info.hThread)
    if previous != 1:
        raise _win_error(9, "ResumeThread")


def _bind_control() -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(8)
        listener.settimeout(0.25)
        port = listener.getsockname()[1]
        if not 1024 <= port <= 65535:
            raise LauncherError(7, "control port range")
        return listener
    except Exception:
        listener.close()
        raise


def _http_health(port: int, path: str, timeout: float = SERVER_HEALTH_TIMEOUT) -> bool:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
        response = connection.getresponse()
        body = response.read(4097)
        return response.status == 200 and len(body) <= 4096
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


_ui_opened = False


def _open_ui(port: int) -> None:
    """Put the app in front of the user as soon as Streamlit answers at all.

    The child is started with --server.headless=true, so Streamlit opens no
    browser, and nothing else here used to open one either: clicking the Start
    Menu shortcut showed the user nothing, ever. Measured on an installed 0.3.0,
    from the click: /_stcore/health answers 200 at 2.6 s, the app script
    finishes at 32.2 s and the run record is published at 39.4 s. Opening at the
    first 200 means the user sees the page immediately and Streamlit's own
    "Running..." indicator covers the rest of the load.

    This is presentation only. It is called once per run, it feeds nothing back
    into discovery, and a failure to open a browser is not a launch failure, so
    nothing here is allowed to propagate.
    """
    global _ui_opened
    if _ui_opened:
        return
    _ui_opened = True
    try:
        os.startfile(f"http://127.0.0.1:{port}/")
    except OSError:
        pass


def _discover_ui(child_pid: int, control_port: int, timeout_seconds: float = UI_DISCOVERY_SECONDS) -> int:
    deadline = time.monotonic() + timeout_seconds
    stable_port: int | None = None
    while time.monotonic() < deadline:
        listeners = _tcp_listeners()
        owned = [row for row in listeners if row[2] == child_pid]
        if len(owned) == 1:
            address, port, _pid = owned[0]
            canonical = address == "127.0.0.1" and port != control_port and _has_exact_listener(listeners, address, port, child_pid)
            if canonical and 1024 <= port <= 65535 and _http_health(port, "/_stcore/health"):
                _open_ui(port)
                if _http_health(port, "/_stcore/script-health-check", SCRIPT_HEALTH_TIMEOUT):
                    if stable_port == port:
                        fresh = _tcp_listeners()
                        if _has_only_owned_listener(fresh, "127.0.0.1", port, child_pid):
                            return port
                    stable_port = port
                else:
                    stable_port = None
            else:
                stable_port = None
        else:
            stable_port = None
        time.sleep(0.2)
    raise LauncherError(8, "Streamlit UI discovery/health timeout")


_PROCESS_IDENTITY_KEYS = ("creation", "path", "sha256", "bytes", "volume", "index")


def _bounded_job_membership_snapshot(job: int) -> tuple[tuple[int, ...], tuple[int, int, int]]:
    accounting = _job_accounting(job)
    active, total, terminated = accounting
    process_ids = _job_process_ids(job)
    if (
        active != len(process_ids)
        or active < 1
        or active > MAX_PREPUBLICATION_JOB_PROCESSES
        or total < active
        or terminated > total
        or any(not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0 for pid in process_ids)
        or len(set(process_ids)) != len(process_ids)
    ):
        raise LauncherError(9, "Job membership bounds")
    return tuple(sorted(process_ids)), accounting


def _require_live_job_member(job: int, handle: int) -> None:
    wait = kernel32.WaitForSingleObject(handle, 0)
    if wait != WAIT_TIMEOUT:
        raise LauncherError(9, "Job member not live")
    assigned = wintypes.BOOL(False)
    if not kernel32.IsProcessInJob(handle, job, ctypes.byref(assigned)):
        raise _win_error(9, "IsProcessInJob(prepublication)")
    if not assigned.value:
        raise LauncherError(9, "process absent from Job")


def _open_prepublication_job_proof(
    job: int,
    child_handle: int,
    child_pid: int,
    child_identity: dict[str, object],
    child_authority: dict[str, object],
) -> dict[str, object]:
    process_ids, accounting = _bounded_job_membership_snapshot(job)
    if process_ids.count(child_pid) != 1:
        raise LauncherError(9, "canonical child absent from Job")
    try:
        child_creation = int(child_identity["creation"])
    except (KeyError, TypeError, ValueError) as exc:
        raise LauncherError(9, "canonical child identity invalid") from exc

    # The Job is unnamed, its handle is non-inheritable, CreateProcessW uses
    # bInheritHandles=False, and only the verified suspended primary is assigned.
    # Windows therefore admits additional members only through unbreakaway Job
    # inheritance from that primary.  Hold every member handle across all health
    # checks so PID reuse cannot satisfy the two stable membership snapshots.
    members: list[dict[str, object]] = []
    try:
        for pid in process_ids:
            owned = pid != child_pid
            if owned:
                ctypes.set_last_error(0)
                handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
                if not handle:
                    raise _win_error(9, "OpenProcess(Job descendant)")
            else:
                handle = child_handle
            try:
                _require_live_job_member(job, handle)
                identity = _process_identity_from_handle(handle, child_authority if pid == child_pid else None)
                if pid == child_pid:
                    if any(identity[key] != child_identity[key] for key in _PROCESS_IDENTITY_KEYS):
                        raise LauncherError(9, "canonical child identity changed")
                elif int(identity["creation"]) < child_creation:
                    raise LauncherError(9, "Job descendant predates canonical child")
                members.append({"pid": pid, "handle": handle, "owned": owned, "identity": identity})
            except Exception:
                if owned:
                    _close_handle(handle)
                raise
        return {
            "process_ids": process_ids,
            "accounting": accounting,
            "child_pid": child_pid,
            "members": members,
        }
    except Exception:
        for member in reversed(members):
            if member["owned"]:
                _close_handle(member["handle"])
        raise


def _recheck_prepublication_job_proof(job: int, proof: dict[str, object], child_authority: dict[str, object]) -> None:
    process_ids, accounting = _bounded_job_membership_snapshot(job)
    if process_ids != proof["process_ids"] or accounting != proof["accounting"]:
        raise LauncherError(9, "Job membership changed during publication proof")
    for member in proof["members"]:
        handle = member["handle"]
        _require_live_job_member(job, handle)
        expected_authority = child_authority if member["pid"] == proof["child_pid"] else None
        identity = _process_identity_from_handle(handle, expected_authority)
        if any(identity[key] != member["identity"][key] for key in _PROCESS_IDENTITY_KEYS):
            raise LauncherError(9, "Job member identity changed during publication proof")


def _close_prepublication_job_proof(proof: dict[str, object] | None) -> None:
    if proof is None:
        return
    for member in reversed(proof["members"]):
        if member["owned"]:
            _close_handle(member["handle"])


def _assert_prepublication(
    job: int,
    child_handle: int,
    child_pid: int,
    child_identity: dict[str, object],
    child_authority: dict[str, object],
    supervisor_pid: int,
    ui_port: int,
    control_port: int,
) -> None:
    proof: dict[str, object] | None = None
    try:
        proof = _open_prepublication_job_proof(job, child_handle, child_pid, child_identity, child_authority)
        listeners = _tcp_listeners()
        job_listeners = sorted(row for row in listeners if row[2] in proof["process_ids"])
        if job_listeners != [("127.0.0.1", ui_port, child_pid)]:
            raise LauncherError(7, "Job TCP ownership before publication")
        if not _has_only_owned_listener(listeners, "127.0.0.1", control_port, supervisor_pid):
            raise LauncherError(7, "control TCP ownership before publication")
        if not _http_health(ui_port, "/_stcore/health") or not _http_health(
            ui_port, "/_stcore/script-health-check", SCRIPT_HEALTH_TIMEOUT
        ):
            raise LauncherError(8, "UI health before publication")

        listeners = _tcp_listeners()
        job_listeners = sorted(row for row in listeners if row[2] in proof["process_ids"])
        if job_listeners != [("127.0.0.1", ui_port, child_pid)]:
            raise LauncherError(7, "Job TCP ownership changed during publication proof")
        if not _has_only_owned_listener(listeners, "127.0.0.1", control_port, supervisor_pid):
            raise LauncherError(7, "control TCP ownership changed during publication proof")
        _recheck_prepublication_job_proof(job, proof, child_authority)
    finally:
        _close_prepublication_job_proof(proof)


def _publish_record(path: str, state_root: str, record: dict[str, object]) -> bytes:
    raw = _canonical_json(record)
    if len(raw) > 4096 or tuple(record.keys()) != RUN_KEYS:
        raise LauncherError(5, "record construction")
    _validate_run_record(
        raw,
        os.path.dirname(os.path.dirname(record["child_image_path"])),
        record["install_identity_sha256"],
    )
    if os.path.lexists(path):
        raise LauncherError(5, "run record collision")
    temp = os.path.join(os.path.dirname(path), f".run.{secrets.token_hex(16)}.tmp")
    fd = None
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        written = 0
        while written < len(raw):
            count = os.write(fd, raw[written:])
            if count <= 0:
                raise OSError("short record write")
            written += count
        os.fsync(fd)
        os.close(fd); fd = None
        if not kernel32.MoveFileExW(temp, path, MOVEFILE_WRITE_THROUGH):
            raise _win_error(9, "MoveFileExW publish run.json")
    except Exception:
        if fd is not None:
            os.close(fd)
        raise
    return raw


def _response(status: int, reason: str, payload: bytes) -> bytes:
    return (
        f"HTTP/1.1 {status} {reason}\r\nContent-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n"
    ).encode("ascii") + payload


class ControlServer:
    def __init__(self, listener: socket.socket, token: str, nonce: str, port: int) -> None:
        self.listener = listener
        self.token = token
        self.nonce = nonce
        self.port = port
        self.stop_requested = threading.Event()
        self.failed = threading.Event()
        self.stopping = threading.Event()
        self.ready = threading.Event()
        self.serving = threading.Event()
        self._thread_started = False
        self._closed = False
        self._close_lock = threading.Lock()
        self.thread = threading.Thread(target=self._serve, name="ThermoGarControl", daemon=True)

    def start(self) -> None:
        self.thread.start()
        self._thread_started = True
        if not self.serving.wait(2.0) or self.failed.is_set():
            self.close()
            raise LauncherError(9, "control server start")

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            self.stopping.set()
            try:
                self.listener.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.listener.close()
            except OSError:
                pass
            if self._thread_started and self.thread is not threading.current_thread():
                try:
                    self.thread.join(timeout=1.0)
                except RuntimeError:
                    self.failed.set()
                if self.thread.is_alive():
                    self.failed.set()

    def verify_ready(self) -> None:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2.0)
        expected = _canonical_json({"schema": 1, "status": "HEALTHY", "nonce": self.nonce})
        try:
            connection.request(
                "GET", "/thermogar/health",
                headers={"Host": f"127.0.0.1:{self.port}", "Authorization": f"Bearer {self.token}"},
            )
            response = connection.getresponse()
            body = response.read(4097)
            if response.status != 200 or body != expected or self.failed.is_set():
                raise LauncherError(9, "control server readiness")
        except (OSError, http.client.HTTPException) as exc:
            raise LauncherError(9, "control server readiness") from exc
        finally:
            connection.close()

    def _serve(self) -> None:
        try:
            self.serving.set()
            while not self.stopping.is_set():
                try:
                    connection, address = self.listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if not self.stopping.is_set():
                        self.failed.set()
                    break
                try:
                    if address[0] != "127.0.0.1":
                        continue
                    self._handle(connection)
                finally:
                    connection.close()
        except Exception:
            self.failed.set()

    def _handle(self, connection: socket.socket) -> None:
        connection.settimeout(2.0)
        data = bytearray()
        while b"\r\n\r\n" not in data:
            chunk = connection.recv(2048)
            if not chunk:
                return
            data.extend(chunk)
            if len(data) > 8192:
                connection.sendall(_response(413, "Payload Too Large", b'{"schema":1,"status":"REJECTED"}'))
                return
        head, tail = bytes(data).split(b"\r\n\r\n", 1)
        try:
            lines = head.decode("ascii", "strict").split("\r\n")
            request = lines[0].split(" ")
            if len(request) != 3 or request[2] != "HTTP/1.1":
                raise ValueError
            headers: dict[str, str] = {}
            for line in lines[1:]:
                if ":" not in line:
                    raise ValueError
                name, value = line.split(":", 1)
                name = name.strip().lower(); value = value.strip()
                if not name or name in headers:
                    raise ValueError
                headers[name] = value
            if headers.get("host") != f"127.0.0.1:{self.port}" or headers.get("authorization") != f"Bearer {self.token}":
                connection.sendall(_response(403, "Forbidden", b'{"schema":1,"status":"REJECTED"}'))
                return
            if "transfer-encoding" in headers or headers.get("content-length", "0") != "0" or tail:
                raise ValueError
            method, path, _version = request
            if self.stopping.is_set() or not self.ready.is_set():
                connection.sendall(_response(503, "Service Unavailable", b'{"schema":1,"status":"REJECTED"}'))
            elif method == "GET" and path == "/thermogar/health":
                payload = _canonical_json({"schema": 1, "status": "HEALTHY", "nonce": self.nonce})
                connection.sendall(_response(200, "OK", payload))
            elif method == "POST" and path == "/thermogar/stop":
                self.stopping.set()
                self.stop_requested.set()
                payload = _canonical_json({"schema": 1, "status": "STOP_ACCEPTED", "nonce": self.nonce})
                connection.sendall(_response(202, "Accepted", payload))
            else:
                connection.sendall(_response(404, "Not Found", b'{"schema":1,"status":"REJECTED"}'))
        except (UnicodeDecodeError, ValueError, OSError):
            try:
                connection.sendall(_response(400, "Bad Request", b'{"schema":1,"status":"REJECTED"}'))
            except OSError:
                pass


def _job_accounting(job: int) -> tuple[int, int, int]:
    accounting = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION_STRUCT()
    returned = wintypes.DWORD(0)
    if not kernel32.QueryInformationJobObject(job, JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION, ctypes.byref(accounting), ctypes.sizeof(accounting), ctypes.byref(returned)):
        raise _win_error(9, "QueryInformationJobObject")
    if returned.value not in (0, ctypes.sizeof(accounting)):
        raise LauncherError(9, "Job accounting size")
    return (
        int(accounting.ActiveProcesses),
        int(accounting.TotalProcesses),
        int(accounting.TotalTerminatedProcesses),
    )


def _job_active(job: int) -> int:
    return _job_accounting(job)[0]


def _job_process_ids(job: int) -> list[int]:
    values = JOB_OBJECT_BASIC_PROCESS_ID_LIST_MAX()
    returned = wintypes.DWORD(0)
    if not kernel32.QueryInformationJobObject(
        job, JOB_OBJECT_BASIC_PROCESS_ID_LIST, ctypes.byref(values),
        ctypes.sizeof(values), ctypes.byref(returned),
    ):
        raise _win_error(9, "QueryInformationJobObject(PID list)")
    assigned = int(values.NumberOfAssignedProcesses)
    present = int(values.NumberOfProcessIdsInList)
    if assigned != present or present > len(values.ProcessIdList):
        raise LauncherError(9, "Job PID list bounds")
    return [int(values.ProcessIdList[index]) for index in range(present)]


def _clear_record_exact(path: str, state_root: str, expected: bytes) -> None:
    _delete_exact_file(path, state_root, expected)


def _listeners_gone(child_pid: int, supervisor_pid: int, ui_port: int, control_port: int) -> bool:
    recorded_ports = {port for port in (ui_port, control_port) if port > 0}
    for _address, port, _pid in _tcp_listeners():
        if port in recorded_ports:
            return False
    return True


def _guard_forever() -> None:
    while True:
        time.sleep(60.0)


def _log_cleanup_stall(
    state_root: str, child_done: bool, active: int, process_ids: list[int], ports_gone: bool,
) -> None:
    """Record why shutdown could not be confirmed, then let the caller guard.

    Without this a stalled cleanup is a silent hang: the supervisor never
    exits, run.json is never cleared and there is nothing to look at.
    """
    try:
        path = os.path.join(state_root, "logs", "cleanup-stall.log")
        entry = {
            "utc": _datetime.datetime.now(_datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "child_done": bool(child_done),
            "job_active_processes": int(active),
            "job_process_ids": [int(value) for value in process_ids],
            "ports_released": bool(ports_gone),
            "confirm_seconds": CLEANUP_CONFIRM_SECONDS,
        }
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:
        pass


def _cleanup(job: int, child_handle: int, child_pid: int, supervisor_pid: int, ui_port: int, control_port: int, record_path: str | None, state_root: str, record_raw: bytes | None) -> None:
    if not kernel32.TerminateJobObject(job, 0):
        _guard_forever()
    # Tearing down Streamlit plus the pycalphad/numpy DLL set takes well over
    # five seconds the first time a fresh install is exercised. Guarding
    # forever is still the answer when the child cannot be proved dead --
    # releasing run.lock while it might be alive is what the guard prevents --
    # but the budget has to be realistic or every clean stop hangs.
    deadline = time.monotonic() + CLEANUP_CONFIRM_SECONDS
    safe = False
    child_done = False
    active = -1
    process_ids: list[int] = [-1]
    ports_gone = False
    while time.monotonic() < deadline:
        child_done = kernel32.WaitForSingleObject(child_handle, 0) == WAIT_OBJECT_0
        try:
            active = _job_active(job)
            process_ids = _job_process_ids(job)
            ports_gone = _listeners_gone(child_pid, supervisor_pid, ui_port, control_port)
        except Exception:
            active = -1; process_ids = [-1]; ports_gone = False
        if child_done and active == 0 and not process_ids and ports_gone:
            safe = True
            break
        time.sleep(0.1)
    if not safe:
        _log_cleanup_stall(state_root, child_done, active, process_ids, ports_gone)
        _guard_forever()
    if record_path is not None and record_raw is not None:
        # stop.pyw polls run.json while waiting for shutdown, and the delete
        # opens it exclusively, so a single attempt loses the race often. The
        # child is already proved dead here; only bookkeeping is left, so
        # retrying is safe where guarding forever would just strand the
        # supervisor and leave a stale record behind.
        deadline = time.monotonic() + RECORD_CLEAR_SECONDS
        while True:
            try:
                _clear_record_exact(record_path, state_root, record_raw)
                break
            except Exception:
                if not os.path.lexists(record_path):
                    break
                if time.monotonic() >= deadline:
                    _log_cleanup_stall(state_root, child_done, active, process_ids, ports_gone)
                    _guard_forever()
                time.sleep(0.2)


def _preassignment_cleanup(child_handle: int) -> None:
    if not kernel32.TerminateProcess(child_handle, 9):
        _guard_forever()
    if kernel32.WaitForSingleObject(child_handle, 5000) != WAIT_OBJECT_0:
        _guard_forever()


def _run() -> int:
    if len(sys.argv) != 1:
        return 2
    own_authority: dict[str, object] | None = None
    install: dict[str, object] | None = None
    try:
        own_authority = _open_held_file(_normal_abs(__file__), 16 * 1024 * 1024)
        own_path = own_authority["path"]
        install_root = _normal_abs(os.path.dirname(own_path))
        install = _validate_install(install_root)
        if not _same_file_authority(own_authority, install["critical"]["launcher.pyw"]):
            raise ValueError("launcher authority")
        supervisor_pid = int(kernel32.GetCurrentProcessId())
        supervisor_identity = _process_identity_from_handle(
            kernel32.GetCurrentProcess(), install["critical"]["runtime/pythonw.exe"],
        )
    except Exception:
        if install is not None:
            for handle in reversed(install.get("held_handles", [])):
                _close_handle(handle)
        if own_authority is not None:
            _close_handle(own_authority["handle"])
        return 3
    paths: dict[str, str] | None = None
    lock_handle: int | None = None
    job: int | None = None
    info: PROCESS_INFORMATION | None = None
    listener: socket.socket | None = None
    server: ControlServer | None = None
    assigned = False
    preassignment_cleaned = False
    cleanup_done = False
    record_raw: bytes | None = None
    ui_port = 0
    control_port = 0
    result = 9
    try:
        paths = _state_paths()
        lock_handle = _open_lock(paths["lock"])
        _recover_stale(paths, install_root, install["identity_sha256"])
        listener = _bind_control()
        control_port = int(listener.getsockname()[1])
        if not _has_only_owned_listener(_tcp_listeners(), "127.0.0.1", control_port, supervisor_pid):
            raise LauncherError(7, "control TCP ownership")
        job = _create_job()
        # Родительские PYTHON*-переменные отбрасываются целиком: без "-E" они
        # снова действуют, а доверять им нельзя. Дочерний процесс получает
        # только те, что заданы здесь.
        env = {
            name: value
            for name, value in os.environ.items()
            if not name.upper().startswith("PYTHON")
        }
        env.update({
            "THERMOGAR_STATE_ROOT": paths["state"],
            "TMP": paths["tmp"], "TEMP": paths["tmp"],
            "MPLCONFIGDIR": paths["mpl"], "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1", "PYTHONHASHSEED": "0",
        })
        info = _create_child(install_root, env)
        child_identity = _process_identity_from_handle(
            info.hProcess, install["critical"]["runtime/python.exe"],
        )
        try:
            if not kernel32.AssignProcessToJobObject(job, info.hProcess):
                _preassignment_cleanup(info.hProcess)
                preassignment_cleaned = True
                raise _win_error(9, "AssignProcessToJobObject")
            assigned = True
            _verify_assignment_and_resume(job, info)
        finally:
            _close_handle(info.hThread)
            info.hThread = None
        ui_port = _discover_ui(int(info.dwProcessId), control_port)
        nonce = secrets.token_hex(32); token = secrets.token_hex(32)
        published = _datetime.datetime.now(_datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        record = {
            "schema": 1,
            "state": "RUNNING",
            "install_identity_sha256": install["identity_sha256"],
            "supervisor_pid": supervisor_pid,
            "supervisor_creation_filetime": supervisor_identity["creation"],
            "supervisor_image_sha256": supervisor_identity["sha256"],
            "child_pid": int(info.dwProcessId),
            "child_creation_filetime": child_identity["creation"],
            "child_image_path": child_identity["path"],
            "child_image_sha256": child_identity["sha256"],
            "control_port": control_port,
            "ui_port": ui_port,
            "nonce": nonce,
            "token": token,
            "published_utc": published,
        }
        server = ControlServer(listener, token, nonce, control_port)
        listener = None
        server.start()
        server.ready.set()
        server.verify_ready()
        _assert_prepublication(
            job, info.hProcess, int(info.dwProcessId), child_identity,
            install["critical"]["runtime/python.exe"], supervisor_pid, ui_port, control_port,
        )
        if server.failed.is_set() or server.stopping.is_set():
            raise LauncherError(9, "control server changed before publication")
        record_raw = _publish_record(paths["record"], paths["state"], record)
        while True:
            if server.stop_requested.wait(0.1):
                break
            if server.failed.is_set():
                raise LauncherError(9, "control server failed")
            wait = kernel32.WaitForSingleObject(info.hProcess, 0)
            if wait == WAIT_OBJECT_0:
                raise LauncherError(9, "child exited unexpectedly")
            if wait != WAIT_TIMEOUT:
                raise LauncherError(9, "child wait failed")
        server.close(); server = None
        _cleanup(job, info.hProcess, int(info.dwProcessId), supervisor_pid, ui_port, control_port, paths["record"], paths["state"], record_raw)
        cleanup_done = True
        record_raw = None
        result = 0
    except LauncherError as exc:
        result = exc.code
    except Exception:
        result = 9
    finally:
        if server is not None:
            server.close()
        if listener is not None:
            try:
                listener.close()
            except OSError:
                pass
        if assigned and not cleanup_done and job is not None and info is not None and paths is not None:
            record_path = paths["record"] if record_raw is not None else None
            _cleanup(job, info.hProcess, int(info.dwProcessId), supervisor_pid, ui_port, control_port, record_path, paths["state"], record_raw)
        elif info is not None and not assigned and not preassignment_cleaned:
            _preassignment_cleanup(info.hProcess)
        if info is not None:
            _close_handle(info.hThread)
            _close_handle(info.hProcess)
        _close_handle(job)
        _close_handle(lock_handle)
        for handle in reversed(install.get("held_handles", [])):
            _close_handle(handle)
        _close_handle(own_authority["handle"])
    return result


if __name__ == "__main__":
    raise SystemExit(_run())
