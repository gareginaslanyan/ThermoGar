"""Цветовые роли и стили графиков ThermoGar.

Палитра основана на HIG_RULES.md проекта. Экранный код не должен содержать
HEX-литералы: все смысловые цвета живут здесь.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable


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


# ---------------------------------------------------------------------------
# Символы элементов в текстах графиков: Ni, Al, Cr (решение владельца
# 24.09.2026). Данные, ключи и столбцы таблиц не меняются — только текст.
# ---------------------------------------------------------------------------

ELEMENT_SYMBOLS = frozenset(
    """
    H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co
    Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb
    Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re
    Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es
    Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og
    """.split()
)

_UPPER_PAIR = re.compile(r"(?<!\w)([A-Z]{2})(?!\w)")


def element_label(symbol: str) -> str:
    """Символ элемента для графика: первая буква заглавная, вторая строчная."""
    text = str(symbol)
    candidate = text[:1].upper() + text[1:].lower()
    return candidate if candidate in ELEMENT_SYMBOLS else text


def element_case_text(text: str) -> str:
    """Заменить в тексте графика отдельные символы элементов «NI» на «Ni».

    Меняются только отдельно стоящие пары заглавных латинских букв, которые
    являются символом элемента; имена фаз вида FCC_A1 или NI3AL — одно слово
    и не меняются.
    """
    return _UPPER_PAIR.sub(
        lambda match: element_label(match.group(1)),
        str(text),
    )


# ---------------------------------------------------------------------------
# Подписи у концов линий и легенда под осями (решение владельца 5Б)
# ---------------------------------------------------------------------------


def annotate_line_ends(
    axes: Any,
    points: dict[str, tuple[float, float]],
    colors: dict[str, str],
    fontsize: float = 11,
    offset_points: float = 5,
) -> list[Any]:
    """Подписать концы линий так, чтобы подписи не налезали друг на друга.

    Вызывать после окончательной раскладки осей (tight_layout, пределы).
    Подписи, которые перекрылись бы по горизонтали, разводятся вверх с
    шагом в одну строку.
    """
    if not points:
        return []
    figure = axes.figure
    points_to_px = figure.dpi / 72.0
    gap = 1.25 * fontsize * points_to_px
    offset_px = offset_points * points_to_px

    anchors = []
    for name, (x_value, y_value) in points.items():
        x_px, y_px = axes.transData.transform((x_value, y_value))
        width = 0.62 * fontsize * points_to_px * len(str(name))
        anchors.append((y_px, x_px, width, str(name), (x_value, y_value)))
    anchors.sort(key=lambda item: (item[0], item[1]))

    placed: list[tuple[float, float, float]] = []
    annotations = []
    for y_px, x_px, width, name, point in anchors:
        left = x_px + offset_px
        right = left + width
        label_y = y_px
        while True:
            # Допуск в полпикселя: иначе ошибка округления держит подпись
            # «вплотную» к соседней и цикл не кончается.
            conflicts = [
                other_y
                for other_left, other_right, other_y in placed
                if other_left < right
                and left < other_right
                and abs(other_y - label_y) < gap - 0.5
            ]
            if not conflicts:
                break
            label_y = max(label_y + 0.5, max(conflicts) + gap)
        placed.append((left, right, label_y))
        annotations.append(
            axes.annotate(
                name,
                point,
                xytext=(offset_points, (label_y - y_px) / points_to_px),
                textcoords="offset points",
                color=colors[name],
                fontsize=fontsize,
                va="center",
                # Конец линии лежит на краю поля (в том числе на стороне
                # треугольника): подпись не прячется вместе с точкой.
                annotation_clip=False,
            )
        )
    return annotations


def place_legend_below(
    figure: Any,
    axes: Any,
    roles: dict[str, str],
    handles: list[Any] | None = None,
    fontsize: float = 11,
    max_columns: int = 4,
) -> Any | None:
    """Легенда под осями, по центру, в несколько столбцов.

    Вызывать после окончательной раскладки: поле графика не сжимается,
    легенда лежит ниже подписей оси, а PNG (bbox_inches="tight") и
    st.pyplot забирают её в кадр.
    """
    if handles is None:
        handles, labels = axes.get_legend_handles_labels()
    else:
        labels = [handle.get_label() for handle in handles]
    if not handles:
        return None

    renderer = figure.canvas.get_renderer()
    to_figure = figure.transFigure.inverted()
    legend = axes.get_legend()
    if legend is not None:
        legend.remove()
    bottom = axes.get_tightbbox(renderer).transformed(to_figure).y0
    position = axes.get_position()
    center_x = 0.5 * (position.x0 + position.x1)
    pad = 8.0 / figure.bbox.height

    columns = max(1, min(len(handles), int(max_columns)))
    while True:
        legend = axes.legend(
            handles,
            labels,
            loc="upper center",
            bbox_to_anchor=(center_x, bottom - pad),
            bbox_transform=figure.transFigure,
            ncol=columns,
            fontsize=fontsize,
        )
        width = legend.get_window_extent(renderer).width
        if columns == 1 or width <= 0.98 * figure.bbox.width:
            break
        legend.remove()
        columns -= 1
    style_legend(legend, roles)
    return legend


# ---------------------------------------------------------------------------
# Фигура в теме прогона (решение владельца 7Б)
# ---------------------------------------------------------------------------


def normalize_theme(theme_type: str | None) -> str:
    return "dark" if str(theme_type).lower() == "dark" else "light"


class ThemedFigure:
    """Фигура, которая строится из сохранённых данных в нужной теме.

    В состоянии сессии хранится не готовая картинка, а построитель и его
    данные. При смене темы фигура строится заново без повторного расчёта;
    построенные фигуры кэшируются по теме, при возврате темы новая фигура
    не строится. Построитель принимает ``theme_type`` ключевым аргументом и
    возвращает фигуру или кортеж (фигура, оси).
    """

    def __init__(self, builder: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self.builder = builder
        self.args = args
        self.kwargs = kwargs
        self._figures: dict[str, Any] = {}

    def figure(self, theme_type: str | None) -> Any:
        key = normalize_theme(theme_type)
        figure = self._figures.get(key)
        if figure is None:
            import matplotlib.pyplot as plt

            built = self.builder(*self.args, theme_type=key, **self.kwargs)
            figure = built[0] if isinstance(built, tuple) else built
            # Фигура живёт в состоянии сессии, а не в менеджере pyplot:
            # иначе matplotlib копит фигуры до «More than 20 figures».
            plt.close(figure)
            self._figures[key] = figure
        return figure


def resolve_figure(item: Any, theme_type: str | None) -> Any:
    """Готовая фигура для показа и выгрузки в теме прогона."""
    if isinstance(item, ThemedFigure):
        return item.figure(theme_type)
    return item
