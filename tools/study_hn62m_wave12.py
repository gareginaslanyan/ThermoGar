#!/usr/bin/env python3
"""Волна 12, подпункт 12-2 — равновесия ЭК199-ВИ (ХН62М(Sc)-ВИ) в точках ТЗ.

Задача `tasks/WAVE12_2_REPORT.md`. Считается полный равновесный фазовый набор
в температурных точках ТЗ ИЖСР-1476 (580, 595, 664, 700, 750 °C) и на сетке
500…900 °C с шагом 25 K, чтобы точки ТЗ лежали на кривой, а не висели
изолированно.

Модуль не переписывает `tools/study_hn62m_wave11.py`, а импортирует из него
базу, состав, путь ремонта базы и замер памяти. Причина ровно обратная той, по
которой волна 11 отделялась от волны 10: там числа сравнивались построчно со
старыми, и общий код сделал бы сравнение недоказуемым, а здесь числа новые, и
единственная опасность — тихий разъезд контрольного состава, порога памяти или
списка фаз между двумя волнами. Одно определение исключает такой разъезд.

Запуск (интерпретатор — venv основного репозитория, PYTHONHASHSEED=0):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 ^
        tools\\study_hn62m_wave12.py --only e1

Память. Порог свободной физической памяти взят тот же, что у волны 11
(`J2_MIN_FREE_GIB = 4.0`), и проверяется дважды: в родителе перед запуском
потомка и в самом потомке перед разбором базы. Тяжёлый счёт идёт в отдельном
процессе, результат каждой температуры дописывается в кэш на диск сразу, а
пиковая память потомка со всем его потомством замеряется по ходу.

Границы достоверности числами не задаются и живут в отчёте. Здесь называется
только то, что видно из кода: скандия в списке компонентов нет, потому что его
нет в mc_ni; расчёт равновесный и о временах появления фаз не говорит ничего.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
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

ROOT = w11.ROOT
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

OUT = ROOT / "results" / "hn62m_wave12"
CACHE = OUT / "cache"
PROGRESS_PATH = OUT / "_progress.json"

# Формат таблиц волн 9…11: точка с запятой и десятичная запятая.
CSV_WRITE = dict(w11.CSV_WRITE)
CSV_READ = dict(w11.CSV_READ)

log = w11.log

# Состав, база и порог памяти — из волны 11 без копирования значений.
CONTROL_WT: dict[str, float] = dict(w11.CONTROL_WT)
COMPONENTS: tuple[str, ...] = tuple(w11.COMPONENTS)
ELEMENTS: tuple[str, ...] = tuple(w11.ELEMENTS)
DB_REL = w11.DB_REL
# Порог «запускать или нет», проверяемый до старта тяжёлого счёта. Значение
# волны 11 (J2_MIN_FREE_GIB), а не своё.
MIN_FREE_GIB = w11.J2_MIN_FREE_GIB
# Порог «остановиться, пока не сняли по памяти», проверяемый по ходу счёта.
# Это другая величина, и путать её с MIN_FREE_GIB нельзя: к моменту второй
# температуры разобранная база и скомпилированные модели сами занимают больше
# гигабайта, свободной физической памяти становится меньше MIN_FREE_GIB, и
# сравнение с ним остановило бы прогон, который сам же и создал эту разницу
# (первый прогон волны 12 так и встал после первой температуры). Здесь нужен
# признак настоящей нехватки — до свопа остаётся мало.
E1_ABORT_FREE_GIB = 1.0

# Порядок элементов в таблицах: основа, затем два элемента, ради которых
# задача и ставилась, затем остальные по алфавиту.
ELEMENT_ORDER: tuple[str, ...] = ("NI", "CR", "MO") + tuple(
    name for name in sorted(ELEMENTS) if name not in ("NI", "CR", "MO")
)

# --- 12-2 ------------------------------------------------------------------ #

# Температурные точки ТЗ ИЖСР-1476.
E1_REQUIRED_C: tuple[float, ...] = (580.0, 595.0, 664.0, 700.0, 750.0)
# Сетка, на которую точки ТЗ должны лечь: 500…900 °C с шагом 25 K.
E1_GRID_C: tuple[float, ...] = tuple(500.0 + 25.0 * index for index in range(17))

# Плотность стартовой выборки. Значение волны 11 (A2_PDENS), на котором там
# считался полный фазовый набор на сетке 50…1300 °C; менять его здесь незачем,
# иначе числа двух волн окажутся несравнимы.
E1_PDENS = w11.A2_PDENS
# Ряд повторов для точки, сошедшейся в пустое решение. Порядок — волны 11
# (A2_RETRY_PDENS), она ловила ту же дыру и лечила её так же.
E1_RETRY_PDENS: tuple[int, ...] = tuple(w11.A2_RETRY_PDENS)

# Порог «фаза присутствует». Совпадает с порогом свёртки долей приложения
# (`thermogar_parallel.PHASE_FRACTION_FLOOR`), поэтому набор фаз здесь тот же,
# что показала бы программа на том же составе и той же температуре.
E1_PRESENT_FLOOR = 1.0e-10
# Порог, с которого фаза попадает на график и в короткую таблицу точек ТЗ.
# Всё, что ниже, остаётся в полной таблице: выкидывать его нельзя, рисовать —
# нечитаемо.
E1_VISIBLE_FLOOR = 1.0e-4
# Допустимая невязка суммы мольных долей фаз. Больше — точка считается
# несошедшейся и пересчитывается с другой плотностью выборки.
E1_SUM_TOLERANCE = 1.0e-3

# ТКП-фазы ровно в той номенклатуре, в какой их называет постановка, и имена,
# под которыми они лежат в mc_ni. LAV_C14 добавлена к Laves: в базе это
# отдельная фаза того же семейства, и умолчать о ней значило бы ответить
# «Laves нет», не посмотрев на половину Laves.
E1_TCP_PHASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("P", ("P_PHASE",)),
    ("sigma", ("SIGMA",)),
    ("mu", ("MU_PHASE",)),
    ("chi", ("CHI_A12",)),
    ("Laves", ("LAVES", "LAV_C14")),
    ("R", ("R_PHASE",)),
    ("D_NiMo", ("D_NIMO",)),
)
# Упорядочение Ni2Cr — не ТКП, но постановка требует его отдельно.
E1_ORDERING_PHASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Ni2Cr", ("NI2CR",)),
)
E1_MATRIX_PHASE = "FCC_A1"
# Элементы, обеднение матрицы по которым и есть предмет задачи.
E1_MATRIX_ELEMENTS: tuple[str, ...] = ("CR", "MO")


# --------------------------------------------------------------------------- #
# Разбор одного равновесия
# --------------------------------------------------------------------------- #


def aggregate(result: Any) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Мольные доли фаз и составы фаз из результата ``equilibrium``.

    Свёртка та же, что у приложения (`thermogar_parallel._aggregate`):
    одинаковые имена фаз складываются, пустые имена и нефизичные доли
    отбрасываются, состав фазы усредняется по её вершинам с весами долей.
    Функция вызывается отсюда, а не переписывается, чтобы набор фаз и составы
    совпадали с тем, что на том же составе показала бы сама программа.
    """

    from thermogar_parallel import _aggregate

    return _aggregate(result, list(COMPONENTS))


