#!/usr/bin/env python3
"""22-В, шаг 4 а (BL-41): какие элементы баз ni, al, fe в каких прямых DP-моделях идут по умолчанию.

Для каждой базы: элементы (без VA) и составляющие фаз FCC_A1, BCC_A2, HCP_A3, LIQUID по
разобранной и починенной базе (как в tools/test_density.py: Database + repair_database). Для каждой
пары «фаза × элемент первой (замещающей) подрешётки» — какую запись PDB выберет
``PhysicalDensityDatabase.density_from_site_fractions`` для конечного члена X:VA (у LIQUID — X):
та же логика выбора кандидата (самая конкретная запись, при равенстве — последняя). Если
выбрана запись-умолчание (``DP(фаза,*)`` — в FCC/BCC нормализуется до *:VA, в LIQUID — глобальная),
элемент идёт «по умолчанию». Отдельно: есть ли атомная масса в ``_ATOMIC_MASSES`` (без неё
конечный член не покрыт) и какая своя модель плотности элемента есть в PDB
(``element_density_model``, 298,15 K и 1073,15 K). Для элементов второй подрешётки
(междоузлия) — какая запись выбирается для конечного члена <основа>:X.

Только разбор баз, расчёта равновесия нет. Пишет results/wave22_v/bl41/perechen.json и .md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "app"))
OUT = ROOT / "results" / "wave22_v" / "bl41"

import thermogar_database_repair as repair  # noqa: E402
import thermogar_physical as phys  # noqa: E402
from pycalphad import Database  # noqa: E402

PDB = ROOT / "databases/physical/original/physical_data_v103.pdb"
TDB = {
    "ni": ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
    "al": ROOT / "databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb",
    "fe": ROOT / "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb",
}
PHASES = ("FCC_A1", "BCC_A2", "HCP_A3", "LIQUID")
BASE = {"ni": "NI", "al": "AL", "fe": "FE"}


def selected(pdb: phys.PhysicalDensityDatabase, phase: str, endmember: tuple[str, ...]):
    """Запись PDB для конечного члена — та же логика, что в density_from_site_fractions."""
    parameters = pdb.parameters_by_phase.get(phase, [])
    n = phys._phase_sublattice_count(phase, parameters)
    if len(endmember) != n:
        return None, None, n
    pure = [p for p in parameters if not p.is_interaction]
    candidates = []
    for index, parameter in enumerate(pure):
        pattern, global_default = phys._normalized_pattern(phase, parameter.constituent_array, n)
        if global_default:
            candidates.append((0, index, parameter, True))
            continue
        if pattern is None:
            continue
        if all(pattern[i][0] in {"*", endmember[i]} for i in range(n)):
            specificity = sum(pattern[i][0] != "*" for i in range(n))
            is_default = any(pattern[i][0] == "*" for i in range(n))
            candidates.append((specificity, index, parameter, is_default))
    if not candidates:
        return None, None, n
    _s, _i, parameter, is_default = max(candidates, key=lambda c: (c[0], c[1]))
    return parameter, is_default, n


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pdb = phys.PhysicalDensityDatabase(PDB, overrides=None)
    rows = []
    for key, path in TDB.items():
        db = Database(str(path))
        repair.repair_database(db, database_label=path.name)
        elements = sorted(str(e) for e in db.elements if str(e) not in {"VA", "/-"})
        refphases = phys.element_reference_phases(db)
        for phase in PHASES:
            if phase not in db.phases:
                continue
            constituents = [sorted(str(s) for s in sub) for sub in db.phases[phase].constituents]
            for sub_index, sublattice in enumerate(constituents[:2]):
                for element in sublattice:
                    if element in {"VA", "/-"} or element not in elements:
                        continue
                    params = pdb.parameters_by_phase.get(phase, [])
                    n = phys._phase_sublattice_count(phase, params)
                    if phase == "LIQUID" or n == 1:
                        if sub_index > 0:
                            continue
                        endmember = (element,)
                        kind = "замещение"
                    elif sub_index == 0:
                        endmember = (element, "VA")
                        kind = "замещение"
                    else:
                        endmember = (BASE[key], element)
                        kind = "междоузлие"
                    parameter, is_default, _n = selected(pdb, phase, endmember)
                    own = pdb.element_density_model(element, 298.15, refphases.get(element))
                    own_hot = pdb.element_density_model(element, 1073.15, refphases.get(element))
                    rows.append({
                        "база": key, "фаза": phase, "элемент": element, "подрешётка": kind,
                        "конечный член": ":".join(endmember),
                        "запись PDB": parameter.raw_command.split("!")[0].strip() if parameter else None,
                        "по умолчанию": bool(is_default) if parameter else None,
                        "не покрыт": parameter is None,
                        "масса в _ATOMIC_MASSES": element in phys._ATOMIC_MASSES,
                        "своя модель элемента (298 K)": list(own) if own else None,
                        "своя модель элемента (1073 K)": list(own_hot) if own_hot else None,
                        "значение выбранной записи 298 K": (pdb.parameter_value(parameter, 298.15) if parameter else None),
                        "значение выбранной записи 1073 K": (pdb.parameter_value(parameter, 1073.15) if parameter else None),
                    })
    (OUT / "perechen.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), "utf-8")
    lines = ["| база | фаза | элемент | конечный член | запись PDB | ρ записи 298 / 1073 K | своя модель элемента (298 K) | масса |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["подрешётка"] != "замещение":
            continue
        if not (r["по умолчанию"] or r["не покрыт"] or not r["масса в _ATOMIC_MASSES"]):
            continue
        own = r["своя модель элемента (298 K)"]
        value = (f"{r['значение выбранной записи 298 K']:.0f} / {r['значение выбранной записи 1073 K']:.0f}"
                 if r["запись PDB"] else "—")
        lines.append(
            f"| {r['база']} | {r['фаза']} | {r['элемент']} | {r['конечный член']} | "
            f"{(r['запись PDB'] or 'нет').replace('PARAMETER ', '').replace('|', '/')} | {value} | "
            f"{(f'{own[0]:.0f} ({own[1]}, {own[2]})' if own else 'нет')} | "
            f"{'есть' if r['масса в _ATOMIC_MASSES'] else '**нет**'} |"
        )
    (OUT / "perechen.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))
    inter = [r for r in rows if r["подрешётка"] == "междоузлие"]
    print("\nмеждоузлия:")
    for r in inter:
        print(r["база"], r["фаза"], r["конечный член"], (r["запись PDB"] or "не покрыт")[:70])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
