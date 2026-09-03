"""Библиотека составов, пакетный расчёт, проекты и история ThermoGar.

Модуль получает расчётные функции из основного приложения и хранит
пользовательские данные только в каноническом профиле ``ThermoGarPaths``
(``%LOCALAPPDATA%\\ThermoGar`` либо ``THERMOGAR_STATE_ROOT``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import re
import uuid
from typing import Any, Callable, Mapping, Protocol

import numpy as np
import pandas as pd
import streamlit as st
from thermogar_release_policy import (
    APP_STAGE,
    APP_VERSION,
    PRODUCTION_USE,
    RELEASE_DATABASE_ELEMENTS,
    RELEASE_CLASS,
    RELEASE_DATABASE_KEYS,
    SCIENTIFIC_MATERIAL_STATUS,
    SOFTWARE_RELEASE_STATUS,
)
from thermogar_release_ui import (
    release_calculation_button,
    verified_batch_execute_button,
    verified_batch_export_button,
    verified_state_uploader,
)
from thermogar_verified_loaders import (
    FeatureReceipt,
    FeatureRequest,
    RejectedFeatureReceipt,
    ResultEnvelope,
)
from thermogar_paths import ThermoGarPaths
from thermogar_verified_state import (
    ALLOY_UI_TYPES,
    ALLOY_UPLOAD_KEY,
    BATCH_ALIAS_PAIRS,
    BATCH_UI_TYPES,
    BATCH_UPLOAD_KEY,
    HISTORY_HEADERS,
    PROJECT_UI_TYPES,
    PROJECT_UPLOAD_KEY,
    StateStore,
    VerifiedArtifactRef,
    batch_result_value,
    batch_template_value,
    semantic_digest_for,
)
from thermogar_secure_io import (
    MAX_WORKSPACE_FILE_BYTES,
    atomic_update_bytes,
    atomic_write_bytes,
    ensure_plain_directory,
    held_verified_snapshot,
    read_verified_snapshot,
    secure_archive_and_clear,
    secure_move_no_overwrite,
)


STORAGE_SCHEMA_VERSION = 1

# Версия набора настроек, который проект сохраняет и восстанавливает.
# Восстанавливаются только числовые и логические настройки расчётных
# разделов: их нельзя сделать недопустимыми для выпадающего списка,
# поэтому загрузка чужого проекта не может сломать интерфейс.
WIDGET_STATE_VERSION = 1
WIDGET_STATE_VERSION_FIELD = "_version"
RESTORABLE_WIDGET_PREFIXES: tuple[str, ...] = (
    "b4b2_hall_",
    "b4b2_orowan_",
    "b4b2_other_",
    "b4b2_solid_",
    "b4b2_taylor_",
    "b4b2_elastic_temperature_",
    "binary_c_",
    "binary_nodes_",
    "binary_t_",
    "binary_tielines_",
    "concentration_temperature_",
    "concentration_threshold",
    "driving_exclude_target_",
    "driving_t_",
    "energy_t_",
    "isopleth_nodes_",
    "isopleth_t_",
    "physical_t_",
    "physical_temperature_",
    "single_temperature_",
    "solidification_adaptive_",
    "solidification_auto_start_",
    "solidification_binary_tol_",
    "solidification_pdens_",
    "solidification_start_increment_",
    "solidification_step_",
    "solidification_stop_",
    "t_max_",
    "t_min_",
    "t_step_",
    "ternary_map_step_",
    "ternary_map_temperature_",
    "ternary_map_threshold_",
    "ternary_nodes_",
    "ternary_step_",
    "ternary_temperature_",
    "ternary_tieline_every_",
    "ternary_tielines_",
    "tzero_c_",
    "tzero_t_",
)
# Настройки заводятся отдельно для каждой базы, поэтому за сеанс, в котором
# пользователь прошёл все три, их набирается около сотни. Предел нужен только
# как граница размера файла проекта.
MAX_WIDGET_STATE_KEYS = 500

FE_DATABASE_KEY = "fe"
FE_PROFILE_CANONICAL = "thermogar_patch"
# Fe-профиль исключает C15_LAVES из фаз, доступных пользователю.
EXCLUDED_PHASES = {FE_DATABASE_KEY: ("C15_LAVES",)}
FE_DATABASE_RELATIVE_PATH = (
    "databases/converted/fe/"
    "mc_fe_v2062_with_mobility.thermogar.tdb"
)
FE_DATABASE_SHA256 = (
    "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612"
)
FE_DATABASE_ELEMENTS = frozenset(
    {
        "AL", "B", "C", "CO", "CR", "CU", "FE", "H", "HF", "LA",
        "MN", "MO", "N", "NB", "NI", "O", "P", "PD", "S", "SI",
        "TA", "TI", "V", "W", "Y",
    }
)
PRODUCT_DATABASE_KEYS = frozenset((*RELEASE_DATABASE_KEYS, FE_DATABASE_KEY))


# Понятные пользователю причины отказа. Ключ — код проверки схемы; сам код
# и техническая деталь проверки в интерфейс не выводятся.
REJECTION_MESSAGES: dict[str, str] = {
    "USER_INPUT_REQUIRED": "Выберите файл.",
    "IMPORT_SCHEMA_REJECTED": (
        "Файл не соответствует ожидаемой структуре и не был принят."
    ),
    "C15_PHASE_REJECTED": (
        "В файле указана фаза C15_LAVES. Для стального профиля "
        "thermogar_patch она исключена; уберите её и повторите загрузку."
    ),
    "ARTIFACT_OVERSIZE": "Файл слишком большой и не был прочитан.",
    "ARTIFACT_MISSING": "Файл не найден.",
    "ARTIFACT_IO_FAILED": "Файл не удалось прочитать целиком.",
    "ARTIFACT_WRITE_FAILED": "Не удалось записать файл в папку данных ThermoGar.",
    "CANONICAL_JSON_INVALID": "Файл не является корректным JSON.",
    "SCHEMA_INVALID": "Структура файла не совпадает с ожидаемой.",
    "INPUT_INVALID": "Введённые значения не проходят проверку.",
    "DATABASE_KEY_REJECTED": "В файле указана база, которой нет в ThermoGar.",
    "PROFILE_KEY_REJECTED": "В файле указан недопустимый профиль базы.",
    "PATCH_ID_MISMATCH": "Профиль стальной базы в файле не совпадает с текущим.",
    "TDB_HASH_MISMATCH": "Контрольная сумма базы в файле не совпадает с текущей.",
    "PASSPORT_REQUIRED": "Для стальной базы требуется паспорт профиля.",
    "BINDING_STALE": (
        "Выбор базы изменился, пока готовился файл. Повторите действие."
    ),
    "GENERATION_STALE": (
        "Выбор базы изменился, пока готовился файл. Повторите действие."
    ),
    "BINDING_IDENTITY_MISMATCH": (
        "Данные файла не соответствуют выбранной базе."
    ),
    "STATE_CONFLICT": "Файл изменился во время операции; повторите действие.",
    "CAPABILITY_UNAVAILABLE": "Это действие недоступно для выбранного файла.",
    "EXPORT_SOURCE_REJECTED": "Нечего выгружать: исходные данные не приняты.",
}


def rejection_text(receipt: Any) -> str:
    """Перевести отказ проверки схемы в сообщение для пользователя."""

    code = str(getattr(receipt, "reason_code", "") or "")
    return REJECTION_MESSAGES.get(
        code,
        "Действие отклонено проверкой данных. Проверьте выбранный файл "
        "и текущую базу.",
    )


def show_rejection(receipt: Any, prefix: str = "") -> None:
    """Показать понятный отказ вместо технической квитанции."""

    text = rejection_text(receipt)
    st.error(f"{prefix} {text}".strip() if prefix else text)


def _flash_key(section: str) -> str:
    return f"_thermogar_flash_{section}"


def flash(section: str, kind: str, message: str) -> None:
    """Запомнить сообщение, которое переживёт немедленный ``st.rerun``.

    Раздел указывается явно: Streamlit рисует все вкладки на каждом прогоне,
    и общая очередь показала бы сообщение в чужой вкладке.
    """

    key = _flash_key(section)
    pending = st.session_state.get(key)
    if not isinstance(pending, list):
        pending = []
    pending.append({"kind": kind, "message": message})
    st.session_state[key] = pending


def render_flash(section: str) -> None:
    """Показать сообщения раздела, отложенные предыдущим прогоном."""

    pending = st.session_state.pop(_flash_key(section), None)
    if not isinstance(pending, list):
        return
    renderers = {
        "success": st.success,
        "warning": st.warning,
        "error": st.error,
        "info": st.info,
    }
    for item in pending:
        if not isinstance(item, dict):
            continue
        renderer = renderers.get(str(item.get("kind", "info")), st.info)
        renderer(str(item.get("message", "")))


DEMO_ALLOYS: list[dict[str, Any]] = [
    {
        "id": "demo-ni-15al",
        "name": "Пример Ni–15Al",
        "database_key": "ni",
        "balance": "NI",
        "units": "at",
        "composition": "AL=15",
        "pressure_pa": 101325.0,
        "steel_mode": "stable",
        "notes": "Проверочный состав для γ/γ′-расчётов.",
        "origin": "demo",
    },
    {
        "id": "demo-al-4cu",
        "name": "Пример Al–4Cu",
        "database_key": "al",
        "balance": "AL",
        "units": "at",
        "composition": "CU=4",
        "pressure_pa": 101325.0,
        "steel_mode": "stable",
        "notes": "Проверочный состав для Al–Cu.",
        "origin": "demo",
    },
]


# ---------------------------------------------------------------------------
# Общие файловые операции
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def workspace_directory(paths: ThermoGarPaths) -> Path:
    if not isinstance(paths, ThermoGarPaths):
        raise TypeError("paths must be a ThermoGarPaths instance")
    directory = ensure_plain_directory(paths.workspace_root)
    ensure_plain_directory(paths.projects_root)
    return directory


def safe_slug(value: str, fallback: str = "project") -> str:
    normalized = re.sub(r"[^0-9A-Za-zА-Яа-яЁё_-]+", "_", value.strip())
    normalized = normalized.strip("_-")
    return normalized[:80] or fallback


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def payload_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _workspace_canonical_root(paths: ThermoGarPaths) -> Path:
    if not isinstance(paths, ThermoGarPaths):
        raise TypeError("paths must be a ThermoGarPaths instance")
    return paths.state_root


def atomic_write_json(
    paths: ThermoGarPaths,
    path: str | Path,
    payload: Any,
    *,
    create_backup: bool = True,
    overwrite: bool = True,
) -> None:
    atomic_write_bytes(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        create_backup=create_backup,
        overwrite=overwrite,
        canonical_root=_workspace_canonical_root(paths),
    )

def read_json(paths: ThermoGarPaths, path: str | Path, default: Any) -> Any:
    source = Path(path)
    try:
        source.lstat()
    except FileNotFoundError:
        return default
    try:
        snapshot = read_verified_snapshot(
            source,
            maximum_bytes=MAX_WORKSPACE_FILE_BYTES,
            canonical_root=_workspace_canonical_root(paths),
        )
        return json.loads(snapshot.data.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Файл {source.name} не читается. "
            "Не заменяйте его пустым файлом: восстановите резервную копию "
            f"или исправьте JSON. Техническая причина: {error}"
        ) from error

def make_envelope(kind: str, payload: Any) -> dict[str, Any]:
    body = {
        "schema_version": STORAGE_SCHEMA_VERSION,
        "kind": kind,
        "exported_at": now_iso(),
        "payload": payload,
    }
    body["sha256"] = payload_sha256(body)
    return body


def validate_iso_timestamp(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Поле {field_name} должно быть ISO-датой со смещением.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            f"Поле {field_name} должно быть ISO-датой со смещением."
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Поле {field_name} должно содержать часовой пояс.")
    return value


def validate_envelope(envelope: Any, expected_kind: str) -> Any:
    if not isinstance(envelope, dict):
        raise ValueError("Файл должен содержать JSON-объект.")
    required_keys = {
        "schema_version",
        "kind",
        "exported_at",
        "payload",
        "sha256",
    }
    missing_keys = sorted(required_keys - set(envelope))
    extra_keys = sorted(set(envelope) - required_keys)
    if missing_keys:
        raise ValueError(
            "В envelope отсутствуют обязательные поля: "
            + ", ".join(missing_keys)
            + "."
        )
    if extra_keys:
        raise ValueError(
            "Envelope содержит неизвестные поля: "
            + ", ".join(extra_keys)
            + "."
        )
    if (
        type(envelope.get("schema_version")) is not int
        or envelope.get("schema_version") != STORAGE_SCHEMA_VERSION
    ):
        raise ValueError(
            "Неподдерживаемая версия схемы: ожидалась "
            f"{STORAGE_SCHEMA_VERSION!r}, получена "
            f"{envelope.get('schema_version')!r}. Автоматическая миграция "
            "не выполняется."
        )
    if envelope.get("kind") != expected_kind:
        raise ValueError(
            f"Ожидался файл типа {expected_kind!r}, "
            f"получен {envelope.get('kind')!r}."
        )
    validate_iso_timestamp(envelope.get("exported_at"), "exported_at")
    expected_hash = envelope.get("sha256")
    if not isinstance(expected_hash, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_hash
    ):
        raise ValueError("Обязательная контрольная сумма SHA-256 отсутствует или неверна.")
    content = dict(envelope)
    content.pop("sha256", None)
    actual_hash = payload_sha256(content)
    if expected_hash != actual_hash:
        raise ValueError("Контрольная сумма файла не совпала.")
    return envelope.get("payload")


def validate_context_payload(context: Any) -> dict[str, Any]:
    """Validate restorable inputs without inventing missing values."""

    if not isinstance(context, dict):
        raise ValueError("Контекст должен быть JSON-объектом.")
    required = {
        "database_key",
        "balance",
        "units",
        "composition",
        "pressure_pa",
        "steel_mode",
    }
    known_optional = {
        "database_path",
        "database_sha256",
        "database_label",
        "fe_profile_key",
    }
    missing = sorted(required - set(context))
    extra = sorted(set(context) - required - known_optional)
    if missing:
        raise ValueError(
            "Контекст неполон; отсутствуют поля: " + ", ".join(missing) + "."
        )
    if extra:
        raise ValueError(
            "Контекст содержит неизвестные поля: " + ", ".join(extra) + "."
        )
    if not isinstance(context["database_key"], str):
        raise ValueError("Ключ базы должен быть строкой.")
    database_key = context["database_key"].strip().casefold()
    if database_key not in PRODUCT_DATABASE_KEYS:
        raise ValueError(
            f"База {database_key!r} не входит в доступную поверхность ThermoGar."
        )
    if not isinstance(context["balance"], str):
        raise ValueError("Элемент-основа должен быть строкой.")
    balance = context["balance"].strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_+-]*", balance):
        raise ValueError("Основа состава отсутствует или имеет неверный формат.")
    allowed_elements = (
        FE_DATABASE_ELEMENTS
        if database_key == FE_DATABASE_KEY
        else RELEASE_DATABASE_ELEMENTS[database_key]
    )
    if balance not in allowed_elements:
        raise ValueError(
            f"Элемент-основа {balance!r} отсутствует в базе {database_key!r}."
        )
    if not isinstance(context["units"], str):
        raise ValueError("Единицы состава должны быть строкой.")
    units = context["units"].strip().casefold()
    if units not in {"at", "wt"}:
        raise ValueError("Единицы должны быть строго 'at' или 'wt'.")
    if not isinstance(context["steel_mode"], str):
        raise ValueError("Режим должен быть строкой.")
    steel_mode = context["steel_mode"].strip().casefold()
    if steel_mode not in {"stable", "metastable"}:
        raise ValueError("Режим должен быть строго 'stable' или 'metastable'.")
    if isinstance(context["pressure_pa"], bool):
        raise ValueError("Давление должно быть конечным положительным числом.")
    try:
        pressure_pa = float(context["pressure_pa"])
    except (TypeError, ValueError) as error:
        raise ValueError("Давление должно быть конечным положительным числом.") from error
    if not math.isfinite(pressure_pa) or pressure_pa <= 0.0:
        raise ValueError("Давление должно быть конечным положительным числом.")
    composition = context["composition"]
    if not isinstance(composition, str):
        raise ValueError("Состав должен быть строкой без автоматического преобразования.")
    composition = composition.strip()
    if composition:
        pattern = re.compile(
            r"([A-Za-z]{1,2})\s*=\s*([+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+))"
        )
        matches = list(pattern.finditer(composition))
        remainder = pattern.sub("", composition)
        remainder = re.sub(r"[\s,;]+", "", remainder)
        if not matches or remainder:
            raise ValueError("Состав имеет неверный формат; пример: AL=15, CR=10.")
        values: dict[str, float] = {}
        for match in matches:
            element = match.group(1).upper()
            if element in values:
                raise ValueError(f"Элемент {element} указан более одного раза.")
            if element not in allowed_elements:
                raise ValueError(
                    f"Элемент {element!r} отсутствует в базе {database_key!r}."
                )
            if element == balance:
                raise ValueError(
                    f"{balance} выбран как основа и не должен повторяться в добавках."
                )
            value = float(match.group(2).replace(",", "."))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"Содержание {element} должно быть больше нуля.")
            values[element] = value
        if sum(values.values()) >= 100.0:
            raise ValueError("Сумма добавок должна быть меньше 100 %.")
    if "database_path" in context and (
        not isinstance(context["database_path"], str)
        or not context["database_path"].strip()
    ):
        raise ValueError("Путь базы в контексте должен быть непустой строкой.")
    if "database_label" in context and (
        not isinstance(context["database_label"], str)
        or not context["database_label"].strip()
    ):
        raise ValueError("Название базы в контексте должно быть непустой строкой.")
    fe_profile_key = context.get("fe_profile_key")
    if database_key == FE_DATABASE_KEY:
        if fe_profile_key != FE_PROFILE_CANONICAL:
            raise ValueError(
                "Fe-контекст отклонён: требуется единственный профиль "
                f"{FE_PROFILE_CANONICAL!r}; получен {fe_profile_key!r}."
            )
        database_path = context.get("database_path")
        if database_path:
            normalized_path = str(database_path).replace("\\", "/").casefold()
            expected_path = FE_DATABASE_RELATIVE_PATH.casefold()
            if not (
                normalized_path == expected_path
                or normalized_path.endswith("/" + expected_path)
            ):
                raise ValueError(
                    "Fe-контекст отклонён: путь базы не соответствует "
                    "каноническому профилю thermogar_patch."
                )
    elif fe_profile_key is not None:
        raise ValueError("Fe-профиль не допускается для Ni/Al-контекста.")
    database_sha256 = context.get("database_sha256", "")
    if not isinstance(database_sha256, str) or (
        database_sha256
        and not re.fullmatch(r"[0-9a-f]{64}", database_sha256)
    ):
        raise ValueError("SHA-256 базы в контексте имеет неверный формат.")
    if database_key == FE_DATABASE_KEY and database_sha256 != FE_DATABASE_SHA256:
        raise ValueError(
            "Fe-контекст отклонён: SHA-256 базы отсутствует или не совпадает "
            "с каноническим профилем thermogar_patch."
        )
    clean = {
        "database_key": database_key,
        "balance": balance,
        "units": units,
        "composition": composition,
        "pressure_pa": pressure_pa,
        "steel_mode": steel_mode,
    }
    if database_sha256:
        clean["database_sha256"] = database_sha256
    if database_key == FE_DATABASE_KEY:
        clean["fe_profile_key"] = FE_PROFILE_CANONICAL
    return clean


def context_from_history_entry(entry: Any) -> dict[str, Any]:
    """Extract only the restorable context from an authenticated history row."""

    if not isinstance(entry, dict):
        raise ValueError("Запись истории должна быть JSON-объектом.")
    fields = {
        "database_key",
        "balance",
        "units",
        "composition",
        "pressure_pa",
        "steel_mode",
    }
    context = {field: entry.get(field) for field in fields}
    if entry.get("database_sha256"):
        context["database_sha256"] = entry["database_sha256"]
    if "fe_profile_key" in entry:
        context["fe_profile_key"] = entry["fe_profile_key"]
    return validate_context_payload(context)


def validate_project_payload(payload: Any) -> dict[str, Any]:
    """Проверить схему проекта целиком; автоматическая миграция не делается."""

    if not isinstance(payload, dict):
        raise ValueError("Данные проекта должны быть JSON-объектом.")
    required = {
        "schema_version",
        "kind",
        "name",
        "description",
        "created_at",
        "updated_at",
        "app_stage",
        "app_version",
        "release_class",
        "software_release_status",
        "scientific_material_status",
        "production_use",
        "context",
        "widget_state",
    }
    missing = sorted(required - set(payload))
    extra = sorted(set(payload) - required)
    if missing or extra:
        parts = []
        if missing:
            parts.append("отсутствуют: " + ", ".join(missing))
        if extra:
            parts.append("неизвестны: " + ", ".join(extra))
        raise ValueError("Схема проекта не совпадает (" + "; ".join(parts) + ").")
    expected_identity = {
        "schema_version": STORAGE_SCHEMA_VERSION,
        "kind": "thermogar_project_payload",
        "app_stage": APP_STAGE,
        "app_version": APP_VERSION,
        "release_class": RELEASE_CLASS,
        "software_release_status": SOFTWARE_RELEASE_STATUS,
        "scientific_material_status": SCIENTIFIC_MATERIAL_STATUS,
        "production_use": PRODUCTION_USE,
    }
    if type(payload.get("schema_version")) is not int:
        raise ValueError(
            "Версия схемы проекта должна быть целым числом; "
            "автоматическое приведение типа отключено."
        )
    drift = {
        key: (expected, payload.get(key))
        for key, expected in expected_identity.items()
        if payload.get(key) != expected
    }
    if drift:
        raise ValueError(
            "Проект сохранён другой версией ThermoGar; автоматическое "
            "приведение не выполняется: " + repr(drift)
        )
    name = payload.get("name")
    description = payload.get("description")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        raise ValueError("Название проекта должно содержать от 1 до 200 символов.")
    if not isinstance(description, str):
        raise ValueError("Описание проекта должно быть строкой.")
    validate_iso_timestamp(payload.get("created_at"), "created_at")
    validate_iso_timestamp(payload.get("updated_at"), "updated_at")
    clean = dict(payload)
    clean["name"] = name.strip()
    clean["description"] = description.strip()
    clean["context"] = validate_context_payload(payload.get("context"))
    clean["widget_state"] = validate_widget_state(payload.get("widget_state"))
    return clean


# ---------------------------------------------------------------------------
# Контекст и перенос настроек в боковую панель
# ---------------------------------------------------------------------------


def context_snapshot(
    database_key: str,
    balance: str,
    units: str,
    composition: str,
    pressure_pa: float,
    steel_mode: str,
    database_path: str | Path,
    database_sha256: str,
    fe_profile_key: str | None = None,
) -> dict[str, Any]:
    path = Path(database_path)
    context = {
        "database_key": database_key,
        "balance": balance,
        "units": units,
        "composition": composition,
        "pressure_pa": float(pressure_pa),
        "steel_mode": steel_mode,
        "database_path": str(path),
        "database_sha256": database_sha256,
    }
    if database_key.strip().casefold() == FE_DATABASE_KEY:
        context["fe_profile_key"] = fe_profile_key
    return validate_context_payload(context)


def units_label(units: str) -> str:
    if units == "at":
        return "атомные %"
    if units == "wt":
        return "массовые %"
    return str(units).strip() or "—"

def steel_mode_label(mode: str) -> str:
    if mode == "metastable":
        return "Практический Fe–Fe₃C — цементит, без графита"
    return "Стабильный Fe–C — графит разрешён"


def queue_context_load(
    context: dict[str, Any],
    widget_state: dict[str, Any] | None = None,
    *,
    label: str = "",
) -> None:
    clean_context = validate_context_payload(context)
    st.session_state["_thermogar_pending_context"] = clean_context
    st.session_state["_thermogar_pending_context_label"] = label
    st.session_state["_thermogar_pending_widget_state"] = (
        validate_widget_state(widget_state) if widget_state else {}
    )

def apply_pending_state() -> None:
    """Применить отложенную загрузку до создания виджетов Streamlit."""
    pending_widgets = st.session_state.pop(
        "_thermogar_pending_widget_state",
        None,
    )

    context = st.session_state.pop("_thermogar_pending_context", None)
    label = st.session_state.pop("_thermogar_pending_context_label", "")
    if not isinstance(context, dict):
        return

    context = validate_context_payload(context)
    database_key = context["database_key"]
    st.session_state["thermogar_database_key"] = database_key
    if database_key == FE_DATABASE_KEY:
        st.session_state["thermogar_fe_profile"] = context["fe_profile_key"]
    else:
        st.session_state.pop("thermogar_fe_profile", None)
    st.session_state[f"thermogar_balance_{database_key}"] = str(
        context["balance"]
    ).upper()
    st.session_state[f"thermogar_units_{database_key}"] = units_label(
        context["units"]
    )
    st.session_state[f"thermogar_composition_{database_key}"] = str(
        context["composition"]
    )
    st.session_state["thermogar_pressure_pa"] = float(
        context["pressure_pa"]
    )
    st.session_state["thermogar_steel_mode"] = steel_mode_label(
        context["steel_mode"]
    )
    st.session_state["_thermogar_loaded_context"] = {
        "label": label,
        "database_key": database_key,
        "database_sha256": str(context.get("database_sha256", "")),
        "fe_profile_key": context.get("fe_profile_key"),
    }
    if isinstance(pending_widgets, dict):
        for key, value in pending_widgets.items():
            if key == WIDGET_STATE_VERSION_FIELD:
                continue
            st.session_state[key] = value


def is_restorable_widget_key(key: Any) -> bool:
    """Настройка входит в разрешённый набор и не может сломать виджет."""

    return isinstance(key, str) and key.startswith(RESTORABLE_WIDGET_PREFIXES)


def capture_widget_state() -> dict[str, Any]:
    """Собрать настройки расчётных разделов из разрешённого набора.

    Сохраняются только числа и флажки: их значение нельзя сделать
    недопустимым для списка вариантов, поэтому загрузка чужого проекта
    не может привести к отказу интерфейса.
    """

    result: dict[str, Any] = {WIDGET_STATE_VERSION_FIELD: WIDGET_STATE_VERSION}
    for key in sorted(st.session_state.keys()):
        if not is_restorable_widget_key(key):
            continue
        value = st.session_state[key]
        if isinstance(value, bool):
            result[key] = value
        elif isinstance(value, int):
            result[key] = int(value)
        elif isinstance(value, float) and math.isfinite(value):
            result[key] = float(value)
        if len(result) > MAX_WIDGET_STATE_KEYS:
            raise ValueError(
                "Настроек расчётных разделов больше, чем допускает проект."
            )
    return result


def validate_widget_state(widget_state: Any) -> dict[str, Any]:
    """Принять только текущую версию набора настроек и только её ключи."""

    if not isinstance(widget_state, dict):
        raise ValueError("Настройки проекта должны быть JSON-объектом.")
    if not widget_state:
        return {}
    version = widget_state.get(WIDGET_STATE_VERSION_FIELD)
    if type(version) is not int or version != WIDGET_STATE_VERSION:
        raise ValueError(
            "Настройки расчётных разделов сохранены другой версией "
            f"({version!r}); ожидается {WIDGET_STATE_VERSION!r}. "
            "Материал проекта загружается, настройки — нет."
        )
    if len(widget_state) - 1 > MAX_WIDGET_STATE_KEYS:
        raise ValueError(
            "Настроек расчётных разделов больше, чем допускает проект."
        )
    clean: dict[str, Any] = {WIDGET_STATE_VERSION_FIELD: WIDGET_STATE_VERSION}
    for key, value in widget_state.items():
        if key == WIDGET_STATE_VERSION_FIELD:
            continue
        if not is_restorable_widget_key(key):
            raise ValueError(
                f"Настройка {key!r} не входит в восстанавливаемый набор."
            )
        if isinstance(value, bool):
            clean[key] = value
        elif type(value) is int:
            clean[key] = value
        elif type(value) is float and math.isfinite(value):
            clean[key] = value
        else:
            raise ValueError(
                f"Настройка {key!r} должна быть числом или флажком."
            )
    return clean


# ---------------------------------------------------------------------------
# Библиотека пользовательских марок
# ---------------------------------------------------------------------------


def alloys_path(paths: ThermoGarPaths) -> Path:
    workspace_directory(paths)
    return paths.alloys_path


def load_user_alloys(paths: ThermoGarPaths) -> list[dict[str, Any]]:
    payload = read_json(paths, alloys_path(paths), {"alloys": []})
    alloys = payload.get("alloys", []) if isinstance(payload, dict) else []
    return [item for item in alloys if isinstance(item, dict)]


def _decode_user_alloys_bytes(data: bytes) -> list[dict[str, Any]]:
    if not data:
        return []
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "Файл alloys.json не читается; изменение библиотеки отклонено."
        ) from error
    alloys = payload.get("alloys", []) if isinstance(payload, dict) else []
    return [dict(item) for item in alloys if isinstance(item, dict)]


def _encode_user_alloys_bytes(alloys: list[dict[str, Any]]) -> bytes:
    return json.dumps(
        {
            "schema_version": STORAGE_SCHEMA_VERSION,
            "updated_at": now_iso(),
            "alloys": alloys,
        },
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def save_user_alloys(paths: ThermoGarPaths, alloys: list[dict[str, Any]]) -> None:
    atomic_write_bytes(
        alloys_path(paths),
        _encode_user_alloys_bytes(alloys),
        create_backup=True,
        overwrite=True,
        canonical_root=_workspace_canonical_root(paths),
    )


def upsert_user_alloy(
    paths: ThermoGarPaths,
    name: str,
    notes: str,
    context: dict[str, Any],
    *,
    overwrite: bool = True,
) -> dict[str, Any]:
    clean_context = validate_context_payload(context)
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Введите название марки или состава.")

    saved: dict[str, Any] = {}

    def mutate(existing_bytes: bytes) -> bytes:
        alloys = _decode_user_alloys_bytes(existing_bytes)
        current_time = now_iso()
        existing = next(
            (
                item
                for item in alloys
                if str(item.get("name", "")).casefold()
                == clean_name.casefold()
                and item.get("database_key")
                == clean_context.get("database_key")
            ),
            None,
        )
        if existing is not None and not overwrite:
            raise FileExistsError(
                "Запись с таким названием уже существует."
            )
        if existing is None:
            existing = {
                "id": uuid.uuid4().hex,
                "created_at": current_time,
                "origin": "user",
            }
            alloys.append(existing)

        existing.update(
            {
                "name": clean_name,
                "database_key": clean_context["database_key"],
                "balance": clean_context["balance"],
                "units": clean_context["units"],
                "composition": clean_context["composition"],
                "pressure_pa": clean_context["pressure_pa"],
                "steel_mode": clean_context["steel_mode"],
                "notes": notes.strip(),
                "updated_at": current_time,
            }
        )
        if clean_context.get("database_sha256"):
            existing["database_sha256"] = clean_context["database_sha256"]
        else:
            existing.pop("database_sha256", None)
        if clean_context.get("fe_profile_key"):
            existing["fe_profile_key"] = clean_context["fe_profile_key"]
        else:
            existing.pop("fe_profile_key", None)
        saved.update(existing)
        return _encode_user_alloys_bytes(alloys)

    path = alloys_path(paths)
    atomic_update_bytes(
        path,
        mutate,
        create_backup=True,
        canonical_root=_workspace_canonical_root(paths),
    )
    return saved


def delete_user_alloy(paths: ThermoGarPaths, alloy_id: str) -> None:
    def mutate(existing_bytes: bytes) -> bytes:
        alloys = [
            item
            for item in _decode_user_alloys_bytes(existing_bytes)
            if item.get("id") != alloy_id
        ]
        return _encode_user_alloys_bytes(alloys)

    path = alloys_path(paths)
    atomic_update_bytes(
        path,
        mutate,
        create_backup=True,
        canonical_root=_workspace_canonical_root(paths),
    )


def merge_user_alloys(
    paths: ThermoGarPaths,
    imported: list[dict[str, Any]],
    *,
    overwrite: bool,
) -> int:
    clean_imported = [dict(item) for item in imported if item.get("id")]

    def mutate(existing_bytes: bytes) -> bytes:
        merged = {
            item["id"]: item
            for item in _decode_user_alloys_bytes(existing_bytes)
            if item.get("id")
        }
        conflicts = [item["id"] for item in clean_imported if item["id"] in merged]
        if conflicts and not overwrite:
            raise ValueError(
                "Найдены совпадающие ID. Включите разрешение на замену "
                "либо импортируйте файл без конфликтующих записей."
            )
        for item in clean_imported:
            merged[item["id"]] = item
        return _encode_user_alloys_bytes(list(merged.values()))

    path = alloys_path(paths)
    atomic_update_bytes(
        path,
        mutate,
        create_backup=True,
        canonical_root=_workspace_canonical_root(paths),
    )
    return len(clean_imported)


def alloy_context(alloy: dict[str, Any]) -> dict[str, Any]:
    context = {
        "database_key": alloy["database_key"],
        "balance": alloy["balance"],
        "units": alloy["units"],
        "composition": alloy["composition"],
        "pressure_pa": alloy["pressure_pa"],
        "steel_mode": alloy["steel_mode"],
    }
    for field in ("database_sha256", "fe_profile_key"):
        if field in alloy:
            context[field] = alloy[field]
    return validate_context_payload(context)


def alloy_table(
    alloys: list[dict[str, Any]],
    database_definitions: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    for item in alloys:
        database_key = item.get("database_key", "")
        rows.append(
            {
                "Название": item.get("name", ""),
                "База": database_definitions.get(database_key, {}).get(
                    "label",
                    database_key,
                ),
                "Основа": item.get("balance", ""),
                "Единицы": units_label(item.get("units", "at")),
                "Добавки": item.get("composition", ""),
                "Заметка": item.get("notes", ""),
                "Источник": (
                    "пример ThermoGar"
                    if item.get("origin") == "demo"
                    else "пользователь"
                ),
            }
        )
    return pd.DataFrame(rows)


def render_alloy_library(
    paths: ThermoGarPaths,
    context: dict[str, Any],
    database_definitions: dict[str, dict[str, Any]],
    state_store: StateStore,
    state_broker: VerifiedBatchBroker,
) -> None:
    st.subheader("Библиотека марок и составов")
    st.caption(
        "Сохранённая запись запоминает базу, основу, единицы и состав. "
        "Учебные примеры помечены отдельно и не являются промышленными марками."
    )
    render_flash("alloys")

    current = pd.DataFrame(
        [
            {
                "База": database_definitions[context["database_key"]]["label"],
                "Основа": context["balance"],
                "Единицы": units_label(context["units"]),
                "Добавки": context["composition"],
            }
        ]
    )
    st.markdown("### Текущий состав")
    st.dataframe(current, width="stretch", hide_index=True)

    user_alloys = load_user_alloys(paths)
    with st.form("alloy_save_form", clear_on_submit=False):
        alloy_name = st.text_input(
            "Название марки или состава",
            placeholder="Например: Опытный Ni-сплав №1",
        )
        alloy_notes = st.text_area(
            "Заметка (не обязательно)",
            placeholder="Состояние поставки, источник состава, назначение…",
        )
        allow_overwrite = st.checkbox(
            "Разрешить обновить одноимённую пользовательскую запись"
        )
        save_alloy = st.form_submit_button(
            "Сохранить текущий состав",
            type="primary",
        )

    if save_alloy:
        try:
            saved = upsert_user_alloy(
                paths,
                alloy_name,
                alloy_notes,
                context,
                overwrite=allow_overwrite,
            )
            history_warning = record_history_nonfatal(
                paths,
                "alloy_saved",
                "Сохранена марка",
                context,
                {"name": saved["name"]},
            )
            flash("alloys", "success", f"Состав «{saved['name']}» сохранён.")
            if history_warning:
                flash(
                    "alloys",
                    "warning",
                    "Состав сохранён, но запись в историю не добавлена: "
                    f"{history_warning}",
                )
            st.rerun()
        except Exception as error:
            st.error(str(error))

    user_alloys = load_user_alloys(paths)
    all_alloys = DEMO_ALLOYS + user_alloys

    st.markdown("### Доступные записи")
    if not all_alloys:
        st.info("Сохранённых составов пока нет.")
        return

    st.dataframe(
        alloy_table(all_alloys, database_definitions),
        width="stretch",
        hide_index=True,
    )

    alloy_by_id = {item["id"]: item for item in all_alloys}
    selected_id = st.selectbox(
        "Выберите запись",
        options=list(alloy_by_id),
        format_func=lambda item_id: str(
            alloy_by_id[item_id].get("name", item_id)
        ),
        key="alloy_selected_id",
    )
    selected = alloy_by_id[selected_id]
    selected_database_available = (
        selected.get("database_key") in database_definitions
    )
    if not selected_database_available:
        st.warning(
            "В этой записи нет допустимого контекста базы; она остаётся "
            "данными библиотеки и не может запускать расчёт."
        )

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button(
            "Загрузить состав в программу",
            type="primary",
            key="alloy_load_button",
            disabled=not selected_database_available,
        ):
            try:
                selected_context = state_broker.rebind_context(
                    alloy_context(selected)
                )
                record_history(
                    paths,
                    "alloy_loaded",
                    "Загружена марка",
                    selected_context,
                    {"name": selected.get("name", str(selected_id))},
                )
                queue_context_load(
                    selected_context,
                    label=selected.get("name", "Сохранённый состав"),
                )
                st.rerun()
            except Exception as error:
                st.error(f"Состав не загружен: {error}")

    with action_col2:
        if selected.get("origin") == "user":
            confirm_delete = st.checkbox(
                f"Подтверждаю удаление «{selected.get('name', selected_id)}»",
                key=f"alloy_delete_confirm_{selected_id}",
            )
            if st.button(
                f"Удалить «{selected.get('name', selected_id)}»",
                disabled=not confirm_delete,
                key=f"alloy_delete_button_{selected_id}",
            ):
                delete_user_alloy(paths, selected_id)
                flash(
                    "alloys",
                    "success",
                    "Запись удалена; предыдущая версия файла библиотеки "
                    "сохранена как alloys.json.bak.",
                )
                st.rerun()
        else:
            st.caption("Учебные примеры не удаляются.")

    alloy_export_request = state_broker.state_decision(
        "data_alloy_state",
        {
            "direction": "egress",
            "content_kind": "alloy-library-json",
            "semantic_digest": semantic_digest_for(
                "alloy-library-json",
                user_alloys,
            ),
        },
    )
    if type(alloy_export_request) is FeatureRequest:
        alloy_export = state_store.prepare_egress(
            alloy_export_request,
            "alloy-library-json",
            user_alloys,
        )
        if type(alloy_export) is VerifiedArtifactRef:
            state_store.render_download(
                alloy_export,
                alloy_export.source_envelope_digest,
                "Скачать пользовательскую библиотеку",
                key="alloy_library_download",
            )
        else:
            show_rejection(alloy_export, "Библиотека не выгружена:")
    else:
        show_rejection(alloy_export_request, "Библиотека не выгружена:")

    alloy_import_request = state_broker.state_decision(
        "data_alloy_transfer",
        {"direction": "ingress", "content_kind": "alloy-library-json"},
    )
    imported_library = verified_state_uploader(
        alloy_import_request,
        "Импортировать библиотеку JSON",
        ALLOY_UI_TYPES,
        ALLOY_UPLOAD_KEY,
        lambda label, types, key: state_store.ingest_from_widget(
            alloy_import_request,
            "alloy-library-json",
            label,
            types,
            key,
        ),
    )
    if (
        type(imported_library) is not VerifiedArtifactRef
        and getattr(imported_library, "reason_code", "") != "USER_INPUT_REQUIRED"
    ):
        show_rejection(
            imported_library,
            "Файл библиотеки не принят:",
        )
        st.caption(
            "Импортировать можно только файл, выгруженный кнопкой "
            "«Скачать пользовательскую библиотеку»."
        )
    allow_import_overwrite = st.checkbox(
        "Разрешить заменить записи с совпадающим ID",
        key="alloy_import_overwrite",
        disabled=type(imported_library) is not VerifiedArtifactRef,
    )
    if type(imported_library) is VerifiedArtifactRef and st.button(
        "Импортировать выбранную библиотеку",
        key="alloy_import_button",
    ):
        try:
            imported = state_store.canonical_value(
                imported_library,
                imported_library.source_envelope_digest,
            )
            imported_count = merge_user_alloys(
                paths,
                imported,
                overwrite=allow_import_overwrite,
            )
            flash("alloys", "success", f"Импортировано записей: {imported_count}.")
            st.rerun()
        except Exception as error:
            st.error(f"Библиотеку импортировать не удалось: {error}")

# ---------------------------------------------------------------------------
# История с цепочкой контрольных сумм
# ---------------------------------------------------------------------------


def history_path(paths: ThermoGarPaths) -> Path:
    workspace_directory(paths)
    return paths.history_path


def record_history(
    paths: ThermoGarPaths,
    event_type: str,
    label: str,
    context: dict[str, Any],
    details: dict[str, Any] | None = None,
) -> None:
    path = history_path(paths)
    clean_context = validate_context_payload(context)

    def append_entry(existing_bytes: bytes) -> bytes:
        existing_entries, chain_ok = _parse_history_bytes(existing_bytes)
        if not chain_ok:
            raise RuntimeError(
                "Новая запись не добавлена: цепочка history.jsonl повреждена. "
                "Сначала сохраните повреждённый файл отдельно и начните новую историю."
            )
        previous_hash = (
            str(existing_entries[-1]["entry_sha256"])
            if existing_entries
            else ""
        )
        entry = {
            "timestamp": now_iso(),
            "app_stage": APP_STAGE,
            "app_version": APP_VERSION,
            "release_class": RELEASE_CLASS,
            "software_release_status": SOFTWARE_RELEASE_STATUS,
            "scientific_material_status": SCIENTIFIC_MATERIAL_STATUS,
            "production_use": PRODUCTION_USE,
            "event_type": event_type,
            "label": label,
            "database_key": clean_context.get("database_key"),
            "balance": clean_context.get("balance"),
            "units": clean_context.get("units"),
            "composition": clean_context.get("composition"),
            "pressure_pa": clean_context.get("pressure_pa"),
            "steel_mode": clean_context.get("steel_mode"),
            "database_sha256": clean_context.get("database_sha256", ""),
            "fe_profile_key": clean_context.get("fe_profile_key"),
            "details": details or {},
            "previous_sha256": previous_hash,
        }
        entry["entry_sha256"] = payload_sha256(entry)
        separator = b"" if not existing_bytes or existing_bytes.endswith(b"\n") else b"\n"
        encoded_entry = (json.dumps(entry, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
        return existing_bytes + separator + encoded_entry

    atomic_update_bytes(
        path,
        append_entry,
        canonical_root=_workspace_canonical_root(paths),
    )


def record_history_nonfatal(
    paths: ThermoGarPaths,
    event_type: str,
    label: str,
    context: dict[str, Any],
    details: dict[str, Any] | None = None,
) -> str | None:
    """Record provenance without turning a completed durable write into failure."""

    try:
        record_history(paths, event_type, label, context, details)
    except Exception as error:
        return f"{type(error).__name__}: {error}"
    return None


def record_calculation_history(
    paths: ThermoGarPaths,
    label: str,
    context: dict[str, Any],
    details: dict[str, Any] | None = None,
) -> None:
    record_history(
        paths,
        "calculation",
        label,
        context,
        details,
    )


def _parse_history_bytes(data: bytes) -> tuple[list[dict[str, Any]], bool]:
    entries: list[dict[str, Any]] = []
    chain_ok = True
    expected_previous = ""

    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return [], False
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            chain_ok = False
            continue

        if not isinstance(entry, dict):
            chain_ok = False
            continue

        entry_hash = entry.get("entry_sha256", "")
        if not isinstance(entry_hash, str) or not re.fullmatch(
            r"[0-9a-f]{64}", entry_hash
        ):
            chain_ok = False
            continue
        content = dict(entry)
        content.pop("entry_sha256", None)
        actual_hash = payload_sha256(content)
        if entry_hash != actual_hash:
            chain_ok = False
        if entry.get("previous_sha256", "") != expected_previous:
            chain_ok = False
        expected_previous = entry_hash
        entries.append(entry)

    if not chain_ok:
        # Never expose a partially trusted prefix for restore or export.
        return [], False
    return entries, True


def load_history(paths: ThermoGarPaths) -> tuple[list[dict[str, Any]], bool]:
    path = history_path(paths)
    try:
        path.lstat()
    except FileNotFoundError:
        return [], True
    snapshot = read_verified_snapshot(
        path,
        maximum_bytes=MAX_WORKSPACE_FILE_BYTES,
        canonical_root=_workspace_canonical_root(paths),
    )
    return _parse_history_bytes(snapshot.data)


def history_dataframe(entries: list[dict[str, Any]]) -> pd.DataFrame:
    database_labels = {
        "ni": "Никелевые сплавы",
        "fe": "Стали и Fe-сплавы",
        "al": "Алюминиевые сплавы",
        "mixed": "Несколько баз",
    }
    event_labels = {
        "calculation": "Расчёт",
        "batch_calculation": "Пакетный расчёт",
        "alloy_saved": "Сохранение состава",
        "alloy_loaded": "Загрузка состава",
        "project_saved": "Сохранение проекта",
        "project_loaded": "Открытие проекта",
    }
    rows = []
    for entry in reversed(entries):
        details = entry.get("details", {})
        event_type = str(entry.get("event_type", ""))
        database_key = str(entry.get("database_key", ""))
        rows.append(
            {
                "Время": entry.get("timestamp", ""),
                "Событие": entry.get("label", ""),
                "Тип": event_labels.get(event_type, event_type),
                "База": database_labels.get(database_key, database_key or "—"),
                "Основа": entry.get("balance", "") or "—",
                "Единицы": units_label(entry.get("units", "")),
                "Состав": entry.get("composition", ""),
                "Подробности": json.dumps(
                    details,
                    ensure_ascii=False,
                    separators=(", ", ": "),
                ),
                "База SHA-256": entry.get("database_sha256", ""),
                "Запись SHA-256": entry.get("entry_sha256", ""),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Проекты
# ---------------------------------------------------------------------------


def projects_directory(paths: ThermoGarPaths) -> Path:
    workspace_directory(paths)
    return paths.projects_root


def build_project_payload(
    name: str,
    description: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "schema_version": STORAGE_SCHEMA_VERSION,
        "kind": "thermogar_project_payload",
        "name": name.strip(),
        "description": description.strip(),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "app_stage": APP_STAGE,
        "app_version": APP_VERSION,
        "release_class": RELEASE_CLASS,
        "software_release_status": SOFTWARE_RELEASE_STATUS,
        "scientific_material_status": SCIENTIFIC_MATERIAL_STATUS,
        "production_use": PRODUCTION_USE,
        "context": validate_context_payload(context),
        "widget_state": capture_widget_state(),
    }
    return validate_project_payload(payload)


def project_file_path(paths: ThermoGarPaths, project_name: str) -> Path:
    return projects_directory(paths) / (
        safe_slug(project_name, "ThermoGar_project") + ".thermogar.json"
    )


def save_project_local(
    paths: ThermoGarPaths,
    payload: dict[str, Any],
    *,
    overwrite: bool = False,
) -> Path:
    clean_payload = validate_project_payload(payload)
    envelope = make_envelope("thermogar_project", clean_payload)
    path = project_file_path(paths, clean_payload["name"])
    try:
        atomic_write_json(
            paths,
            path,
            envelope,
            create_backup=overwrite,
            overwrite=overwrite,
        )
    except FileExistsError as error:
        raise FileExistsError(
            "Проект с таким названием уже существует. "
            "Разрешите замену либо задайте другое название."
        ) from error
    return path

def scan_projects(
    paths: ThermoGarPaths,
) -> tuple[list[tuple[Path, dict[str, Any], bytes]], list[str]]:
    result: list[tuple[Path, dict[str, Any], bytes]] = []
    errors: list[str] = []
    for path in sorted(projects_directory(paths).glob("*.thermogar.json")):
        try:
            with held_verified_snapshot(
                path,
                maximum_bytes=MAX_WORKSPACE_FILE_BYTES,
                canonical_root=_workspace_canonical_root(paths),
            ) as snapshot:
                envelope = json.loads(snapshot.data.decode("utf-8-sig"))
                payload = validate_envelope(envelope, "thermogar_project")
                result.append(
                    (path, validate_project_payload(payload), snapshot.data)
                )
        except Exception as error:
            errors.append(f"{path.name}: {type(error).__name__}: {error}")
    return result, errors


def portable_project_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Копия проекта для переноса на другой компьютер.

    Настройки расчётных разделов в переносимый файл не попадают: их набор
    привязан к версии интерфейса, а материал — нет.
    """

    portable = dict(payload)
    portable["widget_state"] = {}
    return portable


