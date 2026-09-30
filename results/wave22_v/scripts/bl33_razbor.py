#!/usr/bin/env python3
"""22-В, шаг 2 б: разбор внутренних рядов BL-33 (npz из bl33_run.py).

Для каждого прогона: ход шага и пределов kawin, скорость зарождения, доля, число частиц, скорость
роста на границах класса зародыша, заселённые классы; на последних шагах — распределение и скорость
роста по классам. Пишет results/wave22_v/bl33/razbor.md и графики bl33/*.png.

    python -B bl33_razbor.py A5_k2_s0 C4_k2_s0 NI_k2_s0 A6_k2_s0 ...
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

W = Path(__file__).resolve().parents[1] / "bl33"
LIMITS = ["lim_psd", "lim_nuc", "lim_temp", "lim_rcrit", "lim_vol"]


def load(tag: str, sub: str = "a"):
    z = np.load(W / sub / f"{tag}.npz", allow_pickle=True)
    names = [str(n) for n in z["names"]]
    a = z["scalars"]
    col = {n: a[:, i] for i, n in enumerate(names)}
    meta = json.loads((W / sub / f"{tag}.json").read_text("utf-8"))
    return col, z["comps"], list(z["snapshots"]), meta


def limiter_names(col) -> np.ndarray:
    lims = np.vstack([col[k] for k in LIMITS]).T
    k = np.argmin(lims, axis=1)
    names = np.array([n[4:] for n in LIMITS])[k]
    grow = lims[np.arange(len(k)), k] >= col["dt_max"]
    names = names.astype(object)
    names[grow] = "рост"
    capped = col["dt_after_k"] < col["dt_kawin"] * (1 - 1e-12)
    names[capped] = "K"
    return names


def main() -> int:
    tags = sys.argv[1:]
    sub = "a"
    if tags and tags[0].startswith("--sub="):
        sub = tags.pop(0).split("=", 1)[1]
    lines = [f"# BL-33: разбор рядов ({sub})", ""]
    fig, axes = plt.subplots(3, 2, figsize=(13, 11))
    for tag in tags:
        col, comps, snaps, meta = load(tag, sub)
        t = col["t"]
        lim = limiter_names(col)
        n = len(t)
        # скорость набора доли зарождением против фактической
        vol_nuc = (4 * np.pi / 3) * col["nucRate"] * col["Rnuc"] ** 3
        dfv = np.gradient(col["volFrac"], t) if n > 2 else np.zeros(n)
        lines.append(f"## {tag}: {meta['outcome']}, u = {meta.get('u')}, шагов {n}, t = {meta.get('t_model_s')} с")
        lines.append("")
        uniq, counts = np.unique(lim, return_counts=True)
        lines.append("Сработавший предел (шагов): " + ", ".join(f"{u} {c}" for u, c in zip(uniq, counts)))
        lines.append("")
        lines.append("| шаг | t, с | шаг, с | предел | J, 1/(м³·с) | (4π/3)·J·Rnuc³, 1/с | dfv/dt, 1/с | fv | N, 1/м³ | G на нижней/верхней границе класса зародыша, м/с | класс зародыша | классов | заселено | Rnuc, нм |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        picks = sorted(set([0, 1, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
                           + list(range(max(0, n - 5), n))))
        for i in picks:
            if i >= n:
                continue
            lines.append(
                f"| {int(col['n'][i])} | {t[i]:.6g} | {col['dt_taken'][i]:.3g} | {lim[i]} | {col['nucRate'][i]:.3g} | "
                f"{vol_nuc[i]:.3g} | {dfv[i]:.3g} | {col['volFrac'][i]:.4g} | {col['density'][i]:.3g} | "
                f"{col['g_nuc_lo'][i]:.3g} / {col['g_nuc_hi'][i]:.3g} | {int(col['n_rad'][i])} | {int(col['bins'][i])} | "
                f"{int(col['filled'][i])} | {col['Rnuc'][i]*1e9:.4g} |"
            )
        lines.append("")
        if comps.size:
            k = comps.shape[1] // 3
            solutes = meta.get("solutes") or [f"x{j}" for j in range(k)]
            lines.append("Состав матрицы / xEqAlpha / xEqBeta на первом и последнем шаге (мольн. доли):")
            lines.append("")
            lines.append("| элемент | x0 | x (конец) | xEqAlpha (конец) | xEqBeta (конец) |")
            lines.append("|---|---|---|---|---|")
            for j in range(k):
                lines.append(f"| {solutes[j] if j < len(solutes) else j} | {comps[0, j]:.5g} | {comps[-1, j]:.5g} | "
                             f"{comps[-1, k + j]:.5g} | {comps[-1, 2 * k + j]:.5g} |")
            lines.append("")
        if snaps:
            s = snaps[-1]
            b, p, g = s["bounds"], s["psd"], s["growth"]
            lines.append(f"Последний снимок (шаг {s['n']}): заселённые классы, R (левая граница) / N / G(левая граница):")
            lines.append("")
            lines.append("| класс | R, нм | N, 1/м³ | G, м/с |")
            lines.append("|---|---|---|---|")
            for j in np.nonzero(p > 0)[0][:40]:
                lines.append(f"| {j} | {b[j]*1e9:.4g} | {p[j]:.3g} | {g[j]:.3g} |")
            lines.append("")
        label = tag
        axes[0, 0].loglog(t, col["dt_taken"], label=label)
        axes[0, 1].loglog(t, np.maximum(col["nucRate"], 1e-3), label=label)
        axes[1, 0].semilogx(t, 100 * col["volFrac"], label=label)
        axes[1, 1].loglog(t, np.maximum(np.abs(col["g_nuc_lo"]), 1e-16), label=label)
        axes[2, 0].semilogx(t, col["filled"], label=label)
        axes[2, 1].loglog(t, np.maximum(vol_nuc, 1e-12), label=label)
    for ax, title in zip(axes.ravel(), ["шаг решателя, с", "скорость зарождения J, 1/(м³·с)", "доля, %",
                                        "|G| на нижней границе класса зародыша, м/с", "заселённых классов",
                                        "(4π/3)·J·Rnuc³ — прирост доли от зарождения, 1/с"]):
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("модельное время, с")
        ax.grid(alpha=0.3)
    axes[0, 0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(W / f"razbor_{sub}.png", dpi=110)
    (W / f"razbor_{sub}.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines[:400]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
