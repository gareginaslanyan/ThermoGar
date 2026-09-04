"""Verified, path-free B4B1 physical-property execution boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import re
from typing import Any, Callable, Mapping, Sequence

import thermogar_physical as physical
import thermogar_verified_loaders as verified_loaders


PHYSICAL_FEATURE_IDS = (
    "property_density_single",
    "property_density_temperature",
    "property_pdb_self_test",
    "property_coverage_view",
)
PARSER_REVISION = "pycalphad-0.11.2"
PDB_PARSER_REVISION = "thermogar-physical-pdb-1"
ADAPTER_ID = "thermogar.verified-physical"
ADAPTER_REVISION = "1"
BACKEND_ID = "pycalphad-equilibrium-physical"
BACKEND_VERSION = "0.11.2"
_ELEMENT_RE = re.compile(r"[A-Z][A-Z0-9]{0,2}")
_C15 = "C15_LAVES"


@dataclass(frozen=True, slots=True)
class PhysicalCall:
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
class PhysicalPoint:
    call_index: int
    axis_value: float | None
    projection: dict[str, Any]


@dataclass(frozen=True, slots=True)
class VerifiedPhysicalResult:
    points: tuple[PhysicalPoint, ...]
    feature_receipt: verified_loaders.FeatureReceipt
    result_envelope: verified_loaders.ResultEnvelope


def _fail(reason: verified_loaders.ReasonCode, detail: str) -> None:
    raise verified_loaders.VerifiedLoaderError(reason, detail)


def _plain_float(value: object, label: str, *, positive: bool = False) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} must be a finite number.")
    result = float(value)
    if not math.isfinite(result) or result < 0.0 or (positive and result <= 0.0):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} is outside the accepted range.")
    return result


def _element(value: object, label: str) -> str:
    if type(value) is not str or _ELEMENT_RE.fullmatch(value) is None:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} must be a canonical element token.")
    return value


def make_physical_inputs(
    feature_id: str,
    *,
    balance: str | None = None,
    units: str | None = None,
    composition_pct: Mapping[str, object] | None = None,
    pressure_pa: object | None = None,
    temperatures_k: Sequence[object] = (),
) -> dict[str, Any]:
    """Build the closed scalar input object for one B4B1 feature."""

    if feature_id not in PHYSICAL_FEATURE_IDS:
        _fail(verified_loaders.ReasonCode.FEATURE_ID_UNKNOWN, "Feature is outside B4B1.")
    if feature_id in ("property_pdb_self_test", "property_coverage_view"):
        if any(value is not None for value in (balance, units, composition_pct, pressure_pa)) or temperatures_k:
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Parse-only feature takes no calculation inputs.")
        return {"operation": feature_id}

    canonical_balance = _element(balance, "balance")
    if units not in ("wt", "at"):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Composition units must be wt or at.")
    if type(composition_pct) is not dict:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "composition_pct must be a plain object.")
    composition: list[tuple[str, float]] = []
    for raw_element, raw_value in composition_pct.items():
        element = _element(raw_element, "composition element")
        if element == canonical_balance:
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Balance must not be repeated in composition_pct.")
        composition.append((element, _plain_float(raw_value, f"composition_pct.{element}")))
    composition.sort()
    if len({element for element, _value in composition}) != len(composition):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Composition elements must be unique.")
    if sum(value for _element_name, value in composition) >= 100.0:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Composition leaves no positive balance fraction.")
    if isinstance(temperatures_k, (str, bytes)):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "temperatures_k must be an ordered sequence.")
    temperatures = tuple(
        _plain_float(value, f"temperatures_k[{index}]", positive=True)
        for index, value in enumerate(temperatures_k)
    )
    if feature_id == "property_density_single" and len(temperatures) != 1:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Density single requires exactly one temperature.")
    if feature_id == "property_density_temperature":
        if not temperatures or len(temperatures) > 100:
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Density scan requires between 1 and 100 points.")
        if any(right <= left for left, right in zip(temperatures, temperatures[1:])):
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Density temperatures must be strictly ascending.")
    return {
        "balance": canonical_balance,
        "composition_pct": [[element, value] for element, value in composition],
        "pressure_pa": _plain_float(pressure_pa, "pressure_pa", positive=True),
        "temperatures_k": list(temperatures),
        "units": units,
    }


def _inputs_from_request(request: verified_loaders.FeatureRequest) -> dict[str, Any]:
    if type(request) is not verified_loaders.FeatureRequest:
        _fail(verified_loaders.ReasonCode.REQUEST_DIGEST_MISMATCH, "Adapter requires a frozen FeatureRequest.")
    raw = request.inputs
    try:
        if request.feature_id in ("property_pdb_self_test", "property_coverage_view"):
            rebuilt = make_physical_inputs(request.feature_id)
        else:
            pairs = raw["composition_pct"]
            if type(pairs) is not list:
                raise TypeError
            composition = {
                item[0]: item[1]
                for item in pairs
                if type(item) is list and len(item) == 2
            }
            rebuilt = make_physical_inputs(
                request.feature_id,
                balance=raw["balance"],
                units=raw["units"],
                composition_pct=composition,
                pressure_pa=raw["pressure_pa"],
                temperatures_k=raw["temperatures_k"],
            )
    except (KeyError, TypeError, IndexError):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Physical request input shape is invalid.")
    if rebuilt != raw:
        _fail(verified_loaders.ReasonCode.REQUEST_DIGEST_MISMATCH, "Physical request inputs are not canonical.")
    return rebuilt


def _default_tdb_parser(source: object) -> object:
    from pycalphad import Database

    return Database.from_file(source, fmt="tdb")


def _default_pdb_parser(data: bytes) -> physical.PhysicalDensityDatabase:
    return physical.PhysicalDensityDatabase.from_verified_bytes(data)


def _database_masses(database: object, components: Sequence[str]) -> dict[str, float]:
    refstates = getattr(database, "refstates", None)
    if not isinstance(refstates, Mapping):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Parsed database lacks reference-state masses.")
    result: dict[str, float] = {}
    for component in components:
        record = refstates.get(component)
        mass = record.get("mass") if isinstance(record, Mapping) else None
        if type(mass) not in (int, float) or not math.isfinite(float(mass)) or float(mass) <= 0.0:
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, f"Missing atomic mass for {component}.")
        result[component] = float(mass)
    return result


def _fractions(database: object, inputs: Mapping[str, Any]) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, float], ...]]:
    balance = inputs["balance"]
    composition = {element: float(value) for element, value in inputs["composition_pct"]}
    composition[balance] = 100.0 - sum(composition.values())
    ordered = tuple(sorted(composition))
    masses = _database_masses(database, ordered)
    if inputs["units"] == "wt":
        mass = {element: composition[element] / 100.0 for element in ordered}
        unscaled = {element: mass[element] / masses[element] for element in ordered}
        total = sum(unscaled.values())
        atomic = {element: unscaled[element] / total for element in ordered}
    else:
        atomic = {element: composition[element] / 100.0 for element in ordered}
        unscaled = {element: atomic[element] * masses[element] for element in ordered}
        total = sum(unscaled.values())
        mass = {element: unscaled[element] / total for element in ordered}
    return (
        tuple((element, float(atomic[element])) for element in ordered),
        tuple((element, float(mass[element])) for element in ordered),
    )


def _plain_cell(value: object) -> object:
    if value is None or type(value) in (str, bool, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "item"):
        return _plain_cell(value.item())
    return str(value)


def _rows(frame: object) -> list[dict[str, object]]:
    records = getattr(frame, "to_dict")(orient="records")
    return [
        {str(key): _plain_cell(value) for key, value in record.items()}
        for record in records
    ]


def _physical_projection(result: physical.PhysicalCalculationResult) -> dict[str, Any]:
    return {
        "alloy_density_g_cm3": _plain_cell(result.alloy_density_g_cm3),
        "alloy_density_kg_m3": _plain_cell(result.alloy_density_kg_m3),
        "direct_mole_pct": float(result.direct_mole_pct),
        "inherited_mole_pct": float(result.inherited_mole_pct),
        "mass_coverage_pct": float(result.mass_coverage_pct),
        "missing_rows": _rows(result.missing_table),
        "mole_coverage_pct": float(result.mole_coverage_pct),
        "phase_rows": _rows(result.phase_table),
        "physical_database_sha256": result.physical_database_sha256,
        "physical_database_version": result.physical_database_version,
        "quality_label": result.quality_label,
        "warnings": [str(value) for value in result.warnings],
    }


def _default_backend(
    database: object,
    physical_database: physical.PhysicalDensityDatabase,
    call: PhysicalCall,
) -> Mapping[str, object]:
    from pycalphad import equilibrium, variables as v

    conditions: dict[Any, float] = {
        v.N: 1.0,
        v.P: call.pressure_pa,
        v.T: call.temperature_k,
    }
    conditions.update(
        {
            v.X(element): value
            for element, value in call.atomic_fractions
            if element != call.balance
        }
    )
    equilibrium_result = equilibrium(
        database,
        list(call.components),
        list(call.phases),
        conditions,
        calc_opts={"pdens": 500},
    )
    result = physical.calculate_physical_properties(
        database,
        equilibrium_result,
        list(call.components),
        call.temperature_k,
        physical_database,
    )
    return _physical_projection(result)


def composition_fractions(
    database: object,
    inputs: Mapping[str, Any],
) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, float], ...]]:
    """Атомные и массовые доли состава — те же, что у verified-маршрута.

    Многоточечный расчёт плотности идёт мимо лизы (лиза сериализует бэкенд
    по одному вызову), но состав и набор фаз обязан брать теми же функциями,
    иначе точка и скан разойдутся.
    """
    return _fractions(database, inputs)


def effective_phases(
    context: verified_loaders.BoundDatabaseContext,
    requested_phases: Sequence[str],
    database: object,
) -> tuple[str, ...]:
    """Список фаз политики привязки для уже разобранной базы."""
    phases = getattr(database, "phases", None)
    if not isinstance(phases, Mapping):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Parsed database lacks a phase catalog.")
    candidates = tuple(
        sorted(
            phase
            for phase in phases
            if type(phase) is str
            and phase
            and phase not in context.phase_policy.explicit_rejections
        )
    )
    return context.phase_policy.effective(tuple(requested_phases), candidates=candidates)


def physical_projection(result: physical.PhysicalCalculationResult) -> dict[str, Any]:
    """Плоская проекция результата расчёта плотности."""
    return _physical_projection(result)


def _canonical_projection(value: object) -> dict[str, Any]:
    if type(value) is not dict or not value:
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Physical result must be a non-empty plain object.")
    forbidden = {"path", "filename", "database", "bytes", "session", "materializer"}
    for node in value:
        if type(node) is not str or node.casefold() in forbidden:
            _fail(verified_loaders.ReasonCode.RAW_PATH_REJECTED, "Physical result exposes authority.")
    try:
        return json.loads(verified_loaders.canonical_json_bytes(value).decode("utf-8"))
    except verified_loaders.VerifiedLoaderError:
        raise
    except Exception as error:
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, f"Physical result is not canonical: {type(error).__name__}.")
    raise AssertionError


def _validate_density_projection(value: object) -> dict[str, Any]:
    fields = (
        "alloy_density_g_cm3",
        "alloy_density_kg_m3",
        "direct_mole_pct",
        "inherited_mole_pct",
        "mass_coverage_pct",
        "missing_rows",
        "mole_coverage_pct",
        "phase_rows",
        "physical_database_sha256",
        "physical_database_version",
        "quality_label",
        "warnings",
    )
    if type(value) is not dict or tuple(value) != fields:
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Density backend returned an invalid projection shape.")
    for label in (
        "alloy_density_g_cm3",
        "alloy_density_kg_m3",
        "direct_mole_pct",
        "inherited_mole_pct",
        "mass_coverage_pct",
        "mole_coverage_pct",
    ):
        item = value[label]
        if item is not None and (type(item) is not float or not math.isfinite(item)):
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, f"Density backend {label} is invalid.")
    if type(value["physical_database_sha256"]) is not str or re.fullmatch(r"[0-9a-f]{64}", value["physical_database_sha256"]) is None:
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Density backend PDB digest is invalid.")
    if any(type(value[label]) is not str or not value[label] for label in ("physical_database_version", "quality_label")):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Density backend labels are invalid.")
    if type(value["phase_rows"]) is not list or type(value["missing_rows"]) is not list:
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Density backend rows are invalid.")
    if type(value["warnings"]) is not list or any(type(item) is not str for item in value["warnings"]):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Density backend warnings are invalid.")
    return _canonical_projection(value)


def _phase_identity(
    context: verified_loaders.BoundDatabaseContext,
    request: verified_loaders.FeatureRequest,
    database: object,
) -> tuple[str, ...]:
    if _C15 in request.requested_phases or _C15 in request.effective_phases:
        _fail(verified_loaders.ReasonCode.C15_PHASE_REJECTED, "C15_LAVES is rejected before physical parsing or dispatch.")
    phases = getattr(database, "phases", None)
    if not isinstance(phases, Mapping):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Parsed database lacks a phase catalog.")
    candidates = tuple(
        sorted(
            phase
            for phase in phases
            if type(phase) is str
            and phase
            and phase not in context.phase_policy.explicit_rejections
        )
    )
    live = context.phase_policy.effective(request.requested_phases, candidates=candidates)
    if request.requested_phases:
        matches = live == request.effective_phases
    else:
        order = {phase: index for index, phase in enumerate(live)}
        matches = (
            bool(request.effective_phases)
            and all(phase in order for phase in request.effective_phases)
            and tuple(sorted(request.effective_phases, key=order.__getitem__))
            == request.effective_phases
        )
    if not matches:
        _fail(verified_loaders.ReasonCode.PHASE_POLICY_MISMATCH, "Live phase policy does not match the request.")
    return request.effective_phases


def _utc(clock: Callable[[], object]) -> str:
    value = clock()
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if type(value) is str and value.endswith("Z"):
        return value
    _fail(verified_loaders.ReasonCode.SCHEMA_INVALID, "Adapter clock returned an invalid value.")
    raise AssertionError


def _system_utc() -> datetime:
    return datetime.now(timezone.utc)


def execute_verified_physical(
    context: verified_loaders.BoundDatabaseContext,
    feature_request: verified_loaders.FeatureRequest,
    lease: verified_loaders.ExecutionLease,
    *,
    tdb_parser: Callable[[object], object] = _default_tdb_parser,
    backend: Callable[[object, physical.PhysicalDensityDatabase, PhysicalCall], Mapping[str, object]] = _default_backend,
    clock: Callable[[], object] = _system_utc,
    packages: Sequence[Mapping[str, str]] = (),
) -> VerifiedPhysicalResult:
    """Execute one B4B1 request only through its live verified capability."""

    if type(context) is not verified_loaders.BoundDatabaseContext:
        _fail(verified_loaders.ReasonCode.BINDING_IDENTITY_MISMATCH, "Physical adapter requires a bound context.")
    if context.database_key not in ("ni", "al", "fe") or context.physical_pdb is None:
        _fail(verified_loaders.ReasonCode.DATA_UNAVAILABLE, "Canonical TDB and physical PDB must both be bound.")
    if context.database_key == "fe" and context.profile_key != "thermogar_patch":
        _fail(verified_loaders.ReasonCode.UPSTREAM_PROFILE_REJECTED, "Fe physical execution requires thermogar_patch.")
    if type(feature_request) is not verified_loaders.FeatureRequest or feature_request.feature_id not in PHYSICAL_FEATURE_IDS:
        _fail(verified_loaders.ReasonCode.FEATURE_ID_UNKNOWN, "Request is outside B4B1.")
    if type(lease) is not verified_loaders.ExecutionLease or lease.request != feature_request:
        _fail(verified_loaders.ReasonCode.LEASE_IDENTITY_MISMATCH, "Physical adapter requires the matching live lease.")
    if (
        feature_request.binding_digest != context.binding_digest
        or feature_request.binding_generation != context.binding_generation
    ):
        _fail(verified_loaders.ReasonCode.BINDING_IDENTITY_MISMATCH, "Context/request identity mismatch.")
    if _C15 in feature_request.requested_phases or _C15 in feature_request.effective_phases:
        _fail(verified_loaders.ReasonCode.C15_PHASE_REJECTED, "C15_LAVES is rejected before lease parsing or dispatch.")
    if not callable(tdb_parser) or not callable(backend):
        _fail(verified_loaders.ReasonCode.PACKAGE_UNAVAILABLE, "Physical parser/backend seam is unavailable.")

    inputs = _inputs_from_request(feature_request)
    started_at = lease.identity.acquired_at_utc
    physical_database: physical.PhysicalDensityDatabase
    try:
        physical_database = lease.parse_physical_dataset(
            _default_pdb_parser,
            PDB_PARSER_REVISION,
        )
    except verified_loaders.VerifiedLoaderError:
        raise
    except Exception as error:
        _fail(verified_loaders.ReasonCode.PDB_INVALID, f"Physical PDB parse failed: {type(error).__name__}.")

    database: object | None = None
    phases = feature_request.effective_phases
    if feature_request.feature_id != "property_pdb_self_test":
        try:
            database = lease.parse_tdb(
                parser=tdb_parser,
                parser_revision=PARSER_REVISION,
                fresh=True,
            )
        except verified_loaders.VerifiedLoaderError:
            raise
        except Exception as error:
            _fail(verified_loaders.ReasonCode.PACKAGE_UNAVAILABLE, f"TDB parse failed: {type(error).__name__}.")
        phases = _phase_identity(context, feature_request, database)

    points: list[PhysicalPoint] = []
    if feature_request.feature_id == "property_pdb_self_test":
        projection = {"rows": _rows(physical_database.self_test())}
        points.append(PhysicalPoint(1, None, _canonical_projection(projection)))
    elif feature_request.feature_id == "property_coverage_view":
        assert database is not None
        coverage_rows = _rows(
            physical.physical_coverage_dataframe(
                database,
                physical_database,
                {},
            )
        )
        projection = {
            "rows": [
                row
                for row in coverage_rows
                if row.get("Фаза") != _C15
            ]
        }
        points.append(PhysicalPoint(1, None, _canonical_projection(projection)))
    else:
        assert database is not None
        atomic, mass = _fractions(database, inputs)
        components = tuple(element for element, _value in atomic) + ("VA",)
        for index, temperature in enumerate(inputs["temperatures_k"], start=1):
            call = PhysicalCall(
                feature_id=feature_request.feature_id,
                call_index=index,
                axis_value=float(temperature),
                temperature_k=float(temperature),
                pressure_pa=float(inputs["pressure_pa"]),
                balance=inputs["balance"],
                components=components,
                atomic_fractions=atomic,
                mass_fractions=mass,
                phases=phases,
            )
            try:
                raw = lease.invoke_backend(
                    lambda _live, current=call: backend(
                        database,
                        physical_database,
                        current,
                    )
                )
            except verified_loaders.VerifiedLoaderError:
                raise
            except Exception as error:
                _fail(verified_loaders.ReasonCode.BACKEND_FAILED, type(error).__name__)
            projection = _validate_density_projection(raw)
            projection["temperature_k"] = float(temperature)
            points.append(
                PhysicalPoint(
                    call_index=index,
                    axis_value=float(temperature),
                    projection=_canonical_projection(projection),
                )
            )

    settings = {
        "experimental_qualification": "NOT_PERFORMED" if context.database_key == "fe" else None,
        "physical_pdb_sha256": context.physical_pdb.sha256,
        "points": [
            {
                "axis_value": point.axis_value,
                "call_index": point.call_index,
                "projection": point.projection,
            }
            for point in points
        ],
    }
    result_digest = verified_loaders.canonical_digest(
        {
            "settings_digest": verified_loaders.canonical_digest(settings),
            "tables_digest": verified_loaders.canonical_digest([]),
            "figures_digest": verified_loaders.canonical_digest([]),
            "artifacts_digest": verified_loaders.canonical_digest([]),
        }
    )
    finished_at = _utc(clock)
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
        packages=packages,
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
    return VerifiedPhysicalResult(tuple(points), receipt, envelope)


__all__ = (
    "ADAPTER_ID",
    "PHYSICAL_FEATURE_IDS",
    "PhysicalCall",
    "PhysicalPoint",
    "VerifiedPhysicalResult",
    "composition_fractions",
    "effective_phases",
    "execute_verified_physical",
    "make_physical_inputs",
    "physical_projection",
)
