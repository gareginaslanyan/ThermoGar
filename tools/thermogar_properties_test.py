#!/usr/bin/env python3
"""ThermoGar SWR — software regressions for transparent property equations."""

from __future__ import annotations

import atexit
from pathlib import Path
import argparse
import json
import math
import os
import sys
import tempfile


_PROCESS_TEMPORARY = tempfile.TemporaryDirectory(
    prefix="thermogar-properties-test-"
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

import numpy as np

os.environ.setdefault("MPLBACKEND", "Agg")


def assert_close(label: str, actual: float, expected: float, tolerance: float) -> None:
    difference = abs(float(actual) - float(expected))
    if difference > tolerance:
        raise AssertionError(
            f"{label}: actual={actual}, expected={expected}, difference={difference}"
        )
    print(f"PASS: {label}: {actual:.10g}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        default=None,
    )
    args = parser.parse_args()

    project_root = (
        Path(args.project_root).expanduser().resolve()
        if args.project_root
        else Path(__file__).resolve().parent.parent
    )
    app_dir = project_root / "app"
    if not app_dir.is_dir():
        # Allow testing from an extracted bundle.
        app_dir = Path(__file__).resolve().parent.parent / "app"
    sys.path.insert(0, str(app_dir))

    # The shipped test normally runs inside ThermoGar's .venv, where
    # Streamlit and pycalphad are installed. The lightweight bundle audit
    # may run in a build container without those UI packages; pure formula
    # tests only need import-compatible stubs.
    try:
        import streamlit  # noqa: F401
    except ModuleNotFoundError:
        import types
        sys.modules["streamlit"] = types.ModuleType("streamlit")

    try:
        import pycalphad  # noqa: F401
    except ModuleNotFoundError:
        import types
        dummy_pycalphad = types.ModuleType("pycalphad")
        dummy_pycalphad.equilibrium = lambda *args, **kwargs: None
        dummy_pycalphad.variables = types.SimpleNamespace()
        sys.modules["pycalphad"] = dummy_pycalphad

    from thermogar_properties import (
        calculate_strengthening,
        empty_elastic_library,
        hall_petch_contribution,
        load_elastic_library,
        moduli_from_e_nu,
        moduli_from_k_g,
        save_elastic_library,
        taylor_contribution,
        vrh_homogenization,
    )
    from thermogar_paths import ThermoGarPaths

    print("THERMOGAR SWR — PROPERTIES SOFTWARE REGRESSION")
    print("App:", app_dir)
    print()

    elastic = moduli_from_e_nu(200.0, 0.30)
    assert_close("E→K", elastic.bulk_gpa, 166.6666666667, 1e-8)
    assert_close("E→G", elastic.shear_gpa, 76.9230769231, 1e-8)

    restored = moduli_from_k_g(elastic.bulk_gpa, elastic.shear_gpa)
    assert_close("K/G→E", restored.young_gpa, 200.0, 1e-8)
    assert_close("K/G→nu", restored.poisson, 0.30, 1e-10)

    bounds, summary = vrh_homogenization(
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
    assert_close("K_Voigt", summary["K_Voigt_GPa"], 150.0, 1e-10)
    assert_close("K_Reuss", summary["K_Reuss_GPa"], 133.3333333333, 1e-8)
    assert_close("K_Hill", summary["K_Hill_GPa"], 141.6666666667, 1e-8)
    assert_close("G_Voigt", summary["G_Voigt_GPa"], 75.0, 1e-10)
    assert_close("G_Reuss", summary["G_Reuss_GPa"], 66.6666666667, 1e-8)
    assert_close("G_Hill", summary["G_Hill_GPa"], 70.8333333333, 1e-8)
    if list(bounds["Метод"]) != [
        "Reuss — нижняя граница",
        "Hill — средняя VRH",
        "Voigt — верхняя граница",
    ]:
        raise AssertionError("Unexpected VRH table order")
    print("PASS: VRH table order")

    hp = hall_petch_contribution(0.70, 20.0)
    assert_close("Hall–Petch educational example", hp, 156.52475842499, 1e-6)

    taylor = taylor_contribution(3.06, 0.30, 80.0, 0.248, 1e13)
    assert_close("Taylor educational example", taylor, 57.59494249796592, 1e-6)

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
    expected_total = 50.0 + hp + taylor
    assert_close("Educational strengthening total", strength.total_mpa, expected_total, 1e-6)
    if strength.input_provenance != "SYNTHETIC_SOFTWARE_REGRESSION":
        raise AssertionError("Strengthening provenance was not retained")
    if strength.input_confirmation is not True:
        raise AssertionError("Strengthening confirmation was not retained")
    print("PASS: strengthening provenance retained")

    # Round-trip local library without touching installation/legacy state.
    install_elastic = (
        project_root
        / "user_data"
        / "properties"
        / "elastic_phase_properties.json"
    )
    install_elastic_before = (
        install_elastic.read_bytes() if install_elastic.is_file() else None
    )
    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary)
        paths = ThermoGarPaths(temporary_root / "profile")
        paths.configure_process_environment()
        library = empty_elastic_library()
        library["entries"]["ni::FCC_A1"] = {
            "database_key": "ni",
            "phase": "FCC_A1",
            "young_gpa": 200.0,
            "poisson": 0.30,
            "source": "test",
        }
        destination = save_elastic_library(paths, library)
        loaded = load_elastic_library(paths)
        if loaded["entries"]["ni::FCC_A1"]["young_gpa"] != 200.0:
            raise AssertionError("Elastic library round-trip failed")
        if not destination.is_file():
            raise AssertionError("Elastic library file was not created")
        if destination != paths.elastic_properties_path:
            raise AssertionError(f"Unexpected elastic profile path: {destination}")
        if (temporary_root / "user_data").exists():
            raise AssertionError("Obsolete user_data path was created")
        install_elastic_after = (
            install_elastic.read_bytes() if install_elastic.is_file() else None
        )
        if install_elastic_after != install_elastic_before:
            raise AssertionError("Install-root elastic state changed")
        print("PASS: elastic library round-trip")

    print()
    print("RESULT: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
