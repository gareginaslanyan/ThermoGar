#!/usr/bin/env python3
"""Волна 12, подпункт 12-4 — бор и кремний припоя в основе сплава ЭК199-ВИ.

Задание `tasks/WAVE12_4_OPUS.md`, отчёт `tasks/WAVE12_4_REPORT.md`. Контекст —
ТЗ ИЖСР-1476, вариант крепления труб «сварка плюс пайка». Никелевые припои
содержат бор и кремний как депрессанты температуры плавления; спрашивается, что
эти два элемента образуют в основе и связывают ли они хром и молибден в бориды
и силициды дополнительно к P-фазе, найденной подпунктом 12-2.

Состав припоя по памяти не подставляется (правило «Источники» из
`tasks/RULES.md`): ГОСТ 19248 в проекте нет, он выписан в
`tasks/SOURCES_WANTED.md` позицией S-2. Считается параметрическая сетка по бору
и кремнию, которая от марки припоя не зависит.

Модуль не переписывает `tools/study_hn62m_wave12.py` и
`tools/study_hn62m_wave11.py`, а импортирует из них базу, состав основы,
разбор равновесия, формат таблиц, порог памяти и замер памяти. Своё здесь
только то, чего в волне 12-2 не было: одиннадцатый компонент B, сетка по двум
добавкам, разделение фаз на бориды и силициды и солидус обогащённой основы.

Запуск (интерпретатор — venv основного репозитория, PYTHONHASHSEED=0):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 ^
        tools\\study_hn62m_wave12_braze.py --only b1
    ... --only b2      # солидус обогащённой основы, отдельный прогон
    rem волна 13, поток G — та же сетка при точках ТЗ 580 и 595 °C
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 ^
        tools\\study_hn62m_wave12_braze.py --only b1 ^
        --temperatures 580,595 --prefix g1 --subpoint 13G-1 --min-free-gib 2.5

Память. Порог запуска тот же, что у волн 11 и 12-2 (`w12.MIN_FREE_GIB`,
4,0 ГиБ), порог остановки по ходу — тот же `w12.E1_ABORT_FREE_GIB`. Тяжёлый
счёт идёт в отдельном процессе, каждая посчитанная точка дописывается в кэш на
диск сразу, пиковая память потомка замеряется по ходу.

Границы достоверности живут в отчёте. Из кода видно только то, что здесь
названо: скандия в списке компонентов нет, потому что его нет в mc_ni; расчёт
равновесный и о глубине диффузии бора за время пайки не говорит ничего.
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
import pandas as pd

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import study_hn62m_wave11 as w11
import study_hn62m_wave12 as w12

ROOT = w12.ROOT
OUT = w12.OUT
CACHE = w12.CACHE

log = w12.log
CSV_WRITE = dict(w12.CSV_WRITE)
CSV_READ = dict(w12.CSV_READ)

# Порог «запускать или нет» и порог «остановиться по ходу» — значения волны
# 12-2, а не свои. Расходиться им нельзя: это один и тот же счёт на одной и
# той же машине.
MIN_FREE_GIB = w12.MIN_FREE_GIB
ABORT_FREE_GIB = w12.E1_ABORT_FREE_GIB

DB_REL = w12.DB_REL

# --- одиннадцатый компонент ------------------------------------------------ #

# Бор добавляется в список компонентов, а не подменяется чем-то другим. Список
# компонентов в волнах 11 и 12-2 — глобальная переменная модуля, и обе волны
# читают её на каждый вызов (`w11.solve_raw`, `w12.aggregate`). Поэтому
# включение бора сделано патчем этих переменных, а не вторым определением
# состава и пути к базе: второе определение — это ровно тот тихий разъезд, от
# которого волна 12-2 уходила, импортируя состав вместо копирования.
BORON = "B"


def enable_boron() -> None:
    """Добавить B в список компонентов волн 11 и 12-2. Идемпотентна."""

    if BORON in w11.COMPONENTS:
        return
    components = tuple(
        name for name in w11.COMPONENTS if name != "VA"
    ) + (BORON, "VA")
    elements = tuple(name for name in components if name != "VA")
    order = ("NI", "CR", "MO", BORON, "SI") + tuple(
        name for name in sorted(elements)
        if name not in ("NI", "CR", "MO", BORON, "SI")
    )
    for module in (w11, w12):
        module.COMPONENTS = components
        module.ELEMENTS = elements
    w12.ELEMENT_ORDER = order
    log(f"компонентов {len(components)}: {', '.join(components)}")


# --- сетка ----------------------------------------------------------------- #

# Кремний в основе есть и без припоя: 0,10 масс. % (`w11.CONTROL_WT['SI']`).
SI_BASE = float(w11.CONTROL_WT["SI"])

# Ось по бору при кремнии основы, масс. %. Значения задания.
B_AXIS: tuple[float, ...] = (0.0, 0.1, 0.3, 0.5, 1.0, 2.0, 3.0)
# Ось по кремнию при нулевом боре, масс. %. Задание называет 1,0; 2,0; 3,5;
# 5,0 — это полное содержание кремния в сплаве, а не добавка к 0,10: 0,10
# лежит внутри интервала и служит его началом.
SI_AXIS: tuple[float, ...] = (1.0, 2.0, 3.5, 5.0)
# Узлы, где обе добавки вместе. Значения задания.
CROSS_B: tuple[float, ...] = (0.0, 0.5, 1.5, 3.0)
CROSS_SI: tuple[float, ...] = (SI_BASE, 2.0, 5.0)

# Температуры. Две служебные из ТЗ ИЖСР-1476 (они же есть в сетке 12-2, и на
# них числа двух подпунктов сравниваются напрямую) и три высоких: пайка и
# последующая термообработка.
SERVICE_C: tuple[float, ...] = (700.0, 750.0)
BRAZE_C: tuple[float, ...] = (1050.0, 1150.0, 1200.0)
TEMPERATURES: tuple[float, ...] = SERVICE_C + BRAZE_C

# Подпункт, чьи результаты пишет прогон, и префикс его файлов. Умолчания —
# подпункта 12-4, чтобы его команда прогона осталась прежней. Волна 13 (поток
# G) считает ту же сетку при 580 и 595 °C и зовёт модуль ключами
# `--temperatures 580,595 --prefix g1 --subpoint 13G-1`. Префикс разделяет
# кэш точек, итог потомка, замеры памяти, таблицы, график и сводку — иначе
# прогон при новых температурах затёр бы результаты 12-4. Так же устроены
# ключи модуля кинетики в подпункте 12-9.
SUBPOINT = "12-4"
PREFIX = "e4"
# Порог входа, фактически применённый прогоном. Константа `MIN_FREE_GIB`
# остаётся общей, ключ `--min-free-gib` меняет только это значение, и в сводку
# уходят оба (правило «Память и параллельность» из `tasks/RULES.md`). Порог
# остановки по ходу ключом не меняется.
RUN_MIN_FREE_GIB = MIN_FREE_GIB


def configure(temperatures: Sequence[float] | None = None,
              prefix: str | None = None,
              subpoint: str | None = None,
              min_free_gib: float | None = None) -> None:
    """Назначить температуры, префикс, подпункт и порог входа на этот процесс.

    Зовётся из `main` до всякого счёта, в том числе в потомке: ключи ему
    передаются те же.
    """

    global TEMPERATURES, PREFIX, SUBPOINT, RUN_MIN_FREE_GIB
    if temperatures:
        TEMPERATURES = tuple(float(value) for value in temperatures)
    if prefix:
        PREFIX = str(prefix)
    if subpoint:
        SUBPOINT = str(subpoint)
    if min_free_gib is not None:
        RUN_MIN_FREE_GIB = float(min_free_gib)


def service_mode(temperature_c: float) -> bool:
    """Служебная ли температура: служебная 12-4 или точка ТЗ волны 12-2."""

    return (float(temperature_c) in SERVICE_C
            or float(temperature_c) in w12.E1_REQUIRED_C)

# Плотность стартовой выборки и ряд повторов — волны 12-2, чтобы числа узла
# «бора нет, кремний основы» совпали с числами 12-2, а не разъехались с ними
# из-за другой выборки.
PDENS = w12.E1_PDENS
# Ряд повторов волны 12-2 и три своих плотности сверху. Своё добавлено по
# числу, а не на всякий случай: на ряде 12-2 шесть точек из девяноста
# сходились в пустое решение (сумма мольных долей фаз ноль), и все шесть —
# на богатых узлах, где фаз восемь. Повторять тот же ряд ещё раз правило
# «Память и параллельность» запрещает, поэтому меняется сама выборка.
EXTRA_RETRY_PDENS: tuple[int, ...] = (400, 500, 150)
RETRY_PDENS: tuple[int, ...] = tuple(w12.E1_RETRY_PDENS) + EXTRA_RETRY_PDENS

PRESENT_FLOOR = w12.E1_PRESENT_FLOOR
VISIBLE_FLOOR = w12.E1_VISIBLE_FLOOR
SUM_TOLERANCE = w12.E1_SUM_TOLERANCE

MATRIX_PHASE = w12.E1_MATRIX_PHASE          # FCC_A1
MATRIX_ELEMENTS = tuple(w12.E1_MATRIX_ELEMENTS)   # CR, MO
P_PHASE = "P_PHASE"

# Порог «элемент в фазе есть», мольные доли. Нужен, чтобы отделить фазу, в
# которой бор или кремний действительно сидит, от фазы, куда решатель занёс
# численный ноль.
IN_PHASE_FLOOR = 1.0e-6


def nodes() -> list[dict[str, Any]]:
    """Узлы сетки: бор, кремний и то, какой осью задания узел назван.

    Узел, попавший в две оси сразу, считается один раз, а обе принадлежности
    сохраняются: таблицы по осям собираются потом выборкой из общего набора, и
    считать один и тот же состав дважды незачем.
    """

    collected: dict[tuple[float, float], dict[str, Any]] = {}

    def add(boron: float, silicon: float, axis: str) -> None:
        key = (round(float(boron), 6), round(float(silicon), 6))
        record = collected.setdefault(key, {
            "B, масс. %": key[0], "SI, масс. %": key[1], "оси": [],
        })
        if axis not in record["оси"]:
            record["оси"].append(axis)

    for boron in B_AXIS:
        add(boron, SI_BASE, "ось бора")
    for silicon in SI_AXIS:
        add(0.0, silicon, "ось кремния")
    for boron in CROSS_B:
        for silicon in CROSS_SI:
            add(boron, silicon, "перекрёстные узлы")

    return [collected[key] for key in sorted(collected)]


BASELINE_NODE = (0.0, SI_BASE)


# Ноль бора в узле задаётся не нулём, а следом. Причина не физическая, а в
# решателе: `pycalphad` требует условие по каждому компоненту системы, и состав
# без бора при включённом в систему боре даёт «Number of degrees of freedom is
# not zero» ещё до счёта. Обойти это, убрав бор из системы для нулевых узлов,
# значит разобрать базу второй раз и держать два набора моделей одновременно —
# при 4 ГиБ свободной памяти это дороже, чем след.
# Величина следа физически пустая: 10⁻⁶ масс. % — это 10 ppb, на три порядка
# ниже любого нормируемого содержания бора и на пять порядков ниже самого
# маленького узла сетки (0,1 масс. %). Что след действительно ничего не сдвинул,
# проверяется числом: матрица узла (0; 0,10) при 700 и 750 °C сверяется с
# `e1_matrix_fcc_a1.csv` волны 12-2, где бора в системе не было вовсе. Сверка
# лежит в сводке полем «сверка узла без припоя с 12-2».
ZERO_BORON_WT = 1.0e-6


def node_wt(boron: float, silicon: float) -> dict[str, float]:
    """Массовый состав узла: основа 12-2 с перезаписанным Si и добавленным B.

    Никель — остаток до 100 %, как в `w11.full_wt`. При нулевом боре вместо
    нуля ставится след `ZERO_BORON_WT` — почему, сказано выше.
    """

    overrides = {
        "SI": float(silicon),
        BORON: float(boron) if float(boron) > 0.0 else ZERO_BORON_WT,
    }
    return w11.full_wt(overrides)


def node_label(boron: float, silicon: float) -> str:
    return f"B={boron:g}; Si={silicon:g}"


# --- бориды и силициды: классификация по самой базе ------------------------ #

# Классификация берётся не из списка, написанного по памяти, а из подрешёточных
# записей `CONSTITUENT` самой mc_ni. Правило названо прямо:
#   * бор — основной (замещающий) составляющий подрешётки → фаза борид;
#   * бор — в подрешётке внедрения рядом с C или N → фаза не борид, а фаза с
#     бором в подрешётке внедрения (так устроены FCC_A1, BCC_A2, M23C6_WY);
#     одна вакансия рядом с бором борид не отменяет (так устроен MOB2);
#   * кремний — единственный составляющий подрешётки → фаза силицид (так
#     устроена G_PHASE, никелевый силицид типа Ni16Si7X6);
#   * кремний — один из многих в подрешётке → фаза с растворённым кремнием.
# Так список нельзя разойтись с базой, а в отчёт попадает и правило, и то, что
# по нему вышло.

# Признак подрешётки внедрения — углерод или азот рядом с бором. Вакансия в
# этот список не входит: в MOB2 вакансия стоит в борной подрешётке, и борид от
# этого борид.
INTERSTITIAL_MARKERS = frozenset({"C", "N"})
# Жидкость — раствор, а не борид и не силицид, хотя бор в ней рядом с
# углеродом: у неё одна подрешётка со всеми компонентами сразу.
SOLUTION_PHASES = frozenset({"LIQUID"})


def db_sublattices() -> dict[str, list[list[str]]]:
    """Составляющие каждой фазы по подрешёткам, прочитанные из .tdb.

    Ключевое слово читается и полностью, и сокращением: в mc_ni 96 записей
    написаны как `CONSTITUENT`, а три — как `CONST` (DELTA, GAMMA_DP,
    GAMMA_PRIME), и синтаксис TDB это разрешает. Читать только полное слово
    значило бы не найти модель γ′ и объявить фазу неклассифицированной —
    первый прогон подпункта так и сделал.
    """

    text = (ROOT / DB_REL).read_text("utf-8", errors="replace")
    sublattices: dict[str, list[list[str]]] = {}
    for record in re.findall(r"(?m)^\s*CONST(?:ITUENT)?\s.*?!", text, re.S):
        flat = " ".join(record.split())
        body = flat.split(None, 1)[1].rstrip("!").strip()
        name, _, rest = body.partition(":")
        groups = [
            [
                item.strip().rstrip("%").upper()
                for item in group.replace(" ", "").split(",")
                if item.strip().rstrip("%")
            ]
            for group in rest.split(":")
        ]
        sublattices[name.strip().upper()] = [group for group in groups if group]
    return sublattices


def classify(name: str, sublattices: Mapping[str, list[list[str]]]) -> str:
    """Чем фаза является по отношению к бору и кремнию. Правило — выше."""

    groups = sublattices.get(name.upper())
    if groups is None:
        return "нет записи CONSTITUENT в базе"
    if name.upper() in SOLUTION_PHASES:
        return "раствор"
    verdicts: list[str] = []
    for group in groups:
        if BORON in group:
            interstitial = bool(set(group) & INTERSTITIAL_MARKERS)
            verdicts.append(
                "бор в подрешётке внедрения" if interstitial else "борид"
            )
        if "SI" in group:
            verdicts.append("силицид" if len(group) == 1 else "кремний в растворе")
    for preferred in ("борид", "силицид", "бор в подрешётке внедрения",
                      "кремний в растворе"):
        if preferred in verdicts:
            return preferred
    return "ни бора, ни кремния в модели фазы"


# --------------------------------------------------------------------------- #
# Кэш точек
# --------------------------------------------------------------------------- #


class BrazePointCache(w12.PointCache):
    """Кэш точек подпункта 12-4. Отличие от 12-2 — только имя файла.

    Ключ кэша волны 12-2 — мольный состав и температура, а состав здесь как раз
    и меняется от узла к узлу, поэтому механизм годится без правок. Файл свой,
    чтобы два подпункта не писали в один.
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
            log(f"кэш точек {SUBPOINT}: {len(self.records)} записей")


