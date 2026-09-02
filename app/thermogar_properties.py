"""ThermoGar elastic homogenization and transparent strengthening equations.

The module deliberately separates two kinds of answers:

* elastic homogenization — a reproducible Voigt/Reuss/Hill calculation that
  requires complete phase volume fractions and user-supplied intrinsic phase
  properties;
* strengthening contributions — transparent mechanism equations fed by
  explicit microstructure inputs. This is not an automatic prediction of UTS,
  yield strength, hardness or elongation from composition alone.

No elastic constants or strengthening coefficients are invented. The local
phase-property library stores only values entered/imported by the user together
with provenance and a reference temperature.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import json
import math
import re
from types import MappingProxyType
from typing import Any, Callable, Mapping

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from pycalphad import equilibrium, variables as v

from thermogar_palette import chart_roles
from thermogar_physical import calculate_physical_properties
from thermogar_release_ui import (
    release_calculation_button,
    release_download_button,
)
from thermogar_paths import ThermoGarPaths
from thermogar_secure_io import (
    atomic_update_bytes,
    atomic_write_bytes,
    ensure_plain_directory,
    read_verified_snapshot,
)


ELASTIC_LIBRARY_SCHEMA_VERSION = 1
ELASTIC_RESULT_SCHEMA_VERSION = 1
MAX_ELASTIC_LIBRARY_BYTES = 8 * 1024 * 1024


PROPERTY_CALCULATION_REASON_CODES: Mapping[str, str] = MappingProxyType(
    {
        "ELASTIC_INPUT_INVALID": (
            "Elastic input is missing, malformed, or outside its physical domain."
        ),
        "ELASTIC_NONFINITE_INPUT": (
            "Elastic input contains NaN or infinity."
        ),
        "ELASTIC_NONFINITE_OUTPUT": (
            "Elastic arithmetic produced a non-finite or numerically collapsed result."
        ),
        "STRENGTHENING_PROVENANCE_REQUIRED": (
            "Strengthening coefficients require declared provenance and scope."
        ),
        "STRENGTHENING_CONFIRMATION_REQUIRED": (
            "The research-only strengthening boundary must be confirmed."
        ),
        "STRENGTHENING_INPUT_INVALID": (
            "Strengthening input is missing, malformed, or outside its physical domain."
        ),
        "STRENGTHENING_NONFINITE_INPUT": (
            "Strengthening input contains NaN or infinity."
        ),
        "STRENGTHENING_NONFINITE_OUTPUT": (
            "Strengthening arithmetic produced a non-finite or numerically collapsed result."
        ),
        "STRENGTHENING_RULE_INVALID": (
            "The requested strengthening summation rule is unsupported."
        ),
    }
)
STRENGTHENING_SUMMATION_RULES = (
    "Не суммировать",
    "Линейная сумма",
    "Квадратичное объединение вкладов",
)


class PropertyCalculationError(ValueError):
    """Fail-closed numerical error with a stable machine-readable reason."""

    def __init__(self, reason_code: str, message: str) -> None:
        if reason_code not in PROPERTY_CALCULATION_REASON_CODES:
            raise RuntimeError(f"Unknown property reason code: {reason_code}")
        self.reason_code = reason_code
        super().__init__(message)


def _property_fail(reason_code: str, message: str) -> None:
    raise PropertyCalculationError(reason_code, message)


def _finite_input_number(
    value: Any,
    *,
    invalid_reason: str,
    nonfinite_reason: str,
    label: str,
) -> float:
    if isinstance(value, (bool, np.bool_)):
        _property_fail(
            invalid_reason,
            f"{label}: логическое значение не является числовым входом.",
        )
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise PropertyCalculationError(
            invalid_reason,
            f"{label}: требуется число, представимое в binary64.",
        ) from error
    if not math.isfinite(number):
        _property_fail(nonfinite_reason, f"{label}: NaN и бесконечность запрещены.")
    if number == 0.0:
        return 0.0
    return number


def _finite_output_number(value: float, *, reason: str, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise PropertyCalculationError(
            reason,
            f"{label}: результат не представим в binary64.",
        ) from error
    if not math.isfinite(number):
        _property_fail(reason, f"{label}: получен NaN или бесконечность.")
    if number == 0.0:
        return 0.0
    return number


def _elastic_input(value: Any, label: str) -> float:
    return _finite_input_number(
        value,
        invalid_reason="ELASTIC_INPUT_INVALID",
        nonfinite_reason="ELASTIC_NONFINITE_INPUT",
        label=label,
    )


def _strengthening_input(value: Any, label: str) -> float:
    return _finite_input_number(
        value,
        invalid_reason="STRENGTHENING_INPUT_INVALID",
        nonfinite_reason="STRENGTHENING_NONFINITE_INPUT",
        label=label,
    )


def _elastic_output(value: float, label: str) -> float:
    return _finite_output_number(
        value,
        reason="ELASTIC_NONFINITE_OUTPUT",
        label=label,
    )


def _strengthening_output(value: float, label: str) -> float:
    return _finite_output_number(
        value,
        reason="STRENGTHENING_NONFINITE_OUTPUT",
        label=label,
    )


def _strengthening_ratio_product(
    numerators: list[float],
    denominators: list[float],
    label: str,
) -> float:
    """Multiply/divide positive factors without avoidable intermediates."""
    if any(value == 0 for value in numerators):
        return 0.0
    mantissa = 1.0
    exponent = 0
    for value in numerators:
        factor_mantissa, factor_exponent = math.frexp(value)
        mantissa *= factor_mantissa
        exponent += factor_exponent
        mantissa, adjustment = math.frexp(mantissa)
        exponent += adjustment
    for value in denominators:
        factor_mantissa, factor_exponent = math.frexp(value)
        mantissa /= factor_mantissa
        exponent -= factor_exponent
        mantissa, adjustment = math.frexp(mantissa)
        exponent += adjustment
    try:
        result = math.ldexp(mantissa, exponent)
    except OverflowError as error:
        raise PropertyCalculationError(
            "STRENGTHENING_NONFINITE_OUTPUT",
            f"{label}: результат вышел за диапазон binary64.",
        ) from error
    return _strengthening_output(result, label)


@dataclass(frozen=True)
class ElasticModuli:
    young_gpa: float
    poisson: float
    bulk_gpa: float
    shear_gpa: float


@dataclass
class ElasticHomogenizationResult:
    phase_table: pd.DataFrame
    bounds_table: pd.DataFrame
    volume_coverage_pct: float
    source_coverage_pct: float
    density_quality: str
    warnings: list[str]
    library_path: str
    library_sha256: str


@dataclass(frozen=True)
class StrengtheningResult:
    contribution_table: pd.DataFrame
    total_mpa: float | None
    summation_rule: str
    warnings: tuple[str, ...]
    input_provenance: str
    input_confirmation: bool


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha256(paths: ThermoGarPaths, path: str | Path) -> str:
    path = Path(path)
    try:
        path.lstat()
    except FileNotFoundError:
        return ""
    return read_verified_snapshot(
        path,
        maximum_bytes=MAX_ELASTIC_LIBRARY_BYTES,
        canonical_root=_elastic_canonical_root(paths),
    ).sha256


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        default=str,
    ).encode("utf-8-sig")


def elastic_library_path(paths: ThermoGarPaths) -> Path:
    if not isinstance(paths, ThermoGarPaths):
        raise TypeError("paths must be a ThermoGarPaths instance")
    return paths.elastic_properties_path


def _elastic_canonical_root(paths: ThermoGarPaths) -> Path:
    if not isinstance(paths, ThermoGarPaths):
        raise TypeError("paths must be a ThermoGarPaths instance")
    return paths.state_root


def empty_elastic_library() -> dict[str, Any]:
    return {
        "schema_version": ELASTIC_LIBRARY_SCHEMA_VERSION,
        "updated_at": _now_iso(),
        "entries": {},
    }


def _decode_elastic_library(data: bytes) -> dict[str, Any]:
    if not data:
        return empty_elastic_library()
    try:
        payload = json.loads(data.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Библиотека упругих свойств содержит неверный JSON.") from error
    if not isinstance(payload, dict):
        raise ValueError("Библиотека упругих свойств должна быть JSON-объектом.")
    if int(payload.get("schema_version", 0)) != ELASTIC_LIBRARY_SCHEMA_VERSION:
        raise ValueError(
            "Неподдерживаемая версия библиотеки упругих свойств: "
            f"{payload.get('schema_version')!r}."
        )
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        raise ValueError("В библиотеке отсутствует объект entries.")
    return payload


def _encode_elastic_library(library: dict[str, Any]) -> bytes:
    payload = dict(library)
    payload["schema_version"] = ELASTIC_LIBRARY_SCHEMA_VERSION
    payload["updated_at"] = _now_iso()
    payload.setdefault("entries", {})
    encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    if len(encoded) > MAX_ELASTIC_LIBRARY_BYTES:
        raise ValueError("Библиотека упругих свойств превысила допустимый размер.")
    return encoded


def load_elastic_library(paths: ThermoGarPaths) -> dict[str, Any]:
    path = elastic_library_path(paths)
    try:
        path.lstat()
    except FileNotFoundError:
        return empty_elastic_library()
    snapshot = read_verified_snapshot(
        path,
        maximum_bytes=MAX_ELASTIC_LIBRARY_BYTES,
        canonical_root=_elastic_canonical_root(paths),
    )
    return _decode_elastic_library(snapshot.data)


def save_elastic_library(
    paths: ThermoGarPaths,
    library: dict[str, Any],
) -> Path:
    path = elastic_library_path(paths)
    ensure_plain_directory(path.parent)
    atomic_write_bytes(
        path,
        _encode_elastic_library(library),
        create_backup=True,
        overwrite=True,
        canonical_root=_elastic_canonical_root(paths),
    )
    return path


def elastic_library_key(database_key: str, phase_name: str) -> str:
    return f"{str(database_key).lower()}::{str(phase_name).upper()}"


# B4B2 keeps its verified property repository private to the adapter.  These
# pure helpers deliberately live beside the frozen numerical kernels so the
# legacy editor and the verified adapter agree on the one historical entry
# shape without granting the editor any verified execution authority.
_VERIFIED_ELASTIC_ENTRY_FIELDS = (
    "database_key",
    "phase",
    "young_gpa",
    "poisson",
    "bulk_gpa",
    "shear_gpa",
    "origin",
    "source",
    "reference_temperature_c",
    "note",
    "updated_at",
)
_VERIFIED_ELASTIC_ORIGINS = ("измерено", "справочно", "модель")
_VERIFIED_PHASE_RE = re.compile(r"[A-Z][A-Z0-9_#+.:-]{0,79}")


def _verified_utc_timestamp(value: object, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    if type(value) is not str or not value:
        raise ValueError("Elastic repository timestamp is invalid.")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as error:
        raise ValueError("Elastic repository timestamp is invalid.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Elastic repository timestamp must be offset-aware.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _verified_finite_number(value: object, label: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise ValueError(f"{label} must be a binary64 number.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite.")
    return result


def _verified_legacy_compatible_entry(
    key: object,
    value: object,
) -> dict[str, Any]:
    """Validate one exhaustive writer-reachable stored entry.

    This is storage compatibility only.  The verified request gate separately
    requires complete, bounded provenance before any calculation or mutation.
    """

    if type(key) is not str or len(key) > 96 or type(value) is not dict:
        raise ValueError("Elastic repository entry identity is invalid.")
    if set(value) != set(_VERIFIED_ELASTIC_ENTRY_FIELDS):
        raise ValueError("Elastic repository entry fields are invalid.")
    database_key = value["database_key"]
    phase = value["phase"]
    if (
        database_key not in ("ni", "al", "fe")
        or type(phase) is not str
        or _VERIFIED_PHASE_RE.fullmatch(phase) is None
        or phase == "C15_LAVES"
        or key != f"{database_key}::{phase}"
    ):
        raise ValueError("Elastic repository entry key/phase is invalid.")
    young = _verified_finite_number(value["young_gpa"], "young_gpa")
    poisson = _verified_finite_number(value["poisson"], "poisson")
    bulk = _verified_finite_number(value["bulk_gpa"], "bulk_gpa")
    shear = _verified_finite_number(value["shear_gpa"], "shear_gpa")
    expected = moduli_from_e_nu(young, poisson)
    if not math.isclose(bulk, expected.bulk_gpa, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("Stored bulk modulus is inconsistent with E/nu.")
    if not math.isclose(shear, expected.shear_gpa, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("Stored shear modulus is inconsistent with E/nu.")
    origin = value["origin"]
    if type(origin) is not str or len(origin) > 128 or (
        origin != "" and origin not in _VERIFIED_ELASTIC_ORIGINS
    ):
        raise ValueError("Stored elastic origin is invalid.")
    source = value["source"]
    note = value["note"]
    if type(source) is not str or type(note) is not str:
        raise ValueError("Stored elastic source/note must be strings.")
    reference = value["reference_temperature_c"]
    if reference is not None:
        reference = _verified_finite_number(reference, "reference_temperature_c")
    updated_at = _verified_utc_timestamp(value["updated_at"])
    return {
        "database_key": database_key,
        "phase": phase,
        "young_gpa": young,
        "poisson": poisson,
        "bulk_gpa": bulk,
        "shear_gpa": shear,
        "origin": origin,
        "source": source,
        "reference_temperature_c": reference,
        "note": note,
        "updated_at": updated_at,
    }


def _verified_elastic_library_payload(value: object) -> dict[str, Any]:
    if type(value) is not dict or set(value) != {
        "schema_version",
        "updated_at",
        "entries",
    }:
        raise ValueError("Elastic repository outer fields are invalid.")
    if type(value["schema_version"]) is not int or isinstance(
        value["schema_version"], bool
    ) or value["schema_version"] != 1:
        raise ValueError("Elastic repository schema version is invalid.")
    entries = value["entries"]
    if type(entries) is not dict or len(entries) > 512:
        raise ValueError("Elastic repository entry count is invalid.")
    updated_at = _verified_utc_timestamp(value["updated_at"], allow_none=True)
    if updated_at is None and entries:
        raise ValueError("A populated elastic repository needs an update time.")
    normalized = {
        key: _verified_legacy_compatible_entry(key, entry)
        for key, entry in entries.items()
    }
    return {
        "schema_version": 1,
        "updated_at": updated_at,
        "entries": normalized,
    }


def _verified_prefill_entry(value: Mapping[str, Any]) -> dict[str, Any]:
    """Create a non-mutating strict-request copy of compatible stored data."""

    result = dict(value)
    if result.get("origin") == "":
        result["origin"] = None
    source = result.get("source")
    if source == "" or (type(source) is str and len(source) > 1024):
        result["source"] = None
    reference = result.get("reference_temperature_c")
    if reference is None or not (-273.15 <= float(reference) <= 10000.0):
        result["reference_temperature_c"] = None
    note = result.get("note")
    if type(note) is str and len(note) > 2048:
        result["note"] = ""
    return result


def moduli_from_e_nu(young_gpa: float, poisson: float) -> ElasticModuli:
    young = _elastic_input(young_gpa, "Модуль Юнга E")
    nu = _elastic_input(poisson, "Коэффициент Пуассона ν")
    if young <= 0:
        _property_fail(
            "ELASTIC_INPUT_INVALID",
            "Модуль Юнга должен быть положительным.",
        )
    if not (-1.0 < nu < 0.5):
        _property_fail(
            "ELASTIC_INPUT_INVALID",
            "Коэффициент Пуассона должен лежать между -1 и 0,5.",
        )

    bulk = young / (3.0 * (1.0 - 2.0 * nu))
    shear = young / (2.0 * (1.0 + nu))
    bulk = _elastic_output(bulk, "Объёмный модуль K")
    shear = _elastic_output(shear, "Модуль сдвига G")
    if bulk <= 0 or shear <= 0:
        _property_fail(
            "ELASTIC_NONFINITE_OUTPUT",
            "Положительные входы дали непредставимые K или G.",
        )
    return ElasticModuli(young, nu, bulk, shear)


def moduli_from_k_g(bulk_gpa: float, shear_gpa: float) -> ElasticModuli:
    bulk = _elastic_input(bulk_gpa, "Объёмный модуль K")
    shear = _elastic_input(shear_gpa, "Модуль сдвига G")
    if bulk <= 0:
        _property_fail(
            "ELASTIC_INPUT_INVALID",
            "Объёмный модуль K должен быть положительным.",
        )
    if shear <= 0:
        _property_fail(
            "ELASTIC_INPUT_INVALID",
            "Модуль сдвига G должен быть положительным.",
        )

    # Scaling keeps strongly separated, but finite, moduli from overflowing in
    # intermediate products.  A genuinely unrepresentable result still fails
    # closed in the explicit output checks below.
    scale = max(bulk, shear)
    scaled_bulk = bulk / scale
    scaled_shear = shear / scale
    denominator = 3.0 * scaled_bulk + scaled_shear
    young = scale * (
        9.0 * scaled_bulk * scaled_shear / denominator
    )
    poisson = (
        (3.0 * scaled_bulk - 2.0 * scaled_shear)
        / (2.0 * denominator)
    )
    young = _elastic_output(young, "Модуль Юнга E")
    poisson = _elastic_output(poisson, "Коэффициент Пуассона ν")
    if young <= 0 or not (-1.0 < poisson < 0.5):
        _property_fail(
            "ELASTIC_NONFINITE_OUTPUT",
            "Положительные K и G дали численно вырожденные E или ν.",
        )
    return ElasticModuli(young, poisson, bulk, shear)


def vrh_homogenization(
    phase_rows: list[dict[str, float | str]],
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Compute isotropic Voigt/Reuss/Hill bounds from phase K/G values."""
    if not isinstance(phase_rows, list) or not phase_rows:
        _property_fail(
            "ELASTIC_INPUT_INVALID",
            "Нет фаз для расчёта упругих свойств.",
        )

    fractions: list[float] = []
    bulk: list[float] = []
    shear: list[float] = []
    for index, row in enumerate(phase_rows):
        if not isinstance(row, Mapping):
            _property_fail(
                "ELASTIC_INPUT_INVALID",
                f"Фаза {index}: ожидается объект с volume_fraction, bulk_gpa и shear_gpa.",
            )
        required_fields = {"volume_fraction", "bulk_gpa", "shear_gpa"}
        allowed_fields = required_fields | {"phase"}
        row_fields = set(row)
        missing_fields = required_fields - row_fields
        extra_fields = row_fields - allowed_fields
        if missing_fields or extra_fields:
            details: list[str] = []
            if missing_fields:
                details.append(
                    "отсутствуют " + ", ".join(sorted(str(value) for value in missing_fields))
                )
            if extra_fields:
                details.append(
                    "лишние " + ", ".join(sorted(str(value) for value in extra_fields))
                )
            _property_fail(
                "ELASTIC_INPUT_INVALID",
                f"Фаза {index}: недопустимый набор полей ({'; '.join(details)}).",
            )
        try:
            fraction_value = row["volume_fraction"]
            bulk_value = row["bulk_gpa"]
            shear_value = row["shear_gpa"]
        except KeyError as error:
            raise PropertyCalculationError(
                "ELASTIC_INPUT_INVALID",
                f"Фаза {index}: отсутствует обязательное поле {error.args[0]!r}.",
            ) from error
        fractions.append(
            _elastic_input(fraction_value, f"Фаза {index}: объёмная доля")
        )
        bulk.append(_elastic_input(bulk_value, f"Фаза {index}: K"))
        shear.append(_elastic_input(shear_value, f"Фаза {index}: G"))

    # Homogenized outputs have no phase-order semantics.  Canonical numeric
    # ordering makes permutation replays take the same summation path.
    canonical_rows = sorted(zip(fractions, bulk, shear))
    fractions = [row[0] for row in canonical_rows]
    bulk = [row[1] for row in canonical_rows]
    shear = [row[2] for row in canonical_rows]

    if any(value < 0 for value in fractions):
        _property_fail(
            "ELASTIC_INPUT_INVALID",
            "Объёмные доли фаз содержат недопустимые значения.",
        )
    fraction_scale = max(fractions)
    if fraction_scale <= 0:
        _property_fail(
            "ELASTIC_INPUT_INVALID",
            "Сумма объёмных долей равна нулю.",
        )
    scaled_fractions = [value / fraction_scale for value in fractions]
    fraction_sum = math.fsum(scaled_fractions)
    if not math.isfinite(fraction_sum) or fraction_sum <= 0:
        _property_fail(
            "ELASTIC_NONFINITE_OUTPUT",
            "Нормирование объёмных долей дало непредставимый результат.",
        )

    if any(value <= 0 for value in bulk):
        _property_fail(
            "ELASTIC_INPUT_INVALID",
            "Все фазовые значения K должны быть положительными.",
        )
    if any(value <= 0 for value in shear):
        _property_fail(
            "ELASTIC_INPUT_INVALID",
            "Все фазовые значения G должны быть положительными.",
        )

    def arithmetic_mean(values: list[float], label: str) -> float:
        scale = max(values)
        scaled_mean = math.fsum(
            weight * (value / scale)
            for weight, value in zip(scaled_fractions, values)
        ) / fraction_sum
        # A weighted mean cannot exceed its largest input.  Clamp only the
        # possible one-ulp normalization overshoot at that exact boundary.
        scaled_mean = min(scaled_mean, 1.0)
        return _elastic_output(scale * scaled_mean, label)

    def harmonic_mean(values: list[float], label: str) -> float:
        scale = min(values)
        denominator = math.fsum(
            weight * (scale / value)
            for weight, value in zip(scaled_fractions, values)
        ) / fraction_sum
        if denominator <= 0 or not math.isfinite(denominator):
            _property_fail(
                "ELASTIC_NONFINITE_OUTPUT",
                f"{label}: гармоническое среднее непредставимо.",
            )
        return _elastic_output(scale / denominator, label)

    try:
        k_voigt = arithmetic_mean(bulk, "K Voigt")
        g_voigt = arithmetic_mean(shear, "G Voigt")
        k_reuss = harmonic_mean(bulk, "K Reuss")
        g_reuss = harmonic_mean(shear, "G Reuss")
    except (OverflowError, ZeroDivisionError) as error:
        raise PropertyCalculationError(
            "ELASTIC_NONFINITE_OUTPUT",
            "Расчёт VRH вышел за диапазон конечных binary64-чисел.",
        ) from error
    k_hill = _elastic_output(0.5 * k_voigt + 0.5 * k_reuss, "K Hill")
    g_hill = _elastic_output(0.5 * g_voigt + 0.5 * g_reuss, "G Hill")

    vrh_outputs = {
        "K Voigt": k_voigt,
        "G Voigt": g_voigt,
        "K Reuss": k_reuss,
        "G Reuss": g_reuss,
        "K Hill": k_hill,
        "G Hill": g_hill,
    }
    collapsed_outputs = [
        label for label, value in vrh_outputs.items() if value <= 0
    ]
    if collapsed_outputs:
        _property_fail(
            "ELASTIC_NONFINITE_OUTPUT",
            "Положительные фазовые модули дали численно вырожденные значения: "
            + ", ".join(collapsed_outputs)
            + ".",
        )

    methods = [
        ("Reuss — нижняя граница", k_reuss, g_reuss),
        ("Hill — средняя VRH", k_hill, g_hill),
        ("Voigt — верхняя граница", k_voigt, g_voigt),
    ]

    rows: list[dict[str, float | str]] = []
    for name, k_value, g_value in methods:
        elastic = moduli_from_k_g(k_value, g_value)
        k_over_g = _elastic_output(
            elastic.bulk_gpa / elastic.shear_gpa,
            f"{name}: K/G",
        )
        if k_over_g <= 0:
            _property_fail(
                "ELASTIC_NONFINITE_OUTPUT",
                f"{name}: положительное отношение K/G численно выродилось.",
            )
        rows.append(
            {
                "Метод": name,
                "K, ГПа": elastic.bulk_gpa,
                "G, ГПа": elastic.shear_gpa,
                "E, ГПа": elastic.young_gpa,
                "ν": elastic.poisson,
                "K/G": k_over_g,
            }
        )

    table = pd.DataFrame(rows)
    summary = {
        "K_Reuss_GPa": k_reuss,
        "K_Hill_GPa": k_hill,
        "K_Voigt_GPa": k_voigt,
        "G_Reuss_GPa": g_reuss,
        "G_Hill_GPa": g_hill,
        "G_Voigt_GPa": g_voigt,
        "E_Reuss_GPa": float(table.iloc[0]["E, ГПа"]),
        "E_Hill_GPa": float(table.iloc[1]["E, ГПа"]),
        "E_Voigt_GPa": float(table.iloc[2]["E, ГПа"]),
        "nu_Hill": float(table.iloc[1]["ν"]),
        "K_over_G_Hill": float(table.iloc[1]["K/G"]),
    }
    for key, value in summary.items():
        _elastic_output(value, key)
    return table, summary


