#!/usr/bin/env python3
"""22-В, шаг 2 б: скорость зарождения по стадиям итератора kawin на каждом шаге (BL-33).

kawin 0.5.0 ``rk4Iterator`` вызывает f четыре раза (k1…k4), но каждое ``updateX`` проходит через
``correctdXdt``, а тот (``KWNEuler._correctdXdt`` → ``PopulationBalanceModel.correctdXdtEuler``)
пересобирает производную из ``PBM._netFlux`` и ``self._currY.nucRate`` ПОСЛЕДНЕГО вызова f. Итоговое
``updateX(X_old, dxdtsum/6, dt)`` поэтому берёт производную стадии 4 (состояние X_k3), а не сумму.

Скрипт — та же постановка, что bl33_run.py (штатный run_precipitation, порог BL-32 поднят, модель
приложения с K = 2), плюс обёртка ``_calcNucleationRate``: на каждом шаге записываются J, Rcrit,
движущая сила, состав матрицы и число частиц по стадиям; и приращение числа частиц за шаг.

    PYTHONHASHSEED=0 python -B bl33_stadii.py --case A5 --steps 400 --out results/wave22_v/bl33/stadii
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "app"))


class Enough(Exception):
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="A5")
    parser.add_argument("--gamma", type=float, default=None)
    parser.add_argument("--variant", default="k2", choices=["k2", "kawin"])
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    import warnings

    warnings.filterwarnings("ignore")
    import numpy as np
    import bl33_run
    import thermogar_precipitation as tp
    from kawin.precipitation import PrecipitateModel
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    text, base = bl33_run.CASES[args.case]
    case = dict(base)
    if args.gamma is not None:
        case["gamma"] = args.gamma
    tp.CRITICAL_RADIUS_REFUSAL_RATIO = 1e9
    Base = tp._StepLimitedPrecipitateModel if args.variant == "k2" else PrecipitateModel
    if args.variant == "kawin":
        tp.KWN_MIN_COMPOSITION = 0.0
    records: list[dict] = []
    current: dict = {}

    class Staged(Base):  # type: ignore[misc, valid-type]
        DT_GROWTH_LIMIT = getattr(Base, "DT_GROWTH_LIMIT", float("inf"))

        def getDt(self, dXdt):  # noqa: N802
            dt = super().getDt(dXdt)
            current["dt"] = float(dt)
            return dt

        def _calcNucleationRate(self, t, x, Y):  # noqa: N802
            Y = super()._calcNucleationRate(t, x, Y)
            current.setdefault("stages", []).append({
                "J": float(Y.nucRate[0, 0]), "beta": float(Y.impingement[0, 0]), "Gcrit": float(Y.Gcrit[0, 0]), "Rcrit_nm": float(Y.Rcrit[0, 0]) * 1e9,
                "Rnuc_nm": float(Y.Rnuc[0, 0]) * 1e9, "dGv": float(Y.drivingForce[0, 0]),
                "x": np.asarray(Y.composition[0], float).tolist(), "fv": float(Y.volFrac[0, 0]),
                "N_in_x": float(np.sum(x[0])),
            })
            return Y

        def postProcess(self, t, x):  # noqa: N802
            n_before = float(np.sum(self.PBM[0].PSD))
            result = super().postProcess(t, x)
            stages = current.pop("stages", [])
            n_after = float(np.sum(self.PBM[0].PSD))
            records.append({
                "n": int(self.data.n), "t": float(t), "dt": current.get("dt"),
                "N_before": n_before, "N_after": n_after, "dN": n_after - n_before,
                "stages": stages,
            })
            if len(records) >= args.steps:
                raise Enough()
            return result

    tp._StepLimitedPrecipitateModel = Staged
    try:
        tp.run_precipitation(
            db=object(), database_path=ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
            database_label=RELEASE_DATABASE_LABELS["ni"], database_key="ni", balance="NI",
            composition_text=text, units=case["units"], matrix_phase=case["matrix_phase"],
            precipitate_phase=case["precipitate_phase"], schedule_mode="isothermal",
            temperature_c=case["temperature_c"], duration_h=case["duration_s"] / 3600.0, profile_text="",
            gamma=case["gamma"], matrix_vm=case["matrix_vm"], precip_vm=case["precip_vm"],
            nucleation_type="BULK", bulk_n0=1e30, grain_size_um=100.0, dislocation_density=5e12,
            gb_energy=0.3, cmin_nm=case["cmin_nm"], cmax_nm=case["cmax_nm"], bins=case["bins"],
            input_provenance="SYNTHETIC_WAVE22V_BL33_NOT_MATERIAL_INPUT", input_confirmation=True,
        )
        outcome = "расчёт закончился"
    except Enough:
        outcome = f"остановлено скриптом после {args.steps} шагов"
    except Exception as error:  # noqa: BLE001
        outcome = f"{type(error).__name__}: {error}"
    seed = os.environ.get("PYTHONHASHSEED", "?")
    name = f"{args.case}{'' if args.gamma is None else '_g%g' % args.gamma}_{args.variant}_s{seed}"
    (out / f"{name}.json").write_text(json.dumps({"outcome": outcome, "steps": records}, ensure_ascii=False), "utf-8")
    print(outcome)
    for r in records[:: max(1, len(records) // 25)] + records[-3:]:
        s = r["stages"]
        js = " / ".join(f"{q['J']:.2e}" for q in s)
        print(f"n={r['n']} t={r['t']:.5g} dt={r['dt']:.3g} J по вызовам: {js}  J·dt(1)={s[0]['J'] * (r['dt'] or 0):.3g} "
              f"ΔN={r['dN']:.3g} x_Nb(1..)={[round(q['x'][3], 6) if len(q['x']) > 3 else None for q in s]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
