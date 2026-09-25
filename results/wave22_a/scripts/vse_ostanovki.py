#!/usr/bin/env python3
"""22-А2, шаг 3: все остановки BL-35 по сохранённым NPZ — числа для признака.

Для каждого прогона с остановкой: наибольшая невязка баланса C до шага
остановки (в долях x0), C матрицы на предыдущем шаге против xEqAlpha kawin,
C в выделениях на шаге остановки (в долях x0), рост шага на нём (dt/dt_пред).

    python -B vse_ostanovki.py > ../logs/a2_s3_vse_ostanovki.txt
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    rows = []
    for path in sorted(DATA.glob("*.json")):
        summary = json.loads(path.read_text(encoding="utf-8"))
        npz = DATA / f"{path.stem}.npz"
        if not isinstance(summary, dict) or not summary.get("stop") or not npz.exists():
            continue
        with np.load(npz) as archive:
            d = {name: archive[name] for name in archive.files}
        x = d["composition"][:, 0]
        fv = np.sum(d["volFrac"], axis=1)
        fconc = np.sum(d["fconc"], axis=1)[:, 0]
        x0 = x[0]
        residual = x0 - ((1 - fv) * x + fconc)
        last = len(x) - 1
        t = d["time"]
        x_eq = d["xEqAlpha"][last - 1, 0, 0]
        rows.append({
            "tag": path.stem,
            "res_before": float(np.max(np.abs(residual[:last])) / x0),
            "x_prev_over_eq": float(x[last - 1] / x_eq) if x_eq > 0 else float("nan"),
            "fconc_stop": float(fconc[last] / x0),
            "res_stop": float(residual[last] / x0),
            "dt_ratio": float((t[last] - t[last - 1]) / (t[last - 1] - t[last - 2])),
            "fraction_100": bool(fv[last] >= 1 - 1e-9),
        })
    print("тег; невязка до остановки / x0; x_C(пред) / xEqAlpha; C в выделениях / x0 на остановке; невязка на остановке / x0; dt/dt_пред; доля 100 %")
    for r in rows:
        print(f"{r['tag']}; {r['res_before']:.2e}; {r['x_prev_over_eq']:.3f}; {r['fconc_stop']:.4f}; {r['res_stop']:+.4f}; {r['dt_ratio']:.1f}; {r['fraction_100']}")
    if rows:
        res = [r["res_before"] for r in rows]
        ratio = [r["x_prev_over_eq"] for r in rows]
        fconc = [r["fconc_stop"] for r in rows]
        dts = [r["dt_ratio"] for r in rows]
        print(f"\nостановок: {len(rows)}")
        print(f"невязка до шага остановки / x0: max {max(res):.2e}")
        print(f"x_C на предыдущем шаге / xEqAlpha: {min(ratio):.3f} … {max(ratio):.3f}")
        print(f"C в выделениях на шаге остановки / x0: {min(fconc):.4f} … {max(fconc):.4f}")
        print(f"рост шага на шаге остановки: ×{min(dts):.1f} … ×{max(dts):.1f}")
        print(f"с долей 100 % (BL-22): {sum(r['fraction_100'] for r in rows)}")


if __name__ == "__main__":
    main()
