"""Strict Wave 2B database, domain, and result receipt contracts.

This module is a pure provenance boundary.  It imports only the Python
standard library, performs no calculation, grants no release permission, and
does not count toward NE-03 feature coverage or acceptance.  Database bytes,
the NE-04 contract, and the release-policy generation are pinned before a
request can receive a domain receipt.  The same files can be rehashed before
and after execution so a result cannot silently cross a database/profile
change.

Steel is an explicit supported family.  Fe callers must name exactly one of
``thermogar_patch`` or ``upstream_original``.  Neither is selected as a
baseline here, and the C15 exclusion decision remains explicitly undecided.
Known legacy Fe report count/path drift is retained in internal qualification
receipts and is a hard RELEASE blocker.

Receipt digests and in-process lease identifiers are integrity coordinates,
not cryptographic authority.  Every public edge reconstructs all exact
primitive fields and reruns structural invariants.  Backend integration is
limited to paths supplied by an active ``ExecutionLease``; those paths point
to private content-addressed copies held deny-write for the execution window.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import stat
import struct
import tempfile
from types import MappingProxyType
from typing import Any, ClassVar, Final
import unicodedata


PROFILE_MANIFEST_SCHEMA: Final = "SWR-NE03-WAVE2B-DATABASE-PROFILES-1"
PROFILE_RECEIPT_SCHEMA: Final = "SWR-NE03-WAVE2B-DATABASE-PROFILE-RECEIPT-1"
DOMAIN_RECEIPT_SCHEMA: Final = "SWR-NE03-WAVE2B-DOMAIN-RECEIPT-1"
RESULT_RECEIPT_SCHEMA: Final = "SWR-NE03-WAVE2B-RESULT-RECEIPT-1"
REHASH_SNAPSHOT_SCHEMA: Final = "SWR-NE03-WAVE2B-REHASH-SNAPSHOT-1"
EXECUTION_LEASE_SCHEMA: Final = "SWR-NE03-WAVE2B-EXECUTION-LEASE-1"
NE04_CONTRACT_SCHEMA: Final = "SWR-NE04-DATABASE-DOMAINS-3"

INTERNAL_QUALIFICATION: Final = "INTERNAL_QUALIFICATION"
RELEASE: Final = "RELEASE"
EXECUTION_MODES: Final = (INTERNAL_QUALIFICATION, RELEASE)
SUPPORTED_DATABASE_FAMILIES: Final = ("ni", "al", "fe")
SUPPORTED_FE_PROFILE_IDS: Final = ("thermogar_patch", "upstream_original")
SUPPORTED_WAVE2B_FEATURES: Final = (
    "equilibrium_single",
    "equilibrium_temperature_scan",
    "equilibrium_composition_scan",
    "ternary_phase_fraction_map",
    "manual_phase_selection_metastable",
    "phase_gibbs_energy",
    "phase_driving_force",
    "tzero_temperature",
    "binary_phase_diagram",
    "multicomponent_isopleth",
    "ternary_phase_diagram",
    "equilibrium_solidification",
    "scheil_solidification",
)
DIRECT_RESULT_FEATURES: Final = SUPPORTED_WAVE2B_FEATURES[:8]
MAPPING_RESULT_FEATURES: Final = SUPPORTED_WAVE2B_FEATURES[8:11]
SOLIDIFICATION_RESULT_FEATURES: Final = SUPPORTED_WAVE2B_FEATURES[11:]
FE_POLICY_UNDECIDED: Final = "UNDECIDED_USER_DECISION_REQUIRED"
POLICY_NOT_APPLICABLE: Final = "NOT_APPLICABLE"
PHASE_FINGERPRINT_ALGORITHM: Final = "SHA256_SORTED_UPPERCASE_UTF8_LF"
PRODUCTION_USE: Final = "DENIED"
ACCEPTANCE_CLAIM: Final = False
COUNTS_TOWARD_FEATURE_COVERAGE: Final = False
DEFAULT_PROFILE_MANIFEST_PATH: Final = "configs/ne03_wave2b_database_profiles.json"
PROFILE_MANIFEST_SHA256: Final = "2ff6fb8a07668b01065ba351c2214b8fff3093fdc785de223b98e826f5614cbc"

_PROFILE_BY_NON_FE_FAMILY = {
    "ni": "mc_ni_v2036",
    "al": "mc_al_v2037",
}
_PROFILE_ROLE = {
    ("ni", "mc_ni_v2036"): "RELEASE_CANDIDATE_PENDING_NE04",
    ("al", "mc_al_v2037"): "RELEASE_CANDIDATE_PENDING_NE04",
    ("fe", "thermogar_patch"): "EVALUATION_PROFILE",
    ("fe", "upstream_original"): "DIAGNOSTIC_CONTROL",
}
_PINNED_INTERNAL_PROFILE_RECEIPT_DIGESTS = MappingProxyType(
    {
        ("ni", "mc_ni_v2036"): "7661094dbfa9e4427cecfe428a9e4b998ff8c7585c67d7ff3507599dac6c07bb",
        ("al", "mc_al_v2037"): "8ed36df9b468da8f4e97043ec612961837372870fc75dc9acbaa6975b6019c5e",
        ("fe", "thermogar_patch"): "a7115c076e5e7d41f098db252c2e8a6925c0532d72d97b032e5c3028df921284",
        ("fe", "upstream_original"): "3ca15ff2375a986ffec9b2d613248b3be338acb6d14f41a8e1e76628886a5a88",
    }
)
_FILE_ROLES = (
    "source",
    "thermodynamic",
    "mobility",
    "runtime",
    "report",
    "passport",
)
_OBSERVATION_ROLES = (
    "profile_manifest",
    "release_policy",
    "ne04_contract",
    *_FILE_ROLES,
)
_MAX_FILE_BYTES = MappingProxyType(
    {
        "profile_manifest": 1 * 1024 * 1024,
        "release_policy": 2 * 1024 * 1024,
        "ne04_contract": 2 * 1024 * 1024,
        "source": 32 * 1024 * 1024,
        "thermodynamic": 32 * 1024 * 1024,
        "mobility": 16 * 1024 * 1024,
        "runtime": 48 * 1024 * 1024,
        "report": 4 * 1024 * 1024,
        "passport": 4 * 1024 * 1024,
    }
)
_MAX_CANONICAL_JSON_BYTES = 8 * 1024 * 1024
_MAX_JSON_DEPTH = 64
_MAX_CONTAINER_ITEMS = 100_000
_MAX_TEXT_LENGTH = 1_000_000
_HASH_CHUNK_BYTES = 1024 * 1024
_LEASE_MARKER_NAME = ".thermogar_wave2b_lease"
_LOWER_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_CANONICAL_TOKEN = re.compile(r"[a-z0-9][a-z0-9_.-]{0,127}\Z")
_FEATURE_TOKEN = re.compile(r"[a-z][a-z0-9_]{0,127}\Z")
_PHASE_TOKEN = re.compile(r"[A-Z0-9_#:+.-]{1,128}\Z")
_REASON_TOKEN = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z")
_PHASE_NAME = re.compile(r"(?is)^\s*PHASE\s+([A-Z0-9_:+-]+)(?:\s|$)")
_REFERENCE_MARKER = re.compile(
    r"(?im)^\s*LIST(?:_|\s+|-)+OF(?:_|\s+|-)+REFERENCES\b"
)
_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
_REPARSE_POINT = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))

_DIRECT_BACKEND_SCHEMA = "THERMOGAR-WAVE2B-RECEIPT-BOUND-BACKEND-1"
_DIRECT_BACKEND_ID = "thermogar_wave2b_pycalphad_0_11_2_candidate"
_MAPPING_BACKEND_SCHEMA = "THERMOGAR-WAVE2B-RECEIPT-BOUND-MAPPING-BACKEND-1"
_MAPPING_BACKEND_ID = "thermogar_wave2b_pycalphad_0_11_2_mapping_candidate"
_SOLIDIFICATION_BACKEND_SCHEMA = "THERMOGAR-WAVE2B-SOLIDIFICATION-BACKEND-1"
_SOLIDIFICATION_BACKEND_ID = "thermogar_wave2b_scheil_0_3_0_candidate"
_PATH_CONTRACT_V2_SHA256 = (
    "c58a35d1548c3d5b321ac4094c3ef86bd6b30d2d2f5f4e6570cad2556afc7ed7"
)
_MAPPING_MEMBERSHIP_POLICY = (
    "RAW_BINARY64_RETAINED_PYCALPHAD_0_11_2_FEATURE_PINNED_MOLE_"
    "FRACTION_ABS_1E_9"
)
_MAPPING_PARTIAL_REASON = "PYCALPHAD_0_11_2_HIDDEN_ATTEMPTS_UNAVAILABLE"
_MAPPING_PARTIAL_TERMINALS = (
    "PARTIAL_UNRESOLVED_BRANCHES",
    "TOPOLOGY_OBSERVED_DIAGNOSTICS_PARTIAL",
)
_MAPPING_DIAGNOSTIC_STATES = (
    "NOT_RUN",
    "COMPLETE_TRACE_COMPLETED",
    "COMPLETE_TRACE_TERMINATED",
    "INCOMPLETE_DIAGNOSTICS",
    "DTO_V2_REQUIRED",
    "FAILED",
    "V2_NATIVE_PARTIAL_UNRESOLVED_BRANCHES",
    "V2_NATIVE_TOPOLOGY_OBSERVED_DIAGNOSTICS_PARTIAL",
    "V2_NATIVE_FAILED_CLOSED",
)
_SOLIDIFICATION_PARTIAL_STATUS = "PARTIAL_UNRESOLVED_BRANCHES"
_SOLIDIFICATION_PARTIAL_REASON = (
    "SCHEIL_0_3_0_HIDDEN_INTERNAL_ATTEMPTS_UNAVAILABLE"
)
_V2_DATABASE_ID = MappingProxyType(
    {
        ("ni", "mc_ni_v2036"): "mc_ni_v2036",
        ("al", "mc_al_v2037"): "mc_al_v2037",
        ("fe", "thermogar_patch"): "mc_fe_v2062",
        ("fe", "upstream_original"): "mc_fe_v2062",
    }
)

_REASON_TEXT = {
    "W2B_RECEIPT_JSON_INVALID": "JSON is malformed or violates the strict canonical data model.",
    "W2B_RECEIPT_JSON_NOT_CANONICAL": "JSON bytes are not the exact canonical representation.",
    "W2B_RECEIPT_JSON_DUPLICATE_KEY": "A JSON object repeats a key.",
    "W2B_RECEIPT_JSON_NONFINITE": "A numeric JSON value is non-finite.",
    "W2B_RECEIPT_JSON_LIMIT": "A JSON payload exceeds a bounded size, depth, or cardinality limit.",
    "W2B_RECEIPT_PATH_INVALID": "A receipt path is not an exact safe in-tree POSIX relative path.",
    "W2B_RECEIPT_FILE_INVALID": "A required receipt file is missing, non-regular, linked, or reparse-backed.",
    "W2B_RECEIPT_FILE_TOO_LARGE": "A required receipt file exceeds its bounded role limit.",
    "W2B_RECEIPT_FILE_CHANGED": "A file changed identity or metadata while it was being hashed.",
    "W2B_RECEIPT_FILE_SIZE_MISMATCH": "A file size differs from the pinned profile contract.",
    "W2B_RECEIPT_FILE_HASH_MISMATCH": "A file SHA-256 differs from the pinned profile contract.",
    "W2B_RECEIPT_MANIFEST_INVALID": "The database profile manifest violates its exact schema.",
    "W2B_RECEIPT_MANIFEST_HASH_MISMATCH": "The loaded profile manifest differs from the receipt pin.",
    "W2B_RECEIPT_FAMILY_INVALID": "The database family must be exactly ni, al, or fe.",
    "W2B_RECEIPT_PROFILE_REQUIRED": "A database profile must be supplied explicitly.",
    "W2B_RECEIPT_PROFILE_INVALID": "The profile is absent, aliased, or not exact for its database family.",
    "W2B_RECEIPT_PROFILE_ROLE_INVALID": "The profile role differs from the pinned profile contract.",
    "W2B_RECEIPT_MODE_INVALID": "Execution mode must be INTERNAL_QUALIFICATION or RELEASE.",
    "W2B_RECEIPT_FE_POLICY_INVALID": "Fe baseline and C15 decisions must remain explicitly undecided.",
    "W2B_RECEIPT_NON_FE_POLICY_INVALID": "Non-Fe policy decision fields must be NOT_APPLICABLE.",
    "W2B_RECEIPT_REPORT_INVALID": "The merge report differs from its pinned structural observations.",
    "W2B_RECEIPT_FE_REPORT_DRIFT_RELEASE_DENIED": "Known Fe report count/path drift forbids RELEASE use.",
    "W2B_RECEIPT_PHASE_FINGERPRINT_MISMATCH": "Runtime phases differ from the pinned count or fingerprint.",
    "W2B_RECEIPT_NE04_INVALID": "The NE-04 contract differs from the pinned schema, hash, or release state.",
    "W2B_RECEIPT_POLICY_INVALID": "The release policy differs from its pinned hash or generation.",
    "W2B_RECEIPT_RELEASE_DENIED": "Current NE-04 and release policy state deny RELEASE calculations.",
    "W2B_RECEIPT_FEATURE_INVALID": "The feature identifier is outside the exact Wave 2B feature set.",
    "W2B_RECEIPT_REQUEST_INVALID": "The complete request payload or database binding is invalid.",
    "W2B_RECEIPT_PHASE_SET_INVALID": "Candidate/requested/excluded/effective phases violate the explicit partition.",
    "W2B_RECEIPT_FE_C15_DECISION_REQUIRED": "Fe cannot omit or exclude C15_LAVES while its exclusion decision is undecided.",
    "W2B_RECEIPT_DOMAIN_INVALID": "A domain receipt violates its immutable binding contract.",
    "W2B_RECEIPT_RESULT_INVALID": "A result receipt violates its immutable binding contract.",
    "W2B_RECEIPT_BACKEND_BINDING_INVALID": "The result backend payload is not the exact feature-route backend schema.",
    "W2B_RECEIPT_RUNTIME_BINDING_INVALID": "The result runtime payload differs from its exact domain, profile, or execution snapshot.",
    "W2B_RECEIPT_CONTEXT_BINDING_INVALID": "The result context payload differs from its exact feature, mode, lease, or PRE snapshot.",
    "W2B_RECEIPT_DENIAL_BINDING_INVALID": "A result payload weakens the mandatory nonacceptance, noncoverage, or production denial state.",
    "W2B_RECEIPT_FAILURE_LEDGER_INVALID": "The result failure ledger is not explicit and ordinal ordered.",
    "W2B_RECEIPT_OUTPUT_DIGEST_INVALID": "The result output digest or byte count is invalid.",
    "W2B_RECEIPT_PRE_REHASH_MISMATCH": "A pre-execution rehash no longer matches the domain/profile receipt.",
    "W2B_RECEIPT_POST_REHASH_MISMATCH": "A post-execution rehash differs from the pre-execution snapshot.",
    "W2B_RECEIPT_LEASE_REQUIRED": "Backend execution requires one matching active ExecutionLease.",
    "W2B_RECEIPT_LEASE_STATE_INVALID": "The execution lease is inactive, reused, or in the wrong stage.",
    "W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID": "The private content-addressed execution snapshot is missing or changed.",
    "W2B_RECEIPT_EXECUTION_SNAPSHOT_LOCK_FAILED": "The private execution snapshot could not be held deny-write.",
}
WAVE2B_RECEIPT_REASON_CODES: Mapping[str, str] = MappingProxyType(_REASON_TEXT)


class ReceiptError(ValueError):
    """Stable fail-closed error emitted by this receipt layer."""

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


def _fail(reason_code: str) -> None:
    raise ReceiptError(reason_code)


def _strict_string(value: object, pattern: re.Pattern[str], reason: str) -> str:
    if type(value) is not str or unicodedata.normalize("NFC", value) != value:
        _fail(reason)
    if len(value) > _MAX_TEXT_LENGTH or pattern.fullmatch(value) is None:
        _fail(reason)
    return value


def _sha256(value: object, reason: str = "W2B_RECEIPT_FILE_HASH_MISMATCH") -> str:
    if type(value) is not str or _LOWER_SHA256.fullmatch(value) is None:
        _fail(reason)
    return value


def _execution_mode(value: object) -> str:
    if type(value) is not str or value not in EXECUTION_MODES:
        _fail("W2B_RECEIPT_MODE_INVALID")
    return value


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    normalized: set[str] = set()
    for key, value in pairs:
        nfc = unicodedata.normalize("NFC", key)
        if key in result or nfc in normalized:
            _fail("W2B_RECEIPT_JSON_DUPLICATE_KEY")
        result[key] = value
        normalized.add(nfc)
    return result


def _reject_constant(_value: str) -> None:
    _fail("W2B_RECEIPT_JSON_NONFINITE")


def _reject_raw_float(_value: str) -> None:
    _fail("W2B_RECEIPT_JSON_NOT_CANONICAL")


def _decode_f64(value: object) -> float:
    if (
        type(value) is not dict
        or set(value) != {"$f64"}
        or type(value["$f64"]) is not str
        or re.fullmatch(r"[0-9a-f]{16}", value["$f64"]) is None
    ):
        _fail("W2B_RECEIPT_JSON_INVALID")
    number = struct.unpack(">d", bytes.fromhex(value["$f64"]))[0]
    if not math.isfinite(number):
        _fail("W2B_RECEIPT_JSON_NONFINITE")
    return number


def _validate_loaded(value: object, depth: int = 0) -> None:
    if depth > _MAX_JSON_DEPTH:
        _fail("W2B_RECEIPT_JSON_LIMIT")
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if not -(2**63) <= value < 2**63:
            _fail("W2B_RECEIPT_JSON_LIMIT")
        return
    if type(value) is str:
        if len(value) > _MAX_TEXT_LENGTH or unicodedata.normalize("NFC", value) != value:
            _fail("W2B_RECEIPT_JSON_INVALID")
        return
    if type(value) is list:
        if len(value) > _MAX_CONTAINER_ITEMS:
            _fail("W2B_RECEIPT_JSON_LIMIT")
        for item in value:
            _validate_loaded(item, depth + 1)
        return
    if type(value) is dict:
        if len(value) > _MAX_CONTAINER_ITEMS:
            _fail("W2B_RECEIPT_JSON_LIMIT")
        if set(value) == {"$f64"}:
            _decode_f64(value)
            return
        if "$f64" in value:
            _fail("W2B_RECEIPT_JSON_INVALID")
        for key, item in value.items():
            if type(key) is not str:
                _fail("W2B_RECEIPT_JSON_INVALID")
            _validate_loaded(key, depth + 1)
            _validate_loaded(item, depth + 1)
        return
    _fail("W2B_RECEIPT_JSON_INVALID")


def strict_canonical_json_loads(data: bytes) -> Any:
    """Load exact canonical JSON (UTF-8, newline, binary64 as ``$f64``)."""

    if type(data) is not bytes or len(data) > _MAX_CANONICAL_JSON_BYTES:
        _fail("W2B_RECEIPT_JSON_LIMIT")
    if data.startswith(b"\xef\xbb\xbf"):
        _fail("W2B_RECEIPT_JSON_INVALID")
    try:
        value = json.loads(
            data.decode("utf-8", errors="strict"),
            object_pairs_hook=_pairs,
            parse_float=_reject_raw_float,
            parse_constant=_reject_constant,
        )
    except ReceiptError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as error:
        raise ReceiptError("W2B_RECEIPT_JSON_INVALID") from error
    _validate_loaded(value)
    if canonical_json_bytes(value) != data:
        _fail("W2B_RECEIPT_JSON_NOT_CANONICAL")
    return value


def _canonicalize(value: object, depth: int = 0) -> Any:
    if depth > _MAX_JSON_DEPTH:
        _fail("W2B_RECEIPT_JSON_LIMIT")
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if not -(2**63) <= value < 2**63:
            _fail("W2B_RECEIPT_JSON_LIMIT")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _fail("W2B_RECEIPT_JSON_NONFINITE")
        return {"$f64": struct.pack(">d", value).hex()}
    if type(value) is str:
        if len(value) > _MAX_TEXT_LENGTH or unicodedata.normalize("NFC", value) != value:
            _fail("W2B_RECEIPT_JSON_INVALID")
        return value
    if type(value) is dict:
        if len(value) > _MAX_CONTAINER_ITEMS:
            _fail("W2B_RECEIPT_JSON_LIMIT")
        if set(value) == {"$f64"}:
            _decode_f64(dict(value))
            return {"$f64": value["$f64"]}
        result: dict[str, Any] = {}
        normalized: set[str] = set()
        for key, item in value.items():
            if type(key) is not str or key == "$f64":
                _fail("W2B_RECEIPT_JSON_INVALID")
            nfc = unicodedata.normalize("NFC", key)
            if nfc != key or nfc in normalized:
                _fail("W2B_RECEIPT_JSON_INVALID")
            normalized.add(nfc)
            result[key] = _canonicalize(item, depth + 1)
        return result
    if type(value) in (list, tuple):
        if len(value) > _MAX_CONTAINER_ITEMS:
            _fail("W2B_RECEIPT_JSON_LIMIT")
        return [_canonicalize(item, depth + 1) for item in value]
    _fail("W2B_RECEIPT_JSON_INVALID")


def canonical_json_bytes(value: object) -> bytes:
    """Return the one exact receipt JSON representation with a final LF."""

    payload = _canonicalize(value)
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    if len(encoded) > _MAX_CANONICAL_JSON_BYTES:
        _fail("W2B_RECEIPT_JSON_LIMIT")
    return encoded


@dataclass(frozen=True, slots=True)
class CanonicalPayload:
    """Immutable exact JSON bytes plus their SHA-256 identity."""

    canonical_json: bytes
    sha256: str = field(init=False)

    def __post_init__(self) -> None:
        strict_canonical_json_loads(self.canonical_json)
        object.__setattr__(self, "sha256", hashlib.sha256(self.canonical_json).hexdigest())

    @classmethod
    def from_value(cls, value: object) -> "CanonicalPayload":
        return cls(canonical_json_bytes(value))

    @classmethod
    def from_bytes(cls, data: bytes) -> "CanonicalPayload":
        return cls(data)

    def value(self) -> Any:
        if (
            type(self.canonical_json) is not bytes
            or type(self.sha256) is not str
            or hashlib.sha256(self.canonical_json).hexdigest() != self.sha256
        ):
            _fail("W2B_RECEIPT_JSON_INVALID")
        return strict_canonical_json_loads(self.canonical_json)


def canonical_payload_digest(value: object) -> str:
    """Digest an arbitrary bounded canonicalizable JSON value."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _safe_relative_path(value: object) -> str:
    if type(value) is not str or not value or "\\" in value:
        _fail("W2B_RECEIPT_PATH_INVALID")
    if unicodedata.normalize("NFC", value) != value:
        _fail("W2B_RECEIPT_PATH_INVALID")
    posix = PurePosixPath(value)
    if posix.is_absolute() or value != posix.as_posix() or not posix.parts:
        _fail("W2B_RECEIPT_PATH_INVALID")
    for part in posix.parts:
        if (
            part in ("", ".", "..")
            or len(part) > 255
            or any(ord(character) < 32 or character in '<>:"|?*\\/' for character in part)
        ):
            _fail("W2B_RECEIPT_PATH_INVALID")
    return value


