"""Палитра, style.css и графики по решениям владельца 24.09.2026 (21-Е).

Проверяется:

* палитра — роли обеих тем равны значениям задания 21-Е; семь видов линий;
  у 49 фаз 49 разных пар «цвет + линия», у первых семи различны и цвет, и
  линия; контраст text и axis к фону графика ≥ 4.5:1, primary и рядов ≥ 3:1;
* style.css — каждый data-testid из файла есть в бандле установленного
  Streamlit (защита от обновления Streamlit);
* графики — сетка на девяти графиках ``style_chart_axes`` (роль grid,
  прозрачность 0.25), на карте доли фазы сетки нет; в заголовках нет
  «ThermoGar:»; легенда под осями; подписи у концов линий в обеих темах и
  без наложения; символы элементов в текстах графика — Ni, Al, Cr;
* перерисовка при смене темы (решение 7Б) — фигура другой темы строится из
  сохранённых данных без вызова расчёта, при возврате темы не строится
  заново; фон и оси — роли новой темы.

Функции ``ThermoGar_app.py`` берутся из исходника без запуска Streamlit,
диффузия и выделения — импортом модулей.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -B -m pytest tools/test_chart_theme_21e.py -v
"""

from __future__ import annotations

import ast
import re
import sys
import warnings
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
import streamlit  # noqa: E402
from matplotlib.colors import to_rgb  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "app" / "ThermoGar_app.py"
STYLE_PATH = ROOT / "app" / "style.css"
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

import thermogar_diffusion as diffusion  # noqa: E402
import thermogar_palette as palette  # noqa: E402
import thermogar_precipitation as precipitation  # noqa: E402
import thermogar_properties as properties  # noqa: E402
from thermogar_palette import ThemedFigure, chart_roles  # noqa: E402

THEMES = ("light", "dark")

