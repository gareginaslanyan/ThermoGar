#!/usr/bin/env python3
"""Проверка параллельного движка в установленной копии ThermoGar.

Установленная программа работает под embeddable-рантаймом: ``python.exe`` без
обычного ``site``, с ``python311._pth`` и с изоляцией от переменных окружения.
``multiprocessing`` там ведёт себя не так, как в venv, поэтому воркеров нужно
поднимать и проверять прямо из установленного каталога, а не только из
репозитория.

Скрипт считает температурный скан Fe на 10 точках тем же движком и тем же
списком фаз, что и раздел «Расчёты», и печатает JSON: сколько воркеров
поднялось, их PID, время последовательного и параллельного счёта и
канонический отпечаток чисел. Отпечатки установленной копии и репозитория
обязаны совпадать — это и есть «числа побайтово те же».

Запуск (установленная копия):

    "C:\\Program Files\\ThermoGar\\runtime\\python.exe" -P -s -B -X utf8 ^
        tools\\installed_parallel_check.py --root "C:\\Program Files\\ThermoGar"

Запуск (репозиторий, для сравнения):

    .venv-windows\\Scripts\\python.exe -X utf8 tools/installed_parallel_check.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


FE_RELATIVE_PATH = (
    "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb"
)
# Состав и сетка релизной матрицы: Fe–0.2C–11.5Cr–0.7Ni, 500…900 °C.
FE_MOLE_FRACTIONS = {
    "C": 0.009157572527802667,
    "CR": 0.1216346874530286,
    "NI": 0.0065593902318969565,
}
COMPONENTS = ["C", "CR", "FE", "NI", "VA"]
# Тот же список, что отдаёт prepare_calculation для этого состава в быстром
# наборе фаз (волна 5A) — снят с работающего приложения.
PHASES = [
    "BCC_B2", "BCC_DISL", "CEMENTITE", "CHI_A12", "EPS_CARB", "ETA",
    "ETA_CARB", "FCC_A1", "GAMMA_PRIME", "HCP_A3", "KSI_FE5C2",
    "LAVES_PHASE", "LIQUID", "M23C6", "M3C2", "M6C", "M7C3", "MU_PHASE_I",
    "SIGMA", "TIB2",
]


def build_points(count: int) -> list[dict[str, object]]:
    start_c, stop_c = 500.0, 900.0
    step = (stop_c - start_c) / (count - 1) if count > 1 else 0.0
    return [
        {
            "N": 1.0,
            "P": 101325.0,
            "T": start_c + step * index + 273.15,
            "X": dict(FE_MOLE_FRACTIONS),
        }
        for index in range(count)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Корень программы: репозиторий или каталог установки.",
    )
    parser.add_argument("--points", type=int, default=10)
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Дополнительно посчитать те же точки без пула, для сравнения.",
    )
    arguments = parser.parse_args()

    root = Path(arguments.root).resolve()
    application = root / "app"
    if str(application) not in sys.path:
        sys.path.insert(0, str(application))

    import thermogar_parallel as parallel

    database_path = (root / FE_RELATIVE_PATH).resolve()
    sha256 = parallel.file_sha256(database_path)
    points = build_points(int(arguments.points))
    workers = parallel.auto_worker_count()

    report: dict[str, object] = {
        "root": str(root),
        "executable": sys.executable,
        "isolated": bool(sys.flags.isolated),
        "ignore_environment": bool(sys.flags.ignore_environment),
        "parent_hash_seed_fixed": parallel.parent_hash_seed_is_fixed(),
        "points": len(points),
        "workers_requested": workers,
    }

    started = time.perf_counter()
    with parallel.ParallelEquilibrium(database_path, sha256, workers=workers) as engine:
        parallel_results = engine.map_points(
            points, COMPONENTS, PHASES, pdens=500, capture=("X",)
        )
        report["worker_pids"] = engine.worker_pids()
        report["workers_started"] = len(engine.worker_pids())
    report["parallel_seconds"] = round(time.perf_counter() - started, 2)
    report["worker_hash_seed_effective"] = parallel.hash_seed_is_effective()
    report["failed_points"] = [
        {"index": item.index, "error": item.error}
        for item in parallel_results
        if not item.ok
    ]
    report["parallel_digest"] = parallel.canonical_digest(parallel_results)

    if arguments.sequential:
        database = parallel.load_database(database_path, sha256)
        started = time.perf_counter()
        sequential_results = parallel.solve_points_in_process(
            database, points, COMPONENTS, PHASES, pdens=500, capture=("X",)
        )
        report["sequential_seconds"] = round(time.perf_counter() - started, 2)
        report["sequential_digest"] = parallel.canonical_digest(sequential_results)
        report["digests_match"] = (
            report["sequential_digest"] == report["parallel_digest"]
        )

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not report["failed_points"] else 1


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    raise SystemExit(main())
