"""Цветовые роли и стили графиков ThermoGar.

Палитра основана на HIG_RULES.md проекта. Экранный код не должен содержать
HEX-литералы: все смысловые цвета живут здесь.
"""

from __future__ import annotations

from typing import Iterable


# Холодная шкала (оттенок 216°), решение владельца 24.09.2026. Фон графика —
# поверхность: белая на окне #F8F8F9 в светлой теме, #1F2226 на окне #17181B
# в тёмной (А-8).

# Светлая тема
LIGHT = {
    "background": "#FFFFFF",
    "surface": "#ECEDEF",
    "grid": "#CFD1D5",
    "axis": "#4B4F56",
    "text": "#232529",
    "primary": "#1F60C1",
    "primary_dark": "#0D2768",
    "primary_light": "#4587DE",
    "muted": "#79808B",
    "danger": "#A62A1E",
    "danger_sign": "#C93425",
    "info_fill": "#EFF6FA",
    "legend_fill": "#FFFFFF",
    "legend_edge": "#CFD1D5",
}

# Тёмная тема
DARK = {
    "background": "#1F2226",
    "surface": "#25292F",
    "grid": "#33373E",
    "axis": "#BCC2CD",
    "text": "#ECEDEF",
    "primary": "#5C97E8",
    "primary_dark": "#4587DE",
    "primary_light": "#B4D1EE",
    "muted": "#8A92A0",
    "danger": "#F06157",
    "danger_sign": "#F06157",
    "info_fill": "#16233B",
    "legend_fill": "#1F2226",
    "legend_edge": "#33373E",
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
    "#ECEDEF",
    "#F5A79F",
    "#8FE0B4",
    "#E8B200",
    "#9CC0F2",
)

# Семь видов линий (решение владельца 5Б): сплошная, штрих, штрих-пунктир,
# точки, длинный штрих, штрих и две точки, короткий штрих.
LINE_STYLES = (
    "-",
    (0, (7, 4)),
    (0, (8, 3, 2, 3)),
    (0, (2, 3)),
    (0, (14, 5)),
    (0, (8, 3, 2, 3, 2, 3)),
    (0, (3, 2)),
)
MARKERS = ("o", "s", "^", "D", "v", "P", "X")


def chart_roles(theme_type: str | None = None) -> dict[str, str]:
    """Вернуть роли графика для светлой или тёмной темы."""
    return DARK if str(theme_type).lower() == "dark" else LIGHT


def phase_styles(
    phases: Iterable[str],
    theme_type: str | None = None,
) -> dict[str, dict[str, object]]:
    """Назначить фазам устойчивую пару «цвет + линия» и маркер.

    Фаза с номером i (по отсортированным именам) получает цвет i mod 7 и
    линию (i + i div 7) mod 7: у первых семи фаз различны и цвет, и линия,
    у 49 фаз — 49 разных пар.
    """
    colors = DARK_SERIES if str(theme_type).lower() == "dark" else LIGHT_SERIES

    result: dict[str, dict[str, object]] = {}
    for index, phase in enumerate(sorted(dict.fromkeys(str(item) for item in phases))):
        result[phase] = {
            "color": colors[index % len(colors)],
            "linestyle": LINE_STYLES[(index + index // len(colors)) % len(LINE_STYLES)],
            "marker": MARKERS[index % len(MARKERS)],
        }
    return result


def style_legend(legend, roles: dict[str, str]) -> None:
    """Покрасить легенду matplotlib по ролям темы: заливка, рамка, текст."""
    frame = legend.get_frame()
    frame.set_facecolor(roles["legend_fill"])
    frame.set_edgecolor(roles["legend_edge"])
    for text in legend.get_texts():
        text.set_color(roles["axis"])
    legend.get_title().set_color(roles["axis"])