def list_projects(paths: ThermoGarPaths) -> list[tuple[Path, dict[str, Any]]]:
    """Return only projects that pass the complete current schema."""

    return [
        (path, payload)
        for path, payload, _snapshot_bytes in scan_projects(paths)[0]
    ]


def render_projects_and_history(
    paths: ThermoGarPaths,
    context: dict[str, Any],
    database_definitions: dict[str, dict[str, Any]],
    state_store: StateStore,
    state_broker: VerifiedBatchBroker,
) -> None:
    st.subheader("Проекты и история")
    st.caption(
        "Проект сохраняет материал и числовые настройки расчётных разделов. "
        "История хранит отпечаток базы и цепочку контрольных сумм."
    )
    render_flash("projects")

    view_mode = st.radio(
        "Что открыть",
        ["Проекты", "История расчётов"],
        horizontal=True,
        key="projects_history_mode",
    )

    if view_mode == "Проекты":
        with st.form("project_save_form"):
            project_name = st.text_input(
                "Название проекта",
                placeholder="Например: Исследовательское сравнение Ni-сценариев",
            )
            project_description = st.text_area(
                "Описание (не обязательно)",
                placeholder="Цель расчётов, состояние материала, источник состава…",
            )
            allow_overwrite = st.checkbox(
                "Разрешить заменить одноимённый локальный проект"
            )
            save_project = st.form_submit_button(
                "Сохранить проект в папке ThermoGar",
                type="primary",
            )

        if save_project:
            try:
                payload = build_project_payload(
                    project_name,
                    project_description,
                    context,
                )
                path = save_project_local(
                    paths,
                    payload,
                    overwrite=allow_overwrite,
                )
                history_warning = record_history_nonfatal(
                    paths,
                    "project_saved",
                    "Сохранён проект",
                    context,
                    {"name": payload["name"], "path": str(path)},
                )
                flash("projects", "success", f"Проект сохранён: {path.name}")
                if history_warning:
                    flash(
                        "projects",
                        "warning",
                        "Проект сохранён, но запись в историю не добавлена: "
                        f"{history_warning}",
                    )
                st.rerun()
            except Exception as error:
                st.error(str(error))

        projects, project_errors = scan_projects(paths)
        if project_errors:
            st.error(
                "Некоторые локальные проекты отклонены без применения: "
                + " | ".join(project_errors)
            )
        if not projects:
            st.info("Сохранённых проектов пока нет.")
        else:
            table = pd.DataFrame(
                [
                    {
                        "Проект": payload.get("name", path.stem),
                        "Описание": payload.get("description", ""),
                        "База": database_definitions.get(
                            payload.get("context", {}).get("database_key", ""),
                            {},
                        ).get("label", ""),
                        "Состав": payload.get("context", {}).get(
                            "composition",
                            "",
                        ),
                        "Изменён": payload.get("updated_at", ""),
                        "Файл": path.name,
                    }
                    for path, payload, _snapshot_bytes in projects
                ]
            )
            st.dataframe(table, width="stretch", hide_index=True)

            project_map = {
                str(path): (path, payload, snapshot_bytes)
                for path, payload, snapshot_bytes in projects
            }
            selected_path_string = st.selectbox(
                "Выберите проект",
                options=list(project_map),
                format_func=lambda value: project_map[value][1].get(
                    "name",
                    Path(value).stem,
                ),
                key="project_selected_path",
            )
            selected_path, selected_payload, selected_snapshot_bytes = project_map[
                selected_path_string
            ]

            col1, col2 = st.columns(2)
            with col1:
                if st.button(
                    "Открыть проект",
                    type="primary",
                    key="project_load_button",
                ):
                    try:
                        selected_context = state_broker.rebind_context(
                            validate_context_payload(
                                selected_payload.get("context")
                            )
                        )
                        record_history(
                            paths,
                            "project_loaded",
                            "Открыт проект",
                            selected_context,
                            {"name": selected_payload.get("name", "")},
                        )
                        queue_context_load(
                            selected_context,
                            selected_payload.get("widget_state"),
                            label=selected_payload.get("name", "Проект"),
                        )
                        st.rerun()
                    except Exception as error:
                        st.error(f"Проект не открыт: {error}")

                portable_payload = portable_project_payload(selected_payload)
                project_export_request = state_broker.state_decision(
                    "data_project_state",
                    {
                        "direction": "egress",
                        "content_kind": "project-json",
                        "semantic_digest": semantic_digest_for(
                            "project-json",
                            portable_payload,
                        ),
                    },
                )
                if type(project_export_request) is FeatureRequest:
                    project_export = state_store.prepare_egress(
                        project_export_request,
                        "project-json",
                        portable_payload,
                    )
                    if type(project_export) is VerifiedArtifactRef:
                        state_store.render_download(
                            project_export,
                            project_export.source_envelope_digest,
                            "Скачать выбранный проект",
                            key="project_download",
                        )
                        if selected_payload.get("widget_state"):
                            st.caption(
                                "В переносимый файл попадает материал; "
                                "числовые настройки разделов остаются "
                                "в локальном проекте."
                            )
                    else:
                        show_rejection(project_export, "Проект не выгружен:")
                else:
                    show_rejection(
                        project_export_request,
                        "Проект не выгружен:",
                    )

            with col2:
                confirm_delete = st.checkbox(
                    f"Подтверждаю удаление «{selected_payload.get('name', '')}»",
                    key="project_delete_confirm",
                )
                if st.button(
                    f"Удалить «{selected_payload.get('name', 'проект')}»",
                    disabled=not confirm_delete,
                    key="project_delete_button",
                ):
                    deleted_path = selected_path.with_suffix(
                        selected_path.suffix + ".deleted"
                    )
                    try:
                        secure_move_no_overwrite(
                            selected_path,
                            deleted_path,
                            canonical_root=_workspace_canonical_root(
                                paths
                            ),
                        )
                        flash(
                            "projects",
                            "success",
                            "Проект убран из списка; исходный файл сохранён "
                            "с окончанием .deleted.",
                        )
                        st.rerun()
                    except Exception as error:
                        st.error(f"Проект не удалён: {error}")

        project_import_request = state_broker.state_decision(
            "data_project_transfer",
            {"direction": "ingress", "content_kind": "project-json"},
        )
        uploaded_project = verified_state_uploader(
            project_import_request,
            "Импортировать проект",
            PROJECT_UI_TYPES,
            PROJECT_UPLOAD_KEY,
            lambda label, types, key: state_store.ingest_from_widget(
                project_import_request,
                "project-json",
                label,
                types,
                key,
            ),
        )
        if (
            type(uploaded_project) is not VerifiedArtifactRef
            and getattr(uploaded_project, "reason_code", "")
            != "USER_INPUT_REQUIRED"
        ):
            show_rejection(uploaded_project, "Файл проекта не принят:")
            st.caption(
                "Импортировать можно только файл, выгруженный кнопкой "
                "«Скачать выбранный проект» этой же версии ThermoGar."
            )
        import_overwrite = st.checkbox(
            "Разрешить заменить одноимённый локальный проект",
            key="project_import_overwrite",
            disabled=type(uploaded_project) is not VerifiedArtifactRef,
        )
        if type(uploaded_project) is VerifiedArtifactRef and st.button(
            "Импортировать выбранный проект",
            key="project_import_button",
        ):
            try:
                payload = validate_project_payload(
                    state_store.canonical_value(
                        uploaded_project,
                        uploaded_project.source_envelope_digest,
                    )
                )
                state_store.restore_context(
                    uploaded_project,
                    uploaded_project.source_envelope_digest,
                    state_broker.rebind_context,
                )
                imported_path = save_project_local(
                    paths,
                    payload,
                    overwrite=import_overwrite,
                )
                flash("projects", "success", f"Проект импортирован: {imported_path.name}")
                st.rerun()
            except Exception as error:
                st.error(f"Проект импортировать не удалось: {error}")

    else:
        entries, chain_ok = load_history(paths)
        if chain_ok:
            st.success("Цепочка контрольных сумм истории совпала.")
        else:
            st.error(
                "Цепочка истории повреждена или редактировалась вручную. "
                "Сами расчёты это не меняет, но родословную следует считать "
                "неподтверждённой."
            )

        history_df = history_dataframe(entries)
        if history_df.empty:
            st.info(
                "История пока пуста."
                if chain_ok
                else "Повреждённые записи не показаны и не доступны для восстановления."
            )
        else:
            event_options = sorted(history_df["Событие"].dropna().unique())
            selected_events = st.multiselect(
                "Показывать события",
                event_options,
                default=event_options,
            )
            filtered = history_df[
                history_df["Событие"].isin(selected_events)
            ].head(250)
            st.dataframe(filtered, width="stretch", hide_index=True)

            restorable_entries: list[tuple[int, dict[str, Any]]] = []
            for index, entry in enumerate(entries):
                try:
                    restorable_entries.append(
                        (index, context_from_history_entry(entry))
                    )
                except Exception:
                    continue
            restore_col, download_col = st.columns(2)
            with restore_col:
                if not restorable_entries:
                    st.info(
                        "В истории нет записей, из которых можно восстановить "
                        "материал."
                    )
                else:
                    context_by_index = dict(restorable_entries)
                    entry_options = sorted(context_by_index, reverse=True)
                    selected_entry_index = st.selectbox(
                        "Запись для восстановления материала",
                        options=entry_options,
                        format_func=lambda index: (
                            f"{entries[index].get('timestamp', '')} · "
                            f"{entries[index].get('label', '')} · "
                            f"{entries[index].get('composition', '')}"
                        ),
                        key="history_restore_entry",
                    )
                    selected_entry = entries[selected_entry_index]
                    if st.button(
                        "Восстановить материал из записи",
                        type="primary",
                        key="history_restore_button",
                    ):
                        try:
                            queue_context_load(
                                state_broker.rebind_context(
                                    context_by_index[selected_entry_index]
                                ),
                                label=selected_entry.get("label", "История"),
                            )
                            st.rerun()
                        except Exception as error:
                            st.error(f"Запись истории не восстановлена: {error}")
            with download_col:
                history_rows = [
                    {
                        header: str(row.get(header, ""))
                        for header in HISTORY_HEADERS
                    }
                    for row in history_df.to_dict(orient="records")
                ]
                history_request = state_broker.state_decision(
                    "data_history_export",
                    {
                        "direction": "egress",
                        "content_kind": "history-csv",
                        "semantic_digest": semantic_digest_for(
                            "history-csv",
                            history_rows,
                        ),
                    },
                )
                if type(history_request) is FeatureRequest:
                    history_export = state_store.prepare_egress(
                        history_request,
                        "history-csv",
                        history_rows,
                    )
                    if type(history_export) is VerifiedArtifactRef:
                        state_store.render_download(
                            history_export,
                            history_export.source_envelope_digest,
                            "Скачать историю CSV",
                            key="history_download",
                        )
                    else:
                        show_rejection(history_export, "История не выгружена:")
                else:
                    show_rejection(history_request, "История не выгружена:")

            confirm_clear = st.checkbox(
                "Подтверждаю очистку всей истории",
                key="history_clear_confirm",
            )
            if st.button(
                "Очистить всю историю",
                disabled=not confirm_clear,
                key="history_clear_button",
            ):
                source = history_path(paths)
                backup = source.with_name(
                    "history_"
                    + datetime.now().strftime("%Y%m%d_%H%M%S")
                    + ".jsonl.bak"
                )
                try:
                    archived = secure_archive_and_clear(
                        source,
                        backup,
                        canonical_root=_workspace_canonical_root(paths),
                        missing_ok=True,
                    )
                    flash(
                        "projects",
                        "success",
                        "История очищена; резервная копия сохранена."
                        if archived
                        else "История уже пуста.",
                    )
                    st.rerun()
                except Exception as error:
                    st.error(f"История не очищена: {error}")

