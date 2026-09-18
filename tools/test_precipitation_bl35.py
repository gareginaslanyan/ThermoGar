#!/usr/bin/env python3
"""Внятный отказ расчёта выделений при нарушенном балансе масс (BL-35).

На сплаве 718 (волна 15-В) модель зарождает частицы практически без барьера,
баланс масс выводит состав матрицы за границы, и pycalphad на следующем
локальном равновесии делит на ноль. Приложение должно вернуть посчитанную
часть и ошибку проверки «Состав матрицы допустим», а не исключение.

Разбор — ``tasks/WAVE15_D_REPORT.md``.

Запуск (пофайлово):
    <root>/.venv-windows/Scripts/python.exe -B -X utf8 -m pytest tools/test_precipitation_bl35.py -q
"""

from __future__ import annotations

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

COMPOSITION_CHECK = "Состав матрицы допустим"


def _model(rows: list[list[float]]) -> SimpleNamespace:
    composition = np.asarray(rows, float)
    data = SimpleNamespace(
        n=len(rows) - 1,
        composition=composition,
        time=np.arange(len(rows), dtype=float),
    )
    return SimpleNamespace(data=data)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ([0.10, 0.20], None),
        ([0.10, 0.00], ("CR", 0.0)),
        ([0.10, -1e-12], ("CR", -1e-12)),
        ([1.20, 0.10], ("NB", 1.2)),
        ([0.70, 0.50], ("NI", pytest.approx(-0.2))),
        ([np.nan, 0.10], ("NB", pytest.approx(np.nan, nan_ok=True))),
    ],
)
def test_violation_is_mass_balance_without_threshold(row, expected) -> None:
    found = precipitation._matrix_composition_violation(row, ["NB", "CR"], "NI", [0.1, 0.1])
    assert found == expected


def test_solute_absent_from_start_may_stay_zero() -> None:
    assert precipitation._matrix_composition_violation([0.1, 0.0], ["NB", "CR"], "NI", [0.1, 0.0]) is None


def test_stop_condition_fires_on_first_bad_step_and_resets() -> None:
    condition = precipitation._MatrixCompositionStop(["NB", "CR"], "NI", [0.1, 0.1])
    condition.testCondition(_model([[0.1, 0.1], [0.05, 0.1]]))
    assert not condition.isSatisfied()
    condition.testCondition(_model([[0.1, 0.1], [0.05, 0.1], [0.0, 0.1]]))
    assert condition.isSatisfied()
    assert (condition.satisfiedTime(), condition.element, condition.value) == (2.0, "NB", 0.0)
    # Первое срабатывание не перезаписывается следующими шагами.
    condition.testCondition(_model([[0.1, 0.1], [0.05, 0.1], [0.0, 0.1], [0.0, 1.5]]))
    assert condition.element == "NB"
    condition.reset()
    assert not condition.isSatisfied()


def test_only_pycalphad_division_is_recognised() -> None:
    fake = compile("1/0", "site-packages/pycalphad/core/minimizer.pyx", "exec")
    with pytest.raises(ZeroDivisionError) as inside:
        exec(fake, {})
    assert precipitation._raised_in_pycalphad(inside.value)
    with pytest.raises(ZeroDivisionError) as outside:
        1 / 0  # noqa: B018
    assert not precipitation._raised_in_pycalphad(outside.value)


def test_quality_reports_stop_note_as_error() -> None:
    data = SimpleNamespace(
        time=np.array([0.0, 1.0]),
        temperature=np.array([1000.0, 1000.0]),
        volFrac=np.zeros((2, 1)),
        Ravg=np.zeros((2, 1)),
        precipitateDensity=np.zeros((2, 1)),
        composition=np.array([[0.1], [0.1]]),
    )
    passed = precipitation._quality(data, 0, 1)
    row = passed[passed["Проверка"] == COMPOSITION_CHECK].iloc[0]
    assert row["Статус"] == "пройдена"
    stopped = precipitation._quality(data, 0, 1, stop_note="остановлен")
    row = stopped[stopped["Проверка"] == COMPOSITION_CHECK].iloc[0]
    assert (row["Статус"], row["Примечание"]) == ("ошибка", "остановлен")


def test_718_run_ends_with_quality_error_not_exception() -> None:
    """Случай 15-В: 718, 700 °C, 95 мДж/м².

    Без метки slow: с остановкой по составу считается 43 с (замер 15-Д), пик
    памяти 0,35 ГиБ.
    """

    pytest.importorskip("kawin")
    import study_wave15_v_718 as study

    result = precipitation.run_precipitation(**study.case_arguments(700.0, 95.0, study.GRID))
    row = result.quality[result.quality["Проверка"] == COMPOSITION_CHECK].iloc[0]
    assert row["Статус"] == "ошибка"
    assert row["Примечание"] == result.stop_note
    assert result.stop_note.startswith(("Расчёт остановлен", "Расчёт прерван"))
    assert "LIMITS_OF_APPLICABILITY" in result.stop_note
    # Посчитанная часть не пропала, и до горизонта 100 ч расчёт не дошёл.
    time_s = result.kinetics["Время, с"].to_numpy()
    assert len(time_s) > 100
    assert time_s[-1] < 100 * 3600
