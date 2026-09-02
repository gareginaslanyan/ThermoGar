"""Contained local Fe real-equilibrium witness controller (S2 code stage).

The only public call accepts a pinned profile, an exact 25-key mass-fraction
mapping, and temperature.  Scientific work is delegated to one suspended,
job-contained Windows worker.  No product or release surface imports this
module.
"""

from __future__ import annotations

import base64
from collections import deque
from collections.abc import Mapping
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
import json
import math
import msvcrt
import os
from pathlib import Path, PurePosixPath
import platform
import secrets
import stat
import subprocess
import sys
import threading
import time
from typing import Any, Iterator


CONFIG_SCHEMA = "SWR-NE04-FE-EQUILIBRIUM-WITNESS-2"
CONFIG_RELATIVE_PATH = "configs/ne04_fe_equilibrium_witness_v1.json"
CONFIG_BYTES = 18796
CONFIG_SHA256 = "a14e6bfec5049347f9bbcb5de43ad1c5b55e31b9de5e5534fac7a119235da27f"
WORKER_RELATIVE_PATH = "app/thermogar_fe_equilibrium_worker.py"
WORKER_BYTES = 48278
WORKER_SHA256 = "7b8c9f4a0293fedd14ac7c95cf45e857e1b39530138fdff1d7f1208a67547a14"
REQUEST_SCHEMA = "SWR-NE04-FE-EQUILIBRIUM-WORKER-REQUEST-2"
RESPONSE_SCHEMA = "SWR-NE04-FE-EQUILIBRIUM-WORKER-RESPONSE-2"
CLAIM = "LOCAL_INTERNAL_DIAGNOSTIC_REAL_EQUILIBRIUM_NOT_NE04_RELEASE"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROFILE_KEYS = ("thermogar_patch", "upstream_original")
PROFILE_SHA256 = {
    "thermogar_patch": "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612",
    "upstream_original": "f9375c3a7a8649bace698e2177f2cc964bce3f8a19f08ae05d88840abd77b112",
}
MASS_ORDER = (
    "AL", "B", "C", "CO", "CR", "CU", "FE", "H", "HF", "LA",
    "MN", "MO", "N", "NB", "NI", "O", "P", "PD", "S", "SI",
    "TA", "TI", "V", "W", "Y",
)
NON_FE_ORDER = tuple(element for element in MASS_ORDER if element != "FE")
FULL_SOLVER_COMPONENTS = (*NON_FE_ORDER, "FE", "VA")
COMPONENT_PROJECTION_ALGORITHM = "MASS_ORDER_STRICTLY_POSITIVE_NORMALIZED_MASS_V1"
PHASE_PROJECTION_ALGORITHM = "PYCALPHAD_0_11_2_FILTER_PHASES_FROZEN_131_V1"
PRESSURE_PA = 101325.0
PDENS = 25
ZERO_FLOOR = 1e-10
BALANCE_TOLERANCE = 1e-8
TIMEOUT_SECONDS = 300.0
TREE_RSS_LIMIT_BYTES = 4294967296
POLL_SECONDS = 0.1
MAX_INPUT_BYTES = 1048576
MAX_STDOUT_BYTES = 262144
MAX_STDERR_TAIL_BYTES = 8192
MAX_RAW_ROWS = 512
MAX_ATTEMPTS = 2
MUTEX_NAME = "Global\\ThermoGar.NE04.FeWitness.S2.v1"
PRIVATE_DIRECTORY_SDDL = "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;OW)"
RETRY_CODES = {
    "FE_EQ_WORKER_CHILD_EXIT_NO_RESPONSE",
    "FE_EQ_WORKER_PIPE_BROKEN",
}
SCIENTIFIC_FAILURE_STAGE = "EQUILIBRIUM_CALL"
SCIENTIFIC_FAILURE_CHAIN_LIMIT = 4
SCIENTIFIC_FAILURE_CATEGORIES = {
    "MEMORY_ALLOCATION",
    "MODEL_CONSTRUCTION",
    "CONDITION_CONTRACT",
    "SOLVER_FAILURE",
    "OTHER",
}
SCIENTIFIC_EXCEPTION_TOKENS = {
    "MEMORY_ERROR",
    "PYCALPHAD_DOF_ERROR",
    "PYCALPHAD_CONDITION_ERROR",
    "PYCALPHAD_EQUILIBRIUM_ERROR",
    "NUMPY_LINALG_ERROR",
    "OTHER",
}
STRICT_UPPER_BOUNDS_WT_PERCENT = {
    "AL": 3.0, "B": 0.5, "C": 0.5, "CO": 3.0, "CR": 25.0,
    "CU": 1.0, "H": 0.1, "HF": 0.5, "LA": 0.5, "MN": 25.0,
    "MO": 5.0, "N": 1.0, "NB": 1.0, "NI": 26.0, "O": 0.5,
    "P": 0.05, "PD": 4.0, "S": 0.1, "SI": 3.5, "TA": 0.5,
    "TI": 0.5, "V": 0.5, "W": 3.0, "Y": 0.5,
}
ALLOWED_WORKER_FAILURE_CODES = {
    "FE_EQ_WORKER_INPUT_LIMIT_EXCEEDED",
    "FE_EQ_WORKER_PROTOCOL_INVALID",
    "FE_EQ_WORKER_REQUEST_ID_INVALID",
    "FE_EQ_WORKER_PROFILE_INVALID",
    "FE_EQ_WORKER_RUNTIME_IDENTITY_INVALID",
    "FE_EQ_WORKER_REQUEST_COMPOSITION_INVALID",
    "FE_EQ_WORKER_TEMPERATURE_INVALID",
    "FE_EQ_WORKER_SCOPE_INVALID",
    "FE_EQ_WORKER_PHASE_SCOPE_INVALID",
    "FE_EQ_WORKER_RUNTIME_POLICY_INVALID",
    "FE_EQ_WORKER_SCIENTIFIC_API_UNAVAILABLE",
    "FE_EQ_WORKER_DATABASE_LOAD_FAILED",
    "FE_EQ_WORKER_DATABASE_METADATA_INVALID",
    "FE_EQ_WORKER_ATOMIC_MASS_MISMATCH",
    "FE_EQ_WORKER_BASIS_CONVERSION_FAILED",
    "FE_EQ_WORKER_EFFECTIVE_COMPOSITION_INVALID",
    "FE_EQ_WORKER_CONDITION_SCOPE_INVALID",
    "FE_EQ_WORKER_SCIENTIFIC_API_FAILED",
    "FE_EQ_WORKER_DATASET_SHAPE_INVALID",
    "FE_EQ_WORKER_COMPONENT_AXIS_INVALID",
    "FE_EQ_WORKER_PHASE_RESULT_INVALID",
    "FE_EQ_WORKER_COMPONENT_RESULT_INVALID",
    "FE_EQ_WORKER_EMPTY_RESULT",
    "FE_EQ_WORKER_PHASE_BALANCE_INVALID",
    "FE_EQ_WORKER_COMPONENT_BULK_BALANCE_INVALID",
    "FE_EQ_WORKER_RESPONSE_LIMIT_EXCEEDED",
    "FE_EQ_WORKER_INTERNAL_FAILURE",
}
CONTROLLER_FAILURE_CODES = {
    "FE_EQ_CONTROLLER_CONTRACT_INVALID",
    "FE_EQ_CONTROLLER_REQUEST_INVALID",
    "FE_EQ_CONTROLLER_PLATFORM_UNSUPPORTED",
    "FE_EQ_CONTROLLER_RUNTIME_DEPENDENCY_INVALID",
    "FE_EQ_CONTROLLER_MUTEX_UNAVAILABLE",
    "FE_EQ_CONTROLLER_MUTEX_TIMEOUT",
    "FE_EQ_CONTROLLER_MUTEX_BUSY",
    "FE_EQ_CONTROLLER_CONTAINMENT_UNAVAILABLE",
    "FE_EQ_WORKER_TIMEOUT",
    "FE_EQ_WORKER_TREE_RSS_LIMIT",
    "FE_EQ_WORKER_RESOURCE_MONITOR_FAILED",
    "FE_EQ_WORKER_WAIT_STATE_INVALID",
    "FE_EQ_WORKER_STDOUT_LIMIT",
    "FE_EQ_WORKER_CHILD_EXIT_NO_RESPONSE",
    "FE_EQ_WORKER_PIPE_BROKEN",
    "FE_EQ_WORKER_PROTOCOL_INVALID",
    "FE_EQ_WORKER_TERMINATION_FAILED",
    "FE_EQ_WORKER_TRANSPORT_AFTER_VALID_RESPONSE",
    "FE_EQ_CONTROLLER_CLEANUP_FAILED",
    "FE_EQ_CONTROLLER_INPUT_CHANGED",
    "FE_EQ_CONTROLLER_INTERNAL_FAILURE",
}


class EquilibriumWitnessError(RuntimeError):
    def __init__(self, code: str):
        if code not in CONTROLLER_FAILURE_CODES | ALLOWED_WORKER_FAILURE_CODES:
            code = "FE_EQ_CONTROLLER_INTERNAL_FAILURE"
        self.code = code
        super().__init__(code)


class _ContractFailure(ValueError):
    pass


class _ContainmentStageFailure(_ContractFailure):
    __slots__ = ("operation", "win32_code")

    def __init__(self, operation: str, win32_code: int | None):
        self.operation = operation
        self.win32_code = win32_code
        code_text = "NONE" if win32_code is None else str(win32_code)
        super().__init__(f"operation={operation};win32_code={code_text}")


def _fail(message: str) -> None:
    raise _ContractFailure(message)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_token: str) -> None:
    _fail("non-finite JSON constant")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _relative_parts(value: object) -> tuple[str, ...]:
    if type(value) is not str or not value or "\\" in value or "\x00" in value:
        _fail("unsafe relative path")
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or pure.as_posix() != value
        or any(part in {"", ".", ".."} or ":" in part for part in pure.parts)
    ):
        _fail("unsafe relative path")
    return pure.parts


def _resolve_pinned(root: Path, relative: object) -> Path:
    current = root
    for part in _relative_parts(relative):
        current = current / part
        if _is_reparse(current):
            _fail("pinned path crosses reparse point")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as error:
        raise _ContractFailure("pinned path invalid") from error
    if not resolved.is_file() or _is_reparse(resolved):
        _fail("pinned path not regular")
    return resolved


def _read_stable(path: Path) -> tuple[bytes, int, str]:
    try:
        with path.open("rb") as source:
            before = os.fstat(source.fileno())
            payload = source.read()
            after = os.fstat(source.fileno())
        path_after = path.lstat()
    except OSError as error:
        raise _ContractFailure("stable read failed") from error
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or not os.path.samestat(after, path_after)
        or len(payload) != after.st_size
        or _is_reparse(path)
    ):
        _fail("stable read changed")
    return payload, len(payload), hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class _FileCard:
    role: str
    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _Contract:
    value: dict[str, Any]
    cards: tuple[_FileCard, ...]
    eligible_phases: tuple[str, ...]
    profile_cards: tuple[_FileCard, ...]
    worker_python: _FileCard