# ---------------------------------------------------------------------------
# Пакетный расчёт
# ---------------------------------------------------------------------------



BATCH_COLUMN_ALIASES: dict[str, str] = dict(BATCH_ALIAS_PAIRS)


def canonicalize_batch_columns(source: pd.DataFrame) -> pd.DataFrame:
    result = source.copy()
    rename_map: dict[Any, str] = {}
    existing_lower = {str(column).strip().lower(): str(column) for column in result.columns}
    for alias, canonical in BATCH_COLUMN_ALIASES.items():
        column = existing_lower.get(alias.lower())
        if column is not None and canonical not in result.columns:
            rename_map[column] = canonical
    return result.rename(columns=rename_map)


def batch_table_dataframe(value: Mapping[str, object]) -> pd.DataFrame:
    """Build display scalars from the StateStore's canonical table value."""

    if type(value) is not dict or set(value) != {"columns", "rows"}:
        raise ValueError("Каноническая пакетная таблица повреждена.")
    columns = value["columns"]
    rows = value["rows"]
    if type(columns) is not list or type(rows) is not list:
        raise ValueError("Каноническая пакетная таблица повреждена.")
    return canonicalize_batch_columns(pd.DataFrame(rows, columns=columns))


def dataframe_state_value(source: pd.DataFrame) -> dict[str, object]:
    """Reduce a display frame to canonical scalar columns and rows.

    Пропуски приводятся к ``None`` поштучно. ``DataFrame.where(..., None)``
    для этого не годится: в столбце с плавающей точкой ``None`` хранить
    нельзя, и пропуск возвращается как ``NaN``. Пропуски здесь обычные —
    таблицы составов фаз объединяют строки с разными наборами элементов,
    а несериализуемое значение отклоняется на границе выгрузки.
    """

    rows: list[list[object]] = []
    for values in source.itertuples(index=False, name=None):
        row: list[object] = []
        for value in values:
            if isinstance(value, np.generic):
                value = value.item()
            if isinstance(value, (datetime, pd.Timestamp)):
                value = value.isoformat()
            elif value is not None and not isinstance(value, (str, bytes)):
                try:
                    missing = bool(pd.isna(value))
                except (TypeError, ValueError):
                    missing = False
                if missing or (
                    isinstance(value, float) and not math.isfinite(value)
                ):
                    value = None
            row.append(value)
        rows.append(row)
    return {
        "columns": [str(column) for column in source.columns],
        "rows": rows,
    }

