"""Receipt-bound real solver backend for the Wave 2B direct adapters.

This module deliberately has no Streamlit dependency and imports pycalphad
only when a bound operation is actually executed.  A backend can be created
only after a matching PRE snapshot has been issued for an active
``ExecutionLease``.  The database path used by pycalphad is obtained solely
from ``ExecutionLease.file_path("runtime")``; project database paths are
never accepted by this API.

The implementation is an internal-qualification integration candidate.  It
does not count toward feature coverage, does not make an acceptance claim,
and is denied for production/release use.  Both exact Fe profiles remain
separate identities.  No Fe baseline is selected and C15_LAVES cannot be
omitted or excluded while that product decision is undecided.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
import importlib as _importlib
import math as _math
from pathlib import Path as _Path
import struct as _struct
from types import MappingProxyType as _MappingProxyType
from typing import Mapping as _Mapping

import thermogar_wave2b_direct as _direct
import thermogar_wave2b_receipts as _receipts
from thermogar_equilibrium_core import (
    EquilibriumRawResult as _EquilibriumRawResult,
    EquilibriumRequest as _EquilibriumRequest,
    RawPhaseState as _RawPhaseState,
)
from thermogar_numerical_grid import GridNode as _GridNode


BACKEND_SCHEMA = "THERMOGAR-WAVE2B-RECEIPT-BOUND-BACKEND-1"
BACKEND_ID = "thermogar_wave2b_pycalphad_0_11_2_candidate"
SUPPORTED_DATABASE_FAMILIES = ("ni", "al", "fe")
SUPPORTED_FE_PROFILE_IDS = ("thermogar_patch", "upstream_original")
IMPLEMENTED_DIRECT_OPERATIONS = (
    "solve_equilibrium",
    "phase_gibbs_energy",
    "phase_driving_force",
    "tzero_temperature",
)
UNSUPPORTED_PATH_OPERATIONS = ("map", "simulate")
STEEL_REQUIRED_PRODUCT_SCOPE = True
FE_BASELINE_PROFILE = None
FE_EXCLUSION_DECISION_MADE = False
COUNTS_TOWARD_FEATURE_COVERAGE = False
ACCEPTANCE_CLAIM = False
PRODUCTION_USE = "DENIED"

_REASONS = {
    "W2B_BACKEND_CONTEXT_INVALID": "Backend context must contain one exact domain, PRE snapshot, and active lease.",
    "W2B_BACKEND_INTERNAL_QUALIFICATION_REQUIRED": "This backend is restricted to INTERNAL_QUALIFICATION.",
    "W2B_BACKEND_LEASE_INACTIVE": "The bound ExecutionLease is not active in the PRE execution window.",
    "W2B_BACKEND_PRE_MISMATCH": "The PRE snapshot does not match the bound domain, profile, lease, or execution snapshot.",
    "W2B_BACKEND_PROFILE_IDENTITY_MISMATCH": "The direct request uses a different exact database profile identity.",
    "W2B_BACKEND_DOMAIN_MISMATCH": "The direct request is outside the exact receipt-bound feature or phase domain.",
    "W2B_BACKEND_FE_POLICY_REQUIRED": "Fe requires an exact profile and retained C15_LAVES while both policy decisions are undecided.",
    "W2B_BACKEND_REQUEST_INVALID": "The backend node request is not an exact valid direct-adapter DTO.",
    "W2B_BACKEND_BOUNDS_INVALID": "The request state is outside the exact receipt bounds.",
    "W2B_BACKEND_SOLVER_OPTIONS_UNSUPPORTED": "Only a bounded integer pdens solver option is supported by this backend revision.",
    "W2B_BACKEND_PYCALPHAD_UNAVAILABLE": "The pinned pycalphad runtime could not be imported lazily.",
    "W2B_BACKEND_PYCALPHAD_VERSION_MISMATCH": "The real backend requires exact pycalphad 0.11.2 semantics.",
    "W2B_BACKEND_DATABASE_LOAD_FAILED": "pycalphad could not load the runtime database snapshot.",
    "W2B_BACKEND_RUNTIME_PATH_INVALID": "The runtime path is not the exact active lease snapshot path.",
    "W2B_BACKEND_REPLY_INVALID": "The solver result cannot be represented by the exact direct DTO contract.",
    "W2B_BACKEND_NOT_IMPLEMENTED": "This receipt-bound path operation is explicitly not implemented and makes no coverage claim.",
}
WAVE2B_BACKEND_REASON_CODES: _Mapping[str, str] = _MappingProxyType(_REASONS)
del _REASONS


class Wave2BBackendError(ValueError):
    """Fail-closed backend error carrying one stable reason code."""

    __slots__ = ("reason_code",)

    def __init__(self, reason_code: str) -> None:
        if type(reason_code) is not str or reason_code not in WAVE2B_BACKEND_REASON_CODES:
            raise RuntimeError("Unknown Wave 2B backend reason code")
        self.reason_code = reason_code
        super().__init__(reason_code)


def _fail(reason_code: str) -> None:
    raise Wave2BBackendError(reason_code)


def _exact_strings(value: object, *, allow_empty: bool = False) -> tuple[str, ...]:
    if type(value) is not tuple or (not value and not allow_empty):
        _fail("W2B_BACKEND_REQUEST_INVALID")
    copied: list[str] = []
    seen: set[str] = set()
    for item in value:
        if type(item) is not str or not item or item in seen:
            _fail("W2B_BACKEND_REQUEST_INVALID")
        copied.append(item)
        seen.add(item)
    return tuple(copied)


def _copy_identity(value: object) -> _direct.DatabaseProfileIdentity:
    try:
        if type(value) is not _direct.DatabaseProfileIdentity:
            _fail("W2B_BACKEND_REQUEST_INVALID")
        return _direct.DatabaseProfileIdentity(
            value.database_family,
            value.profile_id,
            value.runtime_sha256,
        )
    except Wave2BBackendError:
        raise
    except Exception as error:
        raise Wave2BBackendError("W2B_BACKEND_REQUEST_INVALID") from error


def _copy_key(value: object) -> _direct.DirectNodeKey:
    try:
        if type(value) is not _direct.DirectNodeKey or type(value.node) is not _GridNode:
            _fail("W2B_BACKEND_REQUEST_INVALID")
        node = _GridNode(
            value.node.ordinal,
            tuple((name, number) for name, number in value.node.coordinates),
        )
        return _direct.DirectNodeKey(
            node,
            tuple((name, label) for name, label in value.labels),
        )
    except Wave2BBackendError:
        raise
    except Exception as error:
        raise Wave2BBackendError("W2B_BACKEND_REQUEST_INVALID") from error


def _copy_phase_binding(value: object) -> _direct.PhaseSetBinding:
    try:
        if type(value) is not _direct.PhaseSetBinding:
            _fail("W2B_BACKEND_REQUEST_INVALID")
        return _direct.PhaseSetBinding(
            tuple(value.phase_universe),
            tuple(value.effective_phases),
            tuple(value.explicit_exclusions),
        )
    except Wave2BBackendError:
        raise
    except Exception as error:
        raise Wave2BBackendError("W2B_BACKEND_REQUEST_INVALID") from error


def _copy_state(value: object) -> _EquilibriumRequest:
    try:
        if type(value) is not _EquilibriumRequest:
            _fail("W2B_BACKEND_REQUEST_INVALID")
        return _EquilibriumRequest(
            value.temperature_k,
            value.pressure_pa,
            tuple(value.components),
            tuple(value.phases),
            tuple((name, number) for name, number in value.composition),
        )
    except Wave2BBackendError:
        raise
    except Exception as error:
        raise Wave2BBackendError("W2B_BACKEND_REQUEST_INVALID") from error


def _copy_node(value: object, expected_type: type):
    """Reconstruct every primitive instead of trusting a frozen instance."""

    try:
        if type(value) is not expected_type:
            _fail("W2B_BACKEND_REQUEST_INVALID")
        identity = _copy_identity(value.identity)
        key = _copy_key(value.key)
        binding = _copy_phase_binding(value.phase_binding)
        if expected_type is _direct.EquilibriumBackendNodeRequest:
            return expected_type(
                identity,
                value.feature_id,
                key,
                _copy_state(value.equilibrium),
                binding,
            )
        if expected_type is _direct.PhaseGibbsBackendNodeRequest:
            return expected_type(
                identity,
                value.feature_id,
                key,
                _copy_state(value.state),
                value.phase,
                binding,
            )
        if expected_type is _direct.PhaseDrivingForceBackendNodeRequest:
            return expected_type(
                identity,
                value.feature_id,
                key,
                _copy_state(value.reference_state),
                value.target_phase,
                binding,
            )
        if expected_type is _direct.TZeroBackendNodeRequest:
            return expected_type(
                identity,
                value.feature_id,
                key,
                _copy_state(value.state),
                value.phase_one,
                value.phase_two,
                value.minimum_temperature_k,
                value.maximum_temperature_k,
                binding,
            )
    except Wave2BBackendError:
        raise
    except Exception as error:
        raise Wave2BBackendError("W2B_BACKEND_REQUEST_INVALID") from error
    _fail("W2B_BACKEND_REQUEST_INVALID")


def _decode_canonical_value(value: object, depth: int = 0) -> object:
    """Decode the receipt layer's explicit binary64 JSON representation."""

    if depth > 64:
        _fail("W2B_BACKEND_CONTEXT_INVALID")
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
                _fail("W2B_BACKEND_CONTEXT_INVALID")
            number = _struct.unpack(">d", bytes.fromhex(encoded))[0]
            if not _math.isfinite(number):
                _fail("W2B_BACKEND_CONTEXT_INVALID")
            return number
        return {
            key: _decode_canonical_value(item, depth + 1)
            for key, item in value.items()
        }
    _fail("W2B_BACKEND_CONTEXT_INVALID")


