#!/usr/bin/env python3
"""22-В, шаг 1: график BL-28 — шаг решателя и доля по ряду кинетики (CSV из bl28_run.py).

Пишет results/wave22_v/bl28/bl28_shag_i_dolya.png и таблицу bl28/itog_progonov.md (все JSON bl28).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

B = Path(__file__).resolve().parents[1] / "bl28"


def series(stem: str):
    rows = list(csv.DictReader((B / f"{stem}_kinetics.csv").open(encoding="utf-8")))
    t = [float(r["Время, с"]) for r in rows]
    f = [float(r["Объёмная доля, %"]) for r in rows]
    dt = [b - a for a, b in zip(t, t[1:])]
    return t, f, dt


def main() -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.5))
    for stem, label in (("ni_1c47789_s0", "ni, код 1c47789 (97 строк)"), ("ni_724da6e_s0", "ni, 724da6e (97)"),
                        ("ni_6ee93bf_s0", "ni, 6ee93bf (246)"), ("ni_HEAD_s0", "ni, 45eb7e0 (246)"),
                        ("al_HEAD_s0", "al, 45eb7e0 (97)")):
        t, f, dt = series(stem)
        a1.semilogy(t[1:], dt, label=label, lw=1.2)
        a2.plot(t, f, label=label, lw=1.2)
    a1.set_xlabel("модельное время, с")
    a1.set_ylabel("шаг решателя, с")
    a1.set_title("Шаг: без событий — 0,01·1,001ᵏ (96 шагов)", fontsize=10)
    a2.set_xlabel("модельное время, с")
    a2.set_ylabel("объёмная доля выделения, %")
    a2.set_title("Доля γ′ (ni) и θ (al) за 1 с", fontsize=10)
    for ax in (a1, a2):
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(B / "bl28_shag_i_dolya.png", dpi=110)

    lines = ["| база | коммит | зерно | строк | доля в конце, % | R, нм | частиц, 1/м³ | первый шаг, с | мин. шаг, с | стена, с |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for p in sorted(B.glob("*_s[0-9].json")):
        d = json.loads(p.read_text("utf-8"))
        lines.append(f"| {d['db']} | {d['tag']} | {d['seed']} | {d['rows']} | {d['fraction_pct']:.6g} | {d['radius_nm']:.4g} | "
                     f"{d['density_m3']:.4g} | {d['dt_first_s']:.5g} | {d['dt_min_s']:.4g} | {d['wall_s']:.1f} |")
    (B / "itog_progonov.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
