"""Fail-closed NE-04 domain evaluator for release numerical requests.

The evaluator is deliberately independent of Streamlit, pycalphad, NumPy and
the rest of the scientific runtime.  It authenticates the selected database,
validates the complete request shape and applies the machine-readable NE-04
contract.  Unknown or unaccepted domains never become permissive defaults.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from typing import Any


DECISION_SCHEMA = "SWR-NE04-DOMAIN-DECISION-1"
CONTRACT_SCHEMA = "SWR-NE04-DATABASE-DOMAINS-3"
MOLE_FRACTION = "MOLE_FRACTION"
MASS_FRACTION = "MASS_FRACTION"
COMPOSITION_BASES = frozenset({MOLE_FRACTION, MASS_FRACTION})

CONFIG_INVALID = "NE04_CONFIG_INVALID"
CALCULATIONS_DISABLED = "NE04_CALCULATIONS_DISABLED"
DECISION_REQUIRED = "NE04_DOMAIN_DECISION_REQUIRED"
FEATURE_ID_REQUIRED = "NE04_FEATURE_ID_REQUIRED"
COMPOSITION_REQUIRED = "NE04_COMPOSITION_REQUIRED"
COMPOSITION_BASIS_INVALID = "NE04_COMPOSITION_BASIS_INVALID"
COMPOSITION_ELEMENT_INVALID = "NE04_COMPOSITION_ELEMENT_INVALID"
COMPOSITION_VALUE_INVALID = "NE04_COMPOSITION_VALUE_INVALID"
COMPOSITION_TOTAL_INVALID = "NE04_COMPOSITION_TOTAL_INVALID"
TEMPERATURE_REQUEST_INVALID = "NE04_TEMPERATURE_REQUEST_INVALID"
PRESSURE_REQUEST_INVALID = "NE04_PRESSURE_REQUEST_INVALID"

_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
_PHASE_NAME = re.compile(r"(?is)^\s*PHASE\s+([A-Z0-9_:+-]+)(?:\s|$)")
_REFERENCE_MARKER = re.compile(
    r"(?im)^\s*LIST(?:_|\s+|-)+OF(?:_|\s+|-)+REFERENCES\b"
)


class DuplicateJsonKeyError(ValueError):
    """Raised when the domain contract repeats a JSON object key."""


@dataclass(frozen=True, slots=True)
class DomainRequest:
    """Complete numerical request at the release calculation boundary.

    ``composition`` contains the complete normalized alloy composition,
    including the configured balance element. Values are fractions in the
    basis named by ``composition_basis`` and must sum to one.
    """

    feature_id: object
    database_key: object
    composition: object
    composition_basis: object
    temperature_min_k: object
    temperature_max_k: object
    pressure_pa: object
    requested_phases: object
    excluded_phases: object


@dataclass(frozen=True, slots=True)
class DomainDecision:
    """Immutable result returned by :func:`evaluate_domain_request`."""

    allowed: bool
    reason_codes: tuple[str, ...]
    feature_id: str
    database_key: str
    effective_phases: tuple[str, ...]
    schema_version: str = DECISION_SCHEMA

    @property
    def decision(self) -> str:
        return "ALLOW" if self.allowed else "BLOCK"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "decision": self.decision,
            "allowed": self.allowed,
            "reason_codes": list(self.reason_codes),
            "feature_id": self.feature_id,
            "database_key": self.database_key,
            "effective_phases": list(self.effective_phases),
        }


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _load_contract(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8-sig"),
        object_pairs_hook=_strict_object,
    )
    if not isinstance(value, dict):
        raise ValueError("NE-04 contract root must be an object")
    if value.get("schema_version") != CONTRACT_SCHEMA:
        raise ValueError("unexpected NE-04 contract schema")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_contract_file(project_root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("database path is absent")
    posix = PurePosixPath(value)
    if posix.is_absolute() or ".." in posix.parts:
        raise ValueError("database path is not a safe relative path")
    root = project_root.resolve()
    candidate = root.joinpath(*posix.parts).resolve()
    candidate.relative_to(root)
    if not candidate.is_file() or candidate.is_symlink():
        raise ValueError("database path is not a regular in-tree file")
    return candidate


def _decode_file(path: Path) -> str:
    payload = path.read_bytes()
    for encoding in _ENCODINGS:
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"could not decode {path}")


def _strip_tdb_comments(text: str) -> str:
    return "\n".join(line.split("$", 1)[0] for line in text.splitlines())


def _command_keyword(command: str) -> str:
    match = re.match(r"\s*([A-Za-z_]+)", command)
    return match.group(1).upper() if match else ""


def _declared_phases(text: str) -> frozenset[str]:
    """Return only active, terminated PHASE commands before references."""

    active = _strip_tdb_comments(text)
    references = _REFERENCE_MARKER.search(active)
    if references:
        active = active[: references.start()]
    pieces = active.split("!")
    remainder = pieces.pop()
    if remainder.strip() and _command_keyword(remainder) == "PHASE":
        raise ValueError("unterminated active PHASE command")

    phases: set[str] = set()
    for command in pieces:
        command = command.strip()
        if not command or _command_keyword(command) != "PHASE":
            continue
        match = _PHASE_NAME.match(command)
        if not match:
            raise ValueError("malformed active PHASE command")
        phases.add(match.group(1).upper().split(":", 1)[0])
    return frozenset(phases)


def _phase_fingerprint(phases: frozenset[str]) -> str:
    payload = "".join(f"{name}\n" for name in sorted(phases)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_database_key(value: object) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def _normalize_phase_array(
    value: object,
) -> tuple[tuple[str, ...], bool, bool]:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
    ):
        return (), False, False
    normalized: list[str] = []
    valid = True
    for item in value:
        if not isinstance(item, str) or not item.strip():
            valid = False
            continue
        normalized.append(item.strip().upper())
    duplicate = len(normalized) != len(set(normalized))
    return tuple(normalized), valid, duplicate


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _validate_composition(
    value: object,
    basis_value: object,
    card: Mapping[str, Any],
    reasons: set[str],
) -> None:
    basis = _normalize_text(basis_value).upper()
    if basis not in COMPOSITION_BASES:
        reasons.add(COMPOSITION_BASIS_INVALID)

    if not isinstance(value, Mapping) or not value:
        reasons.add(COMPOSITION_REQUIRED)
        return

    elements = card.get("elements")
    if not isinstance(elements, Mapping):
        reasons.add(CONFIG_INVALID)
        return
    allowed = elements.get("allowed_user_elements")
    balance = elements.get("balance")
    if not isinstance(allowed, list) or not isinstance(balance, str):
        reasons.add(CONFIG_INVALID)
        return
    allowed_set = {str(item).upper() for item in allowed}
    balance = balance.upper()

    normalized: dict[str, float] = {}
    for raw_element, raw_value in value.items():
        if not isinstance(raw_element, str) or not raw_element.strip():
            reasons.add(COMPOSITION_ELEMENT_INVALID)
            continue
        element = raw_element.strip().upper()
        if element in normalized or element == "VA" or element not in allowed_set:
            reasons.add(COMPOSITION_ELEMENT_INVALID)
        number = _finite_number(raw_value)
        if number is None or number < 0.0 or number > 1.0:
            reasons.add(COMPOSITION_VALUE_INVALID)
            continue
        normalized[element] = number

    if balance not in normalized or normalized.get(balance, 0.0) <= 0.0:
        reasons.add(COMPOSITION_TOTAL_INVALID)
    total = sum(normalized.values())
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
        reasons.add(COMPOSITION_TOTAL_INVALID)

    composition = card.get("composition")
    if not isinstance(composition, Mapping):
        reasons.add(CONFIG_INVALID)
    elif (
        composition.get("status") == "ELEMENT_MEMBERSHIP_ONLY_BLOCKED"
        and composition.get("numeric_limits_machine_enforced") is False
    ):
        reasons.add("NE04_COMPOSITION_DOMAIN_NOT_MACHINE_ENFORCED")
    else:
        # No accepted numerical composition schema exists in contract v3.
        reasons.add(CONFIG_INVALID)


def _validate_temperature(
    minimum_value: object,
    maximum_value: object,
    card: Mapping[str, Any],
    reasons: set[str],
) -> None:
    minimum = _finite_number(minimum_value)
    maximum = _finite_number(maximum_value)
    if (
        minimum is None
        or maximum is None
        or minimum <= 0.0
        or maximum < minimum
    ):
        reasons.add(TEMPERATURE_REQUEST_INVALID)
    field = card.get("temperature_k")
    if not isinstance(field, Mapping):
        reasons.add(CONFIG_INVALID)
    elif (
        field.get("status") == "UNKNOWN_BLOCKED"
        and field.get("minimum") is None
        and field.get("maximum") is None
    ):
        reasons.add("NE04_TEMPERATURE_DOMAIN_UNKNOWN")
    else:
        reasons.add(CONFIG_INVALID)


def _validate_pressure(
    value: object,
    card: Mapping[str, Any],
    reasons: set[str],
) -> None:
    pressure = _finite_number(value)
    if pressure is None or pressure <= 0.0:
        reasons.add(PRESSURE_REQUEST_INVALID)
    field = card.get("pressure_pa")
    if not isinstance(field, Mapping):
        reasons.add(CONFIG_INVALID)
    elif (
        field.get("status") == "UNKNOWN_BLOCKED"
        and field.get("minimum") is None
        and field.get("maximum") is None
    ):
        reasons.add("NE04_PRESSURE_DOMAIN_UNKNOWN")
    else:
        reasons.add(CONFIG_INVALID)


def _blocked_decision(
    request: DomainRequest,
    reasons: set[str],
    *,
    database_key: str = "",
    effective_phases: tuple[str, ...] = (),
) -> DomainDecision:
    return DomainDecision(
        allowed=False,
        reason_codes=tuple(sorted(reasons or {CONFIG_INVALID})),
        feature_id=_normalize_text(request.feature_id),
        database_key=database_key,
        effective_phases=effective_phases,
    )


def evaluate_domain_request(
    project_root: str | Path,
    request: DomainRequest,
    *,
    config_path: str | Path | None = None,
) -> DomainDecision:
    """Evaluate one complete request and never allow an unknown condition."""

    if not isinstance(request, DomainRequest):
        raise TypeError("request must be DomainRequest")
    reasons: set[str] = set()
    root = Path(project_root).expanduser().resolve()
    path = (
        Path(config_path).expanduser().resolve()
        if config_path is not None
        else root / "configs" / "ne04_database_domains.json"
    )
    try:
        contract = _load_contract(path)
    except Exception:
        return _blocked_decision(request, {CONFIG_INVALID})

    if not _normalize_text(request.feature_id):
        reasons.add(FEATURE_ID_REQUIRED)
    if contract.get("calculations_enabled") is not True:
        reasons.add(CALCULATIONS_DISABLED)

    key = _normalize_database_key(request.database_key)
    diagnostic_keys = contract.get("diagnostic_database_keys")
    release_keys = contract.get("release_database_keys")
    if isinstance(diagnostic_keys, list) and key in diagnostic_keys:
        reasons.add("NE04_DATABASE_DIAGNOSTIC_ONLY")
        return _blocked_decision(request, reasons, database_key=key)
    if not isinstance(release_keys, list) or key not in release_keys:
        reasons.add("NE04_UNKNOWN_DATABASE")
        return _blocked_decision(request, reasons, database_key=key)

    databases = contract.get("databases")
    card = databases.get(key) if isinstance(databases, Mapping) else None
    if not isinstance(card, Mapping):
        reasons.add(CONFIG_INVALID)
        return _blocked_decision(request, reasons, database_key=key)

    identity = card.get("identity")
    phases_card = card.get("phases")
    phases: frozenset[str] = frozenset()
    if not isinstance(identity, Mapping) or not isinstance(phases_card, Mapping):
        reasons.add(CONFIG_INVALID)
    else:
        try:
            database_path = _resolve_contract_file(
                root, identity.get("runtime_relative_path")
            )
            if _sha256_file(database_path) != identity.get("runtime_sha256"):
                raise ValueError("runtime database SHA-256 mismatch")
            phases = _declared_phases(_decode_file(database_path))
            if len(phases) != phases_card.get("expected_count"):
                raise ValueError("runtime phase count mismatch")
            if _phase_fingerprint(phases) != phases_card.get("sorted_lf_sha256"):
                raise ValueError("runtime phase fingerprint mismatch")
        except Exception:
            reasons.add("NE04_DATABASE_IDENTITY_MISMATCH")

    requested, requested_valid, requested_duplicate = _normalize_phase_array(
        request.requested_phases
    )
    excluded, excluded_valid, excluded_duplicate = _normalize_phase_array(
        request.excluded_phases
    )
    if request.requested_phases is None:
        reasons.add("NE04_REQUESTED_PHASES_REQUIRED")
    if request.excluded_phases is None:
        reasons.add("NE04_EXPLICIT_EXCLUSIONS_REQUIRED")
    if not requested:
        reasons.add("NE04_EMPTY_EFFECTIVE_PHASE_SET")
    if not requested_valid or set(requested) - phases:
        reasons.add("NE04_REQUESTED_PHASE_NOT_PRESENT")
    if not excluded_valid or set(excluded) - phases:
        reasons.add("NE04_EXCLUDED_PHASE_NOT_PRESENT")
    if requested_duplicate or excluded_duplicate:
        reasons.add("NE04_DUPLICATE_PHASE_INPUT")
    overlap = set(requested) & set(excluded)
    if overlap:
        reasons.add("NE04_PHASE_REQUEST_EXCLUSION_OVERLAP")
    effective = tuple(sorted(set(requested) - set(excluded)))
    if not effective:
        reasons.add("NE04_EMPTY_EFFECTIVE_PHASE_SET")

    _validate_composition(
        request.composition,
        request.composition_basis,
        card,
        reasons,
    )
    _validate_temperature(
        request.temperature_min_k,
        request.temperature_max_k,
        card,
        reasons,
    )
    _validate_pressure(request.pressure_pa, card, reasons)

    legal = card.get("legal")
    if not isinstance(legal, Mapping):
        reasons.add(CONFIG_INVALID)
    elif (
        legal.get("status") == "REVIEW_REQUIRED_BLOCKED"
        and legal.get("redistribution_allowed") is None
    ):
        reasons.add("NE04_LEGAL_REDISTRIBUTION_REVIEW_OPEN")
    else:
        reasons.add(CONFIG_INVALID)

    # Contract v3 contains no permissive numerical or legal state.  If every
    # blocker were accidentally removed without a schema migration, fail shut.
    if not reasons:
        reasons.add(CONFIG_INVALID)
    return _blocked_decision(
        request,
        reasons,
        database_key=key,
        effective_phases=effective,
    )
