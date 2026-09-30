#!/usr/bin/env python3
"""22-В, шаг 2 г: признак «расчёт не успевает» на рядах времени — чем разделить сошедшиеся и зависшие.

P(n) = (t_кон − t_n) / медиана шага за последние 50 шагов — прогноз оставшихся шагов. Для каждого прогона:
наибольший P, наибольшая длина серии подряд идущих шагов с P > 1e5 / 1e6 / 1e7, число шагов, мин. шаг / t_кон.
Ряды: bl33/*/*.npz этой волны и results/wave22_b/data/*.npz (model.toDict() 22-Б: умолчания ni/al/fe, 718, ячейки fe).
Пишет bl33/potolok.md.
"""
import glob
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results/wave22_v/bl33/potolok.md"


def series_22v(path):
    z = np.load(path, allow_pickle=True)
    a = z["scalars"]
    names = [str(n) for n in z["names"]]
    j = json.loads(Path(str(path)[:-4] + ".json").read_text("utf-8"))
    t = a[:, names.index("t")] + a[:, names.index("dt_taken")]
    return np.concatenate([[0.0], t]), j["duration_s"], j["outcome"]


def series_22b(path):
    z = np.load(path, allow_pickle=True)
    t = np.asarray(z["time"], float)
    return t, None, "22-Б"


def stats(t, T):
    dt = np.diff(t)
    dt = dt[dt > 0]
    tt = t[1:len(dt) + 1]
    T = T if T else float(t[-1])
    med = np.array([np.median(dt[max(0, i - 49):i + 1]) for i in range(len(dt))])
    P = (T - tt) / med
    res = {"шагов": len(dt), "t_кон": T, "t_посл": float(t[-1]), "мин шаг/T": float(dt.min() / T), "max P": float(P.max())}
    for thr in (1e5, 1e6, 1e7):
        run = best = 0
        for p in P:
            run = run + 1 if p > thr else 0
            best = max(best, run)
        res[f"серия P>{thr:.0e}"] = best
    return res


def main():
    rows = []
    for p in sorted(glob.glob(str(ROOT / "results/wave22_v/bl33/*/*_s[0-9].npz"))):
        t, T, outcome = series_22v(p)
        rows.append((Path(p).parent.name + "/" + Path(p).stem, outcome, stats(t, T)))
    for p in sorted(glob.glob(str(ROOT / "results/wave22_b/data/*.npz"))):
        t, T, outcome = series_22b(p)
        rows.append(("22-Б/" + Path(p).stem, "см. отчёт 22-Б", stats(t, T)))
    lines = ["| прогон | исход | шагов | t, с (последнее / конец) | мин. шаг / t_кон | max P | серия P>1e5 | P>1e6 | P>1e7 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, outcome, s in rows:
        lines.append(f"| {name} | {outcome} | {s['шагов']} | {s['t_посл']:.4g} / {s['t_кон']:.4g} | {s['мин шаг/T']:.2e} | "
                     f"{s['max P']:.2e} | {s['серия P>1e+05']} | {s['серия P>1e+06']} | {s['серия P>1e+07']} |")
    OUT.write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