@dataclass(frozen=True, slots=True)
class InputObservation:
    role: str
    size_bytes: int
    sha256: str

    def _validate(self) -> None:
        if (
            type(self.role) is not str
            or not self.role
            or type(self.size_bytes) is not int
            or self.size_bytes < 0
            or type(self.sha256) is not str
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            _fail("input observation invalid")

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
class InputSnapshot:
    stage: str
    request_sha256: str
    observations: tuple[InputObservation, ...]

    def _validate(self) -> None:
        if (
            self.stage not in {"PRE", "POST"}
            or type(self.request_sha256) is not str
            or len(self.request_sha256) != 64
            or type(self.observations) is not tuple
            or not self.observations
            or any(type(item) is not InputObservation for item in self.observations)
            or len({item.role for item in self.observations}) != len(self.observations)
        ):
            _fail("input snapshot invalid")
        for item in self.observations:
            item._validate()

    def __post_init__(self) -> None:
        self._validate()

    @property
    def digest(self) -> str:
        return _digest(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        self._validate()
        return {
            "stage": self.stage,
            "request_sha256": self.request_sha256,
            "observations": [item.as_dict() for item in self.observations],
        }


@dataclass(frozen=True, slots=True)
class AttemptReceipt:
    attempt_number: int
    request_sha256: str
    status: str
    failure_code: str | None
    return_code: int | None
    duration_seconds: float
    peak_observed_tree_rss_bytes: int
    stdout_observed_bytes: int
    stdout_sha256: str
    stderr_observed_bytes: int
    stderr_tail_bytes: int
    stderr_tail_sha256: str
    process_tree_terminated: bool
    matched_valid_response: bool
    real_equilibrium_execution_status: str

    def _validate(self) -> None:
        if (
            self.attempt_number not in {1, 2}
            or type(self.request_sha256) is not str
            or len(self.request_sha256) != 64
            or self.status not in {"SUCCESS", "FAILURE"}
            or (
                self.status == "SUCCESS" and self.failure_code is not None
            )
            or (
                self.status == "FAILURE"
                and self.failure_code
                not in CONTROLLER_FAILURE_CODES | ALLOWED_WORKER_FAILURE_CODES
            )
            or (self.return_code is not None and type(self.return_code) is not int)
            or type(self.duration_seconds) is not float
            or not math.isfinite(self.duration_seconds)
            or self.duration_seconds < 0.0
            or type(self.peak_observed_tree_rss_bytes) is not int
            or self.peak_observed_tree_rss_bytes < 0
            or type(self.stdout_observed_bytes) is not int
            or self.stdout_observed_bytes < 0
            or type(self.stderr_observed_bytes) is not int
            or self.stderr_observed_bytes < 0
            or type(self.stderr_tail_bytes) is not int
            or not 0 <= self.stderr_tail_bytes <= MAX_STDERR_TAIL_BYTES
            or any(
                type(digest) is not str or len(digest) != 64
                for digest in (self.stdout_sha256, self.stderr_tail_sha256)
            )
            or type(self.process_tree_terminated) is not bool
            or type(self.matched_valid_response) is not bool
            or self.real_equilibrium_execution_status
            not in {
                "CONFIRMED_EXECUTED",
                "CONFIRMED_NOT_INVOKED",
                "UNKNOWN_AFTER_TRANSPORT_OR_CONTAINMENT_FAILURE",
            }
            or (
                self.matched_valid_response
                and self.real_equilibrium_execution_status
                == "UNKNOWN_AFTER_TRANSPORT_OR_CONTAINMENT_FAILURE"
                and self.failure_code != "FE_EQ_CONTROLLER_CLEANUP_FAILED"
            )
            or (
                not self.matched_valid_response
                and self.real_equilibrium_execution_status
                != "UNKNOWN_AFTER_TRANSPORT_OR_CONTAINMENT_FAILURE"
            )
            or (self.status == "SUCCESS" and not self.matched_valid_response)
            or (
                self.status == "SUCCESS"
                and self.real_equilibrium_execution_status != "CONFIRMED_EXECUTED"
            )
            or (
                self.failure_code in RETRY_CODES
                and (
                    self.matched_valid_response
                    or self.real_equilibrium_execution_status
                    != "UNKNOWN_AFTER_TRANSPORT_OR_CONTAINMENT_FAILURE"
                )
            )
        ):
            _fail("attempt receipt invalid")

    def __post_init__(self) -> None:
        self._validate()

    def as_dict(self) -> dict[str, Any]:
        self._validate()
        return {
            "attempt_number": self.attempt_number,
            "request_sha256": self.request_sha256,
            "status": self.status,
            "failure_code": self.failure_code,
            "return_code": self.return_code,
            "duration_seconds": self.duration_seconds,
            "peak_observed_tree_rss_bytes": self.peak_observed_tree_rss_bytes,
            "stdout_observed_bytes": self.stdout_observed_bytes,
            "stdout_sha256": self.stdout_sha256,
            "stderr_observed_bytes": self.stderr_observed_bytes,
            "stderr_tail_bytes": self.stderr_tail_bytes,
            "stderr_tail_sha256": self.stderr_tail_sha256,
            "process_tree_terminated": self.process_tree_terminated,
            "matched_valid_response": self.matched_valid_response,
            "real_equilibrium_execution_status": self.real_equilibrium_execution_status,
            "timeout_seconds": TIMEOUT_SECONDS,
            "tree_rss_limit_bytes": TREE_RSS_LIMIT_BYTES,
            "stdout_limit_bytes": MAX_STDOUT_BYTES,
            "stderr_tail_limit_bytes": MAX_STDERR_TAIL_BYTES,
        }


@dataclass(frozen=True, slots=True)
class _AttemptExecution:
    receipt: AttemptReceipt
    response_json: str | None


@dataclass(frozen=True, slots=True)
class _LockedCodeFile:
    role: str
    path: Path
    file_object: Any


@dataclass(frozen=True, slots=True)
class EquilibriumWitnessResult:
    profile_id: str
    temperature_k: float
    mass_fractions: tuple[tuple[str, float], ...]
    request_sha256: str
    pre: InputSnapshot
    post: InputSnapshot
    attempts: tuple[AttemptReceipt, ...]
    status: str
    failure_code: str | None
    worker_response_json: str | None
    eligible_phases: tuple[str, ...]

    def _validate(self) -> dict[str, Any] | None:
        if (
            self.profile_id not in PROFILE_KEYS
            or type(self.temperature_k) is not float
            or not 673.0 <= self.temperature_k <= 2000.0
            or _validate_mass_tuple(self.mass_fractions) != self.mass_fractions
            or type(self.pre) is not InputSnapshot
            or type(self.post) is not InputSnapshot
            or self.pre.stage != "PRE"
            or self.post.stage != "POST"
            or self.pre.request_sha256 != self.request_sha256
            or self.post.request_sha256 != self.request_sha256
            or self.pre.observations != self.post.observations
            or type(self.attempts) is not tuple
            or not 1 <= len(self.attempts) <= MAX_ATTEMPTS
            or tuple(item.attempt_number for item in self.attempts)
            != tuple(range(1, len(self.attempts) + 1))
            or any(item.request_sha256 != self.request_sha256 for item in self.attempts)
            or self.status not in {"SUCCESS", "FAILURE"}
            or type(self.eligible_phases) is not tuple
            or len(self.eligible_phases) != 131
            or self.eligible_phases != tuple(sorted(self.eligible_phases))
            or _phase_digest(self.eligible_phases)
            != "facf84563f444d5bdca2d16f22689a2e8dd6bc6a331d7f188dfcf4d8f2ed91b4"
        ):
            _fail("result chain invalid")
        for attempt in self.attempts:
            attempt._validate()
        if len(self.attempts) == 2 and self.attempts[0].failure_code not in RETRY_CODES:
            _fail("retry reason invalid")
        if len(self.attempts) == 2 and self.attempts[0].matched_valid_response:
            _fail("retry after valid response invalid")
        response: dict[str, Any] | None = None
        if self.worker_response_json is not None:
            response = _parse_worker_response(
                self.worker_response_json.encode("ascii") + b"\n",
                self.request_sha256,
                self.eligible_phases,
            )
        if response is not None and response["status"] == "SUCCESS":
            if (
                response.get("profile_id") != self.profile_id
                or response.get("temperature_k") != self.temperature_k
                or _number_rows(
                    response.get("nominal_mass_fractions"), MASS_ORDER
                ) != self.mass_fractions
            ):
                _fail("worker response request binding invalid")
        if (
            response is not None
            and "solver_component_axis" in response
            and tuple(response["solver_component_axis"])
            != _solver_components_for_mass(self.mass_fractions)
        ):
            _fail("worker response component projection binding invalid")
        if self.status == "SUCCESS":
            if (
                self.failure_code is not None
                or response is None
                or response["status"] != "SUCCESS"
                or self.attempts[-1].status != "SUCCESS"
            ):
                _fail("success result inconsistent")
        else:
            if (
                self.failure_code
                not in CONTROLLER_FAILURE_CODES | ALLOWED_WORKER_FAILURE_CODES
                or self.attempts[-1].status != "FAILURE"
            ):
                _fail("failure result inconsistent")
            if (
                response is not None
                and response["status"] != "FAILURE"
                and self.failure_code
                not in {
                    "FE_EQ_WORKER_TRANSPORT_AFTER_VALID_RESPONSE",
                    "FE_EQ_CONTROLLER_CLEANUP_FAILED",
                }
            ):
                _fail("failure response inconsistent")
        return response

    def __post_init__(self) -> None:
        self._validate()

    def as_dict(self) -> dict[str, Any]:
        response = self._validate()
        attempt_execution_states = tuple(
            item.real_equilibrium_execution_status for item in self.attempts
        )
        has_unknown = (
            "UNKNOWN_AFTER_TRANSPORT_OR_CONTAINMENT_FAILURE"
            in attempt_execution_states
        )
        if "CONFIRMED_EXECUTED" in attempt_execution_states:
            execution_status = (
                "CONFIRMED_AT_LEAST_ONE_EXECUTION_WITH_UNKNOWN_OTHER_ATTEMPT"
                if has_unknown
                else "CONFIRMED_EXECUTED"
            )
            real_executed = True
        elif has_unknown:
            execution_status = "UNKNOWN_ACROSS_ONE_OR_MORE_ATTEMPTS"
            real_executed = None
        else:
            execution_status = "CONFIRMED_NOT_INVOKED"
            real_executed = False
        payload = {
            "schema_version": "SWR-NE04-FE-EQUILIBRIUM-WITNESS-RESULT-2",
            "status": self.status,
            "failure_code": self.failure_code,
            "profile_id": self.profile_id,
            "temperature_k": self.temperature_k,
            "pressure_pa": PRESSURE_PA,
            "pressure_domain_status": "UNKNOWN_BLOCKED",
            "mass_fractions": [list(row) for row in self.mass_fractions],
            "request_sha256": self.request_sha256,
            "pre": self.pre.as_dict(),
            "post": self.post.as_dict(),
            "attempts": [item.as_dict() for item in self.attempts],
            "worker_response": response,
            "real_equilibrium_executed": real_executed,
            "real_equilibrium_execution_status": execution_status,
            "confirmed_executed_attempt_count": attempt_execution_states.count(
                "CONFIRMED_EXECUTED"
            ),
            "scientific_api_invocation_count": (
                None
                if has_unknown
                else attempt_execution_states.count("CONFIRMED_EXECUTED")
            ),
            "validation_status": (
                "STRUCTURALLY_AND_NUMERICALLY_VALIDATED"
                if self.status == "SUCCESS"
                else None
            ),
            "expected_phase_claim": None,
            "physics_claim": None,
            "raw_xarray_included": False,
            "path_included": False,
            "stderr_included": False,
            "limitations": [
                *(
                    list(response["limitations"])
                    if response is not None
                    else [
                        "CONVERGENCE_STATUS_NOT_EXPORTED",
                        "PRESSURE_DOMAIN_UNKNOWN_BLOCKED",
                        "NOT_NE04_ACCEPTANCE",
                        "NOT_RELEASE_AUTHORIZATION",
                    ]
                ),
                *(
                    []
                    if response is not None
                    and "NO_EXPECTED_PHASE_OR_PHYSICS_CLAIM"
                    in response["limitations"]
                    else ["NO_EXPECTED_PHASE_OR_PHYSICS_CLAIM"]
                ),
                *(
                    ["EXECUTION_STATUS_UNKNOWN_FOR_ONE_OR_MORE_ATTEMPTS"]
                    if has_unknown
                    else []
                ),
            ],
        }
        return {
            **payload,
            "claim": CLAIM,
            "acceptance": False,
            "counts_toward_ne04_acceptance": False,
            "execution_eligible": False,
            "execution_eligible_semantic": "NOT_RELEASE_OR_PRODUCT_ELIGIBILITY",
            "local_diagnostic_execution_capable": True,
            "local_diagnostic_execution_permitted": "ONLY_EXACT_BOUNDED_S2_WORKER",
            "release_eligible": False,
            "production_use": "DENIED",
        }


def _card(role: str, relative: str, value: object) -> _FileCard:
    if type(value) is not dict or set(value) != {"bytes", "sha256"}:
        _fail("file card invalid")
    return _FileCard(role, relative, value["bytes"], value["sha256"])


def _path_card(role: str, value: object) -> _FileCard:
    if type(value) is not dict or set(value) != {"relative_path", "bytes", "sha256"}:
        _fail("path card invalid")
    return _FileCard(role, value["relative_path"], value["bytes"], value["sha256"])


def _phase_digest(phases: tuple[str, ...]) -> str:
    return hashlib.sha256(
        "".join(f"{phase}\n" for phase in phases).encode("utf-8")
    ).hexdigest()


def _load_contract(root: Path) -> _Contract:
    config_path = _resolve_pinned(root, CONFIG_RELATIVE_PATH)
    payload, size, digest = _read_stable(config_path)
    if size != CONFIG_BYTES or digest != CONFIG_SHA256:
        _fail("config identity mismatch")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise _ContractFailure("config strict JSON invalid") from error
    if (
        type(value) is not dict
        or value.get("schema_version") != CONFIG_SCHEMA
        or value.get("stage") != "S2-CODE-A"
        or value.get("claim") != CLAIM
        or value.get("acceptance") is not False
        or value.get("counts_toward_ne04_acceptance") is not False
        or value.get("execution_eligible") is not False
        or value.get("execution_eligible_semantic")
        != "NOT_RELEASE_OR_PRODUCT_ELIGIBILITY"
        or value.get("local_diagnostic_execution_capable") is not True
        or value.get("local_diagnostic_execution_permitted")
        != "ONLY_EXACT_BOUNDED_S2_WORKER"
        or value.get("release_eligible") is not False
        or value.get("production_use") != "DENIED"
        or value.get("pressure_domain_status") != "UNKNOWN_BLOCKED"
        or value.get("product_ui_connected") is not False
        or value.get("real_equilibrium_executed_in_code_stage") is not False
    ):
        _fail("config safety invalid")
    anchor = value.get("s1_external_anchor")
    if (
        type(anchor) is not dict
        or anchor.get("anchor_id") != "NE04_FE_S1_R2_20260827T125427Z"
        or anchor.get("anchor_json_sha256")
        != "f20b5a0ca903e6b7bb5f923aedfd30ae6782996d116e70a4ae5d5e9a638b6de9"
        or anchor.get("external_path_is_runtime_dependency") is not False
    ):
        _fail("S1 anchor pin invalid")
    request = value.get("request_contract")
    process = value.get("process_contract")
    protocol = value.get("worker_protocol")
    success = value.get("success_contract")
    if (
        type(request) is not dict
        or request.get("public_api_parameters")
        != ["profile_id", "mass_fractions", "temperature_k"]
        or tuple(request.get("mass_fraction_elements", ())) != MASS_ORDER
        or tuple(request.get("full_inventory_filter_components", ()))
        != FULL_SOLVER_COMPONENTS
        or request.get("solver_component_projection")
        != {
            "algorithm": COMPONENT_PROJECTION_ALGORITHM,
            "source": "NORMALIZED_PUBLIC_25_MASS_ROWS",
            "active_non_fe_rule": "STRICTLY_GREATER_THAN_ZERO",
            "ordering": "MASS_ORDER_FILTERED_THEN_FE_VA",
            "zero_sign_normalization": "PLUS_ZERO_BEFORE_HASH_PROJECTION_AND_RECEIPT",
            "caller_selectable": False,
        }
        or request.get("strict_upper_bounds_wt_percent")
        != STRICT_UPPER_BOUNDS_WT_PERCENT
        or request.get("strict_upper_operator") != "<"
        or request.get("fraction_sum_absolute_tolerance") != 1e-12
        or request.get("pressure_pa")
        != {
            "value": PRESSURE_PA,
            "arbitrary_input_allowed": False,
            "domain_status": "UNKNOWN_BLOCKED",
        }
        or request.get("solver_options")
        != {
            "pdens": PDENS,
            "arbitrary_input_allowed": False,
            "semantic": "LOW_RESOLUTION_LOCAL_NUMERICAL_DIAGNOSTIC_NOT_SOURCE_DOMAIN_CLAIM",
        }
    ):
        _fail("request contract invalid")
    selection = request.get("phase_selection")
    if type(selection) is not dict:
        _fail("phase selection invalid")
    phases = tuple(selection.get("phases", ()))
    if (
        len(phases) != 131
        or selection.get("policy")
        != "FROZEN_131_CANDIDATES_THEN_ACTIVE_COMPONENT_FILTER"
        or selection.get("active_projection_algorithm")
        != PHASE_PROJECTION_ALGORITHM
        or phases != tuple(sorted(phases))
        or len(set(phases)) != len(phases)
        or _phase_digest(phases)
        != "facf84563f444d5bdca2d16f22689a2e8dd6bc6a331d7f188dfcf4d8f2ed91b4"
        or "C15_LAVES" not in phases
        or "LIQUID" not in phases
        or "BCC_A2" in phases
    ):
        _fail("phase inventory invalid")
    if (
        type(protocol) is not dict
        or protocol.get("request_schema") != REQUEST_SCHEMA
        or protocol.get("response_schema") != RESPONSE_SCHEMA
        or protocol.get("approved_scientific_api") != "pycalphad.equilibrium"
        or protocol.get("approved_scientific_api_calls_per_worker") != 1
        or protocol.get("max_input_bytes") != MAX_INPUT_BYTES
        or protocol.get("max_stdout_bytes") != MAX_STDOUT_BYTES
        or protocol.get("max_stderr_tail_bytes") != MAX_STDERR_TAIL_BYTES
        or protocol.get("max_raw_result_rows") != MAX_RAW_ROWS
        or protocol.get("submitted_non_fe_x_count_minimum") != 0
        or protocol.get("submitted_non_fe_x_count_maximum") != 24
        or protocol.get("submitted_non_fe_x_exactly_matches_active_non_fe")
        is not True
        or protocol.get("submitted_non_fe_x_includes_nominal_zeros") is not False
        or protocol.get("workspace_effective_x_floor") != ZERO_FLOOR
        or protocol.get("workspace_effective_x_floor_semantic")
        != "ACTIVE_POSITIVE_ONLY_PINNED_PYCALPHAD_0_11_2_RUNTIME_POLICY"
        or protocol.get("inactive_exact_zero_remains_exact_zero") is not True
        or protocol.get("convergence_status") != "NOT_EXPORTED_BY_DATASET"
        or protocol.get("scientific_failure_diagnostic")
        != {
            "applies_only_to_failure_code": "FE_EQ_WORKER_SCIENTIFIC_API_FAILED",
            "stage": SCIENTIFIC_FAILURE_STAGE,
            "scientific_api_invocation_count": 1,
            "dataset_returned": False,
            "exception_chain_maximum_items": SCIENTIFIC_FAILURE_CHAIN_LIMIT,
            "exception_chain_policy": "CAUSE_ELSE_CONTEXT_ID_CYCLE_GUARD",
            "category_allowlist": [
                "MEMORY_ALLOCATION",
                "MODEL_CONSTRUCTION",
                "CONDITION_CONTRACT",
                "SOLVER_FAILURE",
                "OTHER",
            ],
            "exception_token_allowlist": [
                "MEMORY_ERROR",
                "PYCALPHAD_DOF_ERROR",
                "PYCALPHAD_CONDITION_ERROR",
                "PYCALPHAD_EQUILIBRIUM_ERROR",
                "NUMPY_LINALG_ERROR",
                "OTHER",
            ],
            "classification_precedence": [
                "MEMORY_ERROR",
                "PYCALPHAD_DOF_ERROR",
                "PYCALPHAD_CONDITION_ERROR",
                "PYCALPHAD_EQUILIBRIUM_ERROR",
                "NUMPY_LINALG_ERROR",
                "OTHER",
            ],
            "unknown_exception_collapses_to": "OTHER",
            "fingerprint_algorithm": "SHA256_CANONICAL_ASCII_JSON",
            "fingerprint_payload_keys": [
                "stage",
                "category",
                "exception_tokens",
            ],
            "raw_exception_included": False,
            "path_included": False,
            "forbidden_exception_observations": [
                "CLASS_NAME_OR_MODULE_OUTSIDE_ALLOWLIST",
                "STR",
                "REPR",
                "ARGS",
                "MESSAGE",
                "TRACEBACK",
                "PATH",
            ],
            "required_limitation": "DIAGNOSTIC_MESSAGE_REDACTED",
        }
    ):
        _fail("worker protocol invalid")
    if (
        type(process) is not dict
        or process.get("cross_process_lock_id") != MUTEX_NAME
        or process.get("cross_process_lock_wait_milliseconds") != 0
        or process.get("scientific_processes_must_be_serial") is not True
        or process.get("popen_fallback_allowed") is not False
        or process.get("timeout_seconds_per_attempt") != TIMEOUT_SECONDS
        or process.get("tree_rss_limit_bytes") != TREE_RSS_LIMIT_BYTES
        or process.get("resource_poll_interval_seconds") != POLL_SECONDS
        or process.get("max_attempts") != MAX_ATTEMPTS
        or set(process.get("retry_only_failure_codes", ())) != RETRY_CODES
        or process.get("timeout_retry_allowed") is not False
        or process.get("retry_scope_mutation_allowed") is not False
        or process.get("process_tree_termination_required") is not True
        or process.get("assign_job_before_resume") is not True
        or process.get("rss_monitor_required") is not True
        or process.get("worker_private_directory_sddl")
        != PRIVATE_DIRECTORY_SDDL
        or process.get("worker_private_directory_components")
        != ["ThermoGar", "S2", "run-*", "pycache"]
        or process.get("worker_private_directory_creation")
        != "CREATEDIRECTORYW_SECURITY_ATTRIBUTES_FULL_SELF_RELATIVE_PROTECTED_DESCRIPTOR"
        or process.get("worker_existing_directory_policy")
        != "READ_ONLY_HANDLE_REPARSE_IDENTITY_FINAL_PATH_AND_EXACT_DACL_OR_FAIL_CLOSED"
        or process.get("worker_private_dacl_mismatch_policy")
        != "BLOCK_BEFORE_ENV_LOCK_PIPE_PROCESS_OR_RESUME"
        or process.get("private_containment_diagnostics")
        != "PRIVATE_OPERATION_AND_IMMEDIATE_WIN32_CODE_PUBLIC_FIXED_REDACTED_CODE"
    ):
        _fail("process contract invalid")
    if (
        type(success) is not dict
        or success.get("component_bulk_balance_against_runtime_effective_vector_absolute_tolerance")
        != BALANCE_TOLERANCE
        or success.get("phase_fraction_sum_absolute_tolerance")
        != BALANCE_TOLERANCE
        or success.get("expected_phase_claim_allowed") is not False
        or success.get("physics_claim_allowed") is not False
        or success.get("raw_xarray_allowed_in_public_output") is not False
        or success.get("path_allowed_in_public_output") is not False
        or success.get("raw_active_vertex_rows_allowed_in_public_output") is not False
        or success.get("terminal_phase_rows_sorted_and_unique") is not True
        or success.get("max_projected_phase_rows") != 131
        or success.get("solver_component_axis_dynamic_exact") is not True
        or success.get("dataset_nonvacant_component_axis_dynamic_exact") is not True
        or success.get("projected_active_phase_list_count_sha_algorithm_required")
        is not True
        or success.get("dataset_nonvacant_component_axis_exact_projected_once")
        is not True
    ):
        _fail("success contract invalid")

    cards: list[_FileCard] = [
        _FileCard("s2_config", CONFIG_RELATIVE_PATH, CONFIG_BYTES, CONFIG_SHA256),
        _FileCard("s2_worker", WORKER_RELATIVE_PATH, WORKER_BYTES, WORKER_SHA256),
    ]
    frozen = anchor.get("frozen_s1_subjects")
    if type(frozen) is not dict or len(frozen) != 6:
        _fail("frozen S1 subjects invalid")
    cards.extend(
        _card(f"s1_{index}", relative, card)
        for index, (relative, card) in enumerate(frozen.items(), start=1)
    )
    profiles = value.get("runtime_profiles")
    if type(profiles) is not dict or tuple(profiles) != PROFILE_KEYS:
        _fail("runtime profiles invalid")
    profile_cards = tuple(
        _path_card(f"runtime_{profile}", {
            key: profiles[profile][key]
            for key in ("relative_path", "bytes", "sha256")
        })
        for profile in PROFILE_KEYS
    )
    cards.extend(profile_cards)
    pinned = value.get("pinned_inputs")
    expected_pins = (
        "source",
        "equilibrium_core",
        "numerical_grid_dependency",
        "worker_python",
        "pycalphad_workspace_policy",
        "pycalphad_equilibrium_api",
        "pycalphad_solver",
        "pycalphad_utils_filter",
    )
    if type(pinned) is not dict or tuple(pinned) != expected_pins:
        _fail("pinned input roles invalid")
    pin_cards = tuple(_path_card(role, pinned[role]) for role in expected_pins)
    cards.extend(pin_cards)
    contract = _Contract(
        value=value,
        cards=tuple(cards),
        eligible_phases=phases,
        profile_cards=profile_cards,
        worker_python=next(card for card in pin_cards if card.role == "worker_python"),
    )
    _observe_cards(root, contract.cards)
    dependencies = value.get("runtime_dependencies")
    if (
        type(dependencies) is not dict
        or dependencies.get("python_major_minor") != "3.11"
        or dependencies.get("python_architecture") != "64bit"
        or dependencies.get("pycalphad_version") != "0.11.2"
        or dependencies.get("psutil_version") != "7.2.2"
    ):
        _fail("runtime dependency contract invalid")
    return contract


def _observe_card(root: Path, card: _FileCard) -> InputObservation:
    path = _resolve_pinned(root, card.relative_path)
    _payload, size, digest = _read_stable(path)
    if size != card.size_bytes or digest != card.sha256:
        _fail("pinned input identity mismatch")
    return InputObservation(card.role, size, digest)


def _observe_cards(root: Path, cards: tuple[_FileCard, ...]) -> tuple[InputObservation, ...]:
    observations = tuple(_observe_card(root, card) for card in cards)
    if len({card.relative_path for card in cards}) != len(cards):
        _fail("duplicate pinned paths")
    return observations


def _validate_mass_tuple(
    value: object,
) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple or len(value) != 25:
        _fail("mass tuple invalid")
    result: list[tuple[str, float]] = []
    for expected, row in zip(MASS_ORDER, value):
        if type(row) is not tuple or len(row) != 2 or row[0] != expected:
            _fail("mass tuple invalid")
        raw = row[1]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            _fail("mass tuple invalid")
        number = float(raw)
        if not math.isfinite(number) or number < 0.0:
            _fail("mass tuple invalid")
        result.append((expected, 0.0 if number == 0.0 else number))
    canonical = tuple(result)
    values = dict(canonical)
    if abs(math.fsum(values.values()) - 1.0) > 1e-12 or values["FE"] <= 0.0:
        _fail("mass tuple invalid")
    for element, upper in STRICT_UPPER_BOUNDS_WT_PERCENT.items():
        if values[element] >= upper * 0.01:
            _fail("mass tuple invalid")
    return canonical


def _solver_components_for_mass(
    mass: tuple[tuple[str, float], ...],
) -> tuple[str, ...]:
    values = dict(mass)
    active_non_fe = tuple(
        element for element in NON_FE_ORDER if values[element] > 0.0
    )
    return (*active_non_fe, "FE", "VA")


def _canonical_mass_mapping(value: object) -> tuple[tuple[str, float], ...]:
    if not isinstance(value, Mapping):
        _fail("mass mapping invalid")
    try:
        keys = tuple(value.keys())
    except Exception as error:
        raise _ContractFailure("mass mapping invalid") from error
    if len(keys) != 25 or any(type(key) is not str for key in keys) or set(keys) != set(MASS_ORDER):
        _fail("mass mapping invalid")
    rows: list[tuple[str, float]] = []
    for element in MASS_ORDER:
        try:
            raw = value[element]
        except Exception as error:
            raise _ContractFailure("mass mapping invalid") from error
        rows.append((element, raw))
    return _validate_mass_tuple(tuple(rows))


def _runtime_bytes(root: Path, contract: _Contract, profile_id: str) -> bytes:
    matches = [card for card in contract.profile_cards if card.role == f"runtime_{profile_id}"]
    if len(matches) != 1:
        _fail("runtime profile missing")
    path = _resolve_pinned(root, matches[0].relative_path)
    payload, size, digest = _read_stable(path)
    if size != matches[0].size_bytes or digest != matches[0].sha256:
        _fail("runtime profile identity mismatch")
    return payload


def _worker_request(
    contract: _Contract,
    profile_id: str,
    mass: tuple[tuple[str, float], ...],
    temperature: float,
    runtime_bytes: bytes,
) -> tuple[dict[str, Any], bytes, str]:
    profile_card = next(
        card for card in contract.profile_cards if card.role == f"runtime_{profile_id}"
    )
    solver_components = _solver_components_for_mass(mass)
    body: dict[str, Any] = {
        "schema_version": REQUEST_SCHEMA,
        "profile_id": profile_id,
        "runtime_size_bytes": profile_card.size_bytes,
        "runtime_sha256": profile_card.sha256,
        "runtime_base64": base64.b64encode(runtime_bytes).decode("ascii"),
        "mass_fractions": [list(row) for row in mass],
        "temperature_k": temperature,
        "pressure_pa": PRESSURE_PA,
        "solver_components": list(solver_components),
        "solver_component_count": len(solver_components),
        "solver_component_sha256": _phase_digest(solver_components),
        "component_projection_algorithm": COMPONENT_PROJECTION_ALGORITHM,
        "eligible_phases": list(contract.eligible_phases),
        "eligible_phase_sha256": (
            "facf84563f444d5bdca2d16f22689a2e8dd6bc6a331d7f188dfcf4d8f2ed91b4"
        ),
        "pdens": PDENS,
        "atomic_mass_sha256": (
            "b1d3ab2a3c238c00654e32aadce6c14e22af3434349c00e354ef729d8f4014a2"
        ),
        "workspace_effective_x_floor": ZERO_FLOOR,
    }
    request_id = _digest(body)
    request = {**body, "request_id": request_id}
    request_bytes = _canonical_bytes(request)
    if len(request_bytes) > MAX_INPUT_BYTES:
        _fail("worker request exceeds input cap")
    return request, request_bytes, request_id


def _parse_worker_response(
    payload: bytes,
    request_id: str,
    eligible_phases: tuple[str, ...],
) -> dict[str, Any]:
    if (
        not payload
        or len(payload) > MAX_STDOUT_BYTES
        or not payload.endswith(b"\n")
        or payload.count(b"\n") != 1
    ):
        _fail("worker response framing invalid")
    raw = payload[:-1]
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise _ContractFailure("worker response JSON invalid") from error
    if type(value) is not dict or _canonical_bytes(value) != raw:
        _fail("worker response not canonical")
    safety = {
        "schema_version": RESPONSE_SCHEMA,
        "claim": CLAIM,
        "acceptance": False,
        "counts_toward_ne04_acceptance": False,
        "execution_eligible": False,
        "execution_eligible_semantic": "NOT_RELEASE_OR_PRODUCT_ELIGIBILITY",
        "local_diagnostic_execution_capable": True,
        "local_diagnostic_execution_permitted": "ONLY_EXACT_BOUNDED_S2_WORKER",
        "release_eligible": False,
        "production_use": "DENIED",
        "pressure_domain_status": "UNKNOWN_BLOCKED",
    }
    if any(value.get(key) != expected for key, expected in safety.items()):
        _fail("worker response safety invalid")
    if value.get("request_id") != request_id or value.get("status") not in {"SUCCESS", "FAILURE"}:
        _fail("worker response identity invalid")
    if value["status"] == "FAILURE":
        failure_keys = {
            "schema_version", "claim", "acceptance",
            "counts_toward_ne04_acceptance", "execution_eligible",
            "execution_eligible_semantic", "local_diagnostic_execution_capable",
            "local_diagnostic_execution_permitted", "release_eligible",
            "production_use", "pressure_domain_status", "status", "failure_code",
            "request_id", "real_equilibrium_executed", "raw_exception_included",
            "path_included", "convergence_status", "limitations",
        }
        scientific_failure_keys = {
            "scientific_failure_stage",
            "scientific_api_invocation_count",
            "dataset_returned",
            "scientific_failure_category",
            "scientific_exception_tokens",
            "scientific_failure_fingerprint_sha256",
            "solver_component_axis",
            "solver_component_count",
            "solver_component_sha256",
            "component_projection_algorithm",
            "projected_active_phases",
            "projected_active_phase_count",
            "projected_active_phase_sha256",
            "phase_projection_algorithm",
        }
        failure_code = value.get("failure_code")
        is_scientific_failure = (
            failure_code == "FE_EQ_WORKER_SCIENTIFIC_API_FAILED"
        )
        expected_keys = failure_keys | (
            scientific_failure_keys if is_scientific_failure else set()
        )
        tokens = value.get("scientific_exception_tokens")
        category = value.get("scientific_failure_category")
        diagnostic_valid = (
            is_scientific_failure
            and value.get("scientific_failure_stage") == SCIENTIFIC_FAILURE_STAGE
            and type(value.get("scientific_api_invocation_count")) is int
            and value.get("scientific_api_invocation_count") == 1
            and value.get("dataset_returned") is False
            and type(category) is str
            and category in SCIENTIFIC_FAILURE_CATEGORIES
            and type(tokens) is list
            and 1 <= len(tokens) <= SCIENTIFIC_FAILURE_CHAIN_LIMIT
            and all(
                type(token) is str and token in SCIENTIFIC_EXCEPTION_TOKENS
                for token in tokens
            )
            and value.get("scientific_failure_fingerprint_sha256")
            == _digest(
                {
                    "stage": SCIENTIFIC_FAILURE_STAGE,
                    "category": category,
                    "exception_tokens": tokens,
                }
            )
            and _validate_projection_response(value, eligible_phases) is not None
            and value.get("real_equilibrium_executed") is True
            and value.get("limitations")
            == [
                "CONVERGENCE_STATUS_NOT_EXPORTED",
                "DIAGNOSTIC_MESSAGE_REDACTED",
                "PRESSURE_DOMAIN_UNKNOWN_BLOCKED",
                "NOT_NE04_ACCEPTANCE",
                "NOT_RELEASE_AUTHORIZATION",
            ]
        )
        ordinary_failure_valid = (
            not is_scientific_failure
            and type(value.get("real_equilibrium_executed")) is bool
            and value.get("limitations")
            == [
                "CONVERGENCE_STATUS_NOT_EXPORTED",
                "PRESSURE_DOMAIN_UNKNOWN_BLOCKED",
                "NOT_NE04_ACCEPTANCE",
                "NOT_RELEASE_AUTHORIZATION",
            ]
        )
        if (
            set(value) != expected_keys
            or failure_code not in ALLOWED_WORKER_FAILURE_CODES
            or value.get("raw_exception_included") is not False
            or value.get("path_included") is not False
            or value.get("convergence_status") != "NOT_EXPORTED_BY_DATASET"
            or not (diagnostic_valid or ordinary_failure_valid)
        ):
            _fail("worker failure response invalid")
        return value
    _validate_success_response(value, eligible_phases)
    return value


def _number_rows(value: object, order: tuple[str, ...]) -> tuple[tuple[str, float], ...]:
    if type(value) is not list or len(value) != len(order):
        _fail("response rows invalid")
    result: list[tuple[str, float]] = []
    for expected, row in zip(order, value):
        if type(row) is not list or len(row) != 2 or row[0] != expected:
            _fail("response rows invalid")
        raw = row[1]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            _fail("response rows invalid")
        number = float(raw)
        if not math.isfinite(number) or number < 0.0:
            _fail("response rows invalid")
        result.append((expected, 0.0 if number == 0.0 else number))
    return tuple(result)


def _validate_projection_response(
    value: dict[str, Any],
    eligible_phases: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    solver_raw = value.get("solver_component_axis")
    projected_raw = value.get("projected_active_phases")
    if (
        type(solver_raw) is not list
        or not 2 <= len(solver_raw) <= len(FULL_SOLVER_COMPONENTS)
        or any(type(item) is not str for item in solver_raw)
        or len(set(solver_raw)) != len(solver_raw)
        or solver_raw[-2:] != ["FE", "VA"]
    ):
        _fail("solver component projection invalid")
    solver = tuple(solver_raw)
    active_non_fe = solver[:-2]
    if (
        active_non_fe
        != tuple(element for element in NON_FE_ORDER if element in active_non_fe)
        or any(element not in NON_FE_ORDER for element in active_non_fe)
        or value.get("solver_component_count") != len(solver)
        or value.get("solver_component_sha256") != _phase_digest(solver)
        or value.get("component_projection_algorithm")
        != COMPONENT_PROJECTION_ALGORITHM
        or type(projected_raw) is not list
        or not 1 <= len(projected_raw) <= len(eligible_phases)
        or any(type(item) is not str for item in projected_raw)
    ):
        _fail("solver component projection invalid")
    projected = tuple(projected_raw)
    if (
        projected != tuple(sorted(set(projected)))
        or not set(projected).issubset(eligible_phases)
        or value.get("projected_active_phase_count") != len(projected)
        or value.get("projected_active_phase_sha256") != _phase_digest(projected)
        or value.get("phase_projection_algorithm") != PHASE_PROJECTION_ALGORITHM
    ):
        _fail("active phase projection invalid")
    return solver, projected


def _validate_success_response(
    value: dict[str, Any],
    eligible_phases: tuple[str, ...],
) -> None:
    expected_keys = {
        "schema_version", "claim", "acceptance", "counts_toward_ne04_acceptance",
        "execution_eligible", "execution_eligible_semantic",
        "local_diagnostic_execution_capable", "local_diagnostic_execution_permitted",
        "release_eligible", "production_use", "pressure_domain_status", "status",
        "failure_code", "request_id", "profile_id", "runtime_pre_sha256",
        "runtime_post_sha256", "temperature_k", "pressure_pa", "pdens",
        "scientific_api", "scientific_api_call_count", "real_equilibrium_executed",
        "validation_status", "nominal_mass_fractions", "atomic_masses",
        "nominal_mole_fractions", "submitted_non_fe_x", "workspace_effective_x_floor",
        "workspace_effective_x_ceiling", "upper_x_clamp_reachable_for_submitted_non_fe",
        "runtime_effective_mole_fractions", "max_nominal_to_effective_abs_delta",
        "round_trip_mass_fractions", "max_round_trip_abs_error",
        "raw_result_row_count", "raw_active_phase_row_count",
        "raw_active_phase_projection_sha256", "terminal_phase_row_count",
        "solver_component_axis", "solver_component_count",
        "solver_component_sha256", "component_projection_algorithm",
        "projected_active_phases", "projected_active_phase_count",
        "projected_active_phase_sha256", "phase_projection_algorithm",
        "dataset_nonvacant_component_axis", "dataset_nonvacant_component_count",
        "dataset_nonvacant_component_sha256", "dataset_vacancy_axis_present",
        "terminal_phase_rows", "aggregation_semantic",
        "raw_dataset_serialized", "phase_fraction_sum",
        "c15_scope_included", "c15_present_in_terminal_rows",
        "runtime_effective_bulk_mole_fractions", "component_bulk_absolute_residuals",
        "max_component_bulk_absolute_residual", "convergence_status",
        "expected_phase_claim", "physics_claim", "raw_xarray_included", "limitations",
    }
    profile_id = value.get("profile_id")
    if (
        set(value) != expected_keys
        or value.get("failure_code") is not None
        or value.get("real_equilibrium_executed") is not True
        or value.get("validation_status") != "STRUCTURALLY_AND_NUMERICALLY_VALIDATED"
        or profile_id not in PROFILE_KEYS
        or value.get("runtime_pre_sha256") != PROFILE_SHA256.get(profile_id)
        or value.get("runtime_post_sha256") != PROFILE_SHA256.get(profile_id)
        or value.get("scientific_api") != "pycalphad.equilibrium"
        or value.get("scientific_api_call_count") != 1
        or value.get("pressure_pa") != PRESSURE_PA
        or value.get("pdens") != PDENS
        or value.get("workspace_effective_x_floor") != ZERO_FLOOR
        or value.get("workspace_effective_x_ceiling") != 1.0 - ZERO_FLOOR
        or value.get("upper_x_clamp_reachable_for_submitted_non_fe") is not False
        or value.get("convergence_status") != "NOT_EXPORTED_BY_DATASET"
        or value.get("expected_phase_claim") is not None
        or value.get("physics_claim") is not None
        or value.get("raw_xarray_included") is not False
        or value.get("raw_dataset_serialized") is not False
        or value.get("aggregation_semantic")
        != "FRACTION_WEIGHTED_BY_EXACT_PHASE_NAME_NO_RAW_RENORMALIZATION"
        or type(value.get("c15_present_in_terminal_rows")) is not bool
    ):
        _fail("worker success envelope invalid")
    nominal_mass = _number_rows(value.get("nominal_mass_fractions"), MASS_ORDER)
    _validate_mass_tuple(nominal_mass)
    atomic = _number_rows(value.get("atomic_masses"), MASS_ORDER)
    if (
        any(number <= 0.0 for _element, number in atomic)
        or _digest([list(row) for row in atomic])
        != "b1d3ab2a3c238c00654e32aadce6c14e22af3434349c00e354ef729d8f4014a2"
    ):
        _fail("atomic mass response invalid")
    nominal_mole = _number_rows(value.get("nominal_mole_fractions"), MASS_ORDER)
    solver_components, projected_phases = _validate_projection_response(
        value, eligible_phases
    )
    if solver_components != _solver_components_for_mass(nominal_mass):
        _fail("success component projection binding invalid")
    active_non_fe = solver_components[:-2]
    inactive_non_fe = tuple(
        element for element in NON_FE_ORDER if element not in active_non_fe
    )
    submitted = _number_rows(value.get("submitted_non_fe_x"), active_non_fe)
    effective = _number_rows(value.get("runtime_effective_mole_fractions"), MASS_ORDER)
    round_trip = _number_rows(value.get("round_trip_mass_fractions"), MASS_ORDER)
    if (
        tuple((element, dict(nominal_mole)[element]) for element in active_non_fe)
        != submitted
        or abs(math.fsum(number for _element, number in nominal_mole) - 1.0) > 1e-12
        or abs(math.fsum(number for _element, number in effective) - 1.0) > 1e-12
        or any(
            abs(dict(round_trip)[element] - dict(nominal_mass)[element]) > 1e-12
            for element in MASS_ORDER
        )
        or any(dict(nominal_mole)[element] != 0.0 for element in inactive_non_fe)
        or any(dict(round_trip)[element] != 0.0 for element in inactive_non_fe)
    ):
        _fail("nominal/effective response invalid")
    nominal_map = dict(nominal_mole)
    expected_effective = {
        element: max(nominal_map[element], ZERO_FLOOR) for element in active_non_fe
    }
    expected_effective.update({element: 0.0 for element in inactive_non_fe})
    expected_effective["FE"] = 1.0 - math.fsum(expected_effective.values())
    if any(
        abs(dict(effective)[element] - expected_effective[element]) > 1e-15
        for element in MASS_ORDER
    ):
        _fail("effective zero-floor vector invalid")
    expected_delta = max(
        abs(nominal_map[element] - expected_effective[element])
        for element in MASS_ORDER
    )
    if value.get("max_nominal_to_effective_abs_delta") != expected_delta:
        _fail("zero-floor delta invalid")
    round_trip_error = max(
        abs(dict(round_trip)[element] - dict(nominal_mass)[element])
        for element in MASS_ORDER
    )
    if (
        not isinstance(value.get("max_round_trip_abs_error"), (int, float))
        or isinstance(value.get("max_round_trip_abs_error"), bool)
        or abs(float(value["max_round_trip_abs_error"]) - round_trip_error) > 1e-15
        or round_trip_error > 1e-12
    ):
        _fail("round-trip response invalid")
    component_axis = value.get("dataset_nonvacant_component_axis")
    canonical_nonvacant = (*active_non_fe, "FE")
    if (
        type(component_axis) is not list
        or tuple(component_axis) != canonical_nonvacant
        or value.get("dataset_nonvacant_component_count")
        != len(canonical_nonvacant)
        or value.get("dataset_nonvacant_component_sha256")
        != _phase_digest(canonical_nonvacant)
        or type(value.get("dataset_vacancy_axis_present")) is not bool
    ):
        _fail("component axis invalid")
    rows = value.get("terminal_phase_rows")
    raw_count = value.get("raw_result_row_count")
    active_count = value.get("raw_active_phase_row_count")
    projection_digest = value.get("raw_active_phase_projection_sha256")
    if (
        type(rows) is not list
        or not rows
        or len(rows) > 131
        or value.get("terminal_phase_row_count") != len(rows)
        or type(raw_count) is not int
        or type(active_count) is not int
        or not len(rows) <= active_count <= raw_count <= MAX_RAW_ROWS
        or type(projection_digest) is not str
        or len(projection_digest) != 64
        or any(character not in "0123456789abcdef" for character in projection_digest)
    ):
        _fail("phase row count invalid")
    names: set[str] = set()
    phase_sum = 0.0
    bulk = {element: 0.0 for element in MASS_ORDER}
    if (
        type(eligible_phases) is not tuple
        or len(eligible_phases) != 131
        or eligible_phases != tuple(sorted(eligible_phases))
        or _phase_digest(eligible_phases)
        != "facf84563f444d5bdca2d16f22689a2e8dd6bc6a331d7f188dfcf4d8f2ed91b4"
    ):
        _fail("eligible phase validator scope invalid")
    eligible = set(projected_phases)
    raw_vertex_total = 0
    ordered_names: list[str] = []
    for row in rows:
        if type(row) is not dict or set(row) != {
            "phase", "fraction", "chemical_coordinates", "vacancy_coordinate",
            "raw_vertex_count",
        }:
            _fail("phase row schema invalid")
        name = row["phase"]
        fraction = row["fraction"]
        coordinates = _number_rows(row["chemical_coordinates"], MASS_ORDER)
        vacancy = row["vacancy_coordinate"]
        if value["dataset_vacancy_axis_present"]:
            if (
                isinstance(vacancy, bool)
                or not isinstance(vacancy, (int, float))
                or not math.isfinite(float(vacancy))
                or float(vacancy) < 0.0
            ):
                _fail("vacancy coordinate invalid")
            vacancy_value = float(vacancy)
        else:
            if vacancy is not None:
                _fail("vacancy coordinate invalid")
            vacancy_value = 0.0
        if (
            type(name) is not str
            or name not in eligible
            or name in names
            or isinstance(fraction, bool)
            or not isinstance(fraction, (int, float))
            or not math.isfinite(float(fraction))
            or float(fraction) <= 0.0
            or type(row["raw_vertex_count"]) is not int
            or row["raw_vertex_count"] <= 0
            or abs(
                math.fsum(number for _element, number in coordinates)
                + vacancy_value
                - 1.0
            ) > BALANCE_TOLERANCE
            or any(dict(coordinates)[element] != 0.0 for element in inactive_non_fe)
        ):
            _fail("phase row values invalid")
        names.add(name)
        ordered_names.append(name)
        phase_sum += float(fraction)
        raw_vertex_total += row["raw_vertex_count"]
        for element, number in coordinates:
            bulk[element] += float(fraction) * number
    if (
        raw_vertex_total != active_count
        or ordered_names != sorted(ordered_names)
        or value.get("c15_present_in_terminal_rows")
        is not ("C15_LAVES" in names)
        or value.get("c15_scope_included")
        is not ("C15_LAVES" in projected_phases)
        or abs(phase_sum - 1.0) > BALANCE_TOLERANCE
        or abs(float(value.get("phase_fraction_sum")) - phase_sum) > 1e-15
    ):
        _fail("phase balance response invalid")
    maximum_residual = max(
        abs(bulk[element] - expected_effective[element]) for element in MASS_ORDER
    )
    reported_bulk = _number_rows(
        value.get("runtime_effective_bulk_mole_fractions"), MASS_ORDER
    )
    reported_residuals = _number_rows(
        value.get("component_bulk_absolute_residuals"), MASS_ORDER
    )
    if (
        maximum_residual > BALANCE_TOLERANCE
        or any(
            abs(dict(reported_bulk)[element] - bulk[element]) > 1e-15
            for element in MASS_ORDER
        )
        or any(dict(reported_bulk)[element] != 0.0 for element in inactive_non_fe)
        or any(
            dict(reported_residuals)[element] != 0.0
            for element in inactive_non_fe
        )
        or any(
            abs(dict(reported_residuals)[element]
                - abs(bulk[element] - expected_effective[element])) > 1e-15
            for element in MASS_ORDER
        )
        or abs(float(value.get("max_component_bulk_absolute_residual")) - maximum_residual)
        > 1e-15
        or value.get("limitations")
        != [
            (
                "NUMERICAL_ZERO_FLOOR_APPLIED"
                if expected_delta > 0.0
                else "NUMERICAL_ZERO_FLOOR_NOT_APPLIED_TO_THIS_REQUEST"
            ),
            "EXACT_ZERO_COMPONENTS_EXCLUDED_FROM_SOLVER_LOCAL_DIAGNOSTIC",
            "UPPER_X_CLAMP_UNREACHABLE_BY_EXPLICIT_SUBMISSION_GATE",
            "CONVERGENCE_STATUS_NOT_EXPORTED",
            "PRESSURE_DOMAIN_UNKNOWN_BLOCKED",
            "NOT_NE04_ACCEPTANCE",
            "NOT_RELEASE_AUTHORIZATION",
            "NO_EXPECTED_PHASE_OR_PHYSICS_CLAIM",
        ]
    ):
        _fail("bulk balance response invalid")


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", _STARTUPINFOW),
        ("lpAttributeList", wintypes.LPVOID),
    ]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _LARGE_INTEGER(ctypes.Union):
    _fields_ = [("QuadPart", ctypes.c_longlong)]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", _LARGE_INTEGER),
        ("PerJobUserTimeLimit", _LARGE_INTEGER),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _FILE_DISPOSITION_INFO(ctypes.Structure):
    _fields_ = [("DeleteFile", wintypes.BOOL)]


def _win_error(
    operation: str,
    win32_code: int | None = None,
) -> _ContainmentStageFailure:
    captured = ctypes.get_last_error() if win32_code is None else win32_code
    return _ContainmentStageFailure(operation, int(captured))


def _kernel32_api() -> Any:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle_pointer = ctypes.POINTER(wintypes.HANDLE)
    size_pointer = ctypes.POINTER(ctypes.c_size_t)

    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel32.ReleaseMutex.restype = wintypes.BOOL
    kernel32.CreatePipe.argtypes = [
        handle_pointer,
        handle_pointer,
        ctypes.POINTER(_SECURITY_ATTRIBUTES),
        wintypes.DWORD,
    ]
    kernel32.CreatePipe.restype = wintypes.BOOL
    kernel32.CreateDirectoryW.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(_SECURITY_ATTRIBUTES),
    ]
    kernel32.CreateDirectoryW.restype = wintypes.BOOL
    kernel32.GetFinalPathNameByHandleW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.SetHandleInformation.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel32.SetHandleInformation.restype = wintypes.BOOL
    kernel32.InitializeProcThreadAttributeList.argtypes = [
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        size_pointer,
    ]
    kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    kernel32.UpdateProcThreadAttribute.argtypes = [
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.c_size_t,
        wintypes.LPVOID,
        ctypes.c_size_t,
        wintypes.LPVOID,
        size_pointer,
    ]
    kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
    kernel32.DeleteProcThreadAttributeList.argtypes = [wintypes.LPVOID]
    kernel32.DeleteProcThreadAttributeList.restype = None
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPCWSTR,
        wintypes.LPVOID,
        ctypes.POINTER(_PROCESS_INFORMATION),
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.GetExitCodeProcess.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.SetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel32.SetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.LPVOID]
    kernel32.LocalFree.restype = wintypes.LPVOID
    return kernel32


