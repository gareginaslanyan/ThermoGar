"""Write the phase-count note that sits next to a converted database passport.

Why this script exists
----------------------
``thermodynamic_phase_count`` in the converted-database report JSON was once
produced by a line-oriented ``^PHASE`` search.  That search also caught
bibliography entries starting with the ordinary word ``Phase`` -- for ``mc_fe``
it counted ``DIAGRAM``, ``EQUILIBRIA``, ``EQUILBRIA`` (the typo is upstream's)
and ``STABILITY`` as phases, giving 136 instead of 132.  The converters in this
directory have since been fixed: they cut the text at ``LIST_OF_REFERENCES``
and only accept ``!``-terminated active commands.

The fe report JSON still carries the old 136 because its SHA-256 and byte size
are pinned by the runtime loaders and by several config domains, and the chain
of re-signatures reaches files that no single wave owns.  Rather than break
those pins for a cosmetic number, the true count and the way it is obtained are
recorded beside the passport, in this note.  The note is generated, not typed,
so it cannot drift away from the counting code.

The databases themselves are never read for anything but counting, and never
written.

Usage
-----
    python scripts/thermogar_phase_count_note.py            # all known targets
    python scripts/thermogar_phase_count_note.py --check    # verify, write nothing
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import sys
from typing import Iterable

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

COUNT_METHOD = (
    "declared thermodynamic phases after truncating the TDB text at "
    "LIST_OF_REFERENCES, counting only !-terminated active PHASE commands, "
    "unique names, part before the first colon"
)

TARGETS = (
    "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb",
    "databases/converted/fe/mc_fe_v2062.thermogar.tdb",
)


def load_converter():
    """Load the current merge converter as the single source of the counter."""
    path = HERE / "thermogar_merge_matcalc_ddb_v3.py"
    spec = importlib.util.spec_from_file_location("tg_merge_v3", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def naive_phase_count(converter, text: str) -> int:
    """Reproduce the discarded line-oriented count, for the record only."""
    active = converter.strip_tdb_comments(text).upper()
    return len(set(re.findall(r"(?m)^\s*PHASE\s+([A-Z0-9_:+-]+)", active)))


def report_path_for(tdb: pathlib.Path) -> pathlib.Path:
    return tdb.with_suffix(tdb.suffix + ".json")


def note_path_for(tdb: pathlib.Path) -> pathlib.Path:
    return tdb.with_suffix(".phase_count.json")


def build_note(converter, relative: str) -> dict[str, object]:
    tdb = ROOT / relative
    text, encoding = converter.read_text(tdb)
    phases = sorted(converter.declared_phases(text))
    naive = naive_phase_count(converter, text)

    report = report_path_for(tdb)
    reported = None
    if report.is_file():
        payload = json.loads(report.read_text(encoding="utf-8-sig"))
        if isinstance(payload, dict):
            reported = payload.get("thermodynamic_phase_count")

    note: dict[str, object] = {
        "schema_version": "THERMOGAR-PHASE-COUNT-NOTE-1",
        "database_path": relative,
        "database_encoding": encoding,
        "thermodynamic_phase_count": len(phases),
        "count_method": COUNT_METHOD,
        "count_method_source": "scripts/thermogar_merge_matcalc_ddb_v3.py:declared_phases",
        "superseded_count_method": (
            "line-oriented ^PHASE search over the whole file, which also "
            "matched bibliography entries beginning with the word Phase"
        ),
        "superseded_count": naive,
        "conversion_report_path": str(report.relative_to(ROOT)).replace("\\", "/"),
        "conversion_report_phase_count": reported,
        "conversion_report_is_stale": reported is not None and reported != len(phases),
        "conversion_report_stale_reason": (
            "The report SHA-256 and byte size are pinned by the runtime "
            "loaders and by the ne03/ne04 config domains. Re-signing the "
            "report cascades into files outside one wave's ownership, so the "
            "stale field is documented here instead of rewritten."
        ),
        "phases": phases,
    }
    return note


def write_notes(targets: Iterable[str], check_only: bool) -> int:
    converter = load_converter()
    failures = 0
    for relative in targets:
        note = build_note(converter, relative)
        path = note_path_for(ROOT / relative)
        text = json.dumps(note, indent=2, ensure_ascii=False) + "\n"
        if check_only:
            current = path.read_text(encoding="utf-8") if path.is_file() else None
            state = "ok" if current == text else "DRIFT"
            if state == "DRIFT":
                failures += 1
            print(f"{state} {path.relative_to(ROOT)}")
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
            print(
                f"wrote {path.relative_to(ROOT)}: "
                f"{note['thermodynamic_phase_count']} phases "
                f"(superseded count {note['superseded_count']})"
            )
    return failures


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the notes on disk match what the counter produces now",
    )
    parser.add_argument(
        "database",
        nargs="*",
        default=None,
        help="repository-relative TDB paths; defaults to the fe pair",
    )
    args = parser.parse_args(argv)
    targets = args.database or list(TARGETS)
    return 1 if write_notes(targets, args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