# --------------------------------------------------------------------------- #
# B1. Равновесия на сетке
# --------------------------------------------------------------------------- #


def free_gib() -> float:
    return w12.free_gib()


def b1_grid(force: bool = False) -> dict[str, Any]:
    """Равновесия во всех узлах сетки и всех температурах. Считается в потомке."""

    enable_boron()
    cache = BrazePointCache()
    if force:
        cache.records.clear()
        if cache.path.is_file():
            cache.path.unlink()

    free = free_gib()
    if free < RUN_MIN_FREE_GIB:
        return {
            "точки": [],
            "пропущено": [{
                "узел": None, "T, °C": None,
                "причина": (
                    f"свободной физической памяти {free:.2f} ГиБ при требуемых "
                    f"{RUN_MIN_FREE_GIB:.1f} ГиБ; база не разбиралась, прогон не "
                    f"начинался"
                ),
            }],
            "фаз в расчёте": None, "фазы расчёта": [],
            "исключено из расчёта": [], "ремонт базы доступен": None,
        }

    ctx = w11.Context()
    points: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    stopped = False

    for node in nodes():
        if stopped:
            break
        boron = node["B, масс. %"]
        silicon = node["SI, масс. %"]
        wt = node_wt(boron, silicon)
        mole = w11.wt_to_mole(ctx, wt)
        for temperature in TEMPERATURES:
            cached = cache.get(mole, temperature)
            if cached is not None and w12.converged(cached):
                cached = dict(cached)
                cached.update(node)
                cached["состав, масс. %"] = wt
                points.append(cached)
                continue

            free = free_gib()
            if free < ABORT_FREE_GIB:
                skipped.append({
                    "узел": node_label(boron, silicon),
                    "T, °C": float(temperature),
                    "причина": (
                        f"свободной физической памяти {free:.2f} ГиБ, ниже "
                        f"порога остановки {ABORT_FREE_GIB:.1f} ГиБ; остаток "
                        f"сетки не считался"
                    ),
                })
                log(f"{node_label(boron, silicon)}, {temperature:.0f} °C и "
                    f"далее не считались: свободно {free:.2f} ГиБ")
                stopped = True
                break

            used_pdens = PDENS
            payload = w12.point_payload(ctx, mole, temperature, used_pdens)
            retries: list[int] = []
            for retry_pdens in RETRY_PDENS:
                if w12.converged(payload):
                    break
                log(f"{node_label(boron, silicon)}, {temperature:.0f} °C: сумма "
                    f"долей {payload['сумма мольных долей фаз']:.6f} при "
                    f"pdens={used_pdens}, повтор при pdens={retry_pdens}")
                retries.append(used_pdens)
                del payload
                gc.collect()
                used_pdens = retry_pdens
                payload = w12.point_payload(ctx, mole, temperature, used_pdens)

            payload["неудачные pdens"] = retries
            payload["сошлась"] = w12.converged(payload)
            if payload["сошлась"]:
                cache.put(mole, temperature, payload)
            else:
                skipped.append({
                    "узел": node_label(boron, silicon),
                    "T, °C": float(temperature),
                    "причина": (
                        f"не сошлась ни при одной из плотностей выборки "
                        f"{[PDENS, *RETRY_PDENS]}: сумма мольных долей фаз "
                        f"{payload['сумма мольных долей фаз']:.6f}, фаз "
                        f"{payload['фаз']}"
                    ),
                })
            payload.update(node)
            payload["состав, масс. %"] = wt
            points.append(payload)
            log(f"{node_label(boron, silicon)}, {temperature:.0f} °C: фаз "
                f"{payload['фаз']}, {' + '.join(sorted(payload['фазы']))}, "
                f"{payload['секунд']:.1f} с")
            gc.collect()

    return {
        "точки": points,
        "пропущено": skipped,
        "фаз в расчёте": len(ctx.phases),
        "фазы расчёта": list(ctx.phases),
        "исключено из расчёта": list(ctx.excluded_phases),
        "ремонт базы доступен": bool(ctx.repair_available),
    }


