"""Fail-closed adapter between the compact steel UI and the pinned stdin bridge."""
from __future__ import annotations

import hashlib
import ctypes
import json
import math
import msvcrt
import os
import stat
import subprocess
import threading
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON = PROJECT_ROOT / ".venv-windows" / "Scripts" / "python.exe"
BRIDGE = PROJECT_ROOT / "tools" / "run_ne04_fe_steel_diagnostic.py"
EVIDENCE_ROOT = Path(r"C:\Users\gareg\Documents\Codex\2026-08-26\new-chat\thermogar_r2_evidence\NE04_FE_S2_ACTIVEPROJ_R7_20260827T202952Z")
GATE = EVIDENCE_ROOT / "gate_fix1" / "R7_CONTROL_POINT_GATE_FIX1.json"
CONTROL_RECEIPT = EVIDENCE_ROOT / "actual" / "PATCHED_RESULT.json"
INPUT_SCHEMA = "SWR-NE04-FE-STEEL-DIAGNOSTIC-REQUEST-1"
OUTPUT_SCHEMA = "SWR-NE04-FE-STEEL-DIAGNOSTIC-RESPONSE-1"
MASS_ORDER = (
    "AL", "B", "C", "CO", "CR", "CU", "FE", "H", "HF", "LA", "MN", "MO",
    "N", "NB", "NI", "O", "P", "PD", "S", "SI", "TA", "TI", "V", "W", "Y",
)
NON_FE_ORDER = tuple(element for element in MASS_ORDER if element != "FE")
UPPER_WT_PERCENT = {
    "AL": 3.0, "B": 0.5, "C": 0.5, "CO": 3.0, "CR": 25.0, "CU": 1.0,
    "H": 0.1, "HF": 0.5, "LA": 0.5, "MN": 25.0, "MO": 5.0, "N": 1.0,
    "NB": 1.0, "NI": 26.0, "O": 0.5, "P": 0.05, "PD": 4.0, "S": 0.1,
    "SI": 3.5, "TA": 0.5, "TI": 0.5, "V": 0.5, "W": 3.0, "Y": 0.5,
}
DEFAULT_WT_PERCENT = {element: 0.0 for element in NON_FE_ORDER}
DEFAULT_WT_PERCENT.update({"C": 0.2, "CR": 11.5})
DEFAULT_TEMPERATURE_K = 1200.0
MAX_OUTPUT_BYTES = 262144
TIMEOUT_SECONDS = 330.0
BALANCE_TOLERANCE = 1e-8
ZERO_FLOOR = 1e-10
COMPONENT_PROJECTION_ALGORITHM = "MASS_ORDER_STRICTLY_POSITIVE_NORMALIZED_MASS_V1"
PHASE_PROJECTION_ALGORITHM = "PYCALPHAD_0_11_2_FILTER_PHASES_FROZEN_131_V1"
FROZEN_PHASE_SHA256 = "facf84563f444d5bdca2d16f22689a2e8dd6bc6a331d7f188dfcf4d8f2ed91b4"
ATOMIC_MASS_SHA256 = "b1d3ab2a3c238c00654e32aadce6c14e22af3434349c00e354ef729d8f4014a2"
RUN_LOCK = threading.Lock()
ACTIVE_HELD_PINS: list["HeldPin"] = []
TOP_SUCCESS_KEYS = frozenset({
    "acceptance", "attempts", "claim", "confirmed_executed_attempt_count",
    "counts_toward_ne04_acceptance", "execution_eligible", "execution_eligible_semantic",
    "expected_phase_claim", "failure_code", "limitations",
    "local_diagnostic_execution_capable", "local_diagnostic_execution_permitted",
    "mass_fractions", "path_included", "physics_claim", "post", "pre",
    "pressure_domain_status", "pressure_pa", "production_use", "profile_id",
    "raw_xarray_included", "real_equilibrium_executed",
    "real_equilibrium_execution_status", "release_eligible", "request_sha256",
    "schema_version", "scientific_api_invocation_count", "status", "stderr_included",
    "temperature_k", "validation_status", "worker_response",
})
ATTEMPT_KEYS = frozenset({
    "attempt_number", "duration_seconds", "failure_code", "matched_valid_response",
    "peak_observed_tree_rss_bytes", "process_tree_terminated",
    "real_equilibrium_execution_status", "request_sha256", "return_code", "status",
    "stderr_observed_bytes", "stderr_tail_bytes", "stderr_tail_limit_bytes",
    "stderr_tail_sha256", "stdout_limit_bytes", "stdout_observed_bytes", "stdout_sha256",
    "timeout_seconds", "tree_rss_limit_bytes",
})
WORKER_SUCCESS_KEYS = frozenset({
    "acceptance", "aggregation_semantic", "atomic_masses", "c15_present_in_terminal_rows",
    "c15_scope_included", "claim", "component_bulk_absolute_residuals",
    "component_projection_algorithm", "convergence_status", "counts_toward_ne04_acceptance",
    "dataset_nonvacant_component_axis", "dataset_nonvacant_component_count",
    "dataset_nonvacant_component_sha256", "dataset_vacancy_axis_present", "execution_eligible",
    "execution_eligible_semantic", "expected_phase_claim", "failure_code", "limitations",
    "local_diagnostic_execution_capable", "local_diagnostic_execution_permitted",
    "max_component_bulk_absolute_residual", "max_nominal_to_effective_abs_delta",
    "max_round_trip_abs_error", "nominal_mass_fractions", "nominal_mole_fractions", "pdens",
    "phase_fraction_sum", "phase_projection_algorithm", "physics_claim",
    "pressure_domain_status", "pressure_pa", "production_use", "profile_id",
    "projected_active_phase_count", "projected_active_phase_sha256", "projected_active_phases",
    "raw_active_phase_projection_sha256", "raw_active_phase_row_count",
    "raw_dataset_serialized", "raw_result_row_count", "raw_xarray_included",
    "real_equilibrium_executed", "release_eligible", "request_id",
    "round_trip_mass_fractions", "runtime_effective_bulk_mole_fractions",
    "runtime_effective_mole_fractions", "runtime_post_sha256", "runtime_pre_sha256",
    "schema_version", "scientific_api", "scientific_api_call_count", "solver_component_axis",
    "solver_component_count", "solver_component_sha256", "status", "submitted_non_fe_x",
    "temperature_k", "terminal_phase_row_count", "terminal_phase_rows",
    "upper_x_clamp_reachable_for_submitted_non_fe", "validation_status",
    "workspace_effective_x_ceiling", "workspace_effective_x_floor",
})

