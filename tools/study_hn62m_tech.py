#!/usr/bin/env python3
"""Технологические расчёты по ХН62М(Sc)-ВИ — часть B волны 10.

Отвечает на три вопроса заказчика: что расчёт говорит о сварке, о горячей
деформации и о пайке.

* **B1** — корректный расчёт Шейля от ликвидуса и индекс горячих трещин Kou.
* **B2** — цена серы: то же при S = 0,020 / 0,010 / 0,005 / 0,002 % и при
  Mn = 0,50 / 0,20.
* **B3** — локальный солидус междендритной области: потолок нагрева в литом
  состоянии против гомогенизированного.

Запуск (интерпретатор venv основного репозитория, ``PYTHONHASHSEED=0``):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 ^
        tools\\study_hn62m_tech.py --only all

Пункты идемпотентны: выполненное отмечается в
``results/hn62m_tech/_progress.json`` и при повторном запуске пропускается,
пересчёт — ключом ``--force``. Отдельные расчёты Шейля кэшируются по составу,
поэтому B3 не пересчитывает то, что уже посчитал B1.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

OUT = ROOT / "results" / "hn62m_tech"
CACHE = OUT / "cache"
PROGRESS_PATH = OUT / "_progress.json"

DB_REL = "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"
BALANCE = "NI"
PDENS = 100

# Контрольный состав, масс. %; никель — основа.
CONTROL_WT: dict[str, float] = {
    "C": 0.005, "SI": 0.10, "MN": 0.50, "S": 0.020, "CR": 23.5,
    "MO": 13.0, "NB": 0.06, "AL": 0.25, "TI": 0.10, "FE": 0.50,
}
COMPONENTS: tuple[str, ...] = (
    "NI", "CR", "MO", "C", "SI", "MN", "S", "NB", "AL", "TI", "FE", "VA",
)
ELEMENTS: tuple[str, ...] = tuple(name for name in COMPONENTS if name != "VA")

# Шаг по температуре в расчёте Шейля. Постановка просит 2 K и 0,5 K в хвосте
# при fs > 0,9; ``scheil`` кусочного шага не умеет, поэтому головной расчёт B1
# гоняется целиком с 0,5 K, а сравнительный B2 — с 2 K: там важно, что шаг у
# всех составов одинаковый, а не его абсолютная величина.
SCHEIL_STEP_K = 2.0
SCHEIL_STOP = 1.0e-4
FS_MARKS = (0.5, 0.9, 0.95, 0.99)
KOU_WINDOW = (0.9, 0.99)


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


# --------------------------------------------------------------------------- #
# База и состав
# --------------------------------------------------------------------------- #


class Context:
    """Разобранная база и всё, что от неё зависит."""

    def __init__(self) -> None:
        from pycalphad import Database
        from pycalphad.core.utils import filter_phases, unpack_species

        import thermogar_database_repair as repair

        started = time.perf_counter()
        self.path = ROOT / DB_REL
        self.db = Database(str(self.path))
        report = repair.repair_database(self.db, database_label=self.path.name)
        self.repair_report = report["mobility_defaults"]
        phases = sorted(filter_phases(self.db, unpack_species(self.db, list(COMPONENTS))))
        phases, removed = repair.drop_broken_order_disorder(
            self.db, list(COMPONENTS), phases
        )
        self.phases = phases
        self.excluded_phases = removed
        self.masses = {
            element: float(self.db.refstates[element]["mass"]) for element in ELEMENTS
        }
        log(
            f"база разобрана за {time.perf_counter() - started:.1f} с; "
            f"фаз {len(self.phases)}; исключено {sorted(removed) or 'нет'}"
        )


def full_wt(overrides: Mapping[str, float] | None = None) -> dict[str, float]:
    values = dict(CONTROL_WT)
    if overrides:
        for element, value in overrides.items():
            values[element.upper()] = float(value)
    values = {element: value for element, value in values.items() if value > 0.0}
    values[BALANCE] = 100.0 - sum(values.values())
    return values


def wt_to_mole(ctx: Context, wt_percent: Mapping[str, float]) -> dict[str, float]:
    from thermogar_equilibrium_core import mass_to_mole_fractions

    names = sorted(wt_percent)
    mass = tuple((element, wt_percent[element] / 100.0) for element in names)
    masses = tuple((element, ctx.masses[element]) for element in names)
    return {element: value for element, value in mass_to_mole_fractions(mass, masses)}


def independent_x(mole: Mapping[str, float]) -> dict[str, float]:
    return {
        element: value
        for element, value in sorted(mole.items())
        if element != BALANCE
    }


def composition_id(mole: Mapping[str, float]) -> str:
    payload = {element: round(float(value), 9) for element, value in sorted(mole.items())}
    import hashlib

    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Равновесия
# --------------------------------------------------------------------------- #


def solve(ctx: Context, mole: Mapping[str, float], temperature_c: float) -> dict[str, float]:
    """Мольные доли фаз в равновесии при заданной температуре."""

    from pycalphad import equilibrium, variables as v

    conditions: dict[Any, float] = {
        v.N: 1.0, v.P: 101325.0, v.T: float(temperature_c) + 273.15,
    }
    conditions.update(
        {v.X(element): value for element, value in independent_x(mole).items()}
    )
    result = equilibrium(
        ctx.db, list(COMPONENTS), ctx.phases, conditions, calc_opts={"pdens": PDENS}
    )
    names = np.asarray(result.Phase.values, dtype=str).ravel()
    amounts = np.asarray(result.NP.values, dtype=float).ravel()
    aggregated: dict[str, float] = {}
    for name, amount in zip(names, amounts):
        if not name or not np.isfinite(amount) or float(amount) <= 1.0e-9:
            continue
        aggregated[str(name)] = aggregated.get(str(name), 0.0) + float(amount)
    del result
    gc.collect()
    return aggregated


def liquidus_c(
    ctx: Context,
    mole: Mapping[str, float],
    low: float = 1200.0,
    high: float = 1500.0,
    tolerance: float = 0.5,
) -> float:
    """Равновесный ликвидус: температура, ниже которой появляется твёрдое.

    Половинным делением, а не сканом: восемь-девять равновесий вместо трёх
    десятков. Признак «полностью жидко» — доля LIQUID не меньше 1 − 1e-6.
    """

    def fully_liquid(temperature_c: float) -> bool:
        fractions = solve(ctx, mole, temperature_c)
        return fractions.get("LIQUID", 0.0) >= 1.0 - 1.0e-6

    if not fully_liquid(high):
        raise RuntimeError(f"При {high} °C сплав не полностью жидкий")
    if fully_liquid(low):
        raise RuntimeError(f"При {low} °C сплав уже полностью жидкий")
    while high - low > tolerance:
        middle = 0.5 * (low + high)
        if fully_liquid(middle):
            high = middle
        else:
            low = middle
    return 0.5 * (low + high)


def solidus_c(
    ctx: Context,
    mole: Mapping[str, float],
    low: float = 1000.0,
    high: float = 1450.0,
    tolerance: float = 0.5,
) -> float:
    """Равновесный солидус: температура появления первой жидкости."""

    def has_liquid(temperature_c: float) -> bool:
        return solve(ctx, mole, temperature_c).get("LIQUID", 0.0) > 1.0e-6

    if has_liquid(low):
        raise RuntimeError(f"При {low} °C уже есть жидкость")
    if not has_liquid(high):
        raise RuntimeError(f"При {high} °C жидкости ещё нет")
    while high - low > tolerance:
        middle = 0.5 * (low + high)
        if has_liquid(middle):
            high = middle
        else:
            low = middle
    return 0.5 * (low + high)


# --------------------------------------------------------------------------- #
# Шейль
# --------------------------------------------------------------------------- #


def scheil_result(ctx: Context, mole: Mapping[str, float], label: str) -> Any:
    """Расчёт Шейля от ликвидуса + 5 K с кэшем по составу."""

    import scheil
    from pycalphad import variables as v

    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"scheil_{composition_id(mole)}_step{SCHEIL_STEP_K:g}.json"
    if path.is_file():
        payload = json.loads(path.read_text("utf-8"))
        log(f"{label}: Шейль взят из кэша ({payload['steps']} шагов)")
        return scheil.SolidificationResult.from_dict(payload["result"]), payload

    started = time.perf_counter()
    liquidus = liquidus_c(ctx, mole)
    log(f"{label}: равновесный ликвидус {liquidus:.1f} °C")
    start_k = liquidus + 5.0 + 273.15
    composition = {
        v.X(element): value for element, value in independent_x(mole).items()
    }
    result = scheil.simulate_scheil_solidification(
        ctx.db,
        list(COMPONENTS),
        ctx.phases,
        composition,
        start_k,
        step_temperature=SCHEIL_STEP_K,
        liquid_phase_name="LIQUID",
        eq_kwargs={"calc_opts": {"pdens": PDENS}},
        stop=SCHEIL_STOP,
        verbose=False,
    )
    seconds = time.perf_counter() - started
    payload = {
        "result": result.to_dict(),
        "liquidus_c": liquidus,
        "start_c": start_k - 273.15,
        "steps": len(result.temperatures),
        "seconds": seconds,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    log(f"{label}: Шейль {len(result.temperatures)} шагов за {seconds / 60.0:.1f} мин")
    return result, payload


def scheil_curve(result: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, temperature in enumerate(result.temperatures):
        row: dict[str, Any] = {
            "T, °C": float(temperature) - 273.15,
            "Доля твёрдого": float(result.fraction_solid[index]),
        }
        for element, values in result.x_liquid.items():
            row[f"x(LIQUID,{element})"] = float(values[index])
        for phase, values in sorted(result.cum_phase_amounts.items()):
            if float(values[-1]) > 1.0e-9:
                row[f"накоплено {phase}"] = float(values[index])
        rows.append(row)
    return pd.DataFrame(rows)


def temperature_at_fraction(curve: pd.DataFrame, target: float) -> float:
    """Температура при заданной доле твёрдого, линейно между шагами."""

    solid = curve["Доля твёрдого"].to_numpy(dtype=float)
    temperature = curve["T, °C"].to_numpy(dtype=float)
    for (f1, t1), (f2, t2) in zip(zip(solid, temperature), zip(solid[1:], temperature[1:])):
        if f1 <= target <= f2 and f2 != f1:
            return t1 + (target - f1) * (t2 - t1) / (f2 - f1)
    return math.nan


def kou_criterion(curve: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """Критерий Kou: |dT/d(fs^0.5)| в области fs = 0,9…0,99.

    Чем больше величина, тем выше склонность к горячим трещинам: последняя
    жидкость охлаждается быстрее, чем успевает подпитывать междендритные
    промежутки.
    """

    solid = curve["Доля твёрдого"].to_numpy(dtype=float)
    temperature = curve["T, °C"].to_numpy(dtype=float)
    root = np.sqrt(np.clip(solid, 0.0, 1.0))
    rows: list[dict[str, Any]] = []
    peak = 0.0
    for index in range(1, len(solid)):
        if not (KOU_WINDOW[0] <= solid[index] <= KOU_WINDOW[1]):
            continue
        d_root = root[index] - root[index - 1]
        if abs(d_root) < 1.0e-12:
            continue
        value = abs((temperature[index] - temperature[index - 1]) / d_root)
        rows.append({
            "Доля твёрдого": solid[index],
            "T, °C": temperature[index],
            "|dT/d(fs^0.5)|, K": value,
        })
        peak = max(peak, value)
    return peak, pd.DataFrame(rows)


def terminal_phases(result: Any, curve: pd.DataFrame) -> pd.DataFrame:
    """Фазы, образующиеся в последние 5 % затвердевания, и их температуры."""

    solid = np.asarray(result.fraction_solid, dtype=float)
    temperatures = np.asarray(result.temperatures, dtype=float) - 273.15
    tail = solid >= 0.95
    rows: list[dict[str, Any]] = []
    for phase, amounts in sorted(result.phase_amounts.items()):
        values = np.asarray(amounts, dtype=float)
        in_tail = float(values[tail].sum())
        if in_tail <= 1.0e-9:
            continue
        appearing = [
            temperatures[index]
            for index in range(len(values))
            if values[index] > 1.0e-9
        ]
        rows.append({
            "Фаза": phase,
            "Доля, образовавшаяся после fs=0,95": in_tail,
            "Всего за затвердевание": float(values.sum()),
            "T появления, °C": max(appearing) if appearing else math.nan,
            "T конца, °C": min(appearing) if appearing else math.nan,
        })
    del curve
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Общее
# --------------------------------------------------------------------------- #


def write_csv(table: pd.DataFrame, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    table.to_csv(path, index=False, encoding="utf-8-sig", sep=";", decimal=",")
    log(f"записано: {path.relative_to(ROOT)} ({len(table)} строк)")
    return path


def write_json(payload: Any, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"записано: {path.relative_to(ROOT)}")
    return path


def load_progress() -> dict[str, Any]:
    if not PROGRESS_PATH.is_file():
        return {}
    try:
        return json.loads(PROGRESS_PATH.read_text("utf-8"))
    except json.JSONDecodeError:
        return {}


def save_progress(progress: Mapping[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# B1
# --------------------------------------------------------------------------- #


def solidification_summary(
    ctx: Context,
    mole: Mapping[str, float],
    label: str,
) -> tuple[dict[str, Any], pd.DataFrame, Any]:
    result, payload = scheil_result(ctx, mole, label)
    curve = scheil_curve(result)
    peak, kou_table = kou_criterion(curve)
    marks = {
        f"T при fs={mark:.2f}, °C": round(temperature_at_fraction(curve, mark), 1)
        for mark in FS_MARKS
    }
    liquidus = float(payload["liquidus_c"])
    end_c = float(curve["T, °C"].min())
    summary: dict[str, Any] = {
        "состав": label,
        "равновесный ликвидус, °C": round(liquidus, 1),
        "старт Шейля, °C": round(float(payload["start_c"]), 1),
        "шагов": int(payload["steps"]),
        **marks,
        "T конца затвердевания, °C": round(end_c, 1),
        "интервал по Шейлю (ликвидус − T при fs=0,99), K": round(
            liquidus - temperature_at_fraction(curve, 0.99), 1
        ),
        "максимум |dT/d(fs^0.5)| при fs 0,9…0,99, K": round(peak, 1),
        "макс. шаг по T в хвосте fs>0,9, K": round(
            float(
                np.max(
                    np.abs(
                        np.diff(
                            curve.loc[curve["Доля твёрдого"] > 0.9, "T, °C"].to_numpy(
                                dtype=float
                            )
                        )
                    )
                )
            )
            if (curve["Доля твёрдого"] > 0.9).sum() > 1
            else math.nan,
            2,
        ),
    }
    return summary, kou_table, result


def step_b1(ctx: Context) -> None:
    mole = wt_to_mole(ctx, full_wt())
    summary, kou_table, result = solidification_summary(ctx, mole, "контрольный состав")
    curve = scheil_curve(result)
    write_csv(curve, "b1_scheil_curve.csv")
    write_csv(kou_table, "b1_kou.csv")
    write_csv(terminal_phases(result, curve), "b1_terminal_phases.csv")
    write_json(summary, "b1_summary.json")

    figure, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].plot(curve["Доля твёрдого"], curve["T, °C"], linewidth=1.8)
    for mark in FS_MARKS:
        temperature = temperature_at_fraction(curve, mark)
        if temperature == temperature:
            axes[0].axvline(mark, color="grey", linewidth=0.7, linestyle=":")
            axes[0].annotate(
                f"fs={mark:g}\n{temperature:.0f} °C",
                (mark, temperature),
                fontsize=7,
                ha="right",
            )
    axes[0].set_xlabel("доля твёрдого")
    axes[0].set_ylabel("температура, °C")
    axes[0].grid(alpha=0.3)
    axes[0].set_title("Затвердевание по Шейлю, контрольный состав")

    if not kou_table.empty:
        axes[1].plot(
            kou_table["Доля твёрдого"], kou_table["|dT/d(fs^0.5)|, K"],
            marker="o", linewidth=1.6,
        )
    axes[1].set_xlabel("доля твёрдого")
    axes[1].set_ylabel("|dT/d(fs^0.5)|, K")
    axes[1].grid(alpha=0.3)
    axes[1].set_title("Критерий Kou в области fs = 0,9…0,99")
    figure.tight_layout()
    figure.savefig(OUT / "b1_solidification.png", dpi=150)
    plt.close(figure)


# --------------------------------------------------------------------------- #
# B2
# --------------------------------------------------------------------------- #


SULFUR_LEVELS = (0.020, 0.010, 0.005, 0.002)
MANGANESE_LEVELS = (0.50, 0.20)


def step_b2(ctx: Context) -> None:
    rows: list[dict[str, Any]] = []
    sulphide_rows: list[dict[str, Any]] = []

    cases: list[tuple[str, dict[str, float]]] = [
        (f"S={sulfur:.3f} %, Mn=0,50 %", {"S": sulfur}) for sulfur in SULFUR_LEVELS
    ]
    cases += [
        (f"S=0,020 %, Mn={manganese:.2f} %", {"S": 0.020, "MN": manganese})
        for manganese in MANGANESE_LEVELS
        if manganese != CONTROL_WT["MN"]
    ]

    for label, overrides in cases:
        mole = wt_to_mole(ctx, full_wt(overrides))
        summary, _kou, result = solidification_summary(ctx, mole, label)
        rows.append(summary)
        write_csv(pd.DataFrame(rows), "b2_sulfur.csv")

        amounts = {
            phase: float(np.asarray(values, dtype=float).sum())
            for phase, values in result.phase_amounts.items()
        }
        for phase, amount in sorted(amounts.items()):
            if amount <= 1.0e-9 or phase not in {"MNS_Q", "TIS", "TI4C2S2", "CU2S", "FES_P", "PYRR", "DISULF", "DIGENITE"}:
                continue
            sulphide_rows.append({
                "Случай": label,
                "Сульфид": phase,
                "Мольная доля за затвердевание": amount,
            })
        write_csv(pd.DataFrame(sulphide_rows), "b2_sulphides.csv")

    table = pd.DataFrame(rows)
    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    sulfur_table = table[table["состав"].str.contains("Mn=0,50")]
    sulfur_values = [float(name.split("=")[1].split(" ")[0].replace(",", ".")) for name in sulfur_table["состав"]]
    axes[0].plot(sulfur_values, sulfur_table["интервал по Шейлю (ликвидус − T при fs=0,99), K"],
                 marker="o", linewidth=1.8)
    axes[0].set_xlabel("сера, масс. %")
    axes[0].set_ylabel("интервал кристаллизации по Шейлю, K")
    axes[0].grid(alpha=0.3)
    axes[0].set_title("Эффективный интервал против содержания серы")

    axes[1].plot(sulfur_values, sulfur_table["максимум |dT/d(fs^0.5)| при fs 0,9…0,99, K"],
                 marker="s", linewidth=1.8, color="#b03a2e")
    axes[1].set_xlabel("сера, масс. %")
    axes[1].set_ylabel("максимум |dT/d(fs^0.5)|, K")
    axes[1].grid(alpha=0.3)
    axes[1].set_title("Критерий Kou против содержания серы")
    figure.tight_layout()
    figure.savefig(OUT / "b2_sulfur.png", dpi=150)
    plt.close(figure)


# --------------------------------------------------------------------------- #
# B3
# --------------------------------------------------------------------------- #


B3_MARKS = (0.9, 0.95, 0.99)


def _solid_composition_at(result: Any, target: float) -> dict[str, float] | None:
    """Состав твёрдой фазы FCC_A1 при заданной доле твёрдого."""

    solid = np.asarray(result.fraction_solid, dtype=float)
    columns = result.phase_compositions.get("FCC_A1")
    if columns is None:
        return None
    index = int(np.argmin(np.abs(solid - target)))
    composition = {
        str(element).upper(): float(np.asarray(values, dtype=float)[index])
        for element, values in columns.items()
    }
    total = sum(value for value in composition.values() if value > 0.0)
    if total <= 0.0:
        return None
    return {
        element: value / total
        for element, value in composition.items()
        if value > 0.0
    }


def step_b3(ctx: Context) -> None:
    nominal = wt_to_mole(ctx, full_wt())
    result, _payload = scheil_result(ctx, nominal, "контрольный состав")

    homogeneous_solidus = solidus_c(ctx, nominal)
    log(f"B3: равновесный солидус номинального состава {homogeneous_solidus:.1f} °C")

    rows: list[dict[str, Any]] = [{
        "Состояние": "гомогенизированное (номинальный состав)",
        "fs": math.nan,
        **{f"x({element})": nominal.get(element, 0.0)
           for element in ("CR", "MO", "NI", "NB", "TI", "C", "SI")},
        "Локальный солидус, °C": round(homogeneous_solidus, 1),
        "Разница с гомогенизированным, K": 0.0,
    }]
    write_csv(pd.DataFrame(rows), "b3_local_solidus.csv")

    for mark in B3_MARKS:
        composition = _solid_composition_at(result, mark)
        if composition is None:
            log(f"B3: нет состава твёрдой фазы при fs={mark}")
            continue
        try:
            local = solidus_c(ctx, composition)
        except RuntimeError as error:
            log(f"B3: fs={mark}: {error}")
            continue
        rows.append({
            "Состояние": f"литое, междендритный участок (fs={mark:g})",
            "fs": mark,
            **{f"x({element})": composition.get(element, 0.0)
               for element in ("CR", "MO", "NI", "NB", "TI", "C", "SI")},
            "Локальный солидус, °C": round(local, 1),
            "Разница с гомогенизированным, K": round(local - homogeneous_solidus, 1),
        })
        log(f"B3: fs={mark}: локальный солидус {local:.1f} °C "
            f"({local - homogeneous_solidus:+.1f} K)")
        write_csv(pd.DataFrame(rows), "b3_local_solidus.csv")

    table = pd.DataFrame(rows)
    write_json({
        "равновесный солидус гомогенизированного, °C": round(homogeneous_solidus, 1),
        "минимальный локальный солидус, °C": round(
            float(table["Локальный солидус, °C"].min()), 1
        ),
        "потолок нагрева в литом состоянии, °C": round(
            float(table["Локальный солидус, °C"].min()) - 20.0, 1
        ),
        "потолок нагрева после гомогенизации, °C": round(
            homogeneous_solidus - 20.0, 1
        ),
        "запас, взятый на неопределённость, K": 20.0,
    }, "b3_summary.json")

    figure, ax = plt.subplots(figsize=(8, 5))
    local_rows = table.dropna(subset=["fs"])
    ax.plot(local_rows["fs"], local_rows["Локальный солидус, °C"],
            marker="o", linewidth=1.8, label="литое состояние")
    ax.axhline(homogeneous_solidus, color="#2e86c1", linestyle="--",
               label=f"гомогенизированное, {homogeneous_solidus:.0f} °C")
    ax.set_xlabel("доля твёрдого, при которой взят состав")
    ax.set_ylabel("локальный солидус, °C")
    ax.grid(alpha=0.3)
    ax.legend()
    ax.set_title("Потолок нагрева: литое против гомогенизированного")
    figure.tight_layout()
    figure.savefig(OUT / "b3_local_solidus.png", dpi=150)
    plt.close(figure)


# --------------------------------------------------------------------------- #
# Точка входа
# --------------------------------------------------------------------------- #


STEPS = {"B1": step_b1, "B2": step_b2, "B3": step_b3}
ORDER = ("B1", "B2", "B3")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="all", help="B1, B2, B3, all; через запятую")
    parser.add_argument("--force", action="store_true", help="пересчитать отмеченное")
    parser.add_argument("--scheil-step", type=float, default=None,
                        help="шаг по температуре в расчёте Шейля, K")
    arguments = parser.parse_args(argv)

    global SCHEIL_STEP_K

    if os.environ.get("PYTHONHASHSEED") != "0":
        log("ВНИМАНИЕ: PYTHONHASHSEED != 0")
    if arguments.scheil_step:
        SCHEIL_STEP_K = float(arguments.scheil_step)
    log(f"шаг Шейля: {SCHEIL_STEP_K} K")

    selected = (
        list(ORDER)
        if arguments.only.strip().lower() == "all"
        else [item.strip().upper() for item in arguments.only.split(",") if item.strip()]
    )
    unknown = [item for item in selected if item not in STEPS]
    if unknown:
        parser.error(f"неизвестные пункты: {', '.join(unknown)}")

    OUT.mkdir(parents=True, exist_ok=True)
    ctx = Context()
    progress = load_progress()
    failures: dict[str, str] = {}

    for item in selected:
        entry = progress.get(item)
        if entry and entry.get("статус") == "готов" and not arguments.force:
            log(f"пункт {item} пропущен, посчитан ранее ({entry.get('завершён')})")
            continue
        log(f"=== пункт {item} ===")
        started = time.perf_counter()
        error_text: str | None = None
        try:
            STEPS[item](ctx)
        except Exception as error:
            import traceback

            error_text = f"{type(error).__name__}: {error}"
            failures[item] = error_text
            log(f"пункт {item} УПАЛ: {error_text}")
            traceback.print_exc()
        seconds = time.perf_counter() - started
        progress[item] = {
            "статус": "не выполнен" if error_text else "готов",
            "завершён": time.strftime("%Y-%m-%d %H:%M:%S"),
            "минут": round(seconds / 60.0, 2),
        }
        if error_text:
            progress[item]["ошибка"] = error_text
        save_progress(progress)
        log(f"пункт {item}: {seconds / 60.0:.1f} мин")
        gc.collect()

    log("--- сводка ---")
    log(f"упало: {', '.join(failures) or 'нет'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
