"""21-E, step 6b: rows of the 21-B colour table «было → стало» and contrasts.

Reads results/wave21_b/izmereniya.json (was) and results/wave21_z/izmereniya.json
(now), takes for every colour key the most frequent value over all subtabs
of one theme, and the minimum and maximum of every contrast pair. Writes
results/wave21_z/bylo_stalo.json and prints Markdown tables.

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_z\\scripts\\bylo_stalo.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WAS = ROOT / "results" / "wave21_b" / "izmereniya.json"
NOW = ROOT / "results" / "wave21_z" / "izmereniya.json"
OUT = ROOT / "results" / "wave21_z" / "bylo_stalo.json"

KEYS = [
    ("window_bg", "Окно"),
    ("sidebar_bg", "Боковая панель"),
    ("expander_bg", "Раскрытие: фон"),
    ("expander_border", "Раскрытие: рамка"),
    ("bordered_container_bg", "Контейнер или форма с рамкой: фон"),
    ("bordered_container_border", "Контейнер или форма с рамкой: рамка"),
    ("body_text", "Основной текст"),
    ("caption", "st.caption (как нарисован)"),
    ("widget_label", "Подпись поля"),
    ("input_bg", "Поле: заливка"),
    ("input_border", "Поле: рамка"),
    ("primary_button_text", "Основная кнопка: текст"),
    ("primary_button_bg", "Основная кнопка: фон"),
]


def colour_of(entry: dict | None) -> str | None:
    if not entry:
        return None
    if "painted" in entry and entry.get("opacity", 1) != 1:
        return f"{entry['value']} × {entry['opacity']} = {entry['painted']}"
    return entry["value"]


def summary(data: dict, theme: str) -> dict:
    styles = data.get(theme, {}).get("styles", {})
    colours: dict[str, Counter] = {key: Counter() for key, _ in KEYS}
    contrasts: dict[str, list] = {}
    for tab, measured in styles.items():
        for key, _ in KEYS:
            value = colour_of(measured["colours"].get(key))
            if value:
                colours[key][value] += 1
        for pair in measured.get("contrast", []):
            contrasts.setdefault(pair["what"], []).append(
                (pair["ratio"], pair.get("fg"), pair.get("bg"), tab)
            )
    return {
        "colours": {key: counter.most_common(3) for key, counter in colours.items()},
        "contrasts": {
            what: {
                "min": min(values),
                "max": max(values),
                "count": len(values),
            }
            for what, values in contrasts.items()
        },
        "dataframe_header": data.get(theme, {}).get("dataframe_header"),
    }


def main() -> int:
    was = json.loads(WAS.read_text("utf-8"))
    now = json.loads(NOW.read_text("utf-8"))
    result = {}
    for theme in ("Light", "Dark"):
        result[theme] = {"was": summary(was, theme), "now": summary(now, theme)}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    for theme in ("Light", "Dark"):
        print(f"\n### {theme}\n")
        print("| Элемент | Было (21-Б) | Стало (21-Е) |\n|---|---|---|")
        for key, title in KEYS:
            before = result[theme]["was"]["colours"][key]
            after = result[theme]["now"]["colours"][key]
            fmt = lambda items: "; ".join(f"{value} ({count})" for value, count in items) or "—"
            print(f"| {title} | {fmt(before)} | {fmt(after)} |")
        print("\n| Пара | Было | Стало |\n|---|---|---|")
        names = sorted(set(result[theme]["was"]["contrasts"]) | set(result[theme]["now"]["contrasts"]))
        for name in names:
            def cell(block):
                item = block["contrasts"].get(name)
                if not item:
                    return "—"
                low, high = item["min"], item["max"]
                if low[0] == high[0]:
                    return f"{low[0]:.2f}:1 ({low[1]} / {low[2]})"
                return f"{low[0]:.2f}–{high[0]:.2f}:1 ({low[1]} / {low[2]} … {high[1]} / {high[2]})"
            print(f"| {name} | {cell(result[theme]['was'])} | {cell(result[theme]['now'])} |")
        print("\ndataframe header was:", result[theme]["was"]["dataframe_header"])
        print("dataframe header now:", result[theme]["now"]["dataframe_header"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
