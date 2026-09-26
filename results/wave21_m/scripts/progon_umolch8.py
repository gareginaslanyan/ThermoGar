"""21-М, ШАГ 5 (решение 8Б): прогон «Многокомпонентного T–X» ni по умолчанию.

AppTest, база ni, умолчания без изменений; нажатие «Построить многокомпонентное
сечение». Из таблицы границ результата: линии границ (группы «Граница…»), узлы
(группы «Инвариант…»), фазы линий — так же, как считала 21-Л
(results/wave21_l/scripts/progon_10b.py, download_excel). PNG графика и
таблица — в results/wave21_m/umolch8/.

Запуск из корня дерева:
    set PYTHONHASHSEED=0 & set MPLBACKEND=Agg & set THERMOGAR_STATE_ROOT=%TEMP%\\tg21m_umolch8
    python -B results/wave21_m/scripts/progon_umolch8.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "app"))
OUT = ROOT / "results" / "wave21_m" / "umolch8"
OUT.mkdir(parents=True, exist_ok=True)

from streamlit.testing.v1 import AppTest  # noqa: E402

app = AppTest.from_file(str(ROOT / "app" / "ThermoGar_app.py"), default_timeout=1800)
app.session_state["thermogar_database_key"] = "ni"
app.run()
assert not app.exception, [e.message for e in app.exception]

inputs = {
    item.key: item.value
    for item in app.number_input
    if item.key and item.key.startswith("isopleth_")
}
inputs.update(
    {
        item.key: item.value
        for item in app.text_area
        if item.key and item.key.startswith("isopleth_fixed")
    }
)
inputs["variable"] = [
    item.value for item in app.selectbox if item.key and item.key.startswith("isopleth_variable")
][0]

button = [item for item in app.button if item.key == "isopleth_calculate"][0]
started = time.perf_counter()
button.click().run()
elapsed = time.perf_counter() - started
errors = [e.value for e in app.error]
exceptions = [e.message for e in app.exception]

result = app.session_state["isopleth_result_ni"]
boundaries = result["boundaries"]
boundaries.to_csv(OUT / "granicy.csv", sep=";", index=False, encoding="utf-8-sig")
settings = result["settings"]
settings.to_csv(OUT / "parametry.csv", sep=";", index=False, encoding="utf-8-sig")

heads = list(boundaries.columns)
phase_columns = [h for h in heads if str(h).startswith("Фаза")]
lines, nodes, line_phases = set(), set(), set()
for _index, row in boundaries.iterrows():
    kind = str(row["Тип"])
    if kind.startswith("Граница"):
        lines.add(row["Группа"])
        for column in phase_columns[:1]:
            line_phases.add(str(row[column]))
    elif kind.startswith("Инвариант"):
        nodes.add(row["Группа"])

from thermogar_palette import resolve_figure  # noqa: E402

figure = resolve_figure(result["figure"], "light")
figure.savefig(OUT / "umolch8_ni.png", dpi=100)

summary = {
    "inputs": inputs,
    "seconds": round(elapsed, 1),
    "errors": errors,
    "exceptions": exceptions,
    "rows": int(len(boundaries)),
    "columns": heads,
    "lines": len(lines),
    "nodes": len(nodes),
    "line_phases": sorted(line_phases),
    "all_phase_values": sorted(
        {str(value) for column in phase_columns for value in boundaries[column].dropna()}
    ),
    "temperature_range_c": [
        float(boundaries[c].min()) if c in boundaries else None for c in heads if "°C" in str(c)
    ],
}
(OUT / "itog.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
