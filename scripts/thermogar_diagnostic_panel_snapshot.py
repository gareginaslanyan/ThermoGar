"""Render the steel diagnostic panel as it looks in the installed configuration.

The installed payload carries ``databases/converted`` and
``databases/physical`` only: ``databases/diagnostic/fe`` is excluded as a second
full-size ODbL derivative, and the reference fingerprint is shipped in its
place.  To show the panel the way a user sees it, this script mirrors that
layout into a staging directory, asks the guard for the panel table, and writes
the table out as text and as a PNG.

No equilibrium is computed. The guard imports pycalphad, but only TDB text
parsing and SHA-256 digests are exercised.

Usage
-----
    python scripts/thermogar_diagnostic_panel_snapshot.py --out-dir build/snapshot
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import sys
from typing import Iterable

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "app"))

# Directory names the payload allowlist never stages, with the one documented
# exception; see packaging/stage_payload.ps1.
DENIED_DIR_NAMES = ("__pycache__", ".git", "original", "diagnostic", "experimental")
DENIED_DIR_EXCEPTIONS = (("databases", "physical", "original"),)
STAGED_TREES = (("databases", "converted"), ("databases", "physical"))


def is_denied(relative: pathlib.PurePath) -> bool:
    parts = relative.parts
    for index, part in enumerate(parts[:-1]):
        if part in DENIED_DIR_NAMES and parts[: index + 1] not in DENIED_DIR_EXCEPTIONS:
            return True
    return False


def stage_installed_configuration(destination: pathlib.Path) -> int:
    """Copy the database trees the installer actually ships."""
    if destination.exists():
        shutil.rmtree(destination)
    staged = 0
    for tree in STAGED_TREES:
        source = ROOT.joinpath(*tree)
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if is_denied(relative):
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            staged += 1
    return staged


def wrap(text: object, width: int) -> str:
    words: list[str] = []
    for token in str(text).split():
        # Paths carry no spaces; break them so the cell never runs off the page.
        while len(token) > width:
            words.append(token[:width])
            token = token[width:]
        words.append(token)
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return "\n".join(lines)


def render_png(frame, path: pathlib.Path, subtitle: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cells = [
        [wrap(row["Поле"], 42), wrap(row["Значение"], 62)]
        for _, row in frame.iterrows()
    ]
    heights = [
        max(cell[0].count("\n"), cell[1].count("\n")) + 1 for cell in cells
    ]
    total = 0.30 * sum(heights) + 1.2
    figure, axes = plt.subplots(figsize=(14, total))
    axes.axis("off")
    axes.set_title(
        "ThermoGar — панель диагностики стальной базы\n" + subtitle,
        fontsize=11,
        loc="left",
        pad=14,
    )
    table = axes.table(
        cellText=cells,
        colLabels=["Поле", "Значение"],
        loc="upper left",
        cellLoc="left",
        colWidths=[0.34, 0.66],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    for (row, _column), cell in table.get_celld().items():
        cell.set_edgecolor("#c8ccd0")
        if row == 0:
            cell.set_facecolor("#e8eaed")
            cell.set_text_props(weight="bold")
            cell.set_height(2 * 0.30 / total)
        else:
            cell.set_height(heights[row - 1] * 0.30 / total)
            if row % 2 == 0:
                cell.set_facecolor("#f7f8f9")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        required=True,
        help="directory for the staged databases and the rendered snapshot",
    )
    parser.add_argument(
        "--name",
        default="WAVE11G_diagnostic_panel_installed",
        help="base name for the .png and .txt outputs",
    )
    args = parser.parse_args(argv)

    out_dir = pathlib.Path(args.out_dir).resolve()
    staging = out_dir / "ThermoGar-installed-configuration"
    staged = stage_installed_configuration(staging)

    import thermogar_database_guard as guard

    frame = guard.passport_dataframe(staging, guard.FE_PROFILE_WORKING)

    lines = [f"{row['Поле']} | {row['Значение']}" for _, row in frame.iterrows()]
    text_path = out_dir / f"{args.name}.txt"
    text_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    diagnostic_present = (staging / "databases" / "diagnostic").exists()
    fingerprint_present = (
        staging / guard.UPSTREAM_FINGERPRINT_RELATIVE_PATH
    ).is_file()
    subtitle = (
        f"databases/diagnostic/fe "
        f"{'присутствует' if diagnostic_present else 'отсутствует'}, "
        f"отпечаток эталона "
        f"{'поставлен' if fingerprint_present else 'отсутствует'}"
    )
    png_path = out_dir / f"{args.name}.png"
    render_png(frame, png_path, subtitle)

    print(f"staged files: {staged}")
    print(f"text: {text_path}")
    print(f"png:  {png_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
