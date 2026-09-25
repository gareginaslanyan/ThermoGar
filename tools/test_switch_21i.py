"""Переключатель вместо вкладок в «Кинетике» и «Затвердевании» (21-И, N-4).

* «Диффузия и гомогенизация», виды результата «Выделений» и «Затвердевания» —
  st.segmented_control на месте st.tabs: те же названия в том же порядке,
  default — первый, required=True, подпись — заголовок раздела (скрыта),
  свой key, persist_state="session";
* исполняется только выбранный вид (цепочка if / elif по значению
  переключателя), и у каждого виджета внутри видов, у которого в Streamlit 1.62
  есть persist_state, — persist_state="session" и key; виджеты ищутся и в
  функциях этого же модуля, которые вызываются из видов;
* style.css: у выбранного варианта при наведении и фокусе фон — как в покое
  (primary с альфой 0.1), кольцо фокуса штатное;
* AppTest (база ni): значение поля «Левая сторона» переживает переход на
  «Покрытие базы подвижностей» и обратно; снять выбор переключателя нельзя.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
STYLE_PATH = APP / "style.css"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

# Виджеты Streamlit 1.62 с параметром persist_state.
PERSIST_WIDGETS = {
    "selectbox",
    "radio",
    "text_area",
    "text_input",
    "number_input",
    "multiselect",
    "checkbox",
    "toggle",
    "slider",
    "select_slider",
    "segmented_control",
    "pills",
    "color_picker",
    "date_input",
    "time_input",
}

SWITCHES = {
    "kinetics_diffusion_view": (
        "thermogar_diffusion.py",
        "Диффузия и гомогенизация",
        ["Однофазная пара", "Многофазная гомогенизация", "Покрытие базы подвижностей"],
    ),
    "precipitation_result_view": (
        "thermogar_precipitation.py",
        "Кинетика выделений",
        ["Итоги", "Кинетика и состав", "Распределение размеров", "Экспорт и ограничения"],
    ),
    "solidification_result_view": (
        "ThermoGar_app.py",
        "Затвердевание",
        ["Сводка", "Твёрдые фазы", "Остаточный расплав", "Выгрузка"],
    ),
}


def _tree(file_name: str) -> ast.Module:
    return ast.parse((APP / file_name).read_text("utf-8"))


def _is_st_call(node: ast.AST, name: str | None = None) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "st"
        and (name is None or node.func.attr == name)
    )


def _keywords(call: ast.Call) -> dict[str, Any]:
    return {item.arg: item.value for item in call.keywords if item.arg}


def _literal(node: ast.AST) -> Any:
    return ast.literal_eval(node)


def _switch_call(tree: ast.Module, key: str) -> tuple[str, ast.Call]:
    found = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and _is_st_call(node.value, "segmented_control")
            and "key" in _keywords(node.value)
            and _literal(_keywords(node.value)["key"]) == key
        ):
            assert len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
            found.append((node.targets[0].id, node.value))
    assert len(found) == 1, (key, len(found))
    return found[0]


def _view_branches(tree: ast.Module, variable: str) -> dict[str, list[ast.stmt]]:
    """Цепочка if / elif по значению переключателя: вид -> тело."""

    branches: dict[str, list[ast.stmt]] = {}
    seen: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or id(node) in seen:
            continue
        current: ast.AST | None = node
        chain = {}
        while isinstance(current, ast.If):
            test = current.test
            if not (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == variable
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Eq)
            ):
                break
            seen.add(id(current))
            chain[_literal(test.comparators[0])] = current.body
            if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                current = current.orelse[0]
            else:
                assert not current.orelse, "после последнего вида — без else"
                current = None
        if chain:
            assert not branches, f"две цепочки по {variable}"
            branches = chain
    return branches


def _module_functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def _widgets_in(
    statements: list[ast.stmt],
    functions: dict[str, ast.FunctionDef],
    visited: set[str] | None = None,
) -> list[ast.Call]:
    """Вызовы st.<виджет с persist_state> в теле и в вызванных функциях модуля."""

    visited = set() if visited is None else visited
    calls: list[ast.Call] = []
    for statement in statements:
        for node in ast.walk(statement):
            if _is_st_call(node) and node.func.attr in PERSIST_WIDGETS:
                calls.append(node)
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in functions
                and node.func.id not in visited
            ):
                visited.add(node.func.id)
                calls.extend(
                    _widgets_in(functions[node.func.id].body, functions, visited)
                )
    return calls


@pytest.mark.parametrize("key", sorted(SWITCHES))
def test_switch_replaces_tabs(key: str) -> None:
    file_name, label, options = SWITCHES[key]
    tree = _tree(file_name)
    for node in ast.walk(tree):
        if _is_st_call(node, "tabs") and node.args:
            try:
                names = _literal(node.args[0])
            except ValueError:
                continue
            assert names != options, f"{file_name}: st.tabs({options}) остался"
    _variable, call = _switch_call(tree, key)
    assert _literal(call.args[0]) == label
    assert _literal(call.args[1]) == options
    keywords = _keywords(call)
    assert _literal(keywords["default"]) == options[0]
    assert _literal(keywords["required"]) is True
    assert _literal(keywords["label_visibility"]) == "collapsed"
    assert _literal(keywords["persist_state"]) == "session"
    assert "selection_mode" not in keywords


@pytest.mark.parametrize("key", sorted(SWITCHES))
def test_only_selected_view_runs(key: str) -> None:
    file_name, _label, options = SWITCHES[key]
    tree = _tree(file_name)
    variable, _call = _switch_call(tree, key)
    branches = _view_branches(tree, variable)
    assert list(branches) == options
    # Значение переключателя больше нигде не читается, кроме цепочки видов.
    uses = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == variable and isinstance(node.ctx, ast.Load)
    ]
    assert len(uses) == len(options)


@pytest.mark.parametrize("key", sorted(SWITCHES))
def test_widgets_inside_views_persist(key: str) -> None:
    file_name, _label, _options = SWITCHES[key]
    tree = _tree(file_name)
    variable, _call = _switch_call(tree, key)
    functions = _module_functions(tree)
    problems = []
    for view, body in _view_branches(tree, variable).items():
        for call in _widgets_in(body, functions):
            keywords = _keywords(call)
            where = f"{file_name}:{call.lineno} st.{call.func.attr} ({view})"
            if "key" not in keywords:
                problems.append(f"{where}: нет key")
            persist = keywords.get("persist_state")
            if persist is None or _literal(persist) != "session":
                problems.append(f"{where}: нет persist_state=\"session\"")
    assert problems == [], problems


def test_persistent_widget_count() -> None:
    """Перечень отчёта 21-И: 16 виджетов в «Диффузии», 0 в «Выделениях», 4 в «Затвердевании»."""

    counts = {}
    for key, (file_name, _label, _options) in SWITCHES.items():
        tree = _tree(file_name)
        variable, _call = _switch_call(tree, key)
        functions = _module_functions(tree)
        calls = {
            (call.lineno, call.col_offset)
            for body in _view_branches(tree, variable).values()
            for call in _widgets_in(body, functions)
        }
        counts[key] = len(calls)
    assert counts == {
        "kinetics_diffusion_view": 16,
        "precipitation_result_view": 0,
        "solidification_result_view": 4,
    }


def _css_rules() -> list[tuple[list[str], dict[str, str]]]:
    css = re.sub(r"/\*.*?\*/", "", STYLE_PATH.read_text("utf-8"), flags=re.S)
    rules = []
    for block in css.split("}"):
        if "{" not in block:
            continue
        head, body = block.split("{", 1)
        selectors = [" ".join(part.split()) for part in head.split(",") if part.strip()]
        declarations = {}
        for item in body.split(";"):
            if ":" in item:
                name, value = item.split(":", 1)
                declarations[name.strip()] = " ".join(value.split())
        rules.append((selectors, declarations))
    return rules


def test_selected_option_keeps_rest_background_on_hover_and_focus() -> None:
    # В 1.62 вариант — button role="radio" без data-testid (сверено по DOM, 21-И).
    marker = (
        'div[data-testid="stButtonGroup"] '
        'button[data-variant="segmented_control"][aria-checked="true"]'
    )
    rules = [
        (selector, declarations)
        for selectors, declarations in _css_rules()
        for selector in selectors
        if selector.startswith(marker)
    ]
    selectors = {selector for selector, _ in rules}
    assert selectors == {
        marker + ":not(:disabled):hover",
        marker + ":not(:disabled):focus-visible",
    }
    for _selector, declarations in rules:
        assert declarations == {
            "background-color": "light-dark(rgba(31, 96, 193, 0.1), rgba(92, 151, 232, 0.1))"
        }
    # Невыбранный вариант и кольцо фокуса — штатные.
    for selectors_, declarations in _css_rules():
        for selector in selectors_:
            assert "segmented_control" not in selector or selector.startswith(marker)
            if selector.startswith(marker):
                assert not {"outline", "box-shadow", "color", "border-color"} & set(declarations)


def test_rest_background_is_primary_with_alpha_01() -> None:
    """Фон покоя в Streamlit — primary с прозрачностью 0.9; primary темы — config.toml."""

    config = (ROOT / ".streamlit" / "config.toml").read_text("utf-8")
    primaries = re.findall(r'^primaryColor\s*=\s*"(#[0-9A-Fa-f]{6})"', config, flags=re.M)
    assert primaries == ["#1F60C1", "#5C97E8"]
    rgb = [tuple(int(color[i : i + 2], 16) for i in (1, 3, 5)) for color in primaries]
    assert rgb == [(31, 96, 193), (92, 151, 232)]


# --------------------------------------------------------------------------- #
# AppTest
# --------------------------------------------------------------------------- #


def _start_ni():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(APP / "ThermoGar_app.py"), default_timeout=900)
    app.session_state["thermogar_database_key"] = "ni"
    app.run()
    assert not app.exception, [element.message for element in app.exception]
    return app


def _text_area(app, key: str):
    matches = [item for item in app.text_area if item.key == key]
    return matches[0] if matches else None


def test_value_survives_view_switch_and_switch_cannot_be_cleared() -> None:
    app = _start_ni()
    switch = app.segmented_control(key="kinetics_diffusion_view")
    assert switch.value == "Однофазная пара"
    assert switch.options == [
        "Однофазная пара",
        "Многофазная гомогенизация",
        "Покрытие базы подвижностей",
    ]
    left = _text_area(app, "kin_single_left_ni")
    assert left is not None and left.label == "Левая сторона"
    new_value = "CR=12, AL=4"
    assert left.value != new_value
    left.set_value(new_value).run()
    assert _text_area(app, "kin_single_left_ni").value == new_value

    app.segmented_control(key="kinetics_diffusion_view").set_value(
        "Покрытие базы подвижностей"
    ).run()
    assert not app.exception, [element.message for element in app.exception]
    assert _text_area(app, "kin_single_left_ni") is None
    assert not [item for item in app.button if item.key == "kin_single_run_ni"]

    app.segmented_control(key="kinetics_diffusion_view").set_value(
        "Однофазная пара"
    ).run()
    assert _text_area(app, "kin_single_left_ni").value == new_value

    # required=True: попытка снять выбор оставляет выбранный вид.
    app.segmented_control(key="kinetics_diffusion_view").set_value(None).run()
    assert not app.exception, [element.message for element in app.exception]
    assert app.segmented_control(key="kinetics_diffusion_view").value == "Однофазная пара"
    assert _text_area(app, "kin_single_left_ni").value == new_value
    # Предупреждений Streamlit о значении по умолчанию и Session State нет.
    assert not [
        item.value
        for item in app.warning
        if "Session State" in str(item.value) or "default value" in str(item.value)
    ]
