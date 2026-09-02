#!/usr/bin/env python3
"""Fail-closed internal Fe diagnostic smoke check for TG-FE-2062-C15-001.

This is a narrow engineering diagnostic.  It is not a release, material
qualification, or physical-validation calculation.  The upstream profile is
run only to record the known diagnostic symptom and is never an accepted
output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PATCH_ID = "TG-FE-2062-C15-001"
PRESSURE_PA = 101325.0
TEMPERATURES_K = (1800.0, 1900.0, 2000.0)
LIQUID_MINIMUM = 0.999999
C15_LAVES_MAXIMUM = 1.0e-8
PHASE_FRACTION_CLOSURE_TOLERANCE = 1.0e-8
WORKER_TIMEOUT_SECONDS = 90.0
WORKER_STDOUT_MAX_CHARS = 256 * 1024
WORKER_SCHEMA = "thermogar.fe.internal_smoke.worker.v2"
PROFILE_SCHEMA = "thermogar.fe.internal_smoke.profile.v2"

# Pin the exact database files used by this diagnostic.  A mismatch is a hard
# stop; a receipt must never silently describe a different database revision.
PROFILES = {
    "patched": {
        "relative_path": Path("databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb"),
        "sha256": "236EC4D9B0540DE04E4E6305FAA208672F31FBDF45B2AE84E92F80BD98053612",
        "role": "patched_diagnostic_only",
    },
    "upstream": {
        "relative_path": Path("databases/diagnostic/fe/mc_fe_v2062_unpatched_with_mobility.thermogar.tdb"),
        "sha256": "F9375C3A7A8649BACE698E2177F2CC964BCE3F8A19F08AE05D88840ABD77B112",
        "role": "upstream_diagnostic_control_only",
    },
}

WITNESS_WT_PCT = {
    "CR": 11.5,
    "NI": 0.7,
    "MN": 0.7,
    "SI": 0.3,
    "C": 0.20,
    "MO": 0.6,
    "W": 0.9,
    "V": 0.225,
}
BALANCE_ELEMENT = "FE"

EXPECTED_COMPONENTS = (
    "C",
    "CR",
    "FE",
    "MN",
    "MO",
    "NI",
    "SI",
    "V",
    "W",
    "VA",
)

# This is the complete pycalphad eligibility result for EXPECTED_COMPONENTS in
# both pinned Fe profiles.  It is deliberately explicit so a child cannot
# silently reduce the scientific phase scope in its JSON response.
EXPECTED_ELIGIBLE_PHASES = (
    "ALPHA_MN",
    "BCC_B2",
    "BCC_DISL",
    "BETA_MN",
    "BETA_RHOMBO_B",
    "C15_LAVES",
    "CEMENTITE",
    "CHI_A12",
    "CR2VC2",
    "CR3MN5",
    "DIAMOND_A4",
    "EPS_CARB",
    "ETA",
    "ETA_CARB",
    "FCC_A1",
    "FE24C10",
    "GAMMA_PRIME",
    "GRAPHITE",
    "G_PHASE",
    "HCP_A3",
    "H_BCC",
    "KSI_CARBIDE",
    "KSI_FE5C2",
    "LAVES_PHASE",
    "LIQUID",
    "M23C6",
    "M3C2",
    "M6C",
    "M7C3",
    "MNNI",
    "MNNI2",
    "MOB2",
    "MOC_ETA",
    "MU_PHASE",
    "MU_PHASE_I",
    "NI2SIH",
    "NI2SIL",
    "NI3SI2",
    "NI3SIH",
    "NI3SIL",
    "NI5SI2",
    "NISI",
    "NITI2",
    "PD3MN",
    "PDFE_L12",
    "PDMN_AF",
    "PDMN_B2",
    "PDMN_P",
    "R_PHASE",
    "SIGMA",
    "T2_MNNISI",
    "T4",
    "T7",
    "TIB2",
    "V3C2",
    "WC",
    "ZET",
)

# Exact binary64 values derived from the pinned database reference masses and
# the fixed 20Kh12VNMF proxy.  Both pinned profiles produce this same vector.
EXPECTED_WITNESS_ATOMIC_FRACTIONS = (
    ("C", 0.009207219386236021),
    ("CR", 0.12229411767760304),
    ("FE", 0.8403449634788673),
    ("MN", 0.007045354620996085),
    ("MO", 0.0034580335224540597),
    ("NI", 0.00659495130632617),
    ("SI", 0.005906317070093865),
    ("V", 0.0024422406300185695),
    ("W", 0.0027068023074047526),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def profile_path(project_root: Path, profile_name: str) -> Path:
    try:
        relative_path = PROFILES[profile_name]["relative_path"]
    except KeyError as error:
        raise ValueError(f"Unknown profile: {profile_name!r}") from error
    return (project_root / relative_path).resolve()


def verify_profile_identity(project_root: Path, profile_name: str) -> Path:
    path = profile_path(project_root, profile_name)
    if not path.is_file():
        raise FileNotFoundError(f"Required {profile_name} profile is absent: {path}")
    actual = sha256_file(path)
    expected = str(PROFILES[profile_name]["sha256"])
    if actual != expected:
        raise RuntimeError(
            f"{profile_name} database SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return path


def witness_weights() -> dict[str, float]:
    """Return the complete 20Kh12VNMF proxy in wt.%, with Fe by balance."""
    values = {element: float(value) for element, value in WITNESS_WT_PCT.items()}
    if any(not math.isfinite(value) or value < 0.0 for value in values.values()):
        raise ValueError("Witness wt.% values must be finite and non-negative")
    balance = 100.0 - sum(values.values())
    if not math.isfinite(balance) or balance <= 0.0:
        raise ValueError("Witness Fe balance must be finite and positive")
    return {BALANCE_ELEMENT: balance, **values}


def wt_pct_to_atomic_fractions(
    weights: Mapping[str, float], masses: Mapping[str, float]
) -> dict[str, float]:
    """Convert a complete wt.% composition to atomic fractions."""
    missing = sorted(set(weights) - set(masses))
    if missing:
        raise ValueError("Database lacks reference masses for: " + ", ".join(missing))
    moles = {element: float(weight) / float(masses[element]) for element, weight in weights.items()}
    if any(not math.isfinite(value) or value < 0.0 for value in moles.values()):
        raise ValueError("Composition conversion produced an invalid mole amount")
    total = sum(moles.values())
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("Composition conversion has a non-positive mole total")
    atomic = {element: amount / total for element, amount in moles.items()}
    if not math.isclose(sum(atomic.values()), 1.0, rel_tol=0.0, abs_tol=1.0e-12):
        raise ValueError("Atomic composition does not close to one")
    return atomic


def aggregate_phase_fractions(equilibrium_result: Any) -> dict[str, float]:
    """Aggregate pycalphad NP values by phase name, excluding numerical noise."""
    import numpy as np

    names = np.asarray(equilibrium_result.Phase.values, dtype=str).ravel()
    fractions = np.asarray(equilibrium_result.NP.values, dtype=float).ravel()
    result: dict[str, float] = {}
    for name, fraction in zip(names, fractions):
        phase_name = str(name)
        if phase_name and math.isfinite(float(fraction)) and float(fraction) > 1.0e-12:
            result[phase_name] = result.get(phase_name, 0.0) + float(fraction)
    return dict(sorted(result.items()))


def eligible_phases(database: Any, components: Sequence[str]) -> list[str]:
    """Return the complete pinned eligibility result without phase reduction."""
    from pycalphad.core.utils import filter_phases

    if tuple(components) != EXPECTED_COMPONENTS:
        raise RuntimeError("Component scope differs from the pinned Fe smoke witness")
    observed = tuple(
        sorted(filter_phases(database, list(components), candidate_phases=None))
    )
    if observed != EXPECTED_ELIGIBLE_PHASES:
        raise RuntimeError("Eligible phase scope differs from the pinned full phase list")
    if "C15_LAVES" not in observed or "LIQUID" not in observed:
        raise RuntimeError("Required LIQUID/C15_LAVES phases are not eligible")
    return list(observed)


def _fixed_temperature(value: object) -> float:
    if type(value) not in (int, float) or isinstance(value, bool):
        raise ValueError("Worker temperature must be a real scalar")
    temperature = float(value)
    if not math.isfinite(temperature) or temperature not in TEMPERATURES_K:
        raise ValueError(
            "Worker temperature must be exactly one of "
            + ", ".join(f"{item:.1f}" for item in TEMPERATURES_K)
        )
    return temperature


def _expected_witness_payload() -> dict[str, Any]:
    return {
        "name": "20Kh12VNMF_proxy",
        "basis": "wt_pct",
        "balance_element": BALANCE_ELEMENT,
        "wt_pct": witness_weights(),
        "atomic_fractions": dict(EXPECTED_WITNESS_ATOMIC_FRACTIONS),
    }


def _exact_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise RuntimeError(f"{label} schema mismatch")
    return value


def _exact_json_float(value: object, label: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise RuntimeError(f"{label} must be a finite JSON float")
    return value


def _validate_exact_float_mapping(
    value: object,
    expected: Mapping[str, float],
    label: str,
) -> dict[str, float]:
    mapping = _exact_keys(value, set(expected), label)
    rebuilt: dict[str, float] = {}
    for key, expected_value in expected.items():
        observed = _exact_json_float(mapping[key], f"{label}.{key}")
        if observed != expected_value:
            raise RuntimeError(f"{label}.{key} differs from the pinned witness")
        rebuilt[key] = observed
    return rebuilt


def _worker_identity(project_root: Path, profile_name: str) -> dict[str, Any]:
    if profile_name not in PROFILES:
        raise ValueError(f"Unknown profile: {profile_name!r}")
    return {
        "patch_id": PATCH_ID,
        "profile": profile_name,
        "role": str(PROFILES[profile_name]["role"]),
        "database_path": str(profile_path(project_root, profile_name)),
        "database_sha256": str(PROFILES[profile_name]["sha256"]),
        "components": list(EXPECTED_COMPONENTS),
        "eligible_phases": list(EXPECTED_ELIGIBLE_PHASES),
        "witness": _expected_witness_payload(),
    }


def validate_worker_receipt(
    project_root: Path,
    profile_name: str,
    temperature_k: object,
    payload: object,
) -> dict[str, Any]:
    """Reconstruct one child result under exact parent-owned identities."""
    requested_temperature = _fixed_temperature(temperature_k)
    worker = _exact_keys(
        payload,
        {
            "schema",
            "patch_id",
            "profile",
            "role",
            "database_path",
            "database_sha256",
            "components",
            "eligible_phases",
            "witness",
            "point",
        },
        "worker receipt",
    )
    expected_identity = _worker_identity(project_root.resolve(), profile_name)
    if worker["schema"] != WORKER_SCHEMA:
        raise RuntimeError("Worker schema identity mismatch")
    for key in (
        "patch_id",
        "profile",
        "role",
        "database_path",
        "database_sha256",
    ):
        if type(worker[key]) is not str or worker[key] != expected_identity[key]:
            raise RuntimeError(f"Worker {key} identity mismatch")
    if type(worker["components"]) is not list or worker["components"] != list(
        EXPECTED_COMPONENTS
    ):
        raise RuntimeError("Worker component scope mismatch")
    if type(worker["eligible_phases"]) is not list or worker[
        "eligible_phases"
    ] != list(EXPECTED_ELIGIBLE_PHASES):
        raise RuntimeError("Worker eligible phase scope mismatch")

    witness = _exact_keys(
        worker["witness"],
        {"name", "basis", "balance_element", "wt_pct", "atomic_fractions"},
        "worker witness",
    )
    if (
        witness["name"] != "20Kh12VNMF_proxy"
        or witness["basis"] != "wt_pct"
        or witness["balance_element"] != BALANCE_ELEMENT
    ):
        raise RuntimeError("Worker witness identity mismatch")
    weights = _validate_exact_float_mapping(
        witness["wt_pct"], witness_weights(), "worker witness wt_pct"
    )
    atomic = _validate_exact_float_mapping(
        witness["atomic_fractions"],
        dict(EXPECTED_WITNESS_ATOMIC_FRACTIONS),
        "worker witness atomic_fractions",
    )

    point = _exact_keys(
        worker["point"],
        {
            "temperature_k",
            "pressure_pa",
            "stable_phase_fractions",
            "liquid_fraction",
            "c15_laves_fraction",
            "patched_assertions",
        },
        "worker point",
    )
    observed_temperature = _exact_json_float(
        point["temperature_k"], "worker point temperature_k"
    )
    if observed_temperature != requested_temperature:
        raise RuntimeError("Worker temperature identity mismatch")
    pressure = _exact_json_float(point["pressure_pa"], "worker point pressure_pa")
    if pressure != PRESSURE_PA:
        raise RuntimeError("Worker pressure identity mismatch")

    stable_raw = point["stable_phase_fractions"]
    if type(stable_raw) is not dict or not stable_raw:
        raise RuntimeError("Worker stable phase evidence must be a non-empty object")
    stable: dict[str, float] = {}
    for phase, raw_fraction in stable_raw.items():
        if type(phase) is not str or phase not in EXPECTED_ELIGIBLE_PHASES:
            raise RuntimeError("Worker stable phase is outside the eligible phase scope")
        fraction = _exact_json_float(
            raw_fraction, f"worker stable_phase_fractions.{phase}"
        )
        if fraction <= 0.0 or fraction > 1.0 + PHASE_FRACTION_CLOSURE_TOLERANCE:
            raise RuntimeError("Worker phase fraction is outside the physical range")
        stable[phase] = fraction
    if not math.isclose(
        sum(stable.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=PHASE_FRACTION_CLOSURE_TOLERANCE,
    ):
        raise RuntimeError("Worker stable phase fractions do not close to one")
    stable = dict(sorted(stable.items()))

    liquid = _exact_json_float(point["liquid_fraction"], "worker liquid_fraction")
    c15 = _exact_json_float(
        point["c15_laves_fraction"], "worker c15_laves_fraction"
    )
    if liquid != stable.get("LIQUID", 0.0):
        raise RuntimeError("Worker LIQUID fraction does not match phase evidence")
    if c15 != stable.get("C15_LAVES", 0.0):
        raise RuntimeError("Worker C15_LAVES fraction does not match phase evidence")

    assertions = _exact_keys(
        point["patched_assertions"],
        {"liquid_gte_0_999999", "c15_laves_lte_1e-8"},
        "worker point gates",
    )
    expected_assertions = {
        "liquid_gte_0_999999": liquid >= LIQUID_MINIMUM,
        "c15_laves_lte_1e-8": c15 <= C15_LAVES_MAXIMUM,
    }
    if any(type(value) is not bool for value in assertions.values()):
        raise RuntimeError("Worker point gates must be exact booleans")
    if assertions != expected_assertions:
        raise RuntimeError("Worker point gates do not match the phase evidence")

    return {
        "schema": WORKER_SCHEMA,
        **expected_identity,
        "witness": {
            "name": "20Kh12VNMF_proxy",
            "basis": "wt_pct",
            "balance_element": BALANCE_ELEMENT,
            "wt_pct": weights,
            "atomic_fractions": atomic,
        },
        "point": {
            "temperature_k": observed_temperature,
            "pressure_pa": pressure,
            "stable_phase_fractions": stable,
            "liquid_fraction": liquid,
            "c15_laves_fraction": c15,
            "patched_assertions": expected_assertions,
        },
    }


def _profile_receipt(
    project_root: Path,
    profile_name: str,
    points: Sequence[Mapping[str, Any]],
    *,
    complete: bool,
) -> dict[str, Any]:
    identity = _worker_identity(project_root.resolve(), profile_name)
    return {
        "schema": PROFILE_SCHEMA,
        **identity,
        "complete": complete,
        "points": [dict(point) for point in points],
    }


def validate_profile_receipt(
    project_root: Path,
    profile_name: str,
    payload: object,
) -> dict[str, Any]:
    """Require a complete exact three-temperature profile receipt."""
    profile = _exact_keys(
        payload,
        {
            "schema",
            "patch_id",
            "profile",
            "role",
            "database_path",
            "database_sha256",
            "components",
            "eligible_phases",
            "witness",
            "complete",
            "points",
        },
        "profile receipt",
    )
    if profile["schema"] != PROFILE_SCHEMA or profile["complete"] is not True:
        raise RuntimeError("Profile receipt is not a complete pinned receipt")
    points = profile["points"]
    if type(points) is not list or len(points) != len(TEMPERATURES_K):
        raise RuntimeError("Profile receipt must contain exactly three points")

    rebuilt_points: list[dict[str, Any]] = []
    for expected_temperature, point in zip(TEMPERATURES_K, points):
        worker_payload = {
            "schema": WORKER_SCHEMA,
            "patch_id": profile["patch_id"],
            "profile": profile["profile"],
            "role": profile["role"],
            "database_path": profile["database_path"],
            "database_sha256": profile["database_sha256"],
            "components": profile["components"],
            "eligible_phases": profile["eligible_phases"],
            "witness": profile["witness"],
            "point": point,
        }
        rebuilt = validate_worker_receipt(
            project_root.resolve(), profile_name, expected_temperature, worker_payload
        )
        rebuilt_points.append(rebuilt["point"])
    if tuple(point["temperature_k"] for point in rebuilt_points) != TEMPERATURES_K:
        raise RuntimeError("Profile receipt temperature set/order mismatch")
    return _profile_receipt(
        project_root.resolve(), profile_name, rebuilt_points, complete=True
    )


def evaluate_profile_point(
    project_root: Path,
    profile_name: str,
    temperature_k: object,
) -> dict[str, Any]:
    """Evaluate one pinned profile at exactly one fixed temperature."""
    from pycalphad import Database, equilibrium, variables as v

    temperature = _fixed_temperature(temperature_k)
    path = verify_profile_identity(project_root, profile_name)
    database = Database(str(path))
    weights = witness_weights()
    elements = sorted(weights)
    masses = {element: float(database.refstates[element]["mass"]) for element in elements}
    atomic = wt_pct_to_atomic_fractions(weights, masses)
    if atomic != dict(EXPECTED_WITNESS_ATOMIC_FRACTIONS):
        raise RuntimeError("Database reference masses changed the pinned atomic witness")
    components = list(EXPECTED_COMPONENTS)
    phases = eligible_phases(database, components)
    conditions = {v.N: 1.0, v.P: PRESSURE_PA, v.T: temperature}
    conditions.update(
        {
            v.X(element): atomic[element]
            for element in elements
            if element != BALANCE_ELEMENT
        }
    )
    calculation = equilibrium(
        database,
        components,
        phases,
        conditions,
        calc_opts={"pdens": 100},
    )
    stable = aggregate_phase_fractions(calculation)
    liquid = float(stable.get("LIQUID", 0.0))
    c15 = float(stable.get("C15_LAVES", 0.0))

    # Defend against a file replacement during calculation as well as before it.
    verify_profile_identity(project_root, profile_name)
    payload = {
        "schema": WORKER_SCHEMA,
        "patch_id": PATCH_ID,
        "profile": profile_name,
        "role": PROFILES[profile_name]["role"],
        "database_path": str(path),
        "database_sha256": PROFILES[profile_name]["sha256"],
        "components": components,
        "eligible_phases": phases,
        "witness": _expected_witness_payload(),
        "point": {
            "temperature_k": temperature,
            "pressure_pa": PRESSURE_PA,
            "stable_phase_fractions": stable,
            "liquid_fraction": liquid,
            "c15_laves_fraction": c15,
            "patched_assertions": {
                "liquid_gte_0_999999": liquid >= LIQUID_MINIMUM,
                "c15_laves_lte_1e-8": c15 <= C15_LAVES_MAXIMUM,
            },
        },
    }
    return validate_worker_receipt(
        project_root.resolve(), profile_name, temperature, payload
    )


def patched_profile_passed(
    profile_receipt: Mapping[str, Any],
    project_root: Path = PROJECT_ROOT,
) -> bool:
    try:
        rebuilt = validate_profile_receipt(project_root, "patched", profile_receipt)
    except Exception:
        return False
    return all(
        point["patched_assertions"]
        == {
            "liquid_gte_0_999999": True,
            "c15_laves_lte_1e-8": True,
        }
        for point in rebuilt["points"]
    )


def upstream_diagnostic_interpretation(
    profile_receipt: Mapping[str, Any],
    project_root: Path = PROJECT_ROOT,
) -> str:
    """Classify upstream without allowing it to become an accepted result."""
    rebuilt = validate_profile_receipt(project_root, "upstream", profile_receipt)
    symptom = any(
        point["liquid_fraction"] < LIQUID_MINIMUM
        or point["c15_laves_fraction"] > C15_LAVES_MAXIMUM
        for point in rebuilt["points"]
    )
    if symptom:
        return "EXPECTED_DIAGNOSTIC_SYMPTOM_OBSERVED"
    return "NO_EXPECTED_SYMPTOM_OBSERVED__STILL_DIAGNOSTIC_ONLY_NOT_ACCEPTED"


def evaluate_profile_in_worker(
    project_root: Path,
    profile_name: str,
    temperature_k: object,
    *,
    timeout_seconds: float = WORKER_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run and validate one temperature in one native-failure boundary."""
    temperature = _fixed_temperature(temperature_k)
    if type(timeout_seconds) is not float or timeout_seconds != WORKER_TIMEOUT_SECONDS:
        raise ValueError("Worker timeout must remain exactly 90 seconds")
    verify_profile_identity(project_root, profile_name)
    command = [
        sys.executable,
        "-I",
        "-B",
        "-X",
        "utf8",
        str(Path(__file__).resolve()),
        "--worker",
        profile_name,
        "--temperature-k",
        f"{temperature:.1f}",
        "--project-root",
        str(project_root),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=WORKER_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"{profile_name} worker at {temperature:.1f} K timed out after 90 seconds"
        ) from error
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        if len(detail) > 1000:
            detail = detail[-1000:]
        raise RuntimeError(
            f"{profile_name} worker at {temperature:.1f} K exited with code "
            f"{completed.returncode}"
            + (f": {detail}" if detail else "")
        )
    if len(completed.stdout) > WORKER_STDOUT_MAX_CHARS:
        raise RuntimeError(f"{profile_name} worker JSON exceeds the bounded size")

    def reject_constant(token: str) -> None:
        raise ValueError(f"non-finite JSON constant: {token}")

    try:
        payload = json.loads(completed.stdout, parse_constant=reject_constant)
    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(f"{profile_name} worker emitted invalid JSON") from error
    verify_profile_identity(project_root, profile_name)
    return validate_worker_receipt(
        project_root.resolve(), profile_name, temperature, payload
    )