def hall_petch_contribution(
    k_y_mpa_sqrt_m: float,
    grain_size_um: float,
) -> float:
    k_y = _strengthening_input(k_y_mpa_sqrt_m, "Коэффициент Hall–Petch")
    grain_um = _strengthening_input(grain_size_um, "Размер зерна")
    if k_y < 0:
        _property_fail(
            "STRENGTHENING_INPUT_INVALID",
            "Коэффициент Hall–Petch не может быть отрицательным.",
        )
    if grain_um <= 0:
        _property_fail(
            "STRENGTHENING_INPUT_INVALID",
            "Размер зерна должен быть положительным.",
        )
    contribution = _strengthening_ratio_product(
        [k_y, 1000.0],
        [math.sqrt(grain_um)],
        "Вклад Hall–Petch",
    )
    if k_y > 0 and contribution <= 0:
        _property_fail(
            "STRENGTHENING_NONFINITE_OUTPUT",
            "Положительный вклад Hall–Petch численно выродился.",
        )
    return contribution


def taylor_contribution(
    taylor_factor: float,
    alpha: float,
    shear_gpa: float,
    burgers_nm: float,
    dislocation_density_m2: float,
) -> float:
    m = _strengthening_input(taylor_factor, "Taylor factor M")
    interaction = _strengthening_input(alpha, "Коэффициент взаимодействия α")
    shear = _strengthening_input(shear_gpa, "Модуль сдвига G")
    burgers = _strengthening_input(burgers_nm, "Вектор Бюргерса b")
    density = _strengthening_input(
        dislocation_density_m2,
        "Плотность дислокаций",
    )

    if m <= 0 or interaction <= 0:
        _property_fail(
            "STRENGTHENING_INPUT_INVALID",
            "M и α должны быть положительными.",
        )
    if shear <= 0 or burgers <= 0 or density <= 0:
        _property_fail(
            "STRENGTHENING_INPUT_INVALID",
            "G, b и плотность дислокаций должны быть положительными.",
        )

    # With G in GPa and b in nm, the 1e9/1e-9 unit factors cancel.
    contribution = _strengthening_ratio_product(
        [m, interaction, shear, burgers, math.sqrt(density)],
        [1e6],
        "Вклад Taylor",
    )
    if contribution <= 0:
        _property_fail(
            "STRENGTHENING_NONFINITE_OUTPUT",
            "Положительный вклад Taylor численно выродился.",
        )
    return contribution


