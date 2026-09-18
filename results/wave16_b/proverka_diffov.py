"""Summarise the wave 16-B conversion diffs (diff_*.patch in this folder).

Usage: python proverka_diffov.py [patch ...]

Each patch is a unified diff between two TDB files after normalisation
(CRLF -> LF, source encoding -> UTF-8). Every contiguous run of removed/added
lines is sorted into one kind:

* comment_only       - only comment ($) or blank lines were added or removed;
* disabled_commands  - active lines were removed and reappear verbatim as
                       comments, nothing active was added;
* syntax             - active lines were rewritten or added.

Independently, every run is checked for numeric tokens: a token that leaves
the active text and does not reappear either in the new active text or in
the added comments, or a token that appears in the new active text without
being in the removed one, is listed with its place. Nothing is interpreted:
the listing is what the master reviews.

Only the standard library is used; no database is loaded.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

TOKEN = re.compile(
    r"(?<![A-Za-z_\d:])[\d.]*\d[\d.]*(?:[eE][-+]?\d+)?(?![A-Za-z_\d])"
)


def is_comment(line: str) -> bool:
    stripped = line.lstrip()
    return stripped == "" or stripped.startswith("$")


def runs(path: Path):
    """Yield (old_line, new_line, removed, added) for each change run."""
    old = new = 0
    removed: list[str] = []
    added: list[str] = []
    start = (0, 0)
    for raw in path.read_text(encoding="utf-8").split("\n"):
        if raw.startswith("--- ") or raw.startswith("+++ "):
            continue
        if raw.startswith("@@"):
            if removed or added:
                yield (*start, removed, added)
                removed, added = [], []
            match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", raw)
            old, new = int(match.group(1)), int(match.group(2))
            continue
        tag, body = raw[:1], raw[1:]
        if tag == "-":
            if not removed and not added:
                start = (old, new)
            removed.append(body)
            old += 1
        elif tag == "+":
            if not removed and not added:
                start = (old, new)
            added.append(body)
            new += 1
        elif tag == " ":
            if removed or added:
                yield (*start, removed, added)
                removed, added = [], []
            old += 1
            new += 1
    if removed or added:
        yield (*start, removed, added)


def tokens(lines):
    return Counter(t for line in lines for t in TOKEN.findall(line))


def summarise(path: Path) -> dict:
    kinds = Counter()
    lines = Counter()
    numeric = []
    for old, new, removed, added in runs(path):
        lines["added"] += len(added)
        lines["removed"] += len(removed)
        lines["changed"] += min(len(removed), len(added))
        removed_active = [l for l in removed if not is_comment(l)]
        added_active = [l for l in added if not is_comment(l)]
        added_comment = [l.lstrip()[1:] for l in added if is_comment(l)]
        pool = Counter(added_comment)
        pool.update(c[1:] for c in added_comment if c.startswith(" "))
        still_active = []
        disabled = 0
        for line in removed_active:
            if pool[line] > 0:
                pool[line] -= 1
                disabled += 1
            else:
                still_active.append(line)
        if not removed_active and not added_active:
            kind = "comment_only"
        elif not added_active and not still_active:
            kind = "disabled_commands"
        else:
            kind = "syntax"
        kinds[kind] += 1
        lines[f"{kind}_removed"] += len(removed)
        lines[f"{kind}_added"] += len(added)
        lines["disabled_active_lines"] += disabled
        if removed:  # pure insertions (mobility layer) carry new data by design
            lost = tokens(still_active) - tokens(added_active) - tokens(added_comment)
            new_tokens = tokens(added_active) - tokens(still_active)
            if lost or new_tokens:
                numeric.append((old, new, still_active, added_active,
                                dict(lost), dict(new_tokens)))
    return {"kinds": kinds, "lines": lines, "numeric": numeric}


def main(argv: list[str]) -> int:
    here = Path(__file__).resolve().parent
    paths = [Path(p) for p in argv] or sorted(here.glob("diff_*.patch"))
    for path in paths:
        result = summarise(path)
        lines, kinds = result["lines"], result["kinds"]
        print(f"== {path.name}")
        print(f"  lines: +{lines['added']} -{lines['removed']} "
              f"changed(min per run) {lines['changed']}")
        for kind in ("comment_only", "disabled_commands", "syntax"):
            print(f"  {kind}: runs {kinds[kind]}, "
                  f"-{lines[kind + '_removed']} +{lines[kind + '_added']}")
        print(f"  active lines disabled (kept verbatim as comments): "
              f"{lines['disabled_active_lines']}")
        print(f"  runs with numeric-token differences: {len(result['numeric'])}")
        for old, new, rem, add, lost, new_tokens in result["numeric"]:
            print(f"    old line {old} / new line {new}: "
                  f"removed {lost} added {new_tokens}")
            for line in rem:
                print(f"      - {line.strip()}")
            for line in add:
                print(f"      + {line.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
