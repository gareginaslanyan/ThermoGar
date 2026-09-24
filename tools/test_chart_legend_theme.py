"""Легенда графиков — по ролям темы, контраст текста к заливке ≥ 4,5:1 (21-Д).

21-Б, кадры 04 и 17 в тёмной теме: легенда — светлая плашка matplotlib по
умолчанию (белая заливка с прозрачностью 0,8 поверх тёмного фона, ≈#D0D0CF),
а текст приложение красило в светлую роль ``axis`` (#C7C1B6): контраст
≈1,16:1. ``style_chart_axes`` красил фон, оси и подписи, но не легенду.

Теперь каждая легенда проходит через ``thermogar_palette.style_legend``:
заливка ``legend_fill``, рамка ``legend_edge``, текст ``axis`` текущей темы.
В светлой теме это прежние цвета matplotlib — вид не меняется.

Фигуры строят функции отрисовки приложения на малых модельных данных:
``ThermoGar_app.py`` — из исходника без запуска Streamlit, диффузия и
выделение — импортом модулей.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -B -m pytest tools/test_chart_legend_theme.py -v
"""

from __future__ import annotations

import ast
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from matplotlib.colors import to_rgb, to_rgba  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "app" / "ThermoGar_app.py"
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

import thermogar_diffusion as diffusion  # noqa: E402
import thermogar_precipitation as precipitation  # noqa: E402
from thermogar_palette import chart_roles, style_legend  # noqa: E402

APP_NAMES = (
    "current_theme_type",
    "style_chart_axes",
    "CelsiusLocatorOnKelvinAxis",
    "set_celsius_ticks_on_kelvin_axis",
    "plot_driving_force",
    "plot_binary_thermogar",
    "plot_isopleth_thermogar",
)

THEMES = ("light", "dark")
WCAG_AA_TEXT = 4.5


@pytest.fixture(scope="module")
def app() -> dict[str, Any]:
    """Импорты верхнего уровня приложения и нужные определения — его же текстом."""

    tree = ast.parse(APP_PATH.read_text("utf-8"))
    wanted = set(APP_NAMES)
    header: list[ast.stmt] = []
    definitions: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            header.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted:
            definitions.append(node)
    namespace: dict[str, Any] = {"__file__": str(APP_PATH), "__name__": "thermogar_app_extract"}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        exec(
            compile(ast.Module(body=header + definitions, type_ignores=[]), str(APP_PATH), "exec"),
            namespace,
        )
    missing = wanted - set(namespace)
    assert not missing, sorted(missing)
    return namespace


