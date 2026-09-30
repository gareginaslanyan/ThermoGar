#!/usr/bin/env python3
"""22-В, шаг 3 г: есть ли риск BL-23 в разделе «Выделения» — случай 12-1 штатным run_precipitation.

Нынешний код приложения как есть: модель с K = 2 (22-Б), minComposition 1e-8, адаптивная сетка раздела
(minBins = max(20, bins//2), maxBins = max(80, 2·bins)), проверки BL-22/BL-32/BL-35. Входы — 12-1: состав ЭК199-ВИ
без Nb (tools/study_hn62m_wave11.CONTROL_WT, как k1.working_wt()), FCC_A1 / P_PHASE, 700 °C, молярные объёмы из
кэша 22-В (bl23/w12/cache/k1_volumes.json), bulk_n0 = N_A / Vm матрицы, зерно 30 мкм, энергия границы = γ.
Сетка — умолчание раздела (0,2…10 нм × 80) или --bins/--cmin/--cmax. Выдержка --hours (по умолчанию 200 ч).
На каждом шаге пишется: N, J, шаг, классов, границы сетки, индекс растворения, заселённые классы; в конце —
шаги, где прирост N больше 100·J·dt (признак численного рождения частиц).

    PYTHONHASHSEED=0 python -B bl23_app.py --gamma 0.125 --site BULK --hours 200
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "app"))
OUT = ROOT / "results" / "wave22_v" / "bl23" / "app"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gamma", type=float, required=True)
    parser.add_argument("--site", default="BULK")
    parser.add_argument("--hours", type=float, default=200.0)
    parser.add_argument("--bins", type=int, default=80)
    parser.add_argument("--cmin", type=float, default=0.2)
    parser.add_argument("--cmax", type=float, default=10.0)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    import warnings

    warnings.filterwarnings("ignore")
    import numpy as np
    import study_hn62m_wave11 as w11
    import thermogar_precipitation as tp
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    wt = {k: v for k, v in w11.full_wt().items() if k not in ("NB", w11.BALANCE)}
    text = ", ".join(f"{k}={v:g}" for k, v in wt.items())
    vol = json.loads((ROOT / "results/wave22_v/bl23/w12/cache/k1_volumes.json").read_text("utf-8"))["молярные объёмы"]["700"]
    vm_m = float(vol["FCC_A1"]["молярный объём, см³/моль"])
    vm_p = float(vol["P_PHASE"]["молярный объём, см³/моль"])
    bulk = 6.02214076e23 / (vm_m * 1e-6)
    rows: list[list[float]] = []
    Base = tp._StepLimitedPrecipitateModel
    wall0 = time.perf_counter()

    class Logged(Base):  # type: ignore[misc, valid-type]
        def getDt(self, dXdt):  # noqa: N802
            dt = super().getDt(dXdt)
            d = self.data
            i = int(d.n)
            pbm = self.PBM[0]
            psd = np.asarray(pbm.PSD, float)
            rows.append([i, float(d.time[i]), float(dt), int(pbm.bins), float(pbm.PSDbounds[0]), float(pbm.PSDbounds[-1]),
                         int(self.dissolutionIndex[0]), int((psd > 0).sum()), float(d.precipitateDensity[i, 0]),
                         float(d.nucRate[i, 0]), float(d.Rcrit[i, 0]), float(d.Ravg[i, 0]), float(d.volFrac[i, 0]),
                         time.perf_counter() - wall0])
            return dt

    tp._StepLimitedPrecipitateModel = Logged
    seed = os.environ.get("PYTHONHASHSEED", "?")
    tag = f"app_T700_{'obyom' if args.site == 'BULK' else 'granicy'}_g{args.gamma:g}_{args.bins}kl_{args.hours:g}h_s{seed}"
    extra: dict = {}
    try:
        result = tp.run_precipitation(
            db=object(), database_path=ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
            database_label=RELEASE_DATABASE_LABELS["ni"], database_key="ni", balance="NI",
            composition_text=text, units="wt", matrix_phase="FCC_A1", precipitate_phase="P_PHASE",
            schedule_mode="isothermal", temperature_c=700.0, duration_h=args.hours, profile_text="",
            gamma=args.gamma, matrix_vm=vm_m, precip_vm=vm_p, nucleation_type=args.site, bulk_n0=bulk,
            grain_size_um=30.0, dislocation_density=5e12, gb_energy=args.gamma, cmin_nm=args.cmin,
            cmax_nm=args.cmax, bins=args.bins, input_provenance="SYNTHETIC_WAVE22V_BL23_APP_NOT_MATERIAL_INPUT",
            input_confirmation=True,
        )
        k = result.kinetics
        outcome = "остановка BL-35" if result.stop_note else "сошёлся"
        extra = {"rows": int(len(k)), "fraction_pct_end": float(k["Объёмная доля, %"].iloc[-1]),
                 "R_nm_end": float(k["Средний радиус, нм"].iloc[-1]), "N_end": float(k["Плотность частиц, 1/м³"].iloc[-1]),
                 "stop_note": result.stop_note, "warnings": list(result.warnings),
                 "quality_ok": bool((result.quality["Статус"] == "пройдена").all())}
    except Exception as error:  # noqa: BLE001
        outcome = f"ошибка: {type(error).__name__}: {error}"
    a = np.asarray(rows, float) if rows else np.zeros((0, 14))
    jumps = []
    if len(a) > 1:
        dN = np.diff(a[:, 8])
        nuc = np.maximum(a[:-1, 9], a[1:, 9]) * a[:-1, 2]
        idx = np.nonzero((dN > 100 * np.maximum(nuc, 1)) & (dN > 1e10) & (dN > 0.01 * a[:-1, 8]))[0]
        jumps = [{"n": int(a[i, 0]), "t_h": float(a[i, 1] / 3600), "N": [float(a[i, 8]), float(a[i + 1, 8])],
                  "J_dt": float(nuc[i]), "bins": int(a[i, 3]), "bins_next": int(a[i + 1, 3]), "diss": int(a[i, 6])}
                 for i in idx[:50]]
    np.savez_compressed(OUT / f"{tag}.npz", rows=a)
    summary = {"tag": tag, "composition_wt": text, "gamma": args.gamma, "site": args.site, "hours": args.hours,
               "bins": args.bins, "cmin": args.cmin, "cmax": args.cmax, "bulk_n0": bulk, "vm": [vm_m, vm_p],
               "outcome": outcome, "steps": int(len(a)), "t_h_end": float(a[-1, 1] / 3600) if len(a) else None,
               "bins_seen": sorted({int(b) for b in a[:, 3]}) if len(a) else [], "jumps_N_without_J": len(jumps),
               "first_jumps": jumps[:10], "wall_s": time.perf_counter() - wall0,
               "peak_rss_gib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, **extra}
    (OUT / f"{tag}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps({k: summary[k] for k in ("outcome", "steps", "t_h_end", "jumps_N_without_J")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
