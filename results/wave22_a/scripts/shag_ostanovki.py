#!/usr/bin/env python3
"""22-А: шаг остановки BL-35 по сохранённым NPZ — до и после последнего шага.

Для каждого прогона ячейки приложения: шаг по времени перед остановкой и на
ней, углерод матрицы, равновесный состав феррита на конноде kawin
(``xEqAlpha``), доля, число частиц, средний радиус, углерод в выделениях
против исходного и «сырой» состав до зажима, невязка баланса на принятых шагах.

    python -B shag_ostanovki.py > ../logs/shag1_shag_ostanovki.txt
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"
RUNS = ("shag1_app", "shag1_app_seed0_a", "shag1_app_seed1", "shag1_app_seed2")


def main() -> None:
    for tag in RUNS:
        with np.load(DATA / f"{tag}.npz") as archive:
            d = {name: archive[name] for name in archive.files}
        t = d["time"]
        x = d["composition"][:, 0]
        fv = d["volFrac"][:, 0]
        n_part = d["precipitateDensity"][:, 0]
        radius = d["Ravg"][:, 0] * 1e9
        fconc = d["fconc"][:, 0, 0]
        x_eq = d["xEqAlpha"][:, 0, 0]
        x0 = x[0]
        raw = (x0 - fconc) / (1 - fv)
        residual = x0 - ((1 - fv) * x + fconc)
        last = len(t) - 1
        prev = last - 1
        dt_last = t[last] - t[last - 1]
        dt_prev = t[prev] - t[prev - 1]
        plateau = (t > 0.8) & (np.arange(len(t)) < last)
        print(f"== {tag}: шагов {len(t)}, остановка на {t[last]:.10g} с")
        print(f"   невязка C на шагах 0…{prev}: max |x0 − [(1−f)x + f_conc]| = {np.max(np.abs(residual[:last])):.3g}")
        print(f"   плато (t > 0,8 с, до остановки): x_C {x[plateau].min():.4g}…{x[plateau].max():.4g}, "
              f"xEqAlpha_C {x_eq[plateau].min():.4g}…{x_eq[plateau].max():.4g}, доля {fv[plateau].min():.6f}…{fv[plateau].max():.6f}"
              if plateau.any() else "   плато t > 0,8 с нет")
        print(f"   шаг по времени: предпоследний {dt_prev:.4g} с, последний {dt_last:.4g} с (×{dt_last / dt_prev:.1f})")
        print(f"   до (шаг {prev}): x_C {x[prev]:.4g}, xEqAlpha_C {x_eq[prev]:.4g} (x_C/xEq = {x[prev] / x_eq[prev]:.3f}), "
              f"доля {fv[prev]:.5f}, N {n_part[prev]:.4g} м⁻³, R {radius[prev]:.4g} нм, C в выделениях {fconc[prev] / x0:.4f}·x0")
        print(f"   после (шаг {last}): x_C {x[last]:.4g} (сырой {raw[last]:.4g} = {raw[last] / x0:+.3f}·x0), "
              f"доля {fv[last]:.5f}, N {n_part[last]:.4g} м⁻³, R {radius[last]:.4g} нм, C в выделениях {fconc[last] / x0:.4f}·x0, "
              f"невязка {residual[last]:.4g}")
        print(f"   за один шаг: доля ×{fv[last] / fv[prev]:.3f}, N ×{n_part[last] / n_part[prev]:.1f}, "
              f"зарождение на шаге остановки {d['nucRate'][last, 0]:.3g} м⁻³с⁻¹, "
              f"движущая сила {d['drivingForce'][last, 0]:.4g} Дж/м³ (до: {d['drivingForce'][prev, 0]:.4g})")


if __name__ == "__main__":
    main()
