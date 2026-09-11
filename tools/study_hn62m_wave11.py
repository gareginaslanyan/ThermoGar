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
import threading
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
PDB_REL = "databases/physical/original/physical_data_v103.pdb"
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

# --- A2 -------------------------------------------------------------------- #

# Температуры, названные постановкой A2.
A2_REQUIRED_C = (25.0, 400.0, 700.0, 900.0, 1100.0, 1300.0)
# Вспомогательная сетка: нужна, чтобы найти границу, с которой доля оценочных
# фаз падает ниже 1 %. Половинным делением её искать нельзя — доля оценочных
# немонотонна по температуре (фазы растворяются и появляются на разных
# интервалах), и деление сошлось бы на случайной точке.
A2_SCAN_C = tuple(float(50 * index) for index in range(1, 27))  # 50…1300 с шагом 50
A2_ESTIMATED_LIMIT_PCT = 1.0
A2_PDENS = 100
# Плотности выборки для повтора точки, сошедшейся в пустое решение. Волна 9
# ловила ровно ту же дыру на 350 °C (results/hn62m/p6_density.csv) и лечила её
# так же; список и порядок оттуда.
A2_RETRY_PDENS: tuple[int, ...] = (200, 300, 50)
# Фазы, у которых собственной модели плотности в PDB нет; названы в постановке.
# Их доля и решает, прикидка низкотемпературная плотность или расчёт.
A2_WATCHED_PHASES: tuple[str, ...] = (
    "NI2CR", "P_PHASE", "MNS_Q", "DELTA", "MU_PHASE",
)

# --- A3 -------------------------------------------------------------------- #

A3_T_C = (1150.0, 1175.0, 1200.0)
A3_CELLS_UM = (1.0, 3.0, 5.0)
A3_TARGET = 0.05            # остаточная неоднородность по молибдену
A3_NODES = 40
A3_PHASE = "FCC_A1"
A3_ELEMENTS = ("NI", "CR", "MO")
A3_GAS_CONSTANT = 8.31446261815324

# Начальный профиль — прямоугольная ступень на отрезке длиной L с
# непроницаемыми краями, что эквивалентно периодической сегрегации с длиной
# волны 2L. Первая мода прямоугольной волны имеет амплитуду 4/π от амплитуды
# ступени, поэтому размах падает как (4/π)·exp(−π²Dt/L²), и время до остатка
# 5 % равно t = (L²/π²D)·ln((4/π)/0,05). Те же соотношения у волны 9 — иначе
# старые и новые числа были бы несравнимы.
A3_FIRST_MODE = 4.0 / math.pi

# Выражения MQ(FCC_A1&X,NI:*) из mc_ni, Дж/моль. Нужны, чтобы сверить то, что
# отдаёт kawin, с тем, что написано в самой базе.
A3_MQ_EXPRESSIONS: dict[str, Any] = {
    "NI": lambda t: -287000.0 - 69.8 * t,
    "CR": lambda t: -287000.0 - 64.4 * t,
    "MO": lambda t: -267585.0 - 79.5 * t,
}

# Профиль сегрегации берётся тот же, что считала волна 9: расчёт Шейля от
# мобильностей не зависит, а одинаковый вход — единственный способ показать,
# что разница в числах A3 целиком от поправки подвижности.
A3_SEGREGATION_INPUT = "a3_segregation_input.csv"

# Числа волны 9 (results/hn62m/p7_homogenization.csv) — для колонки «старое».
A3_WAVE9: dict[tuple[float, float], dict[str, float]] = {
    (1150.0, 1.0): {"D": 1.0328715926679819e-12, "аналитически, с": 0.3175677796938177,
                    "численно, с": 1.2801895259508165, "остаток": 0.10543418180128744},
    (1150.0, 3.0): {"D": 1.0328715926679819e-12, "аналитически, с": 2.85811001724436,
                    "численно, с": 11.521705734124948, "остаток": 0.10543418179881583},
    (1150.0, 5.0): {"D": 1.0328715926679819e-12, "аналитически, с": 7.939194492345442,
                    "численно, с": 32.00473815135267, "остаток": 0.1054341817964768},
    (1175.0, 1.0): {"D": 1.4431184610244325e-12, "аналитически, с": 0.22729023794730252,
                    "численно, с": 0.8509693735879449, "остаток": 0.10482396619721525},
    (1175.0, 3.0): {"D": 1.4431184610244325e-12, "аналитически, с": 2.0456121415257233,
                    "численно, с": 7.6587243635183, "остаток": 0.10482396618043893},
    (1175.0, 5.0): {"D": 1.4431184610244325e-12, "аналитически, с": 5.682255948682562,
                    "численно, с": 21.274234343630408, "остаток": 0.10482396618155986},
    (1200.0, 1.0): {"D": 1.993551814520756e-12, "аналитически, с": 0.16453384156019046,
                    "численно, с": 0.5705979590297453, "остаток": 0.10438537475888417},
    (1200.0, 3.0): {"D": 1.993551814520756e-12, "аналитически, с": 1.4808045740417144,
                    "численно, с": 5.135381630924319, "остаток": 0.10438537476011997},
    (1200.0, 5.0): {"D": 1.993551814520756e-12, "аналитически, с": 4.11334603900476,
                    "численно, с": 14.264948974815313, "остаток": 0.10438537476199783},
}

# --- 11D-2 ----------------------------------------------------------------- #

# Полуволны ячейки, названные постановкой 11D-2. Ряд 1, 3, 5 мкм, на котором
# считалась A3, отвечает только лазерной печати; у литой заготовки расстояние
# между вторичными осями дендритов — десятки-сотни микрон, и время идёт как
# квадрат размера, поэтому разница не косметическая.
D2_CELLS_UM = (0.5, 1.0, 5.0, 25.0, 50.0, 100.0)
# Какому состоянию отвечает размер. Подпись обязательна: «окно гомогенизации
# 1175–1200 °C» без размера ячейки технолога введёт в заблуждение.
D2_STRUCTURE: dict[float, str] = {
    0.5: "лазерная печать, ячеистая структура",
    1.0: "лазерная печать, ячеистая структура",
    5.0: "мелкая дендритная структура, быстрая кристаллизация",
    25.0: "литая заготовка, вторичные оси дендритов",
    50.0: "литая заготовка, вторичные оси дендритов",
    100.0: "литая заготовка, вторичные оси дендритов",
}
# Численно считаются все размеры. Так вышло не по недосмотру: явная схема
# держит шаг dt ~ dx², а сетка узлов одна и та же, поэтому число шагов до
# момента t ~ L²/D равно (L/dx)² = (узлов)² и от L не зависит — прогоны A3 на
# 1, 3 и 5 мкм заняли 15,3, 18,5 и 16,3 с. Порог оставлен на случай, если
# сетку придётся сгущать: тогда крупные размеры уйдут на аналитику.
D2_NUMERIC_MAX_UM = 100.0

# --- A4, A5 ---------------------------------------------------------------- #

A4_PDENS = 100
A4_STEP_K = 0.5
A4_START_OVER_LIQUIDUS_K = 5.0
# Порог останова ``scheil``: расчёт прекращается, когда доля жидкости падает
# ниже него. Значение волны 10 сохранено, чтобы прогоны были сравнимы.
A4_STOP_LIQUID = 1.0e-4
# Доли твёрдого, для которых постановка просит температуру. Выводятся только
# те, что действительно достигнуты посчитанными точками.
A4_FS_MARKS = (0.5, 0.9, 0.95, 0.99)
# Окно критерия Kou. Первое — заявленное волной 10, фактические границы
# подставляются в имя поля. Второе — фиксированное, где данные есть у всех
# прогонов, поэтому составы сравниваются на одном и том же окне.
A4_KOU_DECLARED_WINDOW = (0.90, 0.99)
A4_KOU_FIXED_WINDOW = (0.85, 0.95)
# Фазы, которые пробуем исключить, проверяя гипотезу «останов вызван
# появлением σ и инвариантным равновесием».
A4_EXCLUSION_TRIALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("без исключений", ()),
    ("без SIGMA", ("SIGMA",)),
    ("без SIGMA и TI4C2S2", ("SIGMA", "TI4C2S2")),
)

# --- 11J-2 ----------------------------------------------------------------- #

# Гипотеза мастера: отказ сходимости в хвосте вызван не пределом метода, а
# редкой выборкой в той области состава, куда уехала остаточная жидкость
# (Cr 0,32 и Mo 0,14 мольной доли против исходных 0,26 и 0,13). Проверяется
# повторением головного прогона на более плотной выборке.
J2_PDENS: tuple[int, ...] = (300, 500)
# Прогон при pdens 100 занял 1314 с. Рост стоимости с плотностью близок к
# линейному, поэтому pdens 500 ожидается около пяти часов. Если он переберёт
# этот предел, подпункт ограничивается плотностью 300 — так прямо сказано в
# постановке.
J2_BUDGET_SECONDS = 6.0 * 3600.0
# Сколько свободной физической памяти должно быть на старте прогона. Правило
# проекта — при признаках свопа уменьшать сетку, а не ждать. Прогон при
# pdens 500 дважды снимался системой, когда свободной физической оставалось
# около трёх гигабайт; пик его собственного рабочего набора при этом был всего
# 1,97 ГиБ, то есть память съедал не он, но снимали именно его. Порог с
# запасом: подкачка потолок и поднимает, но счёт по ней идёт в разы медленнее.
J2_MIN_FREE_GIB = 6.0


A5_STEP_K = 0.5
A5_CASES: tuple[tuple[str, dict[str, float]], ...] = (
    ("Mn 0,50 %, S 0,020 %", {"MN": 0.50, "S": 0.020}),
    ("Mn 0,20 %, S 0,020 %", {"MN": 0.20, "S": 0.020}),
)

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
        self._models: Any = None
        self._phase_records: Any = None
        log(
            f"база разобрана за {time.perf_counter() - started:.1f} с; "
            f"фаз {len(self.phases)}; исключено {self.excluded_phases or 'нет'}; "
            f"ремонт базы {'доступен' if self.repair_available else 'недоступен'}"
        )


    def compiled(self) -> tuple[Any, Any]:
        """Модели фаз и скомпилированные записи, построенные один раз.

        Без этого ``pycalphad.equilibrium`` строит символьные модели всех 48
        фаз и компилирует их заново на каждый вызов, и это, а не сам решатель,
        занимает основное время: на десятикомпонентном составе сборка стоит
        минуты, а решение — секунды. Объекты те же самые, что построил бы сам
        ``equilibrium``, поэтому числа не меняются; ровно так же переиспользует
        их ``scheil.simulate_scheil_solidification``.
        """

        if self._phase_records is None:
            from pycalphad import variables as v
            from pycalphad.codegen.phase_record_factory import PhaseRecordFactory
            from pycalphad.core.utils import instantiate_models

            started = time.perf_counter()
            self._models = instantiate_models(self.db, list(COMPONENTS), self.phases)
            self._phase_records = PhaseRecordFactory(
                self.db, list(COMPONENTS), [v.N, v.P, v.T], self._models
            )
            log(f"модели фаз построены за {time.perf_counter() - started:.1f} с")
        return self._models, self._phase_records


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


def solve_raw(
    ctx: Context, mole: Mapping[str, float], temperature_c: float, pdens: int
) -> Any:
    """Сырой результат pycalphad: нужен там, где смотрят подрешётки (A2)."""

    from pycalphad import equilibrium, variables as v

    conditions: dict[Any, float] = {
        v.N: 1.0, v.P: 101325.0, v.T: float(temperature_c) + 273.15,
    }
    conditions.update(
        {v.X(element): value for element, value in independent_x(mole).items()}
    )
    models, phase_records = ctx.compiled()
    return equilibrium(
        ctx.db, list(COMPONENTS), ctx.phases, conditions,
        model=models, phase_records=phase_records,
        calc_opts={"pdens": int(pdens)},
    )


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

    result = solve_raw(ctx, mole, temperature_c, pdens)
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
        pd.DataFrame(rows).to_csv(curve_path, **CSV_WRITE)
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
# A2. Плотность сплава
# --------------------------------------------------------------------------- #


