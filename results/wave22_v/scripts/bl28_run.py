#!/usr/bin/env python3
"""22-В, шаг 1 (BL-28): ячейка «KWN (модуль)» test_kwn_module на коде любого коммита.

Вызов run_precipitation — тот же, что в tools/test_backend_calculations.py::test_kwn_module
того дерева, которое передано в --tree (CASES и database_path берутся из самого дерева):
1 с модельного времени, BULK, bulk_n0 1e30, 30 классов, сетка case.kwn_size_nm.

Дополнительно (не меняя вызов) пишется ряд кинетики CSV и сводка JSON: строк кинетики,
итоговые доля / средний радиус / плотность частиц, шаги решателя, стена, пик памяти.

Запуск:
    PYTHONHASHSEED=0 python -B bl28_run.py --tree <дерево> --db ni --tag 1c47789 --out <каталог>
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import resource
import sys
import time
from pathlib import Path


def load_test_module(tree: Path):
    path = tree / "tools" / "test_backend_calculations.py"
    sys.path.insert(0, str(tree / "app"))
    sys.path.insert(0, str(tree / "tools"))
    spec = importlib.util.spec_from_file_location("tbc_" + tree.name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    tree = Path(args.tree).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    os.chdir(tree)
    import warnings

    warnings.filterwarnings("ignore")
    tbc = load_test_module(tree)
    case = tbc.CASES[args.db]
    import numpy as np
    import thermogar_precipitation as tp
    from thermogar_precipitation import run_precipitation
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    assert Path(tp.__file__).resolve().is_relative_to(tree), tp.__file__
    composition_text = ", ".join(
        f"{element}={value:g}" for element, value in case.kwn_composition_pct.items()
    )
    started = time.perf_counter()
    result = run_precipitation(
        db=object(),
        database_path=tbc.database_path(case),
        database_label=RELEASE_DATABASE_LABELS.get(case.key, case.label),
        database_key=case.key,
        balance=case.balance,
        composition_text=composition_text,
        units=case.kwn_units,
        matrix_phase=case.kwn_matrix,
        precipitate_phase=case.kwn_precipitate,
        schedule_mode="isothermal",
        temperature_c=case.kwn_temperature_c,
        duration_h=1.0 / 3600.0,
        profile_text="",
        gamma=case.kwn_gamma,
        matrix_vm=case.kwn_molar_volume_cm3,
        precip_vm=case.kwn_molar_volume_cm3,
        nucleation_type="BULK",
        bulk_n0=1e30,
        grain_size_um=100.0,
        dislocation_density=5e12,
        gb_energy=0.3,
        cmin_nm=case.kwn_size_nm[0],
        cmax_nm=case.kwn_size_nm[1],
        bins=30,
        input_provenance="SYNTHETIC_BACKEND_REGRESSION_NOT_MATERIAL_INPUT",
        input_confirmation=True,
    )
    wall = time.perf_counter() - started
    k = result.kinetics
    t = np.asarray(k["Время, с"], float)
    dt = np.diff(t)
    quality_ok = bool((result.quality["Статус"] == "пройдена").all())
    summary = {
        "tag": args.tag,
        "db": args.db,
        "seed": os.environ.get("PYTHONHASHSEED"),
        "tree": str(tree),
        "module": str(Path(tp.__file__).resolve()),
        "composition": composition_text,
        "pair": f"{case.kwn_matrix} / {case.kwn_precipitate}",
        "T_c": case.kwn_temperature_c,
        "gamma": case.kwn_gamma,
        "size_nm": list(case.kwn_size_nm),
        "rows": int(len(k)),
        "t_end_s": float(t[-1]),
        "fraction_pct": float(k["Объёмная доля, %"].iloc[-1]),
        "radius_nm": float(k["Средний радиус, нм"].iloc[-1]),
        "density_m3": float(k["Плотность частиц, 1/м³"].iloc[-1]),
        "psd_bins_end": int(len(getattr(result, "psd", []))),
        "dt_first_s": float(dt[0]) if len(dt) else None,
        "dt_min_s": float(dt.min()) if len(dt) else None,
        "dt_max_s": float(dt.max()) if len(dt) else None,
        "quality_ok": quality_ok,
        "wall_s": wall,
        "peak_rss_gib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20,
    }
    stem = f"{args.db}_{args.tag}_s{summary['seed']}"
    k.to_csv(out / f"{stem}_kinetics.csv", index=False, encoding="utf-8")
    (out / f"{stem}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
