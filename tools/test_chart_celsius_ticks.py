"""Деления оси температуры на T–X диаграммах — целые °C (21-Д).

21-Б, кадры 15 и 16: бинарная и многокомпонентная T–X диаграммы строятся в K,
а подписи оси температуры получались пересчётом ``value − 273.15``. Деления
стояли на круглых K и подписывались 726.85, 926.85, 1126.85 °C.

Теперь ``set_celsius_ticks_on_kelvin_axis`` ставит деления на круглые °C
(локатор считает в °C и переводит в K), подписи — целые °C. Данные графика
остаются в K.

Функции отрисовки берутся из исходника приложения (без запуска Streamlit) и
рисуют малые модельные данные — без расчёта равновесия.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -B -m pytest tools/test_chart_celsius_ticks.py -v
"""

from __future__ import annotations

import ast
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "app" / "ThermoGar_app.py"
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

APP_NAMES = (
    "current_theme_type",
    "style_chart_axes",
    "CelsiusLocatorOnKelvinAxis",
    "set_celsius_ticks_on_kelvin_axis",
    "plot_binary_thermogar",
    "plot_isopleth_thermogar",
)

# Кадры 15/16 21-Б, ось 700…1600 °C: было 726.85, 826.85, … 1526.85.
FRAME_15_16_LABELS = [str(value) for value in range(700, 1601, 100)]

# Пределы оси температуры, K: как в кадрах 15/16 (700…1600 °C), широкий,
# узкий и с нецелыми °C на краях.
TEMPERATURE_LIMITS_K = (
    (973.15, 1873.15),
    (300.0, 2000.0),
    (1000.0, 1060.0),
    (1234.5, 1301.7),
)


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


def phase_line(phase: str, x: list[float], y: list[float]) -> SimpleNamespace:
    return SimpleNamespace(phase=phase, x=np.asarray(x), y=np.asarray(y))


class BinaryModel:
    """Минимум ``BinaryStrategy``, который читает ``plot_binary_thermogar``."""

    def __init__(self, low_k: float, high_k: float) -> None:
        self.low_k = low_k
        self.high_k = high_k

    def get_all_phases(self) -> set[str]:
        return {"FCC_A1", "LIQUID"}

    def get_tieline_data(self, _x: Any, _y: Any) -> list[SimpleNamespace]:
        middle = 0.5 * (self.low_k + self.high_k)
        return [
            SimpleNamespace(
                data=[
                    phase_line("LIQUID", [0.1, 0.4], [self.high_k, middle]),
                    phase_line("FCC_A1", [0.05, 0.3], [self.high_k, middle]),
                ],
                x=np.zeros(0),
                y=np.zeros(0),
            )
        ]

    def get_invariant_data(self, _x: Any, _y: Any) -> list[Any]:
        return []


class IsoplethModel(BinaryModel):
    """Минимум ``IsoplethStrategy``, который читает ``plot_isopleth_thermogar``."""

    def get_zpf_data(self, _x: Any, _y: Any) -> SimpleNamespace:
        return SimpleNamespace(data=self.get_tieline_data(_x, _y)[0].data)


def draw_binary(app: dict[str, Any], limits_k: tuple[float, float]):
    return app["plot_binary_thermogar"](
        BinaryModel(*limits_k),
        None,
        None,
        (0.0, 0.5),
        limits_k,
        "ThermoGar: модель",
        "X(CR), %",
        False,
        False,
    )


def draw_isopleth(app: dict[str, Any], limits_k: tuple[float, float]):
    return app["plot_isopleth_thermogar"](
        IsoplethModel(*limits_k),
        None,
        None,
        (0.0, 0.5),
        limits_k,
        "ThermoGar: модель",
        "W(CR), %",
        False,
    )


DRAWERS = {"binary": draw_binary, "isopleth": draw_isopleth}


def visible_ticks(axes: Any) -> tuple[list[float], list[str]]:
    """Деления оси температуры в пределах оси и их подписи (после draw)."""

    low, high = axes.get_ylim()
    locations = axes.yaxis.get_majorticklocs()
    labels = [label.get_text() for label in axes.get_yticklabels()]
    assert len(locations) == len(labels), (locations, labels)
    pairs = [
        (float(tick), label)
        for tick, label in zip(locations, labels)
        if low - 1e-9 <= tick <= high + 1e-9
    ]
    return [tick for tick, _ in pairs], [label for _, label in pairs]


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("limits_k", TEMPERATURE_LIMITS_K, ids=str)
@pytest.mark.parametrize("diagram", sorted(DRAWERS))
def test_temperature_ticks_are_whole_celsius(app, monkeypatch, diagram, limits_k, theme):
    monkeypatch.setitem(app, "current_theme_type", lambda: theme)
    figure, axes = DRAWERS[diagram](app, limits_k)
    try:
        figure.canvas.draw()
        low, high = axes.get_ylim()
        assert (low, high) == pytest.approx(limits_k)  # данные и пределы — в K

        ticks_k, labels = visible_ticks(axes)
        assert len(ticks_k) >= 3, (ticks_k, labels)

        ticks_c = [tick - 273.15 for tick in ticks_k]
        for tick_c, label in zip(ticks_c, labels):
            assert tick_c == pytest.approx(round(tick_c), abs=1e-6), (ticks_c, labels)
            assert label == str(round(tick_c)), (ticks_c, labels)
        steps = {round(b - a, 6) for a, b in zip(ticks_c, ticks_c[1:])}
        assert len(steps) == 1, ticks_c
        step = steps.pop()
        assert all(round(tick_c) % step == 0 for tick_c in ticks_c), ticks_c
    finally:
        plt.close(figure)


def test_frames_15_16_ticks(app, monkeypatch):
    """Кадры 15/16 21-Б: 700…1600 °C подписаны круглыми °C, а не 726.85."""

    monkeypatch.setitem(app, "current_theme_type", lambda: "light")
    for drawer in DRAWERS.values():
        figure, axes = drawer(app, (973.15, 1873.15))
        try:
            figure.canvas.draw()
            _ticks, labels = visible_ticks(axes)
            assert labels == FRAME_15_16_LABELS, labels
        finally:
            plt.close(figure)
