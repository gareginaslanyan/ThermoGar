#!/usr/bin/env python3
"""22-В, шаг 2 (BL-33): расчёт выделений штатным run_precipitation с поднятым порогом BL-32
и записью внутренних рядов решателя kawin на каждом шаге.

Подмены — только в этом процессе, app/ не меняется:
* ``tp.CRITICAL_RADIUS_REFUSAL_RATIO = 1e9`` — отказ BL-32 не срабатывает (сравнение в
  ``_check_critical_radius_floor`` читает глобальное имя модуля);
* ``tp._StepLimitedPrecipitateModel`` — подкласс с записью: вариант ``k2`` — наследник модели
  приложения (ограничение роста шага 22-Б, K = 2, minComposition 1e-8); вариант ``kawin`` —
  наследник ``kawin PrecipitateModel`` без ограничения шага и с minComposition kawin по
  умолчанию (0), как в 14-А;
* вариант ``k2s`` — ``k2`` плюс проверка баланса масс BL-35 на КАЖДОЙ стадии итератора kawin (обёртка
  ``_calcMassBalance``): если у добавки, бывшей в сплаве, x0 − Σfconc ≤ 0 на любой стадии, расчёт
  останавливается после этого шага (исход «остановка по стадии»); проба предложения 22-В, не код приложения;
* ``--gamma``/``--T`` — лестница по u (u = Rmin/r*, r* = 2γ/ΔGv до зажима).

На каждом шаге записываются: пределы шага ``KWNEuler.getDt`` по отдельности (PSD, скорость
зарождения, температура, Rcrit, объём), какой из них сработал, ответ после K, шаг после зажима
решателя (minDtFrac·t_кон), число классов PBM и их границы, заселённые классы, класс зародыша и
скорость роста на его границах, класс с наибольшей |G| (он задаёт предел PSD), Rcrit, Rnuc,
скорость зарождения, доля, плотность, средний радиус, состав матрицы, xEqAlpha / xEqBeta.
Последние 60 шагов — ещё и полные массивы (границы, PSD, скорость роста).

Потолок стены ``--cap`` (с): поток опроса пишет ход раз в 10 с, а на потолке сохраняет всё и
завершает процесс с кодом 4 (исход «потолок»).

    PYTHONHASHSEED=0 python -B bl33_run.py --case A5 --variant k2 --cap 600 --out <каталог>
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import resource
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "app"))

# Входы 14-А (results/wave14_a/p3_ladder.py, kwn_parts.LADDER_WT; results/wave14_g/p3_cases.py):
# γ′ в FCC_A1, 750 °C, γ = 0,023, Vm 6,5662724928 у обеих фаз, BULK 1e30, 0,2…10 нм × 80, 10 с, масс. %.
LADDER = dict(units="wt", matrix_phase="FCC_A1", precipitate_phase="GAMMA_PRIME", temperature_c=750.0,
              duration_s=10.0, gamma=0.023, matrix_vm=6.5662724928, precip_vm=6.5662724928,
              cmin_nm=0.2, cmax_nm=10.0, bins=80)
# Умолчание Ni-раздела (14-Г: u = 1,12, 1 ч): AL=15 ат.%, 800 °C, γ 0,023, Vm 6,57, 0,2…10 нм × 80.
NI_DEFAULT = dict(units="at", matrix_phase="FCC_A1", precipitate_phase="GAMMA_PRIME", temperature_c=800.0,
                  duration_s=3600.0, gamma=0.023, matrix_vm=6.57, precip_vm=6.57,
                  cmin_nm=0.2, cmax_nm=10.0, bins=80)
CASES = {
    "A5": ("CR=19, NB=5.1, TI=0.9, AL=0.5, FE=18", LADDER),
    "A6": ("CR=19, NB=5.1, TI=0.9, AL=0.5, FE=18, MO=3", LADDER),
    "A7": ("CR=19, NB=5.1, TI=0.9, AL=0.5, FE=18, MO=3, CO=1", LADDER),
    "C4": ("CR=19, NB=5.1, TI=0.9, FE=18", LADDER),
    "A4": ("CR=19, NB=5.1, TI=0.9, AL=0.5", LADDER),
    "B5": ("CR=19, NB=5.1, TI=0.9, AL=0.5, FE=0.5", LADDER),
    "NI": ("AL=15", NI_DEFAULT),
}

SCALARS = [
    "n", "t", "dt_prev", "dt_max", "lim_psd", "lim_nuc", "lim_temp", "lim_rcrit", "lim_vol",
    "dt_kawin", "dt_after_k", "dt_taken", "bins", "pbm_min", "pbm_max", "filled", "first_filled",
    "last_filled", "diss_index", "n_rad", "g_nuc_lo", "g_nuc_hi", "gmax_index", "gmax", "gmax_R",
    "gmax_psd", "Rcrit", "Rnuc", "nucRate", "volFrac", "density", "Ravg", "drivingForce", "wall",
]
LIMIT_NAMES = ["psd", "nuc", "temp", "rcrit", "vol"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=sorted(CASES))
    parser.add_argument("--variant", default="k2", choices=["k2", "kawin", "k2s"])
    parser.add_argument("--gamma", type=float, default=None)
    parser.add_argument("--T", type=float, default=None, help="температура, °C")
    parser.add_argument("--duration", type=float, default=None, help="модельное время, с")
    parser.add_argument("--nucleation", default="BULK")
    parser.add_argument("--cap", type=float, default=600.0)
    parser.add_argument("--tag", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    seed = os.environ.get("PYTHONHASHSEED", "?")
    text, base = CASES[args.case]
    case = dict(base)
    if args.gamma is not None:
        case["gamma"] = args.gamma
    if args.T is not None:
        case["temperature_c"] = args.T
    if args.duration is not None:
        case["duration_s"] = args.duration
    tag = args.tag or f"{args.case}_{args.variant}"
    stem = f"{tag}_s{seed}"
    progress_path = out / f"{stem}_progress.jsonl"
    progress_path.write_text("", encoding="utf-8")

    import warnings

    warnings.filterwarnings("ignore")
    import numpy as np
    import thermogar_precipitation as tp
    from kawin.precipitation import PrecipitateModel
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    tp.CRITICAL_RADIUS_REFUSAL_RATIO = 1e9
    if args.variant == "kawin":
        tp.KWN_MIN_COMPOSITION = 0.0  # по умолчанию kawin (Constraints.minComposition = 0), как в 14-А
        Base = PrecipitateModel
    else:
        Base = tp._StepLimitedPrecipitateModel

    rows: list[list[float]] = []
    comps: list[list[float]] = []
    snapshots: collections.deque = collections.deque(maxlen=60)
    state: dict = {"model": None, "t0": None, "dtmin": None, "estimates": None, "u": None}
    wall0 = time.perf_counter()

    class Logged(Base):  # type: ignore[misc, valid-type]
        def getDt(self, dXdt):  # noqa: N802 — имя kawin
            d = self.data
            i = int(d.n)
            dt_prev = 0.01 if i == 0 else float(d.time[i] - d.time[i - 1])
            dt_max = float(self.finalTime - d.time[i])
            c = self.constraints
            vm_a = self.matrix.volume.Vm
            vm_b = [pp.volume.Vm for pp in self.precipitates]
            nuc = [pp.nucleation for pp in self.precipitates]
            lims = [
                float(c.computeDTfromPSD(i, d.temperature, self.PBM, self.growth, self.dissolutionIndex, self.phases, dt_max)),
                float(c.computeDTfromNucleationRate(i, d.nucRate, self.phases, dt_prev, dt_max)),
                float(c.computeDTfromTemperature(i, d.temperature, dt_prev, dt_max)),
                float(c.computeDTfromRcrit(i, d.Rcrit, d.drivingForce, self.phases, dt_prev, dt_max)),
                float(c.computeDTfromVolume(i, d.nucRate, d.Rnuc, self.PBM, self.growth, vm_a, vm_b, nuc, self.phases, dt_max)),
            ]
            dt_kawin = float(PrecipitateModel.getDt(self, dXdt))
            dt = float(super().getDt(dXdt))
            dtmin = state["dtmin"] or 0.0
            taken = min(dt if dt > dtmin else dtmin, dt_max)  # DESolver: зажим снизу dtmin, сверху — остаток времени
            pbm = self.PBM[0]
            g = np.asarray(self.growth[0], float)
            psd = np.asarray(pbm.PSD, float)
            bounds = np.asarray(pbm.PSDbounds, float)
            filled = np.nonzero(psd > 0)[0]
            di = int(self.dissolutionIndex[0])
            idx = np.nonzero(psd[di:] > 0)[0] + di
            if len(idx) and len(g) == len(bounds):
                j = int(idx[np.argmax(np.abs(g[idx]))])
                gmax, gmax_r, gmax_psd = float(g[j]), float(bounds[j]), float(psd[j])
            else:
                j, gmax, gmax_r, gmax_psd = -1, 0.0, 0.0, 0.0
            rnuc = float(d.Rnuc[i, 0])
            n_rad = int(np.argmax(bounds > rnuc) - 1) if rnuc > 0 else -2
            g_lo = float(g[n_rad]) if 0 <= n_rad < len(g) else float("nan")
            g_hi = float(g[n_rad + 1]) if 0 <= n_rad + 1 < len(g) else float("nan")
            rows.append([
                i, float(d.time[i]), dt_prev, dt_max, *lims, dt_kawin, dt, taken, int(pbm.bins),
                float(bounds[0]), float(bounds[-1]), len(filled),
                int(filled[0]) if len(filled) else -1, int(filled[-1]) if len(filled) else -1,
                di, n_rad, g_lo, g_hi, j, gmax, gmax_r, gmax_psd,
                float(d.Rcrit[i, 0]), rnuc, float(d.nucRate[i, 0]), float(d.volFrac[i, 0]),
                float(d.precipitateDensity[i, 0]), float(d.Ravg[i, 0]), float(d.drivingForce[i, 0]),
                time.perf_counter() - wall0,
            ])
            comps.append([*np.asarray(d.composition[i], float).tolist(),
                          *np.asarray(d.xEqAlpha[i, 0], float).tolist(),
                          *np.asarray(d.xEqBeta[i, 0], float).tolist()])
            snapshots.append({"n": i, "bounds": bounds.copy(), "psd": psd.copy(), "growth": g.copy()})
            return dt

        def _calcMassBalance(self, t, x, Y):  # noqa: N802
            Y = super()._calcMassBalance(t, x, Y)
            if args.variant == "k2s" and state.get("stage_stop") is None:
                raw = np.asarray(self.data.composition[0], float) - np.sum(np.asarray(Y.fconc[0], float), axis=0)
                bad = np.nonzero((np.asarray(self.data.composition[0], float) > 0) & (raw <= 0))[0]
                if len(bad):
                    names_ = [e for e in self.therm.elements[1:] if e != "VA"]
                    state["stage_stop"] = {"t": float(t), "n": int(self.data.n), "element": names_[int(bad[0])],
                                           "raw": float(raw[int(bad[0])])}
            return Y

        def postProcess(self, t, x):  # noqa: N802
            X, stop = super().postProcess(t, x)
            if state.get("stage_stop") is not None:
                stop = True
            return X, stop

        def solve(self, simTime, *a, **k):  # noqa: N802
            state["model"] = self
            state["dtmin"] = 1e-8 * float(simTime)  # DESolver: minDtFrac (1e-8 по умолчанию) × simTime
            state["t0"] = time.perf_counter()
            return super().solve(simTime, *a, **k)

    if args.variant == "kawin":
        Logged.DT_GROWTH_LIMIT = float("inf")  # диагностика остановки 22-Б читает это поле у модели
    tp._StepLimitedPrecipitateModel = Logged
    original_floor = tp._check_critical_radius_floor

    def floor_check(estimates, floor_nm, gb):
        state["estimates"] = [list(map(float, item)) for item in estimates]
        if estimates and floor_nm:
            state["u"] = max(float(floor_nm) / item[3] if item[3] > 0 else float("inf") for item in estimates)
            state["rmin_nm"] = float(floor_nm)
        return original_floor(estimates, floor_nm, gb)

    tp._check_critical_radius_floor = floor_check

    meta = {
        "case": args.case, "composition": text, "variant": args.variant, "seed": seed,
        "nucleation": args.nucleation, "cap_s": args.cap, **case,
    }
    def dump(outcome: str, extra: dict | None = None) -> None:
        r = list(rows)
        cm = list(comps)
        arr = np.asarray(r, float) if r else np.zeros((0, len(SCALARS)))
        np.savez_compressed(out / f"{stem}.npz", scalars=arr, names=np.asarray(SCALARS),
                            comps=np.asarray(cm, float) if cm else np.zeros((0, 0)),
                            snapshots=np.asarray(list(snapshots), dtype=object))
        last = arr[-1] if len(arr) else None
        limiter = None
        if last is not None:
            lims = last[4:9]
            k = int(np.argmin(lims))
            limiter = LIMIT_NAMES[k] if lims[k] < last[3] else "рост dtScale"
        summary = {
            **meta, "outcome": outcome, "u": state.get("u"), "rmin_nm": state.get("rmin_nm"),
            "estimates [T K, Rcrit нм, Rnuc нм, r* до зажима нм]": state.get("estimates"),
            "steps": int(len(arr)), "t_model_s": float(last[1] + last[11]) if last is not None else None,
            "dt_last_s": float(last[11]) if last is not None else None,
            "limiter_last": limiter, "bins_last": int(last[12]) if last is not None else None,
            "volFrac_last": float(last[29]) if last is not None else None,
            "wall_solve_s": (time.perf_counter() - state["t0"]) if state["t0"] else None,
            "wall_total_s": time.perf_counter() - wall0,
            "peak_rss_gib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20,
            "solutes": [e for e in (state["model"].therm.elements[1:] if state["model"] is not None else []) if e != "VA"],
            **(extra or {}),
        }
        (out / f"{stem}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), "utf-8")

    stop = threading.Event()

    def watch() -> None:
        while not stop.wait(10.0):
            r = rows[-1] if rows else None
            wall = time.perf_counter() - wall0
            line = {"wall_s": round(wall, 1)}
            if r is not None:
                lims = r[4:9]
                k = min(range(5), key=lambda q: lims[q])
                line.update({"n": r[0], "t": r[1], "dt_taken": r[11], "limiter": LIMIT_NAMES[k] if lims[k] < r[3] else "рост",
                             "bins": r[12], "filled": r[15], "volFrac": r[29], "Rcrit": r[26], "Rnuc": r[27],
                             "nucRate": r[28]})
            with progress_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            if state["t0"] is not None and wall > args.cap:
                dump("потолок")
                print(f"CAP: {args.cap} с стены, шагов {len(rows)}", flush=True)
                os._exit(4)

    threading.Thread(target=watch, daemon=True).start()
    try:
        result = tp.run_precipitation(
            db=object(), database_path=ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
            database_label=RELEASE_DATABASE_LABELS["ni"], database_key="ni", balance="NI",
            composition_text=text, units=case["units"], matrix_phase=case["matrix_phase"],
            precipitate_phase=case["precipitate_phase"], schedule_mode="isothermal",
            temperature_c=case["temperature_c"], duration_h=case["duration_s"] / 3600.0, profile_text="",
            gamma=case["gamma"], matrix_vm=case["matrix_vm"], precip_vm=case["precip_vm"],
            nucleation_type=args.nucleation, bulk_n0=1e30, grain_size_um=100.0,
            dislocation_density=5e12, gb_energy=0.3, cmin_nm=case["cmin_nm"], cmax_nm=case["cmax_nm"],
            bins=case["bins"], input_provenance="SYNTHETIC_WAVE22V_BL33_NOT_MATERIAL_INPUT",
            input_confirmation=True,
        )
    except Exception as error:  # noqa: BLE001
        stop.set()
        dump("ошибка", {"error": f"{type(error).__name__}: {error}"})
        print(f"ERROR: {type(error).__name__}: {error}", flush=True)
        return 3
    stop.set()
    k = result.kinetics
    outcome = "остановка BL-35" if result.stop_note else "сошёлся"
    if state.get("stage_stop") is not None and not result.stop_note:
        outcome = "остановка по стадии"
    dump(outcome, {
        "rows": int(len(k)), "fraction_pct": float(k["Объёмная доля, %"].iloc[-1]),
        "radius_nm": float(k["Средний радиус, нм"].iloc[-1]),
        "density_m3": float(k["Плотность частиц, 1/м³"].iloc[-1]),
        "t_end_s": float(k["Время, с"].iloc[-1]),
        "quality_ok": bool((result.quality["Статус"] == "пройдена").all()),
        "stop_note": result.stop_note, "stop_diagnostics": {kk: str(v) for kk, v in result.stop_diagnostics.items()},
        "warnings": list(result.warnings), "stage_stop": state.get("stage_stop"),
    })
    print(json.dumps({"outcome": outcome, "rows": len(k), "u": state.get("u")}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
