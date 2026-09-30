#!/usr/bin/env python3
"""22-В, шаг 1 б: почему у ni до 6ee93bf нет зарождения — β, Z, τ, D по коду дерева.

Прогоняет ту же ячейку, что bl28_run.py (тот же вызов run_precipitation дерева), но перехватывает
модель kawin (обёртка GenericModel.solve только запоминает self) и после расчёта читает:
impingement β, Rcrit, Gcrit/kT, скорость зарождения на первых шагах; τ = 1/(θ·β·Z²);
трассерные коэффициенты диффузии матрицы при начальном составе; строки MQ базы для FCC_A1.

    PYTHONHASHSEED=0 python -B bl28_beta.py --tree <дерево> --tag <метка> --out <каталог>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--db", default="ni")
    args = parser.parse_args()
    tree = Path(args.tree).resolve()
    out = Path(args.out).resolve()
    import warnings

    warnings.filterwarnings("ignore")
    os.chdir(tree)
    import bl28_run

    tbc = bl28_run.load_test_module(tree)
    case = tbc.CASES[args.db]
    import numpy as np
    from kawin.GenericModel import GenericModel
    from kawin.Constants import BOLTZMANN_CONSTANT
    from kawin.precipitation import NucleationRate as nucfuncs

    captured: list = []
    original_solve = GenericModel.solve

    def solve(self, *a, **k):
        captured.append(self)
        return original_solve(self, *a, **k)

    GenericModel.solve = solve
    import thermogar_precipitation as tp
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    composition_text = ", ".join(f"{e}={v:g}" for e, v in case.kwn_composition_pct.items())
    tp.run_precipitation(
        db=object(), database_path=tbc.database_path(case),
        database_label=RELEASE_DATABASE_LABELS.get(case.key, case.label), database_key=case.key,
        balance=case.balance, composition_text=composition_text, units=case.kwn_units,
        matrix_phase=case.kwn_matrix, precipitate_phase=case.kwn_precipitate,
        schedule_mode="isothermal", temperature_c=case.kwn_temperature_c, duration_h=1.0/3600.0,
        profile_text="", gamma=case.kwn_gamma, matrix_vm=case.kwn_molar_volume_cm3,
        precip_vm=case.kwn_molar_volume_cm3, nucleation_type="BULK", bulk_n0=1e30,
        grain_size_um=100.0, dislocation_density=5e12, gb_energy=0.3,
        cmin_nm=case.kwn_size_nm[0], cmax_nm=case.kwn_size_nm[1], bins=30,
        input_provenance="SYNTHETIC_BACKEND_REGRESSION_NOT_MATERIAL_INPUT", input_confirmation=True,
    )
    model = captured[-1]
    d = model.data
    p = 0
    T = float(d.temperature[0])
    x0 = np.asarray(d.composition[0], float)
    prec = model.precipitates[p]
    rows = []
    for i in range(1, 4):
        Rcrit = float(d.Rcrit[i, p])
        beta = float(d.impingement[i, p])
        Z = float(nucfuncs.zeldovich(T, Rcrit, prec)) if Rcrit > 0 else 0.0
        tau = 1.0/(model.matrix.theta*beta*Z**2) if beta > 0 and Z > 0 else None
        rows.append({
            "шаг": i, "t, с": float(d.time[i]), "Rcrit, нм": Rcrit*1e9,
            "beta (impingement), 1/с": beta, "Z": Z, "tau, с": tau,
            "Gcrit/kT": float(d.Gcrit[i, p])/(BOLTZMANN_CONSTANT*T),
            "скорость зарождения, 1/(м3·с)": float(d.nucRate[i, p]),
        })
    try:
        diff = model.therm.getTracerDiffusivity(x0, T)
        tracer = {el: float(v) for el, v in zip(model.therm.elements[:-1] if len(np.atleast_1d(diff)) == len(model.therm.elements) - 1 else model.therm.elements, np.atleast_1d(diff))}
    except Exception as error:  # noqa: BLE001
        tracer = f"{type(error).__name__}: {error}"
    dilute = {}
    for label, xd in (("разбавленный предел (добавки по 1e-6)", [1e-6]*len(x0)),
                      ("половина состава", list(0.5*x0))):
        try:
            dd = np.atleast_1d(model.therm.getTracerDiffusivity(np.asarray(xd), T))
            dilute[label] = [float(v) for v in dd]
        except Exception as error:  # noqa: BLE001
            dilute[label] = f"{type(error).__name__}: {error}"
    try:
        imp = float(model.therm.impingementFactor(x0, T, precPhase=prec.phase))
    except Exception as error:  # noqa: BLE001
        imp = f"{type(error).__name__}: {error}"
    # строки подвижности матрицы в разобранной (и поправленной приложением) базе
    db = model.therm.db
    mq = []
    for record in db._parameters.all():
        if record.get("phase_name") == case.kwn_matrix and record.get("parameter_type") in ("MQ", "MF"):
            mq.append((record.get("parameter_type"), str(record.get("diffusing_species")),
                       str(record.get("constituent_array")), int(record.get("parameter_order", 0))))
    summary = {
        "tag": args.tag, "tree": str(tree), "T, K": T, "x0 (добавки)": x0.tolist(),
        "элементы therm": list(model.therm.elements),
        "трассерная D при x0, м2/с": tracer,
        "трассерная D (порядок как выше) при других составах": dilute,
        "impingementFactor при x0 (без Rcrit²/a⁴)": imp,
        "theta матрицы": float(model.matrix.theta), "a матрицы, м": float(model.matrix.volume.a),
        "первые шаги": rows,
        "строк MQ/MF FCC_A1 в базе": len(mq),
        "строки MQ/MF FCC_A1": sorted(mq),
    }
    (out / f"beta_{args.db}_{args.tag}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "строки MQ/MF FCC_A1"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
