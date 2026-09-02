"""Receipt-bound Wave 2B equilibrium and Scheil solidification backend.

This module is an internal-qualification integration boundary.  It is import
safe: pycalphad, scheil, and numpy are imported only when ``simulate`` is
called.  The thermodynamic database is loaded solely from the locked
``ExecutionLease.file_path("runtime")`` snapshot after a matching PRE rehash.

Native scheil 0.3.0 results do not expose every attempted internal solve.
Consequently this backend deliberately refuses to describe a native result as
complete.  A diagnostic-complete solver integration can use the exact private
attempt envelope below; the native integration fails closed with
``W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS``.  No failed point is fabricated.

Steel is mandatory scope.  Both explicit Fe profiles are supported as
separate identities, neither is selected as a baseline, and C15_LAVES remains
candidate, requested, effective, and unexcluded while the user decision is
undecided.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
import hashlib as _hashlib
import importlib as _importlib
import math as _math
from pathlib import Path as _Path
import struct as _struct
from types import MappingProxyType as _MappingProxyType, MethodType as _MethodType
from typing import Mapping as _Mapping

import thermogar_wave2b_path_adapters as _path
import thermogar_wave2b_path_contract_v2 as _path_v2
import thermogar_wave2b_receipts as _receipts


BACKEND_SCHEMA = "THERMOGAR-WAVE2B-SOLIDIFICATION-BACKEND-1"
BACKEND_ID = "thermogar_wave2b_scheil_0_3_0_candidate"
SUPPORTED_DATABASE_FAMILIES = ("ni", "al", "fe")
SUPPORTED_FE_PROFILE_IDS = ("thermogar_patch", "upstream_original")
IDENTITY_V2_REQUIRED_FAMILIES = ("ni", "al")
BOUND_OPERATIONS = (
    "equilibrium_solidification",
    "scheil_solidification",
)
NATIVE_COMPLETE_OPERATIONS: tuple[str, ...] = tuple()
REQUIRED_SOLIDIFICATION_CONTRACT_SCHEMA = _path_v2.CONTRACT_SCHEMA
PATH_CONTRACT_V2_SHA256 = (
    "c58a35d1548c3d5b321ac4094c3ef86bd6b30d2d2f5f4e6570cad2556afc7ed7"
)
REQUIRED_SOLIDIFICATION_CONTRACT_VERSION = "2.1"
CONTRACT_V2_REQUIRED = True
LEGACY_COMPLETE_OUTPUT_ENABLED = False
NATIVE_V2_RESULT_STATUS = "PARTIAL_UNRESOLVED_BRANCHES"
NATIVE_V2_DIAGNOSTIC_REASON = (
    "SCHEIL_0_3_0_HIDDEN_INTERNAL_ATTEMPTS_UNAVAILABLE"
)
SOLIDIFICATION_PRESSURE_PA = 101325.0
STEEL_REQUIRED_PRODUCT_SCOPE = True
FE_BASELINE_PROFILE = None
FE_EXCLUSION_DECISION_MADE = False
COUNTS_TOWARD_FEATURE_COVERAGE = False
ACCEPTANCE_CLAIM = False
PRODUCTION_USE = "DENIED"

_NATIVE_DIAGNOSTIC_KIND = "NATIVE_SUCCESS_ARRAYS_ONLY"
_MANUFACTURED_DIAGNOSTIC_KIND = (
    "MANUFACTURED_TEST_ONLY_FULL_INTERNAL_ATTEMPT_LEDGER_V2"
)
_NATIVE_PROVENANCE = "NATIVE_RUNTIME"
_MANUFACTURED_PROVENANCE = "MANUFACTURED_TEST_ONLY"
_DIAGNOSTIC_ENVELOPE_SCHEMA = "THERMOGAR-WAVE2B-SOLID-DIAGNOSTIC-ENVELOPE-2"
_MANUFACTURED_INSTRUMENTATION_ID = "manufactured-solidification-hook"
_MANUFACTURED_INSTRUMENTATION_VERSION = "2.0.0"
_FULL_INSTRUMENTATION_LEVEL = "FULL_INTERNAL_ATTEMPT_LEDGER"
_NATIVE_V2_INSTRUMENTATION_ID = "scheil-public-result-rows"
_NATIVE_V2_INSTRUMENTATION_VERSION = "2.1.0"
_NATIVE_V2_PUBLIC_ROW_LIMIT = 20_000
_BALANCE_TOLERANCE = 1.0e-10
_BOUND_TOLERANCE = 1.0e-12

_REASONS = {
    "W2B_SOLID_BACKEND_CONTEXT_INVALID": "One exact domain, PRE snapshot, and active execution lease are required.",
    "W2B_SOLID_BACKEND_INTERNAL_QUALIFICATION_REQUIRED": "The backend is restricted to INTERNAL_QUALIFICATION.",
    "W2B_SOLID_BACKEND_LEASE_INACTIVE": "The bound execution lease is not active in its PRE execution window.",
    "W2B_SOLID_BACKEND_PRE_MISMATCH": "The PRE snapshot does not match the domain, profile, lease, or execution snapshot.",
    "W2B_SOLID_BACKEND_PROFILE_IDENTITY_MISMATCH": "The request uses a different exact database/profile identity.",
    "W2B_SOLID_BACKEND_IDENTITY_CONTRACT_INCOMPATIBLE": "The frozen path DTO cannot represent the exact Ni/Al receipt profile role; DTO v2 is required.",
    "W2B_SOLID_BACKEND_DOMAIN_MISMATCH": "The request differs from the exact receipt-bound feature or phase domain.",
    "W2B_SOLID_BACKEND_FE_POLICY_REQUIRED": "Fe requires an explicit profile and retained C15_LAVES while policy is undecided.",
    "W2B_SOLID_BACKEND_REQUEST_INVALID": "The request is not an exact valid solidification DTO.",
    "W2B_SOLID_BACKEND_BOUNDS_INVALID": "The start, terminal-temperature bound, step, pressure, or result is outside the receipt bounds.",
    "W2B_SOLID_BACKEND_SOLVER_OPTIONS_UNSUPPORTED": "The receipt solver options do not exactly match the method request.",
    "W2B_SOLID_BACKEND_PYCALPHAD_UNAVAILABLE": "The pycalphad runtime could not be imported lazily.",
    "W2B_SOLID_BACKEND_PYCALPHAD_VERSION_MISMATCH": "Exact pycalphad 0.11.2 semantics are required.",
    "W2B_SOLID_BACKEND_SCHEIL_VERSION_MISMATCH": "Exact scheil 0.3.0 semantics are required.",
    "W2B_SOLID_BACKEND_DATABASE_LOAD_FAILED": "pycalphad could not load the active runtime snapshot.",
    "W2B_SOLID_BACKEND_RUNTIME_PATH_INVALID": "The database path is not the exact active lease runtime snapshot.",
    "W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS": "The solver does not expose every attempted internal point in order.",
    "W2B_SOLID_BACKEND_DTO_V2_REQUIRED": "A diagnostic-complete solidification result requires the exact path Contract V2 ledger.",
    "W2B_SOLID_BACKEND_MANUFACTURED_RECEIPT_DENIED": "MANUFACTURED_TEST_ONLY output cannot produce a result receipt.",
    "W2B_SOLID_BACKEND_RESULT_INVALID": "The diagnostic result cannot be represented honestly by RawSolidificationLedger.",
    "W2B_SOLID_BACKEND_V2_CONTRACT_MISMATCH": "The frozen Path Contract V2 source identity does not match the required integration.",
    "W2B_SOLID_BACKEND_NATIVE_RUNTIME_REQUIRED": "The V2 runner requires the exact installed native pycalphad and scheil runtime.",
    "W2B_SOLID_BACKEND_NATIVE_SOLVER_FAILED": "The native solidification solver did not return a public result.",
    "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE": "A native public row, bound, phase instance, composition, or source index cannot be represented exactly by frozen Path Contract V2.1.",
    "W2B_SOLID_BACKEND_PROTOCOL_INVALID": "The public V2 protocol requires the exact receipt-bound solidification backend and method.",
    "W2B_SOLID_BACKEND_PROTOCOL_RAISED": "The exact public V2 backend method raised an unexpected exception.",
}
WAVE2B_SOLID_BACKEND_REASON_CODES: _Mapping[str, str] = _MappingProxyType(
    _REASONS
)
del _REASONS


class Wave2BSolidificationBackendError(ValueError):
    """Fail-closed backend error carrying one stable machine reason code."""

    __slots__ = ("reason_code",)

    def __init__(self, reason_code: str) -> None:
        if (
            type(reason_code) is not str
            or reason_code not in WAVE2B_SOLID_BACKEND_REASON_CODES
        ):
            raise RuntimeError("Unknown Wave 2B solidification backend reason")
        self.reason_code = reason_code
        super().__init__(reason_code)


def _fail(reason_code: str) -> None:
    raise Wave2BSolidificationBackendError(reason_code)


def _finite(value: object, reason: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(reason)
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise Wave2BSolidificationBackendError(reason) from error
    if not _math.isfinite(number):
        _fail(reason)
    return 0.0 if number == 0.0 else number


def _explicit_nan(value: object, reason: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(reason)
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise Wave2BSolidificationBackendError(reason) from error
    if not _math.isnan(number):
        _fail(reason)
    return number


def _same_binary64(left: float, right: float) -> bool:
    return _struct.pack(">d", left) == _struct.pack(">d", right)


def _guard_path_contract_v2() -> None:
    try:
        expected = _Path(__file__).resolve(strict=True).with_name(
            "thermogar_wave2b_path_contract_v2.py"
        )
        observed = _Path(_path_v2.__file__).resolve(strict=True)
        if expected != observed or not observed.is_file():
            _fail("W2B_SOLID_BACKEND_V2_CONTRACT_MISMATCH")
        digest = _hashlib.sha256()
        total = 0
        with observed.open("rb") as stream:
            while True:
                block = stream.read(65_536)
                if not block:
                    break
                total += len(block)
                if total > 1_048_576:
                    _fail("W2B_SOLID_BACKEND_V2_CONTRACT_MISMATCH")
                digest.update(block)
        if (
            total == 0
            or digest.hexdigest() != PATH_CONTRACT_V2_SHA256
            or _path_v2.CONTRACT_SCHEMA
            != REQUIRED_SOLIDIFICATION_CONTRACT_SCHEMA
            or _path_v2.CONTRACT_VERSION
            != REQUIRED_SOLIDIFICATION_CONTRACT_VERSION
        ):
            _fail("W2B_SOLID_BACKEND_V2_CONTRACT_MISMATCH")
    except Wave2BSolidificationBackendError:
        raise
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_V2_CONTRACT_MISMATCH"
        ) from error


def _decode_canonical_value(value: object, depth: int = 0) -> object:
    """Decode the receipt layer's explicit binary64 JSON representation."""

    if depth > 64:
        _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
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
                _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
            number = _struct.unpack(">d", bytes.fromhex(encoded))[0]
            if not _math.isfinite(number):
                _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
            return number
        return {
            key: _decode_canonical_value(item, depth + 1)
            for key, item in value.items()
        }
    _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")


def _payload_dict(value: object) -> dict[str, object]:
    try:
        if type(value) is not _receipts.CanonicalPayload:
            _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
        decoded = _decode_canonical_value(value.value())
    except Wave2BSolidificationBackendError:
        raise
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_CONTEXT_INVALID"
        ) from error
    if type(decoded) is not dict:
        _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
    return decoded