def molar_mass_g_mol(ctx: Any, composition: Mapping[str, float]) -> float:
    """Средняя молярная масса фазы по её мольному составу, г/моль."""

    total = sum(float(value) for value in composition.values())
    if total <= 0.0:
        return 0.0
    return sum(
        float(value) / total * float(ctx.masses[element])
        for element, value in composition.items()
    )


def mass_percent(ctx: Any, composition: Mapping[str, float]) -> dict[str, float]:
    """Состав фазы в массовых процентах из её мольного состава."""

    weighted = {
        element: float(value) * float(ctx.masses[element])
        for element, value in composition.items()
    }
    total = sum(weighted.values())
    if total <= 0.0:
        return {element: 0.0 for element in composition}
    return {
        element: 100.0 * value / total for element, value in weighted.items()
    }


def point_payload(ctx: Any, mole: Mapping[str, float], temperature_c: float,
                  pdens: int) -> dict[str, Any]:
    """Полный разбор одного равновесия: доли фаз, составы фаз, молярные массы.

    Массовые доли фаз считаются здесь же и из тех же чисел: масса фазы —
    её мольная доля, умноженная на среднюю молярную массу её состава, а
    массовая доля — эта масса, отнесённая к сумме по всем фазам. Отдельного
    источника массовых долей в равновесии нет, поэтому путь назван прямо.
    """

    started = time.perf_counter()
    result = w11.solve_raw(ctx, mole, temperature_c, pdens)
    fractions, compositions = aggregate(result)
    del result
    gc.collect()

    kept = {
        name: value for name, value in fractions.items()
        if value > E1_PRESENT_FLOOR
    }
    masses = {
        name: value * molar_mass_g_mol(ctx, compositions[name])
        for name, value in kept.items()
    }
    mass_total = sum(masses.values())

    phases: dict[str, Any] = {}
    for name in sorted(kept):
        composition = {
            element: float(compositions[name].get(element, 0.0))
            for element in ELEMENT_ORDER
        }
        phases[name] = {
            "мольная доля": float(kept[name]),
            "массовая доля": (masses[name] / mass_total) if mass_total > 0.0 else 0.0,
            "молярная масса, г/моль": molar_mass_g_mol(ctx, composition),
            "состав, мольные доли": composition,
            "состав, масс. %": mass_percent(ctx, composition),
        }

    return {
        "T, °C": float(temperature_c),
        "pdens": int(pdens),
        "сумма мольных долей фаз": float(sum(kept.values())),
        "фаз": len(phases),
        "фазы": phases,
        "секунд": time.perf_counter() - started,
    }


