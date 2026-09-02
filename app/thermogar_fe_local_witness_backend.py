"""Snapshot-only preparation boundary for the standalone Fe local witness.

S1 can load the selected temporary database snapshot, confirm its pinned
metadata and phase universe, and perform the pinned mass-basis conversion.
It cannot run a thermodynamic solver.  There is deliberately no runtime
switch or callback that can promote preparation into execution.
"""

from __future__ import annotations

from contextlib import redirect_stderr
from dataclasses import dataclass
import hashlib
import io
import math
from typing import Any

from thermogar_fe_local_witness_receipts import (
    DATABASE_ELEMENTS,
    ELIGIBLE_PHASE_COUNT,
    ELIGIBLE_PHASE_SHA256,
    FIXED_PDENS,
    FIXED_PRESSURE_PA,
    _LocalWitnessLease,
    MASS_ORDER,
    PROFILE_KEYS,
    RAW_PHASE_COUNT,
    RAW_PHASE_SHA256,
    SOLVER_COMPONENTS,
    _WitnessContract,
    _canonical_digest,
    _validate_mass_fractions,
)


class WitnessBackendError(RuntimeError):
    """Backend failure carrying only one stable non-sensitive code."""

    def __init__(self, code: str):
        if (
            type(code) is not str
            or not code.startswith("FE_LOCAL_WITNESS_")
            or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in code)
        ):
            code = "FE_LOCAL_WITNESS_INTERNAL_FAILURE"
        self.code = code
        super().__init__(code)


def _backend_fail(code: str) -> None:
    raise WitnessBackendError(code)


def _phase_fingerprint(phases: tuple[str, ...]) -> str:
    payload = "".join(f"{phase}\n" for phase in phases).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class WitnessBackendPlan:
    profile_key: str
    temperature_k: float
    mass_fractions: tuple[tuple[str, float], ...]
    solver_components: tuple[str, ...]
    eligible_phases: tuple[str, ...]
    pressure_pa: float
    pdens: int

    def _validate(self) -> None:
        if self.profile_key not in PROFILE_KEYS:
            _backend_fail("FE_LOCAL_WITNESS_PROFILE_INVALID")
        if (
            type(self.temperature_k) is not float
            or not math.isfinite(self.temperature_k)
            or not 673.0 <= self.temperature_k <= 2000.0
        ):
            _backend_fail("FE_LOCAL_WITNESS_TEMPERATURE_INVALID")
        try:
            canonical_mass = _validate_mass_fractions(self.mass_fractions)
        except Exception as error:
            raise WitnessBackendError("FE_LOCAL_WITNESS_COMPOSITION_INVALID") from error
        if canonical_mass != self.mass_fractions:
            _backend_fail("FE_LOCAL_WITNESS_COMPOSITION_INVALID")
        if (
            self.solver_components != SOLVER_COMPONENTS
            or self.solver_components[-2:] != ("FE", "VA")
            or self.eligible_phases != tuple(sorted(self.eligible_phases))
            or _phase_fingerprint(self.eligible_phases) != ELIGIBLE_PHASE_SHA256
            or "C15_LAVES" not in self.eligible_phases
            or self.pressure_pa != FIXED_PRESSURE_PA
            or self.pdens != FIXED_PDENS
        ):
            _backend_fail("FE_LOCAL_WITNESS_SOLVER_SCOPE_INVALID")

    def __post_init__(self) -> None:
        self._validate()


def _build_backend_plan(
    contract: object,
    profile_key: object,
    temperature_k: object,
    mass_fractions: object,
) -> WitnessBackendPlan:
    if type(contract) is not _WitnessContract:
        _backend_fail("FE_LOCAL_WITNESS_CONTRACT_INVALID")
    if type(profile_key) is not str or profile_key not in PROFILE_KEYS:
        _backend_fail("FE_LOCAL_WITNESS_PROFILE_INVALID")
    if isinstance(temperature_k, bool) or not isinstance(temperature_k, (int, float)):
        _backend_fail("FE_LOCAL_WITNESS_TEMPERATURE_INVALID")
    temperature = float(temperature_k)
    try:
        canonical_mass = _validate_mass_fractions(mass_fractions)
    except Exception as error:
        raise WitnessBackendError("FE_LOCAL_WITNESS_COMPOSITION_INVALID") from error
    return WitnessBackendPlan(
        profile_key=profile_key,
        temperature_k=temperature,
        mass_fractions=canonical_mass,
        solver_components=contract.solver_components,
        eligible_phases=contract.eligible_phases,
        pressure_pa=FIXED_PRESSURE_PA,
        pdens=FIXED_PDENS,
    )