def evaluate_profile_in_workers(
    project_root: Path,
    profile_name: str,
) -> tuple[dict[str, Any], str | None]:
    """Run fixed temperatures sequentially and retain prior valid evidence."""
    points: list[dict[str, Any]] = []
    for temperature in TEMPERATURES_K:
        try:
            raw = evaluate_profile_in_worker(project_root, profile_name, temperature)
            rebuilt = validate_worker_receipt(
                project_root.resolve(), profile_name, temperature, raw
            )
        except Exception as error:
            partial = _profile_receipt(
                project_root.resolve(), profile_name, points, complete=False
            )
            detail = (
                f"{type(error).__name__} at {temperature:.1f} K: {error}"
            )
            return partial, detail
        points.append(rebuilt["point"])
    complete = _profile_receipt(
        project_root.resolve(), profile_name, points, complete=True
    )
    return validate_profile_receipt(project_root, profile_name, complete), None


def run(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    started = time.perf_counter()
    receipt: dict[str, Any] = {
        "harness": "thermogar_fe_internal_smoke",
        "scope": "internal_diagnostic_only",
        "patch_id": PATCH_ID,
        "release_or_qualification_claim": False,
        "thresholds": {
            "liquid_minimum": LIQUID_MINIMUM,
            "c15_laves_maximum": C15_LAVES_MAXIMUM,
        },
        "profiles": {},
    }
    patched, patched_error = evaluate_profile_in_workers(project_root, "patched")
    receipt["profiles"]["patched"] = patched
    if patched_error is not None:
        receipt["patched_status"] = "ERROR"
        receipt["patched_error"] = patched_error
        receipt["upstream_diagnostic_status"] = "NOT_RUN_PATCHED_WORKER_ERROR"
        receipt["passed"] = False
        receipt["duration_seconds"] = round(time.perf_counter() - started, 6)
        return receipt

    receipt["patched_status"] = (
        "PASS" if patched_profile_passed(patched, project_root) else "FAIL"
    )
    upstream, upstream_error = evaluate_profile_in_workers(project_root, "upstream")
    receipt["profiles"]["upstream"] = upstream
    if upstream_error is not None:
        receipt["upstream_diagnostic_status"] = "ERROR"
        receipt["upstream_diagnostic_error"] = upstream_error
    else:
        upstream["diagnostic_interpretation"] = upstream_diagnostic_interpretation(
            upstream, project_root
        )
        upstream["accepted_output"] = False
        receipt["upstream_diagnostic_status"] = "COMPLETE_DIAGNOSTIC_ONLY"

    receipt["passed"] = (
        receipt["patched_status"] == "PASS"
        and receipt["upstream_diagnostic_status"] == "COMPLETE_DIAGNOSTIC_ONLY"
    )
    receipt["duration_seconds"] = round(time.perf_counter() - started, 6)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--json", action="store_true", help="emit the JSON receipt (the default output)")
    parser.add_argument("--worker", choices=sorted(PROFILES), help=argparse.SUPPRESS)
    parser.add_argument("--temperature-k", type=float, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        if args.temperature_k is None:
            parser.error("--worker requires exactly one --temperature-k")
        print(
            json.dumps(
                evaluate_profile_point(
                    args.project_root.resolve(), args.worker, args.temperature_k
                ),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    if args.temperature_k is not None:
        parser.error("--temperature-k is valid only with --worker")
    receipt = run(args.project_root.resolve())
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
