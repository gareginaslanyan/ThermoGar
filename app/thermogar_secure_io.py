"""Fail-closed local file snapshots and atomic sibling replacement."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
import ctypes
import hashlib
import os
import re
import stat
import uuid
from typing import Any, Callable, Iterator, TypeVar


MAX_TDB_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_WORKSPACE_FILE_BYTES = 64 * 1024 * 1024
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_BINARY_FLAG = getattr(os, "O_BINARY", 0)
_NOFOLLOW_FLAG = getattr(os, "O_NOFOLLOW", 0)
_T = TypeVar("_T")


class SecureIOError(RuntimeError):
    """A local path or file changed across a protected operation."""


@dataclass(frozen=True)
class VerifiedSnapshot:
    data: bytes
    sha256: str
    size: int
    identity: tuple[int, int]
    metadata: tuple[int, int, int, int, int, int]


def lexical_absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _path_components(path: Path) -> tuple[Path, ...]:
    absolute = lexical_absolute(path)
    anchor = Path(absolute.anchor)
    components: list[Path] = [anchor]
    current = anchor
    for part in absolute.parts[1:]:
        current = current / part
        components.append(current)
    return tuple(components)


def _is_reparse_or_symlink(path_stat: os.stat_result) -> bool:
    if stat.S_ISLNK(path_stat.st_mode):
        return True
    attributes = getattr(path_stat, "st_file_attributes", 0)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_attribute)


def assert_plain_path(
    path: str | Path,
    *,
    leaf_may_be_missing: bool = False,
    leaf_must_be_directory: bool = False,
) -> Path:
    absolute = lexical_absolute(path)
    components = _path_components(absolute)
    for index, component in enumerate(components):
        is_leaf = index == len(components) - 1
        try:
            component_stat = component.lstat()
        except FileNotFoundError:
            if is_leaf and leaf_may_be_missing:
                return absolute
            raise SecureIOError(f"Path component is missing: {component}") from None
        if _is_reparse_or_symlink(component_stat):
            raise SecureIOError(f"Reparse or symlink path is forbidden: {component}")
        if not is_leaf and not stat.S_ISDIR(component_stat.st_mode):
            raise SecureIOError(f"Non-directory path component: {component}")
        if is_leaf and leaf_must_be_directory and not stat.S_ISDIR(
            component_stat.st_mode
        ):
            raise SecureIOError(f"Expected directory path: {component}")
    return absolute


if os.name == "nt":
    import msvcrt

    class _FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
        _fields_ = [
            ("FileAttributes", ctypes.c_uint32),
            ("ReparseTag", ctypes.c_uint32),
        ]

    class _FILE_ID_128(ctypes.Structure):
        _fields_ = [("Identifier", ctypes.c_ubyte * 16)]

    class _FILE_ID_INFO(ctypes.Structure):
        _fields_ = [
            ("VolumeSerialNumber", ctypes.c_uint64),
            ("FileId", _FILE_ID_128),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _CreateFileW = _kernel32.CreateFileW
    _CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    _CreateFileW.restype = ctypes.c_void_p
    _CloseHandle = _kernel32.CloseHandle
    _CloseHandle.argtypes = [ctypes.c_void_p]
    _CloseHandle.restype = ctypes.c_int
    _GetFinalPathNameByHandleW = _kernel32.GetFinalPathNameByHandleW
    _GetFinalPathNameByHandleW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
    ]
    _GetFinalPathNameByHandleW.restype = ctypes.c_uint32
    _GetFileInformationByHandleEx = _kernel32.GetFileInformationByHandleEx
    _GetFileInformationByHandleEx.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    _GetFileInformationByHandleEx.restype = ctypes.c_int

    _INVALID_HANDLE = ctypes.c_void_p(-1).value
    _GENERIC_READ = 0x80000000
    _FILE_READ_ATTRIBUTES = 0x00000080
    _FILE_SHARE_READ = 0x00000001
    _FILE_SHARE_WRITE = 0x00000002
    _FILE_SHARE_DELETE = 0x00000004
    _OPEN_EXISTING = 3
    _FILE_ATTRIBUTE_NORMAL = 0x00000080
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
def _require_windows_pinning() -> None:
    if os.name != "nt":
        raise SecureIOError(
            "Secure ancestor-pinned file operations require Windows."
        )


def _win_close(handle: int) -> None:
    if os.name == "nt":
        _CloseHandle(ctypes.c_void_p(handle))


def _win_handle_is_reparse(handle: int) -> bool:
    info = _FILE_ATTRIBUTE_TAG_INFO()
    if not _GetFileInformationByHandleEx(
        ctypes.c_void_p(handle),
        9,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        raise SecureIOError("Cannot inspect Windows file attributes.")
    return bool(info.FileAttributes & 0x00000400)


def _win_handle_identity(handle: int) -> tuple[int, bytes]:
    info = _FILE_ID_INFO()
    if not _GetFileInformationByHandleEx(
        ctypes.c_void_p(handle),
        18,
        ctypes.byref(info),
        ctypes.sizeof(info),
    ):
        raise SecureIOError("Cannot inspect Windows volume/file identity.")
    return int(info.VolumeSerialNumber), bytes(info.FileId.Identifier)


def _win_final_path(handle: int) -> str:
    buffer = ctypes.create_unicode_buffer(32768)
    length = _GetFinalPathNameByHandleW(
        ctypes.c_void_p(handle), buffer, len(buffer), 0
    )
    if not 0 < length < len(buffer):
        raise SecureIOError("Cannot resolve a held Windows file handle.")
    value = buffer.value
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return os.path.normcase(os.path.abspath(value))


def _win_open_handle(path: Path, *, directory: bool, read_data: bool) -> int:
    access = _GENERIC_READ if read_data else 0
    share = (
        _FILE_SHARE_READ
        if read_data
        else (_FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE)
    )
    flags = _FILE_FLAG_OPEN_REPARSE_POINT
    flags |= _FILE_FLAG_BACKUP_SEMANTICS if directory else _FILE_ATTRIBUTE_NORMAL
    if read_data:
        flags |= _FILE_FLAG_SEQUENTIAL_SCAN
    raw = _CreateFileW(str(path), access, share, None, _OPEN_EXISTING, flags, None)
    if raw in (None, _INVALID_HANDLE) and directory:
        # Some ordinary Windows profile directories deny OPEN_REPARSE_POINT
        # even for a zero-access metadata handle. The pathname was already
        # checked with lstat; the fallback handle is still bound to its final
        # path plus volume/file identity and the pathname is checked again
        # after the protected operation. Source-file leaves never use this
        # fallback.
        raw = _CreateFileW(
            str(path),
            access,
            share,
            None,
            _OPEN_EXISTING,
            flags & ~_FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
    if raw in (None, _INVALID_HANDLE):
        error_code = ctypes.get_last_error()
        raise SecureIOError(
            f"Cannot hold canonical path component: {path} "
            f"(Windows error {error_code})."
        )
    handle = int(raw)
    try:
        if _win_handle_is_reparse(handle):
            raise SecureIOError(f"Reparse path is forbidden: {path}")
        if _win_final_path(handle) != os.path.normcase(os.path.abspath(path)):
            raise SecureIOError(f"Windows handle escaped canonical path: {path}")
    except Exception:
        _win_close(handle)
        raise
    return handle


def _open_pinned_source(
    path: Path,
    canonical_root: Path,
) -> tuple[int, list[tuple[int, Path, tuple[int, bytes]]]]:
    held: list[tuple[int, Path, tuple[int, bytes]]] = []
    try:
        if os.name == "nt":
            components = _components_from_root(path, canonical_root)
            for component in components[:-1]:
                handle = _win_open_handle(
                    component, directory=True, read_data=False
                )
                held.append((handle, component, _win_handle_identity(handle)))
            leaf_handle = _win_open_handle(path, directory=False, read_data=True)
            try:
                descriptor = msvcrt.open_osfhandle(
                    leaf_handle, os.O_RDONLY | _BINARY_FLAG
                )
            except Exception:
                _win_close(leaf_handle)
                raise
            return descriptor, held
        descriptor = os.open(path, os.O_RDONLY | _BINARY_FLAG | _NOFOLLOW_FLAG)
        return descriptor, held
    except Exception:
        for handle, _component, _identity in reversed(held):
            _win_close(handle)
        raise


def _recheck_held_components(
    held: list[tuple[int, Path, tuple[int, bytes]]],
) -> None:
    if os.name != "nt":
        return
    for handle, component, identity in held:
        if _win_handle_is_reparse(handle):
            raise SecureIOError(f"Held component became reparse: {component}")
        if _win_final_path(handle) != os.path.normcase(os.path.abspath(component)):
            raise SecureIOError(f"Held component identity changed: {component}")
        if _win_handle_identity(handle) != identity:
            raise SecureIOError(
                f"Held component volume/file identity changed: {component}"
            )


def _close_held_components(
    held: list[tuple[int, Path, tuple[int, bytes]]],
) -> None:
    for handle, _component, _identity in reversed(held):
        _win_close(handle)


def _metadata(path_stat: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        int(path_stat.st_dev),
        int(path_stat.st_ino),
        int(path_stat.st_mode),
        int(path_stat.st_size),
        int(path_stat.st_mtime_ns),
        int(path_stat.st_ctime_ns),
    )


def _component_identity(path_stat: os.stat_result) -> tuple[int, int, int]:
    return (
        int(path_stat.st_dev),
        int(path_stat.st_ino),
        int(path_stat.st_mode),
    )


def _archive_identity(path_stat: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        int(path_stat.st_dev),
        int(path_stat.st_ino),
        int(path_stat.st_mode),
        int(path_stat.st_size),
        int(path_stat.st_mtime_ns),
    )


def _component_metadata(path: Path) -> tuple[tuple[Path, tuple[int, ...]], ...]:
    return tuple(
        (component, _component_identity(component.lstat()))
        for component in _path_components(path)
    )


def _recheck_component_metadata(
    baseline: tuple[tuple[Path, tuple[int, ...]], ...],
) -> None:
    for component, expected in baseline:
        current = component.lstat()
        if (
            _is_reparse_or_symlink(current)
            or _component_identity(current) != expected
        ):
            raise SecureIOError(
                f"Canonical path component identity changed: {component}"
            )


def _components_from_root(path: Path, canonical_root: Path) -> tuple[Path, ...]:
    absolute_path = lexical_absolute(path)
    absolute_root = lexical_absolute(canonical_root)
    if os.path.commonpath((str(absolute_path), str(absolute_root))) != str(
        absolute_root
    ):
        raise SecureIOError("Canonical path escaped its protected root.")
    components = _path_components(absolute_path)
    try:
        root_index = components.index(absolute_root)
    except ValueError as error:
        raise SecureIOError("Protected root is not a canonical path component.") from error
    return components[root_index:]


def _read_bounded(descriptor: int, maximum_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while total <= maximum_bytes:
        chunk = os.read(descriptor, min(1024 * 1024, maximum_bytes + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    data = b"".join(chunks)
    if len(data) > maximum_bytes:
        raise SecureIOError("File exceeds the bounded snapshot limit.")
    return data


@contextmanager
def held_verified_snapshot(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
    maximum_bytes: int,
    canonical_root: str | Path | None = None,
) -> Iterator[VerifiedSnapshot]:
    _require_windows_pinning()
    if type(maximum_bytes) is not int or maximum_bytes <= 0:
        raise ValueError("maximum_bytes must be a positive integer.")
    if expected_sha256 is not None and not _SHA256_PATTERN.fullmatch(
        expected_sha256
    ):
        raise ValueError("expected_sha256 must be lowercase SHA-256.")
    source = assert_plain_path(path)
    protected_root = assert_plain_path(
        canonical_root if canonical_root is not None else source.parent,
        leaf_must_be_directory=True,
    )
    component_baseline = _component_metadata(source)
    before_path = source.lstat()
    if not stat.S_ISREG(before_path.st_mode):
        raise SecureIOError("Snapshot source must be a regular file.")
    if before_path.st_size > maximum_bytes:
        raise SecureIOError("File exceeds the bounded snapshot limit.")

    descriptor = -1
    held: list[tuple[int, Path, tuple[int, bytes]]] = []
    try:
        descriptor, held = _open_pinned_source(source, protected_root)
        opened = os.fstat(descriptor)
        if not os.path.samestat(before_path, opened):
            raise SecureIOError("Source identity changed while opening snapshot.")
        if _metadata(before_path) != _metadata(opened):
            raise SecureIOError("Source metadata changed while opening snapshot.")
        data = _read_bounded(descriptor, maximum_bytes)
        after_descriptor = os.fstat(descriptor)
        _recheck_held_components(held)
        after_path = source.lstat()
        assert_plain_path(source)
        _recheck_component_metadata(component_baseline)
        if not (
            os.path.samestat(opened, after_descriptor)
            and os.path.samestat(opened, after_path)
            and _metadata(opened) == _metadata(after_descriptor)
            and _metadata(opened) == _metadata(after_path)
            and len(data) == opened.st_size
        ):
            raise SecureIOError("Source identity or metadata changed during snapshot.")
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise SecureIOError("Snapshot SHA-256 does not match the pinned value.")
        snapshot = VerifiedSnapshot(
            data=data,
            sha256=digest,
            size=len(data),
            identity=(int(opened.st_dev), int(opened.st_ino)),
            metadata=_metadata(opened),
        )
        yield snapshot
        after_consumer = os.fstat(descriptor)
        final_path = source.lstat()
        _recheck_held_components(held)
        assert_plain_path(source)
        _recheck_component_metadata(component_baseline)
        if not (
            os.path.samestat(opened, after_consumer)
            and os.path.samestat(opened, final_path)
            and _metadata(opened) == _metadata(after_consumer)
            and _metadata(opened) == _metadata(final_path)
        ):
            raise SecureIOError(
                "Source identity or metadata changed while snapshot was consumed."
            )
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        _close_held_components(held)


def read_verified_snapshot(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
    maximum_bytes: int,
    canonical_root: str | Path | None = None,
) -> VerifiedSnapshot:
    with held_verified_snapshot(
        path,
        expected_sha256=expected_sha256,
        maximum_bytes=maximum_bytes,
        canonical_root=canonical_root,
    ) as snapshot:
        return snapshot


def parse_verified_utf8_snapshot(
    snapshot_bytes: bytes,
    *,
    expected_sha256: str,
    snapshot_sha256: str,
    parser: Callable[[StringIO], _T],
) -> _T:
    if type(snapshot_bytes) is not bytes:
        raise SecureIOError("Database snapshot must be immutable bytes.")
    actual_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()
    if (
        not _SHA256_PATTERN.fullmatch(expected_sha256)
        or not _SHA256_PATTERN.fullmatch(snapshot_sha256)
        or actual_sha256 != expected_sha256
        or actual_sha256 != snapshot_sha256
    ):
        raise SecureIOError("Parser snapshot identity does not match its cache key.")
    encoding = "utf-8-sig" if snapshot_bytes.startswith(b"\xef\xbb\xbf") else "utf-8"
    try:
        text = snapshot_bytes.decode(encoding)
    except UnicodeDecodeError as error:
        raise SecureIOError("Database snapshot is not strict UTF-8 text.") from error
    if text.encode(encoding) != snapshot_bytes:
        raise SecureIOError("Database snapshot text round-trip changed bytes.")
    return parser(StringIO(text))


def ensure_plain_directory(path: str | Path) -> Path:
    destination = lexical_absolute(path)
    components = _path_components(destination)
    for component in components:
        try:
            component_stat = component.lstat()
        except FileNotFoundError:
            try:
                component.mkdir()
            except FileExistsError:
                pass
            component_stat = component.lstat()
        if _is_reparse_or_symlink(component_stat) or not stat.S_ISDIR(
            component_stat.st_mode
        ):
            raise SecureIOError(f"Workspace directory is not plain: {component}")
    return assert_plain_path(destination, leaf_must_be_directory=True)


@contextmanager
def hold_plain_directory(
    path: str | Path,
    *,
    canonical_root: str | Path | None = None,
) -> Iterator[Path]:
    _require_windows_pinning()
    directory = assert_plain_path(path, leaf_must_be_directory=True)
    protected_root = assert_plain_path(
        canonical_root if canonical_root is not None else directory,
        leaf_must_be_directory=True,
    )
    component_baseline = _component_metadata(directory)
    held: list[tuple[int, Path, tuple[int, bytes]]] = []
    try:
        if os.name == "nt":
            for component in _components_from_root(directory, protected_root):
                handle = _win_open_handle(
                    component, directory=True, read_data=False
                )
                held.append((handle, component, _win_handle_identity(handle)))
        yield directory
        _recheck_held_components(held)
        assert_plain_path(directory, leaf_must_be_directory=True)
        _recheck_component_metadata(component_baseline)
    finally:
        _close_held_components(held)


@contextmanager
def exclusive_writer(
    path: str | Path,
    *,
    canonical_root: str | Path | None = None,
) -> Iterator[Path]:
    _require_windows_pinning()
    destination = lexical_absolute(path)
    with hold_plain_directory(
        destination.parent,
        canonical_root=canonical_root,
    ) as parent:
        if os.path.commonpath((str(parent), str(destination))) != str(parent):
            raise SecureIOError("Workspace destination escaped its parent.")
        assert_plain_path(destination, leaf_may_be_missing=True)
        lock_path = destination.with_name(destination.name + ".thermogar.lock")
        assert_plain_path(lock_path, leaf_may_be_missing=True)
        try:
            lock_descriptor = os.open(
                lock_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _BINARY_FLAG,
                0o600,
            )
        except FileExistsError as error:
            raise SecureIOError(
                "Workspace writer is already active or requires recovery: "
                f"{lock_path.name}"
            ) from error
        lock_identity = os.fstat(lock_descriptor)
        try:
            os.write(lock_descriptor, f"pid={os.getpid()}\n".encode("ascii"))
            os.fsync(lock_descriptor)
            yield destination
        finally:
            os.close(lock_descriptor)
            try:
                current_lock = lock_path.lstat()
                if _is_reparse_or_symlink(current_lock) or not os.path.samestat(
                    lock_identity, current_lock
                ):
                    raise SecureIOError("Workspace writer lock identity changed.")
                lock_path.unlink()
            except FileNotFoundError as error:
                raise SecureIOError("Workspace writer lock disappeared.") from error


def _atomic_replace_locked(
    destination: Path,
    data: bytes,
    *,
    allow_overwrite: bool = True,
) -> None:
    if type(data) is not bytes or len(data) > MAX_WORKSPACE_FILE_BYTES:
        raise SecureIOError("Workspace payload is not bounded immutable bytes.")
    parent = assert_plain_path(destination.parent, leaf_must_be_directory=True)
    assert_plain_path(destination, leaf_may_be_missing=True)
    temporary = parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
    if os.path.commonpath((str(parent), str(temporary))) != str(parent):
        raise SecureIOError("Temporary file escaped destination parent.")
    assert_plain_path(temporary, leaf_may_be_missing=True)
    descriptor = -1
    temporary_identity: os.stat_result | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _BINARY_FLAG,
            0o600,
        )
        opened = os.fstat(descriptor)
        offset = 0
        while offset < len(data):
            written = os.write(descriptor, data[offset:])
            if written <= 0:
                raise SecureIOError("Short workspace write.")
            offset += written
        os.fsync(descriptor)
        finished = os.fstat(descriptor)
        if not os.path.samestat(opened, finished) or finished.st_size != len(data):
            raise SecureIOError("Temporary file identity changed during write.")
        temporary_identity = finished
        os.close(descriptor)
        descriptor = -1
        temporary_path_stat = temporary.lstat()
        if (
            _is_reparse_or_symlink(temporary_path_stat)
            or not stat.S_ISREG(temporary_path_stat.st_mode)
            or not os.path.samestat(temporary_identity, temporary_path_stat)
        ):
            raise SecureIOError("Temporary sibling identity changed before replace.")
        assert_plain_path(destination, leaf_may_be_missing=True)
        if not allow_overwrite:
            try:
                destination.lstat()
            except FileNotFoundError:
                pass
            else:
                raise SecureIOError("Archive destination already exists.")
        assert_plain_path(parent, leaf_must_be_directory=True)
        if allow_overwrite:
            os.replace(temporary, destination)
        else:
            # Windows os.rename is a no-overwrite transition. Non-Windows
            # callers are rejected by the held parent context.
            os.rename(temporary, destination)
        destination_stat = destination.lstat()
        if (
            _is_reparse_or_symlink(destination_stat)
            or not stat.S_ISREG(destination_stat.st_mode)
            or not os.path.samestat(temporary_identity, destination_stat)
        ):
            raise SecureIOError("Destination identity changed across atomic replace.")
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            remaining = temporary.lstat()
        except FileNotFoundError:
            remaining = None
        if (
            remaining is not None
            and temporary_identity is not None
            and os.path.samestat(temporary_identity, remaining)
        ):
            temporary.unlink()


def _before_atomic_write_decision(destination: Path) -> None:
    """Deterministic concurrent-creator test seam; production is a no-op."""

    del destination


def atomic_write_bytes(
    path: str | Path,
    data: bytes,
    *,
    create_backup: bool = False,
    overwrite: bool = True,
    canonical_root: str | Path | None = None,
) -> None:
    with exclusive_writer(path, canonical_root=canonical_root) as destination:
        _before_atomic_write_decision(destination)
        try:
            destination_stat = destination.lstat()
        except FileNotFoundError:
            destination_exists = False
        else:
            destination_exists = True
            if (
                _is_reparse_or_symlink(destination_stat)
                or not stat.S_ISREG(destination_stat.st_mode)
            ):
                raise SecureIOError(
                    "Workspace destination is not a plain regular file."
                )
        if destination_exists and not overwrite:
            raise FileExistsError(
                "Workspace destination appeared before create-only commit: "
                f"{destination}"
            )
        if create_backup and destination_exists:
            previous = read_verified_snapshot(
                destination,
                maximum_bytes=MAX_WORKSPACE_FILE_BYTES,
                canonical_root=canonical_root,
            )
            backup = destination.with_suffix(destination.suffix + ".bak")
            atomic_write_bytes(
                backup,
                previous.data,
                create_backup=False,
                overwrite=True,
                canonical_root=canonical_root,
            )
            verified_backup = read_verified_snapshot(
                backup,
                expected_sha256=previous.sha256,
                maximum_bytes=MAX_WORKSPACE_FILE_BYTES,
                canonical_root=canonical_root,
            )
            if verified_backup.data != previous.data:
                raise SecureIOError("Workspace backup changed verified bytes.")
            current_destination = destination.lstat()
            if (
                _is_reparse_or_symlink(current_destination)
                or not stat.S_ISREG(current_destination.st_mode)
                or _metadata(current_destination) != previous.metadata
            ):
                raise SecureIOError(
                    "Workspace destination identity changed after backup."
                )
        _atomic_replace_locked(
            destination,
            data,
            # A destination absent at the locked decision is always committed
            # create-only, including overwrite=True. A racing creator is never
            # overwritten without first becoming a verified backup candidate.
            allow_overwrite=destination_exists,
        )


def atomic_update_bytes(
    path: str | Path,
    update: Callable[[bytes], bytes],
    *,
    create_backup: bool = False,
    maximum_bytes: int = MAX_WORKSPACE_FILE_BYTES,
    canonical_root: str | Path | None = None,
) -> None:
    with exclusive_writer(path, canonical_root=canonical_root) as destination:
        _before_atomic_update_decision(destination)
        try:
            destination.lstat()
        except FileNotFoundError:
            destination_exists = False
        else:
            destination_exists = True
        if destination_exists:
            previous = read_verified_snapshot(
                destination,
                maximum_bytes=maximum_bytes,
                canonical_root=canonical_root,
            )
            current = previous.data
        else:
            previous = None
            current = b""
        replacement = update(current)
        if type(replacement) is not bytes:
            raise SecureIOError("Workspace updater must return immutable bytes.")
        if len(replacement) > maximum_bytes:
            raise SecureIOError("Workspace updater exceeded its bounded size.")
        if create_backup and previous is not None:
            backup = destination.with_suffix(destination.suffix + ".bak")
            atomic_write_bytes(
                backup,
                previous.data,
                create_backup=False,
                overwrite=True,
                canonical_root=canonical_root,
            )
            verified_backup = read_verified_snapshot(
                backup,
                expected_sha256=previous.sha256,
                maximum_bytes=maximum_bytes,
                canonical_root=canonical_root,
            )
            if verified_backup.data != previous.data:
                raise SecureIOError("Workspace update backup changed verified bytes.")
            current_destination = destination.lstat()
            if (
                _is_reparse_or_symlink(current_destination)
                or not stat.S_ISREG(current_destination.st_mode)
                or _metadata(current_destination) != previous.metadata
            ):
                raise SecureIOError(
                    "Workspace update destination changed after backup."
                )
        _atomic_replace_locked(
            destination,
            replacement,
            allow_overwrite=destination_exists,
        )


def _before_atomic_update_decision(destination: Path) -> None:
    """Deterministic read-modify-write race seam; production is a no-op."""

    del destination


def _rename_no_overwrite(source: Path, destination: Path) -> None:
    # Windows os.rename refuses an existing destination. Non-Windows callers
    # are rejected before this test hook is reached.
    os.rename(source, destination)


def _before_secure_transition(
    operation: str,
    source: Path,
    destination: Path,
) -> None:
    """Deterministic race-injection seam; production behavior is a no-op."""

    del operation, source, destination


def secure_move_no_overwrite(
    source_path: str | Path,
    destination_path: str | Path,
    *,
    canonical_root: str | Path,
) -> Path:
    """Move one verified regular file to a recoverable sibling/archive path."""

    _require_windows_pinning()
    root = assert_plain_path(canonical_root, leaf_must_be_directory=True)
    source = lexical_absolute(source_path)
    destination = lexical_absolute(destination_path)
    for candidate in (source, destination):
        if os.path.commonpath((str(root), str(candidate))) != str(root):
            raise SecureIOError("Archive path escaped the canonical root.")
    if source == destination:
        raise SecureIOError("Archive source and destination must differ.")
    assert_plain_path(source)
    assert_plain_path(destination, leaf_may_be_missing=True)

    with exclusive_writer(source, canonical_root=root):
        with exclusive_writer(destination, canonical_root=root):
            try:
                destination.lstat()
            except FileNotFoundError:
                pass
            else:
                raise SecureIOError("Archive destination already exists.")
            with held_verified_snapshot(
                source,
                maximum_bytes=MAX_WORKSPACE_FILE_BYTES,
                canonical_root=root,
            ) as snapshot:
                source_metadata = snapshot.metadata
                source_archive_identity = _archive_identity(source.lstat())
            _before_secure_transition("move", source, destination)
            current_source = source.lstat()
            if (
                _is_reparse_or_symlink(current_source)
                or not stat.S_ISREG(current_source.st_mode)
                or _metadata(current_source) != source_metadata
            ):
                raise SecureIOError("Archive source identity changed before move.")
            _rename_no_overwrite(source, destination)
            try:
                moved = destination.lstat()
                if (
                    _is_reparse_or_symlink(moved)
                    or not stat.S_ISREG(moved.st_mode)
                    or _archive_identity(moved) != source_archive_identity
                ):
                    raise SecureIOError("Archive identity changed across move.")
                try:
                    source.lstat()
                except FileNotFoundError:
                    pass
                else:
                    raise SecureIOError("Archive source remained after move.")
            except Exception:
                try:
                    rollback = destination.lstat()
                except FileNotFoundError:
                    rollback = None
                try:
                    source.lstat()
                except FileNotFoundError:
                    source_missing = True
                else:
                    source_missing = False
                if (
                    rollback is not None
                    and _archive_identity(rollback) == source_archive_identity
                    and source_missing
                ):
                    _rename_no_overwrite(destination, source)
                raise
    return destination


def secure_archive_and_clear(
    source_path: str | Path,
    backup_path: str | Path,
    *,
    canonical_root: str | Path,
    missing_ok: bool = False,
) -> bool:
    """Copy exact verified bytes to a new backup, then atomically empty source."""

    _require_windows_pinning()
    root = assert_plain_path(canonical_root, leaf_must_be_directory=True)
    source = lexical_absolute(source_path)
    backup = lexical_absolute(backup_path)
    for candidate in (source, backup):
        if os.path.commonpath((str(root), str(candidate))) != str(root):
            raise SecureIOError("History archive path escaped the canonical root.")
    if source == backup:
        raise SecureIOError("History source and backup must differ.")
    assert_plain_path(source, leaf_may_be_missing=missing_ok)
    assert_plain_path(backup, leaf_may_be_missing=True)

    with exclusive_writer(source, canonical_root=root):
        try:
            source.lstat()
        except FileNotFoundError:
            if missing_ok:
                return False
            raise SecureIOError("History source is missing.") from None
        with exclusive_writer(backup, canonical_root=root):
            try:
                backup.lstat()
            except FileNotFoundError:
                pass
            else:
                raise SecureIOError("History backup already exists.")
            with held_verified_snapshot(
                source,
                maximum_bytes=MAX_WORKSPACE_FILE_BYTES,
                canonical_root=root,
            ) as snapshot:
                _atomic_replace_locked(
                    backup,
                    snapshot.data,
                    allow_overwrite=False,
                )
                verified_backup = read_verified_snapshot(
                    backup,
                    expected_sha256=snapshot.sha256,
                    maximum_bytes=MAX_WORKSPACE_FILE_BYTES,
                    canonical_root=root,
                )
                if verified_backup.data != snapshot.data:
                    raise SecureIOError("History backup changed verified bytes.")
            _before_secure_transition("archive", source, backup)
            with held_verified_snapshot(
                backup,
                expected_sha256=snapshot.sha256,
                maximum_bytes=MAX_WORKSPACE_FILE_BYTES,
                canonical_root=root,
            ) as pinned_backup:
                if pinned_backup.data != snapshot.data:
                    raise SecureIOError("History backup changed before clear.")
                current_source = source.lstat()
                if (
                    _is_reparse_or_symlink(current_source)
                    or not stat.S_ISREG(current_source.st_mode)
                    or _metadata(current_source) != snapshot.metadata
                ):
                    raise SecureIOError(
                        "History source identity changed before clear."
                    )
                _atomic_replace_locked(source, b"", allow_overwrite=True)
            cleared = read_verified_snapshot(
                source,
                expected_sha256=hashlib.sha256(b"").hexdigest(),
                maximum_bytes=1,
                canonical_root=root,
            )
            if cleared.data != b"":
                raise SecureIOError("History source was not atomically cleared.")
    return True