def _advapi32_api() -> Any:
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    advapi32.GetSecurityInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.LPVOID),
    ]
    advapi32.GetSecurityInfo.restype = wintypes.DWORD
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL
    return advapi32


def _security_descriptor_sddl(
    advapi32: Any,
    kernel32: Any,
    descriptor: Any,
) -> str:
    output = wintypes.LPWSTR()
    length = wintypes.DWORD()
    if not advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
        descriptor,
        1,
        0x00000004,
        ctypes.byref(output),
        ctypes.byref(length),
    ):
        raise _win_error("ConvertSecurityDescriptorToStringSecurityDescriptorW")
    try:
        return str(output.value)
    finally:
        kernel32.LocalFree(ctypes.cast(output, wintypes.LPVOID))


def _new_private_security_descriptor(advapi32: Any) -> wintypes.LPVOID:
    descriptor = wintypes.LPVOID()
    descriptor_size = wintypes.DWORD()
    if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        PRIVATE_DIRECTORY_SDDL,
        1,
        ctypes.byref(descriptor),
        ctypes.byref(descriptor_size),
    ):
        raise _win_error(
            "ConvertStringSecurityDescriptorToSecurityDescriptorW.private_directory"
        )
    if not descriptor or descriptor_size.value == 0:
        raise _ContainmentStageFailure("private_descriptor_empty", None)
    return descriptor


