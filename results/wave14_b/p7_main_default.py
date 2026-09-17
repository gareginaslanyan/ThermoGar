"""14-Б, разбор регрессии: умолчание никелевого раздела KWN на коде ``main`` (без BL-32).

    p7_main_default.py <корень снимка main> <часов модельного времени> <потолок, с>

Штатный ``run_precipitation`` снимка ``git archive 8c1458e``: Ni-15Al ат. %,
``DEFAULTS["ni"]`` (γ′ в FCC_A1, 800 °C, γ = 0,023 Дж/м², Vm 6,57), сетка
умолчаний раздела 0,2…10 нм × 80 классов — постановка
``test_ni_kwn_reaches_a_precipitated_state``. Вопрос один: заканчивается ли
расчёт с прижатым критическим радиусом и за сколько. Если за потолок не
вернулся — пишет исход и выходит кодом 4.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1]).resolve()
HOURS = float(sys.argv[2])
CAP_S = float(sys.argv[3])
OUT = HERE / "p7"
OUT.mkdir(parents=True, exist_ok=True)
TAG = f"main_default_{HOURS:g}h"
os.environ["THERMOGAR_STATE_ROOT"] = str(Path(os.environ.get("TEMP", str(OUT))) / f"tg14b_state_{TAG}")
sys.path.insert(0, str(ROOT / "app"))

import psutil  # noqa: E402
import thermogar_precipitation as tp  # noqa: E402
from thermogar_release_policy import RELEASE_DATABASE_LABELS  # noqa: E402

matrix_phase, precipitate_phase, t_c, _hours, gamma, vm_m, vm_p = tp.DEFAULTS["ni"]
record: dict = {"снимок": str(ROOT), "модуль": tp.__file__, "часов": HOURS, "потолок, с": CAP_S,
                "BL-32 в модуле": hasattr(tp, "_check_critical_radius_floor"),
                "постановка": dict(composition="AL=15 ат. %", matrix=matrix_phase, precipitate=precipitate_phase,
                                   temperature_c=t_c, gamma=gamma, vm=(vm_m, vm_p), grid=(0.2, 10.0, 80))}
started = time.perf_counter()
done = threading.Event()


def write() -> None:
    record["с"] = round(time.perf_counter() - started, 1)
    record["пик рабочего набора, ГиБ"] = round(psutil.Process().memory_info().peak_wset / 2**30, 3)
    (OUT / f"{TAG}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False), flush=True)


def watchdog() -> None:
    if not done.wait(CAP_S):
        record["исход"] = f"ПОТОЛОК: run_precipitation не вернулся за {CAP_S:.0f} с"
        write()
        os._exit(4)


threading.Thread(target=watchdog, daemon=True).start()
db_path = ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"
result = tp.run_precipitation(
    db=object(), database_path=db_path, database_label=RELEASE_DATABASE_LABELS["ni"], database_key="ni",
    balance="NI", composition_text="AL=15", units="at", matrix_phase=matrix_phase,
    precipitate_phase=precipitate_phase, schedule_mode="isothermal", temperature_c=t_c, duration_h=HOURS,
    profile_text="", gamma=gamma, matrix_vm=vm_m, precip_vm=vm_p, nucleation_type="BULK", bulk_n0=1e30,
    grain_size_um=100.0, dislocation_density=5e12, gb_energy=0.3, cmin_nm=0.2, cmax_nm=10.0, bins=80,
    input_provenance="SYNTHETIC_WAVE14B_DIAGNOSTIC_NOT_MATERIAL_INPUT", input_confirmation=True,
)
done.set()
kinetics = result.kinetics
record["исход"] = "вернулся"
record["строк кинетики"] = int(len(kinetics))
record["критический радиус на шагах зарождения, нм: минимум / максимум"] = [
    float(kinetics["Критический радиус, нм"][kinetics["Скорость зарождения, 1/(м³·с)"] > 0].min()),
    float(kinetics["Критический радиус, нм"][kinetics["Скорость зарождения, 1/(м³·с)"] > 0].max()),
]
record["доля строк зарождения с r* = 0,3 нм"] = float(
    ((kinetics["Критический радиус, нм"] == 1e9 * 3e-10) & (kinetics["Скорость зарождения, 1/(м³·с)"] > 0)).sum()
    / max(1, (kinetics["Скорость зарождения, 1/(м³·с)"] > 0).sum())
)
record["итоги"] = dict(zip(result.summary["Показатель"], result.summary["Значение"]))
record["проверки качества"] = dict(zip(result.quality["Проверка"], result.quality["Статус"]))
write()