APP_NAMES = (
    "current_theme_type",
    "chart_figure",
    "build_themed_figure",
    "style_chart_axes",
    "CelsiusLocatorOnKelvinAxis",
    "set_celsius_ticks_on_kelvin_axis",
    "figure_to_png",
    "solidification_path_dataframe",
    "plot_density_temperature",
    "plot_phase_fraction_scan",
    "plot_isolated_phase_energies",
    "plot_driving_force",
    "plot_tzero",
    "plot_solidification_liquid_comparison",
    "plot_solidification_phase_path",
    "plot_liquid_composition_comparison",
    "plot_binary_thermogar",
    "plot_isopleth_thermogar",
    "plot_ternary_thermogar",
    "plot_ternary_phase_fraction_map",
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
    namespace: dict[str, Any] = {
        "__file__": str(APP_PATH),
        "__name__": "thermogar_app_extract",
        "PHASE_EXPLANATIONS": {},
        "SOLIDIFICATION_METHOD_LABELS": {
            "equilibrium": "Равновесное охлаждение",
            "scheil": "Scheil",
        },
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        exec(
            compile(ast.Module(body=header + definitions, type_ignores=[]), str(APP_PATH), "exec"),
            namespace,
        )
    missing = wanted - set(namespace)
    assert not missing, sorted(missing)
    return namespace


@pytest.fixture
def themed(app, monkeypatch):
    """Тема «текущего прогона» для функций, которые берут её сами."""

    def use(theme: str) -> None:
        monkeypatch.setitem(app, "current_theme_type", lambda: theme)
        monkeypatch.setattr(diffusion, "_theme_type", lambda: theme)
        monkeypatch.setattr(precipitation, "_theme", lambda: theme)

    return use


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


# --------------------------------------------------------------------------- #
# WCAG 2.2
# --------------------------------------------------------------------------- #


def relative_luminance(color: Any) -> float:
    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(value) for value in to_rgb(color))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: Any, second: Any) -> float:
    lighter, darker = sorted(
        (relative_luminance(first), relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


# --------------------------------------------------------------------------- #
# Палитра (ШАГ 2)
# --------------------------------------------------------------------------- #

EXPECTED_LIGHT = {
    "background": "#FFFFFF", "surface": "#ECEDEF", "grid": "#CFD1D5",
    "axis": "#4B4F56", "text": "#232529", "primary": "#1F60C1",
    "primary_dark": "#0D2768", "primary_light": "#4587DE", "muted": "#79808B",
    "danger": "#A62A1E", "danger_sign": "#C93425", "info_fill": "#EFF6FA",
    "legend_fill": "#FFFFFF", "legend_edge": "#CFD1D5",
}
EXPECTED_DARK = {
    "background": "#1F2226", "surface": "#25292F", "grid": "#33373E",
    "axis": "#BCC2CD", "text": "#ECEDEF", "primary": "#5C97E8",
    "primary_dark": "#4587DE", "primary_light": "#B4D1EE", "muted": "#8A92A0",
    "danger": "#F06157", "danger_sign": "#F06157", "info_fill": "#16233B",
    "legend_fill": "#1F2226", "legend_edge": "#33373E",
}
EXPECTED_LINE_STYLES = (
    "-",
    (0, (7, 4)),
    (0, (8, 3, 2, 3)),
    (0, (2, 3)),
    (0, (14, 5)),
    (0, (8, 3, 2, 3, 2, 3)),
    (0, (3, 2)),
)


def test_roles_are_the_values_of_the_task():
    assert palette.LIGHT == EXPECTED_LIGHT
    assert palette.DARK == EXPECTED_DARK
    assert chart_roles("light") is palette.LIGHT
    assert chart_roles("dark") is palette.DARK


def test_series():
    assert palette.LIGHT_SERIES == (
        "#0D2768", "#4587DE", "#000000", "#D55E00", "#009E73", "#CC79A7", "#0072B2",
    )
    assert palette.DARK_SERIES == (
        "#4587DE", "#B4D1EE", "#ECEDEF", "#F5A79F", "#8FE0B4", "#E8B200", "#9CC0F2",
    )


def test_seven_line_styles():
    assert palette.LINE_STYLES == EXPECTED_LINE_STYLES
    assert len(set(palette.LINE_STYLES)) == 7


@pytest.mark.parametrize("theme", THEMES)
def test_49_phases_get_49_pairs(theme):
    names = [f"PHASE_{index:02d}" for index in range(49)]
    styles = palette.phase_styles(names, theme)
    pairs = [(styles[name]["color"], styles[name]["linestyle"]) for name in names]
    assert len(set(pairs)) == 49
    first = pairs[:7]
    assert len({color for color, _ in first}) == 7
    assert len({line for _, line in first}) == 7
    series = palette.DARK_SERIES if theme == "dark" else palette.LIGHT_SERIES
    for index, name in enumerate(names):
        assert styles[name]["color"] == series[index % 7]
        assert styles[name]["linestyle"] == EXPECTED_LINE_STYLES[(index + index // 7) % 7]
        assert styles[name]["marker"] == palette.MARKERS[index % 7]


@pytest.mark.parametrize("theme", THEMES)
def test_contrast_of_roles_and_series(theme):
    roles = chart_roles(theme)
    background = roles["background"]
    assert contrast_ratio(roles["text"], background) >= 4.5
    assert contrast_ratio(roles["axis"], background) >= 4.5
    assert contrast_ratio(roles["primary"], background) >= 3.0
    series = palette.DARK_SERIES if theme == "dark" else palette.LIGHT_SERIES
    for color in series:
        assert contrast_ratio(color, background) >= 3.0, color


def test_contrasts_named_by_the_master():
    expected = {
        ("#4B4F56", "#FFFFFF"): 8.23,
        ("#BCC2CD", "#1F2226"): 8.92,
        ("#1F60C1", "#FFFFFF"): 6.00,
        ("#5C97E8", "#1F2226"): 5.36,
        ("#4587DE", "#1F2226"): 4.39,
        ("#ECEDEF", "#1F2226"): 13.63,
        ("#CC79A7", "#FFFFFF"): 3.06,
        ("#4B4F56", "#F8F8F9"): 7.75,
        ("#4B4F56", "#ECEDEF"): 7.02,
        ("#BCC2CD", "#17181B"): 9.92,
        ("#79808B", "#ECEDEF"): 3.40,
        ("#79808B", "#F8F8F9"): 3.75,
        ("#8A92A0", "#1F2226"): 5.09,
        ("#17181B", "#5C97E8"): 5.96,
        ("#FFFFFF", "#1F60C1"): 6.00,
    }
    for (first, second), ratio in expected.items():
        assert round(contrast_ratio(first, second), 2) == ratio, (first, second)


# --------------------------------------------------------------------------- #
# style.css (ШАГ 3)
# --------------------------------------------------------------------------- #


def streamlit_bundle_text() -> str:
    js_dir = Path(streamlit.__file__).parent / "static" / "static" / "js"
    return "\n".join(
        path.read_text("utf-8", errors="ignore") for path in sorted(js_dir.glob("*.js"))
    )


def test_every_testid_of_style_css_is_in_the_streamlit_bundle():
    css = STYLE_PATH.read_text("utf-8")
    testids = sorted(set(re.findall(r'data-testid="([^"]+)"', css)))
    assert testids, "в style.css нет ни одного data-testid"
    bundle = streamlit_bundle_text()
    missing = []
    for testid in testids:
        if testid.startswith("stBaseButton-"):
            kind = testid.removeprefix("stBaseButton-")
            found = "stBaseButton-${" in bundle and f"`{kind}`" in bundle
        else:
            found = f"`{testid}`" in bundle or f'"{testid}"' in bundle
        if not found:
            missing.append(testid)
    assert not missing, missing


def test_style_css_rules_of_the_owner_decisions():
    css = STYLE_PATH.read_text("utf-8")
    assert ".main .block-container" not in css
    assert ".stMarkdown li" in css
    assert "--st-gray-text-color" not in css
    assert "light-dark(#4B4F56, #BCC2CD)" in css
    assert "light-dark(#79808B, #8A92A0)" in css
    assert "light-dark(#FFFFFF, #17181B)" in css
    assert "light-dark(#FFFFFF, #1F2226)" in css
    assert '[data-testid="InputInstructions"]' in css
    note = "Отступление от S-4, решение владельца 24.09.2026 (1Г, 2Б, 4Б); проверка S-5 — 21-Е"
    assert css.count(note) == 3


# --------------------------------------------------------------------------- #
# Модельные данные для графиков
# --------------------------------------------------------------------------- #


def phase_line(phase: str, x: list[float], y: list[float]) -> SimpleNamespace:
    return SimpleNamespace(phase=phase, x=np.asarray(x), y=np.asarray(y))


class MappingModel:
    """Минимум Binary/Isopleth/TernaryStrategy. Счётчик do_map — «расчёт»."""

    def __init__(self, phases: int = 3) -> None:
        names = ["LIQUID", "FCC_A1", "BCC_A2", "GAMMA_PRIME", "SIGMA", "MU_PHASE", "LAVES_C14"]
        self.lines = [
            phase_line(name, [0.05 + 0.02 * index, 0.2 + 0.03 * index], [0.3, 0.1 + 0.01 * index])
            for index, name in enumerate(names[:phases])
        ]
        self.map_calls = 0

    def do_map(self) -> None:
        self.map_calls += 1

    def get_all_phases(self) -> set[str]:
        return {line.phase for line in self.lines}

    def get_tieline_data(self, _x: Any, _y: Any) -> list[SimpleNamespace]:
        return [SimpleNamespace(data=self.lines, x=np.zeros(0), y=np.zeros(0))]

    def get_zpf_data(self, _x: Any, _y: Any) -> SimpleNamespace:
        return SimpleNamespace(data=self.lines)

    def get_invariant_data(self, _x: Any, _y: Any) -> list[Any]:
        return []


class TxModel(MappingModel):
    """Линии в K для бинарной и изоплеты."""

    def __init__(self, phases: int = 3) -> None:
        super().__init__(phases)
        for index, line in enumerate(self.lines):
            line.y = np.asarray([1873.15 - 20 * index, 1400.0 + 30 * index])


def temperature_table(phases: list[str]) -> pd.DataFrame:
    temperatures = np.linspace(600.0, 1300.0, 15)
    data = {"Температура, °C": temperatures}
    for index, phase in enumerate(phases):
        data[phase] = np.linspace(10.0 + index, 50.0 - index, 15)
    return pd.DataFrame(data)


def solidification_result(scale: float = 1.0) -> SimpleNamespace:
    temperatures = np.linspace(1700.0, 1500.0, 9)
    liquid = np.linspace(1.0, 0.0, 9) * scale
    return SimpleNamespace(
        method="equilibrium",
        temperatures=temperatures,
        fraction_liquid=liquid,
        fraction_solid=1.0 - liquid,
        cum_phase_amounts={"FCC_A1": 1.0 - liquid, "GAMMA_PRIME": 0.1 * (1.0 - liquid)},
    )


def liquid_tables() -> dict[str, pd.DataFrame]:
    temperatures = np.linspace(1400.0, 1250.0, 6)
    return {
        "equilibrium": pd.DataFrame(
            {"Температура, °C": temperatures, "NI, ат.%": np.linspace(70.0, 60.0, 6)}
        ),
        "scheil": pd.DataFrame(
            {"Температура, °C": temperatures, "NI, ат.%": np.linspace(70.0, 55.0, 6)}
        ),
    }


def map_table() -> pd.DataFrame:
    rows = []
    for x in np.linspace(0.0, 0.5, 6):
        for y in np.linspace(0.0, 0.5, 6):
            rows.append(
                {
                    "AL, доля на карте": x,
                    "CR, доля на карте": y,
                    "GAMMA_PRIME, мольная доля, %": 100.0 * x * (1.0 - y),
                }
            )
    return pd.DataFrame(rows)


def diffusion_profile_args() -> tuple:
    z = np.linspace(0.0, 100.0, 11)
    initial = np.column_stack([np.where(z < 50, 0.8, 0.6), np.where(z < 50, 0.1, 0.25), np.where(z < 50, 0.1, 0.15)])
    final = np.column_stack([0.7 + 0.001 * z, 0.18 - 0.0005 * z, 0.12 - 0.0005 * z])
    return (z, ["NI", "AL", "CR"], initial, final, "ат.%", "Модель: профиль состава")


def diffusion_phase_table() -> pd.DataFrame:
    x = np.linspace(0.0, 100.0, 6)
    return pd.DataFrame(
        {
            "Расстояние, мкм": x,
            "FCC_A1, локальная доля, %": 100.0 - x,
            "BCC_A2, локальная доля, %": x,
        }
    )


def precipitation_matrix_table() -> pd.DataFrame:
    times = np.array([0.0, 0.01, 0.1, 1.0])
    return pd.DataFrame(
        {
            "Время, ч": times,
            "AL, матрица, ат.%": [15.0, 14.0, 12.0, 11.0],
            "CR, матрица, ат.%": [10.0, 10.2, 10.4, 10.5],
        }
    )


# Девять графиков style_chart_axes: построитель(app) -> фигура.
STYLE_CHART_AXES_FIGURES: dict[str, Callable[[dict[str, Any]], Any]] = {
    "density_temperature": lambda app: app["plot_density_temperature"](
        pd.DataFrame({"Температура, K": [800.0, 900.0, 1000.0], "Плотность сплава, кг/м³": [8200.0, 8150.0, 8100.0]})
    ),
    "phase_fractions": lambda app: app["plot_phase_fraction_scan"](
        temperature_table(["FCC_A1", "GAMMA_PRIME"]), "Температура, °C",
        ["FCC_A1", "GAMMA_PRIME"], "Фазовые доли от температуры", "ni",
    ),
    "phase_energies": lambda app: app["plot_isolated_phase_energies"](
        temperature_table(["FCC_A1", "BCC_A2"]), ["FCC_A1", "BCC_A2"], "ni", True,
    ),
    "driving_force": lambda app: app["plot_driving_force"](
        pd.DataFrame({"Температура, °C": [600.0, 700.0, 800.0], "Движущая сила, Дж/моль": [-100.0, 0.0, 100.0]}),
        "SIGMA",
    ),
    "tzero": lambda app: app["plot_tzero"](
        pd.DataFrame({"AL, ат.%": [1.0, 2.0, 3.0], "T₀, °C": [900.0, 880.0, 860.0]}),
        "AL, ат.%", "FCC_A1", "BCC_A2",
    ),
    "liquid_fraction": lambda app: app["plot_solidification_liquid_comparison"](
        {"equilibrium": solidification_result(), "scheil": solidification_result(0.9)}
    ),
    "liquid_composition": lambda app: app["plot_liquid_composition_comparison"](
        liquid_tables(), "NI", "at"
    ),
    "binary_tx": lambda app: app["plot_binary_thermogar"](
        TxModel(), None, None, (0.0, 0.5), (973.15, 1873.15),
        "Диаграмма состояния AL–NI", "Содержание NI, ат.%", False, False,
    )[0],
    "isopleth_tx": lambda app: app["plot_isopleth_thermogar"](
        TxModel(), None, None, (0.0, 0.5), (973.15, 1873.15),
        "Многокомпонентное сечение: основа NI, меняется CR", "Содержание CR, ат.%", False,
    )[0],
}


def ternary(app: dict[str, Any], phases: int = 3) -> Any:
    return app["plot_ternary_thermogar"](
        MappingModel(phases), None, None, "NI", "AL", "CR", 900.0, False, 5, False,
    )[0]


def phase_map(app: dict[str, Any]) -> Any:
    return app["plot_ternary_phase_fraction_map"](
        map_table(), "NI", "AL", "CR", "GAMMA_PRIME", 900.0, "ат.%", 5.0, "По данным",
    )[0]


def all_figures(app: dict[str, Any]) -> dict[str, Any]:
    figures = {name: build(app) for name, build in STYLE_CHART_AXES_FIGURES.items()}
    figures["solid_phases"] = app["plot_solidification_phase_path"](solidification_result(), "ni", 0.0)
    figures["ternary"] = ternary(app)
    figures["phase_map"] = phase_map(app)
    figures["diffusion_profile"] = diffusion._profile_figure(*diffusion_profile_args())
    figures["diffusion_phases"] = diffusion._phase_figure(diffusion_phase_table(), ["FCC_A1", "BCC_A2"])
    figures["precipitation_matrix"] = precipitation._composition_figure(precipitation_matrix_table(), ["AL", "CR"])
    figures["precipitation_psd"] = precipitation._psd_figure(
        pd.DataFrame({"Радиус класса, нм": [1.0, 2.0, 3.0], "Число частиц в классе, 1/м³": [1e20, 5e20, 1e20]}),
        "GAMMA_PRIME",
    )
    figures["elastic"] = properties._elastic_figure(
        pd.DataFrame({"Метод": ["Reuss — нижняя", "Hill — средняя", "Voigt — верхняя"], "E, ГПа": [190.0, 200.0, 210.0]}),
        None,
    )
    figures["strengthening"] = properties._strengthening_figure(
        pd.DataFrame({"Механизм": ["Внутреннее сопротивление / базовый уровень", "Обход частиц Orowan"], "Вклад, МПа": [100.0, 200.0]}),
        None,
    )
    return figures


def figure_texts(figure: Any) -> list[str]:
    texts: list[str] = []
    for text in figure.findobj(matplotlib.text.Text):
        if text.get_visible() and text.get_text():
            texts.append(text.get_text())
    return texts


# --------------------------------------------------------------------------- #
# Графики (ШАГ 4)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("name", sorted(STYLE_CHART_AXES_FIGURES))
def test_grid_on_nine_style_chart_axes_charts(app, themed, name, theme):
    themed(theme)
    roles = chart_roles(theme)
    figure = STYLE_CHART_AXES_FIGURES[name](app)
    axes = figure.axes[0]
    gridlines = axes.get_xgridlines() + axes.get_ygridlines()
    assert gridlines and all(line.get_visible() for line in gridlines), name
    for line in gridlines:
        assert to_rgb(line.get_color()) == to_rgb(roles["grid"]), name
        assert line.get_alpha() == pytest.approx(0.25), name


def test_nine_charts_go_through_style_chart_axes():
    source = APP_PATH.read_text("utf-8")
    tree = ast.parse(source)
    callers = sorted(
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith("plot_")
        and any(
            isinstance(call, ast.Call) and getattr(call.func, "id", "") == "style_chart_axes"
            for call in ast.walk(node)
        )
    )
    assert callers == sorted(
        [
            "plot_density_temperature",
            "plot_phase_fraction_scan",
            "plot_isolated_phase_energies",
            "plot_driving_force",
            "plot_tzero",
            "plot_solidification_liquid_comparison",
            "plot_liquid_composition_comparison",
            "plot_binary_thermogar",
            "plot_isopleth_thermogar",
        ]
    )


@pytest.mark.parametrize("theme", THEMES)
def test_phase_fraction_map_has_no_grid(app, themed, theme):
    themed(theme)
    figure = phase_map(app)
    axes = figure.axes[0]
    assert not any(line.get_visible() for line in axes.get_xgridlines() + axes.get_ygridlines())


@pytest.mark.parametrize("theme", THEMES)
def test_titles_have_no_thermogar_prefix(app, themed, theme):
    themed(theme)
    for name, figure in all_figures(app).items():
        for axes in figure.axes:
            assert "ThermoGar:" not in axes.get_title(), name
    source = "\n".join(
        (ROOT / "app" / module).read_text("utf-8")
        for module in ("ThermoGar_app.py", "thermogar_diffusion.py", "thermogar_precipitation.py", "thermogar_properties.py")
    )
    assert '"ThermoGar: ' not in source
    assert 'f"ThermoGar: ' not in source


LEGEND_BELOW = (
    "phase_fractions",
    "phase_energies",
    "driving_force",
    "tzero",
    "liquid_fraction",
    "liquid_composition",
    "binary_tx",
    "isopleth_tx",
    "solid_phases",
    "ternary",
    "phase_map",
    "diffusion_profile",
    "diffusion_phases",
    "precipitation_matrix",
)


@pytest.mark.parametrize("theme", THEMES)
def test_legend_below_axes_in_columns_and_in_png(app, themed, theme):
    themed(theme)
    roles = chart_roles(theme)
    figures = all_figures(app)
    for name in LEGEND_BELOW:
        figure = figures[name]
        renderer = figure.canvas.get_renderer()
        axes = figure.axes[0]
        legend = axes.get_legend()
        assert legend is not None, name
        legend_box = legend.get_window_extent(renderer)
        axes_box = axes.get_tightbbox(renderer)
        plot_box = axes.get_window_extent(renderer)
        # Под осями и под подписью оси x, по центру поля графика.
        assert legend_box.y1 <= plot_box.y0, name
        assert abs(0.5 * (legend_box.x0 + legend_box.x1) - 0.5 * (plot_box.x0 + plot_box.x1)) < 2.0, name
        # Легенда входит в PNG выгрузки (bbox_inches="tight").
        tight = figure.get_tightbbox(renderer).transformed(figure.dpi_scale_trans)
        assert tight.y0 <= legend_box.y0 + 1e-6, name
        assert axes_box.y0 >= legend_box.y0, name
        for text in legend.get_texts():
            assert to_rgb(text.get_color()) == to_rgb(roles["axis"]), name


def test_legend_does_not_shrink_the_plot(app, themed):
    """Поле графика то же, что без легенды: легенда вынесена за оси."""

    themed("light")
    table = temperature_table(["FCC_A1", "GAMMA_PRIME", "BCC_A2"])
    phases = ["FCC_A1", "GAMMA_PRIME", "BCC_A2"]
    with_legend = app["plot_phase_fraction_scan"](table, "Температура, °C", phases, "Модель", "ni")
    without_legend = app["plot_phase_fraction_scan"](table, "Температура, °C", [], "Модель", "ni")
    assert with_legend.axes[0].get_position().height == pytest.approx(
        without_legend.axes[0].get_position().height, rel=0.02
    )


def test_legend_uses_several_columns(app, themed):
    themed("light")
    phases = ["FCC_A1", "GAMMA_PRIME", "BCC_A2", "SIGMA"]
    figure = app["plot_phase_fraction_scan"](
        temperature_table(phases), "Температура, °C", phases, "Модель", "ni"
    )
    legend = figure.axes[0].get_legend()
    assert legend._ncols > 1


END_LABEL_FIGURES = {
    "phase_fractions": ["FCC_A1", "GAMMA_PRIME"],
    "phase_energies": ["FCC_A1", "BCC_A2"],
    "binary_tx": ["LIQUID", "FCC_A1", "BCC_A2"],
    "isopleth_tx": ["LIQUID", "FCC_A1", "BCC_A2"],
    "ternary": ["LIQUID", "FCC_A1", "BCC_A2"],
    "diffusion_phases": ["FCC_A1", "BCC_A2"],
    "diffusion_profile": ["Ni", "Al", "Cr"],
}


def annotations_of(figure: Any) -> list[Any]:
    return [
        child
        for axes in figure.axes
        for child in axes.get_children()
        if isinstance(child, matplotlib.text.Annotation)
    ]


@pytest.mark.parametrize("theme", THEMES)
def test_end_labels_in_both_themes(app, themed, theme):
    themed(theme)
    figures = all_figures(app)
    for name, phases in END_LABEL_FIGURES.items():
        labels = sorted(annotation.get_text() for annotation in annotations_of(figures[name]))
        assert labels == sorted(phases), name


@pytest.mark.parametrize("theme", THEMES)
def test_end_labels_do_not_overlap(app, themed, theme):
    """Семь линий сходятся в одну точку: подписи разведены по вертикали."""

    themed(theme)
    phases = ["LIQUID", "FCC_A1", "BCC_A2", "GAMMA_PRIME", "SIGMA", "MU_PHASE", "LAVES_C14"]
    temperatures = np.linspace(600.0, 1300.0, 8)
    table = pd.DataFrame({"Температура, °C": temperatures})
    for index, phase in enumerate(phases):
        table[phase] = np.linspace(5.0 * index, 20.0, 8)
    figure = app["plot_phase_fraction_scan"](table, "Температура, °C", phases, "Модель", "ni")
    renderer = figure.canvas.get_renderer()
    boxes = [annotation.get_window_extent(renderer) for annotation in annotations_of(figure)]
    assert len(boxes) == 7
    for first, second in combinations(boxes, 2):
        assert not first.overlaps(second)


ELEMENT_FIGURES = (
    "liquid_composition",
    "binary_tx",
    "isopleth_tx",
    "ternary",
    "phase_map",
    "diffusion_profile",
    "precipitation_matrix",
    "tzero",
)


@pytest.mark.parametrize("theme", THEMES)
def test_element_symbols_in_chart_texts(app, themed, theme):
    themed(theme)
    figures = all_figures(app)
    upper = re.compile(r"(?<!\w)(NI|AL|CR)(?!\w)")
    for name in ELEMENT_FIGURES:
        texts = figure_texts(figures[name])
        joined = "\n".join(texts)
        assert not upper.search(joined), (name, upper.findall(joined))
        assert re.search(r"(?<!\w)(Ni|Al|Cr)(?!\w)", joined), name
    # Имена фаз — как в базе.
    assert "GAMMA_PRIME" in "\n".join(figure_texts(figures["phase_map"]))
    assert "FCC_A1" in "\n".join(figure_texts(figures["binary_tx"]))


def test_element_case_text_keeps_phase_names():
    assert palette.element_case_text("Диаграмма состояния AL–NI") == "Диаграмма состояния Al–Ni"
    assert palette.element_case_text("FCC_A1 NI3AL GAMMA_PRIME") == "FCC_A1 NI3AL GAMMA_PRIME"
    assert palette.element_case_text("Молярная энергия Гиббса GM, Дж/моль") == "Молярная энергия Гиббса GM, Дж/моль"
    assert palette.element_label("VA") == "VA"
    assert palette.element_label("CR") == "Cr"


@pytest.mark.parametrize("theme", THEMES)
def test_single_series_is_primary(app, themed, theme):
    themed(theme)
    roles = chart_roles(theme)
    figures = all_figures(app)
    for name in ("driving_force", "tzero"):
        assert to_rgb(figures[name].axes[0].get_lines()[0].get_color()) == to_rgb(roles["primary"]), name
    fraction = precipitation._single_figure(np.array([0.0, 0.1, 1.0]), np.array([0.0, 1.0, 2.0]), "Доля", "Доля X", "X")
    assert to_rgb(fraction.axes[0].get_lines()[0].get_color()) == to_rgb(roles["primary"])
    psd = figures["precipitation_psd"].axes[0]
    assert to_rgb(psd.get_lines()[0].get_color()) == to_rgb(roles["primary"])
    bars = figures["strengthening"].axes[0].patches
    assert bars and all(to_rgb(bar.get_facecolor()) == to_rgb(chart_roles("light")["primary"]) for bar in bars)


@pytest.mark.parametrize("theme", THEMES)
def test_kinetics_chrome(themed, theme):
    """Находки 8, 12, 14, 17: рамки — axis, кегли 11/13, начальный профиль, правая ось."""

    themed(theme)
    roles = chart_roles(theme)
    profile = diffusion._profile_figure(*diffusion_profile_args())
    radius = precipitation._radius_density_figure(
        np.array([0.0, 0.1, 1.0]), np.array([1.0, 2.0, 3.0]), np.array([1e20, 2e21, 1e21]), "GAMMA_PRIME"
    )
    for figure in (profile, radius):
        for axes in figure.axes:
            for spine in axes.spines.values():
                assert to_rgb(spine.get_edgecolor()) == to_rgb(roles["axis"])
    axes = profile.axes[0]
    assert axes.title.get_fontsize() == 13
    assert axes.xaxis.label.get_fontsize() == 13
    assert axes.yaxis.label.get_fontsize() == 13
    assert axes.xaxis.get_major_ticks()[0].label1.get_fontsize() == 11
    def pattern(line):
        offset, dashes = line._unscaled_dash_pattern
        return (offset, tuple(dashes) if dashes else None)

    initial_styles = {pattern(line) for line in axes.get_lines() if line.get_alpha() == 0.65}
    final_styles = {pattern(line) for line in axes.get_lines() if line.get_alpha() != 0.65}
    assert initial_styles and not (initial_styles & final_styles)
    right = radius.axes[1]
    assert to_rgb(right.yaxis.label.get_color()) == to_rgb(roles["axis"])
    assert right.yaxis.label.get_fontsize() == 13


def test_content_width_instead_of_use_container_width():
    for module in ("ThermoGar_app.py", "thermogar_diffusion.py"):
        assert "use_container_width" not in (ROOT / "app" / module).read_text("utf-8"), module


# --------------------------------------------------------------------------- #
# Перерисовка при смене темы (ШАГ 5)
# --------------------------------------------------------------------------- #


def assert_theme_roles(figure: Any, theme: str, spine_role: str = "axis") -> None:
    roles = chart_roles(theme)
    assert to_rgb(figure.get_facecolor()) == to_rgb(roles["background"])
    axes = figure.axes[0]
    assert to_rgb(axes.get_facecolor()) == to_rgb(roles["background"])
    for spine in axes.spines.values():
        assert to_rgb(spine.get_edgecolor()) == to_rgb(roles[spine_role])


def counted(builder: Callable[..., Any], calls: list[str]) -> Callable[..., Any]:
    def wrapper(*args: Any, theme_type: str | None = None, **kwargs: Any) -> Any:
        calls.append(str(theme_type))
        return builder(*args, theme_type=theme_type, **kwargs)

    return wrapper


def redraw_cases(app: dict[str, Any]) -> dict[str, tuple[Callable[..., Any], tuple, MappingModel | None]]:
    """Что хранит экран: построитель и его данные (без расчёта)."""

    tx = TxModel()
    tri = MappingModel()
    return {
        "density_temperature": (app["plot_density_temperature"], (pd.DataFrame({"Температура, K": [800.0, 900.0], "Плотность сплава, кг/м³": [8200.0, 8150.0]}),), None),
        "phase_fractions": (app["plot_phase_fraction_scan"], (temperature_table(["FCC_A1"]), "Температура, °C", ["FCC_A1"], "Фазовые доли от температуры", "ni"), None),
        "phase_energies": (app["plot_isolated_phase_energies"], (temperature_table(["FCC_A1"]), ["FCC_A1"], "ni", False), None),
        "driving_force": (app["plot_driving_force"], (pd.DataFrame({"Температура, °C": [600.0, 700.0], "Движущая сила, Дж/моль": [-1.0, 1.0]}), "SIGMA"), None),
        "tzero": (app["plot_tzero"], (pd.DataFrame({"AL, ат.%": [1.0, 2.0], "T₀, °C": [900.0, 880.0]}), "AL, ат.%", "FCC_A1", "BCC_A2"), None),
        "liquid_fraction": (app["plot_solidification_liquid_comparison"], ({"equilibrium": solidification_result()},), None),
        "solid_phases": (app["plot_solidification_phase_path"], (solidification_result(), "ni", 0.0), None),
        "liquid_composition": (app["plot_liquid_composition_comparison"], (liquid_tables(), "NI", "at"), None),
        "binary_tx": (app["plot_binary_thermogar"], (tx, None, None, (0.0, 0.5), (973.15, 1873.15), "Модель", "Содержание NI, ат.%", False, False), tx),
        "isopleth_tx": (app["plot_isopleth_thermogar"], (tx, None, None, (0.0, 0.5), (973.15, 1873.15), "Модель", "Содержание CR, ат.%", False), tx),
        "ternary": (app["plot_ternary_thermogar"], (tri, None, None, "NI", "AL", "CR", 900.0, False, 5, False), tri),
        "phase_map": (app["plot_ternary_phase_fraction_map"], (map_table(), "NI", "AL", "CR", "GAMMA_PRIME", 900.0, "ат.%", 5.0, "По данным"), None),
        "diffusion_profile": (diffusion._profile_figure, diffusion_profile_args(), None),
        "diffusion_phases": (diffusion._phase_figure, (diffusion_phase_table(), ["FCC_A1", "BCC_A2"]), None),
        "precipitation_fraction": (precipitation._single_figure, (np.array([0.0, 0.1, 1.0]), np.array([0.0, 1.0, 2.0]), "Доля", "Доля X", "X"), None),
        "precipitation_radius": (precipitation._radius_density_figure, (np.array([0.0, 0.1, 1.0]), np.array([1.0, 2.0, 3.0]), np.array([1e20, 2e21, 1e21]), "X"), None),
        "precipitation_matrix": (precipitation._composition_figure, (precipitation_matrix_table(), ["AL", "CR"]), None),
        "precipitation_psd": (precipitation._psd_figure, (pd.DataFrame({"Радиус класса, нм": [1.0, 2.0], "Число частиц в классе, 1/м³": [1e20, 2e20]}), "X"), None),
        "elastic": (properties._elastic_figure, (pd.DataFrame({"Метод": ["Reuss — нижняя", "Voigt — верхняя"], "E, ГПа": [190.0, 210.0]}),), None),
        "strengthening": (properties._strengthening_figure, (pd.DataFrame({"Механизм": ["Обход частиц Orowan"], "Вклад, МПа": [200.0]}),), None),
    }


REDRAW_NAMES = (
    "density_temperature", "phase_fractions", "phase_energies", "driving_force", "tzero",
    "liquid_fraction", "solid_phases", "liquid_composition", "binary_tx", "isopleth_tx",
    "ternary", "phase_map", "diffusion_profile", "diffusion_phases", "precipitation_fraction",
    "precipitation_radius", "precipitation_matrix", "precipitation_psd", "elastic", "strengthening",
)


@pytest.mark.parametrize("name", REDRAW_NAMES)
def test_redraw_in_other_theme_from_saved_data(app, themed, name):
    themed("light")
    builder, args, model = redraw_cases(app)[name]
    calls: list[str] = []
    stored = ThemedFigure(counted(builder, calls), *args)

    # Рамки графиков «Свойств» — роль grid, как были (находка 8 касалась
    # только диффузии и выделений).
    spine_role = "grid" if name in ("elastic", "strengthening") else "axis"
    light = stored.figure("light")
    assert_theme_roles(light, "light", spine_role)
    # Пользователь переключил тему: следующий прогон видит «dark».
    themed("dark")
    dark = stored.figure("dark")
    assert_theme_roles(dark, "dark", spine_role)
    assert dark is not light
    # Возврат темы: фигура из кэша, построитель не вызывается.
    assert stored.figure("light") is light
    assert stored.figure("dark") is dark
    assert calls == ["light", "dark"]
    # Расчёт (do_map модели) не вызывался ни разу.
    if model is not None:
        assert model.map_calls == 0
    # Фигуры не копятся в менеджере pyplot.
    assert light.number not in plt.get_fignums()
    assert dark.number not in plt.get_fignums()


def test_chart_figure_and_png_follow_the_theme_of_the_run(app, themed):
    themed("light")
    stored = app["build_themed_figure"](
        app["plot_driving_force"],
        pd.DataFrame({"Температура, °C": [600.0, 700.0], "Движущая сила, Дж/моль": [-1.0, 1.0]}),
        "SIGMA",
    )
    assert_theme_roles(app["chart_figure"](stored), "light")
    light_png = app["figure_to_png"](stored)
    themed("dark")
    assert_theme_roles(app["chart_figure"](stored), "dark")
    dark_png = app["figure_to_png"](stored)
    assert light_png[:8] == dark_png[:8] == b"\x89PNG\r\n\x1a\n"
    assert light_png != dark_png
    # Готовая фигура проходит через chart_figure без изменений.
    figure = plt.figure()
    assert app["chart_figure"](figure) is figure


def test_build_themed_figure_builds_in_the_theme_of_the_calculation(app, themed):
    themed("dark")
    calls: list[str] = []
    app["build_themed_figure"](
        counted(app["plot_driving_force"], calls),
        pd.DataFrame({"Температура, °C": [600.0, 700.0], "Движущая сила, Дж/моль": [-1.0, 1.0]}),
        "SIGMA",
    )
    assert calls == ["dark"]


def test_screens_store_builders_not_pictures():
    """Экран хранит построитель с данными, а не готовую фигуру (7Б)."""

    source = APP_PATH.read_text("utf-8")
    for builder in (
        "plot_phase_fraction_scan",
        "plot_binary_thermogar",
        "plot_isopleth_thermogar",
        "plot_ternary_thermogar",
        "plot_ternary_phase_fraction_map",
        "plot_isolated_phase_energies",
        "plot_driving_force",
        "plot_tzero",
    ):
        assert re.search(rf"build_themed_figure\(\s*{builder},", source), builder
    for builder in (
        "plot_density_temperature",
        "plot_solidification_liquid_comparison",
        "plot_solidification_phase_path",
        "plot_liquid_composition_comparison",
    ):
        assert re.search(rf"ThemedFigure\(\s*{builder},", source), builder
    assert not re.search(r"st\.pyplot\(\s*(?!\s|chart_figure\()", source)
    diffusion_source = (ROOT / "app" / "thermogar_diffusion.py").read_text("utf-8")
    assert re.search(r"ThemedFigure\(\s*_profile_figure,", diffusion_source)
    assert re.search(r"ThemedFigure\(_phase_figure,", diffusion_source)
    precipitation_source = (ROOT / "app" / "thermogar_precipitation.py").read_text("utf-8")
    assert precipitation_source.count("ThemedFigure(_") == 5
    assert not re.search(r"st\.pyplot\(\s*(?!\s|resolve_figure\()", precipitation_source)
    # Диффузия: результат на экране пересобирается из построителей в теме
    # прогона до показа и выгрузок.
    assert "result = replace(" in diffusion_source
    assert "resolve_figure(result.phase_chart, theme)" in diffusion_source


def test_theme_watch_asks_for_a_rerun_only_on_a_change():
    """Наблюдатель темы: прогон просится только при смене color-scheme."""

    source = APP_PATH.read_text("utf-8")
    assert "st.components.v2.component(" in source
    assert "\nwatch_theme_change()\n" in source
    script = source.split('_THEME_WATCH_JS = """', 1)[1].split('"""', 1)[0]
    assert "scheme !== watch.seen" in script
    assert "watch.fixed !== current" in script
    assert "if (!watch.timer)" in script
    assert ".st-key-thermogar_theme_watch" in STYLE_PATH.read_text("utf-8")