def a2_point(ctx: Context, physical_db: Any, mole: Mapping[str, float],
             temperature_c: float) -> tuple[dict[str, Any], list[dict[str, Any]],
                                            list[dict[str, Any]]]:
    """Плотность сплава при одной температуре и всё, что к ней прилагается.

    Возвращает тройку: строку сводки, пофазную роспись покрытия и сами тексты
    предупреждений расчёта. Предупреждения снимаются здесь, а не
    пересказываются: поток B отложил этот вывод по памяти, и подпункт A2 идёт
    ровно по тому же пути, поэтому дословный текст должен уехать в результаты.
    """

    from thermogar_physical import calculate_physical_properties

    temperature_k = float(temperature_c) + 273.15
    started = time.perf_counter()

    # Точка может сойтись в пустое решение: фаз нет, плотности нет. Молча
    # оставить дыру в кривой нельзя — повторяем с другой плотностью выборки и
    # записываем, какая помогла.
    used_pdens = A2_PDENS
    equilibrium_result = solve_raw(ctx, mole, temperature_c, used_pdens)
    result = calculate_physical_properties(
        ctx.db, equilibrium_result, list(ELEMENTS), temperature_k, physical_db
    )
    for retry_pdens in A2_RETRY_PDENS:
        if result.alloy_density_kg_m3 is not None and not result.phase_table.empty:
            break
        log(f"A2 {temperature_c:.0f} °C: пустое решение при pdens={used_pdens}, "
            f"повтор при pdens={retry_pdens}")
        del equilibrium_result, result
        gc.collect()
        used_pdens = retry_pdens
        equilibrium_result = solve_raw(ctx, mole, temperature_c, used_pdens)
        result = calculate_physical_properties(
            ctx.db, equilibrium_result, list(ELEMENTS), temperature_k, physical_db
        )
    seconds = time.perf_counter() - started

    table = result.phase_table
    estimated_names: list[str] = []
    missing_names: list[str] = []
    phase_rows: list[dict[str, Any]] = []
    if not table.empty:
        estimated_names = sorted(
            str(name) for name in
            table.loc[table["Статус данных"].str.startswith("оценка"), "Фаза"]
        )
        missing_names = sorted(
            str(name) for name in
            table.loc[table["Статус данных"] == "нет данных", "Фаза"]
        )
        for record in table.to_dict("records"):
            phase_rows.append({
                "T, °C": float(temperature_c),
                "фаза": str(record.get("Фаза", "")),
                "статус данных": str(record.get("Статус данных", "")),
                "мольная доля, %": record.get("Мольная доля, %"),
                "массовая доля, %": record.get("Массовая доля, %"),
                "плотность фазы, кг/м³": record.get("Плотность фазы, кг/м³"),
                "модель плотности": str(record.get("Модель плотности", "")),
                "примечание": str(record.get("Примечание", "")),
                "диагностика": str(record.get("Диагностика", "")),
            })
    phases_present = sorted(str(name) for name in table["Фаза"]) if not table.empty else []

    warning_rows = [
        {"T, °C": float(temperature_c), "источник": "предупреждение расчёта",
         "текст": str(text)}
        for text in (result.warnings or [])
    ]
    warning_rows.append({
        "T, °C": float(temperature_c), "источник": "качество результата",
        "текст": str(result.quality_label),
    })
    if not result.missing_table.empty:
        for record in result.missing_table.to_dict("records"):
            warning_rows.append({
                "T, °C": float(temperature_c),
                "источник": f"фаза без модели: {record.get('Фаза', '')}",
                "текст": (
                    f"мольная доля {record.get('Мольная доля, %')} %; "
                    f"{record.get('Причина', '')} {record.get('Диагностика', '')}"
                ).strip(),
            })

    density = result.alloy_density_kg_m3
    row = {
        "T, °C": float(temperature_c),
        "плотность, кг/м³": None if density is None else round(float(density), 1),
        "плотность, г/см³": None if density is None else round(float(density) / 1000.0, 4),
        "pdens точки": int(used_pdens),
        "оценочных фаз, % молей": round(float(result.estimated_mole_pct), 3),
        "покрытие по массе, %": round(float(result.mass_coverage_pct), 3),
        "прямая модель, % молей": round(float(result.direct_mole_pct), 3),
        "оценочные фазы": ", ".join(estimated_names) or "нет",
        "фазы без данных": ", ".join(missing_names) or "нет",
        "равновесные фазы": " + ".join(phases_present),
        "качество": str(result.quality_label),
        "предупреждений": len(result.warnings or []),
        "время, с": round(seconds, 1),
    }
    del equilibrium_result, result
    gc.collect()
    log(f"A2 {temperature_c:.0f} °C: "
        f"{row['плотность, г/см³']} г/см³, оценочных {row['оценочных фаз, % молей']} %, "
        f"{row['оценочные фазы']}")
    return row, phase_rows, warning_rows


def a2_density(force: bool = False) -> dict[str, Any]:
    """Плотность на сетке температур. Считается в потомке."""

    from thermogar_physical import PhysicalDensityDatabase

    ctx = Context()
    physical_db = PhysicalDensityDatabase(str(ROOT / PDB_REL))
    mole = wt_to_mole(ctx, full_wt())

    temperatures = sorted(set(A2_REQUIRED_C) | set(A2_SCAN_C))
    partial = OUT / "a2_density.csv"
    phases_path = OUT / "a2_phase_coverage.csv"
    warnings_path = OUT / "a2_density_warnings.csv"

    def resume(path: Path) -> dict[float, list[dict[str, Any]]]:
        """Строки прошлого прогона, разложенные по температуре."""
        if not path.is_file() or force:
            return {}
        grouped: dict[float, list[dict[str, Any]]] = {}
        for record in pd.read_csv(path, **CSV_READ).to_dict("records"):
            grouped.setdefault(round(float(record["T, °C"]), 3), []).append(record)
        return grouped

    # Все три таблицы подхватываются вместе: иначе после обрыва сводка была бы
    # полной, а роспись и предупреждения — только за досчитанные точки.
    done_rows = resume(partial)
    done_phases = resume(phases_path)
    done_warnings = resume(warnings_path)

    rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    warning_rows: list[dict[str, Any]] = []
    for temperature in temperatures:
        key = round(float(temperature), 3)
        # Точка с непосчитанной плотностью не переиспользуется: в прошлом
        # прогоне она была дырой, и повтор с другой плотностью выборки должен
        # получить свой шанс.
        reusable = (
            key in done_rows and key in done_phases and key in done_warnings
            and pd.notna(done_rows[key][0].get("плотность, кг/м³"))
        )
        if reusable:
            rows.append(done_rows[key][0])
            phase_rows.extend(done_phases[key])
            warning_rows.extend(done_warnings[key])
        else:
            row, phases, warnings = a2_point(ctx, physical_db, mole, temperature)
            rows.append(row)
            phase_rows.extend(phases)
            warning_rows.extend(warnings)
        # Запись после каждой точки: расчёт длинный, обрыв не должен его терять.
        pd.DataFrame(rows).to_csv(partial, **CSV_WRITE)
        pd.DataFrame(phase_rows).to_csv(phases_path, **CSV_WRITE)
        pd.DataFrame(warning_rows).to_csv(warnings_path, **CSV_WRITE)

    return {
        "таблица": rows,
        "роспись фаз": phase_rows,
        "предупреждения": warning_rows,
    }


def a2_watched_phase_report(phase_rows: pd.DataFrame) -> list[dict[str, Any]]:
    """Роспись по фазам, у которых модели плотности в PDB нет.

    Список назван в постановке: NI2CR, P_PHASE, MNS_Q, DELTA, MU_PHASE. Для
    каждой — в каком интервале температур она вообще встречается, с каким
    статусом и какую долю молей набирает в худшей точке. Именно эти фазы и
    делают низкотемпературную плотность прикидкой.
    """

    report: list[dict[str, Any]] = []
    for phase in A2_WATCHED_PHASES:
        block = phase_rows[phase_rows["фаза"] == phase]
        if block.empty:
            report.append({
                "фаза": phase,
                "встречается": False,
                "примечание": "в равновесии на этой сетке температур не появилась",
            })
            continue
        share = block["мольная доля, %"].astype(float)
        worst = block.loc[share.idxmax()]
        statuses = sorted({str(value) for value in block["статус данных"]})
        report.append({
            "фаза": phase,
            "встречается": True,
            "температуры, °C": [
                float(block["T, °C"].min()), float(block["T, °C"].max())
            ],
            "точек сетки": int(len(block)),
            "статусы": statuses,
            "наибольшая мольная доля, %": round(float(share.max()), 3),
            "при T, °C": float(worst["T, °C"]),
            "модель плотности": str(worst["модель плотности"]) or "нет",
            "примечание": str(worst["примечание"]),
        })
    return report


def a2_reliable_from(table: pd.DataFrame) -> float | None:
    """Наименьшая температура, начиная с которой доля оценочных всюду < 1 %.

    Условие проверяется «и выше тоже», а не в одной точке: доля оценочных
    немонотонна, и первая точка ниже порога может оказаться провалом между
    двумя интервалами, где оценочных снова много.
    """

    ordered = table.sort_values("T, °C").reset_index(drop=True)
    values = ordered["оценочных фаз, % молей"].astype(float).to_numpy()
    temperatures = ordered["T, °C"].astype(float).to_numpy()
    for index in range(len(values)):
        if bool(np.all(values[index:] < A2_ESTIMATED_LIMIT_PCT)):
            return float(temperatures[index])
    return None


def plot_a2(table: pd.DataFrame, path: Path) -> None:
    ordered = table.sort_values("T, °C")
    density = ordered["плотность, г/см³"].astype(float)
    figure, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))

    axes[0].plot(ordered["T, °C"], density, "o-", linewidth=1.6, markersize=3)
    axes[0].set_xlabel("температура, °C")
    axes[0].set_ylabel("плотность сплава, г/см³")
    axes[0].set_title("Плотность ХН62М(Sc)-ВИ")
    axes[0].grid(alpha=0.3)

    estimated = ordered["оценочных фаз, % молей"].astype(float)
    axes[1].plot(ordered["T, °C"], estimated, "s-", color="#b03a2e",
                 linewidth=1.6, markersize=3)
    axes[1].axhline(A2_ESTIMATED_LIMIT_PCT, color="grey", linestyle="--", linewidth=0.9)
    axes[1].set_yscale("symlog", linthresh=0.1)
    axes[1].set_xlabel("температура, °C")
    axes[1].set_ylabel("доля оценочных фаз, % молей")
    axes[1].set_title("Доля фаз без модели плотности в PDB")
    axes[1].grid(alpha=0.3, which="both")

    boundary = a2_reliable_from(ordered)
    if boundary is not None:
        for axis in axes:
            axis.axvline(boundary, color="tab:green", linestyle=":", linewidth=1.2)
        axes[1].annotate(f"ниже 1 % с {boundary:.0f} °C", (boundary, A2_ESTIMATED_LIMIT_PCT),
                         fontsize=8, ha="left", va="bottom")

    figure.suptitle("A2. Плотность сплава и граница достоверности")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


def step_a2(force: bool = False) -> None:
    progress = load_progress()
    if progress.get("A2", {}).get("готов") and not force:
        log("A2 пропущен, посчитан ранее (--force для пересчёта)")
        return

    payload = run_child(["--a2", "1"] + (["--force"] if force else []))
    table = pd.DataFrame(payload["таблица"])
    phase_rows = pd.DataFrame(payload["роспись фаз"])
    warning_rows = pd.DataFrame(payload["предупреждения"])
    write_csv(table, "a2_density.csv")
    write_csv(phase_rows, "a2_phase_coverage.csv")
    write_csv(warning_rows, "a2_density_warnings.csv")
    plot_a2(table, OUT / "a2_density.png")

    required = table[table["T, °C"].isin(A2_REQUIRED_C)].sort_values("T, °C")
    write_csv(required, "a2_density_required.csv")
    boundary = a2_reliable_from(table)
    watched = a2_watched_phase_report(phase_rows)

    # Дословные тексты — отдельным файлом: сводка в JSON читается глазами, а
    # предупреждения должны быть цитируемы как есть.
    lines: list[str] = [
        "Предупреждения расчёта плотности ХН62М(Sc)-ВИ",
        f"База плотностей: {PDB_REL}",
        f"Порог достоверности: доля оценочных молей ниже "
        f"{A2_ESTIMATED_LIMIT_PCT:g} %",
        "",
    ]
    for temperature, block in warning_rows.groupby("T, °C"):
        lines.append(f"--- {float(temperature):.0f} °C ---")
        for record in block.to_dict("records"):
            lines.append(f"  [{record['источник']}] {record['текст']}")
        lines.append("")
    (OUT / "a2_density_warnings.txt").write_text("\n".join(lines), "utf-8")
    log(f"записано {(OUT / 'a2_density_warnings.txt').relative_to(ROOT)}")

    at_25 = required[required["T, °C"] == 25.0]
    summary: dict[str, Any] = {
        "подпункт": "A2. Плотность сплава на исправленном коде",
        "база плотностей": PDB_REL,
        "pdens": A2_PDENS,
        "температуры постановки": required.to_dict("records"),
        "порог достоверности, % оценочных молей": A2_ESTIMATED_LIMIT_PCT,
        "доля оценочных ниже порога начиная с, °C": boundary,
        "при 25 °C оценочных, % молей": (
            None if at_25.empty else float(at_25.iloc[0]["оценочных фаз, % молей"])
        ),
        "при 25 °C оценочные фазы": (
            None if at_25.empty else str(at_25.iloc[0]["оценочные фазы"])
        ),
        "фазы без модели в PDB": watched,
        "предупреждений всего": int(len(warning_rows)),
        "файл предупреждений": "a2_density_warnings.txt",
        "предупреждение": (
            "Низкотемпературная плотность — прикидка: основная часть молей "
            "приходится на фазы без собственной модели в PDB, они посчитаны по "
            "правилу смеси из плотностей элементов. В документы такое число "
            "идёт только с этой пометкой."
        ),
    }
    write_json(summary, "a2_summary.json")

    progress["A2"] = {
        "готов": True,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pdens": A2_PDENS,
        "точек": int(len(table)),
        "режим набора фаз": "все фазы",
    }
    save_progress(progress)


# --------------------------------------------------------------------------- #
# A3. Времена гомогенизации
# --------------------------------------------------------------------------- #


def a3_segregation() -> dict[str, float]:
    """Размах сегрегации Mo и Cr в FCC_A1 из расчёта Шейля волны 9."""

    path = OUT / A3_SEGREGATION_INPUT
    if not path.is_file():
        raise RuntimeError(
            f"Нет {path.relative_to(ROOT)}: положите туда p3_scheil.csv волны 9 "
            "(тот же вход, что у старых чисел)."
        )
    table = pd.read_csv(path, **CSV_READ)
    result: dict[str, float] = {}
    for element in ("MO", "CR"):
        column = f"x(FCC_A1,{element})"
        if column not in table.columns:
            raise RuntimeError(f"В {path.name} нет столбца {column}.")
        values = pd.to_numeric(table[column], errors="coerce").dropna()
        values = values[values > 0.0]
        if values.empty:
            raise RuntimeError(f"В {path.name} нет положительных значений {column}.")
        # Именно экстремумы, а не первая и последняя строка: у fs→1 идут
        # терминальные реакции, и состав FCC_A1 на последних шагах разворачивается.
        result[f"{element}_min"] = float(values.min())
        result[f"{element}_max"] = float(values.max())
    return result


def a3_thermodynamics(ctx: Context) -> Any:
    from kawin.thermo import GeneralThermodynamics

    return GeneralThermodynamics(ctx.db, list(A3_ELEMENTS), [A3_PHASE])


def a3_tracer(thermodynamics: Any, x_cr: float, x_mo: float,
              temperature_k: float) -> dict[str, float]:
    values = np.asarray(
        thermodynamics.getTracerDiffusivity([x_cr, x_mo], temperature_k, phase=A3_PHASE),
        dtype=float,
    ).ravel()
    return {element: float(value) for element, value in zip(A3_ELEMENTS, values)}


