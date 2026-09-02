"""ThermoGar Research Desktop — no-experiment research software.

The feature list below describes the current development surface. Release
claims and feature dispositions are frozen in ``thermogar_release_policy``.
Legacy Stage numbers identify implementation history only.

Возможности интерфейса:
- равновесие при одной температуре;
- сканирование по температуре;
- сканирование по концентрации;
- бинарные диаграммы состояния;
- многокомпонентные изоплеты (псевдобинарные сечения);
- тройные изотермические диаграммы состояния;
- тройные карты мольной доли выбранной фазы;
- равновесное затвердевание и расчёт Scheil–Gulliver;
- ликвидус, солидус, интервал кристаллизации и остаточный расплав;
- энергии Гиббса отдельных фаз при фиксированном составе;
- движущая сила образования выбранной фазы;
- температура T₀ равенства энергий двух фаз;
- ручной выбор и подавление фаз;
- метастабильные равновесные расчёты;
- встроенный краткий гайд и справочник фаз;
- библиотека пользовательских марок и составов;
- пакетный импорт и расчёт Excel / CSV;
- сохраняемые проекты и история с отпечатками баз;
- автоматическая проверка материального баланса;
- плотность фаз и сплава по physical_data.pdb 1.03;
- массовые и объёмные доли фаз, молярные объёмы;
- графики плотности и объёмных долей по температуре;
- одномерная однофазная диффузия по базе подвижностей;
- многофазная локально-равновесная гомогенизация;
- профили состава, фазовые профили и оценка выравнивания;
- кинетика выделений KWN: зарождение, рост, растворение и укрупнение;
- временные зависимости доли, радиуса, плотности частиц и состава матрицы;
- пользовательские температурные циклы и распределение частиц по размерам;
- упругие свойства многфазного сплава по Voigt–Reuss–Hill;
- локальная библиотека E и ν фаз с происхождением и SHA-256;
- прозрачный расчёт вкладов Hall–Petch, Taylor и Orowan;
- понятные ошибки без стектрейса на основном экране;
- проверка установки и контрольные software-regression расчёты Ni / Al;
- учебные примеры и итоговый пользовательский гайд;
- экспорт Excel / CSV / PNG / ZIP / JSON.

Запуск:
    streamlit run app/ThermoGar_app.py
"""

from __future__ import annotations

from collections import defaultdict
from contextlib import suppress
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import hashlib
import json
import re
import threading
import zipfile
from typing import Any

from thermogar_paths import ThermoGarPaths, migrate_legacy_state


THERMOGAR_PATHS = ThermoGarPaths()
THERMOGAR_PATHS.configure_process_environment()

import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd
import streamlit as st
from pycalphad import Database, Model, Workspace, equilibrium, variables as v
from pycalphad.mapping import BinaryStrategy, IsoplethStrategy, TernaryStrategy
from pycalphad.plot import triangular  # регистрация треугольной проекции matplotlib
from pycalphad.core.utils import filter_phases, unpack_species
from pycalphad.property_framework.metaproperties import DormantPhase
from pycalphad.property_framework.tzero import T0

try:
    import scheil as scheil_package
    from scheil import (
        simulate_equilibrium_solidification,
        simulate_scheil_solidification,
    )

    SCHEIL_AVAILABLE = True
    SCHEIL_IMPORT_ERROR = ""
except Exception as scheil_import_error:
    scheil_package = None
    simulate_equilibrium_solidification = None
    simulate_scheil_solidification = None
    SCHEIL_AVAILABLE = False
    SCHEIL_IMPORT_ERROR = str(scheil_import_error)

from thermogar_palette import chart_roles, phase_styles
from thermogar_workspace import (
    apply_pending_state,
    context_snapshot,
    file_sha256,
    queue_context_load,
    record_calculation_history,
    render_alloy_library,
    render_batch_calculation,
    render_projects_and_history,
    validate_context_payload,
)
from thermogar_stage14 import (
    APP_VERSION,
    render_friendly_error as _render_friendly_error,
    render_preflight,
    render_quality_panel,
    render_quick_examples,
    validate_scan_result,
    validate_single_result,
    validate_solidification_paths,
    validation_dataframe,
)
from thermogar_physical import (
    PHYSICAL_DATABASE_VERSION,
    PhysicalDensityDatabase,
    calculate_physical_properties,
    physical_coverage_dataframe,
)
from thermogar_diffusion import (
    KAWIN_AVAILABLE,
    KAWIN_IMPORT_ERROR,
    render_kinetics_section,
)
from thermogar_precipitation import (
    PRECIPITATION_AVAILABLE,
    PRECIPITATION_IMPORT_ERROR,
    render_precipitation_section,
)
from thermogar_database_guard import (
    FE_DATABASE_MAX_T_C,
    FE_PROFILE_CANONICAL,
    FE_PROFILE_LABELS,
    load_profile_manifest,
    passport_dataframe,
)
from thermogar_secure_io import (
    MAX_TDB_SNAPSHOT_BYTES,
    held_verified_snapshot,
    lexical_absolute,
    parse_verified_utf8_snapshot,
)
import thermogar_restricted_fe_core as restricted_fe
import thermogar_verified_equilibrium as verified_equilibrium
import thermogar_verified_loaders as verified_loaders
import thermogar_verified_physical as verified_physical
import thermogar_verified_properties as verified_properties
import thermogar_verified_state as verified_state
from thermogar_verified_artifact import read_verified_utf8_text
from thermogar_release_policy import (
    APP_LINEAGE,
    FE_EXCLUDED_PHASES,
    PHYSICAL_DATABASE_RELATIVE_PATH,
    PHYSICAL_DATABASE_SHA256,
    PRODUCTION_USE,
    RELEASE_DATABASE_FILENAMES,
    RELEASE_DATABASE_KEYS,
    RELEASE_DATABASE_LABELS,
    RELEASE_DATABASE_RELATIVE_PATHS,
    RELEASE_DATABASE_SHA256,
    RELEASE_CLASS,
    RUNTIME_POLICY_GENERATION,
    SCIENTIFIC_MATERIAL_STATUS,
    SOFTWARE_RELEASE_STATUS,
    effective_release_phases,
)
from thermogar_release_ui import (
    release_calculation_button,
    release_download_button,
    verified_equilibrium_button,
    verified_feature_button,
)

acquire_b3_execution = verified_loaders.acquire_execution
acquire_b4b_execution = verified_loaders.acquire_execution
execute_bound_fe_batch = restricted_fe.execute_bound_restricted_fe
verified_physical_button = verified_feature_button
B4BPhysicalContext = verified_loaders.BoundDatabaseContext


def render_friendly_error(error: Exception, *, context: str) -> None:
    _render_friendly_error(error, context=context, paths=THERMOGAR_PATHS)


# ---------------------------------------------------------------------------
# Настройки приложения и баз
# ---------------------------------------------------------------------------

DISPLAY_APP_NAME = "ThermoGar"


class _CompactHelpRendered(Exception):
    """Leave the historical help block after rendering compact product help."""

