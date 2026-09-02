from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

import thermogar_paths as paths_module
from thermogar_paths import (
    LegacyMigrationConflict,
    MAX_MIGRATION_FILES,
    MIGRATION_RECEIPT_NAME,
    ThermoGarPathError,
    ThermoGarPaths,
    migrate_legacy_state,
)


def tree_manifest(root: Path) -> tuple[tuple[str, int, int, int, str], ...]:
    rows: list[tuple[str, int, int, int, str]] = []
    if not root.exists():
        return ()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        info = path.lstat()
        digest = ""
        if stat.S_ISREG(info.st_mode):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(
            (
                path.relative_to(root).as_posix(),
                int(info.st_mode),
                int(info.st_size),
                int(info.st_mtime_ns),
                digest,
            )
        )
    return tuple(rows)


def seed_allowlist(install: Path) -> dict[str, bytes]:
    payloads = {
        "user_data/alloys.json": b'{"alloys":[]}\n',
        "user_data/alloys.json.bak": b'{"alloys":["backup"]}\n',
        "user_data/history.jsonl": b'{"event":"one"}\n',
        "user_data/history_20260828_010203.jsonl.bak": b'{"event":"old"}\n',
        "user_data/projects/plain.thermogar.json": b'{"project":1}\n',
        "user_data/projects/plain.thermogar.json.bak": b'{"project":0}\n',
        "user_data/projects/plain.thermogar.json.deleted": b'{"deleted":1}\n',
        "user_data/properties/elastic_phase_properties.json": b'{"entries":{}}\n',
        "user_data/properties/elastic_phase_properties.json.bak": b'{"entries":{"A":{}}}\n',
        "user_data/logs/errors.jsonl": b'{"error_id":"legacy"}\n',
    }
    for relative, data in payloads.items():
        path = install / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return payloads


