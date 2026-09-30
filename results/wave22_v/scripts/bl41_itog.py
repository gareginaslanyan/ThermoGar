#!/usr/bin/env python3
"""22-В, шаг 4 в: сводка BL-41 по ocenka_*.json — таблица «элемент × фаза × содержание × T → ошибка».

Ошибка = ρ как считает программа − ρ с собственной моделью плотности добавки (правило Вегарда только для
неё), кг/м³ и %; поправки базы вкл. (основное) и выкл. Отмечаются |Δ| > 0,1 % и > 0,5 %.
Пишет results/wave22_v/bl41/itog_tablica.md и bl41/oshibka.png.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

B = Path(__file__).resolve().parents[1] / "bl41"
DIRECT = ("FCC_A1", "BCC_A2", "HCP_A3", "LIQUID")


def main() -> None:
    lines = ["| база | состав | добавка по умолчанию (фазы умолчания) | T, °C | фазы (мольн. доли) | добавка в фазах с прямой/унаследованной DP-моделью, мольн. доля | ρ программа, кг/м³ | ρ своя модель, кг/м³ | Δ, кг/м³ | Δ, % | Δ выкл., % | метка |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    series: dict[str, list[tuple[float, float, float]]] = {}
    for p in sorted(B.glob("ocenka_*.json")):
        d = json.loads(p.read_text("utf-8"))
        src = d["источники"]
        tgt = "; ".join(f"{k} ({', '.join(v['фазы умолчания'])}; своя: {v['источник']})" for k, v in src.items())
        for r in d["строки"]:
            dv = r.get("Δ вкл, %")
            mark = ""
            if dv is not None:
                mark = "**> 0,5 %**" if abs(dv) > 0.5 else ("> 0,1 %" if abs(dv) > 0.1 else "")
            mod = r.get("модель плотности фаз", {})
            phases = ", ".join(f"{k} {v:.3g}" + (f" [{mod[k].split(' ')[0]}]" if k in mod and mod[k].split(' ')[0] != k else "")
                               for k, v in r["фазы (мольн.)"].items())
            fmt = lambda x, f="{:.2f}": "—" if x is None else f.format(x)  # noqa: E731
            lines.append(
                f"| {r['база']} | {r['состав']} | {tgt} | {r['T, °C']:g} | {phases} | {r['добавка в прямых моделях, мольн. доля сплава']:.3g} | "
                f"{fmt(r['ρ прог_вкл, кг/м³'])} | {fmt(r['ρ своя_вкл, кг/м³'])} | {fmt(r['Δ вкл, кг/м³ (прог − своя)'])} | "
                f"{fmt(dv, '{:+.3f}')} | {fmt(r.get('Δ выкл, %'), '{:+.3f}')} | {mark} |"
            )
            if "-" in r["состав"] and len(r["масс. %"]) == 1 and dv is not None:
                (el, wt), = r["масс. %"].items()
                series.setdefault(f"{r['база']}: {el}, {r['T, °C']:g} °C", []).append((wt, dv, r["T, °C"]))
    (B / "itog_tablica.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))
    fig, ax = plt.subplots(figsize=(10, 6))
    for label, pts in sorted(series.items()):
        pts.sort()
        ax.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", lw=1, label=label)
    ax.axhline(0.1, ls="--", color="gray", lw=0.8)
    ax.axhline(-0.1, ls="--", color="gray", lw=0.8)
    ax.axhline(0.5, ls=":", color="gray", lw=0.8)
    ax.axhline(-0.5, ls=":", color="gray", lw=0.8)
    ax.set_xlabel("добавка, масс. %")
    ax.set_ylabel("ошибка плотности сплава, % (программа − своя модель)")
    ax.set_title("BL-41: ошибка от умолчания DP(фаза,*) для добавки, поправки вкл.", fontsize=10)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=6, ncol=3)
    fig.tight_layout()
    fig.savefig(B / "oshibka.png", dpi=110)


if __name__ == "__main__":
    main()