# --------------------------------------------------------------------------- #
# WCAG 2.2
# --------------------------------------------------------------------------- #


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(value) for value in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: Any, second: Any) -> float:
    lighter, darker = sorted(
        (relative_luminance(to_rgb(first)), relative_luminance(to_rgb(second))),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def over(color: Any, background: Any) -> tuple[float, float, float]:
    """Цвет с прозрачностью поверх непрозрачного фона."""

    red, green, blue, alpha = to_rgba(color)
    base = to_rgb(background)
    return tuple(alpha * top + (1.0 - alpha) * low for top, low in zip((red, green, blue), base))


def legend_fill(legend: Any, axes: Any) -> tuple[float, float, float]:
    """Цвет, на котором стоит текст легенды."""

    if legend.get_frame_on():
        return over(legend.get_frame().get_facecolor(), axes.figure.get_facecolor())
    return to_rgb(axes.get_facecolor())


# --------------------------------------------------------------------------- #
# Figures with a legend
# --------------------------------------------------------------------------- #


def phase_line(phase: str, x: list[float], y: list[float]) -> SimpleNamespace:
    return SimpleNamespace(phase=phase, x=np.asarray(x), y=np.asarray(y))


class MappingModel:
    """Минимум Binary/IsoplethStrategy для функций отрисовки T–X."""

    lines = [
        phase_line("LIQUID", [0.1, 0.4], [1873.15, 1400.0]),
        phase_line("FCC_A1", [0.05, 0.3], [1873.15, 1400.0]),
    ]

    def get_all_phases(self) -> set[str]:
        return {"FCC_A1", "LIQUID"}

    def get_tieline_data(self, _x: Any, _y: Any) -> list[SimpleNamespace]:
        return [SimpleNamespace(data=self.lines, x=np.zeros(0), y=np.zeros(0))]

    def get_zpf_data(self, _x: Any, _y: Any) -> SimpleNamespace:
        return SimpleNamespace(data=self.lines)

    def get_invariant_data(self, _x: Any, _y: Any) -> list[Any]:
        return []


def app_binary(app: dict[str, Any]) -> Any:
    figure, _axes = app["plot_binary_thermogar"](
        MappingModel(), None, None, (0.0, 0.5), (973.15, 1873.15),
        "ThermoGar: модель", "X(CR), %", False, False,
    )
    return figure


def app_isopleth(app: dict[str, Any]) -> Any:
    figure, _axes = app["plot_isopleth_thermogar"](
        MappingModel(), None, None, (0.0, 0.5), (973.15, 1873.15),
        "ThermoGar: модель", "W(CR), %", False,
    )
    return figure


def app_driving_force(app: dict[str, Any]) -> Any:
    temperatures = np.linspace(600.0, 900.0, 7)
    table = pd.DataFrame(
        {
            "Температура, °C": temperatures,
            "Движущая сила, Дж/моль": 2.0 * (temperatures - 750.0),
        }
    )
    return app["plot_driving_force"](table, "FCC_A1")


def diffusion_phases(_app: dict[str, Any]) -> Any:
    x = np.linspace(0.0, 100.0, 6)
    table = pd.DataFrame(
        {
            "Расстояние, мкм": x,
            "FCC_A1, локальная доля, %": 100.0 - x,
            "BCC_A2, локальная доля, %": x,
        }
    )
    return diffusion._phase_figure(table, ["FCC_A1", "BCC_A2"])


def precipitation_matrix(_app: dict[str, Any]) -> Any:
    times = np.array([0.0, 0.01, 0.1, 1.0])
    table = pd.DataFrame(
        {
            "Время, ч": times,
            "AL, матрица, ат.%": [15.0, 14.0, 12.0, 11.0],
            "CR, матрица, ат.%": [10.0, 10.2, 10.4, 10.5],
        }
    )
    return precipitation._composition_figure(table, ["AL", "CR"])


FIGURES: dict[str, Callable[[dict[str, Any]], Any]] = {
    "binary_tx": app_binary,
    "isopleth_tx": app_isopleth,
    "driving_force": app_driving_force,
    "diffusion_phases": diffusion_phases,
    "precipitation_matrix": precipitation_matrix,
}


@pytest.fixture
def themed(app, monkeypatch):
    def use(theme: str) -> None:
        monkeypatch.setitem(app, "current_theme_type", lambda: theme)
        monkeypatch.setattr(diffusion, "_theme_type", lambda: theme)
        monkeypatch.setattr(precipitation, "_theme", lambda: theme)

    return use


def legends_of(figure: Any) -> list[tuple[Any, Any]]:
    return [
        (axes, axes.get_legend())
        for axes in figure.axes
        if axes.get_legend() is not None
    ]


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("name", sorted(FIGURES))
def test_legend_colours_follow_theme_and_text_reads(app, themed, name, theme):
    themed(theme)
    roles = chart_roles(theme)
    figure = FIGURES[name](app)
    try:
        figure.canvas.draw()
        pairs = legends_of(figure)
        assert pairs, f"{name}: на фигуре нет легенды"
        for axes, legend in pairs:
            texts = legend.get_texts()
            assert texts
            for text in texts:
                assert to_rgb(text.get_color()) == to_rgb(roles["axis"]), text.get_text()
            if legend.get_frame_on():
                frame = legend.get_frame()
                assert to_rgb(frame.get_facecolor()) == to_rgb(roles["legend_fill"])
                assert to_rgb(frame.get_edgecolor()) == to_rgb(roles["legend_edge"])
            fill = legend_fill(legend, axes)
            ratio = contrast_ratio(roles["axis"], fill)
            assert ratio >= WCAG_AA_TEXT, (name, theme, fill, round(ratio, 2))
    finally:
        plt.close(figure)


def test_light_legend_keeps_matplotlib_look():
    """Светлая тема: белая плашка, рамка — роль legend_edge холодной шкалы.

    21-Е: роли светлой темы #FFFFFF / #CCCCCC (как у matplotlib) заменены
    ролями новой шкалы #FFFFFF / #CFD1D5 (решение владельца 24.09.2026,
    замечание 2 приёмки 21-Д).
    """

    roles = chart_roles("light")
    assert roles["legend_fill"] == "#FFFFFF"
    assert roles["legend_edge"] == "#CFD1D5"

    figure, axes = plt.subplots()
    try:
        axes.plot([0, 1], [0, 1], label="FCC_A1")
        before = axes.legend()
        face = before.get_frame().get_facecolor()
        style_legend(before, roles)
        after = before.get_frame()
        assert after.get_facecolor() == pytest.approx(face)
        assert to_rgb(after.get_edgecolor()) == to_rgb(roles["legend_edge"])
    finally:
        plt.close(figure)


def test_dark_legend_before_and_after():
    """Тёмная тема: было ≈1,16:1 (кадры 04, 17), стало ≥ 4,5:1."""

    roles = chart_roles("dark")
    figure, axes = plt.subplots()
    figure.set_facecolor(roles["background"])
    try:
        axes.plot([0, 1], [0, 1], label="FCC_A1")
        legend = axes.legend()
        default_fill = over(legend.get_frame().get_facecolor(), roles["background"])
        assert contrast_ratio(roles["axis"], default_fill) < 1.5

        style_legend(legend, roles)
        fill = legend_fill(legend, axes)
        assert contrast_ratio(roles["axis"], fill) >= WCAG_AA_TEXT
    finally:
        plt.close(figure)