def orowan_contribution(
    taylor_factor: float,
    shear_gpa: float,
    burgers_nm: float,
    poisson: float,
    particle_radius_nm: float,
    spacing_nm: float,
) -> float:
    m = _strengthening_input(taylor_factor, "Taylor factor M для Orowan")
    shear = _strengthening_input(shear_gpa, "Модуль сдвига G для Orowan")
    burgers = _strengthening_input(burgers_nm, "Вектор Бюргерса b для Orowan")
    nu = _strengthening_input(poisson, "Коэффициент Пуассона ν")
    radius = _strengthening_input(particle_radius_nm, "Радиус частицы")
    spacing = _strengthening_input(spacing_nm, "Межчастичное расстояние")

    if m <= 0 or shear <= 0 or burgers <= 0:
        _property_fail(
            "STRENGTHENING_INPUT_INVALID",
            "M, G и b должны быть положительными.",
        )
    if not (-1.0 < nu < 0.5):
        _property_fail(
            "STRENGTHENING_INPUT_INVALID",
            "Коэффициент Пуассона должен лежать между -1 и 0,5.",
        )
    if radius <= burgers:
        _property_fail(
            "STRENGTHENING_INPUT_INVALID",
            "Радиус частицы должен быть больше вектора Бюргерса.",
        )
    if spacing <= 0:
        _property_fail(
            "STRENGTHENING_INPUT_INVALID",
            "Межчастичное расстояние должно быть положительным.",
        )

    # Use the ratio for close values (avoids cancellation), and logarithm
    # subtraction only when the ratio itself would overflow.
    radius_ratio = radius / burgers
    logarithm = (
        math.log(radius_ratio)
        if math.isfinite(radius_ratio)
        else math.log(radius) - math.log(burgers)
    )
    contribution = _strengthening_ratio_product(
        [m, 0.4, shear, burgers, logarithm, 1000.0],
        [2.0 * math.pi, math.sqrt(1.0 - nu), spacing],
        "Вклад Orowan",
    )
    if contribution <= 0:
        _property_fail(
            "STRENGTHENING_NONFINITE_OUTPUT",
            "Положительный вклад Orowan численно выродился.",
        )
    return contribution


