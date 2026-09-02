"""Reusable Steel diagnostic body for ThermoGar Streamlit surfaces."""
from __future__ import annotations

import math

import streamlit as st

import thermogar_fe_steel_adapter as steel


CAPTION = "Локальный диагностический расчёт; не является квалификацией материала, производственным режимом или подтверждением свойств."


def _default_inputs() -> dict[str, float]:
    return dict(steel.DEFAULT_WT_PERCENT)


def _is_control_point(values: dict[str, float], temperature: float) -> bool:
    return values == steel.DEFAULT_WT_PERCENT and temperature == steel.DEFAULT_TEMPERATURE_K


def _show_result(result: dict[str, object]) -> None:
    st.dataframe(
        [{"Фаза": row["phase"], "Доля": row["fraction"]} for row in result["terminal_rows"]],
        hide_index=True,
        width="stretch",
    )
    if result["c15_observed"]:
        st.write("C15_LAVES наблюдается в терминальном состоянии.")
    else:
        st.write("C15_LAVES не наблюдается в терминальном состоянии.")


def render_steel_section() -> None:
    st.caption(CAPTION)

    if "steel_values" not in st.session_state:
        st.session_state.steel_values = _default_inputs()
    if "steel_temperature" not in st.session_state:
        st.session_state.steel_temperature = steel.DEFAULT_TEMPERATURE_K
    if "steel_running" not in st.session_state:
        st.session_state.steel_running = False

    values: dict[str, float] = {}
    columns = st.columns(6)
    for index, element in enumerate(steel.NON_FE_ORDER):
        with columns[index % len(columns)]:
            values[element] = st.number_input(
                f"{element}, wt%",
                min_value=0.0,
                max_value=math.nextafter(steel.UPPER_WT_PERCENT[element], 0.0),
                value=float(st.session_state.steel_values[element]),
                step=0.01,
                format="%.6f",
                key=f"steel_{element}",
            )
    temperature = st.number_input(
        "Температура, K", min_value=673.0, max_value=2000.0,
        value=float(st.session_state.steel_temperature), step=1.0, format="%.1f", key="steel_T",
    )
    fe_balance = 100.0 - math.fsum(values.values())
    st.metric("Fe, wt% (баланс)", f"{fe_balance:.6f}")

    try:
        pin_signature = steel.verify_pins()
        signature = steel.input_signature(values, temperature, pin_signature)
    except steel.SteelAdapterError:
        signature = None
    if st.session_state.get("steel_signature") != signature:
        st.session_state.pop("steel_result", None)
        st.session_state.steel_signature = signature

    if st.button("Рассчитать локально", type="primary", disabled=st.session_state.steel_running or signature is None):
        st.session_state.steel_running = True
        st.session_state.pop("steel_result", None)
        try:
            result = steel.run_diagnostic(
                values, temperature,
                current_signature=lambda: steel.input_signature(values, temperature, steel.verify_pins()),
            )
            if result["signature"] == st.session_state.get("steel_signature"):
                st.session_state.steel_result = result
        except steel.SteelAdapterError:
            st.error("Локальный расчёт недоступен.")
        finally:
            st.session_state.steel_running = False

    result = st.session_state.get("steel_result")
    if result is None and _is_control_point(values, temperature):
        try:
            result = steel.load_control_point_view()
        except steel.SteelAdapterError:
            result = None
    if result is not None and signature == st.session_state.get("steel_signature"):
        _show_result(result)
