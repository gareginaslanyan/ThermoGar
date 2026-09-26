"""Решение владельца 26.09.2026 по пустым ячейкам (BL-68) и недочёты BL-70–BL-72 (21-У).

* BL-68, вариант Б: пустая ячейка таблицы на экране — прочерк «—» (U+2014);
  постоянная ``EMPTY_CELL_TEXT`` и параметр ``placeholder`` у каждого из 64
  вызовов ``st.dataframe`` / ``st.data_editor`` в ``app/*.py``; данные таблиц
  не меняются (T₀ стали по умолчанию: в строках C 1.8–2.0 мас.% — NaN);
* BL-70: VRH считается, если «Примечание» стёрто (None) или в
  «Происхождении» и «Источнике» есть пробел в конце;
* BL-71: пустая ячейка столбца элемента при пустых «Добавках» — элемента нет
  в составе, строка пакета посчитана;
* BL-72: пустые поля поправки в паспорте базы стали — пустые ячейки (None),
  а не слово «None».

Запуск:

    python -m pytest tools/test_wave21_u.py
"""

from __future__ import annotations

import ast
import math
import sys
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
TOOLS = ROOT / "tools"
for path in (APP, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import streamlit as st  # noqa: E402

from thermogar_user_errors import EMPTY_CELL_TEXT  # noqa: E402

KNOWN_FOREIGN_ERRORS = ("BINDING_STALE",)
# Опись 21-С (results/wave21_s/tablicy.csv): 64 вызова, по файлам.
TABLE_CALLS = {
    "ThermoGar_app.py": 37,
    "thermogar_workspace.py": 7,
    "thermogar_precipitation.py": 6,
    "thermogar_diffusion.py": 5,
    "thermogar_stage14.py": 5,
    "thermogar_properties.py": 4,
}
ELASTIC_PREPARE_STATE = "_thermogar_vlb_b4b_result_property_elastic_prepare"
ELASTIC_VRH_STATE = "_thermogar_vlb_b4b_result_property_elastic_vrh"
ELASTIC_NI20CR = {
    "thermogar_database_key": "ni",
    "thermogar_composition_ni": "CR=20",
    "thermogar_units_ni": "массовые %",
    "thermogar_balance_ni": "NI",
    "b4b2_elastic_temperature_ni": 700.0,
}
ELASTIC_ROW_VALUES = {
    "young_gpa": 200.0,
    "poisson": 0.3,
    "origin": "measured",
    "source": "условное значение для проверки BL-70",
    "reference_temperature_c": 25.0,
    "note": "",
}


@pytest.fixture(autouse=True)
def _private_state_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("THERMOGAR_STATE_ROOT", str(tmp_path / "state"))


@pytest.fixture(autouse=True)
def _bounded_memory(monkeypatch) -> Iterator[None]:
    """Два воркера на тест, как в test_ui_f; после теста пул закрыт."""

    import gc

    import matplotlib.pyplot as plt
    import thermogar_parallel_ui

    monkeypatch.setattr(thermogar_parallel_ui, "_WORKER_COUNT", 2)
    yield
    thermogar_parallel_ui.close_shared_engines()
    plt.close("all")
    gc.collect()


def _start(state: dict[str, Any]):
    from streamlit.testing.v1 import AppTest

    app_test = AppTest.from_file(str(APP / "ThermoGar_app.py"), default_timeout=1800)
    for key, value in state.items():
        app_test.session_state[key] = value
    app_test.run()
    _assert_clean(app_test)
    return app_test


def _assert_clean(app_test) -> None:
    assert not app_test.exception, [str(e.value) for e in app_test.exception]
    errors = [
        e.value for e in app_test.error
        if not any(known in e.value for known in KNOWN_FOREIGN_ERRORS)
    ]
    assert not errors, errors


def _frames_with(app_test, column: str) -> list[Any]:
    return [
        frame for frame in app_test.dataframe
        if column in getattr(frame.value, "columns", [])
    ]


# --------------------------------------------------------------------------- #
# BL-68: постоянная и 64 вызова
# --------------------------------------------------------------------------- #


def test_empty_cell_text_is_em_dash() -> None:
    assert EMPTY_CELL_TEXT == "—"


def _table_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in ("dataframe", "data_editor")
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "st"
    ]


def test_every_table_call_has_the_placeholder() -> None:
    found: dict[str, int] = {}
    missing: list[str] = []
    for path in sorted(APP.glob("*.py")):
        calls = _table_calls(ast.parse(path.read_text(encoding="utf-8")))
        if not calls:
            continue
        found[path.name] = len(calls)
        for call in calls:
            values = [k.value for k in call.keywords if k.arg == "placeholder"]
            if not (
                len(values) == 1
                and isinstance(values[0], ast.Name)
                and values[0].id == "EMPTY_CELL_TEXT"
            ):
                missing.append(f"{path.name}:{call.lineno}")
    assert found == TABLE_CALLS
    assert sum(found.values()) == 64
    assert not missing, missing


