"""Вкладка «Кинетика» головного сценария ThermoGar.

BL-57, разрез app/ThermoGar_app.py (20-К): первая вкладка в своём модуле.
Подвкладки «Диффузия и гомогенизация» и «Выделения» рисуют модули
thermogar_diffusion и thermogar_precipitation; вкладка передаёт им базу,
контекст боковой панели и службы прогона.

Тело вкладки перенесено из головного сценария без изменений. Имена, которые
оно читало из головного сценария, связываются в начале функции из
SidebarContext и RunServices — это те же объекты, без копий.
"""

from __future__ import annotations

import streamlit as st

from thermogar_app_common import figure_to_png
from thermogar_app_context import RunServices, SidebarContext
from thermogar_diffusion import render_kinetics_section
from thermogar_precipitation import render_precipitation_section
from thermogar_workspace import record_calculation_history


def render_kinetics_tab(*, sidebar: SidebarContext, services: RunServices) -> None:
    """Вкладка «Кинетика»; головной сценарий вызывает её в ``with diffusion_tab:``."""

    # Имена головного сценария, которые читает тело вкладки.
    database_key = sidebar.database_key
    definition = sidebar.definition
    db = sidebar.db
    database_path = sidebar.database_path
    CURRENT_CONTEXT = sidebar.current_context
    THERMOGAR_PATHS = services.paths
    render_friendly_error = services.render_friendly_error
    dataframe_to_excel = services.dataframe_to_excel

    diffusion_subtab, precipitation_subtab = st.tabs(
        ["Диффузия и гомогенизация", "Выделения"]
    )
    with diffusion_subtab:
        render_kinetics_section(
            db=db,
            database_key=database_key,
            database_path=database_path,
            database_label=definition["label"],
            project_root=THERMOGAR_PATHS,
            current_context=CURRENT_CONTEXT,
            dataframe_to_excel=dataframe_to_excel,
            figure_to_png=figure_to_png,
            render_error=render_friendly_error,
            record_history=record_calculation_history,
        )
    with precipitation_subtab:
        render_precipitation_section(
            db=db,
            database_key=database_key,
            database_path=database_path,
            database_label=definition["label"],
            project_root=THERMOGAR_PATHS,
            current_context=CURRENT_CONTEXT,
            render_error=render_friendly_error,
            record_history=record_calculation_history,
        )
