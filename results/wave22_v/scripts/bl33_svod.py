#!/usr/bin/env python3
"""22-В, шаг 2: сводка прогонов BL-33 (все JSON bl33/a и bl33/v) — таблица и граница по u.

Пишет results/wave22_v/bl33/svod.md и bl33/granica_u.png.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

B = Path(__file__).resolve().parents[1] / "bl33"


def main() -> None:
    rows = []
    for sub in ("a", "v"):
        for p in sorted((B / sub).glob("*_s[0-9].json")):
            d = json.loads(p.read_text("utf-8"))
            z = np.load(p.with_suffix(".npz"), allow_pickle=True)
            a = z["scalars"]
            names = [str(n) for n in z["names"]]
            dt = a[:, names.index("dt_taken")] if len(a) else np.array([np.nan])
            j = a[:, names.index("nucRate")] if len(a) else np.array([np.nan])
            rows.append({
                "sub": sub, "file": p.stem, "case": d["case"], "variant": d["variant"], "seed": d["seed"],
                "gamma": d["gamma"], "u": d.get("u"), "outcome": d["outcome"], "steps": d["steps"],
                "t": d.get("t_model_s"), "dur": d.get("duration_s"), "dt_min": float(np.nanmin(dt)),
                "dt_last": d.get("dt_last_s"), "J_max": float(np.nanmax(j)), "fv": d.get("volFrac_last"),
                "wall": d.get("wall_total_s"), "lim": d.get("limiter_last"),
                "stop": (d.get("stop_note") or "")[:60],
            })
    lines = ["| серия | случай | вариант | зерно | γ | u | исход | шагов | t, с (из) | мин. шаг, с | последний шаг, с | max J | доля | стена, с | предел в конце |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["sub"], r["case"], r["u"] or 0, r["variant"], r["seed"])):
        lines.append(
            f"| {r['sub']} | {r['case']} | {r['variant']} | {r['seed']} | {r['gamma']:.5g} | {r['u']:.3f} | {r['outcome']} | "
            f"{r['steps']} | {r['t']:.4g} ({r['dur']:g}) | {r['dt_min']:.3g} | {r['dt_last']:.3g} | {r['J_max']:.3g} | "
            f"{100 * (r['fv'] or 0):.3g} % | {r['wall']:.0f} | {r['lim']} |"
        )
    (B / "svod.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))

    fig, ax = plt.subplots(figsize=(9, 4.5))
    marks = {"сошёлся": ("o", "tab:green"), "потолок": ("x", "tab:red"), "остановка BL-35": ("s", "tab:orange"),
             "ошибка": ("^", "k")}
    ys = {"A4": 0, "NI": 1, "A5": 2, "C4": 3, "A6": 4, "A7": 5, "B5": 6}
    seen = set()
    for r in rows:
        if r["variant"] != "k2" or r["u"] is None:
            continue
        m, c = marks.get(r["outcome"], ("?", "gray"))
        y = ys.get(r["case"], 7) + 0.12 * (int(r["seed"]) - 1)
        ax.scatter(r["u"], y, marker=m, color=c, label=r["outcome"] if r["outcome"] not in seen else None)
        seen.add(r["outcome"])
    ax.axvline(1.5, ls="--", color="gray", lw=1)
    ax.text(1.51, 5.6, "порог BL-32 = 1,5", fontsize=8, color="gray")
    ax.set_yticks(list(ys.values()))
    ax.set_yticklabels(list(ys.keys()))
    ax.set_xlabel("u = Rmin / r* (до зажима), лестница через γ")
    ax.set_title("BL-33: исход расчёта (K = 2, потолок 10 мин стены), зёрна 0–2", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(B / "granica_u.png", dpi=110)


if __name__ == "__main__":
    main()
