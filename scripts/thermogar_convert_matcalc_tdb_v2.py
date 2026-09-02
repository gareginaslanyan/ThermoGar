"""Convert an open MatCalc thermodynamic TDB to a pycalphad/ThermoGar copy.

The source file is never modified. MatCalc-only commands are preserved as
comments, order/disorder links are translated to pycalphad TYPE_DEFINITION
syntax, malformed references are normalized, and a JSON conversion report is
written next to the converted database.

This script targets thermodynamic equilibrium use first. MatCalc HMVA and SE
metadata and ADD_COMPOSITION_SET commands are retained as comments for later
treatment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import traceback
from pathlib import Path

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
TYPE_CHARS = "XYZQUVJK"


def read_text(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"Could not decode {path}")


def comment_block(block: str, tag: str | None = None) -> str:
    result: list[str] = []
    if tag:
        result.append(f"$ THERMOGAR_DISABLED: {tag}")
    for line in block.splitlines():
        result.append(line if line.lstrip().startswith("$") else "$" + line)
    return "\n".join(result)


def sanitize_reference_key(raw: str) -> str:
    key = re.sub(r"\s+", "", raw.strip())
    key = re.sub(r"[^A-Za-z0-9_:+-]", "_", key)
    key = re.sub(r"_+", "_", key).strip("_")
    return key or "UNSPECIFIED"


def add_type_char_to_phase(
    text: str, phase_name: str, type_char: str
) -> tuple[str, int]:
    pattern = re.compile(
        rf"(?im)^(?P<prefix>[ \t]*PHASE[ \t]+{re.escape(phase_name)}[ \t]+)"
        rf"(?P<types>\S+)(?P<rest>[ \t]+.*)$"
    )
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        types = match.group("types")
        if type_char not in types:
            types += type_char
            count += 1
        return f"{match.group('prefix')}{types}{match.group('rest')}"

    return pattern.sub(repl, text, count=1), count


def insert_reference_list_marker(text: str) -> tuple[str, int]:
    if re.search(
        r"(?im)^(?![ \t]*\$)[ \t]*LIST[-_]OF[-_]REFERENCES?\b", text
    ):
        return text, 0

    lines = text.splitlines()
    section_idx = next(
        (
            i
            for i, line in enumerate(lines)
            if re.search(r"E\)\s*LIST\s+OF\s+REFERENCES", line, re.IGNORECASE)
        ),
        None,
    )
    if section_idx is None:
        return text, 0

    insert_idx = None
    for i in range(section_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("$"):
            continue
        insert_idx = i
        break

    if insert_idx is None:
        return text, 0

    lines[insert_idx:insert_idx] = ["LIST_OF_REFERENCES", "NUMBER SOURCE"]
    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(lines) + suffix, 1


def convert(source: Path, destination: Path) -> dict[str, object]:
    text, encoding = read_text(source)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    report: dict[str, object] = {
        "source": str(source),
        "destination": str(destination),
        "source_encoding": encoding,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest().upper(),
        "changes": {},
        "warnings": [],
    }
    changes = report["changes"]
    warnings = report["warnings"]
    assert isinstance(changes, dict)
    assert isinstance(warnings, list)

    # Preserve MatCalc phase descriptions and priority values as comments.
    phase_pattern = re.compile(
        r"(?ims)^([ \t]*PHASE[ \t]+[^\n!]*?)\s*>\s*(.*?)\s*>>\s*([0-9]+)\s*!"
    )

    def phase_repl(match: re.Match[str]) -> str:
        prefix = match.group(1).rstrip()
        description = " ".join(match.group(2).split())
        priority = match.group(3)
        metadata: list[str] = []
        if description:
            metadata.append(f"$ MATCALC_DESCRIPTION: {description}")
        metadata.append(f"$ MATCALC_PRIORITY: {priority}")
        metadata.append(prefix + " !")
        return "\n".join(metadata)

    text, count = phase_pattern.subn(phase_repl, text)
    changes["phase_descriptions_preserved_as_comments"] = count

    # Translate MatCalc order/disorder links.
    attach_pattern = re.compile(
        r"(?im)^[ \t]*ATTACH_CONTRIBUTION[ \t]+(?P<ordered>\S+)"
        r"[ \t]+(?P<disordered>\S+)[ \t]+ORDER_DISORDER[ \t]*!"
    )
    attach_matches = list(attach_pattern.finditer(text))
    used_type_chars = set(
        re.findall(r"(?im)^[ \t]*TYPE_DEFINITION[ \t]+([^\s!])", text)
    )
    available_chars = [char for char in TYPE_CHARS if char not in used_type_chars]
    pair_to_char: dict[tuple[str, str], str] = {}

    for match in attach_matches:
        pair = (
            match.group("ordered").upper(),
            match.group("disordered").upper(),
        )
        if pair not in pair_to_char:
            if not available_chars:
                raise RuntimeError("No free TYPE_DEFINITION character is available")
            pair_to_char[pair] = available_chars.pop(0)

    def attach_repl(match: re.Match[str]) -> str:
        ordered = match.group("ordered").upper()
        disordered = match.group("disordered").upper()
        type_char = pair_to_char[(ordered, disordered)]
        typedef = (
            f"TYPE_DEFINITION {type_char} GES AMEND_PHASE_DESCRIPTION "
            f"{ordered} DIS_PART {disordered} !"
        )
        return (
            comment_block(match.group(0), "MatCalc ATTACH_CONTRIBUTION")
            + "\n"
            + typedef
        )

    text, count = attach_pattern.subn(attach_repl, text)
    changes["attach_contribution_translated"] = count

    if attach_matches and not re.search(
        r"(?im)^[ \t]*TYPE_DEFINITION[ \t]+%[ \t]+SEQ[ \t]+\*[ \t]*!", text
    ):
        first_typedef = re.search(
            r"(?im)^[ \t]*TYPE_DEFINITION[ \t]+[XYZQUVJK][ \t]+GES"
            r"[ \t]+AMEND_PHASE_DESCRIPTION[^\n]*!",
            text,
        )
        if first_typedef:
            pos = first_typedef.end()
            text = text[:pos] + "\nTYPE_DEFINITION % SEQ * !" + text[pos:]
            changes["sequence_type_definition_added"] = 1
        else:
            changes["sequence_type_definition_added"] = 0
    else:
        changes["sequence_type_definition_added"] = 0

    phase_type_updates = 0
    for (ordered, disordered), type_char in pair_to_char.items():
        text, c1 = add_type_char_to_phase(text, ordered, type_char)
        text, c2 = add_type_char_to_phase(text, disordered, type_char)
        phase_type_updates += c1 + c2
        if c1 == 0:
            warnings.append(
                f"Ordered phase {ordered} was not found for type character {type_char}"
            )
        if c2 == 0:
            warnings.append(
                f"Disordered phase {disordered} was not found for type character {type_char}"
            )
    changes["phase_type_characters_added"] = phase_type_updates

    # Preserve unsupported MatCalc commands as comments.
    single_line_patterns = {
        "reference_element_disabled": re.compile(
            r"(?im)^[ \t]*REFERENCE_ELEMENT\b[^\n!]*!"
        ),
        "composition_sets_disabled": re.compile(
            r"(?im)^[ \t]*ADD_COMPOSITION_SET\b[^\n!]*!"
        ),
        "create_new_phase_disabled": re.compile(
            r"(?im)^[ \t]*CREATE_NEW_PHASE\b[^\n!]*!"
        ),
    }
    for key, pattern in single_line_patterns.items():
        text, count = pattern.subn(
            lambda match, key=key: comment_block(match.group(0), key), text
        )
        changes[key] = count

    hmva_pattern = re.compile(
        r"(?ims)^[ \t]*PARAMETER[ \t]+HMVA\s*\([^!]*?!"
    )
    text, count = hmva_pattern.subn(
        lambda match: comment_block(
            match.group(0), "unsupported HMVA parameter retained as comments"
        ),
        text,
    )
    changes["hmva_parameters_disabled"] = count

    se_pattern = re.compile(
        r"(?ims)^[ \t]*PARAMETER[ \t]+SE\s*\([^!]*?!"
    )
    text, count = se_pattern.subn(
        lambda match: comment_block(
            match.group(0),
            "unsupported MatCalc SE parameter retained as comments",
        ),
        text,
    )
    changes["se_parameters_disabled"] = count

    # Normalize malformed active-command syntax without touching comments.
    repaired_lines: list[str] = []
    repeated_decimal_count = 0
    reference_key_count = 0
    g_phase_separator_count = 0
    missing_terminal_bang_count = 0
    duplicated_temperature_token_count = 0
    duplicated_function_tail_count = 0
    mnb4_constituent_relic_count = 0
    create_new_phase_line_count = 0

    for line in text.splitlines():
        if line.lstrip().startswith("$"):
            repaired_lines.append(line)
            continue

        # MatCalc mc_fe_v2.062 contains a known one-character typo:
        # PARAMETER G(G_PHASE;...) must use a comma after the phase name
        # in standard TDB PARAMETER syntax.
        line, n = re.subn(
            r"(?i)PARAMETER\s+G\(G_PHASE\s*;",
            "PARAMETER G(G_PHASE,",
            line,
        )
        g_phase_separator_count += n

        # Known missing command terminator in mc_fe_v2.062.
        if re.search(
            r"(?i)^\s*PARAMETER\s+L\(LAVES_PHASE,MN,TI:NI;0\)"
            r"\s+273\.00\s+\+70000;\s*6000\.00\s+N\s*$",
            line,
        ):
            line = line.rstrip() + " !"
            missing_terminal_bang_count += 1

        # Known duplicated tokens in the PDMN_B2 expression.
        line, n = re.subn(r"\b273\.00\s+273\b", "273.00", line)
        duplicated_temperature_token_count += n

        line, n = re.subn(
            r";\s*6000\.00\s+N\s*;\s*6000\.00\s+N\b",
            "; 6000.00 N",
            line,
        )
        duplicated_function_tail_count += n

        # Remove a MatCalc phase-description relic from a CONSTITUENT line.
        if re.search(r"(?i)^\s*CONSTITUENT\s+MNB4\b", line):
            line, n = re.subn(r"\s*>\s*>>\s*1\s*!", " !", line)
            mnb4_constituent_relic_count += n

        # Be defensive if CREATE_NEW_PHASE appears without a terminal bang.
        if re.match(r"(?i)^\s*CREATE_NEW_PHASE\b", line):
            repaired_lines.append(
                "$ THERMOGAR_DISABLED: unsupported CREATE_NEW_PHASE command"
            )
            repaired_lines.append("$" + line)
            create_new_phase_line_count += 1
            continue

        line, n = re.subn(
            r"\b(\d+\.\d+)\.\d+([ \t]+[NYny]\b)", r"\1\2", line
        )
        repeated_decimal_count += n

        def ref_repl(match: re.Match[str]) -> str:
            nonlocal reference_key_count
            raw_key = match.group(1)
            clean_key = sanitize_reference_key(raw_key)
            if clean_key != raw_key.strip() or re.match(
                r"(?i)^REF\s+", match.group(0)
            ):
                reference_key_count += 1
            return f"REF:{clean_key} !"

        line = re.sub(
            r"(?i)\bREF\s*:?[ \t]*([^!\r\n]+?)[ \t]*!", ref_repl, line
        )
        repaired_lines.append(line)

    suffix = "\n" if text.endswith("\n") else ""
    text = "\n".join(repaired_lines) + suffix
    changes["duplicated_decimal_temperatures_repaired"] = repeated_decimal_count
    changes["reference_keys_normalized"] = reference_key_count
    changes["g_phase_parameter_separator_repaired"] = g_phase_separator_count
    changes["missing_terminal_bangs_repaired"] = missing_terminal_bang_count
    changes["duplicated_temperature_tokens_repaired"] = (
        duplicated_temperature_token_count
    )
    changes["duplicated_function_tails_repaired"] = duplicated_function_tail_count
    changes["mnb4_constituent_relics_repaired"] = mnb4_constituent_relic_count
    changes["create_new_phase_lines_disabled"] = create_new_phase_line_count

    # Shield the free-form bibliography from the command parser.
    text, count = insert_reference_list_marker(text)
    changes["reference_list_marker_added"] = count

    header = (
        "$ THERMOGAR_CONVERSION\n"
        "$ Source file is preserved separately and remains authoritative.\n"
        "$ MatCalc-only metadata disabled below is retained as comments.\n"
        "$ Conversion target: pycalphad-compatible thermodynamic TDB.\n"
    )
    text = header + text.lstrip("\ufeff")

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8", newline="\n")
    report["destination_sha256"] = hashlib.sha256(
        destination.read_bytes()
    ).hexdigest().upper()
    report["destination_size"] = destination.stat().st_size
    report["order_disorder_pairs"] = [
        {"ordered": ordered, "disordered": disordered, "type_char": type_char}
        for (ordered, disordered), type_char in pair_to_char.items()
    ]
    return report


def validate_database(path: Path, report: dict[str, object]) -> bool:
    try:
        import pycalphad
        from pycalphad import Database
    except ImportError:
        print("VALIDATION SKIPPED: pycalphad is not installed in this Python environment")
        return False

    print("\n=== PYCALPHAD VALIDATION ===")
    print(f"pycalphad: {pycalphad.__version__}")
    print(f"database:  {path}")

    try:
        db = Database(str(path))
    except Exception:
        print("DATABASE LOAD FAILED")
        traceback.print_exc()
        return False

    print("DATABASE LOADED SUCCESSFULLY")
    print(f"Elements: {sorted(db.elements)}")
    print(f"Number of phases: {len(db.phases)}")

    pairs = report.get("order_disorder_pairs", [])
    if isinstance(pairs, list):
        for pair in pairs:
            if not isinstance(pair, dict):
                continue
            ordered = str(pair.get("ordered", ""))
            disordered = str(pair.get("disordered", ""))
            if ordered in db.phases:
                print(f"{ordered} model_hints: {db.phases[ordered].model_hints}")
            if disordered in db.phases:
                print(f"{disordered} model_hints: {db.phases[disordered].model_hints}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert an open MatCalc TDB for pycalphad/ThermoGar"
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Load the converted TDB with the active pycalphad installation",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    destination = args.destination.resolve()
    if not source.is_file():
        parser.error(f"Source file does not exist: {source}")
    if source == destination:
        parser.error("Source and destination must be different files")

    report = convert(source, destination)
    report_path = (
        args.report.resolve()
        if args.report
        else destination.with_suffix(destination.suffix + ".json")
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("CONVERSION COMPLETED")
    print(f"Source:      {source}")
    print(f"Destination: {destination}")
    print(f"Report:      {report_path}")
    print("Changes:")
    print(json.dumps(report["changes"], indent=2))

    warnings = report.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        print("WARNINGS:")
        for warning in warnings:
            print(f"- {warning}")

    if args.validate and not validate_database(destination, report):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