def _payload_dict(value: object) -> dict[str, object]:
    try:
        if type(value) is not _receipts.CanonicalPayload:
            _fail("W2B_BACKEND_CONTEXT_INVALID")
        decoded = _decode_canonical_value(value.value())
    except Wave2BBackendError:
        raise
    except Exception as error:
        raise Wave2BBackendError("W2B_BACKEND_CONTEXT_INVALID") from error
    if type(decoded) is not dict:
        _fail("W2B_BACKEND_CONTEXT_INVALID")
    return decoded


def _same_binary64(left: float, right: float) -> bool:
    return _struct.pack(">d", left) == _struct.pack(">d", right)


@_dataclass(frozen=True, slots=True)
class _SolverModules:
    Database: object
    equilibrium: object
    Workspace: object
    variables: object
    DormantPhase: object
    T0: object
    numpy: object
    version: str


def _load_solver_modules() -> _SolverModules:
    """Import the heavy solver stack only on the first real operation."""

    try:
        pycalphad = _importlib.import_module("pycalphad")
        numpy = _importlib.import_module("numpy")
        dormant_module = _importlib.import_module(
            "pycalphad.property_framework.metaproperties"
        )
        tzero_module = _importlib.import_module("pycalphad.property_framework.tzero")
        version = getattr(pycalphad, "__version__", None)
        if type(version) is not str:
            _fail("W2B_BACKEND_PYCALPHAD_UNAVAILABLE")
        modules = _SolverModules(
            Database=getattr(pycalphad, "Database"),
            equilibrium=getattr(pycalphad, "equilibrium"),
            Workspace=getattr(pycalphad, "Workspace"),
            variables=getattr(pycalphad, "variables"),
            DormantPhase=getattr(dormant_module, "DormantPhase"),
            T0=getattr(tzero_module, "T0"),
            numpy=numpy,
            version=version,
        )
    except Wave2BBackendError:
        raise
    except Exception as error:
        raise Wave2BBackendError("W2B_BACKEND_PYCALPHAD_UNAVAILABLE") from error
    if modules.version != "0.11.2":
        _fail("W2B_BACKEND_PYCALPHAD_VERSION_MISMATCH")
    return modules


