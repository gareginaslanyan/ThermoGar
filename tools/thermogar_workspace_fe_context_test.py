from __future__ import annotations

import atexit
from contextlib import contextmanager
import hashlib
from pathlib import Path
import json
import os
import stat
import subprocess
import sys
import tempfile
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest import mock


_PROCESS_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="thermogar-workspace-fe-context-test-"
)
_PROCESS_TEMPORARY_ROOT = Path(_PROCESS_TEMPORARY.name).resolve(strict=True)
_PROCESS_STATE_ROOT = _PROCESS_TEMPORARY_ROOT / "state"
_PROCESS_MATPLOTLIB_ROOT = _PROCESS_TEMPORARY_ROOT / "matplotlib"
_PROCESS_RUNTIME_TEMP = _PROCESS_TEMPORARY_ROOT / "runtime" / "tmp"
for _directory in (
    _PROCESS_STATE_ROOT,
    _PROCESS_MATPLOTLIB_ROOT,
    _PROCESS_RUNTIME_TEMP,
):
    _directory.mkdir(parents=True, exist_ok=True)
os.environ["THERMOGAR_STATE_ROOT"] = str(_PROCESS_STATE_ROOT)
os.environ["MPLCONFIGDIR"] = str(_PROCESS_MATPLOTLIB_ROOT)
os.environ["TMP"] = str(_PROCESS_RUNTIME_TEMP)
os.environ["TEMP"] = str(_PROCESS_RUNTIME_TEMP)
tempfile.tempdir = str(_PROCESS_RUNTIME_TEMP)
atexit.register(_PROCESS_TEMPORARY.cleanup)


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

import thermogar_workspace as workspace
import thermogar_secure_io as secure_io
from thermogar_paths import ThermoGarPaths


FE_SHA256 = "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612"


def profile_paths(temporary_directory: str) -> ThermoGarPaths:
    return ThermoGarPaths(Path(temporary_directory) / "profile")


def tree_manifest(root: Path) -> tuple[tuple[str, int, str], ...]:
    rows: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        info = path.lstat()
        digest = (
            hashlib.sha256(path.read_bytes()).hexdigest()
            if stat.S_ISREG(info.st_mode)
            else ""
        )
        rows.append((path.relative_to(root).as_posix(), int(info.st_size), digest))
    return tuple(rows)


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
    target_before = tree_manifest(target)
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
            final_attributes = link.lstat().st_file_attributes
            if not final_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise AssertionError("junction lost reparse identity before cleanup")
            if link.resolve(strict=True) != resolved_target:
                raise AssertionError("junction target changed before cleanup")
            os.rmdir(link)
        if sentinel.read_bytes() != sentinel_payload:
            raise AssertionError("junction cleanup changed its target sentinel")
        if tree_manifest(target) != target_before:
            raise AssertionError("junction target manifest changed")


def fe_context() -> dict[str, object]:
    return {
        "database_key": "fe",
        "balance": "FE",
        "units": "wt",
        "composition": "C=0.20, CR=11.5, NI=0.7",
        "pressure_pa": 101325.0,
        "steel_mode": "metastable",
        "database_path": str(
            ROOT
            / "databases/converted/fe/"
            / "mc_fe_v2062_with_mobility.thermogar.tdb"
        ),
        "database_sha256": FE_SHA256,
        "fe_profile_key": "thermogar_patch",
    }


def legacy_context(database_key: str) -> dict[str, object]:
    if database_key == "ni":
        return {
            "database_key": "ni",
            "balance": "NI",
            "units": "at",
            "composition": "AL=15",
            "pressure_pa": 101325.0,
            "steel_mode": "stable",
        }
    return {
        "database_key": "al",
        "balance": "AL",
        "units": "at",
        "composition": "CU=4",
        "pressure_pa": 101325.0,
        "steel_mode": "stable",
    }


class FeWorkspaceContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.equilibrium_guard = mock.patch.object(
            workspace,
            "equilibrium",
            side_effect=AssertionError("workspace test attempted scientific execution"),
        )
        self.equilibrium = self.equilibrium_guard.start()

    def tearDown(self) -> None:
        self.equilibrium.assert_not_called()
        self.equilibrium_guard.stop()

    def test_001_canonical_fe_context_is_exact_and_schema_stays_v1(self):
        clean = workspace.validate_context_payload(fe_context())
        self.assertEqual(workspace.STORAGE_SCHEMA_VERSION, 1)
        self.assertEqual(clean["database_key"], "fe")
        self.assertEqual(clean["fe_profile_key"], "thermogar_patch")
        self.assertEqual(clean["database_sha256"], FE_SHA256)
        self.assertNotIn("database_path", clean)

    def test_002_unknown_upstream_missing_profile_and_hash_drift_fail_closed(self):
        mutations = (
            ("database_key", "unknown"),
            ("fe_profile_key", "upstream_original"),
            ("fe_profile_key", "unknown_profile"),
            ("fe_profile_key", None),
            ("database_sha256", "0" * 64),
            ("database_sha256", ""),
            (
                "database_path",
                "databases/diagnostic/fe/"
                "mc_fe_v2062_unpatched_with_mobility.thermogar.tdb",
            ),
        )
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                context = fe_context()
                context[field] = value
                with self.assertRaises(ValueError):
                    workspace.validate_context_payload(context)

    def test_003_legacy_ni_and_al_projects_remain_compatible(self):
        for database_key in ("ni", "al"):
            with self.subTest(database_key=database_key):
                payload = workspace.build_project_payload(
                    f"Legacy {database_key}",
                    "",
                    legacy_context(database_key),
                )
                clean = workspace.validate_project_payload(payload)
                self.assertEqual(clean["context"]["database_key"], database_key)
                self.assertNotIn("fe_profile_key", clean["context"])

    def test_004_fe_project_round_trip_preserves_profile_and_hash(self):
        payload = workspace.build_project_payload("Fe project", "", fe_context())
        clean = workspace.validate_project_payload(payload)
        self.assertEqual(clean["context"]["fe_profile_key"], "thermogar_patch")
        self.assertEqual(clean["context"]["database_sha256"], FE_SHA256)

        tampered = dict(payload)
        tampered["context"] = dict(payload["context"])
        tampered["context"]["fe_profile_key"] = "upstream_original"
        with self.assertRaises(ValueError):
            workspace.validate_project_payload(tampered)

    def test_005_fe_alloy_round_trip_preserves_profile_and_hash(self):
        with TemporaryDirectory() as temporary_directory:
            saved = workspace.upsert_user_alloy(
                profile_paths(temporary_directory),
                "Fe diagnostic",
                "",
                fe_context(),
            )
            restored = workspace.alloy_context(saved)
        self.assertEqual(restored["fe_profile_key"], "thermogar_patch")
        self.assertEqual(restored["database_sha256"], FE_SHA256)

        tampered = dict(saved)
        tampered["database_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            workspace.alloy_context(tampered)

    def test_006_fe_history_round_trip_preserves_profile_and_hash(self):
        with TemporaryDirectory() as temporary_directory:
            workspace.record_history(
                profile_paths(temporary_directory),
                "project_loaded",
                "Fe project",
                fe_context(),
            )
            entries, chain_ok = workspace.load_history(
                profile_paths(temporary_directory)
            )
        self.assertTrue(chain_ok)
        self.assertEqual(len(entries), 1)
        restored = workspace.context_from_history_entry(entries[0])
        self.assertEqual(restored["fe_profile_key"], "thermogar_patch")
        self.assertEqual(restored["database_sha256"], FE_SHA256)

        tampered = dict(entries[0])
        tampered["fe_profile_key"] = "upstream_original"
        with self.assertRaises(ValueError):
            workspace.context_from_history_entry(tampered)

    def test_007_queue_and_apply_are_atomic_for_fe_and_do_not_fallback_to_ni(self):
        fake_streamlit = SimpleNamespace(session_state={})
        with mock.patch.object(workspace, "st", fake_streamlit):
            workspace.queue_context_load(fe_context(), label="Fe project")
            workspace.apply_pending_state()
        state = fake_streamlit.session_state
        self.assertEqual(state["thermogar_database_key"], "fe")
        self.assertEqual(state["thermogar_fe_profile"], "thermogar_patch")
        self.assertEqual(state["thermogar_balance_fe"], "FE")
        self.assertEqual(
            state["_thermogar_loaded_context"]["database_sha256"], FE_SHA256
        )
        self.assertEqual(
            state["_thermogar_loaded_context"]["fe_profile_key"],
            "thermogar_patch",
        )

    def test_008_rejected_queue_does_not_partially_modify_active_context(self):
        fake_streamlit = SimpleNamespace(
            session_state={
                "thermogar_database_key": "al",
                "thermogar_balance_al": "AL",
            }
        )
        tampered = fe_context()
        tampered["fe_profile_key"] = "upstream_original"
        with mock.patch.object(workspace, "st", fake_streamlit):
            with self.assertRaises(ValueError):
                workspace.queue_context_load(tampered, label="Tampered")
        self.assertEqual(
            fake_streamlit.session_state,
            {"thermogar_database_key": "al", "thermogar_balance_al": "AL"},
        )

    def test_009_project_scan_returns_exact_verified_download_snapshot(self):
        with TemporaryDirectory() as temporary_directory:
            payload = workspace.build_project_payload(
                "Exact download",
                "",
                fe_context(),
            )
            path = workspace.save_project_local(
                profile_paths(temporary_directory),
                payload,
            )
            exact_bytes = path.read_bytes()
            records, errors = workspace.scan_projects(
                profile_paths(temporary_directory)
            )
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 1)
        scanned_path, scanned_payload, download_bytes = records[0]
        self.assertEqual(scanned_path.name, path.name)
        self.assertEqual(scanned_payload["name"], "Exact download")
        self.assertEqual(download_bytes, exact_bytes)

    def test_010_project_reparse_entry_is_rejected_from_scan(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve(strict=True)
            payload = workspace.build_project_payload(
                "Plain project",
                "",
                legacy_context("ni"),
            )
            target_paths = ThermoGarPaths(root / "target-profile")
            target_path = workspace.save_project_local(
                target_paths,
                payload,
            )
            exact_target = target_path.read_bytes()

            attack_paths = ThermoGarPaths(root / "attack-profile")
            attack_paths.configure_process_environment()
            os.rmdir(attack_paths.projects_root)
            with directory_junction(
                root,
                attack_paths.projects_root,
                target_paths.projects_root,
            ):
                with mock.patch.object(
                    workspace,
                    "held_verified_snapshot",
                ) as snapshot_mock:
                    with self.assertRaises(secure_io.SecureIOError):
                        workspace.scan_projects(attack_paths)
                snapshot_mock.assert_not_called()
                self.assertEqual(target_path.read_bytes(), exact_target)

    def test_011_project_create_and_overwrite_decisions_are_atomic(self):
        payload = workspace.build_project_payload(
            "Atomic project",
            "",
            fe_context(),
        )
        with TemporaryDirectory() as temporary_directory:
            expected = workspace.project_file_path(
                profile_paths(temporary_directory),
                payload["name"],
            )

            def create_concurrently(destination):
                if destination == expected:
                    destination.write_bytes(b"concurrent project")

            with mock.patch.object(
                secure_io,
                "_before_atomic_write_decision",
                side_effect=create_concurrently,
            ):
                with self.assertRaises(FileExistsError):
                    workspace.save_project_local(
                        profile_paths(temporary_directory),
                        payload,
                        overwrite=False,
                    )
            self.assertEqual(expected.read_bytes(), b"concurrent project")

        with TemporaryDirectory() as temporary_directory:
            expected = workspace.project_file_path(
                profile_paths(temporary_directory),
                payload["name"],
            )

            def create_concurrently(destination):
                if destination == expected:
                    destination.write_bytes(b"concurrent project")

            with mock.patch.object(
                secure_io,
                "_before_atomic_write_decision",
                side_effect=create_concurrently,
            ):
                saved_path = workspace.save_project_local(
                    profile_paths(temporary_directory),
                    payload,
                    overwrite=True,
                )
            self.assertEqual(saved_path, expected)
            self.assertEqual(
                expected.with_suffix(expected.suffix + ".bak").read_bytes(),
                b"concurrent project",
            )
            self.assertEqual(
                workspace.list_projects(profile_paths(temporary_directory))[0][1]["name"],
                "Atomic project",
            )

    def test_012_alloy_mutations_consume_latest_locked_snapshot(self):
        with TemporaryDirectory() as temporary_directory:
            first = workspace.upsert_user_alloy(
                profile_paths(temporary_directory),
                "First",
                "",
                legacy_context("ni"),
            )
            path = workspace.alloys_path(profile_paths(temporary_directory))
            concurrent = {
                "id": "concurrent",
                "name": "Concurrent",
                "database_key": "al",
            }
            injected_bytes: list[bytes] = []

            def concurrent_upsert(destination):
                if destination != path:
                    return
                payload = json.loads(destination.read_text(encoding="utf-8"))
                payload["alloys"].append(concurrent)
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
                destination.write_bytes(data)
                injected_bytes.append(data)

            with mock.patch.object(
                secure_io,
                "_before_atomic_update_decision",
                side_effect=concurrent_upsert,
            ):
                workspace.upsert_user_alloy(
                    profile_paths(temporary_directory),
                    "Third",
                    "",
                    legacy_context("ni"),
                )
            ids = {
                item["id"]
                for item in workspace.load_user_alloys(profile_paths(temporary_directory))
            }
            self.assertIn(first["id"], ids)
            self.assertIn("concurrent", ids)
            self.assertEqual(path.with_suffix(".json.bak").read_bytes(), injected_bytes[0])

            def concurrent_delete(destination):
                if destination != path:
                    return
                payload = json.loads(destination.read_text(encoding="utf-8"))
                payload["alloys"].append(
                    {"id": "during-delete", "name": "During delete"}
                )
                destination.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            with mock.patch.object(
                secure_io,
                "_before_atomic_update_decision",
                side_effect=concurrent_delete,
            ):
                workspace.delete_user_alloy(
                    profile_paths(temporary_directory), first["id"]
                )
            ids = {
                item["id"]
                for item in workspace.load_user_alloys(profile_paths(temporary_directory))
            }
            self.assertNotIn(first["id"], ids)
            self.assertIn("during-delete", ids)

    def test_013_alloy_duplicate_and_import_conflicts_use_locked_snapshot(self):
        with TemporaryDirectory() as temporary_directory:
            path = workspace.alloys_path(profile_paths(temporary_directory))
            workspace.save_user_alloys(profile_paths(temporary_directory), [])

            def concurrent_duplicate(destination):
                if destination != path:
                    return
                payload = json.loads(destination.read_text(encoding="utf-8"))
                payload["alloys"].append(
                    {
                        "id": "racing-duplicate",
                        "name": "Duplicate",
                        "database_key": "ni",
                    }
                )
                destination.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            with mock.patch.object(
                secure_io,
                "_before_atomic_update_decision",
                side_effect=concurrent_duplicate,
            ):
                with self.assertRaises(FileExistsError):
                    workspace.upsert_user_alloy(
                        profile_paths(temporary_directory),
                        "Duplicate",
                        "",
                        legacy_context("ni"),
                        overwrite=False,
                    )
            before_import = path.read_bytes()
            with self.assertRaises(ValueError):
                workspace.merge_user_alloys(
                    profile_paths(temporary_directory),
                    [{"id": "racing-duplicate", "name": "Imported"}],
                    overwrite=False,
                )
            self.assertEqual(path.read_bytes(), before_import)

            def concurrent_import(destination):
                if destination != path:
                    return
                payload = json.loads(destination.read_text(encoding="utf-8"))
                payload["alloys"].append(
                    {"id": "during-import", "name": "During import"}
                )
                destination.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            with mock.patch.object(
                secure_io,
                "_before_atomic_update_decision",
                side_effect=concurrent_import,
            ):
                workspace.merge_user_alloys(
                    profile_paths(temporary_directory),
                    [{"id": "imported", "name": "Imported"}],
                    overwrite=False,
                )
            ids = {
                item["id"]
                for item in workspace.load_user_alloys(profile_paths(temporary_directory))
            }
            self.assertIn("during-import", ids)
            self.assertIn("imported", ids)

    def test_014_history_failure_is_nonfatal_after_durable_mutation(self):
        with TemporaryDirectory() as temporary_directory:
            payload = workspace.build_project_payload(
                "Durable project",
                "",
                fe_context(),
            )
            path = workspace.save_project_local(
                profile_paths(temporary_directory), payload
            )
            durable_bytes = path.read_bytes()
            with mock.patch.object(
                workspace,
                "record_history",
                side_effect=RuntimeError("injected history failure"),
            ):
                warning = workspace.record_history_nonfatal(
                    profile_paths(temporary_directory),
                    "project_saved",
                    "Saved",
                    fe_context(),
                )
            self.assertIn("injected history failure", warning or "")
            self.assertEqual(path.read_bytes(), durable_bytes)

    def test_015_all_databases_share_exact_profile_state_routes(self):
        with TemporaryDirectory() as temporary_directory:
            paths = profile_paths(temporary_directory)
            paths.configure_process_environment()
            for database_key in ("ni", "al", "fe"):
                with self.subTest(database_key=database_key):
                    self.assertEqual(workspace.alloys_path(paths), paths.alloys_path)
                    self.assertEqual(workspace.history_path(paths), paths.history_path)
                    self.assertEqual(
                        workspace.projects_directory(paths),
                        paths.projects_root,
                    )
            self.assertFalse((Path(temporary_directory) / "user_data").exists())
            with self.assertRaises(TypeError):
                workspace.alloys_path(Path(temporary_directory))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main(verbosity=2)
