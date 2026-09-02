"""Receipt-bound pycalphad mapping backend for Wave 2B.

This module is an internal-qualification integration candidate.  It loads a
thermodynamic database only from ``ExecutionLease.file_path("runtime")`` and
binds every mapping request to the exact database, request, phase-domain,
bounds, and solver-option primitives recorded by a ``DomainReceipt``.

pycalphad 0.11.2 exposes final mapped nodes and ZPF-line records, but it does
not expose a complete, stable ledger of every attempted equilibrium (including
rejected and failed steps).  The legacy V1 entry point therefore remains fail
closed unless a strategy implements this module's explicit complete-trace
protocol.  The V2.1 entry point separately reports only the exact public
post-run observations as ``PARTIAL`` evidence; it never relabels those records
as hidden chronological solver attempts and never claims ``COMPLETE``.

The frozen V1 path-adapter ledger cannot represent every possible complete
trace, and its database identity cannot express the exact Ni/Al receipt role
``RELEASE_CANDIDATE_PENDING_NE04``.  V1 therefore retains its existing
``*_V2_REQUIRED`` failures.  V2.1 retains the exact role, execution binding,
phase-instance multiplicity, component membership, coordinates, relation
evidence, and incomplete-observability diagnosis without inventing missing
attempts, coordinates, phases, or line completion.

Steel is mandatory scope.  The exact Fe profiles ``thermogar_patch`` and
``upstream_original`` remain distinct internal identities; neither is chosen
as a baseline.  C15_LAVES must remain candidate, requested, and effective and
must not be excluded while the user's product decision is undecided.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
import hashlib as _hashlib
import importlib as _importlib
import math as _math
from pathlib import Path as _Path
import struct as _struct
from types import MappingProxyType as _MappingProxyType
from typing import Mapping as _Mapping

import thermogar_wave2b_path_adapters as _path
import thermogar_wave2b_path_contract_v2 as _v2
import thermogar_wave2b_receipts as _receipts


MAPPING_BACKEND_SCHEMA = "THERMOGAR-WAVE2B-RECEIPT-BOUND-MAPPING-BACKEND-1"
MAPPING_REQUEST_SCHEMA = "THERMOGAR-WAVE2B-MAPPING-REQUEST-1"
MAPPING_REQUEST_V2_SCHEMA = "THERMOGAR-WAVE2B-MAPPING-REQUEST-V2-1"
COMPLETE_DIAGNOSTICS_SCHEMA = "THERMOGAR-PYCALPHAD-MAPPING-DIAGNOSTICS-1"
BACKEND_ID = "thermogar_wave2b_pycalphad_0_11_2_mapping_candidate"
PYCALPHAD_VERSION = "0.11.2"
PATH_CONTRACT_V2_SHA256 = (
    "c58a35d1548c3d5b321ac4094c3ef86bd6b30d2d2f5f4e6570cad2556afc7ed7"
)
SUPPORTED_MAPPING_FEATURES = (
    "binary_phase_diagram",
    "multicomponent_isopleth",
    "ternary_phase_diagram",
)
SUPPORTED_DATABASE_FAMILIES = ("ni", "al", "fe")
SUPPORTED_FE_PROFILE_IDS = ("thermogar_patch", "upstream_original")
STEEL_REQUIRED_PRODUCT_SCOPE = True
FE_BASELINE_PROFILE = None
FE_EXCLUSION_DECISION_MADE = False
COUNTS_TOWARD_FEATURE_COVERAGE = False
ACCEPTANCE_CLAIM = False
PRODUCTION_USE = "DENIED"
V2_PARTIAL_TERMINAL_REASON = "PARTIAL_UNRESOLVED_BRANCHES"
V2_TOPOLOGY_PARTIAL_TERMINAL_REASON = (
    "TOPOLOGY_OBSERVED_DIAGNOSTICS_PARTIAL"
)
V2_PARTIAL_REASON_CODE = "PYCALPHAD_0_11_2_HIDDEN_ATTEMPTS_UNAVAILABLE"

# pycalphad's mapping equilibrium solve may return a mole-fraction coordinate
# a few 1e-11 away from an exact fixed value, or a few ulps outside a closed
# composition boundary.  Post-run evidence retains that observed binary64
# value rather than rewriting it to the request value.  These finite,
# solver/feature-pinned gates only prove domain membership; strategy inputs
# remain bit-exactly checked before and after ``do_map``.
PYCALPHAD_0_11_2_MOLE_FRACTION_ABS_TOL_BY_FEATURE = _MappingProxyType(
    {
        "binary_phase_diagram": 1.0e-9,
        "multicomponent_isopleth": 1.0e-9,
        "ternary_phase_diagram": 1.0e-9,
    }
)
PYCALPHAD_0_11_2_ISOPLETH_FIXED_COMPOSITION_ABS_TOL = (
    PYCALPHAD_0_11_2_MOLE_FRACTION_ABS_TOL_BY_FEATURE[
        "multicomponent_isopleth"
    ]
)
V2_POSTRUN_MEMBERSHIP_POLICY = (
    "RAW_BINARY64_RETAINED_PYCALPHAD_0_11_2_FEATURE_PINNED_MOLE_"
    "FRACTION_ABS_1E_9"
)

_V2_DATABASE_ID = _MappingProxyType(
    {
        ("ni", "mc_ni_v2036"): "mc_ni_v2036",
        ("al", "mc_al_v2037"): "mc_al_v2037",
        ("fe", "thermogar_patch"): "mc_fe_v2062",
        ("fe", "upstream_original"): "mc_fe_v2062",
    }
)

_EXACT_FE_PROFILE_ROLE = _MappingProxyType(
    {
        ("fe", "thermogar_patch"): "EVALUATION_PROFILE",
        ("fe", "upstream_original"): "DIAGNOSTIC_CONTROL",
    }
)
_FEATURE_STRATEGY = _MappingProxyType(
    {
        "binary_phase_diagram": "BinaryStrategy",
        "multicomponent_isopleth": "IsoplethStrategy",
        "ternary_phase_diagram": "TernaryStrategy",
    }
)
_FAILURE_REASONS = frozenset(
    {
        "W2B_MAP_STARTING_POINT_FAILED",
        "W2B_MAP_CONVERGENCE_FAILED",
        "W2B_MAP_DOMAIN_FAILED",
        "W2B_MAP_INTERNAL_FAILED",
    }
)
_TERMINATIONS = frozenset(
    {
        "W2B_MAP_COMPLETED",
        "W2B_MAP_TERMINATED_BACKEND_FAILURE",
        "W2B_MAP_TERMINATED_NO_PROGRESS",
    }
)
_LEDGER_NODE_KINDS = frozenset(
    {"BOUNDARY_NODE", "INTERNAL_NODE", "INVARIANT_NODE", "STARTING_POINT"}
)
_DIAGNOSTIC_NODE_KINDS = _LEDGER_NODE_KINDS | frozenset(
    {
        "ABANDONED_BRANCH_POINT",
        "DIRECTION_PROBE",
        "TRANSIENT_PROBE",
    }
)
_SEGMENT_KINDS = _MappingProxyType(
    {
        "binary_phase_diagram": frozenset(
            {"BOUNDARY", "INVARIANT_LINK", "TIELINE"}
        ),
        "multicomponent_isopleth": frozenset({"INVARIANT_LINK", "ZPF"}),
        "ternary_phase_diagram": frozenset(
            {"BOUNDARY", "THREE_PHASE_LINK", "TIELINE"}
        ),
    }
)

_REASONS = {
    "W2B_MAPPING_BACKEND_CONTEXT_INVALID": (
        "Backend context must contain one exact domain, PRE snapshot, and active lease."
    ),
    "W2B_MAPPING_BACKEND_INTERNAL_QUALIFICATION_REQUIRED": (
        "The mapping backend is restricted to INTERNAL_QUALIFICATION."
    ),
    "W2B_MAPPING_BACKEND_LEASE_INACTIVE": (
        "The bound ExecutionLease is inactive or outside its PRE execution window."
    ),
    "W2B_MAPPING_BACKEND_PRE_MISMATCH": (
        "The PRE snapshot does not match the domain, profile, lease, or execution snapshot."
    ),
    "W2B_MAPPING_BACKEND_PROFILE_IDENTITY_MISMATCH": (
        "The mapping request uses a different exact database profile identity."
    ),
    "W2B_MAPPING_BACKEND_DOMAIN_MISMATCH": (
        "The mapping request differs from the exact receipt-bound request or phase domain."
    ),
    "W2B_MAPPING_BACKEND_FE_POLICY_REQUIRED": (
        "Fe requires an exact profile and retained C15_LAVES while policy is undecided."
    ),
    "W2B_MAPPING_BACKEND_REQUEST_INVALID": (
        "The request is not an exact valid Wave 2B mapping request DTO."
    ),
    "W2B_MAPPING_BACKEND_BOUNDS_INVALID": (
        "The receipt bounds are not the exact bounds declared by the mapping request."
    ),
    "W2B_MAPPING_BACKEND_SOLVER_OPTIONS_UNSUPPORTED": (
        "Only bounded global_min_pdensity and max_iterations options are supported."
    ),
    "W2B_MAPPING_BACKEND_PYCALPHAD_UNAVAILABLE": (
        "The pinned pycalphad mapping runtime could not be imported lazily."
    ),
    "W2B_MAPPING_BACKEND_PYCALPHAD_VERSION_MISMATCH": (
        "The backend requires exact pycalphad 0.11.2 mapping semantics."
    ),
    "W2B_MAPPING_BACKEND_DATABASE_LOAD_FAILED": (
        "pycalphad could not load the active runtime database snapshot."
    ),
    "W2B_MAPPING_BACKEND_RUNTIME_PATH_INVALID": (
        "The database path is not the exact active lease runtime snapshot path."
    ),
    "W2B_MAPPING_BACKEND_STRATEGY_CONSTRUCTION_FAILED": (
        "The exact pycalphad mapping strategy could not be constructed."
    ),
    "W2B_MAPPING_BACKEND_STRATEGY_RAISED": (
        "The mapping strategy raised and did not provide a complete retained trace."
    ),
    "W2B_MAPPING_BACKEND_INCOMPLETE_DIAGNOSTICS": (
        "The strategy API cannot prove a complete attempted-node and true-segment trace."
    ),
    "W2B_MAPPING_BACKEND_NOT_IMPLEMENTED_LEDGER_V2_REQUIRED": (
        "The complete trace contains honest state that RawMappingLedger v1 cannot represent."
    ),
    "W2B_MAPPING_BACKEND_NOT_IMPLEMENTED_IDENTITY_V2_REQUIRED": (
        "DatabaseIdentity v1 cannot represent the exact Ni or Al receipt profile role."
    ),
    "W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID": (
        "The claimed complete strategy diagnostic trace is structurally inconsistent."
    ),
    "W2B_MAPPING_BACKEND_V2_BINDING_INVALID": (
        "The V2 request, receipt, PRE snapshot, or active execution binding is not exact."
    ),
    "W2B_MAPPING_BACKEND_V2_CONTRACT_DRIFT": (
        "The loaded Path Contract V2 module is not the exact frozen audited file."
    ),
    "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID": (
        "A public post-run mapping observation cannot be translated without ambiguity."
    ),
    "W2B_MAPPING_BACKEND_V2_OBSERVATION_BUDGET_EXCEEDED": (
        "The exact public post-run observation set exceeds the declared V2 evidence budget."
    ),
    "W2B_MAPPING_BACKEND_V2_NO_PUBLIC_OBSERVATIONS": (
        "The strategy exposed no final public node or ZPF observation to retain."
    ),
    "W2B_MAPPING_BACKEND_V2_STRATEGY_RAISED": (
        "The native strategy raised; V2 has no exact exception-bound terminal envelope."
    ),
}
WAVE2B_MAPPING_BACKEND_REASON_CODES: _Mapping[str, str] = _MappingProxyType(
    _REASONS
)
del _REASONS


class Wave2BMappingBackendError(ValueError):
    """Stable fail-closed backend error carrying one registered reason code."""

    __slots__ = ("reason_code",)

    def __init__(self, reason_code: str) -> None:
        if (
            type(reason_code) is not str
            or reason_code not in WAVE2B_MAPPING_BACKEND_REASON_CODES
        ):
            raise RuntimeError("Unknown Wave 2B mapping backend reason code")
        self.reason_code = reason_code
        super().__init__(reason_code)


def _fail(reason_code: str) -> None:
    raise Wave2BMappingBackendError(reason_code)


def _finite(value: object, reason: str) -> float:
    if type(value) not in (int, float):
        _fail(reason)
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise Wave2BMappingBackendError(reason) from error
    if not _math.isfinite(number):
        _fail(reason)
    return 0.0 if number == 0.0 else number


def _same_binary64(left: float, right: float) -> bool:
    return _struct.pack(">d", left) == _struct.pack(">d", right)


def _within_postrun_fixed_condition(
    feature: str,
    observed: float,
    expected: float,
) -> bool:
    tolerance = PYCALPHAD_0_11_2_MOLE_FRACTION_ABS_TOL_BY_FEATURE.get(
        feature
    )
    return (
        feature == "multicomponent_isopleth"
        and tolerance is not None
        and _math.isfinite(observed)
        and _math.isfinite(expected)
        and abs(observed - expected) <= tolerance
    )


def _within_postrun_mole_fraction_interval(
    feature: str,
    observed: float,
    lower: float,
    upper: float,
) -> bool:
    tolerance = PYCALPHAD_0_11_2_MOLE_FRACTION_ABS_TOL_BY_FEATURE.get(
        feature
    )
    return (
        tolerance is not None
        and _math.isfinite(observed)
        and _math.isfinite(lower)
        and _math.isfinite(upper)
        and lower <= upper
        and lower - tolerance <= observed <= upper + tolerance
    )


def _decode_canonical_value(value: object, depth: int = 0) -> object:
    """Decode the receipt layer's explicit canonical binary64 representation."""

    if depth > 64:
        _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is list:
        return [_decode_canonical_value(item, depth + 1) for item in value]
    if type(value) is dict:
        if set(value) == {"$f64"}:
            encoded = value["$f64"]
            if (
                type(encoded) is not str
                or len(encoded) != 16
                or any(character not in "0123456789abcdef" for character in encoded)
            ):
                _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")
            number = _struct.unpack(">d", bytes.fromhex(encoded))[0]
            if not _math.isfinite(number):
                _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")
            return number
        return {
            key: _decode_canonical_value(item, depth + 1)
            for key, item in value.items()
        }
    _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")


