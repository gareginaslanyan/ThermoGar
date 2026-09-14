"""Пункт 1 выпуска 0.4.1: расчёт без ниобия на одной версии кода.

Запуск: python p1_run.py <корень дерева версии> <каталог вывода>
Корень дерева — снимок `git archive` нужной ревизии (app + databases).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import threading
import time
from pathlib import Path

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
os.environ["THERMOGAR_STATE_ROOT"] = str(out / "state")
sys.path.insert(0, str(root / "app"))

import numpy as np  # noqa: E402
import psutil  # noqa: E402

peak = {"rss": 0}
stop = threading.Event()


def watch() -> None:
    proc = psutil.Process()
    while not stop.is_set():
        peak["rss"] = max(peak["rss"], proc.memory_info().rss)
        time.sleep(0.2)


threading.Thread(target=watch, daemon=True).start()

from pycalphad import Database, equilibrium, variables as v  # noqa: E402

import thermogar_db_cache as cache  # noqa: E402
import thermogar_database_repair as repair  # noqa: E402

DB_REL = "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"
db_path = root / DB_REL
raw = db_path.read_bytes()
sha = hashlib.sha256(raw).hexdigest()

started = time.perf_counter()
db = cache.load_or_parse(
    expected_sha256=sha,
    snapshot_sha256=sha,
    snapshot_bytes=raw,
    parse=lambda: Database(str(db_path)),
    database_label=db_path.name,
)
meta = {
    "root": str(root),
    "db_sha256": sha,
    "MOBILITY_DEDUP_VERSION": repair.MOBILITY_DEDUP_VERSION,
    "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
}

# 1. Все записи параметров разобранной и починенной базы, по одной строке.
table = db._parameters.table(db._parameters.default_table_name)
lines = []
for record in table.all():
    diffusing = record.get("diffusing_species")
    lines.append(
        "|".join(
            [
                str(record.get("phase_name")),
                str(record.get("parameter_type")),
                str(getattr(diffusing, "name", diffusing)),
                repr(
                    tuple(
                        tuple(str(getattr(s, "name", s)) for s in sub)
                        for sub in record.get("constituent_array")
                    )
                ),
                str(record.get("parameter_order")),
                str(record.get("parameter")),
            ]
        )
    )
lines.sort()
(out / "db_parameters.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

# 2. Скан температуры Ni-15Al ат. % — results/ni15al_temperature_scan_coarse.csv.
phases = ["FCC_A1", "GAMMA_PRIME", "LIQUID", "BCC_B2"]
temps_c = [500.0 + 25.0 * i for i in range(33)]
rows = ["T_C,T_K,FCC_A1_NP,GAMMA_PRIME_NP,LIQUID_NP,BCC_B2_NP,phase_fraction_sum"]
for t_c in temps_c:
    eq = equilibrium(
        db,
        ["NI", "AL", "VA"],
        phases,
        {v.X("AL"): 0.15, v.T: t_c + 273.15, v.P: 101325, v.N: 1},
    )
    names = eq.Phase.values.squeeze()
    nps = eq.NP.values.squeeze()
    frac = {p: 0.0 for p in phases}
    for name, np_value in zip(names, nps):
        name = str(name)
        if name and np.isfinite(np_value):
            frac[name] = frac.get(name, 0.0) + float(np_value)
    rows.append(
        ",".join(
            [repr(t_c), repr(t_c + 273.15)]
            + [repr(frac[p]) for p in phases]
            + [repr(sum(frac.values()))]
        )
    )
(out / "ni15al_scan.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
meta["scan_seconds"] = round(time.perf_counter() - started, 2)

# 3. KWN Ni-9.8Al-8.3Cr ат. %, 800 °C — ячейка test_kwn_module[ni].
started = time.perf_counter()
from thermogar_precipitation import run_precipitation  # noqa: E402
from thermogar_release_policy import RELEASE_DATABASE_LABELS  # noqa: E402

result = run_precipitation(
    db=object(),
    database_path=db_path,
    database_label=RELEASE_DATABASE_LABELS.get("ni", ""),
    database_key="ni",
    balance="NI",
    composition_text="AL=9.8, CR=8.3",
    units="at",
    matrix_phase="FCC_A1",
    precipitate_phase="GAMMA_PRIME",
    schedule_mode="isothermal",
    temperature_c=800.0,
    duration_h=1.0 / 3600.0,
    profile_text="",
    gamma=0.023,
    matrix_vm=6.5662724928,
    precip_vm=6.5662724928,
    nucleation_type="BULK",
    bulk_n0=1e30,
    grain_size_um=100.0,
    dislocation_density=5e12,
    gb_energy=0.3,
    cmin_nm=0.2,
    cmax_nm=5.0,
    bins=30,
    input_provenance="SYNTHETIC_BACKEND_REGRESSION_NOT_MATERIAL_INPUT",
    input_confirmation=True,
)
meta["kwn_seconds"] = round(time.perf_counter() - started, 2)
for name in ("kinetics", "summary", "matrix_composition", "interface_composition", "psd",
             "settings", "quality"):
    frame = getattr(result, name)
    frame.to_csv(out / f"kwn_{name}.csv", index=True, float_format="%.17g",
                 lineterminator="\n")
with np.load(io.BytesIO(result.npz), allow_pickle=True) as arrays:
    buf = []
    for key in sorted(arrays.files):
        arr = arrays[key]
        buf.append(f"{key}|{arr.dtype}|{arr.shape}|{hashlib.sha256(np.ascontiguousarray(arr).tobytes() if arr.dtype != object else repr(arr.tolist()).encode()).hexdigest()}")
(out / "kwn_npz_arrays.txt").write_text("\n".join(buf) + "\n", encoding="utf-8")
(out / "kwn_warnings.json").write_text(
    json.dumps(getattr(result, "warnings", None), ensure_ascii=False, indent=1), encoding="utf-8"
)
stop.set()
meta["peak_rss_gib"] = round(peak["rss"] / 2**30, 3)
(out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(meta, ensure_ascii=False))