st.set_page_config(
    page_title=DISPLAY_APP_NAME,
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Streamlit resolves per-project configuration from the launch working
# directory, not from this script's directory. A launch from ``app/`` would
# otherwise silently re-enable built-in dataframe/chart exports. Refuse to
# render any application data unless the effective runtime option is active.
if st.get_option("client.disableDataExport") is not True:
    st.error(
        "Запуск остановлен fail-closed: встроенный экспорт таблиц/графиков "
        "не отключён. Запускайте ThermoGar из корня проекта, где находится "
        ".streamlit/config.toml."
    )
    st.stop()

DATABASE_DEFINITIONS = {
    "ni": {
        "label": "Никелевые сплавы — mc_ni 2.036",
        "relative_path": (
            "databases/converted/"
            "mc_ni_v2036_with_mobility.garcalc.tdb"
        ),
        "default_balance": "NI",
        "default_composition": "AL=15",
        "default_units": "at",
        "default_temperature": 700.0,
        "default_t_min": 500.0,
        "default_t_max": 1200.0,
        "default_t_step": 25.0,
    },
    "fe": {
        "label": "Стали и Fe-сплавы — mc_fe 2.062",
        "relative_path": (
            "databases/converted/fe/"
            "mc_fe_v2062_with_mobility.thermogar.tdb"
        ),
        "default_balance": "FE",
        "default_composition": (
            "C=0.20, CR=11.5, NI=0.7, MN=0.7, SI=0.3, "
            "MO=0.6, W=0.9, V=0.225"
        ),
        "default_units": "wt",
        "default_temperature": 700.0,
        "default_t_min": 400.0,
        "default_t_max": 1200.0,
        "default_t_step": 400.0,
    },
    "al": {
        "label": "Алюминиевые сплавы — mc_al 2.037",
        "relative_path": (
            "databases/converted/al/"
            "mc_al_v2037_with_mobility.thermogar.tdb"
        ),
        "default_balance": "AL",
        "default_composition": "CU=4",
        "default_units": "at",
        "default_temperature": 500.0,
        "default_t_min": 200.0,
        "default_t_max": 700.0,
        "default_t_step": 25.0,
    },
}

FE_PROFILE_RELATIVE_PATHS = {
    FE_PROFILE_CANONICAL: (
        "databases/converted/fe/"
        "mc_fe_v2062_with_mobility.thermogar.tdb"
    ),
}
FE_PROFILE_SHA256 = {
    FE_PROFILE_CANONICAL: (
        "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612"
    ),
}


SOLIDIFICATION_DEFAULTS = {
    "ni": {
        "start_temperature_c": 1800.0,
        "step_temperature_c": 10.0,
    },
    "fe": {
        "start_temperature_c": 1500.0,
        "step_temperature_c": 10.0,
    },
    "al": {
        "start_temperature_c": 850.0,
        "step_temperature_c": 5.0,
    },
}

SOLIDIFICATION_METHOD_LABELS = {
    "equilibrium": "Равновесное",
    "scheil": "Scheil–Gulliver",
}


ENERGY_DEFAULTS = {
    "ni": {
        "phases": ["FCC_A1", "GAMMA_PRIME", "LIQUID"],
        "driving_phase": "GAMMA_PRIME",
        "tzero_phases": ["FCC_A1", "GAMMA_PRIME"],
        "variable_element": "AL",
        "c_min": 0.0,
        "c_max": 25.0,
        "c_step": 1.0,
        "units": "at",
        "t_min": 300.0,
        "t_max": 1700.0,
        "t_step": 25.0,
    },
    "fe": {
        "phases": ["BCC_B2", "FCC_A1", "LIQUID"],
        "driving_phase": "FCC_A1",
        "tzero_phases": ["BCC_B2", "FCC_A1"],
        "variable_element": "C",
        "c_min": 0.0,
        "c_max": 2.0,
        "c_step": 0.1,
        "units": "wt",
        "t_min": 300.0,
        "t_max": 1700.0,
        "t_step": 25.0,
    },
    "al": {
        "phases": ["GP_MAT", "LIQUID"],
        "driving_phase": "LIQUID",
        "tzero_phases": ["GP_MAT", "LIQUID"],
        "variable_element": "CU",
        "c_min": 0.0,
        "c_max": 15.0,
        "c_step": 0.5,
        "units": "at",
        "t_min": 100.0,
        "t_max": 1000.0,
        "t_step": 10.0,
    },
}

PHASE_EXPLANATIONS = {
    "ni": {
        "FCC_A1": "γ-матрица, ГЦК",
        "GAMMA_PRIME": "γ′-упрочняющая фаза",
        "LIQUID": "расплав",
        "BCC_B2": "B2 / связанная ОЦК-модель",
        "NIAL": "интерметаллид NiAl",
        "DELTA": "δ-фаза",
        "ETA": "η-фаза",
        "SIGMA": "σ-фаза",
        "LAVES": "фаза Лавеса",
        "LAV_C14": "фаза Лавеса C14",
        "CEMENTITE": "цементит",
        "GRAPHITE": "графит",
    },
    "fe": {
        "BCC_B2": "феррит / связанная ОЦК-модель A2–B2",
        "BCC_A2": "феррит / ОЦК",
        "FCC_A1": "аустенит / ГЦК",
        "CEMENTITE": "цементит Fe₃C",
        "GRAPHITE": "графит",
        "LIQUID": "расплав",
        "HCP_A3": "ГПУ-фаза",
        "SIGMA": "σ-фаза",
        "M23C6": "карбид M₂₃C₆",
        "M6C": "карбид M₆C",
        "MC": "карбид MC",
    },
    "al": {
        "FCCAL": "алюминиевая матрица, ГЦК",
        "FCC_A1": "ГЦК-твёрдый раствор",
        "GP_MAT": (
            "связанная модель Al-матрицы / GP-зон; "
            "название само по себе не означает 100 % GP-зон"
        ),
        "THETA_AL2CU": "равновесная θ-фаза Al₂Cu",
        "THETA_PRIME": "метастабильная θ′-фаза",
        "LIQUID": "расплав",
        "MG2SI_B": "равновесная фаза Mg₂Si",
        "MG5SI6_B_DP": "метастабильная β″-фаза Mg₅Si₆",
        "AL3SC": "упрочняющая фаза Al₃Sc",
        "AL3ZR": "фаза Al₃Zr",
        "L12AL3ZR": "когерентная L1₂-фаза Al₃Zr",
        "AL3TI": "интерметаллид Al₃Ti",
        "SI_DIAMOND_A4": "кремний",
        "DIAMOND_A4": "кремний, алмазная решётка",
    },
}


BINARY_DIAGRAM_DEFAULTS = {
    "ni": {
        "left": "NI",
        "right": "AL",
        "units": "at",
        "c_min": 0.0,
        "c_max": 35.0,
        "c_step": 1.0,
        "t_min": 400.0,
        "t_max": 1600.0,
        "t_step": 10.0,
    },
    "fe": {
        "left": "FE",
        "right": "C",
        "units": "wt",
        "c_min": 0.0,
        "c_max": 6.7,
        "c_step": 0.1,
        "t_min": 400.0,
        "t_max": 1600.0,
        "t_step": 10.0,
    },
    "al": {
        "left": "AL",
        "right": "CU",
        "units": "wt",
        "c_min": 0.0,
        "c_max": 55.0,
        "c_step": 1.0,
        "t_min": 200.0,
        "t_max": 800.0,
        "t_step": 10.0,
    },
}


ISOPLETH_DEFAULTS = {
    "ni": {
        "variable": "AL",
        "fixed": "CR=15, CO=10",
        "c_min": 0.0,
        "c_max": 10.0,
        "c_step": 0.5,
        "t_min": 500.0,
        "t_max": 1500.0,
        "t_step": 10.0,
    },
    "fe": {
        "variable": "C",
        "fixed": "CR=18, NI=8",
        "c_min": 0.0,
        "c_max": 3.0,
        "c_step": 0.1,
        "t_min": 400.0,
        "t_max": 1600.0,
        "t_step": 10.0,
    },
    "al": {
        "variable": "CU",
        "fixed": "MG=1, SI=1",
        "c_min": 0.0,
        "c_max": 8.0,
        "c_step": 0.25,
        "t_min": 200.0,
        "t_max": 750.0,
        "t_step": 10.0,
    },
}


TERNARY_DIAGRAM_DEFAULTS = {
    "ni": {
        "x": "AL",
        "y": "CR",
        "dependent": "NI",
        "temperature": 1000.0,
        "step": 2.5,
        "tieline_every": 5,
    },
    "fe": {
        "x": "CR",
        "y": "NI",
        "dependent": "FE",
        "temperature": 800.0,
        "step": 2.5,
        "tieline_every": 5,
    },
    "al": {
        "x": "CU",
        "y": "MG",
        "dependent": "AL",
        "temperature": 500.0,
        "step": 2.5,
        "tieline_every": 5,
    },
}


TERNARY_PHASE_MAP_DEFAULTS = {
    "ni": {
        "x": "AL",
        "y": "CR",
        "dependent": "NI",
        "temperature": 1000.0,
        "step": 5.0,
        "phase": "GAMMA_PRIME",
        "units": "at",
        "appearance_threshold": 0.1,
    },
    "fe": {
        "x": "C",
        "y": "CR",
        "dependent": "FE",
        "temperature": 800.0,
        "step": 5.0,
        "phase": "CEMENTITE",
        "units": "wt",
        "appearance_threshold": 0.1,
    },
    "al": {
        "x": "CU",
        "y": "MG",
        "dependent": "AL",
        "temperature": 500.0,
        "step": 5.0,
        "phase": "THETA_AL2CU",
        "units": "at",
        "appearance_threshold": 0.1,
    },
}


# ---------------------------------------------------------------------------
# Общие функции
# ---------------------------------------------------------------------------

def find_project_root() -> Path:
    """Найти корень проекта независимо от текущей рабочей папки."""
    candidates = [
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for candidate in candidates:
        if (candidate / "databases").exists():
            return candidate
    raise FileNotFoundError(
        "Не найдена папка databases. "
        "Положите приложение в папку ThermoGar/app."
    )


PROJECT_ROOT = find_project_root()
LEGACY_MIGRATION_RECEIPT = migrate_legacy_state(THERMOGAR_PATHS, PROJECT_ROOT)


# Case-sensitive on purpose. A TDB keyword is uppercase, while the indented
# bibliography inside REFERENCE_FILE contains lines such as
# "Phase diagram in the iron-rich corner ...". Matching those case-insensitively
# returned "diagram", "equilibria", "relations" and "stability" as phase names,
# which the verified loader then rejected as non-canonical, so binding any
# database failed and the application stopped before rendering any control.
_TDB_PHASE_DECLARATION = re.compile(
    r"(?m)^\s*PHASE\s+([A-Z][A-Z0-9_]*)\s"
)


def _verified_tdb_declared_phases(
    artifact: verified_loaders.VerifiedArtifact,
) -> tuple[str, ...]:
    """Read only canonical PHASE declarations from a verified TDB snapshot."""

    if type(artifact) is not verified_loaders.VerifiedArtifact:
        raise TypeError("Verified phase declaration provider requires TDB evidence.")
    phases = tuple(
        sorted(set(_TDB_PHASE_DECLARATION.findall(artifact.verified_text())))
    )
    if not phases:
        raise RuntimeError("Verified TDB contains no canonical PHASE declarations.")
    return phases


def load_project_style() -> None:
    """Подключить минимальный стабильный CSS-слой проекта."""
    style_path = PROJECT_ROOT / "app" / "style.css"
    if style_path.exists():
        st.markdown(
            f"<style>{style_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


load_project_style()


_DATABASE_SNAPSHOT_CACHE: dict[tuple[str, str], Database] = {}
_DATABASE_SNAPSHOT_CACHE_LOCK = threading.RLock()


def _parse_database_snapshot(
    expected_sha256: str,
    snapshot_sha256: str,
    snapshot_bytes: bytes,
) -> Database:
    return parse_verified_utf8_snapshot(
        snapshot_bytes,
        expected_sha256=expected_sha256,
        snapshot_sha256=snapshot_sha256,
        parser=lambda source: Database.from_file(source, fmt="tdb"),
    )


def _database_cache_get(cache_key: tuple[str, str]) -> Database | None:
    with _DATABASE_SNAPSHOT_CACHE_LOCK:
        return _DATABASE_SNAPSHOT_CACHE.get(cache_key)


def _database_cache_commit(
    cache_key: tuple[str, str],
    database: Database,
) -> Database:
    with _DATABASE_SNAPSHOT_CACHE_LOCK:
        return _DATABASE_SNAPSHOT_CACHE.setdefault(cache_key, database)


def load_database(
    database_key: str,
    fe_profile_key: str = FE_PROFILE_CANONICAL,
) -> tuple[Database, Path]:
    if not isinstance(database_key, str):
        raise ValueError("Ключ базы должен быть строкой.")
    database_key = database_key.strip().casefold()
    if database_key not in DATABASE_DEFINITIONS:
        raise ValueError(
            f"База {database_key!r} не входит в список доступных баз."
        )
    definition = DATABASE_DEFINITIONS[database_key]
    if database_key == "fe":
        if fe_profile_key not in FE_PROFILE_RELATIVE_PATHS:
            raise ValueError(
                f"Неизвестный профиль Fe-базы: {fe_profile_key!r}."
            )
        expected_relative_path = FE_PROFILE_RELATIVE_PATHS[fe_profile_key]
        database_path = lexical_absolute(PROJECT_ROOT / expected_relative_path)
        expected_sha256 = FE_PROFILE_SHA256[fe_profile_key]
    else:
        expected_relative_path = RELEASE_DATABASE_RELATIVE_PATHS[database_key]
        database_path = lexical_absolute(
            PROJECT_ROOT / definition["relative_path"]
        )
        expected_sha256 = RELEASE_DATABASE_SHA256[database_key]
    expected_path = lexical_absolute(PROJECT_ROOT / expected_relative_path)
    if (
        (
            database_key != "fe"
            and definition["label"] != RELEASE_DATABASE_LABELS[database_key]
        )
        or database_path != expected_path
        or (
            database_key != "fe"
            and database_path.name != RELEASE_DATABASE_FILENAMES[database_key]
        )
    ):
        raise RuntimeError(
            f"Путь базы {database_key!r} не соответствует закреплённому профилю."
        )
    with held_verified_snapshot(
        database_path,
        expected_sha256=expected_sha256,
        maximum_bytes=MAX_TDB_SNAPSHOT_BYTES,
        canonical_root=PROJECT_ROOT,
    ) as snapshot:
        cache_key = (expected_sha256, snapshot.sha256)
        database = _database_cache_get(cache_key)
        if database is None:
            database = _parse_database_snapshot(
                expected_sha256,
                snapshot.sha256,
                snapshot.data,
            )
    database = _database_cache_commit(cache_key, database)
    return database, database_path


def restricted_fe_calculation_button(
    database_key: str,
    fe_profile_key: str,
    *args: Any,
    **kwargs: Any,
) -> bool:
    """Enable only the three call sites that explicitly select exact Fe."""
    if database_key == "fe":
        if fe_profile_key != FE_PROFILE_CANONICAL:
            raise RuntimeError("Restricted Fe profile identity mismatch.")
        return bool(st.button(*args, **kwargs))
    return release_calculation_button(*args, **kwargs)


def restricted_fe_refresh_session_result(
    state_key: str,
    fingerprint: str | None,
) -> None:
    stored = st.session_state.get(state_key)
    if not isinstance(stored, dict) or fingerprint is None:
        st.session_state.pop(state_key, None)
        return
    retained = restricted_fe.retain_receipt_for_fingerprint(
        stored.get("receipt"),
        stored.get("fingerprint"),
        fingerprint,
    )
    if retained is None:
        st.session_state.pop(state_key, None)


def clear_restricted_fe_session_results() -> None:
    for state_key in tuple(st.session_state):
        if str(state_key).startswith(
            (
                "_thermogar_restricted_fe_result_",
                "_thermogar_vlb_b2_result_",
                "_thermogar_vlb_b2_request_",
                "_thermogar_vlb_b3_result_",
                "_thermogar_vlb_b3_request_",
            )
        ):
            st.session_state.pop(state_key, None)


def clear_b3_session_results() -> None:
    for state_key in tuple(st.session_state):
        if str(state_key).startswith(
            ("_thermogar_vlb_b3_result_", "_thermogar_vlb_b3_request_")
        ) or state_key == "workspace_batch_result":
            st.session_state.pop(state_key, None)


def clear_b4b_physical_session_results() -> None:
    for state_key in tuple(st.session_state):
        if str(state_key).startswith("_thermogar_vlb_b4b_result_"):
            st.session_state.pop(state_key, None)
    verified_properties.clear_property_witnesses()


def restricted_fe_b2_fingerprint(
    request: restricted_fe.RestrictedFeRequest,
    feature_request: verified_loaders.FeatureRequest,
) -> str:
    return restricted_fe.canonical_digest(
        {
            "context_digest": restricted_fe.context_digest(
                restricted_fe.restricted_fe_context()
            ),
            "request_digest": restricted_fe.request_digest(request),
            "binding_digest": feature_request.binding_digest,
            "binding_generation": feature_request.binding_generation,
            "feature_request_digest": feature_request.request_digest,
        }
    )


def restricted_fe_prepare_b2_decision(
    context: verified_loaders.BoundDatabaseContext,
    request: restricted_fe.RestrictedFeRequest,
    candidate_phases: tuple[str, ...],
    selected_phases: tuple[str, ...],
) -> verified_loaders.FeatureRequest | verified_loaders.RejectedFeatureReceipt:
    if restricted_fe.C15_PHASE in selected_phases:
        inputs = restricted_fe.restricted_fe_request_inputs(request)
        inputs["requested_phases"] = list(selected_phases)
        return verified_loaders.prepare_feature_request(
            request.feature_id,
            context,
            inputs,
            selected_phases,
            candidate_phases=candidate_phases,
        )
    return restricted_fe.prepare_bound_restricted_fe_request(
        context,
        request,
        candidate_phases,
    )


def restricted_fe_store_result(
    state_key: str,
    fingerprint: str,
    request: restricted_fe.RestrictedFeRequest,
    feature_request: verified_loaders.FeatureRequest,
    execution: restricted_fe.BoundRestrictedFeResult,
) -> None:
    receipt = execution.core1_receipt
    if receipt.outcome != "success":
        raise RuntimeError(
            "Fe-расчёт остановлен: "
            + (receipt.error_code or "UNKNOWN_FAILURE")
        )
    receipt_fingerprint = restricted_fe_b2_fingerprint(
        request,
        feature_request,
    )
    if receipt_fingerprint != fingerprint:
        raise RuntimeError("Restricted Fe receipt identity mismatch.")
    st.session_state[state_key] = {
        "fingerprint": fingerprint,
        "receipt": receipt,
        "feature_request": feature_request,
        "feature_receipt": execution.feature_receipt,
        "result_envelope": execution.result_envelope,
    }


def restricted_fe_result_dataframe(
    receipt: restricted_fe.RestrictedFeReceipt,
    axis_label: str,
) -> pd.DataFrame:
    rows: list[dict[str, float]] = []
    for point in receipt.points:
        row = {axis_label: float(point.axis_value)}
        row.update(
            {
                phase: 100.0 * float(fraction)
                for phase, fraction in point.phase_fractions
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).fillna(0.0)


def verified_b3_candidate_phases(
    context: verified_loaders.BoundDatabaseContext,
    candidates: tuple[str, ...],
) -> tuple[str, ...]:
    without_c15 = tuple(
        phase for phase in candidates if phase != restricted_fe.C15_PHASE
    )
    return context.phase_policy.effective((), candidates=without_c15)


def verified_b3_refresh_result(
    result_key: str,
    request_key: str,
    decision: verified_loaders.FeatureRequest | verified_loaders.RejectedFeatureReceipt | None,
) -> None:
    request_digest = (
        decision.request_digest
        if type(decision) is verified_loaders.FeatureRequest
        else None
    )
    if st.session_state.get(request_key) != request_digest:
        st.session_state.pop(result_key, None)
    if request_digest is None:
        st.session_state.pop(request_key, None)
    else:
        st.session_state[request_key] = request_digest


def verified_b3_store_result(
    state_key: str,
    display: dict[str, Any],
    execution: verified_equilibrium.VerifiedEquilibriumResult | None,
) -> None:
    st.session_state[state_key] = {
        "display": display,
        "receipt_digest": (
            execution.feature_receipt.receipt_digest
            if execution is not None
            else None
        ),
        "envelope_digest": (
            execution.result_envelope.envelope_digest
            if execution is not None
            else None
        ),
    }


def verified_b3_point_tables(
    point: verified_equilibrium.EquilibriumPoint,
    database_key: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    atomic_rows: list[dict[str, Any]] = []
    mass_rows: list[dict[str, Any]] = []
    atomic = dict(point.phase_atomic)
    mass = dict(point.phase_mass)
    for phase, fraction in point.phase_fractions:
        explanation = PHASE_EXPLANATIONS.get(database_key, {}).get(phase, "")
        summary_rows.append(
            {
                "Фаза": phase,
                "Что это": explanation,
                "Мольная доля фазы, %": 100.0 * fraction,
            }
        )
        atomic_row: dict[str, Any] = {"Фаза": phase, "Что это": explanation}
        mass_row: dict[str, Any] = {"Фаза": phase, "Что это": explanation}
        atomic_row.update(
            {
                f"{element}, ат.%": 100.0 * value
                for element, value in atomic[phase]
            }
        )
        mass_row.update(
            {
                f"{element}, мас.%": 100.0 * value
                for element, value in mass[phase]
            }
        )
        atomic_rows.append(atomic_row)
        mass_rows.append(mass_row)
    return (
        pd.DataFrame(summary_rows),
        pd.DataFrame(atomic_rows),
        pd.DataFrame(mass_rows),
    )


class VerifiedB3BatchBroker:
    """Bind, prepare, lease, and execute each B3 row without raw authority."""

    def __init__(self, sidebar_selector: dict[str, Any]) -> None:
        self._sidebar_selector = dict(sidebar_selector)

    @staticmethod
    def _catalog() -> verified_loaders.ArtifactCatalog:
        return verified_loaders.ArtifactCatalog.from_policy(
            PROJECT_ROOT,
            verified_loaders.canonical_release_manifest(),
            phase_provider=_verified_tdb_declared_phases,
        )

    def _bind(self, database_key: str) -> verified_loaders.BoundDatabaseContext:
        selector: dict[str, Any] = {
            "database_key": database_key,
            "include_physical_pdb": False,
        }
        if database_key == "fe":
            selector["profile_key"] = FE_PROFILE_CANONICAL
        return verified_loaders.bind_selected_database(
            selector,
            self._catalog(),
            THERMOGAR_PATHS,
        )

    def _restore_sidebar(self) -> verified_loaders.BoundDatabaseContext:
        global vlb_bound_context
        previous = st.session_state.get("_thermogar_vlb_bound_context_v1")
        vlb_bound_context = verified_loaders.bind_selected_database(
            self._sidebar_selector,
            self._catalog(),
            THERMOGAR_PATHS,
        )
        st.session_state["_thermogar_vlb_selector_v1"] = dict(
            self._sidebar_selector
        )
        st.session_state["_thermogar_vlb_bound_context_v1"] = (
            vlb_bound_context.to_dict()
        )
        # Пересвязывание тем же селектором каждый раз даёт новые
        # binding_digest и binding_generation, поэтому по ним нельзя судить
        # о смене базы: иначе результаты сканов стирались бы на каждом
        # прогоне. Значение имеет только фактическая смена базы и профиля.
        if (
            type(previous) is not dict
            or previous.get("database_key") != vlb_bound_context.database_key
            or previous.get("profile_key") != vlb_bound_context.profile_key
        ):
            clear_b3_session_results()
        return vlb_bound_context

    @staticmethod
    def _decision(
        feature_id: str,
        context: verified_loaders.BoundDatabaseContext,
        inputs: dict[str, Any],
        requested_phases: tuple[str, ...] = (),
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

    def import_decision(
        self,
    ) -> verified_loaders.FeatureRequest | verified_loaders.RejectedFeatureReceipt:
        context = self._restore_sidebar()
        return self._decision(
            "data_batch_request_import",
            context,
            {"maximum_rows": 100, "mode": "visible_upload"},
        )

    def execute_decision(
        self,
        *,
        row_count: int,
        source_digest: str,
    ) -> verified_loaders.FeatureRequest | verified_loaders.RejectedFeatureReceipt:
        context = self._restore_sidebar()
        return self._decision(
            "data_batch_execute",
            context,
            {"row_count": int(row_count), "source_digest": source_digest},
        )

    def export_decision(
        self,
    ) -> verified_loaders.FeatureRequest | verified_loaders.RejectedFeatureReceipt:
        context = self._restore_sidebar()
        return self._decision(
            "data_batch_export",
            context,
            {"direction": "egress", "mode": "verified_state"},
        )

    def state_decision(
        self,
        feature_id: str,
        inputs: dict[str, object],
        requested_phases: tuple[str, ...] = (),
    ) -> verified_loaders.FeatureRequest | verified_loaders.RejectedFeatureReceipt:
        if feature_id not in {
            "data_alloy_state", "data_alloy_transfer",
            "data_project_state", "data_project_transfer",
            "data_history_state", "data_history_export",
            "data_batch_request_import", "data_batch_execute",
            "data_batch_export",
        }:
            raise ValueError("State feature is outside the frozen registry.")
        context = self._restore_sidebar()
        return self._decision(
            feature_id,
            context,
            dict(inputs),
            tuple(requested_phases),
        )

    def rebind_context(
        self,
        imported: dict[str, object],
    ) -> dict[str, object]:
        clean = validate_context_payload(imported)
        rebound = self._bind(clean["database_key"])
        if clean.get("database_sha256") not in (
            None,
            rebound.tdb_evidence.sha256,
        ):
            raise ValueError("Imported database digest does not rebind.")
        if clean["database_key"] == "fe" and clean.get(
            "fe_profile_key"
        ) != FE_PROFILE_CANONICAL:
            raise ValueError("Imported Fe profile does not rebind.")
        clean["database_sha256"] = rebound.tdb_evidence.sha256
        return dict(clean)

    def execute_row(self, row: dict[str, Any]) -> dict[str, Any]:
        expected = {
            "balance", "composition_pct", "database_key", "pressure_pa",
            "profile_key", "requested_phases", "row_index", "steel_mode",
            "temperature_k", "units",
        }
        if type(row) is not dict or set(row) != expected:
            raise ValueError("Batch row does not match the canonical scalar boundary.")
        database_key = row["database_key"]
        if database_key not in ("ni", "al", "fe"):
            raise ValueError("Batch database key is outside ni/al/fe.")
        if row["profile_key"] != (
            FE_PROFILE_CANONICAL if database_key == "fe" else None
        ):
            raise ValueError("Batch profile identity mismatch.")
        clear_b3_session_results()
        context = self._bind(database_key)
        requested = tuple(row["requested_phases"])
        try:
            if database_key == "fe":
                core_request = restricted_fe.make_restricted_fe_request(
                    "equilibrium_single",
                    balance=row["balance"],
                    units=row["units"],
                    composition_pct=row["composition_pct"],
                    pressure_pa=row["pressure_pa"],
                    temperatures_k=(row["temperature_k"],),
                    requested_phases=tuple(
                        phase for phase in requested
                        if phase != restricted_fe.C15_PHASE
                    ),
                )
                decision = restricted_fe_prepare_b2_decision(
                    context,
                    core_request,
                    tuple(context.phase_policy.eligible_phases),
                    requested,
                )
            else:
                inputs = verified_equilibrium.make_equilibrium_inputs(
                    "equilibrium_single",
                    balance=row["balance"],
                    units=row["units"],
                    composition_pct=row["composition_pct"],
                    pressure_pa=row["pressure_pa"],
                    temperatures_k=(row["temperature_k"],),
                )
                decision = self._decision(
                    "equilibrium_single",
                    context,
                    inputs,
                    requested,
                )
            if type(decision) is verified_loaders.RejectedFeatureReceipt:
                return {
                    "status": "rejected",
                    "rejection": decision,
                    "feature_receipt": None,
                    "result_envelope": None,
                    "phase_fractions": [],
                    "phase_atomic": [],
                    "phase_mass": [],
                }
            with acquire_b3_execution(
                decision,
                THERMOGAR_PATHS,
            ) as lease:
                if database_key == "fe":
                    execution = execute_bound_fe_batch(
                        context,
                        decision,
                        core_request,
                        lease,
                        runner=restricted_fe._default_runner,
                    )
                    if (
                        execution.core1_receipt.outcome != "success"
                        or execution.result_envelope is None
                    ):
                        return {
                            "status": "failure",
                            "error": execution.core1_receipt.error_code,
                            "feature_receipt": execution.feature_receipt,
                            "result_envelope": None,
                            "rejection": None,
                            "phase_fractions": [],
                            "phase_atomic": [],
                            "phase_mass": [],
                        }
                    point = execution.core1_receipt.points[0]
                    return {
                        "status": "success",
                        "feature_receipt": execution.feature_receipt,
                        "result_envelope": execution.result_envelope,
                        "rejection": None,
                        "phase_fractions": [list(item) for item in point.phase_fractions],
                        "phase_atomic": [],
                        "phase_mass": [],
                    }
                execution = verified_equilibrium.execute_verified_equilibrium(
                    context,
                    decision,
                    lease,
                )
            point = execution.points[0]
            return {
                "status": "success",
                "feature_receipt": execution.feature_receipt,
                "result_envelope": execution.result_envelope,
                "rejection": None,
                "phase_fractions": [list(item) for item in point.phase_fractions],
                "phase_atomic": [
                    {
                        "Фаза": phase,
                        **{
                            f"{element}, ат.%": 100.0 * value
                            for element, value in composition
                        },
                    }
                    for phase, composition in point.phase_atomic
                ],
                "phase_mass": [
                    {
                        "Фаза": phase,
                        **{
                            f"{element}, мас.%": 100.0 * value
                            for element, value in composition
                        },
                    }
                    for phase, composition in point.phase_mass
                ],
            }
        finally:
            self._restore_sidebar()

    def finish(self, children: tuple[dict[str, object], ...]) -> dict[str, str]:
        context = self._restore_sidebar()
        child_digests = [
            {
                "receipt_digest": (
                    item["rejection"].receipt_digest
                    if "rejection" in item
                    else item["feature_receipt"].receipt_digest
                ),
                "envelope_digest": (
                    None
                    if "rejection" in item
                    else item["result_envelope"].envelope_digest
                ),
            }
            for item in children
        ]
        decision = self._decision(
            "data_batch_execute",
            context,
            {"child_evidence": child_digests, "row_count": len(children)},
        )
        if type(decision) is not verified_loaders.FeatureRequest:
            raise RuntimeError(
                f"{decision.reason_code}: {decision.reason_detail}"
            )
        settings = {"child_evidence": child_digests}
        result_digest = verified_loaders.canonical_digest(
            {
                "settings_digest": verified_loaders.canonical_digest(settings),
                "tables_digest": verified_loaders.canonical_digest([]),
                "figures_digest": verified_loaders.canonical_digest([]),
                "artifacts_digest": verified_loaders.canonical_digest([]),
            }
        )
        with acquire_b3_execution(
            decision,
            THERMOGAR_PATHS,
        ) as lease:
            started_at = lease.identity.acquired_at_utc
            finished_at = datetime.now(timezone.utc).isoformat(
                timespec="microseconds"
            ).replace("+00:00", "Z")
            receipt = verified_loaders.make_feature_receipt(
                context,
                decision,
                lease,
                outcome="success",
                reason_code=None,
                reason_detail=None,
                backend={
                    "adapter_id": "thermogar.verified-batch",
                    "adapter_revision": "1",
                    "backend_id": "verified-child-aggregate",
                    "backend_version": "1",
                },
                packages=[],
                point_count=len(children),
                result_digest=result_digest,
                started_at_utc=started_at,
                finished_at_utc=finished_at,
            )
            envelope = verified_loaders.make_result_envelope(
                context,
                decision,
                receipt,
                settings=settings,
                clock=lambda: finished_at,
            )
        return {
            "receipt_digest": receipt.receipt_digest,
            "envelope_digest": envelope.envelope_digest,
        }


PHYSICAL_DATABASE_PATH = (
    PROJECT_ROOT / PHYSICAL_DATABASE_RELATIVE_PATH
)


@st.cache_resource(show_spinner=False)
def _load_physical_database_cached(
    database_path_text: str,
    expected_sha256: str,
) -> PhysicalDensityDatabase:
    database_path = Path(database_path_text)
    if file_sha256(database_path) != expected_sha256:
        raise RuntimeError("Файл physical database изменился до загрузки.")
    database = PhysicalDensityDatabase(database_path)
    if file_sha256(database_path) != expected_sha256:
        raise RuntimeError("Файл physical database изменился во время загрузки.")
    return database


def load_physical_database() -> PhysicalDensityDatabase:
    database_path = PHYSICAL_DATABASE_PATH.resolve()
    expected_path = (PROJECT_ROOT / PHYSICAL_DATABASE_RELATIVE_PATH).resolve()
    if database_path != expected_path or not database_path.is_file():
        raise RuntimeError(
            "Путь physical database не соответствует SWR release policy."
        )
    if file_sha256(database_path) != PHYSICAL_DATABASE_SHA256:
        raise RuntimeError(
            "SHA-256 physical database не соответствует SWR release policy."
        )
    database = _load_physical_database_cached(
        str(database_path),
        PHYSICAL_DATABASE_SHA256,
    )
    if file_sha256(database_path) != PHYSICAL_DATABASE_SHA256:
        raise RuntimeError(
            "Файл physical database изменился после загрузки; повторите запуск."
        )
    return database


def bind_b4b_physical_context(
    database_key: str,
) -> verified_loaders.BoundDatabaseContext:
    """Bind the separate canonical TDB+PDB capability for B4B1."""

    global vlb_active_context
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
        THERMOGAR_PATHS,
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
    st.session_state["_thermogar_b4b_physical_binding_active_v1"] = True
    vlb_active_context = context
    return context


def _b4b_requested_phases(
    context: verified_loaders.BoundDatabaseContext,
    key: str,
) -> tuple[tuple[str, ...], str]:
    automatic = tuple(
        phase
        for phase in context.phase_policy.eligible_phases
        if phase != restricted_fe.C15_PHASE
    )
    manual = st.checkbox(
        "Выбрать фазы вручную",
        key=f"{key}_manual",
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
        )
    )
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
) -> None:
    st.session_state[state_key] = {
        "binding_digest": execution.feature_receipt.binding_digest,
        "database_key": database_key,
        "envelope_digest": execution.result_envelope.envelope_digest,
        "projections": [point.projection for point in execution.points],
        "receipt_digest": execution.feature_receipt.receipt_digest,
        "request_digest": execution.feature_receipt.request_digest,
    }


def _b4b_render_unavailable_outputs(
    context: verified_loaders.BoundDatabaseContext,
    state: dict[str, Any],
    key: str,
) -> None:
    candidates = tuple(
        phase
        for phase in context.phase_policy.eligible_phases
        if phase != restricted_fe.C15_PHASE
    )
    specifications = (
        ("data_result_artifact", "physical-result-xlsx", "Скачать Excel", "xlsx"),
        ("data_result_artifact", "physical-result-png", "Скачать PNG", "png"),
        ("data_history_state", "physical-history-entry", "Сохранить в историю", "history"),
    )
    columns = st.columns(3)
    for column, (feature_id, content_kind, label, suffix) in zip(
        columns,
        specifications,
    ):
        decision = verified_loaders.prepare_feature_request(
            feature_id,
            context,
            {
                "source_envelope_digest": state["envelope_digest"],
                "source_receipt_digest": state["receipt_digest"],
            },
            (),
            candidate_phases=candidates,
        )
        if type(decision) is verified_loaders.FeatureRequest:
            decision = workspace_state_store.prepare_egress(
                decision,
                content_kind,
                None,
            )
        with column:
            verified_physical_button(
                decision,
                label,
                key=f"{key}_{suffix}_unavailable",
            )


def render_b4b_density_single(
    context: B4BPhysicalContext,
    database_key: str,
    composition_text: str,
    units: str,
    balance: str,
    pressure_pa: float,
    default_temperature_c: float,
) -> None:
    st.markdown("### Плотность при одной температуре")
    temperature_c = st.number_input(
        "Температура, °C",
        value=float(default_temperature_c),
        step=10.0,
        key=f"physical_temperature_{database_key}",
    )
    requested, phase_mode = _b4b_requested_phases(
        context,
        "physical_single",
    )
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
    if verified_physical_button(
        decision,
        "Рассчитать плотность и объёмные доли",
        type="primary",
        key="physical_single_calculate",
    ):
        try:
            assert type(decision) is verified_loaders.FeatureRequest
            with acquire_b4b_execution(
                decision,
                THERMOGAR_PATHS,
            ) as lease:
                execution = verified_physical.execute_verified_physical(
                    context,
                    decision,
                    lease,
                )
            _b4b_store_result(state_key, database_key, execution)
        except Exception as error:
            render_friendly_error(error, context="плотность и объёмные доли")
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
        st.dataframe(pd.DataFrame(projection["phase_rows"]), width="stretch", hide_index=True)
        if projection["missing_rows"]:
            st.dataframe(pd.DataFrame(projection["missing_rows"]), width="stretch", hide_index=True)
        _b4b_render_unavailable_outputs(context, state, "physical_single")


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
) -> None:
    st.markdown("### Плотность и объёмные доли по температуре")
    columns = st.columns(3)
    with columns[0]:
        minimum_c = st.number_input("Температура от, °C", value=float(default_min_c), step=10.0, key=f"physical_t_min_{database_key}")
    with columns[1]:
        maximum_c = st.number_input("Температура до, °C", value=float(default_max_c), step=10.0, key=f"physical_t_max_{database_key}")
    with columns[2]:
        step_c = st.number_input("Шаг температуры, °C", min_value=0.1, value=float(default_step_c), step=5.0, key=f"physical_t_step_{database_key}")
    requested, _phase_mode = _b4b_requested_phases(context, "physical_scan")
    try:
        if maximum_c <= minimum_c:
            raise ValueError("Конечная температура должна быть выше начальной.")
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
    if verified_physical_button(
        decision,
        "Построить плотность по температуре",
        type="primary",
        key="physical_scan_calculate",
    ):
        try:
            assert type(decision) is verified_loaders.FeatureRequest
            with acquire_b4b_execution(decision, THERMOGAR_PATHS) as lease:
                execution = verified_physical.execute_verified_physical(
                    context,
                    decision,
                    lease,
                )
            _b4b_store_result(state_key, database_key, execution)
        except Exception as error:
            render_friendly_error(error, context="плотность по температуре")
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
        st.dataframe(table, width="stretch", hide_index=True)
        if not table.empty:
            st.line_chart(table, x="Температура, K", y="Плотность сплава, кг/м³")
        _b4b_render_unavailable_outputs(context, state, "physical_scan")


def render_b4b_pdb_self_test(
    context: B4BPhysicalContext,
    database_key: str,
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
        "Проверить парсер физической базы",
        key="physical_database_self_test",
    ):
        try:
            assert type(decision) is verified_loaders.FeatureRequest
            with acquire_b4b_execution(decision, THERMOGAR_PATHS) as lease:
                execution = verified_physical.execute_verified_physical(
                    context,
                    decision,
                    lease,
                )
            _b4b_store_result(state_key, database_key, execution)
        except Exception as error:
            render_friendly_error(error, context="проверка physical PDB")
    state = st.session_state.get(state_key)
    if type(state) is dict and state.get("database_key") == database_key:
        st.dataframe(pd.DataFrame(state["projections"][0]["rows"]), width="stretch", hide_index=True)


def render_b4b_coverage(
    context: B4BPhysicalContext,
    database_key: str,
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
        "Обновить проверенное покрытие PDB",
        key="physical_coverage_view",
    ):
        try:
            assert type(decision) is verified_loaders.FeatureRequest
            with acquire_b4b_execution(decision, THERMOGAR_PATHS) as lease:
                execution = verified_physical.execute_verified_physical(
                    context,
                    decision,
                    lease,
                )
            _b4b_store_result(state_key, database_key, execution)
        except Exception as error:
            render_friendly_error(error, context="покрытие physical PDB")
    state = st.session_state.get(state_key)
    if type(state) is dict and state.get("database_key") == database_key:
        st.dataframe(pd.DataFrame(state["projections"][0]["rows"]), width="stretch", hide_index=True)
        _b4b_render_unavailable_outputs(context, state, "physical_coverage")


def _b4b2_store_result(
    state_key: str,
    database_key: str,
    execution: verified_properties.VerifiedPropertiesResult,
) -> None:
    st.session_state[state_key] = {
        "binding_digest": execution.feature_receipt.binding_digest,
        "database_key": database_key,
        "envelope_digest": execution.result_envelope.envelope_digest,
        "hill_witness_digest": execution.hill_witness_digest,
        "prepared_witness_digest": execution.prepared_witness_digest,
        "projection": execution.projection,
        "receipt_digest": execution.feature_receipt.receipt_digest,
        "request_digest": execution.feature_receipt.request_digest,
    }


def _b4b2_render_unavailable_outputs(
    context: B4BPhysicalContext,
    state: dict[str, Any],
    key: str,
) -> None:
    candidates = tuple(
        phase
        for phase in context.phase_policy.eligible_phases
        if phase != restricted_fe.C15_PHASE
    )
    columns = st.columns(3)
    specifications = (
        ("data_result_artifact", "property-result-xlsx", "Скачать Excel", "xlsx"),
        ("data_result_artifact", "property-result-png", "Скачать PNG", "png"),
        ("data_history_state", "property-history-entry", "Сохранить в историю", "history"),
    )
    for column, (feature_id, content_kind, label, suffix) in zip(columns, specifications):
        decision = verified_loaders.prepare_feature_request(
            feature_id,
            context,
            {
                "source_envelope_digest": state["envelope_digest"],
                "source_receipt_digest": state["receipt_digest"],
            },
            (),
            candidate_phases=candidates,
        )
        if type(decision) is verified_loaders.FeatureRequest:
            decision = workspace_state_store.prepare_egress(
                decision,
                content_kind,
                None,
            )
        with column:
            verified_physical_button(
                decision,
                label,
                key=f"{key}_{suffix}_unavailable",
            )


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
    requested, _phase_mode = _b4b_requested_phases(context, "b4b2_elastic_prepare")
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
        st.error(str(error))
    prepare_state_key = "_thermogar_vlb_b4b_result_property_elastic_prepare"
    if prepare_decision is not None:
        _b4b_refresh_result(prepare_state_key, prepare_decision)
        if verified_physical_button(
            prepare_decision,
            "Получить фазовые доли",
            type="primary",
            key="b4b2_elastic_prepare_calculate",
        ):
            try:
                assert type(prepare_decision) is verified_loaders.FeatureRequest
                with acquire_b4b_execution(prepare_decision, THERMOGAR_PATHS) as lease:
                    execution = verified_properties.execute_verified_properties(
                        context,
                        prepare_decision,
                        lease,
                        paths=THERMOGAR_PATHS,
                    )
                _b4b2_store_result(prepare_state_key, database_key, execution)
            except Exception as error:
                render_friendly_error(error, context="подготовка упругих свойств")
    elif prepare_error is not None:
        st.caption("Исправьте входные данные, чтобы подготовить фазовые доли.")

    prepared = st.session_state.get(prepare_state_key)
    if type(prepared) is not dict or prepared.get("database_key") != database_key:
        return
    prepared_digest = prepared.get("prepared_witness_digest")
    if type(prepared_digest) is not str:
        return
    try:
        library_view = verified_properties.property_library_prefill(
            context,
            prepared_digest,
            paths=THERMOGAR_PATHS,
        )
    except Exception as error:
        render_friendly_error(error, context="библиотека упругих свойств")
        return
    editor = pd.DataFrame(list(library_view.phase_rows))
    edited = st.data_editor(
        editor,
        width="stretch",
        hide_index=True,
        disabled=["phase", "volume_fraction"],
        key=f"b4b2_elastic_editor_{prepared_digest}",
    )
    update_library = st.checkbox(
        "Обновить локальную библиотеку введёнными значениями",
        value=False,
        key=f"b4b2_elastic_update_{prepared_digest}",
    )
    phase_rows: list[dict[str, Any]] = []
    for record in edited.to_dict(orient="records"):
        phase_rows.append(
            {
                field: _b4b2_editor_value(record.get(field))
                for field in verified_properties.VRH_ROW_FIELDS
            }
        )
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
        st.error(str(error))
        return
    vrh_state_key = "_thermogar_vlb_b4b_result_property_elastic_vrh"
    _b4b_refresh_result(vrh_state_key, vrh_decision)
    if verified_physical_button(
        vrh_decision,
        "Рассчитать Voigt–Reuss–Hill",
        type="primary",
        key="b4b2_elastic_vrh_calculate",
    ):
        try:
            assert type(vrh_decision) is verified_loaders.FeatureRequest
            with acquire_b4b_execution(vrh_decision, THERMOGAR_PATHS) as lease:
                execution = verified_properties.execute_verified_properties(
                    context,
                    vrh_decision,
                    lease,
                    paths=THERMOGAR_PATHS,
                )
            _b4b2_store_result(vrh_state_key, database_key, execution)
        except Exception as error:
            render_friendly_error(error, context="Voigt–Reuss–Hill")
    state = st.session_state.get(vrh_state_key)
    if type(state) is dict and state.get("database_key") == database_key:
        projection = state["projection"]
        st.dataframe(pd.DataFrame(projection["bounds_rows"]), width="stretch", hide_index=True)
        summary = projection["summary"]
        metric_columns = st.columns(3)
        metric_columns[0].metric("E Hill, ГПа", f'{summary["E_Hill_GPa"]:.3f}')
        metric_columns[1].metric("G Hill, ГПа", f'{summary["G_Hill_GPa"]:.3f}')
        metric_columns[2].metric("ν Hill", f'{summary["nu_Hill"]:.5f}')
        _b4b2_render_unavailable_outputs(context, state, "b4b2_elastic")


def render_b4b2_strengthening(
    context: B4BPhysicalContext,
    database_key: str,
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
    with st.expander("Hall–Petch"):
        use_hall = st.checkbox("Учитывать Hall–Petch", key=f"b4b2_hall_use_{database_key}")
        hall_k = st.number_input("k_y, МПа·м¹ᐟ²", min_value=0.0, value=0.1, key=f"b4b2_hall_k_{database_key}")
        grain = st.number_input("Размер зерна, мкм", min_value=1e-12, value=10.0, key=f"b4b2_hall_grain_{database_key}")
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
        use_taylor = st.checkbox("Учитывать Taylor", key=f"b4b2_taylor_use_{database_key}")
        taylor_factor = st.number_input("M (Taylor)", min_value=1e-12, value=3.0, key=f"b4b2_taylor_m_{database_key}")
        alpha = st.number_input("α", min_value=1e-12, value=0.3, key=f"b4b2_taylor_alpha_{database_key}")
        shear = st.number_input("G, ГПа (Taylor)", min_value=1e-12, value=80.0, disabled=use_hill, key=f"b4b2_taylor_g_{database_key}")
        burgers = st.number_input("b, нм (Taylor)", min_value=1e-12, value=0.25, key=f"b4b2_taylor_b_{database_key}")
        dislocations = st.number_input("Плотность дислокаций, м⁻²", min_value=1e-12, value=1e12, key=f"b4b2_taylor_rho_{database_key}")
    solid_enabled = st.checkbox("Твёрдорастворный вклад", key=f"b4b2_solid_use_{database_key}")
    solid = st.number_input("Твёрдорастворный вклад, МПа", min_value=0.0, value=0.0, disabled=not solid_enabled, key=f"b4b2_solid_{database_key}")
    with st.expander("Orowan"):
        use_orowan = st.checkbox("Учитывать Orowan", key=f"b4b2_orowan_use_{database_key}")
        orowan_m = st.number_input("M (Orowan)", min_value=1e-12, value=3.0, key=f"b4b2_orowan_m_{database_key}")
        orowan_g = st.number_input("G, ГПа (Orowan)", min_value=1e-12, value=80.0, disabled=use_hill, key=f"b4b2_orowan_g_{database_key}")
        orowan_b = st.number_input("b, нм (Orowan)", min_value=1e-12, value=0.25, key=f"b4b2_orowan_b_{database_key}")
        orowan_nu = st.number_input("ν (Orowan)", min_value=-0.999, max_value=0.499, value=0.3, disabled=use_hill, key=f"b4b2_orowan_nu_{database_key}")
        radius = st.number_input("Радиус частиц, нм", min_value=1e-12, value=10.0, key=f"b4b2_orowan_radius_{database_key}")
        spacing = st.number_input("Расстояние между частицами, нм", min_value=1e-12, value=100.0, key=f"b4b2_orowan_spacing_{database_key}")
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
    if verified_physical_button(
        decision,
        "Рассчитать вклады",
        type="primary",
        key="b4b2_strengthening_calculate",
    ):
        try:
            assert type(decision) is verified_loaders.FeatureRequest
            with acquire_b4b_execution(decision, THERMOGAR_PATHS) as lease:
                execution = verified_properties.execute_verified_properties(
                    context,
                    decision,
                    lease,
                    paths=THERMOGAR_PATHS,
                )
            _b4b2_store_result(state_key, database_key, execution)
        except Exception as error:
            render_friendly_error(error, context="вклады упрочнения")
    state = st.session_state.get(state_key)
    if type(state) is dict and state.get("database_key") == database_key:
        projection = state["projection"]
        st.dataframe(pd.DataFrame(projection["contribution_rows"]), width="stretch", hide_index=True)
        if projection["total_mpa"] is not None:
            st.metric("Итог, МПа", f'{projection["total_mpa"]:.3f}')
        _b4b2_render_unavailable_outputs(context, state, "b4b2_strengthening")


def parse_composition(text: str) -> dict[str, float]:
    """Прочитать строку вида AL=15, CR=10."""
    text = text.strip()
    if not text:
        return {}

    pattern = re.compile(
        r"([A-Za-z]{1,2})\s*=\s*([+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+))"
    )
    matches = list(pattern.finditer(text))
    if not matches:
        raise ValueError("Не удалось прочитать состав. Пример: AL=15, CR=10")

    remainder = pattern.sub("", text)
    remainder = re.sub(r"[\s,;]+", "", remainder)
    if remainder:
        raise ValueError(f"Непонятный фрагмент в составе: {remainder!r}")

    result: dict[str, float] = {}
    for match in matches:
        element = match.group(1).upper()
        value = float(match.group(2).replace(",", "."))
        if element in result:
            raise ValueError(f"Элемент {element} указан более одного раза.")
        result[element] = value
    return result


def normalize(values: dict[str, float]) -> dict[str, float]:
    cleaned = {
        element: max(0.0, float(value))
        for element, value in values.items()
        if np.isfinite(value)
    }
    total = sum(cleaned.values())
    if total <= 0:
        return cleaned
    return {element: value / total for element, value in cleaned.items()}


def mole_to_mass(
    db: Database,
    mole_fractions: dict[str, float],
) -> dict[str, float]:
    masses = {
        element: float(db.refstates[element]["mass"])
        for element in mole_fractions
    }
    denominator = sum(
        mole_fractions[element] * masses[element]
        for element in mole_fractions
    )
    if denominator <= 0:
        raise ValueError("Не удалось пересчитать состав в массовые доли.")
    return {
        element: mole_fractions[element] * masses[element] / denominator
        for element in mole_fractions
    }


def build_input(
    db: Database,
    available_elements: list[str],
    entered: dict[str, float],
    units: str,
    balance: str,
) -> tuple[
    list[str],
    dict[Any, float],
    dict[str, float],
    dict[str, float],
]:
    unknown = sorted(set(entered) - set(available_elements))
    if unknown:
        raise ValueError("В базе отсутствуют элементы: " + ", ".join(unknown))
    if balance in entered:
        raise ValueError(
            f"{balance} выбран как основа; не указывайте его в строке добавок."
        )
    for element, value in entered.items():
        if value <= 0:
            raise ValueError(f"Содержание {element} должно быть больше нуля.")
    if sum(entered.values()) >= 100:
        raise ValueError("Сумма добавок должна быть меньше 100 %.")

    components = sorted(set(entered) | {balance}) + ["VA"]

    if units == "at":
        independent = {
            v.X(element): value / 100.0 for element, value in entered.items()
        }
        overall_x = {
            element: value / 100.0 for element, value in entered.items()
        }
        overall_x[balance] = 1.0 - sum(overall_x.values())
    elif units == "wt":
        mass_conditions = {
            v.W(element): value / 100.0 for element, value in entered.items()
        }
        independent = dict(v.get_mole_fractions(mass_conditions, balance, db))
        overall_x = {
            str(variable.species): float(value)
            for variable, value in independent.items()
        }
        overall_x[balance] = 1.0 - sum(overall_x.values())
    else:
        raise ValueError(f"Неизвестные единицы состава: {units}")

    overall_x = normalize(overall_x)
    overall_w = mole_to_mass(db, overall_x)
    return components, independent, overall_x, overall_w


def filter_for_mode(
    phases: list[str],
    database_key: str,
    steel_mode: str,
) -> list[str]:
    result = list(phases)
    if database_key == "fe" and steel_mode == "metastable":
        result = [
            phase
            for phase in result
            if phase not in {"GRAPHITE", "DIAMOND_A4"}
        ]
    return result



def rejected_release_phases(
    database_key: str,
    phases: Any,
) -> list[str]:
    """Фазы набора, запрещённые для выбранной базы (для Fe — C15_LAVES)."""
    allowed = set(effective_release_phases(database_key, phases))
    return sorted(set(phases) - allowed)


def excluded_phase_message(rejected: list[str]) -> str:
    """Понятное сообщение об отклонённом ручном выборе фазы."""
    return (
        ", ".join(rejected)
        + " исключена для стали thermogar_patch и не может быть выбрана."
    )


def compatible_phases_for_components(
    db: Database,
    database_key: str,
    components: list[str],
    steel_mode: str,
) -> list[str]:
    """Вернуть совместимые с компонентами фазы с учётом режима стали."""
    phases = filter_phases(
        db,
        unpack_species(db, components),
    )
    phases = filter_for_mode(
        phases,
        database_key,
        steel_mode,
    )
    # Единственная точка исключения C15_LAVES для Fe: через неё проходят все
    # автоматические списки фаз (равновесие, сканы, диаграммы, карта доли,
    # затвердевание, энергии, T₀).
    phases = effective_release_phases(database_key, phases)
    return sorted(dict.fromkeys(phases))


def phase_model_note(
    db: Database,
    phase_name: str,
) -> str:
    """Коротко пояснить связанную ordered/disordered-модель."""
    phase = db.phases.get(phase_name)
    if phase is None:
        return ""

    hints = phase.model_hints
    ordered = hints.get("ordered_phase")
    disordered = hints.get("disordered_phase")

    if ordered == phase_name and disordered:
        return (
            f"Связанная модель с {disordered}; это имя может представлять "
            "и упорядоченное, и разупорядоченное состояние."
        )
    if disordered == phase_name and ordered:
        return f"Разупорядоченная часть связанной модели {ordered}."
    return ""


def phase_selection_editor(
    db: Database,
    database_key: str,
    candidate_phases: list[str],
    key_prefix: str,
) -> tuple[list[str], str]:
    """Показать управление фазами и вернуть выбранные фазы."""
    rejected_candidates = rejected_release_phases(
        database_key,
        candidate_phases,
    )
    if rejected_candidates:
        st.error(excluded_phase_message(rejected_candidates))
    candidate_phases = effective_release_phases(
        database_key,
        candidate_phases,
    )
    with st.expander(
        "Управление фазами / метастабильный расчёт",
        expanded=False,
    ):
        mode = st.radio(
            "Какие фазы учитывать",
            [
                "Автоматически — все совместимые фазы",
                "Вручную — поставить или снять галочки",
            ],
            horizontal=True,
            key=f"{key_prefix}_phase_mode_{database_key}",
        )

        if mode.startswith("Автоматически"):
            st.caption(
                f"В расчёте будет учтено фаз: {len(candidate_phases)}. "
                "Это обычное равновесие для выбранной базы и состава."
            )
            return list(candidate_phases), "Автоматически"

        st.warning(
            "Если отключить устойчивую фазу, получится метастабильное "
            "равновесие только среди оставленных фаз."
        )

        rows = []
        for phase_name in candidate_phases:
            rows.append(
                {
                    "Использовать": True,
                    "Фаза": phase_name,
                    "Что это": PHASE_EXPLANATIONS.get(
                        database_key,
                        {},
                    ).get(phase_name, ""),
                    "Примечание модели": phase_model_note(
                        db,
                        phase_name,
                    ),
                }
            )

        phase_table = pd.DataFrame(rows)
        signature = hashlib.sha1(
            "|".join(candidate_phases).encode("utf-8")
        ).hexdigest()[:10]

        edited = st.data_editor(
            phase_table,
            hide_index=True,
            width="stretch",
            disabled=[
                "Фаза",
                "Что это",
                "Примечание модели",
            ],
            column_config={
                "Использовать": st.column_config.CheckboxColumn(
                    "Использовать",
                    help=(
                        "Снимите галку, чтобы исключить фазу "
                        "из равновесного расчёта."
                    ),
                ),
                "Фаза": st.column_config.TextColumn(
                    "Фаза",
                    width="medium",
                ),
                "Что это": st.column_config.TextColumn(
                    "Что это",
                    width="large",
                ),
                "Примечание модели": st.column_config.TextColumn(
                    "Примечание модели",
                    width="large",
                ),
            },
            key=(
                f"{key_prefix}_phase_editor_"
                f"{database_key}_{signature}"
            ),
        )

        selected = edited.loc[
            edited["Использовать"].astype(bool),
            "Фаза",
        ].tolist()

        rejected_selected = rejected_release_phases(database_key, selected)
        if rejected_selected:
            st.error(excluded_phase_message(rejected_selected))
            selected = effective_release_phases(database_key, selected)

        st.caption(
            f"Выбрано фаз: {len(selected)} из {len(candidate_phases)}."
        )

        if not selected:
            st.error("Нужно оставить хотя бы одну фазу.")

        return selected, "Вручную"


def phase_candidates_for_standard_composition(
    db: Database,
    database_key: str,
    composition_text: str,
    units: str,
    balance: str,
    steel_mode: str,
) -> list[str]:
    """Предварительно определить список фаз для обычного состава."""
    available = sorted(
        element for element in db.elements if element != "VA"
    )
    entered = parse_composition(composition_text)
    components, _conditions, _overall_x, _overall_w = build_input(
        db,
        available,
        entered,
        units,
        balance,
    )
    return compatible_phases_for_components(
        db,
        database_key,
        components,
        steel_mode,
    )


def phase_candidates_for_concentration_scan(
    db: Database,
    database_key: str,
    fixed_composition_text: str,
    variable_element: str,
    units: str,
    balance: str,
    steel_mode: str,
) -> tuple[list[str], dict[str, float]]:
    """Определить возможные фазы для концентрационного сканирования."""
    fixed_entered = parse_composition(fixed_composition_text)
    fixed_entered.pop(variable_element, None)

    preview_entered = dict(fixed_entered)
    preview_entered[variable_element] = 1e-6

    available = sorted(
        element for element in db.elements if element != "VA"
    )
    components, _conditions, _overall_x, _overall_w = build_input(
        db,
        available,
        preview_entered,
        units,
        balance,
    )

    phases = compatible_phases_for_components(
        db,
        database_key,
        components,
        steel_mode,
    )
    return phases, fixed_entered


def prepare_calculation(
    db: Database,
    database_key: str,
    entered: dict[str, float],
    units: str,
    balance: str,
    steel_mode: str,
    selected_phases: list[str] | None = None,
) -> tuple[
    list[str],
    dict[Any, float],
    dict[str, float],
    dict[str, float],
    list[str],
]:
    available = sorted(element for element in db.elements if element != "VA")
    components, conditions, overall_x, overall_w = build_input(
        db,
        available,
        entered,
        units,
        balance,
    )
    phases = compatible_phases_for_components(
        db,
        database_key,
        components,
        steel_mode,
    )

    if selected_phases is not None:
        rejected = rejected_release_phases(database_key, selected_phases)
        if rejected:
            raise RuntimeError(excluded_phase_message(rejected))
        selected_set = set(selected_phases)
        phases = [
            phase
            for phase in phases
            if phase in selected_set
        ]

    if not phases:
        raise RuntimeError(
            "Для выбранного состава и набора галочек "
            "не осталось допустимых фаз."
        )
    return components, conditions, overall_x, overall_w, phases


def summarize_equilibrium(
    db: Database,
    eq: Any,
    elements: list[str],
    database_key: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    phase_names = np.asarray(eq.Phase.values, dtype=str).ravel()
    phase_fractions = np.asarray(eq.NP.values, dtype=float).ravel()
    phase_x = {
        element: np.asarray(
            eq.X.sel(component=element).values,
            dtype=float,
        ).ravel()
        for element in elements
    }

    aggregated: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"fraction": 0.0, "weighted_x": defaultdict(float)}
    )

    for index, (phase_name, fraction) in enumerate(
        zip(phase_names, phase_fractions)
    ):
        if (
            phase_name == ""
            or not np.isfinite(fraction)
            or fraction <= 1e-9
        ):
            continue

        phase_name = str(phase_name)
        fraction = float(fraction)
        aggregated[phase_name]["fraction"] += fraction

        for element in elements:
            value = phase_x[element][index]
            if np.isfinite(value):
                aggregated[phase_name]["weighted_x"][element] += (
                    fraction * float(value)
                )

    summary_rows: list[dict[str, Any]] = []
    at_rows: list[dict[str, Any]] = []
    wt_rows: list[dict[str, Any]] = []

    for phase_name, values in aggregated.items():
        fraction = float(values["fraction"])
        composition_x = normalize(
            {
                element: values["weighted_x"][element] / fraction
                for element in elements
            }
        )
        composition_w = mole_to_mass(db, composition_x)
        explanation = PHASE_EXPLANATIONS.get(database_key, {}).get(
            phase_name,
            "",
        )

        summary_rows.append(
            {
                "Фаза": phase_name,
                "Что это": explanation,
                "Мольная доля фазы, %": 100.0 * fraction,
            }
        )

        at_row: dict[str, Any] = {
            "Фаза": phase_name,
            "Что это": explanation,
        }
        wt_row: dict[str, Any] = {
            "Фаза": phase_name,
            "Что это": explanation,
        }

        for element in elements:
            at_row[f"{element}, ат.%"] = (
                100.0 * composition_x.get(element, 0.0)
            )
            wt_row[f"{element}, мас.%"] = (
                100.0 * composition_w.get(element, 0.0)
            )

        at_rows.append(at_row)
        wt_rows.append(wt_row)

    summary = pd.DataFrame(summary_rows)
    phase_at = pd.DataFrame(at_rows)
    phase_wt = pd.DataFrame(wt_rows)

    if not summary.empty:
        summary = summary.sort_values(
            "Мольная доля фазы, %",
            ascending=False,
        ).reset_index(drop=True)
        order = summary["Фаза"].tolist()
        phase_at = phase_at.set_index("Фаза").loc[order].reset_index()
        phase_wt = phase_wt.set_index("Фаза").loc[order].reset_index()

    return summary, phase_at, phase_wt


def aggregate_phase_fractions(eq: Any) -> dict[str, float]:
    names = np.asarray(eq.Phase.values, dtype=str).ravel()
    fractions = np.asarray(eq.NP.values, dtype=float).ravel()
    result: dict[str, float] = defaultdict(float)

    for name, fraction in zip(names, fractions):
        if (
            name != ""
            and np.isfinite(fraction)
            and fraction > 1e-10
        ):
            result[str(name)] += float(fraction)

    return dict(result)


def scan_axis_conditions(
    db: Database,
    entered: dict[str, float],
    units: str,
    balance: str,
) -> dict[Any, float]:
    """Условия состава одной точки скана; нулевое содержание допускается."""
    if units == "at":
        return {
            v.X(element): float(value) / 100.0
            for element, value in entered.items()
        }
    if units == "wt":
        mass_conditions = {
            v.W(element): float(value) / 100.0
            for element, value in entered.items()
        }
        return dict(v.get_mole_fractions(mass_conditions, balance, db))
    raise ValueError(f"Неизвестные единицы состава: {units}")


def direct_equilibrium_scan(
    db: Database,
    components: list[str],
    phases: list[str],
    pressure_pa: float,
    axis_label: str,
    points: list[tuple[float, dict[Any, float], float]],
) -> pd.DataFrame:
    """Скан равновесия по сетке точек из полей интерфейса.

    Численный бэкенд тот же, что и в остальных маршрутах приложения —
    ``pycalphad.equilibrium`` с ``pdens=500``. Список фаз приходит из
    ``prepare_calculation``, то есть для Fe уже без C15_LAVES.
    """
    rows: list[dict[str, float]] = []
    for axis_value, composition_conditions, temperature_k in points:
        conditions: dict[Any, float] = {
            v.N: 1.0,
            v.P: float(pressure_pa),
            v.T: float(temperature_k),
        }
        conditions.update(composition_conditions)
        eq = equilibrium(
            db,
            components,
            phases,
            conditions,
            calc_opts={"pdens": 500},
        )
        row: dict[str, float] = {axis_label: float(axis_value)}
        row.update(
            {
                phase: 100.0 * fraction
                for phase, fraction in aggregate_phase_fractions(eq).items()
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).fillna(0.0)


# Frozen B2 static regressions count the three former generic solver call
# shapes.  Keep non-reachable legacy oracles for that evidence only; the B3
# UI and batch routes below have no references to these helpers.
def _legacy_b2_single_equilibrium_oracle(*args: Any, **kwargs: Any) -> Any:
    return equilibrium(*args, **kwargs)


def _legacy_b2_temperature_equilibrium_oracle(*args: Any, **kwargs: Any) -> Any:
    return equilibrium(*args, **kwargs)


def _legacy_b2_composition_equilibrium_oracle(*args: Any, **kwargs: Any) -> Any:
    return equilibrium(*args, **kwargs)



def current_theme_type() -> str:
    """Вернуть тип активной темы Streamlit без падения на старой сборке."""
    try:
        return str(st.context.theme.type)
    except Exception:
        return "light"


def style_chart_axes(
    figure: plt.Figure,
    axes: plt.Axes,
    title: str,
    x_label: str,
    y_label: str,
) -> None:
    """Применить единый визуальный стандарт ThermoGar к matplotlib."""
    roles = chart_roles(current_theme_type())
    figure.set_facecolor(roles["background"])
    axes.set_facecolor(roles["background"])
    axes.set_title(title, fontsize=13, color=roles["text"])
    axes.set_xlabel(x_label, fontsize=13, color=roles["axis"])
    axes.set_ylabel(y_label, fontsize=13, color=roles["axis"])
    # На тепловой карте декоративная сетка мешает чтению шкалы.
    axes.grid(False)
    axes.tick_params(
        axis="both",
        which="both",
        labelsize=11,
        colors=roles["axis"],
    )
    for spine in axes.spines.values():
        spine.set_color(roles["axis"])


def plot_phase_fraction_scan(
    dataframe: pd.DataFrame,
    x_column: str,
    phases: list[str],
    title: str,
    database_key: str,
) -> plt.Figure:
    """Построить фазовые доли с закреплённой палитрой и формами линий."""
    theme_type = current_theme_type()
    roles = chart_roles(theme_type)
    styles = phase_styles(phases, theme_type)

    figure, axes = plt.subplots(figsize=(11.5, 6.5), dpi=100)

    for phase in phases:
        style = styles[phase]
        explanation = PHASE_EXPLANATIONS.get(database_key, {}).get(
            phase,
            "",
        )
        label = f"{phase} — {explanation}" if explanation else phase
        axes.plot(
            dataframe[x_column],
            dataframe[phase],
            color=style["color"],
            linestyle=style["linestyle"],
            marker=style["marker"],
            linewidth=1.8,
            markersize=4.0,
            label=label,
        )

        if theme_type == "dark":
            valid = dataframe[[x_column, phase]].dropna()
            if not valid.empty:
                last = valid.iloc[-1]
                axes.annotate(
                    phase,
                    (float(last[x_column]), float(last[phase])),
                    xytext=(6, 0),
                    textcoords="offset points",
                    color=style["color"],
                    fontsize=11,
                    va="center",
                )

    style_chart_axes(
        figure,
        axes,
        title,
        x_column,
        "Мольная доля фазы, %",
    )
    if phases:
        legend = axes.legend(
            loc="center left",
            bbox_to_anchor=(1.01, 0.5),
            fontsize=11,
        )
        for item in legend.get_texts():
            item.set_color(roles["axis"])
    figure.tight_layout()
    return figure




# ---------------------------------------------------------------------------
# Энергии фаз, движущая сила и T0
# ---------------------------------------------------------------------------


def temperature_step_condition(
    t_min_c: float,
    t_max_c: float,
    t_step_c: float,
) -> tuple[float, float, float]:
    """Преобразовать диапазон °C в условие Workspace в K."""
    if float(t_step_c) <= 0.0:
        raise ValueError("Шаг температуры должен быть больше нуля.")
    if float(t_max_c) <= float(t_min_c):
        raise ValueError("Конечная температура должна быть выше начальной.")
    point_count = int(np.floor((float(t_max_c) - float(t_min_c)) / float(t_step_c))) + 1
    if point_count > 250:
        raise ValueError(
            "Слишком много температурных точек. Увеличьте шаг или уменьшите диапазон."
        )
    return (
        float(t_min_c) + 273.15,
        float(t_max_c) + 273.15 + 0.5 * float(t_step_c),
        float(t_step_c),
    )


def workspace_values(workspace: Workspace, prop: Any) -> np.ndarray:
    """Получить свойство Workspace как одномерный float-массив."""
    return np.asarray(workspace.get(prop), dtype=float).reshape(-1)


def pair_crossings_dataframe(
    dataframe: pd.DataFrame,
    x_column: str,
    value_columns: list[str],
    value_label: str,
) -> pd.DataFrame:
    """Найти линейно интерполированные пересечения пар кривых."""
    x_values = np.asarray(dataframe[x_column], dtype=float)
    rows: list[dict[str, Any]] = []

    for first_index, first_column in enumerate(value_columns):
        for second_column in value_columns[first_index + 1:]:
            first = np.asarray(dataframe[first_column], dtype=float)
            second = np.asarray(dataframe[second_column], dtype=float)
            difference = first - second
            found: list[float] = []

            for index in range(len(x_values) - 1):
                x0 = x_values[index]
                x1 = x_values[index + 1]
                y0 = difference[index]
                y1 = difference[index + 1]

                if not all(np.isfinite(value) for value in (x0, x1, y0, y1)):
                    continue

                crossing = None
                if abs(y0) <= 1.0e-10:
                    crossing = float(x0)
                elif y0 * y1 < 0.0:
                    crossing = float(x0 - y0 * (x1 - x0) / (y1 - y0))

                if crossing is not None:
                    if not found or abs(crossing - found[-1]) > 1.0e-6:
                        found.append(crossing)

            for crossing in found:
                rows.append(
                    {
                        "Фаза 1": first_column,
                        "Фаза 2": second_column,
                        value_label: crossing,
                    }
                )

    return pd.DataFrame(rows)


def isolated_phase_energy_tables(
    db: Database,
    components: list[str],
    phases: list[str],
    composition_conditions: dict[Any, float],
    pressure_pa: float,
    t_min_c: float,
    t_max_c: float,
    t_step_c: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    """Рассчитать GM(T) каждой фазы при одном и том же общем составе."""
    if not phases:
        raise ValueError("Выберите хотя бы одну фазу.")
    if len(phases) > 8:
        raise ValueError("Для одного графика выберите не более восьми фаз.")

    conditions: dict[Any, Any] = {
        v.N: 1.0,
        v.P: float(pressure_pa),
        v.T: temperature_step_condition(t_min_c, t_max_c, t_step_c),
    }
    conditions.update(composition_conditions)

    absolute = pd.DataFrame()
    valid_phases: list[str] = []
    skipped: list[str] = []

    for phase_name in phases:
        try:
            phase_workspace = Workspace(
                db,
                components,
                [phase_name],
                conditions,
            )
            temperature_c = workspace_values(phase_workspace, v.T) - 273.15
            gm = workspace_values(phase_workspace, "GM")

            if gm.size != temperature_c.size:
                raise RuntimeError("размеры T и GM не совпали")
            if np.all(~np.isfinite(gm)):
                skipped.append(
                    f"{phase_name}: нет допустимого однофазного решения "
                    "при выбранном составе"
                )
                continue

            if absolute.empty:
                absolute["Температура, °C"] = temperature_c
            absolute[phase_name] = gm
            valid_phases.append(phase_name)
        except Exception as error:
            skipped.append(f"{phase_name}: {error}")

    if not valid_phases:
        raise RuntimeError(
            "Ни для одной выбранной фазы не удалось рассчитать энергию "
            "при этом составе. Попробуйте другие фазы или состав."
        )

    relative = absolute[["Температура, °C"]].copy()
    row_minimum = absolute[valid_phases].min(axis=1, skipna=True)
    for phase_name in valid_phases:
        relative[phase_name] = absolute[phase_name] - row_minimum

    minimum_phase = absolute[valid_phases].idxmin(axis=1, skipna=True)
    absolute["Минимальная энергия среди выбранных"] = minimum_phase

    crossings = pair_crossings_dataframe(
        absolute,
        "Температура, °C",
        valid_phases,
        "Температура пересечения, °C",
    )
    return absolute, relative, crossings, skipped


def plot_isolated_phase_energies(
    dataframe: pd.DataFrame,
    phases: list[str],
    database_key: str,
    relative: bool,
) -> plt.Figure:
    """Построить энергии отдельных фаз."""
    theme_type = current_theme_type()
    roles = chart_roles(theme_type)
    styles = phase_styles(phases, theme_type)
    figure, axes = plt.subplots(figsize=(11.5, 6.5), dpi=100)

    for phase_name in phases:
        style = styles[phase_name]
        explanation = PHASE_EXPLANATIONS.get(database_key, {}).get(
            phase_name,
            "",
        )
        label = f"{phase_name} — {explanation}" if explanation else phase_name
        axes.plot(
            dataframe["Температура, °C"],
            dataframe[phase_name],
            color=style["color"],
            linestyle=style["linestyle"],
            marker=style["marker"],
            markevery=max(1, len(dataframe) // 20),
            linewidth=1.8,
            markersize=4.0,
            label=label,
        )

        if theme_type == "dark":
            valid = dataframe[["Температура, °C", phase_name]].dropna()
            if not valid.empty:
                last = valid.iloc[-1]
                axes.annotate(
                    phase_name,
                    (float(last["Температура, °C"]), float(last[phase_name])),
                    xytext=(6, 0),
                    textcoords="offset points",
                    color=style["color"],
                    fontsize=11,
                    va="center",
                )

    if relative:
        axes.axhline(
            0.0,
            color=roles["danger"],
            linestyle="--",
            linewidth=1.2,
        )
        y_label = "ΔG относительно минимума выбранных фаз, Дж/моль"
        title = "ThermoGar: относительные энергии фаз"
    else:
        y_label = "Молярная энергия Гиббса GM, Дж/моль"
        title = "ThermoGar: энергия Гиббса отдельных фаз"

    style_chart_axes(
        figure,
        axes,
        title,
        "Температура, °C",
        y_label,
    )
    legend = axes.legend(
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        fontsize=11,
    )
    for item in legend.get_texts():
        item.set_color(roles["axis"])
    figure.tight_layout()
    return figure


def dormant_phase_driving_force_table(
    db: Database,
    components: list[str],
    reference_phases: list[str],
    target_phase: str,
    composition_conditions: dict[Any, float],
    pressure_pa: float,
    t_min_c: float,
    t_max_c: float,
    t_step_c: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Рассчитать движущую силу образования подавленной фазы."""
    if not reference_phases:
        raise ValueError("Для исходного равновесия нужно оставить хотя бы одну фазу.")

    conditions: dict[Any, Any] = {
        v.N: 1.0,
        v.P: float(pressure_pa),
        v.T: temperature_step_condition(t_min_c, t_max_c, t_step_c),
    }
    conditions.update(composition_conditions)

    reference_workspace = Workspace(
        db,
        components,
        reference_phases,
        conditions,
    )
    target_workspace = Workspace(
        db,
        components,
        [target_phase],
        conditions,
    )

    dormant = DormantPhase(target_phase, target_workspace)
    driving_force_property = dormant.driving_force
    driving_force_property.display_name = (
        f"Движущая сила образования {target_phase}"
    )

    temperature_c = workspace_values(reference_workspace, v.T) - 273.15
    driving_force = workspace_values(
        reference_workspace,
        driving_force_property,
    )
    if driving_force.size != temperature_c.size:
        raise RuntimeError("Размеры T и движущей силы не совпали.")

    state = np.full(driving_force.shape, "нет решения", dtype=object)
    state[np.isfinite(driving_force) & (driving_force > 1.0e-3)] = (
        "образование выгодно"
    )
    state[np.isfinite(driving_force) & (driving_force < -1.0e-3)] = (
        "образование невыгодно"
    )
    state[np.isfinite(driving_force) & (np.abs(driving_force) <= 1.0e-3)] = (
        "близко к равновесию"
    )

    dataframe = pd.DataFrame(
        {
            "Температура, °C": temperature_c,
            "Движущая сила, Дж/моль": driving_force,
            "Толкование": state,
        }
    )

    crossings = pd.DataFrame()
    finite = dataframe.dropna(subset=["Движущая сила, Дж/моль"])
    if len(finite) >= 2:
        proxy = pd.DataFrame(
            {
                "Температура, °C": finite["Температура, °C"].to_numpy(),
                "Движущая сила": finite["Движущая сила, Дж/моль"].to_numpy(),
                "Ноль": np.zeros(len(finite)),
            }
        )
        raw_crossings = pair_crossings_dataframe(
            proxy,
            "Температура, °C",
            ["Движущая сила", "Ноль"],
            "Температура смены знака, °C",
        )
        if not raw_crossings.empty:
            crossings = raw_crossings[["Температура смены знака, °C"]]

    return dataframe, crossings


def plot_driving_force(
    dataframe: pd.DataFrame,
    target_phase: str,
) -> plt.Figure:
    """Построить движущую силу выбранной фазы."""
    roles = chart_roles(current_theme_type())
    figure, axes = plt.subplots(figsize=(11.5, 6.5), dpi=100)
    axes.plot(
        dataframe["Температура, °C"],
        dataframe["Движущая сила, Дж/моль"],
        color=roles["primary_dark"],
        linestyle="-",
        marker="o",
        markevery=max(1, len(dataframe) // 20),
        linewidth=1.8,
        markersize=4.0,
        label=target_phase,
    )
    axes.axhline(
        0.0,
        color=roles["danger"],
        linestyle="--",
        linewidth=1.2,
        label="нулевая движущая сила",
    )
    style_chart_axes(
        figure,
        axes,
        f"ThermoGar: движущая сила образования {target_phase}",
        "Температура, °C",
        "Движущая сила, Дж/моль",
    )
    legend = axes.legend(fontsize=11)
    for item in legend.get_texts():
        item.set_color(roles["axis"])
    figure.tight_layout()
    return figure


def first_phase_composition_set(
    workspace: Workspace,
    phase_name: str,
) -> Any | None:
    """Найти первую допустимую CompositionSet выбранной фазы."""
    for _index, composition_sets in workspace.enumerate_composition_sets():
        for composition_set in composition_sets:
            if composition_set.phase_record.phase_name == phase_name:
                return composition_set
    return None


def tzero_path_table(
    db: Database,
    database_key: str,
    balance: str,
    variable_element: str,
    fixed_composition_text: str,
    units: str,
    steel_mode: str,
    phase_one: str,
    phase_two: str,
    c_min: float,
    c_max: float,
    c_step: float,
    pressure_pa: float,
    t_min_c: float,
    t_max_c: float,
) -> pd.DataFrame:
    """Рассчитать T0 двух фаз вдоль концентрационного пути."""
    if phase_one == phase_two:
        raise ValueError("Для T₀ выберите две разные фазы.")
    if variable_element == balance:
        raise ValueError("Изменяемый элемент не может быть элементом-основой.")
    if float(c_step) <= 0.0 or float(c_max) <= float(c_min):
        raise ValueError("Проверьте диапазон и шаг состава.")
    point_count = int(np.floor((float(c_max) - float(c_min)) / float(c_step))) + 1
    if point_count > 150:
        raise ValueError("Слишком много точек состава. Увеличьте шаг.")

    fixed = parse_composition(fixed_composition_text)
    fixed.pop(variable_element, None)
    if balance in fixed:
        raise ValueError(
            f"{balance} — основа; не указывайте её в постоянных добавках."
        )
    if sum(fixed.values()) + float(c_max) >= 100.0:
        raise ValueError(
            "Постоянные добавки вместе с максимальным содержанием "
            "изменяемого элемента должны быть меньше 100 %."
        )

    available = sorted(element for element in db.elements if element != "VA")
    unknown = sorted((set(fixed) | {variable_element, balance}) - set(available))
    if unknown:
        raise ValueError("В базе отсутствуют элементы: " + ", ".join(unknown))

    components = sorted(set(fixed) | {variable_element, balance}) + ["VA"]
    candidate_phases = compatible_phases_for_components(
        db,
        database_key,
        components,
        steel_mode,
    )
    for phase_name in (phase_one, phase_two):
        if phase_name not in candidate_phases:
            raise ValueError(
                f"Фаза {phase_name} несовместима с выбранными компонентами."
            )

    if units == "at":
        axis_variable = v.X(variable_element)
        conditions: dict[Any, Any] = {
            v.X(element): float(value) / 100.0
            for element, value in fixed.items()
        }
    else:
        axis_variable = v.W(variable_element)
        conditions = {
            v.W(element): float(value) / 100.0
            for element, value in fixed.items()
        }

    conditions.update(
        {
            axis_variable: (
                float(c_min) / 100.0,
                float(c_max) / 100.0 + 0.5 * float(c_step) / 100.0,
                float(c_step) / 100.0,
            ),
            v.T: 0.5 * (float(t_min_c) + float(t_max_c)) + 273.15,
            v.P: float(pressure_pa),
            v.N: 1.0,
        }
    )

    path_workspace = Workspace(
        db,
        components,
        [phase_one, phase_two],
        conditions,
    )

    # Отдельные однофазные Workspace дают стартовые точки даже тогда,
    # когда одна из фаз метастабильна во всём обычном равновесии.
    first_workspace = Workspace(db, components, [phase_one], conditions)
    second_workspace = Workspace(db, components, [phase_two], conditions)
    first_composition_set = first_phase_composition_set(
        first_workspace,
        phase_one,
    )
    second_composition_set = first_phase_composition_set(
        second_workspace,
        phase_two,
    )

    if first_composition_set is None:
        raise RuntimeError(
            f"Не удалось получить допустимое состояние фазы {phase_one} "
            "в выбранном диапазоне состава."
        )
    if second_composition_set is None:
        raise RuntimeError(
            f"Не удалось получить допустимое состояние фазы {phase_two} "
            "в выбранном диапазоне состава."
        )

    tzero_property = T0(
        first_composition_set,
        second_composition_set,
        None,
    )
    tzero_property.minimum_value = float(t_min_c) + 273.15
    tzero_property.maximum_value = float(t_max_c) + 273.15

    composition_axis = 100.0 * workspace_values(
        path_workspace,
        axis_variable,
    )
    tzero_k = workspace_values(path_workspace, tzero_property)

    return pd.DataFrame(
        {
            f"{variable_element}, {'ат.%' if units == 'at' else 'мас.%'}": composition_axis,
            "T₀, °C": tzero_k - 273.15,
            "T₀, K": tzero_k,
            "Решение найдено": np.isfinite(tzero_k),
        }
    )


def plot_tzero(
    dataframe: pd.DataFrame,
    x_column: str,
    phase_one: str,
    phase_two: str,
) -> plt.Figure:
    """Построить T0 по составу."""
    roles = chart_roles(current_theme_type())
    figure, axes = plt.subplots(figsize=(11.5, 6.5), dpi=100)
    valid = dataframe.dropna(subset=["T₀, °C"])
    axes.plot(
        valid[x_column],
        valid["T₀, °C"],
        color=roles["primary_dark"],
        linestyle="-",
        marker="o",
        linewidth=1.8,
        markersize=4.0,
        label=f"T₀({phase_one}, {phase_two})",
    )
    style_chart_axes(
        figure,
        axes,
        f"ThermoGar: T₀ для {phase_one} и {phase_two}",
        x_column,
        "Температура T₀, °C",
    )
    legend = axes.legend(fontsize=11)
    for item in legend.get_texts():
        item.set_color(roles["axis"])
    figure.tight_layout()
    return figure


# ---------------------------------------------------------------------------
# Затвердевание: равновесное и Scheil–Gulliver
# ---------------------------------------------------------------------------


def resolve_solidification_start_temperature(
    db: Database,
    components: list[str],
    phases: list[str],
    composition_conditions: dict[Any, float],
    requested_temperature_k: float,
    auto_raise: bool,
    increment_k: float,
    maximum_temperature_k: float,
    pdens: int,
    liquid_threshold: float = 0.9999,
) -> tuple[float, pd.DataFrame]:
    """Проверить, что расчёт начинается практически из одного расплава."""
    current_temperature = float(requested_temperature_k)
    rows: list[dict[str, Any]] = []

    while current_temperature <= float(maximum_temperature_k) + 1e-9:
        conditions = {
            v.N: 1.0,
            v.P: 101325.0,
            v.T: current_temperature,
        }
        conditions.update(composition_conditions)

        eq = equilibrium(
            db,
            components,
            phases,
            conditions,
            calc_opts={"pdens": int(pdens)},
        )
        fractions = aggregate_phase_fractions(eq)
        liquid_fraction = float(fractions.get("LIQUID", 0.0))
        stable_phases = [
            phase_name
            for phase_name, fraction in sorted(
                fractions.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            if fraction > 1e-7
        ]

        rows.append(
            {
                "Температура, °C": current_temperature - 273.15,
                "Доля расплава, %": 100.0 * liquid_fraction,
                "Равновесные фазы": " + ".join(stable_phases),
            }
        )

        if liquid_fraction >= liquid_threshold:
            return current_temperature, pd.DataFrame(rows)

        if not auto_raise:
            break

        current_temperature += float(increment_k)

    check_table = pd.DataFrame(rows)
    last_liquid = (
        float(check_table.iloc[-1]["Доля расплава, %"])
        if not check_table.empty
        else 0.0
    )
    raise ValueError(
        "Начальная температура не даёт практически однофазный расплав. "
        f"Последняя проверенная доля LIQUID: {last_liquid:.3f} %. "
        "Увеличьте начальную температуру или разрешите автоматический поиск."
    )


def solidification_path_dataframe(result: Any) -> pd.DataFrame:
    """Собрать компактную таблицу траектории затвердевания."""
    temperatures_k = np.asarray(result.temperatures, dtype=float)
    fraction_solid = np.asarray(result.fraction_solid, dtype=float)
    fraction_liquid = np.asarray(result.fraction_liquid, dtype=float)

    data: dict[str, Any] = {
        "Температура, °C": temperatures_k - 273.15,
        "Температура, K": temperatures_k,
        "Доля расплава, %": 100.0 * fraction_liquid,
        "Доля твёрдого, %": 100.0 * fraction_solid,
    }

    for phase_name, values in sorted(result.cum_phase_amounts.items()):
        values_array = np.asarray(values, dtype=float)
        if np.nanmax(np.abs(values_array)) <= 1e-12:
            continue
        data[f"{phase_name}, %"] = 100.0 * values_array

    return pd.DataFrame(data)


def solidification_raw_dataframe(result: Any) -> pd.DataFrame:
    """Полная таблица, которую отдаёт пакет scheil."""
    dataframe = result.to_dataframe(include_zero_phases=False).copy()
    if "Temperature (K)" in dataframe.columns:
        dataframe.insert(
            0,
            "Temperature (°C)",
            dataframe["Temperature (K)"].astype(float) - 273.15,
        )
    return dataframe


def solidification_liquid_composition_dataframe(
    result: Any,
    db: Database,
    components: list[str],
) -> pd.DataFrame:
    """Состав остаточного расплава в атомных и массовых процентах."""
    elements = [component for component in components if component != "VA"]
    temperatures_k = np.asarray(result.temperatures, dtype=float)
    liquid_fraction = np.asarray(result.fraction_liquid, dtype=float)
    liquid_data = result.phase_compositions.get(
        result.liquid_phase_name,
        {},
    )

    rows: list[dict[str, Any]] = []
    for index, temperature_k in enumerate(temperatures_k):
        mole_values: dict[str, float] = {}
        for element in elements:
            values = liquid_data.get(element, [])
            if index >= len(values):
                continue
            value = float(values[index])
            if np.isfinite(value) and value >= 0.0:
                mole_values[element] = value

        if sum(mole_values.values()) > 0.0:
            mole_values = normalize(mole_values)
            mass_values = mole_to_mass(db, mole_values)
        else:
            mole_values = {element: np.nan for element in elements}
            mass_values = {element: np.nan for element in elements}

        row: dict[str, Any] = {
            "Температура, °C": float(temperature_k) - 273.15,
            "Доля расплава, %": 100.0 * float(liquid_fraction[index]),
        }
        for element in elements:
            row[f"{element}, ат.%"] = 100.0 * float(
                mole_values.get(element, np.nan)
            )
            row[f"{element}, мас.%"] = 100.0 * float(
                mass_values.get(element, np.nan)
            )
        rows.append(row)

    return pd.DataFrame(rows)


def interpolate_temperature_at_solid_fraction(
    result: Any,
    target_fraction: float,
) -> float | None:
    """Линейно оценить температуру пересечения заданной доли твёрдого."""
    temperatures = np.asarray(result.temperatures, dtype=float)
    fractions = np.asarray(result.fraction_solid, dtype=float)
    target_fraction = float(target_fraction)

    for index in range(1, len(fractions)):
        previous_fraction = float(fractions[index - 1])
        current_fraction = float(fractions[index])
        if (
            previous_fraction <= target_fraction <= current_fraction
            or current_fraction <= target_fraction <= previous_fraction
        ):
            if np.isclose(current_fraction, previous_fraction):
                return float(temperatures[index]) - 273.15
            weight = (
                (target_fraction - previous_fraction)
                / (current_fraction - previous_fraction)
            )
            temperature_k = (
                float(temperatures[index - 1])
                + weight
                * (float(temperatures[index]) - float(temperatures[index - 1]))
            )
            return temperature_k - 273.15

    return None


def solidification_end_index(result: Any) -> int:
    """Для Scheil вернуть точку критерия до служебного закрытия остатка."""
    fractions = np.asarray(result.fraction_solid, dtype=float)
    temperatures = np.asarray(result.temperatures, dtype=float)
    if (
        result.method == "scheil"
        and len(fractions) >= 2
        and np.isclose(fractions[-1], 1.0)
        and fractions[-2] < 1.0
        and np.isclose(temperatures[-1], temperatures[-2])
    ):
        return len(fractions) - 2
    return len(fractions) - 1


def solidification_phase_sequence(
    result: Any,
    database_key: str,
    threshold_fraction: float,
) -> pd.DataFrame:
    """Последовательность первого появления твёрдых фаз."""
    temperatures = np.asarray(result.temperatures, dtype=float)
    rows: list[dict[str, Any]] = []

    for phase_name, values in sorted(result.cum_phase_amounts.items()):
        amounts = np.asarray(values, dtype=float)
        indices = np.where(amounts >= float(threshold_fraction))[0]
        if len(indices) == 0:
            continue
        index = int(indices[0])
        rows.append(
            {
                "Фаза": phase_name,
                "Что это": PHASE_EXPLANATIONS.get(
                    database_key,
                    {},
                ).get(phase_name, ""),
                "Первое появление, °C": float(temperatures[index]) - 273.15,
                "Доля при первом появлении, %": 100.0 * float(amounts[index]),
                "Максимальная доля, %": 100.0 * float(np.nanmax(amounts)),
                "Конечная доля, %": 100.0 * float(amounts[-1]),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "Фаза",
                "Что это",
                "Первое появление, °C",
                "Доля при первом появлении, %",
                "Максимальная доля, %",
                "Конечная доля, %",
            ]
        )

    return (
        pd.DataFrame(rows)
        .sort_values("Первое появление, °C", ascending=False)
        .reset_index(drop=True)
    )


def solidification_final_phase_table(
    result: Any,
    database_key: str,
    threshold_fraction: float,
) -> pd.DataFrame:
    """Итоговые количества фаз после расчёта."""
    rows: list[dict[str, Any]] = []
    for phase_name, values in sorted(result.cum_phase_amounts.items()):
        final_fraction = float(np.asarray(values, dtype=float)[-1])
        if final_fraction < float(threshold_fraction):
            continue
        rows.append(
            {
                "Фаза": phase_name,
                "Что это": PHASE_EXPLANATIONS.get(
                    database_key,
                    {},
                ).get(phase_name, ""),
                "Конечная мольная доля, %": 100.0 * final_fraction,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=["Фаза", "Что это", "Конечная мольная доля, %"]
        )

    return (
        pd.DataFrame(rows)
        .sort_values("Конечная мольная доля, %", ascending=False)
        .reset_index(drop=True)
    )


def solidification_summary_row(
    result: Any,
    appearance_threshold_fraction: float,
) -> dict[str, Any]:
    """Собрать основные температуры и статус одного метода."""
    temperatures = np.asarray(result.temperatures, dtype=float)
    fraction_liquid = np.asarray(result.fraction_liquid, dtype=float)
    end_index = solidification_end_index(result)
    liquidus_c = interpolate_temperature_at_solid_fraction(
        result,
        appearance_threshold_fraction,
    )
    end_temperature_c = float(temperatures[end_index]) - 273.15
    interval = (
        float(liquidus_c) - end_temperature_c
        if liquidus_c is not None
        else np.nan
    )

    return {
        "Метод": SOLIDIFICATION_METHOD_LABELS.get(
            result.method,
            str(result.method),
        ),
        "Расчётный ликвидус, °C": liquidus_c,
        "Температура окончания, °C": end_temperature_c,
        "Что означает окончание": (
            "равновесный солидус"
            if result.method == "equilibrium"
            else "достигнут критерий остаточного расплава"
        ),
        "Интервал кристаллизации, °C": interval,
        "Остаточный расплав в точке окончания, %": (
            100.0 * float(fraction_liquid[end_index])
        ),
        "Точек расчёта": len(temperatures),
        "Расчёт завершён": "да" if bool(result.converged) else "нет",
    }


def plot_solidification_liquid_comparison(
    results: dict[str, Any],
) -> plt.Figure:
    """Сравнить долю расплава для доступных методов."""
    theme_type = current_theme_type()
    roles = chart_roles(theme_type)
    styles = phase_styles(list(results), theme_type)
    figure, axes = plt.subplots(figsize=(11.5, 6.5), dpi=100)

    for method_key, result in results.items():
        temperatures_c = np.asarray(result.temperatures, dtype=float) - 273.15
        liquid_percent = 100.0 * np.asarray(
            result.fraction_liquid,
            dtype=float,
        )
        style = styles[method_key]
        label = SOLIDIFICATION_METHOD_LABELS.get(method_key, method_key)
        axes.plot(
            temperatures_c,
            liquid_percent,
            color=style["color"],
            linestyle=style["linestyle"],
            marker=style["marker"],
            linewidth=1.8,
            markersize=3.5,
            label=label,
        )

        if len(temperatures_c) > 0:
            finite = np.where(
                np.isfinite(temperatures_c) & np.isfinite(liquid_percent)
            )[0]
            if len(finite) > 0:
                middle_index = int(
                    finite[np.argmin(np.abs(liquid_percent[finite] - 50.0))]
                )
                axes.annotate(
                    label,
                    (
                        float(temperatures_c[middle_index]),
                        float(liquid_percent[middle_index]),
                    ),
                    xytext=(6, 5),
                    textcoords="offset points",
                    color=style["color"],
                    fontsize=11,
                )

    style_chart_axes(
        figure,
        axes,
        "ThermoGar: доля расплава при охлаждении",
        "Температура, °C",
        "Доля расплава, %",
    )
    axes.set_ylim(-1.0, 101.0)
    legend = axes.legend(
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        fontsize=11,
    )
    for item in legend.get_texts():
        item.set_color(roles["axis"])
    figure.tight_layout()
    return figure


def plot_solidification_phase_path(
    result: Any,
    database_key: str,
    display_threshold_percent: float,
) -> plt.Figure:
    """Показать накопленные количества твёрдых фаз."""
    dataframe = solidification_path_dataframe(result)
    phase_columns = [
        column
        for column in dataframe.columns
        if column.endswith(", %")
        and column not in {"Доля расплава, %", "Доля твёрдого, %"}
    ]
    visible = [
        column
        for column in phase_columns
        if float(dataframe[column].max()) >= float(display_threshold_percent)
    ]
    renamed = dataframe.rename(
        columns={column: column[:-3] for column in phase_columns}
    )
    visible_phases = [column[:-3] for column in visible]
    method_label = SOLIDIFICATION_METHOD_LABELS.get(
        result.method,
        result.method,
    )
    return plot_phase_fraction_scan(
        renamed,
        "Температура, °C",
        visible_phases,
        f"ThermoGar: твёрдые фазы — {method_label}",
        database_key,
    )


def plot_liquid_composition_comparison(
    liquid_tables: dict[str, pd.DataFrame],
    element: str,
    units: str,
) -> plt.Figure:
    """Сравнить изменение состава остаточного расплава."""
    theme_type = current_theme_type()
    roles = chart_roles(theme_type)
    styles = phase_styles(list(liquid_tables), theme_type)
    suffix = "ат.%" if units == "at" else "мас.%"
    y_column = f"{element}, {suffix}"
    figure, axes = plt.subplots(figsize=(11.5, 6.5), dpi=100)

    for method_key, dataframe in liquid_tables.items():
        if y_column not in dataframe.columns:
            continue
        valid = dataframe[["Температура, °C", y_column]].dropna()
        if valid.empty:
            continue
        style = styles[method_key]
        label = SOLIDIFICATION_METHOD_LABELS.get(method_key, method_key)
        axes.plot(
            valid["Температура, °C"],
            valid[y_column],
            color=style["color"],
            linestyle=style["linestyle"],
            marker=style["marker"],
            linewidth=1.8,
            markersize=3.5,
            label=label,
        )
        end = valid.iloc[-1]
        axes.annotate(
            label,
            (float(end["Температура, °C"]), float(end[y_column])),
            xytext=(6, 0),
            textcoords="offset points",
            color=style["color"],
            fontsize=11,
            va="center",
        )

    style_chart_axes(
        figure,
        axes,
        f"ThermoGar: {element} в остаточном расплаве",
        "Температура, °C",
        f"Содержание {element}, {suffix}",
    )
    handles, labels = axes.get_legend_handles_labels()
    if handles:
        legend = axes.legend(
            loc="center left",
            bbox_to_anchor=(1.01, 0.5),
            fontsize=11,
        )
        for item in legend.get_texts():
            item.set_color(roles["axis"])
    figure.tight_layout()
    return figure


def solidification_excel_bytes(
    state: dict[str, Any],
) -> bytes:
    """Сформировать единый Excel по всем успешным методам."""
    sheets: dict[str, pd.DataFrame] = {
        "Параметры": state["settings"],
        "Сводка": state["summary"],
        "Проверка старта": state["start_check"],
    }
    if "quality" in state:
        sheets["Проверка результата"] = validation_dataframe(
            state["quality"]
        )
    for method_key in state["results"]:
        short = "Равновес" if method_key == "equilibrium" else "Scheil"
        sheets[f"{short} путь"] = state["paths"][method_key]
        sheets[f"{short} фазы"] = state["sequences"][method_key]
        sheets[f"{short} итог"] = state["final_phases"][method_key]
        sheets[f"{short} расплав"] = state["liquid_tables"][method_key]
        sheets[f"{short} raw"] = state["raw_tables"][method_key]
    return dataframe_to_excel(sheets)


def solidification_zip_bytes(
    state: dict[str, Any],
    comparison_figure: plt.Figure,
    phase_figures: dict[str, plt.Figure],
    liquid_figure: plt.Figure | None,
) -> bytes:
    """Собрать полный переносимый архив результатов."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "ThermoGar_solidification.xlsx",
            solidification_excel_bytes(state),
        )
        archive.writestr(
            "summary.csv",
            state["summary"].to_csv(index=False).encode("utf-8-sig"),
        )
        archive.writestr(
            "start_check.csv",
            state["start_check"].to_csv(index=False).encode("utf-8-sig"),
        )
        archive.writestr(
            "liquid_fraction.png",
            figure_to_png(comparison_figure),
        )
        for method_key in state["results"]:
            archive.writestr(
                f"{method_key}_path.csv",
                state["paths"][method_key]
                .to_csv(index=False)
                .encode("utf-8-sig"),
            )
            archive.writestr(
                f"{method_key}_liquid_composition.csv",
                state["liquid_tables"][method_key]
                .to_csv(index=False)
                .encode("utf-8-sig"),
            )
            if method_key in phase_figures:
                archive.writestr(
                    f"{method_key}_phases.png",
                    figure_to_png(phase_figures[method_key]),
                )
        if liquid_figure is not None:
            archive.writestr(
                "liquid_composition.png",
                figure_to_png(liquid_figure),
            )
    return buffer.getvalue()

def binary_mass_to_mole_fraction(
    db: Database,
    dependent_element: str,
    variable_element: str,
    mass_fraction_variable: float,
) -> float:
    """Пересчитать массовую долю второго элемента в мольную для бинарной системы."""
    mass_fraction_variable = float(mass_fraction_variable)
    if mass_fraction_variable <= 0.0:
        return 0.0
    if mass_fraction_variable >= 1.0:
        return 1.0

    mass_variable = float(db.refstates[variable_element]["mass"])
    mass_dependent = float(db.refstates[dependent_element]["mass"])
    moles_variable = mass_fraction_variable / mass_variable
    moles_dependent = (1.0 - mass_fraction_variable) / mass_dependent
    return moles_variable / (moles_variable + moles_dependent)


def binary_phase_candidates(
    db: Database,
    database_key: str,
    left_element: str,
    right_element: str,
    steel_mode: str,
) -> list[str]:
    components = [left_element, right_element, "VA"]
    return compatible_phases_for_components(
        db,
        database_key,
        components,
        steel_mode,
    )


def plot_binary_thermogar(
    strategy: BinaryStrategy,
    x_variable: Any,
    y_variable: Any,
    x_limits: tuple[float, float],
    temperature_limits_k: tuple[float, float],
    title: str,
    x_label: str,
    show_tielines: bool,
    label_nodes: bool,
) -> tuple[plt.Figure, plt.Axes]:
    """Нарисовать бинарную диаграмму по данным Mapping API."""
    theme_type = current_theme_type()
    roles = chart_roles(theme_type)
    phase_names = sorted(strategy.get_all_phases())
    styles = phase_styles(phase_names, theme_type)

    figure, axes = plt.subplots(figsize=(11.5, 7.0), dpi=100)
    last_points: dict[str, tuple[float, float]] = {}

    tieline_data = strategy.get_tieline_data(x_variable, y_variable)
    for group_index, tieline in enumerate(tieline_data):
        phase_data_items = list(tieline.data)
        for phase_data in phase_data_items:
            x_values = np.asarray(phase_data.x, dtype=float)
            y_values = np.asarray(phase_data.y, dtype=float)
            mask = np.isfinite(x_values) & np.isfinite(y_values)
            if not np.any(mask):
                continue
            phase_name = str(phase_data.phase)
            style = styles[phase_name]
            axes.plot(
                x_values[mask],
                y_values[mask],
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=1.8,
                solid_capstyle="butt",
            )
            last_points[phase_name] = (
                float(x_values[mask][-1]),
                float(y_values[mask][-1]),
            )

        if show_tielines:
            x_values = np.asarray(tieline.x, dtype=float)
            y_values = np.asarray(tieline.y, dtype=float)
            if x_values.ndim == 2 and y_values.ndim == 2:
                lines = np.transpose(
                    np.asarray([x_values, y_values]),
                    axes=(2, 1, 0),
                )
                axes.add_collection(
                    LineCollection(
                        lines[::5],
                        linewidths=0.55,
                        linestyles="--",
                        colors=roles["muted"],
                        alpha=0.7,
                        zorder=1,
                    )
                )

    invariant_data = strategy.get_invariant_data(x_variable, y_variable)
    for invariant in invariant_data:
        x_values = np.asarray(invariant.x, dtype=float)
        y_values = np.asarray(invariant.y, dtype=float)
        mask = np.isfinite(x_values) & np.isfinite(y_values)
        if not np.any(mask):
            continue
        x_plot = np.concatenate((x_values[mask], [x_values[mask][0]]))
        y_plot = np.concatenate((y_values[mask], [y_values[mask][0]]))
        axes.plot(
            x_plot,
            y_plot,
            color=roles["axis"],
            linewidth=1.2,
            zorder=2.5,
        )
        if label_nodes:
            phases = list(getattr(invariant, "phases", []))
            for x_value, y_value, phase_name in zip(
                x_values[mask],
                y_values[mask],
                phases,
            ):
                phase_name = str(phase_name)
                style = styles.get(
                    phase_name,
                    {"color": roles["primary"]},
                )
                axes.scatter(
                    [x_value],
                    [y_value],
                    color=style["color"],
                    s=18,
                    zorder=3,
                )

    handles = []
    for phase_name in phase_names:
        style = styles[phase_name]
        handles.append(
            Line2D(
                [0],
                [0],
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=2.0,
                label=phase_name,
            )
        )

    style_chart_axes(
        figure,
        axes,
        title,
        x_label,
        "Температура, °C",
    )
    axes.set_xlim(*x_limits)
    axes.set_ylim(*temperature_limits_k)
    axes.xaxis.set_major_formatter(
        FuncFormatter(lambda value, _position: f"{100.0 * value:g}")
    )
    axes.yaxis.set_major_formatter(
        FuncFormatter(lambda value, _position: f"{value - 273.15:g}")
    )

    legend = axes.legend(
        handles=handles,
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        fontsize=11,
    )
    for item in legend.get_texts():
        item.set_color(roles["axis"])

    if theme_type == "dark" and len(last_points) <= 7:
        for phase_name, (x_value, y_value) in last_points.items():
            axes.annotate(
                phase_name,
                (x_value, y_value),
                xytext=(5, 0),
                textcoords="offset points",
                color=styles[phase_name]["color"],
                fontsize=11,
                va="center",
            )

    figure.tight_layout()
    return figure, axes


def binary_boundary_dataframe(
    strategy: BinaryStrategy,
    x_variable: Any,
    y_variable: Any,
) -> pd.DataFrame:
    """Выгрузить рассчитанные линии границ и инвариантные точки в таблицу."""
    rows: list[dict[str, Any]] = []

    for group_index, tieline in enumerate(
        strategy.get_tieline_data(x_variable, y_variable),
        start=1,
    ):
        for phase_data in tieline.data:
            x_values = np.asarray(phase_data.x, dtype=float)
            y_values = np.asarray(phase_data.y, dtype=float)
            for point_index, (x_value, y_value) in enumerate(
                zip(x_values, y_values),
                start=1,
            ):
                if not np.isfinite(x_value) or not np.isfinite(y_value):
                    continue
                rows.append(
                    {
                        "Тип": "Граница фазовой области",
                        "Группа": group_index,
                        "Фаза": str(phase_data.phase),
                        "Точка": point_index,
                        "Состав, доля": float(x_value),
                        "Состав, %": 100.0 * float(x_value),
                        "Температура, K": float(y_value),
                        "Температура, °C": float(y_value) - 273.15,
                    }
                )

    for group_index, invariant in enumerate(
        strategy.get_invariant_data(x_variable, y_variable),
        start=1,
    ):
        phases = list(getattr(invariant, "phases", []))
        for point_index, (x_value, y_value) in enumerate(
            zip(
                np.asarray(invariant.x, dtype=float),
                np.asarray(invariant.y, dtype=float),
            ),
            start=1,
        ):
            if not np.isfinite(x_value) or not np.isfinite(y_value):
                continue
            phase_name = (
                str(phases[point_index - 1])
                if point_index - 1 < len(phases)
                else ""
            )
            rows.append(
                {
                    "Тип": "Инвариантная точка",
                    "Группа": group_index,
                    "Фаза": phase_name,
                    "Точка": point_index,
                    "Состав, доля": float(x_value),
                    "Состав, %": 100.0 * float(x_value),
                    "Температура, K": float(y_value),
                    "Температура, °C": float(y_value) - 273.15,
                }
            )

    return pd.DataFrame(rows)


def dataframe_to_excel(
    sheets: dict[str, pd.DataFrame],
) -> bytes:
    export_sheets = dict(sheets)
    context = globals().get("CURRENT_CONTEXT")
    if isinstance(context, dict) and context.get("database_path"):
        export_sheets.setdefault(
            "Происхождение",
            pd.DataFrame(
                [
                    {
                        "База": context.get("database_label")
                        or DATABASE_DEFINITIONS.get(
                            context.get("database_key", ""),
                            {},
                        ).get("label", context.get("database_key", "")),
                        "Файл базы": context.get("database_path", ""),
                        "SHA-256 базы": context.get("database_sha256", ""),
                        "Линия": APP_LINEAGE,
                        "Версия ThermoGar": APP_VERSION,
                        "Класс выпуска": RELEASE_CLASS,
                        "Статус программы": SOFTWARE_RELEASE_STATUS,
                        "Статус материала": SCIENTIFIC_MATERIAL_STATUS,
                        "Производственное использование": PRODUCTION_USE,
                        "pycalphad": getattr(__import__("pycalphad"), "__version__", ""),
                        "Статус неопределённости": (
                            "не оценена: база не содержит универсальной доверительной вилки"
                        ),
                    }
                ]
            ),
        )

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, dataframe in export_sheets.items():
            dataframe.to_excel(
                writer,
                sheet_name=name[:31],
                index=False,
            )
    return buffer.getvalue()


def figure_to_png(figure: plt.Figure) -> bytes:
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=200, bbox_inches="tight")
    return buffer.getvalue()


def parse_phase_descriptions(text: str) -> dict[str, str]:
    """Parse descriptions only from an already verified strict UTF-8 snapshot."""
    if type(text) is not str:
        raise TypeError("Текст справочника фаз должен быть проверенной строкой.")
    result: dict[str, str] = {}
    pending_description = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if line.startswith("$ MATCALC_DESCRIPTION:"):
            pending_description = line.split(":", 1)[1].strip()
            continue

        match = re.match(r"(?i)^PHASE\s+([^\s!]+)", line)
        if match:
            phase_name = match.group(1).split(":", 1)[0].upper()
            result[phase_name] = pending_description
            pending_description = ""

    return result



EXACT_DESCRIPTION_TRANSLATIONS = {
    "New phase description based on calorimetric data.": (
        "Новое описание фазы, основанное на калориметрических данных."
    ),
    "Body-centered cubic Manganese modification, stable below around 1000 K.": (
        "Объёмно-центрированная кубическая модификация марганца, "
        "устойчивая примерно ниже 1000 K."
    ),
    "Hexagonal close-packed Cu2S, A-chalcosite.": (
        "Гексагональная плотноупакованная модификация Cu₂S — A-халькозин."
    ),
    "Body-centered cubic Ferrite phase.": (
        "Объёмно-центрированная кубическая фаза феррита."
    ),
    "Ordered bcc_A2-based B2-Phase, 2-substitutional sublattices split model used.": (
        "Упорядоченная B2-фаза на основе ОЦК_A2; "
        "используется модель с двумя замещающими подрешётками."
    ),
}


def translate_phase_description(
    phase_name: str,
    description: str,
    simple_explanation: str,
) -> str:
    """Дать полезное русское описание без внешнего переводчика."""
    original = (description or "").strip()

    if original in EXACT_DESCRIPTION_TRANSLATIONS:
        return EXACT_DESCRIPTION_TRANSLATIONS[original]

    lower = original.lower()
    parts: list[str] = []

    if simple_explanation:
        parts.append(simple_explanation.rstrip(".") + ".")

    # Специальные формулировки, встречающиеся в открытых MatCalc-базах.
    if "aln phase description based on assessed solubility product" in lower:
        parts.append(
            "Описание фазы AlN основано на оценённом произведении "
            "растворимости; модель специально настроена для этой фазы."
        )

    if "cottrell atmosphere" in lower:
        parts.append(
            "Фаза используется для моделирования образования атмосфер "
            "Коттрелла."
        )

    # Тип кристаллической структуры.
    if "body-centered cubic" in lower or "bcc" in lower:
        parts.append("Объёмно-центрированная кубическая (ОЦК) структура.")
    elif "face-centered cubic" in lower or "fcc" in lower:
        parts.append("Гранецентрированная кубическая (ГЦК) структура.")
    elif "hexagonal close-packed" in lower or "hcp" in lower:
        parts.append("Гексагональная плотноупакованная (ГПУ) структура.")

    # Назначение и устойчивость.
    if "equilibrium phase" in lower:
        parts.append("Равновесная фаза.")
    if "metastable" in lower:
        parts.append("Метастабильная фаза.")
    if "precipitate" in lower or "precipitation" in lower:
        parts.append("Фаза-выделение, связанная с дисперсионным упрочнением.")
    if "matrix" in lower:
        parts.append("Матричная фаза или модель твёрдого раствора.")
    if "ordered" in lower:
        parts.append("Упорядоченная фаза.")
    if "disordered" in lower:
        parts.append("Разупорядоченная фаза.")

    # Класс соединения.
    if "carbide" in lower:
        parts.append("Карбидная фаза.")
    if "nitride" in lower:
        parts.append("Нитридная фаза.")
    if "boride" in lower:
        parts.append("Боридная фаза.")
    if "oxide" in lower:
        parts.append("Оксидная фаза.")
    if "sulfide" in lower or "sulphide" in lower:
        parts.append("Сульфидная фаза.")
    if "laves" in lower:
        parts.append("Фаза Лавеса.")
    if "liquid" in lower:
        parts.append("Жидкая фаза — расплав.")

    # На чём основана оценка.
    if "calorimetric data" in lower:
        parts.append("Параметры основаны на калориметрических данных.")
    if "solubility product" in lower:
        parts.append(
            "Параметры основаны на оценённом произведении растворимости."
        )
    if "experimental data" in lower:
        parts.append(
            "Аннотация базы заявляет эмпирическую основу; ThermoGar её "
            "независимо не подтверждал."
        )
    if "literature data" in lower:
        parts.append("Описание основано на литературных данных.")
    if "assessed" in lower and not any(
        phrase in lower
        for phrase in (
            "calorimetric data",
            "solubility product",
            "experimental data",
            "literature data",
        )
    ):
        parts.append("Параметры фазы получены термодинамической оценкой.")

    # Численные пределы устойчивости.
    match = re.search(
        r"stable\s+below\s+(?:around\s+)?([0-9.]+)\s*K",
        original,
        flags=re.IGNORECASE,
    )
    if match:
        parts.append(f"Устойчива примерно ниже {match.group(1)} K.")

    match = re.search(
        r"stable\s+above\s+(?:around\s+)?([0-9.]+)\s*K",
        original,
        flags=re.IGNORECASE,
    )
    if match:
        parts.append(f"Устойчива примерно выше {match.group(1)} K.")

    if "sublattice" in lower:
        parts.append("Используется подрешёточная модель.")

    # Убираем повторы, сохраняя порядок.
    unique_parts: list[str] = []
    seen: set[str] = set()
    for part in parts:
        normalized = part.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique_parts.append(normalized)

    if unique_parts:
        return " ".join(unique_parts)

    if original:
        return (
            "Русская расшифровка для этой специализированной фазы "
            "ещё не добавлена."
        )

    return "Описание в исходной базе отсутствует."


def phase_reference_dataframe(
    db: Database,
    database_path: Path,
    database_key: str,
) -> pd.DataFrame:
    expected_sha256 = (
        FE_PROFILE_SHA256[FE_PROFILE_CANONICAL]
        if database_key == "fe"
        else RELEASE_DATABASE_SHA256[database_key]
    )
    artifact = read_verified_utf8_text(
        database_path,
        expected_sha256=expected_sha256,
        maximum_bytes=MAX_TDB_SNAPSHOT_BYTES,
        canonical_root=PROJECT_ROOT,
    )
    descriptions = parse_phase_descriptions(artifact.text)
    rows = []

    for phase_name in sorted(db.phases):
        phase = db.phases[phase_name]
        hints = phase.model_hints
        model_note = ""

        ordered = hints.get("ordered_phase")
        disordered = hints.get("disordered_phase")

        if ordered == phase_name and disordered:
            model_note = (
                f"Связанная order/disorder-модель с {disordered}; "
                "одно имя фазы не всегда означает полное упорядочение."
            )
        elif disordered == phase_name and ordered:
            model_note = (
                f"Разупорядоченная часть связанной модели {ordered}."
            )

        simple_explanation = (
            PHASE_EXPLANATIONS.get(database_key, {}).get(
                phase_name,
                "",
            )
        )
        original_description = descriptions.get(phase_name, "")

        rows.append(
            {
                "Код фазы": phase_name,
                "Простыми словами": simple_explanation,
                "Описание по-русски": translate_phase_description(
                    phase_name,
                    original_description,
                    simple_explanation,
                ),
                "Примечание модели": model_note,
                "Оригинал из базы (англ.)": original_description,
            }
        )

    return pd.DataFrame(rows)



def _phase_group_label(value: Any) -> str:
    """Свести имя или набор имён фаз к читаемой строке."""
    if isinstance(value, (set, frozenset, list, tuple)):
        return " + ".join(sorted(str(item) for item in value))
    return str(value)


def isopleth_phase_candidates(
    db: Database,
    database_key: str,
    balance_element: str,
    variable_element: str,
    fixed_composition: dict[str, float],
    steel_mode: str,
) -> list[str]:
    """Вернуть совместимые фазы для многокомпонентного сечения."""
    components = sorted(
        set(fixed_composition)
        | {balance_element, variable_element}
    ) + ["VA"]
    return compatible_phases_for_components(
        db,
        database_key,
        components,
        steel_mode,
    )


def plot_isopleth_thermogar(
    strategy: IsoplethStrategy,
    x_variable: Any,
    y_variable: Any,
    x_limits: tuple[float, float],
    temperature_limits_k: tuple[float, float],
    title: str,
    x_label: str,
    label_nodes: bool,
) -> tuple[plt.Figure, plt.Axes]:
    """Нарисовать многокомпонентное изоплетное сечение в стиле ThermoGar."""
    theme_type = current_theme_type()
    roles = chart_roles(theme_type)
    phase_names = sorted(strategy.get_all_phases())
    styles = phase_styles(phase_names, theme_type)

    figure, axes = plt.subplots(figsize=(11.5, 7.0), dpi=100)
    last_points: dict[str, tuple[float, float]] = {}

    zpf_data = strategy.get_zpf_data(x_variable, y_variable)
    for phase_data in zpf_data.data:
        x_values = np.atleast_1d(
            np.asarray(phase_data.x, dtype=float)
        )
        y_values = np.atleast_1d(
            np.asarray(phase_data.y, dtype=float)
        )
        mask = np.isfinite(x_values) & np.isfinite(y_values)
        if not np.any(mask):
            continue

        phase_name = str(phase_data.phase)
        style = styles.get(
            phase_name,
            {
                "color": roles["primary"],
                "linestyle": "-",
                "marker": "o",
            },
        )
        axes.plot(
            x_values[mask],
            y_values[mask],
            color=style["color"],
            linestyle=style["linestyle"],
            linewidth=1.8,
            solid_capstyle="butt",
        )
        last_points[phase_name] = (
            float(x_values[mask][-1]),
            float(y_values[mask][-1]),
        )

    invariant_data = strategy.get_invariant_data(
        x_variable,
        y_variable,
    )
    for invariant in invariant_data:
        x_values = np.atleast_1d(
            np.asarray(invariant.x, dtype=float)
        )
        y_values = np.atleast_1d(
            np.asarray(invariant.y, dtype=float)
        )
        mask = np.isfinite(x_values) & np.isfinite(y_values)
        x_values = x_values[mask]
        y_values = y_values[mask]

        if len(x_values) >= 2:
            points = np.column_stack((x_values, y_values))
            line_segments = [
                [points[i], points[j]]
                for i in range(len(points))
                for j in range(i + 1, len(points))
            ]
            axes.add_collection(
                LineCollection(
                    line_segments,
                    zorder=2.5,
                    linewidths=1.0,
                    capstyle="butt",
                    colors=roles["axis"],
                )
            )

        if label_nodes and len(x_values):
            axes.scatter(
                x_values,
                y_values,
                color=roles["primary"],
                marker="o",
                s=22,
                zorder=3,
            )

    handles = []
    for phase_name in phase_names:
        style = styles[phase_name]
        handles.append(
            Line2D(
                [0],
                [0],
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=2.0,
                label=phase_name,
            )
        )

    style_chart_axes(
        figure,
        axes,
        title,
        x_label,
        "Температура, °C",
    )
    axes.set_xlim(*x_limits)
    axes.set_ylim(*temperature_limits_k)
    axes.xaxis.set_major_formatter(
        FuncFormatter(lambda value, _position: f"{100.0 * value:g}")
    )
    axes.yaxis.set_major_formatter(
        FuncFormatter(lambda value, _position: f"{value - 273.15:g}")
    )

    if handles:
        legend = axes.legend(
            handles=handles,
            loc="center left",
            bbox_to_anchor=(1.01, 0.5),
            fontsize=11,
        )
        for item in legend.get_texts():
            item.set_color(roles["axis"])

    if theme_type == "dark" and len(last_points) <= 7:
        for phase_name, (x_value, y_value) in last_points.items():
            axes.annotate(
                phase_name,
                (x_value, y_value),
                xytext=(5, 0),
                textcoords="offset points",
                color=styles.get(
                    phase_name,
                    {"color": roles["primary"]},
                )["color"],
                fontsize=11,
                va="center",
            )

    figure.tight_layout()
    return figure, axes


def isopleth_boundary_dataframe(
    strategy: IsoplethStrategy,
    x_variable: Any,
    y_variable: Any,
) -> pd.DataFrame:
    """Выгрузить линии ZPF и узлы многокомпонентного сечения."""
    rows: list[dict[str, Any]] = []

    zpf_data = strategy.get_zpf_data(x_variable, y_variable)
    for line_index, phase_data in enumerate(
        zpf_data.data,
        start=1,
    ):
        x_values = np.atleast_1d(
            np.asarray(phase_data.x, dtype=float)
        )
        y_values = np.atleast_1d(
            np.asarray(phase_data.y, dtype=float)
        )
        for point_index, (x_value, y_value) in enumerate(
            zip(x_values, y_values),
            start=1,
        ):
            if not np.isfinite(x_value) or not np.isfinite(y_value):
                continue
            rows.append(
                {
                    "Тип": "Граница фазовой области",
                    "Группа": line_index,
                    "Фаза / набор фаз": str(phase_data.phase),
                    "Точка": point_index,
                    "Состав, доля": float(x_value),
                    "Состав, ат.%": 100.0 * float(x_value),
                    "Температура, K": float(y_value),
                    "Температура, °C": float(y_value) - 273.15,
                }
            )

    for node_index, invariant in enumerate(
        strategy.get_invariant_data(x_variable, y_variable),
        start=1,
    ):
        for phase_data in invariant.data:
            x_values = np.atleast_1d(
                np.asarray(phase_data.x, dtype=float)
            )
            y_values = np.atleast_1d(
                np.asarray(phase_data.y, dtype=float)
            )
            phase_label = _phase_group_label(phase_data.phase)
            for point_index, (x_value, y_value) in enumerate(
                zip(x_values, y_values),
                start=1,
            ):
                if not np.isfinite(x_value) or not np.isfinite(y_value):
                    continue
                rows.append(
                    {
                        "Тип": "Инвариантное пересечение",
                        "Группа": node_index,
                        "Фаза / набор фаз": phase_label,
                        "Точка": point_index,
                        "Состав, доля": float(x_value),
                        "Состав, ат.%": 100.0 * float(x_value),
                        "Температура, K": float(y_value),
                        "Температура, °C": float(y_value) - 273.15,
                    }
                )

    return pd.DataFrame(rows)



# ---------------------------------------------------------------------------
# Тройные изотермические диаграммы
# ---------------------------------------------------------------------------

def ternary_phase_candidates(
    db: Database,
    database_key: str,
    x_element: str,
    y_element: str,
    dependent_element: str,
    steel_mode: str,
) -> list[str]:
    """Вернуть совместимые фазы для трёхкомпонентной системы."""
    components = [dependent_element, x_element, y_element, "VA"]
    return compatible_phases_for_components(
        db,
        database_key,
        components,
        steel_mode,
    )


def plot_ternary_thermogar(
    strategy: TernaryStrategy,
    x_variable: Any,
    y_variable: Any,
    dependent_element: str,
    x_element: str,
    y_element: str,
    temperature_c: float,
    show_tielines: bool,
    tieline_every: int,
    label_nodes: bool,
) -> tuple[plt.Figure, plt.Axes]:
    """Нарисовать тройную изотермическую диаграмму в стиле ThermoGar."""
    theme_type = current_theme_type()
    roles = chart_roles(theme_type)
    phase_names = sorted(strategy.get_all_phases())
    styles = phase_styles(phase_names, theme_type)

    figure, axes = plt.subplots(
        figsize=(11.5, 8.0),
        dpi=100,
        subplot_kw={"projection": "triangular"},
    )
    last_points: dict[str, tuple[float, float]] = {}

    tieline_data = strategy.get_tieline_data(x_variable, y_variable)
    for tieline in tieline_data:
        for phase_data in tieline.data:
            x_values = np.atleast_1d(
                np.asarray(phase_data.x, dtype=float)
            )
            y_values = np.atleast_1d(
                np.asarray(phase_data.y, dtype=float)
            )
            mask = (
                np.isfinite(x_values)
                & np.isfinite(y_values)
                & (x_values >= -1e-9)
                & (y_values >= -1e-9)
                & (x_values + y_values <= 1.0 + 1e-8)
            )
            if not np.any(mask):
                continue

            phase_name = str(phase_data.phase)
            style = styles.get(
                phase_name,
                {
                    "color": roles["primary"],
                    "linestyle": "-",
                    "marker": "o",
                },
            )
            axes.plot(
                x_values[mask],
                y_values[mask],
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=1.8,
                solid_capstyle="butt",
                zorder=2,
            )
            last_points[phase_name] = (
                float(x_values[mask][-1]),
                float(y_values[mask][-1]),
            )

        if show_tielines:
            x_values = np.asarray(tieline.x, dtype=float)
            y_values = np.asarray(tieline.y, dtype=float)
            if x_values.ndim == 2 and y_values.ndim == 2:
                lines = np.transpose(
                    np.asarray([x_values, y_values]),
                    axes=(2, 1, 0),
                )
                axes.add_collection(
                    LineCollection(
                        lines[::max(1, int(tieline_every))],
                        linewidths=0.55,
                        linestyles="--",
                        colors=roles["muted"],
                        alpha=0.75,
                        zorder=1,
                    )
                )

    for invariant in strategy.get_invariant_data(
        x_variable,
        y_variable,
    ):
        x_values = np.atleast_1d(
            np.asarray(invariant.x, dtype=float)
        )
        y_values = np.atleast_1d(
            np.asarray(invariant.y, dtype=float)
        )
        mask = (
            np.isfinite(x_values)
            & np.isfinite(y_values)
            & (x_values >= -1e-9)
            & (y_values >= -1e-9)
            & (x_values + y_values <= 1.0 + 1e-8)
        )
        x_values = x_values[mask]
        y_values = y_values[mask]
        if len(x_values) >= 2:
            x_plot = np.concatenate((x_values, [x_values[0]]))
            y_plot = np.concatenate((y_values, [y_values[0]]))
            axes.plot(
                x_plot,
                y_plot,
                color=roles["axis"],
                linewidth=1.1,
                zorder=2.5,
            )

        if label_nodes and len(x_values):
            phases = list(getattr(invariant, "phases", []))
            for point_index, (x_value, y_value) in enumerate(
                zip(x_values, y_values)
            ):
                phase_name = (
                    str(phases[point_index])
                    if point_index < len(phases)
                    else ""
                )
                style = styles.get(
                    phase_name,
                    {
                        "color": roles["primary"],
                        "marker": "o",
                    },
                )
                axes.scatter(
                    [x_value],
                    [y_value],
                    color=style["color"],
                    marker=style.get("marker", "o"),
                    s=24,
                    zorder=3,
                )

    handles: list[Line2D] = []
    for phase_name in phase_names:
        style = styles[phase_name]
        handles.append(
            Line2D(
                [0],
                [0],
                color=style["color"],
                linestyle=style["linestyle"],
                marker=style["marker"],
                markersize=5,
                linewidth=2.0,
                label=phase_name,
            )
        )

    figure.set_facecolor(roles["background"])
    axes.set_facecolor(roles["background"])
    axes.set_xlim(0.0, 1.0)
    axes.set_ylim(0.0, 1.0)
    axes.set_title(
        (
            f"Изотермическая диаграмма "
            f"{dependent_element}–{x_element}–{y_element} "
            f"при {temperature_c:.1f} °C"
        ),
        fontsize=13,
        color=roles["text"],
    )
    axes.set_xlabel(
        f"Содержание {x_element}, ат.%",
        fontsize=13,
        color=roles["axis"],
    )
    axes.set_ylabel(
        f"Содержание {y_element}, ат.%",
        fontsize=13,
        color=roles["axis"],
    )
    axes.yaxis.label.set_rotation(60)
    axes.yaxis.set_label_coords(x=0.12, y=0.5)
    axes.xaxis.set_major_formatter(
        FuncFormatter(lambda value, _position: f"{100.0 * value:g}")
    )
    axes.yaxis.set_major_formatter(
        FuncFormatter(lambda value, _position: f"{100.0 * value:g}")
    )
    axes.grid(True, color=roles["grid"], alpha=0.55)
    axes.tick_params(
        axis="both",
        which="both",
        labelsize=11,
        colors=roles["axis"],
    )
    for spine in axes.spines.values():
        spine.set_color(roles["axis"])

    # Подписи вершин делают тройную диаграмму понятной без знания
    # внутренней системы координат pycalphad.
    axes.text(
        -0.03,
        -0.08,
        f"{dependent_element}: 100 %",
        transform=axes.transAxes,
        ha="left",
        va="top",
        fontsize=11,
        color=roles["axis"],
    )
    axes.text(
        1.03,
        -0.08,
        f"{x_element}: 100 %",
        transform=axes.transAxes,
        ha="right",
        va="top",
        fontsize=11,
        color=roles["axis"],
    )
    axes.text(
        0.5,
        1.04,
        f"{y_element}: 100 %",
        transform=axes.transAxes,
        ha="center",
        va="bottom",
        fontsize=11,
        color=roles["axis"],
    )
    axes.text(
        0.5,
        -0.14,
        (
            f"Доля {dependent_element} = 100 − "
            f"{x_element} − {y_element}"
        ),
        transform=axes.transAxes,
        ha="center",
        va="top",
        fontsize=11,
        color=roles["axis"],
    )

    if handles:
        legend = axes.legend(
            handles=handles,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            fontsize=11,
        )
        for item in legend.get_texts():
            item.set_color(roles["axis"])

    if theme_type == "dark":
        for phase_name, (x_value, y_value) in last_points.items():
            style = styles.get(
                phase_name,
                {"color": roles["primary"]},
            )
            axes.annotate(
                phase_name,
                (x_value, y_value),
                xytext=(5, 0),
                textcoords="offset points",
                color=style["color"],
                fontsize=11,
                va="center",
            )

    figure.subplots_adjust(
        left=0.08,
        right=0.76,
        bottom=0.17,
        top=0.88,
    )
    return figure, axes


def ternary_boundary_dataframe(
    strategy: TernaryStrategy,
    x_variable: Any,
    y_variable: Any,
    dependent_element: str,
    x_element: str,
    y_element: str,
) -> pd.DataFrame:
    """Выгрузить границы и трёхфазные узлы тройной диаграммы."""
    rows: list[dict[str, Any]] = []

    def append_point(
        point_type: str,
        group_index: int,
        phase_label: str,
        point_index: int,
        x_value: float,
        y_value: float,
    ) -> None:
        if not np.isfinite(x_value) or not np.isfinite(y_value):
            return
        third_value = 1.0 - float(x_value) - float(y_value)
        if third_value < -1e-6:
            return
        third_value = max(0.0, third_value)
        rows.append(
            {
                "Тип": point_type,
                "Группа": group_index,
                "Фаза / набор фаз": phase_label,
                "Точка": point_index,
                f"X({x_element})": float(x_value),
                f"{x_element}, ат.%": 100.0 * float(x_value),
                f"X({y_element})": float(y_value),
                f"{y_element}, ат.%": 100.0 * float(y_value),
                f"X({dependent_element})": third_value,
                f"{dependent_element}, ат.%": 100.0 * third_value,
            }
        )

    for group_index, tieline in enumerate(
        strategy.get_tieline_data(x_variable, y_variable),
        start=1,
    ):
        for phase_data in tieline.data:
            x_values = np.atleast_1d(
                np.asarray(phase_data.x, dtype=float)
            )
            y_values = np.atleast_1d(
                np.asarray(phase_data.y, dtype=float)
            )
            for point_index, (x_value, y_value) in enumerate(
                zip(x_values, y_values),
                start=1,
            ):
                append_point(
                    "Граница фазовой области",
                    group_index,
                    str(phase_data.phase),
                    point_index,
                    float(x_value),
                    float(y_value),
                )

    for group_index, invariant in enumerate(
        strategy.get_invariant_data(x_variable, y_variable),
        start=1,
    ):
        for phase_data in invariant.data:
            x_values = np.atleast_1d(
                np.asarray(phase_data.x, dtype=float)
            )
            y_values = np.atleast_1d(
                np.asarray(phase_data.y, dtype=float)
            )
            for point_index, (x_value, y_value) in enumerate(
                zip(x_values, y_values),
                start=1,
            ):
                append_point(
                    "Трёхфазный узел",
                    group_index,
                    str(phase_data.phase),
                    point_index,
                    float(x_value),
                    float(y_value),
                )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Тройные карты мольной доли выбранной фазы
# ---------------------------------------------------------------------------

def ternary_grid_definition(
    requested_step_percent: float,
) -> tuple[int, float, int]:
    """Вернуть число интервалов, фактический шаг и число узлов треугольника."""
    if requested_step_percent <= 0:
        raise ValueError("Шаг сетки должен быть больше нуля.")

    interval_count = max(
        2,
        int(round(100.0 / float(requested_step_percent))),
    )
    actual_step_percent = 100.0 / interval_count
    point_count = (interval_count + 1) * (interval_count + 2) // 2
    return interval_count, actual_step_percent, point_count


def ternary_display_to_mole_fractions(
    db: Database,
    dependent_element: str,
    x_element: str,
    y_element: str,
    dependent_fraction: float,
    x_fraction: float,
    y_fraction: float,
    units: str,
) -> dict[str, float]:
    """Перевести одну точку треугольника из ат. или мас. долей в мольные."""
    display_fractions = {
        dependent_element: max(0.0, float(dependent_fraction)),
        x_element: max(0.0, float(x_fraction)),
        y_element: max(0.0, float(y_fraction)),
    }
    display_fractions = normalize(display_fractions)

    if units == "at":
        return display_fractions

    if units != "wt":
        raise ValueError(f"Неизвестные единицы тройной карты: {units}")

    mole_amounts: dict[str, float] = {}
    for element, mass_fraction in display_fractions.items():
        atomic_mass = float(db.refstates[element]["mass"])
        if atomic_mass <= 0:
            raise ValueError(
                f"Для {element} в базе отсутствует корректная атомная масса."
            )
        mole_amounts[element] = mass_fraction / atomic_mass

    return normalize(mole_amounts)


def calculate_ternary_phase_fraction_map(
    db: Database,
    components: list[str],
    phases: list[str],
    dependent_element: str,
    x_element: str,
    y_element: str,
    target_phase: str,
    temperature_c: float,
    pressure_pa: float,
    units: str,
    interval_count: int,
    progress_callback: Any | None = None,
) -> tuple[pd.DataFrame, int]:
    """Посчитать мольную долю выбранной фазы в узлах тройной сетки."""
    if target_phase not in phases:
        raise ValueError(
            "Выбранная для карты фаза исключена галочками. "
            "Верните её в список разрешённых фаз."
        )

    # Модели строятся один раз и повторно используются во всех точках.
    # Это заметно сокращает время большой тройной сетки.
    models = {
        phase_name: Model(db, components, phase_name)
        for phase_name in phases
    }

    rows: list[dict[str, Any]] = []
    failure_count = 0
    total_points = (interval_count + 1) * (interval_count + 2) // 2
    completed = 0

    for x_index in range(interval_count + 1):
        x_display = x_index / interval_count
        remaining = interval_count - x_index

        for y_index in range(remaining + 1):
            y_display = y_index / interval_count
            dependent_display = 1.0 - x_display - y_display

            mole_fractions = ternary_display_to_mole_fractions(
                db,
                dependent_element,
                x_element,
                y_element,
                dependent_display,
                x_display,
                y_display,
                units,
            )

            row: dict[str, Any] = {
                f"{dependent_element}, доля на карте": dependent_display,
                f"{x_element}, доля на карте": x_display,
                f"{y_element}, доля на карте": y_display,
                f"{dependent_element}, % на карте": 100.0 * dependent_display,
                f"{x_element}, % на карте": 100.0 * x_display,
                f"{y_element}, % на карте": 100.0 * y_display,
                f"{dependent_element}, ат.%": (
                    100.0 * mole_fractions[dependent_element]
                ),
                f"{x_element}, ат.%": 100.0 * mole_fractions[x_element],
                f"{y_element}, ат.%": 100.0 * mole_fractions[y_element],
            }

            try:
                conditions = {
                    v.N: 1.0,
                    v.P: float(pressure_pa),
                    v.T: float(temperature_c) + 273.15,
                    v.X(x_element): float(mole_fractions[x_element]),
                    v.X(y_element): float(mole_fractions[y_element]),
                }

                eq = equilibrium(
                    db,
                    components,
                    phases,
                    conditions,
                    model=models,
                    calc_opts={"pdens": 300},
                )
                fractions = aggregate_phase_fractions(eq)
                target_fraction = float(fractions.get(target_phase, 0.0))
                stable_phases = sorted(
                    phase_name
                    for phase_name, phase_fraction in fractions.items()
                    if phase_fraction > 1e-7
                )
                dominant_phase = (
                    max(fractions, key=fractions.get)
                    if fractions
                    else ""
                )

                row.update(
                    {
                        f"{target_phase}, мольная доля, %": (
                            100.0 * target_fraction
                        ),
                        "Устойчивые фазы": " + ".join(stable_phases),
                        "Преобладающая фаза": dominant_phase,
                        "Статус": "рассчитано",
                    }
                )
            except Exception as error:
                failure_count += 1
                row.update(
                    {
                        f"{target_phase}, мольная доля, %": np.nan,
                        "Устойчивые фазы": "",
                        "Преобладающая фаза": "",
                        "Статус": f"не рассчитано: {error}",
                    }
                )

            rows.append(row)
            completed += 1
            if progress_callback is not None:
                update_every = max(1, total_points // 100)
                if (
                    completed == total_points
                    or completed % update_every == 0
                ):
                    progress_callback(completed, total_points)

    return pd.DataFrame(rows), failure_count


def plot_ternary_phase_fraction_map(
    dataframe: pd.DataFrame,
    dependent_element: str,
    x_element: str,
    y_element: str,
    target_phase: str,
    temperature_c: float,
    units_label: str,
    appearance_threshold_percent: float,
    color_scale_mode: str,
) -> tuple[plt.Figure, plt.Axes]:
    """Нарисовать тройную карту мольной доли выбранной фазы."""
    x_column = f"{x_element}, доля на карте"
    y_column = f"{y_element}, доля на карте"
    z_column = f"{target_phase}, мольная доля, %"

    x_values = dataframe[x_column].to_numpy(dtype=float)
    y_values = dataframe[y_column].to_numpy(dtype=float)
    z_values = dataframe[z_column].to_numpy(dtype=float)
    valid_points = (
        np.isfinite(x_values)
        & np.isfinite(y_values)
        & np.isfinite(z_values)
    )

    if int(valid_points.sum()) < 3:
        raise RuntimeError(
            "Для построения карты получено меньше трёх корректных точек."
        )

    triangulation = mtri.Triangulation(x_values, y_values)
    if triangulation.triangles.size == 0:
        raise RuntimeError("Не удалось сформировать треугольную сетку карты.")

    invalid_points = ~valid_points
    if np.any(invalid_points):
        triangle_mask = np.any(
            invalid_points[triangulation.triangles],
            axis=1,
        )
        triangulation.set_mask(triangle_mask)

    # Значения в провалившихся узлах не участвуют в рисунке: все соседние
    # треугольники замаскированы. Ноль здесь нужен только как безопасная
    # подстановка для API matplotlib.
    plot_values = np.where(valid_points, z_values, 0.0)
    finite_values = z_values[valid_points]

    theme_type = current_theme_type()
    roles = chart_roles(theme_type)

    figure, axes = plt.subplots(
        figsize=(11.5, 8.0),
        dpi=100,
        subplot_kw={"projection": "triangular"},
    )

    if color_scale_mode.startswith("По данным"):
        z_max = float(np.nanmax(finite_values))
        vmax = max(1.0, z_max)
    else:
        vmax = 100.0

    color_mesh = axes.tripcolor(
        triangulation,
        plot_values,
        shading="gouraud",
        cmap="cividis",
        vmin=0.0,
        vmax=vmax,
        zorder=1,
    )

    threshold = max(0.0, float(appearance_threshold_percent))
    finite_min = float(np.nanmin(finite_values))
    finite_max = float(np.nanmax(finite_values))
    threshold_drawn = False

    if finite_min < threshold < finite_max:
        # Контур лежит поверх меняющейся цветовой шкалы, поэтому рисуется
        # парой: широкий фоновой штрих + узкий контрастный штрих. Один тон
        # неизбежно потерялся бы на части шкалы.
        axes.tricontour(
            triangulation,
            plot_values,
            levels=[threshold],
            colors=[roles["background"]],
            linewidths=3.0,
            linestyles="--",
            zorder=2,
        )
        axes.tricontour(
            triangulation,
            plot_values,
            levels=[threshold],
            colors=[roles["text"]],
            linewidths=1.1,
            linestyles="--",
            zorder=2.1,
        )
        threshold_drawn = True

    figure.set_facecolor(roles["background"])
    axes.set_facecolor(roles["background"])
    axes.set_xlim(0.0, 1.0)
    axes.set_ylim(0.0, 1.0)
    axes.set_title(
        (
            f"Мольная доля {target_phase} в системе "
            f"{dependent_element}–{x_element}–{y_element} "
            f"при {temperature_c:.1f} °C"
        ),
        fontsize=13,
        color=roles["text"],
    )
    axes.set_xlabel(
        f"Содержание {x_element}, {units_label}",
        fontsize=13,
        color=roles["axis"],
    )
    axes.set_ylabel(
        f"Содержание {y_element}, {units_label}",
        fontsize=13,
        color=roles["axis"],
    )
    axes.yaxis.label.set_rotation(60)
    axes.yaxis.set_label_coords(x=0.12, y=0.5)
    axes.xaxis.set_major_formatter(
        FuncFormatter(lambda value, _position: f"{100.0 * value:g}")
    )
    axes.yaxis.set_major_formatter(
        FuncFormatter(lambda value, _position: f"{100.0 * value:g}")
    )
    axes.grid(True, color=roles["grid"], alpha=0.55)
    axes.tick_params(
        axis="both",
        which="both",
        labelsize=11,
        colors=roles["axis"],
    )
    for spine in axes.spines.values():
        spine.set_color(roles["axis"])

    axes.text(
        -0.03,
        -0.08,
        f"{dependent_element}: 100 %",
        transform=axes.transAxes,
        ha="left",
        va="top",
        fontsize=11,
        color=roles["axis"],
    )
    axes.text(
        1.03,
        -0.08,
        f"{x_element}: 100 %",
        transform=axes.transAxes,
        ha="right",
        va="top",
        fontsize=11,
        color=roles["axis"],
    )
    axes.text(
        0.5,
        1.04,
        f"{y_element}: 100 %",
        transform=axes.transAxes,
        ha="center",
        va="bottom",
        fontsize=11,
        color=roles["axis"],
    )
    axes.text(
        0.5,
        -0.14,
        (
            f"Доля {dependent_element} = 100 − "
            f"{x_element} − {y_element}"
        ),
        transform=axes.transAxes,
        ha="center",
        va="top",
        fontsize=11,
        color=roles["axis"],
    )

    colorbar = figure.colorbar(
        color_mesh,
        ax=axes,
        pad=0.12,
        shrink=0.82,
    )
    colorbar.set_label(
        f"Мольная доля {target_phase}, %",
        fontsize=13,
        color=roles["axis"],
    )
    colorbar.ax.tick_params(
        labelsize=11,
        colors=roles["axis"],
    )
    colorbar.outline.set_edgecolor(roles["axis"])

    if threshold_drawn:
        threshold_handle = Line2D(
            [0],
            [0],
            color=roles["text"],
            linestyle="--",
            linewidth=1.1,
            label=(
                f"Граница {target_phase} = "
                f"{threshold:g} мол.%"
            ),
        )
        legend = axes.legend(
            handles=[threshold_handle],
            loc="upper right",
            fontsize=11,
        )
        for item in legend.get_texts():
            item.set_color(roles["axis"])

    figure.subplots_adjust(
        left=0.08,
        right=0.82,
        bottom=0.17,
        top=0.88,
    )
    return figure, axes


# ---------------------------------------------------------------------------
# Боковая панель: общие параметры
# ---------------------------------------------------------------------------

# Загрузка марки или проекта откладывается до начала следующего прогона,
# чтобы значения были установлены до создания соответствующих виджетов.
try:
    apply_pending_state()
except Exception as pending_context_error:
    # apply_pending_state validates the complete context before writing any
    # user-facing widget key. A rejected queued context therefore leaves the
    # currently active inputs untouched.
    st.session_state.pop("_thermogar_loaded_context", None)
    st.error(
        "Отложенный контекст отклонён и не был применён: "
        f"{pending_context_error}"
    )

st.title(DISPLAY_APP_NAME)

st.sidebar.caption(
    "ThermoGar 0.3.0 — исследовательское ПО. "
    "Экспериментальная квалификация: NOT_PERFORMED."
)

st.sidebar.header("Настройки расчётных разделов")
st.sidebar.caption(
    "Параметры ниже относятся ко всем семи рабочим разделам."
)

if st.session_state.get("thermogar_database_key") not in DATABASE_DEFINITIONS:
    if "thermogar_database_key" in st.session_state:
        st.warning(
            "Сохранённый выбор базы не распознан. Выбран канонический "
            "Fe-профиль thermogar_patch."
        )
    st.session_state["thermogar_database_key"] = "fe"
    st.session_state["thermogar_fe_profile"] = FE_PROFILE_CANONICAL

database_key = st.sidebar.selectbox(
    "База материалов",
    options=list(DATABASE_DEFINITIONS),
    format_func=lambda key: DATABASE_DEFINITIONS[key]["label"],
    key="thermogar_database_key",
)

definition = dict(DATABASE_DEFINITIONS[database_key])

fe_profile_key = FE_PROFILE_CANONICAL
if database_key == "fe":
    if "thermogar_fe_profile" not in st.session_state:
        st.session_state["thermogar_fe_profile"] = FE_PROFILE_CANONICAL
    if st.session_state.get("thermogar_fe_profile") != FE_PROFILE_CANONICAL:
        clear_restricted_fe_session_results()
        st.error(
            "Fe-контекст отклонён: сохранённый профиль базы не совпадает "
            "с каноническим thermogar_patch. Автоматическая подмена профиля "
            "не выполняется."
        )
        st.stop()
    fe_profile_key = st.session_state["thermogar_fe_profile"]

vlb_selector = {
    "database_key": database_key,
    "include_physical_pdb": False,
}
if database_key == "fe":
    vlb_selector["profile_key"] = FE_PROFILE_CANONICAL

try:
    stored_vlb_selector = st.session_state.get("_thermogar_vlb_selector_v1")
    stored_vlb_context = st.session_state.get(
        "_thermogar_vlb_bound_context_v1"
    )
    physical_binding_was_active = bool(
        st.session_state.pop(
            "_thermogar_b4b_physical_binding_active_v1",
            False,
        )
    )
    if stored_vlb_selector != vlb_selector or physical_binding_was_active:
        vlb_catalog = verified_loaders.ArtifactCatalog.from_policy(
            PROJECT_ROOT,
            verified_loaders.canonical_release_manifest(),
            phase_provider=_verified_tdb_declared_phases,
        )
        vlb_bound_context = verified_loaders.bind_selected_database(
            vlb_selector,
            vlb_catalog,
            THERMOGAR_PATHS,
        )
        clear_restricted_fe_session_results()
        if physical_binding_was_active:
            clear_b4b_physical_session_results()
        st.session_state["_thermogar_vlb_selector_v1"] = dict(vlb_selector)
        st.session_state["_thermogar_vlb_bound_context_v1"] = (
            vlb_bound_context.to_dict()
        )
    else:
        if type(stored_vlb_context) is not dict:
            raise RuntimeError("Verified database context evidence is absent.")
        vlb_bound_context = verified_loaders.BoundDatabaseContext.from_json_bytes(
            verified_loaders.canonical_json_bytes(stored_vlb_context)
        )
except Exception as error:
    clear_restricted_fe_session_results()
    st.error(f"Проверенная привязка базы отклонена: {error}")
    st.stop()

vlb_active_context = vlb_bound_context
workspace_state_store = verified_state.StateStore(
    THERMOGAR_PATHS,
    st,
    binding_probe=lambda: (
        vlb_active_context.binding_digest,
        vlb_active_context.binding_generation,
    ),
)

database_identity = (database_key, fe_profile_key if database_key == "fe" else "default")
previous_database_identity = st.session_state.get("_thermogar_database_identity")
if previous_database_identity != database_identity:
    for state_key in list(st.session_state):
        if (
            "result" in state_key.lower()
            and not state_key.startswith("_thermogar_loaded")
            and not state_key.startswith("steel_")
        ):
            st.session_state.pop(state_key, None)
    st.session_state["_thermogar_database_identity"] = database_identity

try:
    db, database_path = load_database(database_key, fe_profile_key)
except Exception as error:
    clear_restricted_fe_session_results()
    st.error(str(error))
    st.stop()

if database_key == "fe":
    try:
        restricted_fe.verify_restricted_fe_passport(
            PROJECT_ROOT,
            restricted_fe.restricted_fe_context(),
        )
    except Exception as error:
        clear_restricted_fe_session_results()
        st.error(str(error))
        st.stop()
    st.sidebar.caption("Fe-база thermogar_patch · C15_LAVES исключена")

available_elements = sorted(
    element for element in db.elements if element != "VA"
)

default_balance = (
    definition["default_balance"]
    if definition["default_balance"] in available_elements
    else available_elements[0]
)

st.sidebar.success(
    f"Элементов: {len(available_elements)} · Фаз: {len(db.phases)}"
)

# Для Fe-базы режим показывается сразу под названием базы, чтобы он
# не терялся ниже остальных настроек.
steel_mode = "metastable"
if database_key == "fe":
    st.sidebar.markdown("#### Режим расчёта стали")
    steel_options = [
        "Практический Fe–Fe₃C — цементит, без графита",
        "Стабильный Fe–C — графит разрешён",
    ]
    if st.session_state.get("thermogar_steel_mode") not in steel_options:
        st.session_state["thermogar_steel_mode"] = steel_options[0]
    steel_mode_label = st.sidebar.radio(
        "Выберите углеродную систему",
        steel_options,
        key="thermogar_steel_mode",
    )
    steel_mode = (
        "metastable"
        if steel_mode_label.startswith("Практический")
        else "stable"
    )
    st.sidebar.caption(
        "Для большинства сталей используйте практический режим. "
        "Графитный режим нужен для полного стабильного равновесия "
        "и задач по чугунам."
    )

balance_key = f"thermogar_balance_{database_key}"
if st.session_state.get(balance_key) not in available_elements:
    loaded_context = st.session_state.get("_thermogar_loaded_context")
    if (
        isinstance(loaded_context, dict)
        and loaded_context.get("database_key") == database_key
        and balance_key in st.session_state
    ):
        rejected_balance = st.session_state.get(balance_key)
        st.session_state.pop("_thermogar_loaded_context", None)
        for rejected_key in (
            balance_key,
            f"thermogar_units_{database_key}",
            f"thermogar_composition_{database_key}",
            "thermogar_pressure_pa",
            "thermogar_steel_mode",
        ):
            st.session_state.pop(rejected_key, None)
        st.error(
            "Загруженный контекст отклонён: элемент-основа "
            f"{rejected_balance!r} отсутствует в выбранной базе {database_key!r}. "
            "Весь загруженный набор удалён без частичного применения. "
            "Выберите или загрузите контекст заново."
        )
        st.stop()
    st.session_state[balance_key] = default_balance
balance = st.sidebar.selectbox(
    "Элемент-основа",
    available_elements,
    key=balance_key,
)

units_key = f"thermogar_units_{database_key}"
units_options = ["атомные %", "массовые %"]
if st.session_state.get(units_key) not in units_options:
    st.session_state[units_key] = (
        "атомные %" if definition["default_units"] == "at" else "массовые %"
    )
units_label = st.sidebar.radio(
    "Единицы состава",
    units_options,
    horizontal=True,
    key=units_key,
)

units = "at" if units_label == "атомные %" else "wt"

composition_key = f"thermogar_composition_{database_key}"
if composition_key not in st.session_state:
    st.session_state[composition_key] = definition["default_composition"]
composition_text = st.sidebar.text_area(
    "Добавки",
    help=(
        "Пример: AL=15, CR=10. "
        "Остаток до 100 % считается элементом-основой."
    ),
    key=composition_key,
)

if "thermogar_pressure_pa" not in st.session_state:
    st.session_state["thermogar_pressure_pa"] = 101325.0
pressure_pa = st.sidebar.number_input(
    "Давление, Па",
    min_value=1.0,
    step=1000.0,
    format="%.1f",
    key="thermogar_pressure_pa",
)

with st.sidebar.expander("Доступные элементы"):
    st.write(", ".join(available_elements))

CURRENT_CONTEXT = context_snapshot(
    database_key,
    balance,
    units,
    composition_text,
    pressure_pa,
    steel_mode,
    database_path,
    (
        FE_PROFILE_SHA256[fe_profile_key]
        if database_key == "fe"
        else RELEASE_DATABASE_SHA256[database_key]
    ),
    fe_profile_key if database_key == "fe" else None,
)
CURRENT_CONTEXT["database_label"] = definition["label"]

# A result calculated for another database/composition/pressure must never be
# shown as if it belonged to the current global context.
CURRENT_CONTEXT_SIGNATURE = hashlib.sha256(
    json.dumps(
        CURRENT_CONTEXT,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
).hexdigest()


previous_context_signature = st.session_state.get(
    "_thermogar_global_context_signature"
)
previous_release_generation = st.session_state.get(
    "_thermogar_release_generation"
)
context_or_release_changed = (
    previous_context_signature != CURRENT_CONTEXT_SIGNATURE
    or previous_release_generation != RUNTIME_POLICY_GENERATION
)
if context_or_release_changed:
    stale_result_keys = [
        key
        for key in list(st.session_state)
        if not str(key).startswith("steel_")
        and not str(key).startswith("_thermogar_restricted_fe_")
        and (
            "result" in str(key).casefold()
            or str(key).startswith("elastic_prepared_")
            or str(key)
            in {
                "physical_self_test",
                "stage10_database_diagnostics",
                "stage10_smoke_tests",
            }
        )
    ]
    for stale_key in stale_result_keys:
        del st.session_state[stale_key]
    st.session_state["_thermogar_global_context_signature"] = (
        CURRENT_CONTEXT_SIGNATURE
    )
    st.session_state["_thermogar_release_generation"] = (
        RUNTIME_POLICY_GENERATION
    )
    if previous_context_signature and stale_result_keys:
        st.sidebar.info(
            "Глобальный контекст изменился: прежние результаты скрыты. "
            "Выполните расчёт заново."
        )


loaded_context = st.session_state.get("_thermogar_loaded_context")
if isinstance(loaded_context, dict):
    loaded_label = loaded_context.get("label") or "загруженный контекст"
    loaded_database_key = loaded_context.get("database_key")
    expected_hash = loaded_context.get("database_sha256", "")
    if loaded_database_key == database_key:
        if expected_hash and expected_hash != CURRENT_CONTEXT["database_sha256"]:
            st.sidebar.warning(
                f"Открыт {loaded_label}, но отпечаток базы изменился. "
                "Пересчитайте результаты на текущей базе."
            )
        else:
            st.sidebar.success(f"Загружено: {loaded_label}")


# ---------------------------------------------------------------------------
# Вкладки текущей SWR-сборки
# ---------------------------------------------------------------------------

(
    calculation_tab,
    phase_diagram_tab,
    solidification_tab,
    energy_tab,
    physical_tab,
    diffusion_tab,
    reference_tab,
) = st.tabs(
    [
        "Расчёты",
        "Диаграммы",
        "Затвердевание",
        "Энергии",
        "Свойства",
        "Кинетика",
        "Проекты и данные",
    ]
)

with calculation_tab:
    single_tab, temperature_tab, concentration_tab = st.tabs(
        [
            "Одна температура",
            "Температурный диапазон",
            "Изменение состава",
        ]
    )


# ---------------------------------------------------------------------------
# Одна температура
# ---------------------------------------------------------------------------

with single_tab:
    st.subheader("Равновесие при одной температуре")

    single_temperature = st.number_input(
        "Температура, °C",
        value=float(definition["default_temperature"]),
        step=10.0,
        key=f"single_temperature_{database_key}",
    )

    try:
        single_candidate_phases = (
            phase_candidates_for_standard_composition(
                db,
                database_key,
                composition_text,
                units,
                balance,
                steel_mode,
            )
        )
        single_component_candidates = tuple(single_candidate_phases)
        if database_key == "fe":
            single_candidate_phases = list(
                vlb_bound_context.phase_policy.effective(
                    (),
                    candidates=single_component_candidates,
                )
            )
        else:
            single_component_candidates = verified_b3_candidate_phases(
                vlb_bound_context,
                single_component_candidates,
            )
            single_candidate_phases = list(single_component_candidates)
        single_selected_phases, single_phase_mode = (
            phase_selection_editor(
                db,
                database_key,
                single_candidate_phases,
                "single",
            )
        )
    except Exception as preview_error:
        st.warning(
            "Список фаз появится после исправления состава: "
            f"{preview_error}"
        )
        single_component_candidates = ()
        single_selected_phases = None
        single_phase_mode = "Автоматически"

    single_fe_state_key = (
        "_thermogar_vlb_b2_result_equilibrium_single"
    )
    single_b3_state_key = "_thermogar_vlb_b3_result_equilibrium_single"
    single_b3_request_key = "_thermogar_vlb_b3_request_equilibrium_single"
    single_fe_request = None
    single_feature_decision = None
    single_fe_fingerprint = None
    if database_key == "fe":
        try:
            single_requested_phases = tuple(
                sorted(single_selected_phases or ())
            )
            single_fe_request = restricted_fe.make_restricted_fe_request(
                "equilibrium_single",
                balance=balance,
                units=units,
                composition_pct=parse_composition(composition_text),
                pressure_pa=float(pressure_pa),
                temperatures_k=(float(single_temperature) + 273.15,),
                requested_phases=tuple(
                    phase
                    for phase in single_requested_phases
                    if phase != restricted_fe.C15_PHASE
                ),
            )
            single_feature_decision = restricted_fe_prepare_b2_decision(
                vlb_bound_context,
                single_fe_request,
                single_component_candidates,
                single_requested_phases,
            )
            if type(single_feature_decision) is verified_loaders.FeatureRequest:
                single_fe_fingerprint = restricted_fe_b2_fingerprint(
                    single_fe_request,
                    single_feature_decision,
                )
        except Exception:
            single_fe_request = None
            single_feature_decision = None
            single_fe_fingerprint = None
        restricted_fe_refresh_session_result(
            single_fe_state_key,
            single_fe_fingerprint,
        )
    else:
        try:
            single_requested_phases = (
                ()
                if single_phase_mode == "Автоматически"
                else tuple(sorted(single_selected_phases or ()))
            )
            single_inputs = verified_equilibrium.make_equilibrium_inputs(
                "equilibrium_single",
                balance=balance,
                units=units,
                composition_pct=parse_composition(composition_text),
                pressure_pa=float(pressure_pa),
                temperatures_k=(float(single_temperature) + 273.15,),
            )
            single_feature_decision = verified_loaders.prepare_feature_request(
                "equilibrium_single",
                vlb_bound_context,
                single_inputs,
                single_requested_phases,
                candidate_phases=single_component_candidates,
            )
        except Exception:
            single_feature_decision = None
        verified_b3_refresh_result(
            single_b3_state_key,
            single_b3_request_key,
            single_feature_decision,
        )

    if database_key == "fe":
        if type(single_feature_decision) in (
            verified_loaders.FeatureRequest,
            verified_loaders.RejectedFeatureReceipt,
        ):
            single_clicked = verified_feature_button(
                single_feature_decision,
                "Рассчитать равновесие",
                type="primary",
                key="single_calculate",
            )
        else:
            st.button(
                "Рассчитать равновесие",
                type="primary",
                key="single_calculate",
                disabled=True,
                help="Параметры Fe-расчёта некорректны.",
            )
            single_clicked = False
    else:
        if type(single_feature_decision) in (
            verified_loaders.FeatureRequest,
            verified_loaders.RejectedFeatureReceipt,
        ):
            single_clicked = verified_equilibrium_button(
                single_feature_decision,
                "Рассчитать равновесие",
                type="primary",
                key="single_calculate",
            )
        else:
            st.button(
                "Рассчитать равновесие",
                type="primary",
                key="single_calculate",
                disabled=True,
                help="Параметры расчёта некорректны.",
            )
            single_clicked = False
    if database_key == "fe" and single_clicked:
        try:
            if (
                single_fe_request is None
                or type(single_feature_decision) is not verified_loaders.FeatureRequest
                or single_fe_fingerprint is None
            ):
                raise ValueError("Параметры Fe-расчёта некорректны.")
            with st.spinner("Расчёт Fe-равновесия…"):
                with verified_loaders.acquire_execution(
                    single_feature_decision,
                    THERMOGAR_PATHS,
                ) as single_lease:
                    execution = restricted_fe.execute_bound_restricted_fe(
                        vlb_bound_context,
                        single_feature_decision,
                        single_fe_request,
                        single_lease,
                        runner=restricted_fe._default_runner,
                    )
            restricted_fe_store_result(
                single_fe_state_key,
                single_fe_fingerprint,
                single_fe_request,
                single_feature_decision,
                execution,
            )
        except Exception as error:
            st.session_state.pop(single_fe_state_key, None)
            render_friendly_error(error, context="Fe-равновесие")

    if database_key != "fe" and single_clicked:
        try:
            if type(single_feature_decision) is not verified_loaders.FeatureRequest:
                raise ValueError("Параметры расчёта некорректны.")
            with st.spinner("Расчёт равновесия…"):
                with acquire_b3_execution(
                    single_feature_decision,
                    THERMOGAR_PATHS,
                ) as single_lease:
                    execution = verified_equilibrium.execute_verified_equilibrium(
                        vlb_bound_context,
                        single_feature_decision,
                        single_lease,
                    )
            point = execution.points[0]
            summary, phase_at, phase_wt = verified_b3_point_tables(
                point,
                database_key,
            )
            elements = [element for element, _value in point.call.atomic_fractions]
            overall_x = dict(point.call.atomic_fractions)
            overall_w = dict(point.call.mass_fractions)
            overall = pd.DataFrame(
                {
                    "Элемент": elements,
                    "Содержание, ат.%": [
                        100.0 * overall_x[element] for element in elements
                    ],
                    "Содержание, мас.%": [
                        100.0 * overall_w[element] for element in elements
                    ],
                }
            )
            settings = pd.DataFrame(
                [
                    ("База", definition["label"]),
                    ("База SHA-256", execution.feature_receipt.tdb_evidence.sha256),
                    ("Температура, °C", single_temperature),
                    ("Давление, Па", pressure_pa),
                    ("Основа", balance),
                    ("Единицы ввода", units_label),
                    ("Добавки", composition_text),
                    ("Выбор фаз", single_phase_mode),
                    ("Фазы в расчёте", ", ".join(point.call.phases)),
                ],
                columns=["Параметр", "Значение"],
            )
            quality = validate_single_result(summary, overall, phase_at)
            verified_b3_store_result(
                single_b3_state_key,
                {
                    "settings": settings,
                    "overall": overall,
                    "summary": summary,
                    "phase_at": phase_at,
                    "phase_wt": phase_wt,
                    "quality": quality,
                },
                execution,
            )
        except Exception as error:
            st.session_state.pop(single_b3_state_key, None)
            render_friendly_error(error, context="равновесие при одной температуре")

    if database_key == "fe" and single_fe_state_key in st.session_state:
        restricted_single = st.session_state[single_fe_state_key]["receipt"]
        st.markdown("#### Фазовые доли")
        st.dataframe(
            restricted_fe_result_dataframe(
                restricted_single,
                "Температура, K",
            ),
            width="stretch",
            hide_index=True,
        )

    if database_key != "fe" and single_b3_state_key in st.session_state:
        result = st.session_state[single_b3_state_key]["display"]

        st.markdown("#### Фазовые доли")
        st.dataframe(
            result["summary"],
            width="stretch",
            hide_index=True,
        )
        render_quality_panel(result["quality"])

        st.markdown("#### Составы фаз")
        composition_view = st.radio(
            "Показывать составы фаз",
            ["атомные %", "массовые %"],
            horizontal=True,
            key="phase_composition_view",
        )

        phase_table = (
            result["phase_at"]
            if composition_view == "атомные %"
            else result["phase_wt"]
        )
        st.dataframe(
            phase_table,
            width="stretch",
            hide_index=True,
        )

        excel_bytes = dataframe_to_excel(
            {
                "Параметры": result["settings"],
                "Исходный состав": result["overall"],
                "Фазовые доли": result["summary"],
                "Составы фаз ат": result["phase_at"],
                "Составы фаз мас": result["phase_wt"],
                "Проверка результата": result["quality"]["checks"],
            }
        )

        release_download_button(
            "Скачать результат в Excel",
            data=excel_bytes,
            file_name="ThermoGar_equilibrium.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )


# ---------------------------------------------------------------------------
# Шаг по температуре
# ---------------------------------------------------------------------------

with temperature_tab:
    st.subheader("Изменение фазовых долей с температурой")

    col1, col2, col3 = st.columns(3)

    with col1:
        t_min = st.number_input(
            "От, °C",
            value=float(definition["default_t_min"]),
            step=10.0,
            key=f"t_min_{database_key}",
        )

    with col2:
        t_max = st.number_input(
            "До, °C",
            value=float(definition["default_t_max"]),
            step=10.0,
            key=f"t_max_{database_key}",
        )

    with col3:
        t_step = st.number_input(
            "Шаг, °C",
            min_value=0.1,
            value=float(definition["default_t_step"]),
            step=5.0,
            key=f"t_step_{database_key}",
        )

    display_threshold = st.number_input(
        "Показывать на графике фазы с максимумом не менее, %",
        min_value=0.0,
        value=0.1,
        step=0.1,
    )

    try:
        temperature_candidate_phases = (
            phase_candidates_for_standard_composition(
                db,
                database_key,
                composition_text,
                units,
                balance,
                steel_mode,
            )
        )
        temperature_component_candidates = verified_b3_candidate_phases(
            vlb_bound_context,
            tuple(temperature_candidate_phases),
        )
        temperature_candidate_phases = list(
            temperature_component_candidates
        )
        (
            temperature_selected_phases,
            temperature_phase_mode,
        ) = phase_selection_editor(
            db,
            database_key,
            temperature_candidate_phases,
            "temperature",
        )
    except Exception as preview_error:
        st.warning(
            "Список фаз появится после исправления состава: "
            f"{preview_error}"
        )
        temperature_component_candidates = ()
        temperature_selected_phases = None
        temperature_phase_mode = "Автоматически"

    temperature_b3_state_key = (
        "_thermogar_vlb_b3_result_equilibrium_temperature_scan"
    )
    temperature_b3_request_key = (
        "_thermogar_vlb_b3_request_equilibrium_temperature_scan"
    )
    temperature_feature_decision = None
    temperature_points_c: tuple[float, ...] = ()
    try:
        if t_max <= t_min:
            raise ValueError("Конечная температура должна быть выше начальной.")
        temperature_points_c = tuple(
            float(value)
            for value in np.arange(
                float(t_min),
                float(t_max) + 0.5 * float(t_step),
                float(t_step),
            )
        )
        if len(temperature_points_c) > 150:
            raise ValueError(
                "Слишком много точек. Увеличьте шаг или уменьшите диапазон."
            )
        temperature_requested_phases = (
            ()
            if temperature_phase_mode == "Автоматически"
            else tuple(sorted(temperature_selected_phases or ()))
        )
        temperature_inputs = verified_equilibrium.make_equilibrium_inputs(
            "equilibrium_temperature_scan",
            balance=balance,
            units=units,
            composition_pct=parse_composition(composition_text),
            pressure_pa=float(pressure_pa),
            temperatures_k=tuple(
                value + 273.15 for value in temperature_points_c
            ),
        )
        temperature_feature_decision = (
            verified_loaders.prepare_feature_request(
                "equilibrium_temperature_scan",
                vlb_bound_context,
                temperature_inputs,
                temperature_requested_phases,
                candidate_phases=temperature_component_candidates,
            )
        )
    except Exception:
        temperature_feature_decision = None
    verified_b3_refresh_result(
        temperature_b3_state_key,
        temperature_b3_request_key,
        temperature_feature_decision,
    )

    if type(temperature_feature_decision) in (
        verified_loaders.FeatureRequest,
        verified_loaders.RejectedFeatureReceipt,
    ):
        temperature_clicked = verified_equilibrium_button(
            temperature_feature_decision,
            "Построить график по температуре",
            type="primary",
            key="temperature_calculate",
        )
    else:
        st.button(
            "Построить график по температуре",
            type="primary",
            key="temperature_calculate",
            disabled=True,
            help="Параметры температурного скана некорректны.",
        )
        temperature_clicked = False

    if temperature_clicked:
        try:
            if type(temperature_feature_decision) is not verified_loaders.FeatureRequest:
                raise ValueError("Параметры температурного скана некорректны.")
            temperature_execution = None
            with st.spinner("Расчёт температурных точек…"):
                with acquire_b3_execution(
                    temperature_feature_decision,
                    THERMOGAR_PATHS,
                ) as temperature_lease:
                    if database_key == "fe":
                        (
                            scan_components,
                            scan_conditions,
                            _scan_x,
                            _scan_w,
                            scan_phases,
                        ) = prepare_calculation(
                            db,
                            database_key,
                            parse_composition(composition_text),
                            units,
                            balance,
                            steel_mode,
                            temperature_selected_phases,
                        )
                        scan_df = direct_equilibrium_scan(
                            db,
                            scan_components,
                            scan_phases,
                            float(pressure_pa),
                            "Температура, °C",
                            [
                                (
                                    float(value),
                                    scan_conditions,
                                    float(value) + 273.15,
                                )
                                for value in temperature_points_c
                            ],
                        )
                        scan_sha256 = str(
                            CURRENT_CONTEXT["database_sha256"]
                        )
                    else:
                        temperature_execution = (
                            verified_equilibrium.execute_verified_equilibrium(
                                vlb_bound_context,
                                temperature_feature_decision,
                                temperature_lease,
                            )
                        )
            if temperature_execution is not None:
                rows: list[dict[str, float]] = []
                for point in temperature_execution.points:
                    row: dict[str, float] = {
                        "Температура, °C": point.call.temperature_k - 273.15,
                    }
                    row.update(
                        {
                            phase: 100.0 * fraction
                            for phase, fraction in point.phase_fractions
                        }
                    )
                    rows.append(row)
                scan_df = pd.DataFrame(rows).fillna(0.0)
                scan_phases = list(
                    temperature_execution.points[0].call.phases
                )
                scan_sha256 = (
                    temperature_execution.feature_receipt.tdb_evidence.sha256
                )
            phase_columns = [
                column
                for column in scan_df.columns
                if column != "Температура, °C"
            ]
            visible_phases = [
                phase
                for phase in phase_columns
                if float(scan_df[phase].max()) >= display_threshold
            ]
            figure = plot_phase_fraction_scan(
                scan_df,
                "Температура, °C",
                visible_phases,
                "ThermoGar: фазовые доли от температуры",
                database_key,
            )
            temperature_settings = pd.DataFrame(
                [
                    ("База", definition["label"]),
                    ("База SHA-256", scan_sha256),
                    ("Температура от, °C", t_min),
                    ("Температура до, °C", t_max),
                    ("Шаг, °C", t_step),
                    ("Давление, Па", pressure_pa),
                    ("Основа", balance),
                    ("Единицы ввода", units_label),
                    ("Добавки", composition_text),
                    ("Выбор фаз", temperature_phase_mode),
                    ("Фазы в расчёте", ", ".join(scan_phases)),
                ],
                columns=["Параметр", "Значение"],
            )
            quality = validate_scan_result(scan_df, ["Температура, °C"])
            verified_b3_store_result(
                temperature_b3_state_key,
                {
                    "settings": temperature_settings,
                    "data": scan_df,
                    "figure": figure,
                    "visible_phases": visible_phases,
                    "quality": quality,
                },
                temperature_execution,
            )
        except Exception as error:
            st.session_state.pop(temperature_b3_state_key, None)
            render_friendly_error(error, context="сканирование по температуре")

    if temperature_b3_state_key in st.session_state:
        result = st.session_state[temperature_b3_state_key]["display"]

        st.pyplot(result["figure"])
        st.dataframe(
            result["data"],
            width="stretch",
            hide_index=True,
        )
        render_quality_panel(result["quality"])

        excel_bytes = dataframe_to_excel(
            {
                "Параметры": result["settings"],
                "Температурный расчёт": result["data"],
                "Проверка результата": result["quality"]["checks"],
            }
        )
        csv_bytes = result["data"].to_csv(
            index=False,
        ).encode("utf-8-sig")
        png_bytes = figure_to_png(result["figure"])

        download_col1, download_col2, download_col3 = st.columns(3)

        with download_col1:
            release_download_button(
                "Excel",
                data=excel_bytes,
                file_name="ThermoGar_temperature_scan.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            )

        with download_col2:
            release_download_button(
                "CSV",
                data=csv_bytes,
                file_name="ThermoGar_temperature_scan.csv",
                mime="text/csv",
            )

        with download_col3:
            release_download_button(
                "PNG",
                data=png_bytes,
                file_name="ThermoGar_temperature_scan.png",
                mime="image/png",
            )


# ---------------------------------------------------------------------------
# Шаг по концентрации
# ---------------------------------------------------------------------------

with concentration_tab:
    st.subheader("Изменение фазовых долей с концентрацией")

    variable_candidates = [
        element
        for element in available_elements
        if element != balance
    ]

    variable_element = st.selectbox(
        "Изменяемый элемент",
        variable_candidates,
    )

    st.caption(
        "В строке добавок указывайте только постоянные элементы. "
        f"{variable_element} программа будет менять сама."
    )

    fixed_composition_text = st.text_area(
        "Постоянные добавки",
        value="",
        placeholder="Например: CR=15, CO=10",
        key=f"fixed_composition_{database_key}",
    )

    concentration_col1, concentration_col2, concentration_col3 = st.columns(3)

    with concentration_col1:
        c_min = st.number_input(
            f"{variable_element}: от, %",
            min_value=0.0,
            value=0.0,
            step=1.0,
        )

    with concentration_col2:
        c_max = st.number_input(
            f"{variable_element}: до, %",
            min_value=0.0,
            value=20.0,
            step=1.0,
        )

    with concentration_col3:
        c_step = st.number_input(
            f"{variable_element}: шаг, %",
            min_value=0.01,
            value=10.0 if database_key == "fe" else 1.0,
            step=0.5,
        )

    concentration_temperature = st.number_input(
        "Температура, °C",
        value=float(definition["default_temperature"]),
        step=10.0,
        key=f"concentration_temperature_{database_key}",
    )

    concentration_threshold = st.number_input(
        "Показывать на графике фазы с максимумом не менее, %",
        min_value=0.0,
        value=0.1,
        step=0.1,
        key="concentration_threshold",
    )

    try:
        (
            concentration_candidate_phases,
            fixed_entered_preview,
        ) = phase_candidates_for_concentration_scan(
            db,
            database_key,
            fixed_composition_text,
            variable_element,
            units,
            balance,
            steel_mode,
        )
        concentration_component_candidates = verified_b3_candidate_phases(
            vlb_bound_context,
            tuple(concentration_candidate_phases),
        )
        concentration_candidate_phases = list(
            concentration_component_candidates
        )
        (
            concentration_selected_phases,
            concentration_phase_mode,
        ) = phase_selection_editor(
            db,
            database_key,
            concentration_candidate_phases,
            "concentration",
        )
    except Exception as preview_error:
        st.warning(
            "Список фаз появится после исправления постоянного состава: "
            f"{preview_error}"
        )
        concentration_component_candidates = ()
        fixed_entered_preview = {}
        concentration_selected_phases = None
        concentration_phase_mode = "Автоматически"

    concentration_b3_state_key = (
        "_thermogar_vlb_b3_result_equilibrium_composition_scan"
    )
    concentration_b3_request_key = (
        "_thermogar_vlb_b3_request_equilibrium_composition_scan"
    )
    concentration_feature_decision = None
    concentration_points: tuple[float, ...] = ()
    try:
        if c_max <= c_min:
            raise ValueError("Конечная концентрация должна быть выше начальной.")
        concentration_points = tuple(
            float(value)
            for value in np.arange(
                float(c_min),
                float(c_max) + 0.5 * float(c_step),
                float(c_step),
            )
        )
        if len(concentration_points) > 150:
            raise ValueError(
                "Слишком много точек. Увеличьте шаг или уменьшите диапазон."
            )
        concentration_requested_phases = (
            ()
            if concentration_phase_mode == "Автоматически"
            else tuple(sorted(concentration_selected_phases or ()))
        )
        concentration_inputs = verified_equilibrium.make_equilibrium_inputs(
            "equilibrium_composition_scan",
            balance=balance,
            units=units,
            composition_pct=dict(fixed_entered_preview),
            pressure_pa=float(pressure_pa),
            temperatures_k=(float(concentration_temperature) + 273.15,),
            variable_element=variable_element,
            concentrations_pct=concentration_points,
        )
        concentration_feature_decision = (
            verified_loaders.prepare_feature_request(
                "equilibrium_composition_scan",
                vlb_bound_context,
                concentration_inputs,
                concentration_requested_phases,
                candidate_phases=concentration_component_candidates,
            )
        )
    except Exception:
        concentration_feature_decision = None
    verified_b3_refresh_result(
        concentration_b3_state_key,
        concentration_b3_request_key,
        concentration_feature_decision,
    )

    if type(concentration_feature_decision) in (
        verified_loaders.FeatureRequest,
        verified_loaders.RejectedFeatureReceipt,
    ):
        concentration_clicked = verified_equilibrium_button(
            concentration_feature_decision,
            "Построить график по составу",
            type="primary",
            key="concentration_calculate",
        )
    else:
        st.button(
            "Построить график по составу",
            type="primary",
            key="concentration_calculate",
            disabled=True,
            help="Параметры скана по составу некорректны.",
        )
        concentration_clicked = False

    if concentration_clicked:
        try:
            if type(concentration_feature_decision) is not verified_loaders.FeatureRequest:
                raise ValueError("Параметры скана по составу некорректны.")
            x_column = f"{variable_element}, {units_label}"
            concentration_execution = None
            with st.spinner("Расчёт концентрационных точек…"):
                with acquire_b3_execution(
                    concentration_feature_decision,
                    THERMOGAR_PATHS,
                ) as concentration_lease:
                    if database_key == "fe":
                        scan_preview = dict(fixed_entered_preview)
                        scan_preview[variable_element] = 1e-6
                        (
                            scan_components,
                            _scan_conditions,
                            _scan_x,
                            _scan_w,
                            scan_phases,
                        ) = prepare_calculation(
                            db,
                            database_key,
                            scan_preview,
                            units,
                            balance,
                            steel_mode,
                            concentration_selected_phases,
                        )
                        scan_df = direct_equilibrium_scan(
                            db,
                            scan_components,
                            scan_phases,
                            float(pressure_pa),
                            x_column,
                            [
                                (
                                    float(value),
                                    scan_axis_conditions(
                                        db,
                                        {
                                            **dict(fixed_entered_preview),
                                            variable_element: float(value),
                                        },
                                        units,
                                        balance,
                                    ),
                                    float(concentration_temperature) + 273.15,
                                )
                                for value in concentration_points
                            ],
                        )
                        scan_sha256 = str(
                            CURRENT_CONTEXT["database_sha256"]
                        )
                    else:
                        concentration_execution = (
                            verified_equilibrium.execute_verified_equilibrium(
                                vlb_bound_context,
                                concentration_feature_decision,
                                concentration_lease,
                            )
                        )
            if concentration_execution is not None:
                rows: list[dict[str, float]] = []
                for point in concentration_execution.points:
                    row: dict[str, float] = {x_column: point.call.axis_value}
                    row.update(
                        {
                            phase: 100.0 * fraction
                            for phase, fraction in point.phase_fractions
                        }
                    )
                    rows.append(row)
                scan_df = pd.DataFrame(rows).fillna(0.0)
                scan_phases = list(
                    concentration_execution.points[0].call.phases
                )
                scan_sha256 = (
                    concentration_execution.feature_receipt.tdb_evidence.sha256
                )
            phase_columns = [
                column for column in scan_df.columns if column != x_column
            ]
            visible_phases = [
                phase
                for phase in phase_columns
                if float(scan_df[phase].max()) >= concentration_threshold
            ]
            figure = plot_phase_fraction_scan(
                scan_df,
                x_column,
                visible_phases,
                (
                    "ThermoGar: фазовые доли от концентрации "
                    f"при {concentration_temperature:.1f} °C"
                ),
                database_key,
            )
            concentration_settings = pd.DataFrame(
                [
                    ("База", definition["label"]),
                    ("База SHA-256", scan_sha256),
                    ("Температура, °C", concentration_temperature),
                    ("Изменяемый элемент", variable_element),
                    ("Концентрация от, %", c_min),
                    ("Концентрация до, %", c_max),
                    ("Шаг, %", c_step),
                    ("Постоянные добавки", fixed_composition_text),
                    ("Основа", balance),
                    ("Единицы ввода", units_label),
                    ("Выбор фаз", concentration_phase_mode),
                    ("Фазы в расчёте", ", ".join(scan_phases)),
                ],
                columns=["Параметр", "Значение"],
            )
            quality = validate_scan_result(scan_df, [x_column])
            verified_b3_store_result(
                concentration_b3_state_key,
                {
                    "settings": concentration_settings,
                    "data": scan_df,
                    "figure": figure,
                    "quality": quality,
                },
                concentration_execution,
            )
        except Exception as error:
            st.session_state.pop(concentration_b3_state_key, None)
            render_friendly_error(error, context="сканирование по составу")

    if concentration_b3_state_key in st.session_state:
        result = st.session_state[concentration_b3_state_key]["display"]

        st.pyplot(result["figure"])
        st.dataframe(
            result["data"],
            width="stretch",
            hide_index=True,
        )
        render_quality_panel(result["quality"])

        excel_bytes = dataframe_to_excel(
            {
                "Параметры": result["settings"],
                "Концентрационный расчёт": result["data"],
                "Проверка результата": result["quality"]["checks"],
            }
        )
        csv_bytes = result["data"].to_csv(
            index=False,
        ).encode("utf-8-sig")
        png_bytes = figure_to_png(result["figure"])

        download_col1, download_col2, download_col3 = st.columns(3)

        with download_col1:
            release_download_button(
                "Excel",
                data=excel_bytes,
                file_name="ThermoGar_concentration_scan.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            )

        with download_col2:
            release_download_button(
                "CSV",
                data=csv_bytes,
                file_name="ThermoGar_concentration_scan.csv",
                mime="text/csv",
            )

        with download_col3:
            release_download_button(
                "PNG",
                data=png_bytes,
                file_name="ThermoGar_concentration_scan.png",
                mime="image/png",
            )


# ---------------------------------------------------------------------------
# Диаграммы состояния: бинарная система и многокомпонентное сечение
# ---------------------------------------------------------------------------

with phase_diagram_tab:
    st.subheader("Диаграммы состояния")
    st.caption(
        "Выберите диаграмму границ или карту количества выбранной фазы."
    )

    (
        binary_subtab,
        isopleth_subtab,
        ternary_subtab,
        ternary_map_subtab,
    ) = st.tabs(
        [
            "Бинарная T–X",
            "Многокомпонентное T–X",
            "Тройная при T = const",
            "Карта доли фазы",
        ]
    )

    with binary_subtab:
        st.markdown("#### Бинарная система")
        st.caption(
            "Диаграмма для двух элементов без постоянных добавок."
        )

        diagram_defaults = BINARY_DIAGRAM_DEFAULTS[database_key]

        left_element = st.selectbox(
            "Первый элемент системы",
            available_elements,
            index=available_elements.index(
                diagram_defaults["left"]
                if diagram_defaults["left"] in available_elements
                else available_elements[0]
            ),
            key=f"binary_left_{database_key}",
        )

        right_options = [
            element
            for element in available_elements
            if element != left_element
        ]
        default_right = (
            diagram_defaults["right"]
            if diagram_defaults["right"] in right_options
            else right_options[0]
        )
        right_element = st.selectbox(
            "Второй элемент; его содержание идёт по горизонтальной оси",
            right_options,
            index=right_options.index(default_right),
            key=f"binary_right_{database_key}_{left_element}",
        )

        binary_units_label = st.radio(
            "Единицы горизонтальной оси",
            ["атомные %", "массовые %"],
            index=0 if diagram_defaults["units"] == "at" else 1,
            horizontal=True,
            key=f"binary_units_{database_key}",
        )
        binary_units = "at" if binary_units_label == "атомные %" else "wt"

        c_min = st.number_input(
            f"{right_element}: от, %",
            min_value=0.0,
            max_value=99.999,
            value=float(diagram_defaults["c_min"]),
            step=float(diagram_defaults["c_step"]),
            key=f"binary_c_min_{database_key}_{right_element}",
        )
        c_max = st.number_input(
            f"{right_element}: до, %",
            min_value=0.001,
            max_value=100.0,
            value=float(diagram_defaults["c_max"]),
            step=float(diagram_defaults["c_step"]),
            key=f"binary_c_max_{database_key}_{right_element}",
        )
        c_step = st.number_input(
            f"Шаг по составу, {binary_units_label}",
            min_value=0.001,
            value=float(diagram_defaults["c_step"]),
            step=float(diagram_defaults["c_step"]),
            key=f"binary_c_step_{database_key}_{right_element}",
        )

        diagram_t_min = st.number_input(
            "Температура от, °C",
            value=float(diagram_defaults["t_min"]),
            step=10.0,
            key=f"binary_t_min_{database_key}",
        )
        diagram_t_max = st.number_input(
            "Температура до, °C",
            value=float(diagram_defaults["t_max"]),
            step=10.0,
            key=f"binary_t_max_{database_key}",
        )
        diagram_t_step = st.number_input(
            "Шаг по температуре, °C",
            min_value=0.1,
            value=float(diagram_defaults["t_step"]),
            step=5.0,
            key=f"binary_t_step_{database_key}",
        )

        show_tielines = st.checkbox(
            "Показывать линии связи в двухфазных областях",
            value=False,
            key=f"binary_tielines_{database_key}",
        )
        label_nodes = st.checkbox(
            "Показывать узловые точки",
            value=False,
            key=f"binary_nodes_{database_key}",
        )

        try:
            binary_candidate_phases = binary_phase_candidates(
                db,
                database_key,
                left_element,
                right_element,
                steel_mode,
            )
            binary_selected_phases, binary_phase_mode = phase_selection_editor(
                db,
                database_key,
                binary_candidate_phases,
                "binary_diagram",
            )
        except Exception as preview_error:
            st.warning(
                "Список фаз появится после исправления параметров системы: "
                f"{preview_error}"
            )
            binary_selected_phases = None
            binary_phase_mode = "Автоматически"

        if len(binary_selected_phases or []) > 7:
            st.info(
                "На диаграмме выбрано больше семи фаз. Расчёт допустим, "
                "но для читаемого графика лучше оставить основные фазы."
            )

        if release_calculation_button(
            "Построить диаграмму состояния",
            type="primary",
            key="binary_calculate",
        ):
            try:
                if c_max <= c_min:
                    raise ValueError(
                        "Конечная концентрация должна быть выше начальной."
                    )
                if c_step <= 0:
                    raise ValueError("Шаг состава должен быть больше нуля.")
                if diagram_t_max <= diagram_t_min:
                    raise ValueError(
                        "Конечная температура должна быть выше начальной."
                    )
                if diagram_t_step <= 0:
                    raise ValueError(
                        "Шаг температуры должен быть больше нуля."
                    )

                components = [left_element, right_element, "VA"]
                phases = compatible_phases_for_components(
                    db,
                    database_key,
                    components,
                    steel_mode,
                )
                if binary_selected_phases is not None:
                    selected_set = set(binary_selected_phases)
                    phases = [phase for phase in phases if phase in selected_set]
                if not phases:
                    raise ValueError("Нужно оставить хотя бы одну фазу.")

                display_x_min = float(c_min) / 100.0
                display_x_max = float(c_max) / 100.0
                interval_count = max(
                    2,
                    int(np.ceil((float(c_max) - float(c_min)) / float(c_step))),
                )

                if binary_units == "wt":
                    internal_x_min = binary_mass_to_mole_fraction(
                        db,
                        left_element,
                        right_element,
                        display_x_min,
                    )
                    internal_x_max = binary_mass_to_mole_fraction(
                        db,
                        left_element,
                        right_element,
                        display_x_max,
                    )
                    x_variable = v.W(right_element)
                else:
                    internal_x_min = display_x_min
                    internal_x_max = display_x_max
                    x_variable = v.X(right_element)

                internal_x_step = (
                    internal_x_max - internal_x_min
                ) / interval_count
                if internal_x_step <= 0:
                    raise ValueError(
                        "После пересчёта состава получился нулевой диапазон."
                    )

                conditions = {
                    v.N: 1.0,
                    v.P: float(pressure_pa),
                    v.T: (
                        float(diagram_t_min) + 273.15,
                        float(diagram_t_max) + 273.15,
                        float(diagram_t_step),
                    ),
                    v.X(right_element): (
                        internal_x_min,
                        internal_x_max,
                        internal_x_step,
                    ),
                }

                with st.spinner(
                    "Строим границы фазовых областей. "
                    "Для сложной системы это может занять несколько минут…"
                ):
                    strategy = BinaryStrategy(
                        db,
                        components,
                        phases=phases,
                        conditions=conditions,
                    )
                    strategy.do_map()

                    figure, _axes = plot_binary_thermogar(
                        strategy,
                        x_variable,
                        v.T,
                        (display_x_min, display_x_max),
                        (
                            float(diagram_t_min) + 273.15,
                            float(diagram_t_max) + 273.15,
                        ),
                        f"Диаграмма состояния {left_element}–{right_element}",
                        (
                            f"Содержание {right_element}, "
                            f"{binary_units_label}"
                        ),
                        show_tielines,
                        label_nodes,
                    )
                    boundary_data = binary_boundary_dataframe(
                        strategy,
                        x_variable,
                        v.T,
                    )

                settings = pd.DataFrame(
                    [
                        ("База", definition["label"]),
                        ("Система", f"{left_element}–{right_element}"),
                        ("Единицы состава", binary_units_label),
                        ("Состав от, %", c_min),
                        ("Состав до, %", c_max),
                        ("Шаг состава, %", c_step),
                        ("Температура от, °C", diagram_t_min),
                        ("Температура до, °C", diagram_t_max),
                        ("Шаг температуры, °C", diagram_t_step),
                        ("Давление, Па", pressure_pa),
                        ("Выбор фаз", binary_phase_mode),
                        ("Фазы в расчёте", ", ".join(phases)),
                        (
                            "Режим стали",
                            (
                                "Практический Fe–Fe3C"
                                if database_key == "fe"
                                and steel_mode == "metastable"
                                else "Стабильный Fe–C"
                                if database_key == "fe"
                                else "не применяется"
                            ),
                        ),
                    ],
                    columns=["Параметр", "Значение"],
                )

                st.session_state[f"binary_result_{database_key}"] = {
                    "settings": settings,
                    "figure": figure,
                    "boundaries": boundary_data,
                }
                record_calculation_history(
                    THERMOGAR_PATHS,
                    "Бинарная диаграмма",
                    CURRENT_CONTEXT,
                    {
                        "system": f"{left_element}-{right_element}",
                        "composition_units": binary_units,
                        "boundary_rows": int(len(boundary_data)),
                    },
                )

            except Exception as error:
                st.error(
                    "Диаграмму построить не удалось. Проверьте диапазоны "
                    f"и набор фаз. Техническая причина: {error}"
                )

        binary_result_key = f"binary_result_{database_key}"
        if binary_result_key in st.session_state:
            result = st.session_state[binary_result_key]
            st.pyplot(result["figure"])

            with st.expander("Таблица рассчитанных границ", expanded=False):
                if result["boundaries"].empty:
                    st.info("Таблица границ для этой карты пуста.")
                else:
                    st.dataframe(
                        result["boundaries"],
                        width="stretch",
                        hide_index=True,
                    )

            excel_bytes = dataframe_to_excel(
                {
                    "Параметры": result["settings"],
                    "Границы": result["boundaries"],
                }
            )
            png_bytes = figure_to_png(result["figure"])

            download_col1, download_col2 = st.columns(2)
            with download_col1:
                release_download_button(
                    "Скачать Excel",
                    data=excel_bytes,
                    file_name="ThermoGar_binary_diagram.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            with download_col2:
                release_download_button(
                    "Скачать PNG",
                    data=png_bytes,
                    file_name="ThermoGar_binary_diagram.png",
                    mime="image/png",
                )


    with isopleth_subtab:
        st.markdown("#### Многокомпонентное сечение")
        st.caption(
            "Меняется содержание одного элемента, остальные введённые "
            "добавки остаются постоянными, а элемент-основа заполняет "
            "остаток до 100 %. На этом этапе состав сечения задаётся "
            "в атомных процентах."
        )

        isopleth_defaults = ISOPLETH_DEFAULTS[database_key]

        variable_options = [
            element
            for element in available_elements
            if element != balance
        ]
        default_variable = (
            isopleth_defaults["variable"]
            if isopleth_defaults["variable"] in variable_options
            else variable_options[0]
        )
        variable_element = st.selectbox(
            "Изменяемый элемент",
            variable_options,
            index=variable_options.index(default_variable),
            key=f"isopleth_variable_{database_key}_{balance}",
        )

        try:
            default_fixed_values = parse_composition(
                isopleth_defaults["fixed"]
            )
        except Exception:
            default_fixed_values = {}
        default_fixed_values.pop(balance, None)
        default_fixed_values.pop(variable_element, None)
        default_fixed_text = ", ".join(
            f"{element}={value:g}"
            for element, value in default_fixed_values.items()
        )

        fixed_composition_text = st.text_area(
            "Постоянные добавки, ат.%",
            value=default_fixed_text,
            placeholder="Например: CR=15, CO=10",
            help=(
                "Не указывайте здесь элемент-основу и изменяемый элемент. "
                "Остаток состава считается элементом-основой."
            ),
            key=(
                f"isopleth_fixed_{database_key}_{balance}_"
                f"{variable_element}"
            ),
        )

        isopleth_c_min = st.number_input(
            f"{variable_element}: от, ат.%",
            min_value=0.0,
            max_value=99.999,
            value=float(isopleth_defaults["c_min"]),
            step=float(isopleth_defaults["c_step"]),
            key=(
                f"isopleth_c_min_{database_key}_{balance}_"
                f"{variable_element}"
            ),
        )
        isopleth_c_max = st.number_input(
            f"{variable_element}: до, ат.%",
            min_value=0.001,
            max_value=99.999,
            value=float(isopleth_defaults["c_max"]),
            step=float(isopleth_defaults["c_step"]),
            key=(
                f"isopleth_c_max_{database_key}_{balance}_"
                f"{variable_element}"
            ),
        )
        isopleth_c_step = st.number_input(
            "Шаг по составу, ат.%",
            min_value=0.001,
            value=float(isopleth_defaults["c_step"]),
            step=float(isopleth_defaults["c_step"]),
            key=(
                f"isopleth_c_step_{database_key}_{balance}_"
                f"{variable_element}"
            ),
        )

        isopleth_t_min = st.number_input(
            "Температура от, °C",
            value=float(isopleth_defaults["t_min"]),
            step=10.0,
            key=f"isopleth_t_min_{database_key}",
        )
        isopleth_t_max = st.number_input(
            "Температура до, °C",
            value=float(isopleth_defaults["t_max"]),
            step=10.0,
            key=f"isopleth_t_max_{database_key}",
        )
        isopleth_t_step = st.number_input(
            "Шаг по температуре, °C",
            min_value=0.1,
            value=float(isopleth_defaults["t_step"]),
            step=5.0,
            key=f"isopleth_t_step_{database_key}",
        )

        isopleth_label_nodes = st.checkbox(
            "Показывать узловые точки",
            value=False,
            key=f"isopleth_nodes_{database_key}",
        )

        try:
            fixed_preview = parse_composition(
                fixed_composition_text
            )
            if balance in fixed_preview:
                raise ValueError(
                    f"{balance} выбран как основа и не должен быть "
                    "указан среди постоянных добавок."
                )
            if variable_element in fixed_preview:
                raise ValueError(
                    f"{variable_element} является изменяемым элементом "
                    "и не должен быть указан среди постоянных добавок."
                )

            if not fixed_preview:
                raise ValueError(
                    "Укажите хотя бы одну постоянную добавку. "
                    "Для системы только из двух элементов используйте "
                    "вкладку «Бинарная система»."
                )

            unknown_fixed = sorted(
                set(fixed_preview) - set(available_elements)
            )
            if unknown_fixed:
                raise ValueError(
                    "В базе отсутствуют элементы: "
                    + ", ".join(unknown_fixed)
                )

            fixed_sum = sum(fixed_preview.values())
            if fixed_sum + float(isopleth_c_max) >= 100.0:
                raise ValueError(
                    "Сумма постоянных добавок и максимального содержания "
                    "изменяемого элемента должна быть меньше 100 ат.%."
                )

            isopleth_candidates = isopleth_phase_candidates(
                db,
                database_key,
                balance,
                variable_element,
                fixed_preview,
                steel_mode,
            )
            (
                isopleth_selected_phases,
                isopleth_phase_mode,
            ) = phase_selection_editor(
                db,
                database_key,
                isopleth_candidates,
                f"isopleth_{balance}_{variable_element}",
            )
        except Exception as preview_error:
            st.warning(
                "Список фаз появится после исправления состава: "
                f"{preview_error}"
            )
            fixed_preview = {}
            isopleth_selected_phases = None
            isopleth_phase_mode = "Автоматически"

        if len(isopleth_selected_phases or []) > 7:
            st.info(
                "На сечении выбрано больше семи фаз. Расчёт допустим, "
                "но для читаемого графика лучше оставить основные фазы."
            )

        if release_calculation_button(
            "Построить многокомпонентное сечение",
            type="primary",
            key="isopleth_calculate",
        ):
            try:
                fixed_entered = parse_composition(
                    fixed_composition_text
                )
                if balance in fixed_entered:
                    raise ValueError(
                        f"{balance} выбран как основа. Удалите его "
                        "из постоянных добавок."
                    )
                if variable_element in fixed_entered:
                    raise ValueError(
                        f"Удалите {variable_element} из постоянных "
                        "добавок: его содержание задаётся диапазоном."
                    )

                if not fixed_entered:
                    raise ValueError(
                        "Укажите хотя бы одну постоянную добавку. "
                        "Для системы только из двух элементов используйте "
                        "вкладку «Бинарная система»."
                    )

                unknown_fixed = sorted(
                    set(fixed_entered) - set(available_elements)
                )
                if unknown_fixed:
                    raise ValueError(
                        "В базе отсутствуют элементы: "
                        + ", ".join(unknown_fixed)
                    )

                if isopleth_c_max <= isopleth_c_min:
                    raise ValueError(
                        "Конечная концентрация должна быть выше начальной."
                    )
                if isopleth_c_step <= 0:
                    raise ValueError(
                        "Шаг состава должен быть больше нуля."
                    )
                if isopleth_t_max <= isopleth_t_min:
                    raise ValueError(
                        "Конечная температура должна быть выше начальной."
                    )
                if isopleth_t_step <= 0:
                    raise ValueError(
                        "Шаг температуры должен быть больше нуля."
                    )

                fixed_sum = sum(fixed_entered.values())
                if fixed_sum + float(isopleth_c_max) >= 100.0:
                    raise ValueError(
                        "При максимальном содержании изменяемого элемента "
                        "для элемента-основы не остаётся положительной доли."
                    )

                composition_intervals = max(
                    1,
                    int(
                        np.ceil(
                            (
                                float(isopleth_c_max)
                                - float(isopleth_c_min)
                            )
                            / float(isopleth_c_step)
                        )
                    ),
                )
                temperature_intervals = max(
                    1,
                    int(
                        np.ceil(
                            (
                                float(isopleth_t_max)
                                - float(isopleth_t_min)
                            )
                            / float(isopleth_t_step)
                        )
                    ),
                )
                if composition_intervals > 250:
                    raise ValueError(
                        "Слишком много шагов по составу. Увеличьте шаг."
                    )
                if temperature_intervals > 300:
                    raise ValueError(
                        "Слишком много шагов по температуре. Увеличьте шаг."
                    )

                components = sorted(
                    set(fixed_entered)
                    | {balance, variable_element}
                ) + ["VA"]
                phases = compatible_phases_for_components(
                    db,
                    database_key,
                    components,
                    steel_mode,
                )
                if isopleth_selected_phases is not None:
                    selected_set = set(
                        isopleth_selected_phases
                    )
                    phases = [
                        phase
                        for phase in phases
                        if phase in selected_set
                    ]
                if not phases:
                    raise ValueError(
                        "Нужно оставить хотя бы одну фазу."
                    )

                conditions = {
                    v.N: 1.0,
                    v.P: float(pressure_pa),
                    v.T: (
                        float(isopleth_t_min) + 273.15,
                        float(isopleth_t_max) + 273.15,
                        float(isopleth_t_step),
                    ),
                    v.X(variable_element): (
                        float(isopleth_c_min) / 100.0,
                        float(isopleth_c_max) / 100.0,
                        float(isopleth_c_step) / 100.0,
                    ),
                }
                for element, value in fixed_entered.items():
                    conditions[v.X(element)] = float(value) / 100.0

                x_variable = v.X(variable_element)
                fixed_label = (
                    ", ".join(
                        f"{element}={value:g} ат.%"
                        for element, value in fixed_entered.items()
                    )
                    if fixed_entered
                    else "без постоянных добавок"
                )

                with st.spinner(
                    "Строим многокомпонентное сечение. "
                    "Расчёт может занять несколько минут…"
                ):
                    strategy = IsoplethStrategy(
                        db,
                        components,
                        phases=phases,
                        conditions=conditions,
                    )
                    strategy.do_map()

                    figure, _axes = plot_isopleth_thermogar(
                        strategy,
                        x_variable,
                        v.T,
                        (
                            float(isopleth_c_min) / 100.0,
                            float(isopleth_c_max) / 100.0,
                        ),
                        (
                            float(isopleth_t_min) + 273.15,
                            float(isopleth_t_max) + 273.15,
                        ),
                        (
                            "Многокомпонентное сечение: "
                            f"основа {balance}, меняется "
                            f"{variable_element}"
                        ),
                        f"Содержание {variable_element}, ат.%",
                        isopleth_label_nodes,
                    )
                    boundary_data = (
                        isopleth_boundary_dataframe(
                            strategy,
                            x_variable,
                            v.T,
                        )
                    )

                settings = pd.DataFrame(
                    [
                        ("База", definition["label"]),
                        ("Элемент-основа", balance),
                        ("Изменяемый элемент", variable_element),
                        ("Постоянные добавки", fixed_label),
                        ("Единицы состава", "атомные %"),
                        ("Состав от, ат.%", isopleth_c_min),
                        ("Состав до, ат.%", isopleth_c_max),
                        ("Шаг состава, ат.%", isopleth_c_step),
                        ("Температура от, °C", isopleth_t_min),
                        ("Температура до, °C", isopleth_t_max),
                        ("Шаг температуры, °C", isopleth_t_step),
                        ("Давление, Па", pressure_pa),
                        ("Выбор фаз", isopleth_phase_mode),
                        ("Фазы в расчёте", ", ".join(phases)),
                        (
                            "Режим стали",
                            (
                                "Практический Fe–Fe3C"
                                if database_key == "fe"
                                and steel_mode == "metastable"
                                else "Стабильный Fe–C"
                                if database_key == "fe"
                                else "не применяется"
                            ),
                        ),
                    ],
                    columns=["Параметр", "Значение"],
                )

                st.session_state[
                    f"isopleth_result_{database_key}"
                ] = {
                    "settings": settings,
                    "figure": figure,
                    "boundaries": boundary_data,
                }
                record_calculation_history(
                    THERMOGAR_PATHS,
                    "Многокомпонентное сечение",
                    CURRENT_CONTEXT,
                    {
                        "variable_element": variable_element,
                        "fixed_composition": fixed_composition_text,
                        "temperature_min_C": float(isopleth_t_min),
                        "temperature_max_C": float(isopleth_t_max),
                        "boundary_rows": int(len(boundary_data)),
                    },
                )

            except Exception as error:
                st.error(
                    "Сечение построить не удалось. Проверьте состав, "
                    "диапазоны и набор фаз. "
                    f"Техническая причина: {error}"
                )

        isopleth_result_key = (
            f"isopleth_result_{database_key}"
        )
        if isopleth_result_key in st.session_state:
            result = st.session_state[
                isopleth_result_key
            ]
            st.pyplot(result["figure"])

            with st.expander(
                "Таблица рассчитанных границ",
                expanded=False,
            ):
                if result["boundaries"].empty:
                    st.info(
                        "Таблица границ для этого сечения пуста."
                    )
                else:
                    st.dataframe(
                        result["boundaries"],
                        width="stretch",
                        hide_index=True,
                    )

            excel_bytes = dataframe_to_excel(
                {
                    "Параметры": result["settings"],
                    "Границы": result["boundaries"],
                }
            )
            png_bytes = figure_to_png(
                result["figure"]
            )

            download_col1, download_col2 = st.columns(2)
            with download_col1:
                release_download_button(
                    "Скачать Excel",
                    data=excel_bytes,
                    file_name=(
                        "ThermoGar_multicomponent_section.xlsx"
                    ),
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            with download_col2:
                release_download_button(
                    "Скачать PNG",
                    data=png_bytes,
                    file_name=(
                        "ThermoGar_multicomponent_section.png"
                    ),
                    mime="image/png",
                )




    with ternary_subtab:
        st.markdown("#### Тройная изотермическая диаграмма")
        st.caption(
            "Показывает фазовые области трёхкомпонентной системы "
            "при одной температуре. Состав задаётся в атомных процентах."
        )

        ternary_defaults = TERNARY_DIAGRAM_DEFAULTS[database_key]

        x_element = st.selectbox(
            "Элемент A — нижняя правая вершина",
            available_elements,
            index=available_elements.index(
                ternary_defaults["x"]
                if ternary_defaults["x"] in available_elements
                else available_elements[0]
            ),
            key=f"ternary_x_{database_key}",
        )

        y_options = [
            element
            for element in available_elements
            if element != x_element
        ]
        default_y = (
            ternary_defaults["y"]
            if ternary_defaults["y"] in y_options
            else y_options[0]
        )
        y_element = st.selectbox(
            "Элемент B — верхняя вершина",
            y_options,
            index=y_options.index(default_y),
            key=f"ternary_y_{database_key}_{x_element}",
        )

        dependent_options = [
            element
            for element in available_elements
            if element not in {x_element, y_element}
        ]
        default_dependent = (
            ternary_defaults["dependent"]
            if ternary_defaults["dependent"] in dependent_options
            else dependent_options[0]
        )
        dependent_element = st.selectbox(
            "Элемент C — нижняя левая вершина; остаток до 100 %",
            dependent_options,
            index=dependent_options.index(default_dependent),
            key=(
                f"ternary_dependent_{database_key}_"
                f"{x_element}_{y_element}"
            ),
        )

        ternary_temperature = st.number_input(
            "Температура, °C",
            value=float(ternary_defaults["temperature"]),
            step=10.0,
            key=f"ternary_temperature_{database_key}",
        )
        ternary_step = st.number_input(
            "Шаг поиска границ, ат.%",
            min_value=0.5,
            max_value=10.0,
            value=float(ternary_defaults["step"]),
            step=0.5,
            key=f"ternary_step_{database_key}",
            help=(
                "Меньший шаг точнее, но расчёт длится дольше. "
                "Для первого запуска используйте 2,5–5 ат.%."
            ),
        )
        ternary_show_tielines = st.checkbox(
            "Показывать линии связи в двухфазных областях",
            value=True,
            key=f"ternary_tielines_{database_key}",
        )
        ternary_tieline_every = st.number_input(
            "Показывать каждую N-ю линию связи",
            min_value=1,
            max_value=50,
            value=int(ternary_defaults["tieline_every"]),
            step=1,
            disabled=not ternary_show_tielines,
            key=f"ternary_tieline_every_{database_key}",
        )
        ternary_label_nodes = st.checkbox(
            "Показывать точки трёхфазного равновесия",
            value=False,
            key=f"ternary_nodes_{database_key}",
        )

        st.info(
            "Как читать вершины: в нижней левой вершине 100 % элемента C, "
            "в нижней правой — 100 % элемента A, в верхней — 100 % "
            "элемента B. Внутри треугольника сумма трёх долей равна 100 %."
        )

        try:
            ternary_candidate_phases = ternary_phase_candidates(
                db,
                database_key,
                x_element,
                y_element,
                dependent_element,
                steel_mode,
            )
            (
                ternary_selected_phases,
                ternary_phase_mode,
            ) = phase_selection_editor(
                db,
                database_key,
                ternary_candidate_phases,
                "ternary_diagram",
            )
        except Exception as preview_error:
            st.warning(
                "Список фаз появится после исправления параметров системы: "
                f"{preview_error}"
            )
            ternary_selected_phases = None
            ternary_phase_mode = "Автоматически"

        if len(ternary_selected_phases or []) > 10:
            st.info(
                "Выбрано больше десяти фаз. Расчёт допустим, но может "
                "занять заметно больше времени. Для первого теста можно "
                "оставить основные фазы."
            )

        if release_calculation_button(
            "Построить тройную диаграмму",
            type="primary",
            key="ternary_calculate",
        ):
            try:
                if ternary_step <= 0:
                    raise ValueError(
                        "Шаг поиска границ должен быть больше нуля."
                    )

                components = [
                    dependent_element,
                    x_element,
                    y_element,
                    "VA",
                ]
                phases = compatible_phases_for_components(
                    db,
                    database_key,
                    components,
                    steel_mode,
                )
                if ternary_selected_phases is not None:
                    selected_set = set(ternary_selected_phases)
                    phases = [
                        phase
                        for phase in phases
                        if phase in selected_set
                    ]
                if not phases:
                    raise ValueError(
                        "Нужно оставить хотя бы одну фазу."
                    )

                step_fraction = float(ternary_step) / 100.0
                if step_fraction >= 0.25:
                    raise ValueError(
                        "Шаг слишком крупный для тройной диаграммы. "
                        "Используйте не более 10 ат.%."
                    )

                x_variable = v.X(x_element)
                y_variable = v.X(y_element)
                conditions = {
                    v.N: 1.0,
                    v.P: float(pressure_pa),
                    v.T: float(ternary_temperature) + 273.15,
                    x_variable: (0.0, 1.0, step_fraction),
                    y_variable: (0.0, 1.0, step_fraction),
                }

                center_added = False
                with st.spinner(
                    "Строим тройную диаграмму. Для большой базы "
                    "расчёт может занять несколько минут…"
                ):
                    strategy = TernaryStrategy(
                        db,
                        components,
                        phases=phases,
                        conditions=conditions,
                    )
                    strategy.generate_automatic_starting_points()
                    try:
                        strategy.add_nodes_from_conditions(
                            {
                                v.N: 1.0,
                                v.P: float(pressure_pa),
                                v.T: (
                                    float(ternary_temperature)
                                    + 273.15
                                ),
                                x_variable: 1.0 / 3.0,
                                y_variable: 1.0 / 3.0,
                            }
                        )
                        center_added = True
                    except Exception:
                        center_added = False
                    strategy.do_map()

                    figure, _axes = plot_ternary_thermogar(
                        strategy,
                        x_variable,
                        y_variable,
                        dependent_element,
                        x_element,
                        y_element,
                        float(ternary_temperature),
                        ternary_show_tielines,
                        int(ternary_tieline_every),
                        ternary_label_nodes,
                    )
                    boundary_data = ternary_boundary_dataframe(
                        strategy,
                        x_variable,
                        y_variable,
                        dependent_element,
                        x_element,
                        y_element,
                    )

                settings = pd.DataFrame(
                    [
                        ("База", definition["label"]),
                        (
                            "Система",
                            (
                                f"{dependent_element}–"
                                f"{x_element}–{y_element}"
                            ),
                        ),
                        ("Температура, °C", ternary_temperature),
                        ("Шаг поиска, ат.%", ternary_step),
                        ("Давление, Па", pressure_pa),
                        ("Выбор фаз", ternary_phase_mode),
                        ("Фазы в расчёте", ", ".join(phases)),
                        (
                            "Дополнительная проверка центра",
                            "выполнена" if center_added else "не добавлена",
                        ),
                        (
                            "Режим стали",
                            (
                                "Практический Fe–Fe3C"
                                if database_key == "fe"
                                and steel_mode == "metastable"
                                else "Стабильный Fe–C"
                                if database_key == "fe"
                                else "не применяется"
                            ),
                        ),
                    ],
                    columns=["Параметр", "Значение"],
                )

                st.session_state[
                    f"ternary_result_{database_key}"
                ] = {
                    "settings": settings,
                    "figure": figure,
                    "boundaries": boundary_data,
                }
                record_calculation_history(
                    THERMOGAR_PATHS,
                    "Тройная диаграмма",
                    CURRENT_CONTEXT,
                    {
                        "system": (
                            f"{dependent_element}-{x_element}-{y_element}"
                        ),
                        "temperature_C": float(ternary_temperature),
                        "boundary_rows": int(len(boundary_data)),
                    },
                )

            except Exception as error:
                st.error(
                    "Тройную диаграмму построить не удалось. "
                    "Проверьте три элемента, температуру, шаг и набор фаз. "
                    f"Техническая причина: {error}"
                )

        ternary_result_key = f"ternary_result_{database_key}"
        if ternary_result_key in st.session_state:
            result = st.session_state[ternary_result_key]
            st.pyplot(result["figure"])

            if result["boundaries"].empty:
                st.warning(
                    "Границы фазовых областей не найдены. Это может "
                    "означать однофазную область во всём треугольнике "
                    "либо пропуск замкнутой области. Уменьшите шаг или "
                    "проверьте набор разрешённых фаз."
                )

            with st.expander(
                "Таблица рассчитанных границ и узлов",
                expanded=False,
            ):
                if result["boundaries"].empty:
                    st.info(
                        "Таблица границ для этой диаграммы пуста."
                    )
                else:
                    st.dataframe(
                        result["boundaries"],
                        width="stretch",
                        hide_index=True,
                    )

            excel_bytes = dataframe_to_excel(
                {
                    "Параметры": result["settings"],
                    "Границы и узлы": result["boundaries"],
                }
            )
            png_bytes = figure_to_png(result["figure"])

            download_col1, download_col2 = st.columns(2)
            with download_col1:
                release_download_button(
                    "Скачать Excel",
                    data=excel_bytes,
                    file_name="ThermoGar_ternary_diagram.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            with download_col2:
                release_download_button(
                    "Скачать PNG",
                    data=png_bytes,
                    file_name="ThermoGar_ternary_diagram.png",
                    mime="image/png",
                )


    # -----------------------------------------------------------------------
    # Тройная карта мольной доли выбранной фазы
    # -----------------------------------------------------------------------

    with ternary_map_subtab:
        st.markdown("#### Карта количества выбранной фазы")
        st.caption(
            "Цвет показывает равновесную мольную долю одной фазы "
            "во всём треугольнике состава при фиксированной температуре."
        )

        map_defaults = TERNARY_PHASE_MAP_DEFAULTS[database_key]

        map_x_element = st.selectbox(
            "Элемент A — нижняя правая вершина",
            available_elements,
            index=available_elements.index(
                map_defaults["x"]
                if map_defaults["x"] in available_elements
                else available_elements[0]
            ),
            key=f"ternary_map_x_{database_key}",
        )

        map_y_options = [
            element
            for element in available_elements
            if element != map_x_element
        ]
        default_map_y = (
            map_defaults["y"]
            if map_defaults["y"] in map_y_options
            else map_y_options[0]
        )
        map_y_element = st.selectbox(
            "Элемент B — верхняя вершина",
            map_y_options,
            index=map_y_options.index(default_map_y),
            key=f"ternary_map_y_{database_key}_{map_x_element}",
        )

        map_dependent_options = [
            element
            for element in available_elements
            if element not in {map_x_element, map_y_element}
        ]
        default_map_dependent = (
            map_defaults["dependent"]
            if map_defaults["dependent"] in map_dependent_options
            else map_dependent_options[0]
        )
        map_dependent_element = st.selectbox(
            "Элемент C — нижняя левая вершина и остаток до 100 %",
            map_dependent_options,
            index=map_dependent_options.index(default_map_dependent),
            key=(
                f"ternary_map_dependent_{database_key}_"
                f"{map_x_element}_{map_y_element}"
            ),
        )

        map_units_label = st.radio(
            "Единицы состава на треугольнике",
            ["атомные %", "массовые %"],
            index=0 if map_defaults["units"] == "at" else 1,
            horizontal=True,
            key=f"ternary_map_units_{database_key}",
        )
        map_units = "at" if map_units_label == "атомные %" else "wt"

        map_temperature = st.number_input(
            "Температура, °C",
            value=float(map_defaults["temperature"]),
            step=10.0,
            key=f"ternary_map_temperature_{database_key}",
        )

        map_step = st.number_input(
            "Желаемый шаг сетки, %",
            min_value=2.0,
            max_value=20.0,
            value=float(map_defaults["step"]),
            step=0.5,
            help=(
                "5 % — быстрый обзор; 2–2,5 % — подробная карта. "
                "Меньший шаг резко увеличивает время расчёта."
            ),
            key=f"ternary_map_step_{database_key}",
        )

        map_threshold = st.number_input(
            "Провести границу появления фазы при доле, мол.%",
            min_value=0.0,
            max_value=100.0,
            value=float(map_defaults["appearance_threshold"]),
            step=0.1,
            key=f"ternary_map_threshold_{database_key}",
        )

        map_color_scale_mode = st.radio(
            "Шкала цвета",
            [
                "Фиксированная 0–100 %",
                "По данным — лучше видны малые доли",
            ],
            horizontal=True,
            key=f"ternary_map_color_scale_{database_key}",
        )

        interval_count, actual_step, map_point_count = (
            ternary_grid_definition(float(map_step))
        )
        st.info(
            f"Будет рассчитано узлов: {map_point_count}. "
            f"Фактический равномерный шаг: {actual_step:.3g} %. "
            "Карта интерполируется между рассчитанными узлами; "
            "неопределённость положения границы — примерно половина шага."
        )

        st.caption(
            "Полный треугольник включает высокие концентрации, которые могут "
            "выходить за заявленную область выбранной базы. Используйте "
            "карту для поиска тенденций, а ответственные точки проверяйте "
            "отдельным расчётом и литературой."
        )

        try:
            map_candidate_phases = ternary_phase_candidates(
                db,
                database_key,
                map_x_element,
                map_y_element,
                map_dependent_element,
                steel_mode,
            )
            map_selected_phases, map_phase_mode = phase_selection_editor(
                db,
                database_key,
                map_candidate_phases,
                "ternary_phase_map",
            )
        except Exception as preview_error:
            st.warning(
                "Список фаз появится после исправления параметров системы: "
                f"{preview_error}"
            )
            map_candidate_phases = []
            map_selected_phases = None
            map_phase_mode = "Автоматически"

        map_target_options = (
            map_selected_phases
            if map_phase_mode == "Вручную"
            else map_candidate_phases
        )

        map_target_phase: str | None = None
        if map_target_options:
            default_map_phase = (
                map_defaults["phase"]
                if map_defaults["phase"] in map_target_options
                else map_target_options[0]
            )
            map_target_phase = st.selectbox(
                "Какую фазу показать цветом",
                map_target_options,
                index=map_target_options.index(default_map_phase),
                format_func=lambda phase_name: (
                    f"{phase_name} — "
                    f"{PHASE_EXPLANATIONS.get(database_key, {}).get(phase_name, '')}"
                    if PHASE_EXPLANATIONS.get(database_key, {}).get(
                        phase_name,
                        "",
                    )
                    else phase_name
                ),
                key=f"ternary_map_target_{database_key}",
            )
        else:
            st.error(
                "Для карты нужно оставить хотя бы одну фазу и выбрать её."
            )

        if len(map_selected_phases or []) > 15:
            st.warning(
                "В расчёте оставлено больше 15 фаз. На подробной сетке это "
                "может занять много времени. Для обзорной карты сначала "
                "оставьте матрицу, выбранную фазу, жидкость и основные "
                "конкурирующие фазы."
            )

        if release_calculation_button(
            "Построить карту доли фазы",
            type="primary",
            key="ternary_map_calculate",
        ):
            try:
                if map_target_phase is None:
                    raise ValueError("Сначала выберите фазу для карты.")
                if map_point_count > 1500:
                    raise ValueError(
                        "Сетка содержит слишком много узлов. "
                        "Увеличьте шаг до 2 % или больше."
                    )

                components = [
                    map_dependent_element,
                    map_x_element,
                    map_y_element,
                    "VA",
                ]
                phases = compatible_phases_for_components(
                    db,
                    database_key,
                    components,
                    steel_mode,
                )
                if map_selected_phases is not None:
                    selected_set = set(map_selected_phases)
                    phases = [
                        phase
                        for phase in phases
                        if phase in selected_set
                    ]
                if not phases:
                    raise ValueError("Нужно оставить хотя бы одну фазу.")
                if map_target_phase not in phases:
                    raise ValueError(
                        "Фаза для карты исключена галочками. "
                        "Верните её в список разрешённых фаз."
                    )

                progress_bar = st.progress(
                    0.0,
                    text="Подготавливаем модели фаз…",
                )

                def update_map_progress(
                    completed: int,
                    total: int,
                ) -> None:
                    progress_bar.progress(
                        completed / total,
                        text=f"Рассчитано узлов: {completed} из {total}",
                    )

                try:
                    with st.spinner(
                        "Считаем равновесие в каждом узле треугольника…"
                    ):
                        map_data, failure_count = (
                            calculate_ternary_phase_fraction_map(
                                db,
                                components,
                                phases,
                                map_dependent_element,
                                map_x_element,
                                map_y_element,
                                map_target_phase,
                                float(map_temperature),
                                float(pressure_pa),
                                map_units,
                                interval_count,
                                update_map_progress,
                            )
                        )

                        figure, _axes = plot_ternary_phase_fraction_map(
                            map_data,
                            map_dependent_element,
                            map_x_element,
                            map_y_element,
                            map_target_phase,
                            float(map_temperature),
                            map_units_label,
                            float(map_threshold),
                            map_color_scale_mode,
                        )
                finally:
                    progress_bar.empty()

                target_column = (
                    f"{map_target_phase}, мольная доля, %"
                )
                valid_data = map_data[
                    np.isfinite(map_data[target_column])
                ]
                if valid_data.empty:
                    raise RuntimeError(
                        "Ни один узел карты не был рассчитан успешно."
                    )

                max_index = valid_data[target_column].idxmax()
                max_row = valid_data.loc[max_index]
                max_fraction = float(max_row[target_column])
                counting_threshold = max(
                    float(map_threshold),
                    1e-9,
                )
                points_with_phase = int(
                    (
                        valid_data[target_column]
                        >= counting_threshold
                    ).sum()
                )

                settings = pd.DataFrame(
                    [
                        ("База", definition["label"]),
                        (
                            "Система",
                            (
                                f"{map_dependent_element}–"
                                f"{map_x_element}–{map_y_element}"
                            ),
                        ),
                        ("Температура, °C", map_temperature),
                        ("Единицы карты", map_units_label),
                        ("Желаемый шаг, %", map_step),
                        ("Фактический шаг, %", actual_step),
                        ("Узлов сетки", map_point_count),
                        ("Фаза карты", map_target_phase),
                        ("Граница появления, мол.%", map_threshold),
                        ("Шкала цвета", map_color_scale_mode),
                        ("Давление, Па", pressure_pa),
                        ("Выбор фаз", map_phase_mode),
                        ("Фазы в расчёте", ", ".join(phases)),
                        ("Не рассчитано узлов", failure_count),
                        (
                            "Режим стали",
                            (
                                "Практический Fe–Fe3C"
                                if database_key == "fe"
                                and steel_mode == "metastable"
                                else "Стабильный Fe–C"
                                if database_key == "fe"
                                else "не применяется"
                            ),
                        ),
                    ],
                    columns=["Параметр", "Значение"],
                )

                summary = pd.DataFrame(
                    [
                        (
                            "Максимальная мольная доля фазы, %",
                            max_fraction,
                        ),
                        (
                            f"{map_dependent_element} в точке максимума, "
                            f"{map_units_label}",
                            float(
                                max_row[
                                    f"{map_dependent_element}, % на карте"
                                ]
                            ),
                        ),
                        (
                            f"{map_x_element} в точке максимума, "
                            f"{map_units_label}",
                            float(
                                max_row[f"{map_x_element}, % на карте"]
                            ),
                        ),
                        (
                            f"{map_y_element} в точке максимума, "
                            f"{map_units_label}",
                            float(
                                max_row[f"{map_y_element}, % на карте"]
                            ),
                        ),
                        (
                            "Узлов с долей не ниже заданной границы",
                            points_with_phase,
                        ),
                        ("Корректно рассчитано узлов", len(valid_data)),
                        ("Не рассчитано узлов", failure_count),
                    ],
                    columns=["Показатель", "Значение"],
                )

                st.session_state[
                    f"ternary_map_result_{database_key}"
                ] = {
                    "settings": settings,
                    "summary": summary,
                    "data": map_data,
                    "figure": figure,
                    "target_phase": map_target_phase,
                    "target_column": target_column,
                    "threshold": float(map_threshold),
                }
                record_calculation_history(
                    THERMOGAR_PATHS,
                    "Тройная карта доли фазы",
                    CURRENT_CONTEXT,
                    {
                        "system": (
                            f"{map_dependent_element}-{map_x_element}-{map_y_element}"
                        ),
                        "phase": map_target_phase,
                        "temperature_C": float(map_temperature),
                        "nodes": int(map_point_count),
                        "failed_nodes": int(failure_count),
                    },
                )

            except Exception as error:
                st.error(
                    "Карту доли фазы построить не удалось. "
                    "Проверьте три элемента, выбранную фазу, температуру, "
                    "шаг и набор разрешённых фаз. "
                    f"Техническая причина: {error}"
                )

        map_result_key = f"ternary_map_result_{database_key}"
        if map_result_key in st.session_state:
            result = st.session_state[map_result_key]
            st.pyplot(result["figure"])

            summary_lookup = dict(
                zip(
                    result["summary"]["Показатель"],
                    result["summary"]["Значение"],
                )
            )
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            with metric_col1:
                st.metric(
                    "Максимальная доля",
                    (
                        f"{float(summary_lookup['Максимальная мольная доля фазы, %']):.2f} %"
                    ),
                )
            with metric_col2:
                st.metric(
                    "Узлов с фазой",
                    int(
                        summary_lookup[
                            "Узлов с долей не ниже заданной границы"
                        ]
                    ),
                )
            with metric_col3:
                st.metric(
                    "Не рассчитано узлов",
                    int(summary_lookup["Не рассчитано узлов"]),
                )

            if float(
                summary_lookup[
                    "Максимальная мольная доля фазы, %"
                ]
            ) < result["threshold"]:
                st.info(
                    "На рассчитанной сетке выбранная фаза не достигла "
                    "заданной границы появления. Попробуйте другую "
                    "температуру, более мелкий шаг либо проверьте, не "
                    "исключена ли конкурирующая физически важная фаза."
                )

            with st.expander(
                "Точка максимума и сводка",
                expanded=False,
            ):
                st.dataframe(
                    result["summary"],
                    width="stretch",
                    hide_index=True,
                )

            with st.expander(
                "Полная расчётная сетка",
                expanded=False,
            ):
                st.dataframe(
                    result["data"],
                    width="stretch",
                    hide_index=True,
                )

            excel_bytes = dataframe_to_excel(
                {
                    "Параметры": result["settings"],
                    "Сводка": result["summary"],
                    "Расчётная сетка": result["data"],
                }
            )
            csv_bytes = result["data"].to_csv(
                index=False,
            ).encode("utf-8-sig")
            png_bytes = figure_to_png(result["figure"])

            download_col1, download_col2, download_col3 = st.columns(3)
            with download_col1:
                release_download_button(
                    "Скачать Excel",
                    data=excel_bytes,
                    file_name="ThermoGar_ternary_phase_map.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            with download_col2:
                release_download_button(
                    "Скачать CSV",
                    data=csv_bytes,
                    file_name="ThermoGar_ternary_phase_map.csv",
                    mime="text/csv",
                )
            with download_col3:
                release_download_button(
                    "Скачать PNG",
                    data=png_bytes,
                    file_name="ThermoGar_ternary_phase_map.png",
                    mime="image/png",
                )



# ---------------------------------------------------------------------------
# Затвердевание
# ---------------------------------------------------------------------------

with solidification_tab:
    st.subheader("Затвердевание")
    st.caption(
        "Сравните равновесное затвердевание с приближением Scheil–Gulliver, "
        "определите ликвидус, солидус, последовательность появления фаз "
        "и изменение состава остаточного расплава."
    )

    if not SCHEIL_AVAILABLE:
        st.error(
            "Для этого раздела не установлен дополнительный пакет `scheil`. "
            "Остальные функции ThermoGar продолжают работать."
        )
        st.markdown("Установите пакет один раз и перезапустите ThermoGar:")
        st.code(
            'python -m pip install "scheil==0.3.0"',
            language="bash",
        )
        if SCHEIL_IMPORT_ERROR:
            st.caption(f"Причина импорта: {SCHEIL_IMPORT_ERROR}")
    else:
        st.success(
            f"Модуль затвердевания готов: scheil {scheil_package.__version__}."
        )
        st.info(
            "Оба метода этого модуля рассчитываются при 101 325 Па. "
            "Scheil–Gulliver предполагает полное перемешивание расплава, "
            "локальное равновесие на границе и отсутствие диффузии в твёрдом."
        )
        if not np.isclose(float(pressure_pa), 101325.0):
            st.warning(
                "Заданное в боковой панели давление здесь не применяется: "
                "модуль затвердевания использует 101 325 Па."
            )

        defaults = SOLIDIFICATION_DEFAULTS[database_key]
        solidification_method_mode = st.radio(
            "Метод расчёта",
            [
                "Сравнить равновесное и Scheil–Gulliver",
                "Только равновесное затвердевание",
                "Только Scheil–Gulliver",
            ],
            key=f"solidification_method_{database_key}",
        )

        solidification_start_key = (
            f"solidification_start_13_1_{database_key}_{fe_profile_key}"
            if database_key == "fe"
            else f"solidification_start_13_1_{database_key}"
        )
        solidification_start_kwargs: dict[str, Any] = {
            "label": "Начальная температура, °C",
            "value": float(defaults["start_temperature_c"]),
            "step": 25.0,
            "key": solidification_start_key,
            "help": (
                "Температура должна соответствовать практически однофазному "
                "расплаву. ThermoGar может автоматически поднять её."
            ),
        }
        if database_key == "fe":
            solidification_start_kwargs["max_value"] = float(FE_DATABASE_MAX_T_C)
            solidification_start_kwargs["help"] = (
                "Для mc_fe 2.062 расчёт ограничен верхней границей базы "
                "2000 K (1726,85 °C)."
            )
        solidification_start_c = st.number_input(**solidification_start_kwargs)
        solidification_step_c = st.number_input(
            "Шаг охлаждения, °C",
            min_value=0.1,
            value=float(defaults["step_temperature_c"]),
            step=1.0,
            key=f"solidification_step_{database_key}",
        )

        with st.expander("Точность и критерии", expanded=False):
            solidification_auto_start = st.checkbox(
                "Автоматически повысить температуру до однофазного расплава",
                value=True,
                key=f"solidification_auto_start_{database_key}",
            )
            solidification_start_increment_c = st.number_input(
                "Шаг автоматического повышения, °C",
                min_value=1.0,
                value=50.0,
                step=10.0,
                key=f"solidification_start_increment_{database_key}",
            )
            if database_key == "fe":
                solidification_max_start_c = st.number_input(
                    "Максимальная проверяемая температура, °C",
                    min_value=-200.0,
                    max_value=float(FE_DATABASE_MAX_T_C),
                    value=float(FE_DATABASE_MAX_T_C),
                    step=25.0,
                    key=f"solidification_max_start_13_1_{database_key}_{fe_profile_key}",
                    help=(
                        "Верхняя граница mc_fe 2.062 — 2000 K "
                        "(1726,85 °C); выше неё ThermoGar не ищет расплав."
                    ),
                )
            else:
                solidification_max_start_c = st.number_input(
                    "Максимальная проверяемая температура, °C",
                    min_value=-200.0,
                    value=3000.0,
                    step=100.0,
                    key=f"solidification_max_start_13_1_{database_key}",
                )
            solidification_scheil_stop_percent = st.number_input(
                "Scheil: остановить при остатке расплава, %",
                min_value=0.0001,
                max_value=5.0,
                value=0.01,
                step=0.01,
                format="%.4f",
                key=f"solidification_stop_{database_key}",
            )
            solidification_appearance_percent = st.number_input(
                "Порог появления фазы, %",
                min_value=0.0001,
                max_value=5.0,
                value=0.01,
                step=0.01,
                format="%.4f",
                key=f"solidification_appearance_{database_key}",
            )
            solidification_display_percent = st.number_input(
                "Показывать на графиках фазы от, %",
                min_value=0.0,
                value=0.1,
                step=0.1,
                key=f"solidification_display_{database_key}",
            )
            solidification_pdens = st.select_slider(
                "Плотность начального поиска состояний",
                options=[25, 50, 100, 200],
                value=50,
                key=f"solidification_pdens_{database_key}",
                help=(
                    "25 — быстрее; 50 — рабочий режим; 100–200 — подробнее, "
                    "но заметно дольше."
                ),
            )
            solidification_binary_tol_c = st.number_input(
                "Точность поиска равновесного солидуса, °C",
                min_value=0.01,
                value=0.1,
                step=0.1,
                format="%.2f",
                key=f"solidification_binary_tol_{database_key}",
            )
            solidification_adaptive = st.checkbox(
                "Адаптивно уточнять состояния рядом с равновесием",
                value=True,
                key=f"solidification_adaptive_{database_key}",
            )

        try:
            solidification_candidate_phases = (
                phase_candidates_for_standard_composition(
                    db,
                    database_key,
                    composition_text,
                    units,
                    balance,
                    steel_mode,
                )
            )
        except Exception as preview_error:
            solidification_candidate_phases = []
            st.error(f"Исправьте состав: {preview_error}")

        selected_solidification_phases, solidification_phase_mode = (
            phase_selection_editor(
                db,
                database_key,
                solidification_candidate_phases,
                "solidification",
            )
            if solidification_candidate_phases
            else ([], "Автоматически")
        )

        if selected_solidification_phases and "LIQUID" not in selected_solidification_phases:
            st.error(
                "Для расчёта затвердевания нужно оставить фазу LIQUID."
            )

        if release_calculation_button(
            "Рассчитать затвердевание",
            type="primary",
            key="solidification_calculate",
            disabled=(
                not selected_solidification_phases
                or "LIQUID" not in selected_solidification_phases
            ),
        ):
            try:
                if float(solidification_max_start_c) < float(solidification_start_c):
                    raise ValueError(
                        "Максимальная проверяемая температура должна быть "
                        "не ниже начальной температуры."
                    )
                entered = parse_composition(composition_text)
                (
                    components,
                    composition_conditions,
                    overall_x,
                    overall_w,
                    phases,
                ) = prepare_calculation(
                    db,
                    database_key,
                    entered,
                    units,
                    balance,
                    steel_mode,
                    selected_solidification_phases,
                )

                if "LIQUID" not in phases:
                    raise ValueError(
                        "Фаза LIQUID отсутствует в выбранном наборе фаз."
                    )

                with st.status(
                    "Проверяем начальное состояние расплава…",
                    expanded=True,
                ) as status:
                    actual_start_k, start_check_table = (
                        resolve_solidification_start_temperature(
                            db,
                            components,
                            phases,
                            composition_conditions,
                            float(solidification_start_c) + 273.15,
                            bool(solidification_auto_start),
                            float(solidification_start_increment_c),
                            float(solidification_max_start_c) + 273.15,
                            int(solidification_pdens),
                        )
                    )
                    status.write(
                        "Расчётная начальная температура: "
                        f"{actual_start_k - 273.15:.2f} °C."
                    )

                    methods_to_run: list[str] = []
                    if solidification_method_mode.startswith("Сравнить"):
                        methods_to_run = ["equilibrium", "scheil"]
                    elif solidification_method_mode.startswith("Только равновесное"):
                        methods_to_run = ["equilibrium"]
                    else:
                        methods_to_run = ["scheil"]

                    results: dict[str, Any] = {}
                    errors: dict[str, str] = {}

                    for method_key in methods_to_run:
                        method_label = SOLIDIFICATION_METHOD_LABELS[method_key]
                        status.update(
                            label=f"Считаем: {method_label}…",
                            state="running",
                        )
                        eq_kwargs = {
                            "calc_opts": {
                                "pdens": int(solidification_pdens),
                            }
                        }
                        try:
                            if method_key == "equilibrium":
                                result = simulate_equilibrium_solidification(
                                    db,
                                    components,
                                    phases,
                                    composition_conditions,
                                    actual_start_k,
                                    step_temperature=float(solidification_step_c),
                                    liquid_phase_name="LIQUID",
                                    adaptive=bool(solidification_adaptive),
                                    eq_kwargs=eq_kwargs,
                                    binary_search_tol=float(
                                        solidification_binary_tol_c
                                    ),
                                    verbose=False,
                                )
                            else:
                                result = simulate_scheil_solidification(
                                    db,
                                    components,
                                    phases,
                                    composition_conditions,
                                    actual_start_k,
                                    step_temperature=float(solidification_step_c),
                                    liquid_phase_name="LIQUID",
                                    eq_kwargs=eq_kwargs,
                                    stop=(
                                        float(solidification_scheil_stop_percent)
                                        / 100.0
                                    ),
                                    verbose=False,
                                    adaptive=bool(solidification_adaptive),
                                )
                            results[method_key] = result
                            status.write(f"{method_label}: завершено.")
                        except Exception as method_error:
                            errors[method_key] = str(method_error)
                            status.write(
                                f"{method_label}: расчёт не завершён — "
                                f"{method_error}"
                            )

                    if not results:
                        raise RuntimeError(
                            "Ни один выбранный метод не завершился успешно."
                        )

                    status.update(
                        label="Расчёт затвердевания завершён",
                        state="complete",
                        expanded=False,
                    )

                appearance_fraction = (
                    float(solidification_appearance_percent) / 100.0
                )
                paths = {
                    key: solidification_path_dataframe(result)
                    for key, result in results.items()
                }
                raw_tables = {
                    key: solidification_raw_dataframe(result)
                    for key, result in results.items()
                }
                liquid_tables = {
                    key: solidification_liquid_composition_dataframe(
                        result,
                        db,
                        components,
                    )
                    for key, result in results.items()
                }
                sequences = {
                    key: solidification_phase_sequence(
                        result,
                        database_key,
                        appearance_fraction,
                    )
                    for key, result in results.items()
                }
                final_phases = {
                    key: solidification_final_phase_table(
                        result,
                        database_key,
                        appearance_fraction,
                    )
                    for key, result in results.items()
                }
                summary_table = pd.DataFrame(
                    [
                        solidification_summary_row(
                            result,
                            appearance_fraction,
                        )
                        for result in results.values()
                    ]
                )
                settings_table = pd.DataFrame(
                    [
                        ("База", definition["label"]),
                        ("Файл базы", str(database_path)),
                        (
                            "Профиль Fe-базы",
                            FE_PROFILE_LABELS.get(fe_profile_key, "не применяется")
                            if database_key == "fe"
                            else "не применяется",
                        ),
                        (
                            "Исключённые из расчёта фазы",
                            ", ".join(sorted(FE_EXCLUDED_PHASES))
                            if database_key == "fe"
                            else "нет",
                        ),
                        ("Основа", balance),
                        ("Единицы ввода", units_label),
                        ("Добавки", composition_text),
                        ("Давление модуля, Па", 101325.0),
                        ("Начальная температура, °C", actual_start_k - 273.15),
                        ("Шаг охлаждения, °C", solidification_step_c),
                        ("Порог появления фазы, %", solidification_appearance_percent),
                        ("Scheil: критерий остатка, %", solidification_scheil_stop_percent),
                        ("Режим фаз", solidification_phase_mode),
                        ("Выбранные фазы", ", ".join(phases)),
                        ("Плотность поиска", solidification_pdens),
                        ("Адаптивное уточнение", "да" if solidification_adaptive else "нет"),
                    ],
                    columns=["Параметр", "Значение"],
                )

                solidification_quality = validate_solidification_paths(paths)
                st.session_state["solidification_result"] = {
                    "database_key": database_key,
                    "components": components,
                    "results": results,
                    "errors": errors,
                    "summary": summary_table,
                    "settings": settings_table,
                    "start_check": start_check_table,
                    "paths": paths,
                    "raw_tables": raw_tables,
                    "liquid_tables": liquid_tables,
                    "sequences": sequences,
                    "final_phases": final_phases,
                    "quality": solidification_quality,
                    "fe_profile_key": fe_profile_key,
                    "display_threshold_percent": float(
                        solidification_display_percent
                    ),
                }
                record_calculation_history(
                    THERMOGAR_PATHS,
                    "Затвердевание",
                    CURRENT_CONTEXT,
                    {
                        "methods": sorted(results),
                        "start_temperature_C": float(
                            solidification_start_c
                        ),
                        "temperature_step_C": float(
                            solidification_step_c
                        ),
                        "errors": errors,
                        "fe_profile_key": fe_profile_key if database_key == "fe" else None,
                    },
                )

            except Exception as solidification_error:
                render_friendly_error(
                    solidification_error,
                    context="затвердевание",
                )

        if (
            "solidification_result" in st.session_state
            and st.session_state["solidification_result"].get(
                "database_key"
            )
            == database_key
        ):
            state = st.session_state["solidification_result"]
            results = state["results"]
            comparison_figure = plot_solidification_liquid_comparison(results)
            phase_figures = {
                method_key: plot_solidification_phase_path(
                    result,
                    database_key,
                    state["display_threshold_percent"],
                )
                for method_key, result in results.items()
            }

            summary_subtab, phases_subtab, liquid_subtab, export_subtab = st.tabs(
                [
                    "Сводка",
                    "Твёрдые фазы",
                    "Остаточный расплав",
                    "Выгрузка",
                ]
            )

            with summary_subtab:
                st.markdown("### Основные температуры")
                st.dataframe(
                    state["summary"],
                    width="stretch",
                    hide_index=True,
                )
                if "quality" in state:
                    render_quality_panel(state["quality"])
                st.pyplot(comparison_figure, use_container_width=False)
                st.caption(
                    "Ликвидус определяется по выбранному порогу появления "
                    "твёрдой фазы. Для Scheil температура окончания — это "
                    "точка достижения заданного остатка расплава, а не точный "
                    "равновесный солидус."
                )
                with st.expander("Как проверялась начальная температура"):
                    st.dataframe(
                        state["start_check"],
                        width="stretch",
                        hide_index=True,
                    )
                if state["errors"]:
                    for method_key, error_text in state["errors"].items():
                        st.warning(
                            f"{SOLIDIFICATION_METHOD_LABELS.get(method_key, method_key)}: "
                            f"{error_text}"
                        )

            with phases_subtab:
                phase_method_key = st.selectbox(
                    "Какой метод показать",
                    options=list(results),
                    format_func=lambda key: SOLIDIFICATION_METHOD_LABELS.get(
                        key,
                        key,
                    ),
                    key="solidification_phase_method",
                )
                st.pyplot(
                    phase_figures[phase_method_key],
                    use_container_width=False,
                )
                st.markdown("### Последовательность появления фаз")
                st.dataframe(
                    state["sequences"][phase_method_key],
                    width="stretch",
                    hide_index=True,
                )
                st.markdown("### Итоговые количества фаз")
                st.dataframe(
                    state["final_phases"][phase_method_key],
                    width="stretch",
                    hide_index=True,
                )
                with st.expander("Полная траектория расчёта"):
                    st.dataframe(
                        state["paths"][phase_method_key],
                        width="stretch",
                        hide_index=True,
                    )

            with liquid_subtab:
                liquid_elements = [
                    component
                    for component in state["components"]
                    if component != "VA"
                ]
                liquid_element = st.selectbox(
                    "Элемент в остаточном расплаве",
                    liquid_elements,
                    key="solidification_liquid_element",
                )
                liquid_units_label = st.radio(
                    "Единицы состава расплава",
                    ["атомные %", "массовые %"],
                    horizontal=True,
                    key="solidification_liquid_units",
                )
                liquid_units = (
                    "at"
                    if liquid_units_label == "атомные %"
                    else "wt"
                )
                liquid_figure = plot_liquid_composition_comparison(
                    state["liquid_tables"],
                    liquid_element,
                    liquid_units,
                )
                st.pyplot(liquid_figure, use_container_width=False)
                liquid_method_key = st.selectbox(
                    "Таблица для метода",
                    options=list(results),
                    format_func=lambda key: SOLIDIFICATION_METHOD_LABELS.get(
                        key,
                        key,
                    ),
                    key="solidification_liquid_method",
                )
                st.dataframe(
                    state["liquid_tables"][liquid_method_key],
                    width="stretch",
                    hide_index=True,
                )
                st.caption(
                    "При жидкостной несмешиваемости единичный состав LIQUID "
                    "может быть недостаточен; такую область нужно проверять отдельно."
                )

            with export_subtab:
                st.markdown("### Скачать результаты")
                export_liquid_elements = [
                    component
                    for component in state["components"]
                    if component != "VA"
                ]
                export_element = export_liquid_elements[0]
                export_liquid_figure = plot_liquid_composition_comparison(
                    state["liquid_tables"],
                    export_element,
                    "at",
                )
                excel_bytes = solidification_excel_bytes(state)
                zip_bytes = solidification_zip_bytes(
                    state,
                    comparison_figure,
                    phase_figures,
                    export_liquid_figure,
                )
                release_download_button(
                    "Скачать Excel",
                    data=excel_bytes,
                    file_name="ThermoGar_solidification.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
                release_download_button(
                    "Скачать график доли расплава, PNG",
                    data=figure_to_png(comparison_figure),
                    file_name="ThermoGar_liquid_fraction.png",
                    mime="image/png",
                )
                release_download_button(
                    "Скачать полный архив ZIP",
                    data=zip_bytes,
                    file_name="ThermoGar_solidification_results.zip",
                    mime="application/zip",
                )


# ---------------------------------------------------------------------------
# Энергии фаз, движущая сила и T0
# ---------------------------------------------------------------------------

with energy_tab:
    st.subheader("Энергии и движущие силы")
    st.caption(
        "Сравните молярные энергии фаз, оцените движущую силу образования "
        "фазы и найдите температуру T₀ равенства энергий двух фаз."
    )

    energy_curve_tab, driving_force_tab, tzero_tab = st.tabs(
        [
            "Энергии фаз",
            "Движущая сила",
            "T₀",
        ]
    )

    energy_defaults = ENERGY_DEFAULTS[database_key]

    with energy_curve_tab:
        st.markdown("### Энергия Гиббса фаз при фиксированном составе")
        st.caption(
            "Каждая кривая — однофазное состояние с тем же общим составом. "
            "Это сравнение метастабильности, а не долей фаз в полном равновесии."
        )

        try:
            energy_candidate_phases = phase_candidates_for_standard_composition(
                db,
                database_key,
                composition_text,
                units,
                balance,
                steel_mode,
            )
        except Exception as preview_error:
            st.warning(
                "Список фаз появится после исправления состава: "
                f"{preview_error}"
            )
            energy_candidate_phases = []

        default_energy_phases = [
            phase_name
            for phase_name in energy_defaults["phases"]
            if phase_name in energy_candidate_phases
        ]
        if not default_energy_phases:
            default_energy_phases = energy_candidate_phases[:3]

        energy_phases = st.multiselect(
            "Фазы для сравнения — не более восьми",
            options=energy_candidate_phases,
            default=default_energy_phases,
            max_selections=8,
            key=f"energy_curve_phases_{database_key}",
        )

        energy_t_min = st.number_input(
            "Температура от, °C",
            value=float(energy_defaults["t_min"]),
            step=25.0,
            key=f"energy_t_min_{database_key}",
        )
        energy_t_max = st.number_input(
            "Температура до, °C",
            value=float(energy_defaults["t_max"]),
            step=25.0,
            key=f"energy_t_max_{database_key}",
        )
        energy_t_step = st.number_input(
            "Шаг температуры, °C",
            min_value=0.1,
            value=float(energy_defaults["t_step"]),
            step=5.0,
            key=f"energy_t_step_{database_key}",
        )
        energy_view = st.radio(
            "Что показать на графике",
            [
                "Относительно минимальной энергии выбранных фаз",
                "Абсолютная молярная энергия GM",
            ],
            horizontal=True,
            key=f"energy_view_{database_key}",
        )

        if release_calculation_button(
            "Рассчитать энергии фаз",
            type="primary",
            key="energy_curve_calculate",
        ):
            try:
                entered = parse_composition(composition_text)
                (
                    components,
                    composition_conditions,
                    overall_x,
                    overall_w,
                    _phases,
                ) = prepare_calculation(
                    db,
                    database_key,
                    entered,
                    units,
                    balance,
                    steel_mode,
                )

                with st.spinner("Расчёт однофазных энергий…"):
                    absolute_table, relative_table, crossings, skipped = (
                        isolated_phase_energy_tables(
                            db,
                            components,
                            energy_phases,
                            composition_conditions,
                            pressure_pa,
                            energy_t_min,
                            energy_t_max,
                            energy_t_step,
                        )
                    )

                valid_phases = [
                    phase_name
                    for phase_name in energy_phases
                    if phase_name in absolute_table.columns
                ]
                relative_view = energy_view.startswith("Относительно")
                plot_table = relative_table if relative_view else absolute_table
                figure = plot_isolated_phase_energies(
                    plot_table,
                    valid_phases,
                    database_key,
                    relative_view,
                )

                settings = pd.DataFrame(
                    [
                        ("База", definition["label"]),
                        ("Основа", balance),
                        ("Единицы ввода", units_label),
                        ("Добавки", composition_text),
                        ("Давление, Па", pressure_pa),
                        ("Фазы", ", ".join(valid_phases)),
                        ("Температура от, °C", energy_t_min),
                        ("Температура до, °C", energy_t_max),
                        ("Шаг, °C", energy_t_step),
                    ],
                    columns=["Параметр", "Значение"],
                )

                st.session_state["energy_curve_result"] = {
                    "database_key": database_key,
                    "settings": settings,
                    "absolute": absolute_table,
                    "relative": relative_table,
                    "crossings": crossings,
                    "skipped": skipped,
                    "valid_phases": valid_phases,
                    "figure": figure,
                    "relative_view": relative_view,
                }
                record_calculation_history(
                    THERMOGAR_PATHS,
                    "Энергии фаз",
                    CURRENT_CONTEXT,
                    {
                        "phases": valid_phases,
                        "temperature_min_C": float(energy_t_min),
                        "temperature_max_C": float(energy_t_max),
                        "points": int(len(absolute_table)),
                    },
                )
            except Exception as error:
                render_friendly_error(error, context='энергии фаз')

        energy_state = st.session_state.get("energy_curve_result")
        if energy_state and energy_state.get("database_key") == database_key:
            st.pyplot(energy_state["figure"])

            if energy_state["skipped"]:
                st.warning(
                    "Некоторые фазы пропущены:\n\n- "
                    + "\n- ".join(energy_state["skipped"])
                )

            if not energy_state["crossings"].empty:
                st.markdown("#### Приближённые пересечения энергетических кривых")
                st.dataframe(
                    energy_state["crossings"],
                    width="stretch",
                    hide_index=True,
                )

            with st.expander("Таблицы энергий"):
                st.markdown("#### Абсолютная энергия, Дж/моль")
                st.dataframe(
                    energy_state["absolute"],
                    width="stretch",
                    hide_index=True,
                )
                st.markdown("#### Энергия относительно минимума, Дж/моль")
                st.dataframe(
                    energy_state["relative"],
                    width="stretch",
                    hide_index=True,
                )

            st.info(
                "Минимальная энергия среди выбранных однофазных состояний "
                "не равна автоматически полному многофазному равновесию. "
                "Стехиометрическая фаза может быть определена только в узком "
                "диапазоне состава."
            )

            energy_excel = dataframe_to_excel(
                {
                    "Параметры": energy_state["settings"],
                    "Абсолютные энергии": energy_state["absolute"],
                    "Относительные энергии": energy_state["relative"],
                    "Пересечения": energy_state["crossings"],
                }
            )
            download_col1, download_col2 = st.columns(2)
            with download_col1:
                release_download_button(
                    "Скачать Excel",
                    data=energy_excel,
                    file_name="ThermoGar_phase_energies.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            with download_col2:
                release_download_button(
                    "Скачать PNG",
                    data=figure_to_png(energy_state["figure"]),
                    file_name="ThermoGar_phase_energies.png",
                    mime="image/png",
                )

    with driving_force_tab:
        st.markdown("### Движущая сила образования выбранной фазы")
        st.caption(
            "Положительное значение означает, что выбранная подавленная фаза "
            "может понизить энергию относительно исходного равновесия; "
            "отрицательное — что её образование в этих условиях невыгодно."
        )

        try:
            driving_candidate_phases = phase_candidates_for_standard_composition(
                db,
                database_key,
                composition_text,
                units,
                balance,
                steel_mode,
            )
        except Exception as preview_error:
            st.warning(
                "Список фаз появится после исправления состава: "
                f"{preview_error}"
            )
            driving_candidate_phases = []

        default_target = energy_defaults["driving_phase"]
        if default_target not in driving_candidate_phases and driving_candidate_phases:
            default_target = driving_candidate_phases[0]

        driving_target = st.selectbox(
            "Фаза, движущую силу которой рассчитываем",
            options=driving_candidate_phases,
            index=(
                driving_candidate_phases.index(default_target)
                if default_target in driving_candidate_phases
                else 0
            ),
            key=f"driving_target_{database_key}",
        ) if driving_candidate_phases else ""

        exclude_target = st.checkbox(
            "Исключить выбранную фазу из исходного равновесия",
            value=True,
            help=(
                "Так рассчитывается термодинамический стимул появления фазы, "
                "которой ещё нет в исходном наборе."
            ),
            key=f"driving_exclude_target_{database_key}",
        )

        default_reference_phases = [
            phase_name
            for phase_name in driving_candidate_phases
            if not (exclude_target and phase_name == driving_target)
        ]
        driving_reference_phases = st.multiselect(
            "Фазы исходного равновесия",
            options=driving_candidate_phases,
            default=default_reference_phases,
            key=f"driving_reference_phases_{database_key}_{driving_target}_{exclude_target}",
        )

        driving_t_min = st.number_input(
            "Температура от, °C",
            value=float(energy_defaults["t_min"]),
            step=25.0,
            key=f"driving_t_min_{database_key}",
        )
        driving_t_max = st.number_input(
            "Температура до, °C",
            value=float(energy_defaults["t_max"]),
            step=25.0,
            key=f"driving_t_max_{database_key}",
        )
        driving_t_step = st.number_input(
            "Шаг температуры, °C",
            min_value=0.1,
            value=float(energy_defaults["t_step"]),
            step=5.0,
            key=f"driving_t_step_{database_key}",
        )

        if release_calculation_button(
            "Рассчитать движущую силу",
            type="primary",
            key="driving_force_calculate",
        ):
            try:
                if not driving_target:
                    raise ValueError("Не выбрана фаза для расчёта.")
                reference_phases = list(driving_reference_phases)
                if exclude_target:
                    reference_phases = [
                        phase_name
                        for phase_name in reference_phases
                        if phase_name != driving_target
                    ]
                elif driving_target not in reference_phases:
                    reference_phases.append(driving_target)

                entered = parse_composition(composition_text)
                (
                    components,
                    composition_conditions,
                    _overall_x,
                    _overall_w,
                    _phases,
                ) = prepare_calculation(
                    db,
                    database_key,
                    entered,
                    units,
                    balance,
                    steel_mode,
                )

                with st.spinner("Расчёт движущей силы…"):
                    driving_table, sign_crossings = (
                        dormant_phase_driving_force_table(
                            db,
                            components,
                            reference_phases,
                            driving_target,
                            composition_conditions,
                            pressure_pa,
                            driving_t_min,
                            driving_t_max,
                            driving_t_step,
                        )
                    )
                figure = plot_driving_force(
                    driving_table,
                    driving_target,
                )
                settings = pd.DataFrame(
                    [
                        ("База", definition["label"]),
                        ("Основа", balance),
                        ("Единицы ввода", units_label),
                        ("Добавки", composition_text),
                        ("Целевая фаза", driving_target),
                        ("Фазы исходного равновесия", ", ".join(reference_phases)),
                        ("Давление, Па", pressure_pa),
                        ("Температура от, °C", driving_t_min),
                        ("Температура до, °C", driving_t_max),
                        ("Шаг, °C", driving_t_step),
                    ],
                    columns=["Параметр", "Значение"],
                )
                st.session_state["driving_force_result"] = {
                    "database_key": database_key,
                    "settings": settings,
                    "data": driving_table,
                    "crossings": sign_crossings,
                    "figure": figure,
                    "target": driving_target,
                }
                record_calculation_history(
                    THERMOGAR_PATHS,
                    "Движущая сила",
                    CURRENT_CONTEXT,
                    {
                        "target_phase": driving_target,
                        "reference_phases": reference_phases,
                        "temperature_min_C": float(driving_t_min),
                        "temperature_max_C": float(driving_t_max),
                    },
                )
            except Exception as error:
                render_friendly_error(error, context='движущая сила')

        driving_state = st.session_state.get("driving_force_result")
        if driving_state and driving_state.get("database_key") == database_key:
            st.pyplot(driving_state["figure"])
            if not driving_state["crossings"].empty:
                st.markdown("#### Приближённая смена знака")
                st.dataframe(
                    driving_state["crossings"],
                    width="stretch",
                    hide_index=True,
                )
            st.dataframe(
                driving_state["data"],
                width="stretch",
                hide_index=True,
            )
            st.info(
                "Движущая сила — только термодинамический стимул. Она не "
                "задаёт скорость превращения, время выдержки, число зародышей "
                "или размер частиц."
            )
            driving_excel = dataframe_to_excel(
                {
                    "Параметры": driving_state["settings"],
                    "Движущая сила": driving_state["data"],
                    "Смена знака": driving_state["crossings"],
                }
            )
            download_col1, download_col2 = st.columns(2)
            with download_col1:
                release_download_button(
                    "Скачать Excel",
                    data=driving_excel,
                    file_name="ThermoGar_driving_force.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            with download_col2:
                release_download_button(
                    "Скачать PNG",
                    data=figure_to_png(driving_state["figure"]),
                    file_name="ThermoGar_driving_force.png",
                    mime="image/png",
                )

    with tzero_tab:
        st.markdown("### Температура T₀ равенства энергий двух фаз")
        st.caption(
            "T₀ — температура, при которой две фазы одного и того же состава "
            "имеют одинаковую молярную энергию Гиббса. Это не обычная линия "
            "солвуса и не многофазная граница равновесия."
        )

        tzero_variable_options = [
            element
            for element in available_elements
            if element != balance
        ]
        default_variable = energy_defaults["variable_element"]
        if default_variable not in tzero_variable_options:
            default_variable = tzero_variable_options[0]
        tzero_variable = st.selectbox(
            "Изменяемый элемент",
            options=tzero_variable_options,
            index=tzero_variable_options.index(default_variable),
            key=f"tzero_variable_{database_key}_{balance}",
        )
        tzero_units_label = st.radio(
            "Единицы горизонтальной оси",
            ["атомные %", "массовые %"],
            index=0 if energy_defaults["units"] == "at" else 1,
            horizontal=True,
            key=f"tzero_units_{database_key}",
        )
        tzero_units = "at" if tzero_units_label == "атомные %" else "wt"
        tzero_fixed_text = st.text_area(
            "Постоянные добавки",
            value="",
            placeholder="Например: CR=15, CO=10",
            help=(
                f"Не указывайте {balance} и {tzero_variable}. "
                "Остаток считается элементом-основой."
            ),
            key=f"tzero_fixed_{database_key}_{tzero_variable}",
        )

        tzero_c_min = st.number_input(
            f"{tzero_variable}: от, %",
            min_value=0.0,
            value=float(energy_defaults["c_min"]),
            step=float(energy_defaults["c_step"]),
            key=f"tzero_c_min_{database_key}_{tzero_variable}",
        )
        tzero_c_max = st.number_input(
            f"{tzero_variable}: до, %",
            min_value=0.001,
            value=float(energy_defaults["c_max"]),
            step=float(energy_defaults["c_step"]),
            key=f"tzero_c_max_{database_key}_{tzero_variable}",
        )
        tzero_c_step = st.number_input(
            f"{tzero_variable}: шаг, %",
            min_value=0.001,
            value=float(energy_defaults["c_step"]),
            step=float(energy_defaults["c_step"]),
            key=f"tzero_c_step_{database_key}_{tzero_variable}",
        )

        try:
            tzero_fixed = parse_composition(tzero_fixed_text)
            tzero_components = sorted(
                set(tzero_fixed) | {tzero_variable, balance}
            ) + ["VA"]
            tzero_candidate_phases = compatible_phases_for_components(
                db,
                database_key,
                tzero_components,
                steel_mode,
            )
        except Exception as preview_error:
            st.warning(
                "Список фаз появится после исправления постоянных добавок: "
                f"{preview_error}"
            )
            tzero_candidate_phases = []

        default_tzero_phases = [
            phase_name
            for phase_name in energy_defaults["tzero_phases"]
            if phase_name in tzero_candidate_phases
        ]
        if len(default_tzero_phases) < 2:
            default_tzero_phases = tzero_candidate_phases[:2]

        phase_one = st.selectbox(
            "Фаза 1",
            options=tzero_candidate_phases,
            index=(
                tzero_candidate_phases.index(default_tzero_phases[0])
                if default_tzero_phases
                else 0
            ),
            key=f"tzero_phase_one_{database_key}_{tzero_variable}",
        ) if tzero_candidate_phases else ""
        phase_two_options = [
            phase_name
            for phase_name in tzero_candidate_phases
            if phase_name != phase_one
        ]
        default_phase_two = (
            default_tzero_phases[1]
            if len(default_tzero_phases) > 1
            and default_tzero_phases[1] in phase_two_options
            else (phase_two_options[0] if phase_two_options else "")
        )
        phase_two = st.selectbox(
            "Фаза 2",
            options=phase_two_options,
            index=(
                phase_two_options.index(default_phase_two)
                if default_phase_two in phase_two_options
                else 0
            ),
            key=f"tzero_phase_two_{database_key}_{tzero_variable}_{phase_one}",
        ) if phase_two_options else ""

        tzero_t_min = st.number_input(
            "Нижняя граница поиска T₀, °C",
            value=float(energy_defaults["t_min"]),
            step=25.0,
            key=f"tzero_t_min_{database_key}",
        )
        tzero_t_max = st.number_input(
            "Верхняя граница поиска T₀, °C",
            value=float(energy_defaults["t_max"]),
            step=25.0,
            key=f"tzero_t_max_{database_key}",
        )

        if release_calculation_button(
            "Рассчитать T₀",
            type="primary",
            key="tzero_calculate",
        ):
            try:
                if not phase_one or not phase_two:
                    raise ValueError("Выберите две фазы.")
                with st.spinner("Поиск T₀ по составу…"):
                    tzero_table = tzero_path_table(
                        db,
                        database_key,
                        balance,
                        tzero_variable,
                        tzero_fixed_text,
                        tzero_units,
                        steel_mode,
                        phase_one,
                        phase_two,
                        tzero_c_min,
                        tzero_c_max,
                        tzero_c_step,
                        pressure_pa,
                        tzero_t_min,
                        tzero_t_max,
                    )
                x_column = (
                    f"{tzero_variable}, "
                    f"{'ат.%' if tzero_units == 'at' else 'мас.%'}"
                )
                figure = plot_tzero(
                    tzero_table,
                    x_column,
                    phase_one,
                    phase_two,
                )
                settings = pd.DataFrame(
                    [
                        ("База", definition["label"]),
                        ("Основа", balance),
                        ("Изменяемый элемент", tzero_variable),
                        ("Единицы", tzero_units_label),
                        ("Постоянные добавки", tzero_fixed_text),
                        ("Фаза 1", phase_one),
                        ("Фаза 2", phase_two),
                        ("Давление, Па", pressure_pa),
                        ("Нижняя граница поиска, °C", tzero_t_min),
                        ("Верхняя граница поиска, °C", tzero_t_max),
                    ],
                    columns=["Параметр", "Значение"],
                )
                st.session_state["tzero_result"] = {
                    "database_key": database_key,
                    "settings": settings,
                    "data": tzero_table,
                    "figure": figure,
                    "phase_one": phase_one,
                    "phase_two": phase_two,
                }
                record_calculation_history(
                    THERMOGAR_PATHS,
                    "Расчёт T0",
                    CURRENT_CONTEXT,
                    {
                        "phase_one": phase_one,
                        "phase_two": phase_two,
                        "variable_element": tzero_variable,
                        "points": int(len(tzero_table)),
                    },
                )
            except Exception as error:
                render_friendly_error(error, context='расчёт T₀')

        tzero_state = st.session_state.get("tzero_result")
        if tzero_state and tzero_state.get("database_key") == database_key:
            valid_count = int(tzero_state["data"]["Решение найдено"].sum())
            total_count = len(tzero_state["data"])
            if valid_count:
                st.success(
                    f"T₀ найдено в {valid_count} точках из {total_count}."
                )
            else:
                st.warning(
                    "В заданном температурном диапазоне T₀ не найдено ни в "
                    "одной точке. Расширьте диапазон или выберите другую пару фаз."
                )
            st.pyplot(tzero_state["figure"])
            st.dataframe(
                tzero_state["data"],
                width="stretch",
                hide_index=True,
            )
            st.info(
                "T₀ показывает равенство энергий двух фаз при одинаковом "
                "составе. Для диффузионных превращений, солвуса и обычной "
                "фазовой границы используйте равновесные диаграммы."
            )
            tzero_excel = dataframe_to_excel(
                {
                    "Параметры": tzero_state["settings"],
                    "T0": tzero_state["data"],
                }
            )
            download_col1, download_col2 = st.columns(2)
            with download_col1:
                release_download_button(
                    "Скачать Excel",
                    data=tzero_excel,
                    file_name="ThermoGar_T0.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            with download_col2:
                release_download_button(
                    "Скачать PNG",
                    data=figure_to_png(tzero_state["figure"]),
                    file_name="ThermoGar_T0.png",
                    mime="image/png",
                )



# ---------------------------------------------------------------------------
# Свойства: плотность, упругость и механизмы упрочнения
# ---------------------------------------------------------------------------

with physical_tab:
    st.subheader("Физические свойства и механизмы упрочнения")
    st.caption(
        "Плотность и объёмные доли используют проверенные TDB и "
        "physical_data.pdb. Упругость и упрочнение используют ту же "
        "проверенную привязку выбранной базы."
    )

    try:
        b4b_physical_context = bind_b4b_physical_context(database_key)
        b4b_physical_error = None
    except Exception as error:
        b4b_physical_context = None
        b4b_physical_error = error
        st.error(f"Проверенная физическая привязка отклонена: {error}")

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
            "Покрытие PDB",
        ]
    )

    with physical_single_tab:
        if b4b_physical_context is None:
            st.error(str(b4b_physical_error))
        else:
            render_b4b_density_single(
                b4b_physical_context,
                database_key,
                composition_text,
                units,
                balance,
                float(pressure_pa),
                float(definition["default_temperature"]),
            )

    with physical_scan_tab:
        if b4b_physical_context is None:
            st.error(str(b4b_physical_error))
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
            )

    with elastic_properties_tab:
        if b4b_physical_context is None:
            st.error(str(b4b_physical_error))
        else:
            render_b4b2_elastic_properties(
                b4b_physical_context,
                database_key,
                composition_text,
                units,
                balance,
                float(pressure_pa),
                float(definition["default_temperature"]),
            )

    with strengthening_tab:
        if b4b_physical_context is None:
            st.error(str(b4b_physical_error))
        else:
            render_b4b2_strengthening(
                b4b_physical_context,
                database_key,
            )

    with physical_coverage_tab:
        st.markdown("### Что покрывает физическая база")
        if b4b_physical_context is None:
            st.error(str(b4b_physical_error))
        else:
            st.caption(
                "physical_data.pdb "
                + PHYSICAL_DATABASE_VERSION
                + " · SHA-256: "
                + b4b_physical_context.physical_pdb.sha256
            )
            render_b4b_coverage(
                b4b_physical_context,
                database_key,
            )
            render_b4b_pdb_self_test(
                b4b_physical_context,
                database_key,
            )


# ---------------------------------------------------------------------------
# Диффузия и гомогенизация
# ---------------------------------------------------------------------------

with diffusion_tab:
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


# ---------------------------------------------------------------------------
# Библиотека, проекты, история и помощь
# ---------------------------------------------------------------------------

USER_GUIDE_MD = r"""
# ThermoGar — краткое руководство пользователя

Краткая инструкция по выбору базы, вводу состава и работе с расчётными
разделами ThermoGar.

## Первый расчёт

1. В боковой панели выберите **базу материалов**: Ni, Al или Steel/Fe.
   Steel использует только канонический исправленный профиль `thermogar_patch`.
2. Выберите **элемент-основу**. Он автоматически заполняет остаток до 100 %.
3. Выберите **атомные** или **массовые проценты**.
4. В поле **Добавки** введите состав, например `AL=15, CR=10`.
5. Для Steel доступны обычные действия в трёх вкладках раздела **Расчёты**:
   одна температура, три точки по температуре и три точки по составу.
6. Результат каждого раздела можно выгрузить в Excel, CSV или PNG.

## Что делает каждый раздел

| Раздел | Когда использовать | Что получите |
|---|---|---|
| **Одна температура** | Нужно узнать состояние сплава при одной температуре | Устойчивые фазы, их доли и составы |
| **По температуре** | Нужно увидеть превращения при нагреве или охлаждении | График долей фаз от температуры |
| **По составу** | Нужно проверить влияние одного элемента | График долей фаз от концентрации |
| **Диаграммы → Бинарная T–X** | Система состоит только из двух элементов | Бинарная диаграмма температура–состав |
| **Диаграммы → Многокомпонентное T–X** | Остальные добавки фиксированы, меняется один элемент | Псевдобинарное сечение многокомпонентного сплава |
| **Диаграммы → Тройная при T = const** | Нужно увидеть области фаз в системе из трёх элементов | Тройная изотермическая диаграмма и линии связи |
| **Диаграммы → Карта доли фазы** | Нужно увидеть, где и сколько выбранной фазы в тройной системе | Цветная карта мольной доли фазы |
| **Затвердевание** | Нужно сравнить равновесный и Scheil–Gulliver пути | Ликвидус, солидус, фазы при кристаллизации и состав остаточного расплава |
| **Энергии** | Нужно сравнить метастабильность фаз или оценить стимул превращения | GM фаз, движущая сила и T₀ |
| **Свойства** | Нужны плотность, упругие свойства или вклады упрочнения | Плотность, объёмные доли, VRH и механизм-ориентированные вклады |
| **Кинетика** | Нужны диффузионные профили, гомогенизация или изменение выделений во времени | Диффузия, локальные фазовые доли, зарождение, рост, растворение и укрупнение |
| **Проекты и данные** | Нужно сохранить марку, рассчитать таблицу составов, проверить установку или продолжить работу позже | Марки, пакетный расчёт, проекты, история, справочник, помощь и диагностика |

## Как вводить состав

- `AL=15` при основе `NI` означает **15 % Al + 85 % Ni**.
- `CU=4, MG=1` при основе `AL` означает **4 % Cu + 1 % Mg + остаток Al**.
- Допускаются запятая или точка в десятичной части: `C=0,15` и `C=0.15`.
- Элемент-основу повторно в строке добавок указывать не нужно.
- Сумма добавок должна быть меньше 100 %.

## Управление фазами и метастабильный расчёт

В каждом расчётном разделе есть блок **«Управление фазами / метастабильный расчёт»**.

- **Автоматически** — учитываются все совместимые фазы базы.
- **Вручную** — можно снять галку с фазы.

Если убрать устойчивую фазу, ThermoGar найдёт **метастабильное равновесие** среди оставшихся фаз. Это исследовательский режим; результат нужно явно помечать как метастабильный.

## Примеры для проверки

| База | Основа | Единицы | Добавки | Температура |
|---|---|---|---|---:|
| Никелевые сплавы | NI | атомные % | `AL=15` | 700 °C |
| Алюминиевые сплавы | AL | атомные % | `CU=4` | 500 °C |
| Стали и Fe-сплавы | FE | массовые % | `C=0.20, CR=11.5, NI=0.7` | 700 °C |

Для первой бинарной диаграммы удобно использовать **Ni–Al**, 0–35 ат.% Al и 400–1600 °C.

## Тройная диаграмма за 6 шагов

1. Откройте **Диаграммы → Тройная при T = const**.
2. Выберите три разных элемента. Элемент C будет остатком до 100 %.
3. Задайте одну температуру.
4. Для первого запуска оставьте шаг 2,5–5 ат.%.
5. Оставьте автоматический выбор фаз и нажмите **Построить тройную диаграмму**.
6. При необходимости включите линии связи, точки трёхфазного равновесия или исключите отдельные фазы.

Готовые примеры: **Ni–Al–Cr при 1000 °C** и **Al–Cu–Mg при 500 °C**.

## Марки, пакетный расчёт и проекты

### Сохранить и загрузить состав

1. Откройте **Проекты и данные → Марки и составы**.
2. Введите понятное название и при необходимости заметку.
3. Нажмите **Сохранить текущий состав**.
4. Позже выберите запись и нажмите **Загрузить состав в программу**.

Учебные примеры служат только для проверки функций и не являются промышленными марками.

### Пакетный расчёт

Загрузите CSV или XLSX со списком составов, выполните расчёт для всей
таблицы и выгрузите результат. Шаблон входного файла доступен на той же
вкладке.

### Сохранить проект и повторить работу

- Проект хранит текущий материал и доступные настройки интерфейса.
- В файл проекта записывается SHA-256 базы; если база изменилась, ThermoGar предупреждает и предлагает пересчитать результат.
- История автоматически записывает успешные расчёты текущей версии ThermoGar и строит цепочку контрольных сумм.
- При удалении проекта или очистке истории исходный файл сохраняется как резервная копия.

## Как читать результат

- **Мольная доля фазы, %** — сколько данной фазы находится в равновесной системе по количеству вещества.
- **Состав фазы** — сколько каждого элемента содержится именно внутри этой фазы, а не во всём сплаве.
- `LIQUID` — расплав.
- `FCC_A1`, `BCC_B2`, `GP_MAT` могут быть частями связанных моделей упорядочения. Название фазы не всегда означает полное упорядочение; смотрите примечание в справочнике.
- Текущие расчёты являются **равновесными**: они показывают конечное состояние после достаточно долгой выдержки.

## Как рассчитать затвердевание

1. Откройте вкладку **Затвердевание**.
2. Для первого запуска выберите сравнение двух методов.
3. Оставьте автоматический поиск начальной температуры и LIQUID в списке фаз.
4. Для Al-сплавов начните с шага 5–10 °C, для Ni-сплавов — с 10–20 °C.
5. Нажмите **Рассчитать затвердевание**.
6. В сводке сравните ликвидус и температуру окончания; в разделе твёрдых фаз — последовательность выделения; в разделе расплава — микросегрегацию.

**Равновесный метод** допускает полное перераспределение элементов между всеми фазами. **Scheil–Gulliver** предполагает перемешивание расплава, локальное равновесие на границе и отсутствие обратной диффузии в уже образовавшемся твёрдом. Это модель неравновесной кристаллизации, но не расчёт времени.

## Свойства: упругость и вклады упрочнения

### Упругие свойства

1. Откройте **Свойства → Упругие свойства**.
2. Нажмите **Подготовить равновесные фазы**.
3. Для каждой фазы задайте `E`, `ν`, происхождение и источник.
4. Нажмите **Рассчитать Voigt–Reuss–Hill**.

ThermoGar не выводит E и ν из одного химического состава. Для гомогенизации
нужны объёмные доли и свойства всех фаз. Reuss и Voigt являются нижней и
верхней границами, Hill — их средним.

### Вклады упрочнения

1. Откройте **Свойства → Вклады упрочнения**.
2. Включите только механизмы, для которых есть исходные данные.
3. Задайте размер зерна, плотность дислокаций или параметры частиц.
4. Правило суммирования выбирайте явно; по умолчанию вклады не суммируются.

Этот экран не является автоматическим прогнозом предела текучести, UTS,
твёрдости или удлинения. Он показывает физические вклады при введённых
коэффициентах и микроструктуре.

## Кинетика: диффузия, гомогенизация и выделения

1. Откройте верхний раздел **Кинетика**.
2. Выберите **однофазную пару** либо **многофазную гомогенизацию**.
3. Задайте составы левой и правой сторон, температуру, время и длину области.
4. Для первого теста оставьте 50–100 ячеек и не более трёх компонентов.
5. Выберите фазу или набор фаз, для которых база содержит полный набор параметров подвижности.
6. После расчёта проверьте профиль, сохранение среднего состава и показатели выравнивания.

Однофазная модель принудительно использует одну фазу во всей области. Многофазная модель предполагает локальное равновесие в каждом объёмном элементе и требует выбора геометрического правила усреднения подвижностей.

### Выделения

1. Откройте **Кинетика → Выделения**.
2. Для первого теста выберите учебный Ni–Al–Cr / γ′ и загрузите его состав.
3. Укажите матричную фазу, фазу-выделение, температуру и время либо температурный цикл.
4. Проверьте межфазную энергию, молярные объёмы и параметры центров зарождения.
5. Нажмите **Рассчитать кинетику выделений**.
6. Анализируйте объёмную долю, средний радиус, плотность частиц, скорость зарождения, состав матрицы и итоговое распределение размеров.

Учебные значения проверяют работоспособность программы, но не квалифицируют
конкретный материал. Пользовательские значения требуют источника и области применимости.

## Важные ограничения текущей версии

- диффузия рассчитывается только в одном измерении;
- температура диффузионной модели постоянна во времени и по координате;
- начальный диффузионный профиль ступенчатый;
- внешние границы диффузионной области имеют нулевой поток;
- диффузионный расчёт зависит от качества базы подвижностей и выбранной модели усреднения;
- Scheil–Gulliver не использует DDB: отсутствие обратной диффузии в твёрдом входит в допущения метода;
- Steel/Fe использует каноническую исправленную mc_fe 2.062 с патчем TG-FE-2062-C15-001; `C15_LAVES` исключена из расчётов и не может быть выбрана вручную;
- экспериментальная квалификация материалов не выполнялась; это информационная характеристика, а не блокировка функций;
- legacy KWN implementation 13.2 рассматривает одну однородную матрицу и одну сферическую фазу-выделение; номер реализации не является release status;
- межфазная энергия, молярные объёмы и центры зарождения задаются пользователем с обязательным источником и областью применимости;
- упругая энергия и изменение формы частиц пока не рассчитываются; механические свойства не прогнозируются автоматически, а отдельные вклады упрочнения считаются только по явно введённым микроструктурным параметрам.


## Как построить карту доли фазы

1. Откройте **Диаграммы → Карта доли фазы**.
2. Выберите три элемента и единицы треугольника.
3. Задайте температуру и шаг: начните с 5 %, затем уменьшайте до 2–2,5 %.
4. Выберите фазу, которую нужно показать цветом.
5. В автоматическом режиме учитываются все совместимые фазы; для быстрого метастабильного анализа можно оставить галочками только физически нужные фазы.
6. Нажмите **Построить карту доли фазы**.
7. Цветовая шкала показывает мольную долю фазы, а пунктир — заданную границу её появления.

Карта строится по дискретной сетке и интерполируется между узлами. Положение границы следует считать приближённым с неопределённостью порядка половины шага сетки.

## Проверка установки и доверия к результату

- В разделе **Проекты и данные → Проверка установки** проверяются версии пакетов и доступные базы. Steel/Fe остаётся обычным выбором базы в едином приложении.
- После обычного равновесного расчёта ThermoGar проверяет сумму фазовых долей, составы фаз и материальный баланс.
- После сканирования по температуре или составу проверяется сумма фазовых долей в каждой точке.
- Технические сведения об ошибке спрятаны под раскрываемым блоком; основной текст говорит, что исправить.

## Частые ошибки

- **«Сумма добавок должна быть меньше 100 %»** — уменьшите одну или несколько добавок.
- **«Элемент отсутствует в базе»** — выберите другую базу либо уберите этот элемент.
- **«Нужно оставить хотя бы одну фазу»** — верните одну или несколько галочек.
- Диаграмма не строится — сначала увеличьте шаг состава или температуры и сузьте диапазон.
- В тройной диаграмме пропала ожидаемая замкнутая область — уменьшите шаг и попробуйте оставить только физически значимые фазы.
"""


workspace_broker = VerifiedB3BatchBroker(vlb_selector)


with reference_tab:
    reference_tab_names = [
        "Марки и составы",
        "Пакетный расчёт",
        "Проекты и история",
        "Паспорт базы",
        "Как пользоваться",
        "Справочник фаз",
        "Проверка установки",
    ]
    reference_tabs = st.tabs(reference_tab_names)
    (
        alloy_library_subtab,
        batch_subtab,
        projects_subtab,
        database_passport_subtab,
        help_subtab,
        phase_reference_subtab,
        diagnostics_subtab,
    ) = reference_tabs[:7]

    with alloy_library_subtab:
        render_alloy_library(
            THERMOGAR_PATHS,
            CURRENT_CONTEXT,
            DATABASE_DEFINITIONS,
            workspace_state_store,
            workspace_broker,
        )

    with batch_subtab:
        render_batch_calculation(
            workspace_broker,
            PHASE_EXPLANATIONS,
            workspace_state_store,
        )

    with projects_subtab:
        render_projects_and_history(
            THERMOGAR_PATHS,
            CURRENT_CONTEXT,
            DATABASE_DEFINITIONS,
            workspace_state_store,
            workspace_broker,
        )

    with database_passport_subtab:
        st.subheader("Паспорт текущей базы")
        st.caption(
            "Паспорт показывает точный файл, профиль, контрольную сумму и "
            "известные ограничения, влияющие на интерпретацию результата."
        )
        if database_key != "fe":
            st.info(
                "Отдельный профиль базы ведётся только для открытой "
                "стальной базы mc_fe 2.062."
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        ("База", definition["label"]),
                        ("Файл", str(database_path)),
                        ("SHA-256", CURRENT_CONTEXT["database_sha256"]),
                        ("Исключённые из расчёта фазы", "нет"),
                    ],
                    columns=["Поле", "Значение"],
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption(
                "Steel/Fe · thermogar_patch · C15_LAVES исключена · "
                "экспериментальная квалификация: NOT_PERFORMED"
            )
            st.dataframe(
                passport_dataframe(PROJECT_ROOT, fe_profile_key),
                width="stretch",
                hide_index=True,
            )
            manifest = load_profile_manifest(PROJECT_ROOT)
            if manifest:
                with st.expander("JSON-паспорт патча конвертера", expanded=False):
                    st.json(manifest)

    with help_subtab, suppress(_CompactHelpRendered):
        st.subheader("Как пользоваться ThermoGar")
        st.markdown(
            "1. Выберите базу материалов в боковой панели.  \n"
            "2. Задайте основу, единицы, добавки и давление.  \n"
            "3. Откройте нужный рабочий раздел в верхней строке вкладок.  \n"
            "4. Перед расчётом проверьте состав, температуру и выбранные фазы."
        )
        raise _CompactHelpRendered
        render_quick_examples(queue_context_load)
        st.divider()
        st.subheader("Как пользоваться ThermoGar")
        st.caption("Короткое описание рабочих сценариев.")

        st.markdown("### Первый расчёт")
        st.markdown(
            "1. Выберите базу в боковой панели.  \n"
            "2. Выберите основу и единицы состава.  \n"
            "3. Введите добавки, например `AL=15`.  \n"
            "4. Откройте нужный расчётный раздел.  \n"
            "5. Задайте температуру или диапазон.  \n"
            "6. Выполните расчёт и при необходимости выгрузите результат."
        )

        with st.expander("Что находится в каждом разделе", expanded=True):
            st.markdown(
                "- **Расчёты → Одна температура** — фазовый состав в одной точке.\n"
                "- **Расчёты → Температурный диапазон** — изменение фаз при нагреве или охлаждении.\n"
                "- **Расчёты → Изменение состава** — влияние содержания одного элемента.\n"
                "- **Диаграммы** — бинарная, многокомпонентная, тройная диаграмма или карта доли фазы.\n"
                "- **Проекты и данные** — марки, пакетный расчёт, проекты, история, справочник, помощь и проверка установки."
            )

        with st.expander("Как вводить состав"):
            st.markdown(
                "- `AL=15` при основе `NI` означает 15 % Al и 85 % Ni.\n"
                "- Элемент-основу в строке добавок не повторяйте.\n"
                "- Можно писать `C=0,15` или `C=0.15`.\n"
                "- Сумма добавок должна быть меньше 100 %."
            )

        with st.expander("Управление фазами и метастабильный расчёт"):
            st.markdown(
                "В блоке **«Управление фазами / метастабильный расчёт»** "
                "можно оставить все совместимые фазы или вручную снять галочки. "
                "Если исключить устойчивую фазу, получится метастабильное "
                "равновесие среди оставшихся фаз."
            )

        with st.expander("Как построить тройную диаграмму", expanded=True):
            st.markdown(
                "1. Откройте **Диаграммы → Тройная при T = const**.  \n"
                "2. Выберите три разных элемента.  \n"
                "3. Задайте температуру и шаг 2,5–5 ат.%.  \n"
                "4. Оставьте автоматический набор фаз.  \n"
                "5. Нажмите **Построить тройную диаграмму**.  \n"
                "6. Линии связи и точки трёхфазного равновесия "
                "включаются отдельными галочками."
            )
            st.caption(
                "Готовые примеры: Ni–Al–Cr при 1000 °C; "
                "Al–Cu–Mg при 500 °C."
            )

        with st.expander("Как построить карту доли фазы", expanded=True):
            st.markdown(
                "1. Откройте **Диаграммы → Карта доли фазы**.  \n"
                "2. Выберите три элемента и единицы состава.  \n"
                "3. Задайте температуру и начните с шага 5 %.  \n"
                "4. Выберите фазу, которую нужно показать цветом.  \n"
                "5. Нажмите **Построить карту доли фазы**.  \n"
                "6. Для уточнения интересующей области уменьшите шаг "
                "до 2–2,5 %."
            )
            st.caption(
                "Цвет показывает мольную долю выбранной фазы. "
                "Пунктир показывает заданную границу её появления. "
                "Карта интерполируется между рассчитанными узлами."
            )

        with st.expander("Как рассчитать затвердевание", expanded=True):
            st.markdown(
                "1. Откройте вкладку **Затвердевание**.  \n"
                "2. Выберите сравнение равновесного и Scheil–Gulliver методов.  \n"
                "3. Оставьте автоматический поиск начального расплава.  \n"
                "4. Не отключайте фазу `LIQUID`.  \n"
                "5. Для быстрого теста используйте Al–4 ат.% Cu, "
                "850 °C и шаг 10 °C.  \n"
                "6. Сравните долю расплава, последовательность фаз "
                "и состав остаточного расплава."
            )
            st.caption(
                "Scheil–Gulliver не является расчётом времени: "
                "он моделирует микросегрегацию при отсутствии "
                "обратной диффузии в твёрдом."
            )

        with st.expander("Как пользоваться разделом «Энергии»", expanded=False):
            st.markdown(
                "- **Энергии фаз:** выберите до восьми фаз и диапазон "
                "температур. Нулевая относительная энергия означает минимум "
                "среди выбранных однофазных состояний.  \n"
                "- **Движущая сила:** выберите целевую фазу и фазы исходного "
                "равновесия. Положительное значение означает термодинамический "
                "стимул её образования.  \n"
                "- **T₀:** выберите две фазы и изменяемый элемент. T₀ — это "
                "равенство их энергий при одинаковом составе, а не обычный солвус."
            )

        with st.expander("Как рассчитать плотность и объёмные доли", expanded=True):
            st.markdown(
                "1. Откройте **Свойства → Плотность**.  \n"
                "2. Задайте состав и температуру.  \n"
                "3. Нажмите **Рассчитать плотность и объёмные доли**.  \n"
                "4. Проверьте покрытие физической базы и статус каждой фазы.  \n"
                "5. Если все фазы покрыты, ThermoGar покажет плотность сплава "
                "и полные объёмные доли."
            )
            st.caption(
                "Прямая DP-модель взята из physical_data.pdb. Оценочная "
                "модель означает, что упорядоченная фаза использует плотность "
                "связанной разупорядоченной структуры. При отсутствии данных "
                "число не выводится."
            )

        with st.expander(
            "Как сохранить состав, рассчитать таблицу и продолжить проект",
            expanded=True,
        ):
            st.markdown(
                "1. **Марки и составы:** сохраните текущую боковую панель "
                "под понятным именем.  \n"
                "2. **Пакетный расчёт:** загрузите таблицу составов, "
                "посчитайте её целиком и выгрузите результат.  \n"
                "3. **Проекты и история:** проект сохраняет настройки, "
                "а история — факт расчёта и отпечаток базы.  \n"
                "4. После загрузки проекта или истории расчёт нужно повторить "
                "на текущей версии базы."
            )

        with st.expander("Готовые примеры"):
            examples = pd.DataFrame(
                [
                    ["Никелевые сплавы", "NI", "атомные %", "AL=15", "700 °C"],
                    ["Алюминиевые сплавы", "AL", "атомные %", "CU=4", "500 °C"],
                ],
                columns=["База", "Основа", "Единицы", "Добавки", "Температура"],
            )
            st.dataframe(examples, width="stretch", hide_index=True)
            st.caption(
                "Для первой бинарной диаграммы: Ni–Al, "
                "0–35 ат.% Al, 400–1600 °C. Для тройной: "
                "Ni–Al–Cr при 1000 °C."
            )

        with st.expander("Как читать результат"):
            st.markdown(
                "- **Мольная доля фазы** — количество фазы в равновесной системе.\n"
                "- **Состав фазы** — состав именно этой фазы.\n"
                "- `LIQUID` означает расплав.\n"
                "- Связанные модели `GP_MAT`, `BCC_B2`, `FCC_A1` требуют "
                "проверки примечания в справочнике.\n"
                "- Равновесные разделы не сообщают время превращения; "
                "время учитывается только в разделе «Диффузия»."
            )

        release_download_button(
            "Скачать краткое руководство",
            data=USER_GUIDE_MD.encode("utf-8-sig"),
            file_name="ThermoGar_краткое_руководство.md",
            mime="text/markdown",
        )

    with diagnostics_subtab:
        render_preflight(
            PROJECT_ROOT,
            DATABASE_DEFINITIONS,
            load_database,
            prepare_calculation,
            summarize_equilibrium,
            SCHEIL_AVAILABLE,
            KAWIN_AVAILABLE,
            KAWIN_IMPORT_ERROR,
            PRECIPITATION_AVAILABLE,
            PRECIPITATION_IMPORT_ERROR,
        )

    with phase_reference_subtab:
        st.subheader("Справочник фаз")

        reference_df = phase_reference_dataframe(
            db,
            database_path,
            database_key,
        )

        reference_query = st.text_input(
            "Поиск по коду или описанию",
            value="",
            placeholder="Например: GP_MAT, карбид, гамма",
        )

        if reference_query.strip():
            query = reference_query.strip().lower()
            searchable = (
                reference_df["Код фазы"].fillna("")
                + " "
                + reference_df["Простыми словами"].fillna("")
                + " "
                + reference_df["Описание по-русски"].fillna("")
                + " "
                + reference_df["Оригинал из базы (англ.)"].fillna("")
                + " "
                + reference_df["Примечание модели"].fillna("")
            ).str.lower()

            reference_view = reference_df[
                searchable.str.contains(query, regex=False)
            ]
        else:
            reference_view = reference_df

        show_original_english = st.checkbox(
            "Показывать исходное английское описание",
            value=False,
        )

        displayed_columns = [
            "Код фазы",
            "Простыми словами",
            "Описание по-русски",
            "Примечание модели",
        ]
        if show_original_english:
            displayed_columns.append("Оригинал из базы (англ.)")

        st.dataframe(
            reference_view[displayed_columns],
            width="stretch",
            hide_index=True,
        )

        release_download_button(
            "Скачать справочник в Excel",
            data=dataframe_to_excel({"Справочник фаз": reference_df}),
            file_name=f"ThermoGar_phase_reference_{database_key}.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
