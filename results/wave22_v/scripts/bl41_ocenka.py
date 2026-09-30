#!/usr/bin/env python3
"""22-В, шаг 4 б (BL-41): величина ошибки плотности сплава от умолчания DP(фаза,*) для добавки.

Для состава и температуры: равновесие pycalphad (как tools/test_density.py: разобранная и починенная
база, все фазы базы для этих компонентов, drop_broken_order_disorder, pdens 100) и плотность сплава
``thermogar_physical.calculate_physical_properties`` — четыре раза на одном и том же равновесии:

* «программа» — PDB как есть (поправки вкл. и выкл.);
* «своя модель» — та же PDB, в которую (только в этом процессе) добавлена запись DP(фаза,X:VA)
  (у LIQUID — DP(LIQUID,X)) для добавки X во всех прямых моделях, где X шла по умолчанию.
  Выражение — собственная модель плотности X в той же PDB (``element_density_model``: своя запись
  в другой фазе либо D0-функция), а если её нет — справочная плотность при 20…25 °C (константа,
  без расширения; источник — ниже). Правило Вегарда только для этой добавки; остальные элементы
  и все прочие записи — как в программе.

У Sc нет массы в ``_ATOMIC_MASSES``: в варианте «своя модель» масса Sc добавляется (по refstates
базы), иначе конечный член Sc не покрыт.

Справочные плотности (нет ни записи, ни D0 в PDB): Hf 13 310 кг/м³, Y 4 472 кг/м³ — CRC Handbook of
Chemistry and Physics, таблица «Physical Properties of the Elements» (20…25 °C); в этой сессии с
печатным источником не сверены.

    PYTHONHASHSEED=0 python -B bl41_ocenka.py --db ni --x ZR --wt 0.1 0.5 1 2 --T 25 800 1000
    PYTHONHASHSEED=0 python -B bl41_ocenka.py --db ni --name IN738_bez_Ta --comp "AL=3.4,B=0.01,..." --T 25 800 1000
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "app"))
OUT = ROOT / "results" / "wave22_v" / "bl41"

import numpy as np  # noqa: E402
import thermogar_database_repair as repair  # noqa: E402
import thermogar_physical as phys  # noqa: E402
from pycalphad import Database, equilibrium, variables as v  # noqa: E402
from pycalphad.core.utils import filter_phases, unpack_species  # noqa: E402

PDB = ROOT / "databases/physical/original/physical_data_v103.pdb"
TDB = {
    "ni": ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
    "al": ROOT / "databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb",
    "fe": ROOT / "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb",
}
BASE = {"ni": "NI", "al": "AL", "fe": "FE"}
DIRECT = ("FCC_A1", "BCC_A2", "HCP_A3", "LIQUID")
HANDBOOK = {"HF": 13310.0, "Y": 4472.0}
SC_MASS_FALLBACK = 44.955908


def own_expression(pdb: phys.PhysicalDensityDatabase, element: str, reference: str | None) -> tuple[str, str]:
    model = pdb.element_density_model(element, 298.15, reference)
    if model is None:
        if element in HANDBOOK:
            return f"{HANDBOOK[element]:.1f}", "справочник (CRC), 20…25 °C, константа"
        raise KeyError(element)
    _value, kind, label = model
    if label.startswith("DP("):
        phase = label[3:label.index(",")]
        array = label[label.index(",") + 1:-1]
        for parameter in pdb.parameters_by_phase.get(phase, []):
            text = ":".join(",".join(g) for g in parameter.constituent_array)
            if text == array and not parameter.is_interaction:
                return parameter.expression, f"{label} ({kind})"
        raise KeyError(label)
    return label, f"{label} ({kind}, D0 при 298,15 K{' + DT' if '+' in label else ', без расширения'})"


def default_phases(pdb: phys.PhysicalDensityDatabase, element: str) -> list[str]:
    import bl41_perechen as per

    found = []
    for phase in DIRECT:
        params = pdb.parameters_by_phase.get(phase, [])
        if not params:
            continue
        n = phys._phase_sublattice_count(phase, params)
        endmember = (element,) if n == 1 else (element, "VA")
        parameter, is_default, _ = per.selected(pdb, phase, endmember)
        if parameter is not None and is_default:
            found.append(phase)
    return found


def corrected_pdb(pdb: phys.PhysicalDensityDatabase, element: str, expression: str) -> phys.PhysicalDensityDatabase:
    fixed = copy.deepcopy(pdb)
    for phase in default_phases(pdb, element):
        params = fixed.parameters_by_phase[phase]
        n = phys._phase_sublattice_count(phase, params)
        array = ((element,),) if n == 1 else ((element,), ("VA",))
        fixed.parameters_by_phase[phase].append(phys.DensityParameter(
            phase=phase, constituent_array=array, order=0, lower_temperature=298.15,
            expression=expression, upper_temperature=6000.0,
            raw_command=f"22V: DP({phase},{element}{':VA' if n > 1 else ''}) = {expression}",
        ))
    return fixed


def mole_fractions(db, wt: dict[str, float], base: str) -> dict[str, float]:
    masses = {el: float(db.refstates[el]["mass"]) for el in [*wt, base]}
    w = dict(wt)
    w[base] = 100.0 - sum(wt.values())
    moles = {el: w[el] / masses[el] for el in w}
    total = sum(moles.values())
    return {el: moles[el] / total for el in wt}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, choices=sorted(TDB))
    parser.add_argument("--x", help="добавка модельного ряда")
    parser.add_argument("--wt", type=float, nargs="*", default=[0.1, 0.5, 1.0, 2.0])
    parser.add_argument("--name", help="имя состава проекта")
    parser.add_argument("--comp", help="состав проекта, масс. %: EL=значение,…")
    parser.add_argument("--solutes", help="добавки, для которых оценивается умолчание (для состава проекта)")
    parser.add_argument("--T", type=float, nargs="+", default=[25.0, 800.0, 1000.0])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    base = BASE[args.db]
    db0 = Database(str(TDB[args.db]))
    repair.repair_database(db0, database_label=TDB[args.db].name)
    refphases = phys.element_reference_phases(db0)
    pdb_on = phys.PhysicalDensityDatabase(PDB)
    pdb_off = phys.PhysicalDensityDatabase(PDB, overrides=None)

    if args.name:
        cases = [(args.name, {k.strip().upper(): float(val) for k, val in (p.split("=") for p in args.comp.split(","))})]
        targets = [s.strip().upper() for s in args.solutes.split(",")]
    else:
        cases = [(f"{base}-{wt:g}{args.x}", {args.x.upper(): wt}) for wt in args.wt]
        targets = [args.x.upper()]

    fixes_on, fixes_off, sources = pdb_on, pdb_off, {}
    for x in targets:
        expression, source = own_expression(pdb_off, x, refphases.get(x))
        sources[x] = {"выражение": expression, "источник": source, "фазы умолчания": default_phases(pdb_off, x)}
        fixes_on = corrected_pdb(fixes_on, x, expression)
        fixes_off = corrected_pdb(fixes_off, x, expression)

    rows = []
    for name, wt in cases:
        x = mole_fractions(db0, wt, base)
        components = [base, *sorted(wt), "VA"]
        elements = [c for c in components if c != "VA"]
        db = copy.deepcopy(db0)
        db.phases = copy.deepcopy(db0.phases)
        db.symbols = copy.deepcopy(db0.symbols)
        db.species = copy.deepcopy(db0.species)
        phases = filter_phases(db, unpack_species(db, components))
        phases, _removed = repair.drop_broken_order_disorder(db, components, phases)
        for t_c in args.T:
            T = t_c + 273.15
            started = time.perf_counter()
            conditions = {v.N: 1.0, v.P: 101325.0, v.T: T}
            conditions.update({v.X(el): val for el, val in sorted(x.items())})
            eq = equilibrium(db, components, phases, conditions, calc_opts={"pdens": 100})
            solve_s = time.perf_counter() - started
            names = np.asarray(eq.Phase.values, dtype=str).ravel()
            amounts = np.asarray(eq.NP.values, dtype=float).ravel()
            present = {}
            for ph, amount in zip(names, amounts):
                if ph and np.isfinite(amount) and amount > 1e-8:
                    present[ph] = present.get(ph, 0.0) + float(amount)
            result = {}
            for label, pdb in (("прог_вкл", pdb_on), ("прог_выкл", pdb_off), ("своя_вкл", fixes_on), ("своя_выкл", fixes_off)):
                added_sc = False
                if label.startswith("своя") and "SC" in targets and "SC" not in phys._ATOMIC_MASSES:
                    phys._ATOMIC_MASSES["SC"] = float(db0.refstates.get("SC", {}).get("mass", SC_MASS_FALLBACK))
                    added_sc = True
                try:
                    res = phys.calculate_physical_properties(db, eq, elements, T, pdb)
                    result[label] = (res.alloy_density_kg_m3, res.quality_label, res.mass_coverage_pct, res.estimated_mole_pct,
                                     res.phase_table.to_dict("records"))
                finally:
                    if added_sc:
                        phys._ATOMIC_MASSES.pop("SC", None)
            row = {
                "база": args.db, "состав": name, "масс. %": wt, "мольн. доли": x, "T, °C": t_c,
                "фазы (мольн.)": {k: round(val, 6) for k, val in sorted(present.items())},
                "равновесие, с": round(solve_s, 2),
            }
            for label, (rho, quality, cov, est, table) in result.items():
                row[f"ρ {label}, кг/м³"] = rho
                row[f"качество {label}"] = quality
                row[f"покрытие по массе {label}, %"] = cov
            for mode in ("вкл", "выкл"):
                a, b = row[f"ρ прог_{mode}, кг/м³"], row[f"ρ своя_{mode}, кг/м³"]
                row[f"Δ {mode}, кг/м³ (прог − своя)"] = (a - b) if a is not None and b is not None else None
                row[f"Δ {mode}, %"] = (100 * (a - b) / b) if a is not None and b else None
            # сколько добавки сидит в прямых моделях, где она шла по умолчанию
            # модель плотности каждой фазы — как её выбирает программа (resolve_phase): прямая, унаследованная
            # (например BCC_B2 → BCC_A2, GAMMA_PRIME → FCC_A1) или оценка правилом смеси
            models = {}
            for ph in present:
                res_ph = pdb_on.resolve_phase(db, ph)
                models[ph] = f"{res_ph.physical_phase or '—'} ({res_ph.quality})"
            row["модель плотности фаз"] = models
            in_direct = 0.0
            xs_by_el = {el: np.asarray(eq.X.sel(component=el).values, dtype=float).ravel() for el in targets}
            for i, (ph, amount) in enumerate(zip(names, amounts)):
                if not ph or not np.isfinite(amount) or amount <= 1e-8:
                    continue
                phys_phase = pdb_on.resolve_phase(db, ph).physical_phase
                if phys_phase in DIRECT:
                    in_direct += float(amount) * sum(float(xs_by_el[el][i]) for el in targets)
            row["добавка в прямых моделях, мольн. доля сплава"] = in_direct
            rows.append(row)
            print(json.dumps({k: row[k] for k in ("состав", "T, °C", "фазы (мольн.)", "ρ прог_вкл, кг/м³", "ρ своя_вкл, кг/м³", "Δ вкл, %", "Δ выкл, %")}, ensure_ascii=False), flush=True)
    stem = args.name or f"{args.db}_{args.x}"
    (OUT / f"ocenka_{stem}.json").write_text(json.dumps({"источники": sources, "строки": rows}, ensure_ascii=False, indent=1, default=str), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
