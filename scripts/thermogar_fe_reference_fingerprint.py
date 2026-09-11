"""Generate the mc_fe reference-base fingerprint shipped instead of the base.

Why a fingerprint
-----------------
The diagnostic panel compares the working steel database against the unpatched
upstream copy in ``databases/diagnostic/fe/``.  That copy is a second
full-size TDB and is itself an ODbL derivative, so it is not placed in the
installer.  Without it the panel has nothing to compare against and honestly
reports that no cross-check was performed.

This script distils the reference base down to the handful of values the panel
actually reads from it, writes them next to the working passport, and lets the
panel finish the cross-check from the fingerprint when the base is absent.  The
fingerprint is a few hundred bytes, carries no thermodynamic data, and is
therefore not a database extract in the ODbL sense.

Everything here is read-only with respect to the databases.  The values are
computed by the guard's own helpers, so the fingerprint cannot disagree with
what the panel would have measured on the file itself.

Usage
-----
    python scripts/thermogar_fe_reference_fingerprint.py
    python scripts/thermogar_fe_reference_fingerprint.py --check
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Iterable

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "app"))

import thermogar_database_guard as guard  # noqa: E402

SCHEMA_VERSION = "THERMOGAR-FE-REFERENCE-FINGERPRINT-1"


def build_fingerprint(project_root: pathlib.Path) -> dict[str, object]:
    paths = guard.profile_paths(project_root)
    upstream = paths[guard.FE_PROFILE_UPSTREAM]
    if not upstream.is_file():
        raise SystemExit(
            f"reference base not found: {upstream}\n"
            "The fingerprint can only be generated in a tree that still has "
            "databases/diagnostic/fe/."
        )

    c15 = guard.phase_parameter_commands(upstream, "C15_LAVES")
    laves = guard.phase_parameter_commands(upstream, "LAVES_PHASE")
    suspect = guard.find_exact_suspect_commands(upstream)
    reciprocal = guard.find_c15_reciprocal_commands(upstream)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "scripts/thermogar_fe_reference_fingerprint.py",
        "profile_key": guard.FE_PROFILE_UPSTREAM,
        "patch_id": guard.PATCH_ID,
        "reference_database_path": str(
            guard.UPSTREAM_FE_RELATIVE_PATH
        ).replace("\\", "/"),
        "reference_database_shipped": False,
        "reference_database_sha256": guard.file_sha256(upstream),
        "reference_database_size_bytes": upstream.stat().st_size,
        "c15_laves_g_parameter_count": len(c15),
        "c15_laves_g_parameter_list_sha256": guard.command_list_sha256(c15),
        "c15_reciprocal_command_count": len(reciprocal),
        "exact_suspect_command_signature": guard.SUSPECT_PARAMETER_SIGNATURE,
        "exact_suspect_command_present": bool(suspect),
        "laves_phase_g_parameter_count": len(laves),
        "laves_phase_g_parameter_list_sha256": guard.command_list_sha256(laves),
        "value_source": (
            "app/thermogar_database_guard.py helpers: file_sha256, "
            "phase_parameter_commands, find_exact_suspect_commands, "
            "find_c15_reciprocal_commands, command_list_sha256"
        ),
        "note": (
            "Shipped in place of databases/diagnostic/fe/. It contains only "
            "digests and counts, no thermodynamic parameters."
        ),
    }


def fingerprint_path(project_root: pathlib.Path) -> pathlib.Path:
    return project_root / guard.UPSTREAM_FINGERPRINT_RELATIVE_PATH


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the fingerprint on disk with a freshly computed one",
    )
    parser.add_argument(
        "--project-root",
        default=str(ROOT),
        help="repository root to read the reference base from",
    )
    args = parser.parse_args(argv)

    project_root = pathlib.Path(args.project_root).resolve()
    payload = build_fingerprint(project_root)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    path = fingerprint_path(project_root)

    if args.check:
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current == text:
            print(f"ok {path.relative_to(project_root)}")
            return 0
        print(f"DRIFT {path.relative_to(project_root)}")
        return 1

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(
        f"wrote {path.relative_to(project_root)}: "
        f"C15_LAVES G-parameters {payload['c15_laves_g_parameter_count']}, "
        f"-9e6 present {payload['exact_suspect_command_present']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
