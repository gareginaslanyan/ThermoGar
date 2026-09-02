from __future__ import annotations

import ctypes
from ctypes import wintypes
from datetime import datetime
import hashlib
import json
import os
import re
import socket
import struct
import sys
import time


sys.dont_write_bytecode = True

P0_ROOT = "42455F51E284BAD35F5BFD4971F5099889A2A0D4518FFB95310FC5C400461F7F"
RUNTIME_ROOT = "58F81C014DF3C3E8AA6F85517BCEE4263C0AE751365B53CA0ED197964538121C"
NATIVE_ROOT = "A08EC90744637E0CFE3F7E72D8F4564F58D37C190704B660F4267AF02616604C"
TRUST_MANIFEST_REL = "manifests/runtime-trust-manifest.json"
TRUST_RECEIPT_REL = "manifests/runtime-trust-manifest.receipt.json"
EXPECTED_EXECUTION_ROWS = 15035
EXPECTED_PROJECT_ROWS = 29
EXPECTED_PROJECT_BYTES = 2674489
EXPECTED_RUNTIME_ROWS = 15003
EXPECTED_RUNTIME_BYTES = 575844438
HELPERS = {"launcher.pyw", "stop.pyw", "healthcheck.py"}
SHA_RE = re.compile(r"^[0-9A-F]{64}$")
LOWER_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
DECIMAL_RE = re.compile(r"^(0|[1-9][0-9]*)$")
RFC3339_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$")
RUN_KEYS = (
    "schema", "state", "runtime_trust_manifest_sha256", "supervisor_pid",
    "supervisor_creation_filetime", "supervisor_image_sha256", "child_pid",
    "child_creation_filetime", "child_image_path", "child_image_sha256",
    "control_port", "ui_port", "nonce", "token", "published_utc",
)
STATUS = {
    2: "USAGE", 3: "RUNTIME_TRUST_INVALID", 4: "NO_RUN",
    5: "RECORD_INVALID", 6: "IDENTITY_MISMATCH",
    7: "ENDPOINT_REJECTED", 8: "TIMEOUT", 9: "INTERNAL_ERROR",
}

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
ERROR_INVALID_PARAMETER = 87
ERROR_ACCESS_DENIED = 5
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
AF_INET = 2
TCP_TABLE_OWNER_PID_LISTENER = 3
MIB_TCP_STATE_LISTEN = 2

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)


class FILETIME(ctypes.Structure):
    _fields_ = (("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD))


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


kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.GetCurrentProcess.argtypes = ()
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetProcessTimes.argtypes = (
    wintypes.HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME),
    ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME),
)
kernel32.GetProcessTimes.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
)
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.CreateFileW.argtypes = (
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
)
kernel32.CreateFileW.restype = wintypes.HANDLE
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
iphlpapi.GetExtendedTcpTable.argtypes = (
    wintypes.LPVOID, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
    wintypes.ULONG, ctypes.c_int, wintypes.ULONG,
)
iphlpapi.GetExtendedTcpTable.restype = wintypes.DWORD


class ObserverError(Exception):
    def __init__(self, code: int, message: str = "") -> None:
        super().__init__(message)
        self.code = code


class HeldOpenError(OSError):
    def __init__(self, winerror_code: int, path: str) -> None:
        super().__init__(winerror_code, "CreateFileW", path)
        self.winerror_code = winerror_code


def _normal_abs(path: os.PathLike[str] | str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(os.fspath(path))))


def _under(root: str, path: str) -> bool:
    try:
        return os.path.commonpath((_normal_abs(root), _normal_abs(path))) == _normal_abs(root)
    except ValueError:
        return False


def _assert_plain(path: str, want_directory: bool) -> os.stat_result:
    result = os.lstat(path)
    if int(getattr(result, "st_file_attributes", 0)) & FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError("reparse")
    if os.path.isdir(path) != want_directory:
        raise ValueError("type")
    return result


