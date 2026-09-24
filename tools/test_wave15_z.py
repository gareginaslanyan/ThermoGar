#!/usr/bin/env python3
"""Волна 15-З: BL-26, BL-24 и текст отказа BL-35 на экране.

* BL-26 — зародыш крупнее начального ``cMax`` сетки: предупреждение в
  ``PrecipitationResult.warnings``, расчёт не останавливается (решение мастера
  13-Ф2). Опыт 13-Ф: Ni–9,8Al–8,3Cr ат. %, γ/γ′, 800 °C, радиус зародыша
  1,02 нм; при ``cMax`` 0,5 нм предупреждение есть, при 2,0 нм — нет.
* BL-24 — пустое решение pycalphad (все NP — NaN, фаз нет) не проходит молча:
  точка помечается несошедшейся, на экране — понятный текст.
* BL-35 — текст отказа ``stop_note`` показан над вкладками раздела кинетики.

Разбор — ``tasks/WAVE15_Z_REPORT.md``.

Запуск (пофайлово):
    <root>/.venv-windows/Scripts/python.exe -B -X utf8 -m pytest tools/test_wave15_z.py -q
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
for entry in (ROOT / "app", ROOT / "tools"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import thermogar_precipitation as precipitation

NI_DATABASE = ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"


# --------------------------------------------------------------------------- #
# BL-26
# --------------------------------------------------------------------------- #


def _estimate(rnuc_nm: float, temperature_k: float = 1073.15) -> tuple[float, float, float, float]:
    return (temperature_k, 0.8, rnuc_nm, 0.8)


BL26_TEXT_1_02 = (
    "Радиус зародыша 1.02 нм (оценка при 800.0 °C) больше начального максимального "
    "радиуса сетки 0.5 нм, поэтому первые зародыши записываются мельче своего размера, "
    "пока модель не расширит сетку размеров. Итоговые доля, радиус и число частиц от этого почти "
    "не меняются, но начало зарождения на графиках искажено: доля и радиус занижены, "
    "число частиц завышено. Задайте «Начальный максимальный радиус» больше 1.02 нм."
)


def test_nucleus_above_grid_gives_the_approved_text() -> None:
    assert precipitation._check_nucleus_above_grid([_estimate(1.0236)], 0.5) == [BL26_TEXT_1_02]


@pytest.mark.parametrize("cmax_nm", (2.0, 1.0236))
def test_nucleus_inside_grid_is_silent(cmax_nm: float) -> None:
    assert precipitation._check_nucleus_above_grid([_estimate(1.0236)], cmax_nm) == []


def test_nucleus_above_grid_is_silent_without_estimates() -> None:
    assert precipitation._check_nucleus_above_grid([], 0.5) == []


def test_nucleus_above_grid_takes_the_largest_nucleus_of_a_profile() -> None:
    """Наибольший радиус по температурам, а не наименьший, как у проверки cMin."""

    estimates = [_estimate(0.9, 1023.15), _estimate(1.4, 1123.15), _estimate(1.1, 1073.15)]
    warnings = precipitation._check_nucleus_above_grid(estimates, 1.2)
    assert len(warnings) == 1
    assert warnings[0].startswith("Радиус зародыша 1.4 нм (оценка при 850.0 °C)")
    assert warnings[0].endswith("больше 1.4 нм.")
    assert precipitation._check_nucleus_above_grid(estimates, 1.4) == []


def _run_wave13_f(cmax_nm: float):
    """Постановка 13-Ф, п. 2; горизонт 1 мс — до первых зародышей (0,02 с)."""

    pytest.importorskip("kawin")
    if not NI_DATABASE.is_file():
        pytest.skip(f"Нет базы: {NI_DATABASE}")
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    return precipitation.run_precipitation(
        db=object(),
        database_path=NI_DATABASE,
        database_label=RELEASE_DATABASE_LABELS["ni"],
        database_key="ni",
        balance="NI",
        composition_text="AL=9.8, CR=8.3",
        units="at",
        matrix_phase="FCC_A1",
        precipitate_phase="GAMMA_PRIME",
        schedule_mode="isothermal",
        temperature_c=800.0,
        duration_h=1.0e-3 / 3600.0,
        profile_text="",
        gamma=0.023,
        matrix_vm=6.5662724928,
        precip_vm=6.5662724928,
        nucleation_type="BULK",
        bulk_n0=1e30,
        grain_size_um=100.0,
        dislocation_density=5e12,
        gb_energy=0.3,
        cmin_nm=0.05,
        cmax_nm=cmax_nm,
        bins=150,
        input_provenance="SYNTHETIC_WAVE15_Z_NOT_MATERIAL_INPUT",
        input_confirmation=True,
    )


def test_run_precipitation_warns_when_nucleus_exceeds_cmax() -> None:
    result = _run_wave13_f(0.5)
    assert result.warnings == [BL26_TEXT_1_02]
    # Предупреждение, не отказ: расчёт дошёл до конца, проверки пройдены.
    assert result.stop_note == ""
    assert (result.quality["Статус"] == "пройдена").all(), result.quality
    assert result.kinetics["Время, с"].iloc[-1] == pytest.approx(1.0e-3)


def test_run_precipitation_is_silent_when_cmax_covers_nucleus() -> None:
    result = _run_wave13_f(2.0)
    assert result.warnings == []
    assert (result.quality["Статус"] == "пройдена").all(), result.quality


# --------------------------------------------------------------------------- #
# BL-24
# --------------------------------------------------------------------------- #


class _Values:
    def __init__(self, values) -> None:
        self.values = np.asarray(values)


class _FakeEquilibrium:
    """Минимум ``xarray``-результата pycalphad, который читает ``_default_backend``."""

    def __init__(self, phases, fractions, compositions) -> None:
        self.Phase = _Values([phases])
        self.NP = _Values([fractions])
        self._x = {element: _Values([column]) for element, column in compositions.items()}

    @property
    def X(self):
        return SimpleNamespace(sel=lambda component: self._x[component])


class _FakeDatabase:
    refstates = {"AL": {"mass": 26.9815385}, "NI": {"mass": 58.6934}}


def _call(temperature_k: float = 1023.15):
    import thermogar_verified_equilibrium as adapter

    return adapter.EquilibriumCall(
        feature_id="equilibrium_single",
        call_index=1,
        axis_value=temperature_k,
        temperature_k=temperature_k,
        pressure_pa=101325.0,
        balance="NI",
        components=("AL", "NI", "VA"),
        atomic_fractions=(("AL", 0.15), ("NI", 0.85)),
        mass_fractions=(("AL", 0.0750), ("NI", 0.9250)),
        phases=("FCC_A1", "GAMMA_PRIME", "LIQUID"),
    )


def _backend_with(monkeypatch: pytest.MonkeyPatch, fake: _FakeEquilibrium):
    pycalphad = pytest.importorskip("pycalphad")
    import thermogar_verified_equilibrium as adapter

    monkeypatch.setattr(pycalphad, "equilibrium", lambda *args, **kwargs: fake)
    return adapter._default_backend(_FakeDatabase(), _call())


def _empty(fractions) -> _FakeEquilibrium:
    nan = float("nan")
    return _FakeEquilibrium(
        ["", "", ""], fractions, {"AL": [nan, nan, nan], "NI": [nan, nan, nan]}
    )


@pytest.mark.parametrize(
    "fractions",
    (
        [float("nan")] * 3,  # узел 12-4: все NP — NaN
        [0.0, float("nan"), float("nan")],
        [5e-7, float("nan"), float("nan")],
    ),
)
def test_empty_solution_is_marked_as_not_converged(monkeypatch: pytest.MonkeyPatch, fractions) -> None:
    import thermogar_verified_loaders as vl

    fake = _empty(fractions)
    if fractions[0] == 5e-7:
        fake = _FakeEquilibrium(
            ["FCC_A1", "", ""], fractions,
            {"AL": [0.15, math.nan, math.nan], "NI": [0.85, math.nan, math.nan]},
        )
    with pytest.raises(vl.VerifiedLoaderError) as caught:
        _backend_with(monkeypatch, fake)
    assert caught.value.reason_code is vl.ReasonCode.RESULT_INVALID
    assert caught.value.detail.startswith("EMPTY_SOLUTION: ")
    assert "T=1023.15 K" in caught.value.detail
    assert "did not converge" in caught.value.detail


def test_converged_solution_passes_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeEquilibrium(
        ["FCC_A1", "GAMMA_PRIME", ""],
        [0.75, 0.25, float("nan")],
        {"AL": [0.12, 0.24, math.nan], "NI": [0.88, 0.76, math.nan]},
    )
    result = _backend_with(monkeypatch, fake)
    assert result["phase_fractions"] == {"FCC_A1": 0.75, "GAMMA_PRIME": 0.25}
    assert result["phase_atomic"]["GAMMA_PRIME"]["AL"] == pytest.approx(0.24)


def test_empty_solution_reaches_the_screen_as_one_sentence() -> None:
    import thermogar_stage14 as stage14
    import thermogar_verified_loaders as vl

    error = vl.VerifiedLoaderError(
        vl.ReasonCode.RESULT_INVALID,
        "EMPTY_SOLUTION: phase fractions sum to 0 at T=1023.15 K; the equilibrium did not converge.",
    )
    title, action = stage14._friendly_error_text(error, "равновесие при одной температуре")
    assert title == (
        "Равновесие при 750.0 °C не найдено: pycalphad не нашёл ни одной фазы (сумма "
        "долей фаз равна нулю), поэтому результата нет — попробуйте другую "
        "температуру или состав; на части составов расчёт не сходится, и "
        "соседние точки тоже могут оказаться пустыми."
    )
    assert action == ""


def test_other_result_errors_keep_the_generic_text() -> None:
    import thermogar_stage14 as stage14
    import thermogar_verified_loaders as vl

    error = vl.VerifiedLoaderError(vl.ReasonCode.RESULT_INVALID, "Backend phase fractions do not close to one.")
    title, action = stage14._friendly_error_text(error, "равновесие при одной температуре")
    assert title == "ThermoGar не завершил расчёт."
    # 21-Ж: текст чужого исключения — в «Технических сведениях», не в подсказке.
    assert action == (
        "Проверьте состав, диапазон и набор фаз. Если ошибка повторяется, "
        "скачайте технический отчёт ниже."
    )


# --------------------------------------------------------------------------- #
# BL-35: текст отказа над вкладками
# --------------------------------------------------------------------------- #


def _render_stored_result() -> None:
    """Скрипт AppTest: раздел кинетики с готовым результатом в состоянии сессии."""

    import os
    import sys
    from unittest import mock

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    import streamlit as st

    sys.path.insert(0, os.environ["WAVE15_Z_APP_DIR"])
    import thermogar_precipitation as p

    note = os.environ["WAVE15_Z_STOP_NOTE"]
    frame = pd.DataFrame({"a": [1.0]})
    quality = pd.DataFrame(
        {
            "Проверка": ["Состав матрицы допустим"],
            "Статус": ["ошибка" if note else "пройдена"],
            "Примечание": [note or "Проверка независимых компонентов."],
        }
    )
    figure = plt.figure()
    st.session_state["thermogar_precipitation_result"] = p.PrecipitationResult(
        database_key="ni", phase="GAMMA_PRIME", settings=frame, summary=frame,
        kinetics=frame, matrix_composition=frame, interface_composition=frame,
        psd=frame, quality=quality,
        figures={name: figure for name in ("fraction", "radius_density", "nucleation", "composition", "psd")},
        npz=b"", provenance=b"{}", warnings=["предупреждение расчёта"], stop_note=note,
    )
    with mock.patch.multiple(
        p,
        _composition_vectors=lambda *args: (["NI", "AL"], None, None),
        _matrix_candidates=lambda *args: ["FCC_A1"],
        _compatible_phases=lambda *args: ["FCC_A1", "GAMMA_PRIME"],
        _order_disorder_partner=lambda *args: "",
    ):
        p.render_precipitation_section(
            db=None, database_key="ni", database_path="stub.tdb", database_label="stub",
            project_root=".", current_context={"balance": "NI", "composition": "AL=9.8", "units": "at"},
            render_error=lambda *args, **kwargs: None,
        )


def _app_with_note(monkeypatch: pytest.MonkeyPatch, note: str):
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    monkeypatch.setenv("WAVE15_Z_APP_DIR", str(ROOT / "app"))
    monkeypatch.setenv("WAVE15_Z_STOP_NOTE", note)
    app = streamlit_testing.AppTest.from_function(_render_stored_result, default_timeout=120)
    app.run()
    assert not app.exception, [element.value for element in app.exception]
    return app


def test_stop_note_is_shown_above_the_tabs(monkeypatch: pytest.MonkeyPatch) -> None:
    note = precipitation._composition_stop_note(2.011, "NB", 0.0)
    app = _app_with_note(monkeypatch, note)
    # 21-Ж (часть 3, строка 29): остановка расчёта — уровень error.
    main_errors = [element.value for element in app.main.error]
    assert note in main_errors
    # Над вкладками: в основном блоке, до итога проверок, не внутри вкладки.
    assert main_errors.index(note) < main_errors.index(
        "Одна или несколько внутренних проверок не пройдены."
    )
    for tab in app.tabs:
        assert note not in [element.value for element in tab.error]
    assert "предупреждение расчёта" in [element.value for element in app.main.warning]
    # Строка в таблице проверок осталась.
    assert [element.value for element in app.error] == [
        note,
        "Одна или несколько внутренних проверок не пройдены.",
    ]


def test_no_stop_note_no_extra_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app_with_note(monkeypatch, "")
    warnings = [element.value for element in app.main.warning]
    errors = [element.value for element in app.main.error]
    assert "предупреждение расчёта" in warnings
    assert not any(
        "Расчёт остановлен" in value or "Расчёт прерван" in value
        for value in warnings + errors
    )
    assert [element.value for element in app.success] == ["Внутренние численные проверки пройдены."]
