#!/usr/bin/env python3
"""Волна 12, подпункт 12-3 — изменение объёма при выделении P-фазы.

Задание `tasks/WAVE12_3_OPUS.md`. Вопрос подпункта пришёл из механики
вальцованного соединения труба—трубная решётка: вальцовка держится контактным
давлением, и если металл при выделении P-фазы меняет объём, давление меняется
вместе с ним. Здесь считается **только изменение объёма**. Само контактное
давление и усилие вырыва не считаются: это механика, которой в проекте нет.

Что считается.

* **Исходное состояние** — однофазная пересыщенная матрица состава сплава:
  равновесие, в котором разрешена одна фаза `FCC_A1`, поэтому её состав равен
  составу сплава. Удельный (молярный) объём — из плотности и молярной массы.
* **Равновесное состояние** — два набора фаз сразу, и они не подменяют друг
  друга. «Двухфазный» набор `FCC_A1 + P_PHASE` отвечает букве задания и
  сравним с опорным равновесием подпункта 12-1; «полный» набор — все фазы
  базы, то есть штатный путь приложения, и именно из него взяты опорные
  молярные объёмы `results/hn62m_wave12/cache/k1_volumes.json`.
* **ΔV/V и ΔL/L = ΔV/(3V)** в точках ТЗ 580, 595, 664, 700 и 750 °C.
* **Зависимость от доли выделившейся P-фазы** от 0 до равновесной. Состав
  матрицы на промежуточной доле берётся не на глаз, а балансом вещества:
  `X_матрица(x) = (X_сплава − x·f_P·X_P) / (1 − x·f_P)`, и на каждом `x`
  считается своё однофазное равновесие `FCC_A1`, то есть своя плотность. Это
  связывает объём с кинетикой 12-1, где за 200 ч набирается 97…99 % конечной
  доли.

Погрешность плотности P-фазы прогоняется через весь расчёт. У P-фазы нет
своей модели плотности в `physical_data_v103.pdb`; приложение само называет её
плотность оценкой по правилу смеси с погрешностью до 10 %. Поэтому каждая
величина считается трижды: при номинальной плотности P-фазы, при −10 % и при
+10 %. Если знак ΔV/V при этом меняется, расчёт не устанавливает даже
направления изменения объёма, и это результат, а не неудача: подгонять здесь
нечего.

Масштабная сверка обязательна и делается тем же модулем плотности: ΔL/L от
выделения сравнивается с тепловым расширением того же сплава на переходах
25 → 700 °C и 700 → 750 °C. Без этого сравнения число ΔL/L инженеру ничего не
говорит. Нижняя точка 25 °C, а не 20 °C, названные заданием: DP-параметры
`physical_data_v103.pdb` определены от 298,15 K, и база на 293,15 K отказывается
считать, а не экстраполирует (см. `THERMAL_LOW_C`).

Перекрытие по хрому. Плотности идут штатным путём приложения, то есть с файлом
перекрытий `databases/physical/overrides/physical_data_v103.overrides.json`
(волна 11M-2: тепловая функция хрома `DTCRBCC` в .pdb давала расширение втрое
круче измеренного). Факт применения не предполагается, а берётся из
предупреждений самого расчёта (`PhysicalCalculationResult.warnings`) и из
списка `PhysicalDensityDatabase.applied_overrides`; оба уходят в сводку
подпункта отдельными полями.

Модуль не переписывает волну 12-2, а импортирует из неё разбор состава, кэш,
пороги, формат CSV и замер памяти; путь «плотность фазы → молярный объём»
повторяет подпункт 12-1 и сверяется с его числами. Своими остались только те
служебные функции, которые привязаны к имени файла или к префиксу подпункта:
`run_child` запускает `Path(__file__)`, а `memory_report` кладёт файл под
префиксом `e3`. Та же причина и то же решение, что в подпунктах 12-1, 12-4
и 12-5.

Запуск (интерпретатор — venv основного репозитория, PYTHONHASHSEED=0):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 ^
        tools\\study_hn62m_wave12_volume.py --only e3 --min-free-gib 2.5

Память. Порог входа — параметр задачи (`tasks/RULES.md`, раздел «Память и
параллельность») и задаётся ключом `--min-free-gib`, а не правкой константы:
константа остаётся общей и импортируемой (`w12.MIN_FREE_GIB`, он же
`w11.J2_MIN_FREE_GIB` = 4,0 ГиБ), фактическое значение уходит в сводку рядом с
умолчанием. Для этого подпункта объявлено 2,5 ГиБ. Обоснование числом: подпункт
12-5 устроен так же — та же база, тот же состав по числу компонентов, тот же
`pdens`, тот же полный набор фаз, тот же разбор точки — и показал пик рабочего
набора дерева 1,355 ГиБ при пике фиксации 2,249 ГиБ
(`results/hn62m_wave12/e5_memory_e5_1_min-free-gib_2_5_stage-b-elements_4.json`).
Порог 2,5 ГиБ покрывает измеренную фиксацию и не требует 4,0 ГиБ, которых на
этой машине при занятой посторонними памяти может не быть. Аварийный порог по
ходу счёта — другая величина (`w12.E1_ABORT_FREE_GIB`), ключа не имеет и не
понижается ни ключом, ни правкой.

Кэш обязателен: прогон могут снять посторонние процессы, и каждое сошедшееся
равновесие уходит на диск сразу (`cache/e3_points.jsonl`). Ключ кэша — состав,
температура и набор разрешённых фаз, поэтому однофазные точки развёртки по доле
не путаются с полными равновесиями на том же составе.

Границы достоверности живут в отчёте. Здесь называется только то, что видно из
кода: скандия в списке компонентов нет, потому что его нет в mc_ni; фосфора там
тоже нет; расчёт равновесный и о временах не говорит ничего; механики в проекте
нет вовсе, поэтому ни давление, ни усилие вырыва отсюда не выходят.
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

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import study_hn62m_wave11 as w11
import study_hn62m_wave12 as w12

ROOT = w12.ROOT
OUT = w12.OUT
CACHE = w12.CACHE

CSV_WRITE = dict(w12.CSV_WRITE)
log = w12.log

# Префикс подпункта в именах результатов. Волна 12 уже занимает e1 (12-2),
# e4 (12-4), e5 (12-5) и k1 (12-1).
PREFIX = "e3"

DB_REL = w12.DB_REL
PDB_REL = w11.PDB_REL
COMPONENTS: tuple[str, ...] = tuple(w12.COMPONENTS)
ELEMENT_ORDER: tuple[str, ...] = tuple(w12.ELEMENT_ORDER)

# Пороги памяти — значения волны 12-2, а не свои.
MIN_FREE_GIB = w12.MIN_FREE_GIB
ABORT_FREE_GIB = w12.E1_ABORT_FREE_GIB

# Измеренный пик прогона 12-5, которым обосновывается порог входа.
JUSTIFY_PEAK_SET_GIB = 1.355
JUSTIFY_PEAK_COMMIT_GIB = 2.249
JUSTIFY_SOURCE = (
    "results/hn62m_wave12/e5_memory_e5_1_min-free-gib_2_5_stage-b-elements_4.json"
)
TASK_MIN_FREE_GIB = 2.5

# Плотность выборки и ряд повторов — волны 12-2, иначе числа подпунктов
# окажутся несравнимы.
PDENS = w12.E1_PDENS
RETRY_PDENS: tuple[int, ...] = tuple(w12.E1_RETRY_PDENS)

PRESENT_FLOOR = w12.E1_PRESENT_FLOOR
SUM_TOLERANCE = w12.E1_SUM_TOLERANCE

MATRIX_PHASE = w12.E1_MATRIX_PHASE          # FCC_A1
PRECIPITATE_PHASE = "P_PHASE"

# --- 12-3 ------------------------------------------------------------------ #

# Точки ТЗ. Те же пять, что считала волна 12-2.
E3_T_C: tuple[float, ...] = tuple(w12.E1_REQUIRED_C)

# Наборы разрешённых фаз. None — все фазы базы, то есть штатный путь приложения.
FULL_SET = "полный"
TWO_PHASE_SET = "двухфазный"
MATRIX_SET = "однофазный"
PHASE_SETS: dict[str, tuple[str, ...] | None] = {
    FULL_SET: None,
    TWO_PHASE_SET: (MATRIX_PHASE, PRECIPITATE_PHASE),
    MATRIX_SET: (MATRIX_PHASE,),
}

# Погрешность плотности P-фазы. Величину называет само приложение в примечании
# к фазе: «Плотность оценена по правилу смеси; погрешность до 10 %».
DENSITY_BAND: tuple[float, ...] = (-0.10, 0.0, 0.10)

# Доли выделившейся P-фазы от равновесной. Узлы 0,97 и 0,99 стоят здесь не для
# красоты сетки: подпункт 12-1 показал, что за 200 ч набирается 97,4…99,4 %
# конечной доли, и именно на этих долях отчёт связывает объём с кинетикой.
FRACTION_GRID: tuple[float, ...] = (
    0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.97, 0.99, 1.0
)

# Переходы для масштабной сверки с тепловым расширением. Задание называло
# нижней точкой 20 °C («например, 20 → 700 °C»), но DP-параметры
# physical_data_v103.pdb определены от 298,15 K, и на 293,15 K база отказывается
# считать, а не экстраполирует: «Температура 293.15 K вне диапазона DP-параметра
# FCC_A1: 298.15-6000.00 K». Нижняя точка взята 25 °C — это собственная опорная
# температура базы (ρ(298,15 K) = 7181,91 кг/м³ у хрома, см. файл перекрытий), и
# подставлять вместо неё несуществующее в базе значение нельзя. Расхождение с
# заданием названо в отчёте отдельным пунктом.
THERMAL_LOW_C = 25.0
THERMAL_PAIRS: tuple[tuple[float, float], ...] = (
    (THERMAL_LOW_C, 700.0), (700.0, 750.0)
)
THERMAL_T_C: tuple[float, ...] = tuple(sorted(
    {*E3_T_C, *(value for pair in THERMAL_PAIRS for value in pair)}
))

# Опорные числа подпункта 12-1 для сверки молярных объёмов.
REFERENCE_NAME = "k1_volumes.json"
REFERENCE_TOLERANCE = 1.0e-4      # см³/моль; расхождение сверх — это расхождение


# --------------------------------------------------------------------------- #
# Составы
# --------------------------------------------------------------------------- #


def normalised(composition: Mapping[str, float]) -> dict[str, float]:
    """Мольные доли, приведённые к сумме 1 по элементам расчёта."""

    values = {element: max(0.0, float(composition.get(element, 0.0)))
              for element in w11.ELEMENTS}
    total = sum(values.values())
    if total <= 0.0:
        raise ValueError("пустой состав")
    return {element: value / total for element, value in values.items()}


def lever_matrix(alloy: Mapping[str, float], precipitate: Mapping[str, float],
                 precipitate_fraction: float, share: float) -> dict[str, float]:
    """Состав матрицы, когда выделилась доля ``share`` равновесной P-фазы.

    Баланс вещества, а не приближение: из состава сплава вычитается то, что
    ушло в выделение, и остаток делится на оставшиеся моли матрицы.

        X_матрица = (X_сплава − x·f_P·X_P) / (1 − x·f_P)

    Результат — выпуклая комбинация равновесного состава матрицы и состава
    P-фазы, поэтому отрицательных долей тут не бывает по построению.
    Состав самой P-фазы принят равным равновесному и от доли не зависящим: это
    допущение равновесной постановки, оно названо в отчёте.
    """

    taken = float(share) * float(precipitate_fraction)
    rest = 1.0 - taken
    if rest <= 1.0e-9:
        raise ValueError("доля выделения не оставляет матрицы")
    return normalised({
        element: (float(alloy.get(element, 0.0))
                  - taken * float(precipitate.get(element, 0.0))) / rest
        for element in w11.ELEMENTS
    })


# --------------------------------------------------------------------------- #
# Кэш точек
# --------------------------------------------------------------------------- #


class PointCache:
    """Кэш разобранных равновесий подпункта 12-3.

    Механизм волны 12-2 (строка на точку, ``fsync`` сразу, свой файл по правилу
    владения), но ключ шире: в него входит набор разрешённых фаз. Иначе
    однофазная точка развёртки по доле и полное равновесие на том же составе и
    той же температуре легли бы под один ключ.
    """

    def __init__(self) -> None:
        CACHE.mkdir(parents=True, exist_ok=True)
        self.path = CACHE / f"{PREFIX}_points.jsonl"
        self.records: dict[str, dict[str, Any]] = {}
        if self.path.is_file():
            for line in self.path.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                self.records[record["key"]] = record["payload"]
            log(f"кэш точек: {len(self.records)} записей")

    @staticmethod
    def key(mole: Mapping[str, float], temperature_c: float,
            phase_set: str) -> str:
        return f"{w11.composition_id(mole)}|{temperature_c:.4f}|{phase_set}"

    def get(self, mole: Mapping[str, float], temperature_c: float,
            phase_set: str) -> dict[str, Any] | None:
        return self.records.get(self.key(mole, temperature_c, phase_set))

    def put(self, mole: Mapping[str, float], temperature_c: float,
            phase_set: str, payload: Mapping[str, Any]) -> None:
        key = self.key(mole, temperature_c, phase_set)
        self.records[key] = dict(payload)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(
                {"key": key, "payload": payload},
                ensure_ascii=False, sort_keys=True,
            ) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


# --------------------------------------------------------------------------- #
# Равновесие с ограниченным набором фаз
# --------------------------------------------------------------------------- #


class Restricted:
    """Модели фаз для ограниченных наборов, построенные по одному разу.

    ``w11.Context.compiled`` строит символьные модели всех сорока восьми фаз, и
    это правильный путь для полного равновесия. Для набора из одной или двух
    фаз строить сорок восемь незачем, а строить две заново на каждый из
    шестидесяти пяти вызовов развёртки по доле — тем более. Объекты те же
    самые, что построил бы сам ``equilibrium``, поэтому числа не меняются;
    ровно так же переиспользует их ``w11.Context.compiled``.
    """

    def __init__(self, ctx: Any) -> None:
        self.ctx = ctx
        self._built: dict[tuple[str, ...], tuple[Any, Any]] = {}

    def compiled(self, phases: Sequence[str]) -> tuple[Any, Any]:
        from pycalphad import variables as v
        from pycalphad.codegen.phase_record_factory import PhaseRecordFactory
        from pycalphad.core.utils import instantiate_models

        key = tuple(phases)
        if key not in self._built:
            started = time.perf_counter()
            models = instantiate_models(self.ctx.db, list(COMPONENTS), list(key))
            records = PhaseRecordFactory(
                self.ctx.db, list(COMPONENTS), [v.N, v.P, v.T], models
            )
            self._built[key] = (models, records)
            log(f"модели набора {', '.join(key)} построены за "
                f"{time.perf_counter() - started:.1f} с")
        return self._built[key]


def solve_set(ctx: Any, restricted: Restricted, mole: Mapping[str, float],
              temperature_c: float, pdens: int,
              phases: Sequence[str] | None) -> Any:
    """Сырой результат ``equilibrium`` на заданном наборе фаз.

    ``phases is None`` — полный набор базы, и тогда это ровно ``w11.solve_raw``,
    то есть штатный путь приложения, которым шли волны 11 и 12-2.
    """

    if phases is None:
        return w11.solve_raw(ctx, mole, temperature_c, pdens)

    from pycalphad import equilibrium, variables as v

    conditions: dict[Any, float] = {
        v.N: 1.0, v.P: 101325.0, v.T: float(temperature_c) + 273.15,
    }
    conditions.update(
        {v.X(element): value for element, value in w11.independent_x(mole).items()}
    )
    models, records = restricted.compiled(phases)
    return equilibrium(
        ctx.db, list(COMPONENTS), list(phases), conditions,
        model=models, phase_records=records,
        calc_opts={"pdens": int(pdens)},
    )


def volume_payload(ctx: Any, restricted: Restricted, physical_db: Any,
                   mole: Mapping[str, float], temperature_c: float, pdens: int,
                   phase_set: str) -> dict[str, Any]:
    """Разбор одного равновесия: доли фаз, составы, плотности, молярные объёмы.

    Плотность фазы берётся тем же путём, которым её взял подпункт 12-1 и берёт
    само приложение: `thermogar_physical.calculate_physical_properties` на базе
    `physical_data_v103.pdb` со штатным файлом перекрытий. Молярная масса фазы
    считается из её равновесного состава (`w12.molar_mass_g_mol`). Молярный
    объём — отношение одного к другому.
    """

    from thermogar_physical import calculate_physical_properties

    started = time.perf_counter()
    result = solve_set(ctx, restricted, mole, temperature_c, pdens,
                       PHASE_SETS[phase_set])
    physical = calculate_physical_properties(
        ctx.db, result, list(w11.ELEMENTS), float(temperature_c) + 273.15,
        physical_db,
    )
    fractions, compositions = w12.aggregate(result)
    del result
    gc.collect()

    table = physical.phase_table
    kept = {name: value for name, value in fractions.items()
            if value > PRESENT_FLOOR}

    phases: dict[str, Any] = {}
    for name in sorted(kept):
        composition = {
            element: float(compositions[name].get(element, 0.0))
            for element in ELEMENT_ORDER
        }
        molar_mass = w12.molar_mass_g_mol(ctx, composition)
        rows = table[table["Фаза"] == name] if not table.empty else table
        density = (
            float(rows["Плотность фазы, кг/м³"].iloc[0]) if not rows.empty else None
        )
        status = (
            str(rows["Статус данных"].iloc[0]) if not rows.empty else "нет плотности"
        )
        phases[name] = {
            "мольная доля": float(kept[name]),
            "молярная масса, г/моль": molar_mass,
            "плотность, кг/м³": density,
            "статус плотности": status,
            # (г/моль) / (кг/м³) = 1e-3 кг/моль / (кг/м³) = 1e-3 м³/моль,
            # а 1 м³ = 1e6 см³, отсюда множитель 1e3 и единица см³/моль.
            "молярный объём, см³/моль": (
                1.0e3 * molar_mass / density if density else None
            ),
            "состав, мольные доли": composition,
            "состав, масс. %": w12.mass_percent(ctx, composition),
        }

    payload = {
        "T, °C": float(temperature_c),
        "pdens": int(pdens),
        "набор фаз": phase_set,
        "сумма мольных долей фаз": float(sum(kept.values())),
        "фаз": len(phases),
        "фазы": phases,
        "плотность сплава, кг/м³": physical.alloy_density_kg_m3,
        "качество плотности сплава": physical.quality_label,
        "покрытие по мольной доле, %": float(physical.mole_coverage_pct),
        "предупреждения расчёта": list(physical.warnings),
        "секунд": time.perf_counter() - started,
    }
    del physical
    gc.collect()
    return payload


def converged(payload: Mapping[str, Any]) -> bool:
    """Сошлась ли точка. Пустое решение и уехавшая сумма долей — не результат."""

    if not payload["фазы"]:
        return False
    return abs(float(payload["сумма мольных долей фаз"]) - 1.0) <= SUM_TOLERANCE


def solve_point(ctx: Any, restricted: Restricted, physical_db: Any,
                cache: PointCache, mole: Mapping[str, float],
                temperature_c: float, phase_set: str,
                label: str) -> dict[str, Any] | None:
    """Одна точка: из кэша либо счётом, с тем же рядом повторов, что у 12-2."""

    cached = cache.get(mole, temperature_c, phase_set)
    if cached is not None and converged(cached):
        return cached

    used_pdens = PDENS
    payload = volume_payload(ctx, restricted, physical_db, mole, temperature_c,
                             used_pdens, phase_set)
    retries: list[int] = []
    for retry_pdens in RETRY_PDENS:
        if converged(payload):
            break
        log(f"{label}: сумма долей {payload['сумма мольных долей фаз']:.6f} "
            f"при pdens={used_pdens}, повтор при pdens={retry_pdens}")
        retries.append(used_pdens)
        del payload
        gc.collect()
        used_pdens = retry_pdens
        payload = volume_payload(ctx, restricted, physical_db, mole,
                                 temperature_c, used_pdens, phase_set)

    payload["неудачные pdens"] = retries
    payload["сошлась"] = converged(payload)
    if not payload["сошлась"]:
        return None
    cache.put(mole, temperature_c, phase_set, payload)
    return payload


# --------------------------------------------------------------------------- #
# Объёмы
# --------------------------------------------------------------------------- #


def scaled_molar_volume(phase: str, block: Mapping[str, Any],
                        shift: float) -> float | None:
    """Молярный объём фазы при плотности P-фазы, сдвинутой на ``shift``.

    Сдвиг применяется только к P-фазе, и только потому, что её плотность —
    оценка по правилу смеси. У фаз с прямой DP-моделью объём не трогается.
    Объём обратен плотности: ρ·(1+s) даёт V/(1+s).
    """

    volume = block.get("молярный объём, см³/моль")
    if volume is None:
        return None
    if phase != PRECIPITATE_PHASE or shift == 0.0:
        return float(volume)
    return float(volume) / (1.0 + float(shift))


def mixture_volume(payload: Mapping[str, Any],
                   shift: float) -> tuple[float | None, float, list[str]]:
    """Молярный объём смеси фаз, см³/моль атомов, и покрытие по мольной доле.

    Фазы без плотности в расчёт объёма не берутся, а их суммарная доля
    возвращается отдельно: делать вид, что такой фазы нет, нельзя. Смесь
    нормируется на покрытую долю, то есть объём считается на моль атомов тех
    фаз, у которых объём есть.
    """

    covered = 0.0
    total = 0.0
    missing: list[str] = []
    for name, block in payload["фазы"].items():
        fraction = float(block["мольная доля"])
        volume = scaled_molar_volume(name, block, shift)
        if volume is None:
            missing.append(name)
            continue
        covered += fraction
        total += fraction * volume
    if covered <= 0.0:
        return None, 0.0, missing
    return total / covered, covered, missing


def band_label(shift: float) -> str:
    if shift == 0.0:
        return "номинальная"
    return f"{shift * 100.0:+.0f} %"


# --------------------------------------------------------------------------- #
# Счёт (идёт в потомке)
# --------------------------------------------------------------------------- #


def _child_result(points: Mapping[str, Any], sweep: Sequence[Any],
                  thermal: Mapping[str, Any], skipped: Sequence[Any],
                  ctx: Any, applied: Sequence[str], notices: Any,
                  wt: Mapping[str, float],
                  alloy: Mapping[str, float]) -> dict[str, Any]:
    """Единый вид результата потомка: и при полном прогоне, и при остановке."""

    return {
        "точки": dict(points),
        "развёртка": list(sweep),
        "тепловое": dict(thermal),
        "пропущено": list(skipped),
        "фаз в расчёте": len(ctx.phases),
        "фазы расчёта": list(ctx.phases),
        "исключено из расчёта": list(ctx.excluded_phases),
        "ремонт базы доступен": bool(ctx.repair_available),
        "перекрытия физической базы": list(applied),
        "предупреждения расчёта": sorted(notices),
        "состав сплава, масс. %": dict(wt),
        "состав сплава, мольные доли": dict(alloy),
    }


def e3_volume(min_free_gib: float, force: bool = False) -> dict[str, Any]:
    """Весь подпункт целиком. Считается в потомке."""

    cache = PointCache()
    if force:
        cache.records.clear()
        if cache.path.is_file():
            cache.path.unlink()

    free = w12.free_gib()
    if free < float(min_free_gib):
        return {
            "точки": {}, "развёртка": [], "тепловое": {},
            "пропущено": [{
                "что": None,
                "причина": (
                    f"свободной физической памяти {free:.2f} ГиБ при требуемых "
                    f"{float(min_free_gib):.1f} ГиБ; база не разбиралась, прогон "
                    f"не начинался"
                ),
            }],
            "фаз в расчёте": None, "фазы расчёта": [],
            "исключено из расчёта": [], "ремонт базы доступен": None,
            "перекрытия физической базы": [], "предупреждения расчёта": [],
            "состав сплава, масс. %": {}, "состав сплава, мольные доли": {},
        }

    from thermogar_physical import PhysicalDensityDatabase

    ctx = w11.Context()
    restricted = Restricted(ctx)
    physical_db = PhysicalDensityDatabase(str(ROOT / PDB_REL))
    applied = [
        f"{entry.name}: {entry.reason}"
        for entry in getattr(physical_db, "applied_overrides", ())
    ]
    log(f"перекрытий физической базы применено: {len(applied)}"
        + (f" ({', '.join(entry.name for entry in physical_db.applied_overrides)})"
           if applied else ""))

    wt = w11.full_wt()
    mole = w11.wt_to_mole(ctx, wt)
    alloy = normalised(mole)

    skipped: list[dict[str, Any]] = []
    points: dict[str, dict[str, Any]] = {}
    notices: set[str] = set()

    def take(composition: Mapping[str, float], temperature: float,
             phase_set: str, label: str) -> dict[str, Any] | None:
        free_now = w12.free_gib()
        if free_now < ABORT_FREE_GIB:
            skipped.append({
                "что": label,
                "причина": (
                    f"свободной физической памяти {free_now:.2f} ГиБ, ниже "
                    f"порога остановки {ABORT_FREE_GIB:.1f} ГиБ; остаток не "
                    f"считался"
                ),
            })
            return None
        try:
            payload = solve_point(ctx, restricted, physical_db, cache,
                                  composition, temperature, phase_set, label)
        except ValueError as error:
            # Отказ базы плотностей — это ответ базы, а не сбой счёта: считать
            # вне области определения DP-параметров она не берётся и правильно
            # делает. Такую точку пропускаем с дословной причиной.
            skipped.append({"что": label, "причина": str(error)})
            return None
        if payload is None:
            skipped.append({
                "что": label,
                "причина": (
                    f"не сошлась ни при одной из плотностей выборки "
                    f"{[PDENS, *RETRY_PDENS]}"
                ),
            })
            return None
        notices.update(payload.get("предупреждения расчёта", ()))
        return payload

    # --- равновесия в точках ТЗ и исходная пересыщенная матрица ------------- #
    log("--- равновесия в точках ТЗ: полный набор, двухфазный, однофазный ---")
    for temperature in E3_T_C:
        for phase_set in (FULL_SET, TWO_PHASE_SET, MATRIX_SET):
            label = f"{phase_set} @ {temperature:.0f} °C"
            payload = take(alloy, temperature, phase_set, label)
            if payload is None:
                return _child_result(points, [], {}, skipped, ctx, applied,
                                     notices, wt, alloy)
            points[f"{phase_set}|{temperature:.0f}"] = payload
            log(f"{label}: фаз {payload['фаз']}, {payload['секунд']:.1f} с")

    # --- тепловое расширение исходного состояния ---------------------------- #
    log("--- масштабная сверка: тепловое расширение того же сплава ---")
    thermal: dict[str, Any] = {}
    for temperature in THERMAL_T_C:
        key = f"{MATRIX_SET}|{temperature:.0f}"
        if key not in points:
            label = f"{MATRIX_SET} @ {temperature:.0f} °C"
            payload = take(alloy, temperature, MATRIX_SET, label)
            if payload is None:
                return _child_result(points, [], {}, skipped, ctx, applied,
                                     notices, wt, alloy)
            points[key] = payload
            log(f"{label}: {payload['секунд']:.1f} с")
        thermal[f"{temperature:.0f}"] = points[key]

    # --- развёртка по доле выделившейся P-фазы ------------------------------ #
    log("--- развёртка по доле выделившейся P-фазы ---")
    sweep: list[dict[str, Any]] = []
    for temperature in E3_T_C:
        base = points[f"{TWO_PHASE_SET}|{temperature:.0f}"]
        block = base["фазы"].get(PRECIPITATE_PHASE)
        if block is None:
            skipped.append({
                "что": f"развёртка @ {temperature:.0f} °C",
                "причина": "в двухфазном равновесии нет P-фазы",
            })
            continue
        precipitate_fraction = float(block["мольная доля"])
        precipitate = normalised(block["состав, мольные доли"])
        for share in FRACTION_GRID:
            composition = lever_matrix(alloy, precipitate,
                                       precipitate_fraction, share)
            label = f"матрица при доле {share:.2f} @ {temperature:.0f} °C"
            payload = take(composition, temperature, MATRIX_SET, label)
            if payload is None:
                return _child_result(points, sweep, thermal, skipped, ctx,
                                     applied, notices, wt, alloy)
            sweep.append({
                "T, °C": float(temperature),
                "доля выделения": float(share),
                "мольная доля P-фазы": precipitate_fraction * float(share),
                "равновесная мольная доля P-фазы": precipitate_fraction,
                "матрица": payload,
                "P-фаза": block,
            })
        log(f"развёртка @ {temperature:.0f} °C: {len(FRACTION_GRID)} узлов")

    return _child_result(points, sweep, thermal, skipped, ctx, applied,
                         notices, wt, alloy)


# --------------------------------------------------------------------------- #
# Таблицы
# --------------------------------------------------------------------------- #


def molar_volume_table(points: Mapping[str, Any]) -> pd.DataFrame:
    """Молярные объёмы всех фаз по температурам и наборам фаз."""

    rows: list[dict[str, Any]] = []
    for key, payload in points.items():
        phase_set = key.split("|")[0]
        for name, block in sorted(payload["фазы"].items()):
            rows.append({
                "T, °C": float(payload["T, °C"]),
                "набор фаз": phase_set,
                "фаза": name,
                "мольная доля, %": float(block["мольная доля"]) * 100.0,
                "молярная масса, г/моль": float(block["молярная масса, г/моль"]),
                "плотность, кг/м³": block["плотность, кг/м³"],
                "молярный объём, см³/моль": block["молярный объём, см³/моль"],
                "статус плотности": block["статус плотности"],
            })
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    return table.sort_values(["T, °C", "набор фаз", "фаза"]).reset_index(drop=True)


def change_table(points: Mapping[str, Any]) -> pd.DataFrame:
    """ΔV/V и ΔL/L по температурам, наборам фаз и полосе плотности P-фазы."""

    rows: list[dict[str, Any]] = []
    for temperature in E3_T_C:
        initial = points.get(f"{MATRIX_SET}|{temperature:.0f}")
        if initial is None:
            continue
        start_block = initial["фазы"].get(MATRIX_PHASE)
        if start_block is None or start_block["молярный объём, см³/моль"] is None:
            continue
        start_volume = float(start_block["молярный объём, см³/моль"])
        for phase_set in (TWO_PHASE_SET, FULL_SET):
            payload = points.get(f"{phase_set}|{temperature:.0f}")
            if payload is None:
                continue
            for shift in DENSITY_BAND:
                volume, covered, missing = mixture_volume(payload, shift)
                if volume is None:
                    continue
                relative = volume / start_volume - 1.0
                precipitate = payload["фазы"].get(PRECIPITATE_PHASE)
                rows.append({
                    "T, °C": float(temperature),
                    "набор фаз": phase_set,
                    "плотность P-фазы": band_label(shift),
                    "сдвиг плотности P-фазы": float(shift),
                    "доля P-фазы, мольн. %": (
                        float(precipitate["мольная доля"]) * 100.0
                        if precipitate else 0.0
                    ),
                    "V исходный, см³/моль": start_volume,
                    "V равновесный, см³/моль": volume,
                    "ΔV/V": relative,
                    "ΔV/V, %": relative * 100.0,
                    "ΔL/L": relative / 3.0,
                    "ΔL/L, %": relative / 3.0 * 100.0,
                    "покрытие плотностью, мольная доля": covered,
                    "фазы без плотности": "; ".join(missing),
                })
    return pd.DataFrame(rows)


def sweep_table(points: Mapping[str, Any],
                sweep: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """ΔV/V в зависимости от доли выделившейся P-фазы."""

    rows: list[dict[str, Any]] = []
    for record in sweep:
        temperature = float(record["T, °C"])
        initial = points.get(f"{MATRIX_SET}|{temperature:.0f}")
        if initial is None:
            continue
        start_block = initial["фазы"].get(MATRIX_PHASE)
        if start_block is None or start_block["молярный объём, см³/моль"] is None:
            continue
        start_volume = float(start_block["молярный объём, см³/моль"])
        matrix_block = record["матрица"]["фазы"].get(MATRIX_PHASE)
        if matrix_block is None or matrix_block["молярный объём, см³/моль"] is None:
            continue
        matrix_volume = float(matrix_block["молярный объём, см³/моль"])
        amount = float(record["мольная доля P-фазы"])
        for shift in DENSITY_BAND:
            precipitate_volume = scaled_molar_volume(
                PRECIPITATE_PHASE, record["P-фаза"], shift
            )
            if precipitate_volume is None:
                continue
            volume = (1.0 - amount) * matrix_volume + amount * precipitate_volume
            relative = volume / start_volume - 1.0
            rows.append({
                "T, °C": temperature,
                "доля выделения от равновесной": float(record["доля выделения"]),
                "мольная доля P-фазы, %": amount * 100.0,
                "плотность P-фазы": band_label(shift),
                "сдвиг плотности P-фазы": float(shift),
                "молярный объём матрицы, см³/моль": matrix_volume,
                "молярный объём P-фазы, см³/моль": precipitate_volume,
                "V, см³/моль": volume,
                "ΔV/V": relative,
                "ΔV/V, %": relative * 100.0,
                "ΔL/L": relative / 3.0,
                "ΔL/L, %": relative / 3.0 * 100.0,
            })
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    return table.sort_values(
        ["T, °C", "сдвиг плотности P-фазы", "доля выделения от равновесной"]
    ).reset_index(drop=True)


def thermal_table(thermal: Mapping[str, Any]) -> pd.DataFrame:
    """Тепловое расширение исходного состояния — масштаб для сверки.

    Считается тот же сплав в том же исходном состоянии (однофазная пересыщенная
    матрица), чтобы сравнивались две деформации одного и того же материала, а не
    деформация одного материала с расширением другого.
    """

    rows: list[dict[str, Any]] = []
    for low, high in THERMAL_PAIRS:
        start = thermal.get(f"{low:.0f}")
        finish = thermal.get(f"{high:.0f}")
        if start is None or finish is None:
            continue
        start_block = start["фазы"].get(MATRIX_PHASE)
        finish_block = finish["фазы"].get(MATRIX_PHASE)
        if start_block is None or finish_block is None:
            continue
        start_volume = start_block["молярный объём, см³/моль"]
        finish_volume = finish_block["молярный объём, см³/моль"]
        if start_volume is None or finish_volume is None:
            continue
        start_volume = float(start_volume)
        finish_volume = float(finish_volume)
        relative = finish_volume / start_volume - 1.0
        linear = relative / 3.0
        rows.append({
            "переход": f"{low:.0f} → {high:.0f} °C",
            "T нижняя, °C": float(low),
            "T верхняя, °C": float(high),
            "плотность при нижней, кг/м³": start_block["плотность, кг/м³"],
            "плотность при верхней, кг/м³": finish_block["плотность, кг/м³"],
            "V при нижней, см³/моль": start_volume,
            "V при верхней, см³/моль": finish_volume,
            "ΔV/V": relative,
            "ΔV/V, %": relative * 100.0,
            "ΔL/L": linear,
            "ΔL/L, %": linear * 100.0,
            "средний коэффициент линейного расширения, 1/К": (
                linear / (high - low) if high != low else None
            ),
        })
    return pd.DataFrame(rows)


def reference_table(points: Mapping[str, Any]) -> pd.DataFrame:
    """Сверка молярных объёмов с опорными числами подпункта 12-1.

    Опорные числа лежат в `results/hn62m_wave12/cache/k1_volumes.json` и
    получены полным равновесием, поэтому сверяется полный набор фаз.
    """

    path = CACHE / REFERENCE_NAME
    if not path.is_file():
        return pd.DataFrame()
    stored = json.loads(path.read_text("utf-8"))["молярные объёмы"]
    rows: list[dict[str, Any]] = []
    for _, block in sorted(stored.items(), key=lambda item: float(item[0])):
        temperature = float(block["T, °C"])
        payload = points.get(f"{FULL_SET}|{temperature:.0f}")
        if payload is None:
            continue
        for phase in (MATRIX_PHASE, PRECIPITATE_PHASE):
            if phase not in block or phase not in payload["фазы"]:
                continue
            reference = float(block[phase]["молярный объём, см³/моль"])
            here = payload["фазы"][phase]["молярный объём, см³/моль"]
            if here is None:
                continue
            here = float(here)
            rows.append({
                "T, °C": temperature,
                "фаза": phase,
                "12-1, см³/моль": reference,
                "12-3, см³/моль": here,
                "разность, см³/моль": here - reference,
                "совпало": bool(abs(here - reference) <= REFERENCE_TOLERANCE),
            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Рисунок
# --------------------------------------------------------------------------- #


def plot_e3(change: pd.DataFrame, sweep: pd.DataFrame, thermal: pd.DataFrame,
            path: Path) -> None:
    """Слева — ΔL/L по точкам ТЗ на фоне теплового, справа — развёртка по доле."""

    figure, axes = plt.subplots(1, 2, figsize=(13.0, 5.5))
    colours = ("#1f77b4", "#2ca02c", "#d62728")

    left = axes[0]
    block = change[change["набор фаз"] == TWO_PHASE_SET]
    width = 12.0
    for offset, (shift, colour) in enumerate(zip(DENSITY_BAND, colours)):
        part = block[block["сдвиг плотности P-фазы"] == shift]
        if part.empty:
            continue
        left.bar(part["T, °C"] + (offset - 1) * width, part["ΔL/L, %"],
                 width=width, color=colour, alpha=0.8,
                 label=f"ρ(P) {band_label(shift)}")
    for _, row in thermal.iterrows():
        left.axhline(float(row["ΔL/L, %"]), linestyle="--", linewidth=1.0,
                     color="black", alpha=0.6)
        left.annotate(f"тепловое {row['переход']}: {row['ΔL/L, %']:+.3f} %",
                      xy=(float(E3_T_C[0]) - 25.0, float(row["ΔL/L, %"])),
                      fontsize=7, va="bottom")
    left.axhline(0.0, color="black", linewidth=0.8)
    left.set_xlabel("температура, °C")
    left.set_ylabel("ΔL/L, %")
    left.set_title("Линейная деформация от выделения P-фазы\n"
                   "на фоне теплового расширения")
    left.legend(fontsize=8)
    left.grid(axis="y", alpha=0.3)

    right = axes[1]
    for temperature, style in ((700.0, "-"), (750.0, "--")):
        for shift, colour in zip(DENSITY_BAND, colours):
            part = sweep[(sweep["T, °C"] == temperature)
                         & (sweep["сдвиг плотности P-фазы"] == shift)]
            if part.empty:
                continue
            right.plot(part["доля выделения от равновесной"], part["ΔV/V, %"],
                       style, color=colour,
                       label=f"{temperature:.0f} °C, ρ(P) {band_label(shift)}")
    right.axhline(0.0, color="black", linewidth=0.8)
    right.axvspan(0.97, 1.0, color="grey", alpha=0.15)
    right.annotate("200 ч по 12-1: 97…99 %", xy=(0.55, 0.02),
                   xycoords="axes fraction", fontsize=8)
    right.set_xlabel("доля выделившейся P-фазы от равновесной")
    right.set_ylabel("ΔV/V, %")
    right.set_title("Изменение объёма по ходу выделения")
    right.legend(fontsize=7)
    right.grid(alpha=0.3)

    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


# --------------------------------------------------------------------------- #
# Служебное: имена файлов подпункта
# --------------------------------------------------------------------------- #


def write_csv(table: pd.DataFrame, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    table.to_csv(path, **CSV_WRITE)
    log(f"записано {path.relative_to(ROOT)} ({len(table)} строк)")
    return path


def memory_report(stem: str, record: Mapping[str, Any], seconds: float,
                  final: bool = True) -> Path | None:
    """Итог замера памяти. Устроен как у 12-2, но с префиксом подпункта 12-3."""

    if not record.get("замеров"):
        return None
    payload: dict[str, Any] = {
        key: (round(value, 3) if isinstance(value, float) else value)
        for key, value in record.items()
    }
    payload.pop("начало, perf_counter", None)
    payload["секунд под наблюдением"] = round(seconds, 1)
    payload["шаг опроса, с"] = w11.MEMORY_POLL_SECONDS
    payload["замер завершён"] = bool(final)
    payload["прирост занятой подкачки в системе, ГиБ"] = round(
        float(record["максимум занятой подкачки в системе, ГиБ"])
        - float(record["занято подкачки до старта, ГиБ"]), 3
    )
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{PREFIX}_memory_{stem}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    if final:
        log(
            f"память: пик набора {payload['пик рабочего набора дерева, ГиБ']:.2f} ГиБ, "
            f"минимум свободной {payload['минимум свободной физической, ГиБ']:.2f} ГиБ, "
            f"прирост подкачки "
            f"{payload['прирост занятой подкачки в системе, ГиБ']:+.2f} ГиБ"
        )
    return path


def memory_watch(process: Any, stop: Any, record: dict[str, Any],
                 stem: str) -> None:
    """Фоновый опрос памяти потомка. Замер — `w11.memory_probe`, без своего.

    Своя копия нужна ровно из-за одной строки: промежуточный сброс зовёт
    `memory_report` этого модуля, иначе файл замера уехал бы под префиксом
    подпункта 12-2.
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
    started = float(record.get("начало, perf_counter", time.perf_counter()))
    while not stop.wait(w11.MEMORY_POLL_SECONDS):
        probe = w11.memory_probe(process)
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
        if now - flushed >= w11.MEMORY_FLUSH_SECONDS:
            memory_report(stem, record, now - started, final=False)
            flushed = now


