#!/usr/bin/env python3
"""21-Х: текст остановки выделений по варианту А и номер выпуска 0.5.0.

Вариант А (решение владельца 26.09.2026): слова «, баланс масс нарушен»
показываются только при разрыве баланса масс (``stop_diagnostics["kind"]``
== "разрыв"); при перелёте баланс до остановки выполнялся, и их нет.

Запуск (пофайлово):
    <root>/.venv-windows/Scripts/python.exe -B -X utf8 -m pytest tools/test_wave21_x.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for entry in (ROOT / "app", ROOT / "tools"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import thermogar_precipitation as precipitation
from thermogar_release_policy import APP_VERSION

BROKEN = "баланс масс нарушен"


@pytest.mark.parametrize(("value", "words"), [(-9.864e-5, "ушла ниже нуля"), (0.0, "стала 0 ат.%")])
def test_overshoot_note_has_no_broken_balance(value: float, words: str) -> None:
    note = precipitation._composition_stop_note(3.885, "TI", value, "перелёт")
    assert f"в матрице {words}. Показана часть расчёта до остановки." in note
    assert BROKEN not in note
    assert note.endswith(precipitation.KWN_COMPOSITION_STOP_CAUSE)


@pytest.mark.parametrize(("value", "words"), [(-9.864e-5, "ушла ниже нуля"), (0.0, "стала 0 ат.%")])
def test_broken_balance_note_keeps_the_words(value: float, words: str) -> None:
    note = precipitation._composition_stop_note(3.885, "TI", value, "разрыв")
    assert f"в матрице {words}, {BROKEN}. Показана часть расчёта до остановки." in note


def test_718_stop_is_overshoot_without_broken_balance() -> None:
    """Случай 15-В, как в ``test_precipitation_bl35.py``: 718, 700 °C, 95 мДж/м²."""

    pytest.importorskip("kawin")
    import study_wave15_v_718 as study

    result = precipitation.run_precipitation(**study.case_arguments(700.0, 95.0, study.GRID))
    assert result.stop_diagnostics["kind"] == "перелёт"
    assert result.stop_note.startswith("Расчёт остановлен")
    assert BROKEN not in result.stop_note


def test_release_number_and_guide() -> None:
    assert APP_VERSION == "0.5.0"
    assert (ROOT / "docs" / "guide" / "ThermoGar_Guide_0.5.0.html").is_file()