def _payload_dict(value: object) -> dict[str, object]:
    try:
        if type(value) is not _receipts.CanonicalPayload:
            _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")
        decoded = _decode_canonical_value(value.value())
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_CONTEXT_INVALID"
        ) from error
    if type(decoded) is not dict:
        _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")
    return decoded


def _copy_database(value: object) -> _path.DatabaseIdentity:
    try:
        if type(value) is not _path.DatabaseIdentity:
            _fail("W2B_MAPPING_BACKEND_REQUEST_INVALID")
        return _path.DatabaseIdentity(
            family=value.family,
            database_id=value.database_id,
            database_sha256=value.database_sha256,
            profile_id=value.profile_id,
            profile_role=value.profile_role,
            fe_baseline_decision=value.fe_baseline_decision,
            c15_exclusion_decision=value.c15_exclusion_decision,
        )
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_REQUEST_INVALID"
        ) from error


def _copy_selection(value: object) -> _path.PhaseSelection:
    try:
        if type(value) is not _path.PhaseSelection:
            _fail("W2B_MAPPING_BACKEND_REQUEST_INVALID")
        return _path.PhaseSelection(
            candidate_phases=tuple(value.candidate_phases),
            requested_phases=tuple(value.requested_phases),
            excluded_phases=tuple(value.excluded_phases),
            effective_phases=tuple(value.effective_phases),
        )
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_REQUEST_INVALID"
        ) from error


def _copy_range(value: object) -> _path.ClosedRange:
    try:
        if type(value) is not _path.ClosedRange:
            _fail("W2B_MAPPING_BACKEND_REQUEST_INVALID")
        return _path.ClosedRange(value.lower, value.upper, value.seed_step)
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_REQUEST_INVALID"
        ) from error


def _copy_request(value: object) -> _path.MappingRequest:
    """Reconstruct all nested primitives; never trust a frozen instance."""

    try:
        if type(value) is _path.BinaryPhaseDiagramRequest:
            return _path.BinaryPhaseDiagramRequest(
                database=_copy_database(value.database),
                left_component=value.left_component,
                right_component=value.right_component,
                phase_selection=_copy_selection(value.phase_selection),
                pressure_pa=value.pressure_pa,
                right_fraction=_copy_range(value.right_fraction),
                temperature_k=_copy_range(value.temperature_k),
            )
        if type(value) is _path.MulticomponentIsoplethRequest:
            return _path.MulticomponentIsoplethRequest(
                database=_copy_database(value.database),
                balance_component=value.balance_component,
                variable_component=value.variable_component,
                fixed_composition=tuple(
                    (name, amount) for name, amount in value.fixed_composition
                ),
                phase_selection=_copy_selection(value.phase_selection),
                pressure_pa=value.pressure_pa,
                variable_fraction=_copy_range(value.variable_fraction),
                temperature_k=_copy_range(value.temperature_k),
            )
        if type(value) is _path.TernaryPhaseDiagramRequest:
            return _path.TernaryPhaseDiagramRequest(
                database=_copy_database(value.database),
                dependent_component=value.dependent_component,
                x_component=value.x_component,
                y_component=value.y_component,
                phase_selection=_copy_selection(value.phase_selection),
                pressure_pa=value.pressure_pa,
                temperature_k=value.temperature_k,
                starting_point_step=value.starting_point_step,
            )
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_REQUEST_INVALID"
        ) from error
    _fail("W2B_MAPPING_BACKEND_REQUEST_INVALID")


def _database_payload(identity: _path.DatabaseIdentity) -> dict[str, object]:
    return {
        "family": identity.family,
        "database_id": identity.database_id,
        "database_sha256": identity.database_sha256,
        "profile_id": identity.profile_id,
        "profile_role": identity.profile_role,
        "fe_baseline_decision": identity.fe_baseline_decision,
        "c15_exclusion_decision": identity.c15_exclusion_decision,
    }


def _selection_payload(selection: _path.PhaseSelection) -> dict[str, object]:
    return {
        "candidate": list(selection.candidate_phases),
        "requested": list(selection.requested_phases),
        "excluded": list(selection.excluded_phases),
        "effective": list(selection.effective_phases),
    }


def _range_payload(value: _path.ClosedRange) -> dict[str, float]:
    return {
        "minimum": value.lower,
        "maximum": value.upper,
        "seed_step": value.seed_step,
    }


def mapping_request_payload(request: object) -> dict[str, object]:
    """Return the exact primitive mapping request card for ``full_request``."""

    value = _copy_request(request)
    payload: dict[str, object] = {
        "schema_version": MAPPING_REQUEST_SCHEMA,
        "feature_id": value.feature,
        "database_identity": _database_payload(value.database),
        "components": list(value.components),
        "phase_selection": _selection_payload(value.phase_selection),
        "pressure_pa": value.pressure_pa,
        "total_moles": 1.0,
    }
    if type(value) is _path.BinaryPhaseDiagramRequest:
        payload.update(
            {
                "left_component": value.left_component,
                "right_component": value.right_component,
                "right_fraction": _range_payload(value.right_fraction),
                "temperature_k": _range_payload(value.temperature_k),
            }
        )
    elif type(value) is _path.MulticomponentIsoplethRequest:
        payload.update(
            {
                "balance_component": value.balance_component,
                "variable_component": value.variable_component,
                "fixed_composition": {
                    name: amount for name, amount in value.fixed_composition
                },
                "variable_fraction": _range_payload(value.variable_fraction),
                "temperature_k": _range_payload(value.temperature_k),
            }
        )
    else:
        payload.update(
            {
                "dependent_component": value.dependent_component,
                "x_component": value.x_component,
                "y_component": value.y_component,
                "temperature_k": value.temperature_k,
                "starting_point_step": value.starting_point_step,
            }
        )
    return payload


def mapping_bounds_payload(request: object) -> dict[str, object]:
    """Return the exact closed domain card required by a mapping receipt."""

    value = _copy_request(request)
    bounds: dict[str, object] = {
        "pressure_pa": {
            "minimum": value.pressure_pa,
            "maximum": value.pressure_pa,
        },
        "total_moles": {"minimum": 1.0, "maximum": 1.0},
    }
    if type(value) is _path.BinaryPhaseDiagramRequest:
        bounds["right_fraction"] = _range_payload(value.right_fraction)
        bounds["temperature_k"] = _range_payload(value.temperature_k)
    elif type(value) is _path.MulticomponentIsoplethRequest:
        bounds["variable_fraction"] = _range_payload(value.variable_fraction)
        bounds["temperature_k"] = _range_payload(value.temperature_k)
        bounds["fixed_composition"] = {
            name: {"minimum": amount, "maximum": amount}
            for name, amount in value.fixed_composition
        }
    else:
        bounds.update(
            {
                "temperature_k": {
                    "minimum": value.temperature_k,
                    "maximum": value.temperature_k,
                },
                "x_fraction": {"minimum": 0.0, "maximum": 1.0},
                "y_fraction": {"minimum": 0.0, "maximum": 1.0},
                "simplex_sum_maximum": 1.0,
                "starting_point_step": value.starting_point_step,
            }
        )
    return bounds


def mapping_full_request_payload(
    request: object,
    profile_receipt: object,
) -> dict[str, object]:
    """Build the exact full request shape accepted by this backend."""

    value = _copy_request(request)
    try:
        database = _receipts.request_database_binding(profile_receipt)
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_CONTEXT_INVALID"
        ) from error
    return {
        "feature_id": value.feature,
        "database": database,
        "mapping_request": mapping_request_payload(value),
    }


def _database_identity_v2_from_profile(
    profile_receipt: object,
) -> _v2.DatabaseIdentityV2:
    """Reconstruct the exact V2 identity from a verified profile receipt."""

    try:
        if type(profile_receipt) is not _receipts.DatabaseProfileReceipt:
            _fail("W2B_MAPPING_BACKEND_V2_BINDING_INVALID")
        key = (profile_receipt.family, profile_receipt.profile)
        database_id = _V2_DATABASE_ID.get(key)
        if database_id is None:
            _fail("W2B_MAPPING_BACKEND_V2_BINDING_INVALID")
        return _v2.DatabaseIdentityV2(
            family=profile_receipt.family,
            database_id=database_id,
            database_sha256=profile_receipt.runtime.sha256,
            profile_id=profile_receipt.profile,
            profile_role=profile_receipt.profile_role,
            fe_baseline_decision=profile_receipt.baseline_decision,
            c15_exclusion_decision=profile_receipt.c15_exclusion_decision,
        )
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_BINDING_INVALID"
        ) from error


def _database_payload_v2(identity: _v2.DatabaseIdentityV2) -> dict[str, object]:
    return {
        "family": identity.family,
        "database_id": identity.database_id,
        "database_sha256": identity.database_sha256,
        "profile_id": identity.profile_id,
        "profile_role": identity.profile_role,
        "fe_baseline_decision": identity.fe_baseline_decision,
        "c15_exclusion_decision": identity.c15_exclusion_decision,
    }


def _bind_geometry_identity_to_v2_profile(
    request: _path.MappingRequest,
    identity: _v2.DatabaseIdentityV2,
) -> None:
    """Bind the legacy geometry carrier without copying its V1-only role."""

    legacy = request.database
    if (
        legacy.family != identity.family
        or legacy.database_id != identity.database_id
        or legacy.database_sha256 != identity.database_sha256
        or legacy.profile_id != identity.profile_id
    ):
        _fail("W2B_MAPPING_BACKEND_V2_BINDING_INVALID")
    if identity.family == "fe":
        if (
            legacy.profile_role != identity.profile_role
            or legacy.fe_baseline_decision != identity.fe_baseline_decision
            or legacy.c15_exclusion_decision
            != identity.c15_exclusion_decision
            or "C15_LAVES" not in request.phase_selection.candidate_phases
            or "C15_LAVES" not in request.phase_selection.requested_phases
            or "C15_LAVES" in request.phase_selection.excluded_phases
            or "C15_LAVES" not in request.phase_selection.effective_phases
        ):
            _fail("W2B_MAPPING_BACKEND_FE_POLICY_REQUIRED")
    elif (
        legacy.fe_baseline_decision != _receipts.POLICY_NOT_APPLICABLE
        or legacy.c15_exclusion_decision
        != _receipts.POLICY_NOT_APPLICABLE
    ):
        _fail("W2B_MAPPING_BACKEND_V2_BINDING_INVALID")


def mapping_request_payload_v2(
    request: object,
    profile_receipt: object,
) -> dict[str, object]:
    """Return a V2 request card whose database role comes only from receipt."""

    value = _copy_request(request)
    identity = _database_identity_v2_from_profile(profile_receipt)
    _bind_geometry_identity_to_v2_profile(value, identity)
    payload = mapping_request_payload(value)
    payload["schema_version"] = MAPPING_REQUEST_V2_SCHEMA
    payload["database_identity"] = _database_payload_v2(identity)
    return payload


def mapping_full_request_payload_v2(
    request: object,
    profile_receipt: object,
) -> dict[str, object]:
    """Build the exact receipt-bound full request for native V2 mapping."""

    value = _copy_request(request)
    try:
        database = _receipts.request_database_binding(profile_receipt)
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_BINDING_INVALID"
        ) from error
    return {
        "feature_id": value.feature,
        "database": database,
        "mapping_request": mapping_request_payload_v2(value, profile_receipt),
    }


@_dataclass(frozen=True, slots=True)
class MappingDiagnosticAttempt:
    """One package-exposed attempt from a complete strategy trace."""

    raw_ordinal: int
    kind: str
    outcome: str
    coordinates: tuple[tuple[str, float], ...]
    phases: tuple[str, ...]
    reason_code: str | None

    def __post_init__(self) -> None:
        if type(self.raw_ordinal) is not int or self.raw_ordinal < 0:
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if type(self.kind) is not str or self.kind not in _DIAGNOSTIC_NODE_KINDS:
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if type(self.outcome) is not str or self.outcome not in ("PASS", "FAIL"):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if type(self.coordinates) is not tuple or not self.coordinates:
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        coordinates: list[tuple[str, float]] = []
        coordinate_names: set[str] = set()
        for pair in self.coordinates:
            if type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not str:
                _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
            if not pair[0] or pair[0] in coordinate_names:
                _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
            coordinate_names.add(pair[0])
            coordinates.append(
                (
                    pair[0],
                    _finite(pair[1], "W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID"),
                )
            )
        if type(self.phases) is not tuple:
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if any(type(phase) is not str or not phase for phase in self.phases):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        phases = tuple(sorted(self.phases))
        if len(set(phases)) != len(phases):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if self.outcome == "PASS":
            if not phases or self.reason_code is not None:
                _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        elif (
            type(self.reason_code) is not str
            or self.reason_code not in _FAILURE_REASONS
        ):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        object.__setattr__(self, "coordinates", tuple(coordinates))
        object.__setattr__(self, "phases", phases)


@_dataclass(frozen=True, slots=True)
class MappingDiagnosticSegment:
    """One true strategy connection between two successful raw attempts."""

    raw_ordinal: int
    kind: str
    start_raw_ordinal: int
    end_raw_ordinal: int
    phases: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            type(self.raw_ordinal) is not int
            or self.raw_ordinal < 0
            or type(self.start_raw_ordinal) is not int
            or self.start_raw_ordinal < 0
            or type(self.end_raw_ordinal) is not int
            or self.end_raw_ordinal < 0
            or self.start_raw_ordinal == self.end_raw_ordinal
            or type(self.kind) is not str
        ):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if type(self.phases) is not tuple or not self.phases:
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if any(type(phase) is not str or not phase for phase in self.phases):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        phases = tuple(sorted(self.phases))
        if len(set(phases)) != len(phases):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        object.__setattr__(self, "phases", phases)


