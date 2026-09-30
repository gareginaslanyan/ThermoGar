#!/usr/bin/env python3
"""22-В, шаг 3 б: ширина распределения по размерам во времени (снимки PSD из ryady.npz bl23_run.py).

Для каждого снимка: N, R̄ (по числу), σ/R̄, доля частиц в пределах ±10 % от R̄, число классов, в которых сидит
99 % частиц, и Rcrit/R̄ (Rcrit из рядов на том же шаге). Пишет bl23/shirina.md.
"""
import sys
from pathlib import Path

import numpy as np

B = Path(__file__).resolve().parents[1] / "bl23"


def main():
    lines = ["| прогон | t, ч | классов | N, 1/м³ | R̄, нм | σ/R̄ | доля N в ±10 % R̄ | классов на 99 % N | Rcrit/R̄ |",
             "|---|---|---|---|---|---|---|---|---|"]
    for run in sorted((B / "runs").glob("*")):
        f = run / "ryady.npz"
        if not f.is_file():
            continue
        z = np.load(f, allow_pickle=True)
        a = z["scalars"]
        names = [str(n) for n in z["names"]]
        steps = a[:, names.index("n")].astype(int)
        rc = dict(zip(steps, a[:, names.index("Rcrit")]))
        snaps = sorted(list(z["snapshots"]), key=lambda s: s["n"])
        want = [1, 5, 10, 30, 100, 300, 1000, 3000, 1e4, 3e4, 8.7e4]
        picked = []
        for w in want:
            s = min(snaps, key=lambda s: abs(np.log(max(s["t"] / 3600, 1e-9)) - np.log(w)))
            if s["n"] not in [p["n"] for p in picked]:
                picked.append(s)
        for s in picked:
            b, p = np.asarray(s["bounds"]), np.asarray(s["psd"])
            r = 0.5 * (b[1:] + b[:-1])
            N = p.sum()
            if N <= 0:
                continue
            m = (p * r).sum() / N
            sd = np.sqrt((p * (r - m) ** 2).sum() / N)
            near = p[np.abs(r - m) <= 0.1 * m].sum() / N
            order = np.argsort(p)[::-1]
            k99 = int(np.searchsorted(np.cumsum(p[order]) / N, 0.99) + 1)
            lines.append(f"| {run.name} | {s['t'] / 3600:.4g} | {len(p)} | {N:.3g} | {m * 1e9:.4g} | {sd / m:.3f} | "
                         f"{near:.3f} | {k99} | {rc.get(s['n'], float('nan')) / m:.3f} |")
    (B / "shirina.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
