from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

from thermogar_paths import ThermoGarPathError, ThermoGarPaths


class ThermoGarPathsTests(unittest.TestCase):
    def test_001_exact_injected_layout_and_immutable_public_contract(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / "profile"
            paths = ThermoGarPaths(root)
            expected = {
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
            self.assertEqual(
                {name: getattr(paths, name) for name in expected},
                expected,
            )
            for value in expected.values():
                self.assertEqual(os.path.commonpath((root, value)), str(root))
            with self.assertRaises(FrozenInstanceError):
                paths.state_root = root / "other"  # type: ignore[misc]
            self.assertFalse(hasattr(paths, "run_root"))
            self.assertFalse(hasattr(paths, "pycache_root"))

    def test_002_production_resolution_is_one_root_for_ni_al_and_steel(self):
        with TemporaryDirectory() as temporary:
            local = Path(temporary) / "LocalAppData"
            with mock.patch.dict(
                os.environ,
                {"LOCALAPPDATA": str(local)},
                clear=True,
            ):
                resolved = {key: ThermoGarPaths() for key in ("ni", "al", "fe")}
            self.assertEqual(
                {value.state_root for value in resolved.values()},
                {local / "ThermoGar"},
            )
            self.assertEqual(
                {value.workspace_root for value in resolved.values()},
                {local / "ThermoGar" / "workspace"},
            )

            explicit = Path(temporary) / "explicit"
            with mock.patch.dict(
                os.environ,
                {
                    "LOCALAPPDATA": str(local),
                    "THERMOGAR_STATE_ROOT": str(explicit),
                },
                clear=True,
            ):
                self.assertEqual(ThermoGarPaths().state_root, explicit)

    def test_003_relative_or_reparse_root_is_rejected(self):
        with self.assertRaises(ThermoGarPathError):
            ThermoGarPaths("relative/profile")
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(strict=True)
            target = root / "target"
            target.mkdir()
            sentinel = target / "junction-target-sentinel.txt"
            sentinel.write_bytes(b"junction target must survive cleanup\n")
            link = root / "profile-link"

            resolved_target = target.resolve(strict=True)
            resolved_target_parent = target.parent.resolve(strict=True)
            resolved_link_parent = link.parent.resolve(strict=True)
            for candidate in (
                resolved_target,
                resolved_target_parent,
                resolved_link_parent,
            ):
                self.assertEqual(
                    os.path.commonpath((str(root), str(candidate))),
                    str(root),
                )

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
                    self.fail(
                        "junction fixture creation failed: "
                        f"exit={completed.returncode}; "
                        f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
                    )
                attributes = link.lstat().st_file_attributes
                created_reparse = bool(
                    attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
                )
                if not created_reparse:
                    self.fail(
                        "junction fixture lacks FILE_ATTRIBUTE_REPARSE_POINT"
                    )
                self.assertEqual(link.resolve(strict=True), resolved_target)

                paths = ThermoGarPaths(link)
                with self.assertRaises(ThermoGarPathError):
                    paths.configure_process_environment()
            finally:
                if created_reparse:
                    os.rmdir(link)
            self.assertFalse(link.exists())
            self.assertEqual(
                sentinel.read_bytes(),
                b"junction target must survive cleanup\n",
            )

    def test_004_environment_is_exact_and_bootstrapped_before_heavy_imports(self):
        source = (APP / "ThermoGar_app.py").read_text(encoding="utf-8")
        heavy_offsets = [
            source.index("import matplotlib.pyplot"),
            source.index("import streamlit"),
            source.index("from pycalphad import"),
        ]
        boundary = min(heavy_offsets)
        prefix = source[:boundary]
        self.assertIn("from thermogar_paths import", prefix)
        self.assertIn(".configure_process_environment()", prefix)
        self.assertNotIn("PYTHONPYCACHEPREFIX", source)

        with TemporaryDirectory() as temporary:
            profile = Path(temporary) / "profile"
            environment = {
                "THERMOGAR_STATE_ROOT": str(profile),
                "LOCALAPPDATA": str(Path(temporary) / "unused"),
            }
            with mock.patch.dict(os.environ, environment, clear=True):
                namespace: dict[str, object] = {}
                exec(compile(prefix, "ThermoGar_app.bootstrap", "exec"), namespace)
                captured = {
                    name: os.environ.get(name)
                    for name in ("THERMOGAR_STATE_ROOT", "MPLCONFIGDIR", "TMP", "TEMP")
                }
            self.assertEqual(
                captured,
                {
                    "THERMOGAR_STATE_ROOT": str(profile),
                    "MPLCONFIGDIR": str(profile / "runtime" / "matplotlib"),
                    "TMP": str(profile / "runtime" / "tmp"),
                    "TEMP": str(profile / "runtime" / "tmp"),
                },
            )
            self.assertTrue((profile / "workspace" / "projects").is_dir())
            self.assertTrue((profile / "properties").is_dir())
            self.assertTrue((profile / "logs" / "stage14").is_dir())

    def test_005_module_is_stdlib_only_and_minus_b_creates_no_bytecode(self):
        module_path = APP / "thermogar_paths.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertTrue(imported <= set(sys.stdlib_module_names), imported)
        scoped_prefixes = (
            "thermogar_paths.",
            "thermogar_workspace.",
            "thermogar_properties.",
            "thermogar_stage14.",
            "ThermoGar_app.",
        )
        scoped_bytecode = [
            path
            for path in (APP / "__pycache__").glob("*.pyc")
            if path.name.startswith(scoped_prefixes)
        ]
        self.assertEqual(scoped_bytecode, [])
        with TemporaryDirectory() as temporary:
            paths = ThermoGarPaths(Path(temporary) / "profile")
            paths.configure_process_environment()
            self.assertEqual(list(paths.state_root.rglob("*.pyc")), [])

    def test_006_exact_official_venv_interpreter_identity(self):
        self.assertEqual(sys.version_info[:3], (3, 11, 9))
        self.assertEqual(platform.architecture()[0], "64bit")
        expected = ROOT / ".venv-windows" / "Scripts" / "python.exe"
        self.assertEqual(
            os.path.normcase(os.path.abspath(sys.executable)),
            os.path.normcase(os.path.abspath(expected)),
        )
        print("INTERPRETER_EXECUTABLE:", sys.executable)
        print("INTERPRETER_VERSION:", sys.version)
        print("INTERPRETER_ARCHITECTURE:", platform.architecture()[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