@dataclass(frozen=True, slots=True)
class PreparedProjection:
    profile_key: str
    atomic_masses: tuple[tuple[str, float], ...]
    mole_fractions: tuple[tuple[str, float], ...]
    round_trip_mass_fractions: tuple[tuple[str, float], ...]
    max_round_trip_abs_error: float
    raw_phase_count: int
    raw_phase_sha256: str
    eligible_phase_count: int
    eligible_phase_sha256: str
    c15_laves_present: bool
    liquid_present: bool
    real_equilibrium_executed: bool = False

    def _validate(self) -> None:
        if self.profile_key not in PROFILE_KEYS:
            _backend_fail("FE_LOCAL_WITNESS_PREPARATION_INVALID")
        for rows, require_positive in (
            (self.atomic_masses, True),
            (self.mole_fractions, False),
            (self.round_trip_mass_fractions, False),
        ):
            if (
                type(rows) is not tuple
                or tuple(name for name, _value in rows) != MASS_ORDER
                or any(
                    type(value) is not float
                    or not math.isfinite(value)
                    or value < 0.0
                    or (require_positive and value <= 0.0)
                    for _name, value in rows
                )
            ):
                _backend_fail("FE_LOCAL_WITNESS_PREPARATION_INVALID")
        if (
            abs(math.fsum(value for _name, value in self.mole_fractions) - 1.0)
            > 1e-12
            or _validate_mass_fractions(self.round_trip_mass_fractions)
            != self.round_trip_mass_fractions
            or
            type(self.max_round_trip_abs_error) is not float
            or not 0.0 <= self.max_round_trip_abs_error <= 1e-12
            or self.raw_phase_count != RAW_PHASE_COUNT
            or self.raw_phase_sha256 != RAW_PHASE_SHA256
            or self.eligible_phase_count != ELIGIBLE_PHASE_COUNT
            or self.eligible_phase_sha256 != ELIGIBLE_PHASE_SHA256
            or self.c15_laves_present is not True
            or self.liquid_present is not True
            or self.real_equilibrium_executed is not False
        ):
            _backend_fail("FE_LOCAL_WITNESS_PREPARATION_INVALID")

    def __post_init__(self) -> None:
        self._validate()


def _database_atomic_masses(
    database: object,
    contract: _WitnessContract,
    profile_key: str,
) -> tuple[tuple[str, float], ...]:
    try:
        observed_elements = tuple(sorted(str(item).upper() for item in database.elements))
        refstates = database.refstates
    except Exception as error:
        raise WitnessBackendError("FE_LOCAL_WITNESS_DATABASE_METADATA_INVALID") from error
    if observed_elements != DATABASE_ELEMENTS:
        _backend_fail("FE_LOCAL_WITNESS_DATABASE_ELEMENTS_MISMATCH")
    rows: list[tuple[str, float]] = []
    for element in MASS_ORDER:
        try:
            raw_mass = refstates[element]["mass"]
        except Exception as error:
            raise WitnessBackendError("FE_LOCAL_WITNESS_REFSTATE_MASS_INVALID") from error
        if isinstance(raw_mass, bool) or not isinstance(raw_mass, (int, float)):
            _backend_fail("FE_LOCAL_WITNESS_REFSTATE_MASS_INVALID")
        mass = float(raw_mass)
        if not math.isfinite(mass) or mass <= 0.0:
            _backend_fail("FE_LOCAL_WITNESS_REFSTATE_MASS_INVALID")
        rows.append((element, mass))
    result = tuple(rows)
    selected_digest = dict(contract.profile_atomic_mass_sha256).get(profile_key)
    if (
        result != contract.observed_atomic_masses
        or _canonical_digest([list(item) for item in result]) != selected_digest
    ):
        _backend_fail("FE_LOCAL_WITNESS_CROSS_PROFILE_MASS_PIN_MISMATCH")
    return result


