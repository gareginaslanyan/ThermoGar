#!/usr/bin/env python3
"""Волна 11A — закрытие расчётных вопросов по сплаву ХН62М(Sc)-ВИ.

Задача `tasks/WAVE11A_TECH_OPUS.md`. Модуль намеренно отделён от
`tools/study_hn62m_tech.py` (волна 10) и `tools/study_hn62m.py` (волна 9):
он их не переписывает, а достраивает, поэтому волны остаются сравнимыми
построчно, а слияние ветки волны 10 в эту ветку не даёт конфликтов.

Запуск (интерпретатор — venv основного репозитория, PYTHONHASHSEED=0):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 ^
        tools\\study_hn62m_wave11.py --only a1

Память. В волне 9 машину трижды снимало по нехватке памяти, воркер здесь один,
поэтому:

* каждый тяжёлый подпункт считается в отдельном дочернем процессе — память
  возвращает операционная система, а не сборщик мусора;
* результат каждого равновесия дописывается в кэш на диск сразу, до перехода к
  следующей температуре, поэтому обрыв не теряет посчитанного;
* после каждого равновесия результат pycalphad освобождается явно.

Пункты идемпотентны: посчитанный подпункт отмечается в
`results/hn62m_tech/_progress.json` и при повторном запуске пропускается
(пересчёт — ключом ``--force``).
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

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

# Контрольный состав волны 11A, масс. %; никель — основа.
CONTROL_WT: dict[str, float] = {
    "C": 0.005, "SI": 0.10, "MN": 0.50, "S": 0.020, "CR": 23.5,
    "MO": 13.0, "NB": 0.06, "AL": 0.25, "TI": 0.10, "FE": 0.50,
}
COMPONENTS: tuple[str, ...] = (
    "NI", "CR", "MO", "C", "SI", "MN", "S", "NB", "AL", "TI", "FE", "VA",
)
ELEMENTS: tuple[str, ...] = tuple(name for name in COMPONENTS if name != "VA")

# Пара порядок/беспорядок BCC_B2/BCC_A2 в mc_ni не строится, когда в системе
# есть внедрённый углерод: pycalphad поднимает ValueError ещё на этапе Model.
# Запасной список на случай, когда модуль ремонта базы (волна 10) недоступен.
UNBUILDABLE_PHASES = ("BCC_B2",)

# --- A1 -------------------------------------------------------------------- #

A1_PDENS = (50, 100, 200, 500)
A1_TOLERANCE_K = 0.1          # точность половинного деления, постановка A1
A1_LIQUIDUS_BRACKET = (1200.0, 1500.0)
A1_SOLIDUS_BRACKET = (1000.0, 1450.0)
# Порог «фаза присутствует» в долях молей. Половинное деление сравнивает долю
# LIQUID именно с ним, поэтому он вынесен в константу и попадает в отчёт.
A1_PRESENT_FLOOR = 1.0e-6

# Метод волны 9: скан по равномерной сетке и линейная интерполяция кривой доли
# жидкости к уровням 0,999 (ликвидус) и 1e-4 (солидус). Значения взяты из
# `tools/study_hn62m.py` (SOLIDIFICATION_TEMPERATURES, step3) без изменений.
A1_WAVE9_GRID = tuple(1200.0 + 5.0 * index for index in range(51))  # 1200…1450
A1_WAVE9_LIQUIDUS_LEVEL = 0.999
A1_WAVE9_SOLIDUS_LEVEL = 1.0e-4


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


# --------------------------------------------------------------------------- #
# База и состав
# --------------------------------------------------------------------------- #


class Context:
    """Разобранная база, список фаз и молярные массы.

    Ремонт базы (`thermogar_database_repair`) появился в волне 10. Если модуль
    в дереве есть — используется он, и список фаз получается ровно тот же, что
    у волны 10; если нет — работает запасной путь волны 9. Какой путь выбран,
    пишется в лог и в сводку подпункта, чтобы числа нельзя было спутать.
    """

    def __init__(self) -> None:
        from pycalphad import Database
        from pycalphad.core.utils import filter_phases, unpack_species

        started = time.perf_counter()
        self.path = ROOT / DB_REL
        self.db = Database(str(self.path))
        phases = sorted(filter_phases(self.db, unpack_species(self.db, list(COMPONENTS))))

        try:
            import thermogar_database_repair as repair
        except ImportError:
            self.repair_available = False
            removed = [name for name in UNBUILDABLE_PHASES if name in phases]
            phases = [name for name in phases if name not in UNBUILDABLE_PHASES]
        else:
            self.repair_available = True
            repair.repair_database(self.db, database_label=self.path.name)
            phases, removed = repair.drop_broken_order_disorder(
                self.db, list(COMPONENTS), phases
            )

        self.phases = list(phases)
        self.excluded_phases = sorted(removed)
        self.masses = {
            element: float(self.db.refstates[element]["mass"]) for element in ELEMENTS
        }
        log(
            f"база разобрана за {time.perf_counter() - started:.1f} с; "
            f"фаз {len(self.phases)}; исключено {self.excluded_phases or 'нет'}; "
            f"ремонт базы {'доступен' if self.repair_available else 'недоступен'}"
        )


def full_wt(overrides: Mapping[str, float] | None = None) -> dict[str, float]:
    values = dict(CONTROL_WT)
    if overrides:
        for element, value in overrides.items():
            values[element.upper()] = float(value)
    values = {element: value for element, value in values.items() if value > 0.0}
    values[BALANCE] = 100.0 - sum(values.values())
    if values[BALANCE] <= 0.0:
        raise ValueError("Сумма легирующих превысила 100 %.")
    return values


def wt_to_mole(ctx: Context, wt_percent: Mapping[str, float]) -> dict[str, float]:
    from thermogar_equilibrium_core import mass_to_mole_fractions

    names = sorted(wt_percent)
    mass = tuple((element, wt_percent[element] / 100.0) for element in names)
    masses = tuple((element, ctx.masses[element]) for element in names)
    return {element: value for element, value in mass_to_mole_fractions(mass, masses)}


def independent_x(mole: Mapping[str, float]) -> dict[str, float]:
    return {
        element: value for element, value in sorted(mole.items()) if element != BALANCE
    }


def composition_id(mole: Mapping[str, float]) -> str:
    payload = {element: round(float(value), 9) for element, value in sorted(mole.items())}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Равновесие с кэшем на диске
# --------------------------------------------------------------------------- #


class EquilibriumCache:
    """Кэш равновесий, дописываемый построчно.

    Ключ — плотность выборки, состав и температура: только они меняют числа.
    Строка уходит на диск сразу после расчёта точки, поэтому обрыв по памяти
    теряет самое большее одну точку.
    """

    def __init__(self, pdens: int) -> None:
        CACHE.mkdir(parents=True, exist_ok=True)
        self.pdens = int(pdens)
        self.path = CACHE / f"a1_eq_pdens{self.pdens}.jsonl"
        self.records: dict[str, dict[str, float]] = {}
        self.hits = 0
        self.misses = 0
        if self.path.is_file():
            for line in self.path.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                self.records[payload["key"]] = payload["fractions"]
            log(f"кэш pdens={self.pdens}: {len(self.records)} точек")

    @staticmethod
    def key(mole: Mapping[str, float], temperature_c: float) -> str:
        return f"{composition_id(mole)}|{temperature_c:.4f}"

    def get(self, mole: Mapping[str, float], temperature_c: float) -> dict[str, float] | None:
        record = self.records.get(self.key(mole, temperature_c))
        if record is not None:
            self.hits += 1
        return record

    def put(
        self, mole: Mapping[str, float], temperature_c: float, fractions: Mapping[str, float]
    ) -> None:
        key = self.key(mole, temperature_c)
        self.records[key] = dict(fractions)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"key": key, "T_C": temperature_c, "pdens": self.pdens,
                     "fractions": dict(fractions)},
                    ensure_ascii=False, sort_keys=True,
                ) + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        self.misses += 1


def solve(
    ctx: Context,
    mole: Mapping[str, float],
    temperature_c: float,
    pdens: int,
    cache: EquilibriumCache | None = None,
) -> dict[str, float]:
    """Мольные доли фаз в равновесии при заданной температуре."""

    if cache is not None:
        cached = cache.get(mole, temperature_c)
        if cached is not None:
            return dict(cached)

    from pycalphad import equilibrium, variables as v

    conditions: dict[Any, float] = {
        v.N: 1.0, v.P: 101325.0, v.T: float(temperature_c) + 273.15,
    }
    conditions.update(
        {v.X(element): value for element, value in independent_x(mole).items()}
    )
    result = equilibrium(
        ctx.db, list(COMPONENTS), ctx.phases, conditions, calc_opts={"pdens": int(pdens)}
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

    if cache is not None:
        cache.put(mole, temperature_c, aggregated)
    return aggregated


# --------------------------------------------------------------------------- #
# A1. Ликвидус и солидус половинным делением
# --------------------------------------------------------------------------- #


def _bisect(
    predicate,
    low: float,
    high: float,
    tolerance: float,
    low_expected: bool,
    high_expected: bool,
    what: str,
) -> tuple[float, int]:
    """Половинное деление по монотонному признаку.

    ``predicate`` возвращает булев признак; ожидается, что на ``low`` он равен
    ``low_expected``, на ``high`` — ``high_expected``. Скобка проверяется, а не
    предполагается: если признак на краю не тот, считать нечего и функция
    поднимает ошибку, а не возвращает середину заведомо неверного отрезка.
    Возвращает температуру и число вычисленных равновесий.
    """

    calls = 0

    def check(temperature: float) -> bool:
        nonlocal calls
        calls += 1
        return predicate(temperature)

    if check(low) != low_expected:
        raise RuntimeError(f"{what}: признак на нижнем крае {low} °C не тот, что ожидался")
    if check(high) != high_expected:
        raise RuntimeError(f"{what}: признак на верхнем крае {high} °C не тот, что ожидался")

    while high - low > tolerance:
        middle = 0.5 * (low + high)
        if check(middle) == high_expected:
            high = middle
        else:
            low = middle
    return 0.5 * (low + high), calls


def a1_liquidus(
    ctx: Context, mole: Mapping[str, float], pdens: int, cache: EquilibriumCache
) -> tuple[float, int]:
    """Ликвидус: нижняя граница области, где расплав полностью жидкий."""

    def fully_liquid(temperature_c: float) -> bool:
        fractions = solve(ctx, mole, temperature_c, pdens, cache)
        return fractions.get("LIQUID", 0.0) >= 1.0 - A1_PRESENT_FLOOR

    low, high = A1_LIQUIDUS_BRACKET
    return _bisect(
        fully_liquid, low, high, A1_TOLERANCE_K,
        low_expected=False, high_expected=True, what="ликвидус",
    )


def a1_solidus(
    ctx: Context, mole: Mapping[str, float], pdens: int, cache: EquilibriumCache
) -> tuple[float, int]:
    """Солидус: температура появления первой жидкости при нагреве."""

    def has_liquid(temperature_c: float) -> bool:
        fractions = solve(ctx, mole, temperature_c, pdens, cache)
        return fractions.get("LIQUID", 0.0) > A1_PRESENT_FLOOR

    low, high = A1_SOLIDUS_BRACKET
    return _bisect(
        has_liquid, low, high, A1_TOLERANCE_K,
        low_expected=False, high_expected=True, what="солидус",
    )


def a1_one_pdens(pdens: int) -> dict[str, Any]:
    """Ликвидус и солидус при одной плотности выборки. Считается в потомке."""

    ctx = Context()
    mole = wt_to_mole(ctx, full_wt())
    cache = EquilibriumCache(pdens)

    started = time.perf_counter()
    liquidus, liquidus_calls = a1_liquidus(ctx, mole, pdens, cache)
    liquidus_seconds = time.perf_counter() - started
    log(f"pdens={pdens}: ликвидус {liquidus:.2f} °C "
        f"({liquidus_calls} равновесий, {liquidus_seconds:.1f} с)")

    started = time.perf_counter()
    solidus, solidus_calls = a1_solidus(ctx, mole, pdens, cache)
    solidus_seconds = time.perf_counter() - started
    log(f"pdens={pdens}: солидус {solidus:.2f} °C "
        f"({solidus_calls} равновесий, {solidus_seconds:.1f} с)")

    return {
        "pdens": int(pdens),
        "ликвидус, °C": round(liquidus, 2),
        "солидус, °C": round(solidus, 2),
        "интервал, K": round(liquidus - solidus, 2),
        "равновесий": liquidus_calls + solidus_calls,
        "из кэша": cache.hits,
        "посчитано": cache.misses,
        "время, с": round(liquidus_seconds + solidus_seconds, 1),
        "фаз в наборе": len(ctx.phases),
        "ремонт базы": bool(ctx.repair_available),
    }


# --------------------------------------------------------------------------- #
# A1. Воспроизведение метода волны 9
# --------------------------------------------------------------------------- #


def _crossing(temperatures: Sequence[float], values: Sequence[float], level: float) -> float:
    """Температура пересечения уровня — копия `study_hn62m.py::_crossing`.

    Копия, а не импорт: воспроизводить метод волны 9 нужно ровно тем кодом,
    каким он был посчитан, а `study_hn62m.py` в этой ветке ещё может меняться.
    """

    ordered = sorted(zip(temperatures, values), key=lambda pair: -pair[0])
    crossings: list[float] = []
    for (t1, v1), (t2, v2) in zip(ordered, ordered[1:]):
        if (v1 - level) * (v2 - level) <= 0.0 and v1 != v2:
            crossings.append(t1 + (level - v1) * (t2 - t1) / (v2 - v1))
    if not crossings:
        return math.nan
    if len(crossings) > 1:
        log(f"уровень {level:g} пересекается {len(crossings)} раз "
            f"({', '.join(f'{value:.1f} °C' for value in crossings)}): кривая немонотонна")
        return math.nan
    return crossings[0]


def a1_wave9_method(pdens: int = 100) -> dict[str, Any]:
    """Скан по сетке 5 K и линейная интерполяция — как считала волна 9."""

    ctx = Context()
    mole = wt_to_mole(ctx, full_wt())
    cache = EquilibriumCache(pdens)
    curve_path = OUT / "a1_wave9_curve.csv"

    started = time.perf_counter()
    rows: list[dict[str, float]] = []
    for temperature in sorted(A1_WAVE9_GRID, reverse=True):
        fractions = solve(ctx, mole, temperature, pdens, cache)
        rows.append({
            "T, °C": temperature,
            "доля LIQUID": fractions.get("LIQUID", 0.0),
        })
        # Кривая дописывается на диск после каждой точки: скан из 51 точки на
        # десятикомпонентном составе — это тот самый расчёт, на котором волну 9
        # трижды снимало по памяти.
        pd.DataFrame(rows).to_csv(curve_path, index=False, encoding="utf-8-sig")
    seconds = time.perf_counter() - started

    temperatures = [row["T, °C"] for row in rows]
    liquid = [row["доля LIQUID"] for row in rows]
    liquidus = _crossing(temperatures, liquid, A1_WAVE9_LIQUIDUS_LEVEL)
    solidus = _crossing(temperatures, liquid, A1_WAVE9_SOLIDUS_LEVEL)
    log(f"метод волны 9 при pdens={pdens}: ликвидус "
        f"{liquidus:.2f} °C, солидус {solidus:.2f} °C, {seconds:.1f} с")

    return {
        "pdens": int(pdens),
        "шаг сетки, K": 5.0,
        "уровень для ликвидуса": A1_WAVE9_LIQUIDUS_LEVEL,
        "уровень для солидуса": A1_WAVE9_SOLIDUS_LEVEL,
        "ликвидус, °C": None if liquidus != liquidus else round(liquidus, 2),
        "солидус, °C": None if solidus != solidus else round(solidus, 2),
        "интервал, K": (
            None if (liquidus != liquidus or solidus != solidus)
            else round(liquidus - solidus, 2)
        ),
        "точек сетки": len(rows),
        "время, с": round(seconds, 1),
        "кривая": curve_path.name,
    }


# --------------------------------------------------------------------------- #
# Ввод-вывод
# --------------------------------------------------------------------------- #


def write_csv(table: pd.DataFrame, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    table.to_csv(path, index=False, encoding="utf-8-sig")
    log(f"записано {path.relative_to(ROOT)} ({len(table)} строк)")
    return path


def write_json(payload: Any, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False), "utf-8"
    )
    log(f"записано {path.relative_to(ROOT)}")
    return path


def load_progress() -> dict[str, Any]:
    if PROGRESS_PATH.is_file():
        try:
            return json.loads(PROGRESS_PATH.read_text("utf-8"))
        except json.JSONDecodeError:
            log("_progress.json не разбирается, считаем пустым")
    return {}


def save_progress(progress: Mapping[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2, sort_keys=True), "utf-8"
    )


def run_child(arguments: Sequence[str]) -> dict[str, Any]:
    """Тяжёлый кусок — в отдельном процессе; результат приходит файлом.

    Возврат через файл, а не через stdout: лог подпункта должен идти на экран
    по мере счёта, а не копиться в трубе до конца работы потомка.
    """

    handoff = CACHE / f"child_{arguments[0].strip('-')}_{arguments[-1]}.json"
    CACHE.mkdir(parents=True, exist_ok=True)
    if handoff.is_file():
        handoff.unlink()
    environment = dict(os.environ, PYTHONHASHSEED="0")
    command = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
               *arguments, "--handoff", str(handoff)]
    completed = subprocess.run(command, env=environment, cwd=str(ROOT))
    if completed.returncode != 0 or not handoff.is_file():
        raise RuntimeError(
            f"потомок {' '.join(arguments)} завершился с кодом {completed.returncode}"
        )
    return json.loads(handoff.read_text("utf-8"))


# --------------------------------------------------------------------------- #
# Подпункт A1 целиком
# --------------------------------------------------------------------------- #


def plot_a1(table: pd.DataFrame, path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    axes[0].plot(table["pdens"], table["ликвидус, °C"], "o-", label="ликвидус")
    axes[0].plot(table["pdens"], table["солидус, °C"], "s-", label="солидус")
    axes[0].set_xscale("log")
    axes[0].set_xticks(list(table["pdens"]))
    axes[0].set_xticklabels([str(int(value)) for value in table["pdens"]])
    axes[0].set_xlabel("плотность стартовой выборки pdens")
    axes[0].set_ylabel("температура, °C")
    axes[0].set_title("Ликвидус и солидус ХН62М(Sc)-ВИ")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].plot(table["pdens"], table["интервал, K"], "d-", color="tab:red")
    axes[1].set_xscale("log")
    axes[1].set_xticks(list(table["pdens"]))
    axes[1].set_xticklabels([str(int(value)) for value in table["pdens"]])
    axes[1].set_xlabel("плотность стартовой выборки pdens")
    axes[1].set_ylabel("интервал кристаллизации, K")
    axes[1].set_title("Интервал кристаллизации")
    axes[1].grid(True, alpha=0.3)

    figure.suptitle("A1. Сходимость по плотности сетки, половинное деление 0,1 K")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


def converged_pdens(table: pd.DataFrame, threshold: float = 0.5) -> int | None:
    """Наименьший pdens, начиная с которого числа не меняются сверх порога.

    Сравнение идёт со **самым плотным** прогоном: «перестали меняться» значит
    «совпали с пределом», а не «совпали с соседом». Соседние точки могут
    случайно сойтись и на несошедшемся участке.
    """

    ordered = table.sort_values("pdens")
    reference = ordered.iloc[-1]
    for _, row in ordered.iterrows():
        liquidus_gap = abs(row["ликвидус, °C"] - reference["ликвидус, °C"])
        solidus_gap = abs(row["солидус, °C"] - reference["солидус, °C"])
        if liquidus_gap <= threshold and solidus_gap <= threshold:
            return int(row["pdens"])
    return None


def step_a1(force: bool = False) -> None:
    progress = load_progress()
    if progress.get("A1", {}).get("готов") and not force:
        log("A1 пропущен, посчитан ранее (--force для пересчёта)")
        return

    rows: list[dict[str, Any]] = []
    partial = OUT / "a1_pdens_convergence.csv"
    for pdens in A1_PDENS:
        log(f"A1: плотность выборки {pdens}")
        rows.append(run_child(["--a1-one", str(pdens)]))
        # Таблица переписывается после каждой плотности: если следующий прогон
        # снимет по памяти, посчитанное уже лежит на диске.
        pd.DataFrame(rows).to_csv(partial, index=False, encoding="utf-8-sig")
        log(f"A1: промежуточная таблица записана ({len(rows)} строк)")

    table = pd.DataFrame(rows)
    write_csv(table, "a1_pdens_convergence.csv")
    plot_a1(table, OUT / "a1_pdens_convergence.png")

    wave9 = run_child(["--a1-wave9", "100"])

    reference = table.sort_values("pdens").iloc[-1]
    summary: dict[str, Any] = {
        "подпункт": "A1. Сходимость ликвидуса и солидуса по плотности сетки",
        "метод": (
            "половинное деление по признаку «доля LIQUID ≥ 1 − 1e-6» (ликвидус) "
            "и «доля LIQUID > 1e-6» (солидус), точность "
            f"{A1_TOLERANCE_K} K, режим «все фазы»"
        ),
        "таблица": table.to_dict("records"),
        "pdens сходимости в пределах 0,5 K": converged_pdens(table, 0.5),
        "окончательный ликвидус, °C": float(reference["ликвидус, °C"]),
        "окончательный солидус, °C": float(reference["солидус, °C"]),
        "окончательный интервал, K": float(reference["интервал, K"]),
        "окончательные числа при pdens": int(reference["pdens"]),
        "метод волны 9, воспроизведение": wave9,
        "волна 9, опубликовано": {"ликвидус, °C": 1378.2, "солидус, °C": 1340.1},
        "волна 10, опубликовано": {"ликвидус, °C": 1375.0, "солидус, °C": 1344.3},
    }
    if wave9.get("ликвидус, °C") is not None:
        summary["метод волны 9 против публикации волны 9, K"] = {
            "ликвидус": round(wave9["ликвидус, °C"] - 1378.2, 2),
            "солидус": round(wave9["солидус, °C"] - 1340.1, 2),
        }
    write_json(summary, "a1_summary.json")

    progress["A1"] = {
        "готов": True,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pdens": list(A1_PDENS),
        "точность, K": A1_TOLERANCE_K,
        "режим набора фаз": "все фазы",
    }
    save_progress(progress)


# --------------------------------------------------------------------------- #
# Точка входа
# --------------------------------------------------------------------------- #


STEPS = {"a1": step_a1}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Волна 11A: расчёты по ХН62М")
    parser.add_argument("--only", default="all", help="a1, … ; через запятую")
    parser.add_argument("--force", action="store_true", help="пересчитать готовое")
    parser.add_argument("--a1-one", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--a1-wave9", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--handoff", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    if args.a1_one is not None:
        payload = a1_one_pdens(args.a1_one)
    elif args.a1_wave9 is not None:
        payload = a1_wave9_method(args.a1_wave9)
    else:
        payload = None

    if payload is not None:
        if args.handoff:
            Path(args.handoff).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), "utf-8"
            )
        return 0

    requested = [name.strip().lower() for name in args.only.split(",") if name.strip()]
    if requested == ["all"]:
        requested = list(STEPS)
    unknown = [name for name in requested if name not in STEPS]
    if unknown:
        parser.error(f"неизвестные подпункты: {', '.join(unknown)}")

    for name in requested:
        started = time.perf_counter()
        log(f"=== {name.upper()} ===")
        STEPS[name](force=args.force)
        log(f"=== {name.upper()} готов за {time.perf_counter() - started:.1f} с ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
