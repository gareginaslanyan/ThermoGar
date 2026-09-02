#!/usr/bin/env python3
"""ThermoGar Stage 13.2 — паспорт рабочего патча Fe-базы."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root")
    args = parser.parse_args()

    root = find_root(args.project_root)
    sys.path.insert(0, str(root / "app"))

    from thermogar_database_guard import (
        FE_PATCH_ID,
        FE_PROFILE_CANONICAL,
        FE_PROFILE_EXPERIMENTAL,
        compatibility_patch_record,
        fe_database_path,
        find_exact_suspect_commands,
        command_list_sha256,
        passport_dataframe,
        phase_parameter_commands,
    )

    working = fe_database_path(root, FE_PROFILE_CANONICAL)
    upstream = fe_database_path(root, FE_PROFILE_EXPERIMENTAL)
    patch = compatibility_patch_record(root) or {}

    print("THERMOGAR STAGE 13.2 — FE DATABASE PASSPORT")
    print("Project:", root)
    print("Patch:", patch.get("patch_id", "not found"))
    print("Working:", working)
    print("Upstream diagnostic:", upstream)

    working_c15 = phase_parameter_commands(working, "C15_LAVES")
    upstream_c15 = phase_parameter_commands(upstream, "C15_LAVES")
    working_laves = phase_parameter_commands(working, "LAVES_PHASE")
    upstream_laves = phase_parameter_commands(upstream, "LAVES_PHASE")

    checks = {
        "patch id": patch.get("patch_id") == FE_PATCH_ID,
        "patch applied": patch.get("applied") is True,
        "matched one active command": (
            patch.get("matched_active_commands") == 1
        ),
        "working exact -9e6 inactive": (
            len(find_exact_suspect_commands(working)) == 0
        ),
        "upstream exact -9e6 active": (
            len(find_exact_suspect_commands(upstream)) == 1
        ),
        "working C15 parameter count": len(working_c15) == 18,
        "upstream C15 parameter count": len(upstream_c15) == 19,
        "LAVES_PHASE unchanged": (
            command_list_sha256(working_laves)
            == command_list_sha256(upstream_laves)
        ),
    }
    for label, passed in checks.items():
        print(("PASS" if passed else "FAIL") + ":", label)

    print()
    print(passport_dataframe(root, FE_PROFILE_CANONICAL).to_string(index=False))
    passed = all(checks.values())
    print("RESULT:", "PASSED" if passed else "FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
