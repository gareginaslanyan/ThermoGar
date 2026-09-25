#!/usr/bin/env python3
"""BL-43 (22-Б): ограничение роста шага KWN, страховка minComposition,
условие остановки BL-35 по составу до зажима и признак «перелёт / разрыв».

На стали (BCC_A2 / M23C6, 700 °C) kawin 0.5.0 отпускал шаг по времени в
5–42 раза за раз, стадия RK4 уводила углерод матрицы ниже нуля, kawin
зажимал его в 0, и при нуле движущая сила M23C6 не определена — расчёт шёл в
остановку BL-35. Разбор — ``tasks/WAVE22_A_REPORT.md``, правка и проверка —
``tasks/WAVE22_B_REPORT.md``.

Запуск (пофайлово):
    <root>/.venv-windows/Scripts/python.exe -B -X utf8 -m pytest tools/test_kwn_step_cap_22b.py -q
"""

from __future__ import annotations

import io
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

SOLUTES = ["C", "CR"]
X0 = np.array([0.0092, 0.1216])


def _model(fraction: list[float], fconc: list[list[float]], recorded: list[list[float]] | None = None) -> SimpleNamespace:
    """Синтетическая история kawin: доля выделений, fconc и записанный состав по шагам.

    Без ``recorded`` записанный состав — из баланса масс, как у kawin, с
    зажимом отрицательного в ``KWN_MIN_COMPOSITION``.
    """

    volume = np.asarray(fraction, float)[:, None]
    solute = np.asarray(fconc, float)[:, None, :]
    if recorded is None:
        raw = (X0 - solute[:, 0, :])/(1.0 - volume)
        composition = np.where(raw < 0.0, precipitation.KWN_MIN_COMPOSITION, raw)
    else:
        composition = np.asarray(recorded, float)
    composition[0] = X0
    data = SimpleNamespace(
        n=len(fraction) - 1,
        time=np.arange(len(fraction), dtype=float),
        composition=composition,
        volFrac=volume,
        fconc=solute,
    )
    return SimpleNamespace(data=data)


def _condition() -> precipitation._MatrixCompositionStop:
    return precipitation._MatrixCompositionStop(SOLUTES, "FE", X0)


# --------------------------------------------------------------------------- #
# Ограничение роста шага и minComposition
# --------------------------------------------------------------------------- #