def normalize_database_key(value: Any) -> str:
    text = str(value).strip().lower()
    if text not in {"ni", "al", "fe"}:
        raise ValueError(f"Неизвестная база: {value!r}. Используйте ni, al или fe.")
    return text


def normalize_units(value: Any) -> str:
    normalized = str(value).strip().lower().replace(" ", "").replace(".", "")
    if normalized in {
        "at",
        "at%",
        "ат%",
        "атомные%",
        "атомные",
        "atomic",
    }:
        return "at"
    if normalized in {
        "wt",
        "wt%",
        "мас%",
        "массовые%",
        "массовые",
        "mass",
    }:
        return "wt"
    raise ValueError(f"Неизвестные единицы состава: {value!r}.")

def normalize_steel_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if any(token in normalized for token in ("стаб", "граф", "stable", "graphite")):
        return "stable"
    return "metastable"

def composition_from_row(
    row: pd.Series,
    balance: str,
) -> tuple[str, dict[str, float]]:
    composition_value = row.get("composition", "")
    if pd.notna(composition_value) and str(composition_value).strip():
        entered: dict[str, float] = {}
        for match in re.finditer(
            r"([A-Za-z][A-Za-z0-9]{0,2})\s*=\s*([+-]?\d+(?:[.,]\d+)?)",
            str(composition_value).strip(),
        ):
            element = match.group(1).upper()
            value = float(match.group(2).replace(",", "."))
            if element in entered:
                raise ValueError(f"Элемент {element} указан повторно.")
            entered[element] = value
        if not entered:
            raise ValueError("Строка «Добавки» не содержит пар ЭЛЕМЕНТ=ЧИСЛО.")
        entered.pop(balance, None)
        text = ", ".join(
            f"{element}={value:g}"
            for element, value in entered.items()
        )
        return text, entered

    entered: dict[str, float] = {}
    reserved = {
        "NAME", "DATABASE", "BALANCE", "UNITS", "TEMPERATURE_C",
        "PRESSURE_PA", "COMPOSITION", "PHASES", "STEEL_MODE",
    }
    for column in row.index:
        element = str(column).strip().upper()
        if (
            element in reserved
            or element == balance
            or re.fullmatch(r"[A-Z][A-Z0-9]{0,2}", element) is None
        ):
            continue
        value = row.get(column)
        if pd.notna(value):
            entered[element] = float(value)

    if not entered:
        raise ValueError(
            "Не задана колонка «Добавки» и не найдены числовые столбцы элементов."
        )

    text = ", ".join(f"{element}={value:g}" for element, value in entered.items())
    return text, entered