def _copy_database(value: object) -> _path.DatabaseIdentity:
    try:
        if type(value) is not _path.DatabaseIdentity:
            _fail("W2B_SOLID_BACKEND_REQUEST_INVALID")
        return _path.DatabaseIdentity(
            family=value.family,
            database_id=value.database_id,
            database_sha256=value.database_sha256,
            profile_id=value.profile_id,
            profile_role=value.profile_role,
            fe_baseline_decision=value.fe_baseline_decision,
            c15_exclusion_decision=value.c15_exclusion_decision,
        )
    except Wave2BSolidificationBackendError:
        raise
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_REQUEST_INVALID"
        ) from error


def _copy_phase_selection(value: object) -> _path.PhaseSelection:
    try:
        if type(value) is not _path.PhaseSelection:
            _fail("W2B_SOLID_BACKEND_REQUEST_INVALID")
        return _path.PhaseSelection(
            candidate_phases=tuple(value.candidate_phases),
            requested_phases=tuple(value.requested_phases),
            excluded_phases=tuple(value.excluded_phases),
            effective_phases=tuple(value.effective_phases),
        )
    except Wave2BSolidificationBackendError:
        raise
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_REQUEST_INVALID"
        ) from error


def _copy_request(value: object):
    try:
        if type(value) not in (
            _path.EquilibriumSolidificationRequest,
            _path.ScheilSolidificationRequest,
        ):
            _fail("W2B_SOLID_BACKEND_REQUEST_INVALID")
        common = {
            "database": _copy_database(value.database),
            "components": tuple(value.components),
            "phase_selection": _copy_phase_selection(value.phase_selection),
            "composition": tuple(
                (component, amount) for component, amount in value.composition
            ),
            "liquid_phase": value.liquid_phase,
            "pressure_pa": value.pressure_pa,
            "start_temperature_k": value.start_temperature_k,
            "step_temperature_k": value.step_temperature_k,
            "adaptive": value.adaptive,
            "pdens": value.pdens,
        }
        if type(value) is _path.EquilibriumSolidificationRequest:
            return _path.EquilibriumSolidificationRequest(
                **common,
                binary_search_tolerance_k=value.binary_search_tolerance_k,
            )
        return _path.ScheilSolidificationRequest(
            **common,
            stop_liquid_fraction=value.stop_liquid_fraction,
        )
    except Wave2BSolidificationBackendError:
        raise
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_REQUEST_INVALID"
        ) from error


def _capture_request_anchors(value: object) -> tuple[object, object]:
    """Retain the caller's exact nested graph for fail-closed restoration."""

    try:
        if type(value) not in (
            _path.EquilibriumSolidificationRequest,
            _path.ScheilSolidificationRequest,
        ):
            _fail("W2B_SOLID_BACKEND_REQUEST_INVALID")
        database = value.database
        selection = value.phase_selection
        if (
            type(database) is not _path.DatabaseIdentity
            or type(selection) is not _path.PhaseSelection
        ):
            _fail("W2B_SOLID_BACKEND_REQUEST_INVALID")
        return database, selection
    except Wave2BSolidificationBackendError:
        raise
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_REQUEST_INVALID"
        ) from error


def _restore_exact_class(value: object, expected: type) -> None:
    if type(value) is expected:
        return
    try:
        object.__setattr__(value, "__class__", expected)
    except (AttributeError, TypeError, ValueError) as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_REQUEST_INVALID"
        ) from error
    if type(value) is not expected:
        _fail("W2B_SOLID_BACKEND_REQUEST_INVALID")


def _restore_request_caller(
    caller: object,
    pristine: object,
    anchors: tuple[object, object],
) -> None:
    """Restore the caller DTO in place, including its original nested objects."""

    try:
        if type(pristine) not in (
            _path.EquilibriumSolidificationRequest,
            _path.ScheilSolidificationRequest,
        ) or len(anchors) != 2:
            _fail("W2B_SOLID_BACKEND_REQUEST_INVALID")
        _restore_exact_class(caller, type(pristine))
        database, selection = anchors
        _restore_exact_class(database, _path.DatabaseIdentity)
        _restore_exact_class(selection, _path.PhaseSelection)
        for name in (
            "family",
            "database_id",
            "database_sha256",
            "profile_id",
            "profile_role",
            "fe_baseline_decision",
            "c15_exclusion_decision",
        ):
            object.__setattr__(database, name, getattr(pristine.database, name))
        for name in (
            "candidate_phases",
            "requested_phases",
            "excluded_phases",
            "effective_phases",
        ):
            object.__setattr__(
                selection,
                name,
                getattr(pristine.phase_selection, name),
            )
        for name, item in (
            ("database", database),
            ("components", pristine.components),
            ("phase_selection", selection),
            ("composition", pristine.composition),
            ("liquid_phase", pristine.liquid_phase),
            ("pressure_pa", pristine.pressure_pa),
            ("start_temperature_k", pristine.start_temperature_k),
            ("step_temperature_k", pristine.step_temperature_k),
            ("adaptive", pristine.adaptive),
            ("pdens", pristine.pdens),
        ):
            object.__setattr__(caller, name, item)
        if type(pristine) is _path.EquilibriumSolidificationRequest:
            object.__setattr__(
                caller,
                "binary_search_tolerance_k",
                pristine.binary_search_tolerance_k,
            )
        else:
            object.__setattr__(
                caller,
                "stop_liquid_fraction",
                pristine.stop_liquid_fraction,
            )
    except Wave2BSolidificationBackendError:
        raise
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_REQUEST_INVALID"
        ) from error


def _request_integrity_error(
    value: object,
    pristine_card: dict[str, object],
) -> Wave2BSolidificationBackendError | None:
    try:
        if _request_card(value) != pristine_card:
            return Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_REQUEST_INVALID"
            )
    except Exception:
        return Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_REQUEST_INVALID"
        )
    return None


def _assert_public_requests_pristine(
    caller: object,
    outbound: object,
    pristine: object,
    pristine_card: dict[str, object],
    anchors: tuple[object, object],
) -> None:
    """Detect both caller and outbound mutation, then restore the caller graph."""

    caller_error = _request_integrity_error(caller, pristine_card)
    outbound_error = _request_integrity_error(outbound, pristine_card)
    try:
        _restore_request_caller(caller, pristine, anchors)
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_REQUEST_INVALID"
        ) from error
    restored_error = _request_integrity_error(caller, pristine_card)
    if restored_error is not None:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_REQUEST_INVALID"
        ) from restored_error
    if caller_error is not None:
        raise caller_error
    if outbound_error is not None:
        raise outbound_error


def _database_card(database: _path.DatabaseIdentity) -> dict[str, object]:
    return {
        "family": database.family,
        "database_id": database.database_id,
        "database_sha256": database.database_sha256,
        "profile_id": database.profile_id,
        "profile_role": database.profile_role,
        "fe_baseline_decision": database.fe_baseline_decision,
        "c15_exclusion_decision": database.c15_exclusion_decision,
    }


def _request_card(request: object) -> dict[str, object]:
    checked = _copy_request(request)
    selection = checked.phase_selection
    card: dict[str, object] = {
        "database_identity": _database_card(checked.database),
        "components": list(checked.components),
        "composition": [
            {"component": component, "mole_fraction": amount}
            for component, amount in checked.composition
        ],
        "phases": {
            "candidate": list(selection.candidate_phases),
            "requested": list(selection.requested_phases),
            "excluded": list(selection.excluded_phases),
            "effective": list(selection.effective_phases),
        },
        "liquid_phase": checked.liquid_phase,
        "pressure_pa": checked.pressure_pa,
        "start_temperature_k": checked.start_temperature_k,
        "step_temperature_k": checked.step_temperature_k,
        "adaptive": checked.adaptive,
        "pdens": checked.pdens,
        "method": checked.method,
    }
    if type(checked) is _path.EquilibriumSolidificationRequest:
        card["binary_search_tolerance_k"] = checked.binary_search_tolerance_k
    else:
        card["stop_liquid_fraction"] = checked.stop_liquid_fraction
    return card


def _profile_matches_request(
    profile: object,
    request: object,
) -> None:
    checked = _copy_request(request)
    try:
        binding = _receipts.request_database_binding(profile)
        family = profile.family
        profile_id = profile.profile
        profile_role = profile.profile_role
        runtime_sha256 = profile.runtime.sha256
        baseline = profile.baseline_decision
        c15 = profile.c15_exclusion_decision
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_PROFILE_IDENTITY_MISMATCH"
        ) from error
    database = checked.database
    if (
        type(binding) is not dict
        or family not in SUPPORTED_DATABASE_FAMILIES
        or database.family != family
        or database.profile_id != profile_id
        or database.database_id != profile_id
        or database.database_sha256 != runtime_sha256
        or database.fe_baseline_decision != baseline
        or database.c15_exclusion_decision != c15
    ):
        _fail("W2B_SOLID_BACKEND_PROFILE_IDENTITY_MISMATCH")
    if database.profile_role != profile_role:
        if (
            family in IDENTITY_V2_REQUIRED_FAMILIES
            and profile_role == "RELEASE_CANDIDATE_PENDING_NE04"
            and database.profile_role == "EVALUATION_PROFILE"
        ):
            _fail("W2B_SOLID_BACKEND_IDENTITY_CONTRACT_INCOMPATIBLE")
        else:
            _fail("W2B_SOLID_BACKEND_PROFILE_IDENTITY_MISMATCH")
    if family == "fe":
        if (
            profile_id not in SUPPORTED_FE_PROFILE_IDS
            or baseline != _receipts.FE_POLICY_UNDECIDED
            or c15 != _receipts.FE_POLICY_UNDECIDED
            or "C15_LAVES" not in checked.phase_selection.candidate_phases
            or "C15_LAVES" not in checked.phase_selection.requested_phases
            or "C15_LAVES" in checked.phase_selection.excluded_phases
            or "C15_LAVES" not in checked.phase_selection.effective_phases
        ):
            _fail("W2B_SOLID_BACKEND_FE_POLICY_REQUIRED")
    elif profile_id in SUPPORTED_FE_PROFILE_IDS:
        _fail("W2B_SOLID_BACKEND_PROFILE_IDENTITY_MISMATCH")


def solidification_full_request(
    profile_receipt: object,
    request: object,
) -> dict[str, object]:
    """Return the exact full-request card required by ``DomainReceipt``."""

    checked = _copy_request(request)
    _bind_solidification_identity_to_v2_profile(
        checked,
        _database_identity_v2(profile_receipt),
    )
    return {
        "feature_id": checked.feature,
        "database": _receipts.request_database_binding(profile_receipt),
        "request": _request_card(checked),
    }


def _database_identity_v2(profile_receipt: object) -> _path_v2.DatabaseIdentityV2:
    try:
        _receipts.request_database_binding(profile_receipt)
        family = profile_receipt.family
        profile_id = profile_receipt.profile
        database_id = (
            "mc_fe_v2062" if family == "fe" else profile_id
        )
        return _path_v2.DatabaseIdentityV2(
            family=family,
            database_id=database_id,
            database_sha256=profile_receipt.runtime.sha256,
            profile_id=profile_id,
            profile_role=profile_receipt.profile_role,
            fe_baseline_decision=profile_receipt.baseline_decision,
            c15_exclusion_decision=profile_receipt.c15_exclusion_decision,
        )
    except _path_v2.PathContractV2Error as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_PROFILE_IDENTITY_MISMATCH"
        ) from error
    except Wave2BSolidificationBackendError:
        raise
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_PROFILE_IDENTITY_MISMATCH"
        ) from error


