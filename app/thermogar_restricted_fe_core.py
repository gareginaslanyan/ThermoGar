"""Fail-closed execution boundary for three restricted Fe UI calculations."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import partial
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

from pycalphad import Database
from pycalphad.core.utils import filter_phases

from thermogar_secure_io import MAX_TDB_SNAPSHOT_BYTES, lexical_absolute
from thermogar_verified_artifact import (
    VerifiedTextArtifact,
    duplicate_reject_json,
    held_verified_utf8_text,
)
import thermogar_verified_loaders as verified_loaders


DATABASE_KEY = "fe"
PROFILE_KEY = "thermogar_patch"
PATCH_ID = "TG-FE-2062-C15-001"
DATABASE_RELATIVE_PATH = (
    "databases/converted/fe/"
    "mc_fe_v2062_with_mobility.thermogar.tdb"
)
DATABASE_SHA256 = (
    "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612"
)
PASSPORT_RELATIVE_PATH = (
    "databases/converted/fe/"
    "mc_fe_v2062_with_mobility.thermogar.passport.json"
)
PASSPORT_SHA256 = (
    "c818f3132840304ea38017cb7419790a290a1ca2e949b01e8954931ac8f17491"
)
MAX_PASSPORT_SNAPSHOT_BYTES = 256 * 1024
C15_PHASE = "C15_LAVES"
FEATURE_IDS = frozenset(
    {
        "equilibrium_single",
        "equilibrium_temperature_scan",
        "equilibrium_composition_scan",
    }
)


class RestrictedFeError(RuntimeError):
    """The exact restricted-Fe contract was not satisfied."""


def _plain_float(value: object, label: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise RestrictedFeError(f"{label} must be a finite real scalar.")
    result = float(value)
    if not math.isfinite(result):
        raise RestrictedFeError(f"{label} must be finite.")
    return result


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise RestrictedFeError("Restricted Fe identity is not canonical JSON.") from error


def canonical_digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class RestrictedFeContext:
    database_key: str = DATABASE_KEY
    profile_key: str = PROFILE_KEY
    database_relative_path: str = DATABASE_RELATIVE_PATH
    database_sha256: str = DATABASE_SHA256
    passport_relative_path: str = PASSPORT_RELATIVE_PATH
    passport_sha256: str = PASSPORT_SHA256
    patch_id: str = PATCH_ID

    def __post_init__(self) -> None:
        if self != RestrictedFeContext.__new_exact():
            raise RestrictedFeError("Restricted Fe context identity mismatch.")

    @classmethod
    def __new_exact(cls) -> "RestrictedFeContext":
        value = object.__new__(cls)
        object.__setattr__(value, "database_key", DATABASE_KEY)
        object.__setattr__(value, "profile_key", PROFILE_KEY)
        object.__setattr__(value, "database_relative_path", DATABASE_RELATIVE_PATH)
        object.__setattr__(value, "database_sha256", DATABASE_SHA256)
        object.__setattr__(value, "passport_relative_path", PASSPORT_RELATIVE_PATH)
        object.__setattr__(value, "passport_sha256", PASSPORT_SHA256)
        object.__setattr__(value, "patch_id", PATCH_ID)
        return value


def restricted_fe_context() -> RestrictedFeContext:
    return RestrictedFeContext()


@dataclass(frozen=True, slots=True)
class RestrictedFeRequest:
    feature_id: str
    balance: str
    units: str
    composition_pct: tuple[tuple[str, float], ...]
    pressure_pa: float
    temperatures_k: tuple[float, ...]
    requested_phases: tuple[str, ...] = ()
    variable_element: str | None = None
    concentrations_pct: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if type(self.feature_id) is not str or self.feature_id not in FEATURE_IDS:
            raise RestrictedFeError("Restricted Fe feature_id is not allowed.")
        if type(self.balance) is not str or self.balance != self.balance.upper():
            raise RestrictedFeError("Balance element must be an uppercase symbol.")
        if self.units not in {"at", "wt"}:
            raise RestrictedFeError("Composition units must be exactly at or wt.")
        pressure = _plain_float(self.pressure_pa, "pressure_pa")
        if pressure <= 0.0 or type(self.pressure_pa) is not float:
            raise RestrictedFeError("pressure_pa must be a positive JSON float.")
        if type(self.composition_pct) is not tuple:
            raise RestrictedFeError("composition_pct must be an immutable tuple.")
        elements: list[str] = []
        total = 0.0
        for item in self.composition_pct:
            if type(item) is not tuple or len(item) != 2:
                raise RestrictedFeError("Composition entries must be immutable pairs.")
            element, raw_value = item
            if type(element) is not str or element != element.upper():
                raise RestrictedFeError("Composition element is not canonical.")
            value = _plain_float(raw_value, f"composition_pct.{element}")
            if type(raw_value) is not float or value <= 0.0:
                raise RestrictedFeError("Composition percentages must be positive floats.")
            elements.append(element)
            total += value
        if tuple(elements) != tuple(sorted(set(elements))):
            raise RestrictedFeError("Composition elements must be unique and ordered.")
        if self.balance in elements or total >= 100.0:
            raise RestrictedFeError("Composition does not leave a positive balance.")
        if type(self.requested_phases) is not tuple or any(
            type(phase) is not str or phase != phase.upper()
            for phase in self.requested_phases
        ):
            raise RestrictedFeError("Requested phases must be an immutable canonical tuple.")
        if self.requested_phases != tuple(sorted(set(self.requested_phases))):
            raise RestrictedFeError("Requested phases must be unique and ordered.")
        if C15_PHASE in self.requested_phases:
            raise RestrictedFeError("C15_LAVES is disabled in restricted Fe execution.")

        temperatures = tuple(
            _plain_float(value, "temperature_k") for value in self.temperatures_k
        )
        if type(self.temperatures_k) is not tuple or any(
            type(value) is not float or value <= 0.0 for value in temperatures
        ):
            raise RestrictedFeError("Temperatures must be positive immutable floats.")
        concentrations = tuple(
            _plain_float(value, "concentration_pct")
            for value in self.concentrations_pct
        )
        if type(self.concentrations_pct) is not tuple or any(
            type(value) is not float or value < 0.0 for value in concentrations
        ):
            raise RestrictedFeError("Concentrations must be non-negative immutable floats.")

        if self.feature_id == "equilibrium_single":
            valid_shape = (
                len(temperatures) == 1
                and not concentrations
                and self.variable_element is None
            )
        elif self.feature_id == "equilibrium_temperature_scan":
            valid_shape = (
                len(temperatures) == 3
                and tuple(sorted(set(temperatures))) == temperatures
                and not concentrations
                and self.variable_element is None
            )
        else:
            valid_shape = (
                len(temperatures) == 1
                and len(concentrations) == 3
                and tuple(sorted(set(concentrations))) == concentrations
                and type(self.variable_element) is str
                and self.variable_element == self.variable_element.upper()
                and self.variable_element != self.balance
                and self.variable_element not in elements
                and total + concentrations[-1] < 100.0
            )
        if not valid_shape:
            raise RestrictedFeError("Restricted Fe request point shape is invalid.")


def make_restricted_fe_request(
    feature_id: str,
    *,
    balance: str,
    units: str,
    composition_pct: Mapping[str, float],
    pressure_pa: float,
    temperatures_k: Sequence[float],
    requested_phases: Sequence[str] = (),
    variable_element: str | None = None,
    concentrations_pct: Sequence[float] = (),
) -> RestrictedFeRequest:
    if type(composition_pct) is not dict:
        raise RestrictedFeError("Composition must be a plain mapping.")
    return RestrictedFeRequest(
        feature_id=feature_id,
        balance=str(balance).upper(),
        units=units,
        composition_pct=tuple(
            sorted((str(key).upper(), float(value)) for key, value in composition_pct.items())
        ),
        pressure_pa=float(pressure_pa),
        temperatures_k=tuple(float(value) for value in temperatures_k),
        requested_phases=tuple(sorted(str(value).upper() for value in requested_phases)),
        variable_element=(
            None if variable_element is None else str(variable_element).upper()
        ),
        concentrations_pct=tuple(float(value) for value in concentrations_pct),
    )


@dataclass(frozen=True, slots=True)
class RestrictedFeRunnerCall:
    feature_id: str
    call_index: int
    axis_value: float
    temperature_k: float
    pressure_pa: float
    balance: str
    components: tuple[str, ...]
    atomic_fractions: tuple[tuple[str, float], ...]
    phases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RestrictedFePointReceipt:
    call_index: int
    axis_value: float
    temperature_k: float
    pressure_pa: float
    atomic_fractions: tuple[tuple[str, float], ...]
    phase_fractions: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        if type(self.call_index) is not int or self.call_index <= 0:
            raise RestrictedFeError("Receipt call index is invalid.")
        for value, label in (
            (self.axis_value, "axis_value"),
            (self.temperature_k, "temperature_k"),
            (self.pressure_pa, "pressure_pa"),
        ):
            if type(value) is not float or not math.isfinite(value):
                raise RestrictedFeError(f"Receipt {label} is invalid.")
        if self.temperature_k <= 0.0 or self.pressure_pa <= 0.0:
            raise RestrictedFeError("Receipt T/P must be positive.")
        if type(self.atomic_fractions) is not tuple or not self.atomic_fractions:
            raise RestrictedFeError("Receipt atomic composition is not immutable.")
        if not math.isclose(
            sum(value for _element, value in self.atomic_fractions),
            1.0,
            abs_tol=1e-12,
        ):
            raise RestrictedFeError("Receipt atomic composition does not close.")
        if type(self.phase_fractions) is not tuple or not self.phase_fractions:
            raise RestrictedFeError("Receipt phase evidence is not immutable.")
        if C15_PHASE in dict(self.phase_fractions):
            raise RestrictedFeError("Receipt contains disabled C15_LAVES.")
        if not math.isclose(
            sum(value for _phase, value in self.phase_fractions),
            1.0,
            abs_tol=1e-8,
        ):
            raise RestrictedFeError("Receipt phase evidence does not close.")


@dataclass(frozen=True, slots=True)
class RestrictedFeReceipt:
    schema: str
    feature_id: str
    context_digest: str
    request_digest: str
    ordered_phases: tuple[str, ...]
    ordered_phases_digest: str
    source_hashes: tuple[tuple[str, str], ...]
    calls: int
    points: tuple[RestrictedFePointReceipt, ...]
    outcome: str
    error_code: str | None
    material_base: str
    experimental_qualification: str

    def __post_init__(self) -> None:
        if self.schema != "thermogar.restricted_fe.receipt.v2":
            raise RestrictedFeError("Restricted Fe receipt schema mismatch.")
        if self.feature_id not in FEATURE_IDS:
            raise RestrictedFeError("Restricted Fe receipt feature mismatch.")
        for digest in (
            self.context_digest,
            self.request_digest,
            self.ordered_phases_digest,
        ):
            if (
                type(digest) is not str
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise RestrictedFeError("Restricted Fe receipt digest is invalid.")
        if (
            type(self.ordered_phases) is not tuple
            or self.ordered_phases != tuple(sorted(set(self.ordered_phases)))
            or C15_PHASE in self.ordered_phases
            or not self.ordered_phases
            or self.ordered_phases_digest
            != canonical_digest(list(self.ordered_phases))
        ):
            raise RestrictedFeError("Restricted Fe receipt phase identity mismatch.")
        if self.source_hashes != (
            ("database_sha256", DATABASE_SHA256),
            ("passport_sha256", PASSPORT_SHA256),
        ):
            raise RestrictedFeError("Restricted Fe receipt source identity mismatch.")
        if type(self.calls) is not int or type(self.points) is not tuple:
            raise RestrictedFeError("Restricted Fe receipt call evidence is invalid.")
        expected_calls = 1 if self.feature_id == "equilibrium_single" else 3
        success_shape = (
            self.outcome == "success"
            and self.error_code is None
            and self.calls == expected_calls
            and len(self.points) == expected_calls
        )
        failure_shape = (
            self.outcome == "failure"
            and type(self.error_code) is str
            and 1 <= self.calls <= expected_calls
            and len(self.points) < self.calls
        )
        if not (success_shape or failure_shape):
            raise RestrictedFeError("Restricted Fe receipt outcome evidence mismatch.")
        if tuple(point.call_index for point in self.points) != tuple(
            range(1, len(self.points) + 1)
        ):
            raise RestrictedFeError("Restricted Fe receipt point order mismatch.")
        if (
            self.material_base != "STEEL"
            or self.experimental_qualification != "NOT_PERFORMED"
        ):
            raise RestrictedFeError("Restricted Fe receipt metadata mismatch.")


def context_digest(context: RestrictedFeContext) -> str:
    if type(context) is not RestrictedFeContext:
        raise RestrictedFeError("Context must be the frozen restricted Fe type.")
    return canonical_digest(asdict(context))


def request_digest(request: RestrictedFeRequest) -> str:
    if type(request) is not RestrictedFeRequest:
        raise RestrictedFeError("Request must be the frozen restricted Fe type.")
    return canonical_digest(asdict(request))


def input_fingerprint(
    context: RestrictedFeContext,
    request: RestrictedFeRequest,
) -> str:
    return canonical_digest(
        {"context_digest": context_digest(context), "request_digest": request_digest(request)}
    )


def retain_receipt_for_fingerprint(
    receipt: RestrictedFeReceipt | None,
    stored_fingerprint: str | None,
    current_fingerprint: str,
) -> RestrictedFeReceipt | None:
    if (
        type(receipt) is RestrictedFeReceipt
        and type(stored_fingerprint) is str
        and stored_fingerprint == current_fingerprint
        and receipt.outcome == "success"
    ):
        return receipt
    return None


def effective_phase_names(
    candidate_phases: Sequence[str],
    requested_phases: Sequence[str] = (),
) -> tuple[str, ...]:
    candidates = tuple(sorted(set(candidate_phases)))
    if any(type(phase) is not str or phase != phase.upper() for phase in candidates):
        raise RestrictedFeError("Database phase names are not canonical.")
    effective = tuple(phase for phase in candidates if phase != C15_PHASE)
    requested = tuple(requested_phases)
    if C15_PHASE in requested:
        raise RestrictedFeError("C15_LAVES is disabled before runner dispatch.")
    if requested:
        if requested != tuple(sorted(set(requested))):
            raise RestrictedFeError("Explicit phase selection is not canonical.")
        unknown = tuple(phase for phase in requested if phase not in effective)
        if unknown:
            raise RestrictedFeError("Explicit phase selection is outside effective phases.")
        effective = requested
    if not effective:
        raise RestrictedFeError("Restricted Fe execution has no effective phases.")
    return effective


@dataclass(frozen=True, slots=True)
class _VerifiedArtifacts:
    database: VerifiedTextArtifact
    passport: Mapping[str, Any]


def _validate_passport(payload: object) -> Mapping[str, Any]:
    if type(payload) is not dict:
        raise RestrictedFeError("Fe passport must be a JSON object.")
    if (
        payload.get("schema_version") != 2
        or payload.get("patch_id") != PATCH_ID
        or payload.get("profile_id") != "mc_fe_v2062_thermogar_working"
    ):
        raise RestrictedFeError("Fe passport identity mismatch.")
    working = payload.get("working_profile")
    if type(working) is not dict:
        raise RestrictedFeError("Fe passport working profile is absent.")
    combined = working.get("thermodynamic_plus_mobility_database")
    if type(combined) is not dict or str(combined.get("sha256", "")).lower() != DATABASE_SHA256:
        raise RestrictedFeError("Fe passport database hash mismatch.")
    patches = payload.get("compatibility_patches")
    if type(patches) is not list or len(patches) != 1:
        raise RestrictedFeError("Fe passport patch witness is not singular.")
    patch = patches[0]
    if (
        type(patch) is not dict
        or patch.get("patch_id") != PATCH_ID
        or patch.get("phase") != C15_PHASE
        or patch.get("applied") is not True
        or patch.get("matched_active_commands") != 1
    ):
        raise RestrictedFeError("Fe passport patch witness mismatch.")
    return payload


def verify_restricted_fe_passport(
    project_root: str | Path,
    context: RestrictedFeContext,
) -> str:
    if type(context) is not RestrictedFeContext or context != restricted_fe_context():
        raise RestrictedFeError("Only the exact restricted Fe context is accepted.")
    root = lexical_absolute(project_root)
    passport_path = lexical_absolute(root / context.passport_relative_path)
    if passport_path != lexical_absolute(root / PASSPORT_RELATIVE_PATH):
        raise RestrictedFeError("Fe passport path is not canonical.")
    with held_verified_utf8_text(
        passport_path,
        expected_sha256=context.passport_sha256,
        maximum_bytes=MAX_PASSPORT_SNAPSHOT_BYTES,
        canonical_root=root,
    ) as passport_artifact:
        _validate_passport(duplicate_reject_json(passport_artifact.text))
        return passport_artifact.sha256


@contextmanager
def _open_verified_artifacts(
    project_root: Path,
    context: RestrictedFeContext,
) -> Iterator[_VerifiedArtifacts]:
    root = lexical_absolute(project_root)
    database_path = lexical_absolute(root / context.database_relative_path)
    passport_path = lexical_absolute(root / context.passport_relative_path)
    if database_path != lexical_absolute(root / DATABASE_RELATIVE_PATH):
        raise RestrictedFeError("Fe database path is not canonical.")
    if passport_path != lexical_absolute(root / PASSPORT_RELATIVE_PATH):
        raise RestrictedFeError("Fe passport path is not canonical.")
    with held_verified_utf8_text(
        database_path,
        expected_sha256=context.database_sha256,
        maximum_bytes=MAX_TDB_SNAPSHOT_BYTES,
        canonical_root=root,
    ) as database_artifact:
        with held_verified_utf8_text(
            passport_path,
            expected_sha256=context.passport_sha256,
            maximum_bytes=MAX_PASSPORT_SNAPSHOT_BYTES,
            canonical_root=root,
        ) as passport_artifact:
            passport = _validate_passport(duplicate_reject_json(passport_artifact.text))
            yield _VerifiedArtifacts(database=database_artifact, passport=passport)


def _point_composition(
    database: Any,
    request: RestrictedFeRequest,
    concentration_pct: float | None,
) -> tuple[tuple[str, float], ...]:
    percentages = dict(request.composition_pct)
    if request.variable_element is not None and concentration_pct is not None:
        percentages[request.variable_element] = concentration_pct
    percentages[request.balance] = 100.0 - sum(percentages.values())
    if percentages[request.balance] <= 0.0:
        raise RestrictedFeError("Point composition has no positive balance.")
    if request.units == "at":
        amounts = {element: value / 100.0 for element, value in percentages.items()}
    else:
        try:
            amounts = {
                element: value / float(database.refstates[element]["mass"])
                for element, value in percentages.items()
            }
        except Exception as error:
            raise RestrictedFeError("Database lacks a pinned composition mass.") from error
    total = sum(amounts.values())
    if not math.isfinite(total) or total <= 0.0:
        raise RestrictedFeError("Atomic conversion has no finite total.")
    atomic = tuple(sorted((element, value / total) for element, value in amounts.items()))
    if not math.isclose(sum(value for _element, value in atomic), 1.0, abs_tol=1e-12):
        raise RestrictedFeError("Atomic composition does not close to one.")
    return atomic


def _validate_runner_result(
    result: object,
    phases: tuple[str, ...],
) -> tuple[tuple[str, float], ...]:
    if type(result) is not dict or not result:
        raise RestrictedFeError("Runner result must be a non-empty plain mapping.")
    values: list[tuple[str, float]] = []
    for phase, raw_value in result.items():
        if type(phase) is not str or phase not in phases or phase == C15_PHASE:
            raise RestrictedFeError("Runner returned a phase outside effective scope.")
        value = _plain_float(raw_value, f"phase_fraction.{phase}")
        if type(raw_value) is not float or value <= 0.0 or value > 1.0 + 1e-8:
            raise RestrictedFeError("Runner returned an invalid phase fraction.")
        values.append((phase, value))
    values.sort()
    if not math.isclose(sum(value for _phase, value in values), 1.0, abs_tol=1e-8):
        raise RestrictedFeError("Runner phase fractions do not close to one.")
    return tuple(values)


def _default_runner(
    database: Database,
    call: RestrictedFeRunnerCall,
) -> Mapping[str, float]:
    import numpy as np
    from pycalphad import equilibrium, variables as v

    atomic = dict(call.atomic_fractions)
    conditions: dict[Any, float] = {
        v.N: 1.0,
        v.P: call.pressure_pa,
        v.T: call.temperature_k,
    }
    conditions.update(
        {
            v.X(element): value
            for element, value in atomic.items()
            if element != call.balance
        }
    )
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
        raise RestrictedFeError("Runner Phase/NP cardinality mismatch.")
    aggregated: dict[str, float] = {}
    for raw_phase, fraction in zip(names, fractions):
        # NumPy exposes fixed-width string array entries as np.str_.  Canonicalize
        # only at this trusted pycalphad adapter boundary; injected runner output
        # remains subject to the exact built-in-type checks below.
        phase = str(raw_phase)
        value = float(fraction)
        if phase:
            if phase == C15_PHASE or phase not in call.phases:
                raise RestrictedFeError(
                    "Runner returned a phase outside effective scope."
                )
            if not math.isfinite(value) or value < 0.0:
                raise RestrictedFeError(
                    "Runner returned an invalid raw phase fraction."
                )
            if value <= 1e-12:
                continue
            aggregated[phase] = aggregated.get(phase, 0.0) + value
            continue
        if math.isnan(value):
            continue
        if not math.isfinite(value) or value < 0.0 or value > 1e-12:
            raise RestrictedFeError("Runner returned invalid unlabeled phase mass.")
    return aggregated


def execute_restricted_fe(
    project_root: str | Path,
    context: RestrictedFeContext,
    request: RestrictedFeRequest,
    *,
    runner: Callable[[Database, RestrictedFeRunnerCall], Mapping[str, float]] | None = None,
) -> RestrictedFeReceipt:
    if type(context) is not RestrictedFeContext or context != restricted_fe_context():
        raise RestrictedFeError("Only the exact restricted Fe context is accepted.")
    if type(request) is not RestrictedFeRequest:
        raise RestrictedFeError("Only a frozen restricted Fe request is accepted.")
    if C15_PHASE in request.requested_phases:
        raise RestrictedFeError("C15_LAVES is disabled before runner dispatch.")
    selected_runner = _default_runner if runner is None else runner
    if not callable(selected_runner):
        raise RestrictedFeError("Restricted Fe runner must be callable.")

    with _open_verified_artifacts(Path(project_root), context) as artifacts:
        # A fresh mutable Database is created for this explicit execution only.
        database = Database.from_file(StringIO(artifacts.database.text), fmt="tdb")
        component_set = {request.balance, *(element for element, _ in request.composition_pct)}
        if request.variable_element is not None:
            component_set.add(request.variable_element)
        components = tuple(sorted(component_set)) + ("VA",)
        candidates = tuple(
            sorted(filter_phases(database, list(components), candidate_phases=None))
        )
        phases = effective_phase_names(candidates, request.requested_phases)
        phases_digest = canonical_digest(list(phases))

        if request.feature_id == "equilibrium_composition_scan":
            specifications = tuple(
                (value, request.temperatures_k[0], value)
                for value in request.concentrations_pct
            )
        else:
            specifications = tuple(
                (temperature, temperature, None)
                for temperature in request.temperatures_k
            )

        points: list[RestrictedFePointReceipt] = []
        attempted_calls = 0
        error_code: str | None = None
        for call_index, (axis_value, temperature_k, concentration) in enumerate(
            specifications, start=1
        ):
            atomic = _point_composition(database, request, concentration)
            call = RestrictedFeRunnerCall(
                feature_id=request.feature_id,
                call_index=call_index,
                axis_value=axis_value,
                temperature_k=temperature_k,
                pressure_pa=request.pressure_pa,
                balance=request.balance,
                components=components,
                atomic_fractions=atomic,
                phases=phases,
            )
            attempted_calls += 1
            try:
                phase_fractions = _validate_runner_result(
                    selected_runner(database, call), phases
                )
            except Exception as error:
                error_code = type(error).__name__
                break
            points.append(
                RestrictedFePointReceipt(
                    call_index=call_index,
                    axis_value=axis_value,
                    temperature_k=temperature_k,
                    pressure_pa=request.pressure_pa,
                    atomic_fractions=atomic,
                    phase_fractions=phase_fractions,
                )
            )

    expected_calls = 1 if request.feature_id == "equilibrium_single" else 3
    outcome = (
        "success"
        if error_code is None
        and attempted_calls == expected_calls
        and len(points) == expected_calls
        else "failure"
    )
    return RestrictedFeReceipt(
        schema="thermogar.restricted_fe.receipt.v2",
        feature_id=request.feature_id,
        context_digest=context_digest(context),
        request_digest=request_digest(request),
        ordered_phases=phases,
        ordered_phases_digest=phases_digest,
        source_hashes=(
            ("database_sha256", context.database_sha256),
            ("passport_sha256", context.passport_sha256),
        ),
        calls=attempted_calls,
        points=tuple(points),
        outcome=outcome,
        error_code=error_code,
        material_base="STEEL",
        experimental_qualification="NOT_PERFORMED",
    )


def receipt_as_dict(receipt: RestrictedFeReceipt) -> dict[str, Any]:
    if type(receipt) is not RestrictedFeReceipt:
        raise RestrictedFeError("Receipt must be the frozen restricted Fe type.")
    return asdict(receipt)


_BOUND_INPUT_FIELDS = (
    "balance",
    "units",
    "composition_pct",
    "pressure_pa",
    "temperatures_k",
    "requested_phases",
    "variable_element",
    "concentrations_pct",
)


def restricted_fe_request_inputs(request: RestrictedFeRequest) -> dict[str, Any]:
    """Return the exact path-free B1 input object for a frozen Core1 request."""

    if type(request) is not RestrictedFeRequest:
        raise RestrictedFeError("Only a frozen restricted Fe request is accepted.")
    return {
        "balance": request.balance,
        "units": request.units,
        "composition_pct": [list(item) for item in request.composition_pct],
        "pressure_pa": request.pressure_pa,
        "temperatures_k": list(request.temperatures_k),
        "requested_phases": list(request.requested_phases),
        "variable_element": request.variable_element,
        "concentrations_pct": list(request.concentrations_pct),
    }


def restricted_fe_request_from_inputs(
    feature_id: str,
    inputs: Mapping[str, Any],
) -> RestrictedFeRequest:
    """Reconstruct Core1 only when the B1 input object is exact and canonical."""

    if type(inputs) is not dict or set(inputs) != set(_BOUND_INPUT_FIELDS):
        raise RestrictedFeError("Bound Core1 input fields/order mismatch.")
    composition = inputs["composition_pct"]
    if type(composition) is not list or any(
        type(item) is not list or len(item) != 2 for item in composition
    ):
        raise RestrictedFeError("Bound Core1 composition pairs are invalid.")
    temperatures = inputs["temperatures_k"]
    requested = inputs["requested_phases"]
    concentrations = inputs["concentrations_pct"]
    if (
        type(temperatures) is not list
        or type(requested) is not list
        or type(concentrations) is not list
    ):
        raise RestrictedFeError("Bound Core1 ordered axes are invalid.")
    try:
        request = make_restricted_fe_request(
            feature_id,
            balance=inputs["balance"],
            units=inputs["units"],
            composition_pct={item[0]: item[1] for item in composition},
            pressure_pa=inputs["pressure_pa"],
            temperatures_k=temperatures,
            requested_phases=requested,
            variable_element=inputs["variable_element"],
            concentrations_pct=concentrations,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise RestrictedFeError("Bound Core1 inputs cannot be reconstructed.") from error
    if restricted_fe_request_inputs(request) != inputs:
        raise RestrictedFeError("Bound Core1 input reconstruction mismatch.")
    return request


def prepare_bound_restricted_fe_request(
    context: verified_loaders.BoundDatabaseContext,
    request: RestrictedFeRequest,
    candidate_phases: tuple[str, ...],
    *,
    clock: Callable[[], object] | None = None,
) -> verified_loaders.FeatureRequest | verified_loaders.RejectedFeatureReceipt:
    """Prepare the B1 capability decision for one exact Core1 request."""

    kwargs: dict[str, Any] = {"candidate_phases": candidate_phases}
    if clock is not None:
        kwargs["clock"] = clock
    return verified_loaders.prepare_feature_request(
        request.feature_id,
        context,
        restricted_fe_request_inputs(request),
        request.requested_phases,
        **kwargs,
    )


@dataclass(frozen=True, slots=True)
class BoundRestrictedFeResult:
    core1_receipt: RestrictedFeReceipt
    feature_receipt: verified_loaders.FeatureReceipt
    result_envelope: verified_loaders.ResultEnvelope | None

    def __post_init__(self) -> None:
        if type(self.core1_receipt) is not RestrictedFeReceipt:
            raise RestrictedFeError("Bound Core1 receipt type mismatch.")
        if type(self.feature_receipt) is not verified_loaders.FeatureReceipt:
            raise RestrictedFeError("Bound feature receipt type mismatch.")
        if self.core1_receipt.outcome == "success":
            if type(self.result_envelope) is not verified_loaders.ResultEnvelope:
                raise RestrictedFeError("Successful bound Core1 result lacks an envelope.")
        elif self.result_envelope is not None:
            raise RestrictedFeError("Failed bound Core1 result cannot expose an envelope.")


def _utc_timestamp(clock: Callable[[], object]) -> str:
    value = clock()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise RestrictedFeError("Bound Core1 clock must be UTC-aware.")
        value = value.astimezone(timezone.utc).isoformat(timespec="microseconds")
        return value.replace("+00:00", "Z")
    if type(value) is str:
        return value
    raise RestrictedFeError("Bound Core1 clock returned an invalid value.")


def _system_utc() -> datetime:
    return datetime.now(timezone.utc)


def _core1_receipt_plain(receipt: RestrictedFeReceipt) -> dict[str, Any]:
    return json.loads(_canonical_bytes(receipt_as_dict(receipt)).decode("utf-8"))


def execute_bound_restricted_fe(
    context: verified_loaders.BoundDatabaseContext,
    feature_request: verified_loaders.FeatureRequest,
    request: RestrictedFeRequest,
    lease: verified_loaders.ExecutionLease,
    *,
    runner: Callable[[Database, RestrictedFeRunnerCall], Mapping[str, float]],
    clock: Callable[[], object] = _system_utc,
) -> BoundRestrictedFeResult:
    """Execute Core1 through one current B1 lease and a fresh verified parser."""

    if type(context) is not verified_loaders.BoundDatabaseContext or (
        context.database_key != DATABASE_KEY
        or context.profile_key != PROFILE_KEY
        or context.patch_id != PATCH_ID
        or context.tdb.sha256 != DATABASE_SHA256
        or context.passport is None
        or context.passport.sha256 != PASSPORT_SHA256
        or context.physical_pdb is not None
    ):
        raise RestrictedFeError("Bound Core1 requires the exact Fe context.")
    if type(feature_request) is not verified_loaders.FeatureRequest:
        raise RestrictedFeError("Bound Core1 requires a frozen FeatureRequest.")
    if type(request) is not RestrictedFeRequest or request.feature_id != feature_request.feature_id:
        raise RestrictedFeError("Bound Core1 feature identity mismatch.")
    if type(lease) is not verified_loaders.ExecutionLease or lease.request != feature_request:
        raise RestrictedFeError("Bound Core1 lease/request identity mismatch.")
    if feature_request.binding_digest != context.binding_digest or (
        feature_request.binding_generation != context.binding_generation
    ):
        raise RestrictedFeError("Bound Core1 context/request identity mismatch.")
    if restricted_fe_request_from_inputs(
        feature_request.feature_id,
        feature_request.inputs,
    ) != request:
        raise RestrictedFeError("Bound Core1 request reconstruction mismatch.")
    if feature_request.requested_phases != request.requested_phases:
        raise RestrictedFeError("Bound Core1 requested phase identity mismatch.")
    phases = effective_phase_names(
        feature_request.effective_phases,
        request.requested_phases,
    )
    if phases != feature_request.effective_phases:
        raise RestrictedFeError("Bound Core1 effective phase identity mismatch.")
    if not callable(runner):
        raise RestrictedFeError("Bound Core1 runner seam must be callable.")

    started_at = lease.identity.acquired_at_utc
    parser = partial(Database.from_file, fmt="tdb")
    database = lease.parse_tdb(
        parser=parser,
        parser_revision="pycalphad-0.11.2",
        fresh=True,
    )
    component_set = {
        request.balance,
        *(element for element, _value in request.composition_pct),
    }
    if request.variable_element is not None:
        component_set.add(request.variable_element)
    components = tuple(sorted(component_set)) + ("VA",)
    phases_digest = canonical_digest(list(phases))

    if request.feature_id == "equilibrium_composition_scan":
        specifications = tuple(
            (value, request.temperatures_k[0], value)
            for value in request.concentrations_pct
        )
    else:
        specifications = tuple(
            (temperature, temperature, None)
            for temperature in request.temperatures_k
        )

    points: list[RestrictedFePointReceipt] = []
    attempted_calls = 0
    error_code: str | None = None
    for call_index, (axis_value, temperature_k, concentration) in enumerate(
        specifications,
        start=1,
    ):
        atomic = _point_composition(database, request, concentration)
        call = RestrictedFeRunnerCall(
            feature_id=request.feature_id,
            call_index=call_index,
            axis_value=axis_value,
            temperature_k=temperature_k,
            pressure_pa=request.pressure_pa,
            balance=request.balance,
            components=components,
            atomic_fractions=atomic,
            phases=phases,
        )
        attempted_calls += 1
        try:
            raw_result = lease.invoke_backend(
                lambda _live_lease, current_call=call: runner(
                    database,
                    current_call,
                )
            )
            phase_fractions = _validate_runner_result(raw_result, phases)
        except Exception as error:
            error_code = type(error).__name__
            break
        points.append(
            RestrictedFePointReceipt(
                call_index=call_index,
                axis_value=axis_value,
                temperature_k=temperature_k,
                pressure_pa=request.pressure_pa,
                atomic_fractions=atomic,
                phase_fractions=phase_fractions,
            )
        )

    expected_calls = 1 if request.feature_id == "equilibrium_single" else 3
    outcome = (
        "success"
        if error_code is None
        and attempted_calls == expected_calls
        and len(points) == expected_calls
        else "failure"
    )
    core1_receipt = RestrictedFeReceipt(
        schema="thermogar.restricted_fe.receipt.v2",
        feature_id=request.feature_id,
        context_digest=context_digest(restricted_fe_context()),
        request_digest=request_digest(request),
        ordered_phases=phases,
        ordered_phases_digest=phases_digest,
        source_hashes=(
            ("database_sha256", context.tdb.sha256),
            ("passport_sha256", context.passport.sha256),
        ),
        calls=attempted_calls,
        points=tuple(points),
        outcome=outcome,
        error_code=error_code,
        material_base="STEEL",
        experimental_qualification="NOT_PERFORMED",
    )
    bridge = verified_loaders.verified_core1_v2_evidence_bridge(
        _core1_receipt_plain(core1_receipt),
        context,
        feature_request,
    )
    settings = {"verified_core1_v2_evidence": bridge}
    finished_at = _utc_timestamp(clock)
    backend = {
        "adapter_id": "thermogar.restricted-fe-bound",
        "adapter_revision": "1",
        "backend_id": "pycalphad-equilibrium",
        "backend_version": "0.11.2",
    }
    packages = [
        {"name": "pycalphad", "version": "0.11.2", "status": "available"}
    ]
    result_envelope: verified_loaders.ResultEnvelope | None = None
    if outcome == "success":
        result_digest = verified_loaders.canonical_digest(
            {
                "settings_digest": verified_loaders.canonical_digest(settings),
                "tables_digest": verified_loaders.canonical_digest([]),
                "figures_digest": verified_loaders.canonical_digest([]),
                "artifacts_digest": verified_loaders.canonical_digest([]),
            }
        )
        feature_receipt = verified_loaders.make_feature_receipt(
            context,
            feature_request,
            lease,
            outcome="success",
            reason_code=None,
            reason_detail=None,
            backend=backend,
            packages=packages,
            point_count=len(points),
            result_digest=result_digest,
            started_at_utc=started_at,
            finished_at_utc=finished_at,
        )
        result_envelope = verified_loaders.make_result_envelope(
            context,
            feature_request,
            feature_receipt,
            settings=settings,
            clock=lambda: finished_at,
        )
    else:
        feature_receipt = verified_loaders.make_feature_receipt(
            context,
            feature_request,
            lease,
            outcome="failure",
            reason_code=verified_loaders.ReasonCode.BACKEND_FAILED,
            reason_detail=error_code or "Restricted Fe execution failed.",
            backend=backend,
            packages=packages,
            point_count=len(points),
            result_digest=None,
            started_at_utc=started_at,
            finished_at_utc=finished_at,
        )
    return BoundRestrictedFeResult(
        core1_receipt=core1_receipt,
        feature_receipt=feature_receipt,
        result_envelope=result_envelope,
    )
