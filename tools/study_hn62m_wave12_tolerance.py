#!/usr/bin/env python3
"""Волна 12, подпункт 12-5 — углы марочного допуска ЭК199-ВИ при 700 и 750 °C.

Задание `tasks/WAVE12_5_OPUS.md`. Вопрос подпункта: насколько плавка, целиком
укладывающаяся в марку, может оказаться хуже контрольного состава по доле
P-фазы и по обеднению матрицы молибденом. Ответ нужен для спецификации на
поставку, поэтому считается не «середина марки», а её углы.

Метод двухступенчатый, полный перебор углов не делается.

* **Ступень А** — отсев по одному элементу: каждый элемент, для которого в
  репозитории есть марочные пределы, ставится на нижний и на верхний предел,
  остальные остаются в контрольном значении, никель пересчитывается в основу
  (`w11.full_wt`). Обе температуры. Цель — узнать, какие элементы вообще
  двигают долю P-фазы и молибден в матрице.
* **Ступень Б** — полный перебор углов по нескольким элементам, отобранным
  ступенью А по величине сдвига (`--stage-b-elements`, по умолчанию 4, то есть
  16 углов), плюс два собранных состава: «худший» — каждый элемент с
  пределами на том пределе, который ступень А назвала ухудшающим, и «лучший» —
  на противоположном.

Откуда взяты марочные пределы. Из репозитория, а не из стандарта в руках:
`tools/study_hn62m.py`, `CORNER_LIMITS` и `CORNER_FE` (волна 9), первоисточник
в репозитории — `tasks/WAVE9_HN62M_OPUS.md`, строка 16: «Границы марки для
расчёта по углам: Cr 23,0/24,0 · Mo 12,0/14,0 · Ti 0,03/0,16 · Nb 0,02/0,10 ·
Fe 0/0,50». Пределов на C, Si, Mn, S и Al в репозитории нет нигде, поэтому эти
пять элементов остаются в контрольном значении и в ступени А не участвуют;
позиция на ТУ или ГОСТ заведена в `tasks/SOURCES_WANTED.md`. Числа по памяти
не подставляются (`tasks/RULES.md`, раздел «Источники»).

Модуль не переписывает волну 12-2, а импортирует из неё разбор точки, кэш,
пороги, формат CSV и замер памяти; марочные пределы импортируются из волны 9.
Своими остались только те служебные функции, которые привязаны к имени файла
или к префиксу подпункта: `run_child` запускает `Path(__file__)`, а
`memory_report` кладёт файл под префиксом `e5`. Та же причина и то же решение,
что в подпунктах 12-1 и 12-4.

Запуск (интерпретатор — venv основного репозитория, PYTHONHASHSEED=0):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 ^
        tools\\study_hn62m_wave12_tolerance.py --only e5 --min-free-gib 2.5

Память. Порог входа — параметр задачи (`tasks/RULES.md`, раздел «Память и
параллельность»), и задаётся он ключом `--min-free-gib`, а не правкой
константы: константа остаётся общей и импортируемой (`w12.MIN_FREE_GIB`, он же
`w11.J2_MIN_FREE_GIB` = 4,0 ГиБ), фактическое значение уходит в сводку рядом с
умолчанием. Для этого подпункта объявлено 2,5 ГиБ. Обоснование числом:
равновесный прогон 12-2 устроен так же (та же база, тот же состав по числу
компонентов, тот же `pdens`, тот же разбор точки) и показал пик рабочего
набора дерева 1,355 ГиБ при пике фиксации 2,219 ГиБ
(`results/hn62m_wave12/e1_memory_e1_1_force.json`). Порог 2,5 ГиБ покрывает
измеренную фиксацию с запасом и не требует 4,0 ГиБ, которых на этой машине при
занятой посторонними памяти может не быть. Аварийный порог по ходу счёта —
другая величина (`w12.E1_ABORT_FREE_GIB`), ключа не имеет и не понижается.

Кэш обязателен: прогон могут снять посторонние процессы, и каждая сошедшаяся
точка уходит на диск сразу (`cache/e5_points.jsonl`). Ключ кэша — состав и
температура, поэтому совпавшие составы (например, верхний предел Fe и
контрольный состав, у которых Fe одинаков) считаются один раз.

Границы достоверности живут в отчёте. Здесь называется только то, что видно из
кода: скандия в списке компонентов нет, потому что его нет в mc_ni; фосфора там
тоже нет; расчёт равновесный и о временах появления фаз не говорит ничего.
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
import study_hn62m as w9

ROOT = w12.ROOT
OUT = w12.OUT
CACHE = w12.CACHE

CSV_WRITE = dict(w12.CSV_WRITE)
log = w12.log

# Префикс подпункта в именах результатов. Волна 12 уже занимает e1 (12-2),
# e4 (12-4) и k1 (12-1).
PREFIX = "e5"

DB_REL = w12.DB_REL
COMPONENTS: tuple[str, ...] = tuple(w12.COMPONENTS)
ELEMENT_ORDER: tuple[str, ...] = tuple(w12.ELEMENT_ORDER)

# Пороги памяти — значения волны 12-2, а не свои.
MIN_FREE_GIB = w12.MIN_FREE_GIB
ABORT_FREE_GIB = w12.E1_ABORT_FREE_GIB

# Измеренный пик равновесного прогона 12-2, которым обосновывается порог входа
# этого подпункта.
JUSTIFY_PEAK_SET_GIB = 1.355
JUSTIFY_PEAK_COMMIT_GIB = 2.219
JUSTIFY_SOURCE = "results/hn62m_wave12/e1_memory_e1_1_force.json"
TASK_MIN_FREE_GIB = 2.5

# Плотность выборки и ряд повторов — волны 12-2, иначе числа двух подпунктов
# окажутся несравнимы.
PDENS = w12.E1_PDENS
RETRY_PDENS: tuple[int, ...] = tuple(w12.E1_RETRY_PDENS)

PRESENT_FLOOR = w12.E1_PRESENT_FLOOR
VISIBLE_FLOOR = w12.E1_VISIBLE_FLOOR
SUM_TOLERANCE = w12.E1_SUM_TOLERANCE

TCP_PHASES = tuple(w12.E1_TCP_PHASES)
ORDERING_PHASES = tuple(w12.E1_ORDERING_PHASES)
MATRIX_PHASE = w12.E1_MATRIX_PHASE
MATRIX_ELEMENTS: tuple[str, ...] = tuple(w12.E1_MATRIX_ELEMENTS)

# --- 12-5 ------------------------------------------------------------------ #

# Температуры подпункта.
TOL_T_C: tuple[float, ...] = (700.0, 750.0)

# Марочные пределы. Значения не набираются здесь заново, а берутся из волны 9.
GRADE_LIMITS: dict[str, tuple[float, float]] = {
    element: (float(low), float(high))
    for element, (low, high) in w9.CORNER_LIMITS.items()
}
# Железо волна 9 в углах не варьировала (`CORNER_FE = 0.5`), но пределы на него
# в её задании названы: «Fe 0/0,50». Нижний предел 0 — это «железо не
# требуется», а не «железа ноль»: с X(FE) = 0 равновесие не ставится, поэтому
# вместо нуля берётся следовое значение, и оно названо в таблицах и в сводке.
GRADE_LIMITS["FE"] = (0.0, float(w9.CORNER_FE))
TRACE_WT = 1.0e-3

# Элементы марки, пределов на которые в репозитории нет. Они остаются в
# контрольном значении; выдумывать их пределы правила проекта запрещают.
WITHOUT_LIMITS: tuple[str, ...] = tuple(
    element for element in sorted(w11.CONTROL_WT) if element not in GRADE_LIMITS
)

GRADE_SOURCE = (
    "tools/study_hn62m.py: CORNER_LIMITS и CORNER_FE (волна 9); первоисточник "
    "в репозитории — tasks/WAVE9_HN62M_OPUS.md, строка 16"
)

# Порядок элементов в таблицах ступеней.
LIMIT_ELEMENTS: tuple[str, ...] = tuple(
    element for element in ("CR", "MO", "TI", "NB", "FE") if element in GRADE_LIMITS
)

STAGE_B_DEFAULT = 4


# --------------------------------------------------------------------------- #
# Составы
# --------------------------------------------------------------------------- #


def overrides_to_wt(overrides: Mapping[str, float]) -> dict[str, float]:
    """Массовые проценты состава: контрольный состав с заменами, Ni — основа."""

    replaced = {
        element: (TRACE_WT if value <= 0.0 else float(value))
        for element, value in overrides.items()
    }
    return w11.full_wt(replaced)


def case_label(overrides: Mapping[str, float]) -> str:
    if not overrides:
        return "контроль"
    return " · ".join(
        f"{element} {value:g}" for element, value in sorted(overrides.items())
    )


def stage_a_cases() -> list[dict[str, Any]]:
    """Контрольный состав и по два случая на каждый элемент с пределами."""

    cases: list[dict[str, Any]] = [{
        "ступень": "контроль",
        "случай": "контроль",
        "элемент": "",
        "предел": "",
        "переопределения": {},
    }]
    for element in LIMIT_ELEMENTS:
        low, high = GRADE_LIMITS[element]
        for name, value in (("нижний", low), ("верхний", high)):
            cases.append({
                "ступень": "А",
                "случай": f"{element} {name}",
                "элемент": element,
                "предел": name,
                "переопределения": {element: value},
            })
    return cases


def stage_b_cases(order: Sequence[str], worsening: Mapping[str, str],
                  width: int) -> list[dict[str, Any]]:
    """Полный перебор углов по отобранным элементам плюс два крайних состава."""

    chosen = list(order[:width])
    cases: list[dict[str, Any]] = []
    for mask in range(2 ** len(chosen)):
        overrides: dict[str, float] = {}
        for bit, element in enumerate(chosen):
            low, high = GRADE_LIMITS[element]
            overrides[element] = high if (mask >> bit) & 1 else low
        cases.append({
            "ступень": "Б",
            "случай": f"угол {case_label(overrides)}",
            "элемент": "",
            "предел": "",
            "переопределения": overrides,
        })

    for kind in ("худший", "лучший"):
        overrides = {}
        for element in LIMIT_ELEMENTS:
            low, high = GRADE_LIMITS[element]
            bad = worsening.get(element, "верхний")
            take_high = (bad == "верхний") if kind == "худший" else (bad != "верхний")
            overrides[element] = high if take_high else low
        cases.append({
            "ступень": "Б",
            "случай": f"собранный {kind}",
            "элемент": "",
            "предел": "",
            "переопределения": overrides,
        })
    return cases


# --------------------------------------------------------------------------- #
# Кэш точек
# --------------------------------------------------------------------------- #


class PointCache(w12.PointCache):
    """Кэш подпункта 12-5: механизм волны 12-2, свой файл.

    Файл свой, а не общий с 12-2, по правилу владения файлами: чужой кэш этот
    подпункт не дописывает. Ключ (состав и температура) и запись строкой с
    ``fsync`` — оттуда же, без изменений.
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