def combine_strengthening(
    sigma_internal_mpa: float,
    contributions_mpa: list[float],
    rule: str,
) -> float | None:
    sigma_internal = _strengthening_input(
        sigma_internal_mpa,
        "Базовое внутреннее сопротивление",
    )
    if not isinstance(contributions_mpa, list):
        _property_fail(
            "STRENGTHENING_INPUT_INVALID",
            "Вклады упрочнения должны быть переданы списком.",
        )
    contributions = [
        _strengthening_input(value, f"Вклад упрочнения {index}")
        for index, value in enumerate(contributions_mpa)
    ]
    if sigma_internal < 0 or any(value < 0 for value in contributions):
        _property_fail(
            "STRENGTHENING_INPUT_INVALID",
            "Вклады упрочнения не должны быть отрицательными.",
        )

    if rule == "Не суммировать":
        return None
    if rule == "Линейная сумма":
        try:
            total = math.fsum([sigma_internal, *contributions])
        except OverflowError as error:
            raise PropertyCalculationError(
                "STRENGTHENING_NONFINITE_OUTPUT",
                "Линейная сумма вышла за диапазон binary64.",
            ) from error
        return _strengthening_output(total, "Линейная сумма вкладов")
    if rule == "Квадратичное объединение вкладов":
        contribution_norm = math.hypot(*contributions)
        return _strengthening_output(
            sigma_internal + contribution_norm,
            "Квадратичное объединение вкладов",
        )
    _property_fail(
        "STRENGTHENING_RULE_INVALID",
        f"Неизвестное правило суммирования: {rule}",
    )


def calculate_strengthening(
    *,
    input_provenance: str,
    input_confirmation: bool,
    sigma_internal_mpa: float,
    hall_petch: dict[str, float] | None,
    taylor: dict[str, float] | None,
    solid_solution_mpa: float | None,
    orowan: dict[str, float] | None,
    other_mpa: float | None,
    summation_rule: str,
) -> StrengtheningResult:
    if not isinstance(input_provenance, str) or not input_provenance.strip():
        raise PropertyCalculationError(
            "STRENGTHENING_PROVENANCE_REQUIRED",
            "Укажите источник и область применимости всех коэффициентов."
        )
    if input_confirmation is not True:
        raise PropertyCalculationError(
            "STRENGTHENING_CONFIRMATION_REQUIRED",
            "Требуется явное подтверждение research-only границы расчёта."
        )
    if summation_rule not in STRENGTHENING_SUMMATION_RULES:
        _property_fail(
            "STRENGTHENING_RULE_INVALID",
            f"Неизвестное правило суммирования: {summation_rule}",
        )

    sigma_internal = _strengthening_input(
        sigma_internal_mpa,
        "Базовое внутреннее сопротивление",
    )
    if sigma_internal < 0:
        _property_fail(
            "STRENGTHENING_INPUT_INVALID",
            "Вклады упрочнения не должны быть отрицательными.",
        )

    def mechanism_inputs(
        payload: Mapping[str, Any],
        required: tuple[str, ...],
        label: str,
    ) -> dict[str, float]:
        if not isinstance(payload, Mapping) or set(payload) != set(required):
            _property_fail(
                "STRENGTHENING_INPUT_INVALID",
                f"{label}: требуется точный набор полей {required!r}.",
            )
        return {
            key: _strengthening_input(payload[key], f"{label}.{key}")
            for key in required
        }

    rows: list[dict[str, Any]] = []
    values: list[float] = []
    warnings: list[str] = []

    rows.append(
        {
            "Механизм": "Внутреннее сопротивление / базовый уровень",
            "Вклад, МПа": sigma_internal,
            "Формула": "σ_int",
            "Исходные данные": "задано пользователем",
        }
    )

    if hall_petch is not None:
        hall_petch_inputs = mechanism_inputs(
            hall_petch,
            ("k_y_mpa_sqrt_m", "grain_size_um"),
            "Hall–Petch",
        )
        value = hall_petch_contribution(**hall_petch_inputs)
        values.append(value)
        rows.append(
            {
                "Механизм": "Hall–Petch",
                "Вклад, МПа": value,
                "Формула": "Δσ = k_y / √d",
                "Исходные данные": (
                    f"k_y={hall_petch_inputs['k_y_mpa_sqrt_m']:.6g} МПа·м^1/2; "
                    f"d={hall_petch_inputs['grain_size_um']:.6g} мкм"
                ),
            }
        )

    if taylor is not None:
        taylor_inputs = mechanism_inputs(
            taylor,
            (
                "taylor_factor",
                "alpha",
                "shear_gpa",
                "burgers_nm",
                "dislocation_density_m2",
            ),
            "Taylor",
        )
        value = taylor_contribution(**taylor_inputs)
        values.append(value)
        rows.append(
            {
                "Механизм": "Дислокационное упрочнение Taylor",
                "Вклад, МПа": value,
                "Формула": "Δσ = M α G b √ρ_d",
                "Исходные данные": (
                    f"M={taylor_inputs['taylor_factor']:.6g}; "
                    f"α={taylor_inputs['alpha']:.6g}; "
                    f"G={taylor_inputs['shear_gpa']:.6g} ГПа; "
                    f"b={taylor_inputs['burgers_nm']:.6g} нм; "
                    f"ρ_d={taylor_inputs['dislocation_density_m2']:.6g} м⁻²"
                ),
            }
        )

    if solid_solution_mpa is not None:
        value = _strengthening_input(
            solid_solution_mpa,
            "Твёрдорастворный вклад",
        )
        if value < 0:
            _property_fail(
                "STRENGTHENING_INPUT_INVALID",
                "Твёрдорастворный вклад не может быть отрицательным.",
            )
        values.append(value)
        rows.append(
            {
                "Механизм": "Твёрдорастворное упрочнение",
                "Вклад, МПа": value,
                "Формула": "внешняя source-backed модель / объявленный ввод",
                "Исходные данные": "вклад введён пользователем",
            }
        )
        warnings.append(
            "ThermoGar не подбирает коэффициенты Fleischer/Labusch: "
            "введённый твёрдорастворный вклад должен иметь внешний источник."
        )

    if orowan is not None:
        orowan_inputs = mechanism_inputs(
            orowan,
            (
                "taylor_factor",
                "shear_gpa",
                "burgers_nm",
                "poisson",
                "particle_radius_nm",
                "spacing_nm",
            ),
            "Orowan",
        )
        value = orowan_contribution(**orowan_inputs)
        values.append(value)
        rows.append(
            {
                "Механизм": "Обход частиц Orowan",
                "Вклад, МПа": value,
                "Формула": (
                    "Δσ = M·0,4Gb/[2π√(1-ν)λ]·ln(r/b)"
                ),
                "Исходные данные": (
                    f"M={orowan_inputs['taylor_factor']:.6g}; "
                    f"G={orowan_inputs['shear_gpa']:.6g} ГПа; "
                    f"b={orowan_inputs['burgers_nm']:.6g} нм; "
                    f"ν={orowan_inputs['poisson']:.6g}; "
                    f"r={orowan_inputs['particle_radius_nm']:.6g} нм; "
                    f"λ={orowan_inputs['spacing_nm']:.6g} нм"
                ),
            }
        )
        warnings.append(
            "Orowan применим к несрезаемым частицам; для малых когерентных "
            "частиц может действовать механизм перерезания."
        )

    if other_mpa is not None:
        value = _strengthening_input(other_mpa, "Дополнительный вклад")
        if value < 0:
            _property_fail(
                "STRENGTHENING_INPUT_INVALID",
                "Дополнительный вклад не может быть отрицательным.",
            )
        values.append(value)
        rows.append(
            {
                "Механизм": "Другой калиброванный вклад",
                "Вклад, МПа": value,
                "Формула": "задано пользователем",
                "Исходные данные": "модель и источник указываются отдельно",
            }
        )

    total = combine_strengthening(
        sigma_internal,
        values,
        summation_rule,
    )

    if total is not None:
        warnings.append(
            "Итог является механизм-ориентированной оценкой при выбранном "
            "правиле объединения, а не автоматически валидированным пределом "
            "текучести конкретной марки."
        )

    return StrengtheningResult(
        contribution_table=pd.DataFrame(rows),
        total_mpa=total,
        summation_rule=summation_rule,
        warnings=tuple(warnings),
        input_provenance=input_provenance.strip(),
        input_confirmation=input_confirmation,
    )


