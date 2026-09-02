"""Fail-closed NE-04 Fe diagnostic-domain side-car.

This module is deliberately not imported by the release UI or the central
NE-04 v3 evaluator.  It machine-checks only the composition and temperature
limits printed in the pinned mc_fe 2.062 source header.  It never authorizes
execution, release, production use, pressure, or a scientific/material claim.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from numbers import Real
from pathlib import Path, PurePosixPath
import stat
from typing import Any


CONTRACT_SCHEMA = "SWR-NE04-FE-DIAGNOSTIC-DOMAIN-4"
REPORT_SCHEMA = "SWR-NE04-FE-DIAGNOSTIC-REPORT-1"
CONTRACT_CLAIM = "DIAGNOSTIC_DOMAIN_ONLY_NOT_NE04_ACCEPTANCE"
EXPECTED_CONFIG_SHA256 = (
    "d0397897e8661d54b67fc6b4ae8897481854062f125a10bd36d2358342dcdd48"
)
DEFAULT_CONFIG_RELATIVE_PATH = Path("configs/ne04_fe_diagnostic_domain_v4.json")

MASS_FRACTION = "MASS_FRACTION"
DATABASE_KEY = "fe"
PRESSURE_STATUS = "UNKNOWN_BLOCKED"
SOURCE_SEMANTIC = "DATABASE_OPTIMISED_INSIDE_LIMITS"
TEMPERATURE_MINIMUM_K = 673.0
TEMPERATURE_MAXIMUM_K = 2000.0
FRACTION_SUM_TOLERANCE = 1.0e-12

DIAGNOSTIC_NOT_RELEASED = "NE04_FE_DIAGNOSTIC_NOT_RELEASED"
PRESSURE_DOMAIN_UNKNOWN = "NE04_PRESSURE_DOMAIN_UNKNOWN"
LEGAL_REVIEW_OPEN = "NE04_FE_LEGAL_REVIEW_OPEN"
UPSTREAM_CONFIRMATION_OPEN = "NE04_FE_UPSTREAM_CONFIRMATION_OPEN"
RUNTIME_REPLAY_NOT_SEALED = "NE04_FE_RUNTIME_REPLAY_NOT_SEALED"
SIDECAR_NOT_INTEGRATED = "NE04_FE_SIDECAR_NOT_INTEGRATED"
PROVENANCE_INVALID = "NE04_FE_PROVENANCE_INVALID"
CONFIG_INVALID = "NE04_FE_CONFIG_INVALID"
PROFILE_INVALID = "NE04_FE_PROFILE_INVALID"
COMPOSITION_BASIS_UNSUPPORTED = "NE04_FE_COMPOSITION_BASIS_UNSUPPORTED"
COMPOSITION_INPUT_INVALID = "NE04_FE_COMPOSITION_INPUT_INVALID"
COMPOSITION_OUTSIDE_SOURCE_DOMAIN = (
    "NE04_FE_COMPOSITION_OUTSIDE_SOURCE_DOMAIN"
)
TEMPERATURE_INPUT_INVALID = "NE04_FE_TEMPERATURE_INPUT_INVALID"
TEMPERATURE_OUTSIDE_SOURCE_DOMAIN = (
    "NE04_FE_TEMPERATURE_OUTSIDE_SOURCE_DOMAIN"
)
PRESSURE_REQUEST_INVALID = "NE04_FE_PRESSURE_REQUEST_INVALID"

MANDATORY_REASON_CODES = (
    DIAGNOSTIC_NOT_RELEASED,
    PRESSURE_DOMAIN_UNKNOWN,
    LEGAL_REVIEW_OPEN,
    UPSTREAM_CONFIRMATION_OPEN,
    RUNTIME_REPLAY_NOT_SEALED,
    SIDECAR_NOT_INTEGRATED,
)

REGISTERED_REASON_CODES = frozenset(
    {
        *MANDATORY_REASON_CODES,
        PROVENANCE_INVALID,
        CONFIG_INVALID,
        PROFILE_INVALID,
        COMPOSITION_BASIS_UNSUPPORTED,
        COMPOSITION_INPUT_INVALID,
        COMPOSITION_OUTSIDE_SOURCE_DOMAIN,
        TEMPERATURE_INPUT_INVALID,
        TEMPERATURE_OUTSIDE_SOURCE_DOMAIN,
        PRESSURE_REQUEST_INVALID,
    }
)

PROFILE_KEYS = ("thermogar_patch", "upstream_original")

STRICT_UPPER_BOUNDS_WT_PERCENT = {
    "AL": 3.0,
    "B": 0.5,
    "C": 0.5,
    "CO": 3.0,
    "CR": 25.0,
    "CU": 1.0,
    "H": 0.1,
    "HF": 0.5,
    "LA": 0.5,
    "MN": 25.0,
    "MO": 5.0,
    "N": 1.0,
    "NB": 1.0,
    "NI": 26.0,
    "O": 0.5,
    "P": 0.05,
    "PD": 4.0,
    "S": 0.1,
    "SI": 3.5,
    "TA": 0.5,
    "TI": 0.5,
    "V": 0.5,
    "W": 3.0,
    "Y": 0.5,
}
COMPLETE_ELEMENTS = frozenset({"FE", *STRICT_UPPER_BOUNDS_WT_PERCENT})

EXPECTED_HEADER_LINE_NUMBERS = (59, 60, 61, 62, 63, 64)
EXPECTED_HEADER_LINES = (
    "$ This database has been optimised inside the following limits:",
    "$ Temperature: 673 K - 2000 K",
    "$",
    "$ Alloy composition (wt.%): Al<3  B<0.5  C<0.5  Co<3  Cr<25  Cu<1  H<0.1 Hf<0.5  ",
    "$ La<0.5  Mn<25  Mo<5  N<1  Nb<1  Ni<26  O<0.5  P<0.05  Pd<4  S<0.1  Si<3.5  ",
    "$ Ta<0.5 Ti<0.5  V<0.5  W<3  Y<0.5 ",
)

EXPECTED_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "gate",
        "status",
        "claim",
        "calculations_enabled",
        "production_use",
        "release_eligible",
        "database_key",
        "release_disposition",
        "integration",
        "provenance",
        "domain",
        "mandatory_report_reason_codes",
        "reason_code_registry",
    }
)


class DuplicateJsonKeyError(ValueError):
    """Raised when a side-car JSON object repeats a key."""


class SidecarContractError(ValueError):
    """Raised when the side-car contract or pinned provenance is invalid."""


@dataclass(frozen=True, slots=True)
class FeDiagnosticRequest:
    """Complete canonical Fe diagnostic-domain request.

    ``composition`` must contain all 25 configured elements, including a
    positive Fe balance, in MASS_FRACTION.  No mole/mass conversion occurs in
    this side-car.
    """

    profile_key: object
    composition: object
    composition_basis: object
    temperature_min_k: object
    temperature_max_k: object
    pressure_pa: object


@dataclass(frozen=True, slots=True)
class FeDiagnosticReport:
    """Immutable diagnostic report; deliberately has no generic ALLOW field."""

    profile_key: str
    source_evidence_valid: bool
    composition_in_source_domain: bool
    temperature_in_source_domain: bool
    composition_temperature_in_source_domain: bool
    reason_codes: tuple[str, ...]

    def __getattribute__(self, name: str) -> Any:
        if name == "schema_version":
            return "SWR-NE04-FE-DIAGNOSTIC-REPORT-1"
        if name == "report_kind":
            return "DIAGNOSTIC_BLOCKED_REPORT"
        if name == "claim":
            return "DIAGNOSTIC_DOMAIN_ONLY_NOT_NE04_ACCEPTANCE"
        if name == "production_use":
            return "DENIED"
        if name == "database_key":
            return "fe"
        if name == "pressure_domain_status":
            return "UNKNOWN_BLOCKED"
        if name in {"execution_eligible", "release_eligible"}:
            return False
        return object.__getattribute__(self, name)

    def _validate_invariants(self) -> None:
        boolean_fields = (
            self.source_evidence_valid,
            self.composition_in_source_domain,
            self.temperature_in_source_domain,
            self.composition_temperature_in_source_domain,
        )
        if type(self.profile_key) is not str or any(
            type(value) is not bool for value in boolean_fields
        ):
            raise TypeError("diagnostic report fields have invalid types")
        if type(self.reason_codes) is not tuple or not all(
            type(code) is str for code in self.reason_codes
        ):
            raise TypeError("diagnostic reason codes must be a tuple of strings")
        if (
            self.reason_codes[: len(MANDATORY_REASON_CODES)]
            != MANDATORY_REASON_CODES
        ):
            raise ValueError("mandatory diagnostic reason prefix is absent or reordered")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("diagnostic reason codes must be unique")
        if not set(self.reason_codes).issubset(REGISTERED_REASON_CODES):
            raise ValueError("diagnostic report contains an unregistered reason code")
        reasons = set(self.reason_codes)
        profile_valid = self.profile_key in PROFILE_KEYS
        if profile_valid == (PROFILE_INVALID in reasons):
            raise ValueError("profile identity and PROFILE_INVALID reason disagree")
        if not self.source_evidence_valid:
            if PROVENANCE_INVALID not in reasons:
                raise ValueError("invalid source evidence requires PROVENANCE_INVALID")
            if any(boolean_fields[1:]):
                raise ValueError("invalid source evidence cannot yield an in-domain flag")
        elif PROVENANCE_INVALID in reasons or CONFIG_INVALID in reasons:
            raise ValueError("valid source evidence forbids provenance/config failure reasons")

        composition_failures = {
            COMPOSITION_BASIS_UNSUPPORTED,
            COMPOSITION_INPUT_INVALID,
            COMPOSITION_OUTSIDE_SOURCE_DOMAIN,
        }
        composition_has_failure = bool(reasons & composition_failures)
        if self.composition_in_source_domain and composition_has_failure:
            raise ValueError("composition flag conflicts with a composition failure reason")
        if (
            self.source_evidence_valid
            and not self.composition_in_source_domain
            and not composition_has_failure
        ):
            raise ValueError("rejected composition requires a composition failure reason")

        temperature_failures = {
            TEMPERATURE_INPUT_INVALID,
            TEMPERATURE_OUTSIDE_SOURCE_DOMAIN,
        }
        temperature_has_failure = bool(reasons & temperature_failures)
        if self.temperature_in_source_domain and temperature_has_failure:
            raise ValueError("temperature flag conflicts with a temperature failure reason")
        if (
            self.source_evidence_valid
            and not self.temperature_in_source_domain
            and not temperature_has_failure
        ):
            raise ValueError("rejected temperature requires a temperature failure reason")

        if self.composition_temperature_in_source_domain and not all(
            (*boolean_fields[:3], profile_valid)
        ):
            raise ValueError(
                "combined domain flag requires valid source, composition, temperature, and profile"
            )

    def __post_init__(self) -> None:
        self._validate_invariants()

    def as_dict(self) -> dict[str, Any]:
        self._validate_invariants()
        return {
            "schema_version": "SWR-NE04-FE-DIAGNOSTIC-REPORT-1",
            "report_kind": "DIAGNOSTIC_BLOCKED_REPORT",
            "claim": "DIAGNOSTIC_DOMAIN_ONLY_NOT_NE04_ACCEPTANCE",
            "production_use": "DENIED",
            "database_key": "fe",
            "profile_key": self.profile_key,
            "source_evidence_valid": self.source_evidence_valid,
            "composition_in_source_domain": self.composition_in_source_domain,
            "temperature_in_source_domain": self.temperature_in_source_domain,
            "composition_temperature_in_source_domain": (
                self.composition_temperature_in_source_domain
            ),
            "pressure_domain_status": "UNKNOWN_BLOCKED",
            "execution_eligible": False,
            "release_eligible": False,
            "reason_codes": list(self.reason_codes),
        }


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_json_constant(token: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {token}")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_symlink_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _resolve_pinned_file(project_root: Path, relative_value: object) -> Path:
    if not isinstance(relative_value, str) or not relative_value:
        raise SidecarContractError("pinned path is absent")
    if "\\" in relative_value or "\x00" in relative_value:
        raise SidecarContractError("pinned path is not canonical POSIX")
    relative = PurePosixPath(relative_value)
    if (
        relative.is_absolute()
        or relative.as_posix() != relative_value
        or any(part in {"", ".", ".."} or ":" in part for part in relative.parts)
    ):
        raise SidecarContractError("pinned path is not a safe relative path")

    root = project_root.expanduser().resolve(strict=True)
    candidate = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if _is_symlink_or_reparse(current):
            raise SidecarContractError("pinned path crosses a symlink/reparse point")
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise SidecarContractError("pinned path escapes the project root") from error
    if not resolved.is_file() or _is_symlink_or_reparse(resolved):
        raise SidecarContractError("pinned path is not a regular file")
    return resolved


def _read_contract(path: Path) -> dict[str, Any]:
    if not path.is_file() or _is_symlink_or_reparse(path):
        raise SidecarContractError("side-car config is not a regular file")
    payload = path.read_bytes()
    if len(payload) > 512 * 1024:
        raise SidecarContractError("side-car config exceeds the bounded size")
    try:
        text = payload.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise SidecarContractError("side-car config is not strict UTF-8 JSON") from error
    if type(value) is not dict or set(value) != EXPECTED_TOP_LEVEL_KEYS:
        raise SidecarContractError("side-car top-level schema mismatch")
    if _sha256_bytes(payload) != EXPECTED_CONFIG_SHA256:
        raise SidecarContractError("side-car config SHA-256 mismatch")
    if (
        value.get("schema_version") != CONTRACT_SCHEMA
        or value.get("gate") != "NE-04"
        or value.get("status")
        != "SIDE_CAR_STATIC_DIAGNOSTIC_ONLY_NOT_INTEGRATED"
        or value.get("claim") != CONTRACT_CLAIM
        or value.get("calculations_enabled") is not False
        or value.get("production_use") != "DENIED"
        or value.get("release_eligible") is not False
        or value.get("database_key") != DATABASE_KEY
        or value.get("release_disposition") != "DIAGNOSTIC_ONLY"
        or value.get("mandatory_report_reason_codes")
        != list(MANDATORY_REASON_CODES)
    ):
        raise SidecarContractError("side-car safety identity mismatch")
    registry = value.get("reason_code_registry")
    if (
        type(registry) is not dict
        or set(registry) != REGISTERED_REASON_CODES
        or not all(type(text) is str and text.strip() for text in registry.values())
    ):
        raise SidecarContractError("side-car reason registry mismatch")
    return value


def _verify_file_entry(project_root: Path, entry: object) -> Path:
    if type(entry) is not dict:
        raise SidecarContractError("pinned file entry is not an object")
    relative = entry.get("relative_path")
    expected_hash = entry.get("sha256")
    expected_size = entry.get("bytes")
    if (
        type(expected_hash) is not str
        or len(expected_hash) != 64
        or any(character not in "0123456789abcdef" for character in expected_hash)
        or type(expected_size) is not int
        or expected_size < 0
    ):
        raise SidecarContractError("pinned file hash/size identity is invalid")
    path = _resolve_pinned_file(project_root, relative)
    before_size = path.stat().st_size
    actual_hash = _sha256_file(path)
    after_size = path.stat().st_size
    if before_size != expected_size or after_size != expected_size:
        raise SidecarContractError("pinned file size mismatch")
    if actual_hash != expected_hash:
        raise SidecarContractError("pinned file SHA-256 mismatch")
    return path


def _validate_contract_semantics(contract: Mapping[str, Any]) -> None:
    integration = contract.get("integration")
    if type(integration) is not dict or integration != {
        "central_contract_integration": False,
        "release_ui_callsite_bound": False,
        "status": "DEFERRED_PIN_ROTATION_REQUIRED",
        "observed_central_v3_relative_path": "configs/ne04_database_domains.json",
        "observed_central_v3_sha256": (
            "2d588fe38a0f7c2c746b60e49d0c029a17721665400290233a0a22ec79db7204"
        ),
    }:
        raise SidecarContractError("side-car integration boundary mismatch")

    domain = contract.get("domain")
    if type(domain) is not dict or set(domain) != {
        "composition",
        "temperature_k",
        "pressure_pa",
        "g_function_temperature_observation",
    }:
        raise SidecarContractError("side-car domain schema mismatch")
    composition = domain["composition"]
    if (
        type(composition) is not dict
        or composition.get("status")
        != "SOURCE_HEADER_LIMITS_MACHINE_ENFORCED_DIAGNOSTIC_ONLY"
        or composition.get("source_semantic") != SOURCE_SEMANTIC
        or composition.get("request_basis") != MASS_FRACTION
        or composition.get("source_limit_unit") != "WT_PERCENT"
        or composition.get("no_implicit_mole_mass_conversion") is not True
        or composition.get("complete_element_set_required") is not True
        or composition.get("balance_element") != "FE"
        or composition.get("balance_minimum_exclusive") != 0.0
        or composition.get("balance_maximum") is not None
        or composition.get("fraction_sum") != 1.0
        or composition.get("fraction_sum_absolute_tolerance")
        != FRACTION_SUM_TOLERANCE
        or composition.get("strict_upper_operator") != "<"
        or composition.get("strict_upper_bounds_wt_percent")
        != STRICT_UPPER_BOUNDS_WT_PERCENT
    ):
        raise SidecarContractError("side-car composition semantics mismatch")

    temperature = domain["temperature_k"]
    if (
        type(temperature) is not dict
        or temperature.get("status")
        != "SOURCE_HEADER_LIMITS_MACHINE_ENFORCED_DIAGNOSTIC_ONLY"
        or temperature.get("source_semantic") != SOURCE_SEMANTIC
        or temperature.get("minimum") != TEMPERATURE_MINIMUM_K
        or temperature.get("maximum") != TEMPERATURE_MAXIMUM_K
        or temperature.get("minimum_inclusive") is not True
        or temperature.get("maximum_inclusive") is not True
    ):
        raise SidecarContractError("side-car temperature semantics mismatch")

    pressure = domain["pressure_pa"]
    if pressure != {
        "status": PRESSURE_STATUS,
        "minimum": None,
        "maximum": None,
        "positive_finite_request_required": True,
    }:
        raise SidecarContractError("side-car pressure must remain UNKNOWN_BLOCKED")

    g_observation = domain["g_function_temperature_observation"]
    if g_observation != {
        "minimum": 273.0,
        "maximum": 6000.0,
        "accepted_as_database_domain": False,
        "semantic": "G_FUNCTION_EXPRESSION_LIMIT_NOT_DATABASE_OPTIMISATION_DOMAIN",
    }:
        raise SidecarContractError("G-function limits were promoted into a domain")


def _validate_source_evidence(project_root: Path, contract: Mapping[str, Any]) -> None:
    _validate_contract_semantics(contract)
    provenance = contract.get("provenance")
    if type(provenance) is not dict or set(provenance) != {
        "thermodynamic_source",
        "mobility_source",
        "profiles",
        "artifacts",
    }:
        raise SidecarContractError("side-car provenance schema mismatch")

    source = provenance["thermodynamic_source"]
    if (
        type(source) is not dict
        or source.get("version") != "2.062"
        or source.get("exact_ascii_header_line_numbers")
        != list(EXPECTED_HEADER_LINE_NUMBERS)
        or source.get("exact_ascii_header_lines") != list(EXPECTED_HEADER_LINES)
    ):
        raise SidecarContractError("thermodynamic source/header pin mismatch")
    source_path = _verify_file_entry(project_root, source)
    raw_lines = source_path.read_bytes().splitlines()
    try:
        observed_lines = tuple(
            raw_lines[line_number - 1].decode("ascii")
            for line_number in EXPECTED_HEADER_LINE_NUMBERS
        )
    except (IndexError, UnicodeDecodeError) as error:
        raise SidecarContractError("source header lines are not exact ASCII") from error
    if observed_lines != EXPECTED_HEADER_LINES:
        raise SidecarContractError("source header lines differ from the pin")
    if _sha256_file(source_path) != source["sha256"]:
        raise SidecarContractError("thermodynamic source changed during validation")

    mobility = provenance["mobility_source"]
    if type(mobility) is not dict or mobility.get("version") != "2.016":
        raise SidecarContractError("mobility source version pin mismatch")
    _verify_file_entry(project_root, mobility)

    profiles = provenance["profiles"]
    if type(profiles) is not dict or tuple(profiles) != PROFILE_KEYS:
        raise SidecarContractError("diagnostic profile registry mismatch")
    observed_identities: set[tuple[str, str]] = set()
    for profile_key in PROFILE_KEYS:
        entry = profiles[profile_key]
        if type(entry) is not dict:
            raise SidecarContractError("diagnostic profile entry is invalid")
        path = _verify_file_entry(project_root, entry)
        observed_identities.add((str(path), str(entry.get("sha256"))))
    if len(observed_identities) != 2:
        raise SidecarContractError("patched and upstream profile identities coincide")
    if (
        profiles["thermogar_patch"].get("role")
        != "PATCHED_DIAGNOSTIC_ONLY"
        or profiles["thermogar_patch"].get("patch_id")
        != "TG-FE-2062-C15-001"
        or profiles["thermogar_patch"].get("upstream_confirmation")
        != "PENDING_CONFIRMATION"
        or profiles["upstream_original"].get("role")
        != "UPSTREAM_CONTROL_DIAGNOSTIC_ONLY"
        or profiles["upstream_original"].get("patch_id") is not None
        or profiles["upstream_original"].get("upstream_confirmation")
        != "SOURCE_CONTROL_NOT_ACCEPTED_OUTPUT"
    ):
        raise SidecarContractError("diagnostic profile safety roles mismatch")

    artifacts = provenance["artifacts"]
    if (
        not isinstance(artifacts, Sequence)
        or isinstance(artifacts, (str, bytes, bytearray))
        or len(artifacts) != 7
    ):
        raise SidecarContractError("diagnostic artifact registry mismatch")
    roles: set[str] = set()
    for entry in artifacts:
        if type(entry) is not dict or type(entry.get("role")) is not str:
            raise SidecarContractError("diagnostic artifact entry is invalid")
        role = entry["role"]
        if role in roles:
            raise SidecarContractError("duplicate diagnostic artifact role")
        roles.add(role)
        _verify_file_entry(project_root, entry)


def _finite_real(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _validate_composition(
    value: object,
    basis_value: object,
    reasons: set[str],
) -> tuple[bool, bool]:
    basis_valid = type(basis_value) is str and basis_value == MASS_FRACTION
    if not basis_valid:
        reasons.add(COMPOSITION_BASIS_UNSUPPORTED)

    if type(value) is not dict:
        reasons.add(COMPOSITION_INPUT_INVALID)
        return False, False

    normalized: dict[str, float] = {}
    structure_valid = True
    for raw_element, raw_fraction in value.items():
        if type(raw_element) is not str or not raw_element:
            structure_valid = False
            continue
        element = raw_element.strip().upper()
        if (
            not element
            or element in normalized
            or element == "VA"
            or element not in COMPLETE_ELEMENTS
        ):
            structure_valid = False
        fraction = _finite_real(raw_fraction)
        if fraction is None or fraction < 0.0:
            structure_valid = False
            continue
        normalized[element] = fraction

    if set(normalized) != COMPLETE_ELEMENTS:
        structure_valid = False
    if normalized.get("FE", 0.0) <= 0.0:
        structure_valid = False
    total = sum(normalized.values())
    if not math.isclose(
        total,
        1.0,
        rel_tol=0.0,
        abs_tol=FRACTION_SUM_TOLERANCE,
    ):
        structure_valid = False
    if not structure_valid:
        reasons.add(COMPOSITION_INPUT_INVALID)
        return False, False

    within = all(
        normalized[element] < upper / 100.0
        for element, upper in STRICT_UPPER_BOUNDS_WT_PERCENT.items()
    )
    if not within:
        reasons.add(COMPOSITION_OUTSIDE_SOURCE_DOMAIN)
    return basis_valid, within


def _validate_temperature(
    minimum_value: object,
    maximum_value: object,
    reasons: set[str],
) -> tuple[bool, bool]:
    minimum = _finite_real(minimum_value)
    maximum = _finite_real(maximum_value)
    structurally_valid = not (
        minimum is None
        or maximum is None
        or minimum <= 0.0
        or maximum < minimum
    )
    if not structurally_valid:
        reasons.add(TEMPERATURE_INPUT_INVALID)
        return False, False
    within = bool(
        TEMPERATURE_MINIMUM_K <= minimum
        and maximum <= TEMPERATURE_MAXIMUM_K
    )
    if not within:
        reasons.add(TEMPERATURE_OUTSIDE_SOURCE_DOMAIN)
    return True, within


def _validate_pressure(value: object, reasons: set[str]) -> bool:
    pressure = _finite_real(value)
    valid = pressure is not None and pressure > 0.0
    if not valid:
        reasons.add(PRESSURE_REQUEST_INVALID)
    return valid


def _ordered_reasons(reasons: set[str]) -> tuple[str, ...]:
    mandatory = list(MANDATORY_REASON_CODES)
    return tuple(mandatory + sorted(reasons - set(mandatory)))


def _report(
    request: FeDiagnosticRequest,
    *,
    source_valid: bool,
    composition_valid: bool,
    temperature_valid: bool,
    combined_valid: bool,
    reasons: set[str],
) -> FeDiagnosticReport:
    profile_key = request.profile_key if type(request.profile_key) is str else ""
    if profile_key not in PROFILE_KEYS:
        reasons.add(PROFILE_INVALID)
    return FeDiagnosticReport(
        profile_key=profile_key,
        source_evidence_valid=bool(source_valid),
        composition_in_source_domain=bool(composition_valid),
        temperature_in_source_domain=bool(temperature_valid),
        composition_temperature_in_source_domain=bool(combined_valid),
        reason_codes=_ordered_reasons(reasons),
    )


def evaluate_fe_diagnostic_domain(
    project_root: str | Path,
    request: FeDiagnosticRequest,
    *,
    config_path: str | Path | None = None,
) -> FeDiagnosticReport:
    """Evaluate source-backed Fe composition/T limits and always fail release shut."""

    if not isinstance(request, FeDiagnosticRequest):
        raise TypeError("request must be FeDiagnosticRequest")
    root = Path(project_root).expanduser().resolve()
    if config_path is None:
        path = root / DEFAULT_CONFIG_RELATIVE_PATH
    else:
        supplied_path = Path(config_path).expanduser()
        path = supplied_path if supplied_path.is_absolute() else Path.cwd() / supplied_path
    reasons = set(MANDATORY_REASON_CODES)
    try:
        contract = _read_contract(path)
    except Exception:
        reasons.update({CONFIG_INVALID, PROVENANCE_INVALID})
        return _report(
            request,
            source_valid=False,
            composition_valid=False,
            temperature_valid=False,
            combined_valid=False,
            reasons=reasons,
        )
    try:
        _validate_source_evidence(root, contract)
    except Exception:
        reasons.add(PROVENANCE_INVALID)
        return _report(
            request,
            source_valid=False,
            composition_valid=False,
            temperature_valid=False,
            combined_valid=False,
            reasons=reasons,
        )

    profile_valid = type(request.profile_key) is str and request.profile_key in PROFILE_KEYS
    if not profile_valid:
        reasons.add(PROFILE_INVALID)
    basis_valid, composition_within = _validate_composition(
        request.composition,
        request.composition_basis,
        reasons,
    )
    temperature_input_valid, temperature_within = _validate_temperature(
        request.temperature_min_k,
        request.temperature_max_k,
        reasons,
    )
    _validate_pressure(request.pressure_pa, reasons)

    composition_valid = bool(basis_valid and composition_within)
    combined = bool(
        profile_valid
        and composition_valid
        and temperature_input_valid
        and temperature_within
    )
    return _report(
        request,
        source_valid=True,
        composition_valid=composition_valid,
        temperature_valid=bool(temperature_input_valid and temperature_within),
        combined_valid=combined,
        reasons=reasons,
    )


__all__ = [
    "COMPLETE_ELEMENTS",
    "CONTRACT_CLAIM",
    "CONTRACT_SCHEMA",
    "EXPECTED_CONFIG_SHA256",
    "FeDiagnosticReport",
    "FeDiagnosticRequest",
    "MANDATORY_REASON_CODES",
    "MASS_FRACTION",
    "PROFILE_KEYS",
    "REGISTERED_REASON_CODES",
    "REPORT_SCHEMA",
    "STRICT_UPPER_BOUNDS_WT_PERCENT",
    "TEMPERATURE_MAXIMUM_K",
    "TEMPERATURE_MINIMUM_K",
    "evaluate_fe_diagnostic_domain",
]