PIN_CARDS = (
    (PROJECT_ROOT / "configs/ne04_fe_equilibrium_witness_v1.json", 18796, "a14e6bfec5049347f9bbcb5de43ad1c5b55e31b9de5e5534fac7a119235da27f"),
    (PROJECT_ROOT / "app/thermogar_fe_equilibrium_worker.py", 48278, "7b8c9f4a0293fedd14ac7c95cf45e857e1b39530138fdff1d7f1208a67547a14"),
    (PROJECT_ROOT / "app/thermogar_fe_equilibrium_witness.py", 112669, "bde9bd3af26be7012032d1ef5b36d2053c3f32bd3db8c403edc7b0e021d23e75"),
    (PROJECT_ROOT / "tools/run_ne04_fe_equilibrium_witness.py", 3367, "968715bb5f19180ea121de7419da5c8d725f552a9c9608dfd89919c49ae7e36e"),
    (PROJECT_ROOT / "tools/thermogar_fe_equilibrium_witness_test.py", 45903, "9fde63ee31e9a54881b39822de205ff8b9e28fda6ff834d22633cdab0959b326"),
    (PROJECT_ROOT / "tools/verify_ne04_fe_equilibrium_witness.py", 23065, "7be0fb2356f04634f03b44be202ac17e08702a5faa7d49dbf1b03d106fce5142"),
    (PROJECT_ROOT / "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb", 568690, "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612"),
    (PROJECT_ROOT / "databases/diagnostic/fe/mc_fe_v2062_unpatched_with_mobility.thermogar.tdb", 568418, "f9375c3a7a8649bace698e2177f2cc964bce3f8a19f08ae05d88840abd77b112"),
    (PROJECT_ROOT / "databases/original/fe/mc_fe_v2062.tdb", 489296, "aa02077eac3f602dd7479cbeafb09b450e282716752b3ae2b1fc3a57d9c64865"),
    (PROJECT_ROOT / "app/thermogar_equilibrium_core.py", 27988, "24734a4c404d7a60220f18a956c884e06ff8dfcfec2ecc10b417f912ecf46bd3"),
    (PROJECT_ROOT / "app/thermogar_numerical_grid.py", 19791, "7115ae94edeb7522c40bd8991b70c568f71e80b8dcd20c94277293bcd239e63f"),
    (EVIDENCE_ROOT / "actual/S2_ACTUAL_SCOPE.json", 13567, "3509445070dd3340327f7305551689f5c3724352b0051f5d57af5aa55f662604"),
    (EVIDENCE_ROOT / "actual/verify_s2_actual_receipt.py", 53133, "776544fbfa342c2e35bdf99d99702c31781e0cf560a80359ac483aab1b19e43c"),
    (CONTROL_RECEIPT, 13560, "3c0c27edf2f457bc904450515fad59d4528bafdc55f7855e949c037b7f3743d9"),
    (GATE, 11436, "30351cd5a563ca1ccab844ca0984feb1e82a0b89a0c0dcbb04ac21278ba1b1ce"),
    (PYTHON, 274712, "21bb438c0d4a6f1f164b9a646f6ee000340185e5871180aec06db8d3f07c0082"),
    (BRIDGE, 8728, "6ed2a6369a85b0babd33bbfbc55375e3cb37641893d3acb00ef6a6526812f233"),
)


