#!/usr/bin/env python3
"""Тепловое расширение в расчёте плотности: величина, а не только знак.

Вопрос, поднятый по итогам A2 волны 11A. Плотность контрольного состава
ХН62М(Sc)-ВИ падает с 8480,6 кг/м³ при 25 °C до 7937,1 при 1100 °C. Это
отвечает среднему линейному коэффициенту расширения 21,2e-6 /K при справочных
примерно 15,5e-6 для сплавов Ni-Cr-Mo, а на участке 1100…1300 °C, где 99,93 %
молей считаются прямой моделью, коэффициент доходит до 30,7e-6. Тесты волны 10
проверяли монотонность ρ(T), то есть знак, и величину не проверяли.

Разведено так же, как корень плотности в волне 10: плотность чистого никеля
в FCC_A1 вычисляется прямо из функций базы `D0FCC_NI + DTNIFCC`, минуя код
приложения, и сравнивается с тем, что приложение выдаёт на тех же
температурах. Совпадает до последней цифры, причём и для смеси Ni-Cr-Mo
приложение точно воспроизводит объёмную аддитивность по конечным членам базы.
Двойного учёта расширения в приложении нет.

Виновата база. Её собственные конечные члены дают:

    NI   17,8e-6 /K   при справочных 13,4e-6
    CR   34,5e-6 /K   при справочных  6,2e-6   ← источник ошибки
    MO    6,0e-6 /K   при справочных  4,8e-6

Хром даёт 55 % расширения смеси, занимая 28 % её объёма. Если подставить
литературный коэффициент хрома, коэффициент сплава падает с 30,7e-6 до
15,8e-6 /K, то есть попадает в физически ожидаемое окно. База сама себя
выдаёт в шапке файла: «densities from ref 14 are based on molar volume data,
**except Cr** (based on density data)» — хром единственный посчитан иначе.

Поэтому тестов три вида:

* `test_pure_nickel_*` и `test_alloy_matrix_*` — приложение против базы; они
  проходят и доказывают, что код чист;
* `test_alloy_expansion_magnitude_is_physical` — физическое требование
  12…20e-6 /K; помечен `xfail(strict=True)`, потому что база его не
  выполняет. Строгий режим выбран сознательно: когда базу починят, тест
  неожиданно пройдёт, и это уронит прогон, то есть о починке скажут, а не
  промолчат;
* `test_alloy_expansion_regression_anchor` — фиксирует нынешнюю величину,
  чтобы молчаливая подмена базы не прошла незамеченной.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -m pytest tools/test_density_thermal_expansion.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

NI_TDB = ROOT / "databases" / "converted" / "mc_ni_v2036_with_mobility.garcalc.tdb"
PDB_PATH = ROOT / "databases" / "physical" / "original" / "physical_data_v103.pdb"

CONTROL_WT: dict[str, float] = {
    "C": 0.005, "SI": 0.10, "MN": 0.50, "S": 0.020, "CR": 23.5,
    "MO": 13.0, "NB": 0.06, "AL": 0.25, "TI": 0.10, "FE": 0.50,
}
COMPONENTS: tuple[str, ...] = (
    "NI", "CR", "MO", "C", "SI", "MN", "S", "NB", "AL", "TI", "FE", "VA",
)
ELEMENTS: tuple[str, ...] = tuple(name for name in COMPONENTS if name != "VA")
BALANCE = "NI"
PDENS = 100

# Конечные члены physical_data_v103.pdb, выписанные из файла дословно.
#   PARAMETER DP(FCC_A1,NI:VA) = D0FCC_NI + DTNIFCC
#   PARAMETER DP(FCC_A1,CR:VA) = D0BCC_CR + DTCRBCC
#   PARAMETER DP(FCC_A1,MO:VA) = D0BCC_MO + DTMOBCC
BASE_FUNCTIONS = {
    "NI": lambda t: 8914.0 + (103.38 - 0.3432863 * t - 0.0000627364 * t ** 2),
    "CR": lambda t: 7200.0 + (
        73.9748 - 0.263244367 * t - 0.00013071 * t ** 2 - 0.000000073784 * t ** 3
    ),
    "MO": lambda t: 10223.8 + (
        49.966 - 0.17146 * t + 0.0000161584 * t ** 2 - 0.0000000151 * t ** 3
    ),
}
ATOMIC_MASS = {"NI": 58.693, "CR": 51.996, "MO": 95.95}

# Справочные линейные коэффициенты расширения чистых металлов, 1e-6 /K.
REFERENCE_ALPHA = {"NI": 13.4, "CR": 6.2, "MO": 4.8}

# Физически ожидаемое окно для сплава Ni-Cr-Mo, 1e-6 /K.
PHYSICAL_ALPHA_WINDOW = (12.0, 20.0)
# Измерено на этой базе 2026-09-11; якорь регрессии, а не эталон физики.
MEASURED_ALPHA_25_1100 = 21.2
MEASURED_ALPHA_TOLERANCE = 1.0


def linear_alpha(density_hot: float, density_cold: float,
                 temperature_hot: float, temperature_cold: float) -> float:
    """Средний линейный коэффициент расширения из пары плотностей, 1/K.

    Объём обратен плотности, линейный размер — кубический корень объёма,
    поэтому ρ_хол/ρ_гор = (1 + α·ΔT)³, и при малом α·ΔT это 1 + 3α·ΔT.
    """
    return (density_cold / density_hot - 1.0) / (
        3.0 * (temperature_hot - temperature_cold)
    )


@pytest.fixture(scope="module")
def physical_db() -> Any:
    """База плотностей **без перекрывающего слоя проекта**.

    Тесты этого файла отвечают на вопрос «приложение добавляет своё или так
    написано в базе», поэтому сравнивать надо с базой как есть. С волны 11M-2
    к базе применяется перекрытие плотности хрома
    (`databases/physical/overrides/physical_data_v103.overrides.json`), и по
    умолчанию конструктор его подхватывает: тогда смесь Ni-Cr-Mo от функций
    базы отличается на 1,4e-7 при 298,15 K и на 2 % при 1373,15 K — это
    поправка, а не «код добавил своё». Перекрытие проверяется своими тестами в
    `tools/test_density.py`, раздел «11K-2».
    """

    from thermogar_physical import PhysicalDensityDatabase

    if not PDB_PATH.is_file():
        pytest.skip(f"Нет базы плотностей {PDB_PATH}")
    return PhysicalDensityDatabase(str(PDB_PATH), overrides=None)


@pytest.fixture(scope="module")
def alloy_density(physical_db: Any):
    """Плотность контрольного состава через полный путь приложения."""

    from pycalphad import Database, equilibrium, variables as v
    from pycalphad.codegen.phase_record_factory import PhaseRecordFactory
    from pycalphad.core.utils import filter_phases, instantiate_models, unpack_species
    from thermogar_equilibrium_core import mass_to_mole_fractions
    from thermogar_physical import calculate_physical_properties

    if not NI_TDB.is_file():
        pytest.skip(f"Нет базы {NI_TDB}")

    database = Database(str(NI_TDB))
    phases = sorted(filter_phases(database, unpack_species(database, list(COMPONENTS))))
    phases = [name for name in phases if name != "BCC_B2"]
    weights = dict(CONTROL_WT)
    weights[BALANCE] = 100.0 - sum(weights.values())
    names = sorted(weights)
    mole = dict(
        mass_to_mole_fractions(
            tuple((name, weights[name] / 100.0) for name in names),
            tuple((name, float(database.refstates[name]["mass"])) for name in names),
        )
    )
    conditions = {
        v.X(name): value for name, value in sorted(mole.items()) if name != BALANCE
    }
    models = instantiate_models(database, list(COMPONENTS), phases)
    records = PhaseRecordFactory(database, list(COMPONENTS), [v.N, v.P, v.T], models)
    memo: dict[float, Any] = {}

    def value(temperature_c: float) -> Any:
        key = round(float(temperature_c), 6)
        if key in memo:
            return memo[key]
        temperature_k = key + 273.15
        state = {v.N: 1.0, v.P: 101325.0, v.T: temperature_k}
        state.update(conditions)
        eq = equilibrium(
            database, list(COMPONENTS), phases, state,
            model=models, phase_records=records, calc_opts={"pdens": PDENS},
        )
        memo[key] = calculate_physical_properties(
            database, eq, list(ELEMENTS), temperature_k, physical_db
        )
        return memo[key]

    return value


# --------------------------------------------------------------------------- #
# Приложение против базы: двойного учёта расширения нет
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("temperature_k", [298.15, 500.0, 800.0, 1100.0, 1400.0])
def test_pure_nickel_matches_base_function(
    physical_db: Any, temperature_k: float
) -> None:
    """Чистый никель в FCC_A1 совпадает с функцией базы на всех температурах.

    Проверяется именно наклон, а не одна опорная точка: расширение, учтённое
    дважды, дало бы совпадение при 298 K и расхождение выше.
    """

    value, coverage, warnings = physical_db.density_from_site_fractions(
        "FCC_A1", [{"NI": 1.0}, {"VA": 1.0}], temperature_k
    )
    assert value is not None, f"плотность не посчитана: {warnings}"
    assert coverage > 0.999
    expected = BASE_FUNCTIONS["NI"](temperature_k)
    assert value == pytest.approx(expected, rel=1.0e-12), (
        f"{temperature_k} K: приложение {value:.4f}, база {expected:.4f}"
    )


def test_alloy_matrix_follows_volume_additivity(physical_db: Any) -> None:
    """Смесь Ni-Cr-Mo приложение считает объёмно-аддитивно по базе.

    Это отделяет «код добавил своё» от «так написано в базе»: если числа
    совпадают с ручной объёмной аддитивностью конечных членов, приложению
    добавить нечего.
    """

    site_fractions = {"NI": 0.66, "CR": 0.26, "MO": 0.08}
    for temperature_k in (298.15, 1373.15, 1573.15):
        value, _coverage, _warnings = physical_db.density_from_site_fractions(
            "FCC_A1", [dict(site_fractions), {"VA": 1.0}], temperature_k
        )
        mass = sum(
            site_fractions[name] * ATOMIC_MASS[name] for name in site_fractions
        )
        volume = sum(
            site_fractions[name] * ATOMIC_MASS[name]
            / BASE_FUNCTIONS[name](temperature_k)
            for name in site_fractions
        )
        assert value == pytest.approx(mass / volume, rel=1.0e-9), (
            f"{temperature_k} K: приложение {value:.4f}, "
            f"объёмная аддитивность {mass / volume:.4f}"
        )


# --------------------------------------------------------------------------- #
# Где именно ошибка
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("element", sorted(REFERENCE_ALPHA))
def test_endmember_expansion_against_reference(element: str) -> None:
    """Коэффициенты расширения конечных членов базы против справочных.

    Никель и молибден лежат близко к справочным, хром завышен впятеро. Тест
    удерживает этот расклад: если база сменится, расклад изменится, и об этом
    скажут здесь, а не через сплав.
    """

    function = BASE_FUNCTIONS[element]
    alpha = linear_alpha(function(1400.0), function(298.15), 1400.0, 298.15) * 1.0e6
    reference = REFERENCE_ALPHA[element]
    if element == "CR":
        assert alpha > 3.0 * reference, (
            f"хром в базе больше не завышен ({alpha:.1f}e-6 против "
            f"справочных {reference:.1f}e-6) — корень ошибки исчез, "
            "пересмотрите выводы A2"
        )
    else:
        assert alpha == pytest.approx(reference, abs=5.0), (
            f"{element}: база {alpha:.1f}e-6, справочно {reference:.1f}e-6"
        )


def test_literature_chromium_brings_alloy_into_window() -> None:
    """С литературным хромом коэффициент сплава попадает в физическое окно.

    Это и есть доказательство, что весь избыток расширения идёт от хрома, а не
    распределён по конечным членам.
    """

    site_fractions = {"NI": 0.66, "CR": 0.26, "MO": 0.08}
    cold = BASE_FUNCTIONS["CR"](298.15)
    fixed = dict(BASE_FUNCTIONS)
    fixed["CR"] = lambda t: cold * (1.0 - 3.0 * REFERENCE_ALPHA["CR"] * 1.0e-6 * (t - 298.15))

    def mixture(functions: dict[str, Any], temperature_k: float) -> float:
        mass = sum(site_fractions[n] * ATOMIC_MASS[n] for n in site_fractions)
        volume = sum(
            site_fractions[n] * ATOMIC_MASS[n] / functions[n](temperature_k)
            for n in site_fractions
        )
        return mass / volume

    as_is = linear_alpha(
        mixture(BASE_FUNCTIONS, 1573.15), mixture(BASE_FUNCTIONS, 1373.15),
        1573.15, 1373.15,
    ) * 1.0e6
    repaired = linear_alpha(
        mixture(fixed, 1573.15), mixture(fixed, 1373.15), 1573.15, 1373.15
    ) * 1.0e6

    assert as_is > PHYSICAL_ALPHA_WINDOW[1], (
        f"база как есть даёт {as_is:.1f}e-6 — она уже в окне, вывод устарел"
    )
    low, high = PHYSICAL_ALPHA_WINDOW
    assert low <= repaired <= high, (
        f"с литературным хромом вышло {repaired:.1f}e-6, окно {low}…{high}e-6"
    )


# --------------------------------------------------------------------------- #
# Величина для сплава
# --------------------------------------------------------------------------- #


@pytest.mark.slow
@pytest.mark.xfail(
    strict=True,
    reason=(
        "physical_data_v103.pdb завышает расширение хрома впятеро "
        "(DTCRBCC даёт 34,5e-6 /K против справочных 6,2e-6), поэтому сплав "
        "выходит за физическое окно. Починят базу — тест пройдёт и уронит "
        "прогон, чтобы о починке узнали."
    ),
)
def test_alloy_expansion_magnitude_is_physical(alloy_density) -> None:
    """ρ(25)/ρ(1100) должно отвечать 12…20e-6 /K, как у сплавов Ni-Cr-Mo."""

    cold = alloy_density(25.0).alloy_density_kg_m3
    hot = alloy_density(1100.0).alloy_density_kg_m3
    assert cold is not None and hot is not None
    alpha = linear_alpha(hot, cold, 1100.0 + 273.15, 25.0 + 273.15) * 1.0e6
    low, high = PHYSICAL_ALPHA_WINDOW
    assert low <= alpha <= high, (
        f"средний линейный коэффициент {alpha:.1f}e-6 /K вне окна "
        f"{low}…{high}e-6 (ρ25={cold:.1f}, ρ1100={hot:.1f})"
    )


@pytest.mark.slow
def test_alloy_expansion_regression_anchor(alloy_density) -> None:
    """Нынешняя величина зафиксирована: подмена базы не пройдёт молча."""

    cold = alloy_density(25.0).alloy_density_kg_m3
    hot = alloy_density(1100.0).alloy_density_kg_m3
    alpha = linear_alpha(hot, cold, 1100.0 + 273.15, 25.0 + 273.15) * 1.0e6
    assert alpha == pytest.approx(
        MEASURED_ALPHA_25_1100, abs=MEASURED_ALPHA_TOLERANCE
    ), (
        f"коэффициент {alpha:.1f}e-6 /K разошёлся с замером "
        f"{MEASURED_ALPHA_25_1100}e-6: база или код поменялись"
    )
    # Знак тоже держим: он проверялся волной 10 и должен остаться.
    assert hot < cold