@_dataclass(frozen=True, slots=True)
class StrategyExceptionBinding:
    """Stable type/message digest for one caught strategy exception."""

    exception_type: str
    message_sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.exception_type) is not str
            or not self.exception_type
            or len(self.exception_type) > 512
            or any(ord(character) < 0x21 or ord(character) > 0x7E for character in self.exception_type)
            or type(self.message_sha256) is not str
            or len(self.message_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.message_sha256)
        ):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")


def _strategy_exception_binding(error: BaseException) -> StrategyExceptionBinding:
    """Bind the exact caught exception class and a bounded stable message."""

    error_type = type(error)
    exception_type = f"{error_type.__module__}.{error_type.__qualname__}"
    try:
        message = str(error)
    except Exception:
        message = "<UNSTRINGIFIABLE_EXCEPTION>"
    payload = message.encode("utf-8", errors="backslashreplace")
    return StrategyExceptionBinding(
        exception_type=exception_type,
        message_sha256=_hashlib.sha256(payload).hexdigest(),
    )


def _copy_exception_binding(value: object) -> StrategyExceptionBinding:
    try:
        if type(value) is not StrategyExceptionBinding:
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        return StrategyExceptionBinding(
            exception_type=value.exception_type,
            message_sha256=value.message_sha256,
        )
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID"
        ) from error


@_dataclass(frozen=True, slots=True)
class CompleteMappingDiagnostics:
    """Attested complete trace required before a RawMappingLedger may exist."""

    schema_version: str
    diagnostics_complete: bool
    feature_id: str
    attempts: tuple[MappingDiagnosticAttempt, ...]
    segments: tuple[MappingDiagnosticSegment, ...]
    package_exposed_attempt_count: int
    package_exposed_segment_count: int
    completed: bool
    termination_reason_code: str
    backend_exception: StrategyExceptionBinding | None
    backend_exception_attempt_ordinal: int | None

    def __post_init__(self) -> None:
        if (
            type(self.schema_version) is not str
            or self.schema_version != COMPLETE_DIAGNOSTICS_SCHEMA
            or type(self.diagnostics_complete) is not bool
            or self.diagnostics_complete is not True
            or type(self.feature_id) is not str
            or self.feature_id not in SUPPORTED_MAPPING_FEATURES
            or type(self.attempts) is not tuple
            or not self.attempts
            or type(self.segments) is not tuple
            or any(type(item) is not MappingDiagnosticAttempt for item in self.attempts)
            or any(type(item) is not MappingDiagnosticSegment for item in self.segments)
            or type(self.package_exposed_attempt_count) is not int
            or type(self.package_exposed_segment_count) is not int
            or self.package_exposed_attempt_count != len(self.attempts)
            or self.package_exposed_segment_count != len(self.segments)
            or type(self.completed) is not bool
            or type(self.termination_reason_code) is not str
            or self.termination_reason_code not in _TERMINATIONS
            or (
                self.backend_exception is not None
                and type(self.backend_exception) is not StrategyExceptionBinding
            )
            or (
                self.backend_exception_attempt_ordinal is not None
                and type(self.backend_exception_attempt_ordinal) is not int
            )
        ):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        attempts = tuple(_copy_diagnostic_attempt(item) for item in self.attempts)
        segments = tuple(_copy_diagnostic_segment(item) for item in self.segments)
        exception_binding = (
            None
            if self.backend_exception is None
            else _copy_exception_binding(self.backend_exception)
        )
        if tuple(item.raw_ordinal for item in attempts) != tuple(range(len(attempts))):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if tuple(item.raw_ordinal for item in segments) != tuple(range(len(segments))):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if self.completed:
            if self.termination_reason_code != "W2B_MAP_COMPLETED":
                _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        elif self.termination_reason_code == "W2B_MAP_COMPLETED":
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if not self.completed and not any(
            item.outcome == "FAIL" for item in attempts
        ):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if (
            self.termination_reason_code
            == "W2B_MAP_TERMINATED_BACKEND_FAILURE"
            and attempts[-1].outcome != "FAIL"
        ):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if exception_binding is not None and (
            self.completed
            or self.termination_reason_code
            != "W2B_MAP_TERMINATED_BACKEND_FAILURE"
            or attempts[-1].outcome != "FAIL"
            or self.backend_exception_attempt_ordinal
            != attempts[-1].raw_ordinal
        ):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        if (
            exception_binding is None
            and self.backend_exception_attempt_ordinal is not None
        ):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        object.__setattr__(self, "attempts", attempts)
        object.__setattr__(self, "segments", segments)
        object.__setattr__(self, "backend_exception", exception_binding)


def _copy_diagnostic_attempt(value: object) -> MappingDiagnosticAttempt:
    try:
        if type(value) is not MappingDiagnosticAttempt:
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        return MappingDiagnosticAttempt(
            raw_ordinal=value.raw_ordinal,
            kind=value.kind,
            outcome=value.outcome,
            coordinates=tuple((name, amount) for name, amount in value.coordinates),
            phases=tuple(value.phases),
            reason_code=value.reason_code,
        )
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID"
        ) from error


def _copy_diagnostic_segment(value: object) -> MappingDiagnosticSegment:
    try:
        if type(value) is not MappingDiagnosticSegment:
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        return MappingDiagnosticSegment(
            raw_ordinal=value.raw_ordinal,
            kind=value.kind,
            start_raw_ordinal=value.start_raw_ordinal,
            end_raw_ordinal=value.end_raw_ordinal,
            phases=tuple(value.phases),
        )
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID"
        ) from error


def _copy_complete_diagnostics(value: object) -> CompleteMappingDiagnostics:
    try:
        if type(value) is not CompleteMappingDiagnostics:
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        return CompleteMappingDiagnostics(
            schema_version=value.schema_version,
            diagnostics_complete=value.diagnostics_complete,
            feature_id=value.feature_id,
            attempts=tuple(_copy_diagnostic_attempt(item) for item in value.attempts),
            segments=tuple(_copy_diagnostic_segment(item) for item in value.segments),
            package_exposed_attempt_count=value.package_exposed_attempt_count,
            package_exposed_segment_count=value.package_exposed_segment_count,
            completed=value.completed,
            termination_reason_code=value.termination_reason_code,
            backend_exception=(
                None
                if value.backend_exception is None
                else _copy_exception_binding(value.backend_exception)
            ),
            backend_exception_attempt_ordinal=(
                value.backend_exception_attempt_ordinal
            ),
        )
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID"
        ) from error


@_dataclass(frozen=True, slots=True)
class _SolverModules:
    Database: object
    BinaryStrategy: object
    IsoplethStrategy: object
    TernaryStrategy: object
    variables: object
    version: str


def _load_solver_modules() -> _SolverModules:
    """Load pycalphad only for an actual active-lease mapping operation."""

    try:
        pycalphad = _importlib.import_module("pycalphad")
        mapping = _importlib.import_module("pycalphad.mapping")
        version = getattr(pycalphad, "__version__", None)
        modules = _SolverModules(
            Database=getattr(pycalphad, "Database"),
            BinaryStrategy=getattr(mapping, "BinaryStrategy"),
            IsoplethStrategy=getattr(mapping, "IsoplethStrategy"),
            TernaryStrategy=getattr(mapping, "TernaryStrategy"),
            variables=getattr(pycalphad, "variables"),
            version=version,
        )
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_PYCALPHAD_UNAVAILABLE"
        ) from error
    if type(modules.version) is not str or modules.version != PYCALPHAD_VERSION:
        _fail("W2B_MAPPING_BACKEND_PYCALPHAD_VERSION_MISMATCH")
    return modules


def _default_strategy_factory(
    strategy_class: object,
    database: object,
    components: list[str],
    phases: list[str],
    conditions: dict[object, object],
    options: dict[str, object],
) -> object:
    if not callable(strategy_class):
        _fail("W2B_MAPPING_BACKEND_STRATEGY_CONSTRUCTION_FAILED")
    return strategy_class(database, components, phases, conditions, **options)


@_dataclass(frozen=True, slots=True)
class _V2PointObservation:
    global_coordinates: tuple[tuple[str, float], ...]
    phase_local_coordinates: tuple[
        tuple[str, tuple[tuple[str, float], ...]], ...
    ]
    phase_instances: tuple[_v2.PhaseInstanceV2, ...]


def _solver_scalar(value: object) -> float:
    """Read one public solver scalar without importing its numeric package."""

    if type(value) is bool:
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    candidate = value
    if type(candidate) not in (int, float):
        try:
            item = getattr(candidate, "item", None)
            if callable(item):
                candidate = item()
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
            ) from error
    if type(candidate) is bool:
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    try:
        number = float(candidate)
    except (OverflowError, TypeError, ValueError) as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
        ) from error
    if not _math.isfinite(number):
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    return 0.0 if number == 0.0 else number


def _condition_coordinate_name(value: object) -> str:
    """Use stable public state-variable metadata, including X(component)."""

    try:
        species = getattr(value, "species", None)
        phase_name = getattr(value, "phase_name", None)
        if species is not None:
            component = str(species).upper()
            if phase_name is None:
                name = f"X({component})"
            else:
                name = f"X({str(phase_name).upper()},{component})"
        else:
            name = str(value).upper()
        allowed = frozenset(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_#:+-.()/,[]"
        )
        if not name or len(name) > 96 or any(char not in allowed for char in name):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        return name
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
        ) from error


def _global_coordinates(point: object) -> tuple[tuple[str, float], ...]:
    try:
        conditions = getattr(point, "global_conditions")
        if not isinstance(conditions, _Mapping) or not conditions:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        rows = tuple(
            sorted(
                (
                    (_condition_coordinate_name(key), _solver_scalar(value))
                    for key, value in conditions.items()
                ),
                key=lambda pair: pair[0],
            )
        )
        if len({name for name, _value in rows}) != len(rows):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        return rows
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
        ) from error


def _point_observation(
    point: object,
    request: _path.MappingRequest,
) -> _V2PointObservation:
    """Translate one exact public Point/Node, normalizing multiplicity groups."""

    try:
        request_components = request.components
        if (
            type(request_components) is not tuple
            or len(request_components) < 3
            or any(type(component) is not str for component in request_components)
            or request_components[-1] != "VA"
        ):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        expected_nonvacant_elements = request_components[:-1]
        if (
            not expected_nonvacant_elements
            or "VA" in expected_nonvacant_elements
            or tuple(sorted(expected_nonvacant_elements))
            != expected_nonvacant_elements
            or len(set(expected_nonvacant_elements))
            != len(expected_nonvacant_elements)
        ):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        expected_nonvacant_set = frozenset(expected_nonvacant_elements)
        composition_sets = getattr(point, "stable_composition_sets")
        if (
            type(composition_sets) not in (list, tuple)
            or not composition_sets
            or len(composition_sets) > 65_535
        ):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        bases: list[str] = []
        for composition_set in composition_sets:
            phase_record = getattr(composition_set, "phase_record")
            base_phase = str(getattr(phase_record, "phase_name")).upper()
            if not base_phase or "#" in base_phase:
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
            bases.append(base_phase)
        totals: dict[str, int] = {}
        for base_phase in bases:
            totals[base_phase] = totals.get(base_phase, 0) + 1
        seen: dict[str, int] = {}
        instances: list[_v2.PhaseInstanceV2] = []
        locals_by_instance: list[
            tuple[str, tuple[tuple[str, float], ...]]
        ] = []
        for composition_set, base_phase in zip(composition_sets, bases):
            index = seen.get(base_phase, 0) + 1
            seen[base_phase] = index
            instance_name = (
                f"{base_phase}#{index}"
                if totals[base_phase] > 1
                else base_phase
            )
            instance = _v2.PhaseInstanceV2(
                instance_name=instance_name,
                base_phase=base_phase,
                instance_index=index,
            )
            phase_record = getattr(composition_set, "phase_record")
            elements = getattr(phase_record, "nonvacant_elements")
            fractions = getattr(composition_set, "X")
            if (
                type(elements) not in (list, tuple)
                or not elements
                or len(elements) > 65_535
                or any(type(component) is not str for component in elements)
            ):
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
            element_names = tuple(elements)
            if (
                any(
                    component == "VA"
                    or component != component.upper()
                    or component not in expected_nonvacant_set
                    for component in element_names
                )
                or len(set(element_names)) != len(element_names)
                or element_names != expected_nonvacant_elements
            ):
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
            try:
                fraction_count = len(fractions)
            except Exception as error:
                raise Wave2BMappingBackendError(
                    "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
                ) from error
            if len(element_names) != fraction_count:
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
            local_rows = [
                (f"X({component})", _solver_scalar(amount))
                for component, amount in zip(element_names, fractions)
            ]
            local_rows.append(("NP", _solver_scalar(getattr(composition_set, "NP"))))
            if len({name for name, _value in local_rows}) != len(local_rows):
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
            instances.append(instance)
            locals_by_instance.append((instance_name, tuple(local_rows)))

        global_rows = _global_coordinates(point)
        global_names = {name for name, _value in global_rows}
        expected_names = {"P", "N", "T", *request.coordinate_names}
        if type(request) is _path.MulticomponentIsoplethRequest:
            expected_names.update(
                f"X({name})" for name, _amount in request.fixed_composition
            )
        if global_names != expected_names:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        global_values = dict(global_rows)
        if (
            not _same_binary64(global_values["P"], request.pressure_pa)
            or not _same_binary64(global_values["N"], 1.0)
        ):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        if type(request) is _path.BinaryPhaseDiagramRequest:
            fraction = global_values[request.coordinate_names[0]]
            temperature = global_values["T"]
            if (
                not _within_postrun_mole_fraction_interval(
                    request.feature,
                    fraction,
                    request.right_fraction.lower,
                    request.right_fraction.upper,
                )
                or not request.temperature_k.lower
                <= temperature
                <= request.temperature_k.upper
            ):
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        elif type(request) is _path.MulticomponentIsoplethRequest:
            fraction = global_values[request.coordinate_names[0]]
            temperature = global_values["T"]
            if (
                not _within_postrun_mole_fraction_interval(
                    request.feature,
                    fraction,
                    request.variable_fraction.lower,
                    request.variable_fraction.upper,
                )
                or not request.temperature_k.lower
                <= temperature
                <= request.temperature_k.upper
                or any(
                    not _within_postrun_fixed_condition(
                        request.feature,
                        global_values[f"X({name})"],
                        amount,
                    )
                    for name, amount in request.fixed_composition
                )
            ):
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        else:
            x_fraction = global_values[request.coordinate_names[0]]
            y_fraction = global_values[request.coordinate_names[1]]
            if (
                not _same_binary64(global_values["T"], request.temperature_k)
                or not _within_postrun_mole_fraction_interval(
                    request.feature, x_fraction, 0.0, 1.0
                )
                or not _within_postrun_mole_fraction_interval(
                    request.feature, y_fraction, 0.0, 1.0
                )
                or not _within_postrun_mole_fraction_interval(
                    request.feature, x_fraction + y_fraction, 0.0, 1.0
                )
            ):
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        return _V2PointObservation(
            global_coordinates=global_rows,
            phase_local_coordinates=tuple(locals_by_instance),
            phase_instances=tuple(instances),
        )
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
        ) from error