class SteelAdapterError(Exception):
    pass


if os.name == "nt":
    class _FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
        _fields_ = [("FileAttributes", ctypes.c_uint32), ("ReparseTag", ctypes.c_uint32)]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _CreateFileW = _kernel32.CreateFileW
    _CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    _CreateFileW.restype = ctypes.c_void_p
    _CloseHandle = _kernel32.CloseHandle
    _CloseHandle.argtypes = [ctypes.c_void_p]
    _CloseHandle.restype = ctypes.c_int
    _GetFinalPathNameByHandleW = _kernel32.GetFinalPathNameByHandleW
    _GetFinalPathNameByHandleW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32]
    _GetFinalPathNameByHandleW.restype = ctypes.c_uint32
    _GetFileInformationByHandleEx = _kernel32.GetFileInformationByHandleEx
    _GetFileInformationByHandleEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    _GetFileInformationByHandleEx.restype = ctypes.c_int


def _final_handle_path(handle: int) -> str:
    buffer = ctypes.create_unicode_buffer(32768)
    length = _GetFinalPathNameByHandleW(ctypes.c_void_p(handle), buffer, len(buffer), 0)
    if not 0 < length < len(buffer):
        fail()
    value = buffer.value
    if value.startswith("\\\\?\\"):
        value = value[4:]
    return os.path.normcase(os.path.abspath(value))


def _handle_is_reparse(handle: int) -> bool:
    info = _FILE_ATTRIBUTE_TAG_INFO()
    if not _GetFileInformationByHandleEx(ctypes.c_void_p(handle), 9, ctypes.byref(info), ctypes.sizeof(info)):
        fail()
    return bool(info.FileAttributes & 0x00000400)