def a3_diffusivity_check(ctx: Context) -> tuple[pd.DataFrame, dict[str, float]]:
    """Сверка D от kawin со строками MQ самой базы на разбавленном пределе.

    Волна 9 показала здесь квадрат: параметр подвижности задавался в базе
    дважды — общей строкой ``MQ(<фаза>&<элемент>,*)`` и явной
    ``MQ(<фаза>&<элемент>,NI:*)`` с тем же выражением, — pycalphad складывал обе
    и получал ``exp(2·MQ/RT)``. Волна 10 разворачивает умолчание в явные строки
    вместо сложения. Таблица говорит, что получилось теперь: отношение
    ``kawin/база`` должно быть единицей, а ``√(kawin)/база`` — нет. Если
    наоборот, удвоение никуда не делось, и считать времена нельзя.

    Обе величины участвуют в проверке, но в таблицу уходит только первая:
    ``√(kawin)/база`` имела смысл, пока отношение было квадратом, а на
    исправленной базе показывает мусор порядка 10⁷ (пункт 11D-2).
    """

    thermodynamics = a3_thermodynamics(ctx)
    rows: list[dict[str, Any]] = []
    direct_gaps: list[float] = []
    squared_gaps: list[float] = []
    for temperature_c in A3_T_C:
        temperature_k = temperature_c + 273.15
        dilute = a3_tracer(thermodynamics, 1.0e-6, 1.0e-6, temperature_k)
        for element, expression in A3_MQ_EXPRESSIONS.items():
            from_database = math.exp(
                expression(temperature_k) / (A3_GAS_CONSTANT * temperature_k)
            )
            direct = dilute[element] / from_database
            squared = math.sqrt(dilute[element]) / from_database
            direct_gaps.append(abs(direct - 1.0))
            squared_gaps.append(abs(squared - 1.0))
            rows.append({
                "T, °C": temperature_c,
                "элемент": element,
                "D по строке MQ базы (разб. предел), м²/с": from_database,
                "D от kawin (разб. предел), м²/с": dilute[element],
                "отношение kawin / база": direct,
            })
    return pd.DataFrame(rows), {
        "макс. отклонение kawin/база от 1": max(direct_gaps),
        "макс. отклонение √(kawin)/база от 1": max(squared_gaps),
    }


def a3_solve_couple(thermodynamics: Any, left_x: Sequence[float],
                    right_x: Sequence[float], temperature_k: float,
                    length_um: float, time_s: float) -> float:
    """Диффузионная пара через kawin; возвращает остаточный размах по Mo."""

    from kawin.diffusion import SinglePhaseModel
    from kawin.diffusion.mesh import Cartesian1D, ProfileBuilder, StepProfile1D
    from kawin.solver import explicitEulerIterator

    length_m = float(length_um) * 1.0e-6
    independent = list(A3_ELEMENTS[1:])
    mesh = Cartesian1D(independent, [0.0, length_m], A3_NODES)
    builder = ProfileBuilder()
    builder.addBuildStep(
        StepProfile1D(length_m / 2.0, list(left_x), list(right_x)), independent
    )
    mesh.setResponseProfile(builder)
    model = SinglePhaseModel(
        mesh, list(A3_ELEMENTS), [A3_PHASE], thermodynamics=thermodynamics,
        temperature=temperature_k, record=False,
    )
    initial = np.asarray(model.getCompositions(), dtype=float).copy()
    model.solve(float(time_s), iterator=explicitEulerIterator, verbose=False,
                vIt=100000, minDtFrac=1e-10)
    final = np.asarray(model.getCompositions(), dtype=float)
    index = list(A3_ELEMENTS).index("MO")
    span_0 = float(initial[:, index].max() - initial[:, index].min())
    span_t = float(final[:, index].max() - final[:, index].min())
    del model, mesh
    gc.collect()
    return span_t / span_0 if span_0 > 0.0 else math.nan


def a3_homogenization(force: bool = False) -> dict[str, Any]:
    """Времена гомогенизации на исправленной подвижности. Считается в потомке."""

    del force
    ctx = Context()
    check, gaps = a3_diffusivity_check(ctx)
    check.to_csv(OUT / "a3_diffusivity_check.csv", **CSV_WRITE)
    log(f"A3 сверка D: |kawin/база − 1| ≤ {gaps['макс. отклонение kawin/база от 1']:.2e}, "
        f"|√(kawin)/база − 1| ≤ {gaps['макс. отклонение √(kawin)/база от 1']:.2e}")

    # Какую величину отдаёт kawin, решается измерением, а не верой: если
    # единицей оказалось отношение квадратного корня, удвоение параметра
    # осталось, и времена считать нельзя — пункт обязан упасть, а не выдать
    # числа, отличающиеся на два порядка.
    direct_ok = gaps["макс. отклонение kawin/база от 1"] < 1.0e-3
    squared_ok = gaps["макс. отклонение √(kawin)/база от 1"] < 1.0e-3
    if not direct_ok:
        raise RuntimeError(
            "kawin отдаёт не D базы: "
            f"kawin/база отклоняется на {gaps['макс. отклонение kawin/база от 1']:.3e}"
            + (", а √(kawin)/база — единица, то есть удвоение MQ не исправлено"
               if squared_ok else "")
        )

    segregation = a3_segregation()
    mo_min, mo_max = segregation["MO_min"], segregation["MO_max"]
    cr_min, cr_max = segregation["CR_min"], segregation["CR_max"]
    x_mean_cr = 0.5 * (cr_min + cr_max)
    x_mean_mo = 0.5 * (mo_min + mo_max)
    log(f"A3 профиль: ось дендрита x(CR)={cr_min:.5f}, x(MO)={mo_min:.5f} | "
        f"междендритная x(CR)={cr_max:.5f}, x(MO)={mo_max:.5f}")

    thermodynamics = a3_thermodynamics(ctx)
    rows: list[dict[str, Any]] = []
    search_rows: list[dict[str, Any]] = []

    for temperature_c in A3_T_C:
        temperature_k = temperature_c + 273.15
        mean = a3_tracer(thermodynamics, x_mean_cr, x_mean_mo, temperature_k)["MO"]
        ends = [
            a3_tracer(thermodynamics, cr, mo, temperature_k)["MO"]
            for cr, mo in ((cr_min, mo_min), (cr_max, mo_max))
        ]
        log(f"A3 {temperature_c:.0f} °C: D(Mo) при среднем составе {mean:.3e} м²/с, "
            f"на концах профиля {min(ends):.3e} … {max(ends):.3e}")

        for length_um in A3_CELLS_UM:
            length_m = length_um * 1.0e-6
            tau_s = length_m ** 2 / (math.pi ** 2 * mean)
            analytic_s = tau_s * math.log(A3_FIRST_MODE / A3_TARGET)
            slow_s = (length_m ** 2 / (math.pi ** 2 * min(ends))) * math.log(
                A3_FIRST_MODE / A3_TARGET)
            fast_s = (length_m ** 2 / (math.pi ** 2 * max(ends))) * math.log(
                A3_FIRST_MODE / A3_TARGET)

            numeric_s = math.nan
            residual = math.nan
            time_s = analytic_s
            for attempt in range(6):
                started = time.perf_counter()
                residual = a3_solve_couple(
                    thermodynamics, [cr_min, mo_min], [cr_max, mo_max],
                    temperature_k, length_um, time_s,
                )
                wall = time.perf_counter() - started
                search_rows.append({
                    "T, °C": temperature_c,
                    "ячейка, мкм": length_um,
                    "время, с": time_s,
                    "остаточная амплитуда Mo": residual,
                    "счёт, с": round(wall, 1),
                })
                pd.DataFrame(search_rows).to_csv(OUT / "a3_search_runs.csv", **CSV_WRITE)
                log(f"A3 {temperature_c:.0f} °C, L={length_um} мкм, t={time_s:.4g} с: "
                    f"остаток {residual:.4f} ({wall:.0f} с счёта)")
                if not math.isfinite(residual) or residual <= 0.0:
                    break
                if abs(residual - A3_TARGET) <= 0.004:
                    numeric_s = time_s
                    break
                fitted_tau = -time_s / math.log(residual / A3_FIRST_MODE)
                target = fitted_tau * math.log(A3_FIRST_MODE / A3_TARGET)
                if not math.isfinite(target) or target <= 0.0:
                    break
                if attempt == 5:
                    # Шесть попыток кончились, остаток на месте: это и есть
                    # полка, о которой предупреждала волна 9. Экстраполяция
                    # пишется в отдельное поле и расчётом не называется.
                    break
                time_s = target

            old = A3_WAVE9.get((temperature_c, length_um), {})
            rows.append({
                "T, °C": temperature_c,
                "ячейка (полуволна), мкм": length_um,
                "D(Mo) при среднем составе, м²/с": mean,
                "D(Mo) на концах профиля, м²/с": f"{min(ends):.3e} … {max(ends):.3e}",
                "τ = L²/π²D, с": tau_s,
                "аналитически до 5 %, с": analytic_s,
                "аналитически до 5 %, ч": analytic_s / 3600.0,
                "вилка до 5 %, ч": (
                    f"{min(slow_s, fast_s) / 3600.0:.3g} … "
                    f"{max(slow_s, fast_s) / 3600.0:.3g}"
                ),
                "численно до 5 %, с": numeric_s,
                "остаток на последнем прогоне": residual,
                "полка достигнута": bool(
                    math.isnan(numeric_s) and math.isfinite(residual)
                ),
                "волна 9: D(Mo), м²/с": old.get("D"),
                "волна 9: аналитически, с": old.get("аналитически, с"),
                "волна 9: численно, с": old.get("численно, с"),
                "волна 9: остаток": old.get("остаток"),
                "поправка D, ×": (
                    mean / old["D"] if old.get("D") else None
                ),
                "поправка времени, ×": (
                    analytic_s / old["аналитически, с"]
                    if old.get("аналитически, с") else None
                ),
            })
            pd.DataFrame(rows).to_csv(OUT / "a3_homogenization.csv", **CSV_WRITE)

    return {
        "сверка D": check.to_dict("records"),
        "отклонения сверки": gaps,
        "профиль": {
            "x(CR) ось дендрита": cr_min, "x(CR) междендритная": cr_max,
            "x(MO) ось дендрита": mo_min, "x(MO) междендритная": mo_max,
        },
        "таблица": rows,
    }


def plot_a3(table: pd.DataFrame, path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12.0, 4.6))
    for temperature_c, block in table.groupby("T, °C"):
        hours = block["аналитически до 5 %, с"].astype(float) / 3600.0
        axes[0].plot(block["ячейка (полуволна), мкм"], hours, marker="o",
                     label=f"{temperature_c:.0f} °C, волна 11A")
        old = block["волна 9: аналитически, с"].astype(float) / 3600.0
        axes[0].plot(block["ячейка (полуволна), мкм"], old, marker="s",
                     linestyle="--", linewidth=1.0,
                     label=f"{temperature_c:.0f} °C, волна 9")
    axes[0].set_xlabel("масштаб ячейки (полуволна), мкм")
    axes[0].set_ylabel("время до остатка 5 % по Mo, ч")
    axes[0].set_yscale("log")
    axes[0].grid(alpha=0.3, which="both")
    axes[0].legend(fontsize=7)
    axes[0].set_title("Гомогенизация по Mo: до и после поправки")

    by_temperature = table.drop_duplicates("T, °C")
    axes[1].semilogy(by_temperature["T, °C"],
                     by_temperature["D(Mo) при среднем составе, м²/с"].astype(float),
                     marker="o", label="волна 11A")
    axes[1].semilogy(by_temperature["T, °C"],
                     by_temperature["волна 9: D(Mo), м²/с"].astype(float),
                     marker="s", linestyle="--", label="волна 9")
    axes[1].set_xlabel("температура, °C")
    axes[1].set_ylabel("D(Mo), м²/с")
    axes[1].grid(alpha=0.3, which="both")
    axes[1].legend(fontsize=8)
    axes[1].set_title("Коэффициент диффузии молибдена в FCC_A1")

    figure.suptitle("A3. Времена гомогенизации на исправленной подвижности")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


def step_a3(force: bool = False) -> None:
    progress = load_progress()
    if progress.get("A3", {}).get("готов") and not force:
        log("A3 пропущен, посчитан ранее (--force для пересчёта)")
        return

    payload = run_child(["--a3", "1"] + (["--force"] if force else []))
    table = pd.DataFrame(payload["таблица"])
    write_csv(table, "a3_homogenization.csv")
    plot_a3(table, OUT / "a3_homogenization.png")

    plateau = table["полка достигнута"].astype(bool)
    residuals = table.loc[plateau, "остаток на последнем прогоне"].astype(float)
    summary = {
        "подпункт": "A3. Времена гомогенизации на исправленной подвижности",
        "сверка D": payload["сверка D"],
        "отклонения сверки": payload["отклонения сверки"],
        "профиль сегрегации": payload["профиль"],
        "вход профиля": A3_SEGREGATION_INPUT,
        "критерий": "остаточная неоднородность по молибдену 5 %",
        "основная величина": (
            "аналитическая оценка τ = L²/π²D с амплитудой первой моды 4/π; "
            "численный прогон kawin — справочный"
        ),
        "полка решателя осталась": bool(plateau.any()),
        "полка, диапазон остатка": (
            [round(float(residuals.min()), 4), round(float(residuals.max()), 4)]
            if not residuals.empty else None
        ),
        "полка волны 9, диапазон остатка": [0.066, 0.105],
        "таблица": table.to_dict("records"),
    }
    write_json(summary, "a3_summary.json")

    progress["A3"] = {
        "готов": True,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "температуры, °C": list(A3_T_C),
        "ячейки, мкм": list(A3_CELLS_UM),
        "узлов сетки": A3_NODES,
    }
    save_progress(progress)


# --------------------------------------------------------------------------- #
# 11D-2. Гомогенизация на реальных размерах ячейки
# --------------------------------------------------------------------------- #


def d2_readable_time(seconds: float, reference: float | None = None) -> str:
    """Время в единицах, удобных для этого размера ячейки.

    Постановка просит секунды для мелких ячеек и часы для крупных. Для самых
    крупных и часы нечитаемы: 100 мкм при 1150 °C — это больше трёх суток.

    Единицу выбирает ``reference``, а не само значение: иначе в одной строке
    таблицы аналитика вышла бы в часах, а численный счёт, который на пятую
    часть меньше, — в секундах, и строка перестала бы читаться.
    """

    if not math.isfinite(seconds):
        return "не считалось"
    scale = seconds if reference is None or not math.isfinite(reference) else reference
    if scale < 600.0:
        return f"{seconds:.0f} с"
    if scale < 172800.0:
        return f"{seconds / 3600.0:.2f} ч"
    return f"{seconds / 86400.0:.2f} сут"


