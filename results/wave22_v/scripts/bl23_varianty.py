#!/usr/bin/env python3
"""22-В, шаг 3 в: варианты BL-23 (base / k2 / fine) по четырём случаям 12-1 — уходит ли «замирание», меняется ли доля.

По bl23/runs/*/ryady.npz и itog.json. Для каждого прогона: исход, шагов, стена, t конца, доля (мольн. % по узлу
сценария, у снятых по потолку — объёмная по шагу), N и R у 100 ч и в конце, спад N и рост R, начало огрубления
(первое t после максимума N, где N < 0,9·max), первый численный скачок N (ΔN > 100·J·dt, > 1 % N и > 10¹⁰ 1/м³),
max N/∫J dt (как bl23_priznak.py). Пишет bl23/varianty.md и bl23/varianty.png.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

B = Path(__file__).resolve().parents[1] / "bl23"
CASES = [("obyom", "0.1", "объём, γ 0,100 (аномалия)"), ("obyom", "0.125", "объём, γ 0,125 (сосед)"),
         ("granicy", "0.125", "границы, γ 0,125 (аномалия)"), ("granicy", "0.15", "границы, γ 0,150 (сосед)")]
VARIANTS = ("base", "k2", "fine")


def at(t, y, th):
    i = int(np.searchsorted(t, th * 3600.0))
    return float(y[min(i, len(y) - 1)]) if len(y) else float("nan")


def metrics(run: Path) -> dict | None:
    if not (run / "itog.json").is_file():
        return None
    d = json.loads((run / "itog.json").read_text("utf-8"))
    z = np.load(run / "ryady.npz", allow_pickle=True)
    a = z["scalars"]
    nm = [str(x) for x in z["names"]]
    c = lambda k: a[:, nm.index(k)]  # noqa: E731
    t, N, R, J, fv = c("t"), c("density"), c("Ravg"), c("nucRate"), c("volFrac")
    dt = np.diff(t)
    dN = np.diff(N)
    nuc = np.maximum(J[1:], J[:-1]) * dt
    jump = np.nonzero((dN > 100 * np.maximum(nuc, 1.0)) & (dN > 1e10) & (dN > 0.01 * N[:-1]))[0]
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (J[1:] + J[:-1]) * dt)])
    mask = N > 1e6
    ratio = float(np.max(N[mask] / np.maximum(cum[mask], 1.0))) if mask.any() else 0.0
    imax = int(np.argmax(N))
    after = np.nonzero(N[imax:] < 0.9 * N[imax])[0]
    onset = float(t[imax + after[0]] / 3600) if len(after) else None
    end_h = float(t[-1] / 3600)
    ok = d["outcome"] == "сошёлся"
    return {
        "run": run.name, "variant": d["variant"], "seed": str(d["seed"]), "outcome": d["outcome"], "steps": d["steps"],
        "wall": d["wall_s"], "t_end_h": end_h,
        "frac": d.get("fraction_mol_pct_end") if ok else 100 * float(fv[-1]), "frac_kind": "мольн." if ok else "об.",
        "N100": at(t, N, 100), "N_end": float(N[-1]), "R100": at(t, R, 100) * 1e9, "R_end": float(R[-1]) * 1e9,
        "Nmax": float(N[imax]), "t_Nmax_h": float(t[imax] / 3600), "onset_h": onset,
        "jump_h": float(t[jump[0]] / 3600) if len(jump) else None, "jumps": int(len(jump)), "ratio": ratio,
        "series": (t / 3600, N, R * 1e9),
    }


def main() -> None:
    lines = ["# BL-23 в: варианты (base — сценарий 12-1 как есть; k2 — предел роста шага K = 2, как в программе; "
             "fine — сетка PBM вдвое мельче)", "",
             "| случай | вариант | зерно | исход | шагов | стена, с | t конца, ч | доля в конце, % | N(100 ч) | N(конец) | спад N | "
             "R(100 ч), нм | R(конец), нм | рост R | max N (при t, ч) | огрубление с, ч | первый численный скачок N, ч (шагов) | max N/∫J dt |",
             "|" + "---|" * 18]
    got: dict[tuple[str, str], list[dict]] = {}
    for site, g, label in CASES:
        for v in VARIANTS:
            for run in sorted(B.glob(f"runs/T700_{site}_g{g}_{v}_s[0-9]")):
                m = metrics(run)
                if m is None:
                    continue
                got.setdefault((site, g), []).append(m)
                onset = "—" if m["onset_h"] is None else f"{m['onset_h']:.3g}"
                jump = "нет" if m["jump_h"] is None else f"{m['jump_h']:.4g} ({m['jumps']})"
                lines.append(
                    f"| {label} | {v} | {m['seed']} | {m['outcome']} | {m['steps']} | {m['wall']:.0f} | {m['t_end_h']:.6g} | "
                    f"{m['frac']:.4f} ({m['frac_kind']}) | {m['N100']:.3g} | {m['N_end']:.3g} | {m['N100'] / m['N_end']:.3g} | "
                    f"{m['R100']:.3g} | {m['R_end']:.4g} | {m['R_end'] / m['R100']:.3g} | {m['Nmax']:.3g} ({m['t_Nmax_h']:.3g}) | "
                    f"{onset} | {jump} | {m['ratio']:.3g} |")
    (B / "varianty.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))
    fig, axes = plt.subplots(2, 4, figsize=(16, 7), sharex=True)
    colors = {"base": "tab:blue", "k2": "tab:red", "fine": "tab:green"}
    for j, (site, g, label) in enumerate(CASES):
        for m in got.get((site, g), []):
            th, N, R = m["series"]
            ls = "-" if m["seed"] == "0" else (":" if m["seed"] == "1" else "--")
            lab = f"{m['variant']} з{m['seed']}"
            axes[0, j].loglog(np.maximum(th, 1e-3), np.maximum(N, 1.0), ls=ls, color=colors[m["variant"]], lw=1, label=lab)
            axes[1, j].loglog(np.maximum(th, 1e-3), np.maximum(R, 1e-2), ls=ls, color=colors[m["variant"]], lw=1, label=lab)
        axes[0, j].set_title(label, fontsize=9)
        axes[0, j].set_ylim(1e8, 1e24)
        axes[1, j].set_xlabel("t, ч")
        axes[0, j].grid(alpha=0.3)
        axes[1, j].grid(alpha=0.3)
        axes[0, j].legend(fontsize=6)
    axes[0, 0].set_ylabel("N, 1/м³")
    axes[1, 0].set_ylabel("R̄, нм")
    fig.suptitle("BL-23: 700 °C, 12-1 — base / K = 2 / сетка ×2; сплошная — зерно 0, точки — 1, штрих — 2", fontsize=10)
    fig.tight_layout()
    fig.savefig(B / "varianty.png", dpi=100)


if __name__ == "__main__":
    main()