def _bind_solidification_identity_to_v2_profile(
    request: object,
    identity: _path_v2.DatabaseIdentityV2,
) -> None:
    """Bind the legacy request carrier without copying its V1-only role."""

    checked = _copy_request(request)
    legacy = checked.database
    expected_legacy_database_id = (
        identity.profile_id if identity.family == "fe" else identity.database_id
    )
    if (
        legacy.family != identity.family
        or legacy.database_id != expected_legacy_database_id
        or legacy.database_sha256 != identity.database_sha256
        or legacy.profile_id != identity.profile_id
    ):
        _fail("W2B_SOLID_BACKEND_PROFILE_IDENTITY_MISMATCH")
    if identity.family == "fe":
        selection = checked.phase_selection
        if (
            legacy.profile_role != identity.profile_role
            or legacy.fe_baseline_decision != identity.fe_baseline_decision
            or legacy.c15_exclusion_decision
            != identity.c15_exclusion_decision
            or "C15_LAVES" not in selection.candidate_phases
            or "C15_LAVES" not in selection.requested_phases
            or "C15_LAVES" in selection.excluded_phases
            or "C15_LAVES" not in selection.effective_phases
        ):
            _fail("W2B_SOLID_BACKEND_FE_POLICY_REQUIRED")
    elif (
        legacy.profile_role != "EVALUATION_PROFILE"
        or legacy.fe_baseline_decision != _receipts.POLICY_NOT_APPLICABLE
        or legacy.c15_exclusion_decision != _receipts.POLICY_NOT_APPLICABLE
    ):
        _fail("W2B_SOLID_BACKEND_PROFILE_IDENTITY_MISMATCH")


def _phase_domain_v2(request: object) -> _path_v2.PhaseDomainV2:
    checked = _copy_request(request)
    selection = checked.phase_selection
    try:
        return _path_v2.PhaseDomainV2(
            candidate_phases=tuple(selection.candidate_phases),
            requested_phases=tuple(selection.requested_phases),
            excluded_phases=tuple(selection.excluded_phases),
            effective_phases=tuple(selection.effective_phases),
        )
    except _path_v2.PathContractV2Error as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_DOMAIN_MISMATCH"
        ) from error


def solidification_full_request_payload_v2(
    profile_receipt: object,
    request: object,
) -> dict[str, object]:
    """Return the exact Contract V2 request identity without a free lease card."""

    _guard_path_contract_v2()
    checked = _copy_request(request)
    database = _database_identity_v2(profile_receipt)
    _bind_solidification_identity_to_v2_profile(checked, database)
    domain = _phase_domain_v2(checked)
    request_card = _request_card(checked)
    request_card["database_identity"] = {
        "family": database.family,
        "database_id": database.database_id,
        "database_sha256": database.database_sha256,
        "profile_id": database.profile_id,
        "profile_role": database.profile_role,
        "fe_baseline_decision": database.fe_baseline_decision,
        "c15_exclusion_decision": database.c15_exclusion_decision,
    }
    request_card["schema_version"] = REQUIRED_SOLIDIFICATION_CONTRACT_SCHEMA
    request_card["contract_version"] = REQUIRED_SOLIDIFICATION_CONTRACT_VERSION
    request_card["contract_sha256"] = PATH_CONTRACT_V2_SHA256
    request_card["phases"] = {
        "candidate": list(domain.candidate_phases),
        "requested": list(domain.requested_phases),
        "excluded": list(domain.excluded_phases),
        "effective": list(domain.effective_phases),
    }
    return {
        "feature_id": checked.feature,
        "database": _receipts.request_database_binding(profile_receipt),
        "request": request_card,
    }


def solidification_solver_options(request: object) -> dict[str, object]:
    """Return the exact method options that must be receipt-bound."""

    checked = _copy_request(request)
    options: dict[str, object] = {
        "adaptive": checked.adaptive,
        "pdens": checked.pdens,
    }
    if type(checked) is _path.EquilibriumSolidificationRequest:
        options["binary_search_tolerance_k"] = checked.binary_search_tolerance_k
    else:
        options["stop_liquid_fraction"] = checked.stop_liquid_fraction
    return options


def solidification_bounds(
    request: object,
    *,
    minimum_temperature_k: object,
) -> dict[str, object]:
    """Bind the exact start and fixed pressure plus a terminal lower bound."""

    checked = _copy_request(request)
    minimum = _finite(
        minimum_temperature_k,
        "W2B_SOLID_BACKEND_BOUNDS_INVALID",
    )
    if minimum <= 0.0 or minimum >= checked.start_temperature_k:
        _fail("W2B_SOLID_BACKEND_BOUNDS_INVALID")
    return {
        "temperature_k": {
            "minimum": minimum,
            "maximum": checked.start_temperature_k,
        },
        "pressure_pa": {
            "minimum": SOLIDIFICATION_PRESSURE_PA,
            "maximum": SOLIDIFICATION_PRESSURE_PA,
        },
    }


@_dataclass(frozen=True, slots=True)
class _SolverModules:
    Database: object
    variables: object
    simulate_equilibrium_solidification: object
    simulate_scheil_solidification: object
    numpy: object
    pycalphad_version: str
    scheil_version: str
    diagnostic_kind: str
    provenance: str


def _load_solver_modules() -> _SolverModules:
    """Load the scientific stack only for an actual backend call."""

    try:
        pycalphad = _importlib.import_module("pycalphad")
        scheil = _importlib.import_module("scheil")
        numpy = _importlib.import_module("numpy")
        modules = _SolverModules(
            Database=getattr(pycalphad, "Database"),
            variables=getattr(pycalphad, "variables"),
            simulate_equilibrium_solidification=getattr(
                scheil,
                "simulate_equilibrium_solidification",
            ),
            simulate_scheil_solidification=getattr(
                scheil,
                "simulate_scheil_solidification",
            ),
            numpy=numpy,
            pycalphad_version=getattr(pycalphad, "__version__"),
            scheil_version=getattr(scheil, "__version__"),
            diagnostic_kind=_NATIVE_DIAGNOSTIC_KIND,
            provenance=_NATIVE_PROVENANCE,
        )
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_PYCALPHAD_UNAVAILABLE"
        ) from error
    if modules.pycalphad_version != "0.11.2":
        _fail("W2B_SOLID_BACKEND_PYCALPHAD_VERSION_MISMATCH")
    if modules.scheil_version != "0.3.0":
        _fail("W2B_SOLID_BACKEND_SCHEIL_VERSION_MISMATCH")
    if (
        modules.provenance != _NATIVE_PROVENANCE
        or modules.diagnostic_kind != _NATIVE_DIAGNOSTIC_KIND
    ):
        _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
    return modules


@_dataclass(frozen=True, slots=True)
class _AttemptDiagnostic:
    ordinal: int
    attempt_id: str
    kind: str
    provenance: str
    outcome: str
    temperature_k: float
    result_index: int | None
    reason_code: str | None
    transient: bool

    def __post_init__(self) -> None:
        if type(self.ordinal) is not int or self.ordinal < 0:
            _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")
        if (
            type(self.attempt_id) is not str
            or not self.attempt_id
            or len(self.attempt_id) > 128
            or type(self.kind) is not str
            or self.kind
            not in {
                "INITIAL_STATE_VALIDATION",
                "COOLING_STEP",
                "ADAPTIVE_STEP",
                "ADAPTIVE_BACKTRACK",
                "BINARY_SEARCH",
            }
            or type(self.provenance) is not str
            or self.provenance != _MANUFACTURED_PROVENANCE
            or type(self.outcome) is not str
            or type(self.transient) is not bool
        ):
            _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")
        temperature = _finite(
            self.temperature_k,
            "W2B_SOLID_BACKEND_RESULT_INVALID",
        )
        if temperature <= 0.0 or self.outcome not in ("ACCEPTED", "FAILED"):
            if self.outcome not in ("ACCEPTED", "FAILED"):
                _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")
            _fail("W2B_SOLID_BACKEND_RESULT_INVALID")
        if self.outcome == "ACCEPTED":
            if (
                type(self.result_index) is not int
                or self.result_index < 0
                or self.reason_code is not None
            ):
                _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")
        elif (
            self.result_index is not None
            or type(self.reason_code) is not str
            or self.reason_code
            not in {
                "W2B_SOLID_BACKEND_NODE_FAILED",
                "W2B_SOLID_BACKEND_DOMAIN_FAILED",
                "W2B_SOLID_BACKEND_INTERNAL_FAILED",
            }
        ):
            _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")
        object.__setattr__(self, "temperature_k", temperature)


@_dataclass(frozen=True, slots=True)
class _SyntheticResultRow:
    result_index: int
    provenance: str
    reason_code: str

    def __post_init__(self) -> None:
        if (
            type(self.result_index) is not int
            or self.result_index < 0
            or type(self.provenance) is not str
            or self.provenance != "MANUFACTURED_TEST_ONLY_SYNTHETIC_INITIAL_STATE"
            or type(self.reason_code) is not str
            or self.reason_code
            != "SCHEIL_LIBRARY_SYNTHETIC_INITIAL_STATE_NOT_PHYSICAL_ATTEMPT"
        ):
            _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")


@_dataclass(frozen=True, slots=True)
class _DiagnosticSolverResult:
    schema_version: str
    provenance: str
    diagnostics_complete: bool
    instrumentation_id: str
    instrumentation_version: str
    instrumentation_level: str
    full_attempt_ledger: bool
    failed_attempts_retained: bool
    merged_attempts_retained: bool
    abandoned_attempts_retained: bool
    adaptive_backtracks_retained: bool
    binary_search_attempts_retained: bool
    transient_attempts_retained: bool
    synthetic_rows_explicit: bool
    service_closure_separated: bool
    partial: bool
    unresolved_attempt_count: int
    attempt_budget: int
    budget_exhausted: bool
    attempt_count: int
    result: object
    attempts: tuple[_AttemptDiagnostic, ...]
    synthetic_rows: tuple[_SyntheticResultRow, ...]
    termination_reason_code: str

    def __post_init__(self) -> None:
        flags = (
            self.diagnostics_complete,
            self.full_attempt_ledger,
            self.failed_attempts_retained,
            self.merged_attempts_retained,
            self.abandoned_attempts_retained,
            self.adaptive_backtracks_retained,
            self.binary_search_attempts_retained,
            self.transient_attempts_retained,
            self.synthetic_rows_explicit,
            self.service_closure_separated,
        )
        if (
            type(self.schema_version) is not str
            or self.schema_version != _DIAGNOSTIC_ENVELOPE_SCHEMA
            or type(self.provenance) is not str
            or self.provenance != _MANUFACTURED_PROVENANCE
            or type(self.instrumentation_id) is not str
            or self.instrumentation_id != _MANUFACTURED_INSTRUMENTATION_ID
            or type(self.instrumentation_version) is not str
            or self.instrumentation_version
            != _MANUFACTURED_INSTRUMENTATION_VERSION
            or type(self.instrumentation_level) is not str
            or self.instrumentation_level != _FULL_INSTRUMENTATION_LEVEL
            or any(type(flag) is not bool for flag in flags)
            or not all(flags)
            or type(self.partial) is not bool
            or self.partial
            or type(self.unresolved_attempt_count) is not int
            or self.unresolved_attempt_count != 0
            or type(self.attempt_budget) is not int
            or self.attempt_budget < 1
            or type(self.budget_exhausted) is not bool
            or self.budget_exhausted
            or type(self.attempt_count) is not int
            or type(self.attempts) is not tuple
            or not self.attempts
            or self.attempt_count != len(self.attempts)
            or self.attempt_count > self.attempt_budget
        ):
            _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")
        if any(type(item) is not _AttemptDiagnostic for item in self.attempts):
            _fail("W2B_SOLID_BACKEND_RESULT_INVALID")
        if tuple(item.ordinal for item in self.attempts) != tuple(
            range(len(self.attempts))
        ):
            _fail("W2B_SOLID_BACKEND_RESULT_INVALID")
        if (
            len({item.attempt_id for item in self.attempts}) != len(self.attempts)
            or type(self.synthetic_rows) is not tuple
            or any(type(item) is not _SyntheticResultRow for item in self.synthetic_rows)
            or len({item.result_index for item in self.synthetic_rows})
            != len(self.synthetic_rows)
            or type(self.termination_reason_code) is not str
            or not self.termination_reason_code
        ):
            _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")