def _phase_instance_union(
    observations: tuple[_V2PointObservation, ...],
) -> tuple[_v2.PhaseInstanceV2, ...]:
    by_name: dict[str, _v2.PhaseInstanceV2] = {}
    for observation in observations:
        for instance in observation.phase_instances:
            previous = by_name.get(instance.instance_name)
            if previous is not None and previous != instance:
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
            by_name[instance.instance_name] = instance
    groups: dict[str, list[_v2.PhaseInstanceV2]] = {}
    for item in by_name.values():
        groups.setdefault(item.base_phase, []).append(item)
    for base_phase, group in groups.items():
        ordered = sorted(group, key=lambda item: item.instance_index)
        if [item.instance_index for item in ordered] != list(
            range(1, len(ordered) + 1)
        ):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        if len(ordered) > 1 and any(
            item.instance_name != f"{base_phase}#{item.instance_index}"
            for item in ordered
        ):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    return tuple(
        sorted(
            by_name.values(),
            key=lambda item: (
                item.base_phase,
                item.instance_index,
                item.instance_name,
            ),
        )
    )


def _phase_instance_intersection(
    observations: tuple[_V2PointObservation, ...],
) -> tuple[_v2.PhaseInstanceV2, ...]:
    if not observations:
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    common_names = {
        item.instance_name for item in observations[0].phase_instances
    }
    for observation in observations[1:]:
        common_names &= {
            item.instance_name for item in observation.phase_instances
        }
    if not common_names:
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    return tuple(
        item
        for item in observations[0].phase_instances
        if item.instance_name in common_names
    )


class _V2ProjectionBuilder:
    """Build separate post-run evidence and topology collections exactly once."""

    __slots__ = (
        "budget",
        "evidence",
        "nodes",
        "segments",
        "regions",
        "_node_source_index",
        "_line_source_index",
        "_region_source_index",
    )

    def __init__(self, budget: int) -> None:
        self.budget = budget
        self.evidence: list[_v2.MappingPostrunEvidenceRecordV2] = []
        self.nodes: list[_v2.TopologyNode] = []
        self.segments: list[_v2.TopologySegment] = []
        self.regions: list[_v2.TopologyRegion] = []
        self._node_source_index = 0
        self._line_source_index = 0
        self._region_source_index = 0

    def _reserve_evidence(self, source_collection: str) -> tuple[int, int]:
        ordinal = len(self.evidence)
        if ordinal >= self.budget:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_BUDGET_EXCEEDED")
        if source_collection == "PUBLIC_NODE_RECORDS":
            source_index = self._node_source_index
            self._node_source_index += 1
        elif source_collection == "PUBLIC_LINE_RECORDS":
            source_index = self._line_source_index
            self._line_source_index += 1
        elif source_collection == "PUBLIC_REGION_RECORDS":
            source_index = self._region_source_index
            self._region_source_index += 1
        else:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        return ordinal, source_index

    def add_node(
        self,
        *,
        observation: _V2PointObservation,
        node_id: str,
        component_id: str,
        node_kind: str,
        phase_instances: tuple[_v2.PhaseInstanceV2, ...] | None = None,
        phase_local_coordinates: tuple[
            tuple[str, tuple[tuple[str, float], ...]], ...
        ] | None = None,
    ) -> str:
        evidence_ordinal, source_index = self._reserve_evidence(
            "PUBLIC_NODE_RECORDS"
        )
        if phase_instances is None:
            phase_instances = observation.phase_instances
        if phase_local_coordinates is None:
            phase_local_coordinates = observation.phase_local_coordinates
        role_by_kind = {
            "STARTING_POINT": "STARTING_NODE_OBSERVATION",
            "TERMINAL_NODE": "EXIT_NODE_OBSERVATION",
            "ZPF_NODE": "ZPF_NODE_OBSERVATION",
            "TIELINE_ENDPOINT": "TIELINE_ENDPOINT_OBSERVATION",
            "INVARIANT_NODE": "INVARIANT_NODE_OBSERVATION",
            "MULTIPHASE_NODE": "MULTIPHASE_NODE_OBSERVATION",
        }
        evidence_role = role_by_kind.get(node_kind)
        if evidence_role is None:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        evidence_id = f"postrun.node.{evidence_ordinal:08d}"
        evidence = _v2.MappingPostrunEvidenceRecordV2(
            ordinal=evidence_ordinal,
            evidence_id=evidence_id,
            source_collection="PUBLIC_NODE_RECORDS",
            source_record_index=source_index,
            evidence_role=evidence_role,
            status="RESOLVED",
            topology_component_id=component_id,
            topology_target_id=node_id,
            member_node_ids=tuple(),
            global_coordinates=observation.global_coordinates,
            phase_local_coordinates=phase_local_coordinates,
            phase_instances=phase_instances,
            diagnostic_reason=None,
        )
        node = _v2.TopologyNode(
            ordinal=len(self.nodes),
            node_id=node_id,
            topology_component_id=component_id,
            node_kind=node_kind,
            global_coordinates=observation.global_coordinates,
            phase_local_coordinates=phase_local_coordinates,
            phase_instances=phase_instances,
            base_phases=tuple(
                sorted({item.base_phase for item in phase_instances})
            ),
            evidence_record_ids=(evidence_id,),
        )
        self.evidence.append(evidence)
        self.nodes.append(node)
        return node_id

    def add_segment(
        self,
        *,
        observations: tuple[_V2PointObservation, _V2PointObservation],
        segment_id: str,
        component_id: str,
        start_node_id: str,
        end_node_id: str,
        segment_kind: str,
        phase_instances: tuple[_v2.PhaseInstanceV2, ...] | None = None,
    ) -> None:
        evidence_ordinal, source_index = self._reserve_evidence(
            "PUBLIC_LINE_RECORDS"
        )
        if phase_instances is None:
            phase_instances = _phase_instance_intersection(observations)
        evidence_id = f"postrun.line.{evidence_ordinal:08d}"
        member_ids = (start_node_id, end_node_id)
        role_by_kind = {
            "SEQUENTIAL_ZPF": "SEQUENTIAL_ZPF_LINE_OBSERVATION",
            "EXPLICIT_TIELINE": "EXPLICIT_TIELINE_OBSERVATION",
        }
        evidence_role = role_by_kind.get(segment_kind)
        if evidence_role is None:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        evidence = _v2.MappingPostrunEvidenceRecordV2(
            ordinal=evidence_ordinal,
            evidence_id=evidence_id,
            source_collection="PUBLIC_LINE_RECORDS",
            source_record_index=source_index,
            evidence_role=evidence_role,
            status="RESOLVED",
            topology_component_id=component_id,
            topology_target_id=segment_id,
            member_node_ids=member_ids,
            global_coordinates=None,
            phase_local_coordinates=None,
            phase_instances=phase_instances,
            diagnostic_reason=None,
        )
        segment = _v2.TopologySegment(
            ordinal=len(self.segments),
            segment_id=segment_id,
            topology_component_id=component_id,
            segment_kind=segment_kind,
            start_node_id=start_node_id,
            end_node_id=end_node_id,
            phase_instances=phase_instances,
            base_phases=tuple(
                sorted({item.base_phase for item in phase_instances})
            ),
            evidence_record_ids=(evidence_id,),
        )
        self.evidence.append(evidence)
        self.segments.append(segment)

    def add_region(
        self,
        *,
        observations: tuple[_V2PointObservation, ...],
        region_id: str,
        component_id: str,
        member_node_ids: tuple[str, ...],
        region_kind: str,
        phase_instances: tuple[_v2.PhaseInstanceV2, ...] | None = None,
    ) -> None:
        evidence_ordinal, source_index = self._reserve_evidence(
            "PUBLIC_REGION_RECORDS"
        )
        if phase_instances is None:
            phase_instances = _phase_instance_union(observations)
        evidence_id = f"postrun.region.{evidence_ordinal:08d}"
        role_by_kind = {
            "INVARIANT_REGION": "INVARIANT_REGION_OBSERVATION",
            "MULTIPHASE_REGION": "MULTIPHASE_REGION_OBSERVATION",
        }
        evidence_role = role_by_kind.get(region_kind)
        if evidence_role is None:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        evidence = _v2.MappingPostrunEvidenceRecordV2(
            ordinal=evidence_ordinal,
            evidence_id=evidence_id,
            source_collection="PUBLIC_REGION_RECORDS",
            source_record_index=source_index,
            evidence_role=evidence_role,
            status="RESOLVED",
            topology_component_id=component_id,
            topology_target_id=region_id,
            member_node_ids=member_node_ids,
            global_coordinates=None,
            phase_local_coordinates=None,
            phase_instances=phase_instances,
            diagnostic_reason=None,
        )
        region = _v2.TopologyRegion(
            ordinal=len(self.regions),
            region_id=region_id,
            topology_component_id=component_id,
            region_kind=region_kind,
            member_node_ids=member_node_ids,
            phase_instances=phase_instances,
            base_phases=tuple(
                sorted({item.base_phase for item in phase_instances})
            ),
            evidence_record_ids=(evidence_id,),
        )
        self.evidence.append(evidence)
        self.regions.append(region)

    def add_unresolved_line_status(
        self,
        *,
        component_id: str,
        member_node_ids: tuple[str, ...],
    ) -> None:
        evidence_ordinal, source_index = self._reserve_evidence(
            "PUBLIC_LINE_RECORDS"
        )
        evidence = _v2.MappingPostrunEvidenceRecordV2(
            ordinal=evidence_ordinal,
            evidence_id=f"postrun.unresolved.{evidence_ordinal:08d}",
            source_collection="PUBLIC_LINE_RECORDS",
            source_record_index=source_index,
            evidence_role="UNRESOLVED_LINE_STATUS",
            status="UNRESOLVED",
            topology_component_id=component_id,
            topology_target_id=None,
            member_node_ids=member_node_ids,
            global_coordinates=None,
            phase_local_coordinates=None,
            phase_instances=tuple(),
            diagnostic_reason=_v2.StructuredDiagnosticReasonV2(
                code="MAPPING_LINE_STATUS_UNRESOLVED",
                category="MAPPING_POSTRUN_TOPOLOGY",
                severity="WARNING",
            ),
        )
        self.evidence.append(evidence)


def _public_sequence(value: object) -> tuple[object, ...]:
    if type(value) not in (list, tuple):
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    return tuple(value)


def _line_point_observation(
    line: object,
    point: object,
    request: _path.MappingRequest,
) -> tuple[_V2PointObservation, _V2PointObservation]:
    """Return the full point and its exact line-phase subset."""

    full = _point_observation(point, request)
    try:
        line_phases = _public_sequence(getattr(line, "stable_phases"))
        if not line_phases or any(type(item) is not str for item in line_phases):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        requested_bases = tuple(str(item).upper() for item in line_phases)
        point_by_base: dict[str, list[_v2.PhaseInstanceV2]] = {}
        for instance in full.phase_instances:
            point_by_base.setdefault(instance.base_phase, []).append(instance)
        line_counts: dict[str, int] = {}
        for base_phase in requested_bases:
            line_counts[base_phase] = line_counts.get(base_phase, 0) + 1
        selected: list[_v2.PhaseInstanceV2] = []
        for base_phase, required_count in line_counts.items():
            candidates = point_by_base.get(base_phase, [])
            # Selecting one member from a larger same-base multiplicity group
            # is ambiguous, even though selecting an extra distinct node phase is not.
            if len(candidates) != required_count:
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
            selected.extend(candidates)
        if len(selected) != len(requested_bases):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        selected_names = {item.instance_name for item in selected}
        local = tuple(
            row
            for row in full.phase_local_coordinates
            if row[0] in selected_names
        )
        if len(local) != len(selected):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        line_observation = _V2PointObservation(
            global_coordinates=full.global_coordinates,
            phase_local_coordinates=local,
            phase_instances=tuple(selected),
        )
        return full, line_observation
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
        ) from error


def _tieline_endpoint_observation(
    observation: _V2PointObservation,
    instance: _v2.PhaseInstanceV2,
) -> _V2PointObservation:
    local = tuple(
        row
        for row in observation.phase_local_coordinates
        if row[0] == instance.instance_name
    )
    if len(local) != 1:
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    return _V2PointObservation(
        global_coordinates=observation.global_coordinates,
        phase_local_coordinates=local,
        # V2.1 requires both tieline endpoints to carry the same exact phase
        # assemblage.  The one phase-local row identifies which physical end
        # is observed without dropping the other phase instance.
        phase_instances=observation.phase_instances,
    )


