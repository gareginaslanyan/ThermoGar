"""Compact Steel-first Streamlit entry point."""
from __future__ import annotations

import streamlit as st

from thermogar_steel_section import render_steel_section


def render() -> None:
    st.set_page_config(page_title="ThermoGar · Сталь", layout="wide")
    if st.get_option("client.disableDataExport") is not True:
        st.error(
            "Запуск остановлен: не найдены обязательные настройки защиты "
            "данных. Запустите ThermoGar из основной папки программы."
        )
        st.stop()
    st.title("ThermoGar · Сталь")
    render_steel_section()


if __name__ == "__main__":
    render()