def converged(payload: Mapping[str, Any]) -> bool:
    """Сошлась ли точка. Пустое решение и уехавшая сумма долей — не результат."""

    if not payload["фазы"]:
        return False
    return abs(float(payload["сумма мольных долей фаз"]) - 1.0) <= E1_SUM_TOLERANCE


# --------------------------------------------------------------------------- #
# Кэш точек на диске
# --------------------------------------------------------------------------- #


class PointCache:
    """Кэш разобранных точек, дописываемый построчно.

    Ключ — состав и температура. Плотность выборки в ключ не входит: она здесь
    не параметр исследования, а средство сойтись, и записанная в точке
    `pdens` говорит, какая помогла. Строка уходит на диск сразу после расчёта,
    поэтому обрыв по памяти теряет самое большее одну температуру.
    """

    def __init__(self) -> None:
        CACHE.mkdir(parents=True, exist_ok=True)
        self.path = CACHE / "e1_points.jsonl"
        self.records: dict[str, dict[str, Any]] = {}
        if self.path.is_file():
            for line in self.path.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                self.records[record["key"]] = record["payload"]
            log(f"кэш точек: {len(self.records)} температур")

    @staticmethod
    def key(mole: Mapping[str, float], temperature_c: float) -> str:
        return f"{w11.composition_id(mole)}|{temperature_c:.4f}"

    def get(self, mole: Mapping[str, float],
            temperature_c: float) -> dict[str, Any] | None:
        return self.records.get(self.key(mole, temperature_c))

    def put(self, mole: Mapping[str, float], temperature_c: float,
            payload: Mapping[str, Any]) -> None:
        key = self.key(mole, temperature_c)
        self.records[key] = dict(payload)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(
                {"key": key, "payload": payload},
                ensure_ascii=False, sort_keys=True,
            ) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


# --------------------------------------------------------------------------- #
# 12-2. Равновесия на сетке
# --------------------------------------------------------------------------- #


def temperatures() -> list[float]:
    return sorted(set(E1_GRID_C) | set(E1_REQUIRED_C))


def free_gib() -> float:
    import psutil

    return psutil.virtual_memory().available / 1024.0 ** 3


