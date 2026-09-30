#!/usr/bin/env python3
"""22-В, шаг 3 (BL-23): случаи 12-1 тем же сценарием (tools/study_hn62m_wave12_kinetics.py,
импорт без правок) с записью внутренних рядов решателя kawin на каждом шаге.

Сценарий 12-1 строит модель kawin ``PrecipitateModel`` напрямую (``build_model``: импорт
``from kawin.precipitation import PrecipitateModel`` внутри функции). Здесь на время процесса
``kawin.precipitation.PrecipitateModel`` подменён подклассом с записью — сценарий получает его,
ничего в сценарии не меняя. Варианты:

* ``base`` — как в 12-1 (запись без вмешательства в шаг);
* ``k2`` — ограничение роста шага 22-Б: не больше K = 2 предыдущих (как
  app/thermogar_precipitation.py:346–352);
* ``cfl`` — сверх задания: ``constraints.maxDissolution = 0`` — индекс растворения kawin не исключает мелкие
  классы из предела шага PSD (0,4·dR/|G| по всем заселённым классам), проверка численной природы скачка N;
* ``fine`` — сетка PBM вдвое мельче: ``K_PBM`` сценария с bins/minBins/maxBins × 2
  (300 / 200 / 400 вместо 150 / 100 / 200), cMin/cMax прежние.

Молярные объёмы и равновесие двух фаз считаются заново (кэш 12-1 не берётся): шаг ``--volumes``
пишет их в results/wave22_v/bl23/w12/cache/k1_volumes.json, а каждый прогон случая копирует этот
файл в свой каталог и дальше идёт по сценарию (``volumes_and_references`` читает кэш, если id
состава совпал). Кэш точек, журнал и итог — в своём каталоге прогона
results/wave22_v/bl23/runs/<метка>_s<зерно>/.

На каждом шаге записываются: пределы шага ``KWNEuler.getDt`` (PSD, зарождение, T, Rcrit, объём) и
какой сработал, шаг kawin и после K; сетка PBM (классов, границы, заселённые > 0 и > 1, первый и
последний заселённый, класс с максимумом PSD, индекс растворения); Rcrit, Rnuc, Ravg, число
выделений, доля, скорость зарождения, движущая сила; наибольшая |G| среди заселённых классов и
число частиц в классах с G < 0. Раз в 200 шагов и на последних 60 — полные массивы (границы, PSD,
скорость роста).

    PYTHONHASHSEED=0 python -B bl23_run.py --volumes
    PYTHONHASHSEED=0 python -B bl23_run.py --T 700 --gamma 0.100 --site BULK --variant base
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import resource
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "app"))
W = ROOT / "results" / "wave22_v" / "bl23"
VOLUMES_DIR = "results/wave22_v/bl23/w12"

SCALARS = [
    "n", "t", "dt_prev", "dt_max", "lim_psd", "lim_nuc", "lim_temp", "lim_rcrit", "lim_vol",
    "dt_kawin", "dt_after_k", "bins", "pbm_min", "pbm_max", "filled", "filled_gt1", "first_filled",
    "last_filled", "psd_argmax", "diss_index", "Rcrit", "Rnuc", "Ravg", "density", "volFrac",
    "nucRate", "drivingForce", "gmax_index", "gmax", "n_negative_growth", "wall",
]
LIMIT_NAMES = ["psd", "nuc", "temp", "rcrit", "vol"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--volumes", action="store_true")
    parser.add_argument("--T", type=float, default=700.0)
    parser.add_argument("--gamma", type=float)
    parser.add_argument("--site", choices=["BULK", "GRAIN BOUNDARIES"])
    parser.add_argument("--variant", default="base", choices=["base", "k2", "fine", "cfl"])
    parser.add_argument("--cap", type=float, default=5400.0)
    args = parser.parse_args()

    import warnings

    warnings.filterwarnings("ignore")
    import numpy as np
    import study_hn62m_wave11 as w11
    import study_hn62m_wave12_kinetics as k1

    if args.volumes:
        k1.configure(temperatures=[args.T], out_dir=VOLUMES_DIR)
        ctx = w11.Context()
        mole = w11.wt_to_mole(ctx, k1.working_wt())
        mole_full = w11.wt_to_mole(ctx, w11.full_wt())
        volumes, refs, refs_full = k1.volumes_and_references(ctx, mole, mole_full)
        print(json.dumps({"volumes": volumes, "refs": refs}, ensure_ascii=False, default=str)[:2000])
        return 0

    seed = os.environ.get("PYTHONHASHSEED", "?")
    site_tag = "obyom" if args.site == "BULK" else "granicy"
    tag = f"T{args.T:g}_{site_tag}_g{args.gamma:g}_{args.variant}"
    run_rel = f"results/wave22_v/bl23/runs/{tag}_s{seed}"
    run_dir = ROOT / run_rel
    (run_dir / "cache").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / VOLUMES_DIR / "cache" / "k1_volumes.json", run_dir / "cache" / "k1_volumes.json")
    k1.configure(temperatures=[args.T], out_dir=run_rel)
    if args.variant == "fine":
        k1.K_PBM = dict(k1.K_PBM, bins=2 * k1.K_PBM["bins"], minBins=2 * k1.K_PBM["minBins"],
                        maxBins=2 * k1.K_PBM["maxBins"])

    import kawin.precipitation as kp

    Original = kp.PrecipitateModel
    rows: list[list[float]] = []
    snapshots: list[dict] = []
    tail: collections.deque = collections.deque(maxlen=60)
    state: dict = {"model": None}
    wall0 = time.perf_counter()
    K = 2.0 if args.variant == "k2" else None

    class Logged(Original):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            if args.variant == "cfl":
                self.constraints.maxDissolution = 0.0

        def getDt(self, dXdt):  # noqa: N802
            d = self.data
            i = int(d.n)
            dt_prev = 0.01 if i == 0 else float(d.time[i] - d.time[i - 1])
            dt_max = float(self.finalTime - d.time[i])
            c = self.constraints
            lims = [
                float(c.computeDTfromPSD(i, d.temperature, self.PBM, self.growth, self.dissolutionIndex, self.phases, dt_max)),
                float(c.computeDTfromNucleationRate(i, d.nucRate, self.phases, dt_prev, dt_max)),
                float(c.computeDTfromTemperature(i, d.temperature, dt_prev, dt_max)),
                float(c.computeDTfromRcrit(i, d.Rcrit, d.drivingForce, self.phases, dt_prev, dt_max)),
                float(c.computeDTfromVolume(i, d.nucRate, d.Rnuc, self.PBM, self.growth, self.matrix.volume.Vm,
                                            [pp.volume.Vm for pp in self.precipitates],
                                            [pp.nucleation for pp in self.precipitates], self.phases, dt_max)),
            ]
            dt_kawin = float(super().getDt(dXdt))
            dt = dt_kawin
            if K is not None and i > 0:
                dt = min(dt, K * dt_prev)
            pbm = self.PBM[0]
            psd = np.asarray(pbm.PSD, float)
            bounds = np.asarray(pbm.PSDbounds, float)
            g = np.asarray(self.growth[0], float)
            filled = np.nonzero(psd > 0)[0]
            filled1 = np.nonzero(psd > 1)[0]
            di = int(self.dissolutionIndex[0])
            if len(filled) and len(g) == len(bounds):
                j = int(filled[np.argmax(np.abs(g[filled]))])
                gmax = float(g[j])
                neg = float(psd[filled][g[filled] < 0].sum())
            else:
                j, gmax, neg = -1, 0.0, 0.0
            rows.append([
                i, float(d.time[i]), dt_prev, dt_max, *lims, dt_kawin, dt, int(pbm.bins), float(bounds[0]),
                float(bounds[-1]), len(filled), len(filled1), int(filled[0]) if len(filled) else -1,
                int(filled[-1]) if len(filled) else -1, int(np.argmax(psd)) if len(psd) else -1, di,
                float(d.Rcrit[i, 0]), float(d.Rnuc[i, 0]), float(d.Ravg[i, 0]),
                float(d.precipitateDensity[i, 0]), float(d.volFrac[i, 0]), float(d.nucRate[i, 0]),
                float(d.drivingForce[i, 0]), j, gmax, neg, time.perf_counter() - wall0,
            ])
            snap = {"n": i, "t": float(d.time[i]), "bounds": bounds.copy(), "psd": psd.copy(), "growth": g.copy()}
            if i % 200 == 0:
                snapshots.append(snap)
            tail.append(snap)
            return dt

    kp.PrecipitateModel = Logged

    def dump(outcome: str, extra: dict | None = None) -> None:
        arr = np.asarray(list(rows), float) if rows else np.zeros((0, len(SCALARS)))
        np.savez_compressed(run_dir / "ryady.npz", scalars=arr, names=np.asarray(SCALARS),
                            snapshots=np.asarray(list(snapshots) + list(tail), dtype=object))
        summary = {
            "T": args.T, "gamma": args.gamma, "site": args.site, "variant": args.variant, "seed": seed,
            "K_PBM": k1.K_PBM, "outcome": outcome, "steps": int(len(arr)),
            "t_model_h": float(arr[-1, 1]) / 3600.0 if len(arr) else None,
            "wall_s": time.perf_counter() - wall0,
            "peak_rss_gib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20,
            **(extra or {}),
        }
        (run_dir / "itog.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), "utf-8")

    stop = threading.Event()

    def watch() -> None:
        with (run_dir / "hod.jsonl").open("a", encoding="utf-8") as fh:
            while not stop.wait(30.0):
                r = rows[-1] if rows else None
                line = {"wall_s": round(time.perf_counter() - wall0, 1)}
                if r is not None:
                    lims = r[4:9]
                    kmin = min(range(5), key=lambda q: lims[q])
                    line.update({"n": r[0], "t_h": r[1] / 3600, "dt": r[10],
                                 "limiter": LIMIT_NAMES[kmin] if lims[kmin] < r[3] else "рост",
                                 "bins": r[11], "filled": r[14], "filled_gt1": r[15], "Ravg_nm": r[22] * 1e9,
                                 "Rcrit_nm": r[20] * 1e9, "N": r[23], "fv": r[24]})
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
                fh.flush()
                if time.perf_counter() - wall0 > args.cap:
                    dump("потолок")
                    os._exit(4)

    threading.Thread(target=watch, daemon=True).start()

    from thermogar_precipitation import _build_precipitation_thermodynamics

    ctx = w11.Context()
    mole = w11.wt_to_mole(ctx, k1.working_wt())
    mole_full = w11.wt_to_mole(ctx, w11.full_wt())
    volumes, refs, _refs_full = k1.volumes_and_references(ctx, mole, mole_full)
    ctx._models = None
    ctx._phase_records = None
    thermodynamics, cls = _build_precipitation_thermodynamics(ctx.db, k1.elements(), [k1.MATRIX_PHASE, k1.PRECIPITATE_PHASE])
    nodes = k1.time_nodes()
    edges = k1.stage_edges()
    cache = k1.CaseCache()
    key = k1.CaseCache.key(mole, args.T, args.gamma, args.site)
    label = "объём зерна" if args.site == "BULK" else "границы зёрен"
    try:
        result_rows = k1.run_case(ctx, thermodynamics, mole, args.T, args.gamma, label, args.site,
                                  volumes[args.T], nodes, edges, cache, key)
    except Exception as error:  # noqa: BLE001
        stop.set()
        dump("ошибка", {"error": f"{type(error).__name__}: {error}"})
        return 3
    stop.set()
    (run_dir / "uzly.json").write_text(json.dumps(result_rows, ensure_ascii=False, indent=0, default=str), "utf-8")
    last = result_rows[-1]
    dump("сошёлся", {
        "rows_nodes": len(result_rows), "fraction_mol_pct_end": last["мольная доля P-фазы, %"],
        "R_nm_end": last["средний радиус, нм"], "N_end": last["число выделений, 1/м³"],
        "thermodynamics_class": cls, "volumes": volumes[args.T],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
