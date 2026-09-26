"""Решения владельца 25.09.2026 (п. 9 и 10), внедрённые в 21-М.

* 1В: основная кнопка каждого из 19 экранов — в контейнере с ключом
  tg_action_<экран>; «Рассчитать Voigt–Reuss–Hill» — в контейнере без
  приставки; правило sticky в app/style.css;
* 2, 3: 42 поля на 15 экранах — внутри блоков «Точность и критерии»,
  «Управление фазами / метастабильный расчёт», «Параметры модели»;
  «Время, ч» диффузии — на виду;
* 4: подпись «Не по умолчанию: …» над кнопкой — есть при изменённом поле
  свёрнутого блока, нет при умолчаниях; текст дословно;
* 11Б: неактивные «Рассчитать вклады» и «Рассчитать Voigt–Reuss–Hill» с
  причиной под кнопкой; user_text отказов проверенного пути (BL-65, BL-67);
* 5–9: новые умолчания; 13Б: «(0.0001–5)» в двух подписях;
* 14Б: кольцо фокуса — сплошной primary; 15Б: на «Плотности по T» нет
  st.line_chart, ось без смещения; 16Б: две плитки результата диффузии.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
STYLE_PATH = APP / "style.css"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

PRECISION = "Точность и критерии"
PHASES = "Управление фазами / метастабильный расчёт"
MODEL = "Параметры модели"

# Экран (ключ строки кнопки) -> текст основной кнопки.
ACTION_ROWS = {
    "single": "Рассчитать равновесие",
    "temperature": "Построить график по температуре",
    "concentration": "Построить график по составу",
    "binary": "Построить диаграмму состояния",
    "isopleth": "Построить многокомпонентное сечение",
    "ternary": "Построить тройную диаграмму",
    "ternary_map": "Построить карту доли фазы",
    "solidification": "Рассчитать затвердевание",
    "energy_curve": "Рассчитать энергии фаз",
    "driving_force": "Рассчитать движущую силу",
    "tzero": "Рассчитать T₀",
    "physical_single": "Рассчитать плотность и объёмные доли",
    "physical_scan": "Построить плотность по температуре",
    "elastic_prepare": "Получить фазовые доли",
    "strengthening": "Рассчитать вклады",
    "diffusion_single": "Рассчитать однофазную диффузию",
    "diffusion_homogenization": "Рассчитать гомогенизацию",
    "precipitation": "Рассчитать кинетику выделений",
    "installation_check": "Проверить базы и запустить три контрольных расчёта",
}

# Вкладка экрана (база ni) -> блок -> свёрнутые поля 21-М.
FOLDED = {
    "Температурный диапазон": {PRECISION: ["Показывать на графике фазы с максимумом не менее, %"]},
    "Изменение состава": {PRECISION: ["Показывать на графике фазы с максимумом не менее, %"]},
    "Бинарная T–X": {PRECISION: [
        "Шаг по составу, ат.%",
        "Шаг по температуре, °C",
        "Показывать линии связи в двухфазных областях",
        "Показывать узловые точки",
    ]},
    "Многокомпонентное T–X": {PRECISION: [
        "Шаг по составу, ат.%",
        "Шаг по температуре, °C",
        "Показывать узловые точки",
    ]},
    "Тройная при T = const": {PRECISION: [
        "Шаг поиска границ, ат.% (0.5–10)",
        "Показывать линии связи в двухфазных областях",
        "Показывать каждую N-ю линию связи (1–50)",
        "Показывать точки трёхфазного равновесия",
    ]},
    "Карта доли фазы": {PRECISION: [
        "Единицы состава на треугольнике",
        "Желаемый шаг сетки, % (2–20)",
        "Провести границу появления фазы при доле, мол.% (0–100)",
        "Шкала цвета",
    ]},
    "Затвердевание": {PRECISION: ["Начальная температура, °C", "Шаг охлаждения, °C"]},
    "Энергии фаз": {PRECISION: ["Шаг температуры, °C", "Что показать на графике"]},
    "Движущая сила": {
        PRECISION: ["Шаг температуры, °C"],
        PHASES: ["Исключить выбранную фазу из исходного равновесия", "Фазы исходного равновесия"],
    },
    "T₀": {PRECISION: ["Al: шаг, ат.%"]},
    "Плотность": {PHASES: ["Выбрать фазы вручную", "Фазы"]},
    "Плотность по T": {PHASES: ["Выбрать фазы вручную", "Фазы"]},
    "Упругие свойства": {PHASES: ["Выбрать фазы вручную", "Фазы"]},
}
FOLDED_SINGLE_PAIR = {MODEL: [
    "Длина области, мкм",
    "Граница пары, % (1–99)",
    "Ячеек (12–160)",
    "Источник и назначение исходных данных диффузии",
]}
FOLDED_HOMOGENIZATION = {MODEL: FOLDED_SINGLE_PAIR[MODEL] + [
    "Модель эффективной подвижности",
    "Сглаживающий коэффициент ε (0–0.2)",
    "Лабиринтный фактор (1–2)",
]}
WIDGETS = {
    "NumberInput", "Checkbox", "Radio", "Selectbox", "Multiselect", "TextArea",
    "SelectSlider", "Slider", "TextInput",
}


# --------------------------------------------------------------------------- #
# Статические проверки
# --------------------------------------------------------------------------- #


def _css_rules() -> list[tuple[list[str], dict[str, str]]]:
    css = re.sub(r"/\*.*?\*/", "", STYLE_PATH.read_text("utf-8"), flags=re.S)
    rules = []
    for block in css.split("}"):
        if "{" not in block:
            continue
        head, body = block.split("{", 1)
        selectors = [" ".join(part.split()) for part in head.split(",") if part.strip()]
        properties = {}
        for item in body.split(";"):
            if ":" in item:
                name, value = item.split(":", 1)
                properties[name.strip()] = " ".join(value.split())
        rules.append((selectors, properties))
    return rules


def test_sticky_action_row_rule() -> None:
    selector = (
        'div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"]'
        ':has(> [class*="st-key-tg_action_"])'
    )
    found = [props for selectors, props in _css_rules() if selectors == [selector]]
    assert found == [{
        "position": "sticky",
        "bottom": "0",
        "z-index": "2",
        "background-color": "light-dark(#F8F8F9, #17181B)",
        "border-top": "1px solid light-dark(#CFD1D5, #33373E)",
        "padding": "12px 0",
    }]


def test_focus_ring_is_solid_primary() -> None:
    expected = {
        'button[data-testid^="stBaseButton-"]:focus-visible',
        'div[data-testid="stButtonGroup"] button:focus-visible',
        '[data-testid="stTab"]:focus-visible',
        'div[data-testid="stExpander"] summary:focus-visible',
        '[data-testid="stHeaderActionElements"] a:focus-visible',
        '[data-testid="stTooltipHoverTarget"] button:focus-visible',
    }
    found = [props for selectors, props in _css_rules() if set(selectors) == expected]
    assert found == [{"box-shadow": "0 0 0 0.2rem light-dark(#1F60C1, #5C97E8)"}]
    # Правило 21-З о фоне основной кнопки в фокусе осталось.
    focus_background = [
        props for selectors, props in _css_rules()
        if 'button[data-testid="stBaseButton-primary"]:not(:disabled):not(:active):focus-visible' in selectors
    ]
    assert focus_background == [{
        "background-color": "light-dark(#153F7F, #4587DE)",
        "border-color": "light-dark(#153F7F, #4587DE)",
    }]


def _calls(file_name: str, name: str) -> list[ast.Call]:
    tree = ast.parse((APP / file_name).read_text("utf-8"))
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (getattr(node.func, "attr", None) == name or getattr(node.func, "id", None) == name)
    ]


def test_action_rows_in_code() -> None:
    keys = []
    for file_name in (
        "ThermoGar_app.py", "thermogar_diffusion.py",
        "thermogar_precipitation.py", "thermogar_stage14.py",
    ):
        for call in _calls(file_name, "action_row"):
            sticky = {k.arg: k.value for k in call.keywords}.get("sticky")
            keys.append((
                ast.literal_eval(call.args[0]),
                True if sticky is None else ast.literal_eval(sticky),
            ))
    sticky_keys = [key for key, sticky in keys if sticky]
    # «Плотность» и «Плотность по T» — по две строки (ранний выход ниже
    # границы физической базы), на странице каждая одна.
    assert sorted(set(sticky_keys)) == sorted(ACTION_ROWS)
    assert len(sticky_keys) == 21
    assert [key for key, sticky in keys if not sticky] == ["b4b2_elastic_vrh_action"]


def test_no_line_chart_in_app() -> None:
    for path in APP.glob("*.py"):
        assert not _calls(path.name, "line_chart"), path.name


def test_density_scan_shows_the_png_figure() -> None:
    tree = ast.parse((APP / "ThermoGar_app.py").read_text("utf-8"))
    function = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "render_b4b_density_temperature"
    )
    source = ast.unparse(function)
    assert "st.pyplot(chart_figure(figure))" in source
    assert "ThemedFigure(plot_density_temperature, table)" in source


def test_density_axis_formatter_plain() -> None:
    """Ось плотности без смещения: ThermoGar_app — сценарий, проверка по коду
    и тем же вызовом matplotlib на узком диапазоне."""

    tree = ast.parse((APP / "ThermoGar_app.py").read_text("utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "plot_density_temperature"
    )
    assert "axes.ticklabel_format(axis='y', style='plain', useOffset=False)" in ast.unparse(function)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots()
    try:
        axes.plot([1.0, 2.0, 3.0], [7600.11, 7600.12, 7600.13])
        figure.canvas.draw()
        assert axes.yaxis.get_major_formatter().get_offset() != ""
        axes.ticklabel_format(axis="y", style="plain", useOffset=False)
        figure.canvas.draw()
        assert axes.yaxis.get_major_formatter().get_offset() == ""
        assert all("," not in label.get_text() for label in axes.get_yticklabels())
    finally:
        plt.close(figure)


def test_diffusion_result_has_two_metrics() -> None:
    tree = ast.parse((APP / "thermogar_diffusion.py").read_text("utf-8"))
    function = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_result_display"
    )
    labels = [
        ast.literal_eval(node.args[0]) for node in ast.walk(function)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "metric"
    ]
    assert labels == ["Время выдержки, ч", "Макс. ошибка баланса, u-доля"]


def test_defaults_5_to_9() -> None:
    source = (APP / "ThermoGar_app.py").read_text("utf-8")
    tree = ast.parse(source)
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"ISOPLETH_DEFAULTS", "CONCENTRATION_SCAN_DEFAULTS"}:
                values[name] = ast.literal_eval(node.value)
            if name == "DATABASE_DEFINITIONS":
                fe = next(
                    v for k, v in zip(node.value.keys, node.value.values)
                    if ast.literal_eval(k) == "fe"
                )
                values["fe"] = {
                    ast.literal_eval(k): ast.literal_eval(v)
                    for k, v in zip(fe.keys, fe.values)
                    if ast.literal_eval(k).startswith("default_t_")
                }
    assert values["fe"] == {"default_t_min": 500.0, "default_t_max": 900.0, "default_t_step": 100.0}
    assert values["CONCENTRATION_SCAN_DEFAULTS"] == {
        "fe": {"variable": "C", "c_min": 0.1, "c_max": 0.5, "c_step": 0.1},
        "al": {"variable": "CU", "c_min": 1.0, "c_max": 5.0, "c_step": 1.0},
    }
    assert values["ISOPLETH_DEFAULTS"]["ni"] == {
        "variable": "AL", "fixed": "CR=8", "c_min": 0.0, "c_max": 30.0,
        "c_step": 2.0, "t_min": 625.0, "t_max": 1625.0, "t_step": 50.0,
    }
    import thermogar_diffusion

    assert thermogar_diffusion.DEFAULTS["ni"]["homogenization_phases"] == ["FCC_A1", "NIAL"]


# --------------------------------------------------------------------------- #
# Подпись «Не по умолчанию» и причины — функции
# --------------------------------------------------------------------------- #


def test_folded_fields_caption() -> None:
    from thermogar_release_ui import FoldedFields, field_label_without_bounds, same_as_default

    folded = FoldedFields()
    folded.note("Шаг по температуре, °C", 25.0, 25.0)
    folded.note("Фазы", ("B", "A"), ["A", "B"])
    folded.note("Показывать узловые точки", False, False)
    folded.note("Ячеек (12–160)", 80, 80)
    assert folded.caption_text() is None
    folded.note("Шаг поиска границ, ат.% (0.5–10)", 3.0, 5.0)
    folded.note("Фазы", ("A",), ["A", "B"])
    folded.note("ν (Orowan) (-0.999–0.499)", 0.31, 0.3)
    assert folded.caption_text() == "Не по умолчанию: Шаг поиска границ, ат.%; Фазы; ν (Orowan)."
    assert same_as_default(0.1 + 1e-12, 0.1)
    assert not same_as_default(0.1 + 1e-6, 0.1)
    assert field_label_without_bounds("M (Taylor)") == "M (Taylor)"
    assert field_label_without_bounds("Максимальная проверяемая температура, °C (-200–1726.85)") == (
        "Максимальная проверяемая температура, °C"
    )


def test_elastic_rows_missing_text() -> None:
    import thermogar_properties as properties

    full = {"phase": "A", "young_gpa": 200.0, "poisson": 0.3, "origin": "справочник",
            "source": "DOI", "reference_temperature_c": 20.0}
    assert properties.elastic_rows_missing_text([full]) is None
    assert properties.elastic_rows_missing_text([
        {**full, "phase": "FCC_A1", "young_gpa": None},
        {**full, "phase": "GAMMA_PRIME", "poisson": float("nan")},
    ]) == "Не заданы E и ν для фаз: FCC_A1, GAMMA_PRIME."
    assert properties.elastic_rows_missing_text([
        {**full, "phase": "FCC_A1", "origin": " "},
        {**full, "phase": "B", "young_gpa": None},
    ]) == "Не заданы E и ν для фаз: B."
    assert properties.elastic_rows_missing_text([{**full, "phase": "FCC_A1", "source": None}]) == (
        "Для каждой фазы обязательны происхождение и источник: FCC_A1."
    )
    assert properties.elastic_rows_missing_text([
        {**full, "phase": "FCC_A1", "reference_temperature_c": None}
    ]) == "Для каждой фазы обязательна температура источника: FCC_A1."


def _vrh_error(row_update: dict[str, Any]):
    import thermogar_verified_loaders as loaders
    import thermogar_verified_properties as verified

    row = {field: None for field in verified.VRH_ROW_FIELDS}
    row.update({"phase": "FCC_A1", "volume_fraction": 1.0, "young_gpa": 200.0, "poisson": 0.3,
                "origin": "справочник", "source": "DOI", "reference_temperature_c": 20.0,
                "note": ""})
    row.update(row_update)
    witness = SimpleNamespace(phase_rows=(("FCC_A1", 1.0),))
    with pytest.raises(loaders.VerifiedLoaderError) as caught:
        verified._validate_vrh_rows([row], witness)
    return caught.value


@pytest.mark.parametrize(
    ("update", "text"),
    [
        ({"young_gpa": None}, "Не заданы E и ν для фаз: FCC_A1."),
        ({"poisson": None, "source": None}, "Не заданы E и ν для фаз: FCC_A1."),
        ({"origin": None}, "Для каждой фазы обязательны происхождение и источник: FCC_A1."),
        ({"source": None, "reference_temperature_c": None},
         "Для каждой фазы обязательны происхождение и источник: FCC_A1."),
        ({"reference_temperature_c": None}, "Для каждой фазы обязательна температура источника: FCC_A1."),
    ],
)
def test_vrh_refusal_user_text(update: dict[str, Any], text: str) -> None:
    import thermogar_verified_loaders as loaders

    error = _vrh_error(update)
    assert error.reason_code is loaders.ReasonCode.USER_INPUT_REQUIRED
    assert error.detail == "Complete phase modulus provenance is required."
    assert error.user_text == text


def test_strengthening_refusal_user_text() -> None:
    import thermogar_verified_loaders as loaders
    import thermogar_verified_properties as verified

    inputs = verified.make_strengthening_inputs(
        input_provenance="Проверка 21-М", input_confirmation=False, sigma_internal_mpa=0.0,
        hall_petch=None, taylor=None, solid_solution_mpa=None, orowan=None, other_mpa=None,
        summation_rule="Не суммировать", hill_witness_digest=None,
    )
    with pytest.raises(loaders.VerifiedLoaderError) as caught:
        verified._strengthening_inputs(inputs, None)
    assert caught.value.reason_code is loaders.ReasonCode.USER_INPUT_REQUIRED
    assert caught.value.detail == "Strengthening input scope must be confirmed."
    assert caught.value.user_text == "Подтвердите область применимости введённых коэффициентов."
    inputs["input_provenance"] = None
    with pytest.raises(loaders.VerifiedLoaderError) as caught:
        verified._strengthening_inputs(inputs, None)
    assert caught.value.user_text == "Укажите источник и область применимости всех коэффициентов."


# --------------------------------------------------------------------------- #
# AppTest
# --------------------------------------------------------------------------- #


def _start(base: str = "ni"):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(APP / "ThermoGar_app.py"), default_timeout=900)
    app.session_state["thermogar_database_key"] = base
    app.run()
    assert not app.exception, [element.message for element in app.exception]
    return app


def _walk(node, acc=None):
    acc = acc if acc is not None else []
    acc.append(node)
    for child in getattr(node, "children", {}).values():
        _walk(child, acc)
    return acc


def _rows(app) -> dict[str, Any]:
    rows = {}
    for node in _walk(app._tree):
        proto = getattr(node, "proto", None)
        node_id = str(getattr(proto, "id", "")) if proto is not None else ""
        match = re.search(r"-(tg_action_\w+|b4b2_elastic_vrh_action)$", node_id)
        if match and type(node).__name__ == "Block":
            rows[match.group(1)] = node
    return rows


def _row_items(row) -> list[tuple[str, Any]]:
    return [
        (type(node).__name__, getattr(node, "label", None) or getattr(node, "value", None))
        for node in _walk(row)[1:]
        if type(node).__name__ in {"Button", "Caption"}
    ]


def _tab(app, label: str):
    tabs = [tab for tab in app.tabs if tab.label == label]
    assert len(tabs) == 1, (label, len(tabs))
    return tabs[0]


def _folded_labels(node) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    for item in _walk(node):
        if type(item).__name__ == "Expander" and item.label in {PRECISION, PHASES, MODEL}:
            blocks.setdefault(item.label, []).extend(
                child.label for child in _walk(item)[1:] if type(child).__name__ in WIDGETS
            )
    return blocks


def _open_labels(node) -> list[str]:
    inside = set()
    for item in _walk(node):
        if type(item).__name__ == "Expander":
            inside.update(id(child) for child in _walk(item)[1:])
    return [
        item.label for item in _walk(node)
        if type(item).__name__ in WIDGETS and id(item) not in inside
    ]


def test_action_rows_and_folded_fields_ni() -> None:
    app = _start("ni")
    # Ручной выбор фаз в трёх экранах «Свойств» показывает поле «Фазы».
    for key in ("physical_single_manual", "physical_scan_manual", "b4b2_elastic_prepare_manual"):
        app.checkbox(key=key).check()
    app.run()
    assert not app.exception, [element.message for element in app.exception]

    rows = _rows(app)
    manual = {"physical_single", "physical_scan", "elastic_prepare"}
    for key, text in ACTION_ROWS.items():
        if key == "diffusion_homogenization":
            continue
        items = _row_items(rows[f"tg_action_{key}"])
        expected = [("Button", text)]
        if key in manual:
            expected.insert(0, ("Caption", "Не по умолчанию: Выбрать фазы вручную."))
        if key == "strengthening":
            expected.append(
                ("Caption", "Укажите источник и область применимости всех коэффициентов.")
            )
        assert items == expected, (key, items)

    count = 0
    for tab_label, blocks in FOLDED.items():
        found = _folded_labels(_tab(app, tab_label))
        open_labels = _open_labels(_tab(app, tab_label))
        for block, labels in blocks.items():
            for label in labels:
                assert label in found.get(block, []), (tab_label, block, label, found)
                assert label not in open_labels, (tab_label, label)
                count += 1
    diffusion = _tab(app, "Диффузия и гомогенизация")
    found = _folded_labels(diffusion)
    assert found == FOLDED_SINGLE_PAIR, found
    assert "Время, ч" in _open_labels(diffusion)
    count += len(FOLDED_SINGLE_PAIR[MODEL])

    app.segmented_control(key="kinetics_diffusion_view").set_value("Многофазная гомогенизация").run()
    assert not app.exception, [element.message for element in app.exception]
    diffusion = _tab(app, "Диффузия и гомогенизация")
    found = _folded_labels(diffusion)
    assert found == FOLDED_HOMOGENIZATION, found
    assert "Время, ч" in _open_labels(diffusion)
    assert _row_items(_rows(app)["tg_action_diffusion_homogenization"]) == [
        ("Button", "Рассчитать гомогенизацию")
    ]
    count += len(FOLDED_HOMOGENIZATION[MODEL])
    assert count == 42


def test_not_default_caption_ni() -> None:
    app = _start("ni")
    # При умолчаниях подписи нет ни на одном экране.
    assert not [c.value for c in app.caption if c.value.startswith("Не по умолчанию")]
    default_step = app.number_input(key="binary_t_step_ni").value
    assert default_step == 10.0
    app.number_input(key="binary_t_step_ni").set_value(20.0).run()
    assert _row_items(_rows(app)["tg_action_binary"]) == [
        ("Caption", "Не по умолчанию: Шаг по температуре, °C."),
        ("Button", "Построить диаграмму состояния"),
    ]
    app.checkbox(key="binary_nodes_ni").check().run()
    app.radio(key="binary_diagram_phase_mode_ni").set_value(
        "Вручную — поставить или снять галочки"
    ).run()
    assert _row_items(_rows(app)["tg_action_binary"])[0] == (
        "Caption",
        "Не по умолчанию: Шаг по температуре, °C; Показывать узловые точки; Какие фазы учитывать.",
    )
    app.number_input(key="binary_t_step_ni").set_value(default_step).run()
    app.checkbox(key="binary_nodes_ni").uncheck().run()
    app.radio(key="binary_diagram_phase_mode_ni").set_value(
        "Автоматически — все совместимые фазы"
    ).run()
    assert _row_items(_rows(app)["tg_action_binary"]) == [
        ("Button", "Построить диаграмму состояния")
    ]
    # Блоки механизмов «Вкладов упрочнения» и «Численная сетка размеров».
    app.checkbox(key="b4b2_hall_use_ni").check().run()
    assert _row_items(_rows(app)["tg_action_strengthening"])[0] == (
        "Caption", "Не по умолчанию: Учитывать Hall–Petch."
    )
    grid_bins = [s for s in app.slider if s.label == "Классов размеров"]
    assert len(grid_bins) == 1
    grid_bins[0].set_value(100).run()
    assert _row_items(_rows(app)["tg_action_precipitation"])[0] == (
        "Caption", "Не по умолчанию: Классов размеров."
    )


def test_disabled_buttons_with_reason_ni() -> None:
    app = _start("ni")

    def strengthening():
        items = _row_items(_rows(app)["tg_action_strengthening"])
        button = [b for b in app.button if b.key == "b4b2_strengthening_calculate"][0]
        return button.disabled, items

    disabled, items = strengthening()
    assert disabled
    assert items == [
        ("Button", "Рассчитать вклады"),
        ("Caption", "Укажите источник и область применимости всех коэффициентов."),
    ]
    app.text_area(key="b4b2_strengthening_provenance_ni").set_value("   ").run()
    assert strengthening()[1][1] == (
        "Caption", "Укажите источник и область применимости всех коэффициентов."
    )
    app.text_area(key="b4b2_strengthening_provenance_ni").set_value("Проверка 21-М").run()
    disabled, items = strengthening()
    assert disabled
    assert items == [
        ("Button", "Рассчитать вклады"),
        ("Caption", "Подтвердите область применимости введённых коэффициентов."),
    ]
    app.checkbox(key="b4b2_strengthening_confirmation_ni").check().run()
    disabled, items = strengthening()
    assert not disabled
    assert items == [("Button", "Рассчитать вклады")]

    [b for b in app.button if b.key == "b4b2_elastic_prepare_calculate"][0].click().run()
    assert not app.exception, [element.message for element in app.exception]
    vrh = [b for b in app.button if b.key == "b4b2_elastic_vrh_calculate"]
    assert len(vrh) == 1 and vrh[0].disabled
    items = _row_items(_rows(app)["b4b2_elastic_vrh_action"])
    assert items[0] == ("Button", "Рассчитать Voigt–Reuss–Hill")
    assert len(items) == 2 and items[1][0] == "Caption"
    assert re.fullmatch(r"Не заданы E и ν для фаз: [A-Z0-9_]+(, [A-Z0-9_]+)*\.", items[1][1]), items


def test_labels_13_and_defaults_ni() -> None:
    app = _start("ni")
    labels = {item.key: item.label for item in app.number_input if item.key}
    assert labels["solidification_stop_ni"] == "Scheil: остановить при остатке расплава, % (0.0001–5)"
    assert labels["solidification_appearance_ni"] == "Порог появления фазы, % (0.0001–5)"
    values = {item.key: item.value for item in app.number_input if item.key}
    assert (values["isopleth_c_max_ni_NI_AL"], values["isopleth_c_step_ni_NI_AL"]) == (30.0, 2.0)
    assert (values["isopleth_t_min_ni"], values["isopleth_t_max_ni"], values["isopleth_t_step_ni"]) == (
        625.0, 1625.0, 50.0,
    )
    assert [t.value for t in app.text_area if t.key == "isopleth_fixed_ni_NI_AL"] == ["Cr=8"]
    app.segmented_control(key="kinetics_diffusion_view").set_value("Многофазная гомогенизация").run()
    assert [m.value for m in app.multiselect if m.key == "kin_hom_phases_ni"] == [["FCC_A1", "NIAL"]]


@pytest.mark.parametrize(
    ("base", "element", "labels"),
    [
        ("fe", "C", {"C: от, мас.%": 0.1, "C: до, мас.%": 0.5, "C: шаг, мас.%": 0.1}),
        ("al", "CU", {"Cu: от, ат.%": 1.0, "Cu: до, ат.%": 5.0, "Cu: шаг, ат.%": 1.0}),
    ],
)
def test_concentration_defaults(base: str, element: str, labels: dict[str, float]) -> None:
    app = _start(base)
    tab = _tab(app, "Изменение состава")
    selects = [item for item in _walk(tab) if type(item).__name__ == "Selectbox"
               and item.label == "Изменяемый элемент"]
    assert [item.value for item in selects] == [element]
    numbers = {item.label: item.value for item in _walk(tab) if type(item).__name__ == "NumberInput"}
    for label, value in labels.items():
        assert numbers[label] == pytest.approx(value)
    if base == "fe":
        values = {item.key: item.value for item in app.number_input if item.key}
        assert (values["t_min_fe"], values["t_max_fe"], values["t_step_fe"]) == (500.0, 900.0, 100.0)
        assert (
            values["physical_t_min_fe"], values["physical_t_max_fe"], values["physical_t_step_fe"]
        ) == (500.0, 900.0, 100.0)
