#!/usr/bin/env python3
"""Волна 12, подпункт 12-1 — кинетика выделения P-фазы в ЭК199-ВИ.

Задание `tasks/WAVE12_1_OPUS.md`, отчёт `tasks/WAVE12_1_REPORT.md`. Контекст —
ТЗ ИЖСР-1476: цикл испытаний 200 ч и ресурс 10 лет (87 600 ч) при 700 и
750 °C. Подпункт 12-2 нашёл, что P-фаза в этих точках равновесно есть
(22,31 и 19,10 мольн. %); здесь спрашивается, за какое время она появляется.

Считает KWN-модель пакета kawin 0.5.0 тем же путём, которым её зовёт само
приложение: класс термодинамики строит `thermogar_precipitation.
_build_precipitation_thermodynamics`, номенклатура мест зарождения и предел
применимости геометрии гетерогенного зарождения — `NUCLEATION_TYPES` и
`HETEROGENEOUS_RATIO_LIMITS` того же модуля. Своей реализации KWN здесь нет.

ГЛАВНОЕ. Межфазной энергии матрица/P-фаза в базе нет, эксперимента для
подгонки нет. Поэтому результат — карта чувствительности: межфазная энергия
пробегает диапазон, места зарождения берутся двумя предельными случаями
(объём зерна и границы зёрен), а вывод формулируется как порог по межфазной
энергии, а не как одно время. Абсолютная шкала времени верна ровно настолько,
насколько верна межфазная энергия.

Что взято импортом, а не переписано: база, состав, атомные массы, перевод
масс. % в мольные доли, формат таблиц, оба порога памяти, опрос памяти
(`w11.memory_probe`), запись CSV и JSON, журнал прогресса. Скопированы три
служебные функции — `memory_report`, `memory_watch` и `run_child`: первая и
вторая пишут файл замера под префиксом своего подпункта, третья запускает
`Path(__file__)` своего модуля, то есть `w12.run_child` запустил бы волну 12-2.
Ровно та же причина и то же решение, что в подпункте 12-4.

Запуск (интерпретатор — venv основного репозитория, PYTHONHASHSEED=0):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 ^
        tools\\study_hn62m_wave12_kinetics.py --only k1

Память. Порог запуска — `w12.MIN_FREE_GIB` (4,0 ГиБ, значение волны 11
`J2_MIN_FREE_GIB`), порог остановки по ходу — `w12.E1_ABORT_FREE_GIB`
(1,0 ГиБ). Оба берутся импортом. Тяжёлый счёт идёт в отдельном процессе,
каждая посчитанная точка сетки времени дописывается в кэш на диск сразу,
повторный запуск продолжает с первого несчитанного случая.

Границы достоверности живут в отчёте. Из кода видно только то, что здесь
названо: скандия в списке компонентов нет, потому что его нет в mc_ni; ниобия
нет, потому что kawin 0.5.0 не собирает модель подвижности FCC_A1 с ниобием в
наборе компонентов; межфазная энергия задана диапазоном, а не измерена.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
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
import numpy as np
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

# Пороги памяти — значения волны 12-2, а не свои. Расходиться им нельзя: это
# один и тот же счёт на одной и той же машине.
MIN_FREE_GIB = w12.MIN_FREE_GIB
ABORT_FREE_GIB = w12.E1_ABORT_FREE_GIB

# Порог входа можно понизить ключом запуска `--min-free-gib`, и только им:
# константа выше остаётся значением волны 11, её никто не переписывает.
# Зачем ключ. Порог 4,0 ГиБ назначался волной 11J под расчёт Шейля с пиком
# 2,3 ГиБ (двукратный запас, округлённый вниз). KWN-прогон этого подпункта
# держит на порядок меньше: замеренный пик рабочего набора потомка — десятые
# доли гигабайта. На машине, где посторонним занято около 12 ГиБ из 15,7,
# порог 4,0 не пускает счёт, который сам по себе помещается в полгигабайта.
# Понижение — отступление от задания, оно требует санкции мастера и называется
# в отчёте отдельным пунктом вместе с фактическим значением порога, которое
# уходит в сводку подпункта. Порог аварийной остановки по ходу
# (`ABORT_FREE_GIB`) не понижается никогда и ключа не имеет: он защищает не
# от напрасного старта, а от свопа на полном ходу.

DB_REL = w12.DB_REL
PDB_REL = w11.PDB_REL

AVOGADRO = 6.02214076e23
GAS_CONSTANT = w11.A3_GAS_CONSTANT
BOLTZMANN = GAS_CONSTANT / AVOGADRO

# --------------------------------------------------------------------------- #
# Химия расчёта
# --------------------------------------------------------------------------- #

# Матрица и выделение. KWN-модель — двухфазная по устройству: одна однородная
# матрица и одно выделение. Полный равновесный набор волны 12-2 (48 фаз) здесь
# не воспроизводим, и насколько это стоит по доле P-фазы — считается ниже
# функцией `reference_equilibrium` и попадает в сводку.
MATRIX_PHASE = "FCC_A1"
PRECIPITATE_PHASE = "P_PHASE"

# Ниобий исключён из набора компонентов. Причина не в физике, а в инструменте:
# `kawin.thermo.Thermodynamics._buildMobilityModels` строит MOB_NB для FCC_A1
# через symengine, и компиляция падает с `RuntimeError: ln(1.0, 0.0)`. Проверено
# поэлементно: с любым другим из десяти элементов состава класс собирается, с
# ниобием — нет, и в наборе {NI, CR, MO, NB} падает уже на одной FCC_A1.
# Ниобия в контрольном составе 0,06 масс. %; чего стоит его исключение по доле
# P-фазы, посчитано и названо в сводке.
DROPPED_ELEMENTS: tuple[str, ...] = ("NB",)
DROPPED_REASON = (
    "kawin 0.5.0 не собирает модель подвижности FCC_A1 с ниобием в наборе "
    "компонентов: symengine падает с RuntimeError: ln(1.0, 0.0) в "
    "Thermodynamics._buildMobilityModels"
)

# Элементы, обеднение матрицы по которым и есть предмет задачи. Значение
# волны 12-2, не своё.
MATRIX_ELEMENTS: tuple[str, ...] = tuple(w12.E1_MATRIX_ELEMENTS)

# --------------------------------------------------------------------------- #
# Сетка карты чувствительности
# --------------------------------------------------------------------------- #

# Температуры ТЗ, по которым ставится вопрос о кинетике. Обе есть в списке
# точек ТЗ волны 12-2 (`w12.E1_REQUIRED_C`), проверяется при старте.
K_TEMPERATURES_C: tuple[float, ...] = (700.0, 750.0)

# Межфазная энергия, Дж/м². Диапазон задания 0,05…0,50. Шаг логарифмический, а
# не равномерный, и вот почему: барьер зарождения растёт как γ³, а движущая
# сила на P-фазу мала (≈1,6 кДж/моль при 700 °C, ≈1,3 при 750 °C), поэтому
# переход «выделяется / не выделяется» лежит у нижнего края диапазона.
# Равномерный шаг 0,05 дал бы одну-две различимые кривые и восемь нулевых.
K_GAMMA: tuple[float, ...] = (0.05, 0.075, 0.10, 0.15, 0.25, 0.50)

# Два предельных случая по местам зарождения. Имена — из номенклатуры
# приложения (`thermogar_precipitation.NUCLEATION_TYPES`), не свои.
K_SITES: tuple[tuple[str, str], ...] = (
    ("объём зерна", "BULK"),
    ("границы зёрен", "GRAIN BOUNDARIES"),
)

# Горизонты ТЗ. Обязаны быть узлами сетки времени, а не интерполяцией.
K_HORIZONS_H: tuple[float, ...] = (200.0, 87600.0)

# Сетка времени: логарифмическая от K_T_MIN_H до 87 600 ч. Модель решается
# одним непрерывным прогоном, а узел сетки — это шаг решателя, попавший ближе
# всех к узлу: kawin записывает состояние на каждом принятом шаге, и брать
# оттуда дешевле и точнее, чем прерывать решение на каждом узле.
#
# Почему прерывать дорого. `KWNEuler.getDt` наращивает шаг всего на
# `dtScale = 1e-3`, то есть на 0,1 % за шаг, а в конце интервала решения
# обрезает его остатком интервала (`dtMax = finalTime - time`). Каждое
# прерывание поэтому отбрасывает шаг вниз, и следующий интервал заново
# набирает его сотнями шагов. Прерываний ровно столько, сколько нужно, чтобы
# 200 ч и 87 600 ч были не ближайшими шагами, а точными концами интервалов:
# по одному на декаду плюс оба горизонта ТЗ.
K_T_MIN_H = 1.0e-3
K_PER_DECADE = 4

# Размер зерна, мкм. Входит только в плотность центров на границах зёрен
# (`kawin` считает GBareaN0 обратно пропорционально размеру зерна). Не
# измерение: сертификата на зерно ЭК199-ВИ в проекте нет, позиция выписана в
# `tasks/SOURCES_WANTED.md`. Объявленный вход сценария, как это помечает и
# приложение (`DEFAULT_INPUT_PROVENANCE`).
K_GRAIN_SIZE_UM = 30.0
# Плотность дислокаций — умолчание kawin (5e12 1/м²). В расчёт не входит:
# дислокации не входят ни в один из двух предельных случаев.
K_DISLOCATION_DENSITY = 5.0e12

# Отношение энергии границы зерна к межфазной. Геометрия гетерогенного
# зарождения в kawin определена только при gbEnergy / (2 γ) < 1
# (`HETEROGENEOUS_RATIO_LIMITS['GRAIN BOUNDARIES']`), то есть при
# gbEnergy < 2 γ. Измеренная энергия границы зерна в никеле — величина порядка
# 0,8 Дж/м², и она больше 2 γ на всём диапазоне 0,05…0,50, поэтому подставить
# её нельзя: модель там не определена. Взято gbEnergy = γ, то есть отношение
# 0,5 — середина области определения, одинаковая для всех γ. Это объявленная
# геометрия смачивания, а не измерение.
K_GB_ENERGY_FACTOR = 1.0

# Параметры сетки размеров PBM — библиотечные умолчания kawin
# (`KWNEuler.setPBMParameters`: cMin 1e-10 м, cMax 1e-9 м, 150 классов,
# адаптивно). Свои числа здесь опасны: сетка линейна по радиусу, и при cMax
# шире критического радиуса на порядки первый класс оказывается крупнее
# зародыша, доля выделений улетает в 100 % на первом же шаге. Проверено.
K_PBM = dict(cMin=1.0e-10, cMax=1.0e-9, bins=150, minBins=100, maxBins=200,
             adaptive=True)

# Порог «выделения есть» по мольной доле P-фазы. Тот же, что порог видимости
# фазы в волне 12-2 (`w12.E1_VISIBLE_FLOOR`), чтобы «есть» в кинетике и «есть»
# в равновесии значили одно и то же.
PRESENT_FLOOR = w12.E1_VISIBLE_FLOOR

# Доля равновесия, по достижении которой случай считается «дошедшим».
#
# 0,90, а не 0,95, и причина в поведении самой модели, а не в желании смягчить
# критерий. KWN — среднеполевая модель: после того как зарождение кончилось,
# доля выделений подходит к равновесию через огрубление, то есть логарифмически
# медленно. В посчитанных случаях с полным выделением доля за 87 600 ч выходит
# на 94…95 % равновесия собственной двухфазной задачи и продолжает ползти
# вверх. Порог 0,95 пометил бы такой случай как «не дошло», а это не то, что
# он должен различать: различать он должен «выделилось» и «не выделилось».
# Сколько именно набралось — стоит отдельным числом в столбце «доля
# равновесия», и вывод строится по нему, а не по этому признаку.
REACHED_FRACTION = 0.90


def elements() -> list[str]:
    """Компоненты расчёта: основа первой, дальше по алфавиту.

    Порядок важен: `MatrixParameters` принимает растворённые элементы в том же
    порядке, в каком они идут в векторе состава, и kawin трактует первый
    элемент как основу.
    """

    rest = sorted(
        name for name in w11.ELEMENTS
        if name != w11.BALANCE and name not in DROPPED_ELEMENTS
    )
    return [w11.BALANCE, *rest]


def working_wt() -> dict[str, float]:
    """Контрольный состав волны 12 без исключённых элементов, масс. %.

    Состав не перепечатывается: берётся `w11.full_wt()`, то есть та же
    `CONTROL_WT`, которую импортирует и волна 12-2. Исключённые элементы
    выбрасываются, а основа пересчитывается, чтобы сумма осталась 100 %.
    """

    values = {
        name: value for name, value in w11.full_wt().items()
        if name not in DROPPED_ELEMENTS
    }
    values[w11.BALANCE] = 100.0 - sum(
        value for name, value in values.items() if name != w11.BALANCE
    )
    return values


def mass_percent(ctx: Any, mole: Mapping[str, float]) -> dict[str, float]:
    """Мольные доли в массовые проценты. Молярные массы — из базы."""

    weighted = {
        name: float(value) * float(ctx.masses[name])
        for name, value in mole.items()
    }
    total = sum(weighted.values())
    if total <= 0.0:
        return {name: 0.0 for name in mole}
    return {name: 100.0 * value / total for name, value in weighted.items()}


def time_nodes(t_min_h: float = K_T_MIN_H,
               per_decade: int = K_PER_DECADE) -> list[float]:
    """Логарифмическая сетка времени с горизонтами ТЗ в узлах."""

    top = math.log10(max(K_HORIZONS_H))
    low = math.log10(t_min_h)
    count = max(1, int(round((top - low) * per_decade)))
    nodes = {round(10.0 ** (low + (top - low) * index / count), 12)
             for index in range(count + 1)}
    nodes.update(float(value) for value in K_HORIZONS_H)
    return sorted(value for value in nodes if value <= max(K_HORIZONS_H))


def stage_edges(t_min_h: float = K_T_MIN_H) -> list[float]:
    """Концы интервалов непрерывного решения: по одному на декаду и горизонты.

    Решение прерывается только здесь, и только по двум причинам: горизонты ТЗ
    должны быть точными концами интервалов, а не ближайшими шагами, и
    посчитанное надо отдавать на диск не одним куском в конце, а по ходу.
    Узлы сетки времени внутри интервала берутся из записанных шагов решателя.
    """

    top = math.log10(max(K_HORIZONS_H))
    low = math.log10(t_min_h)
    edges = {round(10.0 ** value, 12)
             for value in np.arange(math.ceil(low), math.floor(top) + 1.0)}
    edges.update(float(value) for value in K_HORIZONS_H)
    return sorted(value for value in edges if value <= max(K_HORIZONS_H))


# --------------------------------------------------------------------------- #
# Молярные объёмы и равновесная опорная точка
# --------------------------------------------------------------------------- #


def phase_molar_volumes(ctx: Any, physical_db: Any, mole: Mapping[str, float],
                        temperature_c: float) -> dict[str, Any]:
    """Молярные объёмы матрицы и P-фазы, см³/моль, из баз проекта.

    KWN требует молярные объёмы обеих фаз, и придумывать их нельзя. Плотность
    фазы берётся тем же путём, которым её считает приложение
    (`thermogar_physical.calculate_physical_properties` на той же базе
    плотностей `physical_data_v103.pdb`), молярная масса фазы — из её
    равновесного состава и атомных масс базы. Объём есть отношение одного к
    другому.

    Статус данных возвращается вместе с числом и не прячется: у P-фазы
    собственной модели плотности в PDB нет, и её плотность — оценка по правилу
    смеси. Волна 12-2 называла P_PHASE в том же качестве
    (`w11.A2_WATCHED_PHASES`).

    Состав здесь — полный, одиннадцатикомпонентный, а не сокращённый набор
    KWN. Причина: `w11.solve_raw` считает равновесие на глобальном списке
    `COMPONENTS`, и подменять его ради 0,06 масс. % ниобия значило бы получить
    молярные объёмы не тем путём, которым их получила волна 12-2 на той же
    базе плотностей. Объёмы фаз от ниобия в таком количестве не зависят, а
    сверять числа с 12-2 построчно — зависит.
    """

    from thermogar_physical import calculate_physical_properties

    result = w11.solve_raw(ctx, mole, temperature_c, w11.A2_PDENS)
    physical = calculate_physical_properties(
        ctx.db, result, list(w11.ELEMENTS), temperature_c + 273.15, physical_db
    )
    fractions, compositions = w12.aggregate(result)
    del result
    gc.collect()

    table = physical.phase_table
    payload: dict[str, Any] = {"T, °C": float(temperature_c)}
    for phase in (MATRIX_PHASE, PRECIPITATE_PHASE):
        rows = table[table["Фаза"] == phase] if not table.empty else table
        if rows.empty or phase not in compositions:
            raise RuntimeError(
                f"нет плотности фазы {phase} при {temperature_c:.0f} °C: "
                "молярный объём для KWN взять не из чего"
            )
        density = float(rows["Плотность фазы, кг/м³"].iloc[0])
        status = str(rows["Статус данных"].iloc[0])
        molar_mass = w12.molar_mass_g_mol(ctx, compositions[phase])
        payload[phase] = {
            "плотность, кг/м³": density,
            "статус плотности": status,
            "молярная масса, г/моль": molar_mass,
            # г/моль / (кг/м³) = 1e-3 м³/моль / 1e3 = 1e-6 м³/моль = см³/моль
            "молярный объём, см³/моль": 1.0e3 * molar_mass / density,
            "равновесная мольная доля фазы, %": 100.0 * float(
                fractions.get(phase, 0.0)
            ),
        }
    return payload


def reference_equilibrium(ctx: Any, mole: Mapping[str, float],
                          temperature_c: float) -> dict[str, Any]:
    """Равновесие в той же паре фаз и том же наборе компонентов, что у KWN.

    Нужно, чтобы предел кинетики сравнивался с равновесием той же задачи, а не
    только с числом волны 12-2, посчитанным на 48 фазах и одиннадцати
    компонентах. Разница между двумя равновесиями — цена сокращения, и она
    должна быть видна отдельно от расхождений самой кинетики.
    """

    from pycalphad import equilibrium, variables as v

    components = [*elements(), "VA"]
    conditions: dict[Any, float] = {
        v.P: 101325.0, v.N: 1.0, v.T: float(temperature_c) + 273.15
    }
    for name, value in sorted(mole.items()):
        if name != w11.BALANCE:
            conditions[v.X(name)] = float(value)
    result = equilibrium(
        ctx.db, components, [MATRIX_PHASE, PRECIPITATE_PHASE], conditions,
        calc_opts={"pdens": w11.A2_PDENS},
    )
    from thermogar_parallel import _aggregate

    fractions, compositions = _aggregate(result, components)
    del result
    gc.collect()

    matrix = compositions.get(MATRIX_PHASE, {})
    matrix_wt = mass_percent(ctx, matrix) if matrix else {}
    return {
        "T, °C": float(temperature_c),
        "мольная доля P-фазы, %": 100.0 * float(
            fractions.get(PRECIPITATE_PHASE, 0.0)
        ),
        "мольная доля FCC_A1, %": 100.0 * float(fractions.get(MATRIX_PHASE, 0.0)),
        "матрица, мольные доли": {
            name: float(value) for name, value in sorted(matrix.items())
        },
        "матрица, масс. %": {
            name: float(matrix_wt.get(name, 0.0)) for name in sorted(matrix)
        },
    }


def wave12_2_targets() -> dict[str, Any]:
    """Равновесная цель подпункта 12-2: доля P-фазы и обеднение матрицы.

    Читается из результатов 12-2 на диске, а не переписывается числами в код.
    Если файлов нет, поля остаются пустыми, и это видно в сводке: подставлять
    числа по памяти правило «Источники» запрещает и для своих результатов тоже.
    """

    payload: dict[str, Any] = {
        "источник": "results/hn62m_wave12/e1_phase_fractions.csv "
                    "и e1_matrix_fcc_a1.csv (подпункт 12-2)",
        "доля P-фазы, мольн. %": {},
        "матрица FCC_A1, масс. %": {},
    }
    fractions_path = OUT / "e1_phase_fractions.csv"
    matrix_path = OUT / "e1_matrix_fcc_a1.csv"
    if fractions_path.is_file():
        table = pd.read_csv(fractions_path, **CSV_READ)
        for temperature in K_TEMPERATURES_C:
            rows = table[(table["T, °C"] == temperature)
                         & (table["фаза"] == PRECIPITATE_PHASE)]
            if len(rows):
                payload["доля P-фазы, мольн. %"][f"{temperature:.0f}"] = float(
                    rows["мольная доля, %"].iloc[0]
                )
    if matrix_path.is_file():
        table = pd.read_csv(matrix_path, **CSV_READ)
        for temperature in K_TEMPERATURES_C:
            rows = table[table["T, °C"] == temperature]
            if not len(rows):
                continue
            payload["матрица FCC_A1, масс. %"][f"{temperature:.0f}"] = {
                element: float(rows[f"{element} в FCC_A1, масс. %"].iloc[0])
                for element in MATRIX_ELEMENTS
            }
    return payload


def gamma_estimate_available() -> dict[str, Any]:
    """Умеет ли kawin 0.5.0 сам оценить межфазную энергию.

    Проверено по установленному пакету: ни `kawin.thermo`, ни
    `kawin.precipitation.parameters` не содержат ни одной функции оценки
    межфазной энергии — ни приближением широкой границы раздела, ни
    разорванных связей, ни какого-либо другого. `gamma` есть только как
    входное поле `PrecipitateParameters.gamma`, которое обязан заполнить
    пользователь, иначе `NucleationBarrierParameters` поднимает ValueError.

    Поэтому опорной точки «оценка модели» в этом расчёте нет. Считать её по
    формуле из памяти правило «Источники» запрещает; позиция на приближение
    широкой границы раздела выписана в `tasks/SOURCES_WANTED.md`.
    """

    import kawin
    from kawin.precipitation import PrecipitateParameters

    names = sorted(
        name for name in dir(PrecipitateParameters)
        if "gamma" in name.lower() or "interfacial" in name.lower()
    )
    return {
        "kawin": getattr(kawin, "__version__", "0.5.0"),
        "оценка межфазной энергии в kawin": False,
        "что есть вместо неё": names,
        "вывод": (
            "kawin 0.5.0 межфазную энергию не оценивает: gamma — обязательный "
            "вход модели. Опорной точки «оценка модели» в подпункте нет, "
            "источник на приближение широкой границы раздела выписан в "
            "tasks/SOURCES_WANTED.md"
        ),
    }


# --------------------------------------------------------------------------- #
# Кэш случаев на диске
# --------------------------------------------------------------------------- #


VOLUMES_PATH_NAME = "k1_volumes.json"


def volumes_and_references(ctx: Any, mole: Mapping[str, float],
                           mole_full: Mapping[str, float]
                           ) -> tuple[dict[float, dict[str, Any]],
                                      dict[float, dict[str, Any]]]:
    """Молярные объёмы и равновесие двух фаз — из кэша, иначе посчитать.

    Кэш здесь не ради скорости, а ради памяти, и это главное в устройстве
    подпункта. Молярные объёмы берутся из равновесия на полном наборе 48 фаз,
    а `w11.Context.compiled` строит символьные модели всех сорока восьми и
    держит их до конца процесса: около 1,3 ГиБ рабочего набора, которые
    KWN-счёту не нужны совсем — он работает на двух фазах. Освободить их
    внутри процесса не помогает: CPython отпускает объекты, но не возвращает
    арены системе, и рабочий набор остаётся прежним (проверено).

    Поэтому тяжёлое равновесие считается один раз, результат ложится на диск,
    и долгий прогон кинетики его читает, ни разу не трогая `compiled()`.
    Первый прогон подпункта этого не делал и был снят системой по нехватке
    памяти на пятнадцатом случае из двадцати четырёх.
    """

    path = CACHE / VOLUMES_PATH_NAME
    if path.is_file():
        stored = json.loads(path.read_text("utf-8"))
        if stored.get("состав, мольные доли id") == w11.composition_id(mole):
            volumes = {float(key): value
                       for key, value in stored["молярные объёмы"].items()}
            references = {float(key): value
                          for key, value in stored["равновесие двух фаз"].items()}
            if all(temperature in volumes and temperature in references
                   for temperature in K_TEMPERATURES_C):
                log(f"молярные объёмы и равновесие двух фаз из кэша "
                    f"({path.name}); модели 48 фаз не строятся")
                return volumes, references

    from thermogar_physical import PhysicalDensityDatabase

    physical_db = PhysicalDensityDatabase(str(ROOT / PDB_REL))
    volumes: dict[float, dict[str, Any]] = {}
    references: dict[float, dict[str, Any]] = {}
    for temperature in K_TEMPERATURES_C:
        volumes[temperature] = phase_molar_volumes(
            ctx, physical_db, mole_full, temperature
        )
        references[temperature] = reference_equilibrium(ctx, mole, temperature)
    del physical_db
    gc.collect()

    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "состав, мольные доли id": w11.composition_id(mole),
        "молярные объёмы": {f"{key:g}": value
                            for key, value in volumes.items()},
        "равновесие двух фаз": {f"{key:g}": value
                                for key, value in references.items()},
    }, ensure_ascii=False, indent=2), "utf-8")
    log(f"молярные объёмы и равновесие двух фаз записаны в {path.name}")
    return volumes, references


class CaseCache:
    """Кэш посчитанных точек, дописываемый построчно.

    Ключ случая — состав, температура, межфазная энергия и место зарождения.
    Каждый посчитанный узел сетки времени уходит на диск сразу отдельной
    строкой, поэтому снятый прогон теряет самое большее один незакрытый
    случай, а всё посчитанное до него остаётся. Случай считается готовым,
    когда за его строками идёт строка-закрытие с полным списком узлов:
    незакрытый случай при повторном запуске считается заново, потому что
    состояние модели kawin между запусками не переносится.
    """

    def __init__(self) -> None:
        CACHE.mkdir(parents=True, exist_ok=True)
        self.path = CACHE / "k1_points.jsonl"
        self.rows: dict[str, list[dict[str, Any]]] = {}
        self.done: dict[str, dict[str, Any]] = {}
        if self.path.is_file():
            for line in self.path.read_text("utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                key = record["key"]
                if record.get("kind") == "done":
                    self.done[key] = record["payload"]
                else:
                    self.rows.setdefault(key, []).append(record["payload"])
            log(f"кэш кинетики: закрытых случаев {len(self.done)}, "
                f"строк {sum(len(rows) for rows in self.rows.values())}")

    @staticmethod
    def key(mole: Mapping[str, float], temperature_c: float, gamma: float,
            site: str) -> str:
        return (f"{w11.composition_id(mole)}|{temperature_c:.4f}"
                f"|{gamma:.6f}|{site}")

    def is_done(self, key: str) -> bool:
        return key in self.done

    def rows_of(self, key: str) -> list[dict[str, Any]]:
        return list(self.rows.get(key, []))

    def _append(self, record: Mapping[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False,
                                    sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def put_row(self, key: str, payload: Mapping[str, Any]) -> None:
        self.rows.setdefault(key, [])
        # Незакрытый случай считается заново, поэтому его прежние строки
        # вытесняются новыми: держать в памяти обе версии одного узла незачем.
        self.rows[key] = [
            row for row in self.rows[key]
            if abs(float(row["узел, ч"]) - float(payload["узел, ч"]))
            > 1.0e-12
        ]
        self.rows[key].append(dict(payload))
        self._append({"key": key, "kind": "row", "payload": dict(payload)})

    def close(self, key: str, payload: Mapping[str, Any]) -> None:
        self.done[key] = dict(payload)
        self._append({"key": key, "kind": "done", "payload": dict(payload)})


# --------------------------------------------------------------------------- #
# Один случай карты чувствительности
# --------------------------------------------------------------------------- #


def build_model(ctx: Any, thermodynamics: Any, mole: Mapping[str, float],
                temperature_c: float, gamma: float, site: str,
                volumes: Mapping[str, Any]) -> Any:
    """KWN-модель одного случая. Собирается тем же порядком, что в приложении.

    Порядок и смысл присваиваний повторяют `thermogar_precipitation.
    run_precipitation`: молярные объёмы через `volume.setVolume(..., 'VM', 1)`,
    плотность центров через `nucleationSites.setNucleationDensity`, тип центров
    через `precipitate.nucleation.setNucleationType`. Отличий от приложения
    два, и оба названы здесь.

    Первое: `bulkN0` задаётся явно и равен числу узлов решётки в кубометре
    (N_A / V_m матрицы). Умолчание kawin — число атомов наименее
    представленного растворённого элемента (`setBulkDensityFromComposition`
    берёт `min(x0)`), и в десятикомпонентном составе это сера, 3,7e-4 мольных
    доли, то есть плотность центров определялась бы элементом, не входящим в
    P-фазу. Объём зерна здесь — предельный случай, и предел берётся сверху.

    Второе: энергия границы зерна задана как `K_GB_ENERGY_FACTOR * gamma`.
    Причина в области определения самой модели kawin и объяснена у константы.
    """

    from thermogar_precipitation import HETEROGENEOUS_RATIO_LIMITS
    from kawin.precipitation import (
        MatrixParameters, PrecipitateModel, PrecipitateParameters,
        TemperatureParameters,
    )

    names = elements()
    solutes = names[1:]
    matrix_vm = float(volumes[MATRIX_PHASE]["молярный объём, см³/моль"])
    precip_vm = float(volumes[PRECIPITATE_PHASE]["молярный объём, см³/моль"])
    gb_energy = K_GB_ENERGY_FACTOR * float(gamma)

    limit = HETEROGENEOUS_RATIO_LIMITS.get(site)
    if limit is not None and gb_energy / (2.0 * float(gamma)) >= limit:
        raise ValueError(
            f"gbEnergy / (2 gamma) = {gb_energy / (2.0 * gamma):.3f} не меньше "
            f"предела {limit:.3f} для мест зарождения {site}"
        )

    matrix = MatrixParameters(solutes)
    matrix.initComposition = np.asarray([mole[name] for name in solutes], float)
    matrix.volume.setVolume(matrix_vm * 1.0e-6, "VM", 1)
    matrix.GBenergy = gb_energy
    matrix.nucleationSites.setNucleationDensity(
        grainSize=K_GRAIN_SIZE_UM, aspectRatio=1,
        dislocationDensity=K_DISLOCATION_DENSITY,
        bulkN0=AVOGADRO / (matrix_vm * 1.0e-6),
    )

    precipitate = PrecipitateParameters(PRECIPITATE_PHASE)
    precipitate.gamma = float(gamma)
    precipitate.volume.setVolume(precip_vm * 1.0e-6, "VM", 1)
    precipitate.nucleation.setNucleationType(site)

    model = PrecipitateModel(
        matrix, [precipitate], thermodynamics,
        TemperatureParameters(float(temperature_c) + 273.15),
    )
    model.setPBMParameters(**K_PBM)
    model.setPSDrecording(False)
    if hasattr(model, "cacheCalculations"):
        model.cacheCalculations(True)
    return model


def mole_fraction_of_precipitate(volume_fraction: float, matrix_vm: float,
                                 precip_vm: float) -> float:
    """Мольная доля выделения из объёмной. Сравнивать надо с мольной.

    Волна 12-2 даёт мольные доли фаз, kawin — объёмные. Перевод через молярные
    объёмы обеих фаз: моли фазы есть её объём, делённый на молярный объём.
    """

    value = float(volume_fraction)
    if value <= 0.0:
        return 0.0
    beta = value / precip_vm
    alpha = (1.0 - value) / matrix_vm
    return beta / (beta + alpha) if (beta + alpha) > 0.0 else 0.0


def snapshot(ctx: Any, model: Any, index: int, node_h: float,
             volumes: Mapping[str, Any], seconds: float) -> dict[str, Any]:
    """Состояние модели на записанном шаге `index`.

    `node_h` — узел сетки времени, к которому шаг отнесён, а `t, ч` в строке
    — фактическое время шага. Оба поля остаются в результате: узел нужен,
    чтобы кривые разных случаев ложились на одну ось, фактическое время —
    чтобы видеть, насколько шаг от узла отстоит. На концах интервалов
    решения они совпадают точно, и оба горизонта ТЗ — как раз такие концы.
    """

    names = elements()
    solutes = names[1:]
    data = model.data
    index = int(index)
    phase = model.phaseIndex(PRECIPITATE_PHASE)
    matrix_vm = float(volumes[MATRIX_PHASE]["молярный объём, см³/моль"])
    precip_vm = float(volumes[PRECIPITATE_PHASE]["молярный объём, см³/моль"])

    volume_fraction = float(data.volFrac[index, phase])
    composition = np.asarray(data.composition[index], float)
    mole_matrix = {
        name: float(composition[position])
        for position, name in enumerate(solutes)
    }
    mole_matrix[names[0]] = max(0.0, 1.0 - float(composition.sum()))
    wt_matrix = mass_percent(ctx, mole_matrix)

    equilibrium_alpha = np.asarray(data.xEqAlpha[index, phase], float)
    mole_eq = {
        name: float(equilibrium_alpha[position])
        for position, name in enumerate(solutes)
    }
    mole_eq[names[0]] = max(0.0, 1.0 - float(equilibrium_alpha.sum()))

    return {
        "t, ч": float(data.time[index]) / 3600.0,
        "узел, ч": float(node_h),
        "t, с": float(data.time[index]),
        "шаг модели": index,
        "объёмная доля P-фазы, %": 100.0 * volume_fraction,
        "мольная доля P-фазы, %": 100.0 * mole_fraction_of_precipitate(
            volume_fraction, matrix_vm, precip_vm
        ),
        "средний радиус, нм": 1.0e9 * float(data.Ravg[index, phase]),
        "число выделений, 1/м³": float(data.precipitateDensity[index, phase]),
        "критический радиус, нм": 1.0e9 * float(data.Rcrit[index, phase]),
        "скорость зарождения, 1/(м³·с)": float(data.nucRate[index, phase]),
        "движущая сила, Дж/м³": float(data.drivingForce[index, phase]),
        "матрица, мольные доли": mole_matrix,
        "матрица, масс. %": wt_matrix,
        "равновесная матрица, мольные доли": mole_eq,
        "равновесная матрица, масс. %": mass_percent(ctx, mole_eq),
        "секунд счёта на узел": float(seconds),
    }


def run_case(ctx: Any, thermodynamics: Any, mole: Mapping[str, float],
             temperature_c: float, gamma: float, label: str, site: str,
             volumes: Mapping[str, Any], nodes: Sequence[float],
             edges: Sequence[float], cache: CaseCache,
             key: str) -> list[dict[str, Any]]:
    """Один случай (T, межфазная энергия, места зарождения) целиком.

    Модель решается непрерывно от нуля до 87 600 ч. Прерывается решение только
    на концах интервалов `edges` — по одному на декаду плюс оба горизонта ТЗ —
    и по двум причинам: 200 ч и 87 600 ч должны быть точными концами, а
    посчитанное должно уходить на диск по ходу, а не одним куском в конце.
    Между прерываниями `model.solve` продолжает с того состояния, на котором
    остановился (`GenericModel.solve` считает от `currentTime`, `setup` защищён
    от повторного вызова), поэтому 200 ч и 87 600 ч лежат на одной кривой.

    Узлы сетки времени внутри интервала выбираются из шагов, которые решатель
    уже записал: для каждого узла берётся ближайший по времени шаг. Ничего не
    интерполируется — в строке стоит состояние настоящего шага и его настоящее
    время рядом с номером узла.
    """

    model = build_model(ctx, thermodynamics, mole, temperature_c, gamma, site,
                        volumes)
    rows: list[dict[str, Any]] = []
    previous = 0.0
    taken: set[int] = set()
    for edge in edges:
        started = time.perf_counter()
        model.solve((float(edge) - previous) * 3600.0, verbose=False)
        seconds = time.perf_counter() - started
        last = int(model.data.n)
        recorded = np.asarray(model.data.time[:last + 1], float) / 3600.0

        # Конец интервала идёт первым, и это важно: горизонты ТЗ обязаны быть
        # точными узлами. Если бы он шёл последним, а ближайшим шагом к
        # предыдущему узлу сетки оказался тот же последний шаг, точный узел
        # горизонта вытеснился бы соседним узлом и 200 ч в таблице горизонтов
        # не нашлось бы вовсе. Потерять при таком совпадении внутренний узел
        # сетки безобидно, потерять горизонт — нет.
        chosen: list[tuple[int, float]] = [(last, float(edge))]
        for value in nodes:
            if not (previous < float(value) <= float(edge) + 1.0e-9):
                continue
            chosen.append((int(np.argmin(np.abs(recorded - float(value)))),
                           float(value)))
        for index, value in chosen:
            if index in taken:
                continue
            taken.add(index)
            row = snapshot(ctx, model, index, value, volumes, seconds)
            rows.append(row)
            cache.put_row(key, row)
        previous = float(edge)

    rows.sort(key=lambda item: item["t, ч"])
    log(f"{temperature_c:.0f} °C, gamma={gamma:.3f} Дж/м², {label}: "
        f"P-фаза {rows[-1]['мольная доля P-фазы, %']:.4f} мольн. % за "
        f"{rows[-1]['t, ч']:.0f} ч, R {rows[-1]['средний радиус, нм']:.2f} нм, "
        f"N {rows[-1]['число выделений, 1/м³']:.2e} 1/м³, "
        f"шагов {int(model.data.n)}")
    del model
    gc.collect()
    return rows


# --------------------------------------------------------------------------- #
# 12-1. Карта чувствительности целиком
# --------------------------------------------------------------------------- #


def k1_kinetics(force: bool = False, gammas: Sequence[float] = K_GAMMA,
                per_decade: int = K_PER_DECADE,
                t_min_h: float = K_T_MIN_H,
                min_free_gib: float = MIN_FREE_GIB) -> dict[str, Any]:
    """Карта чувствительности. Считается в потомке."""

    from thermogar_precipitation import _build_precipitation_thermodynamics

    cache = CaseCache()
    if force:
        cache.rows.clear()
        cache.done.clear()
        if cache.path.is_file():
            cache.path.unlink()

    free = w12.free_gib()
    if free < float(min_free_gib):
        return {
            "случаи": [], "точки": [],
            "пропущено": [{
                "случай": None,
                "причина": (
                    f"свободной физической памяти {free:.1f} ГиБ при требуемых "
                    f"{float(min_free_gib):.1f} ГиБ; база не разбиралась, прогон "
                    f"не начинался"
                ),
            }],
            "состав, масс. %": working_wt(),
        }

    ctx = w11.Context()
    mole = w11.wt_to_mole(ctx, working_wt())
    mole_full = w11.wt_to_mole(ctx, w11.full_wt())

    volumes, references = volumes_and_references(ctx, mole, mole_full)
    for temperature in K_TEMPERATURES_C:
        log(f"{temperature:.0f} °C: V_m {MATRIX_PHASE} "
            f"{volumes[temperature][MATRIX_PHASE]['молярный объём, см³/моль']:.4f}, "
            f"{PRECIPITATE_PHASE} "
            f"{volumes[temperature][PRECIPITATE_PHASE]['молярный объём, см³/моль']:.4f} "
            f"см³/моль; равновесие двух фаз: P-фаза "
            f"{references[temperature]['мольная доля P-фазы, %']:.4f} мольн. %")
    ctx._models = None
    ctx._phase_records = None
    gc.collect()
    log(f"свободно {w12.free_gib():.2f} ГиБ перед счётом кинетики")

    thermodynamics, thermodynamics_class = _build_precipitation_thermodynamics(
        ctx.db, elements(), [MATRIX_PHASE, PRECIPITATE_PHASE]
    )
    log(f"термодинамика kawin: {thermodynamics_class}, "
        f"компонентов {len(elements())}, фазы "
        f"{MATRIX_PHASE} + {PRECIPITATE_PHASE}")

    nodes = time_nodes(t_min_h, per_decade)
    edges = stage_edges(t_min_h)
    log(f"узлов сетки времени {len(nodes)}, "
        f"прерываний решения {len(edges)}")
    cases: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for temperature in K_TEMPERATURES_C:
        for label, site in K_SITES:
            for gamma in gammas:
                key = CaseCache.key(mole, temperature, gamma, site)
                descriptor = {
                    "T, °C": float(temperature),
                    "межфазная энергия, Дж/м²": float(gamma),
                    "места зарождения": label,
                    "места зарождения, kawin": site,
                }
                if cache.is_done(key) and not force:
                    cases.append({**descriptor,
                                  "строк": len(cache.rows_of(key)),
                                  "из кэша": True})
                    continue

                free = w12.free_gib()
                if free < ABORT_FREE_GIB:
                    skipped.append({
                        "случай": descriptor,
                        "причина": (
                            f"свободной физической памяти {free:.1f} ГиБ, ниже "
                            f"порога остановки {ABORT_FREE_GIB:.1f} ГиБ; "
                            f"остаток карты не считался"
                        ),
                    })
                    log(f"{temperature:.0f} °C, γ={gamma:.3f}, {label} и далее "
                        f"не считались: свободно {free:.1f} ГиБ")
                    return {
                        "случаи": cases, "пропущено": skipped,
                        "узлы, ч": nodes,
                        "состав, масс. %": working_wt(),
                        "состав, мольные доли": dict(mole),
                        "молярные объёмы": {
                            f"{key_t:.0f}": value
                            for key_t, value in volumes.items()
                        },
                        "равновесие двух фаз": {
                            f"{key_t:.0f}": value
                            for key_t, value in references.items()
                        },
                        "класс термодинамики kawin": thermodynamics_class,
                        "фаз в базе": len(ctx.phases),
                        "ремонт базы доступен": bool(ctx.repair_available),
                    }

                started = time.perf_counter()
                try:
                    rows = run_case(
                        ctx, thermodynamics, mole, temperature, gamma, label,
                        site, volumes[temperature], nodes, edges, cache, key
                    )
                except Exception as error:  # noqa: BLE001
                    skipped.append({
                        "случай": descriptor,
                        "причина": f"{type(error).__name__}: {error}",
                    })
                    log(f"{temperature:.0f} °C, γ={gamma:.3f}, {label}: "
                        f"{type(error).__name__}: {error}")
                    continue
                cache.close(key, {**descriptor, "узлов": len(rows),
                                  "секунд": time.perf_counter() - started})
                cases.append({**descriptor, "строк": len(rows),
                              "из кэша": False,
                              "секунд": time.perf_counter() - started})

    return {
        "случаи": cases,
        "пропущено": skipped,
        "узлы, ч": nodes,
        "состав, масс. %": working_wt(),
        "состав, мольные доли": dict(mole),
        "молярные объёмы": {f"{key_t:.0f}": value
                            for key_t, value in volumes.items()},
        "равновесие двух фаз": {f"{key_t:.0f}": value
                                for key_t, value in references.items()},
        "класс термодинамики kawin": thermodynamics_class,
        "фаз в базе": len(ctx.phases),
        "ремонт базы доступен": bool(ctx.repair_available),
    }


def collect_rows(payload: Mapping[str, Any]) -> pd.DataFrame:
    """Все посчитанные строки из кэша в одну таблицу.

    Кэш читается заново, а не передаётся из потомка: строки уже лежат на
    диске, и второй путь передачи тех же чисел — лишний повод для расхождения.
    """

    cache = CaseCache()
    rows: list[dict[str, Any]] = []
    for case in payload["случаи"]:
        mole = payload["состав, мольные доли"]
        key = CaseCache.key(mole, case["T, °C"],
                            case["межфазная энергия, Дж/м²"],
                            case["места зарождения, kawin"])
        for row in sorted(cache.rows_of(key), key=lambda item: item["t, ч"]):
            record = {
                "T, °C": case["T, °C"],
                "межфазная энергия, Дж/м²": case["межфазная энергия, Дж/м²"],
                "места зарождения": case["места зарождения"],
                "t, ч": row["t, ч"],
                "узел, ч": row["узел, ч"],
                "мольная доля P-фазы, %": row["мольная доля P-фазы, %"],
                "объёмная доля P-фазы, %": row["объёмная доля P-фазы, %"],
                "средний радиус, нм": row["средний радиус, нм"],
                "число выделений, 1/м³": row["число выделений, 1/м³"],
                "критический радиус, нм": row["критический радиус, нм"],
                "скорость зарождения, 1/(м³·с)":
                    row["скорость зарождения, 1/(м³·с)"],
                "движущая сила, Дж/м³": row["движущая сила, Дж/м³"],
            }
            for element in MATRIX_ELEMENTS:
                record[f"{element} в матрице, масс. %"] = (
                    row["матрица, масс. %"].get(element)
                )
                record[f"{element} в матрице, ат. %"] = 100.0 * float(
                    row["матрица, мольные доли"].get(element, 0.0)
                )
                record[f"{element} в матрице равновесно, масс. %"] = (
                    row["равновесная матрица, масс. %"].get(element)
                )
            rows.append(record)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Таблицы
# --------------------------------------------------------------------------- #


def fraction_table(rows: pd.DataFrame) -> pd.DataFrame:
    """Пункт 1: доля P-фазы от времени по всем случаям."""

    columns = ["T, °C", "межфазная энергия, Дж/м²", "места зарождения", "t, ч",
               "мольная доля P-фазы, %", "объёмная доля P-фазы, %",
               "движущая сила, Дж/м³"]
    return rows[columns].copy() if len(rows) else pd.DataFrame(columns=columns)


def size_table(rows: pd.DataFrame) -> pd.DataFrame:
    """Пункт 2: средний размер и число выделений от времени."""

    columns = ["T, °C", "межфазная энергия, Дж/м²", "места зарождения", "t, ч",
               "средний радиус, нм", "число выделений, 1/м³",
               "критический радиус, нм", "скорость зарождения, 1/(м³·с)"]
    return rows[columns].copy() if len(rows) else pd.DataFrame(columns=columns)


def depletion_table(rows: pd.DataFrame,
                    targets: Mapping[str, Any]) -> pd.DataFrame:
    """Пункт 3: обеднение матрицы по Cr и Mo и сравнение с равновесием 12-2.

    Сравнение идёт с двумя равновесиями сразу: с матрицей волны 12-2
    (48 фаз, одиннадцать компонентов) и с равновесной матрицей той же
    двухфазной задачи, которую решает сама KWN-модель. Первое отвечает на
    вопрос задания «к чему приходит», второе показывает, сколько из
    расхождения приносит сокращение задачи, а сколько — незавершённость
    кинетики.
    """

    if not len(rows):
        return pd.DataFrame()
    table = rows[["T, °C", "межфазная энергия, Дж/м²", "места зарождения",
                  "t, ч"]].copy()
    equilibrium_12_2 = targets.get("матрица FCC_A1, масс. %", {})
    for element in MATRIX_ELEMENTS:
        nominal = float(working_wt()[element])
        table[f"{element} в сплаве, масс. %"] = nominal
        table[f"{element} в матрице, масс. %"] = rows[
            f"{element} в матрице, масс. %"
        ]
        table[f"{element}, сдвиг от сплава, масс. %"] = (
            rows[f"{element} в матрице, масс. %"] - nominal
        )
        table[f"{element} равновесно в двухфазной задаче, масс. %"] = rows[
            f"{element} в матрице равновесно, масс. %"
        ]
        table[f"{element} равновесно по 12-2, масс. %"] = [
            equilibrium_12_2.get(f"{value:.0f}", {}).get(element)
            for value in rows["T, °C"]
        ]
    return table


def horizon_table(rows: pd.DataFrame, targets: Mapping[str, Any],
                  two_phase: Mapping[str, Any] | None = None) -> pd.DataFrame:
    """Пункт 4: что успевает произойти за 200 ч — и что за 87 600 ч рядом.

    Обе строки одного случая стоят рядом намеренно: вопрос задания — не
    «сколько за 200 ч», а «отличит ли испытание по ТЗ стойкий сплав от
    нестойкого», и ответ на него читается только из сравнения двух горизонтов.
    """

    if not len(rows):
        return pd.DataFrame()
    equilibrium_12_2 = targets.get("доля P-фазы, мольн. %", {})
    records: list[dict[str, Any]] = []
    keys = ["T, °C", "межфазная энергия, Дж/м²", "места зарождения"]
    for values, block in rows.groupby(keys, sort=True):
        case = dict(zip(keys, values))
        target = equilibrium_12_2.get(f"{case['T, °C']:.0f}")
        limit = None
        if two_phase:
            limit = (two_phase.get(f"{case['T, °C']:.0f}") or {}).get(
                "мольная доля P-фазы, %"
            )
        record: dict[str, Any] = dict(case)
        record["равновесие 12-2, мольн. %"] = target
        record["равновесие двухфазной задачи, мольн. %"] = limit
        for horizon in K_HORIZONS_H:
            # Горизонт — точный конец интервала решения, поэтому строка с ним
            # существует и сравнение точное. Если её нет, столбцов горизонта в
            # таблице не будет, и это видно, а не заметено под ближайший узел.
            at = block[np.isclose(block["t, ч"], horizon, rtol=1.0e-9,
                                  atol=1.0e-9)]
            if not len(at):
                continue
            row = at.iloc[0]
            prefix = f"{horizon:.0f} ч"
            record[f"{prefix}: P-фаза, мольн. %"] = float(
                row["мольная доля P-фазы, %"]
            )
            record[f"{prefix}: доля равновесия 12-2, %"] = (
                None if not target else
                100.0 * float(row["мольная доля P-фазы, %"]) / float(target)
            )
            record[f"{prefix}: радиус, нм"] = float(row["средний радиус, нм"])
            record[f"{prefix}: число выделений, 1/м³"] = float(
                row["число выделений, 1/м³"]
            )
            for element in MATRIX_ELEMENTS:
                record[f"{prefix}: {element} в матрице, масс. %"] = float(
                    row[f"{element} в матрице, масс. %"]
                )
        # Отсутствие строки 200 ч и отсутствие выделений на 200 ч — разные
        # вещи, и путать их нельзя: первое значит «не посчитано», второе —
        # «испытание по ТЗ не увидит ничего».
        key = f"{K_HORIZONS_H[0]:.0f} ч: P-фаза, мольн. %"
        if key not in record:
            record["видно за 200 ч"] = "не посчитано"
        else:
            record["видно за 200 ч"] = (
                "да" if float(record[key]) > 100.0 * PRESENT_FLOOR else "нет"
            )
        records.append(record)
    return pd.DataFrame(records)


def sensitivity_map(rows: pd.DataFrame, targets: Mapping[str, Any],
                    two_phase: Mapping[str, Any] | None = None
                    ) -> pd.DataFrame:
    """Карта чувствительности: один случай — одна строка, без кривых.

    Именно та форма вывода, которую требует задание: не «выделится через N
    часов», а «при межфазной энергии ниже X доля достигает Y за 87 600 ч».
    """

    if not len(rows):
        return pd.DataFrame()
    equilibrium_12_2 = targets.get("доля P-фазы, мольн. %", {})
    records: list[dict[str, Any]] = []
    keys = ["T, °C", "межфазная энергия, Дж/м²", "места зарождения"]
    for values, block in rows.groupby(keys, sort=True):
        case = dict(zip(keys, values))
        block = block.sort_values("t, ч")
        target = equilibrium_12_2.get(f"{case['T, °C']:.0f}")
        limit = None
        if two_phase:
            limit = (two_phase.get(f"{case['T, °C']:.0f}") or {}).get(
                "мольная доля P-фазы, %"
            )
        # Предел, которого эта модель может достичь, — равновесие её
        # собственной двухфазной задачи, а не число 12-2: разница между ними
        # известна арифметически и к кинетике не относится. Поэтому «дошло»
        # считается от двухфазного предела, а доля от цели 12-2 остаётся
        # отдельным столбцом.
        against = float(limit) if limit else (float(target) if target else 0.0)
        final = block.iloc[-1]
        present = block[block["мольная доля P-фазы, %"]
                        > 100.0 * PRESENT_FLOOR]
        reached = (
            block[block["мольная доля P-фазы, %"] >= REACHED_FRACTION * against]
            if against > 0.0 else block.iloc[0:0]
        )
        records.append({
            **case,
            "узлов": int(len(block)),
            "до, ч": float(block["t, ч"].max()),
            "равновесие 12-2, мольн. %": target,
            "равновесие двухфазной задачи, мольн. %": limit,
            "P-фаза в конце, мольн. %": float(final["мольная доля P-фазы, %"]),
            "доля равновесия 12-2 в конце, %": (
                None if not target else
                100.0 * float(final["мольная доля P-фазы, %"]) / float(target)
            ),
            "доля двухфазного равновесия в конце, %": (
                None if not limit else
                100.0 * float(final["мольная доля P-фазы, %"]) / float(limit)
            ),
            "радиус в конце, нм": float(final["средний радиус, нм"]),
            "число выделений в конце, 1/м³": float(final["число выделений, 1/м³"]),
            "выделения появились": "да" if len(present) else "нет",
            "первый узел с выделениями, ч": (
                float(present["t, ч"].iloc[0]) if len(present) else None
            ),
            f"дошло до {100 * REACHED_FRACTION:.0f} % равновесия": (
                "да" if len(reached) else "нет"
            ),
            f"первый узел на {100 * REACHED_FRACTION:.0f} % равновесия, ч": (
                float(reached["t, ч"].iloc[0]) if len(reached) else None
            ),
            "критический радиус в конце, нм": float(
                final["критический радиус, нм"]
            ),
            "движущая сила в конце, Дж/м³": float(final["движущая сила, Дж/м³"]),
        })
    return pd.DataFrame(records)


def threshold_verdict(mapping: pd.DataFrame) -> list[dict[str, Any]]:
    """Порог по межфазной энергии в той форме, которую требует задание."""

    if not len(mapping):
        return []
    verdict: list[dict[str, Any]] = []
    for (temperature, label), block in mapping.groupby(
        ["T, °C", "места зарождения"], sort=True
    ):
        block = block.sort_values("межфазная энергия, Дж/м²")
        reached = block[block[
            f"дошло до {100 * REACHED_FRACTION:.0f} % равновесия"
        ] == "да"]
        appeared = block[block["выделения появились"] == "да"]
        verdict.append({
            "T, °C": float(temperature),
            "места зарождения": label,
            "γ прогнано, Дж/м²": [
                float(value) for value in block["межфазная энергия, Дж/м²"]
            ],
            "наибольшая γ, при которой выделения появляются, Дж/м²": (
                float(appeared["межфазная энергия, Дж/м²"].max())
                if len(appeared) else None
            ),
            "наименьшая γ, при которой не появляются, Дж/м²": (
                float(block[block["выделения появились"] == "нет"]
                      ["межфазная энергия, Дж/м²"].min())
                if len(block[block["выделения появились"] == "нет"]) else None
            ),
            f"наибольшая γ, при которой доля доходит до "
            f"{100 * REACHED_FRACTION:.0f} % равновесия, Дж/м²": (
                float(reached["межфазная энергия, Дж/м²"].max())
                if len(reached) else None
            ),
            "доля P-фазы за 87 600 ч по γ, мольн. %": {
                f"{float(row['межфазная энергия, Дж/м²']):.3f}":
                    float(row["P-фаза в конце, мольн. %"])
                for _, row in block.iterrows()
            },
        })
    return verdict


# --------------------------------------------------------------------------- #
# Графики
# --------------------------------------------------------------------------- #


def plot_k1(rows: pd.DataFrame, targets: Mapping[str, Any], path: Path) -> None:
    """Доля P-фазы от времени: по столбцу на температуру, по строке на места."""

    if not len(rows):
        return
    equilibrium_12_2 = targets.get("доля P-фазы, мольн. %", {})
    figure, axes = plt.subplots(
        len(K_SITES), len(K_TEMPERATURES_C),
        figsize=(6.2 * len(K_TEMPERATURES_C), 4.4 * len(K_SITES)),
        squeeze=False,
    )
    gammas = sorted(rows["межфазная энергия, Дж/м²"].unique())
    colours = plt.cm.viridis(np.linspace(0.0, 0.9, max(1, len(gammas))))
    for row_index, (label, _site) in enumerate(K_SITES):
        for column, temperature in enumerate(K_TEMPERATURES_C):
            axis = axes[row_index][column]
            block = rows[(rows["T, °C"] == temperature)
                         & (rows["места зарождения"] == label)]
            for colour, gamma in zip(colours, gammas):
                series = block[
                    block["межфазная энергия, Дж/м²"] == gamma
                ].sort_values("t, ч")
                if not len(series):
                    continue
                axis.plot(series["t, ч"], series["мольная доля P-фазы, %"],
                          linewidth=1.6, color=colour,
                          label=f"γ = {gamma:.3f}".replace(".", ","))
            target = equilibrium_12_2.get(f"{temperature:.0f}")
            if target:
                axis.axhline(float(target), color="tab:red", linewidth=1.0,
                             linestyle="--",
                             label=f"равновесие 12-2 = "
                                   f"{target:.2f}".replace(".", ","))
            for horizon in K_HORIZONS_H:
                axis.axvline(horizon, color="0.6", linewidth=0.8,
                             linestyle=":")
            axis.set_xscale("log")
            axis.set_xlabel("время, ч")
            axis.set_ylabel("мольная доля P-фазы, %")
            axis.set_title(f"{temperature:.0f} °C, {label}")
            axis.grid(alpha=0.3)
            axis.legend(fontsize=7)
    figure.suptitle(
        "12-1. Доля P-фазы от времени; пунктир — 200 ч и 87 600 ч по ТЗ. "
        "Межфазная энергия не измерена, а прогнана диапазоном"
    )
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


def plot_k1_size(rows: pd.DataFrame, path: Path) -> None:
    """Средний радиус и число выделений от времени."""

    if not len(rows):
        return
    figure, axes = plt.subplots(
        2, len(K_TEMPERATURES_C),
        figsize=(6.2 * len(K_TEMPERATURES_C), 8.4), squeeze=False,
    )
    gammas = sorted(rows["межфазная энергия, Дж/м²"].unique())
    colours = plt.cm.viridis(np.linspace(0.0, 0.9, max(1, len(gammas))))
    styles = {label: style for (label, _), style
              in zip(K_SITES, ("-", "--"))}
    for column, temperature in enumerate(K_TEMPERATURES_C):
        for position, (column_name, ylabel, logscale) in enumerate((
            ("средний радиус, нм", "средний радиус, нм", True),
            ("число выделений, 1/м³", "число выделений, 1/м³", True),
        )):
            axis = axes[position][column]
            for colour, gamma in zip(colours, gammas):
                for label, _site in K_SITES:
                    series = rows[
                        (rows["T, °C"] == temperature)
                        & (rows["места зарождения"] == label)
                        & (rows["межфазная энергия, Дж/м²"] == gamma)
                    ].sort_values("t, ч")
                    series = series[series[column_name] > 0.0]
                    if not len(series):
                        continue
                    axis.plot(series["t, ч"], series[column_name],
                              linewidth=1.4, color=colour,
                              linestyle=styles[label],
                              label=f"γ = {gamma:.3f}, {label}".replace(".", ","))
            axis.set_xscale("log")
            if logscale:
                axis.set_yscale("log")
            axis.set_xlabel("время, ч")
            axis.set_ylabel(ylabel)
            axis.set_title(f"{temperature:.0f} °C")
            axis.grid(alpha=0.3)
            axis.legend(fontsize=6, ncol=2)
    figure.suptitle("12-1. Размер и число выделений P-фазы; сплошная — объём "
                    "зерна, штриховая — границы зёрен")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


def plot_k1_depletion(rows: pd.DataFrame, targets: Mapping[str, Any],
                      path: Path) -> None:
    """Обеднение матрицы по Cr и Mo против равновесного обеднения 12-2."""

    if not len(rows):
        return
    equilibrium_12_2 = targets.get("матрица FCC_A1, масс. %", {})
    nominal = working_wt()
    figure, axes = plt.subplots(
        len(MATRIX_ELEMENTS), len(K_TEMPERATURES_C),
        figsize=(6.2 * len(K_TEMPERATURES_C), 4.2 * len(MATRIX_ELEMENTS)),
        squeeze=False,
    )
    gammas = sorted(rows["межфазная энергия, Дж/м²"].unique())
    colours = plt.cm.viridis(np.linspace(0.0, 0.9, max(1, len(gammas))))
    styles = {label: style for (label, _), style
              in zip(K_SITES, ("-", "--"))}
    for position, element in enumerate(MATRIX_ELEMENTS):
        for column, temperature in enumerate(K_TEMPERATURES_C):
            axis = axes[position][column]
            for colour, gamma in zip(colours, gammas):
                for label, _site in K_SITES:
                    series = rows[
                        (rows["T, °C"] == temperature)
                        & (rows["места зарождения"] == label)
                        & (rows["межфазная энергия, Дж/м²"] == gamma)
                    ].sort_values("t, ч")
                    if not len(series):
                        continue
                    axis.plot(series["t, ч"],
                              series[f"{element} в матрице, масс. %"],
                              linewidth=1.4, color=colour,
                              linestyle=styles[label],
                              label=f"γ = {gamma:.3f}, {label}".replace(".", ","))
            axis.axhline(float(nominal[element]), color="0.3", linewidth=1.0,
                         linestyle="-.", label=f"{element} в сплаве")
            target = equilibrium_12_2.get(f"{temperature:.0f}", {}).get(element)
            if target is not None:
                axis.axhline(float(target), color="tab:red", linewidth=1.0,
                             linestyle="--",
                             label=f"{element} равновесно по 12-2")
            for horizon in K_HORIZONS_H:
                axis.axvline(horizon, color="0.6", linewidth=0.8,
                             linestyle=":")
            axis.set_xscale("log")
            axis.set_xlabel("время, ч")
            axis.set_ylabel(f"{element} в матрице, масс. %")
            axis.set_title(f"{temperature:.0f} °C")
            axis.grid(alpha=0.3)
            axis.legend(fontsize=6, ncol=2)
    figure.suptitle("12-1. Обеднение матрицы FCC_A1 по хрому и молибдену; "
                    "красная штриховая — равновесие подпункта 12-2")
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    log(f"записано {path.relative_to(ROOT)}")


# --------------------------------------------------------------------------- #
# Служебное: потомок и замер памяти
# --------------------------------------------------------------------------- #


def memory_report(stem: str, record: Mapping[str, Any], seconds: float,
                  final: bool = True) -> Path | None:
    """Итог замера памяти. Устроен как у 12-2, но с префиксом подпункта 12-1."""

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
    path = OUT / f"k1_memory_{stem}.json"
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
                record.get("начало, perf_counter", time.perf_counter())
            ), final=False)
            flushed = now


def run_child(arguments: Sequence[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Тяжёлый кусок — в отдельном процессе, результат приходит файлом.

    Своя копия механизма волны 12-2 нужна по одной причине: `w12.run_child`
    запускает `Path(__file__)` своего модуля, то есть саму волну 12-2. Всё, что
    можно было взять оттуда без правок, взято: опрос памяти зовёт
    `w11.memory_probe`, шаги опроса и сброса — тоже волны 11. То же решение и
    та же причина, что в подпункте 12-4.
    """

    stem = "_".join(argument.strip("-").replace(".", "_").replace(",", "_")
                    for argument in arguments)
    handoff = CACHE / f"child_k1_{stem}.json"
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
# Подпункт 12-1 целиком
# --------------------------------------------------------------------------- #