def _assert_chain(root: str, path: str, want_directory: bool) -> None:
    root = _normal_abs(root); path = _normal_abs(path)
    if not _under(root, path):
        raise ValueError("escape")
    _assert_plain(root, True)
    relative = os.path.relpath(path, root)
    current = root
    if relative == ".":
        if not want_directory:
            raise ValueError("type")
        return
    parts = relative.split(os.sep)
    for index, part in enumerate(parts):
        current = os.path.join(current, part)
        _assert_plain(current, want_directory if index == len(parts) - 1 else True)


def _close_handle(handle: int | None) -> None:
    if handle not in (None, 0, INVALID_HANDLE_VALUE):
        kernel32.CloseHandle(handle)


def _strip_extended(path: str) -> str:
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def _final_path(handle: int) -> str:
    capacity = 32768
    buffer = ctypes.create_unicode_buffer(capacity)
    length = kernel32.GetFinalPathNameByHandleW(handle, buffer, capacity, 0)
    if length == 0 or length >= capacity:
        raise OSError(ctypes.get_last_error(), "GetFinalPathNameByHandleW")
    return _normal_abs(_strip_extended(buffer.value))


def _read_handle(handle: int, maximum: int) -> tuple[bytes, dict[str, int]]:
    info = BY_HANDLE_FILE_INFORMATION()
    if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise OSError(ctypes.get_last_error(), "GetFileInformationByHandle")
    if info.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY):
        raise ValueError("held type")
    size = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
    if size < 0 or size > maximum:
        raise ValueError("size")
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        request = min(1024 * 1024, remaining)
        buffer = ctypes.create_string_buffer(request)
        received = wintypes.DWORD(0)
        if not kernel32.ReadFile(handle, buffer, request, ctypes.byref(received), None):
            raise OSError(ctypes.get_last_error(), "ReadFile")
        if received.value == 0 or received.value > request:
            raise ValueError("short read")
        chunks.append(buffer.raw[:received.value]); remaining -= received.value
    extra = ctypes.create_string_buffer(1); received = wintypes.DWORD(0)
    if not kernel32.ReadFile(handle, extra, 1, ctypes.byref(received), None) or received.value != 0:
        raise ValueError("EOF")
    raw = b"".join(chunks)
    if len(raw) != size:
        raise ValueError("read size")
    return raw, {
        "volume": int(info.dwVolumeSerialNumber),
        "index": (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
        "bytes": size,
    }


def _open_held(path: str, maximum: int, root: str | None = None) -> dict[str, object]:
    expected = _normal_abs(path)
    if root is not None and not _under(root, expected):
        raise ValueError("escape")
    handle = kernel32.CreateFileW(
        expected, GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise HeldOpenError(ctypes.get_last_error(), expected)
    try:
        final = _final_path(handle)
        if final != expected or (root is not None and not _under(root, final)):
            raise ValueError("final path")
        raw, identity = _read_handle(handle, maximum)
        return {
            "handle": handle, "path": final, "raw": raw,
            "sha256": hashlib.sha256(raw).hexdigest().upper(), **identity,
        }
    except Exception:
        _close_handle(handle)
        raise


def _stable_read(path: str, root: str, maximum: int) -> tuple[bytes, str]:
    held = _open_held(path, maximum, root)
    try:
        return held["raw"], held["sha256"]
    finally:
        _close_handle(held["handle"])


def _same_authority(left: dict[str, object], right: dict[str, object]) -> bool:
    return all(left[key] == right[key] for key in ("path", "volume", "index", "bytes", "sha256"))


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _json(raw: bytes, maximum: int, keys: tuple[str, ...]) -> dict[str, object]:
    if not raw or len(raw) > maximum or raw.startswith(b"\xef\xbb\xbf") or raw.endswith((b"\r", b"\n")):
        raise ValueError("framing")
    value = json.loads(
        raw.decode("utf-8", "strict"), object_pairs_hook=_pairs,
        parse_constant=lambda _x: (_ for _ in ()).throw(ValueError("constant")),
    )
    if not isinstance(value, dict) or tuple(value.keys()) != keys or _canonical(value) != raw:
        raise ValueError("canonical JSON")
    return value


def _int(value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError("integer")
    return value


def _relative(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 1024 or "\\" in value or ":" in value or "\x00" in value:
        raise ValueError("path")
    if any(not part or part in (".", "..") for part in value.split("/")):
        raise ValueError("path")
    return value


def _current_process_image_path() -> str:
    capacity = wintypes.DWORD(32768)
    buffer = ctypes.create_unicode_buffer(capacity.value)
    if not kernel32.QueryFullProcessImageNameW(
        kernel32.GetCurrentProcess(), 0, buffer, ctypes.byref(capacity)
    ):
        raise OSError(ctypes.get_last_error(), "QueryFullProcessImageNameW")
    return _normal_abs(buffer.value)


def _validate_trust(caller_file: str, role: str) -> dict[str, object]:
    expected_caller = {"health": "healthcheck.py", "stop": "stop.pyw"}.get(role)
    if expected_caller is None:
        raise ValueError("role")
    held_handles: list[int] = []
    critical_authority: dict[str, dict[str, object]] = {}
    success = False
    try:
        caller_file_authority = _open_held(_normal_abs(caller_file), 16 * 1024 * 1024)
        held_handles.append(caller_file_authority["handle"])
        caller = caller_file_authority["path"]
        install_root = _normal_abs(os.path.dirname(caller))
        manifest_path = os.path.join(install_root, *TRUST_MANIFEST_REL.split("/"))
        receipt_path = os.path.join(install_root, *TRUST_RECEIPT_REL.split("/"))
        manifest_file = _open_held(manifest_path, 64 * 1024 * 1024, install_root)
        held_handles.append(manifest_file["handle"])
        manifest_raw = manifest_file["raw"]; manifest_sha = manifest_file["sha256"]
        manifest = _json(manifest_raw, 64 * 1024 * 1024, (
            "schema", "version", "algorithm", "p0_root_sha256",
            "runtime_input_root_sha256", "native_closure_root_sha256",
            "rows", "execution_root_sha256",
        ))
        if type(manifest["schema"]) is not int or manifest["schema"] != 1 or type(manifest["version"]) is not int or manifest["version"] != 1 or manifest["algorithm"] != "SHA-256":
            raise ValueError("manifest metadata")
        if manifest["p0_root_sha256"] != P0_ROOT or manifest["runtime_input_root_sha256"] != RUNTIME_ROOT or manifest["native_closure_root_sha256"] != NATIVE_ROOT:
            raise ValueError("manifest anchors")
        rows = manifest["rows"]
        if not isinstance(rows, list) or len(rows) != EXPECTED_EXECUTION_ROWS:
            raise ValueError("rows")
        previous: str | None = None
        folded: set[str] = set()
        row_map: dict[str, tuple[int, str]] = {}
        all_literals: list[str] = []
        project_literals: list[str] = []
        runtime_literals: list[str] = []
        project_bytes = 0; runtime_bytes = 0; total = 0
        helpers: set[str] = set()
        for row in rows:
            if not isinstance(row, dict) or tuple(row.keys()) != ("path", "bytes", "sha256"):
                raise ValueError("row schema")
            path = _relative(row["path"])
            count = _int(row["bytes"], 0, 1024 * 1024 * 1024)
            sha = row["sha256"]
            if not isinstance(sha, str) or SHA_RE.fullmatch(sha) is None:
                raise ValueError("row SHA")
            if previous is not None and previous >= path or path.casefold() in folded:
                raise ValueError("row order/collision")
            previous = path; folded.add(path.casefold()); row_map[path] = (count, sha)
            literal = f"{path}|{count}|{sha}"; all_literals.append(literal); total += count
            if total > (1 << 63) - 1:
                raise ValueError("total")
            if path.startswith("runtime/"):
                runtime_literals.append(literal); runtime_bytes += count
            elif path in HELPERS:
                helpers.add(path)
            else:
                project_literals.append(literal); project_bytes += count
        project_root = hashlib.sha256("\r\n".join(project_literals).encode()).hexdigest().upper()
        runtime_root = hashlib.sha256("\r\n".join(runtime_literals).encode()).hexdigest().upper()
        execution_root = hashlib.sha256("\r\n".join(all_literals).encode()).hexdigest().upper()
        if len(project_literals) != EXPECTED_PROJECT_ROWS or project_bytes != EXPECTED_PROJECT_BYTES or project_root != P0_ROOT:
            raise ValueError("project root")
        if len(runtime_literals) != EXPECTED_RUNTIME_ROWS or runtime_bytes != EXPECTED_RUNTIME_BYTES or runtime_root != RUNTIME_ROOT:
            raise ValueError("runtime root")
        if helpers != HELPERS or manifest["execution_root_sha256"] != execution_root:
            raise ValueError("execution root/helpers")
        caller_rel = os.path.basename(caller).casefold()
        critical = {
            "launcher.pyw", "healthcheck.py", "stop.pyw",
            "runtime/python.exe", "runtime/pythonw.exe",
        }
        if caller_rel not in {item.casefold() for item in HELPERS}:
            raise ValueError("caller")
        for path in critical:
            if path not in row_map:
                raise ValueError("critical row")
            expected_count, expected_sha = row_map[path]
            physical = os.path.join(install_root, *path.split("/"))
            physical_file = _open_held(physical, expected_count, install_root)
            retained = False
            try:
                if physical_file["bytes"] != expected_count or physical_file["sha256"] != expected_sha:
                    raise ValueError("critical identity")
                held_handles.append(physical_file["handle"]); retained = True
                critical_authority[path] = {
                    key: physical_file[key]
                    for key in ("handle", "path", "volume", "index", "bytes", "sha256")
                }
            finally:
                if not retained:
                    _close_handle(physical_file["handle"])
        caller_key = next(item for item in HELPERS if item.casefold() == caller_rel)
        if caller_key != expected_caller or not _same_authority(
            caller_file_authority, critical_authority[caller_key]
        ):
            raise ValueError("caller authority")
        current_image = _current_process_image_path()
        expected_python = critical_authority["runtime/python.exe"]
        if current_image != expected_python["path"]:
            raise ValueError("observer process image")
        current_image_file = _open_held(
            current_image, int(expected_python["bytes"]), install_root
        )
        held_handles.append(current_image_file["handle"])
        if not _same_authority(current_image_file, expected_python):
            raise ValueError("observer process authority")
        receipt_file = _open_held(receipt_path, 65536, install_root)
        held_handles.append(receipt_file["handle"])
        receipt_raw = receipt_file["raw"]; receipt_sha = receipt_file["sha256"]
        receipt = _json(receipt_raw, 65536, (
            "schema", "version", "algorithm", "manifest_sha256",
            "execution_root_sha256", "row_count", "total_bytes",
            "producer_sha256", "verifier_sha256",
        ))
        if type(receipt["schema"]) is not int or receipt["schema"] != 1 or type(receipt["version"]) is not int or receipt["version"] != 1 or receipt["algorithm"] != "SHA-256":
            raise ValueError("receipt metadata")
        if receipt["manifest_sha256"] != manifest_sha or receipt["execution_root_sha256"] != execution_root:
            raise ValueError("receipt roots")
        if _int(receipt["row_count"], 0, 1_000_000) != len(rows) or _int(receipt["total_bytes"], 0, (1 << 63) - 1) != total:
            raise ValueError("receipt counts")
        for key in ("producer_sha256", "verifier_sha256"):
            if not isinstance(receipt[key], str) or SHA_RE.fullmatch(receipt[key]) is None:
                raise ValueError("receipt identity")
        success = True
        return {
            "install_root": install_root, "manifest_sha256": manifest_sha,
            "receipt_sha256": receipt_sha, "rows": row_map,
            "critical": critical_authority, "held_handles": held_handles,
        }
    finally:
        if not success:
            for handle in reversed(held_handles):
                _close_handle(handle)


def _state_root() -> str:
    local = os.environ.get("LOCALAPPDATA")
    if not local or not os.path.isabs(local):
        raise ObserverError(5, "LOCALAPPDATA")
    local = _normal_abs(local)
    try:
        _assert_plain(local, True)
    except FileNotFoundError as exc:
        raise ObserverError(5, "LOCALAPPDATA") from exc
    except ValueError as exc:
        raise ObserverError(5, "LOCALAPPDATA") from exc
    except OSError as exc:
        raise ObserverError(9, "LOCALAPPDATA uncertainty") from exc
    state = os.path.join(local, "ThermoGar")
    runtime = os.path.join(state, "runtime")
    try:
        _assert_chain(local, state, True)
    except FileNotFoundError as exc:
        raise ObserverError(4, "no state") from exc
    except ValueError as exc:
        raise ObserverError(5, "state chain") from exc
    except OSError as exc:
        raise ObserverError(9, "state uncertainty") from exc
    try:
        _assert_chain(state, runtime, True)
    except FileNotFoundError as exc:
        raise ObserverError(4, "no runtime state") from exc
    except ValueError as exc:
        raise ObserverError(5, "runtime state chain") from exc
    except OSError as exc:
        raise ObserverError(9, "runtime state uncertainty") from exc
    return state


def _validate_record(raw: bytes, install_root: str, manifest_sha: str) -> dict[str, object]:
    value = _json(raw, 4096, RUN_KEYS)
    if type(value["schema"]) is not int or value["schema"] != 1 or value["state"] != "RUNNING" or value["runtime_trust_manifest_sha256"] != manifest_sha:
        raise ValueError("record state/trust")
    for key in ("supervisor_pid", "child_pid"):
        _int(value[key], 1, (1 << 32) - 1)
    for key in ("control_port", "ui_port"):
        _int(value[key], 1024, 65535)
    if value["control_port"] == value["ui_port"]:
        raise ValueError("ports")
    for key in ("supervisor_creation_filetime", "child_creation_filetime"):
        if not isinstance(value[key], str) or DECIMAL_RE.fullmatch(value[key]) is None:
            raise ValueError("creation")
        creation = int(value[key], 10)
        if not 0 <= creation <= (1 << 64) - 1:
            raise ValueError("creation bounds")
    for key in ("supervisor_image_sha256", "child_image_sha256"):
        if not isinstance(value[key], str) or SHA_RE.fullmatch(value[key]) is None:
            raise ValueError("image SHA")
    for key in ("nonce", "token"):
        if not isinstance(value[key], str) or LOWER_HEX_RE.fullmatch(value[key]) is None:
            raise ValueError("secret")
    if not isinstance(value["published_utc"], str) or RFC3339_RE.fullmatch(value["published_utc"]) is None:
        raise ValueError("time")
    try:
        published = datetime.strptime(value["published_utc"], "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise ValueError("time") from exc
    if published.strftime("%Y-%m-%dT%H:%M:%S.%fZ") != value["published_utc"]:
        raise ValueError("time canonical")
    expected_child = _normal_abs(os.path.join(install_root, "runtime", "python.exe"))
    if value["child_image_path"] != expected_child:
        raise ValueError("child path")
    return value


def _read_record(state: str, trust: dict[str, object]) -> tuple[bytes, dict[str, object]]:
    path = os.path.join(state, "runtime", "run.json")
    try:
        raw, _sha = _stable_read(path, state, 4096)
        return raw, _validate_record(raw, trust["install_root"], trust["manifest_sha256"])
    except HeldOpenError as exc:
        if exc.winerror_code in (ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND):
            raise ObserverError(4, "no run") from exc
        raise ObserverError(9, "record open uncertainty") from exc
    except ObserverError:
        raise
    except ValueError as exc:
        raise ObserverError(5, "record") from exc
    except OSError as exc:
        raise ObserverError(9, "record read uncertainty") from exc


def _creation_value(value: FILETIME) -> str:
    return str((int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime))


def _open_process_authority(
    pid: int, creation: str, path: str, sha: str, trust: dict[str, object]
) -> dict[str, object]:
    ctypes.set_last_error(0)
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
    if not handle:
        raise ObserverError(6, "process open")
    retained = False
    try:
        created = FILETIME(); exited = FILETIME(); kernel = FILETIME(); user = FILETIME()
        if not kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
            raise ValueError("process times")
        capacity = wintypes.DWORD(32768); buffer = ctypes.create_unicode_buffer(capacity.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(capacity)):
            raise ValueError("process image")
        observed_path = _normal_abs(buffer.value)
        if _creation_value(created) != creation or observed_path != _normal_abs(path):
            raise ValueError("process identity")
        relative = os.path.relpath(observed_path, trust["install_root"]).replace("\\", "/")
        expected = trust["rows"].get(relative)
        if expected is None or expected[1] != sha:
            raise ValueError("process row")
        expected_authority = trust["critical"].get(relative)
        if expected_authority is None:
            raise ValueError("process authority row")
        image_file = _open_held(observed_path, expected[0], trust["install_root"])
        try:
            if image_file["sha256"] != sha or not _same_authority(image_file, expected_authority):
                raise ValueError("process image authority")
        finally:
            _close_handle(image_file["handle"])
        wait = kernel32.WaitForSingleObject(handle, 0)
        if wait != WAIT_TIMEOUT:
            raise ValueError("process not live")
        retained = True
        return {
            "handle": handle, "pid": pid, "creation_filetime": creation,
            "path": observed_path, "sha256": sha,
        }
    except ObserverError:
        raise
    except Exception as exc:
        raise ObserverError(6, "process identity") from exc
    finally:
        if not retained:
            _close_handle(handle)


def _held_process_state(authority: dict[str, object]) -> str:
    wait = kernel32.WaitForSingleObject(authority["handle"], 0)
    if wait == WAIT_OBJECT_0:
        return "DEAD"
    if wait == WAIT_TIMEOUT:
        return "LIVE"
    return "UNCERTAIN"


def _require_processes_live(processes: dict[str, dict[str, object]]) -> None:
    if any(_held_process_state(authority) != "LIVE" for authority in processes.values()):
        raise ObserverError(6, "process exited")


def _listeners(error_code: int) -> list[tuple[str, int, int]]:
    size = wintypes.DWORD(0)
    result = iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), True, AF_INET, TCP_TABLE_OWNER_PID_LISTENER, 0)
    if result not in (0, 122) or not 4 <= size.value <= 16 * 1024 * 1024:
        raise ObserverError(error_code, "TCP sizing")
    buffer = ctypes.create_string_buffer(size.value)
    if iphlpapi.GetExtendedTcpTable(buffer, ctypes.byref(size), True, AF_INET, TCP_TABLE_OWNER_PID_LISTENER, 0) != 0:
        raise ObserverError(error_code, "TCP table")
    count = struct.unpack_from("<I", buffer.raw, 0)[0]
    if count > 1_000_000 or 4 + count * 24 > size.value:
        raise ObserverError(error_code, "TCP bounds")
    rows: list[tuple[str, int, int]] = []
    for index in range(count):
        state, local_addr, local_port, _ra, _rp, pid = struct.unpack_from("<IIIIII", buffer.raw, 4 + index * 24)
        if state == MIB_TCP_STATE_LISTEN:
            rows.append((socket.inet_ntoa(struct.pack("<I", local_addr)), socket.ntohs(local_port & 0xFFFF), pid))
    return rows


def _validate_identities(
    record: dict[str, object], trust: dict[str, object]
) -> dict[str, dict[str, object]]:
    root = trust["install_root"]
    supervisor_path = _normal_abs(os.path.join(root, "runtime", "pythonw.exe"))
    child_path = _normal_abs(os.path.join(root, "runtime", "python.exe"))
    processes: dict[str, dict[str, object]] = {}
    success = False
    try:
        processes["supervisor"] = _open_process_authority(
            record["supervisor_pid"], record["supervisor_creation_filetime"],
            supervisor_path, record["supervisor_image_sha256"], trust,
        )
        processes["child"] = _open_process_authority(
            record["child_pid"], record["child_creation_filetime"],
            child_path, record["child_image_sha256"], trust,
        )
        rows = _listeners(7)
        control = [(a, p, pid) for a, p, pid in rows if p == record["control_port"]]
        ui = [(a, p, pid) for a, p, pid in rows if p == record["ui_port"]]
        supervisor_owned = [(a, p, pid) for a, p, pid in rows if pid == record["supervisor_pid"]]
        child_owned = [(a, p, pid) for a, p, pid in rows if pid == record["child_pid"]]
        if control != [("127.0.0.1", record["control_port"], record["supervisor_pid"])]:
            raise ObserverError(7, "control owner")
        if ui != [("127.0.0.1", record["ui_port"], record["child_pid"])]:
            raise ObserverError(7, "UI owner")
        if supervisor_owned != control or child_owned != ui:
            raise ObserverError(7, "noncanonical listener")
        _require_processes_live(processes)
        success = True
        return processes
    finally:
        if not success:
            for authority in reversed(tuple(processes.values())):
                _close_handle(authority.get("handle"))


def _remaining_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0.0:
        raise ObserverError(8, "endpoint timeout")
    return remaining


def _request(
    record: dict[str, object], role: str, deadline: float
) -> dict[str, object]:
    method = "GET" if role == "health" else "POST"
    path = "/thermogar/health" if role == "health" else "/thermogar/stop"
    port = record["control_port"]
    request = (
        f"{method} {path} HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        f"Authorization: Bearer {record['token']}\r\n"
        "Content-Length: 0\r\nConnection: close\r\n\r\n"
    ).encode("ascii")
    connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        connection.settimeout(_remaining_seconds(deadline))
        connection.connect(("127.0.0.1", port))
        connection.settimeout(_remaining_seconds(deadline))
        connection.sendall(request)
        response = bytearray()
        while b"\r\n\r\n" not in response:
            connection.settimeout(_remaining_seconds(deadline))
            chunk = connection.recv(2048)
            if not chunk:
                raise ObserverError(7, "endpoint closed before headers")
            response.extend(chunk)
            if len(response) > 8192:
                raise ObserverError(7, "endpoint headers")
        head, initial_body = bytes(response).split(b"\r\n\r\n", 1)
        lines = head.decode("ascii", "strict").split("\r\n")
        status_parts = lines[0].split(" ", 2)
        if (
            len(status_parts) != 3
            or status_parts[0] != "HTTP/1.1"
            or re.fullmatch(r"[0-9]{3}", status_parts[1]) is None
        ):
            raise ObserverError(7, "endpoint status line")
        status = int(status_parts[1], 10)
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" not in line:
                raise ObserverError(7, "endpoint header")
            name, value = line.split(":", 1)
            name = name.strip().casefold(); value = value.strip()
            if not name or name in headers:
                raise ObserverError(7, "endpoint header")
            headers[name] = value
        length_text = headers.get("content-length")
        if (
            length_text is None
            or re.fullmatch(r"0|[1-9][0-9]*", length_text) is None
            or "transfer-encoding" in headers
            or headers.get("content-type") != "application/json"
            or headers.get("connection", "").casefold() != "close"
        ):
            raise ObserverError(7, "endpoint framing")
        content_length = int(length_text, 10)
        if content_length > 4096 or len(initial_body) > content_length:
            raise ObserverError(7, "endpoint body bounds")
        body = bytearray(initial_body)
        while len(body) < content_length:
            connection.settimeout(_remaining_seconds(deadline))
            chunk = connection.recv(min(2048, content_length - len(body)))
            if not chunk:
                raise ObserverError(7, "endpoint short body")
            body.extend(chunk)
        _remaining_seconds(deadline)
        raw = bytes(body)
    except (TimeoutError, socket.timeout) as exc:
        raise ObserverError(8, "endpoint timeout") from exc
    except ObserverError:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ObserverError(7, "endpoint") from exc
    finally:
        connection.close()
    expected_status = 200 if role == "health" else 202
    expected_word = "HEALTHY" if role == "health" else "STOP_ACCEPTED"
    if status != expected_status or len(raw) > 4096:
        raise ObserverError(7, "endpoint status")
    try:
        payload = _json(raw, 4096, ("schema", "status", "nonce"))
    except Exception as exc:
        raise ObserverError(7, "endpoint JSON") from exc
    if type(payload["schema"]) is not int or payload != {"schema": 1, "status": expected_word, "nonce": record["nonce"]}:
        raise ObserverError(7, "endpoint response")
    return payload


def _before_deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise ObserverError(8, "stop timeout")


def _record_after_stop(path: str, state: str, expected_raw: bytes) -> str:
    try:
        held = _open_held(path, 4096, state)
    except HeldOpenError as exc:
        if exc.winerror_code in (ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND):
            return "ABSENT"
        raise ObserverError(9, "record open uncertainty after stop") from exc
    except OSError as exc:
        raise ObserverError(9, "record probe after stop") from exc
    except ValueError as exc:
        raise ObserverError(5, "record invalid after stop") from exc
    try:
        if held["raw"] != expected_raw:
            raise ObserverError(5, "record changed after stop")
        return "SAME"
    finally:
        _close_handle(held["handle"])


def _stopped(
    record_raw: bytes,
    record: dict[str, object],
    state: str,
    processes: dict[str, dict[str, object]],
    deadline: float,
) -> bool:
    path = os.path.join(state, "runtime", "run.json")
    _before_deadline(deadline)
    if _record_after_stop(path, state, record_raw) == "SAME":
        _before_deadline(deadline)
        return False
    _before_deadline(deadline)
    supervisor = _held_process_state(processes["supervisor"])
    child = _held_process_state(processes["child"])
    if supervisor == "UNCERTAIN" or child == "UNCERTAIN":
        raise ObserverError(9, "identity uncertainty after stop")
    _before_deadline(deadline)
    for _address, port, _pid in _listeners(9):
        if port in (record["control_port"], record["ui_port"]):
            _before_deadline(deadline)
            return False
    _before_deadline(deadline)
    if supervisor != "DEAD" or child != "DEAD":
        return False
    final_presence = _record_after_stop(path, state, record_raw)
    _before_deadline(deadline)
    return final_presence == "ABSENT"


def _emit(value: dict[str, object]) -> None:
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(_canonical(value)); stream.flush()


def _failure(code: int) -> int:
    if code not in STATUS:
        code = 9
    _emit({"schema": 1, "status": STATUS[code], "detail_code": code})
    return code


def run_observer(role: str, caller_file: str) -> int:
    if role not in ("health", "stop"):
        return _failure(9)
    if sys.argv != [sys.argv[0], "--json"]:
        return _failure(2)
    trust: dict[str, object] | None = None
    processes: dict[str, dict[str, object]] | None = None
    try:
        try:
            trust = _validate_trust(caller_file, role)
        except Exception as exc:
            raise ObserverError(3, "trust") from exc
        state = _state_root()
        record_raw, record = _read_record(state, trust)
        processes = _validate_identities(record, trust)
        _require_processes_live(processes)
        if role == "health":
            _request(record, role, time.monotonic() + 3.0)
            _require_processes_live(processes)
            _emit({
                "schema": 1, "status": "HEALTHY",
                "runtime_trust_manifest_sha256": trust["manifest_sha256"],
                "supervisor_pid": record["supervisor_pid"],
                "supervisor_creation_filetime": record["supervisor_creation_filetime"],
                "child_pid": record["child_pid"],
                "child_creation_filetime": record["child_creation_filetime"],
                "control_port": record["control_port"], "ui_port": record["ui_port"],
                "nonce": record["nonce"],
            })
            return 0
        _request(record, role, time.monotonic() + 3.0)
        deadline = time.monotonic() + 5.0
        _before_deadline(deadline)
        while True:
            _before_deadline(deadline)
            if _stopped(record_raw, record, state, processes, deadline):
                _before_deadline(deadline)
                _emit({
                    "schema": 1, "status": "STOPPED",
                    "supervisor_pid": record["supervisor_pid"],
                    "supervisor_creation_filetime": record["supervisor_creation_filetime"],
                    "nonce": record["nonce"],
                })
                return 0
            remaining = deadline - time.monotonic()
            if remaining <= 0.0:
                raise ObserverError(8, "stop timeout")
            time.sleep(min(0.1, remaining))
    except ObserverError as exc:
        return _failure(exc.code)
    except Exception:
        return _failure(9)
    finally:
        if processes is not None:
            for authority in reversed(tuple(processes.values())):
                _close_handle(authority.get("handle"))
        if trust is not None:
            for handle in reversed(trust.get("held_handles", [])):
                _close_handle(handle)


if __name__ == "__main__":
    raise SystemExit(run_observer("health", __file__))
