#!/usr/bin/env python3
"""BL-63: a wrong "Добавки" line in the sidebar does not crash the page.

``context_snapshot`` validates the sidebar context with
``thermogar_workspace.validate_context_payload``, which raises ``ValueError``
with a plain Russian message. Before wave 21-Д the exception left the script
unhandled: Streamlit printed a Traceback with file paths and the tabs were
gone (``results/wave21_b/kadry/36_*``). Now the message is shown with
``st.error`` in the main area and the script stops before the tabs.

Every message the validator can raise for the "Добавки" line has one wrong
input below. After the wrong inputs a valid line brings the tabs back.

Run:
    <root>/.venv-windows/Scripts/python.exe -B -m pytest tools/test_sidebar_composition_error.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from streamlit.testing.v1 import AppTest

APP_SCRIPT = str(ROOT / "app" / "ThermoGar_app.py")

# The Fe database is the default one; its balance is FE.
DATABASE_KEY = "fe"
COMPOSITION_KEY = f"thermogar_composition_{DATABASE_KEY}"
VALID_COMPOSITION = "C=0.20, CR=11.5, NI=0.7"

# Wrong line -> message of app/thermogar_workspace.py validate_context_payload.
WRONG_INPUTS = [
    # :517, no "element=value" pair at all
    ("AL15", "Состав имеет неверный формат; пример: Al=15, Cr=10."),
    # :517, a pair plus text that is not a pair
    ("CR=10, что-то", "Состав имеет неверный формат; пример: Al=15, Cr=10."),
    # :522
    ("CR=5, CR=3", "Элемент Cr указан более одного раза."),
    # :524-526, ZN is not in the Fe database
    ("ZN=1", "Элемента Zn нет в базе «Стали и Fe-сплавы — mc_fe 2.062»."),
    # :528-530
    ("FE=5", "Fe выбран как основа и не должен повторяться в добавках."),
    # :532-533, zero
    ("CR=0", "Содержание Cr должно быть больше нуля."),
    # :532-533, negative
    ("CR=-5", "Содержание Cr должно быть больше нуля."),
    # :535-536
    ("CR=60, NI=50", "Сумма добавок должна быть меньше 100 %."),
]

MAIN_TABS = (
    "Расчёты",
    "Диаграммы",
    "Затвердевание",
    "Энергии",
    "Свойства",
    "Кинетика",
    "Проекты и данные",
)


def tab_labels(at: AppTest) -> set[str]:
    return {tab.label for tab in at.tabs}


@pytest.fixture(scope="module")
def app(tmp_path_factory) -> AppTest:
    state_root = tmp_path_factory.mktemp("state")
    patch = pytest.MonkeyPatch()
    patch.setenv("THERMOGAR_STATE_ROOT", str(state_root))
    instance = AppTest.from_file(APP_SCRIPT, default_timeout=900)
    instance.session_state["thermogar_database_key"] = DATABASE_KEY
    instance.run()
    assert not instance.exception, instance.exception
    assert set(MAIN_TABS) <= tab_labels(instance)
    yield instance
    patch.undo()


@pytest.mark.parametrize(
    ("composition", "message"),
    WRONG_INPUTS,
    ids=[composition for composition, _message in WRONG_INPUTS],
)
def test_wrong_additions_show_the_message_and_no_tabs(app, composition, message):
    app.sidebar.text_area(COMPOSITION_KEY).set_value(composition)
    app.run()

    assert not app.exception, [item.value for item in app.exception]
    errors = [error.value for error in app.main.error]
    assert message in errors, errors
    assert not app.tabs, sorted(tab_labels(app))


def test_valid_additions_bring_the_tabs_back(app):
    app.sidebar.text_area(COMPOSITION_KEY).set_value("AL15")
    app.run()
    assert not app.tabs

    app.sidebar.text_area(COMPOSITION_KEY).set_value(VALID_COMPOSITION)
    app.run()

    assert not app.exception, [item.value for item in app.exception]
    assert set(MAIN_TABS) <= tab_labels(app)
    errors = [error.value for error in app.main.error]
    for _composition, message in WRONG_INPUTS:
        assert message not in errors, errors