def stored_child_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    """Итог потомка и замер памяти с диска, без повторного счёта.

    Нужно режиму `--tables-only`: таблицы, графики и сводка пересобираются из
    того, что уже посчитано, когда меняется только их код. Пересчитывать
    четыре часа ради нового столбца незачем, а считать этот режим полноценным
    прогоном нельзя — он не трогает журнал прогресса и помечает сводку.
    """

    handoffs = sorted(CACHE.glob("child_k1_*.json"),
                      key=lambda item: item.stat().st_mtime)
    if not handoffs:
        raise RuntimeError(
            f"нет итога потомка в {CACHE}: режиму --tables-only пересобирать "
            f"нечего, сначала нужен прогон"
        )
    payload = json.loads(handoffs[-1].read_text("utf-8"))
    measurement: dict[str, Any] = {
        "источник": f"{handoffs[-1].name} и k1_memory_*.json с диска; "
                    f"пересборка таблиц, не новый прогон"
    }
    memories = sorted(OUT.glob("k1_memory_*.json"),
                      key=lambda item: item.stat().st_mtime)
    if memories:
        measurement.update(json.loads(memories[-1].read_text("utf-8")))
    return payload, measurement


def step_k1(force: bool = False, gammas: Sequence[float] = K_GAMMA,
            per_decade: int = K_PER_DECADE,
            t_min_h: float = K_T_MIN_H,
            min_free_gib: float = MIN_FREE_GIB,
            tables_only: bool = False) -> None:
    progress = w12.load_progress()
    if progress.get("12-1", {}).get("готов") and not force and not tables_only:
        log("12-1 пропущен, посчитан ранее (--force для пересчёта, "
            "--tables-only для пересборки таблиц)")
        return

    missing = [value for value in K_TEMPERATURES_C
               if value not in w12.E1_REQUIRED_C]
    if missing:
        raise RuntimeError(
            f"температуры {missing} не входят в точки ТЗ волны 12-2: "
            "равновесной цели для них нет"
        )

    free = w12.free_gib()
    cache_ready = (CACHE / "k1_points.jsonl").is_file() and not force
    if free < float(min_free_gib) and not cache_ready and not tables_only:
        w12.write_json({
            "подпункт": "12-1. Кинетика выделения P-фазы в ЭК199-ВИ",
            "прогон": "не начинался",
            "причина": (
                f"свободной физической памяти {free:.2f} ГиБ при требуемых "
                f"{float(min_free_gib):.1f} ГиБ"
            ),
            "порог задания, ГиБ": MIN_FREE_GIB,
        }, "k1_summary.json")
        log(f"12-1 не запускался: свободно {free:.2f} ГиБ при требуемых "
            f"{float(min_free_gib):.1f} ГиБ")
        return

    if tables_only:
        payload, measurement = stored_child_payload()
        log(f"--tables-only: пересборка по {len(payload.get('случаи', []))} "
            f"случаям с диска, счёт не запускался")
    else:
        arguments = ["--k1", "1",
                     "--gammas", ",".join(f"{value:g}" for value in gammas),
                     "--per-decade", str(int(per_decade)),
                     "--t-min-h", f"{t_min_h:g}",
                     "--min-free-gib", f"{float(min_free_gib):g}"]
        if force:
            arguments.append("--force")
        payload, measurement = run_child(arguments)
        measurement["свободной физической перед запуском, ГиБ"] = round(free, 2)

    targets = wave12_2_targets()
    rows = collect_rows(payload)
    w12.write_csv(fraction_table(rows), "k1_phase_fraction_vs_time.csv")
    w12.write_csv(size_table(rows), "k1_size_and_density.csv")
    w12.write_csv(depletion_table(rows, targets), "k1_matrix_depletion.csv")
    two_phase = payload.get("равновесие двух фаз", {})
    horizons = horizon_table(rows, targets, two_phase)
    w12.write_csv(horizons, "k1_horizons_200h.csv")
    mapping = sensitivity_map(rows, targets, two_phase)
    w12.write_csv(mapping, "k1_sensitivity_map.csv")
    plot_k1(rows, targets, OUT / "k1_phase_fraction.png")
    plot_k1_size(rows, OUT / "k1_size_and_density.png")
    plot_k1_depletion(rows, targets, OUT / "k1_matrix_depletion.png")

    summary = {
        "подпункт": "12-1. Кинетика выделения P-фазы в ЭК199-ВИ (ХН62М(Sc)-ВИ) "
                    "при 700 и 750 °C",
        "база": DB_REL,
        "sha256 базы": w12.database_sha256(),
        "база плотностей": PDB_REL,
        "ремонт базы доступен": payload.get("ремонт базы доступен"),
        "фаз в базе": payload.get("фаз в расчёте", payload.get("фаз в базе")),
        "модель": "KWN пакета kawin через thermogar_precipitation, "
                  "одна однородная матрица и одно выделение",
        "класс термодинамики kawin": payload.get("класс термодинамики kawin"),
        "матрица": MATRIX_PHASE,
        "выделение": PRECIPITATE_PHASE,
        "компоненты расчёта": elements(),
        "исключено из состава": {
            "элементы": list(DROPPED_ELEMENTS),
            "причина": DROPPED_REASON,
            "содержание в контрольном составе, масс. %": {
                name: float(w11.CONTROL_WT.get(name, 0.0))
                for name in DROPPED_ELEMENTS
            },
        },
        "состав, масс. %": payload["состав, масс. %"],
        "состав, мольные доли": payload.get("состав, мольные доли", {}),
        "скандий": (
            "в mc_ni 2.036 скандия нет; счёт идёт по составу без него, то есть "
            "по основе сплава ЭК199-ВИ, а не по сплаву со скандием"
        ),
        "температуры, °C": list(K_TEMPERATURES_C),
        "межфазная энергия, Дж/м²": [float(value) for value in gammas],
        "межфазная энергия — статус": (
            "не измерена и не подобрана: в базе её нет, эксперимента для "
            "подгонки нет. Прогнана диапазоном, и абсолютная шкала времени "
            "верна ровно настолько, насколько верна она"
        ),
        "оценка межфазной энергии средствами kawin": gamma_estimate_available(),
        "места зарождения": [
            {"название": label, "kawin": site} for label, site in K_SITES
        ],
        "энергия границы зерна": {
            "значение": f"{K_GB_ENERGY_FACTOR:g} * γ",
            "отношение gbEnergy / (2 γ)": K_GB_ENERGY_FACTOR / 2.0,
            "почему не измеренная": (
                "геометрия гетерогенного зарождения в kawin определена только "
                "при gbEnergy < 2 γ (HETEROGENEOUS_RATIO_LIMITS), а измеренная "
                "энергия границы зерна в никеле больше 2 γ на всём диапазоне "
                "0,05…0,50 Дж/м². Объявленная геометрия смачивания, не измерение"
            ),
        },
        "размер зерна, мкм": {
            "значение": K_GRAIN_SIZE_UM,
            "статус": "объявленный вход сценария, не измерение; сертификата на "
                      "зерно ЭК199-ВИ в проекте нет, позиция в SOURCES_WANTED",
        },
        "плотность центров в объёме": {
            "значение, 1/м³": "N_A / V_m матрицы",
            "почему не умолчание kawin": (
                "умолчание берёт число атомов наименее представленного "
                "растворённого элемента (min(x0)), а это сера 3,7e-4 мольных "
                "доли, не входящая в P-фазу"
            ),
        },
        "сетка размеров PBM": {key: value for key, value in K_PBM.items()},
        "горизонты ТЗ, ч": list(K_HORIZONS_H),
        "сетка времени": {
            "от, ч": t_min_h, "до, ч": max(K_HORIZONS_H),
            "узлов на декаду": int(per_decade),
            "узлов всего": len(payload.get("узлы, ч", [])),
            "прерываний решения": len(stage_edges(t_min_h)),
            "как считано": (
                "одним непрерывным прогоном модели от 0 до 87 600 ч; решение "
                "прерывается только на концах интервалов (по одному на "
                "декаду плюс оба горизонта ТЗ), узлы сетки внутри интервала "
                "берутся из уже записанных шагов решателя без интерполяции. "
                "Поэтому 200 ч и 87 600 ч — точные концы интервалов и лежат "
                "на одной кривой"
            ),
        },
        "молярные объёмы": payload.get("молярные объёмы", {}),
        "равновесие двух фаз того же состава": payload.get(
            "равновесие двух фаз", {}
        ),
        "равновесная цель подпункта 12-2": targets,
        "случаев посчитано": len(payload.get("случаи", [])),
        "случаев в сетке": len(K_TEMPERATURES_C) * len(K_SITES) * len(gammas),
        "пропущено": payload.get("пропущено", []),
        "порог запуска, свободной физической ГиБ": {
            "задания (w12.MIN_FREE_GIB, он же w11.J2_MIN_FREE_GIB)": MIN_FREE_GIB,
            "фактический в этом прогоне": float(min_free_gib),
            "понижен": float(min_free_gib) < MIN_FREE_GIB,
            "чем понижен": (
                "ключом запуска --min-free-gib по санкции мастера; константа "
                "в коде не менялась. Основание — замеренный пик этого счёта "
                "против 2,3 ГиБ расчёта Шейля, под который порог 4,0 "
                "назначался волной 11J"
            ) if float(min_free_gib) < MIN_FREE_GIB else "не понижен",
        },
        "порог остановки по ходу, свободной физической ГиБ": ABORT_FREE_GIB,
        "порог присутствия выделений, мольная доля": PRESENT_FLOOR,
        "порог «дошло до равновесия», доля": REACHED_FRACTION,
        "карта чувствительности": mapping.to_dict("records") if len(mapping)
        else [],
        "порог по межфазной энергии": threshold_verdict(mapping),
        "за 200 ч": horizons.to_dict("records") if len(horizons) else [],
        "замер памяти": measurement,
        "как получена эта сводка": (
            "пересобрана из кэша ключом --tables-only, счёт не запускался"
            if tables_only else "посчитана прогоном"
        ),
        "чего расчёт не устанавливает": [
            "межфазная энергия матрица/P-фаза не измерена; она прогнана "
            "диапазоном 0,05…0,50 Дж/м², и абсолютная шкала времени верна "
            "ровно настолько, насколько верна она",
            "скандия в mc_ni 2.036 нет; считается основа ЭК199-ВИ, влияние "
            "скандия не оценивается никак",
            "ниобия в расчёте нет по причине инструмента, а не физики; "
            "0,06 масс. % ниобия сдвигают равновесную долю P-фазы, и величина "
            "сдвига названа в сводке отдельно",
            "KWN-модель двухфазная: M23C6 и MNS_Q, найденные волной 12-2, в "
            "кинетике не участвуют",
            "плотность P-фазы в базе плотностей — оценка по правилу смеси, а "
            "не своя модель; молярный объём выделения известен с той же "
            "точностью",
            "ползучесть, релаксация контактного давления вальцовки и коррозия "
            "во фторидах вне расчёта",
            "бориды и силициды паяной зоны из подпункта 12-4 здесь не "
            "рассматриваются",
        ],
    }
    w12.write_json(summary, "k1_summary.json")

    if tables_only:
        log("--tables-only: журнал прогресса не менялся")
        return

    complete = (
        not payload.get("пропущено")
        and len(payload.get("случаи", []))
        == len(K_TEMPERATURES_C) * len(K_SITES) * len(gammas)
    )
    progress["12-1"] = {
        "готов": complete,
        "время": time.strftime("%Y-%m-%d %H:%M:%S"),
        "случаев посчитано": len(payload.get("случаи", [])),
        "случаев в сетке": len(K_TEMPERATURES_C) * len(K_SITES) * len(gammas),
        "пропущено": len(payload.get("пропущено", [])),
        "узлов по времени": len(payload.get("узлы, ч", [])),
        "межфазная энергия, Дж/м²": [float(value) for value in gammas],
    }
    w12.save_progress(progress)