class _ReceiptBoundContext:
    """Shared active-lease guard used by real and explicit stub backends."""

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
                _fail("W2B_BACKEND_CONTEXT_INVALID")
            domain_bytes = _receipts.receipt_json_bytes(domain_receipt)
            pre_bytes = _receipts.receipt_json_bytes(pre_snapshot)
            profile = domain_receipt.profile_receipt
            if (
                domain_receipt.execution_mode != _receipts.INTERNAL_QUALIFICATION
                or domain_receipt.authorization_state
                != "INTERNAL_QUALIFICATION_ONLY_NOT_RELEASE"
                or profile.verification_mode != _receipts.INTERNAL_QUALIFICATION
            ):
                _fail("W2B_BACKEND_INTERNAL_QUALIFICATION_REQUIRED")
            lease_id = execution_lease.lease_id
            snapshot_digest = execution_lease.execution_snapshot_digest
            runtime_path = execution_lease.file_path("runtime").resolve(strict=True)
            if (
                pre_snapshot.lease_id != lease_id
                or pre_snapshot.domain_receipt_digest != domain_receipt.canonical_digest
                or pre_snapshot.profile_receipt_digest != profile.canonical_digest
                or pre_snapshot.execution_snapshot_digest != snapshot_digest
            ):
                _fail("W2B_BACKEND_PRE_MISMATCH")
            if profile.family not in SUPPORTED_DATABASE_FAMILIES:
                _fail("W2B_BACKEND_CONTEXT_INVALID")
            if profile.family == "fe":
                if (
                    profile.profile not in SUPPORTED_FE_PROFILE_IDS
                    or profile.baseline_decision != _receipts.FE_POLICY_UNDECIDED
                    or profile.c15_exclusion_decision != _receipts.FE_POLICY_UNDECIDED
                    or "C15_LAVES" not in domain_receipt.candidate_phases
                    or "C15_LAVES" not in domain_receipt.requested_phases
                    or "C15_LAVES" in domain_receipt.excluded_phases
                    or "C15_LAVES" not in domain_receipt.effective_phases
                ):
                    _fail("W2B_BACKEND_FE_POLICY_REQUIRED")
            elif profile.profile in SUPPORTED_FE_PROFILE_IDS:
                _fail("W2B_BACKEND_CONTEXT_INVALID")
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
            self._effective_phases = tuple(domain_receipt.effective_phases)
            self._excluded_phases = tuple(domain_receipt.excluded_phases)
            self._full_request = _payload_dict(domain_receipt.full_request)
            self._bounds = _payload_dict(domain_receipt.bounds)
            self._solver_options = _payload_dict(domain_receipt.solver_options)
            self._validate_solver_options()
        except Wave2BBackendError:
            raise
        except _receipts.ReceiptError as error:
            raise Wave2BBackendError("W2B_BACKEND_LEASE_INACTIVE") from error
        except Exception as error:
            raise Wave2BBackendError("W2B_BACKEND_CONTEXT_INVALID") from error
        self._guard()

    def _validate_solver_options(self) -> None:
        if set(self._solver_options) != {"pdens"}:
            _fail("W2B_BACKEND_SOLVER_OPTIONS_UNSUPPORTED")
        pdens = self._solver_options["pdens"]
        if type(pdens) is not int or isinstance(pdens, bool) or not 1 <= pdens <= 10000:
            _fail("W2B_BACKEND_SOLVER_OPTIONS_UNSUPPORTED")

    @property
    def _calc_opts(self) -> dict[str, int]:
        return {"pdens": self._solver_options["pdens"]}  # type: ignore[dict-item]

    def _guard_receipt_identity(self) -> None:
        """Revalidate receipt primitives even after POST closes file_path()."""

        try:
            current_profile = self._domain.profile_receipt
            current_full_request = _payload_dict(self._domain.full_request)
            current_bounds = _payload_dict(self._domain.bounds)
            current_solver_options = _payload_dict(self._domain.solver_options)
            if (
                type(self._domain) is not _receipts.DomainReceipt
                or type(self._pre) is not _receipts.PreExecutionSnapshot
                or type(self._lease) is not _receipts.ExecutionLease
                or _receipts.receipt_json_bytes(self._domain) != self._domain_bytes
                or _receipts.receipt_json_bytes(self._pre) != self._pre_bytes
                or self._domain.canonical_digest != self._domain_digest
                or self._domain.profile_receipt.canonical_digest != self._profile_digest
                or self._lease.lease_id != self._lease_id
                or self._lease.execution_snapshot_digest != self._snapshot_digest
                or self._pre.lease_id != self._lease_id
                or self._pre.domain_receipt_digest != self._domain_digest
                or self._pre.profile_receipt_digest != self._profile_digest
                or self._pre.execution_snapshot_digest != self._snapshot_digest
                or current_profile.family != self._family
                or current_profile.profile != self._profile
                or current_profile.runtime.sha256 != self._runtime_sha256
                or self._domain.feature_id != self._feature_id
                or tuple(self._domain.candidate_phases) != self._candidate_phases
                or tuple(self._domain.effective_phases) != self._effective_phases
                or tuple(self._domain.excluded_phases) != self._excluded_phases
                or current_full_request != self._full_request
                or current_bounds != self._bounds
                or current_solver_options != self._solver_options
            ):
                _fail("W2B_BACKEND_CONTEXT_INVALID")
        except Wave2BBackendError:
            raise
        except _receipts.ReceiptError as error:
            raise Wave2BBackendError("W2B_BACKEND_LEASE_INACTIVE") from error
        except Exception as error:
            raise Wave2BBackendError("W2B_BACKEND_CONTEXT_INVALID") from error

    def _guard(self) -> _Path:
        """Revalidate receipts and the active PRE snapshot capability."""

        self._guard_receipt_identity()
        try:
            path = self._lease.file_path("runtime").resolve(strict=True)
            if path != self._runtime_path or not path.is_file():
                _fail("W2B_BACKEND_RUNTIME_PATH_INVALID")
            return path
        except Wave2BBackendError:
            raise
        except _receipts.ReceiptError as error:
            raise Wave2BBackendError("W2B_BACKEND_LEASE_INACTIVE") from error
        except Exception as error:
            raise Wave2BBackendError("W2B_BACKEND_CONTEXT_INVALID") from error

    def _bind_identity(self, identity: _direct.DatabaseProfileIdentity) -> None:
        if (
            identity.database_family != self._family
            or identity.profile_id != self._profile
            or identity.runtime_sha256 != self._runtime_sha256
        ):
            _fail("W2B_BACKEND_PROFILE_IDENTITY_MISMATCH")

    def _bind_phase_domain(
        self,
        feature_id: str,
        phase_binding: _direct.PhaseSetBinding,
        *,
        isolated_phase: str | None = None,
    ) -> None:
        if feature_id != self._feature_id:
            _fail("W2B_BACKEND_DOMAIN_MISMATCH")
        universe = tuple(sorted(_exact_strings(phase_binding.phase_universe)))
        effective = tuple(sorted(_exact_strings(phase_binding.effective_phases)))
        excluded = tuple(
            sorted(_exact_strings(phase_binding.explicit_exclusions, allow_empty=True))
        )
        if universe != self._candidate_phases:
            _fail("W2B_BACKEND_DOMAIN_MISMATCH")
        if isolated_phase is None:
            if effective != self._effective_phases or excluded != self._excluded_phases:
                _fail("W2B_BACKEND_DOMAIN_MISMATCH")
        else:
            expected_exclusions = tuple(
                phase for phase in self._candidate_phases if phase != isolated_phase
            )
            if (
                isolated_phase not in self._effective_phases
                or effective != (isolated_phase,)
                or excluded != expected_exclusions
            ):
                _fail("W2B_BACKEND_DOMAIN_MISMATCH")
        if self._family == "fe" and (
            "C15_LAVES" not in self._candidate_phases
            or "C15_LAVES" not in self._effective_phases
            or "C15_LAVES" in self._excluded_phases
            or "C15_LAVES" not in phase_binding.effective_phases
            or "C15_LAVES" in phase_binding.explicit_exclusions
        ):
            _fail("W2B_BACKEND_FE_POLICY_REQUIRED")

    @staticmethod
    def _check_range_card(card: object, number: float) -> None:
        if type(card) is not dict or set(card) != {"minimum", "maximum"}:
            _fail("W2B_BACKEND_BOUNDS_INVALID")
        minimum = card["minimum"]
        maximum = card["maximum"]
        if (
            isinstance(minimum, bool)
            or not isinstance(minimum, (int, float))
            or isinstance(maximum, bool)
            or not isinstance(maximum, (int, float))
        ):
            _fail("W2B_BACKEND_BOUNDS_INVALID")
        lower = float(minimum)
        upper = float(maximum)
        if not (_math.isfinite(lower) and _math.isfinite(upper) and lower <= number <= upper):
            _fail("W2B_BACKEND_BOUNDS_INVALID")

    def _check_range(self, key: str, number: float) -> None:
        self._check_range_card(self._bounds.get(key), number)

    def _bind_state(self, state: _EquilibriumRequest) -> None:
        self._check_range("temperature_k", state.temperature_k)
        self._check_range("pressure_pa", state.pressure_pa)
        state_card = self._full_request.get("state")
        if type(state_card) is not dict:
            _fail("W2B_BACKEND_DOMAIN_MISMATCH")
        declared_components = state_card.get("components")
        if (
            type(declared_components) is not list
            or any(type(item) is not str for item in declared_components)
            or tuple(declared_components) != state.components
        ):
            _fail("W2B_BACKEND_DOMAIN_MISMATCH")
        composition_bounds = self._bounds.get("composition")
        if (
            type(composition_bounds) is not dict
            or set(composition_bounds) != set(state.components)
        ):
            _fail("W2B_BACKEND_BOUNDS_INVALID")
        for component, number in state.composition:
            self._check_range_card(composition_bounds[component], number)
        if self._family == "fe" and "C15_LAVES" not in self._candidate_phases:
            _fail("W2B_BACKEND_FE_POLICY_REQUIRED")

    @staticmethod
    def _bind_key(node: object, state: _EquilibriumRequest) -> None:
        """Bind coordinate/label claims to the exact state and scalar target."""

        composition = dict(state.composition)
        coordinates = dict(node.key.node.coordinates)
        for name, number in coordinates.items():
            if name == "TEMPERATURE_K" and not _same_binary64(number, state.temperature_k):
                _fail("W2B_BACKEND_REQUEST_INVALID")
            if name.startswith("X_"):
                component = name[2:]
                if component not in composition or not _same_binary64(
                    number,
                    composition[component],
                ):
                    _fail("W2B_BACKEND_REQUEST_INVALID")
        labels = dict(node.key.labels)
        if type(node) is _direct.PhaseGibbsBackendNodeRequest:
            if labels.get("PHASE") != node.phase:
                _fail("W2B_BACKEND_REQUEST_INVALID")
        elif type(node) is _direct.PhaseDrivingForceBackendNodeRequest:
            if labels.get("TARGET_PHASE") != node.target_phase:
                _fail("W2B_BACKEND_REQUEST_INVALID")
        elif type(node) is _direct.TZeroBackendNodeRequest:
            if (
                labels.get("PHASE_ONE") != node.phase_one
                or labels.get("PHASE_TWO") != node.phase_two
            ):
                _fail("W2B_BACKEND_REQUEST_INVALID")