def _is_reparse(info: os.stat_result) -> bool:
    return bool(int(getattr(info, "st_file_attributes", 0)) & _REPARSE_POINT)


def _project_root(value: str | Path) -> Path:
    if not isinstance(value, (str, Path)):
        _fail("W2B_RECEIPT_PATH_INVALID")
    path = Path(value).expanduser()
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ReceiptError("W2B_RECEIPT_PATH_INVALID") from error
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or _is_reparse(info):
        _fail("W2B_RECEIPT_PATH_INVALID")
    return resolved


def _resolve_regular_file(root: Path, relative_path: str) -> Path:
    checked = _safe_relative_path(relative_path)
    current = root
    try:
        for index, part in enumerate(PurePosixPath(checked).parts):
            current = current / part
            info = current.lstat()
            if stat.S_ISLNK(info.st_mode) or _is_reparse(info):
                _fail("W2B_RECEIPT_FILE_INVALID")
            if index < len(PurePosixPath(checked).parts) - 1:
                if not stat.S_ISDIR(info.st_mode):
                    _fail("W2B_RECEIPT_FILE_INVALID")
            elif not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1:
                _fail("W2B_RECEIPT_FILE_INVALID")
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except ReceiptError:
        raise
    except (OSError, RuntimeError, ValueError) as error:
        raise ReceiptError("W2B_RECEIPT_FILE_INVALID") from error
    return resolved


@dataclass(frozen=True, slots=True)
class FileIdentity:
    role: str
    relative_path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if type(self.role) is not str or self.role not in _FILE_ROLES:
            _fail("W2B_RECEIPT_MANIFEST_INVALID")
        object.__setattr__(self, "relative_path", _safe_relative_path(self.relative_path))
        object.__setattr__(self, "sha256", _sha256(self.sha256))
        if (
            type(self.size_bytes) is not int
            or isinstance(self.size_bytes, bool)
            or self.size_bytes < 0
            or self.size_bytes > _MAX_FILE_BYTES[self.role]
        ):
            _fail("W2B_RECEIPT_FILE_TOO_LARGE")

    def as_dict(self) -> dict[str, object]:
        try:
            rebuilt = FileIdentity(
                role=self.role,
                relative_path=self.relative_path,
                sha256=self.sha256,
                size_bytes=self.size_bytes,
            )
        except Exception:
            _fail("W2B_RECEIPT_FILE_INVALID")
        return {
            "path": rebuilt.relative_path,
            "sha256": rebuilt.sha256,
            "size_bytes": rebuilt.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class FileHashObservation:
    role: str
    relative_path: str
    sha256: str
    size_bytes: int
    device: int
    inode: int
    link_count: int
    mtime_ns: int
    ctime_ns: int

    def __post_init__(self) -> None:
        if type(self.role) is not str or self.role not in _OBSERVATION_ROLES:
            _fail("W2B_RECEIPT_FILE_INVALID")
        object.__setattr__(self, "relative_path", _safe_relative_path(self.relative_path))
        object.__setattr__(self, "sha256", _sha256(self.sha256))
        for number in (
            self.size_bytes,
            self.device,
            self.inode,
            self.link_count,
            self.mtime_ns,
            self.ctime_ns,
        ):
            if type(number) is not int or isinstance(number, bool) or number < 0:
                _fail("W2B_RECEIPT_FILE_INVALID")
        if self.link_count != 1 or self.size_bytes > _MAX_FILE_BYTES[self.role]:
            _fail("W2B_RECEIPT_FILE_INVALID")

    def as_dict(self) -> dict[str, object]:
        try:
            rebuilt = FileHashObservation(
                role=self.role,
                relative_path=self.relative_path,
                sha256=self.sha256,
                size_bytes=self.size_bytes,
                device=self.device,
                inode=self.inode,
                link_count=self.link_count,
                mtime_ns=self.mtime_ns,
                ctime_ns=self.ctime_ns,
            )
        except Exception:
            _fail("W2B_RECEIPT_FILE_INVALID")
        return {
            "role": rebuilt.role,
            "path": rebuilt.relative_path,
            "sha256": rebuilt.sha256,
            "size_bytes": rebuilt.size_bytes,
            "device": rebuilt.device,
            "inode": rebuilt.inode,
            "link_count": rebuilt.link_count,
            "mtime_ns": rebuilt.mtime_ns,
            "ctime_ns": rebuilt.ctime_ns,
        }


def _stat_signature(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_nlink),
        int(info.st_size),
        int(info.st_mtime_ns),
        int(info.st_ctime_ns),
    )


