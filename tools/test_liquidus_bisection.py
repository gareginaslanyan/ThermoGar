#!/usr/bin/env python3
"""Температуры фазовых переходов ищутся половинным делением, а не интерполяцией.

Подпункт A1b волны 11A (`tasks/WAVE11A_TECH_OPUS.md`).

Что проверяется. В приложении «расчётный ликвидус» получался линейной
интерполяцией траектории затвердевания к выбранному порогу доли твёрдого.
У такой оценки две беды сразу: порог — величина отображения, и ликвидус от
него зависеть не должен; а доля твёрдого у собственной границы уходит от нуля
почти вертикально, поэтому линейная интерполяция через шаг траектории выдаёт
температуру, которой управляет шаг, а не фазовая граница.

Эталон — подпункт A1 той же волны: на контрольном составе ХН62М(Sc)-ВИ
половинное деление с точностью 0,1 K даёт ликвидус 1375,0 °C и солидус
1344,5 °C, причём одинаково при pdens 50, 100, 200 и 500. Метод же волны 9
(сетка 5 K плюс интерполяция к уровням 0,999 и 1e-4) даёт 1378,2 и 1340,1 °C:
ликвидус завышен на 3,2 K, солидус занижен на 4,4 K.

Поэтому тесты идут парой. Первый требует, чтобы половинное деление попадало в
1375,0 ± 0,2 и 1344,5 ± 0,2. Второй требует, чтобы старый способ в эти окна
**не** попадал: без него первый тест прошёл бы и на прежнем коде, и регрессия
осталась бы незамеченной.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -m pytest tools/test_liquidus_bisection.py -v
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

NI_TDB = ROOT / "databases" / "converted" / "mc_ni_v2036_with_mobility.garcalc.tdb"

# Контрольный состав волны 11A, масс. %; никель — основа.
CONTROL_WT: dict[str, float] = {
    "C": 0.005, "SI": 0.10, "MN": 0.50, "S": 0.020, "CR": 23.5,
    "MO": 13.0, "NB": 0.06, "AL": 0.25, "TI": 0.10, "FE": 0.50,
}
COMPONENTS: tuple[str, ...] = (
    "NI", "CR", "MO", "C", "SI", "MN", "S", "NB", "AL", "TI", "FE", "VA",
)
ELEMENTS: tuple[str, ...] = tuple(name for name in COMPONENTS if name != "VA")
BALANCE = "NI"

# Пара порядок/беспорядок BCC_B2/BCC_A2 в mc_ni не строится при внедрённом
# углероде: pycalphad поднимает ValueError ещё на этапе Model.
UNBUILDABLE_PHASES = ("BCC_B2",)

# pdens=50 выбран сознательно: подпункт A1 показал, что ликвидус и солидус не
# меняются ни на 0,01 K вплоть до pdens=500, а 50 считается вчетверо быстрее.
PDENS = 50
TOLERANCE_C = 0.1
SOLID_PRESENCE_FLOOR = 1.0e-6

EXPECTED_LIQUIDUS_C = 1375.0
EXPECTED_SOLIDUS_C = 1344.5
EXPECTED_WINDOW_C = 0.2

# Метод волны 9, воспроизведённый в подпункте A1.
WAVE9_GRID_STEP_C = 5.0
WAVE9_GRID_C = tuple(1200.0 + WAVE9_GRID_STEP_C * index for index in range(51))
WAVE9_LIQUIDUS_LEVEL = 0.999
WAVE9_SOLIDUS_LEVEL = 1.0e-4


# --------------------------------------------------------------------------- #
# Оснастка
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def system() -> dict[str, Any]:
    """База, список фаз и мольные доли контрольного состава.

    Модели фаз строятся один раз на модуль и передаются в ``equilibrium``:
    иначе pycalphad пересобирает и перекомпилирует все 48 фаз на каждый вызов,
    и тест из полусотни равновесий идёт не минуты, а часы.
    """

    from pycalphad import Database, variables as v
    from pycalphad.codegen.phase_record_factory import PhaseRecordFactory
    from pycalphad.core.utils import filter_phases, instantiate_models, unpack_species
    from thermogar_equilibrium_core import mass_to_mole_fractions

    if not NI_TDB.is_file():
        pytest.skip(f"Нет базы {NI_TDB}")

    database = Database(str(NI_TDB))
    phases = sorted(filter_phases(database, unpack_species(database, list(COMPONENTS))))
    phases = [name for name in phases if name not in UNBUILDABLE_PHASES]

    weights = dict(CONTROL_WT)
    weights[BALANCE] = 100.0 - sum(weights.values())
    names = sorted(weights)
    mole = dict(
        mass_to_mole_fractions(
            tuple((name, weights[name] / 100.0) for name in names),
            tuple(
                (name, float(database.refstates[name]["mass"])) for name in names
            ),
        )
    )

    models = instantiate_models(database, list(COMPONENTS), phases)
    return {
        "db": database,
        "phases": phases,
        "models": models,
        "records": PhaseRecordFactory(
            database, list(COMPONENTS), [v.N, v.P, v.T], models
        ),
        "conditions": {
            v.X(name): value
            for name, value in sorted(mole.items())
            if name != BALANCE
        },
    }


def solid_fraction_at(system: dict[str, Any], temperature_c: float) -> float:
    """Суммарная мольная доля твёрдых фаз при температуре."""

    from pycalphad import equilibrium, variables as v

    conditions = {v.N: 1.0, v.P: 101325.0, v.T: float(temperature_c) + 273.15}
    conditions.update(system["conditions"])
    result = equilibrium(
        system["db"], list(COMPONENTS), system["phases"], conditions,
        model=system["models"], phase_records=system["records"],
        calc_opts={"pdens": PDENS},
    )
    names = np.asarray(result.Phase.values, dtype=str).ravel()
    amounts = np.asarray(result.NP.values, dtype=float).ravel()
    total = 0.0
    for name, amount in zip(names, amounts):
        if not name or name == "LIQUID" or not np.isfinite(amount):
            continue
        if float(amount) > 1.0e-9:
            total += float(amount)
    del result
    return total


@pytest.fixture(scope="module")
def cached_solid_fraction(system: dict[str, Any]):
    """Доля твёрдого с запоминанием: оба теста щупают одни и те же точки."""

    memo: dict[float, float] = {}

    def value(temperature_c: float) -> float:
        key = round(float(temperature_c), 6)
        if key not in memo:
            memo[key] = solid_fraction_at(system, key)
        return memo[key]

    return value


def wave9_crossing(
    temperatures: list[float], values: list[float], level: float
) -> float:
    """Линейная интерполяция кривой к уровню — способ волны 9."""

    ordered = sorted(zip(temperatures, values), key=lambda pair: -pair[0])
    crossings: list[float] = []
    for (t1, v1), (t2, v2) in zip(ordered, ordered[1:]):
        if (v1 - level) * (v2 - level) <= 0.0 and v1 != v2:
            crossings.append(t1 + (level - v1) * (t2 - t1) / (v2 - v1))
    return crossings[0] if len(crossings) == 1 else math.nan


# --------------------------------------------------------------------------- #
# Тесты
# --------------------------------------------------------------------------- #


@pytest.mark.slow
def test_bisection_finds_control_liquidus_and_solidus(
    cached_solid_fraction,
) -> None:
    """Половинное деление попадает в 1375,0 ± 0,2 и 1344,5 ± 0,2 °C."""

    from thermogar_equilibrium_core import bisect_transition_temperature

    liquidus = bisect_transition_temperature(
        lambda temperature: bool(
            cached_solid_fraction(temperature) <= SOLID_PRESENCE_FLOOR
        ),
        1200.0, 1500.0, TOLERANCE_C,
    )
    solidus = bisect_transition_temperature(
        lambda temperature: bool(
            cached_solid_fraction(temperature) < 1.0 - SOLID_PRESENCE_FLOOR
        ),
        1000.0, 1450.0, TOLERANCE_C,
    )

    assert liquidus.value == pytest.approx(
        EXPECTED_LIQUIDUS_C, abs=EXPECTED_WINDOW_C
    ), f"ликвидус {liquidus.value:.2f} °C вне окна {EXPECTED_LIQUIDUS_C} ± {EXPECTED_WINDOW_C}"
    assert solidus.value == pytest.approx(
        EXPECTED_SOLIDUS_C, abs=EXPECTED_WINDOW_C
    ), f"солидус {solidus.value:.2f} °C вне окна {EXPECTED_SOLIDUS_C} ± {EXPECTED_WINDOW_C}"
    # Вилка действительно сжата до заявленного допуска, а не брошена на полпути.
    assert liquidus.high - liquidus.low <= TOLERANCE_C
    assert solidus.high - solidus.low <= TOLERANCE_C


@pytest.mark.slow
def test_grid_interpolation_misses_both_windows(cached_solid_fraction) -> None:
    """Старый способ в те же окна не попадает — иначе тест выше бесполезен.

    Ровно этот способ считал волна 9 и считало приложение: сетка 5 K и
    линейная интерполяция доли жидкости к уровням 0,999 и 1e-4.
    """

    temperatures = list(WAVE9_GRID_C)
    liquid = [1.0 - cached_solid_fraction(value) for value in temperatures]

    liquidus = wave9_crossing(temperatures, liquid, WAVE9_LIQUIDUS_LEVEL)
    solidus = wave9_crossing(temperatures, liquid, WAVE9_SOLIDUS_LEVEL)

    assert math.isfinite(liquidus) and math.isfinite(solidus)
    assert abs(liquidus - EXPECTED_LIQUIDUS_C) > EXPECTED_WINDOW_C, (
        f"интерполяция по сетке дала ликвидус {liquidus:.2f} °C — он попал в "
        "окно, и тогда парный тест ничего не сторожит"
    )
    assert abs(solidus - EXPECTED_SOLIDUS_C) > EXPECTED_WINDOW_C, (
        f"интерполяция по сетке дала солидус {solidus:.2f} °C — он попал в "
        "окно, и тогда парный тест ничего не сторожит"
    )
    # Знак ошибки тоже зафиксирован: ликвидус завышается, солидус занижается.
    assert liquidus > EXPECTED_LIQUIDUS_C
    assert solidus < EXPECTED_SOLIDUS_C
