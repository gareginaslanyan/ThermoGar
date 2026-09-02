"""Цветовые роли и стили графиков ThermoGar.

Палитра основана на HIG_RULES.md проекта. Экранный код не должен содержать
HEX-литералы: все смысловые цвета живут здесь.
"""

from __future__ import annotations

from itertools import cycle
from typing import Iterable


# Светлая тема
LIGHT = {
    "background": "#FFFFFF",
    "surface": "#F1EFEA",
    "grid": "#D8D4CC",
    "axis": "#57534A",
    "text": "#2A2722",
    "primary": "#1F60C1",
    "primary_dark": "#0D2768",
    "primary_light": "#4587DE",
    "muted": "#8A857A",
    "danger": "#A62A1E",
    "danger_sign": "#C93425",
    "info_fill": "#EFF6FA",
}

# Тёмная тема
DARK = {
    "background": "#1A1816",
    "surface": "#24211D",
    "grid": "#3A362F",
    "axis": "#C7C1B6",
    "text": "#F1EFEA",
    "primary": "#5C97E8",
    "primary_dark": "#4587DE",
    "primary_light": "#B4D1EE",
    "muted": "#8A857A",
    "danger": "#F06157",
    "danger_sign": "#F06157",
    "info_fill": "#16233B",
}

# Категориальная палитра: сначала два синих ряда, затем допустимые цвета
# Okabe–Ito с контрастом >= 3:1 к белому.
LIGHT_SERIES = (
    "#0D2768",
    "#4587DE",
    "#000000",
    "#D55E00",
    "#009E73",
    "#CC79A7",
    "#0072B2",
)

DARK_SERIES = (
    "#4587DE",
    "#B4D1EE",
    "#F1EFEA",
    "#F5A79F",
    "#8FE0B4",
    "#E8B200",
    "#9CC0F2",
)

LINE_STYLES = ("-", "--", "-.", ":")
MARKERS = ("o", "s", "^", "D", "v", "P", "X")


def chart_roles(theme_type: str | None = None) -> dict[str, str]:
    """Вернуть роли графика для светлой или тёмной темы."""
    return DARK if str(theme_type).lower() == "dark" else LIGHT


def phase_styles(
    phases: Iterable[str],
    theme_type: str | None = None,
) -> dict[str, dict[str, str]]:
    """Назначить фазам устойчивую комбинацию цвета, линии и маркера."""
    colors = DARK_SERIES if str(theme_type).lower() == "dark" else LIGHT_SERIES
    color_cycle = cycle(colors)
    line_cycle = cycle(LINE_STYLES)
    marker_cycle = cycle(MARKERS)

    result: dict[str, dict[str, str]] = {}
    for phase in sorted(dict.fromkeys(str(item) for item in phases)):
        result[phase] = {
            "color": next(color_cycle),
            "linestyle": next(line_cycle),
            "marker": next(marker_cycle),
        }
    return result
