"""Verified, path-free binding foundation for the unified ThermoGar app.

Wave B1 intentionally provides no scientific implementation.  Immutable
installation artifacts are admitted by a closed catalog, public state contains
evidence only, and parsing/backend work is possible solely through injected
seams held by a current process-local execution lease.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import uuid
from typing import Any, Callable, Mapping, Sequence

from thermogar_secure_io import (
    MAX_TDB_SNAPSHOT_BYTES,
    assert_plain_path,
    parse_verified_utf8_snapshot,
    read_verified_snapshot,
)
from thermogar_verified_artifact import duplicate_reject_json, strict_utf8_text


SCHEMA_BOUND_CONTEXT = "thermogar.bound-database-context.v1"
SCHEMA_FEATURE_REQUEST = "thermogar.feature-request.v1"
SCHEMA_EXECUTION_LEASE = "thermogar.execution-lease.v1"
SCHEMA_REJECTION = "thermogar.feature-rejection.v1"
SCHEMA_FEATURE_RECEIPT = "thermogar.feature-receipt.v1"
SCHEMA_RESULT_ENVELOPE = "thermogar.feature-result.v1"
SCHEMA_CORE1_BRIDGE = "thermogar.core1-v2-evidence-bridge.v1"
FEATURE_REVISION = "1"
SCIENTIFIC_LANE_ID = "steel-numerical-v1"
C15_PHASE = "C15_LAVES"
FE_PATCH_ID = "TG-FE-2062-C15-001"
PARSER_SEAM_REVISION = "b1-injected-only"
MAX_PASSPORT_BYTES = 1024 * 1024
MAX_PHYSICAL_PDB_BYTES = 16 * 1024 * 1024
MAX_REASON_DETAIL_CHARS = 512

_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_UTC_Z_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z"
)
_PHASE_RE = re.compile(r"[A-Z0-9][A-Z0-9_:+\-]*(?:#[0-9]+)?")
_REVISION_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.+\-]{0,63}")
_RAW_PATH_KEYS = frozenset(
    {
        "database_path",
        "tdb_path",
        "passport_path",
        "physical_pdb_path",
        "installation_root",
        "project_root",
        "source_root",
        "temp_root",
    }
)


class ReasonCode(str, Enum):
    SCHEMA_INVALID = "SCHEMA_INVALID"
    CANONICAL_JSON_INVALID = "CANONICAL_JSON_INVALID"
    FEATURE_ID_UNKNOWN = "FEATURE_ID_UNKNOWN"
    FEATURE_REVISION_UNSUPPORTED = "FEATURE_REVISION_UNSUPPORTED"
    DATABASE_KEY_REJECTED = "DATABASE_KEY_REJECTED"
    PROFILE_KEY_REJECTED = "PROFILE_KEY_REJECTED"
    UPSTREAM_PROFILE_REJECTED = "UPSTREAM_PROFILE_REJECTED"
    ARTIFACT_PATH_REJECTED = "ARTIFACT_PATH_REJECTED"
    ARTIFACT_MISSING = "ARTIFACT_MISSING"
    ARTIFACT_OVERSIZE = "ARTIFACT_OVERSIZE"
    ARTIFACT_IO_FAILED = "ARTIFACT_IO_FAILED"
    TDB_HASH_MISMATCH = "TDB_HASH_MISMATCH"
    PASSPORT_REQUIRED = "PASSPORT_REQUIRED"
    PASSPORT_HASH_MISMATCH = "PASSPORT_HASH_MISMATCH"
    PASSPORT_INVALID = "PASSPORT_INVALID"
    PATCH_ID_MISMATCH = "PATCH_ID_MISMATCH"
    PDB_HASH_MISMATCH = "PDB_HASH_MISMATCH"
    PDB_INVALID = "PDB_INVALID"
    BINDING_IDENTITY_MISMATCH = "BINDING_IDENTITY_MISMATCH"
    BINDING_STALE = "BINDING_STALE"
    GENERATION_STALE = "GENERATION_STALE"
    INPUT_INVALID = "INPUT_INVALID"
    USER_INPUT_REQUIRED = "USER_INPUT_REQUIRED"
    PHASE_NOT_PRESENT = "PHASE_NOT_PRESENT"
    PHASE_SET_EMPTY = "PHASE_SET_EMPTY"
    PHASE_POLICY_MISMATCH = "PHASE_POLICY_MISMATCH"
    C15_PHASE_REJECTED = "C15_PHASE_REJECTED"
    LIQUID_PHASE_REQUIRED = "LIQUID_PHASE_REQUIRED"
    PACKAGE_UNAVAILABLE = "PACKAGE_UNAVAILABLE"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    REQUEST_DIGEST_MISMATCH = "REQUEST_DIGEST_MISMATCH"
    LEASE_BUSY = "LEASE_BUSY"
    LEASE_IDENTITY_MISMATCH = "LEASE_IDENTITY_MISMATCH"
    BACKEND_FAILED = "BACKEND_FAILED"
    RESULT_INVALID = "RESULT_INVALID"
    RESULT_DIGEST_MISMATCH = "RESULT_DIGEST_MISMATCH"
    RECEIPT_INVALID = "RECEIPT_INVALID"
    ENVELOPE_INVALID = "ENVELOPE_INVALID"
    ENVELOPE_CONTEXT_MISMATCH = "ENVELOPE_CONTEXT_MISMATCH"
    RAW_PATH_REJECTED = "RAW_PATH_REJECTED"
    IMPORT_SCHEMA_REJECTED = "IMPORT_SCHEMA_REJECTED"
    EXPORT_SOURCE_REJECTED = "EXPORT_SOURCE_REJECTED"
    STATE_CONFLICT = "STATE_CONFLICT"
    ARTIFACT_WRITE_FAILED = "ARTIFACT_WRITE_FAILED"


FEATURE_IDS = (
    "equilibrium_single",
    "equilibrium_temperature_scan",
    "equilibrium_composition_scan",
    "diagram_binary",
    "diagram_isopleth",
    "diagram_ternary",
    "diagram_phase_fraction_map",
    "solidification_equilibrium",
    "solidification_scheil",
    "solidification_compare",
    "energy_isolated_gm",
    "energy_driving_force",
    "energy_tzero",
    "property_density_single",
    "property_density_temperature",
    "property_elastic_prepare",
    "property_elastic_vrh",
    "property_strengthening",
    "property_pdb_self_test",
    "property_coverage_view",
    "kinetics_diffusion_single",
    "kinetics_homogenization",
    "kinetics_mobility_coverage",
    "kinetics_precipitation_kwn",
    "data_alloy_state",
    "data_alloy_transfer",
    "data_project_state",
    "data_project_transfer",
    "data_history_state",
    "data_history_export",
    "data_batch_request_import",
    "data_batch_execute",
    "data_batch_export",
    "data_result_artifact",
    "data_database_passport_view",
    "data_install_preflight_view",
    "data_reference_artifact",
)
FEATURE_REGISTRY = {feature_id: FEATURE_REVISION for feature_id in FEATURE_IDS}

BOUND_CONTEXT_FIELDS = (
    "schema", "database_key", "display_label", "profile_key", "patch_id",
    "tdb", "passport", "physical_pdb", "binding_digest",
    "binding_generation", "phase_policy",
)
FEATURE_REQUEST_FIELDS = (
    "schema", "feature_id", "feature_revision", "binding_digest",
    "binding_generation", "inputs", "inputs_digest", "requested_phases",
    "requested_phases_digest", "effective_phases", "effective_phases_digest",
    "request_digest",
)
EXECUTION_LEASE_FIELDS = (
    "schema", "lease_id", "lane_id", "lease_sequence", "feature_id",
    "feature_revision", "binding_digest", "binding_generation",
    "request_digest", "effective_phases_digest", "acquired_at_utc",
    "lease_digest",
)
REJECTION_FIELDS = (
    "schema", "feature_id", "feature_revision", "outcome", "reason_code",
    "reason_detail", "binding_digest", "binding_generation", "inputs_digest",
    "requested_phases_digest", "effective_phases_digest", "request_digest",
    "backend_calls", "rejected_at_utc", "receipt_digest",
)
FEATURE_RECEIPT_FIELDS = (
    "schema", "feature_id", "feature_revision", "outcome", "reason_code",
    "reason_detail", "binding_digest", "binding_generation", "tdb_evidence",
    "passport_evidence", "physical_pdb_evidence", "phase_policy_id",
    "phase_policy_revision", "requested_phases", "requested_phases_digest",
    "effective_phases", "effective_phases_digest", "inputs_digest",
    "request_digest", "lease_id", "backend", "packages", "backend_calls",
    "point_count", "result_digest", "started_at_utc", "finished_at_utc",
    "receipt_digest",
)
RESULT_ENVELOPE_FIELDS = (
    "schema", "feature_id", "feature_revision", "binding_digest",
    "binding_generation", "request_digest", "receipt_digest", "outcome",
    "settings", "settings_digest", "tables", "tables_digest", "figures",
    "figures_digest", "artifacts", "artifacts_digest", "result_digest",
    "created_at_utc", "envelope_digest",
)


class VerifiedLoaderError(RuntimeError):
    """Fail-closed error carrying one frozen reason classification."""

    def __init__(self, reason_code: ReasonCode, detail: str):
        if type(reason_code) is not ReasonCode:
            raise TypeError("reason_code must be a ReasonCode.")
        if type(detail) is not str or not detail or len(detail) > MAX_REASON_DETAIL_CHARS:
            raise TypeError("detail must be bounded non-empty text.")
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code.value}: {detail}")


def _fail(reason_code: ReasonCode, detail: str) -> None:
    raise VerifiedLoaderError(reason_code, detail[:MAX_REASON_DETAIL_CHARS])


def _validate_sha256(value: object, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail(ReasonCode.SCHEMA_INVALID, f"{label} must be lowercase SHA-256.")
    return value


def _validate_timestamp(value: object, label: str) -> str:
    if type(value) is not str or _UTC_Z_RE.fullmatch(value) is None:
        _fail(ReasonCode.SCHEMA_INVALID, f"{label} must be a UTC Z timestamp.")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        _fail(ReasonCode.SCHEMA_INVALID, f"{label} is not a real UTC timestamp.")
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        _fail(ReasonCode.SCHEMA_INVALID, f"{label} is not UTC.")
    return value


def _system_clock() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _clock_value(clock: Callable[[], object]) -> str:
    if not callable(clock):
        _fail(ReasonCode.SCHEMA_INVALID, "Clock seam must be callable.")
    value = clock()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() != timezone.utc.utcoffset(value):
            _fail(ReasonCode.SCHEMA_INVALID, "Clock returned a non-UTC datetime.")
        value = value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )
    return _validate_timestamp(value, "timestamp")


def _walk_canonical(value: object, *, path: str = "$", reject_raw_paths: bool = False) -> None:
    value_type = type(value)
    if value is None or value_type in (str, bool, int):
        return
    if value_type is float:
        if not math.isfinite(value):
            _fail(ReasonCode.CANONICAL_JSON_INVALID, f"{path} is non-finite.")
        return
    if value_type is list:
        for index, child in enumerate(value):
            _walk_canonical(child, path=f"{path}[{index}]", reject_raw_paths=reject_raw_paths)
        return
    if value_type is dict:
        for key, child in value.items():
            if type(key) is not str:
                _fail(ReasonCode.CANONICAL_JSON_INVALID, f"{path} has a non-string key.")
            if reject_raw_paths and key.casefold() in _RAW_PATH_KEYS:
                _fail(ReasonCode.RAW_PATH_REJECTED, f"Raw path field {key!r} is forbidden.")
            _walk_canonical(
                child,
                path=f"{path}.{key}",
                reject_raw_paths=reject_raw_paths,
            )
        return
    _fail(
        ReasonCode.CANONICAL_JSON_INVALID,
        f"{path} has unsupported exact type {value_type.__name__}.",
    )


def canonical_json_bytes(value: object) -> bytes:
    _walk_canonical(value)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeError) as error:
        _fail(ReasonCode.CANONICAL_JSON_INVALID, f"Canonical JSON encoding failed: {error}")


def canonical_digest(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def load_canonical_json(data: bytes) -> object:
    if type(data) is not bytes:
        _fail(ReasonCode.CANONICAL_JSON_INVALID, "Canonical JSON input must be bytes.")
    try:
        text = data.decode("utf-8", errors="strict")
        value = duplicate_reject_json(text)
    except Exception as error:
        _fail(ReasonCode.CANONICAL_JSON_INVALID, f"Canonical JSON parse failed: {error}")
    _walk_canonical(value)
    if canonical_json_bytes(value) != data:
        _fail(ReasonCode.CANONICAL_JSON_INVALID, "JSON bytes are not canonical.")
    return value


def _expect_plain_object(value: object, fields: Sequence[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(fields) or len(value) != len(fields):
        _fail(ReasonCode.SCHEMA_INVALID, f"{label} fields do not match its schema.")
    return value


def _digest_without(payload: Mapping[str, Any], field: str) -> str:
    return canonical_digest({key: value for key, value in payload.items() if key != field})


def _validate_phase_tuple(value: object, label: str, *, allow_empty: bool) -> tuple[str, ...]:
    if type(value) is not tuple or (not allow_empty and not value):
        _fail(ReasonCode.SCHEMA_INVALID, f"{label} must be an immutable phase tuple.")
    if len(set(value)) != len(value):
        _fail(ReasonCode.SCHEMA_INVALID, f"{label} contains duplicates.")
    for phase in value:
        if type(phase) is not str or _PHASE_RE.fullmatch(phase) is None:
            _fail(ReasonCode.SCHEMA_INVALID, f"{label} contains a non-canonical phase.")
    return value


def _phase_tuple_from_json(value: object, label: str, *, allow_empty: bool) -> tuple[str, ...]:
    if type(value) is not list:
        _fail(ReasonCode.SCHEMA_INVALID, f"{label} must be a JSON array.")
    return _validate_phase_tuple(tuple(value), label, allow_empty=allow_empty)


@dataclass(frozen=True, slots=True)
class ArtifactEvidence:
    logical_path: str
    sha256: str
    size_bytes: int
    media_type: str

    def __post_init__(self) -> None:
        if (
            type(self.logical_path) is not str
            or not self.logical_path
            or "\\" in self.logical_path
            or self.logical_path.startswith("/")
            or ":" in self.logical_path
            or any(part in ("", ".", "..") for part in self.logical_path.split("/"))
        ):
            _fail(ReasonCode.SCHEMA_INVALID, "Artifact logical_path is not canonical relative form.")
        _validate_sha256(self.sha256, "artifact.sha256")
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            _fail(ReasonCode.SCHEMA_INVALID, "Artifact size_bytes is invalid.")
        if type(self.media_type) is not str or not self.media_type or len(self.media_type) > 128:
            _fail(ReasonCode.SCHEMA_INVALID, "Artifact media_type is invalid.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "logical_path": self.logical_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
        }

    @classmethod
    def from_dict(cls, value: object) -> "ArtifactEvidence":
        obj = _expect_plain_object(
            value, ("logical_path", "sha256", "size_bytes", "media_type"), "ArtifactEvidence"
        )
        return cls(**obj)


@dataclass(frozen=True, slots=True)
class VerifiedArtifact:
    evidence: ArtifactEvidence
    _snapshot_bytes: bytes = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self._snapshot_bytes) is not bytes:
            _fail(ReasonCode.ARTIFACT_IO_FAILED, "Verified artifact snapshot is not immutable bytes.")
        if len(self._snapshot_bytes) != self.evidence.size_bytes:
            _fail(ReasonCode.ARTIFACT_IO_FAILED, "Verified artifact size evidence mismatch.")

    def verified_text(self) -> str:
        try:
            return strict_utf8_text(self._snapshot_bytes)
        except Exception as error:
            _fail(ReasonCode.ARTIFACT_IO_FAILED, f"Artifact is not strict UTF-8: {error}")


@dataclass(frozen=True, slots=True)
class VerifiedBinaryArtifact:
    evidence: ArtifactEvidence
    _snapshot_bytes: bytes = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self._snapshot_bytes) is not bytes or len(self._snapshot_bytes) != self.evidence.size_bytes:
            _fail(ReasonCode.PDB_INVALID, "Verified binary artifact evidence mismatch.")


@dataclass(frozen=True, slots=True)
class _ArtifactSpec:
    logical_path: str
    sha256: str
    size_bytes: int
    media_type: str
    maximum_bytes: int

    def evidence(self) -> ArtifactEvidence:
        return ArtifactEvidence(
            logical_path=self.logical_path,
            sha256=self.sha256,
            size_bytes=self.size_bytes,
            media_type=self.media_type,
        )


_TDB_SPECS = {
    "ni": _ArtifactSpec(
        "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
        "1882d841a337063e0585d261c690ae7e565838234e231e21b8541a5cb0dba391",
        466074, "application/vnd.thermogar.tdb", MAX_TDB_SNAPSHOT_BYTES,
    ),
    "al": _ArtifactSpec(
        "databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb",
        "f9bdf21d434fbe78b5ef3f7f2de69763fa40b81335cdc58889907d41c80cd717",
        351241, "application/vnd.thermogar.tdb", MAX_TDB_SNAPSHOT_BYTES,
    ),
    "fe": _ArtifactSpec(
        "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb",
        "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612",
        568690, "application/vnd.thermogar.tdb", MAX_TDB_SNAPSHOT_BYTES,
    ),
}
_FE_PASSPORT_SPEC = _ArtifactSpec(
    "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.passport.json",
    "c818f3132840304ea38017cb7419790a290a1ca2e949b01e8954931ac8f17491",
    12393, "application/json", MAX_PASSPORT_BYTES,
)
_PHYSICAL_PDB_SPEC = _ArtifactSpec(
    "databases/physical/original/physical_data_v103.pdb",
    "4cf81c992b57263c50b370ea47eb0d5bb4f622cf23c18479bab54267762f20bd",
    28102, "application/vnd.thermogar.pdb", MAX_PHYSICAL_PDB_BYTES,
)
_DISPLAY_LABELS = {
    "ni": "Nickel alloys - mc_ni 2.036",
    "al": "Aluminium alloys - mc_al 2.037",
    "fe": "Steel/Fe - mc_fe 2.062 thermogar_patch",
}


def canonical_release_manifest() -> dict[str, Any]:
    def artifact(spec: _ArtifactSpec) -> dict[str, Any]:
        return spec.evidence().to_dict()

    return {
        "schema": "thermogar.artifact-catalog-policy.v1",
        "databases": {
            "ni": {
                "display_label": _DISPLAY_LABELS["ni"], "profile_key": None,
                "patch_id": None, "tdb": artifact(_TDB_SPECS["ni"]), "passport": None,
            },
            "al": {
                "display_label": _DISPLAY_LABELS["al"], "profile_key": None,
                "patch_id": None, "tdb": artifact(_TDB_SPECS["al"]), "passport": None,
            },
            "fe": {
                "display_label": _DISPLAY_LABELS["fe"], "profile_key": "thermogar_patch",
                "patch_id": FE_PATCH_ID, "tdb": artifact(_TDB_SPECS["fe"]),
                "passport": artifact(_FE_PASSPORT_SPEC),
            },
        },
        "physical_pdb": artifact(_PHYSICAL_PDB_SPEC),
    }


def _classify_policy_mismatch(actual: object, expected: object, path: str = "policy") -> None:
    if type(actual) is not type(expected):
        _fail(ReasonCode.SCHEMA_INVALID, f"{path} has an unexpected exact type.")
    if type(expected) is dict:
        if set(actual) != set(expected):
            _fail(ReasonCode.SCHEMA_INVALID, f"{path} has unknown or missing fields.")
        for key in expected:
            _classify_policy_mismatch(actual[key], expected[key], f"{path}.{key}")
        return
    if actual == expected:
        return
    lowered = path.casefold()
    if lowered.endswith("logical_path"):
        _fail(ReasonCode.ARTIFACT_PATH_REJECTED, f"{path} is not allowlisted.")
    if lowered.endswith("sha256"):
        if "passport" in lowered:
            reason = ReasonCode.PASSPORT_HASH_MISMATCH
        elif "physical_pdb" in lowered:
            reason = ReasonCode.PDB_HASH_MISMATCH
        else:
            reason = ReasonCode.TDB_HASH_MISMATCH
        _fail(reason, f"{path} does not match the pinned digest.")
    if lowered.endswith("profile_key"):
        token = str(actual).casefold()
        reason = (
            ReasonCode.UPSTREAM_PROFILE_REJECTED
            if any(part in token for part in ("upstream", "unpatched", "diagnostic"))
            else ReasonCode.PROFILE_KEY_REJECTED
        )
        _fail(reason, f"{path} is not the canonical profile.")
    if lowered.endswith("patch_id"):
        _fail(ReasonCode.PATCH_ID_MISMATCH, f"{path} is not the pinned patch.")
    _fail(ReasonCode.SCHEMA_INVALID, f"{path} differs from the frozen policy.")


def _default_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class ArtifactCatalog:
    """Read-only, allowlist-backed immutable artifact source."""

    __slots__ = ("_root", "_snapshot_reader", "_digest_function", "_phase_provider")

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        _fail(ReasonCode.SCHEMA_INVALID, "Use ArtifactCatalog.from_policy().")

    @classmethod
    def from_policy(
        cls,
        installation_root: str | Path,
        release_manifest: Mapping[str, Any],
        *,
        snapshot_reader: Callable[..., object] = read_verified_snapshot,
        digest_function: Callable[[bytes], str] = _default_digest,
        phase_provider: Callable[[VerifiedArtifact], Sequence[str]] | None = None,
    ) -> "ArtifactCatalog":
        if type(release_manifest) is not dict:
            _fail(ReasonCode.SCHEMA_INVALID, "Release manifest must be a plain object.")
        _walk_canonical(release_manifest)
        _classify_policy_mismatch(release_manifest, canonical_release_manifest())
        if not callable(snapshot_reader) or not callable(digest_function):
            _fail(ReasonCode.SCHEMA_INVALID, "Artifact seams must be callable.")
        if phase_provider is not None and not callable(phase_provider):
            _fail(ReasonCode.SCHEMA_INVALID, "Phase provider seam must be callable.")
        try:
            root = Path(os.path.abspath(os.fspath(installation_root)))
            if not root.is_absolute():
                raise ValueError("not absolute")
            assert_plain_path(root, leaf_must_be_directory=True)
        except Exception as error:
            _fail(ReasonCode.ARTIFACT_PATH_REJECTED, f"Installation root is unusable: {error}")
        instance = object.__new__(cls)
        instance._root = root
        instance._snapshot_reader = snapshot_reader
        instance._digest_function = digest_function
        instance._phase_provider = phase_provider
        return instance

    def _read(self, spec: _ArtifactSpec, hash_reason: ReasonCode) -> bytes:
        candidate = Path(os.path.abspath(str(self._root / Path(*spec.logical_path.split("/")))))
        try:
            if os.path.commonpath((str(candidate), str(self._root))) != str(self._root):
                _fail(ReasonCode.ARTIFACT_PATH_REJECTED, "Artifact escaped installation root.")
            snapshot = self._snapshot_reader(
                candidate,
                expected_sha256=spec.sha256,
                maximum_bytes=spec.maximum_bytes,
                canonical_root=self._root,
            )
            data = snapshot.data
        except VerifiedLoaderError:
            raise
        except FileNotFoundError:
            _fail(ReasonCode.ARTIFACT_MISSING, f"Pinned artifact is missing: {spec.logical_path}")
        except Exception as error:
            detail = str(error)
            if "bounded snapshot limit" in detail or "exceeds" in detail:
                reason = ReasonCode.ARTIFACT_OVERSIZE
            elif "SHA-256" in detail or "digest" in detail:
                reason = hash_reason
            else:
                reason = ReasonCode.ARTIFACT_IO_FAILED
            _fail(reason, f"Pinned artifact read failed: {detail}")
        if type(data) is not bytes:
            _fail(ReasonCode.ARTIFACT_IO_FAILED, "Snapshot reader returned mutable/non-byte data.")
        if len(data) > spec.maximum_bytes:
            _fail(ReasonCode.ARTIFACT_OVERSIZE, "Artifact exceeds its bounded snapshot limit.")
        if len(data) != spec.size_bytes:
            _fail(hash_reason, "Artifact byte count differs from pinned evidence.")
        try:
            observed = self._digest_function(data)
        except Exception as error:
            _fail(ReasonCode.ARTIFACT_IO_FAILED, f"Digest seam failed: {error}")
        if type(observed) is not str or observed != spec.sha256:
            _fail(hash_reason, "Artifact bytes differ from the pinned SHA-256.")
        return data

    def open_tdb(self, database_key: str, profile_key: str | None) -> VerifiedArtifact:
        database_key, profile_key = _validate_database_selection(database_key, profile_key)
        data = self._read(_TDB_SPECS[database_key], ReasonCode.TDB_HASH_MISMATCH)
        try:
            strict_utf8_text(data)
        except Exception as error:
            _fail(ReasonCode.ARTIFACT_IO_FAILED, f"TDB is not strict UTF-8: {error}")
        return VerifiedArtifact(_TDB_SPECS[database_key].evidence(), data)

    def open_passport(self, profile_key: str | None) -> VerifiedArtifact | None:
        if profile_key is None:
            return None
        token = str(profile_key).casefold() if type(profile_key) is str else ""
        if any(part in token for part in ("upstream", "unpatched", "diagnostic")):
            _fail(ReasonCode.UPSTREAM_PROFILE_REJECTED, "Upstream/unpatched Fe profile is forbidden.")
        if profile_key != "thermogar_patch":
            _fail(ReasonCode.PROFILE_KEY_REJECTED, "Only thermogar_patch has a passport.")
        data = self._read(_FE_PASSPORT_SPEC, ReasonCode.PASSPORT_HASH_MISMATCH)
        artifact = VerifiedArtifact(_FE_PASSPORT_SPEC.evidence(), data)
        _validate_fe_passport(artifact.verified_text())
        return artifact

    def open_physical_dataset(self) -> VerifiedBinaryArtifact:
        data = self._read(_PHYSICAL_PDB_SPEC, ReasonCode.PDB_HASH_MISMATCH)
        try:
            text = strict_utf8_text(data)
        except Exception as error:
            _fail(ReasonCode.PDB_INVALID, f"Physical dataset is not strict UTF-8: {error}")
        if "$thermo-physical" not in text or "DEFINE_PARAMETER DP density!" not in text:
            _fail(ReasonCode.PDB_INVALID, "Physical dataset identity markers are absent.")
        return VerifiedBinaryArtifact(_PHYSICAL_PDB_SPEC.evidence(), data)

    def phase_candidates(self, artifact: VerifiedArtifact) -> tuple[str, ...]:
        if self._phase_provider is None:
            _fail(
                ReasonCode.CAPABILITY_UNAVAILABLE,
                "B1 phase parser is an injected seam and has no production implementation.",
            )
        try:
            raw = self._phase_provider(artifact)
        except VerifiedLoaderError:
            raise
        except Exception as error:
            _fail(ReasonCode.PHASE_POLICY_MISMATCH, f"Phase provider failed: {error}")
        if isinstance(raw, (str, bytes)):
            _fail(ReasonCode.PHASE_POLICY_MISMATCH, "Phase provider returned a scalar.")
        try:
            phases = tuple(raw)
        except TypeError:
            _fail(ReasonCode.PHASE_POLICY_MISMATCH, "Phase provider is not iterable.")
        _validate_phase_tuple(phases, "phase candidates", allow_empty=False)
        return tuple(sorted(phases))


def _validate_database_selection(
    database_key: object, profile_key: object
) -> tuple[str, str | None]:
    if type(database_key) is not str or database_key not in _TDB_SPECS:
        _fail(ReasonCode.DATABASE_KEY_REJECTED, "Database key is outside ni/al/fe allowlist.")
    if database_key == "fe":
        token = str(profile_key).casefold() if type(profile_key) is str else ""
        if any(part in token for part in ("upstream", "unpatched", "diagnostic", "original")):
            _fail(ReasonCode.UPSTREAM_PROFILE_REJECTED, "Upstream/unpatched Fe profile is forbidden.")
        if profile_key != "thermogar_patch":
            _fail(ReasonCode.PROFILE_KEY_REJECTED, "Fe requires thermogar_patch.")
        return database_key, profile_key
    if profile_key is not None:
        _fail(ReasonCode.PROFILE_KEY_REJECTED, "Ni/Al do not admit a profile key.")
    return database_key, None


def _validate_fe_passport(text: str) -> dict[str, Any]:
    try:
        payload = duplicate_reject_json(text)
    except Exception as error:
        _fail(ReasonCode.PASSPORT_INVALID, f"Passport JSON is invalid: {error}")
    if type(payload) is not dict:
        _fail(ReasonCode.PASSPORT_INVALID, "Passport must be a JSON object.")
    if payload.get("schema_version") != 2 or payload.get("profile_id") != "mc_fe_v2062_thermogar_working":
        _fail(ReasonCode.PASSPORT_INVALID, "Passport schema/profile identity mismatch.")
    if payload.get("patch_id") != FE_PATCH_ID:
        _fail(ReasonCode.PATCH_ID_MISMATCH, "Passport patch_id mismatch.")
    working = payload.get("working_profile")
    combined = working.get("thermodynamic_plus_mobility_database") if type(working) is dict else None
    if type(combined) is not dict or str(combined.get("sha256", "")).lower() != _TDB_SPECS["fe"].sha256:
        _fail(ReasonCode.PASSPORT_HASH_MISMATCH, "Passport TDB witness mismatch.")
    patches = payload.get("compatibility_patches")
    if type(patches) is not list or len(patches) != 1 or type(patches[0]) is not dict:
        _fail(ReasonCode.PASSPORT_INVALID, "Passport patch witness must be singular.")
    patch = patches[0]
    if patch.get("patch_id") != FE_PATCH_ID:
        _fail(ReasonCode.PATCH_ID_MISMATCH, "Passport patch witness ID mismatch.")
    if (
        patch.get("phase") != C15_PHASE
        or patch.get("applied") is not True
        or patch.get("matched_active_commands") != 1
    ):
        _fail(ReasonCode.PASSPORT_INVALID, "Passport patch witness is invalid.")
    return payload


@dataclass(frozen=True, slots=True)
class PhasePolicy:
    policy_id: str
    policy_revision: str
    eligible_phases: tuple[str, ...]
    eligible_phases_digest: str
    automatic_exclusions: tuple[str, ...]
    explicit_rejections: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.policy_id) is not str or not self.policy_id:
            _fail(ReasonCode.SCHEMA_INVALID, "Phase policy ID is invalid.")
        if self.policy_revision != FEATURE_REVISION:
            _fail(ReasonCode.SCHEMA_INVALID, "Phase policy revision is invalid.")
        _validate_phase_tuple(self.eligible_phases, "eligible_phases", allow_empty=False)
        if self.eligible_phases != tuple(sorted(self.eligible_phases)):
            _fail(ReasonCode.SCHEMA_INVALID, "Eligible phases are not deterministic.")
        if self.eligible_phases_digest != canonical_digest(list(self.eligible_phases)):
            _fail(ReasonCode.SCHEMA_INVALID, "Eligible phase digest mismatch.")
        _validate_phase_tuple(self.automatic_exclusions, "automatic_exclusions", allow_empty=True)
        _validate_phase_tuple(self.explicit_rejections, "explicit_rejections", allow_empty=True)
        if any(phase in self.eligible_phases for phase in self.automatic_exclusions):
            _fail(ReasonCode.PHASE_POLICY_MISMATCH, "Excluded phase remains eligible.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "policy_revision": self.policy_revision,
            "eligible_phases": list(self.eligible_phases),
            "eligible_phases_digest": self.eligible_phases_digest,
            "automatic_exclusions": list(self.automatic_exclusions),
            "explicit_rejections": list(self.explicit_rejections),
        }

    @classmethod
    def from_dict(cls, value: object) -> "PhasePolicy":
        obj = _expect_plain_object(
            value,
            (
                "policy_id", "policy_revision", "eligible_phases",
                "eligible_phases_digest", "automatic_exclusions", "explicit_rejections",
            ),
            "PhasePolicy",
        )
        return cls(
            policy_id=obj["policy_id"],
            policy_revision=obj["policy_revision"],
            eligible_phases=_phase_tuple_from_json(obj["eligible_phases"], "eligible_phases", allow_empty=False),
            eligible_phases_digest=obj["eligible_phases_digest"],
            automatic_exclusions=_phase_tuple_from_json(obj["automatic_exclusions"], "automatic_exclusions", allow_empty=True),
            explicit_rejections=_phase_tuple_from_json(obj["explicit_rejections"], "explicit_rejections", allow_empty=True),
        )

    def effective(
        self,
        requested: Sequence[str] | None,
        candidates: Sequence[str] | None = None,
    ) -> tuple[str, ...]:
        if requested is not None and isinstance(requested, (str, bytes)):
            _fail(ReasonCode.INPUT_INVALID, "Requested phases must be a sequence.")
        requested_tuple = () if requested is None else tuple(requested)
        _validate_phase_tuple(requested_tuple, "requested phases", allow_empty=True)
        if C15_PHASE in requested_tuple or any(
            phase in self.explicit_rejections for phase in requested_tuple
        ):
            _fail(ReasonCode.C15_PHASE_REJECTED, "C15_LAVES is rejected before dispatch.")
        eligible = self.eligible_phases
        if candidates is not None:
            if isinstance(candidates, (str, bytes)):
                _fail(ReasonCode.PHASE_POLICY_MISMATCH, "Candidates must be a sequence.")
            candidate_tuple = tuple(candidates)
            _validate_phase_tuple(candidate_tuple, "phase candidates", allow_empty=False)
            candidate_set = set(candidate_tuple)
            eligible = tuple(phase for phase in eligible if phase in candidate_set)
        if requested_tuple:
            unknown = tuple(phase for phase in requested_tuple if phase not in eligible)
            if unknown:
                _fail(ReasonCode.PHASE_NOT_PRESENT, f"Requested phase is not eligible: {unknown[0]}")
            requested_set = set(requested_tuple)
            eligible = tuple(phase for phase in eligible if phase in requested_set)
        if not eligible:
            _fail(ReasonCode.PHASE_SET_EMPTY, "Effective phase set is empty.")
        if C15_PHASE in eligible:
            _fail(ReasonCode.PHASE_POLICY_MISMATCH, "C15_LAVES survived phase policy.")
        return eligible


@dataclass(frozen=True, slots=True)
class BoundDatabaseContext:
    schema: str
    database_key: str
    display_label: str
    profile_key: str | None
    patch_id: str | None
    tdb: ArtifactEvidence
    passport: ArtifactEvidence | None
    physical_pdb: ArtifactEvidence | None
    binding_digest: str
    binding_generation: int
    phase_policy: PhasePolicy

    def __post_init__(self) -> None:
        if self.schema != SCHEMA_BOUND_CONTEXT:
            _fail(ReasonCode.SCHEMA_INVALID, "Bound context schema mismatch.")
        _validate_database_selection(self.database_key, self.profile_key)
        if self.display_label != _DISPLAY_LABELS[self.database_key]:
            _fail(ReasonCode.BINDING_IDENTITY_MISMATCH, "Display label is not catalog-bound.")
        if self.patch_id != (FE_PATCH_ID if self.database_key == "fe" else None):
            _fail(ReasonCode.PATCH_ID_MISMATCH, "Context patch identity mismatch.")
        if type(self.tdb) is not ArtifactEvidence:
            _fail(ReasonCode.SCHEMA_INVALID, "Context TDB evidence type mismatch.")
        if self.tdb != _TDB_SPECS[self.database_key].evidence():
            _fail(ReasonCode.BINDING_IDENTITY_MISMATCH, "Context TDB evidence mismatch.")
        if self.database_key == "fe":
            if self.passport != _FE_PASSPORT_SPEC.evidence():
                _fail(ReasonCode.PASSPORT_REQUIRED, "Canonical Fe passport evidence is required.")
        elif self.passport is not None:
            _fail(ReasonCode.BINDING_IDENTITY_MISMATCH, "Ni/Al passport evidence must be null.")
        if self.physical_pdb is not None and self.physical_pdb != _PHYSICAL_PDB_SPEC.evidence():
            _fail(ReasonCode.BINDING_IDENTITY_MISMATCH, "Physical PDB evidence mismatch.")
        if type(self.binding_generation) is not int or self.binding_generation <= 0:
            _fail(ReasonCode.SCHEMA_INVALID, "Binding generation is invalid.")
        _validate_sha256(self.binding_digest, "binding_digest")
        if self.binding_digest != _digest_without(self.to_dict(), "binding_digest"):
            _fail(ReasonCode.BINDING_IDENTITY_MISMATCH, "Binding digest mismatch.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "database_key": self.database_key,
            "display_label": self.display_label,
            "profile_key": self.profile_key,
            "patch_id": self.patch_id,
            "tdb": self.tdb.to_dict(),
            "passport": None if self.passport is None else self.passport.to_dict(),
            "physical_pdb": None if self.physical_pdb is None else self.physical_pdb.to_dict(),
            "binding_digest": self.binding_digest,
            "binding_generation": self.binding_generation,
            "phase_policy": self.phase_policy.to_dict(),
        }

    def to_json_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @classmethod
    def from_json_bytes(cls, data: bytes) -> "BoundDatabaseContext":
        obj = _expect_plain_object(load_canonical_json(data), BOUND_CONTEXT_FIELDS, "BoundDatabaseContext")
        return cls(
            schema=obj["schema"], database_key=obj["database_key"], display_label=obj["display_label"],
            profile_key=obj["profile_key"], patch_id=obj["patch_id"],
            tdb=ArtifactEvidence.from_dict(obj["tdb"]),
            passport=None if obj["passport"] is None else ArtifactEvidence.from_dict(obj["passport"]),
            physical_pdb=None if obj["physical_pdb"] is None else ArtifactEvidence.from_dict(obj["physical_pdb"]),
            binding_digest=obj["binding_digest"], binding_generation=obj["binding_generation"],
            phase_policy=PhasePolicy.from_dict(obj["phase_policy"]),
        )


@dataclass(frozen=True, slots=True)
class _PayloadBundle:
    tdb: VerifiedArtifact
    passport: VerifiedArtifact | None
    physical_pdb: VerifiedBinaryArtifact | None
    phase_policy: PhasePolicy


class _FifoLane:
    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.next_ticket = 1
        self.serving_ticket = 1
        self.active = False

    def reserve_and_enter(self) -> int:
        with self.condition:
            ticket = self.next_ticket
            self.next_ticket += 1
            while ticket != self.serving_ticket or self.active:
                self.condition.wait()
            self.active = True
            return ticket

    def leave(self, ticket: int) -> None:
        with self.condition:
            if not self.active or ticket != self.serving_ticket:
                _fail(ReasonCode.LEASE_IDENTITY_MISMATCH, "FIFO lease release identity mismatch.")
            self.active = False
            self.serving_ticket += 1
            self.condition.notify_all()

    def wait_idle(self) -> None:
        with self.condition:
            while self.active:
                self.condition.wait()


class _BindingRuntime:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.generation = 0
        self.proof_digest: str | None = None
        self.binding_digest: str | None = None
        self.payload: _PayloadBundle | None = None
        self.parser_cache: dict[tuple[str, str, str], object] = {}
        self.lane = _FifoLane()

    def begin_binding(self, proof_digest: str) -> int:
        changed = False
        with self.lock:
            if proof_digest != self.proof_digest:
                self.generation += 1
                self.proof_digest = proof_digest
                self.binding_digest = None
                self.payload = None
                self.parser_cache.clear()
                changed = True
            generation = self.generation
        if changed:
            self.lane.wait_idle()
        return generation

    def commit_binding(self, context: BoundDatabaseContext, payload: _PayloadBundle) -> None:
        with self.lock:
            if context.binding_generation != self.generation:
                _fail(ReasonCode.GENERATION_STALE, "Generation changed during binding.")
            self.binding_digest = context.binding_digest
            self.payload = payload

    def require_current(self, binding_digest: str, generation: int) -> _PayloadBundle:
        with self.lock:
            if generation != self.generation:
                _fail(ReasonCode.GENERATION_STALE, "Binding generation is stale.")
            if binding_digest != self.binding_digest or self.payload is None:
                _fail(ReasonCode.BINDING_STALE, "Binding identity is not current.")
            return self.payload

    def invalidate(self) -> int:
        with self.lock:
            self.generation += 1
            self.proof_digest = None
            self.binding_digest = None
            self.payload = None
            self.parser_cache.clear()
            return self.generation


_RUNTIME = _BindingRuntime()


def invalidate_binding_generation() -> int:
    """Invalidate current binding and every generation-scoped in-memory cache."""

    return _RUNTIME.invalidate()


def _selector_fields(selector: object) -> tuple[str, str | None, bool]:
    if type(selector) is not dict:
        _fail(ReasonCode.SCHEMA_INVALID, "Database selector must be a plain object.")
    raw_fields = set(selector).intersection(_RAW_PATH_KEYS)
    if raw_fields:
        _fail(ReasonCode.RAW_PATH_REJECTED, f"Raw selector path field is forbidden: {sorted(raw_fields)[0]}")
    allowed = {"database_key", "profile_key", "include_physical_pdb"}
    if not set(selector).issubset(allowed) or "database_key" not in selector:
        _fail(ReasonCode.SCHEMA_INVALID, "Database selector has unknown or missing fields.")
    include = selector.get("include_physical_pdb", False)
    if type(include) is not bool:
        _fail(ReasonCode.SCHEMA_INVALID, "include_physical_pdb must be boolean.")
    database_key, profile_key = _validate_database_selection(
        selector["database_key"], selector.get("profile_key")
    )
    return database_key, profile_key, include


def bind_selected_database(
    selector: Mapping[str, Any],
    catalog: ArtifactCatalog,
    paths: object,
) -> BoundDatabaseContext:
    if type(catalog) is not ArtifactCatalog:
        _fail(ReasonCode.SCHEMA_INVALID, "Catalog must be the closed ArtifactCatalog type.")
    if paths is None or isinstance(paths, (str, bytes, Path)):
        _fail(ReasonCode.RAW_PATH_REJECTED, "An injected ThermoGarPaths-like object is required.")
    database_key, profile_key, include_physical = _selector_fields(selector)
    tdb = catalog.open_tdb(database_key, profile_key)
    passport = catalog.open_passport(profile_key) if database_key == "fe" else None
    if database_key == "fe" and passport is None:
        _fail(ReasonCode.PASSPORT_REQUIRED, "Canonical Fe passport is required.")
    physical = catalog.open_physical_dataset() if include_physical else None
    candidates = catalog.phase_candidates(tdb)
    automatic_exclusions = (C15_PHASE,) if database_key == "fe" else ()
    explicit_rejections = (C15_PHASE,)
    eligible = tuple(sorted(phase for phase in candidates if phase not in automatic_exclusions))
    if not eligible:
        _fail(ReasonCode.PHASE_SET_EMPTY, "Catalog phase set is empty after policy.")
    phase_policy = PhasePolicy(
        policy_id=("thermogar.fe-c15-exclusion@1" if database_key == "fe" else "thermogar.standard-phase-policy@1"),
        policy_revision=FEATURE_REVISION,
        eligible_phases=eligible,
        eligible_phases_digest=canonical_digest(list(eligible)),
        automatic_exclusions=automatic_exclusions,
        explicit_rejections=explicit_rejections,
    )
    proof = {
        "database_key": database_key,
        "profile_key": profile_key,
        "patch_id": FE_PATCH_ID if database_key == "fe" else None,
        "tdb": tdb.evidence.to_dict(),
        "passport": None if passport is None else passport.evidence.to_dict(),
        "physical_pdb": None if physical is None else physical.evidence.to_dict(),
        "phase_policy": phase_policy.to_dict(),
    }
    generation = _RUNTIME.begin_binding(canonical_digest(proof))
    provisional = {
        "schema": SCHEMA_BOUND_CONTEXT,
        "database_key": database_key,
        "display_label": _DISPLAY_LABELS[database_key],
        "profile_key": profile_key,
        "patch_id": FE_PATCH_ID if database_key == "fe" else None,
        "tdb": tdb.evidence.to_dict(),
        "passport": None if passport is None else passport.evidence.to_dict(),
        "physical_pdb": None if physical is None else physical.evidence.to_dict(),
        "binding_digest": "",
        "binding_generation": generation,
        "phase_policy": phase_policy.to_dict(),
    }
    binding_digest = _digest_without(provisional, "binding_digest")
    context = BoundDatabaseContext(
        schema=SCHEMA_BOUND_CONTEXT,
        database_key=database_key,
        display_label=_DISPLAY_LABELS[database_key],
        profile_key=profile_key,
        patch_id=FE_PATCH_ID if database_key == "fe" else None,
        tdb=tdb.evidence,
        passport=None if passport is None else passport.evidence,
        physical_pdb=None if physical is None else physical.evidence,
        binding_digest=binding_digest,
        binding_generation=generation,
        phase_policy=phase_policy,
    )
    _RUNTIME.commit_binding(context, _PayloadBundle(tdb, passport, physical, phase_policy))
    return context


@dataclass(frozen=True, slots=True)
class FeatureRequest:
    schema: str
    feature_id: str
    feature_revision: str
    binding_digest: str
    binding_generation: int
    inputs: dict[str, Any]
    inputs_digest: str
    requested_phases: tuple[str, ...]
    requested_phases_digest: str
    effective_phases: tuple[str, ...]
    effective_phases_digest: str
    request_digest: str

    def __post_init__(self) -> None:
        if self.schema != SCHEMA_FEATURE_REQUEST:
            _fail(ReasonCode.SCHEMA_INVALID, "Feature request schema mismatch.")
        if self.feature_id not in FEATURE_REGISTRY:
            _fail(ReasonCode.FEATURE_ID_UNKNOWN, "Feature ID is not registered.")
        if self.feature_revision != FEATURE_REGISTRY[self.feature_id]:
            _fail(ReasonCode.FEATURE_REVISION_UNSUPPORTED, "Feature revision is unsupported.")
        _validate_sha256(self.binding_digest, "binding_digest")
        if type(self.binding_generation) is not int or self.binding_generation <= 0:
            _fail(ReasonCode.SCHEMA_INVALID, "Request generation is invalid.")
        if type(self.inputs) is not dict:
            _fail(ReasonCode.INPUT_INVALID, "Feature inputs must be a plain object.")
        _walk_canonical(self.inputs, reject_raw_paths=True)
        if self.inputs_digest != canonical_digest(self.inputs):
            _fail(ReasonCode.REQUEST_DIGEST_MISMATCH, "Inputs digest mismatch.")
        _validate_phase_tuple(self.requested_phases, "requested_phases", allow_empty=True)
        _validate_phase_tuple(self.effective_phases, "effective_phases", allow_empty=False)
        if self.requested_phases_digest != canonical_digest(list(self.requested_phases)):
            _fail(ReasonCode.REQUEST_DIGEST_MISMATCH, "Requested phase digest mismatch.")
        if self.effective_phases_digest != canonical_digest(list(self.effective_phases)):
            _fail(ReasonCode.REQUEST_DIGEST_MISMATCH, "Effective phase digest mismatch.")
        _validate_sha256(self.request_digest, "request_digest")
        if self.request_digest != _digest_without(self.to_dict(), "request_digest"):
            _fail(ReasonCode.REQUEST_DIGEST_MISMATCH, "Feature request digest mismatch.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "feature_id": self.feature_id,
            "feature_revision": self.feature_revision,
            "binding_digest": self.binding_digest,
            "binding_generation": self.binding_generation,
            "inputs": self.inputs,
            "inputs_digest": self.inputs_digest,
            "requested_phases": list(self.requested_phases),
            "requested_phases_digest": self.requested_phases_digest,
            "effective_phases": list(self.effective_phases),
            "effective_phases_digest": self.effective_phases_digest,
            "request_digest": self.request_digest,
        }

    def to_json_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @classmethod
    def from_json_bytes(cls, data: bytes) -> "FeatureRequest":
        obj = _expect_plain_object(load_canonical_json(data), FEATURE_REQUEST_FIELDS, "FeatureRequest")
        return cls(
            schema=obj["schema"], feature_id=obj["feature_id"], feature_revision=obj["feature_revision"],
            binding_digest=obj["binding_digest"], binding_generation=obj["binding_generation"],
            inputs=obj["inputs"], inputs_digest=obj["inputs_digest"],
            requested_phases=_phase_tuple_from_json(obj["requested_phases"], "requested_phases", allow_empty=True),
            requested_phases_digest=obj["requested_phases_digest"],
            effective_phases=_phase_tuple_from_json(obj["effective_phases"], "effective_phases", allow_empty=False),
            effective_phases_digest=obj["effective_phases_digest"], request_digest=obj["request_digest"],
        )


@dataclass(frozen=True, slots=True)
class RejectedFeatureReceipt:
    schema: str
    feature_id: str | None
    feature_revision: str | None
    outcome: str
    reason_code: str
    reason_detail: str
    binding_digest: str | None
    binding_generation: int | None
    inputs_digest: str | None
    requested_phases_digest: str | None
    effective_phases_digest: str | None
    request_digest: str | None
    backend_calls: int
    rejected_at_utc: str
    receipt_digest: str

    def __post_init__(self) -> None:
        if self.schema != SCHEMA_REJECTION or self.outcome not in ("rejected", "unavailable"):
            _fail(ReasonCode.SCHEMA_INVALID, "Rejected receipt schema/outcome mismatch.")
        if type(self.reason_code) is not str or self.reason_code not in {item.value for item in ReasonCode}:
            _fail(ReasonCode.RECEIPT_INVALID, "Rejected receipt reason is not in the closed set.")
        if type(self.reason_detail) is not str or not self.reason_detail or len(self.reason_detail) > MAX_REASON_DETAIL_CHARS:
            _fail(ReasonCode.RECEIPT_INVALID, "Rejected receipt detail is invalid.")
        if self.feature_id is not None and type(self.feature_id) is not str:
            _fail(ReasonCode.RECEIPT_INVALID, "Rejected feature_id must be text or null.")
        if self.feature_revision is not None and type(self.feature_revision) is not str:
            _fail(ReasonCode.RECEIPT_INVALID, "Rejected feature revision must be text or null.")
        for label, digest in (
            ("binding_digest", self.binding_digest), ("inputs_digest", self.inputs_digest),
            ("requested_phases_digest", self.requested_phases_digest),
            ("effective_phases_digest", self.effective_phases_digest),
            ("request_digest", self.request_digest),
        ):
            if digest is not None:
                _validate_sha256(digest, label)
        if self.binding_generation is not None and (
            type(self.binding_generation) is not int or self.binding_generation <= 0
        ):
            _fail(ReasonCode.RECEIPT_INVALID, "Rejected binding generation is invalid.")
        if self.backend_calls != 0:
            _fail(ReasonCode.RECEIPT_INVALID, "Pre-dispatch rejection must have backend_calls=0.")
        _validate_timestamp(self.rejected_at_utc, "rejected_at_utc")
        if self.receipt_digest != _digest_without(self.to_dict(), "receipt_digest"):
            _fail(ReasonCode.RECEIPT_INVALID, "Rejected receipt digest mismatch.")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in REJECTION_FIELDS}

    def to_json_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @classmethod
    def from_json_bytes(cls, data: bytes) -> "RejectedFeatureReceipt":
        obj = _expect_plain_object(load_canonical_json(data), REJECTION_FIELDS, "RejectedFeatureReceipt")
        return cls(**obj)


def _make_rejection(
    reason: ReasonCode,
    detail: str,
    *,
    feature_id: str | None,
    feature_revision: str | None,
    context: BoundDatabaseContext | None,
    inputs_digest: str | None,
    requested_phases_digest: str | None,
    effective_phases_digest: str | None,
    request_digest: str | None,
    clock: Callable[[], object],
    outcome: str = "rejected",
) -> RejectedFeatureReceipt:
    payload = {
        "schema": SCHEMA_REJECTION,
        "feature_id": feature_id,
        "feature_revision": feature_revision,
        "outcome": outcome,
        "reason_code": reason.value,
        "reason_detail": detail[:MAX_REASON_DETAIL_CHARS],
        "binding_digest": None if context is None else context.binding_digest,
        "binding_generation": None if context is None else context.binding_generation,
        "inputs_digest": inputs_digest,
        "requested_phases_digest": requested_phases_digest,
        "effective_phases_digest": effective_phases_digest,
        "request_digest": request_digest,
        "backend_calls": 0,
        "rejected_at_utc": _clock_value(clock),
        "receipt_digest": "",
    }
    payload["receipt_digest"] = _digest_without(payload, "receipt_digest")
    return RejectedFeatureReceipt(**payload)


def prepare_feature_request(
    feature_id: str,
    context: BoundDatabaseContext,
    inputs: Mapping[str, Any],
    requested_phases: Sequence[str] | None,
    *,
    candidate_phases: tuple[str, ...] | None = None,
    feature_revision: str = FEATURE_REVISION,
    clock: Callable[[], object] = _system_clock,
) -> FeatureRequest | RejectedFeatureReceipt:
    safe_feature = feature_id if type(feature_id) is str else None
    if type(feature_id) is not str or feature_id not in FEATURE_REGISTRY:
        return _make_rejection(
            ReasonCode.FEATURE_ID_UNKNOWN, "Feature ID is not registered.",
            feature_id=safe_feature, feature_revision=None, context=context if type(context) is BoundDatabaseContext else None,
            inputs_digest=None, requested_phases_digest=None, effective_phases_digest=None,
            request_digest=None, clock=clock,
        )
    if feature_revision != FEATURE_REGISTRY[feature_id]:
        return _make_rejection(
            ReasonCode.FEATURE_REVISION_UNSUPPORTED, "Feature revision is unsupported.",
            feature_id=feature_id, feature_revision=feature_revision if type(feature_revision) is str else None,
            context=context if type(context) is BoundDatabaseContext else None,
            inputs_digest=None, requested_phases_digest=None, effective_phases_digest=None,
            request_digest=None, clock=clock,
        )
    if type(context) is not BoundDatabaseContext:
        return _make_rejection(
            ReasonCode.BINDING_IDENTITY_MISMATCH, "Context is not the frozen bound type.",
            feature_id=feature_id, feature_revision=FEATURE_REVISION, context=None,
            inputs_digest=None, requested_phases_digest=None, effective_phases_digest=None,
            request_digest=None, clock=clock,
        )
    try:
        _RUNTIME.require_current(context.binding_digest, context.binding_generation)
    except VerifiedLoaderError as error:
        return _make_rejection(
            error.reason_code, error.detail, feature_id=feature_id, feature_revision=FEATURE_REVISION,
            context=context, inputs_digest=None, requested_phases_digest=None,
            effective_phases_digest=None, request_digest=None, clock=clock,
        )
    if type(inputs) is not dict:
        return _make_rejection(
            ReasonCode.INPUT_INVALID, "Feature inputs must be a plain object.",
            feature_id=feature_id, feature_revision=FEATURE_REVISION, context=context,
            inputs_digest=None, requested_phases_digest=None, effective_phases_digest=None,
            request_digest=None, clock=clock,
        )
    try:
        _walk_canonical(inputs, reject_raw_paths=True)
        safe_inputs = json.loads(canonical_json_bytes(inputs).decode("utf-8"))
        inputs_digest = canonical_digest(safe_inputs)
    except VerifiedLoaderError as error:
        reason = ReasonCode.RAW_PATH_REJECTED if error.reason_code == ReasonCode.RAW_PATH_REJECTED else ReasonCode.INPUT_INVALID
        return _make_rejection(
            reason, error.detail, feature_id=feature_id, feature_revision=FEATURE_REVISION,
            context=context, inputs_digest=None, requested_phases_digest=None,
            effective_phases_digest=None, request_digest=None, clock=clock,
        )
    try:
        if requested_phases is not None and isinstance(requested_phases, (str, bytes)):
            _fail(ReasonCode.INPUT_INVALID, "Requested phases must be a sequence.")
        requested = () if requested_phases is None else tuple(requested_phases)
        _validate_phase_tuple(requested, "requested_phases", allow_empty=True)
        if candidate_phases is not None:
            if type(candidate_phases) is not tuple:
                _fail(
                    ReasonCode.PHASE_POLICY_MISMATCH,
                    "Component phase candidates must be an immutable tuple.",
                )
            _validate_phase_tuple(
                candidate_phases,
                "component phase candidates",
                allow_empty=False,
            )
        requested_digest = canonical_digest(list(requested))
        effective = context.phase_policy.effective(
            requested,
            candidates=candidate_phases,
        )
        effective_digest = canonical_digest(list(effective))
    except VerifiedLoaderError as error:
        return _make_rejection(
            error.reason_code, error.detail, feature_id=feature_id, feature_revision=FEATURE_REVISION,
            context=context, inputs_digest=inputs_digest,
            requested_phases_digest=(canonical_digest(list(requested)) if "requested" in locals() and type(requested) is tuple else None),
            effective_phases_digest=None, request_digest=None, clock=clock,
        )
    provisional = {
        "schema": SCHEMA_FEATURE_REQUEST,
        "feature_id": feature_id,
        "feature_revision": FEATURE_REVISION,
        "binding_digest": context.binding_digest,
        "binding_generation": context.binding_generation,
        "inputs": safe_inputs,
        "inputs_digest": inputs_digest,
        "requested_phases": list(requested),
        "requested_phases_digest": requested_digest,
        "effective_phases": list(effective),
        "effective_phases_digest": effective_digest,
        "request_digest": "",
    }
    request_digest = _digest_without(provisional, "request_digest")
    return FeatureRequest(
        schema=SCHEMA_FEATURE_REQUEST, feature_id=feature_id, feature_revision=FEATURE_REVISION,
        binding_digest=context.binding_digest, binding_generation=context.binding_generation,
        inputs=safe_inputs, inputs_digest=inputs_digest, requested_phases=requested,
        requested_phases_digest=requested_digest, effective_phases=effective,
        effective_phases_digest=effective_digest, request_digest=request_digest,
    )


@dataclass(frozen=True, slots=True)
class ExecutionLeaseIdentity:
    schema: str
    lease_id: str
    lane_id: str
    lease_sequence: int
    feature_id: str
    feature_revision: str
    binding_digest: str
    binding_generation: int
    request_digest: str
    effective_phases_digest: str
    acquired_at_utc: str
    lease_digest: str

    def __post_init__(self) -> None:
        if self.schema != SCHEMA_EXECUTION_LEASE:
            _fail(ReasonCode.SCHEMA_INVALID, "Execution lease schema mismatch.")
        if type(self.lease_id) is not str or re.fullmatch(r"[0-9a-f]{32}", self.lease_id) is None:
            _fail(ReasonCode.LEASE_IDENTITY_MISMATCH, "Lease ID must be 32 lowercase hex.")
        if self.lane_id != SCIENTIFIC_LANE_ID or type(self.lease_sequence) is not int or self.lease_sequence <= 0:
            _fail(ReasonCode.LEASE_IDENTITY_MISMATCH, "Lease lane/sequence mismatch.")
        if self.feature_id not in FEATURE_REGISTRY or self.feature_revision != FEATURE_REGISTRY[self.feature_id]:
            _fail(ReasonCode.LEASE_IDENTITY_MISMATCH, "Lease feature identity mismatch.")
        _validate_sha256(self.binding_digest, "binding_digest")
        _validate_sha256(self.request_digest, "request_digest")
        _validate_sha256(self.effective_phases_digest, "effective_phases_digest")
        if type(self.binding_generation) is not int or self.binding_generation <= 0:
            _fail(ReasonCode.LEASE_IDENTITY_MISMATCH, "Lease generation is invalid.")
        _validate_timestamp(self.acquired_at_utc, "acquired_at_utc")
        if self.lease_digest != _digest_without(self.to_dict(), "lease_digest"):
            _fail(ReasonCode.LEASE_IDENTITY_MISMATCH, "Lease digest mismatch.")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in EXECUTION_LEASE_FIELDS}

    def to_json_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @classmethod
    def from_json_bytes(cls, data: bytes) -> "ExecutionLeaseIdentity":
        obj = _expect_plain_object(load_canonical_json(data), EXECUTION_LEASE_FIELDS, "ExecutionLease")
        return cls(**obj)


class ExecutionLease:
    """Current, FIFO-held scientific capability with injected seams only."""

    __slots__ = ("request", "_clock", "_nonce_factory", "_ticket", "_identity", "_entered", "_closed", "_backend_calls")

    def __init__(
        self,
        request: FeatureRequest,
        *,
        clock: Callable[[], object],
        nonce_factory: Callable[[], str],
    ) -> None:
        self.request = request
        self._clock = clock
        self._nonce_factory = nonce_factory
        self._ticket: int | None = None
        self._identity: ExecutionLeaseIdentity | None = None
        self._entered = False
        self._closed = False
        self._backend_calls = 0

    def __enter__(self) -> "ExecutionLease":
        if self._entered or self._closed:
            _fail(ReasonCode.LEASE_IDENTITY_MISMATCH, "Execution lease cannot be re-entered.")
        _RUNTIME.require_current(self.request.binding_digest, self.request.binding_generation)
        ticket = _RUNTIME.lane.reserve_and_enter()
        try:
            _RUNTIME.require_current(self.request.binding_digest, self.request.binding_generation)
            lease_id = self._nonce_factory()
            if type(lease_id) is not str or re.fullmatch(r"[0-9a-f]{32}", lease_id) is None:
                _fail(ReasonCode.LEASE_IDENTITY_MISMATCH, "Nonce seam did not return 32 lowercase hex.")
            payload = {
                "schema": SCHEMA_EXECUTION_LEASE,
                "lease_id": lease_id,
                "lane_id": SCIENTIFIC_LANE_ID,
                "lease_sequence": ticket,
                "feature_id": self.request.feature_id,
                "feature_revision": self.request.feature_revision,
                "binding_digest": self.request.binding_digest,
                "binding_generation": self.request.binding_generation,
                "request_digest": self.request.request_digest,
                "effective_phases_digest": self.request.effective_phases_digest,
                "acquired_at_utc": _clock_value(self._clock),
                "lease_digest": "",
            }
            payload["lease_digest"] = _digest_without(payload, "lease_digest")
            self._identity = ExecutionLeaseIdentity(**payload)
            self._ticket = ticket
            self._entered = True
            return self
        except Exception:
            _RUNTIME.lane.leave(ticket)
            raise

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        if self._entered and not self._closed and self._ticket is not None:
            self._closed = True
            _RUNTIME.lane.leave(self._ticket)

    @property
    def identity(self) -> ExecutionLeaseIdentity:
        self._require_live()
        assert self._identity is not None
        return self._identity

    @property
    def backend_calls(self) -> int:
        return self._backend_calls

    def _require_live(self) -> _PayloadBundle:
        if not self._entered or self._closed:
            _fail(ReasonCode.LEASE_IDENTITY_MISMATCH, "Execution lease is not live.")
        bundle = _RUNTIME.require_current(
            self.request.binding_digest, self.request.binding_generation
        )
        policy_effective = bundle.phase_policy.effective(
            self.request.requested_phases
        )
        request_effective = self.request.effective_phases
        if self.request.requested_phases:
            phase_identity_matches = request_effective == policy_effective
        else:
            policy_order = {
                phase: index for index, phase in enumerate(policy_effective)
            }
            phase_identity_matches = (
                bool(request_effective)
                and all(phase in policy_order for phase in request_effective)
                and tuple(
                    sorted(request_effective, key=policy_order.__getitem__)
                )
                == request_effective
            )
        if (
            not phase_identity_matches
            or canonical_digest(list(request_effective))
            != self.request.effective_phases_digest
        ):
            _fail(
                ReasonCode.PHASE_POLICY_MISMATCH,
                "Request phase evidence changed before dispatch.",
            )
        return bundle

    def parse_tdb(
        self,
        parser: Callable[[Any], object],
        parser_revision: str,
        *,
        fresh: bool = False,
    ) -> object:
        bundle = self._require_live()
        if (
            not callable(parser)
            or type(parser_revision) is not str
            or _REVISION_RE.fullmatch(parser_revision) is None
            or type(fresh) is not bool
        ):
            _fail(ReasonCode.SCHEMA_INVALID, "Injected TDB parser seam/revision is invalid.")
        key = ("tdb", bundle.tdb.evidence.sha256, parser_revision)
        if not fresh:
            with _RUNTIME.lock:
                cached = _RUNTIME.parser_cache.get(key)
            if cached is not None:
                return cached
        parsed = parse_verified_utf8_snapshot(
            bundle.tdb._snapshot_bytes,
            expected_sha256=bundle.tdb.evidence.sha256,
            snapshot_sha256=bundle.tdb.evidence.sha256,
            parser=parser,
        )
        self._require_live()
        if not fresh:
            with _RUNTIME.lock:
                _RUNTIME.parser_cache[key] = parsed
        return parsed

    def parse_physical_dataset(self, parser: Callable[[bytes], object], parser_revision: str) -> object:
        bundle = self._require_live()
        if bundle.physical_pdb is None:
            _fail(ReasonCode.DATA_UNAVAILABLE, "No physical PDB is bound to this request.")
        if not callable(parser) or type(parser_revision) is not str or _REVISION_RE.fullmatch(parser_revision) is None:
            _fail(ReasonCode.SCHEMA_INVALID, "Injected PDB parser seam/revision is invalid.")
        key = ("pdb", bundle.physical_pdb.evidence.sha256, parser_revision)
        with _RUNTIME.lock:
            cached = _RUNTIME.parser_cache.get(key)
        if cached is not None:
            return cached
        parsed = parser(bundle.physical_pdb._snapshot_bytes)
        self._require_live()
        with _RUNTIME.lock:
            _RUNTIME.parser_cache[key] = parsed
        return parsed

    def invoke_backend(self, backend: Callable[["ExecutionLease"], object]) -> object:
        self._require_live()
        if not callable(backend):
            _fail(ReasonCode.SCHEMA_INVALID, "Backend seam must be callable.")
        self._backend_calls += 1
        result = backend(self)
        self._require_live()
        return result

    def materialize_filename(self, *_args: object, **_kwargs: object) -> None:
        self._require_live()
        _fail(
            ReasonCode.CAPABILITY_UNAVAILABLE,
            "Filename materialization is deliberately non-executable in Wave B1.",
        )


def acquire_execution(
    request: FeatureRequest,
    paths: object,
    *,
    clock: Callable[[], object] = _system_clock,
    nonce_factory: Callable[[], str] = lambda: uuid.uuid4().hex,
) -> ExecutionLease:
    if type(request) is not FeatureRequest:
        _fail(ReasonCode.SCHEMA_INVALID, "Execution requires the frozen FeatureRequest type.")
    if paths is None or isinstance(paths, (str, bytes, Path)):
        _fail(ReasonCode.RAW_PATH_REJECTED, "Execution requires injected paths authority, not a raw path.")
    _RUNTIME.require_current(request.binding_digest, request.binding_generation)
    return ExecutionLease(request, clock=clock, nonce_factory=nonce_factory)


def _validate_backend(value: object) -> dict[str, str]:
    obj = _expect_plain_object(value, ("adapter_id", "adapter_revision", "backend_id", "backend_version"), "backend")
    for key, item in obj.items():
        if type(item) is not str or not item or len(item) > 128:
            _fail(ReasonCode.RECEIPT_INVALID, f"backend.{key} is invalid.")
    return obj


def _validate_packages(value: object) -> list[dict[str, str]]:
    if type(value) is not list:
        _fail(ReasonCode.RECEIPT_INVALID, "packages must be an ordered list.")
    result: list[dict[str, str]] = []
    for item in value:
        obj = _expect_plain_object(item, ("name", "version", "status"), "package")
        if any(type(obj[key]) is not str or not obj[key] for key in obj):
            _fail(ReasonCode.RECEIPT_INVALID, "Package evidence is invalid.")
        result.append(dict(obj))
    return result


@dataclass(frozen=True, slots=True)
class FeatureReceipt:
    schema: str
    feature_id: str
    feature_revision: str
    outcome: str
    reason_code: str | None
    reason_detail: str | None
    binding_digest: str
    binding_generation: int
    tdb_evidence: ArtifactEvidence
    passport_evidence: ArtifactEvidence | None
    physical_pdb_evidence: ArtifactEvidence | None
    phase_policy_id: str
    phase_policy_revision: str
    requested_phases: tuple[str, ...]
    requested_phases_digest: str
    effective_phases: tuple[str, ...]
    effective_phases_digest: str
    inputs_digest: str
    request_digest: str
    lease_id: str
    backend: dict[str, str]
    packages: tuple[dict[str, str], ...]
    backend_calls: int
    point_count: int
    result_digest: str | None
    started_at_utc: str
    finished_at_utc: str
    receipt_digest: str

    def __post_init__(self) -> None:
        if self.schema != SCHEMA_FEATURE_RECEIPT or self.feature_id not in FEATURE_REGISTRY:
            _fail(ReasonCode.RECEIPT_INVALID, "Feature receipt schema/feature mismatch.")
        if self.feature_revision != FEATURE_REGISTRY[self.feature_id] or self.outcome not in ("success", "failure", "unavailable"):
            _fail(ReasonCode.RECEIPT_INVALID, "Feature receipt revision/outcome mismatch.")
        if self.outcome == "success":
            if self.reason_code is not None or self.reason_detail is not None or self.result_digest is None:
                _fail(ReasonCode.RECEIPT_INVALID, "Successful receipt reason/result shape mismatch.")
        else:
            if self.reason_code not in {item.value for item in ReasonCode} or type(self.reason_detail) is not str:
                _fail(ReasonCode.RECEIPT_INVALID, "Failed/unavailable receipt reason is invalid.")
            if not self.reason_detail or len(self.reason_detail) > MAX_REASON_DETAIL_CHARS or self.result_digest is not None:
                _fail(ReasonCode.RECEIPT_INVALID, "Failed/unavailable receipt detail/result shape mismatch.")
        _validate_sha256(self.binding_digest, "binding_digest")
        if type(self.binding_generation) is not int or self.binding_generation <= 0:
            _fail(ReasonCode.RECEIPT_INVALID, "Receipt generation is invalid.")
        if type(self.tdb_evidence) is not ArtifactEvidence:
            _fail(ReasonCode.RECEIPT_INVALID, "Receipt TDB evidence is invalid.")
        _validate_phase_tuple(self.requested_phases, "requested_phases", allow_empty=True)
        _validate_phase_tuple(self.effective_phases, "effective_phases", allow_empty=False)
        for label, digest in (
            ("requested_phases_digest", self.requested_phases_digest),
            ("effective_phases_digest", self.effective_phases_digest),
            ("inputs_digest", self.inputs_digest), ("request_digest", self.request_digest),
        ):
            _validate_sha256(digest, label)
        if self.requested_phases_digest != canonical_digest(list(self.requested_phases)) or self.effective_phases_digest != canonical_digest(list(self.effective_phases)):
            _fail(ReasonCode.RECEIPT_INVALID, "Receipt phase digest mismatch.")
        if type(self.lease_id) is not str or re.fullmatch(r"[0-9a-f]{32}", self.lease_id) is None:
            _fail(ReasonCode.RECEIPT_INVALID, "Receipt lease ID is invalid.")
        _validate_backend(self.backend)
        _validate_packages(list(self.packages))
        if type(self.backend_calls) is not int or self.backend_calls < 0 or type(self.point_count) is not int or self.point_count < 0:
            _fail(ReasonCode.RECEIPT_INVALID, "Receipt counts are invalid.")
        if self.result_digest is not None:
            _validate_sha256(self.result_digest, "result_digest")
        _validate_timestamp(self.started_at_utc, "started_at_utc")
        _validate_timestamp(self.finished_at_utc, "finished_at_utc")
        if self.receipt_digest != _digest_without(self.to_dict(), "receipt_digest"):
            _fail(ReasonCode.RECEIPT_INVALID, "Feature receipt digest mismatch.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "feature_id": self.feature_id,
            "feature_revision": self.feature_revision, "outcome": self.outcome,
            "reason_code": self.reason_code, "reason_detail": self.reason_detail,
            "binding_digest": self.binding_digest, "binding_generation": self.binding_generation,
            "tdb_evidence": self.tdb_evidence.to_dict(),
            "passport_evidence": None if self.passport_evidence is None else self.passport_evidence.to_dict(),
            "physical_pdb_evidence": None if self.physical_pdb_evidence is None else self.physical_pdb_evidence.to_dict(),
            "phase_policy_id": self.phase_policy_id, "phase_policy_revision": self.phase_policy_revision,
            "requested_phases": list(self.requested_phases), "requested_phases_digest": self.requested_phases_digest,
            "effective_phases": list(self.effective_phases), "effective_phases_digest": self.effective_phases_digest,
            "inputs_digest": self.inputs_digest, "request_digest": self.request_digest,
            "lease_id": self.lease_id, "backend": self.backend,
            "packages": list(self.packages), "backend_calls": self.backend_calls,
            "point_count": self.point_count, "result_digest": self.result_digest,
            "started_at_utc": self.started_at_utc, "finished_at_utc": self.finished_at_utc,
            "receipt_digest": self.receipt_digest,
        }

    def to_json_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @classmethod
    def from_json_bytes(cls, data: bytes) -> "FeatureReceipt":
        obj = _expect_plain_object(load_canonical_json(data), FEATURE_RECEIPT_FIELDS, "FeatureReceipt")
        return cls(
            schema=obj["schema"], feature_id=obj["feature_id"], feature_revision=obj["feature_revision"],
            outcome=obj["outcome"], reason_code=obj["reason_code"], reason_detail=obj["reason_detail"],
            binding_digest=obj["binding_digest"], binding_generation=obj["binding_generation"],
            tdb_evidence=ArtifactEvidence.from_dict(obj["tdb_evidence"]),
            passport_evidence=None if obj["passport_evidence"] is None else ArtifactEvidence.from_dict(obj["passport_evidence"]),
            physical_pdb_evidence=None if obj["physical_pdb_evidence"] is None else ArtifactEvidence.from_dict(obj["physical_pdb_evidence"]),
            phase_policy_id=obj["phase_policy_id"], phase_policy_revision=obj["phase_policy_revision"],
            requested_phases=_phase_tuple_from_json(obj["requested_phases"], "requested_phases", allow_empty=True),
            requested_phases_digest=obj["requested_phases_digest"],
            effective_phases=_phase_tuple_from_json(obj["effective_phases"], "effective_phases", allow_empty=False),
            effective_phases_digest=obj["effective_phases_digest"], inputs_digest=obj["inputs_digest"],
            request_digest=obj["request_digest"], lease_id=obj["lease_id"], backend=_validate_backend(obj["backend"]),
            packages=tuple(_validate_packages(obj["packages"])), backend_calls=obj["backend_calls"],
            point_count=obj["point_count"], result_digest=obj["result_digest"],
            started_at_utc=obj["started_at_utc"], finished_at_utc=obj["finished_at_utc"],
            receipt_digest=obj["receipt_digest"],
        )


def make_feature_receipt(
    context: BoundDatabaseContext,
    request: FeatureRequest,
    lease: ExecutionLease,
    *,
    outcome: str,
    reason_code: ReasonCode | None,
    reason_detail: str | None,
    backend: Mapping[str, str],
    packages: Sequence[Mapping[str, str]],
    point_count: int,
    result_digest: str | None,
    started_at_utc: str,
    finished_at_utc: str,
) -> FeatureReceipt:
    if type(context) is not BoundDatabaseContext or type(request) is not FeatureRequest or type(lease) is not ExecutionLease:
        _fail(ReasonCode.RECEIPT_INVALID, "Receipt factory identities are invalid.")
    identity = lease.identity
    if identity.request_digest != request.request_digest or request.binding_digest != context.binding_digest:
        _fail(ReasonCode.RECEIPT_INVALID, "Receipt context/request/lease identity mismatch.")
    backend_obj = _validate_backend(dict(backend) if type(backend) is dict else backend)
    package_list = _validate_packages([dict(item) for item in packages])
    payload = {
        "schema": SCHEMA_FEATURE_RECEIPT, "feature_id": request.feature_id,
        "feature_revision": request.feature_revision, "outcome": outcome,
        "reason_code": None if reason_code is None else reason_code.value,
        "reason_detail": reason_detail, "binding_digest": context.binding_digest,
        "binding_generation": context.binding_generation, "tdb_evidence": context.tdb.to_dict(),
        "passport_evidence": None if context.passport is None else context.passport.to_dict(),
        "physical_pdb_evidence": None if context.physical_pdb is None else context.physical_pdb.to_dict(),
        "phase_policy_id": context.phase_policy.policy_id,
        "phase_policy_revision": context.phase_policy.policy_revision,
        "requested_phases": list(request.requested_phases),
        "requested_phases_digest": request.requested_phases_digest,
        "effective_phases": list(request.effective_phases),
        "effective_phases_digest": request.effective_phases_digest,
        "inputs_digest": request.inputs_digest, "request_digest": request.request_digest,
        "lease_id": identity.lease_id, "backend": backend_obj, "packages": package_list,
        "backend_calls": lease.backend_calls, "point_count": point_count,
        "result_digest": result_digest, "started_at_utc": started_at_utc,
        "finished_at_utc": finished_at_utc, "receipt_digest": "",
    }
    payload["receipt_digest"] = _digest_without(payload, "receipt_digest")
    return FeatureReceipt.from_json_bytes(canonical_json_bytes(payload))


def _validate_result_entries(value: object, label: str) -> list[dict[str, Any]]:
    if type(value) is not list:
        _fail(ReasonCode.ENVELOPE_INVALID, f"{label} must be an ordered list.")
    result: list[dict[str, Any]] = []
    for entry in value:
        obj = _expect_plain_object(entry, ("name", "media_type", "sha256", "size_bytes", "payload_ref"), label)
        if type(obj["name"]) is not str or not obj["name"] or type(obj["media_type"]) is not str or not obj["media_type"]:
            _fail(ReasonCode.ENVELOPE_INVALID, f"{label} entry label/type is invalid.")
        _validate_sha256(obj["sha256"], f"{label}.sha256")
        if type(obj["size_bytes"]) is not int or obj["size_bytes"] < 0:
            _fail(ReasonCode.ENVELOPE_INVALID, f"{label}.size_bytes is invalid.")
        ref = obj["payload_ref"]
        if (
            type(ref) is not str or not ref.startswith("state/") or "\\" in ref
            or ":" in ref or any(part in ("", ".", "..") for part in ref.split("/"))
        ):
            _fail(ReasonCode.RAW_PATH_REJECTED, f"{label}.payload_ref is not a state logical reference.")
        result.append(dict(obj))
    return result


@dataclass(frozen=True, slots=True)
class ResultEnvelope:
    schema: str
    feature_id: str
    feature_revision: str
    binding_digest: str
    binding_generation: int
    request_digest: str
    receipt_digest: str
    outcome: str
    settings: dict[str, Any]
    settings_digest: str
    tables: tuple[dict[str, Any], ...]
    tables_digest: str
    figures: tuple[dict[str, Any], ...]
    figures_digest: str
    artifacts: tuple[dict[str, Any], ...]
    artifacts_digest: str
    result_digest: str
    created_at_utc: str
    envelope_digest: str

    def __post_init__(self) -> None:
        if self.schema != SCHEMA_RESULT_ENVELOPE or self.feature_id not in FEATURE_REGISTRY:
            _fail(ReasonCode.ENVELOPE_INVALID, "Result envelope schema/feature mismatch.")
        if self.feature_revision != FEATURE_REGISTRY[self.feature_id] or self.outcome not in ("success", "failure", "unavailable"):
            _fail(ReasonCode.ENVELOPE_INVALID, "Result envelope revision/outcome mismatch.")
        _validate_sha256(self.binding_digest, "binding_digest")
        _validate_sha256(self.request_digest, "request_digest")
        _validate_sha256(self.receipt_digest, "receipt_digest")
        if type(self.binding_generation) is not int or self.binding_generation <= 0 or type(self.settings) is not dict:
            _fail(ReasonCode.ENVELOPE_INVALID, "Envelope generation/settings are invalid.")
        _walk_canonical(self.settings, reject_raw_paths=True)
        for label, value, digest in (
            ("settings", self.settings, self.settings_digest),
            ("tables", list(self.tables), self.tables_digest),
            ("figures", list(self.figures), self.figures_digest),
            ("artifacts", list(self.artifacts), self.artifacts_digest),
        ):
            if digest != canonical_digest(value):
                _fail(ReasonCode.RESULT_DIGEST_MISMATCH, f"{label} digest mismatch.")
        _validate_result_entries(list(self.tables), "tables")
        _validate_result_entries(list(self.figures), "figures")
        _validate_result_entries(list(self.artifacts), "artifacts")
        result_payload = {
            "settings_digest": self.settings_digest, "tables_digest": self.tables_digest,
            "figures_digest": self.figures_digest, "artifacts_digest": self.artifacts_digest,
        }
        if self.result_digest != canonical_digest(result_payload):
            _fail(ReasonCode.RESULT_DIGEST_MISMATCH, "Envelope result digest mismatch.")
        _validate_timestamp(self.created_at_utc, "created_at_utc")
        if self.envelope_digest != _digest_without(self.to_dict(), "envelope_digest"):
            _fail(ReasonCode.ENVELOPE_INVALID, "Envelope digest mismatch.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "feature_id": self.feature_id,
            "feature_revision": self.feature_revision, "binding_digest": self.binding_digest,
            "binding_generation": self.binding_generation, "request_digest": self.request_digest,
            "receipt_digest": self.receipt_digest, "outcome": self.outcome,
            "settings": self.settings, "settings_digest": self.settings_digest,
            "tables": list(self.tables), "tables_digest": self.tables_digest,
            "figures": list(self.figures), "figures_digest": self.figures_digest,
            "artifacts": list(self.artifacts), "artifacts_digest": self.artifacts_digest,
            "result_digest": self.result_digest, "created_at_utc": self.created_at_utc,
            "envelope_digest": self.envelope_digest,
        }

    def to_json_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())

    @classmethod
    def from_json_bytes(cls, data: bytes) -> "ResultEnvelope":
        obj = _expect_plain_object(load_canonical_json(data), RESULT_ENVELOPE_FIELDS, "ResultEnvelope")
        return cls(
            schema=obj["schema"], feature_id=obj["feature_id"], feature_revision=obj["feature_revision"],
            binding_digest=obj["binding_digest"], binding_generation=obj["binding_generation"],
            request_digest=obj["request_digest"], receipt_digest=obj["receipt_digest"], outcome=obj["outcome"],
            settings=obj["settings"], settings_digest=obj["settings_digest"],
            tables=tuple(_validate_result_entries(obj["tables"], "tables")), tables_digest=obj["tables_digest"],
            figures=tuple(_validate_result_entries(obj["figures"], "figures")), figures_digest=obj["figures_digest"],
            artifacts=tuple(_validate_result_entries(obj["artifacts"], "artifacts")), artifacts_digest=obj["artifacts_digest"],
            result_digest=obj["result_digest"], created_at_utc=obj["created_at_utc"], envelope_digest=obj["envelope_digest"],
        )


def make_result_envelope(
    context: BoundDatabaseContext,
    request: FeatureRequest,
    receipt: FeatureReceipt,
    *,
    settings: Mapping[str, Any],
    tables: Sequence[Mapping[str, Any]] = (),
    figures: Sequence[Mapping[str, Any]] = (),
    artifacts: Sequence[Mapping[str, Any]] = (),
    clock: Callable[[], object] = _system_clock,
) -> ResultEnvelope:
    if type(context) is not BoundDatabaseContext or type(request) is not FeatureRequest or type(receipt) is not FeatureReceipt:
        _fail(ReasonCode.ENVELOPE_CONTEXT_MISMATCH, "Envelope identities use unexpected types.")
    if (
        receipt.binding_digest != context.binding_digest
        or receipt.binding_generation != context.binding_generation
        or receipt.request_digest != request.request_digest
        or receipt.feature_id != request.feature_id
    ):
        _fail(ReasonCode.ENVELOPE_CONTEXT_MISMATCH, "Envelope context/request/receipt mismatch.")
    if type(settings) is not dict:
        _fail(ReasonCode.ENVELOPE_INVALID, "Envelope settings must be a plain object.")
    _walk_canonical(settings, reject_raw_paths=True)
    safe_settings = json.loads(canonical_json_bytes(settings).decode("utf-8"))
    safe_tables = _validate_result_entries([dict(item) for item in tables], "tables")
    safe_figures = _validate_result_entries([dict(item) for item in figures], "figures")
    safe_artifacts = _validate_result_entries([dict(item) for item in artifacts], "artifacts")
    settings_digest = canonical_digest(safe_settings)
    tables_digest = canonical_digest(safe_tables)
    figures_digest = canonical_digest(safe_figures)
    artifacts_digest = canonical_digest(safe_artifacts)
    result_digest = canonical_digest(
        {
            "settings_digest": settings_digest, "tables_digest": tables_digest,
            "figures_digest": figures_digest, "artifacts_digest": artifacts_digest,
        }
    )
    if receipt.result_digest != result_digest:
        _fail(ReasonCode.RESULT_DIGEST_MISMATCH, "Receipt and envelope result digests differ.")
    payload = {
        "schema": SCHEMA_RESULT_ENVELOPE, "feature_id": request.feature_id,
        "feature_revision": request.feature_revision, "binding_digest": context.binding_digest,
        "binding_generation": context.binding_generation, "request_digest": request.request_digest,
        "receipt_digest": receipt.receipt_digest, "outcome": receipt.outcome,
        "settings": safe_settings, "settings_digest": settings_digest,
        "tables": safe_tables, "tables_digest": tables_digest,
        "figures": safe_figures, "figures_digest": figures_digest,
        "artifacts": safe_artifacts, "artifacts_digest": artifacts_digest,
        "result_digest": result_digest, "created_at_utc": _clock_value(clock),
        "envelope_digest": "",
    }
    payload["envelope_digest"] = _digest_without(payload, "envelope_digest")
    return ResultEnvelope.from_json_bytes(canonical_json_bytes(payload))


def verified_core1_v2_evidence_bridge(
    core1_receipt: Mapping[str, Any],
    context: BoundDatabaseContext,
    request: FeatureRequest,
) -> dict[str, Any]:
    """Validate and bind all Core1-v2 facts for embedding in envelope settings."""

    if type(core1_receipt) is not dict:
        _fail(ReasonCode.RECEIPT_INVALID, "Core1-v2 receipt must be a plain object.")
    _walk_canonical(core1_receipt, reject_raw_paths=True)
    expected_fields = (
        "schema", "feature_id", "context_digest", "request_digest", "ordered_phases",
        "ordered_phases_digest", "source_hashes", "calls", "points", "outcome",
        "error_code", "material_base", "experimental_qualification",
    )
    obj = _expect_plain_object(core1_receipt, expected_fields, "Core1-v2 receipt")
    if obj["schema"] != "thermogar.restricted_fe.receipt.v2":
        _fail(ReasonCode.RECEIPT_INVALID, "Core1-v2 schema mismatch.")
    if obj["feature_id"] != request.feature_id or request.feature_id not in FEATURE_IDS[:3]:
        _fail(ReasonCode.RECEIPT_INVALID, "Core1-v2 feature identity mismatch.")
    phases = obj["ordered_phases"]
    if type(phases) is not list or C15_PHASE in phases or tuple(phases) != request.effective_phases:
        _fail(ReasonCode.PHASE_POLICY_MISMATCH, "Core1-v2 effective phases mismatch.")
    if obj["ordered_phases_digest"] != canonical_digest(phases):
        _fail(ReasonCode.RECEIPT_INVALID, "Core1-v2 phase digest mismatch.")
    if obj["source_hashes"] != [
        ["database_sha256", context.tdb.sha256],
        ["passport_sha256", context.passport.sha256 if context.passport is not None else None],
    ]:
        _fail(ReasonCode.BINDING_IDENTITY_MISMATCH, "Core1-v2 source evidence mismatch.")
    if obj["material_base"] != "STEEL" or obj["experimental_qualification"] != "NOT_PERFORMED":
        _fail(ReasonCode.RECEIPT_INVALID, "Core1-v2 factual metadata mismatch.")
    if type(obj["calls"]) is not int or obj["calls"] < 0 or type(obj["points"]) is not list:
        _fail(ReasonCode.RECEIPT_INVALID, "Core1-v2 call/point evidence is invalid.")
    if obj["outcome"] not in ("success", "failure"):
        _fail(ReasonCode.RECEIPT_INVALID, "Core1-v2 outcome is invalid.")
    receipt_copy = json.loads(canonical_json_bytes(obj).decode("utf-8"))
    bridge = {
        "schema": SCHEMA_CORE1_BRIDGE,
        "binding_digest": context.binding_digest,
        "binding_generation": context.binding_generation,
        "feature_request_digest": request.request_digest,
        "core1_receipt": receipt_copy,
        "core1_receipt_digest": canonical_digest(receipt_copy),
    }
    return json.loads(canonical_json_bytes(bridge).decode("utf-8"))


__all__ = (
    "ArtifactCatalog", "ArtifactEvidence", "BoundDatabaseContext", "C15_PHASE",
    "EXECUTION_LEASE_FIELDS", "ExecutionLease", "ExecutionLeaseIdentity",
    "FEATURE_IDS", "FEATURE_RECEIPT_FIELDS", "FEATURE_REGISTRY",
    "FEATURE_REQUEST_FIELDS", "FEATURE_REVISION", "FeatureReceipt", "FeatureRequest",
    "REJECTION_FIELDS", "RESULT_ENVELOPE_FIELDS", "ReasonCode", "RejectedFeatureReceipt",
    "ResultEnvelope", "VerifiedArtifact", "VerifiedBinaryArtifact", "VerifiedLoaderError",
    "acquire_execution", "bind_selected_database", "canonical_digest",
    "canonical_json_bytes", "canonical_release_manifest", "invalidate_binding_generation",
    "load_canonical_json", "make_feature_receipt", "make_result_envelope",
    "prepare_feature_request", "verified_core1_v2_evidence_bridge",
)