def _private_handle_sddl(
    kernel32: Any,
    advapi32: Any,
    handle: Any,
) -> str:
    descriptor = wintypes.LPVOID()
    result = advapi32.GetSecurityInfo(
        handle,
        1,
        0x00000004,
        None,
        None,
        None,
        None,
        ctypes.byref(descriptor),
    )
    if result != 0 or not descriptor:
        raise _win_error(
            "GetSecurityInfo.private_directory",
            int(result),
        )
    try:
        return _security_descriptor_sddl(
            advapi32,
            kernel32,
            descriptor,
        )
    finally:
        kernel32.LocalFree(descriptor)


def _open_private_directory_security_handle(
    kernel32: Any,
    path: Path,
) -> Any:
    handle = kernel32.CreateFileW(
        str(path),
        0x00020000,
        0x00000001 | 0x00000002,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if not handle or _handle_value(handle) == invalid_handle:
        raise _win_error("CreateFileW.private_directory_security_handle")
    return handle


def _final_directory_path(kernel32: Any, handle: Any) -> str:
    required = kernel32.GetFinalPathNameByHandleW(handle, None, 0, 0)
    if required == 0:
        raise _win_error("GetFinalPathNameByHandleW.private_directory.size")
    buffer = ctypes.create_unicode_buffer(required + 1)
    written = kernel32.GetFinalPathNameByHandleW(
        handle,
        buffer,
        len(buffer),
        0,
    )
    if written == 0:
        raise _win_error("GetFinalPathNameByHandleW.private_directory.read")
    if written >= len(buffer):
        raise _ContainmentStageFailure(
            "GetFinalPathNameByHandleW.private_directory.unstable",
            None,
        )
    value = str(buffer.value)
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return os.path.normcase(os.path.normpath(os.path.abspath(value)))


def _expected_directory_path(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path.resolve(strict=True))))