def test_tzero_steel_table_shows_dash_and_keeps_nan() -> None:
    """T₀ стали по умолчанию: прочерк в показе, NaN в данных (C 1.8–2.0)."""

    app_test = _start({"thermogar_database_key": "fe"})
    app_test.button(key="tzero_calculate").click().run()
    _assert_clean(app_test)

    data = app_test.session_state["tzero_result"]["data"]
    tables = _frames_with(app_test, "T₀, °C")
    assert len(tables) == 1, len(tables)
    table = tables[0]
    assert table.proto.placeholder == EMPTY_CELL_TEXT
    shown = table.value
    assert len(shown) == len(data) == 21
    empty = shown[shown["C, мас.%"].round(6).isin([1.8, 1.9, 2.0])]
    assert len(empty) == 3
    for column in ("T₀, °C", "T₀, K"):
        assert all(math.isnan(value) for value in empty[column]), column
        assert pd.api.types.is_numeric_dtype(shown[column]), column
    assert data["T₀, °C"].isna().sum() == 3


def test_elastic_editor_placeholder() -> None:
    """«Упругие свойства», шаг 2: у редактора таблицы фаз — прочерк."""

    app_test = _start(ELASTIC_NI20CR)
    app_test.button(key="b4b2_elastic_prepare_calculate").click().run()
    _assert_clean(app_test)
    assert ELASTIC_PREPARE_STATE in app_test.session_state
    editors = _frames_with(app_test, "young_gpa")
    assert len(editors) == 1, len(editors)
    assert editors[0].proto.placeholder == EMPTY_CELL_TEXT


# --------------------------------------------------------------------------- #
# BL-70: VRH при стёртом «Примечании» и пробелах по краям
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "values",
    [
        {"note": None},
        {
            "origin": "measured ",
            "source": "условное значение для проверки BL-70 ",
        },
    ],
    ids=["note-none", "trailing-space"],
)
def test_elastic_vrh_accepts_editor_text(monkeypatch, values) -> None:
    original_editor = st.data_editor

    def filled_editor(frame, *args, **kwargs):
        original_editor(frame, *args, **kwargs)
        edited = frame.copy()
        for column, value in {**ELASTIC_ROW_VALUES, **values}.items():
            edited[column] = pd.Series([value] * len(edited), index=edited.index, dtype=object)
        return edited

    monkeypatch.setattr(st, "data_editor", filled_editor)
    app_test = _start(ELASTIC_NI20CR)
    app_test.button(key="b4b2_elastic_prepare_calculate").click().run()
    _assert_clean(app_test)
    button = app_test.button(key="b4b2_elastic_vrh_calculate")
    assert button.proto.disabled is False
    button.click().run()
    _assert_clean(app_test)
    rows = app_test.session_state[ELASTIC_VRH_STATE]["projection"]["phase_rows"]
    assert [row["phase"] for row in rows] == ["FCC_A1"]
    assert app_test.session_state[ELASTIC_VRH_STATE]["projection"]["summary"]["E_Hill_GPa"] == pytest.approx(200.0)


# --------------------------------------------------------------------------- #
# BL-71: пустая ячейка элемента в пакете
# --------------------------------------------------------------------------- #


def test_batch_empty_element_cell_is_no_addition() -> None:
    from streamlit.testing.v1 import AppTest

    payload = (
        'Название,База,Основа,Единицы,"Температура, °C",Добавки,AL,CR\n'
        "NI-AL-CR,ni,NI,ат.%,700,,15,5\n"
        "NI-AL,ni,NI,ат.%,700,,15,\n"
    ).encode("utf-8")
    app_test = AppTest.from_file(str(APP / "ThermoGar_app.py"), default_timeout=1800)
    app_test.run()
    _assert_clean(app_test)
    uploader = next(
        item for item in app_test.get("file_uploader")
        if item.proto.label == "Файл составов"
    )
    uploader.set_value(("batch.csv", payload, "text/csv"))
    app_test.run()
    app_test.button(key="batch_calculate_button").click().run()
    assert not app_test.exception, [str(e.value) for e in app_test.exception]

    summary = app_test.session_state["workspace_batch_result"]["display"]["Сводка"]
    by_name = {row["Название"]: row for _index, row in summary.iterrows()}
    assert list(summary["Статус"]) == ["готово", "готово"], list(summary.get("Ошибка", []))
    assert "CR=5" in str(by_name["NI-AL-CR"]["Состав"]).upper()
    assert "AL=15" in str(by_name["NI-AL"]["Состав"]).upper()
    assert "CR" not in str(by_name["NI-AL"]["Состав"]).upper()


# --------------------------------------------------------------------------- #
# BL-72: пустые поля поправки в паспорте базы стали
# --------------------------------------------------------------------------- #


def test_passport_empty_patch_fields_are_empty_cells(monkeypatch) -> None:
    import thermogar_database_guard as guard

    real = guard.compatibility_patch_record(ROOT)
    assert real is not None
    blank = {**real, "status": None, "action": None, "matched_active_commands": None}
    monkeypatch.setattr(guard, "compatibility_patch_record", lambda *_args, **_kw: blank)

    table = guard.passport_dataframe(ROOT, guard.FE_PROFILE_CANONICAL)
    values = dict(zip(table["Поле"], table["Значение"]))
    # pandas 3: столбец строк хранит пустое значение как NaN — ячейка пустая.
    for field in ("Статус поправки", "Действие", "Совпавших активных команд"):
        assert pd.isna(values[field]), (field, values[field])
    assert "None" not in list(table["Значение"])
