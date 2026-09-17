"""14-Г, пункт 3: признак BL-32 на известных случаях — штатным ``run_precipitation`` нового кода.

    p3_cases.py

Для случаев, которые должны отклоняться, ``PrecipitateModel.solve`` подменён
на исключение: если проверка их пропустит, скрипт это запишет, а не зависнет.
Умолчание Ni-раздела считается по-настоящему — 1 ч, постановка
``test_ni_kwn_reaches_a_precipitated_state``; Б5 и А4 — 10 с, постановка 14-А.
Оценки зародыша записываются обёрткой над ``_nucleus_estimates`` (u = Rmin/r*).
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "wave14_b"))
import kwn_parts as parts  # noqa: E402

OUT = HERE / "p3"
OUT.mkdir(parents=True, exist_ok=True)
parts.setup_state(OUT, "cases")

import thermogar_precipitation as tp  # noqa: E402
from thermogar_release_policy import RELEASE_DATABASE_LABELS  # noqa: E402

LADDER = dict(units="wt", matrix_phase="FCC_A1", precipitate_phase="GAMMA_PRIME", temperature_c=750.0,
              duration_h=10.0 / 3600.0, gamma=0.023, matrix_vm=6.5662724928, precip_vm=6.5662724928,
              cmin_nm=0.2, cmax_nm=10.0, bins=80)
_m, _p, t_ni, _h, g_ni, vm_m, vm_p = tp.DEFAULTS["ni"]
NI_DEFAULT = dict(units="at", matrix_phase=_m, precipitate_phase=_p, temperature_c=t_ni, duration_h=1.0,
                  gamma=g_ni, matrix_vm=vm_m, precip_vm=vm_p, cmin_nm=0.2, cmax_nm=10.0, bins=80)
CASES = [
    ("А5 (проходы a и b — один случай)", "CR=19, NB=5.1, TI=0.9, AL=0.5, FE=18", LADDER, True),
    ("А6", "CR=19, NB=5.1, TI=0.9, AL=0.5, FE=18, MO=3", LADDER, True),
    ("А7", "CR=19, NB=5.1, TI=0.9, AL=0.5, FE=18, MO=3, CO=1", LADDER, True),
    ("C4, штатный путь", "CR=19, NB=5.1, TI=0.9, FE=18", LADDER, True),
    ("умолчание Ni-раздела, 1 ч", "AL=15", NI_DEFAULT, False),
    ("Б5", "CR=19, NB=5.1, TI=0.9, AL=0.5, FE=0.5", LADDER, False),
    ("А4", "CR=19, NB=5.1, TI=0.9, AL=0.5", LADDER, False),
]

original_solve = tp.PrecipitateModel.solve
original_estimates = tp._nucleus_estimates
seen: list = []


def recorded_estimates(*arguments):
    result = original_estimates(*arguments)
    seen.append(result)
    return result


def forbidden_solve(*_arguments, **_keywords):
    raise RuntimeError("SOLVE_REACHED: проверка пропустила случай")


tp._nucleus_estimates = recorded_estimates
rows = []
for name, text, case, expect_refusal in CASES:
    tp.PrecipitateModel.solve = forbidden_solve if expect_refusal else original_solve
    seen.clear()
    row: dict = {"случай": name, "состав": text, "ожидается": "отказ" if expect_refusal else "расчёт"}
    started = time.perf_counter()
    try:
        result = tp.run_precipitation(
            db=object(), database_path=parts.DB_PATH, database_label=RELEASE_DATABASE_LABELS["ni"],
            database_key="ni", balance="NI", composition_text=text, schedule_mode="isothermal",
            profile_text="", nucleation_type="BULK", bulk_n0=1e30, grain_size_um=100.0,
            dislocation_density=5e12, gb_energy=0.3,
            input_provenance="SYNTHETIC_WAVE14G_CHECK_NOT_MATERIAL_INPUT", input_confirmation=True, **case,
        )
        row["исход"] = "посчитан"
        row["строк кинетики"] = int(len(result.kinetics))
        row["проверки качества все пройдены"] = bool((result.quality["Статус"] == "пройдена").all())
        row["warnings"] = list(result.warnings)
        row["итоговая доля, %"] = float(result.kinetics["Объёмная доля, %"].iloc[-1])
    except ValueError as error:
        row["исход"] = "отказ"
        row["сообщение"] = str(error)
    except Exception as error:  # noqa: BLE001
        row["исход"] = f"{type(error).__name__}: {error}"
        row["traceback, хвост"] = traceback.format_exc().strip().splitlines()[-4:]
    row["с"] = round(time.perf_counter() - started, 1)
    if seen and seen[0]:
        temperature_k, rcrit_nm, _rnuc_nm, free_nm = seen[0][0]
        row["r* до зажима, нм"] = free_nm
        row["u = Rmin/r*"] = 0.3 / free_nm
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)

parts.write_json(OUT / "cases.json", {"случаи": rows, "память": parts.mem()})
