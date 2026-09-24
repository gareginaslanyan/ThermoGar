#!/usr/bin/env python3
"""Сетка баланса населённости KWN и ложная объёмная доля 100 % (BL-22).

Механизм разобран волнами 12-1 и 13-Г: kawin строит сетку линейно по радиусу
и кладёт зародыш в класс ``argmax(PSDbounds > Rnuc) - 1``. Класс шире
критического радиуса завышает объём зародыша на порядки, доля обрезается
единицей и защёлкивается; зародыш меньше ``cMin`` получает индекс -1, то есть
уходит в последний, самый крупный класс. Тесты проверяют, что приложение не
пускает в расчёт такую сетку и не называет долю 100 % пройденной проверкой.

С волны 14-Б здесь же: критический радиус до зажима против нижнего предела
kawin (BL-32; с 14-Г — отказ при u = Rmin/r* ≥ 1,5, предупреждение при 1 < u < 1,5,
тексты по типу центров) и предел числа добавок 10 (BL-21).

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


def _kawin_radius_floor_nm() -> float:
    pytest.importorskip("kawin")
    return 1e9 * float(precipitation.PrecipitateParameters("GAMMA_PRIME").Rmin)


def _estimate(free_nm: float, temperature_k: float = 1023.15) -> tuple[float, float, float, float]:
    """Оценка в форме ``_nucleus_estimates``: радиус kawin зажат снизу пределом."""

    clamped_nm = max(free_nm, _kawin_radius_floor_nm())
    return (temperature_k, clamped_nm, clamped_nm + 0.2, free_nm)


def test_refusal_ratio_is_the_zero_of_the_grain_boundary_barrier() -> None:
    """BL-32, 14-Г: ΔG(R)/G* = 3u² − 2u³ ветки kawin для границ зёрен — ноль на пороге."""

    ratio = precipitation.CRITICAL_RADIUS_REFUSAL_RATIO
    barrier = lambda u: 3 * u**2 - 2 * u**3  # noqa: E731
    assert barrier(ratio) == pytest.approx(0.0, abs=1e-12)
    assert barrier(ratio * (1 - 1e-6)) > 0
    assert barrier(ratio * (1 + 1e-6)) < 0


def test_check_refuses_bulk_without_barrier_wording() -> None:
    """Объём и дислокации: порог эмпирический, причина в терминах барьера не называется."""

    floor_nm = _kawin_radius_floor_nm()
    # 0,149 нм — r* до зажима у А5 14-А (u = 2,01).
    with pytest.raises(ValueError) as error:
        precipitation._check_critical_radius_floor([_estimate(0.149)], floor_nm, False)
    message = str(error.value)
    assert "меньше предела модели" in message
    assert "более чем в полтора раза" in message
    assert "в наших опытах не сходился" in message
    assert message.endswith("Поднимите межфазную энергию либо температуру.")
    assert "750.0 °C" in message
    assert "барьер" not in message
    assert "порядки" not in message


def test_check_refuses_grain_boundaries_with_the_derived_reason() -> None:
    floor_nm = _kawin_radius_floor_nm()
    with pytest.raises(ValueError) as error:
        precipitation._check_critical_radius_floor([_estimate(0.149)], floor_nm, True)
    message = str(error.value)
    assert "более чем в полтора раза" in message
    assert "барьер зарождения на границах зёрен обращается в ноль" in message
    assert "скорость зарождения расходится" in message
    assert message.endswith("Поднимите межфазную энергию либо температуру.")


@pytest.mark.parametrize("grain_boundary_nucleation", (False, True))
def test_check_warns_between_floor_and_refusal_ratio(grain_boundary_nucleation: bool) -> None:
    """1 < u < 1,5 — только предупреждение, по факту, без процентов и «занижения»."""

    floor_nm = _kawin_radius_floor_nm()
    # 0,268 нм — умолчание Ni-раздела (u = 1,12).
    warnings = precipitation._check_critical_radius_floor(
        [_estimate(0.268)], floor_nm, grain_boundary_nucleation
    )
    assert len(warnings) == 1, warnings
    assert "меньше предела модели" in warnings[0]
    assert "модель считает зарождение от этого предела" in warnings[0]
    assert "не классическая для этой движущей силы" in warnings[0]
    assert "может быть искажено" in warnings[0]
    for word in ("%", "занижен", "барьер", "порядки"):
        assert word not in warnings[0]


def test_check_is_silent_without_clamp() -> None:
    floor_nm = _kawin_radius_floor_nm()
    # 0,373 нм — Б5 (u = 0,80); радиус ровно на пределе — u = 1, зажима нет.
    assert precipitation._check_critical_radius_floor([_estimate(0.373)], floor_nm, False) == []
    assert precipitation._check_critical_radius_floor([_estimate(floor_nm)], floor_nm, True) == []
    assert precipitation._check_critical_radius_floor([], floor_nm, False) == []
    assert precipitation._check_critical_radius_floor([_estimate(0.149)], None, False) == []


@pytest.mark.parametrize("grain_boundary_nucleation", (False, True))
def test_check_boundary_from_both_sides(grain_boundary_nucleation: bool) -> None:
    floor_nm = _kawin_radius_floor_nm()
    at_ratio_nm = floor_nm / precipitation.CRITICAL_RADIUS_REFUSAL_RATIO
    # Радиус чуть больше порогового — u чуть меньше 1,5: предупреждение.
    warnings = precipitation._check_critical_radius_floor(
        [_estimate(at_ratio_nm * (1 + 1e-9))], floor_nm, grain_boundary_nucleation
    )
    assert len(warnings) == 1
    # Чуть меньше — отказ.
    with pytest.raises(ValueError, match="более чем в полтора раза"):
        precipitation._check_critical_radius_floor(
            [_estimate(at_ratio_nm * (1 - 1e-9))], floor_nm, grain_boundary_nucleation
        )


def test_check_takes_the_worst_temperature_of_a_profile() -> None:
    floor_nm = _kawin_radius_floor_nm()
    estimates = [_estimate(0.797, 1073.15), _estimate(0.149, 973.15)]
    with pytest.raises(ValueError, match="700.0 °C"):
        precipitation._check_critical_radius_floor(estimates, floor_nm, False)


# --------------------------------------------------------------------------- #
# Предел числа добавок (BL-21)
# --------------------------------------------------------------------------- #


def _database_stub(elements: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        elements=set(elements) | {"VA"},
        refstates={element: {"mass": 50.0} for element in elements},
    )


TEN_SOLUTES = ["AL", "CO", "CR", "FE", "MN", "MO", "NB", "SI", "TI", "W"]


def test_composition_accepts_ten_solutes() -> None:
    database = _database_stub(["NI", *TEN_SOLUTES])
    text = ", ".join(f"{element}=0.5" for element in TEN_SOLUTES)
    elements, x_at, _x_wt = precipitation._composition_vectors(database, "NI", text, "wt")
    assert elements == ["NI", *TEN_SOLUTES]
    assert x_at.sum() == pytest.approx(1.0)


def test_composition_refuses_eleven_solutes_as_measured_limit() -> None:
    database = _database_stub(["NI", *TEN_SOLUTES, "V"])
    text = ", ".join(f"{element}=0.5" for element in [*TEN_SOLUTES, "V"])
    with pytest.raises(ValueError) as error:
        precipitation._composition_vectors(database, "NI", text, "wt")
    message = str(error.value)
    assert "не более 10 добавок" in message
    assert "в составе 11" in message
    assert "предел измеренного, а не физический" in message


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


# Постановка 14-А: γ′ в FCC_A1 при 750 °C, физические входы пункта 5 отчёта
# 13-Р2, сетка умолчаний раздела, 10 с. Составы синтетические, масс. %.
WAVE14_CASE = dict(
    units="wt",
    matrix_phase="FCC_A1",
    precipitate_phase="GAMMA_PRIME",
    temperature_c=750.0,
    duration_h=10.0 / 3600.0,
    gamma=0.023,
    matrix_vm=6.5662724928,
    precip_vm=6.5662724928,
    bulk_n0=1e30,
    cmin_nm=0.2,
    cmax_nm=10.0,
    bins=80,
    input_provenance="SYNTHETIC_WAVE14_NOT_MATERIAL_INPUT",
)


# Состав А5 14-А: r* γ′ до зажима 0,149 нм, u = 2,01; в 14-А расчёт завис.
A5_COMPOSITION = "CR=19, NB=5.1, TI=0.9, AL=0.5, FE=18"


class _SolveReached(Exception):
    """Расчёт дошёл до ``solve``, то есть проверки до расчёта пропустили случай."""


def _forbid_solve(monkeypatch: pytest.MonkeyPatch, exception: type[BaseException] = AssertionError) -> None:
    def solve(*_arguments, **_keywords):
        raise exception("расчёт запущен")

    monkeypatch.setattr(precipitation.PrecipitateModel, "solve", solve)


def test_run_precipitation_refuses_bulk_case_a5_before_solving(monkeypatch: pytest.MonkeyPatch) -> None:
    """BL-32, объём: А5 отклоняется до расчёта, за секунды.

    ``solve`` подменён на ``AssertionError``: если проверку однажды сломают,
    тест упадёт сразу, а не зависнет, как расчёт в 14-А.
    """

    import time

    _forbid_solve(monkeypatch)
    started = time.perf_counter()
    with pytest.raises(ValueError) as error:
        _run_demo(composition_text=A5_COMPOSITION, **WAVE14_CASE)
    elapsed = time.perf_counter() - started
    message = str(error.value)
    assert "более чем в полтора раза" in message
    assert "в наших опытах не сходился" in message
    assert "барьер" not in message
    assert elapsed < 60.0, elapsed


def test_run_precipitation_refuses_grain_boundary_case_a5_before_solving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BL-32, границы зёрен: тот же состав, барьер kawin неположителен.

    γ_gb 0,02 Дж/м² — чтобы пройти проверку отношения энергий
    (γ_gb / 2γ = 0,43 < 1); источника у числа нет.
    """

    _forbid_solve(monkeypatch)
    case = dict(WAVE14_CASE, nucleation_type="GRAIN BOUNDARIES", gb_energy=0.02)
    with pytest.raises(ValueError) as error:
        _run_demo(composition_text=A5_COMPOSITION, **case)
    assert "барьер зарождения на границах зёрен обращается в ноль" in str(error.value)