# --------------------------------------------------------------------------- #
# B2. Солидус обогащённой основы
# --------------------------------------------------------------------------- #

# Солидус считается не по всей сетке, а по объявленному подмножеству узлов.
# Причина названа числом: одна точка равновесия на одиннадцати компонентах
# стоит 10…27 с, половинное деление до 1 K на скобке 600…1450 °C — это 12
# равновесий на узел, то есть 2…5 минут на узел. Восемнадцать узлов сетки дали
# бы около часа сверх самой сетки при 4 ГиБ свободной памяти и тяжёлом счёте в
# соседнем терминале. Подмножество выбрано так, чтобы обе оси и дальний угол
# были покрыты: что депрессант делает с плавлением, видно и по нему.
SOLIDUS_NODES: tuple[tuple[float, float], ...] = (
    (0.0, SI_BASE),     # основа без припоя — опорная точка
    (0.5, SI_BASE),
    (1.0, SI_BASE),
    (3.0, SI_BASE),
    (0.0, 2.0),
    (0.0, 5.0),
    (1.5, 2.0),
    (3.0, 5.0),         # дальний угол сетки
)
# Скобка половинного деления. Нижний край ниже, чем у волны 11
# (`w11.A1_SOLIDUS_BRACKET` = 1000…1450 °C): бор и кремний как раз и опускают
# солидус, и скобка волны 11 на богатых узлах не прошла бы проверку края.
SOLIDUS_BRACKET = (600.0, 1450.0)
SOLIDUS_TOLERANCE_K = 1.0
# Порог «жидкость есть», мольные доли. Значение волны 11 (A1_PRESENT_FLOOR),
# чтобы солидус основы без припоя здесь и в волне 11 считался одинаково.
SOLIDUS_PRESENT_FLOOR = w11.A1_PRESENT_FLOOR


