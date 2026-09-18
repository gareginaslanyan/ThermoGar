"""15-Ш, п. 3б: перебор составов базы fe — где в равновесии карбид без прямой модели."""
import sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "app"))
import numpy as np
from pycalphad import Database, equilibrium, variables as v
db = Database(str(root / "databases/converted/fe/mc_fe_v2062.thermogar.tdb"))
cases = [
    ("W", 0.10, 0.010, 1073.15), ("W", 0.18, 0.008, 1073.15), ("W", 0.30, 0.015, 1073.15),
    ("V", 0.10, 0.030, 1073.15), ("V", 0.20, 0.050, 1073.15),
]
masses = {k: float(db.refstates[k]["mass"]) for k in ("FE", "W", "V", "C")}
for element, w_m, w_c, T in cases:
    wfe = 1 - w_m - w_c
    n = {"FE": wfe / masses["FE"], element: w_m / masses[element], "C": w_c / masses["C"]}
    tot = sum(n.values())
    x = {k: val / tot for k, val in n.items()}
    comps = ["FE", element, "C", "VA"]
    phases = [p for p in db.phases if p not in {"GAS"}]
    res = equilibrium(db, comps, phases, {v.T: T, v.P: 101325, v.N: 1, v.X(element): x[element], v.X("C"): x["C"]}, calc_opts={"pdens": 200})
    names = res.Phase.values.ravel(); nps = res.NP.values.ravel()
    print(element, w_m, w_c, T, [(str(a), round(float(b), 5)) for a, b in zip(names, nps) if a], flush=True)
