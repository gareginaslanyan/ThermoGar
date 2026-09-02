"""Verified B4B2 elastic-property and strengthening execution boundary.

The adapter accepts only the already-bound physical context, its canonical
feature request and a matching live execution lease.  Repository authority is
an injected ``ThermoGarPaths`` object and never crosses the result boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any, Callable, Mapping, Sequence

import thermogar_physical as physical
import thermogar_properties as properties
from thermogar_paths import ThermoGarPaths
from thermogar_secure_io import (
    SecureIOError,
    atomic_update_bytes,
    ensure_plain_directory,
    read_verified_snapshot,
)
from thermogar_verified_artifact import duplicate_reject_json
import thermogar_verified_loaders as verified_loaders


PROPERTY_FEATURE_IDS = (
    "property_elastic_prepare",
    "property_elastic_vrh",
    "property_strengthening",
)
PREPARE_INPUT_FIELDS = (
    "balance",
    "composition_pct",
    "pressure_pa",
    "temperatures_k",
    "units",
)
VRH_INPUT_FIELDS = (
    "prepared_witness_digest",
    "library_snapshot_digest",
    "library_update",
    "phase_rows",
)
VRH_ROW_FIELDS = (
    "phase",
    "volume_fraction",
    "young_gpa",
    "poisson",
    "origin",
    "source",
    "reference_temperature_c",
    "note",
)
STRENGTHENING_INPUT_FIELDS = (
    "input_provenance",
    "input_confirmation",
    "sigma_internal_mpa",
    "hall_petch",
    "taylor",
    "solid_solution_mpa",
    "orowan",
    "other_mpa",
    "summation_rule",
    "hill_witness_digest",
)
HALL_PETCH_FIELDS = ("k_y_mpa_sqrt_m", "grain_size_um")
TAYLOR_FIELDS = (
    "taylor_factor",
    "alpha",
    "shear_gpa",
    "burgers_nm",
    "dislocation_density_m2",
)
OROWAN_FIELDS = (
    "taylor_factor",
    "shear_gpa",
    "burgers_nm",
    "poisson",
    "particle_radius_nm",
    "spacing_nm",
)
ADAPTER_ID = "thermogar.verified-properties"
ADAPTER_REVISION = "1"
PARSER_REVISION = "pycalphad-0.11.2"
PDB_PARSER_REVISION = "thermogar-physical-pdb-1"
MAX_LIBRARY_BYTES = 8_388_608
MAX_LIBRARY_ENTRIES = 512
C15_PHASE = "C15_LAVES"
_ELEMENT_RE = re.compile(r"[A-Z][A-Z0-9]{0,2}")
_SHA_RE = re.compile(r"[0-9a-f]{64}")
_EMPTY_LIBRARY = {"schema_version": 1, "updated_at": None, "entries": {}}


@dataclass(frozen=True, slots=True)
class PropertyPrepareCall:
    temperature_k: float
    pressure_pa: float
    balance: str
    components: tuple[str, ...]
    atomic_fractions: tuple[tuple[str, float], ...]
    phases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PropertyLibraryView:
    library_snapshot_digest: str
    phase_rows: tuple[dict[str, Any], ...]
    updated_at: str | None


@dataclass(frozen=True, slots=True)
class VerifiedPropertiesResult:
    projection: dict[str, Any]
    feature_receipt: verified_loaders.FeatureReceipt
    result_envelope: verified_loaders.ResultEnvelope
    prepared_witness_digest: str | None = None
    hill_witness_digest: str | None = None


@dataclass(frozen=True, slots=True)
class _PreparedWitness:
    binding_digest: str
    binding_generation: int
    request_digest: str
    receipt_digest: str
    envelope_digest: str
    tdb_sha256: str
    physical_pdb_sha256: str
    phase_rows: tuple[tuple[str, float], ...]
    witness_digest: str


@dataclass(frozen=True, slots=True)
class _HillWitness:
    binding_digest: str
    binding_generation: int
    request_digest: str
    receipt_digest: str
    envelope_digest: str
    bulk_gpa: float
    shear_gpa: float
    young_gpa: float
    poisson: float
    witness_digest: str


_PREPARED_WITNESSES: dict[str, _PreparedWitness] = {}
_HILL_WITNESSES: dict[str, _HillWitness] = {}


def _fail(reason: verified_loaders.ReasonCode, detail: str) -> None:
    raise verified_loaders.VerifiedLoaderError(reason, detail)


def clear_property_witnesses() -> None:
    """Clear only process-local B4B2 evidence after binding invalidation."""

    _PREPARED_WITNESSES.clear()
    _HILL_WITNESSES.clear()


def _plain_float(
    value: object,
    label: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    minimum_inclusive: bool = True,
) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} must be a finite number.")
    result = float(value)
    if not math.isfinite(result):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} must be finite.")
    if minimum is not None and (
        result < minimum if minimum_inclusive else result <= minimum
    ):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} is below its accepted domain.")
    if maximum is not None and result > maximum:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} is above its accepted domain.")
    return result


def _element(value: object, label: str) -> str:
    if type(value) is not str or _ELEMENT_RE.fullmatch(value) is None:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} must be a canonical element token.")
    return value


def _exact_dict(value: object, fields: Sequence[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(fields) or len(value) != len(fields):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} fields are invalid.")
    return value


def _digest(value: object, label: str) -> str:
    if type(value) is not str or _SHA_RE.fullmatch(value) is None:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} must be lowercase SHA-256.")
    return value


def _trimmed(
    value: object,
    label: str,
    *,
    maximum: int,
    allow_empty: bool = False,
) -> str:
    if type(value) is not str or value != value.strip() or len(value) > maximum:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} is invalid.")
    if not allow_empty and not value:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"{label} must not be empty.")
    return value


def make_prepare_inputs(
    *,
    balance: object,
    composition_pct: Mapping[str, object],
    pressure_pa: object,
    temperatures_k: Sequence[object],
    units: object,
) -> dict[str, Any]:
    canonical_balance = _element(balance, "balance")
    if units not in ("wt", "at"):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "units must be wt or at.")
    if type(composition_pct) is not dict or len(composition_pct) > 32:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "composition_pct must be a bounded plain object.")
    pairs: list[tuple[str, float]] = []
    for raw_element, raw_value in composition_pct.items():
        element = _element(raw_element, "composition element")
        if element == canonical_balance:
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Balance must be absent from composition_pct.")
        pairs.append((element, _plain_float(raw_value, f"composition_pct.{element}", minimum=0.0)))
    pairs.sort()
    if len({name for name, _value in pairs}) != len(pairs) or sum(value for _name, value in pairs) >= 100.0:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Composition is not unique or leaves no balance.")
    if isinstance(temperatures_k, (str, bytes)):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "temperatures_k must be an ordered sequence.")
    temperatures = tuple(
        _plain_float(value, f"temperatures_k[{index}]", minimum=0.0, minimum_inclusive=False)
        for index, value in enumerate(temperatures_k)
    )
    if len(temperatures) != 1:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Elastic prepare requires one temperature.")
    return {
        "balance": canonical_balance,
        "composition_pct": [[name, value] for name, value in pairs],
        "pressure_pa": _plain_float(pressure_pa, "pressure_pa", minimum=0.0, minimum_inclusive=False),
        "temperatures_k": list(temperatures),
        "units": units,
    }


def make_vrh_inputs(
    *,
    prepared_witness_digest: object,
    library_snapshot_digest: object,
    library_update: object,
    phase_rows: Sequence[Mapping[str, object]],
) -> dict[str, Any]:
    _digest(prepared_witness_digest, "prepared_witness_digest")
    _digest(library_snapshot_digest, "library_snapshot_digest")
    if type(library_update) is not bool or isinstance(phase_rows, (str, bytes)):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "VRH update/rows are invalid.")
    rows = [dict(row) if type(row) is dict else row for row in phase_rows]
    try:
        verified_loaders.canonical_json_bytes(rows)
    except verified_loaders.VerifiedLoaderError:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "VRH rows are not finite canonical values.")
    return {
        "prepared_witness_digest": prepared_witness_digest,
        "library_snapshot_digest": library_snapshot_digest,
        "library_update": library_update,
        "phase_rows": rows,
    }


def make_strengthening_inputs(**values: object) -> dict[str, Any]:
    _exact_dict(values, STRENGTHENING_INPUT_FIELDS, "strengthening")
    return dict(values)


def _prepare_inputs_from_request(request: verified_loaders.FeatureRequest) -> dict[str, Any]:
    raw = _exact_dict(request.inputs, PREPARE_INPUT_FIELDS, "prepare inputs")
    try:
        pairs = raw["composition_pct"]
        if type(pairs) is not list or any(type(item) is not list or len(item) != 2 for item in pairs):
            raise TypeError
        composition = {item[0]: item[1] for item in pairs}
        if len(composition) != len(pairs):
            raise TypeError
        rebuilt = make_prepare_inputs(
            balance=raw["balance"],
            composition_pct=composition,
            pressure_pa=raw["pressure_pa"],
            temperatures_k=raw["temperatures_k"],
            units=raw["units"],
        )
    except (KeyError, TypeError, IndexError):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Prepare input shape is invalid.")
    if rebuilt != raw:
        _fail(verified_loaders.ReasonCode.REQUEST_DIGEST_MISMATCH, "Prepare inputs are not canonical.")
    return rebuilt


def _database_masses(database: object, elements: Sequence[str]) -> dict[str, float]:
    refstates = getattr(database, "refstates", None)
    if not isinstance(refstates, Mapping):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Parsed database lacks reference-state masses.")
    result: dict[str, float] = {}
    for element in elements:
        record = refstates.get(element)
        mass = record.get("mass") if isinstance(record, Mapping) else None
        if type(mass) not in (int, float) or not math.isfinite(float(mass)) or float(mass) <= 0.0:
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, f"Parsed database lacks mass for {element}.")
        result[element] = float(mass)
    return result


def _atomic_fractions(database: object, inputs: Mapping[str, Any]) -> tuple[tuple[str, float], ...]:
    percentages = {name: float(value) for name, value in inputs["composition_pct"]}
    percentages[inputs["balance"]] = 100.0 - sum(percentages.values())
    ordered = tuple(sorted(percentages))
    if inputs["units"] == "at":
        raw = {name: percentages[name] / 100.0 for name in ordered}
    else:
        masses = _database_masses(database, ordered)
        raw = {name: percentages[name] / masses[name] for name in ordered}
    total = sum(raw.values())
    if not math.isfinite(total) or total <= 0.0:
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Atomic conversion failed.")
    return tuple((name, raw[name] / total) for name in ordered)


def _default_tdb_parser(source: object) -> object:
    from pycalphad import Database

    return Database.from_file(source, fmt="tdb")


def _default_pdb_parser(data: bytes) -> physical.PhysicalDensityDatabase:
    return physical.PhysicalDensityDatabase.from_verified_bytes(data)


def _default_backend(
    database: object,
    _physical_database: physical.PhysicalDensityDatabase,
    call: PropertyPrepareCall,
) -> Mapping[str, float]:
    import numpy as np
    from pycalphad import equilibrium, variables as v

    atomic = dict(call.atomic_fractions)
    conditions: dict[Any, float] = {v.N: 1.0, v.P: call.pressure_pa, v.T: call.temperature_k}
    conditions.update({v.X(name): value for name, value in atomic.items() if name != call.balance})
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
    for raw_name, raw_fraction in zip(names, fractions):
        name = str(raw_name)
        value = float(raw_fraction)
        if not name:
            if math.isnan(value) or (math.isfinite(value) and 0.0 <= value <= 1e-12):
                continue
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend returned unlabeled phase mass.")
        if name == C15_PHASE or name not in call.phases:
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend returned a phase outside effective scope.")
        if not math.isfinite(value) or value < 0.0:
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Backend returned an invalid phase fraction.")
        if value > 1e-12:
            aggregated[name] = aggregated.get(name, 0.0) + value
    return aggregated


def _phase_identity(
    context: verified_loaders.BoundDatabaseContext,
    request: verified_loaders.FeatureRequest,
    database: object,
) -> tuple[str, ...]:
    phases = getattr(database, "phases", None)
    if not isinstance(phases, Mapping):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Parsed database lacks a phase catalog.")
    candidates = tuple(
        sorted(
            name
            for name in phases
            if type(name) is str
            and name
            and name != C15_PHASE
            and name not in context.phase_policy.explicit_rejections
        )
    )
    live = context.phase_policy.effective(request.requested_phases, candidates=candidates)
    if request.requested_phases:
        matches = live == request.effective_phases
    else:
        order = {name: index for index, name in enumerate(live)}
        matches = (
            bool(request.effective_phases)
            and all(name in order for name in request.effective_phases)
            and tuple(sorted(request.effective_phases, key=order.__getitem__)) == request.effective_phases
        )
    if not matches:
        _fail(verified_loaders.ReasonCode.PHASE_POLICY_MISMATCH, "Live phase identity differs from request evidence.")
    return request.effective_phases


def _validate_phase_projection(
    value: object,
    phases: tuple[str, ...],
) -> tuple[tuple[str, float], ...]:
    if type(value) is not dict or not value:
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Prepare backend must return a non-empty plain mapping.")
    order = {name: index for index, name in enumerate(phases)}
    rows: list[tuple[str, float]] = []
    for name, raw_fraction in value.items():
        if type(name) is not str or name not in order or name == C15_PHASE:
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Prepare backend returned an ineligible phase.")
        if type(raw_fraction) is not float:
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Prepare backend fraction type/domain is invalid.")
        fraction = float(raw_fraction)
        if not math.isfinite(fraction) or fraction <= 0.0 or fraction > 1.0 + 1e-8:
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Prepare backend fraction type/domain is invalid.")
        rows.append((name, fraction))
    rows.sort(key=lambda item: order[item[0]])
    if not math.isclose(sum(value for _name, value in rows), 1.0, abs_tol=1e-8):
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, "Prepare phase fractions do not close to one.")
    return tuple(rows)


def _utc(clock: Callable[[], object]) -> str:
    value = clock()
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if type(value) is str and value.endswith("Z"):
        return value
    _fail(verified_loaders.ReasonCode.SCHEMA_INVALID, "Adapter clock returned an invalid value.")
    raise AssertionError


def _system_clock() -> datetime:
    return datetime.now(timezone.utc)


def _canonical(value: object) -> Any:
    try:
        return json.loads(verified_loaders.canonical_json_bytes(value).decode("utf-8"))
    except verified_loaders.VerifiedLoaderError:
        raise
    except Exception as error:
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, f"Projection is not canonical: {type(error).__name__}.")
    raise AssertionError


def _frame_rows(frame: object) -> list[dict[str, Any]]:
    try:
        records = frame.to_dict(orient="records")
    except Exception as error:
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, f"Kernel table is invalid: {type(error).__name__}.")
    result: list[dict[str, Any]] = []
    for record in records:
        row: dict[str, Any] = {}
        for key, value in record.items():
            if hasattr(value, "item"):
                value = value.item()
            if type(value) is float and not math.isfinite(value):
                value = None
            row[str(key)] = value
        result.append(_canonical(row))
    return result


def _make_result(
    context: verified_loaders.BoundDatabaseContext,
    request: verified_loaders.FeatureRequest,
    lease: verified_loaders.ExecutionLease,
    projection: Mapping[str, Any],
    *,
    backend_id: str,
    point_count: int,
    clock: Callable[[], object],
    packages: Sequence[Mapping[str, str]],
) -> tuple[dict[str, Any], verified_loaders.FeatureReceipt, verified_loaders.ResultEnvelope]:
    safe_projection = _canonical(dict(projection))
    settings = {
        "experimental_qualification": "NOT_PERFORMED" if context.database_key == "fe" else None,
        "projection": safe_projection,
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
        request,
        lease,
        outcome="success",
        reason_code=None,
        reason_detail=None,
        backend={
            "adapter_id": ADAPTER_ID,
            "adapter_revision": ADAPTER_REVISION,
            "backend_id": backend_id,
            "backend_version": "1",
        },
        packages=packages,
        point_count=point_count,
        result_digest=result_digest,
        started_at_utc=lease.identity.acquired_at_utc,
        finished_at_utc=finished_at,
    )
    envelope = verified_loaders.make_result_envelope(
        context,
        request,
        receipt,
        settings=settings,
        clock=lambda: finished_at,
    )
    return safe_projection, receipt, envelope


def _context_request_lease(
    context: object,
    request: object,
    lease: object,
) -> tuple[
    verified_loaders.BoundDatabaseContext,
    verified_loaders.FeatureRequest,
    verified_loaders.ExecutionLease,
]:
    if type(context) is not verified_loaders.BoundDatabaseContext:
        _fail(verified_loaders.ReasonCode.BINDING_IDENTITY_MISMATCH, "Properties require a bound context.")
    if type(request) is not verified_loaders.FeatureRequest or request.feature_id not in PROPERTY_FEATURE_IDS:
        _fail(verified_loaders.ReasonCode.FEATURE_ID_UNKNOWN, "Request is outside B4B2.")
    if C15_PHASE in request.requested_phases or C15_PHASE in request.effective_phases:
        _fail(verified_loaders.ReasonCode.C15_PHASE_REJECTED, "C15_LAVES is rejected before every B4B2 side effect.")
    if type(lease) is not verified_loaders.ExecutionLease or lease.request != request:
        _fail(verified_loaders.ReasonCode.LEASE_IDENTITY_MISMATCH, "Properties require the matching live lease.")
    lease.identity
    if request.binding_digest != context.binding_digest or request.binding_generation != context.binding_generation:
        _fail(verified_loaders.ReasonCode.BINDING_IDENTITY_MISMATCH, "Context/request identity mismatch.")
    if context.database_key not in ("ni", "al", "fe") or context.physical_pdb is None:
        _fail(verified_loaders.ReasonCode.DATA_UNAVAILABLE, "Canonical TDB and PDB evidence are required.")
    if context.database_key == "fe" and context.profile_key != "thermogar_patch":
        _fail(verified_loaders.ReasonCode.UPSTREAM_PROFILE_REJECTED, "Fe properties require thermogar_patch.")
    return context, request, lease


def _library_path(paths: object) -> tuple[ThermoGarPaths, object]:
    if type(paths) is not ThermoGarPaths:
        _fail(verified_loaders.ReasonCode.RAW_PATH_REJECTED, "Property repository requires injected ThermoGarPaths.")
    return paths, paths.elastic_properties_path


def _decode_library(data: bytes) -> dict[str, Any]:
    if type(data) is not bytes or len(data) > MAX_LIBRARY_BYTES or data.startswith(b"\xef\xbb\xbf"):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Property repository bytes are invalid.")
    try:
        try:
            payload = verified_loaders.load_canonical_json(data)
        except verified_loaders.VerifiedLoaderError:
            payload = duplicate_reject_json(data.decode("utf-8", errors="strict"))
            verified_loaders.canonical_json_bytes(payload)
        return properties._verified_elastic_library_payload(payload)
    except (UnicodeError, ValueError, TypeError) as error:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, f"Property repository schema is invalid: {type(error).__name__}.")
    except verified_loaders.VerifiedLoaderError:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Property repository JSON is invalid.")
    raise AssertionError


def _read_library(paths: object) -> tuple[dict[str, Any], str, bytes]:
    authority, path = _library_path(paths)
    try:
        path.lstat()
    except FileNotFoundError:
        raw = verified_loaders.canonical_json_bytes(_EMPTY_LIBRARY)
        return properties._verified_elastic_library_payload(_EMPTY_LIBRARY), hashlib.sha256(raw).hexdigest(), raw
    try:
        snapshot = read_verified_snapshot(
            path,
            maximum_bytes=8388608,
            canonical_root=authority.state_root,
        )
    except SecureIOError as error:
        reason = (
            verified_loaders.ReasonCode.ARTIFACT_OVERSIZE
            if "bounded snapshot limit" in str(error)
            else verified_loaders.ReasonCode.ARTIFACT_IO_FAILED
        )
        _fail(reason, str(error))
    return _decode_library(snapshot.data), snapshot.sha256, snapshot.data


def _prepared_witness(
    context: verified_loaders.BoundDatabaseContext,
    digest: object,
) -> _PreparedWitness:
    key = _digest(digest, "prepared_witness_digest")
    witness = _PREPARED_WITNESSES.get(key)
    if witness is None:
        _fail(verified_loaders.ReasonCode.DATA_UNAVAILABLE, "Prepared elastic witness is unavailable.")
    if witness.binding_generation != context.binding_generation:
        _fail(verified_loaders.ReasonCode.GENERATION_STALE, "Prepared elastic witness generation is stale.")
    if witness.binding_digest != context.binding_digest:
        _fail(verified_loaders.ReasonCode.BINDING_STALE, "Prepared elastic witness binding is stale.")
    if C15_PHASE in dict(witness.phase_rows):
        _fail(verified_loaders.ReasonCode.C15_PHASE_REJECTED, "Prepared witness contains C15_LAVES.")
    return witness


def property_library_prefill(
    context: verified_loaders.BoundDatabaseContext,
    prepared_witness_digest: str,
    *,
    paths: ThermoGarPaths,
) -> PropertyLibraryView:
    if type(context) is not verified_loaders.BoundDatabaseContext:
        _fail(verified_loaders.ReasonCode.BINDING_IDENTITY_MISMATCH, "Prefill requires a bound context.")
    witness = _prepared_witness(context, prepared_witness_digest)
    library, raw_digest, _raw = _read_library(paths)
    rows: list[dict[str, Any]] = []
    for phase, fraction in witness.phase_rows:
        stored = library["entries"].get(f"{context.database_key}::{phase}")
        if stored is None:
            row = {
                "phase": phase,
                "volume_fraction": fraction,
                "young_gpa": None,
                "poisson": None,
                "origin": None,
                "source": None,
                "reference_temperature_c": None,
                "note": "",
            }
        else:
            normalized = properties._verified_prefill_entry(stored)
            row = {
                "phase": phase,
                "volume_fraction": fraction,
                "young_gpa": normalized["young_gpa"],
                "poisson": normalized["poisson"],
                "origin": normalized["origin"],
                "source": normalized["source"],
                "reference_temperature_c": normalized["reference_temperature_c"],
                "note": normalized["note"],
            }
        rows.append(row)
    return PropertyLibraryView(raw_digest, tuple(rows), library["updated_at"])


def _validate_vrh_rows(
    value: object,
    witness: _PreparedWitness,
) -> tuple[dict[str, Any], ...]:
    if type(value) is not list or not (1 <= len(value) <= 64):
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "VRH phase_rows must contain 1..64 rows.")
    expected = witness.phase_rows
    if len(value) != len(expected):
        _fail(verified_loaders.ReasonCode.DATA_UNAVAILABLE, "VRH rows do not match the prepared witness.")
    rows: list[dict[str, Any]] = []
    for index, (raw, (expected_phase, expected_fraction)) in enumerate(zip(value, expected)):
        row = _exact_dict(raw, VRH_ROW_FIELDS, f"phase_rows[{index}]")
        if row["phase"] == C15_PHASE:
            _fail(verified_loaders.ReasonCode.C15_PHASE_REJECTED, "C15_LAVES is rejected before repository access.")
        if row["phase"] != expected_phase or row["volume_fraction"] != expected_fraction:
            _fail(verified_loaders.ReasonCode.DATA_UNAVAILABLE, "VRH phase identity differs from the prepared witness.")
        missing = ("young_gpa", "poisson", "origin", "source", "reference_temperature_c")
        if any(row[field] is None for field in missing):
            _fail(verified_loaders.ReasonCode.USER_INPUT_REQUIRED, "Complete phase modulus provenance is required.")
        young = _plain_float(row["young_gpa"], "young_gpa", minimum=0.0, minimum_inclusive=False)
        poisson = _plain_float(row["poisson"], "poisson")
        if not (-1.0 < poisson < 0.5):
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "poisson is outside (-1, 0.5).")
        origin = _trimmed(row["origin"], "origin", maximum=128)
        source = _trimmed(row["source"], "source", maximum=1024)
        reference = _plain_float(
            row["reference_temperature_c"],
            "reference_temperature_c",
            minimum=-273.15,
            maximum=10000.0,
        )
        note = _trimmed(row["note"], "note", maximum=2048, allow_empty=True)
        rows.append(
            {
                "phase": expected_phase,
                "volume_fraction": expected_fraction,
                "young_gpa": young,
                "poisson": poisson,
                "origin": origin,
                "source": source,
                "reference_temperature_c": reference,
                "note": note,
            }
        )
    return tuple(rows)


def _write_library(
    paths: object,
    context: verified_loaders.BoundDatabaseContext,
    expected_digest: str,
    rows: Sequence[Mapping[str, Any]],
    timestamp: str,
) -> tuple[dict[str, Any], str]:
    authority, path = _library_path(paths)
    ensure_plain_directory(path.parent)

    def updater(current: bytes) -> bytes:
        raw = current if current else verified_loaders.canonical_json_bytes(_EMPTY_LIBRARY)
        if hashlib.sha256(raw).hexdigest() != expected_digest:
            _fail(verified_loaders.ReasonCode.STATE_CONFLICT, "Property repository changed before held update.")
        library = _decode_library(raw)
        entries = dict(library["entries"])
        for row in rows:
            moduli = properties.moduli_from_e_nu(row["young_gpa"], row["poisson"])
            phase = row["phase"]
            entries[f"{context.database_key}::{phase}"] = {
                "database_key": context.database_key,
                "phase": phase,
                "young_gpa": moduli.young_gpa,
                "poisson": moduli.poisson,
                "bulk_gpa": moduli.bulk_gpa,
                "shear_gpa": moduli.shear_gpa,
                "origin": row["origin"],
                "source": row["source"],
                "reference_temperature_c": row["reference_temperature_c"],
                "note": row["note"],
                "updated_at": timestamp,
            }
        if len(entries) > MAX_LIBRARY_ENTRIES:
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Property repository exceeds 512 entries.")
        payload = properties._verified_elastic_library_payload(
            {"schema_version": 1, "updated_at": timestamp, "entries": entries}
        )
        encoded = verified_loaders.canonical_json_bytes(payload)
        if len(encoded) > MAX_LIBRARY_BYTES:
            _fail(verified_loaders.ReasonCode.ARTIFACT_OVERSIZE, "Property repository exceeds 8 MiB.")
        return encoded

    try:
        atomic_update_bytes(path, updater, create_backup=False, maximum_bytes=8388608, canonical_root=paths.state_root)
    except verified_loaders.VerifiedLoaderError:
        raise
    except SecureIOError as error:
        reason = (
            verified_loaders.ReasonCode.ARTIFACT_OVERSIZE
            if "bounded" in str(error)
            else verified_loaders.ReasonCode.ARTIFACT_WRITE_FAILED
        )
        _fail(reason, str(error))
    try:
        snapshot = read_verified_snapshot(
            path,
            maximum_bytes=8388608,
            canonical_root=paths.state_root,
        )
    except SecureIOError as error:
        _fail(verified_loaders.ReasonCode.ARTIFACT_IO_FAILED, str(error))
    return _decode_library(snapshot.data), snapshot.sha256


def _hill_witness(
    context: verified_loaders.BoundDatabaseContext,
    digest: object,
) -> _HillWitness:
    key = _digest(digest, "hill_witness_digest")
    witness = _HILL_WITNESSES.get(key)
    if witness is None:
        _fail(verified_loaders.ReasonCode.DATA_UNAVAILABLE, "Hill witness is unavailable.")
    if witness.binding_generation != context.binding_generation:
        _fail(verified_loaders.ReasonCode.GENERATION_STALE, "Hill witness generation is stale.")
    if witness.binding_digest != context.binding_digest:
        _fail(verified_loaders.ReasonCode.BINDING_STALE, "Hill witness binding is stale.")
    return witness


def _optional_nonnegative(value: object, label: str) -> float | None:
    if value is None:
        return None
    return _plain_float(value, label, minimum=0.0)


def _strengthening_inputs(
    value: object,
    context: verified_loaders.BoundDatabaseContext,
) -> tuple[dict[str, Any], _HillWitness | None]:
    raw = _exact_dict(value, STRENGTHENING_INPUT_FIELDS, "strengthening inputs")
    if raw["input_provenance"] is None:
        _fail(verified_loaders.ReasonCode.USER_INPUT_REQUIRED, "Strengthening input provenance is required.")
    provenance = _trimmed(raw["input_provenance"], "input_provenance", maximum=2048)
    if type(raw["input_confirmation"]) is not bool:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "input_confirmation must be bool.")
    if raw["input_confirmation"] is False:
        _fail(verified_loaders.ReasonCode.USER_INPUT_REQUIRED, "Strengthening input scope must be confirmed.")
    sigma = _plain_float(raw["sigma_internal_mpa"], "sigma_internal_mpa", minimum=0.0)
    hall = raw["hall_petch"]
    if hall is not None:
        hall = _exact_dict(hall, HALL_PETCH_FIELDS, "hall_petch")
        hall = {
            "k_y_mpa_sqrt_m": _plain_float(hall["k_y_mpa_sqrt_m"], "hall_petch.k_y", minimum=0.0),
            "grain_size_um": _plain_float(hall["grain_size_um"], "hall_petch.grain", minimum=0.0, minimum_inclusive=False),
        }
    taylor = raw["taylor"]
    if taylor is not None:
        taylor = dict(_exact_dict(taylor, TAYLOR_FIELDS, "taylor"))
    orowan = raw["orowan"]
    if orowan is not None:
        orowan = dict(_exact_dict(orowan, OROWAN_FIELDS, "orowan"))
    digest = raw["hill_witness_digest"]
    hill: _HillWitness | None = None
    if digest is not None:
        hill = _hill_witness(context, digest)
        for record, field in ((taylor, "shear_gpa"), (orowan, "shear_gpa"), (orowan, "poisson")):
            if record is not None and record[field] is not None:
                _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Hill witness fills missing fields only.")
        if taylor is not None:
            taylor["shear_gpa"] = hill.shear_gpa
        if orowan is not None:
            orowan["shear_gpa"] = hill.shear_gpa
            orowan["poisson"] = hill.poisson
    elif digest is not None:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "hill_witness_digest is invalid.")
    if taylor is not None:
        for field in TAYLOR_FIELDS:
            taylor[field] = _plain_float(taylor[field], f"taylor.{field}", minimum=0.0, minimum_inclusive=False)
    if orowan is not None:
        for field in OROWAN_FIELDS:
            minimum_inclusive = field == "poisson"
            minimum = None if field == "poisson" else 0.0
            orowan[field] = _plain_float(
                orowan[field],
                f"orowan.{field}",
                minimum=minimum,
                minimum_inclusive=minimum_inclusive,
            )
        if not (-1.0 < orowan["poisson"] < 0.5):
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "orowan.poisson is outside (-1, 0.5).")
        if orowan["particle_radius_nm"] <= orowan["burgers_nm"]:
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "Orowan radius must exceed Burgers vector.")
    rule = raw["summation_rule"]
    if rule not in properties.STRENGTHENING_SUMMATION_RULES:
        _fail(verified_loaders.ReasonCode.INPUT_INVALID, "summation_rule is invalid.")
    return (
        {
            "input_provenance": provenance,
            "input_confirmation": True,
            "sigma_internal_mpa": sigma,
            "hall_petch": hall,
            "taylor": taylor,
            "solid_solution_mpa": _optional_nonnegative(raw["solid_solution_mpa"], "solid_solution_mpa"),
            "orowan": orowan,
            "other_mpa": _optional_nonnegative(raw["other_mpa"], "other_mpa"),
            "summation_rule": rule,
        },
        hill,
    )


def execute_verified_properties(
    context: verified_loaders.BoundDatabaseContext,
    feature_request: verified_loaders.FeatureRequest,
    lease: verified_loaders.ExecutionLease,
    *,
    paths: ThermoGarPaths,
    tdb_parser: Callable[[object], object] = _default_tdb_parser,
    backend: Callable[[object, physical.PhysicalDensityDatabase, PropertyPrepareCall], Mapping[str, float]] = _default_backend,
    clock: Callable[[], object] = _system_clock,
    packages: Sequence[Mapping[str, str]] = (),
) -> VerifiedPropertiesResult:
    """Execute one B4B2 feature through the matching live verified lease."""

    context, feature_request, lease = _context_request_lease(context, feature_request, lease)
    if type(paths) is not ThermoGarPaths:
        _fail(verified_loaders.ReasonCode.RAW_PATH_REJECTED, "Properties require injected ThermoGarPaths.")

    if feature_request.feature_id == "property_elastic_prepare":
        inputs = _prepare_inputs_from_request(feature_request)
        try:
            physical_database = lease.parse_physical_dataset(_default_pdb_parser, PDB_PARSER_REVISION)
        except verified_loaders.VerifiedLoaderError:
            raise
        except Exception as error:
            _fail(verified_loaders.ReasonCode.PDB_INVALID, f"PDB parse failed: {type(error).__name__}.")
        try:
            database = lease.parse_tdb(tdb_parser, PARSER_REVISION, fresh=True)
        except verified_loaders.VerifiedLoaderError:
            raise
        except Exception as error:
            _fail(verified_loaders.ReasonCode.PACKAGE_UNAVAILABLE, f"TDB parse failed: {type(error).__name__}.")
        phases = _phase_identity(context, feature_request, database)
        atomic = _atomic_fractions(database, inputs)
        call = PropertyPrepareCall(
            temperature_k=float(inputs["temperatures_k"][0]),
            pressure_pa=float(inputs["pressure_pa"]),
            balance=inputs["balance"],
            components=tuple(name for name, _value in atomic) + ("VA",),
            atomic_fractions=atomic,
            phases=phases,
        )
        try:
            raw = lease.invoke_backend(lambda _live: backend(database, physical_database, call))
        except verified_loaders.VerifiedLoaderError:
            raise
        except Exception as error:
            _fail(verified_loaders.ReasonCode.BACKEND_FAILED, type(error).__name__)
        phase_rows = _validate_phase_projection(raw, phases)
        projection = {
            "operation": "property_elastic_prepare",
            "phase_rows": [
                {"phase": phase, "volume_fraction": fraction}
                for phase, fraction in phase_rows
            ],
            "physical_pdb_sha256": context.physical_pdb.sha256,
            "tdb_sha256": context.tdb.sha256,
        }
        safe, receipt, envelope = _make_result(
            context,
            feature_request,
            lease,
            projection,
            backend_id="pycalphad-equilibrium-properties",
            point_count=1,
            clock=clock,
            packages=packages,
        )
        witness_payload = {
            "binding_digest": context.binding_digest,
            "binding_generation": context.binding_generation,
            "request_digest": feature_request.request_digest,
            "receipt_digest": receipt.receipt_digest,
            "envelope_digest": envelope.envelope_digest,
            "tdb_sha256": context.tdb.sha256,
            "physical_pdb_sha256": context.physical_pdb.sha256,
            "phase_rows": [[phase, fraction] for phase, fraction in phase_rows],
        }
        witness_digest = verified_loaders.canonical_digest(witness_payload)
        _PREPARED_WITNESSES[witness_digest] = _PreparedWitness(
            phase_rows=phase_rows,
            witness_digest=witness_digest,
            **{key: witness_payload[key] for key in witness_payload if key != "phase_rows"},
        )
        return VerifiedPropertiesResult(safe, receipt, envelope, prepared_witness_digest=witness_digest)

    if feature_request.feature_id == "property_elastic_vrh":
        raw_inputs = _exact_dict(feature_request.inputs, VRH_INPUT_FIELDS, "VRH inputs")
        witness = _prepared_witness(context, raw_inputs["prepared_witness_digest"])
        rows = _validate_vrh_rows(raw_inputs["phase_rows"], witness)
        expected_library_digest = _digest(raw_inputs["library_snapshot_digest"], "library_snapshot_digest")
        if type(raw_inputs["library_update"]) is not bool:
            _fail(verified_loaders.ReasonCode.INPUT_INVALID, "library_update must be bool.")
        library, current_digest, _raw = _read_library(paths)
        if current_digest != expected_library_digest:
            _fail(verified_loaders.ReasonCode.STATE_CONFLICT, "Property repository digest does not match the request.")
        kernel_rows: list[dict[str, float | str]] = []
        for row in rows:
            moduli = properties.moduli_from_e_nu(row["young_gpa"], row["poisson"])
            kernel_rows.append(
                {
                    "phase": row["phase"],
                    "volume_fraction": row["volume_fraction"],
                    "bulk_gpa": moduli.bulk_gpa,
                    "shear_gpa": moduli.shear_gpa,
                }
            )
        try:
            bounds_table, summary = properties.vrh_homogenization(kernel_rows)
        except properties.PropertyCalculationError as error:
            _fail(verified_loaders.ReasonCode.RESULT_INVALID, error.reason_code)
        post_digest = current_digest
        post_updated_at = library["updated_at"]
        if raw_inputs["library_update"]:
            timestamp = _utc(clock)
            library, post_digest = _write_library(
                paths,
                context,
                expected_library_digest,
                rows,
                timestamp,
            )
            post_updated_at = library["updated_at"]
        projection = {
            "bounds_rows": _frame_rows(bounds_table),
            "library_snapshot_digest_before": current_digest,
            "library_snapshot_digest_after": post_digest,
            "library_updated_at": post_updated_at,
            "operation": "property_elastic_vrh",
            "phase_rows": [dict(row) for row in rows],
            "summary": _canonical(summary),
        }
        safe, receipt, envelope = _make_result(
            context,
            feature_request,
            lease,
            projection,
            backend_id="thermogar-vrh-kernel",
            point_count=1,
            clock=clock,
            packages=packages,
        )
        hill_payload = {
            "binding_digest": context.binding_digest,
            "binding_generation": context.binding_generation,
            "request_digest": feature_request.request_digest,
            "receipt_digest": receipt.receipt_digest,
            "envelope_digest": envelope.envelope_digest,
            "bulk_gpa": float(summary["K_Hill_GPa"]),
            "shear_gpa": float(summary["G_Hill_GPa"]),
            "young_gpa": float(summary["E_Hill_GPa"]),
            "poisson": float(summary["nu_Hill"]),
        }
        hill_digest = verified_loaders.canonical_digest(hill_payload)
        _HILL_WITNESSES[hill_digest] = _HillWitness(witness_digest=hill_digest, **hill_payload)
        return VerifiedPropertiesResult(safe, receipt, envelope, hill_witness_digest=hill_digest)

    inputs, _hill = _strengthening_inputs(feature_request.inputs, context)
    try:
        result = properties.calculate_strengthening(**inputs)
    except properties.PropertyCalculationError as error:
        _fail(verified_loaders.ReasonCode.RESULT_INVALID, error.reason_code)
    projection = {
        "contribution_rows": _frame_rows(result.contribution_table),
        "input_confirmation": result.input_confirmation,
        "input_provenance": result.input_provenance,
        "operation": "property_strengthening",
        "summation_rule": result.summation_rule,
        "total_mpa": result.total_mpa,
        "warnings": list(result.warnings),
    }
    safe, receipt, envelope = _make_result(
        context,
        feature_request,
        lease,
        projection,
        backend_id="thermogar-strengthening-kernel",
        point_count=1,
        clock=clock,
        packages=packages,
    )
    return VerifiedPropertiesResult(safe, receipt, envelope)


__all__ = (
    "ADAPTER_ID",
    "PROPERTY_FEATURE_IDS",
    "PropertyLibraryView",
    "PropertyPrepareCall",
    "VerifiedPropertiesResult",
    "clear_property_witnesses",
    "execute_verified_properties",
    "make_prepare_inputs",
    "make_strengthening_inputs",
    "make_vrh_inputs",
    "property_library_prefill",
)
