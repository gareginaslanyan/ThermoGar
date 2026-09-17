"""15-Ш, п. 1: аудит element_density по всем элементам трёх баз.

    python audit_elements.py <корень снимка> <файл вывода .tsv>

Для каждого элемента: что возвращает element_density(X, 1073.15 K); какой
DP-параметр PDB дал это значение (прежний перебор FCC_A1, BCC_A2, HCP_A3,
LIQUID — трассировка той же логикой выбора кандидата); что вообще есть в PDB
для элемента: функции D0*/DT*, DP с элементом единственной составляющей
первой подрешётки. Поправки проекта выключены (чистая база).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(root / "app"))

import thermogar_physical as physical  # noqa: E402

T = 1073.15
PDB = root / "databases/physical/original/physical_data_v103.pdb"
db = physical.PhysicalDensityDatabase(PDB, overrides=None)

TDBS = {
    "ni": root / "databases/converted/mc_ni_v2036.garcalc.tdb",
    "al": root / "databases/converted/al/mc_al_v2037.thermogar.tdb",
    "fe": root / "databases/converted/fe/mc_fe_v2062.thermogar.tdb",
}
members: dict[str, list[str]] = {}
for key, path in TDBS.items():
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].upper() == "ELEMENT":
            name = parts[1].upper()
            if name not in {"VA", "/-"}:
                members.setdefault(name, []).append(key)
counts = {key: sum(key in v for v in members.values()) for key in TDBS}


def selected_parameter(phase, endmember):
    """Тот же выбор, что в density_from_site_fractions, для одного конечного члена."""
    parameters = db.parameters_by_phase.get(phase, [])
    n = physical._phase_sublattice_count(phase, parameters)
    if len(endmember) != n:
        return None
    candidates = []
    pure = [p for p in parameters if not p.is_interaction]
    for index, parameter in enumerate(pure):
        pattern, default = physical._normalized_pattern(phase, parameter.constituent_array, n)
        if default:
            candidates.append((0, index, parameter))
            continue
        if pattern is None:
            continue
        if all(pattern[i][0] in {"*", endmember[i]} for i in range(n)):
            candidates.append((sum(pattern[i][0] != "*" for i in range(n)), index, parameter))
    if not candidates:
        return None
    return max(candidates, key=lambda c: (c[0], c[1]))[2]


def trace_old(element):
    """Прежний перебор element_density — какая фаза и какой параметр дали значение."""
    for phase in ("FCC_A1", "BCC_A2", "HCP_A3", "LIQUID"):
        if phase not in db.phases:
            continue
        for second in ({"VA": 1.0}, {element: 1.0}, {}):
            fractions = [{element: 1.0}] + ([second] if second else [])
            try:
                value, coverage, _ = db.density_from_site_fractions(phase, fractions, T)
            except Exception:
                continue
            if value is not None and coverage > 0.999 and value > 0.0:
                endmember = tuple(next(iter(s)) for s in fractions)
                return phase, endmember, selected_parameter(phase, endmember), value
    return None


def describe(parameter):
    array = ":".join(",".join(s) for s in parameter.constituent_array)
    return f"DP({parameter.phase},{array}) = {parameter.expression}"


def pdb_inventory(element):
    functions = sorted(
        name for name in db.functions
        if re.fullmatch(rf"D0[A-Z]+_{element}", name)
        or re.fullmatch(rf"DT{element}(FCC|BCC|HCP|LIQ|DIAM)", name)
    )
    own = []
    for parameter in db.parameters:
        if parameter.is_interaction:
            continue
        array = parameter.constituent_array
        if array[0] == (element,) and all(s in {("VA",), (element,)} for s in array[1:]):
            own.append(describe(parameter))
    return functions, own


def now_source(element):
    if not hasattr(db, "element_density_model"):
        return ""
    model = db.element_density_model(element, T)
    if model is None:
        return "нет в PDB"
    note = db.element_density_note(element, T) or ""
    return f"{model[1]} {model[2]}" + (f" | {note}" if note else "")


rows = []
for element in sorted(members):
    new_value = db.element_density(element, T)
    traced = trace_old(element)
    functions, own = pdb_inventory(element)
    if traced is None:
        source = "—"
        wildcard = None
    else:
        phase, endmember, parameter, _value = traced
        source = f"{phase} {':'.join(endmember)} <- {describe(parameter)}"
        wildcard = any(s == ("*",) for s in parameter.constituent_array)
    rows.append(
        [
            element,
            ",".join(members[element]),
            "" if new_value is None else repr(new_value),
            "" if traced is None else repr(traced[3]),
            source,
            " ".join(functions) or "—",
            " | ".join(own) or "—",
            "подмена (умолчание *)" if wildcard else ("верно" if traced else "нет значения"),
            now_source(element),
        ]
    )

header = [
    "element", "databases", "element_density_now", "old_trace_value",
    "old_source", "pdb_functions", "pdb_own_dp", "old_verdict", "now_source",
]
text = "\t".join(header) + "\n" + "\n".join("\t".join(r) for r in rows) + "\n"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(text.encode("utf-8"))
print("counts", counts, "union", len(members))
print(text)