def _verify_private_directory_handle_dacl(
    kernel32: Any,
    advapi32: Any,
    handle: Any,
    expected_sddl: str,
) -> None:
    actual_sddl = _private_handle_sddl(kernel32, advapi32, handle)
    if actual_sddl != expected_sddl:
        raise _ContainmentStageFailure("private_dacl_exact_readback", None)


def _verify_existing_private_directory(
    kernel32: Any,
    advapi32: Any,
    path: Path,
    expected_sddl: str,
) -> None:
    if not path.is_dir() or _path_chain_has_reparse(path):
        raise _ContainmentStageFailure("existing_private_directory_invalid", None)
    identity = _directory_identity(path)
    expected_path = _expected_directory_path(path)
    handle = _open_private_directory_security_handle(
        kernel32,
        path,
    )
    try:
        if _final_directory_path(kernel32, handle) != expected_path:
            raise _ContainmentStageFailure(
                "existing_private_directory_path_invalid",
                None,
            )
        if _private_handle_sddl(kernel32, advapi32, handle) != expected_sddl:
            raise _ContainmentStageFailure("existing_private_dacl_invalid", None)
        if _final_directory_path(kernel32, handle) != expected_path:
            raise _ContainmentStageFailure(
                "existing_private_directory_path_changed",
                None,
            )
    finally:
        _close_handle(kernel32, handle)
    if (
        not path.is_dir()
        or _path_chain_has_reparse(path)
        or _directory_identity(path) != identity
    ):
        raise _ContainmentStageFailure(
            "existing_private_directory_identity_changed",
            None,
        )


