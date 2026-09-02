"""Merge an open MatCalc diffusion-mobility DDB into a GarCalc TDB.

The thermodynamic input must already be converted to pycalphad-compatible TDB
syntax (for example with ``garcalc_convert_matcalc_tdb.py``). The source files
are never modified.

What this utility does
----------------------
* reads the elements and phases declared by the thermodynamic TDB;
* imports MatCalc MQ/MF/DQ/DF mobility parameters whose phase and species are
  compatible with that TDB;
* preserves incompatible commands as comments instead of deleting them;
* inserts mobility commands before the thermodynamic LIST_OF_REFERENCES block;
* keeps a fully commented archive of the original DDB in the output file;
* writes a JSON audit report;
* optionally validates the merged file with the installed pycalphad version.

This script makes the mobility data readable and queryable by pycalphad. It
must not be interpreted as implementing a diffusion or precipitation solver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import traceback
from collections import Counter
from pathlib import Path
from typing import Iterable

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
KINETIC_PARAMETER_TYPES = {"MQ", "MF", "DQ", "DF"}


def read_text(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"Could not decode {path}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def strip_tdb_comments(text: str) -> str:
    """Remove `$` comments while preserving line breaks."""
    return "\n".join(line.split("$", 1)[0] for line in text.splitlines())


def active_commands(text: str) -> list[str]:
    """Return active TDB commands without their terminal exclamation marks."""
    uncommented = strip_tdb_comments(text)
    return [piece.strip() for piece in uncommented.split("!") if piece.strip()]


def command_keyword(command: str) -> str:
    match = re.match(r"\s*([A-Za-z_]+)", command)
    return match.group(1).upper() if match else "UNKNOWN"


def comment_command(command: str, reason: str) -> str:
    lines = [f"$ GARCALC_DISABLED_MOBILITY: {reason}"]
    for line in command.splitlines():
        lines.append(line if line.lstrip().startswith("$") else "$" + line)
    lines.append("$!")
    return "\n".join(lines)


def comment_archive(text: str, source_name: str) -> str:
    lines = [
        "$" * 78,
        f"$ GARCALC_SOURCE_ARCHIVE_BEGIN: {source_name}",
        "$ Original DDB retained below as comments for traceability.",
        "$" * 78,
    ]
    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        lines.append(line if line.lstrip().startswith("$") else "$" + line)
    lines.extend(
        [
            "$" * 78,
            f"$ GARCALC_SOURCE_ARCHIVE_END: {source_name}",
            "$" * 78,
        ]
    )
    return "\n".join(lines)


def normalize_reference_keys(command: str) -> tuple[str, int]:
    """Sanitize active REF keys to the character set accepted by pycalphad."""
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        raw = match.group(1).strip()
        clean = re.sub(r"[^A-Za-z0-9_:+-]", "_", raw)
        clean = re.sub(r"_+", "_", clean).strip("_") or "UNSPECIFIED"
        if clean != raw:
            count += 1
        return "REF:" + clean

    result = re.sub(r"(?i)\bREF\s*:\s*([^\s!;]+)", repl, command)
    return result, count


def parse_parameter_header(
    command: str,
) -> tuple[str, str, str, str] | None:
    """Return parameter type, phase, diffusing species and constituents."""
    match = re.match(
        r"(?is)^\s*PARAMETER\s+([A-Za-z]+)\s*\(\s*"
        r"([A-Za-z0-9_:+-]+)\s*&\s*([A-Za-z]{1,2})\s*,\s*"
        r"([^)]*)\)",
        command,
    )
    if not match:
        return None
    parameter_type, phase, diffusing_species, constituents = match.groups()
    # The optional Redlich-Kister order (e.g. ;0, ;1, ;2) belongs to the
    # parameter header, not to the final sublattice constituent.
    constituents = re.sub(r";\s*[0-9]+\s*$", "", constituents)
    return (
        parameter_type.upper(),
        phase.upper(),
        diffusing_species.upper(),
        constituents.upper(),
    )


def constituent_species(constituents: str) -> set[str]:
    """Extract simple species names from a MatCalc mobility parameter header."""
    result: set[str] = set()
    for token in re.split(r"[:,\s]+", constituents):
        token = token.strip().upper()
        if not token or token == "*":
            continue
        result.add(token)
    return result


def declared_elements(text: str) -> set[str]:
    active = strip_tdb_comments(text).upper()
    return set(re.findall(r"(?m)^\s*ELEMENT\s+([A-Z]{1,2})\s", active))


def declared_phases(text: str) -> set[str]:
    """Return phases declared by active, terminated TDB commands only.

    A line-oriented regex is unsafe here because bibliography entries can
    legitimately start with the ordinary word ``Phase``.  The reference
    section is not TDB command input and active commands are ``!`` terminated.
    Reject an unterminated ``PHASE`` remainder instead of silently counting it.
    """
    active = strip_tdb_comments(text)
    references = re.search(
        r"(?im)^\s*LIST(?:_|\s+|-)+OF(?:_|\s+|-)+REFERENCES\b",
        active,
    )
    if references:
        active = active[: references.start()]

    pieces = active.split("!")
    remainder = pieces.pop()
    if remainder.strip() and command_keyword(remainder) == "PHASE":
        raise RuntimeError(
            "Unterminated active PHASE command before LIST_OF_REFERENCES"
        )

    phases: set[str] = set()
    for command in pieces:
        command = command.strip()
        if not command or command_keyword(command) != "PHASE":
            continue
        match = re.match(
            r"(?is)^\s*PHASE\s+([A-Z0-9_:+-]+)(?:\s|$)", command
        )
        if not match:
            raise RuntimeError(f"Malformed active PHASE command: {command!r}")
        phases.add(match.group(1).upper().split(":", 1)[0])
    return phases


def declared_functions(text: str) -> set[str]:
    active = strip_tdb_comments(text).upper()
    return set(
        re.findall(r"(?m)^\s*FUNCTION\s+([A-Z0-9_:+-]+)", active)
    )


def function_name(command: str) -> str | None:
    match = re.match(r"(?is)^\s*FUNCTION\s+([A-Za-z0-9_:+-]+)", command)
    return match.group(1).upper() if match else None


def insert_before_reference_list(thermo_text: str, block: str) -> tuple[str, bool]:
    marker = re.search(
        r"(?im)^(?![ \t]*\$)[ \t]*LIST[_-]OF[_-]REFERENCES\b",
        thermo_text,
    )
    if marker is None:
        return thermo_text.rstrip() + "\n\n" + block.rstrip() + "\n", False
    return (
        thermo_text[: marker.start()].rstrip()
        + "\n\n"
        + block.rstrip()
        + "\n\n"
        + thermo_text[marker.start() :].lstrip(),
        True,
    )


def build_mobility_block(
    ddb_text: str,
    thermo_elements: set[str],
    thermo_phases: set[str],
    thermo_functions: set[str],
    source_name: str,
) -> tuple[str, dict[str, object]]:
    retained_functions: list[str] = []
    retained_diffusion: list[str] = []
    retained_parameters: list[str] = []
    disabled_commands: list[str] = []

    retained_by_type: Counter[str] = Counter()
    retained_by_phase: Counter[str] = Counter()
    disabled_by_reason: Counter[str] = Counter()
    disabled_by_species: Counter[str] = Counter()
    duplicate_functions: list[str] = []
    normalized_reference_keys = 0
    seen_ddb_functions: set[str] = set()

    commands = active_commands(ddb_text)

    for command in commands:
        keyword = command_keyword(command)

        # The final reference bibliography is preserved in the commented source
        # archive. It is not activated because the thermodynamic TDB already owns
        # the final LIST_OF_REFERENCES section.
        if keyword == "LIST_OF_REFERENCES":
            continue

        normalized, changed_refs = normalize_reference_keys(command)
        normalized_reference_keys += changed_refs
        command = normalized

        if keyword == "FUNCTION":
            name = function_name(command)
            if name is None:
                reason = "unparseable FUNCTION command"
                disabled_by_reason[reason] += 1
                disabled_commands.append(comment_command(command, reason))
                continue
            if name in thermo_functions or name in seen_ddb_functions:
                duplicate_functions.append(name)
                reason = f"duplicate FUNCTION {name}"
                disabled_by_reason[reason] += 1
                disabled_commands.append(comment_command(command, reason))
                continue
            seen_ddb_functions.add(name)
            retained_functions.append(command.rstrip() + " !")
            continue

        if keyword == "DIFFUSION":
            # pycalphad accepts this command syntactically but currently stores no
            # settings from it. Preserve it for provenance and future readers.
            retained_diffusion.append(command.rstrip() + " !")
            continue

        if keyword != "PARAMETER":
            reason = f"unsupported DDB command {keyword}"
            disabled_by_reason[reason] += 1
            disabled_commands.append(comment_command(command, reason))
            continue

        header = parse_parameter_header(command)
        if header is None:
            reason = "unparseable mobility PARAMETER command"
            disabled_by_reason[reason] += 1
            disabled_commands.append(comment_command(command, reason))
            continue

        parameter_type, phase, diffusing_species, constituents = header

        if parameter_type not in KINETIC_PARAMETER_TYPES:
            reason = f"unsupported mobility parameter type {parameter_type}"
            disabled_by_reason[reason] += 1
            disabled_commands.append(comment_command(command, reason))
            continue

        reasons: list[str] = []
        if phase not in thermo_phases:
            reasons.append(f"phase {phase} is absent from thermodynamic TDB")

        used_species = constituent_species(constituents) | {diffusing_species}
        missing_species = sorted(
            species
            for species in used_species
            if species not in thermo_elements and species != "VA"
        )
        if missing_species:
            reasons.append(
                "species absent from thermodynamic TDB: "
                + ", ".join(missing_species)
            )
            disabled_by_species.update(missing_species)

        if reasons:
            reason = "; ".join(reasons)
            disabled_by_reason[reason] += 1
            disabled_commands.append(comment_command(command, reason))
            continue

        retained_parameters.append(command.rstrip() + " !")
        retained_by_type[parameter_type] += 1
        retained_by_phase[phase] += 1

    header_lines = [
        "$" * 78,
        "$ GARCALC MOBILITY BLOCK",
        f"$ Source DDB: {source_name}",
        "$ Compatible MQ/MF/DQ/DF parameters were selected against the",
        "$ elements and phases declared by the thermodynamic TDB.",
        "$ Incompatible source commands are retained below as comments.",
        "$" * 78,
    ]

    sections: list[str] = ["\n".join(header_lines)]

    if retained_diffusion:
        sections.extend(
            [
                "$ --- MatCalc diffusion settings (parsed but not evaluated by pycalphad) ---",
                "\n".join(retained_diffusion),
            ]
        )

    if retained_functions:
        sections.extend(
            [
                "$ --- Mobility helper functions ---",
                "\n\n".join(retained_functions),
            ]
        )

    if retained_parameters:
        sections.extend(
            [
                "$ --- Compatible mobility parameters ---",
                "\n\n".join(retained_parameters),
            ]
        )

    if disabled_commands:
        sections.extend(
            [
                "$ --- DDB commands disabled for this thermodynamic element set ---",
                "\n\n".join(disabled_commands),
            ]
        )

    report = {
        "ddb_active_commands_total": len(commands),
        "retained_functions": len(retained_functions),
        "retained_diffusion_commands": len(retained_diffusion),
        "retained_mobility_parameters": len(retained_parameters),
        "retained_parameters_by_type": dict(sorted(retained_by_type.items())),
        "retained_parameters_by_phase": dict(sorted(retained_by_phase.items())),
        "disabled_commands": len(disabled_commands),
        "disabled_commands_by_reason": dict(sorted(disabled_by_reason.items())),
        "disabled_parameters_by_missing_species": dict(
            sorted(disabled_by_species.items())
        ),
        "duplicate_functions": sorted(set(duplicate_functions)),
        "reference_keys_normalized": normalized_reference_keys,
    }

    return "\n\n".join(sections), report


def merge(
    thermo_path: Path,
    ddb_path: Path,
    destination: Path,
) -> dict[str, object]:
    thermo_text, thermo_encoding = read_text(thermo_path)
    ddb_text, ddb_encoding = read_text(ddb_path)

    thermo_text = thermo_text.replace("\r\n", "\n").replace("\r", "\n")
    ddb_text = ddb_text.replace("\r\n", "\n").replace("\r", "\n")

    elements = declared_elements(thermo_text)
    phases = declared_phases(thermo_text)
    functions = declared_functions(thermo_text)

    if not elements:
        raise RuntimeError("No active ELEMENT commands found in thermodynamic TDB")
    if not phases:
        raise RuntimeError("No active PHASE commands found in thermodynamic TDB")

    mobility_block, mobility_report = build_mobility_block(
        ddb_text,
        elements,
        phases,
        functions,
        ddb_path.name,
    )

    merged_text, inserted_before_references = insert_before_reference_list(
        thermo_text,
        mobility_block,
    )

    merged_text = (
        merged_text.rstrip()
        + "\n\n"
        + comment_archive(ddb_text, ddb_path.name)
        + "\n"
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(merged_text, encoding="utf-8", newline="\n")

    report: dict[str, object] = {
        "thermodynamic_source": str(thermo_path.resolve()),
        "mobility_source": str(ddb_path.resolve()),
        "destination": str(destination.resolve()),
        "thermodynamic_source_encoding": thermo_encoding,
        "mobility_source_encoding": ddb_encoding,
        "thermodynamic_source_sha256": sha256(thermo_path),
        "mobility_source_sha256": sha256(ddb_path),
        "destination_sha256": sha256(destination),
        "thermodynamic_elements": sorted(elements),
        "thermodynamic_phase_count": len(phases),
        "mobility_block_inserted_before_list_of_references": (
            inserted_before_references
        ),
        "mobility": mobility_report,
    }

    report_path = destination.with_suffix(destination.suffix + ".json")
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    report["report_path"] = str(report_path.resolve())
    return report


def validate_with_pycalphad(
    destination: Path,
    expected_mobility_parameter_count: int,
) -> dict[str, object]:
    try:
        import pycalphad
        from pycalphad import Database
    except ImportError as exc:
        raise RuntimeError(
            "--validate requires pycalphad in the active Python environment"
        ) from exc

    db = Database(str(destination))
    all_parameters = db._parameters.all()  # audit only; TinyDB public data store
    kinetic_parameters = [
        parameter
        for parameter in all_parameters
        if parameter.get("parameter_type") in KINETIC_PARAMETER_TYPES
    ]

    by_type = Counter(
        parameter.get("parameter_type") for parameter in kinetic_parameters
    )
    by_phase = Counter(
        parameter.get("phase_name") for parameter in kinetic_parameters
    )
    diffusing_species = sorted(
        {
            getattr(parameter.get("diffusing_species"), "name", "")
            for parameter in kinetic_parameters
        }
        - {"", None}
    )

    if len(kinetic_parameters) != expected_mobility_parameter_count:
        raise RuntimeError(
            "Merged database loaded, but the number of kinetic parameters "
            f"is {len(kinetic_parameters)} instead of the expected "
            f"{expected_mobility_parameter_count}."
        )

    return {
        "pycalphad_version": pycalphad.__version__,
        "elements": sorted(db.elements),
        "phase_count": len(db.phases),
        "kinetic_parameter_count": len(kinetic_parameters),
        "kinetic_parameters_by_type": dict(sorted(by_type.items())),
        "kinetic_parameters_by_phase": dict(sorted(by_phase.items())),
        "diffusing_species": diffusing_species,
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge a MatCalc diffusion DDB into a pycalphad-compatible "
            "GarCalc thermodynamic TDB."
        )
    )
    parser.add_argument("thermodynamic_tdb", type=Path)
    parser.add_argument("mobility_ddb", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Load the merged database with pycalphad and audit MQ/MF/DQ/DF.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)

    thermo_path = args.thermodynamic_tdb.expanduser().resolve()
    ddb_path = args.mobility_ddb.expanduser().resolve()
    destination = args.destination.expanduser().resolve()

    for path, label in (
        (thermo_path, "thermodynamic TDB"),
        (ddb_path, "mobility DDB"),
    ):
        if not path.is_file():
            print(f"ERROR: {label} does not exist: {path}", file=sys.stderr)
            return 2

    if destination in {thermo_path, ddb_path}:
        print(
            "ERROR: destination must differ from both source files.",
            file=sys.stderr,
        )
        return 2

    try:
        report = merge(thermo_path, ddb_path, destination)
    except Exception:
        print("MERGE FAILED", file=sys.stderr)
        traceback.print_exc()
        return 1

    mobility = report["mobility"]
    assert isinstance(mobility, dict)

    print("MOBILITY MERGE COMPLETED")
    print(f"Thermodynamic TDB: {thermo_path}")
    print(f"Mobility DDB:      {ddb_path}")
    print(f"Destination:       {destination}")
    print(f"Report:            {report['report_path']}")
    print()
    print("Mobility import summary:")
    print(json.dumps(mobility, indent=2, ensure_ascii=False))

    if args.validate:
        try:
            validation = validate_with_pycalphad(
                destination,
                int(mobility["retained_mobility_parameters"]),
            )
        except Exception:
            print("\n=== PYCALPHAD VALIDATION FAILED ===", file=sys.stderr)
            traceback.print_exc()
            return 1

        print("\n=== PYCALPHAD MOBILITY VALIDATION ===")
        print("DATABASE LOADED SUCCESSFULLY")
        print(json.dumps(validation, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
