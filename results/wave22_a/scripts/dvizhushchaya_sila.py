#!/usr/bin/env python3
"""22-А2, шаг 1 г: движущая сила M23C6 и зарождение при малом C в матрице.

Состав матрицы — со шага перед остановкой прогона на зерне 0 (Cr, Ni — как на
том шаге), C заменяется на 0; 1e-12; 1e-9; 1e-6; 2,75e-5; x_C того шага.
Считается теми же функциями kawin, что ``KWNBase._calcNucleationRate``
(``kawin/precipitation/KWNBase.py:411-466``): ``volumetricDrivingForce`` →
``nucleationBarrier`` → ``betaMulti`` → ``zeldovich`` → ``incubationTime`` →
``nucleationRate`` × число мест; объекты — как в ``run_precipitation``
(``app/thermogar_precipitation.py:1116-1144``), база — через
``_bind_release_database``.

Два режима кэша kawin:

* «без кэша» — новый объект термодинамики и ``removeCache=True``;
* «как в расчёте» — ``removeCache=False`` (``run_precipitation`` включает
  ``cacheCalculations(True)``), новый объект, сначала вызов при составе шага
  перед остановкой, затем при пробном — как в расчёте, где предыдущая стадия
  оставила в кэше свои наборы составов.

Отдельно — локальное равновесие одной матрицы (первый шаг метода касательной,
``Thermodynamics.py:868``): химические потенциалы и признак сходимости решателя
pycalphad.

    python -B dvizhushchaya_sila.py [--npz ../data/a2_shag0_app_seed0.npz] [--out ../data/a2_s1_dvizhushchaya_sila.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for entry in (ROOT / "app", HERE):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import numpy as np  # noqa: E402

import vhody  # noqa: E402

PROBES = (0.0, 1e-12, 1e-9, 1e-6, 2.75e-5)


def build(arguments: dict[str, Any]) -> dict[str, Any]:
    """Те же объекты, что ``build_model`` в ``run_precipitation``."""

    import thermogar_precipitation as tp
    from kawin.precipitation import MatrixParameters, PrecipitateModel, PrecipitateParameters, TemperatureParameters
    from thermogar_release_policy import RELEASE_DATABASE_LABELS, RELEASE_DATABASE_RELATIVE_PATHS

    _key, _path, _sha, _label, db = tp._bind_release_database(
        "fe", ROOT / RELEASE_DATABASE_RELATIVE_PATHS["fe"], RELEASE_DATABASE_LABELS["fe"]
    )
    elements, x_at, _x_wt = tp._composition_vectors(
        db, arguments["balance"], arguments["composition_text"], arguments["units"]
    )
    solutes = elements[1:]

    def make() -> Any:
        temperature = TemperatureParameters(float(arguments["temperature_c"]) + 273.15)
        therm, _class = tp._build_precipitation_thermodynamics(
            db, elements, [arguments["matrix_phase"], arguments["precipitate_phase"]]
        )
        matrix = MatrixParameters(solutes)
        matrix.initComposition = np.asarray(x_at[1:], float)
        matrix.volume.setVolume(float(arguments["matrix_vm"]) * 1e-6, "VM", 1)
        matrix.GBenergy = float(arguments["gb_energy"])
        matrix.nucleationSites.setNucleationDensity(
            grainSize=float(arguments["grain_size_um"]), aspectRatio=1,
            dislocationDensity=float(arguments["dislocation_density"]), bulkN0=float(arguments["bulk_n0"]),
        )
        precipitate = PrecipitateParameters(arguments["precipitate_phase"])
        precipitate.gamma = float(arguments["gamma"])
        precipitate.volume.setVolume(float(arguments["precip_vm"]) * 1e-6, "VM", 1)
        precipitate.nucleation.setNucleationType(arguments["nucleation_type"])
        model = PrecipitateModel(matrix, [precipitate], therm, temperature)
        model.setup()
        return model

    return {"make": make, "elements": elements, "solutes": solutes}


def nucleation(model: Any, x: np.ndarray, t: float, n_particles: float, remove_cache: bool) -> dict[str, Any]:
    """Последовательность ``KWNBase._calcNucleationRate`` для одной фазы."""

    import kawin.precipitation.NucleationRate as nucfuncs

    temperature = float(model.temperatureParameters(t))
    parameters = model.precipitates[0]
    chem, vol_dg, beta_comp = nucfuncs.volumetricDrivingForce(model.therm, x, temperature, parameters, 1, remove_cache)
    out: dict[str, Any] = {
        "dG_J_mol": float(chem) if chem is not None and np.ndim(chem) == 0 else None,
        "dG_J_m3": float(vol_dg),
        "precipitate_composition": None if beta_comp is None else [float(v) for v in np.atleast_1d(beta_comp)],
    }
    if not vol_dg >= 0:
        out.update({"note": "dG < 0: KWNBase.py:422-423 — дальше не считается", "J": 0.0, "Rcrit_nm": None})
        return out
    rcrit, gcrit = nucfuncs.nucleationBarrier(vol_dg, parameters, 1)
    beta = nucfuncs.betaMulti(model.therm, x, temperature, rcrit, model.matrix, parameters, remove_cache, searchDir=beta_comp)
    z = nucfuncs.zeldovich(temperature, rcrit, parameters)
    tau = nucfuncs.incubationTime(beta, z, model.matrix)
    rate = nucfuncs.nucleationRate(z, beta, gcrit, temperature, tau, time=t)
    sites = max(model.matrix.nucleationSites.bulkN0 - n_particles, 0.0)
    out.update({
        "Rcrit_nm": 1e9 * float(rcrit),
        "Gcrit_over_kT": float(gcrit) / (1.380649e-23 * temperature),
        "beta": float(beta),
        "Z": float(z),
        "tau_s": float(tau),
        "J": float(rate) * sites,
        "Rnuc_nm": 1e9 * float(nucfuncs.nucleationRadius(temperature, rcrit, parameters)),
    })
    return out


def matrix_local_eq(model: Any, x: np.ndarray, t: float) -> dict[str, Any]:
    therm = model.therm
    temperature = float(model.temperatureParameters(t))
    result, composition_sets = therm.getLocalEq(x, temperature, 0, [therm.phases[0]], composition_sets=None)
    elements = list(composition_sets[0].phase_record.nonvacant_elements)
    return {
        "converged": bool(result.converged),
        "MU": {e: float(m) for e, m in zip(elements, result.chemical_potentials)},
        "X_matrix": {e: float(v) for e, v in zip(elements, composition_sets[0].X)},
    }


def tangent_steps(model: Any, x: np.ndarray, t: float) -> dict[str, Any]:
    """Метод касательной kawin по шагам (``Thermodynamics.py:866-914``) с флагами сходимости.

    kawin проверяет только NaN в химических потенциалах (``:869``, ``:891``), но не
    ``result.converged``. Здесь — те же вызовы на новом объекте без кэша.
    """

    from kawin.thermo.LocalEquilibrium import local_equilibrium
    from pycalphad import variables as v

    therm = model.therm
    temperature = float(model.temperatureParameters(t))
    precipitate_phase = therm.phases[1]
    result, matrix_sets = therm.getLocalEq(x, temperature, 0, [therm.phases[0]], composition_sets=None)
    conditions = {v.T: temperature, v.P: 101325, v.N: 1}
    elements = list(matrix_sets[0].phase_record.nonvacant_elements)
    conditions.update({v.MU(e): result.chemical_potentials[i] for i, e in enumerate(elements)})
    _dg, precipitate_set = therm._getPrecCompositionSetSamplingDF(
        x, temperature, result.chemical_potentials, precipitate_phase, None
    )
    phases, sub_models = therm._setupSubModels([precipitate_phase])
    precipitate_result, precipitate_sets = local_equilibrium(
        therm.db, therm.elements, phases, conditions, sub_models, therm.phase_records,
        composition_sets=[precipitate_set], pDens=therm.local_pDens,
    )
    return {
        "matrix_converged": bool(result.converged),
        "precipitate_converged": bool(precipitate_result.converged),
        "sampling_start_dG_J_mol": float(np.squeeze(_dg)),
        "dG_J_mol": float(precipitate_result.x[0]),
        "precipitate_X": {e: float(val) for e, val in zip(
            precipitate_sets[0].phase_record.nonvacant_elements, precipitate_sets[0].X)},
        "precipitate_site_fractions": [float(val) for val in precipitate_sets[0].dof[len(therm.stateVariables):]],
        "precipitate_constituents": [[str(sp) for sp in sub] for sub in therm.db.phases[precipitate_phase].constituents],
    }


START_C = (9.1576e-3, 1e-3, 1e-4, 3.8e-5, 1e-6, 1e-9)


def start_dependence(make: Any, x_before: np.ndarray, c_index: int, t: float, targets: tuple[float, ...]) -> list[dict[str, Any]]:
    """Та же функция kawin при x_C = 0 (и 1e-12) после старта из разных составов.

    Кэш метода касательной (``_matrix_cs``, ``_compset_cache_df``) — стартовая
    точка решателя; перед пробой он заполняется одним вызовом при x_C старта.
    """

    import kawin.precipitation.NucleationRate as nucfuncs

    rows = []
    for start_c in START_C:
        for target in targets:
            model = make()
            temperature = float(model.temperatureParameters(t))
            start = x_before.copy()
            start[c_index] = start_c
            nucfuncs.volumetricDrivingForce(model.therm, start, temperature, model.precipitates[0], 1, False)
            probe = x_before.copy()
            probe[c_index] = target
            chem, vol, _comp = nucfuncs.volumetricDrivingForce(model.therm, probe, temperature, model.precipitates[0], 1, False)
            rows.append({"start_x_C": start_c, "x_C": target, "dG_J_mol": float(chem), "dG_J_m3": float(vol)})
            print(f"старт x_C={start_c:<9.3g} → x_C={target:<6.3g}: dG={float(vol):+.4e} Дж/м³ ({float(chem):+.4g} Дж/моль)", flush=True)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npz", default=str(HERE.parent / "data" / "a2_shag0_app_seed0.npz"))
    parser.add_argument("--out", default=str(HERE.parent / "data" / "a2_s1_dvizhushchaya_sila.json"))
    args = parser.parse_args()

    with np.load(args.npz) as archive:
        data = {name: archive[name] for name in archive.files}
    last = len(data["time"]) - 1
    before = last - 1
    x_before = np.asarray(data["composition"][before], float)
    t_before = float(data["time"][before])
    n_before = float(data["precipitateDensity"][before, 0])
    arguments = vhody.app_cell()["arguments"]
    objects = build(arguments)
    solutes = objects["solutes"]
    report: dict[str, Any] = {
        "npz": str(Path(args.npz).relative_to(ROOT)),
        "step_before_stop": before,
        "t_before_s": t_before,
        "x_before": dict(zip(solutes, x_before.tolist())),
        "N_before_m3": n_before,
        "recorded_before": {
            "dG_J_m3": float(data["drivingForce"][before, 0]),
            "J": float(data["nucRate"][before, 0]),
            "Rcrit_nm": 1e9 * float(data["Rcrit"][before, 0]),
        },
        "recorded_at_stop": {
            "x": dict(zip(solutes, np.asarray(data["composition"][last], float).tolist())),
            "dG_J_m3": float(data["drivingForce"][last, 0]),
            "J": float(data["nucRate"][last, 0]),
            "Rcrit_nm": 1e9 * float(data["Rcrit"][last, 0]),
            "Rnuc_nm": 1e9 * float(data["Rnuc"][last, 0]),
        },
        "probes": [],
    }
    c_index = solutes.index("C")
    for x_c in (*PROBES, float(x_before[c_index])):
        x = x_before.copy()
        x[c_index] = x_c
        row: dict[str, Any] = {"x_C": x_c}
        fresh = objects["make"]()
        row["без_кэша"] = nucleation(fresh, x, t_before, n_before, remove_cache=True)
        cached = objects["make"]()
        nucleation(cached, x_before, t_before, n_before, remove_cache=False)
        row["как_в_расчёте"] = nucleation(cached, x, t_before, n_before, remove_cache=False)
        row["матрица_локально"] = matrix_local_eq(objects["make"](), x, t_before)
        row["касательная_по_шагам"] = tangent_steps(objects["make"](), x, t_before)
        report["probes"].append(row)
        a, b, m = row["без_кэша"], row["как_в_расчёте"], row["матрица_локально"]
        print(
            f"x_C={x_c:<10.4g} без кэша: dG={a['dG_J_m3']:+.4e} Дж/м³, J={a['J']:.3e}, Rcrit={a.get('Rcrit_nm')} | "
            f"как в расчёте: dG={b['dG_J_m3']:+.4e}, J={b['J']:.3e}, Rcrit={b.get('Rcrit_nm')} | "
            f"матрица: сошлось={m['converged']}, μ_C={m['MU'].get('C'):.4e} | касательная: матрица "
            f"{row['касательная_по_шагам']['matrix_converged']}, выделение {row['касательная_по_шагам']['precipitate_converged']}, "
            f"dG={row['касательная_по_шагам']['dG_J_mol']:+.4g} Дж/моль, "
            f"X(C) выделения={row['касательная_по_шагам']['precipitate_X'].get('C', float('nan')):.4g}",
            flush=True,
        )
    report["start_dependence"] = start_dependence(objects["make"], x_before, c_index, t_before, (0.0, 1e-12))
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
