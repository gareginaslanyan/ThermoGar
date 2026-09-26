"""21-U, step 5: results/wave21_u/zamery.csv from kadry_21u.json (UTF-8 with BOM, «;»)."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[1]
record = json.loads((RESULTS / "kadry_21u.json").read_text("utf-8"))
THEME = {"svet": "светлая", "tyomn": "тёмная"}

rows = []


def add(what, base, slug, name, value, before, frames):
    rows.append([len(rows) + 1, what, base, THEME[slug], name, value, before, ", ".join(frames)])


for slug in ("svet", "tyomn"):
    e = record[f"tzero_fe_umolch_{slug}"]
    what = "Энергии → T₀, сталь по умолчанию (200–950 °C)"
    grid = e["grid_rows_in_view"]
    tail = [row for row in grid if row and row[0] in ("1.8", "1.9", "2")]
    add(what, "fe", slug, "время счёта, с", e["seconds"], "", e["frames"])
    add(what, "fe", slug, "строк в Excel T0", e["rows"], "21 (21-О)", e["frames"])
    add(what, "fe", slug, "T₀ найдено, точек", e["found"], "18 (21-О)", e["frames"])
    add(what, "fe", slug, "пустых «T₀, °C» / «T₀, K» в строках C 1.8–2.0 мас.% (Excel)",
        f"{e['tail_tzero_c_empty']} / {e['tail_tzero_k_empty']}", "3 / 3 (данные не меняются)", e["frames"])
    add(what, "fe", slug, "строки C 1.8–2.0 мас.% на экране", "прочерк «—» в «T₀, °C» и «T₀, K» (кадр)",
        "серое «None» (21-С)", e["frames"])
    add(what, "fe", slug, "текст ячеек T₀ этих строк в доступной таблице сетки",
        " | ".join(",".join(repr(c) for c in row[1:3]) for row in tail), "", e["frames"])

for slug in ("svet", "tyomn"):
    e = record[f"uprugie_shag2_{slug}"]
    what = "Свойства → Упругие свойства, шаг 2, Ni по умолчанию"
    add(what, "ni", slug, "время «Получить фазовые доли», с", e["seconds_step1"], "", e["frames"])
    add(what, "ni", slug, "фаз в редакторе", len(e["grid_rows_in_view"]) - 1, "", e["frames"])
    add(what, "ni", slug, "пустые E, ν, «Происхождение», «Источник», «Температура источника, °C»",
        "прочерк «—» (кадр)", "серое «None» (21-М, 21-С)", e["frames"])
    add(what, "ni", slug, "«Примечание» (пустая строка \"\")", "пустая ячейка (кадр)",
        "пустая ячейка (21-С)", e["frames"])

buf = io.StringIO()
writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
writer.writerow(["№", "замер", "база", "тема", "величина", "ноутбук", "мастер / было", "кадры"])
writer.writerows(rows)
(RESULTS / "zamery.csv").write_bytes(("﻿" + buf.getvalue()).encode("utf-8"))
print(len(rows))