class SolidusCache:
    """Кэш «есть ли жидкость» по составу и температуре, дописываемый построчно.

    Хранится доля жидкости, а не только признак: по ней видно, насколько близко
    к порогу прошло деление, и повторный прогон не пересчитывает то же самое.
    """

    def __init__(self) -> None:
        CACHE.mkdir(parents=True, exist_ok=True)
        self.path = CACHE / f"{PREFIX}_solidus_points.jsonl"
        self.records: dict[str, float] = {}
        if self.path.is_file():
            for line in self.path.read_text("utf-8").splitlines():
                if line.strip():
                    record = json.loads(line)
                    self.records[record["key"]] = float(record["LIQUID"])
            log(f"кэш солидуса: {len(self.records)} равновесий")

    @staticmethod
    def key(mole: Mapping[str, float], temperature_c: float) -> str:
        return f"{w11.composition_id(mole)}|{temperature_c:.4f}"

    def liquid(self, ctx: Any, mole: Mapping[str, float],
               temperature_c: float, pdens: int) -> float:
        key = self.key(mole, temperature_c)
        if key in self.records:
            return self.records[key]
        fractions = w11.solve(ctx, mole, temperature_c, pdens)
        value = float(fractions.get("LIQUID", 0.0))
        self.records[key] = value
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(
                {"key": key, "T, °C": float(temperature_c), "LIQUID": value},
                ensure_ascii=False, sort_keys=True,
            ) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        gc.collect()
        return value


def b2_solidus(force: bool = False) -> dict[str, Any]:
    """Солидус по подмножеству узлов половинным делением. Считается в потомке."""

    enable_boron()
    cache = SolidusCache()
    if force:
        cache.records.clear()
        if cache.path.is_file():
            cache.path.unlink()

    free = free_gib()
    if free < RUN_MIN_FREE_GIB:
        return {
            "узлы": [],
            "пропущено": [{
                "узел": None,
                "причина": (
                    f"свободной физической памяти {free:.2f} ГиБ при требуемых "
                    f"{RUN_MIN_FREE_GIB:.1f} ГиБ; прогон не начинался"
                ),
            }],
        }

    ctx = w11.Context()
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for boron, silicon in SOLIDUS_NODES:
        free = free_gib()
        if free < ABORT_FREE_GIB:
            skipped.append({
                "узел": node_label(boron, silicon),
                "причина": (
                    f"свободной физической памяти {free:.2f} ГиБ, ниже порога "
                    f"остановки {ABORT_FREE_GIB:.1f} ГиБ"
                ),
            })
            break
        wt = node_wt(boron, silicon)
        mole = w11.wt_to_mole(ctx, wt)
        started = time.perf_counter()

        def has_liquid(temperature_c: float) -> bool:
            return cache.liquid(
                ctx, mole, temperature_c, PDENS
            ) > SOLIDUS_PRESENT_FLOOR

        low, high = SOLIDUS_BRACKET
        try:
            temperature, calls = w11._bisect(
                has_liquid, low, high, SOLIDUS_TOLERANCE_K,
                low_expected=False, high_expected=True,
                what=f"солидус {node_label(boron, silicon)}",
            )
        except RuntimeError as error:
            skipped.append({
                "узел": node_label(boron, silicon),
                "причина": f"скобка не прошла проверку края: {error}",
            })
            log(f"{node_label(boron, silicon)}: {error}")
            continue
        rows.append({
            "B, масс. %": float(boron),
            "SI, масс. %": float(silicon),
            "узел": node_label(boron, silicon),
            "солидус, °C": float(temperature),
            "равновесий": int(calls),
            "секунд": time.perf_counter() - started,
            "состав, масс. %": wt,
        })
        log(f"{node_label(boron, silicon)}: солидус {temperature:.1f} °C "
            f"({calls} равновесий, {time.perf_counter() - started:.0f} с)")
        gc.collect()

    return {
        "узлы": rows,
        "пропущено": skipped,
        "скобка, °C": list(SOLIDUS_BRACKET),
        "точность, K": SOLIDUS_TOLERANCE_K,
        "порог жидкости, мольные доли": SOLIDUS_PRESENT_FLOOR,
        "фаз в расчёте": len(ctx.phases),
        "исключено из расчёта": list(ctx.excluded_phases),
    }


# --------------------------------------------------------------------------- #
# Таблицы
# --------------------------------------------------------------------------- #


def node_columns(point: Mapping[str, Any]) -> dict[str, Any]:
    """Столбцы, называющие узел сетки.

    Имена нарочно не «B, масс. %» и «SI, масс. %»: в таблицах, где рядом
    стоит состав фазы, такие столбцы сталкиваются со столбцами состава по
    бору и кремнию и молча затираются последними. Первый прогон подпункта
    на этом и ошибся — в `e4_borides_silicides.csv` вместо состава узла
    оказался состав фазы, и отбор по узлу для графика вышел пустым.
    """

    return {
        "B узла, масс. %": point["B, масс. %"],
        "SI узла, масс. %": point["SI, масс. %"],
        "узел": node_label(point["B, масс. %"], point["SI, масс. %"]),
        "оси задания": ", ".join(point["оси"]),
        "T, °C": point["T, °C"],
        "режим": "служба" if service_mode(point["T, °C"]) else "пайка и ТО",
    }