def _explicitize_multiplicity(
    observation: _V2PointObservation,
    explicit_bases: frozenset[str],
) -> _V2PointObservation:
    """Use BASE#1 globally whenever any public record exposes BASE#2+."""

    renamed: dict[str, str] = {}
    instances: list[_v2.PhaseInstanceV2] = []
    for instance in observation.phase_instances:
        name = (
            f"{instance.base_phase}#{instance.instance_index}"
            if instance.base_phase in explicit_bases
            else instance.instance_name
        )
        renamed[instance.instance_name] = name
        instances.append(
            _v2.PhaseInstanceV2(
                instance_name=name,
                base_phase=instance.base_phase,
                instance_index=instance.instance_index,
            )
        )
    local = tuple(
        (renamed[name], coordinates)
        for name, coordinates in observation.phase_local_coordinates
    )
    return _V2PointObservation(
        global_coordinates=observation.global_coordinates,
        phase_local_coordinates=local,
        phase_instances=tuple(instances),
    )


def _line_status_is_unresolved(line: object) -> bool:
    try:
        status = getattr(line, "status")
        name = getattr(status, "name", status)
        if type(name) is not str:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        if name in ("NEW_NODE_FOUND", "REACHED_LIMIT"):
            return False
        if name in ("NOT_FINISHED", "FAILED", "ATTEMPT_NEW_STEP"):
            return True
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
        ) from error
    raise AssertionError("unreachable")


def _public_node_kind(
    node: object,
    *,
    is_invariant: bool,
) -> str:
    """Classify a public queue node only from its exposed origin semantics."""

    if is_invariant:
        return "INVARIANT_NODE"
    try:
        parent = getattr(node, "parent")
        exit_hint = getattr(node, "exit_hint", None)
        if exit_hint is None:
            # Structural test doubles expose the unambiguous parent relation.
            return "STARTING_POINT" if parent is None else "TERMINAL_NODE"
        hint_name = getattr(exit_hint, "name", exit_hint)
        if type(hint_name) is not str:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        if parent is None or hint_name == "POINT_IS_EXIT":
            return "STARTING_POINT"
        if hint_name == "NORMAL":
            return "TERMINAL_NODE"
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
        ) from error
    raise AssertionError("unreachable")


def _mapping_axes(
    request: _path.MappingRequest,
    variables: object,
) -> tuple[object, object]:
    try:
        mole_fraction = getattr(variables, "X")
        temperature = getattr(variables, "T")
        if type(request) is _path.BinaryPhaseDiagramRequest:
            return mole_fraction(request.right_component), temperature
        if type(request) is _path.MulticomponentIsoplethRequest:
            return mole_fraction(request.variable_component), temperature
        return (
            mole_fraction(request.x_component),
            mole_fraction(request.y_component),
        )
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
        ) from error


def _public_numeric_vector(value: object) -> tuple[float, ...]:
    """Copy one public scalar or one-dimensional numeric vector exactly."""

    candidate = value
    if type(candidate) not in (list, tuple):
        try:
            to_list = getattr(candidate, "tolist", None)
            if callable(to_list):
                candidate = to_list()
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
            ) from error
    if type(candidate) not in (list, tuple):
        return (_solver_scalar(candidate),)
    if not candidate or any(type(item) in (list, tuple) for item in candidate):
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    return tuple(_solver_scalar(item) for item in candidate)


def _normalized_view_phase_name(
    value: object,
    explicit_bases: frozenset[str],
) -> str:
    if type(value) is not str:
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    name = value.upper()
    if not name:
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    if "#" in name:
        base, separator, index_text = name.rpartition("#")
        if (
            separator != "#"
            or not base
            or not index_text.isdecimal()
            or int(index_text) < 1
        ):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        return f"{base}#{int(index_text)}"
    return f"{name}#1" if name in explicit_bases else name


def _observation_coordinate(
    observation: _V2PointObservation,
    instance_name: str,
    coordinate_name: str,
    *,
    phase_specific_mole_fraction: bool,
) -> float:
    rows: tuple[tuple[str, float], ...]
    if phase_specific_mole_fraction and coordinate_name.startswith("X("):
        matching = tuple(
            coordinates
            for name, coordinates in observation.phase_local_coordinates
            if name == instance_name
        )
        if len(matching) != 1:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        rows = matching[0]
    else:
        rows = observation.global_coordinates
    values = tuple(value for name, value in rows if name == coordinate_name)
    if len(values) != 1:
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    return values[0]


def _validate_phase_region_view(
    region_data: object,
    observations: tuple[_V2PointObservation, ...],
    coordinate_names: tuple[str, str],
    explicit_bases: frozenset[str],
    *,
    phase_specific_mole_fraction: bool,
) -> None:
    """Bind public plotting-view phase rows back to their exact public points."""

    if not observations:
        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    try:
        items = _public_sequence(getattr(region_data, "data"))
        expected_instances = observations[0].phase_instances
        expected_names = tuple(
            instance.instance_name for instance in expected_instances
        )
        if not items or len(items) != len(expected_instances):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        for observation in observations[1:]:
            if tuple(
                item.instance_name for item in observation.phase_instances
            ) != expected_names:
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        actual_names = tuple(
            _normalized_view_phase_name(
                getattr(item, "phase"), explicit_bases
            )
            for item in items
        )
        if actual_names != expected_names:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        x_name, y_name = coordinate_names
        for item, instance in zip(items, expected_instances):
            actual_x = _public_numeric_vector(getattr(item, "x"))
            actual_y = _public_numeric_vector(getattr(item, "y"))
            expected_x = tuple(
                _observation_coordinate(
                    observation,
                    instance.instance_name,
                    x_name,
                    phase_specific_mole_fraction=(
                        phase_specific_mole_fraction
                    ),
                )
                for observation in observations
            )
            expected_y = tuple(
                _observation_coordinate(
                    observation,
                    instance.instance_name,
                    y_name,
                    phase_specific_mole_fraction=(
                        phase_specific_mole_fraction
                    ),
                )
                for observation in observations
            )
            if (
                len(actual_x) != len(expected_x)
                or len(actual_y) != len(expected_y)
                or any(
                    not _same_binary64(actual, expected)
                    for actual, expected in zip(actual_x, expected_x)
                )
                or any(
                    not _same_binary64(actual, expected)
                    for actual, expected in zip(actual_y, expected_y)
                )
            ):
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
        ) from error


def _validate_public_strategy_views(
    strategy: object,
    request: _path.MappingRequest,
    variables: object,
    *,
    node_observations: tuple[_V2PointObservation, ...],
    public_lines: tuple[object, ...],
    line_records: tuple[
        tuple[
            tuple[_V2PointObservation, ...],
            tuple[_V2PointObservation, ...],
            bool,
        ],
        ...,
    ],
    invariant_indices: tuple[int, ...],
    explicit_bases: frozenset[str],
) -> None:
    """Cross-check every documented invariant/tieline/ZPF public view."""

    x_axis, y_axis = _mapping_axes(request, variables)
    try:
        invariant_method = getattr(strategy, "get_invariant_data", None)
        if not callable(invariant_method):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        invariant_data = _public_sequence(invariant_method(x_axis, y_axis))
        if type(request) is _path.MulticomponentIsoplethRequest:
            # The isopleth view contains derived polytope intersections rather
            # than raw queue-node coordinates.  Until those derived records
            # have an unambiguous DTO representation, refuse rather than
            # attach them to the wrong node or invent a region geometry.
            if invariant_data or invariant_indices:
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        else:
            if len(invariant_data) != len(invariant_indices):
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
            for data, node_index in zip(invariant_data, invariant_indices):
                _validate_phase_region_view(
                    data,
                    (node_observations[node_index],),
                    request.coordinate_names,
                    explicit_bases,
                    phase_specific_mole_fraction=True,
                )

        if type(request) in (
            _path.BinaryPhaseDiagramRequest,
            _path.TernaryPhaseDiagramRequest,
        ):
            tieline_method = getattr(strategy, "get_tieline_data", None)
            if not callable(tieline_method):
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
            tieline_data = _public_sequence(tieline_method(x_axis, y_axis))
            if len(tieline_data) != len(line_records):
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
            for data, (_full, line_observations, _unresolved) in zip(
                tieline_data, line_records
            ):
                _validate_phase_region_view(
                    data,
                    line_observations,
                    request.coordinate_names,
                    explicit_bases,
                    phase_specific_mole_fraction=True,
                )
        elif line_records:
            zpf_method = getattr(strategy, "get_zpf_data", None)
            if not callable(zpf_method):
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
            zpf_data = zpf_method(x_axis, y_axis)
            data_items = _public_sequence(getattr(zpf_data, "data"))
            if len(data_items) != len(line_records):
                _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
            for item, line, (full_observations, _line, _unresolved) in zip(
                data_items, public_lines, line_records
            ):
                fixed_phases = _public_sequence(
                    getattr(line, "fixed_phases")
                )
                if len(fixed_phases) != 1:
                    _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
                phase_name = _normalized_view_phase_name(
                    getattr(item, "phase"), explicit_bases
                )
                expected_phase = _normalized_view_phase_name(
                    fixed_phases[0], explicit_bases
                )
                actual_x = _public_numeric_vector(getattr(item, "x"))
                actual_y = _public_numeric_vector(getattr(item, "y"))
                x_name, y_name = request.coordinate_names
                expected_x = tuple(
                    _observation_coordinate(
                        observation,
                        observation.phase_instances[0].instance_name,
                        x_name,
                        phase_specific_mole_fraction=False,
                    )
                    for observation in full_observations
                )
                expected_y = tuple(
                    _observation_coordinate(
                        observation,
                        observation.phase_instances[0].instance_name,
                        y_name,
                        phase_specific_mole_fraction=False,
                    )
                    for observation in full_observations
                )
                if (
                    phase_name != expected_phase
                    or len(actual_x) != len(expected_x)
                    or len(actual_y) != len(expected_y)
                    or any(
                        not _same_binary64(actual, expected)
                        for actual, expected in zip(actual_x, expected_x)
                    )
                    or any(
                        not _same_binary64(actual, expected)
                        for actual, expected in zip(actual_y, expected_y)
                    )
                ):
                    _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
        ) from error


def _project_public_mapping_v2(
    strategy: object,
    request: _path.MappingRequest,
    variables: object,
    evidence_record_budget: int,
) -> tuple[
    tuple[_v2.MappingPostrunEvidenceRecordV2, ...],
    tuple[_v2.TopologyNode, ...],
    tuple[_v2.TopologySegment, ...],
    tuple[_v2.TopologyRegion, ...],
    int,
]:
    """Project final public state; this is explicitly not internal chronology."""

    try:
        node_queue = getattr(strategy, "node_queue")
        public_nodes = _public_sequence(getattr(node_queue, "nodes"))
        public_lines = _public_sequence(getattr(strategy, "zpf_lines"))
    except Wave2BMappingBackendError:
        raise
    except Exception as error:
        raise Wave2BMappingBackendError(
            "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
        ) from error

    raw_node_observations = tuple(
        _point_observation(point, request) for point in public_nodes
    )
    invariant_indices = (
        tuple(
            index
            for index, observation in enumerate(raw_node_observations)
            if len(observation.phase_instances) == 3
        )
        if type(request)
        in (_path.BinaryPhaseDiagramRequest, _path.TernaryPhaseDiagramRequest)
        else tuple()
    )
    raw_lines: list[
        tuple[
            tuple[_V2PointObservation, ...],
            tuple[_V2PointObservation, ...],
            bool,
        ]
    ] = []
    all_observations: list[_V2PointObservation] = list(
        raw_node_observations
    )
    for line in public_lines:
        try:
            points = _public_sequence(getattr(line, "points"))
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
            ) from error
        if not points:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        full_rows: list[_V2PointObservation] = []
        line_rows: list[_V2PointObservation] = []
        for point in points:
            full, line_observation = _line_point_observation(
                line, point, request
            )
            full_rows.append(full)
            line_rows.append(line_observation)
            all_observations.extend((full, line_observation))
        raw_lines.append(
            (
                tuple(full_rows),
                tuple(line_rows),
                _line_status_is_unresolved(line),
            )
        )
    explicit_bases = frozenset(
        instance.base_phase
        for observation in all_observations
        for instance in observation.phase_instances
        if instance.instance_index > 1
    )
    node_observations = tuple(
        _explicitize_multiplicity(observation, explicit_bases)
        for observation in raw_node_observations
    )
    line_records = tuple(
        (
            tuple(
                _explicitize_multiplicity(observation, explicit_bases)
                for observation in full_rows
            ),
            tuple(
                _explicitize_multiplicity(observation, explicit_bases)
                for observation in line_rows
            ),
            unresolved,
        )
        for full_rows, line_rows, unresolved in raw_lines
    )
    _validate_public_strategy_views(
        strategy,
        request,
        variables,
        node_observations=node_observations,
        public_lines=public_lines,
        line_records=line_records,
        invariant_indices=invariant_indices,
        explicit_bases=explicit_bases,
    )
    builder = _V2ProjectionBuilder(evidence_record_budget)
    node_ids: list[str] = []
    node_components: list[str] = []
    invariant_index_set = set(invariant_indices)
    for index, observation in enumerate(node_observations):
        component_id = f"component.node_queue.{index:08d}"
        node_id = f"node.node_queue.{index:08d}"
        node_kind = _public_node_kind(
            public_nodes[index],
            is_invariant=index in invariant_index_set,
        )
        builder.add_node(
            observation=observation,
            node_id=node_id,
            component_id=component_id,
            node_kind=node_kind,
        )
        node_ids.append(node_id)
        node_components.append(component_id)

    for index in invariant_indices:
        observation = node_observations[index]
        bases = {item.base_phase for item in observation.phase_instances}
        if len(bases) < 3:
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
        builder.add_region(
            observations=(observation,),
            region_id=f"region.invariant.{index:08d}",
            component_id=node_components[index],
            member_node_ids=(node_ids[index],),
            region_kind="INVARIANT_REGION",
            phase_instances=observation.phase_instances,
        )

    unresolved_count = 0
    for line_index, (
        full_observations,
        line_observations,
        line_unresolved,
    ) in enumerate(line_records):
        component_id = f"component.zpf_line.{line_index:08d}"
        line_node_ids: list[str] = []
        for point_index, full in enumerate(full_observations):
            node_id = f"node.zpf.{line_index:08d}.{point_index:08d}"
            builder.add_node(
                observation=full,
                node_id=node_id,
                component_id=component_id,
                node_kind="ZPF_NODE",
            )
            line_node_ids.append(node_id)
            if point_index:
                builder.add_segment(
                    observations=(
                        full_observations[point_index - 1],
                        full,
                    ),
                    segment_id=(
                        f"segment.zpf.{line_index:08d}."
                        f"{point_index - 1:08d}"
                    ),
                    component_id=component_id,
                    start_node_id=line_node_ids[point_index - 1],
                    end_node_id=node_id,
                    segment_kind="SEQUENTIAL_ZPF",
                    phase_instances=_phase_instance_intersection(
                        (
                            line_observations[point_index - 1],
                            line_observations[point_index],
                        )
                    ),
                )

        if line_unresolved:
            member_ids = (
                (line_node_ids[0],)
                if len(line_node_ids) == 1
                else (line_node_ids[0], line_node_ids[-1])
            )
            builder.add_unresolved_line_status(
                component_id=component_id,
                member_node_ids=member_ids,
            )
            unresolved_count += 1

        if type(request) in (
            _path.BinaryPhaseDiagramRequest,
            _path.TernaryPhaseDiagramRequest,
        ):
            for point_index, observation in enumerate(line_observations):
                if len(observation.phase_instances) < 2:
                    continue
                tieline_component = (
                    f"component.tieline.{line_index:08d}.{point_index:08d}"
                )
                endpoint_ids: list[str] = []
                endpoint_observations: list[_V2PointObservation] = []
                for phase_index, instance in enumerate(
                    observation.phase_instances
                ):
                    endpoint = _tieline_endpoint_observation(
                        observation, instance
                    )
                    endpoint_id = (
                        f"node.tieline.{line_index:08d}."
                        f"{point_index:08d}.{phase_index:04d}"
                    )
                    builder.add_node(
                        observation=endpoint,
                        node_id=endpoint_id,
                        component_id=tieline_component,
                        node_kind="TIELINE_ENDPOINT",
                    )
                    endpoint_ids.append(endpoint_id)
                    endpoint_observations.append(endpoint)
                if len(endpoint_ids) == 2:
                    builder.add_segment(
                        observations=(
                            endpoint_observations[0],
                            endpoint_observations[1],
                        ),
                        segment_id=(
                            f"segment.tieline.{line_index:08d}."
                            f"{point_index:08d}"
                        ),
                        component_id=tieline_component,
                        start_node_id=endpoint_ids[0],
                        end_node_id=endpoint_ids[1],
                        segment_kind="EXPLICIT_TIELINE",
                        phase_instances=observation.phase_instances,
                    )
                else:
                    if len(
                        {
                            item.base_phase
                            for item in observation.phase_instances
                        }
                    ) < 2:
                        _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID")
                    builder.add_region(
                        observations=tuple(endpoint_observations),
                        region_id=(
                            f"region.multiphase.{line_index:08d}."
                            f"{point_index:08d}"
                        ),
                        component_id=tieline_component,
                        member_node_ids=tuple(endpoint_ids),
                        region_kind="MULTIPHASE_REGION",
                        phase_instances=observation.phase_instances,
                    )

    if not builder.evidence or not builder.nodes:
        _fail("W2B_MAPPING_BACKEND_V2_NO_PUBLIC_OBSERVATIONS")
    return (
        tuple(builder.evidence),
        tuple(builder.nodes),
        tuple(builder.segments),
        tuple(builder.regions),
        unresolved_count,
    )