def _convert_mass_basis(
    mass_fractions: tuple[tuple[str, float], ...],
    atomic_masses: tuple[tuple[str, float], ...],
) -> tuple[
    tuple[tuple[str, float], ...],
    tuple[tuple[str, float], ...],
    float,
]:
    try:
        from thermogar_equilibrium_core import (
            mass_to_mole_fractions,
            mole_to_mass_fractions,
        )

        mole = mass_to_mole_fractions(mass_fractions, atomic_masses)
        round_trip = mole_to_mass_fractions(mole, atomic_masses)
    except Exception as error:
        raise WitnessBackendError("FE_LOCAL_WITNESS_BASIS_CONVERSION_FAILED") from error
    if (
        tuple(name for name, _value in mole) != MASS_ORDER
        or tuple(name for name, _value in round_trip) != MASS_ORDER
        or len(mole) != 25
        or any(name == "VA" for name, _value in mole)
    ):
        _backend_fail("FE_LOCAL_WITNESS_BASIS_CONVERSION_FAILED")
    error = max(
        abs(dict(mass_fractions)[name] - dict(round_trip)[name])
        for name in MASS_ORDER
    )
    if not math.isfinite(error) or error > 1e-12:
        _backend_fail("FE_LOCAL_WITNESS_ROUND_TRIP_FAILED")
    return mole, round_trip, float(error)


def _load_preflight_api() -> tuple[Any, Any]:
    from pycalphad import Database
    from pycalphad.core.utils import filter_phases

    return Database, filter_phases


def _prepare_snapshot_plan(
    lease: _LocalWitnessLease,
    plan: WitnessBackendPlan,
) -> PreparedProjection:
    """Validate a selected runtime snapshot without invoking a solver."""

    if type(lease) is not _LocalWitnessLease or type(plan) is not WitnessBackendPlan:
        _backend_fail("FE_LOCAL_WITNESS_BACKEND_INPUT_INVALID")
    plan._validate()
    contract, profile_key, snapshot_bytes = lease._backend_snapshot_capability()
    with redirect_stderr(io.StringIO()):
        Database, filter_phases = _load_preflight_api()
    before_database_load = lease._backend_snapshot_observation()
    try:
        snapshot_text = snapshot_bytes.decode("utf-8-sig")
        with redirect_stderr(io.StringIO()):
            database = Database(io.StringIO(snapshot_text))
    except Exception as error:
        raise WitnessBackendError("FE_LOCAL_WITNESS_DATABASE_LOAD_FAILED") from error
    finally:
        snapshot_text = ""
        snapshot_bytes = b""
    after_database_load = lease._backend_snapshot_observation()
    if before_database_load != after_database_load:
        _backend_fail("FE_LOCAL_WITNESS_SNAPSHOT_CHANGED_DURING_DATABASE_LOAD")
    atomic_masses = _database_atomic_masses(database, contract, profile_key)
    mole, round_trip, round_trip_error = _convert_mass_basis(
        plan.mass_fractions,
        atomic_masses,
    )
    try:
        raw_phases = tuple(sorted(str(name).upper() for name in database.phases))
        with redirect_stderr(io.StringIO()):
            eligible = tuple(
                sorted(
                    str(name).upper()
                    for name in filter_phases(
                        database,
                        list(plan.solver_components),
                        candidate_phases=None,
                    )
                )
            )
    except Exception as error:
        raise WitnessBackendError("FE_LOCAL_WITNESS_PHASE_FILTER_FAILED") from error
    raw_sha = _phase_fingerprint(raw_phases)
    eligible_sha = _phase_fingerprint(eligible)
    if (
        len(raw_phases) != RAW_PHASE_COUNT
        or len(set(raw_phases)) != len(raw_phases)
        or raw_sha != RAW_PHASE_SHA256
        or len(eligible) != ELIGIBLE_PHASE_COUNT
        or len(set(eligible)) != len(eligible)
        or eligible != plan.eligible_phases
        or eligible_sha != ELIGIBLE_PHASE_SHA256
        or tuple(sorted(set(raw_phases) - set(eligible))) != ("BCC_A2",)
        or "C15_LAVES" not in eligible
        or "LIQUID" not in eligible
    ):
        _backend_fail("FE_LOCAL_WITNESS_PHASE_SCOPE_MISMATCH")
    return PreparedProjection(
        profile_key=profile_key,
        atomic_masses=atomic_masses,
        mole_fractions=mole,
        round_trip_mass_fractions=round_trip,
        max_round_trip_abs_error=round_trip_error,
        raw_phase_count=len(raw_phases),
        raw_phase_sha256=raw_sha,
        eligible_phase_count=len(eligible),
        eligible_phase_sha256=eligible_sha,
        c15_laves_present=True,
        liquid_present=True,
        real_equilibrium_executed=False,
    )


def _prepare_local_witness_backend(
    lease: _LocalWitnessLease,
    plan: WitnessBackendPlan,
) -> PreparedProjection:
    """Run the fixed S1 preparation path; no callback is accepted."""

    return _prepare_snapshot_plan(lease, plan)
