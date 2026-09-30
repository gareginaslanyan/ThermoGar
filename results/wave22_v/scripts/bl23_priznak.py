#!/usr/bin/env python3
"""22-В, шаг 3 г: признак «частиц больше, чем зародилось» — max_t N(t) / ∫₀ᵗ J dt' по рядам.

Ряды: bl23/runs/*/ryady.npz (сценарий 12-1), bl23/app/*.npz (штатный run_precipitation), bl33/*/*.npz, данные 22-Б
(results/wave22_b/data/*.npz: time, nucRate, precipitateDensity). Интеграл — трапециями по записанным шагам.
Пишет bl23/priznak.md.
"""
import glob
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results/wave22_v/bl23/priznak.md"


def ratio(t, J, N):
    t, J, N = map(lambda v: np.asarray(v, float), (t, J, N))
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (J[1:] + J[:-1]) * np.diff(t))])
    mask = N > 1e6
    if not mask.any():
        return 0.0, None
    r = N[mask] / np.maximum(cum[mask], 1.0)
    k = int(np.argmax(r))
    return float(r[k]), float(t[mask][k])


def main():
    rows = []
    for p in sorted(glob.glob(str(ROOT / "results/wave22_v/bl23/runs/*/ryady.npz"))):
        z = np.load(p, allow_pickle=True)
        a = z["scalars"]
        n = [str(x) for x in z["names"]]
        rows.append(("22-В/12-1 " + Path(p).parent.name, *ratio(a[:, n.index("t")], a[:, n.index("nucRate")], a[:, n.index("density")])))
    for p in sorted(glob.glob(str(ROOT / "results/wave22_v/bl23/app/*.npz"))):
        a = np.load(p)["rows"]
        rows.append(("22-В/приложение " + Path(p).stem, *ratio(a[:, 1], a[:, 9], a[:, 8])))
    for p in sorted(glob.glob(str(ROOT / "results/wave22_v/bl33/*/*_s[0-9].npz"))):
        z = np.load(p, allow_pickle=True)
        a = z["scalars"]
        n = [str(x) for x in z["names"]]
        rows.append(("22-В/BL-33 " + Path(p).stem, *ratio(a[:, n.index("t")], a[:, n.index("nucRate")], a[:, n.index("density")])))
    for p in sorted(glob.glob(str(ROOT / "results/wave22_b/data/*.npz"))):
        z = np.load(p, allow_pickle=True)
        rows.append(("22-Б " + Path(p).stem, *ratio(z["time"], np.asarray(z["nucRate"])[:, 0], np.asarray(z["precipitateDensity"])[:, 0])))
    lines = ["| ряд | max N / ∫J dt | при t, с |", "|---|---|---|"]
    for name, r, t in rows:
        lines.append(f"| {name} | {r:.3g} | {'' if t is None else f'{t:.4g}'} |")
    OUT.write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