def d2_numeric_time(thermodynamics: Any, profile: Mapping[str, float],
                    temperature_c: float, length_um: float,
                    start_s: float, search_rows: list[dict[str, Any]]) -> tuple[float, float]:
    """Численное время до остатка 5 % подбором. Возвращает (время, остаток).

    Подбор тот же, что в A3: прогон, затем пересчёт постоянной времени по
    полученному остатку и повтор. Шесть попыток — потолок; если остаток на
    месте, это полка решателя, и время остаётся ненайденным.
    """

    temperature_k = temperature_c + 273.15
    time_s = start_s
    residual = math.nan
    numeric_s = math.nan
    for attempt in range(6):
        started = time.perf_counter()
        residual = a3_solve_couple(
            thermodynamics,
            [profile["CR_min"], profile["MO_min"]],
            [profile["CR_max"], profile["MO_max"]],
            temperature_k, length_um, time_s,
        )
        wall = time.perf_counter() - started
        search_rows.append({
            "T, °C": temperature_c,
            "ячейка, мкм": length_um,
            "время, с": time_s,
            "остаточная амплитуда Mo": residual,
            "счёт, с": round(wall, 1),
        })
        pd.DataFrame(search_rows).to_csv(OUT / "d2_search_runs.csv", **CSV_WRITE)
        log(f"11D-2 {temperature_c:.0f} °C, L={length_um} мкм, t={time_s:.4g} с: "
            f"остаток {residual:.4f} ({wall:.0f} с счёта)")
        if not math.isfinite(residual) or residual <= 0.0:
            break
        if abs(residual - A3_TARGET) <= 0.004:
            numeric_s = time_s
            break
        fitted_tau = -time_s / math.log(residual / A3_FIRST_MODE)
        target = fitted_tau * math.log(A3_FIRST_MODE / A3_TARGET)
        if not math.isfinite(target) or target <= 0.0 or attempt == 5:
            break
        time_s = target
    return numeric_s, residual


def d2_homogenization(force: bool = False) -> dict[str, Any]:
    """Времена гомогенизации на ряде размеров ячейки. Считается в потомке."""

    del force
    ctx = Context()
    check, gaps = a3_diffusivity_check(ctx)
    check.to_csv(OUT / "a3_diffusivity_check.csv", **CSV_WRITE)
    log(f"11D-2 сверка D: |kawin/база − 1| ≤ "
        f"{gaps['макс. отклонение kawin/база от 1']:.2e}")
    if gaps["макс. отклонение kawin/база от 1"] >= 1.0e-3:
        raise RuntimeError(
            "kawin отдаёт не D базы: "
            f"kawin/база отклоняется на {gaps['макс. отклонение kawin/база от 1']:.3e}"
        )

    segregation = a3_segregation()
    profile = {
        "CR_min": segregation["CR_min"], "CR_max": segregation["CR_max"],
        "MO_min": segregation["MO_min"], "MO_max": segregation["MO_max"],
    }
    x_mean_cr = 0.5 * (profile["CR_min"] + profile["CR_max"])
    x_mean_mo = 0.5 * (profile["MO_min"] + profile["MO_max"])

    thermodynamics = a3_thermodynamics(ctx)
    rows: list[dict[str, Any]] = []
    search_rows: list[dict[str, Any]] = []

    for temperature_c in A3_T_C:
        temperature_k = temperature_c + 273.15
        mean = a3_tracer(thermodynamics, x_mean_cr, x_mean_mo, temperature_k)["MO"]
        ends = [
            a3_tracer(thermodynamics, cr, mo, temperature_k)["MO"]
            for cr, mo in ((profile["CR_min"], profile["MO_min"]),
                           (profile["CR_max"], profile["MO_max"]))
        ]
        log(f"11D-2 {temperature_c:.0f} °C: D(Mo) при среднем составе "
            f"{mean:.3e} м²/с, на концах профиля {min(ends):.3e} … {max(ends):.3e}")

        for length_um in D2_CELLS_UM:
            length_m = length_um * 1.0e-6
            tau_s = length_m ** 2 / (math.pi ** 2 * mean)
            analytic_s = tau_s * math.log(A3_FIRST_MODE / A3_TARGET)
            slow_s = (length_m ** 2 / (math.pi ** 2 * min(ends))) * math.log(
                A3_FIRST_MODE / A3_TARGET)
            fast_s = (length_m ** 2 / (math.pi ** 2 * max(ends))) * math.log(
                A3_FIRST_MODE / A3_TARGET)

            if length_um <= D2_NUMERIC_MAX_UM:
                numeric_s, residual = d2_numeric_time(
                    thermodynamics, profile, temperature_c, length_um,
                    analytic_s, search_rows,
                )
                numeric_note = "численный прогон kawin"
            else:
                numeric_s, residual = math.nan, math.nan
                numeric_note = (
                    "только аналитика: численный счёт на этом размере не "
                    "выполнялся, аналитика масштабируется как L² точно"
                )

            rows.append({
                "T, °C": temperature_c,
                "ячейка (полуволна), мкм": length_um,
                "состояние": D2_STRUCTURE[length_um],
                "D(Mo) при среднем составе, м²/с": mean,
                "τ = L²/π²D, с": tau_s,
                "аналитически до 5 %, с": analytic_s,
                "аналитически до 5 %, удобно": d2_readable_time(analytic_s),
                "вилка по профилю, удобно": (
                    f"{d2_readable_time(min(slow_s, fast_s), analytic_s)} … "
                    f"{d2_readable_time(max(slow_s, fast_s), analytic_s)}"
                ),
                "численно до 5 %, с": numeric_s,
                "численно до 5 %, удобно": d2_readable_time(numeric_s, analytic_s),
                "численно / аналитически": (
                    numeric_s / analytic_s if math.isfinite(numeric_s) else None
                ),
                "остаток на последнем прогоне": residual,
                "чем посчитано": numeric_note,
            })
            pd.DataFrame(rows).to_csv(OUT / "d2_homogenization.csv", **CSV_WRITE)

    return {
        "сверка D": check.to_dict("records"),
        "отклонения сверки": gaps,
        "профиль": {
            "x(CR) ось дендрита": profile["CR_min"],
            "x(CR) междендритная": profile["CR_max"],
            "x(MO) ось дендрита": profile["MO_min"],
            "x(MO) междендритная": profile["MO_max"],
        },
        "таблица": rows,
    }


def plot_d2(table: pd.DataFrame, path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))

    for temperature_c, block in table.groupby("T, °C"):
        block = block.sort_values("ячейка (полуволна), мкм")
        axes[0].plot(
            block["ячейка (полуволна), мкм"].astype(float),
            block["аналитически до 5 %, с"].astype(float),
            marker="o", label=f"{temperature_c:.0f} °C, аналитика",
        )
        numeric = block.dropna(subset=["численно до 5 %, с"])
        if not numeric.empty:
            axes[0].plot(
                numeric["ячейка (полуволна), мкм"].astype(float),
                numeric["численно до 5 %, с"].astype(float),
                marker="s", linestyle="none", markersize=5,
                label=f"{temperature_c:.0f} °C, численно",
            )
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("масштаб ячейки (полуволна), мкм")
    axes[0].set_ylabel("время до остатка 5 % по Mo, с")
    axes[0].grid(alpha=0.3, which="both")
    axes[0].legend(fontsize=7)
    axes[0].set_title("Время гомогенизации против размера ячейки")

    # Второй график — то же в часах и линейно по размеру: именно так вопрос
    # выглядит у технолога, и именно здесь видно, что 100 мкм не про печку.
    for temperature_c, block in table.groupby("T, °C"):
        block = block.sort_values("ячейка (полуволна), мкм")
        axes[1].plot(
            block["ячейка (полуволна), мкм"].astype(float),
            block["аналитически до 5 %, с"].astype(float) / 3600.0,
            marker="o", label=f"{temperature_c:.0f} °C",
        )
    axes[1].axhline(8.0, color="grey", linestyle="--", linewidth=1.0)
    axes[1].annotate("рабочая смена, 8 ч", (0.6, 8.5), fontsize=7)
    axes[1].set_xlabel("масштаб ячейки (полуволна), мкм")
    axes[1].set_ylabel("время до остатка 5 % по Mo, ч")
    axes[1].set_yscale("log")
    axes[1].grid(alpha=0.3, which="both")
    axes[1].legend(fontsize=8)
    axes[1].set_title("То же в часах")

    figure.suptitle("11D-2. Гомогенизация по молибдену на реальных размерах ячейки")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


def d2_drop_squared_column() -> bool:
    """Убрать «√(kawin)/база» из готовой сводки A3.

    Колонку сняли из таблицы сверки, и оставлять её в ``a3_summary.json``
    нельзя: файл и CSV разошлись бы, а число там заведомо мусорное. Значения
    остальных полей не трогаются — расчёт детерминированный, и пересчитывать
    A3 ради удаления одного ключа не требуется.
    """

    path = OUT / "a3_summary.json"
    if not path.is_file():
        return False
    payload = json.loads(path.read_text("utf-8"))
    changed = False
    for record in payload.get("сверка D", []):
        if "√(kawin) / база" in record:
            record.pop("√(kawin) / база")
            changed = True
    gaps = payload.get("отклонения сверки", {})
    if "макс. отклонение √(kawin)/база от 1" in gaps:
        gaps.pop("макс. отклонение √(kawin)/база от 1")
        changed = True
    if changed:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False), "utf-8"
        )
        log("из a3_summary.json убрана колонка √(kawin)/база")
    return changed


def step_d2(force: bool = False) -> None:
    progress = load_progress()
    if progress.get("11D-2", {}).get("готов") and not force:
        log("11D-2 пропущен, посчитан ранее (--force для пересчёта)")
        return

    payload = run_child(["--d2", "1"] + (["--force"] if force else []))
    table = pd.DataFrame(payload["таблица"])
    write_csv(table, "d2_homogenization.csv")
    plot_d2(table, OUT / "d2_homogenization.png")
    d2_drop_squared_column()

    # Проверка масштабирования: аналитика идёт как L² по построению, а
    # численный счёт — нет, поэтому отношение «численно/аналитически» обязано
    # быть постоянным по размеру. Разъехалось — численный счёт где-то не сошёлся.
    ratios = table["численно / аналитически"].dropna().astype(float)
    scaling = {
        "точек с численным счётом": int(len(ratios)),
        "численно/аналитически, мин": round(float(ratios.min()), 4) if len(ratios) else None,
        "численно/аналитически, макс": round(float(ratios.max()), 4) if len(ratios) else None,
        "разброс отношения, %": (
            round(100.0 * (float(ratios.max()) / float(ratios.min()) - 1.0), 2)
            if len(ratios) else None
        ),
    }

    by_state: list[dict[str, Any]] = []
    for length_um in D2_CELLS_UM:
        block = table[table["ячейка (полуволна), мкм"].astype(float) == length_um]
        entry: dict[str, Any] = {
            "ячейка (полуволна), мкм": length_um,
            "состояние": D2_STRUCTURE[length_um],
        }
        for record in block.to_dict("records"):
            entry[f"{record['T, °C']:.0f} °C, аналитика"] = (
                record["аналитически до 5 %, удобно"]
            )
            entry[f"{record['T, °C']:.0f} °C, численно"] = (
                record["численно до 5 %, удобно"]
            )
        by_state.append(entry)

    summary = {
        "подпункт": "11D-2. Гомогенизация на реальных размерах ячейки",
        "температуры, °C": list(A3_T_C),
        "ячейки (полуволна), мкм": list(D2_CELLS_UM),
        "узлов сетки": A3_NODES,
        "критерий": "остаточная неоднородность по молибдену 5 %",
        "профиль сегрегации": payload["профиль"],
        "вход профиля": A3_SEGREGATION_INPUT,
        "сверка D": payload["сверка D"],
        "отклонения сверки": payload["отклонения сверки"],
        "численный предел, мкм": D2_NUMERIC_MAX_UM,
        "почему счёт не дорожает с размером": (
            "явная схема держит dt ~ dx², а число узлов одно и то же, поэтому "
            "число шагов до момента t ~ L²/D равно квадрату числа узлов и от L "
            "не зависит"
        ),
        "масштабирование": scaling,
        "таблица по размерам": by_state,
        "таблица": table.to_dict("records"),
        "оговорка": (
            "Аналитическая оценка τ = L²/π²D с амплитудой первой моды 4/π — "
            "основная величина; численный прогон kawin справочный. Размер "
            "ячейки указывать обязательно: время идёт как квадрат размера, и "
            "между лазерной печатью и литой заготовкой разница в сотни раз."
        ),
    }
    write_json(summary, "d2_summary.json")

    progress["11D-2"] = {
        "готов": True,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "температуры, °C": list(A3_T_C),
        "ячейки, мкм": list(D2_CELLS_UM),
        "узлов сетки": A3_NODES,
        "численно до, мкм": D2_NUMERIC_MAX_UM,
    }
    save_progress(progress)


# --------------------------------------------------------------------------- #
# A4. Шейль с инструментовкой
# --------------------------------------------------------------------------- #


def scheil_key(mole: Mapping[str, float], step_k: float,
               excluded: Sequence[str], pdens: int = A4_PDENS) -> str:
    """Ключ кэша прогона Шейля.

    Плотность выборки дописывается в имя только когда она не базовая: иначе
    ключи волн A4 и 11D-3 сменились бы, и семьдесят минут уже посчитанного
    пришлось бы считать заново.
    """

    suffix = "_".join(sorted(excluded)) or "full"
    tail = "" if int(pdens) == A4_PDENS else f"_pdens{int(pdens)}"
    return f"scheil11_{composition_id(mole)}_step{step_k:g}_{suffix}{tail}"