def test_run_precipitation_boundary_from_both_sides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Порог на штатном пути: γ чуть больше пороговой — предупреждение, чуть меньше — отказ.

    r* до зажима пропорционален γ при той же движущей силе, поэтому пороговая
    γ = γ₀·u₀/1,5 берётся из оценки А5 при γ₀ = 0,023. До ``solve`` расчёт
    доходит только в первом случае — там ``solve`` бросает ``_SolveReached``.
    """

    floor_nm = _kawin_radius_floor_nm()
    original_estimates = precipitation._nucleus_estimates
    original_check = precipitation._check_critical_radius_floor
    seen: dict[str, list] = {"estimates": [], "warnings": []}

    def estimates(*arguments):
        result = original_estimates(*arguments)
        seen["estimates"].append(result)
        return result

    def check(*arguments):
        result = original_check(*arguments)
        seen["warnings"].append(result)
        return result

    monkeypatch.setattr(precipitation, "_nucleus_estimates", estimates)
    monkeypatch.setattr(precipitation, "_check_critical_radius_floor", check)
    _forbid_solve(monkeypatch, _SolveReached)

    with pytest.raises(ValueError, match="более чем в полтора раза"):
        _run_demo(composition_text=A5_COMPOSITION, **WAVE14_CASE)
    ratio_at_default = floor_nm / seen["estimates"][-1][0][3]
    threshold_gamma = WAVE14_CASE["gamma"] * ratio_at_default / precipitation.CRITICAL_RADIUS_REFUSAL_RATIO

    with pytest.raises(_SolveReached):
        _run_demo(composition_text=A5_COMPOSITION, **dict(WAVE14_CASE, gamma=threshold_gamma * (1 + 1e-3)))
    assert len(seen["warnings"][-1]) == 1, seen["warnings"][-1]
    assert "модель считает зарождение от этого предела" in seen["warnings"][-1][0]

    with pytest.raises(ValueError, match="более чем в полтора раза"):
        _run_demo(composition_text=A5_COMPOSITION, **dict(WAVE14_CASE, gamma=threshold_gamma * (1 - 1e-3)))


def test_run_precipitation_warns_and_solves_on_the_ni_section_default() -> None:
    """Умолчание Ni-раздела (Ni-15Al ат. %, ``DEFAULTS["ni"]``): u = 1,12 — считается с предупреждением."""

    matrix, precipitate, temperature_c, _hours, gamma, matrix_vm, precip_vm = precipitation.DEFAULTS["ni"]
    result = _run_demo(
        composition_text="AL=15", units="at", matrix_phase=matrix, precipitate_phase=precipitate,
        temperature_c=temperature_c, duration_h=0.001, gamma=gamma, matrix_vm=matrix_vm,
        precip_vm=precip_vm, cmin_nm=0.2, cmax_nm=10.0, bins=80,
    )
    assert (result.quality["Статус"] == "пройдена").all(), result.quality
    radius = [warning for warning in result.warnings if "модель считает зарождение от этого предела" in warning]
    assert len(radius) == 1, result.warnings
    assert "800.0 °C" in radius[0]


def test_run_precipitation_still_solves_five_solutes_of_ladder_b() -> None:
    """Встречный тест BL-32 и BL-21: ступень Б5 14-А считается штатным путём.

    Критический радиус 0,373 нм — выше предела kawin, ни отказа, ни
    предупреждения о радиусе. Пять добавок — внутри нового предела;
    предупреждение о времени стоит в ``warnings`` рядом с сообщением о правке
    подвижности ниобия.
    """

    result = _run_demo(composition_text="CR=19, NB=5.1, TI=0.9, AL=0.5, FE=0.5", **WAVE14_CASE)
    assert (result.quality["Статус"] == "пройдена").all(), result.quality
    # 14-А, ступень Б5 (сборка из частей): 328 строк, доля 6,749 %.
    assert len(result.kinetics) == 328
    assert result.kinetics["Объёмная доля, %"].iloc[-1] == pytest.approx(6.749, abs=1e-3)
    assert precipitation.KWN_LONG_COMPOSITION_WARNING.format(count=5) in result.warnings
    assert any("ниобия" in warning for warning in result.warnings), result.warnings
    assert not any("предела модели" in warning for warning in result.warnings), result.warnings


def _numeric_outputs(result) -> dict[str, bytes]:
    """Все числа расчёта KWN в побайтово сравнимом виде."""

    import io

    outputs = {
        name: getattr(result, name).to_csv(float_format="%.17g", lineterminator="\n").encode()
        for name in ("kinetics", "summary", "matrix_composition", "interface_composition", "psd")
    }
    # Сам zip в ``npz`` несёт время записи, поэтому сравниваются массивы.
    with np.load(io.BytesIO(result.npz), allow_pickle=False) as arrays:
        for key in sorted(arrays.files):
            array = np.ascontiguousarray(arrays[key])
            outputs[f"npz:{key}"] = f"{array.dtype}|{array.shape}|".encode() + array.tobytes()
    return outputs


def test_nucleus_estimate_does_not_change_kinetics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Оценка зародыша до расчёта не меняет ни одного числа расчёта.

    Волна 13-Р нашла, что оценка на объектах самого расчёта (``setup()`` и
    движущая сила на общей модели) сдвигала кинетику до 6·10⁻⁸ относительных
    даже с ``removeCache=True``. Теперь оценка идёт на своей модели; тест
    считает один и тот же расчёт с оценкой и с выключенной оценкой и требует
    побайтового совпадения всех таблиц и массивов модели.
    """

    original = precipitation._nucleus_estimates
    calls: list[list[tuple[float, ...]]] = []

    def recorded(model, precipitate_phase, temperatures_k):
        estimates = original(model, precipitate_phase, temperatures_k)
        calls.append(estimates)
        return estimates

    monkeypatch.setattr(precipitation, "_nucleus_estimates", recorded)
    with_estimate = _run_demo()
    # Оценка действительно посчитана, а не проглочена исключением:
    # критический радиус γ′ при 800 °C — 0,797 нм (13-Д).
    assert len(calls) == 1 and len(calls[0]) == 1, calls
    assert calls[0][0][1] == pytest.approx(0.797, abs=5e-3)

    monkeypatch.setattr(precipitation, "_nucleus_estimates", lambda *arguments: [])
    without_estimate = _run_demo()

    first = _numeric_outputs(with_estimate)
    second = _numeric_outputs(without_estimate)
    assert first.keys() == second.keys()
    differing = [name for name in first if first[name] != second[name]]
    assert not differing, f"оценка зародыша изменила: {differing}"
