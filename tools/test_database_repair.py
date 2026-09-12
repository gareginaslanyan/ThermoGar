#!/usr/bin/env python3
"""Правки разобранной базы (волна 10): физика, а не форма.

Байты TDB и PDB неприкосновенны, поэтому проверяется поведение кода загрузки.
Главный тест раздела подвижностей — числовой: коэффициент диффузии, который
отдаёт ``kawin``, должен совпадать с тем, что записано строкой ``MQ`` самой
базы, а не быть её квадратом.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -X utf8 -m pytest tools/test_database_repair.py -v
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from pycalphad import Database

import thermogar_database_repair as repair

GAS_CONSTANT = 8.31446261815324

DATABASES = {
    "ni": "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
    "al": "databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb",
    "fe": "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb",
}

# Выражения MQ(FCC_A1&X,NI:*) из mc_ni 2.036, Дж/моль. Это не справочные данные
# о материале, а буквальное содержимое строк базы: тест проверяет, что расчёт
# возвращает именно их, а не их квадрат.
NI_FCC_MQ = {
    "NI": lambda t: -287000.0 - 69.8 * t,
    "CR": lambda t: -287000.0 - 64.4 * t,
    "MO": lambda t: -267585.0 - 79.5 * t,
}

_PARSED: dict[str, Any] = {}


def _database(key: str) -> Any:
    """Разобранная база без правок — по одной на сессию, разбор дорогой."""

    if key not in _PARSED:
        path = ROOT / DATABASES[key]
        if not path.is_file():
            pytest.skip(f"База {key} не найдена: {path}")
        _PARSED[key] = Database(str(path))
    return _PARSED[key]


def _fresh(key: str) -> Any:
    """Свежая копия базы: правка меняет объект на месте."""

    import pickle

    return pickle.loads(pickle.dumps(_database(key), protocol=pickle.HIGHEST_PROTOCOL))


# --------------------------------------------------------------------------- #
# Умолчания подвижности
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("key", sorted(DATABASES))
def test_duplicated_defaults_exist_before_repair(key: str) -> None:
    """Дефект есть во всех трёх релизных базах — иначе правка бессмысленна."""

    database = _fresh(key)
    duplicated = repair.duplicated_default_keys(database)
    assert duplicated, (
        f"В базе {key} не найдено ни одного умолчания подвижности, дублирующего "
        "явную строку: проверьте, не изменился ли формат базы"
    )


@pytest.mark.parametrize("key", sorted(DATABASES))
def test_default_rows_are_materialised_not_just_deleted(key: str) -> None:
    """Умолчание разворачивается в явные строки, а не просто выбрасывается.

    Строка ``MQ(<фаза>&<элемент>,*)`` в TDB значит «значение для любого
    составляющего, у которого нет своей строки». Просто удалить её нельзя: в
    ``mc_ni`` она была единственным источником подвижности молибдена в хроме, и
    без неё сумма Редлиха — Кистера теряла вклад, а коэффициент диффузии при
    составе сплава улетал на четыре порядка вверх. Поэтому умолчание
    материализуется для «непокрытых» составляющих, и лишь затем убирается.
    """

    database = _fresh(key)
    before_defaults = len(repair.degenerate_default_records(database))
    assert before_defaults > 0

    report = repair.repair_mobility_defaults(database, database_label=key)

    assert not repair.duplicated_default_keys(database), (
        "После правки остались умолчания, дублирующие явную строку"
    )
    assert report.removed > 0
    assert report.materialised > report.removed, (
        "Умолчания удалены, но не развёрнуты в явные строки"
    )
    # Каждое снятое умолчание оставило после себя хотя бы одну явную строку.
    remaining = len(repair.degenerate_default_records(database))
    assert remaining == before_defaults - report.removed


@pytest.mark.parametrize("key", sorted(DATABASES))
def test_every_constituent_has_a_mobility_row_after_repair(key: str) -> None:
    """После правки у каждого составляющего есть своя строка подвижности.

    Прямая проверка того, что материализация ничего не потеряла: для фазы
    FCC_A1 и каждого диффундирующего элемента, у которого было умолчание,
    в таблице обязаны найтись строки для всех составляющих первой подрешётки.
    """

    database = _fresh(key)
    before = {
        (
            str(record.get("phase_name")),
            str(record.get("parameter_type")),
            str(getattr(record.get("diffusing_species"), "name", "")).upper(),
        )
        for record in repair.degenerate_default_records(database)
    }
    repair.repair_mobility_defaults(database, database_label=key)

    table = database._parameters.table(  # noqa: SLF001
        database._parameters.default_table_name  # noqa: SLF001
    )
    rows = table.all()
    for phase_name, parameter_type, species in sorted(before):
        phase = database.phases.get(phase_name)
        if phase is None:
            continue
        covered: set[str] = set()
        for record in rows:
            if str(record.get("phase_name")) != phase_name:
                continue
            if str(record.get("parameter_type")) != parameter_type:
                continue
            name = str(getattr(record.get("diffusing_species"), "name", "")).upper()
            if name != species:
                continue
            array = record.get("constituent_array")
            try:
                if len(array[0]) == 1:
                    covered.add(str(array[0][0]))
            except Exception:
                continue
        constituents = {str(item) for item in phase.constituents[0]}
        missing = constituents - covered
        assert not missing, (
            f"{phase_name}/{parameter_type}/{species}: без строки остались "
            + ", ".join(sorted(missing))
        )


@pytest.mark.parametrize("key", sorted(DATABASES))
def test_repair_is_idempotent(key: str) -> None:
    """Повторный вызов ничего не меняет — путь загрузки зовёт правку не раз."""

    database = _fresh(key)
    first = repair.repair_mobility_defaults(database)
    second = repair.repair_mobility_defaults(database)
    assert first.removed > 0
    assert second.removed == 0
    assert second.already_repaired is True


def test_repair_keeps_thermodynamic_parameters_untouched() -> None:
    """Правка не трогает ничего, кроме кинетики: G, L, TC, BMAGN и прочее."""

    database = _fresh("ni")
    table = database._parameters.table(  # noqa: SLF001
        database._parameters.default_table_name  # noqa: SLF001
    )
    before = sum(
        1
        for record in table.all()
        if str(record.get("parameter_type", "")) not in repair.KINETIC_PARAMETER_TYPES
    )
    repair.repair_mobility_defaults(database)
    after = sum(
        1
        for record in table.all()
        if str(record.get("parameter_type", "")) not in repair.KINETIC_PARAMETER_TYPES
    )
    assert before == after, "Правка удалила термодинамические параметры"


# --------------------------------------------------------------------------- #
# Физика: коэффициент диффузии
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("temperature_k", [1423.15, 1473.15])
def test_tracer_diffusivity_matches_database_after_repair(temperature_k: float) -> None:
    """D из kawin равен exp(MQ/RT) базы, а не его квадрату.

    Это и есть физическая проверка правки: до неё отношение было равно самому
    D (то есть возвращался D²), после — единице.
    """

    pytest.importorskip("kawin")
    from kawin.thermo import GeneralThermodynamics

    database = _fresh("ni")
    repair.repair_mobility_defaults(database)
    thermodynamics = GeneralThermodynamics(database, ["NI", "CR", "MO"], ["FCC_A1"])
    # Предел бесконечного разбавления: там значение задаётся одной строкой базы
    # и сравнение не зависит от параметров взаимодействия.
    values = np.asarray(
        thermodynamics.getTracerDiffusivity([1.0e-6, 1.0e-6], temperature_k,
                                            phase="FCC_A1"),
        dtype=float,
    ).ravel()

    for index, (element, expression) in enumerate(NI_FCC_MQ.items()):
        expected = math.exp(expression(temperature_k) / (GAS_CONSTANT * temperature_k))
        ratio = float(values[index]) / expected
        assert ratio == pytest.approx(1.0, rel=1.0e-3), (
            f"{element} при {temperature_k} K: D = {values[index]:.4e}, "
            f"в базе {expected:.4e}, отношение {ratio:.4g}"
        )


def test_tracer_diffusivity_is_squared_without_repair() -> None:
    """Без правки D равен квадрату записанного в базе — фиксация дефекта.

    Тест держит причину, ради которой правка существует: если однажды
    ``pycalphad``/``kawin`` начнут понимать умолчание сами, он упадёт, и правку
    можно будет снять.
    """

    pytest.importorskip("kawin")
    from kawin.thermo import GeneralThermodynamics

    database = _fresh("ni")
    assert not repair.mobility_repair_applied(database)
    thermodynamics = GeneralThermodynamics(database, ["NI", "CR", "MO"], ["FCC_A1"])
    temperature_k = 1423.15
    values = np.asarray(
        thermodynamics.getTracerDiffusivity([1.0e-6, 1.0e-6], temperature_k,
                                            phase="FCC_A1"),
        dtype=float,
    ).ravel()
    expected = math.exp(NI_FCC_MQ["NI"](temperature_k) / (GAS_CONSTANT * temperature_k))
    assert float(values[0]) == pytest.approx(expected**2, rel=1.0e-3)


def test_diffusion_actually_homogenises_after_repair() -> None:
    """Профиль пары действительно выравнивается — на дефектной базе он стоял.

    Прямая проверка того, ради чего правка делалась: за время, сравнимое с
    L²/D, размах по молибдену должен заметно упасть. До правки он оставался
    равным 1,000 даже за час модельного времени.
    """

    pytest.importorskip("kawin")
    from kawin.diffusion import SinglePhaseModel
    from kawin.diffusion.mesh import Cartesian1D, ProfileBuilder, StepProfile1D
    from kawin.solver import explicitEulerIterator
    from kawin.thermo import GeneralThermodynamics

    database = _fresh("ni")
    repair.repair_mobility_defaults(database)

    elements = ["NI", "CR", "MO"]
    independent = elements[1:]
    length_m = 2.0e-6
    temperature_k = 1473.15

    thermodynamics = GeneralThermodynamics(database, elements, ["FCC_A1"])
    diffusivity = float(
        np.asarray(
            thermodynamics.getTracerDiffusivity([0.28, 0.09], temperature_k,
                                                phase="FCC_A1"),
            dtype=float,
        ).ravel()[2]
    )
    # Две постоянных релаксации первой моды: для прямоугольного профиля размах
    # падает как (4/π)·exp(−t/τ), то есть ожидается около 0,17 — далеко и от
    # единицы (дефектная база), и от порога теста.
    time_s = 2.0 * length_m**2 / (math.pi**2 * diffusivity)

    mesh = Cartesian1D(independent, [0.0, length_m], 30)
    builder = ProfileBuilder()
    builder.addBuildStep(
        StepProfile1D(length_m / 2.0, [0.2569, 0.0699], [0.3084, 0.1146]), independent
    )
    mesh.setResponseProfile(builder)
    model = SinglePhaseModel(
        mesh, elements, ["FCC_A1"], thermodynamics=thermodynamics,
        temperature=temperature_k, record=False,
    )
    initial = np.asarray(model.getCompositions(), dtype=float).copy()
    model.solve(time_s, iterator=explicitEulerIterator, verbose=False,
                vIt=100000, minDtFrac=1e-10)
    final = np.asarray(model.getCompositions(), dtype=float)

    index = elements.index("MO")
    span_0 = float(initial[:, index].max() - initial[:, index].min())
    span_t = float(final[:, index].max() - final[:, index].min())
    assert span_0 > 0.0
    assert span_t / span_0 < 0.35, (
        f"Профиль не выровнялся: остаточный размах {span_t / span_0:.3f} "
        "от исходного (на дефектной базе было 1.000)"
    )


# --------------------------------------------------------------------------- #
# Путь загрузки
# --------------------------------------------------------------------------- #


def test_load_path_applies_repair() -> None:
    """База, полученная штатным загрузчиком движка, уже починена."""

    from thermogar_parallel import file_sha256, load_database

    path = ROOT / DATABASES["ni"]
    if not path.is_file():
        pytest.skip(f"Нет базы: {path}")
    database = load_database(path, file_sha256(path))
    assert repair.mobility_repair_applied(database), (
        "Загрузчик движка вернул базу без правки подвижностей"
    )
    assert not repair.duplicated_default_keys(database)


def test_cache_format_version_bumped() -> None:
    """Записи кэша, сделанные до правки, не должны переиспользоваться."""

    import thermogar_db_cache as db_cache

    assert db_cache.CACHE_FORMAT_VERSION >= 2


# --------------------------------------------------------------------------- #
# Быстрый набор фаз
# --------------------------------------------------------------------------- #

# Составы, на которых проверяется полнота быстрых наборов: по одному «рабочему»
# сплаву на базу. Ni-сплав — ХН62М(Sc)-ВИ из волны 9, ровно тот, на котором
# набор терял Ni2Cr.
PRESET_CASES = {
    "ni": {
        "components": ("NI", "CR", "MO", "C", "SI", "MN", "S", "NB", "AL", "TI", "FE", "VA"),
        "balance": "NI",
        "mass_percent": {
            "C": 0.005, "SI": 0.10, "MN": 0.50, "S": 0.020, "CR": 23.5,
            "MO": 13.0, "NB": 0.06, "AL": 0.25, "TI": 0.10, "FE": 0.50,
        },
        "temperatures_c": (400.0, 700.0, 1340.0),
    },
    "al": {
        "components": ("AL", "CU", "MG", "VA"),
        "balance": "AL",
        "mass_percent": {"CU": 4.0, "MG": 1.0},
        "temperatures_c": (200.0, 400.0, 500.0),
    },
    "fe": {
        "components": ("FE", "C", "CR", "NI", "VA"),
        "balance": "FE",
        "mass_percent": {"C": 0.2, "CR": 11.5, "NI": 0.7},
        "temperatures_c": (600.0, 700.0, 900.0),
    },
}


def _mole_fractions(database: Any, case: dict[str, Any]) -> dict[str, float]:
    from thermogar_equilibrium_core import mass_to_mole_fractions

    percent = dict(case["mass_percent"])
    percent[case["balance"]] = 100.0 - sum(percent.values())
    names = sorted(percent)
    mass = tuple((element, percent[element] / 100.0) for element in names)
    masses = tuple(
        (element, float(database.refstates[element]["mass"])) for element in names
    )
    return dict(mass_to_mole_fractions(mass, masses))


def _stable_phases(key: str, case: dict[str, Any]) -> set[str]:
    """Фазы, устойчивые на этом сплаве хотя бы при одной температуре."""

    from pycalphad import equilibrium, variables as v
    from pycalphad.core.utils import filter_phases, unpack_species

    database = _fresh(key)
    repair.repair_database(database)
    components = list(case["components"])
    phases = sorted(filter_phases(database, unpack_species(database, components)))
    if key == "fe":
        phases = [name for name in phases if name != "C15_LAVES"]
    phases, _removed = repair.drop_broken_order_disorder(database, components, phases)

    mole = _mole_fractions(database, case)
    seen: set[str] = set()
    for temperature_c in case["temperatures_c"]:
        conditions: dict[Any, float] = {
            v.N: 1.0, v.P: 101325.0, v.T: temperature_c + 273.15,
        }
        conditions.update(
            {v.X(element): value for element, value in sorted(mole.items())
             if element != case["balance"]}
        )
        result = equilibrium(
            database, components, phases, conditions, calc_opts={"pdens": 100}
        )
        names = np.asarray(result.Phase.values, dtype=str).ravel()
        amounts = np.asarray(result.NP.values, dtype=float).ravel()
        for name, amount in zip(names, amounts):
            if name and np.isfinite(amount) and float(amount) > 1.0e-6:
                seen.add(str(name))
    return seen


@pytest.mark.parametrize("key", sorted(PRESET_CASES))
def test_fast_preset_keeps_every_stable_phase(key: str) -> None:
    """Быстрый набор не теряет ни одной фазы, устойчивой на рабочем сплаве.

    Это физическая проверка, а не сверка списков: устойчивые фазы берутся из
    равновесий на полном наборе. Именно она ловит пропажу NI2CR (мольная доля
    0,80 при 400 °C) и TIS в никелевом наборе.
    """

    from thermogar_release_policy import load_phase_presets

    presets = load_phase_presets(ROOT)
    preset = {str(name).upper() for name in presets[key]}
    stable = _stable_phases(key, PRESET_CASES[key])
    assert stable, "Равновесие не дало ни одной фазы: проверьте состав"
    missing = sorted(stable - preset)
    assert not missing, (
        f"Быстрый набор базы {key} теряет устойчивые фазы: {', '.join(missing)}"
    )


def test_ni_preset_contains_ordering_and_tcp_family() -> None:
    """Ni2Cr и семья TCP присутствуют целиком.

    Ni2Cr — механизм охрупчивания при 300–500 °C, он обязан быть в наборе.
    Из TCP-фаз в наборе должны быть все, что описаны базой, иначе быстрый режим
    отвечает на вопрос «есть ли TCP» неполно.
    """

    from thermogar_release_policy import load_phase_presets

    preset = {str(name).upper() for name in load_phase_presets(ROOT)["ni"]}
    required = {
        "NI2CR",
        "SIGMA", "MU_PHASE", "P_PHASE", "CHI_A12", "R_PHASE", "D_NIMO", "LAVES",
    }
    assert required <= preset, f"В наборе нет: {sorted(required - preset)}"


# --------------------------------------------------------------------------- #
# Пары «порядок/беспорядок»
# --------------------------------------------------------------------------- #


def test_bcc_b2_detected_only_with_carbon() -> None:
    """BCC_B2 в mc_ni нельзя построить с углеродом и можно — без него."""

    database = _fresh("ni")
    with_carbon = repair.broken_order_disorder_phases(
        database, ["NI", "CR", "MO", "C", "AL", "TI", "VA"]
    )
    without_carbon = repair.broken_order_disorder_phases(
        database, ["NI", "CR", "MO", "AL", "TI", "VA"]
    )
    assert "BCC_B2" in with_carbon
    assert without_carbon == {}
    assert "C" in with_carbon["BCC_B2"].interstitial_of_disordered


def test_steel_bcc_b2_stays_with_carbon() -> None:
    """У стальной базы пара согласована: матричную фазу снимать нельзя."""

    database = _fresh("fe")
    broken = repair.broken_order_disorder_phases(
        database, ["FE", "C", "CR", "NI", "VA"]
    )
    assert broken == {}, (
        "Для стальной базы BCC_B2 — матрица, её исключение сломало бы раздел"
    )


def test_model_build_matches_detector() -> None:
    """Детектор согласован с pycalphad: что он снял — то и не строится.

    Проверяется с обеих сторон: помеченная фаза действительно поднимает
    ValueError, а оставшиеся строятся молча.
    """

    from pycalphad import Model
    from pycalphad.core.utils import filter_phases, unpack_species

    database = _fresh("ni")
    components = ["NI", "CR", "MO", "C", "AL", "TI", "VA"]
    phases = sorted(filter_phases(database, unpack_species(database, components)))
    kept, removed = repair.drop_broken_order_disorder(database, components, phases)

    assert removed, "Детектор ничего не снял, хотя углерод в системе есть"
    for name in removed:
        with pytest.raises(ValueError):
            Model(database, components, name)
    for name in kept:
        Model(database, components, name)


def test_equilibrium_runs_on_carbon_bearing_nickel_alloy() -> None:
    """Расчёт с «всеми фазами базы» на Ni-сплаве с углеродом больше не падает.

    До правки этот вызов заканчивался ValueError из ``Model`` ещё до решения.
    """

    from pycalphad import equilibrium, variables as v
    from pycalphad.core.utils import filter_phases, unpack_species

    database = _fresh("ni")
    repair.repair_database(database)
    case = PRESET_CASES["ni"]
    components = list(case["components"])
    phases = sorted(filter_phases(database, unpack_species(database, components)))
    phases, removed = repair.drop_broken_order_disorder(database, components, phases)
    assert "BCC_B2" in removed

    mole = _mole_fractions(database, case)
    conditions: dict[Any, float] = {v.N: 1.0, v.P: 101325.0, v.T: 1173.15}
    conditions.update(
        {v.X(element): value for element, value in sorted(mole.items())
         if element != "NI"}
    )
    result = equilibrium(
        database, components, phases, conditions, calc_opts={"pdens": 100}
    )
    amounts = np.asarray(result.NP.values, dtype=float).ravel()
    total = float(np.nansum(amounts[np.isfinite(amounts)]))
    assert total == pytest.approx(1.0, abs=1.0e-5), (
        f"Сумма долей фаз {total}, равновесие не решено"
    )


# --------------------------------------------------------------------------- #
# A3: приёмочные требования постановки волны 10
# --------------------------------------------------------------------------- #


def test_diffusivity_order_of_magnitude_at_1200c() -> None:
    """D(Mo) в FCC-Ni при 1200 °C лежит в 1e-15…1e-13 м²/с.

    Проверка разумности порядка, а не точного значения: литературный ориентир
    для молибдена в никеле при 1200 °C — около 1e-14 м²/с. До дедупликации
    здесь было 5e-28.
    """

    pytest.importorskip("kawin")
    from kawin.thermo import GeneralThermodynamics

    database = _fresh("ni")
    repair.repair_mobility_defaults(database)
    thermodynamics = GeneralThermodynamics(database, ["NI", "CR", "MO"], ["FCC_A1"])
    value = float(
        np.asarray(
            thermodynamics.getTracerDiffusivity([1.0e-6, 1.0e-6], 1473.15,
                                                phase="FCC_A1"),
            dtype=float,
        ).ravel()[2]
    )
    assert 1.0e-15 <= value <= 1.0e-13, (
        f"D(Mo) при 1200 °C = {value:.3e} м²/с вне разумного диапазона"
    )


def test_run_diffusion_changes_composition() -> None:
    """Штатный ``run_diffusion`` действительно выравнивает пару.

    Прежние тесты раздела проверяли только баланс массы и форму профиля, и
    поэтому дефект пропустили: профиль стоял на месте, а баланс сходился.
    Здесь утверждение по существу — перепад по молибдену падает не менее чем
    на 40 % за время порядка L²/D.
    """

    pytest.importorskip("kawin")
    from thermogar_diffusion import run_diffusion
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    path = ROOT / DATABASES["ni"]
    if not path.is_file():
        pytest.skip(f"Нет базы: {path}")

    length_um = 2.0
    temperature_c = 1200.0
    # Время оценивается по первой моде: τ = L²/π²D. Коэффициент берётся из той
    # же базы, поэтому тест не зависит от справочных чисел.
    from kawin.thermo import GeneralThermodynamics

    database = _fresh("ni")
    repair.repair_mobility_defaults(database)
    thermodynamics = GeneralThermodynamics(database, ["NI", "CR", "MO"], ["FCC_A1"])
    diffusivity = float(
        np.asarray(
            thermodynamics.getTracerDiffusivity([0.28, 0.09], temperature_c + 273.15,
                                                phase="FCC_A1"),
            dtype=float,
        ).ravel()[2]
    )
    time_h = (length_um * 1.0e-6) ** 2 / (math.pi**2 * diffusivity) / 3600.0

    result = run_diffusion(
        db=object(),
        database_key="ni",
        database_path=path,
        database_label=RELEASE_DATABASE_LABELS.get("ni", "mc_ni"),
        balance="NI",
        units="wt",
        left_text="CR=22.42, MO=11.26",
        right_text="CR=26.21, MO=18.26",
        temperature_c=temperature_c,
        time_h=max(time_h, 1.0e-6),
        length_um=length_um,
        interface_percent=50.0,
        nodes=30,
        phases=["FCC_A1"],
        model_kind="single",
        input_provenance="Приёмочный тест волны 10, пункт A3; research-only",
        input_confirmation=True,
    )
    index = list(result.elements).index("MO")
    initial = np.asarray(result.initial_wt, dtype=float)[:, index]
    final = np.asarray(result.final_wt, dtype=float)[:, index]
    span_0 = float(initial.max() - initial.min())
    span_t = float(final.max() - final.min())
    assert span_0 > 0.0
    drop = 1.0 - span_t / span_0
    assert drop >= 0.4, (
        f"Перепад по Mo упал лишь на {100 * drop:.1f} % "
        "(на дефектной базе он не менялся вовсе)"
    )


def test_dedup_report_counts_and_log_line() -> None:
    """Отчёт дедупликации содержит числа и строку для лога и паспорта базы."""

    database = _fresh("ni")
    report = repair.repair_mobility_defaults(database, database_label="mc_ni")
    assert report.removed > 0
    assert report.kept_as_only_source > 0
    line = report.log_line()
    assert "дедупликация подвижностей" in line
    assert "mc_ni" in line
    assert str(report.removed) in line


def test_dedup_keeps_parameters_with_different_expressions() -> None:
    """Различающиеся выражения не считаются дублем и не отбрасываются."""

    database = _fresh("ni")
    report = repair.repair_mobility_defaults(database, database_label="mc_ni")
    assert report.kept_as_different_expression > 0, (
        "Ни одного места с различающимися выражениями не найдено: "
        "проверьте, работает ли символьное сравнение"
    )
    assert not set(report.suspicious_keys) & set(report.removed_keys)


def test_excluded_phase_metadata_has_reason() -> None:
    """Метаданные расчёта содержат непустой список исключённых фаз с причиной."""

    database = _fresh("ni")
    components = ["NI", "CR", "MO", "C", "AL", "TI", "VA"]
    from pycalphad.core.utils import filter_phases, unpack_species

    phases = sorted(filter_phases(database, unpack_species(database, components)))
    _kept, removed = repair.drop_broken_order_disorder(database, components, phases)
    assert removed, "Список исключённых фаз пуст"
    for name, item in removed.items():
        assert item.reason, f"У фазы {name} нет причины исключения"
        assert item.disordered_phase
    note = repair.excluded_phases_note(removed)
    assert "исключены" in note and "BCC_B2" in note


def test_balance_is_measured_on_the_conserved_quantity() -> None:
    """Невязка баланса считается по u-долям, а не по мольным (волна 11L).

    Решатели ``kawin`` работают в объёмно-фиксированной системе отсчёта и
    хранят состояние в u-долях ``u_k = x_k / сумма замещающих``: внедрённый
    углерод сидит в междоузлиях и узлов решётки не создаёт. При закрытых
    границах конечно-объёмная схема сохраняет среднюю u-долю. Средняя мольная
    доля при этом смещается, потому что знаменатель меняется от узла к узлу, —
    и на стальной паре ``C=0,1…0,3 / CR=8…14`` смещение доходит до 7,2e-6, то
    есть в семь раз выше допуска 1e-6.

    Тест закрепляет обе половины: по u-долям расчёт сходится, по мольным на
    той же паре — нет. Если кто-то вернёт проверку на мольные доли, тест
    упадёт и назовёт причину.
    """

    pytest.importorskip("kawin")
    import thermogar_diffusion as diffusion
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    path = ROOT / DATABASES["fe"]
    if not path.is_file():
        pytest.skip(f"Нет базы: {path}")

    result = diffusion.run_diffusion(
        db=object(),
        database_key="fe",
        database_path=path,
        database_label=RELEASE_DATABASE_LABELS.get("fe", ""),
        balance="FE",
        units="wt",
        left_text="C=0.1, CR=8",
        right_text="C=0.3, CR=14",
        temperature_c=900.0,
        time_h=0.001,
        length_um=100.0,
        interface_percent=50.0,
        nodes=20,
        phases=["FCC_A1"],
        model_kind="single",
        input_provenance="Приёмочный тест волны 11L, пункт 11L-1; research-only",
        input_confirmation=True,
    )

    assert diffusion._has_interstitials_in(result.elements), (
        "В паре нет внедрённого элемента — тест проверяет не то, что задумано"
    )
    assert result.max_balance_error <= 1e-6, result.max_balance_error

    mole_error = float(
        np.max(
            np.abs(
                np.mean(result.final_at, axis=0) - np.mean(result.initial_at, axis=0)
            )
        )
    )
    assert mole_error > 1e-6, (
        "Средняя мольная доля на стальной паре сохранилась — тогда переход на "
        "u-доли ничем не подкреплён, и разницу надо объяснять заново"
    )


def test_u_fraction_balance_equals_mole_balance_without_interstitials() -> None:
    """Без внедрённых элементов u ≡ x, и число невязки не меняется.

    Переход на u-доли не должен ослаблять проверку на никеле и алюминии: там
    сумма замещающих равна единице в каждом узле, поэтому обе величины
    совпадают побитно.
    """

    import thermogar_diffusion as diffusion

    elements = ["NI", "AL", "CR"]
    profile = np.array(
        [
            [0.724, 0.058, 0.218],
            [0.700, 0.070, 0.230],
            [0.650, 0.100, 0.250],
        ]
    )
    assert not diffusion._has_interstitials_in(elements)
    assert np.array_equal(diffusion._u_fractions(elements, profile), profile)

    with_carbon = ["FE", "C", "CR"]
    assert diffusion._has_interstitials_in(with_carbon)
    u_frac = diffusion._u_fractions(with_carbon, profile)
    assert not np.allclose(u_frac, profile), (
        "С углеродом u-доли обязаны отличаться от мольных"
    )
    # Сумма замещающих в u-долях равна единице по построению.
    assert np.allclose(u_frac[:, 0] + u_frac[:, 2], 1.0)