class ReceiptBoundDirectBackend(_ReceiptBoundContext):
    """Real pycalphad implementation of the four direct backend operations."""

    __slots__ = (
        "_solver_modules",
        "_database_object",
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
        self._attempted_calls = 0
        self._completed_calls = 0
        self._failed_calls = 0

    def _modules(self) -> _SolverModules:
        self._guard()
        if self._solver_modules is None:
            self._solver_modules = _load_solver_modules()
        if type(self._solver_modules) is not _SolverModules:
            _fail("W2B_BACKEND_CONTEXT_INVALID")
        return self._solver_modules

    def _database(self) -> object:
        runtime_path = self._guard()
        if self._database_object is None:
            modules = self._modules()
            try:
                self._database_object = modules.Database(str(runtime_path))  # type: ignore[operator]
            except Exception as error:
                raise Wave2BBackendError("W2B_BACKEND_DATABASE_LOAD_FAILED") from error
            self._guard()
        return self._database_object

    def _run(self, request: object, expected_type: type, operation):
        self._guard()
        canonical = _copy_node(request, expected_type)
        self._bind_identity(canonical.identity)
        isolated = canonical.phase if expected_type is _direct.PhaseGibbsBackendNodeRequest else None
        self._bind_phase_domain(
            canonical.feature_id,
            canonical.phase_binding,
            isolated_phase=isolated,
        )
        state = (
            canonical.equilibrium
            if expected_type is _direct.EquilibriumBackendNodeRequest
            else canonical.reference_state
            if expected_type is _direct.PhaseDrivingForceBackendNodeRequest
            else canonical.state
        )
        self._bind_state(state)
        self._bind_key(canonical, state)
        if expected_type is _direct.TZeroBackendNodeRequest:
            self._check_range("temperature_k", canonical.minimum_temperature_k)
            self._check_range("temperature_k", canonical.maximum_temperature_k)
        self._attempted_calls += 1
        try:
            reply = operation(canonical)
        except Exception:
            self._failed_calls += 1
            raise
        else:
            self._completed_calls += 1
            return reply
        finally:
            self._guard()

    @staticmethod
    def _conditions(modules: _SolverModules, state: _EquilibriumRequest) -> tuple[list[str], dict[object, float]]:
        variables = modules.variables
        components = list(state.components)
        composition = dict(state.composition)
        if "VA" in composition and composition["VA"] != 0.0:
            raise _direct.ExpectedDirectNodeFailure("DIRECT_BACKEND_DOMAIN_REJECTED")
        material_components = [name for name in components if name != "VA"]
        if not material_components:
            raise _direct.ExpectedDirectNodeFailure("DIRECT_BACKEND_DOMAIN_REJECTED")
        dependent = material_components[-1]
        conditions: dict[object, float] = {
            variables.N: 1.0,
            variables.P: state.pressure_pa,
            variables.T: state.temperature_k,
        }
        for component in material_components:
            if component != dependent:
                conditions[variables.X(component)] = composition[component]
        return components, conditions

    def _solve_dataset(self, state: _EquilibriumRequest, phases: tuple[str, ...]):
        modules = self._modules()
        database = self._database()
        components, conditions = self._conditions(modules, state)
        try:
            dataset = modules.equilibrium(  # type: ignore[operator]
                database,
                components,
                list(phases),
                conditions,
                calc_opts=self._calc_opts,
            )
        except _direct.ExpectedDirectNodeFailure:
            raise
        except Exception as error:
            raise _direct.ExpectedDirectNodeFailure(
                "DIRECT_BACKEND_CONVERGENCE_FAILED"
            ) from error
        return modules, dataset

    @staticmethod
    def _raw_result(
        modules: _SolverModules,
        dataset: object,
        state: _EquilibriumRequest,
    ) -> _EquilibriumRawResult:
        numpy = modules.numpy
        try:
            phase_names = numpy.asarray(dataset.Phase.values, dtype=str).reshape(-1)
            phase_fractions = numpy.asarray(dataset.NP.values, dtype=float).reshape(-1)
            output_components = tuple(
                str(item) for item in dataset.X.coords["component"].values.tolist()
            )
            phase_compositions = numpy.asarray(dataset.X.values, dtype=float).reshape(
                (-1, len(output_components))
            )
        except Exception as error:
            raise _direct.ExpectedDirectNodeFailure("DIRECT_BACKEND_NO_SOLUTION") from error
        if not (
            len(phase_names) == len(phase_fractions) == phase_compositions.shape[0]
        ):
            raise _direct.ExpectedDirectNodeFailure("DIRECT_BACKEND_NO_SOLUTION")
        requested = set(state.phases)
        rows: list[_RawPhaseState] = []
        for index, phase_name in enumerate(phase_names):
            fraction = float(phase_fractions[index])
            phase = str(phase_name)
            if not phase or not _math.isfinite(fraction) or fraction <= 0.0:
                continue
            if phase not in requested:
                _fail("W2B_BACKEND_REPLY_INVALID")
            values = {
                name: float(phase_compositions[index, component_index])
                for component_index, name in enumerate(output_components)
            }
            composition_values: list[float] = []
            for component in state.components:
                value = 0.0 if component == "VA" and component not in values else values.get(component)
                if value is None or not _math.isfinite(value) or value < 0.0:
                    raise _direct.ExpectedDirectNodeFailure("DIRECT_BACKEND_NO_SOLUTION")
                composition_values.append(float(value))
            total = _math.fsum(composition_values)
            if not _math.isfinite(total) or total <= 0.0 or abs(total - 1.0) > 1.0e-8:
                raise _direct.ExpectedDirectNodeFailure("DIRECT_BACKEND_NO_SOLUTION")
            normalized = tuple(
                (component, 0.0 if value == 0.0 else value / total)
                for component, value in zip(state.components, composition_values)
            )
            try:
                rows.append(_RawPhaseState(phase, fraction, normalized))
            except Exception as error:
                raise Wave2BBackendError("W2B_BACKEND_REPLY_INVALID") from error
        if not rows:
            raise _direct.ExpectedDirectNodeFailure("DIRECT_BACKEND_NO_SOLUTION")
        try:
            return _EquilibriumRawResult(tuple(rows))
        except Exception as error:
            raise Wave2BBackendError("W2B_BACKEND_REPLY_INVALID") from error

    @staticmethod
    def _one_finite(modules: _SolverModules, value: object, missing_reason: str) -> float:
        try:
            numbers = modules.numpy.asarray(value, dtype=float).reshape(-1)
            finite = numbers[modules.numpy.isfinite(numbers)]
        except Exception as error:
            raise _direct.ExpectedDirectNodeFailure(missing_reason) from error
        if finite.size != 1:
            raise _direct.ExpectedDirectNodeFailure(missing_reason)
        result = float(finite[0])
        if not _math.isfinite(result):
            raise _direct.ExpectedDirectNodeFailure(missing_reason)
        return 0.0 if result == 0.0 else result

    def solve_equilibrium(
        self,
        request: _direct.EquilibriumBackendNodeRequest,
    ) -> _direct.EquilibriumBackendReply:
        def operation(node: _direct.EquilibriumBackendNodeRequest):
            modules, dataset = self._solve_dataset(node.equilibrium, node.equilibrium.phases)
            raw = self._raw_result(modules, dataset, node.equilibrium)
            return _direct.EquilibriumBackendReply(
                node.identity,
                node.feature_id,
                node.key,
                node.phase_binding,
                raw,
            )

        return self._run(
            request,
            _direct.EquilibriumBackendNodeRequest,
            operation,
        )

    def phase_gibbs_energy(
        self,
        request: _direct.PhaseGibbsBackendNodeRequest,
    ) -> _direct.ScalarBackendReply:
        def operation(node: _direct.PhaseGibbsBackendNodeRequest):
            modules, dataset = self._solve_dataset(node.state, (node.phase,))
            value = self._one_finite(
                modules,
                dataset.GM.values,
                "DIRECT_BACKEND_PROPERTY_UNDEFINED",
            )
            return _direct.ScalarBackendReply(
                node.identity,
                node.feature_id,
                node.key,
                node.phase_binding,
                value,
            )

        return self._run(
            request,
            _direct.PhaseGibbsBackendNodeRequest,
            operation,
        )

    @staticmethod
    def _workspace_values(modules: _SolverModules, workspace: object, prop: object) -> object:
        try:
            return modules.numpy.asarray(workspace.get(prop), dtype=float).reshape(-1)
        except Exception as error:
            raise _direct.ExpectedDirectNodeFailure(
                "DIRECT_BACKEND_PROPERTY_UNDEFINED"
            ) from error

    def phase_driving_force(
        self,
        request: _direct.PhaseDrivingForceBackendNodeRequest,
    ) -> _direct.ScalarBackendReply:
        def operation(node: _direct.PhaseDrivingForceBackendNodeRequest):
            modules = self._modules()
            database = self._database()
            components, conditions = self._conditions(modules, node.reference_state)
            try:
                reference_workspace = modules.Workspace(  # type: ignore[operator]
                    database,
                    components,
                    list(node.reference_state.phases),
                    conditions,
                    calc_opts=self._calc_opts,
                )
                target_workspace = modules.Workspace(  # type: ignore[operator]
                    database,
                    components,
                    [node.target_phase],
                    conditions,
                    calc_opts=self._calc_opts,
                )
                dormant = modules.DormantPhase(  # type: ignore[operator]
                    node.target_phase,
                    target_workspace,
                )
                values = self._workspace_values(
                    modules,
                    reference_workspace,
                    dormant.driving_force,
                )
                value = self._one_finite(
                    modules,
                    values,
                    "DIRECT_BACKEND_PROPERTY_UNDEFINED",
                )
            except _direct.ExpectedDirectNodeFailure:
                raise
            except Exception as error:
                raise _direct.ExpectedDirectNodeFailure(
                    "DIRECT_BACKEND_PROPERTY_UNDEFINED"
                ) from error
            return _direct.ScalarBackendReply(
                node.identity,
                node.feature_id,
                node.key,
                node.phase_binding,
                value,
            )

        return self._run(
            request,
            _direct.PhaseDrivingForceBackendNodeRequest,
            operation,
        )

    @staticmethod
    def _first_composition_set(workspace: object, phase_name: str) -> object | None:
        try:
            for _index, composition_sets in workspace.enumerate_composition_sets():
                for composition_set in composition_sets:
                    if composition_set.phase_record.phase_name == phase_name:
                        return composition_set
        except Exception:
            return None
        return None

    def tzero_temperature(
        self,
        request: _direct.TZeroBackendNodeRequest,
    ) -> _direct.ScalarBackendReply:
        def operation(node: _direct.TZeroBackendNodeRequest):
            modules = self._modules()
            database = self._database()
            components, conditions = self._conditions(modules, node.state)
            try:
                path_workspace = modules.Workspace(  # type: ignore[operator]
                    database,
                    components,
                    [node.phase_one, node.phase_two],
                    conditions,
                    calc_opts=self._calc_opts,
                )
                first_workspace = modules.Workspace(  # type: ignore[operator]
                    database,
                    components,
                    [node.phase_one],
                    conditions,
                    calc_opts=self._calc_opts,
                )
                second_workspace = modules.Workspace(  # type: ignore[operator]
                    database,
                    components,
                    [node.phase_two],
                    conditions,
                    calc_opts=self._calc_opts,
                )
                first = self._first_composition_set(first_workspace, node.phase_one)
                second = self._first_composition_set(second_workspace, node.phase_two)
                if first is None or second is None:
                    raise _direct.ExpectedDirectNodeFailure(
                        "DIRECT_BACKEND_TZERO_NOT_FOUND"
                    )
                tzero_property = modules.T0(first, second, None)  # type: ignore[operator]
                tzero_property.minimum_value = node.minimum_temperature_k
                tzero_property.maximum_value = node.maximum_temperature_k
                values = self._workspace_values(modules, path_workspace, tzero_property)
                value = self._one_finite(
                    modules,
                    values,
                    "DIRECT_BACKEND_TZERO_NOT_FOUND",
                )
                if not (
                    node.minimum_temperature_k
                    <= value
                    <= node.maximum_temperature_k
                ):
                    raise _direct.ExpectedDirectNodeFailure(
                        "DIRECT_BACKEND_TZERO_NOT_FOUND"
                    )
            except _direct.ExpectedDirectNodeFailure:
                raise
            except Exception as error:
                raise _direct.ExpectedDirectNodeFailure(
                    "DIRECT_BACKEND_TZERO_NOT_FOUND"
                ) from error
            return _direct.ScalarBackendReply(
                node.identity,
                node.feature_id,
                node.key,
                node.phase_binding,
                value,
            )

        return self._run(
            request,
            _direct.TZeroBackendNodeRequest,
            operation,
        )

    def receipt_payloads(self) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        """Return canonical-JSON-ready backend/runtime/context payloads.

        The values are suitable for the corresponding arguments of
        ``build_result_receipt``.  No filesystem path is disclosed or retained
        in the payloads.
        """

        self._guard_receipt_identity()
        version = (
            self._solver_modules.version
            if type(self._solver_modules) is _SolverModules
            else "NOT_LOADED"
        )
        backend = {
            "schema_version": BACKEND_SCHEMA,
            "backend_id": BACKEND_ID,
            "pycalphad_version": version,
            "implemented_operations": list(IMPLEMENTED_DIRECT_OPERATIONS),
            "unsupported_path_operations": list(UNSUPPORTED_PATH_OPERATIONS),
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


class ReceiptBoundMappingBackend(_ReceiptBoundContext):
    """Explicit fail-closed MappingBackend stub; it produces no fake ledger."""

    __slots__ = ()

    def map(self, _request: object) -> object:
        self._guard()
        _fail("W2B_BACKEND_NOT_IMPLEMENTED")


class ReceiptBoundSolidificationBackend(_ReceiptBoundContext):
    """Explicit fail-closed SolidificationBackend stub; no path is invented."""

    __slots__ = ()

    def simulate(self, _request: object) -> object:
        self._guard()
        _fail("W2B_BACKEND_NOT_IMPLEMENTED")


__all__ = (
    "BACKEND_SCHEMA",
    "BACKEND_ID",
    "SUPPORTED_DATABASE_FAMILIES",
    "SUPPORTED_FE_PROFILE_IDS",
    "IMPLEMENTED_DIRECT_OPERATIONS",
    "UNSUPPORTED_PATH_OPERATIONS",
    "STEEL_REQUIRED_PRODUCT_SCOPE",
    "FE_BASELINE_PROFILE",
    "FE_EXCLUSION_DECISION_MADE",
    "COUNTS_TOWARD_FEATURE_COVERAGE",
    "ACCEPTANCE_CLAIM",
    "PRODUCTION_USE",
    "WAVE2B_BACKEND_REASON_CODES",
    "Wave2BBackendError",
    "ReceiptBoundDirectBackend",
    "ReceiptBoundMappingBackend",
    "ReceiptBoundSolidificationBackend",
)