def _library_entry(
    library: dict[str, Any],
    database_key: str,
    phase_name: str,
) -> dict[str, Any]:
    entries = library.get("entries", {})
    entry = entries.get(elastic_library_key(database_key, phase_name), {})
    return dict(entry) if isinstance(entry, dict) else {}


def _elastic_editor_dataframe(
    phase_table: pd.DataFrame,
    library: dict[str, Any],
    database_key: str,
    calculation_temperature_c: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, phase_row in phase_table.iterrows():
        volume_fraction = phase_row.get("Объёмная доля, %")
        if pd.isna(volume_fraction) or float(volume_fraction) <= 1e-10:
            continue
        phase_name = str(phase_row["Фаза"])
        entry = _library_entry(library, database_key, phase_name)
        rows.append(
            {
                "Фаза": phase_name,
                "Объёмная доля, %": float(volume_fraction),
                "E, ГПа": entry.get("young_gpa"),
                "ν": entry.get("poisson"),
                "Происхождение": entry.get("origin", ""),
                "Источник": entry.get("source", ""),
                "Температура источника, °C": entry.get(
                    "reference_temperature_c",
                    float(calculation_temperature_c),
                ),
                "Примечание": entry.get("note", ""),
                "Статус плотности": phase_row.get("Статус данных", ""),
            }
        )
    return pd.DataFrame(rows)


def _save_editor_to_library(
    paths: ThermoGarPaths,
    database_key: str,
    edited: pd.DataFrame,
) -> tuple[Path, int]:
    updates: dict[str, dict[str, Any]] = {}

    for _, row in edited.iterrows():
        phase = str(row.get("Фаза", "")).strip().upper()
        if not phase:
            continue
        young = pd.to_numeric(pd.Series([row.get("E, ГПа")]), errors="coerce").iloc[0]
        poisson = pd.to_numeric(pd.Series([row.get("ν")]), errors="coerce").iloc[0]
        if pd.isna(young) or pd.isna(poisson):
            continue
        moduli = moduli_from_e_nu(float(young), float(poisson))
        reference_temperature = pd.to_numeric(
            pd.Series([row.get("Температура источника, °C")]),
            errors="coerce",
        ).iloc[0]
        updates[elastic_library_key(database_key, phase)] = {
            "database_key": database_key,
            "phase": phase,
            "young_gpa": moduli.young_gpa,
            "poisson": moduli.poisson,
            "bulk_gpa": moduli.bulk_gpa,
            "shear_gpa": moduli.shear_gpa,
            "origin": str(row.get("Происхождение", "")).strip(),
            "source": str(row.get("Источник", "")).strip(),
            "reference_temperature_c": (
                None
                if pd.isna(reference_temperature)
                else float(reference_temperature)
            ),
            "note": str(row.get("Примечание", "")).strip(),
            "updated_at": _now_iso(),
        }

    path = elastic_library_path(paths)
    ensure_plain_directory(path.parent)

    def mutate(existing_bytes: bytes) -> bytes:
        library = _decode_elastic_library(existing_bytes)
        entries = library.setdefault("entries", {})
        entries.update(updates)
        return _encode_elastic_library(library)

    atomic_update_bytes(
        path,
        mutate,
        create_backup=True,
        maximum_bytes=MAX_ELASTIC_LIBRARY_BYTES,
        canonical_root=_elastic_canonical_root(paths),
    )
    return path, len(updates)


def _calculate_elastic_from_editor(
    edited: pd.DataFrame,
    calculation_temperature_c: float,
    density_quality: str,
    paths: ThermoGarPaths,
) -> ElasticHomogenizationResult:
    if edited.empty:
        raise ValueError("Нет фаз с рассчитанной объёмной долей.")

    phase_rows: list[dict[str, float | str]] = []
    output_rows: list[dict[str, Any]] = []
    missing_phases: list[str] = []
    source_missing: list[str] = []
    reference_temperature_missing: list[str] = []
    temperature_warnings: list[str] = []
    covered_volume = 0.0
    source_covered_volume = 0.0

    for _, row in edited.iterrows():
        phase = str(row["Фаза"])
        volume_pct = float(row["Объёмная доля, %"])
        young = pd.to_numeric(pd.Series([row.get("E, ГПа")]), errors="coerce").iloc[0]
        poisson = pd.to_numeric(pd.Series([row.get("ν")]), errors="coerce").iloc[0]

        if pd.isna(young) or pd.isna(poisson):
            missing_phases.append(phase)
            continue

        moduli = moduli_from_e_nu(float(young), float(poisson))
        covered_volume += volume_pct
        source = str(row.get("Источник", "")).strip()
        origin = str(row.get("Происхождение", "")).strip()
        if source and origin:
            source_covered_volume += volume_pct
        else:
            source_missing.append(phase)

        reference_temperature = pd.to_numeric(
            pd.Series([row.get("Температура источника, °C")]),
            errors="coerce",
        ).iloc[0]
        if pd.isna(reference_temperature):
            reference_temperature_missing.append(phase)
        else:
            difference = abs(float(reference_temperature) - calculation_temperature_c)
            if difference > 50.0:
                temperature_warnings.append(
                    f"{phase}: свойства заданы при {float(reference_temperature):.1f} °C, "
                    f"расчёт выполняется при {calculation_temperature_c:.1f} °C."
                )

        phase_rows.append(
            {
                "phase": phase,
                "volume_fraction": volume_pct / 100.0,
                "bulk_gpa": moduli.bulk_gpa,
                "shear_gpa": moduli.shear_gpa,
            }
        )
        output_rows.append(
            {
                "Фаза": phase,
                "Объёмная доля, %": volume_pct,
                "E, ГПа": moduli.young_gpa,
                "ν": moduli.poisson,
                "K, ГПа": moduli.bulk_gpa,
                "G, ГПа": moduli.shear_gpa,
                "Происхождение": origin,
                "Источник": source,
                "Температура источника, °C": (
                    None
                    if pd.isna(reference_temperature)
                    else float(reference_temperature)
                ),
                "Статус плотности": str(row.get("Статус плотности", "")),
                "Примечание": str(row.get("Примечание", "")),
            }
        )

    total_volume = float(edited["Объёмная доля, %"].sum())
    volume_coverage = 100.0 * covered_volume / total_volume if total_volume else 0.0
    source_coverage = (
        100.0 * source_covered_volume / total_volume if total_volume else 0.0
    )

    if missing_phases:
        raise ValueError(
            "Не заданы E и ν для фаз: " + ", ".join(missing_phases) + "."
        )
    if source_missing:
        raise ValueError(
            "Для каждой фазы обязательны происхождение и источник: "
            + ", ".join(source_missing)
            + "."
        )
    if reference_temperature_missing:
        raise ValueError(
            "Для каждой фазы обязательна температура источника: "
            + ", ".join(reference_temperature_missing)
            + "."
        )
    if abs(total_volume - 100.0) > 1e-4:
        raise ValueError(
            "Полные объёмные доли недоступны или не суммируются к 100 %. "
            "Сначала обеспечьте плотностями все равновесные фазы."
        )

    bounds, _summary = vrh_homogenization(phase_rows)
    warnings: list[str] = []
    warnings.extend(temperature_warnings)
    if "оценоч" in density_quality.lower():
        warnings.append(
            "Часть объёмных долей опирается на оценочные соответствия плотности "
            "связанным фазам."
        )

    library_path = elastic_library_path(paths)
    return ElasticHomogenizationResult(
        phase_table=pd.DataFrame(output_rows),
        bounds_table=bounds,
        volume_coverage_pct=volume_coverage,
        source_coverage_pct=source_coverage,
        density_quality=density_quality,
        warnings=warnings,
        library_path=str(library_path),
        library_sha256=_sha256(paths, library_path),
    )


def _elastic_figure(
    bounds: pd.DataFrame,
    theme_type: str | None,
) -> plt.Figure:
    roles = chart_roles(theme_type)
    figure, axes = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(bounds))
    axes.bar(
        x,
        bounds["E, ГПа"].to_numpy(dtype=float),
        color=roles["primary"],
    )
    axes.set_xticks(x)
    axes.set_xticklabels(
        [str(value).split(" — ")[0] for value in bounds["Метод"]],
    )
    axes.set_ylabel("Модуль Юнга E, ГПа")
    axes.set_title("ThermoGar: границы Voigt–Reuss–Hill")
    axes.grid(True, axis="y", color=roles["grid"], alpha=0.35)
    axes.tick_params(colors=roles["axis"])
    axes.yaxis.label.set_color(roles["axis"])
    axes.xaxis.label.set_color(roles["axis"])
    axes.title.set_color(roles["text"])
    for spine in axes.spines.values():
        spine.set_color(roles["grid"])
    figure.tight_layout()
    return figure