def test_step_growth_limit_caps_kawin_step(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("kawin")
    model_class = precipitation._StepLimitedPrecipitateModel
    limit = model_class.DT_GROWTH_LIMIT
    assert limit == precipitation.KWN_DT_GROWTH_LIMIT
    assert limit > 1.0
    proposed = [100.0]
    monkeypatch.setattr(precipitation.PrecipitateModel, "getDt", lambda self, dXdt: proposed[0])
    model = model_class.__new__(model_class)
    # Предыдущий шаг 0,5 с: kawin предлагает 100 с — берётся limit × 0,5 с.
    model.data = SimpleNamespace(n=2, time=np.array([0.0, 0.25, 0.75]))
    assert model.getDt(None) == pytest.approx(limit*0.5)
    # Шаг kawin меньше предела — остаётся его.
    proposed[0] = 0.1
    assert model.getDt(None) == pytest.approx(0.1)
    # Первый шаг: предыдущего нет, шаг — за kawin.
    proposed[0] = 100.0
    model.data = SimpleNamespace(n=0, time=np.array([0.0]))
    assert model.getDt(None) == pytest.approx(100.0)


def test_run_uses_step_limit_and_min_composition(monkeypatch: pytest.MonkeyPatch) -> None:
    """Сталь BCC_A2 / M23C6, 700 °C — ячейка BL-43 (40 классов, 0,2–10 нм,
    bulk_n0 1e28), но 0,05 с вместо 3,6 с (≈ 10 с счёта): модель — подкласс с
    ограничением шага, minComposition = 1e-8, шаг после первого растёт не
    больше чем в ``DT_GROWTH_LIMIT`` раз, и предел в расчёте срабатывает
    (на зарождении, около 0,03 с модельного времени)."""

    pytest.importorskip("kawin")
    from thermogar_release_policy import RELEASE_DATABASE_LABELS, RELEASE_DATABASE_RELATIVE_PATHS

    model_class = precipitation._StepLimitedPrecipitateModel
    models: list[object] = []
    binding: list[bool] = []
    original_solve = model_class.solve
    original_parent_get_dt = precipitation.PrecipitateModel.getDt

    def solve(self, *args, **kwargs):
        models.append(self)
        return original_solve(self, *args, **kwargs)

    def parent_get_dt(self, dXdt):
        dt = original_parent_get_dt(self, dXdt)
        n = int(self.data.n)
        if n > 0:
            binding.append(dt > self.DT_GROWTH_LIMIT*float(self.data.time[n] - self.data.time[n - 1]))
        return dt

    monkeypatch.setattr(model_class, "solve", solve)
    monkeypatch.setattr(precipitation.PrecipitateModel, "getDt", parent_get_dt)
    result = precipitation.run_precipitation(
        db=object(),
        database_path=ROOT / RELEASE_DATABASE_RELATIVE_PATHS["fe"],
        database_label=RELEASE_DATABASE_LABELS["fe"],
        database_key="fe",
        balance="FE",
        composition_text="C=0.20, Cr=11.5, Ni=0.7",
        units="wt",
        matrix_phase="BCC_A2",
        precipitate_phase="M23C6",
        schedule_mode="isothermal",
        temperature_c=700.0,
        duration_h=0.05/3600.0,
        profile_text="",
        gamma=0.3,
        matrix_vm=7.09,
        precip_vm=7.09,
        nucleation_type="BULK",
        bulk_n0=1e28,
        grain_size_um=100.0,
        dislocation_density=5e12,
        gb_energy=0.3,
        cmin_nm=0.2,
        cmax_nm=10.0,
        bins=40,
        input_provenance="SYNTHETIC_22B_STEP_LIMIT_TEST",
        input_confirmation=True,
    )
    assert len(models) == 1
    model = models[0]
    assert isinstance(model, model_class)
    assert model.constraints.minComposition == precipitation.KWN_MIN_COMPOSITION == 1e-8
    assert result.stop_note == "" and result.stop_diagnostics == {}
    with np.load(io.BytesIO(result.npz)) as archive:
        time = np.asarray(archive["time"], float)
    dt = np.diff(time)
    # Первый шаг — за kawin; последний может быть короче (упор в конец выдержки).
    assert np.all(dt[1:] <= model_class.DT_GROWTH_LIMIT*dt[:-1]*(1.0 + 1e-12))
    # Предел срабатывал: kawin предлагал шаг длиннее, чем разрешено.
    assert any(binding)


# --------------------------------------------------------------------------- #
# Условие остановки BL-35 по составу до зажима
# --------------------------------------------------------------------------- #


def test_stop_fires_when_precipitates_hold_all_solute() -> None:
    """Σ fconc ≥ x0: состав до зажима ≤ 0, записанный — зажат в 1e-8."""

    history = _model(
        [0.0, 0.03, 0.04],
        [[0.0, 0.0], [0.006, 0.02], [1.0005*X0[0], 0.03]],
    )
    recorded = history.data.composition[2]
    assert recorded[0] == precipitation.KWN_MIN_COMPOSITION
    # Проверка по записанному составу этого шага не видит.
    assert precipitation._matrix_composition_violation(recorded, SOLUTES, "FE", X0) is None
    condition = _condition()
    history.data.n = 1
    condition.testCondition(history)
    assert not condition.isSatisfied()
    history.data.n = 2
    condition.testCondition(history)
    assert condition.isSatisfied()
    assert condition.element == "C" and condition.step == 2 and condition.satisfiedTime() == 2.0
    assert condition.value == pytest.approx((X0[0] - 1.0005*X0[0])/(1.0 - 0.04))
    assert condition.value < 0.0


def test_stop_fires_when_precipitates_hold_exactly_all_solute() -> None:
    history = _model([0.0, 0.04], [[0.0, 0.0], [X0[0], 0.03]])
    condition = _condition()
    condition.testCondition(history)
    assert condition.isSatisfied()
    assert (condition.element, condition.value) == ("C", 0.0)


def test_stop_does_not_fire_on_small_positive_matrix_content() -> None:
    """Состав матрицы 1e-8 из баланса масс — это ещё не нарушение."""

    fraction = 0.04
    fconc_c = X0[0] - (1.0 - fraction)*precipitation.KWN_MIN_COMPOSITION
    history = _model([0.0, fraction], [[0.0, 0.0], [fconc_c, 0.03]])
    assert history.data.composition[1][0] == pytest.approx(precipitation.KWN_MIN_COMPOSITION)
    condition = _condition()
    condition.testCondition(history)
    assert not condition.isSatisfied()


def test_solute_absent_from_alloy_is_checked_as_recorded() -> None:
    """Добавки не было в сплаве: след в выделении не останавливает расчёт."""

    initial = np.array([0.0092, 0.0])
    data = SimpleNamespace(
        n=1,
        time=np.array([0.0, 1.0]),
        composition=np.array([[0.0092, 0.0], [0.005, precipitation.KWN_MIN_COMPOSITION]]),
        volFrac=np.array([[0.0], [0.02]]),
        fconc=np.array([[[0.0, 0.0]], [[0.0092 - 0.98*0.005, 1e-12]]]),
    )
    condition = precipitation._MatrixCompositionStop(SOLUTES, "FE", initial)
    condition.testCondition(SimpleNamespace(data=data))
    assert not condition.isSatisfied()


def test_stop_fires_when_matrix_is_used_up() -> None:
    """Σ f = 1: kawin состав не пересчитывает, состав до зажима не определён."""

    history = _model([0.0, 1.0], [[0.0, 0.0], [0.2, 0.5]], recorded=[[0.0, 0.0], [0.004, 0.1]])
    condition = _condition()
    condition.testCondition(history)
    assert condition.isSatisfied()
    assert not np.isfinite(condition.value) or condition.value <= 0.0


# --------------------------------------------------------------------------- #
# Признак «перелёт / разрыв»
# --------------------------------------------------------------------------- #


def test_balance_kept_before_stop_is_overshoot() -> None:
    """Баланс до остановки сходится с точностью округления — «перелёт»."""

    history = _model(
        [0.0, 0.01, 0.03, 0.04],
        [[0.0, 0.0], [0.002, 0.005], [0.007, 0.015], [1.2*X0[0], 0.02]],
    )
    diagnostics = precipitation._stop_diagnostics(history.data, 3, 3, SOLUTES, "состав матрицы", "C", -0.1)
    assert diagnostics["kind"] == "перелёт"
    assert diagnostics["residual_max_rel"] <= precipitation.KWN_BALANCE_RESIDUAL_LIMIT
    assert diagnostics["raw_composition"]["C"] < 0.0
    assert diagnostics["recorded_composition"]["C"] == precipitation.KWN_MIN_COMPOSITION
    # Сам шаг остановки (с зажатым составом) в невязку не входит, а если бы
    # входил, признак был бы другим.
    residual_with_stop, element = precipitation._balance_residual(history.data, 4)
    assert residual_with_stop > precipitation.KWN_BALANCE_RESIDUAL_LIMIT and SOLUTES[element] == "C"


def test_balance_broken_before_stop_is_gap() -> None:
    """Невязка на шаге до остановки больше 1e-12·x0 — «разрыв»."""

    history = _model(
        [0.0, 0.01, 0.03, 0.04],
        [[0.0, 0.0], [0.002, 0.005], [0.007, 0.015], [1.2*X0[0], 0.02]],
    )
    history.data.composition[2, 1] *= 1.0 + 1e-9
    diagnostics = precipitation._stop_diagnostics(history.data, 3, 3, SOLUTES, "состав матрицы", "C", -0.1)
    assert diagnostics["kind"] == "разрыв"
    assert diagnostics["residual_element"] == "CR"
    assert diagnostics["residual_max_rel"] > precipitation.KWN_BALANCE_RESIDUAL_LIMIT
