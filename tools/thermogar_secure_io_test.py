from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

import thermogar_secure_io as secure_io


class SecureIOTests(unittest.TestCase):
    def test_001_good_path_returns_one_bounded_immutable_snapshot(self):
        payload = b"$ minimal verified TDB snapshot\n"
        digest = hashlib.sha256(payload).hexdigest()
        with TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "good.tdb"
            source.write_bytes(payload)
            snapshot = secure_io.read_verified_snapshot(
                source,
                expected_sha256=digest,
                maximum_bytes=1024,
            )
        self.assertIs(type(snapshot.data), bytes)
        self.assertEqual(snapshot.data, payload)
        self.assertEqual(snapshot.sha256, digest)
        self.assertEqual(snapshot.size, len(payload))

    def test_002_hash_and_size_mismatch_fail_closed(self):
        with TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "bounded.tdb"
            source.write_bytes(b"12345678")
            with self.assertRaises(secure_io.SecureIOError):
                secure_io.read_verified_snapshot(
                    source,
                    expected_sha256="0" * 64,
                    maximum_bytes=1024,
                )
            with self.assertRaises(secure_io.SecureIOError):
                secure_io.read_verified_snapshot(source, maximum_bytes=7)

    def test_003_parser_receives_only_verified_snapshot_text(self):
        payload = b"$ exact parser input\r\nELEMENT /- ELECTRON_GAS 0 0 0 !\r\n"
        digest = hashlib.sha256(payload).hexdigest()
        received: list[str] = []

        def parser(source):
            received.append(source.read())
            return "parsed"

        result = secure_io.parse_verified_utf8_snapshot(
            payload,
            expected_sha256=digest,
            snapshot_sha256=digest,
            parser=parser,
        )
        self.assertEqual(result, "parsed")
        self.assertEqual(received, [payload.decode("utf-8")])

        with self.assertRaises(secure_io.SecureIOError):
            secure_io.parse_verified_utf8_snapshot(
                payload,
                expected_sha256=digest,
                snapshot_sha256="0" * 64,
                parser=lambda _source: self.fail("parser received unverified bytes"),
            )

    def test_004_leaf_and_component_symlink_or_reparse_are_rejected(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            target = root / "target.tdb"
            target.write_bytes(b"target")
            link = root / "link.tdb"
            try:
                link.symlink_to(target)
            except OSError:
                with mock.patch.object(
                    secure_io,
                    "_is_reparse_or_symlink",
                    return_value=True,
                ):
                    with self.assertRaises(secure_io.SecureIOError):
                        secure_io.read_verified_snapshot(target, maximum_bytes=1024)
            else:
                with self.assertRaises(secure_io.SecureIOError):
                    secure_io.read_verified_snapshot(link, maximum_bytes=1024)

            real_directory = root / "real"
            real_directory.mkdir()
            (real_directory / "component.tdb").write_bytes(b"component")
            directory_link = root / "linked-directory"
            try:
                directory_link.symlink_to(real_directory, target_is_directory=True)
            except OSError:
                return
            with self.assertRaises(secure_io.SecureIOError):
                secure_io.read_verified_snapshot(
                    directory_link / "component.tdb",
                    maximum_bytes=1024,
                )

    def test_005_read_time_mutation_is_rejected_or_blocked(self):
        with TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "mutable.tdb"
            source.write_bytes(b"stable-before-read")
            original_read = secure_io._read_bounded

            def mutate_after_read(descriptor: int, maximum_bytes: int) -> bytes:
                data = original_read(descriptor, maximum_bytes)
                try:
                    source.write_bytes(b"changed-during-read")
                except OSError as error:
                    raise secure_io.SecureIOError(
                        "Concurrent mutation was blocked by the held source handle."
                    ) from error
                return data

            with mock.patch.object(
                secure_io,
                "_read_bounded",
                side_effect=mutate_after_read,
            ):
                with self.assertRaises(secure_io.SecureIOError):
                    secure_io.read_verified_snapshot(source, maximum_bytes=1024)

    def test_006_path_swap_identity_contract_rejects_replacement(self):
        with TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "identity.tdb"
            source.write_bytes(b"original identity")
            baseline = secure_io._component_metadata(source)
            replacement = source.with_suffix(".replacement")
            replacement.write_bytes(b"replacement identity")
            os.replace(replacement, source)
            with self.assertRaises(secure_io.SecureIOError):
                secure_io._recheck_component_metadata(baseline)

    def test_007_atomic_write_uses_sibling_replace_and_verified_backup(self):
        with TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "workspace.json"
            secure_io.atomic_write_bytes(destination, b"first")
            secure_io.atomic_write_bytes(
                destination,
                b"second",
                create_backup=True,
            )
            self.assertEqual(destination.read_bytes(), b"second")
            self.assertEqual(
                destination.with_suffix(".json.bak").read_bytes(),
                b"first",
            )
            self.assertEqual(list(destination.parent.glob(".*.tmp")), [])
            self.assertEqual(
                list(destination.parent.glob("*.thermogar.lock")), []
            )

    def test_008_existing_lock_refuses_second_writer_without_change(self):
        with TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "workspace.json"
            destination.write_bytes(b"original")
            lock = destination.with_name(destination.name + ".thermogar.lock")
            lock.write_bytes(b"occupied")
            with self.assertRaises(secure_io.SecureIOError):
                secure_io.atomic_write_bytes(destination, b"replacement")
            self.assertEqual(destination.read_bytes(), b"original")

    def test_009_reparse_destination_is_never_overwritten(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            target = root / "target.json"
            target.write_bytes(b"target")
            destination = root / "destination.json"
            try:
                destination.symlink_to(target)
            except OSError:
                with mock.patch.object(
                    secure_io,
                    "_is_reparse_or_symlink",
                    return_value=True,
                ):
                    with self.assertRaises(secure_io.SecureIOError):
                        secure_io.atomic_write_bytes(target, b"replacement")
            else:
                with self.assertRaises(secure_io.SecureIOError):
                    secure_io.atomic_write_bytes(destination, b"replacement")
            self.assertEqual(target.read_bytes(), b"target")

    def test_010_secure_move_is_recoverable_and_never_overwrites(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "project.json"
            destination = root / "project.json.deleted"
            source.write_bytes(b"project snapshot")
            moved = secure_io.secure_move_no_overwrite(
                source,
                destination,
                canonical_root=root,
            )
            self.assertEqual(moved, destination)
            self.assertFalse(source.exists())
            self.assertEqual(destination.read_bytes(), b"project snapshot")

            source.write_bytes(b"second project")
            with self.assertRaises(secure_io.SecureIOError):
                secure_io.secure_move_no_overwrite(
                    source,
                    destination,
                    canonical_root=root,
                )
            self.assertEqual(source.read_bytes(), b"second project")
            self.assertEqual(destination.read_bytes(), b"project snapshot")

    def test_011_move_reparse_conflict_and_concurrent_lock_have_no_mutation(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.json"
            destination = root / "destination.json"
            target = root / "target.json"
            source.write_bytes(b"source")
            target.write_bytes(b"target")
            try:
                destination.symlink_to(target)
            except OSError:
                destination.write_bytes(b"conflict")
            with self.assertRaises(secure_io.SecureIOError):
                secure_io.secure_move_no_overwrite(
                    source,
                    destination,
                    canonical_root=root,
                )
            self.assertEqual(source.read_bytes(), b"source")
            self.assertEqual(target.read_bytes(), b"target")

        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.json"
            destination = root / "destination.json"
            source.write_bytes(b"source")
            lock = source.with_name(source.name + ".thermogar.lock")
            lock.write_bytes(b"occupied")
            with self.assertRaises(secure_io.SecureIOError):
                secure_io.secure_move_no_overwrite(
                    source,
                    destination,
                    canonical_root=root,
                )
            self.assertEqual(source.read_bytes(), b"source")
            self.assertFalse(destination.exists())

    def test_012_move_hook_failure_leaves_source_and_destination_unchanged(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.json"
            destination = root / "destination.json"
            source.write_bytes(b"source")
            with mock.patch.object(
                secure_io,
                "_rename_no_overwrite",
                side_effect=secure_io.SecureIOError("injected move failure"),
            ):
                with self.assertRaises(secure_io.SecureIOError):
                    secure_io.secure_move_no_overwrite(
                        source,
                        destination,
                        canonical_root=root,
                    )
            self.assertEqual(source.read_bytes(), b"source")
            self.assertFalse(destination.exists())

    def test_013_history_archive_preserves_exact_bytes_and_clears_atomically(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "history.jsonl"
            backup = root / "history.jsonl.bak"
            payload = b'{"entry":1}\n{"entry":2}\n'
            source.write_bytes(payload)
            archived = secure_io.secure_archive_and_clear(
                source,
                backup,
                canonical_root=root,
            )
            self.assertTrue(archived)
            self.assertEqual(backup.read_bytes(), payload)
            self.assertEqual(source.read_bytes(), b"")

    def test_014_history_conflict_or_source_reparse_preserves_all_bytes(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "history.jsonl"
            backup = root / "history.jsonl.bak"
            source.write_bytes(b"history")
            backup.write_bytes(b"existing backup")
            with self.assertRaises(secure_io.SecureIOError):
                secure_io.secure_archive_and_clear(
                    source,
                    backup,
                    canonical_root=root,
                )
            self.assertEqual(source.read_bytes(), b"history")
            self.assertEqual(backup.read_bytes(), b"existing backup")

            target = root / "target.jsonl"
            target.write_bytes(b"target")
            reparse_source = root / "reparse.jsonl"
            try:
                reparse_source.symlink_to(target)
            except OSError:
                return
            with self.assertRaises(secure_io.SecureIOError):
                secure_io.secure_archive_and_clear(
                    reparse_source,
                    root / "reparse.bak",
                    canonical_root=root,
                )
            self.assertEqual(target.read_bytes(), b"target")

    def test_015_non_windows_secure_operations_fail_closed(self):
        with TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source.json"
            source.write_bytes(b"source")
            with mock.patch.object(secure_io.os, "name", "posix"):
                with self.assertRaises(secure_io.SecureIOError):
                    secure_io.read_verified_snapshot(source, maximum_bytes=1024)
                with self.assertRaises(secure_io.SecureIOError):
                    secure_io.atomic_write_bytes(source, b"replacement")
            self.assertEqual(source.read_bytes(), b"source")

    def test_016_move_source_and_destination_swap_hooks_fail_recoverably(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "project.json"
            destination = root / "project.json.deleted"
            displaced = root / "project.displaced"
            replacement = root / "project.replacement"
            source.write_bytes(b"verified project")
            replacement.write_bytes(b"attacker project")

            def swap_source(operation, hooked_source, hooked_destination):
                self.assertEqual(operation, "move")
                self.assertEqual(hooked_source, source)
                self.assertEqual(hooked_destination, destination)
                os.rename(source, displaced)
                os.rename(replacement, source)

            with mock.patch.object(
                secure_io,
                "_before_secure_transition",
                side_effect=swap_source,
            ):
                with self.assertRaises(secure_io.SecureIOError):
                    secure_io.secure_move_no_overwrite(
                        source,
                        destination,
                        canonical_root=root,
                    )
            self.assertEqual(displaced.read_bytes(), b"verified project")
            self.assertEqual(source.read_bytes(), b"attacker project")
            self.assertFalse(destination.exists())

        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "project.json"
            destination = root / "project.json.deleted"
            source.write_bytes(b"verified project")

            def occupy_destination(_operation, _source, hooked_destination):
                hooked_destination.write_bytes(b"destination swap")

            with mock.patch.object(
                secure_io,
                "_before_secure_transition",
                side_effect=occupy_destination,
            ):
                with self.assertRaises((secure_io.SecureIOError, FileExistsError)):
                    secure_io.secure_move_no_overwrite(
                        source,
                        destination,
                        canonical_root=root,
                    )
            self.assertEqual(source.read_bytes(), b"verified project")
            self.assertEqual(destination.read_bytes(), b"destination swap")

    def test_017_history_swaps_and_concurrent_writer_preserve_source_bytes(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "history.jsonl"
            backup = root / "history.jsonl.bak"
            displaced = root / "history.displaced"
            replacement = root / "history.replacement"
            source.write_bytes(b"verified history")
            replacement.write_bytes(b"attacker history")

            def swap_source(operation, hooked_source, hooked_backup):
                self.assertEqual(operation, "archive")
                self.assertEqual(hooked_source, source)
                self.assertEqual(hooked_backup, backup)
                os.rename(source, displaced)
                os.rename(replacement, source)

            with mock.patch.object(
                secure_io,
                "_before_secure_transition",
                side_effect=swap_source,
            ):
                with self.assertRaises(secure_io.SecureIOError):
                    secure_io.secure_archive_and_clear(
                        source,
                        backup,
                        canonical_root=root,
                    )
            self.assertEqual(backup.read_bytes(), b"verified history")
            self.assertEqual(displaced.read_bytes(), b"verified history")
            self.assertEqual(source.read_bytes(), b"attacker history")

        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "history.jsonl"
            backup = root / "history.jsonl.bak"
            replacement = root / "backup.replacement"
            source.write_bytes(b"verified history")
            replacement.write_bytes(b"attacker backup")

            def swap_backup(_operation, _source, hooked_backup):
                os.replace(replacement, hooked_backup)

            with mock.patch.object(
                secure_io,
                "_before_secure_transition",
                side_effect=swap_backup,
            ):
                with self.assertRaises(secure_io.SecureIOError):
                    secure_io.secure_archive_and_clear(
                        source,
                        backup,
                        canonical_root=root,
                    )
            self.assertEqual(source.read_bytes(), b"verified history")
            self.assertEqual(backup.read_bytes(), b"attacker backup")

        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "history.jsonl"
            backup = root / "history.jsonl.bak"
            source.write_bytes(b"verified history")
            lock = source.with_name(source.name + ".thermogar.lock")
            lock.write_bytes(b"occupied")
            with self.assertRaises(secure_io.SecureIOError):
                secure_io.secure_archive_and_clear(
                    source,
                    backup,
                    canonical_root=root,
                )
            self.assertEqual(source.read_bytes(), b"verified history")
            self.assertFalse(backup.exists())

    def test_018_atomic_create_or_overwrite_decision_is_inside_writer_lock(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            destination = root / "project.json"

            def racing_creator(hooked_destination):
                if hooked_destination == destination:
                    hooked_destination.write_bytes(b"concurrent creator")

            with mock.patch.object(
                secure_io,
                "_before_atomic_write_decision",
                side_effect=racing_creator,
            ):
                with self.assertRaises(FileExistsError):
                    secure_io.atomic_write_bytes(
                        destination,
                        b"caller payload",
                        overwrite=False,
                        canonical_root=root,
                    )
            self.assertEqual(destination.read_bytes(), b"concurrent creator")
            self.assertFalse(destination.with_suffix(".json.bak").exists())

        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            destination = root / "project.json"

            def racing_creator(hooked_destination):
                if hooked_destination == destination:
                    hooked_destination.write_bytes(b"concurrent creator")

            with mock.patch.object(
                secure_io,
                "_before_atomic_write_decision",
                side_effect=racing_creator,
            ):
                secure_io.atomic_write_bytes(
                    destination,
                    b"caller replacement",
                    create_backup=True,
                    overwrite=True,
                    canonical_root=root,
                )
            self.assertEqual(destination.read_bytes(), b"caller replacement")
            self.assertEqual(
                destination.with_suffix(".json.bak").read_bytes(),
                b"concurrent creator",
            )

    def test_019_atomic_update_consumes_latest_locked_snapshot_and_backs_it_up(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            destination = root / "alloys.json"
            destination.write_bytes(b"stale caller snapshot")

            def concurrent_update(hooked_destination):
                if hooked_destination == destination:
                    hooked_destination.write_bytes(b"concurrent update")

            with mock.patch.object(
                secure_io,
                "_before_atomic_update_decision",
                side_effect=concurrent_update,
            ):
                secure_io.atomic_update_bytes(
                    destination,
                    lambda current: current + b" + caller mutation",
                    create_backup=True,
                    canonical_root=root,
                )
            self.assertEqual(
                destination.read_bytes(),
                b"concurrent update + caller mutation",
            )
            self.assertEqual(
                destination.with_suffix(".json.bak").read_bytes(),
                b"concurrent update",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
