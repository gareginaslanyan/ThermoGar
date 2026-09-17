"""Галочка поправок проекта к физической базе (15-У, BL-14).

Проверяется поведение, а не факт запуска:

* метка ``OVERRIDES_OFF_BY_USER`` считает ровно как ``overrides=None`` и
  называет неприменённые правки; при ``THERMOGAR_PHYSICAL_OVERRIDES=off``
  выключать нечего, и отметки нет;
* в разделе «Свойства» галочка есть и по умолчанию включена;
* снятая галочка меняет плотность Ni-20Cr при 700 °C (без поправки хрома она
  ниже) и первую строку предупреждений результата — ту самую, где названа
  применённая поправка; показанный результат при переключении сбрасывается;
* при переменной окружения «off» галочка неактивна и пояснена;
* (15-Ч, BL-40) подготовка упругих свойств Ni-20Cr-0,3C не падает на паре
  BCC_B2/BCC_A2: фаза снята тем же детектором, что у плотности, и названа
  в предупреждениях сразу после отметки поправок;
* (15-Ф, BL-38) веса VRH во вкладке «Упругие свойства» — объёмные доли фаз
  из той же физической базы: у одной фазы φ = 1 при любой галочке; у
  Fe-15Cr-0,4C (FCC_A1 + M23C6) φ/x отличаются ровно в отношении молярных
  объёмов, и снятая галочка меняет φ; у состава без хрома — не меняет.

Запуск:

    python -m pytest tools/test_physical_overrides_toggle.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "app" / "ThermoGar_app.py"
PDB_PATH = (
    PROJECT_ROOT / "databases" / "physical" / "original" / "physical_data_v103.pdb"
)
if str(PROJECT_ROOT / "app") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "app"))

import thermogar_physical as physical  # noqa: E402

TOGGLE_KEY = "physical_overrides_enabled"
SINGLE_STATE = "_thermogar_vlb_b4b_result_property_density_single"
SCAN_STATE = "_thermogar_vlb_b4b_result_property_density_temperature"
USER_OFF_PREFIX = "Поправки проекта ThermoGar к физической базе выключены пользователем"
CR_OVERRIDE_PREFIX = "Плотность хрома посчитана по поправке проекта ThermoGar"


@pytest.fixture(autouse=True)
def _private_state_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("THERMOGAR_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.delenv(physical.PHYSICAL_OVERRIDES_ENV, raising=False)
    yield
    if physical.PHYSICAL_OVERRIDES_ENV in os.environ:
        # Разбор PDB без поправок не должен достаться следующим тестам.
        import thermogar_verified_loaders as verified_loaders

        verified_loaders.invalidate_binding_generation()


# ---------------------------------------------------------------------------
# Модуль физической базы
# ---------------------------------------------------------------------------


def test_user_switch_matches_plain_database_and_names_the_override() -> None:
    plain = physical.PhysicalDensityDatabase(PDB_PATH, overrides=None)
    user_off = physical.PhysicalDensityDatabase(
        PDB_PATH, overrides=physical.OVERRIDES_OFF_BY_USER
    )
    corrected = physical.PhysicalDensityDatabase(PDB_PATH)

    assert corrected.applied_overrides, "поправка по хрому должна быть включена"
    assert user_off.functions == plain.functions
    assert user_off.functions != corrected.functions
    assert not user_off.applied_overrides
    assert [entry.name for entry in user_off.suppressed_overrides] == ["DTCRBCC"]

    notes = user_off.override_notes
    assert len(notes) == 1
    assert notes[0].startswith(USER_OFF_PREFIX)
    assert "DTCRBCC" in notes[0]
    assert plain.override_notes == []

    # Хром без поправки при 700 °C легче: наклон ρ(T) базы завышен.
    t = 973.15
    assert user_off.function_value("DTCRBCC", t) < corrected.function_value(
        "DTCRBCC", t
    )


def test_environment_off_leaves_nothing_to_suppress(monkeypatch) -> None:
    monkeypatch.setenv(physical.PHYSICAL_OVERRIDES_ENV, "off")
    user_off = physical.PhysicalDensityDatabase(
        PDB_PATH, overrides=physical.OVERRIDES_OFF_BY_USER
    )
    assert user_off.suppressed_overrides == ()
    assert user_off.override_notes == []


# ---------------------------------------------------------------------------
# Интерфейс
# ---------------------------------------------------------------------------


def _start(extra: dict[str, Any] | None = None):
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
    state.update(extra or {})
    for name, value in state.items():
        at.session_state[name] = value
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def _toggle(at, key: str = TOGGLE_KEY):
    return at.checkbox(key=key)


def _assert_clean(at) -> None:
    assert not at.exception, [str(e.value) for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def test_toggle_is_present_and_on_by_default() -> None:
    at = _start()
    toggle = _toggle(at)
    assert toggle.value is True
    assert not toggle.disabled
    assert "поправки проекта ThermoGar" in toggle.label
    assert toggle.help and "DTCRBCC" in toggle.help


def test_switching_off_changes_density_and_result_note() -> None:
    at = _start()
    at.button(key="physical_single_calculate").click().run()
    _assert_clean(at)
    on_state = at.session_state[SINGLE_STATE]
    on = on_state["projections"][0]
    assert on_state["physical_overrides"] is True
    assert on["warnings"][0].startswith(CR_OVERRIDE_PREFIX)
    assert not any(USER_OFF_PREFIX in text for text in on["warnings"])

    _toggle(at).uncheck().run()
    _assert_clean(at)
    # Результат, посчитанный с поправкой, при снятой галочке не показывается.
    assert SINGLE_STATE not in at.session_state

    at.button(key="physical_single_calculate").click().run()
    _assert_clean(at)
    off_state = at.session_state[SINGLE_STATE]
    off = off_state["projections"][0]
    assert off_state["physical_overrides"] is False
    assert off["warnings"][0].startswith(USER_OFF_PREFIX)
    assert not any(CR_OVERRIDE_PREFIX in text for text in off["warnings"])
    assert off["warnings"][1:] == on["warnings"][1:]
    shown = [element.value for element in at.warning]
    assert any(text.startswith(USER_OFF_PREFIX) for text in shown), shown

    # Ni-20Cr масс. %, 700 °C: без поправки хрома плотность ниже на 0,78 %
    # (docs/DATABASES.md, раздел 8: «примерно на 1 % при 700 °C»).
    ratio = off["alloy_density_kg_m3"] / on["alloy_density_kg_m3"] - 1.0
    assert ratio == pytest.approx(-0.0078, abs=0.0005), ratio
    # Покрытие и прочее от поправки не зависят.
    assert off["mass_coverage_pct"] == on["mass_coverage_pct"]
    assert off["quality_label"] == on["quality_label"]


def test_switching_off_changes_density_scan() -> None:
    at = _start({TOGGLE_KEY: False})
    at.button(key="physical_scan_calculate").click().run()
    _assert_clean(at)
    off_state = at.session_state[SCAN_STATE]
    assert off_state["physical_overrides"] is False
    off = off_state["projections"]
    assert len(off) == 2
    assert all(p["warnings"][0].startswith(USER_OFF_PREFIX) for p in off)

    _toggle(at).check().run()
    assert SCAN_STATE not in at.session_state
    at.button(key="physical_scan_calculate").click().run()
    _assert_clean(at)
    on = at.session_state[SCAN_STATE]["projections"]
    assert all(p["warnings"][0].startswith(CR_OVERRIDE_PREFIX) for p in on)
    for p_on, p_off in zip(on, off):
        assert p_off["alloy_density_kg_m3"] < p_on["alloy_density_kg_m3"]
    # Разница растёт с температурой: виноват наклон ρ(T) хрома.
    drops = [
        p_on["alloy_density_kg_m3"] - p_off["alloy_density_kg_m3"]
        for p_on, p_off in zip(on, off)
    ]
    assert drops[1] > drops[0]


def test_environment_off_locks_the_toggle(monkeypatch) -> None:
    import thermogar_verified_loaders as verified_loaders

    monkeypatch.setenv(physical.PHYSICAL_OVERRIDES_ENV, "off")
    # Переменная читается при разборе PDB, а разбор кэшируется лизой на весь
    # процесс. В приложении переменная задаётся при запуске; здесь соседние
    # тесты того же процесса уже разобрали базу с поправкой — сбросить.
    verified_loaders.invalidate_binding_generation()
    at = _start()
    toggle = _toggle(at, f"{TOGGLE_KEY}_env_locked")
    assert toggle.disabled
    assert toggle.value is False
    assert TOGGLE_KEY not in [w.key for w in at.checkbox]
    captions = " ".join(element.value for element in at.caption)
    assert physical.PHYSICAL_OVERRIDES_ENV in captions
    assert "сильнее галочки" in captions

    at.button(key="physical_single_calculate").click().run()
    _assert_clean(at)
    projection = at.session_state[SINGLE_STATE]["projections"][0]
    # Выключила переменная окружения, а не пользователь галочкой: отметки
    # «выключены пользователем» нет, как нет и текста поправки.
    assert not any(USER_OFF_PREFIX in text for text in projection["warnings"])
    assert not any(CR_OVERRIDE_PREFIX in text for text in projection["warnings"])


# ---------------------------------------------------------------------------
# 15-У2: тексты и подпись столбца долей во вкладке «Упругие свойства»
# ---------------------------------------------------------------------------

APPROVED_RANGE = "до 1 % при 700 °C и до 2 % при 1300 °C"


def test_texts_name_the_approved_range() -> None:
    at = _start()
    help_text = _toggle(at).help
    assert APPROVED_RANGE in help_text
    assert "около 1 %" not in help_text
    assert (
        "Действует на вкладки «Плотность», «Плотность по T» и «Упругие "
        "свойства» (через объёмные доли фаз)." in help_text
    )
    assert "от поправок не зависят" not in help_text
    assert APPROVED_RANGE in physical.OVERRIDES_OFF_BY_USER_NOTE
    assert "около 1 %" not in physical.OVERRIDES_OFF_BY_USER_NOTE


# ---------------------------------------------------------------------------
# 15-Ф (BL-38): веса VRH — объёмные доли фаз из физической базы
# ---------------------------------------------------------------------------

PREPARE_STATE = "_thermogar_vlb_b4b_result_property_elastic_prepare"
VRH_STATE = "_thermogar_vlb_b4b_result_property_elastic_vrh"

# Условные модули для проверки весов, а не данные о фазах: при одинаковых
# модулях фаз веса на результат VRH не влияли бы.
ELASTIC_YOUNG_BY_ORDER = (100.0, 300.0)
ELASTIC_ROW_VALUES = {
    "poisson": 0.25,
    "origin": "measured",
    "source": "условное значение для проверки весов VRH",
    "reference_temperature_c": 25.0,
}

# Ni-20Cr масс. %, 700 °C — одна фаза FCC_A1.
NI20CR = {"key": "ni", "composition": "CR=20", "balance": "NI", "t_c": 700.0}
# Fe-15Cr-0,4C масс. %, 950 °C — FCC_A1 + M23C6, у обеих прямые DP-модели.
FE15CR04C = {"key": "fe", "composition": "CR=15, C=0.4", "balance": "FE", "t_c": 950.0}
# Fe-1C масс. %, 800 °C — FCC_A1 + GRAPHITE, хрома нет.
FE1C = {"key": "fe", "composition": "C=1", "balance": "FE", "t_c": 800.0}
# Ni-20Cr-0,3C масс. %, 700 °C — пара BCC_B2/BCC_A2 не строится (BL-40).
NI20CR03C = {"key": "ni", "composition": "CR=20, C=0.3", "balance": "NI", "t_c": 700.0}
EXCLUDED_PREFIX = "Из расчёта исключены фазы, модель которых не строится"


@pytest.fixture
def elastic_capture(monkeypatch):
    """Подменить редактор (AppTest не вводит значения) и собрать выгрузки."""

    import streamlit as st

    captured: dict[str, Any] = {"downloads": {}, "editor": []}
    original_button = st.download_button
    original_editor = st.data_editor

    def capture(label, data=None, *args, **kwargs):
        name = str(kwargs.get("file_name") or label)
        if isinstance(data, (bytes, bytearray)):
            captured["downloads"][name] = bytes(data)
        return original_button(label, data, *args, **kwargs)

    def filled_editor(frame, *args, **kwargs):
        captured["editor"].append(
            {
                "columns": list(frame.columns),
                "column_config": dict(kwargs.get("column_config") or {}),
                "disabled": list(kwargs.get("disabled") or []),
            }
        )
        original_editor(frame, *args, **kwargs)
        edited = frame.copy()
        edited["young_gpa"] = [
            ELASTIC_YOUNG_BY_ORDER[index % 2] for index in range(len(edited))
        ]
        for column, value in ELASTIC_ROW_VALUES.items():
            edited[column] = value
        return edited

    monkeypatch.setattr(st, "download_button", capture)
    monkeypatch.setattr(st, "data_editor", filled_editor)
    return captured


def _start_elastic(case: dict[str, Any], extra: dict[str, Any] | None = None):
    key = case["key"]
    state = {
        "thermogar_database_key": key,
        f"thermogar_composition_{key}": case["composition"],
        f"thermogar_units_{key}": "массовые %",
        f"thermogar_balance_{key}": case["balance"],
        f"b4b2_elastic_temperature_{key}": case["t_c"],
    }
    state.update(extra or {})
    return _start(state)


def _prepare(at) -> dict[str, Any]:
    at.button(key="b4b2_elastic_prepare_calculate").click().run()
    _assert_clean(at)
    return at.session_state[PREPARE_STATE]


def _rows(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["phase"]: row for row in state["projection"]["phase_rows"]}


def test_elastic_single_phase_weight_is_one_with_and_without_corrections(
    elastic_capture,
) -> None:
    """(а), (в) Ni-20Cr, одна фаза: φ = x = 1 при любой галочке."""

    at = _start_elastic(NI20CR)
    on_state = _prepare(at)
    assert on_state["physical_overrides"] is True
    on = on_state["projection"]
    assert [row["phase"] for row in on["phase_rows"]] == ["FCC_A1"]
    row = on["phase_rows"][0]
    assert row["volume_fraction"] == 1.0
    assert row["mole_fraction"] == pytest.approx(1.0, abs=1e-9)
    assert row["volume_source"] == "direct"
    assert row["molar_volume_cm3"] > 0.0
    assert on["warnings"][0].startswith(CR_OVERRIDE_PREFIX)
    shown = [element.value for element in at.warning]
    assert on["warnings"][0] in shown

    # Столбцы доли: оба только для чтения, подписи — мольная и объёмная.
    editor = elastic_capture["editor"][-1]
    assert editor["columns"][:3] == ["phase", "mole_fraction", "volume_fraction"]
    assert {"phase", "mole_fraction", "volume_fraction"} <= set(editor["disabled"])
    assert editor["column_config"]["mole_fraction"]["label"] == "Мольная доля фаз"
    assert editor["column_config"]["volume_fraction"]["label"] == "Объёмная доля фаз"

    at.button(key="b4b2_elastic_vrh_calculate").click().run()
    _assert_clean(at)
    assert at.session_state[VRH_STATE]["projection"]["phase_rows"][0][
        "volume_fraction"
    ] == 1.0

    # Снятая галочка сбрасывает показанную подготовку и VRH.
    _toggle(at).uncheck().run()
    _assert_clean(at)
    assert PREPARE_STATE not in at.session_state
    assert VRH_STATE not in at.session_state

    off_state = _prepare(at)
    assert off_state["physical_overrides"] is False
    off = off_state["projection"]
    assert off["warnings"][0].startswith(USER_OFF_PREFIX)
    assert not any(CR_OVERRIDE_PREFIX in text for text in off["warnings"])
    assert off["warnings"][1:] == on["warnings"][1:]
    off_row = off["phase_rows"][0]
    assert off_row["volume_fraction"] == 1.0
    assert off_row["mole_fraction"] == row["mole_fraction"]
    # Хром без поправки легче: молярный объём фазы больше.
    assert off_row["molar_volume_cm3"] > row["molar_volume_cm3"]


def test_elastic_two_phase_weights_are_volume_fractions(elastic_capture) -> None:
    """(б), (в) Fe-15Cr-0,4C, 950 °C: FCC_A1 + M23C6, обе модели прямые."""

    import io

    import pandas as pd

    at = _start_elastic(FE15CR04C)
    on_state = _prepare(at)
    on = _rows(on_state)
    assert sorted(on) == ["FCC_A1", "M23C6"]
    assert {row["volume_source"] for row in on.values()} == {"direct"}
    assert sum(row["volume_fraction"] for row in on.values()) == pytest.approx(1.0, abs=1e-12)
    assert sum(row["mole_fraction"] for row in on.values()) == pytest.approx(1.0, abs=1e-8)

    # φᵢ = xᵢ·Vmᵢ / Σ xⱼ·Vmⱼ, и отношение φ/x у двух фаз равно отношению Vm.
    total = sum(row["mole_fraction"] * row["molar_volume_cm3"] for row in on.values())
    for row in on.values():
        assert row["volume_fraction"] == pytest.approx(
            row["mole_fraction"] * row["molar_volume_cm3"] / total, rel=1e-12
        )
    ratio = (on["M23C6"]["volume_fraction"] / on["M23C6"]["mole_fraction"]) / (
        on["FCC_A1"]["volume_fraction"] / on["FCC_A1"]["mole_fraction"]
    )
    assert ratio == pytest.approx(
        on["M23C6"]["molar_volume_cm3"] / on["FCC_A1"]["molar_volume_cm3"], rel=1e-12
    )
    # У карбида на моль атомов объём меньше, чем у аустенита: доля по объёму ниже.
    assert on["M23C6"]["molar_volume_cm3"] < on["FCC_A1"]["molar_volume_cm3"]
    assert on["M23C6"]["volume_fraction"] < on["M23C6"]["mole_fraction"]

    at.button(key="b4b2_elastic_vrh_calculate").click().run()
    _assert_clean(at)
    vrh = at.session_state[VRH_STATE]["projection"]
    weights = {row["phase"]: row["volume_fraction"] for row in vrh["phase_rows"]}
    assert weights == {name: row["volume_fraction"] for name, row in on.items()}
    young = {row["phase"]: row["young_gpa"] for row in vrh["phase_rows"]}
    assert sorted(young.values()) == [100.0, 300.0]
    expected_e_voigt = sum(weights[name] * young[name] for name in weights)
    # При одинаковом ν среднее Фойгта по K и G даёт E как взвешенное среднее.
    assert vrh["summary"]["E_Voigt_GPa"] == pytest.approx(expected_e_voigt, rel=1e-12)

    sheets = pd.read_excel(
        io.BytesIO(elastic_capture["downloads"]["ThermoGar_elastic_vrh.xlsx"]),
        sheet_name=None,
    )
    columns = list(sheets["Входные значения по фазам"].columns)
    assert "Мольная доля фаз" in columns
    assert "Объёмная доля фаз" in columns
    assert "volume_fraction" not in columns

    # (в) Без поправки хрома объёмные доли другие, мольные — те же.
    _toggle(at).uncheck().run()
    off = _rows(_prepare(at))
    for name in on:
        assert off[name]["mole_fraction"] == on[name]["mole_fraction"]
        assert off[name]["volume_fraction"] != on[name]["volume_fraction"]


def test_elastic_weights_without_chromium_ignore_the_toggle(elastic_capture) -> None:
    """(в) Fe-1C, 800 °C: хрома нет — объёмные доли от галочки не зависят."""

    at = _start_elastic(FE1C)
    on_state = _prepare(at)
    on = on_state["projection"]
    assert len(on["phase_rows"]) == 2
    _toggle(at).uncheck().run()
    off_state = _prepare(at)
    off = off_state["projection"]
    assert off_state["physical_overrides"] is False
    assert off["phase_rows"] == on["phase_rows"]
    assert off["warnings"][0].startswith(USER_OFF_PREFIX)
    assert off["warnings"][1:] == on["warnings"][1:]
    # GRAPHITE в физической базе своей модели не имеет: оценка по смеси
    # элементов названа в warnings.
    assert any("GRAPHITE" in text and "правилу смеси" in text for text in on["warnings"])


def test_elastic_prepare_drops_unbuildable_order_disorder_pair(elastic_capture) -> None:
    """(15-Ч, BL-40) Ni-20Cr-0,3C, 700 °C: BCC_B2 снята и названа, VRH считается."""

    at = _start_elastic(NI20CR03C)
    state = _prepare(at)
    projection = state["projection"]
    phases = [row["phase"] for row in projection["phase_rows"]]
    assert "BCC_B2" not in phases
    assert "FCC_A1" in phases
    assert len(phases) >= 2, "углерод должен дать карбид рядом с аустенитом"
    assert sum(row["volume_fraction"] for row in projection["phase_rows"]) == pytest.approx(1.0, abs=1e-12)

    warnings = projection["warnings"]
    assert warnings[0].startswith(CR_OVERRIDE_PREFIX)
    assert warnings[1].startswith(EXCLUDED_PREFIX)
    assert "BCC_B2 (связана с BCC_A2" in warnings[1]
    assert sum(text.startswith(EXCLUDED_PREFIX) for text in warnings) == 1
    assert warnings[1] in [element.value for element in at.warning]

    at.button(key="b4b2_elastic_vrh_calculate").click().run()
    _assert_clean(at)
    vrh = at.session_state[VRH_STATE]["projection"]
    assert [row["phase"] for row in vrh["phase_rows"]] == phases
    summary = vrh["summary"]
    assert summary["E_Reuss_GPa"] < summary["E_Hill_GPa"] < summary["E_Voigt_GPa"]

    # Без поправок отметка «выключены пользователем» первая, снятая фаза — вторая.
    _toggle(at).uncheck().run()
    off = _prepare(at)["projection"]
    assert off["warnings"][0].startswith(USER_OFF_PREFIX)
    assert off["warnings"][1] == warnings[1]
