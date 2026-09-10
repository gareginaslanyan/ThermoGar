#!/usr/bin/env python3
"""Расчётное исследование сплава ХН62М(Sc)-ВИ (ЭК199-ВИ) на движке ThermoGar.

Задача 9 (`tasks/WAVE9_HN62M_OPUS.md`). Скрипт ничего не меняет в `app/`: он
пользуется публичными функциями проекта (`thermogar_parallel`,
`thermogar_equilibrium_core`, `thermogar_physical`, `thermogar_diffusion`,
`thermogar_release_policy`) и прямыми вызовами pycalphad/scheil — ровно так же,
как это делают tools/test_backend_calculations.py и приложение.

Запуск (интерпретатор — venv основного репозитория, PYTHONHASHSEED=0):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 ^
        tools\\study_hn62m.py --only all

Пункты запускаются по отдельности ключом ``--only 1`` … ``--only 9`` (плюс
``fix`` и ``excel``). Все равновесные точки кэшируются в
``results/hn62m/cache/eq_<набор фаз>.jsonl`` по ключу «температура + состав»,
поэтому повторный запуск не пересчитывает готовое, а падение на позднем пункте
не теряет ранние.

Память (правка мастера проекта к волне 9). Состав десятикомпонентный, сетка
pycalphad заметно тяжелее эталонных замеров ``tools/backend_reference.md``,
и прогон на четырёх воркерах система снимает по нехватке памяти. Поэтому:

* воркеров не больше двух (``--workers``, по умолчанию 1);
* каждый пункт по умолчанию выполняется в отдельном дочернем процессе — память
  освобождается операционной системой целиком, а не ``gc``-ом;
* точки решаются кусками по ``--chunk`` штук, результат каждой точки пишется в
  кэш сразу; между кусками — ``gc.collect()``;
* ``MemoryError`` не снимает пункт: ``pdens`` для куска понижается вдвое,
  куски пересчитываются по одной точке;
* пункт 1 (скан 400–1450 °C) считается в режиме «быстрый набор фаз»; режим
  «все фазы базы» остаётся у пункта 2 (8 точек) и у контрольных точек пункта 9.

Порядок и повторные запуски (вторая правка мастера). Пункты идут по возрастанию
стоимости, а не по номерам: 5 → 6 → 2 → 1 → 3 → 7 → 8 → 9 → 4. Изоплеты (4)
самые тяжёлые по памяти и стоят последними: если упадут, всё остальное уже
посчитано. Падение любого пункта не останавливает работу.

``results/hn62m/_progress.json`` хранит для каждого пункта отметку о завершении,
время и параметры прогона. Пункт с отметкой «готов» пропускается («пункт N
пропущен, посчитан ранее»); пересчёт — по ключу ``--force`` или автоматически,
если значимые параметры разошлись с записанными (в лог пишется, чем именно).
Значимыми считаются ``pdens`` и режим набора фаз: только они меняют числа.
Число воркеров записывается, но пересчёт не вызывает — движок
``thermogar_parallel`` даёт при ``PYTHONHASHSEED=0`` те же числа на любом числе
процессов, и пересчитывать из-за него нечего.

Внутри длинных пунктов тот же принцип на уровне точки: результат каждой точки
дописывается в ``cache/eq_<набор фаз>.jsonl`` сразу, ключ — температура и состав,
при перезапуске такие точки пропускаются и расчёт продолжается с места обрыва.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass
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

OUT = ROOT / "results" / "hn62m"
CACHE = OUT / "cache"

DB_REL = "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"
PDB_REL = "databases/physical/original/physical_data_v103.pdb"
DATABASE_KEY = "ni"
BALANCE = "NI"

# Плотность стартовой выборки ``equilibrium(..., calc_opts={"pdens": …})``.
# Значение проекта — 100 (``app/ThermoGar_app.py:3281`` и весь
# ``tools/backend_reference.md``); правка мастера требовала «снизить до 150–200»,
# то есть верхнюю границу, а 100 уже ниже неё и памяти просит меньше, поэтому
# оставлено 100 и записано в отчёт. Меняется ключом ``--pdens``.
PDENS = 100

# Плотности выборки, которыми пересчитывается точка, сошедшаяся в пустое
# решение (все NP = NaN при ok=True).
RETRY_PDENS = (200, 300, 50)

# Сколько точек решается за один заход, прежде чем результат уходит в кэш и
# вызывается ``gc.collect()``.
CHUNK_POINTS = 8

MAX_WORKERS = 2

# Состав марки, масс. %; основа — никель (дополняется до 100 %).
# Sc 0,05 % и P 0,025 % в mc_ni отсутствуют и в расчёт не входят (см. отчёт).
NOMINAL_WT: dict[str, float] = {
    "C": 0.005,
    "SI": 0.10,
    "MN": 0.50,
    "S": 0.020,
    "CR": 23.5,
    "MO": 13.0,
    "NB": 0.06,
    "AL": 0.25,
    "TI": 0.10,
    "FE": 0.50,
}

COMPONENTS: tuple[str, ...] = (
    "NI", "CR", "MO", "C", "SI", "MN", "S", "NB", "AL", "TI", "FE", "VA",
)
ELEMENTS: tuple[str, ...] = tuple(c for c in COMPONENTS if c != "VA")

# Пара порядок/беспорядок BCC_B2/BCC_A2 в mc_ni не строится, когда в системе
# есть внедрённый углерод: pycalphad поднимает ValueError ещё на этапе Model.
# Фаза исключается из всех наборов; факт зафиксирован в отчёте.
UNBUILDABLE_PHASES = ("BCC_B2",)

TCP_PHASES = (
    "P_PHASE", "MU_PHASE", "SIGMA", "CHI_A12", "LAVES", "LAV_C14",
    "R_PHASE", "D_NIMO",
)
CARBIDE_PHASES = (
    "M6C", "M6C_WY", "M23C6", "M23C6_WY", "M12C", "M7C3", "M3C2",
    "CEMENTITE", "KSI_CARBIDE",
)
WATCHED_PHASES = TCP_PHASES + CARBIDE_PHASES + ("NI2CR", "MNS_Q", "TI4C2S2",
                                                "GAMMA_PRIME", "DELTA", "ETA",
                                                "SIGMA", "LIQUID", "FCC_A1")

PRESENT_FLOOR = 1.0e-6  # доля фазы, ниже которой считаем, что фазы нет

MODE_ALL = "all"
MODE_FAST = "fast"


# --------------------------------------------------------------------------- #
# Контекст расчёта
# --------------------------------------------------------------------------- #


@dataclass
class Context:
    db: Any
    db_path: Path
    sha256: str
    masses: dict[str, float]
    phases_all: list[str]
    phases_fast: list[str]
    workers: int
    engine: Any = None

    def phases(self, mode: str) -> list[str]:
        return self.phases_all if mode == MODE_ALL else self.phases_fast

    def get_engine(self) -> Any:
        from thermogar_parallel import ParallelEquilibrium

        if self.engine is None:
            self.engine = ParallelEquilibrium(
                self.db_path, self.sha256, workers=self.workers, hash_seed="0"
            )
        return self.engine

    def close(self) -> None:
        if self.engine is not None:
            self.engine.close()
            self.engine = None


def log(message: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def build_context(workers: int) -> Context:
    from pycalphad import Database
    from pycalphad.core.utils import filter_phases, unpack_species
    from thermogar_parallel import file_sha256
    from thermogar_release_policy import preset_phases

    db_path = ROOT / DB_REL
    started = time.perf_counter()
    db = Database(str(db_path))
    log(f"база разобрана за {time.perf_counter() - started:.1f} с: {db_path.name}")

    phases_all = sorted(filter_phases(db, unpack_species(db, list(COMPONENTS))))
    dropped = [p for p in UNBUILDABLE_PHASES if p in phases_all]
    phases_all = [p for p in phases_all if p not in UNBUILDABLE_PHASES]
    if dropped:
        log(f"исключены нестроящиеся фазы: {', '.join(dropped)}")

    presets = json.loads((ROOT / "configs" / "phase_presets.json").read_text("utf-8"))
    phases_fast = sorted(preset_phases(presets, DATABASE_KEY, phases_all))

    masses = {e: float(db.refstates[e]["mass"]) for e in ELEMENTS}
    log(f"фаз «все» {len(phases_all)}, фаз «быстрый набор» {len(phases_fast)}")
    return Context(
        db=db,
        db_path=db_path,
        sha256=file_sha256(db_path),
        masses=masses,
        phases_all=phases_all,
        phases_fast=phases_fast,
        workers=workers,
    )


# --------------------------------------------------------------------------- #
# Состав
# --------------------------------------------------------------------------- #


def full_wt(overrides: dict[str, float] | None = None) -> dict[str, float]:
    """Полный массовый состав с никелем-основой, % по массе."""
    values = dict(NOMINAL_WT)
    if overrides:
        for element, value in overrides.items():
            values[element.upper()] = float(value)
    values = {e: v for e, v in values.items() if v > 0.0}
    values[BALANCE] = 100.0 - sum(values.values())
    if values[BALANCE] <= 0.0:
        raise ValueError("Сумма легирующих превысила 100 %.")
    return values


def wt_to_mole(ctx: Context, wt_percent: dict[str, float]) -> dict[str, float]:
    """Массовые % → мольные доли (той же функцией, что и приложение)."""
    from thermogar_equilibrium_core import mass_to_mole_fractions

    names = sorted(wt_percent)
    mass = tuple((e, wt_percent[e] / 100.0) for e in names)
    masses = tuple((e, ctx.masses[e]) for e in names)
    return {e: v for e, v in mass_to_mole_fractions(mass, masses)}


def independent_x(mole: dict[str, float]) -> dict[str, float]:
    """Мольные доли без элемента-основы — условия для pycalphad."""
    return {e: v for e, v in sorted(mole.items()) if e != BALANCE}


def mole_to_wt(ctx: Context, mole: dict[str, float]) -> dict[str, float]:
    """Мольные доли фазы → массовые %, для таблиц составов фаз."""
    from thermogar_equilibrium_core import mole_to_mass_fractions

    names = [e for e in sorted(mole) if mole[e] > 0.0]
    if not names:
        return {}
    total = sum(mole[e] for e in names)
    fractions = tuple((e, mole[e] / total) for e in names)
    masses = tuple((e, ctx.masses[e]) for e in names)
    return {e: 100.0 * v for e, v in mole_to_mass_fractions(fractions, masses)}


def phase_molar_mass(ctx: Context, composition: dict[str, float]) -> float:
    return sum(ctx.masses[e] * float(x) for e, x in composition.items() if e in ctx.masses)


def mass_fractions_of_phases(
    ctx: Context,
    fractions: dict[str, float],
    compositions: dict[str, dict[str, float]],
) -> dict[str, float]:
    """Массовые доли фаз из мольных долей и составов фаз."""
    weights: dict[str, float] = {}
    for phase, amount in fractions.items():
        molar_mass = phase_molar_mass(ctx, compositions.get(phase, {}))
        weights[phase] = float(amount) * molar_mass
    total = sum(weights.values())
    if total <= 0.0:
        return {phase: 0.0 for phase in fractions}
    return {phase: value / total for phase, value in weights.items()}


# --------------------------------------------------------------------------- #
# Кэш точек равновесия
# --------------------------------------------------------------------------- #


PROGRESS_PATH = OUT / "_progress.json"

# Режим набора фаз, которым считает каждый пункт: значимый параметр прогона.
STEP_PHASE_MODE: dict[str, str] = {
    "1": "fast (+ all из кэша)",
    "2": "all",
    "3": "all",
    "4": "all",
    "5": "all",
    "6": "all",
    "7": "нет (диффузия по FCC_A1)",
    "8": "all",
    "9": "fast + all",
    "fix": "all + fast",
    "excel": "нет",
}


def load_progress() -> dict[str, Any]:
    if not PROGRESS_PATH.is_file():
        return {}
    try:
        return json.loads(PROGRESS_PATH.read_text("utf-8"))
    except json.JSONDecodeError:
        log("_progress.json повреждён, начинаем отметки заново")
        return {}


def save_progress(progress: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def step_parameters(step: str, workers: int) -> dict[str, Any]:
    return {
        "pdens": PDENS,
        "режим набора фаз": STEP_PHASE_MODE.get(step, "?"),
        "воркеров": workers,
    }


# Параметры, расхождение которых заставляет пересчитать пункт. Число воркеров
# сюда не входит: на числа оно не влияет (см. модуль-док).
SIGNIFICANT_PARAMETERS = ("pdens", "режим набора фаз")


def progress_mismatch(recorded: Mapping[str, Any], current: Mapping[str, Any]) -> list[str]:
    differences: list[str] = []
    for name in SIGNIFICANT_PARAMETERS:
        was = recorded.get(name)
        now = current.get(name)
        if was != now:
            differences.append(f"{name}: было {was!r}, стало {now!r}")
    return differences


def point_key(point: dict[str, Any]) -> str:
    payload = {
        "T": round(float(point["T"]), 4),
        "X": {e: round(float(v), 9) for e, v in sorted(point["X"].items())},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def cache_file(mode: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"eq_{mode}.jsonl"


def load_cache(mode: str) -> dict[str, dict[str, Any]]:
    path = cache_file(mode)
    records: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return records
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # оборванная строка после падения — просто пересчитаем
            records[record["key"]] = record
    return records


def solve_points(
    ctx: Context,
    mode: str,
    points: Sequence[dict[str, Any]],
    label: str,
    cached_only: bool = False,
) -> list[dict[str, Any]]:
    """Посчитать точки с кэшем и вернуть записи в исходном порядке.

    ``points`` — словари ``{"T": кельвины, "X": {элемент: мольная доля}}``
    без элемента-основы в ``X``. Результат каждой точки уходит в кэш сразу,
    между кусками вызывается ``gc.collect()``. При ``cached_only=True`` ничего
    не считается: возвращаются только уже посчитанные точки (для таблиц,
    которые не должны стоить новых расчётов).
    """
    cached = load_cache(mode)
    keys = [point_key(p) for p in points]
    if cached_only:
        found = [cached[key] for key in keys if key in cached]
        log(f"{label}: из кэша {len(found)} из {len(points)} (без досчёта)")
        return found

    missing = [(p, key) for p, key in zip(points, keys) if key not in cached]
    reused_other_pdens = [
        key for key in keys
        if key in cached and record_pdens(cached[key]) != PDENS
    ]
    log(f"{label}: точек {len(points)}, из кэша {len(points) - len(missing)}, "
        f"считать {len(missing)}")
    if reused_other_pdens:
        # Ключ кэша намеренно не содержит ``pdens`` (см. ``_record_of``), но
        # молча смешивать плотности нельзя: строка в логе и строка в
        # ``p0_point_pdens.csv`` делают такие точки видимыми.
        log(f"{label}: {len(reused_other_pdens)} точек взяты из кэша с другой "
            f"плотностью выборки (не {PDENS}); список — p0_point_pdens.csv")

    if missing:
        phases = ctx.phases(mode)
        handle = cache_file(mode).open("a", encoding="utf-8")
        try:
            done = 0
            started = time.perf_counter()
            for begin in range(0, len(missing), CHUNK_POINTS):
                block = missing[begin:begin + CHUNK_POINTS]
                results, block_pdens = _map_block(
                    ctx, [item[0] for item in block], phases
                )
                for (point, key), result in zip(block, results):
                    if result.ok and result.phase_fractions:
                        used_pdens = block_pdens
                    else:
                        result, used_pdens = _retry_if_empty(
                            ctx, phases, point, result
                        )
                    record = _record_of(point, key, result, used_pdens)
                    cached[key] = record
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    handle.flush()
                os.fsync(handle.fileno())
                del results
                gc.collect()
                done += len(block)
                elapsed = time.perf_counter() - started
                rate = elapsed / max(done, 1)
                left = rate * (len(missing) - done)
                log(f"{label}: {done}/{len(missing)}, {rate:.1f} с/точку, "
                    f"осталось ~{left / 60.0:.1f} мин")
        finally:
            handle.close()

    return [cached[key] for key in keys]


def _retry_if_empty(
    ctx: Context,
    phases: list[str],
    point: dict[str, Any],
    result: Any,
) -> tuple[Any, int]:
    """Пустое решение — не ошибка pycalphad, но и не результат.

    ``equilibrium`` может вернуть NaN во всех вершинах: исключения нет,
    ``ok=True``, а фаз ноль. Такая точка сразу пересчитывается с другой
    плотностью стартовой выборки, чтобы дыра не попала в кэш.

    Возвращает пару «результат, плотность выборки, которой он получен»: вторая
    величина попадает в запись кэша, поэтому точки, посчитанные не штатной
    плотностью, видны в ``p0_point_pdens.csv``, а не растворяются среди
    остальных.
    """
    from thermogar_parallel import solve_points_in_process

    if not result.ok or result.phase_fractions:
        return result, PDENS
    for pdens in RETRY_PDENS:
        if pdens == PDENS:
            continue
        retried = solve_points_in_process(
            ctx.db, [point], list(COMPONENTS), phases, pdens=pdens
        )[0]
        if retried.ok and retried.phase_fractions:
            log(f"пустое решение при {_point_label(point)}: помогло pdens={pdens}")
            return retried, pdens
    log(f"пустое решение при {_point_label(point)}: "
        f"не помогло ни одно pdens из {RETRY_PDENS}")
    return result, PDENS


def _point_label(point: Mapping[str, Any]) -> str:
    """Короткая подпись точки: температура и ключевые мольные доли."""
    x = point.get("X", {})
    return (
        f"{float(point['T']) - 273.15:.0f} °C, "
        f"x(CR)={float(x.get('CR', 0.0)):.4f}, x(MO)={float(x.get('MO', 0.0)):.4f}"
    )


def _map_block(
    ctx: Context,
    points: Sequence[dict[str, Any]],
    phases: list[str],
) -> tuple[list[Any], int]:
    """Блок точек; при потере воркера или нехватке памяти — щадящий досчёт.

    Возвращает пару «результаты, плотность выборки, которой они получены»:
    ветка ``MemoryError`` считает блок более редкой сеткой, и это значение
    должно дойти до записи кэша, иначе огрублённые точки будут неотличимы от
    остальных.
    """
    from thermogar_parallel import WorkerLostError, solve_points_in_process

    def sequential(pdens: int) -> list[Any]:
        return solve_points_in_process(
            ctx.db, points, list(COMPONENTS), phases, pdens=pdens
        )

    try:
        if ctx.workers <= 1:
            return sequential(PDENS), PDENS
        return ctx.get_engine().map_points(
            points, list(COMPONENTS), phases, pdens=PDENS
        ), PDENS
    except WorkerLostError as error:
        log(f"пул потерял воркер ({error}); блок досчитывается последовательно")
        ctx.workers = 1
        ctx.close()
        gc.collect()
        return sequential(PDENS), PDENS
    except MemoryError:
        # Пункт не снимается: та же точка решается с более редкой стартовой
        # выборкой и по одной, чтобы пик памяти был минимальным.
        reduced = max(20, PDENS // 2)
        log(f"MemoryError на куске из {len(points)} точек; "
            f"повтор по одной точке с pdens={reduced}; "
            "эти точки будут помечены в p0_point_pdens.csv")
        ctx.close()
        gc.collect()
        results: list[Any] = []
        for index, point in enumerate(points):
            results.extend(
                solve_points_in_process(
                    ctx.db, [point], list(COMPONENTS), phases,
                    pdens=reduced, indices=[index],
                )
            )
            gc.collect()
        return results, reduced


def _record_of(
    point: dict[str, Any],
    key: str,
    result: Any,
    pdens: int | None = None,
) -> dict[str, Any]:
    fractions = {
        str(name): float(value)
        for name, value in result.phase_fractions.items()
        if float(value) > PRESENT_FLOOR
    }
    compositions = {
        str(name): {str(e): float(x) for e, x in composition.items()}
        for name, composition in result.phase_compositions.items()
        if str(name) in fractions
    }
    return {
        "key": key,
        "T_K": float(point["T"]),
        "T_C": float(point["T"]) - 273.15,
        "X": {e: float(v) for e, v in point["X"].items()},
        "ok": bool(result.ok),
        "error": result.error,
        "seconds": float(result.seconds),
        # Плотность выборки, которой решена именно эта точка. Ключ кэша её не
        # содержит намеренно: пересчёт всей сетки ради смены ``pdens`` стоил бы
        # часы, а точка от этого не становится другой физической точкой. Зато
        # запись позволяет увидеть, где числа получены не штатной плотностью:
        # такие точки перечисляет ``p0_point_pdens.csv``, о них пишет лог, и их
        # число уходит в лист «Состав и настройки» сводной книги.
        "pdens": int(PDENS if pdens is None else pdens),
        "fractions": fractions,
        "compositions": compositions,
    }


def record_pdens(record: Mapping[str, Any]) -> int:
    """Плотность выборки записи; у старых записей поля нет.

    Кэш до появления поля писался только штатной плотностью: точки, которым
    потребовалась другая, проходили через ``step_fix``, а тот своё значение
    записывал. Поэтому отсутствие поля означает ``PDENS``.
    """
    return int(record.get("pdens", PDENS))


def off_nominal_points(mode: str) -> list[dict[str, Any]]:
    """Точки кэша, решённые не штатной плотностью выборки."""
    return [
        {
            "Набор фаз": mode,
            "T, °C": round(float(record["T_C"]), 2),
            "x(CR)": float(record["X"].get("CR", 0.0)),
            "x(MO)": float(record["X"].get("MO", 0.0)),
            "pdens точки": record_pdens(record),
            "pdens прогона": PDENS,
            "Фазы": " + ".join(sorted(record.get("fractions", {}))) or "нет решения",
        }
        for record in load_cache(mode).values()
        if record_pdens(record) != PDENS
    ]


def temperature_points(
    ctx: Context,
    temperatures_c: Iterable[float],
    wt_percent: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    mole = wt_to_mole(ctx, wt_percent or full_wt())
    x = independent_x(mole)
    return [{"T": float(t) + 273.15, "X": dict(x)} for t in temperatures_c]


# --------------------------------------------------------------------------- #
# Общие таблицы
# --------------------------------------------------------------------------- #


def scan_tables(ctx: Context, records: Sequence[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Длинная таблица «T — фаза — доли», широкая сводка и составы фаз."""
    long_rows: list[dict[str, Any]] = []
    comp_rows: list[dict[str, Any]] = []
    for record in records:
        if not record["ok"]:
            long_rows.append({
                "T, °C": round(record["T_C"], 2),
                "Фаза": "ОШИБКА",
                "Мольная доля": math.nan,
                "Массовая доля": math.nan,
                "Ошибка": record["error"],
            })
            continue
        mass = mass_fractions_of_phases(ctx, record["fractions"], record["compositions"])
        for phase, amount in sorted(record["fractions"].items(), key=lambda kv: -kv[1]):
            long_rows.append({
                "T, °C": round(record["T_C"], 2),
                "Фаза": phase,
                "Мольная доля": amount,
                "Массовая доля": mass.get(phase, math.nan),
                "Ошибка": "",
            })
            composition = record["compositions"].get(phase, {})
            wt_composition = mole_to_wt(ctx, composition)
            row: dict[str, Any] = {
                "T, °C": round(record["T_C"], 2),
                "Фаза": phase,
                "Мольная доля": amount,
                "Массовая доля": mass.get(phase, math.nan),
            }
            for element in ELEMENTS:
                row[f"x({element})"] = composition.get(element, 0.0)
            for element in ELEMENTS:
                row[f"мас.% {element}"] = wt_composition.get(element, 0.0)
            comp_rows.append(row)

    long_table = pd.DataFrame(long_rows)
    comp_table = pd.DataFrame(comp_rows)
    wide = pd.DataFrame(
        [
            {"T, °C": round(record["T_C"], 2), **record["fractions"]}
            for record in records
            if record["ok"]
        ]
    )
    if not wide.empty:
        wide = wide.fillna(0.0).sort_values("T, °C").reset_index(drop=True)
        ordered = ["T, °C"] + sorted(
            [c for c in wide.columns if c != "T, °C"],
            key=lambda name: -float(wide[name].max()),
        )
        wide = wide[ordered]
    return long_table, wide, comp_table