def step_volumes(force: bool = False, **_ignored: Any) -> None:
    """Посчитать молярные объёмы и равновесие двух фаз и выйти.

    Отдельный шаг, а не часть прогона кинетики, и причина — память.
    Равновесие на полном наборе 48 фаз тянет за собой символьные модели всех
    сорока восьми, около 1,3 ГиБ рабочего набора, и CPython не возвращает их
    системе даже после освобождения объектов. В отдельном процессе они
    умирают вместе с ним, а прогон кинетики читает готовые числа с диска и
    моделей 48 фаз не строит вовсе.

    Порядок запуска подпункта поэтому такой:

        ... study_hn62m_wave12_kinetics.py --only volumes
        ... study_hn62m_wave12_kinetics.py --only k1
    """

    path = CACHE / VOLUMES_PATH_NAME
    if path.is_file() and force:
        path.unlink()
    ctx = w11.Context()
    mole = w11.wt_to_mole(ctx, working_wt())
    mole_full = w11.wt_to_mole(ctx, w11.full_wt())
    volumes, references = volumes_and_references(ctx, mole, mole_full)
    for temperature in K_TEMPERATURES_C:
        log(f"{temperature:.0f} °C: V_m {MATRIX_PHASE} "
            f"{volumes[temperature][MATRIX_PHASE]['молярный объём, см³/моль']:.4f}, "
            f"{PRECIPITATE_PHASE} "
            f"{volumes[temperature][PRECIPITATE_PHASE]['молярный объём, см³/моль']:.4f} "
            f"см³/моль; равновесие двух фаз: P-фаза "
            f"{references[temperature]['мольная доля P-фазы, %']:.4f} мольн. %")