def fraction_table(points: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Пункт 1 задания: полный фазовый набор в каждом узле, доли обе."""

    rows: list[dict[str, Any]] = []
    for point in points:
        for name, phase in sorted(
            point["фазы"].items(), key=lambda item: -item[1]["мольная доля"]
        ):
            row = node_columns(point)
            row.update({
                "фаза": name,
                "мольная доля, %": 100.0 * phase["мольная доля"],
                "массовая доля, %": 100.0 * phase["массовая доля"],
                "молярная масса фазы, г/моль": phase["молярная масса, г/моль"],
                "pdens точки": point["pdens"],
                "сошлась": "да" if point.get("сошлась", True) else "нет",
            })
            rows.append(row)
    return pd.DataFrame(rows)


def boride_table(points: Sequence[Mapping[str, Any]],
                 sublattices: Mapping[str, list[list[str]]]) -> pd.DataFrame:
    """Пункт 2 задания: бориды и силициды отдельным списком, с составом.

    В таблицу попадает фаза, которая по модели базы борид или силицид, и та, в
    которой бор или кремний действительно сидит выше порога `IN_PHASE_FLOOR` —
    иначе ответ «силицидов нет» остался бы без указания на то, куда в таком
    случае уходит кремний.
    """

    order = tuple(w12.ELEMENT_ORDER)
    rows: list[dict[str, Any]] = []
    for point in points:
        for name, phase in sorted(
            point["фазы"].items(), key=lambda item: -item[1]["мольная доля"]
        ):
            kind = classify(name, sublattices)
            mole_b = float(phase["состав, мольные доли"].get(BORON, 0.0))
            mole_si = float(phase["состав, мольные доли"].get("SI", 0.0))
            carries = mole_b > IN_PHASE_FLOOR or mole_si > IN_PHASE_FLOOR
            if kind not in ("борид", "силицид") and not carries:
                continue
            row = node_columns(point)
            row.update({
                "фаза": name,
                "чем является по модели базы": kind,
                "мольная доля, %": 100.0 * phase["мольная доля"],
                "массовая доля, %": 100.0 * phase["массовая доля"],
                "x(B) в фазе": mole_b,
                "x(SI) в фазе": mole_si,
            })
            for element in order:
                row[f"{element}, масс. %"] = phase["состав, масс. %"][element]
            rows.append(row)
    return pd.DataFrame(rows)


def baseline_matrix(points: Sequence[Mapping[str, Any]]) -> dict[float, dict[str, float]]:
    """Матрица в узле «бора нет, кремний основы» по температурам.

    Это и есть состояние без припоя, посчитанное здесь же и той же выборкой.
    Сравнение с ним корректно при любой температуре сетки, в том числе при
    1050…1200 °C, которых в волне 12-2 не было.
    """

    baseline: dict[float, dict[str, float]] = {}
    for point in points:
        key = (round(point["B, масс. %"], 6), round(point["SI, масс. %"], 6))
        if key != (round(BASELINE_NODE[0], 6), round(BASELINE_NODE[1], 6)):
            continue
        phase = point["фазы"].get(MATRIX_PHASE)
        if phase is None:
            continue
        baseline[float(point["T, °C"])] = {
            element: float(phase["состав, масс. %"][element])
            for element in MATRIX_ELEMENTS
        }
        baseline[float(point["T, °C"])]["мольная доля FCC_A1, %"] = (
            100.0 * phase["мольная доля"]
        )
    return baseline


def wave12_2_matrix() -> dict[float, dict[str, float]]:
    """Матрица без припоя из результата 12-2, `e1_matrix_fcc_a1.csv`.

    Берётся ровно для сверки: узел (0; 0,10) этой сетки — тот же состав, что
    считала 12-2, и при 700 и 750 °C числа обязаны совпасть. Если не совпадут,
    значит расходится что-то в счёте, и это видно в сводке, а не замазано.
    """

    path = OUT / "e1_matrix_fcc_a1.csv"
    if not path.is_file():
        return {}
    table = pd.read_csv(path, **CSV_READ)
    result: dict[float, dict[str, float]] = {}
    for _, line in table.iterrows():
        if str(line["FCC_A1 есть"]).strip() != "да":
            continue
        result[float(line["T, °C"])] = {
            element: float(line[f"{element} в FCC_A1, масс. %"])
            for element in MATRIX_ELEMENTS
        }
    return result


def matrix_table(points: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Пункт 3 задания: хром и молибден в FCC_A1 и добавка обеднения от припоя.

    Обеднение пишется двумя разными величинами, и путать их нельзя:
      * «сдвиг от состава сплава» — то же, что считала 12-2: матрица против
        номинала, то есть сколько элемента вообще ушло из твёрдого раствора;
      * «добавка от припоя» — матрица узла против матрицы узла без бора и
        кремния при той же температуре, то есть ровно то, что добавил припой.
    """

    baseline = baseline_matrix(points)
    rows: list[dict[str, Any]] = []
    for point in points:
        phase = point["фазы"].get(MATRIX_PHASE)
        reference = baseline.get(float(point["T, °C"]), {})
        row = node_columns(point)
        row["FCC_A1 есть"] = "да" if phase is not None else "нет"
        row["мольная доля FCC_A1, %"] = (
            100.0 * phase["мольная доля"] if phase is not None else None
        )
        row["массовая доля FCC_A1, %"] = (
            100.0 * phase["массовая доля"] if phase is not None else None
        )
        for element in MATRIX_ELEMENTS:
            nominal = float(point["состав, масс. %"].get(element, 0.0))
            actual = (
                float(phase["состав, масс. %"][element])
                if phase is not None else None
            )
            without = reference.get(element)
            row[f"{element} в сплаве, масс. %"] = nominal
            row[f"{element} в FCC_A1, масс. %"] = actual
            row[f"{element}, сдвиг от состава сплава, масс. %"] = (
                None if actual is None else actual - nominal
            )
            row[f"{element} в FCC_A1 без припоя, масс. %"] = without
            row[f"{element}, добавка от припоя, масс. %"] = (
                None if actual is None or without is None else actual - without
            )
            row[f"{element}, доля от состава без припоя, %"] = (
                None if actual is None or not without else 100.0 * actual / without
            )
        rows.append(row)
    return pd.DataFrame(rows)


def p_phase_table(points: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Пункт 4 задания: доля P-фазы против узла без припоя при той же T.

    В P_PHASE по модели базы (`CONSTITUENT P_PHASE : CO,CR,NI : CO,CR,W :
    MO,W :`) ни бора, ни кремния нет вовсе, поэтому действовать на неё они
    могут только через состав матрицы, а не входя в неё. Столбец «есть» пишется
    и когда фазы нет: «строки нет» — это не ответ на вопрос, растёт она или
    падает.
    """

    reference: dict[float, float] = {}
    for point in points:
        key = (round(point["B, масс. %"], 6), round(point["SI, масс. %"], 6))
        if key == (round(BASELINE_NODE[0], 6), round(BASELINE_NODE[1], 6)):
            phase = point["фазы"].get(P_PHASE)
            reference[float(point["T, °C"])] = (
                100.0 * phase["мольная доля"] if phase is not None else 0.0
            )

    order = tuple(w12.ELEMENT_ORDER)
    rows: list[dict[str, Any]] = []
    for point in points:
        phase = point["фазы"].get(P_PHASE)
        mole_pct = 100.0 * phase["мольная доля"] if phase is not None else 0.0
        without = reference.get(float(point["T, °C"]))
        row = node_columns(point)
        row.update({
            "P-фаза есть": "да" if phase is not None else "нет",
            "мольная доля, %": mole_pct,
            "массовая доля, %": (
                100.0 * phase["массовая доля"] if phase is not None else 0.0
            ),
            "без припоя, мольная доля, %": without,
            "изменение, мольн. %": (
                None if without is None else mole_pct - without
            ),
            "куда двинулась": (
                "—" if without is None
                else "выросла" if mole_pct - without > 1.0e-3
                else "упала" if without - mole_pct > 1.0e-3
                else "на месте"
            ),
        })
        for element in order:
            row[f"{element}, масс. %"] = (
                phase["состав, масс. %"][element] if phase is not None else None
            )
        rows.append(row)
    return pd.DataFrame(rows)


def composition_table(points: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Состав каждой фазы каждого узла: мольные доли и массовые проценты."""

    order = tuple(w12.ELEMENT_ORDER)
    rows: list[dict[str, Any]] = []
    for point in points:
        for name, phase in sorted(point["фазы"].items()):
            row = node_columns(point)
            row.update({
                "фаза": name,
                "мольная доля фазы, %": 100.0 * phase["мольная доля"],
                "массовая доля фазы, %": 100.0 * phase["массовая доля"],
            })
            for element in order:
                row[f"x({element})"] = phase["состав, мольные доли"][element]
            for element in order:
                row[f"{element}, масс. %"] = phase["состав, масс. %"][element]
            rows.append(row)
    return pd.DataFrame(rows)


def balance_table(points: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Сверка: состав, собранный обратно из фаз, против состава узла."""

    order = tuple(w12.ELEMENT_ORDER)
    rows: list[dict[str, Any]] = []
    for point in points:
        for element in order:
            recombined = sum(
                phase["массовая доля"] * phase["состав, масс. %"][element]
                for phase in point["фазы"].values()
            )
            nominal = float(point["состав, масс. %"].get(element, 0.0))
            row = node_columns(point)
            row.update({
                "элемент": element,
                "в сплаве, масс. %": nominal,
                "собрано из фаз, масс. %": recombined,
                "невязка, масс. %": recombined - nominal,
            })
            rows.append(row)
    return pd.DataFrame(rows)


def solidus_table(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Пункт 5 задания: солидус узла и насколько депрессант его опустил."""

    reference = None
    for row in rows:
        if (round(row["B, масс. %"], 6), round(row["SI, масс. %"], 6)) == (
            round(BASELINE_NODE[0], 6), round(BASELINE_NODE[1], 6)
        ):
            reference = float(row["солидус, °C"])
    table: list[dict[str, Any]] = []
    for row in rows:
        table.append({
            "B, масс. %": row["B, масс. %"],
            "SI, масс. %": row["SI, масс. %"],
            "узел": row["узел"],
            "солидус, °C": row["солидус, °C"],
            "солидус без припоя, °C": reference,
            "опустился на, K": (
                None if reference is None else row["солидус, °C"] - reference
            ),
            "равновесий половинного деления": row["равновесий"],
            "секунд": row["секунд"],
        })
    return pd.DataFrame(table)


# --------------------------------------------------------------------------- #
# График
# --------------------------------------------------------------------------- #


def plot_b1(borides: pd.DataFrame, matrix: pd.DataFrame, path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))

    axis_b = borides[
        (borides["SI узла, масс. %"] == SI_BASE)
        & (borides["чем является по модели базы"] == "борид")
    ]
    for temperature in TEMPERATURES:
        block = axis_b[axis_b["T, °C"] == temperature]
        if not len(block):
            continue
        total = block.groupby("B узла, масс. %")["мольная доля, %"].sum().sort_index()
        axes[0].plot(total.index, total.values, marker="o", markersize=4,
                     linewidth=1.5, label=f"{temperature:.0f} °C")
    axes[0].set_xlabel("бор в сплаве, масс. %")
    axes[0].set_ylabel("сумма мольных долей боридов, %")
    axes[0].set_title(f"Бориды по оси бора при Si = {SI_BASE:g} масс. %")
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=8)

    present = matrix[
        (matrix["FCC_A1 есть"] == "да") & (matrix["SI узла, масс. %"] == SI_BASE)
    ]
    for element, colour in (("CR", "tab:blue"), ("MO", "tab:red")):
        for temperature, style in zip(TEMPERATURES, ("-", "--", ":", "-.", (0, (3, 1, 1, 1)))):
            block = present[present["T, °C"] == temperature].sort_values("B узла, масс. %")
            if not len(block):
                continue
            axes[1].plot(block["B узла, масс. %"], block[f"{element} в FCC_A1, масс. %"],
                         linestyle=style, color=colour, linewidth=1.4,
                         marker="o", markersize=3,
                         label=f"{element}, {temperature:.0f} °C")
    axes[1].set_xlabel("бор в сплаве, масс. %")
    axes[1].set_ylabel("в FCC_A1, масс. %")
    axes[1].set_title("Матрица FCC_A1: хром и молибден по оси бора")
    axes[1].grid(alpha=0.3)
    axes[1].legend(fontsize=6, ncol=2)

    figure.suptitle(
        f"{SUBPOINT}. Бор и кремний припоя в основе ЭК199-ВИ (без скандия), "
        f"mc_ni 2.036, pdens {PDENS}"
    )
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


# --------------------------------------------------------------------------- #
# Служебное: потомок и замер памяти
# --------------------------------------------------------------------------- #


def memory_report(stem: str, record: Mapping[str, Any], seconds: float,
                  final: bool = True) -> Path | None:
    """Итог замера памяти. Устроен как у 12-2, но с префиксом подпункта 12-4."""

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
    """Фоновый опрос памяти потомка. Замер — `w11.memory_probe`, без своего."""

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
            memory_report(stem, record, now - float(
                record.get("начало, perf_counter", now)
            ), final=False)
            flushed = now


def run_child(arguments: Sequence[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Тяжёлый кусок — в отдельном процессе, результат приходит файлом.

    Своя копия механизма волны 12-2 нужна по одной причине: `w12.run_child`
    запускает `Path(__file__)` своего модуля, то есть саму волну 12-2. Всё, что
    можно было взять оттуда без правок, взято — опрос памяти зовёт
    `w11.memory_probe`, шаги опроса и сброса тоже волны 11.
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
        key: value for key, value in record.items()
        if key != "начало, perf_counter"
    }
    measurement["секунд прогона"] = round(seconds, 1)
    if record.get("замеров"):
        measurement["прирост занятой подкачки в системе, ГиБ"] = round(
            float(record["максимум занятой подкачки в системе, ГиБ"])
            - float(record["занято подкачки до старта, ГиБ"]), 3
        )
    return json.loads(handoff.read_text("utf-8")), measurement


# --------------------------------------------------------------------------- #
# Подпункт 12-4 целиком
# --------------------------------------------------------------------------- #


def boride_verdict(borides: pd.DataFrame) -> list[dict[str, Any]]:
    """По каждой борид- и силицид-фазе: где встретилась и сколько её больше всего."""

    verdict: list[dict[str, Any]] = []
    if not len(borides):
        return verdict
    for name in sorted(borides["фаза"].unique()):
        block = borides[borides["фаза"] == name]
        peak = block.loc[block["мольная доля, %"].idxmax()]
        verdict.append({
            "фаза": name,
            "чем является по модели базы": str(peak["чем является по модели базы"]),
            "узлов с фазой": int(len(block)),
            "температуры, °C": sorted({float(value) for value in block["T, °C"]}),
            "наименьший бор с этой фазой, масс. %": float(block["B узла, масс. %"].min()),
            "наибольшая мольная доля, %": float(peak["мольная доля, %"]),
            "в узле": str(peak["узел"]),
            "при T, °C": float(peak["T, °C"]),
            "CR в фазе на пике, масс. %": float(peak["CR, масс. %"]),
            "MO в фазе на пике, масс. %": float(peak["MO, масс. %"]),
        })
    return verdict


def matrix_verdict(matrix: pd.DataFrame) -> list[dict[str, Any]]:
    """Где матрица обеднена сильнее всего и на сколько это больше, чем без припоя."""

    verdict: list[dict[str, Any]] = []
    present = matrix[matrix["FCC_A1 есть"] == "да"]
    for temperature in TEMPERATURES:
        block = present[present["T, °C"] == temperature]
        if not len(block):
            continue
        record: dict[str, Any] = {"T, °C": float(temperature)}
        for element in MATRIX_ELEMENTS:
            column = f"{element} в FCC_A1, масс. %"
            worst = block.loc[block[column].idxmin()]
            record[f"{element} без припоя, масс. %"] = (
                float(worst[f"{element} в FCC_A1 без припоя, масс. %"])
                if pd.notna(worst[f"{element} в FCC_A1 без припоя, масс. %"]) else None
            )
            record[f"{element} наименьший в матрице, масс. %"] = float(worst[column])
            record[f"{element} в узле"] = str(worst["узел"])
            record[f"{element} добавка от припоя, масс. %"] = (
                float(worst[f"{element}, добавка от припоя, масс. %"])
                if pd.notna(worst[f"{element}, добавка от припоя, масс. %"]) else None
            )
        verdict.append(record)
    return verdict


def p_phase_verdict(p_table: pd.DataFrame) -> list[dict[str, Any]]:
    """Растёт P-фаза от бора и кремния или падает — по каждой температуре."""

    verdict: list[dict[str, Any]] = []
    for temperature in TEMPERATURES:
        block = p_table[p_table["T, °C"] == temperature]
        if not len(block):
            continue
        without = block["без припоя, мольная доля, %"].dropna()
        moved = block["куда двинулась"].value_counts().to_dict()
        verdict.append({
            "T, °C": float(temperature),
            "без припоя, мольная доля, %": float(without.iloc[0]) if len(without) else None,
            "узлов с P-фазой": int((block["P-фаза есть"] == "да").sum()),
            "узлов всего": int(len(block)),
            "наибольшая мольная доля, %": float(block["мольная доля, %"].max()),
            "в узле": str(block.loc[block["мольная доля, %"].idxmax(), "узел"]),
            "наименьшая мольная доля, %": float(block["мольная доля, %"].min()),
            "куда двинулась, узлов": {str(key): int(value) for key, value in moved.items()},
        })
    return verdict


def step_b1(force: bool = False) -> None:
    progress = w12.load_progress()
    if progress.get(f"{SUBPOINT} сетка", {}).get("готов") and not force:
        log(f"{SUBPOINT} сетка пропущена, посчитана ранее (--force для пересчёта)")
        return

    free = free_gib()
    cache_ready = (CACHE / f"{PREFIX}_points.jsonl").is_file() and not force
    if free < RUN_MIN_FREE_GIB and not cache_ready:
        w12.write_json({
            "подпункт": f"{SUBPOINT}. Бор и кремний припоя в основе ЭК199-ВИ",
            "прогон": "не начинался",
            "причина": (
                f"свободной физической памяти {free:.2f} ГиБ при требуемых "
                f"{RUN_MIN_FREE_GIB:.1f} ГиБ"
            ),
            "порог по умолчанию, ГиБ": MIN_FREE_GIB,
        }, f"{PREFIX}_summary.json")
        log(f"{SUBPOINT} не запускался: свободно {free:.2f} ГиБ при требуемых "
            f"{RUN_MIN_FREE_GIB:.1f} ГиБ")
        return

    payload, measurement = run_child(
        ["--b1", "1"] + child_keys() + (["--force"] if force else [])
    )
    measurement["свободной физической перед запуском, ГиБ"] = round(free, 2)
    points = payload["точки"]
    if not points:
        w12.write_json({
            "подпункт": f"{SUBPOINT}. Бор и кремний припоя в основе ЭК199-ВИ",
            "прогон": "пуст",
            "пропущено": payload["пропущено"],
            "замер памяти": measurement,
        }, f"{PREFIX}_summary.json")
        return

    enable_boron()
    sublattices = db_sublattices()

    fractions = fraction_table(points)
    w12.write_csv(fractions, f"{PREFIX}_phase_fractions.csv")
    borides = boride_table(points, sublattices)
    w12.write_csv(borides, f"{PREFIX}_borides_silicides.csv")
    matrix = matrix_table(points)
    w12.write_csv(matrix, f"{PREFIX}_matrix_fcc_a1.csv")
    p_table = p_phase_table(points)
    w12.write_csv(p_table, f"{PREFIX}_p_phase.csv")
    compositions = composition_table(points)
    w12.write_csv(compositions, f"{PREFIX}_phase_compositions.csv")
    balance = balance_table(points)
    w12.write_csv(balance, f"{PREFIX}_mass_balance.csv")
    # Невязку баланса имеет смысл смотреть только там, где решение есть: у
    # пустой точки собранный из фаз состав равен нулю, и «невязка» равна
    # минус всему составу. Такие точки названы отдельным числом.
    converged_points = [
        point for point in points if point.get("сошлась", True)
    ]
    balance_converged = balance_table(converged_points)
    plot_b1(borides, matrix, OUT / f"{PREFIX}_braze.png")

    # Сверка узла без припоя с результатом 12-2. Узел (0; 0,10) — тот же
    # состав, и при 700 и 750 °C числа обязаны совпасть до знаков округления
    # записи в CSV.
    reference = wave12_2_matrix()
    own = baseline_matrix(points)
    checks: list[dict[str, Any]] = []
    for temperature in sorted(set(own) & set(reference)):
        for element in MATRIX_ELEMENTS:
            checks.append({
                "T, °C": float(temperature),
                "элемент": element,
                f"{SUBPOINT}, узел без припоя, масс. %": own[temperature][element],
                "12-2, e1_matrix_fcc_a1.csv, масс. %": reference[temperature][element],
                "разность, масс. %": (
                    own[temperature][element] - reference[temperature][element]
                ),
            })

    silicide_names = sorted({
        name for name in fractions["фаза"].unique()
        if classify(name, sublattices) == "силицид"
    })
    boride_names = sorted({
        name for name in fractions["фаза"].unique()
        if classify(name, sublattices) == "борид"
    })

    summary = {
        "подпункт": (
            f"{SUBPOINT}. Что делает с основой сплава ЭК199-ВИ бор и кремний "
            f"из припоя"
        ),
        "модуль": "tools/study_hn62m_wave12_braze.py (подпункт 12-4)",
        "база": DB_REL,
        "sha256 базы": w12.database_sha256(),
        "бор в базе": True,
        "кремний в базе": True,
        "ремонт базы доступен": payload["ремонт базы доступен"],
        "компоненты": list(w11.COMPONENTS),
        "фаз в расчёте": payload["фаз в расчёте"],
        "исключено из расчёта": payload["исключено из расчёта"],
        "фазы расчёта": payload["фазы расчёта"],
        "основа, масс. %": w11.CONTROL_WT,
        "сетка": {
            "ось бора, масс. %": list(B_AXIS),
            "кремний на оси бора, масс. %": SI_BASE,
            "ось кремния, масс. %": list(SI_AXIS),
            "перекрёстные узлы, бор": list(CROSS_B),
            "перекрёстные узлы, кремний": list(CROSS_SI),
            "узлов": len(nodes()),
            "температуры, °C": list(TEMPERATURES),
            "точек": len(nodes()) * len(TEMPERATURES),
        },
        "точек посчитано": len(points),
        "pdens": PDENS,
        "ряд повторов pdens": list(RETRY_PDENS),
        "из них своих, добавленных в 12-4": list(EXTRA_RETRY_PDENS),
        "порог запуска, свободной физической ГиБ": RUN_MIN_FREE_GIB,
        "порог запуска по умолчанию, ГиБ": MIN_FREE_GIB,
        "порог остановки по ходу, свободной физической ГиБ": ABORT_FREE_GIB,
        "порог присутствия фазы, мольные доли": PRESENT_FLOOR,
        "порог присутствия элемента в фазе, мольные доли": IN_PHASE_FLOOR,
        "ноль бора задан следом, масс. %": ZERO_BORON_WT,
        "почему след, а не ноль": (
            "pycalphad требует условие по каждому компоненту системы; состав "
            "без бора при включённом в систему боре падает с «Number of degrees "
            "of freedom is not zero». 10⁻⁶ масс. % — это 10 ppb, на пять "
            "порядков ниже наименьшего узла сетки; что след ничего не сдвинул, "
            "показывает сверка с 12-2"
        ),
        "правило классификации": (
            "бор основной составляющий подрешётки — борид; бор только в "
            "подрешётке внедрения рядом с C, N, O или VA — не борид; кремний "
            "единственный составляющий подрешётки — силицид; кремний один из "
            "многих — растворён. Читается из записей CONSTITUENT самой mc_ni"
        ),
        "бориды, встреченные в расчёте": boride_names,
        "силициды, встреченные в расчёте": silicide_names,
        "бориды и силициды": boride_verdict(borides),
        "матрица FCC_A1": matrix_verdict(matrix),
        "P-фаза": p_phase_verdict(p_table),
        "сверка узла без припоя с 12-2": checks,
        "наибольшее расхождение с 12-2, масс. %": (
            max(abs(record["разность, масс. %"]) for record in checks)
            if checks else None
        ),
        "наибольшая невязка баланса на сошедшихся точках, масс. %": float(
            balance_converged["невязка, масс. %"].abs().max()
        ) if len(balance_converged) else None,
        "точек без решения": int(len(points) - len(converged_points)),
        "температуры, не сошедшиеся с первого раза": [
            {"узел": node_label(point["B, масс. %"], point["SI, масс. %"]),
             "T, °C": point["T, °C"],
             "неудачные pdens": point["неудачные pdens"],
             "сошлась при pdens": point["pdens"]}
            for point in points if point.get("неудачные pdens")
        ],
        "пропущено": payload["пропущено"],
        "замер памяти": measurement,
        "чего расчёт не устанавливает": [
            "скандия в mc_ni 2.036 нет; счёт идёт по основе ЭК199-ВИ без него",
            "состав припоя по ГОСТ 19248 не подставлялся: стандарта в проекте "
            "нет, он выписан в tasks/SOURCES_WANTED.md позицией S-2",
            "смачивание, растекание, прочность паяного шва и поведение шва во "
            "фторидном расплаве равновесием не описываются вовсе",
            "равновесие ничего не говорит о глубине диффузии бора за время "
            "пайки: посчитано, что образуется при данном содержании бора, а не "
            "как далеко бор успеет уйти от шва",
        ],
    }
    w12.write_json(summary, f"{PREFIX}_summary.json")

    complete = (
        not payload["пропущено"]
        and len(points) == len(nodes()) * len(TEMPERATURES)
        and all(point.get("сошлась", True) for point in points)
    )
    progress[f"{SUBPOINT} сетка"] = {
        "готов": complete,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "точек посчитано": len(points),
        "точек в сетке": len(nodes()) * len(TEMPERATURES),
        "пропущено": len(payload["пропущено"]),
        "pdens": PDENS,
    }
    w12.save_progress(progress)


def step_b2(force: bool = False) -> None:
    progress = w12.load_progress()
    if progress.get(f"{SUBPOINT} солидус", {}).get("готов") and not force:
        log(f"{SUBPOINT} солидус пропущен, посчитан ранее (--force для пересчёта)")
        return

    free = free_gib()
    cache_ready = (CACHE / f"{PREFIX}_solidus_points.jsonl").is_file() and not force
    if free < RUN_MIN_FREE_GIB and not cache_ready:
        w12.write_json({
            "подпункт": "12-4, пункт 5. Солидус обогащённой бором и кремнием основы",
            "прогон": "не начинался",
            "причина": (
                f"свободной физической памяти {free:.2f} ГиБ при требуемых "
                f"{RUN_MIN_FREE_GIB:.1f} ГиБ"
            ),
        }, f"{PREFIX}_solidus_summary.json")
        log(f"{SUBPOINT} солидус не запускался: свободно {free:.2f} ГиБ")
        return

    payload, measurement = run_child(
        ["--b2", "1"] + child_keys() + (["--force"] if force else [])
    )
    measurement["свободной физической перед запуском, ГиБ"] = round(free, 2)
    rows = payload["узлы"]
    table = solidus_table(rows)
    if len(table):
        w12.write_csv(table, f"{PREFIX}_solidus.csv")

    summary = {
        "подпункт": "12-4, пункт 5. Солидус обогащённой бором и кремнием основы",
        "база": DB_REL,
        "sha256 базы": w12.database_sha256(),
        "узлы, где считался солидус": [
            {"B, масс. %": item[0], "SI, масс. %": item[1]}
            for item in SOLIDUS_NODES
        ],
        "почему не вся сетка": (
            "одно равновесие на одиннадцати компонентах стоит 10…27 с, "
            "половинное деление до 1 K на скобке 600…1450 °C — 12 равновесий на "
            "узел; восемнадцать узлов сетки дали бы около часа сверх самой "
            "сетки при 4 ГиБ свободной памяти и тяжёлом счёте в соседнем "
            "терминале. Подмножество покрывает обе оси и дальний угол"
        ),
        "скобка, °C": payload.get("скобка, °C"),
        "точность, K": payload.get("точность, K"),
        "порог жидкости, мольные доли": payload.get("порог жидкости, мольные доли"),
        "солидус": rows and [
            {key: value for key, value in row.items() if key != "состав, масс. %"}
            for row in rows
        ] or [],
        "пропущено": payload["пропущено"],
        "замер памяти": measurement,
        "чего расчёт не устанавливает": [
            "это равновесный солидус самой основы, обогащённой бором и "
            "кремнием, а не температура плавления припоя и не солидус шва",
            "равновесие не говорит, на какую глубину основа успеет обогатиться "
            "бором за время пайки, поэтому к какой точке у шва относится каждый "
            "узел, из расчёта не следует",
        ],
    }
    w12.write_json(summary, f"{PREFIX}_solidus_summary.json")

    progress[f"{SUBPOINT} солидус"] = {
        "готов": bool(rows) and not payload["пропущено"]
        and len(rows) == len(SOLIDUS_NODES),
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "узлов посчитано": len(rows),
        "узлов в подмножестве": len(SOLIDUS_NODES),
    }
    w12.save_progress(progress)


def child_keys() -> list[str]:
    """Ключи, которые потомок получает те же, что родитель.

    При умолчаниях подпункта 12-4 список пуст, и имя итога потомка остаётся
    прежним: `child_e4_b1_1.json`.
    """

    keys: list[str] = []
    if SUBPOINT != "12-4" or PREFIX != "e4" or TEMPERATURES != SERVICE_C + BRAZE_C:
        keys += ["--temperatures", ",".join(f"{value:g}" for value in TEMPERATURES),
                 "--prefix", PREFIX, "--subpoint", SUBPOINT]
    if RUN_MIN_FREE_GIB != MIN_FREE_GIB:
        keys += ["--min-free-gib", f"{RUN_MIN_FREE_GIB:g}"]
    return keys


STEPS = {"b1": step_b1, "b2": step_b2}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Волна 12, подпункт 12-4: бор и кремний припоя в основе ЭК199-ВИ"
    )
    parser.add_argument("--only", default="all", help="b1, b2; через запятую")
    parser.add_argument("--force", action="store_true", help="пересчитать готовое")
    parser.add_argument("--temperatures", default=None,
                        help="температуры, °C, через запятую; умолчание — "
                             "температуры подпункта 12-4")
    parser.add_argument("--prefix", default=None,
                        help="префикс файлов результатов и кэша; умолчание e4")
    parser.add_argument("--subpoint", default=None,
                        help="номер подпункта для сводки, журнала прогресса и "
                             "подписи графика; умолчание 12-4")
    parser.add_argument("--min-free-gib", type=float, default=None,
                        help="порог входа по свободной физической памяти, ГиБ; "
                             f"умолчание {MIN_FREE_GIB:g}. Порог остановки по "
                             "ходу этим ключом не меняется")
    parser.add_argument("--b1", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--b2", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--handoff", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    configure(
        temperatures=(
            [float(value) for value in args.temperatures.split(",")
             if value.strip()] if args.temperatures else None
        ),
        prefix=args.prefix,
        subpoint=args.subpoint,
        min_free_gib=args.min_free_gib,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    if args.b1 is not None or args.b2 is not None:
        payload = (
            b1_grid(force=args.force) if args.b1 is not None
            else b2_solidus(force=args.force)
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
        STEPS[name](force=args.force)
        log(f"=== {name.upper()} готов за {time.perf_counter() - started:.1f} с ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
