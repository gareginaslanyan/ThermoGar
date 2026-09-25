#!/usr/bin/env python3
"""22-А2: таблицы для отчёта (markdown) из JSON прогонов — без ручного переписывания чисел.

    python -B tablicy_otcheta.py > ../logs/a2_tablicy.md
"""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"


def load(tag: str) -> dict | None:
    path = DATA / f"{tag}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def comma(value: float, fmt: str) -> str:
    return format(value, fmt).replace(".", ",")


def cell(summary: dict | None) -> str:
    if summary is None:
        return "—"
    if summary.get("status") == "error":
        return "отказ BL-22" if "Сетка размеров" in summary.get("error", "") else "ошибка"
    if summary.get("status") == "limit":
        return f"снят на {comma(summary['final_time_s'], '.4g')} с"
    t = comma(summary["final_time_s"], ".4g")
    full = summary.get("final_fraction_pct", 0) >= 99.9999
    if summary.get("stop"):
        return f"**{t} с**" + (" (доля 100 %)" if full else "")
    return f"нет ({comma(summary['final_fraction_pct'], '.4f')} %, {comma(summary['final_radius_nm'], '.3g')} нм)"


def wall(summary: dict | None) -> str:
    return "—" if summary is None else comma(summary.get("wall_s", 0), ".0f")


def rows(summary: dict | None) -> str:
    return "—" if summary is None or not summary.get("rows") else str(summary["rows"])


def triple(pattern: str) -> list[dict | None]:
    return [load(pattern.format(seed)) for seed in (0, 1, 2)]


