#!/usr/bin/env python3
"""Плотность: приёмочные тесты волны 10 (пункт A4).

Проверяется физика, а не факт вызова: чистые элементы против справочных
значений, матрица контрольного сплава против известного диапазона для сплавов
Ni–Cr–Mo, монотонность по температуре.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -X utf8 -m pytest tools/test_density.py -v
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from pycalphad import Database, equilibrium, variables as v
from pycalphad.core.utils import filter_phases, unpack_species

import thermogar_database_repair as repair
import thermogar_verified_physical as verified_physical
from thermogar_physical import (
    PhysicalDensityDatabase,
    calculate_physical_properties,
    default_overrides_path,
    load_physical_overrides,
)

PDB_PATH = ROOT / "databases/physical/original/physical_data_v103.pdb"
NI_TDB = ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"
AL_TDB = ROOT / "databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb"
FE_TDB = ROOT / "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb"

# Контрольный состав ХН62М(Sc)-ВИ, мольные доли без никеля.
CONTROL_X = {
    "AL": 0.005522, "C": 0.000248, "CR": 0.269357, "FE": 0.005336,
    "MN": 0.005424, "MO": 0.080756, "NB": 0.000385, "S": 0.000372,
    "SI": 0.002122, "TI": 0.001245,
}
CONTROL_COMPONENTS = (
    "NI", "CR", "MO", "C", "SI", "MN", "S", "NB", "AL", "TI", "FE", "VA",
)

# Разобранная и починенная база. Наружу не отдаётся никогда: тесты получают
# изолированную копию, см. _database. Разбор одного TDB стоит около 4,5 с, и
# повторять его на каждый тест незачем — незачем и делить один объект.
_MASTER: dict[str, Any] = {}


@pytest.fixture
def physical_db() -> PhysicalDensityDatabase:
    """Своя физическая база на каждый тест.

    Область видимости — тест, а не модуль: у ``PhysicalDensityDatabase`` есть
    изменяемые ``functions`` и кэш значений, и делить их между тестами значит
    заводить ту же зависимость от порядка, из-за которой чинился `BL-19`.
    Разбор PDB стоит меньше миллисекунды, так что делить нечего ради чего.
    """

    if not PDB_PATH.is_file():
        pytest.skip(f"Нет PDB: {PDB_PATH}")
    return PhysicalDensityDatabase(PDB_PATH)


@pytest.fixture
def physical_db_plain() -> PhysicalDensityDatabase:
    """База без единой нашей поправки, что бы ни стояло в окружении."""

    if not PDB_PATH.is_file():
        pytest.skip(f"Нет PDB: {PDB_PATH}")
    return PhysicalDensityDatabase(PDB_PATH, overrides=None)


def _mean_linear_expansion(
    physical_database: PhysicalDensityDatabase,
) -> float:
    """Средний линейный коэффициент расширения матрицы, 25…1100 °C, 1/K.

    Плотность обратна кубу линейного размера, поэтому
    ᾱ = ((ρ₂₅/ρ₁₁₀₀)^(1/3) − 1) / ΔT.
    """

    database = _database(NI_TDB)
    components = list(CONTROL_COMPONENTS)
    elements = [name for name in components if name != "VA"]
    densities: list[float] = []
    for temperature_c in (25.0, 1100.0):
        temperature_k = temperature_c + 273.15
        result = calculate_physical_properties(
            database,
            _solve(database, components, ["FCC_A1"], CONTROL_X, temperature_k),
            elements,
            temperature_k,
            physical_database,
        )
        assert result.alloy_density_kg_m3 is not None, (
            f"При {temperature_c} °C плотность матрицы не посчитана"
        )
        densities.append(float(result.alloy_density_kg_m3))
    cold, hot = densities
    return ((cold / hot) ** (1.0 / 3.0) - 1.0) / (1100.0 - 25.0)


def _database(path: Path) -> Any:
    """Изолированная копия разобранной базы — своя на каждый вызов.

    `BL-19`: до волны 11N здесь отдавался один и тот же объект ``Database``
    всем тестам сразу. Тест, который проходит или падает в зависимости от
    порядка выполнения, однажды соврёт в обе стороны, поэтому общего
    изменяемого состояния тут быть не должно вовсе — независимо от того,
    кто именно его правит.

    Копия делается руками, а не одним ``deepcopy``: ``Database.__deepcopy__``
    самого pycalphad копирует только ``_parameters``, а ``phases``,
    ``symbols`` и ``species`` оставляет **общими** с оригиналом. То есть
    правка модельных подсказок фазы в «копии» дошла бы до всех. Копирование
    стоит около 2 мс против 4,5 с на повторный разбор TDB.
    """

    key = str(path)
    if key not in _MASTER:
        if not path.is_file():
            pytest.skip(f"Нет базы: {path}")
        database = Database(str(path))
        repair.repair_database(database, database_label=path.name)
        _MASTER[key] = database
    return _isolated_copy(_MASTER[key])


def _isolated_copy(database: Any) -> Any:
    """Копия базы, ничего изменяемого не делящая с оригиналом."""

    copied = copy.deepcopy(database)
    copied.phases = copy.deepcopy(database.phases)
    copied.symbols = copy.deepcopy(database.symbols)
    copied.species = copy.deepcopy(database.species)
    return copied


def _solve(
    database: Any,
    components: list[str],
    phases: list[str],
    mole: dict[str, float],
    temperature_k: float,
) -> Any:
    conditions: dict[Any, float] = {
        v.N: 1.0, v.P: 101325.0, v.T: float(temperature_k),
    }
    conditions.update({v.X(element): value for element, value in sorted(mole.items())})
    return equilibrium(
        database, components, phases, conditions, calc_opts={"pdens": 100}
    )


# --------------------------------------------------------------------------- #
# 1. Чистые элементы
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "phase, element, reference",
    [
        ("FCC_A1", "NI", 8914.0),
        ("FCC_A1", "CR", 7200.0),
        ("FCC_A1", "MO", 10223.8),
        ("FCC_A1", "AL", 2698.15),
        ("BCC_A2", "FE", 7874.0),
    ],
)
def test_pure_elements_match_pdb(
    physical_db: PhysicalDensityDatabase,
    phase: str,
    element: str,
    reference: float,
) -> None:
    """Чистые элементы при 298,15 K совпадают со значениями PDB.

    Это проверка формулы объёма одной фазы: если она врёт, врут и все смеси.
    Допуск 0,5 % — разница между табличным значением и тем, что даёт
    температурная функция PDB в точке 298,15 K.
    """

    value, coverage, warnings = physical_db.density_from_site_fractions(
        phase, [{element: 1.0}, {"VA": 1.0}], 298.15
    )
    assert value is not None, f"{phase}/{element}: плотность не посчитана {warnings}"
    assert coverage > 0.999
    assert value == pytest.approx(reference, rel=5.0e-3), (
        f"{phase}/{element}: {value:.1f} против справочных {reference}"
    )


# --------------------------------------------------------------------------- #
# 2–4. Контрольный сплав
# --------------------------------------------------------------------------- #


def test_matrix_density_of_control_alloy(physical_db: PhysicalDensityDatabase) -> None:
    """Матрица контрольного состава при 25 °C — около 8,5 г/см³.

    До правки здесь выходило 4,9 г/см³: ``Model`` строился без вакансии, и
    межузельная подрешётка ``(C,VA)`` после нормировки вырождалась в чистый
    углерод, то есть модель считала плотность карбидного конечного члена.

    Про диапазон. В постановке волны 10 заявлено 8,5…8,7 г/см³ по аналогии со
    сплавами C-4/C-276 (8,6–8,9). Расчёт даёт **8,481 г/см³** — на 0,23 % ниже
    нижней границы, и это не ошибка смешения: у нашего состава хрома заметно
    больше (23,5 % против 16 %), а молибдена меньше (13 % против 16 %), то есть
    сплав легче обоих названных. Ближайший по составу промышленный ориентир —
    Inconel 625 (Ni–21Cr–9Mo–4Nb) с 8,44 г/см³; 8,48 ложится ровно между ним и
    C-4. Поэтому окно теста взято по физике, 8,35…8,75, а расхождение с
    постановкой вынесено в отчёт.
    """

    database = _database(NI_TDB)
    components = list(CONTROL_COMPONENTS)
    elements = [name for name in components if name != "VA"]
    result = calculate_physical_properties(
        database,
        _solve(database, components, ["FCC_A1"], CONTROL_X, 298.15),
        elements,
        298.15,
        physical_db,
    )
    density = result.alloy_density_kg_m3
    assert density is not None, "Плотность матрицы не посчитана"
    assert 8350.0 <= density <= 8750.0, (
        f"Плотность матрицы {density:.1f} кг/м³ вне диапазона 8350…8750"
    )


def test_alloy_density_available_at_every_temperature(
    physical_db: PhysicalDensityDatabase,
) -> None:
    """Плотность сплава выдаётся, а не молчит из-за непокрытых фаз.

    На контрольном составе всегда есть хотя бы MnS, у которого модели в PDB
    нет. Раньше это обнуляло весь результат; теперь такие фазы оцениваются по
    правилу смеси и помечаются как оценочные.
    """

    database = _database(NI_TDB)
    components = list(CONTROL_COMPONENTS)
    elements = [name for name in components if name != "VA"]
    phases = sorted(filter_phases(database, unpack_species(database, components)))
    phases, _removed = repair.drop_broken_order_disorder(database, components, phases)

    temperature_k = 1100.0 + 273.15
    result = calculate_physical_properties(
        database,
        _solve(database, components, phases, CONTROL_X, temperature_k),
        elements,
        temperature_k,
        physical_db,
    )
    assert result.alloy_density_kg_m3 is not None
    assert result.mass_coverage_pct == pytest.approx(100.0, abs=0.01)
    # При 1100 °C сплав практически однофазный, оценочных фаз — доли процента.
    assert result.estimated_mole_pct < 1.0
    assert "оцен" in result.quality_label or "полная" in result.quality_label
    # Диапазон шире заявленного в постановке 8,2–8,6 г/см³, и вот почему.
    #
    # Проверка D1 волны 11D (`tools/d1_density_expansion_check.py`) вырезала
    # выражения DP(FCC_A1,<элемент>:VA) прямо из текста physical_data_v103.pdb и
    # посчитала их собственным разбором, минуя код приложения. На 298,15, 500,
    # 800, 1100 и 1400 K приложение совпало с базой до нуля (макс. расхождение
    # 0,000e+00 кг/м³), то есть двойного учёта расширения в коде нет — наклон
    # ρ(T) целиком из базы.
    #
    # Сама база даёт средние линейные коэффициенты расширения 298…1400 K:
    #   NI 17,8e-6 /K при справочных 13,4e-6
    #   CR 34,5e-6 /K при справочных  6,2e-6  ← в 5,6 раза
    #   MO  6,0e-6 /K при справочных  4,8e-6
    # Для матрицы Ni-0,26Cr-0,08Mo это 30,7e-6 /K на 1100…1300 °C; подстановка
    # литературного хрома опускает её до 15,8e-6, то есть в физическое окно.
    # Сплав полным путём приложения: 8480,6 кг/м³ при 25 °C, 7937,1 при 1100 °C
    # (α = 21,2e-6 /K) и 7790,5 при 1300 °C (α = 31,4e-6 /K на этом участке).
    #
    # Поэтому нижняя граница окна — ограничение базы, а не физика. Величину
    # коэффициента держит `tools/test_density_thermal_expansion.py`.
    assert 7700.0 <= result.alloy_density_kg_m3 <= 8600.0


def test_density_decreases_with_temperature(
    physical_db: PhysicalDensityDatabase,
) -> None:
    """ρ(T) убывает на всём интервале 25…1300 °C.

    Ловит перевёрнутый знак теплового расширения.
    """

    database = _database(NI_TDB)
    components = list(CONTROL_COMPONENTS)
    elements = [name for name in components if name != "VA"]
    phases = sorted(filter_phases(database, unpack_species(database, components)))
    phases, _removed = repair.drop_broken_order_disorder(database, components, phases)

    values: list[tuple[float, float]] = []
    for temperature_c in (25.0, 400.0, 700.0, 1100.0, 1300.0):
        temperature_k = temperature_c + 273.15
        result = calculate_physical_properties(
            database,
            _solve(database, components, phases, CONTROL_X, temperature_k),
            elements,
            temperature_k,
            physical_db,
        )
        assert result.alloy_density_kg_m3 is not None, (
            f"При {temperature_c} °C плотность не посчитана"
        )
        values.append((temperature_c, float(result.alloy_density_kg_m3)))

    for (t1, d1), (t2, d2) in zip(values, values[1:]):
        assert d2 < d1, (
            f"Плотность выросла с {t1} °C ({d1:.1f}) до {t2} °C ({d2:.1f})"
        )


# --------------------------------------------------------------------------- #
# 5. Те же элементы по другим базам
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "tdb, components, phase, mole, reference, tolerance",
    [
        (AL_TDB, ["AL", "CU", "VA"], "FCC_A1", {"CU": 1.0e-6}, 2698.15, 0.02),
        (FE_TDB, ["FE", "CR", "VA"], "BCC_A2", {"CR": 1.0e-6}, 7874.0, 0.02),
    ],
)
def test_pure_element_through_other_databases(
    physical_db: PhysicalDensityDatabase,
    tdb: Path,
    components: list[str],
    phase: str,
    mole: dict[str, float],
    reference: float,
    tolerance: float,
) -> None:
    """Al ≈ 2700 и Fe ≈ 7874 кг/м³ через полный путь расчёта, а не только PDB."""

    database = _database(tdb)
    elements = [name for name in components if name != "VA"]
    result = calculate_physical_properties(
        database,
        _solve(database, components, [phase], mole, 298.15),
        elements,
        298.15,
        physical_db,
    )
    assert result.alloy_density_kg_m3 is not None
    assert result.alloy_density_kg_m3 == pytest.approx(reference, rel=tolerance)


# --------------------------------------------------------------------------- #
# Регрессия на корень дефекта
# --------------------------------------------------------------------------- #


def test_site_fractions_keep_vacancies(physical_db: PhysicalDensityDatabase) -> None:
    """Межузельная подрешётка сохраняет вакансию, а не вырождается в углерод.

    Прямая проверка корня A4.2: ``Model`` строится с ``VA``, поэтому доли
    подрешётки ``(C,VA)`` остаются 2,5·10⁻⁴ и 0,99975. Без этого модель
    плотности считала карбидный конечный член.
    """

    from thermogar_physical import _site_fractions_from_equilibrium

    database = _database(NI_TDB)
    components = ["NI", "CR", "MO", "C", "VA"]
    elements = ["NI", "CR", "MO", "C"]
    result = _solve(
        database, components, ["FCC_A1"],
        {"CR": 0.2694, "MO": 0.0808, "C": 0.000248}, 1423.15,
    )
    y_values = np.asarray(result.Y.values, dtype=float)
    y_rows = y_values.reshape((-1, y_values.shape[-1]))
    site_fractions = _site_fractions_from_equilibrium(
        database, elements, "FCC_A1", y_rows[0]
    )
    assert len(site_fractions) == 2
    assert "VA" in site_fractions[1], (
        "Вакансия пропала из межузельной подрешётки: вернулся дефект A4.2"
    )
    assert site_fractions[1]["VA"] > 0.99
    assert site_fractions[1].get("C", 0.0) < 0.01


def test_mixture_rule_is_volume_additive(
    physical_db: PhysicalDensityDatabase,
) -> None:
    """Плотности смешиваются по объёму, а не линейно по мольной доле.

    Для смеси с сильно разными плотностями правильный ответ строго меньше
    линейного среднего. Тест берёт крайний случай Ni–Al, где разница видна
    невооружённым глазом.
    """

    half = {"NI": 0.5, "AL": 0.5}
    value, coverage, _warnings = physical_db.density_from_site_fractions(
        "FCC_A1", [half, {"VA": 1.0}], 298.15
    )
    assert value is not None and coverage > 0.999
    ni, _c, _w = physical_db.density_from_site_fractions(
        "FCC_A1", [{"NI": 1.0}, {"VA": 1.0}], 298.15
    )
    al, _c, _w = physical_db.density_from_site_fractions(
        "FCC_A1", [{"AL": 1.0}, {"VA": 1.0}], 298.15
    )
    linear = 0.5 * ni + 0.5 * al
    mass_ni, mass_al = 58.693, 26.982
    expected = (0.5 * mass_ni + 0.5 * mass_al) / (
        0.5 * mass_ni / ni + 0.5 * mass_al / al
    )
    assert value == pytest.approx(expected, rel=1.0e-6)
    assert value < linear, (
        "Смешение всё ещё линейно по мольной доле: правило смеси не исправлено"
    )


# --------------------------------------------------------------------------- #
# 11K-2. Тепловое расширение матрицы и поправка по хрому
# --------------------------------------------------------------------------- #

# Физическое окно для аустенитных никелевых жаропрочных сплавов, 25…1100 °C.
EXPANSION_WINDOW = (12.0e-6, 20.0e-6)


def _chromium_override():
    """Запись о поправке по хрому из файла-дополнения, или None."""

    path = default_overrides_path()
    if not path.is_file():
        return None
    overrides = load_physical_overrides(path)
    for entry in overrides.entries:
        if entry.identifier == "cr-thermal-expansion":
            return entry
    return None


def test_plain_database_expansion_is_out_of_physical_window(
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """Сторож теста: без поправки коэффициент расширения вне окна 12…20.

    Без этой проверки основной тест ничего не сторожит — нельзя отличить
    «поправка работает» от «окно такое широкое, что проходит всё».
    Число на чистой базе — около 21,2·10⁻⁶/K, причина в хроме: база даёт ему
    среднее расширение 32,7·10⁻⁶/K на 25…1100 °C.
    """

    assert not physical_db_plain.applied_overrides, (
        "Фикстура обязана давать базу без поправок"
    )
    coefficient = _mean_linear_expansion(physical_db_plain)
    low, high = EXPANSION_WINDOW
    assert not (low <= coefficient <= high), (
        f"Чистая база вдруг попала в окно: {coefficient * 1e6:.2f}e-6/K. "
        "Значит, либо базу подменили, либо окно теста бессмысленно."
    )
    assert coefficient > high, (
        f"Ожидалось завышение, получено {coefficient * 1e6:.2f}e-6/K"
    )


def test_matrix_expansion_within_physical_window(
    physical_db: PhysicalDensityDatabase,
) -> None:
    """С поправкой по хрому матрица укладывается в 12…20·10⁻⁶/K.

    Проверяется отношение ρ(25 °C)/ρ(1100 °C), то есть ровно тот наклон ρ(T),
    который волна 11D-1 признала завышенным.
    """

    entry = _chromium_override()
    if entry is None:
        pytest.skip("Нет файла-дополнения с поправкой по хрому.")
    if not entry.is_filled:
        pytest.skip(
            "Поправка по хрому не заполнена: нет прослеживаемого "
            "первоисточника на тепловое расширение хрома. Список нужных "
            "статей с DOI — tasks/SOURCES_WANTED.md, позиция S-1. "
            f"Состояние записи: {entry.status}."
        )
    assert physical_db.applied_overrides, (
        "Поправка заполнена, но не применилась: проверьте enabled в файле "
        "дополнения и переменную THERMOGAR_PHYSICAL_OVERRIDES."
    )
    coefficient = _mean_linear_expansion(physical_db)
    low, high = EXPANSION_WINDOW
    assert low <= coefficient <= high, (
        f"Средний коэффициент расширения матрицы {coefficient * 1e6:.2f}e-6/K "
        f"вне окна {low * 1e6:.0f}…{high * 1e6:.0f}e-6/K"
    )


# Окно измерений теплового расширения чистого хрома, 25…700 °C.
# Хиднерт 1941 (NBS RP1407, таблица 3) даёт 9,5·10⁻⁶/K до 700 °C, оценка
# REF 14 — 8,8·10⁻⁶/K; окно взято с запасом на обе стороны.
CHROMIUM_EXPANSION_WINDOW = (8.0e-6, 10.0e-6)

# Холодная точка взята 25 °C, а не 20 °C как у Хиднерта: DP-параметр
# BCC_A2 в physical_data_v103.pdb начинается с 298,15 K, ниже он не
# определён. Сдвиг холодной точки на 5 K меняет средний коэффициент на
# 0,04·10⁻⁶/K — на два порядка меньше ширины окна.
CHROMIUM_COLD_C = 25.0
CHROMIUM_HOT_C = 700.0


def _pure_chromium_expansion(
    physical_database: PhysicalDensityDatabase,
) -> float:
    """Средний линейный коэффициент расширения чистого хрома, 25…700 °C, 1/K.

    Считается прямо по DP(BCC_A2,CR:VA), без равновесия: это ровно та
    функция DTCRBCC, которую перекрывает поправка.
    """

    densities: list[float] = []
    for temperature_c in (CHROMIUM_COLD_C, CHROMIUM_HOT_C):
        value, coverage, warnings = physical_database.density_from_site_fractions(
            "BCC_A2", [{"CR": 1.0}, {"VA": 1.0}], temperature_c + 273.15
        )
        assert value is not None, (
            f"Плотность чистого хрома при {temperature_c} °C не посчитана: {warnings}"
        )
        assert coverage > 0.999
        densities.append(float(value))
    cold, hot = densities
    return ((cold / hot) ** (1.0 / 3.0) - 1.0) / (CHROMIUM_HOT_C - CHROMIUM_COLD_C)


def test_plain_chromium_expansion_is_far_above_measurement(
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """Сторож: без поправки хром расширяется втрое быстрее измеренного.

    Активный полином DTCRBCC (REF 14 в переносе базы) даёт на 25…700 °C
    около 25,8·10⁻⁶/K против 9,5·10⁻⁶/K у Хиднерта. Без этой проверки
    основной тест не отличает «поправка работает» от «окно широкое».
    """

    assert not physical_db_plain.applied_overrides, (
        "Фикстура обязана давать базу без поправок"
    )
    coefficient = _pure_chromium_expansion(physical_db_plain)
    assert coefficient > CHROMIUM_EXPANSION_WINDOW[1] * 2.0, (
        "Чистая база вдруг перестала завышать расширение хрома: "
        f"{coefficient * 1e6:.2f}e-6/K"
    )


def test_pure_chromium_expansion_matches_measurement(
    physical_db: PhysicalDensityDatabase,
) -> None:
    """С поправкой чистый хром ложится на измерения: 8…10·10⁻⁶/K.

    Это проверка самого восстановленного наклона, без примеси сплава.
    Коэффициенты взяты из таблицы 1 статьи REF 14 самой базы
    (Lu, Selleby, Sundman, Calphad 29 (2005) 68-89,
    doi:10.1016/j.calphad.2005.05.001) и сверены с независимым измерением
    Хиднерта (NBS RP1407, 1941, таблица 3).
    """

    entry = _chromium_override()
    if entry is None:
        pytest.skip("Нет файла-дополнения с поправкой по хрому.")
    assert entry.is_filled, (
        "Поправка по хрому не заполнена, хотя источник восстановлен в "
        f"волне 11M-2. Состояние записи: {entry.status}."
    )
    assert physical_db.applied_overrides, (
        "Поправка заполнена, но не применилась: проверьте enabled в файле "
        "дополнения и переменную THERMOGAR_PHYSICAL_OVERRIDES."
    )
    coefficient = _pure_chromium_expansion(physical_db)
    low, high = CHROMIUM_EXPANSION_WINDOW
    assert low <= coefficient <= high, (
        f"Средний коэффициент расширения чистого хрома "
        f"{coefficient * 1e6:.2f}e-6/K вне окна "
        f"{low * 1e6:.0f}…{high * 1e6:.0f}e-6/K"
    )


def test_chromium_override_keeps_the_reference_point_of_the_base(
    physical_db: PhysicalDensityDatabase,
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """ρ(298,15 K) чистого хрома не сдвинута: правится наклон, не точка.

    Опорное значение базы 7181,91 кг/м³ со справочником согласуется, а
    V₀ = 7,04033e-6 м³/моль из таблицы 1 статьи описывает НЕмагнитный
    объём и опорной точкой служить не может: M/V₀ даёт 7385 кг/м³, то есть
    на 2,7 % выше справочных 7190.
    """

    if not physical_db.applied_overrides:
        pytest.skip("Поправка не применена — сравнивать нечего.")
    values = []
    for database in (physical_db_plain, physical_db):
        value, _, _ = database.density_from_site_fractions(
            "BCC_A2", [{"CR": 1.0}, {"VA": 1.0}], 298.15
        )
        assert value is not None
        values.append(float(value))
    plain, corrected = values
    assert plain == pytest.approx(7181.91, abs=0.01), (
        f"Опорная точка базы уехала сама по себе: {plain:.2f} кг/м³"
    )
    assert corrected == pytest.approx(7181.91, abs=0.01), (
        f"Поправка сдвинула опорную точку 298,15 K: {plain:.2f} -> {corrected:.2f}"
    )


def test_reference_density_survives_the_override(
    physical_db: PhysicalDensityDatabase,
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """Опорная точка 25 °C верна и сейчас, поправка не имеет права её сдвинуть.

    Правится наклон ρ(T), а не значение при комнатной температуре.
    """

    database = _database(NI_TDB)
    components = list(CONTROL_COMPONENTS)
    elements = [name for name in components if name != "VA"]
    values: list[float] = []
    for physical_database in (physical_db_plain, physical_db):
        result = calculate_physical_properties(
            database,
            _solve(database, components, ["FCC_A1"], CONTROL_X, 298.15),
            elements,
            298.15,
            physical_database,
        )
        assert result.alloy_density_kg_m3 is not None
        values.append(float(result.alloy_density_kg_m3))
    plain, corrected = values
    assert plain == pytest.approx(8481.0, abs=15.0), (
        f"Опорная плотность 25 °C уехала сама по себе: {plain:.1f} кг/м³"
    )
    assert corrected == pytest.approx(plain, rel=1.0e-4), (
        f"Поправка сдвинула опорную точку 25 °C: {plain:.1f} -> {corrected:.1f}"
    )


def test_override_is_announced_in_the_result(
    physical_db: PhysicalDensityDatabase,
) -> None:
    """Применённая поправка названа в результате расчёта, а не молчит.

    Подменять данные источника без ведома пользователя нельзя, поэтому текст
    обязан попасть в ``warnings`` — именно их рисует интерфейс.
    """

    if not physical_db.applied_overrides:
        pytest.skip("Ни одна поправка не применена — объявлять нечего.")
    database = _database(NI_TDB)
    components = list(CONTROL_COMPONENTS)
    elements = [name for name in components if name != "VA"]
    result = calculate_physical_properties(
        database,
        _solve(database, components, ["FCC_A1"], CONTROL_X, 298.15),
        elements,
        298.15,
        physical_db,
    )
    for entry in physical_db.applied_overrides:
        assert entry.user_message in result.warnings, (
            f"Поправка {entry.identifier} применена, но в результате о ней "
            "не сказано"
        )


def test_override_switch_off_returns_the_plain_database() -> None:
    """Выключатель работает и не требует правки файлов.

    Проверяются оба документированных способа: переменная окружения и явный
    ``overrides=None``. Расчёта равновесия здесь нет — сравниваются сами
    выражения базы.
    """

    if not PDB_PATH.is_file():
        pytest.skip(f"Нет PDB: {PDB_PATH}")
    plain = PhysicalDensityDatabase(PDB_PATH, overrides=None)
    assert not plain.applied_overrides

    import os

    from thermogar_physical import (
        PHYSICAL_OVERRIDES_ENV,
        overrides_enabled_by_environment,
    )

    saved = os.environ.get(PHYSICAL_OVERRIDES_ENV)
    try:
        os.environ[PHYSICAL_OVERRIDES_ENV] = "off"
        assert overrides_enabled_by_environment() is False
        switched_off = PhysicalDensityDatabase(PDB_PATH)
        assert not switched_off.applied_overrides
        assert switched_off.overrides is None
        assert (
            switched_off.functions["DTCRBCC"].expression
            == plain.functions["DTCRBCC"].expression
        )
    finally:
        if saved is None:
            os.environ.pop(PHYSICAL_OVERRIDES_ENV, None)
        else:
            os.environ[PHYSICAL_OVERRIDES_ENV] = saved


def test_override_file_is_honest_about_itself() -> None:
    """Файл-дополнение обязан называть себя нашей правкой, а не данными базы.

    И обязан указывать, к какой именно базе он применим: иначе его можно
    незаметно наложить на другую версию PDB.
    """

    path = default_overrides_path()
    if not path.is_file():
        pytest.skip("Файла-дополнения нет.")
    overrides = load_physical_overrides(path)
    assert "правка проекта" in overrides.notice.lower()
    assert re.fullmatch(r"[0-9a-f]{64}", overrides.target_sha256), (
        "Файл-дополнение не называет SHA-256 базы, к которой применим"
    )
    assert overrides.entries, "Пустой файл-дополнение"
    for entry in overrides.entries:
        assert entry.quantity, f"{entry.identifier}: не названа перекрываемая величина"
        assert entry.reason, f"{entry.identifier}: не названа причина правки"
        assert entry.date, f"{entry.identifier}: нет даты"
        assert entry.original_expression, (
            f"{entry.identifier}: не сохранено исходное выражение базы"
        )
        if entry.is_filled:
            assert entry.user_message, (
                f"{entry.identifier}: заполнена, но пользователю сказать нечего"
            )
        else:
            # Незаполненная правка обязана быть выключена — иначе она молча
            # подменит величину пустотой.
            assert not overrides.enabled or entry.expression is None
# --------------------------------------------------------------------------- #
# 11N-2. Автоматический набор фаз не уносит расчёт плотности
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("tdb", [NI_TDB, AL_TDB, FE_TDB], ids=["ni", "al", "fe"])
def test_automatic_phase_set_builds_after_the_detector(tdb: Path) -> None:
    """Автоматический набор фаз строится в pycalphad, а не валит расчёт.

    Раздел плотности на автоматическом наборе берёт все фазы базы (для
    никелевой это 99 штук) и до волны 11N отдавал их движку, минуя детектор
    волны 10. На никелевой базе с углеродом в составе ``Model`` пары
    ``BCC_B2``/``BCC_A2`` не строится, и ``Workspace`` падал с ``ValueError``
    ещё до расчёта равновесия — пользователь получал ``BACKEND_FAILED``.

    Строится только ``Workspace``: именно там был отказ, а равновесие на сотне
    фаз здесь считать незачем. Проверяются все три базы, потому что дефект —
    свойство описания пары фаз, а не конкретной базы.
    """

    from pycalphad import Workspace

    database = _database(tdb)
    components = list(CONTROL_COMPONENTS)
    # Ровно то, что даёт политика привязки на автоматическом наборе: все фазы
    # базы за вычетом C15_LAVES, который снимается до расчёта.
    phases = sorted(name for name in database.phases if name != "C15_LAVES")
    kept, removed = verified_physical.buildable_phases(database, components, phases)
    assert kept, "Детектор снял вообще всё — так быть не должно"

    conditions: dict[Any, float] = {v.N: 1.0, v.P: 101325.0, v.T: 1373.15}
    conditions.update({v.X(element): value for element, value in sorted(CONTROL_X.items())})
    Workspace(
        database=database,
        components=components,
        phases=list(kept),
        conditions=conditions,
    )

    if tdb == NI_TDB:
        assert "BCC_B2" in removed, (
            "На никелевой базе с углеродом BCC_B2 обязана сниматься: "
            "именно она и уносила расчёт"
        )


def test_excluded_phases_are_explained_in_the_result() -> None:
    """Снятые фазы объясняются пользователю, а не исчезают молча.

    Текст один на оба расчётных пути: ``ThermoGar_app.unbuildable_phase_note``
    берёт его из ``thermogar_verified_physical``. Если тексты разойдутся,
    пользователь получит разные объяснения одного и того же.
    """

    database = _database(NI_TDB)
    components = list(CONTROL_COMPONENTS)
    phases = sorted(name for name in database.phases if name != "C15_LAVES")
    _kept, removed = verified_physical.buildable_phases(database, components, phases)

    note = verified_physical.excluded_phases_note(removed)
    assert "BCC_B2" in note, note
    assert "BCC_A2" in note, "Не названа фаза, из-за которой сняли: " + note
    assert "не отказ расчёта" in note, (
        "Сообщение не говорит, что расчёт продолжается: " + note
    )
    assert verified_physical.excluded_phases_note({}) == ""


def test_backend_failure_message_names_the_error() -> None:
    """Отказ движка уходит пользователю текстом, а не одним именем класса.

    Волна 11K получила «BACKEND_FAILED: ValueError» и код ошибки — по такой
    строке нельзя ни понять, что случилось, ни разобрать обращение.
    """

    detail = verified_physical._backend_failure_detail(
        ValueError(
            "Order (BCC_B2) and disorder (BCC_A2) model must have no "
            "interstitial sublattice or a single matching one"
        )
    )
    assert detail.startswith("ValueError: ")
    assert "BCC_B2" in detail

    # Исключение без текста не должно давать пустую строку.
    assert verified_physical._backend_failure_detail(RuntimeError()) == "RuntimeError"
    # Длинный текст обрезается, но остаётся читаемым.
    long_detail = verified_physical._backend_failure_detail(ValueError("x" * 5000))
    assert len(long_detail) < 500 and long_detail.endswith("...")
def test_missing_elements_are_named_instead_of_a_pycalphad_error() -> None:
    """Состав с элементами, которых в базе нет, отвергается внятно.

    Алюминиевая база не описывает Mo, C, S и Nb. Отдай ей контрольный
    никелевый состав — и pycalphad уронит расчёт своим «Number of degrees of
    freedom is not zero» через одиннадцать секунд: условия по составу он
    примет, а лишние компоненты молча отбросит. Пользователю от такой строки
    толку нет, поэтому элементы называются до вызова движка.
    """

    database = _database(AL_TDB)
    absent = verified_physical._elements_absent_from(
        database, list(CONTROL_COMPONENTS)
    )
    assert set(absent) == {"MO", "C", "S", "NB"}, absent
    # Вакансия — не элемент состава и в список попадать не должна.
    assert "VA" not in absent

    database_ni = _database(NI_TDB)
    assert verified_physical._elements_absent_from(
        database_ni, list(CONTROL_COMPONENTS)
    ) == ()
# --------------------------------------------------------------------------- #
# 11N-3. Никель и молибден верны — сторож против «починки» верного
# --------------------------------------------------------------------------- #

# Оценка среднего линейного коэффициента расширения по таблице 1 статьи REF 14
# самой базы: Lu, Selleby, Sundman, Calphad 29 (2005) 68-89,
# doi:10.1016/j.calphad.2005.05.001. Интервал 25…1100 °C. Значения разобраны
# мастером по той же таблице, по которой в волне 11M восстановлен хром.
LU2005_MEAN_EXPANSION = {
    "NI": 17.14e-6,
    "MO": 5.30e-6,
}
# Окно сторожа. Двадцать процентов — заведомо шире, чем расхождение метода
# (никель 1,5 %, молибден 12 %), и заведомо уже, чем дефект переноса, каким он
# оказался у хрома: там отношение к оценке 3,2.
LU2005_TOLERANCE = 0.20


def _pure_element_expansion(
    physical_database: PhysicalDensityDatabase,
    phase: str,
    element: str,
) -> float:
    """Средний линейный коэффициент расширения чистого элемента, 25…1100 °C.

    Формула та же, что у матрицы и у хрома: ᾱ = ((ρ₂₅/ρ₁₁₀₀)^(1/3) − 1) / ΔT.
    """

    densities: list[float] = []
    for temperature_c in (25.0, 1100.0):
        value, coverage, warnings = physical_database.density_from_site_fractions(
            phase, [{element: 1.0}, {"VA": 1.0}], temperature_c + 273.15
        )
        assert value is not None, (
            f"{element} при {temperature_c} °C: плотность не посчитана {warnings}"
        )
        assert coverage > 0.999
        densities.append(float(value))
    cold, hot = densities
    return ((cold / hot) ** (1.0 / 3.0) - 1.0) / (1100.0 - 25.0)


@pytest.mark.parametrize(
    "phase, element",
    [("FCC_A1", "NI"), ("BCC_A2", "MO")],
)
def test_nickel_and_molybdenum_expansion_match_the_source(
    physical_db: PhysicalDensityDatabase,
    phase: str,
    element: str,
) -> None:
    """Никель и молибден воспроизводят оценку Lu 2005 — трогать их не надо.

    Тест сторожит в обе стороны. Он поймает будущую поломку переноса, как у
    хрома, и он же поймает попытку «поправить» то, что верно: никель
    расходится с оценкой на 1,5 %, молибден на 12 %, и никакая поправка тут
    не нужна.

    Про молибденовые 12 %. Расхождение направлено вверх и невелико; оно того
    же порядка, что разброс самих измерений расширения тугоплавких металлов
    до 1100 °C. У хрома отношение к оценке 3,2 — это другой класс величины,
    и потому чинили только его.
    """

    estimate = LU2005_MEAN_EXPANSION[element]
    coefficient = _pure_element_expansion(physical_db, phase, element)
    ratio = coefficient / estimate
    assert abs(ratio - 1.0) <= LU2005_TOLERANCE, (
        f"{element}: база даёт {coefficient * 1e6:.2f}e-6/K против оценки "
        f"Lu 2005 {estimate * 1e6:.2f}e-6/K, отношение {ratio:.2f}. "
        "Либо сломан перенос, либо кто-то наложил на элемент поправку."
    )


@pytest.mark.parametrize("element", ["NI", "MO"])
def test_nickel_and_molybdenum_are_not_overridden(element: str) -> None:
    """Ни одна поправка проекта не касается никеля и молибдена.

    Проверка отдельная от окна: окно в 20 % пропустило бы небольшую поправку,
    а её быть не должно вовсе — волна 11N-3 постановила, что оба элемента
    база описывает верно.
    """

    path = default_overrides_path()
    if not path.is_file():
        pytest.skip("Файла-дополнения нет.")
    overrides = load_physical_overrides(path)
    for entry in overrides.entries:
        assert element not in entry.identifier.upper().split("-"), (
            f"Появилась поправка на {element}: {entry.identifier}. "
            "Никель и молибден проверены по Lu 2005 и верны."
        )


@pytest.mark.parametrize(
    "phase, element",
    [("FCC_A1", "NI"), ("BCC_A2", "MO")],
)
def test_nickel_and_molybdenum_are_the_same_in_the_plain_database(
    physical_db: PhysicalDensityDatabase,
    physical_db_plain: PhysicalDensityDatabase,
    phase: str,
    element: str,
) -> None:
    """Наклон ρ(T) у никеля и молибдена одинаков с поправками и без них.

    Прямое доказательство, что перекрывающий слой их не трогает: у хрома те
    же два прогона расходятся втрое.
    """

    with_overrides = _pure_element_expansion(physical_db, phase, element)
    plain = _pure_element_expansion(physical_db_plain, phase, element)
    assert with_overrides == pytest.approx(plain, rel=1.0e-12), (
        f"{element}: {with_overrides * 1e6:.3f} против {plain * 1e6:.3f}e-6/K"
    )
# --------------------------------------------------------------------------- #
# 11N-4. Тесты не делят изменяемое состояние (BL-19)
# --------------------------------------------------------------------------- #


def test_each_test_gets_its_own_database() -> None:
    """`_database` отдаёт изолированную копию, а не общий объект.

    Проверяется именно то, чего не даёт ``copy.deepcopy`` самого pycalphad:
    ``phases``, ``symbols`` и ``species`` у копии свои. Без этого правка в
    одном тесте доходила бы до всех следующих, и порядок выполнения менял бы
    результат — это и есть `BL-19`.
    """

    first = _database(NI_TDB)
    second = _database(NI_TDB)
    assert first is not second
    for attribute in ("phases", "symbols", "species", "_parameters"):
        assert getattr(first, attribute) is not getattr(second, attribute), (
            f"{attribute} общий у двух копий базы"
        )
    assert first.phases["FCC_A1"] is not second.phases["FCC_A1"]

    # Правка в одной копии не видна в следующей.
    first.phases.pop("FCC_A1")
    first.symbols["ТОЛЬКО_ДЛЯ_ТЕСТА"] = 1.0
    third = _database(NI_TDB)
    assert "FCC_A1" in third.phases
    assert "ТОЛЬКО_ДЛЯ_ТЕСТА" not in third.symbols
    assert set(third.phases) == set(second.phases)


def test_physical_database_fixtures_are_per_test(
    physical_db: PhysicalDensityDatabase,
) -> None:
    """Физическая база тоже своя на каждый тест.

    Тест портит свой экземпляр намеренно. Если бы фикстура была модульной,
    следующий тест получил бы испорченную базу — и падал бы или проходил в
    зависимости от порядка.
    """

    physical_db.functions.clear()
    assert not physical_db.functions


# --------------------------------------------------------------------------- #
# 15-Ш (BL-39). Плотность элемента в правиле смеси — плотность самого элемента
# --------------------------------------------------------------------------- #

T_BL39 = 1073.15

# Элементы трёх баз, у которых до 15-Ш правило смеси брало запись-умолчание
# DP(FCC_A1,*), то есть плотность железа.
BL39_SUBSTITUTED = (
    "B", "C", "H", "HF", "LA", "N", "O", "P", "PD", "TA", "Y", "ZN", "ZR",
)
# Из них плотности нет в физической базе ни в каком виде.
BL39_ABSENT = ("H", "HF", "N", "O", "Y")


def _fe_matrix_density(physical_database: PhysicalDensityDatabase) -> float:
    value, _coverage, _warnings = physical_database.density_from_site_fractions(
        "FCC_A1", [{"FE": 1.0}, {"VA": 1.0}], T_BL39
    )
    assert value is not None
    return float(value)


def _mass_percent_to_mole(
    database: Any,
    mass_pct: dict[str, float],
    balance: str,
) -> dict[str, float]:
    masses = {
        name: float(database.refstates[name]["mass"])
        for name in (*mass_pct, balance)
    }
    moles = {name: value / masses[name] for name, value in mass_pct.items()}
    moles[balance] = (100.0 - sum(mass_pct.values())) / masses[balance]
    total = sum(moles.values())
    return {name: value / total for name, value in moles.items() if name != balance}


@pytest.mark.parametrize("element", BL39_SUBSTITUTED)
def test_element_density_is_not_the_iron_matrix(
    physical_db_plain: PhysicalDensityDatabase,
    element: str,
) -> None:
    """Ни один элемент не получает плотность железа из записи-умолчания."""

    iron = _fe_matrix_density(physical_db_plain)
    value = physical_db_plain.element_density(element, T_BL39)
    if element in BL39_ABSENT:
        assert value is None, f"{element}: плотность {value} взята не из базы"
    else:
        assert value is not None
        assert abs(value - iron) > 100.0, f"{element}: {value} — это плотность железа"


def test_carbon_density_is_the_diamond_model_of_the_base(
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """Углерод — по DP(DIAMOND_A4,C) = D0DIAM_C + DTCDIAM, с отметкой для графита."""

    expected = physical_db_plain.function_value(
        "D0DIAM_C", T_BL39
    ) + physical_db_plain.function_value("DTCDIAM", T_BL39)
    value = physical_db_plain.element_density("C", T_BL39)
    assert value == pytest.approx(expected, rel=1.0e-12)
    assert 3000.0 < value < 4000.0
    note = physical_db_plain.element_density_note("C", T_BL39)
    assert note is not None and "алмазной модели" in note and "графита" in note


def test_element_density_ignores_foreign_d0_records(
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """DP(DIAMOND_A4,B) задан через D0BCC_FE — бор берёт свою D0TETR_B."""

    assert physical_db_plain.element_density("B", T_BL39) == pytest.approx(
        physical_db_plain.function_value("D0TETR_B", T_BL39), rel=1.0e-12
    )
    note = physical_db_plain.element_density_note("B", T_BL39)
    assert note is not None and "D0TETR_B" in note and "298.15 K" in note
    # Азот: единственная запись DP(LIQUID,N) — это плотность алмаза.
    assert physical_db_plain.element_density("N", T_BL39) is None


@pytest.mark.parametrize("element", ("B", "LA", "P", "PD", "TA"))
def test_function_only_element_note_warns_about_volume_error(
    physical_db_plain: PhysicalDensityDatabase,
    element: str,
) -> None:
    """Элемент только с D0 при 298,15 K: текст предупреждает об ошибке объёма (15-Э)."""

    note = physical_db_plain.element_density_note(element, T_BL39)
    assert note is not None
    # 21-Ж, шаг 4: символ элемента на экране — La, Pd, Ta.
    symbol = element[:1] + element[1:].lower()
    assert note.startswith(f"Плотность элемента {symbol} в правиле смеси взята по функции D0")
    assert note.endswith(
        "при рабочих температурах ошибка объёма может превышать 10 %."
    )


@pytest.mark.parametrize("element", ("NI", "CR", "FE", "AL", "MO", "SI", "S"))
def test_matrix_elements_keep_their_fcc_record(
    physical_db_plain: PhysicalDensityDatabase,
    element: str,
) -> None:
    """Для элементов со своей записью FCC_A1 значение прежнее, отметки нет."""

    value, _coverage, _warnings = physical_db_plain.density_from_site_fractions(
        "FCC_A1", [{element: 1.0}, {"VA": 1.0}], T_BL39
    )
    assert physical_db_plain.element_density(element, T_BL39) == value
    assert physical_db_plain.element_density_note(element, T_BL39) is None


def test_graphite_volume_in_fe_1c_uses_carbon_density(
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """Fe-1C масс. %, 800 °C: объём графита — по плотности углерода, не железа."""

    database = _database(FE_TDB)
    components = ["FE", "C", "VA"]
    mole = _mass_percent_to_mole(database, {"C": 1.0}, "FE")
    result = calculate_physical_properties(
        database,
        _solve(database, components, ["FCC_A1", "GRAPHITE"], mole, T_BL39),
        ["FE", "C"],
        T_BL39,
        physical_db_plain,
    )
    rows = {row["Фаза"]: row for row in result.phase_table.to_dict("records")}
    assert "GRAPHITE" in rows, rows
    graphite = rows["GRAPHITE"]
    carbon = physical_db_plain.element_density("C", T_BL39)
    mass = float(database.refstates["C"]["mass"])
    assert graphite["Статус данных"] == "оценка по правилу смеси"
    assert graphite["Плотность фазы, кг/м³"] == pytest.approx(carbon, rel=1.0e-9)
    assert graphite["Молярный объём, см³/моль атомов"] == pytest.approx(
        mass / carbon * 1000.0, rel=1.0e-3
    )
    # Объёмная доля — из мольных долей и молярных объёмов обеих фаз; прежняя
    # плотность железа давала графиту Vm 1,557 см³/моль и φ 0,139 %.
    products = {
        name: row["Мольная доля, %"] * row["Молярный объём, см³/моль атомов"]
        for name, row in rows.items()
    }
    assert graphite["Объёмная доля, %"] == pytest.approx(
        100.0 * products["GRAPHITE"] / sum(products.values()), rel=1.0e-9
    )
    assert graphite["Молярный объём, см³/моль атомов"] > 3.0
    assert graphite["Объёмная доля, %"] > 0.25
    assert result.mole_coverage_pct == pytest.approx(100.0)
    assert any("алмазной модели" in text for text in result.warnings)
    assert any("алмазной модели" in text for text in result.element_density_notes)


def _ni_y_result(physical_database: PhysicalDensityDatabase) -> tuple[Any, Any]:
    database = _database(FE_TDB)
    components = ["NI", "Y", "VA"]
    equilibrium_result = _solve(
        database, components, ["FCC_A1", "NI5Y"], {"Y": 0.05}, T_BL39
    )
    return database, equilibrium_result


def test_phase_without_element_density_drops_out_of_coverage(
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """Иттрия в физической базе нет: Ni5Y не покрыт, плотность сплава не выдаётся."""

    database, equilibrium_result = _ni_y_result(physical_db_plain)
    result = calculate_physical_properties(
        database, equilibrium_result, ["NI", "Y"], T_BL39, physical_db_plain
    )
    phases = set(result.phase_table["Фаза"])
    assert "NI5Y" in phases, phases
    assert result.mole_coverage_pct < 99.0
    assert result.mass_coverage_pct < 99.0
    assert result.alloy_density_kg_m3 is None
    assert "NI5Y" in set(result.missing_table["Фаза"])
    assert (
        "Объём фазы NI5Y не оценён: в физической базе нет плотности элемента Y."
        in result.warnings
    )


def test_vrh_volumes_refuse_a_phase_without_element_density(
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """Для весов VRH такая фаза — DATA_UNAVAILABLE с тем же текстом."""

    import thermogar_verified_loaders as verified_loaders
    import thermogar_verified_properties as verified_properties

    database, equilibrium_result = _ni_y_result(physical_db_plain)
    names = np.asarray(equilibrium_result.Phase.values, dtype=str).ravel()
    amounts = np.asarray(equilibrium_result.NP.values, dtype=float).ravel()
    with pytest.raises(verified_loaders.VerifiedLoaderError) as caught:
        verified_properties._mixture_molar_volumes_cm3(
            database,
            physical_db_plain,
            equilibrium_result,
            ["NI", "Y", "VA"],
            T_BL39,
            ["NI5Y"],
            names,
            amounts,
            [],
        )
    assert caught.value.reason_code is verified_loaders.ReasonCode.DATA_UNAVAILABLE
    assert "Объём фазы NI5Y не оценён: в физической базе нет плотности элемента Y." in str(
        caught.value
    )


# --------------------------------------------------------------------------- #
# 18-А (BL-47). Эталонная фаза элемента из записи ELEMENT пробуется первой
# --------------------------------------------------------------------------- #

T_BL47 = 298.15


def test_reference_phases_come_from_element_records() -> None:
    """Эталонные фазы — из записей ELEMENT базы (refstates pycalphad)."""

    from thermogar_physical import element_reference_phases

    phases = element_reference_phases(Database(str(AL_TDB)))
    assert phases["FE"] == "BCC_A2"
    assert phases["SI"] == "DIA_A4"
    assert phases["MN"] == "BCC_A12"
    assert phases["AL"] == "FCC_A1"


@pytest.mark.parametrize(
    ("element", "reference", "phase", "expected"),
    (
        # До 18-А: Fe из DP(FCC_A1,FE:VA) = 8140, Si из DP(FCC_A1,SI:VA) = 3053.
        ("FE", "BCC_A2", "BCC_A2", 7876.16),
        ("SI", "DIA_A4", "DIAMOND_A4", 2329.38),
    ),
)
def test_reference_phase_is_tried_first(
    physical_db_plain: PhysicalDensityDatabase,
    element: str,
    reference: str,
    phase: str,
    expected: float,
) -> None:
    value, kind, label = physical_db_plain.element_density_model(
        element, T_BL47, reference
    )
    assert label.startswith(f"DP({phase},{element}")
    assert kind == "reference"
    assert value == pytest.approx(expected, abs=0.01)
    # Эталонная фаза — главный путь, как FCC_A1: примечания нет (решение 18-А).
    assert physical_db_plain.element_density_note(element, T_BL47, reference) is None


@pytest.mark.parametrize(
    ("element", "reference"),
    (("AL", "FCC_A1"), ("NI", "FCC_A1"), ("CU", "FCC_A1"), ("MN", "BCC_A12")),
)
def test_fcc_reference_or_phase_without_model_keeps_old_path(
    physical_db_plain: PhysicalDensityDatabase,
    element: str,
    reference: str,
) -> None:
    """Эталон FCC_A1 совпадает с прежним первым; BCC_A12 в PDB нет — прежний порядок."""

    assert physical_db_plain.element_density_model(
        element, T_BL47, reference
    ) == physical_db_plain.element_density_model(element, T_BL47)
    assert physical_db_plain.element_density_note(element, T_BL47, reference) is None


def test_reference_phase_does_not_take_a_foreign_d0(
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """BL-39 остаётся: DP(DIAMOND_A4,B) = D0BCC_FE+… бору не годится и как эталон."""

    for reference in ("DIAMOND_A4", "BETA_RHOMBO_B"):
        assert physical_db_plain.element_density(
            "B", T_BL47, reference
        ) == pytest.approx(physical_db_plain.function_value("D0TETR_B", T_BL47))


def test_mixture_uses_reference_phases(
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """Правило смеси Fe–Si берёт Fe из BCC_A2 и Si из DIAMOND_A4."""

    composition = {"FE": 0.5, "SI": 0.5}
    references = {"FE": "BCC_A2", "SI": "DIA_A4"}
    density, coverage, warnings = physical_db_plain.estimate_density_by_mixture(
        composition, T_BL47, None, references
    )
    mass_fe, mass_si = 0.5 * 55.845, 0.5 * 28.085
    fe = physical_db_plain.element_density("FE", T_BL47, "BCC_A2")
    si = physical_db_plain.element_density("SI", T_BL47, "DIA_A4")
    assert density == pytest.approx((mass_fe + mass_si) / (mass_fe / fe + mass_si / si))
    assert coverage == pytest.approx(1.0) and warnings == []
    assert physical_db_plain.mixture_element_notes(composition, T_BL47, references) == []


def test_zinc_reference_phase_drops_the_old_note(
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """Zn и раньше шёл из HCP_A3, но как обходной путь с примечанием; по эталону — без."""

    assert physical_db_plain.element_density_note("ZN", T_BL47) is not None
    assert physical_db_plain.element_density_note("ZN", T_BL47, "HCP_A3") is None


def test_si_diamond_a4_inherits_the_diamond_model(
    physical_db_plain: PhysicalDensityDatabase,
) -> None:
    """18-А (BL-48): SI_DIAMOND_A4 mc_al — по DP-модели DIAMOND_A4, вид inherited."""

    database = Database(str(AL_TDB))
    resolution = physical_db_plain.resolve_phase(database, "SI_DIAMOND_A4")
    assert resolution.physical_phase == "DIAMOND_A4"
    assert resolution.quality == "inherited"
    assert resolution.note == "Плотность оценена по модели DIAMOND_A4 той же структуры."
    value, coverage, _warnings = physical_db_plain.density_from_site_fractions(
        "DIAMOND_A4", [{"SI": 1.0}], T_BL47
    )
    assert coverage == pytest.approx(1.0)
    assert value == pytest.approx(
        physical_db_plain.element_density("SI", T_BL47, "DIA_A4"), rel=1.0e-12
    )


def test_vrh_prepare_accepts_element_notes_and_rejects_bad_ones() -> None:
    """Необязательное поле volume_notes: список строк или отказ RESULT_INVALID."""

    import thermogar_verified_loaders as verified_loaders
    import thermogar_verified_properties as verified_properties

    backend = {
        "mole_fractions": {"FCC_A1": 0.9, "GRAPHITE": 0.1},
        "molar_volumes_cm3": {"FCC_A1": 7.0, "GRAPHITE": 3.5},
        "volume_sources": {"FCC_A1": "direct", "GRAPHITE": "mixture"},
    }
    phases = ("FCC_A1", "GRAPHITE")
    assert verified_properties._validate_prepare_notes(backend) == []
    with_notes = dict(backend, volume_notes=["текст"])
    rows = verified_properties._validate_prepare_backend(with_notes, phases)
    assert [row.phase for row in rows] == list(phases)
    assert verified_properties._validate_prepare_notes(with_notes) == ["текст"]
    for bad in ("текст", [1], [""]):
        with pytest.raises(verified_loaders.VerifiedLoaderError) as caught:
            verified_properties._validate_prepare_notes(dict(backend, volume_notes=bad))
        assert caught.value.reason_code is verified_loaders.ReasonCode.RESULT_INVALID
    with pytest.raises(verified_loaders.VerifiedLoaderError):
        verified_properties._validate_prepare_backend(dict(backend, extra=[]), phases)