def solvus_table(records: Sequence[dict[str, Any]], phases: Iterable[str]) -> pd.DataFrame:
    """Верхняя граница устойчивости каждой фазы (линейная интерполяция по сетке)."""
    ordered = sorted((r for r in records if r["ok"]), key=lambda r: r["T_C"])
    temperatures = [r["T_C"] for r in ordered]
    rows: list[dict[str, Any]] = []
    for phase in sorted(set(phases)):
        amounts = [r["fractions"].get(phase, 0.0) for r in ordered]
        indices = [i for i, a in enumerate(amounts) if a > PRESENT_FLOOR]
        if not indices:
            rows.append({
                "Фаза": phase,
                "Есть в расчёте": "нет",
                "Нижняя граница, °C": math.nan,
                "Сольвус (верх), °C": math.nan,
                "Верх на краю сетки": "",
                "Макс. мольная доля": 0.0,
                "T макс. доли, °C": math.nan,
            })
            continue
        top_index = indices[-1]
        bottom_index = indices[0]
        # Сольвус — линейная интерполяция доли между последней точкой «фаза есть»
        # и следующей точкой «фазы нет».
        solvus = temperatures[top_index]
        on_edge = top_index == len(temperatures) - 1
        if not on_edge:
            t1, a1 = temperatures[top_index], amounts[top_index]
            t2, a2 = temperatures[top_index + 1], amounts[top_index + 1]
            if a1 > a2:
                solvus = t1 + (a1 - PRESENT_FLOOR) * (t2 - t1) / (a1 - a2)
        best = max(zip(amounts, temperatures))
        rows.append({
            "Фаза": phase,
            "Есть в расчёте": "да",
            "Нижняя граница, °C": temperatures[bottom_index],
            "Сольвус (верх), °C": round(solvus, 1),
            "Верх на краю сетки": "да" if on_edge else "",
            "Макс. мольная доля": best[0],
            "T макс. доли, °C": best[1],
        })
    return pd.DataFrame(rows)


