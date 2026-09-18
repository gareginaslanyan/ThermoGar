"""14-А, контроль к пункту 3: ловушка доли 100 % внутри нынешнего предела.

    p3_stock4.py <потолок, с>

Штатный ``run_precipitation`` приложения, без обходов, на четырёх добавках —
Ni–19Cr–5,1Nb–0,9Ti–18Fe масс. % (лестница А без Al и Mo; FE=18 — та же
синтетическая нагрузка). Остальные входы — как у лестницы. Если за потолок
расчёт не кончится, сторожевой поток пишет исход и завершает процесс кодом 4.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kwn_parts as parts  # noqa: E402

CAP_S = float(sys.argv[1])
OUT = HERE / "p3"
parts.setup_state(OUT, "stock4")

import thermogar_precipitation as tp  # noqa: E402
from thermogar_release_policy import RELEASE_DATABASE_LABELS  # noqa: E402

COMPOSITION = "CR=19, NB=5.1, TI=0.9, FE=18"
record: dict = {"путь": "run_precipitation как есть", "состав, масс. %": COMPOSITION, "потолок, с": CAP_S}
started = time.perf_counter()
done = threading.Event()


def watchdog() -> None:
    if not done.wait(CAP_S):
        record["исход"] = f"ПОТОЛОК: run_precipitation не вернулся за {CAP_S:.0f} с"
        record["с"] = round(time.perf_counter() - started, 1)
        record["память"] = parts.mem()
        parts.write_json(OUT / "stock4.json", record)
        print(record, flush=True)
        os._exit(4)


threading.Thread(target=watchdog, daemon=True).start()
try:
    result = tp.run_precipitation(
        db=object(), database_path=parts.DB_PATH, database_label=RELEASE_DATABASE_LABELS["ni"],
        database_key="ni", balance="NI", composition_text=COMPOSITION, units="wt",
        matrix_phase="FCC_A1", precipitate_phase="GAMMA_PRIME", schedule_mode="isothermal",
        temperature_c=750.0, duration_h=10.0 / 3600.0, profile_text="", gamma=0.023,
        matrix_vm=6.5662724928, precip_vm=6.5662724928, nucleation_type="BULK", bulk_n0=1e30,
        grain_size_um=100.0, dislocation_density=5e12, gb_energy=0.3, cmin_nm=0.2, cmax_nm=10.0,
        bins=80, input_provenance="SYNTHETIC_WAVE14A_CONTROL_NOT_MATERIAL_INPUT", input_confirmation=True,
    )
    record["исход"] = "вернулся"
    record["строк кинетики"] = int(len(result.kinetics))
    record["проверки качества"] = dict(zip(result.quality["Проверка"], result.quality["Статус"]))
except Exception as error:  # noqa: BLE001
    record["исход"] = "отказ"
    record["отказ дословно"] = f"{type(error).__name__}: {error}"
    record["traceback, хвост"] = traceback.format_exc().strip().splitlines()[-6:]
done.set()
record["с"] = round(time.perf_counter() - started, 1)
record["память"] = parts.mem()
parts.write_json(OUT / "stock4.json", record)
print(record, flush=True)
