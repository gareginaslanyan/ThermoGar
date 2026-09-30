#!/usr/bin/env python3
"""22-В, шаг 4 в: компактная таблица BL-41 — добавка × содержание × T → Δ, % (поправки вкл.), где сидит добавка.

Пишет results/wave22_v/bl41/svodka.md.
"""
import json
from pathlib import Path

B = Path(__file__).resolve().parents[1] / "bl41"


def main():
    rows = []
    for p in sorted(B.glob("ocenka_*.json")):
        d = json.loads(p.read_text("utf-8"))
        for r in d["строки"]:
            if "-" not in r["состав"] or len(r["масс. %"]) != 1:
                continue
            (el, wt), = r["масс. %"].items()
            rows.append((r["база"], el, wt, r["T, °C"], r.get("Δ вкл, %"), r.get("Δ вкл, кг/м³ (прог − своя)"),
                         r["фазы (мольн.)"], d["источники"][el]["источник"]))
    temps = sorted({t for *_, t, _, _, _, _ in [(0, 0, 0, r[3], 0, 0, 0, 0) for r in rows]})
    lines = ["| база | добавка | своя модель (источник) | масс. % | " + " | ".join(f"{t:g} °C: Δ, % (кг/м³)" for t in temps) + " |",
             "|---|---|---|---|" + "---|" * len(temps)]
    keys = sorted({(r[0], r[1], r[2]) for r in rows})
    for db, el, wt in keys:
        cells = []
        src = next(r[7] for r in rows if r[0] == db and r[1] == el)
        for t in temps:
            m = [r for r in rows if r[0] == db and r[1] == el and r[2] == wt and r[3] == t]
            if not m:
                cells.append("")
                continue
            dv, dk = m[0][4], m[0][5]
            cells.append("нет плотности" if dv is None else f"{dv:+.3f} ({dk:+.1f})")
        lines.append(f"| {db} | {el} | {src} | {wt:g} | " + " | ".join(cells) + " |")
    (B / "svodka.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