def _create_or_verify_private_directory(
    kernel32: Any,
    path: Path,
    *,
    allow_existing: bool,
    operation: str,
) -> bool:
    advapi32 = _advapi32_api()
    descriptor = _new_private_security_descriptor(advapi32)
    try:
        expected_sddl = _security_descriptor_sddl(
            advapi32,
            kernel32,
            descriptor,
        )
        security = _SECURITY_ATTRIBUTES(
            ctypes.sizeof(_SECURITY_ATTRIBUTES),
            descriptor,
            False,
        )
        ctypes.set_last_error(0)
        created = bool(kernel32.CreateDirectoryW(str(path), ctypes.byref(security)))
        create_code = ctypes.get_last_error()
        if not created:
            if create_code != 183 or not allow_existing:
                raise _win_error(f"CreateDirectoryW.{operation}", create_code)
            _verify_existing_private_directory(
                kernel32,
                advapi32,
                path,
                expected_sddl,
            )
            return False
        if not path.is_dir() or _path_chain_has_reparse(path):
            raise _ContainmentStageFailure(
                f"{operation}.new_directory_invalid",
                None,
            )
        handle = _open_private_directory_security_handle(
            kernel32,
            path,
        )
        try:
            _verify_private_directory_handle_dacl(
                kernel32,
                advapi32,
                handle,
                expected_sddl,
            )
        finally:
            _close_handle(kernel32, handle)
        return True
    finally:
        kernel32.LocalFree(descriptor)


def _close_handle(kernel32: Any, handle: Any) -> None:
    if handle:
        kernel32.CloseHandle(handle)


def _handle_value(handle: Any) -> int:
    raw = getattr(handle, "value", handle)
    if type(raw) is not int or raw <= 0:
        raise _ContractFailure("invalid Win32 handle")
    return raw


def _read_locked_file(file_object: Any) -> tuple[bytes, int, str]:
    try:
        file_object.seek(0)
        before = os.fstat(file_object.fileno())
        payload = file_object.read()
        after = os.fstat(file_object.fileno())
        file_object.seek(0)
    except Exception as error:
        raise _ContractFailure("locked code read failed") from error
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or len(payload) != after.st_size
    ):
        _fail("locked code identity changed")
    return payload, len(payload), hashlib.sha256(payload).hexdigest()


