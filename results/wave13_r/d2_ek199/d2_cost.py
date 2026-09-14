"""Д-2 к 13-Р2: цена развязки оценки зародыша на кинетике ЭК199.

Запуск: python -B -X utf8 d2_cost.py <on|off> <каталог вывода>

Один случай кинетики волны 12-1: состав ЭК199-ВИ без Nb (компоненты и мольные
доли — из results/hn62m_wave12/k1_summary.json), FCC_A1 / P_PHASE, 700 °C,
γ = 0,10 Дж/м², зарождение в объёме зерна, сетка PBM волны 12 (умолчания kawin:
cMin 0,1 нм, cMax 1 нм, 150 классов, адаптивно), решение до 87 600 ч с теми же
прерываниями, что в 12-1. Модель собирается функцией build_model того же
модуля tools/study_hn62m_wave12_kinetics.py, термодинамика — функцией
приложения _build_precipitation_thermodynamics.

off — как в 0.4.0: одна термодинамика, одна модель, расчёт.
on  — как run_precipitation на 36c9c4f: модель расчёта, затем вторая модель со
      своей термодинамикой, на ней _nucleus_estimates приложения; ссылка на
      вторую модель живёт до конца расчёта (в run_precipitation она остаётся
      локальной переменной функции).

Штатный путь run_precipitation для ЭК199 закрыт (не больше четырёх добавок,
BL-21), поэтому оба варианта собраны из тех же частей, из которых собран
run_precipitation и подпункт 12-1.
"""

from __future__ import annotations

import gc
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

mode = sys.argv[1]
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).resolve().parents[3]
os.environ["THERMOGAR_STATE_ROOT"] = str(out / f"state_{mode}")
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "tools"))

import numpy as np  # noqa: E402
import psutil  # noqa: E402

proc = psutil.Process()
samples = {"rss_max": 0, "private_max": 0}
stop = threading.Event()


def watch() -> None:
    while not stop.is_set():
        info = proc.memory_info()
        samples["rss_max"] = max(samples["rss_max"], info.rss)
        samples["private_max"] = max(samples["private_max"], info.private)
        time.sleep(0.25)


def mem() -> dict:
    info = proc.memory_info()
    return {
        "rss_gib": round(info.rss / 2**30, 4),
        "peak_wset_gib": round(info.peak_wset / 2**30, 4),
        "private_gib": round(info.private / 2**30, 4),
        "peak_pagefile_gib": round(info.peak_pagefile / 2**30, 4),
    }


threading.Thread(target=watch, daemon=True).start()
record: dict = {"mode": mode, "free_at_start_gib": round(psutil.virtual_memory().available / 2**30, 3)}
t0 = time.perf_counter()

from pycalphad import Database  # noqa: E402
import thermogar_db_cache as db_cache  # noqa: E402
import thermogar_precipitation as tp  # noqa: E402
import study_hn62m_wave12_kinetics as k  # noqa: E402

summary = json.loads((ROOT / "results/hn62m_wave12/k1_summary.json").read_text(encoding="utf-8"))
mole = {str(key): float(value) for key, value in summary["состав, мольные доли"].items()}
volumes = summary["молярные объёмы"]["700"]
assert k.elements() == summary["компоненты расчёта"], (k.elements(), summary["компоненты расчёта"])
assert k.K_PBM == summary["сетка размеров PBM"], k.K_PBM

db_path = ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"
raw = db_path.read_bytes()
sha = hashlib.sha256(raw).hexdigest()
db = db_cache.load_or_parse(
    expected_sha256=sha, snapshot_sha256=sha, snapshot_bytes=raw,
    parse=lambda: Database(str(db_path)), database_label=db_path.name,
)
del raw
gc.collect()
record["after_database"] = mem()
record["seconds_database"] = round(time.perf_counter() - t0, 2)

TEMPERATURE_C, GAMMA, SITE = 700.0, 0.10, "BULK"

t1 = time.perf_counter()
therm, therm_class = tp._build_precipitation_thermodynamics(db, k.elements(), [k.MATRIX_PHASE, k.PRECIPITATE_PHASE])
model = k.build_model(None, therm, mole, TEMPERATURE_C, GAMMA, SITE, volumes)
record["seconds_build_calc_model"] = round(time.perf_counter() - t1, 2)
record["after_calc_model"] = mem()

estimate_model = None
if mode == "on":
    t2 = time.perf_counter()
    estimate_therm, _ = tp._build_precipitation_thermodynamics(db, k.elements(), [k.MATRIX_PHASE, k.PRECIPITATE_PHASE])
    estimate_model = k.build_model(None, estimate_therm, mole, TEMPERATURE_C, GAMMA, SITE, volumes)
    record["seconds_build_estimate_model"] = round(time.perf_counter() - t2, 2)
    t3 = time.perf_counter()
    estimates = tp._nucleus_estimates(estimate_model, k.PRECIPITATE_PHASE, [TEMPERATURE_C + 273.15])
    record["seconds_nucleus_estimates"] = round(time.perf_counter() - t3, 2)
    record["nucleus_estimates_nm"] = estimates
    del estimate_therm
    record["after_estimate"] = mem()

t4 = time.perf_counter()
previous = 0.0
for edge in k.stage_edges(k.K_T_MIN_H):
    model.solve((float(edge) - previous) * 3600.0, verbose=False)
    previous = float(edge)
record["seconds_solve"] = round(time.perf_counter() - t4, 2)
record["seconds_total"] = round(time.perf_counter() - t0, 2)
record["after_solve"] = mem()
stop.set()
n = int(model.data.n)
record["solver_steps"] = n
record["final_time_h"] = float(model.data.time[n]) / 3600.0
record["final_volume_fraction"] = float(model.data.volFrac[n, 0])
record["final_mean_radius_nm"] = 1e9 * float(model.data.Ravg[n, 0])
record["sampled_rss_max_gib"] = round(samples["rss_max"] / 2**30, 4)
record["sampled_private_max_gib"] = round(samples["private_max"] / 2**30, 4)
record["estimate_model_alive_during_solve"] = estimate_model is not None
record["min_free_during_run_note"] = "см. раннер"
path = out / f"d2_{mode}_{time.strftime('%Y%m%dT%H%M%S')}.json"
path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(record, ensure_ascii=False))