def _rebuild_diagnostic_result(value: object) -> _DiagnosticSolverResult:
    if type(value) is not _DiagnosticSolverResult:
        _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")
    try:
        attempts = tuple(
            _AttemptDiagnostic(
                ordinal=item.ordinal,
                attempt_id=item.attempt_id,
                kind=item.kind,
                provenance=item.provenance,
                outcome=item.outcome,
                temperature_k=item.temperature_k,
                result_index=item.result_index,
                reason_code=item.reason_code,
                transient=item.transient,
            )
            for item in value.attempts
        )
        synthetic = tuple(
            _SyntheticResultRow(
                result_index=item.result_index,
                provenance=item.provenance,
                reason_code=item.reason_code,
            )
            for item in value.synthetic_rows
        )
        return _DiagnosticSolverResult(
            schema_version=value.schema_version,
            provenance=value.provenance,
            diagnostics_complete=value.diagnostics_complete,
            instrumentation_id=value.instrumentation_id,
            instrumentation_version=value.instrumentation_version,
            instrumentation_level=value.instrumentation_level,
            full_attempt_ledger=value.full_attempt_ledger,
            failed_attempts_retained=value.failed_attempts_retained,
            merged_attempts_retained=value.merged_attempts_retained,
            abandoned_attempts_retained=value.abandoned_attempts_retained,
            adaptive_backtracks_retained=value.adaptive_backtracks_retained,
            binary_search_attempts_retained=value.binary_search_attempts_retained,
            transient_attempts_retained=value.transient_attempts_retained,
            synthetic_rows_explicit=value.synthetic_rows_explicit,
            service_closure_separated=value.service_closure_separated,
            partial=value.partial,
            unresolved_attempt_count=value.unresolved_attempt_count,
            attempt_budget=value.attempt_budget,
            budget_exhausted=value.budget_exhausted,
            attempt_count=value.attempt_count,
            result=value.result,
            attempts=attempts,
            synthetic_rows=synthetic,
            termination_reason_code=value.termination_reason_code,
        )
    except Wave2BSolidificationBackendError:
        raise
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS"
        ) from error


@_dataclass(frozen=True, slots=True)
class _NativeObservationV2:
    temperature_k: float
    solid_fraction: _path_v2.Binary64FractionV2
    liquid_fraction: _path_v2.Binary64FractionV2
    phase_fractions: tuple[_path_v2.PhaseFractionV2, ...]
    liquid_composition: tuple[_path_v2.CompositionEntryV2, ...]


def _native_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
        ) from error
    if not _math.isfinite(number):
        _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
    return number


def _native_fraction(value: object) -> _path_v2.Binary64FractionV2:
    number = _native_number(value)
    try:
        return _path_v2.Binary64FractionV2.observe(number)
    except _path_v2.PathContractV2Error as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
        ) from error


def _native_composition(
    liquid: dict[str, tuple[object, ...]],
    index: int,
    pure_components: tuple[str, ...],
) -> tuple[_path_v2.CompositionEntryV2, ...]:
    try:
        return tuple(
            _path_v2.CompositionEntryV2(
                component=component,
                fraction=_native_fraction(liquid[component][index]),
            )
            for component in pure_components
        )
    except Wave2BSolidificationBackendError:
        raise
    except _path_v2.PathContractV2Error as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
        ) from error
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
        ) from error


def _phase_instance_v2(name: str) -> _path_v2.PhaseInstanceV2:
    if type(name) is not str or name.count("#") > 1:
        _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
    if "#" in name:
        base, marker, suffix = name.rpartition("#")
        if marker != "#" or not base or not suffix.isascii() or not suffix.isdigit():
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        try:
            index = int(suffix)
        except (OverflowError, TypeError, ValueError) as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
            ) from error
    else:
        base = name
        index = 1
    try:
        return _path_v2.PhaseInstanceV2(
            instance_name=name,
            base_phase=base,
            instance_index=index,
        )
    except _path_v2.PathContractV2Error as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
        ) from error


def _native_phase_fractions(
    cumulative: dict[str, tuple[object, ...]],
    index: int,
    solid_fraction: _path_v2.Binary64FractionV2,
    allowed_solid_phases: frozenset[str],
) -> tuple[_path_v2.PhaseFractionV2, ...]:
    grouped: dict[
        str,
        list[tuple[str, _path_v2.PhaseInstanceV2, _path_v2.Binary64FractionV2]],
    ] = {}
    for name in sorted(cumulative):
        phase_instance = _phase_instance_v2(name)
        if phase_instance.base_phase not in allowed_solid_phases:
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        fraction = _native_fraction(cumulative[name][index])
        grouped.setdefault(phase_instance.base_phase, []).append(
            (name, phase_instance, fraction)
        )

    selected: list[_path_v2.PhaseFractionV2] = []
    for base in sorted(grouped):
        entries = grouped[base]
        plain = tuple(item for item in entries if "#" not in item[0])
        explicit = tuple(item for item in entries if "#" in item[0])
        positive_plain = tuple(
            item for item in plain if item[2].canonical_value != 0.0
        )
        positive_explicit = tuple(
            item for item in explicit if item[2].canonical_value != 0.0
        )
        if positive_plain and positive_explicit:
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        if positive_explicit:
            indices = tuple(
                item[1].instance_index
                for item in sorted(
                    positive_explicit,
                    key=lambda item: item[1].instance_index,
                )
            )
            if indices != tuple(range(1, len(indices) + 1)):
                _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
            retained = positive_explicit
        elif positive_plain:
            if len(positive_plain) != 1:
                _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
            retained = positive_plain
        else:
            retained = tuple()
        for _name, phase_instance, fraction in retained:
            try:
                selected.append(
                    _path_v2.PhaseFractionV2(
                        phase_instance=phase_instance,
                        fraction=fraction,
                    )
                )
            except _path_v2.PathContractV2Error as error:
                raise Wave2BSolidificationBackendError(
                    "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
                ) from error

    if solid_fraction.canonical_value == 0.0 and selected:
        _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
    return tuple(selected)


class _ReceiptBoundContext:
    """Exact active-lease guard independent of application/UI state."""

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
        "_effective_phases",
        "_excluded_phases",
        "_full_request",
        "_bounds",
        "_solver_options",
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
                _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
            domain_bytes = _receipts.receipt_json_bytes(domain_receipt)
            pre_bytes = _receipts.receipt_json_bytes(pre_snapshot)
            profile = domain_receipt.profile_receipt
            if (
                domain_receipt.execution_mode != _receipts.INTERNAL_QUALIFICATION
                or domain_receipt.authorization_state
                != "INTERNAL_QUALIFICATION_ONLY_NOT_RELEASE"
                or profile.verification_mode != _receipts.INTERNAL_QUALIFICATION
            ):
                _fail("W2B_SOLID_BACKEND_INTERNAL_QUALIFICATION_REQUIRED")
            lease_id = execution_lease.lease_id
            snapshot_digest = execution_lease.execution_snapshot_digest
            runtime_path = execution_lease.file_path("runtime").resolve(strict=True)
            if (
                pre_snapshot.lease_id != lease_id
                or pre_snapshot.domain_receipt_digest
                != domain_receipt.canonical_digest
                or pre_snapshot.profile_receipt_digest
                != profile.canonical_digest
                or pre_snapshot.execution_snapshot_digest != snapshot_digest
            ):
                _fail("W2B_SOLID_BACKEND_PRE_MISMATCH")
            if (
                domain_receipt.feature_id not in BOUND_OPERATIONS
                or profile.family not in SUPPORTED_DATABASE_FAMILIES
            ):
                _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
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
                    _fail("W2B_SOLID_BACKEND_FE_POLICY_REQUIRED")
            elif profile.profile in SUPPORTED_FE_PROFILE_IDS:
                _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
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
            self._effective_phases = tuple(domain_receipt.effective_phases)
            self._excluded_phases = tuple(domain_receipt.excluded_phases)
            self._full_request = _payload_dict(domain_receipt.full_request)
            self._bounds = _payload_dict(domain_receipt.bounds)
            self._solver_options = _payload_dict(domain_receipt.solver_options)
        except Wave2BSolidificationBackendError:
            raise
        except _receipts.ReceiptError as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_LEASE_INACTIVE"
            ) from error
        except Exception as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_CONTEXT_INVALID"
            ) from error
        self._validate_static_domain()
        self._guard()

    def _validate_static_domain(self) -> None:
        if set(self._full_request) != {"feature_id", "database", "request"}:
            _fail("W2B_SOLID_BACKEND_DOMAIN_MISMATCH")
        if self._full_request.get("feature_id") != self._feature_id:
            _fail("W2B_SOLID_BACKEND_DOMAIN_MISMATCH")
        if set(self._bounds) != {"temperature_k", "pressure_pa"}:
            _fail("W2B_SOLID_BACKEND_BOUNDS_INVALID")
        temperature = self._bounds.get("temperature_k")
        pressure = self._bounds.get("pressure_pa")
        for card in (temperature, pressure):
            if type(card) is not dict or set(card) != {"minimum", "maximum"}:
                _fail("W2B_SOLID_BACKEND_BOUNDS_INVALID")
        p_min = _finite(pressure["minimum"], "W2B_SOLID_BACKEND_BOUNDS_INVALID")
        p_max = _finite(pressure["maximum"], "W2B_SOLID_BACKEND_BOUNDS_INVALID")
        t_min = _finite(temperature["minimum"], "W2B_SOLID_BACKEND_BOUNDS_INVALID")
        t_max = _finite(temperature["maximum"], "W2B_SOLID_BACKEND_BOUNDS_INVALID")
        if (
            not _same_binary64(p_min, SOLIDIFICATION_PRESSURE_PA)
            or not _same_binary64(p_max, SOLIDIFICATION_PRESSURE_PA)
            or t_min <= 0.0
            or t_min >= t_max
        ):
            _fail("W2B_SOLID_BACKEND_BOUNDS_INVALID")
        expected_keys = (
            {"adaptive", "pdens", "binary_search_tolerance_k"}
            if self._feature_id == "equilibrium_solidification"
            else {"adaptive", "pdens", "stop_liquid_fraction"}
        )
        if set(self._solver_options) != expected_keys:
            _fail("W2B_SOLID_BACKEND_SOLVER_OPTIONS_UNSUPPORTED")

    def _guard_receipt_identity(self) -> None:
        try:
            profile = self._domain.profile_receipt
            if (
                type(self._domain) is not _receipts.DomainReceipt
                or type(self._pre) is not _receipts.PreExecutionSnapshot
                or type(self._lease) is not _receipts.ExecutionLease
                or _receipts.receipt_json_bytes(self._domain) != self._domain_bytes
                or _receipts.receipt_json_bytes(self._pre) != self._pre_bytes
                or self._domain.canonical_digest != self._domain_digest
                or profile.canonical_digest != self._profile_digest
                or self._lease.lease_id != self._lease_id
                or self._lease.execution_snapshot_digest != self._snapshot_digest
                or self._pre.lease_id != self._lease_id
                or self._pre.domain_receipt_digest != self._domain_digest
                or self._pre.profile_receipt_digest != self._profile_digest
                or self._pre.execution_snapshot_digest != self._snapshot_digest
                or profile.family != self._family
                or profile.profile != self._profile
                or profile.runtime.sha256 != self._runtime_sha256
                or self._domain.feature_id != self._feature_id
                or tuple(self._domain.candidate_phases) != self._candidate_phases
                or tuple(self._domain.requested_phases) != self._requested_phases
                or tuple(self._domain.effective_phases) != self._effective_phases
                or tuple(self._domain.excluded_phases) != self._excluded_phases
                or _payload_dict(self._domain.full_request) != self._full_request
                or _payload_dict(self._domain.bounds) != self._bounds
                or _payload_dict(self._domain.solver_options)
                != self._solver_options
            ):
                _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
        except Wave2BSolidificationBackendError:
            raise
        except _receipts.ReceiptError as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_LEASE_INACTIVE"
            ) from error
        except Exception as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_CONTEXT_INVALID"
            ) from error

    def _guard(self) -> _Path:
        self._guard_receipt_identity()
        try:
            path = self._lease.file_path("runtime").resolve(strict=True)
            if path != self._runtime_path or not path.is_file():
                _fail("W2B_SOLID_BACKEND_RUNTIME_PATH_INVALID")
            return path
        except Wave2BSolidificationBackendError:
            raise
        except _receipts.ReceiptError as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_LEASE_INACTIVE"
            ) from error
        except Exception as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_CONTEXT_INVALID"
            ) from error