def _read_stable_file(
    root: Path,
    role: str,
    relative_path: str,
    *,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
) -> tuple[bytes, FileHashObservation]:
    if role not in _MAX_FILE_BYTES:
        _fail("W2B_RECEIPT_FILE_INVALID")
    path = _resolve_regular_file(root, relative_path)
    maximum = _MAX_FILE_BYTES[role]
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    try:
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or _is_reparse(before)
                or int(before.st_nlink) != 1
            ):
                _fail("W2B_RECEIPT_FILE_INVALID")
            if before.st_size > maximum:
                _fail("W2B_RECEIPT_FILE_TOO_LARGE")
            while True:
                chunk = handle.read(min(_HASH_CHUNK_BYTES, maximum - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    _fail("W2B_RECEIPT_FILE_TOO_LARGE")
                chunks.append(chunk)
                digest.update(chunk)
            after = os.fstat(handle.fileno())
        path_after = path.lstat()
    except ReceiptError:
        raise
    except OSError as error:
        raise ReceiptError("W2B_RECEIPT_FILE_INVALID") from error
    if _stat_signature(before) != _stat_signature(after):
        _fail("W2B_RECEIPT_FILE_CHANGED")
    if (
        not stat.S_ISREG(after.st_mode)
        or _is_reparse(after)
        or int(after.st_nlink) != 1
        or not stat.S_ISREG(path_after.st_mode)
        or _is_reparse(path_after)
        or int(path_after.st_nlink) != 1
        or not os.path.samestat(after, path_after)
        or _stat_signature(after) != _stat_signature(path_after)
    ):
        _fail("W2B_RECEIPT_FILE_CHANGED")
    actual_sha = digest.hexdigest()
    if expected_size is not None and total != expected_size:
        _fail("W2B_RECEIPT_FILE_SIZE_MISMATCH")
    if expected_sha256 is not None and actual_sha != expected_sha256:
        _fail("W2B_RECEIPT_FILE_HASH_MISMATCH")
    observation = FileHashObservation(
        role=role,
        relative_path=relative_path,
        sha256=actual_sha,
        size_bytes=total,
        device=int(after.st_dev),
        inode=int(after.st_ino),
        link_count=int(after.st_nlink),
        mtime_ns=int(after.st_mtime_ns),
        ctime_ns=int(after.st_ctime_ns),
    )
    return b"".join(chunks), observation


def _validate_external_json(value: object, depth: int = 0) -> None:
    if depth > _MAX_JSON_DEPTH:
        _fail("W2B_RECEIPT_JSON_LIMIT")
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if not -(2**63) <= value < 2**63:
            _fail("W2B_RECEIPT_JSON_LIMIT")
        return
    if type(value) is float:
        if not math.isfinite(value):
            _fail("W2B_RECEIPT_JSON_NONFINITE")
        return
    if type(value) is str:
        if len(value) > _MAX_TEXT_LENGTH:
            _fail("W2B_RECEIPT_JSON_LIMIT")
        return
    if type(value) is list:
        if len(value) > _MAX_CONTAINER_ITEMS:
            _fail("W2B_RECEIPT_JSON_LIMIT")
        for item in value:
            _validate_external_json(item, depth + 1)
        return
    if type(value) is dict:
        if len(value) > _MAX_CONTAINER_ITEMS:
            _fail("W2B_RECEIPT_JSON_LIMIT")
        for key, item in value.items():
            if type(key) is not str:
                _fail("W2B_RECEIPT_JSON_INVALID")
            _validate_external_json(item, depth + 1)
        return
    _fail("W2B_RECEIPT_JSON_INVALID")


def _external_json(data: bytes) -> Any:
    try:
        value = json.loads(
            data.decode("utf-8-sig", errors="strict"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except ReceiptError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as error:
        raise ReceiptError("W2B_RECEIPT_JSON_INVALID") from error
    _validate_external_json(value)
    return value


def _decode_tdb(payload: bytes) -> str:
    for encoding in _ENCODINGS:
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    _fail("W2B_RECEIPT_PHASE_FINGERPRINT_MISMATCH")
    raise AssertionError("unreachable")


def _command_keyword(command: str) -> str:
    match = re.match(r"\s*([A-Za-z_]+)", command)
    return match.group(1).upper() if match else ""


def _declared_phases(payload: bytes) -> tuple[str, ...]:
    text = _decode_tdb(payload)
    active = "\n".join(line.split("$", 1)[0] for line in text.splitlines())
    references = _REFERENCE_MARKER.search(active)
    if references:
        active = active[: references.start()]
    commands = active.split("!")
    remainder = commands.pop()
    if remainder.strip() and _command_keyword(remainder) == "PHASE":
        _fail("W2B_RECEIPT_PHASE_FINGERPRINT_MISMATCH")
    phases: set[str] = set()
    declarations = 0
    for command in commands:
        command = command.strip()
        if not command or _command_keyword(command) != "PHASE":
            continue
        match = _PHASE_NAME.match(command)
        if match is None:
            _fail("W2B_RECEIPT_PHASE_FINGERPRINT_MISMATCH")
        phase = match.group(1).upper().split(":", 1)[0]
        if phase in phases:
            _fail("W2B_RECEIPT_PHASE_FINGERPRINT_MISMATCH")
        phases.add(phase)
        declarations += 1
    if declarations != len(phases) or not phases:
        _fail("W2B_RECEIPT_PHASE_FINGERPRINT_MISMATCH")
    return tuple(sorted(phases))


def phase_fingerprint(phases: tuple[str, ...]) -> str:
    """Fingerprint an exact canonical phase set using sorted UTF-8 LF rows."""

    checked = _phase_tuple(phases, allow_empty=False)
    payload = "".join(f"{name}\n" for name in checked).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _phase_tuple(value: object, *, allow_empty: bool) -> tuple[str, ...]:
    if type(value) is not tuple or (not value and not allow_empty):
        _fail("W2B_RECEIPT_PHASE_SET_INVALID")
    result: list[str] = []
    previous: str | None = None
    for item in value:
        phase = _strict_string(item, _PHASE_TOKEN, "W2B_RECEIPT_PHASE_SET_INVALID")
        if previous is not None and phase <= previous:
            _fail("W2B_RECEIPT_PHASE_SET_INVALID")
        result.append(phase)
        previous = phase
    return tuple(result)


@dataclass(frozen=True, slots=True)
class ReportObservation:
    """Pinned legacy merge-report facts; drift is never normalized away."""

    reported_phase_count: int
    runtime_phase_count: int
    phase_count_drift: int
    embedded_paths: tuple[tuple[str, str], ...]
    embedded_path_drift: bool
    release_blocking: bool
    status: str

    def __post_init__(self) -> None:
        for value in (self.reported_phase_count, self.runtime_phase_count):
            if type(value) is not int or isinstance(value, bool) or value <= 0:
                _fail("W2B_RECEIPT_REPORT_INVALID")
        if (
            type(self.phase_count_drift) is not int
            or isinstance(self.phase_count_drift, bool)
            or self.phase_count_drift
            != self.reported_phase_count - self.runtime_phase_count
        ):
            _fail("W2B_RECEIPT_REPORT_INVALID")
        if type(self.embedded_paths) is not tuple or len(self.embedded_paths) != 3:
            _fail("W2B_RECEIPT_REPORT_INVALID")
        expected_fields = ("destination", "mobility_source", "thermodynamic_source")
        observed_fields: list[str] = []
        for pair in self.embedded_paths:
            if type(pair) is not tuple or len(pair) != 2:
                _fail("W2B_RECEIPT_REPORT_INVALID")
            field_name, legacy_path = pair
            if type(field_name) is not str or type(legacy_path) is not str:
                _fail("W2B_RECEIPT_REPORT_INVALID")
            if not legacy_path.startswith("/Volumes/Disk/Pet/ThermoGar/"):
                _fail("W2B_RECEIPT_REPORT_INVALID")
            observed_fields.append(field_name)
        if tuple(observed_fields) != expected_fields:
            _fail("W2B_RECEIPT_REPORT_INVALID")
        if type(self.embedded_path_drift) is not bool or type(self.release_blocking) is not bool:
            _fail("W2B_RECEIPT_REPORT_INVALID")
        _strict_string(self.status, re.compile(r"[A-Z0-9_]{1,128}\Z"), "W2B_RECEIPT_REPORT_INVALID")

    def as_dict(self) -> dict[str, object]:
        try:
            rebuilt = ReportObservation(
                reported_phase_count=self.reported_phase_count,
                runtime_phase_count=self.runtime_phase_count,
                phase_count_drift=self.phase_count_drift,
                embedded_paths=self.embedded_paths,
                embedded_path_drift=self.embedded_path_drift,
                release_blocking=self.release_blocking,
                status=self.status,
            )
        except Exception:
            _fail("W2B_RECEIPT_REPORT_INVALID")
        return {
            "reported_phase_count": rebuilt.reported_phase_count,
            "runtime_phase_count": rebuilt.runtime_phase_count,
            "phase_count_drift": rebuilt.phase_count_drift,
            "embedded_paths": {key: value for key, value in rebuilt.embedded_paths},
            "embedded_path_drift": rebuilt.embedded_path_drift,
            "release_blocking": rebuilt.release_blocking,
            "status": rebuilt.status,
        }


@dataclass(frozen=True, slots=True)
class DatabaseProfileReceipt:
    """Exact content-addressed identity for one Ni, Al, or Fe profile."""

    family: str
    profile: str
    profile_role: str
    verification_mode: str
    source: FileIdentity
    thermodynamic: FileIdentity
    mobility: FileIdentity
    runtime: FileIdentity
    report: FileIdentity
    passport: FileIdentity
    phase_fingerprint_algorithm: str
    phase_count: int
    phase_fingerprint_sha256: str
    report_observation: ReportObservation
    baseline_decision: str
    c15_exclusion_decision: str
    profile_manifest_path: str
    profile_manifest_sha256: str
    ne04_contract_path: str
    ne04_contract_sha256: str
    ne04_contract_schema: str
    ne04_calculations_enabled: bool
    release_policy_path: str
    release_policy_sha256: str
    policy_generation: str
    policy_calculations_enabled: bool
    release_enabled: bool
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.family) is not str or self.family not in SUPPORTED_DATABASE_FAMILIES:
            _fail("W2B_RECEIPT_FAMILY_INVALID")
        if type(self.profile) is not str:
            _fail("W2B_RECEIPT_PROFILE_REQUIRED")
        if self.family == "fe":
            if self.profile not in SUPPORTED_FE_PROFILE_IDS:
                _fail("W2B_RECEIPT_PROFILE_INVALID")
        elif self.profile != _PROFILE_BY_NON_FE_FAMILY[self.family]:
            _fail("W2B_RECEIPT_PROFILE_INVALID")
        if self.profile_role != _PROFILE_ROLE.get((self.family, self.profile)):
            _fail("W2B_RECEIPT_PROFILE_ROLE_INVALID")
        mode = _execution_mode(self.verification_mode)
        expected_files = {
            "source": self.source,
            "thermodynamic": self.thermodynamic,
            "mobility": self.mobility,
            "runtime": self.runtime,
            "report": self.report,
            "passport": self.passport,
        }
        if any(type(item) is not FileIdentity or item.role != role for role, item in expected_files.items()):
            _fail("W2B_RECEIPT_MANIFEST_INVALID")
        if self.phase_fingerprint_algorithm != PHASE_FINGERPRINT_ALGORITHM:
            _fail("W2B_RECEIPT_PHASE_FINGERPRINT_MISMATCH")
        if type(self.phase_count) is not int or isinstance(self.phase_count, bool) or self.phase_count <= 0:
            _fail("W2B_RECEIPT_PHASE_FINGERPRINT_MISMATCH")
        object.__setattr__(
            self,
            "phase_fingerprint_sha256",
            _sha256(self.phase_fingerprint_sha256, "W2B_RECEIPT_PHASE_FINGERPRINT_MISMATCH"),
        )
        if type(self.report_observation) is not ReportObservation:
            _fail("W2B_RECEIPT_REPORT_INVALID")
        if self.report_observation.runtime_phase_count != self.phase_count:
            _fail("W2B_RECEIPT_REPORT_INVALID")
        if self.family == "fe":
            if (
                self.baseline_decision != FE_POLICY_UNDECIDED
                or self.c15_exclusion_decision != FE_POLICY_UNDECIDED
            ):
                _fail("W2B_RECEIPT_FE_POLICY_INVALID")
            if (
                not self.report_observation.release_blocking
                or self.report_observation.phase_count_drift == 0
                or not self.report_observation.embedded_path_drift
            ):
                _fail("W2B_RECEIPT_REPORT_INVALID")
            if mode == RELEASE:
                _fail("W2B_RECEIPT_FE_REPORT_DRIFT_RELEASE_DENIED")
        elif (
            self.baseline_decision != POLICY_NOT_APPLICABLE
            or self.c15_exclusion_decision != POLICY_NOT_APPLICABLE
        ):
            _fail("W2B_RECEIPT_NON_FE_POLICY_INVALID")
        object.__setattr__(self, "profile_manifest_path", _safe_relative_path(self.profile_manifest_path))
        object.__setattr__(self, "profile_manifest_sha256", _sha256(self.profile_manifest_sha256))
        object.__setattr__(self, "ne04_contract_path", _safe_relative_path(self.ne04_contract_path))
        object.__setattr__(self, "ne04_contract_sha256", _sha256(self.ne04_contract_sha256))
        if self.ne04_contract_schema != NE04_CONTRACT_SCHEMA or type(self.ne04_calculations_enabled) is not bool:
            _fail("W2B_RECEIPT_NE04_INVALID")
        object.__setattr__(self, "release_policy_path", _safe_relative_path(self.release_policy_path))
        object.__setattr__(self, "release_policy_sha256", _sha256(self.release_policy_sha256))
        if (
            type(self.policy_generation) is not str
            or not self.policy_generation
            or len(self.policy_generation) > 512
            or type(self.policy_calculations_enabled) is not bool
            or type(self.release_enabled) is not bool
        ):
            _fail("W2B_RECEIPT_POLICY_INVALID")
        if mode == RELEASE and (
            not self.release_enabled
            or not self.ne04_calculations_enabled
            or not self.policy_calculations_enabled
        ):
            _fail("W2B_RECEIPT_RELEASE_DENIED")
        digest = canonical_payload_digest(self._payload())
        if (
            mode == INTERNAL_QUALIFICATION
            and digest != _PINNED_INTERNAL_PROFILE_RECEIPT_DIGESTS.get(
                (self.family, self.profile)
            )
        ):
            _fail("W2B_RECEIPT_PROFILE_INVALID")
        object.__setattr__(self, "canonical_digest", digest)

    @property
    def files(self) -> tuple[FileIdentity, ...]:
        return (
            _copy_profile_file(self.source, "source"),
            _copy_profile_file(self.thermodynamic, "thermodynamic"),
            _copy_profile_file(self.mobility, "mobility"),
            _copy_profile_file(self.runtime, "runtime"),
            _copy_profile_file(self.report, "report"),
            _copy_profile_file(self.passport, "passport"),
        )

    @property
    def thermo(self) -> FileIdentity:
        """Short, read-only name for the converted thermodynamic file pin."""

        return _copy_profile_file(self.thermodynamic, "thermodynamic")

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": PROFILE_RECEIPT_SCHEMA,
            "family": self.family,
            "profile": self.profile,
            "profile_role": self.profile_role,
            "verification_mode": self.verification_mode,
            "files": {item.role: item.as_dict() for item in self.files},
            "phases": {
                "algorithm": self.phase_fingerprint_algorithm,
                "count": self.phase_count,
                "sha256": self.phase_fingerprint_sha256,
            },
            "report_observation": self.report_observation.as_dict(),
            "fe_policy": {
                "baseline_decision": self.baseline_decision,
                "c15_exclusion_decision": self.c15_exclusion_decision,
            },
            "profile_manifest": {
                "path": self.profile_manifest_path,
                "sha256": self.profile_manifest_sha256,
            },
            "ne04_contract": {
                "path": self.ne04_contract_path,
                "sha256": self.ne04_contract_sha256,
                "schema_version": self.ne04_contract_schema,
                "calculations_enabled": self.ne04_calculations_enabled,
            },
            "release_policy": {
                "path": self.release_policy_path,
                "sha256": self.release_policy_sha256,
                "generation": self.policy_generation,
                "calculations_enabled": self.policy_calculations_enabled,
            },
            "release_enabled": self.release_enabled,
            "acceptance_claim": ACCEPTANCE_CLAIM,
            "counts_toward_feature_coverage": COUNTS_TOWARD_FEATURE_COVERAGE,
            "production_use": PRODUCTION_USE,
        }

    def as_dict(self) -> dict[str, object]:
        rebuilt = _rebuild_profile_receipt(self)
        payload = rebuilt._payload()
        payload["canonical_digest"] = rebuilt.canonical_digest
        return payload


def _copy_profile_file(value: object, role: str) -> FileIdentity:
    try:
        if type(value) is not FileIdentity or value.role != role:
            _fail("W2B_RECEIPT_PROFILE_INVALID")
        return FileIdentity(
            role=value.role,
            relative_path=value.relative_path,
            sha256=value.sha256,
            size_bytes=value.size_bytes,
        )
    except Exception:
        _fail("W2B_RECEIPT_PROFILE_INVALID")
    raise AssertionError("unreachable")


def _copy_report_observation(value: object) -> ReportObservation:
    try:
        if type(value) is not ReportObservation:
            _fail("W2B_RECEIPT_PROFILE_INVALID")
        return ReportObservation(
            reported_phase_count=value.reported_phase_count,
            runtime_phase_count=value.runtime_phase_count,
            phase_count_drift=value.phase_count_drift,
            embedded_paths=value.embedded_paths,
            embedded_path_drift=value.embedded_path_drift,
            release_blocking=value.release_blocking,
            status=value.status,
        )
    except Exception:
        _fail("W2B_RECEIPT_PROFILE_INVALID")
    raise AssertionError("unreachable")


def _rebuild_profile_receipt(value: object) -> DatabaseProfileReceipt:
    """Reconstruct every profile invariant from exact primitive field values."""

    if type(value) is not DatabaseProfileReceipt:
        _fail("W2B_RECEIPT_PROFILE_INVALID")
    try:
        rebuilt = DatabaseProfileReceipt(
            family=value.family,
            profile=value.profile,
            profile_role=value.profile_role,
            verification_mode=value.verification_mode,
            source=_copy_profile_file(value.source, "source"),
            thermodynamic=_copy_profile_file(value.thermodynamic, "thermodynamic"),
            mobility=_copy_profile_file(value.mobility, "mobility"),
            runtime=_copy_profile_file(value.runtime, "runtime"),
            report=_copy_profile_file(value.report, "report"),
            passport=_copy_profile_file(value.passport, "passport"),
            phase_fingerprint_algorithm=value.phase_fingerprint_algorithm,
            phase_count=value.phase_count,
            phase_fingerprint_sha256=value.phase_fingerprint_sha256,
            report_observation=_copy_report_observation(value.report_observation),
            baseline_decision=value.baseline_decision,
            c15_exclusion_decision=value.c15_exclusion_decision,
            profile_manifest_path=value.profile_manifest_path,
            profile_manifest_sha256=value.profile_manifest_sha256,
            ne04_contract_path=value.ne04_contract_path,
            ne04_contract_sha256=value.ne04_contract_sha256,
            ne04_contract_schema=value.ne04_contract_schema,
            ne04_calculations_enabled=value.ne04_calculations_enabled,
            release_policy_path=value.release_policy_path,
            release_policy_sha256=value.release_policy_sha256,
            policy_generation=value.policy_generation,
            policy_calculations_enabled=value.policy_calculations_enabled,
            release_enabled=value.release_enabled,
        )
    except ReceiptError:
        _fail("W2B_RECEIPT_PROFILE_INVALID")
    except Exception:
        _fail("W2B_RECEIPT_PROFILE_INVALID")
    if type(value.canonical_digest) is not str or value.canonical_digest != rebuilt.canonical_digest:
        _fail("W2B_RECEIPT_PROFILE_INVALID")
    return rebuilt


def _exact_keys(value: object, keys: set[str], reason: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        _fail(reason)
    return value


def _manifest_file(role: str, value: object) -> FileIdentity:
    card = _exact_keys(
        value,
        {"path", "sha256", "size_bytes"},
        "W2B_RECEIPT_MANIFEST_INVALID",
    )
    return FileIdentity(
        role=role,
        relative_path=card["path"],
        sha256=card["sha256"],
        size_bytes=card["size_bytes"],
    )


def _manifest_report_observation(value: object) -> ReportObservation:
    card = _exact_keys(
        value,
        {
            "reported_phase_count",
            "runtime_phase_count",
            "phase_count_drift",
            "embedded_paths",
            "embedded_path_drift",
            "release_blocking",
            "status",
        },
        "W2B_RECEIPT_MANIFEST_INVALID",
    )
    paths = _exact_keys(
        card["embedded_paths"],
        {"destination", "mobility_source", "thermodynamic_source"},
        "W2B_RECEIPT_MANIFEST_INVALID",
    )
    return ReportObservation(
        reported_phase_count=card["reported_phase_count"],
        runtime_phase_count=card["runtime_phase_count"],
        phase_count_drift=card["phase_count_drift"],
        embedded_paths=tuple((key, paths[key]) for key in sorted(paths)),
        embedded_path_drift=card["embedded_path_drift"],
        release_blocking=card["release_blocking"],
        status=card["status"],
    )


def _validate_profile_manifest(value: object) -> dict[str, Any]:
    manifest = _exact_keys(
        value,
        {
            "schema_version",
            "acceptance_claim",
            "counts_toward_feature_coverage",
            "production_use",
            "calculations_enabled",
            "release_enabled",
            "phase_fingerprint_algorithm",
            "execution_modes",
            "ne04_contract",
            "release_policy",
            "profiles",
        },
        "W2B_RECEIPT_MANIFEST_INVALID",
    )
    if (
        manifest["schema_version"] != PROFILE_MANIFEST_SCHEMA
        or manifest["acceptance_claim"] is not False
        or manifest["counts_toward_feature_coverage"] is not False
        or manifest["production_use"] != PRODUCTION_USE
        or manifest["calculations_enabled"] is not False
        or manifest["release_enabled"] is not False
        or manifest["phase_fingerprint_algorithm"] != PHASE_FINGERPRINT_ALGORITHM
        or manifest["execution_modes"] != list(EXECUTION_MODES)
    ):
        _fail("W2B_RECEIPT_MANIFEST_INVALID")
    ne04 = _exact_keys(
        manifest["ne04_contract"],
        {"path", "sha256", "size_bytes", "schema_version", "calculations_enabled"},
        "W2B_RECEIPT_MANIFEST_INVALID",
    )
    _safe_relative_path(ne04["path"])
    _sha256(ne04["sha256"])
    if (
        type(ne04["size_bytes"]) is not int
        or ne04["size_bytes"] < 0
        or ne04["size_bytes"] > _MAX_FILE_BYTES["ne04_contract"]
        or ne04["schema_version"] != NE04_CONTRACT_SCHEMA
        or ne04["calculations_enabled"] is not False
    ):
        _fail("W2B_RECEIPT_MANIFEST_INVALID")
    policy = _exact_keys(
        manifest["release_policy"],
        {"path", "sha256", "size_bytes", "generation", "calculations_enabled"},
        "W2B_RECEIPT_MANIFEST_INVALID",
    )
    _safe_relative_path(policy["path"])
    _sha256(policy["sha256"])
    if (
        type(policy["size_bytes"]) is not int
        or policy["size_bytes"] < 0
        or policy["size_bytes"] > _MAX_FILE_BYTES["release_policy"]
        or type(policy["generation"]) is not str
        or not policy["generation"]
        or len(policy["generation"]) > 512
        or policy["calculations_enabled"] is not False
    ):
        _fail("W2B_RECEIPT_MANIFEST_INVALID")
    profiles = manifest["profiles"]
    if type(profiles) is not list or len(profiles) != 4:
        _fail("W2B_RECEIPT_MANIFEST_INVALID")
    expected_order = (
        ("ni", "mc_ni_v2036"),
        ("al", "mc_al_v2037"),
        ("fe", "thermogar_patch"),
        ("fe", "upstream_original"),
    )
    observed: list[tuple[str, str]] = []
    for card_value in profiles:
        card = _exact_keys(
            card_value,
            {
                "family",
                "profile",
                "profile_role",
                "files",
                "phases",
                "report_observation",
                "fe_policy",
            },
            "W2B_RECEIPT_MANIFEST_INVALID",
        )
        family = card["family"]
        profile = card["profile"]
        if type(family) is not str or family not in SUPPORTED_DATABASE_FAMILIES:
            _fail("W2B_RECEIPT_MANIFEST_INVALID")
        if type(profile) is not str or _PROFILE_ROLE.get((family, profile)) != card["profile_role"]:
            _fail("W2B_RECEIPT_MANIFEST_INVALID")
        observed.append((family, profile))
        files = _exact_keys(card["files"], set(_FILE_ROLES), "W2B_RECEIPT_MANIFEST_INVALID")
        for role in _FILE_ROLES:
            _manifest_file(role, files[role])
        phases = _exact_keys(
            card["phases"],
            {"algorithm", "count", "sha256"},
            "W2B_RECEIPT_MANIFEST_INVALID",
        )
        if (
            phases["algorithm"] != PHASE_FINGERPRINT_ALGORITHM
            or type(phases["count"]) is not int
            or phases["count"] <= 0
        ):
            _fail("W2B_RECEIPT_MANIFEST_INVALID")
        _sha256(phases["sha256"], "W2B_RECEIPT_MANIFEST_INVALID")
        report = _manifest_report_observation(card["report_observation"])
        policy_card = _exact_keys(
            card["fe_policy"],
            {"baseline_decision", "c15_exclusion_decision"},
            "W2B_RECEIPT_MANIFEST_INVALID",
        )
        if family == "fe":
            if (
                policy_card["baseline_decision"] != FE_POLICY_UNDECIDED
                or policy_card["c15_exclusion_decision"] != FE_POLICY_UNDECIDED
                or report.status != "PINNED_FE_REPORT_COUNT_AND_PATH_DRIFT_INTERNAL_ONLY"
                or not report.release_blocking
            ):
                _fail("W2B_RECEIPT_MANIFEST_INVALID")
        elif (
            policy_card["baseline_decision"] != POLICY_NOT_APPLICABLE
            or policy_card["c15_exclusion_decision"] != POLICY_NOT_APPLICABLE
            or report.release_blocking
            or report.phase_count_drift != 0
        ):
            _fail("W2B_RECEIPT_MANIFEST_INVALID")
    if tuple(observed) != expected_order:
        _fail("W2B_RECEIPT_MANIFEST_INVALID")
    return manifest


def _validate_report_file(
    report_payload: bytes,
    observation: ReportObservation,
    thermodynamic: FileIdentity,
    mobility: FileIdentity,
    runtime: FileIdentity,
) -> None:
    report = _external_json(report_payload)
    if type(report) is not dict:
        _fail("W2B_RECEIPT_REPORT_INVALID")
    if report.get("thermodynamic_phase_count") != observation.reported_phase_count:
        _fail("W2B_RECEIPT_REPORT_INVALID")
    paths = dict(observation.embedded_paths)
    for key in ("destination", "mobility_source", "thermodynamic_source"):
        if report.get(key) != paths[key]:
            _fail("W2B_RECEIPT_REPORT_INVALID")
    expected_basenames = {
        "destination": PurePosixPath(runtime.relative_path).name,
        "mobility_source": PurePosixPath(mobility.relative_path).name,
        "thermodynamic_source": PurePosixPath(thermodynamic.relative_path).name,
    }
    if any(PurePosixPath(paths[key]).name != basename for key, basename in expected_basenames.items()):
        _fail("W2B_RECEIPT_REPORT_INVALID")
    actual_path_drift = any(
        paths[key] != {
            "destination": runtime.relative_path,
            "mobility_source": mobility.relative_path,
            "thermodynamic_source": thermodynamic.relative_path,
        }[key]
        for key in paths
    )
    if actual_path_drift != observation.embedded_path_drift:
        _fail("W2B_RECEIPT_REPORT_INVALID")


def _nested_profile_file(
    card: object,
    expected: FileIdentity,
) -> None:
    if type(card) is not dict:
        _fail("W2B_RECEIPT_REPORT_INVALID")
    path = card.get("path")
    sha = card.get("sha256")
    if (
        type(path) is not str
        or PurePosixPath(path).name != PurePosixPath(expected.relative_path).name
        or type(sha) is not str
        or sha.lower() != expected.sha256
    ):
        _fail("W2B_RECEIPT_REPORT_INVALID")


def _validate_fe_passport(
    passport_payload: bytes,
    profile: str,
    source: FileIdentity,
    thermodynamic: FileIdentity,
    mobility: FileIdentity,
    runtime: FileIdentity,
) -> None:
    passport = _external_json(passport_payload)
    if type(passport) is not dict or passport.get("schema_version") != 2:
        _fail("W2B_RECEIPT_REPORT_INVALID")
    source_card = passport.get("source_database")
    if type(source_card) is not dict:
        _fail("W2B_RECEIPT_REPORT_INVALID")
    if (
        str(source_card.get("thermodynamic_sha256", "")).lower() != source.sha256
        or str(source_card.get("mobility_sha256", "")).lower() != mobility.sha256
    ):
        _fail("W2B_RECEIPT_REPORT_INVALID")
    section_name = (
        "working_profile"
        if profile == "thermogar_patch"
        else "upstream_unpatched_diagnostic_profile"
    )
    section = passport.get(section_name)
    if type(section) is not dict:
        _fail("W2B_RECEIPT_REPORT_INVALID")
    _nested_profile_file(section.get("thermodynamic_database"), thermodynamic)
    _nested_profile_file(section.get("thermodynamic_plus_mobility_database"), runtime)


def _profile_card(manifest: dict[str, Any], family: str, profile: str) -> dict[str, Any]:
    matches = [
        card
        for card in manifest["profiles"]
        if card.get("family") == family and card.get("profile") == profile
    ]
    if len(matches) != 1:
        _fail("W2B_RECEIPT_PROFILE_INVALID")
    return matches[0]


def _load_profile_impl(
    project_root: str | Path,
    family: object,
    profile: object,
    execution_mode: object,
) -> tuple[DatabaseProfileReceipt, tuple[FileHashObservation, ...], tuple[str, ...]]:
    root = _project_root(project_root)
    if type(family) is not str or family not in SUPPORTED_DATABASE_FAMILIES:
        _fail("W2B_RECEIPT_FAMILY_INVALID")
    if type(profile) is not str or not profile:
        _fail("W2B_RECEIPT_PROFILE_REQUIRED")
    mode = _execution_mode(execution_mode)
    manifest_bytes, manifest_observation = _read_stable_file(
        root,
        "profile_manifest",
        DEFAULT_PROFILE_MANIFEST_PATH,
        expected_sha256=PROFILE_MANIFEST_SHA256,
    )
    manifest = _validate_profile_manifest(strict_canonical_json_loads(manifest_bytes))
    card = _profile_card(manifest, family, profile)

    policy_card = manifest["release_policy"]
    _policy_bytes, policy_observation = _read_stable_file(
        root,
        "release_policy",
        policy_card["path"],
        expected_sha256=policy_card["sha256"],
        expected_size=policy_card["size_bytes"],
    )
    ne04_card = manifest["ne04_contract"]
    ne04_bytes, ne04_observation = _read_stable_file(
        root,
        "ne04_contract",
        ne04_card["path"],
        expected_sha256=ne04_card["sha256"],
        expected_size=ne04_card["size_bytes"],
    )
    ne04 = _external_json(ne04_bytes)
    if (
        type(ne04) is not dict
        or ne04.get("schema_version") != ne04_card["schema_version"]
        or ne04.get("calculations_enabled") is not ne04_card["calculations_enabled"]
    ):
        _fail("W2B_RECEIPT_NE04_INVALID")

    file_cards = card["files"]
    identities: dict[str, FileIdentity] = {}
    payloads: dict[str, bytes] = {}
    observations: list[FileHashObservation] = [
        manifest_observation,
        policy_observation,
        ne04_observation,
    ]
    for role in _FILE_ROLES:
        identity = _manifest_file(role, file_cards[role])
        payload, observation = _read_stable_file(
            root,
            role,
            identity.relative_path,
            expected_sha256=identity.sha256,
            expected_size=identity.size_bytes,
        )
        identities[role] = identity
        payloads[role] = payload
        observations.append(observation)

    phases = _declared_phases(payloads["runtime"])
    phases_card = card["phases"]
    if (
        len(phases) != phases_card["count"]
        or phase_fingerprint(phases) != phases_card["sha256"]
    ):
        _fail("W2B_RECEIPT_PHASE_FINGERPRINT_MISMATCH")
    report_observation = _manifest_report_observation(card["report_observation"])
    if report_observation.runtime_phase_count != len(phases):
        _fail("W2B_RECEIPT_REPORT_INVALID")
    _validate_report_file(
        payloads["report"],
        report_observation,
        identities["thermodynamic"],
        identities["mobility"],
        identities["runtime"],
    )
    if family == "fe":
        _validate_fe_passport(
            payloads["passport"],
            profile,
            identities["source"],
            identities["thermodynamic"],
            identities["mobility"],
            identities["runtime"],
        )
    fe_policy = card["fe_policy"]
    receipt = DatabaseProfileReceipt(
        family=family,
        profile=profile,
        profile_role=card["profile_role"],
        verification_mode=mode,
        source=identities["source"],
        thermodynamic=identities["thermodynamic"],
        mobility=identities["mobility"],
        runtime=identities["runtime"],
        report=identities["report"],
        passport=identities["passport"],
        phase_fingerprint_algorithm=phases_card["algorithm"],
        phase_count=phases_card["count"],
        phase_fingerprint_sha256=phases_card["sha256"],
        report_observation=report_observation,
        baseline_decision=fe_policy["baseline_decision"],
        c15_exclusion_decision=fe_policy["c15_exclusion_decision"],
        profile_manifest_path=DEFAULT_PROFILE_MANIFEST_PATH,
        profile_manifest_sha256=manifest_observation.sha256,
        ne04_contract_path=ne04_card["path"],
        ne04_contract_sha256=ne04_card["sha256"],
        ne04_contract_schema=ne04_card["schema_version"],
        ne04_calculations_enabled=ne04_card["calculations_enabled"],
        release_policy_path=policy_card["path"],
        release_policy_sha256=policy_card["sha256"],
        policy_generation=policy_card["generation"],
        policy_calculations_enabled=policy_card["calculations_enabled"],
        release_enabled=manifest["release_enabled"],
    )
    return receipt, tuple(observations), phases


def load_database_profile_receipt(
    project_root: str | Path,
    family: object,
    profile: object,
    execution_mode: object,
) -> DatabaseProfileReceipt:
    """Hash and load one exact profile; no family has an implicit alias."""

    receipt, _observations, _phases = _load_profile_impl(
        project_root,
        family,
        profile,
        execution_mode,
    )
    return receipt


def runtime_phase_names(
    project_root: str | Path,
    profile_receipt: object,
) -> tuple[str, ...]:
    """Return the verified full runtime phase set for an existing receipt."""

    profile_receipt = _rebuild_profile_receipt(profile_receipt)
    current, _observations, phases = _load_profile_impl(
        project_root,
        profile_receipt.family,
        profile_receipt.profile,
        profile_receipt.verification_mode,
    )
    if canonical_json_bytes(current._payload()) != canonical_json_bytes(profile_receipt._payload()):
        _fail("W2B_RECEIPT_MANIFEST_HASH_MISMATCH")
    return phases


def request_database_binding(profile_receipt: object) -> dict[str, object]:
    """Return the exact database block required in a full request payload."""

    profile_receipt = _rebuild_profile_receipt(profile_receipt)
    return {
        "family": profile_receipt.family,
        "profile": profile_receipt.profile,
        "runtime_sha256": profile_receipt.runtime.sha256,
        "profile_receipt_digest": profile_receipt.canonical_digest,
        "baseline_decision": profile_receipt.baseline_decision,
        "c15_exclusion_decision": profile_receipt.c15_exclusion_decision,
    }


def _payload_mapping(payload: CanonicalPayload, reason: str) -> dict[str, Any]:
    value = payload.value()
    if type(value) is not dict:
        _fail(reason)
    return value


def _validate_full_request(
    feature_id: str,
    payload: CanonicalPayload,
    profile: DatabaseProfileReceipt,
) -> None:
    request = _payload_mapping(payload, "W2B_RECEIPT_REQUEST_INVALID")
    if request.get("feature_id") != feature_id:
        _fail("W2B_RECEIPT_REQUEST_INVALID")
    database = request.get("database")
    expected = request_database_binding(profile)
    if type(database) is not dict or database != expected:
        _fail("W2B_RECEIPT_REQUEST_INVALID")


@dataclass(frozen=True, slots=True)
class DomainReceipt:
    """Full request and explicit phase-domain receipt bound to NE-04."""

    feature_id: str
    full_request: CanonicalPayload
    profile_receipt: DatabaseProfileReceipt
    ne04_contract_path: str
    ne04_contract_sha256: str
    ne04_contract_schema: str
    candidate_phases: tuple[str, ...]
    requested_phases: tuple[str, ...]
    excluded_phases: tuple[str, ...]
    effective_phases: tuple[str, ...]
    bounds: CanonicalPayload
    solver_options: CanonicalPayload
    execution_mode: str
    policy_generation: str
    authorization_state: str
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        feature = _strict_string(
            self.feature_id,
            _FEATURE_TOKEN,
            "W2B_RECEIPT_FEATURE_INVALID",
        )
        if feature not in SUPPORTED_WAVE2B_FEATURES:
            _fail("W2B_RECEIPT_FEATURE_INVALID")
        full_request = _copy_canonical_payload(
            self.full_request,
            "W2B_RECEIPT_REQUEST_INVALID",
        )
        profile_receipt = _rebuild_profile_receipt(self.profile_receipt)
        object.__setattr__(self, "full_request", full_request)
        object.__setattr__(self, "profile_receipt", profile_receipt)
        mode = _execution_mode(self.execution_mode)
        if self.profile_receipt.verification_mode != mode:
            _fail("W2B_RECEIPT_DOMAIN_INVALID")
        object.__setattr__(self, "ne04_contract_path", _safe_relative_path(self.ne04_contract_path))
        object.__setattr__(self, "ne04_contract_sha256", _sha256(self.ne04_contract_sha256))
        if (
            self.ne04_contract_path != self.profile_receipt.ne04_contract_path
            or self.ne04_contract_sha256 != self.profile_receipt.ne04_contract_sha256
            or self.ne04_contract_schema != self.profile_receipt.ne04_contract_schema
            or self.ne04_contract_schema != NE04_CONTRACT_SCHEMA
        ):
            _fail("W2B_RECEIPT_NE04_INVALID")
        candidate = _phase_tuple(self.candidate_phases, allow_empty=False)
        requested = _phase_tuple(self.requested_phases, allow_empty=False)
        excluded = _phase_tuple(self.excluded_phases, allow_empty=True)
        effective = _phase_tuple(self.effective_phases, allow_empty=False)
        candidate_set = set(candidate)
        requested_set = set(requested)
        excluded_set = set(excluded)
        if (
            not requested_set.issubset(candidate_set)
            or not excluded_set.issubset(candidate_set)
            or requested_set & excluded_set
            or requested_set | excluded_set != candidate_set
            or effective != tuple(sorted(requested_set - excluded_set))
        ):
            _fail("W2B_RECEIPT_PHASE_SET_INVALID")
        if self.profile_receipt.family == "fe" and (
            "C15_LAVES" not in candidate_set
            or "C15_LAVES" not in requested_set
            or "C15_LAVES" in excluded_set
            or "C15_LAVES" not in effective
        ):
            _fail("W2B_RECEIPT_FE_C15_DECISION_REQUIRED")
        bounds = _copy_canonical_payload(self.bounds, "W2B_RECEIPT_DOMAIN_INVALID")
        solver_options = _copy_canonical_payload(
            self.solver_options,
            "W2B_RECEIPT_DOMAIN_INVALID",
        )
        _payload_mapping(bounds, "W2B_RECEIPT_DOMAIN_INVALID")
        _payload_mapping(solver_options, "W2B_RECEIPT_DOMAIN_INVALID")
        object.__setattr__(self, "bounds", bounds)
        object.__setattr__(self, "solver_options", solver_options)
        if self.policy_generation != self.profile_receipt.policy_generation:
            _fail("W2B_RECEIPT_POLICY_INVALID")
        expected_authorization = (
            "INTERNAL_QUALIFICATION_ONLY_NOT_RELEASE"
            if mode == INTERNAL_QUALIFICATION
            else "RELEASE_AUTHORIZED"
        )
        if self.authorization_state != expected_authorization:
            _fail("W2B_RECEIPT_DOMAIN_INVALID")
        if mode == RELEASE and (
            not self.profile_receipt.release_enabled
            or not self.profile_receipt.ne04_calculations_enabled
            or not self.profile_receipt.policy_calculations_enabled
        ):
            _fail("W2B_RECEIPT_RELEASE_DENIED")
        _validate_full_request(feature, self.full_request, self.profile_receipt)
        object.__setattr__(self, "canonical_digest", canonical_payload_digest(self._payload()))

    def _payload(self) -> dict[str, object]:
        profile_payload = self.profile_receipt._payload()
        profile_payload["canonical_digest"] = self.profile_receipt.canonical_digest
        return {
            "schema_version": DOMAIN_RECEIPT_SCHEMA,
            "feature_id": self.feature_id,
            "full_request": self.full_request.value(),
            "full_request_sha256": self.full_request.sha256,
            "profile_receipt": profile_payload,
            "profile_receipt_digest": self.profile_receipt.canonical_digest,
            "ne04_contract": {
                "path": self.ne04_contract_path,
                "sha256": self.ne04_contract_sha256,
                "schema_version": self.ne04_contract_schema,
            },
            "phases": {
                "candidate": list(self.candidate_phases),
                "requested": list(self.requested_phases),
                "excluded": list(self.excluded_phases),
                "effective": list(self.effective_phases),
            },
            "bounds": self.bounds.value(),
            "bounds_sha256": self.bounds.sha256,
            "solver_options": self.solver_options.value(),
            "solver_options_sha256": self.solver_options.sha256,
            "execution_mode": self.execution_mode,
            "policy_generation": self.policy_generation,
            "authorization_state": self.authorization_state,
            "acceptance_claim": ACCEPTANCE_CLAIM,
            "counts_toward_feature_coverage": COUNTS_TOWARD_FEATURE_COVERAGE,
            "production_use": PRODUCTION_USE,
        }

    def as_dict(self) -> dict[str, object]:
        rebuilt = _rebuild_domain_receipt(self)
        payload = rebuilt._payload()
        payload["canonical_digest"] = rebuilt.canonical_digest
        return payload


def _copy_canonical_payload(value: object, reason: str) -> CanonicalPayload:
    try:
        if type(value) is not CanonicalPayload:
            _fail(reason)
        rebuilt = CanonicalPayload.from_bytes(value.canonical_json)
    except Exception:
        _fail(reason)
    if type(value.sha256) is not str or value.sha256 != rebuilt.sha256:
        _fail(reason)
    return rebuilt


def _rebuild_domain_receipt(value: object) -> DomainReceipt:
    """Reconstruct all nested domain primitives and rerun every invariant."""

    if type(value) is not DomainReceipt:
        _fail("W2B_RECEIPT_DOMAIN_INVALID")
    try:
        rebuilt = DomainReceipt(
            feature_id=value.feature_id,
            full_request=_copy_canonical_payload(
                value.full_request,
                "W2B_RECEIPT_DOMAIN_INVALID",
            ),
            profile_receipt=_rebuild_profile_receipt(value.profile_receipt),
            ne04_contract_path=value.ne04_contract_path,
            ne04_contract_sha256=value.ne04_contract_sha256,
            ne04_contract_schema=value.ne04_contract_schema,
            candidate_phases=value.candidate_phases,
            requested_phases=value.requested_phases,
            excluded_phases=value.excluded_phases,
            effective_phases=value.effective_phases,
            bounds=_copy_canonical_payload(value.bounds, "W2B_RECEIPT_DOMAIN_INVALID"),
            solver_options=_copy_canonical_payload(
                value.solver_options,
                "W2B_RECEIPT_DOMAIN_INVALID",
            ),
            execution_mode=value.execution_mode,
            policy_generation=value.policy_generation,
            authorization_state=value.authorization_state,
        )
    except ReceiptError:
        _fail("W2B_RECEIPT_DOMAIN_INVALID")
    except Exception:
        _fail("W2B_RECEIPT_DOMAIN_INVALID")
    if type(value.canonical_digest) is not str or value.canonical_digest != rebuilt.canonical_digest:
        _fail("W2B_RECEIPT_DOMAIN_INVALID")
    return rebuilt


def build_domain_receipt(
    project_root: str | Path,
    *,
    feature_id: object,
    full_request: object,
    profile_receipt: object,
    candidate_phases: object,
    requested_phases: object,
    excluded_phases: object,
    effective_phases: object,
    bounds: object,
    solver_options: object,
    execution_mode: object,
    policy_generation: object,
) -> DomainReceipt:
    """Build a domain receipt only after revalidating all pinned inputs."""

    profile_receipt = _rebuild_profile_receipt(profile_receipt)
    mode = _execution_mode(execution_mode)
    if profile_receipt.verification_mode != mode:
        _fail("W2B_RECEIPT_DOMAIN_INVALID")
    current, _observations, runtime_phases = _load_profile_impl(
        project_root,
        profile_receipt.family,
        profile_receipt.profile,
        mode,
    )
    if canonical_json_bytes(current._payload()) != canonical_json_bytes(profile_receipt._payload()):
        _fail("W2B_RECEIPT_MANIFEST_HASH_MISMATCH")
    candidate = _phase_tuple(candidate_phases, allow_empty=False)
    if not set(candidate).issubset(set(runtime_phases)):
        _fail("W2B_RECEIPT_PHASE_SET_INVALID")
    if type(policy_generation) is not str or policy_generation != current.policy_generation:
        _fail("W2B_RECEIPT_POLICY_INVALID")
    return DomainReceipt(
        feature_id=feature_id,  # type: ignore[arg-type]
        full_request=CanonicalPayload.from_value(full_request),
        profile_receipt=current,
        ne04_contract_path=current.ne04_contract_path,
        ne04_contract_sha256=current.ne04_contract_sha256,
        ne04_contract_schema=current.ne04_contract_schema,
        candidate_phases=candidate,
        requested_phases=requested_phases,  # type: ignore[arg-type]
        excluded_phases=excluded_phases,  # type: ignore[arg-type]
        effective_phases=effective_phases,  # type: ignore[arg-type]
        bounds=CanonicalPayload.from_value(bounds),
        solver_options=CanonicalPayload.from_value(solver_options),
        execution_mode=mode,
        policy_generation=policy_generation,
        authorization_state=(
            "INTERNAL_QUALIFICATION_ONLY_NOT_RELEASE"
            if mode == INTERNAL_QUALIFICATION
            else "RELEASE_AUTHORIZED"
        ),
    )


@dataclass(frozen=True, slots=True)
class ExecutionSnapshotFile:
    """One immutable, content-addressed file copied for backend execution."""

    role: str
    source_relative_path: str
    snapshot_relative_path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if type(self.role) is not str or self.role not in _OBSERVATION_ROLES:
            _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
        object.__setattr__(self, "source_relative_path", _safe_relative_path(self.source_relative_path))
        object.__setattr__(self, "snapshot_relative_path", _safe_relative_path(self.snapshot_relative_path))
        object.__setattr__(
            self,
            "sha256",
            _sha256(self.sha256, "W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID"),
        )
        if (
            type(self.size_bytes) is not int
            or isinstance(self.size_bytes, bool)
            or self.size_bytes < 0
            or self.size_bytes > _MAX_FILE_BYTES[self.role]
        ):
            _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")

    def as_dict(self) -> dict[str, object]:
        try:
            rebuilt = ExecutionSnapshotFile(
                role=self.role,
                source_relative_path=self.source_relative_path,
                snapshot_relative_path=self.snapshot_relative_path,
                sha256=self.sha256,
                size_bytes=self.size_bytes,
            )
        except Exception:
            _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
        return {
            "role": rebuilt.role,
            "source_path": rebuilt.source_relative_path,
            "snapshot_path": rebuilt.snapshot_relative_path,
            "sha256": rebuilt.sha256,
            "size_bytes": rebuilt.size_bytes,
        }


def _copy_observation(value: object, reason: str) -> FileHashObservation:
    try:
        if type(value) is not FileHashObservation:
            _fail(reason)
        return FileHashObservation(
            role=value.role,
            relative_path=value.relative_path,
            sha256=value.sha256,
            size_bytes=value.size_bytes,
            device=value.device,
            inode=value.inode,
            link_count=value.link_count,
            mtime_ns=value.mtime_ns,
            ctime_ns=value.ctime_ns,
        )
    except Exception:
        _fail(reason)
    raise AssertionError("unreachable")


def _copy_observations(value: object, reason: str) -> tuple[FileHashObservation, ...]:
    if type(value) is not tuple or len(value) != len(_OBSERVATION_ROLES):
        _fail(reason)
    copied = tuple(_copy_observation(item, reason) for item in value)
    if tuple(item.role for item in copied) != _OBSERVATION_ROLES:
        _fail(reason)
    return copied


@dataclass(frozen=True, slots=True)
class PreExecutionSnapshot:
    """PRE-only source observation bound to one active execution lease."""

    STAGE: ClassVar[str] = "PRE_EXECUTION"
    lease_id: str
    domain_receipt_digest: str
    profile_receipt_digest: str
    execution_snapshot_digest: str
    observations: tuple[FileHashObservation, ...]
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        reason = "W2B_RECEIPT_PRE_REHASH_MISMATCH"
        object.__setattr__(self, "lease_id", _sha256(self.lease_id, reason))
        object.__setattr__(self, "domain_receipt_digest", _sha256(self.domain_receipt_digest, reason))
        object.__setattr__(self, "profile_receipt_digest", _sha256(self.profile_receipt_digest, reason))
        object.__setattr__(
            self,
            "execution_snapshot_digest",
            _sha256(self.execution_snapshot_digest, reason),
        )
        object.__setattr__(self, "observations", _copy_observations(self.observations, reason))
        object.__setattr__(self, "canonical_digest", canonical_payload_digest(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": REHASH_SNAPSHOT_SCHEMA,
            "stage": "PRE_EXECUTION",
            "lease_id": self.lease_id,
            "domain_receipt_digest": self.domain_receipt_digest,
            "profile_receipt_digest": self.profile_receipt_digest,
            "execution_snapshot_digest": self.execution_snapshot_digest,
            "observations": [item.as_dict() for item in self.observations],
            "acceptance_claim": ACCEPTANCE_CLAIM,
            "counts_toward_feature_coverage": COUNTS_TOWARD_FEATURE_COVERAGE,
            "production_use": PRODUCTION_USE,
        }

    def as_dict(self) -> dict[str, object]:
        rebuilt = _rebuild_pre_snapshot(self)
        payload = rebuilt._payload()
        payload["canonical_digest"] = rebuilt.canonical_digest
        return payload


@dataclass(frozen=True, slots=True)
class PostExecutionSnapshot:
    """POST-only observation; its extra field prevents PRE object relabeling."""

    STAGE: ClassVar[str] = "POST_EXECUTION"
    lease_id: str
    domain_receipt_digest: str
    profile_receipt_digest: str
    execution_snapshot_digest: str
    pre_snapshot_digest: str
    observations: tuple[FileHashObservation, ...]
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        reason = "W2B_RECEIPT_POST_REHASH_MISMATCH"
        object.__setattr__(self, "lease_id", _sha256(self.lease_id, reason))
        object.__setattr__(self, "domain_receipt_digest", _sha256(self.domain_receipt_digest, reason))
        object.__setattr__(self, "profile_receipt_digest", _sha256(self.profile_receipt_digest, reason))
        object.__setattr__(
            self,
            "execution_snapshot_digest",
            _sha256(self.execution_snapshot_digest, reason),
        )
        object.__setattr__(self, "pre_snapshot_digest", _sha256(self.pre_snapshot_digest, reason))
        object.__setattr__(self, "observations", _copy_observations(self.observations, reason))
        object.__setattr__(self, "canonical_digest", canonical_payload_digest(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": REHASH_SNAPSHOT_SCHEMA,
            "stage": "POST_EXECUTION",
            "lease_id": self.lease_id,
            "domain_receipt_digest": self.domain_receipt_digest,
            "profile_receipt_digest": self.profile_receipt_digest,
            "execution_snapshot_digest": self.execution_snapshot_digest,
            "pre_snapshot_digest": self.pre_snapshot_digest,
            "observations": [item.as_dict() for item in self.observations],
            "acceptance_claim": ACCEPTANCE_CLAIM,
            "counts_toward_feature_coverage": COUNTS_TOWARD_FEATURE_COVERAGE,
            "production_use": PRODUCTION_USE,
        }

    def as_dict(self) -> dict[str, object]:
        rebuilt = _rebuild_post_snapshot(self)
        payload = rebuilt._payload()
        payload["canonical_digest"] = rebuilt.canonical_digest
        return payload


def _rebuild_pre_snapshot(value: object, reason: str = "W2B_RECEIPT_PRE_REHASH_MISMATCH") -> PreExecutionSnapshot:
    if type(value) is not PreExecutionSnapshot:
        _fail(reason)
    try:
        rebuilt = PreExecutionSnapshot(
            lease_id=value.lease_id,
            domain_receipt_digest=value.domain_receipt_digest,
            profile_receipt_digest=value.profile_receipt_digest,
            execution_snapshot_digest=value.execution_snapshot_digest,
            observations=_copy_observations(value.observations, reason),
        )
    except Exception:
        _fail(reason)
    if type(value.canonical_digest) is not str or value.canonical_digest != rebuilt.canonical_digest:
        _fail(reason)
    return rebuilt


def _rebuild_post_snapshot(value: object, reason: str = "W2B_RECEIPT_POST_REHASH_MISMATCH") -> PostExecutionSnapshot:
    if type(value) is not PostExecutionSnapshot:
        _fail(reason)
    try:
        rebuilt = PostExecutionSnapshot(
            lease_id=value.lease_id,
            domain_receipt_digest=value.domain_receipt_digest,
            profile_receipt_digest=value.profile_receipt_digest,
            execution_snapshot_digest=value.execution_snapshot_digest,
            pre_snapshot_digest=value.pre_snapshot_digest,
            observations=_copy_observations(value.observations, reason),
        )
    except Exception:
        _fail(reason)
    if type(value.canonical_digest) is not str or value.canonical_digest != rebuilt.canonical_digest:
        _fail(reason)
    return rebuilt


def _bound_file_specs(profile: DatabaseProfileReceipt) -> tuple[tuple[str, str, str, int | None], ...]:
    return (
        ("profile_manifest", profile.profile_manifest_path, profile.profile_manifest_sha256, None),
        ("release_policy", profile.release_policy_path, profile.release_policy_sha256, None),
        ("ne04_contract", profile.ne04_contract_path, profile.ne04_contract_sha256, None),
        *((item.role, item.relative_path, item.sha256, item.size_bytes) for item in profile.files),
    )


def _collect_bound_files(
    root: Path,
    profile: DatabaseProfileReceipt,
) -> tuple[tuple[FileHashObservation, ...], dict[str, bytes]]:
    observations: list[FileHashObservation] = []
    payloads: dict[str, bytes] = {}
    for role, path, digest, size in _bound_file_specs(profile):
        payload, observation = _read_stable_file(
            root,
            role,
            path,
            expected_sha256=digest,
            expected_size=size,
        )
        observations.append(observation)
        payloads[role] = payload
    result = tuple(observations)
    if tuple(item.role for item in result) != _OBSERVATION_ROLES:
        _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
    return result, payloads


def _same_profile(left: DatabaseProfileReceipt, right: DatabaseProfileReceipt) -> bool:
    return canonical_json_bytes(left._payload()) == canonical_json_bytes(right._payload())


def _same_domain(left: DomainReceipt, right: DomainReceipt) -> bool:
    return canonical_json_bytes(left._payload()) == canonical_json_bytes(right._payload())


def _reload_domain_profile(root: Path, domain: DomainReceipt, reason: str) -> DatabaseProfileReceipt:
    try:
        current, _observations, phases = _load_profile_impl(
            root,
            domain.profile_receipt.family,
            domain.profile_receipt.profile,
            domain.execution_mode,
        )
    except ReceiptError:
        _fail(reason)
    if (
        not _same_profile(current, domain.profile_receipt)
        or not set(domain.candidate_phases).issubset(set(phases))
        or current.ne04_contract_sha256 != domain.ne04_contract_sha256
        or current.policy_generation != domain.policy_generation
    ):
        _fail(reason)
    return current


def _snapshot_relative_path(role: str, source_path: str, digest: str) -> str:
    basename = PurePosixPath(source_path).name
    return _safe_relative_path(f"{role}/{digest}-{basename}")


def _hold_deny_write(path: Path) -> tuple[str, object]:
    if os.name != "nt":
        try:
            return ("python", path.open("rb"))
        except OSError as error:
            raise ReceiptError("W2B_RECEIPT_EXECUTION_SNAPSHOT_LOCK_FAILED") from error
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = (
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        )
        create_file.restype = ctypes.c_void_p
        handle = create_file(
            str(path),
            0x80000000,
            0x00000001,
            None,
            3,
            0x00000080,
            None,
        )
        invalid = ctypes.c_void_p(-1).value
        if handle in (None, invalid):
            _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_LOCK_FAILED")
        return ("windows", int(handle))
    except ReceiptError:
        raise
    except Exception as error:
        raise ReceiptError("W2B_RECEIPT_EXECUTION_SNAPSHOT_LOCK_FAILED") from error


def _close_held_handle(held: tuple[str, object]) -> None:
    kind, handle = held
    try:
        if kind == "python":
            handle.close()  # type: ignore[union-attr]
        else:
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
            kernel32.CloseHandle.restype = ctypes.c_int
            kernel32.CloseHandle(ctypes.c_void_p(handle))
    except Exception:
        pass


def _held_handle_is_open(held: object) -> bool:
    if type(held) is not tuple or len(held) != 2:
        return False
    kind, handle = held
    if kind == "python":
        return not bool(getattr(handle, "closed", True))
    if kind != "windows" or type(handle) is not int or isinstance(handle, bool):
        return False
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.SetLastError(0)
        kernel32.GetFileType.argtypes = (ctypes.c_void_p,)
        kernel32.GetFileType.restype = ctypes.c_uint32
        file_type = int(kernel32.GetFileType(ctypes.c_void_p(handle)))
        return file_type == 0x0001
    except Exception:
        return False


def _write_snapshot_marker(snapshot_root: Path, lease_id: str) -> None:
    marker = snapshot_root / _LEASE_MARKER_NAME
    try:
        with marker.open("xb") as handle:
            handle.write((lease_id + "\n").encode("ascii"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(marker, stat.S_IREAD)
    except OSError as error:
        raise ReceiptError("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID") from error


def _validate_snapshot_marker(snapshot_root: Path, lease_id: str) -> None:
    marker = snapshot_root / _LEASE_MARKER_NAME
    try:
        before = marker.lstat()
        with marker.open("rb") as handle:
            handle_info = os.fstat(handle.fileno())
            payload = handle.read(66)
            after = os.fstat(handle.fileno())
        final = marker.lstat()
    except OSError as error:
        raise ReceiptError("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID") from error
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or _is_reparse(before)
        or int(before.st_nlink) != 1
        or _stat_signature(before) != _stat_signature(handle_info)
        or _stat_signature(handle_info) != _stat_signature(after)
        or _stat_signature(after) != _stat_signature(final)
        or payload != (lease_id + "\n").encode("ascii")
    ):
        _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")


def _remove_snapshot_tree(
    snapshot_root: Path | None,
    project_root: Path,
    lease_id: str,
) -> None:
    if snapshot_root is None:
        return
    try:
        resolved = snapshot_root.resolve(strict=True)
        temp_parent = Path(tempfile.gettempdir()).resolve(strict=True)
        if (
            resolved.parent != temp_parent
            or not resolved.name.startswith("thermogar_wave2b_lease_")
        ):
            _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
        try:
            resolved.relative_to(project_root)
            _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
        except ValueError:
            pass
        _validate_snapshot_marker(resolved, lease_id)
        pending = [resolved]
        while pending:
            directory = pending.pop()
            for child in directory.iterdir():
                child_info = child.lstat()
                if stat.S_ISLNK(child_info.st_mode) or _is_reparse(child_info):
                    _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
                if stat.S_ISREG(child_info.st_mode):
                    os.chmod(child, stat.S_IREAD | stat.S_IWRITE)
                elif stat.S_ISDIR(child_info.st_mode):
                    pending.append(child)
                else:
                    _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
        shutil.rmtree(resolved)
    except FileNotFoundError:
        return
    except ReceiptError:
        raise
    except OSError as error:
        raise ReceiptError("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID") from error


_ACTIVE_EXECUTION_LEASES: dict[str, "ExecutionLease"] = {}


class ExecutionLease:
    """Active context exposing only locked, content-addressed backend inputs."""

    __slots__ = (
        "_project_root",
        "_domain",
        "_lease_id",
        "_active",
        "_entered",
        "_snapshot_root",
        "_snapshot_files",
        "_snapshot_digest",
        "_source_observations",
        "_held_handles",
        "_pre_bytes",
        "_post_bytes",
        "_result_built",
    )

    def __init__(self, project_root: str | Path, domain_receipt: object):
        self._project_root = _project_root(project_root)
        self._domain = _rebuild_domain_receipt(domain_receipt)
        self._lease_id = secrets.token_hex(32)
        self._active = False
        self._entered = False
        self._snapshot_root: Path | None = None
        self._snapshot_files: tuple[ExecutionSnapshotFile, ...] = ()
        self._snapshot_digest = ""
        self._source_observations: tuple[FileHashObservation, ...] = ()
        self._held_handles: list[tuple[str, object]] = []
        self._pre_bytes: bytes | None = None
        self._post_bytes: bytes | None = None
        self._result_built = False

    @property
    def lease_id(self) -> str:
        return self._lease_id

    @property
    def execution_snapshot_digest(self) -> str:
        if not self._active or _ACTIVE_EXECUTION_LEASES.get(self._lease_id) is not self:
            _fail("W2B_RECEIPT_LEASE_STATE_INVALID")
        self._verify_snapshot()
        return self._snapshot_digest

    def __enter__(self) -> "ExecutionLease":
        if self._entered or self._active:
            _fail("W2B_RECEIPT_LEASE_STATE_INVALID")
        try:
            self._domain = _rebuild_domain_receipt(self._domain)
            self._lease_id = _sha256(self._lease_id, "W2B_RECEIPT_LEASE_STATE_INVALID")
        except Exception:
            _fail("W2B_RECEIPT_LEASE_STATE_INVALID")
        self._entered = True
        _reload_domain_profile(
            self._project_root,
            self._domain,
            "W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID",
        )
        observations, payloads = _collect_bound_files(
            self._project_root,
            self._domain.profile_receipt,
        )
        snapshot_root: Path | None = None
        try:
            snapshot_root = Path(
                tempfile.mkdtemp(prefix="thermogar_wave2b_lease_")
            ).resolve(strict=True)
            _write_snapshot_marker(snapshot_root, self._lease_id)
            try:
                snapshot_root.relative_to(self._project_root)
                _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
            except ValueError:
                pass
            files: list[ExecutionSnapshotFile] = []
            handles: list[tuple[str, object]] = []
            for observation in observations:
                relative = _snapshot_relative_path(
                    observation.role,
                    observation.relative_path,
                    observation.sha256,
                )
                target = snapshot_root.joinpath(*PurePosixPath(relative).parts)
                target.parent.mkdir(parents=True, exist_ok=False)
                with target.open("xb") as output:
                    output.write(payloads[observation.role])
                    output.flush()
                    os.fsync(output.fileno())
                os.chmod(target, stat.S_IREAD)
                _payload, verified = _read_stable_file(
                    snapshot_root,
                    observation.role,
                    relative,
                    expected_sha256=observation.sha256,
                    expected_size=observation.size_bytes,
                )
                file_identity = ExecutionSnapshotFile(
                    role=observation.role,
                    source_relative_path=observation.relative_path,
                    snapshot_relative_path=relative,
                    sha256=verified.sha256,
                    size_bytes=verified.size_bytes,
                )
                handles.append(_hold_deny_write(target))
                files.append(file_identity)
            snapshot_files = tuple(files)
            snapshot_digest = canonical_payload_digest(
                {
                    "schema_version": EXECUTION_LEASE_SCHEMA,
                    "files": [item.as_dict() for item in snapshot_files],
                }
            )
            self._snapshot_root = snapshot_root
            self._snapshot_files = snapshot_files
            self._snapshot_digest = snapshot_digest
            self._source_observations = observations
            self._held_handles = handles
            self._active = True
            if self._lease_id in _ACTIVE_EXECUTION_LEASES:
                _fail("W2B_RECEIPT_LEASE_STATE_INVALID")
            _ACTIVE_EXECUTION_LEASES[self._lease_id] = self
            self._verify_snapshot()
            return self
        except Exception as error:
            _ACTIVE_EXECUTION_LEASES.pop(self._lease_id, None)
            for handle in locals().get("handles", []):
                _close_held_handle(handle)
            try:
                _remove_snapshot_tree(snapshot_root, self._project_root, self._lease_id)
            except ReceiptError:
                pass
            self._active = False
            if isinstance(error, ReceiptError):
                raise
            raise ReceiptError("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID") from error

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        cleanup_error: ReceiptError | None = None
        registered_ids = tuple(
            key for key, value in _ACTIVE_EXECUTION_LEASES.items() if value is self
        )
        cleanup_id = registered_ids[0] if len(registered_ids) == 1 else self._lease_id
        for key in registered_ids:
            _ACTIVE_EXECUTION_LEASES.pop(key, None)
        self._active = False
        for handle in self._held_handles:
            _close_held_handle(handle)
        self._held_handles.clear()
        try:
            _remove_snapshot_tree(self._snapshot_root, self._project_root, cleanup_id)
        except ReceiptError as error:
            cleanup_error = error
        self._snapshot_root = None
        if cleanup_error is not None and exc_type is None:
            raise cleanup_error
        return False

    def _verify_snapshot(self) -> None:
        if (
            not self._active
            or self._snapshot_root is None
            or type(self._snapshot_files) is not tuple
            or len(self._snapshot_files) != len(_OBSERVATION_ROLES)
            or len(self._held_handles) != len(_OBSERVATION_ROLES)
        ):
            _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
        try:
            if _project_root(self._snapshot_root) != self._snapshot_root:
                _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
        except ReceiptError:
            _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
        _validate_snapshot_marker(self._snapshot_root, self._lease_id)
        rebuilt_files: list[ExecutionSnapshotFile] = []
        for item in self._snapshot_files:
            if type(item) is not ExecutionSnapshotFile:
                _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
            snapshot_path = self._snapshot_root.joinpath(
                *PurePosixPath(item.snapshot_relative_path).parts
            )
            try:
                snapshot_info = snapshot_path.lstat()
            except OSError as error:
                raise ReceiptError("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID") from error
            if snapshot_info.st_mode & stat.S_IWRITE:
                _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
            _payload, observation = _read_stable_file(
                self._snapshot_root,
                item.role,
                item.snapshot_relative_path,
                expected_sha256=item.sha256,
                expected_size=item.size_bytes,
            )
            rebuilt_files.append(
                ExecutionSnapshotFile(
                    role=item.role,
                    source_relative_path=item.source_relative_path,
                    snapshot_relative_path=item.snapshot_relative_path,
                    sha256=observation.sha256,
                    size_bytes=observation.size_bytes,
                )
            )
        if any(not _held_handle_is_open(item) for item in self._held_handles):
            _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_LOCK_FAILED")
        if tuple(item.role for item in rebuilt_files) != _OBSERVATION_ROLES:
            _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
        digest = canonical_payload_digest(
            {
                "schema_version": EXECUTION_LEASE_SCHEMA,
                "files": [item.as_dict() for item in rebuilt_files],
            }
        )
        if digest != self._snapshot_digest:
            _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")

    def file_path(self, role: object) -> Path:
        """Return one locked snapshot path; project paths are never exposed."""

        if (
            not self._active
            or _ACTIVE_EXECUTION_LEASES.get(self._lease_id) is not self
            or self._pre_bytes is None
            or self._post_bytes is not None
            or type(role) is not str
        ):
            _fail("W2B_RECEIPT_LEASE_STATE_INVALID")
        self._verify_snapshot()
        matches = [item for item in self._snapshot_files if item.role == role]
        if len(matches) != 1 or self._snapshot_root is None:
            _fail("W2B_RECEIPT_EXECUTION_SNAPSHOT_INVALID")
        return self._snapshot_root.joinpath(*PurePosixPath(matches[0].snapshot_relative_path).parts)


def open_execution_lease(
    project_root: str | Path,
    domain_receipt: object,
) -> ExecutionLease:
    """Create a single-use lease; it becomes authoritative only inside ``with``."""

    return ExecutionLease(project_root, domain_receipt)


def _require_active_lease(
    project_root: str | Path,
    domain_receipt: object,
    execution_lease: object,
    reason: str,
) -> tuple[Path, DomainReceipt, ExecutionLease]:
    try:
        root = _project_root(project_root)
        domain = _rebuild_domain_receipt(domain_receipt)
        if type(execution_lease) is not ExecutionLease:
            _fail(reason)
        lease_domain = _rebuild_domain_receipt(execution_lease._domain)
        lease_id = _sha256(execution_lease._lease_id, reason)
        snapshot_digest = _sha256(execution_lease._snapshot_digest, reason)
        source_observations = _copy_observations(execution_lease._source_observations, reason)
    except Exception:
        _fail(reason)
    if (
        not execution_lease._active
        or _ACTIVE_EXECUTION_LEASES.get(lease_id) is not execution_lease
        or root != execution_lease._project_root
        or not _same_domain(domain, lease_domain)
        or snapshot_digest != execution_lease._snapshot_digest
        or source_observations != execution_lease._source_observations
    ):
        _fail(reason)
    execution_lease._verify_snapshot()
    return root, domain, execution_lease


def pre_execution_rehash(
    project_root: str | Path,
    domain_receipt: object,
    execution_lease: object,
) -> PreExecutionSnapshot:
    """Issue PRE only for the matching active immutable execution snapshot."""

    reason = "W2B_RECEIPT_PRE_REHASH_MISMATCH"
    root, domain, lease = _require_active_lease(
        project_root,
        domain_receipt,
        execution_lease,
        reason,
    )
    if lease._pre_bytes is not None or lease._post_bytes is not None:
        _fail(reason)
    _reload_domain_profile(root, domain, reason)
    observations, _payloads = _collect_bound_files(root, domain.profile_receipt)
    if observations != lease._source_observations:
        _fail(reason)
    snapshot = PreExecutionSnapshot(
        lease_id=lease._lease_id,
        domain_receipt_digest=domain.canonical_digest,
        profile_receipt_digest=domain.profile_receipt.canonical_digest,
        execution_snapshot_digest=lease._snapshot_digest,
        observations=observations,
    )
    lease._pre_bytes = canonical_json_bytes(snapshot.as_dict())
    return snapshot


def post_execution_rehash(
    project_root: str | Path,
    domain_receipt: object,
    pre_snapshot: object,
    execution_lease: object,
) -> PostExecutionSnapshot:
    """Issue POST only from this lease's exact PRE while the lease is active."""

    reason = "W2B_RECEIPT_POST_REHASH_MISMATCH"
    root, domain, lease = _require_active_lease(
        project_root,
        domain_receipt,
        execution_lease,
        reason,
    )
    pre = _rebuild_pre_snapshot(pre_snapshot, reason)
    if (
        lease._pre_bytes is None
        or lease._post_bytes is not None
        or canonical_json_bytes(pre.as_dict()) != lease._pre_bytes
        or pre.lease_id != lease._lease_id
        or pre.domain_receipt_digest != domain.canonical_digest
        or pre.profile_receipt_digest != domain.profile_receipt.canonical_digest
        or pre.execution_snapshot_digest != lease._snapshot_digest
    ):
        _fail(reason)
    _reload_domain_profile(root, domain, reason)
    observations, _payloads = _collect_bound_files(root, domain.profile_receipt)
    if observations != pre.observations or observations != lease._source_observations:
        _fail(reason)
    lease._verify_snapshot()
    snapshot = PostExecutionSnapshot(
        lease_id=lease._lease_id,
        domain_receipt_digest=domain.canonical_digest,
        profile_receipt_digest=domain.profile_receipt.canonical_digest,
        execution_snapshot_digest=lease._snapshot_digest,
        pre_snapshot_digest=pre.canonical_digest,
        observations=observations,
    )
    lease._post_bytes = canonical_json_bytes(snapshot.as_dict())
    return snapshot


def _validate_failure_payload(payload: CanonicalPayload) -> int:
    failures = payload.value()
    if type(failures) is not list:
        _fail("W2B_RECEIPT_FAILURE_LEDGER_INVALID")
    for expected_ordinal, item in enumerate(failures):
        if type(item) is not dict or set(item) != {"ordinal", "node_id", "reason_code", "context"}:
            _fail("W2B_RECEIPT_FAILURE_LEDGER_INVALID")
        if item["ordinal"] != expected_ordinal:
            _fail("W2B_RECEIPT_FAILURE_LEDGER_INVALID")
        if (
            type(item["node_id"]) is not str
            or not item["node_id"]
            or len(item["node_id"]) > 256
            or unicodedata.normalize("NFC", item["node_id"]) != item["node_id"]
        ):
            _fail("W2B_RECEIPT_FAILURE_LEDGER_INVALID")
        _strict_string(
            item["reason_code"],
            _REASON_TOKEN,
            "W2B_RECEIPT_FAILURE_LEDGER_INVALID",
        )
        if type(item["context"]) is not dict:
            _fail("W2B_RECEIPT_FAILURE_LEDGER_INVALID")
    return len(failures)


def _strict_primitive_equal(left: object, right: object) -> bool:
    """Compare only exact canonical primitives without polymorphic equality."""

    if type(left) is not type(right):
        return False
    if left is None:
        return True
    if type(left) in (bool, int, str):
        return left == right
    if type(left) is list:
        if len(left) != len(right):  # type: ignore[arg-type]
            return False
        return all(
            _strict_primitive_equal(item, right[index])  # type: ignore[index]
            for index, item in enumerate(left)
        )
    if type(left) is dict:
        if len(left) != len(right):  # type: ignore[arg-type]
            return False
        for key, item in left.items():
            if type(key) is not str or key not in right:  # type: ignore[operator]
                return False
            if not _strict_primitive_equal(item, right[key]):  # type: ignore[index]
                return False
        return True
    return False


def _validate_denial_fields(payload: dict[str, Any]) -> None:
    if (
        type(payload.get("acceptance_claim")) is not bool
        or payload.get("acceptance_claim") is not False
        or type(payload.get("counts_toward_feature_coverage")) is not bool
        or payload.get("counts_toward_feature_coverage") is not False
        or type(payload.get("production_use")) is not str
        or payload.get("production_use") != PRODUCTION_USE
    ):
        _fail("W2B_RECEIPT_DENIAL_BINDING_INVALID")


def _result_route(feature_id: str) -> str:
    if feature_id in DIRECT_RESULT_FEATURES:
        return "direct"
    if feature_id in MAPPING_RESULT_FEATURES:
        return "mapping"
    if feature_id in SOLIDIFICATION_RESULT_FEATURES:
        return "solidification"
    _fail("W2B_RECEIPT_BACKEND_BINDING_INVALID")


def _validate_backend_payload(
    feature_id: str,
    family: str,
    backend: dict[str, Any],
) -> None:
    route = _result_route(feature_id)
    _validate_denial_fields(backend)
    if route == "direct":
        version = backend.get("pycalphad_version")
        if type(version) is not str or version not in ("NOT_LOADED", "0.11.2"):
            _fail("W2B_RECEIPT_BACKEND_BINDING_INVALID")
        expected: object = {
            "schema_version": _DIRECT_BACKEND_SCHEMA,
            "backend_id": _DIRECT_BACKEND_ID,
            "pycalphad_version": version,
            "implemented_operations": [
                "solve_equilibrium",
                "phase_gibbs_energy",
                "phase_driving_force",
                "tzero_temperature",
            ],
            "unsupported_path_operations": ["map", "simulate"],
            "acceptance_claim": False,
            "counts_toward_feature_coverage": False,
            "production_use": PRODUCTION_USE,
        }
    elif route == "mapping":
        version = backend.get("pycalphad_version")
        if type(version) is not str or version not in ("NOT_LOADED", "0.11.2"):
            _fail("W2B_RECEIPT_BACKEND_BINDING_INVALID")
        expected = _canonicalize(
            {
                "schema_version": _MAPPING_BACKEND_SCHEMA,
                "backend_id": _MAPPING_BACKEND_ID,
                "pycalphad_version": version,
                "supported_mapping_features": list(MAPPING_RESULT_FEATURES),
                "complete_diagnostics_required": True,
                "stock_pycalphad_0_11_2_complete_diagnostics": False,
                "native_v2_partial_observations_supported": True,
                "native_v2_complete_diagnostics_supported": False,
                "native_v2_hidden_attempts_available": False,
                "native_v2_isopleth_derived_invariants_supported": False,
                "native_v2_projection_policy": "EXACT_OR_FAIL_CLOSED",
                "native_v2_postrun_membership_policy": _MAPPING_MEMBERSHIP_POLICY,
                "native_v2_isopleth_fixed_composition_abs_tolerance": 1.0e-9,
                "native_v2_mole_fraction_abs_tolerance_by_feature": {
                    name: 1.0e-9 for name in MAPPING_RESULT_FEATURES
                },
                "path_contract_v2_sha256": _PATH_CONTRACT_V2_SHA256,
                "v2_partial_reason_code": _MAPPING_PARTIAL_REASON,
                "acceptance_claim": False,
                "counts_toward_feature_coverage": False,
                "production_use": PRODUCTION_USE,
            }
        )
    else:
        runtime_identity = (
            backend.get("pycalphad_version"),
            backend.get("scheil_version"),
            backend.get("diagnostic_kind"),
            backend.get("solver_provenance"),
        )
        if runtime_identity not in (
            ("NOT_LOADED", "NOT_LOADED", "NOT_LOADED", "NOT_LOADED"),
            ("0.11.2", "0.3.0", "NATIVE_SUCCESS_ARRAYS_ONLY", "NATIVE_RUNTIME"),
        ):
            _fail("W2B_RECEIPT_BACKEND_BINDING_INVALID")
        legacy_identity = (
            "DTO_V2_REQUIRED_EXACT_RECEIPT_ROLE_UNREPRESENTABLE"
            if family in ("ni", "al")
            else "EXACT_RECEIPT_ROLE_BOUND"
        )
        expected = {
            "schema_version": _SOLIDIFICATION_BACKEND_SCHEMA,
            "backend_id": _SOLIDIFICATION_BACKEND_ID,
            "pycalphad_version": runtime_identity[0],
            "scheil_version": runtime_identity[1],
            "diagnostic_kind": runtime_identity[2],
            "solver_provenance": runtime_identity[3],
            "required_contract_schema": "THERMOGAR-WAVE2B-PATH-CONTRACT-V2-2",
            "required_contract_version": "2.1",
            "required_contract_sha256": _PATH_CONTRACT_V2_SHA256,
            "path_contract_v2_sha256": _PATH_CONTRACT_V2_SHA256,
            "contract_v2_required": True,
            "legacy_complete_output_enabled": False,
            "native_v2_partial_observations_supported": True,
            "native_v2_complete_diagnostics_supported": False,
            "native_v2_hidden_attempts_available": False,
            "native_v2_result_status": _SOLIDIFICATION_PARTIAL_STATUS,
            "native_v2_diagnostic_reason": _SOLIDIFICATION_PARTIAL_REASON,
            "v2_partial_terminal_reason": _SOLIDIFICATION_PARTIAL_STATUS,
            "v2_partial_reason_code": _SOLIDIFICATION_PARTIAL_REASON,
            "legacy_identity_contract": legacy_identity,
            "identity_contract": legacy_identity,
            "v2_identity_contract": "EXACT_RECEIPT_ROLE_BOUND",
            "bound_operations": list(SOLIDIFICATION_RESULT_FEATURES),
            "native_complete_operations": [],
            "acceptance_claim": False,
            "counts_toward_feature_coverage": False,
            "production_use": PRODUCTION_USE,
        }
    if not _strict_primitive_equal(backend, expected):
        _fail("W2B_RECEIPT_BACKEND_BINDING_INVALID")


def _validate_runtime_payload(
    domain: DomainReceipt,
    execution_snapshot_digest: str,
    runtime: dict[str, Any],
) -> None:
    profile = domain.profile_receipt
    expected: dict[str, object] = {
        "database_family": profile.family,
        "profile_id": profile.profile,
        "runtime_sha256": profile.runtime.sha256,
        "profile_receipt_digest": profile.canonical_digest,
        "domain_receipt_digest": domain.canonical_digest,
        "execution_snapshot_digest": execution_snapshot_digest,
        "database_source_role": "runtime",
        "database_path_kind": "ACTIVE_EXECUTION_LEASE_SNAPSHOT_ONLY",
    }
    if _result_route(domain.feature_id) == "mapping":
        database_key = (profile.family, profile.profile)
        if database_key not in _V2_DATABASE_ID:
            _fail("W2B_RECEIPT_RUNTIME_BINDING_INVALID")
        expected["v2_database_id"] = _V2_DATABASE_ID[database_key]
    if not _strict_primitive_equal(runtime, expected):
        _fail("W2B_RECEIPT_RUNTIME_BINDING_INVALID")


def _exact_result_counter(value: object) -> int:
    if type(value) is not int or value < 0 or value >= 2**63:
        _fail("W2B_RECEIPT_CONTEXT_BINDING_INVALID")
    return value


def _validate_context_payload(
    domain: DomainReceipt,
    execution_lease_id: str,
    pre_snapshot_digest: str,
    context: dict[str, Any],
) -> None:
    route = _result_route(domain.feature_id)
    _validate_denial_fields(context)
    expected: dict[str, object] = {
        "feature_id": domain.feature_id,
        "execution_mode": domain.execution_mode,
        "authorization_state": domain.authorization_state,
        "execution_lease_id": execution_lease_id,
        "pre_snapshot_digest": pre_snapshot_digest,
        "steel_required_product_scope": True,
        "fe_baseline_profile": None,
        "fe_exclusion_decision_made": False,
        "acceptance_claim": False,
        "counts_toward_feature_coverage": False,
        "production_use": PRODUCTION_USE,
    }
    if route in ("direct", "solidification"):
        expected.update(
            {
                "attempted_calls": _exact_result_counter(context.get("attempted_calls")),
                "completed_calls": _exact_result_counter(context.get("completed_calls")),
                "failed_calls": _exact_result_counter(context.get("failed_calls")),
            }
        )
    else:
        last_state = context.get("last_diagnostic_state")
        if (
            type(last_state) is not str
            or last_state not in _MAPPING_DIAGNOSTIC_STATES
        ):
            _fail("W2B_RECEIPT_CONTEXT_BINDING_INVALID")
        expected.update(
            {
                "attempted_maps": _exact_result_counter(context.get("attempted_maps")),
                "completed_maps": _exact_result_counter(context.get("completed_maps")),
                "failed_maps": _exact_result_counter(context.get("failed_maps")),
                "last_diagnostic_state": last_state,
                "v2_partial_terminal_reasons": list(_MAPPING_PARTIAL_TERMINALS),
                "v2_partial_reason_code": _MAPPING_PARTIAL_REASON,
            }
        )
    if not _strict_primitive_equal(context, expected):
        _fail("W2B_RECEIPT_CONTEXT_BINDING_INVALID")


@dataclass(frozen=True, slots=True)
class ResultReceipt:
    """Result provenance bound to domain, profile, runtime, and failures."""

    domain_receipt: DomainReceipt
    profile_receipt_digest: str
    post_rehash_digest: str
    execution_lease_id: str
    execution_snapshot_digest: str
    pre_snapshot_digest: str
    backend: CanonicalPayload
    runtime: CanonicalPayload
    failures: CanonicalPayload
    output_sha256: str
    output_size_bytes: int
    context: CanonicalPayload
    failure_count: int = field(init=False)
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        try:
            domain = _rebuild_domain_receipt(self.domain_receipt)
        except ReceiptError:
            _fail("W2B_RECEIPT_RESULT_INVALID")
        object.__setattr__(self, "domain_receipt", domain)
        object.__setattr__(
            self,
            "profile_receipt_digest",
            _sha256(self.profile_receipt_digest, "W2B_RECEIPT_RESULT_INVALID"),
        )
        object.__setattr__(
            self,
            "post_rehash_digest",
            _sha256(self.post_rehash_digest, "W2B_RECEIPT_RESULT_INVALID"),
        )
        object.__setattr__(
            self,
            "execution_lease_id",
            _sha256(self.execution_lease_id, "W2B_RECEIPT_RESULT_INVALID"),
        )
        object.__setattr__(
            self,
            "execution_snapshot_digest",
            _sha256(self.execution_snapshot_digest, "W2B_RECEIPT_RESULT_INVALID"),
        )
        object.__setattr__(
            self,
            "pre_snapshot_digest",
            _sha256(self.pre_snapshot_digest, "W2B_RECEIPT_RESULT_INVALID"),
        )
        if self.profile_receipt_digest != self.domain_receipt.profile_receipt.canonical_digest:
            _fail("W2B_RECEIPT_RESULT_INVALID")
        backend = _copy_canonical_payload(self.backend, "W2B_RECEIPT_RESULT_INVALID")
        runtime = _copy_canonical_payload(self.runtime, "W2B_RECEIPT_RESULT_INVALID")
        failures = _copy_canonical_payload(self.failures, "W2B_RECEIPT_RESULT_INVALID")
        context = _copy_canonical_payload(self.context, "W2B_RECEIPT_RESULT_INVALID")
        backend_mapping = _payload_mapping(backend, "W2B_RECEIPT_RESULT_INVALID")
        runtime_mapping = _payload_mapping(runtime, "W2B_RECEIPT_RESULT_INVALID")
        context_mapping = _payload_mapping(context, "W2B_RECEIPT_RESULT_INVALID")
        _validate_backend_payload(
            self.domain_receipt.feature_id,
            self.domain_receipt.profile_receipt.family,
            backend_mapping,
        )
        _validate_runtime_payload(
            self.domain_receipt,
            self.execution_snapshot_digest,
            runtime_mapping,
        )
        _validate_context_payload(
            self.domain_receipt,
            self.execution_lease_id,
            self.pre_snapshot_digest,
            context_mapping,
        )
        count = _validate_failure_payload(failures)
        object.__setattr__(self, "backend", backend)
        object.__setattr__(self, "runtime", runtime)
        object.__setattr__(self, "failures", failures)
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "failure_count", count)
        object.__setattr__(
            self,
            "output_sha256",
            _sha256(self.output_sha256, "W2B_RECEIPT_OUTPUT_DIGEST_INVALID"),
        )
        if (
            type(self.output_size_bytes) is not int
            or isinstance(self.output_size_bytes, bool)
            or self.output_size_bytes < 0
            or self.output_size_bytes >= 2**63
        ):
            _fail("W2B_RECEIPT_OUTPUT_DIGEST_INVALID")
        object.__setattr__(self, "canonical_digest", canonical_payload_digest(self._payload()))

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": RESULT_RECEIPT_SCHEMA,
            "domain_receipt_digest": self.domain_receipt.canonical_digest,
            "profile_receipt_digest": self.profile_receipt_digest,
            "post_rehash_digest": self.post_rehash_digest,
            "execution_lease_id": self.execution_lease_id,
            "execution_snapshot_digest": self.execution_snapshot_digest,
            "pre_snapshot_digest": self.pre_snapshot_digest,
            "backend": self.backend.value(),
            "backend_sha256": self.backend.sha256,
            "runtime": self.runtime.value(),
            "runtime_sha256": self.runtime.sha256,
            "failures": self.failures.value(),
            "failures_sha256": self.failures.sha256,
            "failure_count": self.failure_count,
            "output": {
                "sha256": self.output_sha256,
                "size_bytes": self.output_size_bytes,
            },
            "context": self.context.value(),
            "context_sha256": self.context.sha256,
            "execution_mode": self.domain_receipt.execution_mode,
            "authorization_state": self.domain_receipt.authorization_state,
            "acceptance_claim": ACCEPTANCE_CLAIM,
            "counts_toward_feature_coverage": COUNTS_TOWARD_FEATURE_COVERAGE,
            "production_use": PRODUCTION_USE,
        }

    def as_dict(self) -> dict[str, object]:
        rebuilt = _rebuild_result_receipt(self)
        payload = rebuilt._payload()
        payload["canonical_digest"] = rebuilt.canonical_digest
        return payload


def _rebuild_result_receipt(value: object) -> ResultReceipt:
    """Reconstruct all result primitives; the stored digest is never authority."""

    if type(value) is not ResultReceipt:
        _fail("W2B_RECEIPT_RESULT_INVALID")
    try:
        rebuilt = ResultReceipt(
            domain_receipt=_rebuild_domain_receipt(value.domain_receipt),
            profile_receipt_digest=value.profile_receipt_digest,
            post_rehash_digest=value.post_rehash_digest,
            execution_lease_id=value.execution_lease_id,
            execution_snapshot_digest=value.execution_snapshot_digest,
            pre_snapshot_digest=value.pre_snapshot_digest,
            backend=_copy_canonical_payload(value.backend, "W2B_RECEIPT_RESULT_INVALID"),
            runtime=_copy_canonical_payload(value.runtime, "W2B_RECEIPT_RESULT_INVALID"),
            failures=_copy_canonical_payload(value.failures, "W2B_RECEIPT_RESULT_INVALID"),
            output_sha256=value.output_sha256,
            output_size_bytes=value.output_size_bytes,
            context=_copy_canonical_payload(value.context, "W2B_RECEIPT_RESULT_INVALID"),
        )
    except Exception:
        _fail("W2B_RECEIPT_RESULT_INVALID")
    if type(value.canonical_digest) is not str or value.canonical_digest != rebuilt.canonical_digest:
        _fail("W2B_RECEIPT_RESULT_INVALID")
    return rebuilt


def build_result_receipt(
    *,
    domain_receipt: object,
    post_snapshot: object,
    execution_lease: object,
    backend: object,
    runtime: object,
    failures: object,
    output_sha256: object,
    output_size_bytes: object,
    context: object,
) -> ResultReceipt:
    """Build a result receipt only from a matching POST rehash snapshot."""

    if type(execution_lease) is not ExecutionLease:
        _fail("W2B_RECEIPT_RESULT_INVALID")
    try:
        _root, domain_receipt, lease = _require_active_lease(
            execution_lease._project_root,
            domain_receipt,
            execution_lease,
            "W2B_RECEIPT_RESULT_INVALID",
        )
        post_snapshot = _rebuild_post_snapshot(
            post_snapshot,
            "W2B_RECEIPT_RESULT_INVALID",
        )
    except ReceiptError:
        _fail("W2B_RECEIPT_RESULT_INVALID")
    if (
        lease._post_bytes is None
        or lease._result_built
        or canonical_json_bytes(post_snapshot.as_dict()) != lease._post_bytes
        or post_snapshot.lease_id != lease._lease_id
        or post_snapshot.execution_snapshot_digest != lease._snapshot_digest
        or post_snapshot.domain_receipt_digest != domain_receipt.canonical_digest
        or post_snapshot.profile_receipt_digest
        != domain_receipt.profile_receipt.canonical_digest
    ):
        _fail("W2B_RECEIPT_RESULT_INVALID")
    result = ResultReceipt(
        domain_receipt=domain_receipt,
        profile_receipt_digest=domain_receipt.profile_receipt.canonical_digest,
        post_rehash_digest=post_snapshot.canonical_digest,
        execution_lease_id=lease._lease_id,
        execution_snapshot_digest=lease._snapshot_digest,
        pre_snapshot_digest=post_snapshot.pre_snapshot_digest,
        backend=CanonicalPayload.from_value(backend),
        runtime=CanonicalPayload.from_value(runtime),
        failures=CanonicalPayload.from_value(failures),
        output_sha256=output_sha256,  # type: ignore[arg-type]
        output_size_bytes=output_size_bytes,  # type: ignore[arg-type]
        context=CanonicalPayload.from_value(context),
    )
    lease._result_built = True
    return result


def receipt_json_bytes(receipt: object) -> bytes:
    """Serialize any public receipt/snapshot to exact canonical JSON."""

    if type(receipt) is DatabaseProfileReceipt:
        rebuilt = _rebuild_profile_receipt(receipt)
    elif type(receipt) is DomainReceipt:
        rebuilt = _rebuild_domain_receipt(receipt)
    elif type(receipt) is ResultReceipt:
        rebuilt = _rebuild_result_receipt(receipt)
    elif type(receipt) is PreExecutionSnapshot:
        rebuilt = _rebuild_pre_snapshot(receipt)
    elif type(receipt) is PostExecutionSnapshot:
        rebuilt = _rebuild_post_snapshot(receipt)
    else:
        _fail("W2B_RECEIPT_JSON_INVALID")
    return canonical_json_bytes(rebuilt.as_dict())


__all__ = (
    "PROFILE_MANIFEST_SCHEMA",
    "PROFILE_RECEIPT_SCHEMA",
    "DOMAIN_RECEIPT_SCHEMA",
    "RESULT_RECEIPT_SCHEMA",
    "REHASH_SNAPSHOT_SCHEMA",
    "EXECUTION_LEASE_SCHEMA",
    "NE04_CONTRACT_SCHEMA",
    "INTERNAL_QUALIFICATION",
    "RELEASE",
    "EXECUTION_MODES",
    "SUPPORTED_DATABASE_FAMILIES",
    "SUPPORTED_FE_PROFILE_IDS",
    "SUPPORTED_WAVE2B_FEATURES",
    "DIRECT_RESULT_FEATURES",
    "MAPPING_RESULT_FEATURES",
    "SOLIDIFICATION_RESULT_FEATURES",
    "FE_POLICY_UNDECIDED",
    "POLICY_NOT_APPLICABLE",
    "PHASE_FINGERPRINT_ALGORITHM",
    "PRODUCTION_USE",
    "ACCEPTANCE_CLAIM",
    "COUNTS_TOWARD_FEATURE_COVERAGE",
    "DEFAULT_PROFILE_MANIFEST_PATH",
    "PROFILE_MANIFEST_SHA256",
    "WAVE2B_RECEIPT_REASON_CODES",
    "ReceiptError",
    "CanonicalPayload",
    "FileIdentity",
    "FileHashObservation",
    "ReportObservation",
    "DatabaseProfileReceipt",
    "DomainReceipt",
    "ExecutionSnapshotFile",
    "PreExecutionSnapshot",
    "PostExecutionSnapshot",
    "ExecutionLease",
    "ResultReceipt",
    "canonical_json_bytes",
    "strict_canonical_json_loads",
    "canonical_payload_digest",
    "phase_fingerprint",
    "load_database_profile_receipt",
    "runtime_phase_names",
    "request_database_binding",
    "build_domain_receipt",
    "open_execution_lease",
    "pre_execution_rehash",
    "post_execution_rehash",
    "build_result_receipt",
    "receipt_json_bytes",
)