def plot_scan(wide: pd.DataFrame, title: str, path: Path) -> None:
    if wide.empty:
        return
    phases = [c for c in wide.columns if c != "T, °C"]
    figure, axes = plt.subplots(2, 1, figsize=(11, 9), sharex=True)
    for phase in phases:
        axes[0].plot(wide["T, °C"], wide[phase], label=phase, linewidth=1.6)
    axes[0].set_ylabel("мольная доля фазы")
    axes[0].set_title(title)
    axes[0].set_ylim(-0.02, 1.02)
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=7, ncol=3)

    for phase in phases:
        values = wide[phase].to_numpy(dtype=float)
        if values.max() < 0.9:
            axes[1].semilogy(wide["T, °C"], np.clip(values, 1e-8, None),
                             label=phase, linewidth=1.4)
    axes[1].set_ylabel("мольная доля (лог.)")
    axes[1].set_xlabel("температура, °C")
    axes[1].set_ylim(1e-7, 1.0)
    axes[1].grid(alpha=0.3, which="both")
    axes[1].legend(fontsize=7, ncol=3)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


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


# --------------------------------------------------------------------------- #
# Пункт 1 — скан по температуре
# --------------------------------------------------------------------------- #


SCAN_TEMPERATURES = [400.0 + 10.0 * i for i in range(106)]  # 400…1450 °C


def step_scan(ctx: Context, mode: str, cached_only: bool = False) -> pd.DataFrame:
    points = temperature_points(ctx, SCAN_TEMPERATURES)
    records = solve_points(ctx, mode, points, f"п.1 скан T ({mode})",
                           cached_only=cached_only)
    if not records:
        log(f"п.1 ({mode}): в кэше нет точек, таблицы не строятся")
        return pd.DataFrame()
    long_table, wide, comp_table = scan_tables(ctx, records)
    suffix = "_all" if mode == MODE_ALL else ""
    write_csv(long_table, f"p1_scan_long{suffix}.csv")
    write_csv(wide, f"p1_scan_wide{suffix}.csv")
    write_csv(comp_table, f"p1_scan_phase_compositions{suffix}.csv")

    watched = sorted(set(WATCHED_PHASES) | {
        phase for record in records if record["ok"] for phase in record["fractions"]
    })
    solvus = solvus_table(records, watched)
    write_csv(solvus, f"p1_solvus{suffix}.csv")
    plot_scan(wide, f"ХН62М: фазовый состав, набор фаз «{mode}»",
              OUT / f"p1_scan{suffix}.png")
    failed = [r for r in records if not r["ok"]]
    if failed:
        log(f"п.1 ({mode}): не сошлись {len(failed)} точек")
    return wide


def step1(ctx: Context) -> None:
    """Главный скан — «быстрый набор фаз» (правка мастера: экономия памяти).

    Точки в режиме «все фазы базы», уже лежащие в кэше от первого прогона,
    выводятся отдельным комплектом таблиц ``*_all`` — новых расчётов это не
    стоит, а сверять пресет с полным набором становится проще.
    """
    step_scan(ctx, MODE_FAST)
    step_scan(ctx, MODE_ALL, cached_only=True)


# --------------------------------------------------------------------------- #
# Пункт 2 — точечные равновесия
# --------------------------------------------------------------------------- #


POINT_TEMPERATURES = [600.0, 700.0, 800.0, 900.0, 1000.0, 1100.0, 1150.0, 1200.0]


def step2(ctx: Context) -> None:
    points = temperature_points(ctx, POINT_TEMPERATURES)
    records = solve_points(ctx, MODE_ALL, points, "п.2 точечные равновесия")
    _long, _wide, comp_table = scan_tables(ctx, records)
    write_csv(comp_table, "p2_point_equilibria.csv")

    # Куда уходят Cr и Mo: доля элемента, сидящая в каждой фазе.
    rows: list[dict[str, Any]] = []
    for record in records:
        if not record["ok"]:
            continue
        totals = {e: 0.0 for e in ELEMENTS}
        for phase, amount in record["fractions"].items():
            for element, x in record["compositions"].get(phase, {}).items():
                totals[element] = totals.get(element, 0.0) + amount * x
        for phase, amount in sorted(record["fractions"].items(), key=lambda kv: -kv[1]):
            row = {
                "T, °C": round(record["T_C"], 1),
                "Фаза": phase,
                "Мольная доля фазы": amount,
            }
            for element in ("CR", "MO", "NI", "NB", "TI", "C", "S", "FE", "SI", "MN", "AL"):
                share = 0.0
                if totals.get(element, 0.0) > 0.0:
                    share = amount * record["compositions"].get(phase, {}).get(element, 0.0)
                    share /= totals[element]
                row[f"доля общего {element}, %"] = 100.0 * share
            rows.append(row)
    write_csv(pd.DataFrame(rows), "p2_element_partition.csv")


# --------------------------------------------------------------------------- #
# Пункт 3 — затвердевание
# --------------------------------------------------------------------------- #


SOLIDIFICATION_TEMPERATURES = [1200.0 + 5.0 * i for i in range(51)]  # 1200…1450 °C
SCHEIL_START_K = 1750.0
SCHEIL_STEP_K = 5.0


