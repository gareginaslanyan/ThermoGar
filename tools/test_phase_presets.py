#!/usr/bin/env python3
"""Быстрые наборы фаз (волна 5A): набор не должен менять устойчивые фазы.

Проверяется ровно то, ради чего наборы вводились: на эталонных точках
`tools/backend_reference.md` (Ni–15Al 700 °C, Al–4Cu–1Mg 500 °C,
Fe–0.2C–11.5Cr–0.7Ni 700 °C) режимы «все фазы базы» и «быстрый набор»
дают один и тот же список устойчивых фаз и те же доли. Если в режиме
«все» устойчива фаза, которой нет в наборе, тест падает — и такую фазу
нужно добавить в `configs/phase_presets.json`.

Дополнительно проверяются схема файла наборов, существование каждого
имени фазы в соответствующей TDB и правило продукта: `C15_LAVES` для Fe
исключается в обоих режимах, то есть быстрый набор применяется до
фильтра C15 и фильтр C15 остаётся последним словом.

Запуск:

    python -m pytest tools/test_phase_presets.py -m "not slow"
    python -m pytest tools/test_phase_presets.py -m slow
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from pycalphad import Database, equilibrium, variables as v
from pycalphad.core.utils import filter_phases, unpack_species

from thermogar_release_policy import (
    FE_EXCLUDED_PHASES,
    PHASE_MODE_ALL,
    PHASE_MODE_FAST,
    PHASE_PRESETS_RELATIVE_PATH,
    RELEASE_DATABASE_KEYS,
    PhasePresetError,
    effective_release_phases,
    load_phase_presets,
    phase_mode_note,
    preset_phases,
)

DB_KEYS = ("ni", "al", "fe")

# Фазы Al-базы, без которых быстрый набор перестаёт повторять режим «все
# фазы» на полнодиапазонных диаграммах: они устойчивы на сетке бинарной
# AL–CU (2–50 ат.% Cu, 600–1100 °C) и тройного сечения AL–CU–MG при 773 K
# по всему треугольнику. Проверено прямым перебором равновесий волны 5A;
# список удерживает их в наборе, если кто-то решит его сократить.
AL_FULL_RANGE_PHASES = frozenset(
    {
        "AL2CU3_D",
        "AL9CU11_ZP",
        "ALCU_EPS",
        "ALCU_ETH",
        "ALCU_ETL",
        "ALCU_G_P",
        "CL_FCC",
        "CL_MGX",
        "LAVES_C15",
        "LAVES_C36",
    }
)
DEFAULT_TIMEOUT = 300
SLOW_TIMEOUT = 900


@dataclass(frozen=True)
class Case:
    """Эталонный состав базы — тот же, что в backend_reference.md."""

    key: str
    relative_path: str
    balance: str
    components: tuple[str, ...]
    composition_pct: dict[str, float]
    units: str
    temperature_c: float
    scan_temperatures_c: tuple[float, ...]
    scan_element: str
    scan_mole_fractions: tuple[float, ...]


CASES: dict[str, Case] = {
    "ni": Case(
        key="ni",
        relative_path=(
            "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"
        ),
        balance="NI",
        components=("NI", "AL", "VA"),
        composition_pct={"AL": 15.0},
        units="at",
        temperature_c=700.0,
        scan_temperatures_c=(600.0, 700.0, 800.0, 900.0, 1000.0),
        scan_element="AL",
        scan_mole_fractions=(0.05, 0.10, 0.15, 0.20, 0.25),
    ),
    "al": Case(
        key="al",
        relative_path=(
            "databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb"
        ),
        balance="AL",
        components=("AL", "CU", "MG", "VA"),
        composition_pct={"CU": 4.0, "MG": 1.0},
        units="wt",
        temperature_c=500.0,
        scan_temperatures_c=(300.0, 400.0, 500.0, 550.0, 600.0),
        scan_element="CU",
        scan_mole_fractions=(0.005, 0.010, 0.017, 0.024, 0.030),
    ),
    "fe": Case(
        key="fe",
        relative_path=(
            "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb"
        ),
        balance="FE",
        components=("FE", "C", "CR", "NI", "VA"),
        composition_pct={"C": 0.2, "CR": 11.5, "NI": 0.7},
        units="wt",
        temperature_c=700.0,
        scan_temperatures_c=(500.0, 600.0, 700.0, 800.0, 900.0),
        scan_element="C",
        scan_mole_fractions=(0.002, 0.005, 0.009, 0.015, 0.020),
    ),
}

_DB_CACHE: dict[str, Database] = {}


def load_case_database(case: Case) -> Database:
    """Разбор TDB стоит 3–7 с, поэтому база читается один раз на сессию."""

    path = ROOT / case.relative_path
    if not path.is_file():
        pytest.skip(f"База {case.key} не найдена: {path}")
    if case.key not in _DB_CACHE:
        _DB_CACHE[case.key] = Database(str(path))
    return _DB_CACHE[case.key]


def mode_phases(
    db: Database,
    case: Case,
    presets: Any,
    phase_mode: str,
    components: tuple[str, ...] | None = None,
) -> list[str]:
    """Список фаз режима — тот же порядок действий, что в приложении."""

    active = list(components or case.components)
    phases = sorted(filter_phases(db, unpack_species(db, active)))
    if phase_mode == PHASE_MODE_FAST:
        phases = preset_phases(presets, case.key, phases)
    return sorted(effective_release_phases(case.key, phases))


def mole_fractions(db: Database, case: Case) -> dict[str, float]:
    percent = dict(case.composition_pct)
    percent[case.balance] = 100.0 - sum(case.composition_pct.values())
    elements = sorted(percent)
    if case.units != "wt":
        return {element: percent[element] / 100.0 for element in elements}

    from thermogar_equilibrium_core import mass_to_mole_fractions

    mass = tuple((element, percent[element] / 100.0) for element in elements)
    masses = tuple(
        (element, float(db.refstates[element]["mass"])) for element in elements
    )
    return dict(mass_to_mole_fractions(mass, masses))


def phase_fractions(eq: Any) -> dict[str, float]:
    """Доли фаз, собранные по составным множествам, как в приложении."""

    import numpy as np

    names = np.asarray(eq.Phase.values, dtype=str).ravel()
    amounts = np.asarray(eq.NP.values, dtype=float).ravel()
    aggregate: dict[str, float] = {}
    for name, amount in zip(names, amounts):
        if not name or amount != amount:  # noqa: PLR0124 - фильтр NaN
            continue
        aggregate[str(name)] = aggregate.get(str(name), 0.0) + float(amount)
    return {name: value for name, value in aggregate.items() if value > 1e-9}


def solve(
    db: Database,
    case: Case,
    phases: list[str],
    temperature_k: float,
    overrides: dict[Any, float] | None = None,
) -> dict[str, float]:
    fractions = mole_fractions(db, case)
    conditions: dict[Any, float] = {
        v.N: 1.0,
        v.P: 101325.0,
        v.T: float(temperature_k),
    }
    conditions.update(
        {
            v.X(element): fractions[element]
            for element in sorted(fractions)
            if element != case.balance
        }
    )
    if overrides:
        conditions.update(overrides)
    return phase_fractions(
        equilibrium(
            db,
            list(case.components),
            phases,
            conditions,
            calc_opts={"pdens": 100},
        )
    )


def assert_same_stable_phases(
    label: str,
    all_fractions: dict[str, float],
    fast_fractions: dict[str, float],
) -> None:
    """Наборы устойчивых фаз и их доли должны совпасть."""

    missing = sorted(set(all_fractions) - set(fast_fractions))
    assert not missing, (
        f"{label}: в режиме «все фазы» устойчива фаза вне быстрого набора: "
        f"{', '.join(missing)}. Добавьте её в {PHASE_PRESETS_RELATIVE_PATH}."
    )
    extra = sorted(set(fast_fractions) - set(all_fractions))
    assert not extra, (
        f"{label}: быстрый набор дал лишние устойчивые фазы: "
        f"{', '.join(extra)}"
    )
    for name, value in all_fractions.items():
        assert abs(value - fast_fractions[name]) < 1e-3, (
            f"{label}: доля {name} разошлась: "
            f"{value:.5f} против {fast_fractions[name]:.5f}"
        )


@pytest.fixture(scope="session")
def presets() -> Any:
    return load_phase_presets(ROOT)


@pytest.fixture(scope="session", params=DB_KEYS, ids=DB_KEYS)
def case(request: pytest.FixtureRequest) -> Case:
    return CASES[str(request.param)]


@pytest.fixture(scope="session")
def db(case: Case) -> Database:
    return load_case_database(case)


# --------------------------------------------------------------------------- #
# Файл наборов: схема и имена фаз
# --------------------------------------------------------------------------- #


def test_preset_file_shape(presets: Any) -> None:
    """Ключи — базы выпуска, имена — непустые, без повторов и без C15."""

    assert set(presets) == set(RELEASE_DATABASE_KEYS)
    payload = json.loads(
        (ROOT / PHASE_PRESETS_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    assert set(payload) == set(RELEASE_DATABASE_KEYS)
    for key in RELEASE_DATABASE_KEYS:
        names = list(presets[key])
        assert names, f"Пустой набор базы {key}"
        assert len(names) == len(set(names)), f"Повторы в наборе базы {key}"
        assert all(name == name.upper().strip() for name in names)
        assert "LIQUID" in names, (
            f"В наборе базы {key} нет LIQUID: затвердевание работать не будет"
        )
        assert not (set(names) & FE_EXCLUDED_PHASES), (
            f"Запрещённая для стали фаза попала в набор базы {key}"
        )


def test_broken_preset_file_is_rejected(tmp_path: Path) -> None:
    """Испорченный файл наборов не проходит молча."""

    root = tmp_path / "project"
    (root / "configs").mkdir(parents=True)
    target = root / PHASE_PRESETS_RELATIVE_PATH
    target.write_text('{"ni": [], "al": ["FCC_A1"]}', encoding="utf-8")
    with pytest.raises(PhasePresetError):
        load_phase_presets(root)


def test_preset_names_exist_in_database(
    db: Database,
    case: Case,
    presets: Any,
) -> None:
    """Каждое имя набора должно быть фазой этой TDB, иначе оно бесполезно."""

    unknown = sorted(name for name in presets[case.key] if name not in db.phases)
    assert not unknown, (
        f"В базе {case.key} нет фаз из набора: {', '.join(unknown)}"
    )


def test_fast_set_is_a_smaller_subset(
    db: Database,
    case: Case,
    presets: Any,
) -> None:
    """Быстрый набор — непустое строгое подмножество всех совместимых фаз."""

    all_phases = mode_phases(db, case, presets, PHASE_MODE_ALL)
    fast_phases = mode_phases(db, case, presets, PHASE_MODE_FAST)
    assert fast_phases, "Быстрый набор пуст"
    assert set(fast_phases) < set(all_phases), (
        "Быстрый набор не сокращает список фаз — смысла в режиме нет"
    )
    assert "LIQUID" in fast_phases


def test_al_preset_covers_full_range_diagrams(presets: Any) -> None:
    """Быстрый набор Al обязан покрывать полнодиапазонные диаграммы."""

    missing = sorted(AL_FULL_RANGE_PHASES - set(presets["al"]))
    assert not missing, (
        "Без этих фаз бинарная AL–CU и тройное сечение AL–CU–MG в быстром "
        f"наборе перестают совпадать с режимом «все фазы»: {', '.join(missing)}"
    )


def test_preset_never_empties_the_phase_list(presets: Any) -> None:
    """Набор не имеет права оставить расчёт вовсе без фаз."""

    assert preset_phases(presets, "fe", ["ZET"]) == ["ZET"]
    assert preset_phases({}, "fe", ["ZET", "M23C6"]) == ["ZET", "M23C6"]


def test_c15_excluded_in_both_modes(presets: Any) -> None:
    """Правило продукта: C15_LAVES для Fe не проходит ни в одном режиме."""

    case = CASES["fe"]
    db = load_case_database(case)
    unfiltered = sorted(
        filter_phases(db, unpack_species(db, list(case.components)))
    )
    assert "C15_LAVES" in unfiltered, (
        "C15_LAVES исчезла из filter_phases — правило перестало что-то значить"
    )
    for phase_mode in (PHASE_MODE_ALL, PHASE_MODE_FAST):
        assert "C15_LAVES" not in mode_phases(db, case, presets, phase_mode)


def test_phase_mode_note_text() -> None:
    """Строка «Набор фаз: …» для результата и выгрузки."""

    assert phase_mode_note(PHASE_MODE_FAST, 21, 34) == (
        "Набор фаз: быстрый (21 из 34)"
    )
    assert phase_mode_note(PHASE_MODE_ALL, 21, 34) == (
        "Набор фаз: все фазы базы (34)"
    )


# --------------------------------------------------------------------------- #
# Главное: устойчивые фазы «все» vs «быстрый» на эталонных точках
# --------------------------------------------------------------------------- #


@pytest.mark.timeout(DEFAULT_TIMEOUT)
def test_stable_phases_match_at_reference_point(
    db: Database,
    case: Case,
    presets: Any,
) -> None:
    """Эталонная точка: одни и те же устойчивые фазы и те же доли."""

    temperature_k = case.temperature_c + 273.15
    all_result = solve(
        db, case, mode_phases(db, case, presets, PHASE_MODE_ALL), temperature_k
    )
    fast_result = solve(
        db, case, mode_phases(db, case, presets, PHASE_MODE_FAST), temperature_k
    )
    assert all_result, "Равновесие в режиме «все фазы» не дало ни одной фазы"
    assert abs(sum(fast_result.values()) - 1.0) < 1e-5
    assert_same_stable_phases(
        f"{case.key}, {case.temperature_c:g} °C",
        all_result,
        fast_result,
    )


@pytest.mark.slow
@pytest.mark.timeout(SLOW_TIMEOUT)
def test_stable_phases_match_on_temperature_scan(
    db: Database,
    case: Case,
    presets: Any,
) -> None:
    """T-скан из пяти точек: набор не должен потерять ни одной фазы."""

    all_phases = mode_phases(db, case, presets, PHASE_MODE_ALL)
    fast_phases = mode_phases(db, case, presets, PHASE_MODE_FAST)
    for temperature_c in case.scan_temperatures_c:
        temperature_k = temperature_c + 273.15
        assert_same_stable_phases(
            f"{case.key}, T-скан {temperature_c:g} °C",
            solve(db, case, all_phases, temperature_k),
            solve(db, case, fast_phases, temperature_k),
        )


@pytest.mark.slow
@pytest.mark.timeout(SLOW_TIMEOUT)
def test_stable_phases_match_on_composition_scan(
    db: Database,
    case: Case,
    presets: Any,
) -> None:
    """X-скан из пяти точек по легирующему элементу."""

    all_phases = mode_phases(db, case, presets, PHASE_MODE_ALL)
    fast_phases = mode_phases(db, case, presets, PHASE_MODE_FAST)
    temperature_k = case.temperature_c + 273.15
    for fraction in case.scan_mole_fractions:
        override = {v.X(case.scan_element): float(fraction)}
        assert_same_stable_phases(
            f"{case.key}, X-скан x({case.scan_element})={fraction:g}",
            solve(db, case, all_phases, temperature_k, override),
            solve(db, case, fast_phases, temperature_k, override),
        )
