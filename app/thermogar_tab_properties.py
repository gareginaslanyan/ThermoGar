"""Вкладка «Свойства» головного сценария ThermoGar.

BL-57, разрез app/ThermoGar_app.py (20-Л). Плотность в точке и по
температуре, упругие свойства, вклады упрочнения и покрытие физической
базы (контур B4B/B4B2): привязка физической базы, галочка поправок,
расчёт, показ и выгрузка. Определения, нужные только этой вкладке,
перенесены из головного сценария без изменений, в прежнем порядке; тело
вкладки — тоже без изменений. Имена головного сценария, которые читает
тело, связываются в начале функции из SidebarContext и RunServices — это
те же объекты, без копий.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from thermogar_palette import (
    ThemedFigure,
    chart_roles,
    normalize_theme,
)
import thermogar_parallel_ui as parallel_ui
from thermogar_workspace import (
    file_sha256,
    record_calculation_history,
)
from thermogar_physical import (
    OVERRIDES_OFF_BY_USER,
    PHYSICAL_DATABASE_VERSION,
    PhysicalDensityDatabase,
    calculate_physical_properties,
    overrides_enabled_by_environment,
)
from thermogar_database_guard import (
    FE_PROFILE_CANONICAL,
)
import thermogar_restricted_fe_core as restricted_fe
import thermogar_verified_loaders as verified_loaders
import thermogar_verified_physical as verified_physical
import thermogar_verified_properties as verified_properties
from thermogar_release_policy import (
    PHYSICAL_DATABASE_RELATIVE_PATH,
    PHYSICAL_DATABASE_SHA256,
)
from thermogar_properties import (
    STRENGTHENING_CONFIRMATION_TEXT,
    STRENGTHENING_PROVENANCE_TEXT,
    elastic_rows_missing_text,
)
from thermogar_release_ui import (
    BLOCK_PHASES,
    FoldedFields,
    action_row,
    folded_block,
    release_download_button,
    verified_feature_button,
)
from thermogar_user_errors import (
    EMPTY_CELL_TEXT,
    UserRuntimeError,
    UserValueError,
    element_columns_for_display,
)
from thermogar_app_texts import (
    ELASTIC_EDITOR_COLUMN_LABELS,
    ELASTIC_FRACTION_LABELS,
    PHYSICAL_BINDING_ERROR_TITLE,
    PHYSICAL_OVERRIDES_ENV_LOCKED_DETAILS,
    PHYSICAL_OVERRIDES_ENV_LOCKED_NOTE,
    PHYSICAL_OVERRIDES_TOGGLE_HELP,
    PHYSICAL_OVERRIDES_TOGGLE_KEY,
    PHYSICAL_OVERRIDES_TOGGLE_LABEL,
)
from thermogar_app_context import RunServices, SidebarContext
from thermogar_app_common import (
    PROJECT_ROOT,
    _verified_tdb_declared_phases,
    chart_figure,
    clear_b4b_physical_session_results,
    current_theme_type,
    figure_to_png,
    parse_composition,
    run_equilibrium_points,
    style_chart_axes,
)


acquire_b4b_execution = verified_loaders.acquire_execution
verified_physical_button = verified_feature_button
B4BPhysicalContext = verified_loaders.BoundDatabaseContext


PHYSICAL_DATABASE_PATH = (
    PROJECT_ROOT / PHYSICAL_DATABASE_RELATIVE_PATH
)


@st.cache_resource(show_spinner=False)
def _load_physical_database_cached(
    database_path_text: str,
    expected_sha256: str,
    physical_overrides: bool = True,
) -> PhysicalDensityDatabase:
    database_path = Path(database_path_text)
    if file_sha256(database_path) != expected_sha256:
        raise UserRuntimeError(
            "Файл физической базы изменился во время загрузки. Повторите действие."
        )
    if physical_overrides:
        database = PhysicalDensityDatabase(database_path)
    else:
        database = PhysicalDensityDatabase(
            database_path,
            overrides=OVERRIDES_OFF_BY_USER,
        )
    if file_sha256(database_path) != expected_sha256:
        raise UserRuntimeError(
            "Файл физической базы изменился во время загрузки. Повторите действие."
        )
    return database


def load_physical_database(
    physical_overrides: bool = True,
) -> PhysicalDensityDatabase:
    database_path = PHYSICAL_DATABASE_PATH.resolve()
    expected_path = (PROJECT_ROOT / PHYSICAL_DATABASE_RELATIVE_PATH).resolve()
    if database_path != expected_path or not database_path.is_file():
        raise UserRuntimeError(
            "Файл базы не совпадает с поставкой ThermoGar. Переустановите программу."
        )
    if file_sha256(database_path) != PHYSICAL_DATABASE_SHA256:
        raise UserRuntimeError(
            "Файл базы не совпадает с поставкой ThermoGar. Переустановите программу."
        )
    database = _load_physical_database_cached(
        str(database_path),
        PHYSICAL_DATABASE_SHA256,
        bool(physical_overrides),
    )
    if file_sha256(database_path) != PHYSICAL_DATABASE_SHA256:
        raise UserRuntimeError(
            "Файл физической базы изменился во время загрузки. Повторите действие."
        )
    return database


def density_below_pdb_text(
    temperature_c: float,
    physical_overrides: bool = True,
) -> str | None:
    """Текст отказа, если температура ниже той, с которой PDB задаёт плотность.

    BL-49: все DP-параметры physical_data_v103.pdb действуют с 298,15 K, и
    ниже расчёт падал ValueError (BACKEND_FAILED). Граница берётся из самой
    базы, текст утверждён владельцем. Сравнение то же, что у
    ``PhysicalDensityDatabase.parameter_value``, на той же температуре в K.
    """

    try:
        lower_k = load_physical_database(
            physical_overrides
        ).density_lower_temperature_k
    except Exception:
        # Базу не загрузить — об этом скажет сам расчёт, не эта проверка.
        return None
    if float(temperature_c) + 273.15 >= lower_k:
        return None
    lower_c = f"{lower_k - 273.15:.2f}".rstrip("0").rstrip(".")
    return (
        f"Физическая база задаёт плотность с {lower_c} °C; "
        f"введите {lower_c} °C или выше."
    )


def render_physical_overrides_toggle() -> bool:
    """Галочка поправок проекта к физической базе (BL-14).

    Возвращает ``False`` только когда поправки сняты галочкой. Если их
    выключила переменная окружения, галочка неактивна, а расчёт идёт штатным
    путём: там переменная уже решила всё сама.
    """

    if not overrides_enabled_by_environment():
        st.checkbox(
            PHYSICAL_OVERRIDES_TOGGLE_LABEL,
            value=False,
            disabled=True,
            help=PHYSICAL_OVERRIDES_TOGGLE_HELP,
            key=f"{PHYSICAL_OVERRIDES_TOGGLE_KEY}_env_locked",
        )
        st.caption(PHYSICAL_OVERRIDES_ENV_LOCKED_NOTE)
        with st.expander("Технические сведения", expanded=False):
            st.caption(PHYSICAL_OVERRIDES_ENV_LOCKED_DETAILS)
        return True
    return bool(
        st.checkbox(
            PHYSICAL_OVERRIDES_TOGGLE_LABEL,
            value=True,
            help=PHYSICAL_OVERRIDES_TOGGLE_HELP,
            key=PHYSICAL_OVERRIDES_TOGGLE_KEY,
        )
    )


def _b4b_refresh_overrides(state_key: str, physical_overrides: bool) -> None:
    """Показанный результат посчитан при другом положении галочки — убрать."""

    state = st.session_state.get(state_key)
    if type(state) is dict and state.get("physical_overrides", True) != bool(
        physical_overrides
    ):
        st.session_state.pop(state_key, None)


def bind_b4b_physical_context(
    database_key: str,
    *,
    services: RunServices,
) -> verified_loaders.BoundDatabaseContext:
    """Bind the separate canonical TDB+PDB capability for B4B1."""

    selector: dict[str, Any] = {
        "database_key": database_key,
        "include_physical_pdb": True,
    }
    if database_key == "fe":
        selector["profile_key"] = FE_PROFILE_CANONICAL
    catalog = verified_loaders.ArtifactCatalog.from_policy(
        PROJECT_ROOT,
        verified_loaders.canonical_release_manifest(),
        phase_provider=_verified_tdb_declared_phases,
    )
    context = verified_loaders.bind_selected_database(
        selector,
        catalog,
        services.paths,
    )
    proof_digest = verified_loaders.canonical_digest(
        {
            "database_key": context.database_key,
            "patch_id": context.patch_id,
            "passport": None
            if context.passport is None
            else context.passport.to_dict(),
            "phase_policy": context.phase_policy.to_dict(),
            "physical_pdb": context.physical_pdb.to_dict(),
            "profile_key": context.profile_key,
            "tdb": context.tdb.to_dict(),
        }
    )
    if st.session_state.get("_thermogar_b4b_physical_proof_v1") not in (
        None,
        proof_digest,
    ):
        clear_b4b_physical_session_results()
    st.session_state["_thermogar_b4b_physical_proof_v1"] = proof_digest
    return context


def _b4b_requested_phases(
    context: verified_loaders.BoundDatabaseContext,
    key: str,
    folded: FoldedFields | None = None,
) -> tuple[tuple[str, ...], str]:
    automatic = tuple(
        phase
        for phase in context.phase_policy.eligible_phases
        if phase != restricted_fe.C15_PHASE
    )
    folded = folded if folded is not None else FoldedFields()
    # Решение владельца 25.09.2026, п. 9 (2): выбор фаз — в свёрнутом блоке.
    with folded_block(BLOCK_PHASES):
        manual = folded.note(
            "Выбрать фазы вручную",
            st.checkbox(
                "Выбрать фазы вручную",
                key=f"{key}_manual",
            ),
            False,
        )
        if not manual:
            st.caption("Автоматические фазы: " + ", ".join(automatic))
            return (), "Автоматически"
        options = automatic + (
            () if restricted_fe.C15_PHASE in automatic else (restricted_fe.C15_PHASE,)
        )
        selected = tuple(
            st.multiselect(
                "Фазы",
                options=options,
                default=list(automatic),
                key=f"{key}_tokens",
                placeholder="Выберите из списка",
            )
        )
        folded.note("Фазы", selected, automatic)
    return selected, "Вручную"


def _b4b_prepare_decision(
    feature_id: str,
    context: verified_loaders.BoundDatabaseContext,
    inputs: dict[str, Any],
    requested_phases: tuple[str, ...],
) -> verified_loaders.FeatureRequest | verified_loaders.RejectedFeatureReceipt:
    candidates = tuple(
        phase
        for phase in context.phase_policy.eligible_phases
        if phase != restricted_fe.C15_PHASE
    )
    return verified_loaders.prepare_feature_request(
        feature_id,
        context,
        inputs,
        requested_phases,
        candidate_phases=candidates,
    )


def _b4b_refresh_result(
    state_key: str,
    decision: verified_loaders.FeatureRequest | verified_loaders.RejectedFeatureReceipt,
) -> None:
    state = st.session_state.get(state_key)
    if (
        type(decision) is not verified_loaders.FeatureRequest
        or type(state) is not dict
        or state.get("binding_digest") != decision.binding_digest
        or state.get("request_digest") != decision.request_digest
    ):
        st.session_state.pop(state_key, None)


def _b4b_store_result(
    state_key: str,
    database_key: str,
    execution: verified_physical.VerifiedPhysicalResult,
    physical_overrides: bool = True,
) -> None:
    st.session_state[state_key] = {
        "binding_digest": execution.feature_receipt.binding_digest,
        "database_key": database_key,
        "envelope_digest": execution.result_envelope.envelope_digest,
        "physical_overrides": bool(physical_overrides),
        "projections": [point.projection for point in execution.points],
        "receipt_digest": execution.feature_receipt.receipt_digest,
        "request_digest": execution.feature_receipt.request_digest,
    }


def _b4b_store_engine_result(
    state_key: str,
    database_key: str,
    decision: verified_loaders.FeatureRequest,
    projections: list[dict[str, Any]],
    note: str,
    physical_overrides: bool = True,
) -> None:
    """Результат многоточечного раздела «Свойства», посчитанный движком.

    Форма записи та же, что у ``_b4b_store_result``; квитанции лизы у неё нет,
    потому что многоточечный расчёт идёт мимо лизы, а отпечатки привязки и
    запроса сохраняются — по ним ``_b4b_refresh_result`` решает, жив ли ещё
    показанный результат.
    """
    st.session_state[state_key] = {
        "binding_digest": decision.binding_digest,
        "database_key": database_key,
        "engine_note": note,
        "envelope_digest": None,
        "physical_overrides": bool(physical_overrides),
        "projections": projections,
        "receipt_digest": None,
        "request_digest": decision.request_digest,
    }


def _b4b_render_result_downloads(
    key: str,
    sheets: dict[str, pd.DataFrame],
    *,
    sidebar: SidebarContext,
    services: RunServices,
    file_stem: str,
    figure: Any | None = None,
    history_label: str | None = None,
    history_details: dict[str, Any] | None = None,
) -> None:
    """Выгрузки раздела «Свойства».

    Раньше здесь стояли три кнопки, которые всегда оставались
    заблокированными: они запрашивали у StateStore типы содержимого
    (``physical-result-xlsx`` и другие), которых нет в его списке
    ``CONTENT_KINDS``. Выгрузка идёт тем же путём, что и в остальных
    разделах приложения: Excel и PNG собираются здесь и отдаются
    ``release_download_button``.
    """

    controls = 1 + (figure is not None) + (history_label is not None)
    columns = st.columns(controls)
    position = 0

    with columns[position]:
        release_download_button(
            "Скачать Excel",
            data=services.dataframe_to_excel(sheets),
            file_name=f"{file_stem}.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            key=f"{key}_xlsx",
        )
    position += 1

    if figure is not None:
        with columns[position]:
            release_download_button(
                "Скачать PNG",
                data=figure_to_png(figure),
                file_name=f"{file_stem}.png",
                mime="image/png",
                key=f"{key}_png",
            )
        position += 1

    if history_label is not None:
        with columns[position]:
            if st.button("Сохранить в историю", key=f"{key}_history"):
                record_calculation_history(
                    services.paths,
                    history_label,
                    sidebar.current_context,
                    dict(history_details or {}),
                )
                st.success("Запись добавлена в историю расчётов.")


def render_b4b_density_single(
    context: B4BPhysicalContext,
    database_key: str,
    composition_text: str,
    units: str,
    balance: str,
    pressure_pa: float,
    default_temperature_c: float,
    physical_overrides: bool = True,
    *,
    sidebar: SidebarContext,
    services: RunServices,
) -> None:
    st.markdown("### Плотность при одной температуре")
    temperature_c = st.number_input(
        "Температура, °C",
        value=float(default_temperature_c),
        step=10.0,
        key=f"physical_temperature_{database_key}",
    )
    density_folded = FoldedFields()
    requested, phase_mode = _b4b_requested_phases(
        context,
        "physical_single",
        density_folded,
    )
    too_cold = density_below_pdb_text(temperature_c, physical_overrides)
    if too_cold is not None:
        st.error(too_cold)
        with action_row("physical_single", density_folded):
            st.button(
                "Рассчитать плотность и объёмные доли",
                type="primary",
                key="physical_single_calculate",
                disabled=True,
            )
        return
    try:
        inputs = verified_physical.make_physical_inputs(
            "property_density_single",
            balance=balance,
            units=units,
            composition_pct=parse_composition(composition_text),
            pressure_pa=float(pressure_pa),
            temperatures_k=(float(temperature_c) + 273.15,),
        )
        decision = _b4b_prepare_decision(
            "property_density_single",
            context,
            inputs,
            requested,
        )
    except verified_loaders.VerifiedLoaderError as error:
        decision = verified_loaders.prepare_feature_request(
            "property_density_single",
            context,
            {"invalid_input": str(error)},
            requested,
            candidate_phases=tuple(context.phase_policy.eligible_phases),
        )
    state_key = "_thermogar_vlb_b4b_result_property_density_single"
    _b4b_refresh_result(state_key, decision)
    _b4b_refresh_overrides(state_key, physical_overrides)
    with action_row("physical_single", density_folded):
        density_clicked = verified_physical_button(
            decision,
            "Рассчитать плотность и объёмные доли",
            type="primary",
            key="physical_single_calculate",
        )
    if density_clicked:
        try:
            assert type(decision) is verified_loaders.FeatureRequest
            with acquire_b4b_execution(
                decision,
                services.paths,
            ) as lease:
                execution = verified_physical.execute_verified_physical(
                    context,
                    decision,
                    lease,
                    physical_overrides=physical_overrides,
                )
            _b4b_store_result(
                state_key,
                database_key,
                execution,
                physical_overrides,
            )
        except Exception as error:
            services.render_friendly_error(error, context="плотность и объёмные доли")
    state = st.session_state.get(state_key)
    if type(state) is dict and state.get("database_key") == database_key:
        projection = state["projections"][0]
        st.metric(
            "Плотность сплава, кг/м³",
            "—"
            if projection["alloy_density_kg_m3"] is None
            else f'{projection["alloy_density_kg_m3"]:.1f}',
        )
        st.caption(f"Режим фаз: {phase_mode}")
        coverage = pd.DataFrame(
            [
                ("Температура, °C", f"{float(temperature_c):.1f}"),
                (
                    "Покрытие физической базы по массе, %",
                    f'{projection["mass_coverage_pct"]:.2f}',
                ),
                (
                    "Покрытие физической базы по молям, %",
                    f'{projection["mole_coverage_pct"]:.2f}',
                ),
                ("Качество оценки", projection["quality_label"]),
                (
                    "Версия физической базы",
                    projection["physical_database_version"],
                ),
            ],
            columns=["Параметр", "Значение"],
        )
        st.dataframe(coverage, width="stretch", hide_index=True, placeholder=EMPTY_CELL_TEXT)
        if projection["alloy_density_kg_m3"] is None:
            # Пустое поле плотности само по себе ничего не объясняет:
            # у Al-состава для THETA_AL2CU в physical_data_v103.pdb нет
            # модели плотности, поэтому покрытие меньше 100 % и общая
            # плотность сплава честно не считается.
            missing_names = ", ".join(
                sorted(
                    {
                        str(row.get("Фаза") or row.get("phase") or "")
                        for row in projection["missing_rows"]
                    }
                    - {""}
                )
            )
            st.error(
                "Плотность сплава не рассчитана: покрытие физической базы "
                f'{projection["mass_coverage_pct"]:.2f} % по массе, '
                "то есть плотность есть не у всех равновесных фаз."
                + (
                    f" Без данных остались: {missing_names}."
                    if missing_names
                    else ""
                )
                + " Плотности отдельных фаз ниже посчитаны и выгружаются."
            )
        for warning_text in projection["warnings"]:
            st.warning(warning_text)
        st.dataframe(element_columns_for_display(pd.DataFrame(projection["phase_rows"])), width="stretch", hide_index=True, placeholder=EMPTY_CELL_TEXT)
        if projection["missing_rows"]:
            st.dataframe(element_columns_for_display(pd.DataFrame(projection["missing_rows"])), width="stretch", hide_index=True, placeholder=EMPTY_CELL_TEXT)
        _b4b_render_result_downloads(
            "physical_single",
            {
                "Параметры": coverage,
                "Фазы": pd.DataFrame(projection["phase_rows"]),
                "Без данных PDB": pd.DataFrame(projection["missing_rows"]),
            },
            file_stem="ThermoGar_density_single",
            history_label="Плотность при одной температуре",
            history_details={
                "temperature_c": float(temperature_c),
                "alloy_density_kg_m3": projection["alloy_density_kg_m3"],
                "mass_coverage_pct": projection["mass_coverage_pct"],
            },
            sidebar=sidebar,
            services=services,
        )


def render_b4b_density_temperature(
    context: B4BPhysicalContext,
    database_key: str,
    composition_text: str,
    units: str,
    balance: str,
    pressure_pa: float,
    default_min_c: float,
    default_max_c: float,
    default_step_c: float,
    physical_overrides: bool = True,
    *,
    sidebar: SidebarContext,
    services: RunServices,
) -> None:
    st.markdown("### Плотность и объёмные доли по температуре")
    columns = st.columns(3)
    with columns[0]:
        minimum_c = st.number_input("Температура от, °C", value=float(default_min_c), step=10.0, key=f"physical_t_min_{database_key}")
    with columns[1]:
        maximum_c = st.number_input("Температура до, °C", value=float(default_max_c), step=10.0, key=f"physical_t_max_{database_key}")
    with columns[2]:
        step_c = st.number_input("Шаг температуры, °C", min_value=0.1, value=float(default_step_c), step=5.0, key=f"physical_t_step_{database_key}")
    scan_folded = FoldedFields()
    requested, _phase_mode = _b4b_requested_phases(
        context, "physical_scan", scan_folded
    )
    # Скан начинается с minimum_c: ниже границы PDB счёт не запускается (BL-49).
    too_cold = density_below_pdb_text(minimum_c, physical_overrides)
    if too_cold is not None:
        st.error(too_cold)
        with action_row("physical_scan", scan_folded):
            st.button(
                "Построить плотность по температуре",
                type="primary",
                key="physical_scan_calculate",
                disabled=True,
            )
        return
    try:
        if maximum_c <= minimum_c:
            raise UserValueError("Конечная температура должна быть выше начальной.")
        temperatures_c = tuple(
            float(value)
            for value in np.arange(
                float(minimum_c),
                float(maximum_c) + 0.5 * float(step_c),
                float(step_c),
            )
        )
        inputs = verified_physical.make_physical_inputs(
            "property_density_temperature",
            balance=balance,
            units=units,
            composition_pct=parse_composition(composition_text),
            pressure_pa=float(pressure_pa),
            temperatures_k=tuple(value + 273.15 for value in temperatures_c),
        )
        decision = _b4b_prepare_decision(
            "property_density_temperature",
            context,
            inputs,
            requested,
        )
    except Exception as error:
        decision = verified_loaders.prepare_feature_request(
            "property_density_temperature",
            context,
            {"invalid_input": str(error)},
            requested,
            candidate_phases=tuple(context.phase_policy.eligible_phases),
        )
    state_key = "_thermogar_vlb_b4b_result_property_density_temperature"
    _b4b_refresh_result(state_key, decision)
    _b4b_refresh_overrides(state_key, physical_overrides)
    with action_row("physical_scan", scan_folded):
        density_scan_clicked = verified_physical_button(
            decision,
            "Построить плотность по температуре",
            type="primary",
            key="physical_scan_calculate",
        )
    if density_scan_clicked:
        try:
            assert type(decision) is verified_loaders.FeatureRequest
            # Температурный скан плотности многоточечный, поэтому идёт в
            # движок напрямую; одиночная точка остаётся на verified-маршруте.
            with st.spinner("Расчёт плотности по температуре…"):
                atomic, _mass = verified_physical.composition_fractions(sidebar.db, inputs)
                scan_components = [
                    element for element, _value in atomic
                ] + ["VA"]
                # Скан идёт в движок напрямую, мимо verified-бэкенда, поэтому
                # структурный детектор волны 10 применяется здесь же: иначе
                # нестроящаяся пара «порядок/беспорядок» уносит весь скан.
                scan_phases, scan_removed = verified_physical.buildable_phases(
                    sidebar.db,
                    scan_components,
                    verified_physical.effective_phases(
                        context,
                        decision.requested_phases,
                        sidebar.db,
                    ),
                )
                scan_points = [
                    {
                        "N": 1.0,
                        "P": float(pressure_pa),
                        "T": float(temperature_k),
                        "X": {
                            element: value
                            for element, value in atomic
                            if element != inputs["balance"]
                        },
                    }
                    for temperature_k in inputs["temperatures_k"]
                ]
                density_run = run_equilibrium_points(
                    scan_components,
                    list(scan_phases),
                    scan_points,
                    pdens=500,
                    capture=("X", "Y"),
                    progress_text="Точки плотности",
                    sidebar=sidebar,
                )
                physical_db = load_physical_database(physical_overrides)
                projections: list[dict[str, Any]] = []
                for temperature_k, result in zip(
                    inputs["temperatures_k"], density_run.results
                ):
                    properties = calculate_physical_properties(
                        sidebar.db,
                        parallel_ui.snapshot_of(result),
                        list(scan_components),
                        float(temperature_k),
                        physical_db,
                    )
                    projection = verified_physical.physical_projection(
                        properties,
                        excluded_phases=scan_removed,
                    )
                    projection["temperature_k"] = float(temperature_k)
                    projections.append(projection)
            _b4b_store_engine_result(
                state_key,
                database_key,
                decision,
                projections,
                density_run.note,
                physical_overrides,
            )
        except Exception as error:
            services.render_friendly_error(error, context="плотность по температуре")
    state = st.session_state.get(state_key)
    if type(state) is dict and state.get("database_key") == database_key:
        rows = []
        for projection in state["projections"]:
            rows.append(
                {
                    "Температура, K": projection.get("temperature_k"),
                    "Плотность сплава, кг/м³": projection["alloy_density_kg_m3"],
                    "Покрытие фаз, мол.%": projection["mole_coverage_pct"],
                    "Качество": projection["quality_label"],
                }
            )
        table = pd.DataFrame(rows)
        if state.get("engine_note"):
            st.caption(str(state["engine_note"]))
        # Поправки проекта поверх физической базы должны быть названы и здесь,
        # а не только в расчёте при одной температуре: они одинаковы во всех
        # точках, поэтому берутся из первой.
        for warning_text in (
            state["projections"][0]["warnings"] if state["projections"] else ()
        ):
            st.warning(warning_text)
        st.dataframe(table, width="stretch", hide_index=True, placeholder=EMPTY_CELL_TEXT)
        figure = None
        if not table.empty:
            # На экране и в PNG — один график из сохранённых точек в теме
            # прогона, кэш по теме (решение владельца 25.09.2026, п. 10, 15Б).
            figure = state.setdefault(
                "figure",
                ThemedFigure(plot_density_temperature, table),
            )
            st.pyplot(chart_figure(figure))
        _b4b_render_result_downloads(
            "physical_scan",
            {
                "Параметры": pd.DataFrame(
                    [
                        ("Температура от, °C", minimum_c),
                        ("Температура до, °C", maximum_c),
                        ("Шаг, °C", step_c),
                        ("Основа", balance),
                        ("Добавки", composition_text),
                        ("Давление, Па", pressure_pa),
                    ],
                    columns=["Параметр", "Значение"],
                ),
                "Плотность по температуре": table,
            },
            file_stem="ThermoGar_density_scan",
            figure=figure,
            history_label="Плотность по температуре",
            history_details={
                "temperature_from_c": float(minimum_c),
                "temperature_to_c": float(maximum_c),
                "points": int(len(table)),
            },
            sidebar=sidebar,
            services=services,
        )


def render_b4b_pdb_self_test(
    context: B4BPhysicalContext,
    database_key: str,
    *,
    services: RunServices,
) -> None:
    decision = _b4b_prepare_decision(
        "property_pdb_self_test",
        context,
        verified_physical.make_physical_inputs("property_pdb_self_test"),
        (),
    )
    state_key = "_thermogar_vlb_b4b_result_property_pdb_self_test"
    _b4b_refresh_result(state_key, decision)
    if verified_physical_button(
        decision,
        "Проверить чтение физической базы",
        key="physical_database_self_test",
    ):
        try:
            assert type(decision) is verified_loaders.FeatureRequest
            with acquire_b4b_execution(decision, services.paths) as lease:
                execution = verified_physical.execute_verified_physical(
                    context,
                    decision,
                    lease,
                )
            _b4b_store_result(state_key, database_key, execution)
        except Exception as error:
            services.render_friendly_error(error, context="проверка физической базы")
    state = st.session_state.get(state_key)
    if type(state) is dict and state.get("database_key") == database_key:
        st.dataframe(pd.DataFrame(state["projections"][0]["rows"]), width="stretch", hide_index=True, placeholder=EMPTY_CELL_TEXT)


def render_b4b_coverage(
    context: B4BPhysicalContext,
    database_key: str,
    *,
    sidebar: SidebarContext,
    services: RunServices,
) -> None:
    decision = _b4b_prepare_decision(
        "property_coverage_view",
        context,
        verified_physical.make_physical_inputs("property_coverage_view"),
        (),
    )
    state_key = "_thermogar_vlb_b4b_result_property_coverage_view"
    _b4b_refresh_result(state_key, decision)
    if verified_physical_button(
        decision,
        "Обновить покрытие физической базы",
        key="physical_coverage_view",
    ):
        try:
            assert type(decision) is verified_loaders.FeatureRequest
            with acquire_b4b_execution(decision, services.paths) as lease:
                execution = verified_physical.execute_verified_physical(
                    context,
                    decision,
                    lease,
                )
            _b4b_store_result(state_key, database_key, execution)
        except Exception as error:
            services.render_friendly_error(error, context="покрытие физической базы")
    state = st.session_state.get(state_key)
    if type(state) is dict and state.get("database_key") == database_key:
        coverage_rows = pd.DataFrame(state["projections"][0]["rows"])
        st.dataframe(coverage_rows, width="stretch", hide_index=True, placeholder=EMPTY_CELL_TEXT)
        _b4b_render_result_downloads(
            "physical_coverage",
            {"Покрытие физической базы": coverage_rows},
            file_stem="ThermoGar_pdb_coverage",
            sidebar=sidebar,
            services=services,
        )


def _b4b2_store_result(
    state_key: str,
    database_key: str,
    execution: verified_properties.VerifiedPropertiesResult,
    physical_overrides: bool = True,
) -> None:
    st.session_state[state_key] = {
        "binding_digest": execution.feature_receipt.binding_digest,
        "database_key": database_key,
        "envelope_digest": execution.result_envelope.envelope_digest,
        "hill_witness_digest": execution.hill_witness_digest,
        "physical_overrides": bool(physical_overrides),
        "prepared_witness_digest": execution.prepared_witness_digest,
        "projection": execution.projection,
        "receipt_digest": execution.feature_receipt.receipt_digest,
        "request_digest": execution.feature_receipt.request_digest,
    }


def _b4b2_editor_value(value: object) -> object:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


def render_b4b2_elastic_properties(
    context: B4BPhysicalContext,
    database_key: str,
    composition_text: str,
    units: str,
    balance: str,
    pressure_pa: float,
    default_temperature_c: float,
    physical_overrides: bool = True,
    *,
    sidebar: SidebarContext,
    services: RunServices,
) -> None:
    st.markdown("### Упругие свойства по фазовым долям")
    st.caption(
        "Сначала получите проверенные фазовые доли, затем укажите E, ν и "
        "происхождение значений для расчёта Voigt–Reuss–Hill."
    )
    temperature_c = st.number_input(
        "Температура, °C",
        value=float(default_temperature_c),
        step=10.0,
        key=f"b4b2_elastic_temperature_{database_key}",
    )
    prepare_folded = FoldedFields()
    requested, _phase_mode = _b4b_requested_phases(
        context, "b4b2_elastic_prepare", prepare_folded
    )
    try:
        prepare_inputs = verified_properties.make_prepare_inputs(
            balance=balance,
            composition_pct=parse_composition(composition_text),
            pressure_pa=float(pressure_pa),
            temperatures_k=(float(temperature_c) + 273.15,),
            units=units,
        )
        prepare_decision = _b4b_prepare_decision(
            "property_elastic_prepare",
            context,
            prepare_inputs,
            requested,
        )
        prepare_error = None
    except Exception as error:
        prepare_decision = None
        prepare_error = error
        services.render_friendly_error(
            error,
            context="подготовка упругих свойств",
            title="Исходные данные для упругих свойств не приняты.",
        )
    prepare_state_key = "_thermogar_vlb_b4b_result_property_elastic_prepare"
    vrh_state_key = "_thermogar_vlb_b4b_result_property_elastic_vrh"
    # Объёмные доли фаз зависят от поправок к физической базе (BL-38):
    # посчитанное при другом положении галочки не показывается.
    _b4b_refresh_overrides(prepare_state_key, physical_overrides)
    _b4b_refresh_overrides(vrh_state_key, physical_overrides)
    if prepare_decision is not None:
        _b4b_refresh_result(prepare_state_key, prepare_decision)
        with action_row("elastic_prepare", prepare_folded):
            prepare_clicked = verified_physical_button(
                prepare_decision,
                "Получить фазовые доли",
                type="primary",
                key="b4b2_elastic_prepare_calculate",
            )
        if prepare_clicked:
            try:
                assert type(prepare_decision) is verified_loaders.FeatureRequest
                with acquire_b4b_execution(prepare_decision, services.paths) as lease:
                    execution = verified_properties.execute_verified_properties(
                        context,
                        prepare_decision,
                        lease,
                        paths=services.paths,
                        physical_overrides=physical_overrides,
                    )
                _b4b2_store_result(
                    prepare_state_key,
                    database_key,
                    execution,
                    physical_overrides,
                )
            except Exception as error:
                services.render_friendly_error(error, context="подготовка упругих свойств")
    elif prepare_error is not None:
        st.caption("Исправьте входные данные, чтобы подготовить фазовые доли.")

    prepared = st.session_state.get(prepare_state_key)
    if type(prepared) is not dict or prepared.get("database_key") != database_key:
        return
    prepared_digest = prepared.get("prepared_witness_digest")
    if type(prepared_digest) is not str:
        return
    for text in prepared.get("projection", {}).get("warnings", ()):
        st.warning(text)
    try:
        library_view = verified_properties.property_library_prefill(
            context,
            prepared_digest,
            paths=services.paths,
        )
    except Exception as error:
        services.render_friendly_error(error, context="библиотека упругих свойств")
        return
    editor = pd.DataFrame(list(library_view.phase_rows))
    edited = st.data_editor(
        editor,
        width="stretch",
        hide_index=True,
        disabled=["phase", "mole_fraction", "volume_fraction"],
        # Мольные доли даёт равновесие (NP); объёмные — они же, пересчитанные
        # через молярные объёмы фаз из физической базы. VRH берёт объёмные.
        column_config={
            **{
                field: st.column_config.NumberColumn(label)
                for field, label in ELASTIC_FRACTION_LABELS.items()
            },
            **ELASTIC_EDITOR_COLUMN_LABELS,
        },
        key=f"b4b2_elastic_editor_{prepared_digest}",
        placeholder=EMPTY_CELL_TEXT,
    )
    update_library = st.checkbox(
        "Обновить локальную библиотеку введёнными значениями",
        value=False,
        key=f"b4b2_elastic_update_{prepared_digest}",
    )
    phase_rows: list[dict[str, Any]] = []
    for record in edited.to_dict(orient="records"):
        row = {
            field: _b4b2_editor_value(record.get(field))
            for field in verified_properties.VRH_ROW_FIELDS
        }
        # BL-70: проверенный путь принимает текст без пробелов по краям, а
        # стёртое «Примечание» приходит из редактора как None. Пустоту
        # обязательных полей по-прежнему ловит elastic_rows_missing_text.
        for field in ("origin", "source", "note"):
            if isinstance(row[field], str):
                row[field] = row[field].strip()
        if row["note"] is None:
            row["note"] = ""
        phase_rows.append(row)
    try:
        vrh_inputs = verified_properties.make_vrh_inputs(
            prepared_witness_digest=prepared_digest,
            library_snapshot_digest=library_view.library_snapshot_digest,
            library_update=update_library,
            phase_rows=phase_rows,
        )
        vrh_decision = _b4b_prepare_decision(
            "property_elastic_vrh",
            context,
            vrh_inputs,
            (),
        )
    except Exception as error:
        services.render_friendly_error(
            error,
            context="Voigt–Reuss–Hill",
            title="Таблица упругих свойств не принята. Проверьте E и ν каждой фазы.",
        )
        return
    _b4b_refresh_result(vrh_state_key, vrh_decision)
    # Решение владельца 11Б (25.09.2026): пока таблица фаз неполна, кнопка
    # неактивна, под ней — первая причина фразой раздела.
    vrh_missing = elastic_rows_missing_text(phase_rows)
    with action_row("b4b2_elastic_vrh_action", sticky=False):
        vrh_clicked = verified_physical_button(
            vrh_decision,
            "Рассчитать Voigt–Reuss–Hill",
            type="primary",
            key="b4b2_elastic_vrh_calculate",
            disabled=vrh_missing is not None,
        )
        if vrh_missing is not None:
            st.caption(vrh_missing)
    if vrh_clicked:
        try:
            assert type(vrh_decision) is verified_loaders.FeatureRequest
            with acquire_b4b_execution(vrh_decision, services.paths) as lease:
                execution = verified_properties.execute_verified_properties(
                    context,
                    vrh_decision,
                    lease,
                    paths=services.paths,
                )
            _b4b2_store_result(
                vrh_state_key,
                database_key,
                execution,
                physical_overrides,
            )
        except Exception as error:
            services.render_friendly_error(error, context="Voigt–Reuss–Hill")
    state = st.session_state.get(vrh_state_key)
    if type(state) is dict and state.get("database_key") == database_key:
        projection = state["projection"]
        bounds_table = pd.DataFrame(projection["bounds_rows"])
        st.dataframe(bounds_table, width="stretch", hide_index=True, placeholder=EMPTY_CELL_TEXT)
        summary = projection["summary"]
        metric_columns = st.columns(3)
        metric_columns[0].metric("E Hill, ГПа", f'{summary["E_Hill_GPa"]:.3f}')
        metric_columns[1].metric("G Hill, ГПа", f'{summary["G_Hill_GPa"]:.3f}')
        metric_columns[2].metric("ν Hill", f'{summary["nu_Hill"]:.5f}')
        _b4b_render_result_downloads(
            "b4b2_elastic",
            {
                "Voigt-Reuss-Hill": bounds_table,
                "Итог": pd.DataFrame(
                    [(name, value) for name, value in summary.items()],
                    columns=["Величина", "Значение"],
                ),
                "Входные значения по фазам": pd.DataFrame(
                    [
                        {
                            "phase": row["phase"],
                            "mole_fraction": view_row["mole_fraction"],
                            **{
                                key: value
                                for key, value in row.items()
                                if key != "phase"
                            },
                        }
                        for row, view_row in zip(
                            phase_rows, library_view.phase_rows
                        )
                    ]
                ).rename(columns=ELASTIC_FRACTION_LABELS),
            },
            file_stem="ThermoGar_elastic_vrh",
            history_label="Упругие свойства (Voigt-Reuss-Hill)",
            history_details={
                "temperature_c": float(temperature_c),
                "E_Hill_GPa": summary["E_Hill_GPa"],
                "G_Hill_GPa": summary["G_Hill_GPa"],
                "nu_Hill": summary["nu_Hill"],
            },
            sidebar=sidebar,
            services=services,
        )


def render_b4b2_strengthening(
    context: B4BPhysicalContext,
    database_key: str,
    *,
    sidebar: SidebarContext,
    services: RunServices,
) -> None:
    st.markdown("### Вклады механизмов упрочнения")
    st.caption(
        "Коэффициенты и область применимости задаются явно; отсутствие "
        "экспериментальной квалификации не блокирует расчёт."
    )
    provenance = st.text_area(
        "Источник и область применимости входов",
        key=f"b4b2_strengthening_provenance_{database_key}",
    )
    confirmation = st.checkbox(
        "Подтверждаю область применимости введённых коэффициентов",
        key=f"b4b2_strengthening_confirmation_{database_key}",
    )
    sigma_internal = st.number_input(
        "Базовое внутреннее сопротивление, МПа",
        min_value=0.0,
        value=0.0,
        key=f"b4b2_strengthening_sigma_{database_key}",
    )
    rule = st.selectbox(
        "Правило объединения",
        options=(
            "Не суммировать",
            "Линейная сумма",
            "Квадратичное объединение вкладов",
        ),
        key=f"b4b2_strengthening_rule_{database_key}",
    )
    # Поля блоков механизмов считаются в подписи «Не по умолчанию».
    strengthening_folded = FoldedFields()
    note = strengthening_folded.note
    with st.expander("Hall–Petch"):
        use_hall = note("Учитывать Hall–Petch", st.checkbox("Учитывать Hall–Petch", key=f"b4b2_hall_use_{database_key}"), False)
        hall_k = note("k_y, МПа·м¹ᐟ²", st.number_input("k_y, МПа·м¹ᐟ²", min_value=0.0, value=0.1, key=f"b4b2_hall_k_{database_key}"), 0.1)
        grain = note("Размер зерна, мкм", st.number_input("Размер зерна, мкм", min_value=1e-12, value=10.0, key=f"b4b2_hall_grain_{database_key}"), 10.0)
    vrh_state = st.session_state.get("_thermogar_vlb_b4b_result_property_elastic_vrh")
    hill_digest = (
        vrh_state.get("hill_witness_digest")
        if type(vrh_state) is dict and vrh_state.get("database_key") == database_key
        else None
    )
    use_hill = st.checkbox(
        "Использовать G и ν из текущего результата Hill",
        value=False,
        disabled=type(hill_digest) is not str,
        key=f"b4b2_strengthening_hill_{database_key}",
    )
    with st.expander("Taylor"):
        use_taylor = note("Учитывать Taylor", st.checkbox("Учитывать Taylor", key=f"b4b2_taylor_use_{database_key}"), False)
        taylor_factor = note("M (Taylor)", st.number_input("M (Taylor)", min_value=1e-12, value=3.0, key=f"b4b2_taylor_m_{database_key}"), 3.0)
        alpha = note("α", st.number_input("α", min_value=1e-12, value=0.3, key=f"b4b2_taylor_alpha_{database_key}"), 0.3)
        shear = note("G, ГПа (Taylor)", st.number_input("G, ГПа (Taylor)", min_value=1e-12, value=80.0, disabled=use_hill, key=f"b4b2_taylor_g_{database_key}"), 80.0)
        burgers = note("b, нм (Taylor)", st.number_input("b, нм (Taylor)", min_value=1e-12, value=0.25, key=f"b4b2_taylor_b_{database_key}"), 0.25)
        dislocations = note("Плотность дислокаций, м⁻²", st.number_input("Плотность дислокаций, м⁻²", min_value=1e-12, value=1e12, key=f"b4b2_taylor_rho_{database_key}"), 1e12)
    solid_enabled = st.checkbox("Твёрдорастворный вклад", key=f"b4b2_solid_use_{database_key}")
    solid = st.number_input("Твёрдорастворный вклад, МПа", min_value=0.0, value=0.0, disabled=not solid_enabled, key=f"b4b2_solid_{database_key}")
    with st.expander("Orowan"):
        use_orowan = note("Учитывать Orowan", st.checkbox("Учитывать Orowan", key=f"b4b2_orowan_use_{database_key}"), False)
        orowan_m = note("M (Orowan)", st.number_input("M (Orowan)", min_value=1e-12, value=3.0, key=f"b4b2_orowan_m_{database_key}"), 3.0)
        orowan_g = note("G, ГПа (Orowan)", st.number_input("G, ГПа (Orowan)", min_value=1e-12, value=80.0, disabled=use_hill, key=f"b4b2_orowan_g_{database_key}"), 80.0)
        orowan_b = note("b, нм (Orowan)", st.number_input("b, нм (Orowan)", min_value=1e-12, value=0.25, key=f"b4b2_orowan_b_{database_key}"), 0.25)
        orowan_nu = note("ν (Orowan) (-0.999–0.499)", st.number_input("ν (Orowan) (-0.999–0.499)", min_value=-0.999, max_value=0.499, value=0.3, disabled=use_hill, key=f"b4b2_orowan_nu_{database_key}"), 0.3)
        radius = note("Радиус частиц, нм", st.number_input("Радиус частиц, нм", min_value=1e-12, value=10.0, key=f"b4b2_orowan_radius_{database_key}"), 10.0)
        spacing = note("Расстояние между частицами, нм", st.number_input("Расстояние между частицами, нм", min_value=1e-12, value=100.0, key=f"b4b2_orowan_spacing_{database_key}"), 100.0)
    other_enabled = st.checkbox("Другой вклад", key=f"b4b2_other_use_{database_key}")
    other = st.number_input("Другой вклад, МПа", min_value=0.0, value=0.0, disabled=not other_enabled, key=f"b4b2_other_{database_key}")
    inputs = verified_properties.make_strengthening_inputs(
        input_provenance=provenance if provenance else None,
        input_confirmation=confirmation,
        sigma_internal_mpa=float(sigma_internal),
        hall_petch=(
            {"k_y_mpa_sqrt_m": float(hall_k), "grain_size_um": float(grain)}
            if use_hall
            else None
        ),
        taylor=(
            {
                "taylor_factor": float(taylor_factor),
                "alpha": float(alpha),
                "shear_gpa": None if use_hill else float(shear),
                "burgers_nm": float(burgers),
                "dislocation_density_m2": float(dislocations),
            }
            if use_taylor
            else None
        ),
        solid_solution_mpa=float(solid) if solid_enabled else None,
        orowan=(
            {
                "taylor_factor": float(orowan_m),
                "shear_gpa": None if use_hill else float(orowan_g),
                "burgers_nm": float(orowan_b),
                "poisson": None if use_hill else float(orowan_nu),
                "particle_radius_nm": float(radius),
                "spacing_nm": float(spacing),
            }
            if use_orowan
            else None
        ),
        other_mpa=float(other) if other_enabled else None,
        summation_rule=rule,
        hill_witness_digest=hill_digest if use_hill else None,
    )
    decision = _b4b_prepare_decision(
        "property_strengthening",
        context,
        inputs,
        (),
    )
    state_key = "_thermogar_vlb_b4b_result_property_strengthening"
    _b4b_refresh_result(state_key, decision)
    # Решение владельца 11Б (25.09.2026): пока обязательное не заполнено,
    # кнопка неактивна, под ней — что заполнить.
    if not str(provenance or "").strip():
        strengthening_missing = STRENGTHENING_PROVENANCE_TEXT
    elif not confirmation:
        strengthening_missing = STRENGTHENING_CONFIRMATION_TEXT
    else:
        strengthening_missing = None
    with action_row("strengthening", strengthening_folded):
        strengthening_clicked = verified_physical_button(
            decision,
            "Рассчитать вклады",
            type="primary",
            key="b4b2_strengthening_calculate",
            disabled=strengthening_missing is not None,
        )
        if strengthening_missing is not None:
            st.caption(strengthening_missing)
    if strengthening_clicked:
        try:
            assert type(decision) is verified_loaders.FeatureRequest
            with acquire_b4b_execution(decision, services.paths) as lease:
                execution = verified_properties.execute_verified_properties(
                    context,
                    decision,
                    lease,
                    paths=services.paths,
                )
            _b4b2_store_result(state_key, database_key, execution)
        except Exception as error:
            services.render_friendly_error(error, context="вклады упрочнения")
    state = st.session_state.get(state_key)
    if type(state) is dict and state.get("database_key") == database_key:
        projection = state["projection"]
        contribution_table = pd.DataFrame(projection["contribution_rows"])
        st.dataframe(contribution_table, width="stretch", hide_index=True, placeholder=EMPTY_CELL_TEXT)
        if projection["total_mpa"] is not None:
            st.metric("Итог, МПа", f'{projection["total_mpa"]:.3f}')
        _b4b_render_result_downloads(
            "b4b2_strengthening",
            {
                "Вклады механизмов": contribution_table,
                "Параметры": pd.DataFrame(
                    [
                        ("Правило объединения", rule),
                        (
                            "Базовое внутреннее сопротивление, МПа",
                            sigma_internal,
                        ),
                        ("Источник входов", provenance),
                        ("Итог, МПа", projection["total_mpa"]),
                    ],
                    columns=["Параметр", "Значение"],
                ),
            },
            file_stem="ThermoGar_strengthening",
            history_label="Вклады механизмов упрочнения",
            history_details={
                "summation_rule": rule,
                "total_mpa": projection["total_mpa"],
            },
            sidebar=sidebar,
            services=services,
        )


def plot_density_temperature(
    dataframe: pd.DataFrame,
    theme_type: str | None = None,
) -> plt.Figure:
    """Кривая плотности сплава по температуре для выгрузки PNG."""
    theme_type = normalize_theme(theme_type or current_theme_type())
    roles = chart_roles(theme_type)
    figure, axes = plt.subplots(figsize=(9.5, 5.5), dpi=100)
    axes.plot(
        np.asarray(dataframe["Температура, K"], dtype=float),
        np.asarray(dataframe["Плотность сплава, кг/м³"], dtype=float),
        color=roles["primary"],
        linewidth=1.8,
        marker="o",
        markersize=3.5,
    )
    style_chart_axes(
        figure,
        axes,
        "Плотность сплава по температуре",
        "Температура, K",
        "Плотность сплава, кг/м³",
        theme_type,
    )
    # Решение владельца 25.09.2026, п. 10 (15Б): ось плотности — по данным,
    # числа целиком, без смещения вида «+7.6e3» на узком диапазоне.
    axes.ticklabel_format(axis="y", style="plain", useOffset=False)
    figure.tight_layout()
    return figure


def render_properties_tab(*, sidebar: SidebarContext, services: RunServices) -> None:
    """Вкладка «Свойства»; головной сценарий вызывает её в ``with physical_tab:``."""

    # Имена головного сценария, которые читает тело вкладки.
    database_key = sidebar.database_key
    definition = sidebar.definition
    balance = sidebar.balance
    units = sidebar.units
    composition_text = sidebar.composition_text
    pressure_pa = sidebar.pressure_pa
    render_friendly_error = services.render_friendly_error
    SIDEBAR = sidebar
    SERVICES = services

    st.subheader("Физические свойства и механизмы упрочнения")
    st.caption(
        "Плотность и объёмные доли считаются по термодинамической и "
        "физической базам. Упругость и упрочнение — по тем же базам."
    )

    try:
        b4b_physical_context = bind_b4b_physical_context(database_key, services=SERVICES)
        b4b_physical_error = None
    except Exception as error:
        b4b_physical_context = None
        b4b_physical_error = error
        render_friendly_error(
            error,
            context="физическая база",
            title="Физическая база не подключена: файлы не прошли проверку.",
        )

    physical_overrides = render_physical_overrides_toggle()

    (
        physical_single_tab,
        physical_scan_tab,
        elastic_properties_tab,
        strengthening_tab,
        physical_coverage_tab,
    ) = st.tabs(
        [
            "Плотность",
            "Плотность по T",
            "Упругие свойства",
            "Вклады упрочнения",
            "Покрытие физической базы",
        ]
    )

    with physical_single_tab:
        if b4b_physical_context is None:
            st.error(PHYSICAL_BINDING_ERROR_TITLE)
        else:
            render_b4b_density_single(
                b4b_physical_context,
                database_key,
                composition_text,
                units,
                balance,
                float(pressure_pa),
                float(definition["default_temperature"]),
                physical_overrides,
                sidebar=SIDEBAR,
                services=SERVICES,
            )

    with physical_scan_tab:
        if b4b_physical_context is None:
            st.error(PHYSICAL_BINDING_ERROR_TITLE)
        else:
            render_b4b_density_temperature(
                b4b_physical_context,
                database_key,
                composition_text,
                units,
                balance,
                float(pressure_pa),
                float(definition["default_t_min"]),
                float(definition["default_t_max"]),
                float(definition["default_t_step"]),
                physical_overrides,
                sidebar=SIDEBAR,
                services=SERVICES,
            )

    with elastic_properties_tab:
        if b4b_physical_context is None:
            st.error(PHYSICAL_BINDING_ERROR_TITLE)
        else:
            render_b4b2_elastic_properties(
                b4b_physical_context,
                database_key,
                composition_text,
                units,
                balance,
                float(pressure_pa),
                float(definition["default_temperature"]),
                physical_overrides,
                sidebar=SIDEBAR,
                services=SERVICES,
            )

    with strengthening_tab:
        if b4b_physical_context is None:
            st.error(PHYSICAL_BINDING_ERROR_TITLE)
        else:
            render_b4b2_strengthening(
                b4b_physical_context,
                database_key,
                sidebar=SIDEBAR,
                services=SERVICES,
            )

    with physical_coverage_tab:
        st.markdown("### Что покрывает физическая база")
        if b4b_physical_context is None:
            st.error(PHYSICAL_BINDING_ERROR_TITLE)
        else:
            st.caption("Физическая база " + PHYSICAL_DATABASE_VERSION)
            with st.expander("Технические сведения", expanded=False):
                st.code(
                    "SHA-256: " + b4b_physical_context.physical_pdb.sha256,
                    language=None,
                )
            render_b4b_coverage(
                b4b_physical_context,
                database_key,
                sidebar=SIDEBAR,
                services=SERVICES,
            )
            render_b4b_pdb_self_test(
                b4b_physical_context,
                database_key,
                services=SERVICES,
            )