class ReceiptBoundSolidificationBackend(_ReceiptBoundContext):
    """Receipt-bound structural ``SolidificationBackend`` implementation."""

    __slots__ = (
        "_solver_modules",
        "_database_object",
        "_manufactured_test_only",
        "_attempted_calls",
        "_completed_calls",
        "_failed_calls",
    )

    def __init__(
        self,
        *,
        domain_receipt: object,
        pre_snapshot: object,
        execution_lease: object,
    ) -> None:
        super().__init__(
            domain_receipt=domain_receipt,
            pre_snapshot=pre_snapshot,
            execution_lease=execution_lease,
        )
        self._solver_modules: _SolverModules | None = None
        self._database_object: object | None = None
        self._manufactured_test_only = False
        self._attempted_calls = 0
        self._completed_calls = 0
        self._failed_calls = 0

    def _modules(self) -> _SolverModules:
        self._guard()
        if self._solver_modules is None:
            self._solver_modules = _load_solver_modules()
        if type(self._solver_modules) is not _SolverModules:
            _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
        modules = self._solver_modules
        if any(
            type(value) is not str
            for value in (
                modules.pycalphad_version,
                modules.scheil_version,
                modules.diagnostic_kind,
                modules.provenance,
            )
        ):
            _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
        if modules.provenance == _NATIVE_PROVENANCE:
            if (
                modules.pycalphad_version != "0.11.2"
                or modules.scheil_version != "0.3.0"
                or modules.diagnostic_kind != _NATIVE_DIAGNOSTIC_KIND
            ):
                _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
        elif modules.provenance == _MANUFACTURED_PROVENANCE:
            if (
                modules.pycalphad_version != _MANUFACTURED_PROVENANCE
                or modules.scheil_version != _MANUFACTURED_PROVENANCE
                or modules.diagnostic_kind != _MANUFACTURED_DIAGNOSTIC_KIND
            ):
                _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
            self._manufactured_test_only = True
        else:
            _fail("W2B_SOLID_BACKEND_CONTEXT_INVALID")
        return modules

    def _database(self) -> object:
        runtime_path = self._guard()
        if self._database_object is None:
            modules = self._modules()
            try:
                self._database_object = modules.Database(str(runtime_path))  # type: ignore[operator]
            except Exception as error:
                raise Wave2BSolidificationBackendError(
                    "W2B_SOLID_BACKEND_DATABASE_LOAD_FAILED"
                ) from error
            self._guard()
        return self._database_object

    def _execution_binding_v2(self) -> _path_v2.ExecutionBindingV2:
        self._guard()
        try:
            return _path_v2.ExecutionBindingV2(
                profile_receipt_digest=self._profile_digest,
                domain_receipt_digest=self._domain_digest,
                execution_lease_id=self._lease_id,
                execution_snapshot_digest=self._snapshot_digest,
            )
        except _path_v2.PathContractV2Error as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_CONTEXT_INVALID"
            ) from error

    def _bind_request(
        self,
        request: object,
    ):
        checked = _copy_request(request)
        _profile_matches_request(self._domain.profile_receipt, checked)
        if checked.feature != self._feature_id:
            _fail("W2B_SOLID_BACKEND_DOMAIN_MISMATCH")
        selection = checked.phase_selection
        if (
            tuple(sorted(selection.candidate_phases)) != self._candidate_phases
            or tuple(sorted(selection.requested_phases)) != self._requested_phases
            or tuple(sorted(selection.excluded_phases)) != self._excluded_phases
            or tuple(sorted(selection.effective_phases)) != self._effective_phases
            or solidification_full_request(self._domain.profile_receipt, checked)
            != self._full_request
        ):
            _fail("W2B_SOLID_BACKEND_DOMAIN_MISMATCH")
        if solidification_solver_options(checked) != self._solver_options:
            _fail("W2B_SOLID_BACKEND_SOLVER_OPTIONS_UNSUPPORTED")
        temperature = self._bounds["temperature_k"]
        pressure = self._bounds["pressure_pa"]
        minimum = _finite(
            temperature["minimum"],
            "W2B_SOLID_BACKEND_BOUNDS_INVALID",
        )
        maximum = _finite(
            temperature["maximum"],
            "W2B_SOLID_BACKEND_BOUNDS_INVALID",
        )
        if (
            not _same_binary64(maximum, checked.start_temperature_k)
            or not _same_binary64(
                _finite(pressure["minimum"], "W2B_SOLID_BACKEND_BOUNDS_INVALID"),
                checked.pressure_pa,
            )
            or not _same_binary64(
                _finite(pressure["maximum"], "W2B_SOLID_BACKEND_BOUNDS_INVALID"),
                checked.pressure_pa,
            )
            or not _same_binary64(checked.pressure_pa, SOLIDIFICATION_PRESSURE_PA)
            or checked.step_temperature_k >= checked.start_temperature_k - minimum
        ):
            _fail("W2B_SOLID_BACKEND_BOUNDS_INVALID")
        return checked

    def _bind_request_v2(
        self,
        request: object,
    ) -> tuple[object, _path_v2.DatabaseIdentityV2]:
        checked = _copy_request(request)
        identity = _database_identity_v2(self._domain.profile_receipt)
        _bind_solidification_identity_to_v2_profile(checked, identity)
        if checked.feature != self._feature_id:
            _fail("W2B_SOLID_BACKEND_DOMAIN_MISMATCH")
        selection = checked.phase_selection
        if (
            tuple(sorted(selection.candidate_phases)) != self._candidate_phases
            or tuple(sorted(selection.requested_phases)) != self._requested_phases
            or tuple(sorted(selection.excluded_phases)) != self._excluded_phases
            or tuple(sorted(selection.effective_phases)) != self._effective_phases
            or solidification_full_request_payload_v2(
                self._domain.profile_receipt,
                checked,
            )
            != self._full_request
        ):
            _fail("W2B_SOLID_BACKEND_DOMAIN_MISMATCH")
        if solidification_solver_options(checked) != self._solver_options:
            _fail("W2B_SOLID_BACKEND_SOLVER_OPTIONS_UNSUPPORTED")
        temperature = self._bounds["temperature_k"]
        pressure = self._bounds["pressure_pa"]
        minimum = _finite(
            temperature["minimum"],
            "W2B_SOLID_BACKEND_BOUNDS_INVALID",
        )
        maximum = _finite(
            temperature["maximum"],
            "W2B_SOLID_BACKEND_BOUNDS_INVALID",
        )
        if (
            not _same_binary64(maximum, checked.start_temperature_k)
            or not _same_binary64(
                _finite(pressure["minimum"], "W2B_SOLID_BACKEND_BOUNDS_INVALID"),
                checked.pressure_pa,
            )
            or not _same_binary64(
                _finite(pressure["maximum"], "W2B_SOLID_BACKEND_BOUNDS_INVALID"),
                checked.pressure_pa,
            )
            or not _same_binary64(checked.pressure_pa, SOLIDIFICATION_PRESSURE_PA)
            or checked.step_temperature_k
            >= checked.start_temperature_k - minimum
        ):
            _fail("W2B_SOLID_BACKEND_BOUNDS_INVALID")
        return checked, identity

    @staticmethod
    def _solver_composition(modules: _SolverModules, request: object):
        pure = tuple(name for name in request.components if name != "VA")
        if len(pure) < 2:
            _fail("W2B_SOLID_BACKEND_REQUEST_INVALID")
        amounts = dict(request.composition)
        dependent = pure[-1]
        variables = modules.variables
        try:
            return {
                variables.X(component): amounts[component]
                for component in pure
                if component != dependent
            }
        except Exception as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_REQUEST_INVALID"
            ) from error

    def _invoke_diagnostic_solver(
        self,
        modules: _SolverModules,
        database: object,
        request: object,
    ) -> _DiagnosticSolverResult:
        if (
            modules.provenance != _MANUFACTURED_PROVENANCE
            or modules.diagnostic_kind != _MANUFACTURED_DIAGNOSTIC_KIND
        ):
            _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")
        composition = self._solver_composition(modules, request)
        kwargs = {
            "dbf": database,
            "comps": list(request.components),
            "phases": list(request.phases),
            "composition": composition,
            "start_temperature": request.start_temperature_k,
            "step_temperature": request.step_temperature_k,
            "liquid_phase_name": request.liquid_phase,
            "adaptive": request.adaptive,
            "eq_kwargs": {"calc_opts": {"pdens": request.pdens}},
            "verbose": False,
        }
        try:
            if type(request) is _path.EquilibriumSolidificationRequest:
                returned = modules.simulate_equilibrium_solidification(  # type: ignore[operator]
                    **kwargs,
                    binary_search_tol=request.binary_search_tolerance_k,
                )
            else:
                returned = modules.simulate_scheil_solidification(  # type: ignore[operator]
                    **kwargs,
                    stop=request.stop_liquid_fraction,
                )
        except Wave2BSolidificationBackendError:
            raise
        except Exception as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS"
            ) from error
        return _rebuild_diagnostic_result(returned)

    def _invoke_native_solver(
        self,
        modules: _SolverModules,
        database: object,
        request: object,
    ) -> object:
        if (
            modules.provenance != _NATIVE_PROVENANCE
            or modules.diagnostic_kind != _NATIVE_DIAGNOSTIC_KIND
            or modules.pycalphad_version != "0.11.2"
            or modules.scheil_version != "0.3.0"
        ):
            _fail("W2B_SOLID_BACKEND_NATIVE_RUNTIME_REQUIRED")
        composition = self._solver_composition(modules, request)
        kwargs = {
            "dbf": database,
            "comps": list(request.components),
            "phases": list(request.phases),
            "composition": composition,
            "start_temperature": request.start_temperature_k,
            "step_temperature": request.step_temperature_k,
            "liquid_phase_name": request.liquid_phase,
            "adaptive": request.adaptive,
            "eq_kwargs": {"calc_opts": {"pdens": request.pdens}},
            "verbose": False,
        }
        try:
            if type(request) is _path.EquilibriumSolidificationRequest:
                return modules.simulate_equilibrium_solidification(  # type: ignore[operator]
                    **kwargs,
                    binary_search_tol=request.binary_search_tolerance_k,
                )
            return modules.simulate_scheil_solidification(  # type: ignore[operator]
                **kwargs,
                stop=request.stop_liquid_fraction,
            )
        except Exception as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_NATIVE_SOLVER_FAILED"
            ) from error

    def _translate_native_v2(
        self,
        result: object,
        request: object,
        modules: _SolverModules,
        database_identity: _path_v2.DatabaseIdentityV2,
    ) -> _path_v2.SolidificationResultV2:
        try:
            raw_temperatures = result.temperatures
            raw_solid = result.fraction_solid
            raw_liquid = result.fraction_liquid
            raw_cumulative = result.cum_phase_amounts
            raw_x_liquid = result.x_liquid
            raw_phase_compositions = result.phase_compositions
            method = result.method
            converged = result.converged
            liquid_phase_name = result.liquid_phase_name
        except Exception as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
            ) from error
        if (
            type(raw_temperatures) not in (list, tuple)
            or type(raw_solid) not in (list, tuple)
            or type(raw_liquid) not in (list, tuple)
            or type(raw_cumulative) is not dict
            or type(raw_x_liquid) is not dict
            or type(raw_phase_compositions) is not dict
            or type(method) is not str
            or type(converged) is not bool
            or converged is not True
            or type(liquid_phase_name) is not str
            or liquid_phase_name != request.liquid_phase
        ):
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        expected_method = (
            "equilibrium"
            if type(request) is _path.EquilibriumSolidificationRequest
            else "scheil"
        )
        if method != expected_method:
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        count = len(raw_temperatures)
        if (
            count < 1
            or count > _NATIVE_V2_PUBLIC_ROW_LIMIT
            or len(raw_solid) != count
            or len(raw_liquid) != count
        ):
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        if any(type(key) is not str for key in raw_cumulative):
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        if any(type(key) is not str for key in raw_phase_compositions):
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        if (
            set(raw_phase_compositions)
            != set(raw_cumulative) | {request.liquid_phase}
            or raw_x_liquid is not raw_phase_compositions.get(request.liquid_phase)
        ):
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        cumulative: dict[str, tuple[object, ...]] = {}
        for phase, values in raw_cumulative.items():
            if type(values) not in (list, tuple) or len(values) != count:
                _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
            cumulative[phase] = tuple(values)
        pure_components = tuple(
            component for component in request.components if component != "VA"
        )
        if set(raw_x_liquid) != set(pure_components):
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        liquid: dict[str, tuple[object, ...]] = {}
        for component in pure_components:
            values = raw_x_liquid[component]
            if type(values) not in (list, tuple) or len(values) != count:
                _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
            liquid[component] = tuple(values)

        temperatures = tuple(_native_number(value) for value in raw_temperatures)
        solid_rows = tuple(_native_fraction(value) for value in raw_solid)
        liquid_rows = tuple(_native_fraction(value) for value in raw_liquid)
        minimum_temperature = _finite(
            self._bounds["temperature_k"]["minimum"],
            "W2B_SOLID_BACKEND_BOUNDS_INVALID",
        )
        if any(
            temperature < minimum_temperature
            or temperature > request.start_temperature_k
            for temperature in temperatures
        ):
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        try:
            bulk = tuple(
                _path_v2.CompositionEntryV2(
                    component=component,
                    fraction=_native_fraction(dict(request.composition)[component]),
                )
                for component in pure_components
            )
        except _path_v2.PathContractV2Error as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
            ) from error
        allowed_solid_phases = frozenset(request.phases) - {
            request.liquid_phase
        }

        def observation(index: int) -> _NativeObservationV2:
            phases = _native_phase_fractions(
                cumulative,
                index,
                solid_rows[index],
                allowed_solid_phases,
            )
            composition = (
                _native_composition(liquid, index, pure_components)
                if liquid_rows[index].canonical_value > 0.0
                else tuple()
            )
            return _NativeObservationV2(
                temperature_k=temperatures[index],
                solid_fraction=solid_rows[index],
                liquid_fraction=liquid_rows[index],
                phase_fractions=phases,
                liquid_composition=composition,
            )

        if not _same_binary64(temperatures[0], request.start_temperature_k):
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        if expected_method == "scheil":
            synthetic_phases = _native_phase_fractions(
                cumulative,
                0,
                solid_rows[0],
                allowed_solid_phases,
            )
            if (
                solid_rows[0].canonical_value != 0.0
                or liquid_rows[0].canonical_value != 1.0
                or synthetic_phases
            ):
                _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
            for component in pure_components:
                _explicit_nan(
                    liquid[component][0],
                    "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE",
                )
        try:
            initial_point = _path_v2.SolidificationPathPoint(
                ordinal=0,
                provenance="SYNTHETIC_INITIAL_STATE",
                source_attempt_id=None,
                source_row_index=None,
                temperature_k=request.start_temperature_k,
                solid_fraction=_native_fraction(0.0),
                liquid_fraction=_native_fraction(1.0),
                phase_fractions=tuple(),
                liquid_composition=bulk,
            )
        except _path_v2.PathContractV2Error as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
            ) from error

        closure_index: int | None = None
        stop_fraction: _path_v2.Binary64FractionV2 | None = None
        if expected_method == "scheil":
            stop_fraction = _native_fraction(request.stop_liquid_fraction)
            if count >= 2 and (
                solid_rows[-1].canonical_value == 1.0
                and liquid_rows[-1].canonical_value == 0.0
                and liquid_rows[-2].canonical_value > 0.0
                and _same_binary64(temperatures[-1], temperatures[-2])
            ):
                if not (
                    liquid_rows[-2].canonical_value
                    < stop_fraction.canonical_value
                ):
                    _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
                closure_index = count - 1

        points: list[_path_v2.SolidificationPathPoint] = [initial_point]
        off_path: list[_path_v2.SolidificationOffPathObservationV2] = []
        same_start_reason = _path_v2.StructuredDiagnosticReasonV2(
            code="SOLID_PUBLIC_SAME_START_T_OFF_PATH",
            category="SOLIDIFICATION_PUBLIC_PATH",
            severity="INFO",
        )

        def append_public_row(index: int) -> None:
            observed = observation(index)
            previous = points[-1]
            if _same_binary64(
                observed.temperature_k,
                request.start_temperature_k,
            ):
                try:
                    off_path.append(
                        _path_v2.SolidificationOffPathObservationV2(
                            ordinal=len(off_path),
                            source_row_index=index,
                            source_outcome="SUCCESSFUL_PUBLIC_ROW",
                            temperature_k=observed.temperature_k,
                            solid_fraction=observed.solid_fraction,
                            liquid_fraction=observed.liquid_fraction,
                            phase_fractions=observed.phase_fractions,
                            liquid_composition=observed.liquid_composition,
                            disposition=(
                                "EXCLUDED_SAME_START_T_FROM_MONOTONIC_PATH"
                            ),
                            diagnostic_reason=same_start_reason,
                        )
                    )
                except _path_v2.PathContractV2Error as error:
                    raise Wave2BSolidificationBackendError(
                        "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
                    ) from error
                return
            if observed.temperature_k >= previous.temperature_k:
                _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
            try:
                points.append(
                    _path_v2.SolidificationPathPoint(
                        ordinal=len(points),
                        provenance="BACKEND_PUBLIC_PATH_ROW",
                        source_attempt_id=None,
                        source_row_index=index,
                        temperature_k=observed.temperature_k,
                        solid_fraction=observed.solid_fraction,
                        liquid_fraction=observed.liquid_fraction,
                        phase_fractions=observed.phase_fractions,
                        liquid_composition=observed.liquid_composition,
                    )
                )
            except _path_v2.PathContractV2Error as error:
                raise Wave2BSolidificationBackendError(
                    "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
                ) from error

        first_public_index = 0 if expected_method == "equilibrium" else 1
        end_index = count if closure_index is None else closure_index
        for index in range(first_public_index, end_index):
            append_public_row(index)

        service_closure: _path_v2.SolidificationServiceClosure | None = None
        closure_evidence: (
            _path_v2.SolidificationServiceClosureEvidenceV2 | None
        ) = None
        if closure_index is not None:
            closure_phases = _native_phase_fractions(
                cumulative,
                closure_index,
                solid_rows[closure_index],
                allowed_solid_phases,
            )
            try:
                service_closure = _path_v2.SolidificationServiceClosure(
                    closure_source="SCHEIL_SERVICE_CLOSURE",
                    temperature_k=temperatures[closure_index],
                    solid_fraction=solid_rows[closure_index],
                    liquid_fraction=liquid_rows[closure_index],
                    phase_fractions=closure_phases,
                    liquid_composition=tuple(),
                    reason_code="SERVICE_CLOSURE_ONLY_NOT_PHYSICAL_ATTEMPT",
                )
            except _path_v2.PathContractV2Error:
                try:
                    closure_reason = _path_v2.StructuredDiagnosticReasonV2(
                        code="SOLID_SERVICE_CLOSURE_ACCOUNTING_INCOMPLETE",
                        category="SOLIDIFICATION_ACCOUNTING",
                        severity="WARNING",
                    )
                    closure_evidence = (
                        _path_v2.SolidificationServiceClosureEvidenceV2(
                            closure_source="SCHEIL_SERVICE_CLOSURE",
                            source_row_index=closure_index,
                            temperature_k=temperatures[closure_index],
                            reported_solid_fraction=solid_rows[closure_index],
                            reported_liquid_fraction=liquid_rows[closure_index],
                            reported_phase_fractions=closure_phases,
                            reported_liquid_composition=_native_composition(
                                liquid,
                                closure_index,
                                pure_components,
                            ),
                            accounting_complete=False,
                            accounting_status=(
                                "INCOMPLETE_REPORTED_PHASE_ACCOUNTING"
                            ),
                            diagnostic_reason=closure_reason,
                        )
                    )
                except (
                    Wave2BSolidificationBackendError,
                    _path_v2.PathContractV2Error,
                ) as error:
                    if isinstance(error, Wave2BSolidificationBackendError):
                        raise
                    raise Wave2BSolidificationBackendError(
                        "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
                    ) from error

        try:
            diagnostics = _path_v2.SolidificationDiagnosticsV2(
                instrumentation_id=_NATIVE_V2_INSTRUMENTATION_ID,
                instrumentation_version=_NATIVE_V2_INSTRUMENTATION_VERSION,
                instrumentation_level="PARTIAL_BACKEND_OBSERVABILITY",
                backend_name="scheil",
                backend_version=modules.scheil_version,
                completeness="PARTIAL",
                full_attempt_ledger=False,
                failed_attempts_retained=False,
                merged_attempts_retained=False,
                abandoned_attempts_retained=False,
                adaptive_backtracks_retained=False,
                binary_search_attempts_retained=False,
                service_closure_separated=True,
                public_off_path_observations_retained=bool(off_path),
                incomplete_closure_evidence_retained=(
                    closure_evidence is not None
                ),
                unresolved_branch_count=1,
                attempt_budget=0,
                attempts_consumed=0,
                budget_exhausted=False,
            )
            ledger = _path_v2.RawSolidificationLedgerV2(
                database=database_identity,
                execution_binding=self._execution_binding_v2(),
                phase_domain=_phase_domain_v2(request),
                feature=request.feature,
                method=request.method,
                components=tuple(request.components),
                bulk_composition=bulk,
                liquid_phase=request.liquid_phase,
                pressure_pa=SOLIDIFICATION_PRESSURE_PA,
                start_temperature_k=request.start_temperature_k,
                minimum_temperature_k=minimum_temperature,
                stop_liquid_fraction=stop_fraction,
                attempts=tuple(),
                path_points=tuple(points),
                off_path_observations=tuple(off_path),
                service_closure=service_closure,
                service_closure_evidence=closure_evidence,
                diagnostics=diagnostics,
                terminal_reason=NATIVE_V2_RESULT_STATUS,
            )
            return _path_v2.SolidificationResultV2(ledger=ledger)
        except Wave2BSolidificationBackendError:
            raise
        except _path_v2.PathContractV2Error as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
            ) from error

    @staticmethod
    def _result_arrays(envelope: _DiagnosticSolverResult, request: object):
        result = envelope.result
        try:
            temperatures = tuple(result.temperatures)
            fraction_solid = tuple(result.fraction_solid)
            fraction_liquid = tuple(result.fraction_liquid)
            cumulative = dict(result.cum_phase_amounts)
            liquid = dict(result.x_liquid)
            converged = result.converged
            method = result.method
        except Exception as error:
            raise Wave2BSolidificationBackendError(
                "W2B_SOLID_BACKEND_RESULT_INVALID"
            ) from error
        count = len(temperatures)
        expected_method = (
            "equilibrium"
            if type(request) is _path.EquilibriumSolidificationRequest
            else "scheil"
        )
        pure_components = tuple(
            component for component in request.components if component != "VA"
        )
        solid_phases = tuple(
            phase for phase in request.phases if phase != request.liquid_phase
        )
        if (
            count == 0
            or len(fraction_solid) != count
            or len(fraction_liquid) != count
            or converged is not True
            or type(method) is not str
            or method != expected_method
            or set(cumulative) != set(solid_phases)
            or set(liquid) != set(pure_components)
            or any(
                type(phase) is not str
                or type(values) not in (list, tuple)
                or len(values) != count
                for phase, values in cumulative.items()
            )
            or any(
                type(component) is not str
                or type(values) not in (list, tuple)
                or len(values) != count
                for component, values in liquid.items()
            )
        ):
            _fail("W2B_SOLID_BACKEND_RESULT_INVALID")
        synthetic_indices = tuple(
            item.result_index for item in envelope.synthetic_rows
        )
        if type(request) is _path.EquilibriumSolidificationRequest:
            if synthetic_indices:
                _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")
        elif synthetic_indices not in (tuple(), (0,)):
            _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")
        if synthetic_indices == (0,):
            initial_temperature = _finite(
                temperatures[0],
                "W2B_SOLID_BACKEND_RESULT_INVALID",
            )
            initial_solid = _finite(
                fraction_solid[0],
                "W2B_SOLID_BACKEND_RESULT_INVALID",
            )
            initial_liquid = _finite(
                fraction_liquid[0],
                "W2B_SOLID_BACKEND_RESULT_INVALID",
            )
            if (
                not _same_binary64(
                    initial_temperature,
                    request.start_temperature_k,
                )
                or initial_solid != 0.0
                or initial_liquid != 1.0
                or any(
                    _finite(
                        values[0],
                        "W2B_SOLID_BACKEND_RESULT_INVALID",
                    )
                    != 0.0
                    for values in cumulative.values()
                )
            ):
                _fail("W2B_SOLID_BACKEND_RESULT_INVALID")
        pass_indices = tuple(
            item.result_index
            for item in envelope.attempts
            if item.outcome == "ACCEPTED"
        )
        accounted = pass_indices + synthetic_indices
        if (
            len(set(accounted)) != len(accounted)
            or set(accounted) != set(range(count))
            or any(
                item < 0 or item >= count
                for item in accounted
            )
        ):
            _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")

        synthetic_set = set(synthetic_indices)
        accepted_indices = tuple(
            index for index in range(count) if index not in synthetic_set
        )
        accepted_by_index = {
            item.result_index: item
            for item in envelope.attempts
            if item.outcome == "ACCEPTED"
        }
        numeric_temperatures: list[float] = []
        numeric_solid: list[float] = []
        numeric_liquid: list[float] = []
        numeric_cumulative: dict[str, list[float]] = {
            phase: [] for phase in solid_phases
        }
        numeric_x_liquid: dict[str, list[float]] = {
            component: [] for component in pure_components
        }
        for index in range(count):
            temperature = _finite(
                temperatures[index],
                "W2B_SOLID_BACKEND_RESULT_INVALID",
            )
            solid = _finite(
                fraction_solid[index],
                "W2B_SOLID_BACKEND_RESULT_INVALID",
            )
            liquid_fraction = _finite(
                fraction_liquid[index],
                "W2B_SOLID_BACKEND_RESULT_INVALID",
            )
            if (
                temperature <= 0.0
                or solid < -_BOUND_TOLERANCE
                or solid > 1.0 + _BOUND_TOLERANCE
                or liquid_fraction < -_BOUND_TOLERANCE
                or liquid_fraction > 1.0 + _BOUND_TOLERANCE
                or abs((solid + liquid_fraction) - 1.0) > _BALANCE_TOLERANCE
            ):
                _fail("W2B_SOLID_BACKEND_RESULT_INVALID")
            phase_total = 0.0
            for phase in solid_phases:
                phase_fraction = _finite(
                    cumulative[phase][index],
                    "W2B_SOLID_BACKEND_RESULT_INVALID",
                )
                if (
                    phase_fraction < -_BOUND_TOLERANCE
                    or phase_fraction > 1.0 + _BOUND_TOLERANCE
                ):
                    _fail("W2B_SOLID_BACKEND_RESULT_INVALID")
                phase_total += phase_fraction
                numeric_cumulative[phase].append(phase_fraction)
            if abs(phase_total - solid) > _BALANCE_TOLERANCE:
                _fail("W2B_SOLID_BACKEND_RESULT_INVALID")
            composition_total = 0.0
            for component in pure_components:
                raw_amount = liquid[component][index]
                if index in synthetic_set:
                    numeric_x_liquid[component].append(
                        _explicit_nan(
                            raw_amount,
                            "W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS",
                        )
                    )
                    continue
                amount = _finite(
                    raw_amount,
                    "W2B_SOLID_BACKEND_RESULT_INVALID",
                )
                if (
                    amount < -_BOUND_TOLERANCE
                    or amount > 1.0 + _BOUND_TOLERANCE
                ):
                    _fail("W2B_SOLID_BACKEND_RESULT_INVALID")
                composition_total += amount
                numeric_x_liquid[component].append(amount)
            if (
                index not in synthetic_set
                and liquid_fraction > _BALANCE_TOLERANCE
                and abs(composition_total - 1.0) > _BALANCE_TOLERANCE
            ):
                _fail("W2B_SOLID_BACKEND_RESULT_INVALID")
            numeric_temperatures.append(temperature)
            numeric_solid.append(solid)
            numeric_liquid.append(liquid_fraction)

        if not accepted_indices:
            _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")
        for index in accepted_indices:
            attempt = accepted_by_index.get(index)
            if attempt is None or not _same_binary64(
                attempt.temperature_k,
                numeric_temperatures[index],
            ):
                _fail("W2B_SOLID_BACKEND_INCOMPLETE_DIAGNOSTICS")
        for previous, current in zip(accepted_indices, accepted_indices[1:]):
            if (
                numeric_temperatures[current] >= numeric_temperatures[previous]
                or numeric_solid[current]
                < numeric_solid[previous] - _BALANCE_TOLERANCE
            ):
                _fail("W2B_SOLID_BACKEND_RESULT_INVALID")

        initial_index = accepted_indices[0]
        bulk = dict(request.composition)
        if (
            not _same_binary64(
                numeric_temperatures[initial_index],
                request.start_temperature_k,
            )
            or abs(numeric_solid[initial_index]) > _BOUND_TOLERANCE
            or abs(numeric_liquid[initial_index] - 1.0) > _BOUND_TOLERANCE
            or any(
                abs(numeric_cumulative[phase][initial_index]) > _BOUND_TOLERANCE
                for phase in solid_phases
            )
            or any(
                not _same_binary64(
                    numeric_x_liquid[component][initial_index],
                    bulk[component],
                )
                for component in pure_components
            )
        ):
            _fail("W2B_SOLID_BACKEND_RESULT_INVALID")
        final_index = accepted_indices[-1]
        expected_termination = (
            "W2B_EQ_NO_LIQUID_REACHED"
            if expected_method == "equilibrium"
            else "W2B_SCHEIL_LIQUID_THRESHOLD_REACHED"
        )
        if (
            envelope.termination_reason_code != expected_termination
            or (
                expected_method == "equilibrium"
                and numeric_liquid[final_index] > _BALANCE_TOLERANCE
            )
            or (
                expected_method == "scheil"
                and numeric_liquid[final_index]
                > request.stop_liquid_fraction + _BALANCE_TOLERANCE
            )
        ):
            _fail("W2B_SOLID_BACKEND_RESULT_INVALID")
        return (
            tuple(numeric_temperatures),
            tuple(numeric_solid),
            tuple(numeric_liquid),
            {phase: tuple(values) for phase, values in numeric_cumulative.items()},
            {
                component: tuple(values)
                for component, values in numeric_x_liquid.items()
            },
            converged,
        )

    def simulate(self, request: object) -> _path.RawSolidificationLedger:
        """Run one exact method request through the active receipt window."""

        self._guard()
        caller = _copy_request(request)
        caller_card = _request_card(caller)
        checked = self._bind_request(caller)
        self._attempted_calls += 1
        try:
            modules = self._modules()
            database = self._database()
            envelope = self._invoke_diagnostic_solver(modules, database, checked)
            self._result_arrays(envelope, checked)
            _fail("W2B_SOLID_BACKEND_DTO_V2_REQUIRED")
        except Exception:
            self._failed_calls += 1
            raise
        finally:
            try:
                if _request_card(request) != caller_card:
                    _fail("W2B_SOLID_BACKEND_REQUEST_INVALID")
                self._guard()
            except Exception:
                if self._failed_calls == 0:
                    self._failed_calls += 1
                raise

    def simulate_v2(self, request: object) -> _path_v2.SolidificationResultV2:
        """Return an honest native partial result in frozen Path Contract V2.

        Only public scheil result rows are retained as public-row evidence.
        They are never relabeled as solver attempts.  Hidden equilibrium
        binary-search attempts, adaptive backtracks, and failed internal
        solves remain explicitly unresolved, so this entrypoint can never
        emit ``COMPLETE``.
        """

        _guard_path_contract_v2()
        self._guard()
        caller = _copy_request(request)
        caller_card = _request_card(caller)
        checked, database_identity = self._bind_request_v2(caller)
        self._attempted_calls += 1
        try:
            modules = self._modules()
            if modules.provenance != _NATIVE_PROVENANCE:
                _fail("W2B_SOLID_BACKEND_NATIVE_RUNTIME_REQUIRED")
            database = self._database()
            raw_result = self._invoke_native_solver(
                modules,
                database,
                checked,
            )
            self._guard()
            result = self._translate_native_v2(
                raw_result,
                checked,
                modules,
                database_identity,
            )
            self._guard()
            _guard_path_contract_v2()
            self._completed_calls += 1
            return result
        except Exception:
            self._failed_calls += 1
            raise
        finally:
            try:
                if _request_card(request) != caller_card:
                    _fail("W2B_SOLID_BACKEND_REQUEST_INVALID")
                self._guard()
                _guard_path_contract_v2()
            except Exception:
                if self._failed_calls == 0:
                    self._failed_calls += 1
                raise

    def receipt_payloads(
        self,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        """Return path-free, nonclaiming payloads for ``build_result_receipt``."""

        self._guard_receipt_identity()
        modules = self._solver_modules
        if self._manufactured_test_only:
            _fail("W2B_SOLID_BACKEND_MANUFACTURED_RECEIPT_DENIED")
        backend = {
            "schema_version": BACKEND_SCHEMA,
            "backend_id": BACKEND_ID,
            "pycalphad_version": (
                modules.pycalphad_version
                if type(modules) is _SolverModules
                else "NOT_LOADED"
            ),
            "scheil_version": (
                modules.scheil_version
                if type(modules) is _SolverModules
                else "NOT_LOADED"
            ),
            "diagnostic_kind": (
                modules.diagnostic_kind
                if type(modules) is _SolverModules
                else "NOT_LOADED"
            ),
            "solver_provenance": (
                modules.provenance
                if type(modules) is _SolverModules
                else "NOT_LOADED"
            ),
            "required_contract_schema": REQUIRED_SOLIDIFICATION_CONTRACT_SCHEMA,
            "required_contract_version": REQUIRED_SOLIDIFICATION_CONTRACT_VERSION,
            "required_contract_sha256": PATH_CONTRACT_V2_SHA256,
            "path_contract_v2_sha256": PATH_CONTRACT_V2_SHA256,
            "contract_v2_required": True,
            "legacy_complete_output_enabled": False,
            "native_v2_partial_observations_supported": True,
            "native_v2_complete_diagnostics_supported": False,
            "native_v2_hidden_attempts_available": False,
            "native_v2_result_status": NATIVE_V2_RESULT_STATUS,
            "native_v2_diagnostic_reason": NATIVE_V2_DIAGNOSTIC_REASON,
            "v2_partial_terminal_reason": NATIVE_V2_RESULT_STATUS,
            "v2_partial_reason_code": NATIVE_V2_DIAGNOSTIC_REASON,
            "legacy_identity_contract": (
                "DTO_V2_REQUIRED_EXACT_RECEIPT_ROLE_UNREPRESENTABLE"
                if self._family in IDENTITY_V2_REQUIRED_FAMILIES
                else "EXACT_RECEIPT_ROLE_BOUND"
            ),
            "identity_contract": (
                "DTO_V2_REQUIRED_EXACT_RECEIPT_ROLE_UNREPRESENTABLE"
                if self._family in IDENTITY_V2_REQUIRED_FAMILIES
                else "EXACT_RECEIPT_ROLE_BOUND"
            ),
            "v2_identity_contract": "EXACT_RECEIPT_ROLE_BOUND",
            "bound_operations": list(BOUND_OPERATIONS),
            "native_complete_operations": list(NATIVE_COMPLETE_OPERATIONS),
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
        }
        context = {
            "feature_id": self._feature_id,
            "execution_mode": _receipts.INTERNAL_QUALIFICATION,
            "authorization_state": "INTERNAL_QUALIFICATION_ONLY_NOT_RELEASE",
            "execution_lease_id": self._lease_id,
            "pre_snapshot_digest": self._pre.canonical_digest,
            "attempted_calls": self._attempted_calls,
            "completed_calls": self._completed_calls,
            "failed_calls": self._failed_calls,
            "steel_required_product_scope": True,
            "fe_baseline_profile": None,
            "fe_exclusion_decision_made": False,
            "acceptance_claim": False,
            "counts_toward_feature_coverage": False,
            "production_use": "DENIED",
        }
        return backend, runtime, context


@_dataclass(frozen=True, slots=True)
class _PublicV2ResultBinding:
    database: _path_v2.DatabaseIdentityV2
    execution_binding: _path_v2.ExecutionBindingV2
    phase_domain: _path_v2.PhaseDomainV2
    feature: str
    method: str
    components: tuple[str, ...]
    bulk_composition: tuple[_path_v2.CompositionEntryV2, ...]
    liquid_phase: str
    pressure_pa: float
    start_temperature_k: float
    minimum_temperature_k: float
    stop_liquid_fraction: _path_v2.Binary64FractionV2 | None


def _public_v2_result_binding(
    backend: object,
    request: object,
) -> _PublicV2ResultBinding:
    """Capture only receipt-derived values that a returned ledger must echo."""

    if type(backend) is not ReceiptBoundSolidificationBackend:
        _fail("W2B_SOLID_BACKEND_PROTOCOL_INVALID")
    _guard_path_contract_v2()
    backend._guard()
    checked, database = backend._bind_request_v2(request)
    try:
        pure_components = tuple(
            component for component in checked.components if component != "VA"
        )
        amounts = dict(checked.composition)
        bulk = tuple(
            _path_v2.CompositionEntryV2(
                component=component,
                fraction=_native_fraction(amounts[component]),
            )
            for component in pure_components
        )
        phase_domain = _path_v2.PhaseDomainV2(
            candidate_phases=backend._candidate_phases,
            requested_phases=backend._requested_phases,
            excluded_phases=backend._excluded_phases,
            effective_phases=backend._effective_phases,
        )
        stop = (
            None
            if type(checked) is _path.EquilibriumSolidificationRequest
            else _native_fraction(checked.stop_liquid_fraction)
        )
        return _PublicV2ResultBinding(
            database=database,
            execution_binding=backend._execution_binding_v2(),
            phase_domain=phase_domain,
            feature=checked.feature,
            method=checked.method,
            components=tuple(checked.components),
            bulk_composition=bulk,
            liquid_phase=checked.liquid_phase,
            pressure_pa=checked.pressure_pa,
            start_temperature_k=checked.start_temperature_k,
            minimum_temperature_k=_finite(
                backend._bounds["temperature_k"]["minimum"],
                "W2B_SOLID_BACKEND_BOUNDS_INVALID",
            ),
            stop_liquid_fraction=stop,
        )
    except Wave2BSolidificationBackendError:
        raise
    except _path_v2.PathContractV2Error as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
        ) from error
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_CONTEXT_INVALID"
        ) from error


