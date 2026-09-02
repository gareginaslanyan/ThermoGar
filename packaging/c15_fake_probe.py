from __future__ import annotations

import ast
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import re
import sys
import time


sys.dont_write_bytecode = True

P0_ROOT = "42455F51E284BAD35F5BFD4971F5099889A2A0D4518FFB95310FC5C400461F7F"
RUNTIME_ROOT = "58F81C014DF3C3E8AA6F85517BCEE4263C0AE751365B53CA0ED197964538121C"
NATIVE_ROOT = "A08EC90744637E0CFE3F7E72D8F4564F58D37C190704B660F4267AF02616604C"
TRUST_MANIFEST_REL = "manifests/runtime-trust-manifest.json"
TRUST_RECEIPT_REL = "manifests/runtime-trust-manifest.receipt.json"
EXPECTED_TRUST_PRODUCER_SHA256 = "762ABCDA551B6BE81B2728D5814E14EA0FB18B5ABC249E12DCD739D04CE779C0"
EXPECTED_TRUST_VERIFIER_SHA256 = "B6FDCA5AFAC6E365818C127DB51DBE8E38824B6A60E84818998BDA3544DDBF79"
EXPECTED_EXECUTION_ROWS = 15035
EXPECTED_PROJECT_ROWS = 29
EXPECTED_PROJECT_BYTES = 2674489
EXPECTED_RUNTIME_ROWS = 15003
EXPECTED_RUNTIME_BYTES = 575844438
HELPERS = {"launcher.pyw", "stop.pyw", "healthcheck.py"}
FIXTURE_BYTES = 814
FIXTURE_SHA256 = "C2D8C46E4B4D2098B924447C974F4B6F5FB9301CA06D61D2CF89C1043F4B2E92"
SUCCESS_SHA256 = "D9B4D22600D037A9C8F049D15E74C71AEF06AF206DE82027D0E993E0CCF0DAB1"
SOURCE_PINS = {
    "app/ThermoGar_app.py": (430274, "7008975720C0EBFDF2D087BCAFE235437D17EC41BC75ED7202B0EBFD8D16A931"),
    "app/thermogar_verified_loaders.py": (92357, "4186E6A4F9AED53EEEEA36BBB72A0B18FD4326A473948FFC82A3B65C0B7F88B8"),
    "app/thermogar_verified_properties.py": (44313, "9C9AC7A4A04C6EE39A066802615E73EA0FBE4A69444C721B4567CDF340308D0A"),
    "app/thermogar_verified_state.py": (52698, "45FFD8AFE5539CA21F21EAF17DA4378142BA88F973D8E346818905E539A2DBFC"),
}
SUCCESS = {
    "schema": 1,
    "status": "C15_REJECTED",
    "feature_id": "property_elastic_prepare",
    "base_key": "fe",
    "profile_key": "thermogar_patch",
    "requested_phase": "C15_LAVES",
    "decision_code": "C15_PHASE_REJECTED",
    "pdb_parser_calls": 0,
    "tdb_parser_calls": 0,
    "backend_calls": 0,
    "state_writes": 0,
    "artifact_writes": 0,
}
FAILURE = {
    2: "USAGE",
    3: "FIXTURE_INVALID",
    4: "RUNTIME_TRUST_INVALID",
    5: "SOURCE_IDENTITY_INVALID",
    6: "C15_PREDICATE_FAILED",
    7: "OUTPUT_SCHEMA_INVALID",
    8: "TIMEOUT",
    9: "INTERNAL_ERROR",
}
SHA_RE = re.compile(r"^[0-9A-F]{64}$")

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_NORMAL = 0x80
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
DRIVE_FIXED = 3

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class FILETIME(ctypes.Structure):
    _fields_ = (("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD))


class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = (
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", FILETIME),
        ("ftLastAccessTime", FILETIME),
        ("ftLastWriteTime", FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    )


kernel32.CreateFileW.argtypes = (
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
)
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetFileInformationByHandle.argtypes = (
    wintypes.HANDLE, ctypes.POINTER(BY_HANDLE_FILE_INFORMATION),
)
kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
kernel32.GetFinalPathNameByHandleW.argtypes = (
    wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
)
kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
kernel32.GetDriveTypeW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetDriveTypeW.restype = wintypes.UINT
kernel32.ReadFile.argtypes = (
    wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
)
kernel32.ReadFile.restype = wintypes.BOOL


class ProbeError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(FAILURE.get(code, "INTERNAL_ERROR"))
        self.code = code


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _emit(value: dict[str, object]) -> None:
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        stream.write(_canonical(value)); stream.flush()


def _fail(code: int) -> int:
    if code not in FAILURE:
        code = 9
    _emit({"schema": 1, "status": FAILURE[code], "detail_code": code})
    return code


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(raw: bytes, maximum: int, keys: tuple[str, ...]) -> dict[str, object]:
    if not raw or len(raw) > maximum or raw.startswith(b"\xef\xbb\xbf") or raw.endswith((b"\r", b"\n")):
        raise ValueError("JSON framing")
    value = json.loads(
        raw.decode("utf-8", "strict"), object_pairs_hook=_pairs,
        parse_constant=lambda _x: (_ for _ in ()).throw(ValueError("JSON constant")),
    )
    if not isinstance(value, dict) or tuple(value.keys()) != keys or _canonical(value) != raw:
        raise ValueError("canonical JSON")
    return value


def _normal(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _under(root: str, path: str) -> bool:
    try:
        return os.path.commonpath((_normal(root), _normal(path))) == _normal(root)
    except ValueError:
        return False


def _check_deadline(deadline: float | None) -> None:
    if deadline is not None and time.monotonic() > deadline:
        raise ProbeError(8)


def _fixed_local_path(value: str) -> str:
    if not value or value.startswith(("\\\\", "\\\\?\\", "\\\\.\\")) or not os.path.isabs(value):
        raise ValueError("local absolute path")
    drive, tail = os.path.splitdrive(value)
    if len(drive) != 2 or drive[1] != ":" or not tail.startswith(("\\", "/")) or ":" in tail:
        raise ValueError("drive-qualified path")
    normal = _normal(value)
    normalized_drive, normalized_tail = os.path.splitdrive(normal)
    if normalized_drive.casefold() != drive.casefold() or not normalized_tail.startswith("\\"):
        raise ValueError("fixed drive path")
    if kernel32.GetDriveTypeW(drive.upper() + "\\") != DRIVE_FIXED:
        raise ValueError("fixed drive required")
    return normal


def _close(handle: int | None) -> None:
    if handle not in (None, 0, INVALID_HANDLE_VALUE):
        kernel32.CloseHandle(handle)


def _strip_extended(path: str) -> str:
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\"):
        return path[4:]
    return path


def _open_held(
    path: str,
    maximum: int,
    root: str | None = None,
    deadline: float | None = None,
) -> dict[str, object]:
    _check_deadline(deadline)
    expected = _normal(path)
    if root is not None and not _under(root, expected):
        raise ValueError("path escape")
    handle = kernel32.CreateFileW(
        expected, GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error(), "CreateFileW")
    try:
        _check_deadline(deadline)
        capacity = 32768; buffer = ctypes.create_unicode_buffer(capacity)
        length = kernel32.GetFinalPathNameByHandleW(handle, buffer, capacity, 0)
        if length == 0 or length >= capacity:
            raise OSError(ctypes.get_last_error(), "GetFinalPathNameByHandleW")
        final = _normal(_strip_extended(buffer.value))
        if final != expected or (root is not None and not _under(root, final)):
            raise ValueError("final path")
        info = BY_HANDLE_FILE_INFORMATION()
        if not kernel32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise OSError(ctypes.get_last_error(), "GetFileInformationByHandle")
        if info.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT | FILE_ATTRIBUTE_DIRECTORY):
            raise ValueError("plain file required")
        size = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
        if size < 0 or size > maximum:
            raise ValueError("file size")
        chunks: list[bytes] = []; remaining = size
        while remaining:
            _check_deadline(deadline)
            request = min(1024 * 1024, remaining)
            chunk = ctypes.create_string_buffer(request); received = wintypes.DWORD(0)
            if not kernel32.ReadFile(handle, chunk, request, ctypes.byref(received), None):
                raise OSError(ctypes.get_last_error(), "ReadFile")
            if received.value == 0 or received.value > request:
                raise ValueError("short read")
            chunks.append(chunk.raw[:received.value]); remaining -= received.value
        extra = ctypes.create_string_buffer(1); received = wintypes.DWORD(0)
        if not kernel32.ReadFile(handle, extra, 1, ctypes.byref(received), None) or received.value != 0:
            raise ValueError("EOF")
        raw = b"".join(chunks)
        _check_deadline(deadline)
        return {
            "handle": handle, "path": final, "raw": raw, "bytes": size,
            "sha256": hashlib.sha256(raw).hexdigest().upper(),
            "volume": int(info.dwVolumeSerialNumber),
            "index": (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
        }
    except Exception:
        _close(handle)
        raise


def _relative(value: object) -> str:
    if not isinstance(value, str) or not value or len(value) > 1024 or "\\" in value or ":" in value or "\x00" in value:
        raise ValueError("relative path")
    if any(not part or part in (".", "..") for part in value.split("/")):
        raise ValueError("relative path")
    return value


def _integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("integer")
    return value


def _validate_runtime_trust(install_root: str, deadline: float) -> dict[str, tuple[int, str]]:
    _check_deadline(deadline)
    manifest_file = _open_held(
        os.path.join(install_root, *TRUST_MANIFEST_REL.split("/")),
        64 * 1024 * 1024,
        install_root,
        deadline,
    )
    receipt_file: dict[str, object] | None = None
    try:
        manifest = _json(manifest_file["raw"], 64 * 1024 * 1024, (
            "schema", "version", "algorithm", "p0_root_sha256",
            "runtime_input_root_sha256", "native_closure_root_sha256",
            "rows", "execution_root_sha256",
        ))
        if type(manifest["schema"]) is not int or manifest["schema"] != 1 or type(manifest["version"]) is not int or manifest["version"] != 1 or manifest["algorithm"] != "SHA-256":
            raise ValueError("manifest metadata")
        if manifest["p0_root_sha256"] != P0_ROOT or manifest["runtime_input_root_sha256"] != RUNTIME_ROOT or manifest["native_closure_root_sha256"] != NATIVE_ROOT:
            raise ValueError("manifest anchors")
        rows = manifest["rows"]
        if not isinstance(rows, list) or len(rows) != EXPECTED_EXECUTION_ROWS:
            raise ValueError("row count")
        row_map: dict[str, tuple[int, str]] = {}
        previous: str | None = None; folded: set[str] = set()
        all_literals: list[str] = []; project_literals: list[str] = []; runtime_literals: list[str] = []
        project_bytes = 0; runtime_bytes = 0; total = 0; helpers: set[str] = set()
        for row in rows:
            _check_deadline(deadline)
            if not isinstance(row, dict) or tuple(row.keys()) != ("path", "bytes", "sha256"):
                raise ValueError("row schema")
            path = _relative(row["path"]); count = _integer(row["bytes"], 0, (1 << 63) - 1); sha = row["sha256"]
            if not isinstance(sha, str) or SHA_RE.fullmatch(sha) is None:
                raise ValueError("row SHA")
            if previous is not None and previous >= path or path.casefold() in folded:
                raise ValueError("row order")
            if path in (TRUST_MANIFEST_REL, TRUST_RECEIPT_REL):
                raise ValueError("self inclusion")
            previous = path; folded.add(path.casefold()); row_map[path] = (count, sha)
            literal = f"{path}|{count}|{sha}"; all_literals.append(literal); total += count
            if total > (1 << 63) - 1:
                raise ValueError("total")
            if path.startswith("runtime/"):
                runtime_literals.append(literal); runtime_bytes += count
            elif path in HELPERS:
                helpers.add(path)
            else:
                project_literals.append(literal); project_bytes += count
        project_root = hashlib.sha256("\r\n".join(project_literals).encode("utf-8")).hexdigest().upper()
        runtime_root = hashlib.sha256("\r\n".join(runtime_literals).encode("utf-8")).hexdigest().upper()
        execution_root = hashlib.sha256("\r\n".join(all_literals).encode("utf-8")).hexdigest().upper()
        if len(project_literals) != EXPECTED_PROJECT_ROWS or project_bytes != EXPECTED_PROJECT_BYTES or project_root != P0_ROOT:
            raise ValueError("project root")
        if len(runtime_literals) != EXPECTED_RUNTIME_ROWS or runtime_bytes != EXPECTED_RUNTIME_BYTES or runtime_root != RUNTIME_ROOT:
            raise ValueError("runtime root")
        if helpers != HELPERS or manifest["execution_root_sha256"] != execution_root:
            raise ValueError("execution root")
        _check_deadline(deadline)
        receipt_file = _open_held(
            os.path.join(install_root, *TRUST_RECEIPT_REL.split("/")),
            65536,
            install_root,
            deadline,
        )
        receipt = _json(receipt_file["raw"], 65536, (
            "schema", "version", "algorithm", "manifest_sha256", "execution_root_sha256",
            "row_count", "total_bytes", "producer_sha256", "verifier_sha256",
        ))
        if type(receipt["schema"]) is not int or receipt["schema"] != 1 or type(receipt["version"]) is not int or receipt["version"] != 1 or receipt["algorithm"] != "SHA-256":
            raise ValueError("receipt metadata")
        if receipt["manifest_sha256"] != manifest_file["sha256"] or receipt["execution_root_sha256"] != execution_root:
            raise ValueError("receipt roots")
        if _integer(receipt["row_count"], 0, 1_000_000) != len(rows) or _integer(receipt["total_bytes"], 0, (1 << 63) - 1) != total:
            raise ValueError("receipt counts")
        if receipt["producer_sha256"] != EXPECTED_TRUST_PRODUCER_SHA256 or receipt["verifier_sha256"] != EXPECTED_TRUST_VERIFIER_SHA256:
            raise ValueError("receipt identity")
        _check_deadline(deadline)
        return row_map
    finally:
        if receipt_file is not None:
            _close(receipt_file["handle"])
        _close(manifest_file["handle"])


def _qualified(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _function(tree: ast.Module, name: str, class_name: str | None = None) -> ast.FunctionDef:
    scope: list[ast.stmt] = tree.body
    if class_name is not None:
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name]
        if len(classes) != 1:
            raise ValueError("class predicate")
        scope = classes[0].body
    matches = [node for node in scope if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    if len(matches) != 1 or not isinstance(matches[0], ast.FunctionDef):
        raise ValueError("function predicate")
    return matches[0]


def _calls(node: ast.AST) -> list[tuple[int, str, ast.Call]]:
    result: list[tuple[int, str, ast.Call]] = []
    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            result.append((int(getattr(item, "lineno", 0)), _qualified(item.func), item))
    return sorted(result, key=lambda row: (row[0], row[1]))


def _dump(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def _expr_is(node: ast.AST, source: str) -> bool:
    return _dump(node) == _dump(ast.parse(source, mode="eval").body)


def _calls_exact(node: ast.AST, qualified_name: str) -> list[ast.Call]:
    return [
        item for item in ast.walk(node)
        if isinstance(item, ast.Call) and _qualified(item.func) == qualified_name
    ]


def _contains(outer: ast.AST, inner: ast.AST) -> bool:
    return any(item is inner for item in ast.walk(outer))


def _call_statement(statement: ast.stmt) -> ast.Call | None:
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
        return statement.value
    if isinstance(statement, ast.Return) and isinstance(statement.value, ast.Call):
        return statement.value
    if isinstance(statement, ast.Raise) and isinstance(statement.exc, ast.Call):
        return statement.exc
    return None


def _reason_statement(statement: ast.stmt, kind: str, reason: str) -> bool:
    call = _call_statement(statement)
    if call is None:
        return False
    if kind == "fail":
        return (
            isinstance(statement, ast.Expr)
            and _qualified(call.func) == "_fail"
            and bool(call.args)
            and _qualified(call.args[0]) == reason
        )
    if kind == "return":
        return (
            isinstance(statement, ast.Return)
            and _qualified(call.func) == "_make_rejection"
            and len(call.args) >= 2
            and _qualified(call.args[1]) == reason
        )
    if kind == "raise":
        return (
            isinstance(statement, ast.Raise)
            and _qualified(call.func) == "_StateFailure"
            and bool(call.args)
            and _qualified(call.args[0]) == reason
        )
    return False


def _guard_is(statement: ast.stmt, test: str, kind: str, reason: str) -> bool:
    return (
        isinstance(statement, ast.If)
        and not statement.orelse
        and _expr_is(statement.test, test)
        and len(statement.body) == 1
        and _reason_statement(statement.body[0], kind, reason)
    )


def _assign_call(statement: ast.stmt, target: str, expression: str) -> bool:
    return (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id == target
        and _expr_is(statement.value, expression)
    )


def _tuple_target_is(node: ast.AST, names: tuple[str, ...]) -> bool:
    return (
        isinstance(node, ast.Tuple)
        and len(node.elts) == len(names)
        and all(isinstance(item, ast.Name) and item.id == name for item, name in zip(node.elts, names))
    )


def _validate_predicates(trees: dict[str, ast.Module], deadline: float) -> None:
    _check_deadline(deadline)
    loaders = trees["app/thermogar_verified_loaders.py"]
    effective = _function(loaders, "effective", "PhasePolicy")
    if (
        len(effective.body) != 10
        or not _guard_is(
            effective.body[3],
            "C15_PHASE in requested_tuple or any(phase in self.explicit_rejections for phase in requested_tuple)",
            "fail",
            "ReasonCode.C15_PHASE_REJECTED",
        )
        or not _guard_is(
            effective.body[8],
            "C15_PHASE in eligible",
            "fail",
            "ReasonCode.PHASE_POLICY_MISMATCH",
        )
        or not isinstance(effective.body[9], ast.Return)
        or not isinstance(effective.body[9].value, ast.Name)
        or effective.body[9].value.id != "eligible"
        or len(_calls_exact(effective, "_fail")) != 6
    ):
        raise ValueError("PhasePolicy C15 dominance")

    prepare = _function(loaders, "prepare_feature_request")
    if len(prepare.body) != 11 or not isinstance(prepare.body[7], ast.Try):
        raise ValueError("FeatureRequest policy layout")
    phase_try = prepare.body[7]
    if (
        len(phase_try.body) <= 5
        or not _assign_call(
            phase_try.body[5],
            "effective",
            "context.phase_policy.effective(requested, candidates=candidate_phases)",
        )
        or len(_calls_exact(prepare, "context.phase_policy.effective")) != 1
        or len(_calls_exact(prepare, "FeatureRequest")) != 1
        or len(_calls_exact(prepare, "_make_rejection")) != 7
        or not isinstance(prepare.body[10], ast.Return)
        or not isinstance(prepare.body[10].value, ast.Call)
        or _qualified(prepare.body[10].value.func) != "FeatureRequest"
    ):
        raise ValueError("FeatureRequest dominance")
    feature_return = prepare.body[10].value
    feature_keywords = {keyword.arg: keyword.value for keyword in feature_return.keywords}
    if (
        not _expr_is(feature_keywords.get("requested_phases", ast.Constant(None)), "requested")
        or not _expr_is(feature_keywords.get("effective_phases", ast.Constant(None)), "effective")
        or any(_contains(phase_try, call) for call in _calls_exact(prepare, "FeatureRequest"))
    ):
        raise ValueError("FeatureRequest result binding")

    _check_deadline(deadline)
    properties = trees["app/thermogar_verified_properties.py"]
    lease_guard = _function(properties, "_context_request_lease")
    if (
        len(lease_guard.body) != 9
        or not _guard_is(
            lease_guard.body[2],
            "C15_PHASE in request.requested_phases or C15_PHASE in request.effective_phases",
            "fail",
            "verified_loaders.ReasonCode.C15_PHASE_REJECTED",
        )
        or not isinstance(lease_guard.body[4], ast.Expr)
        or not _expr_is(lease_guard.body[4].value, "lease.identity")
        or not _guard_is(
            lease_guard.body[7],
            "context.database_key == 'fe' and context.profile_key != 'thermogar_patch'",
            "fail",
            "verified_loaders.ReasonCode.UPSTREAM_PROFILE_REJECTED",
        )
        or len(_calls_exact(lease_guard, "_fail")) != 7
        or not isinstance(lease_guard.body[8], ast.Return)
        or not _expr_is(lease_guard.body[8].value, "(context, request, lease)")
    ):
        raise ValueError("lease C15/profile dominance")

    execute = _function(properties, "execute_verified_properties")
    if (
        len(execute.body) <= 3
        or not isinstance(execute.body[1], ast.Assign)
        or len(execute.body[1].targets) != 1
        or not _tuple_target_is(execute.body[1].targets[0], ("context", "feature_request", "lease"))
        or not _expr_is(execute.body[1].value, "_context_request_lease(context, feature_request, lease)")
        or len(_calls_exact(execute, "_context_request_lease")) != 1
        or not isinstance(execute.body[3], ast.If)
        or not _expr_is(execute.body[3].test, "feature_request.feature_id == 'property_elastic_prepare'")
    ):
        raise ValueError("execution guard binding")
    prepare_branch = execute.body[3]
    for name in ("lease.parse_physical_dataset", "lease.parse_tdb", "lease.invoke_backend"):
        calls = _calls_exact(execute, name)
        if len(calls) != 1 or not _contains(prepare_branch, calls[0]):
            raise ValueError("execution forbidden-call dominance")
    prepared_stores = [
        item for item in ast.walk(prepare_branch)
        if isinstance(item, ast.Subscript)
        and isinstance(item.ctx, ast.Store)
        and _qualified(item.value) == "_PREPARED_WITNESSES"
    ]
    if (
        len(_calls_exact(prepare_branch, "_make_result")) != 1
        or len(_calls_exact(prepare_branch, "VerifiedPropertiesResult")) != 1
        or len(prepared_stores) != 1
        or len(_calls_exact(execute, "_make_result")) != 3
        or len(_calls_exact(execute, "VerifiedPropertiesResult")) != 3
        or len(_calls_exact(execute, "_write_library")) != 1
    ):
        raise ValueError("execution state-write surface")

    _check_deadline(deadline)
    app = trees["app/ThermoGar_app.py"]
    decision = _function(app, "_b4b_prepare_decision")
    if (
        len(decision.body) != 2
        or not _assign_call(
            decision.body[0],
            "candidates",
            "tuple(phase for phase in context.phase_policy.eligible_phases if phase != restricted_fe.C15_PHASE)",
        )
        or not isinstance(decision.body[1], ast.Return)
        or not _expr_is(
            decision.body[1].value,
            "verified_loaders.prepare_feature_request(feature_id, context, inputs, requested_phases, candidate_phases=candidates)",
        )
        or len(_calls_exact(decision, "verified_loaders.prepare_feature_request")) != 1
    ):
        raise ValueError("UI candidate policy")

    render = _function(app, "render_b4b2_elastic_properties")
    expected_totals = {
        "_b4b_prepare_decision": 2,
        "verified_physical_button": 2,
        "acquire_b4b_execution": 2,
        "verified_properties.execute_verified_properties": 2,
        "_b4b2_store_result": 2,
        "_b4b_refresh_result": 2,
    }
    if any(len(_calls_exact(render, name)) != count for name, count in expected_totals.items()):
        raise ValueError("UI execution surface")
    prepare_assignments = [
        item for item in ast.walk(render)
        if _assign_call(
            item,
            "prepare_decision",
            "_b4b_prepare_decision('property_elastic_prepare', context, prepare_inputs, requested)",
        )
    ]
    if len(prepare_assignments) != 1:
        raise ValueError("UI prepare decision binding")
    outer_guards = [
        item for item in render.body
        if isinstance(item, ast.If) and _expr_is(item.test, "prepare_decision is not None")
    ]
    if len(outer_guards) != 1:
        raise ValueError("UI prepare result gate")
    outer_guard = outer_guards[0]
    button_guards = [
        item for item in ast.walk(outer_guard)
        if isinstance(item, ast.If)
        and isinstance(item.test, ast.Call)
        and _qualified(item.test.func) == "verified_physical_button"
        and bool(item.test.args)
        and _expr_is(item.test.args[0], "prepare_decision")
    ]
    if len(button_guards) != 1 or len(button_guards[0].body) != 1 or not isinstance(button_guards[0].body[0], ast.Try):
        raise ValueError("UI prepare button gate")
    button_try = button_guards[0].body[0]
    if (
        len(button_try.body) != 3
        or not isinstance(button_try.body[0], ast.Assert)
        or not _expr_is(button_try.body[0].test, "type(prepare_decision) is verified_loaders.FeatureRequest")
        or not isinstance(button_try.body[1], ast.With)
        or len(button_try.body[1].items) != 1
        or not _expr_is(button_try.body[1].items[0].context_expr, "acquire_b4b_execution(prepare_decision, THERMOGAR_PATHS)")
        or not isinstance(button_try.body[1].items[0].optional_vars, ast.Name)
        or button_try.body[1].items[0].optional_vars.id != "lease"
        or len(button_try.body[1].body) != 1
        or not _assign_call(
            button_try.body[1].body[0],
            "execution",
            "verified_properties.execute_verified_properties(context, prepare_decision, lease, paths=THERMOGAR_PATHS)",
        )
        or not isinstance(button_try.body[2], ast.Expr)
        or not _expr_is(button_try.body[2].value, "_b4b2_store_result(prepare_state_key, database_key, execution)")
    ):
        raise ValueError("UI prepare execution dominance")
    for name in ("acquire_b4b_execution", "verified_properties.execute_verified_properties", "_b4b2_store_result"):
        if len(_calls_exact(button_guards[0], name)) != 1:
            raise ValueError("UI guarded call count")

    _check_deadline(deadline)
    state = trees["app/thermogar_verified_state.py"]
    parse_ingress = _function(state, "_parse_ingress", "StateStore")
    if (
        len(parse_ingress.body) != 8
        or not _guard_is(
            parse_ingress.body[5],
            "_deep_has_c15(value)",
            "raise",
            "verified_loaders.ReasonCode.C15_PHASE_REJECTED",
        )
        or len(_calls_exact(parse_ingress, "_deep_has_c15")) != 1
        or len(_calls_exact(parse_ingress, "semantic_digest_for")) != 1
        or len(_calls_exact(parse_ingress, "self._persist")) != 0
        or len(_calls_exact(parse_ingress, "self._mint")) != 0
    ):
        raise ValueError("ingress value policy")

    ingress = _function(state, "ingest_from_widget", "StateStore")
    if (
        len(ingress.body) <= 9
        or not _guard_is(
            ingress.body[3],
            "_C15 in request.requested_phases or _C15 in request.effective_phases",
            "return",
            "verified_loaders.ReasonCode.C15_PHASE_REJECTED",
        )
    ):
        raise ValueError("ingress dispatch policy")
    ingress_risks = {
        "self._ui.file_uploader": 1,
        "self._parse_ingress": 1,
        "self._persist": 1,
        "self._mint": 1,
    }
    ingress_tail = ast.Module(body=ingress.body[4:], type_ignores=[])
    for name, count in ingress_risks.items():
        calls = _calls_exact(ingress, name)
        if len(calls) != count or any(not _contains(ingress_tail, call) for call in calls):
            raise ValueError("ingress side-effect dominance")

    egress = _function(state, "prepare_egress", "StateStore")
    if len(egress.body) <= 2 or not isinstance(egress.body[2], ast.Try):
        raise ValueError("egress policy layout")
    egress_try = egress.body[2]
    if (
        len(egress_try.body) <= 1
        or not _guard_is(
            egress_try.body[1],
            "_C15 in request.requested_phases or _C15 in request.effective_phases or _deep_has_c15(value)",
            "raise",
            "verified_loaders.ReasonCode.C15_PHASE_REJECTED",
        )
    ):
        raise ValueError("egress C15 guard")
    egress_tail = ast.Module(body=egress_try.body[2:], type_ignores=[])
    for name in ("semantic_digest_for", "self._persist", "self._mint"):
        calls = _calls_exact(egress, name)
        if len(calls) != 1 or not _contains(egress_tail, calls[0]):
            raise ValueError("egress side-effect dominance")
    if len(_calls_exact(egress, "_deep_has_c15")) != 1:
        raise ValueError("egress C15 call count")

    state_class = [item for item in state.body if isinstance(item, ast.ClassDef) and item.name == "StateStore"]
    if len(state_class) != 1:
        raise ValueError("StateStore class")
    class_node = state_class[0]
    if (
        len(_calls_exact(class_node, "self._ui.file_uploader")) != 1
        or len(_calls_exact(class_node, "self._persist")) != 2
        or len(_calls_exact(class_node, "self._mint")) != 2
    ):
        raise ValueError("state side-effect surface")
    _check_deadline(deadline)


def _parse_cli() -> tuple[str, str]:
    if len(sys.argv) != 6 or sys.argv[1] != "--install-root" or sys.argv[3] != "--fixture" or sys.argv[5] != "--json":
        raise ProbeError(2)
    try:
        return _fixed_local_path(sys.argv[2]), _fixed_local_path(sys.argv[4])
    except ValueError as exc:
        raise ProbeError(2) from exc


def _run() -> int:
    started = time.monotonic(); deadline = started + 30.0
    try:
        install_root, fixture_path = _parse_cli()
        _check_deadline(deadline)
        try:
            fixture_file = _open_held(fixture_path, FIXTURE_BYTES, deadline=deadline)
            try:
                fixture_raw = fixture_file["raw"]
                if fixture_file["bytes"] != FIXTURE_BYTES or fixture_file["sha256"] != FIXTURE_SHA256:
                    raise ValueError("fixture identity")
                fixture = _json(fixture_raw, FIXTURE_BYTES, ("c15", "schema", "ui"))
                if fixture["c15"] != SUCCESS or type(fixture["schema"]) is not int or fixture["schema"] != 1 or not isinstance(fixture["ui"], dict):
                    raise ValueError("fixture schema")
                _check_deadline(deadline)
            finally:
                _close(fixture_file["handle"])
        except ProbeError:
            raise
        except Exception as exc:
            raise ProbeError(3) from exc
        _check_deadline(deadline)
        try:
            rows = _validate_runtime_trust(install_root, deadline)
        except ProbeError:
            raise
        except Exception as exc:
            raise ProbeError(4) from exc
        trees: dict[str, ast.Module] = {}
        try:
            for relative, (expected_bytes, expected_sha) in SOURCE_PINS.items():
                if rows.get(relative) != (expected_bytes, expected_sha):
                    raise ValueError("source trust row")
                source_file = _open_held(
                    os.path.join(install_root, *relative.split("/")),
                    expected_bytes,
                    install_root,
                    deadline,
                )
                try:
                    if source_file["bytes"] != expected_bytes or source_file["sha256"] != expected_sha:
                        raise ValueError("source identity")
                    source = source_file["raw"].decode("utf-8", "strict")
                    trees[relative] = ast.parse(source, filename=source_file["path"], mode="exec")
                    _check_deadline(deadline)
                finally:
                    _close(source_file["handle"])
        except ProbeError:
            raise
        except Exception as exc:
            raise ProbeError(5) from exc
        _check_deadline(deadline)
        try:
            _validate_predicates(trees, deadline)
        except ProbeError:
            raise
        except Exception as exc:
            raise ProbeError(6) from exc
        success_raw = _canonical(SUCCESS)
        if len(success_raw) != 288 or hashlib.sha256(success_raw).hexdigest().upper() != SUCCESS_SHA256:
            raise ProbeError(7)
        _check_deadline(deadline)
        _emit(SUCCESS)
        return 0
    except ProbeError as exc:
        return _fail(exc.code)
    except Exception:
        return _fail(9)


if __name__ == "__main__":
    raise SystemExit(_run())
