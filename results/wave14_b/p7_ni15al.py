"""14-Б, разбор регрессии: Ni-15Al ат. % — умолчание никелевого раздела KWN против BL-32.

    p7_ni15al.py

Оба упавших теста ``tools/test_ui_g.py`` считают γ′ в ``FCC_A1`` на составе
боковой панели Ni-15Al ат. % с умолчаниями раздела (``DEFAULTS["ni"]``: 800 °C,
γ = 0,023 Дж/м², Vm 6,57 см³/моль). Скрипт ничего не решает, только считает
теми же функциями kawin, что ``_nucleus_estimates``: объёмную движущую силу по
начальному составу, незажатый радиус 2γ/ΔGv, радиус после зажима и ``Rmin``.
Сетка температур и γ — для того, чтобы увидеть, насколько случай далёк от
предела; сами числа γ источника не имеют и в умолчания не идут.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kwn_parts as parts  # noqa: E402

OUT = HERE / "p7"
OUT.mkdir(parents=True, exist_ok=True)
parts.setup_state(OUT, "ni15al")

import numpy as np  # noqa: E402
import kawin.precipitation.NucleationRate as nucleation  # noqa: E402
import thermogar_precipitation as tp  # noqa: E402

matrix_phase, precipitate_phase, t_default, _hours, gamma_default, vm_m, vm_p = tp.DEFAULTS["ni"]
db = parts.load_database()
elements, x_at, _x_wt = tp._composition_vectors(db, "NI", "AL=15", "at")
record: dict = {
    "состав": "AL=15 ат. %", "умолчания раздела DEFAULTS['ni']": tp.DEFAULTS["ni"],
    "элементы": elements, "мольные доли": [float(v) for v in x_at],
}
rows = []
for temperature_c in (700.0, 750.0, 800.0, 850.0, 900.0, 950.0, 1000.0):
    case = dict(matrix_phase=matrix_phase, precipitate_phase=precipitate_phase,
                temperature_c=temperature_c, gamma=gamma_default, matrix_vm=vm_m, precip_vm=vm_p,
                nucleation_type="BULK", bulk_n0=1e30, grain_size_um=100.0,
                dislocation_density=5e12, gb_energy=0.3, cmin_nm=0.2, cmax_nm=10.0, bins=40)
    model, _therm_s = parts.build_model(db, elements, x_at, case)
    model.setup()
    p = model.phaseIndex(precipitate_phase)
    parameters = model.precipitates[p]
    composition = np.squeeze(model.data.composition[0])
    t_k = temperature_c + 273.15
    chemical, volume_dg, _beta = nucleation.volumetricDrivingForce(
        model.therm, composition, t_k, parameters, removeCache=True)
    volume_dg = float(np.squeeze(volume_dg))
    floor_nm = 1e9 * float(parameters.Rmin)
    row = {"T, °C": temperature_c, "ΔG, Дж/моль": float(np.squeeze(chemical)),
           "ΔGv, Дж/м³": volume_dg, "Rmin kawin, нм": floor_nm}
    if volume_dg > 0:
        for gamma in (gamma_default, 0.03, 0.05, 0.08):
            unclamped = 1e9 * 2 * gamma / volume_dg
            parameters.gamma = gamma
            rcrit, _g = nucleation.nucleationBarrier(volume_dg, parameters)
            row[f"γ={gamma}: 2γ/ΔGv, нм"] = unclamped
            row[f"γ={gamma}: r* kawin, нм"] = 1e9 * float(rcrit)
        row["γ, при котором 2γ/ΔGv = Rmin, Дж/м²"] = float(parameters.Rmin) * volume_dg / 2
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
record["по температурам"] = rows
record["память"] = parts.mem()
parts.write_json(OUT / "ni15al.json", record)
