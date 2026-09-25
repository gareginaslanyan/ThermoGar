#!/usr/bin/env python3
"""22-Б: таблицы отчёта (markdown) из JSON и NPZ прогонов — без ручного переписывания чисел.

    python -B tablicy_22b.py > ../logs/tablicy_otcheta_22b.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"


def load(tag: str) -> dict[str, Any] | None:
    path = DATA / f"{tag}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_a2(tag: str) -> dict[str, Any] | None:
    """Прогон 22-А2 из ветки origin/wave22-a (для строк «до» из 22-А2)."""

    import subprocess

    try:
        text = subprocess.run(
            ["git", "show", f"origin/wave22-a:results/wave22_a/data/{tag}.json"],
            cwd=BASE.parents[1], capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return json.loads(text)


def comma(value: Any, fmt: str) -> str:
    if value is None:
        return "—"
    return format(float(value), fmt).replace(".", ",")


def npz(tag: str) -> dict[str, Any]:
    path = DATA / f"{tag}.npz"
    if not path.exists():
        return {}
    with np.load(path) as archive:
        time = np.asarray(archive["time"], float)
        fv = np.asarray(archive["volFrac"], float).sum(axis=1)
    dfv = np.diff(fv)
    dt = np.diff(time)
    return {
        "down": int(np.sum(dfv < -1e-3)),
        "down_1e4": int(np.sum(dfv < -1e-4)),
        "down_1e5": int(np.sum(dfv < -1e-5)),
        "max_drop_pct": float(100*max(0.0, -dfv.min())) if dfv.size else 0.0,
        "collapses": int(np.sum(dt[1:] < 0.5*dt[:-1])) if dt.size > 1 else 0,
        "max_growth": float(np.max(dt[1:]/dt[:-1])) if dt.size > 1 else None,
        "second_step": float(dt[1]) if dt.size > 1 else None,
    }


# Прогон, остановленный вручную сигналом предела (см. logs/x_k4_s2b_umolch_fe_s0_zametka.txt).
MANUAL_STOP = {"x_k4_s2b_umolch_fe_s0"}


def outcome(s: dict[str, Any] | None) -> str:
    if s is None:
        return "—"
    if s.get("status") == "limit":
        if s.get("tag") in MANUAL_STOP or f"x_k4_{s.get('tag')}" in MANUAL_STOP:
            return f"прерван вручную на {comma(s.get('final_time_s'), '.5g')} с"
        limit = s.get("limit_s", 1800)
        return f"снят по пределу {comma(limit, 'g')} с на {comma(s.get('final_time_s'), '.5g')} с"
    if s.get("status") != "ok":
        return "ошибка"
    if s.get("stop"):
        return f"**остановка на {comma(s['final_time_s'], '.6g')} с**"
    return "нет"


def kind(s: dict[str, Any] | None) -> str:
    if not s or not s.get("stop"):
        return "—"
    d = s.get("stop_diagnostics") or {}
    if d:
        return f"{d['kind']} (невязка {comma(d['residual_max_rel'], '.2g')}·x0)"
    return "см. разбор «до»"


def row(label: str, tag: str, extra: str = "") -> str:
    s = load(tag)
    f = npz(tag)
    if s is None:
        return f"| {label} | {tag} | не посчитан |" + " —|"*8
    counts = s.get("raw_nonpositive_calls") or {}
    return (
        f"| {label} | {tag} | {outcome(s)} | {comma(s.get('final_fraction_pct'), '.6g')} | "
        f"{comma(s.get('final_radius_nm'), '.5g')} | {s.get('rows', '—')} | {comma(s.get('wall_s'), '.0f')} | "
        f"{comma(s.get('peak_rss_gib'), '.3f')} | {kind(s)} | {f.get('down', '—')} | "
        f"{counts.get('stage', '—')} / {counts.get('post', '—')} |{extra}"
    )


HEADER = (
    "| прогон | тег | остановка | доля в конце, % | средний радиус, нм | строк | стена, с | пик, ГиБ | "
    "признак | растворений за шаг | сырой ≤ 0: стадии / шаги |\n"
    "|---|---|---|---:|---:|---:|---:|---:|---|---:|---|"
)


def main() -> None:
    print("### Шаг 1 а. Выбор K: ячейка приложения fe, 3,6 с\n")
    print("| K | зерно | остановка | доля, % | R, нм | N, 1/м³ | строк | стена, с | растворений за шаг (> 0,1 % абс.) | "
          "падений доли > 0,01 % / > 0,001 % абс. | наибольшее падение, % абс. | обвалов шага (< ½ предыдущего) | "
          "min сырого / x0 по добавкам | сырой ≤ 0: стадии / шаги |")
    print("|---:|---:|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|")
    for k, name in ((1.5, "15"), (2.0, "2"), (4.0, "4")):
        for seed in (0, 1, 2):
            tag = f"k{name}_app_s{seed}"
            s = load(tag)
            f = npz(tag)
            if s is None:
                continue
            c = s.get("raw_nonpositive_calls") or {}
            print(f"| {comma(k, 'g')} | {seed} | {outcome(s)} | {comma(s['final_fraction_pct'], '.6g')} | "
                  f"{comma(s['final_radius_nm'], '.5g')} | {comma(s['final_density_m3'], '.4e')} | {s['rows']} | "
                  f"{comma(s['wall_s'], '.1f')} | {f['down']} | {f['down_1e4']} / {f['down_1e5']} | "
                  f"{comma(f['max_drop_pct'], '.2g')} | {f['collapses']} | {comma(c.get('min_raw_over_x0'), '.4g')} | "
                  f"{c.get('stage')} / {c.get('post')} |")

    print("\n### Сверх задания: K = 1,1 и опорный расчёт с шагом ≤ 3,6e-4 с (зерно 0)\n")
    print("| вариант | строк | доля, % | R, нм | N, 1/м³ | стена, с | падений доли > 0,001 % абс. | обвалов шага |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for label, tag in (
        ("K = 1,1", "x_k1.1_app_s0"), ("K = 1,5", "k15_app_s0"), ("K = 2", "k2_app_s0"), ("K = 4", "k4_app_s0"),
        ("K = 2, maxDtFrac 1e-4", "x_k2_dtmax1e-4_app_s0"), ("K = 4, maxDtFrac 1e-4", "x_k4_dtmax1e-4_app_s0"),
    ):
        s = load(tag)
        f = npz(tag)
        if s is None:
            continue
        print(f"| {label} | {s['rows']} | {comma(s['final_fraction_pct'], '.6g')} | {comma(s['final_radius_nm'], '.5g')} | "
              f"{comma(s['final_density_m3'], '.4e')} | {comma(s['wall_s'], '.1f')} | {f['down_1e5']} | {f['collapses']} |")

    print("\n### Шаг 2 а. fe: ячейка приложения 3,6 с (зёрна 0–9) и ячейка расчётного теста 1 с и 3,6 с (зёрна 0–2)\n")
    print(HEADER)
    for seed in range(10):
        print(row(f"приложения, 3,6 с, зерно {seed}", f"s2a_app_s{seed}"))
    for seed in range(3):
        print(row(f"расчётного теста, 1 с, зерно {seed}", f"s2a_backend1s_s{seed}"))
    for seed in range(3):
        print(row(f"расчётного теста, 3,6 с, зерно {seed}", f"s2a_backend36_s{seed}"))

    print("\n### Шаг 2 б. Умолчания раздела «Выделения», зерно 0\n")
    print(HEADER)
    for label, tag in (
        ("ni, 100 ч — до правки", "do_umolch_ni_s0"), ("ni, 100 ч — после", "s2b_umolch_ni_s0"),
        ("al, 24 ч — до правки", "do_umolch_al_s0"), ("al, 24 ч — после", "s2b_umolch_al_s0"),
        ("fe, 0,05 ч — после", "s2b_umolch_fe_s0"),
    ):
        print(row(label, tag))
    a2 = load_a2("a2_005h_umolch_s0")
    if a2:
        print(f"| fe, 0,05 ч — до правки (22-А2) | a2_005h_umolch_s0 | {outcome(a2)} | "
              f"{comma(a2.get('final_fraction_pct'), '.6g')} | {comma(a2.get('final_radius_nm'), '.5g')} | "
              f"{a2.get('rows')} | {comma(a2.get('wall_s'), '.0f')} | {comma(a2.get('peak_rss_gib'), '.3f')} | "
              f"перелёт (22-А2) | 0 | — |")

    print("\n### Шаг 2 в. 718 (15-В), 700 °C, 95 мДж/м², зерно 0\n")
    print(HEADER)
    for label, tag in (
        ("до правки", "do_718_s0"), ("после (K = 2)", "s2v_718_s0"),
        ("сверх задания: K = 4", "x_k4_s2v_718_s0"), ("сверх задания: K = 1,5", "x_718_k15_s0"),
    ):
        print(row(label, tag))

    print("\n### Умолчание стали 0,05 ч по K: первые шаги и ход доли (зерно 0)\n")
    print("| вариант | тег | исход | дошёл до, с | первые шаги, с | доля при 0,75 с, % | R при 0,75 с, нм | "
          "доля в конце, % | R в конце, нм | строк | стена, с |")
    print("|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|")
    for label, tag in (
        ("K = 2 (в коде)", "s2b_umolch_fe_s0"),
        ("K = 4, прерван вручную", "x_k4_s2b_umolch_fe_s0"),
        ("K = 1,5, сверх задания", "x_k15_umolch_fe_s0"),
        ("проба K = 4, 45 с", "x_probe_umolch_fe_k4_45s"),
        ("проба K = 2, 45 с", "x_probe_umolch_fe_k2_45s"),
    ):
        s = load(tag)
        path = DATA / f"{tag}.npz"
        if s is None or not path.exists():
            print(f"| {label} | {tag} | не посчитан |" + " —|"*8)
            continue
        with np.load(path) as archive:
            time = np.asarray(archive["time"], float)
            fv = np.asarray(archive["volFrac"], float).sum(axis=1)
            radius = np.asarray(archive["Ravg"], float)[:, 0]
        i = min(int(np.searchsorted(time, 0.75)), len(time) - 1)
        steps = " → ".join(comma(x, ".4g") for x in np.diff(time)[:4])
        print(f"| {label} | {tag} | {outcome(s)} | {comma(s['final_time_s'], '.5g')} | {steps} | "
              f"{comma(100*fv[i], '.4g')} | {comma(1e9*radius[i], '.4g')} | {comma(s['final_fraction_pct'], '.5g')} | "
              f"{comma(s['final_radius_nm'], '.5g')} | {s['rows']} | {comma(s['wall_s'], '.0f')} |")

    print("\n### Шаг 2 при K = 4 (прерван, заменён K = 2), зерно 0 и ячейка приложения на зёрнах 0–3\n")
    print(HEADER)
    for label, tag in (
        ("fe, приложения, 3,6 с, зерно 0", "x_k4_s2a_app_s0"), ("fe, приложения, 3,6 с, зерно 1", "x_k4_s2a_app_s1"),
        ("fe, приложения, 3,6 с, зерно 2", "x_k4_s2a_app_s2"), ("fe, приложения, 3,6 с, зерно 3", "x_k4_s2a_app_s3"),
        ("ni, 100 ч", "x_k4_s2b_umolch_ni_s0"), ("al, 24 ч", "x_k4_s2b_umolch_al_s0"),
        ("fe, 0,05 ч (прерван вручную)", "x_k4_s2b_umolch_fe_s0"), ("718", "x_k4_s2v_718_s0"),
    ):
        print(row(label, tag))

    total = 0.0
    count = 0
    peak = 0.0
    for path in DATA.glob("*.json"):
        s = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(s, dict) and "wall_s" in s:
            total += float(s["wall_s"])
            count += 1
            peak = max(peak, float(s.get("peak_rss_gib", 0)))
    print(f"\nПрогонов kwn_run: {count}; сумма стены: {comma(total, '.0f')} с ({comma(total/3600, '.2f')} ч); "
          f"пик памяти прогона: {comma(peak, '.3f')} ГиБ.")


if __name__ == "__main__":
    main()