STEPS = {"volumes": step_volumes, "k1": step_k1}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Волна 12, подпункт 12-1: кинетика P-фазы в ЭК199-ВИ"
    )
    parser.add_argument("--only", default="all",
                    help="volumes, k1; через запятую. volumes готовит\n"
                         "молярные объёмы отдельным процессом, см. step_volumes")
    parser.add_argument("--force", action="store_true", help="пересчитать готовое")
    parser.add_argument("--gammas", default=None,
                        help="межфазные энергии, Дж/м², через запятую")
    parser.add_argument("--per-decade", type=int, default=K_PER_DECADE,
                        help="узлов сетки времени на декаду")
    parser.add_argument("--t-min-h", type=float, default=K_T_MIN_H,
                        help="первый узел сетки времени, ч")
    parser.add_argument("--min-free-gib", type=float, default=MIN_FREE_GIB,
                        help="порог входа по свободной физической памяти, "
                             "ГиБ; понижение — отступление от задания")
    parser.add_argument("--tables-only", action="store_true",
                        help="пересобрать таблицы, графики и сводку из кэша "
                             "без счёта")
    parser.add_argument("--k1", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--handoff", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    gammas = (
        tuple(float(value) for value in args.gammas.split(",") if value.strip())
        if args.gammas else K_GAMMA
    )

    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    if args.k1 is not None:
        payload = k1_kinetics(force=args.force, gammas=gammas,
                              per_decade=args.per_decade,
                              t_min_h=args.t_min_h,
                              min_free_gib=args.min_free_gib)
        if args.handoff:
            Path(args.handoff).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), "utf-8"
            )
        return 0

    requested = [name.strip().lower() for name in args.only.split(",")
                 if name.strip()]
    if requested == ["all"]:
        # Умолчание — только кинетика. Шаг volumes намеренно не входит в
        # «всё»: его смысл в том, чтобы идти отдельным процессом, и запуск
        # обоих шагов подряд в одном процессе этот смысл отменяет.
        requested = ["k1"]
    unknown = [name for name in requested if name not in STEPS]
    if unknown:
        parser.error(f"неизвестные подпункты: {', '.join(unknown)}")

    for name in requested:
        started = time.perf_counter()
        log(f"=== {name.upper()} ===")
        if name == "volumes":
            STEPS[name](force=args.force)
        else:
            STEPS[name](force=args.force, gammas=gammas,
                        per_decade=args.per_decade, t_min_h=args.t_min_h,
                        min_free_gib=args.min_free_gib,
                        tables_only=args.tables_only)
        log(f"=== {name.upper()} готов за {time.perf_counter() - started:.1f} с ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
