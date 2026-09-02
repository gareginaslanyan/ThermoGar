#!/usr/bin/env python3
"""Two-sided acceptance test for ThermoGar patch TG-FE-2062-C15-001.

Side A — high-temperature anomaly:
    A 20Х12ВНМФ-like Fe-base proxy must reach one-phase LIQUID at
    1800–2000 K in the patched working database, while the unpatched
    diagnostic profile reproduces the high-temperature C15_LAVES symptom.

Side B — phase survival:
    C15_LAVES must remain defined with 18 active G parameters and remain
    equilibrium-stable in the Fe-free Mn–Ni–Si subsystem. The acceptance
    witness is on the AB2 line:
        Mn = 1/3, Ni = 8/15, Si = 2/15 (mole fractions).
    Acceptance requires stability at one or more tested points within
    673–2000 K; 500 K is retained only as a diagnostic point.
    The disabled reciprocal command requires Fe, so it is mathematically
    inactive in this subsystem. Therefore working and unpatched profiles
    must agree within numerical tolerance.

The earlier duplex-steel and Cr–Nb witnesses are not acceptance criteria:
- the modeled C15_LAVES phase contains only FE, MN, NI and SI;
- Cr–Nb in mc_fe v2.062 is represented by LAVES_PHASE, not C15_LAVES;
- the tested duplex compositions did not provide a C15_LAVES equilibrium
  witness and were methodologically unsuitable for this model.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

import numpy as np
import pandas as pd
from pycalphad import Database, equilibrium, variables as v
from pycalphad.core.utils import filter_phases, unpack_species


DEFAULT_HIGH_TEMP_COMPOSITION = (
    "CR=11.5,NI=0.7,MN=0.7,SI=0.3,C=0.20,"
    "MO=0.6,W=0.9,V=0.225"
)
TEMPERATURES_HIGH_K = (1800.0, 1900.0, 2000.0)

# Exact mole-fraction witness found by systematic Mn–Ni–Si search.
# It lies on the AB2 line: (Ni,Si)2Mn.
MN_NI_SI_WITNESS = {
    "MN": 1.0 / 3.0,
    "NI": 8.0 / 15.0,
    "SI": 2.0 / 15.0,
}
TEMPERATURES_SURVIVAL_K = (500.0, 700.0, 900.0, 1100.0)
DATABASE_VALID_MIN_K = 673.0
DATABASE_VALID_MAX_K = 2000.0
PRESENCE_THRESHOLD = 1e-6
PROFILE_DIFFERENCE_TOLERANCE = 1e-8


def find_root(explicit: str | None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
    else:
        candidates = [Path.cwd(), Path(__file__).resolve().parent.parent]
        root = next(
            (
                candidate.resolve()
                for candidate in candidates
                if (candidate / "app").is_dir()
            ),
            Path.cwd().resolve(),
        )
    if not (root / "app").is_dir():
        raise FileNotFoundError(f"В {root} нет папки app.")
    return root


def parse_composition(text: str) -> dict[str, float]:
    pattern = re.compile(
        r"([A-Za-z]{1,2})\s*=\s*([+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+))"
    )
    matches = list(pattern.finditer(text))
    if not matches:
        raise ValueError("Состав не распознан. Пример: CR=12,NI=0.6")
    remainder = re.sub(r"[\s,;]+", "", pattern.sub("", text))
    if remainder:
        raise ValueError(f"Непонятный фрагмент состава: {remainder!r}")
    result: dict[str, float] = {}
    for match in matches:
        element = match.group(1).upper()
        value = float(match.group(2).replace(",", "."))
        if element == "FE":
            raise ValueError("FE — элемент-основа; не указывайте его в добавках.")
        if element in result:
            raise ValueError(f"Элемент {element} указан дважды.")
        result[element] = value
    if sum(result.values()) >= 100:
        raise ValueError("Сумма добавок должна быть меньше 100 мас.%.")
    return result


def aggregate(eq: Any) -> dict[str, float]:
    names = np.asarray(eq.Phase.values, dtype=str).ravel()
    fractions = np.asarray(eq.NP.values, dtype=float).ravel()
    result: dict[str, float] = {}
    for name, fraction in zip(names, fractions):
        if name and np.isfinite(fraction) and fraction > 1e-12:
            result[str(name)] = result.get(str(name), 0.0) + float(fraction)
    return result


def calculate_fe_base_wt(
    db: Database,
    composition_wt: dict[str, float],
    temperature_k: float,
    *,
    pdens: int,
) -> dict[str, float]:
    elements = sorted(composition_wt)
    components = ["FE"] + elements + (["VA"] if "VA" in db.elements else [])
    mass_conditions = {
        v.W(element): float(value) / 100.0
        for element, value in composition_wt.items()
    }
    composition_conditions = dict(
        v.get_mole_fractions(mass_conditions, "FE", db)
    )
    phases = list(filter_phases(db, unpack_species(db, components)))
    eq = equilibrium(
        db,
        components,
        phases,
        {
            v.N: 1.0,
            v.P: 101325.0,
            v.T: float(temperature_k),
            **composition_conditions,
        },
        calc_opts={"pdens": int(pdens)},
    )
    return aggregate(eq)


def calculate_mn_nisi_witness(
    db: Database,
    temperature_k: float,
    *,
    pdens: int,
) -> dict[str, float]:
    components = ["MN", "NI", "SI", "VA"]
    phases = list(filter_phases(db, unpack_species(db, components)))
    eq = equilibrium(
        db,
        components,
        phases,
        {
            v.N: 1.0,
            v.P: 101325.0,
            v.T: float(temperature_k),
            v.X("MN"): MN_NI_SI_WITNESS["MN"],
            v.X("NI"): MN_NI_SI_WITNESS["NI"],
        },
        calc_opts={"pdens": max(300, int(pdens))},
    )
    return aggregate(eq)


def max_profile_difference(
    left: dict[str, float],
    right: dict[str, float],
) -> float:
    phases = set(left) | set(right)
    return max(
        (
            abs(left.get(phase, 0.0) - right.get(phase, 0.0))
            for phase in phases
        ),
        default=0.0,
    )


def phase_field(result: dict[str, float], threshold: float = 1e-8) -> str:
    return "; ".join(
        f"{phase}={fraction:.8f}"
        for phase, fraction in sorted(
            result.items(),
            key=lambda item: item[1],
            reverse=True,
        )
        if fraction > threshold
    )


def normalized_command_hashes(commands: list[str]) -> list[str]:
    return sorted(
        hashlib.sha256(
            re.sub(r"\s+", " ", command.strip().upper()).encode("utf-8")
        ).hexdigest()
        for command in commands
    )


def phase_commands(guard, path: Path, phase: str) -> list[str]:
    text, _ = guard.read_text(path)
    return [
        command.text.strip()
        for command in guard.iter_active_commands(text)
        if guard.parameter_phase(command.text) == ("G", phase.upper())
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root")
    parser.add_argument(
        "--high-temp-composition",
        default=DEFAULT_HIGH_TEMP_COMPOSITION,
        help=(
            "20Х12ВНМФ midpoint proxy in wt.%%. Pass an exact heat analysis "
            "here when available."
        ),
    )
    parser.add_argument("--pdens", type=int, default=100)
    parser.add_argument(
        "--structural-only",
        action="store_true",
        help="проверить только паспорт и число активных параметров",
    )
    parser.add_argument(
        "--skip-unpatched-symptom",
        action="store_true",
        help="не требовать воспроизведения симптома на непатченной копии",
    )
    args = parser.parse_args()

    root = find_root(args.project_root)
    sys.path.insert(0, str(root / "app"))
    import thermogar_database_guard as guard

    working_path = guard.fe_database_path(root, guard.FE_PROFILE_CANONICAL)
    diagnostic_path = guard.fe_database_path(
        root, guard.FE_PROFILE_EXPERIMENTAL
    )
    manifest = guard.load_profile_manifest(root)
    patch = guard.compatibility_patch_record(manifest) or {}

    print("THERMOGAR STAGE 13.2 — FE C15_LAVES ACCEPTANCE")
    print("Project:", root)
    print("Working:", working_path)
    print("Unpatched diagnostic:", diagnostic_path)

    working_c15 = phase_commands(guard, working_path, "C15_LAVES")
    diagnostic_c15 = phase_commands(guard, diagnostic_path, "C15_LAVES")
    working_old = phase_commands(guard, working_path, "LAVES_PHASE")
    diagnostic_old = phase_commands(guard, diagnostic_path, "LAVES_PHASE")

    structural_checks = {
        "patch id recorded": patch.get("patch_id") == guard.FE_PATCH_ID,
        "patch applied": patch.get("applied") is True,
        "matched exactly one command": patch.get("matched_active_commands") == 1,
        "working -9e6 inactive": len(
            guard.find_exact_suspect_commands(working_path)
        )
        == 0,
        "diagnostic -9e6 active": len(
            guard.find_exact_suspect_commands(diagnostic_path)
        )
        == 1,
        "working C15_LAVES has 18 G parameters": len(working_c15) == 18,
        "diagnostic C15_LAVES has 19 G parameters": len(diagnostic_c15) == 19,
        "C15_LAVES changed by exactly one parameter": (
            len(diagnostic_c15) - len(working_c15) == 1
        ),
        "LAVES_PHASE unchanged": (
            normalized_command_hashes(working_old)
            == normalized_command_hashes(diagnostic_old)
        ),
    }

    print("\n=== STRUCTURAL CHECK ===")
    for label, passed in structural_checks.items():
        print(("PASS" if passed else "FAIL") + ":", label)
    if not all(structural_checks.values()):
        print("RESULT: FAILED")
        return 1

    try:
        working_db = Database(str(working_path))
        diagnostic_db = Database(str(diagnostic_path))
    except Exception as error:
        print("DATABASE LOAD: FAILED")
        print(type(error).__name__ + ":", error)
        return 1

    if "C15_LAVES" not in working_db.phases:
        print("FAIL: C15_LAVES phase is absent from working database")
        return 1
    print("PASS: C15_LAVES phase remains defined")

    constituents = {
        str(species)
        for sublattice in working_db.phases["C15_LAVES"].constituents
        for species in sublattice
    }
    expected_constituents = {"FE", "MN", "NI", "SI"}
    constituent_check = constituents == expected_constituents
    print(
        ("PASS" if constituent_check else "FAIL")
        + ": C15_LAVES model constituents are FE, MN, NI, SI"
    )
    if not constituent_check:
        print("Actual constituents:", sorted(constituents))
        return 1

    if args.structural_only:
        print("RESULT: PASSED (structural only)")
        return 0

    output_dir = root / "results" / "validation" / "stage13_2"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Side A — high-temperature liquidus restoration
    # ------------------------------------------------------------------
    high_composition = parse_composition(args.high_temp_composition)
    high_rows: list[dict[str, Any]] = []
    print("\n=== HIGH-TEMPERATURE MELTING CHECK ===")
    print("Benchmark composition, wt.%:", args.high_temp_composition)
    print(
        "Note: this is a midpoint proxy from published 20Х12ВНМФ grade "
        "ranges. Use --high-temp-composition for an exact heat analysis."
    )

    working_liquid_passed = True
    diagnostic_symptom_seen = False
    for temperature_k in TEMPERATURES_HIGH_K:
        working = calculate_fe_base_wt(
            working_db,
            high_composition,
            temperature_k,
            pdens=args.pdens,
        )
        diagnostic = calculate_fe_base_wt(
            diagnostic_db,
            high_composition,
            temperature_k,
            pdens=args.pdens,
        )
        row = {
            "T_K": temperature_k,
            "working_LIQUID": working.get("LIQUID", 0.0),
            "working_C15_LAVES": working.get("C15_LAVES", 0.0),
            "diagnostic_LIQUID": diagnostic.get("LIQUID", 0.0),
            "diagnostic_C15_LAVES": diagnostic.get("C15_LAVES", 0.0),
        }
        high_rows.append(row)
        point_passed = (
            row["working_LIQUID"] >= 0.999999
            and row["working_C15_LAVES"] <= 1e-8
        )
        working_liquid_passed &= point_passed
        diagnostic_symptom_seen |= (
            row["diagnostic_LIQUID"] < 0.999
            and row["diagnostic_C15_LAVES"] > 1e-4
        )
        print(
            f"T={temperature_k:.0f} K | working LIQUID="
            f"{row['working_LIQUID']:.8f}, C15="
            f"{row['working_C15_LAVES']:.8f} | diagnostic LIQUID="
            f"{row['diagnostic_LIQUID']:.8f}, C15="
            f"{row['diagnostic_C15_LAVES']:.8f} | "
            + ("PASS" if point_passed else "FAIL")
        )

    print(
        ("PASS" if working_liquid_passed else "FAIL")
        + ": working profile reaches LIQUID=1.000 at 1800–2000 K"
    )
    diagnostic_symptom_passed = (
        True if args.skip_unpatched_symptom else diagnostic_symptom_seen
    )
    if args.skip_unpatched_symptom:
        print("SKIP: unpatched high-temperature symptom reproduction")
    else:
        print(
            ("PASS" if diagnostic_symptom_passed else "FAIL")
            + ": unpatched profile reproduces the high-T C15 symptom"
        )

    # ------------------------------------------------------------------
    # Side B — C15_LAVES survives in a subsystem where patch is inactive
    # ------------------------------------------------------------------
    print("\n=== Mn–Ni–Si C15_LAVES SURVIVAL CHECK ===")
    print(
        "Witness, at.%: MN=33.333333, NI=53.333333, SI=13.333333 "
        "((Ni,Si)2Mn AB2 line)"
    )
    print(
        "The disabled FE,NI:MN,SI reciprocal parameter requires Fe and "
        "is inactive in this Fe-free subsystem."
    )

    survival_rows: list[dict[str, Any]] = []
    survival_seen_in_range = False
    invariance_passed = True
    maximum_profile_difference = 0.0
    best_witness: dict[str, Any] | None = None

    for temperature_k in TEMPERATURES_SURVIVAL_K:
        working = calculate_mn_nisi_witness(
            working_db,
            temperature_k,
            pdens=args.pdens,
        )
        diagnostic = calculate_mn_nisi_witness(
            diagnostic_db,
            temperature_k,
            pdens=args.pdens,
        )
        working_c15_fraction = float(working.get("C15_LAVES", 0.0))
        diagnostic_c15_fraction = float(diagnostic.get("C15_LAVES", 0.0))
        difference = max_profile_difference(working, diagnostic)
        maximum_profile_difference = max(
            maximum_profile_difference,
            difference,
        )
        in_database_range = (
            DATABASE_VALID_MIN_K <= temperature_k <= DATABASE_VALID_MAX_K
        )
        if working_c15_fraction > PRESENCE_THRESHOLD and in_database_range:
            survival_seen_in_range = True
            if (
                best_witness is None
                or working_c15_fraction > best_witness["working_C15_LAVES"]
            ):
                best_witness = {
                    "T_K": temperature_k,
                    "working_C15_LAVES": working_c15_fraction,
                    "diagnostic_C15_LAVES": diagnostic_c15_fraction,
                }
        if difference > PROFILE_DIFFERENCE_TOLERANCE:
            invariance_passed = False

        row = {
            "T_K": temperature_k,
            "MN_at_percent": 100.0 * MN_NI_SI_WITNESS["MN"],
            "NI_at_percent": 100.0 * MN_NI_SI_WITNESS["NI"],
            "SI_at_percent": 100.0 * MN_NI_SI_WITNESS["SI"],
            "working_C15_LAVES": working_c15_fraction,
            "diagnostic_C15_LAVES": diagnostic_c15_fraction,
            "maximum_phase_difference": difference,
            "working_phase_field": phase_field(working),
            "diagnostic_phase_field": phase_field(diagnostic),
        }
        survival_rows.append(row)

        print(
            f"T={temperature_k:.0f} K | working C15="
            f"{working_c15_fraction:.8f} | diagnostic C15="
            f"{diagnostic_c15_fraction:.8f} | max Δ={difference:.3e} | "
            + (
                "PASS"
                if difference <= PROFILE_DIFFERENCE_TOLERANCE
                else "FAIL"
            )
        )

    print(
        ("PASS" if survival_seen_in_range else "FAIL")
        + ": C15_LAVES remains equilibrium-stable after the patch "
        f"within {DATABASE_VALID_MIN_K:.0f}–{DATABASE_VALID_MAX_K:.0f} K"
    )
    print(
        ("PASS" if invariance_passed else "FAIL")
        + ": working and unpatched profiles agree in Fe-free Mn–Ni–Si"
    )
    if best_witness:
        print(
            "Best witness: T="
            f"{best_witness['T_K']:.0f} K, C15_LAVES="
            f"{best_witness['working_C15_LAVES']:.8f}"
        )

    pd.DataFrame(high_rows).to_csv(
        output_dir / "high_temperature_liquidus_check.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(survival_rows).to_csv(
        output_dir / "mn_ni_si_c15_survival_check.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary = {
        "schema_version": 2,
        "stage": "13.2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "patch_id": guard.FE_PATCH_ID,
        "structural_checks": structural_checks,
        "c15_model_constituents": sorted(constituents),
        "high_temperature_composition_wt": args.high_temp_composition,
        "high_temperature_rows": high_rows,
        "working_liquidus_restored": working_liquid_passed,
        "unpatched_symptom_reproduced": diagnostic_symptom_seen,
        "mn_ni_si_witness_at_percent": {
            element: 100.0 * value
            for element, value in MN_NI_SI_WITNESS.items()
        },
        "mn_ni_si_rows": survival_rows,
        "c15_phase_survival_found_in_database_range": survival_seen_in_range,
        "database_valid_temperature_range_K": [
            DATABASE_VALID_MIN_K,
            DATABASE_VALID_MAX_K,
        ],
        "best_c15_survival_point": best_witness,
        "patch_inactive_subsystem_invariance": invariance_passed,
        "maximum_working_diagnostic_phase_difference": (
            maximum_profile_difference
        ),
        "limitations": [
            "The default 20Х12ВНМФ case is a midpoint of published grade ranges, not a certified heat analysis.",
            "The Mn–Ni–Si witness proves numerical survival of C15_LAVES within 673–2000 K and patch inactivity in an Fe-free subsystem; it is not an experimental validation of the phase fraction.",
            "The earlier duplex-steel and Cr–Nb checks are retained only as historical diagnostics and are not acceptance criteria for this C15_LAVES model.",
            "Patch status remains pending_upstream_confirmation until MatCalc authors clarify the -9e6 reciprocal parameter.",
        ],
    }
    (output_dir / "stage13_2_acceptance.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    passed = (
        working_liquid_passed
        and diagnostic_symptom_passed
        and survival_seen_in_range
        and invariance_passed
    )
    print("\nRESULT:", "PASSED" if passed else "FAILED")
    print("Reports:", output_dir)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
