#!/usr/bin/env python3
"""Волна 13, задача 13-А — годится ли P_PHASE из mc_ni 2.036 для количественной
оценки в сплаве ЭК199-ВИ.

Задание `tasks/WAVE13_A_OPUS.md`. Четыре пункта, четыре префикса результатов:

* ``a1`` — состав P-фазы по базе во всём поле её устойчивости: прибит ли
  молибден к 12/56 = 21,43 ат. % и меняется ли только отношение Ni/Cr. Берутся
  все узлы сечений, где P-фаза устойчива, и все составы сплава волны 12, где
  она есть; для узлов сечений — ещё и заселённости подрешёток.
* ``a2`` — изотермические сечения Ni–Cr–Mo при 1100 и 1250 °C на сетке 2,5 ат. %
  в области Ni ≥ 15 ат. %; для каждого узла — набор устойчивых фаз. Сверх
  задания то же сечение при 700 °C: при 1100 и 1250 °C P-фазы в базе может не
  оказаться вовсе, и тогда пункту 1 не на чем стоять (отступление названо в
  отчёте).
* ``a3`` — δ-фаза NiMo (`D_NIMO`): где устойчива на сечениях, где на ребре
  Ni–Mo по температуре, и насколько далеки от устойчивости P_PHASE и D_NIMO в
  узлах экспериментального поля P-фазы.
* ``a4`` — оценки доли ТПУ-фазы по балансу молибдена при 580, 700 и 750 °C из
  равновесий волны 12 (`results/hn62m_wave12/e1_*.csv`); равновесий не считает.

Модуль не переписывает волну 12, а импортирует из неё формат таблиц, пороги,
плотность выборки, перевод состава в массовые проценты и замер памяти (волна 11).
Своими остались разбор базы на тройной системе (`Context` волны 11 привязан к
одиннадцатикомпонентному списку `COMPONENTS`), разбор точки с подрешётками и
служебные функции, привязанные к имени файла и к каталогу волны 13.

Запуск (интерпретатор — venv основного репозитория, PYTHONHASHSEED=0):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 ^
        tools\\study_hn62m_wave13_pphase.py --only a2,a1,a3,a4 --min-free-gib 2.5

Память. Порог входа — параметр задачи (`tasks/RULES.md`, «Память и
параллельность»), задаётся ключом `--min-free-gib`; умолчание — общая
константа `w12.MIN_FREE_GIB` (4,0 ГиБ), фактическое значение уходит в сводку.
Задание 13-А объявляет 2,5 ГиБ с обоснованием измеренным пиком равновесного
прогона 12-2 (1,355 ГиБ). Аварийный порог по ходу счёта — `w12.E1_ABORT_FREE_GIB`,
ключа не имеет и не понижается. Бюджет потока (1,5 ГиБ по заданию) — ещё одна
величина: потомок останавливается, если рабочий набор его самого превысил
бюджет; сделанное остаётся в кэше.

Кэш обязателен: каждая сошедшаяся точка уходит на диск сразу
(`cache/a2_points.jsonl`), ключ — температура и узел сетки.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import study_hn62m_wave11 as w11
import study_hn62m_wave12 as w12

ROOT = w12.ROOT
OUT = ROOT / "results" / "hn62m_wave13"
CACHE = OUT / "cache"
W12_OUT = w12.OUT

CSV_WRITE = dict(w12.CSV_WRITE)
CSV_READ = dict(w12.CSV_READ)
log = w12.log

DB_REL = w12.DB_REL

# Пороги памяти — общие константы волны 12; порог входа меняется только ключом.
MIN_FREE_GIB = w12.MIN_FREE_GIB
ABORT_FREE_GIB = w12.E1_ABORT_FREE_GIB
TASK_MIN_FREE_GIB = 2.5
JUSTIFY_PEAK_SET_GIB = 1.355
JUSTIFY_SOURCE = "results/hn62m_wave12/e1_memory_e1_1_force.json"
# Бюджет потока по заданию 13-А.
TASK_BUDGET_GIB = 1.5

# Плотность выборки и ряд повторов — волны 12-2.
PDENS = w12.E1_PDENS
RETRY_PDENS: tuple[int, ...] = tuple(w12.E1_RETRY_PDENS)
PRESENT_FLOOR = w12.E1_PRESENT_FLOOR
SUM_TOLERANCE = w12.E1_SUM_TOLERANCE

# --- тройная система -------------------------------------------------------- #

TERNARY_COMPONENTS: tuple[str, ...] = ("NI", "CR", "MO", "VA")
TERNARY_ELEMENTS: tuple[str, ...] = ("NI", "CR", "MO")

# Сетка: шаг 2,5 ат. %, то есть 40 шагов на 100 %; узел задаётся числом шагов
# по хрому и молибдену, никель — остаток.
GRID_STEPS = 40
STEP_AT = 100.0 / GRID_STEPS
NI_MIN_STEPS = 6  # 15 ат. %
# Нулевую мольную долю равновесие не принимает: на рёбрах треугольника вместо
# нуля ставится следовое значение. Названо в сводке.
EDGE_X = 1.0e-6

# Температуры сечений: две задания и одна сверх задания (см. докстроку).
TASK_SECTIONS_C: tuple[float, ...] = (1100.0, 1250.0)
EXTRA_SECTIONS_C: tuple[float, ...] = (700.0,)

# Ребро Ni–Mo по температуре для пункта 3: Mo 35…57,5 ат. %, 600…1300 °C.
EDGE_SCAN_C: tuple[float, ...] = tuple(600.0 + 50.0 * index for index in range(15))
EDGE_SCAN_MO_STEPS: tuple[int, ...] = tuple(range(14, 24))

# Фазы, для которых в каждом узле считается расстояние до устойчивости.
DISTANCE_PHASES: tuple[str, ...] = ("P_PHASE", "D_NIMO", "SIGMA", "MU_PHASE")
DISTANCE_PDENS = 3000

P_PHASE = "P_PHASE"
DELTA_PHASE = "D_NIMO"
# Подрешётки модели: 24 : 20 : 12 позиций.
P_SITES: tuple[int, ...] = (24, 20, 12)
P_MO_CEILING = 12.0 / 56.0
P_CR_FLOOR = 20.0 / 56.0

# Экспериментальное поле P-фазы при 1100 °C — числа из текста задания 13-А.
EXP_BOX = {"CR": (25.0, 30.0), "MO": (40.0, 45.0), "NI": (25.0, 33.0)}
EXP_BOX_T_C = 1100.0

# Составы реальной P-фазы, ат. %, — из текста задания 13-А.
REAL_P_COMPOSITIONS: tuple[tuple[str, dict[str, float]], ...] = (
    ("ХН62М-ВИ, 5000 ч при 700 °C (Гибадуллина и др., 2025, "
     "DOI 10.3390/app15116133, табл. 3; число из задания)",
     {"CR": 21.8, "NI": 37.6, "MO": 40.7}),
    ("Шумейкер 1957, тройная Mo–Ni–Cr P-фаза, 42 : 40 : 18 (число из задания)",
     {"MO": 42.0, "NI": 40.0, "CR": 18.0}),
)

# Температуры пункта 4 и имена фаз волны 12.
BALANCE_T_C: tuple[float, ...] = (580.0, 700.0, 750.0)
MATRIX_PHASE = w12.E1_MATRIX_PHASE


# --------------------------------------------------------------------------- #
# Сетка
# --------------------------------------------------------------------------- #


def node_at(steps_cr: int, steps_mo: int) -> dict[str, float]:
    steps_ni = GRID_STEPS - steps_cr - steps_mo
    return {"NI": steps_ni * STEP_AT, "CR": steps_cr * STEP_AT, "MO": steps_mo * STEP_AT}


def node_x(steps_cr: int, steps_mo: int) -> dict[str, float]:
    """Независимые мольные доли узла; ноль заменён следовым значением."""

    return {
        "CR": max(steps_cr / GRID_STEPS, EDGE_X),
        "MO": max(steps_mo / GRID_STEPS, EDGE_X),
    }


def section_nodes() -> list[tuple[int, int]]:
    return [
        (steps_cr, steps_mo)
        for steps_cr in range(GRID_STEPS - NI_MIN_STEPS + 1)
        for steps_mo in range(GRID_STEPS - NI_MIN_STEPS - steps_cr + 1)
    ]


def task_list(sections: Sequence[float], edge_scan: bool) -> list[tuple[float, int, int, str]]:
    tasks = [
        (float(temperature), steps_cr, steps_mo, "сечение")
        for temperature in sections
        for steps_cr, steps_mo in section_nodes()
    ]
    if edge_scan:
        seen = {(t, c, m) for t, c, m, _ in tasks}
        for temperature in EDGE_SCAN_C:
            for steps_mo in EDGE_SCAN_MO_STEPS:
                if (temperature, 0, steps_mo) not in seen:
                    tasks.append((temperature, 0, steps_mo, "ребро Ni–Mo"))
    return tasks


def point_key(temperature_c: float, steps_cr: int, steps_mo: int) -> str:
    return f"{temperature_c:.1f}|{steps_cr}|{steps_mo}"


# --------------------------------------------------------------------------- #
# База на тройной системе
# --------------------------------------------------------------------------- #


class TernaryContext:
    """Разбор базы и модели фаз для Ni–Cr–Mo.

    Путь тот же, что у `w11.Context`: `filter_phases`, ремонт базы
    `thermogar_database_repair`, отбрасывание несобираемых пар
    порядок/беспорядок. Отдельный класс нужен только потому, что `w11.Context`
    читает модульный список компонентов сплава.
    """

    def __init__(self) -> None:
        from pycalphad import Database, variables as v
        from pycalphad.codegen.phase_record_factory import PhaseRecordFactory
        from pycalphad.core.utils import filter_phases, instantiate_models, unpack_species
        import thermogar_database_repair as repair

        started = time.perf_counter()
        self.db = Database(str(ROOT / DB_REL))
        phases = sorted(filter_phases(self.db, unpack_species(self.db, list(TERNARY_COMPONENTS))))
        repair.repair_database(self.db, database_label=(ROOT / DB_REL).name)
        phases, removed = repair.drop_broken_order_disorder(
            self.db, list(TERNARY_COMPONENTS), phases
        )
        self.phases = list(phases)
        self.excluded_phases = sorted(removed)
        self.masses = {
            element: float(self.db.refstates[element]["mass"]) for element in TERNARY_ELEMENTS
        }
        self.models = instantiate_models(self.db, list(TERNARY_COMPONENTS), self.phases)
        self.phase_records = PhaseRecordFactory(
            self.db, list(TERNARY_COMPONENTS), [v.N, v.P, v.T], self.models
        )
        self.constituents = {
            name: [sorted(str(species.name) for species in sublattice)
                   for sublattice in self.models[name].constituents]
            for name in self.phases
        }
        self._samples: dict[tuple[float, str], tuple[np.ndarray, np.ndarray]] = {}
        log(f"тройная система: фаз {len(self.phases)}, исключено "
            f"{self.excluded_phases or 'нет'}, {time.perf_counter() - started:.1f} с")

    def samples(self, temperature_c: float, phase: str) -> tuple[np.ndarray, np.ndarray]:
        """Выборка энергии Гиббса фазы по её внутренним степеням свободы."""

        key = (float(temperature_c), phase)
        if key not in self._samples:
            from pycalphad import calculate

            result = calculate(
                self.db, list(TERNARY_COMPONENTS), [phase],
                T=float(temperature_c) + 273.15, P=101325.0, N=1.0,
                pdens=DISTANCE_PDENS, model=self.models, output="GM",
            )
            order = [str(name) for name in result.coords["component"].values]
            x = np.asarray(result.X.values, dtype=float).reshape(-1, len(order))
            gm = np.asarray(result.GM.values, dtype=float).reshape(-1)
            # Столбцы — в порядке TERNARY_ELEMENTS.
            x = x[:, [order.index(element) for element in TERNARY_ELEMENTS]]
            finite = np.isfinite(gm) & np.all(np.isfinite(x), axis=1)
            self._samples[key] = (x[finite], gm[finite])
        return self._samples[key]


def distance_to_stability(ctx: TernaryContext, temperature_c: float, phase: str,
                          mu: Mapping[str, float]) -> float | None:
    """min по составам фазы (G_m − Σ μ_i x_i), Дж/моль атомов.

    Ноль — фаза на касательной плоскости, то есть устойчива; положительное
    число — на столько фаза выше плоскости в самой выгодной точке выборки.
    Для устойчивой фазы число может выйти чуть больше нуля: выборка дискретна,
    а решатель доводит состав фазы точно.
    """

    if phase not in ctx.phases:
        return None
    x, gm = ctx.samples(temperature_c, phase)
    if not len(gm):
        return None
    potentials = np.array([float(mu[element]) for element in TERNARY_ELEMENTS])
    return float(np.min(gm - x @ potentials))


def solve_node(ctx: TernaryContext, temperature_c: float, steps_cr: int, steps_mo: int,
               pdens: int) -> dict[str, Any]:
    from pycalphad import equilibrium, variables as v

    started = time.perf_counter()
    conditions: dict[Any, float] = {
        v.N: 1.0, v.P: 101325.0, v.T: float(temperature_c) + 273.15,
    }
    conditions.update({v.X(element): value for element, value in node_x(steps_cr, steps_mo).items()})
    result = equilibrium(
        ctx.db, list(TERNARY_COMPONENTS), ctx.phases, conditions,
        model=ctx.models, phase_records=ctx.phase_records, calc_opts={"pdens": int(pdens)},
    )

    names = [str(name) for name in np.asarray(result.Phase.values, dtype=str).ravel()]
    amounts = np.asarray(result.NP.values, dtype=float).ravel()
    order = [str(name) for name in result.coords["component"].values]
    x_vertices = np.asarray(result.X.values, dtype=float).reshape(len(names), len(order))
    y_vertices = np.asarray(result.Y.values, dtype=float).reshape(len(names), -1)
    mu_values = np.asarray(result.MU.values, dtype=float).ravel()
    mu = {element: float(mu_values[order.index(element)]) for element in TERNARY_ELEMENTS}
    del result
    gc.collect()

    phases: dict[str, dict[str, Any]] = {}
    vertices: list[dict[str, Any]] = []
    for position, (name, amount) in enumerate(zip(names, amounts)):
        if not name or not np.isfinite(amount) or float(amount) <= PRESENT_FLOOR:
            continue
        composition = {
            element: float(x_vertices[position, order.index(element)])
            for element in TERNARY_ELEMENTS
        }
        bucket = phases.setdefault(name, {"мольная доля": 0.0,
                                          "x": {element: 0.0 for element in TERNARY_ELEMENTS}})
        bucket["мольная доля"] += float(amount)
        for element in TERNARY_ELEMENTS:
            bucket["x"][element] += float(amount) * composition[element]
        if name in (P_PHASE, DELTA_PHASE):
            flat = [float(value) for value in y_vertices[position] if np.isfinite(value)]
            sublattices: list[dict[str, float]] = []
            cursor = 0
            for species in ctx.constituents[name]:
                sublattices.append({
                    element: flat[cursor + index] for index, element in enumerate(species)
                })
                cursor += len(species)
            vertices.append({"фаза": name, "мольная доля": float(amount),
                             "x": composition, "подрешётки": sublattices})
    for bucket in phases.values():
        total = bucket["мольная доля"]
        bucket["x"] = {element: value / total for element, value in bucket["x"].items()}

    total = sum(bucket["мольная доля"] for bucket in phases.values())
    payload = {
        "T, °C": float(temperature_c),
        "шагов CR": int(steps_cr),
        "шагов MO": int(steps_mo),
        "узел, ат. %": node_at(steps_cr, steps_mo),
        "pdens": int(pdens),
        "сумма мольных долей фаз": float(total),
        "фазы": {name: phases[name] for name in sorted(phases)},
        "вершины P и D_NIMO": vertices,
        "мю, Дж/моль": mu,
        "секунд": time.perf_counter() - started,
    }
    if all(np.isfinite(value) for value in mu.values()):
        payload["расстояние до устойчивости, Дж/моль"] = {
            phase: distance_to_stability(ctx, temperature_c, phase, mu)
            for phase in DISTANCE_PHASES
        }
    else:
        payload["расстояние до устойчивости, Дж/моль"] = {phase: None for phase in DISTANCE_PHASES}
    return payload


def converged(payload: Mapping[str, Any]) -> bool:
    if not payload["фазы"]:
        return False
    return abs(float(payload["сумма мольных долей фаз"]) - 1.0) <= SUM_TOLERANCE


# --------------------------------------------------------------------------- #
# Кэш
# --------------------------------------------------------------------------- #


class PointCache:
    """Кэш узлов, дописываемый построчно, — как `w12.PointCache`, но с файлом
    волны 13 и ключом «температура | узел сетки»."""

    def __init__(self) -> None:
        CACHE.mkdir(parents=True, exist_ok=True)
        self.path = CACHE / "a2_points.jsonl"
        self.records: dict[str, dict[str, Any]] = {}
        if self.path.is_file():
            for line in self.path.read_text("utf-8").splitlines():
                if line.strip():
                    record = json.loads(line)
                    self.records[record["key"]] = record["payload"]
            log(f"кэш узлов: {len(self.records)}")

    def put_node(self, key: str, payload: Mapping[str, Any]) -> None:
        self.records[key] = dict(payload)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"key": key, "payload": payload},
                                    ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def load_points() -> list[dict[str, Any]]:
    path = CACHE / "a2_points.jsonl"
    records: dict[str, dict[str, Any]] = {}
    if path.is_file():
        for line in path.read_text("utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                records[record["key"]] = record["payload"]
    return list(records.values())


# --------------------------------------------------------------------------- #
# Потомок: сечения и ребро Ni–Mo
# --------------------------------------------------------------------------- #


def own_rss_gib() -> float:
    import psutil

    return psutil.Process(os.getpid()).memory_info().rss / 1024.0 ** 3


def compute_nodes(sections: Sequence[float], edge_scan: bool, min_free_gib: float,
                  budget_gib: float, force: bool) -> dict[str, Any]:
    cache = PointCache()
    if force:
        cache.records.clear()
        if cache.path.is_file():
            cache.path.unlink()

    tasks = task_list(sections, edge_scan)
    todo = [task for task in tasks
            if point_key(*task[:3]) not in cache.records]
    log(f"узлов всего {len(tasks)}, в кэше {len(tasks) - len(todo)}, считать {len(todo)}")
    stopped: dict[str, Any] | None = None
    failed: list[dict[str, Any]] = []
    if not todo:
        return {"узлов всего": len(tasks), "посчитано сейчас": 0, "не сошлись": failed,
                "остановка": None}

    free = w12.free_gib()
    if free < float(min_free_gib):
        return {"узлов всего": len(tasks), "посчитано сейчас": 0, "не сошлись": failed,
                "остановка": f"свободной физической памяти {free:.2f} ГиБ при пороге входа "
                             f"{float(min_free_gib):.1f} ГиБ; база не разбиралась"}

    ctx = TernaryContext()
    done = 0
    started = time.perf_counter()
    for temperature, steps_cr, steps_mo, kind in todo:
        free = w12.free_gib()
        if free < ABORT_FREE_GIB:
            stopped = (f"свободной физической памяти {free:.2f} ГиБ, ниже аварийного порога "
                       f"{ABORT_FREE_GIB:.1f} ГиБ; остаток не считался")
            break
        rss = own_rss_gib()
        if rss > float(budget_gib):
            stopped = (f"рабочий набор потомка {rss:.2f} ГиБ превысил бюджет потока "
                       f"{float(budget_gib):.2f} ГиБ; остаток не считался")
            break

        payload = solve_node(ctx, temperature, steps_cr, steps_mo, PDENS)
        retries: list[int] = []
        for retry in RETRY_PDENS:
            if converged(payload):
                break
            retries.append(int(payload["pdens"]))
            payload = solve_node(ctx, temperature, steps_cr, steps_mo, retry)
        payload["неудачные pdens"] = retries
        payload["сошлась"] = converged(payload)
        payload["вид"] = kind
        if payload["сошлась"]:
            cache.put_node(point_key(temperature, steps_cr, steps_mo), payload)
        else:
            failed.append({"T, °C": temperature, "узел, ат. %": node_at(steps_cr, steps_mo),
                           "сумма": payload["сумма мольных долей фаз"]})
        done += 1
        if done % 25 == 0 or done == len(todo):
            elapsed = time.perf_counter() - started
            log(f"{done}/{len(todo)} узлов, {elapsed:.0f} с, "
                f"рабочий набор {own_rss_gib():.2f} ГиБ, свободно {w12.free_gib():.2f} ГиБ")
        gc.collect()

    return {
        "узлов всего": len(tasks),
        "посчитано сейчас": done,
        "не сошлись": failed,
        "остановка": stopped,
        "фазы расчёта": list(ctx.phases),
        "исключено из расчёта": list(ctx.excluded_phases),
        "подрешётки": {name: ctx.constituents[name] for name in (P_PHASE, DELTA_PHASE)
                       if name in ctx.constituents},
        "атомные массы": ctx.masses,
    }


# --------------------------------------------------------------------------- #
# Служебное: запись, память, потомок
# --------------------------------------------------------------------------- #


def write_csv(table: pd.DataFrame, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    table.to_csv(path, **CSV_WRITE)
    log(f"записано {path.relative_to(ROOT)} ({len(table)} строк)")
    return path


def write_json(payload: Any, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    log(f"записано {path.relative_to(ROOT)}")
    return path


def memory_report(stem: str, record: Mapping[str, Any], seconds: float,
                  final: bool = True) -> Path | None:
    if not record.get("замеров"):
        return None
    payload = {key: (round(value, 3) if isinstance(value, float) else value)
               for key, value in record.items() if key != "начало, perf_counter"}
    payload["секунд под наблюдением"] = round(seconds, 1)
    payload["шаг опроса, с"] = w11.MEMORY_POLL_SECONDS
    payload["замер завершён"] = bool(final)
    payload["прирост занятой подкачки в системе, ГиБ"] = round(
        float(record["максимум занятой подкачки в системе, ГиБ"])
        - float(record["занято подкачки до старта, ГиБ"]), 3)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"a2_memory_{stem}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    if final:
        log(f"память: пик набора {payload['пик рабочего набора дерева, ГиБ']:.3f} ГиБ, "
            f"минимум свободной {payload['минимум свободной физической, ГиБ']:.2f} ГиБ")
    return path


def memory_watch(process: Any, stop: Any, record: dict[str, Any], stem: str) -> None:
    """Опрос памяти потомка; счёт тот же, что у `w12.memory_watch`, файл свой."""

    import psutil

    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()
    record.update({
        "физической памяти всего, ГиБ": virtual.total / 1024.0 ** 3,
        "подкачки всего, ГиБ": swap.total / 1024.0 ** 3,
        "занято подкачки до старта, ГиБ": swap.used / 1024.0 ** 3,
        "замеров": 0,
        "пик рабочего набора дерева, ГиБ": 0.0,
        "пик фиксации дерева, ГиБ": 0.0,
        "наибольшая разность фиксации и набора, ГиБ": 0.0,
        "минимум свободной физической, ГиБ": virtual.available / 1024.0 ** 3,
        "максимум занятой подкачки в системе, ГиБ": swap.used / 1024.0 ** 3,
    })
    fields = (
        ("пик рабочего набора дерева, ГиБ", "рабочий набор дерева, ГиБ", max),
        ("пик фиксации дерева, ГиБ", "фиксация дерева, ГиБ", max),
        ("наибольшая разность фиксации и набора, ГиБ", "в подкачке у дерева, ГиБ", max),
        ("минимум свободной физической, ГиБ", "свободной физической, ГиБ", min),
        ("максимум занятой подкачки в системе, ГиБ", "занято подкачки в системе, ГиБ", max),
    )
    flushed = time.perf_counter()
    while not stop.wait(w11.MEMORY_POLL_SECONDS):
        probe = w11.memory_probe(process)
        if probe is None:
            continue
        record["замеров"] += 1
        for target, source, pick in fields:
            record[target] = pick(record[target], probe[source])
        now = time.perf_counter()
        if now - flushed >= w11.MEMORY_FLUSH_SECONDS:
            memory_report(stem, record, now - float(record["начало, perf_counter"]), final=False)
            flushed = now


def run_child(arguments: Sequence[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    stem = "_".join(argument.strip("-").replace(",", "_").replace(".", "_")
                    for argument in arguments if argument != "--force")
    handoff = CACHE / f"child_{stem}.json"
    CACHE.mkdir(parents=True, exist_ok=True)
    if handoff.is_file():
        handoff.unlink()
    environment = dict(os.environ, PYTHONHASHSEED="0")
    command = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
               *arguments, "--handoff", str(handoff)]
    started = time.perf_counter()
    popen = subprocess.Popen(command, env=environment, cwd=str(ROOT))
    record: dict[str, Any] = {"подпункт": stem, "начало, perf_counter": started}
    stop = threading.Event()
    import psutil

    watcher = threading.Thread(target=memory_watch,
                               args=(psutil.Process(popen.pid), stop, record, stem),
                               daemon=True)
    watcher.start()
    returncode = popen.wait()
    stop.set()
    seconds = time.perf_counter() - started
    watcher.join(timeout=w11.MEMORY_POLL_SECONDS * 2)
    memory_report(stem, record, seconds)
    if returncode != 0 or not handoff.is_file():
        raise RuntimeError(f"потомок {' '.join(arguments)} завершился с кодом {returncode}")
    measurement = {key: value for key, value in record.items() if key != "начало, perf_counter"}
    measurement["секунд прогона"] = round(seconds, 1)
    return json.loads(handoff.read_text("utf-8")), measurement


# --------------------------------------------------------------------------- #
# a2. Сечения
# --------------------------------------------------------------------------- #


def phase_set(point: Mapping[str, Any]) -> str:
    return " + ".join(sorted(point["фазы"]))


def section_points(points: Sequence[Mapping[str, Any]], temperature: float) -> list[Mapping[str, Any]]:
    return [point for point in points
            if point["T, °C"] == temperature and point.get("вид") == "сечение"]


def in_box(node: Mapping[str, float]) -> bool:
    return all(low - 1.0e-9 <= node[element] <= high + 1.0e-9
               for element, (low, high) in EXP_BOX.items())


def box_distance(node: Mapping[str, float]) -> float:
    """Чебышёвское расстояние узла до экспериментального поля, ат. %.

    Наибольшее по трём элементам отклонение от ближайшей границы интервала;
    ноль — узел внутри поля.
    """

    return max(max(low - node[element], node[element] - high, 0.0)
               for element, (low, high) in EXP_BOX.items())


def nodes_table(points: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    names = sorted({name for point in points for name in point["фазы"]})
    rows: list[dict[str, Any]] = []
    for point in sorted(points, key=lambda p: (p.get("вид", ""), p["T, °C"],
                                               p["шагов CR"], p["шагов MO"])):
        node = point["узел, ат. %"]
        row: dict[str, Any] = {
            "вид": point.get("вид", ""),
            "T, °C": point["T, °C"],
            "Ni, ат. %": node["NI"], "Cr, ат. %": node["CR"], "Mo, ат. %": node["MO"],
            "фазовый набор": phase_set(point),
            "фаз": len(point["фазы"]),
            "в экспериментальном поле P (1100 °C)": "да" if in_box(node) else "нет",
            "pdens": point["pdens"],
        }
        for name in names:
            phase = point["фазы"].get(name)
            row[f"{name}, мольн. %"] = 100.0 * phase["мольная доля"] if phase else 0.0
        for name, value in point["расстояние до устойчивости, Дж/моль"].items():
            row[f"до устойчивости {name}, Дж/моль"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def regions_table(points: Sequence[Mapping[str, Any]], sections: Sequence[float]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for temperature in sections:
        groups: dict[str, list[Mapping[str, float]]] = {}
        for point in section_points(points, temperature):
            groups.setdefault(phase_set(point), []).append(point["узел, ат. %"])
        for name, nodes in sorted(groups.items(), key=lambda item: -len(item[1])):
            row: dict[str, Any] = {"T, °C": temperature, "фазовый набор": name, "узлов": len(nodes)}
            for element, label in (("NI", "Ni"), ("CR", "Cr"), ("MO", "Mo")):
                values = [node[element] for node in nodes]
                row[f"{label} мин, ат. %"] = min(values)
                row[f"{label} макс, ат. %"] = max(values)
            rows.append(row)
    return pd.DataFrame(rows)


def field_summary(points: Sequence[Mapping[str, Any]], temperature: float,
                  phase: str) -> dict[str, Any]:
    section = section_points(points, temperature)
    present = [point for point in section if phase in point["фазы"]]
    box_nodes = [point for point in section if in_box(point["узел, ат. %"])]
    summary: dict[str, Any] = {
        "T, °C": temperature,
        "фаза": phase,
        "узлов в сечении": len(section),
        "узлов с фазой": len(present),
        "узлов экспериментального поля": len(box_nodes),
        "узлов экспериментального поля с фазой": sum(phase in point["фазы"] for point in box_nodes),
        "фазовые наборы в узлах экспериментального поля": sorted({phase_set(p) for p in box_nodes}),
    }
    if present:
        for element, label in (("NI", "Ni"), ("CR", "Cr"), ("MO", "Mo")):
            values = [point["узел, ат. %"][element] for point in present]
            summary[f"{label}, ат. % (мин…макс)"] = [min(values), max(values)]
        nearest = min(present, key=lambda p: box_distance(p["узел, ат. %"]))
        summary["ближайший к экспериментальному полю узел с фазой, ат. %"] = nearest["узел, ат. %"]
        summary["его расстояние до поля (Чебышёв), ат. %"] = box_distance(nearest["узел, ат. %"])
        summary["его фазовый набор"] = phase_set(nearest)
    return summary


def plot_sections(points: Sequence[Mapping[str, Any]], sections: Sequence[float], path: Path) -> None:
    all_sets = sorted({phase_set(point) for temperature in sections
                       for point in section_points(points, temperature)})
    # Наборов больше двадцати, и одна tab20 даёт совпадающие цвета: палитра
    # собрана из трёх качественных карт подряд.
    palette = [plt.get_cmap(name)(index) for name, count in
               (("tab20", 20), ("Dark2", 8), ("Set1", 9)) for index in range(count)]
    colours = {name: palette[index % len(palette)] for index, name in enumerate(all_sets)}
    figure, axes = plt.subplots(1, len(sections), figsize=(6.2 * len(sections), 8.6), squeeze=False)
    for axis, temperature in zip(axes[0], sections):
        section = section_points(points, temperature)
        for name in all_sets:
            nodes = [p["узел, ат. %"] for p in section if phase_set(p) == name]
            if nodes:
                axis.scatter([n["CR"] for n in nodes], [n["MO"] for n in nodes], s=34,
                             color=colours[name], label=name, edgecolors="none")
        for phase, marker, colour in ((P_PHASE, "o", "black"), (DELTA_PHASE, "s", "crimson")):
            nodes = [p["узел, ат. %"] for p in section if phase in p["фазы"]]
            if nodes:
                axis.scatter([n["CR"] for n in nodes], [n["MO"] for n in nodes], s=90,
                             facecolors="none", edgecolors=colour, marker=marker, linewidths=1.2,
                             label=f"есть {phase}")
        # Поле Cr 25…30, Mo 40…45, Ni 25…33: в плоскости Cr–Mo это многоугольник
        # с ограничением 67 ≤ Cr + Mo ≤ 75.
        polygon = [(25.0, 42.0), (25.0, 45.0), (30.0, 45.0), (30.0, 40.0), (27.0, 40.0), (25.0, 42.0)]
        axis.plot([p[0] for p in polygon], [p[1] for p in polygon], color="blue", linewidth=1.6,
                  label="эксп. поле P при 1100 °C (задание)")
        axis.plot([0, 85], [85, 0], color="0.5", linewidth=0.8, linestyle="--")
        axis.set_xlim(-2, 87)
        axis.set_ylim(-2, 87)
        axis.set_aspect("equal")
        axis.set_xlabel("Cr, ат. %")
        axis.set_ylabel("Mo, ат. %")
        axis.set_title(f"{temperature:.0f} °C; Ni = 100 − Cr − Mo, пунктир Ni = 15")
        axis.grid(alpha=0.25)
    handles, labels = [], []
    for axis in axes[0]:
        for handle, label in zip(*axis.get_legend_handles_labels()):
            if label not in labels:
                handles.append(handle)
                labels.append(label)
    figure.suptitle("13-А. Сечения Ni–Cr–Mo, mc_ni 2.036, шаг 2,5 ат. %")
    figure.tight_layout(rect=(0, 0.27, 1, 0.97))
    figure.legend(handles, labels, loc="lower center", ncol=4, fontsize=8,
                  bbox_to_anchor=(0.5, 0.005))
    figure.savefig(path, dpi=140)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


def step_a2(force: bool, min_free_gib: float, budget_gib: float,
            sections: Sequence[float]) -> None:
    arguments = ["--child", "1", "--sections", ",".join(f"{t:g}" for t in sections),
                 "--min-free-gib", f"{float(min_free_gib):g}", "--budget-gib", f"{float(budget_gib):g}"]
    if force:
        arguments.append("--force")
    free = w12.free_gib()
    payload, measurement = run_child(arguments)
    measurement["свободной физической перед запуском, ГиБ"] = round(free, 2)

    points = load_points()
    write_csv(nodes_table(points), "a2_nodes.csv")
    write_csv(regions_table(points, sections), "a2_phase_regions.csv")
    fields = [field_summary(points, t, phase) for t in sections for phase in (P_PHASE, DELTA_PHASE)]
    plot_sections(points, sections, OUT / "a2_sections.png")

    expected = len(task_list(sections, edge_scan=True))
    summary = {
        "подпункт": "13-А, пункт 2. Изотермические сечения Ni–Cr–Mo",
        "база": DB_REL,
        "sha256 базы": w12.database_sha256(),
        "сечения задания, °C": list(TASK_SECTIONS_C),
        "сечения сверх задания, °C": [t for t in sections if t not in TASK_SECTIONS_C],
        "ребро Ni–Mo по температуре, °C": list(EDGE_SCAN_C),
        "ребро Ni–Mo, Mo ат. %": [s * STEP_AT for s in EDGE_SCAN_MO_STEPS],
        "шаг сетки, ат. %": STEP_AT,
        "область": "Ni ≥ 15 ат. %",
        "узлов на сечение": len(section_nodes()),
        "узлов ожидалось всего": expected,
        "узлов в кэше": len(points),
        "следовое значение вместо нуля на рёбрах, мольн. доля": EDGE_X,
        "pdens": PDENS,
        "ряд повторов pdens": list(RETRY_PDENS),
        "узлы, сошедшиеся не с первой pdens": [
            {"T, °C": p["T, °C"], "узел, ат. %": p["узел, ат. %"], "неудачные pdens": p["неудачные pdens"]}
            for p in points if p.get("неудачные pdens")
        ],
        "потомок": payload,
        "поля P_PHASE и D_NIMO": fields,
        "экспериментальное поле P при 1100 °C (из задания), ат. %": EXP_BOX,
        "порог входа": {
            "по умолчанию (w12.MIN_FREE_GIB), ГиБ": MIN_FREE_GIB,
            "объявлен заданием 13-А, ГиБ": TASK_MIN_FREE_GIB,
            "фактический, ГиБ": float(min_free_gib),
            "обоснование": f"пик рабочего набора равновесного прогона 12-2 "
                           f"{JUSTIFY_PEAK_SET_GIB} ГиБ ({JUSTIFY_SOURCE})",
        },
        "аварийный порог по ходу, ГиБ": ABORT_FREE_GIB,
        "бюджет потока, ГиБ": float(budget_gib),
        "замер памяти": measurement,
    }
    write_json(summary, "a2_summary.json")


# --------------------------------------------------------------------------- #
# a1. Состав P-фазы
# --------------------------------------------------------------------------- #


def a1_wave12_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in ("e1_phase_compositions.csv", "e4_phase_compositions.csv"):
        path = W12_OUT / name
        if not path.is_file():
            continue
        table = pd.read_csv(path, **CSV_READ)
        table = table[table["фаза"] == P_PHASE]
        for _, line in table.iterrows():
            x = {element: float(line[f"x({element})"]) for element in TERNARY_ELEMENTS}
            other = sum(float(line[column]) for column in table.columns
                        if column.startswith("x(") and column[2:-1] not in TERNARY_ELEMENTS)
            label = f"волна 12, {name}"
            if "узел" in table.columns:
                label += f", {line['узел']}, {line.get('режим', '')}"
            rows.append({
                "источник": label,
                "T, °C": float(line["T, °C"]),
                "узел Ni, ат. %": None, "узел Cr, ат. %": None, "узел Mo, ат. %": None,
                "мольная доля P, %": float(line["мольная доля фазы, %"]),
                "x(Ni) в P": x["NI"], "x(Cr) в P": x["CR"], "x(Mo) в P": x["MO"],
                "прочие элементы в P, мольн. доля": other,
                "Mo − 12/56, ат. %": 100.0 * (x["MO"] - P_MO_CEILING),
                "Ni/Cr": x["NI"] / x["CR"] if x["CR"] > 0 else None,
                "y(Ni) подрешётки 1": None, "y(Cr) подрешётки 2": None, "y(Mo) подрешётки 3": None,
            })
    return rows


def step_a1(**_: Any) -> None:
    points = load_points()
    rows: list[dict[str, Any]] = []
    for point in points:
        for vertex in point["вершины P и D_NIMO"]:
            if vertex["фаза"] != P_PHASE:
                continue
            x = vertex["x"]
            sub = vertex["подрешётки"]
            node = point["узел, ат. %"]
            rows.append({
                "источник": f"13-А, {point.get('вид', '')}",
                "T, °C": point["T, °C"],
                "узел Ni, ат. %": node["NI"], "узел Cr, ат. %": node["CR"], "узел Mo, ат. %": node["MO"],
                "мольная доля P, %": 100.0 * vertex["мольная доля"],
                "x(Ni) в P": x["NI"], "x(Cr) в P": x["CR"], "x(Mo) в P": x["MO"],
                "прочие элементы в P, мольн. доля": 0.0,
                "Mo − 12/56, ат. %": 100.0 * (x["MO"] - P_MO_CEILING),
                "Ni/Cr": x["NI"] / x["CR"] if x["CR"] > 0 else None,
                "y(Ni) подрешётки 1": sub[0].get("NI"),
                "y(Cr) подрешётки 2": sub[1].get("CR"),
                "y(Mo) подрешётки 3": sub[2].get("MO"),
            })
    rows.extend(a1_wave12_rows())
    table = pd.DataFrame(rows)
    write_csv(table, "a1_p_compositions.csv")

    def block_summary(block: pd.DataFrame) -> dict[str, Any]:
        if not len(block):
            return {"записей": 0}
        return {
            "записей": int(len(block)),
            "температуры, °C": sorted({float(t) for t in block["T, °C"]}),
            "Mo в P, ат. % (мин…макс)": [100.0 * float(block["x(Mo) в P"].min()),
                                        100.0 * float(block["x(Mo) в P"].max())],
            "наибольшее |Mo − 12/56|, ат. %": float(block["Mo − 12/56, ат. %"].abs().max()),
            "Cr в P, ат. % (мин…макс)": [100.0 * float(block["x(Cr) в P"].min()),
                                        100.0 * float(block["x(Cr) в P"].max())],
            "Ni в P, ат. % (мин…макс)": [100.0 * float(block["x(Ni) в P"].min()),
                                        100.0 * float(block["x(Ni) в P"].max())],
            "Ni/Cr (мин…макс)": [float(block["Ni/Cr"].min()), float(block["Ni/Cr"].max())],
            "прочие элементы в P, наибольшая мольн. доля": float(
                block["прочие элементы в P, мольн. доля"].max()),
        }

    own = table[table["источник"].str.startswith("13-А")]
    by_t = {f"{t:g} °C": block_summary(own[own["T, °C"] == t])
            for t in sorted({float(v) for v in own["T, °C"]})} if len(own) else {}
    summary = {
        "подпункт": "13-А, пункт 1. Состав P-фазы во всём поле устойчивости",
        "модель в базе": {
            "подрешётки, позиций": list(P_SITES),
            "потолок Mo, ат. %": 100.0 * P_MO_CEILING,
            "нижняя граница Cr в Ni–Cr–Mo, ат. %": 100.0 * P_CR_FLOOR,
            "верхняя граница Ni в Ni–Cr–Mo, ат. %": 100.0 * 24.0 / 56.0,
            "параметры, существенные для Ni–Cr–Mo": [
                "G(P_PHASE,NI:CR:MO;0) = 24·GHSERNI + 20·GHSERCR + 12·GHSERMO − 50000 − 320·T",
                "G(P_PHASE,CR:CR:MO;0) = 24·GCRFCC + 20·GHSERCR + 12·GHSERMO + 200000",
                "параметров взаимодействия L нет",
            ],
        },
        "узлы 13-А, все": block_summary(own),
        "узлы 13-А по температурам": by_t,
        "сплав, волна 12": block_summary(table[table["источник"].str.startswith("волна 12")]),
        "реальные составы из задания, ат. %": {label: comp for label, comp in REAL_P_COMPOSITIONS},
    }
    write_json(summary, "a1_summary.json")


# --------------------------------------------------------------------------- #
# a3. δ-фаза NiMo
# --------------------------------------------------------------------------- #


def step_a3(**_: Any) -> None:
    points = load_points()
    rows: list[dict[str, Any]] = []
    for point in points:
        node = point["узел, ат. %"]
        delta = point["фазы"].get(DELTA_PHASE)
        rows.append({
            "вид": point.get("вид", ""),
            "T, °C": point["T, °C"],
            "Ni, ат. %": node["NI"], "Cr, ат. %": node["CR"], "Mo, ат. %": node["MO"],
            "фазовый набор": phase_set(point),
            "D_NIMO есть": "да" if delta else "нет",
            "D_NIMO, мольн. %": 100.0 * delta["мольная доля"] if delta else 0.0,
            "Mo в D_NIMO, ат. %": 100.0 * delta["x"]["MO"] if delta else None,
            "Cr в D_NIMO, ат. %": 100.0 * delta["x"]["CR"] if delta else None,
            "до устойчивости D_NIMO, Дж/моль": point["расстояние до устойчивости, Дж/моль"].get(DELTA_PHASE),
            "до устойчивости P_PHASE, Дж/моль": point["расстояние до устойчивости, Дж/моль"].get(P_PHASE),
            "в экспериментальном поле P (1100 °C)": "да" if in_box(node) else "нет",
        })
    table = pd.DataFrame(rows).sort_values(["вид", "T, °C", "Mo, ат. %", "Cr, ат. %"])
    write_csv(table[table["D_NIMO есть"] == "да"], "a3_delta_present.csv")
    edge_mo = {steps * STEP_AT for steps in EDGE_SCAN_MO_STEPS}
    edge = table[(table["Cr, ат. %"] == 0.0) & table["Mo, ат. %"].isin(edge_mo)]
    write_csv(edge.sort_values(["T, °C", "Mo, ат. %"]), "a3_ni_mo_edge.csv")
    box = table[(table["в экспериментальном поле P (1100 °C)"] == "да") & (table["вид"] == "сечение")]
    write_csv(box, "a3_experimental_box.csv")

    present = table[table["D_NIMO есть"] == "да"]
    per_t = []
    for temperature in sorted({float(t) for t in table["T, °C"]}):
        block = present[present["T, °C"] == temperature]
        entry: dict[str, Any] = {"T, °C": temperature, "узлов с D_NIMO": int(len(block))}
        if len(block):
            entry["узлы, Mo ат. % (мин…макс)"] = [float(block["Mo, ат. %"].min()), float(block["Mo, ат. %"].max())]
            entry["узлы, Cr ат. % (мин…макс)"] = [float(block["Cr, ат. %"].min()), float(block["Cr, ат. %"].max())]
            entry["Mo в самой D_NIMO, ат. % (мин…макс)"] = [float(block["Mo в D_NIMO, ат. %"].min()),
                                                           float(block["Mo в D_NIMO, ат. %"].max())]
            entry["Cr в самой D_NIMO, ат. %, макс"] = float(block["Cr в D_NIMO, ат. %"].max())
        per_t.append(entry)
    box_summary = []
    for temperature in sorted({float(t) for t in box["T, °C"]}):
        block = box[box["T, °C"] == temperature]
        box_summary.append({
            "T, °C": temperature,
            "фазовые наборы": sorted(set(block["фазовый набор"])),
            "до устойчивости P_PHASE, Дж/моль (мин…макс)": [
                float(block["до устойчивости P_PHASE, Дж/моль"].min()),
                float(block["до устойчивости P_PHASE, Дж/моль"].max())],
            "до устойчивости D_NIMO, Дж/моль (мин…макс)": [
                float(block["до устойчивости D_NIMO, Дж/моль"].min()),
                float(block["до устойчивости D_NIMO, Дж/моль"].max())],
        })
    summary = {
        "подпункт": "13-А, пункт 3. δ-фаза NiMo",
        "модель в базе": {
            "фаза": "D_NIMO, 24 : 20 : 12, NI : MO,NI : MO",
            "Mo, ат. % (пределы модели)": [100.0 * 12.0 / 56.0, 100.0 * 32.0 / 56.0],
            "хром": "в подрешётках D_NIMO хрома нет; растворить Cr фаза не может",
            "ссылка в базе": "REF:155",
        },
        "по температурам": per_t,
        "экспериментальное поле P": box_summary,
        "расстояние до устойчивости": (
            "min по выборке составов фазы (G_m − Σ μ_i x_i), Дж/моль атомов, "
            f"pdens выборки {DISTANCE_PDENS}; 0 — фаза устойчива"
        ),
    }
    write_json(summary, "a3_summary.json")


# --------------------------------------------------------------------------- #
# a4. Баланс молибдена
# --------------------------------------------------------------------------- #


def tdb_masses() -> dict[str, float]:
    """Атомные массы из строк ELEMENT базы — те же, что `db.refstates[...]['mass']`."""

    masses: dict[str, float] = {}
    pattern = re.compile(r"^\s*ELEMENT\s+(\S+)\s+\S+\s+([0-9.Ee+-]+)")
    with (ROOT / DB_REL).open("r", encoding="utf-8", errors="replace") as source:
        for line in source:
            match = pattern.match(line)
            if match:
                masses[match.group(1).upper()] = float(match.group(2))
    return masses


def to_mass_percent(at_percent: Mapping[str, float], masses: Mapping[str, float]) -> dict[str, float]:
    weighted = {element: value * masses[element] for element, value in at_percent.items()}
    total = sum(weighted.values())
    return {element: 100.0 * value / total for element, value in weighted.items()}


def step_a4(**_: Any) -> None:
    masses = tdb_masses()
    compositions = pd.read_csv(W12_OUT / "e1_phase_compositions.csv", **CSV_READ)
    summary12 = json.loads((W12_OUT / "e1_summary.json").read_text("utf-8"))
    alloy_wt = {k: float(v) for k, v in summary12["состав, масс. %"].items()}
    alloy_x = {k: float(v) for k, v in summary12["состав, мольные доли"].items()}

    real = []
    for label, at in REAL_P_COMPOSITIONS:
        total = sum(at.values())
        normalised = {element: 100.0 * value / total for element, value in at.items()}
        real.append((label, total, normalised, to_mass_percent(normalised, masses)))

    rows: list[dict[str, Any]] = []
    for temperature in BALANCE_T_C:
        block = compositions[compositions["T, °C"] == temperature]
        p_line = block[block["фаза"] == P_PHASE].iloc[0]
        m_line = block[block["фаза"] == MATRIX_PHASE].iloc[0]
        minor = block[~block["фаза"].isin([P_PHASE, MATRIX_PHASE])]

        f_mass = float(p_line["массовая доля фазы, %"]) / 100.0
        f_mole = float(p_line["мольная доля фазы, %"]) / 100.0
        c_p = float(p_line["MO, масс. %"])
        x_p = float(p_line["x(MO)"])
        c_m = float(m_line["MO, масс. %"])
        x_m = float(m_line["x(MO)"])
        cr_m_model = float(m_line["CR, масс. %"])
        minor_mass = float(minor["массовая доля фазы, %"].sum()) / 100.0
        minor_mole = float(minor["мольная доля фазы, %"].sum()) / 100.0
        minor_mo_mass = float((minor["массовая доля фазы, %"] / 100.0 * minor["MO, масс. %"]).sum())
        minor_mo_mole = float((minor["мольная доля фазы, %"] / 100.0 * minor["x(MO)"]).sum())
        minor_cr_mass = float((minor["массовая доля фазы, %"] / 100.0 * minor["CR, масс. %"]).sum())
        c_alloy = alloy_wt["MO"]
        x_alloy = alloy_x["MO"]
        # Проверка: та же формула рычага с модельным составом P должна вернуть
        # модельную долю. Невязка идёт в таблицу.
        lever_mass_model = (c_alloy - minor_mo_mass - (1.0 - minor_mass) * c_m) / (c_p - c_m)
        lever_mole_model = (x_alloy - minor_mo_mole - (1.0 - minor_mole) * x_m) / (x_p - x_m)

        for label, total, at, wt in real:
            c_r = wt["MO"]
            x_r = at["MO"] / 100.0
            upper_mass = f_mass * c_p / c_r
            upper_mole = f_mole * x_p / x_r
            lower_mass = (c_alloy - minor_mo_mass - (1.0 - minor_mass) * c_m) / (c_r - c_m)
            lower_mole = (x_alloy - minor_mo_mole - (1.0 - minor_mole) * x_m) / (x_r - x_m)
            ceiling_mass = (c_alloy - minor_mo_mass) / c_r
            ceiling_mole = (x_alloy - minor_mo_mole) / x_r

            def matrix_cr(f_real: float) -> float:
                return (alloy_wt["CR"] - minor_cr_mass - f_real * wt["CR"]) / (1.0 - f_real - minor_mass)

            def matrix_mo(f_real: float) -> float:
                return (c_alloy - minor_mo_mass - f_real * c_r) / (1.0 - f_real - minor_mass)

            rows.append({
                "T, °C": temperature,
                "состав реальной фазы": label,
                "сумма ат. % в источнике": total,
                "реальная: Mo, ат. %": at["MO"], "реальная: Mo, масс. %": c_r,
                "реальная: Cr, масс. %": wt["CR"], "реальная: Ni, масс. %": wt["NI"],
                "модель: P, мольн. %": 100.0 * f_mole, "модель: P, масс. %": 100.0 * f_mass,
                "модель: Mo в P, ат. %": 100.0 * x_p, "модель: Mo в P, масс. %": c_p,
                "модель: Mo в FCC_A1, масс. %": c_m, "модель: Cr в FCC_A1, масс. %": cr_m_model,
                "проверка рычага на модели, масс. %": 100.0 * lever_mass_model,
                "проверка рычага на модели, мольн. %": 100.0 * lever_mole_model,
                "сверху (тот же связанный Mo), масс. %": 100.0 * upper_mass,
                "сверху (тот же связанный Mo), мольн. %": 100.0 * upper_mole,
                "снизу (тот же Mo в матрице), масс. %": 100.0 * lower_mass,
                "снизу (тот же Mo в матрице), мольн. %": 100.0 * lower_mole,
                "потолок (весь свободный Mo в фазе), масс. %": 100.0 * ceiling_mass,
                "потолок (весь свободный Mo в фазе), мольн. %": 100.0 * ceiling_mole,
                "поправка сверху к модели, масс.": upper_mass / f_mass,
                "поправка сверху к модели, мольн.": upper_mole / f_mole,
                "поправка снизу к модели, масс.": lower_mass / f_mass,
                "поправка снизу к модели, мольн.": lower_mole / f_mole,
                "сверху: Mo в матрице, масс. %": matrix_mo(upper_mass),
                "сверху: Cr в матрице, масс. %": matrix_cr(upper_mass),
                "снизу: Mo в матрице, масс. %": matrix_mo(lower_mass),
                "снизу: Cr в матрице, масс. %": matrix_cr(lower_mass),
            })
    table = pd.DataFrame(rows)
    write_csv(table, "a4_mo_balance.csv")
    write_json({
        "подпункт": "13-А, пункт 4. Доля ТПУ-фазы по балансу молибдена",
        "источник модельных чисел": "results/hn62m_wave12/e1_phase_compositions.csv, e1_summary.json",
        "атомные массы (строки ELEMENT базы)": {k: masses[k] for k in TERNARY_ELEMENTS},
        "составы реальной фазы, нормированные, ат. % и масс. %": [
            {"источник": label, "сумма в источнике": total, "ат. %": at, "масс. %": wt}
            for label, total, at, wt in real
        ],
        "сверху": ("масса (моли) Mo, связанного в ТПУ-фазе, та же, что в модельной P-фазе; "
                   "матрица тогда беднее Mo, чем в модели"),
        "снизу": ("содержание Mo в матрице FCC_A1 то же, что в модели; фаза меньше, "
                  "матрица больше и держит больше Mo"),
        "потолок": "в ТПУ-фазе весь Mo, не связанный малыми фазами (матрица без Mo)",
        "малые фазы": "доли и составы малых фаз (γ', M23C6, MnS) оставлены модельными",
        "строки": rows,
    }, "a4_summary.json")


# --------------------------------------------------------------------------- #
# Запуск
# --------------------------------------------------------------------------- #


STEPS = {"a2": step_a2, "a1": step_a1, "a3": step_a3, "a4": step_a4}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Волна 13, задача 13-А: P-фаза в mc_ni 2.036")
    parser.add_argument("--only", default="all", help="a2,a1,a3,a4; через запятую")
    parser.add_argument("--force", action="store_true", help="пересчитать узлы заново")
    parser.add_argument("--min-free-gib", type=float, default=MIN_FREE_GIB,
                        help=f"порог входа, ГиБ (по умолчанию {MIN_FREE_GIB})")
    parser.add_argument("--budget-gib", type=float, default=TASK_BUDGET_GIB,
                        help="бюджет рабочего набора потомка, ГиБ")
    parser.add_argument("--sections", default=",".join(
        f"{t:g}" for t in (*TASK_SECTIONS_C, *EXTRA_SECTIONS_C)), help="температуры сечений, °C")
    parser.add_argument("--child", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--handoff", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    sections = [float(value) for value in args.sections.split(",") if value.strip()]

    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    if args.child is not None:
        payload = compute_nodes(sections, True, args.min_free_gib, args.budget_gib, args.force)
        if args.handoff:
            Path(args.handoff).write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
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
        if name == "a2":
            free = w12.free_gib()
            cached = {point_key(p["T, °C"], p["шагов CR"], p["шагов MO"]) for p in load_points()}
            complete = all(point_key(*task[:3]) in cached for task in task_list(sections, True))
            if free < args.min_free_gib and not (complete and not args.force):
                write_json({"подпункт": "13-А, пункт 2", "прогон": "не начинался",
                            "причина": f"свободной физической памяти {free:.2f} ГиБ при пороге "
                                       f"входа {args.min_free_gib:.1f} ГиБ"}, "a2_summary.json")
                log(f"a2 не запускался: свободно {free:.2f} ГиБ")
                return 2
            step_a2(args.force, args.min_free_gib, args.budget_gib, sections)
        else:
            STEPS[name]()
        log(f"=== {name.upper()} готов за {time.perf_counter() - started:.1f} с ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