# --------------------------------------------------------------------------- #
# Сжатый разбор точки
# --------------------------------------------------------------------------- #


def phase_label(name: str) -> str | None:
    """Имя фазы постановки по имени фазы в mc_ni, если оно там названо."""

    for label, names in (*TCP_PHASES, *ORDERING_PHASES):
        if name in names:
            return label
    return None


def reduce_point(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Из полного разбора точки — то, что нужно таблицам подпункта.

    Полный разбор остаётся в кэше; в передачу родителю и в таблицы уходят доли
    фаз и состав матрицы. Составы остальных фаз здесь не нужны: вопрос задачи —
    доля P-фазы и обеднение матрицы.
    """

    phases = payload["фазы"]
    matrix = phases.get(MATRIX_PHASE)
    reduced: dict[str, Any] = {
        "T, °C": float(payload["T, °C"]),
        "pdens": int(payload["pdens"]),
        "сошлась": bool(payload.get("сошлась", True)),
        "сумма мольных долей фаз": float(payload["сумма мольных долей фаз"]),
        "фазы": {
            name: float(block["мольная доля"]) for name, block in phases.items()
        },
        "матрица есть": matrix is not None,
        "мольная доля матрицы": float(matrix["мольная доля"]) if matrix else None,
        "матрица, масс. %": (
            {element: float(matrix["состав, масс. %"].get(element, 0.0))
             for element in ELEMENT_ORDER}
            if matrix else {}
        ),
    }
    for label, names in (*TCP_PHASES, *ORDERING_PHASES):
        reduced[f"доля {label}"] = sum(
            reduced["фазы"].get(name, 0.0) for name in names
        )
    return reduced


# --------------------------------------------------------------------------- #
# Счёт (идёт в потомке)
# --------------------------------------------------------------------------- #


def solve_case(ctx: Any, cache: PointCache, case: Mapping[str, Any],
               temperature: float) -> tuple[dict[str, Any] | None,
                                             dict[str, Any] | None]:
    """Одна точка: из кэша либо счётом. Возврат — (сжатая точка, пропуск)."""

    wt = overrides_to_wt(case["переопределения"])
    mole = w11.wt_to_mole(ctx, wt)

    cached = cache.get(mole, temperature)
    if cached is not None and w12.converged(cached):
        log(f"{case['случай']} @ {temperature:.0f} °C из кэша")
        return reduce_point(cached), None

    free = w12.free_gib()
    if free < ABORT_FREE_GIB:
        return None, {
            "случай": case["случай"],
            "T, °C": float(temperature),
            "причина": (
                f"свободной физической памяти {free:.2f} ГиБ, ниже порога "
                f"остановки {ABORT_FREE_GIB:.1f} ГиБ; остаток не считался"
            ),
        }

    used_pdens = PDENS
    payload = w12.point_payload(ctx, mole, temperature, used_pdens)
    retries: list[int] = []
    for retry_pdens in RETRY_PDENS:
        if w12.converged(payload):
            break
        log(f"{case['случай']} @ {temperature:.0f} °C: сумма долей "
            f"{payload['сумма мольных долей фаз']:.6f} при pdens={used_pdens}, "
            f"повтор при pdens={retry_pdens}")
        retries.append(used_pdens)
        del payload
        gc.collect()
        used_pdens = retry_pdens
        payload = w12.point_payload(ctx, mole, temperature, used_pdens)

    payload["неудачные pdens"] = retries
    payload["сошлась"] = w12.converged(payload)
    if not payload["сошлась"]:
        return None, {
            "случай": case["случай"],
            "T, °C": float(temperature),
            "причина": (
                f"не сошлась ни при одной из плотностей выборки "
                f"{[PDENS, *RETRY_PDENS]}: сумма мольных долей фаз "
                f"{payload['сумма мольных долей фаз']:.6f}, фаз {payload['фаз']}"
            ),
        }

    cache.put(mole, temperature, payload)
    reduced = reduce_point(payload)
    log(f"{case['случай']} @ {temperature:.0f} °C: фаз {payload['фаз']}, "
        f"P {reduced['доля P'] * 100.0:.2f} мольн. %, {payload['секунд']:.1f} с")
    del payload
    gc.collect()
    return reduced, None


def run_cases(ctx: Any, cache: PointCache, cases: Sequence[Mapping[str, Any]],
              done: dict[str, dict[str, Any]],
              skipped: list[dict[str, Any]]) -> None:
    """Посчитать список случаев на обеих температурах, дописывая в ``done``."""

    for case in cases:
        if case["случай"] in done:
            continue
        wt = overrides_to_wt(case["переопределения"])
        record: dict[str, Any] = {
            key: value for key, value in case.items() if key != "переопределения"
        }
        record["переопределения"] = dict(case["переопределения"])
        record["состав, масс. %"] = wt
        record["точки"] = {}
        for temperature in TOL_T_C:
            reduced, skip = solve_case(ctx, cache, case, temperature)
            if skip is not None:
                skipped.append(skip)
                return
            record["точки"][f"{temperature:.0f}"] = reduced
        done[case["случай"]] = record


def shift_metrics(record: Mapping[str, Any],
                  control: Mapping[str, Any]) -> dict[str, float]:
    """Сдвиги случая относительно контрольного состава по обеим температурам."""

    metrics: dict[str, float] = {}
    for temperature in TOL_T_C:
        key = f"{temperature:.0f}"
        point = record["точки"].get(key)
        base = control["точки"].get(key)
        if point is None or base is None:
            continue
        metrics[f"ΔP {key}"] = float(point["доля P"]) - float(base["доля P"])
        for element in MATRIX_ELEMENTS:
            metrics[f"Δ{element} {key}"] = (
                float(point["матрица, масс. %"].get(element, 0.0))
                - float(base["матрица, масс. %"].get(element, 0.0))
            )
    return metrics


def rank_elements(done: Mapping[str, Any]) -> tuple[list[str], dict[str, str],
                                                    dict[str, dict[str, float]]]:
    """Ранжирование элементов ступени А и направление ухудшения по каждому.

    Ранг — наибольший по двум температурам модуль сдвига доли P-фазы между
    нижним и верхним пределом элемента. Ухудшающим считается тот предел, при
    котором доля P-фазы больше (в среднем по двум температурам): вопрос задачи
    поставлен по P-фазе, а обеднение матрицы молибденом идёт с ней заодно и
    выносится в таблицу отдельной колонкой, чтобы расхождение было видно.
    """

    ranking: dict[str, dict[str, float]] = {}
    worsening: dict[str, str] = {}
    for element in LIMIT_ELEMENTS:
        low = done.get(f"{element} нижний")
        high = done.get(f"{element} верхний")
        if low is None or high is None:
            continue
        spread_p = 0.0
        spread_mo = 0.0
        mean_low = 0.0
        mean_high = 0.0
        for temperature in TOL_T_C:
            key = f"{temperature:.0f}"
            p_low = float(low["точки"][key]["доля P"])
            p_high = float(high["точки"][key]["доля P"])
            spread_p = max(spread_p, abs(p_high - p_low))
            mean_low += p_low / len(TOL_T_C)
            mean_high += p_high / len(TOL_T_C)
            mo_low = float(low["точки"][key]["матрица, масс. %"].get("MO", 0.0))
            mo_high = float(high["точки"][key]["матрица, масс. %"].get("MO", 0.0))
            spread_mo = max(spread_mo, abs(mo_high - mo_low))
        ranking[element] = {
            "размах доли P, мольн. %": spread_p * 100.0,
            "размах MO в матрице, масс. %": spread_mo,
            "средняя доля P на нижнем пределе, мольн. %": mean_low * 100.0,
            "средняя доля P на верхнем пределе, мольн. %": mean_high * 100.0,
        }
        worsening[element] = "верхний" if mean_high >= mean_low else "нижний"

    order = sorted(ranking, key=lambda name: ranking[name]["размах доли P, мольн. %"],
                   reverse=True)
    return order, worsening, ranking


def e5_tolerance(min_free_gib: float, stage_b_width: int,
                 force: bool = False) -> dict[str, Any]:
    """Обе ступени целиком. Считается в потомке."""

    cache = PointCache()
    if force:
        cache.records.clear()
        if cache.path.is_file():
            cache.path.unlink()

    free = w12.free_gib()
    if free < float(min_free_gib):
        return {
            "случаи": [],
            "пропущено": [{
                "случай": None,
                "T, °C": None,
                "причина": (
                    f"свободной физической памяти {free:.2f} ГиБ при требуемых "
                    f"{float(min_free_gib):.1f} ГиБ; база не разбиралась, прогон "
                    f"не начинался"
                ),
            }],
            "порядок элементов": [],
            "ухудшающий предел": {},
            "ранжирование": {},
            "фаз в расчёте": None,
            "фазы расчёта": [],
            "исключено из расчёта": [],
            "ремонт базы доступен": None,
        }

    ctx = w11.Context()
    done: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, Any]] = []

    log("--- ступень А: отсев по одному элементу ---")
    run_cases(ctx, cache, stage_a_cases(), done, skipped)

    order: list[str] = []
    worsening: dict[str, str] = {}
    ranking: dict[str, dict[str, float]] = {}
    if not skipped and "контроль" in done:
        order, worsening, ranking = rank_elements(done)
        width = max(1, min(int(stage_b_width), len(order)))
        log(f"--- ступень Б: углы по {width} элементам "
            f"({', '.join(order[:width])}), {2 ** width} углов плюс два "
            f"собранных состава ---")
        run_cases(ctx, cache, stage_b_cases(order, worsening, width), done, skipped)

    return {
        "случаи": list(done.values()),
        "пропущено": skipped,
        "порядок элементов": order,
        "ухудшающий предел": worsening,
        "ранжирование": ranking,
        "фаз в расчёте": len(ctx.phases),
        "фазы расчёта": list(ctx.phases),
        "исключено из расчёта": list(ctx.excluded_phases),
        "ремонт базы доступен": bool(ctx.repair_available),
    }


# --------------------------------------------------------------------------- #
# Таблицы
# --------------------------------------------------------------------------- #


def by_label(records: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {record["случай"]: record for record in records}


def stage_a_table(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Таблица ступени А, отсортированная по величине сдвига доли P-фазы."""

    index = by_label(records)
    control = index.get("контроль")
    rows: list[dict[str, Any]] = []
    for record in records:
        if record["ступень"] not in ("А", "контроль"):
            continue
        metrics = shift_metrics(record, control) if control else {}
        for temperature in TOL_T_C:
            key = f"{temperature:.0f}"
            point = record["точки"].get(key)
            if point is None:
                continue
            element = record["элемент"]
            rows.append({
                "элемент": element or "—",
                "предел": record["предел"] or "контроль",
                "значение, масс. %": (
                    float(record["состав, масс. %"].get(element, 0.0))
                    if element else None
                ),
                "T, °C": float(temperature),
                "доля P-фазы, мольн. %": float(point["доля P"]) * 100.0,
                "CR в FCC_A1, масс. %": float(
                    point["матрица, масс. %"].get("CR", 0.0)
                ),
                "MO в FCC_A1, масс. %": float(
                    point["матрица, масс. %"].get("MO", 0.0)
                ),
                "мольная доля FCC_A1, %": (
                    float(point["мольная доля матрицы"]) * 100.0
                    if point["мольная доля матрицы"] is not None else None
                ),
                "сдвиг доли P, п.п.": metrics.get(f"ΔP {key}", 0.0) * 100.0,
                "сдвиг CR в матрице, масс. %": metrics.get(f"ΔCR {key}", 0.0),
                "сдвиг MO в матрице, масс. %": metrics.get(f"ΔMO {key}", 0.0),
                "случай": record["случай"],
            })
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    table["_модуль"] = table["сдвиг доли P, п.п."].abs()
    table = table.sort_values(
        ["_модуль", "элемент", "T, °C"], ascending=[False, True, True]
    ).drop(columns="_модуль")
    return table.reset_index(drop=True)


def stage_b_table(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Таблица ступени Б: состав угла и результат на обеих температурах."""

    index = by_label(records)
    control = index.get("контроль")
    rows: list[dict[str, Any]] = []
    for record in records:
        if record["ступень"] not in ("Б", "контроль"):
            continue
        metrics = shift_metrics(record, control) if control else {}
        row: dict[str, Any] = {"случай": record["случай"]}
        for element in LIMIT_ELEMENTS:
            row[f"{element}, масс. %"] = float(
                record["состав, масс. %"].get(element, 0.0)
            )
        row["NI, масс. %"] = float(record["состав, масс. %"].get("NI", 0.0))
        for temperature in TOL_T_C:
            key = f"{temperature:.0f}"
            point = record["точки"].get(key)
            if point is None:
                continue
            row[f"доля P-фазы {key}, мольн. %"] = float(point["доля P"]) * 100.0
            row[f"CR в FCC_A1 {key}, масс. %"] = float(
                point["матрица, масс. %"].get("CR", 0.0)
            )
            row[f"MO в FCC_A1 {key}, масс. %"] = float(
                point["матрица, масс. %"].get("MO", 0.0)
            )
            row[f"сдвиг доли P {key}, п.п."] = metrics.get(f"ΔP {key}", 0.0) * 100.0
            row[f"сдвиг MO {key}, масс. %"] = metrics.get(f"ΔMO {key}", 0.0)
        rows.append(row)
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    key = f"доля P-фазы {TOL_T_C[0]:.0f}, мольн. %"
    return table.sort_values(key, ascending=False).reset_index(drop=True)


def phases_table(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Полный фазовый набор по каждому случаю и температуре."""

    rows: list[dict[str, Any]] = []
    for record in records:
        for temperature in TOL_T_C:
            key = f"{temperature:.0f}"
            point = record["точки"].get(key)
            if point is None:
                continue
            for name, value in sorted(point["фазы"].items()):
                rows.append({
                    "случай": record["случай"],
                    "ступень": record["ступень"],
                    "T, °C": float(temperature),
                    "фаза": name,
                    "фаза постановки": phase_label(name) or "",
                    "мольная доля": float(value),
                    "мольная доля, %": float(value) * 100.0,
                    "видимая": "да" if value >= VISIBLE_FLOOR else "нет",
                })
    return pd.DataFrame(rows)


def new_phases_table(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Фазы, которых нет у контрольного состава при той же температуре.

    Порог — тот же порог присутствия, что у волны 12-2, поэтому «появилась»
    значит ровно то же, что в 12-2: фаза присутствует в свёртке приложения.
    Колонка «видимая» отделяет следы от того, что видно на графике.
    """

    index = by_label(records)
    control = index.get("контроль")
    if control is None:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for record in records:
        if record["случай"] == "контроль":
            continue
        for temperature in TOL_T_C:
            key = f"{temperature:.0f}"
            point = record["точки"].get(key)
            base = control["точки"].get(key)
            if point is None or base is None:
                continue
            for name, value in sorted(point["фазы"].items()):
                if name in base["фазы"]:
                    continue
                rows.append({
                    "случай": record["случай"],
                    "ступень": record["ступень"],
                    "T, °C": float(temperature),
                    "фаза": name,
                    "фаза постановки": phase_label(name) or "",
                    "мольная доля": float(value),
                    "мольная доля, %": float(value) * 100.0,
                    "видимая": "да" if value >= VISIBLE_FLOOR else "нет",
                    "состав, масс. %": "; ".join(
                        f"{element} {record['состав, масс. %'].get(element, 0.0):g}"
                        for element in LIMIT_ELEMENTS
                    ),
                })
    return pd.DataFrame(rows)


def range_table(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Диапазон «от лучшего угла до худшего» — ответ на вопрос задачи."""

    index = by_label(records)
    control = index.get("контроль")
    rows: list[dict[str, Any]] = []
    for temperature in TOL_T_C:
        key = f"{temperature:.0f}"
        points = [
            (record["случай"], record["точки"][key])
            for record in records if record["точки"].get(key) is not None
        ]
        if not points:
            continue
        base = control["точки"].get(key) if control else None

        def report(metric: str, unit: str, getter: Any, worst_is_max: bool) -> None:
            values = [(label, getter(point)) for label, point in points]
            low_label, low_value = min(values, key=lambda item: item[1])
            high_label, high_value = max(values, key=lambda item: item[1])
            if worst_is_max:
                best_label, best_value = low_label, low_value
                worst_label, worst_value = high_label, high_value
            else:
                best_label, best_value = high_label, high_value
                worst_label, worst_value = low_label, low_value
            control_value = getter(base) if base is not None else None
            rows.append({
                "T, °C": float(temperature),
                "величина": metric,
                "единица": unit,
                "контроль": control_value,
                "лучший угол": best_value,
                "состав лучшего": best_label,
                "худший угол": worst_value,
                "состав худшего": worst_label,
                "размах, худший минус лучший": worst_value - best_value,
                "отношение худший/лучший": (
                    worst_value / best_value if best_value else None
                ),
                "худший минус контроль": (
                    worst_value - control_value if control_value is not None else None
                ),
            })

        report("доля P-фазы", "мольн. %",
               lambda point: float(point["доля P"]) * 100.0, True)
        report("MO в FCC_A1", "масс. %",
               lambda point: float(point["матрица, масс. %"].get("MO", 0.0)), False)
        report("CR в FCC_A1", "масс. %",
               lambda point: float(point["матрица, масс. %"].get("CR", 0.0)), False)
    return pd.DataFrame(rows)


def plot_e5(stage_a: pd.DataFrame, stage_b: pd.DataFrame, path: Path) -> None:
    """Слева — сдвиги ступени А, справа — углы ступени Б по доле P-фазы."""

    figure, axes = plt.subplots(1, 2, figsize=(13.0, 5.5))

    left = axes[0]
    block = stage_a[stage_a["предел"] != "контроль"]
    for temperature, colour in zip(TOL_T_C, ("#1f77b4", "#d62728")):
        part = block[block["T, °C"] == temperature].sort_values("сдвиг доли P, п.п.")
        left.barh(
            [f"{row['элемент']} {row['предел']}" for _, row in part.iterrows()],
            part["сдвиг доли P, п.п."], height=0.4,
            label=f"{temperature:.0f} °C", color=colour, alpha=0.75,
        )
    left.axvline(0.0, color="black", linewidth=0.8)
    left.set_xlabel("сдвиг доли P-фазы относительно контроля, п.п.")
    left.set_title("Ступень А: один элемент на пределе марки")
    left.legend()
    left.grid(axis="x", alpha=0.3)

    right = axes[1]
    for temperature, colour in zip(TOL_T_C, ("#1f77b4", "#d62728")):
        column = f"доля P-фазы {temperature:.0f}, мольн. %"
        if column not in stage_b:
            continue
        right.plot(range(len(stage_b)), stage_b[column], "o-",
                   color=colour, label=f"{temperature:.0f} °C")
    right.set_xticks(range(len(stage_b)))
    right.set_xticklabels(stage_b["случай"], rotation=90, fontsize=6)
    right.set_ylabel("доля P-фазы, мольн. %")
    right.set_title("Ступень Б: углы допуска")
    right.legend()
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
    """Итог замера памяти. Устроен как у 12-2, но с префиксом подпункта 12-5."""

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
    что в подпунктах 12-1 и 12-4.
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
# Подпункт 12-5 целиком
# --------------------------------------------------------------------------- #


def step_e5(force: bool = False, min_free_gib: float = MIN_FREE_GIB,
            stage_b_width: int = STAGE_B_DEFAULT) -> None:
    progress = w12.load_progress()
    if progress.get("12-5", {}).get("готов") and not force:
        log("12-5 пропущен, посчитан ранее (--force для пересчёта)")
        return

    free = w12.free_gib()
    cache_ready = (CACHE / f"{PREFIX}_points.jsonl").is_file() and not force
    if free < float(min_free_gib) and not cache_ready:
        w12.write_json({
            "подпункт": "12-5. Углы марочного допуска ЭК199-ВИ при 700 и 750 °C",
            "прогон": "не начинался",
            "причина": (
                f"свободной физической памяти {free:.2f} ГиБ при требуемых "
                f"{float(min_free_gib):.1f} ГиБ"
            ),
            "порог входа, ГиБ": float(min_free_gib),
            "порог по умолчанию (w12.MIN_FREE_GIB), ГиБ": MIN_FREE_GIB,
        }, f"{PREFIX}_summary.json")
        log(f"12-5 не запускался: свободно {free:.2f} ГиБ при требуемых "
            f"{float(min_free_gib):.1f} ГиБ")
        return

    arguments = ["--e5", "1",
                 "--min-free-gib", f"{float(min_free_gib):g}",
                 "--stage-b-elements", str(int(stage_b_width))]
    if force:
        arguments.append("--force")
    payload, measurement = run_child(arguments)
    measurement["свободной физической перед запуском, ГиБ"] = round(free, 2)

    records = payload["случаи"]
    stage_a = stage_a_table(records)
    write_csv(stage_a, f"{PREFIX}_stage_a.csv")
    stage_b = stage_b_table(records)
    write_csv(stage_b, f"{PREFIX}_stage_b.csv")
    phases = phases_table(records)
    write_csv(phases, f"{PREFIX}_phase_fractions.csv")
    new_phases = new_phases_table(records)
    write_csv(new_phases, f"{PREFIX}_new_phases.csv")
    ranges = range_table(records)
    write_csv(ranges, f"{PREFIX}_range.csv")
    if not stage_a.empty and not stage_b.empty:
        plot_e5(stage_a, stage_b, OUT / f"{PREFIX}_tolerance.png")

    index = by_label(records)
    control = index.get("контроль")
    summary = {
        "подпункт": ("12-5. Углы марочного допуска ЭК199-ВИ (ХН62М(Sc)-ВИ) "
                     "при 700 и 750 °C"),
        "база": DB_REL,
        "sha256 базы": w12.database_sha256(),
        "ремонт базы доступен": payload["ремонт базы доступен"],
        "фаз в расчёте": payload["фаз в расчёте"],
        "исключено из расчёта": payload["исключено из расчёта"],
        "температуры, °C": list(TOL_T_C),
        "контрольный состав, масс. %": (
            control["состав, масс. %"] if control else w11.full_wt()
        ),
        "марочные пределы, масс. %": {
            element: list(values) for element, values in GRADE_LIMITS.items()
        },
        "источник марочных пределов": GRADE_SOURCE,
        "элементы марки без пределов в репозитории": list(WITHOUT_LIMITS),
        "следовое значение вместо нижнего предела 0, масс. %": TRACE_WT,
        "ступень А, случаев": int(sum(
            1 for record in records if record["ступень"] == "А"
        )),
        "ступень Б, случаев": int(sum(
            1 for record in records if record["ступень"] == "Б"
        )),
        "точек посчитано": int(sum(len(record["точки"]) for record in records)),
        "порядок элементов по сдвигу доли P": payload["порядок элементов"],
        "ухудшающий предел по элементам": payload["ухудшающий предел"],
        "ранжирование ступени А": payload["ранжирование"],
        "ширина ступени Б, элементов": int(stage_b_width),
        "pdens": PDENS,
        "ряд повторов pdens": list(RETRY_PDENS),
        "порог входа по свободной памяти": {
            "по умолчанию (w12.MIN_FREE_GIB, он же w11.J2_MIN_FREE_GIB), ГиБ":
                MIN_FREE_GIB,
            "объявлен заданием 12-5, ГиБ": TASK_MIN_FREE_GIB,
            "фактический в этом прогоне, ГиБ": float(min_free_gib),
            "понижен относительно умолчания": float(min_free_gib) < MIN_FREE_GIB,
            "обоснование": (
                f"равновесный прогон 12-2 устроен так же и показал пик рабочего "
                f"набора {JUSTIFY_PEAK_SET_GIB:.3f} ГиБ при пике фиксации "
                f"{JUSTIFY_PEAK_COMMIT_GIB:.3f} ГиБ ({JUSTIFY_SOURCE})"
            ),
        },
        "порог остановки по ходу, свободной физической ГиБ": ABORT_FREE_GIB,
        "порог присутствия фазы, мольные доли": PRESENT_FLOOR,
        "порог видимости фазы, мольные доли": VISIBLE_FLOOR,
        "допуск на сумму мольных долей": SUM_TOLERANCE,
        "пропущено": payload["пропущено"],
        "диапазон от лучшего угла к худшему": (
            ranges.to_dict("records") if not ranges.empty else []
        ),
        "новых фаз относительно контроля": int(len(new_phases)),
        "новые фазы": (
            new_phases.to_dict("records") if not new_phases.empty else []
        ),
        "замер памяти": measurement,
        "чего расчёт не устанавливает": [
            "скандия в mc_ni 2.036 нет; счёт идёт по основе сплава ЭК199-ВИ",
            "фосфора в mc_ni 2.036 нет, а в марке он до 0,025 %",
            "равновесие не говорит о временах появления фаз — это задача 12-1",
            "марочные пределы взяты из репозитория (волна 9), а не из стандарта "
            "в руках; на C, Si, Mn, S и Al пределов в репозитории нет вовсе",
        ],
    }
    w12.write_json(summary, f"{PREFIX}_summary.json")

    complete = not payload["пропущено"] and bool(records)
    progress["12-5"] = {
        "готов": complete,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "случаев": len(records),
        "точек": summary["точек посчитано"],
        "пропущено": len(payload["пропущено"]),
        "pdens": PDENS,
        "порог входа, ГиБ": float(min_free_gib),
        "режим набора фаз": "все фазы",
    }
    w12.save_progress(progress)


STEPS = {"e5": step_e5}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Волна 12, подпункт 12-5: углы марочного допуска ЭК199-ВИ"
    )
    parser.add_argument("--only", default="all", help="e5; через запятую")
    parser.add_argument("--force", action="store_true", help="пересчитать готовое")
    parser.add_argument(
        "--min-free-gib", type=float, default=MIN_FREE_GIB,
        help=("порог входа по свободной физической памяти, ГиБ; умолчание — "
              "значение волны 11. Аварийный порог по ходу счёта ключа не имеет"),
    )
    parser.add_argument(
        "--stage-b-elements", type=int, default=STAGE_B_DEFAULT,
        help="сколько элементов ступени А идёт в полный перебор углов",
    )
    parser.add_argument("--e5", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--handoff", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    if args.e5 is not None:
        payload = e5_tolerance(
            min_free_gib=args.min_free_gib,
            stage_b_width=args.stage_b_elements,
            force=args.force,
        )
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
        STEPS[name](force=args.force, min_free_gib=args.min_free_gib,
                    stage_b_width=args.stage_b_elements)
        log(f"=== {name.upper()} готов за {time.perf_counter() - started:.1f} с ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