def main() -> None:
    print("### 2а. Сетка (ячейка приложения, 3,6 с): момент остановки, с — зёрна 0 / 1 / 2\n")
    print("| классов | ширина класса, нм (0,2; 10) | (0,2; 10) нм | ширина, нм (0,5; 10) | (0,5; 10) нм |")
    print("|---:|---:|---|---:|---|")
    for bins in (20, 30, 40, 60, 80):
        a = triple(f"a2_setka_b{bins}_c02_s{{}}")
        b = triple(f"a2_setka_b{bins}_c05_s{{}}")
        print(f"| {bins} | {comma(9.8 / bins, '.3f')} | {' / '.join(cell(s) for s in a)} | "
              f"{comma(9.5 / bins, '.3f')} | {' / '.join(cell(s) for s in b)} |")
    refusal = load("a2_setka_b20_c02_s0")
    if refusal:
        print(f"\nТекст отказа (20 классов, (0,2; 10)): «{refusal['error'].split(': ', 1)[1]}»")
    refusal = load("a2_setka_b20_c05_s0")
    if refusal:
        print(f"\nТекст отказа (20 классов, (0,5; 10)): «{refusal['error'].split(': ', 1)[1]}»")

    print("\n### 2б/2в. Отличия ячеек и настройки kawin (3,6 с): исход — зёрна 0 / 1 / 2; строк; стена, с\n")
    print("| вариант | исход | строк | стена, с |")
    print("|---|---|---|---|")
    configs = [
        ("ячейка приложения (умолчания kawin)", "a2_setka_b40_c02_s{}"),
        ("2б: bulk_n0 = 1e30", "a2_otl_n30_s{}"),
        ("2б: без Ni", "a2_otl_bezNi_s{}"),
        ("2б: сетка (0,5; 10) × 30", "a2_setka_b30_c05_s{}"),
        ("2б: ячейка расчётного теста на 3,6 с", "a2_otl_backend36_s{}"),
        ("2в: maxRcritChange 0,01 → 0,001", "a2_kawin_rcrit1e-3_s{}"),
        ("2в: maxDissolution 1e-3 → 1e-4", "a2_kawin_diss1e-4_s{}"),
        ("2в: maxVolumeChange 1e-3 → 1e-4", "a2_kawin_vol1e-4_s{}"),
        ("2в: maxDtFrac 1 → 0,1", "a2_kawin_dtfrac0.1_s{}"),
        ("2в: minComposition 0 → 1e-8", "a2_kawin_mincomp1e-8_s{}"),
        ("2в: minComposition 0 → 1e-11", "a2_kawin_mincomp1e-11_s{}"),
        ("сверх задания: шаг ≤ 2× предыдущего", "a2_extra_cap2_s{}"),
    ]
    for label, pattern in configs:
        t = triple(pattern)
        print(f"| {label} | {' / '.join(cell(s) for s in t)} | {' / '.join(rows(s) for s in t)} | "
              f"{' / '.join(wall(s) for s in t)} |")

    print("\n### 2г. Ячейка приложения на зёрнах 0–9\n")
    print("| зерно | исход | строк | стена, с |")
    print("|---:|---|---:|---:|")
    tags = {0: "a2_setka_b40_c02_s0", 1: "a2_setka_b40_c02_s1", 2: "a2_setka_b40_c02_s2"}
    tags.update({seed: f"a2_zerno_s{seed}" for seed in range(3, 10)})
    stops = 0
    for seed, tag in tags.items():
        s = load(tag)
        stops += bool(s and s.get("stop"))
        print(f"| {seed} | {cell(s)} | {rows(s)} | {wall(s)} |")
    print(f"\nОстановились до 3,6 с: {stops} из {len(tags)}.")

    print("\n### 2д. 0,05 ч (180 с), сетка раздела (0,2; 10) × 80\n")
    print("| вариант | зерно | исход | дошёл до, с | строк | стена, с | пик, ГиБ |")
    print("|---|---:|---|---:|---:|---:|---:|")
    for label, tag, seed in (
        ("умолчание раздела", "a2_005h_umolch_s0", 0),
        ("minComposition 1e-8", "a2_005h_mincomp1e-8_s0", 0),
        ("minComposition 1e-8", "a2_005h_mincomp1e-8_s1", 1),
        ("minComposition 1e-8", "a2_005h_mincomp1e-8_s2", 2),
    ):
        s = load(tag)
        reached = "—" if s is None else comma(s.get("final_time_s", 0), ".5g")
        peak = "—" if s is None else comma(s.get("peak_rss_gib", 0), ".3f")
        print(f"| {label} | {seed} | {cell(s)} | {reached} | {rows(s)} | {wall(s)} | {peak} |")

    print("\n### Сходимость по сетке (ячейка приложения, (0,2; 10), 3,6 с, зерно 0)\n")
    print("| классов | умолчания kawin | minComposition 1e-8 | шаг ≤ 2× предыдущего (сверх kawin) |")
    print("|---:|---|---|---|")
    for bins in (30, 40, 60, 80):
        default = load(f"a2_setka_b{bins}_c02_s0")
        mincomp = load("a2_kawin_mincomp1e-8_s0" if bins == 40 else f"a2_skhod_mincomp1e-8_b{bins}_s0")
        cap = load("a2_extra_cap2_s0" if bins == 40 else f"a2_skhod_cap2_b{bins}_s0")

        def full(s: dict | None) -> str:
            if s is None or s.get("status") != "ok":
                return cell(s)
            if s.get("stop"):
                return cell(s)
            return (f"{comma(s['final_fraction_pct'], '.4f')} %, R {comma(s['final_radius_nm'], '.4g')} нм, "
                    f"N {comma(s['final_density_m3'], '.3e')} м⁻³; {s['rows']} стр., {comma(s['wall_s'], '.0f')} с")

        print(f"| {bins} | {full(default)} | {full(mincomp)} | {full(cap)} |")

    print("\n### Сверх задания: шаг ≤ 2× предыдущего на 0,05 ч, сетка (0,2; 10) × 80\n")
    print("| зерно | исход | дошёл до, с | строк | стена, с | пик, ГиБ |")
    print("|---:|---|---:|---:|---:|---:|")
    for seed in (0, 1, 2):
        s = load(f"a2_extra_005h_cap2_s{seed}")
        reached = "—" if s is None else comma(s.get("final_time_s", 0), ".5g")
        peak = "—" if s is None else comma(s.get("peak_rss_gib", 0), ".3f")
        print(f"| {seed} | {cell(s)} | {reached} | {rows(s)} | {wall(s)} | {peak} |")

    total = 0.0
    count = 0
    peak = 0.0
    for path in DATA.glob("*.json"):
        s = json.loads(path.read_text(encoding="utf-8"))
        if "wall_s" in s:
            total += float(s["wall_s"])
            count += 1
            peak = max(peak, float(s.get("peak_rss_gib", 0)))
    print(f"\nПрогонов kwn_run: {count}; сумма стены kwn_run: {comma(total, '.0f')} с ({comma(total / 3600, '.2f')} ч); "
          f"пик памяти прогона: {comma(peak, '.3f')} ГиБ.")


if __name__ == "__main__":
    main()