def _strengthening_figure(
    table: pd.DataFrame,
    theme_type: str | None,
) -> plt.Figure:
    roles = chart_roles(theme_type)
    figure, axes = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(table))
    axes.bar(
        x,
        table["Вклад, МПа"].to_numpy(dtype=float),
        color=roles["primary_dark"],
    )
    axes.set_xticks(x)
    axes.set_xticklabels(
        [
            str(value)
            .replace("Внутреннее сопротивление / базовый уровень", "Базовый")
            .replace("Дислокационное упрочнение Taylor", "Taylor")
            .replace("Твёрдорастворное упрочнение", "Раствор")
            .replace("Обход частиц Orowan", "Orowan")
            .replace("Другой калиброванный вклад", "Другой")
            for value in table["Механизм"]
        ],
        rotation=20,
        ha="right",
    )
    axes.set_ylabel("Вклад, МПа")
    axes.set_title("ThermoGar: введённые вклады упрочнения")
    axes.grid(True, axis="y", color=roles["grid"], alpha=0.35)
    axes.tick_params(colors=roles["axis"])
    axes.yaxis.label.set_color(roles["axis"])
    axes.title.set_color(roles["text"])
    for spine in axes.spines.values():
        spine.set_color(roles["grid"])
    figure.tight_layout()
    return figure