class VerifiedBatchBroker(Protocol):
    """Narrow path-free broker owned by the app's verified B3 boundary."""

    def import_decision(self) -> FeatureRequest | RejectedFeatureReceipt: ...

    def execute_decision(
        self,
        *,
        row_count: int,
        source_digest: str,
    ) -> FeatureRequest | RejectedFeatureReceipt: ...

    def export_decision(self) -> FeatureRequest | RejectedFeatureReceipt: ...

    def state_decision(
        self,
        feature_id: str,
        inputs: Mapping[str, object],
        requested_phases: tuple[str, ...] = (),
    ) -> FeatureRequest | RejectedFeatureReceipt: ...

    def rebind_context(
        self,
        context: dict[str, object],
    ) -> dict[str, object]: ...

    def execute_row(self, row: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def finish(self, children: tuple[Mapping[str, object], ...]) -> Mapping[str, str]: ...


def batch_source_digest(source: pd.DataFrame) -> str:
    canonical = canonicalize_batch_columns(source).to_csv(
        index=False,
        lineterminator="\n",
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_batch_calculations(
    source: pd.DataFrame,
    broker: VerifiedBatchBroker,
    phase_explanations: dict[str, dict[str, str]],
) -> dict[str, Any]:
    source = canonicalize_batch_columns(source)
    if source.empty:
        raise ValueError("Таблица пуста.")
    if len(source) > 100:
        raise ValueError(
            "В одном запуске допускается не более 100 составов. "
            "Разделите файл на несколько частей."
        )

    required = {"name", "database", "balance", "units", "temperature_C"}
    missing = sorted(required - set(source.columns))
    if missing:
        raise ValueError("Не хватает столбцов: " + ", ".join(missing))

    summary_rows: list[dict[str, Any]] = []
    phase_rows: list[dict[str, Any]] = []
    phase_at_rows: list[dict[str, Any]] = []
    phase_wt_rows: list[dict[str, Any]] = []
    child_evidence: list[Mapping[str, object]] = []
    progress = st.progress(0.0, text="Подготовка пакетного расчёта…")

    for position, (_, row) in enumerate(source.iterrows(), start=1):
        name = str(row.get("name", f"Строка {position}")).strip() or f"Строка {position}"
        base_summary: dict[str, Any] = {
            "№": position,
            "Название": name,
            "Статус": "ошибка",
            "Ошибка": "",
        }

        try:
            database_key = normalize_database_key(row["database"])
            balance = str(row["balance"]).strip().upper()
            units = normalize_units(row["units"])
            temperature_c = float(row["temperature_C"])
            pressure_value = row.get("pressure_Pa", 101325.0)
            pressure_pa = 101325.0 if pd.isna(pressure_value) else float(pressure_value)
            steel_mode = normalize_steel_mode(row.get("steel_mode", "metastable"))
            composition_text, entered = composition_from_row(row, balance)

            requested_phases: tuple[str, ...] = ()
            phase_value = row.get("phases", "")
            if pd.notna(phase_value) and str(phase_value).strip():
                excluded = EXCLUDED_PHASES.get(database_key, ())
                requested_phases = tuple(
                    item.strip().upper()
                    for item in re.split(r"[,;]", str(phase_value))
                    if item.strip() and item.strip().upper() not in excluded
                )

            child = broker.execute_row(
                {
                    "balance": balance,
                    "composition_pct": dict(sorted(entered.items())),
                    "database_key": database_key,
                    "pressure_pa": pressure_pa,
                    "profile_key": "thermogar_patch" if database_key == "fe" else None,
                    "requested_phases": list(requested_phases),
                    "row_index": position,
                    "steel_mode": steel_mode,
                    "temperature_k": temperature_c + 273.15,
                    "units": units,
                }
            )
            if type(child) is not dict:
                raise RuntimeError("Verified broker returned a non-canonical row result.")
            status = child.get("status")
            feature_receipt = child.get("feature_receipt")
            result_envelope = child.get("result_envelope")
            rejection = child.get("rejection")
            if status == "rejected":
                if type(rejection) is not RejectedFeatureReceipt or rejection.backend_calls != 0:
                    raise RuntimeError("Verified broker rejection evidence is invalid.")
                child_evidence.append({"rejection": rejection})
                raise RuntimeError(rejection_text(rejection))
            if (
                status != "success"
                or type(feature_receipt) is not FeatureReceipt
                or type(result_envelope) is not ResultEnvelope
                or feature_receipt.outcome != "success"
            ):
                raise RuntimeError(str(child.get("error") or "Verified broker execution failed."))
            phase_fractions = child.get("phase_fractions")
            phase_at = child.get("phase_atomic")
            phase_wt = child.get("phase_mass")
            if type(phase_fractions) is not list or type(phase_at) is not list or type(phase_wt) is not list:
                raise RuntimeError("Verified broker scalar result is invalid.")
            child_evidence.append(
                {
                    "feature_receipt": feature_receipt,
                    "result_envelope": result_envelope,
                }
            )
            fraction_sum = sum(float(item[1]) * 100.0 for item in phase_fractions)
            phase_text = "; ".join(
                f"{item[0]}={float(item[1]) * 100.0:.6g}%"
                for item in phase_fractions
            )
            phase_names = [str(item[0]) for item in phase_fractions]

            base_summary.update(
                {
                    "Статус": "готово",
                    "База": database_key,
                    "Основа": balance,
                    "Единицы": units,
                    "Температура, °C": temperature_c,
                    "Давление, Па": pressure_pa,
                    "Состав": composition_text,
                    "Фазовое поле": " + ".join(phase_names),
                    "Фазовые доли": phase_text,
                    "Сумма фазовых долей, %": fraction_sum,
                    "База SHA-256": feature_receipt.tdb_evidence.sha256,
                }
            )

            for phase, fraction in phase_fractions:
                phase_rows.append(
                    {
                        "Название": name,
                        "База": database_key,
                        "Температура, °C": temperature_c,
                        "Фаза": phase,
                        "Что это": phase_explanations.get(database_key, {}).get(
                            phase,
                            "",
                        ),
                        "Мольная доля фазы, %": float(fraction) * 100.0,
                    }
                )

            for item in phase_at:
                current = dict(item)
                current.update({"Название": name, "База": database_key})
                phase_at_rows.append(current)

            for item in phase_wt:
                current = dict(item)
                current.update({"Название": name, "База": database_key})
                phase_wt_rows.append(current)

        except Exception as error:
            base_summary["Ошибка"] = str(error)

        summary_rows.append(base_summary)
        progress.progress(
            position / len(source),
            text=f"Состав {position} из {len(source)}",
        )

    progress.empty()
    result: dict[str, Any] = {
        "Сводка": pd.DataFrame(summary_rows),
        "Фазовые доли": pd.DataFrame(phase_rows),
        "Составы фаз ат": pd.DataFrame(phase_at_rows),
        "Составы фаз мас": pd.DataFrame(phase_wt_rows),
        "Исходные данные": source.copy(),
    }
    aggregate = broker.finish(tuple(child_evidence))
    if type(aggregate) is not dict or set(aggregate) != {"receipt_digest", "envelope_digest"}:
        raise RuntimeError("Verified broker aggregate evidence is invalid.")
    result["_receipt_digest"] = aggregate["receipt_digest"]
    result["_envelope_digest"] = aggregate["envelope_digest"]
    result["_children"] = [
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
        for item in child_evidence
    ]
    return result


def render_batch_calculation(
    broker: VerifiedBatchBroker,
    phase_explanations: dict[str, dict[str, str]],
    state_store: StateStore,
) -> None:
    st.subheader("Пакетный расчёт составов")
    st.caption(
        "Загрузите Excel или CSV: одна строка — один состав при одной "
        "температуре. Ошибка в одной строке не останавливает остальные."
    )

    template_col1, template_col2 = st.columns(2)
    with template_col1:
        template_xlsx_decision = broker.export_decision()
        if verified_batch_export_button(
            template_xlsx_decision,
            "Скачать шаблон Excel",
            key="batch_template_xlsx_prepare",
        ) and type(template_xlsx_decision) is FeatureRequest:
            template_xlsx = state_store.prepare_egress(
                template_xlsx_decision,
                "batch-template-xlsx",
                batch_template_value(),
            )
            if type(template_xlsx) is VerifiedArtifactRef:
                state_store.render_download(
                    template_xlsx,
                    template_xlsx.source_envelope_digest,
                    "Скачать подготовленный XLSX",
                    key="batch_template_xlsx_download",
                )
            else:
                show_rejection(template_xlsx, "Шаблон не подготовлен:")
    with template_col2:
        template_csv_decision = broker.export_decision()
        if verified_batch_export_button(
            template_csv_decision,
            "Скачать шаблон CSV",
            key="batch_template_csv_prepare",
        ) and type(template_csv_decision) is FeatureRequest:
            template_csv = state_store.prepare_egress(
                template_csv_decision,
                "batch-template-csv",
                batch_template_value(),
            )
            if type(template_csv) is VerifiedArtifactRef:
                state_store.render_download(
                    template_csv,
                    template_csv.source_envelope_digest,
                    "Скачать подготовленный CSV",
                    key="batch_template_csv_download",
                )
            else:
                show_rejection(template_csv, "Шаблон не подготовлен:")

    with st.expander("Требуемые столбцы", expanded=False):
        st.markdown(
            "- **Название** — имя расчёта;  \n"
            "- **База** — только `ni`, `al` или `fe`;  \n"
            "- **Основа** — элемент, заполняющий остаток до 100 %;  \n"
            "- **Единицы** — `ат.%` или `мас.%`;  \n"
            "- **Температура, °C** — обязательна;  \n"
            "- **Добавки** — строка вида `CR=18, NI=8, C=0,1`.  \n"
            "Необязательно: давление, режим стали и список фаз. Вместо "
            "«Добавки» можно использовать отдельные столбцы `C`, `CR`, `NI`."
        )

    batch_import_decision = broker.import_decision()
    uploaded = verified_state_uploader(
        batch_import_decision,
        "Файл составов",
        BATCH_UI_TYPES,
        BATCH_UPLOAD_KEY,
        lambda label, types, key: state_store.ingest_from_widget(
            batch_import_decision,
            "batch-input-csv",
            label,
            types,
            key,
        ),
    )

    if (
        type(uploaded) is not VerifiedArtifactRef
        and getattr(uploaded, "reason_code", "") != "USER_INPUT_REQUIRED"
    ):
        show_rejection(uploaded, "Файл составов не принят:")
        st.caption(
            "Скачайте шаблон выше и заполните его, не меняя названий "
            "столбцов. Разделитель CSV — запятая или точка с запятой, "
            "кодировка — UTF-8."
        )

    if type(uploaded) is VerifiedArtifactRef:
        try:
            source = batch_table_dataframe(
                state_store.canonical_value(
                    uploaded,
                    uploaded.source_envelope_digest,
                )
            )
            st.markdown("### Предварительный просмотр")
            st.dataframe(source.head(25), width="stretch", hide_index=True)
            st.caption(f"Строк в файле: {len(source)}. Максимум за один запуск: 100.")

            decision = broker.execute_decision(
                row_count=len(source),
                source_digest=batch_source_digest(source),
            )
            if verified_batch_execute_button(
                decision,
                "Рассчитать все составы",
                type="primary",
                key="batch_calculate_button",
            ):
                result = run_batch_calculations(
                    source,
                    broker,
                    phase_explanations,
                )
                st.session_state["workspace_batch_result"] = {
                    "display": {
                        key: value
                        for key, value in result.items()
                        if not key.startswith("_")
                    },
                    "receipt_digest": result["_receipt_digest"],
                    "envelope_digest": result["_envelope_digest"],
                    "children": result["_children"],
                }
        except Exception as error:
            st.error(f"Файл прочитать или рассчитать не удалось: {error}")

    stored = st.session_state.get("workspace_batch_result")
    if isinstance(stored, dict) and isinstance(stored.get("display"), dict):
        result = stored["display"]
        summary = result["Сводка"]
        completed = int((summary["Статус"] == "готово").sum())
        failed = len(summary) - completed
        if failed:
            st.warning(f"Готово: {completed}. Ошибок: {failed}.")
        else:
            st.success(f"Все составы рассчитаны: {completed}.")

        st.dataframe(summary, width="stretch", hide_index=True)
        if failed:
            with st.expander("Строки с ошибками", expanded=True):
                st.dataframe(
                    summary[summary["Статус"] != "готово"],
                    width="stretch",
                    hide_index=True,
                )

        batch_export_decision = broker.export_decision()
        if verified_batch_export_button(
            batch_export_decision,
            "Скачать пакетный результат Excel",
            key="batch_result_export_prepare",
        ) and type(batch_export_decision) is FeatureRequest:
            result_value = batch_result_value(
                {
                    name: dataframe_state_value(result[name])
                    for name in (
                        "Сводка",
                        "Фазовые доли",
                        "Составы фаз ат",
                        "Составы фаз мас",
                        "Исходные данные",
                    )
                }
            )
            batch_export = state_store.prepare_egress(
                batch_export_decision,
                "batch-result-xlsx",
                result_value,
            )
            if type(batch_export) is VerifiedArtifactRef:
                state_store.render_download(
                    batch_export,
                    batch_export.source_envelope_digest,
                    "Скачать подготовленный результат XLSX",
                    key="batch_result_export_download",
                )
            else:
                show_rejection(batch_export, "Результат не выгружен:")
