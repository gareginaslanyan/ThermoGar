#!/usr/bin/env python3
"""Волна 13, задача 13-Е — годится ли σ-фаза mc_ni 2.036 на роль наблюдаемой
ТПУ-фазы ЭК199-ВИ.

Задание `tasks/WAVE13_E_OPUS.md`. Префиксы результатов в `results/hn62m_wave13/`:

* ``e1`` — состав σ-фазы по базе во всём поле её устойчивости на сечениях
  Ni–Cr–Mo 700, 1100 и 1250 °C (сетка и область те же, что у 13-А) и близость
  его к измеренному составу ТПУ-фазы ХН62М-ВИ. Для полноты те же числа для
  MU_PHASE, D_NIMO и P_PHASE: пункт 5 сравнивает фазы между собой.
* ``e2`` — расстояние до устойчивости σ при составе сплава в пяти точках ТЗ.
* ``e3`` — то же для MU_PHASE и D_NIMO (и P_PHASE как контроль).
* ``e4`` — принудительное равновесие FCC_A1 + SIGMA при составе сплава: доля σ,
  составы σ и матрицы, сравнение с измеренной матрицей.
* ``e5`` — сводка для вывода: какая фаза базы ближе к наблюдаемой.

Равновесия сплава считаются в трёх наборах фаз:
  ``полный``   — все фазы, как в волне 12 (P_PHASE есть);
  ``без P``    — все фазы, кроме P_PHASE (сверх задания: какая фаза займёт
                 место P, если модельную P убрать);
  ``FCC+σ``    — только FCC_A1 и SIGMA (пункт 4 задания).

Расстояние до устойчивости — определение 13-А: min по составам фазы
(G_m − Σ μ_i·x_i), Дж/моль атомов, при химических потенциалах равновесия.
13-А брал минимум по выборке `calculate` (3000 точек плотности). В тройной
системе этого хватало; в одиннадцатикомпонентной выборка редка и завышает
расстояние на сотни Дж/моль. Поэтому здесь даются оба числа: минимум по той же
выборке (механизм 13-А без изменений) и уточнённый минимум — локальный спуск по
долям в подрешётках из лучших точек выборки. Контроль уточнения: у фаз,
которые в равновесии есть, оно обязано дать ноль.

Запуск (интерпретатор — venv основного репозитория, PYTHONHASHSEED=0):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 ^
        tools\\study_hn62m_wave13_sigma.py --only e1,e2,e3,e4,e5 --min-free-gib 2.5

Память. Порог входа — ключ `--min-free-gib` (задание 13-Е: 2,5 ГиБ), умолчание
`w12.MIN_FREE_GIB`. Аварийный порог `w12.E1_ABORT_FREE_GIB` ключа не имеет.
Кэш: `cache/e1_points.jsonl` (узлы сечений) и `cache/e2_points.jsonl`
(равновесия сплава); каждая точка уходит на диск сразу.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import study_hn62m_wave11 as w11
import study_hn62m_wave12 as w12
import study_hn62m_wave13_pphase as w13a

ROOT = w12.ROOT
OUT = w13a.OUT
CACHE = w13a.CACHE
CSV_WRITE = dict(w12.CSV_WRITE)
CSV_READ = dict(w12.CSV_READ)
log = w12.log
DB_REL = w12.DB_REL

MIN_FREE_GIB = w12.MIN_FREE_GIB
ABORT_FREE_GIB = w12.E1_ABORT_FREE_GIB
TASK_MIN_FREE_GIB = 2.5

PDENS = w12.E1_PDENS
RETRY_PDENS: tuple[int, ...] = tuple(w12.E1_RETRY_PDENS)
PRESENT_FLOOR = w12.E1_PRESENT_FLOOR
SUM_TOLERANCE = w12.E1_SUM_TOLERANCE

SIGMA = "SIGMA"
MU = "MU_PHASE"
DELTA = w13a.DELTA_PHASE
P_PHASE = w13a.P_PHASE
MATRIX = w12.E1_MATRIX_PHASE
# Фазы, которые сравниваются с наблюдаемой ТПУ-фазой.
CANDIDATES: tuple[str, ...] = (SIGMA, MU, DELTA, P_PHASE)

# Точки ТЗ — те же, что у волны 12.
REQUIRED_C: tuple[float, ...] = tuple(w12.E1_REQUIRED_C)
SECTIONS_C: tuple[float, ...] = (700.0, 1100.0, 1250.0)

# Наборы фаз равновесий сплава.
VARIANT_FULL = "полный"
VARIANT_NO_P = "без P"
VARIANT_FORCED = "FCC+σ"
VARIANTS: tuple[str, ...] = (VARIANT_FULL, VARIANT_NO_P, VARIANT_FORCED)
FORCED_PHASES: tuple[str, ...] = (MATRIX, SIGMA)

# Измерения — числа из текста задания 13-Е (ХН62М-ВИ, 5000 ч при 700 °C;
# Гибадуллина и др., 2025, DOI 10.3390/app15116133, табл. 3 — по заданию 13-А).
MEASURED_TCP_AT = {"CR": 21.8, "NI": 37.6, "MO": 40.7}
MEASURED_MATRIX_AT = {"NI": 64.9, "CR": 26.3, "MO": 8.8}
MEASURED_T_C = 700.0
MEASURED_SOURCE = ("ХН62М-ВИ, 5000 ч при 700 °C; числа из задания 13-Е "
                   "(Гибадуллина и др., 2025, DOI 10.3390/app15116133, табл. 3)")

# Пределы состава моделей в Ni–Cr–Mo, ат. %: из числа позиций подрешёток
# (строки PHASE/CONSTITUENT базы).
MODEL_LIMITS = {
    SIGMA: {"модель": "SIGMA 8 : 4 : 18, (Co,Fe,Mn,Ni,Ti)(Cr,Mo,V,W)(Co,Cr,Fe,Mn,Mo,Ni,Si,V,W)",
            "в Ni–Cr–Mo": "Ni₈(Cr,Mo)₄(Cr,Mo,Ni)₁₈",
            "Ni, ат. %": [100.0 * 8 / 30, 100.0 * 26 / 30],
            "Cr, ат. %": [0.0, 100.0 * 22 / 30], "Mo, ат. %": [0.0, 100.0 * 22 / 30]},
    MU: {"модель": "MU_PHASE 7 : 2 : 4, (Co,Cr,Fe,Mn,Mo,Nb,Ni,Si)(Mo,Nb,W)(Al,Co,Cr,Fe,Mo,Nb,Ni,Si,W)",
         "в Ni–Cr–Mo": "(Cr,Mo,Ni)₇Mo₂(Cr,Mo,Ni)₄",
         "Ni, ат. %": [0.0, 100.0 * 11 / 13],
         "Cr, ат. %": [0.0, 100.0 * 11 / 13], "Mo, ат. %": [100.0 * 2 / 13, 100.0]},
    DELTA: {"модель": "D_NIMO 24 : 20 : 12, Ni(Mo,Ni)Mo",
            "в Ni–Cr–Mo": "Ni₂₄(Mo,Ni)₂₀Mo₁₂",
            "Ni, ат. %": [100.0 * 24 / 56, 100.0 * 44 / 56],
            "Cr, ат. %": [0.0, 0.0], "Mo, ат. %": [100.0 * 12 / 56, 100.0 * 32 / 56]},
    P_PHASE: {"модель": "P_PHASE 24 : 20 : 12, (Co,Cr,Ni)(Co,Cr,W)(Mo,W)",
              "в Ni–Cr–Mo": "(Cr,Ni)₂₄Cr₂₀Mo₁₂",
              "Ni, ат. %": [0.0, 100.0 * 24 / 56],
              "Cr, ат. %": [100.0 * 20 / 56, 100.0 * 44 / 56],
              "Mo, ат. %": [100.0 * 12 / 56, 100.0 * 12 / 56]},
}

# Расстояние до устойчивости: плотность выборки 13-А и параметры уточнения.
DISTANCE_PDENS = w13a.DISTANCE_PDENS
REFINE_BEST_STARTS = 24
REFINE_RANDOM_STARTS = 8
REFINE_BLEND = 0.05
REFINE_SEED = 0
# Фаза, присутствующая в равновесии, обязана получить ноль; допуск контроля.
CONTROL_TOLERANCE_J = 1.0

TERNARY = ("NI", "CR", "MO")
LABEL = {"NI": "Ni", "CR": "Cr", "MO": "Mo"}


# --------------------------------------------------------------------------- #
# Общие мелочи
# --------------------------------------------------------------------------- #


def normalised(at: Mapping[str, float]) -> dict[str, float]:
    total = sum(float(at[element]) for element in TERNARY)
    return {element: 100.0 * float(at[element]) / total for element in TERNARY}


MEASURED_TCP_NORM = normalised(MEASURED_TCP_AT)
MEASURED_MATRIX_NORM = normalised(MEASURED_MATRIX_AT)


def ternary_at(x: Mapping[str, float]) -> dict[str, float]:
    """Ni, Cr, Mo фазы в ат. %, нормированные на их сумму."""

    values = {element: float(x.get(element, 0.0)) for element in TERNARY}
    if sum(values.values()) <= 0.0:
        # Фаза без Ni, Cr и Mo (MnS): тройной состав не определён.
        return {element: float("nan") for element in TERNARY}
    return normalised(values)


def closeness(at: Mapping[str, float], target: Mapping[str, float]) -> dict[str, float]:
    delta = {element: float(at[element]) - float(target[element]) for element in TERNARY}
    return {
        "евклид, ат. %": float(np.sqrt(sum(value ** 2 for value in delta.values()))),
        "Чебышёв, ат. %": float(max(abs(value) for value in delta.values())),
        **{f"Δ{LABEL[element]}, ат. %": delta[element] for element in TERNARY},
    }


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


class JsonlCache:
    """Кэш, дописываемый построчно, — как `w12.PointCache`, со своим файлом."""

    def __init__(self, name: str) -> None:
        CACHE.mkdir(parents=True, exist_ok=True)
        self.path = CACHE / name
        self.records: dict[str, dict[str, Any]] = {}
        if self.path.is_file():
            for line in self.path.read_text("utf-8").splitlines():
                if line.strip():
                    record = json.loads(line)
                    self.records[record["key"]] = record["payload"]

    def reset(self) -> None:
        self.records.clear()
        if self.path.is_file():
            self.path.unlink()

    def put(self, key: str, payload: Mapping[str, Any]) -> None:
        self.records[key] = dict(payload)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"key": key, "payload": payload},
                                    ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


# --------------------------------------------------------------------------- #
# Расстояние до устойчивости: выборка 13-А и уточнение
# --------------------------------------------------------------------------- #


class DistanceEngine:
    """Расстояние до устойчивости фазы при заданных потенциалах.

    Выборка — `pycalphad.calculate` с плотностью 13-А; хранится для одной
    температуры и сбрасывается при смене температуры. Уточнение — L-BFGS по
    логитам долей в подрешётках (softmax внутри каждой подрешётки), так что
    ограничения Σy = 1 и y ≥ 0 выполняются тождественно и разбавленные
    составляющие не прилипают к границе. Функция и градиент — из
    скомпилированной `PhaseRecord` той же фазы, что считает равновесие:
    на формульную единицу G_f(y) − Σ μ_i·M_i(y), делённое на число атомов N(y).
    """

    def __init__(self, db: Any, components: Sequence[str], models: Mapping[str, Any],
                 phase_records: Any) -> None:
        self.db = db
        self.components = list(components)
        self.models = models
        self.phase_records = phase_records
        self._temperature: float | None = None
        self._samples: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]] = {}

    def samples(self, temperature_c: float, phase: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
        if self._temperature != float(temperature_c):
            self._samples.clear()
            gc.collect()
            self._temperature = float(temperature_c)
        if phase not in self._samples:
            from pycalphad import calculate

            result = calculate(self.db, self.components, [phase],
                               T=float(temperature_c) + 273.15, P=101325.0, N=1.0,
                               pdens=DISTANCE_PDENS, model=self.models, output="GM")
            order = [str(name) for name in result.coords["component"].values]
            gm = np.asarray(result.GM.values, dtype=float).reshape(-1)
            x = np.asarray(result.X.values, dtype=float).reshape(len(gm), len(order))
            n_dof = sum(len(sub) for sub in self.models[phase].constituents)
            y = np.asarray(result.Y.values, dtype=float).reshape(len(gm), -1)[:, :n_dof]
            finite = np.isfinite(gm) & np.all(np.isfinite(x), axis=1) & np.all(np.isfinite(y), axis=1)
            self._samples[phase] = (x[finite], gm[finite], y[finite], order)
            del result
        return self._samples[phase]

    def distance(self, temperature_c: float, phase: str, mu: Mapping[str, float],
                 extra_starts: Sequence[Sequence[float]] = ()) -> dict[str, Any]:
        from scipy.optimize import minimize

        x_s, gm_s, y_s, order = self.samples(temperature_c, phase)
        potentials = np.array([float(mu[element]) for element in order])
        driving = gm_s - x_s @ potentials
        sampled = int(np.argmin(driving))

        record = self.phase_records.get(phase)
        elements = [str(name) for name in record.nonvacant_elements]
        mu_record = np.array([float(mu[element]) for element in elements])
        sizes = [len(sub) for sub in self.models[phase].constituents]
        n_dof = sum(sizes)
        n_el = len(elements)
        temperature_k = float(temperature_c) + 273.15
        bounds = np.cumsum([0, *sizes])

        def evaluate(y: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
            dof = np.concatenate(([1.0, 101325.0, temperature_k], y))
            g = np.zeros(1)
            record.formulaobj(g, dof)
            g_grad = np.zeros(3 + n_dof)
            record.formulagrad(g_grad, dof)
            moles = np.zeros(n_el)
            moles_grad = np.zeros((n_el, 3 + n_dof))
            buffer = np.zeros(1)
            for index in range(n_el):
                record.formulamole_obj(buffer, dof, index)
                moles[index] = buffer[0]
                row = np.zeros(3 + n_dof)
                record.formulamole_grad(row, dof, index)
                moles_grad[index] = row
            atoms = float(moles.sum())
            atoms_grad = moles_grad[:, 3:].sum(axis=0)
            h = float(g[0] - mu_record @ moles)
            h_grad = g_grad[3:] - mu_record @ moles_grad[:, 3:]
            value = h / atoms
            gradient = (h_grad * atoms - h * atoms_grad) / atoms ** 2
            return value, gradient, moles / atoms

        def site_fractions(z: np.ndarray) -> np.ndarray:
            y = np.empty(n_dof)
            for low, high in zip(bounds[:-1], bounds[1:]):
                block = z[low:high]
                weights = np.exp(block - block.max())
                y[low:high] = weights / weights.sum()
            return np.maximum(y, 1.0e-300)

        def objective(z: np.ndarray) -> tuple[float, np.ndarray]:
            y = site_fractions(z)
            value, grad_y, _ = evaluate(y)
            grad_z = np.empty(n_dof)
            for low, high in zip(bounds[:-1], bounds[1:]):
                block_y = y[low:high]
                block_g = grad_y[low:high]
                grad_z[low:high] = block_y * (block_g - block_y @ block_g)
            return value, grad_z

        order_idx = np.argsort(driving)
        starts: list[np.ndarray] = []
        seen: set[bytes] = set()
        for index in order_idx:
            key = np.round(y_s[index], 6).tobytes()
            if key in seen:
                continue
            seen.add(key)
            starts.append(y_s[index])
            if len(starts) >= REFINE_BEST_STARTS:
                break
        rng = np.random.default_rng(REFINE_SEED)
        for index in rng.choice(len(gm_s), size=min(REFINE_RANDOM_STARTS, len(gm_s)), replace=False):
            starts.append(y_s[index])
        for start in extra_starts:
            starts.append(np.asarray(start, dtype=float))

        results: list[tuple[float, np.ndarray]] = []
        for start in starts:
            y0 = np.array(start, dtype=float)
            for low, high in zip(bounds[:-1], bounds[1:]):
                y0[low:high] = (1.0 - REFINE_BLEND) * y0[low:high] / y0[low:high].sum() \
                    + REFINE_BLEND / (high - low)
            fit = minimize(objective, np.log(y0), jac=True, method="L-BFGS-B",
                           options={"maxiter": 3000, "maxfun": 20000, "gtol": 1.0e-7, "ftol": 1.0e-15})
            results.append((float(fit.fun), fit.x))
        results.sort(key=lambda item: item[0])
        best_value, best_z = results[0]
        # Выборочный минимум — тоже кандидат: уточнение не должно ухудшать.
        if float(driving[sampled]) < best_value:
            best_y = y_s[sampled]
            best_value = float(driving[sampled])
        else:
            best_y = site_fractions(best_z)
        _, _, x_best = evaluate(best_y)
        return {
            "по выборке 13-А, Дж/моль": float(driving[sampled]),
            "уточнённое, Дж/моль": float(best_value),
            "стартов": len(starts),
            "стартов в пределах 1 Дж/моль от лучшего": int(sum(value - results[0][0] <= 1.0
                                                               for value, _ in results)),
            "точек выборки": int(len(gm_s)),
            "состав в точке минимума, мольные доли": {
                element: float(value) for element, value in zip(elements, x_best)},
            "доли в подрешётках в точке минимума": [float(value) for value in best_y],
        }


# --------------------------------------------------------------------------- #
# Разбор равновесия по вершинам
# --------------------------------------------------------------------------- #


def parse_vertices(result: Any, constituents: Mapping[str, Sequence[Sequence[str]]],
                   elements: Sequence[str], keep_sites: Sequence[str]) -> dict[str, Any]:
    names = [str(name) for name in np.asarray(result.Phase.values, dtype=str).ravel()]
    amounts = np.asarray(result.NP.values, dtype=float).ravel()
    order = [str(name) for name in result.coords["component"].values]
    x_vertices = np.asarray(result.X.values, dtype=float).reshape(len(names), len(order))
    y_vertices = np.asarray(result.Y.values, dtype=float).reshape(len(names), -1)
    mu_values = np.asarray(result.MU.values, dtype=float).ravel()
    mu = {element: float(mu_values[order.index(element)]) for element in elements}

    phases: dict[str, dict[str, Any]] = {}
    vertices: list[dict[str, Any]] = []
    for position, (name, amount) in enumerate(zip(names, amounts)):
        if not name or not np.isfinite(amount) or float(amount) <= PRESENT_FLOOR:
            continue
        composition = {element: float(x_vertices[position, order.index(element)]) for element in elements}
        bucket = phases.setdefault(name, {"мольная доля": 0.0, "вершин": 0,
                                          "x": {element: 0.0 for element in elements}})
        bucket["мольная доля"] += float(amount)
        bucket["вершин"] += 1
        for element in elements:
            bucket["x"][element] += float(amount) * composition[element]
        entry: dict[str, Any] = {"фаза": name, "мольная доля": float(amount), "x": composition}
        if name in keep_sites:
            n_dof = sum(len(sub) for sub in constituents[name])
            flat = [float(value) for value in y_vertices[position][:n_dof]]
            entry["y"] = flat
            sublattices: list[dict[str, float]] = []
            cursor = 0
            for species in constituents[name]:
                sublattices.append({element: flat[cursor + index] for index, element in enumerate(species)})
                cursor += len(species)
            entry["подрешётки"] = sublattices
        vertices.append(entry)
    for bucket in phases.values():
        total = bucket["мольная доля"]
        bucket["x"] = {element: value / total for element, value in bucket["x"].items()}
    return {
        "сумма мольных долей фаз": float(sum(bucket["мольная доля"] for bucket in phases.values())),
        "фазы": {name: phases[name] for name in sorted(phases)},
        "вершины": vertices,
        "мю, Дж/моль": mu,
    }


def converged(payload: Mapping[str, Any]) -> bool:
    if not payload["фазы"]:
        return False
    return abs(float(payload["сумма мольных долей фаз"]) - 1.0) <= SUM_TOLERANCE


# --------------------------------------------------------------------------- #
# Потомок e1: сечения Ni–Cr–Mo
# --------------------------------------------------------------------------- #


def solve_ternary(ctx: w13a.TernaryContext, temperature_c: float, steps_cr: int, steps_mo: int,
                  pdens: int) -> dict[str, Any]:
    from pycalphad import equilibrium, variables as v

    started = time.perf_counter()
    conditions: dict[Any, float] = {v.N: 1.0, v.P: 101325.0, v.T: float(temperature_c) + 273.15}
    conditions.update({v.X(element): value for element, value in w13a.node_x(steps_cr, steps_mo).items()})
    result = equilibrium(ctx.db, list(w13a.TERNARY_COMPONENTS), ctx.phases, conditions,
                         model=ctx.models, phase_records=ctx.phase_records,
                         calc_opts={"pdens": int(pdens)})
    payload = parse_vertices(result, ctx.constituents, w13a.TERNARY_ELEMENTS, CANDIDATES)
    del result
    gc.collect()
    payload.update({
        "T, °C": float(temperature_c), "шагов CR": int(steps_cr), "шагов MO": int(steps_mo),
        "узел, ат. %": w13a.node_at(steps_cr, steps_mo), "pdens": int(pdens),
        "секунд": time.perf_counter() - started,
    })
    return payload


def child_sections(min_free_gib: float, force: bool) -> dict[str, Any]:
    cache = JsonlCache("e1_points.jsonl")
    if force:
        cache.reset()
    tasks = w13a.task_list(SECTIONS_C, edge_scan=False)
    todo = [task for task in tasks if w13a.point_key(*task[:3]) not in cache.records]
    log(f"e1: узлов {len(tasks)}, в кэше {len(tasks) - len(todo)}, считать {len(todo)}")
    failed: list[dict[str, Any]] = []
    stopped = None
    if todo:
        free = w12.free_gib()
        if free < float(min_free_gib):
            return {"остановка": f"свободной физической памяти {free:.2f} ГиБ при пороге входа "
                                 f"{float(min_free_gib):.1f} ГиБ; база не разбиралась"}
        ctx = w13a.TernaryContext()
        started = time.perf_counter()
        for done, (temperature, steps_cr, steps_mo, kind) in enumerate(todo, start=1):
            free = w12.free_gib()
            if free < ABORT_FREE_GIB:
                stopped = (f"свободной физической памяти {free:.2f} ГиБ, ниже аварийного порога "
                           f"{ABORT_FREE_GIB:.1f} ГиБ; остаток не считался")
                break
            payload = solve_ternary(ctx, temperature, steps_cr, steps_mo, PDENS)
            retries: list[int] = []
            for retry in RETRY_PDENS:
                if converged(payload):
                    break
                retries.append(int(payload["pdens"]))
                payload = solve_ternary(ctx, temperature, steps_cr, steps_mo, retry)
            payload["неудачные pdens"] = retries
            payload["вид"] = kind
            if converged(payload):
                cache.put(w13a.point_key(temperature, steps_cr, steps_mo), payload)
            else:
                failed.append({"T, °C": temperature, "узел, ат. %": w13a.node_at(steps_cr, steps_mo)})
            if done % 50 == 0 or done == len(todo):
                log(f"e1: {done}/{len(todo)}, {time.perf_counter() - started:.0f} с, "
                    f"свободно {w12.free_gib():.2f} ГиБ")
    return {"узлов всего": len(tasks), "посчитано сейчас": len(todo), "не сошлись": failed,
            "остановка": stopped}


# --------------------------------------------------------------------------- #
# Потомок e2: равновесия сплава в трёх наборах фаз
# --------------------------------------------------------------------------- #


def alloy_key(variant: str, mole: Mapping[str, float], temperature_c: float) -> str:
    return f"{variant}|{w11.composition_id(mole)}|{temperature_c:.4f}"


def variant_phases(ctx: w11.Context, variant: str) -> list[str]:
    if variant == VARIANT_FULL:
        return list(ctx.phases)
    if variant == VARIANT_NO_P:
        return [name for name in ctx.phases if name != P_PHASE]
    return [name for name in ctx.phases if name in FORCED_PHASES]


def solve_alloy(ctx: w11.Context, constituents: Mapping[str, Any], mole: Mapping[str, float],
                temperature_c: float, phases: Sequence[str], pdens: int) -> dict[str, Any]:
    from pycalphad import equilibrium, variables as v

    started = time.perf_counter()
    conditions: dict[Any, float] = {v.N: 1.0, v.P: 101325.0, v.T: float(temperature_c) + 273.15}
    conditions.update({v.X(element): value for element, value in w11.independent_x(mole).items()})
    models, phase_records = ctx.compiled()
    result = equilibrium(ctx.db, list(w11.COMPONENTS), list(phases), conditions,
                         model=models, phase_records=phase_records, calc_opts={"pdens": int(pdens)})
    payload = parse_vertices(result, constituents, w11.ELEMENTS, [*CANDIDATES, MATRIX])
    del result
    gc.collect()
    payload.update({"T, °C": float(temperature_c), "pdens": int(pdens),
                    "секунд равновесия": time.perf_counter() - started})
    return payload


def child_alloy(min_free_gib: float, force: bool) -> dict[str, Any]:
    cache = JsonlCache("e2_points.jsonl")
    if force:
        cache.reset()
    free = w12.free_gib()
    if free < float(min_free_gib):
        return {"остановка": f"свободной физической памяти {free:.2f} ГиБ при пороге входа "
                             f"{float(min_free_gib):.1f} ГиБ; база не разбиралась"}
    ctx = w11.Context()
    mole = w11.wt_to_mole(ctx, w11.full_wt())
    todo = [(t, variant) for t in REQUIRED_C for variant in VARIANTS
            if alloy_key(variant, mole, t) not in cache.records]
    log(f"e2: равновесий {len(REQUIRED_C) * len(VARIANTS)}, считать {len(todo)}")
    failed: list[dict[str, Any]] = []
    stopped = None
    if todo:
        models, phase_records = ctx.compiled()
        constituents = {name: [sorted(str(s.name) for s in sub) for sub in models[name].constituents]
                        for name in ctx.phases}
        engine = DistanceEngine(ctx.db, w11.COMPONENTS, models, phase_records)
        for temperature, variant in todo:
            free = w12.free_gib()
            if free < ABORT_FREE_GIB:
                stopped = (f"свободной физической памяти {free:.2f} ГиБ, ниже аварийного порога "
                           f"{ABORT_FREE_GIB:.1f} ГиБ; остаток не считался")
                break
            phases = variant_phases(ctx, variant)
            payload = solve_alloy(ctx, constituents, mole, temperature, phases, PDENS)
            retries: list[int] = []
            for retry in RETRY_PDENS:
                if converged(payload):
                    break
                retries.append(int(payload["pdens"]))
                payload = solve_alloy(ctx, constituents, mole, temperature, phases, retry)
            payload["неудачные pdens"] = retries
            payload["набор фаз"] = variant
            payload["фаз в наборе"] = len(phases)
            if not converged(payload):
                failed.append({"T, °C": temperature, "набор фаз": variant,
                               "сумма": payload["сумма мольных долей фаз"]})
                continue

            started = time.perf_counter()
            targets = sorted(set(CANDIDATES) | set(payload["фазы"]))
            distances: dict[str, Any] = {}
            for phase in targets:
                starts = [vertex["y"] for vertex in payload["вершины"]
                          if vertex["фаза"] == phase and "y" in vertex]
                distances[phase] = engine.distance(temperature, phase, payload["мю, Дж/моль"], starts)
                distances[phase]["в равновесии"] = phase in payload["фазы"]
                distances[phase]["в наборе фаз расчёта"] = phase in phases
            payload["расстояние до устойчивости"] = distances
            payload["секунд расстояний"] = time.perf_counter() - started
            payload["состав сплава, мольные доли"] = dict(mole)
            cache.put(alloy_key(variant, mole, temperature), payload)
            log(f"e2: {temperature:.0f} °C, {variant}: {' + '.join(payload['фазы'])}; "
                f"σ {distances[SIGMA]['уточнённое, Дж/моль']:.0f} Дж/моль; "
                f"{payload['секунд равновесия']:.0f} + {payload['секунд расстояний']:.0f} с")
            gc.collect()
    return {"равновесий всего": len(REQUIRED_C) * len(VARIANTS), "посчитано сейчас": len(todo),
            "не сошлись": failed, "остановка": stopped, "фазы расчёта": list(ctx.phases),
            "исключено из расчёта": list(ctx.excluded_phases),
            "состав, масс. %": w11.full_wt(), "состав, мольные доли": dict(mole),
            "атомные массы": dict(ctx.masses)}


# --------------------------------------------------------------------------- #
# Потомок и замер памяти
# --------------------------------------------------------------------------- #


def memory_report(stem: str, record: Mapping[str, Any], seconds: float, final: bool = True) -> Path | None:
    if not record.get("замеров"):
        return None
    payload = {key: (round(value, 3) if isinstance(value, float) else value)
               for key, value in record.items() if key != "начало, perf_counter"}
    payload["секунд под наблюдением"] = round(seconds, 1)
    payload["шаг опроса, с"] = w11.MEMORY_POLL_SECONDS
    payload["замер завершён"] = bool(final)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"e_memory_{stem}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    if final:
        log(f"память: пик набора {payload['пик рабочего набора дерева, ГиБ']:.3f} ГиБ, "
            f"минимум свободной {payload['минимум свободной физической, ГиБ']:.2f} ГиБ")
    return path


def memory_watch(process: Any, stop: Any, record: dict[str, Any], stem: str) -> None:
    import psutil

    virtual = psutil.virtual_memory()
    record.update({
        "физической памяти всего, ГиБ": virtual.total / 1024.0 ** 3,
        "свободной физической на старте, ГиБ": virtual.available / 1024.0 ** 3,
        "замеров": 0,
        "пик рабочего набора дерева, ГиБ": 0.0,
        "пик фиксации дерева, ГиБ": 0.0,
        "минимум свободной физической, ГиБ": virtual.available / 1024.0 ** 3,
    })
    fields = (
        ("пик рабочего набора дерева, ГиБ", "рабочий набор дерева, ГиБ", max),
        ("пик фиксации дерева, ГиБ", "фиксация дерева, ГиБ", max),
        ("минимум свободной физической, ГиБ", "свободной физической, ГиБ", min),
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


def run_child(kind: str, min_free_gib: float, force: bool,
              complete: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    import psutil

    stem = f"{kind}_min-free-gib_{min_free_gib:g}".replace(".", "_")
    handoff = CACHE / f"child_{stem}.json"
    CACHE.mkdir(parents=True, exist_ok=True)
    if complete and not force:
        # Всё в кэше: потомок не запускается, чтобы не переписать замер памяти
        # считавшего прогона замером пустого.
        memory = OUT / f"e_memory_{stem}.json"
        payload = json.loads(handoff.read_text("utf-8")) if handoff.is_file() else {}
        measurement = json.loads(memory.read_text("utf-8")) if memory.is_file() else {}
        measurement["этот запуск"] = "все точки из кэша, потомок не запускался"
        return payload, measurement
    if handoff.is_file():
        handoff.unlink()
    command = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--child", kind,
               "--min-free-gib", f"{min_free_gib:g}", "--handoff", str(handoff)]
    if force:
        command.append("--force")
    started = time.perf_counter()
    popen = subprocess.Popen(command, env=dict(os.environ, PYTHONHASHSEED="0"), cwd=str(ROOT))
    record: dict[str, Any] = {"потомок": kind, "начало, perf_counter": started}
    stop = threading.Event()
    watcher = threading.Thread(target=memory_watch, args=(psutil.Process(popen.pid), stop, record, stem),
                               daemon=True)
    watcher.start()
    returncode = popen.wait()
    stop.set()
    seconds = time.perf_counter() - started
    watcher.join(timeout=w11.MEMORY_POLL_SECONDS * 2)
    memory_report(stem, record, seconds)
    if returncode != 0 or not handoff.is_file():
        raise RuntimeError(f"потомок {kind} завершился с кодом {returncode}")
    measurement = {key: value for key, value in record.items() if key != "начало, perf_counter"}
    measurement["секунд прогона"] = round(seconds, 1)
    return json.loads(handoff.read_text("utf-8")), measurement


def load_cache(name: str) -> list[dict[str, Any]]:
    return list(JsonlCache(name).records.values())


# --------------------------------------------------------------------------- #
# e1. Составы фаз на сечениях
# --------------------------------------------------------------------------- #


def step_e1(min_free_gib: float, force: bool) -> None:
    cached = set(JsonlCache("e1_points.jsonl").records)
    complete = all(w13a.point_key(*task[:3]) in cached for task in w13a.task_list(SECTIONS_C, edge_scan=False))
    payload, measurement = run_child("sections", min_free_gib, force, complete)
    points = load_cache("e1_points.jsonl")

    # Сверка с кэшем 13-А: наборы фаз в тех же узлах обязаны совпасть.
    reference = {w13a.point_key(p["T, °C"], p["шагов CR"], p["шагов MO"]): w13a.phase_set(p)
                 for p in w13a.load_points() if p.get("вид") == "сечение"}
    mismatches = []
    for point in points:
        key = w13a.point_key(point["T, °C"], point["шагов CR"], point["шагов MO"])
        own = " + ".join(sorted(point["фазы"]))
        if key in reference and reference[key] != own:
            mismatches.append({"узел": key, "13-А": reference[key], "13-Е": own})

    rows: list[dict[str, Any]] = []
    for point in points:
        node = point["узел, ат. %"]
        phase_set = " + ".join(sorted(point["фазы"]))
        for vertex in point["вершины"]:
            if vertex["фаза"] not in CANDIDATES:
                continue
            at = ternary_at(vertex["x"])
            near = closeness(at, MEASURED_TCP_NORM)
            row: dict[str, Any] = {
                "фаза": vertex["фаза"], "T, °C": point["T, °C"],
                "узел Ni, ат. %": node["NI"], "узел Cr, ат. %": node["CR"], "узел Mo, ат. %": node["MO"],
                "фазовый набор": phase_set,
                "мольная доля фазы, %": 100.0 * vertex["мольная доля"],
                "Ni в фазе, ат. %": at["NI"], "Cr в фазе, ат. %": at["CR"], "Mo в фазе, ат. %": at["MO"],
                **{f"{key} (до измеренной)": value for key, value in near.items()},
            }
            for index, sublattice in enumerate(vertex.get("подрешётки", []), start=1):
                for element, value in sorted(sublattice.items()):
                    row[f"y({element}) подрешётки {index}"] = value
            rows.append(row)
    table = pd.DataFrame(rows).sort_values(["фаза", "T, °C", "узел Cr, ат. %", "узел Mo, ат. %"])
    write_csv(table, "e1_phase_compositions.csv")

    def block_summary(block: pd.DataFrame) -> dict[str, Any]:
        if not len(block):
            return {"вершин": 0}
        nearest = block.loc[block["евклид, ат. % (до измеренной)"].idxmin()]
        summary: dict[str, Any] = {
            "вершин": int(len(block)),
            "узлов": int(len(block[["T, °C", "узел Cr, ат. %", "узел Mo, ат. %"]].drop_duplicates())),
        }
        for element in TERNARY:
            column = f"{LABEL[element]} в фазе, ат. %"
            summary[f"{column} (мин…макс)"] = [float(block[column].min()), float(block[column].max())]
        summary["ближайший к измеренному состав фазы, ат. %"] = {
            LABEL[e]: float(nearest[f"{LABEL[e]} в фазе, ат. %"]) for e in TERNARY}
        summary["его расстояние до измеренного (евклид / Чебышёв), ат. %"] = [
            float(nearest["евклид, ат. % (до измеренной)"]), float(nearest["Чебышёв, ат. % (до измеренной)"])]
        summary["его узел и температура"] = {
            "T, °C": float(nearest["T, °C"]), "Ni": float(nearest["узел Ni, ат. %"]),
            "Cr": float(nearest["узел Cr, ат. %"]), "Mo": float(nearest["узел Mo, ат. %"]),
            "фазовый набор": nearest["фазовый набор"]}
        summary["доля вершин ближе 5 ат. % (евклид)"] = float(
            (block["евклид, ат. % (до измеренной)"] <= 5.0).mean())
        return summary

    per_phase = {}
    for phase in CANDIDATES:
        block = table[table["фаза"] == phase]
        per_phase[phase] = {
            "пределы модели": MODEL_LIMITS[phase],
            "все сечения": block_summary(block),
            "по температурам": {f"{t:g} °C": block_summary(block[block["T, °C"] == t]) for t in SECTIONS_C},
        }

    # Узел сетки у измеренного состава: Ni 37,5 · Cr 22,5 · Mo 40 при каждой температуре.
    at_measured = []
    for point in points:
        node = point["узел, ат. %"]
        if abs(node["CR"] - 22.5) < 1e-9 and abs(node["MO"] - 40.0) < 1e-9:
            entry = {"T, °C": point["T, °C"], "узел, ат. %": node,
                     "фазовый набор": " + ".join(sorted(point["фазы"])),
                     "доли фаз, мольн. %": {n: 100.0 * p["мольная доля"] for n, p in point["фазы"].items()},
                     "составы фаз, ат. %": {n: ternary_at(p["x"]) for n, p in point["фазы"].items()}}
            at_measured.append(entry)

    write_json({
        "подпункт": "13-Е, пункт 1. Состав σ-фазы (и MU_PHASE, D_NIMO, P_PHASE) во всём поле устойчивости",
        "база": DB_REL, "sha256 базы": w12.database_sha256(),
        "сечения, °C": list(SECTIONS_C), "сетка": "шаг 2,5 ат. %, Ni ≥ 15 ат. %, как в 13-А",
        "измеренная ТПУ-фаза, ат. % (как в задании)": MEASURED_TCP_AT,
        "измеренная ТПУ-фаза, нормированная на 100, ат. %": MEASURED_TCP_NORM,
        "источник измерения": MEASURED_SOURCE,
        "фазы": per_phase,
        "узел сетки у измеренного состава (Ni 37,5 · Cr 22,5 · Mo 40)": sorted(at_measured, key=lambda e: e["T, °C"]),
        "сверка наборов фаз с кэшем 13-А": {"узлов сравнено": len(set(reference) & {
            w13a.point_key(p["T, °C"], p["шагов CR"], p["шагов MO"]) for p in points}),
            "расхождений": mismatches},
        "узлы, сошедшиеся не с первой pdens": [
            {"T, °C": p["T, °C"], "узел, ат. %": p["узел, ат. %"], "неудачные pdens": p["неудачные pdens"]}
            for p in points if p.get("неудачные pdens")],
        "потомок": payload,
        "порог входа, ГиБ": {"по умолчанию": MIN_FREE_GIB, "задание 13-Е": TASK_MIN_FREE_GIB,
                             "фактический": float(min_free_gib)},
        "аварийный порог, ГиБ": ABORT_FREE_GIB,
        "замер памяти": measurement,
    }, "e1_summary.json")


# --------------------------------------------------------------------------- #
# e2, e3. Расстояние до устойчивости при составе сплава
# --------------------------------------------------------------------------- #


def alloy_points() -> dict[tuple[str, float], dict[str, Any]]:
    return {(p["набор фаз"], float(p["T, °C"])): p for p in load_cache("e2_points.jsonl")}


def distance_rows(points: Mapping[tuple[str, float], Mapping[str, Any]],
                  phases: Sequence[str]) -> pd.DataFrame:
    rows = []
    for (variant, temperature), point in sorted(points.items(), key=lambda item: (VARIANTS.index(item[0][0]), item[0][1])):
        for phase in phases:
            entry = point["расстояние до устойчивости"].get(phase)
            if entry is None:
                continue
            x = entry["состав в точке минимума, мольные доли"]
            at = ternary_at(x)
            refined = float(entry["уточнённое, Дж/моль"])
            rows.append({
                "набор фаз": variant, "T, °C": temperature, "фаза": phase,
                "фазовый набор равновесия": " + ".join(point["фазы"]),
                "в равновесии": "да" if entry["в равновесии"] else "нет",
                "в наборе фаз расчёта": "да" if entry["в наборе фаз расчёта"] else "нет",
                "до устойчивости, уточнённое, Дж/моль": refined,
                "до устойчивости, по выборке 13-А, Дж/моль": float(entry["по выборке 13-А, Дж/моль"]),
                "то же в RT": refined / (8.31446261815324 * (temperature + 273.15)),
                "стартов в пределах 1 Дж/моль от лучшего": entry["стартов в пределах 1 Дж/моль от лучшего"],
                "стартов": entry["стартов"],
                "Ni в точке минимума, ат. % (Ni+Cr+Mo=100)": at["NI"],
                "Cr в точке минимума, ат. % (Ni+Cr+Mo=100)": at["CR"],
                "Mo в точке минимума, ат. % (Ni+Cr+Mo=100)": at["MO"],
                "прочие элементы в точке минимума, ат. %": 100.0 * sum(
                    value for element, value in x.items() if element not in TERNARY),
                **{f"x({element}) в точке минимума": value for element, value in sorted(x.items())},
            })
    return pd.DataFrame(rows)


def controls(points: Mapping[tuple[str, float], Mapping[str, Any]]) -> dict[str, Any]:
    """Фазы, которые в равновесии есть, обязаны получить ноль; отрицательное у
    отсутствующей — признак пропущенной решателем фазы."""

    present, negative = [], []
    for (variant, temperature), point in points.items():
        for phase, entry in point["расстояние до устойчивости"].items():
            value = float(entry["уточнённое, Дж/моль"])
            if entry["в равновесии"]:
                present.append({"набор фаз": variant, "T, °C": temperature, "фаза": phase, "Дж/моль": value})
            elif value < -CONTROL_TOLERANCE_J and entry["в наборе фаз расчёта"]:
                negative.append({"набор фаз": variant, "T, °C": temperature, "фаза": phase, "Дж/моль": value})
    worst = max((abs(item["Дж/моль"]) for item in present), default=None)
    return {"допуск, Дж/моль": CONTROL_TOLERANCE_J,
            "фаз в равновесии проверено": len(present),
            "наибольшее |расстояние| у фаз в равновесии, Дж/моль": worst,
            "вне допуска": [item for item in present if abs(item["Дж/моль"]) > CONTROL_TOLERANCE_J],
            "отрицательные у фаз, отсутствующих в равновесии (из набора расчёта)": negative}


def wave12_check(points: Mapping[tuple[str, float], Mapping[str, Any]]) -> list[dict[str, Any]]:
    table = pd.read_csv(w12.OUT / "e1_phase_fractions.csv", **CSV_READ)
    out = []
    for temperature in REQUIRED_C:
        point = points.get((VARIANT_FULL, temperature))
        if point is None:
            continue
        block = table[table["T, °C"] == temperature]
        theirs = {row["фаза"]: float(row["мольная доля, %"]) for _, row in block.iterrows()}
        ours = {name: 100.0 * phase["мольная доля"] for name, phase in point["фазы"].items()}
        out.append({"T, °C": temperature,
                    "набор 12-2": " + ".join(sorted(theirs)), "набор 13-Е": " + ".join(sorted(ours)),
                    "наибольшее расхождение доли, п. п.": max(
                        abs(theirs.get(name, 0.0) - ours.get(name, 0.0)) for name in set(theirs) | set(ours))})
    return out


def step_e2(min_free_gib: float, force: bool) -> None:
    complete = len({(p["набор фаз"], float(p["T, °C"])) for p in load_cache("e2_points.jsonl")})         == len(VARIANTS) * len(REQUIRED_C)
    payload, measurement = run_child("alloy", min_free_gib, force, complete)
    points = alloy_points()
    table = distance_rows(points, CANDIDATES)
    write_csv(table[table["фаза"] == SIGMA], "e2_sigma_distance.csv")
    write_csv(distance_rows(points, sorted({p for point in points.values()
                                            for p in point["расстояние до устойчивости"]})),
              "e2_all_distances.csv")

    def series(phase: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for variant in VARIANTS:
            block = table[(table["фаза"] == phase) & (table["набор фаз"] == variant)]
            out[variant] = [{
                "T, °C": float(row["T, °C"]),
                "уточнённое, Дж/моль": float(row["до устойчивости, уточнённое, Дж/моль"]),
                "по выборке 13-А, Дж/моль": float(row["до устойчивости, по выборке 13-А, Дж/моль"]),
                "в RT": float(row["то же в RT"]),
                "в равновесии": row["в равновесии"],
                "в наборе фаз расчёта": row["в наборе фаз расчёта"],
                "фазовый набор равновесия": row["фазовый набор равновесия"],
                "состав в точке минимума, Ni/Cr/Mo ат. %": [
                    float(row["Ni в точке минимума, ат. % (Ni+Cr+Mo=100)"]),
                    float(row["Cr в точке минимума, ат. % (Ni+Cr+Mo=100)"]),
                    float(row["Mo в точке минимума, ат. % (Ni+Cr+Mo=100)"])],
                "прочие элементы, ат. %": float(row["прочие элементы в точке минимума, ат. %"]),
            } for _, row in block.sort_values("T, °C").iterrows()]
        return out

    common = {
        "определение": ("min по составам фазы (G_m − Σ μ_i·x_i), Дж/моль атомов, при химических "
                        "потенциалах равновесия сплава; 0 — фаза устойчива"),
        "по выборке 13-А": f"минимум по выборке calculate, pdens {DISTANCE_PDENS} — механизм 13-А без изменений",
        "уточнённое": (f"L-BFGS по логитам долей в подрешётках из {REFINE_BEST_STARTS} лучших и "
                       f"{REFINE_RANDOM_STARTS} случайных точек выборки (и из вершины равновесия, если фаза "
                       f"в нём есть), смешанных с равномерным составом в доле {REFINE_BLEND}; функция и "
                       f"градиент — PhaseRecord равновесия"),
        "наборы фаз": {VARIANT_FULL: "все фазы, как в волне 12", VARIANT_NO_P: "все, кроме P_PHASE",
                       VARIANT_FORCED: "только FCC_A1 и SIGMA"},
        "контроль": controls(points),
        "сверка равновесий «полный» с волной 12 (e1_phase_fractions.csv)": wave12_check(points),
    }
    write_json({"подпункт": "13-Е, пункт 2. Расстояние до устойчивости σ при составе сплава",
                **common, "SIGMA": series(SIGMA),
                "потомок": payload, "замер памяти": measurement,
                "порог входа, ГиБ": {"по умолчанию": MIN_FREE_GIB, "задание 13-Е": TASK_MIN_FREE_GIB,
                                     "фактический": float(min_free_gib)},
                "аварийный порог, ГиБ": ABORT_FREE_GIB}, "e2_summary.json")


def step_e3(**_: Any) -> None:
    points = alloy_points()
    table = distance_rows(points, (MU, DELTA, P_PHASE))
    write_csv(table, "e3_mu_dnimo_distance.csv")
    summary: dict[str, Any] = {"подпункт": "13-Е, пункт 3. Расстояние до устойчивости MU_PHASE и D_NIMO "
                                           "(P_PHASE — для сравнения)"}
    for phase in (MU, DELTA, P_PHASE):
        summary[phase] = {
            variant: [{"T, °C": float(r["T, °C"]),
                       "уточнённое, Дж/моль": float(r["до устойчивости, уточнённое, Дж/моль"]),
                       "по выборке 13-А, Дж/моль": float(r["до устойчивости, по выборке 13-А, Дж/моль"]),
                       "в равновесии": r["в равновесии"],
                       "в наборе фаз расчёта": r["в наборе фаз расчёта"],
                       "состав в точке минимума, Ni/Cr/Mo ат. %": [
                           float(r["Ni в точке минимума, ат. % (Ni+Cr+Mo=100)"]),
                           float(r["Cr в точке минимума, ат. % (Ni+Cr+Mo=100)"]),
                           float(r["Mo в точке минимума, ат. % (Ni+Cr+Mo=100)"])],
                       "прочие элементы, ат. %": float(r["прочие элементы в точке минимума, ат. %"])}
                      for _, r in table[(table["фаза"] == phase) & (table["набор фаз"] == variant)]
                      .sort_values("T, °C").iterrows()]
            for variant in VARIANTS}
    write_json(summary, "e3_summary.json")


# --------------------------------------------------------------------------- #
# e4. Принудительное равновесие FCC_A1 + SIGMA
# --------------------------------------------------------------------------- #


def mass_fractions(point: Mapping[str, Any], masses: Mapping[str, float]) -> dict[str, float]:
    weights = {name: phase["мольная доля"] * sum(phase["x"][e] * masses[e] for e in phase["x"])
               for name, phase in point["фазы"].items()}
    total = sum(weights.values())
    return {name: value / total for name, value in weights.items()}


def lever_from_measurement(alloy_at: Mapping[str, float]) -> dict[str, Any]:
    """Доля ТПУ-фазы, при которой измеренные составы матрицы и фазы сходятся с
    составом сплава по Ni, Cr, Mo (наименьшие квадраты, система Ni+Cr+Mo=100)."""

    a = np.array([MEASURED_TCP_NORM[e] - MEASURED_MATRIX_NORM[e] for e in TERNARY])
    b = np.array([alloy_at[e] - MEASURED_MATRIX_NORM[e] for e in TERNARY])
    f_ls = float(a @ b / (a @ a))
    per_element = {LABEL[e]: float(b[i] / a[i]) for i, e in enumerate(TERNARY)}
    residual = {LABEL[e]: float((1 - f_ls) * MEASURED_MATRIX_NORM[e] + f_ls * MEASURED_TCP_NORM[e] - alloy_at[e])
                for e in TERNARY}
    return {"доля ТПУ-фазы, мольн. % (наименьшие квадраты)": 100.0 * f_ls,
            "то же по каждому элементу отдельно, мольн. %": {k: 100.0 * v for k, v in per_element.items()},
            "невязка баланса при этой доле, ат. %": residual}


def step_e4(**_: Any) -> None:
    points = alloy_points()
    summary12 = json.loads((w12.OUT / "e1_summary.json").read_text("utf-8"))
    masses = w13a.tdb_masses()
    any_point = next(iter(points.values()))
    alloy_x = any_point["состав сплава, мольные доли"]
    alloy_ternary = ternary_at(alloy_x)
    lever = lever_from_measurement(alloy_ternary)

    rows = []
    for variant in VARIANTS:
        for temperature in REQUIRED_C:
            point = points.get((variant, temperature))
            if point is None:
                continue
            mass = mass_fractions(point, masses)
            matrix = point["фазы"].get(MATRIX)
            sigma = point["фазы"].get(SIGMA)
            sigma_vertices = [v for v in point["вершины"] if v["фаза"] == SIGMA]
            row: dict[str, Any] = {
                "набор фаз": variant, "T, °C": temperature,
                "фазовый набор": " + ".join(point["фазы"]),
                "σ, мольн. %": 100.0 * sigma["мольная доля"] if sigma else 0.0,
                "σ, масс. %": 100.0 * mass.get(SIGMA, 0.0),
                "вершин σ": len(sigma_vertices),
                "FCC_A1, мольн. %": 100.0 * matrix["мольная доля"] if matrix else 0.0,
                **{f"{name}, мольн. %": 100.0 * phase["мольная доля"]
                   for name, phase in point["фазы"].items() if name not in (MATRIX, SIGMA)},
            }
            if matrix:
                at = ternary_at(matrix["x"])
                row.update({f"матрица {LABEL[e]}, ат. % (Ni+Cr+Mo=100)": at[e] for e in TERNARY})
                row.update({f"матрица {LABEL[e]}, ат. % (все элементы)": 100.0 * matrix["x"][e] for e in TERNARY})
                near = closeness(at, MEASURED_MATRIX_NORM)
                row.update({f"матрица: {k} (до измеренной)": v for k, v in near.items()})
            if sigma:
                at = ternary_at(sigma["x"])
                row.update({f"σ {LABEL[e]}, ат. % (Ni+Cr+Mo=100)": at[e] for e in TERNARY})
                row["σ прочие элементы, ат. %"] = 100.0 * sum(v for e, v in sigma["x"].items() if e not in TERNARY)
                near = closeness(at, MEASURED_TCP_NORM)
                row.update({f"σ: {k} (до измеренной ТПУ)": v for k, v in near.items()})
                for vertex in sigma_vertices[:1]:
                    for index, sub in enumerate(vertex["подрешётки"], start=1):
                        for element, value in sorted(sub.items()):
                            if value > 1e-4:
                                row[f"σ y({element}) подрешётки {index}"] = value
            rows.append(row)
    table = pd.DataFrame(rows)
    write_csv(table, "e4_forced_equilibria.csv")

    full_compositions = []
    for (variant, temperature), point in sorted(points.items(), key=lambda i: (VARIANTS.index(i[0][0]), i[0][1])):
        for name, phase in point["фазы"].items():
            full_compositions.append({"набор фаз": variant, "T, °C": temperature, "фаза": name,
                                      "мольная доля фазы, %": 100.0 * phase["мольная доля"],
                                      **{f"x({e})": phase["x"][e] for e in w12.ELEMENT_ORDER}})
    write_csv(pd.DataFrame(full_compositions), "e4_phase_compositions.csv")

    a4 = pd.read_csv(OUT / "a4_mo_balance.csv", **CSV_READ)
    a4_rows = a4[a4["состав реальной фазы"].str.startswith("ХН62М")]
    write_json({
        "подпункт": "13-Е, пункт 4. Принудительное равновесие FCC_A1 + SIGMA",
        "состав сплава, масс. %": summary12["состав, масс. %"],
        "состав сплава, Ni/Cr/Mo ат. % (Ni+Cr+Mo=100)": alloy_ternary,
        "измеренная матрица, ат. %": MEASURED_MATRIX_AT,
        "измеренная ТПУ-фаза, нормированная, ат. %": MEASURED_TCP_NORM,
        "источник измерения": MEASURED_SOURCE,
        "баланс по измеренным составам (без термодинамики)": lever,
        "13-А, пункт 4: доля ТПУ-фазы по балансу Mo, мольн. % (сверху / снизу, ХН62М-ВИ)": [
            {"T, °C": float(r["T, °C"]), "сверху": float(r["сверху (тот же связанный Mo), мольн. %"]),
             "снизу": float(r["снизу (тот же Mo в матрице), мольн. %"])} for _, r in a4_rows.iterrows()],
        "строки": rows,
    }, "e4_summary.json")


# --------------------------------------------------------------------------- #
# e5. Сводка для вывода
# --------------------------------------------------------------------------- #


def step_e5(**_: Any) -> None:
    e1 = json.loads((OUT / "e1_summary.json").read_text("utf-8"))
    e2 = json.loads((OUT / "e2_summary.json").read_text("utf-8"))
    e3 = json.loads((OUT / "e3_summary.json").read_text("utf-8"))
    e4 = json.loads((OUT / "e4_summary.json").read_text("utf-8"))
    by_phase = {}
    for phase in CANDIDATES:
        section = e1["фазы"][phase]["все сечения"]
        series = (e2 if phase == SIGMA else e3)[phase]
        by_phase[phase] = {
            "сечения: ближайший состав к измеренному, ат. %": section.get("ближайший к измеренному состав фазы, ат. %"),
            "сечения: его расстояние (евклид / Чебышёв), ат. %":
                section.get("его расстояние до измеренного (евклид / Чебышёв), ат. %"),
            "сечения: вершин": section.get("вершин"),
            "сплав: до устойчивости, уточнённое, Дж/моль": {
                variant: {f"{item['T, °C']:g}": item["уточнённое, Дж/моль"] for item in series[variant]}
                for variant in VARIANTS},
            "сплав: состав в точке минимума при 700 °C (полный набор), Ni/Cr/Mo ат. %": next(
                (item["состав в точке минимума, Ni/Cr/Mo ат. %"] for item in series[VARIANT_FULL]
                 if item["T, °C"] == MEASURED_T_C), None),
        }
    forced_700 = next((r for r in e4["строки"] if r["набор фаз"] == VARIANT_FORCED and r["T, °C"] == MEASURED_T_C), None)
    write_json({
        "подпункт": "13-Е, пункт 5. Сводка для вывода",
        "измеренная ТПУ-фаза, нормированная, ат. %": MEASURED_TCP_NORM,
        "измеренная матрица, ат. %": MEASURED_MATRIX_AT,
        "фазы": by_phase,
        "FCC+σ при 700 °C": forced_700,
        "баланс по измеренным составам": e4["баланс по измеренным составам (без термодинамики)"],
    }, "e5_summary.json")


# --------------------------------------------------------------------------- #
# Запуск
# --------------------------------------------------------------------------- #


STEPS = {"e1": step_e1, "e2": step_e2, "e3": step_e3, "e4": step_e4, "e5": step_e5}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Волна 13, задача 13-Е: σ-фаза mc_ni 2.036")
    parser.add_argument("--only", default="all", help="e1,e2,e3,e4,e5; через запятую")
    parser.add_argument("--force", action="store_true", help="пересчитать заново")
    parser.add_argument("--min-free-gib", type=float, default=MIN_FREE_GIB,
                        help=f"порог входа, ГиБ (по умолчанию {MIN_FREE_GIB})")
    parser.add_argument("--child", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--handoff", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    if args.child is not None:
        worker = {"sections": child_sections, "alloy": child_alloy}[args.child]
        payload = worker(args.min_free_gib, args.force)
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
        if name in ("e1", "e2"):
            free = w12.free_gib()
            if free < args.min_free_gib:
                log(f"{name} не запускался: свободно {free:.2f} ГиБ при пороге {args.min_free_gib:.1f}")
                # История отказов — одной строкой на отказ, для раздела «Память» отчёта.
                with (OUT / "e_refusals.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"время": time.strftime("%Y-%m-%d %H:%M:%S"), "подпункт": name,
                                             "свободно, ГиБ": round(free, 2),
                                             "порог входа, ГиБ": args.min_free_gib},
                                            ensure_ascii=False) + "\n")
                return 2
            STEPS[name](args.min_free_gib, args.force)
        else:
            STEPS[name]()
        log(f"=== {name.upper()} готов за {time.perf_counter() - started:.1f} с ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
