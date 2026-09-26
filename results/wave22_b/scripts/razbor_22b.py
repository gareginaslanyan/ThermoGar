#!/usr/bin/env python3
"""22-Б: разбор прогонов ``kwn_run.py`` — сводка ``progony.csv`` и таблицы отчёта.

По каждому ``data/<tag>.json`` (+ ``<tag>.npz``):

* остановка да/нет и момент, доля, средний радиус, строк, стена, пик памяти;
* признак «перелёт / разрыв» (шаг 1 в): после правки — из результата
  (``stop_diagnostics``); до правки — теми же функциями приложения
  (``_balance_residual``, ``_raw_matrix_composition``) по NPZ;
* растворения за шаг — методика 22-А2 (``results/wave22_a/scripts/pinki.py``):
  доля за один принятый шаг падает больше чем на 0,1 % (абс.); ложные
  зарождения на плато — растёт больше чем на 0,1 % (абс.) при доле не ниже 99 %
  своего максимума;
* наибольший рост шага dt[i]/dt[i−1] (i ≥ 2: первый шаг — за kawin);
* вызовы баланса масс kawin с составом до зажима ≤ 0 (стадии RK4 / шаги).

    python -B razbor_22b.py            # progony.csv и logs/tablicy_22b.md
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[1]
DATA = BASE / "data"
sys.path.insert(0, str(ROOT / "app"))

SERIES = (
    ("do_", "до правки"),
    ("k", "шаг 1 а: выбор K"),
    ("s2a_", "шаг 2 а: fe"),
    ("s2b_", "шаг 2 б: умолчания"),
    ("s2v_", "шаг 2 в: 718"),
    ("x_k4_s2", "шаг 2 при K = 4 (прерван, заменён K = 2)"),
    ("x_probe_", "пробы (предел 45 с)"),
    ("x_", "сверх задания"),
)

COLUMNS = [
    "тег", "серия", "код", "ячейка", "база", "зерно", "K", "классов", "cmin, нм", "cmax, нм",
    "bulk_n0, 1/м³", "состав", "выдержка, с", "статус", "остановка", "момент остановки, с", "конец, с",
    "строк", "доля в конце, %", "максимум доли, %", "радиус в конце, нм", "частиц в конце, 1/м³",
    "признак (шаг 1 в)", "невязка до остановки / x0", "элемент остановки", "сырой состав на остановке / x0",
    "растворений за шаг", "ложных зарождений на плато", "наибольший рост шага, раз",
    "вызовов баланса с сырым ≤ 0: стадии / шаги", "стена, с", "пик памяти, ГиБ", "текст остановки",
]


def series(tag: str) -> str:
    return next((name for prefix, name in SERIES if tag.startswith(prefix)), "—")


def comma(value: Any, fmt: str) -> str:
    if value is None or value == "":
        return ""
    try:
        return format(float(value), fmt).replace(".", ",")
    except (TypeError, ValueError):
        return str(value)


def npz_facts(tag: str, summary: dict[str, Any]) -> dict[str, Any]:
    """Факты по NPZ: скачки доли, рост шага, признак для прогонов до правки."""

    path = DATA / f"{tag}.npz"
    if not path.exists():
        return {}
    with np.load(path) as archive:
        time = np.asarray(archive["time"], float)
        volfrac = np.asarray(archive["volFrac"], float)
        fconc = np.asarray(archive["fconc"], float)
        composition = np.asarray(archive["composition"], float)
    fv = volfrac.sum(axis=1)
    dfv = np.diff(fv)
    down = int(np.sum(dfv < -1e-3))
    # Плато — доля не ниже 99 % своего максимума (у стали ≈ 4,37 %, как порог 4,36 %
    # таблиц 22-А2); рост доли быстрее 0,1 % за шаг до плато — обычный рост.
    up = int(np.sum((dfv > 1e-3) & (fv[:-1] >= 0.99*np.max(fv)))) if fv.size else 0
    dt = np.diff(time)
    growth = dt[1:]/dt[:-1] if dt.size > 1 else np.array([])
    facts: dict[str, Any] = {
        "down": down,
        "up": up,
        "max_growth": float(np.max(growth)) if growth.size else None,
        "second_step_s": float(dt[1]) if dt.size > 1 else None,
    }
    if summary.get("stop"):
        import thermogar_precipitation as tp

        data = SimpleNamespace(time=time, volFrac=volfrac, fconc=fconc, composition=composition)
        step = len(time) - 1
        residual, index = tp._balance_residual(data, step)
        raw = tp._raw_matrix_composition(data, step)
        facts["own_diagnostics"] = {
            "kind": "перелёт" if residual <= tp.KWN_BALANCE_RESIDUAL_LIMIT else "разрыв",
            "residual_max_rel": residual,
            "residual_index": index,
            "raw_over_x0": (raw/composition[0]).tolist(),
            "step": step,
        }
    return facts


def row_for(path: Path) -> dict[str, str] | None:
    s = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(s, dict) or "kawin_overrides" not in s:
        return None
    tag = path.stem
    a = s.get("arguments", {})
    status = s.get("status")
    step_limit = s.get("app_step_limit") or {}
    code = "до правки" if not step_limit.get("class") else "после правки"
    k_used = step_limit.get("K_used")
    facts = npz_facts(tag, s)
    diag = s.get("stop_diagnostics") or {}
    solutes = sorted(s.get("balance", {}))
    kind = residual = element = raw_text = ""
    if s.get("stop"):
        if diag:
            kind = diag.get("kind", "")
            residual = comma(diag.get("residual_max_rel"), ".3g")
            element = diag.get("element") or ""
            x0 = {name: s["balance"][name]["x0"] for name in solutes}
            raw_text = ", ".join(
                f"{name} {comma(value / x0[name], '.4g')}" for name, value in diag.get("raw_composition", {}).items()
                if x0.get(name)
            )
        elif "own_diagnostics" in facts:
            own = facts["own_diagnostics"]
            kind = own["kind"] + " (по NPZ)"
            residual = comma(own["residual_max_rel"], ".3g")
            note = s.get("stop_note", "")
            element = next((name for name in solutes if f"доля {name.capitalize()} " in note), "")
            raw_text = ", ".join(f"{name} {comma(value, '.4g')}" for name, value in zip(solutes, own["raw_over_x0"]))
    counts = s.get("raw_nonpositive_calls") or {}
    stop = "да" if s.get("stop") else ("нет" if status == "ok" else ("предел" if status == "limit" else "отказ"))
    return {
        "тег": tag,
        "серия": series(tag),
        "код": code,
        "ячейка": s.get("cell", ""),
        "база": a.get("database_key", ""),
        "зерно": str(s.get("pythonhashseed", "")),
        "K": comma(k_used, "g") if code == "после правки" else "—",
        "классов": str(a.get("bins", "")),
        "cmin, нм": comma(a.get("cmin_nm"), "g"),
        "cmax, нм": comma(a.get("cmax_nm"), "g"),
        "bulk_n0, 1/м³": comma(a.get("bulk_n0"), ".3e"),
        "состав": f"{a.get('composition_text', '')} ({'мас.%' if a.get('units') == 'wt' else 'ат.%'})",
        "выдержка, с": comma(3600*float(a.get("duration_h", 0) or 0), ".6g"),
        "статус": {"ok": "посчитан", "limit": "снят по пределу 30 мин", "error": "ошибка"}.get(status, str(status)),
        "остановка": stop,
        "момент остановки, с": comma(s.get("final_time_s") if s.get("stop") else None, ".10g"),
        "конец, с": comma(s.get("final_time_s"), ".10g"),
        "строк": str(s.get("rows", "") or ""),
        "доля в конце, %": comma(s.get("final_fraction_pct"), ".6g"),
        "максимум доли, %": comma(s.get("max_fraction_pct"), ".6g"),
        "радиус в конце, нм": comma(s.get("final_radius_nm"), ".6g"),
        "частиц в конце, 1/м³": comma(s.get("final_density_m3"), ".4e"),
        "признак (шаг 1 в)": kind,
        "невязка до остановки / x0": residual,
        "элемент остановки": element,
        "сырой состав на остановке / x0": raw_text,
        "растворений за шаг": str(facts.get("down", "")),
        "ложных зарождений на плато": str(facts.get("up", "")),
        "наибольший рост шага, раз": comma(facts.get("max_growth"), ".4g"),
        "вызовов баланса с сырым ≤ 0: стадии / шаги": (
            f"{counts.get('stage', '')} / {counts.get('post', '')}" if counts else ""
        ),
        "стена, с": comma(s.get("wall_s"), ".1f"),
        "пик памяти, ГиБ": comma(s.get("peak_rss_gib"), ".3f"),
        "текст остановки": " ".join(str(s.get("stop_note") or s.get("error") or "").split()),
    }


def main() -> None:
    rows = [row for path in sorted(DATA.glob("*.json")) if (row := row_for(path)) is not None]
    order = {name: index for index, (_prefix, name) in enumerate(SERIES)}
    rows.sort(key=lambda r: (order.get(r["серия"], 99), r["тег"]))
    with (BASE / "progony.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    print(f"progony.csv: {len(rows)} строк")
    show = [
        "тег", "код", "K", "зерно", "остановка", "конец, с", "строк", "доля в конце, %", "радиус в конце, нм",
        "признак (шаг 1 в)", "невязка до остановки / x0", "растворений за шаг", "ложных зарождений на плато",
        "наибольший рост шага, раз", "вызовов баланса с сырым ≤ 0: стадии / шаги", "стена, с", "пик памяти, ГиБ",
    ]
    lines = ["| " + " | ".join(show) + " |", "|" + "---|"*len(show)]
    for row in rows:
        lines.append("| " + " | ".join(row[name] or "—" for name in show) + " |")
    (BASE / "logs" / "tablicy_22b.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
