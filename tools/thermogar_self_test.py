#!/usr/bin/env python3
"""Самопроверка ThermoGar SWR без запуска Streamlit.

Примеры:
    python tools/thermogar_self_test.py
    python tools/thermogar_self_test.py --project-root /Volumes/Disk/Pet/ThermoGar
    python tools/thermogar_self_test.py --json results/self_test.json
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import hashlib
import json
import os
import platform
import sys
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np
from pycalphad import Database, equilibrium, variables as v
from pycalphad.core.utils import filter_phases, unpack_species


DATABASES = {
    "ni": {
        "label": "Никелевые сплавы",
        "relative_path": (
            "databases/converted/"
            "mc_ni_v2036_with_mobility.garcalc.tdb"
        ),
        "expected_phases": 99,
    },
    "al": {
        "label": "Алюминиевые сплавы",
        "relative_path": (
            "databases/converted/al/"
            "mc_al_v2037_with_mobility.thermogar.tdb"
        ),
        "expected_phases": 195,
    },
}


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "не установлен"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if (root / "databases").exists():
            return root
        raise FileNotFoundError(f"В {root} нет папки databases.")

    candidates = [Path.cwd(), Path.cwd().parent, Path(__file__).resolve().parent.parent]
    for candidate in candidates:
        if (candidate / "databases").exists():
            return candidate.resolve()
    raise FileNotFoundError(
        "Не удалось найти корень ThermoGar. Запустите скрипт из папки проекта "
        "или передайте --project-root."
    )


def stable_phases(
    db: Database,
    components: list[str],
    conditions: dict[Any, float],
    excluded: set[str] | None = None,
) -> tuple[dict[str, float], float]:
    phases = filter_phases(db, unpack_species(db, components))
    if excluded:
        phases = [phase for phase in phases if phase not in excluded]

    eq = equilibrium(
        db,
        components,
        phases,
        conditions,
        calc_opts={"pdens": 300},
    )

    names = np.asarray(eq.Phase.values, dtype=str).ravel()
    fractions = np.asarray(eq.NP.values, dtype=float).ravel()
    result: dict[str, float] = {}
    for name, fraction in zip(names, fractions):
        if name and np.isfinite(fraction) and fraction > 1e-9:
            result[str(name)] = result.get(str(name), 0.0) + float(fraction)
    return result, float(sum(result.values()))


def run(root: Path) -> dict[str, Any]:
    sys.path.insert(0, str(root / "app"))
    from thermogar_release_policy import (
        release_status,
        research_result_evidence,
    )

    report: dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "project_root": ".",
        "release_status": release_status(),
        "environment": {
            "python": platform.python_version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
            "packages": {
                name: package_version(name)
                for name in (
                    "pycalphad",
                    "streamlit",
                    "scheil",
                    "kawin",
                    "numpy",
                    "scipy",
                    "pandas",
                    "matplotlib",
                    "xarray",
                    "openpyxl",
                )
            },
        },
        "files": [],
        "databases": [],
        "calculations": [],
        "physical_database": {},
        "properties": {},
        "diffusion": {},
        "precipitation": {},
        "fe_database_guard": {},
        "passed": True,
    }

    required_files = [
        "app/ThermoGar_app.py",
        "app/thermogar_stage14.py",
        "app/thermogar_properties.py",
        "app/thermogar_diffusion.py",
        "app/thermogar_precipitation.py",
        "app/thermogar_database_guard.py",
        "app/thermogar_physical.py",
        "app/thermogar_workspace.py",
        "app/thermogar_palette.py",
        "app/thermogar_release_policy.py",
        "app/thermogar_release_ui.py",
        "app/thermogar_ne04_domain.py",
        "app/style.css",
        ".streamlit/config.toml",
        "configs/ne04_database_domains.json",
        "databases/physical/original/physical_data_v103.pdb",
    ]

    for relative in required_files:
        path = root / relative
        passed = path.exists() and path.stat().st_size > 0
        report["files"].append(
            {
                "file": relative,
                "exists": path.exists(),
                "size": path.stat().st_size if path.exists() else 0,
                "passed": passed,
            }
        )
        report["passed"] = report["passed"] and passed

    loaded: dict[str, Database] = {}
    for key, definition in DATABASES.items():
        path = root / definition["relative_path"]
        row: dict[str, Any] = {
            "key": key,
            "label": definition["label"],
            "file": definition["relative_path"],
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else 0,
            "sha256": file_sha256(path) if path.exists() else "",
            "elements": None,
            "phases": None,
            "expected_phases": definition["expected_phases"],
            "release_disposition": "RUNTIME_CANDIDATE_PENDING_NE04",
            "passed": False,
            "error": "",
        }
        try:
            db = Database(str(path))
            loaded[key] = db
            row["elements"] = len(db.elements) - (1 if "VA" in db.elements else 0)
            row["phases"] = len(db.phases)
            row["passed"] = row["phases"] == definition["expected_phases"]
        except Exception as error:
            row["error"] = f"{type(error).__name__}: {error}"
        report["databases"].append(row)
        report["passed"] = report["passed"] and bool(row["passed"])

    fe_guard_row: dict[str, Any] = {
        "release_disposition": "DISABLED_DIAGNOSTIC_ONLY_NOT_RELEASE_BASELINE",
        "working_exact_parameter_count": 0,
        "upstream_exact_parameter_count": 0,
        "upstream_profile_exists": False,
        "manifest_exists": False,
        "patch_id": "",
        "passed": False,
        "error": "",
    }
    try:
        sys.path.insert(0, str(root / "app"))
        from thermogar_database_guard import (
            FE_PATCH_ID,
            FE_PROFILE_CANONICAL,
            FE_PROFILE_EXPERIMENTAL,
            compatibility_patch_record,
            fe_database_path,
            find_exact_suspect_commands,
            load_profile_manifest,
        )

        working_path = fe_database_path(root, FE_PROFILE_CANONICAL)
        upstream_path = fe_database_path(root, FE_PROFILE_EXPERIMENTAL)
        fe_guard_row["working_exact_parameter_count"] = len(
            find_exact_suspect_commands(working_path)
        )
        fe_guard_row["upstream_profile_exists"] = upstream_path.is_file()
        fe_guard_row["upstream_exact_parameter_count"] = len(
            find_exact_suspect_commands(upstream_path)
        )
        fe_guard_row["manifest_exists"] = load_profile_manifest(root) is not None
        patch = compatibility_patch_record(root) or {}
        fe_guard_row["patch_id"] = str(patch.get("patch_id", ""))
        fe_guard_row["passed"] = bool(
            fe_guard_row["working_exact_parameter_count"] == 0
            and fe_guard_row["upstream_profile_exists"]
            and fe_guard_row["upstream_exact_parameter_count"] == 1
            and fe_guard_row["manifest_exists"]
            and fe_guard_row["patch_id"] == FE_PATCH_ID
        )
    except Exception as error:
        fe_guard_row["error"] = f"{type(error).__name__}: {error}"

    report["fe_database_guard"] = fe_guard_row
    report["passed"] = report["passed"] and bool(fe_guard_row["passed"])

    cases: list[dict[str, Any]] = []
    if "ni" in loaded:
        cases.append(
            {
                "name": "Ni–15 ат.% Al, 700 °C",
                "db": loaded["ni"],
                "components": ["AL", "NI", "VA"],
                "conditions": {
                    v.N: 1.0,
                    v.P: 101325.0,
                    v.T: 973.15,
                    v.X("AL"): 0.15,
                },
                "expected": {"FCC_A1", "GAMMA_PRIME"},
                "excluded": set(),
            }
        )
    if "al" in loaded:
        cases.append(
            {
                "name": "Al–4 ат.% Cu, 500 °C",
                "db": loaded["al"],
                "components": ["AL", "CU", "VA"],
                "conditions": {
                    v.N: 1.0,
                    v.P: 101325.0,
                    v.T: 773.15,
                    v.X("CU"): 0.04,
                },
                "expected": {"GP_MAT", "THETA_AL2CU"},
                "excluded": set(),
            }
        )

    for case in cases:
        row: dict[str, Any] = {
            "name": case["name"],
            "stable_phases": [],
            "expected_phases": sorted(case["expected"]),
            "fraction_sum": None,
            "passed": False,
            "error": "",
        }
        try:
            fractions, fraction_sum = stable_phases(
                case["db"],
                case["components"],
                case["conditions"],
                excluded=case["excluded"],
            )
            row["stable_phases"] = sorted(fractions)
            row["fraction_sum"] = fraction_sum
            row["passed"] = (
                case["expected"].issubset(set(fractions))
                and abs(fraction_sum - 1.0) <= 1e-6
            )
        except Exception as error:
            row["error"] = f"{type(error).__name__}: {error}"
        report["calculations"].append(row)
        report["passed"] = report["passed"] and bool(row["passed"])

    physical_path = root / "databases/physical/original/physical_data_v103.pdb"
    physical_row: dict[str, Any] = {
        "file": "databases/physical/original/physical_data_v103.pdb",
        "exists": physical_path.exists(),
        "sha256": file_sha256(physical_path) if physical_path.exists() else "",
        "functions": None,
        "parameters": None,
        "parser_checks_passed": False,
        "integrated_density_kg_m3": None,
        "integrated_coverage_pct": None,
        "passed": False,
        "error": "",
    }
    try:
        sys.path.insert(0, str(root / "app"))
        from thermogar_physical import (
            PhysicalDensityDatabase,
            calculate_physical_properties,
        )

        physical_db = PhysicalDensityDatabase(physical_path)
        checks = physical_db.self_test()
        physical_row["functions"] = len(physical_db.functions)
        physical_row["parameters"] = len(physical_db.parameters)
        physical_row["parser_checks_passed"] = bool(
            (checks["Статус"] == "пройдена").all()
        )

        density_ok = False
        if "al" in loaded:
            al_db = loaded["al"]
            components = ["AL", "VA"]
            phases = filter_phases(al_db, unpack_species(al_db, components))
            eq = equilibrium(
                al_db,
                components,
                phases,
                {v.N: 1.0, v.P: 101325.0, v.T: 773.15},
                calc_opts={"pdens": 300},
            )
            physical_result = calculate_physical_properties(
                al_db,
                eq,
                components,
                773.15,
                physical_db,
            )
            physical_row["integrated_density_kg_m3"] = (
                physical_result.alloy_density_kg_m3
            )
            physical_row["integrated_coverage_pct"] = (
                physical_result.mole_coverage_pct
            )
            density_ok = (
                physical_result.alloy_density_kg_m3 is not None
                and 2300.0 < physical_result.alloy_density_kg_m3 < 2900.0
                and physical_result.mole_coverage_pct > 99.9
            )

        physical_row["passed"] = bool(
            physical_row["parser_checks_passed"] and density_ok
        )
    except Exception as error:
        physical_row["error"] = f"{type(error).__name__}: {error}"

    report["physical_database"] = physical_row
    report["passed"] = report["passed"] and bool(physical_row["passed"])

    properties_row: dict[str, Any] = {
        "elastic_conversion_passed": False,
        "vrh_passed": False,
        "strengthening_passed": False,
        "E_Hill_GPa": None,
        "educational_total_MPa": None,
        "passed": False,
        "error": "",
    }
    try:
        sys.path.insert(0, str(root / "app"))
        from thermogar_properties import (
            calculate_strengthening,
            moduli_from_e_nu,
            moduli_from_k_g,
            vrh_homogenization,
        )

        elastic = moduli_from_e_nu(200.0, 0.30)
        restored = moduli_from_k_g(elastic.bulk_gpa, elastic.shear_gpa)
        properties_row["elastic_conversion_passed"] = bool(
            abs(elastic.bulk_gpa - 166.6666666667) <= 1e-8
            and abs(elastic.shear_gpa - 76.9230769231) <= 1e-8
            and abs(restored.young_gpa - 200.0) <= 1e-8
            and abs(restored.poisson - 0.30) <= 1e-10
        )

        _bounds, summary = vrh_homogenization(
            [
                {
                    "phase": "A",
                    "volume_fraction": 0.5,
                    "bulk_gpa": 100.0,
                    "shear_gpa": 50.0,
                },
                {
                    "phase": "B",
                    "volume_fraction": 0.5,
                    "bulk_gpa": 200.0,
                    "shear_gpa": 100.0,
                },
            ]
        )
        properties_row["E_Hill_GPa"] = summary["E_Hill_GPa"]
        properties_row["vrh_passed"] = bool(
            abs(summary["K_Hill_GPa"] - 141.6666666667) <= 1e-8
            and abs(summary["G_Hill_GPa"] - 70.8333333333) <= 1e-8
        )

        strength = calculate_strengthening(
            input_provenance="SYNTHETIC_SOFTWARE_REGRESSION",
            input_confirmation=True,
            sigma_internal_mpa=50.0,
            hall_petch={
                "k_y_mpa_sqrt_m": 0.70,
                "grain_size_um": 20.0,
            },
            taylor={
                "taylor_factor": 3.06,
                "alpha": 0.30,
                "shear_gpa": 80.0,
                "burgers_nm": 0.248,
                "dislocation_density_m2": 1e13,
            },
            solid_solution_mpa=None,
            orowan=None,
            other_mpa=None,
            summation_rule="Линейная сумма",
        )
        properties_row["educational_total_MPa"] = strength.total_mpa
        properties_row["strengthening_passed"] = bool(
            strength.total_mpa is not None
            and abs(strength.total_mpa - 264.11970092296) <= 1e-6
        )
        properties_row["passed"] = bool(
            properties_row["elastic_conversion_passed"]
            and properties_row["vrh_passed"]
            and properties_row["strengthening_passed"]
        )
    except Exception as error:
        properties_row["error"] = f"{type(error).__name__}: {error}"

    report["properties"] = properties_row
    report["passed"] = report["passed"] and bool(properties_row["passed"])

    diffusion_row: dict[str, Any] = {
        "kawin_version": package_version("kawin"),
        "database": "ni",
        "phase": "FCC_A1",
        "nodes": 20,
        "requested_time_s": 3.6,
        "actual_time_s": None,
        "composition_sum_error": None,
        "mass_conservation_error": None,
        "database_sha256": "",
        "input_provenance": "",
        "input_confirmation": False,
        "result_scope": "",
        "passed": False,
        "error": "",
    }
    try:
        if diffusion_row["kawin_version"] == "не установлен":
            raise RuntimeError("kawin не установлен")
        if "ni" not in loaded:
            raise RuntimeError("Ni-база не загружена")

        sys.path.insert(0, str(root / "app"))
        import matplotlib.pyplot as plt
        from thermogar_diffusion import run_diffusion

        ni_path = root / DATABASES["ni"]["relative_path"]
        diffusion_result = run_diffusion(
            db=loaded["ni"],
            database_key="ni",
            database_path=ni_path,
            database_label="Никелевые сплавы — mc_ni 2.036",
            balance="NI",
            units="at",
            left_text="AL=5",
            right_text="AL=15",
            temperature_c=1000.0,
            time_h=0.001,
            length_um=100.0,
            interface_percent=50.0,
            nodes=20,
            phases=["FCC_A1"],
            model_kind="single",
            input_provenance="SYNTHETIC_SOFTWARE_SELF_TEST_NOT_MATERIAL_INPUT",
            input_confirmation=True,
        )
        diffusion_row["actual_time_s"] = float(diffusion_result.actual_time_s)
        quality = diffusion_result.quality.set_index("Проверка")
        diffusion_row["composition_sum_error"] = float(
            quality.loc["Сумма состава в каждом узле", "Значение"]
        )
        diffusion_row["mass_conservation_error"] = float(
            quality.loc["Сохранение среднего состава", "Значение"]
        )
        diffusion_row["database_sha256"] = diffusion_result.database_sha256
        diffusion_row["input_provenance"] = diffusion_result.input_provenance
        diffusion_row["input_confirmation"] = diffusion_result.input_confirmation
        diffusion_row["result_scope"] = diffusion_result.provenance["result_scope"]
        diffusion_row["passed"] = bool(
            (diffusion_result.quality["Статус"] == "пройдена").all()
            and abs(diffusion_row["actual_time_s"] - 3.6) <= 1e-4
            and diffusion_result.database_key == "ni"
            and diffusion_result.database_sha256 == file_sha256(ni_path)
            and diffusion_result.input_provenance
            == "SYNTHETIC_SOFTWARE_SELF_TEST_NOT_MATERIAL_INPUT"
            and diffusion_result.input_confirmation is True
            and diffusion_result.provenance["release_status"]["production_use"]
            == "DENIED"
            and diffusion_result.provenance["result_scope"]
            == "SOFTWARE_MODEL_OUTPUT_NOT_EXPERIMENTAL_VALIDATION_OR_MATERIAL_QUALIFICATION"
        )
        plt.close(diffusion_result.profile_figure)
        if diffusion_result.phase_figure is not None:
            plt.close(diffusion_result.phase_figure)
    except Exception as error:
        diffusion_row["error"] = f"{type(error).__name__}: {error}"

    report["diffusion"] = diffusion_row
    report["passed"] = report["passed"] and bool(diffusion_row["passed"])

    precipitation_row: dict[str, Any] = {
        "kawin_version": package_version("kawin"),
        "database": "ni",
        "matrix": "FCC_A1",
        "precipitate": "GAMMA_PRIME",
        "setup_passed": False,
        "passed": False,
        "error": "",
    }
    try:
        if precipitation_row["kawin_version"] == "не установлен":
            raise RuntimeError("kawin не установлен")
        if "ni" not in loaded:
            raise RuntimeError("Ni-база не загружена")

        sys.path.insert(0, str(root / "app"))
        from kawin.precipitation import (
            MatrixParameters,
            PrecipitateModel,
            PrecipitateParameters,
            TemperatureParameters,
        )
        from kawin.thermo import BinaryThermodynamics, MulticomponentThermodynamics
        from thermogar_precipitation import PRECIPITATION_AVAILABLE

        if not PRECIPITATION_AVAILABLE:
            raise RuntimeError("Kawin precipitation API не импортирован")

        ni_path = root / DATABASES["ni"]["relative_path"]
        therm = MulticomponentThermodynamics(
            str(ni_path),
            ["NI", "AL", "CR"],
            ["FCC_A1", "GAMMA_PRIME"],
        )
        matrix = MatrixParameters(["AL", "CR"])
        matrix.initComposition = np.asarray([0.098, 0.083], dtype=float)
        matrix.volume.setVolume(6.5662724928e-6, "VM", 1)
        matrix.nucleationSites.setNucleationDensity(
            grainSize=100.0,
            aspectRatio=1.0,
            dislocationDensity=5e12,
            bulkN0=1e30,
        )
        precipitate = PrecipitateParameters("GAMMA_PRIME")
        precipitate.gamma = 0.023
        precipitate.volume.setVolume(6.5662724928e-6, "VM", 1)
        precipitate.nucleation.setNucleationType("BULK")
        model = PrecipitateModel(
            matrix,
            [precipitate],
            therm,
            TemperatureParameters(1073.15),
        )
        model.setPBMParameters(
            cMin=0.2e-9,
            cMax=5e-9,
            bins=30,
            minBins=20,
            maxBins=60,
            adaptive=True,
        )
        model.setup()
        precipitation_row["setup_passed"] = bool(
            model.data.composition.shape == (1, 2)
            and np.allclose(model.data.composition[0], [0.098, 0.083])
        )
        precipitation_row["passed"] = precipitation_row["setup_passed"]
    except Exception as error:
        precipitation_row["error"] = f"{type(error).__name__}: {error}"

    report["precipitation"] = precipitation_row
    report["passed"] = report["passed"] and bool(precipitation_row["passed"])

    report["evidence_labels"] = research_result_evidence(
        execution_succeeded=bool(report["passed"]),
        software_diagnostic=True,
    )
    if report["passed"]:
        report["evidence_labels"]["claim_level"] = (
            "SOFTWARE_SELF_TEST_PASSED_NOT_RELEASE_ACCEPTANCE"
        )
    return report


def print_report(report: dict[str, Any]) -> None:
    print("=" * 78)
    print("THERMOGAR SWR · NE-02 — SOFTWARE SELF TEST")
    print("=" * 78)
    print("Project:", report["project_root"])
    print("Python:", report["environment"]["python"])
    print("Platform:", report["environment"]["platform"])
    print("Release class:", report["release_status"]["release_class"])
    print("Production use:", report["release_status"]["production_use"])
    print()

    print("FILES")
    for row in report["files"]:
        print("  ", "PASS" if row["passed"] else "FAIL", row["file"])

    print("\nDATABASES")
    for row in report["databases"]:
        print(
            "  ",
            "PASS" if row["passed"] else "FAIL",
            row["label"],
            f"phases={row['phases']} expected={row['expected_phases']}",
        )
        if row["error"]:
            print("      ", row["error"])

    print("\nCALCULATIONS")
    for row in report["calculations"]:
        print(
            "  ",
            "PASS" if row["passed"] else "FAIL",
            row["name"],
            "phases=",
            ", ".join(row["stable_phases"]),
            "sum=",
            row["fraction_sum"],
        )
        if row["error"]:
            print("      ", row["error"])

    physical = report.get("physical_database", {})
    print("\nPHYSICAL DATABASE")
    print(
        "  ",
        "PASS" if physical.get("passed") else "FAIL",
        f"functions={physical.get('functions')}",
        f"parameters={physical.get('parameters')}",
        f"density={physical.get('integrated_density_kg_m3')}",
        f"coverage={physical.get('integrated_coverage_pct')}",
    )
    if physical.get("error"):
        print("      ", physical["error"])

    properties = report.get("properties", {})
    print("\nPROPERTIES")
    print(
        "  ",
        "PASS" if properties.get("passed") else "FAIL",
        f"elastic={properties.get('elastic_conversion_passed')}",
        f"vrh={properties.get('vrh_passed')}",
        f"strengthening={properties.get('strengthening_passed')}",
        f"E_Hill={properties.get('E_Hill_GPa')}",
        f"educational_total={properties.get('educational_total_MPa')}",
    )
    if properties.get("error"):
        print("      ", properties["error"])

    diffusion = report.get("diffusion", {})
    print("\nDIFFUSION")
    print(
        "  ",
        "PASS" if diffusion.get("passed") else "FAIL",
        f"kawin={diffusion.get('kawin_version')}",
        f"phase={diffusion.get('phase')}",
        f"time={diffusion.get('actual_time_s')}",
        f"mass_error={diffusion.get('mass_conservation_error')}",
    )
    if diffusion.get("error"):
        print("      ", diffusion["error"])

    fe_guard = report.get("fe_database_guard", {})
    print()
    print("Fe database guard — DIAGNOSTIC ONLY, NEVER A RELEASE BASELINE:")
    print(
        "  working exact parameter:",
        fe_guard.get("working_exact_parameter_count"),
        "upstream exact parameter:",
        fe_guard.get("upstream_exact_parameter_count"),
        "upstream profile:",
        fe_guard.get("upstream_profile_exists"),
        "passport:",
        fe_guard.get("manifest_exists"),
        "STRUCTURE_OK" if fe_guard.get("passed") else "DIAGNOSTIC_INCOMPLETE",
    )
    if fe_guard.get("error"):
        print("  error:", fe_guard["error"])

    precipitation = report.get("precipitation", {})
    print("\nPRECIPITATION")
    print(
        "  ",
        "PASS" if precipitation.get("passed") else "FAIL",
        f"kawin={precipitation.get('kawin_version')}",
        f"matrix={precipitation.get('matrix')}",
        f"precipitate={precipitation.get('precipitate')}",
        f"setup={precipitation.get('setup_passed')}",
    )
    if precipitation.get("error"):
        print("      ", precipitation["error"])

    print("\n" + "=" * 78)
    print(
        "RESULT:",
        (
            "SOFTWARE REGRESSION PASSED — NOT MATERIAL QUALIFICATION"
            if report["passed"]
            else "SOFTWARE REGRESSION FAILED"
        ),
    )
    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root")
    parser.add_argument("--json")
    args = parser.parse_args()

    root = find_root(args.project_root)
    report = run(root)
    print_report(report)

    if args.json:
        destination = Path(args.json).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print("JSON:", destination)

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
