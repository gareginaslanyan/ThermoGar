"""21-Щ: BL-77 — «Загружено: …» не переживает ручную смену полей.

* Чистая функция ``loaded_context_is_current``: запись о загрузке текущая,
  если каждое записанное значение равно значению того же ключа в состоянии
  сеанса; расхождение по любому полю — не текущая; режим стали сравнивается
  только у стальной базы; запись без словаря значений (сеанс до правки) —
  текущая, как раньше.
* ``apply_pending_state`` записывает в ``_thermogar_loaded_context`` значения
  основы, единиц, добавок, давления и режима стали.
* AppTest (Windows): запись Ni из «Марок и составов» — «Загружено: …» есть и
  после повторного прогона без изменений; после правки «Добавок» надписи нет.
  То же для стали со сменой режима стали.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -B -m pytest tools/test_wave21_shch.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
TOOLS = ROOT / "tools"
for path in (APP, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import thermogar_workspace as workspace  # noqa: E402

# Приложение гоняется той же фикстурой, что и в test_ui_h.
from test_ui_h import (  # noqa: E402,F401
    app,
    labelled,
    patched_app_source,
    section_errors,
    widget,
)

STEEL_PRACTICAL = "Практический Fe–Fe₃C — цементит, без графита"
STEEL_STABLE = "Стабильный Fe–C — графит разрешён"
NI_VALUES = {
    "thermogar_balance_ni": "NI",
    "thermogar_units_ni": "атомные %",
    "thermogar_composition_ni": "AL=15",
    "thermogar_pressure_pa": 101325.0,
    "thermogar_steel_mode": STEEL_STABLE,
}
FE_VALUES = {
    "thermogar_balance_fe": "FE",
    "thermogar_units_fe": "массовые %",
    "thermogar_composition_fe": "C=0.2, Cr=11.5, Ni=0.7",
    "thermogar_pressure_pa": 101325.0,
    "thermogar_steel_mode": STEEL_PRACTICAL,
}


def _record(database_key: str, values: dict[str, Any] | None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "label": "Запись",
        "database_key": database_key,
        "database_sha256": "",
        "fe_profile_key": None,
    }
    if values is not None:
        record["values"] = dict(values)
    return record


def _is_current(record: dict[str, Any], state: dict[str, Any]) -> bool:
    return workspace.loaded_context_is_current(record, state)


# --------------------------------------------------------------------------- #
# Чистая функция
# --------------------------------------------------------------------------- #


def test_same_values_are_current() -> None:
    assert _is_current(_record("ni", NI_VALUES), dict(NI_VALUES))
    assert _is_current(_record("fe", FE_VALUES), dict(FE_VALUES))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("thermogar_balance_ni", "AL"),
        ("thermogar_units_ni", "массовые %"),
        ("thermogar_composition_ni", "Al=16"),
        ("thermogar_pressure_pa", 200000.0),
    ],
)
def test_any_changed_field_is_not_current(key: str, value: Any) -> None:
    state = dict(NI_VALUES)
    state[key] = value
    assert not _is_current(_record("ni", NI_VALUES), state)


@pytest.mark.parametrize("key", sorted(FE_VALUES))
def test_any_changed_steel_field_is_not_current(key: str) -> None:
    state = dict(FE_VALUES)
    state[key] = STEEL_STABLE if key == "thermogar_steel_mode" else "другое"
    assert not _is_current(_record("fe", FE_VALUES), state)


def test_missing_key_is_not_current() -> None:
    state = dict(NI_VALUES)
    del state["thermogar_composition_ni"]
    assert not _is_current(_record("ni", NI_VALUES), state)


def test_steel_mode_is_not_compared_for_ni() -> None:
    state = dict(NI_VALUES)
    # У Ni виджета режима стали нет, и Streamlit стирает его ключ.
    del state["thermogar_steel_mode"]
    assert _is_current(_record("ni", NI_VALUES), state)
    state["thermogar_steel_mode"] = STEEL_PRACTICAL
    assert _is_current(_record("ni", NI_VALUES), state)


def test_record_without_values_is_current() -> None:
    assert _is_current(_record("ni", None), {})
    assert _is_current(_record("ni", None), {"thermogar_composition_ni": "Al=16"})


def test_apply_pending_state_records_values(monkeypatch: pytest.MonkeyPatch) -> None:
    state: dict[str, Any] = {}
    monkeypatch.setattr(workspace.st, "session_state", state)
    context = {
        "database_key": "ni",
        "balance": "NI",
        "units": "at",
        "composition": "AL=15",
        "pressure_pa": 101325.0,
        "steel_mode": "stable",
    }
    monkeypatch.setattr(workspace, "validate_context_payload", lambda value: value)
    state["_thermogar_pending_context"] = context
    state["_thermogar_pending_context_label"] = "Ni–15Al"

    workspace.apply_pending_state()

    record = state["_thermogar_loaded_context"]
    assert record["values"] == NI_VALUES
    assert _is_current(record, state)


# --------------------------------------------------------------------------- #
# AppTest: боковая панель после загрузки
# --------------------------------------------------------------------------- #


def _loaded_labels(at) -> list[str]:
    return [
        element.value
        for element in [*at.sidebar.success, *at.sidebar.warning]
        if element.value.startswith(("Загружено: ", "Открыт "))
    ]


def _load(at, record_id: str) -> None:
    widget(at.selectbox, "alloy_selected_id").set_value(record_id)
    at.run()
    widget(at.button, "alloy_load_button").click()
    at.run()
    assert not at.exception, at.exception
    assert not section_errors(at)


def test_ni_label_survives_rerun_and_goes_after_composition_edit(app) -> None:
    at, _state_root = app()
    at.sidebar.selectbox("thermogar_database_key").set_value("ni")
    at.run()
    _load(at, "demo-ni-15al")
    assert _loaded_labels(at) == ["Загружено: Пример Ni–15Al"]

    at.run()
    assert _loaded_labels(at) == ["Загружено: Пример Ni–15Al"]

    at.sidebar.text_area(key="thermogar_composition_ni").set_value("Al=16")
    at.run()
    assert _loaded_labels(at) == []
    assert "_thermogar_loaded_context" not in at.session_state
    at.run()
    assert _loaded_labels(at) == []


def test_fe_label_goes_after_steel_mode_change(app) -> None:
    at, state_root = app()
    at.sidebar.selectbox("thermogar_database_key").set_value("fe")
    at.run()
    at.session_state["thermogar_composition_fe"] = "C=0.2, Cr=11.5, Ni=0.7"
    at.run()
    labelled(at.text_input, "Название марки или состава").set_value("Сталь 21-Щ")
    labelled(at.button, "Сохранить текущий состав").click()
    at.run()
    assert not section_errors(at)
    saved = json.loads(
        (state_root / "workspace" / "alloys.json").read_text(encoding="utf-8")
    )["alloys"]
    assert [item["name"] for item in saved] == ["Сталь 21-Щ"]

    # Уйти на Ni и загрузить запись стали обратно.
    at.sidebar.selectbox("thermogar_database_key").set_value("ni")
    at.run()
    _load(at, saved[0]["id"])
    assert at.session_state["thermogar_database_key"] == "fe"
    assert _loaded_labels(at) == ["Загружено: Сталь 21-Щ"]

    at.run()
    assert _loaded_labels(at) == ["Загружено: Сталь 21-Щ"]

    at.sidebar.radio(key="thermogar_steel_mode").set_value(STEEL_STABLE)
    at.run()
    assert _loaded_labels(at) == []
    assert "_thermogar_loaded_context" not in at.session_state
