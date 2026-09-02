"""Fail-closed receipts and temporary execution lease for the Fe local witness.

This module is a standard-library provenance boundary.  It grants no NE-04,
release, production, or pressure-domain permission and performs no scientific
calculation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import stat
import tempfile
from typing import Any


CONFIG_SCHEMA = "SWR-NE04-FE-LOCAL-WITNESS-PROFILES-1"
CONFIG_RELATIVE_PATH = "configs/ne04_fe_local_witness_profiles.json"
EXPECTED_CONFIG_SHA256 = (
    "fcda7fffac6f3b792f6cacdafc35a09cf7f756bff4694bb1ded22b04593f0776"
)
EXPECTED_CONFIG_BYTES = 10421
CLAIM = "LOCAL_INTERNAL_DIAGNOSTIC_NOT_NE04_RELEASE"
PROFILE_KEYS = ("thermogar_patch", "upstream_original")
MASS_ORDER = (
    "AL", "B", "C", "CO", "CR", "CU", "FE", "H", "HF", "LA",
    "MN", "MO", "N", "NB", "NI", "O", "P", "PD", "S", "SI",
    "TA", "TI", "V", "W", "Y",
)
SOLVER_COMPONENTS = (
    "AL", "B", "C", "CO", "CR", "CU", "H", "HF", "LA", "MN",
    "MO", "N", "NB", "NI", "O", "P", "PD", "S", "SI", "TA",
    "TI", "V", "W", "Y", "FE", "VA",
)
DATABASE_ELEMENTS = (
    "AL", "B", "C", "CO", "CR", "CU", "FE", "H", "HF", "LA",
    "MN", "MO", "N", "NB", "NI", "O", "P", "PD", "S", "SI",
    "TA", "TI", "V", "VA", "W", "Y",
)
FIXED_PRESSURE_PA = 101325.0
FIXED_PDENS = 500
TEMPERATURE_MINIMUM_K = 673.0
TEMPERATURE_MAXIMUM_K = 2000.0
ELIGIBLE_PHASE_COUNT = 131
ELIGIBLE_PHASE_SHA256 = (
    "facf84563f444d5bdca2d16f22689a2e8dd6bc6a331d7f188dfcf4d8f2ed91b4"
)
RAW_PHASE_COUNT = 132
RAW_PHASE_SHA256 = (
    "f6a545c3e6a2a8d497caa00eb2fe439a28d91689646f679038c485704dd44ad4"
)
ATOMIC_MASS_VECTOR_SHA256 = (
    "b1d3ab2a3c238c00654e32aadce6c14e22af3434349c00e354ef729d8f4014a2"
)
CROSS_PROFILE_MASS_EQUALITY_SHA256 = (
    "f8874d5410c74e6278f57cbcd6eb474c61a5c74ac0a5b8dcdf4c988fab8952a4"
)
STRICT_UPPER_BOUNDS_WT_PERCENT = {
    "AL": 3.0, "B": 0.5, "C": 0.5, "CO": 3.0, "CR": 25.0,
    "CU": 1.0, "H": 0.1, "HF": 0.5, "LA": 0.5, "MN": 25.0,
    "MO": 5.0, "N": 1.0, "NB": 1.0, "NI": 26.0, "O": 0.5,
    "P": 0.05, "PD": 4.0, "S": 0.1, "SI": 3.5, "TA": 0.5,
    "TI": 0.5, "V": 0.5, "W": 3.0, "Y": 0.5,
}


class WitnessContractError(ValueError):
    """Raised when a local-witness contract or receipt fails closed."""


class DuplicateJsonKeyError(WitnessContractError):
    """Raised for duplicate keys in strict JSON."""


def _fail(message: str) -> None:
    raise WitnessContractError(message)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(token: str) -> None:
    raise WitnessContractError(f"non-finite JSON constant: {token}")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _canonical_digest(value: object) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def _is_symlink_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _project_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve(strict=True)
    if not root.is_dir() or _is_symlink_or_reparse(root):
        _fail("project root is not a regular directory")
    return root


def _relative_parts(value: object) -> tuple[str, ...]:
    if type(value) is not str or not value or "\\" in value or "\x00" in value:
        _fail("pinned path is not canonical POSIX")
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or relative.as_posix() != value
        or any(part in {"", ".", ".."} or ":" in part for part in relative.parts)
    ):
        _fail("pinned path is not a safe relative path")
    return relative.parts


def _resolve_pinned(root: Path, relative_path: object) -> Path:
    parts = _relative_parts(relative_path)
    current = root
    for part in parts:
        current = current / part
        if _is_symlink_or_reparse(current):
            _fail("pinned path crosses a symlink/reparse point")
    resolved = current.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise WitnessContractError("pinned path escapes project root") from error
    if not resolved.is_file() or _is_symlink_or_reparse(resolved):
        _fail("pinned path is not a regular file")
    return resolved


def _read_stable(path: Path) -> tuple[bytes, int, str]:
    if not path.is_file() or _is_symlink_or_reparse(path):
        _fail("file identity target is invalid")
    try:
        with path.open("rb") as source:
            before = os.fstat(source.fileno())
            payload = source.read()
            after = os.fstat(source.fileno())
        path_after = path.lstat()
    except OSError as error:
        raise WitnessContractError("stable single-handle read failed") from error
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or not os.path.samestat(after, path_after)
        or _is_symlink_or_reparse(path)
    ):
        _fail("file changed during stable single-handle read")
    if len(payload) != after.st_size:
        _fail("file length changed during identity read")
    return payload, len(payload), _sha256_bytes(payload)


def _safety_envelope(receipt_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        **payload,
        "receipt_kind": receipt_kind,
        "claim": "LOCAL_INTERNAL_DIAGNOSTIC_NOT_NE04_RELEASE",
        "acceptance": False,
        "execution_eligible": False,
        "release_eligible": False,
        "production_use": "DENIED",
    }


@dataclass(frozen=True, slots=True)
class FileIdentity:
    role: str
    relative_path: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if type(self.role) is not str or not self.role:
            _fail("file identity role is invalid")
        _relative_parts(self.relative_path)
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            _fail("file identity size is invalid")
        if (
            type(self.sha256) is not str
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            _fail("file identity SHA-256 is invalid")

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class FileObservation:
    role: str
    relative_path: str
    size_bytes: int
    sha256: str

    def _validate(self) -> None:
        if type(self.role) is not str or not self.role:
            _fail("file observation role is invalid")
        _relative_parts(self.relative_path)
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            _fail("file observation size is invalid")
        if (
            type(self.sha256) is not str
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            _fail("file observation SHA-256 is invalid")

    def __post_init__(self) -> None:
        self._validate()

    def as_dict(self) -> dict[str, Any]:
        self._validate()
        return {
            "role": self.role,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class ProfileDefinition:
    profile_key: str
    role: str
    runtime: FileIdentity


@dataclass(frozen=True, slots=True)
class _WitnessContract:
    config_identity: FileIdentity
    profiles: tuple[ProfileDefinition, ...]
    pinned_inputs: tuple[FileIdentity, ...]
    mass_order: tuple[str, ...]
    solver_components: tuple[str, ...]
    database_elements: tuple[str, ...]
    eligible_phases: tuple[str, ...]
    observed_atomic_masses: tuple[tuple[str, float], ...]
    profile_atomic_mass_sha256: tuple[tuple[str, str], ...]
    cross_profile_mass_equality_sha256: str

    def profile(self, profile_key: object) -> ProfileDefinition:
        matches = [item for item in self.profiles if item.profile_key == profile_key]
        if len(matches) != 1:
            _fail("profile key is not one of the two pinned profiles")
        return matches[0]

    def bound_identities(self) -> tuple[FileIdentity, ...]:
        return (
            self.config_identity,
            *(profile.runtime for profile in self.profiles),
            *self.pinned_inputs,
        )


def _identity_from_card(role: str, card: object) -> FileIdentity:
    if type(card) is not dict or set(card) != {"relative_path", "bytes", "sha256"}:
        _fail(f"pinned identity card {role!r} is invalid")
    return FileIdentity(
        role=role,
        relative_path=card["relative_path"],
        size_bytes=card["bytes"],
        sha256=card["sha256"],
    )


def _phase_fingerprint(phases: tuple[str, ...]) -> str:
    return _sha256_bytes("".join(f"{phase}\n" for phase in phases).encode("utf-8"))


def _load_config(root: Path) -> tuple[dict[str, Any], FileIdentity]:
    path = _resolve_pinned(root, CONFIG_RELATIVE_PATH)
    payload, size, digest = _read_stable(path)
    if size != EXPECTED_CONFIG_BYTES or digest != EXPECTED_CONFIG_SHA256:
        _fail("local witness config identity mismatch")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WitnessContractError("local witness config is not strict UTF-8 JSON") from error
    if type(value) is not dict:
        _fail("local witness config root is not an object")
    identity = FileIdentity(
        role="witness_config",
        relative_path=CONFIG_RELATIVE_PATH,
        size_bytes=size,
        sha256=digest,
    )
    return value, identity


def _validate_config(value: dict[str, Any]) -> None:
    expected_top = {
        "schema_version", "stage", "claim", "acceptance",
        "counts_toward_ne04_acceptance", "execution_eligible",
        "release_eligible", "production_use", "integration", "profiles",
        "pinned_inputs", "request_contract", "bounded_preflight_observation",
        "runtime_rules",
    }
    if set(value) != expected_top:
        _fail("local witness top-level schema mismatch")
    if (
        value["schema_version"] != CONFIG_SCHEMA
        or value["stage"] != "NE04-FE-WITNESS-S1"
        or value["claim"] != CLAIM
        or value["acceptance"] is not False
        or value["counts_toward_ne04_acceptance"] is not False
        or value["execution_eligible"] is not False
        or value["release_eligible"] is not False
        or value["production_use"] != "DENIED"
    ):
        _fail("local witness safety identity mismatch")
    if value["integration"] != {
        "product_ui_connected": False,
        "central_ne04_connected": False,
        "release_ui_connected": False,
        "central_release_calls_discovered": 23,
        "central_release_calls_bound": 0,
    }:
        _fail("local witness integration boundary mismatch")

    request = value["request_contract"]
    if type(request) is not dict:
        _fail("local witness request contract is invalid")
    if (
        request.get("database_key") != "fe"
        or request.get("profile_keys") != list(PROFILE_KEYS)
        or request.get("composition_basis") != "MASS_FRACTION"
        or request.get("mass_fraction_elements") != list(MASS_ORDER)
        or request.get("database_elements") != list(DATABASE_ELEMENTS)
        or request.get("solver_components") != list(SOLVER_COMPONENTS)
        or request.get("balance_element") != "FE"
        or request.get("positive_balance_required") is not True
        or request.get("vacancy_in_user_composition") is not False
        or request.get("vacancy_solver_component_only") is not True
        or request.get("vacancy_condition_forbidden") is not True
        or request.get("implicit_basis_conversion_allowed") is not False
        or request.get("source_limit_unit") != "WT_PERCENT"
        or request.get("request_fraction_unit") != "FRACTION_OF_ONE"
        or request.get("wt_percent_to_mass_fraction_factor") != 0.01
        or request.get("strict_upper_operator") != "<"
        or request.get("fraction_sum") != 1.0
        or request.get("fraction_sum_absolute_tolerance") != 1e-12
        or request.get("strict_upper_bounds_wt_percent")
        != STRICT_UPPER_BOUNDS_WT_PERCENT
        or request.get("temperature_k")
        != {
            "minimum": 673.0,
            "maximum": 2000.0,
            "minimum_inclusive": True,
            "maximum_inclusive": True,
        }
        or request.get("pressure_pa")
        != {
            "value": 101325.0,
            "arbitrary_input_allowed": False,
            "domain_status": "UNKNOWN_BLOCKED",
        }
        or request.get("solver_options")
        != {
            "pdens": 500,
            "semantic": "LOCAL_NUMERICAL_OPTION_NOT_SOURCE_DOMAIN_CLAIM",
        }
    ):
        _fail("local witness request semantics mismatch")

    selection = request.get("phase_selection")
    if type(selection) is not dict:
        _fail("phase selection contract is invalid")
    phases = selection.get("phases")
    if (
        type(phases) is not list
        or len(phases) != ELIGIBLE_PHASE_COUNT
        or phases != sorted(phases)
        or len(set(phases)) != len(phases)
        or selection.get("policy") != "EXACT_FULL_ELIGIBLE_UNIVERSE"
        or selection.get("arbitrary_input_allowed") is not False
        or selection.get("exclusions") != []
        or selection.get("c15_laves_mandatory") is not True
        or selection.get("liquid_mandatory") is not True
        or "C15_LAVES" not in phases
        or "LIQUID" not in phases
        or selection.get("count") != ELIGIBLE_PHASE_COUNT
        or selection.get("fingerprint_algorithm")
        != "SHA256_SORTED_UPPERCASE_UTF8_LF"
        or selection.get("fingerprint_encoding")
        != "UTF-8_WITH_ONE_LF_AFTER_EACH_SORTED_PHASE"
        or selection.get("sha256") != ELIGIBLE_PHASE_SHA256
        or _phase_fingerprint(tuple(phases)) != ELIGIBLE_PHASE_SHA256
        or selection.get("raw_database_phase_count") != RAW_PHASE_COUNT
        or selection.get("raw_database_phase_fingerprint_algorithm")
        != "SHA256_SORTED_UPPERCASE_UTF8_LF"
        or selection.get("raw_database_phase_fingerprint_encoding")
        != "UTF-8_WITH_ONE_LF_AFTER_EACH_SORTED_PHASE"
        or selection.get("raw_database_phase_sha256") != RAW_PHASE_SHA256
        or selection.get("raw_but_not_eligible_phases") != ["BCC_A2"]
        or "BCC_A2" in phases
    ):
        _fail("eligible phase universe mismatch")

    rules = value["runtime_rules"]
    if rules != {
        "accepted_domain_sidecar_pin_role": (
            "STATIC_OBSERVED_INPUT_NOT_RUNTIME_AUTHORIZATION"
        ),
        "local_domain_enforcement": "INDEPENDENT_EXACT_SOURCE_HEADER_RULES",
        "atomic_mass_source": "EXACT_SELECTED_DATABASE_REFSTATES_MASS",
        "patched_upstream_atomic_mass_exact_match_required": True,
        "fallback_atomic_mass_table_allowed": False,
        "mass_to_mole_function": "thermogar_equilibrium_core.mass_to_mole_fractions",
        "round_trip_function": "thermogar_equilibrium_core.mole_to_mass_fractions",
        "round_trip_max_abs_error": 1e-12,
        "database_load_source": (
            "ACTIVE_LOCAL_TEMP_SELECTED_RUNTIME_SNAPSHOT_ONLY"
        ),
        "pre_post_sha256_required": True,
        "raw_xarray_may_escape_backend": False,
        "normalized_projection_required": True,
        "real_equilibrium_executed_in_s1": False,
    }:
        _fail("local witness runtime rules mismatch")

    preflight = value["bounded_preflight_observation"]
    if type(preflight) is not dict:
        _fail("bounded preflight observation is invalid")
    mass_rows = preflight.get("ordered_atomic_mass_rows")
    profile_mass_digests = preflight.get("profile_atomic_mass_vector_sha256")
    if (
        preflight.get("real_equilibrium_executed") is not False
        or preflight.get("database_load_performed") is not True
        or preflight.get("refstates_read_performed") is not True
        or preflight.get("filter_phases_performed") is not True
        or preflight.get("profiles_have_exact_equal_database_elements") is not True
        or preflight.get("profiles_have_exact_equal_atomic_mass_rows") is not True
        or preflight.get("profiles_have_exact_equal_eligible_phase_lists") is not True
        or preflight.get("atomic_mass_vector_fingerprint_algorithm")
        != "SHA256_CANONICAL_JSON_ASCII_SORTED_KEYS_COMPACT"
        or profile_mass_digests
        != {
            "thermogar_patch": ATOMIC_MASS_VECTOR_SHA256,
            "upstream_original": ATOMIC_MASS_VECTOR_SHA256,
        }
        or preflight.get(
            "cross_profile_atomic_mass_equality_fingerprint_algorithm"
        )
        != "SHA256_ASCII_PROFILE_COLON_DIGEST_LF_IN_PROFILE_ORDER"
        or preflight.get("cross_profile_atomic_mass_equality_sha256")
        != CROSS_PROFILE_MASS_EQUALITY_SHA256
        or type(mass_rows) is not list
        or tuple(row[0] for row in mass_rows if type(row) is list and len(row) == 2)
        != MASS_ORDER
        or len(mass_rows) != len(MASS_ORDER)
        or any(
            type(row) is not list
            or len(row) != 2
            or type(row[1]) not in (int, float)
            or isinstance(row[1], bool)
            or not math.isfinite(float(row[1]))
            or float(row[1]) <= 0.0
            for row in mass_rows
        )
    ):
        _fail("bounded preflight mass observation mismatch")
    if _canonical_digest(mass_rows) != ATOMIC_MASS_VECTOR_SHA256:
        _fail("bounded preflight atomic-mass fingerprint mismatch")
    equality_payload = "".join(
        f"{profile_key}:{profile_mass_digests[profile_key]}\n"
        for profile_key in PROFILE_KEYS
    ).encode("ascii")
    if _sha256_bytes(equality_payload) != CROSS_PROFILE_MASS_EQUALITY_SHA256:
        _fail("cross-profile atomic-mass equality fingerprint mismatch")


def _observe_identity(root: Path, identity: FileIdentity) -> FileObservation:
    path = _resolve_pinned(root, identity.relative_path)
    _payload, size, digest = _read_stable(path)
    if size != identity.size_bytes or digest != identity.sha256:
        _fail(f"pinned file identity mismatch for {identity.role}")
    return FileObservation(
        role=identity.role,
        relative_path=identity.relative_path,
        size_bytes=size,
        sha256=digest,
    )


def _load_witness_contract(project_root: str | Path) -> _WitnessContract:
    """Load and hash the only permitted local witness profile contract."""

    root = _project_root(project_root)
    value, config_identity = _load_config(root)
    _validate_config(value)
    profiles_value = value["profiles"]
    if type(profiles_value) is not dict or tuple(profiles_value) != PROFILE_KEYS:
        _fail("profile registry mismatch")
    profiles: list[ProfileDefinition] = []
    expected_roles = {
        "thermogar_patch": "PATCHED_LOCAL_DIAGNOSTIC_ONLY",
        "upstream_original": "UPSTREAM_LOCAL_DIAGNOSTIC_CONTROL_ONLY",
    }
    for profile_key in PROFILE_KEYS:
        card = profiles_value[profile_key]
        if type(card) is not dict or set(card) != {
            "role", "relative_path", "bytes", "sha256"
        }:
            _fail("profile card schema mismatch")
        if card["role"] != expected_roles[profile_key]:
            _fail("profile role mismatch")
        runtime = _identity_from_card(
            f"runtime_{profile_key}",
            {key: card[key] for key in ("relative_path", "bytes", "sha256")},
        )
        profiles.append(ProfileDefinition(profile_key, card["role"], runtime))

    pinned_value = value["pinned_inputs"]
    expected_pinned_roles = (
        "source",
        "accepted_domain_config",
        "accepted_domain_module",
        "equilibrium_core",
        "numerical_grid_dependency",
        "equilibrium_core_test",
    )
    if type(pinned_value) is not dict or tuple(pinned_value) != expected_pinned_roles:
        _fail("pinned input registry mismatch")
    pinned_inputs = tuple(
        _identity_from_card(role, pinned_value[role]) for role in expected_pinned_roles
    )
    mass_rows = tuple(
        (row[0], float(row[1]))
        for row in value["bounded_preflight_observation"]["ordered_atomic_mass_rows"]
    )
    contract = _WitnessContract(
        config_identity=config_identity,
        profiles=tuple(profiles),
        pinned_inputs=pinned_inputs,
        mass_order=MASS_ORDER,
        solver_components=SOLVER_COMPONENTS,
        database_elements=DATABASE_ELEMENTS,
        eligible_phases=tuple(value["request_contract"]["phase_selection"]["phases"]),
        observed_atomic_masses=mass_rows,
        profile_atomic_mass_sha256=tuple(
            (profile_key, value["bounded_preflight_observation"]
             ["profile_atomic_mass_vector_sha256"][profile_key])
            for profile_key in PROFILE_KEYS
        ),
        cross_profile_mass_equality_sha256=value["bounded_preflight_observation"]
        ["cross_profile_atomic_mass_equality_sha256"],
    )
    observations = tuple(
        _observe_identity(root, identity) for identity in contract.bound_identities()
    )
    if len({item.relative_path for item in observations}) != len(observations):
        _fail("bound witness paths are not unique")
    return contract


@dataclass(frozen=True, slots=True)
class ProfileReceipt:
    profile_key: str
    profile_role: str
    selected_runtime: FileObservation
    selected_atomic_mass_vector_sha256: str
    cross_profile_atomic_mass_equality_sha256: str
    all_bound_inputs: tuple[FileObservation, ...]

    def _validate(self) -> None:
        if self.profile_key not in PROFILE_KEYS:
            _fail("profile receipt key is invalid")
        if type(self.profile_role) is not str or not self.profile_role:
            _fail("profile receipt role is invalid")
        if type(self.selected_runtime) is not FileObservation:
            _fail("profile receipt selected runtime is invalid")
        if (
            self.selected_atomic_mass_vector_sha256
            != ATOMIC_MASS_VECTOR_SHA256
            or self.cross_profile_atomic_mass_equality_sha256
            != CROSS_PROFILE_MASS_EQUALITY_SHA256
        ):
            _fail("profile receipt atomic-mass fingerprint is invalid")
        if (
            type(self.all_bound_inputs) is not tuple
            or not self.all_bound_inputs
            or any(type(item) is not FileObservation for item in self.all_bound_inputs)
            or self.selected_runtime not in self.all_bound_inputs
        ):
            _fail("profile receipt bound inputs are invalid")

    def __post_init__(self) -> None:
        self._validate()

    @property
    def digest(self) -> str:
        return _canonical_digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        self._validate()
        return _safety_envelope(
            "FE_LOCAL_WITNESS_PROFILE",
            {
                "profile_key": self.profile_key,
                "profile_role": self.profile_role,
                "selected_runtime": self.selected_runtime.as_dict(),
                "selected_atomic_mass_vector_sha256": (
                    self.selected_atomic_mass_vector_sha256
                ),
                "cross_profile_atomic_mass_equality_sha256": (
                    self.cross_profile_atomic_mass_equality_sha256
                ),
                "all_bound_inputs": [item.as_dict() for item in self.all_bound_inputs],
            },
        )


def _load_profile_receipt(
    project_root: str | Path,
    profile_key: object,
) -> tuple[_WitnessContract, ProfileReceipt]:
    root = _project_root(project_root)
    contract = _load_witness_contract(root)
    selected = contract.profile(profile_key)
    observations = tuple(
        _observe_identity(root, identity) for identity in contract.bound_identities()
    )
    matches = [item for item in observations if item.role == selected.runtime.role]
    if len(matches) != 1:
        _fail("selected runtime observation is absent")
    return contract, ProfileReceipt(
        profile_key=selected.profile_key,
        profile_role=selected.role,
        selected_runtime=matches[0],
        selected_atomic_mass_vector_sha256=dict(
            contract.profile_atomic_mass_sha256
        )[selected.profile_key],
        cross_profile_atomic_mass_equality_sha256=(
            contract.cross_profile_mass_equality_sha256
        ),
        all_bound_inputs=observations,
    )


def _validate_mass_fractions(
    value: object,
) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple or len(value) != len(MASS_ORDER):
        _fail("mass-fraction input must contain all 25 ordered chemical rows")
    rows: list[tuple[str, float]] = []
    for expected_name, row in zip(MASS_ORDER, value):
        if type(row) is not tuple or len(row) != 2 or row[0] != expected_name:
            _fail("mass-fraction element order mismatch")
        raw = row[1]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            _fail("mass-fraction value is invalid")
        number = float(raw)
        if not math.isfinite(number) or number < 0.0:
            _fail("mass-fraction value is non-finite or negative")
        rows.append((expected_name, 0.0 if number == 0.0 else number))
    result = tuple(rows)
    if abs(math.fsum(number for _name, number in result) - 1.0) > 1e-12:
        _fail("mass-fraction simplex does not close to one")
    if dict(result)["FE"] <= 0.0:
        _fail("FE balance must be positive")
    for element, upper_wt_percent in STRICT_UPPER_BOUNDS_WT_PERCENT.items():
        if dict(result)[element] >= upper_wt_percent * 0.01:
            _fail(f"{element} reaches or exceeds its strict source upper bound")
    return result


def _canonicalize_mass_fraction_mapping(
    value: object,
) -> tuple[tuple[str, float], ...]:
    """Freeze one exact 25-key MASS_FRACTION mapping into source order."""

    if not isinstance(value, Mapping):
        _fail("mass-fraction input must be a 25-key mapping")
    try:
        observed_keys = tuple(value.keys())
    except Exception as error:
        raise WitnessContractError("mass-fraction mapping keys are unreadable") from error
    if (
        len(observed_keys) != len(MASS_ORDER)
        or any(type(key) is not str for key in observed_keys)
        or set(observed_keys) != set(MASS_ORDER)
    ):
        _fail("mass-fraction mapping must contain exactly the 25 chemical keys")
    rows: list[tuple[str, float]] = []
    for element in MASS_ORDER:
        try:
            raw = value[element]
        except Exception as error:
            raise WitnessContractError(
                "mass-fraction mapping changed during canonicalization"
            ) from error
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            _fail("mass-fraction mapping value is invalid")
        rows.append((element, float(raw)))
    try:
        if tuple(value.keys()) != observed_keys:
            _fail("mass-fraction mapping changed during canonicalization")
    except Exception as error:
        if isinstance(error, WitnessContractError):
            raise
        raise WitnessContractError(
            "mass-fraction mapping changed during canonicalization"
        ) from error
    return _validate_mass_fractions(tuple(rows))


@dataclass(frozen=True, slots=True)
class RequestReceipt:
    profile_key: str
    temperature_k: float
    mass_fractions: tuple[tuple[str, float], ...]

    def _validate(self) -> None:
        if self.profile_key not in PROFILE_KEYS:
            _fail("request receipt profile is invalid")
        if (
            type(self.temperature_k) is not float
            or not math.isfinite(self.temperature_k)
            or not TEMPERATURE_MINIMUM_K
            <= self.temperature_k
            <= TEMPERATURE_MAXIMUM_K
        ):
            _fail("request receipt temperature is outside 673..2000 K")
        if _validate_mass_fractions(self.mass_fractions) != self.mass_fractions:
            _fail("request receipt mass rows are not canonical")

    def __post_init__(self) -> None:
        self._validate()

    @property
    def digest(self) -> str:
        return _canonical_digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        self._validate()
        return _safety_envelope(
            "FE_LOCAL_WITNESS_REQUEST",
            {
                "profile_key": self.profile_key,
                "temperature_k": self.temperature_k,
                "pressure_pa": 101325.0,
                "pressure_domain_status": "UNKNOWN_BLOCKED",
                "composition_basis": "MASS_FRACTION",
                "mass_fractions": [list(item) for item in self.mass_fractions],
            },
        )


@dataclass(frozen=True, slots=True)
class DomainReceipt:
    profile_key: str
    temperature_k: float
    mass_fractions_digest: str
    reason_codes: tuple[str, ...]

    def _validate(self) -> None:
        if self.profile_key not in PROFILE_KEYS:
            _fail("domain receipt profile is invalid")
        if (
            type(self.temperature_k) is not float
            or not TEMPERATURE_MINIMUM_K
            <= self.temperature_k
            <= TEMPERATURE_MAXIMUM_K
        ):
            _fail("domain receipt temperature is invalid")
        if (
            type(self.mass_fractions_digest) is not str
            or len(self.mass_fractions_digest) != 64
        ):
            _fail("domain receipt mass digest is invalid")
        if self.reason_codes != (
            "FE_LOCAL_WITNESS_NOT_RELEASED",
            "NE04_PRESSURE_DOMAIN_UNKNOWN",
            "FE_LOCAL_DOMAIN_STATIC_PIN_NOT_AUTHORIZATION",
        ):
            _fail("domain receipt reasons are not exact")

    def __post_init__(self) -> None:
        self._validate()

    @property
    def digest(self) -> str:
        return _canonical_digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        self._validate()
        return _safety_envelope(
            "FE_LOCAL_WITNESS_DOMAIN",
            {
                "profile_key": self.profile_key,
                "temperature_k": self.temperature_k,
                "local_composition_temperature_in_source_domain": True,
                "pressure_domain_status": "UNKNOWN_BLOCKED",
                "accepted_sidecar_pin_role": (
                    "STATIC_OBSERVED_INPUT_NOT_RUNTIME_AUTHORIZATION"
                ),
                "independent_local_domain_enforcement": True,
                "mass_fractions_digest": self.mass_fractions_digest,
                "reason_codes": list(self.reason_codes),
            },
        )


def _build_domain_receipt(
    contract: object,
    profile_key: object,
    temperature_k: object,
    mass_fractions: object,
) -> DomainReceipt:
    if type(contract) is not _WitnessContract:
        _fail("domain receipt contract is invalid")
    if contract.config_identity.sha256 != EXPECTED_CONFIG_SHA256:
        _fail("domain receipt contract identity mismatch")
    canonical_mass = _validate_mass_fractions(mass_fractions)
    if type(profile_key) is not str or profile_key not in PROFILE_KEYS:
        _fail("domain receipt profile is invalid")
    if isinstance(temperature_k, bool) or not isinstance(temperature_k, (int, float)):
        _fail("domain receipt temperature is invalid")
    temperature = float(temperature_k)
    if (
        not math.isfinite(temperature)
        or not TEMPERATURE_MINIMUM_K <= temperature <= TEMPERATURE_MAXIMUM_K
    ):
        _fail("domain receipt temperature is outside source limits")
    return DomainReceipt(
        profile_key=profile_key,
        temperature_k=temperature,
        mass_fractions_digest=_canonical_digest([list(item) for item in canonical_mass]),
        reason_codes=(
            "FE_LOCAL_WITNESS_NOT_RELEASED",
            "NE04_PRESSURE_DOMAIN_UNKNOWN",
            "FE_LOCAL_DOMAIN_STATIC_PIN_NOT_AUTHORIZATION",
        ),
    )


@dataclass(frozen=True, slots=True)
class HashSnapshotReceipt:
    stage: str
    lease_id: str
    request_receipt_digest: str
    domain_receipt_digest: str
    profile_receipt_digest: str
    terminal_state: str
    source_observations: tuple[FileObservation, ...]
    runtime_snapshot_observations: tuple[FileObservation, ...]

    def _validate(self) -> None:
        if self.stage not in {"PRE", "POST_PREPARATION", "POST_FAILURE"}:
            _fail("hash snapshot stage is invalid")
        if type(self.lease_id) is not str or len(self.lease_id) != 64:
            _fail("hash snapshot lease identity is invalid")
        for digest in (
            self.request_receipt_digest,
            self.domain_receipt_digest,
            self.profile_receipt_digest,
        ):
            if type(digest) is not str or len(digest) != 64:
                _fail("hash snapshot chain digest is invalid")
        expected_terminal = {
            "PRE": {"NOT_EXECUTED"},
            "POST_PREPARATION": {"PREPARED_NOT_EXECUTED"},
            "POST_FAILURE": {"FAILED"},
        }[self.stage]
        if self.terminal_state not in expected_terminal:
            _fail("hash snapshot terminal state is invalid")
        if (
            type(self.source_observations) is not tuple
            or not self.source_observations
            or any(type(item) is not FileObservation for item in self.source_observations)
            or type(self.runtime_snapshot_observations) is not tuple
            or len(self.runtime_snapshot_observations) != 1
            or type(self.runtime_snapshot_observations[0]) is not FileObservation
        ):
            _fail("hash snapshot observations are invalid")

    def __post_init__(self) -> None:
        self._validate()

    @property
    def digest(self) -> str:
        return _canonical_digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        self._validate()
        return _safety_envelope(
            f"FE_LOCAL_WITNESS_{self.stage}",
            {
                "stage": self.stage,
                "lease_id": self.lease_id,
                "request_receipt_digest": self.request_receipt_digest,
                "domain_receipt_digest": self.domain_receipt_digest,
                "profile_receipt_digest": self.profile_receipt_digest,
                "terminal_state": self.terminal_state,
                "source_observations": [
                    item.as_dict() for item in self.source_observations
                ],
                "runtime_snapshot_observations": [
                    item.as_dict() for item in self.runtime_snapshot_observations
                ],
            },
        )


@dataclass(frozen=True, slots=True)
class PreparedReceipt:
    profile: ProfileReceipt
    request: RequestReceipt
    domain: DomainReceipt
    pre: HashSnapshotReceipt
    post: HashSnapshotReceipt
    atomic_masses: tuple[tuple[str, float], ...]
    derived_mole_fractions: tuple[tuple[str, float], ...]
    round_trip_mass_fractions: tuple[tuple[str, float], ...]
    max_round_trip_abs_error: float
    raw_phase_count: int
    raw_phase_sha256: str
    eligible_phase_count: int
    eligible_phase_sha256: str

    def _validate(self) -> None:
        for receipt, expected_type in (
            (self.profile, ProfileReceipt),
            (self.request, RequestReceipt),
            (self.domain, DomainReceipt),
            (self.pre, HashSnapshotReceipt),
            (self.post, HashSnapshotReceipt),
        ):
            if type(receipt) is not expected_type:
                _fail("prepared receipt chain object is invalid")
            receipt.as_dict()
        if (
            self.profile.profile_key != self.request.profile_key
            or self.profile.profile_key != self.domain.profile_key
            or self.pre.stage != "PRE"
            or self.pre.terminal_state != "NOT_EXECUTED"
            or self.post.stage != "POST_PREPARATION"
            or self.post.terminal_state != "PREPARED_NOT_EXECUTED"
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
            _fail("prepared receipt chain is inconsistent")
        for rows, label in (
            (self.atomic_masses, "atomic mass"),
            (self.derived_mole_fractions, "derived mole"),
            (self.round_trip_mass_fractions, "round-trip mass"),
        ):
            if (
                type(rows) is not tuple
                or tuple(name for name, _value in rows) != MASS_ORDER
                or any(
                    type(row) is not tuple
                    or len(row) != 2
                    or type(row[1]) is not float
                    or not math.isfinite(row[1])
                    for row in rows
                )
            ):
                _fail(f"prepared {label} rows are not canonical")
        if (
            _canonical_digest([list(item) for item in self.atomic_masses])
            != self.profile.selected_atomic_mass_vector_sha256
            or any(value <= 0.0 for _name, value in self.atomic_masses)
            or abs(
                math.fsum(value for _name, value in self.derived_mole_fractions)
                - 1.0
            )
            > 1e-12
            or _validate_mass_fractions(self.round_trip_mass_fractions)
            != self.round_trip_mass_fractions
            or type(self.max_round_trip_abs_error) is not float
            or not 0.0 <= self.max_round_trip_abs_error <= 1e-12
            or self.raw_phase_count != RAW_PHASE_COUNT
            or self.raw_phase_sha256 != RAW_PHASE_SHA256
            or self.eligible_phase_count != ELIGIBLE_PHASE_COUNT
            or self.eligible_phase_sha256 != ELIGIBLE_PHASE_SHA256
        ):
            _fail("prepared projection is inconsistent with pinned facts")

    def __post_init__(self) -> None:
        self._validate()

    @property
    def digest(self) -> str:
        return _canonical_digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        self._validate()
        return _safety_envelope(
            "FE_LOCAL_WITNESS_PREPARED_NOT_EXECUTED",
            {
                "status": "PREPARED_NOT_EXECUTED",
                "profile_key": self.profile.profile_key,
                "profile_receipt_digest": self.profile.digest,
                "request_receipt_digest": self.request.digest,
                "domain_receipt_digest": self.domain.digest,
                "pre_receipt_digest": self.pre.digest,
                "post_receipt_digest": self.post.digest,
                "input_basis": "MASS_FRACTION",
                "atomic_mass_source": "EXACT_SELECTED_DATABASE_REFSTATES_MASS",
                "input_mass_fractions": [
                    list(item) for item in self.request.mass_fractions
                ],
                "atomic_masses": [list(item) for item in self.atomic_masses],
                "derived_mole_fractions": [
                    list(item) for item in self.derived_mole_fractions
                ],
                "round_trip_mass_fractions": [
                    list(item) for item in self.round_trip_mass_fractions
                ],
                "max_round_trip_abs_error": self.max_round_trip_abs_error,
                "raw_phase_count": self.raw_phase_count,
                "raw_phase_sha256": self.raw_phase_sha256,
                "eligible_phase_count": self.eligible_phase_count,
                "eligible_phase_sha256": self.eligible_phase_sha256,
                "c15_laves_present": True,
                "liquid_present": True,
                "real_equilibrium_executed": False,
                "raw_xarray_included": False,
            },
        )


@dataclass(frozen=True, slots=True)
class FailureReceipt:
    profile: ProfileReceipt
    request: RequestReceipt
    domain: DomainReceipt
    pre: HashSnapshotReceipt
    post: HashSnapshotReceipt
    failure_code: str

    def _validate(self) -> None:
        for receipt, expected_type in (
            (self.profile, ProfileReceipt),
            (self.request, RequestReceipt),
            (self.domain, DomainReceipt),
            (self.pre, HashSnapshotReceipt),
            (self.post, HashSnapshotReceipt),
        ):
            if type(receipt) is not expected_type:
                _fail("failure receipt chain object is invalid")
            receipt.as_dict()
        if (
            type(self.failure_code) is not str
            or not self.failure_code.startswith("FE_LOCAL_WITNESS_")
            or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in self.failure_code)
        ):
            _fail("failure receipt code is invalid")
        if (
            self.failure_code == "FE_LOCAL_WITNESS_S1_PREPARED_NOT_EXECUTED"
            or self.profile.profile_key != self.request.profile_key
            or self.profile.profile_key != self.domain.profile_key
            or self.pre.stage != "PRE"
            or self.pre.terminal_state != "NOT_EXECUTED"
            or self.post.stage != "POST_FAILURE"
            or self.post.terminal_state != "FAILED"
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
            _fail("failure receipt chain is inconsistent")

    def __post_init__(self) -> None:
        self._validate()

    @property
    def digest(self) -> str:
        return _canonical_digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        self._validate()
        return _safety_envelope(
            "FE_LOCAL_WITNESS_FAILURE",
            {
                "profile_key": self.profile.profile_key,
                "terminal_state": "FAILED",
                "failure_code": self.failure_code,
                "profile_receipt_digest": self.profile.digest,
                "request_receipt_digest": self.request.digest,
                "domain_receipt_digest": self.domain.digest,
                "pre_receipt_digest": self.pre.digest,
                "post_receipt_digest": self.post.digest,
                "real_equilibrium_executed": False,
                "raw_exception_included": False,
                "path_included": False,
            },
        )


_ACTIVE_LEASES: dict[str, "_LocalWitnessLease"] = {}


class _LocalWitnessLease:
    """Single-use selected-runtime lease with an exact state transition chain."""

    __slots__ = (
        "_root", "_contract", "_profile", "_request", "_domain",
        "_lease_id", "_active", "_state", "_snapshot_root",
        "_snapshot_paths", "_snapshot_handles", "_pre", "_post",
    )

    def __init__(
        self,
        project_root: str | Path,
        contract: _WitnessContract,
        profile_receipt: ProfileReceipt,
        request_receipt: RequestReceipt,
        domain_receipt: DomainReceipt,
    ) -> None:
        self._root = _project_root(project_root)
        self._contract = contract
        self._profile = profile_receipt
        self._request = request_receipt
        self._domain = domain_receipt
        self._lease_id = secrets.token_hex(32)
        self._active = False
        self._state = "NEW"
        self._snapshot_root: Path | None = None
        self._snapshot_paths: dict[str, Path] = {}
        self._snapshot_handles: dict[str, Any] = {}
        self._pre: HashSnapshotReceipt | None = None
        self._post: HashSnapshotReceipt | None = None

    def _require_active(self) -> None:
        if (
            not self._active
            or self._state in {"NEW", "POST", "CLOSED"}
            or _ACTIVE_LEASES.get(self._lease_id) is not self
        ):
            _fail("local witness lease is not active")

    def _current_source_observations(self) -> tuple[FileObservation, ...]:
        return tuple(
            _observe_identity(self._root, identity)
            for identity in self._contract.bound_identities()
        )

    def _snapshot_observations(self) -> tuple[FileObservation, ...]:
        self._require_active()
        profile_key = self._profile.profile_key
        path = self._snapshot_paths.get(profile_key)
        if path is None or self._snapshot_root is None:
            _fail("selected runtime snapshot path is absent")
        try:
            path.resolve(strict=True).relative_to(self._snapshot_root)
        except (OSError, ValueError) as error:
            raise WitnessContractError("runtime snapshot escaped lease") from error
        payload, size, digest = _read_stable(path)
        del payload
        expected = self._contract.profile(profile_key).runtime
        if size != expected.size_bytes or digest != expected.sha256:
            _fail("selected runtime snapshot identity mismatch")
        return (
            FileObservation(
                role=f"snapshot_{profile_key}",
                relative_path=path.name,
                size_bytes=size,
                sha256=digest,
            ),
        )

    def _verified_snapshot_bytes(self) -> bytes:
        """Read the selected readonly snapshot through its held file handle."""

        self._require_active()
        profile_key = self._profile.profile_key
        path = self._snapshot_paths.get(profile_key)
        handle = self._snapshot_handles.get(profile_key)
        if path is None or handle is None:
            _fail("selected runtime snapshot capability is absent")
        try:
            before = os.fstat(handle.fileno())
            handle.seek(0)
            payload = handle.read()
            after = os.fstat(handle.fileno())
            path_after = path.lstat()
        except OSError as error:
            raise WitnessContractError(
                "snapshot single-handle read failed"
            ) from error
        expected = self._contract.profile(profile_key).runtime
        if (
            before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or not os.path.samestat(after, path_after)
            or _is_symlink_or_reparse(path)
            or len(payload) != expected.size_bytes
            or _sha256_bytes(payload) != expected.sha256
        ):
            _fail("selected runtime snapshot bytes are not the pinned identity")
        return bytes(payload)

    def _discard_snapshot_resources(self) -> bool:
        """Best-effort cleanup returning only a non-sensitive failure flag."""

        cleanup_failed = False
        for handle in self._snapshot_handles.values():
            try:
                handle.close()
            except (OSError, ValueError):
                cleanup_failed = True
        self._snapshot_handles.clear()
        for path in self._snapshot_paths.values():
            try:
                if path.exists():
                    os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
            except OSError:
                cleanup_failed = True
        if self._snapshot_root is not None:
            try:
                shutil.rmtree(self._snapshot_root, ignore_errors=False)
            except OSError:
                cleanup_failed = True
        self._snapshot_root = None
        self._snapshot_paths.clear()
        return cleanup_failed

    def __enter__(self) -> "_LocalWitnessLease":
        if self._state != "NEW" or self._active or self._lease_id in _ACTIVE_LEASES:
            _fail("local witness lease cannot be reused")
        current_contract, current_profile = _load_profile_receipt(
            self._root,
            self._profile.profile_key,
        )
        if (
            _canonical_digest(current_profile.as_dict()) != self._profile.digest
            or current_contract != self._contract
            or self._request.profile_key != self._profile.profile_key
            or self._domain.profile_key != self._profile.profile_key
            or self._request.temperature_k != self._domain.temperature_k
        ):
            _fail("profile changed before lease creation")
        try:
            snapshot_root = Path(
                tempfile.mkdtemp(prefix="thermogar_fe_witness_")
            ).resolve(strict=True)
        except OSError:
            raise WitnessContractError(
                "local witness snapshot setup failed"
            ) from None
        try:
            snapshot_root.relative_to(self._root)
        except ValueError:
            pass
        else:
            try:
                shutil.rmtree(snapshot_root)
            except OSError:
                pass
            _fail("runtime snapshot must be outside the project root")
        self._snapshot_root = snapshot_root
        target: Path | None = None
        try:
            profile = self._contract.profile(self._profile.profile_key)
            source_path = _resolve_pinned(self._root, profile.runtime.relative_path)
            payload, size, digest = _read_stable(source_path)
            if size != profile.runtime.size_bytes or digest != profile.runtime.sha256:
                _fail("selected runtime changed before snapshot copy")
            target = snapshot_root / f"selected-{digest}.tdb"
            with target.open("xb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.chmod(target, stat.S_IREAD)
            self._snapshot_paths[profile.profile_key] = target
            self._snapshot_handles[profile.profile_key] = target.open("rb")
            self._active = True
            self._state = "OPEN"
            _ACTIVE_LEASES[self._lease_id] = self
            self._snapshot_observations()
            return self
        except WitnessContractError as error:
            _ACTIVE_LEASES.pop(self._lease_id, None)
            self._active = False
            self._state = "CLOSED"
            self._discard_snapshot_resources()
            raise WitnessContractError(str(error)) from None
        except Exception:
            _ACTIVE_LEASES.pop(self._lease_id, None)
            self._active = False
            self._state = "CLOSED"
            self._discard_snapshot_resources()
            raise WitnessContractError(
                "local witness snapshot setup failed"
            ) from None

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        incomplete = self._state != "POST"
        _ACTIVE_LEASES.pop(self._lease_id, None)
        self._active = False
        cleanup_failed = self._discard_snapshot_resources()
        self._state = "CLOSED"
        if incomplete:
            raise WitnessContractError(
                "local witness lease closed without terminal POST"
            ) from None
        if cleanup_failed:
            raise WitnessContractError(
                "local witness snapshot cleanup failed"
            ) from None
        return False

    def _preparation_rehash(self) -> HashSnapshotReceipt:
        self._require_active()
        if self._state != "OPEN" or self._pre is not None or self._post is not None:
            _fail("PRE receipt is not single-use")
        observations = self._current_source_observations()
        if observations != self._profile.all_bound_inputs:
            _fail("bound inputs changed before PRE")
        self._pre = HashSnapshotReceipt(
            stage="PRE",
            lease_id=self._lease_id,
            request_receipt_digest=self._request.digest,
            domain_receipt_digest=self._domain.digest,
            profile_receipt_digest=self._profile.digest,
            terminal_state="NOT_EXECUTED",
            source_observations=observations,
            runtime_snapshot_observations=self._snapshot_observations(),
        )
        self._state = "PRE"
        return self._pre

    def _backend_snapshot_capability(
        self,
    ) -> tuple[_WitnessContract, str, bytes]:
        self._require_active()
        if self._state != "PRE" or self._pre is None or self._post is not None:
            _fail("backend inputs require exact PRE and no POST")
        snapshot_bytes = self._verified_snapshot_bytes()
        return (
            self._contract,
            self._profile.profile_key,
            snapshot_bytes,
        )

    def _backend_snapshot_observation(self) -> FileObservation:
        self._require_active()
        if self._state != "PRE" or self._pre is None or self._post is not None:
            _fail("backend snapshot observation requires exact PRE")
        return self._snapshot_observations()[0]

    def _mark_prepared_not_executed(self) -> None:
        self._require_active()
        if self._state != "PRE":
            _fail("lease preparation transition is invalid")
        self._snapshot_observations()
        self._state = "PREPARED_NOT_EXECUTED"

    def _mark_failed(self) -> None:
        self._require_active()
        if self._state != "PRE":
            _fail("lease failure transition is invalid")
        self._snapshot_observations()
        self._state = "FAILED"

    def _post_rehash(
        self,
        pre_receipt: object,
    ) -> HashSnapshotReceipt:
        self._require_active()
        if (
            type(pre_receipt) is not HashSnapshotReceipt
            or self._pre is None
            or self._post is not None
            or pre_receipt.digest != self._pre.digest
            or self._state not in {"PREPARED_NOT_EXECUTED", "FAILED"}
        ):
            _fail("POST receipt does not bind the exact PRE")
        observations = self._current_source_observations()
        snapshots = self._snapshot_observations()
        if (
            observations != self._pre.source_observations
            or snapshots != self._pre.runtime_snapshot_observations
        ):
            _fail("PRE/POST SHA-256 observations differ")
        self._post = HashSnapshotReceipt(
            stage=(
                "POST_PREPARATION"
                if self._state == "PREPARED_NOT_EXECUTED"
                else "POST_FAILURE"
            ),
            lease_id=self._lease_id,
            request_receipt_digest=self._request.digest,
            domain_receipt_digest=self._domain.digest,
            profile_receipt_digest=self._profile.digest,
            terminal_state=self._state,
            source_observations=observations,
            runtime_snapshot_observations=snapshots,
        )
        self._state = "POST"
        return self._post


def _open_local_witness_lease(
    project_root: str | Path,
    contract: object,
    profile_receipt: object,
    request_receipt: object,
    domain_receipt: object,
) -> _LocalWitnessLease:
    if (
        type(contract) is not _WitnessContract
        or type(profile_receipt) is not ProfileReceipt
        or type(request_receipt) is not RequestReceipt
        or type(domain_receipt) is not DomainReceipt
    ):
        _fail("local witness lease inputs are invalid")
    return _LocalWitnessLease(
        project_root,
        contract,
        profile_receipt,
        request_receipt,
        domain_receipt,
    )
