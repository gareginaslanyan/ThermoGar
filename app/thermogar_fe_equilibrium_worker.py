"""Isolated S2 Fe equilibrium worker with one approved scientific call.

The controller supplies verified immutable database bytes over stdin.  This
worker accepts no filesystem path or solver-scope option from a caller and
emits exactly one canonical JSON response line.
"""

from __future__ import annotations

import base64
from contextlib import redirect_stdout
import hashlib
import io
import json
import math
import os
from pathlib import Path
import stat
import sys
import types
from typing import Any


REQUEST_SCHEMA = "SWR-NE04-FE-EQUILIBRIUM-WORKER-REQUEST-2"
RESPONSE_SCHEMA = "SWR-NE04-FE-EQUILIBRIUM-WORKER-RESPONSE-2"
CLAIM = "LOCAL_INTERNAL_DIAGNOSTIC_REAL_EQUILIBRIUM_NOT_NE04_RELEASE"
MAX_INPUT_BYTES = 1048576
MAX_RAW_ROWS = 512
MAX_TERMINAL_ROWS = 131
PRESSURE_PA = 101325.0
PDENS = 25
ZERO_FLOOR = 1e-10
BALANCE_TOLERANCE = 1e-8
ROUND_TRIP_TOLERANCE = 1e-12
ELIGIBLE_PHASE_SHA256 = (
    "facf84563f444d5bdca2d16f22689a2e8dd6bc6a331d7f188dfcf4d8f2ed91b4"
)
RAW_PHASE_COUNT = 132
RAW_PHASE_SHA256 = (
    "f6a545c3e6a2a8d497caa00eb2fe439a28d91689646f679038c485704dd44ad4"
)
ATOMIC_MASS_SHA256 = (
    "b1d3ab2a3c238c00654e32aadce6c14e22af3434349c00e354ef729d8f4014a2"
)
EQUILIBRIUM_CORE_BYTES = 27988
EQUILIBRIUM_CORE_SHA256 = (
    "24734a4c404d7a60220f18a956c884e06ff8dfcfec2ecc10b417f912ecf46bd3"
)
NUMERICAL_GRID_BYTES = 19791
NUMERICAL_GRID_SHA256 = (
    "7115ae94edeb7522c40bd8991b70c568f71e80b8dcd20c94277293bcd239e63f"
)
PROFILE_IDENTITIES = {
    "thermogar_patch": (
        568690,
        "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612",
    ),
    "upstream_original": (
        568418,
        "f9375c3a7a8649bace698e2177f2cc964bce3f8a19f08ae05d88840abd77b112",
    ),
}
RUNTIME_POLICY_IDENTITIES = {
    "python": (
        274712,
        "21bb438c0d4a6f1f164b9a646f6ee000340185e5871180aec06db8d3f07c0082",
    ),
    "workspace": (
        27628,
        "b567955bc03fc2d9977976c02abefbed3221e1ddda2e91662ad5a81726a31a4d",
    ),
    "equilibrium": (
        4304,
        "939696bd5f7a64dcde08591de66828988a8eb45964c3f9ebc1d74686301fdbb8",
    ),
    "solver": (
        9983,
        "308b844ad74929b7d46c093a197006167e0a2e88037d657ab5e3af667fdc2608",
    ),
    "utils": (
        22838,
        "1705991a0984401993805e7231278b1005ff7d1da984704132d28e163d3af258",
    ),
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
DATABASE_ELEMENTS = tuple(sorted((*MASS_ORDER, "VA")))
STRICT_UPPER_BOUNDS_WT_PERCENT = {
    "AL": 3.0, "B": 0.5, "C": 0.5, "CO": 3.0, "CR": 25.0,
    "CU": 1.0, "H": 0.1, "HF": 0.5, "LA": 0.5, "MN": 25.0,
    "MO": 5.0, "N": 1.0, "NB": 1.0, "NI": 26.0, "O": 0.5,
    "P": 0.05, "PD": 4.0, "S": 0.1, "SI": 3.5, "TA": 0.5,
    "TI": 0.5, "V": 0.5, "W": 3.0, "Y": 0.5,
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


def _valid_scientific_failure_diagnostic(value: object) -> bool:
    if type(value) is not tuple or len(value) != 3:
        return False
    category, tokens, fingerprint = value
    if (
        category not in SCIENTIFIC_FAILURE_CATEGORIES
        or type(tokens) is not tuple
        or not 1 <= len(tokens) <= SCIENTIFIC_FAILURE_CHAIN_LIMIT
        or any(token not in SCIENTIFIC_EXCEPTION_TOKENS for token in tokens)
        or type(fingerprint) is not str
        or len(fingerprint) != 64
        or any(character not in "0123456789abcdef" for character in fingerprint)
    ):
        return False
    expected = _digest(
        {
            "stage": SCIENTIFIC_FAILURE_STAGE,
            "category": category,
            "exception_tokens": list(tokens),
        }
    )
    return fingerprint == expected


def _valid_projection_provenance(value: object) -> bool:
    if type(value) is not tuple or len(value) != 2:
        return False
    solver_components, projected_phases = value
    if (
        type(solver_components) is not tuple
        or not 2 <= len(solver_components) <= len(FULL_SOLVER_COMPONENTS)
        or solver_components[-2:] != ("FE", "VA")
        or len(set(solver_components)) != len(solver_components)
        or tuple(item for item in NON_FE_ORDER if item in solver_components)
        != solver_components[:-2]
        or type(projected_phases) is not tuple
        or not 1 <= len(projected_phases) <= 131
        or projected_phases != tuple(sorted(projected_phases))
        or len(set(projected_phases)) != len(projected_phases)
        or any(type(item) is not str or not item for item in projected_phases)
    ):
        return False
    return True


class WorkerFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        scientific_api_invoked: bool = False,
        scientific_failure_diagnostic: object = None,
        projection_provenance: object = None,
    ):
        if (
            type(code) is not str
            or not code.startswith("FE_EQ_WORKER_")
            or any(
                character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
                for character in code
            )
        ):
            code = "FE_EQ_WORKER_INTERNAL_FAILURE"
        self.code = code
        self.scientific_api_invoked = scientific_api_invoked is True
        self.scientific_failure_diagnostic = (
            scientific_failure_diagnostic
            if _valid_scientific_failure_diagnostic(scientific_failure_diagnostic)
            else None
        )
        self.projection_provenance = (
            projection_provenance
            if _valid_projection_provenance(projection_provenance)
            else None
        )
        super().__init__(code)


class DuplicateKeyError(WorkerFailure):
    def __init__(self) -> None:
        super().__init__("FE_EQ_WORKER_PROTOCOL_INVALID")


class _BoundedTextSink(io.TextIOBase):
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._observed = 0
        self._digest = hashlib.sha256()

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        encoded = str(text).encode("utf-8", errors="replace")
        self._observed += len(encoded)
        self._digest.update(encoded)
        return len(text)

    @property
    def observation(self) -> dict[str, Any]:
        return {
            "bytes": min(self._observed, self._limit),
            "truncated": self._observed > self._limit,
            "sha256": self._digest.hexdigest(),
        }


def _fail(code: str) -> None:
    raise WorkerFailure(code)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError()
        result[key] = value
    return result


def _reject_constant(_token: str) -> None:
    _fail("FE_EQ_WORKER_PROTOCOL_INVALID")


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as error:
        raise WorkerFailure("FE_EQ_WORKER_PROTOCOL_INVALID") from error


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _scientific_exception_token(
    error: BaseException,
    exception_types: tuple[object, ...],
) -> tuple[str, str]:
    dof_error, condition_error, equilibrium_error, lin_alg_error = exception_types
    if isinstance(error, MemoryError):
        return "MEMORY_ERROR", "MEMORY_ALLOCATION"
    if isinstance(error, dof_error):
        return "PYCALPHAD_DOF_ERROR", "MODEL_CONSTRUCTION"
    if isinstance(error, condition_error):
        return "PYCALPHAD_CONDITION_ERROR", "CONDITION_CONTRACT"
    if isinstance(error, equilibrium_error):
        return "PYCALPHAD_EQUILIBRIUM_ERROR", "SOLVER_FAILURE"
    if isinstance(error, lin_alg_error):
        return "NUMPY_LINALG_ERROR", "SOLVER_FAILURE"
    return "OTHER", "OTHER"


def _scientific_failure_diagnostic(
    error: BaseException,
    exception_types: object,
) -> tuple[str, tuple[str, ...], str]:
    if (
        type(exception_types) is not tuple
        or len(exception_types) != 4
        or any(
            type(item) is not type or not issubclass(item, BaseException)
            for item in exception_types
        )
    ):
        exception_types = ((), (), (), ())
    current: BaseException | None = error
    seen: set[int] = set()
    tokens: list[str] = []
    categories: list[str] = []
    while (
        current is not None
        and len(tokens) < SCIENTIFIC_FAILURE_CHAIN_LIMIT
        and id(current) not in seen
    ):
        seen.add(id(current))
        token, category = _scientific_exception_token(current, exception_types)
        tokens.append(token)
        categories.append(category)
        try:
            cause = BaseException.__getattribute__(current, "__cause__")
            context = BaseException.__getattribute__(current, "__context__")
            suppress_context = BaseException.__getattribute__(
                current,
                "__suppress_context__",
            )
        except BaseException:
            break
        following = cause if cause is not None else (
            None if suppress_context else context
        )
        current = following if isinstance(following, BaseException) else None
    if not tokens:
        tokens = ["OTHER"]
        categories = ["OTHER"]
    category = next(
        (item for item in categories if item != "OTHER"),
        "OTHER",
    )
    token_chain = tuple(tokens)
    fingerprint = _digest(
        {
            "stage": SCIENTIFIC_FAILURE_STAGE,
            "category": category,
            "exception_tokens": list(token_chain),
        }
    )
    return category, token_chain, fingerprint


def _phase_digest(phases: tuple[str, ...]) -> str:
    payload = "".join(f"{phase}\n" for phase in phases).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _solver_components_for_mass(
    mass_rows: tuple[tuple[str, float], ...],
) -> tuple[str, ...]:
    values = dict(mass_rows)
    active_non_fe = tuple(
        element for element in NON_FE_ORDER if values[element] > 0.0
    )
    return (*active_non_fe, "FE", "VA")


def _projection_fields(
    solver_components: tuple[str, ...],
    projected_phases: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "solver_component_axis": list(solver_components),
        "solver_component_count": len(solver_components),
        "solver_component_sha256": _phase_digest(solver_components),
        "component_projection_algorithm": COMPONENT_PROJECTION_ALGORITHM,
        "projected_active_phases": list(projected_phases),
        "projected_active_phase_count": len(projected_phases),
        "projected_active_phase_sha256": _phase_digest(projected_phases),
        "phase_projection_algorithm": PHASE_PROJECTION_ALGORITHM,
    }


def _safety(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        **payload,
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


def _is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _read_stable(path: Path) -> tuple[bytes, int, str]:
    try:
        with path.open("rb") as source:
            before = os.fstat(source.fileno())
            payload = source.read()
            after = os.fstat(source.fileno())
        path_after = path.lstat()
    except OSError as error:
        raise WorkerFailure("FE_EQ_WORKER_RUNTIME_POLICY_INVALID") from error
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or not os.path.samestat(after, path_after)
        or len(payload) != after.st_size
        or _is_reparse(path)
    ):
        _fail("FE_EQ_WORKER_RUNTIME_POLICY_INVALID")
    return payload, len(payload), hashlib.sha256(payload).hexdigest()


def _load_conversion_api() -> tuple[Any, Any]:
    app_dir = Path(__file__).resolve().parent
    core_path = app_dir / "thermogar_equilibrium_core.py"
    grid_path = app_dir / "thermogar_numerical_grid.py"
    core_payload, size, digest = _read_stable(core_path)
    if size != EQUILIBRIUM_CORE_BYTES or digest != EQUILIBRIUM_CORE_SHA256:
        _fail("FE_EQ_WORKER_RUNTIME_POLICY_INVALID")
    grid_payload, grid_size, grid_digest = _read_stable(grid_path)
    if (
        grid_size != NUMERICAL_GRID_BYTES
        or grid_digest != NUMERICAL_GRID_SHA256
    ):
        _fail("FE_EQ_WORKER_RUNTIME_POLICY_INVALID")
    try:
        grid_module = types.ModuleType("thermogar_numerical_grid")
        grid_module.__file__ = "<PINNED_THERMOGAR_NUMERICAL_GRID_BYTES>"
        sys.modules[grid_module.__name__] = grid_module
        exec(
            compile(
                grid_payload,
                grid_module.__file__,
                "exec",
                dont_inherit=True,
            ),
            grid_module.__dict__,
        )
        core_module = types.ModuleType("_thermogar_pinned_equilibrium_core")
        core_module.__file__ = "<PINNED_THERMOGAR_EQUILIBRIUM_CORE_BYTES>"
        sys.modules[core_module.__name__] = core_module
        exec(
            compile(
                core_payload,
                core_module.__file__,
                "exec",
                dont_inherit=True,
            ),
            core_module.__dict__,
        )
        mass_to_mole_fractions = core_module.mass_to_mole_fractions
        mole_to_mass_fractions = core_module.mole_to_mass_fractions
    except Exception as error:
        raise WorkerFailure("FE_EQ_WORKER_RUNTIME_POLICY_INVALID") from error
    _post_core, post_core_size, post_core_digest = _read_stable(core_path)
    _post_grid, post_grid_size, post_grid_digest = _read_stable(grid_path)
    if (
        (post_core_size, post_core_digest)
        != (EQUILIBRIUM_CORE_BYTES, EQUILIBRIUM_CORE_SHA256)
        or (post_grid_size, post_grid_digest)
        != (NUMERICAL_GRID_BYTES, NUMERICAL_GRID_SHA256)
    ):
        _fail("FE_EQ_WORKER_RUNTIME_POLICY_INVALID")
    return mass_to_mole_fractions, mole_to_mass_fractions


def _validate_scientific_origins(
    pycalphad_module: object,
    equilibrium: object,
    filter_phases: object,
    package_root: Path,
    policy_paths: dict[str, Path],
) -> None:
    imported_file = getattr(pycalphad_module, "__file__", None)
    equilibrium_module = sys.modules.get(getattr(equilibrium, "__module__", ""))
    filter_module = sys.modules.get(getattr(filter_phases, "__module__", ""))
    equilibrium_origin = getattr(equilibrium_module, "__file__", None)
    filter_origin = getattr(filter_module, "__file__", None)
    try:
        valid = (
            imported_file is not None
            and Path(imported_file).resolve().parent == package_root
            and equilibrium_origin is not None
            and Path(equilibrium_origin).resolve()
            == policy_paths["equilibrium"].resolve()
            and filter_origin is not None
            and Path(filter_origin).resolve() == policy_paths["utils"].resolve()
        )
    except (OSError, TypeError, ValueError):
        valid = False
    if not valid:
        _fail("FE_EQ_WORKER_RUNTIME_POLICY_INVALID")


def _load_scientific_api() -> tuple[Any, Any, Any, Any, tuple[type[BaseException], ...]]:
    package_root = (
        Path(sys.prefix) / "Lib" / "site-packages" / "pycalphad"
    ).resolve()
    policy_paths = {
        "python": Path(sys.executable),
        "workspace": package_root / "core" / "workspace.py",
        "equilibrium": package_root / "core" / "equilibrium.py",
        "solver": package_root / "core" / "solver.py",
        "utils": package_root / "core" / "utils.py",
    }
    for role, path in policy_paths.items():
        _payload, size, digest = _read_stable(path)
        if (size, digest) != RUNTIME_POLICY_IDENTITIES[role]:
            _fail("FE_EQ_WORKER_RUNTIME_POLICY_INVALID")
    try:
        import pycalphad
        from pycalphad import Database, equilibrium, variables
        from pycalphad.core.errors import ConditionError, DofError, EquilibriumError
        from pycalphad.core.utils import filter_phases
        from numpy.linalg import LinAlgError
    except Exception as error:
        raise WorkerFailure("FE_EQ_WORKER_SCIENTIFIC_API_UNAVAILABLE") from error
    if getattr(pycalphad, "__version__", None) != "0.11.2":
        _fail("FE_EQ_WORKER_RUNTIME_POLICY_INVALID")
    _validate_scientific_origins(
        pycalphad,
        equilibrium,
        filter_phases,
        package_root,
        policy_paths,
    )
    for role, path in policy_paths.items():
        _payload, size, digest = _read_stable(path)
        if (size, digest) != RUNTIME_POLICY_IDENTITIES[role]:
            _fail("FE_EQ_WORKER_RUNTIME_POLICY_INVALID")
    diagnostic_types = (DofError, ConditionError, EquilibriumError, LinAlgError)
    if any(
        type(item) is not type or not issubclass(item, BaseException)
        for item in diagnostic_types
    ):
        _fail("FE_EQ_WORKER_RUNTIME_POLICY_INVALID")
    return Database, equilibrium, variables, filter_phases, diagnostic_types


def _validate_mass_rows(value: object) -> tuple[tuple[str, float], ...]:
    if type(value) is not list or len(value) != 25:
        _fail("FE_EQ_WORKER_REQUEST_COMPOSITION_INVALID")
    rows: list[tuple[str, float]] = []
    for expected, row in zip(MASS_ORDER, value):
        if type(row) is not list or len(row) != 2 or row[0] != expected:
            _fail("FE_EQ_WORKER_REQUEST_COMPOSITION_INVALID")
        raw = row[1]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            _fail("FE_EQ_WORKER_REQUEST_COMPOSITION_INVALID")
        number = float(raw)
        if not math.isfinite(number) or number < 0.0:
            _fail("FE_EQ_WORKER_REQUEST_COMPOSITION_INVALID")
        rows.append((expected, 0.0 if number == 0.0 else number))
    result = tuple(rows)
    values = dict(result)
    if abs(math.fsum(values.values()) - 1.0) > 1e-12 or values["FE"] <= 0.0:
        _fail("FE_EQ_WORKER_REQUEST_COMPOSITION_INVALID")
    for element, upper in STRICT_UPPER_BOUNDS_WT_PERCENT.items():
        if values[element] >= upper * 0.01:
            _fail("FE_EQ_WORKER_REQUEST_COMPOSITION_INVALID")
    return result


def _validate_request(value: object) -> tuple[
    dict[str, Any],
    str,
    str,
    bytes,
    tuple[tuple[str, float], ...],
    float,
    tuple[str, ...],
    tuple[str, ...],
]:
    expected_keys = {
        "schema_version",
        "request_id",
        "profile_id",
        "runtime_size_bytes",
        "runtime_sha256",
        "runtime_base64",
        "mass_fractions",
        "temperature_k",
        "pressure_pa",
        "solver_components",
        "solver_component_count",
        "solver_component_sha256",
        "component_projection_algorithm",
        "eligible_phases",
        "eligible_phase_sha256",
        "pdens",
        "atomic_mass_sha256",
        "workspace_effective_x_floor",
    }
    if type(value) is not dict or set(value) != expected_keys:
        _fail("FE_EQ_WORKER_PROTOCOL_INVALID")
    body = dict(value)
    request_id = body.pop("request_id")
    if (
        type(request_id) is not str
        or len(request_id) != 64
        or any(character not in "0123456789abcdef" for character in request_id)
    ):
        _fail("FE_EQ_WORKER_REQUEST_ID_INVALID")
    if value["schema_version"] != REQUEST_SCHEMA:
        _fail("FE_EQ_WORKER_PROTOCOL_INVALID")
    profile_id = value["profile_id"]
    if type(profile_id) is not str or profile_id not in PROFILE_IDENTITIES:
        _fail("FE_EQ_WORKER_PROFILE_INVALID")
    expected_size, expected_sha = PROFILE_IDENTITIES[profile_id]
    if (
        value["runtime_size_bytes"] != expected_size
        or value["runtime_sha256"] != expected_sha
        or type(value["runtime_base64"]) is not str
    ):
        _fail("FE_EQ_WORKER_RUNTIME_IDENTITY_INVALID")
    try:
        runtime_bytes = base64.b64decode(
            value["runtime_base64"].encode("ascii"),
            validate=True,
        )
    except (UnicodeError, ValueError) as error:
        raise WorkerFailure("FE_EQ_WORKER_RUNTIME_IDENTITY_INVALID") from error
    if (
        len(runtime_bytes) != expected_size
        or hashlib.sha256(runtime_bytes).hexdigest() != expected_sha
    ):
        _fail("FE_EQ_WORKER_RUNTIME_IDENTITY_INVALID")
    mass_rows = _validate_mass_rows(value["mass_fractions"])
    normalized_body = dict(body)
    normalized_body["mass_fractions"] = [list(row) for row in mass_rows]
    if request_id != _digest(normalized_body):
        _fail("FE_EQ_WORKER_REQUEST_ID_INVALID")
    solver_components = _solver_components_for_mass(mass_rows)
    raw_temperature = value["temperature_k"]
    if isinstance(raw_temperature, bool) or not isinstance(
        raw_temperature, (int, float)
    ):
        _fail("FE_EQ_WORKER_TEMPERATURE_INVALID")
    temperature = float(raw_temperature)
    if not math.isfinite(temperature) or not 673.0 <= temperature <= 2000.0:
        _fail("FE_EQ_WORKER_TEMPERATURE_INVALID")
    if (
        value["pressure_pa"] != PRESSURE_PA
        or value["pdens"] != PDENS
        or value["solver_components"] != list(solver_components)
        or value["solver_component_count"] != len(solver_components)
        or value["solver_component_sha256"] != _phase_digest(solver_components)
        or value["component_projection_algorithm"]
        != COMPONENT_PROJECTION_ALGORITHM
        or value["eligible_phase_sha256"] != ELIGIBLE_PHASE_SHA256
        or value["atomic_mass_sha256"] != ATOMIC_MASS_SHA256
        or value["workspace_effective_x_floor"] != ZERO_FLOOR
    ):
        _fail("FE_EQ_WORKER_SCOPE_INVALID")
    raw_phases = value["eligible_phases"]
    if (
        type(raw_phases) is not list
        or len(raw_phases) != 131
        or any(type(phase) is not str for phase in raw_phases)
    ):
        _fail("FE_EQ_WORKER_PHASE_SCOPE_INVALID")
    phases = tuple(raw_phases)
    if (
        phases != tuple(sorted(phases))
        or len(set(phases)) != len(phases)
        or _phase_digest(phases) != ELIGIBLE_PHASE_SHA256
        or "C15_LAVES" not in phases
        or "LIQUID" not in phases
        or "BCC_A2" in phases
    ):
        _fail("FE_EQ_WORKER_PHASE_SCOPE_INVALID")
    return (
        value,
        request_id,
        profile_id,
        runtime_bytes,
        mass_rows,
        temperature,
        phases,
        solver_components,
    )


def _atomic_masses(database: object) -> tuple[tuple[str, float], ...]:
    try:
        elements = tuple(sorted(str(element).upper() for element in database.elements))
        refstates = database.refstates
    except Exception as error:
        raise WorkerFailure("FE_EQ_WORKER_DATABASE_METADATA_INVALID") from error
    if elements != DATABASE_ELEMENTS:
        _fail("FE_EQ_WORKER_DATABASE_METADATA_INVALID")
    rows: list[tuple[str, float]] = []
    for element in MASS_ORDER:
        try:
            raw = refstates[element]["mass"]
        except Exception as error:
            raise WorkerFailure("FE_EQ_WORKER_DATABASE_METADATA_INVALID") from error
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            _fail("FE_EQ_WORKER_DATABASE_METADATA_INVALID")
        number = float(raw)
        if not math.isfinite(number) or number <= 0.0:
            _fail("FE_EQ_WORKER_DATABASE_METADATA_INVALID")
        rows.append((element, number))
    result = tuple(rows)
    if _digest([list(row) for row in result]) != ATOMIC_MASS_SHA256:
        _fail("FE_EQ_WORKER_ATOMIC_MASS_MISMATCH")
    return result


def _normalized_fraction_rows(
    value: object,
    failure_code: str,
) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple or len(value) != len(MASS_ORDER):
        _fail(failure_code)
    normalized: list[tuple[str, float]] = []
    for expected, row in zip(MASS_ORDER, value):
        if type(row) is not tuple or len(row) != 2 or row[0] != expected:
            _fail(failure_code)
        raw = row[1]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            _fail(failure_code)
        number = float(raw)
        if not math.isfinite(number) or number < 0.0:
            _fail(failure_code)
        normalized.append((expected, 0.0 if number == 0.0 else number))
    return tuple(normalized)


def _effective_mole_rows(
    nominal: tuple[tuple[str, float], ...],
    mass_rows: tuple[tuple[str, float], ...],
    solver_components: tuple[str, ...],
) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, float], ...], float]:
    nominal_map = dict(nominal)
    mass_map = dict(mass_rows)
    active_non_fe = solver_components[:-2]
    inactive = tuple(
        element for element in NON_FE_ORDER if element not in active_non_fe
    )
    if any(
        (mass_map[element] > 0.0 and nominal_map[element] <= 0.0)
        or (mass_map[element] == 0.0 and nominal_map[element] != 0.0)
        for element in NON_FE_ORDER
    ):
        _fail("FE_EQ_WORKER_BASIS_CONVERSION_FAILED")
    submitted = tuple((element, nominal_map[element]) for element in active_non_fe)
    if any(value >= 1.0 - ZERO_FLOOR for _element, value in submitted):
        _fail("FE_EQ_WORKER_EFFECTIVE_COMPOSITION_INVALID")
    effective_map = {
        element: max(nominal_map[element], ZERO_FLOOR)
        for element in active_non_fe
    }
    effective_fe = 1.0 - math.fsum(effective_map.values())
    if not math.isfinite(effective_fe) or effective_fe <= 0.0:
        _fail("FE_EQ_WORKER_EFFECTIVE_COMPOSITION_INVALID")
    effective_map.update({element: 0.0 for element in inactive})
    effective_map["FE"] = effective_fe
    effective = tuple((element, float(effective_map[element])) for element in MASS_ORDER)
    maximum_delta = max(
        abs(nominal_map[element] - effective_map[element]) for element in MASS_ORDER
    )
    return submitted, effective, float(maximum_delta)