def _crossing(temperatures: Sequence[float], values: Sequence[float], level: float) -> float:
    """Температура, где кривая пересекает уровень, идя сверху вниз.

    Вход сортируется здесь же, а не берётся на веру: при выпавшей точке или
    ином порядке записей линейная интерполяция по соседним парам дала бы число
    из неверной пары. Если пересечений больше одного (кривая немонотонна),
    возвращается ``NaN`` — молча брать первое нельзя.
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
            f"({', '.join(f'{value:.1f} °C' for value in crossings)}): "
            "кривая немонотонна, значение не определено")
        return math.nan
    return crossings[0]


def step3(ctx: Context) -> None:
    points = temperature_points(ctx, SOLIDIFICATION_TEMPERATURES)
    records = solve_points(ctx, MODE_ALL, points, "п.3 равновесное затвердевание")
    ordered = sorted((r for r in records if r["ok"]), key=lambda r: -r["T_C"])
    temperatures = [r["T_C"] for r in ordered]
    liquid = [r["fractions"].get("LIQUID", 0.0) for r in ordered]

    rows = []
    for record, amount in zip(ordered, liquid):
        row = {"T, °C": round(record["T_C"], 1), "Доля LIQUID": amount}
        row.update({
            f"доля {p}": v
            for p, v in sorted(record["fractions"].items())
            if p != "LIQUID"
        })
        liquid_composition = record["compositions"].get("LIQUID", {})
        for element in ("CR", "MO", "NB", "TI", "C", "SI"):
            row[f"x(LIQUID,{element})"] = liquid_composition.get(element, math.nan)
        rows.append(row)
    equilibrium_table = pd.DataFrame(rows).fillna(0.0)
    write_csv(equilibrium_table, "p3_equilibrium_solidification.csv")

    liquidus = _crossing(temperatures, liquid, 0.999)
    solidus = _crossing(temperatures, liquid, 1e-4)
    summary = {
        "равновесный ликвидус, °C": round(liquidus, 1) if liquidus == liquidus else None,
        "равновесный солидус, °C": round(solidus, 1) if solidus == solidus else None,
        "интервал кристаллизации, K": (
            round(liquidus - solidus, 1) if liquidus == liquidus and solidus == solidus else None
        ),
    }

    # --- Шейль -------------------------------------------------------------
    import scheil
    from pycalphad import variables as v

    mole = wt_to_mole(ctx, full_wt())
    composition = {v.X(e): value for e, value in independent_x(mole).items()}
    raw_path = CACHE / "p3_scheil_raw.json"
    if raw_path.is_file():
        # Шейль — самый долгий одиночный расчёт исследования; готовый результат
        # переиспользуется, чтобы повторный запуск п.3 не считал его заново.
        payload = json.loads(raw_path.read_text("utf-8"))
        result = scheil.SolidificationResult.from_dict(payload["result"])
        scheil_seconds = float(payload.get("seconds", 0.0))
        log(f"п.3 Шейль: результат взят из кэша ({len(result.temperatures)} шагов)")
    else:
        log(f"п.3 Шейль: старт {SCHEIL_START_K} K, шаг {SCHEIL_STEP_K} K")
        started = time.perf_counter()
        result = scheil.simulate_scheil_solidification(
            ctx.db,
            list(COMPONENTS),
            ctx.phases_all,
            composition,
            SCHEIL_START_K,
            step_temperature=SCHEIL_STEP_K,
            liquid_phase_name="LIQUID",
            eq_kwargs={"calc_opts": {"pdens": PDENS}},
            stop=1.0e-3,
            verbose=False,
        )
        scheil_seconds = time.perf_counter() - started
        CACHE.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            json.dumps({"seconds": scheil_seconds, "result": result.to_dict()},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        log(f"п.3 Шейль: {len(result.temperatures)} шагов за {scheil_seconds / 60.0:.1f} мин")

    scheil_rows: list[dict[str, Any]] = []
    liquid_name = result.liquid_phase_name
    for index, temperature in enumerate(result.temperatures):
        row: dict[str, Any] = {
            "T, °C": round(float(temperature) - 273.15, 2),
            "Доля твёрдого": float(result.fraction_solid[index]),
            "Доля жидкого": float(result.fraction_liquid[index]),
        }
        for element, values in result.x_liquid.items():
            row[f"x(LIQUID,{element})"] = float(values[index])
        for phase, values in sorted(result.cum_phase_amounts.items()):
            row[f"накоплено {phase}"] = float(values[index])
        for phase, values in sorted(result.phase_amounts.items()):
            row[f"прирост {phase}"] = float(values[index])
        for phase, columns in sorted(result.phase_compositions.items()):
            if phase == liquid_name:
                continue
            for element in ("CR", "MO", "NI"):
                if element in columns:
                    row[f"x({phase},{element})"] = float(columns[element][index])
        scheil_rows.append(row)
    scheil_table = pd.DataFrame(scheil_rows)
    write_csv(scheil_table, "p3_scheil.csv")

    terminal = sorted(
        (phase, float(values[-1]))
        for phase, values in result.cum_phase_amounts.items()
        if float(values[-1]) > 1e-6
    )
    summary.update({
        "Шейль: шаг, K": SCHEIL_STEP_K,
        "Шейль: точек": len(result.temperatures),
        "Шейль: T начала, °C": round(float(max(result.temperatures)) - 273.15, 1),
        "Шейль: T конца, °C": round(float(min(result.temperatures)) - 273.15, 1),
        "Шейль: макс. доля твёрдого": round(float(max(result.fraction_solid)), 5),
        "Шейль: секунды": round(scheil_seconds, 1),
        "Шейль: фазы затвердевания": {p: round(a, 6) for p, a in terminal},
        "Шейль: сошёлся": bool(result.converged),
    })

    # обогащение последней жидкости
    for element in ("MO", "CR", "NB", "TI", "C", "SI"):
        values = result.x_liquid.get(element)
        if not values:
            continue
        finite = [float(value) for value in values if math.isfinite(float(value))]
        if not finite:
            continue
        summary[f"Шейль: x(LIQUID,{element}) старт→конец"] = [
            round(finite[0], 6), round(finite[-1], 6)
        ]
        summary[f"Шейль: обогащение жидкости по {element}, ×"] = (
            round(finite[-1] / finite[0], 2) if finite[0] > 0.0 else None
        )

    # сегрегация в твёрдом: для FCC_A1 состав первого и последнего твёрдого
    solid_profile: dict[str, Any] = {}
    fcc = result.phase_compositions.get("FCC_A1")
    if fcc is not None:
        amounts = result.phase_amounts.get("FCC_A1", [])
        formed = [i for i, a in enumerate(amounts) if float(a) > 1e-9]
        if formed:
            first, last = formed[0], formed[-1]
            for element in ("MO", "CR", "NI"):
                if element in fcc:
                    solid_profile[element] = {
                        "первый твёрдый, x": float(fcc[element][first]),
                        "последний твёрдый, x": float(fcc[element][last]),
                    }
    summary["Шейль: сегрегация в FCC_A1"] = solid_profile
    write_json(summary, "p3_solidification_summary.json")

    figure, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].plot(equilibrium_table["T, °C"], equilibrium_table["Доля LIQUID"],
                 label="равновесие", linewidth=1.8)
    axes[0].plot(scheil_table["T, °C"], scheil_table["Доля жидкого"],
                 label="Шейль", linewidth=1.8)
    axes[0].set_xlabel("температура, °C")
    axes[0].set_ylabel("доля жидкого")
    axes[0].grid(alpha=0.3)
    axes[0].legend()
    axes[0].set_title("Затвердевание ХН62М")
    for element in ("MO", "CR", "NB", "TI"):
        column = f"x(LIQUID,{element})"
        if column in scheil_table:
            axes[1].plot(scheil_table["Доля твёрдого"], scheil_table[column],
                         label=element, linewidth=1.6)
    axes[1].set_xlabel("доля твёрдого")
    axes[1].set_ylabel("мольная доля в жидкости")
    axes[1].set_yscale("log")
    axes[1].grid(alpha=0.3, which="both")
    axes[1].legend()
    axes[1].set_title("Обогащение последней жидкости (Шейль)")
    figure.tight_layout()
    figure.savefig(OUT / "p3_solidification.png", dpi=150)
    plt.close(figure)


# --------------------------------------------------------------------------- #
# Пункт 4 — изоплеты
# --------------------------------------------------------------------------- #


ISOPLETH_T = [500.0 + 25.0 * i for i in range(41)]  # 500…1500 °C
ISOPLETH_CR = [20.0 + 0.5 * i for i in range(13)]   # 20…26 масс.%
ISOPLETH_MO = [10.0 + 0.5 * i for i in range(13)]   # 10…16 масс.%


def _isopleth(ctx: Context, element: str, values: Sequence[float]) -> pd.DataFrame:
    points: list[dict[str, Any]] = []
    meta: list[tuple[float, float]] = []
    for value in values:
        mole = wt_to_mole(ctx, full_wt({element: value}))
        x = independent_x(mole)
        for temperature in ISOPLETH_T:
            points.append({"T": temperature + 273.15, "X": dict(x)})
            meta.append((value, temperature))
    records = solve_points(ctx, MODE_ALL, points, f"п.4 изоплета {element}")

    rows: list[dict[str, Any]] = []
    for (value, temperature), record in zip(meta, records):
        fractions = record["fractions"] if record["ok"] else {}
        # Пустой набор фаз при ``ok=True`` — это отказ решателя, а не отсутствие
        # TCP. Нулём такую точку показывать нельзя: на карте она читалась бы как
        # однофазная область. Ставим NaN и снимаем признак «сошлось».
        solved = bool(record["ok"] and fractions)
        tcp = (sum(fractions.get(p, 0.0) for p in TCP_PHASES) if solved else math.nan)
        carbide = (
            sum(fractions.get(p, 0.0) for p in CARBIDE_PHASES) if solved else math.nan
        )
        row = {
            f"{element}, масс.%": value,
            "T, °C": temperature,
            "Сошлось": solved,
            "Σ TCP, мольная доля": tcp,
            "Σ карбиды, мольная доля": carbide,
            "Фазы": (
                " + ".join(sorted(fractions, key=lambda p: -fractions[p]))
                if solved else "нет решения"
            ),
        }
        for phase in TCP_PHASES + ("NI2CR", "LIQUID", "FCC_A1", "M6C", "M23C6"):
            row[phase] = fractions.get(phase, 0.0) if solved else math.nan
        rows.append(row)
    return pd.DataFrame(rows)


def _plot_isopleth(table: pd.DataFrame, element: str, path: Path) -> None:
    axis = f"{element}, масс.%"
    pivot = table.pivot_table(index="T, °C", columns=axis, values="Σ TCP, мольная доля")
    figure, ax = plt.subplots(figsize=(9, 6))
    mesh = ax.pcolormesh(
        pivot.columns.to_numpy(dtype=float),
        pivot.index.to_numpy(dtype=float),
        pivot.to_numpy(dtype=float),
        shading="nearest",
        cmap="magma_r",
    )
    figure.colorbar(mesh, ax=ax, label="Σ мольная доля TCP")
    try:
        contour = ax.contour(
            pivot.columns.to_numpy(dtype=float),
            pivot.index.to_numpy(dtype=float),
            pivot.to_numpy(dtype=float),
            levels=[1e-4, 1e-3, 1e-2],
            colors="cyan",
            linewidths=1.2,
        )
        ax.clabel(contour, fmt="%.0e", fontsize=7)
    except Exception:  # контур может не построиться на вырожденном поле
        pass
    ax.set_xlabel(axis)
    ax.set_ylabel("температура, °C")
    ax.set_title(f"ХН62М: граница TCP по {element}")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _tcp_boundary(table: pd.DataFrame, element: str) -> pd.DataFrame:
    axis = f"{element}, масс.%"
    rows: list[dict[str, Any]] = []
    for value, block in table.groupby(axis):
        block = block.sort_values("T, °C").dropna(subset=["Σ TCP, мольная доля"])
        temperatures = block["T, °C"].tolist()
        tcp = block["Σ TCP, мольная доля"].tolist()
        present = [t for t, a in zip(temperatures, tcp) if a > PRESENT_FLOOR]
        rows.append({
            axis: value,
            "Верхняя граница TCP, °C": max(present) if present else math.nan,
            "Макс. Σ TCP": max(tcp) if tcp else math.nan,
            "T макс. Σ TCP, °C": temperatures[int(np.argmax(tcp))] if tcp else math.nan,
        })
    return pd.DataFrame(rows)


def step4(ctx: Context) -> None:
    for element, values in (("CR", ISOPLETH_CR), ("MO", ISOPLETH_MO)):
        table = _isopleth(ctx, element, values)
        unsolved = int((~table["Сошлось"]).sum())
        if unsolved:
            log(f"п.4 изоплета {element}: {unsolved} точек без решения, "
                "в таблице они помечены NaN")
        write_csv(table, f"p4_isopleth_{element.lower()}.csv")
        write_csv(_tcp_boundary(table, element), f"p4_isopleth_{element.lower()}_boundary.csv")
        _plot_isopleth(table, element, OUT / f"p4_isopleth_{element.lower()}.png")


# --------------------------------------------------------------------------- #
# Пункт 5 — движущие силы
# --------------------------------------------------------------------------- #


DRIVING_FORCE_T = (700.0, 800.0, 900.0)
DRIVING_FORCE_PHASES = ("P_PHASE", "MU_PHASE", "SIGMA", "CHI_A12", "LAVES", "M6C", "M23C6")
DRIVING_FORCE_PDENS = 50


def step5(ctx: Context) -> None:
    from pycalphad import calculate, equilibrium, variables as v

    mole = wt_to_mole(ctx, full_wt())
    base = {v.X(e): value for e, value in independent_x(mole).items()}
    rows: list[dict[str, Any]] = []
    for temperature_c in DRIVING_FORCE_T:
        temperature_k = temperature_c + 273.15
        conditions = {v.N: 1.0, v.P: 101325.0, v.T: temperature_k, **base}

        # Химические потенциалы пересыщенной матрицы: равновесие из одной FCC_A1.
        matrix = equilibrium(
            ctx.db, list(COMPONENTS), ["FCC_A1"], conditions,
            calc_opts={"pdens": PDENS},
        )
        mu = {
            element: float(np.asarray(matrix.MU.sel(component=element).values).ravel()[0])
            for element in ELEMENTS
        }
        matrix_gm = float(np.asarray(matrix.GM.values).ravel()[0])
        log(f"п.5 {temperature_c:.0f} °C: GM(FCC_A1) = {matrix_gm:.1f} Дж/моль")

        # Полное равновесие для справки: какие фазы вообще устойчивы.
        stable = equilibrium(
            ctx.db, list(COMPONENTS), ctx.phases_all, conditions,
            calc_opts={"pdens": PDENS},
        )
        names = np.asarray(stable.Phase.values, dtype=str).ravel()
        amounts = np.asarray(stable.NP.values, dtype=float).ravel()
        stable_phases = sorted({
            str(n) for n, a in zip(names, amounts)
            if n and np.isfinite(a) and float(a) > PRESENT_FLOOR
        })

        for phase in DRIVING_FORCE_PHASES:
            if phase not in ctx.phases_all:
                continue
            driving_force = math.nan
            composition_at_max: dict[str, float] = {}
            try:
                sampled = calculate(
                    ctx.db, list(COMPONENTS), phase,
                    T=temperature_k, P=101325.0, N=1.0,
                    pdens=DRIVING_FORCE_PDENS, output="GM",
                )
                gm = np.asarray(sampled.GM.values, dtype=float).ravel()
                x = np.stack([
                    np.asarray(sampled.X.sel(component=e).values, dtype=float).ravel()
                    for e in ELEMENTS
                ], axis=1)
                potential = x @ np.array([mu[e] for e in ELEMENTS], dtype=float)
                values = potential - gm
                best = int(np.nanargmax(values))
                driving_force = float(values[best])
                composition_at_max = {
                    e: float(x[best, i]) for i, e in enumerate(ELEMENTS)
                }
            except Exception as error:  # фаза может не сэмплироваться
                log(f"п.5 {phase} при {temperature_c:.0f} °C: {type(error).__name__}: {error}")

            same_composition = math.nan
            try:
                single = equilibrium(
                    ctx.db, list(COMPONENTS), [phase], conditions,
                    calc_opts={"pdens": PDENS},
                )
                same_composition = matrix_gm - float(np.asarray(single.GM.values).ravel()[0])
            except Exception:
                pass

            rows.append({
                "T, °C": temperature_c,
                "Фаза": phase,
                "Устойчива в равновесии": "да" if phase in stable_phases else "нет",
                "Движущая сила от матрицы, Дж/моль": driving_force,
                "ΔG при составе сплава, Дж/моль": same_composition,
                "GM матрицы, Дж/моль": matrix_gm,
                **{f"x* {e}": composition_at_max.get(e, math.nan)
                   for e in ("NI", "CR", "MO", "NB", "TI")},
                "Устойчивые фазы": " + ".join(stable_phases),
            })
    table = pd.DataFrame(rows)
    write_csv(table, "p5_driving_forces.csv")

    figure, ax = plt.subplots(figsize=(9, 5))
    for phase, block in table.groupby("Фаза"):
        ax.plot(block["T, °C"], block["Движущая сила от матрицы, Дж/моль"],
                marker="o", label=phase)
    ax.set_xlabel("температура, °C")
    ax.set_ylabel("движущая сила, Дж/моль-ат.")
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    ax.set_title("Движущая сила выделения из пересыщенной матрицы FCC_A1")
    figure.tight_layout()
    figure.savefig(OUT / "p5_driving_forces.png", dpi=150)
    plt.close(figure)


# --------------------------------------------------------------------------- #
# Пункт 6 — плотность
# --------------------------------------------------------------------------- #


# Нижняя точка — 25 °C, а не 20 °C: параметры плотности PDB v1.03 объявлены
# от 298,15 K, и на 293,15 K ``thermogar_physical`` отказывается считать
# («Температура 293.15 K вне диапазона DP-параметра FCC_A1»). Это ограничение
# данных, а не расчёта, и оно записано в отчёт.
DENSITY_TEMPERATURES = [25.0 * i for i in range(1, 49)]  # 25…1200 °C


def step6(ctx: Context) -> None:
    from thermogar_parallel import solve_points_in_process
    from thermogar_parallel_ui import snapshot_of
    from thermogar_physical import PhysicalDensityDatabase, calculate_physical_properties

    physical_db = PhysicalDensityDatabase(ROOT / PDB_REL)
    points = temperature_points(ctx, DENSITY_TEMPERATURES)
    path = CACHE / "p6_density.jsonl"
    CACHE.mkdir(parents=True, exist_ok=True)
    done: dict[str, dict[str, Any]] = {}
    if path.is_file():
        for line in path.read_text("utf-8").splitlines():
            if line.strip():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                done[record["key"]] = record

    keys = [point_key(p) for p in points]
    missing = [(p, k) for p, k in zip(points, keys) if k not in done]
    log(f"п.6 плотность: точек {len(points)}, считать {len(missing)}")

    if missing:
        handle = path.open("a", encoding="utf-8")
        try:
            chunk = max(1, ctx.workers * 3)
            for begin in range(0, len(missing), chunk):
                block = missing[begin:begin + chunk]
                block_points = [item[0] for item in block]
                if ctx.workers <= 1:
                    results = solve_points_in_process(
                        ctx.db, block_points, list(COMPONENTS), ctx.phases_all,
                        pdens=PDENS, capture=("X", "Y"),
                    )
                else:
                    results = ctx.get_engine().map_points(
                        block_points, list(COMPONENTS), ctx.phases_all,
                        pdens=PDENS, capture=("X", "Y"),
                    )
                for (point, key), result in zip(block, results):
                    record: dict[str, Any] = {
                        "key": key,
                        "T_C": float(point["T"]) - 273.15,
                        "ok": bool(result.ok),
                        "error": result.error,
                    }
                    if result.ok:
                        try:
                            properties = calculate_physical_properties(
                                ctx.db, snapshot_of(result), list(ELEMENTS),
                                float(point["T"]), physical_db,
                            )
                        except Exception as error:
                            # Одна температура вне диапазона PDB не должна
                            # уносить весь пункт.
                            record["ok"] = False
                            record["error"] = f"{type(error).__name__}: {error}"
                            log(f"п.6 {record['T_C']:.0f} °C: {record['error']}")
                            done[key] = record
                            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                            handle.flush()
                            continue
                        record.update({
                            "density": properties.alloy_density_kg_m3,
                            "coverage": float(properties.mass_coverage_pct),
                            "quality": properties.quality_label,
                            "phases": {
                                str(n): float(a)
                                for n, a in result.phase_fractions.items()
                                if float(a) > PRESENT_FLOOR
                            },
                        })
                        missing_table = properties.missing_table
                        missing_models: list[str] = []
                        if missing_table is not None and not missing_table.empty:
                            missing_models = [
                                str(name) for name in missing_table["Фаза"].tolist()
                            ]
                        record["без модели"] = missing_models
                        record["warnings"] = list(properties.warnings)
                        # Плотность сплава на этом сплаве не выдаётся ни при
                        # одной температуре: PDB v1.03 не знает NI2CR, P_PHASE,
                        # MNS_Q, DELTA и MU_PHASE. Чтобы пункт не остался
                        # пустым, отдельно сохраняется плотность матрицы —
                        # она покрыта прямой моделью и для практики полезна.
                        phase_table = properties.phase_table
                        if phase_table is not None and not phase_table.empty:
                            matrix = phase_table[phase_table["Фаза"] == "FCC_A1"]
                            if not matrix.empty:
                                value = matrix.iloc[0]["Плотность фазы, кг/м³"]
                                record["density_fcc"] = (
                                    None if value is None or value != value
                                    else float(value)
                                )
                                record["density_fcc_status"] = str(
                                    matrix.iloc[0]["Статус данных"]
                                )
                    done[key] = record
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                log(f"п.6 плотность: {min(begin + chunk, len(missing))}/{len(missing)}")
        finally:
            handle.close()

    rows = []
    for key in keys:
        record = done[key]
        rows.append({
            "T, °C": round(record["T_C"], 1),
            "Плотность сплава, кг/м³": record.get("density"),
            "Плотность матрицы FCC_A1, кг/м³": record.get("density_fcc"),
            "Модель плотности матрицы": record.get("density_fcc_status", ""),
            "Покрытие PDB по массе, %": record.get("coverage"),
            "Качество": record.get("quality"),
            "Фазы без модели плотности": ", ".join(record.get("без модели", [])),
            "Равновесные фазы": " + ".join(sorted(record.get("phases", {}))),
            "Ошибка": record.get("error") or "",
        })
    table = pd.DataFrame(rows).sort_values("T, °C").reset_index(drop=True)
    write_csv(table, "p6_density.csv")

    figure, ax = plt.subplots(figsize=(9, 5))
    alloy = table.dropna(subset=["Плотность сплава, кг/м³"])
    if not alloy.empty:
        ax.plot(alloy["T, °C"], alloy["Плотность сплава, кг/м³"],
                marker=".", linewidth=1.6, label="сплав")
    matrix = table.dropna(subset=["Плотность матрицы FCC_A1, кг/м³"])
    if not matrix.empty:
        ax.plot(matrix["T, °C"], matrix["Плотность матрицы FCC_A1, кг/м³"],
                marker=".", linewidth=1.6, label="матрица FCC_A1")
    ax.set_xlabel("температура, °C")
    ax.set_ylabel("плотность, кг/м³")
    ax.grid(alpha=0.3)
    ax.legend()
    ax.set_title("ХН62М: расчётная плотность (PDB v1.03)")
    figure.tight_layout()
    figure.savefig(OUT / "p6_density.png", dpi=150)
    plt.close(figure)


# --------------------------------------------------------------------------- #
# Пункт 7 — гомогенизация
# --------------------------------------------------------------------------- #


HOMOGENIZATION_T = (1150.0, 1175.0, 1200.0)
HOMOGENIZATION_CELLS_UM = (1.0, 3.0, 5.0)
HOMOGENIZATION_TARGET = 0.05
HOMOGENIZATION_NODES = 40
HOMOGENIZATION_PHASE = "FCC_A1"
HOMOGENIZATION_ELEMENTS = ("NI", "CR", "MO")

# Начальный профиль — прямоугольная ступень: ось дендрита слева, междендритная
# область справа, границы отрезка непроницаемы. Такой отрезок длиной L
# эквивалентен периодической сегрегации с длиной волны 2L, поэтому «масштаб
# ячейки» в таблицах — это L, а не период.
#
# Первая мода прямоугольной волны имеет амплитуду 4/π от амплитуды ступени,
# поэтому размах падает как (4/π)·exp(−π²·D·t/L²), и аналитическая оценка
# времени до остатка 5 % — t = (L²/π²D)·ln((4/π)/0,05).
SQUARE_WAVE_FIRST_MODE = 4.0 / math.pi


def _segregation_from_scheil() -> dict[str, float]:
    """Границы сегрегации Mo и Cr из результата пункта 3."""
    path = OUT / "p3_scheil.csv"
    if not path.is_file():
        raise RuntimeError("Нет p3_scheil.csv: сначала выполните --only 3.")
    table = pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig")
    result: dict[str, float] = {}
    for element in ("MO", "CR"):
        column = f"x(FCC_A1,{element})"
        if column not in table.columns:
            raise RuntimeError(f"В p3_scheil.csv нет столбца {column}.")
        values = pd.to_numeric(table[column], errors="coerce").dropna()
        values = values[values > 0.0]
        if values.empty:
            raise RuntimeError(f"В p3_scheil.csv нет положительных значений {column}.")
        # Именно экстремумы, а не первая и последняя строка: у fs→1 идут
        # терминальные реакции (в этом сплаве SIGMA и M6C), и состав FCC_A1
        # на последних шагах может пойти обратно. Размах сегрегации задают
        # минимум и максимум.
        result[f"{element}_min_x"] = float(values.min())
        result[f"{element}_max_x"] = float(values.max())
        result[f"{element}_first_x"] = float(values.iloc[0])
        result[f"{element}_last_x"] = float(values.iloc[-1])
    return result


def _tracer_diffusivities(
    thermodynamics: Any,
    x_cr: float,
    x_mo: float,
    temperature_k: float,
) -> dict[str, float]:
    """«Сырые» коэффициенты kawin для NI, CR, MO при заданном составе.

    Порядок массива — порядок ``HOMOGENIZATION_ELEMENTS``; проверено на пределе
    чистого никеля сверкой с параметрами MQ самой базы.
    """
    values = np.asarray(
        thermodynamics.getTracerDiffusivity([x_cr, x_mo], temperature_k,
                                            phase=HOMOGENIZATION_PHASE),
        dtype=float,
    ).ravel()
    return {element: float(value)
            for element, value in zip(HOMOGENIZATION_ELEMENTS, values)}


def _diffusivity_report(ctx: Context) -> pd.DataFrame:
    """Сверка коэффициентов диффузии базы с тем, что отдаёт kawin.

    В ``mc_ni_v2036_with_mobility.garcalc.tdb`` параметр подвижности задан
    дважды — общей строкой ``MQ(<фаза>&<элемент>,*)`` и явной
    ``MQ(<фаза>&<элемент>,NI:*)`` с тем же выражением. pycalphad складывает обе,
    поэтому вместо ``exp(MQ/RT)`` получается ``exp(2·MQ/RT)``, то есть квадрат
    коэффициента диффузии. Таблица показывает это на пределе чистого никеля,
    где значение считается из строк базы вручную.
    """
    from kawin.thermo import GeneralThermodynamics

    gas_constant = 8.31446261815324
    # Выражения MQ(FCC_A1&X,NI:*) из базы, Дж/моль.
    mq_expressions = {
        "NI": lambda t: -287000.0 - 69.8 * t,
        "CR": lambda t: -287000.0 - 64.4 * t,
        "MO": lambda t: -267585.0 - 79.5 * t,
    }
    thermodynamics = GeneralThermodynamics(
        ctx.db, list(HOMOGENIZATION_ELEMENTS), [HOMOGENIZATION_PHASE]
    )
    rows: list[dict[str, Any]] = []
    for temperature_c in HOMOGENIZATION_T:
        temperature_k = temperature_c + 273.15
        dilute = _tracer_diffusivities(thermodynamics, 1.0e-6, 1.0e-6, temperature_k)
        for element, expression in mq_expressions.items():
            from_database = math.exp(
                expression(temperature_k) / (gas_constant * temperature_k)
            )
            rows.append({
                "T, °C": temperature_c,
                "Элемент": element,
                "D по строке MQ базы (разб. предел), м²/с": from_database,
                "D от kawin (разб. предел), м²/с": dilute[element],
                "Отношение kawin / база": dilute[element] / from_database,
                "√(kawin) / база": math.sqrt(dilute[element]) / from_database,
            })
    return pd.DataFrame(rows)


def _corrected_thermodynamics(
    ctx: Context,
    x_cr: float,
    x_mo: float,
    temperature_k: float,
) -> tuple[Any, dict[str, float], dict[str, float]]:
    """kawin с подвижностями, поправленными на удвоение параметра MQ.

    ``setMobilityCorrection`` умножает подвижность на **постоянный** множитель,
    а исправить нужно величину, которая сама зависит от состава: kawin считает
    ``M = D(x)²/RT``, нужно ``M = D(x)/RT``, то есть множитель ``1/D(x)``.
    С постоянным множителем ``1/D(x̄)`` по профилю остаётся
    ``M = D(x)·D(x)/D(x̄)/RT`` — точно в середине профиля и с погрешностью
    ``D(x)/D(x̄)`` на его концах.

    Поэтому множитель берётся при среднем составе, а разброс ``D`` между
    концами профиля меряется отдельно (``_diffusivity_spread``) и уходит в
    таблицу пункта как вилка: она честно показывает, в каких пределах лежит
    ответ, вместо одного числа с необъявленной погрешностью.
    """
    from kawin.thermo import GeneralThermodynamics

    thermodynamics = GeneralThermodynamics(
        ctx.db, list(HOMOGENIZATION_ELEMENTS), [HOMOGENIZATION_PHASE]
    )
    raw = _tracer_diffusivities(thermodynamics, x_cr, x_mo, temperature_k)
    for element, value in raw.items():
        thermodynamics.setMobilityCorrection(element, 1.0 / math.sqrt(value))
    corrected = _tracer_diffusivities(thermodynamics, x_cr, x_mo, temperature_k)
    return thermodynamics, {e: math.sqrt(v) for e, v in raw.items()}, corrected


def _diffusivity_spread(
    ctx: Context,
    ends: Sequence[tuple[float, float]],
    temperature_k: float,
) -> dict[str, float]:
    """D(Mo) базы на концах профиля — вилка для времени гомогенизации."""
    from kawin.thermo import GeneralThermodynamics

    thermodynamics = GeneralThermodynamics(
        ctx.db, list(HOMOGENIZATION_ELEMENTS), [HOMOGENIZATION_PHASE]
    )
    values = [
        math.sqrt(_tracer_diffusivities(thermodynamics, x_cr, x_mo, temperature_k)["MO"])
        for x_cr, x_mo in ends
    ]
    return {"D_min": min(values), "D_max": max(values)}


def _solve_couple(
    ctx: Context,
    thermodynamics: Any,
    left_x: Sequence[float],
    right_x: Sequence[float],
    temperature_k: float,
    length_um: float,
    time_s: float,
) -> float:
    """Прогон пары напрямую через kawin; возвращает остаточный размах по Mo."""
    from kawin.diffusion import SinglePhaseModel
    from kawin.diffusion.mesh import Cartesian1D, ProfileBuilder, StepProfile1D
    from kawin.solver import explicitEulerIterator

    length_m = float(length_um) * 1.0e-6
    independent = list(HOMOGENIZATION_ELEMENTS[1:])
    mesh = Cartesian1D(independent, [0.0, length_m], HOMOGENIZATION_NODES)
    builder = ProfileBuilder()
    builder.addBuildStep(
        StepProfile1D(length_m / 2.0, list(left_x), list(right_x)), independent
    )
    mesh.setResponseProfile(builder)
    model = SinglePhaseModel(
        mesh,
        list(HOMOGENIZATION_ELEMENTS),
        [HOMOGENIZATION_PHASE],
        thermodynamics=thermodynamics,
        temperature=temperature_k,
        record=False,
    )
    initial = np.asarray(model.getCompositions(), dtype=float).copy()
    model.solve(float(time_s), iterator=explicitEulerIterator, verbose=False,
                vIt=100000, minDtFrac=1e-10)
    final = np.asarray(model.getCompositions(), dtype=float)
    index = list(HOMOGENIZATION_ELEMENTS).index("MO")
    span_0 = float(initial[:, index].max() - initial[:, index].min())
    span_t = float(final[:, index].max() - final[:, index].min())
    del model, mesh
    gc.collect()
    return span_t / span_0 if span_0 > 0.0 else math.nan


def _module_evidence(
    ctx: Context,
    left_text: str,
    right_text: str,
    temperature_c: float,
    length_um: float,
    time_h: float,
) -> dict[str, Any]:
    """Штатный ``thermogar_diffusion.run_diffusion`` — как он есть, без поправки."""
    from thermogar_diffusion import run_diffusion
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    started = time.perf_counter()
    result = run_diffusion(
        db=object(),
        database_key=DATABASE_KEY,
        database_path=ctx.db_path,
        database_label=RELEASE_DATABASE_LABELS.get(DATABASE_KEY, "mc_ni"),
        balance=BALANCE,
        units="wt",
        left_text=left_text,
        right_text=right_text,
        temperature_c=temperature_c,
        time_h=time_h,
        length_um=length_um,
        interface_percent=50.0,
        nodes=HOMOGENIZATION_NODES,
        phases=[HOMOGENIZATION_PHASE],
        model_kind="single",
        input_provenance=(
            "Профиль сегрегации Mo/Cr из расчёта Шейля этого же исследования "
            "(tasks/WAVE9_HN62M_OPUS.md, п.3); research-only"
        ),
        input_confirmation=True,
    )
    index = list(result.elements).index("MO")
    initial = np.asarray(result.initial_wt, dtype=float)[:, index]
    final = np.asarray(result.final_wt, dtype=float)[:, index]
    span_0 = float(initial.max() - initial.min())
    span_t = float(final.max() - final.min())
    return {
        "T, °C": temperature_c,
        "Ячейка, мкм": length_um,
        "Время выдержки, ч": time_h,
        "Время модели, с": float(result.actual_time_s),
        "Остаточная амплитуда Mo": span_t / span_0 if span_0 > 0.0 else math.nan,
        "Ошибка баланса": float(result.max_balance_error),
        "Счёт, с": round(time.perf_counter() - started, 1),
    }


def step7(ctx: Context) -> None:
    """Гомогенизация по Mo: диагностика подвижностей, расчёт и оценка.

    Пункт устроен в три слоя, потому что штатный кинетический раздел на этой
    базе выдаёт квадрат коэффициента диффузии (см. ``_diffusivity_report``):

    1. таблица сверки D — доказательство и величина расхождения;
    2. прогон штатного ``run_diffusion`` — что раздел выдаёт «как есть»;
    3. численный расчёт с поправленной подвижностью плюс аналитическая оценка
       по первой моде — рабочие числа для технолога.
    """
    segregation = _segregation_from_scheil()
    mo_min, mo_max = segregation["MO_min_x"], segregation["MO_max_x"]
    cr_min, cr_max = segregation["CR_min_x"], segregation["CR_max_x"]
    x_mean_cr = 0.5 * (cr_min + cr_max)
    x_mean_mo = 0.5 * (mo_min + mo_max)

    def side(mo_x: float, cr_x: float) -> str:
        wt = mole_to_wt(ctx, {"NI": 1.0 - mo_x - cr_x, "MO": mo_x, "CR": cr_x})
        return f"CR={wt['CR']:.4f}, MO={wt['MO']:.4f}"

    left_text = side(mo_min, cr_min)
    right_text = side(mo_max, cr_max)
    log(f"п.7 профиль: ось дендрита {left_text} | междендритная {right_text}")

    # --- слой 1: сверка коэффициентов диффузии -----------------------------
    diffusivity = _diffusivity_report(ctx)
    write_csv(diffusivity, "p7_diffusivity_check.csv")
    ratio = float(diffusivity["√(kawin) / база"].abs().sub(1.0).abs().max())
    log(f"п.7 сверка D: макс. отклонение √(kawin)/база от 1 — {ratio:.2e}")

    module_rows: list[dict[str, Any]] = []
    search_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for temperature_c in HOMOGENIZATION_T:
        temperature_k = temperature_c + 273.15
        thermodynamics, true_d, corrected_d = _corrected_thermodynamics(
            ctx, x_mean_cr, x_mean_mo, temperature_k
        )
        d_mo = true_d["MO"]
        spread = _diffusivity_spread(
            ctx, [(cr_min, mo_min), (cr_max, mo_max)], temperature_k
        )
        log(f"п.7 {temperature_c:.0f} °C: D(Mo) на концах профиля "
            f"{spread['D_min']:.3e} … {spread['D_max']:.3e} м²/с")
        log(f"п.7 {temperature_c:.0f} °C: D(Mo) базы при среднем составе "
            f"{d_mo:.3e} м²/с (kawin после поправки {corrected_d['MO']:.3e})")

        for length_um in HOMOGENIZATION_CELLS_UM:
            length_m = length_um * 1.0e-6
            tau_s = length_m ** 2 / (math.pi ** 2 * d_mo)
            analytic_s = tau_s * math.log(SQUARE_WAVE_FIRST_MODE / HOMOGENIZATION_TARGET)

            # слой 2: штатный модуль, время берём из аналитической оценки
            try:
                module_rows.append(_module_evidence(
                    ctx, left_text, right_text, temperature_c, length_um,
                    max(analytic_s / 3600.0, 1.0e-6),
                ))
                write_csv(pd.DataFrame(module_rows), "p7_module_runs.csv")
            except Exception as error:
                log(f"п.7 штатный модуль {temperature_c:.0f} °C / {length_um} мкм: "
                    f"{type(error).__name__}: {error}")

            # слой 3: численный поиск времени до остатка 5 %
            time_s = analytic_s
            answer = math.nan
            last_ratio = math.nan
            for attempt in range(6):
                started = time.perf_counter()
                residual = _solve_couple(
                    ctx, thermodynamics,
                    [cr_min, mo_min], [cr_max, mo_max],
                    temperature_k, length_um, time_s,
                )
                wall = time.perf_counter() - started
                last_ratio = residual
                search_rows.append({
                    "T, °C": temperature_c,
                    "Ячейка, мкм": length_um,
                    "Время, с": time_s,
                    "Остаточная амплитуда Mo": residual,
                    "Счёт, с": round(wall, 1),
                })
                write_csv(pd.DataFrame(search_rows), "p7_search_runs.csv")
                log(f"п.7 {temperature_c:.0f} °C, L={length_um} мкм, "
                    f"t={time_s:.4g} с: остаток {residual:.4f} ({wall:.0f} с счёта)")
                if not math.isfinite(residual) or residual <= 0.0:
                    break
                if abs(residual - HOMOGENIZATION_TARGET) <= 0.004:
                    answer = time_s
                    break
                tau_fit = -time_s / math.log(residual / SQUARE_WAVE_FIRST_MODE)
                target = tau_fit * math.log(
                    SQUARE_WAVE_FIRST_MODE / HOMOGENIZATION_TARGET
                )
                if not math.isfinite(target) or target <= 0.0:
                    break
                if attempt == 5:
                    answer = target
                    break
                time_s = target

            # Вилка по разбросу D между концами профиля: постоянный множитель
            # поправки подвижности точен только при среднем составе.
            slow_s = (length_m ** 2 / (math.pi ** 2 * spread["D_min"])) * math.log(
                SQUARE_WAVE_FIRST_MODE / HOMOGENIZATION_TARGET
            )
            fast_s = (length_m ** 2 / (math.pi ** 2 * spread["D_max"])) * math.log(
                SQUARE_WAVE_FIRST_MODE / HOMOGENIZATION_TARGET
            )
            summary_rows.append({
                "T, °C": temperature_c,
                "Ячейка (полуволна), мкм": length_um,
                "D(Mo) базы при среднем составе, м²/с": d_mo,
                "D(Mo) на концах профиля, м²/с": (
                    f"{spread['D_min']:.3e} … {spread['D_max']:.3e}"
                ),
                "τ = L²/π²D, с": tau_s,
                "Аналитически до 5 %, с": analytic_s,
                "Аналитически до 5 %, мин": analytic_s / 60.0,
                "Вилка до 5 %, мин": (
                    f"{min(slow_s, fast_s) / 60.0:.3g} … {max(slow_s, fast_s) / 60.0:.3g}"
                ),
                "Численно до 5 %, с": answer,
                "Численно до 5 %, мин": answer / 60.0 if answer == answer else math.nan,
                "Последний остаток": last_ratio,
            })
            write_csv(pd.DataFrame(summary_rows), "p7_homogenization.csv")

    table = pd.DataFrame(summary_rows)
    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    for temperature_c, block in table.groupby("T, °C"):
        axes[0].plot(block["Ячейка (полуволна), мкм"], block["Численно до 5 %, мин"],
                     marker="o", label=f"{temperature_c:.0f} °C, расчёт")
        axes[0].plot(block["Ячейка (полуволна), мкм"], block["Аналитически до 5 %, мин"],
                     marker="s", linestyle="--",
                     label=f"{temperature_c:.0f} °C, оценка")
    axes[0].set_xlabel("масштаб ячейки, мкм")
    axes[0].set_ylabel("время до остатка 5 %, мин")
    axes[0].set_yscale("log")
    axes[0].grid(alpha=0.3, which="both")
    axes[0].legend(fontsize=7)
    axes[0].set_title("Гомогенизация по Mo (FCC_A1)")

    axes[1].semilogy(table["T, °C"], table["D(Mo) базы при среднем составе, м²/с"],
                     marker="o")
    axes[1].set_xlabel("температура, °C")
    axes[1].set_ylabel("D(Mo), м²/с")
    axes[1].grid(alpha=0.3, which="both")
    axes[1].set_title("Коэффициент диффузии Mo из базы")
    figure.tight_layout()
    figure.savefig(OUT / "p7_homogenization.png", dpi=150)
    plt.close(figure)

    write_json({
        "профиль: ось дендрита, масс.%": left_text,
        "профиль: междендритная область, масс.%": right_text,
        "x(Mo) ось дендрита": mo_min,
        "x(Mo) междендритная область": mo_max,
        "x(Cr) ось дендрита": cr_min,
        "x(Cr) междендритная область": cr_max,
        "узлов": HOMOGENIZATION_NODES,
        "фаза": HOMOGENIZATION_PHASE,
        "целевая остаточная амплитуда": HOMOGENIZATION_TARGET,
        "поправка подвижности": (
            "постоянный множитель 1/D при среднем составе профиля; нужен из-за "
            "удвоенного параметра MQ в конвертированной базе "
            "(см. p7_diffusivity_check.csv). Точен в середине профиля; на его "
            "концах остаётся погрешность D(x)/D(среднее), она показана "
            "столбцом «Вилка до 5 %, мин»"
        ),
        "x(Mo) минимум и максимум по Шейлу": [mo_min, mo_max],
        "x(Mo) первый и последний шаг Шейля": [
            segregation["MO_first_x"], segregation["MO_last_x"]
        ],
        "модель начального профиля": (
            "прямоугольная ступень на отрезке L с непроницаемыми границами, "
            "что равно периодической сегрегации с длиной волны 2L"
        ),
    }, "p7_homogenization_setup.json")



# --------------------------------------------------------------------------- #
# Пункт 8 — углы марки
# --------------------------------------------------------------------------- #


CORNER_T = (700.0, 900.0, 1100.0)
CORNER_LIMITS = {
    "CR": (23.0, 24.0),
    "MO": (12.0, 14.0),
    "TI": (0.03, 0.16),
    "NB": (0.02, 0.10),
}
CORNER_FE = 0.5


def corner_definitions() -> list[dict[str, float]]:
    corners: list[dict[str, float]] = []
    for mask in range(16):
        overrides = {"FE": CORNER_FE}
        for bit, element in enumerate(("CR", "MO", "TI", "NB")):
            low, high = CORNER_LIMITS[element]
            overrides[element] = high if (mask >> bit) & 1 else low
        corners.append(overrides)
    return corners


def step_corners(ctx: Context, mode: str) -> pd.DataFrame:
    corners = corner_definitions()
    points: list[dict[str, Any]] = []
    meta: list[tuple[dict[str, float], float]] = []
    for overrides in corners:
        mole = wt_to_mole(ctx, full_wt(overrides))
        x = independent_x(mole)
        for temperature_c in CORNER_T:
            points.append({"T": temperature_c + 273.15, "X": dict(x)})
            meta.append((overrides, temperature_c))
    records = solve_points(ctx, mode, points, f"п.8 углы марки ({mode})")

    rows: list[dict[str, Any]] = []
    for (overrides, temperature_c), record in zip(meta, records):
        fractions = record["fractions"] if record["ok"] else {}
        tcp = {p: fractions.get(p, 0.0) for p in TCP_PHASES if fractions.get(p, 0.0) > PRESENT_FLOOR}
        carbides = {p: fractions.get(p, 0.0) for p in CARBIDE_PHASES
                    if fractions.get(p, 0.0) > PRESENT_FLOOR}
        row = {
            "Cr, масс.%": overrides["CR"],
            "Mo, масс.%": overrides["MO"],
            "Ti, масс.%": overrides["TI"],
            "Nb, масс.%": overrides["NB"],
            "Fe, масс.%": overrides["FE"],
            "T, °C": temperature_c,
            "Сошлось": record["ok"],
            "Есть TCP": "да" if tcp else "нет",
            "Σ TCP, мольная доля": sum(tcp.values()),
            "TCP-фазы": " + ".join(f"{p} {v:.4g}" for p, v in sorted(tcp.items())),
            "Σ карбиды, мольная доля": sum(carbides.values()),
            "Карбиды": " + ".join(f"{p} {v:.4g}" for p, v in sorted(carbides.items())),
            "Доля FCC_A1": fractions.get("FCC_A1", 0.0),
            "Все фазы": " + ".join(sorted(fractions, key=lambda p: -fractions[p])),
        }
        rows.append(row)
    table = pd.DataFrame(rows)
    suffix = "" if mode == MODE_ALL else "_fast"
    write_csv(table, f"p8_corners{suffix}.csv")
    return table


def step8(ctx: Context) -> None:
    table = step_corners(ctx, MODE_ALL)
    figure, axes = plt.subplots(1, len(CORNER_T), figsize=(5 * len(CORNER_T), 4.5),
                                sharey=True)
    for axis, temperature_c in zip(np.atleast_1d(axes), CORNER_T):
        block = table[table["T, °C"] == temperature_c]
        labels = [
            f"Cr{row['Cr, масс.%']:.0f}/Mo{row['Mo, масс.%']:.0f}/"
            f"Ti{row['Ti, масс.%']:.2f}/Nb{row['Nb, масс.%']:.2f}"
            for _index, row in block.iterrows()
        ]
        axis.barh(range(len(block)), block["Σ TCP, мольная доля"], color="#b03a2e")
        axis.set_yticks(range(len(block)))
        axis.set_yticklabels(labels, fontsize=6)
        axis.set_xlabel("Σ мольная доля TCP")
        axis.set_title(f"{temperature_c:.0f} °C")
        axis.grid(alpha=0.3, axis="x")
    figure.tight_layout()
    figure.savefig(OUT / "p8_corners.png", dpi=150)
    plt.close(figure)


# --------------------------------------------------------------------------- #
# Пункт 9 — контроль пресета
# --------------------------------------------------------------------------- #


CONTROL_TEMPERATURES = (450.0, 550.0, 1250.0, 1400.0)


def step9(ctx: Context) -> None:
    """Контроль пресета: «быстрый набор» против «всех фаз базы».

    Полный скан в режиме «все фазы» после правки мастера не считается. Сверка
    идёт по точкам, которые в этом режиме посчитаны: 8 температур пункта 2,
    четыре контрольные точки скана и все точки, оставшиеся в кэше от первого
    прогона до перехода на экономный режим.
    """
    control = temperature_points(ctx, sorted(set(POINT_TEMPERATURES) | set(CONTROL_TEMPERATURES)))
    solve_points(ctx, MODE_ALL, control, "п.9 контрольные точки (все фазы)")
    solve_points(ctx, MODE_FAST, control, "п.9 контрольные точки (быстрый набор)")

    wide_fast = step_scan(ctx, MODE_FAST, cached_only=True)
    corners_fast = step_corners(ctx, MODE_FAST)

    wide_all_path = OUT / "p1_scan_wide_all.csv"
    corners_all_path = OUT / "p8_corners.csv"
    if not wide_all_path.is_file() or not corners_all_path.is_file():
        raise RuntimeError("Сначала нужны результаты п.1 и п.8 в режиме «все фазы».")
    wide_all = pd.read_csv(wide_all_path, sep=";", decimal=",", encoding="utf-8-sig")
    corners_all = pd.read_csv(corners_all_path, sep=";", decimal=",", encoding="utf-8-sig")

    rows: list[dict[str, Any]] = []
    phases = sorted(set(wide_all.columns) | set(wide_fast.columns) - {"T, °C"})
    phases = [p for p in phases if p != "T, °C"]
    all_indexed = wide_all.set_index("T, °C")
    fast_indexed = wide_fast.set_index("T, °C")
    for temperature in sorted(set(all_indexed.index) & set(fast_indexed.index)):
        for phase in phases:
            a = float(all_indexed.at[temperature, phase]) if phase in all_indexed.columns else 0.0
            f = float(fast_indexed.at[temperature, phase]) if phase in fast_indexed.columns else 0.0
            if max(a, f) <= PRESENT_FLOOR:
                continue
            rows.append({
                "T, °C": temperature,
                "Фаза": phase,
                "Все фазы": a,
                "Быстрый набор": f,
                "Разница": f - a,
                "Только во «все фазы»": "да" if a > PRESENT_FLOOR >= f else "",
                "Только в «быстром»": "да" if f > PRESENT_FLOOR >= a else "",
            })
    scan_compare = pd.DataFrame(rows)
    write_csv(scan_compare, "p9_scan_compare.csv")

    keys = ["Cr, масс.%", "Mo, масс.%", "Ti, масс.%", "Nb, масс.%", "T, °C"]
    merged = corners_all.merge(
        corners_fast, on=keys, suffixes=(" (все)", " (быстрый)"), validate="one_to_one"
    )
    if len(merged) != len(corners_all) or len(merged) != len(corners_fast):
        # Ключи слияния — числа с плавающей точкой, прошедшие круг через CSV.
        # Потерянная строка означала бы, что вердикт «пресет ничего не теряет»
        # получен не по всем углам, поэтому это отказ, а не предупреждение.
        raise RuntimeError(
            "Слияние углов потеряло строки: "
            f"все фазы {len(corners_all)}, быстрый набор {len(corners_fast)}, "
            f"совпало {len(merged)}. Сверка пресета по неполному набору углов "
            "недействительна."
        )
    merged["Разница Σ TCP"] = (
        merged["Σ TCP, мольная доля (быстрый)"] - merged["Σ TCP, мольная доля (все)"]
    )
    merged["Совпал вердикт TCP"] = merged["Есть TCP (все)"] == merged["Есть TCP (быстрый)"]
    write_csv(
        merged[keys + [
            "Есть TCP (все)", "Есть TCP (быстрый)", "Совпал вердикт TCP",
            "Σ TCP, мольная доля (все)", "Σ TCP, мольная доля (быстрый)",
            "Разница Σ TCP",
            "Все фазы (все)", "Все фазы (быстрый)",
        ]],
        "p9_corners_compare.csv",
    )

    lost = sorted(set(scan_compare.loc[scan_compare["Только во «все фазы»"] == "да", "Фаза"]))
    gained = sorted(set(scan_compare.loc[scan_compare["Только в «быстром»"] == "да", "Фаза"]))
    compared = sorted(set(all_indexed.index) & set(fast_indexed.index))
    summary = {
        "pdens": PDENS,
        "фаз в наборе «все»": len(ctx.phases_all),
        "фаз в «быстром наборе»": len(ctx.phases_fast),
        "сверено температур": len(compared),
        "обязательные контрольные точки, °C": sorted(
            set(POINT_TEMPERATURES) | set(CONTROL_TEMPERATURES)
        ),
        "фазы не из быстрого набора": sorted(set(ctx.phases_all) - set(ctx.phases_fast)),
        "п.1: фазы, потерянные быстрым набором": lost,
        "п.1: фазы, появившиеся только в быстром наборе": gained,
        "п.1: макс. |разница| доли": float(scan_compare["Разница"].abs().max())
        if not scan_compare.empty else 0.0,
        "п.8: вердикт TCP совпал во всех углах": bool(merged["Совпал вердикт TCP"].all()),
        "п.8: макс. |разница| Σ TCP": float(merged["Разница Σ TCP"].abs().max()),
    }
    write_json(summary, "p9_preset_check.json")


# --------------------------------------------------------------------------- #
# Досчёт точек, сошедшихся в пустое решение
# --------------------------------------------------------------------------- #


def step_fix(ctx: Context) -> None:
    """Пересчитать точки, где ``equilibrium`` вернул NaN во всех вершинах.

    pycalphad считает такую точку успешной (исключения нет), но набор фаз пуст.
    Лечится другой плотностью стартовой выборки; какие точки и какой ``pdens``
    их спас — записывается в ``p0_retried_points.csv``.
    """
    from thermogar_parallel import solve_points_in_process

    rows: list[dict[str, Any]] = []
    for mode in (MODE_ALL, MODE_FAST):
        path = cache_file(mode)
        if not path.is_file():
            continue
        records = load_cache(mode)
        broken = [r for r in records.values() if r["ok"] and not r["fractions"]]
        log(f"досчёт ({mode}): пустых решений {len(broken)}")
        if not broken:
            continue
        for record in broken:
            point = {"T": record["T_K"], "X": record["X"]}
            fixed = False
            for pdens in RETRY_PDENS:
                result = solve_points_in_process(
                    ctx.db, [point], list(COMPONENTS), ctx.phases(mode), pdens=pdens
                )[0]
                if result.ok and result.phase_fractions:
                    new_record = _record_of(point, record["key"], result, pdens)
                    records[record["key"]] = new_record
                    fixed = True
                    log(f"досчёт ({mode}) {_point_label(point)}: помогло pdens={pdens}")
                    rows.append({
                        "Набор фаз": mode,
                        "T, °C": round(record["T_C"], 1),
                        "x(CR)": record["X"].get("CR", 0.0),
                        "x(MO)": record["X"].get("MO", 0.0),
                        "pdens": pdens,
                        "Результат": " + ".join(sorted(new_record["fractions"])),
                    })
                    break
            if not fixed:
                log(f"досчёт ({mode}) {_point_label(point)}: не спасло ни одно pdens")
                rows.append({
                    "Набор фаз": mode,
                    "T, °C": round(record["T_C"], 1),
                    "x(CR)": record["X"].get("CR", 0.0),
                    "x(MO)": record["X"].get("MO", 0.0),
                    "pdens": "; ".join(str(value) for value in RETRY_PDENS),
                    "Результат": "не сошлось",
                })
        with path.open("w", encoding="utf-8") as handle:
            for record in records.values():
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    if rows:
        write_csv(pd.DataFrame(rows), "p0_retried_points.csv")

    # Полный список точек кэша, посчитанных не штатной плотностью выборки:
    # ключ кэша ``pdens`` не содержит, поэтому единственный способ не потерять
    # это из виду — отдельная таблица, которая уходит и в сводную книгу.
    off_nominal = off_nominal_points(MODE_ALL) + off_nominal_points(MODE_FAST)
    if off_nominal:
        write_csv(pd.DataFrame(off_nominal), "p0_point_pdens.csv")
        log(f"точек не штатной плотности в кэше: {len(off_nominal)}")
    else:
        log(f"все точки кэша посчитаны штатной плотностью pdens={PDENS}")


# --------------------------------------------------------------------------- #
# Сводный Excel
# --------------------------------------------------------------------------- #


EXCEL_SHEETS: tuple[tuple[str, str], ...] = (
    ("p1_scan_wide.csv", "П1 скан T"),
    ("p1_solvus.csv", "П1 сольвусы"),
    ("p1_scan_wide_all.csv", "П1 скан T все фазы"),
    ("p1_solvus_all.csv", "П1 сольвусы все фазы"),
    ("p0_retried_points.csv", "Досчёт точек"),
    ("p0_point_pdens.csv", "Точки не штатного pdens"),
    ("p1_scan_phase_compositions.csv", "П1 составы фаз"),
    ("p2_point_equilibria.csv", "П2 точки"),
    ("p2_element_partition.csv", "П2 распределение"),
    ("p3_equilibrium_solidification.csv", "П3 равновесное"),
    ("p3_scheil.csv", "П3 Шейль"),
    ("p4_isopleth_cr.csv", "П4 изоплета Cr"),
    ("p4_isopleth_mo.csv", "П4 изоплета Mo"),
    ("p4_isopleth_cr_boundary.csv", "П4 граница Cr"),
    ("p4_isopleth_mo_boundary.csv", "П4 граница Mo"),
    ("p5_driving_forces.csv", "П5 движущие силы"),
    ("p6_density.csv", "П6 плотность"),
    ("p7_homogenization.csv", "П7 гомогенизация"),
    ("p7_diffusivity_check.csv", "П7 сверка D"),
    ("p7_search_runs.csv", "П7 прогоны"),
    ("p7_module_runs.csv", "П7 штатный модуль"),
    ("p8_corners.csv", "П8 углы марки"),
    ("p8_corners_fast.csv", "П9 углы быстрый"),
    ("p9_scan_compare.csv", "П9 сравнение скана"),
    ("p9_corners_compare.csv", "П9 сравнение углов"),
)


def step_excel(ctx: Context) -> None:
    path = OUT / "ХН62М_расчёт.xlsx"
    wt = full_wt()
    mole = wt_to_mole(ctx, wt)
    info = pd.DataFrame(
        [
            {"Параметр": "Сплав", "Значение": "ХН62М(Sc)-ВИ (ЭК199-ВИ), середина марки"},
            {"Параметр": "База", "Значение": DB_REL},
            {"Параметр": "SHA-256 базы", "Значение": ctx.sha256},
            {"Параметр": "Компоненты", "Значение": ", ".join(COMPONENTS)},
            {"Параметр": "Фаз «все»", "Значение": len(ctx.phases_all)},
            {"Параметр": "Фаз «быстрый набор»", "Значение": len(ctx.phases_fast)},
            {"Параметр": "Исключено (не строится модель)",
             "Значение": ", ".join(UNBUILDABLE_PHASES)},
            {"Параметр": "pdens (calc_opts)", "Значение": PDENS},
            {"Параметр": "Воркеров", "Значение": ctx.workers},
            {"Параметр": "Набор фаз в п.1",
             "Значение": "быстрый набор; «все фазы» — п.2 и контрольные точки п.9"},
            {"Параметр": "Не моделируется", "Значение": "Sc 0,05 % и P 0,025 % — нет в mc_ni"},
        ]
        + [{"Параметр": f"{e}, масс.%", "Значение": round(wt[e], 4)} for e in sorted(wt)]
        + [{"Параметр": f"x({e})", "Значение": round(mole[e], 6)} for e in sorted(mole)]
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        info.to_excel(writer, sheet_name="Состав и настройки", index=False)
        for name, sheet in EXCEL_SHEETS:
            source = OUT / name
            if not source.is_file():
                log(f"Excel: пропущен отсутствующий {name}")
                continue
            table = pd.read_csv(source, sep=";", decimal=",", encoding="utf-8-sig")
            table.to_excel(writer, sheet_name=sheet[:31], index=False)
        summary_path = OUT / "p3_solidification_summary.json"
        if summary_path.is_file():
            payload = json.loads(summary_path.read_text("utf-8"))
            pd.DataFrame(
                [{"Показатель": k, "Значение": json.dumps(v, ensure_ascii=False)}
                 for k, v in payload.items()]
            ).to_excel(writer, sheet_name="П3 итоги", index=False)
        check_path = OUT / "p9_preset_check.json"
        if check_path.is_file():
            payload = json.loads(check_path.read_text("utf-8"))
            pd.DataFrame(
                [{"Показатель": k, "Значение": json.dumps(v, ensure_ascii=False)}
                 for k, v in payload.items()]
            ).to_excel(writer, sheet_name="П9 итоги", index=False)
    log(f"записано: {path.relative_to(ROOT)}")


# --------------------------------------------------------------------------- #
# Точка входа
# --------------------------------------------------------------------------- #


STEPS = {
    "1": step1,
    "2": step2,
    "3": step3,
    "4": step4,
    "5": step5,
    "6": step6,
    "7": step7,
    "8": step8,
    "9": step9,
    "fix": step_fix,
    "excel": step_excel,
}

# Порядок по возрастанию стоимости, а не по номерам (правка мастера):
# дешёвые пункты считаются первыми, изоплеты — последними, потому что они
# самые тяжёлые по памяти и их падение не должно уносить остальное.
ORDER = ("fix", "5", "6", "2", "1", "3", "7", "8", "9", "4", "excel")

# Служебные шаги: чинят кэш и собирают книгу из готовых CSV, стоят секунды и
# обязаны выполняться каждый раз — отметка о завершении их не пропускает.
ALWAYS_RUN = frozenset({"fix", "excel"})


def _run_child(step: str, workers: int, pdens: int, chunk: int, force: bool) -> int:
    """Один пункт в отдельном процессе: память отдаётся системе целиком."""
    command = [
        sys.executable, "-X", "utf8", "-u", str(Path(__file__).resolve()),
        "--only", step, "--child",
        "--workers", str(workers), "--pdens", str(pdens), "--chunk", str(chunk),
    ]
    if force:
        command.append("--force")
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = "0"
    completed = subprocess.run(command, env=environment, cwd=str(ROOT), check=False)
    return int(completed.returncode)


def main(argv: Sequence[str] | None = None) -> int:
    global PDENS, CHUNK_POINTS

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="all",
                        help="номер пункта 1…9, 'fix', 'excel' или 'all'; через запятую")
    parser.add_argument("--workers", type=int, default=1,
                        help=f"число процессов, 1…{MAX_WORKERS} (по умолчанию 1)")
    parser.add_argument("--pdens", type=int, default=PDENS,
                        help="плотность стартовой выборки equilibrium")
    parser.add_argument("--chunk", type=int, default=CHUNK_POINTS,
                        help="сколько точек решать между сбросами памяти")
    parser.add_argument("--child", action="store_true",
                        help="служебный: выполнять пункты в этом же процессе")
    parser.add_argument("--in-process", action="store_true",
                        help="не разносить пункты по дочерним процессам")
    parser.add_argument("--force", action="store_true",
                        help="пересчитать пункты, даже если они отмечены в _progress.json")
    arguments = parser.parse_args(argv)

    if os.environ.get("PYTHONHASHSEED") != "0":
        log("ВНИМАНИЕ: PYTHONHASHSEED != 0, числа могут отличаться в последних битах")

    workers = max(1, min(MAX_WORKERS, int(arguments.workers)))
    if workers != arguments.workers:
        log(f"воркеров ограничено до {workers} (память)")
    PDENS = max(10, int(arguments.pdens))
    CHUNK_POINTS = max(1, int(arguments.chunk))
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    if arguments.only.strip().lower() == "all":
        selected = list(ORDER)
    else:
        selected = [item.strip() for item in arguments.only.split(",") if item.strip()]
    unknown = [item for item in selected if item not in STEPS]
    if unknown:
        parser.error(f"неизвестные пункты: {', '.join(unknown)}")

    timings: dict[str, float] = {}
    failures: dict[str, str] = {}
    skipped: list[str] = []

    def should_skip(step: str) -> bool:
        """Пункт уже посчитан теми же значимыми параметрами?"""
        if arguments.force or step in ALWAYS_RUN:
            return False
        entry = load_progress().get(step)
        if not entry or entry.get("статус") != "готов":
            return False
        differences = progress_mismatch(entry.get("параметры", {}),
                                        step_parameters(step, workers))
        if differences:
            log(f"пункт {step} пересчитывается: {'; '.join(differences)}")
            return False
        log(f"пункт {step} пропущен, посчитан ранее "
            f"({entry.get('завершён', '?')}, {entry.get('минут', '?')} мин)")
        return True

    def record(step: str, seconds: float, error: str | None) -> None:
        progress = load_progress()
        progress[step] = {
            "статус": "не выполнен" if error else "готов",
            "завершён": time.strftime("%Y-%m-%d %H:%M:%S"),
            "минут": round(seconds / 60.0, 2),
            "параметры": step_parameters(step, workers),
        }
        if error:
            progress[step]["ошибка"] = error
        save_progress(progress)

    # Родительский режим: каждый пункт — отдельный процесс, база не остаётся
    # в памяти между пунктами. Тяжёлые пункты 4 и 8 таким образом изолированы.
    if not arguments.child and not arguments.in_process:
        log(f"пунктов к выполнению: {len(selected)}; каждый — отдельным процессом")
        log(f"воркеров: {workers}, pdens: {PDENS}, точек в куске: {CHUNK_POINTS}")
        log(f"порядок: {' → '.join(selected)}")
        for item in selected:
            if should_skip(item):
                skipped.append(item)
                continue
            log(f"=== пункт {item} (дочерний процесс) ===")
            started = time.perf_counter()
            code = _run_child(item, workers, PDENS, CHUNK_POINTS, arguments.force)
            timings[item] = time.perf_counter() - started
            if code != 0:
                failures[item] = f"дочерний процесс вернул код {code}"
                log(f"пункт {item} УПАЛ: код {code}; переходим к следующему")
                record(item, timings[item], failures[item])
            log(f"пункт {item}: {timings[item] / 60.0:.1f} мин")
    else:
        ctx = build_context(workers)
        log(f"воркеров: {workers}, pdens: {PDENS}, точек в куске: {CHUNK_POINTS}")
        try:
            for item in selected:
                if should_skip(item):
                    skipped.append(item)
                    continue
                log(f"=== пункт {item} ===")
                started = time.perf_counter()
                error_text: str | None = None
                try:
                    STEPS[item](ctx)
                except Exception as error:  # пункт падает — остальные продолжают
                    error_text = f"{type(error).__name__}: {error}"
                    failures[item] = error_text
                    log(f"пункт {item} УПАЛ: {error_text}; переходим к следующему")
                    import traceback

                    traceback.print_exc()
                timings[item] = time.perf_counter() - started
                record(item, timings[item], error_text)
                gc.collect()
                log(f"пункт {item}: {timings[item] / 60.0:.1f} мин")
        finally:
            ctx.close()

    report = {
        "времена, мин": {k: round(v / 60.0, 2) for k, v in timings.items()},
        "посчитано": sorted(set(timings) - set(failures)),
        "пропущено (посчитано ранее)": skipped,
        "упало": failures,
        "воркеров": workers,
        "pdens": PDENS,
        "точек в куске": CHUNK_POINTS,
        "пункты отдельными процессами": not (arguments.child or arguments.in_process),
        "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
        "_progress.json": load_progress(),
    }
    if not arguments.child:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        write_json(report, f"run_{stamp}.json")
        log("--- сводка ---")
        log(f"посчитано: {', '.join(report['посчитано']) or 'ничего'}")
        log(f"пропущено (посчитано ранее): {', '.join(skipped) or 'нет'}")
        log(f"упало: {', '.join(f'{k} ({v})' for k, v in failures.items()) or 'нет'}")
    log("готово")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