def _reconstruct_public_v2_result(
    returned: object,
) -> _path_v2.SolidificationResultV2:
    try:
        if type(returned) is not _path_v2.SolidificationResultV2:
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        ledger = returned.ledger
        return _path_v2.SolidificationResultV2(ledger=ledger)
    except Wave2BSolidificationBackendError:
        raise
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
        ) from error


def _assert_public_v2_result_binding(
    result: object,
    expected: _PublicV2ResultBinding,
    backend: object,
) -> None:
    """Reject any valid-looking V2 ledger not owned by this receipt/request."""

    try:
        if (
            type(backend) is not ReceiptBoundSolidificationBackend
            or type(result) is not _path_v2.SolidificationResultV2
        ):
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        backend._guard()
        _guard_path_contract_v2()
        modules = backend._solver_modules
        if (
            type(modules) is not _SolverModules
            or modules.provenance != _NATIVE_PROVENANCE
            or modules.diagnostic_kind != _NATIVE_DIAGNOSTIC_KIND
            or modules.pycalphad_version != "0.11.2"
            or modules.scheil_version != "0.3.0"
        ):
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        ledger = result.ledger
        if (
            type(ledger) is not _path_v2.RawSolidificationLedgerV2
            or ledger.database != expected.database
            or ledger.execution_binding != expected.execution_binding
            or ledger.phase_domain != expected.phase_domain
            or ledger.feature != expected.feature
            or ledger.method != expected.method
            or ledger.components != expected.components
            or ledger.bulk_composition != expected.bulk_composition
            or ledger.liquid_phase != expected.liquid_phase
            or not _same_binary64(ledger.pressure_pa, expected.pressure_pa)
            or not _same_binary64(
                ledger.start_temperature_k,
                expected.start_temperature_k,
            )
            or not _same_binary64(
                ledger.minimum_temperature_k,
                expected.minimum_temperature_k,
            )
            or ledger.stop_liquid_fraction != expected.stop_liquid_fraction
            or ledger.attempts != tuple()
            or ledger.terminal_reason != NATIVE_V2_RESULT_STATUS
        ):
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
        diagnostics = ledger.diagnostics
        if (
            diagnostics.instrumentation_id != _NATIVE_V2_INSTRUMENTATION_ID
            or diagnostics.instrumentation_version
            != _NATIVE_V2_INSTRUMENTATION_VERSION
            or diagnostics.instrumentation_level
            != "PARTIAL_BACKEND_OBSERVABILITY"
            or diagnostics.backend_name != "scheil"
            or diagnostics.backend_version != modules.scheil_version
            or diagnostics.completeness != "PARTIAL"
            or diagnostics.full_attempt_ledger
            or diagnostics.failed_attempts_retained
            or diagnostics.merged_attempts_retained
            or diagnostics.abandoned_attempts_retained
            or diagnostics.adaptive_backtracks_retained
            or diagnostics.binary_search_attempts_retained
            or not diagnostics.service_closure_separated
            or diagnostics.unresolved_branch_count < 1
            or diagnostics.attempt_budget != 0
            or diagnostics.attempts_consumed != 0
            or diagnostics.budget_exhausted
        ):
            _fail("W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE")
    except Wave2BSolidificationBackendError:
        raise
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_NATIVE_OUTPUT_UNREPRESENTABLE"
        ) from error


