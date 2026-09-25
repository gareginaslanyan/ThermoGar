#!/usr/bin/env python3
"""Входы ячеек 22-А/22-Б, собранные разбором исходников (ast), а не переписанные руками.

22-Б добавила ячейки ``umolch_ni``, ``umolch_al``, ``umolch_fe`` — умолчания
раздела «Выделения» (``DEFAULTS[база]``, виджеты пользовательского режима:
80 классов, 0,2–10 нм, bulk_n0 виджета) на составе по умолчанию боковой панели
базы (``app/ThermoGar_app.py``, ``DATABASE_DEFINITIONS``), и ``718`` — случай
15-В из ``tools/test_precipitation_bl35.py`` (``study_wave15_v_718.case_arguments``).

Две ячейки BL-43:

* ``app`` — ячейка приложения, как её собирает
  ``tools/test_ui_g.py::test_kwn_precipitation[fe]``: пара и температура —
  ``KWN_CELL["fe"]``, время — ``SHORT_TIME_H``, классов — ``KWN_BINS``; состав —
  боковая панель fe (``app/ThermoGar_app.py``, ``default_composition``, мас.%;
  сверяется с ``SIDEBAR_ALLOY["fe"]`` теста); остальное — умолчания раздела
  «Выделения» (``app/thermogar_precipitation.py``: ``DEFAULTS["fe"]`` и значения
  виджетов ``render_precipitation_section`` в пользовательском режиме).
* ``backend`` — ячейка расчётного теста
  ``tools/test_backend_calculations.py::test_kwn_module[fe]``: поля ``CASES["fe"]``
  и именованные аргументы вызова ``run_precipitation`` в этом тесте.

Модули тестов и приложения не импортируются (импорт ``ThermoGar_app`` выполнил
бы сценарий Streamlit), только читаются.

    python -B vhody.py      # печатает обе ячейки
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
APP_SCRIPT = ROOT / "app" / "ThermoGar_app.py"
PRECIPITATION = ROOT / "app" / "thermogar_precipitation.py"
TEST_UI_G = ROOT / "tools" / "test_ui_g.py"
TEST_BACKEND = ROOT / "tools" / "test_backend_calculations.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _value(node: ast.AST) -> Any:
    """Литерал или арифметика над литералами (``1.0 / 3600.0``)."""

    try:
        return ast.literal_eval(node)
    except ValueError:
        expression = ast.Expression(body=node)
        ast.fix_missing_locations(expression)
        for child in ast.walk(node):
            if not isinstance(
                child,
                (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.operator, ast.unaryop),
            ):
                raise
        return eval(compile(expression, "<ast>", "eval"), {"__builtins__": {}}, {})


def _module_constant(tree: ast.Module, name: str) -> tuple[Any, int]:
    for node in tree.body:
        targets: list[ast.AST] = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                return _value(node.value), node.lineno
    raise KeyError(name)


def _widget_default(tree: ast.Module, key_suffix: str) -> tuple[Any, int]:
    """Значение виджета пользовательского режима по окончанию ключа.

    ``value=float(PRESET_NI[...] if demo else X)`` — берётся ветка ``else``;
    у ``st.slider(label, min, max, value, step)`` — четвёртый позиционный.
    """

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        key = next((kw.value for kw in node.keywords if kw.arg == "key"), None)
        if not isinstance(key, ast.JoinedStr):
            continue
        tail = key.values[-1]
        if not (isinstance(tail, ast.Constant) and str(tail.value).endswith(key_suffix)):
            continue
        value = next((kw.value for kw in node.keywords if kw.arg == "value"), None)
        if value is None and isinstance(node.func, ast.Attribute) and node.func.attr == "slider":
            value = node.args[3]
        if isinstance(value, ast.Call) and getattr(value.func, "id", "") == "float":
            value = value.args[0]
        if isinstance(value, ast.IfExp):
            value = value.orelse
        return _value(value), node.lineno
    raise KeyError(key_suffix)


def _sidebar_fe_composition(tree: ast.Module, database_key: str = "fe") -> tuple[dict[str, Any], int]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == database_key and isinstance(value, ast.Dict):
                fields = {
                    k.value: v for k, v in zip(value.keys, value.values)
                    if isinstance(k, ast.Constant)
                }
                if "default_composition" in fields:
                    return {
                        "default_balance": _value(fields["default_balance"]),
                        "default_composition": _value(fields["default_composition"]),
                        "default_units": _value(fields["default_units"]),
                    }, value.lineno
    raise KeyError(f"{database_key} default_composition")


def _normal(text: str) -> str:
    return "".join(str(text).upper().split())


def app_cell() -> dict[str, Any]:
    ui = _tree(TEST_UI_G)
    kwn_cell, kwn_line = _module_constant(ui, "KWN_CELL")
    short_time_h, short_line = _module_constant(ui, "SHORT_TIME_H")
    kwn_bins, bins_line = _module_constant(ui, "KWN_BINS")
    sidebar_test, sidebar_test_line = _module_constant(ui, "SIDEBAR_ALLOY")
    sidebar_app, sidebar_app_line = _sidebar_fe_composition(_tree(APP_SCRIPT))
    balance_test, composition_test, units_label_test = sidebar_test["fe"]
    units_app = sidebar_app["default_units"]
    if _normal(composition_test) != _normal(sidebar_app["default_composition"]):
        raise SystemExit(
            f"Состав fe в тесте {composition_test!r} и в приложении "
            f"{sidebar_app['default_composition']!r} расходятся"
        )
    if balance_test != sidebar_app["default_balance"] or units_label_test != (
        "массовые %" if units_app == "wt" else "атомные %"
    ):
        raise SystemExit("Основа или единицы fe в тесте и в приложении расходятся")

    precipitation = _tree(PRECIPITATION)
    defaults, defaults_line = _module_constant(precipitation, "DEFAULTS")
    provenance, provenance_line = _module_constant(precipitation, "DEFAULT_INPUT_PROVENANCE")
    nucleation_types, nucleation_line = _module_constant(precipitation, "NUCLEATION_TYPES")
    _matrix, _precipitate, _temperature, _duration, gamma, matrix_vm, precip_vm = defaults["fe"]
    widgets = {
        name: _widget_default(precipitation, suffix)
        for name, suffix in (
            ("bulk_n0", "_bulk_n0"),
            ("grain_size_um", "_grain_size_um"),
            ("dislocation_density", "_dislocation_density"),
            ("gb_energy", "_gb_energy"),
            ("cmin_nm", "_cmin_nm"),
            ("cmax_nm", "_cmax_nm"),
            ("bins_section", "_bins"),
        )
    }
    matrix, precipitate, temperature = kwn_cell["fe"]
    arguments = dict(
        database_key="fe",
        balance=sidebar_app["default_balance"],
        composition_text=sidebar_app["default_composition"],
        units=units_app,
        matrix_phase=matrix,
        precipitate_phase=precipitate,
        schedule_mode="isothermal",
        temperature_c=float(temperature),
        duration_h=float(short_time_h),
        profile_text="",
        gamma=float(gamma),
        matrix_vm=float(matrix_vm),
        precip_vm=float(precip_vm),
        # Selectbox центров без index — первый пункт NUCLEATION_TYPES.
        nucleation_type=next(iter(nucleation_types.values())),
        bulk_n0=float(widgets["bulk_n0"][0]),
        grain_size_um=float(widgets["grain_size_um"][0]),
        dislocation_density=float(widgets["dislocation_density"][0]),
        gb_energy=float(widgets["gb_energy"][0]),
        cmin_nm=float(widgets["cmin_nm"][0]),
        cmax_nm=float(widgets["cmax_nm"][0]),
        bins=int(kwn_bins),
        input_provenance=provenance,
        input_confirmation=True,
    )
    sources = {
        "KWN_CELL": f"tools/test_ui_g.py:{kwn_line}",
        "SHORT_TIME_H": f"tools/test_ui_g.py:{short_line}",
        "KWN_BINS": f"tools/test_ui_g.py:{bins_line}",
        "SIDEBAR_ALLOY": f"tools/test_ui_g.py:{sidebar_test_line}",
        "default_composition fe": f"app/ThermoGar_app.py:{sidebar_app_line}",
        "DEFAULTS": f"app/thermogar_precipitation.py:{defaults_line}",
        "DEFAULT_INPUT_PROVENANCE": f"app/thermogar_precipitation.py:{provenance_line}",
        "NUCLEATION_TYPES": f"app/thermogar_precipitation.py:{nucleation_line}",
        **{f"виджет {name}": f"app/thermogar_precipitation.py:{line}" for name, (_v, line) in widgets.items()},
    }
    section = {
        "fe_section_duration_h": float(_duration),
        "fe_section_bins": int(widgets["bins_section"][0]),
    }
    return {"arguments": arguments, "sources": sources, "section_defaults": section}


def backend_cell() -> dict[str, Any]:
    tree = _tree(TEST_BACKEND)
    case_fields: dict[str, Any] = {}
    case_line = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant) and key.value == "fe"
                and isinstance(value, ast.Call) and getattr(value.func, "id", "") == "Case"
            ):
                # Нужны только поля KWN и основа; прочие (frozenset(...)) — не литералы.
                case_fields = {
                    kw.arg: _value(kw.value) for kw in value.keywords
                    if kw.arg in {"key", "balance"} or str(kw.arg).startswith("kwn_")
                }
                case_line = value.lineno
    if not case_fields:
        raise SystemExit("CASES['fe'] не найден")
    call: ast.Call | None = None
    call_line = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "test_kwn_module":
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call) and getattr(inner.func, "id", "") == "run_precipitation":
                    call, call_line = inner, inner.lineno
    if call is None:
        raise SystemExit("вызов run_precipitation в test_kwn_module не найден")
    arguments: dict[str, Any] = {"database_key": "fe"}
    for keyword in call.keywords:
        node = keyword.value
        if keyword.arg in {"db", "database_path", "database_label", "composition_text"}:
            continue
        if isinstance(node, ast.Attribute) and getattr(node.value, "id", "") == "case":
            arguments[keyword.arg] = case_fields[node.attr]
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and getattr(node.value.value, "id", "") == "case"
        ):
            arguments[keyword.arg] = case_fields[node.value.attr][_value(node.slice)]
        else:
            arguments[keyword.arg] = _value(node)
    # Как в тесте: ", ".join(f"{element}={value:g}" ...).
    arguments["composition_text"] = ", ".join(
        f"{element}={value:g}" for element, value in case_fields["kwn_composition_pct"].items()
    )
    arguments["balance"] = case_fields["balance"]
    ordered = [
        "database_key", "balance", "composition_text", "units", "matrix_phase",
        "precipitate_phase", "schedule_mode", "temperature_c", "duration_h",
        "profile_text", "gamma", "matrix_vm", "precip_vm", "nucleation_type", "bulk_n0",
        "grain_size_um", "dislocation_density", "gb_energy", "cmin_nm", "cmax_nm", "bins",
        "input_provenance", "input_confirmation",
    ]
    arguments = {name: arguments[name] for name in ordered}
    sources = {
        "CASES['fe']": f"tools/test_backend_calculations.py:{case_line}",
        "run_precipitation в test_kwn_module": f"tools/test_backend_calculations.py:{call_line}",
    }
    return {"arguments": arguments, "sources": sources}


def section_default_cell(database_key: str) -> dict[str, Any]:
    """22-Б: умолчания раздела «Выделения» на составе боковой панели базы."""

    sidebar, sidebar_line = _sidebar_fe_composition(_tree(APP_SCRIPT), database_key)
    precipitation = _tree(PRECIPITATION)
    defaults, defaults_line = _module_constant(precipitation, "DEFAULTS")
    provenance, provenance_line = _module_constant(precipitation, "DEFAULT_INPUT_PROVENANCE")
    nucleation_types, nucleation_line = _module_constant(precipitation, "NUCLEATION_TYPES")
    matrix, precipitate, temperature, duration, gamma, matrix_vm, precip_vm = defaults[database_key]
    widgets = {
        name: _widget_default(precipitation, suffix)
        for name, suffix in (
            ("bulk_n0", "_bulk_n0"),
            ("grain_size_um", "_grain_size_um"),
            ("dislocation_density", "_dislocation_density"),
            ("gb_energy", "_gb_energy"),
            ("cmin_nm", "_cmin_nm"),
            ("cmax_nm", "_cmax_nm"),
            ("bins", "_bins"),
        )
    }
    arguments = dict(
        database_key=database_key,
        balance=sidebar["default_balance"],
        composition_text=sidebar["default_composition"],
        units=sidebar["default_units"],
        matrix_phase=matrix,
        precipitate_phase=precipitate,
        schedule_mode="isothermal",
        temperature_c=float(temperature),
        duration_h=float(duration),
        profile_text="",
        gamma=float(gamma),
        matrix_vm=float(matrix_vm),
        precip_vm=float(precip_vm),
        nucleation_type=next(iter(nucleation_types.values())),
        bulk_n0=float(widgets["bulk_n0"][0]),
        grain_size_um=float(widgets["grain_size_um"][0]),
        dislocation_density=float(widgets["dislocation_density"][0]),
        gb_energy=float(widgets["gb_energy"][0]),
        cmin_nm=float(widgets["cmin_nm"][0]),
        cmax_nm=float(widgets["cmax_nm"][0]),
        bins=int(widgets["bins"][0]),
        input_provenance=provenance,
        input_confirmation=True,
    )
    sources = {
        f"DATABASE_DEFINITIONS['{database_key}']": f"app/ThermoGar_app.py:{sidebar_line}",
        "DEFAULTS": f"app/thermogar_precipitation.py:{defaults_line}",
        "DEFAULT_INPUT_PROVENANCE": f"app/thermogar_precipitation.py:{provenance_line}",
        "NUCLEATION_TYPES": f"app/thermogar_precipitation.py:{nucleation_line}",
        **{f"виджет {name}": f"app/thermogar_precipitation.py:{line}" for name, (_v, line) in widgets.items()},
    }
    return {"arguments": arguments, "sources": sources}


def case_718_cell() -> dict[str, Any]:
    """22-Б: случай 15-В (718, 700 °C, 95 мДж/м²) — как в tools/test_precipitation_bl35.py."""

    import sys

    for entry in (ROOT / "app", ROOT / "tools"):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))
    import study_wave15_v_718 as study

    arguments = study.case_arguments(700.0, 95.0, study.GRID)
    arguments.pop("db")
    arguments["database_path"] = str(arguments["database_path"])
    test = _tree(ROOT / "tools" / "test_precipitation_bl35.py")
    line = next(
        node.lineno for node in ast.walk(test)
        if isinstance(node, ast.FunctionDef) and node.name == "test_718_run_ends_with_quality_error_not_exception"
    )
    return {
        "arguments": arguments,
        "sources": {
            "случай": f"tools/test_precipitation_bl35.py:{line}",
            "case_arguments(700.0, 95.0, GRID)": "tools/study_wave15_v_718.py",
        },
    }


CELLS = {
    "app": app_cell,
    "backend": backend_cell,
    "umolch_ni": lambda: section_default_cell("ni"),
    "umolch_al": lambda: section_default_cell("al"),
    "umolch_fe": lambda: section_default_cell("fe"),
    "718": case_718_cell,
}


if __name__ == "__main__":
    print(json.dumps({name: build() for name, build in CELLS.items()}, ensure_ascii=False, indent=2))
