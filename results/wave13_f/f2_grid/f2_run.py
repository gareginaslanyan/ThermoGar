"""13-Ф, пункт 2: зародыш крупнее cMax начальной сетки — прямой опыт.

Запуск (один вариант — один процесс, PYTHONHASHSEED=0):
    python -B -X utf8 f2_run.py <cmax_nm> <каталог вывода>

Учебный Ni–9,8Al–8,3Cr ат. %, FCC_A1 / GAMMA_PRIME, 800 °C, 1 с модельного
времени, штатный путь приложения run_precipitation. Аргументы те же, что у
ячейки KWN Ni в tools/test_backend_calculations.py и в сверке 13-Р2
(results/wave13_r/p1/scripts/p1_run.py), кроме сетки: cMin 0,05 нм и
150 классов в обоих вариантах, различается только cMax.

Перед импортом тяжёлых модулей замеряется свободная физическая память; при
меньше 1,5 ГиБ процесс ничего не считает и пишет цифру.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

import psutil

MIN_FREE_GIB = 1.5
cmax_nm = float(sys.argv[1])
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).resolve().parents[3]

free_gib = psutil.virtual_memory().available / 2**30
record: dict = {
    "cmax_nm": cmax_nm,
    "free_at_start_gib": round(free_gib, 3),
    "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
}
if free_gib < MIN_FREE_GIB:
    record["skipped"] = f"свободно {free_gib:.3f} ГиБ < {MIN_FREE_GIB} ГиБ"
    (out / "meta.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))
    sys.exit(3)

os.environ["THERMOGAR_STATE_ROOT"] = str(out / "state")
sys.path.insert(0, str(ROOT / "app"))

proc = psutil.Process()
peak = {"rss": 0, "min_free": free_gib}
stop = threading.Event()


def watch() -> None:
    while not stop.is_set():
        peak["rss"] = max(peak["rss"], proc.memory_info().rss)
        peak["min_free"] = min(peak["min_free"], psutil.virtual_memory().available / 2**30)
        time.sleep(0.2)


threading.Thread(target=watch, daemon=True).start()

import numpy as np  # noqa: E402

from thermogar_precipitation import run_precipitation  # noqa: E402
from thermogar_release_policy import RELEASE_DATABASE_LABELS  # noqa: E402

db_path = ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"
record["db_sha256"] = hashlib.sha256(db_path.read_bytes()).hexdigest()

started = time.perf_counter()
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
    cmin_nm=0.05,
    cmax_nm=cmax_nm,
    bins=150,
    input_provenance="SYNTHETIC_BACKEND_REGRESSION_NOT_MATERIAL_INPUT",
    input_confirmation=True,
)
record["seconds"] = round(time.perf_counter() - started, 2)
for name in ("kinetics", "summary", "psd", "settings", "quality"):
    getattr(result, name).to_csv(out / f"kwn_{name}.csv", index=True, float_format="%.17g",
                                 lineterminator="\n")
record["warnings"] = list(getattr(result, "warnings", []) or [])
stop.set()
record["peak_rss_gib"] = round(peak["rss"] / 2**30, 3)
record["min_free_during_run_gib"] = round(peak["min_free"], 3)
(out / "meta.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(record, ensure_ascii=False))
