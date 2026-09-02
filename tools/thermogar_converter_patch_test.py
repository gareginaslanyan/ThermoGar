#!/usr/bin/env python3
"""Fail-closed structural test for TG-FE-2062-C15-001.

The test does not need pycalphad or the real database. It verifies that the
converter comments exactly one reviewed command, keeps the other 18
C15_LAVES G parameters and all LAVES_PHASE parameters, records the patch in
JSON-compatible metadata, and stops if zero or two exact matches are found.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile


def load_converter(project_root: Path):
    path = project_root / "scripts" / "thermogar_convert_matcalc_tdb.py"
    spec = importlib.util.spec_from_file_location(
        "thermogar_converter_patch_self_test", path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Не удалось загрузить конвертер: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_merger(project_root: Path):
    path = project_root / "scripts" / "thermogar_merge_matcalc_ddb.py"
    spec = importlib.util.spec_from_file_location(
        "thermogar_merger_patch_self_test", path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Не удалось загрузить merger: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_database(exact_count: int) -> str:
    lines = [
        "$ mc_fe_v2.062.tdb\n",
        "ELEMENT VA VACUUM 0 0 0 !\n",
        "ELEMENT FE BCC_A2 55.845 0 0 !\n",
        "ELEMENT MN BCC_A2 54.938 0 0 !\n",
        "ELEMENT NI FCC_A1 58.693 0 0 !\n",
        "ELEMENT SI DIAMOND_A4 28.085 0 0 !\n",
        "PHASE C15_LAVES % 2 1 1 !\n",
        "CONSTITUENT C15_LAVES :FE,NI:MN,SI: !\n",
        "PHASE LAVES_PHASE % 2 1 1 !\n",
        "CONSTITUENT LAVES_PHASE :FE,NI:MN,SI: !\n",
    ]
    for order in range(18):
        lines.append(
            "PARAMETER G(C15_LAVES,FE:MN;"
            f"{order}) 273.00 +{1000 + order}; 6000.00 N !\n"
        )
    for _ in range(exact_count):
        lines.append(
            "PARAMETER G(C15_LAVES,FE,NI:MN,SI;0) "
            "273.00 -9e6; 6000.00 N !\n"
        )
    lines.extend(
        [
            "PARAMETER G(LAVES_PHASE,FE:MN;0) "
            "273.00 +100; 6000.00 N !\n",
            "PARAMETER G(LAVES_PHASE,NI:SI;0) "
            "273.00 +200; 6000.00 N !\n",
        ]
    )
    return "".join(lines)


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    converter = load_converter(project_root)
    merger = load_merger(project_root)
    source_name = Path("mc_fe_v2062.tdb")

    source = synthetic_database(1)
    patched, records = converter.apply_known_compatibility_patches(
        source, source_name, "thermogar"
    )
    diagnostic, diagnostic_records = (
        converter.apply_known_compatibility_patches(
            source, source_name, "upstream"
        )
    )

    checks = {
        "patch id": records[0].get("patch_id")
        == converter.FE_C15_PATCH_ID,
        "patch applied": records[0].get("applied") is True,
        "matched exactly one": records[0].get("matched_active_commands")
        == 1,
        "working exact command inactive": not any(
            converter.is_exact_c15_minus_9e6_command(command.text)
            for command in converter.iter_active_commands(patched)
        ),
        "diagnostic exact command active": sum(
            converter.is_exact_c15_minus_9e6_command(command.text)
            for command in converter.iter_active_commands(diagnostic)
        )
        == 1,
        "working C15 parameter count": len(
            converter.phase_parameter_commands(patched, "C15_LAVES")
        )
        == 18,
        "diagnostic C15 parameter count": len(
            converter.phase_parameter_commands(diagnostic, "C15_LAVES")
        )
        == 19,
        "LAVES_PHASE unchanged": (
            converter.command_list_sha256(
                converter.phase_parameter_commands(patched, "LAVES_PHASE")
            )
            == converter.command_list_sha256(
                converter.phase_parameter_commands(
                    diagnostic, "LAVES_PHASE"
                )
            )
        ),
        "diagnostic record unapplied": diagnostic_records[0].get("applied")
        is False,
    }

    for exact_count in (0, 2):
        label = f"fail-closed for {exact_count} exact matches"
        try:
            converter.apply_known_compatibility_patches(
                synthetic_database(exact_count),
                source_name,
                "thermogar",
            )
        except RuntimeError:
            checks[label] = True
        else:
            checks[label] = False

    # Full converter + merger passport inheritance check.
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary = Path(temporary_directory)
        source_path = temporary / "mc_fe_v2062.tdb"
        converted_path = temporary / "mc_fe_v2062.thermogar.tdb"
        source_path.write_text(source, encoding="utf-8")
        report = converter.convert(
            source_path,
            converted_path,
            fe_c15_mode="patched",
        )
        report_path = converted_path.with_suffix(
            converted_path.suffix + ".json"
        )
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        disabled = report.get("disabled_thermodynamic_parameters", [])
        checks["converter JSON records disabled parameter"] = bool(
            isinstance(disabled, list)
            and len(disabled) == 1
            and disabled[0].get("patch_id") == converter.FE_C15_PATCH_ID
            and disabled[0].get("matched_active_commands") == 1
        )

        ddb_path = temporary / "empty.ddb"
        ddb_path.write_text("$ no active DDB commands\n", encoding="utf-8")
        merged_path = temporary / "merged.tdb"
        merged_report = merger.merge(
            converted_path,
            ddb_path,
            merged_path,
        )
        inherited = merged_report.get(
            "disabled_thermodynamic_parameters", []
        )
        checks["merged JSON inherits disabled parameter"] = bool(
            isinstance(inherited, list)
            and len(inherited) == 1
            and inherited[0].get("patch_id")
            == converter.FE_C15_PATCH_ID
        )
        active_merged_text = "\n".join(
            line.split("$", 1)[0]
            for line in merged_path.read_text(encoding="utf-8").splitlines()
        )
        checks["merged TDB has no active -9e6"] = "-9e6" not in active_merged_text

    print("THERMOGAR STAGE 13.2 — CONVERTER PATCH TEST")
    for label, passed in checks.items():
        print(("PASS" if passed else "FAIL") + ":", label)

    passed = all(checks.values())
    print("RESULT:", "PASSED" if passed else "FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
