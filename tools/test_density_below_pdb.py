"""Плотность ниже нижней границы физической базы (18-Б, BL-49).

Все DP-параметры ``physical_data_v103.pdb`` действуют с 298,15 K. Раньше
вкладки «Плотность» и «Плотность по T» при 20 °C отказывали
``BACKEND_FAILED: ValueError: Температура 293.15 K вне диапазона
DP-параметра …``. Теперь — текстом, утверждённым владельцем (вариант 1), и
счёт не запускается. Граница берётся из самой базы.

Проверяется:

* граница базы — минимум нижних границ DP-параметров;
* «Плотность» при 20 °C: текст отказа, кнопка неактивна, результата нет;
  при 25 °C — плотность посчитана, отказа нет;
* «Плотность по T» от 20 °C: тот же текст, счёт не запущен; от 25 °C —
  две точки посчитаны.

Запуск:

    python -m pytest tools/test_density_below_pdb.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import pytest  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "app" / "ThermoGar_app.py"
PDB_PATH = (
    PROJECT_ROOT / "databases" / "physical" / "original" / "physical_data_v103.pdb"
)
if str(PROJECT_ROOT / "app") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "app"))

import thermogar_physical as physical  # noqa: E402

OWNER_TEXT = "Физическая база задаёт плотность с 25 °C; введите 25 °C или выше."
SINGLE_STATE = "_thermogar_vlb_b4b_result_property_density_single"
SCAN_STATE = "_thermogar_vlb_b4b_result_property_density_temperature"


@pytest.fixture(autouse=True)
def _private_state_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("THERMOGAR_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.delenv(physical.PHYSICAL_OVERRIDES_ENV, raising=False)


def _start(extra: dict[str, Any]):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP_PATH), default_timeout=1800)
    state = {
        "thermogar_database_key": "ni",
        "thermogar_composition_ni": "CR=20",
        "thermogar_units_ni": "массовые %",
        "thermogar_balance_ni": "NI",
        "physical_temperature_ni": 700.0,
        "physical_t_min_ni": 600.0,
        "physical_t_max_ni": 700.0,
        "physical_t_step_ni": 100.0,
    }
    state.update(extra)
    for name, value in state.items():
        at.session_state[name] = value
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _errors(at) -> list[str]:
    return [element.value for element in at.error]


def test_lower_bound_is_minimum_of_dp_parameters() -> None:
    database = physical.PhysicalDensityDatabase(PDB_PATH)
    expected = min(parameter.lower_temperature for parameter in database.parameters)
    assert database.density_lower_temperature_k == expected
    # v103: все DP-параметры с 298,15 K — отсюда 25 °C в тексте владельца.
    assert expected == 298.15


def test_single_density_at_20c_is_refused_with_owner_text() -> None:
    at = _start({"physical_temperature_ni": 20.0})
    assert _errors(at) == [OWNER_TEXT]
    button = at.button(key="physical_single_calculate")
    assert button.disabled
    assert SINGLE_STATE not in at.session_state
    shown = " ".join(_errors(at) + [element.value for element in at.warning])
    assert "BACKEND_FAILED" not in shown
    assert "ValueError" not in shown


def test_single_density_at_25c_is_calculated() -> None:
    at = _start({"physical_temperature_ni": 25.0})
    assert OWNER_TEXT not in _errors(at)
    at.button(key="physical_single_calculate").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not at.error, _errors(at)
    projection = at.session_state[SINGLE_STATE]["projections"][0]
    assert projection["alloy_density_kg_m3"] is not None
    assert projection["alloy_density_kg_m3"] > 0.0


def test_density_scan_from_20c_is_refused_and_not_started() -> None:
    at = _start({"physical_t_min_ni": 20.0, "physical_t_max_ni": 120.0})
    assert OWNER_TEXT in _errors(at)
    assert at.button(key="physical_scan_calculate").disabled
    assert SCAN_STATE not in at.session_state


def test_density_scan_from_25c_is_calculated() -> None:
    at = _start({"physical_t_min_ni": 25.0, "physical_t_max_ni": 125.0})
    assert OWNER_TEXT not in _errors(at)
    at.button(key="physical_scan_calculate").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not at.error, _errors(at)
    projections = at.session_state[SCAN_STATE]["projections"]
    assert [p["temperature_k"] for p in projections] == pytest.approx([298.15, 398.15])
    assert all(p["alloy_density_kg_m3"] > 0.0 for p in projections)
