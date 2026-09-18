"""14-А (BL-21): общие части опытов — база, состав без предела, модель KWN.

Скрипты волны собирают расчёт выделений из частей
``app/thermogar_precipitation.py``, как Д-2 отчёта 13-Р2, потому что штатный
``run_precipitation`` не пускает больше четырёх добавок. ``app/`` не правится:
предел обходит только локальная копия ``_composition_vectors`` ниже, всё
остальное — функции модуля приложения как есть.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

import numpy as np  # noqa: E402
import psutil  # noqa: E402

DB_PATH = ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"

# Лестница составов, масс. %: каждая ступень — предыдущая плюс один элемент.
# Ступень 4 — состав пункта 5 отчёта 13-Р2 («основа 718 без Fe и Mo»,
# Ni–19Cr–5,1Nb–0,5Al–0,9Ti). FE=18 и MO=3 — круглые синтетические нагрузки
# для замера цены, а не марочный состав 718: источника на них нет, и в
# физический результат проекта они не идут.
LADDER_WT: list[tuple[str, float]] = [
    ("CR", 19.0),
    ("NB", 5.1),
    ("TI", 0.9),
    ("AL", 0.5),
    ("FE", 18.0),
    ("MO", 3.0),
]
# Лестница Б — контроль «число элементов при почти той же физике»: ступени
# 2…4 те же, что в лестнице А, а FE, MO и CO добавляются по 0,5 масс. %, чтобы
# движущая сила и число шагов решателя менялись мало. На лестнице А FE=18
# поднимает движущую силу γ′ с 746 до 2025 Дж/моль, и расчёт уходит в
# ловушку доли 100 % (BL-22) — цену числа элементов она не показывает.
# 0,5 — такая же синтетическая нагрузка без источника, как FE=18 и MO=3.
LADDER_B_EXTRA: list[tuple[str, float]] = [("FE", 0.5), ("MO", 0.5), ("CO", 0.5)]


def ladder_b_text(solute_count: int) -> str:
    items = list(LADDER_WT[: min(solute_count, 4)]) + LADDER_B_EXTRA[: max(0, solute_count - 4)]
    return ", ".join(f"{element}={value:g}" for element, value in items)


# Седьмая добавка — только для вопроса 2 (сборка термодинамики на 7 добавках).
SEVENTH_WT: tuple[str, float] = ("CO", 1.0)


def ladder_text(solute_count: int, with_seventh: bool = False) -> str:
    items = list(LADDER_WT[:solute_count])
    if with_seventh:
        items.append(SEVENTH_WT)
    return ", ".join(f"{element}={value:g}" for element, value in items)


def free_gib() -> float:
    return psutil.virtual_memory().available / 2**30


def mem() -> dict[str, float]:
    info = psutil.Process().memory_info()
    return {
        "rss_gib": round(info.rss / 2**30, 4),
        "peak_wset_gib": round(info.peak_wset / 2**30, 4),
        "private_gib": round(info.private / 2**30, 4),
        "peak_pagefile_gib": round(info.peak_pagefile / 2**30, 4),
    }


def load_database() -> Any:
    """База тем же путём, что ``run_precipitation``: SHA-256, разбор, правки 0.4.1."""

    import thermogar_precipitation as tp
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    _key, _path, _sha, _label, database = tp._bind_release_database(
        "ni", DB_PATH, RELEASE_DATABASE_LABELS["ni"]
    )
    return database


def composition_vectors_unlimited(db: Any, balance: str, text: str, units: str):
    """Копия ``tp._composition_vectors`` без строки ``len(solutes) > 4``.

    Всё прочее — разбор, проверки, пересчёт единиц — то же, что в приложении.
    """

    import thermogar_precipitation as tp

    balance = str(balance).upper()
    entered = tp._parse_composition(text)
    if balance in entered:
        raise ValueError(f"Не указывайте элемент-основу {balance} в добавках.")
    available = {str(e).upper() for e in db.elements if str(e).upper() != "VA"}
    unknown = sorted(set(entered) - available)
    if unknown:
        raise ValueError("В базе отсутствуют: " + ", ".join(unknown))
    total = float(sum(entered.values()))
    if total >= 100:
        raise ValueError("Сумма добавок должна быть меньше 100 %.")
    solutes = sorted(entered)
    if not solutes:
        raise ValueError("Укажите хотя бы одну добавку.")
    elements = [balance] + solutes
    percentages = np.array([100 - total] + [entered[e] for e in solutes], float)
    masses = tp._atomic_masses(db, elements)
    if units == "at":
        x_at = percentages / 100
        weighted = x_at * masses
        x_wt = weighted / weighted.sum()
    elif units == "wt":
        x_wt = percentages / 100
        moles = x_wt / masses
        x_at = moles / moles.sum()
    else:
        raise ValueError("Неизвестные единицы состава.")
    return elements, x_at, x_wt


def build_model(db: Any, elements: list[str], x_at: np.ndarray, case: dict) -> tuple[Any, float]:
    """То же, что ``build_model`` внутри ``run_precipitation`` (изотерма).

    Возвращает модель и время сборки термодинамики kawin, с.
    """

    import thermogar_precipitation as tp

    temperature = tp.TemperatureParameters(float(case["temperature_c"]) + 273.15)
    started = time.perf_counter()
    therm, _class = tp._build_precipitation_thermodynamics(
        db, elements, [case["matrix_phase"], case["precipitate_phase"]]
    )
    therm_seconds = time.perf_counter() - started
    matrix = tp.MatrixParameters(elements[1:])
    matrix.initComposition = np.asarray(x_at[1:], float)
    matrix.volume.setVolume(float(case["matrix_vm"]) * 1e-6, "VM", 1)
    matrix.GBenergy = float(case["gb_energy"])
    matrix.nucleationSites.setNucleationDensity(
        grainSize=float(case["grain_size_um"]), aspectRatio=1,
        dislocationDensity=float(case["dislocation_density"]), bulkN0=float(case["bulk_n0"]),
    )
    precip = tp.PrecipitateParameters(case["precipitate_phase"])
    precip.gamma = float(case["gamma"])
    precip.volume.setVolume(float(case["precip_vm"]) * 1e-6, "VM", 1)
    precip.nucleation.setNucleationType(case["nucleation_type"])
    built = tp.PrecipitateModel(matrix, [precip], therm, temperature)
    bins = int(case["bins"])
    built.setPBMParameters(
        cMin=float(case["cmin_nm"]) * 1e-9, cMax=float(case["cmax_nm"]) * 1e-9, bins=bins,
        minBins=max(20, bins // 2), maxBins=max(80, bins * 2), adaptive=True,
    )
    return built, therm_seconds


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def setup_state(out: Path, tag: str) -> None:
    os.environ["THERMOGAR_STATE_ROOT"] = str(out / f"state_{tag}")