class HeldPin:
    def __init__(self, path: Path, expected_bytes: int, expected_sha256: str) -> None:
        if os.name != "nt" or not path.is_file() or path.is_symlink() or not plain(path):
            fail()
        raw = _CreateFileW(str(path), 0x80000000, 0x00000001, None, 3, 0x00000080 | 0x00200000, None)
        if raw in (None, ctypes.c_void_p(-1).value):
            fail()
        self.fd = -1
        try:
            if _handle_is_reparse(int(raw)) or _final_handle_path(int(raw)) != os.path.normcase(os.path.abspath(path)):
                fail()
            self.fd = msvcrt.open_osfhandle(int(raw), os.O_RDONLY | getattr(os, "O_BINARY", 0))
            raw = None
            self.identity = os.fstat(self.fd)
            self.path = path
            self.expected_bytes = expected_bytes
            self.expected_sha256 = expected_sha256
            self.closed = False
            self.recheck()
        except Exception:
            if self.fd >= 0:
                os.close(self.fd)
                self.fd = -1
            raise
        finally:
            if raw not in (None, ctypes.c_void_p(-1).value):
                _CloseHandle(ctypes.c_void_p(raw))

    def recheck(self) -> None:
        if self.fd < 0 or self.closed:
            fail()
        os.lseek(self.fd, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        total = 0
        while total <= self.expected_bytes:
            chunk = os.read(self.fd, min(65536, self.expected_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        payload = b"".join(chunks)
        current = os.fstat(self.fd)
        if (
            len(payload) != self.expected_bytes
            or hashlib.sha256(payload).hexdigest() != self.expected_sha256
            or not os.path.samestat(self.identity, current)
            or _handle_is_reparse(msvcrt.get_osfhandle(self.fd))
            or _final_handle_path(msvcrt.get_osfhandle(self.fd))
            != os.path.normcase(os.path.abspath(self.path))
        ):
            fail()

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        self.closed = True


class HeldDirectory:
    def __init__(self, path: Path) -> None:
        if os.name != "nt" or not path.is_dir() or path.is_symlink() or not plain(path):
            fail()
        raw = _CreateFileW(str(path), 0x80000000, 0x00000001, None, 3, 0x02000000 | 0x00200000, None)
        if raw in (None, ctypes.c_void_p(-1).value):
            fail()
        try:
            if _handle_is_reparse(int(raw)) or _final_handle_path(int(raw)) != os.path.normcase(os.path.abspath(path)):
                fail()
        except Exception:
            _CloseHandle(ctypes.c_void_p(raw))
            raise
        self.handle = int(raw)
        self.path = path
        self.closed = False

    def recheck(self) -> None:
        if (
            self.closed or _handle_is_reparse(self.handle)
            or _final_handle_path(self.handle) != os.path.normcase(os.path.abspath(self.path))
        ):
            fail()

    def close(self) -> None:
        if not self.closed:
            _CloseHandle(ctypes.c_void_p(self.handle))
        self.closed = True


def fail() -> None:
    raise SteelAdapterError("Локальный расчёт недоступен.")


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("ascii") + b"\n"


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            fail()
        result[key] = value
    return result


def _constant(_: str) -> object:
    fail()


def plain(path: Path) -> bool:
    return all(
        not (part.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        for part in (path, *path.parents) if part.exists()
    )


def stable_bytes(path: Path, expected_bytes: int, expected_sha256: str) -> bytes:
    try:
        if not path.is_file() or path.is_symlink() or not plain(path):
            fail()
        before = path.lstat()
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        try:
            opened = os.fstat(descriptor)
            chunks: list[bytes] = []
            total = 0
            while total <= expected_bytes:
                chunk = os.read(descriptor, min(65536, expected_bytes + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk); total += len(chunk)
            after_fd = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        after = path.lstat()
        payload = b"".join(chunks)
        if (
            len(payload) != expected_bytes or hashlib.sha256(payload).hexdigest() != expected_sha256
            or not os.path.samestat(before, opened) or not os.path.samestat(opened, after_fd)
            or not os.path.samestat(before, after)
        ):
            fail()
        return payload
    except (OSError, ValueError, TypeError):
        fail()


def verify_pins() -> str:
    rows = []
    for path, size, digest_value in PIN_CARDS:
        stable_bytes(path, size, digest_value)
        rows.append([str(path), size, digest_value])
    return hashlib.sha256(canonical(rows)).hexdigest()


def parse_canonical(payload: bytes, maximum: int = MAX_OUTPUT_BYTES) -> dict[str, object]:
    if not payload or len(payload) > maximum or b"\r" in payload or payload.count(b"\n") != 1 or not payload.endswith(b"\n"):
        fail()
    try:
        value = json.loads(payload[:-1].decode("ascii"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        fail()
    try:
        normalized = canonical(value)
    except (ValueError, TypeError):
        fail()
    if type(value) is not dict or normalized != payload:
        fail()
    return value


def build_request(wt_percent: dict[str, object], temperature_k: object) -> tuple[bytes, dict[str, float], float]:
    if type(wt_percent) is not dict or tuple(wt_percent) != NON_FE_ORDER:
        fail()
    values: dict[str, float] = {}
    for element in NON_FE_ORDER:
        value = wt_percent[element]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            fail()
        number = float(value)
        if not math.isfinite(number) or number < 0.0 or number >= UPPER_WT_PERCENT[element]:
            fail()
        values[element] = number
    if isinstance(temperature_k, bool) or not isinstance(temperature_k, (int, float)):
        fail()
    temperature = float(temperature_k)
    if not math.isfinite(temperature) or not 673.0 <= temperature <= 2000.0:
        fail()
    fe_wt = 100.0 - math.fsum(values.values())
    if not math.isfinite(fe_wt) or fe_wt <= 0.0:
        fail()
    mass = {element: (fe_wt if element == "FE" else values[element]) * 0.01 for element in MASS_ORDER}
    rows = [[element, mass[element]] for element in MASS_ORDER]
    request = {"schema_version": INPUT_SCHEMA, "mass_fractions": rows, "temperature_k": temperature}
    return canonical(request), mass, temperature


def input_signature(wt_percent: dict[str, object], temperature_k: object, pin_signature: str) -> str:
    request, _mass, _temperature = build_request(wt_percent, temperature_k)
    return hashlib.sha256(request + pin_signature.encode("ascii")).hexdigest()


def _mass_rows(value: object, expected: dict[str, float]) -> None:
    if type(value) is not list or len(value) != len(MASS_ORDER):
        fail()
    for (element, expected_value), row in zip(expected.items(), value, strict=True):
        if type(row) is not list or len(row) != 2 or row[0] != element or row[1] != expected_value:
            fail()


def _numeric_rows(value: object) -> dict[str, float]:
    if type(value) is not list or len(value) != len(MASS_ORDER):
        fail()
    result: dict[str, float] = {}
    for element, row in zip(MASS_ORDER, value, strict=True):
        if type(row) is not list or len(row) != 2 or row[0] != element:
            fail()
        number = row[1]
        if (
            isinstance(number, bool) or not isinstance(number, (int, float))
            or not math.isfinite(float(number)) or float(number) < 0.0
        ):
            fail()
        if float(number) == 0.0 and math.copysign(1.0, float(number)) < 0.0:
            fail()
        result[element] = float(number)
    return result


def _phase_digest(values: tuple[str, ...]) -> str:
    return hashlib.sha256("".join(f"{value}\n" for value in values).encode("utf-8")).hexdigest()


def _json_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()


def _frozen_phases() -> tuple[str, ...]:
    path, size, digest = PIN_CARDS[0]
    payload = stable_bytes(path, size, digest)
    try:
        config = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
        selection = config["request_contract"]["phase_selection"]
        phases_raw = selection["phases"]
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        fail()
    if (
        type(phases_raw) is not list or any(type(value) is not str for value in phases_raw)
        or len(phases_raw) != 131 or phases_raw != sorted(set(phases_raw))
    ):
        fail()
    phases = tuple(phases_raw)
    if (
        _phase_digest(phases) != FROZEN_PHASE_SHA256
        or selection.get("sha256") != FROZEN_PHASE_SHA256
        or selection.get("count") != 131
        or selection.get("active_projection_algorithm") != PHASE_PROJECTION_ALGORITHM
        or selection.get("c15_laves_mandatory") is not True
        or selection.get("liquid_mandatory") is not True
        or "C15_LAVES" not in phases or "LIQUID" not in phases or "BCC_A2" in phases
    ):
        fail()
    return phases


def _validate_scientific_binding(worker: dict[str, object], mass: dict[str, float]) -> None:
    if (
        worker.get("scientific_api") != "pycalphad.equilibrium" or worker.get("pdens") != 25
        or worker.get("component_projection_algorithm") != COMPONENT_PROJECTION_ALGORITHM
        or worker.get("phase_projection_algorithm") != PHASE_PROJECTION_ALGORITHM
    ):
        fail()
    active_non_fe = tuple(element for element in NON_FE_ORDER if mass[element] > 0.0)
    inactive_non_fe = tuple(element for element in NON_FE_ORDER if element not in active_non_fe)
    solver = (*active_non_fe, "FE", "VA")
    dataset_axis = (*active_non_fe, "FE")
    if (
        worker.get("solver_component_axis") != list(solver)
        or worker.get("solver_component_count") != len(solver)
        or worker.get("solver_component_sha256") != _phase_digest(solver)
        or worker.get("dataset_nonvacant_component_axis") != list(dataset_axis)
        or worker.get("dataset_nonvacant_component_count") != len(dataset_axis)
        or worker.get("dataset_nonvacant_component_sha256") != _phase_digest(dataset_axis)
        or type(worker.get("dataset_vacancy_axis_present")) is not bool
    ):
        fail()
    projected_raw = worker.get("projected_active_phases")
    frozen = _frozen_phases()
    if (
        type(projected_raw) is not list or any(type(value) is not str for value in projected_raw)
        or not projected_raw or projected_raw != sorted(set(projected_raw))
    ):
        fail()
    projected = tuple(projected_raw)
    if (
        not set(projected).issubset(frozen)
        or worker.get("projected_active_phase_count") != len(projected)
        or worker.get("projected_active_phase_sha256") != _phase_digest(projected)
        or "C15_LAVES" not in projected or "LIQUID" not in projected
    ):
        fail()
    atomic = _numeric_rows(worker.get("atomic_masses"))
    if any(value <= 0.0 for value in atomic.values()) or _json_digest([[element, atomic[element]] for element in MASS_ORDER]) != ATOMIC_MASS_SHA256:
        fail()
    mole_terms = {element: mass[element] / atomic[element] for element in MASS_ORDER}
    mole_total = math.fsum(mole_terms.values())
    nominal_expected = {element: mole_terms[element] / mole_total for element in MASS_ORDER}
    nominal = _numeric_rows(worker.get("nominal_mole_fractions"))
    if any(abs(nominal[element] - nominal_expected[element]) > 1e-15 for element in MASS_ORDER):
        fail()
    submitted = worker.get("submitted_non_fe_x")
    if type(submitted) is not list or len(submitted) != len(active_non_fe):
        fail()
    for element, row in zip(active_non_fe, submitted, strict=True):
        if type(row) is not list or row != [element, nominal[element]]:
            fail()
    expected_effective = {element: max(nominal[element], ZERO_FLOOR) for element in active_non_fe}
    expected_effective.update({element: 0.0 for element in inactive_non_fe})
    expected_effective["FE"] = 1.0 - math.fsum(expected_effective.values())
    effective = _numeric_rows(worker.get("runtime_effective_mole_fractions"))
    if any(abs(effective[element] - expected_effective[element]) > 1e-15 for element in MASS_ORDER):
        fail()
    rows = worker.get("terminal_phase_rows")
    if type(rows) is not list or not rows:
        fail()
    bulk = {element: 0.0 for element in MASS_ORDER}
    names: list[str] = []
    fraction_sum = 0.0
    raw_vertex_total = 0
    for row in rows:
        if type(row) is not dict or set(row) != {"phase", "fraction", "chemical_coordinates", "vacancy_coordinate", "raw_vertex_count"}:
            fail()
        name, fraction = row["phase"], row["fraction"]
        coordinates = _numeric_rows(row["chemical_coordinates"])
        vacancy = row["vacancy_coordinate"]
        if worker["dataset_vacancy_axis_present"]:
            if (
                isinstance(vacancy, bool) or not isinstance(vacancy, (int, float))
                or not math.isfinite(float(vacancy)) or not 0.0 <= float(vacancy) <= 1.0
                or (float(vacancy) == 0.0 and math.copysign(1.0, float(vacancy)) < 0.0)
            ):
                fail()
            vacancy_value = float(vacancy)
        else:
            if vacancy is not None:
                fail()
            vacancy_value = 0.0
        if (
            type(name) is not str or name not in projected
            or isinstance(fraction, bool) or not isinstance(fraction, (int, float))
            or not math.isfinite(float(fraction)) or float(fraction) <= 0.0
            or type(row["raw_vertex_count"]) is not int or row["raw_vertex_count"] <= 0
            or abs(math.fsum(coordinates.values()) + vacancy_value - 1.0) > BALANCE_TOLERANCE
            or any(value > 1.0 for value in coordinates.values())
            or any(coordinates[element] != 0.0 for element in inactive_non_fe)
        ):
            fail()
        names.append(name)
        fraction_sum += float(fraction)
        raw_vertex_total += row["raw_vertex_count"]
        for element in MASS_ORDER:
            bulk[element] += float(fraction) * coordinates[element]
    if (
        names != sorted(set(names)) or abs(fraction_sum - 1.0) > BALANCE_TOLERANCE
        or raw_vertex_total != worker.get("raw_active_phase_row_count")
        or worker.get("terminal_phase_row_count") != len(rows)
        or worker.get("c15_scope_included") is not ("C15_LAVES" in projected)
        or worker.get("c15_present_in_terminal_rows") is not ("C15_LAVES" in names)
    ):
        fail()
    reported_bulk = _numeric_rows(worker.get("runtime_effective_bulk_mole_fractions"))
    reported_residuals = _numeric_rows(worker.get("component_bulk_absolute_residuals"))
    expected_residuals = {element: abs(bulk[element] - expected_effective[element]) for element in MASS_ORDER}
    maximum_residual = max(expected_residuals.values())
    maximum_reported = worker.get("max_component_bulk_absolute_residual")
    if (
        maximum_residual > BALANCE_TOLERANCE
        or any(abs(reported_bulk[element] - bulk[element]) > 1e-15 for element in MASS_ORDER)
        or any(abs(reported_residuals[element] - expected_residuals[element]) > 1e-15 for element in MASS_ORDER)
        or isinstance(maximum_reported, bool) or not isinstance(maximum_reported, (int, float))
        or not math.isfinite(float(maximum_reported)) or abs(float(maximum_reported) - maximum_residual) > 1e-15
    ):
        fail()


def _safe_flags(value: dict[str, object]) -> None:
    if (
        value.get("acceptance") is not False or value.get("release_eligible") is not False
        or value.get("production_use") != "DENIED" or value.get("expected_phase_claim") is not None
        or value.get("physics_claim") is not None
    ):
        fail()


def validate_success_envelope(
    envelope: dict[str, object], request_payload: bytes, mass: dict[str, float], temperature: float
) -> dict[str, object]:
    if set(envelope) != {
        "schema_version", "status", "failure_code", "input_sha256", "profile_id",
        "controller_call_count", "receipt", "acceptance", "release_eligible", "production_use",
    }:
        fail()
    if (
        envelope["schema_version"] != OUTPUT_SCHEMA or envelope["status"] != "SUCCESS"
        or envelope["failure_code"] is not None or envelope["input_sha256"] != hashlib.sha256(request_payload).hexdigest()
        or envelope["profile_id"] != "thermogar_patch" or type(envelope["controller_call_count"]) is not int
        or envelope["controller_call_count"] != 1 or envelope["acceptance"] is not False
        or envelope["release_eligible"] is not False or envelope["production_use"] != "DENIED"
    ):
        fail()
    receipt = envelope["receipt"]
    if (
        type(receipt) is not dict or set(receipt) != TOP_SUCCESS_KEYS
        or receipt.get("status") != "SUCCESS" or receipt.get("profile_id") != "thermogar_patch"
    ):
        fail()
    _safe_flags(receipt)
    if (
        receipt.get("temperature_k") != temperature or receipt.get("pressure_pa") != 101325.0
        or receipt.get("real_equilibrium_execution_status") != "CONFIRMED_EXECUTED"
        or receipt.get("confirmed_executed_attempt_count") != 1
        or receipt.get("scientific_api_invocation_count") != 1
        or receipt.get("validation_status") != "STRUCTURALLY_AND_NUMERICALLY_VALIDATED"
    ):
        fail()
    _mass_rows(receipt.get("mass_fractions"), mass)
    pre, post = receipt.get("pre"), receipt.get("post")
    if (
        type(pre) is not dict or type(post) is not dict
        or set(pre) != {"stage", "request_sha256", "observations"}
        or set(post) != {"stage", "request_sha256", "observations"}
        or pre.get("stage") != "PRE" or post.get("stage") != "POST"
    ):
        fail()
    pre_copy, post_copy = dict(pre), dict(post)
    pre_copy["stage"] = "SAME"; post_copy["stage"] = "SAME"
    if pre_copy != post_copy or pre.get("request_sha256") != receipt.get("request_sha256"):
        fail()
    attempts = receipt.get("attempts")
    if type(attempts) is not list or len(attempts) != 1:
        fail()
    attempt = attempts[0]
    if (
        type(attempt) is not dict or set(attempt) != ATTEMPT_KEYS or attempt.get("status") != "SUCCESS"
        or attempt.get("matched_valid_response") is not True
        or attempt.get("real_equilibrium_execution_status") != "CONFIRMED_EXECUTED"
    ):
        fail()
    worker = receipt.get("worker_response")
    if (
        type(worker) is not dict or set(worker) != WORKER_SUCCESS_KEYS
        or worker.get("status") != "SUCCESS" or worker.get("profile_id") != "thermogar_patch"
    ):
        fail()
    _safe_flags(worker)
    _mass_rows(worker.get("nominal_mass_fractions"), mass)
    if (
        worker.get("temperature_k") != temperature or worker.get("pressure_pa") != 101325.0
        or worker.get("scientific_api_call_count") != 1
        or worker.get("real_equilibrium_executed") is not True
        or worker.get("validation_status") != "STRUCTURALLY_AND_NUMERICALLY_VALIDATED"
        or worker.get("c15_scope_included") is not True
    ):
        fail()
    _validate_scientific_binding(worker, mass)
    delta = worker.get("max_nominal_to_effective_abs_delta")
    if isinstance(delta, bool) or not isinstance(delta, (int, float)) or not math.isfinite(float(delta)) or float(delta) < 0.0:
        fail()
    nominal = _numeric_rows(worker.get("nominal_mole_fractions"))
    effective = _numeric_rows(worker.get("runtime_effective_mole_fractions"))
    recomputed_delta = max(abs(nominal[element] - effective[element]) for element in MASS_ORDER)
    if float(delta) != recomputed_delta:
        fail()
    expected_first = "NUMERICAL_ZERO_FLOOR_APPLIED" if float(delta) > 0.0 else "NUMERICAL_ZERO_FLOOR_NOT_APPLIED_TO_THIS_REQUEST"
    expected_limits = [
        expected_first, "EXACT_ZERO_COMPONENTS_EXCLUDED_FROM_SOLVER_LOCAL_DIAGNOSTIC",
        "UPPER_X_CLAMP_UNREACHABLE_BY_EXPLICIT_SUBMISSION_GATE", "CONVERGENCE_STATUS_NOT_EXPORTED",
        "PRESSURE_DOMAIN_UNKNOWN_BLOCKED", "NOT_NE04_ACCEPTANCE", "NOT_RELEASE_AUTHORIZATION",
        "NO_EXPECTED_PHASE_OR_PHYSICS_CLAIM",
    ]
    if worker.get("limitations") != expected_limits or receipt.get("limitations") != expected_limits:
        fail()
    rows = worker.get("terminal_phase_rows")
    if type(rows) is not list or not rows:
        fail()
    output_rows = []
    names = []
    fraction_sum = 0.0
    for row in rows:
        if type(row) is not dict or set(row) != {"phase", "fraction", "chemical_coordinates", "vacancy_coordinate", "raw_vertex_count"}:
            fail()
        name, fraction = row["phase"], row["fraction"]
        if type(name) is not str or isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not math.isfinite(float(fraction)) or float(fraction) <= 0.0:
            fail()
        names.append(name); fraction_sum += float(fraction)
        output_rows.append({"phase": name, "fraction": float(fraction)})
    if names != sorted(set(names)) or abs(fraction_sum - 1.0) > BALANCE_TOLERANCE:
        fail()
    c15 = "C15_LAVES" in names
    phase_sum = worker.get("phase_fraction_sum")
    if (
        worker.get("terminal_phase_row_count") != len(rows)
        or isinstance(phase_sum, bool) or not isinstance(phase_sum, (int, float))
        or not math.isfinite(float(phase_sum)) or float(phase_sum) != fraction_sum
        or worker.get("c15_present_in_terminal_rows") is not c15
    ):
        fail()
    return {"terminal_rows": output_rows, "c15_observed": c15, "control_point_proof": False}


def run_diagnostic(
    wt_percent: dict[str, object], temperature_k: object, *,
    process_runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
    current_signature: Callable[[], str] | None = None,
) -> dict[str, object]:
    if not RUN_LOCK.acquire(blocking=False):
        raise SteelAdapterError("Расчёт уже выполняется.")
    held: list[HeldPin | HeldDirectory] = []
    try:
        request, mass, temperature = build_request(wt_percent, temperature_k)
        pin_signature = verify_pins()
        signature = hashlib.sha256(request + pin_signature.encode("ascii")).hexdigest()
        bridge_card = next(card for card in PIN_CARDS if card[0] == BRIDGE)
        python_card = next(card for card in PIN_CARDS if card[0] == PYTHON)
        directory_paths = (PROJECT_ROOT, PROJECT_ROOT / ".venv-windows", PYTHON.parent, BRIDGE.parent)
        unique_directories = tuple(dict.fromkeys(Path(os.path.abspath(path)) for path in directory_paths))
        for path in unique_directories:
            held.append(HeldDirectory(path))
        held.append(HeldPin(*python_card))
        held.append(HeldPin(*bridge_card))
        ACTIVE_HELD_PINS[:] = [item for item in held if isinstance(item, HeldPin)]
        for item in held:
            item.recheck()
        completed = process_runner(
            [str(PYTHON), "-I", "-B", str(BRIDGE)], input=request, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=TIMEOUT_SECONDS, check=False, shell=False,
        )
        if len(completed.stdout) > MAX_OUTPUT_BYTES or len(completed.stderr) > 8192:
            fail()
        envelope = parse_canonical(completed.stdout)
        if completed.returncode != 0 or envelope.get("status") != "SUCCESS":
            fail()
        result = validate_success_envelope(envelope, request, mass, temperature)
        if current_signature is not None and current_signature() != signature:
            raise SteelAdapterError("Результат устарел.")
        return {**result, "signature": signature}
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        fail()
    finally:
        for item in reversed(held):
            item.close()
        ACTIVE_HELD_PINS.clear()
        RUN_LOCK.release()


def load_control_point_view() -> dict[str, object]:
    verify_pins()
    gate = parse_canonical(stable_bytes(GATE, 11436, "30351cd5a563ca1ccab844ca0984feb1e82a0b89a0c0dcbb04ac21278ba1b1ce"), 65536)
    if (
        gate.get("validation_semantic") != "VIRTUAL_LIMITATION_NORMALIZATION_SELF_CONSISTENCY_ONLY"
        or gate.get("patched_gate_equivalent") is not False or gate.get("acceptance") is not False
        or gate.get("release_eligible") is not False or gate.get("production_use") != "DENIED"
        or gate.get("original_receipt_sha256") != "3c0c27edf2f457bc904450515fad59d4528bafdc55f7855e949c037b7f3743d9"
        or gate.get("scope_sha256") != "3509445070dd3340327f7305551689f5c3724352b0051f5d57af5aa55f662604"
    ):
        fail()
    receipt_payload = stable_bytes(CONTROL_RECEIPT, 13560, "3c0c27edf2f457bc904450515fad59d4528bafdc55f7855e949c037b7f3743d9")
    receipt = parse_canonical(receipt_payload)
    _request, mass, temperature = build_request(dict(DEFAULT_WT_PERCENT), DEFAULT_TEMPERATURE_K)
    envelope = {
        "schema_version": OUTPUT_SCHEMA, "status": "SUCCESS", "failure_code": None,
        "input_sha256": hashlib.sha256(_request).hexdigest(), "profile_id": "thermogar_patch",
        "controller_call_count": 1, "receipt": receipt, "acceptance": False,
        "release_eligible": False, "production_use": "DENIED",
    }
    result = validate_success_envelope(envelope, _request, mass, temperature)
    return {**result, "control_point_proof": True, "signature": hashlib.sha256(receipt_payload + stable_bytes(GATE, 11436, "30351cd5a563ca1ccab844ca0984feb1e82a0b89a0c0dcbb04ac21278ba1b1ce")).hexdigest()}
