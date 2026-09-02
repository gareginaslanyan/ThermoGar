#!/usr/bin/env python3
"""SWR software smoke test for the legacy Kawin KWN adapter.

По умолчанию выполняет очень короткий численный расчёт Ni–Al–Cr / γ′.
Он проверяет интеграцию и структуры результата, но не валидирует параметры
материала и не заменяет длительный контрольный расчёт из интерфейса.
"""
from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import platform
import sys

os.environ.setdefault("MPLBACKEND", "Agg")


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "не установлен"


def find_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
    else:
        candidates = [Path.cwd(), Path(__file__).resolve().parent.parent]
        root = next(
            (candidate.resolve() for candidate in candidates if (candidate / "app").is_dir()),
            Path.cwd().resolve(),
        )
    if not (root / "app").is_dir():
        raise FileNotFoundError(f"В {root} нет папки app.")
    return root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root")
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="проверить импорт и сборку параметров без решения во времени",
    )
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=1.0,
        help="длительность короткого численного теста, с (по умолчанию 1)",
    )
    args = parser.parse_args()

    root = find_root(args.project_root)
    sys.path.insert(0, str(root / "app"))

    print("THERMOGAR SWR — KWN SOFTWARE REGRESSION")
    print("Project:", root)
    print("Python:", platform.python_version(), platform.machine())
    print("pycalphad:", package_version("pycalphad"))
    print("kawin:", package_version("kawin"))

    try:
        from pycalphad import Database
        from kawin.precipitation import (
            MatrixParameters,
            PrecipitateModel,
            PrecipitateParameters,
            TemperatureParameters,
        )
        from kawin.thermo import BinaryThermodynamics, MulticomponentThermodynamics
        from thermogar_precipitation import (
            PRECIPITATION_AVAILABLE,
            PRESET_NI,
            run_precipitation,
        )
    except Exception as error:
        print("IMPORT RESULT: FAILED")
        print(type(error).__name__ + ":", error)
        return 1

    if not PRECIPITATION_AVAILABLE:
        print("IMPORT RESULT: FAILED — precipitation API не доступен")
        return 1

    print("IMPORT RESULT: PASSED")
    print(
        "API:",
        MatrixParameters.__name__,
        PrecipitateParameters.__name__,
        PrecipitateModel.__name__,
        TemperatureParameters.__name__,
        MulticomponentThermodynamics.__name__,
    )

    database_path = (
        root
        / "databases"
        / "converted"
        / "mc_ni_v2036_with_mobility.garcalc.tdb"
    )
    if not database_path.is_file():
        print("DATABASE RESULT: FAILED — файл не найден:", database_path)
        return 1

    try:
        db = Database(str(database_path))
    except Exception as error:
        print("DATABASE RESULT: FAILED")
        print(type(error).__name__ + ":", error)
        return 1

    required_phases = {PRESET_NI["matrix"], PRESET_NI["precipitate"]}
    missing_phases = sorted(required_phases - set(db.phases))
    if missing_phases:
        print("DATABASE RESULT: FAILED — нет фаз:", ", ".join(missing_phases))
        return 1
    print("DATABASE RESULT: PASSED — фаз", len(db.phases))

    if args.setup_only:
        # Собираем те же ключевые объекты, что и интерфейс, без интегрирования.
        therm = MulticomponentThermodynamics(
            str(database_path),
            ["NI", "AL", "CR"],
            [PRESET_NI["matrix"], PRESET_NI["precipitate"]],
        )
        matrix = MatrixParameters(["AL", "CR"])
        matrix.initComposition = [0.098, 0.083]
        matrix.volume.setVolume(PRESET_NI["matrix_vm"] * 1e-6, "VM", 1)
        precipitate = PrecipitateParameters(PRESET_NI["precipitate"])
        precipitate.gamma = PRESET_NI["gamma"]
        precipitate.volume.setVolume(PRESET_NI["precip_vm"] * 1e-6, "VM", 1)
        precipitate.nucleation.setNucleationType("BULK")
        model = PrecipitateModel(
            matrix,
            [precipitate],
            therm,
            TemperatureParameters(PRESET_NI["temperature_c"] + 273.15),
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
        print("SETUP RESULT: PASSED")
        print("RESULT: PASSED")
        return 0

    duration_seconds = max(float(args.duration_seconds), 1e-6)
    try:
        result = run_precipitation(
            db=db,
            database_path=database_path,
            database_label="Никелевые сплавы — mc_ni 2.036",
            database_key="ni",
            balance="NI",
            composition_text=PRESET_NI["composition"],
            units="at",
            matrix_phase=PRESET_NI["matrix"],
            precipitate_phase=PRESET_NI["precipitate"],
            schedule_mode="isothermal",
            temperature_c=PRESET_NI["temperature_c"],
            duration_h=duration_seconds / 3600.0,
            profile_text="",
            gamma=PRESET_NI["gamma"],
            matrix_vm=PRESET_NI["matrix_vm"],
            precip_vm=PRESET_NI["precip_vm"],
            nucleation_type="BULK",
            bulk_n0=PRESET_NI["bulk_n0"],
            grain_size_um=100.0,
            dislocation_density=5e12,
            gb_energy=0.3,
            cmin_nm=0.2,
            cmax_nm=5.0,
            bins=30,
            input_provenance="SYNTHETIC_SOFTWARE_SMOKE_TEST",
            input_confirmation=True,
        )
    except Exception as error:
        print("NUMERIC RESULT: FAILED")
        print(type(error).__name__ + ":", error)
        print("Подсказка: для проверки только API запустите с --setup-only")
        return 1

    checks = {
        "kinetics rows": len(result.kinetics) >= 1,
        "quality rows": len(result.quality) >= 1,
        "all quality passed": bool((result.quality["Статус"] == "пройдена").all()),
        "PSD rows": len(result.psd) >= 1,
        "NPZ nonempty": len(result.npz) > 100,
        "provenance nonempty": len(result.provenance) > 100,
    }
    for label, passed in checks.items():
        print(("PASS" if passed else "FAIL") + ":", label)

    print("Final time, s:", float(result.kinetics["Время, с"].iloc[-1]))
    print(
        "Final volume fraction, %:",
        float(result.kinetics["Объёмная доля, %"].iloc[-1]),
    )
    passed = all(checks.values())
    print("RESULT:", "PASSED" if passed else "FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
