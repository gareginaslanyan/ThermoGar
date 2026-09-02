from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import sys
import types


sys.dont_write_bytecode = True

COMMON_NAME = "healthcheck.py"
COMMON_MAX_BYTES = 4 * 1024 * 1024
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


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


kernel32.CreateFileW.argtypes = (
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
)
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL
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


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _emit_failure(code: int) -> int:
    statuses = {
        2: "USAGE", 3: "INSTALL_INVALID", 4: "NO_RUN",
        5: "RECORD_INVALID", 6: "IDENTITY_MISMATCH",
        7: "ENDPOINT_REJECTED", 8: "TIMEOUT", 9: "INTERNAL_ERROR",
    }
    if code not in statuses:
        code = 9
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(_canonical({"schema": 1, "status": statuses[code], "detail_code": code}))
        stream.flush()
    return code


def _normal(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _close(handle: int | None) -> None:
    if handle not in (None, 0, INVALID_HANDLE_VALUE):
        kernel32.CloseHandle(handle)


def _strip_extended(path: str) -> str:
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def _open_held(path: str, maximum: int, root: str | None = None) -> dict[str, object]:
    expected = _normal(path)
    if root is not None:
        root = _normal(root)
        if os.path.commonpath((root, expected)) != root:
            raise ValueError("escape")
    handle = kernel32.CreateFileW(
        expected, GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateFileW")
    try:
        capacity = 32768; final_buffer = ctypes.create_unicode_buffer(capacity)
        length = kernel32.GetFinalPathNameByHandleW(handle, final_buffer, capacity, 0)
        if length == 0 or length >= capacity:
            raise OSError(ctypes.get_last_error(), "GetFinalPathNameByHandleW")
        final = _normal(_strip_extended(final_buffer.value))
        if final != expected or (root is not None and os.path.commonpath((root, final)) != root):
            raise ValueError("final path")
        info = BY_HANDLE_FILE_INFORMATION()
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise OSError(ctypes.get_last_error(), "GetFileInformationByHandle")
        if info.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY):
            raise ValueError("type")
        size = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
        if size < 0 or size > maximum:
            raise ValueError("size")
        chunks: list[bytes] = []; remaining = size
        while remaining:
            request = min(1024 * 1024, remaining)
            buffer = ctypes.create_string_buffer(request); received = wintypes.DWORD(0)
            if not kernel32.ReadFile(handle, buffer, request, ctypes.byref(received), None):
                raise OSError(ctypes.get_last_error(), "ReadFile")
            if received.value == 0 or received.value > request:
                raise ValueError("short read")
            chunks.append(buffer.raw[:received.value]); remaining -= received.value
        extra = ctypes.create_string_buffer(1); received = wintypes.DWORD(0)
        if not kernel32.ReadFile(handle, extra, 1, ctypes.byref(received), None) or received.value != 0:
            raise ValueError("EOF")
        raw = b"".join(chunks)
        return {
            "handle": handle, "path": final, "raw": raw, "bytes": size,
            "sha256": hashlib.sha256(raw).hexdigest().upper(),
            "volume": int(info.dwVolumeSerialNumber),
            "index": (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
        }
    except Exception:
        _close(handle)
        raise


def _load_common():
    handles: list[int] = []
    try:
        own_file = _open_held(_normal(__file__), 16 * 1024 * 1024)
        handles.append(own_file["handle"])
        root = _normal(os.path.dirname(own_file["path"]))
        common_file = _open_held(os.path.join(root, COMMON_NAME), COMMON_MAX_BYTES, root)
        handles.append(common_file["handle"])
        raw = common_file["raw"]
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ValueError("common BOM")
        source = raw.decode("utf-8", "strict")
        code = compile(source, common_file["path"], "exec", dont_inherit=True)
        module = types.ModuleType("_thermogar_observer_common")
        module.__file__ = common_file["path"]
        module.__package__ = None
        exec(code, module.__dict__)
        return module, handles
    except Exception:
        for handle in reversed(handles):
            _close(handle)
        raise


def _run() -> int:
    if sys.argv != [sys.argv[0], "--json"]:
        return _emit_failure(2)
    handles: list[int] = []
    try:
        common, handles = _load_common()
    except Exception:
        return _emit_failure(3)
    try:
        return int(common.run_observer("stop", __file__))
    except Exception:
        return _emit_failure(9)
    finally:
        for handle in reversed(handles):
            _close(handle)


if __name__ == "__main__":
    raise SystemExit(_run())