def run_scheil(
    ctx: Context,
    mole: Mapping[str, float],
    label: str,
    step_k: float = A4_STEP_K,
    excluded: Sequence[str] = (),
    pdens: int = A4_PDENS,
) -> tuple[Any, dict[str, Any]]:
    """Расчёт Шейля с записью полного протокола солвера.

    Протокол пишется потому, что вопрос A4 — «почему расчёт останавливается»,
    а ``SolidificationResult`` несёт только флаг ``converged``. Причину
    останова печатает сам ``scheil`` при ``verbose=True``, и эти строки —
    единственное прямое свидетельство; они сохраняются рядом с результатом.
    """

    import io
    from contextlib import redirect_stdout

    import scheil
    from pycalphad import variables as v

    CACHE.mkdir(parents=True, exist_ok=True)
    key = scheil_key(mole, step_k, excluded, pdens)
    path = CACHE / f"{key}.json"
    if path.is_file():
        payload = json.loads(path.read_text("utf-8"))
        log(f"{label}: Шейль взят из кэша ({payload['шагов']} шагов)")
        return scheil.SolidificationResult.from_dict(payload["result"]), payload

    phases = [name for name in ctx.phases if name not in set(excluded)]
    # Ликвидус и, значит, точка старта берутся при базовой плотности выборки
    # при любом ``pdens`` прогона. A1 показал, что от плотности ликвидус не
    # зависит (50…500 дают одно и то же с точностью 0,1 K), а одинаковый старт
    # обязателен: иначе сетки температур у прогонов разъедутся и сравнивать
    # точку останова станет не с чем.
    liquidus, _calls = a1_liquidus(ctx, mole, A4_PDENS, EquilibriumCache(A4_PDENS))
    start_k = liquidus + A4_START_OVER_LIQUIDUS_K + 273.15
    composition = {
        v.X(element): value for element, value in independent_x(mole).items()
    }

    log(f"{label}: ликвидус {liquidus:.2f} °C, старт "
        f"{start_k - 273.15:.2f} °C, шаг {step_k} K, pdens {pdens}, "
        f"исключено {list(excluded) or 'ничего'}")
    started = time.perf_counter()
    protocol = io.StringIO()
    with redirect_stdout(protocol):
        result = scheil.simulate_scheil_solidification(
            ctx.db, list(COMPONENTS), phases, composition, start_k,
            step_temperature=step_k,
            liquid_phase_name="LIQUID",
            eq_kwargs={"calc_opts": {"pdens": int(pdens)}},
            stop=A4_STOP_LIQUID,
            verbose=True,
        )
    seconds = time.perf_counter() - started

    protocol_lines = protocol.getvalue().splitlines()
    protocol_path = OUT / f"a4_protocol_{key}.log"
    OUT.mkdir(parents=True, exist_ok=True)
    protocol_path.write_text("\n".join(protocol_lines), "utf-8")

    payload = {
        "result": result.to_dict(),
        "метка": label,
        "ликвидус, °C": liquidus,
        "старт, °C": start_k - 273.15,
        "шаг, K": float(step_k),
        "pdens": int(pdens),
        "исключённые фазы": list(excluded),
        "шагов": len(result.temperatures),
        "секунд": seconds,
        "протокол": protocol_path.name,
        "хвост протокола": protocol_lines[-12:],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
    log(f"{label}: Шейль {len(result.temperatures)} шагов за {seconds / 60.0:.1f} мин, "
        f"сошёлся={result.converged}")
    return result, payload


def last_real_index(result: Any) -> int:
    """Индекс последней **посчитанной** точки кривой.

    ``scheil`` дописывает в конец искусственную точку с долей твёрдого ровно
    1,0, когда расчёт оборвался с нерастворённым остатком жидкости: остаток
    объявляется твёрдым одним куском. Эта точка — не результат расчёта, и все
    величины A4 считаются без неё.
    """

    solid = [float(value) for value in result.fraction_solid]
    if len(solid) >= 2 and solid[-1] == 1.0 and solid[-2] < 1.0:
        return len(solid) - 2
    return len(solid) - 1


def scheil_curve(result: Any) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cut = last_real_index(result)
    for index, temperature in enumerate(result.temperatures):
        row: dict[str, Any] = {
            "T, °C": float(temperature) - 273.15,
            "доля твёрдого": float(result.fraction_solid[index]),
            "точка посчитана": index <= cut,
        }
        for element, values in result.x_liquid.items():
            row[f"x(LIQUID,{element})"] = float(values[index])
        for phase, values in sorted(result.cum_phase_amounts.items()):
            if float(values[-1]) > 1.0e-9:
                row[f"накоплено {phase}"] = float(values[index])
        rows.append(row)
    return pd.DataFrame(rows)


def temperature_at_fraction(curve: pd.DataFrame, target: float) -> float | None:
    """Температура при доле твёрдого ``target``, только по посчитанным точкам.

    Возвращает ``None``, если ``target`` посчитанными точками не достигнут:
    интерполировать внутрь скачка, которым солвер сбрасывает нерастворённый
    остаток, значит выдать за расчёт то, чего не считали.
    """

    real = curve[curve["точка посчитана"]]
    solid = real["доля твёрдого"].to_numpy(dtype=float)
    temperature = real["T, °C"].to_numpy(dtype=float)
    if len(solid) == 0 or target > float(solid.max()):
        return None
    for index in range(1, len(solid)):
        low, high = solid[index - 1], solid[index]
        if low <= target <= high and high != low:
            return float(
                temperature[index - 1]
                + (target - low) * (temperature[index] - temperature[index - 1])
                / (high - low)
            )
    return None


def window_coverage(
    window: tuple[float, float],
    covered: Sequence[float],
    steps: Sequence[float],
    max_solid: float,
    min_solid: float,
) -> dict[str, Any]:
    """Покрыто ли окно доли твёрдого посчитанными точками.

    11J-3. Прежний критерий требовал попадания точки ровно на границу окна с
    точностью 1e-6. Доли твёрдого у точек расчёта дискретны и с круглыми
    числами 0,85 и 0,95 никак не связаны, поэтому флаг не мог стать истинным
    ни при каком расчёте и ничего не сообщал.

    Осмысленный критерий: ближайшие к границам посчитанные точки лежат внутри
    окна и отстоят от своей границы не дальше чем на шаг по доле твёрдого.
    Проверяется он через соседей: если по обе стороны окна есть посчитанные
    точки, то между границей и ближайшей внутренней точкой умещается меньше
    одного шага, и окно покрыто настолько, насколько вообще позволяет шаг
    расчёта. Мерить зазор медианным шагом по всему окну нельзя: шаг по доле
    твёрдого вдоль затвердевания меняется в разы, и у нижней границы он
    крупнее среднего.

    Само значение Kou прежний флаг не портил: максимум берётся по тем точкам,
    что есть, и от флага не зависит.
    """

    if not covered:
        return {
            "окно покрыто полностью": False,
            "зазор у нижней границы": None,
            "зазор у верхней границы": None,
            "шаг у нижней границы": None,
            "шаг у верхней границы": None,
            "почему не покрыто": (
                "посчитанных точек в окне нет: посчитанные доли твёрдого лежат "
                f"от {min_solid:.4f} до {max_solid:.4f}"
            ),
        }

    low_gap = float(min(covered)) - window[0]
    high_gap = window[1] - float(max(covered))
    low_step = abs(float(steps[0])) if len(steps) else None
    high_step = abs(float(steps[-1])) if len(steps) else None

    # Точность 1e-9 — на округление double, а не запас: обе проверки
    # спрашивают о наличии соседа, а не о попадании в границу.
    below = min_solid <= window[0] + 1.0e-9
    above = max_solid >= window[1] - 1.0e-9

    reason = None
    if not above:
        reason = (
            f"расчёт остановился на доле твёрдого {max_solid:.4f}, не дойдя до "
            f"верхней границы окна {window[1]:g}: зазор {high_gap:.4f}"
        )
    elif not below:
        reason = (
            f"первая посчитанная точка на доле твёрдого {min_solid:.4f} уже выше "
            f"нижней границы окна {window[0]:g}"
        )

    return {
        "окно покрыто полностью": bool(below and above),
        "зазор у нижней границы": round(low_gap, 6),
        "зазор у верхней границы": round(high_gap, 6),
        "шаг у нижней границы": round(low_step, 6) if low_step else None,
        "шаг у верхней границы": round(high_step, 6) if high_step else None,
        "почему не покрыто": reason,
    }


def kou_on_window(
    curve: pd.DataFrame, window: tuple[float, float]
) -> dict[str, Any]:
    """Критерий Kou |dT/d(fs^0,5)| на заданном окне доли твёрдого.

    Возвращает и фактические границы окна: если посчитанные точки не покрывают
    заявленное окно целиком, сравнивать значения разной ширины нельзя, и
    границы должны ехать вместе с числом.
    """

    real = curve[curve["точка посчитана"]]
    solid = real["доля твёрдого"].to_numpy(dtype=float)
    temperature = real["T, °C"].to_numpy(dtype=float)
    root = np.sqrt(np.clip(solid, 0.0, 1.0))

    rows: list[dict[str, Any]] = []
    steps: list[float] = []
    peak = 0.0
    for index in range(1, len(solid)):
        if not (window[0] <= solid[index] <= window[1]):
            continue
        d_root = root[index] - root[index - 1]
        if abs(d_root) < 1.0e-12:
            continue
        value = abs((temperature[index] - temperature[index - 1]) / d_root)
        rows.append({
            "доля твёрдого": float(solid[index]),
            "T, °C": float(temperature[index]),
            "|dT/d(fs^0.5)|, K": value,
        })
        steps.append(float(solid[index] - solid[index - 1]))
        peak = max(peak, value)

    table = pd.DataFrame(rows)
    covered = [row["доля твёрдого"] for row in rows]
    coverage = window_coverage(
        window, covered, steps,
        float(solid.max()) if len(solid) else 0.0,
        float(solid.min()) if len(solid) else 1.0,
    )
    return {
        "заявленное окно": [window[0], window[1]],
        "фактическое окно": (
            [round(min(covered), 5), round(max(covered), 5)] if covered else None
        ),
        **coverage,
        "точек в окне": len(rows),
        "максимум, K": round(peak, 1) if rows else None,
        "таблица": table,
    }


def protocol_lines(payload: Mapping[str, Any]) -> list[str]:
    """Строки протокола солвера: файл целиком, иначе сохранённый хвост."""

    name = payload.get("протокол")
    if name:
        path = OUT / str(name)
        if path.is_file():
            return [line for line in path.read_text("utf-8").splitlines() if line.strip()]
    return [line for line in payload.get("хвост протокола", []) if line.strip()]


def found_phases(line: str) -> list[str] | None:
    """Набор фаз из строки протокола ``... (Found <набор>) ...``.

    Возвращает ``None``, когда строка не того вида. Пустой список — это
    ``Found set()``: солвер не нашёл вообще ничего.
    """

    marker = "(Found "
    start = line.find(marker)
    if start < 0:
        return None
    start += len(marker)
    depth = 1
    end = start
    while end < len(line) and depth:
        if line[end] == "(":
            depth += 1
        elif line[end] == ")":
            depth -= 1
            if depth == 0:
                break
        end += 1
    body = line[start:end].strip()
    if body in ("set()", "frozenset()", "{}", ""):
        return []
    return sorted(
        part.strip().strip("'\"")
        for part in body.strip("{}").split(",")
        if part.strip()
    )


def stop_reason(result: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Причина останова расчёта Шейля, различённая по протоколу солвера.

    11J-3. Прежняя редакция писала «отказ солвера на инвариантном равновесии»
    на всякий обрыв. Это две разные вещи, и протокол их различает:

    * ``Found {'FCC_A1', …}`` — жидкости нет, но твёрдые фазы найдены. Это
      инвариантное равновесие: остаток жидкости израсходован реакцией, и
      расчёт упирается в физику;
    * ``Found set()`` — не найдено ни одной фазы. Равновесие не сошлось
      вообще, и это отказ численного метода, а не свойство сплава.

    ``scheil`` в обоих случаях дробит шаг и, исчерпав предел дробления,
    останавливается с ``converged=False``, поэтому по одному флагу их не
    различить — только по протоколу.
    """

    cut = last_real_index(result)
    truncated = cut != len(result.fraction_solid) - 1
    residual = 1.0 - float(result.fraction_solid[cut])
    lines = protocol_lines(payload)
    tail = lines[-4:]

    failures = [line for line in lines if "No liquid phase found" in line]
    last_failure = failures[-1] if failures else None
    phases = found_phases(last_failure) if last_failure else None
    exhausted = bool(
        lines and "Maximum step size reduction exceeded" in lines[-1]
    )

    mechanism = (
        "исчерпан предел дробления шага (scheil: MAXIMUM_STEP_SIZE_REDUCTION)"
        if exhausted else "цикл завершился без сообщения о пределе дробления"
    )

    if bool(result.converged):
        reason = "доля жидкости ниже порога stop"
        detail = f"NL < {A4_STOP_LIQUID:g}"
    elif phases is None:
        reason = "останов без строки об отсутствии жидкости в протоколе"
        detail = (
            "протокол не содержит ни одной строки «No liquid phase found»; "
            "причину по нему установить нельзя"
        )
    elif phases == []:
        reason = "отказ сходимости: равновесие не найдено"
        detail = (
            "в последнем неудачном равновесии не найдено ни одной фазы "
            "(Found set()) — это отказ численного метода, а не инвариантная "
            f"реакция; {mechanism}; остаток жидкости объявлен твёрдым одним "
            "куском"
        )
    else:
        reason = "инвариантное равновесие: найдены только твёрдые фазы"
        detail = (
            "в последнем неудачном равновесии жидкости нет, но твёрдые фазы "
            f"найдены ({', '.join(phases)}) — остаток израсходован реакцией; "
            f"{mechanism}"
        )

    return {
        "причина останова": reason,
        "пояснение": detail,
        "флаг converged": bool(result.converged),
        "фазы в последнем неудачном равновесии": (
            "строки нет" if phases is None else (phases or "ни одной")
        ),
        "неудачных равновесий в протоколе": len(failures),
        "механизм останова": mechanism,
        "остаток дописан искусственной точкой": bool(truncated),
        "неразрешённый остаток жидкости, доля": round(residual, 6),
        "последние строки протокола": tail,
    }


def instrumented_summary(
    result: Any, payload: Mapping[str, Any], curve: pd.DataFrame
) -> dict[str, Any]:
    """Сводка одного прогона Шейля с честными именами полей."""

    cut = last_real_index(result)
    fs_last = float(result.fraction_solid[cut])
    t_last = float(result.temperatures[cut]) - 273.15
    liquidus = float(payload["ликвидус, °C"])

    marks: dict[str, Any] = {}
    for mark in A4_FS_MARKS:
        value = temperature_at_fraction(curve, mark)
        marks[f"T при fs={mark:g}, °C"] = (
            "не достигнуто" if value is None else round(value, 2)
        )

    declared = kou_on_window(curve, A4_KOU_DECLARED_WINDOW)
    fixed = kou_on_window(curve, A4_KOU_FIXED_WINDOW)
    declared_bounds = declared["фактическое окно"]
    declared_name = (
        f"Kou на фактическом окне fs {declared_bounds[0]:.3f}…{declared_bounds[1]:.3f}, K"
        if declared_bounds else "Kou на фактическом окне fs 0,90…0,99, K"
    )

    summary: dict[str, Any] = {
        "состав": payload["метка"],
        "исключённые фазы": payload["исключённые фазы"] or "нет",
        "шаг по температуре, K": payload["шаг, K"],
        "pdens": int(payload.get("pdens", A4_PDENS)),
        "равновесный ликвидус, °C": round(liquidus, 2),
        "шагов": int(payload["шагов"]),
        "доля твёрдого на последней посчитанной точке": round(fs_last, 6),
        "T последней посчитанной точки, °C": round(t_last, 3),
        "неразрешённый остаток жидкости, доля": round(1.0 - fs_last, 6),
        **marks,
        declared_name: declared["максимум, K"],
        "Kou на фактическом окне: точек": declared["точек в окне"],
        "Kou на фактическом окне: заявленное окно покрыто": declared["окно покрыто полностью"],
        "Kou на фактическом окне: почему не покрыто": declared["почему не покрыто"],
        (
            f"Kou на фиксированном окне fs {A4_KOU_FIXED_WINDOW[0]:g}…"
            f"{A4_KOU_FIXED_WINDOW[1]:g}, K"
        ): fixed["максимум, K"],
        "Kou на фиксированном окне: точек": fixed["точек в окне"],
        "Kou на фиксированном окне: покрыто полностью": fixed["окно покрыто полностью"],
        "Kou на фиксированном окне: почему не покрыто": fixed["почему не покрыто"],
        "Kou на фиксированном окне: зазоры у границ": [
            fixed["зазор у нижней границы"], fixed["зазор у верхней границы"],
        ],
        "интервал по Шейлю до последней посчитанной точки, K": round(
            liquidus - t_last, 2
        ),
        "интервал — оценка снизу": True,
        "секунд": round(float(payload["секунд"]), 1),
        **stop_reason(result, payload),
    }
    return summary


def terminal_phases(result: Any) -> pd.DataFrame:
    """Фазы последних 5 % затвердевания — отдельно посчитанное и досыпанное.

    Разделение обязательно: у σ в этом сплаве вся «вторая половина» приходится
    на искусственную точку сброса остатка, и общая сумма без такого деления
    выглядит вдвое больше посчитанного.
    """

    cut = last_real_index(result)
    truncated = cut != len(result.fraction_solid) - 1
    solid = np.asarray(result.fraction_solid, dtype=float)
    temperatures = np.asarray(result.temperatures, dtype=float) - 273.15

    rows: list[dict[str, Any]] = []
    for phase, amounts in sorted(result.phase_amounts.items()):
        values = np.asarray(amounts, dtype=float)
        real = values[: cut + 1]
        dumped = float(values[cut + 1:].sum()) if truncated else 0.0
        if float(values.sum()) <= 1.0e-9:
            continue
        tail_mask = solid[: cut + 1] >= 0.95
        appearing = [
            temperatures[index] for index in range(cut + 1) if values[index] > 1.0e-9
        ]
        rows.append({
            "фаза": phase,
            "посчитано за затвердевание": float(real.sum()),
            "из них после fs=0,95": float(real[tail_mask].sum()),
            "досыпано при сбросе остатка": dumped,
            "T появления, °C": max(appearing) if appearing else math.nan,
            "T последнего роста, °C": min(appearing) if appearing else math.nan,
        })
    return pd.DataFrame(rows)


def plot_a4(curve: pd.DataFrame, summary: Mapping[str, Any], path: Path) -> None:
    real = curve[curve["точка посчитана"]]
    figure, axes = plt.subplots(1, 2, figsize=(13.0, 4.8))

    axes[0].plot(real["доля твёрдого"], real["T, °C"], linewidth=1.8,
                 label="посчитано")
    dumped = curve[~curve["точка посчитана"]]
    if not dumped.empty:
        bridge = pd.concat([real.tail(1), dumped])
        axes[0].plot(bridge["доля твёрдого"], bridge["T, °C"], "--",
                     color="tab:red", linewidth=1.4,
                     label="сброс нерастворённого остатка")
    fs_last = float(summary["доля твёрдого на последней посчитанной точке"])
    axes[0].axvline(fs_last, color="grey", linestyle=":", linewidth=0.9)
    axes[0].annotate(
        f"последняя посчитанная точка\nfs={fs_last:.4f}, "
        f"{summary['T последней посчитанной точки, °C']:.1f} °C",
        (fs_last, float(summary["T последней посчитанной точки, °C"])),
        fontsize=7, ha="right", va="bottom",
    )
    axes[0].set_xlabel("доля твёрдого")
    axes[0].set_ylabel("температура, °C")
    axes[0].set_title("Затвердевание по Шейлю")
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=8)

    declared = kou_on_window(curve, A4_KOU_DECLARED_WINDOW)["таблица"]
    fixed = kou_on_window(curve, A4_KOU_FIXED_WINDOW)["таблица"]
    if not declared.empty:
        axes[1].plot(declared["доля твёрдого"], declared["|dT/d(fs^0.5)|, K"],
                     marker="o", markersize=3, linewidth=1.5,
                     label="фактическое окно (заявлено 0,90…0,99)")
    if not fixed.empty:
        axes[1].plot(fixed["доля твёрдого"], fixed["|dT/d(fs^0.5)|, K"],
                     marker="s", markersize=3, linewidth=1.2, linestyle="--",
                     label="фиксированное окно 0,85…0,95")
    axes[1].set_xlabel("доля твёрдого")
    axes[1].set_ylabel("|dT/d(fs^0,5)|, K")
    axes[1].set_title("Критерий Kou")
    axes[1].grid(alpha=0.3)
    axes[1].legend(fontsize=8)

    figure.suptitle("A4. Хвост Шейля: что посчитано и что досыпано")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


def a4_scheil(force: bool = False) -> dict[str, Any]:
    """Головной прогон B1 плюс попытки пройти дальше. Считается в потомке."""

    del force
    ctx = Context()
    mole = wt_to_mole(ctx, full_wt())

    trials: list[dict[str, Any]] = []
    head_curve: pd.DataFrame | None = None
    head_summary: dict[str, Any] | None = None
    head_result: Any = None

    for label, excluded in A4_EXCLUSION_TRIALS:
        result, payload = run_scheil(ctx, mole, f"контрольный состав, {label}",
                                     A4_STEP_K, excluded)
        curve = scheil_curve(result)
        summary = instrumented_summary(result, payload, curve)
        summary["попытка"] = label
        trials.append(summary)
        # Каждая попытка уходит на диск сразу: следующая может не закончиться.
        pd.DataFrame(trials).to_csv(OUT / "a4_stop_trials.csv", **CSV_WRITE)
        if not excluded:
            head_curve, head_summary, head_result = curve, summary, result
        gc.collect()

    assert head_curve is not None and head_summary is not None

    head_curve.to_csv(OUT / "b1_scheil_curve.csv", **CSV_WRITE)
    kou_on_window(head_curve, A4_KOU_DECLARED_WINDOW)["таблица"].to_csv(OUT / "b1_kou_actual.csv", **CSV_WRITE)
    kou_on_window(head_curve, A4_KOU_FIXED_WINDOW)["таблица"].to_csv(OUT / "b1_kou_fixed.csv", **CSV_WRITE)
    terminal_phases(head_result).to_csv(OUT / "b1_terminal_phases.csv", **CSV_WRITE)
    plot_a4(head_curve, head_summary, OUT / "b1_solidification.png")

    return {"головной прогон": head_summary, "попытки пройти дальше": trials}


def step_a4(force: bool = False) -> None:
    progress = load_progress()
    if progress.get("A4", {}).get("готов") and not force:
        log("A4 пропущен, посчитан ранее (--force для пересчёта)")
        return

    payload = run_child(["--a4", "1"] + (["--force"] if force else []))
    head = payload["головной прогон"]
    trials = pd.DataFrame(payload["попытки пройти дальше"])
    write_csv(trials, "a4_stop_trials.csv")
    write_json(head, "b1_summary.json")

    baseline = trials[trials["попытка"] == "без исключений"].iloc[0]
    moved = [
        {
            "попытка": row["попытка"],
            "доля твёрдого на останове": row["доля твёрдого на последней посчитанной точке"],
            "сдвиг против базового прогона": round(
                float(row["доля твёрдого на последней посчитанной точке"])
                - float(baseline["доля твёрдого на последней посчитанной точке"]), 6
            ),
            "причина останова": row["причина останова"],
        }
        for _, row in trials.iterrows()
    ]

    summary = {
        "подпункт": "A4. Хвост Шейля: инструментовка и честные метрики",
        "шаг по температуре, K": A4_STEP_K,
        "порог останова по доле жидкости": A4_STOP_LIQUID,
        "головной прогон": head,
        "предел метода": moved,
        "вывод по интервалу": (
            "Интервал кристаллизации по Шейлю — оценка снизу: последние "
            f"{100.0 * float(head['неразрешённый остаток жидкости, доля']):.1f} % "
            "жидкости не разрешены, а именно они отвечают за легкоплавкие плёнки "
            "по границам."
        ),
    }
    write_json(summary, "a4_summary.json")

    progress["A4"] = {
        "готов": True,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "шаг, K": A4_STEP_K,
        "pdens": A4_PDENS,
        "режим набора фаз": "все фазы",
    }
    save_progress(progress)


# --------------------------------------------------------------------------- #
# 11D-3. Сверка профиля сегрегации с входом A3
# --------------------------------------------------------------------------- #


# Насколько профиль нового расчёта может разойтись со старым, чтобы времена
# гомогенизации не пересчитывать. Порог назван постановкой 11D-3.
D3_PROFILE_TOLERANCE = 0.10


def d3_solid_segregation(result: Any, phase: str = A3_PHASE) -> dict[str, float]:
    """Размах сегрегации в твёрдой фазе по посчитанным точкам расчёта Шейля.

    Искусственная точка сброса остатка отбрасывается: состав фазы в ней —
    не результат расчёта, а состав последнего сошедшегося равновесия,
    переписанный ещё раз.
    """

    cut = last_real_index(result)
    compositions = result.phase_compositions.get(phase)
    if not compositions:
        raise RuntimeError(f"В расчёте Шейля нет составов фазы {phase}.")
    span: dict[str, float] = {}
    for element in ("MO", "CR"):
        values = np.asarray(compositions[element], dtype=float)[: cut + 1]
        values = values[np.isfinite(values) & (values > 0.0)]
        if values.size == 0:
            raise RuntimeError(f"В фазе {phase} нет положительных значений {element}.")
        span[f"{element}_min"] = float(values.min())
        span[f"{element}_max"] = float(values.max())
        span[f"{element}_точек"] = float(values.size)
    return span


def step_d3(force: bool = False) -> None:
    """Сверка нового профиля сегрегации с тем, что взят входом A3 и 11D-2.

    Отдельный шаг, потому что считать здесь нечего: расчёт Шейля уже лежит в
    кэше A4, и повторять его ради одной таблицы незачем.
    """

    progress = load_progress()
    if progress.get("11D-3", {}).get("готов") and not force:
        log("11D-3 пропущен, посчитан ранее (--force для пересчёта)")
        return

    ctx = Context()
    mole = wt_to_mole(ctx, full_wt())
    result, payload = run_scheil(ctx, mole, "контрольный состав, без исключений",
                                 A4_STEP_K, ())
    fresh = d3_solid_segregation(result)
    old = a3_segregation()

    rows: list[dict[str, Any]] = []
    worst = 0.0
    for element in ("MO", "CR"):
        old_span = old[f"{element}_max"] - old[f"{element}_min"]
        new_span = fresh[f"{element}_max"] - fresh[f"{element}_min"]
        gap = abs(new_span - old_span) / old_span if old_span > 0.0 else math.inf
        worst = max(worst, gap)
        rows.append({
            "элемент": element,
            "вход A3: ось дендрита": old[f"{element}_min"],
            "вход A3: междендритная": old[f"{element}_max"],
            "вход A3: размах": old_span,
            "новый расчёт: ось дендрита": fresh[f"{element}_min"],
            "новый расчёт: междендритная": fresh[f"{element}_max"],
            "новый расчёт: размах": new_span,
            "новый расчёт: точек": int(fresh[f"{element}_точек"]),
            "расхождение размаха, %": round(100.0 * gap, 2),
        })
    table = pd.DataFrame(rows)
    write_csv(table, "d3_segregation_check.csv")

    recompute = worst > D3_PROFILE_TOLERANCE
    summary = {
        "подпункт": "11D-3. Сверка профиля сегрегации с входом A3 и 11D-2",
        "источник нового профиля": (
            f"расчёт Шейля шагом {A4_STEP_K} K, только посчитанные точки, "
            f"фаза {A3_PHASE}"
        ),
        "источник старого профиля": A3_SEGREGATION_INPUT,
        "порог пересчёта, доля": D3_PROFILE_TOLERANCE,
        "наибольшее расхождение размаха, %": round(100.0 * worst, 2),
        "пересчитывать 11D-2": bool(recompute),
        "таблица": table.to_dict("records"),
    }
    write_json(summary, "d3_segregation_check.json")
    log(f"11D-3 профиль: наибольшее расхождение размаха {100.0 * worst:.2f} %, "
        f"пересчёт 11D-2 {'нужен' if recompute else 'не нужен'}")

    progress["11D-3"] = {
        "готов": True,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "наибольшее расхождение размаха, %": round(100.0 * worst, 2),
        "пересчёт 11D-2": bool(recompute),
    }
    save_progress(progress)


# --------------------------------------------------------------------------- #
# 11J-2. Плотность выборки против предела метода
# --------------------------------------------------------------------------- #


def j2_dense(force: bool = False) -> dict[str, Any]:
    """Головной прогон при pdens 300 и 500. Считается в потомке.

    Базовый прогон при pdens 100 берётся готовым из кэша: считать его заново
    незачем, а сравнивать надо именно с ним.
    """

    del force
    ctx = Context()
    mole = wt_to_mole(ctx, full_wt())

    rows: list[dict[str, Any]] = []
    curves: dict[str, list[dict[str, Any]]] = {}
    skipped: list[dict[str, Any]] = []

    base_result, base_payload = run_scheil(
        ctx, mole, "контрольный состав, pdens 100", A4_STEP_K, (), A4_PDENS
    )
    base_curve = scheil_curve(base_result)
    base_summary = instrumented_summary(base_result, base_payload, base_curve)
    base_summary["попытка"] = "pdens 100 (базовый, из кэша)"
    rows.append(base_summary)
    curves["pdens 100"] = base_curve.to_dict("records")
    pd.DataFrame(rows).to_csv(OUT / "j2_pdens_runs.csv", **CSV_WRITE)
    gc.collect()

    import psutil

    spent = 0.0
    for pdens in J2_PDENS:
        cached = (CACHE / f"{scheil_key(mole, A4_STEP_K, (), pdens)}.json").is_file()
        free = psutil.virtual_memory().available / 1024.0 ** 3
        if not cached and free < J2_MIN_FREE_GIB:
            skipped.append({
                "pdens": pdens,
                "причина": (
                    f"свободной физической памяти {free:.1f} ГиБ при требуемых "
                    f"{J2_MIN_FREE_GIB:.1f} ГиБ; прогон не начинался"
                ),
            })
            log(f"pdens {pdens} пропущен: свободно {free:.1f} ГиБ")
            continue

        if spent >= J2_BUDGET_SECONDS:
            skipped.append({
                "pdens": pdens,
                "причина": (
                    f"бюджет времени подпункта {J2_BUDGET_SECONDS / 3600.0:.0f} ч "
                    f"исчерпан предыдущими прогонами ({spent / 3600.0:.1f} ч)"
                ),
            })
            log(f"pdens {pdens} пропущен: бюджет времени исчерпан")
            continue

        result, payload = run_scheil(
            ctx, mole, f"контрольный состав, pdens {pdens}", A4_STEP_K, (), pdens
        )
        curve = scheil_curve(result)
        summary = instrumented_summary(result, payload, curve)
        summary["попытка"] = f"pdens {pdens}"
        rows.append(summary)
        curves[f"pdens {pdens}"] = curve.to_dict("records")
        # На диск сразу: следующий прогон может не закончиться.
        pd.DataFrame(rows).to_csv(OUT / "j2_pdens_runs.csv", **CSV_WRITE)
        spent += float(payload["секунд"])
        gc.collect()

    return {"таблица": rows, "кривые": curves, "пропущено": skipped}


def plot_j2(curves: Mapping[str, pd.DataFrame], path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    for label, curve in curves.items():
        real = curve[curve["точка посчитана"]]
        axes[0].plot(real["доля твёрдого"], real["T, °C"], linewidth=1.6, label=label)
        tail = real[real["доля твёрдого"] >= 0.90]
        if not tail.empty:
            axes[1].plot(tail["доля твёрдого"], tail["T, °C"],
                         marker="o", markersize=3, linewidth=1.4, label=label)

    axes[0].set_xlabel("доля твёрдого")
    axes[0].set_ylabel("температура, °C")
    axes[0].set_title("Затвердевание по Шейлю, только посчитанные точки")
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=8)

    axes[1].set_xlabel("доля твёрдого")
    axes[1].set_ylabel("температура, °C")
    axes[1].set_title("Хвост: доля твёрдого от 0,90 до останова")
    axes[1].grid(alpha=0.3)
    axes[1].legend(fontsize=8)

    figure.suptitle("11J-2. Головной прогон при разной плотности выборки, шаг 0,5 K")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


def step_j2(force: bool = False) -> None:
    progress = load_progress()
    if progress.get("11J-2", {}).get("готов") and not force:
        log("11J-2 пропущен, посчитан ранее (--force для пересчёта)")
        return

    payload = run_child(["--j2", "1"] + (["--force"] if force else []))
    table = pd.DataFrame(payload["таблица"])
    write_csv(table, "j2_pdens_runs.csv")
    curves = {
        label: pd.DataFrame(records) for label, records in payload["кривые"].items()
    }
    plot_j2(curves, OUT / "j2_pdens_runs.png")

    base = table.iloc[0]
    fs_column = "доля твёрдого на последней посчитанной точке"
    t_column = "T последней посчитанной точки, °C"
    interval_column = "интервал по Шейлю до последней посчитанной точки, K"

    comparison = [
        {
            "прогон": row["попытка"],
            "pdens": int(row.get("pdens", A4_PDENS)),
            "доля твёрдого на останове": float(row[fs_column]),
            "сдвиг доли против pdens 100": round(
                float(row[fs_column]) - float(base[fs_column]), 6
            ),
            "T останова, °C": float(row[t_column]),
            "сдвиг T против pdens 100, K": round(
                float(row[t_column]) - float(base[t_column]), 3
            ),
            "интервал по Шейлю, K": float(row[interval_column]),
            "причина останова": row["причина останова"],
            "секунд": float(row["секунд"]),
        }
        for _, row in table.iterrows()
    ]

    # Сдвинулся ли останов. Порог 0,002 по доле твёрдого — это примерно шаг,
    # которым доля растёт на последних точках; меньшее движение неотличимо от
    # того же самого места.
    moved = [
        item for item in comparison[1:]
        if item["сдвиг доли против pdens 100"] > 0.002
    ]
    base_residual = 1.0 - float(base[fs_column])
    if moved:
        best = max(moved, key=lambda item: item["доля твёрдого на останове"])
        residual = 1.0 - float(best["доля твёрдого на останове"])
        shrunk = 1.0 - residual / base_residual if base_residual else 0.0
        # Мера — не сдвиг доли твёрдого сам по себе, а насколько сократился
        # неразрешённый остаток жидкости: именно он и есть то, чего не хватает
        # расчёту. Сокращение вдвое — это уже другая картина хвоста; сокращение
        # на проценты — поправка, которая порядок предела не меняет.
        if shrunk >= 0.5:
            verdict = (
                f"Останов уехал дальше существенно: при pdens {best['pdens']} "
                f"неразрешённый остаток жидкости {100.0 * residual:.1f} % против "
                f"{100.0 * base_residual:.1f} % при pdens 100, то есть меньше "
                f"на {100.0 * shrunk:.0f} %. Предел был в плотности выборки, а "
                f"не в методе; интервал по Шейлю не менее "
                f"{best['интервал по Шейлю, K']:.1f} K."
            )
        else:
            verdict = (
                f"Останов сдвинулся, но немного: при pdens {best['pdens']} доля "
                f"твёрдого на останове {best['доля твёрдого на останове']:.4f} "
                f"против {float(base[fs_column]):.4f} при pdens 100, "
                f"неразрешённый остаток сократился с {100.0 * base_residual:.1f} % "
                f"до {100.0 * residual:.1f} %, то есть на {100.0 * shrunk:.0f} %. "
                f"Плотность выборки в хвосте вносит поправку, но предел метода "
                f"снимает не она: отказ сходимости остаётся тем же самым и "
                f"наступает практически там же. Интервал по Шейлю не менее "
                f"{best['интервал по Шейлю, K']:.1f} K — прежние 79,0 K были "
                f"занижены и обрывом, и сеткой, но по-прежнему это оценка снизу."
            )
    else:
        verdict = (
            "Останов не сдвинулся: уплотнение выборки не меняет ни долю "
            "твёрдого на останове, ни температуру останова. Предел настоящий, "
            "гипотеза о недостаточной плотности выборки в хвосте отклонена."
        )

    summary = {
        "подпункт": "11J-2. Можно ли пройти хвост Шейля дальше",
        "шаг по температуре, K": A4_STEP_K,
        "проверенные pdens": [A4_PDENS] + [
            item["pdens"] for item in comparison[1:]
        ],
        "сравнение": comparison,
        "пропущено": payload["пропущено"],
        "вердикт": verdict,
    }
    write_json(summary, "j2_summary.json")

    progress["11J-2"] = {
        "готов": True,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "шаг, K": A4_STEP_K,
        "pdens": [item["pdens"] for item in comparison],
        "режим набора фаз": "все фазы",
    }
    save_progress(progress)


# --------------------------------------------------------------------------- #
# A5. Марганец
# --------------------------------------------------------------------------- #


def a5_manganese(force: bool = False) -> dict[str, Any]:
    """Два состава по марганцу шагом 0,5 K. Считается в потомке."""

    del force
    ctx = Context()
    rows: list[dict[str, Any]] = []
    curves: dict[str, pd.DataFrame] = {}

    for label, overrides in A5_CASES:
        mole = wt_to_mole(ctx, full_wt(overrides))
        result, payload = run_scheil(ctx, mole, label, A5_STEP_K, ())
        curve = scheil_curve(result)
        summary = instrumented_summary(result, payload, curve)
        summary["состав"] = label
        rows.append(summary)
        curve.to_csv(
            OUT / f"a5_curve_{'mn020' if '0,20' in label else 'mn050'}.csv",
            **CSV_WRITE,
        )
        pd.DataFrame(rows).to_csv(OUT / "a5_manganese.csv", **CSV_WRITE)
        curves[label] = curve
        gc.collect()

    return {
        "таблица": rows,
        "кривые": {label: curve.to_dict("records") for label, curve in curves.items()},
    }


def a5_common_fraction(curves: Mapping[str, pd.DataFrame]) -> dict[str, Any]:
    """Сравнение составов на доле твёрдого, до которой дошли оба прогона.

    11J-1. Постановка требует сравнивать составы только при близкой доле
    твёрдого на останове. Если доли разошлись, «температура последней точки»
    сравнивает разные места кривой: прогон, ушедший дальше, кончается ниже уже
    потому, что прошёл больше, а не потому, что сплав хуже. Поэтому здесь обе
    кривые режутся по общей достигнутой доле, и сравниваются температуры при
    одной и той же доле твёрдого — величина, у которой смысл один.
    """

    labels = list(curves)
    solid: dict[str, Any] = {}
    temperature: dict[str, Any] = {}
    for label in labels:
        real = curves[label][curves[label]["точка посчитана"] == True]  # noqa: E712
        solid[label] = real["доля твёрдого"].to_numpy(dtype=float)
        temperature[label] = real["T, °C"].to_numpy(dtype=float)

    common = min(float(solid[label].max()) for label in labels)
    marks = sorted({0.90, 0.95, round(common, 6)})
    rows: list[dict[str, Any]] = []
    for mark in marks:
        row: dict[str, Any] = {"доля твёрдого": round(mark, 6)}
        for label in labels:
            row[f"T, °C — {label}"] = round(
                float(np.interp(mark, solid[label], temperature[label])), 2
            )
        row["разность, K"] = round(
            row[f"T, °C — {labels[0]}"] - row[f"T, °C — {labels[1]}"], 2
        )
        rows.append(row)

    kou_common = {
        label: kou_on_window(curves[label], (0.90, common))["максимум, K"]
        for label in labels
    }
    return {
        "общая достигнутая доля твёрдого": round(common, 6),
        "температуры при одинаковой доле твёрдого": rows,
        "Kou на общем окне fs 0,90…%.4f, K" % common: kou_common,
    }


def plot_a5(curves: Mapping[str, pd.DataFrame], path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12.5, 4.6))
    for label, curve in curves.items():
        real = curve[curve["точка посчитана"]]
        axes[0].plot(real["доля твёрдого"], real["T, °C"], linewidth=1.7, label=label)
        table = kou_on_window(curve, A4_KOU_FIXED_WINDOW)["таблица"]
        if not table.empty:
            axes[1].plot(table["доля твёрдого"], table["|dT/d(fs^0.5)|, K"],
                         marker="o", markersize=3, linewidth=1.5, label=label)

    axes[0].set_xlabel("доля твёрдого")
    axes[0].set_ylabel("температура, °C")
    axes[0].set_title("Затвердевание по Шейлю, только посчитанные точки")
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=8)

    axes[1].set_xlabel("доля твёрдого")
    axes[1].set_ylabel("|dT/d(fs^0,5)|, K")
    axes[1].set_title(
        f"Критерий Kou на фиксированном окне fs "
        f"{A4_KOU_FIXED_WINDOW[0]:g}…{A4_KOU_FIXED_WINDOW[1]:g}"
    )
    axes[1].grid(alpha=0.3)
    axes[1].legend(fontsize=8)

    figure.suptitle("A5. Марганец 0,50 % против 0,20 % при S 0,020 %, шаг 0,5 K")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


def step_a5(force: bool = False) -> None:
    progress = load_progress()
    if progress.get("A5", {}).get("готов") and not force:
        log("A5 пропущен, посчитан ранее (--force для пересчёта)")
        return

    payload = run_child(["--a5", "1"] + (["--force"] if force else []))
    table = pd.DataFrame(payload["таблица"])
    write_csv(table, "a5_manganese.csv")
    curves = {
        label: pd.DataFrame(records) for label, records in payload["кривые"].items()
    }
    plot_a5(curves, OUT / "a5_manganese.png")

    high = table.iloc[0]
    low = table.iloc[1]
    fixed_column = (
        f"Kou на фиксированном окне fs {A4_KOU_FIXED_WINDOW[0]:g}…"
        f"{A4_KOU_FIXED_WINDOW[1]:g}, K"
    )
    fs_high = float(high["доля твёрдого на последней посчитанной точке"])
    fs_low = float(low["доля твёрдого на последней посчитанной точке"])
    t_high = float(high["T последней посчитанной точки, °C"])
    t_low = float(low["T последней посчитанной точки, °C"])
    kou_high, kou_low = high[fixed_column], low[fixed_column]

    # Сравнение корректно только при близкой доле твёрдого на останове: иначе
    # сравниваются точки, до которых расчёты дошли по-разному.
    comparable = abs(fs_high - fs_low) <= 0.01

    summary = {
        "подпункт": "A5. Марганец: подтвердить или опровергнуть",
        "шаг по температуре, K": A5_STEP_K,
        "сравнение": {
            "T последней посчитанной точки, °C": {
                "Mn 0,50 %": round(t_high, 2),
                "Mn 0,20 %": round(t_low, 2),
                "разность, K": round(t_high - t_low, 2),
            },
            "доля твёрдого на останове": {
                "Mn 0,50 %": round(fs_high, 6),
                "Mn 0,20 %": round(fs_low, 6),
                "разность": round(fs_high - fs_low, 6),
            },
            fixed_column: {
                "Mn 0,50 %": kou_high,
                "Mn 0,20 %": kou_low,
                "отношение": (
                    round(float(kou_low) / float(kou_high), 2)
                    if kou_high and kou_low else None
                ),
            },
        },
        "доли твёрдого на останове сопоставимы": bool(comparable),
        "сравнение на общей доле твёрдого": a5_common_fraction(curves),
        "волна 10, шаг 2 K": {
            "T конца при Mn 0,50 %": 1294.0,
            "T конца при Mn 0,20 %": 1276.6,
            "разность, K": 17.4,
        },
    }
    write_json(summary, "a5_summary.json")

    progress["A5"] = {
        "готов": True,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "шаг, K": A5_STEP_K,
        "pdens": A4_PDENS,
        "режим набора фаз": "все фазы",
    }
    save_progress(progress)


# --------------------------------------------------------------------------- #
# 11J-4. Таблица замеров памяти
# --------------------------------------------------------------------------- #


# Что за прогон стоит за каждым файлом замера. Имя файла — это набор ключей
# командной строки потомка, и само по себе оно не говорит ни о плотности
# выборки, ни о том, чем прогон кончился.
J4_LABELS: dict[str, dict[str, str]] = {
    "a5_1": {
        "пункт": "11J-1, марганец",
        "что считалось": "Mn 0,20 % шагом 0,5 K (Mn 0,50 % взят из кэша)",
        "pdens": "100",
        "шаг, K": "0,5",
    },
    "a5_1_force": {
        "пункт": "11J-1, пересборка",
        "что считалось": "обе сводки пересобраны из кэша, равновесий не считалось",
        "pdens": "100",
        "шаг, K": "0,5",
    },
    "a4_1_force": {
        "пункт": "11J-3, пересборка",
        "что считалось": "три прогона A4 пересобраны из кэша, равновесий не считалось",
        "pdens": "100",
        "шаг, K": "0,5",
    },
    "j2_pdens500_snyat": {
        "пункт": "11J-2, снятый прогон",
        "что считалось": "pdens 500, прогон снят системой по нехватке памяти",
        "pdens": "500",
        "шаг, K": "0,5",
    },
    "j2_1": {
        "пункт": "11J-2, пересборка",
        "что считалось": (
            "pdens 300 взят из кэша, pdens 500 пропущен по нехватке памяти; "
            "равновесий не считалось"
        ),
        "pdens": "300",
        "шаг, K": "0,5",
    },
    "j2_1_force": {
        "пункт": "11J-2, пересборка",
        "что считалось": "сводка пересобрана из кэша, равновесий не считалось",
        "pdens": "300",
        "шаг, K": "0,5",
    },
}

# Собственный прогон при pdens 300 (28,2 мин) замера не имеет: он считался
# раньше, чем замер научился сбрасывать снимок на диск по ходу, а родителя
# сняли вместе со следующим прогоном. Повторять счёт ради одного числа не
# стали — это те же 28 минут на машине, где памяти и так не хватает.
J4_MISSING = (
    "прогон 11J-2 при pdens 300, 28,2 мин: замер потерян вместе со снятым "
    "родительским процессом"
)


def j4_row(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text("utf-8"))
    stem = path.stem.replace("j4_memory_", "")
    label = J4_LABELS.get(stem, {"пункт": stem, "что считалось": "—",
                                 "pdens": "—", "шаг, K": "—"})
    swapped = float(payload["прирост занятой подкачки в системе, ГиБ"])
    return {
        "пункт": label["пункт"],
        "что считалось": label["что считалось"],
        "pdens": label["pdens"],
        "шаг, K": label["шаг, K"],
        "пик рабочего набора, ГиБ": payload["пик рабочего набора дерева, ГиБ"],
        "пик фиксации, ГиБ": payload["пик фиксации дерева, ГиБ"],
        "минимум свободной физической, ГиБ": payload["минимум свободной физической, ГиБ"],
        "ушло в подкачку": "да" if swapped > 0.05 else "нет",
        "прирост подкачки, ГиБ": swapped,
        "минут под наблюдением": round(float(payload["секунд под наблюдением"]) / 60.0, 1),
        "замер завершён": payload.get("замер завершён", True),
    }


def step_j4(force: bool = False) -> None:
    """Сводит замеры, сделанные на прогонах 11J-1 и 11J-2. Ничего не считает."""

    del force
    paths = sorted(OUT.glob("j4_memory_*.json"))
    if not paths:
        log("11J-4: замеров нет, сначала надо посчитать 11J-1 и 11J-2")
        return

    table = pd.DataFrame([j4_row(path) for path in paths])
    write_csv(table, "j4_memory.csv")

    import psutil

    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()
    heavy = table[table["минут под наблюдением"] >= 1.0]
    summary = {
        "подпункт": "11J-4. Замер памяти",
        "физической памяти всего, ГиБ": round(virtual.total / 1024.0 ** 3, 3),
        "подкачки всего, ГиБ": round(swap.total / 1024.0 ** 3, 3),
        "потолок машины, ГиБ": round(
            (virtual.total + swap.total) / 1024.0 ** 3, 3
        ),
        "шаг опроса, с": MEMORY_POLL_SECONDS,
        "таблица": table.to_dict("records"),
        "наибольший пик рабочего набора, ГиБ": (
            float(heavy["пик рабочего набора, ГиБ"].max()) if not heavy.empty else None
        ),
        "замеров нет для": J4_MISSING,
        "наименьшая свободная физическая, ГиБ": (
            float(heavy["минимум свободной физической, ГиБ"].min())
            if not heavy.empty else None
        ),
    }
    write_json(summary, "j4_summary.json")

    progress = load_progress()
    progress["11J-4"] = {
        "готов": True,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "замеров сведено": len(table),
    }
    save_progress(progress)


# --------------------------------------------------------------------------- #
# Ввод-вывод
# --------------------------------------------------------------------------- #


# Формат таблиц волн 9 и 10: точка с запятой и десятичная запятая. Один
# каталог не должен смешивать два формата — иначе половина файлов открывается
# в Excel одним столбцом.
CSV_WRITE = {"index": False, "sep": ";", "decimal": ",", "encoding": "utf-8-sig"}
CSV_READ = {"sep": ";", "decimal": ",", "encoding": "utf-8-sig"}


def write_csv(table: pd.DataFrame, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    table.to_csv(path, **CSV_WRITE)
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


# --------------------------------------------------------------------------- #
# 11J-4. Замер памяти
# --------------------------------------------------------------------------- #

# Опрос раз в две секунды. Прогон Шейля идёт десятки минут, поэтому такая
# частота ничего не стоит, а пик рабочего набора растёт медленно: между двумя
# соседними равновесиями он не успевает подскочить и опасть незамеченным.
MEMORY_POLL_SECONDS = 2.0
# Как часто снимок уезжает на диск. Файл маленький, запись раз в полминуты не
# стоит ничего, зато замер переживает снятие процесса по нехватке памяти.
MEMORY_FLUSH_SECONDS = 30.0


def memory_probe(process: Any) -> dict[str, float] | None:
    """Один замер: процесс-потомок со всем его потомством плюс система.

    Сумма по дереву, а не по одному процессу: тяжёлый подпункт сам может
    запускать процессы, и одиночное значение тогда занижено.

    Два числа по процессу разные, и нужны оба. ``rss`` на Windows — рабочий
    набор, то есть страницы, физически лежащие в памяти. ``pagefile`` —
    зарезервированная фиксация (commit charge), она включает и то, что уехало
    в подкачку. Их разность — прямой признак свопа.
    """

    import psutil

    rss = 0
    commit = 0
    alive = 0
    try:
        family = [process] + process.children(recursive=True)
    except psutil.Error:
        return None
    for member in family:
        try:
            info = member.memory_info()
        except psutil.Error:
            continue
        alive += 1
        rss += int(getattr(info, "rss", 0))
        commit += int(getattr(info, "pagefile", getattr(info, "vms", 0)))
    if alive == 0:
        return None

    virtual = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "процессов": float(alive),
        "рабочий набор дерева, ГиБ": rss / 1024.0 ** 3,
        "фиксация дерева, ГиБ": commit / 1024.0 ** 3,
        "в подкачке у дерева, ГиБ": max(0.0, (commit - rss) / 1024.0 ** 3),
        "свободной физической, ГиБ": virtual.available / 1024.0 ** 3,
        "занято подкачки в системе, ГиБ": swap.used / 1024.0 ** 3,
    }


def memory_watch(process: Any, stop: Any, record: dict[str, Any],
                 stem: str | None = None) -> None:
    """Фоновый опрос до завершения потомка. В расчёт не вмешивается.

    Снимок сбрасывается на диск раз в ``MEMORY_FLUSH_SECONDS``, а не только в
    конце. Прогон при pdens 500 был снят операционной системой по нехватке
    памяти вместе с родителем, и замер, который держался в памяти родителя,
    пропал ровно там, где был нужнее всего. Записанный по ходу файл переживает
    и такой обрыв.
    """

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

    flushed = time.perf_counter()
    while not stop.wait(MEMORY_POLL_SECONDS):
        probe = memory_probe(process)
        if probe is None:
            continue
        record["замеров"] += 1
        record["пик рабочего набора дерева, ГиБ"] = max(
            record["пик рабочего набора дерева, ГиБ"],
            probe["рабочий набор дерева, ГиБ"],
        )
        record["пик фиксации дерева, ГиБ"] = max(
            record["пик фиксации дерева, ГиБ"], probe["фиксация дерева, ГиБ"]
        )
        record["наибольшая разность фиксации и набора, ГиБ"] = max(
            record["наибольшая разность фиксации и набора, ГиБ"],
            probe["в подкачке у дерева, ГиБ"],
        )
        record["минимум свободной физической, ГиБ"] = min(
            record["минимум свободной физической, ГиБ"],
            probe["свободной физической, ГиБ"],
        )
        record["максимум занятой подкачки в системе, ГиБ"] = max(
            record["максимум занятой подкачки в системе, ГиБ"],
            probe["занято подкачки в системе, ГиБ"],
        )
        now = time.perf_counter()
        if stem is not None and now - flushed >= MEMORY_FLUSH_SECONDS:
            memory_report(stem, record, now - started_at(record), final=False)
            flushed = now


def started_at(record: Mapping[str, Any]) -> float:
    return float(record.get("начало, perf_counter", time.perf_counter()))


def memory_report(stem: str, record: Mapping[str, Any], seconds: float,
                  final: bool = True) -> Path | None:
    """Итог замера рядом с результатами подпункта.

    ``final=False`` — промежуточный сброс по ходу счёта: файл тот же самый,
    просто помечен незавершённым, чтобы обрыв не выдавали за конец прогона.
    """

    if not record.get("замеров"):
        return None
    payload: dict[str, Any] = {
        key: (round(value, 3) if isinstance(value, float) else value)
        for key, value in record.items()
    }
    payload.pop("начало, perf_counter", None)
    payload["секунд под наблюдением"] = round(seconds, 1)
    payload["шаг опроса, с"] = MEMORY_POLL_SECONDS
    payload["замер завершён"] = bool(final)
    payload["прирост занятой подкачки в системе, ГиБ"] = round(
        float(record["максимум занятой подкачки в системе, ГиБ"])
        - float(record["занято подкачки до старта, ГиБ"]), 3
    )
    path = OUT / f"j4_memory_{stem}.json"
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    if not final:
        return path
    log(
        f"память: пик набора {payload['пик рабочего набора дерева, ГиБ']:.2f} ГиБ, "
        f"минимум свободной {payload['минимум свободной физической, ГиБ']:.2f} ГиБ, "
        f"прирост подкачки {payload['прирост занятой подкачки в системе, ГиБ']:+.2f} ГиБ"
    )
    return path


def run_child(arguments: Sequence[str]) -> dict[str, Any]:
    """Тяжёлый кусок — в отдельном процессе; результат приходит файлом.

    Возврат через файл, а не через stdout: лог подпункта должен идти на экран
    по мере счёта, а не копиться в трубе до конца работы потомка.

    Пока потомок считает, родитель опрашивает его память (11J-4). Опрос идёт в
    отдельном потоке родителя и к расчёту не прикасается, поэтому числа
    подпункта от наблюдения не зависят.
    """

    stem = "_".join(argument.strip("-") for argument in arguments)
    handoff = CACHE / f"child_{stem}.json"
    CACHE.mkdir(parents=True, exist_ok=True)
    if handoff.is_file():
        handoff.unlink()
    environment = dict(os.environ, PYTHONHASHSEED="0")
    command = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
               *arguments, "--handoff", str(handoff)]

    started = time.perf_counter()
    popen = subprocess.Popen(command, env=environment, cwd=str(ROOT))
    record: dict[str, Any] = {
        "подпункт": stem, "начало, perf_counter": started,
    }
    watcher = None
    stop = threading.Event()
    try:
        import psutil
    except ImportError:
        log("psutil недоступен, память не замеряется")
    else:
        watcher = threading.Thread(
            target=memory_watch,
            args=(psutil.Process(popen.pid), stop, record, stem),
            daemon=True,
        )
        watcher.start()

    returncode = popen.wait()
    stop.set()
    if watcher is not None:
        watcher.join(timeout=MEMORY_POLL_SECONDS * 2)
        memory_report(stem, record, time.perf_counter() - started)

    if returncode != 0 or not handoff.is_file():
        raise RuntimeError(
            f"потомок {' '.join(arguments)} завершился с кодом {returncode}"
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
        pd.DataFrame(rows).to_csv(partial, **CSV_WRITE)
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


STEPS = {"a1": step_a1, "a2": step_a2, "a3": step_a3,
         "d2": step_d2, "a4": step_a4, "d3": step_d3, "a5": step_a5,
         "j2": step_j2, "j4": step_j4}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Волна 11A: расчёты по ХН62М")
    parser.add_argument("--only", default="all", help="a1, … ; через запятую")
    parser.add_argument("--force", action="store_true", help="пересчитать готовое")
    parser.add_argument("--a1-one", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--a1-wave9", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--a2", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--a3", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--d2", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--a4", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--a5", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--j2", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--handoff", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    if args.a1_one is not None:
        payload = a1_one_pdens(args.a1_one)
    elif args.a1_wave9 is not None:
        payload = a1_wave9_method(args.a1_wave9)
    elif args.a2 is not None:
        payload = a2_density(force=args.force)
    elif args.a3 is not None:
        payload = a3_homogenization(force=args.force)
    elif args.d2 is not None:
        payload = d2_homogenization(force=args.force)
    elif args.a4 is not None:
        payload = a4_scheil(force=args.force)
    elif args.a5 is not None:
        payload = a5_manganese(force=args.force)
    elif args.j2 is not None:
        payload = j2_dense(force=args.force)
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
