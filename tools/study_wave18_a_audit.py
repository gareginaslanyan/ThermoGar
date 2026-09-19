#!/usr/bin/env python3
"""18-А (BL-47): аудит плотности элементов трёх баз при 298,15 K.

Для каждого элемента записей ELEMENT трёх баз (Ni, Al, Fe) печатает эталонную
фазу из TDB и модель PDB, по которой правило смеси берёт плотность элемента:
«до» — прежний порядок фаз (эталонная фаза не передаётся), «после» — с
эталонной фазой элемента. Поправки PDB выключены (чистая база).

Запуск:
    .venv-windows/Scripts/python.exe -X utf8 tools/study_wave18_a_audit.py [out.md]
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from pycalphad import Database  # noqa: E402

from thermogar_physical import PhysicalDensityDatabase  # noqa: E402

PDB_PATH = ROOT / "databases/physical/original/physical_data_v103.pdb"
TDBS = {
    "Ni": ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
    "Al": ROOT / "databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb",
    "Fe": ROOT / "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb",
}
T = 298.15


def _fmt(model) -> tuple[str, str]:
    if model is None:
        return "нет", "—"
    value, kind, label = model
    return f"{label} ({kind})", f"{value:.2f}"


def main() -> int:
    pdb = PhysicalDensityDatabase(PDB_PATH, overrides=None)
    has_reference = "reference_phase" in inspect.signature(
        pdb.element_density_model
    ).parameters
    rows: dict[str, dict] = {}
    for label, path in TDBS.items():
        database = Database(str(path))
        for element, record in sorted(database.refstates.items()):
            if element in {"VA", "/-"}:
                continue
            row = rows.setdefault(
                element, {"bases": [], "phase": str(record.get("phase", ""))}
            )
            row["bases"].append(label)
            phase = str(record.get("phase", ""))
            if phase != row["phase"]:
                row["phase"] += f" / {label}: {phase}"
    lines = [
        "| Элемент | Базы | Эталонная фаза TDB | Запись PDB до | Запись PDB после "
        "| ρ(298,15) до, кг/м³ | ρ(298,15) после, кг/м³ | Сдвиг |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for element, row in sorted(rows.items()):
        before = pdb.element_density_model(element, T)
        if has_reference:
            reference = row["phase"].split(" / ")[0]
            after = pdb.element_density_model(element, T, reference_phase=reference)
        else:
            after = before
        b_label, b_value = _fmt(before)
        a_label, a_value = _fmt(after)
        changed = "да" if (before and after and before[0] != after[0]) or (
            (before is None) != (after is None)
        ) or b_label != a_label else "нет"
        lines.append(
            f"| {element} | {', '.join(row['bases'])} | {row['phase']} | {b_label} "
            f"| {a_label} | {b_value} | {a_value} | {changed} |"
        )
    text = "\n".join(lines) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
