"""Fail-closed, database-independent Wave 2B path contract V2.

This module contains immutable data-transfer objects only.  It imports no
thermodynamic database, solver, pycalphad, or scheil package and performs no
calculation.  A backend may use these objects to report what it actually
attempted and what topology or solidification path it actually observed.

Attempt chronology is deliberately separate from accepted topology/path data.
The distinction prevents a service layer from turning a rectangular grid,
discarded branch, failed solve, duplicate endpoint, or convenience closure row
into solver evidence.  This DTO-only module cannot authenticate a completeness
witness, so every ``COMPLETE`` or physical-success terminal is rejected until
an execution adapter supplies a verifier-bound capability across an external
trust boundary.

No object in this module grants release, production use, feature coverage, or
acceptance.  Fe remains an explicit supported family.  Both Fe profiles retain
an undecided baseline and C15-exclusion policy; C15_LAVES is therefore required
in every Fe candidate/requested/effective phase set.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass, field as _field
import math as _math
import struct as _struct
from types import MappingProxyType as _MappingProxyType
from typing import ClassVar as _ClassVar


CONTRACT_SCHEMA = "THERMOGAR-WAVE2B-PATH-CONTRACT-V2-2"
CONTRACT_VERSION = "2.1"
SUPPORTED_DATABASE_FAMILIES = ("ni", "al", "fe")
SUPPORTED_PATH_FEATURES = (
    "binary_phase_diagram",
    "multicomponent_isopleth",
    "ternary_phase_diagram",
    "equilibrium_solidification",
    "scheil_solidification",
)
SUPPORTED_FE_PROFILE_IDS = ("thermogar_patch", "upstream_original")

FE_POLICY_UNDECIDED = "UNDECIDED_USER_DECISION_REQUIRED"
POLICY_NOT_APPLICABLE = "NOT_APPLICABLE"
SOLIDIFICATION_PRESSURE_PA = 101325.0
MAX_ENDPOINT_CORRECTION_ULPS = 4

# These are denials, not provisional approvals.
PRODUCTION_USE = "DENIED"
ACCEPTANCE_CLAIM = False
COUNTS_TOWARD_FEATURE_COVERAGE = False
RELEASE_AUTHORIZED = False
# Python process-local sentinels are introspectable and therefore are not an
# unforgeable instrumentation capability.  V2 deliberately exposes no trusted
# COMPLETE factory until an execution adapter supplies a verifier-bound
# capability across that external boundary.  Caller-provided counters, flags,
# and digests remain useful partial diagnostics but can never mint COMPLETE.
COMPLETE_ISSUANCE_AVAILABLE = False
COMPLETE_ISSUANCE_BOUNDARY = (
    "UNAVAILABLE_UNTIL_EXECUTION_ADAPTER_VERIFIER_CAPABILITY"
)

_PROFILE_ROLES = _MappingProxyType(
    {
        ("ni", "mc_ni_v2036"): "RELEASE_CANDIDATE_PENDING_NE04",
        ("al", "mc_al_v2037"): "RELEASE_CANDIDATE_PENDING_NE04",
        ("fe", "thermogar_patch"): "EVALUATION_PROFILE",
        ("fe", "upstream_original"): "DIAGNOSTIC_CONTROL",
    }
)
_DATABASE_IDS = _MappingProxyType(
    {
        ("ni", "mc_ni_v2036"): "mc_ni_v2036",
        ("al", "mc_al_v2037"): "mc_al_v2037",
        ("fe", "thermogar_patch"): "mc_fe_v2062",
        ("fe", "upstream_original"): "mc_fe_v2062",
    }
)
_MAPPING_STRATEGIES = _MappingProxyType(
    {
        "binary_phase_diagram": "BINARY_MAPPING",
        "multicomponent_isopleth": "ISOPLETH_MAPPING",
        "ternary_phase_diagram": "TERNARY_MAPPING",
    }
)
_SOLIDIFICATION_METHODS = _MappingProxyType(
    {
        "equilibrium_solidification": "EQUILIBRIUM",
        "scheil_solidification": "SCHEIL_GULLIVER",
    }
)
_STRUCTURED_DIAGNOSTIC_SPECS = _MappingProxyType(
    {
        "MAPPING_LINE_STATUS_UNRESOLVED": (
            "MAPPING_POSTRUN_TOPOLOGY",
            "WARNING",
        ),
        "SOLID_PUBLIC_SAME_START_T_OFF_PATH": (
            "SOLIDIFICATION_PUBLIC_PATH",
            "INFO",
        ),
        "SOLID_SERVICE_CLOSURE_ACCOUNTING_INCOMPLETE": (
            "SOLIDIFICATION_ACCOUNTING",
            "WARNING",
        ),
    }
)
STRUCTURED_DIAGNOSTIC_REASONS = _MappingProxyType(
    dict(_STRUCTURED_DIAGNOSTIC_SPECS)
)

_REASON_DESCRIPTIONS = (
    ("W2B_V2_TYPE_INVALID", "an object has the wrong exact type"),
    ("W2B_V2_BOOL_INVALID", "a boolean is not an exact bool"),
    ("W2B_V2_INTEGER_INVALID", "an integer is not exact or is out of range"),
    ("W2B_V2_NUMBER_INVALID", "a number is not an exact int or float"),
    ("W2B_V2_NUMBER_NONFINITE", "a number is non-finite or overflows binary64"),
    ("W2B_V2_TOKEN_INVALID", "a token is empty, malformed, or too long"),
    ("W2B_V2_NAME_INVALID", "a component or phase name is malformed"),
    ("W2B_V2_SHA256_INVALID", "a digest is not lowercase hexadecimal SHA-256"),
    ("W2B_V2_DATABASE_INVALID", "database identity is invalid"),
    ("W2B_V2_DATABASE_ROLE_INVALID", "profile role does not match the receipt profile"),
    ("W2B_V2_FE_POLICY_INVALID", "Fe decisions must remain explicitly undecided"),
    ("W2B_V2_NON_FE_POLICY_INVALID", "non-Fe decisions must be NOT_APPLICABLE"),
    ("W2B_V2_EXECUTION_BINDING_INVALID", "receipt or execution-lease binding is invalid"),
    ("W2B_V2_PHASE_DOMAIN_INVALID", "phase-domain partition is invalid"),
    ("W2B_V2_FE_C15_REQUIRED", "Fe phase domain must retain C15_LAVES"),
    ("W2B_V2_PHASE_INSTANCE_INVALID", "phase-instance identity or multiplicity is invalid"),
    ("W2B_V2_COORDINATES_INVALID", "coordinate collection is invalid"),
    ("W2B_V2_BINARY64_INVALID", "raw/canonical binary64 fraction evidence is invalid"),
    ("W2B_V2_BINARY64_CORRECTION_EXCEEDED", "endpoint correction exceeds the ULP bound"),
    ("W2B_V2_COMPOSITION_INVALID", "composition is invalid or does not sum to one"),
    ("W2B_V2_ATTEMPT_INVALID", "attempt record is invalid"),
    ("W2B_V2_ATTEMPT_OUTCOME_INVALID", "attempt outcome is invalid"),
    ("W2B_V2_ATTEMPT_ORDER_INVALID", "attempt ordinals are incomplete or out of order"),
    ("W2B_V2_TOPOLOGY_NODE_INVALID", "topology node is invalid"),
    ("W2B_V2_TOPOLOGY_SEGMENT_INVALID", "topology segment is not an explicit sequential edge"),
    ("W2B_V2_TOPOLOGY_REGION_INVALID", "topology region hyperedge is invalid"),
    ("W2B_V2_TOPOLOGY_REFERENCE_INVALID", "topology evidence reference is invalid"),
    ("W2B_V2_TOPOLOGY_OWNERSHIP_INVALID", "postrun-evidence-to-topology ownership is not exact one-to-one"),
    ("W2B_V2_POSTRUN_EVIDENCE_INVALID", "mapping postrun evidence is invalid"),
    ("W2B_V2_LINE_PHASE_INVALID", "line phase evidence is not an exact endpoint intersection subset"),
    ("W2B_V2_TIELINE_INVALID", "explicit tieline evidence is invalid"),
    ("W2B_V2_MULTIPLICITY_INVALID", "phase-instance multiplicity naming is inconsistent"),
    ("W2B_V2_DIAGNOSTICS_INVALID", "diagnostics metadata is invalid"),
    ("W2B_V2_COMPLETE_INSTRUMENTATION_REQUIRED", "COMPLETE requires a full instrumented ledger"),
    ("W2B_V2_COMPLETE_CAPABILITY_UNAVAILABLE", "COMPLETE issuance is unavailable without an execution-adapter verifier capability"),
    ("W2B_V2_WORK_BUDGET_EXCEEDED", "aggregate nested reconstruction work exceeds the contract budget"),
    ("W2B_V2_UNRESOLVED_BRANCHES", "unresolved branches require a partial terminal state"),
    ("W2B_V2_BUDGET_EXHAUSTED", "attempt budget exhaustion requires a partial terminal state"),
    ("W2B_V2_MAPPING_LEDGER_INVALID", "mapping ledger is invalid"),
    ("W2B_V2_MAPPING_TERMINAL_INVALID", "mapping terminal reason is inconsistent"),
    ("W2B_V2_SOLID_ATTEMPT_INVALID", "solidification attempt is invalid"),
    ("W2B_V2_SOLID_POINT_INVALID", "accepted solidification path point is invalid"),
    ("W2B_V2_SOLID_BALANCE_INVALID", "solid and liquid fractions do not balance"),
    ("W2B_V2_SOLID_PHASE_SUM_INVALID", "phase-instance fractions do not sum to fraction solid"),
    ("W2B_V2_SOLID_PATH_ORDER_INVALID", "accepted path order or progress is invalid"),
    ("W2B_V2_SERVICE_CLOSURE_INVALID", "service closure is invalid or conflated with a physical attempt"),
    ("W2B_V2_OFF_PATH_OBSERVATION_INVALID", "off-path public solidification observation is invalid"),
    ("W2B_V2_CLOSURE_EVIDENCE_INVALID", "incomplete service-closure evidence is invalid"),
    ("W2B_V2_SOLID_LEDGER_INVALID", "solidification ledger is invalid"),
    ("W2B_V2_SOLID_TERMINAL_INVALID", "solidification terminal reason is inconsistent"),
    ("W2B_V2_RESULT_INVALID", "public result reconstruction failed closed"),
)
WAVE2B_PATH_V2_REASON_CODES = _MappingProxyType(dict(_REASON_DESCRIPTIONS))

_TOKEN_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_#:+-."
)
_NAME_CHARACTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_#:+-.")
_COORDINATE_CHARACTERS = _NAME_CHARACTERS | frozenset("()/,[]")
_HEX_CHARACTERS = frozenset("0123456789abcdef")
_MAX_COLLECTION = 100_000
_MAX_ORDINAL = 2_147_483_647
_BALANCE_ULPS = 8
_MAX_MAPPING_ATTEMPTS = 20_000
_MAX_MAPPING_EVIDENCE_RECORDS = 80_000
_MAX_TOPOLOGY_NODES = 20_000
_MAX_TOPOLOGY_SEGMENTS = 40_000
_MAX_TOPOLOGY_REGIONS = 20_000
_MAX_SOLID_ATTEMPTS = 20_000
_MAX_SOLID_PATH_POINTS = 20_000
_MAX_SOLID_OFF_PATH_OBSERVATIONS = 20_000
_MAX_AGGREGATE_NESTED_ITEMS = 250_000


class PathContractV2Error(ValueError):
    """Fail-closed error carrying one stable machine-readable reason code."""

    __slots__ = ("reason_code",)

    def __init__(self, reason_code: str) -> None:
        if type(reason_code) is not str or reason_code not in WAVE2B_PATH_V2_REASON_CODES:
            raise RuntimeError("Unknown Wave 2B path-contract V2 reason code")
        self.reason_code = reason_code
        super().__init__(reason_code)


def _fail(reason_code: str) -> None:
    raise PathContractV2Error(reason_code)


def _token(value: object, reason: str = "W2B_V2_TOKEN_INVALID", *, maximum: int = 128) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > maximum
        or any(character not in _TOKEN_CHARACTERS for character in value)
    ):
        _fail(reason)
    return value


def _name(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 64
        or any(character not in _NAME_CHARACTERS for character in value)
    ):
        _fail("W2B_V2_NAME_INVALID")
    return value


def _coordinate_name(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 96
        or any(character not in _COORDINATE_CHARACTERS for character in value)
    ):
        _fail("W2B_V2_COORDINATES_INVALID")
    return value


def _sha256(value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in _HEX_CHARACTERS for character in value)
    ):
        _fail("W2B_V2_SHA256_INVALID")
    return value


def _number(value: object) -> float:
    if type(value) not in (int, float):
        _fail("W2B_V2_NUMBER_INVALID")
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise PathContractV2Error("W2B_V2_NUMBER_NONFINITE") from error
    if not _math.isfinite(result):
        _fail("W2B_V2_NUMBER_NONFINITE")
    return 0.0 if result == 0.0 else result


def _positive(value: object) -> float:
    result = _number(value)
    if result <= 0.0:
        _fail("W2B_V2_NUMBER_INVALID")
    return result


def _integer(value: object, *, minimum: int = 0, maximum: int = _MAX_ORDINAL) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        _fail("W2B_V2_INTEGER_INVALID")
    return value


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        _fail("W2B_V2_BOOL_INVALID")
    return value


@_dataclass(frozen=True, slots=True)
class StructuredDiagnosticReasonV2:
    """Closed diagnostic code with an exact category and severity."""

    code: str
    category: str
    severity: str

    def __post_init__(self) -> None:
        if type(self.code) is not str:
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        expected = _STRUCTURED_DIAGNOSTIC_SPECS.get(self.code)
        if (
            expected is None
            or type(self.category) is not str
            or type(self.severity) is not str
            or (self.category, self.severity) != expected
        ):
            _fail("W2B_V2_DIAGNOSTICS_INVALID")


def _copy_structured_reason(value: object) -> StructuredDiagnosticReasonV2:
    if type(value) is not StructuredDiagnosticReasonV2:
        _fail("W2B_V2_DIAGNOSTICS_INVALID")
    try:
        return StructuredDiagnosticReasonV2(
            code=value.code,
            category=value.category,
            severity=value.severity,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_DIAGNOSTICS_INVALID") from error


def _names(value: object, *, allow_empty: bool) -> tuple[str, ...]:
    if type(value) is not tuple or (not value and not allow_empty) or len(value) > _MAX_COLLECTION:
        _fail("W2B_V2_PHASE_DOMAIN_INVALID")
    rebuilt: list[str] = []
    seen: set[str] = set()
    for item in value:
        item = _name(item)
        if item in seen:
            _fail("W2B_V2_PHASE_DOMAIN_INVALID")
        seen.add(item)
        rebuilt.append(item)
    return tuple(sorted(rebuilt))


def _coordinates(
    value: object,
    *,
    allow_none: bool,
    allow_empty: bool = False,
) -> tuple[tuple[str, float], ...] | None:
    if value is None:
        if allow_none:
            return None
        _fail("W2B_V2_COORDINATES_INVALID")
    if type(value) is not tuple or (not value and not allow_empty) or len(value) > _MAX_COLLECTION:
        _fail("W2B_V2_COORDINATES_INVALID")
    rows: list[tuple[str, float]] = []
    seen: set[str] = set()
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            _fail("W2B_V2_COORDINATES_INVALID")
        key = _coordinate_name(pair[0])
        if key in seen:
            _fail("W2B_V2_COORDINATES_INVALID")
        seen.add(key)
        rows.append((key, _number(pair[1])))
    return tuple(rows)


def _ordered_exact(
    value: object,
    record_type: type,
    copier,
    *,
    allow_empty: bool,
    reason: str,
) -> tuple:
    if type(value) is not tuple or (not value and not allow_empty) or len(value) > _MAX_COLLECTION:
        _fail(reason)
    if any(type(record) is not record_type for record in value):
        _fail(reason)
    rebuilt = tuple(copier(record) for record in value)
    if tuple(record.ordinal for record in rebuilt) != tuple(range(len(rebuilt))):
        _fail("W2B_V2_ATTEMPT_ORDER_INVALID")
    return rebuilt


def _within_ulps(left: float, right: float, ulps: int) -> bool:
    if left == right:
        return True
    scale = max(_math.ulp(left), _math.ulp(right), _math.ulp(1.0))
    return abs(left - right) <= ulps * scale


@_dataclass(frozen=True, slots=True)
class DatabaseIdentityV2:
    """Exact receipt profile and runtime-database identity."""

    family: str
    database_id: str
    database_sha256: str
    profile_id: str
    profile_role: str
    fe_baseline_decision: str
    c15_exclusion_decision: str

    def __post_init__(self) -> None:
        if type(self.family) is not str or self.family not in SUPPORTED_DATABASE_FAMILIES:
            _fail("W2B_V2_DATABASE_INVALID")
        database_id = _token(self.database_id, "W2B_V2_DATABASE_INVALID")
        database_sha256 = _sha256(self.database_sha256)
        profile_id = _token(self.profile_id, "W2B_V2_DATABASE_INVALID")
        expected_role = _PROFILE_ROLES.get((self.family, profile_id))
        if expected_role is None:
            _fail("W2B_V2_DATABASE_INVALID")
        if type(self.profile_role) is not str or self.profile_role != expected_role:
            _fail("W2B_V2_DATABASE_ROLE_INVALID")
        if database_id != _DATABASE_IDS[(self.family, profile_id)]:
            _fail("W2B_V2_DATABASE_INVALID")
        if self.family == "fe":
            if (
                type(self.fe_baseline_decision) is not str
                or type(self.c15_exclusion_decision) is not str
                or self.fe_baseline_decision != FE_POLICY_UNDECIDED
                or self.c15_exclusion_decision != FE_POLICY_UNDECIDED
            ):
                _fail("W2B_V2_FE_POLICY_INVALID")
        elif (
            type(self.fe_baseline_decision) is not str
            or type(self.c15_exclusion_decision) is not str
            or self.fe_baseline_decision != POLICY_NOT_APPLICABLE
            or self.c15_exclusion_decision != POLICY_NOT_APPLICABLE
        ):
            _fail("W2B_V2_NON_FE_POLICY_INVALID")
        object.__setattr__(self, "database_id", database_id)
        object.__setattr__(self, "database_sha256", database_sha256)
        object.__setattr__(self, "profile_id", profile_id)


def _copy_database(value: object) -> DatabaseIdentityV2:
    if type(value) is not DatabaseIdentityV2:
        _fail("W2B_V2_DATABASE_INVALID")
    try:
        return DatabaseIdentityV2(
            family=value.family,
            database_id=value.database_id,
            database_sha256=value.database_sha256,
            profile_id=value.profile_id,
            profile_role=value.profile_role,
            fe_baseline_decision=value.fe_baseline_decision,
            c15_exclusion_decision=value.c15_exclusion_decision,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_DATABASE_INVALID") from error


@_dataclass(frozen=True, slots=True)
class ExecutionBindingV2:
    """Content addresses proving which active receipt/lease snapshot was used.

    This DTO cannot prove that a lease is currently active.  The execution
    adapter must obtain these values from its active ``ExecutionLease`` and
    must never accept them as free caller input.
    """

    profile_receipt_digest: str
    domain_receipt_digest: str
    execution_lease_id: str
    execution_snapshot_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_receipt_digest", _sha256(self.profile_receipt_digest))
        object.__setattr__(self, "domain_receipt_digest", _sha256(self.domain_receipt_digest))
        object.__setattr__(self, "execution_lease_id", _token(self.execution_lease_id, "W2B_V2_EXECUTION_BINDING_INVALID", maximum=160))
        object.__setattr__(self, "execution_snapshot_digest", _sha256(self.execution_snapshot_digest))


def _copy_binding(value: object) -> ExecutionBindingV2:
    if type(value) is not ExecutionBindingV2:
        _fail("W2B_V2_EXECUTION_BINDING_INVALID")
    try:
        return ExecutionBindingV2(
            profile_receipt_digest=value.profile_receipt_digest,
            domain_receipt_digest=value.domain_receipt_digest,
            execution_lease_id=value.execution_lease_id,
            execution_snapshot_digest=value.execution_snapshot_digest,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_EXECUTION_BINDING_INVALID") from error


@_dataclass(frozen=True, slots=True)
class PhaseDomainV2:
    """Exact candidate/requested/excluded/effective DomainReceipt phase sets."""

    candidate_phases: tuple[str, ...]
    requested_phases: tuple[str, ...]
    excluded_phases: tuple[str, ...]
    effective_phases: tuple[str, ...]

    def __post_init__(self) -> None:
        candidates = _names(self.candidate_phases, allow_empty=False)
        requested = _names(self.requested_phases, allow_empty=False)
        excluded = _names(self.excluded_phases, allow_empty=True)
        effective = _names(self.effective_phases, allow_empty=False)
        candidate_set = set(candidates)
        requested_set = set(requested)
        excluded_set = set(excluded)
        if (
            not requested_set.issubset(candidate_set)
            or not excluded_set.issubset(candidate_set)
            or requested_set & excluded_set
            or requested_set | excluded_set != candidate_set
            or effective != requested
        ):
            _fail("W2B_V2_PHASE_DOMAIN_INVALID")
        object.__setattr__(self, "candidate_phases", candidates)
        object.__setattr__(self, "requested_phases", requested)
        object.__setattr__(self, "excluded_phases", excluded)
        object.__setattr__(self, "effective_phases", effective)


def _copy_domain(value: object, database: DatabaseIdentityV2) -> PhaseDomainV2:
    if type(value) is not PhaseDomainV2:
        _fail("W2B_V2_PHASE_DOMAIN_INVALID")
    try:
        rebuilt = PhaseDomainV2(
            candidate_phases=value.candidate_phases,
            requested_phases=value.requested_phases,
            excluded_phases=value.excluded_phases,
            effective_phases=value.effective_phases,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_PHASE_DOMAIN_INVALID") from error
    if database.family == "fe":
        c15 = "C15_LAVES"
        if (
            c15 not in rebuilt.candidate_phases
            or c15 not in rebuilt.requested_phases
            or c15 in rebuilt.excluded_phases
            or c15 not in rebuilt.effective_phases
        ):
            _fail("W2B_V2_FE_C15_REQUIRED")
    return rebuilt


@_dataclass(frozen=True, slots=True)
class PhaseInstanceV2:
    """One phase composition-set identity, including multiplicity index."""

    instance_name: str
    base_phase: str
    instance_index: int

    def __post_init__(self) -> None:
        instance_name = _name(self.instance_name)
        base_phase = _name(self.base_phase)
        if "#" in base_phase:
            _fail("W2B_V2_PHASE_INSTANCE_INVALID")
        instance_index = _integer(self.instance_index, minimum=1, maximum=65_535)
        allowed = {base_phase, f"{base_phase}#{instance_index}"}
        if instance_name not in allowed or (instance_name == base_phase and instance_index != 1):
            _fail("W2B_V2_PHASE_INSTANCE_INVALID")
        object.__setattr__(self, "instance_name", instance_name)
        object.__setattr__(self, "base_phase", base_phase)
        object.__setattr__(self, "instance_index", instance_index)


def _copy_phase_instance(value: object) -> PhaseInstanceV2:
    if type(value) is not PhaseInstanceV2:
        _fail("W2B_V2_PHASE_INSTANCE_INVALID")
    try:
        return PhaseInstanceV2(
            instance_name=value.instance_name,
            base_phase=value.base_phase,
            instance_index=value.instance_index,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_PHASE_INSTANCE_INVALID") from error


def _phase_instances(value: object, *, allow_empty: bool) -> tuple[PhaseInstanceV2, ...]:
    if type(value) is not tuple or (not value and not allow_empty) or len(value) > _MAX_COLLECTION:
        _fail("W2B_V2_PHASE_INSTANCE_INVALID")
    rebuilt = tuple(_copy_phase_instance(item) for item in value)
    names = tuple(item.instance_name for item in rebuilt)
    if len(set(names)) != len(names):
        _fail("W2B_V2_PHASE_INSTANCE_INVALID")
    groups: dict[str, list[PhaseInstanceV2]] = {}
    for item in rebuilt:
        groups.setdefault(item.base_phase, []).append(item)
    for base_phase, group in groups.items():
        ordered = sorted(group, key=lambda item: item.instance_index)
        if [item.instance_index for item in ordered] != list(range(1, len(group) + 1)):
            _fail("W2B_V2_PHASE_INSTANCE_INVALID")
        if len(group) > 1 and any(
            item.instance_name != f"{base_phase}#{item.instance_index}" for item in ordered
        ):
            _fail("W2B_V2_PHASE_INSTANCE_INVALID")
    return tuple(
        sorted(
            rebuilt,
            key=lambda item: (item.base_phase, item.instance_index, item.instance_name),
        )
    )


@_dataclass(frozen=True, slots=True)
class Binary64FractionV2:
    """Raw IEEE-754 evidence plus a narrowly corrected canonical fraction."""

    raw_value: float
    canonical_value: float
    raw_bits_hex: str
    corrected: bool
    correction_ulps: int

    @classmethod
    def observe(cls, raw_value: object) -> "Binary64FractionV2":
        if type(raw_value) not in (int, float) or type(raw_value) is bool:
            _fail("W2B_V2_BINARY64_INVALID")
        try:
            raw = float(raw_value)
        except (OverflowError, TypeError, ValueError) as error:
            raise PathContractV2Error("W2B_V2_NUMBER_NONFINITE") from error
        canonical, corrected, ulps = _canonical_fraction(raw)
        return cls(
            raw_value=raw,
            canonical_value=canonical,
            raw_bits_hex=_struct.pack(">d", raw).hex(),
            corrected=corrected,
            correction_ulps=ulps,
        )

    def __post_init__(self) -> None:
        if type(self.raw_value) is not float or type(self.canonical_value) is not float:
            _fail("W2B_V2_BINARY64_INVALID")
        if not _math.isfinite(self.raw_value) or not _math.isfinite(self.canonical_value):
            _fail("W2B_V2_NUMBER_NONFINITE")
        expected, corrected, ulps = _canonical_fraction(self.raw_value)
        bits = _struct.pack(">d", self.raw_value).hex()
        if (
            _struct.pack(">d", self.canonical_value) != _struct.pack(">d", expected)
            or type(self.raw_bits_hex) is not str
            or self.raw_bits_hex != bits
            or type(self.corrected) is not bool
            or self.corrected is not corrected
            or type(self.correction_ulps) is not int
            or self.correction_ulps != ulps
        ):
            _fail("W2B_V2_BINARY64_INVALID")


def _canonical_fraction(raw: float) -> tuple[float, bool, int]:
    if not _math.isfinite(raw):
        _fail("W2B_V2_NUMBER_NONFINITE")
    if 0.0 <= raw <= 1.0:
        return (0.0 if raw == 0.0 else raw), False, 0
    endpoint = 0.0 if raw < 0.0 else 1.0
    direction = -_math.inf if raw < 0.0 else _math.inf
    candidate = endpoint
    for ulps in range(1, MAX_ENDPOINT_CORRECTION_ULPS + 1):
        candidate = _math.nextafter(candidate, direction)
        if raw == candidate:
            return endpoint, True, ulps
    _fail("W2B_V2_BINARY64_CORRECTION_EXCEEDED")
    raise AssertionError("unreachable")


def _copy_fraction(value: object) -> Binary64FractionV2:
    if type(value) is not Binary64FractionV2:
        _fail("W2B_V2_BINARY64_INVALID")
    try:
        return Binary64FractionV2(
            raw_value=value.raw_value,
            canonical_value=value.canonical_value,
            raw_bits_hex=value.raw_bits_hex,
            corrected=value.corrected,
            correction_ulps=value.correction_ulps,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_BINARY64_INVALID") from error


@_dataclass(frozen=True, slots=True)
class CompositionEntryV2:
    component: str
    fraction: Binary64FractionV2

    def __post_init__(self) -> None:
        object.__setattr__(self, "component", _name(self.component))
        object.__setattr__(self, "fraction", _copy_fraction(self.fraction))


def _copy_composition_entry(value: object) -> CompositionEntryV2:
    if type(value) is not CompositionEntryV2:
        _fail("W2B_V2_COMPOSITION_INVALID")
    try:
        return CompositionEntryV2(value.component, _copy_fraction(value.fraction))
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_COMPOSITION_INVALID") from error


def _composition(
    value: object,
    *,
    expected_components: tuple[str, ...] | None,
    allow_empty: bool,
) -> tuple[CompositionEntryV2, ...]:
    if type(value) is not tuple or (not value and not allow_empty) or len(value) > _MAX_COLLECTION:
        _fail("W2B_V2_COMPOSITION_INVALID")
    rebuilt = tuple(_copy_composition_entry(item) for item in value)
    names = tuple(item.component for item in rebuilt)
    if len(set(names)) != len(names):
        _fail("W2B_V2_COMPOSITION_INVALID")
    if expected_components is not None and names != expected_components:
        _fail("W2B_V2_COMPOSITION_INVALID")
    if rebuilt:
        try:
            total = _math.fsum(item.fraction.canonical_value for item in rebuilt)
        except (OverflowError, ValueError) as error:
            raise PathContractV2Error("W2B_V2_COMPOSITION_INVALID") from error
        if not _within_ulps(total, 1.0, max(_BALANCE_ULPS, len(rebuilt))):
            _fail("W2B_V2_COMPOSITION_INVALID")
    return rebuilt


_MAPPING_ATTEMPT_OUTCOMES = frozenset({"ACCEPTED", "FAILED", "MERGED", "ABANDONED"})
_TOPOLOGY_NODE_KINDS = frozenset(
    {
        "STARTING_POINT",
        "ZPF_NODE",
        "TIELINE_ENDPOINT",
        "INVARIANT_NODE",
        "MULTIPHASE_NODE",
        "TERMINAL_NODE",
    }
)
_TOPOLOGY_SEGMENT_KINDS = frozenset({"SEQUENTIAL_ZPF", "EXPLICIT_TIELINE"})
_TOPOLOGY_REGION_KINDS = frozenset({"INVARIANT_REGION", "MULTIPHASE_REGION"})
_MAPPING_TERMINALS = frozenset(
    {
        "COMPLETE",
        "TOPOLOGY_OBSERVED_DIAGNOSTICS_PARTIAL",
        "PARTIAL_UNRESOLVED_BRANCHES",
        "BUDGET_EXHAUSTED",
        "BACKEND_TERMINATED",
        "NO_PROGRESS",
    }
)
_POSTRUN_NODE_ROLES = _MappingProxyType(
    {
        "STARTING_NODE_OBSERVATION": "STARTING_POINT",
        "EXIT_NODE_OBSERVATION": "TERMINAL_NODE",
        "ZPF_NODE_OBSERVATION": "ZPF_NODE",
        "TIELINE_ENDPOINT_OBSERVATION": "TIELINE_ENDPOINT",
        "INVARIANT_NODE_OBSERVATION": "INVARIANT_NODE",
        "MULTIPHASE_NODE_OBSERVATION": "MULTIPHASE_NODE",
    }
)
_POSTRUN_SEGMENT_ROLES = _MappingProxyType(
    {
        "SEQUENTIAL_ZPF_LINE_OBSERVATION": "SEQUENTIAL_ZPF",
        "EXPLICIT_TIELINE_OBSERVATION": "EXPLICIT_TIELINE",
    }
)
_POSTRUN_REGION_ROLES = _MappingProxyType(
    {
        "INVARIANT_REGION_OBSERVATION": "INVARIANT_REGION",
        "MULTIPHASE_REGION_OBSERVATION": "MULTIPHASE_REGION",
    }
)
_POSTRUN_UNRESOLVED_ROLE = "UNRESOLVED_LINE_STATUS"


@_dataclass(frozen=True, slots=True)
class MappingAttemptRecord:
    """One hidden chronological strategy attempt, including failures/merges.

    Failed or abandoned attempts may have ``coordinates=None`` when the solver
    did not resolve a coordinate.  Such absence is retained; it is never filled
    from a nearby successful node.  Public postrun topology records are not
    attempts and must use :class:`MappingPostrunEvidenceRecordV2`.
    """

    ordinal: int
    attempt_id: str
    stage: str
    conditions: tuple[tuple[str, float], ...]
    outcome: str
    coordinates: tuple[tuple[str, float], ...] | None
    phase_local_coordinates: tuple[
        tuple[str, tuple[tuple[str, float], ...]], ...
    ] | None
    phase_instances: tuple[PhaseInstanceV2, ...]
    reason_code: str | None

    def __post_init__(self) -> None:
        ordinal = _integer(self.ordinal)
        attempt_id = _token(self.attempt_id, "W2B_V2_ATTEMPT_INVALID", maximum=128)
        stage = _token(self.stage, "W2B_V2_ATTEMPT_INVALID", maximum=96)
        conditions = _coordinates(self.conditions, allow_none=False)
        if type(self.outcome) is not str or self.outcome not in _MAPPING_ATTEMPT_OUTCOMES:
            _fail("W2B_V2_ATTEMPT_OUTCOME_INVALID")
        coordinates = _coordinates(self.coordinates, allow_none=True)
        phase_local = _phase_local_coordinates(self.phase_local_coordinates)
        phases = _phase_instances(self.phase_instances, allow_empty=True)
        if phase_local is not None and not set(name for name, _coords in phase_local).issubset(
            {item.instance_name for item in phases}
        ):
            _fail("W2B_V2_COORDINATES_INVALID")
        if self.reason_code is None:
            reason_code = None
        else:
            reason_code = _token(self.reason_code, "W2B_V2_ATTEMPT_INVALID", maximum=128)
        if self.outcome in ("ACCEPTED", "MERGED"):
            if (
                (coordinates is None and phase_local is None)
                or not phases
                or reason_code is not None
            ):
                _fail("W2B_V2_ATTEMPT_INVALID")
        elif reason_code is None:
            _fail("W2B_V2_ATTEMPT_INVALID")
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "attempt_id", attempt_id)
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "coordinates", coordinates)
        object.__setattr__(self, "phase_local_coordinates", phase_local)
        object.__setattr__(self, "phase_instances", phases)
        object.__setattr__(self, "reason_code", reason_code)


def _copy_mapping_attempt(value: object) -> MappingAttemptRecord:
    if type(value) is not MappingAttemptRecord:
        _fail("W2B_V2_ATTEMPT_INVALID")
    try:
        return MappingAttemptRecord(
            ordinal=value.ordinal,
            attempt_id=value.attempt_id,
            stage=value.stage,
            conditions=value.conditions,
            outcome=value.outcome,
            coordinates=value.coordinates,
            phase_local_coordinates=value.phase_local_coordinates,
            phase_instances=tuple(_copy_phase_instance(item) for item in value.phase_instances),
            reason_code=value.reason_code,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_ATTEMPT_INVALID") from error


def _phase_local_coordinates(
    value: object,
) -> tuple[tuple[str, tuple[tuple[str, float], ...]], ...] | None:
    if value is None:
        return None
    if type(value) is not tuple or not value or len(value) > _MAX_COLLECTION:
        _fail("W2B_V2_COORDINATES_INVALID")
    rows: list[tuple[str, tuple[tuple[str, float], ...]]] = []
    seen: set[str] = set()
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            _fail("W2B_V2_COORDINATES_INVALID")
        instance_name = _name(pair[0])
        if instance_name in seen:
            _fail("W2B_V2_COORDINATES_INVALID")
        seen.add(instance_name)
        local = _coordinates(pair[1], allow_none=False)
        rows.append((instance_name, local))
    return tuple(rows)


@_dataclass(frozen=True, slots=True)
class MappingPostrunEvidenceRecordV2:
    """One public postrun node/relation/status record, never a solver attempt."""

    ordinal: int
    evidence_id: str
    source_collection: str
    source_record_index: int
    evidence_role: str
    status: str
    topology_component_id: str
    topology_target_id: str | None
    member_node_ids: tuple[str, ...]
    global_coordinates: tuple[tuple[str, float], ...] | None
    phase_local_coordinates: tuple[
        tuple[str, tuple[tuple[str, float], ...]], ...
    ] | None
    phase_instances: tuple[PhaseInstanceV2, ...]
    diagnostic_reason: StructuredDiagnosticReasonV2 | None

    def __post_init__(self) -> None:
        ordinal = _integer(self.ordinal)
        evidence_id = _token(
            self.evidence_id,
            "W2B_V2_POSTRUN_EVIDENCE_INVALID",
            maximum=128,
        )
        if type(self.evidence_role) is not str:
            _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
        node_kind = _POSTRUN_NODE_ROLES.get(self.evidence_role)
        segment_kind = _POSTRUN_SEGMENT_ROLES.get(self.evidence_role)
        region_kind = _POSTRUN_REGION_ROLES.get(self.evidence_role)
        unresolved = self.evidence_role == _POSTRUN_UNRESOLVED_ROLE
        if sum(item is not None for item in (node_kind, segment_kind, region_kind)) + int(unresolved) != 1:
            _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
        expected_collection = (
            "PUBLIC_NODE_RECORDS"
            if node_kind is not None
            else "PUBLIC_REGION_RECORDS"
            if region_kind is not None
            else "PUBLIC_LINE_RECORDS"
        )
        if type(self.source_collection) is not str or self.source_collection != expected_collection:
            _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
        source_index = _integer(self.source_record_index)
        expected_status = "UNRESOLVED" if unresolved else "RESOLVED"
        if type(self.status) is not str or self.status != expected_status:
            _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
        component_id = _token(
            self.topology_component_id,
            "W2B_V2_POSTRUN_EVIDENCE_INVALID",
            maximum=128,
        )
        if self.topology_target_id is None:
            target_id = None
        else:
            target_id = _token(
                self.topology_target_id,
                "W2B_V2_POSTRUN_EVIDENCE_INVALID",
                maximum=128,
            )
        if type(self.member_node_ids) is not tuple or len(self.member_node_ids) > _MAX_COLLECTION:
            _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
        members = tuple(
            _token(item, "W2B_V2_POSTRUN_EVIDENCE_INVALID", maximum=128)
            for item in self.member_node_ids
        )
        if len(set(members)) != len(members):
            _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
        coordinates = _coordinates(self.global_coordinates, allow_none=True)
        phase_local = _phase_local_coordinates(self.phase_local_coordinates)
        phases = _phase_instances(self.phase_instances, allow_empty=unresolved)
        if phase_local is not None and not set(name for name, _coords in phase_local).issubset(
            {item.instance_name for item in phases}
        ):
            _fail("W2B_V2_COORDINATES_INVALID")
        if self.diagnostic_reason is None:
            reason = None
        else:
            reason = _copy_structured_reason(self.diagnostic_reason)

        if node_kind is not None:
            if (
                target_id is None
                or members
                or (coordinates is None and phase_local is None)
                or reason is not None
            ):
                _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
        elif segment_kind is not None:
            if (
                target_id is None
                or len(members) != 2
                or coordinates is not None
                or phase_local is not None
                or reason is not None
            ):
                _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
        elif region_kind is not None:
            if (
                target_id is None
                or not members
                or coordinates is not None
                or phase_local is not None
                or reason is not None
            ):
                _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
        elif (
            target_id is not None
            or not (1 <= len(members) <= 2)
            or coordinates is not None
            or phase_local is not None
            or phases
            or reason is None
            or reason.code != "MAPPING_LINE_STATUS_UNRESOLVED"
        ):
            # A public unresolved-line status is diagnostic relation evidence,
            # never a manufactured failed point or a phase observation.
            _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")

        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "evidence_id", evidence_id)
        object.__setattr__(self, "source_record_index", source_index)
        object.__setattr__(self, "topology_component_id", component_id)
        object.__setattr__(self, "topology_target_id", target_id)
        object.__setattr__(self, "member_node_ids", members)
        object.__setattr__(self, "global_coordinates", coordinates)
        object.__setattr__(self, "phase_local_coordinates", phase_local)
        object.__setattr__(self, "phase_instances", phases)
        object.__setattr__(self, "diagnostic_reason", reason)

    @property
    def topology_target_kind(self) -> str:
        if self.evidence_role in _POSTRUN_NODE_ROLES:
            return "NODE"
        if self.evidence_role in _POSTRUN_SEGMENT_ROLES:
            return "SEGMENT"
        if self.evidence_role in _POSTRUN_REGION_ROLES:
            return "REGION"
        return "UNRESOLVED_LINE"

    @property
    def topology_target_subkind(self) -> str | None:
        if self.evidence_role in _POSTRUN_NODE_ROLES:
            return _POSTRUN_NODE_ROLES[self.evidence_role]
        if self.evidence_role in _POSTRUN_SEGMENT_ROLES:
            return _POSTRUN_SEGMENT_ROLES[self.evidence_role]
        if self.evidence_role in _POSTRUN_REGION_ROLES:
            return _POSTRUN_REGION_ROLES[self.evidence_role]
        return None


def _copy_mapping_postrun_evidence(value: object) -> MappingPostrunEvidenceRecordV2:
    if type(value) is not MappingPostrunEvidenceRecordV2:
        _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
    try:
        return MappingPostrunEvidenceRecordV2(
            ordinal=value.ordinal,
            evidence_id=value.evidence_id,
            source_collection=value.source_collection,
            source_record_index=value.source_record_index,
            evidence_role=value.evidence_role,
            status=value.status,
            topology_component_id=value.topology_component_id,
            topology_target_id=value.topology_target_id,
            member_node_ids=value.member_node_ids,
            global_coordinates=value.global_coordinates,
            phase_local_coordinates=value.phase_local_coordinates,
            phase_instances=tuple(
                _copy_phase_instance(item) for item in value.phase_instances
            ),
            diagnostic_reason=(
                None
                if value.diagnostic_reason is None
                else _copy_structured_reason(value.diagnostic_reason)
            ),
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_POSTRUN_EVIDENCE_INVALID") from error


def _evidence_ids(value: object, *, minimum: int = 1) -> tuple[str, ...]:
    if type(value) is not tuple or len(value) < minimum or len(value) > _MAX_COLLECTION:
        _fail("W2B_V2_TOPOLOGY_REFERENCE_INVALID")
    rebuilt = tuple(
        _token(item, "W2B_V2_TOPOLOGY_REFERENCE_INVALID", maximum=128) for item in value
    )
    if len(set(rebuilt)) != len(rebuilt):
        _fail("W2B_V2_TOPOLOGY_REFERENCE_INVALID")
    return rebuilt


@_dataclass(frozen=True, slots=True)
class TopologyNode:
    """One final topology node, distinct from the attempt chronology."""

    ordinal: int
    node_id: str
    topology_component_id: str
    node_kind: str
    global_coordinates: tuple[tuple[str, float], ...] | None
    phase_local_coordinates: tuple[
        tuple[str, tuple[tuple[str, float], ...]], ...
    ] | None
    phase_instances: tuple[PhaseInstanceV2, ...]
    base_phases: tuple[str, ...]
    evidence_record_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        ordinal = _integer(self.ordinal)
        node_id = _token(self.node_id, "W2B_V2_TOPOLOGY_NODE_INVALID", maximum=128)
        component_id = _token(
            self.topology_component_id,
            "W2B_V2_TOPOLOGY_NODE_INVALID",
            maximum=128,
        )
        if type(self.node_kind) is not str or self.node_kind not in _TOPOLOGY_NODE_KINDS:
            _fail("W2B_V2_TOPOLOGY_NODE_INVALID")
        global_coordinates = _coordinates(self.global_coordinates, allow_none=True)
        phase_local = _phase_local_coordinates(self.phase_local_coordinates)
        if global_coordinates is None and phase_local is None:
            _fail("W2B_V2_COORDINATES_INVALID")
        phases = _phase_instances(self.phase_instances, allow_empty=False)
        bases = _names(self.base_phases, allow_empty=False)
        expected_bases = tuple(sorted({item.base_phase for item in phases}))
        if bases != expected_bases:
            _fail("W2B_V2_PHASE_INSTANCE_INVALID")
        if phase_local is not None and not set(name for name, _coords in phase_local).issubset(
            {item.instance_name for item in phases}
        ):
            _fail("W2B_V2_COORDINATES_INVALID")
        evidence = _evidence_ids(self.evidence_record_ids)
        if len(evidence) != 1:
            _fail("W2B_V2_TOPOLOGY_OWNERSHIP_INVALID")
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "topology_component_id", component_id)
        object.__setattr__(self, "global_coordinates", global_coordinates)
        object.__setattr__(self, "phase_local_coordinates", phase_local)
        object.__setattr__(self, "phase_instances", phases)
        object.__setattr__(self, "base_phases", bases)
        object.__setattr__(self, "evidence_record_ids", evidence)


def _copy_topology_node(value: object) -> TopologyNode:
    if type(value) is not TopologyNode:
        _fail("W2B_V2_TOPOLOGY_NODE_INVALID")
    try:
        return TopologyNode(
            ordinal=value.ordinal,
            node_id=value.node_id,
            topology_component_id=value.topology_component_id,
            node_kind=value.node_kind,
            global_coordinates=value.global_coordinates,
            phase_local_coordinates=value.phase_local_coordinates,
            phase_instances=tuple(_copy_phase_instance(item) for item in value.phase_instances),
            base_phases=value.base_phases,
            evidence_record_ids=value.evidence_record_ids,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_TOPOLOGY_NODE_INVALID") from error


@_dataclass(frozen=True, slots=True)
class TopologySegment:
    """Only an explicit sequential ZPF or explicit tieline edge."""

    ordinal: int
    segment_id: str
    topology_component_id: str
    segment_kind: str
    start_node_id: str
    end_node_id: str
    phase_instances: tuple[PhaseInstanceV2, ...]
    base_phases: tuple[str, ...]
    evidence_record_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        ordinal = _integer(self.ordinal)
        segment_id = _token(self.segment_id, "W2B_V2_TOPOLOGY_SEGMENT_INVALID", maximum=128)
        component_id = _token(
            self.topology_component_id,
            "W2B_V2_TOPOLOGY_SEGMENT_INVALID",
            maximum=128,
        )
        if type(self.segment_kind) is not str or self.segment_kind not in _TOPOLOGY_SEGMENT_KINDS:
            _fail("W2B_V2_TOPOLOGY_SEGMENT_INVALID")
        start = _token(self.start_node_id, "W2B_V2_TOPOLOGY_SEGMENT_INVALID", maximum=128)
        end = _token(self.end_node_id, "W2B_V2_TOPOLOGY_SEGMENT_INVALID", maximum=128)
        if start == end:
            _fail("W2B_V2_TOPOLOGY_SEGMENT_INVALID")
        phases = _phase_instances(self.phase_instances, allow_empty=False)
        bases = _names(self.base_phases, allow_empty=False)
        if bases != tuple(sorted({item.base_phase for item in phases})):
            _fail("W2B_V2_PHASE_INSTANCE_INVALID")
        evidence = _evidence_ids(self.evidence_record_ids)
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "segment_id", segment_id)
        object.__setattr__(self, "topology_component_id", component_id)
        object.__setattr__(self, "start_node_id", start)
        object.__setattr__(self, "end_node_id", end)
        object.__setattr__(self, "phase_instances", phases)
        object.__setattr__(self, "base_phases", bases)
        object.__setattr__(self, "evidence_record_ids", evidence)


def _copy_topology_segment(value: object) -> TopologySegment:
    if type(value) is not TopologySegment:
        _fail("W2B_V2_TOPOLOGY_SEGMENT_INVALID")
    try:
        return TopologySegment(
            ordinal=value.ordinal,
            segment_id=value.segment_id,
            topology_component_id=value.topology_component_id,
            segment_kind=value.segment_kind,
            start_node_id=value.start_node_id,
            end_node_id=value.end_node_id,
            phase_instances=tuple(_copy_phase_instance(item) for item in value.phase_instances),
            base_phases=value.base_phases,
            evidence_record_ids=value.evidence_record_ids,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_TOPOLOGY_SEGMENT_INVALID") from error


@_dataclass(frozen=True, slots=True)
class TopologyRegion:
    """Invariant or multiphase topology represented as a hyperedge."""

    ordinal: int
    region_id: str
    topology_component_id: str
    region_kind: str
    member_node_ids: tuple[str, ...]
    phase_instances: tuple[PhaseInstanceV2, ...]
    base_phases: tuple[str, ...]
    evidence_record_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        ordinal = _integer(self.ordinal)
        region_id = _token(self.region_id, "W2B_V2_TOPOLOGY_REGION_INVALID", maximum=128)
        component_id = _token(
            self.topology_component_id,
            "W2B_V2_TOPOLOGY_REGION_INVALID",
            maximum=128,
        )
        if type(self.region_kind) is not str or self.region_kind not in _TOPOLOGY_REGION_KINDS:
            _fail("W2B_V2_TOPOLOGY_REGION_INVALID")
        if (
            type(self.member_node_ids) is not tuple
            or not self.member_node_ids
            or len(self.member_node_ids) > _MAX_COLLECTION
        ):
            _fail("W2B_V2_TOPOLOGY_REGION_INVALID")
        members = tuple(
            _token(item, "W2B_V2_TOPOLOGY_REGION_INVALID", maximum=128)
            for item in self.member_node_ids
        )
        if len(set(members)) != len(members):
            _fail("W2B_V2_TOPOLOGY_REGION_INVALID")
        phases = _phase_instances(self.phase_instances, allow_empty=False)
        bases = _names(self.base_phases, allow_empty=False)
        if bases != tuple(sorted({item.base_phase for item in phases})):
            _fail("W2B_V2_PHASE_INSTANCE_INVALID")
        minimum_base_phases = 3 if self.region_kind == "INVARIANT_REGION" else 2
        if len(bases) < minimum_base_phases:
            _fail("W2B_V2_TOPOLOGY_REGION_INVALID")
        evidence = _evidence_ids(self.evidence_record_ids)
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "region_id", region_id)
        object.__setattr__(self, "topology_component_id", component_id)
        object.__setattr__(self, "member_node_ids", members)
        object.__setattr__(self, "phase_instances", phases)
        object.__setattr__(self, "base_phases", bases)
        object.__setattr__(self, "evidence_record_ids", evidence)


def _copy_topology_region(value: object) -> TopologyRegion:
    if type(value) is not TopologyRegion:
        _fail("W2B_V2_TOPOLOGY_REGION_INVALID")
    try:
        return TopologyRegion(
            ordinal=value.ordinal,
            region_id=value.region_id,
            topology_component_id=value.topology_component_id,
            region_kind=value.region_kind,
            member_node_ids=value.member_node_ids,
            phase_instances=tuple(_copy_phase_instance(item) for item in value.phase_instances),
            base_phases=value.base_phases,
            evidence_record_ids=value.evidence_record_ids,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_TOPOLOGY_REGION_INVALID") from error


@_dataclass(frozen=True, slots=True)
class MappingDiagnosticsV2:
    """Explicit observability and budget evidence for one mapping run."""

    instrumentation_id: str
    instrumentation_version: str
    instrumentation_level: str
    backend_name: str
    backend_version: str
    completeness: str
    full_attempt_ledger: bool
    failed_attempts_retained: bool
    merged_attempts_retained: bool
    abandoned_attempts_retained: bool
    unresolved_branch_count: int
    attempt_budget: int
    attempts_consumed: int
    attempt_budget_exhausted: bool
    evidence_record_budget: int
    evidence_records_consumed: int
    evidence_record_budget_exhausted: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "instrumentation_id", _token(self.instrumentation_id, "W2B_V2_DIAGNOSTICS_INVALID"))
        object.__setattr__(self, "instrumentation_version", _token(self.instrumentation_version, "W2B_V2_DIAGNOSTICS_INVALID"))
        if type(self.instrumentation_level) is not str or self.instrumentation_level not in (
            "FULL_INTERNAL_ATTEMPT_LEDGER",
            "PARTIAL_BACKEND_OBSERVABILITY",
        ):
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        object.__setattr__(self, "backend_name", _token(self.backend_name, "W2B_V2_DIAGNOSTICS_INVALID"))
        object.__setattr__(self, "backend_version", _token(self.backend_version, "W2B_V2_DIAGNOSTICS_INVALID"))
        if type(self.completeness) is not str or self.completeness not in ("COMPLETE", "PARTIAL"):
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        if self.completeness == "COMPLETE":
            _fail("W2B_V2_COMPLETE_CAPABILITY_UNAVAILABLE")
        full = _boolean(self.full_attempt_ledger)
        failed = _boolean(self.failed_attempts_retained)
        merged = _boolean(self.merged_attempts_retained)
        abandoned = _boolean(self.abandoned_attempts_retained)
        unresolved = _integer(self.unresolved_branch_count)
        budget = _integer(
            self.attempt_budget,
            maximum=_MAX_MAPPING_ATTEMPTS,
        )
        consumed = _integer(self.attempts_consumed, maximum=budget)
        exhausted = _boolean(self.attempt_budget_exhausted)
        evidence_budget = _integer(
            self.evidence_record_budget,
            maximum=_MAX_MAPPING_EVIDENCE_RECORDS,
        )
        evidence_consumed = _integer(
            self.evidence_records_consumed,
            maximum=evidence_budget,
        )
        evidence_exhausted = _boolean(self.evidence_record_budget_exhausted)
        if (
            (exhausted and (budget == 0 or consumed != budget))
            or (
                evidence_exhausted
                and (evidence_budget == 0 or evidence_consumed != evidence_budget)
            )
        ):
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        object.__setattr__(self, "unresolved_branch_count", unresolved)
        object.__setattr__(self, "attempt_budget", budget)
        object.__setattr__(self, "attempts_consumed", consumed)
        object.__setattr__(self, "evidence_record_budget", evidence_budget)
        object.__setattr__(self, "evidence_records_consumed", evidence_consumed)

    @property
    def budget_exhausted(self) -> bool:
        return self.attempt_budget_exhausted or self.evidence_record_budget_exhausted


def _copy_mapping_diagnostics(value: object) -> MappingDiagnosticsV2:
    if type(value) is not MappingDiagnosticsV2:
        _fail("W2B_V2_DIAGNOSTICS_INVALID")
    try:
        return MappingDiagnosticsV2(
            instrumentation_id=value.instrumentation_id,
            instrumentation_version=value.instrumentation_version,
            instrumentation_level=value.instrumentation_level,
            backend_name=value.backend_name,
            backend_version=value.backend_version,
            completeness=value.completeness,
            full_attempt_ledger=value.full_attempt_ledger,
            failed_attempts_retained=value.failed_attempts_retained,
            merged_attempts_retained=value.merged_attempts_retained,
            abandoned_attempts_retained=value.abandoned_attempts_retained,
            unresolved_branch_count=value.unresolved_branch_count,
            attempt_budget=value.attempt_budget,
            attempts_consumed=value.attempts_consumed,
            attempt_budget_exhausted=value.attempt_budget_exhausted,
            evidence_record_budget=value.evidence_record_budget,
            evidence_records_consumed=value.evidence_records_consumed,
            evidence_record_budget_exhausted=value.evidence_record_budget_exhausted,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_DIAGNOSTICS_INVALID") from error


def _phases_within_domain(
    phase_instances: tuple[PhaseInstanceV2, ...],
    effective_phases: set[str],
) -> bool:
    return all(item.base_phase in effective_phases for item in phase_instances)


def _preflight_record_tuple(
    value: object,
    record_type: type,
    maximum: int,
    reason: str,
) -> tuple:
    """Cheap exact outer/type/order gate used before any deep reconstruction."""

    if type(value) is not tuple or not value or len(value) > maximum:
        _fail(reason)
    for ordinal, record in enumerate(value):
        if type(record) is not record_type:
            _fail(reason)
        try:
            observed = record.ordinal
        except Exception as error:
            raise PathContractV2Error(reason) from error
        if type(observed) is not int or observed != ordinal:
            _fail("W2B_V2_ATTEMPT_ORDER_INVALID")
    return value


def _preflight_optional_record_tuple(
    value: object,
    record_type: type,
    maximum: int,
    reason: str,
) -> tuple:
    if type(value) is not tuple or len(value) > maximum:
        _fail(reason)
    for ordinal, record in enumerate(value):
        if type(record) is not record_type:
            _fail(reason)
        try:
            observed = record.ordinal
        except Exception as error:
            raise PathContractV2Error(reason) from error
        if type(observed) is not int or observed != ordinal:
            _fail("W2B_V2_ATTEMPT_ORDER_INVALID")
    return value


def _preflight_nested_tuple(value: object, reason: str) -> int:
    if type(value) is not tuple or len(value) > _MAX_COLLECTION:
        _fail(reason)
    return len(value)


def _preflight_phase_local(value: object, reason: str) -> int:
    if value is None:
        return 0
    outer_count = _preflight_nested_tuple(value, reason)
    total = outer_count
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            _fail(reason)
        total += _preflight_nested_tuple(pair[1], reason)
        if total > _MAX_AGGREGATE_NESTED_ITEMS:
            _fail("W2B_V2_WORK_BUDGET_EXCEEDED")
    return total


def _preflight_mapping_ledger(value: object) -> None:
    """Bound aggregate reconstruction work, counting repeated aliases each time."""

    try:
        if type(value.database) is not DatabaseIdentityV2:
            _fail("W2B_V2_DATABASE_INVALID")
        if type(value.execution_binding) is not ExecutionBindingV2:
            _fail("W2B_V2_EXECUTION_BINDING_INVALID")
        if type(value.phase_domain) is not PhaseDomainV2:
            _fail("W2B_V2_PHASE_DOMAIN_INVALID")
        if type(value.diagnostics) is not MappingDiagnosticsV2:
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        attempts = _preflight_optional_record_tuple(
            value.attempts,
            MappingAttemptRecord,
            _MAX_MAPPING_ATTEMPTS,
            "W2B_V2_MAPPING_LEDGER_INVALID",
        )
        evidence_records = _preflight_optional_record_tuple(
            value.postrun_evidence,
            MappingPostrunEvidenceRecordV2,
            _MAX_MAPPING_EVIDENCE_RECORDS,
            "W2B_V2_MAPPING_LEDGER_INVALID",
        )
        if (
            type(value.diagnostics.attempt_budget) is not int
            or not (0 <= value.diagnostics.attempt_budget <= _MAX_MAPPING_ATTEMPTS)
            or type(value.diagnostics.attempts_consumed) is not int
            or value.diagnostics.attempts_consumed != len(attempts)
            or value.diagnostics.attempts_consumed > value.diagnostics.attempt_budget
            or type(value.diagnostics.attempt_budget_exhausted) is not bool
            or type(value.diagnostics.evidence_record_budget) is not int
            or not (
                0
                <= value.diagnostics.evidence_record_budget
                <= _MAX_MAPPING_EVIDENCE_RECORDS
            )
            or type(value.diagnostics.evidence_records_consumed) is not int
            or value.diagnostics.evidence_records_consumed != len(evidence_records)
            or value.diagnostics.evidence_records_consumed
            > value.diagnostics.evidence_record_budget
            or type(value.diagnostics.evidence_record_budget_exhausted) is not bool
        ):
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        nodes = _preflight_optional_record_tuple(
            value.topology_nodes,
            TopologyNode,
            _MAX_TOPOLOGY_NODES,
            "W2B_V2_MAPPING_LEDGER_INVALID",
        )
        segments = _preflight_optional_record_tuple(
            value.segments,
            TopologySegment,
            _MAX_TOPOLOGY_SEGMENTS,
            "W2B_V2_MAPPING_LEDGER_INVALID",
        )
        regions = _preflight_optional_record_tuple(
            value.regions,
            TopologyRegion,
            _MAX_TOPOLOGY_REGIONS,
            "W2B_V2_MAPPING_LEDGER_INVALID",
        )
        total = (
            len(attempts)
            + len(evidence_records)
            + len(nodes)
            + len(segments)
            + len(regions)
        )
        for phase_tuple in (
            value.phase_domain.candidate_phases,
            value.phase_domain.requested_phases,
            value.phase_domain.excluded_phases,
            value.phase_domain.effective_phases,
        ):
            total += _preflight_nested_tuple(phase_tuple, "W2B_V2_PHASE_DOMAIN_INVALID")
        for attempt in attempts:
            total += _preflight_nested_tuple(
                attempt.conditions,
                "W2B_V2_MAPPING_LEDGER_INVALID",
            )
            if attempt.coordinates is not None:
                total += _preflight_nested_tuple(
                    attempt.coordinates,
                    "W2B_V2_MAPPING_LEDGER_INVALID",
                )
            total += _preflight_phase_local(
                attempt.phase_local_coordinates,
                "W2B_V2_MAPPING_LEDGER_INVALID",
            )
            total += _preflight_nested_tuple(
                attempt.phase_instances,
                "W2B_V2_MAPPING_LEDGER_INVALID",
            )
            if total > _MAX_AGGREGATE_NESTED_ITEMS:
                _fail("W2B_V2_WORK_BUDGET_EXCEEDED")
        for evidence in evidence_records:
            for nested in (
                evidence.member_node_ids,
                evidence.phase_instances,
            ):
                total += _preflight_nested_tuple(
                    nested,
                    "W2B_V2_MAPPING_LEDGER_INVALID",
                )
            if evidence.global_coordinates is not None:
                total += _preflight_nested_tuple(
                    evidence.global_coordinates,
                    "W2B_V2_MAPPING_LEDGER_INVALID",
                )
            total += _preflight_phase_local(
                evidence.phase_local_coordinates,
                "W2B_V2_MAPPING_LEDGER_INVALID",
            )
            if total > _MAX_AGGREGATE_NESTED_ITEMS:
                _fail("W2B_V2_WORK_BUDGET_EXCEEDED")
        for node in nodes:
            if node.global_coordinates is not None:
                total += _preflight_nested_tuple(
                    node.global_coordinates,
                    "W2B_V2_MAPPING_LEDGER_INVALID",
                )
            total += _preflight_phase_local(
                node.phase_local_coordinates,
                "W2B_V2_MAPPING_LEDGER_INVALID",
            )
            for nested in (
                node.phase_instances,
                node.base_phases,
                node.evidence_record_ids,
            ):
                total += _preflight_nested_tuple(nested, "W2B_V2_MAPPING_LEDGER_INVALID")
            if total > _MAX_AGGREGATE_NESTED_ITEMS:
                _fail("W2B_V2_WORK_BUDGET_EXCEEDED")
        for segment in segments:
            for nested in (
                segment.phase_instances,
                segment.base_phases,
                segment.evidence_record_ids,
            ):
                total += _preflight_nested_tuple(nested, "W2B_V2_MAPPING_LEDGER_INVALID")
            if total > _MAX_AGGREGATE_NESTED_ITEMS:
                _fail("W2B_V2_WORK_BUDGET_EXCEEDED")
        for region in regions:
            for nested in (
                region.member_node_ids,
                region.phase_instances,
                region.base_phases,
                region.evidence_record_ids,
            ):
                total += _preflight_nested_tuple(nested, "W2B_V2_MAPPING_LEDGER_INVALID")
            if total > _MAX_AGGREGATE_NESTED_ITEMS:
                _fail("W2B_V2_WORK_BUDGET_EXCEEDED")
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_MAPPING_LEDGER_INVALID") from error


def _validate_mapping_multiplicity_groups(
    phase_groups: tuple[tuple[PhaseInstanceV2, ...], ...],
) -> None:
    explicit_bases: set[str] = set()
    for group in phase_groups:
        counts: dict[str, int] = {}
        for item in group:
            counts[item.base_phase] = counts.get(item.base_phase, 0) + 1
            if item.instance_index > 1:
                explicit_bases.add(item.base_phase)
        explicit_bases.update(base for base, count in counts.items() if count > 1)
    for group in phase_groups:
        for item in group:
            if (
                item.base_phase in explicit_bases
                and item.instance_name
                != f"{item.base_phase}#{item.instance_index}"
            ):
                _fail("W2B_V2_MULTIPLICITY_INVALID")


def _node_coordinates_equal(left: TopologyNode, right: TopologyNode) -> bool:
    return (
        left.global_coordinates == right.global_coordinates
        and left.phase_local_coordinates == right.phase_local_coordinates
    )


@_dataclass(frozen=True, slots=True)
class RawMappingLedgerV2:
    """Unfiltered attempt chronology plus separately reported final topology."""

    database: DatabaseIdentityV2
    execution_binding: ExecutionBindingV2
    phase_domain: PhaseDomainV2
    feature: str
    strategy: str
    attempts: tuple[MappingAttemptRecord, ...]
    postrun_evidence: tuple[MappingPostrunEvidenceRecordV2, ...]
    topology_nodes: tuple[TopologyNode, ...]
    segments: tuple[TopologySegment, ...]
    regions: tuple[TopologyRegion, ...]
    diagnostics: MappingDiagnosticsV2
    terminal_reason: str

    def __post_init__(self) -> None:
        _preflight_mapping_ledger(self)
        database = _copy_database(self.database)
        binding = _copy_binding(self.execution_binding)
        domain = _copy_domain(self.phase_domain, database)
        if type(self.feature) is not str or self.feature not in _MAPPING_STRATEGIES:
            _fail("W2B_V2_MAPPING_LEDGER_INVALID")
        if type(self.strategy) is not str or self.strategy != _MAPPING_STRATEGIES[self.feature]:
            _fail("W2B_V2_MAPPING_LEDGER_INVALID")
        attempts = _ordered_exact(
            self.attempts,
            MappingAttemptRecord,
            _copy_mapping_attempt,
            allow_empty=True,
            reason="W2B_V2_MAPPING_LEDGER_INVALID",
        )
        evidence_records = _ordered_exact(
            self.postrun_evidence,
            MappingPostrunEvidenceRecordV2,
            _copy_mapping_postrun_evidence,
            allow_empty=True,
            reason="W2B_V2_MAPPING_LEDGER_INVALID",
        )
        nodes = _ordered_exact(
            self.topology_nodes,
            TopologyNode,
            _copy_topology_node,
            allow_empty=True,
            reason="W2B_V2_MAPPING_LEDGER_INVALID",
        )
        segments = _ordered_exact(
            self.segments,
            TopologySegment,
            _copy_topology_segment,
            allow_empty=True,
            reason="W2B_V2_MAPPING_LEDGER_INVALID",
        )
        regions = _ordered_exact(
            self.regions,
            TopologyRegion,
            _copy_topology_region,
            allow_empty=True,
            reason="W2B_V2_MAPPING_LEDGER_INVALID",
        )
        diagnostics = _copy_mapping_diagnostics(self.diagnostics)
        if (
            diagnostics.attempts_consumed != len(attempts)
            or diagnostics.evidence_records_consumed != len(evidence_records)
        ):
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        if not attempts and not evidence_records:
            _fail("W2B_V2_MAPPING_LEDGER_INVALID")
        if type(self.terminal_reason) is not str or self.terminal_reason not in _MAPPING_TERMINALS:
            _fail("W2B_V2_MAPPING_TERMINAL_INVALID")
        if self.terminal_reason == "COMPLETE":
            _fail("W2B_V2_COMPLETE_CAPABILITY_UNAVAILABLE")

        attempt_by_id = {attempt.attempt_id: attempt for attempt in attempts}
        if len(attempt_by_id) != len(attempts):
            _fail("W2B_V2_ATTEMPT_INVALID")
        evidence_by_id = {
            evidence.evidence_id: evidence for evidence in evidence_records
        }
        if (
            len(evidence_by_id) != len(evidence_records)
            or set(evidence_by_id) & set(attempt_by_id)
            or len(
                {
                    (evidence.source_collection, evidence.source_record_index)
                    for evidence in evidence_records
                }
            )
            != len(evidence_records)
        ):
            _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
        node_by_id = {node.node_id: node for node in nodes}
        if len(node_by_id) != len(nodes):
            _fail("W2B_V2_TOPOLOGY_NODE_INVALID")
        if len({segment.segment_id for segment in segments}) != len(segments):
            _fail("W2B_V2_TOPOLOGY_SEGMENT_INVALID")
        if len({region.region_id for region in regions}) != len(regions):
            _fail("W2B_V2_TOPOLOGY_REGION_INVALID")

        effective = set(domain.effective_phases)
        for attempt in attempts:
            if not _phases_within_domain(attempt.phase_instances, effective):
                _fail("W2B_V2_PHASE_DOMAIN_INVALID")
        for evidence in evidence_records:
            if not _phases_within_domain(evidence.phase_instances, effective):
                _fail("W2B_V2_PHASE_DOMAIN_INVALID")
        _validate_mapping_multiplicity_groups(
            tuple(attempt.phase_instances for attempt in attempts)
            + tuple(evidence.phase_instances for evidence in evidence_records)
            + tuple(node.phase_instances for node in nodes)
            + tuple(segment.phase_instances for segment in segments)
            + tuple(region.phase_instances for region in regions)
        )

        owner_evidence_ids: set[str] = set()
        starting_components: set[str] = set()
        exit_components: set[str] = set()
        for node in nodes:
            if not _phases_within_domain(node.phase_instances, effective):
                _fail("W2B_V2_PHASE_DOMAIN_INVALID")
            evidence_id = node.evidence_record_ids[0]
            evidence = evidence_by_id.get(evidence_id)
            expected_bases = tuple(
                sorted({item.base_phase for item in evidence.phase_instances})
            ) if evidence is not None else tuple()
            if (
                evidence is None
                or evidence.status != "RESOLVED"
                or evidence.topology_target_kind != "NODE"
                or evidence.topology_target_id != node.node_id
                or evidence.topology_target_subkind != node.node_kind
                or evidence.topology_component_id != node.topology_component_id
                or evidence.global_coordinates != node.global_coordinates
                or evidence.phase_local_coordinates != node.phase_local_coordinates
                or evidence.phase_instances != node.phase_instances
                or expected_bases != node.base_phases
                or evidence_id in owner_evidence_ids
            ):
                _fail("W2B_V2_TOPOLOGY_OWNERSHIP_INVALID")
            owner_evidence_ids.add(evidence_id)
            if evidence.evidence_role == "STARTING_NODE_OBSERVATION":
                if node.topology_component_id in starting_components:
                    _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
                starting_components.add(node.topology_component_id)
            elif evidence.evidence_role == "EXIT_NODE_OBSERVATION":
                if node.topology_component_id in exit_components:
                    _fail("W2B_V2_POSTRUN_EVIDENCE_INVALID")
                exit_components.add(node.topology_component_id)

        seen_tielines: set[tuple[str, frozenset[str]]] = set()
        for segment in segments:
            start = node_by_id.get(segment.start_node_id)
            end = node_by_id.get(segment.end_node_id)
            if (
                start is None
                or end is None
                or start.topology_component_id != segment.topology_component_id
                or end.topology_component_id != segment.topology_component_id
            ):
                _fail("W2B_V2_TOPOLOGY_REFERENCE_INVALID")
            endpoint_intersection = {
                item.instance_name for item in start.phase_instances
            } & {item.instance_name for item in end.phase_instances}
            segment_instances = {
                item.instance_name for item in segment.phase_instances
            }
            if not segment_instances.issubset(endpoint_intersection):
                _fail("W2B_V2_LINE_PHASE_INVALID")
            if len(segment.evidence_record_ids) != 1:
                _fail("W2B_V2_TOPOLOGY_OWNERSHIP_INVALID")
            evidence_id = segment.evidence_record_ids[0]
            evidence = evidence_by_id.get(evidence_id)
            if (
                evidence is None
                or evidence.status != "RESOLVED"
                or evidence.topology_target_kind != "SEGMENT"
                or evidence.topology_target_subkind != segment.segment_kind
                or evidence.topology_target_id != segment.segment_id
                or evidence.topology_component_id != segment.topology_component_id
                or evidence.member_node_ids
                != (segment.start_node_id, segment.end_node_id)
                or evidence.phase_instances != segment.phase_instances
                or tuple(sorted({item.base_phase for item in evidence.phase_instances}))
                != segment.base_phases
                or evidence_id in owner_evidence_ids
            ):
                _fail("W2B_V2_TOPOLOGY_OWNERSHIP_INVALID")
            owner_evidence_ids.add(evidence_id)
            if segment.segment_kind == "EXPLICIT_TIELINE":
                tieline_key = (
                    segment.topology_component_id,
                    frozenset((segment.start_node_id, segment.end_node_id)),
                )
                if (
                    start.node_kind != "TIELINE_ENDPOINT"
                    or end.node_kind != "TIELINE_ENDPOINT"
                    or segment_instances != endpoint_intersection
                    or len(segment.phase_instances) != 2
                    or _node_coordinates_equal(start, end)
                    or tieline_key in seen_tielines
                ):
                    _fail("W2B_V2_TIELINE_INVALID")
                seen_tielines.add(tieline_key)
        for region in regions:
            members = tuple(node_by_id.get(node_id) for node_id in region.member_node_ids)
            if any(node is None for node in members) or any(
                node.topology_component_id != region.topology_component_id  # type: ignore[union-attr]
                for node in members
            ):
                _fail("W2B_V2_TOPOLOGY_REFERENCE_INVALID")
            member_instances = {
                item.instance_name
                for node in members
                for item in node.phase_instances  # type: ignore[union-attr]
            }
            if not {item.instance_name for item in region.phase_instances}.issubset(member_instances):
                _fail("W2B_V2_TOPOLOGY_REFERENCE_INVALID")
            if len(region.evidence_record_ids) != 1:
                _fail("W2B_V2_TOPOLOGY_OWNERSHIP_INVALID")
            evidence_id = region.evidence_record_ids[0]
            evidence = evidence_by_id.get(evidence_id)
            if (
                evidence is None
                or evidence.status != "RESOLVED"
                or evidence.topology_target_kind != "REGION"
                or evidence.topology_target_subkind != region.region_kind
                or evidence.topology_target_id != region.region_id
                or evidence.topology_component_id != region.topology_component_id
                or evidence.member_node_ids != region.member_node_ids
                or evidence.phase_instances != region.phase_instances
                or tuple(sorted({item.base_phase for item in evidence.phase_instances}))
                != region.base_phases
                or evidence_id in owner_evidence_ids
            ):
                _fail("W2B_V2_TOPOLOGY_OWNERSHIP_INVALID")
            owner_evidence_ids.add(evidence_id)

        unresolved_records = tuple(
            evidence
            for evidence in evidence_records
            if evidence.evidence_role == _POSTRUN_UNRESOLVED_ROLE
        )
        for evidence in unresolved_records:
            for node_id in evidence.member_node_ids:
                node = node_by_id.get(node_id)
                if (
                    node is None
                    or node.topology_component_id != evidence.topology_component_id
                ):
                    _fail("W2B_V2_TOPOLOGY_REFERENCE_INVALID")
        if diagnostics.unresolved_branch_count != len(unresolved_records):
            _fail("W2B_V2_UNRESOLVED_BRANCHES")
        resolved_evidence_ids = {
            evidence.evidence_id
            for evidence in evidence_records
            if evidence.status == "RESOLVED"
        }
        if resolved_evidence_ids != owner_evidence_ids:
            _fail("W2B_V2_TOPOLOGY_OWNERSHIP_INVALID")

        if diagnostics.budget_exhausted:
            if self.terminal_reason != "BUDGET_EXHAUSTED":
                _fail("W2B_V2_BUDGET_EXHAUSTED")
        elif diagnostics.unresolved_branch_count > 0:
            if self.terminal_reason != "PARTIAL_UNRESOLVED_BRANCHES":
                _fail("W2B_V2_UNRESOLVED_BRANCHES")
        elif self.terminal_reason == "TOPOLOGY_OBSERVED_DIAGNOSTICS_PARTIAL" and not nodes:
            _fail("W2B_V2_MAPPING_TERMINAL_INVALID")
        if self.terminal_reason in ("PARTIAL_UNRESOLVED_BRANCHES", "BUDGET_EXHAUSTED"):
            if diagnostics.completeness != "PARTIAL":
                _fail("W2B_V2_MAPPING_TERMINAL_INVALID")
        if (
            self.terminal_reason == "PARTIAL_UNRESOLVED_BRANCHES"
            and diagnostics.unresolved_branch_count == 0
        ):
            _fail("W2B_V2_MAPPING_TERMINAL_INVALID")
        if self.terminal_reason == "BUDGET_EXHAUSTED" and not diagnostics.budget_exhausted:
            _fail("W2B_V2_MAPPING_TERMINAL_INVALID")
        if self.terminal_reason == "NO_PROGRESS" and nodes:
            _fail("W2B_V2_MAPPING_TERMINAL_INVALID")

        object.__setattr__(self, "database", database)
        object.__setattr__(self, "execution_binding", binding)
        object.__setattr__(self, "phase_domain", domain)
        object.__setattr__(self, "attempts", attempts)
        object.__setattr__(self, "postrun_evidence", evidence_records)
        object.__setattr__(self, "topology_nodes", nodes)
        object.__setattr__(self, "segments", segments)
        object.__setattr__(self, "regions", regions)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def topology_component_ids(self) -> tuple[str, ...]:
        return tuple(sorted({node.topology_component_id for node in self.topology_nodes}))

    @property
    def is_diagnostics_complete(self) -> bool:
        return False


def _copy_mapping_ledger(value: object) -> RawMappingLedgerV2:
    if type(value) is not RawMappingLedgerV2:
        _fail("W2B_V2_MAPPING_LEDGER_INVALID")
    _preflight_mapping_ledger(value)
    try:
        return RawMappingLedgerV2(
            database=_copy_database(value.database),
            execution_binding=_copy_binding(value.execution_binding),
            phase_domain=PhaseDomainV2(
                candidate_phases=value.phase_domain.candidate_phases,
                requested_phases=value.phase_domain.requested_phases,
                excluded_phases=value.phase_domain.excluded_phases,
                effective_phases=value.phase_domain.effective_phases,
            ),
            feature=value.feature,
            strategy=value.strategy,
            attempts=tuple(_copy_mapping_attempt(item) for item in value.attempts),
            postrun_evidence=tuple(
                _copy_mapping_postrun_evidence(item)
                for item in value.postrun_evidence
            ),
            topology_nodes=tuple(_copy_topology_node(item) for item in value.topology_nodes),
            segments=tuple(_copy_topology_segment(item) for item in value.segments),
            regions=tuple(_copy_topology_region(item) for item in value.regions),
            diagnostics=_copy_mapping_diagnostics(value.diagnostics),
            terminal_reason=value.terminal_reason,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_MAPPING_LEDGER_INVALID") from error


_RESULT_DENIAL_FLAGS = frozenset(
    {
        "acceptance_claim",
        "counts_toward_feature_coverage",
        "production_use",
        "release_authorized",
    }
)
_RESULT_DENIAL_VALUES = _MappingProxyType(
    {
        "acceptance_claim": False,
        "counts_toward_feature_coverage": False,
        "production_use": "DENIED",
        "release_authorized": False,
    }
)
_RESULT_TYPE_SEAL = "_wave2b_v2_type_sealed"


class _SealedResultMeta(type):
    """Prevent ordinary subclassing/mutation of public result denial flags.

    This is an exact in-process DTO boundary, not a hostile-code sandbox:
    direct ``type.__setattr__``/``object.__setattr__`` calls can bypass normal
    Python hooks.  Every consumer must therefore reconstruct the exact result
    type at its own boundary, just as these result constructors reconstruct
    their ledgers.  No same-process Python seal is claimed to be unforgeable.
    """

    def __getattribute__(cls, name: str) -> object:
        if name in _RESULT_DENIAL_FLAGS:
            return _RESULT_DENIAL_VALUES[name]
        return super().__getattribute__(name)

    def __setattr__(cls, name: str, value: object) -> None:
        if cls.__dict__.get(_RESULT_TYPE_SEAL) is True:
            raise TypeError("Wave 2B V2 result type is sealed")
        super().__setattr__(name, value)

    def __delattr__(cls, name: str) -> None:
        if cls.__dict__.get(_RESULT_TYPE_SEAL) is True:
            raise TypeError("Wave 2B V2 result type is sealed")
        super().__delattr__(name)


@_dataclass(frozen=True, slots=True)
class MappingResultV2(metaclass=_SealedResultMeta):
    """Public fail-closed mapping result; it conveys no acceptance claim."""

    ledger: RawMappingLedgerV2

    acceptance_claim: _ClassVar[bool] = False
    counts_toward_feature_coverage: _ClassVar[bool] = False
    production_use: _ClassVar[str] = "DENIED"
    release_authorized: _ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("MappingResultV2 is sealed and cannot be subclassed")

    def __getattribute__(self, name: str) -> object:
        if name in _RESULT_DENIAL_FLAGS:
            return _RESULT_DENIAL_VALUES[name]
        return object.__getattribute__(self, name)

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "ledger", _copy_mapping_ledger(self.ledger))
        except PathContractV2Error:
            raise
        except Exception as error:
            raise PathContractV2Error("W2B_V2_RESULT_INVALID") from error

    @property
    def terminal_reason(self) -> str:
        return self.ledger.terminal_reason

    @property
    def failed_attempts(self) -> tuple[MappingAttemptRecord, ...]:
        return tuple(item for item in self.ledger.attempts if item.outcome == "FAILED")


type.__setattr__(MappingResultV2, _RESULT_TYPE_SEAL, True)


_SOLID_ATTEMPT_OUTCOMES = frozenset({"ACCEPTED", "FAILED", "MERGED", "ABANDONED"})
_SOLID_TERMINALS = frozenset(
    {
        "EQUILIBRIUM_NO_LIQUID_REACHED",
        "SCHEIL_LIQUID_THRESHOLD_REACHED",
        "TERMINAL_STATE_OBSERVED_DIAGNOSTICS_PARTIAL",
        "PARTIAL_UNRESOLVED_BRANCHES",
        "BUDGET_EXHAUSTED",
        "BACKEND_TERMINATED",
        "NO_PROGRESS",
    }
)


@_dataclass(frozen=True, slots=True)
class PhaseFractionV2:
    """Raw/canonical fraction assigned to one exact phase instance."""

    phase_instance: PhaseInstanceV2
    fraction: Binary64FractionV2

    def __post_init__(self) -> None:
        object.__setattr__(self, "phase_instance", _copy_phase_instance(self.phase_instance))
        object.__setattr__(self, "fraction", _copy_fraction(self.fraction))


def _copy_phase_fraction(value: object) -> PhaseFractionV2:
    if type(value) is not PhaseFractionV2:
        _fail("W2B_V2_SOLID_PHASE_SUM_INVALID")
    try:
        return PhaseFractionV2(
            phase_instance=_copy_phase_instance(value.phase_instance),
            fraction=_copy_fraction(value.fraction),
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_SOLID_PHASE_SUM_INVALID") from error


def _phase_fractions(
    value: object,
    *,
    allow_empty: bool,
) -> tuple[PhaseFractionV2, ...]:
    if type(value) is not tuple or (not value and not allow_empty) or len(value) > _MAX_COLLECTION:
        _fail("W2B_V2_SOLID_PHASE_SUM_INVALID")
    rebuilt = tuple(_copy_phase_fraction(item) for item in value)
    instances = _phase_instances(
        tuple(item.phase_instance for item in rebuilt),
        allow_empty=allow_empty,
    )
    by_name = {item.phase_instance.instance_name: item for item in rebuilt}
    return tuple(by_name[item.instance_name] for item in instances)


def _balanced_solid_observation(
    solid_fraction: object,
    liquid_fraction: object,
    phase_fractions: object,
    liquid_composition: object,
) -> tuple[
    Binary64FractionV2,
    Binary64FractionV2,
    tuple[PhaseFractionV2, ...],
    tuple[CompositionEntryV2, ...],
]:
    solid = _copy_fraction(solid_fraction)
    liquid = _copy_fraction(liquid_fraction)
    if not _within_ulps(
        _math.fsum((solid.canonical_value, liquid.canonical_value)),
        1.0,
        _BALANCE_ULPS,
    ):
        _fail("W2B_V2_SOLID_BALANCE_INVALID")
    phases = _phase_fractions(
        phase_fractions,
        allow_empty=solid.canonical_value == 0.0,
    )
    phase_sum = _math.fsum(item.fraction.canonical_value for item in phases)
    if not _within_ulps(
        phase_sum,
        solid.canonical_value,
        max(_BALANCE_ULPS, len(phases)),
    ):
        _fail("W2B_V2_SOLID_PHASE_SUM_INVALID")
    if solid.canonical_value == 0.0 and phases:
        _fail("W2B_V2_SOLID_PHASE_SUM_INVALID")
    if liquid.canonical_value > 0.0:
        composition = _composition(
            liquid_composition,
            expected_components=None,
            allow_empty=False,
        )
    else:
        if type(liquid_composition) is not tuple or len(liquid_composition) != 0:
            _fail("W2B_V2_COMPOSITION_INVALID")
        composition = tuple()
    return solid, liquid, phases, composition


@_dataclass(frozen=True, slots=True)
class SolidificationAttemptRecord:
    """Chronological physical solver attempt; temperatures may move either way."""

    ordinal: int
    attempt_id: str
    stage: str
    conditions: tuple[tuple[str, float], ...]
    temperature_k: float
    outcome: str
    accepted_path_ordinal: int | None
    observed_solid_fraction: Binary64FractionV2 | None
    observed_liquid_fraction: Binary64FractionV2 | None
    observed_phase_fractions: tuple[PhaseFractionV2, ...]
    observed_liquid_composition: tuple[CompositionEntryV2, ...]
    reason_code: str | None

    def __post_init__(self) -> None:
        ordinal = _integer(self.ordinal)
        attempt_id = _token(self.attempt_id, "W2B_V2_SOLID_ATTEMPT_INVALID", maximum=128)
        stage = _token(self.stage, "W2B_V2_SOLID_ATTEMPT_INVALID", maximum=96)
        conditions = _coordinates(self.conditions, allow_none=False)
        temperature = _positive(self.temperature_k)
        if type(self.outcome) is not str or self.outcome not in _SOLID_ATTEMPT_OUTCOMES:
            _fail("W2B_V2_ATTEMPT_OUTCOME_INVALID")
        if self.accepted_path_ordinal is None:
            accepted_path_ordinal = None
        else:
            accepted_path_ordinal = _integer(self.accepted_path_ordinal)
        if self.reason_code is None:
            reason_code = None
        else:
            reason_code = _token(self.reason_code, "W2B_V2_SOLID_ATTEMPT_INVALID")

        if self.outcome in ("ACCEPTED", "MERGED"):
            if (
                accepted_path_ordinal is None
                or reason_code is not None
                or self.observed_solid_fraction is None
                or self.observed_liquid_fraction is None
            ):
                _fail("W2B_V2_SOLID_ATTEMPT_INVALID")
            solid, liquid, phases, composition = _balanced_solid_observation(
                self.observed_solid_fraction,
                self.observed_liquid_fraction,
                self.observed_phase_fractions,
                self.observed_liquid_composition,
            )
        else:
            if accepted_path_ordinal is not None or reason_code is None:
                _fail("W2B_V2_SOLID_ATTEMPT_INVALID")
            if self.observed_solid_fraction is None:
                solid = None
            else:
                solid = _copy_fraction(self.observed_solid_fraction)
            if self.observed_liquid_fraction is None:
                liquid = None
            else:
                liquid = _copy_fraction(self.observed_liquid_fraction)
            phases = _phase_fractions(self.observed_phase_fractions, allow_empty=True)
            composition = _composition(
                self.observed_liquid_composition,
                expected_components=None,
                allow_empty=True,
            )

        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "attempt_id", attempt_id)
        object.__setattr__(self, "stage", stage)
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "temperature_k", temperature)
        object.__setattr__(self, "accepted_path_ordinal", accepted_path_ordinal)
        object.__setattr__(self, "observed_solid_fraction", solid)
        object.__setattr__(self, "observed_liquid_fraction", liquid)
        object.__setattr__(self, "observed_phase_fractions", phases)
        object.__setattr__(self, "observed_liquid_composition", composition)
        object.__setattr__(self, "reason_code", reason_code)


def _copy_solid_attempt(value: object) -> SolidificationAttemptRecord:
    if type(value) is not SolidificationAttemptRecord:
        _fail("W2B_V2_SOLID_ATTEMPT_INVALID")
    try:
        return SolidificationAttemptRecord(
            ordinal=value.ordinal,
            attempt_id=value.attempt_id,
            stage=value.stage,
            conditions=value.conditions,
            temperature_k=value.temperature_k,
            outcome=value.outcome,
            accepted_path_ordinal=value.accepted_path_ordinal,
            observed_solid_fraction=(
                None
                if value.observed_solid_fraction is None
                else _copy_fraction(value.observed_solid_fraction)
            ),
            observed_liquid_fraction=(
                None
                if value.observed_liquid_fraction is None
                else _copy_fraction(value.observed_liquid_fraction)
            ),
            observed_phase_fractions=tuple(
                _copy_phase_fraction(item) for item in value.observed_phase_fractions
            ),
            observed_liquid_composition=tuple(
                _copy_composition_entry(item) for item in value.observed_liquid_composition
            ),
            reason_code=value.reason_code,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_SOLID_ATTEMPT_INVALID") from error


@_dataclass(frozen=True, slots=True)
class SolidificationPathPoint:
    """One accepted monotonic path point, never a failed/backtracked attempt."""

    ordinal: int
    provenance: str
    source_attempt_id: str | None
    source_row_index: int | None
    temperature_k: float
    solid_fraction: Binary64FractionV2
    liquid_fraction: Binary64FractionV2
    phase_fractions: tuple[PhaseFractionV2, ...]
    liquid_composition: tuple[CompositionEntryV2, ...]

    def __post_init__(self) -> None:
        ordinal = _integer(self.ordinal)
        if type(self.provenance) is not str or self.provenance not in (
            "BACKEND_ACCEPTED_ATTEMPT",
            "BACKEND_PUBLIC_PATH_ROW",
            "SYNTHETIC_INITIAL_STATE",
        ):
            _fail("W2B_V2_SOLID_POINT_INVALID")
        if self.provenance == "SYNTHETIC_INITIAL_STATE":
            if (
                self.source_attempt_id is not None
                or self.source_row_index is not None
                or ordinal != 0
            ):
                _fail("W2B_V2_SOLID_POINT_INVALID")
            source_attempt_id = None
            source_row_index = None
        elif self.provenance == "BACKEND_ACCEPTED_ATTEMPT":
            source_attempt_id = _token(
                self.source_attempt_id,
                "W2B_V2_SOLID_POINT_INVALID",
                maximum=128,
            )
            if self.source_row_index is not None:
                _fail("W2B_V2_SOLID_POINT_INVALID")
            source_row_index = None
        else:
            if self.source_attempt_id is not None:
                _fail("W2B_V2_SOLID_POINT_INVALID")
            source_attempt_id = None
            source_row_index = _integer(self.source_row_index)
        temperature = _positive(self.temperature_k)
        solid, liquid, phases, composition = _balanced_solid_observation(
            self.solid_fraction,
            self.liquid_fraction,
            self.phase_fractions,
            self.liquid_composition,
        )
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "source_attempt_id", source_attempt_id)
        object.__setattr__(self, "source_row_index", source_row_index)
        object.__setattr__(self, "temperature_k", temperature)
        object.__setattr__(self, "solid_fraction", solid)
        object.__setattr__(self, "liquid_fraction", liquid)
        object.__setattr__(self, "phase_fractions", phases)
        object.__setattr__(self, "liquid_composition", composition)


def _copy_path_point(value: object) -> SolidificationPathPoint:
    if type(value) is not SolidificationPathPoint:
        _fail("W2B_V2_SOLID_POINT_INVALID")
    try:
        return SolidificationPathPoint(
            ordinal=value.ordinal,
            provenance=value.provenance,
            source_attempt_id=value.source_attempt_id,
            source_row_index=value.source_row_index,
            temperature_k=value.temperature_k,
            solid_fraction=_copy_fraction(value.solid_fraction),
            liquid_fraction=_copy_fraction(value.liquid_fraction),
            phase_fractions=tuple(_copy_phase_fraction(item) for item in value.phase_fractions),
            liquid_composition=tuple(
                _copy_composition_entry(item) for item in value.liquid_composition
            ),
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_SOLID_POINT_INVALID") from error


_SEMANTIC_TYPE_SEAL = "_wave2b_v2_semantic_type_sealed"
_SEMANTIC_FLAG_REGISTRY = "_wave2b_v2_fixed_semantic_flags"


class _SealedSemanticMeta(type):
    """Seal fixed public DTO semantics against ordinary class mutation.

    As elsewhere in this module, direct ``type.__setattr__`` is outside the
    ordinary-Python DTO boundary.  Exact reconstruction still verifies the
    source instance slots, so low-level instance-slot mutation fails closed.
    """

    def __getattribute__(cls, name: str) -> object:
        namespace = type.__getattribute__(cls, "__dict__")
        flags = namespace.get(_SEMANTIC_FLAG_REGISTRY, frozenset())
        if name in flags:
            return False
        return super().__getattribute__(name)

    def __setattr__(cls, name: str, value: object) -> None:
        namespace = type.__getattribute__(cls, "__dict__")
        if namespace.get(_SEMANTIC_TYPE_SEAL) is True:
            raise TypeError("Wave 2B V2 semantic DTO type is sealed")
        super().__setattr__(name, value)

    def __delattr__(cls, name: str) -> None:
        namespace = type.__getattribute__(cls, "__dict__")
        if namespace.get(_SEMANTIC_TYPE_SEAL) is True:
            raise TypeError("Wave 2B V2 semantic DTO type is sealed")
        super().__delattr__(name)


def _verify_fixed_false_semantics(
    value: object,
    names: tuple[str, ...],
    reason: str,
) -> None:
    try:
        for name in names:
            observed = object.__getattribute__(value, name)
            if type(observed) is not bool or observed is not False:
                _fail(reason)
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error(reason) from error


@_dataclass(frozen=True, slots=True)
class SolidificationOffPathObservationV2(metaclass=_SealedSemanticMeta):
    """Successful public same-start-temperature row excluded from the path."""

    _wave2b_v2_fixed_semantic_flags: _ClassVar[frozenset[str]] = frozenset(
        {
            "is_solver_attempt",
            "is_failed_attempt",
            "is_merged_attempt",
            "is_monotonic_path_point",
        }
    )

    ordinal: int
    source_row_index: int
    source_outcome: str
    temperature_k: float
    solid_fraction: Binary64FractionV2
    liquid_fraction: Binary64FractionV2
    phase_fractions: tuple[PhaseFractionV2, ...]
    liquid_composition: tuple[CompositionEntryV2, ...]
    disposition: str
    diagnostic_reason: StructuredDiagnosticReasonV2

    is_solver_attempt: bool = _field(init=False, default=False)
    is_failed_attempt: bool = _field(init=False, default=False)
    is_merged_attempt: bool = _field(init=False, default=False)
    is_monotonic_path_point: bool = _field(init=False, default=False)

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError(
            "SolidificationOffPathObservationV2 is sealed and cannot be subclassed"
        )

    def __post_init__(self) -> None:
        _verify_fixed_false_semantics(
            self,
            (
                "is_solver_attempt",
                "is_failed_attempt",
                "is_merged_attempt",
                "is_monotonic_path_point",
            ),
            "W2B_V2_OFF_PATH_OBSERVATION_INVALID",
        )
        ordinal = _integer(self.ordinal)
        source_index = _integer(self.source_row_index)
        if (
            type(self.source_outcome) is not str
            or self.source_outcome != "SUCCESSFUL_PUBLIC_ROW"
        ):
            _fail("W2B_V2_OFF_PATH_OBSERVATION_INVALID")
        temperature = _positive(self.temperature_k)
        solid, liquid, phases, composition = _balanced_solid_observation(
            self.solid_fraction,
            self.liquid_fraction,
            self.phase_fractions,
            self.liquid_composition,
        )
        if (
            type(self.disposition) is not str
            or self.disposition != "EXCLUDED_SAME_START_T_FROM_MONOTONIC_PATH"
        ):
            _fail("W2B_V2_OFF_PATH_OBSERVATION_INVALID")
        reason = _copy_structured_reason(self.diagnostic_reason)
        if reason.code != "SOLID_PUBLIC_SAME_START_T_OFF_PATH":
            _fail("W2B_V2_OFF_PATH_OBSERVATION_INVALID")
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "source_row_index", source_index)
        object.__setattr__(self, "temperature_k", temperature)
        object.__setattr__(self, "solid_fraction", solid)
        object.__setattr__(self, "liquid_fraction", liquid)
        object.__setattr__(self, "phase_fractions", phases)
        object.__setattr__(self, "liquid_composition", composition)
        object.__setattr__(self, "diagnostic_reason", reason)


type.__setattr__(
    SolidificationOffPathObservationV2,
    _SEMANTIC_TYPE_SEAL,
    True,
)


def _copy_off_path_observation(
    value: object,
) -> SolidificationOffPathObservationV2:
    if type(value) is not SolidificationOffPathObservationV2:
        _fail("W2B_V2_OFF_PATH_OBSERVATION_INVALID")
    _verify_fixed_false_semantics(
        value,
        (
            "is_solver_attempt",
            "is_failed_attempt",
            "is_merged_attempt",
            "is_monotonic_path_point",
        ),
        "W2B_V2_OFF_PATH_OBSERVATION_INVALID",
    )
    try:
        return SolidificationOffPathObservationV2(
            ordinal=value.ordinal,
            source_row_index=value.source_row_index,
            source_outcome=value.source_outcome,
            temperature_k=value.temperature_k,
            solid_fraction=_copy_fraction(value.solid_fraction),
            liquid_fraction=_copy_fraction(value.liquid_fraction),
            phase_fractions=tuple(
                _copy_phase_fraction(item) for item in value.phase_fractions
            ),
            liquid_composition=tuple(
                _copy_composition_entry(item) for item in value.liquid_composition
            ),
            disposition=value.disposition,
            diagnostic_reason=_copy_structured_reason(value.diagnostic_reason),
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error(
            "W2B_V2_OFF_PATH_OBSERVATION_INVALID"
        ) from error


@_dataclass(frozen=True, slots=True)
class SolidificationServiceClosure(metaclass=_SealedSemanticMeta):
    """Non-physical convenience closure kept outside attempt/path chronology."""

    _wave2b_v2_fixed_semantic_flags: _ClassVar[frozenset[str]] = frozenset(
        {"is_physical_attempt"}
    )

    closure_source: str
    temperature_k: float
    solid_fraction: Binary64FractionV2
    liquid_fraction: Binary64FractionV2
    phase_fractions: tuple[PhaseFractionV2, ...]
    liquid_composition: tuple[CompositionEntryV2, ...]
    reason_code: str

    is_physical_attempt: bool = _field(init=False, default=False)

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError(
            "SolidificationServiceClosure is sealed and cannot be subclassed"
        )

    def __post_init__(self) -> None:
        _verify_fixed_false_semantics(
            self,
            ("is_physical_attempt",),
            "W2B_V2_SERVICE_CLOSURE_INVALID",
        )
        if type(self.closure_source) is not str or self.closure_source not in (
            "EQUILIBRIUM_SERVICE_CLOSURE",
            "SCHEIL_SERVICE_CLOSURE",
        ):
            _fail("W2B_V2_SERVICE_CLOSURE_INVALID")
        if (
            type(self.reason_code) is not str
            or self.reason_code != "SERVICE_CLOSURE_ONLY_NOT_PHYSICAL_ATTEMPT"
        ):
            _fail("W2B_V2_SERVICE_CLOSURE_INVALID")
        temperature = _positive(self.temperature_k)
        solid, liquid, phases, composition = _balanced_solid_observation(
            self.solid_fraction,
            self.liquid_fraction,
            self.phase_fractions,
            self.liquid_composition,
        )
        object.__setattr__(self, "temperature_k", temperature)
        object.__setattr__(self, "solid_fraction", solid)
        object.__setattr__(self, "liquid_fraction", liquid)
        object.__setattr__(self, "phase_fractions", phases)
        object.__setattr__(self, "liquid_composition", composition)


type.__setattr__(SolidificationServiceClosure, _SEMANTIC_TYPE_SEAL, True)


def _copy_service_closure(value: object) -> SolidificationServiceClosure:
    if type(value) is not SolidificationServiceClosure:
        _fail("W2B_V2_SERVICE_CLOSURE_INVALID")
    _verify_fixed_false_semantics(
        value,
        ("is_physical_attempt",),
        "W2B_V2_SERVICE_CLOSURE_INVALID",
    )
    try:
        return SolidificationServiceClosure(
            closure_source=value.closure_source,
            temperature_k=value.temperature_k,
            solid_fraction=_copy_fraction(value.solid_fraction),
            liquid_fraction=_copy_fraction(value.liquid_fraction),
            phase_fractions=tuple(_copy_phase_fraction(item) for item in value.phase_fractions),
            liquid_composition=tuple(
                _copy_composition_entry(item) for item in value.liquid_composition
            ),
            reason_code=value.reason_code,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_SERVICE_CLOSURE_INVALID") from error


@_dataclass(frozen=True, slots=True)
class SolidificationServiceClosureEvidenceV2(metaclass=_SealedSemanticMeta):
    """Exact incomplete public closure evidence, never a physical path row.

    Reported phase fractions are retained verbatim through their raw binary64
    fields.  No residual phase, normalization, or mass allocation is created.
    A stale reported liquid composition is admissible evidence even at zero
    reported liquid fraction.
    """

    _wave2b_v2_fixed_semantic_flags: _ClassVar[frozenset[str]] = frozenset(
        {"is_physical_attempt"}
    )

    closure_source: str
    source_row_index: int
    temperature_k: float
    reported_solid_fraction: Binary64FractionV2
    reported_liquid_fraction: Binary64FractionV2
    reported_phase_fractions: tuple[PhaseFractionV2, ...]
    reported_liquid_composition: tuple[CompositionEntryV2, ...]
    accounting_complete: bool
    accounting_status: str
    diagnostic_reason: StructuredDiagnosticReasonV2
    recomputed_raw_phase_sum: Binary64FractionV2 = _field(init=False)

    is_physical_attempt: bool = _field(init=False, default=False)

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError(
            "SolidificationServiceClosureEvidenceV2 is sealed and cannot be subclassed"
        )

    def __post_init__(self) -> None:
        _verify_fixed_false_semantics(
            self,
            ("is_physical_attempt",),
            "W2B_V2_CLOSURE_EVIDENCE_INVALID",
        )
        if type(self.closure_source) is not str or self.closure_source not in (
            "EQUILIBRIUM_SERVICE_CLOSURE",
            "SCHEIL_SERVICE_CLOSURE",
        ):
            _fail("W2B_V2_CLOSURE_EVIDENCE_INVALID")
        source_index = _integer(self.source_row_index)
        temperature = _positive(self.temperature_k)
        solid = _copy_fraction(self.reported_solid_fraction)
        liquid = _copy_fraction(self.reported_liquid_fraction)
        if not _within_ulps(
            _math.fsum((solid.canonical_value, liquid.canonical_value)),
            1.0,
            _BALANCE_ULPS,
        ):
            _fail("W2B_V2_SOLID_BALANCE_INVALID")
        phases = _phase_fractions(self.reported_phase_fractions, allow_empty=True)
        canonical_phase_sum = _math.fsum(
            item.fraction.canonical_value for item in phases
        )
        if (
            canonical_phase_sum > solid.canonical_value
            or _within_ulps(
                canonical_phase_sum,
                solid.canonical_value,
                max(_BALANCE_ULPS, len(phases)),
            )
        ):
            _fail("W2B_V2_CLOSURE_EVIDENCE_INVALID")
        raw_phase_sum = Binary64FractionV2.observe(
            _math.fsum(item.fraction.raw_value for item in phases)
        )
        composition = _composition(
            self.reported_liquid_composition,
            expected_components=None,
            allow_empty=True,
        )
        if type(self.accounting_complete) is not bool or self.accounting_complete:
            _fail("W2B_V2_CLOSURE_EVIDENCE_INVALID")
        if (
            type(self.accounting_status) is not str
            or self.accounting_status != "INCOMPLETE_REPORTED_PHASE_ACCOUNTING"
        ):
            _fail("W2B_V2_CLOSURE_EVIDENCE_INVALID")
        reason = _copy_structured_reason(self.diagnostic_reason)
        if reason.code != "SOLID_SERVICE_CLOSURE_ACCOUNTING_INCOMPLETE":
            _fail("W2B_V2_CLOSURE_EVIDENCE_INVALID")
        object.__setattr__(self, "source_row_index", source_index)
        object.__setattr__(self, "temperature_k", temperature)
        object.__setattr__(self, "reported_solid_fraction", solid)
        object.__setattr__(self, "reported_liquid_fraction", liquid)
        object.__setattr__(self, "reported_phase_fractions", phases)
        object.__setattr__(self, "reported_liquid_composition", composition)
        object.__setattr__(self, "diagnostic_reason", reason)
        object.__setattr__(self, "recomputed_raw_phase_sum", raw_phase_sum)


type.__setattr__(
    SolidificationServiceClosureEvidenceV2,
    _SEMANTIC_TYPE_SEAL,
    True,
)


def _copy_service_closure_evidence(
    value: object,
) -> SolidificationServiceClosureEvidenceV2:
    if type(value) is not SolidificationServiceClosureEvidenceV2:
        _fail("W2B_V2_CLOSURE_EVIDENCE_INVALID")
    _verify_fixed_false_semantics(
        value,
        ("is_physical_attempt",),
        "W2B_V2_CLOSURE_EVIDENCE_INVALID",
    )
    try:
        rebuilt = SolidificationServiceClosureEvidenceV2(
            closure_source=value.closure_source,
            source_row_index=value.source_row_index,
            temperature_k=value.temperature_k,
            reported_solid_fraction=_copy_fraction(
                value.reported_solid_fraction
            ),
            reported_liquid_fraction=_copy_fraction(
                value.reported_liquid_fraction
            ),
            reported_phase_fractions=tuple(
                _copy_phase_fraction(item)
                for item in value.reported_phase_fractions
            ),
            reported_liquid_composition=tuple(
                _copy_composition_entry(item)
                for item in value.reported_liquid_composition
            ),
            accounting_complete=value.accounting_complete,
            accounting_status=value.accounting_status,
            diagnostic_reason=_copy_structured_reason(value.diagnostic_reason),
        )
        if rebuilt.recomputed_raw_phase_sum != _copy_fraction(
            value.recomputed_raw_phase_sum
        ):
            _fail("W2B_V2_CLOSURE_EVIDENCE_INVALID")
        return rebuilt
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_CLOSURE_EVIDENCE_INVALID") from error


@_dataclass(frozen=True, slots=True)
class SolidificationDiagnosticsV2:
    """Versioned attempt observability and bounded-work evidence."""

    instrumentation_id: str
    instrumentation_version: str
    instrumentation_level: str
    backend_name: str
    backend_version: str
    completeness: str
    full_attempt_ledger: bool
    failed_attempts_retained: bool
    merged_attempts_retained: bool
    abandoned_attempts_retained: bool
    adaptive_backtracks_retained: bool
    binary_search_attempts_retained: bool
    service_closure_separated: bool
    public_off_path_observations_retained: bool
    incomplete_closure_evidence_retained: bool
    unresolved_branch_count: int
    attempt_budget: int
    attempts_consumed: int
    budget_exhausted: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "instrumentation_id", _token(self.instrumentation_id, "W2B_V2_DIAGNOSTICS_INVALID"))
        object.__setattr__(self, "instrumentation_version", _token(self.instrumentation_version, "W2B_V2_DIAGNOSTICS_INVALID"))
        if type(self.instrumentation_level) is not str or self.instrumentation_level not in (
            "FULL_INTERNAL_ATTEMPT_LEDGER",
            "PARTIAL_BACKEND_OBSERVABILITY",
        ):
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        object.__setattr__(self, "backend_name", _token(self.backend_name, "W2B_V2_DIAGNOSTICS_INVALID"))
        object.__setattr__(self, "backend_version", _token(self.backend_version, "W2B_V2_DIAGNOSTICS_INVALID"))
        if type(self.completeness) is not str or self.completeness not in ("COMPLETE", "PARTIAL"):
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        if self.completeness == "COMPLETE":
            _fail("W2B_V2_COMPLETE_CAPABILITY_UNAVAILABLE")
        flags = tuple(
            _boolean(value)
            for value in (
                self.full_attempt_ledger,
                self.failed_attempts_retained,
                self.merged_attempts_retained,
                self.abandoned_attempts_retained,
                self.adaptive_backtracks_retained,
                self.binary_search_attempts_retained,
                self.service_closure_separated,
                self.public_off_path_observations_retained,
                self.incomplete_closure_evidence_retained,
            )
        )
        unresolved = _integer(self.unresolved_branch_count)
        budget = _integer(
            self.attempt_budget,
            maximum=_MAX_SOLID_ATTEMPTS,
        )
        consumed = _integer(self.attempts_consumed, maximum=budget)
        exhausted = _boolean(self.budget_exhausted)
        if exhausted and (budget == 0 or consumed != budget):
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        object.__setattr__(self, "unresolved_branch_count", unresolved)
        object.__setattr__(self, "attempt_budget", budget)
        object.__setattr__(self, "attempts_consumed", consumed)


def _copy_solid_diagnostics(value: object) -> SolidificationDiagnosticsV2:
    if type(value) is not SolidificationDiagnosticsV2:
        _fail("W2B_V2_DIAGNOSTICS_INVALID")
    try:
        return SolidificationDiagnosticsV2(
            instrumentation_id=value.instrumentation_id,
            instrumentation_version=value.instrumentation_version,
            instrumentation_level=value.instrumentation_level,
            backend_name=value.backend_name,
            backend_version=value.backend_version,
            completeness=value.completeness,
            full_attempt_ledger=value.full_attempt_ledger,
            failed_attempts_retained=value.failed_attempts_retained,
            merged_attempts_retained=value.merged_attempts_retained,
            abandoned_attempts_retained=value.abandoned_attempts_retained,
            adaptive_backtracks_retained=value.adaptive_backtracks_retained,
            binary_search_attempts_retained=value.binary_search_attempts_retained,
            service_closure_separated=value.service_closure_separated,
            public_off_path_observations_retained=(
                value.public_off_path_observations_retained
            ),
            incomplete_closure_evidence_retained=(
                value.incomplete_closure_evidence_retained
            ),
            unresolved_branch_count=value.unresolved_branch_count,
            attempt_budget=value.attempt_budget,
            attempts_consumed=value.attempts_consumed,
            budget_exhausted=value.budget_exhausted,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_DIAGNOSTICS_INVALID") from error


def _components(value: object) -> tuple[str, ...]:
    names = _names(value, allow_empty=False)
    if "VA" not in names or len(names) < 3:
        _fail("W2B_V2_COMPOSITION_INVALID")
    return tuple(item for item in names if item != "VA") + ("VA",)


def _same_point_observation(
    attempt: SolidificationAttemptRecord,
    point: SolidificationPathPoint,
) -> bool:
    return (
        attempt.temperature_k == point.temperature_k
        and attempt.observed_solid_fraction == point.solid_fraction
        and attempt.observed_liquid_fraction == point.liquid_fraction
        and attempt.observed_phase_fractions == point.phase_fractions
        and attempt.observed_liquid_composition == point.liquid_composition
    )


def _preflight_solid_ledger(value: object) -> None:
    """Bound aggregate solidification reconstruction work before any copier."""

    try:
        if type(value.database) is not DatabaseIdentityV2:
            _fail("W2B_V2_DATABASE_INVALID")
        if type(value.execution_binding) is not ExecutionBindingV2:
            _fail("W2B_V2_EXECUTION_BINDING_INVALID")
        if type(value.phase_domain) is not PhaseDomainV2:
            _fail("W2B_V2_PHASE_DOMAIN_INVALID")
        if type(value.diagnostics) is not SolidificationDiagnosticsV2:
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        attempts = _preflight_optional_record_tuple(
            value.attempts,
            SolidificationAttemptRecord,
            _MAX_SOLID_ATTEMPTS,
            "W2B_V2_SOLID_LEDGER_INVALID",
        )
        if (
            type(value.diagnostics.attempt_budget) is not int
            or not (0 <= value.diagnostics.attempt_budget <= _MAX_SOLID_ATTEMPTS)
            or type(value.diagnostics.attempts_consumed) is not int
            or value.diagnostics.attempts_consumed != len(attempts)
            or value.diagnostics.attempts_consumed > value.diagnostics.attempt_budget
            or type(value.diagnostics.budget_exhausted) is not bool
        ):
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        points = _preflight_record_tuple(
            value.path_points,
            SolidificationPathPoint,
            _MAX_SOLID_PATH_POINTS,
            "W2B_V2_SOLID_LEDGER_INVALID",
        )
        off_path = _preflight_optional_record_tuple(
            value.off_path_observations,
            SolidificationOffPathObservationV2,
            _MAX_SOLID_OFF_PATH_OBSERVATIONS,
            "W2B_V2_SOLID_LEDGER_INVALID",
        )
        if value.service_closure is not None and type(value.service_closure) is not SolidificationServiceClosure:
            _fail("W2B_V2_SERVICE_CLOSURE_INVALID")
        if (
            value.service_closure_evidence is not None
            and type(value.service_closure_evidence)
            is not SolidificationServiceClosureEvidenceV2
        ):
            _fail("W2B_V2_CLOSURE_EVIDENCE_INVALID")
        total = len(attempts) + len(points) + len(off_path)
        for nested in (
            value.components,
            value.bulk_composition,
            value.phase_domain.candidate_phases,
            value.phase_domain.requested_phases,
            value.phase_domain.excluded_phases,
            value.phase_domain.effective_phases,
        ):
            total += _preflight_nested_tuple(nested, "W2B_V2_SOLID_LEDGER_INVALID")
        for attempt in attempts:
            for nested in (
                attempt.conditions,
                attempt.observed_phase_fractions,
                attempt.observed_liquid_composition,
            ):
                total += _preflight_nested_tuple(nested, "W2B_V2_SOLID_LEDGER_INVALID")
            if total > _MAX_AGGREGATE_NESTED_ITEMS:
                _fail("W2B_V2_WORK_BUDGET_EXCEEDED")
        for point in points:
            for nested in (point.phase_fractions, point.liquid_composition):
                total += _preflight_nested_tuple(nested, "W2B_V2_SOLID_LEDGER_INVALID")
            if total > _MAX_AGGREGATE_NESTED_ITEMS:
                _fail("W2B_V2_WORK_BUDGET_EXCEEDED")
        for observation in off_path:
            for nested in (
                observation.phase_fractions,
                observation.liquid_composition,
            ):
                total += _preflight_nested_tuple(
                    nested,
                    "W2B_V2_SOLID_LEDGER_INVALID",
                )
            if total > _MAX_AGGREGATE_NESTED_ITEMS:
                _fail("W2B_V2_WORK_BUDGET_EXCEEDED")
        if value.service_closure is not None:
            for nested in (
                value.service_closure.phase_fractions,
                value.service_closure.liquid_composition,
            ):
                total += _preflight_nested_tuple(nested, "W2B_V2_SOLID_LEDGER_INVALID")
            if total > _MAX_AGGREGATE_NESTED_ITEMS:
                _fail("W2B_V2_WORK_BUDGET_EXCEEDED")
        if value.service_closure_evidence is not None:
            for nested in (
                value.service_closure_evidence.reported_phase_fractions,
                value.service_closure_evidence.reported_liquid_composition,
            ):
                total += _preflight_nested_tuple(
                    nested,
                    "W2B_V2_SOLID_LEDGER_INVALID",
                )
            if total > _MAX_AGGREGATE_NESTED_ITEMS:
                _fail("W2B_V2_WORK_BUDGET_EXCEEDED")
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_SOLID_LEDGER_INVALID") from error


@_dataclass(frozen=True, slots=True)
class RawSolidificationLedgerV2:
    """Chronological attempts and a separate accepted monotonic path."""

    database: DatabaseIdentityV2
    execution_binding: ExecutionBindingV2
    phase_domain: PhaseDomainV2
    feature: str
    method: str
    components: tuple[str, ...]
    bulk_composition: tuple[CompositionEntryV2, ...]
    liquid_phase: str
    pressure_pa: float
    start_temperature_k: float
    minimum_temperature_k: float
    stop_liquid_fraction: Binary64FractionV2 | None
    attempts: tuple[SolidificationAttemptRecord, ...]
    path_points: tuple[SolidificationPathPoint, ...]
    off_path_observations: tuple[SolidificationOffPathObservationV2, ...]
    service_closure: SolidificationServiceClosure | None
    service_closure_evidence: SolidificationServiceClosureEvidenceV2 | None
    diagnostics: SolidificationDiagnosticsV2
    terminal_reason: str

    def __post_init__(self) -> None:
        _preflight_solid_ledger(self)
        database = _copy_database(self.database)
        binding = _copy_binding(self.execution_binding)
        domain = _copy_domain(self.phase_domain, database)
        if type(self.feature) is not str or self.feature not in _SOLIDIFICATION_METHODS:
            _fail("W2B_V2_SOLID_LEDGER_INVALID")
        if type(self.method) is not str or self.method != _SOLIDIFICATION_METHODS[self.feature]:
            _fail("W2B_V2_SOLID_LEDGER_INVALID")
        components = _components(self.components)
        pure_components = tuple(item for item in components if item != "VA")
        bulk = _composition(
            self.bulk_composition,
            expected_components=pure_components,
            allow_empty=False,
        )
        liquid_phase = _name(self.liquid_phase)
        if liquid_phase not in domain.effective_phases:
            _fail("W2B_V2_PHASE_DOMAIN_INVALID")
        pressure = _positive(self.pressure_pa)
        if pressure != SOLIDIFICATION_PRESSURE_PA:
            _fail("W2B_V2_SOLID_LEDGER_INVALID")
        start_temperature = _positive(self.start_temperature_k)
        minimum_temperature = _positive(self.minimum_temperature_k)
        if minimum_temperature >= start_temperature:
            _fail("W2B_V2_SOLID_LEDGER_INVALID")
        if self.feature == "equilibrium_solidification":
            if self.stop_liquid_fraction is not None:
                _fail("W2B_V2_SOLID_LEDGER_INVALID")
            stop_liquid = None
        else:
            stop_liquid = _copy_fraction(self.stop_liquid_fraction)
            if not (0.0 < stop_liquid.canonical_value < 1.0):
                _fail("W2B_V2_SOLID_LEDGER_INVALID")

        attempts = _ordered_exact(
            self.attempts,
            SolidificationAttemptRecord,
            _copy_solid_attempt,
            allow_empty=True,
            reason="W2B_V2_SOLID_LEDGER_INVALID",
        )
        points = _ordered_exact(
            self.path_points,
            SolidificationPathPoint,
            _copy_path_point,
            allow_empty=False,
            reason="W2B_V2_SOLID_LEDGER_INVALID",
        )
        off_path = _ordered_exact(
            self.off_path_observations,
            SolidificationOffPathObservationV2,
            _copy_off_path_observation,
            allow_empty=True,
            reason="W2B_V2_SOLID_LEDGER_INVALID",
        )
        if self.service_closure is None:
            service_closure = None
        else:
            service_closure = _copy_service_closure(self.service_closure)
        if self.service_closure_evidence is None:
            closure_evidence = None
        else:
            closure_evidence = _copy_service_closure_evidence(
                self.service_closure_evidence
            )
        diagnostics = _copy_solid_diagnostics(self.diagnostics)
        if diagnostics.attempts_consumed != len(attempts):
            _fail("W2B_V2_DIAGNOSTICS_INVALID")
        if type(self.terminal_reason) is not str or self.terminal_reason not in _SOLID_TERMINALS:
            _fail("W2B_V2_SOLID_TERMINAL_INVALID")
        if self.terminal_reason in (
            "EQUILIBRIUM_NO_LIQUID_REACHED",
            "SCHEIL_LIQUID_THRESHOLD_REACHED",
        ):
            _fail("W2B_V2_COMPLETE_CAPABILITY_UNAVAILABLE")

        attempt_by_id = {attempt.attempt_id: attempt for attempt in attempts}
        if len(attempt_by_id) != len(attempts):
            _fail("W2B_V2_SOLID_ATTEMPT_INVALID")
        for attempt in attempts:
            if not (minimum_temperature <= attempt.temperature_k <= start_temperature):
                _fail("W2B_V2_SOLID_ATTEMPT_INVALID")
            if attempt.observed_liquid_composition and tuple(
                item.component for item in attempt.observed_liquid_composition
            ) != pure_components:
                _fail("W2B_V2_COMPOSITION_INVALID")
            if not _phases_within_domain(
                tuple(item.phase_instance for item in attempt.observed_phase_fractions),
                set(domain.effective_phases) - {liquid_phase},
            ):
                _fail("W2B_V2_PHASE_DOMAIN_INVALID")

        previous: SolidificationPathPoint | None = None
        backend_point_ids: set[str] = set()
        public_path_source_indices: set[int] = set()
        for point in points:
            if not (minimum_temperature <= point.temperature_k <= start_temperature):
                _fail("W2B_V2_SOLID_PATH_ORDER_INVALID")
            if point.liquid_composition and tuple(
                item.component for item in point.liquid_composition
            ) != pure_components:
                _fail("W2B_V2_COMPOSITION_INVALID")
            if not _phases_within_domain(
                tuple(item.phase_instance for item in point.phase_fractions),
                set(domain.effective_phases) - {liquid_phase},
            ):
                _fail("W2B_V2_PHASE_DOMAIN_INVALID")
            if previous is not None and (
                point.temperature_k >= previous.temperature_k
                or point.solid_fraction.canonical_value < previous.solid_fraction.canonical_value
                or point.liquid_fraction.canonical_value > previous.liquid_fraction.canonical_value
            ):
                _fail("W2B_V2_SOLID_PATH_ORDER_INVALID")
            if point.provenance == "BACKEND_ACCEPTED_ATTEMPT":
                source = attempt_by_id.get(point.source_attempt_id)
                if source is None or source.outcome != "ACCEPTED":
                    _fail("W2B_V2_SOLID_POINT_INVALID")
                if source.accepted_path_ordinal != point.ordinal:
                    _fail("W2B_V2_SOLID_ATTEMPT_INVALID")
                if (
                    not _same_point_observation(source, point)
                    or point.source_attempt_id in backend_point_ids
                ):
                    _fail("W2B_V2_SOLID_POINT_INVALID")
                backend_point_ids.add(point.source_attempt_id)  # type: ignore[arg-type]
            elif point.provenance == "BACKEND_PUBLIC_PATH_ROW":
                if point.source_row_index in public_path_source_indices:
                    _fail("W2B_V2_SOLID_POINT_INVALID")
                public_path_source_indices.add(point.source_row_index)  # type: ignore[arg-type]
            previous = point
        for attempt in attempts:
            if attempt.outcome in ("ACCEPTED", "MERGED"):
                if attempt.accepted_path_ordinal is None or attempt.accepted_path_ordinal >= len(points):
                    _fail("W2B_V2_SOLID_ATTEMPT_INVALID")
                target = points[attempt.accepted_path_ordinal]
                if attempt.outcome == "ACCEPTED":
                    if target.source_attempt_id != attempt.attempt_id:
                        _fail("W2B_V2_SOLID_POINT_INVALID")
                elif not _same_point_observation(attempt, target):
                    _fail("W2B_V2_SOLID_POINT_INVALID")

        off_path_source_indices: set[int] = set()
        for observation in off_path:
            if (
                observation.temperature_k != start_temperature
                or observation.source_row_index in off_path_source_indices
                or observation.source_row_index in public_path_source_indices
            ):
                _fail("W2B_V2_OFF_PATH_OBSERVATION_INVALID")
            off_path_source_indices.add(observation.source_row_index)
            if observation.liquid_composition and tuple(
                item.component for item in observation.liquid_composition
            ) != pure_components:
                _fail("W2B_V2_COMPOSITION_INVALID")
            if not _phases_within_domain(
                tuple(
                    item.phase_instance for item in observation.phase_fractions
                ),
                set(domain.effective_phases) - {liquid_phase},
            ):
                _fail("W2B_V2_PHASE_DOMAIN_INVALID")

        initial = points[0]
        if (
            initial.temperature_k != start_temperature
            or initial.solid_fraction.canonical_value != 0.0
            or initial.liquid_fraction.canonical_value != 1.0
            or initial.phase_fractions
            or initial.liquid_composition != bulk
        ):
            _fail("W2B_V2_SOLID_PATH_ORDER_INVALID")
        if service_closure is not None:
            expected_source = (
                "EQUILIBRIUM_SERVICE_CLOSURE"
                if self.feature == "equilibrium_solidification"
                else "SCHEIL_SERVICE_CLOSURE"
            )
            if (
                service_closure.closure_source != expected_source
                or not diagnostics.service_closure_separated
                or not (
                    minimum_temperature
                    <= service_closure.temperature_k
                    <= start_temperature
                )
            ):
                _fail("W2B_V2_SERVICE_CLOSURE_INVALID")
            if service_closure.liquid_composition and tuple(
                item.component for item in service_closure.liquid_composition
            ) != pure_components:
                _fail("W2B_V2_COMPOSITION_INVALID")
            if not _phases_within_domain(
                tuple(item.phase_instance for item in service_closure.phase_fractions),
                set(domain.effective_phases) - {liquid_phase},
            ):
                _fail("W2B_V2_PHASE_DOMAIN_INVALID")
        if closure_evidence is not None:
            expected_source = (
                "EQUILIBRIUM_SERVICE_CLOSURE"
                if self.feature == "equilibrium_solidification"
                else "SCHEIL_SERVICE_CLOSURE"
            )
            if (
                service_closure is not None
                or closure_evidence.closure_source != expected_source
                or not diagnostics.service_closure_separated
                or not (
                    minimum_temperature
                    <= closure_evidence.temperature_k
                    <= start_temperature
                )
                or closure_evidence.source_row_index
                in public_path_source_indices | off_path_source_indices
            ):
                _fail("W2B_V2_CLOSURE_EVIDENCE_INVALID")
            if closure_evidence.reported_liquid_composition and tuple(
                item.component
                for item in closure_evidence.reported_liquid_composition
            ) != pure_components:
                _fail("W2B_V2_COMPOSITION_INVALID")
            if not _phases_within_domain(
                tuple(
                    item.phase_instance
                    for item in closure_evidence.reported_phase_fractions
                ),
                set(domain.effective_phases) - {liquid_phase},
            ):
                _fail("W2B_V2_PHASE_DOMAIN_INVALID")
        if (
            diagnostics.public_off_path_observations_retained is not bool(off_path)
            or diagnostics.incomplete_closure_evidence_retained
            is not (closure_evidence is not None)
        ):
            _fail("W2B_V2_DIAGNOSTICS_INVALID")

        phase_groups = (
            tuple(
                tuple(item.phase_instance for item in attempt.observed_phase_fractions)
                for attempt in attempts
            )
            + tuple(
                tuple(item.phase_instance for item in point.phase_fractions)
                for point in points
            )
            + tuple(
                tuple(item.phase_instance for item in observation.phase_fractions)
                for observation in off_path
            )
        )
        if service_closure is not None:
            phase_groups += (
                tuple(item.phase_instance for item in service_closure.phase_fractions),
            )
        if closure_evidence is not None:
            phase_groups += (
                tuple(
                    item.phase_instance
                    for item in closure_evidence.reported_phase_fractions
                ),
            )
        _validate_mapping_multiplicity_groups(phase_groups)

        if diagnostics.budget_exhausted:
            if self.terminal_reason != "BUDGET_EXHAUSTED":
                _fail("W2B_V2_BUDGET_EXHAUSTED")
        elif diagnostics.unresolved_branch_count > 0:
            if self.terminal_reason != "PARTIAL_UNRESOLVED_BRANCHES":
                _fail("W2B_V2_UNRESOLVED_BRANCHES")
        elif self.terminal_reason == "TERMINAL_STATE_OBSERVED_DIAGNOSTICS_PARTIAL":
            if len(points) < 2:
                _fail("W2B_V2_SOLID_TERMINAL_INVALID")
            final = points[-1]
            if self.feature == "equilibrium_solidification":
                if final.liquid_fraction.canonical_value != 0.0:
                    _fail("W2B_V2_SOLID_TERMINAL_INVALID")
            elif final.liquid_fraction.canonical_value > stop_liquid.canonical_value:  # type: ignore[union-attr]
                _fail("W2B_V2_SOLID_TERMINAL_INVALID")
        if self.terminal_reason in ("PARTIAL_UNRESOLVED_BRANCHES", "BUDGET_EXHAUSTED"):
            if diagnostics.completeness != "PARTIAL":
                _fail("W2B_V2_SOLID_TERMINAL_INVALID")
        if (
            self.terminal_reason == "PARTIAL_UNRESOLVED_BRANCHES"
            and diagnostics.unresolved_branch_count == 0
        ):
            _fail("W2B_V2_SOLID_TERMINAL_INVALID")
        if self.terminal_reason == "BUDGET_EXHAUSTED" and not diagnostics.budget_exhausted:
            _fail("W2B_V2_SOLID_TERMINAL_INVALID")
        if self.terminal_reason == "NO_PROGRESS" and len(points) != 1:
            _fail("W2B_V2_SOLID_TERMINAL_INVALID")

        object.__setattr__(self, "database", database)
        object.__setattr__(self, "execution_binding", binding)
        object.__setattr__(self, "phase_domain", domain)
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "bulk_composition", bulk)
        object.__setattr__(self, "liquid_phase", liquid_phase)
        object.__setattr__(self, "pressure_pa", pressure)
        object.__setattr__(self, "start_temperature_k", start_temperature)
        object.__setattr__(self, "minimum_temperature_k", minimum_temperature)
        object.__setattr__(self, "stop_liquid_fraction", stop_liquid)
        object.__setattr__(self, "attempts", attempts)
        object.__setattr__(self, "path_points", points)
        object.__setattr__(self, "off_path_observations", off_path)
        object.__setattr__(self, "service_closure", service_closure)
        object.__setattr__(self, "service_closure_evidence", closure_evidence)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def is_diagnostics_complete(self) -> bool:
        return False


def _copy_solid_ledger(value: object) -> RawSolidificationLedgerV2:
    if type(value) is not RawSolidificationLedgerV2:
        _fail("W2B_V2_SOLID_LEDGER_INVALID")
    _preflight_solid_ledger(value)
    try:
        return RawSolidificationLedgerV2(
            database=_copy_database(value.database),
            execution_binding=_copy_binding(value.execution_binding),
            phase_domain=PhaseDomainV2(
                candidate_phases=value.phase_domain.candidate_phases,
                requested_phases=value.phase_domain.requested_phases,
                excluded_phases=value.phase_domain.excluded_phases,
                effective_phases=value.phase_domain.effective_phases,
            ),
            feature=value.feature,
            method=value.method,
            components=value.components,
            bulk_composition=tuple(
                _copy_composition_entry(item) for item in value.bulk_composition
            ),
            liquid_phase=value.liquid_phase,
            pressure_pa=value.pressure_pa,
            start_temperature_k=value.start_temperature_k,
            minimum_temperature_k=value.minimum_temperature_k,
            stop_liquid_fraction=(
                None
                if value.stop_liquid_fraction is None
                else _copy_fraction(value.stop_liquid_fraction)
            ),
            attempts=tuple(_copy_solid_attempt(item) for item in value.attempts),
            path_points=tuple(_copy_path_point(item) for item in value.path_points),
            off_path_observations=tuple(
                _copy_off_path_observation(item)
                for item in value.off_path_observations
            ),
            service_closure=(
                None
                if value.service_closure is None
                else _copy_service_closure(value.service_closure)
            ),
            service_closure_evidence=(
                None
                if value.service_closure_evidence is None
                else _copy_service_closure_evidence(
                    value.service_closure_evidence
                )
            ),
            diagnostics=_copy_solid_diagnostics(value.diagnostics),
            terminal_reason=value.terminal_reason,
        )
    except PathContractV2Error:
        raise
    except Exception as error:
        raise PathContractV2Error("W2B_V2_SOLID_LEDGER_INVALID") from error


@_dataclass(frozen=True, slots=True)
class SolidificationResultV2(metaclass=_SealedResultMeta):
    """Public fail-closed path result; it conveys no acceptance claim."""

    ledger: RawSolidificationLedgerV2

    acceptance_claim: _ClassVar[bool] = False
    counts_toward_feature_coverage: _ClassVar[bool] = False
    production_use: _ClassVar[str] = "DENIED"
    release_authorized: _ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: object) -> None:
        raise TypeError("SolidificationResultV2 is sealed and cannot be subclassed")

    def __getattribute__(self, name: str) -> object:
        if name in _RESULT_DENIAL_FLAGS:
            return _RESULT_DENIAL_VALUES[name]
        return object.__getattribute__(self, name)

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "ledger", _copy_solid_ledger(self.ledger))
        except PathContractV2Error:
            raise
        except Exception as error:
            raise PathContractV2Error("W2B_V2_RESULT_INVALID") from error

    @property
    def terminal_reason(self) -> str:
        return self.ledger.terminal_reason

    @property
    def failed_attempts(self) -> tuple[SolidificationAttemptRecord, ...]:
        return tuple(item for item in self.ledger.attempts if item.outcome == "FAILED")


type.__setattr__(SolidificationResultV2, _RESULT_TYPE_SEAL, True)


__all__ = (
    "CONTRACT_SCHEMA",
    "CONTRACT_VERSION",
    "SUPPORTED_DATABASE_FAMILIES",
    "SUPPORTED_PATH_FEATURES",
    "SUPPORTED_FE_PROFILE_IDS",
    "FE_POLICY_UNDECIDED",
    "POLICY_NOT_APPLICABLE",
    "SOLIDIFICATION_PRESSURE_PA",
    "MAX_ENDPOINT_CORRECTION_ULPS",
    "PRODUCTION_USE",
    "ACCEPTANCE_CLAIM",
    "COUNTS_TOWARD_FEATURE_COVERAGE",
    "RELEASE_AUTHORIZED",
    "COMPLETE_ISSUANCE_AVAILABLE",
    "COMPLETE_ISSUANCE_BOUNDARY",
    "STRUCTURED_DIAGNOSTIC_REASONS",
    "WAVE2B_PATH_V2_REASON_CODES",
    "PathContractV2Error",
    "StructuredDiagnosticReasonV2",
    "DatabaseIdentityV2",
    "ExecutionBindingV2",
    "PhaseDomainV2",
    "PhaseInstanceV2",
    "Binary64FractionV2",
    "CompositionEntryV2",
    "MappingAttemptRecord",
    "MappingPostrunEvidenceRecordV2",
    "TopologyNode",
    "TopologySegment",
    "TopologyRegion",
    "MappingDiagnosticsV2",
    "RawMappingLedgerV2",
    "MappingResultV2",
    "PhaseFractionV2",
    "SolidificationAttemptRecord",
    "SolidificationPathPoint",
    "SolidificationOffPathObservationV2",
    "SolidificationServiceClosure",
    "SolidificationServiceClosureEvidenceV2",
    "SolidificationDiagnosticsV2",
    "RawSolidificationLedgerV2",
    "SolidificationResultV2",
)
