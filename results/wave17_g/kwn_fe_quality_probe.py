"""Диагностика 17-Г: какая проверка качества KWN Fe не проходит.

Повторяет шаги `tools/test_ui_g.py::test_kwn_precipitation[fe]` один в один
(тот же KWN_CELL, SHORT_TIME_H, KWN_BINS) и печатает таблицу
`PrecipitationResult.quality` — ту самую, по которой
`app/thermogar_precipitation.py:1619` решает, показать «пройдены» или
«не пройдены». Приложение и тесты не правятся, читается только результат.

    python -B -X utf8 results/wave17_g/kwn_fe_quality_probe.py
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("MPLBACKEND", "Agg")

import test_ui_g as t  # noqa: E402

matrix, precipitate, temperature = t.KWN_CELL["fe"]
app = t.start_app("fe")
state = app.session_state
state["precipitation_fe_user_matrix"] = matrix
state["precipitation_fe_user_precipitate"] = precipitate
state["precipitation_fe_user_temperature_c"] = temperature
state["precipitation_fe_user_duration_h"] = t.SHORT_TIME_H
state["precipitation_fe_user_bins"] = t.KWN_BINS
app.run()
t.widget(app, "button", "precipitation_fe_user_calculate").click().run()

lines = [
    f"матрица / выделение: {matrix} / {precipitate}, {temperature} °C",
    f"время модели, ч: {t.SHORT_TIME_H}; классов сетки: {t.KWN_BINS}",
    f"ошибки на экране: {t.new_errors(app)}",
    "",
]
try:
    result = app.session_state["thermogar_precipitation_result"]
except (KeyError, AttributeError):
    result = None
if result is None:
    lines.append("результата в session_state нет")
else:
    lines.append(f"строк кинетики: {len(result.kinetics)}")
    lines.append(f"stop_note: {getattr(result, 'stop_note', '')!r}")
    lines.append(f"warnings: {list(getattr(result, 'warnings', ()) or ())}")
    lines.append("")
    lines.append("таблица проверок:")
    for row in result.quality.to_dict(orient="records"):
        lines.append(f"  [{row['Статус']}] {row['Проверка']} — {row['Примечание']}")

text = "\n".join(lines)
(Path(__file__).resolve().parent / "kwn_fe_quality_probe.txt").write_text(text + "\n", encoding="utf-8")
print(text)