def _open_locked_code_file(
    kernel32: Any,
    root: Path,
    card: _FileCard,
) -> _LockedCodeFile:
    path = _resolve_pinned(root, card.relative_path)
    handle = kernel32.CreateFileW(
        str(path),
        0x80000000,  # GENERIC_READ
        0x00000001,  # FILE_SHARE_READ only: deny write/delete opens
        None,
        3,  # OPEN_EXISTING
        0x00000080 | 0x00200000,  # NORMAL | OPEN_REPARSE_POINT
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if not handle or _handle_value(handle) == invalid_handle:
        raise _ContractFailure("code read lock unavailable")
    descriptor: int | None = None
    file_object: Any = None
    try:
        descriptor = msvcrt.open_osfhandle(
            _handle_value(handle),
            os.O_RDONLY | os.O_BINARY,
        )
        handle = None
        file_object = os.fdopen(descriptor, "rb", buffering=0)
        descriptor = None
        payload, size, digest = _read_locked_file(file_object)
        del payload
        path_metadata = path.lstat()
        if (
            size != card.size_bytes
            or digest != card.sha256
            or _is_reparse(path)
            or not os.path.samestat(os.fstat(file_object.fileno()), path_metadata)
        ):
            file_object.close()
            _fail("locked code pin mismatch")
        return _LockedCodeFile(card.role, path, file_object)
    except Exception:
        if file_object is not None:
            try:
                file_object.close()
            except Exception:
                pass
        if descriptor is not None:
            os.close(descriptor)
        if handle:
            kernel32.CloseHandle(handle)
        raise


def _lock_executable_code(
    kernel32: Any,
    root: Path,
    contract: _Contract,
) -> tuple[_LockedCodeFile, ...]:
    roles = (
        "worker_python",
        "s2_worker",
        "equilibrium_core",
        "numerical_grid_dependency",
        "pycalphad_workspace_policy",
        "pycalphad_equilibrium_api",
        "pycalphad_solver",
        "pycalphad_utils_filter",
    )
    cards = {card.role: card for card in contract.cards}
    if set(roles) - set(cards):
        _fail("executable code cards missing")
    locked: list[_LockedCodeFile] = []
    try:
        for role in roles:
            locked.append(_open_locked_code_file(kernel32, root, cards[role]))
        return tuple(locked)
    except Exception:
        for item in locked:
            try:
                item.file_object.close()
            except Exception:
                pass
        raise


def _tree_rss_bytes(pid: int) -> int:
    try:
        import psutil
    except Exception as error:
        raise _ContractFailure("resource monitor unavailable") from error
    if getattr(psutil, "__version__", None) != "7.2.2":
        _fail("resource monitor version invalid")
    try:
        root = psutil.Process(pid)
        processes = [root, *root.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied) as error:
        raise _ContractFailure("resource monitor lost process") from error
    unique: dict[int, Any] = {process.pid: process for process in processes}
    total = 0
    for process in unique.values():
        try:
            total += int(process.memory_info().rss)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as error:
            raise _ContractFailure("resource monitor lost process") from error
    return total


def _path_chain_has_reparse(path: Path) -> bool:
    absolute = Path(os.path.abspath(path))
    chain = [absolute, *absolute.parents]
    return any(_is_reparse(item) for item in chain if item.exists())


def _directory_identity(path: Path) -> tuple[int, int]:
    metadata = path.lstat()
    return int(metadata.st_dev), int(metadata.st_ino)


def _private_worker_directory(
    kernel32: Any,
) -> tuple[Path, Path, tuple[int, int], Any]:
    try:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if type(local_app_data) is not str or not local_app_data:
            raise _ContractFailure("LOCALAPPDATA unavailable")
        local_root = Path(local_app_data)
        if (
            not local_root.is_absolute()
            or not local_root.is_dir()
            or _path_chain_has_reparse(local_root)
        ):
            raise _ContractFailure("LOCALAPPDATA invalid")
        fixed_root = local_root
        for name in ("ThermoGar", "S2"):
            fixed_root = fixed_root / name
            _create_or_verify_private_directory(
                kernel32,
                fixed_root,
                allow_existing=True,
                operation=f"private_root_{name}",
            )
            if not fixed_root.is_dir() or _path_chain_has_reparse(fixed_root):
                raise _ContractFailure("private root invalid")
        path = fixed_root / f"run-{secrets.token_hex(16)}"
        _create_or_verify_private_directory(
            kernel32,
            path,
            allow_existing=False,
            operation="private_worker_run",
        )
        if not path.is_dir() or _path_chain_has_reparse(path):
            raise _ContractFailure("private worker directory invalid")
        parent = path.parent.resolve(strict=True)
        if path.resolve(strict=True).parent != parent:
            raise _ContractFailure("private worker directory invalid")
        directory_handle = kernel32.CreateFileW(
            str(path),
            0x80000000 | 0x00010000,  # GENERIC_READ | DELETE
            0x00000001 | 0x00000002,  # SHARE_READ | SHARE_WRITE, deny delete
            None,
            3,
            0x02000000 | 0x00200000,  # BACKUP_SEMANTICS | OPEN_REPARSE_POINT
            None,
        )
        invalid_handle = ctypes.c_void_p(-1).value
        if not directory_handle or _handle_value(directory_handle) == invalid_handle:
            raise _ContractFailure("private directory anchor unavailable")
        return path, parent, _directory_identity(path), directory_handle
    except _ContractFailure:
        raise
    except Exception as error:
        raise _ContractFailure("private worker directory unavailable") from error


def _verify_private_worker_directory(
    path: Path,
    expected_parent: Path,
    expected_identity: tuple[int, int],
) -> None:
    try:
        if (
            not path.is_dir()
            or _path_chain_has_reparse(path)
            or path.resolve(strict=True).parent != expected_parent
            or _directory_identity(path) != expected_identity
        ):
            _fail("private worker directory identity changed")
    except _ContractFailure:
        raise
    except Exception as error:
        raise _ContractFailure("private worker directory invalid") from error


def _cleanup_private_worker_directory(
    kernel32: Any,
    path: Path,
    expected_parent: Path,
    expected_identity: tuple[int, int],
    directory_handle: Any,
) -> None:
    _verify_private_worker_directory(path, expected_parent, expected_identity)
    try:
        pycache = path / "pycache"
        if (
            not pycache.is_dir()
            or _path_chain_has_reparse(pycache)
            or any(pycache.iterdir())
        ):
            raise _ContractFailure("private pycache not empty after worker")
        pycache.rmdir()
        for entry in tuple(path.iterdir()):
            if _path_chain_has_reparse(entry) or not entry.is_file():
                raise _ContractFailure("unexpected private worker artifact")
            entry.unlink()
        if any(path.iterdir()):
            raise _ContractFailure("private worker directory not empty")
        disposition = _FILE_DISPOSITION_INFO(True)
        if not kernel32.SetFileInformationByHandle(
            directory_handle,
            4,
            ctypes.byref(disposition),
            ctypes.sizeof(disposition),
        ):
            raise _ContractFailure("anchored private directory delete failed")
    except _ContractFailure:
        raise
    except OSError as error:
        raise _ContractFailure("private worker directory cleanup failed") from error


def _minimal_environment_block(
    kernel32: Any,
    worker_directory: Path,
    project_root: Path,
) -> Any:
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
    if not system_root:
        _fail("system root unavailable")
    system_root_path = Path(system_root).resolve(strict=True)
    if _path_chain_has_reparse(system_root_path):
        _fail("system root invalid")
    pycache_directory = worker_directory / "pycache"
    try:
        _create_or_verify_private_directory(
            kernel32,
            pycache_directory,
            allow_existing=False,
            operation="private_worker_pycache",
        )
    except OSError as error:
        raise _ContractFailure("private pycache directory unavailable") from error
    if (
        _path_chain_has_reparse(pycache_directory)
        or any(pycache_directory.iterdir())
    ):
        _fail("private pycache directory invalid")
    environment = {
        "COMSPEC": str(system_root_path / "System32" / "cmd.exe"),
        "MPLCONFIGDIR": str(worker_directory),
        "PATH": str(system_root_path / "System32"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPYCACHEPREFIX": str(pycache_directory),
        "PYTHONUTF8": "1",
        "SYSTEMROOT": str(system_root_path),
        "TEMP": str(worker_directory),
        "TMP": str(worker_directory),
        "WINDIR": str(system_root_path),
    }
    project_text = str(project_root.resolve(strict=True)).casefold()
    if any(project_text in value.casefold() for value in environment.values()):
        _fail("project path leaked into worker environment")
    block = "\0".join(
        f"{key}={environment[key]}"
        for key in sorted(environment, key=str.casefold)
    ) + "\0\0"
    return ctypes.create_unicode_buffer(block)


@contextmanager
def _named_scientific_mutex() -> Iterator[None]:
    if os.name != "nt":
        raise EquilibriumWitnessError("FE_EQ_CONTROLLER_PLATFORM_UNSUPPORTED")
    kernel32 = _kernel32_api()
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        raise EquilibriumWitnessError("FE_EQ_CONTROLLER_MUTEX_UNAVAILABLE")
    acquired = False
    try:
        wait = kernel32.WaitForSingleObject(handle, 0)
        if wait == 0x00000102:
            raise EquilibriumWitnessError("FE_EQ_CONTROLLER_MUTEX_BUSY")
        if wait != 0x00000000:
            raise EquilibriumWitnessError("FE_EQ_CONTROLLER_MUTEX_UNAVAILABLE")
        acquired = True
        yield
    finally:
        if acquired:
            kernel32.ReleaseMutex(handle)
        kernel32.CloseHandle(handle)


def _spawn_win32_attempt(
    root: Path,
    contract: _Contract,
    request_bytes: bytes,
    request_sha256: str,
    attempt_number: int,
) -> _AttemptExecution:
    """Create one suspended, handle-whitelisted, job-contained worker."""

    if os.name != "nt":
        raise EquilibriumWitnessError("FE_EQ_CONTROLLER_PLATFORM_UNSUPPORTED")
    if len(request_bytes) > MAX_INPUT_BYTES:
        raise EquilibriumWitnessError("FE_EQ_CONTROLLER_REQUEST_INVALID")
    try:
        import psutil
    except Exception as error:
        raise EquilibriumWitnessError(
            "FE_EQ_CONTROLLER_RUNTIME_DEPENDENCY_INVALID"
        ) from error
    if getattr(psutil, "__version__", None) != "7.2.2":
        raise EquilibriumWitnessError("FE_EQ_CONTROLLER_RUNTIME_DEPENDENCY_INVALID")

    kernel32 = _kernel32_api()
    handles: list[Any] = []
    converted_files: list[Any] = []
    attribute_list = None
    job = None
    process_info = _PROCESS_INFORMATION()
    child_handles: list[Any] = []
    process_started = False
    process_tree_terminated = False
    worker_directory: Path | None = None
    worker_directory_parent: Path | None = None
    worker_directory_identity: tuple[int, int] | None = None
    worker_directory_handle: Any = None
    readers: tuple[threading.Thread, ...] = ()
    writer: threading.Thread | None = None
    locked_code_files: tuple[_LockedCodeFile, ...] = ()
    completed_execution: _AttemptExecution | None = None
    cleanup_failed = False
    try:
        (
            worker_directory,
            worker_directory_parent,
            worker_directory_identity,
            worker_directory_handle,
        ) = _private_worker_directory(kernel32)
        environment_buffer = _minimal_environment_block(
            kernel32,
            worker_directory,
            root,
        )
        locked_code_files = _lock_executable_code(kernel32, root, contract)
        security = _SECURITY_ATTRIBUTES(
            ctypes.sizeof(_SECURITY_ATTRIBUTES),
            None,
            True,
        )

        def make_pipe(parent_reads: bool) -> tuple[Any, Any]:
            read_handle = wintypes.HANDLE()
            write_handle = wintypes.HANDLE()
            if not kernel32.CreatePipe(
                ctypes.byref(read_handle),
                ctypes.byref(write_handle),
                ctypes.byref(security),
                0,
            ):
                raise _win_error("CreatePipe.worker_transport")
            parent = read_handle if parent_reads else write_handle
            child = write_handle if parent_reads else read_handle
            if not kernel32.SetHandleInformation(parent, 0x00000001, 0):
                raise _win_error("SetHandleInformation.worker_transport")
            handles.append(parent)
            child_handles.append(child)
            return parent, child

        parent_stdin, child_stdin = make_pipe(False)
        parent_stdout, child_stdout = make_pipe(True)
        parent_stderr, child_stderr = make_pipe(True)

        attribute_size = ctypes.c_size_t(0)
        kernel32.InitializeProcThreadAttributeList(
            None, 1, 0, ctypes.byref(attribute_size)
        )
        attribute_buffer = ctypes.create_string_buffer(attribute_size.value)
        attribute_list = ctypes.cast(attribute_buffer, wintypes.LPVOID)
        if not kernel32.InitializeProcThreadAttributeList(
            attribute_list, 1, 0, ctypes.byref(attribute_size)
        ):
            raise _win_error("InitializeProcThreadAttributeList.worker_handles")
        handle_array = (wintypes.HANDLE * 3)(
            child_stdin,
            child_stdout,
            child_stderr,
        )
        if not kernel32.UpdateProcThreadAttribute(
            attribute_list,
            0,
            0x00020002,
            ctypes.cast(handle_array, wintypes.LPVOID),
            ctypes.sizeof(handle_array),
            None,
            None,
        ):
            raise _win_error("UpdateProcThreadAttribute.worker_handles")

        startup = _STARTUPINFOEXW()
        startup.StartupInfo.cb = ctypes.sizeof(_STARTUPINFOEXW)
        startup.StartupInfo.dwFlags = 0x00000100
        startup.StartupInfo.hStdInput = child_stdin
        startup.StartupInfo.hStdOutput = child_stdout
        startup.StartupInfo.hStdError = child_stderr
        startup.lpAttributeList = attribute_list

        locked_by_role = {item.role: item for item in locked_code_files}
        python_path = locked_by_role["worker_python"].path
        worker_path = locked_by_role["s2_worker"].path
        command = subprocess.list2cmdline(
            [str(python_path), "-I", "-B", "-X", "utf8", str(worker_path)]
        )
        command_buffer = ctypes.create_unicode_buffer(command)
        creation_flags = (
            0x00000004  # CREATE_SUSPENDED
            | 0x00000200  # CREATE_NEW_PROCESS_GROUP
            | 0x00000400  # CREATE_UNICODE_ENVIRONMENT
            | 0x00080000  # EXTENDED_STARTUPINFO_PRESENT
            | 0x08000000  # CREATE_NO_WINDOW
        )
        _verify_private_worker_directory(
            worker_directory,
            worker_directory_parent,
            worker_directory_identity,
        )
        for item in locked_code_files:
            _payload, size, digest = _read_locked_file(item.file_object)
            card = next(card for card in contract.cards if card.role == item.role)
            if size != card.size_bytes or digest != card.sha256:
                _fail("executable code changed under read lock")
        if not kernel32.CreateProcessW(
            str(python_path),
            command_buffer,
            None,
            None,
            True,
            creation_flags,
            ctypes.cast(environment_buffer, wintypes.LPVOID),
            str(worker_directory),
            ctypes.byref(startup),
            ctypes.byref(process_info),
        ):
            raise _win_error("CreateProcessW.worker_suspended")
        process_started = True
        for handle in child_handles:
            kernel32.CloseHandle(handle)
        child_handles.clear()

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise _win_error("CreateJobObjectW.worker")
        limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags = 0x00002000 | 0x00000200
        limits.JobMemoryLimit = TREE_RSS_LIMIT_BYTES
        if not kernel32.SetInformationJobObject(
            job,
            9,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            raise _win_error("SetInformationJobObject.worker_limits")
        if not kernel32.AssignProcessToJobObject(job, process_info.hProcess):
            raise _win_error("AssignProcessToJobObject.worker")

        def adopt_parent_handle(handle: Any, flags: int, mode: str) -> Any:
            descriptor = msvcrt.open_osfhandle(_handle_value(handle), flags)
            handles[:] = [candidate for candidate in handles if candidate is not handle]
            try:
                file_object = os.fdopen(descriptor, mode, buffering=0)
            except Exception:
                os.close(descriptor)
                raise
            converted_files.append(file_object)
            return file_object

        stdin_file = adopt_parent_handle(
            parent_stdin,
            os.O_WRONLY | os.O_BINARY,
            "wb",
        )
        stdout_file = adopt_parent_handle(
            parent_stdout,
            os.O_RDONLY | os.O_BINARY,
            "rb",
        )
        stderr_file = adopt_parent_handle(
            parent_stderr,
            os.O_RDONLY | os.O_BINARY,
            "rb",
        )

        stdout_prefix = bytearray()
        stdout_total = 0
        stdout_hash = hashlib.sha256()
        stderr_tail: deque[int] = deque(maxlen=MAX_STDERR_TAIL_BYTES)
        stderr_total = 0
        stdout_overflow = threading.Event()
        pipe_broken = threading.Event()
        state_lock = threading.Lock()

        def stdout_reader() -> None:
            nonlocal stdout_total
            try:
                while True:
                    block = stdout_file.read(8192)
                    if not block:
                        return
                    with state_lock:
                        stdout_total += len(block)
                        stdout_hash.update(block)
                        remaining = max(0, MAX_STDOUT_BYTES - len(stdout_prefix))
                        if remaining:
                            stdout_prefix.extend(block[:remaining])
                        if stdout_total > MAX_STDOUT_BYTES:
                            stdout_overflow.set()
            except (OSError, ValueError):
                pipe_broken.set()

        def stderr_reader() -> None:
            nonlocal stderr_total
            try:
                while True:
                    block = stderr_file.read(8192)
                    if not block:
                        return
                    with state_lock:
                        stderr_total += len(block)
                        stderr_tail.extend(block)
            except (OSError, ValueError):
                pipe_broken.set()

        def stdin_writer() -> None:
            try:
                stdin_file.write(request_bytes)
            except (BrokenPipeError, OSError, ValueError):
                pipe_broken.set()
            finally:
                try:
                    stdin_file.close()
                except (OSError, ValueError):
                    pipe_broken.set()

        readers = (
            threading.Thread(target=stdout_reader, daemon=True),
            threading.Thread(target=stderr_reader, daemon=True),
        )
        for thread in readers:
            thread.start()
        writer = threading.Thread(target=stdin_writer, daemon=True)
        writer.start()
        if kernel32.ResumeThread(process_info.hThread) == 0xFFFFFFFF:
            raise _win_error("ResumeThread.worker")
        resumed_at = time.monotonic()
        peak_rss = 0
        failure_code: str | None = None
        while True:
            wait_state = kernel32.WaitForSingleObject(process_info.hProcess, 0)
            if wait_state == 0x00000000:
                break
            if wait_state != 0x00000102:
                failure_code = "FE_EQ_WORKER_WAIT_STATE_INVALID"
                break
            if pipe_broken.is_set():
                failure_code = "FE_EQ_WORKER_PIPE_BROKEN"
                break
            if stdout_overflow.is_set():
                failure_code = "FE_EQ_WORKER_STDOUT_LIMIT"
                break
            try:
                rss = _tree_rss_bytes(int(process_info.dwProcessId))
            except _ContractFailure:
                if (
                    kernel32.WaitForSingleObject(process_info.hProcess, 0)
                    == 0x00000000
                ):
                    break
                failure_code = "FE_EQ_WORKER_RESOURCE_MONITOR_FAILED"
                break
            peak_rss = max(peak_rss, rss)
            if rss > TREE_RSS_LIMIT_BYTES:
                failure_code = "FE_EQ_WORKER_TREE_RSS_LIMIT"
                break
            if time.monotonic() - resumed_at >= TIMEOUT_SECONDS:
                failure_code = "FE_EQ_WORKER_TIMEOUT"
                break
            time.sleep(POLL_SECONDS)
        if failure_code is not None:
            if not kernel32.TerminateJobObject(job, 70):
                failure_code = "FE_EQ_WORKER_TERMINATION_FAILED"
            else:
                process_tree_terminated = True
        if kernel32.WaitForSingleObject(process_info.hProcess, 10000) != 0x00000000:
            kernel32.TerminateJobObject(job, 70)
            process_tree_terminated = True
            failure_code = "FE_EQ_WORKER_TERMINATION_FAILED"
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(
            process_info.hProcess, ctypes.byref(exit_code)
        ):
            raise _win_error("GetExitCodeProcess.worker")
        writer.join(timeout=5.0)
        for thread in readers:
            thread.join(timeout=5.0)
        if writer.is_alive() or any(thread.is_alive() for thread in readers):
            failure_code = "FE_EQ_WORKER_TERMINATION_FAILED"
        stderr_bytes = bytes(stderr_tail)
        stdout_bytes = bytes(stdout_prefix)
        response: dict[str, Any] | None = None
        response_json: str | None = None
        matched_valid_response = False
        execution_status = "UNKNOWN_AFTER_TRANSPORT_OR_CONTAINMENT_FAILURE"
        if stdout_total > MAX_STDOUT_BYTES:
            failure_code = "FE_EQ_WORKER_STDOUT_LIMIT"
        if failure_code is None or failure_code in RETRY_CODES:
            try:
                response = _parse_worker_response(
                    stdout_bytes,
                    request_sha256,
                    contract.eligible_phases,
                )
            except Exception:
                if stdout_total:
                    failure_code = "FE_EQ_WORKER_PROTOCOL_INVALID"
                elif pipe_broken.is_set():
                    failure_code = "FE_EQ_WORKER_PIPE_BROKEN"
                else:
                    failure_code = "FE_EQ_WORKER_CHILD_EXIT_NO_RESPONSE"
            else:
                matched_valid_response = True
                response_json = _canonical_bytes(response).decode("ascii")
                execution_status = (
                    "CONFIRMED_EXECUTED"
                    if response["real_equilibrium_executed"] is True
                    else "CONFIRMED_NOT_INVOKED"
                )
                if pipe_broken.is_set() or int(exit_code.value) != 0:
                    failure_code = "FE_EQ_WORKER_TRANSPORT_AFTER_VALID_RESPONSE"
                else:
                    failure_code = (
                        response["failure_code"]
                        if response["status"] == "FAILURE"
                        else None
                    )
        status = "SUCCESS" if failure_code is None else "FAILURE"
        receipt = AttemptReceipt(
            attempt_number=attempt_number,
            request_sha256=request_sha256,
            status=status,
            failure_code=failure_code,
            return_code=int(exit_code.value),
            duration_seconds=float(time.monotonic() - resumed_at),
            peak_observed_tree_rss_bytes=peak_rss,
            stdout_observed_bytes=stdout_total,
            stdout_sha256=stdout_hash.hexdigest(),
            stderr_observed_bytes=stderr_total,
            stderr_tail_bytes=len(stderr_bytes),
            stderr_tail_sha256=hashlib.sha256(stderr_bytes).hexdigest(),
            process_tree_terminated=process_tree_terminated,
            matched_valid_response=matched_valid_response,
            real_equilibrium_execution_status=execution_status,
        )
        completed_execution = _AttemptExecution(receipt, response_json)
    except EquilibriumWitnessError:
        raise
    except Exception as error:
        raise EquilibriumWitnessError(
            "FE_EQ_CONTROLLER_CONTAINMENT_UNAVAILABLE"
        ) from error
    finally:
        if process_started:
            if job:
                kernel32.TerminateJobObject(job, 70)
            if process_info.hProcess:
                kernel32.TerminateProcess(process_info.hProcess, 70)
                if (
                    kernel32.WaitForSingleObject(process_info.hProcess, 10000)
                    != 0x00000000
                ):
                    cleanup_failed = True
        for handle in child_handles:
            _close_handle(kernel32, handle)
        child_handles.clear()
        if writer is not None:
            writer.join(timeout=5.0)
            if writer.is_alive():
                cleanup_failed = True
        for thread in readers:
            thread.join(timeout=5.0)
            if thread.is_alive():
                cleanup_failed = True
        for file_object in converted_files:
            try:
                file_object.close()
            except (OSError, ValueError):
                pass
        for item in locked_code_files:
            try:
                item.file_object.close()
            except Exception:
                cleanup_failed = True
        for handle in handles:
            _close_handle(kernel32, handle)
        if attribute_list:
            kernel32.DeleteProcThreadAttributeList(attribute_list)
        _close_handle(kernel32, process_info.hThread)
        _close_handle(kernel32, process_info.hProcess)
        _close_handle(kernel32, job)
        if (
            worker_directory is not None
            and worker_directory_parent is not None
            and worker_directory_identity is not None
            and worker_directory_handle
        ):
            try:
                _cleanup_private_worker_directory(
                    kernel32,
                    worker_directory,
                    worker_directory_parent,
                    worker_directory_identity,
                    worker_directory_handle,
                )
            except _ContractFailure:
                cleanup_failed = True
            finally:
                _close_handle(kernel32, worker_directory_handle)
                worker_directory_handle = None
        elif worker_directory_handle:
            _close_handle(kernel32, worker_directory_handle)
    if completed_execution is None:
        raise EquilibriumWitnessError(
            "FE_EQ_CONTROLLER_CONTAINMENT_UNAVAILABLE"
        ) from None
    if cleanup_failed:
        previous = completed_execution.receipt
        completed_execution = _AttemptExecution(
            AttemptReceipt(
                attempt_number=previous.attempt_number,
                request_sha256=previous.request_sha256,
                status="FAILURE",
                failure_code="FE_EQ_CONTROLLER_CLEANUP_FAILED",
                return_code=previous.return_code,
                duration_seconds=previous.duration_seconds,
                peak_observed_tree_rss_bytes=previous.peak_observed_tree_rss_bytes,
                stdout_observed_bytes=previous.stdout_observed_bytes,
                stdout_sha256=previous.stdout_sha256,
                stderr_observed_bytes=previous.stderr_observed_bytes,
                stderr_tail_bytes=previous.stderr_tail_bytes,
                stderr_tail_sha256=previous.stderr_tail_sha256,
                process_tree_terminated=previous.process_tree_terminated,
                matched_valid_response=previous.matched_valid_response,
                real_equilibrium_execution_status=(
                    "UNKNOWN_AFTER_TRANSPORT_OR_CONTAINMENT_FAILURE"
                ),
            ),
            completed_execution.response_json,
        )
    return completed_execution


def _attempt_sequence(
    root: Path,
    contract: _Contract,
    request_bytes: bytes,
    request_sha256: str,
) -> tuple[_AttemptExecution, ...]:
    attempts: list[_AttemptExecution] = []
    immutable_request = bytes(request_bytes)
    immutable_transport_sha256 = hashlib.sha256(immutable_request).hexdigest()
    for number in range(1, MAX_ATTEMPTS + 1):
        execution = _spawn_win32_attempt(
            root,
            contract,
            immutable_request,
            request_sha256,
            number,
        )
        attempts.append(execution)
        if execution.receipt.status == "SUCCESS":
            break
        if execution.receipt.matched_valid_response:
            break
        if execution.receipt.failure_code not in RETRY_CODES:
            break
        if number == MAX_ATTEMPTS:
            break
        if (
            bytes(request_bytes) != immutable_request
            or hashlib.sha256(immutable_request).hexdigest()
            != immutable_transport_sha256
        ):
            raise EquilibriumWitnessError("FE_EQ_CONTROLLER_REQUEST_INVALID")
    return tuple(attempts)


def _execute_serialized(
    root: Path,
    contract: _Contract,
    request_bytes: bytes,
    request_sha256: str,
) -> tuple[_AttemptExecution, ...]:
    with _named_scientific_mutex():
        return _attempt_sequence(root, contract, request_bytes, request_sha256)


def _run_equilibrium_witness(
    profile_id: object,
    mass_fractions: object,
    temperature_k: object,
) -> EquilibriumWitnessResult:
    if type(profile_id) is not str or profile_id not in PROFILE_KEYS:
        raise EquilibriumWitnessError("FE_EQ_CONTROLLER_REQUEST_INVALID")
    if isinstance(temperature_k, bool) or not isinstance(
        temperature_k, (int, float)
    ):
        raise EquilibriumWitnessError("FE_EQ_CONTROLLER_REQUEST_INVALID")
    temperature = float(temperature_k)
    if not math.isfinite(temperature) or not 673.0 <= temperature <= 2000.0:
        raise EquilibriumWitnessError("FE_EQ_CONTROLLER_REQUEST_INVALID")
    try:
        mass = _canonical_mass_mapping(mass_fractions)
        contract = _load_contract(PROJECT_ROOT)
        runtime_bytes = _runtime_bytes(PROJECT_ROOT, contract, profile_id)
        _request, request_bytes, request_id = _worker_request(
            contract,
            profile_id,
            mass,
            temperature,
            runtime_bytes,
        )
        pre_observations = _observe_cards(PROJECT_ROOT, contract.cards)
        pre = InputSnapshot("PRE", request_id, pre_observations)
        attempts_execution = _execute_serialized(
            PROJECT_ROOT,
            contract,
            request_bytes,
            request_id,
        )
        post_observations = _observe_cards(PROJECT_ROOT, contract.cards)
        post = InputSnapshot("POST", request_id, post_observations)
        if pre.observations != post.observations:
            raise EquilibriumWitnessError("FE_EQ_CONTROLLER_INPUT_CHANGED")
    except EquilibriumWitnessError:
        raise
    except _ContractFailure as error:
        raise EquilibriumWitnessError("FE_EQ_CONTROLLER_CONTRACT_INVALID") from error
    finally:
        if "runtime_bytes" in locals():
            runtime_bytes = b""
        if "request_bytes" in locals():
            request_bytes = b""
    attempts = tuple(item.receipt for item in attempts_execution)
    final = attempts_execution[-1]
    status = final.receipt.status
    return EquilibriumWitnessResult(
        profile_id=profile_id,
        temperature_k=temperature,
        mass_fractions=mass,
        request_sha256=request_id,
        pre=pre,
        post=post,
        attempts=attempts,
        status=status,
        failure_code=final.receipt.failure_code,
        worker_response_json=final.response_json,
        eligible_phases=contract.eligible_phases,
    )


def run_fe_equilibrium_witness(
    profile_id: str,
    mass_fractions: Mapping[str, float],
    temperature_k: float,
) -> EquilibriumWitnessResult:
    """Run one contained local diagnostic witness with fixed scientific scope."""

    error_code: str | None = None
    try:
        result = _run_equilibrium_witness(
            profile_id,
            mass_fractions,
            temperature_k,
        )
    except EquilibriumWitnessError as error:
        error_code = error.code
    except Exception:
        error_code = "FE_EQ_CONTROLLER_INTERNAL_FAILURE"
    else:
        return result
    raise EquilibriumWitnessError(
        error_code or "FE_EQ_CONTROLLER_INTERNAL_FAILURE"
    ) from None


__all__ = [
    "EquilibriumWitnessError",
    "EquilibriumWitnessResult",
    "run_fe_equilibrium_witness",
]
