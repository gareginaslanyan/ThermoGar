"""Import-safe Wave 2B contracts for mapping and solidification paths.

This module is an adapter boundary, not a solver and not a release gate.  A
real integration must inject a mapping or solidification backend.  Mapping
backends must return their strategy topology and internal-node ledger; a
rectangular point grid is not promoted to a binary, isopleth, or ternary map.
Solidification backends must return the attempted trajectory, including failed
attempts.  No object in this module claims feature coverage, NE-03 acceptance,
or production readiness.

The Fe identity deliberately records that both the baseline decision and any
C15-exclusion policy are still undecided.  A profile is identified for an
evaluation run, but this layer cannot designate it as the product baseline.
Until the user makes that decision, every Fe request must bind C15_LAVES in
its candidate, requested, and effective phase sets and cannot exclude it.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
import math as _math
from types import MappingProxyType as _MappingProxyType
from typing import Protocol as _Protocol, TypeAlias as _TypeAlias


SUPPORTED_PATH_FEATURES = (
    "binary_phase_diagram",
    "multicomponent_isopleth",
    "ternary_phase_diagram",
    "equilibrium_solidification",
    "scheil_solidification",
)
SUPPORTED_DATABASE_FAMILIES = ("al", "fe", "ni")
SUPPORTED_FE_PROFILE_IDS = ("thermogar_patch", "upstream_original")
# The installed solidification backend fixes pressure internally.  Mapping
# strategies accept any explicit finite positive pressure through their request.
SOLIDIFICATION_PRESSURE_PA = 101325.0

FE_POLICY_UNDECIDED = "UNDECIDED_USER_DECISION_REQUIRED"
POLICY_NOT_APPLICABLE = "NOT_APPLICABLE"
PROFILE_ROLES = ("DIAGNOSTIC_CONTROL", "EVALUATION_PROFILE")
_FE_PROFILE_ROLES = _MappingProxyType({
    "thermogar_patch": "EVALUATION_PROFILE",
    "upstream_original": "DIAGNOSTIC_CONTROL",
})

_MAPPING_STRATEGIES = _MappingProxyType({
    "binary_phase_diagram": "BINARY_MAPPING",
    "multicomponent_isopleth": "ISOPLETH_MAPPING",
    "ternary_phase_diagram": "TERNARY_MAPPING",
})
_SOLIDIFICATION_METHODS = _MappingProxyType({
    "equilibrium_solidification": "EQUILIBRIUM",
    "scheil_solidification": "SCHEIL_GULLIVER",
})

_REASON_DESCRIPTIONS = (
    ("W2B_DB_IDENTITY_INVALID", "database identity object is invalid"),
    ("W2B_DB_FAMILY_INVALID", "database family is not ni, al, or fe"),
    ("W2B_DB_ID_INVALID", "database identifier is invalid"),
    ("W2B_DB_SHA256_INVALID", "database SHA-256 is not lowercase hexadecimal"),
    ("W2B_DB_PROFILE_INVALID", "database profile identifier is invalid"),
    ("W2B_DB_PROFILE_ROLE_INVALID", "database profile role is invalid"),
    ("W2B_FE_POLICY_STATE_INVALID", "Fe policy must remain explicitly undecided"),
    ("W2B_NON_FE_POLICY_STATE_INVALID", "non-Fe policy fields must be not applicable"),
    ("W2B_NAME_INVALID", "component or phase name is invalid"),
    ("W2B_NAMES_INVALID", "name tuple is invalid or empty"),
    ("W2B_NAME_DUPLICATE", "name tuple contains a duplicate"),
    ("W2B_NUMBER_INVALID", "numeric value has an invalid type"),
    ("W2B_NUMBER_NONFINITE", "numeric value is not finite"),
    ("W2B_RANGE_INVALID", "closed mapping range is invalid"),
    ("W2B_PRESSURE_INVALID", "pressure must be finite and positive"),
    ("W2B_SOLID_PRESSURE_UNSUPPORTED", "solidification pressure is not the backend fixed pressure"),
    ("W2B_TEMPERATURE_INVALID", "temperature must be finite and positive"),
    ("W2B_FRACTION_INVALID", "fraction is outside the closed unit interval"),
    ("W2B_COMPOSITION_INVALID", "composition tuple is invalid"),
    ("W2B_COMPOSITION_SUM_INVALID", "composition does not sum to one"),
    ("W2B_COMPONENT_SET_INVALID", "component set is inconsistent with the request"),
    ("W2B_PHASE_SET_INVALID", "phase set is invalid or inconsistent"),
    ("W2B_PHASE_SELECTION_INVALID", "phase candidate/request/exclusion/effective binding is invalid"),
    ("W2B_FE_C15_DECISION_REQUIRED", "Fe request cannot omit or exclude C15 while policy is undecided"),
    ("W2B_LIQUID_PHASE_REQUIRED", "selected liquid phase is absent"),
    ("W2B_BOOL_INVALID", "boolean option has an invalid type"),
    ("W2B_INTEGER_INVALID", "integer option has an invalid type or range"),
    ("W2B_BINARY_SYSTEM_INVALID", "binary mapping system is invalid"),
    ("W2B_ISOPLETH_SYSTEM_INVALID", "isopleth mapping system is invalid"),
    ("W2B_TERNARY_SYSTEM_INVALID", "ternary mapping system is invalid"),
    ("W2B_TERNARY_STEP_INVALID", "ternary starting-point step is invalid"),
    ("W2B_REQUEST_INVALID", "path request object is invalid"),
    ("W2B_NODE_ORDINAL_INVALID", "ledger ordinal is invalid"),
    ("W2B_NODE_ID_INVALID", "mapping node identifier is invalid"),
    ("W2B_NODE_KIND_INVALID", "mapping node kind is invalid"),
    ("W2B_NODE_OUTCOME_INVALID", "mapping node outcome is invalid"),
    ("W2B_NODE_COORDINATES_INVALID", "mapping node coordinates are invalid"),
    ("W2B_NODE_PHASES_INVALID", "mapping node phase assemblage is invalid"),
    ("W2B_NODE_REASON_INVALID", "mapping node failure reason is invalid"),
    ("W2B_MAP_STARTING_POINT_FAILED", "mapping starting point failed"),
    ("W2B_MAP_CONVERGENCE_FAILED", "mapping internal node did not converge"),
    ("W2B_MAP_DOMAIN_FAILED", "mapping internal node was rejected by the domain"),
    ("W2B_MAP_INTERNAL_FAILED", "mapping backend reported an internal node failure"),
    ("W2B_SEGMENT_KIND_INVALID", "mapping topology segment kind is invalid"),
    ("W2B_SEGMENT_REFERENCE_INVALID", "mapping segment endpoint is invalid"),
    ("W2B_LEDGER_INVALID", "raw backend ledger is invalid"),
    ("W2B_LEDGER_ORDER_INVALID", "raw ledger ordinals are incomplete or duplicated"),
    ("W2B_FEATURE_MISMATCH", "backend ledger feature does not match the request"),
    ("W2B_STRATEGY_MISMATCH", "backend strategy or method does not match the feature"),
    ("W2B_DATABASE_MISMATCH", "backend database identity does not match the request"),
    ("W2B_TERMINATION_INVALID", "backend termination reason is inconsistent"),
    ("W2B_MAP_COMPLETED", "mapping strategy completed"),
    ("W2B_MAP_TERMINATED_BACKEND_FAILURE", "mapping strategy terminated after backend failure"),
    ("W2B_MAP_TERMINATED_NO_PROGRESS", "mapping strategy terminated without progress"),
    ("W2B_MAPPING_BACKEND_INVALID", "mapping backend does not expose map"),
    ("W2B_MAPPING_BACKEND_RAISED", "mapping backend raised instead of returning a ledger"),
    ("W2B_MAPPING_RAW_RESULT_INVALID", "mapping backend result has an invalid type"),
    ("W2B_MAPPING_DOMAIN_INVALID", "mapping node lies outside the declared domain"),
    ("W2B_MAPPING_TOPOLOGY_INVALID", "mapping topology is inconsistent with its nodes"),
    ("W2B_SOLIDIFICATION_BACKEND_INVALID", "solidification backend does not expose simulate"),
    ("W2B_SOLIDIFICATION_BACKEND_RAISED", "solidification backend raised instead of returning a ledger"),
    ("W2B_SOLIDIFICATION_RAW_RESULT_INVALID", "solidification backend result has an invalid type"),
    ("W2B_SOLID_STEP_INVALID", "solidification trajectory record is invalid"),
    ("W2B_SOLID_STEP_REASON_INVALID", "solidification failure reason is invalid"),
    ("W2B_SOLID_BACKEND_NODE_FAILED", "solidification backend node failed"),
    ("W2B_SOLID_BACKEND_DOMAIN_FAILED", "solidification node was rejected by the domain"),
    ("W2B_SOLID_BACKEND_INTERNAL_FAILED", "solidification backend reported an internal failure"),
    ("W2B_SOLID_BALANCE_INVALID", "solid and liquid fractions do not balance"),
    ("W2B_SOLID_PHASE_SUM_INVALID", "solid phase fractions do not match fraction solid"),
    ("W2B_SOLID_LIQUID_COMPOSITION_INVALID", "liquid composition is unavailable or inconsistent"),
    ("W2B_SOLID_TRAJECTORY_INVALID", "solidification trajectory shape is invalid"),
    ("W2B_SOLID_TEMPERATURE_DIRECTION_INVALID", "successful trajectory temperatures do not decrease"),
    ("W2B_SOLID_PROGRESS_INVALID", "fraction solid decreases along the successful trajectory"),
    ("W2B_SOLID_INITIAL_STATE_INVALID", "trajectory does not start from the declared liquid state"),
    ("W2B_SOLID_TERMINAL_STATE_INVALID", "converged trajectory does not satisfy its method terminal condition"),
    ("W2B_EQ_NO_LIQUID_REACHED", "equilibrium path reached the no-liquid terminal state"),
    ("W2B_SCHEIL_LIQUID_THRESHOLD_REACHED", "Scheil path reached its declared liquid threshold"),
    ("W2B_SOLID_PATH_BACKEND_TERMINATED", "solidification path terminated after backend failure"),
    ("W2B_SOLID_PATH_NO_PROGRESS", "solidification path terminated without progress"),
)
WAVE2B_PATH_REASON_CODES = _MappingProxyType(dict(_REASON_DESCRIPTIONS))

_MAPPING_FAILURE_REASONS = frozenset(
    {
        "W2B_MAP_STARTING_POINT_FAILED",
        "W2B_MAP_CONVERGENCE_FAILED",
        "W2B_MAP_DOMAIN_FAILED",
        "W2B_MAP_INTERNAL_FAILED",
    }
)
_SOLID_FAILURE_REASONS = frozenset(
    {
        "W2B_SOLID_BACKEND_NODE_FAILED",
        "W2B_SOLID_BACKEND_DOMAIN_FAILED",
        "W2B_SOLID_BACKEND_INTERNAL_FAILED",
    }
)
_MAP_FAILURE_TERMINATIONS = frozenset(
    {
        "W2B_MAP_TERMINATED_BACKEND_FAILURE",
        "W2B_MAP_TERMINATED_NO_PROGRESS",
    }
)
_SOLID_FAILURE_TERMINATIONS = frozenset(
    {
        "W2B_SOLID_PATH_BACKEND_TERMINATED",
        "W2B_SOLID_PATH_NO_PROGRESS",
    }
)
_MAPPING_NODE_KINDS = frozenset(
    {"BOUNDARY_NODE", "INTERNAL_NODE", "INVARIANT_NODE", "STARTING_POINT"}
)
_SEGMENT_KINDS_BY_FEATURE = _MappingProxyType({
    "binary_phase_diagram": frozenset({"BOUNDARY", "INVARIANT_LINK", "TIELINE"}),
    "multicomponent_isopleth": frozenset({"INVARIANT_LINK", "ZPF"}),
    "ternary_phase_diagram": frozenset({"BOUNDARY", "THREE_PHASE_LINK", "TIELINE"}),
})

_NAME_CHARACTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_#:+-.")
_TOKEN_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_#:+-."
)
_COORDINATE_CHARACTERS = _NAME_CHARACTERS | frozenset("()")
_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_BALANCE_TOLERANCE = 1.0e-10
_DOMAIN_TOLERANCE = 1.0e-12


class PathAdapterError(ValueError):
    """Fail-closed adapter error carrying one stable machine reason code."""

    __slots__ = ("reason_code",)

    def __init__(self, reason_code: str) -> None:
        if (
            type(reason_code) is not str
            or reason_code not in WAVE2B_PATH_REASON_CODES
        ):
            raise RuntimeError("Unknown Wave 2B path-adapter reason code")
        self.reason_code = reason_code
        super().__init__(reason_code)


def _fail(reason_code: str) -> None:
    raise PathAdapterError(reason_code)


def _token(value: object, reason_code: str, *, maximum: int = 128) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > maximum
        or any(character not in _TOKEN_CHARACTERS for character in value)
    ):
        _fail(reason_code)
    return value


def _name(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 64
        or any(character not in _NAME_CHARACTERS for character in value)
    ):
        _fail("W2B_NAME_INVALID")
    return value


def _coordinate_name(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 72
        or any(character not in _COORDINATE_CHARACTERS for character in value)
    ):
        _fail("W2B_NODE_COORDINATES_INVALID")
    return value


def _number(value: object) -> float:
    if type(value) not in (int, float):
        _fail("W2B_NUMBER_INVALID")
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise PathAdapterError("W2B_NUMBER_NONFINITE") from error
    if not _math.isfinite(result):
        _fail("W2B_NUMBER_NONFINITE")
    return 0.0 if result == 0.0 else result


def _safe_fsum(values: object, reason_code: str) -> float:
    try:
        result = _math.fsum(values)  # type: ignore[arg-type]
    except (OverflowError, TypeError, ValueError) as error:
        raise PathAdapterError(reason_code) from error
    if not _math.isfinite(result):
        _fail(reason_code)
    return 0.0 if result == 0.0 else result


def _positive(value: object, reason_code: str) -> float:
    result = _number(value)
    if result <= 0.0:
        _fail(reason_code)
    return result


def _fraction(value: object) -> float:
    result = _number(value)
    if result < 0.0 or result > 1.0:
        _fail("W2B_FRACTION_INVALID")
    return result


def _ordinal(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("W2B_NODE_ORDINAL_INVALID")
    return value


def _names(value: object, *, allow_empty: bool = False) -> tuple[str, ...]:
    if type(value) is not tuple or (not value and not allow_empty):
        _fail("W2B_NAMES_INVALID")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        item_name = _name(item)
        if item_name in seen:
            _fail("W2B_NAME_DUPLICATE")
        seen.add(item_name)
        result.append(item_name)
    return tuple(sorted(result))


def _components(value: object) -> tuple[str, ...]:
    names = _names(value)
    if "VA" not in names or len(names) < 3:
        _fail("W2B_COMPONENT_SET_INVALID")
    return tuple(name for name in names if name != "VA") + ("VA",)


def _named_nonnegative(
    value: object,
    *,
    allow_empty: bool,
    reason_code: str,
) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple or (not value and not allow_empty):
        _fail(reason_code)
    rows: list[tuple[str, float]] = []
    seen: set[str] = set()
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            _fail(reason_code)
        item_name = _name(pair[0])
        if item_name in seen:
            _fail("W2B_NAME_DUPLICATE")
        seen.add(item_name)
        amount = _number(pair[1])
        if amount < 0.0:
            _fail(reason_code)
        rows.append((item_name, amount))
    return tuple(sorted(rows, key=lambda row: row[0]))


def _composition(
    value: object,
    *,
    expected_names: tuple[str, ...] | None,
) -> tuple[tuple[str, float], ...]:
    rows = _named_nonnegative(
        value,
        allow_empty=False,
        reason_code="W2B_COMPOSITION_INVALID",
    )
    if expected_names is not None:
        by_name = dict(rows)
        if set(by_name) != set(expected_names):
            _fail("W2B_COMPONENT_SET_INVALID")
        rows = tuple((name, by_name[name]) for name in expected_names)
    total = _safe_fsum(
        (amount for _name_value, amount in rows),
        "W2B_COMPOSITION_SUM_INVALID",
    )
    if abs(total - 1.0) > _BALANCE_TOLERANCE:
        _fail("W2B_COMPOSITION_SUM_INVALID")
    return rows


def _partial_composition(value: object) -> tuple[tuple[str, float], ...]:
    rows = _named_nonnegative(
        value,
        allow_empty=False,
        reason_code="W2B_COMPOSITION_INVALID",
    )
    total = _safe_fsum(
        (amount for _item_name, amount in rows),
        "W2B_COMPOSITION_SUM_INVALID",
    )
    if total >= 1.0:
        _fail("W2B_COMPOSITION_SUM_INVALID")
    return rows


def _coordinates(value: object) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple or not value:
        _fail("W2B_NODE_COORDINATES_INVALID")
    rows: list[tuple[str, float]] = []
    seen: set[str] = set()
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            _fail("W2B_NODE_COORDINATES_INVALID")
        coordinate = _coordinate_name(pair[0])
        if coordinate in seen:
            _fail("W2B_NODE_COORDINATES_INVALID")
        seen.add(coordinate)
        rows.append((coordinate, _number(pair[1])))
    return tuple(rows)


@_dataclass(frozen=True, slots=True)
class DatabaseIdentity:
    """Exact database/profile identity without an implicit Fe policy choice."""

    family: str
    database_id: str
    database_sha256: str
    profile_id: str
    profile_role: str
    fe_baseline_decision: str
    c15_exclusion_decision: str

    def __post_init__(self) -> None:
        if type(self.family) is not str or self.family not in SUPPORTED_DATABASE_FAMILIES:
            _fail("W2B_DB_FAMILY_INVALID")
        database_id = _token(self.database_id, "W2B_DB_ID_INVALID")
        if (
            type(self.database_sha256) is not str
            or len(self.database_sha256) != 64
            or any(character not in _SHA256_CHARACTERS for character in self.database_sha256)
        ):
            _fail("W2B_DB_SHA256_INVALID")
        profile_id = _token(self.profile_id, "W2B_DB_PROFILE_INVALID")
        if type(self.profile_role) is not str or self.profile_role not in PROFILE_ROLES:
            _fail("W2B_DB_PROFILE_ROLE_INVALID")
        if self.family == "fe":
            if (
                type(self.fe_baseline_decision) is not str
                or type(self.c15_exclusion_decision) is not str
            ):
                _fail("W2B_FE_POLICY_STATE_INVALID")
            if self.profile_id not in SUPPORTED_FE_PROFILE_IDS:
                _fail("W2B_DB_PROFILE_INVALID")
            if self.profile_role != _FE_PROFILE_ROLES[self.profile_id]:
                _fail("W2B_DB_PROFILE_ROLE_INVALID")
            if (
                self.fe_baseline_decision != FE_POLICY_UNDECIDED
                or self.c15_exclusion_decision != FE_POLICY_UNDECIDED
            ):
                _fail("W2B_FE_POLICY_STATE_INVALID")
        else:
            if (
                type(self.fe_baseline_decision) is not str
                or type(self.c15_exclusion_decision) is not str
            ):
                _fail("W2B_NON_FE_POLICY_STATE_INVALID")
            if (
                self.fe_baseline_decision != POLICY_NOT_APPLICABLE
                or self.c15_exclusion_decision != POLICY_NOT_APPLICABLE
            ):
                _fail("W2B_NON_FE_POLICY_STATE_INVALID")
        object.__setattr__(self, "database_id", database_id)
        object.__setattr__(self, "profile_id", profile_id)


@_dataclass(frozen=True, slots=True)
class PhaseSelection:
    """Exact candidate/requested/excluded/effective phase binding.

    ``effective_phases`` must equal ``requested_phases``.  A backend therefore
    cannot silently filter a user request after this contract is created.
    """

    candidate_phases: tuple[str, ...]
    requested_phases: tuple[str, ...]
    excluded_phases: tuple[str, ...]
    effective_phases: tuple[str, ...]

    def __post_init__(self) -> None:
        candidates = _names(self.candidate_phases)
        requested = _names(self.requested_phases)
        excluded = _names(self.excluded_phases, allow_empty=True)
        effective = _names(self.effective_phases)
        candidate_set = set(candidates)
        requested_set = set(requested)
        if not requested_set.issubset(candidate_set):
            _fail("W2B_PHASE_SELECTION_INVALID")
        if set(excluded) != candidate_set - requested_set:
            _fail("W2B_PHASE_SELECTION_INVALID")
        if effective != requested:
            _fail("W2B_PHASE_SELECTION_INVALID")
        object.__setattr__(self, "candidate_phases", candidates)
        object.__setattr__(self, "requested_phases", requested)
        object.__setattr__(self, "excluded_phases", excluded)
        object.__setattr__(self, "effective_phases", effective)


def _phase_selection(
    value: object,
    database: DatabaseIdentity,
) -> PhaseSelection:
    checked = _reconstruct_phase_selection(value)
    if database.family == "fe":
        c15 = "C15_LAVES"
        if (
            c15 not in checked.candidate_phases
            or c15 not in checked.requested_phases
            or c15 in checked.excluded_phases
            or c15 not in checked.effective_phases
        ):
            _fail("W2B_FE_C15_DECISION_REQUIRED")
    return checked


@_dataclass(frozen=True, slots=True)
class ClosedRange:
    """Declared outer mapping range; it is not a generated generic grid."""

    lower: float
    upper: float
    seed_step: float

    def __post_init__(self) -> None:
        lower = _number(self.lower)
        upper = _number(self.upper)
        step = _positive(self.seed_step, "W2B_RANGE_INVALID")
        width = upper - lower
        if not _math.isfinite(width) or upper <= lower or step > width:
            _fail("W2B_RANGE_INVALID")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)
        object.__setattr__(self, "seed_step", step)


def _database(value: object) -> DatabaseIdentity:
    return _reconstruct_database(value)


def _pressure(value: object) -> float:
    """Validate an explicit pressure; solidification adds its fixed-value gate."""

    return _positive(value, "W2B_PRESSURE_INVALID")


def _temperature(value: object) -> float:
    return _positive(value, "W2B_TEMPERATURE_INVALID")


def _temperature_range(value: object) -> ClosedRange:
    checked = _reconstruct_range(value)
    if checked.lower <= 0.0:
        _fail("W2B_TEMPERATURE_INVALID")
    return checked


def _fraction_range(value: object) -> ClosedRange:
    checked = _reconstruct_range(value)
    if checked.lower < 0.0 or checked.upper > 1.0:
        _fail("W2B_RANGE_INVALID")
    return checked


@_dataclass(frozen=True, slots=True)
class BinaryPhaseDiagramRequest:
    """Binary Mapping API request with explicit positive pressure."""

    database: DatabaseIdentity
    left_component: str
    right_component: str
    phase_selection: PhaseSelection
    pressure_pa: float
    right_fraction: ClosedRange
    temperature_k: ClosedRange

    def __post_init__(self) -> None:
        database = _database(self.database)
        left = _name(self.left_component)
        right = _name(self.right_component)
        if left == right or "VA" in (left, right):
            _fail("W2B_BINARY_SYSTEM_INVALID")
        phase_selection = _phase_selection(self.phase_selection, database)
        pressure = _pressure(self.pressure_pa)
        right_fraction = _fraction_range(self.right_fraction)
        temperature = _temperature_range(self.temperature_k)
        object.__setattr__(self, "database", database)
        object.__setattr__(self, "left_component", left)
        object.__setattr__(self, "right_component", right)
        object.__setattr__(self, "phase_selection", phase_selection)
        object.__setattr__(self, "pressure_pa", pressure)
        object.__setattr__(self, "right_fraction", right_fraction)
        object.__setattr__(self, "temperature_k", temperature)

    @property
    def feature(self) -> str:
        return "binary_phase_diagram"

    @property
    def strategy(self) -> str:
        return _MAPPING_STRATEGIES[self.feature]

    @property
    def components(self) -> tuple[str, ...]:
        return tuple(sorted((self.left_component, self.right_component))) + ("VA",)

    @property
    def phases(self) -> tuple[str, ...]:
        return self.phase_selection.effective_phases

    @property
    def coordinate_names(self) -> tuple[str, str]:
        return (f"X({self.right_component})", "T")


@_dataclass(frozen=True, slots=True)
class MulticomponentIsoplethRequest:
    """Isopleth Mapping API request with explicit positive pressure."""

    database: DatabaseIdentity
    balance_component: str
    variable_component: str
    fixed_composition: tuple[tuple[str, float], ...]
    phase_selection: PhaseSelection
    pressure_pa: float
    variable_fraction: ClosedRange
    temperature_k: ClosedRange

    def __post_init__(self) -> None:
        database = _database(self.database)
        balance = _name(self.balance_component)
        variable = _name(self.variable_component)
        if balance == variable or "VA" in (balance, variable):
            _fail("W2B_ISOPLETH_SYSTEM_INVALID")
        fixed = _partial_composition(self.fixed_composition)
        fixed_names = {name for name, _amount in fixed}
        if balance in fixed_names or variable in fixed_names or "VA" in fixed_names:
            _fail("W2B_ISOPLETH_SYSTEM_INVALID")
        variable_fraction = _fraction_range(self.variable_fraction)
        fixed_total = _safe_fsum(
            (amount for _name_value, amount in fixed),
            "W2B_COMPOSITION_SUM_INVALID",
        )
        if fixed_total + variable_fraction.upper >= 1.0:
            _fail("W2B_ISOPLETH_SYSTEM_INVALID")
        phase_selection = _phase_selection(self.phase_selection, database)
        pressure = _pressure(self.pressure_pa)
        temperature = _temperature_range(self.temperature_k)
        object.__setattr__(self, "database", database)
        object.__setattr__(self, "balance_component", balance)
        object.__setattr__(self, "variable_component", variable)
        object.__setattr__(self, "fixed_composition", fixed)
        object.__setattr__(self, "phase_selection", phase_selection)
        object.__setattr__(self, "pressure_pa", pressure)
        object.__setattr__(self, "variable_fraction", variable_fraction)
        object.__setattr__(self, "temperature_k", temperature)

    @property
    def feature(self) -> str:
        return "multicomponent_isopleth"

    @property
    def strategy(self) -> str:
        return _MAPPING_STRATEGIES[self.feature]

    @property
    def components(self) -> tuple[str, ...]:
        names = {
            self.balance_component,
            self.variable_component,
            *(name for name, _amount in self.fixed_composition),
        }
        return tuple(sorted(names)) + ("VA",)

    @property
    def coordinate_names(self) -> tuple[str, str]:
        return (f"X({self.variable_component})", "T")

    @property
    def phases(self) -> tuple[str, ...]:
        return self.phase_selection.effective_phases


@_dataclass(frozen=True, slots=True)
class TernaryPhaseDiagramRequest:
    """Ternary Mapping API request with explicit positive pressure."""

    database: DatabaseIdentity
    dependent_component: str
    x_component: str
    y_component: str
    phase_selection: PhaseSelection
    pressure_pa: float
    temperature_k: float
    starting_point_step: float

    def __post_init__(self) -> None:
        database = _database(self.database)
        dependent = _name(self.dependent_component)
        x_component = _name(self.x_component)
        y_component = _name(self.y_component)
        if (
            len({dependent, x_component, y_component}) != 3
            or "VA" in {dependent, x_component, y_component}
        ):
            _fail("W2B_TERNARY_SYSTEM_INVALID")
        phase_selection = _phase_selection(self.phase_selection, database)
        pressure = _pressure(self.pressure_pa)
        temperature = _temperature(self.temperature_k)
        step = _positive(self.starting_point_step, "W2B_TERNARY_STEP_INVALID")
        if step >= 0.25:
            _fail("W2B_TERNARY_STEP_INVALID")
        object.__setattr__(self, "database", database)
        object.__setattr__(self, "dependent_component", dependent)
        object.__setattr__(self, "x_component", x_component)
        object.__setattr__(self, "y_component", y_component)
        object.__setattr__(self, "phase_selection", phase_selection)
        object.__setattr__(self, "pressure_pa", pressure)
        object.__setattr__(self, "temperature_k", temperature)
        object.__setattr__(self, "starting_point_step", step)

    @property
    def feature(self) -> str:
        return "ternary_phase_diagram"

    @property
    def strategy(self) -> str:
        return _MAPPING_STRATEGIES[self.feature]

    @property
    def components(self) -> tuple[str, ...]:
        return tuple(
            sorted((self.dependent_component, self.x_component, self.y_component))
        ) + ("VA",)

    @property
    def coordinate_names(self) -> tuple[str, str]:
        return (f"X({self.x_component})", f"X({self.y_component})")

    @property
    def phases(self) -> tuple[str, ...]:
        return self.phase_selection.effective_phases


MappingRequest: _TypeAlias = (
    BinaryPhaseDiagramRequest
    | MulticomponentIsoplethRequest
    | TernaryPhaseDiagramRequest
)


@_dataclass(frozen=True, slots=True)
class MappingNodeRecord:
    """One raw strategy node, including an explicit failed attempt."""

    ordinal: int
    node_id: str
    kind: str
    outcome: str
    coordinates: tuple[tuple[str, float], ...]
    phases: tuple[str, ...]
    reason_code: str | None

    def __post_init__(self) -> None:
        ordinal = _ordinal(self.ordinal)
        node_id = _token(self.node_id, "W2B_NODE_ID_INVALID", maximum=96)
        if type(self.kind) is not str or self.kind not in _MAPPING_NODE_KINDS:
            _fail("W2B_NODE_KIND_INVALID")
        if type(self.outcome) is not str or self.outcome not in ("FAIL", "PASS"):
            _fail("W2B_NODE_OUTCOME_INVALID")
        coordinates = _coordinates(self.coordinates)
        phases = _names(self.phases, allow_empty=True)
        if self.outcome == "PASS":
            if not phases:
                _fail("W2B_NODE_PHASES_INVALID")
            if self.reason_code is not None:
                _fail("W2B_NODE_REASON_INVALID")
        else:
            if phases:
                _fail("W2B_NODE_PHASES_INVALID")
            if (
                type(self.reason_code) is not str
                or self.reason_code not in _MAPPING_FAILURE_REASONS
            ):
                _fail("W2B_NODE_REASON_INVALID")
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "coordinates", coordinates)
        object.__setattr__(self, "phases", phases)


@_dataclass(frozen=True, slots=True)
class MappingSegmentRecord:
    """One raw topology connection emitted by a specialized mapping strategy."""

    ordinal: int
    kind: str
    start_node_id: str
    end_node_id: str
    phases: tuple[str, ...]

    def __post_init__(self) -> None:
        ordinal = _ordinal(self.ordinal)
        if type(self.kind) is not str or self.kind not in {
            "BOUNDARY",
            "INVARIANT_LINK",
            "THREE_PHASE_LINK",
            "TIELINE",
            "ZPF",
        }:
            _fail("W2B_SEGMENT_KIND_INVALID")
        start = _token(self.start_node_id, "W2B_SEGMENT_REFERENCE_INVALID", maximum=96)
        end = _token(self.end_node_id, "W2B_SEGMENT_REFERENCE_INVALID", maximum=96)
        if start == end:
            _fail("W2B_SEGMENT_REFERENCE_INVALID")
        phases = _names(self.phases)
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "start_node_id", start)
        object.__setattr__(self, "end_node_id", end)
        object.__setattr__(self, "phases", phases)


def _ordered_records(
    value: object,
    record_type: type,
    *,
    allow_empty: bool,
) -> tuple:
    if type(value) is not tuple or (not value and not allow_empty):
        _fail("W2B_LEDGER_INVALID")
    if any(type(record) is not record_type for record in value):
        _fail("W2B_LEDGER_INVALID")
    if record_type is MappingNodeRecord:
        rebuilt = tuple(_reconstruct_mapping_node(record) for record in value)
    elif record_type is MappingSegmentRecord:
        rebuilt = tuple(_reconstruct_mapping_segment(record) for record in value)
    elif record_type is SolidificationStepRecord:
        rebuilt = tuple(_reconstruct_solidification_step(record) for record in value)
    else:
        _fail("W2B_LEDGER_INVALID")
    ordered = tuple(sorted(rebuilt, key=lambda record: record.ordinal))
    if tuple(record.ordinal for record in ordered) != tuple(range(len(ordered))):
        _fail("W2B_LEDGER_ORDER_INVALID")
    return ordered


@_dataclass(frozen=True, slots=True)
class RawMappingLedger:
    """Unfiltered mapping topology and node attempts returned by a backend."""

    database: DatabaseIdentity
    feature: str
    strategy: str
    nodes: tuple[MappingNodeRecord, ...]
    segments: tuple[MappingSegmentRecord, ...]
    completed: bool
    termination_reason_code: str

    def __post_init__(self) -> None:
        database = _database(self.database)
        if type(self.feature) is not str or self.feature not in _MAPPING_STRATEGIES:
            _fail("W2B_FEATURE_MISMATCH")
        if (
            type(self.strategy) is not str
            or self.strategy != _MAPPING_STRATEGIES[self.feature]
        ):
            _fail("W2B_STRATEGY_MISMATCH")
        nodes = _ordered_records(self.nodes, MappingNodeRecord, allow_empty=False)
        node_ids = tuple(node.node_id for node in nodes)
        if len(set(node_ids)) != len(node_ids):
            _fail("W2B_NODE_ID_INVALID")
        segments = _ordered_records(
            self.segments,
            MappingSegmentRecord,
            allow_empty=True,
        )
        if type(self.completed) is not bool:
            _fail("W2B_BOOL_INVALID")
        if type(self.termination_reason_code) is not str:
            _fail("W2B_TERMINATION_INVALID")
        if self.completed:
            if self.termination_reason_code != "W2B_MAP_COMPLETED":
                _fail("W2B_TERMINATION_INVALID")
        elif self.termination_reason_code not in _MAP_FAILURE_TERMINATIONS:
            _fail("W2B_TERMINATION_INVALID")
        if (
            self.termination_reason_code
            == "W2B_MAP_TERMINATED_BACKEND_FAILURE"
            and nodes[-1].outcome != "FAIL"
        ):
            _fail("W2B_TERMINATION_INVALID")
        object.__setattr__(self, "database", database)
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "segments", segments)


def _in_range(value: float, declared_range: ClosedRange) -> bool:
    return (
        declared_range.lower - _DOMAIN_TOLERANCE
        <= value
        <= declared_range.upper + _DOMAIN_TOLERANCE
    )


def _has_feature_geometric_span(
    request: MappingRequest,
    pass_nodes: tuple[MappingNodeRecord, ...],
) -> bool:
    """Return whether successful nodes witness a nonzero feature geometry."""

    if len(pass_nodes) < 2:
        return False
    if type(request) in (
        BinaryPhaseDiagramRequest,
        MulticomponentIsoplethRequest,
    ):
        for coordinate_index in (0, 1):
            values = tuple(
                node.coordinates[coordinate_index][1]
                for node in pass_nodes
            )
            if max(values) > min(values):
                return True
        return False

    first_x = pass_nodes[0].coordinates[0][1]
    first_y = pass_nodes[0].coordinates[1][1]
    first_z = 1.0 - first_x - first_y
    for node in pass_nodes[1:]:
        x_value = node.coordinates[0][1]
        y_value = node.coordinates[1][1]
        z_value = 1.0 - x_value - y_value
        if _math.hypot(
            x_value - first_x,
            y_value - first_y,
            z_value - first_z,
        ) > 0.0:
            return True
    return False


def _validate_mapping_result(request: MappingRequest, ledger: RawMappingLedger) -> None:
    if ledger.database != request.database:
        _fail("W2B_DATABASE_MISMATCH")
    if ledger.feature != request.feature:
        _fail("W2B_FEATURE_MISMATCH")
    if ledger.strategy != request.strategy:
        _fail("W2B_STRATEGY_MISMATCH")
    requested_phases = set(request.phases)
    pass_nodes: dict[str, MappingNodeRecord] = {}
    pass_coordinates: set[tuple[tuple[str, float], ...]] = set()
    for node in ledger.nodes:
        if tuple(name for name, _amount in node.coordinates) != request.coordinate_names:
            _fail("W2B_NODE_COORDINATES_INVALID")
        coordinate_values = tuple(amount for _name_value, amount in node.coordinates)
        if type(request) is TernaryPhaseDiagramRequest:
            x_value, y_value = coordinate_values
            if (
                x_value < -_DOMAIN_TOLERANCE
                or y_value < -_DOMAIN_TOLERANCE
                or x_value + y_value > 1.0 + _DOMAIN_TOLERANCE
            ):
                _fail("W2B_MAPPING_DOMAIN_INVALID")
        else:
            x_value, temperature = coordinate_values
            if not _in_range(x_value, request.right_fraction if type(request) is BinaryPhaseDiagramRequest else request.variable_fraction):
                _fail("W2B_MAPPING_DOMAIN_INVALID")
            if not _in_range(temperature, request.temperature_k):
                _fail("W2B_MAPPING_DOMAIN_INVALID")
        if node.outcome == "PASS":
            if not set(node.phases).issubset(requested_phases):
                _fail("W2B_NODE_PHASES_INVALID")
            if node.coordinates in pass_coordinates:
                _fail("W2B_MAPPING_TOPOLOGY_INVALID")
            pass_coordinates.add(node.coordinates)
            pass_nodes[node.node_id] = node
    allowed_segment_kinds = _SEGMENT_KINDS_BY_FEATURE[request.feature]
    adjacency = {node_id: set() for node_id in pass_nodes}
    for segment in ledger.segments:
        if segment.kind not in allowed_segment_kinds:
            _fail("W2B_SEGMENT_KIND_INVALID")
        if (
            segment.start_node_id not in pass_nodes
            or segment.end_node_id not in pass_nodes
        ):
            _fail("W2B_SEGMENT_REFERENCE_INVALID")
        if not set(segment.phases).issubset(requested_phases):
            _fail("W2B_PHASE_SET_INVALID")
        start_node = pass_nodes[segment.start_node_id]
        end_node = pass_nodes[segment.end_node_id]
        endpoint_assemblage = tuple(
            sorted(set(start_node.phases) | set(end_node.phases))
        )
        if segment.phases != endpoint_assemblage:
            _fail("W2B_PHASE_SET_INVALID")
        adjacency[segment.start_node_id].add(segment.end_node_id)
        adjacency[segment.end_node_id].add(segment.start_node_id)
    if ledger.completed and (
        len(pass_nodes) < 2 or len(ledger.segments) < 1
    ):
        _fail("W2B_MAPPING_TOPOLOGY_INVALID")
    if ledger.completed and not _has_feature_geometric_span(
        request,
        tuple(pass_nodes[node_id] for node_id in sorted(pass_nodes)),
    ):
        _fail("W2B_MAPPING_TOPOLOGY_INVALID")
    if len(pass_nodes) > 1:
        start_id = min(pass_nodes)
        visited: set[str] = set()
        pending = [start_id]
        while pending:
            node_id = pending.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            pending.extend(sorted(adjacency[node_id] - visited, reverse=True))
        if visited != set(pass_nodes):
            _fail("W2B_MAPPING_TOPOLOGY_INVALID")


@_dataclass(frozen=True, slots=True)
class MappingResult:
    """Validated result retaining every raw mapping node and topology segment."""

    request: MappingRequest
    ledger: RawMappingLedger

    def __post_init__(self) -> None:
        try:
            request = _reconstruct_mapping_request(self.request)
            ledger = _reconstruct_mapping_ledger(self.ledger)
            _validate_mapping_result(request, ledger)
        except PathAdapterError:
            raise
        except Exception as error:
            raise PathAdapterError("W2B_MAPPING_RAW_RESULT_INVALID") from error
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "ledger", ledger)

    @property
    def status(self) -> str:
        failed = any(node.outcome == "FAIL" for node in self.ledger.nodes)
        if self.ledger.completed:
            return "COMPLETE_WITH_RETAINED_FAILURES" if failed else "COMPLETE"
        return "FAILED_WITH_RETAINED_LEDGER"

    @property
    def failed_nodes(self) -> tuple[MappingNodeRecord, ...]:
        return tuple(node for node in self.ledger.nodes if node.outcome == "FAIL")


def _solidification_system(
    database: object,
    components: object,
    phase_selection: object,
    composition: object,
    liquid_phase: object,
    pressure_pa: object,
    start_temperature_k: object,
    step_temperature_k: object,
    adaptive: object,
    pdens: object,
) -> tuple[
    DatabaseIdentity,
    tuple[str, ...],
    PhaseSelection,
    tuple[tuple[str, float], ...],
    str,
    float,
    float,
    float,
    bool,
    int,
]:
    checked_database = _database(database)
    checked_components = _components(components)
    pure_components = tuple(name for name in checked_components if name != "VA")
    checked_phase_selection = _phase_selection(
        phase_selection,
        checked_database,
    )
    checked_liquid = _name(liquid_phase)
    if checked_liquid not in checked_phase_selection.effective_phases:
        _fail("W2B_LIQUID_PHASE_REQUIRED")
    checked_composition = _composition(composition, expected_names=pure_components)
    checked_pressure = _pressure(pressure_pa)
    if checked_pressure != SOLIDIFICATION_PRESSURE_PA:
        _fail("W2B_SOLID_PRESSURE_UNSUPPORTED")
    checked_start = _temperature(start_temperature_k)
    checked_step = _positive(step_temperature_k, "W2B_TEMPERATURE_INVALID")
    if checked_step >= checked_start:
        _fail("W2B_TEMPERATURE_INVALID")
    if type(adaptive) is not bool:
        _fail("W2B_BOOL_INVALID")
    if type(pdens) is not int or not 1 <= pdens <= 100000:
        _fail("W2B_INTEGER_INVALID")
    return (
        checked_database,
        checked_components,
        checked_phase_selection,
        checked_composition,
        checked_liquid,
        checked_pressure,
        checked_start,
        checked_step,
        adaptive,
        pdens,
    )


@_dataclass(frozen=True, slots=True)
class EquilibriumSolidificationRequest:
    database: DatabaseIdentity
    components: tuple[str, ...]
    phase_selection: PhaseSelection
    composition: tuple[tuple[str, float], ...]
    liquid_phase: str
    pressure_pa: float
    start_temperature_k: float
    step_temperature_k: float
    adaptive: bool
    pdens: int
    binary_search_tolerance_k: float

    def __post_init__(self) -> None:
        values = _solidification_system(
            self.database,
            self.components,
            self.phase_selection,
            self.composition,
            self.liquid_phase,
            self.pressure_pa,
            self.start_temperature_k,
            self.step_temperature_k,
            self.adaptive,
            self.pdens,
        )
        tolerance = _positive(
            self.binary_search_tolerance_k,
            "W2B_TEMPERATURE_INVALID",
        )
        if tolerance > values[7]:
            _fail("W2B_TEMPERATURE_INVALID")
        for field_name, value in zip(
            (
                "database",
                "components",
                "phase_selection",
                "composition",
                "liquid_phase",
                "pressure_pa",
                "start_temperature_k",
                "step_temperature_k",
                "adaptive",
                "pdens",
            ),
            values,
        ):
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "binary_search_tolerance_k", tolerance)

    @property
    def feature(self) -> str:
        return "equilibrium_solidification"

    @property
    def method(self) -> str:
        return _SOLIDIFICATION_METHODS[self.feature]

    @property
    def phases(self) -> tuple[str, ...]:
        return self.phase_selection.effective_phases


@_dataclass(frozen=True, slots=True)
class ScheilSolidificationRequest:
    database: DatabaseIdentity
    components: tuple[str, ...]
    phase_selection: PhaseSelection
    composition: tuple[tuple[str, float], ...]
    liquid_phase: str
    pressure_pa: float
    start_temperature_k: float
    step_temperature_k: float
    adaptive: bool
    pdens: int
    stop_liquid_fraction: float

    def __post_init__(self) -> None:
        values = _solidification_system(
            self.database,
            self.components,
            self.phase_selection,
            self.composition,
            self.liquid_phase,
            self.pressure_pa,
            self.start_temperature_k,
            self.step_temperature_k,
            self.adaptive,
            self.pdens,
        )
        stop = _fraction(self.stop_liquid_fraction)
        if stop <= 0.0 or stop >= 1.0:
            _fail("W2B_FRACTION_INVALID")
        for field_name, value in zip(
            (
                "database",
                "components",
                "phase_selection",
                "composition",
                "liquid_phase",
                "pressure_pa",
                "start_temperature_k",
                "step_temperature_k",
                "adaptive",
                "pdens",
            ),
            values,
        ):
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "stop_liquid_fraction", stop)

    @property
    def feature(self) -> str:
        return "scheil_solidification"

    @property
    def method(self) -> str:
        return _SOLIDIFICATION_METHODS[self.feature]

    @property
    def phases(self) -> tuple[str, ...]:
        return self.phase_selection.effective_phases


SolidificationRequest: _TypeAlias = (
    EquilibriumSolidificationRequest | ScheilSolidificationRequest
)


@_dataclass(frozen=True, slots=True)
class SolidificationStepRecord:
    """One attempted trajectory node; failures retain attempted temperature."""

    ordinal: int
    outcome: str
    temperature_k: float
    solid_fraction: float | None
    liquid_fraction: float | None
    phase_fractions: tuple[tuple[str, float], ...]
    liquid_composition: tuple[tuple[str, float], ...]
    reason_code: str | None

    def __post_init__(self) -> None:
        ordinal = _ordinal(self.ordinal)
        if type(self.outcome) is not str or self.outcome not in ("FAIL", "PASS"):
            _fail("W2B_SOLID_STEP_INVALID")
        temperature = _temperature(self.temperature_k)
        if type(self.phase_fractions) is not tuple or type(self.liquid_composition) is not tuple:
            _fail("W2B_SOLID_STEP_INVALID")
        if self.outcome == "FAIL":
            if (
                self.solid_fraction is not None
                or self.liquid_fraction is not None
                or self.phase_fractions
                or self.liquid_composition
            ):
                _fail("W2B_SOLID_STEP_INVALID")
            if (
                type(self.reason_code) is not str
                or self.reason_code not in _SOLID_FAILURE_REASONS
            ):
                _fail("W2B_SOLID_STEP_REASON_INVALID")
            phase_fractions: tuple[tuple[str, float], ...] = tuple()
            liquid_composition: tuple[tuple[str, float], ...] = tuple()
        else:
            if self.solid_fraction is None or self.liquid_fraction is None:
                _fail("W2B_SOLID_STEP_INVALID")
            solid = _fraction(self.solid_fraction)
            liquid = _fraction(self.liquid_fraction)
            if abs(
                _safe_fsum((solid, liquid), "W2B_SOLID_BALANCE_INVALID") - 1.0
            ) > _BALANCE_TOLERANCE:
                _fail("W2B_SOLID_BALANCE_INVALID")
            phase_fractions = _named_nonnegative(
                self.phase_fractions,
                allow_empty=solid == 0.0,
                reason_code="W2B_SOLID_PHASE_SUM_INVALID",
            )
            if any(amount > 1.0 for _phase, amount in phase_fractions):
                _fail("W2B_SOLID_PHASE_SUM_INVALID")
            if abs(
                _safe_fsum(
                    (amount for _phase, amount in phase_fractions),
                    "W2B_SOLID_PHASE_SUM_INVALID",
                )
                - solid
            ) > _BALANCE_TOLERANCE:
                _fail("W2B_SOLID_PHASE_SUM_INVALID")
            if self.liquid_composition:
                liquid_composition = _composition(
                    self.liquid_composition,
                    expected_names=None,
                )
            else:
                liquid_composition = tuple()
            if liquid > _BALANCE_TOLERANCE and not liquid_composition:
                _fail("W2B_SOLID_LIQUID_COMPOSITION_INVALID")
            if self.reason_code is not None:
                _fail("W2B_SOLID_STEP_REASON_INVALID")
            object.__setattr__(self, "solid_fraction", solid)
            object.__setattr__(self, "liquid_fraction", liquid)
        object.__setattr__(self, "ordinal", ordinal)
        object.__setattr__(self, "temperature_k", temperature)
        object.__setattr__(self, "phase_fractions", phase_fractions)
        object.__setattr__(self, "liquid_composition", liquid_composition)


@_dataclass(frozen=True, slots=True)
class RawSolidificationLedger:
    """Unfiltered equilibrium or Scheil trajectory returned by a backend."""

    database: DatabaseIdentity
    feature: str
    method: str
    records: tuple[SolidificationStepRecord, ...]
    converged: bool
    termination_reason_code: str

    def __post_init__(self) -> None:
        database = _database(self.database)
        if (
            type(self.feature) is not str
            or self.feature not in _SOLIDIFICATION_METHODS
        ):
            _fail("W2B_FEATURE_MISMATCH")
        if (
            type(self.method) is not str
            or self.method != _SOLIDIFICATION_METHODS[self.feature]
        ):
            _fail("W2B_STRATEGY_MISMATCH")
        records = _ordered_records(
            self.records,
            SolidificationStepRecord,
            allow_empty=False,
        )
        if type(self.converged) is not bool:
            _fail("W2B_BOOL_INVALID")
        if type(self.termination_reason_code) is not str:
            _fail("W2B_TERMINATION_INVALID")
        expected_success = (
            "W2B_EQ_NO_LIQUID_REACHED"
            if self.feature == "equilibrium_solidification"
            else "W2B_SCHEIL_LIQUID_THRESHOLD_REACHED"
        )
        if self.converged:
            if self.termination_reason_code != expected_success:
                _fail("W2B_TERMINATION_INVALID")
        elif self.termination_reason_code not in _SOLID_FAILURE_TERMINATIONS:
            _fail("W2B_TERMINATION_INVALID")
        if self.converged and records[-1].outcome != "PASS":
            _fail("W2B_TERMINATION_INVALID")
        if (
            self.termination_reason_code
            == "W2B_SOLID_PATH_BACKEND_TERMINATED"
            and records[-1].outcome != "FAIL"
        ):
            _fail("W2B_TERMINATION_INVALID")
        object.__setattr__(self, "database", database)
        object.__setattr__(self, "records", records)


def _validate_solidification_result(
    request: SolidificationRequest,
    ledger: RawSolidificationLedger,
) -> None:
    if ledger.database != request.database:
        _fail("W2B_DATABASE_MISMATCH")
    if ledger.feature != request.feature:
        _fail("W2B_FEATURE_MISMATCH")
    if ledger.method != request.method:
        _fail("W2B_STRATEGY_MISMATCH")
    first_record = ledger.records[0]
    if abs(first_record.temperature_k - request.start_temperature_k) > _DOMAIN_TOLERANCE:
        _fail("W2B_SOLID_INITIAL_STATE_INVALID")
    pure_components = tuple(name for name in request.components if name != "VA")
    requested_solid_phases = set(request.phases) - {request.liquid_phase}
    successful: list[SolidificationStepRecord] = []
    for record_index, record in enumerate(ledger.records):
        if record.temperature_k > request.start_temperature_k + _DOMAIN_TOLERANCE:
            _fail("W2B_SOLID_TEMPERATURE_DIRECTION_INVALID")
        if (
            record_index > 0
            and record.temperature_k
            >= ledger.records[record_index - 1].temperature_k
        ):
            _fail("W2B_SOLID_TEMPERATURE_DIRECTION_INVALID")
        if record.outcome == "FAIL":
            continue
        if record.liquid_composition and tuple(
            name for name, _amount in record.liquid_composition
        ) != pure_components:
            _fail("W2B_SOLID_LIQUID_COMPOSITION_INVALID")
        if not set(name for name, _amount in record.phase_fractions).issubset(
            requested_solid_phases
        ):
            _fail("W2B_PHASE_SET_INVALID")
        if successful:
            previous = successful[-1]
            if record.solid_fraction < previous.solid_fraction:  # type: ignore[operator]
                _fail("W2B_SOLID_PROGRESS_INVALID")
        successful.append(record)
    if successful:
        first_liquid = successful[0].liquid_composition
        if tuple(name for name, _amount in first_liquid) != pure_components:
            _fail("W2B_SOLID_LIQUID_COMPOSITION_INVALID")
        for (
            (_bulk_name, bulk_amount),
            (_liquid_name, liquid_amount),
        ) in zip(request.composition, first_liquid):
            if abs(bulk_amount - liquid_amount) > _DOMAIN_TOLERANCE:
                _fail("W2B_SOLID_LIQUID_COMPOSITION_INVALID")
    if ledger.converged:
        if len(successful) < 2:
            _fail("W2B_SOLID_TRAJECTORY_INVALID")
        first_success = successful[0]
        if (
            abs(first_success.temperature_k - request.start_temperature_k)
            > _DOMAIN_TOLERANCE
            or first_success.solid_fraction is None
            or first_success.liquid_fraction is None
            or first_success.solid_fraction > _BALANCE_TOLERANCE
            or abs(first_success.liquid_fraction - 1.0) > _BALANCE_TOLERANCE
        ):
            _fail("W2B_SOLID_INITIAL_STATE_INVALID")
        final_liquid = successful[-1].liquid_fraction
        final_solid = successful[-1].solid_fraction
        if final_liquid is None or final_solid is None:
            _fail("W2B_SOLID_TERMINAL_STATE_INVALID")
        if final_solid <= first_success.solid_fraction + _DOMAIN_TOLERANCE:
            _fail("W2B_SOLID_PROGRESS_INVALID")
        if type(request) is EquilibriumSolidificationRequest:
            if final_liquid > _BALANCE_TOLERANCE:
                _fail("W2B_SOLID_TERMINAL_STATE_INVALID")
        elif final_liquid > request.stop_liquid_fraction + _BALANCE_TOLERANCE:
            _fail("W2B_SOLID_TERMINAL_STATE_INVALID")


@_dataclass(frozen=True, slots=True)
class SolidificationResult:
    """Validated path with successful and failed attempts retained in order."""

    request: SolidificationRequest
    ledger: RawSolidificationLedger

    def __post_init__(self) -> None:
        try:
            request = _reconstruct_solidification_request(self.request)
            ledger = _reconstruct_solidification_ledger(self.ledger)
            _validate_solidification_result(request, ledger)
        except PathAdapterError:
            raise
        except Exception as error:
            raise PathAdapterError(
                "W2B_SOLIDIFICATION_RAW_RESULT_INVALID"
            ) from error
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "ledger", ledger)

    @property
    def status(self) -> str:
        failed = any(record.outcome == "FAIL" for record in self.ledger.records)
        if self.ledger.converged:
            return "COMPLETE_WITH_RETAINED_FAILURES" if failed else "COMPLETE"
        return "FAILED_WITH_RETAINED_LEDGER"

    @property
    def failed_steps(self) -> tuple[SolidificationStepRecord, ...]:
        return tuple(record for record in self.ledger.records if record.outcome == "FAIL")


def _copy_primitive_tuple(value: object, reason_code: str) -> tuple:
    """Copy an exact tuple without normalizing a mutable container spoof."""

    if type(value) is not tuple:
        _fail(reason_code)
    return tuple(item for item in value)


def _copy_primitive_pairs(value: object, reason_code: str) -> tuple[tuple, ...]:
    """Copy exact two-item tuple rows before their owning DTO revalidates them."""

    if type(value) is not tuple:
        _fail(reason_code)
    rows: list[tuple] = []
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            _fail(reason_code)
        rows.append((pair[0], pair[1]))
    return tuple(rows)


def _reconstruct_database(value: object) -> DatabaseIdentity:
    if type(value) is not DatabaseIdentity:
        _fail("W2B_DB_IDENTITY_INVALID")
    try:
        if (
            type(value.fe_baseline_decision) is not str
            or type(value.c15_exclusion_decision) is not str
        ):
            if type(value.family) is str and value.family == "fe":
                _fail("W2B_FE_POLICY_STATE_INVALID")
            _fail("W2B_DB_IDENTITY_INVALID")
        return DatabaseIdentity(
            family=value.family,
            database_id=value.database_id,
            database_sha256=value.database_sha256,
            profile_id=value.profile_id,
            profile_role=value.profile_role,
            fe_baseline_decision=value.fe_baseline_decision,
            c15_exclusion_decision=value.c15_exclusion_decision,
        )
    except PathAdapterError:
        raise
    except Exception as error:
        raise PathAdapterError("W2B_DB_IDENTITY_INVALID") from error


def _reconstruct_phase_selection(value: object) -> PhaseSelection:
    if type(value) is not PhaseSelection:
        _fail("W2B_PHASE_SELECTION_INVALID")
    try:
        return PhaseSelection(
            candidate_phases=_copy_primitive_tuple(
                value.candidate_phases,
                "W2B_PHASE_SELECTION_INVALID",
            ),
            requested_phases=_copy_primitive_tuple(
                value.requested_phases,
                "W2B_PHASE_SELECTION_INVALID",
            ),
            excluded_phases=_copy_primitive_tuple(
                value.excluded_phases,
                "W2B_PHASE_SELECTION_INVALID",
            ),
            effective_phases=_copy_primitive_tuple(
                value.effective_phases,
                "W2B_PHASE_SELECTION_INVALID",
            ),
        )
    except PathAdapterError:
        raise
    except Exception as error:
        raise PathAdapterError("W2B_PHASE_SELECTION_INVALID") from error


def _reconstruct_range(value: object) -> ClosedRange:
    if type(value) is not ClosedRange:
        _fail("W2B_RANGE_INVALID")
    try:
        return ClosedRange(value.lower, value.upper, value.seed_step)
    except PathAdapterError:
        raise
    except Exception as error:
        raise PathAdapterError("W2B_RANGE_INVALID") from error


def _reconstruct_mapping_request(value: object) -> MappingRequest:
    if type(value) not in (
        BinaryPhaseDiagramRequest,
        MulticomponentIsoplethRequest,
        TernaryPhaseDiagramRequest,
    ):
        _fail("W2B_REQUEST_INVALID")
    try:
        database = _reconstruct_database(value.database)
        phase_selection = _reconstruct_phase_selection(value.phase_selection)
        if type(value) is BinaryPhaseDiagramRequest:
            return BinaryPhaseDiagramRequest(
                database=database,
                left_component=value.left_component,
                right_component=value.right_component,
                phase_selection=phase_selection,
                pressure_pa=value.pressure_pa,
                right_fraction=_reconstruct_range(value.right_fraction),
                temperature_k=_reconstruct_range(value.temperature_k),
            )
        if type(value) is MulticomponentIsoplethRequest:
            return MulticomponentIsoplethRequest(
                database=database,
                balance_component=value.balance_component,
                variable_component=value.variable_component,
                fixed_composition=_copy_primitive_pairs(
                    value.fixed_composition,
                    "W2B_COMPOSITION_INVALID",
                ),
                phase_selection=phase_selection,
                pressure_pa=value.pressure_pa,
                variable_fraction=_reconstruct_range(value.variable_fraction),
                temperature_k=_reconstruct_range(value.temperature_k),
            )
        return TernaryPhaseDiagramRequest(
            database=database,
            dependent_component=value.dependent_component,
            x_component=value.x_component,
            y_component=value.y_component,
            phase_selection=phase_selection,
            pressure_pa=value.pressure_pa,
            temperature_k=value.temperature_k,
            starting_point_step=value.starting_point_step,
        )
    except PathAdapterError:
        raise
    except Exception as error:
        raise PathAdapterError("W2B_REQUEST_INVALID") from error


def _reconstruct_solidification_request(value: object) -> SolidificationRequest:
    if type(value) not in (
        EquilibriumSolidificationRequest,
        ScheilSolidificationRequest,
    ):
        _fail("W2B_REQUEST_INVALID")
    try:
        common = {
            "database": _reconstruct_database(value.database),
            "components": _copy_primitive_tuple(
                value.components,
                "W2B_COMPONENT_SET_INVALID",
            ),
            "phase_selection": _reconstruct_phase_selection(
                value.phase_selection,
            ),
            "composition": _copy_primitive_pairs(
                value.composition,
                "W2B_COMPOSITION_INVALID",
            ),
            "liquid_phase": value.liquid_phase,
            "pressure_pa": value.pressure_pa,
            "start_temperature_k": value.start_temperature_k,
            "step_temperature_k": value.step_temperature_k,
            "adaptive": value.adaptive,
            "pdens": value.pdens,
        }
        if type(value) is EquilibriumSolidificationRequest:
            return EquilibriumSolidificationRequest(
                **common,
                binary_search_tolerance_k=value.binary_search_tolerance_k,
            )
        return ScheilSolidificationRequest(
            **common,
            stop_liquid_fraction=value.stop_liquid_fraction,
        )
    except PathAdapterError:
        raise
    except Exception as error:
        raise PathAdapterError("W2B_REQUEST_INVALID") from error


def _reconstruct_mapping_node(
    value: object,
    fallback_reason: str = "W2B_LEDGER_INVALID",
) -> MappingNodeRecord:
    if type(value) is not MappingNodeRecord:
        _fail("W2B_LEDGER_INVALID")
    try:
        return MappingNodeRecord(
            ordinal=value.ordinal,
            node_id=value.node_id,
            kind=value.kind,
            outcome=value.outcome,
            coordinates=_copy_primitive_pairs(
                value.coordinates,
                "W2B_NODE_COORDINATES_INVALID",
            ),
            phases=_copy_primitive_tuple(
                value.phases,
                "W2B_NODE_PHASES_INVALID",
            ),
            reason_code=value.reason_code,
        )
    except PathAdapterError:
        raise
    except Exception as error:
        raise PathAdapterError(fallback_reason) from error


def _reconstruct_mapping_segment(
    value: object,
    fallback_reason: str = "W2B_LEDGER_INVALID",
) -> MappingSegmentRecord:
    if type(value) is not MappingSegmentRecord:
        _fail("W2B_LEDGER_INVALID")
    try:
        return MappingSegmentRecord(
            ordinal=value.ordinal,
            kind=value.kind,
            start_node_id=value.start_node_id,
            end_node_id=value.end_node_id,
            phases=_copy_primitive_tuple(
                value.phases,
                "W2B_PHASE_SET_INVALID",
            ),
        )
    except PathAdapterError:
        raise
    except Exception as error:
        raise PathAdapterError(fallback_reason) from error


def _reconstruct_solidification_step(
    value: object,
    fallback_reason: str = "W2B_LEDGER_INVALID",
) -> SolidificationStepRecord:
    if type(value) is not SolidificationStepRecord:
        _fail("W2B_LEDGER_INVALID")
    try:
        return SolidificationStepRecord(
            ordinal=value.ordinal,
            outcome=value.outcome,
            temperature_k=value.temperature_k,
            solid_fraction=value.solid_fraction,
            liquid_fraction=value.liquid_fraction,
            phase_fractions=_copy_primitive_pairs(
                value.phase_fractions,
                "W2B_SOLID_STEP_INVALID",
            ),
            liquid_composition=_copy_primitive_pairs(
                value.liquid_composition,
                "W2B_SOLID_STEP_INVALID",
            ),
            reason_code=value.reason_code,
        )
    except PathAdapterError:
        raise
    except Exception as error:
        raise PathAdapterError(fallback_reason) from error


def _reconstruct_mapping_ledger(value: object) -> RawMappingLedger:
    if type(value) is not RawMappingLedger:
        _fail("W2B_MAPPING_RAW_RESULT_INVALID")
    try:
        if type(value.nodes) is not tuple or type(value.segments) is not tuple:
            _fail("W2B_LEDGER_INVALID")
        if type(value.feature) is not str:
            _fail("W2B_FEATURE_MISMATCH")
        if type(value.strategy) is not str:
            _fail("W2B_STRATEGY_MISMATCH")
        if type(value.completed) is not bool:
            _fail("W2B_BOOL_INVALID")
        if type(value.termination_reason_code) is not str:
            _fail("W2B_TERMINATION_INVALID")
        nodes: list[MappingNodeRecord] = []
        for node in value.nodes:
            nodes.append(
                _reconstruct_mapping_node(
                    node,
                    "W2B_MAPPING_RAW_RESULT_INVALID",
                )
            )
        segments: list[MappingSegmentRecord] = []
        for segment in value.segments:
            segments.append(
                _reconstruct_mapping_segment(
                    segment,
                    "W2B_MAPPING_RAW_RESULT_INVALID",
                )
            )
        return RawMappingLedger(
            database=_reconstruct_database(value.database),
            feature=value.feature,
            strategy=value.strategy,
            nodes=tuple(nodes),
            segments=tuple(segments),
            completed=value.completed,
            termination_reason_code=value.termination_reason_code,
        )
    except PathAdapterError:
        raise
    except Exception as error:
        raise PathAdapterError("W2B_MAPPING_RAW_RESULT_INVALID") from error


def _reconstruct_solidification_ledger(
    value: object,
) -> RawSolidificationLedger:
    if type(value) is not RawSolidificationLedger:
        _fail("W2B_SOLIDIFICATION_RAW_RESULT_INVALID")
    try:
        if type(value.records) is not tuple:
            _fail("W2B_LEDGER_INVALID")
        if type(value.feature) is not str:
            _fail("W2B_FEATURE_MISMATCH")
        if type(value.method) is not str:
            _fail("W2B_STRATEGY_MISMATCH")
        if type(value.converged) is not bool:
            _fail("W2B_BOOL_INVALID")
        if type(value.termination_reason_code) is not str:
            _fail("W2B_TERMINATION_INVALID")
        records: list[SolidificationStepRecord] = []
        for record in value.records:
            records.append(
                _reconstruct_solidification_step(
                    record,
                    "W2B_SOLIDIFICATION_RAW_RESULT_INVALID",
                )
            )
        return RawSolidificationLedger(
            database=_reconstruct_database(value.database),
            feature=value.feature,
            method=value.method,
            records=tuple(records),
            converged=value.converged,
            termination_reason_code=value.termination_reason_code,
        )
    except PathAdapterError:
        raise
    except Exception as error:
        raise PathAdapterError("W2B_SOLIDIFICATION_RAW_RESULT_INVALID") from error


def _restore_exact_class(
    target: object,
    expected_type: type,
) -> None:
    if type(target) is expected_type:
        return
    try:
        object.__setattr__(target, "__class__", expected_type)
    except Exception as error:
        raise PathAdapterError("W2B_REQUEST_INVALID") from error
    if type(target) is not expected_type:
        _fail("W2B_REQUEST_INVALID")


def _restore_database_identity(
    target: object,
    pristine: DatabaseIdentity,
) -> None:
    _restore_exact_class(target, DatabaseIdentity)
    if type(target) is not DatabaseIdentity:
        _fail("W2B_REQUEST_INVALID")
    for field_name in (
        "family",
        "database_id",
        "database_sha256",
        "profile_id",
        "profile_role",
        "fe_baseline_decision",
        "c15_exclusion_decision",
    ):
        object.__setattr__(target, field_name, getattr(pristine, field_name))


def _restore_phase_selection(
    target: object,
    pristine: PhaseSelection,
) -> None:
    _restore_exact_class(target, PhaseSelection)
    if type(target) is not PhaseSelection:
        _fail("W2B_REQUEST_INVALID")
    for field_name in (
        "candidate_phases",
        "requested_phases",
        "excluded_phases",
        "effective_phases",
    ):
        object.__setattr__(target, field_name, getattr(pristine, field_name))


def _restore_closed_range(target: object, pristine: ClosedRange) -> None:
    _restore_exact_class(target, ClosedRange)
    if type(target) is not ClosedRange:
        _fail("W2B_REQUEST_INVALID")
    object.__setattr__(target, "lower", pristine.lower)
    object.__setattr__(target, "upper", pristine.upper)
    object.__setattr__(target, "seed_step", pristine.seed_step)


def _capture_mapping_caller_anchors(value: MappingRequest) -> tuple[object, ...]:
    try:
        if type(value) is BinaryPhaseDiagramRequest:
            return (
                value.database,
                value.phase_selection,
                value.right_fraction,
                value.temperature_k,
            )
        if type(value) is MulticomponentIsoplethRequest:
            return (
                value.database,
                value.phase_selection,
                value.variable_fraction,
                value.temperature_k,
            )
        if type(value) is TernaryPhaseDiagramRequest:
            return (value.database, value.phase_selection)
    except AttributeError as error:
        raise PathAdapterError("W2B_REQUEST_INVALID") from error
    _fail("W2B_REQUEST_INVALID")


def _capture_solidification_caller_anchors(
    value: SolidificationRequest,
) -> tuple[object, object]:
    try:
        return (value.database, value.phase_selection)
    except AttributeError as error:
        raise PathAdapterError("W2B_REQUEST_INVALID") from error


def _restore_mapping_caller(
    caller_request: object,
    pristine_request: MappingRequest,
    anchors: tuple[object, ...],
) -> None:
    try:
        _restore_exact_class(caller_request, type(pristine_request))
        if type(caller_request) is BinaryPhaseDiagramRequest and type(
            pristine_request
        ) is BinaryPhaseDiagramRequest:
            if len(anchors) != 4:
                _fail("W2B_REQUEST_INVALID")
            database, selection, right_fraction, temperature = anchors
            _restore_database_identity(database, pristine_request.database)
            _restore_phase_selection(selection, pristine_request.phase_selection)
            _restore_closed_range(right_fraction, pristine_request.right_fraction)
            _restore_closed_range(temperature, pristine_request.temperature_k)
            object.__setattr__(caller_request, "database", database)
            object.__setattr__(
                caller_request,
                "left_component",
                pristine_request.left_component,
            )
            object.__setattr__(
                caller_request,
                "right_component",
                pristine_request.right_component,
            )
            object.__setattr__(caller_request, "phase_selection", selection)
            object.__setattr__(
                caller_request,
                "pressure_pa",
                pristine_request.pressure_pa,
            )
            object.__setattr__(caller_request, "right_fraction", right_fraction)
            object.__setattr__(caller_request, "temperature_k", temperature)
            return
        if type(caller_request) is MulticomponentIsoplethRequest and type(
            pristine_request
        ) is MulticomponentIsoplethRequest:
            if len(anchors) != 4:
                _fail("W2B_REQUEST_INVALID")
            database, selection, variable_fraction, temperature = anchors
            _restore_database_identity(database, pristine_request.database)
            _restore_phase_selection(selection, pristine_request.phase_selection)
            _restore_closed_range(
                variable_fraction,
                pristine_request.variable_fraction,
            )
            _restore_closed_range(temperature, pristine_request.temperature_k)
            object.__setattr__(caller_request, "database", database)
            object.__setattr__(
                caller_request,
                "balance_component",
                pristine_request.balance_component,
            )
            object.__setattr__(
                caller_request,
                "variable_component",
                pristine_request.variable_component,
            )
            object.__setattr__(
                caller_request,
                "fixed_composition",
                pristine_request.fixed_composition,
            )
            object.__setattr__(caller_request, "phase_selection", selection)
            object.__setattr__(
                caller_request,
                "pressure_pa",
                pristine_request.pressure_pa,
            )
            object.__setattr__(
                caller_request,
                "variable_fraction",
                variable_fraction,
            )
            object.__setattr__(caller_request, "temperature_k", temperature)
            return
        if type(caller_request) is TernaryPhaseDiagramRequest and type(
            pristine_request
        ) is TernaryPhaseDiagramRequest:
            if len(anchors) != 2:
                _fail("W2B_REQUEST_INVALID")
            database, selection = anchors
            _restore_database_identity(database, pristine_request.database)
            _restore_phase_selection(selection, pristine_request.phase_selection)
            object.__setattr__(caller_request, "database", database)
            object.__setattr__(
                caller_request,
                "dependent_component",
                pristine_request.dependent_component,
            )
            object.__setattr__(
                caller_request,
                "x_component",
                pristine_request.x_component,
            )
            object.__setattr__(
                caller_request,
                "y_component",
                pristine_request.y_component,
            )
            object.__setattr__(caller_request, "phase_selection", selection)
            object.__setattr__(
                caller_request,
                "pressure_pa",
                pristine_request.pressure_pa,
            )
            object.__setattr__(
                caller_request,
                "temperature_k",
                pristine_request.temperature_k,
            )
            object.__setattr__(
                caller_request,
                "starting_point_step",
                pristine_request.starting_point_step,
            )
            return
        _fail("W2B_REQUEST_INVALID")
    except PathAdapterError:
        raise
    except Exception as error:
        raise PathAdapterError("W2B_REQUEST_INVALID") from error


def _restore_solidification_caller(
    caller_request: object,
    pristine_request: SolidificationRequest,
    anchors: tuple[object, object],
) -> None:
    try:
        _restore_exact_class(caller_request, type(pristine_request))
        if type(caller_request) is not type(pristine_request) or type(
            caller_request
        ) not in (
            EquilibriumSolidificationRequest,
            ScheilSolidificationRequest,
        ):
            _fail("W2B_REQUEST_INVALID")
        database, selection = anchors
        _restore_database_identity(database, pristine_request.database)
        _restore_phase_selection(selection, pristine_request.phase_selection)
        for field_name, value in (
            ("database", database),
            ("components", pristine_request.components),
            ("phase_selection", selection),
            ("composition", pristine_request.composition),
            ("liquid_phase", pristine_request.liquid_phase),
            ("pressure_pa", pristine_request.pressure_pa),
            ("start_temperature_k", pristine_request.start_temperature_k),
            ("step_temperature_k", pristine_request.step_temperature_k),
            ("adaptive", pristine_request.adaptive),
            ("pdens", pristine_request.pdens),
        ):
            object.__setattr__(caller_request, field_name, value)
        if type(pristine_request) is EquilibriumSolidificationRequest:
            object.__setattr__(
                caller_request,
                "binary_search_tolerance_k",
                pristine_request.binary_search_tolerance_k,
            )
        else:
            object.__setattr__(
                caller_request,
                "stop_liquid_fraction",
                pristine_request.stop_liquid_fraction,
            )
    except PathAdapterError:
        raise
    except Exception as error:
        raise PathAdapterError("W2B_REQUEST_INVALID") from error


def _mapping_integrity_error(
    value: object,
    pristine_request: MappingRequest,
) -> PathAdapterError | None:
    try:
        if _reconstruct_mapping_request(value) != pristine_request:
            return PathAdapterError("W2B_REQUEST_INVALID")
    except PathAdapterError as error:
        return error
    except Exception:
        return PathAdapterError("W2B_REQUEST_INVALID")
    return None


def _solidification_integrity_error(
    value: object,
    pristine_request: SolidificationRequest,
) -> PathAdapterError | None:
    try:
        if _reconstruct_solidification_request(value) != pristine_request:
            return PathAdapterError("W2B_REQUEST_INVALID")
    except PathAdapterError as error:
        return error
    except Exception:
        return PathAdapterError("W2B_REQUEST_INVALID")
    return None


def _assert_mapping_requests_pristine(
    caller_request: object,
    backend_request: object,
    pristine_request: MappingRequest,
    caller_anchors: tuple[object, ...],
) -> None:
    integrity_error = _mapping_integrity_error(
        caller_request,
        pristine_request,
    )
    if integrity_error is None:
        integrity_error = _mapping_integrity_error(
            backend_request,
            pristine_request,
        )
    _restore_mapping_caller(
        caller_request,
        pristine_request,
        caller_anchors,
    )
    restored_error = _mapping_integrity_error(
        caller_request,
        pristine_request,
    )
    if restored_error is not None:
        raise PathAdapterError("W2B_REQUEST_INVALID") from restored_error
    if integrity_error is not None:
        raise integrity_error


def _assert_solidification_requests_pristine(
    caller_request: object,
    backend_request: object,
    pristine_request: SolidificationRequest,
    caller_anchors: tuple[object, object],
) -> None:
    integrity_error = _solidification_integrity_error(
        caller_request,
        pristine_request,
    )
    if integrity_error is None:
        integrity_error = _solidification_integrity_error(
            backend_request,
            pristine_request,
        )
    _restore_solidification_caller(
        caller_request,
        pristine_request,
        caller_anchors,
    )
    restored_error = _solidification_integrity_error(
        caller_request,
        pristine_request,
    )
    if restored_error is not None:
        raise PathAdapterError("W2B_REQUEST_INVALID") from restored_error
    if integrity_error is not None:
        raise integrity_error


class MappingBackend(_Protocol):
    """Structural protocol for a Binary/Isopleth/Ternary mapping adapter."""

    def map(self, request: MappingRequest) -> RawMappingLedger:
        """Return raw strategy topology and every attempted internal node."""


class SolidificationBackend(_Protocol):
    """Structural protocol for equilibrium or Scheil path integrations."""

    def simulate(self, request: SolidificationRequest) -> RawSolidificationLedger:
        """Return the complete attempted trajectory, including failures."""


def run_mapping(request: object, backend: object) -> MappingResult:
    """Execute one specialized mapping strategy through an injected backend."""

    pristine_request = _reconstruct_mapping_request(request)
    caller_anchors = _capture_mapping_caller_anchors(request)
    backend_request = _reconstruct_mapping_request(pristine_request)
    try:
        map_method = getattr(backend, "map", None)
    except Exception as error:
        try:
            _assert_mapping_requests_pristine(
                request,
                backend_request,
                pristine_request,
                caller_anchors,
            )
        except Exception as integrity_error:
            raise PathAdapterError("W2B_MAPPING_BACKEND_RAISED") from integrity_error
        raise PathAdapterError("W2B_MAPPING_BACKEND_RAISED") from error
    if not callable(map_method):
        _assert_mapping_requests_pristine(
            request,
            backend_request,
            pristine_request,
            caller_anchors,
        )
        _fail("W2B_MAPPING_BACKEND_INVALID")
    try:
        raw = map_method(backend_request)
    except Exception as error:
        try:
            _assert_mapping_requests_pristine(
                request,
                backend_request,
                pristine_request,
                caller_anchors,
            )
        except Exception as integrity_error:
            raise PathAdapterError("W2B_MAPPING_BACKEND_RAISED") from integrity_error
        raise PathAdapterError("W2B_MAPPING_BACKEND_RAISED") from error
    _assert_mapping_requests_pristine(
        request,
        backend_request,
        pristine_request,
        caller_anchors,
    )
    ledger = _reconstruct_mapping_ledger(raw)
    result = MappingResult(request=pristine_request, ledger=ledger)
    _assert_mapping_requests_pristine(
        request,
        backend_request,
        pristine_request,
        caller_anchors,
    )
    return result


def run_solidification(request: object, backend: object) -> SolidificationResult:
    """Execute one method-specific cooling trajectory through an injected backend."""

    pristine_request = _reconstruct_solidification_request(request)
    caller_anchors = _capture_solidification_caller_anchors(request)
    backend_request = _reconstruct_solidification_request(pristine_request)
    try:
        simulate = getattr(backend, "simulate", None)
    except Exception as error:
        try:
            _assert_solidification_requests_pristine(
                request,
                backend_request,
                pristine_request,
                caller_anchors,
            )
        except Exception as integrity_error:
            raise PathAdapterError(
                "W2B_SOLIDIFICATION_BACKEND_RAISED"
            ) from integrity_error
        raise PathAdapterError("W2B_SOLIDIFICATION_BACKEND_RAISED") from error
    if not callable(simulate):
        _assert_solidification_requests_pristine(
            request,
            backend_request,
            pristine_request,
            caller_anchors,
        )
        _fail("W2B_SOLIDIFICATION_BACKEND_INVALID")
    try:
        raw = simulate(backend_request)
    except Exception as error:
        try:
            _assert_solidification_requests_pristine(
                request,
                backend_request,
                pristine_request,
                caller_anchors,
            )
        except Exception as integrity_error:
            raise PathAdapterError(
                "W2B_SOLIDIFICATION_BACKEND_RAISED"
            ) from integrity_error
        raise PathAdapterError("W2B_SOLIDIFICATION_BACKEND_RAISED") from error
    _assert_solidification_requests_pristine(
        request,
        backend_request,
        pristine_request,
        caller_anchors,
    )
    ledger = _reconstruct_solidification_ledger(raw)
    result = SolidificationResult(request=pristine_request, ledger=ledger)
    _assert_solidification_requests_pristine(
        request,
        backend_request,
        pristine_request,
        caller_anchors,
    )
    return result


def run_equilibrium_solidification(
    request: object,
    backend: object,
) -> SolidificationResult:
    """Typed entry point for the equilibrium cooling-path feature."""

    if type(request) is not EquilibriumSolidificationRequest:
        _fail("W2B_REQUEST_INVALID")
    return run_solidification(request, backend)


def run_scheil_solidification(
    request: object,
    backend: object,
) -> SolidificationResult:
    """Typed entry point for the Scheil-Gulliver cooling-path feature."""

    if type(request) is not ScheilSolidificationRequest:
        _fail("W2B_REQUEST_INVALID")
    return run_solidification(request, backend)


__all__ = (
    "SUPPORTED_PATH_FEATURES",
    "SUPPORTED_DATABASE_FAMILIES",
    "SUPPORTED_FE_PROFILE_IDS",
    "SOLIDIFICATION_PRESSURE_PA",
    "FE_POLICY_UNDECIDED",
    "POLICY_NOT_APPLICABLE",
    "PROFILE_ROLES",
    "WAVE2B_PATH_REASON_CODES",
    "PathAdapterError",
    "DatabaseIdentity",
    "PhaseSelection",
    "ClosedRange",
    "BinaryPhaseDiagramRequest",
    "MulticomponentIsoplethRequest",
    "TernaryPhaseDiagramRequest",
    "MappingNodeRecord",
    "MappingSegmentRecord",
    "RawMappingLedger",
    "MappingResult",
    "EquilibriumSolidificationRequest",
    "ScheilSolidificationRequest",
    "SolidificationStepRecord",
    "RawSolidificationLedger",
    "SolidificationResult",
    "MappingBackend",
    "SolidificationBackend",
    "run_mapping",
    "run_solidification",
    "run_equilibrium_solidification",
    "run_scheil_solidification",
)