@contextmanager
def directory_junction(
    temporary_root: Path,
    link: Path,
    target: Path,
):
    root = temporary_root.resolve(strict=True)
    link = Path(os.path.abspath(link))
    target = Path(os.path.abspath(target))
    if not link.is_absolute() or not target.is_absolute():
        raise AssertionError("junction paths must be absolute")
    if link.exists():
        raise AssertionError(f"junction link already exists: {link}")

    resolved_target = target.resolve(strict=True)
    resolved_target_parent = target.parent.resolve(strict=True)
    resolved_link_parent = link.parent.resolve(strict=True)
    for candidate in (
        resolved_target,
        resolved_target_parent,
        resolved_link_parent,
    ):
        if os.path.commonpath((str(root), str(candidate))) != str(root):
            raise AssertionError(f"junction fixture escaped temporary root: {candidate}")

    sentinel = target / ".junction-target-sentinel"
    sentinel_payload = b"junction target must survive cleanup\n"
    sentinel.write_bytes(sentinel_payload)
    cmd = Path(
        os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
    ).resolve(strict=True)
    created_reparse = False
    try:
        completed = subprocess.run(
            [
                str(cmd),
                "/d",
                "/c",
                "mklink",
                "/J",
                str(link),
                str(target),
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(
                "junction fixture creation failed: "
                f"exit={completed.returncode}; "
                f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
            )
        attributes = link.lstat().st_file_attributes
        created_reparse = bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        if not created_reparse:
            raise AssertionError(
                "junction fixture lacks FILE_ATTRIBUTE_REPARSE_POINT"
            )
        if link.resolve(strict=True) != resolved_target:
            raise AssertionError("junction target identity mismatch")
        yield sentinel
    finally:
        if created_reparse:
            os.rmdir(link)
        if sentinel.read_bytes() != sentinel_payload:
            raise AssertionError("junction cleanup changed its target sentinel")


class StateMigrationTests(unittest.TestCase):
    def test_001_complete_allowlist_copy_receipt_and_source_immutability(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            install = root / "install"
            install.mkdir()
            payloads = seed_allowlist(install)
            unknown = install / "user_data" / "alloys.json.lock"
            unknown.write_bytes(b"lock")
            unknown_project = install / "user_data" / "projects" / "scratch.tmp"
            unknown_project.write_bytes(b"temp")
            unknown_tree = install / "user_data" / "arbitrary"
            unknown_tree.mkdir()
            (unknown_tree / "hidden.json").write_bytes(b"do not follow")
            before = tree_manifest(install)

            paths = ThermoGarPaths(root / "profile")
            receipt = migrate_legacy_state(paths, install)
            self.assertEqual(tree_manifest(install), before)
            self.assertEqual(receipt["schema_version"], 1)
            self.assertEqual(receipt["outcome"], "completed")
            copied = {
                row["source_relative_path"]: row
                for row in receipt["records"]
                if row["disposition"] == "copied"
            }
            self.assertEqual(set(copied), set(payloads))
            for relative, data in payloads.items():
                row = copied[relative]
                self.assertEqual(row["size"], len(data))
                self.assertEqual(row["source_sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(row["destination_sha256"], row["source_sha256"])
                destination = paths.state_root / row["destination_relative_path"]
                self.assertEqual(destination.read_bytes(), data)
            rejected = {
                row["source_relative_path"]
                for row in receipt["records"]
                if row["disposition"] == "rejected"
            }
            self.assertEqual(
                rejected,
                {
                    "user_data/alloys.json.lock",
                    "user_data/arbitrary",
                    "user_data/projects/scratch.tmp",
                },
            )
            receipt_path = paths.state_root / MIGRATION_RECEIPT_NAME
            self.assertEqual(json.loads(receipt_path.read_text(encoding="utf-8")), receipt)

    def test_002_equal_digest_repeat_is_idempotent(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            install = root / "install"
            install.mkdir()
            seed_allowlist(install)
            source_before = tree_manifest(install)
            paths = ThermoGarPaths(root / "profile")
            migrate_legacy_state(paths, install)
            destination_before = {
                path.relative_to(paths.state_root).as_posix(): path.read_bytes()
                for path in paths.state_root.rglob("*")
                if path.is_file() and path.name != MIGRATION_RECEIPT_NAME
            }
            receipt = migrate_legacy_state(paths, install)
            self.assertTrue(receipt["records"])
            self.assertEqual(
                {row["disposition"] for row in receipt["records"]},
                {"skipped_same_digest"},
            )
            destination_after = {
                path.relative_to(paths.state_root).as_posix(): path.read_bytes()
                for path in paths.state_root.rglob("*")
                if path.is_file() and path.name != MIGRATION_RECEIPT_NAME
            }
            self.assertEqual(destination_after, destination_before)
            self.assertEqual(tree_manifest(install), source_before)

    def test_003_different_digest_conflict_preserves_both_sides(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            install = root / "install"
            source = install / "user_data" / "alloys.json"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"legacy")
            source_before = tree_manifest(install)
            paths = ThermoGarPaths(root / "profile")
            paths.configure_process_environment()
            paths.alloys_path.write_bytes(b"profile")
            with self.assertRaises(LegacyMigrationConflict) as caught:
                migrate_legacy_state(paths, install)
            self.assertEqual(source.read_bytes(), b"legacy")
            self.assertEqual(tree_manifest(install), source_before)
            self.assertEqual(paths.alloys_path.read_bytes(), b"profile")
            row = caught.exception.receipt["records"][0]
            self.assertEqual(row["disposition"], "conflict")
            self.assertEqual(
                row["source_sha256"], hashlib.sha256(b"legacy").hexdigest()
            )
            self.assertEqual(
                row["destination_sha256"], hashlib.sha256(b"profile").hexdigest()
            )

    def test_004_source_file_and_directory_reparse_are_rejected(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(strict=True)

            # A fixed source file reached through a reparse parent is rejected
            # before the final file is opened.
            install = root / "install"
            install.mkdir()
            external_user_data = root / "external-user-data"
            external_user_data.mkdir()
            external_alloys = external_user_data / "alloys.json"
            external_alloys.write_bytes(b"external")
            with directory_junction(
                root,
                install / "user_data",
                external_user_data,
            ):
                paths = ThermoGarPaths(root / "profile-file-source")
                receipt = migrate_legacy_state(paths, install)
                self.assertEqual(len(receipt["records"]), 1)
                row = receipt["records"][0]
                self.assertEqual(row["source_relative_path"], "user_data")
                self.assertEqual(row["disposition"], "rejected")
                self.assertFalse(paths.alloys_path.exists())
                self.assertEqual(external_alloys.read_bytes(), b"external")

            # A finite source directory reached through a junction is rejected
            # without enumerating the junction target.
            install = root / "install-directory"
            user_data = install / "user_data"
            user_data.mkdir(parents=True)
            external_projects = root / "external-projects"
            external_projects.mkdir()
            external_project = external_projects / "outside.thermogar.json"
            external_project.write_bytes(b"external-project")
            with directory_junction(
                root,
                user_data / "projects",
                external_projects,
            ):
                paths = ThermoGarPaths(root / "profile-directory-source")
                receipt = migrate_legacy_state(paths, install)
                rejected = {
                    row["source_relative_path"]: row
                    for row in receipt["records"]
                }
                self.assertEqual(
                    rejected["user_data/projects"]["disposition"],
                    "rejected",
                )
                self.assertFalse(
                    (paths.projects_root / "outside.thermogar.json").exists()
                )
                self.assertEqual(external_project.read_bytes(), b"external-project")

    def test_005_destination_file_and_directory_reparse_are_rejected(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(strict=True)
            install = root / "install"
            source = install / "user_data" / "alloys.json"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"legacy")

            # The destination file is below a reparse workspace parent.
            paths = ThermoGarPaths(root / "profile-file")
            paths.configure_process_environment()
            os.rmdir(paths.projects_root)
            os.rmdir(paths.workspace_root)
            external_workspace = root / "external-workspace"
            external_workspace.mkdir()
            with directory_junction(
                root,
                paths.workspace_root,
                external_workspace,
            ):
                receipt = migrate_legacy_state(paths, install)
                self.assertEqual(receipt["records"][0]["disposition"], "rejected")
                self.assertFalse((external_workspace / "alloys.json").exists())

            # The destination project directory itself is a junction.
            paths = ThermoGarPaths(root / "profile-directory")
            paths.configure_process_environment()
            os.rmdir(paths.projects_root)
            external_projects = root / "external-destination-projects"
            external_projects.mkdir()
            project = install / "user_data" / "projects" / "one.thermogar.json"
            project.parent.mkdir(exist_ok=True)
            project.write_bytes(b"project")
            with directory_junction(
                root,
                paths.projects_root,
                external_projects,
            ):
                receipt = migrate_legacy_state(paths, install)
                project_rows = [
                    row
                    for row in receipt["records"]
                    if row["source_relative_path"].endswith("one.thermogar.json")
                ]
                self.assertEqual(project_rows[0]["disposition"], "rejected")
                self.assertFalse(
                    (external_projects / "one.thermogar.json").exists()
                )

    def test_006_enumeration_overflow_is_bounded_and_terminal(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(strict=True)
            install = root / "install"
            user_data = install / "user_data"
            user_data.mkdir(parents=True)
            for index in range(MAX_MIGRATION_FILES + 1):
                (user_data / f"unknown-{index:04d}.bin").write_bytes(b"x")
            source_before = tree_manifest(install)
            paths = ThermoGarPaths(root / "profile-overflow")

            observations: list[str] = []
            original_scandir = os.scandir

            class CountingScandir:
                def __init__(self, directory: Path) -> None:
                    self._context = original_scandir(directory)
                    self._iterator = None

                def __enter__(self):
                    self._iterator = self._context.__enter__()
                    return self

                def __exit__(self, exc_type, exc_value, traceback):
                    return self._context.__exit__(exc_type, exc_value, traceback)

                def __iter__(self):
                    return self

                def __next__(self):
                    if self._iterator is None:
                        raise AssertionError("scandir iterator used before enter")
                    entry = next(self._iterator)
                    observations.append(entry.name)
                    if len(observations) > MAX_MIGRATION_FILES + 1:
                        raise AssertionError("enumeration continued beyond limit+1")
                    return entry

            with (
                mock.patch.object(
                    paths_module.os,
                    "scandir",
                    side_effect=CountingScandir,
                ),
                mock.patch.object(paths_module, "_read_held_snapshot") as read_mock,
                mock.patch.object(
                    paths_module,
                    "_atomic_copy_no_overwrite",
                ) as copy_mock,
            ):
                with self.assertRaises(ThermoGarPathError) as caught:
                    migrate_legacy_state(paths, install)

            exception_detail = str(caught.exception)
            self.assertIn(
                f"MAX_MIGRATION_FILES={MAX_MIGRATION_FILES}",
                exception_detail,
            )
            self.assertIn(
                f"observed_at_least={MAX_MIGRATION_FILES + 1}",
                exception_detail,
            )
            self.assertIn("no_copy_attempted=true", exception_detail)
            self.assertEqual(len(observations), MAX_MIGRATION_FILES + 1)
            read_mock.assert_not_called()
            copy_mock.assert_not_called()
            self.assertEqual(tree_manifest(install), source_before)
            self.assertFalse(paths.workspace_root.exists())

            receipt_path = paths.state_root / MIGRATION_RECEIPT_NAME
            receipt_bytes = receipt_path.read_bytes()
            self.assertLessEqual(len(receipt_bytes), 2048)
            receipt = json.loads(receipt_bytes.decode("utf-8"))
            self.assertEqual(receipt["schema_version"], 1)
            self.assertEqual(receipt["outcome"], "rejected_overflow")
            self.assertEqual(len(receipt["records"]), 1)
            row = receipt["records"][0]
            self.assertEqual(row["source_relative_path"], "user_data")
            self.assertEqual(row["destination_relative_path"], "")
            self.assertEqual(row["disposition"], "rejected")
            self.assertIn(
                f"MAX_MIGRATION_FILES={MAX_MIGRATION_FILES}",
                row["failure_detail"],
            )
            self.assertIn(
                f"observed_at_least={MAX_MIGRATION_FILES + 1}",
                row["failure_detail"],
            )
            self.assertIn("no_copy_attempted=true", row["failure_detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
