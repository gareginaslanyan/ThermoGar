#!/usr/bin/env python3
"""22-В, шаг 3 г: график путей приложения BL-23 — N, доля и число классов во времени (bl23/app/*.npz).

Пишет results/wave22_v/bl23/app_grafik.png.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

B = Path(__file__).resolve().parents[1] / "bl23"


def main():
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.5))
    for p in sorted((B / "app").glob("*.npz")):
        a = np.load(p)["rows"]
        t = a[:, 1] / 3600
        lab = p.stem.replace("app_T700_", "").replace("_500h_s0", "")
        ax[0].loglog(t, np.maximum(a[:, 8], 1.0), label=lab, lw=1)
        ax[1].semilogx(t, 100 * a[:, 12], label=lab, lw=1)
        ax[2].semilogx(t, a[:, 3], label=lab, lw=1)
    for q, title in zip(ax, ["число частиц N, 1/м³", "объёмная доля, %", "классов сетки PBM"]):
        q.set_title(title, fontsize=10)
        q.set_xlabel("t, ч")
        q.grid(alpha=0.3)
        q.axvline(200, ls=":", color="gray", lw=0.8)
    ax[0].legend(fontsize=7)
    fig.suptitle("BL-23: штатный run_precipitation (K = 2, сетка раздела), 700 °C, P-фаза в ЭК199-ВИ", fontsize=10)
    fig.tight_layout()
    fig.savefig(B / "app_grafik.png", dpi=110)


if __name__ == "__main__":
    main()