def render_elastic_section(
    *,
    db: Any,
    database_key: str,
    database_path: str | Path,
    database_label: str,
    paths: ThermoGarPaths,
    current_context: dict[str, Any],
    physical_db: Any,
    balance: str,
    units: str,
    units_label: str,
    composition_text: str,
    pressure_pa: float,
    steel_mode: str,
    default_temperature_c: float,
    parse_composition: Callable[[str], dict[str, float]],
    prepare_calculation: Callable[..., tuple],
    dataframe_to_excel: Callable[[dict[str, pd.DataFrame]], bytes],
    figure_to_png: Callable[[plt.Figure], bytes],
    render_error: Callable[..., None],
    record_history: Callable[..., None],
    theme_type: str | None,
) -> None:
    st.subheader("Упругие свойства и гомогенизация")
    st.caption(
        "ThermoGar рассчитывает границы Voigt–Reuss–Hill только после того, "
        "как пользователь задаст упругие свойства каждой равновесной фазы. "
        "Из одного химического состава E и ν не выводятся."
    )

    if physical_db is None:
        st.error(
            "Для упругой гомогенизации сначала нужна физическая база плотности, "
            "потому что правила смесей используют объёмные доли фаз."
        )
        return

    elastic_temperature = st.number_input(
        "Температура расчёта, °C",
        value=float(default_temperature_c),
        step=10.0,
        key=f"elastic_temperature_{database_key}",
    )

    context_signature = {
        "database_key": database_key,
        "database_sha256": current_context.get("database_sha256", ""),
        "balance": balance,
        "units": units,
        "composition": composition_text.strip(),
        "pressure_pa": float(pressure_pa),
        "steel_mode": steel_mode,
        "temperature_c": float(elastic_temperature),
    }

    if release_calculation_button(
        "Подготовить равновесные фазы",
        type="primary",
        key=f"elastic_prepare_{database_key}",
    ):
        try:
            entered = parse_composition(composition_text)
            (
                components,
                composition_conditions,
                _overall_x,
                _overall_w,
                phases,
            ) = prepare_calculation(
                db,
                database_key,
                entered,
                units,
                balance,
                steel_mode,
            )
            conditions = {
                v.N: 1.0,
                v.P: float(pressure_pa),
                v.T: float(elastic_temperature) + 273.15,
            }
            conditions.update(composition_conditions)

            with st.spinner("Равновесие и объёмные доли фаз…"):
                eq = equilibrium(
                    db,
                    components,
                    phases,
                    conditions,
                    calc_opts={"pdens": 500},
                )
                physical_result = calculate_physical_properties(
                    db,
                    eq,
                    components,
                    float(elastic_temperature) + 273.15,
                    physical_db,
                )

            library = load_elastic_library(paths)
            editor = _elastic_editor_dataframe(
                physical_result.phase_table,
                library,
                database_key,
                float(elastic_temperature),
            )
            st.session_state[f"elastic_prepared_{database_key}"] = {
                "temperature_c": float(elastic_temperature),
                "physical_result": physical_result,
                "editor": editor,
                "context_signature": dict(context_signature),
            }
        except Exception as error:
            render_error(error, context="упругие свойства")

    prepared = st.session_state.get(f"elastic_prepared_{database_key}")
    if not isinstance(prepared, dict):
        st.info(
            "Нажмите «Подготовить равновесные фазы». Затем заполните E, ν и "
            "источник для каждой фазы."
        )
        return

    if prepared.get("context_signature") != context_signature:
        st.warning(
            "После подготовки фаз изменились состав, база, температура или "
            "другие исходные данные. Нажмите «Подготовить равновесные фазы» "
            "ещё раз; старый результат не используется."
        )
        return

    physical_result = prepared["physical_result"]
    st.markdown("### Фазы и исходные свойства")
    st.caption(
        "Объёмные доли получены из равновесия и physical_data.pdb. "
        "Колонки E и ν заполняются пользователем либо загружаются из локальной "
        "библиотеки. Происхождение: «измерено», «справочно» или «модель»."
    )

    edited = st.data_editor(
        prepared["editor"],
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        disabled=[
            "Фаза",
            "Объёмная доля, %",
            "Статус плотности",
        ],
        column_config={
            "E, ГПа": st.column_config.NumberColumn(
                "E, ГПа",
                min_value=0.0,
                format="%.6g",
            ),
            "ν": st.column_config.NumberColumn(
                "ν",
                min_value=-0.99,
                max_value=0.499,
                format="%.6f",
            ),
            "Происхождение": st.column_config.SelectboxColumn(
                "Происхождение",
                options=["", "измерено", "справочно", "модель"],
            ),
            "Температура источника, °C": st.column_config.NumberColumn(
                "Температура источника, °C",
                format="%.2f",
            ),
        },
        key=f"elastic_editor_{database_key}",
    )

    save_to_library = st.checkbox(
        "Сохранить заполненные свойства фаз в локальную библиотеку",
        value=False,
        key=f"elastic_save_library_{database_key}",
    )

    if release_calculation_button(
        "Рассчитать Voigt–Reuss–Hill",
        type="primary",
        key=f"elastic_calculate_{database_key}",
    ):
        try:
            library_path = elastic_library_path(paths)
            saved_count = 0
            if save_to_library:
                library_path, saved_count = _save_editor_to_library(
                    paths,
                    database_key,
                    edited,
                )

            result = _calculate_elastic_from_editor(
                edited,
                float(prepared["temperature_c"]),
                physical_result.quality_label,
                paths,
            )
            figure = _elastic_figure(result.bounds_table, theme_type)

            settings = pd.DataFrame(
                [
                    ("Термодинамическая база", database_label),
                    ("Файл TDB", str(database_path)),
                    ("SHA-256 TDB", current_context.get("database_sha256", "")),
                    ("Температура, °C", prepared["temperature_c"]),
                    ("Давление, Па", pressure_pa),
                    ("Основа", balance),
                    ("Единицы ввода", units_label),
                    ("Добавки", composition_text),
                    ("Библиотека фаз", str(library_path)),
                    ("SHA-256 библиотеки", _sha256(paths, library_path)),
                    ("Сохранено записей", saved_count),
                    ("Схема результата", ELASTIC_RESULT_SCHEMA_VERSION),
                ],
                columns=["Параметр", "Значение"],
            )

            st.session_state[f"elastic_result_{database_key}"] = {
                "result": result,
                "settings": settings,
                "figure": figure,
            }
            record_history(
                paths,
                "Упругие свойства VRH",
                current_context,
                {
                    "temperature_C": float(prepared["temperature_c"]),
                    "E_Hill_GPa": float(
                        result.bounds_table.loc[
                            result.bounds_table["Метод"] == "Hill — средняя VRH",
                            "E, ГПа",
                        ].iloc[0]
                    ),
                    "phase_count": int(len(result.phase_table)),
                    "elastic_library_sha256": result.library_sha256,
                },
            )
        except Exception as error:
            render_error(error, context="упругие свойства VRH")

    state = st.session_state.get(f"elastic_result_{database_key}")
    if not isinstance(state, dict):
        return

    result: ElasticHomogenizationResult = state["result"]
    hill = result.bounds_table.loc[
        result.bounds_table["Метод"] == "Hill — средняя VRH"
    ].iloc[0]
    metric1, metric2, metric3, metric4 = st.columns(4)
    with metric1:
        st.metric("E_Hill, ГПа", f"{float(hill['E, ГПа']):.3f}")
    with metric2:
        st.metric("ν_Hill", f"{float(hill['ν']):.4f}")
    with metric3:
        st.metric("K_Hill, ГПа", f"{float(hill['K, ГПа']):.3f}")
    with metric4:
        st.metric("G_Hill, ГПа", f"{float(hill['G, ГПа']):.3f}")

    st.caption(
        f"Покрытие объёмных долей: {result.volume_coverage_pct:.2f} %. "
        f"Покрытие записей указанным происхождением и источником: "
        f"{result.source_coverage_pct:.2f} %. Статус плотности: "
        f"{result.density_quality}."
    )
    st.success("Расчёт Voigt–Reuss–Hill выполнен.")
    for warning in result.warnings:
        st.warning(warning)
    st.info(
        "Reuss и Voigt — нижняя и верхняя границы идеализированной изотропной "
        "гомогенизации. Реальная текстура, морфология, пористость и интерфейсы "
        "могут вывести реальную систему за границы этой простой модели."
    )

    st.pyplot(state["figure"])
    st.dataframe(result.bounds_table, width="stretch", hide_index=True)
    st.dataframe(result.phase_table, width="stretch", hide_index=True)

    excel = dataframe_to_excel(
        {
            "Параметры": state["settings"],
            "Фазы": result.phase_table,
            "VRH": result.bounds_table,
        }
    )
    download1, download2, download3 = st.columns(3)
    with download1:
        release_download_button(
            "Скачать Excel",
            data=excel,
            file_name="ThermoGar_elastic_VRH.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
    with download2:
        release_download_button(
            "Скачать PNG",
            data=figure_to_png(state["figure"]),
            file_name="ThermoGar_elastic_VRH.png",
            mime="image/png",
        )
    with download3:
        library = load_elastic_library(paths)
        release_download_button(
            "Скачать библиотеку фаз, JSON",
            data=_json_bytes(library),
            file_name="ThermoGar_elastic_phase_library.json",
            mime="application/json",
        )


def render_strengthening_section(
    *,
    paths: ThermoGarPaths,
    current_context: dict[str, Any],
    dataframe_to_excel: Callable[[dict[str, pd.DataFrame]], bytes],
    figure_to_png: Callable[[plt.Figure], bytes],
    render_error: Callable[..., None],
    record_history: Callable[..., None],
    theme_type: str | None,
) -> None:
    st.subheader("Вклады упрочнения")
    st.caption(
        "Это прозрачный калькулятор механизмов. Он не выводит предел текучести, "
        "прочность или твёрдость только из химического состава. Коэффициенты и "
        "микроструктурные параметры задаёт пользователь."
    )

    defaults = {
        "strength_sigma_internal": 0.0,
        "strength_hp_enabled": False,
        "strength_hp_k": 0.0,
        "strength_hp_d": 20.0,
        "strength_taylor_enabled": False,
        "strength_taylor_M": 3.0,
        "strength_taylor_alpha": 0.30,
        "strength_taylor_G": 0.0,
        "strength_taylor_b": 0.25,
        "strength_taylor_rho": 1e12,
        "strength_ss_enabled": False,
        "strength_ss_value": 0.0,
        "strength_ss_source": "",
        "strength_orowan_enabled": False,
        "strength_orowan_M": 3.0,
        "strength_orowan_G": 0.0,
        "strength_orowan_b": 0.25,
        "strength_orowan_nu": 0.30,
        "strength_orowan_r": 10.0,
        "strength_orowan_lambda": 100.0,
        "strength_other_enabled": False,
        "strength_other_value": 0.0,
        "strength_other_source": "",
        "strength_sum_rule": "Не суммировать",
        "strength_input_provenance": "",
        "strength_input_confirmation": False,
    }
    for state_key, default_value in defaults.items():
        st.session_state.setdefault(state_key, default_value)

    database_key = str(current_context.get("database_key", ""))
    elastic_state = st.session_state.get(f"elastic_result_{database_key}")
    if isinstance(elastic_state, dict):
        elastic_result = elastic_state.get("result")
        if isinstance(elastic_result, ElasticHomogenizationResult):
            hill_rows = elastic_result.bounds_table[
                elastic_result.bounds_table["Метод"] == "Hill — средняя VRH"
            ]
            if not hill_rows.empty and st.button(
                "Подставить G_Hill и ν_Hill из последнего упругого расчёта",
                key="strengthening_use_hill_moduli",
            ):
                hill_row = hill_rows.iloc[0]
                st.session_state["strength_taylor_G"] = float(hill_row["G, ГПа"])
                st.session_state["strength_orowan_G"] = float(hill_row["G, ГПа"])
                st.session_state["strength_orowan_nu"] = float(hill_row["ν"])
                st.rerun()

    if st.button(
        "Загрузить учебный пример Fe–0,20C",
        key="strengthening_load_example",
    ):
        st.session_state.update(
            {
                "strength_sigma_internal": 50.0,
                "strength_hp_enabled": True,
                "strength_hp_k": 0.70,
                "strength_hp_d": 20.0,
                "strength_taylor_enabled": True,
                "strength_taylor_M": 3.06,
                "strength_taylor_alpha": 0.30,
                "strength_taylor_G": 80.0,
                "strength_taylor_b": 0.248,
                "strength_taylor_rho": 1e13,
                "strength_ss_enabled": False,
                "strength_orowan_enabled": False,
                "strength_other_enabled": False,
                "strength_sum_rule": "Линейная сумма",
                "strength_example_loaded": True,
                "strength_input_provenance": (
                    "SYNTHETIC_EDUCATIONAL_DEMO_NOT_MATERIAL_INPUT"
                ),
                "strength_input_confirmation": True,
            }
        )
        st.rerun()

    if st.session_state.get("strength_example_loaded"):
        st.info(
            "Загружены демонстрационные числа из методического примера. "
            "Они показывают работу формул и не являются прогнозом марки стали."
        )

    sigma_internal = st.number_input(
        "Базовое внутреннее сопротивление σ_int, МПа",
        min_value=0.0,
        step=10.0,
        key="strength_sigma_internal",
    )

    with st.expander("Hall–Petch — влияние размера зерна"):
        hp_enabled = st.checkbox(
            "Учитывать Hall–Petch",
            key="strength_hp_enabled",
        )
        hp_k = st.number_input(
            "k_y, МПа·м^1/2",
            min_value=0.0,
            format="%.6f",
            key="strength_hp_k",
        )
        hp_d = st.number_input(
            "Средний размер зерна d, мкм",
            min_value=0.001,
            format="%.6f",
            key="strength_hp_d",
        )
        st.caption("Формула: Δσ_HP = k_y / √d. Коэффициент k_y зависит от сплава и состояния.")

    with st.expander("Taylor — дислокационное упрочнение"):
        taylor_enabled = st.checkbox(
            "Учитывать Taylor",
            key="strength_taylor_enabled",
        )
        taylor_m = st.number_input(
            "Taylor factor M",
            min_value=0.01,
            format="%.6f",
            key="strength_taylor_M",
        )
        taylor_alpha = st.number_input(
            "Коэффициент взаимодействия α",
            min_value=0.001,
            format="%.6f",
            key="strength_taylor_alpha",
        )
        taylor_g = st.number_input(
            "Модуль сдвига G, ГПа",
            min_value=0.0,
            format="%.6f",
            key="strength_taylor_G",
        )
        taylor_b = st.number_input(
            "Вектор Бюргерса b, нм",
            min_value=0.0001,
            format="%.6f",
            key="strength_taylor_b",
        )
        taylor_rho = st.number_input(
            "Плотность дислокаций ρ_d, м⁻²",
            min_value=1.0,
            format="%.6g",
            key="strength_taylor_rho",
        )
        st.caption("Формула: Δσ_dis = M α G b √ρ_d.")

    with st.expander("Твёрдорастворное упрочнение"):
        ss_enabled = st.checkbox(
            "Учитывать внешний твёрдорастворный вклад",
            key="strength_ss_enabled",
        )
        ss_value = st.number_input(
            "Δσ_ss, МПа",
            min_value=0.0,
            step=10.0,
            key="strength_ss_value",
        )
        ss_source = st.text_input(
            "Источник коэффициентов / модели",
            key="strength_ss_source",
        )
        st.caption(
            "Коэффициенты Fleischer/Labusch не универсальны. ThermoGar принимает "
            "только уже рассчитанный или калиброванный вклад."
        )

    with st.expander("Orowan — обход несрезаемых частиц"):
        orowan_enabled = st.checkbox(
            "Учитывать Orowan",
            key="strength_orowan_enabled",
        )
        orowan_m = st.number_input(
            "Taylor factor M для Orowan",
            min_value=0.01,
            format="%.6f",
            key="strength_orowan_M",
        )
        orowan_g = st.number_input(
            "Модуль сдвига матрицы G, ГПа",
            min_value=0.0,
            format="%.6f",
            key="strength_orowan_G",
        )
        orowan_b = st.number_input(
            "Вектор Бюргерса b, нм",
            min_value=0.0001,
            format="%.6f",
            key="strength_orowan_b",
        )
        orowan_nu = st.number_input(
            "Коэффициент Пуассона ν",
            min_value=-0.99,
            max_value=0.499,
            format="%.6f",
            key="strength_orowan_nu",
        )
        orowan_r = st.number_input(
            "Средний радиус частиц r, нм",
            min_value=0.0001,
            format="%.6f",
            key="strength_orowan_r",
        )
        orowan_lambda = st.number_input(
            "Межчастичное расстояние λ, нм",
            min_value=0.0001,
            format="%.6f",
            key="strength_orowan_lambda",
        )
        st.caption(
            "Формула применима к несрезаемым частицам. Для когерентных частиц "
            "может требоваться модель перерезания."
        )

    with st.expander("Другой калиброванный вклад"):
        other_enabled = st.checkbox(
            "Учитывать дополнительный вклад",
            key="strength_other_enabled",
        )
        other_value = st.number_input(
            "Дополнительный вклад, МПа",
            min_value=0.0,
            step=10.0,
            key="strength_other_value",
        )
        other_source = st.text_input(
            "Что это и откуда взято",
            key="strength_other_source",
        )

    summation_rule = st.selectbox(
        "Правило объединения вкладов",
        options=[
            "Не суммировать",
            "Линейная сумма",
            "Квадратичное объединение вкладов",
        ],
        key="strength_sum_rule",
    )

    input_provenance = st.text_area(
        "Источник и применимость всех коэффициентов (обязательно)",
        placeholder=(
            "DOI/таблица/страница либо SYNTHETIC/DECLARED_SCENARIO; укажите "
            "материал, состояние и температуру применимости"
        ),
        key="strength_input_provenance",
    )
    input_confirmation = st.checkbox(
        "Подтверждаю: это прозрачные вклады, не прогноз прочности материала",
        key="strength_input_confirmation",
    )
    strengthening_ready = bool(input_provenance.strip()) and bool(input_confirmation)
    if not strengthening_ready:
        st.info("Расчёт заблокирован до заполнения источника и подтверждения границы.")

    if release_calculation_button(
        "Рассчитать вклады упрочнения",
        type="primary",
        key="strengthening_calculate",
        disabled=not strengthening_ready,
    ):
        try:
            result = calculate_strengthening(
                input_provenance=input_provenance.strip(),
                input_confirmation=input_confirmation,
                sigma_internal_mpa=float(sigma_internal),
                hall_petch=(
                    {
                        "k_y_mpa_sqrt_m": float(hp_k),
                        "grain_size_um": float(hp_d),
                    }
                    if hp_enabled
                    else None
                ),
                taylor=(
                    {
                        "taylor_factor": float(taylor_m),
                        "alpha": float(taylor_alpha),
                        "shear_gpa": float(taylor_g),
                        "burgers_nm": float(taylor_b),
                        "dislocation_density_m2": float(taylor_rho),
                    }
                    if taylor_enabled
                    else None
                ),
                solid_solution_mpa=float(ss_value) if ss_enabled else None,
                orowan=(
                    {
                        "taylor_factor": float(orowan_m),
                        "shear_gpa": float(orowan_g),
                        "burgers_nm": float(orowan_b),
                        "poisson": float(orowan_nu),
                        "particle_radius_nm": float(orowan_r),
                        "spacing_nm": float(orowan_lambda),
                    }
                    if orowan_enabled
                    else None
                ),
                other_mpa=float(other_value) if other_enabled else None,
                summation_rule=summation_rule,
            )
            assumptions = pd.DataFrame(
                [
                    ("Базовый уровень, МПа", sigma_internal),
                    ("Hall–Petch", hp_enabled),
                    ("Taylor", taylor_enabled),
                    ("Твёрдый раствор", ss_enabled),
                    ("Источник твёрдого раствора", ss_source),
                    ("Orowan", orowan_enabled),
                    ("Другой вклад", other_enabled),
                    ("Источник другого вклада", other_source),
                    ("Правило суммирования", summation_rule),
                    ("Источник и применимость входов", input_provenance.strip()),
                    ("Research-only подтверждение", input_confirmation),
                    ("Схема результата", ELASTIC_RESULT_SCHEMA_VERSION),
                ],
                columns=["Параметр", "Значение"],
            )
            figure = _strengthening_figure(
                result.contribution_table,
                theme_type,
            )
            st.session_state["strengthening_result"] = {
                "result": result,
                "assumptions": assumptions,
                "figure": figure,
            }
            record_history(
                paths,
                "Вклады упрочнения",
                current_context,
                {
                    "summation_rule": summation_rule,
                    "total_mpa": result.total_mpa,
                    "mechanism_count": int(len(result.contribution_table)),
                    "educational_example": bool(
                        st.session_state.get("strength_example_loaded")
                    ),
                },
            )
        except Exception as error:
            render_error(error, context="вклады упрочнения")

    state = st.session_state.get("strengthening_result")
    if not isinstance(state, dict):
        return

    result: StrengtheningResult = state["result"]
    if result.total_mpa is None:
        st.info(
            "Отдельные вклады рассчитаны. Итог не сформирован, потому что "
            "выбрано «Не суммировать»."
        )
    else:
        st.metric(
            "Механизм-ориентированная оценка, МПа",
            f"{result.total_mpa:.2f}",
        )
        st.warning(
            "Это не автоматически валидированный предел текучести и не UTS. "
            "Результат действителен только при заданных коэффициентах, "
            "микроструктуре и выбранном правиле объединения."
        )

    for warning in result.warnings:
        st.warning(warning)
    st.pyplot(state["figure"])
    st.dataframe(
        result.contribution_table,
        width="stretch",
        hide_index=True,
    )

    excel = dataframe_to_excel(
        {
            "Исходные данные": state["assumptions"],
            "Вклады": result.contribution_table,
        }
    )
    download1, download2 = st.columns(2)
    with download1:
        release_download_button(
            "Скачать Excel",
            data=excel,
            file_name="ThermoGar_strengthening_contributions.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
    with download2:
        release_download_button(
            "Скачать PNG",
            data=figure_to_png(state["figure"]),
            file_name="ThermoGar_strengthening_contributions.png",
            mime="image/png",
        )
