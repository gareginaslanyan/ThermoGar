"""Standalone Fe/Steel local diagnostic witness service.

The service is intentionally disconnected from ThermoGar's product and
release surfaces.  S1 validates a pinned request and prepares the selected
runtime snapshot, but returns a terminal NOT_EXECUTED receipt instead of
running a thermodynamic solver.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import thermogar_fe_local_witness_backend as _backend
import thermogar_fe_local_witness_receipts as _receipts


_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class LocalFeWitnessError(RuntimeError):
    """Fail-closed user-facing error with a stable, non-sensitive code."""

    def __init__(self, code: str):
        if (
            type(code) is not str
            or not code.startswith("FE_LOCAL_WITNESS_")
            or any(
                character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
                for character in code
            )
        ):
            code = "FE_LOCAL_WITNESS_INTERNAL_FAILURE"
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class LocalFeWitnessResult:
    """Immutable, path-free receipt bundle for the S1 preparation attempt."""

    profile: _receipts.ProfileReceipt
    request: _receipts.RequestReceipt
    domain: _receipts.DomainReceipt
    pre: _receipts.HashSnapshotReceipt
    post: _receipts.HashSnapshotReceipt
    prepared: _receipts.PreparedReceipt | None
    failure: _receipts.FailureReceipt | None

    def _validate(self) -> None:
        if (
            type(self.profile) is not _receipts.ProfileReceipt
            or type(self.request) is not _receipts.RequestReceipt
            or type(self.domain) is not _receipts.DomainReceipt
            or type(self.pre) is not _receipts.HashSnapshotReceipt
            or type(self.post) is not _receipts.HashSnapshotReceipt
            or (
                self.prepared is not None
                and type(self.prepared) is not _receipts.PreparedReceipt
            )
            or (
                self.failure is not None
                and type(self.failure) is not _receipts.FailureReceipt
            )
            or (self.prepared is None) == (self.failure is None)
        ):
            raise LocalFeWitnessError("FE_LOCAL_WITNESS_RECEIPT_CHAIN_INVALID")

        # Every nested serializer re-runs its own frozen-slot invariants.
        for receipt in (
            self.profile,
            self.request,
            self.domain,
            self.pre,
            self.post,
        ):
            receipt.as_dict()
        terminal = self.prepared if self.prepared is not None else self.failure
        assert terminal is not None
        terminal.as_dict()

        profile_key = self.profile.profile_key
        if (
            self.request.profile_key != profile_key
            or self.domain.profile_key != profile_key
            or self.request.temperature_k != self.domain.temperature_k
            or self.pre.stage != "PRE"
            or self.pre.terminal_state != "NOT_EXECUTED"
            or self.pre.lease_id != self.post.lease_id
            or self.pre.request_receipt_digest != self.request.digest
            or self.post.request_receipt_digest != self.request.digest
            or self.pre.domain_receipt_digest != self.domain.digest
            or self.post.domain_receipt_digest != self.domain.digest
            or self.pre.profile_receipt_digest != self.profile.digest
            or self.post.profile_receipt_digest != self.profile.digest
            or self.pre.source_observations != self.post.source_observations
            or self.pre.runtime_snapshot_observations
            != self.post.runtime_snapshot_observations
        ):
            raise LocalFeWitnessError("FE_LOCAL_WITNESS_RECEIPT_CHAIN_INVALID")
        if self.prepared is not None and (
            self.post.stage != "POST_PREPARATION"
            or self.post.terminal_state != "PREPARED_NOT_EXECUTED"
            or self.prepared.profile != self.profile
            or self.prepared.request != self.request
            or self.prepared.domain != self.domain
            or self.prepared.pre != self.pre
            or self.prepared.post != self.post
        ):
            raise LocalFeWitnessError("FE_LOCAL_WITNESS_RECEIPT_CHAIN_INVALID")
        if self.failure is not None and (
            self.post.stage != "POST_FAILURE"
            or self.post.terminal_state != "FAILED"
            or self.failure.profile != self.profile
            or self.failure.request != self.request
            or self.failure.domain != self.domain
            or self.failure.pre != self.pre
            or self.failure.post != self.post
        ):
            raise LocalFeWitnessError("FE_LOCAL_WITNESS_RECEIPT_CHAIN_INVALID")

    def __post_init__(self) -> None:
        self._validate()

    def as_dict(self) -> dict[str, Any]:
        self._validate()
        prepared = self.prepared is not None
        payload: dict[str, Any] = {
            "outcome": (
                "PREPARED_NOT_EXECUTED" if prepared else "PREPARATION_FAILED"
            ),
            "profile": self.profile.as_dict(),
            "request": self.request.as_dict(),
            "domain": self.domain.as_dict(),
            "pre": self.pre.as_dict(),
            "post": self.post.as_dict(),
            "prepared": (
                self.prepared.as_dict() if self.prepared is not None else None
            ),
            "failure": (
                self.failure.as_dict() if self.failure is not None else None
            ),
            "pressure_pa": 101325.0,
            "pressure_domain_status": "UNKNOWN_BLOCKED",
            "solver_components": list(_receipts.SOLVER_COMPONENTS),
            "eligible_phase_count": _receipts.ELIGIBLE_PHASE_COUNT,
            "eligible_phase_sha256": _receipts.ELIGIBLE_PHASE_SHA256,
            "c15_laves_required": True,
            "liquid_required": True,
            "phase_exclusions": [],
            "pdens": 500,
            "pdens_semantic": "LOCAL_NUMERICAL_OPTION_NOT_SOURCE_DOMAIN_CLAIM",
            "real_equilibrium_executed": False,
            "raw_xarray_included": False,
            "raw_exception_included": False,
            "path_included": False,
        }
        return {
            **payload,
            "schema_version": "SWR-NE04-FE-LOCAL-WITNESS-RESULT-1",
            "receipt_kind": "FE_LOCAL_WITNESS_S1_BUNDLE",
            "claim": "LOCAL_INTERNAL_DIAGNOSTIC_NOT_NE04_RELEASE",
            "acceptance": False,
            "counts_toward_ne04_acceptance": False,
            "execution_eligible": False,
            "release_eligible": False,
            "production_use": "DENIED",
        }


def _canonical_request(
    profile_id: object,
    mass_fractions: object,
    temperature_k: object,
) -> tuple[str, tuple[tuple[str, float], ...], float]:
    if type(profile_id) is not str or profile_id not in _receipts.PROFILE_KEYS:
        raise LocalFeWitnessError("FE_LOCAL_WITNESS_PROFILE_INVALID")
    if isinstance(temperature_k, bool) or not isinstance(
        temperature_k, (int, float)
    ):
        raise LocalFeWitnessError("FE_LOCAL_WITNESS_TEMPERATURE_INVALID")
    temperature = float(temperature_k)
    if (
        not math.isfinite(temperature)
        or not _receipts.TEMPERATURE_MINIMUM_K
        <= temperature
        <= _receipts.TEMPERATURE_MAXIMUM_K
    ):
        raise LocalFeWitnessError("FE_LOCAL_WITNESS_TEMPERATURE_INVALID")
    try:
        composition = _receipts._canonicalize_mass_fraction_mapping(
            mass_fractions
        )
    except _receipts.WitnessContractError as error:
        raise LocalFeWitnessError(
            "FE_LOCAL_WITNESS_COMPOSITION_INVALID"
        ) from error
    return profile_id, composition, temperature


def _run_local_fe_witness(
    profile_id: str,
    mass_fractions: Mapping[str, float],
    temperature_k: float,
) -> LocalFeWitnessResult:
    """Prepare one pinned Fe witness request and return a blocked S1 receipt."""

    profile_key, composition, temperature = _canonical_request(
        profile_id,
        mass_fractions,
        temperature_k,
    )
    try:
        contract, profile = _receipts._load_profile_receipt(
            _PROJECT_ROOT,
            profile_key,
        )
        request = _receipts.RequestReceipt(
            profile_key=profile_key,
            temperature_k=temperature,
            mass_fractions=composition,
        )
        domain = _receipts._build_domain_receipt(
            contract,
            profile_key,
            temperature,
            composition,
        )
        plan = _backend._build_backend_plan(
            contract,
            profile_key,
            temperature,
            composition,
        )
    except (_receipts.WitnessContractError, _backend.WitnessBackendError) as error:
        code = getattr(error, "code", "FE_LOCAL_WITNESS_CONTRACT_INVALID")
        raise LocalFeWitnessError(code) from error

    prepared_projection: _backend.PreparedProjection | None = None
    failure_code: str | None = None
    try:
        with _receipts._open_local_witness_lease(
            _PROJECT_ROOT,
            contract,
            profile,
            request,
            domain,
        ) as lease:
            pre = lease._preparation_rehash()
            try:
                prepared_projection = _backend._prepare_local_witness_backend(
                    lease,
                    plan,
                )
                prepared_projection._validate()
            except _backend.WitnessBackendError as error:
                failure_code = error.code
            except Exception:
                failure_code = "FE_LOCAL_WITNESS_INTERNAL_FAILURE"
            finally:
                if prepared_projection is not None:
                    lease._mark_prepared_not_executed()
                else:
                    lease._mark_failed()
                post = lease._post_rehash(pre)
    except _receipts.WitnessContractError as error:
        raise LocalFeWitnessError("FE_LOCAL_WITNESS_LEASE_FAILED") from error

    prepared_receipt: _receipts.PreparedReceipt | None = None
    failure_receipt: _receipts.FailureReceipt | None = None
    if prepared_projection is not None:
        prepared_receipt = _receipts.PreparedReceipt(
            profile=profile,
            request=request,
            domain=domain,
            pre=pre,
            post=post,
            atomic_masses=prepared_projection.atomic_masses,
            derived_mole_fractions=prepared_projection.mole_fractions,
            round_trip_mass_fractions=(
                prepared_projection.round_trip_mass_fractions
            ),
            max_round_trip_abs_error=(
                prepared_projection.max_round_trip_abs_error
            ),
            raw_phase_count=prepared_projection.raw_phase_count,
            raw_phase_sha256=prepared_projection.raw_phase_sha256,
            eligible_phase_count=prepared_projection.eligible_phase_count,
            eligible_phase_sha256=prepared_projection.eligible_phase_sha256,
        )
    else:
        failure_receipt = _receipts.FailureReceipt(
            profile=profile,
            request=request,
            domain=domain,
            pre=pre,
            post=post,
            failure_code=(
                failure_code
                if failure_code is not None
                else "FE_LOCAL_WITNESS_INTERNAL_FAILURE"
            ),
        )
    return LocalFeWitnessResult(
        profile=profile,
        request=request,
        domain=domain,
        pre=pre,
        post=post,
        prepared=prepared_receipt,
        failure=failure_receipt,
    )


def run_local_fe_witness(
    profile_id: str,
    mass_fractions: Mapping[str, float],
    temperature_k: float,
) -> LocalFeWitnessResult:
    """Public fail-closed boundary with no raw cause, path, or exception."""

    error_code: str | None = None
    try:
        result = _run_local_fe_witness(
            profile_id,
            mass_fractions,
            temperature_k,
        )
    except LocalFeWitnessError as error:
        error_code = error.code
    except Exception:
        error_code = "FE_LOCAL_WITNESS_INTERNAL_FAILURE"
    else:
        return result
    raise LocalFeWitnessError(error_code) from None


__all__ = [
    "LocalFeWitnessError",
    "LocalFeWitnessResult",
    "run_local_fe_witness",
]
