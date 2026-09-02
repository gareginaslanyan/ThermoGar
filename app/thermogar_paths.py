"""Canonical mutable-state paths and verified copy-only legacy migration.

This module is deliberately standard-library only so the unified application can
establish its process environment before importing Matplotlib, Streamlit, or any
scientific package.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any


MIGRATION_SCHEMA_VERSION = 1
MAX_MIGRATION_FILES = 256
MAX_MIGRATION_FILE_BYTES = 16 * 1024 * 1024
MAX_MIGRATION_TOTAL_BYTES = 64 * 1024 * 1024
MIGRATION_RECEIPT_NAME = "migration_receipt.json"

_REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)
_HISTORY_BACKUP = re.compile(r"history_[0-9A-Za-z_-]+\.jsonl\.bak\Z")
_PROJECT_ARTIFACT = re.compile(
    r".+\.thermogar\.json(?:\.bak|\.deleted)?\Z",
)


class ThermoGarPathError(RuntimeError):
    """A path or migration boundary could not be proven safe."""


class LegacyMigrationConflict(ThermoGarPathError):
    """A legacy source differs from an already present profile destination."""

    def __init__(self, receipt: dict[str, Any]) -> None:
        self.receipt = receipt
        super().__init__("Legacy state migration stopped on a digest conflict.")


class _MigrationEnumerationOverflow(ThermoGarPathError):
    """Bounded legacy enumeration observed more entries than permitted."""

    def __init__(
        self,
        *,
        directory_relative: str,
        destination_relative: str,
        directory_observations: int,
        global_observations: int,
    ) -> None:
        self.directory_relative = directory_relative
        self.destination_relative = destination_relative
        self.directory_observations = directory_observations
        self.global_observations = global_observations
        observed_at_least = max(directory_observations, global_observations)
        super().__init__(
            f"MAX_MIGRATION_FILES={MAX_MIGRATION_FILES}; "
            f"observed_at_least={observed_at_least}; "
            "no_copy_attempted=true; "
            f"directory={directory_relative}; "
            f"directory_observations={directory_observations}; "
            f"global_observations={global_observations}."
        )


def _absolute_path(value: str | os.PathLike[str], *, label: str) -> Path:
    raw = os.fspath(value)
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        raise ThermoGarPathError(f"{label} must be a non-empty filesystem path.")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise ThermoGarPathError(f"{label} must be absolute.")
    if ".." in candidate.parts:
        raise ThermoGarPathError(f"{label} must not contain parent traversal.")
    return Path(os.path.abspath(os.path.normpath(str(candidate))))


def _is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE
    )


def _assert_contained(path: Path, root: Path, *, label: str) -> None:
    try:
        common = os.path.commonpath((str(path), str(root)))
    except ValueError as error:
        raise ThermoGarPathError(f"{label} is outside its canonical root.") from error
    if os.path.normcase(common) != os.path.normcase(str(root)):
        raise ThermoGarPathError(f"{label} is outside its canonical root.")


def _assert_plain_existing_chain(
    path: Path,
    *,
    canonical_root: Path | None,
    final_kind: str | None,
) -> None:
    if canonical_root is not None:
        _assert_contained(path, canonical_root, label=str(path))
    components = list(reversed((path, *path.parents)))
    for component in components:
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if _is_reparse(info):
            raise ThermoGarPathError(f"Reparse path component rejected: {component}")
        if component != path and not stat.S_ISDIR(info.st_mode):
            raise ThermoGarPathError(f"Non-directory path component rejected: {component}")
    try:
        final_info = path.lstat()
    except FileNotFoundError:
        return
    if final_kind == "directory" and not stat.S_ISDIR(final_info.st_mode):
        raise ThermoGarPathError(f"Directory required: {path}")
    if final_kind == "file" and not stat.S_ISREG(final_info.st_mode):
        raise ThermoGarPathError(f"Regular file required: {path}")


def _ensure_plain_directory(path: Path, *, canonical_root: Path | None = None) -> Path:
    if canonical_root is not None:
        _assert_contained(path, canonical_root, label=str(path))
    missing: list[Path] = []
    cursor = path
    while True:
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            missing.append(cursor)
            parent = cursor.parent
            if parent == cursor:
                raise ThermoGarPathError(f"No existing ancestor for {path}")
            cursor = parent
            continue
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise ThermoGarPathError(f"Plain directory chain required: {cursor}")
        break
    for component in reversed(missing):
        try:
            component.mkdir()
        except FileExistsError:
            pass
        info = component.lstat()
        if _is_reparse(info) or not stat.S_ISDIR(info.st_mode):
            raise ThermoGarPathError(f"Plain directory creation failed: {component}")
    _assert_plain_existing_chain(
        path,
        canonical_root=canonical_root,
        final_kind="directory",
    )
    return path


@dataclass(frozen=True, slots=True, init=False)
class ThermoGarPaths:
    """Immutable location-only authority for all canonical mutable state."""

    state_root: Path
    workspace_root: Path
    alloys_path: Path
    history_path: Path
    projects_root: Path
    elastic_properties_path: Path
    stage14_errors_path: Path
    matplotlib_root: Path
    temp_root: Path

    def __init__(self, state_root: str | os.PathLike[str] | None = None) -> None:
        selected: str | os.PathLike[str]
        if state_root is not None:
            selected = state_root
        else:
            explicit = os.environ.get("THERMOGAR_STATE_ROOT")
            if explicit:
                selected = explicit
            else:
                local_app_data = os.environ.get("LOCALAPPDATA")
                if not local_app_data:
                    raise ThermoGarPathError(
                        "LOCALAPPDATA or an explicit THERMOGAR_STATE_ROOT is required."
                    )
                selected = Path(local_app_data) / "ThermoGar"

        root = _absolute_path(selected, label="ThermoGar state root")
        values = {
            "state_root": root,
            "workspace_root": root / "workspace",
            "alloys_path": root / "workspace" / "alloys.json",
            "history_path": root / "workspace" / "history.jsonl",
            "projects_root": root / "workspace" / "projects",
            "elastic_properties_path": (
                root / "properties" / "elastic_phase_properties.json"
            ),
            "stage14_errors_path": root / "logs" / "stage14" / "errors.jsonl",
            "matplotlib_root": root / "runtime" / "matplotlib",
            "temp_root": root / "runtime" / "tmp",
        }
        for field_name, value in values.items():
            object.__setattr__(self, field_name, value)

    def configure_process_environment(self) -> None:
        """Create the fixed layout and set process paths before heavy imports."""

        _ensure_plain_directory(self.state_root)
        for directory in (
            self.workspace_root,
            self.projects_root,
            self.elastic_properties_path.parent,
            self.stage14_errors_path.parent,
            self.matplotlib_root,
            self.temp_root,
        ):
            _ensure_plain_directory(directory, canonical_root=self.state_root)
        expected = {
            "THERMOGAR_STATE_ROOT": self.state_root,
            "MPLCONFIGDIR": self.matplotlib_root,
            "TMP": self.temp_root,
            "TEMP": self.temp_root,
        }
        for name, value in expected.items():
            os.environ[name] = str(value)


@dataclass(frozen=True, slots=True)
class _Snapshot:
    data: bytes
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _Candidate:
    source: Path
    source_relative: str
    destination: Path
    destination_relative: str


@dataclass(slots=True)
class _EnumerationBudget:
    global_observations: int = 0

    def observe(
        self,
        *,
        directory_relative: str,
        destination_relative: str,
        directory_observations: int,
    ) -> None:
        self.global_observations += 1
        if (
            directory_observations > MAX_MIGRATION_FILES
            or self.global_observations > MAX_MIGRATION_FILES
        ):
            raise _MigrationEnumerationOverflow(
                directory_relative=directory_relative,
                destination_relative=destination_relative,
                directory_observations=directory_observations,
                global_observations=self.global_observations,
            )


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_size),
        int(info.st_mtime_ns),
        int(info.st_ctime_ns),
    )


def _read_held_snapshot(
    path: Path,
    *,
    canonical_root: Path,
    maximum_bytes: int,
) -> _Snapshot:
    _assert_plain_existing_chain(
        path,
        canonical_root=canonical_root,
        final_kind="file",
    )
    before = path.lstat()
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if _is_reparse(opened) or not stat.S_ISREG(opened.st_mode):
            raise ThermoGarPathError(f"Regular non-reparse file required: {path}")
        if _identity(opened) != _identity(before):
            raise ThermoGarPathError(f"File identity changed before read: {path}")
        if opened.st_size > maximum_bytes:
            raise ThermoGarPathError(f"File exceeds the bounded snapshot limit: {path}")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining:
            block = os.read(descriptor, min(1024 * 1024, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        data = b"".join(chunks)
        after = os.fstat(descriptor)
        if len(data) > maximum_bytes or len(data) != int(opened.st_size):
            raise ThermoGarPathError(f"File size changed during read: {path}")
        if _identity(after) != _identity(opened):
            raise ThermoGarPathError(f"File metadata changed during read: {path}")
    finally:
        os.close(descriptor)
    final = path.lstat()
    if _identity(final) != _identity(before) or _is_reparse(final):
        raise ThermoGarPathError(f"File identity changed after read: {path}")
    return _Snapshot(data, len(data), hashlib.sha256(data).hexdigest())


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = os.write(descriptor, view[offset:])
        if written <= 0:
            raise ThermoGarPathError("Short write while creating profile state.")
        offset += written
    os.fsync(descriptor)


def _profile_temp(destination: Path) -> Path:
    return destination.with_name(
        f".{destination.name}.migration-{secrets.token_hex(12)}.tmp"
    )


def _atomic_copy_no_overwrite(
    destination: Path,
    data: bytes,
    *,
    canonical_root: Path,
) -> bool:
    _assert_contained(destination, canonical_root, label="migration destination")
    _ensure_plain_directory(destination.parent, canonical_root=canonical_root)
    _assert_plain_existing_chain(
        destination,
        canonical_root=canonical_root,
        final_kind=None,
    )
    temp = _profile_temp(destination)
    descriptor = os.open(
        temp,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
        0o600,
    )
    try:
        _write_all(descriptor, data)
    finally:
        os.close(descriptor)
    try:
        os.link(temp, destination)
        return True
    except FileExistsError:
        return False
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _atomic_write_receipt(paths: ThermoGarPaths, payload: dict[str, Any]) -> None:
    destination = paths.state_root / MIGRATION_RECEIPT_NAME
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    _assert_contained(destination, paths.state_root, label="migration receipt")
    _ensure_plain_directory(destination.parent, canonical_root=paths.state_root)
    try:
        destination.lstat()
    except FileNotFoundError:
        pass
    else:
        _assert_plain_existing_chain(
            destination,
            canonical_root=paths.state_root,
            final_kind="file",
        )
    temp = _profile_temp(destination)
    descriptor = os.open(
        temp,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
        0o600,
    )
    try:
        _write_all(descriptor, encoded)
    finally:
        os.close(descriptor)
    try:
        os.replace(temp, destination)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _record(
    source_relative: str,
    destination_relative: str,
    *,
    size: int = 0,
    source_sha256: str = "",
    destination_sha256: str = "",
    disposition: str,
    failure_detail: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": MIGRATION_SCHEMA_VERSION,
        "source_relative_path": source_relative,
        "destination_relative_path": destination_relative,
        "size": int(size),
        "source_sha256": source_sha256,
        "destination_sha256": destination_sha256,
        "disposition": disposition,
        "failure_detail": failure_detail,
    }


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _write_rejected_overflow_receipt(
    paths: ThermoGarPaths,
    *,
    source_relative: str,
    destination_relative: str,
    observed_at_least: int,
) -> dict[str, Any]:
    bounded_observation = max(MAX_MIGRATION_FILES + 1, int(observed_at_least))
    failure_detail = (
        f"MAX_MIGRATION_FILES={MAX_MIGRATION_FILES}; "
        f"observed_at_least={bounded_observation}; "
        "no_copy_attempted=true"
    )
    receipt = {
        "schema_version": MIGRATION_SCHEMA_VERSION,
        "outcome": "rejected_overflow",
        "records": [
            _record(
                source_relative,
                destination_relative,
                disposition="rejected",
                failure_detail=failure_detail,
            )
        ],
    }
    _atomic_write_receipt(paths, receipt)
    return receipt


def _directory_entries(
    directory: Path,
    *,
    install_root: Path,
    destination_relative: str,
    records: list[dict[str, Any]],
    budget: _EnumerationBudget,
) -> list[Path]:
    try:
        directory.lstat()
    except FileNotFoundError:
        return []
    try:
        _assert_plain_existing_chain(
            directory,
            canonical_root=install_root,
            final_kind="directory",
        )
    except Exception as error:
        records.append(
            _record(
                _relative(directory, install_root),
                destination_relative,
                disposition="rejected",
                failure_detail=f"{type(error).__name__}: {error}",
            )
        )
        return []
    directory_relative = _relative(directory, install_root)
    entries: list[Path] = []
    directory_observations = 0
    try:
        with os.scandir(directory) as iterator:
            for entry in iterator:
                directory_observations += 1
                budget.observe(
                    directory_relative=directory_relative,
                    destination_relative=destination_relative,
                    directory_observations=directory_observations,
                )
                entries.append(Path(entry.path))
    except _MigrationEnumerationOverflow:
        raise
    except Exception as error:
        records.append(
            _record(
                directory_relative,
                destination_relative,
                disposition="rejected",
                failure_detail=f"{type(error).__name__}: {error}",
            )
        )
        return []
    entries.sort(key=lambda item: item.name)
    return entries


def _legacy_candidates(
    paths: ThermoGarPaths,
    install_root: Path,
) -> tuple[list[_Candidate], list[dict[str, Any]]]:
    user_data = install_root / "user_data"
    candidates: list[_Candidate] = []
    records: list[dict[str, Any]] = []
    budget = _EnumerationBudget()
    root_entries = _directory_entries(
        user_data,
        install_root=install_root,
        destination_relative="",
        records=records,
        budget=budget,
    )
    if not root_entries:
        return candidates, records

    fixed_root = {
        "alloys.json": (paths.alloys_path, "workspace/alloys.json"),
        "alloys.json.bak": (
            paths.alloys_path.with_name("alloys.json.bak"),
            "workspace/alloys.json.bak",
        ),
        "history.jsonl": (paths.history_path, "workspace/history.jsonl"),
    }
    known_directories = {"projects", "properties", "logs"}
    for entry in root_entries:
        if entry.name in fixed_root:
            destination, destination_relative = fixed_root[entry.name]
            candidates.append(
                _Candidate(
                    entry,
                    _relative(entry, install_root),
                    destination,
                    destination_relative,
                )
            )
        elif _HISTORY_BACKUP.fullmatch(entry.name):
            candidates.append(
                _Candidate(
                    entry,
                    _relative(entry, install_root),
                    paths.workspace_root / entry.name,
                    f"workspace/{entry.name}",
                )
            )
        elif entry.name not in known_directories:
            records.append(
                _record(
                    _relative(entry, install_root),
                    "",
                    disposition="rejected",
                    failure_detail="not in the finite legacy allowlist",
                )
            )

    projects = user_data / "projects"
    for entry in _directory_entries(
        projects,
        install_root=install_root,
        destination_relative="workspace/projects",
        records=records,
        budget=budget,
    ):
        if _PROJECT_ARTIFACT.fullmatch(entry.name):
            candidates.append(
                _Candidate(
                    entry,
                    _relative(entry, install_root),
                    paths.projects_root / entry.name,
                    f"workspace/projects/{entry.name}",
                )
            )
        else:
            records.append(
                _record(
                    _relative(entry, install_root),
                    "",
                    disposition="rejected",
                    failure_detail="not in the finite project allowlist",
                )
            )

    properties = user_data / "properties"
    property_names = {
        "elastic_phase_properties.json",
        "elastic_phase_properties.json.bak",
    }
    for entry in _directory_entries(
        properties,
        install_root=install_root,
        destination_relative="properties",
        records=records,
        budget=budget,
    ):
        if entry.name in property_names:
            candidates.append(
                _Candidate(
                    entry,
                    _relative(entry, install_root),
                    paths.elastic_properties_path.with_name(entry.name),
                    f"properties/{entry.name}",
                )
            )
        else:
            records.append(
                _record(
                    _relative(entry, install_root),
                    "",
                    disposition="rejected",
                    failure_detail="not in the finite properties allowlist",
                )
            )

    logs = user_data / "logs"
    for entry in _directory_entries(
        logs,
        install_root=install_root,
        destination_relative="logs/stage14",
        records=records,
        budget=budget,
    ):
        if entry.name == "errors.jsonl":
            candidates.append(
                _Candidate(
                    entry,
                    _relative(entry, install_root),
                    paths.stage14_errors_path,
                    "logs/stage14/errors.jsonl",
                )
            )
        else:
            records.append(
                _record(
                    _relative(entry, install_root),
                    "",
                    disposition="rejected",
                    failure_detail="not in the finite logs allowlist",
                )
            )

    candidates.sort(key=lambda item: item.source_relative)
    records.sort(key=lambda item: item["source_relative_path"])
    return candidates, records


def migrate_legacy_state(
    paths: ThermoGarPaths,
    install_root: str | os.PathLike[str],
) -> dict[str, Any]:
    """Copy the finite legacy allowlist once without mutating either source."""

    if not isinstance(paths, ThermoGarPaths):
        raise TypeError("paths must be a ThermoGarPaths instance")
    root = _absolute_path(install_root, label="legacy install root")
    _assert_plain_existing_chain(root, canonical_root=None, final_kind="directory")
    try:
        candidates, records = _legacy_candidates(paths, root)
    except _MigrationEnumerationOverflow as error:
        _write_rejected_overflow_receipt(
            paths,
            source_relative=error.directory_relative,
            destination_relative=error.destination_relative,
            observed_at_least=max(
                error.directory_observations,
                error.global_observations,
            ),
        )
        raise

    total = 0
    conflict = False
    for candidate in candidates:
        try:
            source = _read_held_snapshot(
                candidate.source,
                canonical_root=root,
                maximum_bytes=MAX_MIGRATION_FILE_BYTES,
            )
            total += source.size
            if total > MAX_MIGRATION_TOTAL_BYTES:
                raise ThermoGarPathError("Legacy snapshot total exceeds the bounded limit.")
        except Exception as error:
            records.append(
                _record(
                    candidate.source_relative,
                    candidate.destination_relative,
                    disposition="rejected",
                    failure_detail=f"{type(error).__name__}: {error}",
                )
            )
            continue

        try:
            candidate.destination.lstat()
        except FileNotFoundError:
            try:
                copied = _atomic_copy_no_overwrite(
                    candidate.destination,
                    source.data,
                    canonical_root=paths.state_root,
                )
            except Exception as error:
                records.append(
                    _record(
                        candidate.source_relative,
                        candidate.destination_relative,
                        size=source.size,
                        source_sha256=source.sha256,
                        disposition="rejected",
                        failure_detail=f"{type(error).__name__}: {error}",
                    )
                )
                continue
            if copied:
                destination = _read_held_snapshot(
                    candidate.destination,
                    canonical_root=paths.state_root,
                    maximum_bytes=MAX_MIGRATION_FILE_BYTES,
                )
                if destination.sha256 != source.sha256:
                    raise ThermoGarPathError(
                        f"Copied destination digest mismatch: {candidate.destination}"
                    )
                records.append(
                    _record(
                        candidate.source_relative,
                        candidate.destination_relative,
                        size=source.size,
                        source_sha256=source.sha256,
                        destination_sha256=destination.sha256,
                        disposition="copied",
                    )
                )
                continue

        try:
            destination = _read_held_snapshot(
                candidate.destination,
                canonical_root=paths.state_root,
                maximum_bytes=MAX_MIGRATION_FILE_BYTES,
            )
        except Exception as error:
            records.append(
                _record(
                    candidate.source_relative,
                    candidate.destination_relative,
                    size=source.size,
                    source_sha256=source.sha256,
                    disposition="rejected",
                    failure_detail=f"{type(error).__name__}: {error}",
                )
            )
            continue
        if destination.sha256 == source.sha256:
            records.append(
                _record(
                    candidate.source_relative,
                    candidate.destination_relative,
                    size=source.size,
                    source_sha256=source.sha256,
                    destination_sha256=destination.sha256,
                    disposition="skipped_same_digest",
                )
            )
            continue
        records.append(
            _record(
                candidate.source_relative,
                candidate.destination_relative,
                size=source.size,
                source_sha256=source.sha256,
                destination_sha256=destination.sha256,
                disposition="conflict",
                failure_detail="existing destination has a different SHA-256",
            )
        )
        conflict = True
        break

    records.sort(key=lambda item: item["source_relative_path"])
    receipt = {
        "schema_version": MIGRATION_SCHEMA_VERSION,
        "outcome": "conflict" if conflict else "completed",
        "records": records,
    }
    _atomic_write_receipt(paths, receipt)
    if conflict:
        raise LegacyMigrationConflict(receipt)
    return receipt
