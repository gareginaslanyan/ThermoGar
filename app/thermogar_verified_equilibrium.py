"""Path-free verified equilibrium adapter for Wave B3.

The public boundary accepts only an already-bound database context, a prepared
feature request, and a live execution lease.  Database parsing and backend
dispatch therefore remain inside the verified capability held by the lease.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
import math
import re
from typing import Any, Callable, Mapping, Sequence

import thermogar_verified_loaders as verified_loaders


EQUILIBRIUM_FEATURE_IDS = (
    "equilibrium_single",
    "equilibrium_temperature_scan",
    "equilibrium_composition_scan",
)
PARSER_REVISION = "pycalphad-0.11.2"
ADAPTER_ID = "thermogar.verified-equilibrium"
ADAPTER_REVISION = "1"
BACKEND_ID = "pycalphad-equilibrium"
BACKEND_VERSION = "0.11.2"
_ELEMENT_RE = re.compile(r"[A-Z][A-Z0-9]{0,2}")


@dataclass(frozen=True, slots=True)
class EquilibriumCall:
    feature_id: str
    call_index: int
    axis_value: float
    temperature_k: float
    pressure_pa: float
    balance: str
    components: tuple[str, ...]
    atomic_fractions: tuple[tuple[str, float], ...]
    mass_fractions: tuple[tuple[str, float], ...]
    phases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EquilibriumPoint:
    call: EquilibriumCall
    phase_fractions: tuple[tuple[str, float], ...]
    phase_atomic: tuple[tuple[str, tuple[tuple[str, float], ...]], ...]
    phase_mass: tuple[tuple[str, tuple[tuple[str, float], ...]], ...]
    display_value: object


@dataclass(frozen=True, slots=True)
class VerifiedEquilibriumResult:
    points: tuple[EquilibriumPoint, ...]
    feature_receipt: verified_loaders.FeatureReceipt
    result_envelope: verified_loaders.ResultEnvelope


def _fail(reason: verified_loaders.ReasonCode, detail: str) -> None:
    raise verified_loaders.VerifiedLoaderError(reason, detail)


def _plain_float(value: object, label: str, *, allow_zero: bool = True) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} must be a finite number.")
    result = float(value)
    if not math.isfinite(result) or result < 0.0 or (not allow_zero and result <= 0.0):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} is outside the accepted range.")
    return result


def _element(value: object, label: str) -> str:
    if type(value) is not str or _ELEMENT_RE.fullmatch(value) is None:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} must be a canonical element token.")
    return value


def _composition_pairs(value: Mapping[str, object], balance: str) -> tuple[tuple[str, float], ...]:
    if type(value) is not dict:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "composition_pct must be a plain object.")
    pairs: list[tuple[str, float]] = []
    for raw_element, raw_fraction in value.items():
        element = _element(raw_element, "composition element")
        if element == balance:
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Balance must not be repeated in composition_pct.")
        pairs.append((element, _plain_float(raw_fraction, f"composition_pct.{element}")))
    pairs.sort()
    if len({element for element, _value in pairs}) != len(pairs):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Composition elements must be unique.")
    if sum(value for _element_name, value in pairs) >= 100.0:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Composition leaves no positive balance fraction.")
    return tuple(pairs)


def make_equilibrium_inputs(
    feature_id: str,
    *,
    balance: str,
    units: str,
    composition_pct: Mapping[str, object],
    pressure_pa: object,
    temperatures_k: Sequence[object],
    variable_element: str | None = None,
    concentrations_pct: Sequence[object] = (),
) -> dict[str, Any]:
    """Build the closed, canonical scalar input object used by B3 requests."""

    if feature_id not in EQUILIBRIUM_FEATURE_IDS:
        _fail(verified_loaders.ReasonCode.FEATURE_ID_UNKNOWN, "Feature is outside the B3 equilibrium set.")
    canonical_balance = _element(balance, "balance")
    if units not in ("wt", "at"):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Composition units must be wt or at.")
    composition = _composition_pairs(composition_pct, canonical_balance)
    pressure = _plain_float(pressure_pa, "pressure_pa", allow_zero=False)
    if isinstance(temperatures_k, (str, bytes)):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "temperatures_k must be an ordered sequence.")
    temperatures = tuple(
        _plain_float(value, f"temperatures_k[{index}]", allow_zero=False)
        for index, value in enumerate(temperatures_k)
    )
    if not temperatures:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "At least one temperature is required.")
    if feature_id == "equilibrium_single" and len(temperatures) != 1:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Single equilibrium requires exactly one temperature.")

    if isinstance(concentrations_pct, (str, bytes)):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "concentrations_pct must be an ordered sequence.")
    concentrations = tuple(
        _plain_float(value, f"concentrations_pct[{index}]")
        for index, value in enumerate(concentrations_pct)
    )
    canonical_variable: str | None = None
    if feature_id == "equilibrium_composition_scan":
        canonical_variable = _element(variable_element, "variable_element")
        if canonical_variable == canonical_balance or canonical_variable in dict(composition):
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Variable element must be distinct from fixed composition.")
        if len(temperatures) != 1 or not concentrations:
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Composition scan requires one temperature and an axis.")
        fixed_total = sum(value for _element_name, value in composition)
        if any(fixed_total + value >= 100.0 for value in concentrations):
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Composition scan leaves no positive balance fraction.")
    elif variable_element is not None or concentrations:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Variable composition is only valid for composition scan.")

    return {
        "balance": canonical_balance,
        "composition_pct": [[element, value] for element, value in composition],
        "concentrations_pct": list(concentrations),
        "pressure_pa": pressure,
        "temperatures_k": list(temperatures),
        "units": units,
        "variable_element": canonical_variable,
    }


def _inputs_from_request(request: verified_loaders.FeatureRequest) -> dict[str, Any]:
    if type(request) is not verified_loaders.FeatureRequest:
        _fail(verified_loaders.ReasonCode.REQUEST_DIGEST_MISMATCH, "Adapter requires a frozen FeatureRequest.")
    value = request.inputs
    try:
        composition_value = value["composition_pct"]
        if type(composition_value) is not list:
            raise TypeError
        composition = {
            item[0]: item[1]
            for item in composition_value
            if type(item) is list and len(item) == 2
        }
        rebuilt = make_equilibrium_inputs(
            request.feature_id,
            balance=value["balance"],
            units=value["units"],
            composition_pct=composition,
            pressure_pa=value["pressure_pa"],
            temperatures_k=value["temperatures_k"],
            variable_element=value["variable_element"],
            concentrations_pct=value["concentrations_pct"],
        )
    except (KeyError, TypeError, IndexError):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Feature input object has an invalid shape.")
    if rebuilt != value:
        _fail(verified_loaders.ReasonCode.REQUEST_DIGEST_MISMATCH, "Feature inputs are not canonical.")
    return rebuilt


def _database_masses(database: object, components: Sequence[str]) -> dict[str, float]:
    refstates = getattr(database, "refstates", None)
    if not isinstance(refstates, Mapping):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Parsed database lacks reference-state masses.")
    masses: dict[str, float] = {}
    for component in components:
        if component == "VA":
            continue
        record = refstates.get(component)
        mass = record.get("mass") if isinstance(record, Mapping) else None
        if type(mass) not in (int, float) or not math.isfinite(float(mass)) or float(mass) <= 0.0:
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, f"Missing atomic mass for {component}.")
        masses[component] = float(mass)
    return masses


def _point_fractions(
    database: object,
    inputs: Mapping[str, Any],
    concentration: float | None,
) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, float], ...]]:
    balance = inputs["balance"]
    composition = {element: float(value) for element, value in inputs["composition_pct"]}
    variable = inputs["variable_element"]
    if variable is not None:
        assert concentration is not None
        composition[variable] = concentration
    balance_fraction = 100.0 - sum(composition.values())
    if balance_fraction <= 0.0:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Point composition leaves no positive balance fraction.")
    composition[balance] = balance_fraction
    ordered = tuple(sorted(composition))
    if inputs["units"] == "wt":
        mass = {element: composition[element] / 100.0 for element in ordered}
        masses = _database_masses(database, ordered)
        unscaled = {element: mass[element] / masses[element] for element in ordered}
        total = sum(unscaled.values())
        atomic = {element: unscaled[element] / total for element in ordered}
    else:
        atomic = {element: composition[element] / 100.0 for element in ordered}
        masses = _database_masses(database, ordered)
        unscaled_mass = {element: atomic[element] * masses[element] for element in ordered}
        total_mass = sum(unscaled_mass.values())
        mass = {element: unscaled_mass[element] / total_mass for element in ordered}
    return (
        tuple((element, float(atomic[element])) for element in ordered),
        tuple((element, float(mass[element])) for element in ordered),
    )


def _live_phase_candidates(database: object) -> tuple[str, ...]:
    phases = getattr(database, "phases", None)
    if not isinstance(phases, Mapping):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Parsed database lacks a phase catalog.")
    candidates = tuple(sorted(phase for phase in phases if type(phase) is str and phase))
    if not candidates:
        _fail(verified_loaders.ReasonCode.PHASE_SET_EMPTY, "Parsed database has no phase candidates.")
    return candidates


def _validate_phase_identity(
    context: verified_loaders.BoundDatabaseContext,
    request: verified_loaders.FeatureRequest,
    database: object,
) -> tuple[str, ...]:
    if "C15_LAVES" in request.requested_phases or "C15_LAVES" in request.effective_phases:
        _fail(verified_loaders.ReasonCode.C15_PHASE_REJECTED, "C15_LAVES is rejected before parser/backend dispatch.")
    live_candidates = tuple(
        phase
        for phase in _live_phase_candidates(database)
        if phase not in context.phase_policy.explicit_rejections
    )
    live_effective = context.phase_policy.effective(
        request.requested_phases,
        candidates=live_candidates,
    )
    if request.requested_phases:
        matches = live_effective == request.effective_phases
    else:
        live_order = {phase: index for index, phase in enumerate(live_effective)}
        matches = (
            bool(request.effective_phases)
            and all(phase in live_order for phase in request.effective_phases)
            and tuple(sorted(request.effective_phases, key=live_order.__getitem__)) == request.effective_phases
        )
    if not matches:
        _fail(verified_loaders.ReasonCode.PHASE_POLICY_MISMATCH, "Live parser candidates do not match request phase evidence.")
    return request.effective_phases


def _default_parser(source: object) -> object:
    from pycalphad import Database

    return Database.from_file(source, fmt="tdb")


def _default_backend(database: object, call: EquilibriumCall) -> Mapping[str, object]:
    import numpy as np
    from pycalphad import equilibrium, variables as v

    atomic = dict(call.atomic_fractions)
    conditions: dict[Any, float] = {v.N: 1.0, v.P: call.pressure_pa, v.T: call.temperature_k}
    conditions.update({v.X(element): value for element, value in atomic.items() if element != call.balance})
    result = equilibrium(
        database,
        list(call.components),
        list(call.phases),
        conditions,
        calc_opts={"pdens": 500},
    )
    names = np.asarray(result.Phase.values, dtype=str).ravel()
    fractions = np.asarray(result.NP.values, dtype=float).ravel()
    if len(names) != len(fractions):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend Phase/NP cardinality mismatch.")
    aggregated: dict[str, float] = {}
    elements = tuple(component for component in call.components if component != "VA")
    phase_x = {
        element: np.asarray(result.X.sel(component=element).values, dtype=float).ravel()
        for element in elements
    }
    if any(len(values) != len(names) for values in phase_x.values()):
        _fail(
            verified_loaders.ReasonCode.RESULT_INVALID,
            "Backend Phase/X cardinality mismatch.",
        )
    weighted: dict[str, dict[str, float]] = {}
    for raw_phase, raw_fraction in zip(names, fractions):
        phase = str(raw_phase)
        fraction = float(raw_fraction)
        if not phase:
            if math.isnan(fraction) or (math.isfinite(fraction) and 0.0 <= fraction <= 1e-12):
                continue
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend returned unlabeled phase mass.")
        if phase not in call.phases or phase == "C15_LAVES":
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend returned a phase outside effective scope.")
        if not math.isfinite(fraction) or fraction < 0.0:
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend returned an invalid phase fraction.")
        if fraction <= 1e-12:
            continue
        aggregated[phase] = aggregated.get(phase, 0.0) + fraction
    weighted = {phase: {element: 0.0 for element in elements} for phase in aggregated}
    for index, (raw_phase, raw_fraction) in enumerate(zip(names, fractions)):
        phase = str(raw_phase)
        fraction = float(raw_fraction)
        if phase not in aggregated or not math.isfinite(fraction) or fraction <= 1e-12:
            continue
        for element in elements:
            value = float(phase_x[element][index])
            if math.isfinite(value):
                weighted[phase][element] += fraction * value
    masses = _database_masses(database, elements)
    phase_atomic: dict[str, dict[str, float]] = {}
    phase_mass: dict[str, dict[str, float]] = {}
    for phase, fraction in aggregated.items():
        atomic_raw = {element: weighted[phase][element] / fraction for element in elements}
        atomic_total = sum(atomic_raw.values())
        if atomic_total <= 0.0:
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend phase composition is empty.")
        atomic = {element: atomic_raw[element] / atomic_total for element in elements}
        mass_raw = {element: atomic[element] * masses[element] for element in elements}
        mass_total = sum(mass_raw.values())
        phase_atomic[phase] = atomic
        phase_mass[phase] = {element: mass_raw[element] / mass_total for element in elements}
    return {
        "display_value": result,
        "phase_atomic": phase_atomic,
        "phase_fractions": aggregated,
        "phase_mass": phase_mass,
    }


def _validate_backend_result(
    result: object,
    phases: tuple[str, ...],
) -> tuple[
    tuple[tuple[str, float], ...],
    tuple[tuple[str, tuple[tuple[str, float], ...]], ...],
    tuple[tuple[str, tuple[tuple[str, float], ...]], ...],
    object,
]:
    if type(result) is not dict or tuple(result) != (
        "display_value", "phase_atomic", "phase_fractions", "phase_mass",
    ):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend result must use the exact B3 mapping shape.")
    display_value = result["display_value"]
    phase_atomic = result["phase_atomic"]
    fractions = result["phase_fractions"]
    phase_mass = result["phase_mass"]
    if (
        display_value is None
        or type(fractions) is not dict
        or not fractions
        or type(phase_atomic) is not dict
        or type(phase_mass) is not dict
    ):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend result is incomplete.")
    validated: list[tuple[str, float]] = []
    for phase, raw_fraction in fractions.items():
        if type(phase) is not str or phase not in phases or phase == "C15_LAVES":
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend returned a phase outside effective scope.")
        if type(raw_fraction) is not float or not math.isfinite(raw_fraction) or raw_fraction <= 0.0 or raw_fraction > 1.0 + 1e-8:
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend returned an invalid canonical phase fraction.")
        validated.append((phase, raw_fraction))
    validated.sort()
    if not math.isclose(sum(value for _phase, value in validated), 1.0, abs_tol=1e-8):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend phase fractions do not close to one.")
    ordered_phases = tuple(phase for phase, _value in validated)

    def validate_compositions(value: dict[str, object], label: str) -> tuple[tuple[str, tuple[tuple[str, float], ...]], ...]:
        if set(value) != set(ordered_phases):
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, f"Backend {label} phase set mismatch.")
        output: list[tuple[str, tuple[tuple[str, float], ...]]] = []
        for phase in ordered_phases:
            composition = value[phase]
            if type(composition) is not dict or not composition:
                _fail(verified_loaders.ReasonCode.RESULT_INVALID, f"Backend {label} composition is invalid.")
            items: list[tuple[str, float]] = []
            for element, raw_value in composition.items():
                if (
                    type(element) is not str
                    or _ELEMENT_RE.fullmatch(element) is None
                    or type(raw_value) is not float
                    or not math.isfinite(raw_value)
                    or raw_value < 0.0
                    or raw_value > 1.0 + 1e-8
                ):
                    _fail(verified_loaders.ReasonCode.RESULT_INVALID, f"Backend {label} value is invalid.")
                items.append((element, raw_value))
            items.sort()
            if not math.isclose(sum(item for _element_name, item in items), 1.0, abs_tol=1e-8):
                _fail(verified_loaders.ReasonCode.RESULT_INVALID, f"Backend {label} composition does not close.")
            output.append((phase, tuple(items)))
        return tuple(output)

    return (
        tuple(validated),
        validate_compositions(phase_atomic, "atomic"),
        validate_compositions(phase_mass, "mass"),
        display_value,
    )


def _utc_timestamp(clock: Callable[[], object]) -> str:
    value = clock()
    if isinstance(value, datetime):
        current = value.astimezone(timezone.utc)
        return current.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if type(value) is str and value.endswith("Z"):
        return value
    _fail(verified_loaders.ReasonCode.SCHEMA_INVALID, "Adapter clock returned an invalid value.")
    raise AssertionError


def _system_utc() -> datetime:
    return datetime.now(timezone.utc)


def execute_verified_equilibrium(
    context: verified_loaders.BoundDatabaseContext,
    feature_request: verified_loaders.FeatureRequest,
    lease: verified_loaders.ExecutionLease,
    *,
    parser: Callable[[object], object] = _default_parser,
    backend: Callable[[object, EquilibriumCall], Mapping[str, object]] = _default_backend,
    clock: Callable[[], object] = _system_utc,
) -> VerifiedEquilibriumResult:
    """Execute a generic Ni/Al equilibrium request through a live verified lease."""

    if type(context) is not verified_loaders.BoundDatabaseContext or context.database_key not in ("ni", "al"):
        _fail(verified_loaders.ReasonCode.DATABASE_KEY_REJECTED, "Generic equilibrium accepts only ni or al.")
    if type(feature_request) is not verified_loaders.FeatureRequest or feature_request.feature_id not in EQUILIBRIUM_FEATURE_IDS:
        _fail(verified_loaders.ReasonCode.FEATURE_ID_UNKNOWN, "Request is outside the B3 equilibrium set.")
    if type(lease) is not verified_loaders.ExecutionLease or lease.request != feature_request:
        _fail(verified_loaders.ReasonCode.LEASE_IDENTITY_MISMATCH, "Adapter requires the matching live lease.")
    if (
        feature_request.binding_digest != context.binding_digest
        or feature_request.binding_generation != context.binding_generation
    ):
        _fail(verified_loaders.ReasonCode.BINDING_IDENTITY_MISMATCH, "Context/request identity mismatch.")
    if "C15_LAVES" in feature_request.requested_phases or "C15_LAVES" in feature_request.effective_phases:
        _fail(verified_loaders.ReasonCode.C15_PHASE_REJECTED, "C15_LAVES is rejected before parser/backend dispatch.")
    if not callable(parser):
        _fail(verified_loaders.ReasonCode.PACKAGE_UNAVAILABLE, "Parser seam is unavailable.")
    if not callable(backend):
        _fail(verified_loaders.ReasonCode.BACKEND_FAILED, "Backend seam is unavailable.")
    inputs = _inputs_from_request(feature_request)
    started_at = lease.identity.acquired_at_utc
    try:
        database = lease.parse_tdb(parser=parser, parser_revision=PARSER_REVISION, fresh=True)
    except verified_loaders.VerifiedLoaderError:
        raise
    except Exception as error:
        _fail(verified_loaders.ReasonCode.PACKAGE_UNAVAILABLE, type(error).__name__)
    phases = _validate_phase_identity(context, feature_request, database)

    if feature_request.feature_id == "equilibrium_composition_scan":
        specifications = tuple(
            (value, inputs["temperatures_k"][0], value)
            for value in inputs["concentrations_pct"]
        )
    else:
        specifications = tuple((temperature, temperature, None) for temperature in inputs["temperatures_k"])

    points: list[EquilibriumPoint] = []
    for call_index, (axis_value, temperature_k, concentration) in enumerate(specifications, start=1):
        atomic, mass = _point_fractions(database, inputs, concentration)
        components = tuple(sorted(element for element, _value in atomic)) + ("VA",)
        call = EquilibriumCall(
            feature_id=feature_request.feature_id,
            call_index=call_index,
            axis_value=float(axis_value),
            temperature_k=float(temperature_k),
            pressure_pa=float(inputs["pressure_pa"]),
            balance=inputs["balance"],
            components=components,
            atomic_fractions=atomic,
            mass_fractions=mass,
            phases=phases,
        )
        try:
            raw_result = lease.invoke_backend(
                lambda _live_lease, current_call=call: backend(database, current_call)
            )
        except verified_loaders.VerifiedLoaderError:
            raise
        except Exception as error:
            _fail(verified_loaders.ReasonCode.BACKEND_FAILED, type(error).__name__)
        fractions, phase_atomic, phase_mass, display_value = _validate_backend_result(raw_result, phases)
        points.append(
            EquilibriumPoint(
                call=call,
                phase_fractions=fractions,
                phase_atomic=phase_atomic,
                phase_mass=phase_mass,
                display_value=display_value,
            )
        )

    settings = {
        "points": [
            {
                "axis_value": point.call.axis_value,
                "call_index": point.call.call_index,
                "phase_fractions": [[phase, value] for phase, value in point.phase_fractions],
                "pressure_pa": point.call.pressure_pa,
                "temperature_k": point.call.temperature_k,
            }
            for point in points
        ]
    }
    result_digest = verified_loaders.canonical_digest(
        {
            "settings_digest": verified_loaders.canonical_digest(settings),
            "tables_digest": verified_loaders.canonical_digest([]),
            "figures_digest": verified_loaders.canonical_digest([]),
            "artifacts_digest": verified_loaders.canonical_digest([]),
        }
    )
    finished_at = _utc_timestamp(clock)
    receipt = verified_loaders.make_feature_receipt(
        context,
        feature_request,
        lease,
        outcome="success",
        reason_code=None,
        reason_detail=None,
        backend={
            "adapter_id": ADAPTER_ID,
            "adapter_revision": ADAPTER_REVISION,
            "backend_id": BACKEND_ID,
            "backend_version": BACKEND_VERSION,
        },
        packages=[{"name": "pycalphad", "version": BACKEND_VERSION, "status": "available"}],
        point_count=len(points),
        result_digest=result_digest,
        started_at_utc=started_at,
        finished_at_utc=finished_at,
    )
    envelope = verified_loaders.make_result_envelope(
        context,
        feature_request,
        receipt,
        settings=settings,
        clock=lambda: finished_at,
    )
    return VerifiedEquilibriumResult(
        points=tuple(points),
        feature_receipt=receipt,
        result_envelope=envelope,
    )


def capability_unavailable_receipt(
    context: verified_loaders.BoundDatabaseContext,
    feature_id: str,
    *,
    detail: str,
    clock: Callable[[], object] = _system_utc,
) -> verified_loaders.RejectedFeatureReceipt:
    """Create the frozen no-dispatch receipt for the visible B3 export control."""

    decision = verified_loaders.prepare_feature_request(
        feature_id,
        context,
        {"capability": "disabled_until_b4"},
        (),
        candidate_phases=context.phase_policy.eligible_phases,
        clock=clock,
    )
    if type(decision) is verified_loaders.RejectedFeatureReceipt:
        return decision
    payload = {
        "schema": verified_loaders.SCHEMA_REJECTION,
        "feature_id": feature_id,
        "feature_revision": verified_loaders.FEATURE_REVISION,
        "outcome": "unavailable",
        "reason_code": verified_loaders.ReasonCode.CAPABILITY_UNAVAILABLE.value,
        "reason_detail": detail,
        "binding_digest": context.binding_digest,
        "binding_generation": context.binding_generation,
        "inputs_digest": decision.inputs_digest,
        "requested_phases_digest": decision.requested_phases_digest,
        "effective_phases_digest": decision.effective_phases_digest,
        "request_digest": decision.request_digest,
        "backend_calls": 0,
        "rejected_at_utc": _utc_timestamp(clock),
        "receipt_digest": "",
    }
    payload["receipt_digest"] = verified_loaders.canonical_digest(
        {key: value for key, value in payload.items() if key != "receipt_digest"}
    )
    return verified_loaders.RejectedFeatureReceipt(**payload)
