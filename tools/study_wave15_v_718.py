#!/usr/bin/env python3
"""Волна 15, задача 15-В, часть 2 — сверка по сплаву 718 при 700…750 °C.

Задание `tasks/WAVE15_V_OPUS.md`, отчёт `tasks/WAVE15_V_REPORT.md`.

Вопрос ровно один. В 15-А сверка при 600 °C не сошлась: `mc_ni` 2.036 дала
равновесную долю γ′ 0,61 и 0,38 от измеренной. Холодный ли это край температур
или база вообще? Здесь 700 и 750 °C и другая фаза — γ″ (`GAMMA_DP`, Ni3Nb,
объёмноцентрированная тетрагональная).

Измеренные числа перенесены из задания мастера, а не из статей: сами файлы у
мастера (`tasks/RULES.md`, «Источники»). Источники названы в `SOURCES`.

Шаги:

* ``eq`` — пункт 6: равновесие без кинетики при 700 и 750 °C, двумя наборами
  фаз. Полный набор — что база считает устойчивым на самом деле; пара
  ``FCC_A1 + GAMMA_DP`` — метастабильное равновесие, к которому идёт KWN и с
  которым сопоставимо число Devaux по балансу ниобия. Молярные объёмы — из
  базы физических данных приложения тем же путём, которым их считает сама
  программа (``calculate_physical_properties``).
* ``estimate`` — оценка зародыша самого приложения до расчёта; по ней выбрана
  сетка размеров.
* ``inputs`` — все входы KWN одним файлом, до первого прогона.
* ``kwn`` — пункт 7: шесть прогонов штатным ``run_precipitation``, по одному
  процессу-потомку на случай.
* ``report`` — пункты 7–9: таблицы, преобразование формы, графики. Без счёта.

Ничего не подгоняется. Все входы объявлены в этом файле (``ALLOY``, ``GAMMAS``,
``GRID``, ``case_arguments``) и записаны шагом ``inputs`` до первого прогона.

Запуск (интерпретатор — venv основного репозитория):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 ^
        tools\\study_wave15_v_718.py --only eq
    ... --only estimate   ... --only inputs
    ... --only kwn --min-free-gib 3.0
    ... --only report

Память. Порог входа — ключ ``--min-free-gib`` (по заданию 3,0 ГиБ). Аварийный
порог по ходу — ``study_hn62m_wave12.E1_ABORT_FREE_GIB``, читается из исходника
и не меняется.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
for entry in (ROOT / "app", TOOLS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

OUT = ROOT / "results" / "wave15_v"
DB_REL = "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"
PDB_REL = "databases/physical/original/physical_data_v103.pdb"

MATRIX_PHASE = "FCC_A1"
PRECIPITATE_PHASE = "GAMMA_DP"
# Плотность выборки приложения (`ThermoGar_app`, pdens=500) и контроль на 100.
EQ_PDENS = (500, 100)

AVOGADRO = 6.02214076e23  # 1/моль, точное значение SI 2019

# --------------------------------------------------------------------------- #
# Входы — из задания мастера
# --------------------------------------------------------------------------- #

SOURCES = {
    "состав": "Devaux и др., Mater. Sci. Eng. A 486 (2008) 117",
    "межфазная энергия": "Devaux и др., там же — измерена",
    "молярный объём γ″": "Devaux и др., там же — измерен",
    "размеры частиц": "Slama C., Abdellaoui M., J. Alloys Compd. 306 (2000) 277",
    "доля γ″ по времени": "Ghaemifar S., Mirzadeh H., J. Mater. Res. Technol. 27 (2023) 4248",
}

# Состав 718, масс. %. Основа — железо; добавок шесть, предел BL-21 равен
# десяти, значит штатный путь приложения такой состав принимает.
ALLOY = {
    "название": "718",
    "основа": "FE",
    "состав, масс. %": {
        "NI": 54.2,
        "CR": 17.90,
        "NB": 5.3,
        "MO": 2.99,
        "TI": 0.97,
        "AL": 0.5,
    },
}
COMPONENTS = ("AL", "CR", "FE", "MO", "NB", "NI", "TI", "VA")

# Межфазная энергия измерена: 95 ± 17 мДж/м². Считается трижды — центр и края.
GAMMAS_MJ = (78.0, 95.0, 112.0)
GAMMA_CENTRE_MJ = 95.0

# Молярный объём γ″, измеренный Devaux: 2,92e-5 м³/моль.
#
# Это объём на моль формульных единиц Ni3Nb, то есть на 4 атома. Проверка по
# кристаллографии: у D0_22 (γ″) ячейка a²·c с 8 атомами, при a ≈ 0,3624 нм и
# c ≈ 0,7406 нм объём ячейки 9,73e-29 м³, на атом 1,22e-29 м³, на моль атомов
# 7,32e-6 м³. Ровно четверть от 2,92e-5.
#
# `kawin` получает молярный объём через `VolumeParameter.setVolume(..., 'VM', 1)`
# (`app/thermogar_precipitation.py`: `atomsPerCell = 1`), а движущую силу —
# от `pycalphad` в джоулях на моль атомов. Значит и Vm обязан быть на моль
# атомов. Перевод — деление на 4, не подгонка: числа формульной единицы Ni3Nb.
GAMMA_DP_VM_MEASURED_M3_PER_MOL_FORMULA = 2.92e-5
GAMMA_DP_ATOMS_PER_FORMULA = 4
GAMMA_DP_VM_CM3_PER_MOL_ATOMS = (
    GAMMA_DP_VM_MEASURED_M3_PER_MOL_FORMULA / GAMMA_DP_ATOMS_PER_FORMULA * 1e6
)

TEMPERATURES_C = (700.0, 750.0)

# --------------------------------------------------------------------------- #
# Измеренное — из задания мастера
# --------------------------------------------------------------------------- #

# Пункт 6. Равновесие по Devaux.
DEVAUX_EQUILIBRIUM = {
    "доля γ″ по балансу ниобия, %": 6.2,
    "как получена": (
        "собственный расчёт Devaux из исходных 4660 моль/м³ ниобия и "
        "равновесных 2560 моль/м³ в матрице"
    ),
    "доля γ″ по чужим работам, %": 15.0,
    "как получена чужая": (
        "приведена там же; расхождение авторы объясняют тем, что γ″ содержит "
        "не только ниобий, но и молибден с титаном"
    ),
    "Nb в матрице, ат. %": 1.8,
    "отношение сторон диска q": (0.35, 0.05),
}

# Пункт 7. Slama и Abdellaoui: ПЭМ, закалка от 990 °C. L — длина диска γ″,
# e — его толщина, d — диаметр сферы γ′. Диапазон записан парой (низ, верх).
SLAMA = {
    680.0: {
        "t, ч": (4.0, 50.0, 100.0),
        "L, нм": ((10.0, 10.0), (30.0, 35.0), (50.0, 50.0)),
        "e, нм": (None, (11.0, 11.0), (13.0, 13.0)),
        "γ′ d, нм": (6.0, 12.0, 16.0),
    },
    750.0: {
        "t, ч": (4.0, 50.0, 100.0),
        "L, нм": ((30.0, 30.0), (80.0, 90.0), (120.0, 120.0)),
        "e, нм": ((9.0, 9.0), (17.0, 17.0), (22.0, 22.0)),
        "γ′ d, нм": (8.0, 26.0, 33.0),
    },
}

# Пункт 7. Ghaemifar и Mirzadeh: сплав выращен селективным лазерным плавлением,
# не катаный. Кинетика ускорена, ниобий частично связан фазой Лавеса,
# насыщенная доля ниже. Сверяется отдельно и с этой оговоркой.
GHAEMIFAR = {
    700.0: {
        "t, ч": (0.5, 0.75, 1.0, 2.0),
        "доля γ″, %": (6.38, 7.07, 8.54, 11.70),
        "q = e/L": (0.26, 0.27),
    },
    750.0: {
        "t, ч": (0.5, 0.75, 1.0, 2.0),
        "доля γ″, %": (10.45, 10.82, 11.43, 12.40),
        "q = e/L": (0.25, 0.26),
    },
}

# Отношения расчёт/опыт по равновесной доле при 600 °C из 15-А — то, с чем
# сравнивается ответ пункта 9.
WAVE15A_RATIOS = {"A: Ni-7,5Al-8,5Cr": 0.61, "Б: Ni-5,2Al-14,2Cr": 0.38}

HORIZON_H = 100.0
OUTPUT_TIMES_H = (0.5, 0.75, 1.0, 2.0, 4.0, 50.0, 100.0)

# Параметры, которые при объёмном зарождении в kawin не участвуют
# (`setNucleationDensity` берёт для BULK только bulkN0), но обязательны в
# сигнатуре `run_precipitation`. Значения — из штатного вызова
# `tools/test_precipitation_grid.py::_run_demo`, как в 15-А.
UNUSED_FOR_BULK = {"grain_size_um": 100.0, "dislocation_density": 5e12, "gb_energy": 0.3}

# Сетка размеров. Выбирается шагом ``estimate`` по оценке зародыша самого
# приложения до первого прогона и объявляется здесь; после объявления не
# меняется. Обоснование — в `inputs.json` и в отчёте.
#
# Пробная оценка (`estimate_probe.json`): наименьший критический радиус по шести
# случаям — 0,3003 нм (700 °C, γ = 78 мДж/м²), наибольший — 0,539 нм (750 °C,
# γ = 112 мДж/м²); наименьший радиус зародыша — 0,4174 нм; предел kawin
# Rmin = 0,3 нм.
#
# cMin 0,1 нм ниже и радиуса зародыша, и Rmin. Ширина класса
# (50 − 0,1)/800 = 0,0624 нм — в 4,8 раза меньше наименьшего r*, то есть проверка
# BL-22 проходит с запасом. cMax 50 нм выбран по наибольшей измеренной частице:
# диск Slama L = 120 нм, e = 22 нм при 750 °C и 100 ч имеет объём
# π·(L/2)²·e = 2,49·10⁵ нм³, то есть равновеликую сферу радиусом 39,0 нм; дальше
# kawin расширяет сетку сам (adaptive, maxBins = 2·bins). Сетка одна на все шесть
# случаев.
GRID: dict[str, float] = {"cmin_nm": 0.1, "cmax_nm": 50.0, "bins": 800}

# Метастабильная пара — то равновесие, к которому идёт KWN.
EQ_KEY_PAIR = "FCC_A1 + GAMMA_DP, pdens=500"
EQ_KEY_ALL = "все фазы, pdens=500"
EQ_KEY_TRIPLE = "FCC_A1 + GAMMA_DP + GAMMA_PRIME, pdens=500"


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def write_json(payload: Any, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=float) + "\n",
        encoding="utf-8",
    )
    return path


def read_json(name: str) -> Any:
    return json.loads((OUT / name).read_text("utf-8"))


def free_gib() -> float:
    import psutil

    return psutil.virtual_memory().available / 1024.0**3


def composition_text() -> str:
    return ", ".join(f"{el}={value:g}" for el, value in ALLOY["состав, масс. %"].items())


# --------------------------------------------------------------------------- #
# Пункт 6. Равновесие
# --------------------------------------------------------------------------- #


def _database() -> tuple[Any, list[str], list[str]]:
    """База приложения с его правками загрузки и список фаз этой системы.

    Путь волны 11 (`study_hn62m_wave11.Context`): все фазы, которые
    `filter_phases` допускает для набора компонентов, минус фазы с моделью
    упорядочения, не строящейся на этом составе.
    """

    from pycalphad import Database
    from pycalphad.core.utils import filter_phases, unpack_species
    import thermogar_database_repair as repair

    db = Database(str(ROOT / DB_REL))
    repair.repair_database(db, database_label=Path(DB_REL).name)
    phases = sorted(filter_phases(db, unpack_species(db, list(COMPONENTS))))
    phases, removed = repair.drop_broken_order_disorder(db, list(COMPONENTS), phases)
    return db, list(phases), sorted(removed)


def _mole_fractions(db: Any) -> tuple[list[str], np.ndarray]:
    """Состав в мольных долях штатным путём приложения, из массовых процентов."""

    from thermogar_precipitation import _composition_vectors

    elements, x_at, _x_wt = _composition_vectors(
        db, ALLOY["основа"], composition_text(), "wt"
    )
    return list(elements), np.asarray(x_at, float)


def _phase_rows(db: Any, result: Any, physical_db: Any, temperature_k: float) -> dict[str, Any]:
    from thermogar_parallel import _aggregate
    from thermogar_physical import calculate_physical_properties

    components = [name for name in COMPONENTS]
    fractions, compositions = _aggregate(result, components)
    physical = calculate_physical_properties(
        db, result, components, temperature_k, physical_db
    )
    table = physical.phase_table
    phases: dict[str, Any] = {}
    for name in sorted(fractions):
        row = table[table["Фаза"] == name]
        record: dict[str, Any] = {
            "мольная доля, %": 100.0 * float(fractions[name]),
            "состав, ат. %": {
                element: 100.0 * float(value)
                for element, value in sorted(compositions[name].items())
            },
        }
        if not row.empty:
            first = row.iloc[0]
            for key in (
                "Объёмная доля, %", "Плотность фазы, кг/м³",
                "Молярный объём, см³/моль атомов",
                "Средняя молярная масса, г/моль атомов",
                "Модель плотности", "Статус данных", "Примечание",
            ):
                value = first[key]
                record[key] = (
                    None
                    if value is None or (isinstance(value, float) and not np.isfinite(value))
                    else (
                        float(value)
                        if isinstance(value, (int, float, np.floating))
                        else str(value)
                    )
                )
        phases[name] = record
    return phases


def step_eq(**_ignored: Any) -> None:
    from pycalphad import equilibrium, variables as v
    from thermogar_physical import PhysicalDensityDatabase

    started = time.perf_counter()
    db, phases, removed = _database()
    physical_db = PhysicalDensityDatabase(str(ROOT / PDB_REL))
    elements, x_at = _mole_fractions(db)
    log(f"фаз в системе: {len(phases)}; исключено: {removed or 'нет'}")
    log("состав, ат. %: " + ", ".join(f"{el} {100*x:.4g}" for el, x in zip(elements, x_at)))

    payload: dict[str, Any] = {
        "сплав": ALLOY,
        "источники": SOURCES,
        "база": DB_REL,
        "база плотностей": PDB_REL,
        "SHA-256 базы плотностей": physical_db.sha256,
        "компоненты": list(COMPONENTS),
        "состав, ат. доли": {el: float(x) for el, x in zip(elements, x_at)},
        "добавок к основе": len(elements) - 1,
        "предел BL-21, добавок": None,
        "фазы полного набора": phases,
        "исключены при сборке": removed,
        "температуры, °C": list(TEMPERATURES_C),
        "равновесие": {},
    }
    from thermogar_precipitation import KWN_MAX_SOLUTES

    payload["предел BL-21, добавок"] = int(KWN_MAX_SOLUTES)

    for temperature_c in TEMPERATURES_C:
        temperature_k = temperature_c + 273.15
        conditions = {v.N: 1.0, v.P: 101325.0, v.T: temperature_k}
        conditions.update(
            {v.X(el): float(x) for el, x in zip(elements[1:], x_at[1:])}
        )
        record: dict[str, Any] = {}
        for label, phase_set in (
            ("все фазы", phases),
            ("FCC_A1 + GAMMA_DP", [MATRIX_PHASE, PRECIPITATE_PHASE]),
            # Контроль: та же метастабильная постановка, но γ′ не запрещена.
            # Нужен, чтобы отделить свойство базы от следствия запрета: в паре
            # без γ′ весь алюминий и титан деваться больше некуда, и они уходят
            # в γ″, завышая её долю. KWN эту тройку решать не умеет — выделение
            # у `run_precipitation` одно, — поэтому контроль только равновесный.
            ("FCC_A1 + GAMMA_DP + GAMMA_PRIME",
             [MATRIX_PHASE, PRECIPITATE_PHASE, "GAMMA_PRIME"]),
        ):
            for pdens in EQ_PDENS:
                result = equilibrium(
                    db, list(COMPONENTS), phase_set, conditions,
                    calc_opts={"pdens": pdens},
                )
                rows = _phase_rows(db, result, physical_db, temperature_k)
                record[f"{label}, pdens={pdens}"] = rows
                log(
                    f"{temperature_c:.0f} °C {label} pdens={pdens}: "
                    + "; ".join(
                        f"{n} {r['мольная доля, %']:.3f} мол.% / "
                        f"{(r.get('Объёмная доля, %') if r.get('Объёмная доля, %') is not None else float('nan')):.3f} об.%"
                        for n, r in rows.items()
                    )
                )
                del result
        payload["равновесие"][f"{temperature_c:g}"] = record
    payload["секунд"] = time.perf_counter() - started
    path = write_json(payload, "eq_718.json")
    log(f"записано {path}")


# --------------------------------------------------------------------------- #
# Входы KWN
# --------------------------------------------------------------------------- #


def molar_volumes(temperature_c: float) -> dict[str, Any]:
    """Молярные объёмы из пункта 6: база плотностей приложения, своя T.

    Матрица — на равновесном составе матрицы при этой температуре, как просит
    задание. Выделение — измеренное число Devaux, переведённое на моль атомов;
    рядом сохраняется то, что о `GAMMA_DP` говорит база физических данных
    приложения, для сравнения.
    """

    rows = read_json("eq_718.json")["равновесие"][f"{temperature_c:g}"][EQ_KEY_PAIR]
    payload: dict[str, Any] = {}
    for phase in (MATRIX_PHASE, PRECIPITATE_PHASE):
        row = rows.get(phase, {})
        payload[phase] = {
            "молярный объём базы, см³/моль атомов": row.get("Молярный объём, см³/моль атомов"),
            "плотность базы, кг/м³": row.get("Плотность фазы, кг/м³"),
            "статус": row.get("Статус данных"),
            "модель плотности": row.get("Модель плотности"),
            "примечание": row.get("Примечание"),
            "состав фазы, ат. %": row.get("состав, ат. %"),
        }
    payload[PRECIPITATE_PHASE]["молярный объём измеренный, м³/моль формульных единиц"] = (
        GAMMA_DP_VM_MEASURED_M3_PER_MOL_FORMULA
    )
    payload[PRECIPITATE_PHASE]["атомов в формульной единице"] = GAMMA_DP_ATOMS_PER_FORMULA
    payload[PRECIPITATE_PHASE]["молярный объём в расчёт, см³/моль атомов"] = (
        GAMMA_DP_VM_CM3_PER_MOL_ATOMS
    )
    return payload


def nb_balance_fraction(
    x_nb_initial: float,
    x_nb_matrix_eq: float,
    matrix_vm_cm3: float,
    precip_vm_cm3: float = GAMMA_DP_VM_CM3_PER_MOL_ATOMS,
    nb_in_stoichiometric_gamma_dp: float = 0.25,
) -> dict[str, float]:
    """Доля γ″ по рецепту самого Devaux — балансом ниобия.

    Devaux считает так: из исходных 4660 моль/м³ ниобия и равновесных
    2560 моль/м³, оставшихся в матрице, всё вычтенное уходит в стехиометрический
    Ni3Nb, у которого ниобия ровно четверть узлов:

        c = x(Nb) / Vm,   c(γ″) = 0,25 / Vm(γ″),
        f = (c⁰ − c_матр) / c(γ″).

    Это **другой способ**, чем прямой CALPHAD-расчёт доли двухфазного
    равновесия: он приписывает γ″ только ниобий и только в стехиометрии 3:1.
    Считается здесь ровно для того, чтобы сравнивать с числом Devaux
    одинаковым способом, а не сравнивать разные величины.
    """

    c0 = x_nb_initial / (matrix_vm_cm3 * 1e-6)
    c_matrix = x_nb_matrix_eq / (matrix_vm_cm3 * 1e-6)
    c_precip = nb_in_stoichiometric_gamma_dp / (precip_vm_cm3 * 1e-6)
    return {
        "c⁰(Nb), моль/м³": c0,
        "c равновесная в матрице (Nb), моль/м³": c_matrix,
        "c(Nb) в стехиометрическом Ni3Nb, моль/м³": c_precip,
        "доля по балансу ниобия, %": 100.0 * (c0 - c_matrix) / c_precip,
    }


def bulk_sites(matrix_vm_cm3: float) -> float:
    """N0 = N_A / Vm: атомных узлов матрицы в кубическом метре."""

    return AVOGADRO / (matrix_vm_cm3 * 1e-6)


def case_id(temperature_c: float, gamma_mj: float, horizon_h: float = HORIZON_H) -> str:
    """Имя случая. Горизонт попадает в имя, только если он не объявленный.

    Объявленный горизонт — ``HORIZON_H`` = 100 ч, по наибольшему узлу Slama.
    Прогон с укороченным горизонтом складывается отдельно и в отчёте называется
    отдельно: у ``kawin`` нижний предел шага пропорционален горизонту
    (``Solver.solve``: ``_dtmin = 1e-8 * (tf - t0)``), поэтому горизонт — не
    только окно вывода, но и численный параметр.
    """

    name = f"T{temperature_c:g}_g{gamma_mj:g}"
    if float(horizon_h) != float(HORIZON_H):
        name += f"_h{horizon_h:g}"
    return name.replace(".", "_")


def case_arguments(
    temperature_c: float,
    gamma_mj: float,
    grid: Mapping[str, float],
    horizon_h: float = HORIZON_H,
) -> dict[str, Any]:
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    volumes = molar_volumes(temperature_c)
    matrix_vm = float(volumes[MATRIX_PHASE]["молярный объём базы, см³/моль атомов"])
    precip_vm = float(GAMMA_DP_VM_CM3_PER_MOL_ATOMS)
    return dict(
        db=object(),
        database_path=ROOT / DB_REL,
        database_label=RELEASE_DATABASE_LABELS["ni"],
        database_key="ni",
        balance=ALLOY["основа"],
        composition_text=composition_text(),
        units="wt",
        matrix_phase=MATRIX_PHASE,
        precipitate_phase=PRECIPITATE_PHASE,
        schedule_mode="isothermal",
        temperature_c=float(temperature_c),
        duration_h=float(horizon_h),
        profile_text="",
        gamma=gamma_mj * 1e-3,
        matrix_vm=matrix_vm,
        precip_vm=precip_vm,
        nucleation_type="BULK",
        bulk_n0=bulk_sites(matrix_vm),
        **UNUSED_FOR_BULK,
        cmin_nm=float(grid["cmin_nm"]),
        cmax_nm=float(grid["cmax_nm"]),
        bins=int(grid["bins"]),
        input_provenance=(
            f"WAVE15_V: состав и межфазная энергия — {SOURCES['состав']} (измерена); "
            "Vm(GAMMA_DP) измерен там же, переведён на моль атомов делением на 4; "
            "Vm(FCC_A1) — physical_data_v103.pdb на равновесном составе матрицы; "
            "N0 = N_A/Vm(FCC_A1)"
        ),
        input_confirmation=True,
    )


class _StopBeforeSolve(Exception):
    pass


def estimate_case(
    temperature_c: float, gamma_mj: float, grid: Mapping[str, float]
) -> dict[str, Any]:
    """Оценка зародыша приложения и время инкубации kawin по начальному составу.

    Идёт штатный `run_precipitation` до `solve`: проверки BL-32 и BL-22
    выполняются как в расчёте, `solve` заменён исключением только здесь.
    Постановка — та же, что в 15-А (`study_wave15_validation.estimate_case`).
    """

    import kawin.precipitation.NucleationRate as nr
    import thermogar_precipitation as precipitation

    temperature_k = float(temperature_c) + 273.15
    captured: dict[str, Any] = {}
    original_estimates = precipitation._nucleus_estimates
    original_solve = precipitation.PrecipitateModel.solve

    def estimates(model, phase, temperatures):
        result = original_estimates(model, phase, temperatures)
        p = model.phaseIndex(phase)
        parameters = model.precipitates[p]
        x = np.squeeze(model.data.composition[0])
        _chem, dgv, _b = nr.volumetricDrivingForce(
            model.therm, x, temperature_k, parameters, removeCache=True
        )
        rcrit, gcrit = nr.nucleationBarrier(float(np.squeeze(dgv)), parameters)
        z = nr.zeldovich(temperature_k, rcrit, parameters)
        beta = nr.betaMulti(
            model.therm, x, temperature_k, rcrit, model.matrix, parameters,
            removeCache=True,
        )
        tau = nr.incubationTime(beta, z, model.matrix)
        rate = nr.nucleationRate(z, beta, gcrit, temperature_k, tau, time=np.inf)
        captured.update({
            "движущая сила, Дж/м³": float(np.squeeze(dgv)),
            "химическая движущая сила, Дж/моль": float(np.squeeze(_chem)),
            "критический радиус kawin, нм": 1e9 * float(np.squeeze(rcrit)),
            "барьер, kT": float(np.squeeze(gcrit)) / (1.380649e-23 * temperature_k),
            "Rmin kawin, нм": 1e9 * float(parameters.Rmin),
            "u = Rmin/r*": float(parameters.Rmin) / float(np.squeeze(rcrit)),
            "время инкубации τ, с": float(np.squeeze(tau)),
            "стационарная скорость зарождения на узел, 1/с": float(np.squeeze(rate)),
            "стационарная скорость зарождения, 1/(м³·с)": float(np.squeeze(rate))
            * float(model.matrix.nucleationSites.bulkN0),
            "оценка приложения": [list(map(float, row)) for row in result],
        })
        return result

    def solve(*_a, **_k):
        raise _StopBeforeSolve()

    precipitation._nucleus_estimates = estimates
    precipitation.PrecipitateModel.solve = solve
    try:
        result = precipitation.run_precipitation(
            **case_arguments(temperature_c, gamma_mj, grid)
        )
        captured["проверки до расчёта"] = "пройдены"
        captured["предупреждения"] = list(getattr(result, "warnings", []))
    except _StopBeforeSolve:
        captured["проверки до расчёта"] = "пройдены"
    except ValueError as error:
        captured["проверки до расчёта"] = f"отказ: {error}"
    finally:
        precipitation._nucleus_estimates = original_estimates
        precipitation.PrecipitateModel.solve = original_solve
    return captured


def _warnings_before_solve(
    temperature_c: float, gamma_mj: float, grid: Mapping[str, float]
) -> list[str]:
    """Предупреждения, которые приложение выдаёт до `solve` на этих входах.

    Задание требует, чтобы проверки до расчёта прошли без предупреждений.
    Ловятся они так же, как в 15-А: `solve` подменяется исключением, а список
    `warnings` собирается на модели до него.
    """

    import thermogar_precipitation as precipitation

    captured: list[str] = []
    original_check = precipitation._check_critical_radius_floor
    original_solve = precipitation.PrecipitateModel.solve

    def check(*args, **kwargs):
        found = original_check(*args, **kwargs)
        captured.extend(list(found))
        return found

    def solve(*_a, **_k):
        raise _StopBeforeSolve()

    precipitation._check_critical_radius_floor = check
    precipitation.PrecipitateModel.solve = solve
    try:
        precipitation.run_precipitation(**case_arguments(temperature_c, gamma_mj, grid))
    except _StopBeforeSolve:
        pass
    finally:
        precipitation._check_critical_radius_floor = original_check
        precipitation.PrecipitateModel.solve = original_solve
    return captured


def cases() -> list[tuple[float, float]]:
    """Порядок прогонов: центр, затем края погрешности, по температурам."""

    order = []
    low, centre, high = GAMMAS_MJ
    for temperature_c in TEMPERATURES_C:
        order += [
            (temperature_c, centre),
            (temperature_c, low),
            (temperature_c, high),
        ]
    return order


def step_estimate(**_ignored: Any) -> None:
    """Пробная оценка зародыша — по ней выбирается сетка. Счёта KWN нет."""

    probe = {"cmin_nm": 0.05, "cmax_nm": 5.0, "bins": 1000}
    payload = {}
    for temperature_c, gamma in cases():
        record = estimate_case(temperature_c, gamma, probe)
        payload[case_id(temperature_c, gamma)] = record
        log(
            f"{temperature_c:g} °C γ={gamma:g}: "
            + json.dumps(
                {k: v for k, v in record.items() if k != "оценка приложения"},
                ensure_ascii=False,
            )
        )
    write_json({"пробная сетка": probe, "случаи": payload}, "estimate_probe.json")


def step_inputs(**_ignored: Any) -> None:
    """Все входы KWN одним файлом — до первого прогона."""

    probe = read_json("estimate_probe.json")["случаи"]
    width_nm = (GRID["cmax_nm"] - GRID["cmin_nm"]) / GRID["bins"]
    payload: dict[str, Any] = {
        "сплав": ALLOY,
        "состав, масс. %": ALLOY["состав, масс. %"],
        "источники": SOURCES,
        "матрица": MATRIX_PHASE,
        "выделение": PRECIPITATE_PHASE,
        "температуры, °C": list(TEMPERATURES_C),
        "межфазная энергия, мДж/м²": list(GAMMAS_MJ),
        "горизонт, ч": HORIZON_H,
        "узлы вывода, ч": list(OUTPUT_TIMES_H),
        "зарождение": "BULK",
        "сетка размеров": GRID,
        "ширина класса, нм": width_nm,
        "не участвуют при BULK": UNUSED_FOR_BULK,
        "N0": "N0 = N_A / Vm(FCC_A1), N_A = 6,02214076e23 1/моль",
        "молярный объём γ″": {
            "измерено, м³/моль формульных единиц": GAMMA_DP_VM_MEASURED_M3_PER_MOL_FORMULA,
            "атомов в формульной единице Ni3Nb": GAMMA_DP_ATOMS_PER_FORMULA,
            "в расчёт, см³/моль атомов": GAMMA_DP_VM_CM3_PER_MOL_ATOMS,
        },
        "температуры": {},
    }
    for temperature_c in TEMPERATURES_C:
        volumes = molar_volumes(temperature_c)
        vm = float(volumes[MATRIX_PHASE]["молярный объём базы, см³/моль атомов"])
        record: dict[str, Any] = {
            "молярные объёмы": volumes,
            "N0, 1/м³": bulk_sites(vm),
            "случаи": {},
        }
        for gamma in GAMMAS_MJ:
            arguments = case_arguments(temperature_c, gamma, GRID)
            estimate = probe[case_id(temperature_c, gamma)]
            warnings = _warnings_before_solve(temperature_c, gamma, GRID)
            record["случаи"][case_id(temperature_c, gamma)] = {
                "межфазная энергия, Дж/м²": arguments["gamma"],
                "молярный объём матрицы, см³/моль": arguments["matrix_vm"],
                "молярный объём выделения, см³/моль": arguments["precip_vm"],
                "N0, 1/м³": arguments["bulk_n0"],
                "критический радиус на старте, нм": estimate["критический радиус kawin, нм"],
                "u = Rmin/r*": estimate["u = Rmin/r*"],
                "запас сетки r*/ширина класса": estimate["критический радиус kawin, нм"] / width_nm,
                "проверки до расчёта": estimate["проверки до расчёта"],
                "предупреждений до расчёта": len(warnings),
                "предупреждения до расчёта": warnings,
            }
        payload["температуры"][f"{temperature_c:g}"] = record
    write_json(payload, "inputs.json")
    log("входы записаны в inputs.json")


# --------------------------------------------------------------------------- #
# Прогоны KWN, по одному процессу на случай
# --------------------------------------------------------------------------- #


def abort_free_gib() -> float:
    """Аварийный порог модуля волны 12, прочитанный из исходника без импорта."""

    import ast

    tree = ast.parse((TOOLS / "study_hn62m_wave12.py").read_text("utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "E1_ABORT_FREE_GIB" for t in node.targets
        ):
            return float(ast.literal_eval(node.value))
    raise RuntimeError("E1_ABORT_FREE_GIB не найден")


def run_dir(case: str) -> Path:
    return OUT / "runs" / case


def child_run(
    temperature_c: float, gamma_mj: float, horizon_h: float = HORIZON_H
) -> None:
    """Один расчёт штатным `run_precipitation`; выходы — на диск.

    Обёртка над ``PrecipitateModel.solve`` ловит обрыв интегрирования и
    возвращает управление штатному пути: таблицы, проверки и сводка строятся
    тем же кодом приложения по данным, накопленным до обрыва. Физику обёртка не
    трогает — ни одного входа и ни одной формулы; она только не даёт исключению
    выбросить уже посчитанное.

    Зачем она нужна: на составе 718 (шесть добавок) штатный расчёт при
    `GAMMA_DP` падает внутри `pycalphad` на локальном равновесии, когда добавка
    почти вычерпана из матрицы (`ZeroDivisionError` в
    `minimizer.write_row_fixed_mole_fraction`: полное количество системы
    обращается в ноль). Без обёртки пропадает весь прогон целиком, вместе с той
    его частью, которая посчиталась и на которой стоят все узлы опыта
    Ghaemifar. Обрыв записывается в `run.json` и назван в отчёте.
    """

    import thermogar_precipitation as precipitation

    case = case_id(temperature_c, gamma_mj, horizon_h)
    folder = run_dir(case)
    folder.mkdir(parents=True, exist_ok=True)
    arguments = case_arguments(temperature_c, gamma_mj, GRID, horizon_h)

    interrupted: dict[str, Any] = {}
    original_solve = precipitation.PrecipitateModel.solve

    def tolerant_solve(self, *args: Any, **kwargs: Any):
        try:
            return original_solve(self, *args, **kwargs)
        except BaseException as error:  # noqa: BLE001 — обрыв именно ловится
            data = self.data
            steps = int(data.n)
            reached_h = float(np.asarray(data.time, float)[steps]) / 3600.0
            interrupted.update({
                "оборван": True,
                "тип": type(error).__name__,
                "сообщение": str(error),
                "шагов до обрыва": steps + 1,
                "модельное время обрыва, ч": reached_h,
            })
            return None

    precipitation.PrecipitateModel.solve = tolerant_solve
    started = time.perf_counter()
    try:
        result = precipitation.run_precipitation(**arguments)
    finally:
        precipitation.PrecipitateModel.solve = original_solve
    seconds = time.perf_counter() - started
    write = dict(index=False, encoding="utf-8")
    result.kinetics.to_csv(folder / "kinetics.csv", **write)
    result.matrix_composition.to_csv(folder / "matrix.csv", **write)
    result.interface_composition.to_csv(folder / "interface.csv", **write)
    result.psd.to_csv(folder / "psd_final.csv", **write)
    result.quality.to_csv(folder / "quality.csv", **write)
    result.summary.to_csv(folder / "summary.csv", **write)
    result.settings.to_csv(folder / "settings.csv", **write)
    (folder / "provenance.json").write_bytes(result.provenance)
    meta = {
        "случай": case,
        "температура, °C": temperature_c,
        "межфазная энергия, мДж/м²": gamma_mj,
        "секунд": seconds,
        "шагов": int(len(result.kinetics)),
        "предупреждения": list(result.warnings),
        "проверки": result.quality.to_dict(orient="records"),
        "обрыв": interrupted or {"оборван": False},
        "горизонт прогона, ч": float(horizon_h),
        "горизонт объявленный, ч": HORIZON_H,
        "доведено до, ч": float(result.kinetics["Время, ч"].iloc[-1]),
    }
    (folder / "run.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), "utf-8"
    )
    print("CHILD_DONE", json.dumps(meta, ensure_ascii=False), flush=True)


def step_kwn(
    min_free_gib: float = 3.0,
    only_case: str | None = None,
    force: bool = False,
    horizon_h: float = HORIZON_H,
    **_ignored: Any,
) -> None:
    import psutil

    abort_gib = abort_free_gib()
    log(
        f"порог входа {min_free_gib} ГиБ (ключ), аварийный {abort_gib} ГиБ "
        "(модуль волны 12)"
    )
    summary_path = OUT / "runs" / "memory.jsonl"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    for temperature_c, gamma in cases():
        case = case_id(temperature_c, gamma, horizon_h)
        if only_case and case != only_case:
            continue
        if (run_dir(case) / "run.json").is_file() and not force:
            log(f"{case}: уже посчитан")
            continue
        waited = 0.0
        while free_gib() < min_free_gib:
            if waited > 1800:
                raise RuntimeError(
                    f"{case}: свободной памяти меньше {min_free_gib} ГиБ 1800 с"
                )
            time.sleep(5)
            waited += 5
        free_start = free_gib()
        log(f"{case}: старт, свободно {free_start:.2f} ГиБ")
        run_dir(case).mkdir(parents=True, exist_ok=True)
        log_file = (run_dir(case) / "child.log.txt").open("w", encoding="utf-8")
        env = dict(os.environ, PYTHONHASHSEED="0")
        process = subprocess.Popen(
            [
                sys.executable, "-B", "-X", "utf8", str(Path(__file__)),
                "--child", str(temperature_c), str(gamma), str(horizon_h),
            ],
            stdout=log_file, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT),
        )
        handle = psutil.Process(process.pid)
        record = {
            "случай": case,
            "горизонт прогона, ч": float(horizon_h),
            "порог входа, ГиБ": min_free_gib,
            "аварийный порог, ГиБ": abort_gib,
            "свободно на старте, ГиБ": free_start,
            "пик рабочего набора, ГиБ": 0.0,
            "минимум свободной, ГиБ": free_start,
            "снят": False,
        }
        started = time.perf_counter()
        while process.poll() is None:
            try:
                family = [handle] + handle.children(recursive=True)
                rss = sum(member.memory_info().rss for member in family) / 1024.0**3
            except psutil.Error:
                rss = 0.0
            free = free_gib()
            record["пик рабочего набора, ГиБ"] = max(record["пик рабочего набора, ГиБ"], rss)
            record["минимум свободной, ГиБ"] = min(record["минимум свободной, ГиБ"], free)
            if free < abort_gib:
                record["снят"] = True
                process.kill()
                log(f"{case}: СНЯТ по памяти, свободно {free:.2f} ГиБ")
                break
            time.sleep(2)
        process.wait()
        log_file.close()
        record["exit"] = process.returncode
        record["секунд"] = time.perf_counter() - started
        with summary_path.open("a", encoding="utf-8") as handle_out:
            handle_out.write(json.dumps(record, ensure_ascii=False) + "\n")
        log(
            f"{case}: exit {process.returncode}, {record['секунд']:.0f} с, "
            f"пик {record['пик рабочего набора, ГиБ']:.2f} ГиБ"
        )
        if process.returncode != 0:
            raise RuntimeError(f"{case}: потомок завершился с кодом {process.returncode}")


# --------------------------------------------------------------------------- #
# Пункт 8. Форма: сфера модели -> диск опыта
# --------------------------------------------------------------------------- #


def disk_length_from_radius(radius_nm: np.ndarray | float, q: float) -> np.ndarray | float:
    """Длина диска γ″ той же объёмной величины, что сфера радиуса R.

    Модель считает сферы, а γ″ — диск (толщина e, длина L, отношение сторон
    q = e/L). Приравниваются объёмы:

        (4/3)·π·R³ = π·(L/2)²·e = π·(L/2)²·q·L = (π·q/4)·L³

    отсюда

        L = R · (16 / (3·q))^(1/3),   e = q·L.

    Диск считается круглым цилиндром — так его и меряют в ПЭМ (длина по
    габаритному размеру пластины, толщина по её торцу). Ни один параметр здесь
    не подбирается: q берётся из опыта.
    """

    return np.asarray(radius_nm, float) * (16.0 / (3.0 * float(q))) ** (1.0 / 3.0)


def q_from_slama(record: Mapping[str, Any], index: int) -> float | None:
    """Отношение сторон по измеренным L и e Slama на этом узле."""

    thickness = record["e, нм"][index]
    if thickness is None:
        return None
    length = record["L, нм"][index]
    return float(np.mean(thickness)) / float(np.mean(length))


# --------------------------------------------------------------------------- #
# Отчёт: таблицы и графики. Без счёта.
# --------------------------------------------------------------------------- #


def time_at_fraction(
    time_h: np.ndarray, fraction_percent: np.ndarray, target_percent: float
) -> float:
    """Когда расчёт впервые набирает заданную объёмную долю, ч.

    Берётся возрастающий участок до максимума — то есть до обрыва или до выхода
    на равновесие. Если расчёт такой доли не набрал, возвращается NaN.

    Зачем: оборванный прогон не доходит до узлов опыта по времени, но проходит
    измеренные **доли** — и тогда сверять можно не «доля в момент t», а
    «момент, когда достигнута доля». Так же сравнивала волна 15-Б.
    """

    peak = int(np.nanargmax(fraction_percent))
    rising_t = time_h[: peak + 1]
    rising_f = fraction_percent[: peak + 1]
    if not len(rising_f) or float(rising_f[-1]) < float(target_percent):
        return float("nan")
    return float(np.interp(float(target_percent), rising_f, rising_t))


def load_kinetics(case: str):
    import pandas as pd

    return pd.read_csv(run_dir(case) / "kinetics.csv", encoding="utf-8")


def at_times(time_h: np.ndarray, values: np.ndarray, nodes: Sequence[float]) -> np.ndarray:
    """Значение в узле: линейно по логарифму времени между шагами решателя."""

    mask = time_h > 0
    return np.interp(
        np.log10(nodes), np.log10(time_h[mask]), values[mask], left=np.nan, right=np.nan
    )


def fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    value = float(value)
    if not np.isfinite(value):
        return "—"
    text = f"{value:.{digits}g}"
    if "e" in text:
        mantissa, exponent = text.split("e")
        text = f"{mantissa}·10^{int(exponent)}"
    return text.replace(".", ",")


def step_report(horizon_h: float = HORIZON_H, **_ignored: Any) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    figures = OUT / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    inputs = read_json("inputs.json")
    eq = read_json("eq_718.json")
    probe = read_json("estimate_probe.json")["случаи"]
    low, centre, high = GAMMAS_MJ
    order = (centre, low, high)
    lines: list[str] = []
    summary: dict[str, Any] = {"равновесие": {}, "кинетика": {}}

    # --- Пункт 6: равновесие -------------------------------------------------
    lines.append("## Равновесие\n")
    lines.append(
        "| T, °C | набор фаз | фазы в равновесии | доля GAMMA_DP, об. % | "
        "доля GAMMA_DP, мол. % | Nb в матрице, ат. % |"
    )
    lines.append("|---|---|---|---|---|---|")
    for temperature_c in TEMPERATURES_C:
        record = eq["равновесие"][f"{temperature_c:g}"]
        for key in (EQ_KEY_ALL, EQ_KEY_PAIR, EQ_KEY_TRIPLE):
            rows = record[key]
            gp = rows.get(PRECIPITATE_PHASE, {})
            matrix = rows.get(MATRIX_PHASE, {})
            present = ", ".join(
                name for name, row in sorted(rows.items())
                if row["мольная доля, %"] > 1e-6
            )
            summary["равновесие"].setdefault(f"{temperature_c:g}", {})[key] = {
                "доля GAMMA_DP, об. %": gp.get("Объёмная доля, %"),
                "доля GAMMA_DP, мол. %": gp.get("мольная доля, %"),
                "Nb в матрице, ат. %": (matrix.get("состав, ат. %") or {}).get("NB"),
                "состав GAMMA_DP, ат. %": gp.get("состав, ат. %"),
                "Vm GAMMA_DP базы, см³/моль атомов": gp.get("Молярный объём, см³/моль атомов"),
                "статус Vm GAMMA_DP": gp.get("Статус данных"),
                "фазы": present,
            }
            lines.append(
                f"| {temperature_c:.0f} | {key} | {present} | "
                f"{fmt(gp.get('Объёмная доля, %'))} | {fmt(gp.get('мольная доля, %'))} | "
                f"{fmt((matrix.get('состав, ат. %') or {}).get('NB'))} |"
            )

    # Доля по рецепту самого Devaux — балансом ниобия, на нашем равновесии.
    x_nb_initial = float(eq["состав, ат. доли"]["NB"])
    lines.append("\n### Доля γ″ по балансу ниобия — рецептом самого Devaux\n")
    lines.append(
        "| T, °C | c⁰(Nb), моль/м³ | c(Nb) в матрице, моль/м³ | "
        "c(Nb) в Ni3Nb, моль/м³ | доля по балансу, % | Devaux, % | наше/Devaux |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for temperature_c in TEMPERATURES_C:
      for key in (EQ_KEY_PAIR, EQ_KEY_TRIPLE):
        rows = eq["равновесие"][f"{temperature_c:g}"][key]
        matrix_vm = float(rows[MATRIX_PHASE]["Молярный объём, см³/моль атомов"])
        x_nb_matrix = float(rows[MATRIX_PHASE]["состав, ат. %"]["NB"]) / 100.0
        balance = nb_balance_fraction(x_nb_initial, x_nb_matrix, matrix_vm)
        devaux = DEVAUX_EQUILIBRIUM["доля γ″ по балансу ниобия, %"]
        summary["равновесие"].setdefault(f"{temperature_c:g}", {})[
            f"баланс ниобия: {key}"
        ] = balance
        lines.append(
            f"| {temperature_c:.0f} ({key.split(',')[0]}) | {fmt(balance['c⁰(Nb), моль/м³'], 4)} | "
            f"{fmt(balance['c равновесная в матрице (Nb), моль/м³'], 4)} | "
            f"{fmt(balance['c(Nb) в стехиометрическом Ni3Nb, моль/м³'], 5)} | "
            f"{fmt(balance['доля по балансу ниобия, %'])} | {fmt(devaux)} | "
            f"{fmt(balance['доля по балансу ниобия, %'] / devaux, 2)} |"
        )

    # --- Пункт 7 и 8: кинетика ----------------------------------------------
    for temperature_c in TEMPERATURES_C:
        runs = {
            g: load_kinetics(case_id(temperature_c, g, horizon_h))
            for g in order
            if (run_dir(case_id(temperature_c, g, horizon_h)) / "kinetics.csv").is_file()
        }
        if centre not in runs:
            log(f"{temperature_c:g} °C: центральный прогон не посчитан, пропуск")
            continue
        meta = {
            g: json.loads(
                (run_dir(case_id(temperature_c, g, horizon_h)) / "run.json").read_text("utf-8")
            )
            for g in runs
        }
        key = f"{temperature_c:g}"
        summary["кинетика"][key] = {"прогоны": {}}
        lines.append(f"\n## Кинетика при {temperature_c:.0f} °C\n")
        for g in order:
            if g not in runs:
                continue
            m = meta[g]
            failed = [c["Проверка"] for c in m["проверки"] if c["Статус"] != "пройдена"]
            lines.append(
                f"* γ = {fmt(g)} мДж/м²: шагов {m['шагов']}, {m['секунд']:.0f} с; "
                f"проверки: {'все пройдены' if not failed else 'ошибка — ' + ', '.join(failed)}; "
                f"предупреждений: {len(m['предупреждения'])}"
            )
            summary["кинетика"][key]["прогоны"][g] = {
                "проверки не пройдены": failed,
                "предупреждения": m["предупреждения"],
                "шагов": m["шагов"],
                "секунд": m["секунд"],
            }

        times = {g: runs[g]["Время, ч"].to_numpy(float) for g in runs}

        # Доля — Ghaemifar (СЛП, отдельно).
        gh = GHAEMIFAR.get(temperature_c)
        if gh:
            nodes = list(gh["t, ч"])
            measured = np.asarray(gh["доля γ″, %"], float)
            calc = {
                g: at_times(times[g], runs[g]["Объёмная доля, %"].to_numpy(float), nodes)
                for g in runs
            }
            ratio = calc[centre] / measured
            band_lo = np.nanmin(np.vstack([calc[g] for g in runs]), axis=0) / measured
            band_hi = np.nanmax(np.vstack([calc[g] for g in runs]), axis=0) / measured
            summary["кинетика"][key]["доля против Ghaemifar"] = {
                "узлы, ч": nodes, "опыт, %": measured.tolist(),
                "центр, %": calc[centre].tolist(),
                "отношение центр": ratio.tolist(),
                "полоса min": band_lo.tolist(), "полоса max": band_hi.tolist(),
            }
            lines.append("\n### Объёмная доля γ″ против Ghaemifar (СЛП)\n")
            head = [f"расчёт при {fmt(g)}" for g in order if g in runs]
            lines.append(
                "| t, ч | измерено | " + " | ".join(head)
                + f" | расчёт/опыт при {fmt(centre)} | расчёт/опыт по полосе |"
            )
            lines.append("|---" * (4 + len(head)) + "|")
            for i, t in enumerate(nodes):
                cells = [fmt(calc[g][i]) for g in order if g in runs]
                lines.append(
                    f"| {t:g} | {fmt(measured[i])} | " + " | ".join(cells)
                    + f" | {fmt(ratio[i], 2)} | {fmt(band_lo[i], 2)}…{fmt(band_hi[i], 2)} |"
                )

        # Когда расчёт набирает измеренную долю — сверка по доле, а не по времени.
        if gh:
            lines.append("")
            lines.append(
                f"### Когда расчёт набирает измеренную долю (при {temperature_c:.0f} °C)"
            )
            lines.append("")
            lines.append(
                "| доля опыта, % | t опыта, ч | t расчёта при "
                f"{fmt(centre)}, ч | t расчёта по полосе, ч | t расчёта / t опыта |"
            )
            lines.append("|---|---|---|---|---|")
            reached = []
            for i, t_exp in enumerate(gh["t, ч"]):
                target = float(gh["доля γ″, %"][i])
                got = {
                    g: time_at_fraction(
                        times[g], runs[g]["Объёмная доля, %"].to_numpy(float), target
                    )
                    for g in runs
                }
                centre_t = got[centre]
                band = [v for v in got.values() if np.isfinite(v)]
                lines.append(
                    f"| {fmt(target)} | {t_exp:g} | {fmt(centre_t, 3)} | "
                    + (f"{fmt(min(band), 3)}…{fmt(max(band), 3)}" if band else "—")
                    + f" | {fmt(centre_t / t_exp, 2)} |"
                )
                reached.append({
                    "доля опыта, %": target, "t опыта, ч": t_exp,
                    "t расчёта при центре, ч": centre_t,
                    "t расчёта / t опыта": centre_t / t_exp,
                })
            summary["кинетика"][key]["когда набрана доля опыта"] = reached

        # Размер — Slama, через преобразование формы.
        sl = SLAMA.get(temperature_c)
        if sl:
            nodes = list(sl["t, ч"])
            lines.append("\n### Длина диска γ″ против Slama (после преобразования формы)\n")
            lines.append(
                "| t, ч | L опыт, нм | e опыт, нм | q = e/L опыт | R расчёт, нм | "
                "L расчёт, нм | L расчёт по полосе, нм | L расчёт/опыт |"
            )
            lines.append("|---|---|---|---|---|---|---|---|")
            rows_out = []
            for i, t in enumerate(nodes):
                q = q_from_slama(sl, i)
                length = sl["L, нм"][i]
                thickness = sl["e, нм"][i]
                radius = {
                    g: float(at_times(times[g], runs[g]["Средний радиус, нм"].to_numpy(float), [t])[0])
                    for g in runs
                }
                if q is None:
                    lines.append(
                        f"| {t:g} | {fmt(np.mean(length))} | — | — | "
                        f"{fmt(radius[centre])} | — | — | — |"
                    )
                    rows_out.append({"t, ч": t, "q": None})
                    continue
                converted = {g: float(disk_length_from_radius(radius[g], q)) for g in runs}
                measured_l = float(np.mean(length))
                ratio = converted[centre] / measured_l
                lo = min(converted.values())
                hi = max(converted.values())
                lines.append(
                    f"| {t:g} | {fmt(measured_l)} | {fmt(np.mean(thickness))} | {fmt(q, 2)} | "
                    f"{fmt(radius[centre])} | {fmt(converted[centre])} | "
                    f"{fmt(lo)}…{fmt(hi)} | {fmt(ratio, 2)} |"
                )
                rows_out.append({
                    "t, ч": t, "q": q, "L опыт, нм": measured_l,
                    "R расчёт, нм": radius[centre], "L расчёт, нм": converted[centre],
                    "L расчёт/опыт": ratio,
                })
            summary["кинетика"][key]["размер против Slama"] = rows_out

        # --- Графики ---------------------------------------------------------
        for column, label, fname, measured_points in (
            ("Объёмная доля, %", "Объёмная доля γ″, %", "f",
             (list(gh["t, ч"]), list(gh["доля γ″, %"])) if gh else None),
            ("Средний радиус, нм", "Средний радиус модели, нм", "R", None),
        ):
            fig, ax = plt.subplots(figsize=(6.4, 4.8), dpi=150)
            y_all = {g: runs[g][column].to_numpy(float) for g in runs}
            # Левый край оси — по самому раннему шагу расчёта: при обрыве в
            # первые секунды кривая иначе уходит за границу и графика нет.
            first_h = min(float(times[g][times[g] > 0].min()) for g in runs)
            last_h = max(float(times[g].max()) for g in runs)
            left = 10.0 ** np.floor(np.log10(first_h))
            if low in runs and high in runs:
                grid_t = np.logspace(np.log10(max(left, 1e-9)), np.log10(last_h), 400)
                y_low = at_times(times[low], y_all[low], grid_t)
                y_high = at_times(times[high], y_all[high], grid_t)
                ax.fill_between(
                    grid_t, np.fmin(y_low, y_high), np.fmax(y_low, y_high),
                    color="#9ec5f4", alpha=0.55, linewidth=0,
                    label=f"расчёт, γ от {fmt(low)} до {fmt(high)} мДж/м²",
                )
            mask = times[centre] > 0
            ax.plot(
                times[centre][mask], y_all[centre][mask], color="#2a78d6", linewidth=2,
                label=f"расчёт, γ = {fmt(centre)} мДж/м²",
            )
            if measured_points:
                ax.plot(
                    measured_points[0], measured_points[1], "o", color="#0b0b0b",
                    markersize=6,
                    label="опыт, Ghaemifar (СЛП; погрешности не переданы)",
                )
            if column == "Объёмная доля, %":
                pair = eq["равновесие"][f"{temperature_c:g}"][EQ_KEY_PAIR]
                value = pair[PRECIPITATE_PHASE]["Объёмная доля, %"]
                ax.axhline(
                    value, color="#2a78d6", linewidth=1, linestyle=":",
                    label=f"равновесие пары по базе {fmt(value)} %",
                )
                ax.axhline(
                    DEVAUX_EQUILIBRIUM["доля γ″ по балансу ниобия, %"],
                    color="#52514e", linewidth=1, linestyle="--",
                    label="Devaux, баланс ниобия "
                    f"{fmt(DEVAUX_EQUILIBRIUM['доля γ″ по балансу ниобия, %'])} %",
                )
                ax.axhline(
                    DEVAUX_EQUILIBRIUM["доля γ″ по чужим работам, %"],
                    color="#8a6d3b", linewidth=1, linestyle="-.",
                    label="чужие работы, приведённые там же "
                    f"{fmt(DEVAUX_EQUILIBRIUM['доля γ″ по чужим работам, %'])} %",
                )
            broken = [
                float(times[g].max()) for g in runs
                if meta[g]["обрыв"].get("оборван")
            ]
            if broken:
                ax.axvspan(
                    min(broken), 2e2, color="#d9d7d2", alpha=0.45, linewidth=0,
                    label="расчёта здесь нет: прогоны оборваны",
                )
            ax.set_xscale("log")
            ax.set_xlim(left, 2e2)
            ax.set_xlabel(f"Время старения при {temperature_c:.0f} °C, ч")
            ax.set_ylabel(label)
            ax.set_title(f"Сплав 718, {temperature_c:.0f} °C: {label.split(',')[0].lower()}")
            ax.grid(True, which="major", color="#e4e3df", linewidth=0.6)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
            ax.legend(fontsize=7.5, frameon=False, loc="upper center",
                      bbox_to_anchor=(0.5, -0.16), ncol=2)
            fig.tight_layout()
            fig.savefig(figures / f"T{temperature_c:.0f}_{fname}.png")
            plt.close(fig)

        # График длины диска: расчёт после преобразования против Slama.
        if sl:
            fig, ax = plt.subplots(figsize=(6.4, 4.8), dpi=150)
            q_nodes = [q_from_slama(sl, i) for i in range(len(sl["t, ч"]))]
            known = [q for q in q_nodes if q is not None]
            q_used = float(np.mean(known)) if known else None
            if q_used is not None:
                grid_t = np.logspace(
                    np.log10(min(float(times[g][times[g] > 0].min()) for g in runs)),
                    np.log10(max(float(times[g].max()) for g in runs)),
                    400,
                )
                converted = {
                    g: disk_length_from_radius(
                        at_times(times[g], runs[g]["Средний радиус, нм"].to_numpy(float), grid_t),
                        q_used,
                    )
                    for g in runs
                }
                if low in runs and high in runs:
                    ax.fill_between(
                        grid_t, np.fmin(converted[low], converted[high]),
                        np.fmax(converted[low], converted[high]),
                        color="#9ec5f4", alpha=0.55, linewidth=0,
                        label=f"расчёт, γ от {fmt(low)} до {fmt(high)} мДж/м²",
                    )
                ax.plot(
                    grid_t, converted[centre], color="#2a78d6", linewidth=2,
                    label=f"расчёт, γ = {fmt(centre)} мДж/м², q = {fmt(q_used, 2)}",
                )
                ax.plot(
                    list(sl["t, ч"]), [float(np.mean(v)) for v in sl["L, нм"]], "o",
                    color="#0b0b0b", markersize=6,
                    label="опыт, Slama — длина диска L",
                )
                broken = [
                    float(times[g].max()) for g in runs
                    if meta[g]["обрыв"].get("оборван")
                ]
                if broken:
                    ax.axvspan(
                        min(broken), 2e2, color="#d9d7d2", alpha=0.45, linewidth=0,
                        label="расчёта здесь нет: прогоны оборваны",
                    )
                ax.set_xscale("log")
                ax.set_yscale("log")
                ax.set_xlim(10.0 ** np.floor(np.log10(
                    min(float(times[g][times[g] > 0].min()) for g in runs))), 2e2)
                ax.set_xlabel(f"Время старения при {temperature_c:.0f} °C, ч")
                ax.set_ylabel("Длина диска γ″, нм")
                ax.set_title(
                    f"Сплав 718, {temperature_c:.0f} °C: длина диска после "
                    "преобразования формы"
                )
                ax.grid(True, which="major", color="#e4e3df", linewidth=0.6)
                for side in ("top", "right"):
                    ax.spines[side].set_visible(False)
                ax.legend(fontsize=7.5, frameon=False, loc="upper center",
                          bbox_to_anchor=(0.5, -0.16), ncol=2)
                fig.tight_layout()
                fig.savefig(figures / f"T{temperature_c:.0f}_L.png")
            plt.close(fig)

        # Состав матрицы по ниобию — прямая проверка базы по времени.
        matrix_frame = pd.read_csv(
            run_dir(case_id(temperature_c, centre, horizon_h)) / "matrix.csv",
            encoding="utf-8",
        )
        column = "NB, матрица, ат.%"
        if column in matrix_frame.columns:
            summary["кинетика"][key]["Nb в матрице на горизонте, ат. %"] = float(
                matrix_frame[column].iloc[-1]
            )

    (OUT / "tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(summary, "comparison.json")
    log(f"таблицы: {OUT / 'tables.md'}; графики: {figures}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

STEPS = {
    "eq": step_eq,
    "estimate": step_estimate,
    "inputs": step_inputs,
    "kwn": step_kwn,
    "report": step_report,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", choices=sorted(STEPS))
    parser.add_argument(
        "--child", nargs=3, metavar=("TEMPERATURE_C", "GAMMA_MJ", "HORIZON_H")
    )
    parser.add_argument(
        "--horizon-h", type=float, default=HORIZON_H,
        help="горизонт прогона, ч; объявленный — 100, укороченный кладётся отдельно",
    )
    parser.add_argument("--min-free-gib", type=float, default=3.0)
    parser.add_argument("--case")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.child:
        child_run(float(args.child[0]), float(args.child[1]), float(args.child[2]))
        return 0
    if not args.only:
        parser.error("нужен --only или --child")
    STEPS[args.only](
        min_free_gib=args.min_free_gib, only_case=args.case, force=args.force,
        horizon_h=args.horizon_h,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