def e1_equilibria(force: bool = False) -> dict[str, Any]:
    """Равновесия во всех температурах. Считается в потомке."""

    cache = PointCache()
    if force:
        # Ключ пересчитанной точки тот же, и дописанная строка перекрыла бы
        # старую при следующем чтении. Файл всё равно обнуляется: держать в нём
        # две версии одной температуры незачем, а разбираться потом, какая
        # строка новее, — лишний повод для ошибки.
        cache.records.clear()
        if cache.path.is_file():
            cache.path.unlink()

    # База разбирается всегда, даже когда все температуры уже в кэше: ключ
    # кэша — мольный состав, а перевести массовые проценты в мольные доли без
    # атомных масс из базы нельзя. Разбор стоит десятки секунд, и обходить его
    # ценой второго определения атомных масс в проекте не стоит.
    free = free_gib()
    if free < MIN_FREE_GIB:
        return {
            "точки": [],
            "пропущено": [{
                "T, °C": None,
                "причина": (
                    f"свободной физической памяти {free:.1f} ГиБ при требуемых "
                    f"{MIN_FREE_GIB:.1f} ГиБ; база не разбиралась, прогон не "
                    f"начинался"
                ),
            }],
            "фаз в расчёте": None,
            "фазы расчёта": [],
            "исключено из расчёта": [],
            "ремонт базы доступен": None,
            "состав, мольные доли": {},
            "состав, масс. %": w11.full_wt(),
        }

    ctx = w11.Context()
    mole = w11.wt_to_mole(ctx, w11.full_wt())
    points: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for temperature in temperatures():
        cached = cache.get(mole, temperature)
        if cached is not None and converged(cached):
            points.append(cached)
            log(f"{temperature:.0f} °C из кэша: фаз {cached['фаз']}")
            continue

        free = free_gib()
        if free < E1_ABORT_FREE_GIB:
            skipped.append({
                "T, °C": float(temperature),
                "причина": (
                    f"свободной физической памяти {free:.1f} ГиБ, ниже порога "
                    f"остановки {E1_ABORT_FREE_GIB:.1f} ГиБ; остаток сетки не "
                    f"считался"
                ),
            })
            log(f"{temperature:.0f} °C и далее не считались: "
                f"свободно {free:.1f} ГиБ")
            break

        used_pdens = E1_PDENS
        payload = point_payload(ctx, mole, temperature, used_pdens)
        retries: list[int] = []
        for retry_pdens in E1_RETRY_PDENS:
            if converged(payload):
                break
            log(f"{temperature:.0f} °C: сумма долей "
                f"{payload['сумма мольных долей фаз']:.6f} при pdens={used_pdens}, "
                f"повтор при pdens={retry_pdens}")
            retries.append(used_pdens)
            del payload
            gc.collect()
            used_pdens = retry_pdens
            payload = point_payload(ctx, mole, temperature, used_pdens)

        payload["неудачные pdens"] = retries
        payload["сошлась"] = converged(payload)
        if payload["сошлась"]:
            cache.put(mole, temperature, payload)
        else:
            skipped.append({
                "T, °C": float(temperature),
                "причина": (
                    f"не сошлась ни при одной из плотностей выборки "
                    f"{[E1_PDENS, *E1_RETRY_PDENS]}: сумма мольных долей фаз "
                    f"{payload['сумма мольных долей фаз']:.6f}, фаз "
                    f"{payload['фаз']}"
                ),
            })
        points.append(payload)
        log(f"{temperature:.0f} °C: фаз {payload['фаз']}, "
            f"{' + '.join(sorted(payload['фазы']))}, "
            f"{payload['секунд']:.1f} с")
        gc.collect()

    return {
        "точки": points,
        "пропущено": skipped,
        "фаз в расчёте": len(ctx.phases),
        "фазы расчёта": list(ctx.phases),
        "исключено из расчёта": list(ctx.excluded_phases),
        "ремонт базы доступен": bool(ctx.repair_available),
        "состав, мольные доли": dict(mole),
        "состав, масс. %": w11.full_wt(),
    }


# --------------------------------------------------------------------------- #
# Таблицы
# --------------------------------------------------------------------------- #


