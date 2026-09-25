#!/usr/bin/env python3
"""22-А/22-А2: сводная таблица прогонов ``progony.csv`` (UTF-8 с BOM, «;»).

Одна строка — один прогон ``kwn_run.py`` (``data/<tag>.json``). Серия — по
приставке тега. Остановка: «да» — BL-35 (C матрицы ушёл в 0); «нет» — дошёл до
конца выдержки; «отказ» — ``run_precipitation`` отказал до счёта (BL-22 и
т. п.), текст отказа — в колонке «текст»; «предел» — снят по пределу 30 мин.

    python -B svod.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"

SERIES = (
    ("a2_shag0_", "22-А2 шаг 0"),
    ("a2_s1_", "22-А2 шаг 1"),
    ("a2_setka_", "22-А2 шаг 2а"),
    ("a2_otl_", "22-А2 шаг 2б"),
    ("a2_kawin_", "22-А2 шаг 2в"),
    ("a2_zerno_", "22-А2 шаг 2г"),
    ("a2_005h_", "22-А2 шаг 2д"),
    ("shag", "22-А шаг 1"),
)

COLUMNS = [
    "тег", "серия", "ячейка", "зерно", "классов", "cmin, нм", "cmax, нм", "bulk_n0, 1/м³", "состав",
    "выдержка, с", "настройка kawin", "статус", "остановка", "момент остановки, с", "конец, с", "строк",
    "доля в конце, %", "максимум доли, %", "радиус в конце, нм", "частиц в конце, 1/м³",
    "невязка C до остановки, max |·|", "C в выделениях / C сплава на остановке", "стена, с", "пик памяти, ГиБ",
    "текст",
]


def series(tag: str) -> str:
    return next((name for prefix, name in SERIES if tag.startswith(prefix)), "—")


def setting(summary: dict) -> str:
    overrides = summary.get("kawin_overrides", {})
    parts = [f"{k}={v:g}" for k, v in overrides.get("constraints", {}).items()]
    if isinstance(overrides.get("maxDtFrac"), (int, float)):
        parts.append(f"maxDtFrac={overrides['maxDtFrac']:g}")
    if isinstance(overrides.get("minDtFrac"), (int, float)):
        parts.append(f"minDtFrac={overrides['minDtFrac']:g}")
    iterator = overrides.get("iterator", "")
    if iterator and not str(iterator).startswith("rk4 ("):
        parts.append(f"iterator={iterator}")
    return "; ".join(parts) or "умолчания kawin 0.5.0"


def number(value: object, fmt: str) -> str:
    if value is None or value == "":
        return ""
    try:
        return format(float(value), fmt).replace(".", ",")
    except (TypeError, ValueError):
        return str(value)


def row_for(path: Path) -> dict[str, str]:
    s = json.loads(path.read_text(encoding="utf-8"))
    a = s.get("arguments", {})
    status = s.get("status")
    balance = s.get("balance", {}).get("C", {})
    if status == "ok":
        stop = "да" if s.get("stop") else "нет"
        state = "посчитан"
    elif status == "limit":
        stop, state = "предел", "снят по пределу"
    else:
        stop, state = "отказ", "отказ до счёта" if "UserValueError" in s.get("error", "") else "ошибка"
    text = s.get("stop_note") or s.get("error") or ""
    seed = s.get("pythonhashseed", "")
    if not seed:
        # Прогоны до записи зерна в JSON (22-А и шаг 0 22-А2): зерно — в теге.
        if path.stem in {"shag1_app", "shag1_backend", "shag2_app_trace"}:
            seed = "случайное (22-А)"
        elif "_seed" in path.stem:
            seed = path.stem.split("_seed")[1][0]
    return {
        "тег": path.stem,
        "серия": series(path.stem),
        "ячейка": {"app": "приложения", "backend": "расчётного теста"}.get(s.get("cell"), s.get("cell", "")),
        "зерно": str(seed),
        "классов": str(a.get("bins", "")),
        "cmin, нм": number(a.get("cmin_nm"), "g"),
        "cmax, нм": number(a.get("cmax_nm"), "g"),
        "bulk_n0, 1/м³": number(a.get("bulk_n0"), ".0e"),
        "состав": f"{a.get('composition_text', '')} ({'мас.%' if a.get('units') == 'wt' else 'ат.%'})",
        "выдержка, с": number(3600 * float(a.get("duration_h", 0)), ".4g"),
        "настройка kawin": setting(s),
        "статус": state,
        "остановка": stop,
        "момент остановки, с": number(s.get("final_time_s") if s.get("stop") else None, ".10g"),
        "конец, с": number(s.get("final_time_s"), ".10g"),
        "строк": str(s.get("rows", "") or ""),
        "доля в конце, %": number(s.get("final_fraction_pct"), ".6g"),
        "максимум доли, %": number(s.get("max_fraction_pct"), ".6g"),
        "радиус в конце, нм": number(s.get("final_radius_nm"), ".6g"),
        "частиц в конце, 1/м³": number(s.get("final_density_m3"), ".4e"),
        "невязка C до остановки, max |·|": number(balance.get("max_abs_residual_unclamped"), ".3g"),
        "C в выделениях / C сплава на остановке": number(balance.get("fconc_over_x0_at_first_clamp"), ".4f"),
        "стена, с": number(s.get("wall_s"), ".1f"),
        "пик памяти, ГиБ": number(s.get("peak_rss_gib"), ".3f"),
        "текст": " ".join(str(text).split()),
    }


def main() -> None:
    rows = [row_for(path) for path in sorted(DATA.glob("*.json")) if "kawin_overrides" in path.read_text(encoding="utf-8")]
    order = {name: index for index, (_prefix, name) in enumerate(SERIES)}
    rows.sort(key=lambda r: (order.get(r["серия"], 99), r["тег"]))
    with (BASE / "progony.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    print(f"progony.csv: {len(rows)} строк")


if __name__ == "__main__":
    main()
