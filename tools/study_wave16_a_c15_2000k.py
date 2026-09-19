#!/usr/bin/env python3
"""16-А: фазовый состав стальных марок при верхнем пределе базы Fe (2000 K).

Доказательство к `16A_sravnenie.md` (вопрос 10 «Лилит»): на файле без патча
C15_LAVES устойчива до верхнего предела базы, поэтому расплава при 2000 K нет.
Набор фаз — как в заданиях ``ThermoGar`` / ``polnyj`` с C15_LAVES
(``study_wave16_a_lilith.child_thermogar``), pdens 50; равновесие одной точкой
при ``FE_DATABASE_MAX_T_K`` на обоих файлах Fe. Результат —
``results/wave16_a/c15_2000K.json``.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import study_wave16_a_lilith as s  # noqa: E402


def main() -> None:
    ns = s.app_namespace()
    ns["effective_release_phases"] = lambda database_key, phases: list(phases)
    from pycalphad import equilibrium, variables as v
    from thermogar_database_guard import FE_DATABASE_MAX_T_K

    out = {"T_K": FE_DATABASE_MAX_T_K, "pdens": 50, "marki": {}}
    marki = [r for r in s.read_marki() if r["sistema"] == "Fe"
             and any(j["marka"] == r["marka"] for j in s.plan_jobs(s.read_marki()))]
    for baza in ("mc_fe_2062_bez_patcha", "mc_fe_2062_patch"):
        info = s.BAZY[baza]
        key = info["app_key"]
        db = s.load_db(ns, baza)
        available = sorted(el for el in db.elements if el != "VA")
        for row in marki:
            t0 = time.perf_counter()
            entered = {el: val for el, val in s.sostav_mass(row).items()
                       if el != info["balance"]}
            components, _, _, _ = ns["build_input"](db, available, entered, "wt",
                                                   info["balance"])
            all_phases = ns["compatible_phases_for_components"](
                db, key, components, "metastable", ns["PHASE_MODE_ALL"])
            components, conditions, _, _, phases = ns["prepare_calculation"](
                db, key, entered, "wt", info["balance"], "metastable", list(all_phases))
            cond = {v.N: 1.0, v.P: 101325.0, v.T: FE_DATABASE_MAX_T_K}
            cond.update(conditions)
            eq = equilibrium(db, components, phases, cond, calc_opts={"pdens": 50})
            fractions = {k: round(float(val), 6) for k, val in
                         ns["aggregate_phase_fractions"](eq).items() if val > 0}
            out["marki"].setdefault(row["marka"], {})[baza] = {
                "fazy": fractions, "c15_v_nabore": "C15_LAVES" in phases,
                "sekund": round(time.perf_counter() - t0, 1)}
            s.log(f"{row['marka']} · {baza} · {fractions}")
    path = s.OUT / "c15_2000K.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    s.log(f"{path}")


if __name__ == "__main__":
    main()
