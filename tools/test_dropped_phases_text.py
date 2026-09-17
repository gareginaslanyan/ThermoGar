#!/usr/bin/env python3
"""Текст предупреждения о фазах вне быстрого набора (BL-8, волна 15-Л).

Проверяется только форматирование: сколько имён называет предупреждение,
что дописывается при длинном списке и что попадает в раскрывающийся блок.
Приложение не запускается, равновесия не считаются.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -X utf8 -m pytest ^
        tools/test_dropped_phases_text.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from thermogar_release_policy import (
    DROPPED_PHASES_SHOWN,
    dropped_phases_expander_label,
    dropped_phases_full_list,
    dropped_phases_warning,
)

TAIL = (
    "Если какая-то из них устойчива на вашем составе, быстрый режим её не "
    "покажет — сверьтесь в режиме «все фазы базы»."
)


def test_three_phases_are_named_in_full() -> None:
    dropped = ["BCC_A2", "HCP_A3", "LAVES_PHASE"]

    assert dropped_phases_warning(dropped) == (
        "Быстрый набор не рассматривает часть фаз, совместимых с составом, — "
        "всего 3: BCC_A2, HCP_A3, LAVES_PHASE. " + TAIL
    )
    assert dropped_phases_full_list(dropped) == "BCC_A2, HCP_A3, LAVES_PHASE"


def test_twenty_phases_show_five_names_and_the_rest_in_the_block() -> None:
    dropped = [f"PHASE_{index:02d}" for index in range(1, 21)]
    text = dropped_phases_warning(dropped)

    assert DROPPED_PHASES_SHOWN == 5
    assert text == (
        "Быстрый набор не рассматривает часть фаз, совместимых с составом, — "
        "всего 20: PHASE_01, PHASE_02, PHASE_03, PHASE_04, PHASE_05 и ещё 15. "
        + TAIL + " Полный перечень — в блоке ниже."
    )
    for name in dropped[DROPPED_PHASES_SHOWN:]:
        assert name not in text
    assert dropped_phases_expander_label(len(dropped)) == (
        "Все фазы вне быстрого набора (20)"
    )
    assert dropped_phases_full_list(dropped) == ", ".join(dropped)