def _dataset_component_names(
    dataset: object,
    solver_components: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    try:
        coordinate = dataset.coords["component"]
        raw_values = coordinate.values
        values = raw_values.tolist()
    except Exception as error:
        raise WorkerFailure("FE_EQ_WORKER_DATASET_SHAPE_INVALID") from error
    if type(values) is not list:
        values = list(values)
    names = tuple(str(value).upper() for value in values)
    canonical_nonvacant = tuple(
        component for component in solver_components if component != "VA"
    )
    nonvacant_names = tuple(component for component in names if component != "VA")
    vacancy_present = "VA" in names
    if (
        len(names) not in {len(canonical_nonvacant), len(canonical_nonvacant) + 1}
        or len(set(names)) != len(names)
        or set(nonvacant_names) != set(canonical_nonvacant)
        or len(nonvacant_names) != len(canonical_nonvacant)
        or set(names) not in (
            set(canonical_nonvacant),
            set(canonical_nonvacant) | {"VA"},
        )
    ):
        _fail("FE_EQ_WORKER_COMPONENT_AXIS_INVALID")
    return names, canonical_nonvacant, vacancy_present


def _reshape_values(value: object, shape: tuple[int, ...]) -> list[Any]:
    try:
        array = value.values
        if tuple(int(item) for item in array.shape) != shape:
            _fail("FE_EQ_WORKER_DATASET_SHAPE_INVALID")
        return array.reshape(-1).tolist()
    except WorkerFailure:
        raise
    except Exception as error:
        raise WorkerFailure("FE_EQ_WORKER_DATASET_SHAPE_INVALID") from error


def _normalize_dataset(
    dataset: object,
    projected_phases: tuple[str, ...],
    solver_components: tuple[str, ...],
    effective_mole: tuple[tuple[str, float], ...],
) -> dict[str, Any]:
    try:
        phase_value = dataset["Phase"]
        fraction_value = dataset["NP"]
        x_value = dataset["X"]
        phase_shape = tuple(int(item) for item in phase_value.values.shape)
        fraction_shape = tuple(int(item) for item in fraction_value.values.shape)
        x_shape = tuple(int(item) for item in x_value.values.shape)
    except Exception as error:
        raise WorkerFailure("FE_EQ_WORKER_DATASET_SHAPE_INVALID") from error
    (
        component_names,
        canonical_nonvacant,
        vacancy_present,
    ) = _dataset_component_names(dataset, solver_components)
    if (
        not phase_shape
        or not x_shape
        or phase_shape != fraction_shape
        or x_shape[:-1] != phase_shape
        or x_shape[-1] != len(component_names)
        or math.prod(phase_shape) > MAX_RAW_ROWS
    ):
        _fail("FE_EQ_WORKER_DATASET_SHAPE_INVALID")
    raw_phase = _reshape_values(phase_value, phase_shape)
    raw_fraction = _reshape_values(fraction_value, phase_shape)
    try:
        raw_x = x_value.values.reshape((-1, len(component_names))).tolist()
    except Exception as error:
        raise WorkerFailure("FE_EQ_WORKER_DATASET_SHAPE_INVALID") from error
    if not (len(raw_phase) == len(raw_fraction) == len(raw_x)):
        _fail("FE_EQ_WORKER_DATASET_SHAPE_INVALID")

    component_index = {name: index for index, name in enumerate(component_names)}
    raw_active_rows: list[dict[str, Any]] = []
    for raw_name, raw_np, raw_coordinates in zip(raw_phase, raw_fraction, raw_x):
        name = str(raw_name).strip().upper()
        if isinstance(raw_np, bool) or not isinstance(raw_np, (int, float)):
            _fail("FE_EQ_WORKER_PHASE_RESULT_INVALID")
        fraction = float(raw_np)
        if not name:
            if not (fraction == 0.0 or math.isnan(fraction)):
                _fail("FE_EQ_WORKER_PHASE_RESULT_INVALID")
            continue
        if name not in projected_phases:
            _fail("FE_EQ_WORKER_PHASE_RESULT_INVALID")
        if not math.isfinite(fraction) or fraction <= 0.0:
            _fail("FE_EQ_WORKER_PHASE_RESULT_INVALID")
        if type(raw_coordinates) is not list or len(raw_coordinates) != len(component_names):
            _fail("FE_EQ_WORKER_COMPONENT_RESULT_INVALID")
        all_coordinates: dict[str, float] = {}
        for component in component_names:
            raw = raw_coordinates[component_index[component]]
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                _fail("FE_EQ_WORKER_COMPONENT_RESULT_INVALID")
            number = float(raw)
            if not math.isfinite(number) or number < 0.0 or number > 1.0 + 1e-8:
                _fail("FE_EQ_WORKER_COMPONENT_RESULT_INVALID")
            all_coordinates[component] = 0.0 if number == 0.0 else number
        if (
            abs(math.fsum(all_coordinates.values()) - 1.0)
            > BALANCE_TOLERANCE
        ):
            _fail("FE_EQ_WORKER_COMPONENT_RESULT_INVALID")
        coordinates = [
            [element, all_coordinates.get(element, 0.0)]
            for element in MASS_ORDER
        ]
        raw_active_rows.append(
            {
                "phase": name,
                "fraction": fraction,
                "chemical_coordinates": coordinates,
                "vacancy_coordinate": (
                    all_coordinates["VA"] if vacancy_present else None
                ),
            }
        )
    if not raw_active_rows or len(raw_active_rows) > MAX_RAW_ROWS:
        _fail("FE_EQ_WORKER_EMPTY_RESULT")
    phase_fraction_sum = math.fsum(row["fraction"] for row in raw_active_rows)
    if abs(phase_fraction_sum - 1.0) > BALANCE_TOLERANCE:
        _fail("FE_EQ_WORKER_PHASE_BALANCE_INVALID")

    terminal_rows: list[dict[str, Any]] = []
    for phase_name in sorted({row["phase"] for row in raw_active_rows}):
        vertices = [row for row in raw_active_rows if row["phase"] == phase_name]
        terminal_fraction = math.fsum(row["fraction"] for row in vertices)
        if not math.isfinite(terminal_fraction) or terminal_fraction <= 0.0:
            _fail("FE_EQ_WORKER_PHASE_RESULT_INVALID")
        weighted = []
        for element in MASS_ORDER:
            numerator = math.fsum(
                row["fraction"] * dict(row["chemical_coordinates"])[element]
                for row in vertices
            )
            weighted.append([element, float(numerator / terminal_fraction)])
        vacancy_coordinate = None
        if vacancy_present:
            vacancy_coordinate = float(
                math.fsum(
                    row["fraction"] * float(row["vacancy_coordinate"])
                    for row in vertices
                )
                / terminal_fraction
            )
            if vacancy_coordinate == 0.0:
                vacancy_coordinate = 0.0
        terminal_rows.append(
            {
                "phase": phase_name,
                "fraction": float(terminal_fraction),
                "chemical_coordinates": weighted,
                "vacancy_coordinate": vacancy_coordinate,
                "raw_vertex_count": len(vertices),
            }
        )
    if len(terminal_rows) > MAX_TERMINAL_ROWS:
        _fail("FE_EQ_WORKER_PHASE_RESULT_INVALID")

    bulk: dict[str, float] = {}
    effective_map = dict(effective_mole)
    residuals: dict[str, float] = {}
    for element in MASS_ORDER:
        total = math.fsum(
            row["fraction"] * dict(row["chemical_coordinates"])[element]
            for row in raw_active_rows
        )
        bulk[element] = float(total)
        residuals[element] = abs(total - effective_map[element])
    maximum_residual = max(residuals.values())
    if maximum_residual > BALANCE_TOLERANCE:
        _fail("FE_EQ_WORKER_COMPONENT_BULK_BALANCE_INVALID")
    return {
        "raw_result_row_count": len(raw_phase),
        "raw_active_phase_row_count": len(raw_active_rows),
        "raw_active_phase_projection_sha256": _digest(raw_active_rows),
        "terminal_phase_row_count": len(terminal_rows),
        "dataset_nonvacant_component_axis": list(canonical_nonvacant),
        "dataset_nonvacant_component_count": len(canonical_nonvacant),
        "dataset_nonvacant_component_sha256": _phase_digest(canonical_nonvacant),
        "dataset_vacancy_axis_present": vacancy_present,
        "terminal_phase_rows": terminal_rows,
        "aggregation_semantic": "FRACTION_WEIGHTED_BY_EXACT_PHASE_NAME_NO_RAW_RENORMALIZATION",
        "raw_dataset_serialized": False,
        "c15_scope_included": "C15_LAVES" in projected_phases,
        "c15_present_in_terminal_rows": any(
            row["phase"] == "C15_LAVES" for row in terminal_rows
        ),
        "phase_fraction_sum": float(phase_fraction_sum),
        "runtime_effective_bulk_mole_fractions": [
            [element, bulk[element]] for element in MASS_ORDER
        ],
        "component_bulk_absolute_residuals": [
            [element, residuals[element]] for element in MASS_ORDER
        ],
        "max_component_bulk_absolute_residual": float(maximum_residual),
    }


def _execute_request(value: object) -> dict[str, Any]:
    (
        _request,
        request_id,
        profile_id,
        runtime_bytes,
        mass_rows,
        temperature,
        phases,
        solver_components,
    ) = _validate_request(value)
    (
        Database,
        equilibrium,
        variables,
        filter_phases,
        scientific_exception_types,
    ) = _load_scientific_api()
    try:
        database = Database(io.StringIO(runtime_bytes.decode("utf-8-sig")))
    except Exception as error:
        raise WorkerFailure("FE_EQ_WORKER_DATABASE_LOAD_FAILED") from error
    try:
        raw_phases = tuple(sorted(str(name).upper() for name in database.phases))
        frozen_filtered_phases = tuple(
            sorted(
                str(name).upper()
                for name in filter_phases(
                    database,
                    list(FULL_SOLVER_COMPONENTS),
                    candidate_phases=None,
                )
            )
        )
        projected_phases = tuple(
            sorted(
                str(name).upper()
                for name in filter_phases(
                    database,
                    list(solver_components),
                    candidate_phases=list(phases),
                )
            )
        )
    except Exception as error:
        raise WorkerFailure("FE_EQ_WORKER_PHASE_SCOPE_INVALID") from error
    if (
        len(raw_phases) != RAW_PHASE_COUNT
        or len(set(raw_phases)) != len(raw_phases)
        or _phase_digest(raw_phases) != RAW_PHASE_SHA256
        or frozen_filtered_phases != phases
        or _phase_digest(frozen_filtered_phases) != ELIGIBLE_PHASE_SHA256
        or tuple(sorted(set(raw_phases) - set(frozen_filtered_phases))) != ("BCC_A2",)
        or "C15_LAVES" not in frozen_filtered_phases
        or "LIQUID" not in frozen_filtered_phases
        or not projected_phases
        or len(projected_phases) > len(phases)
        or projected_phases != tuple(sorted(set(projected_phases)))
        or not set(projected_phases).issubset(phases)
    ):
        _fail("FE_EQ_WORKER_PHASE_SCOPE_INVALID")
    atomic_masses = _atomic_masses(database)
    mass_to_mole, mole_to_mass = _load_conversion_api()
    try:
        nominal_mole = mass_to_mole(mass_rows, atomic_masses)
        round_trip_mass = mole_to_mass(nominal_mole, atomic_masses)
    except Exception as error:
        raise WorkerFailure("FE_EQ_WORKER_BASIS_CONVERSION_FAILED") from error
    nominal_mole = _normalized_fraction_rows(
        nominal_mole, "FE_EQ_WORKER_BASIS_CONVERSION_FAILED"
    )
    round_trip_mass = _normalized_fraction_rows(
        round_trip_mass, "FE_EQ_WORKER_BASIS_CONVERSION_FAILED"
    )
    round_trip_error = max(
        abs(dict(mass_rows)[element] - dict(round_trip_mass)[element])
        for element in MASS_ORDER
    )
    if not math.isfinite(round_trip_error) or round_trip_error > ROUND_TRIP_TOLERANCE:
        _fail("FE_EQ_WORKER_BASIS_CONVERSION_FAILED")
    submitted, effective_mole, maximum_floor_delta = _effective_mole_rows(
        nominal_mole,
        mass_rows,
        solver_components,
    )
    conditions = {
        variables.N: 1.0,
        variables.P: PRESSURE_PA,
        variables.T: temperature,
    }
    conditions.update(
        {
            variables.X(element): value
            for element, value in submitted
        }
    )
    if len(conditions) != 3 + len(solver_components[:-2]):
        _fail("FE_EQ_WORKER_CONDITION_SCOPE_INVALID")
    try:
        dataset = equilibrium(
            database,
            list(solver_components),
            list(projected_phases),
            conditions,
            calc_opts={"pdens": PDENS},
        )
    except Exception as error:
        raise WorkerFailure(
            "FE_EQ_WORKER_SCIENTIFIC_API_FAILED",
            scientific_api_invoked=True,
            scientific_failure_diagnostic=_scientific_failure_diagnostic(
                error,
                scientific_exception_types,
            ),
            projection_provenance=(solver_components, projected_phases),
        ) from error
    try:
        normalized = _normalize_dataset(
            dataset,
            projected_phases,
            solver_components,
            effective_mole,
        )
        runtime_post_sha256 = hashlib.sha256(runtime_bytes).hexdigest()
        if runtime_post_sha256 != PROFILE_IDENTITIES[profile_id][1]:
            _fail("FE_EQ_WORKER_RUNTIME_IDENTITY_INVALID")
        response = _safety(
            {
                "status": "SUCCESS",
                "failure_code": None,
                "request_id": request_id,
                "profile_id": profile_id,
                "runtime_pre_sha256": PROFILE_IDENTITIES[profile_id][1],
                "runtime_post_sha256": runtime_post_sha256,
                "temperature_k": temperature,
                "pressure_pa": PRESSURE_PA,
                "pdens": PDENS,
                **_projection_fields(solver_components, projected_phases),
                "scientific_api": "pycalphad.equilibrium",
                "scientific_api_call_count": 1,
                "real_equilibrium_executed": True,
                "validation_status": "STRUCTURALLY_AND_NUMERICALLY_VALIDATED",
                "nominal_mass_fractions": [list(row) for row in mass_rows],
                "atomic_masses": [list(row) for row in atomic_masses],
                "nominal_mole_fractions": [list(row) for row in nominal_mole],
                "submitted_non_fe_x": [list(row) for row in submitted],
                "workspace_effective_x_floor": ZERO_FLOOR,
                "workspace_effective_x_ceiling": 1.0 - ZERO_FLOOR,
                "upper_x_clamp_reachable_for_submitted_non_fe": False,
                "runtime_effective_mole_fractions": [
                    list(row) for row in effective_mole
                ],
                "max_nominal_to_effective_abs_delta": maximum_floor_delta,
                "round_trip_mass_fractions": [list(row) for row in round_trip_mass],
                "max_round_trip_abs_error": float(round_trip_error),
                **normalized,
                "convergence_status": "NOT_EXPORTED_BY_DATASET",
                "expected_phase_claim": None,
                "physics_claim": None,
                "raw_xarray_included": False,
                "limitations": [
                    *(
                        ["NUMERICAL_ZERO_FLOOR_APPLIED"]
                        if maximum_floor_delta > 0.0
                        else ["NUMERICAL_ZERO_FLOOR_NOT_APPLIED_TO_THIS_REQUEST"]
                    ),
                    "EXACT_ZERO_COMPONENTS_EXCLUDED_FROM_SOLVER_LOCAL_DIAGNOSTIC",
                    "UPPER_X_CLAMP_UNREACHABLE_BY_EXPLICIT_SUBMISSION_GATE",
                    "CONVERGENCE_STATUS_NOT_EXPORTED",
                    "PRESSURE_DOMAIN_UNKNOWN_BLOCKED",
                    "NOT_NE04_ACCEPTANCE",
                    "NOT_RELEASE_AUTHORIZATION",
                    "NO_EXPECTED_PHASE_OR_PHYSICS_CLAIM",
                ],
            }
        )
        if len(_canonical_bytes(response)) + 1 > 262144:
            _fail("FE_EQ_WORKER_RESPONSE_LIMIT_EXCEEDED")
        return response
    except WorkerFailure as error:
        raise WorkerFailure(error.code, scientific_api_invoked=True) from error
    except Exception as error:
        raise WorkerFailure(
            "FE_EQ_WORKER_INTERNAL_FAILURE",
            scientific_api_invoked=True,
        ) from error


def _failure_response(
    code: str,
    request_id: str | None = None,
    *,
    scientific_api_invoked: bool = False,
    scientific_failure_diagnostic: object = None,
    projection_provenance: object = None,
) -> dict[str, Any]:
    if (
        type(request_id) is not str
        or len(request_id) != 64
        or any(character not in "0123456789abcdef" for character in request_id)
    ):
        request_id = "0" * 64
    normalized_code = WorkerFailure(code).code
    diagnostic_fields: dict[str, Any] = {}
    limitations = [
        "CONVERGENCE_STATUS_NOT_EXPORTED",
        "PRESSURE_DOMAIN_UNKNOWN_BLOCKED",
        "NOT_NE04_ACCEPTANCE",
        "NOT_RELEASE_AUTHORIZATION",
    ]
    if normalized_code == "FE_EQ_WORKER_SCIENTIFIC_API_FAILED":
        if (
            scientific_api_invoked is not True
            or not _valid_scientific_failure_diagnostic(
                scientific_failure_diagnostic
            )
            or not _valid_projection_provenance(projection_provenance)
        ):
            normalized_code = "FE_EQ_WORKER_INTERNAL_FAILURE"
        else:
            category, tokens, fingerprint = scientific_failure_diagnostic
            solver_components, projected_phases = projection_provenance
            diagnostic_fields = {
                "scientific_failure_stage": SCIENTIFIC_FAILURE_STAGE,
                "scientific_api_invocation_count": 1,
                "dataset_returned": False,
                "scientific_failure_category": category,
                "scientific_exception_tokens": list(tokens),
                "scientific_failure_fingerprint_sha256": fingerprint,
                **_projection_fields(solver_components, projected_phases),
            }
            limitations.insert(1, "DIAGNOSTIC_MESSAGE_REDACTED")
    elif scientific_failure_diagnostic is not None:
        normalized_code = "FE_EQ_WORKER_INTERNAL_FAILURE"
    return _safety(
        {
            "status": "FAILURE",
            "failure_code": normalized_code,
            "request_id": request_id,
            "real_equilibrium_executed": scientific_api_invoked is True,
            "raw_exception_included": False,
            "path_included": False,
            "convergence_status": "NOT_EXPORTED_BY_DATASET",
            **diagnostic_fields,
            "limitations": limitations,
        }
    )


def _read_protocol_request() -> dict[str, Any]:
    payload = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(payload) > MAX_INPUT_BYTES:
        _fail("FE_EQ_WORKER_INPUT_LIMIT_EXCEEDED")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except WorkerFailure:
        raise
    except (UnicodeError, json.JSONDecodeError) as error:
        raise WorkerFailure("FE_EQ_WORKER_PROTOCOL_INVALID") from error
    if type(value) is not dict:
        _fail("FE_EQ_WORKER_PROTOCOL_INVALID")
    return value


def main() -> int:
    protocol_stdout = sys.stdout.buffer
    request_id: str | None = None
    sink = _BoundedTextSink(8192)
    try:
        request = _read_protocol_request()
        if type(request.get("request_id")) is str:
            request_id = request["request_id"]
        with redirect_stdout(sink):
            response = _execute_request(request)
    except WorkerFailure as error:
        response = _failure_response(
            error.code,
            request_id,
            scientific_api_invoked=error.scientific_api_invoked,
            scientific_failure_diagnostic=error.scientific_failure_diagnostic,
            projection_provenance=error.projection_provenance,
        )
    except Exception:
        response = _failure_response("FE_EQ_WORKER_INTERNAL_FAILURE", request_id)
    try:
        encoded = _canonical_bytes(response)
        if len(encoded) + 1 > 262144:
            response = _failure_response(
                "FE_EQ_WORKER_RESPONSE_LIMIT_EXCEEDED",
                request_id,
                scientific_api_invoked=(
                    response.get("real_equilibrium_executed") is True
                ),
            )
            encoded = _canonical_bytes(response)
        if len(encoded) + 1 > 262144:
            return 70
        protocol_stdout.write(encoded + b"\n")
        protocol_stdout.flush()
    except Exception:
        return 70
    return 0


if __name__ == "__main__":
    sys.exit(main())
