"""Import-safe Wave 2B adapters for direct thermodynamic feature nodes.

The module is a product-integration candidate, not qualification evidence.  It
does not import Streamlit, pycalphad, NumPy, pandas, files, or a database.  A
caller supplies an exact opaque database/profile identity and an injected
backend.  Backend replies are bound to that identity, feature, and node before
the frozen numerical/equilibrium foundation is allowed to consume them.

Steel is an explicit member of the supported product families.  This module
does not select a preferred Fe profile and does not silently exclude any Fe
phase; those choices remain explicit request inputs.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass, field as _field
import math as _math
from types import MappingProxyType as _MappingProxyType
from typing import Mapping as _Mapping, Protocol as _Protocol

from thermogar_equilibrium_core import (
    EquilibriumRawResult,
    EquilibriumRequest,
    EquilibriumResult,
    PhaseAggregate,
    RawPhaseState,
    evaluate_equilibrium,
)
from thermogar_numerical_grid import (
    GridNode,
    NumericalAdapterError,
    build_axis,
    build_cartesian_nodes,
)


DIRECT_FEATURE_IDS = (
    "equilibrium_single",
    "equilibrium_temperature_scan",
    "equilibrium_composition_scan",
    "ternary_phase_fraction_map",
    "manual_phase_selection_metastable",
    "phase_gibbs_energy",
    "phase_driving_force",
    "tzero_temperature",
)
SUPPORTED_DATABASE_FAMILIES = ("ni", "al", "fe")
FE_PROFILE_IDS = ("thermogar_patch", "upstream_original")
STEEL_REQUIRED_PRODUCT_SCOPE = True
FE_BASELINE_PROFILE = None
FE_EXCLUSION_DECISION_MADE = False
COUNTS_TOWARD_FEATURE_COVERAGE = False
ACCEPTANCE_CLAIM = False
PRODUCTION_USE = "DENIED"

_REASONS = {
    "DIRECT_NODE_OK": "The requested direct feature node completed successfully.",
    "DIRECT_DATABASE_FAMILY_INVALID": "The database family must be exactly ni, al, or fe.",
    "DIRECT_DATABASE_PROFILE_INVALID": "The database profile identifier is not canonical.",
    "DIRECT_DATABASE_SHA256_INVALID": "The database identity requires an exact lowercase SHA-256.",
    "DIRECT_FEATURE_INVALID": "The direct feature identifier is outside this adapter group.",
    "DIRECT_REQUEST_INVALID": "The direct feature request is structurally invalid.",
    "DIRECT_REQUEST_MUTATED": "The caller request changed after its canonical execution snapshot was taken.",
    "DIRECT_NODE_KEY_INVALID": "A direct node key or label is invalid.",
    "DIRECT_NODE_LIMIT_INVALID": "The node ceiling must be a bounded positive integer.",
    "DIRECT_NODE_LIMIT_EXCEEDED": "The requested direct feature exceeds its node ceiling.",
    "DIRECT_PHASES_INVALID": "A phase collection must be a non-empty immutable tuple.",
    "DIRECT_PHASE_INVALID": "A phase name must be canonical.",
    "DIRECT_PHASE_DUPLICATE": "A phase collection contains a duplicate.",
    "DIRECT_PHASE_EXCLUSION_OVERLAP": "A requested phase is also explicitly excluded.",
    "DIRECT_PHASE_SELECTION_INCOMPLETE": "Selected and excluded phases must exactly partition the available phases.",
    "DIRECT_PHASE_SELECTION_MISMATCH": "The downstream equilibrium request does not use the exact selected phase tuple.",
    "DIRECT_PHASE_BINDING_INVALID": "A phase universe, effective set, and explicit exclusions must form one canonical exact partition.",
    "DIRECT_TARGET_PHASE_INVALID": "The target phase is absent from the requested phase set.",
    "DIRECT_TARGET_PHASE_OVERLAP": "A dormant target phase must not be part of the reference equilibrium.",
    "DIRECT_TARGET_PHASE_NOT_EXCLUDED": "A dormant target phase must be an explicit reference-equilibrium exclusion.",
    "DIRECT_COMPONENT_INVALID": "A component selector is invalid for the requested state.",
    "DIRECT_COMPOSITION_PATH_INVALID": "A composition path cannot preserve a non-negative balance simplex.",
    "DIRECT_TERNARY_COMPONENTS_INVALID": "A ternary map requires exactly three user components and optional VA.",
    "DIRECT_TERNARY_INTERVAL_INVALID": "A ternary interval count must be an integer of at least two.",
    "DIRECT_TEMPERATURE_NONPOSITIVE": "Every requested temperature must be strictly positive kelvin.",
    "DIRECT_TZERO_PHASES_IDENTICAL": "T-zero requires two different phases.",
    "DIRECT_TZERO_BOUNDS_INVALID": "T-zero search bounds must be finite, positive, and increasing.",
    "DIRECT_TZERO_OUT_OF_BOUNDS": "A backend T-zero result is outside the requested search bounds.",
    "DIRECT_BACKEND_INVALID": "The injected backend does not expose the required callable operation.",
    "DIRECT_BACKEND_REQUEST_MUTATED": "The backend changed its isolated request object during the call.",
    "DIRECT_BACKEND_REPLY_INVALID": "A backend reply does not satisfy the direct adapter schema.",
    "DIRECT_BACKEND_IDENTITY_MISMATCH": "A backend reply is bound to a different database/profile identity.",
    "DIRECT_BACKEND_FEATURE_MISMATCH": "A backend reply is bound to a different feature.",
    "DIRECT_BACKEND_NODE_MISMATCH": "A backend reply is bound to a different requested node.",
    "DIRECT_BACKEND_PHASE_BINDING_MISMATCH": "A backend reply is bound to a different phase universe or effective/excluded partition.",
    "DIRECT_SCALAR_INVALID": "A scalar backend value must be binary64-compatible and not bool.",
    "DIRECT_SCALAR_NONFINITE": "A scalar backend value must be finite.",
    "DIRECT_SCALAR_OVERFLOW": "A scalar backend value is outside binary64 range.",
    "DIRECT_BACKEND_NO_SOLUTION": "The backend reported no solution at this requested node.",
    "DIRECT_BACKEND_CONVERGENCE_FAILED": "The backend reported an expected convergence failure at this node.",
    "DIRECT_BACKEND_DOMAIN_REJECTED": "The backend explicitly rejected this node as outside its domain.",
    "DIRECT_BACKEND_PROPERTY_UNDEFINED": "The requested scalar property is undefined at this node.",
    "DIRECT_BACKEND_TZERO_NOT_FOUND": "The backend did not find T-zero inside the requested bounds.",
    "DIRECT_RESULT_INVALID": "A direct feature result violates its retained-ledger invariants.",
}
DIRECT_ADAPTER_REASON_CODES: _Mapping[str, str] = _MappingProxyType(_REASONS)
del _REASONS

_EXPECTED_NODE_REASONS = frozenset(
    {
        "DIRECT_BACKEND_NO_SOLUTION",
        "DIRECT_BACKEND_CONVERGENCE_FAILED",
        "DIRECT_BACKEND_DOMAIN_REJECTED",
        "DIRECT_BACKEND_PROPERTY_UNDEFINED",
        "DIRECT_BACKEND_TZERO_NOT_FOUND",
    }
)
_EQUILIBRIUM_NODE_REASONS = frozenset(
    {
        "DIRECT_BACKEND_NO_SOLUTION",
        "DIRECT_BACKEND_CONVERGENCE_FAILED",
        "DIRECT_BACKEND_DOMAIN_REJECTED",
    }
)
_PROPERTY_NODE_REASONS = frozenset(
    set(_EQUILIBRIUM_NODE_REASONS) | {"DIRECT_BACKEND_PROPERTY_UNDEFINED"}
)
_TZERO_NODE_REASONS = frozenset(
    set(_EQUILIBRIUM_NODE_REASONS) | {"DIRECT_BACKEND_TZERO_NOT_FOUND"}
)
_NAME_CHARACTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_#:+-.")
_PROFILE_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789_.-")
_HEX_CHARACTERS = frozenset("0123456789abcdef")
_ABSOLUTE_MAX_NODES = 1_000_000
_SIMPLEX_EDGE_ULP = _math.ulp(1.0)
_EQUILIBRIUM_OUTPUT_FEATURES = frozenset(
    {
        "equilibrium_single",
        "equilibrium_temperature_scan",
        "equilibrium_composition_scan",
        "ternary_phase_fraction_map",
        "manual_phase_selection_metastable",
    }
)
_SCALAR_OUTPUT_NAMES: _Mapping[str, str] = _MappingProxyType(
    {
        "phase_gibbs_energy": "GIBBS_ENERGY_J_PER_MOL",
        "phase_driving_force": "DRIVING_FORCE_J_PER_MOL",
        "tzero_temperature": "TZERO_TEMPERATURE_K",
    }
)


class DirectAdapterError(ValueError):
    """Fail-closed direct-adapter error with a stable reason code."""

    __slots__ = ("reason_code",)

    def __init__(self, reason_code: str) -> None:
        if type(reason_code) is not str or reason_code not in DIRECT_ADAPTER_REASON_CODES:
            raise RuntimeError("Unknown direct-adapter reason code")
        self.reason_code = reason_code
        super().__init__(reason_code)


class ExpectedDirectNodeFailure(DirectAdapterError):
    """Explicit backend signal retained as one failed requested node."""

    __slots__ = ()

    def __init__(self, reason_code: str) -> None:
        if type(reason_code) is not str or reason_code not in _EXPECTED_NODE_REASONS:
            raise RuntimeError("Reason code is not an expected direct-node failure")
        super().__init__(reason_code)


def _fail(reason_code: str) -> None:
    raise DirectAdapterError(reason_code)


def _canonical_name(value: object, reason_code: str) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 64
        or any(character not in _NAME_CHARACTERS for character in value)
    ):
        _fail(reason_code)
    return value


def _canonical_output_name(value: object) -> str:
    # A valid 64-character phase name can be prefixed by PHASE_FRACTION:.
    if (
        type(value) is not str
        or not value
        or len(value) > 128
        or any(character not in _NAME_CHARACTERS for character in value)
    ):
        _fail("DIRECT_RESULT_INVALID")
    return value


def _binary64(value: object) -> float:
    if type(value) not in (int, float):
        _fail("DIRECT_SCALAR_INVALID")
    try:
        number = float(value)
    except OverflowError as error:
        raise DirectAdapterError("DIRECT_SCALAR_OVERFLOW") from error
    if not _math.isfinite(number):
        _fail("DIRECT_SCALAR_NONFINITE")
    return 0.0 if number == 0.0 else number


def _validated_feature(value: object) -> str:
    if type(value) is not str or value not in DIRECT_FEATURE_IDS:
        _fail("DIRECT_FEATURE_INVALID")
    return value


def _allowed_failure_reasons(feature_id: str) -> frozenset[str]:
    if feature_id == "tzero_temperature":
        return _TZERO_NODE_REASONS
    if feature_id in ("phase_gibbs_energy", "phase_driving_force"):
        return _PROPERTY_NODE_REASONS
    return _EQUILIBRIUM_NODE_REASONS


def _validated_phases(value: object) -> tuple[str, ...]:
    if type(value) is not tuple or not value:
        _fail("DIRECT_PHASES_INVALID")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        phase = _canonical_name(item, "DIRECT_PHASE_INVALID")
        if phase in seen:
            _fail("DIRECT_PHASE_DUPLICATE")
        result.append(phase)
        seen.add(phase)
    return tuple(result)


def _validated_exclusions(value: object) -> tuple[str, ...]:
    if type(value) is not tuple:
        _fail("DIRECT_PHASES_INVALID")
    if not value:
        return tuple()
    return _validated_phases(value)


def _validate_phase_boundary(
    requested_phases: tuple[str, ...],
    explicit_exclusions: object,
) -> tuple[str, ...]:
    exclusions = _validated_exclusions(explicit_exclusions)
    if set(requested_phases) & set(exclusions):
        _fail("DIRECT_PHASE_EXCLUSION_OVERLAP")
    return exclusions


def _validated_max_nodes(value: object) -> int:
    if (
        type(value) is not int
        or value <= 0
        or value > _ABSOLUTE_MAX_NODES
    ):
        _fail("DIRECT_NODE_LIMIT_INVALID")
    return value


def _require_node_count(count: int, maximum: int) -> None:
    if count > maximum:
        _fail("DIRECT_NODE_LIMIT_EXCEEDED")


def _temperature_axis(values: object):
    try:
        axis = build_axis("TEMPERATURE_K", values)
    except NumericalAdapterError as error:
        raise DirectAdapterError("DIRECT_REQUEST_INVALID") from error
    if any(value <= 0.0 for value in axis.values):
        _fail("DIRECT_TEMPERATURE_NONPOSITIVE")
    return axis


def _composition_coordinate_name(component: object) -> str:
    canonical = _canonical_name(component, "DIRECT_COMPONENT_INVALID")
    coordinate = f"X_{canonical}"
    # GridNode/build_axis use the frozen foundation's 64-character name bound.
    if len(coordinate) > 64:
        _fail("DIRECT_COMPONENT_INVALID")
    return coordinate


def _composition_axis(component: str, values: object):
    coordinate = _composition_coordinate_name(component)
    try:
        axis = build_axis(coordinate, values)
    except NumericalAdapterError as error:
        raise DirectAdapterError("DIRECT_COMPOSITION_PATH_INVALID") from error
    if any(value > 1.0 for value in axis.values):
        _fail("DIRECT_COMPOSITION_PATH_INVALID")
    return axis


def _canonical_ternary_fraction(value: object) -> float:
    if type(value) is not float or not _math.isfinite(value):
        _fail("DIRECT_COMPOSITION_PATH_INVALID")
    if -_SIMPLEX_EDGE_ULP <= value <= _SIMPLEX_EDGE_ULP:
        return 0.0
    if 1.0 - _SIMPLEX_EDGE_ULP <= value <= 1.0 + _SIMPLEX_EDGE_ULP:
        return 1.0
    if value < 0.0 or value > 1.0:
        _fail("DIRECT_COMPOSITION_PATH_INVALID")
    return value


def _identity_fields_valid(value: object) -> bool:
    try:
        if type(value) is not DatabaseProfileIdentity:
            return False
        family = value.database_family
        profile = value.profile_id
        digest = value.runtime_sha256
        if (
            type(family) is not str
            or family not in SUPPORTED_DATABASE_FAMILIES
            or type(profile) is not str
            or not profile
            or len(profile) > 128
            or any(character not in _PROFILE_CHARACTERS for character in profile)
            or type(digest) is not str
            or len(digest) != 64
            or any(character not in _HEX_CHARACTERS for character in digest)
        ):
            return False
        return family != "fe" or profile in FE_PROFILE_IDS
    except AttributeError:
        return False


def _identity_fields_same(left: object, right: object) -> bool:
    if not _identity_fields_valid(left) or not _identity_fields_valid(right):
        return False
    return (
        left.database_family == right.database_family
        and left.profile_id == right.profile_id
        and left.runtime_sha256 == right.runtime_sha256
    )


def _grid_node_fields_valid(value: object) -> bool:
    try:
        if type(value) is not GridNode:
            return False
        if type(value.ordinal) is not int or value.ordinal < 0:
            return False
        coordinates = value.coordinates
        if type(coordinates) is not tuple or not coordinates:
            return False
        seen: set[str] = set()
        for pair in coordinates:
            if type(pair) is not tuple or len(pair) != 2:
                return False
            name, number = pair
            if (
                type(name) is not str
                or not name
                or len(name) > 64
                or any(character not in _NAME_CHARACTERS for character in name)
                or name in seen
                or type(number) is not float
                or not _math.isfinite(number)
                or number < 0.0
                or (number == 0.0 and _math.copysign(1.0, number) < 0.0)
            ):
                return False
            seen.add(name)
        return True
    except AttributeError:
        return False


def _grid_node_fields_same(left: object, right: object) -> bool:
    if not _grid_node_fields_valid(left) or not _grid_node_fields_valid(right):
        return False
    if left.ordinal != right.ordinal or len(left.coordinates) != len(right.coordinates):
        return False
    for left_pair, right_pair in zip(left.coordinates, right.coordinates):
        if left_pair[0] != right_pair[0] or left_pair[1] != right_pair[1]:
            return False
    return True


@_dataclass(frozen=True, slots=True)
class DatabaseProfileIdentity:
    """Opaque exact runtime identity; the adapter never opens this database."""

    database_family: str
    profile_id: str
    runtime_sha256: str

    def __post_init__(self) -> None:
        if type(self.database_family) is not str or self.database_family not in SUPPORTED_DATABASE_FAMILIES:
            _fail("DIRECT_DATABASE_FAMILY_INVALID")
        if (
            type(self.profile_id) is not str
            or not self.profile_id
            or len(self.profile_id) > 128
            or any(character not in _PROFILE_CHARACTERS for character in self.profile_id)
        ):
            _fail("DIRECT_DATABASE_PROFILE_INVALID")
        if self.database_family == "fe" and self.profile_id not in FE_PROFILE_IDS:
            _fail("DIRECT_DATABASE_PROFILE_INVALID")
        if (
            type(self.runtime_sha256) is not str
            or len(self.runtime_sha256) != 64
            or any(character not in _HEX_CHARACTERS for character in self.runtime_sha256)
        ):
            _fail("DIRECT_DATABASE_SHA256_INVALID")


@_dataclass(frozen=True, slots=True)
class DirectNodeKey:
    """Frozen numerical grid node plus optional exact categorical labels."""

    node: GridNode
    labels: tuple[tuple[str, str], ...] = tuple()

    def __post_init__(self) -> None:
        if not _grid_node_fields_valid(self.node) or type(self.labels) is not tuple:
            _fail("DIRECT_NODE_KEY_INVALID")
        normalized: list[tuple[str, str]] = []
        previous: str | None = None
        seen: set[str] = set()
        for pair in self.labels:
            if type(pair) is not tuple or len(pair) != 2:
                _fail("DIRECT_NODE_KEY_INVALID")
            name = _canonical_name(pair[0], "DIRECT_NODE_KEY_INVALID")
            value = _canonical_name(pair[1], "DIRECT_NODE_KEY_INVALID")
            if name in seen or (previous is not None and name < previous):
                _fail("DIRECT_NODE_KEY_INVALID")
            normalized.append((name, value))
            seen.add(name)
            previous = name
        object.__setattr__(self, "labels", tuple(normalized))


def _node_key_fields_valid(value: object) -> bool:
    try:
        if type(value) is not DirectNodeKey or not _grid_node_fields_valid(value.node):
            return False
        labels = value.labels
        if type(labels) is not tuple:
            return False
        previous: str | None = None
        seen: set[str] = set()
        for pair in labels:
            if type(pair) is not tuple or len(pair) != 2:
                return False
            name, label = pair
            if (
                type(name) is not str
                or not name
                or len(name) > 64
                or any(character not in _NAME_CHARACTERS for character in name)
                or type(label) is not str
                or not label
                or len(label) > 64
                or any(character not in _NAME_CHARACTERS for character in label)
                or name in seen
                or (previous is not None and name < previous)
            ):
                return False
            seen.add(name)
            previous = name
        return True
    except AttributeError:
        return False


def _node_key_fields_same(left: object, right: object) -> bool:
    if not _node_key_fields_valid(left) or not _node_key_fields_valid(right):
        return False
    if not _grid_node_fields_same(left.node, right.node) or len(left.labels) != len(right.labels):
        return False
    for left_pair, right_pair in zip(left.labels, right.labels):
        if left_pair[0] != right_pair[0] or left_pair[1] != right_pair[1]:
            return False
    return True


@_dataclass(frozen=True, slots=True)
class PhaseSetBinding:
    """Canonical full phase universe, effective set, and explicit complement."""

    phase_universe: tuple[str, ...]
    effective_phases: tuple[str, ...]
    explicit_exclusions: tuple[str, ...]

    def __post_init__(self) -> None:
        universe = _validated_phases(self.phase_universe)
        effective = _validated_phases(self.effective_phases)
        exclusions = _validated_exclusions(self.explicit_exclusions)
        effective_set = set(effective)
        exclusion_set = set(exclusions)
        if (
            effective_set & exclusion_set
            or effective_set | exclusion_set != set(universe)
            or len(effective) + len(exclusions) != len(universe)
            or effective != tuple(phase for phase in universe if phase in effective_set)
            or exclusions != tuple(phase for phase in universe if phase in exclusion_set)
        ):
            _fail("DIRECT_PHASE_BINDING_INVALID")
        object.__setattr__(self, "phase_universe", universe)
        object.__setattr__(self, "effective_phases", effective)
        object.__setattr__(self, "explicit_exclusions", exclusions)


def _phase_binding_fields_valid(value: object) -> bool:
    try:
        if type(value) is not PhaseSetBinding:
            return False
        rebuilt = PhaseSetBinding(
            value.phase_universe,
            value.effective_phases,
            value.explicit_exclusions,
        )
    except (AttributeError, DirectAdapterError):
        return False
    return (
        type(value.phase_universe) is tuple
        and type(value.effective_phases) is tuple
        and type(value.explicit_exclusions) is tuple
        and _string_tuple_fields_same(value.phase_universe, rebuilt.phase_universe)
        and _string_tuple_fields_same(value.effective_phases, rebuilt.effective_phases)
        and _string_tuple_fields_same(value.explicit_exclusions, rebuilt.explicit_exclusions)
    )


def _string_tuple_fields_same(left: object, right: object) -> bool:
    if type(left) is not tuple or type(right) is not tuple or len(left) != len(right):
        return False
    for left_value, right_value in zip(left, right):
        if type(left_value) is not str or type(right_value) is not str or left_value != right_value:
            return False
    return True


def _phase_binding_fields_same(left: object, right: object) -> bool:
    return (
        _phase_binding_fields_valid(left)
        and _phase_binding_fields_valid(right)
        and _string_tuple_fields_same(left.phase_universe, right.phase_universe)
        and _string_tuple_fields_same(left.effective_phases, right.effective_phases)
        and _string_tuple_fields_same(left.explicit_exclusions, right.explicit_exclusions)
    )


def _rebuild_identity(
    value: object,
    reason_code: str,
) -> DatabaseProfileIdentity:
    if not _identity_fields_valid(value):
        _fail(reason_code)
    return DatabaseProfileIdentity(
        value.database_family,
        value.profile_id,
        value.runtime_sha256,
    )


def _rebuild_grid_node(value: object, reason_code: str) -> GridNode:
    if not _grid_node_fields_valid(value):
        _fail(reason_code)
    return GridNode(
        value.ordinal,
        tuple((name, number) for name, number in value.coordinates),
    )


def _rebuild_node_key(value: object, reason_code: str) -> DirectNodeKey:
    if not _node_key_fields_valid(value):
        _fail(reason_code)
    return DirectNodeKey(
        _rebuild_grid_node(value.node, reason_code),
        tuple((name, label) for name, label in value.labels),
    )


def _rebuild_phase_binding(value: object, reason_code: str) -> PhaseSetBinding:
    if not _phase_binding_fields_valid(value):
        _fail(reason_code)
    return PhaseSetBinding(
        tuple(value.phase_universe),
        tuple(value.effective_phases),
        tuple(value.explicit_exclusions),
    )


def _phase_binding_from_effective(
    effective_phases: tuple[str, ...],
    explicit_exclusions: tuple[str, ...],
) -> PhaseSetBinding:
    return PhaseSetBinding(
        effective_phases + explicit_exclusions,
        effective_phases,
        explicit_exclusions,
    )


def _exact_canonical_float(value: object, reason_code: str) -> float:
    if (
        type(value) is not float
        or not _math.isfinite(value)
        or (value == 0.0 and _math.copysign(1.0, value) < 0.0)
    ):
        _fail(reason_code)
    return value


def _copy_exact_names(
    value: object,
    reason_code: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if type(value) is not tuple or (not allow_empty and not value):
        _fail(reason_code)
    result: list[str] = []
    for name in value:
        if type(name) is not str:
            _fail(reason_code)
        result.append(name)
    return tuple(result)


def _copy_named_float_rows(
    value: object,
    reason_code: str,
    *,
    allow_empty: bool,
) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple or (not allow_empty and not value):
        _fail(reason_code)
    result: list[tuple[str, float]] = []
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not str:
            _fail(reason_code)
        result.append((pair[0], _exact_canonical_float(pair[1], reason_code)))
    return tuple(result)


def _named_float_rows_valid(value: object, *, allow_empty: bool) -> bool:
    try:
        _copy_named_float_rows(
            value,
            "DIRECT_RESULT_INVALID",
            allow_empty=allow_empty,
        )
    except DirectAdapterError:
        return False
    return True


def _rebuild_equilibrium_request(
    value: object,
    reason_code: str,
) -> EquilibriumRequest:
    try:
        if type(value) is not EquilibriumRequest:
            _fail(reason_code)
        temperature = _exact_canonical_float(value.temperature_k, reason_code)
        pressure = _exact_canonical_float(value.pressure_pa, reason_code)
        components = _copy_exact_names(value.components, reason_code)
        phases = _copy_exact_names(value.phases, reason_code)
        composition = _copy_named_float_rows(
            value.composition,
            reason_code,
            allow_empty=False,
        )
        return EquilibriumRequest(
            temperature,
            pressure,
            components,
            phases,
            composition,
        )
    except (AttributeError, NumericalAdapterError) as error:
        raise DirectAdapterError(reason_code) from error


def _equilibrium_request_fields_valid(value: object) -> bool:
    try:
        _rebuild_equilibrium_request(value, "DIRECT_REQUEST_INVALID")
    except DirectAdapterError:
        return False
    return True


def _rebuild_raw_phase_state(
    value: object,
    reason_code: str,
) -> RawPhaseState:
    try:
        if type(value) is not RawPhaseState or type(value.phase) is not str:
            _fail(reason_code)
        phase_fraction = _exact_canonical_float(value.phase_fraction, reason_code)
        composition = _copy_named_float_rows(
            value.composition,
            reason_code,
            allow_empty=False,
        )
        return RawPhaseState(value.phase, phase_fraction, composition)
    except (AttributeError, NumericalAdapterError) as error:
        raise DirectAdapterError(reason_code) from error


def _raw_phase_state_fields_valid(value: object) -> bool:
    try:
        _rebuild_raw_phase_state(value, "DIRECT_BACKEND_REPLY_INVALID")
    except DirectAdapterError:
        return False
    return True


def _rebuild_raw_result(
    value: object,
    reason_code: str,
) -> EquilibriumRawResult:
    try:
        if type(value) is not EquilibriumRawResult or type(value.phase_states) is not tuple or not value.phase_states:
            _fail(reason_code)
        states = tuple(
            _rebuild_raw_phase_state(state, reason_code)
            for state in value.phase_states
        )
        return EquilibriumRawResult(states)
    except (AttributeError, NumericalAdapterError) as error:
        raise DirectAdapterError(reason_code) from error


def _raw_result_fields_valid(value: object) -> bool:
    try:
        _rebuild_raw_result(value, "DIRECT_BACKEND_REPLY_INVALID")
    except DirectAdapterError:
        return False
    return True


def _rebuild_phase_aggregate(
    value: object,
    reason_code: str,
) -> PhaseAggregate:
    try:
        if type(value) is not PhaseAggregate or type(value.phase) is not str:
            _fail(reason_code)
        phase_fraction = _exact_canonical_float(value.phase_fraction, reason_code)
        composition = _copy_named_float_rows(
            value.composition,
            reason_code,
            allow_empty=False,
        )
        return PhaseAggregate(value.phase, phase_fraction, composition)
    except (AttributeError, NumericalAdapterError) as error:
        raise DirectAdapterError(reason_code) from error


def _phase_aggregate_fields_valid(value: object) -> bool:
    try:
        _rebuild_phase_aggregate(value, "DIRECT_RESULT_INVALID")
    except DirectAdapterError:
        return False
    return True


def _rebuild_equilibrium_result(
    value: object,
    reason_code: str,
) -> EquilibriumResult:
    try:
        if type(value) is not EquilibriumResult or type(value.phases) is not tuple or not value.phases:
            _fail(reason_code)
        request = _rebuild_equilibrium_request(value.request, reason_code)
        phases = tuple(
            _rebuild_phase_aggregate(phase, reason_code)
            for phase in value.phases
        )
        return EquilibriumResult(request, phases)
    except (AttributeError, NumericalAdapterError) as error:
        raise DirectAdapterError(reason_code) from error


def _equilibrium_result_fields_valid(value: object) -> bool:
    try:
        _rebuild_equilibrium_result(value, "DIRECT_RESULT_INVALID")
    except DirectAdapterError:
        return False
    return True


def _copy_origin_snapshot(value: object) -> object:
    # Nested values are exact immutable primitives, so the validated tuple can
    # be shared without caller/backend alias risk.  Validate iteratively so a
    # hostile public constructor cannot turn excessive nesting into a raw
    # RecursionError.
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is tuple:
            pending.extend(item)
        elif type(item) not in (str, int, bool):
            _fail("DIRECT_RESULT_INVALID")
    return value


def _origin_snapshot_fields_same(left: object, right: object) -> bool:
    pending = [(left, right)]
    while pending:
        left_item, right_item = pending.pop()
        if type(left_item) is not type(right_item):
            return False
        if type(left_item) is tuple:
            if len(left_item) != len(right_item):
                return False
            pending.extend(zip(left_item, right_item))
        elif type(left_item) in (str, int, bool):
            if left_item != right_item:
                return False
        else:
            return False
    return True


class DirectRequestOrigin(tuple):
    """One validated, physically immutable full top-level request snapshot."""

    __slots__ = ()

    def __new__(cls, snapshot: object):
        if type(snapshot) is not tuple or not snapshot:
            _fail("DIRECT_RESULT_INVALID")
        _copy_origin_snapshot(snapshot)
        return tuple.__new__(cls, snapshot)

    @property
    def snapshot(self) -> tuple[object, ...]:
        # Convert the short outer tuple to an exact built-in tuple.  Nested
        # axes are immutable tuples and remain shared without mutable aliases.
        return tuple(self)


@_dataclass(frozen=True, slots=True)
class DirectNodeOrigin:
    """Deep binding to one full request and one exact backend node/state."""

    request_origin: DirectRequestOrigin
    backend_node_snapshot: tuple[object, ...]

    def __post_init__(self) -> None:
        if (
            type(self.request_origin) is not DirectRequestOrigin
            or type(self.request_origin.snapshot) is not tuple
            or not self.request_origin.snapshot
            or type(self.backend_node_snapshot) is not tuple
            or not self.backend_node_snapshot
        ):
            _fail("DIRECT_RESULT_INVALID")
        object.__setattr__(
            self,
            "backend_node_snapshot",
            _copy_origin_snapshot(self.backend_node_snapshot),
        )

    @property
    def request_snapshot(self) -> tuple[object, ...]:
        return self.request_origin.snapshot


def _origin_fields_valid(value: object) -> bool:
    try:
        if type(value) is not DirectNodeOrigin:
            return False
        return (
            type(value.request_origin) is DirectRequestOrigin
            and type(value.request_origin.snapshot) is tuple
            and bool(value.request_origin.snapshot)
            and type(value.backend_node_snapshot) is tuple
            and bool(value.backend_node_snapshot)
            and _copy_origin_snapshot(value.backend_node_snapshot)
            is value.backend_node_snapshot
        )
    except (AttributeError, DirectAdapterError):
        return False


def _origin_fields_same(left: object, right: object) -> bool:
    return (
        _origin_fields_valid(left)
        and _origin_fields_valid(right)
        and (
            left.request_origin is right.request_origin
            or _origin_snapshot_fields_same(
                left.request_snapshot,
                right.request_snapshot,
            )
        )
        and _origin_snapshot_fields_same(
            left.backend_node_snapshot,
            right.backend_node_snapshot,
        )
    )


def _origin_backend_fields_same(left: object, right: object) -> bool:
    return (
        _origin_fields_valid(left)
        and _origin_fields_valid(right)
        and _origin_snapshot_fields_same(
            left.backend_node_snapshot,
            right.backend_node_snapshot,
        )
    )


@_dataclass(frozen=True, slots=True)
class FailedDirectNode:
    """One expected backend/domain failure retained without a fake result."""

    identity: DatabaseProfileIdentity
    feature_id: str
    key: DirectNodeKey
    phase_binding: PhaseSetBinding
    reason_code: str
    origin: DirectNodeOrigin | None = None

    def __post_init__(self) -> None:
        if (
            not _identity_fields_valid(self.identity)
            or type(self.feature_id) is not str
            or self.feature_id not in DIRECT_FEATURE_IDS
            or not _node_key_fields_valid(self.key)
            or not _phase_binding_fields_valid(self.phase_binding)
            or not _origin_fields_valid(self.origin)
            or type(self.reason_code) is not str
            or self.reason_code not in _EXPECTED_NODE_REASONS
        ):
            _fail("DIRECT_RESULT_INVALID")
        object.__setattr__(
            self,
            "origin",
            DirectNodeOrigin(
                self.origin.request_origin,
                self.origin.backend_node_snapshot,
            ),
        )


def _failed_node_fields_valid(value: object) -> bool:
    try:
        return (
            type(value) is FailedDirectNode
            and _identity_fields_valid(value.identity)
            and type(value.feature_id) is str
            and value.feature_id in DIRECT_FEATURE_IDS
            and _node_key_fields_valid(value.key)
            and _phase_binding_fields_valid(value.phase_binding)
            and _origin_fields_valid(value.origin)
            and type(value.reason_code) is str
            and value.reason_code in _EXPECTED_NODE_REASONS
        )
    except AttributeError:
        return False


def _validated_outputs(value: object) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple:
        _fail("DIRECT_RESULT_INVALID")
    result: list[tuple[str, float]] = []
    previous: str | None = None
    seen: set[str] = set()
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            _fail("DIRECT_RESULT_INVALID")
        name = _canonical_output_name(pair[0])
        if name in seen or (previous is not None and name < previous):
            _fail("DIRECT_RESULT_INVALID")
        result.append(
            (
                name,
                _exact_canonical_float(pair[1], "DIRECT_RESULT_INVALID"),
            )
        )
        seen.add(name)
        previous = name
    return tuple(result)


@_dataclass(frozen=True, slots=True)
class DirectNodeResult:
    """One retained PASS/FAIL row for one and only one requested node."""

    identity: DatabaseProfileIdentity
    feature_id: str
    key: DirectNodeKey
    phase_binding: PhaseSetBinding
    outcome: str
    reason_code: str
    equilibrium: EquilibriumResult | None
    outputs: tuple[tuple[str, float], ...]
    origin: DirectNodeOrigin | None = None

    def __post_init__(self) -> None:
        if (
            not _identity_fields_valid(self.identity)
            or type(self.feature_id) is not str
            or self.feature_id not in DIRECT_FEATURE_IDS
            or not _node_key_fields_valid(self.key)
            or not _phase_binding_fields_valid(self.phase_binding)
            or not _origin_fields_valid(self.origin)
            or type(self.outcome) is not str
            or self.outcome not in ("PASS", "FAIL")
            or type(self.reason_code) is not str
        ):
            _fail("DIRECT_RESULT_INVALID")
        object.__setattr__(
            self,
            "origin",
            DirectNodeOrigin(
                self.origin.request_origin,
                self.origin.backend_node_snapshot,
            ),
        )
        if (
            self.feature_id in _SCALAR_OUTPUT_NAMES
            and not _scalar_node_schema_valid(
                self.feature_id,
                self.key,
                self.phase_binding,
            )
        ):
            _fail("DIRECT_RESULT_INVALID")
        if type(self.outputs) is not tuple:
            _fail("DIRECT_RESULT_INVALID")
        if self.outcome == "PASS":
            if self.reason_code != "DIRECT_NODE_OK":
                _fail("DIRECT_RESULT_INVALID")
            outputs = _validated_outputs(self.outputs)
            equilibrium = (
                None
                if self.equilibrium is None
                else _rebuild_equilibrium_result(
                    self.equilibrium,
                    "DIRECT_RESULT_INVALID",
                )
            )
            if not _pass_payload_coherent(
                self.feature_id,
                self.key,
                self.phase_binding,
                equilibrium,
                outputs,
            ):
                _fail("DIRECT_RESULT_INVALID")
            object.__setattr__(self, "equilibrium", equilibrium)
            object.__setattr__(self, "outputs", outputs)
        elif (
            self.reason_code not in _EXPECTED_NODE_REASONS
            or self.equilibrium is not None
            or self.outputs
        ):
            _fail("DIRECT_RESULT_INVALID")


def _outputs_fields_valid(value: object) -> bool:
    if type(value) is not tuple:
        return False
    previous: str | None = None
    seen: set[str] = set()
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            return False
        name, number = pair
        if (
            type(name) is not str
            or not name
            or len(name) > 128
            or any(character not in _NAME_CHARACTERS for character in name)
            or name in seen
            or (previous is not None and name < previous)
            or type(number) is not float
            or not _math.isfinite(number)
            or (number == 0.0 and _math.copysign(1.0, number) < 0.0)
        ):
            return False
        seen.add(name)
        previous = name
    return True


def _direct_node_result_fields_valid_unchecked(value: object) -> bool:
    if (
        type(value) is not DirectNodeResult
        or not _identity_fields_valid(value.identity)
        or type(value.feature_id) is not str
        or value.feature_id not in DIRECT_FEATURE_IDS
        or not _node_key_fields_valid(value.key)
        or not _phase_binding_fields_valid(value.phase_binding)
        or not _origin_fields_valid(value.origin)
        or type(value.outcome) is not str
        or value.outcome not in ("PASS", "FAIL")
        or type(value.reason_code) is not str
        or not _outputs_fields_valid(value.outputs)
    ):
        return False
    if (
        value.feature_id in _SCALAR_OUTPUT_NAMES
        and not _scalar_node_schema_valid(
            value.feature_id,
            value.key,
            value.phase_binding,
        )
    ):
        return False
    if value.outcome == "PASS":
        if value.reason_code != "DIRECT_NODE_OK":
            return False
        try:
            equilibrium = (
                None
                if value.equilibrium is None
                else _rebuild_equilibrium_result(
                    value.equilibrium,
                    "DIRECT_RESULT_INVALID",
                )
            )
        except DirectAdapterError:
            return False
        return _pass_payload_coherent(
            value.feature_id,
            value.key,
            value.phase_binding,
            equilibrium,
            value.outputs,
        )
    return (
        value.reason_code in _EXPECTED_NODE_REASONS
        and value.equilibrium is None
        and not value.outputs
    )


def _direct_node_result_fields_valid(value: object) -> bool:
    try:
        return _direct_node_result_fields_valid_unchecked(value)
    except AttributeError:
        return False


@_dataclass(frozen=True, slots=True)
class DirectFeatureResult:
    """Complete ledger bound to one deep canonical direct-request snapshot."""

    feature_id: str
    identity: DatabaseProfileIdentity
    nodes: tuple[DirectNodeResult, ...]
    failed_nodes: tuple[FailedDirectNode, ...]
    requested_nodes: int
    pass_count: int
    fail_count: int
    request: object = _field(default=None, repr=False)
    counts_toward_feature_coverage: bool = _field(init=False, default=False)
    acceptance_claim: bool = _field(init=False, default=False)
    production_use: str = _field(init=False, default="DENIED")

    def __post_init__(self) -> None:
        _validated_feature(self.feature_id)
        canonical_identity = _rebuild_identity(
            self.identity,
            "DIRECT_RESULT_INVALID",
        )
        canonical_request = _rebuild_result_request(
            self.request,
            self.feature_id,
        )
        if not _identity_fields_same(canonical_request.identity, canonical_identity):
            _fail("DIRECT_RESULT_INVALID")
        if (
            type(self.nodes) is not tuple
            or not self.nodes
            or any(not _direct_node_result_fields_valid(node) for node in self.nodes)
        ):
            _fail("DIRECT_RESULT_INVALID")
        expected_origins = _expected_node_origins(canonical_request)
        if len(self.nodes) != len(expected_origins):
            _fail("DIRECT_RESULT_INVALID")
        actual_request_origin = self.nodes[0].origin.request_origin
        expected_request_origin = expected_origins[0].request_origin
        if not _origin_snapshot_fields_same(
            actual_request_origin.snapshot,
            expected_request_origin.snapshot,
        ):
            _fail("DIRECT_RESULT_INVALID")
        for ordinal, (row, expected_origin) in enumerate(
            zip(self.nodes, expected_origins)
        ):
            if (
                row.key.node.ordinal != ordinal
                or not _identity_fields_same(row.identity, self.identity)
                or row.feature_id != self.feature_id
                or row.origin.request_origin is not actual_request_origin
                or expected_origin.request_origin is not expected_request_origin
                or not _origin_backend_fields_same(row.origin, expected_origin)
            ):
                _fail("DIRECT_RESULT_INVALID")
        if any(
            type(value) is not int or value < 0
            for value in (self.requested_nodes, self.pass_count, self.fail_count)
        ):
            _fail("DIRECT_RESULT_INVALID")
        observed_failures = tuple(row for row in self.nodes if row.outcome == "FAIL")
        allowed_failures = _allowed_failure_reasons(self.feature_id)
        observed_passes = sum(row.outcome == "PASS" for row in self.nodes)
        if (
            type(self.failed_nodes) is not tuple
            or len(self.failed_nodes) != len(observed_failures)
            or self.requested_nodes != len(self.nodes)
            or self.pass_count != observed_passes
            or self.fail_count != len(observed_failures)
            or self.pass_count + self.fail_count != self.requested_nodes
            or self.counts_toward_feature_coverage is not False
            or self.acceptance_claim is not False
            or type(self.production_use) is not str
            or self.production_use != "DENIED"
        ):
            _fail("DIRECT_RESULT_INVALID")
        if not _feature_result_rows_valid(
            self.feature_id,
            self.nodes,
            canonical_request,
        ):
            _fail("DIRECT_RESULT_INVALID")
        for supplied, source in zip(self.failed_nodes, observed_failures):
            if (
                not _failed_node_fields_valid(supplied)
                or not _identity_fields_same(supplied.identity, self.identity)
                or not _identity_fields_same(supplied.identity, source.identity)
                or supplied.feature_id != self.feature_id
                or supplied.feature_id != source.feature_id
                or type(source.reason_code) is not str
                or source.reason_code not in allowed_failures
                or supplied.reason_code != source.reason_code
                or not _node_key_fields_same(supplied.key, source.key)
                or not _phase_binding_fields_same(
                    supplied.phase_binding,
                    source.phase_binding,
                )
                or not _origin_fields_same(supplied.origin, source.origin)
            ):
                _fail("DIRECT_RESULT_INVALID")
        object.__setattr__(self, "identity", canonical_identity)
        object.__setattr__(self, "request", canonical_request)


@_dataclass(frozen=True, slots=True)
class EquilibriumBackendNodeRequest:
    identity: DatabaseProfileIdentity
    feature_id: str
    key: DirectNodeKey
    equilibrium: EquilibriumRequest
    phase_binding: PhaseSetBinding

    def __post_init__(self) -> None:
        if (
            not _identity_fields_valid(self.identity)
            or not _node_key_fields_valid(self.key)
            or not _phase_binding_fields_valid(self.phase_binding)
        ):
            _fail("DIRECT_REQUEST_INVALID")
        _validated_feature(self.feature_id)
        if (
            not _equilibrium_request_fields_valid(self.equilibrium)
            or not _string_tuple_fields_same(
                self.equilibrium.phases,
                self.phase_binding.effective_phases,
            )
        ):
            _fail("DIRECT_REQUEST_INVALID")


@_dataclass(frozen=True, slots=True)
class PhaseGibbsBackendNodeRequest:
    identity: DatabaseProfileIdentity
    feature_id: str
    key: DirectNodeKey
    state: EquilibriumRequest
    phase: str
    phase_binding: PhaseSetBinding

    def __post_init__(self) -> None:
        if (
            type(self.feature_id) is not str
            or self.feature_id != "phase_gibbs_energy"
            or not _identity_fields_valid(self.identity)
            or not _node_key_fields_valid(self.key)
            or not _phase_binding_fields_valid(self.phase_binding)
        ):
            _fail("DIRECT_REQUEST_INVALID")
        phase = _canonical_name(self.phase, "DIRECT_PHASE_INVALID")
        if (
            not _equilibrium_request_fields_valid(self.state)
            or not _string_tuple_fields_same(self.state.phases, (phase,))
            or not _string_tuple_fields_same(
                self.phase_binding.effective_phases,
                (phase,),
            )
        ):
            _fail("DIRECT_REQUEST_INVALID")
        object.__setattr__(self, "phase", phase)


@_dataclass(frozen=True, slots=True)
class PhaseDrivingForceBackendNodeRequest:
    identity: DatabaseProfileIdentity
    feature_id: str
    key: DirectNodeKey
    reference_state: EquilibriumRequest
    target_phase: str
    phase_binding: PhaseSetBinding

    def __post_init__(self) -> None:
        if (
            type(self.feature_id) is not str
            or self.feature_id != "phase_driving_force"
            or not _identity_fields_valid(self.identity)
            or not _node_key_fields_valid(self.key)
            or not _phase_binding_fields_valid(self.phase_binding)
        ):
            _fail("DIRECT_REQUEST_INVALID")
        if (
            not _equilibrium_request_fields_valid(self.reference_state)
            or not _string_tuple_fields_same(
                self.reference_state.phases,
                self.phase_binding.effective_phases,
            )
        ):
            _fail("DIRECT_REQUEST_INVALID")
        target = _canonical_name(self.target_phase, "DIRECT_PHASE_INVALID")
        if target in self.reference_state.phases:
            _fail("DIRECT_TARGET_PHASE_OVERLAP")
        if target not in self.phase_binding.explicit_exclusions:
            _fail("DIRECT_TARGET_PHASE_NOT_EXCLUDED")
        object.__setattr__(self, "target_phase", target)


@_dataclass(frozen=True, slots=True)
class TZeroBackendNodeRequest:
    identity: DatabaseProfileIdentity
    feature_id: str
    key: DirectNodeKey
    state: EquilibriumRequest
    phase_one: str
    phase_two: str
    minimum_temperature_k: float
    maximum_temperature_k: float
    phase_binding: PhaseSetBinding

    def __post_init__(self) -> None:
        if (
            type(self.feature_id) is not str
            or self.feature_id != "tzero_temperature"
            or not _identity_fields_valid(self.identity)
            or not _node_key_fields_valid(self.key)
            or not _phase_binding_fields_valid(self.phase_binding)
        ):
            _fail("DIRECT_REQUEST_INVALID")
        if (
            not _equilibrium_request_fields_valid(self.state)
            or not _string_tuple_fields_same(
                self.state.phases,
                self.phase_binding.effective_phases,
            )
        ):
            _fail("DIRECT_REQUEST_INVALID")
        first = _canonical_name(self.phase_one, "DIRECT_PHASE_INVALID")
        second = _canonical_name(self.phase_two, "DIRECT_PHASE_INVALID")
        if first == second:
            _fail("DIRECT_TZERO_PHASES_IDENTICAL")
        if not _string_tuple_fields_same(self.state.phases, (first, second)):
            _fail("DIRECT_PHASE_SELECTION_MISMATCH")
        minimum, maximum = _tzero_bounds(self.minimum_temperature_k, self.maximum_temperature_k)
        object.__setattr__(self, "phase_one", first)
        object.__setattr__(self, "phase_two", second)
        object.__setattr__(self, "minimum_temperature_k", minimum)
        object.__setattr__(self, "maximum_temperature_k", maximum)


@_dataclass(frozen=True, slots=True)
class EquilibriumBackendReply:
    identity: DatabaseProfileIdentity
    feature_id: str
    key: DirectNodeKey
    phase_binding: PhaseSetBinding
    raw_result: EquilibriumRawResult

    def __post_init__(self) -> None:
        if (
            not _identity_fields_valid(self.identity)
            or not _node_key_fields_valid(self.key)
            or not _phase_binding_fields_valid(self.phase_binding)
        ):
            _fail("DIRECT_BACKEND_REPLY_INVALID")
        _validated_feature(self.feature_id)
        if not _raw_result_fields_valid(self.raw_result):
            _fail("DIRECT_BACKEND_REPLY_INVALID")


@_dataclass(frozen=True, slots=True)
class ScalarBackendReply:
    identity: DatabaseProfileIdentity
    feature_id: str
    key: DirectNodeKey
    phase_binding: PhaseSetBinding
    value: float

    def __post_init__(self) -> None:
        if (
            not _identity_fields_valid(self.identity)
            or not _node_key_fields_valid(self.key)
            or not _phase_binding_fields_valid(self.phase_binding)
        ):
            _fail("DIRECT_BACKEND_REPLY_INVALID")
        _validated_feature(self.feature_id)


class DirectFeatureBackend(_Protocol):
    """Structural backend boundary; implementations may call a real solver."""

    def solve_equilibrium(self, request: EquilibriumBackendNodeRequest) -> EquilibriumBackendReply:
        """Return raw phase states for a bound equilibrium node."""

    def phase_gibbs_energy(self, request: PhaseGibbsBackendNodeRequest) -> ScalarBackendReply:
        """Return isolated-phase molar Gibbs energy in J/mol."""

    def phase_driving_force(self, request: PhaseDrivingForceBackendNodeRequest) -> ScalarBackendReply:
        """Return target-phase driving force in J/mol."""

    def tzero_temperature(self, request: TZeroBackendNodeRequest) -> ScalarBackendReply:
        """Return T-zero in kelvin inside the supplied bounds."""


def _identity_and_equilibrium(identity: object, equilibrium: object) -> None:
    if not _identity_fields_valid(identity) or not _equilibrium_request_fields_valid(equilibrium):
        _fail("DIRECT_REQUEST_INVALID")


@_dataclass(frozen=True, slots=True)
class EquilibriumSingleRequest:
    identity: DatabaseProfileIdentity
    equilibrium: EquilibriumRequest
    explicit_exclusions: tuple[str, ...]
    feature_id: str = _field(init=False, default="equilibrium_single")

    def __post_init__(self) -> None:
        _identity_and_equilibrium(self.identity, self.equilibrium)
        exclusions = _validate_phase_boundary(self.equilibrium.phases, self.explicit_exclusions)
        object.__setattr__(self, "explicit_exclusions", exclusions)


@_dataclass(frozen=True, slots=True)
class EquilibriumTemperatureScanRequest:
    identity: DatabaseProfileIdentity
    base_equilibrium: EquilibriumRequest
    temperatures_k: tuple[float, ...]
    explicit_exclusions: tuple[str, ...]
    max_nodes: int
    feature_id: str = _field(init=False, default="equilibrium_temperature_scan")

    def __post_init__(self) -> None:
        _identity_and_equilibrium(self.identity, self.base_equilibrium)
        axis = _temperature_axis(self.temperatures_k)
        maximum = _validated_max_nodes(self.max_nodes)
        _require_node_count(len(axis.values), maximum)
        exclusions = _validate_phase_boundary(self.base_equilibrium.phases, self.explicit_exclusions)
        object.__setattr__(self, "temperatures_k", axis.values)
        object.__setattr__(self, "explicit_exclusions", exclusions)
        object.__setattr__(self, "max_nodes", maximum)


def _validated_composition_path(
    base: EquilibriumRequest,
    varying_component: object,
    balance_component: object,
    fractions: object,
) -> tuple[str, str, tuple[float, ...]]:
    varying = _canonical_name(varying_component, "DIRECT_COMPONENT_INVALID")
    balance = _canonical_name(balance_component, "DIRECT_COMPONENT_INVALID")
    if (
        varying == balance
        or varying == "VA"
        or balance == "VA"
        or varying not in base.components
        or balance not in base.components
    ):
        _fail("DIRECT_COMPONENT_INVALID")
    axis = _composition_axis(varying, fractions)
    base_values = dict(base.composition)
    fixed_total = _math.fsum(
        base_values[component]
        for component in base.components
        if component not in (varying, balance)
    )
    for fraction in axis.values:
        balance_value = 1.0 - fixed_total - fraction
        if not _math.isfinite(balance_value) or balance_value < -1.0e-12:
            _fail("DIRECT_COMPOSITION_PATH_INVALID")
    return varying, balance, axis.values


@_dataclass(frozen=True, slots=True)
class EquilibriumCompositionScanRequest:
    identity: DatabaseProfileIdentity
    base_equilibrium: EquilibriumRequest
    varying_component: str
    balance_component: str
    fractions: tuple[float, ...]
    explicit_exclusions: tuple[str, ...]
    max_nodes: int
    feature_id: str = _field(init=False, default="equilibrium_composition_scan")

    def __post_init__(self) -> None:
        _identity_and_equilibrium(self.identity, self.base_equilibrium)
        varying, balance, fractions = _validated_composition_path(
            self.base_equilibrium,
            self.varying_component,
            self.balance_component,
            self.fractions,
        )
        maximum = _validated_max_nodes(self.max_nodes)
        _require_node_count(len(fractions), maximum)
        exclusions = _validate_phase_boundary(self.base_equilibrium.phases, self.explicit_exclusions)
        object.__setattr__(self, "varying_component", varying)
        object.__setattr__(self, "balance_component", balance)
        object.__setattr__(self, "fractions", fractions)
        object.__setattr__(self, "explicit_exclusions", exclusions)
        object.__setattr__(self, "max_nodes", maximum)


@_dataclass(frozen=True, slots=True)
class TernaryPhaseFractionMapRequest:
    identity: DatabaseProfileIdentity
    temperature_k: float
    pressure_pa: float
    components: tuple[str, ...]
    phases: tuple[str, ...]
    ternary_components: tuple[str, str, str]
    target_phase: str
    explicit_exclusions: tuple[str, ...]
    interval_count: int
    max_nodes: int
    composition_basis: str = _field(init=False, default="MOLE_FRACTION")
    feature_id: str = _field(init=False, default="ternary_phase_fraction_map")

    def __post_init__(self) -> None:
        if not _identity_fields_valid(self.identity):
            _fail("DIRECT_REQUEST_INVALID")
        components = _validated_phases(self.components)
        phases = _validated_phases(self.phases)
        if type(self.ternary_components) is not tuple or len(self.ternary_components) != 3:
            _fail("DIRECT_TERNARY_COMPONENTS_INVALID")
        ternary = tuple(
            _canonical_name(component, "DIRECT_COMPONENT_INVALID")
            for component in self.ternary_components
        )
        if (
            len(set(ternary)) != 3
            or "VA" in ternary
            or any(component not in components for component in ternary)
        ):
            _fail("DIRECT_TERNARY_COMPONENTS_INVALID")
        for component in ternary:
            _composition_coordinate_name(component)
        extras = set(components) - set(ternary)
        if extras not in (set(), {"VA"}):
            _fail("DIRECT_TERNARY_COMPONENTS_INVALID")
        target = _canonical_name(self.target_phase, "DIRECT_PHASE_INVALID")
        if target not in phases:
            _fail("DIRECT_TARGET_PHASE_INVALID")
        if type(self.interval_count) is not int or self.interval_count < 2:
            _fail("DIRECT_TERNARY_INTERVAL_INVALID")
        maximum = _validated_max_nodes(self.max_nodes)
        count = (self.interval_count + 1) * (self.interval_count + 2) // 2
        _require_node_count(count, maximum)
        exclusions = _validate_phase_boundary(phases, self.explicit_exclusions)
        composition = tuple(
            (component, 1.0 if component == ternary[0] else 0.0)
            for component in components
        )
        state = EquilibriumRequest(
            self.temperature_k,
            self.pressure_pa,
            components,
            phases,
            composition,
        )
        object.__setattr__(self, "temperature_k", state.temperature_k)
        object.__setattr__(self, "pressure_pa", state.pressure_pa)
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "phases", phases)
        object.__setattr__(self, "ternary_components", ternary)
        object.__setattr__(self, "target_phase", target)
        object.__setattr__(self, "explicit_exclusions", exclusions)
        object.__setattr__(self, "max_nodes", maximum)


@_dataclass(frozen=True, slots=True)
class ManualPhaseSelectionRequest:
    identity: DatabaseProfileIdentity
    equilibrium: EquilibriumRequest
    available_phases: tuple[str, ...]
    selected_phases: tuple[str, ...]
    explicit_exclusions: tuple[str, ...]
    feature_id: str = _field(init=False, default="manual_phase_selection_metastable")

    def __post_init__(self) -> None:
        _identity_and_equilibrium(self.identity, self.equilibrium)
        available = _validated_phases(self.available_phases)
        selected = _validated_phases(self.selected_phases)
        excluded = _validated_exclusions(self.explicit_exclusions)
        if set(selected) & set(excluded):
            _fail("DIRECT_PHASE_EXCLUSION_OVERLAP")
        if set(selected) | set(excluded) != set(available) or len(selected) + len(excluded) != len(available):
            _fail("DIRECT_PHASE_SELECTION_INCOMPLETE")
        if self.equilibrium.phases != selected:
            _fail("DIRECT_PHASE_SELECTION_MISMATCH")
        object.__setattr__(self, "available_phases", available)
        object.__setattr__(self, "selected_phases", selected)
        object.__setattr__(self, "explicit_exclusions", excluded)


@_dataclass(frozen=True, slots=True)
class PhaseGibbsEnergyRequest:
    identity: DatabaseProfileIdentity
    base_equilibrium: EquilibriumRequest
    candidate_phases: tuple[str, ...]
    phase_isolations: tuple[PhaseSetBinding, ...]
    temperatures_k: tuple[float, ...]
    max_nodes: int
    feature_id: str = _field(init=False, default="phase_gibbs_energy")

    def __post_init__(self) -> None:
        _identity_and_equilibrium(self.identity, self.base_equilibrium)
        candidates = _validated_phases(self.candidate_phases)
        selected_set = set(self.base_equilibrium.phases)
        if (
            any(phase not in candidates for phase in self.base_equilibrium.phases)
            or not _string_tuple_fields_same(
                self.base_equilibrium.phases,
                tuple(phase for phase in candidates if phase in selected_set),
            )
            or type(self.phase_isolations) is not tuple
            or len(self.phase_isolations) != len(self.base_equilibrium.phases)
        ):
            _fail("DIRECT_PHASE_BINDING_INVALID")
        for phase, binding in zip(
            self.base_equilibrium.phases,
            self.phase_isolations,
        ):
            if (
                not _phase_binding_fields_valid(binding)
                or not _string_tuple_fields_same(
                    binding.phase_universe,
                    candidates,
                )
                or not _string_tuple_fields_same(
                    binding.effective_phases,
                    (phase,),
                )
            ):
                _fail("DIRECT_PHASE_BINDING_INVALID")
        axis = _temperature_axis(self.temperatures_k)
        maximum = _validated_max_nodes(self.max_nodes)
        _require_node_count(len(axis.values) * len(self.base_equilibrium.phases), maximum)
        object.__setattr__(self, "candidate_phases", candidates)
        object.__setattr__(self, "temperatures_k", axis.values)
        object.__setattr__(self, "max_nodes", maximum)


@_dataclass(frozen=True, slots=True)
class PhaseDrivingForceRequest:
    identity: DatabaseProfileIdentity
    reference_equilibrium: EquilibriumRequest
    target_phase: str
    temperatures_k: tuple[float, ...]
    explicit_exclusions: tuple[str, ...]
    max_nodes: int
    feature_id: str = _field(init=False, default="phase_driving_force")

    def __post_init__(self) -> None:
        _identity_and_equilibrium(self.identity, self.reference_equilibrium)
        target = _canonical_name(self.target_phase, "DIRECT_PHASE_INVALID")
        if target in self.reference_equilibrium.phases:
            _fail("DIRECT_TARGET_PHASE_OVERLAP")
        axis = _temperature_axis(self.temperatures_k)
        maximum = _validated_max_nodes(self.max_nodes)
        _require_node_count(len(axis.values), maximum)
        exclusions = _validate_phase_boundary(self.reference_equilibrium.phases, self.explicit_exclusions)
        if target not in exclusions:
            _fail("DIRECT_TARGET_PHASE_NOT_EXCLUDED")
        object.__setattr__(self, "target_phase", target)
        object.__setattr__(self, "temperatures_k", axis.values)
        object.__setattr__(self, "explicit_exclusions", exclusions)
        object.__setattr__(self, "max_nodes", maximum)


def _tzero_bounds(minimum: object, maximum: object) -> tuple[float, float]:
    try:
        lower = _binary64(minimum)
        upper = _binary64(maximum)
    except DirectAdapterError as error:
        raise DirectAdapterError("DIRECT_TZERO_BOUNDS_INVALID") from error
    if lower <= 0.0 or upper <= lower:
        _fail("DIRECT_TZERO_BOUNDS_INVALID")
    return lower, upper


@_dataclass(frozen=True, slots=True)
class TZeroTemperatureRequest:
    identity: DatabaseProfileIdentity
    base_equilibrium: EquilibriumRequest
    phase_one: str
    phase_two: str
    varying_component: str
    balance_component: str
    fractions: tuple[float, ...]
    minimum_temperature_k: float
    maximum_temperature_k: float
    explicit_exclusions: tuple[str, ...]
    max_nodes: int
    feature_id: str = _field(init=False, default="tzero_temperature")

    def __post_init__(self) -> None:
        _identity_and_equilibrium(self.identity, self.base_equilibrium)
        first = _canonical_name(self.phase_one, "DIRECT_PHASE_INVALID")
        second = _canonical_name(self.phase_two, "DIRECT_PHASE_INVALID")
        if first == second:
            _fail("DIRECT_TZERO_PHASES_IDENTICAL")
        if self.base_equilibrium.phases != (first, second):
            _fail("DIRECT_PHASE_SELECTION_MISMATCH")
        varying, balance, fractions = _validated_composition_path(
            self.base_equilibrium,
            self.varying_component,
            self.balance_component,
            self.fractions,
        )
        lower, upper = _tzero_bounds(self.minimum_temperature_k, self.maximum_temperature_k)
        maximum_nodes = _validated_max_nodes(self.max_nodes)
        _require_node_count(len(fractions), maximum_nodes)
        exclusions = _validate_phase_boundary(self.base_equilibrium.phases, self.explicit_exclusions)
        object.__setattr__(self, "phase_one", first)
        object.__setattr__(self, "phase_two", second)
        object.__setattr__(self, "varying_component", varying)
        object.__setattr__(self, "balance_component", balance)
        object.__setattr__(self, "fractions", fractions)
        object.__setattr__(self, "minimum_temperature_k", lower)
        object.__setattr__(self, "maximum_temperature_k", upper)
        object.__setattr__(self, "explicit_exclusions", exclusions)
        object.__setattr__(self, "max_nodes", maximum_nodes)


def _copy_exact_float_tuple(
    value: object,
    reason_code: str,
) -> tuple[float, ...]:
    if type(value) is not tuple or not value:
        _fail(reason_code)
    return tuple(
        _exact_canonical_float(item, reason_code)
        for item in value
    )


def _direct_request_header_valid(value: object, expected_type: type) -> None:
    expected_feature = {
        EquilibriumSingleRequest: "equilibrium_single",
        EquilibriumTemperatureScanRequest: "equilibrium_temperature_scan",
        EquilibriumCompositionScanRequest: "equilibrium_composition_scan",
        TernaryPhaseFractionMapRequest: "ternary_phase_fraction_map",
        ManualPhaseSelectionRequest: "manual_phase_selection_metastable",
        PhaseGibbsEnergyRequest: "phase_gibbs_energy",
        PhaseDrivingForceRequest: "phase_driving_force",
        TZeroTemperatureRequest: "tzero_temperature",
    }.get(expected_type)
    if (
        expected_feature is None
        or type(value) is not expected_type
        or type(value.feature_id) is not str
        or value.feature_id != expected_feature
    ):
        _fail("DIRECT_REQUEST_INVALID")


def _rebuild_direct_request_unchecked(value: object, expected_type: type):
    _direct_request_header_valid(value, expected_type)
    identity = _rebuild_identity(value.identity, "DIRECT_REQUEST_INVALID")
    if expected_type is EquilibriumSingleRequest:
        return EquilibriumSingleRequest(
            identity,
            _rebuild_equilibrium_request(
                value.equilibrium,
                "DIRECT_REQUEST_INVALID",
            ),
            _copy_exact_names(
                value.explicit_exclusions,
                "DIRECT_REQUEST_INVALID",
                allow_empty=True,
            ),
        )
    if expected_type is EquilibriumTemperatureScanRequest:
        if type(value.max_nodes) is not int:
            _fail("DIRECT_REQUEST_INVALID")
        return EquilibriumTemperatureScanRequest(
            identity,
            _rebuild_equilibrium_request(
                value.base_equilibrium,
                "DIRECT_REQUEST_INVALID",
            ),
            _copy_exact_float_tuple(
                value.temperatures_k,
                "DIRECT_REQUEST_INVALID",
            ),
            _copy_exact_names(
                value.explicit_exclusions,
                "DIRECT_REQUEST_INVALID",
                allow_empty=True,
            ),
            value.max_nodes,
        )
    if expected_type is EquilibriumCompositionScanRequest:
        if (
            type(value.varying_component) is not str
            or type(value.balance_component) is not str
            or type(value.max_nodes) is not int
        ):
            _fail("DIRECT_REQUEST_INVALID")
        return EquilibriumCompositionScanRequest(
            identity,
            _rebuild_equilibrium_request(
                value.base_equilibrium,
                "DIRECT_REQUEST_INVALID",
            ),
            value.varying_component,
            value.balance_component,
            _copy_exact_float_tuple(value.fractions, "DIRECT_REQUEST_INVALID"),
            _copy_exact_names(
                value.explicit_exclusions,
                "DIRECT_REQUEST_INVALID",
                allow_empty=True,
            ),
            value.max_nodes,
        )
    if expected_type is TernaryPhaseFractionMapRequest:
        if (
            type(value.temperature_k) is not float
            or type(value.pressure_pa) is not float
            or type(value.target_phase) is not str
            or type(value.max_nodes) is not int
            or type(value.composition_basis) is not str
            or value.composition_basis != "MOLE_FRACTION"
        ):
            _fail("DIRECT_REQUEST_INVALID")
        if type(value.interval_count) is not int:
            _fail("DIRECT_TERNARY_INTERVAL_INVALID")
        ternary = _copy_exact_names(
            value.ternary_components,
            "DIRECT_REQUEST_INVALID",
        )
        return TernaryPhaseFractionMapRequest(
            identity,
            _exact_canonical_float(value.temperature_k, "DIRECT_REQUEST_INVALID"),
            _exact_canonical_float(value.pressure_pa, "DIRECT_REQUEST_INVALID"),
            _copy_exact_names(value.components, "DIRECT_REQUEST_INVALID"),
            _copy_exact_names(value.phases, "DIRECT_REQUEST_INVALID"),
            ternary,
            value.target_phase,
            _copy_exact_names(
                value.explicit_exclusions,
                "DIRECT_REQUEST_INVALID",
                allow_empty=True,
            ),
            value.interval_count,
            value.max_nodes,
        )
    if expected_type is ManualPhaseSelectionRequest:
        return ManualPhaseSelectionRequest(
            identity,
            _rebuild_equilibrium_request(
                value.equilibrium,
                "DIRECT_REQUEST_INVALID",
            ),
            _copy_exact_names(value.available_phases, "DIRECT_REQUEST_INVALID"),
            _copy_exact_names(value.selected_phases, "DIRECT_REQUEST_INVALID"),
            _copy_exact_names(
                value.explicit_exclusions,
                "DIRECT_REQUEST_INVALID",
                allow_empty=True,
            ),
        )
    if expected_type is PhaseGibbsEnergyRequest:
        if type(value.phase_isolations) is not tuple or type(value.max_nodes) is not int:
            _fail("DIRECT_REQUEST_INVALID")
        isolations = tuple(
            _rebuild_phase_binding(binding, "DIRECT_REQUEST_INVALID")
            for binding in value.phase_isolations
        )
        return PhaseGibbsEnergyRequest(
            identity,
            _rebuild_equilibrium_request(
                value.base_equilibrium,
                "DIRECT_REQUEST_INVALID",
            ),
            _copy_exact_names(value.candidate_phases, "DIRECT_REQUEST_INVALID"),
            isolations,
            _copy_exact_float_tuple(
                value.temperatures_k,
                "DIRECT_REQUEST_INVALID",
            ),
            value.max_nodes,
        )
    if expected_type is PhaseDrivingForceRequest:
        if type(value.target_phase) is not str or type(value.max_nodes) is not int:
            _fail("DIRECT_REQUEST_INVALID")
        return PhaseDrivingForceRequest(
            identity,
            _rebuild_equilibrium_request(
                value.reference_equilibrium,
                "DIRECT_REQUEST_INVALID",
            ),
            value.target_phase,
            _copy_exact_float_tuple(
                value.temperatures_k,
                "DIRECT_REQUEST_INVALID",
            ),
            _copy_exact_names(
                value.explicit_exclusions,
                "DIRECT_REQUEST_INVALID",
                allow_empty=True,
            ),
            value.max_nodes,
        )
    if expected_type is TZeroTemperatureRequest:
        if (
            type(value.phase_one) is not str
            or type(value.phase_two) is not str
            or type(value.varying_component) is not str
            or type(value.balance_component) is not str
            or type(value.minimum_temperature_k) is not float
            or type(value.maximum_temperature_k) is not float
            or type(value.max_nodes) is not int
        ):
            _fail("DIRECT_REQUEST_INVALID")
        return TZeroTemperatureRequest(
            identity,
            _rebuild_equilibrium_request(
                value.base_equilibrium,
                "DIRECT_REQUEST_INVALID",
            ),
            value.phase_one,
            value.phase_two,
            value.varying_component,
            value.balance_component,
            _copy_exact_float_tuple(value.fractions, "DIRECT_REQUEST_INVALID"),
            _exact_canonical_float(
                value.minimum_temperature_k,
                "DIRECT_REQUEST_INVALID",
            ),
            _exact_canonical_float(
                value.maximum_temperature_k,
                "DIRECT_REQUEST_INVALID",
            ),
            _copy_exact_names(
                value.explicit_exclusions,
                "DIRECT_REQUEST_INVALID",
                allow_empty=True,
            ),
            value.max_nodes,
        )
    _fail("DIRECT_REQUEST_INVALID")


def _rebuild_direct_request(value: object, expected_type: type):
    try:
        return _rebuild_direct_request_unchecked(value, expected_type)
    except AttributeError as error:
        raise DirectAdapterError("DIRECT_REQUEST_INVALID") from error


def _request_type_for_feature(feature_id: object) -> type | None:
    if type(feature_id) is not str:
        return None
    return {
        "equilibrium_single": EquilibriumSingleRequest,
        "equilibrium_temperature_scan": EquilibriumTemperatureScanRequest,
        "equilibrium_composition_scan": EquilibriumCompositionScanRequest,
        "ternary_phase_fraction_map": TernaryPhaseFractionMapRequest,
        "manual_phase_selection_metastable": ManualPhaseSelectionRequest,
        "phase_gibbs_energy": PhaseGibbsEnergyRequest,
        "phase_driving_force": PhaseDrivingForceRequest,
        "tzero_temperature": TZeroTemperatureRequest,
    }.get(feature_id)


def _rebuild_result_request(value: object, feature_id: object):
    expected_type = _request_type_for_feature(feature_id)
    if expected_type is None:
        _fail("DIRECT_RESULT_INVALID")
    try:
        rebuilt = _rebuild_direct_request(value, expected_type)
    except DirectAdapterError as error:
        raise DirectAdapterError("DIRECT_RESULT_INVALID") from error
    if rebuilt.feature_id != feature_id:
        _fail("DIRECT_RESULT_INVALID")
    return rebuilt


def _identity_snapshot(value: DatabaseProfileIdentity) -> tuple[str, str, str]:
    return (value.database_family, value.profile_id, value.runtime_sha256)


def _equilibrium_request_snapshot(value: EquilibriumRequest) -> tuple[object, ...]:
    return (
        value.temperature_k.hex(),
        value.pressure_pa.hex(),
        value.components,
        value.phases,
        tuple((name, number.hex()) for name, number in value.composition),
    )


def _phase_binding_snapshot(value: PhaseSetBinding) -> tuple[object, ...]:
    return (
        value.phase_universe,
        value.effective_phases,
        value.explicit_exclusions,
    )


def _direct_request_snapshot(value: object) -> tuple[object, ...]:
    identity = _identity_snapshot(value.identity)
    if type(value) is EquilibriumSingleRequest:
        return (
            value.feature_id,
            identity,
            _equilibrium_request_snapshot(value.equilibrium),
            value.explicit_exclusions,
        )
    if type(value) is EquilibriumTemperatureScanRequest:
        return (
            value.feature_id,
            identity,
            _equilibrium_request_snapshot(value.base_equilibrium),
            tuple(number.hex() for number in value.temperatures_k),
            value.explicit_exclusions,
            value.max_nodes,
        )
    if type(value) is EquilibriumCompositionScanRequest:
        return (
            value.feature_id,
            identity,
            _equilibrium_request_snapshot(value.base_equilibrium),
            value.varying_component,
            value.balance_component,
            tuple(number.hex() for number in value.fractions),
            value.explicit_exclusions,
            value.max_nodes,
        )
    if type(value) is TernaryPhaseFractionMapRequest:
        return (
            value.feature_id,
            identity,
            value.temperature_k.hex(),
            value.pressure_pa.hex(),
            value.components,
            value.phases,
            value.ternary_components,
            value.target_phase,
            value.explicit_exclusions,
            value.interval_count,
            value.max_nodes,
            value.composition_basis,
        )
    if type(value) is ManualPhaseSelectionRequest:
        return (
            value.feature_id,
            identity,
            _equilibrium_request_snapshot(value.equilibrium),
            value.available_phases,
            value.selected_phases,
            value.explicit_exclusions,
        )
    if type(value) is PhaseGibbsEnergyRequest:
        return (
            value.feature_id,
            identity,
            _equilibrium_request_snapshot(value.base_equilibrium),
            value.candidate_phases,
            tuple(
                _phase_binding_snapshot(binding)
                for binding in value.phase_isolations
            ),
            tuple(number.hex() for number in value.temperatures_k),
            value.max_nodes,
        )
    if type(value) is PhaseDrivingForceRequest:
        return (
            value.feature_id,
            identity,
            _equilibrium_request_snapshot(value.reference_equilibrium),
            value.target_phase,
            tuple(number.hex() for number in value.temperatures_k),
            value.explicit_exclusions,
            value.max_nodes,
        )
    if type(value) is TZeroTemperatureRequest:
        return (
            value.feature_id,
            identity,
            _equilibrium_request_snapshot(value.base_equilibrium),
            value.phase_one,
            value.phase_two,
            value.varying_component,
            value.balance_component,
            tuple(number.hex() for number in value.fractions),
            value.minimum_temperature_k.hex(),
            value.maximum_temperature_k.hex(),
            value.explicit_exclusions,
            value.max_nodes,
        )
    _fail("DIRECT_REQUEST_INVALID")


def _prepare_direct_request(value: object, expected_type: type):
    rebuilt = _rebuild_direct_request(value, expected_type)
    return rebuilt, _direct_request_snapshot(rebuilt)


def _assert_caller_request_unchanged(
    caller_request: object,
    expected_type: type,
    snapshot: tuple[object, ...],
) -> None:
    try:
        current = _rebuild_direct_request(caller_request, expected_type)
        current_snapshot = _direct_request_snapshot(current)
    except (AttributeError, DirectAdapterError) as error:
        raise DirectAdapterError("DIRECT_REQUEST_MUTATED") from error
    if current_snapshot != snapshot:
        _fail("DIRECT_REQUEST_MUTATED")


class _RawReplyBackend:
    __slots__ = ("_raw_result",)

    def __init__(self, raw_result: EquilibriumRawResult) -> None:
        self._raw_result = raw_result

    def solve(self, _request: EquilibriumRequest) -> EquilibriumRawResult:
        return self._raw_result


def _grid_node_snapshot(value: GridNode) -> tuple[object, ...]:
    return (
        value.ordinal,
        tuple((name, number.hex()) for name, number in value.coordinates),
    )


def _node_key_snapshot(value: DirectNodeKey) -> tuple[object, ...]:
    return (_grid_node_snapshot(value.node), value.labels)


def _rebuild_backend_node_request_unchecked(value: object):
    if type(value) is EquilibriumBackendNodeRequest:
        if type(value.feature_id) is not str:
            _fail("DIRECT_BACKEND_REQUEST_MUTATED")
        return EquilibriumBackendNodeRequest(
            _rebuild_identity(value.identity, "DIRECT_BACKEND_REQUEST_MUTATED"),
            value.feature_id,
            _rebuild_node_key(value.key, "DIRECT_BACKEND_REQUEST_MUTATED"),
            _rebuild_equilibrium_request(
                value.equilibrium,
                "DIRECT_BACKEND_REQUEST_MUTATED",
            ),
            _rebuild_phase_binding(
                value.phase_binding,
                "DIRECT_BACKEND_REQUEST_MUTATED",
            ),
        )
    if type(value) is PhaseGibbsBackendNodeRequest:
        if type(value.feature_id) is not str or type(value.phase) is not str:
            _fail("DIRECT_BACKEND_REQUEST_MUTATED")
        return PhaseGibbsBackendNodeRequest(
            _rebuild_identity(value.identity, "DIRECT_BACKEND_REQUEST_MUTATED"),
            value.feature_id,
            _rebuild_node_key(value.key, "DIRECT_BACKEND_REQUEST_MUTATED"),
            _rebuild_equilibrium_request(
                value.state,
                "DIRECT_BACKEND_REQUEST_MUTATED",
            ),
            value.phase,
            _rebuild_phase_binding(
                value.phase_binding,
                "DIRECT_BACKEND_REQUEST_MUTATED",
            ),
        )
    if type(value) is PhaseDrivingForceBackendNodeRequest:
        if type(value.feature_id) is not str or type(value.target_phase) is not str:
            _fail("DIRECT_BACKEND_REQUEST_MUTATED")
        return PhaseDrivingForceBackendNodeRequest(
            _rebuild_identity(value.identity, "DIRECT_BACKEND_REQUEST_MUTATED"),
            value.feature_id,
            _rebuild_node_key(value.key, "DIRECT_BACKEND_REQUEST_MUTATED"),
            _rebuild_equilibrium_request(
                value.reference_state,
                "DIRECT_BACKEND_REQUEST_MUTATED",
            ),
            value.target_phase,
            _rebuild_phase_binding(
                value.phase_binding,
                "DIRECT_BACKEND_REQUEST_MUTATED",
            ),
        )
    if type(value) is TZeroBackendNodeRequest:
        if (
            type(value.feature_id) is not str
            or type(value.phase_one) is not str
            or type(value.phase_two) is not str
        ):
            _fail("DIRECT_BACKEND_REQUEST_MUTATED")
        return TZeroBackendNodeRequest(
            _rebuild_identity(value.identity, "DIRECT_BACKEND_REQUEST_MUTATED"),
            value.feature_id,
            _rebuild_node_key(value.key, "DIRECT_BACKEND_REQUEST_MUTATED"),
            _rebuild_equilibrium_request(
                value.state,
                "DIRECT_BACKEND_REQUEST_MUTATED",
            ),
            value.phase_one,
            value.phase_two,
            _exact_canonical_float(
                value.minimum_temperature_k,
                "DIRECT_BACKEND_REQUEST_MUTATED",
            ),
            _exact_canonical_float(
                value.maximum_temperature_k,
                "DIRECT_BACKEND_REQUEST_MUTATED",
            ),
            _rebuild_phase_binding(
                value.phase_binding,
                "DIRECT_BACKEND_REQUEST_MUTATED",
            ),
        )
    _fail("DIRECT_BACKEND_REQUEST_MUTATED")


def _rebuild_backend_node_request(value: object):
    try:
        return _rebuild_backend_node_request_unchecked(value)
    except AttributeError as error:
        raise DirectAdapterError("DIRECT_BACKEND_REQUEST_MUTATED") from error


def _backend_node_snapshot(value: object) -> tuple[object, ...]:
    common = (
        value.feature_id,
        _identity_snapshot(value.identity),
        _node_key_snapshot(value.key),
        _phase_binding_snapshot(value.phase_binding),
    )
    if type(value) is EquilibriumBackendNodeRequest:
        return common + (_equilibrium_request_snapshot(value.equilibrium),)
    if type(value) is PhaseGibbsBackendNodeRequest:
        return common + (
            _equilibrium_request_snapshot(value.state),
            value.phase,
        )
    if type(value) is PhaseDrivingForceBackendNodeRequest:
        return common + (
            _equilibrium_request_snapshot(value.reference_state),
            value.target_phase,
        )
    if type(value) is TZeroBackendNodeRequest:
        return common + (
            _equilibrium_request_snapshot(value.state),
            value.phase_one,
            value.phase_two,
            value.minimum_temperature_k.hex(),
            value.maximum_temperature_k.hex(),
        )
    _fail("DIRECT_BACKEND_REQUEST_MUTATED")


def _node_origin(
    direct_request: object,
    backend_node_request: object,
) -> DirectNodeOrigin:
    return _node_origin_from_request_origin(
        DirectRequestOrigin(_direct_request_snapshot(direct_request)),
        backend_node_request,
    )


def _node_origin_from_request_origin(
    request_origin: DirectRequestOrigin,
    backend_node_request: object,
) -> DirectNodeOrigin:
    return DirectNodeOrigin(
        request_origin,
        _backend_node_snapshot(
            _rebuild_backend_node_request(backend_node_request)
        ),
    )


def _assert_backend_request_unchanged(
    outbound: object,
    expected_type: type,
    snapshot: tuple[object, ...],
) -> None:
    try:
        if type(outbound) is not expected_type:
            _fail("DIRECT_BACKEND_REQUEST_MUTATED")
        current = _rebuild_backend_node_request(outbound)
        current_snapshot = _backend_node_snapshot(current)
    except (AttributeError, DirectAdapterError) as error:
        raise DirectAdapterError("DIRECT_BACKEND_REQUEST_MUTATED") from error
    if current_snapshot != snapshot:
        _fail("DIRECT_BACKEND_REQUEST_MUTATED")


def _invoke_backend(
    method: object,
    node_request: object,
    caller_request: object,
    caller_type: type,
    caller_snapshot: tuple[object, ...],
):
    _assert_caller_request_unchanged(
        caller_request,
        caller_type,
        caller_snapshot,
    )
    canonical_node = _rebuild_backend_node_request(node_request)
    outbound_snapshot = _backend_node_snapshot(canonical_node)
    outbound = _rebuild_backend_node_request(canonical_node)
    try:
        return method(outbound)
    finally:
        _assert_backend_request_unchanged(
            outbound,
            type(canonical_node),
            outbound_snapshot,
        )
        _assert_caller_request_unchanged(
            caller_request,
            caller_type,
            caller_snapshot,
        )


def _backend_method(backend: object, name: str):
    method = getattr(backend, name, None)
    if not callable(method):
        _fail("DIRECT_BACKEND_INVALID")
    return method


def _checked_backend_method(
    backend: object,
    name: str,
    caller_request: object,
    caller_type: type,
    caller_snapshot: tuple[object, ...],
):
    try:
        return _backend_method(backend, name)
    finally:
        _assert_caller_request_unchanged(
            caller_request,
            caller_type,
            caller_snapshot,
        )


def _validate_reply_binding_unchecked(
    reply: object,
    expected_type: type,
    identity: DatabaseProfileIdentity,
    feature_id: str,
    key: DirectNodeKey,
    phase_binding: PhaseSetBinding,
):
    if type(reply) is not expected_type or type(reply.feature_id) is not str:
        _fail("DIRECT_BACKEND_REPLY_INVALID")
    if expected_type is EquilibriumBackendReply:
        canonical_reply = EquilibriumBackendReply(
            _rebuild_identity(reply.identity, "DIRECT_BACKEND_REPLY_INVALID"),
            reply.feature_id,
            _rebuild_node_key(reply.key, "DIRECT_BACKEND_REPLY_INVALID"),
            _rebuild_phase_binding(
                reply.phase_binding,
                "DIRECT_BACKEND_REPLY_INVALID",
            ),
            _rebuild_raw_result(
                reply.raw_result,
                "DIRECT_BACKEND_REPLY_INVALID",
            ),
        )
    elif expected_type is ScalarBackendReply:
        canonical_reply = ScalarBackendReply(
            _rebuild_identity(reply.identity, "DIRECT_BACKEND_REPLY_INVALID"),
            reply.feature_id,
            _rebuild_node_key(reply.key, "DIRECT_BACKEND_REPLY_INVALID"),
            _rebuild_phase_binding(
                reply.phase_binding,
                "DIRECT_BACKEND_REPLY_INVALID",
            ),
            _binary64(reply.value),
        )
    else:
        _fail("DIRECT_BACKEND_REPLY_INVALID")
    if not _identity_fields_same(canonical_reply.identity, identity):
        _fail("DIRECT_BACKEND_IDENTITY_MISMATCH")
    if canonical_reply.feature_id != feature_id:
        _fail("DIRECT_BACKEND_FEATURE_MISMATCH")
    if not _node_key_fields_same(canonical_reply.key, key):
        _fail("DIRECT_BACKEND_NODE_MISMATCH")
    if not _phase_binding_fields_same(canonical_reply.phase_binding, phase_binding):
        _fail("DIRECT_BACKEND_PHASE_BINDING_MISMATCH")
    return canonical_reply


def _validate_reply_binding(
    reply: object,
    expected_type: type,
    identity: DatabaseProfileIdentity,
    feature_id: str,
    key: DirectNodeKey,
    phase_binding: PhaseSetBinding,
):
    try:
        return _validate_reply_binding_unchecked(
            reply,
            expected_type,
            identity,
            feature_id,
            key,
            phase_binding,
        )
    except AttributeError as error:
        raise DirectAdapterError("DIRECT_BACKEND_REPLY_INVALID") from error


def _equilibrium_outputs(result: EquilibriumResult) -> tuple[tuple[str, float], ...]:
    return tuple(
        (f"PHASE_FRACTION:{phase.phase}", phase.phase_fraction)
        for phase in result.phases
    )


def _outputs_fields_same(left: object, right: object) -> bool:
    if type(left) is not tuple or type(right) is not tuple or len(left) != len(right):
        return False
    for left_pair, right_pair in zip(left, right):
        if (
            type(left_pair) is not tuple
            or type(right_pair) is not tuple
            or len(left_pair) != 2
            or len(right_pair) != 2
            or type(left_pair[0]) is not str
            or type(right_pair[0]) is not str
            or type(left_pair[1]) is not float
            or type(right_pair[1]) is not float
            or left_pair[0] != right_pair[0]
            or left_pair[1].hex() != right_pair[1].hex()
        ):
            return False
    return True


def _key_label(value: DirectNodeKey, name: str) -> str | None:
    for label_name, label_value in value.labels:
        if label_name == name:
            return label_value
    return None


def _float_fields_same(left: object, right: object) -> bool:
    return (
        type(left) is float
        and type(right) is float
        and left.hex() == right.hex()
    )


def _coordinate_schema(
    key: DirectNodeKey,
    names: tuple[str, ...],
) -> bool:
    coordinates = key.node.coordinates
    return (
        len(coordinates) == len(names)
        and tuple(name for name, _value in coordinates) == names
    )


def _scalar_node_schema_valid(
    feature_id: str,
    key: DirectNodeKey,
    phase_binding: PhaseSetBinding,
) -> bool:
    if feature_id == "phase_gibbs_energy":
        if (
            not _coordinate_schema(
                key,
                ("TEMPERATURE_K", "PHASE_ORDINAL"),
            )
            or len(key.labels) != 1
            or key.labels[0][0] != "PHASE"
            or len(phase_binding.effective_phases) != 1
            or key.labels[0][1] != phase_binding.effective_phases[0]
        ):
            return False
        temperature = key.node.coordinates[0][1]
        phase_ordinal = key.node.coordinates[1][1]
        return (
            temperature > 0.0
            and phase_ordinal >= 0.0
            and phase_ordinal.is_integer()
        )
    if feature_id == "phase_driving_force":
        if (
            not _coordinate_schema(key, ("TEMPERATURE_K",))
            or len(key.labels) != 1
            or key.labels[0][0] != "TARGET_PHASE"
        ):
            return False
        target = key.labels[0][1]
        return (
            key.node.coordinates[0][1] > 0.0
            and target not in phase_binding.effective_phases
            and target in phase_binding.explicit_exclusions
        )
    if feature_id == "tzero_temperature":
        if (
            len(key.node.coordinates) != 1
            or not key.node.coordinates[0][0].startswith("X_")
            or len(key.node.coordinates[0][0]) <= 2
            or key.node.coordinates[0][0] == "X_VA"
            or len(key.labels) != 2
            or key.labels[0][0] != "PHASE_ONE"
            or key.labels[1][0] != "PHASE_TWO"
        ):
            return False
        first = key.labels[0][1]
        second = key.labels[1][1]
        return (
            first != second
            and key.node.coordinates[0][1] <= 1.0
            and _string_tuple_fields_same(
                phase_binding.effective_phases,
                (first, second),
            )
        )
    return False


def _binding_rows_same(nodes: tuple[DirectNodeResult, ...]) -> bool:
    first = nodes[0].phase_binding
    return all(
        _phase_binding_fields_same(first, row.phase_binding)
        for row in nodes[1:]
    )


def _strict_axis(values: tuple[float, ...]) -> bool:
    return all(
        values[index - 1] < values[index]
        for index in range(1, len(values))
    )


def _pass_equilibrium_key_matches(
    row: DirectNodeResult,
    mode: str,
) -> bool:
    if row.outcome == "FAIL":
        return True
    equilibrium = row.equilibrium
    if equilibrium is None:
        return False
    request = equilibrium.request
    coordinates = row.key.node.coordinates
    if mode == "temperature":
        return _float_fields_same(coordinates[0][1], request.temperature_k)
    if mode == "composition":
        component = coordinates[0][0][2:]
        for name, value in request.composition:
            if name == component:
                return _float_fields_same(coordinates[0][1], value)
        return False
    if mode == "ternary":
        composition = dict(request.composition)
        coordinate_components = tuple(name[2:] for name, _value in coordinates)
        if any(component not in composition for component in coordinate_components):
            return False
        if any(
            not _float_fields_same(value, composition[name[2:]])
            for name, value in coordinates
        ):
            return False
        return all(
            component in coordinate_components or value == 0.0
            for component, value in request.composition
        )
    return False


def _equilibrium_scan_rows_valid(
    feature_id: str,
    nodes: tuple[DirectNodeResult, ...],
) -> bool:
    if not _binding_rows_same(nodes):
        return False
    if feature_id == "equilibrium_single":
        return (
            len(nodes) == 1
            and not nodes[0].key.labels
            and _coordinate_schema(nodes[0].key, ("TEMPERATURE_K",))
            and nodes[0].key.node.coordinates[0][1] > 0.0
            and _pass_equilibrium_key_matches(nodes[0], "temperature")
        )
    if feature_id == "manual_phase_selection_metastable":
        return (
            len(nodes) == 1
            and nodes[0].key.labels
            == (("SELECTION_MODE", "MANUAL_METASTABLE"),)
            and _coordinate_schema(nodes[0].key, ("TEMPERATURE_K",))
            and nodes[0].key.node.coordinates[0][1] > 0.0
            and _pass_equilibrium_key_matches(nodes[0], "temperature")
        )
    if feature_id == "equilibrium_temperature_scan":
        if any(
            row.key.labels
            or not _coordinate_schema(row.key, ("TEMPERATURE_K",))
            or not _pass_equilibrium_key_matches(row, "temperature")
            for row in nodes
        ):
            return False
        temperatures = tuple(row.key.node.coordinates[0][1] for row in nodes)
        if not _strict_axis(temperatures):
            return False
        state_snapshots = tuple(
            (
                row.equilibrium.request.pressure_pa.hex(),
                row.equilibrium.request.components,
                row.equilibrium.request.phases,
                tuple(
                    (name, value.hex())
                    for name, value in row.equilibrium.request.composition
                ),
            )
            for row in nodes
            if row.outcome == "PASS"
        )
        return not state_snapshots or all(
            snapshot == state_snapshots[0]
            for snapshot in state_snapshots[1:]
        )
    if feature_id == "equilibrium_composition_scan":
        first_name = nodes[0].key.node.coordinates[0][0]
        if (
            not first_name.startswith("X_")
            or len(first_name) <= 2
            or first_name == "X_VA"
        ):
            return False
        if any(
            row.key.labels
            or not _coordinate_schema(row.key, (first_name,))
            or not _pass_equilibrium_key_matches(row, "composition")
            for row in nodes
        ):
            return False
        fractions = tuple(row.key.node.coordinates[0][1] for row in nodes)
        if any(fraction > 1.0 for fraction in fractions) or not _strict_axis(fractions):
            return False
        state_snapshots = tuple(
            (
                row.equilibrium.request.temperature_k.hex(),
                row.equilibrium.request.pressure_pa.hex(),
                row.equilibrium.request.components,
                row.equilibrium.request.phases,
            )
            for row in nodes
            if row.outcome == "PASS"
        )
        return not state_snapshots or all(
            snapshot == state_snapshots[0]
            for snapshot in state_snapshots[1:]
        )
    return False


def _ternary_rows_valid(nodes: tuple[DirectNodeResult, ...]) -> bool:
    count = len(nodes)
    discriminant = 8 * count + 1
    root = _math.isqrt(discriminant)
    if root * root != discriminant or (root - 3) % 2 or root < 7:
        return False
    interval_count = (root - 3) // 2
    names = tuple(name for name, _value in nodes[0].key.node.coordinates)
    if (
        len(names) != 3
        or len(set(names)) != 3
        or any(not name.startswith("X_") or name == "X_VA" for name in names)
        or len(nodes[0].key.labels) != 1
        or nodes[0].key.labels[0][0] != "TARGET_PHASE"
        or not _binding_rows_same(nodes)
    ):
        return False
    target = nodes[0].key.labels[0][1]
    expected: list[tuple[float, float, float]] = []
    for second_index in range(interval_count + 1):
        second = _canonical_ternary_fraction(second_index / interval_count)
        for third_index in range(interval_count - second_index + 1):
            third = _canonical_ternary_fraction(third_index / interval_count)
            first = _canonical_ternary_fraction(1.0 - second - third)
            expected.append((first, second, third))
    if len(expected) != count:
        return False
    for row, expected_values in zip(nodes, expected):
        if (
            tuple(name for name, _value in row.key.node.coordinates) != names
            or row.key.labels != (("TARGET_PHASE", target),)
            or any(
                not _float_fields_same(observed[1], wanted)
                for observed, wanted in zip(
                    row.key.node.coordinates,
                    expected_values,
                )
            )
            or not _pass_equilibrium_key_matches(row, "ternary")
        ):
            return False
    state_snapshots = tuple(
        (
            row.equilibrium.request.temperature_k.hex(),
            row.equilibrium.request.pressure_pa.hex(),
            row.equilibrium.request.components,
            row.equilibrium.request.phases,
        )
        for row in nodes
        if row.outcome == "PASS"
    )
    return not state_snapshots or all(
        snapshot == state_snapshots[0]
        for snapshot in state_snapshots[1:]
    )


def _gibbs_rows_valid(nodes: tuple[DirectNodeResult, ...]) -> bool:
    if any(
        not _scalar_node_schema_valid(
            row.feature_id,
            row.key,
            row.phase_binding,
        )
        for row in nodes
    ):
        return False
    first_temperature = nodes[0].key.node.coordinates[0][1]
    phase_count = 0
    for row in nodes:
        if not _float_fields_same(
            row.key.node.coordinates[0][1],
            first_temperature,
        ):
            break
        phase_count += 1
    if phase_count < 1 or len(nodes) % phase_count:
        return False
    cycle = nodes[:phase_count]
    phases = tuple(row.key.labels[0][1] for row in cycle)
    if len(set(phases)) != len(phases):
        return False
    universe = cycle[0].phase_binding.phase_universe
    if any(
        not _string_tuple_fields_same(
            row.phase_binding.phase_universe,
            universe,
        )
        for row in cycle[1:]
    ):
        return False
    selected = set(phases)
    if phases != tuple(phase for phase in universe if phase in selected):
        return False
    previous_temperature: float | None = None
    for block_start in range(0, len(nodes), phase_count):
        block = nodes[block_start:block_start + phase_count]
        temperature = block[0].key.node.coordinates[0][1]
        if previous_temperature is not None and temperature <= previous_temperature:
            return False
        previous_temperature = temperature
        for phase_index, row in enumerate(block):
            if (
                not _float_fields_same(
                    row.key.node.coordinates[0][1],
                    temperature,
                )
                or not _float_fields_same(
                    row.key.node.coordinates[1][1],
                    float(phase_index),
                )
                or row.key.labels[0][1] != phases[phase_index]
                or not _phase_binding_fields_same(
                    row.phase_binding,
                    cycle[phase_index].phase_binding,
                )
            ):
                return False
    return True


def _scalar_scan_rows_valid(
    feature_id: str,
    nodes: tuple[DirectNodeResult, ...],
) -> bool:
    if any(
        not _scalar_node_schema_valid(feature_id, row.key, row.phase_binding)
        for row in nodes
    ):
        return False
    if feature_id == "phase_gibbs_energy":
        return _gibbs_rows_valid(nodes)
    if not _binding_rows_same(nodes):
        return False
    if feature_id == "phase_driving_force":
        target = nodes[0].key.labels[0][1]
        if any(row.key.labels != (("TARGET_PHASE", target),) for row in nodes):
            return False
        return _strict_axis(
            tuple(row.key.node.coordinates[0][1] for row in nodes)
        )
    if feature_id == "tzero_temperature":
        labels = nodes[0].key.labels
        axis_name = nodes[0].key.node.coordinates[0][0]
        if any(
            row.key.labels != labels
            or row.key.node.coordinates[0][0] != axis_name
            for row in nodes
        ):
            return False
        return _strict_axis(
            tuple(row.key.node.coordinates[0][1] for row in nodes)
        )
    return False


def _equilibrium_requests_same(left: object, right: object) -> bool:
    try:
        rebuilt_left = _rebuild_equilibrium_request(
            left,
            "DIRECT_RESULT_INVALID",
        )
        rebuilt_right = _rebuild_equilibrium_request(
            right,
            "DIRECT_RESULT_INVALID",
        )
        return (
            _equilibrium_request_snapshot(rebuilt_left)
            == _equilibrium_request_snapshot(rebuilt_right)
        )
    except (AttributeError, DirectAdapterError):
        return False


def _row_key_matches(
    row: DirectNodeResult,
    coordinates: tuple[tuple[str, float], ...],
    labels: tuple[tuple[str, str], ...],
) -> bool:
    if (
        not _node_key_fields_valid(row.key)
        or len(row.key.node.coordinates) != len(coordinates)
        or len(row.key.labels) != len(labels)
    ):
        return False
    for observed, expected in zip(row.key.node.coordinates, coordinates):
        if (
            observed[0] != expected[0]
            or not _float_fields_same(observed[1], expected[1])
        ):
            return False
    return all(
        observed[0] == expected[0] and observed[1] == expected[1]
        for observed, expected in zip(row.key.labels, labels)
    )


def _row_equilibrium_matches(
    row: DirectNodeResult,
    expected: EquilibriumRequest,
) -> bool:
    if row.outcome == "FAIL":
        return True
    return (
        row.equilibrium is not None
        and _equilibrium_requests_same(row.equilibrium.request, expected)
    )


def _rows_use_binding(
    rows: tuple[DirectNodeResult, ...],
    expected: PhaseSetBinding,
) -> bool:
    return all(
        _phase_binding_fields_same(row.phase_binding, expected)
        for row in rows
    )


def _request_bound_equilibrium_rows_valid(
    feature_id: str,
    nodes: tuple[DirectNodeResult, ...],
    request: object,
) -> bool:
    if feature_id == "equilibrium_single":
        if type(request) is not EquilibriumSingleRequest or len(nodes) != 1:
            return False
        binding = _phase_binding_from_effective(
            request.equilibrium.phases,
            request.explicit_exclusions,
        )
        return (
            _rows_use_binding(nodes, binding)
            and _row_key_matches(
                nodes[0],
                (("TEMPERATURE_K", request.equilibrium.temperature_k),),
                tuple(),
            )
            and _row_equilibrium_matches(nodes[0], request.equilibrium)
        )
    if feature_id == "manual_phase_selection_metastable":
        if type(request) is not ManualPhaseSelectionRequest or len(nodes) != 1:
            return False
        binding = PhaseSetBinding(
            request.available_phases,
            request.selected_phases,
            request.explicit_exclusions,
        )
        return (
            _rows_use_binding(nodes, binding)
            and _row_key_matches(
                nodes[0],
                (("TEMPERATURE_K", request.equilibrium.temperature_k),),
                (("SELECTION_MODE", "MANUAL_METASTABLE"),),
            )
            and _row_equilibrium_matches(nodes[0], request.equilibrium)
        )
    if feature_id == "equilibrium_temperature_scan":
        if (
            type(request) is not EquilibriumTemperatureScanRequest
            or len(nodes) != len(request.temperatures_k)
        ):
            return False
        binding = _phase_binding_from_effective(
            request.base_equilibrium.phases,
            request.explicit_exclusions,
        )
        if not _rows_use_binding(nodes, binding):
            return False
        for row, temperature in zip(nodes, request.temperatures_k):
            expected = _state_at_temperature(
                request.base_equilibrium,
                temperature,
            )
            if (
                not _row_key_matches(
                    row,
                    (("TEMPERATURE_K", temperature),),
                    tuple(),
                )
                or not _row_equilibrium_matches(row, expected)
            ):
                return False
        return True
    if feature_id == "equilibrium_composition_scan":
        if (
            type(request) is not EquilibriumCompositionScanRequest
            or len(nodes) != len(request.fractions)
        ):
            return False
        binding = _phase_binding_from_effective(
            request.base_equilibrium.phases,
            request.explicit_exclusions,
        )
        if not _rows_use_binding(nodes, binding):
            return False
        axis_name = _composition_coordinate_name(request.varying_component)
        expected_states = _composition_states(
            request.base_equilibrium,
            request.varying_component,
            request.balance_component,
            request.fractions,
        )
        if len(expected_states) != len(nodes):
            return False
        for row, fraction, expected in zip(
            nodes,
            request.fractions,
            expected_states,
        ):
            if (
                not _row_key_matches(
                    row,
                    ((axis_name, fraction),),
                    tuple(),
                )
                or not _row_equilibrium_matches(row, expected)
            ):
                return False
        return True
    return False


def _request_bound_ternary_rows_valid(
    nodes: tuple[DirectNodeResult, ...],
    request: object,
) -> bool:
    if type(request) is not TernaryPhaseFractionMapRequest:
        return False
    expected_count = (
        (request.interval_count + 1) * (request.interval_count + 2) // 2
    )
    if len(nodes) != expected_count:
        return False
    first, second, third = request.ternary_components
    coordinate_names = tuple(
        _composition_coordinate_name(component)
        for component in (first, second, third)
    )
    binding = _phase_binding_from_effective(
        request.phases,
        request.explicit_exclusions,
    )
    if not _rows_use_binding(nodes, binding):
        return False
    ordinal = 0
    for second_index in range(request.interval_count + 1):
        second_fraction = _canonical_ternary_fraction(
            second_index / request.interval_count
        )
        for third_index in range(
            request.interval_count - second_index + 1
        ):
            third_fraction = _canonical_ternary_fraction(
                third_index / request.interval_count
            )
            first_fraction = _canonical_ternary_fraction(
                1.0 - second_fraction - third_fraction
            )
            values = {
                first: first_fraction,
                second: second_fraction,
                third: third_fraction,
            }
            expected_coordinates = tuple(
                (name, values[component])
                for name, component in zip(
                    coordinate_names,
                    (first, second, third),
                )
            )
            expected_composition = tuple(
                (component, values.get(component, 0.0))
                for component in request.components
            )
            expected_state = EquilibriumRequest(
                request.temperature_k,
                request.pressure_pa,
                request.components,
                request.phases,
                expected_composition,
            )
            row = nodes[ordinal]
            if (
                not _row_key_matches(
                    row,
                    expected_coordinates,
                    (("TARGET_PHASE", request.target_phase),),
                )
                or not _row_equilibrium_matches(row, expected_state)
            ):
                return False
            ordinal += 1
    return ordinal == expected_count


def _request_bound_scalar_rows_valid(
    feature_id: str,
    nodes: tuple[DirectNodeResult, ...],
    request: object,
) -> bool:
    if feature_id == "phase_gibbs_energy":
        if type(request) is not PhaseGibbsEnergyRequest:
            return False
        phases = request.base_equilibrium.phases
        expected_count = len(request.temperatures_k) * len(phases)
        if len(nodes) != expected_count:
            return False
        ordinal = 0
        for temperature in request.temperatures_k:
            for phase_index, phase in enumerate(phases):
                row = nodes[ordinal]
                if (
                    not _row_key_matches(
                        row,
                        (
                            ("TEMPERATURE_K", temperature),
                            ("PHASE_ORDINAL", float(phase_index)),
                        ),
                        (("PHASE", phase),),
                    )
                    or not _phase_binding_fields_same(
                        row.phase_binding,
                        request.phase_isolations[phase_index],
                    )
                ):
                    return False
                ordinal += 1
        return ordinal == expected_count
    if feature_id == "phase_driving_force":
        if (
            type(request) is not PhaseDrivingForceRequest
            or len(nodes) != len(request.temperatures_k)
        ):
            return False
        binding = _phase_binding_from_effective(
            request.reference_equilibrium.phases,
            request.explicit_exclusions,
        )
        if not _rows_use_binding(nodes, binding):
            return False
        return all(
            _row_key_matches(
                row,
                (("TEMPERATURE_K", temperature),),
                (("TARGET_PHASE", request.target_phase),),
            )
            for row, temperature in zip(nodes, request.temperatures_k)
        )
    if feature_id == "tzero_temperature":
        if (
            type(request) is not TZeroTemperatureRequest
            or len(nodes) != len(request.fractions)
        ):
            return False
        binding = _phase_binding_from_effective(
            request.base_equilibrium.phases,
            request.explicit_exclusions,
        )
        if not _rows_use_binding(nodes, binding):
            return False
        axis_name = _composition_coordinate_name(request.varying_component)
        labels = (
            ("PHASE_ONE", request.phase_one),
            ("PHASE_TWO", request.phase_two),
        )
        for row, fraction in zip(nodes, request.fractions):
            if not _row_key_matches(
                row,
                ((axis_name, fraction),),
                labels,
            ):
                return False
            if row.outcome == "PASS":
                value = row.outputs[0][1]
                if not (
                    value > 0.0
                    and request.minimum_temperature_k
                    <= value
                    <= request.maximum_temperature_k
                ):
                    return False
        return True
    return False


def _feature_result_rows_valid(
    feature_id: str,
    nodes: tuple[DirectNodeResult, ...],
    request: object,
) -> bool:
    try:
        if feature_id in (
            "equilibrium_single",
            "equilibrium_temperature_scan",
            "equilibrium_composition_scan",
            "manual_phase_selection_metastable",
        ):
            return _request_bound_equilibrium_rows_valid(
                feature_id,
                nodes,
                request,
            )
        if feature_id == "ternary_phase_fraction_map":
            return _request_bound_ternary_rows_valid(nodes, request)
        return _request_bound_scalar_rows_valid(
            feature_id,
            nodes,
            request,
        )
    except (
        AttributeError,
        DirectAdapterError,
        IndexError,
        KeyError,
        NumericalAdapterError,
    ):
        return False


def _equilibrium_node_outputs(
    feature_id: str,
    key: DirectNodeKey,
    equilibrium: EquilibriumResult,
) -> tuple[tuple[str, float], ...]:
    outputs = _equilibrium_outputs(equilibrium)
    if feature_id != "ternary_phase_fraction_map":
        return outputs
    target = _key_label(key, "TARGET_PHASE")
    if type(target) is not str:
        _fail("DIRECT_RESULT_INVALID")
    target_fraction = 0.0
    for phase in equilibrium.phases:
        if phase.phase == target:
            target_fraction = phase.phase_fraction
            break
    return tuple(sorted(outputs + (("TARGET_PHASE_FRACTION", target_fraction),)))


def _pass_payload_coherent(
    feature_id: str,
    key: DirectNodeKey,
    phase_binding: PhaseSetBinding,
    equilibrium: EquilibriumResult | None,
    outputs: tuple[tuple[str, float], ...],
) -> bool:
    if feature_id in _EQUILIBRIUM_OUTPUT_FEATURES:
        if (
            equilibrium is None
            or not _equilibrium_result_fields_valid(equilibrium)
            or not _string_tuple_fields_same(
                equilibrium.request.phases,
                phase_binding.effective_phases,
            )
        ):
            return False
        expected = _equilibrium_node_outputs(feature_id, key, equilibrium)
        if feature_id == "ternary_phase_fraction_map":
            target = _key_label(key, "TARGET_PHASE")
            if type(target) is not str or target not in phase_binding.effective_phases:
                return False
        return _outputs_fields_same(outputs, expected)
    scalar_name = _SCALAR_OUTPUT_NAMES.get(feature_id)
    return (
        type(scalar_name) is str
        and equilibrium is None
        and len(outputs) == 1
        and outputs[0][0] == scalar_name
        and type(outputs[0][1]) is float
        and (
            feature_id != "tzero_temperature"
            or outputs[0][1] > 0.0
        )
    )


def _failed_row(
    identity: DatabaseProfileIdentity,
    feature_id: str,
    key: DirectNodeKey,
    phase_binding: PhaseSetBinding,
    origin: DirectNodeOrigin,
    error: ExpectedDirectNodeFailure,
    allowed_reasons: frozenset[str],
) -> DirectNodeResult:
    try:
        if (
            type(error) is not ExpectedDirectNodeFailure
            or type(error.reason_code) is not str
            or error.reason_code not in allowed_reasons
        ):
            _fail("DIRECT_BACKEND_REPLY_INVALID")
        return DirectNodeResult(
            identity,
            feature_id,
            key,
            phase_binding,
            "FAIL",
            error.reason_code,
            None,
            tuple(),
            origin,
        )
    except AttributeError as missing:
        raise DirectAdapterError("DIRECT_BACKEND_REPLY_INVALID") from missing


def _finish(
    feature_id: str,
    identity: DatabaseProfileIdentity,
    request: object,
    rows: tuple[DirectNodeResult, ...],
) -> DirectFeatureResult:
    failures = tuple(
        FailedDirectNode(
            row.identity,
            row.feature_id,
            row.key,
            row.phase_binding,
            row.reason_code,
            row.origin,
        )
        for row in rows
        if row.outcome == "FAIL"
    )
    return DirectFeatureResult(
        feature_id=feature_id,
        identity=identity,
        nodes=rows,
        failed_nodes=failures,
        requested_nodes=len(rows),
        pass_count=sum(row.outcome == "PASS" for row in rows),
        fail_count=len(failures),
        request=request,
    )


def _execute_equilibrium_nodes(
    identity: DatabaseProfileIdentity,
    feature_id: str,
    result_request: object,
    nodes: tuple[EquilibriumBackendNodeRequest, ...],
    backend: object,
    caller_request: object,
    caller_type: type,
    caller_snapshot: tuple[object, ...],
) -> DirectFeatureResult:
    solve = _checked_backend_method(
        backend,
        "solve_equilibrium",
        caller_request,
        caller_type,
        caller_snapshot,
    )
    rows: list[DirectNodeResult] = []
    request_origin = DirectRequestOrigin(
        _direct_request_snapshot(result_request)
    )
    for node_request in nodes:
        origin = _node_origin_from_request_origin(
            request_origin,
            node_request,
        )
        try:
            raw_reply = _invoke_backend(
                solve,
                node_request,
                caller_request,
                caller_type,
                caller_snapshot,
            )
        except ExpectedDirectNodeFailure as error:
            rows.append(
                _failed_row(
                    identity,
                    feature_id,
                    node_request.key,
                    node_request.phase_binding,
                    origin,
                    error,
                    _EQUILIBRIUM_NODE_REASONS,
                )
            )
        else:
            reply = _validate_reply_binding(
                raw_reply,
                EquilibriumBackendReply,
                identity,
                feature_id,
                node_request.key,
                node_request.phase_binding,
            )
            equilibrium = evaluate_equilibrium(
                node_request.equilibrium,
                _RawReplyBackend(reply.raw_result),
            )
            rows.append(
                DirectNodeResult(
                    identity,
                    feature_id,
                    node_request.key,
                    node_request.phase_binding,
                    "PASS",
                    "DIRECT_NODE_OK",
                    equilibrium,
                    _equilibrium_node_outputs(
                        feature_id,
                        node_request.key,
                        equilibrium,
                    ),
                    origin,
                )
            )
    result = _finish(feature_id, identity, result_request, tuple(rows))
    _assert_caller_request_unchanged(
        caller_request,
        caller_type,
        caller_snapshot,
    )
    return result


def _state_at_temperature(base: EquilibriumRequest, temperature_k: float, phases: tuple[str, ...] | None = None) -> EquilibriumRequest:
    return EquilibriumRequest(
        temperature_k=temperature_k,
        pressure_pa=base.pressure_pa,
        components=base.components,
        phases=base.phases if phases is None else phases,
        composition=base.composition,
    )


def _composition_states(
    base: EquilibriumRequest,
    varying: str,
    balance: str,
    fractions: tuple[float, ...],
) -> tuple[EquilibriumRequest, ...]:
    base_values = dict(base.composition)
    fixed_total = _math.fsum(
        base_values[component]
        for component in base.components
        if component not in (varying, balance)
    )
    states: list[EquilibriumRequest] = []
    for fraction in fractions:
        balance_value = 1.0 - fixed_total - fraction
        if balance_value < 0.0 and balance_value >= -1.0e-12:
            balance_value = 0.0
        composition = tuple(
            (
                component,
                fraction
                if component == varying
                else balance_value
                if component == balance
                else base_values[component],
            )
            for component in base.components
        )
        states.append(
            EquilibriumRequest(
                base.temperature_k,
                base.pressure_pa,
                base.components,
                base.phases,
                composition,
            )
        )
    return tuple(states)


def _deterministic_backend_nodes(request: object) -> tuple[object, ...]:
    if type(request) is EquilibriumSingleRequest:
        key = DirectNodeKey(
            GridNode(
                0,
                (("TEMPERATURE_K", request.equilibrium.temperature_k),),
            )
        )
        return (
            EquilibriumBackendNodeRequest(
                request.identity,
                request.feature_id,
                key,
                request.equilibrium,
                _phase_binding_from_effective(
                    request.equilibrium.phases,
                    request.explicit_exclusions,
                ),
            ),
        )
    if type(request) is EquilibriumTemperatureScanRequest:
        grid = build_cartesian_nodes(
            (build_axis("TEMPERATURE_K", request.temperatures_k),),
            max_nodes=request.max_nodes,
        )
        binding = _phase_binding_from_effective(
            request.base_equilibrium.phases,
            request.explicit_exclusions,
        )
        return tuple(
            EquilibriumBackendNodeRequest(
                request.identity,
                request.feature_id,
                DirectNodeKey(grid_node),
                _state_at_temperature(
                    request.base_equilibrium,
                    grid_node.coordinates[0][1],
                ),
                binding,
            )
            for grid_node in grid
        )
    if type(request) is EquilibriumCompositionScanRequest:
        grid = build_cartesian_nodes(
            (
                build_axis(
                    _composition_coordinate_name(
                        request.varying_component
                    ),
                    request.fractions,
                ),
            ),
            max_nodes=request.max_nodes,
        )
        states = _composition_states(
            request.base_equilibrium,
            request.varying_component,
            request.balance_component,
            request.fractions,
        )
        binding = _phase_binding_from_effective(
            request.base_equilibrium.phases,
            request.explicit_exclusions,
        )
        return tuple(
            EquilibriumBackendNodeRequest(
                request.identity,
                request.feature_id,
                DirectNodeKey(grid_node),
                state,
                binding,
            )
            for grid_node, state in zip(grid, states)
        )
    if type(request) is TernaryPhaseFractionMapRequest:
        first, second, third = request.ternary_components
        binding = _phase_binding_from_effective(
            request.phases,
            request.explicit_exclusions,
        )
        nodes: list[EquilibriumBackendNodeRequest] = []
        ordinal = 0
        for second_index in range(request.interval_count + 1):
            second_fraction = _canonical_ternary_fraction(
                second_index / request.interval_count
            )
            for third_index in range(
                request.interval_count - second_index + 1
            ):
                third_fraction = _canonical_ternary_fraction(
                    third_index / request.interval_count
                )
                first_fraction = _canonical_ternary_fraction(
                    1.0 - second_fraction - third_fraction
                )
                values = {
                    first: first_fraction,
                    second: second_fraction,
                    third: third_fraction,
                }
                state = EquilibriumRequest(
                    request.temperature_k,
                    request.pressure_pa,
                    request.components,
                    request.phases,
                    tuple(
                        (component, values.get(component, 0.0))
                        for component in request.components
                    ),
                )
                key = DirectNodeKey(
                    GridNode(
                        ordinal,
                        (
                            (
                                _composition_coordinate_name(first),
                                values[first],
                            ),
                            (
                                _composition_coordinate_name(second),
                                values[second],
                            ),
                            (
                                _composition_coordinate_name(third),
                                values[third],
                            ),
                        ),
                    ),
                    (("TARGET_PHASE", request.target_phase),),
                )
                nodes.append(
                    EquilibriumBackendNodeRequest(
                        request.identity,
                        request.feature_id,
                        key,
                        state,
                        binding,
                    )
                )
                ordinal += 1
        return tuple(nodes)
    if type(request) is ManualPhaseSelectionRequest:
        key = DirectNodeKey(
            GridNode(
                0,
                (("TEMPERATURE_K", request.equilibrium.temperature_k),),
            ),
            (("SELECTION_MODE", "MANUAL_METASTABLE"),),
        )
        return (
            EquilibriumBackendNodeRequest(
                request.identity,
                request.feature_id,
                key,
                request.equilibrium,
                PhaseSetBinding(
                    request.available_phases,
                    request.selected_phases,
                    request.explicit_exclusions,
                ),
            ),
        )
    if type(request) is PhaseGibbsEnergyRequest:
        grid = build_cartesian_nodes(
            (
                build_axis("TEMPERATURE_K", request.temperatures_k),
                build_axis(
                    "PHASE_ORDINAL",
                    tuple(range(len(request.base_equilibrium.phases))),
                ),
            ),
            max_nodes=request.max_nodes,
        )
        nodes: list[PhaseGibbsBackendNodeRequest] = []
        for grid_node in grid:
            temperature = grid_node.coordinates[0][1]
            phase_index = int(grid_node.coordinates[1][1])
            phase = request.base_equilibrium.phases[phase_index]
            nodes.append(
                PhaseGibbsBackendNodeRequest(
                    request.identity,
                    request.feature_id,
                    DirectNodeKey(
                        grid_node,
                        (("PHASE", phase),),
                    ),
                    _state_at_temperature(
                        request.base_equilibrium,
                        temperature,
                        (phase,),
                    ),
                    phase,
                    request.phase_isolations[phase_index],
                )
            )
        return tuple(nodes)
    if type(request) is PhaseDrivingForceRequest:
        grid = build_cartesian_nodes(
            (build_axis("TEMPERATURE_K", request.temperatures_k),),
            max_nodes=request.max_nodes,
        )
        binding = _phase_binding_from_effective(
            request.reference_equilibrium.phases,
            request.explicit_exclusions,
        )
        return tuple(
            PhaseDrivingForceBackendNodeRequest(
                request.identity,
                request.feature_id,
                DirectNodeKey(
                    grid_node,
                    (("TARGET_PHASE", request.target_phase),),
                ),
                _state_at_temperature(
                    request.reference_equilibrium,
                    grid_node.coordinates[0][1],
                ),
                request.target_phase,
                binding,
            )
            for grid_node in grid
        )
    if type(request) is TZeroTemperatureRequest:
        grid = build_cartesian_nodes(
            (
                build_axis(
                    _composition_coordinate_name(
                        request.varying_component
                    ),
                    request.fractions,
                ),
            ),
            max_nodes=request.max_nodes,
        )
        states = _composition_states(
            request.base_equilibrium,
            request.varying_component,
            request.balance_component,
            request.fractions,
        )
        binding = _phase_binding_from_effective(
            request.base_equilibrium.phases,
            request.explicit_exclusions,
        )
        return tuple(
            TZeroBackendNodeRequest(
                request.identity,
                request.feature_id,
                DirectNodeKey(
                    grid_node,
                    (
                        ("PHASE_ONE", request.phase_one),
                        ("PHASE_TWO", request.phase_two),
                    ),
                ),
                state,
                request.phase_one,
                request.phase_two,
                request.minimum_temperature_k,
                request.maximum_temperature_k,
                binding,
            )
            for grid_node, state in zip(grid, states)
        )
    _fail("DIRECT_RESULT_INVALID")


def _expected_node_origins(
    request: object,
) -> tuple[DirectNodeOrigin, ...]:
    try:
        nodes = _deterministic_backend_nodes(request)
        request_origin = DirectRequestOrigin(
            _direct_request_snapshot(request)
        )
        return tuple(
            _node_origin_from_request_origin(request_origin, node)
            for node in nodes
        )
    except (AttributeError, DirectAdapterError, NumericalAdapterError) as error:
        raise DirectAdapterError("DIRECT_RESULT_INVALID") from error


def execute_equilibrium_single(
    request: EquilibriumSingleRequest,
    backend: object,
) -> DirectFeatureResult:
    caller_request = request
    request, caller_snapshot = _prepare_direct_request(
        request,
        EquilibriumSingleRequest,
    )
    key = DirectNodeKey(
        GridNode(0, (("TEMPERATURE_K", request.equilibrium.temperature_k),))
    )
    phase_binding = _phase_binding_from_effective(
        request.equilibrium.phases,
        request.explicit_exclusions,
    )
    node = EquilibriumBackendNodeRequest(
        request.identity,
        request.feature_id,
        key,
        request.equilibrium,
        phase_binding,
    )
    return _execute_equilibrium_nodes(
        request.identity,
        request.feature_id,
        request,
        (node,),
        backend,
        caller_request,
        EquilibriumSingleRequest,
        caller_snapshot,
    )


def execute_equilibrium_temperature_scan(
    request: EquilibriumTemperatureScanRequest,
    backend: object,
) -> DirectFeatureResult:
    caller_request = request
    request, caller_snapshot = _prepare_direct_request(
        request,
        EquilibriumTemperatureScanRequest,
    )
    grid = build_cartesian_nodes(
        (build_axis("TEMPERATURE_K", request.temperatures_k),),
        max_nodes=request.max_nodes,
    )
    phase_binding = _phase_binding_from_effective(
        request.base_equilibrium.phases,
        request.explicit_exclusions,
    )
    nodes = tuple(
        EquilibriumBackendNodeRequest(
            request.identity,
            request.feature_id,
            DirectNodeKey(grid_node),
            _state_at_temperature(request.base_equilibrium, grid_node.coordinates[0][1]),
            phase_binding,
        )
        for grid_node in grid
    )
    return _execute_equilibrium_nodes(
        request.identity,
        request.feature_id,
        request,
        nodes,
        backend,
        caller_request,
        EquilibriumTemperatureScanRequest,
        caller_snapshot,
    )


def execute_equilibrium_composition_scan(
    request: EquilibriumCompositionScanRequest,
    backend: object,
) -> DirectFeatureResult:
    caller_request = request
    request, caller_snapshot = _prepare_direct_request(
        request,
        EquilibriumCompositionScanRequest,
    )
    grid = build_cartesian_nodes(
        (
            build_axis(
                _composition_coordinate_name(request.varying_component),
                request.fractions,
            ),
        ),
        max_nodes=request.max_nodes,
    )
    states = _composition_states(
        request.base_equilibrium,
        request.varying_component,
        request.balance_component,
        request.fractions,
    )
    phase_binding = _phase_binding_from_effective(
        request.base_equilibrium.phases,
        request.explicit_exclusions,
    )
    nodes = tuple(
        EquilibriumBackendNodeRequest(
            request.identity,
            request.feature_id,
            DirectNodeKey(grid_node),
            state,
            phase_binding,
        )
        for grid_node, state in zip(grid, states)
    )
    return _execute_equilibrium_nodes(
        request.identity,
        request.feature_id,
        request,
        nodes,
        backend,
        caller_request,
        EquilibriumCompositionScanRequest,
        caller_snapshot,
    )


def execute_ternary_phase_fraction_map(
    request: TernaryPhaseFractionMapRequest,
    backend: object,
) -> DirectFeatureResult:
    caller_request = request
    request, caller_snapshot = _prepare_direct_request(
        request,
        TernaryPhaseFractionMapRequest,
    )
    if type(request.interval_count) is not int:
        _fail("DIRECT_TERNARY_INTERVAL_INVALID")
    expected_node_count = (
        (request.interval_count + 1) * (request.interval_count + 2) // 2
    )
    _require_node_count(expected_node_count, request.max_nodes)
    first, second, third = request.ternary_components
    phase_binding = _phase_binding_from_effective(
        request.phases,
        request.explicit_exclusions,
    )
    nodes: list[EquilibriumBackendNodeRequest] = []
    ordinal = 0
    for second_index in range(request.interval_count + 1):
        second_fraction = _canonical_ternary_fraction(
            second_index / request.interval_count
        )
        remaining = request.interval_count - second_index
        for third_index in range(remaining + 1):
            third_fraction = _canonical_ternary_fraction(
                third_index / request.interval_count
            )
            first_fraction = _canonical_ternary_fraction(
                1.0 - second_fraction - third_fraction
            )
            values = {
                first: 0.0 if first_fraction == 0.0 else first_fraction,
                second: 0.0 if second_fraction == 0.0 else second_fraction,
                third: 0.0 if third_fraction == 0.0 else third_fraction,
            }
            composition = tuple(
                (component, values.get(component, 0.0))
                for component in request.components
            )
            state = EquilibriumRequest(
                request.temperature_k,
                request.pressure_pa,
                request.components,
                request.phases,
                composition,
            )
            key = DirectNodeKey(
                GridNode(
                    ordinal,
                    (
                        (_composition_coordinate_name(first), values[first]),
                        (_composition_coordinate_name(second), values[second]),
                        (_composition_coordinate_name(third), values[third]),
                    ),
                ),
                (("TARGET_PHASE", request.target_phase),),
            )
            nodes.append(
                EquilibriumBackendNodeRequest(
                    request.identity,
                    request.feature_id,
                    key,
                    state,
                    phase_binding,
                )
            )
            ordinal += 1
    if ordinal != expected_node_count or len(nodes) != expected_node_count:
        _fail("DIRECT_REQUEST_INVALID")
    result = _execute_equilibrium_nodes(
        request.identity,
        request.feature_id,
        request,
        tuple(nodes),
        backend,
        caller_request,
        TernaryPhaseFractionMapRequest,
        caller_snapshot,
    )
    _assert_caller_request_unchanged(
        caller_request,
        TernaryPhaseFractionMapRequest,
        caller_snapshot,
    )
    return result


def execute_manual_phase_selection_metastable(
    request: ManualPhaseSelectionRequest,
    backend: object,
) -> DirectFeatureResult:
    caller_request = request
    request, caller_snapshot = _prepare_direct_request(
        request,
        ManualPhaseSelectionRequest,
    )
    key = DirectNodeKey(
        GridNode(0, (("TEMPERATURE_K", request.equilibrium.temperature_k),)),
        (("SELECTION_MODE", "MANUAL_METASTABLE"),),
    )
    phase_binding = PhaseSetBinding(
        request.available_phases,
        request.selected_phases,
        request.explicit_exclusions,
    )
    node = EquilibriumBackendNodeRequest(
        request.identity,
        request.feature_id,
        key,
        request.equilibrium,
        phase_binding,
    )
    return _execute_equilibrium_nodes(
        request.identity,
        request.feature_id,
        request,
        (node,),
        backend,
        caller_request,
        ManualPhaseSelectionRequest,
        caller_snapshot,
    )


def _execute_scalar_nodes(
    identity: DatabaseProfileIdentity,
    feature_id: str,
    result_request: object,
    nodes: tuple[object, ...],
    backend: object,
    method_name: str,
    output_name: str,
    caller_request: object,
    caller_type: type,
    caller_snapshot: tuple[object, ...],
) -> DirectFeatureResult:
    method = _checked_backend_method(
        backend,
        method_name,
        caller_request,
        caller_type,
        caller_snapshot,
    )
    allowed_reasons = (
        _TZERO_NODE_REASONS
        if method_name == "tzero_temperature"
        else _PROPERTY_NODE_REASONS
    )
    rows: list[DirectNodeResult] = []
    request_origin = DirectRequestOrigin(
        _direct_request_snapshot(result_request)
    )
    for node_request in nodes:
        origin = _node_origin_from_request_origin(
            request_origin,
            node_request,
        )
        try:
            raw_reply = _invoke_backend(
                method,
                node_request,
                caller_request,
                caller_type,
                caller_snapshot,
            )
        except ExpectedDirectNodeFailure as error:
            rows.append(
                _failed_row(
                    identity,
                    feature_id,
                    node_request.key,
                    node_request.phase_binding,
                    origin,
                    error,
                    allowed_reasons,
                )
            )
        else:
            reply = _validate_reply_binding(
                raw_reply,
                ScalarBackendReply,
                identity,
                feature_id,
                node_request.key,
                node_request.phase_binding,
            )
            value = _binary64(reply.value)
            if type(node_request) is TZeroBackendNodeRequest and not (
                node_request.minimum_temperature_k <= value <= node_request.maximum_temperature_k
            ):
                _fail("DIRECT_TZERO_OUT_OF_BOUNDS")
            rows.append(
                DirectNodeResult(
                    identity,
                    feature_id,
                    node_request.key,
                    node_request.phase_binding,
                    "PASS",
                    "DIRECT_NODE_OK",
                    None,
                    ((output_name, value),),
                    origin,
                )
            )
    result = _finish(feature_id, identity, result_request, tuple(rows))
    _assert_caller_request_unchanged(
        caller_request,
        caller_type,
        caller_snapshot,
    )
    return result


def execute_phase_gibbs_energy(
    request: PhaseGibbsEnergyRequest,
    backend: object,
) -> DirectFeatureResult:
    caller_request = request
    request, caller_snapshot = _prepare_direct_request(
        request,
        PhaseGibbsEnergyRequest,
    )
    grid = build_cartesian_nodes(
        (
            build_axis("TEMPERATURE_K", request.temperatures_k),
            build_axis("PHASE_ORDINAL", tuple(range(len(request.base_equilibrium.phases)))),
        ),
        max_nodes=request.max_nodes,
    )
    nodes: list[PhaseGibbsBackendNodeRequest] = []
    for grid_node in grid:
        temperature = grid_node.coordinates[0][1]
        phase_index = int(grid_node.coordinates[1][1])
        phase = request.base_equilibrium.phases[phase_index]
        phase_binding = request.phase_isolations[phase_index]
        key = DirectNodeKey(grid_node, (("PHASE", phase),))
        state = _state_at_temperature(request.base_equilibrium, temperature, (phase,))
        nodes.append(
            PhaseGibbsBackendNodeRequest(
                request.identity,
                request.feature_id,
                key,
                state,
                phase,
                phase_binding,
            )
        )
    return _execute_scalar_nodes(
        request.identity,
        request.feature_id,
        request,
        tuple(nodes),
        backend,
        "phase_gibbs_energy",
        "GIBBS_ENERGY_J_PER_MOL",
        caller_request,
        PhaseGibbsEnergyRequest,
        caller_snapshot,
    )


def execute_phase_driving_force(
    request: PhaseDrivingForceRequest,
    backend: object,
) -> DirectFeatureResult:
    caller_request = request
    request, caller_snapshot = _prepare_direct_request(
        request,
        PhaseDrivingForceRequest,
    )
    grid = build_cartesian_nodes(
        (build_axis("TEMPERATURE_K", request.temperatures_k),),
        max_nodes=request.max_nodes,
    )
    phase_binding = _phase_binding_from_effective(
        request.reference_equilibrium.phases,
        request.explicit_exclusions,
    )
    nodes = tuple(
        PhaseDrivingForceBackendNodeRequest(
            request.identity,
            request.feature_id,
            DirectNodeKey(grid_node, (("TARGET_PHASE", request.target_phase),)),
            _state_at_temperature(request.reference_equilibrium, grid_node.coordinates[0][1]),
            request.target_phase,
            phase_binding,
        )
        for grid_node in grid
    )
    return _execute_scalar_nodes(
        request.identity,
        request.feature_id,
        request,
        nodes,
        backend,
        "phase_driving_force",
        "DRIVING_FORCE_J_PER_MOL",
        caller_request,
        PhaseDrivingForceRequest,
        caller_snapshot,
    )


def execute_tzero_temperature(
    request: TZeroTemperatureRequest,
    backend: object,
) -> DirectFeatureResult:
    caller_request = request
    request, caller_snapshot = _prepare_direct_request(
        request,
        TZeroTemperatureRequest,
    )
    grid = build_cartesian_nodes(
        (
            build_axis(
                _composition_coordinate_name(request.varying_component),
                request.fractions,
            ),
        ),
        max_nodes=request.max_nodes,
    )
    states = _composition_states(
        request.base_equilibrium,
        request.varying_component,
        request.balance_component,
        request.fractions,
    )
    phase_binding = _phase_binding_from_effective(
        request.base_equilibrium.phases,
        request.explicit_exclusions,
    )
    nodes = tuple(
        TZeroBackendNodeRequest(
            request.identity,
            request.feature_id,
            DirectNodeKey(
                grid_node,
                (("PHASE_ONE", request.phase_one), ("PHASE_TWO", request.phase_two)),
            ),
            state,
            request.phase_one,
            request.phase_two,
            request.minimum_temperature_k,
            request.maximum_temperature_k,
            phase_binding,
        )
        for grid_node, state in zip(grid, states)
    )
    return _execute_scalar_nodes(
        request.identity,
        request.feature_id,
        request,
        nodes,
        backend,
        "tzero_temperature",
        "TZERO_TEMPERATURE_K",
        caller_request,
        TZeroTemperatureRequest,
        caller_snapshot,
    )


def execute_direct_feature(request: object, backend: object) -> DirectFeatureResult:
    """Dispatch one of the eight direct request DTOs without UI side effects."""

    if type(request) is EquilibriumSingleRequest:
        return execute_equilibrium_single(request, backend)
    if type(request) is EquilibriumTemperatureScanRequest:
        return execute_equilibrium_temperature_scan(request, backend)
    if type(request) is EquilibriumCompositionScanRequest:
        return execute_equilibrium_composition_scan(request, backend)
    if type(request) is TernaryPhaseFractionMapRequest:
        return execute_ternary_phase_fraction_map(request, backend)
    if type(request) is ManualPhaseSelectionRequest:
        return execute_manual_phase_selection_metastable(request, backend)
    if type(request) is PhaseGibbsEnergyRequest:
        return execute_phase_gibbs_energy(request, backend)
    if type(request) is PhaseDrivingForceRequest:
        return execute_phase_driving_force(request, backend)
    if type(request) is TZeroTemperatureRequest:
        return execute_tzero_temperature(request, backend)
    _fail("DIRECT_REQUEST_INVALID")


__all__ = (
    "DIRECT_FEATURE_IDS",
    "SUPPORTED_DATABASE_FAMILIES",
    "FE_PROFILE_IDS",
    "STEEL_REQUIRED_PRODUCT_SCOPE",
    "FE_BASELINE_PROFILE",
    "FE_EXCLUSION_DECISION_MADE",
    "COUNTS_TOWARD_FEATURE_COVERAGE",
    "ACCEPTANCE_CLAIM",
    "PRODUCTION_USE",
    "DIRECT_ADAPTER_REASON_CODES",
    "DirectAdapterError",
    "ExpectedDirectNodeFailure",
    "DatabaseProfileIdentity",
    "DirectNodeKey",
    "PhaseSetBinding",
    "DirectRequestOrigin",
    "DirectNodeOrigin",
    "FailedDirectNode",
    "DirectNodeResult",
    "DirectFeatureResult",
    "EquilibriumBackendNodeRequest",
    "PhaseGibbsBackendNodeRequest",
    "PhaseDrivingForceBackendNodeRequest",
    "TZeroBackendNodeRequest",
    "EquilibriumBackendReply",
    "ScalarBackendReply",
    "DirectFeatureBackend",
    "EquilibriumSingleRequest",
    "EquilibriumTemperatureScanRequest",
    "EquilibriumCompositionScanRequest",
    "TernaryPhaseFractionMapRequest",
    "ManualPhaseSelectionRequest",
    "PhaseGibbsEnergyRequest",
    "PhaseDrivingForceRequest",
    "TZeroTemperatureRequest",
    "execute_equilibrium_single",
    "execute_equilibrium_temperature_scan",
    "execute_equilibrium_composition_scan",
    "execute_ternary_phase_fraction_map",
    "execute_manual_phase_selection_metastable",
    "execute_phase_gibbs_energy",
    "execute_phase_driving_force",
    "execute_tzero_temperature",
    "execute_direct_feature",
)