def _run_solidification_v2(
    request: object,
    backend: object,
) -> _path_v2.SolidificationResultV2:
    pristine = _copy_request(request)
    pristine_card = _request_card(pristine)
    anchors = _capture_request_anchors(request)
    outbound = _copy_request(pristine)
    try:
        if type(backend) is not ReceiptBoundSolidificationBackend:
            _fail("W2B_SOLID_BACKEND_PROTOCOL_INVALID")
        expected = _public_v2_result_binding(backend, pristine)
        simulate_v2 = getattr(backend, "simulate_v2")
        if (
            type(simulate_v2) is not _MethodType
            or simulate_v2.__self__ is not backend
            or not callable(simulate_v2)
        ):
            _fail("W2B_SOLID_BACKEND_PROTOCOL_INVALID")
        returned = simulate_v2(outbound)
    except Wave2BSolidificationBackendError:
        raise
    except Exception as error:
        raise Wave2BSolidificationBackendError(
            "W2B_SOLID_BACKEND_PROTOCOL_RAISED"
        ) from error
    finally:
        _assert_public_requests_pristine(
            request,
            outbound,
            pristine,
            pristine_card,
            anchors,
        )
    rebuilt = _reconstruct_public_v2_result(returned)
    _assert_public_v2_result_binding(rebuilt, expected, backend)
    return rebuilt