def run_child(arguments: Sequence[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Тяжёлый кусок — в отдельном процессе, результат приходит файлом.

    Своя копия механизма волны 12-2 нужна по одной причине: `w12.run_child`
    запускает `Path(__file__)` своего модуля, то есть саму волну 12-2. Всё, что
    можно было взять оттуда без правок, взято. То же решение и та же причина,
    что в подпунктах 12-1, 12-4 и 12-5.
    """

    stem = "_".join(argument.strip("-").replace(".", "_").replace(",", "_")
                    for argument in arguments)
    handoff = CACHE / f"child_{PREFIX}_{stem}.json"
    CACHE.mkdir(parents=True, exist_ok=True)
    if handoff.is_file():
        handoff.unlink()
    environment = dict(os.environ, PYTHONHASHSEED="0")
    command = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
               *arguments, "--handoff", str(handoff)]

    started = time.perf_counter()
    popen = subprocess.Popen(command, env=environment, cwd=str(ROOT))
    record: dict[str, Any] = {"подпункт": stem, "начало, perf_counter": started}
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
    seconds = time.perf_counter() - started
    if watcher is not None:
        watcher.join(timeout=w11.MEMORY_POLL_SECONDS * 2)
        memory_report(stem, record, seconds)

    if returncode != 0 or not handoff.is_file():
        raise RuntimeError(
            f"потомок {' '.join(arguments)} завершился с кодом {returncode}"
        )
    measurement = {
        key: value for key, value in record.items() if key != "начало, perf_counter"
    }
    measurement["секунд прогона"] = round(seconds, 1)
    if record.get("замеров"):
        measurement["прирост занятой подкачки в системе, ГиБ"] = round(
            float(record["максимум занятой подкачки в системе, ГиБ"])
            - float(record["занято подкачки до старта, ГиБ"]), 3
        )
    return json.loads(handoff.read_text("utf-8")), measurement


# --------------------------------------------------------------------------- #
# Сводка
# --------------------------------------------------------------------------- #


def sign_verdict(change: pd.DataFrame) -> dict[str, Any]:
    """Меняет ли знак ΔV/V внутри полосы погрешности плотности P-фазы.

    Это главный вопрос подпункта по части честности. Если на одной и той же
    температуре при −10 % плотности P-фазы объём растёт, а при +10 % падает,
    расчёт не устанавливает даже направления изменения объёма. Никакой подгонки:
    вывод берётся из знаков посчитанного.
    """

    verdict: dict[str, Any] = {}
    for phase_set in (TWO_PHASE_SET, FULL_SET):
        block = change[change["набор фаз"] == phase_set]
        rows: dict[str, Any] = {}
        for temperature in E3_T_C:
            part = block[block["T, °C"] == temperature]
            if part.empty:
                continue
            values = [float(value) for value in part["ΔV/V"]]
            nominal = part[part["сдвиг плотности P-фазы"] == 0.0]
            rows[f"{temperature:.0f}"] = {
                "ΔV/V минимум": min(values),
                "ΔV/V максимум": max(values),
                "знак меняется внутри полосы": bool(min(values) < 0.0 < max(values)),
                "номинальный ΔV/V": (
                    float(nominal["ΔV/V"].iloc[0]) if not nominal.empty else None
                ),
            }
        verdict[phase_set] = {
            "по температурам": rows,
            "знак меняется хотя бы в одной точке": any(
                value["знак меняется внутри полосы"] for value in rows.values()
            ),
        }
    return verdict


def step_e3(force: bool = False, min_free_gib: float = MIN_FREE_GIB) -> None:
    progress = w12.load_progress()
    if progress.get("12-3", {}).get("готов") and not force:
        log("12-3 пропущен, посчитан ранее (--force для пересчёта)")
        return

    free = w12.free_gib()
    cache_ready = (CACHE / f"{PREFIX}_points.jsonl").is_file() and not force
    if free < float(min_free_gib) and not cache_ready:
        w12.write_json({
            "подпункт": ("12-3. Изменение объёма при выделении P-фазы и "
                         "вальцованное соединение"),
            "прогон": "не начинался",
            "причина": (
                f"свободной физической памяти {free:.2f} ГиБ при требуемых "
                f"{float(min_free_gib):.1f} ГиБ"
            ),
            "порог входа, ГиБ": float(min_free_gib),
            "порог по умолчанию (w12.MIN_FREE_GIB), ГиБ": MIN_FREE_GIB,
        }, f"{PREFIX}_summary.json")
        log(f"12-3 не запускался: свободно {free:.2f} ГиБ при требуемых "
            f"{float(min_free_gib):.1f} ГиБ")
        return

    arguments = ["--e3", "1", "--min-free-gib", f"{float(min_free_gib):g}"]
    if force:
        arguments.append("--force")
    payload, measurement = run_child(arguments)
    measurement["свободной физической перед запуском, ГиБ"] = round(free, 2)

    points = payload["точки"]
    volumes = molar_volume_table(points)
    write_csv(volumes, f"{PREFIX}_molar_volumes.csv")
    change = change_table(points)
    write_csv(change, f"{PREFIX}_volume_change.csv")
    sweep = sweep_table(points, payload["развёртка"])
    write_csv(sweep, f"{PREFIX}_fraction.csv")
    thermal = thermal_table(payload["тепловое"])
    write_csv(thermal, f"{PREFIX}_thermal.csv")
    reference = reference_table(points)
    write_csv(reference, f"{PREFIX}_reference_check.csv")
    if not change.empty and not sweep.empty and not thermal.empty:
        plot_e3(change, sweep, thermal, OUT / f"{PREFIX}_volume.png")

    verdict = sign_verdict(change) if not change.empty else {}
    scale: list[dict[str, Any]] = []
    if not change.empty and not thermal.empty:
        block = change[change["набор фаз"] == TWO_PHASE_SET]
        nominal_block = block[block["сдвиг плотности P-фазы"] == 0.0]
        # Сравнивать надо оба числа сразу, иначе сравнение врёт в любую сторону:
        # номинальное ΔL/L мало до незаметности, а полоса по погрешности
        # плотности P-фазы — того же порядка, что всё тепловое расширение.
        nominal = (
            float(nominal_block["ΔL/L"].abs().max())
            if not nominal_block.empty else 0.0
        )
        largest = float(block["ΔL/L"].abs().max()) if not block.empty else 0.0
        for _, row in thermal.iterrows():
            thermal_linear = abs(float(row["ΔL/L"]))
            scale.append({
                "переход": row["переход"],
                "тепловое |ΔL/L|": thermal_linear,
                "номинальное |ΔL/L| от выделения (двухфазный набор)": nominal,
                "во сколько раз тепловое больше номинального": (
                    thermal_linear / nominal if nominal > 0.0 else None
                ),
                "наибольшее |ΔL/L| по полосе погрешности (двухфазный набор)":
                    largest,
                "во сколько раз тепловое больше края полосы": (
                    thermal_linear / largest if largest > 0.0 else None
                ),
            })

    summary = {
        "подпункт": ("12-3. Изменение объёма при выделении P-фазы: удельный "
                     "объём, ΔV/V, ΔL/L и полоса по плотности P-фазы"),
        "база": DB_REL,
        "sha256 базы": w12.database_sha256(),
        "база плотностей": PDB_REL,
        "ремонт базы доступен": payload["ремонт базы доступен"],
        "фаз в расчёте": payload["фаз в расчёте"],
        "исключено из расчёта": payload["исключено из расчёта"],
        "температуры ТЗ, °C": list(E3_T_C),
        "температуры сверки по теплу, °C": list(THERMAL_T_C),
        "состав сплава, масс. %": payload["состав сплава, масс. %"],
        "наборы фаз": {
            FULL_SET: "все фазы базы — штатный путь приложения",
            TWO_PHASE_SET: f"{MATRIX_PHASE} + {PRECIPITATE_PHASE}",
            MATRIX_SET: f"{MATRIX_PHASE} один — исходная пересыщенная матрица",
        },
        "полоса по плотности P-фазы": [band_label(shift) for shift in DENSITY_BAND],
        "сетка по доле выделения": list(FRACTION_GRID),
        "перекрытия физической базы применены": payload["перекрытия физической базы"],
        "предупреждения расчёта": payload["предупреждения расчёта"],
        "сверка с 12-1 (k1_volumes.json)": (
            reference.to_dict("records") if not reference.empty else []
        ),
        "сверка сошлась": (
            bool(reference["совпало"].all()) if not reference.empty else None
        ),
        "ΔV/V и ΔL/L": change.to_dict("records") if not change.empty else [],
        "тепловое расширение": (
            thermal.to_dict("records") if not thermal.empty else []
        ),
        "масштабная сверка": scale,
        "меняется ли знак ΔV/V внутри полосы": verdict,
        "pdens": PDENS,
        "ряд повторов pdens": list(RETRY_PDENS),
        "порог входа по свободной памяти": {
            "по умолчанию (w12.MIN_FREE_GIB, он же w11.J2_MIN_FREE_GIB), ГиБ":
                MIN_FREE_GIB,
            "объявлен заданием 12-3, ГиБ": TASK_MIN_FREE_GIB,
            "фактический в этом прогоне, ГиБ": float(min_free_gib),
            "понижен относительно умолчания": float(min_free_gib) < MIN_FREE_GIB,
            "обоснование": (
                f"подпункт 12-5 устроен так же и показал пик рабочего набора "
                f"{JUSTIFY_PEAK_SET_GIB:.3f} ГиБ при пике фиксации "
                f"{JUSTIFY_PEAK_COMMIT_GIB:.3f} ГиБ ({JUSTIFY_SOURCE})"
            ),
        },
        "порог остановки по ходу, свободной физической ГиБ": ABORT_FREE_GIB,
        "порог присутствия фазы, мольные доли": PRESENT_FLOOR,
        "допуск на сумму мольных долей": SUM_TOLERANCE,
        "пропущено": payload["пропущено"],
        "замер памяти": measurement,
        "чего расчёт не устанавливает": [
            "контактное давление вальцовки и усилие вырыва — это механика, "
            "её в проекте нет вовсе",
            "ползучесть и релаксацию контактного давления",
            "плотность P-фазы — оценка по правилу смеси с погрешностью до 10 %, "
            "своей модели плотности в physical_data_v103.pdb у неё нет",
            "скандия в mc_ni 2.036 нет; счёт идёт по основе сплава ЭК199-ВИ",
            "фосфора в mc_ni 2.036 нет, а в марке он до 0,025 %",
            "равновесие не говорит о временах: когда доля будет набрана — "
            "вопрос подпункта 12-1",
            "состав P-фазы на промежуточной доле принят равным равновесному",
        ],
    }
    w12.write_json(summary, f"{PREFIX}_summary.json")

    complete = not payload["пропущено"] and not change.empty
    progress["12-3"] = {
        "готов": complete,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "точек равновесия": len(points),
        "узлов развёртки": len(payload["развёртка"]),
        "пропущено": len(payload["пропущено"]),
        "pdens": PDENS,
        "порог входа, ГиБ": float(min_free_gib),
    }
    w12.save_progress(progress)


STEPS = {"e3": step_e3}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=("Волна 12, подпункт 12-3: изменение объёма при выделении "
                     "P-фазы")
    )
    parser.add_argument("--only", default="all", help="e3; через запятую")
    parser.add_argument("--force", action="store_true", help="пересчитать готовое")
    parser.add_argument(
        "--min-free-gib", type=float, default=MIN_FREE_GIB,
        help=("порог входа по свободной физической памяти, ГиБ; умолчание — "
              "значение волны 11. Аварийный порог по ходу счёта ключа не имеет"),
    )
    parser.add_argument("--e3", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--handoff", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    if args.e3 is not None:
        payload = e3_volume(min_free_gib=args.min_free_gib, force=args.force)
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
        STEPS[name](force=args.force, min_free_gib=args.min_free_gib)
        log(f"=== {name.upper()} готов за {time.perf_counter() - started:.1f} с ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
