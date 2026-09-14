#!/usr/bin/env python3
"""Сетка баланса населённости KWN и ложная объёмная доля 100 % (BL-22).

Механизм разобран волнами 12-1 и 13-Г: kawin строит сетку линейно по радиусу
и кладёт зародыш в класс ``argmax(PSDbounds > Rnuc) - 1``. Класс шире
критического радиуса завышает объём зародыша на порядки, доля обрезается
единицей и защёлкивается; зародыш меньше ``cMin`` получает индекс -1, то есть
уходит в последний, самый крупный класс. Тесты проверяют, что приложение не
пускает в расчёт такую сетку и не называет долю 100 % пройденной проверкой.

Запуск (пофайлово, см. ``tasks/WAVE11R_REPORT.md``):
    <root>/.venv-windows/Scripts/python.exe -B -X utf8 -m pytest tools/test_precipitation_grid.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

import thermogar_precipitation as precipitation

NI_DATABASE = ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"


# --------------------------------------------------------------------------- #
# Поведение kawin, ради которого стоят проверки
# --------------------------------------------------------------------------- #


def _population_balance(cmin_m: float, cmax_m: float, bins: int) -> object:
    pytest.importorskip("kawin")
    from kawin.precipitation.PopulationBalance import PopulationBalanceModel

    return PopulationBalanceModel(cmin_m, cmax_m, bins, bins // 2, bins * 2)


def test_kawin_puts_nucleus_below_cmin_into_last_class() -> None:
    """Зародыш меньше cMin kawin записывает в последний, самый крупный класс.

    Второй дефект из разбора 13-Г подтверждён. Если kawin однажды начнёт
    класть такой зародыш в первый класс, тест упадёт, и проверку «зародыш не
    меньше минимального радиуса сетки» можно будет пересмотреть.
    """

    model = _population_balance(1.0e-9, 10.0e-9, 20)
    nucleation_rate = 1.0e20
    rates = model.getdXdtEuler(
        np.zeros(model.bins + 1), nucleation_rate, 0.5e-9, np.zeros(model.bins)
    )
    assert rates[-1] == nucleation_rate
    assert np.count_nonzero(rates) == 1
    assert model.PSDsize[-1] > 9.0e-9


def test_kawin_puts_nucleus_into_class_wider_than_nucleus() -> None:
    """При классе шире зародыша частица записывается радиусом центра класса."""

    model = _population_balance(0.2e-9, 1.0e-5, 100)
    nucleus_m = 0.5e-9
    rates = model.getdXdtEuler(
        np.zeros(model.bins + 1), 1.0e20, nucleus_m, np.zeros(model.bins)
    )
    index = int(np.flatnonzero(rates)[0])
    assert index == 0
    # Объём записанной частицы больше объёма зародыша на шесть порядков.
    assert (model.PSDsize[index] / nucleus_m) ** 3 > 1.0e6


# --------------------------------------------------------------------------- #
# Проверки после расчёта
# --------------------------------------------------------------------------- #


def _data(
    fraction: list[float],
    *,
    rcrit_nm: float = 0.6,
    rnuc_nm: float = 0.8,
    nucleation_rate: float = 1.0e20,
) -> SimpleNamespace:
    steps = len(fraction)
    column = lambda values: np.asarray(values, float).reshape(steps, 1)  # noqa: E731
    return SimpleNamespace(
        time=np.linspace(0.0, 10.0, steps),
        temperature=np.full(steps, 1073.15),
        volFrac=column(fraction),
        Ravg=column([1.0e-9] * steps),
        precipitateDensity=column([1.0e22] * steps),
        composition=np.tile([0.098, 0.083], (steps, 1)),
        nucRate=column([nucleation_rate] * steps),
        Rcrit=column([rcrit_nm * 1e-9] * steps),
        Rnuc=column([rnuc_nm * 1e-9] * steps),
    )


def _statuses(table) -> dict[str, str]:
    return dict(zip(table["Проверка"], table["Статус"]))


def test_quality_passes_on_resolved_grid() -> None:
    table = precipitation._quality(_data([0.0, 0.01, 0.02]), 0, 2, 0.2, 10.0, 80)
    assert (table["Статус"] == "пройдена").all(), table


def test_volume_fraction_of_one_is_not_a_passed_check() -> None:
    """Доля ровно 1,0 — ошибка качества, а значит зелёной плашки не будет."""

    table = precipitation._quality(_data([0.0, 1.0, 1.0]), 0, 2, 0.2, 10.0, 80)
    statuses = _statuses(table)
    assert statuses["Объёмная доля 0–1"] == "пройдена"
    assert statuses["Объёмная доля не упёрлась в 100 %"] == "ошибка"
    # Плашку «Внутренние численные проверки пройдены» раздел показывает только
    # при всех пройденных проверках.
    assert not (table["Статус"] == "пройдена").all()


def test_volume_fraction_ceiling_checked_without_grid_arguments() -> None:
    table = precipitation._quality(_data([0.0, 1.0]), 0, 2)
    assert _statuses(table)["Объёмная доля не упёрлась в 100 %"] == "ошибка"


def test_quality_flags_class_wider_than_critical_radius() -> None:
    # (1e4 - 0.2) / 20 ≈ 500 нм при критическом радиусе 0,6 нм.
    table = precipitation._quality(_data([0.0, 0.3]), 0, 2, 0.2, 1.0e4, 20)
    assert _statuses(table)["Ширина класса меньше критического радиуса"] == "ошибка"


def test_quality_flags_nucleus_below_minimum_radius() -> None:
    table = precipitation._quality(_data([0.0, 0.3], rnuc_nm=0.8), 0, 2, 2.0, 10.0, 80)
    statuses = _statuses(table)
    assert statuses["Зародыш не меньше минимального радиуса сетки"] == "ошибка"


def test_quality_ignores_steps_without_nucleation() -> None:
    table = precipitation._quality(
        _data([0.0, 0.0], nucleation_rate=0.0, rnuc_nm=0.0), 0, 2, 2.0, 1.0e4, 20
    )
    assert (table["Статус"] == "пройдена").all(), table


# --------------------------------------------------------------------------- #
# Проверка до расчёта
# --------------------------------------------------------------------------- #


def test_check_size_grid_refuses_class_wider_than_critical_radius() -> None:
    estimates = [(1073.15, 0.6, 0.8)]
    with pytest.raises(ValueError, match="слишком грубая") as error:
        precipitation._check_size_grid(estimates, 0.2, 1.0e4, 20)
    assert "0.6 нм" in str(error.value)


def test_check_size_grid_refuses_nucleus_below_minimum_radius() -> None:
    with pytest.raises(ValueError, match="последний, самый крупный класс"):
        precipitation._check_size_grid([(1073.15, 0.6, 0.8)], 2.0, 10.0, 80)


def test_check_size_grid_uses_strictest_temperature_of_profile() -> None:
    estimates = [(1373.15, 3.0, 3.3), (1073.15, 0.6, 0.8)]
    with pytest.raises(ValueError, match="800.0 °C"):
        precipitation._check_size_grid(estimates, 0.2, 10.0, 16)


def test_check_size_grid_accepts_default_grid_and_empty_estimates() -> None:
    precipitation._check_size_grid([(1073.15, 0.6, 0.8)], 0.2, 10.0, 80)
    precipitation._check_size_grid([], 50.0, 51.0, 20)


# --------------------------------------------------------------------------- #
# Штатный путь run_precipitation
# --------------------------------------------------------------------------- #


def _run_demo(**overrides):
    pytest.importorskip("kawin")
    if not NI_DATABASE.is_file():
        pytest.skip(f"Нет базы: {NI_DATABASE}")
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    preset = precipitation.PRESET_NI
    arguments = dict(
        db=object(),
        database_path=NI_DATABASE,
        database_label=RELEASE_DATABASE_LABELS["ni"],
        database_key="ni",
        balance="NI",
        composition_text=preset["composition"],
        units="at",
        matrix_phase=preset["matrix"],
        precipitate_phase=preset["precipitate"],
        schedule_mode="isothermal",
        temperature_c=preset["temperature_c"],
        duration_h=1.0 / 3600.0,
        profile_text="",
        gamma=preset["gamma"],
        matrix_vm=preset["matrix_vm"],
        precip_vm=preset["precip_vm"],
        nucleation_type="BULK",
        bulk_n0=preset["bulk_n0"],
        grain_size_um=100.0,
        dislocation_density=5e12,
        gb_energy=0.3,
        cmin_nm=0.2,
        cmax_nm=5.0,
        bins=30,
        input_provenance="SYNTHETIC_GRID_REGRESSION_NOT_MATERIAL_INPUT",
        input_confirmation=True,
    )
    arguments.update(overrides)
    return precipitation.run_precipitation(**arguments)


def test_run_precipitation_refuses_coarse_grid_before_solving() -> None:
    """Сетка 12-1 (классы в сотни нанометров) — отказ с понятным текстом."""

    with pytest.raises(ValueError, match="Сетка размеров слишком грубая"):
        _run_demo(cmin_nm=0.2, cmax_nm=1.0e4, bins=20)


def test_run_precipitation_refuses_minimum_radius_above_nucleus() -> None:
    with pytest.raises(ValueError, match="последний, самый крупный класс"):
        _run_demo(cmin_nm=5.0, cmax_nm=5.5, bins=20)


def test_run_precipitation_on_resolved_grid_passes_all_checks() -> None:
    result = _run_demo()
    assert (result.quality["Статус"] == "пройдена").all(), result.quality
    names = set(result.quality["Проверка"])
    assert "Объёмная доля не упёрлась в 100 %" in names
    assert "Ширина класса меньше критического радиуса" in names
    assert "Зародыш не меньше минимального радиуса сетки" in names
    # В составе нет ниобия — сообщения о правке его подвижности нет.
    assert result.warnings == []