def run_equilibrium_solidification_v2(
    request: object,
    backend: object,
) -> _path_v2.SolidificationResultV2:
    """Run one receipt-bound equilibrium request through the V2 protocol."""

    if type(request) is not _path.EquilibriumSolidificationRequest:
        _fail("W2B_SOLID_BACKEND_REQUEST_INVALID")
    return _run_solidification_v2(request, backend)


def run_scheil_solidification_v2(
    request: object,
    backend: object,
) -> _path_v2.SolidificationResultV2:
    """Run one receipt-bound Scheil request through the V2 protocol."""

    if type(request) is not _path.ScheilSolidificationRequest:
        _fail("W2B_SOLID_BACKEND_REQUEST_INVALID")
    return _run_solidification_v2(request, backend)


__all__ = (
    "BACKEND_SCHEMA",
    "BACKEND_ID",
    "SUPPORTED_DATABASE_FAMILIES",
    "SUPPORTED_FE_PROFILE_IDS",
    "IDENTITY_V2_REQUIRED_FAMILIES",
    "BOUND_OPERATIONS",
    "NATIVE_COMPLETE_OPERATIONS",
    "REQUIRED_SOLIDIFICATION_CONTRACT_SCHEMA",
    "REQUIRED_SOLIDIFICATION_CONTRACT_VERSION",
    "PATH_CONTRACT_V2_SHA256",
    "CONTRACT_V2_REQUIRED",
    "LEGACY_COMPLETE_OUTPUT_ENABLED",
    "NATIVE_V2_RESULT_STATUS",
    "NATIVE_V2_DIAGNOSTIC_REASON",
    "SOLIDIFICATION_PRESSURE_PA",
    "STEEL_REQUIRED_PRODUCT_SCOPE",
    "FE_BASELINE_PROFILE",
    "FE_EXCLUSION_DECISION_MADE",
    "COUNTS_TOWARD_FEATURE_COVERAGE",
    "ACCEPTANCE_CLAIM",
    "PRODUCTION_USE",
    "WAVE2B_SOLID_BACKEND_REASON_CODES",
    "Wave2BSolidificationBackendError",
    "solidification_full_request",
    "solidification_full_request_payload_v2",
    "solidification_solver_options",
    "solidification_bounds",
    "ReceiptBoundSolidificationBackend",
    "run_equilibrium_solidification_v2",
    "run_scheil_solidification_v2",
)