class ReceiptBoundMappingBackend:
    """MappingBackend bound to one exact active receipt execution window."""

    __slots__ = (
        "_domain",
        "_pre",
        "_lease",
        "_domain_bytes",
        "_pre_bytes",
        "_domain_digest",
        "_profile_digest",
        "_lease_id",
        "_snapshot_digest",
        "_runtime_path",
        "_family",
        "_profile",
        "_runtime_sha256",
        "_feature_id",
        "_candidate_phases",
        "_requested_phases",
        "_excluded_phases",
        "_effective_phases",
        "_full_request",
        "_bounds",
        "_solver_options",
        "_solver_modules",
        "_database_object",
        "_attempted_maps",
        "_completed_maps",
        "_failed_maps",
        "_last_diagnostic_state",
    )

    def __init__(
        self,
        *,
        domain_receipt: object,
        pre_snapshot: object,
        execution_lease: object,
    ) -> None:
        try:
            if (
                type(domain_receipt) is not _receipts.DomainReceipt
                or type(pre_snapshot) is not _receipts.PreExecutionSnapshot
                or type(execution_lease) is not _receipts.ExecutionLease
            ):
                _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")
            domain_bytes = _receipts.receipt_json_bytes(domain_receipt)
            pre_bytes = _receipts.receipt_json_bytes(pre_snapshot)
            profile = domain_receipt.profile_receipt
            if (
                domain_receipt.execution_mode != _receipts.INTERNAL_QUALIFICATION
                or domain_receipt.authorization_state
                != "INTERNAL_QUALIFICATION_ONLY_NOT_RELEASE"
                or profile.verification_mode != _receipts.INTERNAL_QUALIFICATION
            ):
                _fail("W2B_MAPPING_BACKEND_INTERNAL_QUALIFICATION_REQUIRED")
            if domain_receipt.feature_id not in SUPPORTED_MAPPING_FEATURES:
                _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")
            lease_id = execution_lease.lease_id
            snapshot_digest = execution_lease.execution_snapshot_digest
            runtime_path = execution_lease.file_path("runtime").resolve(strict=True)
            if (
                pre_snapshot.lease_id != lease_id
                or pre_snapshot.domain_receipt_digest
                != domain_receipt.canonical_digest
                or pre_snapshot.profile_receipt_digest != profile.canonical_digest
                or pre_snapshot.execution_snapshot_digest != snapshot_digest
            ):
                _fail("W2B_MAPPING_BACKEND_PRE_MISMATCH")
            if (
                profile.family not in SUPPORTED_DATABASE_FAMILIES
                or (
                    profile.family == "ni"
                    and profile.profile != "mc_ni_v2036"
                )
                or (
                    profile.family == "al"
                    and profile.profile != "mc_al_v2037"
                )
                or (
                    profile.family == "fe"
                    and (profile.family, profile.profile)
                    not in _EXACT_FE_PROFILE_ROLE
                )
            ):
                _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")
            if profile.family == "fe":
                if (
                    profile.profile not in SUPPORTED_FE_PROFILE_IDS
                    or profile.baseline_decision != _receipts.FE_POLICY_UNDECIDED
                    or profile.c15_exclusion_decision
                    != _receipts.FE_POLICY_UNDECIDED
                    or "C15_LAVES" not in domain_receipt.candidate_phases
                    or "C15_LAVES" not in domain_receipt.requested_phases
                    or "C15_LAVES" in domain_receipt.excluded_phases
                    or "C15_LAVES" not in domain_receipt.effective_phases
                ):
                    _fail("W2B_MAPPING_BACKEND_FE_POLICY_REQUIRED")
            elif profile.profile in SUPPORTED_FE_PROFILE_IDS:
                _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")

            self._domain = domain_receipt
            self._pre = pre_snapshot
            self._lease = execution_lease
            self._domain_bytes = bytes(domain_bytes)
            self._pre_bytes = bytes(pre_bytes)
            self._domain_digest = domain_receipt.canonical_digest
            self._profile_digest = profile.canonical_digest
            self._lease_id = lease_id
            self._snapshot_digest = snapshot_digest
            self._runtime_path = runtime_path
            self._family = profile.family
            self._profile = profile.profile
            self._runtime_sha256 = profile.runtime.sha256
            self._feature_id = domain_receipt.feature_id
            self._candidate_phases = tuple(domain_receipt.candidate_phases)
            self._requested_phases = tuple(domain_receipt.requested_phases)
            self._excluded_phases = tuple(domain_receipt.excluded_phases)
            self._effective_phases = tuple(domain_receipt.effective_phases)
            self._full_request = _payload_dict(domain_receipt.full_request)
            self._bounds = _payload_dict(domain_receipt.bounds)
            self._solver_options = _payload_dict(domain_receipt.solver_options)
            self._solver_modules: _SolverModules | None = None
            self._database_object: object | None = None
            self._attempted_maps = 0
            self._completed_maps = 0
            self._failed_maps = 0
            self._last_diagnostic_state = "NOT_RUN"
            self._validate_solver_options()
        except Wave2BMappingBackendError:
            raise
        except _receipts.ReceiptError as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_LEASE_INACTIVE"
            ) from error
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_CONTEXT_INVALID"
            ) from error
        self._guard()

    def _validate_solver_options(self) -> None:
        if set(self._solver_options) != {
            "global_min_pdensity",
            "max_iterations",
        }:
            _fail("W2B_MAPPING_BACKEND_SOLVER_OPTIONS_UNSUPPORTED")
        pdensity = self._solver_options["global_min_pdensity"]
        max_iterations = self._solver_options["max_iterations"]
        if (
            type(pdensity) is not int
            or isinstance(pdensity, bool)
            or not 1 <= pdensity <= 10_000
            or type(max_iterations) is not int
            or isinstance(max_iterations, bool)
            or (max_iterations != -1 and not 1 <= max_iterations <= 1_000_000)
        ):
            _fail("W2B_MAPPING_BACKEND_SOLVER_OPTIONS_UNSUPPORTED")

    def _guard_receipt_identity(self) -> None:
        try:
            current_profile = self._domain.profile_receipt
            receipt_mismatch = (
                type(self._domain) is not _receipts.DomainReceipt
                or type(self._pre) is not _receipts.PreExecutionSnapshot
                or type(self._lease) is not _receipts.ExecutionLease
                or _receipts.receipt_json_bytes(self._domain) != self._domain_bytes
                or _receipts.receipt_json_bytes(self._pre) != self._pre_bytes
                or self._domain.canonical_digest != self._domain_digest
                or current_profile.canonical_digest != self._profile_digest
                or self._pre.lease_id != self._lease_id
                or self._pre.domain_receipt_digest != self._domain_digest
                or self._pre.profile_receipt_digest != self._profile_digest
                or self._pre.execution_snapshot_digest != self._snapshot_digest
                or current_profile.family != self._family
                or current_profile.profile != self._profile
                or current_profile.runtime.sha256 != self._runtime_sha256
                or self._domain.feature_id != self._feature_id
                or tuple(self._domain.candidate_phases) != self._candidate_phases
                or tuple(self._domain.requested_phases) != self._requested_phases
                or tuple(self._domain.excluded_phases) != self._excluded_phases
                or tuple(self._domain.effective_phases) != self._effective_phases
                or _payload_dict(self._domain.full_request) != self._full_request
                or _payload_dict(self._domain.bounds) != self._bounds
                or _payload_dict(self._domain.solver_options)
                != self._solver_options
            )
            if receipt_mismatch:
                _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")
        except Wave2BMappingBackendError:
            raise
        except _receipts.ReceiptError as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_CONTEXT_INVALID"
            ) from error
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_CONTEXT_INVALID"
            ) from error
        try:
            if (
                self._lease.lease_id != self._lease_id
                or self._lease.execution_snapshot_digest != self._snapshot_digest
            ):
                _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")
        except Wave2BMappingBackendError:
            raise
        except _receipts.ReceiptError as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_LEASE_INACTIVE"
            ) from error
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_CONTEXT_INVALID"
            ) from error

    def _guard(self) -> _Path:
        self._guard_receipt_identity()
        try:
            path = self._lease.file_path("runtime").resolve(strict=True)
            if path != self._runtime_path or not path.is_file():
                _fail("W2B_MAPPING_BACKEND_RUNTIME_PATH_INVALID")
            return path
        except Wave2BMappingBackendError:
            raise
        except _receipts.ReceiptError as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_LEASE_INACTIVE"
            ) from error
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_CONTEXT_INVALID"
            ) from error

    def _modules(self) -> _SolverModules:
        self._guard()
        if self._solver_modules is None:
            self._solver_modules = _load_solver_modules()
        if type(self._solver_modules) is not _SolverModules:
            _fail("W2B_MAPPING_BACKEND_CONTEXT_INVALID")
        return self._solver_modules

    def _database(self) -> object:
        runtime_path = self._guard()
        if self._database_object is None:
            modules = self._modules()
            try:
                self._database_object = modules.Database(str(runtime_path))  # type: ignore[operator]
            except Exception as error:
                raise Wave2BMappingBackendError(
                    "W2B_MAPPING_BACKEND_DATABASE_LOAD_FAILED"
                ) from error
            self._guard()
        return self._database_object

    def _bind_request(self, request: _path.MappingRequest) -> None:
        profile = self._domain.profile_receipt
        identity = request.database
        if (
            identity.family != self._family
            or identity.database_id != self._profile
            or identity.database_sha256 != self._runtime_sha256
            or identity.profile_id != self._profile
        ):
            _fail("W2B_MAPPING_BACKEND_PROFILE_IDENTITY_MISMATCH")
        if identity.profile_role != profile.profile_role:
            if self._family in ("ni", "al") and profile.profile_role == (
                "RELEASE_CANDIDATE_PENDING_NE04"
            ):
                _fail(
                    "W2B_MAPPING_BACKEND_NOT_IMPLEMENTED_IDENTITY_V2_REQUIRED"
                )
            _fail("W2B_MAPPING_BACKEND_PROFILE_IDENTITY_MISMATCH")
        if self._family == "fe":
            if (
                identity.profile_id not in SUPPORTED_FE_PROFILE_IDS
                or identity.profile_role
                != _EXACT_FE_PROFILE_ROLE[(self._family, self._profile)]
                or identity.fe_baseline_decision != _receipts.FE_POLICY_UNDECIDED
                or identity.c15_exclusion_decision
                != _receipts.FE_POLICY_UNDECIDED
            ):
                _fail("W2B_MAPPING_BACKEND_FE_POLICY_REQUIRED")
        elif (
            identity.fe_baseline_decision != _receipts.POLICY_NOT_APPLICABLE
            or identity.c15_exclusion_decision
            != _receipts.POLICY_NOT_APPLICABLE
        ):
            _fail("W2B_MAPPING_BACKEND_PROFILE_IDENTITY_MISMATCH")
        selection = request.phase_selection
        if (
            tuple(selection.candidate_phases) != self._candidate_phases
            or tuple(selection.requested_phases) != self._requested_phases
            or tuple(selection.excluded_phases) != self._excluded_phases
            or tuple(selection.effective_phases) != self._effective_phases
        ):
            _fail("W2B_MAPPING_BACKEND_DOMAIN_MISMATCH")
        if self._family == "fe" and (
            "C15_LAVES" not in selection.candidate_phases
            or "C15_LAVES" not in selection.requested_phases
            or "C15_LAVES" in selection.excluded_phases
            or "C15_LAVES" not in selection.effective_phases
            or profile.profile not in SUPPORTED_FE_PROFILE_IDS
        ):
            _fail("W2B_MAPPING_BACKEND_FE_POLICY_REQUIRED")
        expected_full_request = mapping_full_request_payload(request, profile)
        if self._full_request != expected_full_request:
            _fail("W2B_MAPPING_BACKEND_DOMAIN_MISMATCH")
        if self._bounds != mapping_bounds_payload(request):
            _fail("W2B_MAPPING_BACKEND_BOUNDS_INVALID")

    def _strategy_inputs(
        self,
        request: _path.MappingRequest,
    ) -> tuple[object, dict[object, object], dict[str, object]]:
        modules = self._modules()
        variables = modules.variables
        try:
            pressure = getattr(variables, "P")
            temperature = getattr(variables, "T")
            total_moles = getattr(variables, "N")
            mole_fraction = getattr(variables, "X")
            if type(request) is _path.BinaryPhaseDiagramRequest:
                conditions = {
                    pressure: request.pressure_pa,
                    total_moles: 1.0,
                    mole_fraction(request.right_component): (
                        request.right_fraction.lower,
                        request.right_fraction.upper,
                        request.right_fraction.seed_step,
                    ),
                    temperature: (
                        request.temperature_k.lower,
                        request.temperature_k.upper,
                        request.temperature_k.seed_step,
                    ),
                }
            elif type(request) is _path.MulticomponentIsoplethRequest:
                conditions = {
                    pressure: request.pressure_pa,
                    total_moles: 1.0,
                    mole_fraction(request.variable_component): (
                        request.variable_fraction.lower,
                        request.variable_fraction.upper,
                        request.variable_fraction.seed_step,
                    ),
                    temperature: (
                        request.temperature_k.lower,
                        request.temperature_k.upper,
                        request.temperature_k.seed_step,
                    ),
                    **{
                        mole_fraction(name): amount
                        for name, amount in request.fixed_composition
                    },
                }
            else:
                conditions = {
                    pressure: request.pressure_pa,
                    total_moles: 1.0,
                    temperature: request.temperature_k,
                    mole_fraction(request.x_component): (
                        0.0,
                        1.0,
                        request.starting_point_step,
                    ),
                    mole_fraction(request.y_component): (
                        0.0,
                        1.0,
                        request.starting_point_step,
                    ),
                }
            strategy_class = getattr(modules, _FEATURE_STRATEGY[request.feature])
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_STRATEGY_CONSTRUCTION_FAILED"
            ) from error
        options = {
            "GLOBAL_MIN_PDENS": self._solver_options["global_min_pdensity"]
        }
        return strategy_class, conditions, options

    @staticmethod
    def _same_condition_value(left: object, right: object) -> bool:
        if type(right) is tuple:
            if type(left) is not tuple or len(left) != len(right):
                return False
            return all(
                _same_binary64(
                    _finite(left_item, "W2B_MAPPING_BACKEND_DOMAIN_MISMATCH"),
                    _finite(right_item, "W2B_MAPPING_BACKEND_DOMAIN_MISMATCH"),
                )
                for left_item, right_item in zip(left, right)
            )
        return _same_binary64(
            _finite(left, "W2B_MAPPING_BACKEND_DOMAIN_MISMATCH"),
            _finite(right, "W2B_MAPPING_BACKEND_DOMAIN_MISMATCH"),
        )

    @classmethod
    def _verify_strategy_binding(
        cls,
        strategy: object,
        database: object,
        request: _path.MappingRequest,
        expected_conditions: dict[object, object],
    ) -> None:
        """Reject silent component, phase, condition, or database filtering."""

        try:
            strategy_database = getattr(strategy, "dbf")
            components = getattr(strategy, "components")
            phases = getattr(strategy, "phases")
            conditions = getattr(strategy, "conditions")
            if (
                strategy_database is not database
                or type(components) not in (list, tuple)
                or any(type(item) is not str for item in components)
                or tuple(components) != request.components
                or type(phases) not in (list, tuple)
                or any(type(item) is not str for item in phases)
                or tuple(phases) != request.phases
                or type(conditions) is not dict
                or len(conditions) != len(expected_conditions)
            ):
                _fail("W2B_MAPPING_BACKEND_DOMAIN_MISMATCH")
            unmatched = list(conditions.items())
            for expected_key, expected_value in expected_conditions.items():
                matches: list[int] = []
                for index, (actual_key, _actual_value) in enumerate(unmatched):
                    if type(actual_key) is not type(expected_key):
                        continue
                    try:
                        same_key = actual_key == expected_key
                    except Exception as error:
                        raise Wave2BMappingBackendError(
                            "W2B_MAPPING_BACKEND_DOMAIN_MISMATCH"
                        ) from error
                    if type(same_key) is not bool:
                        _fail("W2B_MAPPING_BACKEND_DOMAIN_MISMATCH")
                    if same_key:
                        matches.append(index)
                if len(matches) != 1:
                    _fail("W2B_MAPPING_BACKEND_DOMAIN_MISMATCH")
                index = matches[0]
                _actual_key, actual_value = unmatched.pop(index)
                if not cls._same_condition_value(actual_value, expected_value):
                    _fail("W2B_MAPPING_BACKEND_DOMAIN_MISMATCH")
            if unmatched:
                _fail("W2B_MAPPING_BACKEND_DOMAIN_MISMATCH")
        except Wave2BMappingBackendError:
            raise
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_DOMAIN_MISMATCH"
            ) from error

    @staticmethod
    def _extract_complete_trace(strategy: object) -> CompleteMappingDiagnostics:
        try:
            method = getattr(strategy, "complete_diagnostic_trace", None)
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_INCOMPLETE_DIAGNOSTICS"
            ) from error
        if not callable(method):
            _fail("W2B_MAPPING_BACKEND_INCOMPLETE_DIAGNOSTICS")
        try:
            return _copy_complete_diagnostics(method())
        except Wave2BMappingBackendError:
            raise
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_INCOMPLETE_DIAGNOSTICS"
            ) from error

    @staticmethod
    def _ledger_from_trace(
        request: _path.MappingRequest,
        trace: CompleteMappingDiagnostics,
    ) -> _path.RawMappingLedger:
        if trace.feature_id != request.feature:
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        allowed_segments = _SEGMENT_KINDS[request.feature]
        attempts_by_ordinal = {item.raw_ordinal: item for item in trace.attempts}
        if len(attempts_by_ordinal) != len(trace.attempts):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        pass_attempts = tuple(
            item for item in trace.attempts if item.outcome == "PASS"
        )
        pass_ordinals = {item.raw_ordinal for item in pass_attempts}
        if (
            any(item.kind not in _LEDGER_NODE_KINDS for item in trace.attempts)
            or any(
                item.outcome == "FAIL" and item.phases
                for item in trace.attempts
            )
            or len({item.coordinates for item in pass_attempts})
            != len(pass_attempts)
        ):
            _fail("W2B_MAPPING_BACKEND_NOT_IMPLEMENTED_LEDGER_V2_REQUIRED")
        adjacency = {ordinal: set() for ordinal in pass_ordinals}
        for segment in trace.segments:
            if (
                segment.start_raw_ordinal in adjacency
                and segment.end_raw_ordinal in adjacency
            ):
                adjacency[segment.start_raw_ordinal].add(
                    segment.end_raw_ordinal
                )
                adjacency[segment.end_raw_ordinal].add(
                    segment.start_raw_ordinal
                )
        if len(pass_ordinals) > 1:
            pending = [min(pass_ordinals)]
            visited: set[int] = set()
            while pending:
                ordinal = pending.pop()
                if ordinal in visited:
                    continue
                visited.add(ordinal)
                pending.extend(sorted(adjacency[ordinal] - visited, reverse=True))
            if visited != pass_ordinals:
                _fail(
                    "W2B_MAPPING_BACKEND_NOT_IMPLEMENTED_LEDGER_V2_REQUIRED"
                )
        nodes: list[_path.MappingNodeRecord] = []
        for item in trace.attempts:
            try:
                nodes.append(
                    _path.MappingNodeRecord(
                        ordinal=item.raw_ordinal,
                        node_id=f"raw_{item.raw_ordinal:08d}",
                        kind=item.kind,
                        outcome=item.outcome,
                        coordinates=item.coordinates,
                        phases=item.phases,
                        reason_code=item.reason_code,
                    )
                )
            except Exception as error:
                raise Wave2BMappingBackendError(
                    "W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID"
                ) from error
        segments: list[_path.MappingSegmentRecord] = []
        for item in trace.segments:
            start = attempts_by_ordinal.get(item.start_raw_ordinal)
            end = attempts_by_ordinal.get(item.end_raw_ordinal)
            if (
                item.kind not in allowed_segments
                or start is None
                or end is None
                or start.outcome != "PASS"
                or end.outcome != "PASS"
                or item.phases
                != tuple(sorted(set(start.phases) | set(end.phases)))
            ):
                _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
            try:
                segments.append(
                    _path.MappingSegmentRecord(
                        ordinal=item.raw_ordinal,
                        kind=item.kind,
                        start_node_id=f"raw_{item.start_raw_ordinal:08d}",
                        end_node_id=f"raw_{item.end_raw_ordinal:08d}",
                        phases=item.phases,
                    )
                )
            except Exception as error:
                raise Wave2BMappingBackendError(
                    "W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID"
                ) from error
        try:
            ledger = _path.RawMappingLedger(
                database=_copy_database(request.database),
                feature=request.feature,
                strategy=request.strategy,
                nodes=tuple(nodes),
                segments=tuple(segments),
                completed=trace.completed,
                termination_reason_code=trace.termination_reason_code,
            )
            # MappingResult applies feature geometry, domain, assemblage, and
            # connectivity validation before this ledger leaves the backend.
            _path.MappingResult(request=_copy_request(request), ledger=ledger)
            return ledger
        except Wave2BMappingBackendError:
            raise
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID"
            ) from error

    def _execute_mapping(
        self,
        canonical: _path.MappingRequest,
    ) -> tuple[_path.RawMappingLedger, CompleteMappingDiagnostics]:
        """Construct, bind, and execute after the public edge is validated."""

        strategy_class, conditions, strategy_options = self._strategy_inputs(canonical)
        database = self._database()
        try:
            strategy = _default_strategy_factory(
                strategy_class,
                database,
                list(canonical.components),
                list(canonical.phases),
                dict(conditions),
                dict(strategy_options),
            )
        except Wave2BMappingBackendError:
            raise
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_STRATEGY_CONSTRUCTION_FAILED"
            ) from error
        self._verify_strategy_binding(
            strategy,
            database,
            canonical,
            conditions,
        )
        self._guard()

        # Stock pycalphad 0.11.2 has no complete_diagnostic_trace API.  Detect
        # that before mapping so an expensive calculation cannot be mistaken
        # for an auditable result after its failed attempts were discarded.
        try:
            diagnostic_method = getattr(strategy, "complete_diagnostic_trace", None)
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_INCOMPLETE_DIAGNOSTICS"
            ) from error
        if not callable(diagnostic_method):
            _fail("W2B_MAPPING_BACKEND_INCOMPLETE_DIAGNOSTICS")

        try:
            do_map = getattr(strategy, "do_map", None)
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_STRATEGY_RAISED"
            ) from error
        if not callable(do_map):
            _fail("W2B_MAPPING_BACKEND_STRATEGY_RAISED")

        strategy_error: Exception | None = None
        try:
            do_map(max_iter=self._solver_options["max_iterations"])
        except Exception as error:
            strategy_error = error

        self._verify_strategy_binding(
            strategy,
            database,
            canonical,
            conditions,
        )
        trace = self._extract_complete_trace(strategy)
        if strategy_error is not None:
            expected_exception = _strategy_exception_binding(strategy_error)
            if (
                trace.completed
                or trace.termination_reason_code
                != "W2B_MAP_TERMINATED_BACKEND_FAILURE"
                or trace.attempts[-1].outcome != "FAIL"
                or trace.backend_exception != expected_exception
                or trace.backend_exception_attempt_ordinal
                != trace.attempts[-1].raw_ordinal
            ):
                _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        elif (
            trace.backend_exception is not None
            or trace.backend_exception_attempt_ordinal is not None
        ):
            _fail("W2B_MAPPING_BACKEND_DIAGNOSTIC_INVALID")
        return self._ledger_from_trace(canonical, trace), trace

    def map(self, request: object) -> _path.RawMappingLedger:
        """Execute one exact strategy or fail if complete diagnostics are absent."""

        self._guard()
        canonical = _copy_request(request)
        pristine = _copy_request(canonical)
        self._bind_request(canonical)
        self._attempted_maps += 1
        try:
            ledger, trace = self._execute_mapping(canonical)
            if _copy_request(canonical) != pristine:
                _fail("W2B_MAPPING_BACKEND_REQUEST_INVALID")
            if trace.completed:
                self._completed_maps += 1
                self._last_diagnostic_state = "COMPLETE_TRACE_COMPLETED"
            else:
                self._failed_maps += 1
                self._last_diagnostic_state = "COMPLETE_TRACE_TERMINATED"
            return ledger
        except Wave2BMappingBackendError as error:
            self._failed_maps += 1
            if error.reason_code == "W2B_MAPPING_BACKEND_INCOMPLETE_DIAGNOSTICS":
                self._last_diagnostic_state = "INCOMPLETE_DIAGNOSTICS"
            elif error.reason_code in (
                "W2B_MAPPING_BACKEND_NOT_IMPLEMENTED_LEDGER_V2_REQUIRED",
                "W2B_MAPPING_BACKEND_NOT_IMPLEMENTED_IDENTITY_V2_REQUIRED",
            ):
                self._last_diagnostic_state = "DTO_V2_REQUIRED"
            elif self._last_diagnostic_state in ("NOT_RUN", "FAILED"):
                self._last_diagnostic_state = "FAILED"
            raise
        except Exception as error:
            self._failed_maps += 1
            self._last_diagnostic_state = "FAILED"
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_STRATEGY_RAISED"
            ) from error
        finally:
            self._guard()
            try:
                if _copy_request(request) != pristine:
                    _fail("W2B_MAPPING_BACKEND_REQUEST_INVALID")
            except Wave2BMappingBackendError:
                raise
            except Exception as error:
                raise Wave2BMappingBackendError(
                    "W2B_MAPPING_BACKEND_REQUEST_INVALID"
                ) from error

    @staticmethod
    def _verify_frozen_v2_contract() -> None:
        try:
            contract_file = _Path(_v2.__file__).resolve(strict=True)
            expected_file = _Path(__file__).resolve(strict=True).with_name(
                "thermogar_wave2b_path_contract_v2.py"
            )
            if (
                contract_file != expected_file
                or not contract_file.is_file()
                or _hashlib.sha256(contract_file.read_bytes()).hexdigest()
                != PATH_CONTRACT_V2_SHA256
            ):
                _fail("W2B_MAPPING_BACKEND_V2_CONTRACT_DRIFT")
        except Wave2BMappingBackendError:
            raise
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_V2_CONTRACT_DRIFT"
            ) from error

    def _bind_request_v2(
        self,
        request: _path.MappingRequest,
    ) -> _v2.DatabaseIdentityV2:
        profile = self._domain.profile_receipt
        identity = _database_identity_v2_from_profile(profile)
        _bind_geometry_identity_to_v2_profile(request, identity)
        selection = request.phase_selection
        if (
            tuple(selection.candidate_phases) != self._candidate_phases
            or tuple(selection.requested_phases) != self._requested_phases
            or tuple(selection.excluded_phases) != self._excluded_phases
            or tuple(selection.effective_phases) != self._effective_phases
            or self._full_request
            != mapping_full_request_payload_v2(request, profile)
        ):
            _fail("W2B_MAPPING_BACKEND_V2_BINDING_INVALID")
        if self._bounds != mapping_bounds_payload(request):
            _fail("W2B_MAPPING_BACKEND_BOUNDS_INVALID")
        if self._solver_options["max_iterations"] == -1:
            _fail("W2B_MAPPING_BACKEND_SOLVER_OPTIONS_UNSUPPORTED")
        return identity

    def _execute_mapping_v2(
        self,
        canonical: _path.MappingRequest,
        database_identity: _v2.DatabaseIdentityV2,
        evidence_record_budget: int,
    ) -> _v2.MappingResultV2:
        strategy_class, conditions, strategy_options = self._strategy_inputs(
            canonical
        )
        database = self._database()
        try:
            strategy = _default_strategy_factory(
                strategy_class,
                database,
                list(canonical.components),
                list(canonical.phases),
                dict(conditions),
                dict(strategy_options),
            )
        except Wave2BMappingBackendError:
            raise
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_STRATEGY_CONSTRUCTION_FAILED"
            ) from error
        self._verify_strategy_binding(
            strategy,
            database,
            canonical,
            conditions,
        )
        self._guard()
        try:
            do_map = getattr(strategy, "do_map", None)
            if not callable(do_map):
                _fail("W2B_MAPPING_BACKEND_V2_STRATEGY_RAISED")
            do_map(max_iter=self._solver_options["max_iterations"])
        except Wave2BMappingBackendError:
            raise
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_V2_STRATEGY_RAISED"
            ) from error
        self._verify_strategy_binding(
            strategy,
            database,
            canonical,
            conditions,
        )
        self._guard()
        modules = self._modules()
        evidence, nodes, segments, regions, unresolved_count = (
            _project_public_mapping_v2(
                strategy,
                canonical,
                modules.variables,
                evidence_record_budget,
            )
        )
        terminal_reason = (
            V2_PARTIAL_TERMINAL_REASON
            if unresolved_count
            else V2_TOPOLOGY_PARTIAL_TERMINAL_REASON
        )
        try:
            execution_binding = _v2.ExecutionBindingV2(
                profile_receipt_digest=self._profile_digest,
                domain_receipt_digest=self._domain_digest,
                execution_lease_id=self._lease_id,
                execution_snapshot_digest=self._snapshot_digest,
            )
            phase_domain = _v2.PhaseDomainV2(
                candidate_phases=self._candidate_phases,
                requested_phases=self._requested_phases,
                excluded_phases=self._excluded_phases,
                effective_phases=self._effective_phases,
            )
            diagnostics = _v2.MappingDiagnosticsV2(
                instrumentation_id=(
                    "pycalphad-0.11.2-public-postrun-raw64-"
                    "feature-pinned-mf-abs1e-9"
                ),
                instrumentation_version="2.1.1",
                instrumentation_level="PARTIAL_BACKEND_OBSERVABILITY",
                backend_name="pycalphad",
                backend_version=PYCALPHAD_VERSION,
                completeness="PARTIAL",
                full_attempt_ledger=False,
                failed_attempts_retained=False,
                merged_attempts_retained=False,
                abandoned_attempts_retained=False,
                unresolved_branch_count=unresolved_count,
                attempt_budget=0,
                attempts_consumed=0,
                attempt_budget_exhausted=False,
                evidence_record_budget=evidence_record_budget,
                evidence_records_consumed=len(evidence),
                evidence_record_budget_exhausted=False,
            )
            ledger = _v2.RawMappingLedgerV2(
                database=database_identity,
                execution_binding=execution_binding,
                phase_domain=phase_domain,
                feature=canonical.feature,
                strategy=canonical.strategy,
                attempts=tuple(),
                postrun_evidence=evidence,
                topology_nodes=nodes,
                segments=segments,
                regions=regions,
                diagnostics=diagnostics,
                terminal_reason=terminal_reason,
            )
            result = _v2.MappingResultV2(ledger=ledger)
        except Wave2BMappingBackendError:
            raise
        except Exception as error:
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
            ) from error
        self._guard()
        return result

    def map_v2(
        self,
        request: object,
        *,
        evidence_record_budget: int,
    ) -> _v2.MappingResultV2:
        """Return honest native post-run observations as a V2 partial result.

        ``evidence_record_budget`` bounds public post-run evidence records.
        The separately receipted ``max_iterations`` remains the exact native
        strategy iteration bound.  No public post-run observation is emitted
        as a hidden chronological solver attempt.
        """

        self._guard()
        self._verify_frozen_v2_contract()
        if (
            type(evidence_record_budget) is not int
            or isinstance(evidence_record_budget, bool)
            or not 1 <= evidence_record_budget <= 80_000
        ):
            _fail("W2B_MAPPING_BACKEND_V2_OBSERVATION_BUDGET_EXCEEDED")
        canonical = _copy_request(request)
        pristine = _copy_request(canonical)
        database_identity = self._bind_request_v2(canonical)
        self._attempted_maps += 1
        try:
            result = self._execute_mapping_v2(
                canonical,
                database_identity,
                evidence_record_budget,
            )
            if _copy_request(canonical) != pristine:
                _fail("W2B_MAPPING_BACKEND_REQUEST_INVALID")
            self._failed_maps += 1
            self._last_diagnostic_state = f"V2_NATIVE_{result.terminal_reason}"
            return result
        except Wave2BMappingBackendError:
            self._failed_maps += 1
            self._last_diagnostic_state = "V2_NATIVE_FAILED_CLOSED"
            raise
        except Exception as error:
            self._failed_maps += 1
            self._last_diagnostic_state = "V2_NATIVE_FAILED_CLOSED"
            raise Wave2BMappingBackendError(
                "W2B_MAPPING_BACKEND_V2_OBSERVATION_INVALID"
            ) from error
        finally:
            self._guard()
            try:
                if _copy_request(request) != pristine:
                    _fail("W2B_MAPPING_BACKEND_REQUEST_INVALID")
            except Wave2BMappingBackendError:
                raise
            except Exception as error:
                raise Wave2BMappingBackendError(
                    "W2B_MAPPING_BACKEND_REQUEST_INVALID"
                ) from error

    def receipt_payloads(
        self,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        """Return canonical-JSON-ready nonclaiming backend receipt payloads."""

        self._guard_receipt_identity()
        version = (
            self._solver_modules.version
            if type(self._solver_modules) is _SolverModules
            else "NOT_LOADED"
        )
        backend = {
            "schema_version": MAPPING_BACKEND_SCHEMA,
            "backend_id": BACKEND_ID,
            "pycalphad_version": version,
            "supported_mapping_features": list(SUPPORTED_MAPPING_FEATURES),
            "complete_diagnostics_required": True,
            "stock_pycalphad_0_11_2_complete_diagnostics": False,
            "native_v2_partial_observations_supported": True,
            "native_v2_complete_diagnostics_supported": False,
            "native_v2_hidden_attempts_available": False,
            "native_v2_isopleth_derived_invariants_supported": False,
            "native_v2_projection_policy": "EXACT_OR_FAIL_CLOSED",
            "native_v2_postrun_membership_policy": (
                V2_POSTRUN_MEMBERSHIP_POLICY
            ),
            "native_v2_isopleth_fixed_composition_abs_tolerance": (
                PYCALPHAD_0_11_2_ISOPLETH_FIXED_COMPOSITION_ABS_TOL
            ),
            "native_v2_mole_fraction_abs_tolerance_by_feature": dict(
                PYCALPHAD_0_11_2_MOLE_FRACTION_ABS_TOL_BY_FEATURE
            ),
            "path_contract_v2_sha256": PATH_CONTRACT_V2_SHA256,
            "v2_partial_reason_code": V2_PARTIAL_REASON_CODE,
            "acceptance_claim": False,
            "counts_toward_feature_coverage": False,
            "production_use": "DENIED",
        }
        runtime = {
            "database_family": self._family,
            "profile_id": self._profile,
            "runtime_sha256": self._runtime_sha256,
            "profile_receipt_digest": self._profile_digest,
            "domain_receipt_digest": self._domain_digest,
            "execution_snapshot_digest": self._snapshot_digest,
            "database_source_role": "runtime",
            "database_path_kind": "ACTIVE_EXECUTION_LEASE_SNAPSHOT_ONLY",
            "v2_database_id": _V2_DATABASE_ID[(self._family, self._profile)],
        }
        context = {
            "feature_id": self._feature_id,
            "execution_mode": _receipts.INTERNAL_QUALIFICATION,
            "authorization_state": "INTERNAL_QUALIFICATION_ONLY_NOT_RELEASE",
            "execution_lease_id": self._lease_id,
            "pre_snapshot_digest": self._pre.canonical_digest,
            "attempted_maps": self._attempted_maps,
            "completed_maps": self._completed_maps,
            "failed_maps": self._failed_maps,
            "last_diagnostic_state": self._last_diagnostic_state,
            "steel_required_product_scope": True,
            "fe_baseline_profile": None,
            "fe_exclusion_decision_made": False,
            "v2_partial_terminal_reasons": [
                V2_PARTIAL_TERMINAL_REASON,
                V2_TOPOLOGY_PARTIAL_TERMINAL_REASON,
            ],
            "v2_partial_reason_code": V2_PARTIAL_REASON_CODE,
            "acceptance_claim": False,
            "counts_toward_feature_coverage": False,
            "production_use": "DENIED",
        }
        return backend, runtime, context


__all__ = (
    "MAPPING_BACKEND_SCHEMA",
    "MAPPING_REQUEST_SCHEMA",
    "MAPPING_REQUEST_V2_SCHEMA",
    "COMPLETE_DIAGNOSTICS_SCHEMA",
    "BACKEND_ID",
    "PYCALPHAD_VERSION",
    "PATH_CONTRACT_V2_SHA256",
    "SUPPORTED_MAPPING_FEATURES",
    "SUPPORTED_DATABASE_FAMILIES",
    "SUPPORTED_FE_PROFILE_IDS",
    "STEEL_REQUIRED_PRODUCT_SCOPE",
    "FE_BASELINE_PROFILE",
    "FE_EXCLUSION_DECISION_MADE",
    "COUNTS_TOWARD_FEATURE_COVERAGE",
    "ACCEPTANCE_CLAIM",
    "PRODUCTION_USE",
    "V2_PARTIAL_TERMINAL_REASON",
    "V2_TOPOLOGY_PARTIAL_TERMINAL_REASON",
    "V2_PARTIAL_REASON_CODE",
    "PYCALPHAD_0_11_2_MOLE_FRACTION_ABS_TOL_BY_FEATURE",
    "PYCALPHAD_0_11_2_ISOPLETH_FIXED_COMPOSITION_ABS_TOL",
    "V2_POSTRUN_MEMBERSHIP_POLICY",
    "WAVE2B_MAPPING_BACKEND_REASON_CODES",
    "Wave2BMappingBackendError",
    "MappingDiagnosticAttempt",
    "MappingDiagnosticSegment",
    "StrategyExceptionBinding",
    "CompleteMappingDiagnostics",
    "mapping_request_payload",
    "mapping_bounds_payload",
    "mapping_full_request_payload",
    "mapping_request_payload_v2",
    "mapping_full_request_payload_v2",
    "ReceiptBoundMappingBackend",
)
