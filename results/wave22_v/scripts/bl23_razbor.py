#!/usr/bin/env python3
"""22-В, шаг 3: разбор прогонов BL-23 (results/wave22_v/bl23/runs/*/).

* Сверка с «Д-1» 12-1: спад числа выделений и рост среднего радиуса между 100 ч и 87 600 ч (по узлам
  сценария; 100 ч — ближайший узел и точное значение по рядам решателя), размах Rcrit/R с 100 ч;
  то же по кэшу 12-1 (results/hn62m_wave12/cache/k1_points.jsonl) для того же случая.
* Разбор во времени по рядам: классы сетки и заселённость, R и Rcrit, скорость зарождения, шаг и
  сработавший предел; графики bl23/<прогон>.png и общий bl23/sravnenie.png; таблица bl23/razbor.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
B = ROOT / "results" / "wave22_v" / "bl23"
REF = ROOT / "results" / "hn62m_wave12" / "cache" / "k1_points.jsonl"
LIM = ["lim_psd", "lim_nuc", "lim_temp", "lim_rcrit", "lim_vol"]
H = 3600.0


def ref_rows(T: float, gamma: float, site_label: str) -> list[dict]:
    rows = []
    for line in REF.read_text("utf-8").splitlines():
        r = json.loads(line)
        if r.get("kind") == "done":
            continue
        rows.append((r["key"], r["payload"]))
    # ключ в кэше — хеш; случай узнаётся по записи-закрытию (done)
    done = {}
    for line in REF.read_text("utf-8").splitlines():
        r = json.loads(line)
        if r.get("kind") == "done":
            done[r["key"]] = r["payload"]
    keys = [k for k, p in done.items() if abs(p["T, °C"] - T) < 1e-9 and abs(p["межфазная энергия, Дж/м²"] - gamma) < 1e-12
            and p["места зарождения"] == site_label]
    if not keys:
        return []
    latest: dict[float, dict] = {}
    for k, p in rows:
        if k == keys[0]:
            latest[round(float(p["узел, ч"]), 12)] = p
    return [latest[n] for n in sorted(latest)]


def metrics(nodes: list[dict]) -> dict:
    t = np.array([r["t, ч"] for r in nodes])
    N = np.array([r["число выделений, 1/м³"] for r in nodes])
    R = np.array([r["средний радиус, нм"] for r in nodes])
    Rc = np.array([r["критический радиус, нм"] for r in nodes])
    i100 = int(np.argmin(np.abs(np.log(np.maximum(t, 1e-12)) - np.log(100.0))))
    late = t >= t[i100] - 1e-9
    ratio = np.where(R > 0, Rc / np.maximum(R, 1e-300), np.nan)[late]
    return {"t_100": float(t[i100]), "N_100": float(N[i100]), "N_end": float(N[-1]), "R_100": float(R[i100]),
            "R_end": float(R[-1]), "spad": float(N[i100] / N[-1]) if N[-1] > 0 else None,
            "rost": float(R[-1] / R[i100]) if R[i100] > 0 else None,
            "Rc_R_min": float(np.nanmin(ratio)), "Rc_R_max": float(np.nanmax(ratio)),
            "fraction_end": float(nodes[-1]["мольная доля P-фазы, %"])}


def main() -> None:
    runs = sorted(p for p in (B / "runs").glob("*") if (p / "itog.json").is_file())
    lines = ["# BL-23: разбор прогонов", "",
             "| прогон | исход | шагов | t, ч | стена, с | доля за 87 600 ч, мольн. % | N(≈100 ч) | N(87 600 ч) | спад | рост R | Rcrit/R с 100 ч (мин…макс) | 12-1: спад / рост / Rcrit/R |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    fig_all, ax_all = plt.subplots(2, 2, figsize=(13, 9))
    for run in runs:
        it = json.loads((run / "itog.json").read_text("utf-8"))
        nodes_path = run / "uzly.json"
        m = metrics(json.loads(nodes_path.read_text("utf-8"))) if nodes_path.is_file() else None
        label = "объём зерна" if it["site"] == "BULK" else "границы зёрен"
        ref = ref_rows(float(it["T"]), float(it["gamma"]), label)
        mr = metrics(ref) if ref else None
        if m:
            lines.append(
                f"| {run.name} | {it['outcome']} | {it['steps']} | {it['t_model_h']:.6g} | {it['wall_s']:.0f} | "
                f"{m['fraction_end']:.4f} | {m['N_100']:.3g} (узел {m['t_100']:.4g} ч) | {m['N_end']:.3g} | {m['spad']:.3g} | "
                f"{m['rost']:.3g} | {m['Rc_R_min']:.3g}…{m['Rc_R_max']:.3g} | "
                + (f"{mr['spad']:.3g} / {mr['rost']:.3g} / {mr['Rc_R_min']:.3g}…{mr['Rc_R_max']:.3g} (доля {mr['fraction_end']:.4f})" if mr else "—")
                + " |")
        else:
            lines.append(f"| {run.name} | {it['outcome']} | {it['steps']} | {it.get('t_model_h')} | {it['wall_s']:.0f} | — | — | — | — | — | — | — |")
        z = np.load(run / "ryady.npz", allow_pickle=True)
        names = [str(n) for n in z["names"]]
        a = z["scalars"]
        if not len(a):
            continue
        c = {n: a[:, i] for i, n in enumerate(names)}
        t = c["t"] / H
        lims = np.vstack([c[k] for k in LIM]).T
        k = np.argmin(lims, axis=1)
        grow = lims[np.arange(len(k)), k] >= c["dt_max"]
        fig, ax = plt.subplots(3, 2, figsize=(13, 11))
        ax[0, 0].loglog(t, c["density"], label="N")
        ax[0, 0].set_title("число выделений, 1/м³")
        ax[0, 1].loglog(t, c["Ravg"] * 1e9, label="R ср.")
        ax[0, 1].loglog(t, np.maximum(c["Rcrit"] * 1e9, 1e-3), label="Rcrit", lw=0.8)
        ax[0, 1].set_title("R и Rcrit, нм")
        ax[0, 1].legend(fontsize=8)
        ax[1, 0].semilogx(t, c["bins"], label="классов")
        ax[1, 0].semilogx(t, c["filled"], label="заселено > 0")
        ax[1, 0].semilogx(t, c["filled_gt1"], label="заселено > 1", lw=0.8)
        ax[1, 0].set_title("сетка PBM")
        ax[1, 0].legend(fontsize=8)
        ax[1, 1].loglog(t, c["dt_after_k"], lw=0.8)
        ax[1, 1].set_title("шаг решателя, с")
        for q, name in enumerate(["psd", "nuc", "temp", "rcrit", "vol"]):
            sel = (k == q) & ~grow
            ax[2, 0].scatter(t[sel], np.full(sel.sum(), q), s=2, label=name)
        ax[2, 0].scatter(t[grow], np.full(grow.sum(), 5), s=2, label="рост")
        ax[2, 0].set_xscale("log")
        ax[2, 0].set_yticks(range(6))
        ax[2, 0].set_yticklabels(["PSD", "зарожд.", "T", "Rcrit", "объём", "рост 0,1 %"])
        ax[2, 0].set_title("сработавший предел шага")
        ax[2, 1].loglog(t, np.maximum(c["nucRate"], 1e-30))
        ax[2, 1].set_title("скорость зарождения, 1/(м³·с)")
        for q in ax.ravel():
            q.set_xlabel("t, ч")
            q.grid(alpha=0.3)
        fig.suptitle(run.name)
        fig.tight_layout()
        fig.savefig(B / f"{run.name}.png", dpi=100)
        plt.close(fig)
        ax_all[0, 0].loglog(t, c["density"], label=run.name, lw=1)
        ax_all[0, 1].loglog(t, c["Ravg"] * 1e9, label=run.name, lw=1)
        ax_all[1, 0].semilogx(t, c["filled"], label=run.name, lw=1)
        ax_all[1, 1].loglog(t, np.maximum(c["Rcrit"] / np.maximum(c["Ravg"], 1e-30), 1e-3), label=run.name, lw=0.8)
        # таблица по времени: где замирает
        lines_t = [f"### {run.name}", "", "| t, ч | шаг, с | предел | классов | заселено>0 | >1 | первый/последний заселённый | max PSD в классе | N | R, нм | Rcrit, нм | J |",
                   "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        marks = [1e-3, 1e-2, 0.1, 1, 10, 29, 50, 100, 200, 500, 1000, 3000, 1e4, 3e4, 87600]
        lname = np.array(["PSD", "зарожд.", "T", "Rcrit", "объём"], dtype=object)[k]
        lname[grow] = "рост"
        for mk in marks:
            i = int(np.argmin(np.abs(t - mk)))
            lines_t.append(f"| {t[i]:.4g} | {c['dt_after_k'][i]:.3g} | {lname[i]} | {int(c['bins'][i])} | {int(c['filled'][i])} | "
                           f"{int(c['filled_gt1'][i])} | {int(c['first_filled'][i])}/{int(c['last_filled'][i])} | {int(c['psd_argmax'][i])} | "
                           f"{c['density'][i]:.3g} | {c['Ravg'][i]*1e9:.4g} | {c['Rcrit'][i]*1e9:.4g} | {c['nucRate'][i]:.3g} |")
        lines_t.append("")
        (B / f"{run.name}_po_vremeni.md").write_text("\n".join(lines_t) + "\n", "utf-8")
    for q, title in zip(ax_all.ravel(), ["число выделений, 1/м³", "средний радиус, нм", "заселённых классов", "Rcrit / R"]):
        q.set_title(title)
        q.set_xlabel("t, ч")
        q.grid(alpha=0.3)
    ax_all[0, 0].legend(fontsize=6)
    fig_all.tight_layout()
    fig_all.savefig(B / "sravnenie.png", dpi=100)
    (B / "razbor.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