def fraction_table(points: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Полный фазовый набор по температурам: имя, мольная и массовая доли."""

    rows: list[dict[str, Any]] = []
    for point in points:
        for name, phase in sorted(
            point["фазы"].items(), key=lambda item: -item[1]["мольная доля"]
        ):
            rows.append({
                "T, °C": point["T, °C"],
                "точка ТЗ": "да" if point["T, °C"] in E1_REQUIRED_C else "нет",
                "фаза": name,
                "мольная доля, %": 100.0 * phase["мольная доля"],
                "массовая доля, %": 100.0 * phase["массовая доля"],
                "молярная масса фазы, г/моль": phase["молярная масса, г/моль"],
                "pdens точки": point["pdens"],
                "сошлась": "да" if point.get("сошлась", True) else "нет",
            })
    return pd.DataFrame(rows)


def composition_table(points: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Состав каждой фазы по элементам: мольные доли и массовые проценты."""

    rows: list[dict[str, Any]] = []
    for point in points:
        for name, phase in sorted(point["фазы"].items()):
            row: dict[str, Any] = {
                "T, °C": point["T, °C"],
                "точка ТЗ": "да" if point["T, °C"] in E1_REQUIRED_C else "нет",
                "фаза": name,
                "мольная доля фазы, %": 100.0 * phase["мольная доля"],
                "массовая доля фазы, %": 100.0 * phase["массовая доля"],
            }
            for element in ELEMENT_ORDER:
                row[f"x({element})"] = phase["состав, мольные доли"][element]
            for element in ELEMENT_ORDER:
                row[f"{element}, масс. %"] = phase["состав, масс. %"][element]
            rows.append(row)
    return pd.DataFrame(rows)


def tcp_table(points: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """ТКП-фазы и упорядочение Ni2Cr: есть/нет, доля, состав.

    Строка пишется на каждую названную постановкой фазу в каждой температуре,
    в том числе когда фазы нет. Таблица «только найденное» отвечала бы на
    вопрос «есть ли σ при 580 °C» отсутствием строки, а это не ответ.
    """

    rows: list[dict[str, Any]] = []
    for point in points:
        for label, names in (*E1_TCP_PHASES, *E1_ORDERING_PHASES):
            found = [name for name in names if name in point["фазы"]]
            mole = sum(point["фазы"][name]["мольная доля"] for name in found)
            mass = sum(point["фазы"][name]["массовая доля"] for name in found)
            row: dict[str, Any] = {
                "T, °C": point["T, °C"],
                "точка ТЗ": "да" if point["T, °C"] in E1_REQUIRED_C else "нет",
                "фаза постановки": label,
                "имена в mc_ni": ", ".join(names),
                "тип": "ТКП" if any(
                    label == item[0] for item in E1_TCP_PHASES
                ) else "упорядочение",
                "есть": "да" if found else "нет",
                "найдено как": ", ".join(found) or "—",
                "мольная доля, %": 100.0 * mole,
                "массовая доля, %": 100.0 * mass,
            }
            # Состав пишется у той из найденных, которая больше: смешивать
            # составы двух разных фаз одного семейства в один столбец нельзя.
            leading = max(
                found, key=lambda name: point["фазы"][name]["мольная доля"],
                default=None,
            )
            for element in ELEMENT_ORDER:
                row[f"{element}, масс. %"] = (
                    point["фазы"][leading]["состав, масс. %"][element]
                    if leading is not None else None
                )
            rows.append(row)
    return pd.DataFrame(rows)


def matrix_table(points: Sequence[Mapping[str, Any]],
                 nominal_wt: Mapping[str, float]) -> pd.DataFrame:
    """Матрица FCC_A1 и её обеднение по хрому и молибдену.

    Обеднение считается против исходного состава сплава, а не против матрицы
    при какой-то другой температуре: постановка спрашивает именно это. Знак
    сохраняется — если элемент в матрице не обедняется, а обогащается, в
    столбце стоит плюс, и это видно.
    """

    rows: list[dict[str, Any]] = []
    for point in points:
        phase = point["фазы"].get(E1_MATRIX_PHASE)
        row: dict[str, Any] = {
            "T, °C": point["T, °C"],
            "точка ТЗ": "да" if point["T, °C"] in E1_REQUIRED_C else "нет",
            "FCC_A1 есть": "да" if phase is not None else "нет",
            "мольная доля FCC_A1, %": (
                100.0 * phase["мольная доля"] if phase is not None else None
            ),
            "массовая доля FCC_A1, %": (
                100.0 * phase["массовая доля"] if phase is not None else None
            ),
        }
        for element in E1_MATRIX_ELEMENTS:
            nominal = float(nominal_wt[element])
            actual = (
                phase["состав, масс. %"][element] if phase is not None else None
            )
            row[f"{element} в сплаве, масс. %"] = nominal
            row[f"{element} в FCC_A1, масс. %"] = actual
            row[f"{element}, сдвиг, масс. %"] = (
                None if actual is None else actual - nominal
            )
            row[f"{element}, доля от исходного, %"] = (
                None if actual is None or nominal <= 0.0
                else 100.0 * actual / nominal
            )
        rows.append(row)
    return pd.DataFrame(rows)


def balance_table(points: Sequence[Mapping[str, Any]],
                  nominal_wt: Mapping[str, float]) -> pd.DataFrame:
    """Сверка: состав, собранный обратно из фаз, против исходного.

    Проверка не декоративная. Массовые доли фаз и составы фаз считаются здесь
    из мольных долей и молярных масс, и если где-то потерян множитель, невязка
    это покажет. Столбец остаётся в результатах, чтобы числа можно было не
    брать на веру.
    """

    rows: list[dict[str, Any]] = []
    for point in points:
        for element in ELEMENT_ORDER:
            recombined = sum(
                phase["массовая доля"] * phase["состав, масс. %"][element]
                for phase in point["фазы"].values()
            )
            nominal = float(nominal_wt.get(element, 0.0))
            rows.append({
                "T, °C": point["T, °C"],
                "элемент": element,
                "в сплаве, масс. %": nominal,
                "собрано из фаз, масс. %": recombined,
                "невязка, масс. %": recombined - nominal,
            })
    return pd.DataFrame(rows)


def required_table(points: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Короткая таблица по точкам ТЗ: фаза в строке, температура в столбце.

    Мольные доли в процентах. Фазы ниже порога видимости в эту таблицу не
    попадают — они остаются в полной `e1_phase_fractions.csv`.
    """

    required = [point for point in points if point["T, °C"] in E1_REQUIRED_C]
    names = sorted({
        name for point in required
        for name, phase in point["фазы"].items()
        if phase["мольная доля"] > E1_VISIBLE_FLOOR
    })
    rows: list[dict[str, Any]] = []
    for name in names:
        row: dict[str, Any] = {"фаза": name}
        for point in required:
            phase = point["фазы"].get(name)
            row[f"{point['T, °C']:.0f} °C, мольн. %"] = (
                100.0 * phase["мольная доля"] if phase is not None else 0.0
            )
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# График
# --------------------------------------------------------------------------- #


def plot_e1(fractions: pd.DataFrame, matrix: pd.DataFrame,
            nominal_wt: Mapping[str, float], path: Path) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))

    visible = fractions[fractions["мольная доля, %"] > 100.0 * E1_VISIBLE_FLOOR]
    for name in sorted(visible["фаза"].unique()):
        series = visible[visible["фаза"] == name].sort_values("T, °C")
        axes[0].plot(series["T, °C"], series["мольная доля, %"],
                     marker="o", markersize=3, linewidth=1.4, label=name)
    for temperature in E1_REQUIRED_C:
        axes[0].axvline(temperature, color="0.6", linewidth=0.8, linestyle=":")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("температура, °C")
    axes[0].set_ylabel("мольная доля фазы, %")
    axes[0].set_title("Равновесный фазовый набор; пунктир — точки ТЗ")
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=7, ncol=2)

    present = matrix[matrix["FCC_A1 есть"] == "да"].sort_values("T, °C")
    for element, colour in (("CR", "tab:blue"), ("MO", "tab:red")):
        axes[1].plot(present["T, °C"], present[f"{element} в FCC_A1, масс. %"],
                     marker="o", markersize=3, linewidth=1.6, color=colour,
                     label=f"{element} в FCC_A1")
        axes[1].axhline(float(nominal_wt[element]), color=colour, linewidth=0.9,
                        linestyle="--", label=f"{element} в сплаве")
    for temperature in E1_REQUIRED_C:
        axes[1].axvline(temperature, color="0.6", linewidth=0.8, linestyle=":")
    axes[1].set_xlabel("температура, °C")
    axes[1].set_ylabel("масс. %")
    axes[1].set_title("Матрица FCC_A1: хром и молибден против исходного состава")
    axes[1].grid(alpha=0.3)
    axes[1].legend(fontsize=7)

    figure.suptitle(
        "12-2. Равновесия ЭК199-ВИ (основа без скандия), mc_ni 2.036, "
        f"pdens {E1_PDENS}"
    )
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


# --------------------------------------------------------------------------- #
# Служебное: запись, прогресс, память, потомок
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


def database_sha256() -> str:
    digest = hashlib.sha256()
    with (ROOT / DB_REL).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def memory_report(stem: str, record: Mapping[str, Any], seconds: float,
                  final: bool = True) -> Path | None:
    """Итог замера памяти рядом с результатами подпункта.

    Замер устроен как у волны 11 (`memory_probe` оттуда и вызывается), но файл
    кладётся в каталог волны 12 и под её именем, иначе два прогона переписывали
    бы друг друга.
    """

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
    path = OUT / f"e1_memory_{stem}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    if not final:
        return path
    log(
        f"память: пик набора {payload['пик рабочего набора дерева, ГиБ']:.2f} ГиБ, "
        f"минимум свободной {payload['минимум свободной физической, ГиБ']:.2f} ГиБ, "
        f"прирост подкачки {payload['прирост занятой подкачки в системе, ГиБ']:+.2f} ГиБ"
    )
    return path


def memory_watch(process: Any, stop: Any, record: dict[str, Any],
                 stem: str) -> None:
    """Фоновый опрос памяти потомка до его завершения. В расчёт не вмешивается."""

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
                record.get("начало, perf_counter", time.perf_counter())
            ), final=False)
            flushed = now


def run_child(arguments: Sequence[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Тяжёлый кусок — в отдельном процессе; результат приходит файлом.

    Возврат через файл, а не через stdout: лог должен идти на экран по мере
    счёта, а не копиться в трубе до конца работы потомка. Пока потомок считает,
    родитель опрашивает его память в отдельном потоке.
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
# Подпункт 12-2 целиком
# --------------------------------------------------------------------------- #


def tcp_verdict(tcp: pd.DataFrame) -> list[dict[str, Any]]:
    """По каждой названной постановкой фазе — где она есть и сколько её."""

    verdict: list[dict[str, Any]] = []
    for label in [item[0] for item in (*E1_TCP_PHASES, *E1_ORDERING_PHASES)]:
        block = tcp[tcp["фаза постановки"] == label]
        present = block[block["есть"] == "да"]
        required = present[present["точка ТЗ"] == "да"]
        verdict.append({
            "фаза": label,
            "имена в mc_ni": block["имена в mc_ni"].iloc[0] if len(block) else "",
            "встречается": bool(len(present)),
            "температур с фазой": int(len(present)),
            "температур всего": int(len(block)),
            "интервал, °C": (
                [float(present["T, °C"].min()), float(present["T, °C"].max())]
                if len(present) else None
            ),
            "в точках ТЗ": sorted(float(value) for value in required["T, °C"]),
            "наибольшая мольная доля, %": (
                float(present["мольная доля, %"].max()) if len(present) else 0.0
            ),
            "при T, °C": (
                float(present.loc[present["мольная доля, %"].idxmax(), "T, °C"])
                if len(present) else None
            ),
        })
    return verdict


def step_e1(force: bool = False) -> None:
    progress = load_progress()
    if progress.get("12-2", {}).get("готов") and not force:
        log("12-2 пропущен, посчитан ранее (--force для пересчёта)")
        return

    # Проверка памяти в родителе: порог тот же, что у волны 11. Если она не
    # проходит, потомок не запускается вовсе, и это видно в результатах.
    free = free_gib()
    cache_ready = (CACHE / "e1_points.jsonl").is_file() and not force
    if free < MIN_FREE_GIB and not cache_ready:
        write_json({
            "подпункт": "12-2. Равновесия ЭК199-ВИ в точках ТЗ ИЖСР-1476",
            "прогон": "не начинался",
            "причина": (
                f"свободной физической памяти {free:.2f} ГиБ при требуемых "
                f"{MIN_FREE_GIB:.1f} ГиБ (порог волны 11, J2_MIN_FREE_GIB)"
            ),
        }, "e1_summary.json")
        log(f"12-2 не запускался: свободно {free:.2f} ГиБ при требуемых "
            f"{MIN_FREE_GIB:.1f} ГиБ")
        return

    payload, measurement = run_child(["--e1", "1"] + (["--force"] if force else []))
    measurement["свободной физической перед запуском, ГиБ"] = round(free, 2)
    points = payload["точки"]
    nominal_wt = payload["состав, масс. %"]

    fractions = fraction_table(points)
    write_csv(fractions, "e1_phase_fractions.csv")
    compositions = composition_table(points)
    write_csv(compositions, "e1_phase_compositions.csv")
    tcp = tcp_table(points)
    write_csv(tcp, "e1_tcp_and_ordering.csv")
    matrix = matrix_table(points, nominal_wt)
    write_csv(matrix, "e1_matrix_fcc_a1.csv")
    balance = balance_table(points, nominal_wt)
    write_csv(balance, "e1_mass_balance.csv")
    required = required_table(points)
    write_csv(required, "e1_required_points.csv")
    plot_e1(fractions, matrix, nominal_wt, OUT / "e1_equilibria.png")

    matrix_present = matrix[matrix["FCC_A1 есть"] == "да"]
    summary = {
        "подпункт": "12-2. Равновесия ЭК199-ВИ (ХН62М(Sc)-ВИ) в точках ТЗ ИЖСР-1476",
        "база": DB_REL,
        "sha256 базы": database_sha256(),
        "ремонт базы доступен": payload["ремонт базы доступен"],
        "фаз в расчёте": payload["фаз в расчёте"],
        "исключено из расчёта": payload["исключено из расчёта"],
        "фазы расчёта": payload["фазы расчёта"],
        "состав, масс. %": nominal_wt,
        "состав, мольные доли": payload["состав, мольные доли"],
        "скандий": (
            "в mc_ni 2.036 скандия нет; счёт идёт по составу без него, то есть "
            "по основе сплава ЭК199-ВИ, а не по сплаву со скандием"
        ),
        "точки ТЗ, °C": list(E1_REQUIRED_C),
        "сетка, °C": list(E1_GRID_C),
        "температур посчитано": len(points),
        "pdens": E1_PDENS,
        "ряд повторов pdens": list(E1_RETRY_PDENS),
        "порог запуска, свободной физической ГиБ": MIN_FREE_GIB,
        "порог остановки по ходу, свободной физической ГиБ": E1_ABORT_FREE_GIB,
        "порог присутствия фазы, мольные доли": E1_PRESENT_FLOOR,
        "допуск на сумму мольных долей": E1_SUM_TOLERANCE,
        "температуры, не сошедшиеся с первого раза": [
            {"T, °C": point["T, °C"], "неудачные pdens": point["неудачные pdens"],
             "сошлась при pdens": point["pdens"]}
            for point in points if point.get("неудачные pdens")
        ],
        "пропущено": payload["пропущено"],
        "наибольшая невязка баланса, масс. %": float(
            balance["невязка, масс. %"].abs().max()
        ) if len(balance) else None,
        "ТКП и упорядочение": tcp_verdict(tcp),
        "матрица FCC_A1": {
            "мольная доля, % — минимум": float(
                matrix_present["мольная доля FCC_A1, %"].min()
            ) if len(matrix_present) else None,
            "мольная доля, % — максимум": float(
                matrix_present["мольная доля FCC_A1, %"].max()
            ) if len(matrix_present) else None,
            "CR в FCC_A1, масс. % — минимум": float(
                matrix_present["CR в FCC_A1, масс. %"].min()
            ) if len(matrix_present) else None,
            "MO в FCC_A1, масс. % — минимум": float(
                matrix_present["MO в FCC_A1, масс. %"].min()
            ) if len(matrix_present) else None,
        },
        "замер памяти": measurement,
        "чего расчёт не устанавливает": [
            "равновесие не говорит, за какое время фаза появится; про ресурс "
            "10 лет (87 600 ч) из него не следует ничего — это задача 12-1",
            "скандия в расчёте нет, его влияние здесь не оценивается никак",
        ],
    }
    write_json(summary, "e1_summary.json")

    # Готовым подпункт считается только когда посчитана вся сетка и каждая
    # точка сошлась. Иначе повторный запуск обязан дойти до непосчитанного, а
    # не сообщить, что всё готово.
    complete = (
        not payload["пропущено"]
        and len(points) == len(temperatures())
        and all(point.get("сошлась", True) for point in points)
    )
    progress["12-2"] = {
        "готов": complete,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "температур посчитано": len(points),
        "температур в сетке": len(temperatures()),
        "пропущено": len(payload["пропущено"]),
        "pdens": E1_PDENS,
        "режим набора фаз": "все фазы",
    }
    save_progress(progress)


STEPS = {"e1": step_e1}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Волна 12, подпункт 12-2: равновесия ЭК199-ВИ в точках ТЗ"
    )
    parser.add_argument("--only", default="all", help="e1; через запятую")
    parser.add_argument("--force", action="store_true", help="пересчитать готовое")
    parser.add_argument("--e1", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--handoff", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    if args.e1 is not None:
        payload = e1_equilibria(force=args.force)
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
