"""14-В, пункт 3: признак мастера u = Rmin / r* на всех известных случаях.

    p3_criterion.py

Для каждого случая по начальному составу, теми же функциями kawin, что
``_nucleus_estimates``:

* ΔGv — ``volumetricDrivingForce``;
* r* = 2·f·γ/ΔGv — незажатый критический радиус (f — ``thermoFactor`` сферы, 1);
* u = Rmin / r*, признак мастера 3u² − 2u³ и что даёт новое правило;
* барьер, который kawin 0.5.0 фактически подставляет в скорость зарождения, —
  ``nucleationBarrier`` — против классического G* = (4π/3)·γ·r*², и оба в kT.

Отдельно — тот же расчёт барьера при зарождении на границах зёрен, где kawin
считает барьер другой формулой (``NucleationBarrierParameters.Gcrit``).
Составы и входы — 14-А и 14-Б; синтетические, без источника.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "wave14_b"))
import kwn_parts as parts  # noqa: E402

OUT = HERE / "p3"
OUT.mkdir(parents=True, exist_ok=True)
parts.setup_state(OUT, "criterion")

import numpy as np  # noqa: E402
import kawin.precipitation.NucleationRate as nucleation  # noqa: E402
from kawin.Constants import BOLTZMANN_CONSTANT  # noqa: E402
import thermogar_precipitation as tp  # noqa: E402

BASE = dict(matrix_phase="FCC_A1", precipitate_phase="GAMMA_PRIME", temperature_c=750.0,
            gamma=0.023, matrix_vm=6.5662724928, precip_vm=6.5662724928, nucleation_type="BULK",
            bulk_n0=1e30, grain_size_um=100.0, dislocation_density=5e12, gb_energy=0.3,
            cmin_nm=0.2, cmax_nm=10.0, bins=80)
_m, _p, t_ni, _h, gamma_ni, vm_ni_m, vm_ni_p = tp.DEFAULTS["ni"]
CASES = [
    ("А5, проход a (снят через 69 мин)", "CR=19, NB=5.1, TI=0.9, AL=0.5, FE=18", "wt", {},
     "зависание: > 4130 с процессора, снят"),
    ("А5, проход b", "CR=19, NB=5.1, TI=0.9, AL=0.5, FE=18", "wt", {},
     "зависание: шаг 1,05·10⁻⁷ с к 60 с, снят"),
    ("А6", "CR=19, NB=5.1, TI=0.9, AL=0.5, FE=18, MO=3", "wt", {},
     "зависание: не закончен за 300 с"),
    ("А7", "CR=19, NB=5.1, TI=0.9, AL=0.5, FE=18, MO=3, CO=1", "wt", {},
     "зависание: не закончен за 300 с"),
    ("C4, штатный run_precipitation", "CR=19, NB=5.1, TI=0.9, FE=18", "wt", {},
     "зависание: не вернулся за 300 с (из частей — шаг 10⁻⁷ с к 120 с)"),
    ("умолчание Ni-раздела", "AL=15", "at",
     dict(temperature_c=t_ni, gamma=gamma_ni, matrix_vm=vm_ni_m, precip_vm=vm_ni_p, bins=80),
     "на main: 1 ч за 86 с, все 9 проверок пройдены (14-Б)"),
    ("Б5", "CR=19, NB=5.1, TI=0.9, AL=0.5, FE=0.5", "wt", {}, "PASS, 328 шагов (14-А, 14-Б)"),
    ("А4", "CR=19, NB=5.1, TI=0.9, AL=0.5", "wt", {}, "PASS, 290 шагов (14-А)"),
]


def barrier_ratio(u: float) -> float:
    return 3 * u**2 - 2 * u**3


db = parts.load_database()
rows = []
for name, text, units, override, observed in CASES:
    case = dict(BASE, **override)
    elements, x_at, _x_wt = parts.composition_vectors_unlimited(db, "NI", text, units)
    model, _s = parts.build_model(db, elements, x_at, case)
    model.setup()
    p = model.phaseIndex(case["precipitate_phase"])
    params = model.precipitates[p]
    t_k = case["temperature_c"] + 273.15
    composition = np.squeeze(model.data.composition[0])
    _chem, dgv, _beta = nucleation.volumetricDrivingForce(model.therm, composition, t_k, params, removeCache=True)
    dgv = float(np.squeeze(dgv))
    rmin = float(params.Rmin)
    r_true = 2 * float(params.shapeFactor.description.thermoFactor(1)) * float(params.gamma) / dgv
    u = rmin / r_true
    f = barrier_ratio(u)
    rule = ("ничего (зажима нет)" if r_true >= rmin
            else "ОТКАЗ" if r_true <= (2.0 / 3.0) * rmin
            else f"предупреждение: барьер занижен на {100 * (1 - f):.1f} %")
    rcrit_k, gcrit_k = nucleation.nucleationBarrier(dgv, params)
    g_true = (4 * math.pi / 3) * float(params.gamma) * r_true**2
    kt = BOLTZMANN_CONSTANT * t_k
    row = {
        "случай": name, "состав": f"{text} ({units})", "T, °C": case["temperature_c"], "γ": case["gamma"],
        "ΔGv, Дж/м³": dgv, "Rmin, нм": 1e9 * rmin, "r* незажатый, нм": 1e9 * r_true,
        "r* kawin, нм": 1e9 * float(rcrit_k), "u": u, "3u²−2u³": f, "новое правило": rule,
        "на самом деле": observed,
        "BULK: барьер kawin, Дж": float(gcrit_k), "BULK: G* классический, Дж": g_true,
        "BULK: барьер kawin / G*": float(gcrit_k) / g_true,
        "BULK: барьер kawin / kT": float(gcrit_k) / kt, "BULK: G* / kT": g_true / kt,
    }
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)

# Зарождение на границах зёрен: kawin считает барьер по R полным выражением.
gb_case = dict(BASE, nucleation_type="GRAIN BOUNDARIES", gb_energy=0.02)
elements, x_at, _x_wt = parts.composition_vectors_unlimited(db, "NI", CASES[0][1], "wt")
model, _s = parts.build_model(db, elements, x_at, gb_case)
model.setup()
params = model.precipitates[model.phaseIndex("GAMMA_PRIME")]
t_k = gb_case["temperature_c"] + 273.15
_chem, dgv, _beta = nucleation.volumetricDrivingForce(
    model.therm, np.squeeze(model.data.composition[0]), t_k, params, removeCache=True)
dgv = float(np.squeeze(dgv))
nuc = params.nucleation
r_true = float(nuc.Rcrit(dgv))
g_true = float(nuc.Gcrit(dgv, r_true))
rcrit_k, gcrit_k = nucleation.nucleationBarrier(dgv, params)
u = float(params.Rmin) / r_true
gb = {
    "случай": "А5, GRAIN BOUNDARIES, γ_gb = 0,02 Дж/м² (только проверка формулы kawin)",
    "r* незажатый, нм": 1e9 * r_true, "r* kawin, нм": 1e9 * float(rcrit_k), "u": u,
    "барьер kawin / G*": float(gcrit_k) / g_true, "3u²−2u³": barrier_ratio(u),
}
print(json.dumps(gb, ensure_ascii=False), flush=True)
parts.write_json(OUT / "criterion.json", {"случаи BULK": rows, "границы зёрен": gb, "память": parts.mem()})
