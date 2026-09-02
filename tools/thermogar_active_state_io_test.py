from __future__ import annotations

import atexit
from contextlib import contextmanager, nullcontext
import hashlib
from pathlib import Path
import json
import os
import stat
import subprocess
import sys
import tempfile
from tempfile import TemporaryDirectory
import unittest
from unittest import mock


_PROCESS_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="thermogar-active-state-io-test-"
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

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

import thermogar_properties as properties
import thermogar_secure_io as secure_io
import thermogar_stage14 as stage14
import thermogar_workspace as workspace
from thermogar_paths import ThermoGarPaths


def tree_manifest(root: Path) -> tuple[tuple[str, int, str], ...]:
    rows: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        info = path.lstat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if stat.S_ISREG(info.st_mode) else ""
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


@contextmanager
def readonly_windows_tree(root: Path):
    if os.name != "nt":
        raise AssertionError("The required read-only install gate is Windows-specific.")
    identity = subprocess.run(
        ["whoami"], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()
    deny = subprocess.run(
        ["icacls", str(root), "/deny", f"{identity}:(OI)(CI)M"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if deny.returncode != 0:
        raise AssertionError(f"Unable to establish read-only ACL: {deny.stdout} {deny.stderr}")
    try:
        probe = root / "write-probe"
        try:
            probe.write_bytes(b"forbidden")
        except OSError:
            pass
        else:
            probe.unlink(missing_ok=True)
            raise AssertionError("Synthetic install root remained writable.")
        yield
    finally:
        restore = subprocess.run(
            ["icacls", str(root), "/remove:d", identity, "/T", "/C"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if restore.returncode != 0:
            raise AssertionError(
                f"Unable to restore fixture ACL: {restore.stdout} {restore.stderr}"
            )


def fe_context() -> dict[str, object]:
    return {
        "database_key": "fe",
        "balance": "FE",
        "units": "wt",
        "composition": "C=0.2",
        "pressure_pa": 101325.0,
        "steel_mode": "stable",
        "database_sha256": workspace.FE_DATABASE_SHA256,
        "fe_profile_key": "thermogar_patch",
    }


class _FakeStreamlit:
    def error(self, _value):
        return None

    def caption(self, _value):
        return None

    def write(self, _value):
        return None

    def expander(self, *_args, **_kwargs):
        return nullcontext()


class ActiveStateIOTests(unittest.TestCase):
    def test_001_elastic_library_uses_verified_bounded_snapshot(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = ThermoGarPaths(root / "profile")
            paths.configure_process_environment()
            library = properties.empty_elastic_library()
            library["entries"]["ni::FCC_A1"] = {"young_gpa": 200.0}
            path = properties.save_elastic_library(paths, library)
            exact = path.read_bytes()
            loaded = properties.load_elastic_library(paths)
            self.assertEqual(loaded["entries"]["ni::FCC_A1"]["young_gpa"], 200.0)
            self.assertEqual(
                properties._sha256(paths, path),
                __import__("hashlib").sha256(exact).hexdigest(),
            )

            target_properties = root / "target-properties"
            target_properties.mkdir()
            target_library = target_properties / path.name
            target_library.write_bytes(exact)
            attack_paths = ThermoGarPaths(root / "attack-profile")
            attack_paths.configure_process_environment()
            attack_paths.elastic_properties_path.parent.rmdir()
            with directory_junction(
                root,
                attack_paths.elastic_properties_path.parent,
                target_properties,
            ):
                with mock.patch.object(secure_io.os, "open") as open_mock:
                    with self.assertRaises(secure_io.SecureIOError):
                        properties.load_elastic_library(attack_paths)
                open_mock.assert_not_called()

    def test_002_elastic_editor_merges_latest_locked_snapshot(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = ThermoGarPaths(root / "profile")
            paths.configure_process_environment()
            initial = properties.empty_elastic_library()
            initial["entries"]["ni::A"] = {"phase": "A"}
            path = properties.save_elastic_library(paths, initial)
            injected: list[bytes] = []

            def concurrent_update(destination):
                if destination != path:
                    return
                payload = json.loads(destination.read_text(encoding="utf-8"))
                payload["entries"]["ni::CONCURRENT"] = {"phase": "CONCURRENT"}
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
                destination.write_bytes(data)
                injected.append(data)

            edited = pd.DataFrame(
                [
                    {
                        "Фаза": "B",
                        "E, ГПа": 210.0,
                        "ν": 0.29,
                        "Происхождение": "test",
                        "Источник": "focused test",
                        "Температура источника, °C": 25.0,
                        "Примечание": "",
                    }
                ]
            )
            with mock.patch.object(
                secure_io,
                "_before_atomic_update_decision",
                side_effect=concurrent_update,
            ):
                saved_path, count = properties._save_editor_to_library(
                    paths,
                    "ni",
                    edited,
                )
            self.assertEqual(saved_path, path)
            self.assertEqual(count, 1)
            entries = properties.load_elastic_library(paths)["entries"]
            self.assertIn("ni::A", entries)
            self.assertIn("ni::CONCURRENT", entries)
            self.assertIn("ni::B", entries)
            self.assertEqual(path.with_suffix(".json.bak").read_bytes(), injected[0])

    def test_003_stage14_error_append_consumes_latest_locked_log(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = ThermoGarPaths(root / "profile")
            paths.configure_process_environment()
            log_path = paths.stage14_errors_path
            log_path.write_bytes(b'{"error_id":"initial"}\n')

            def concurrent_append(destination):
                if destination == log_path:
                    destination.write_bytes(
                        destination.read_bytes()
                        + b'{"error_id":"concurrent"}\n'
                    )

            with mock.patch.object(
                secure_io,
                "_before_atomic_update_decision",
                side_effect=concurrent_append,
            ):
                error_id, _payload = stage14._write_error_log(
                    paths,
                    RuntimeError("focused error"),
                    "focused-test",
                )
            lines = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(lines[0]["error_id"], "initial")
            self.assertEqual(lines[1]["error_id"], "concurrent")
            self.assertEqual(lines[2]["error_id"], error_id)
            with (
                mock.patch.object(stage14, "st", _FakeStreamlit()),
                mock.patch.object(stage14, "release_download_button"),
            ):
                stage14.render_friendly_error(
                    RuntimeError("wrapper"),
                    context="wrapper-test",
                    paths=paths,
                )
            self.assertIn(b'"context": "wrapper-test"', log_path.read_bytes())

    def test_004_stage14_error_log_is_bounded_and_reparse_safe(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = ThermoGarPaths(root / "profile")
            paths.configure_process_environment()
            with mock.patch.object(stage14, "MAX_ERROR_LOG_BYTES", 4096):
                for index in range(12):
                    error_id, _payload = stage14._write_error_log(
                        paths,
                        RuntimeError("bounded-" + str(index) + "-" + "x" * 200),
                        "bounded-test",
                    )
            log_path = paths.stage14_errors_path
            self.assertLessEqual(log_path.stat().st_size, 4096)
            self.assertEqual(
                json.loads(log_path.read_text(encoding="utf-8").splitlines()[-1])["error_id"],
                error_id,
            )

        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = ThermoGarPaths(root / "profile")
            paths.configure_process_environment()
            target = root / "target-logs"
            target.mkdir()
            logs = paths.stage14_errors_path.parent
            logs.rmdir()
            with directory_junction(root, logs, target):
                with mock.patch.object(secure_io.os, "open") as open_mock:
                    with self.assertRaises(secure_io.SecureIOError):
                        stage14._write_error_log(
                            paths,
                            RuntimeError("reparse"),
                            "reparse-test",
                        )
                open_mock.assert_not_called()

    def test_005_read_only_install_all_active_writes_are_profile_only(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            install = root / "install"
            install.mkdir()
            (install / "immutable.txt").write_bytes(b"immutable install")
            before = tree_manifest(install)
            paths = ThermoGarPaths(root / "profile")
            paths.configure_process_environment()
            payload = workspace.build_project_payload(
                "Profile project",
                "",
                fe_context(),
            )

            with readonly_windows_tree(install):
                first = workspace.upsert_user_alloy(
                    paths,
                    "Steel",
                    "",
                    fe_context(),
                )
                workspace.upsert_user_alloy(
                    paths,
                    "Steel",
                    "updated",
                    fe_context(),
                )
                workspace.record_calculation_history(
                    paths,
                    "Focused profile event",
                    fe_context(),
                )
                project_path = workspace.save_project_local(paths, payload)
                workspace.save_project_local(paths, payload, overwrite=True)
                properties.save_elastic_library(
                    paths,
                    properties.empty_elastic_library(),
                )
                with (
                    mock.patch.object(stage14, "st", _FakeStreamlit()),
                    mock.patch.object(stage14, "release_download_button"),
                ):
                    stage14.render_friendly_error(
                        RuntimeError("profile-only"),
                        context="read-only-install",
                        paths=paths,
                    )

            self.assertEqual(tree_manifest(install), before)
            self.assertEqual(workspace.load_user_alloys(paths)[0]["id"], first["id"])
            self.assertTrue(paths.alloys_path.with_suffix(".json.bak").is_file())
            self.assertTrue(paths.history_path.is_file())
            self.assertTrue(project_path.is_file())
            self.assertTrue(
                project_path.with_suffix(project_path.suffix + ".bak").is_file()
            )
            self.assertTrue(paths.elastic_properties_path.is_file())
            self.assertTrue(paths.stage14_errors_path.is_file())
            for path in paths.state_root.rglob("*"):
                self.assertEqual(
                    os.path.commonpath((paths.state_root, path)),
                    str(paths.state_root),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
