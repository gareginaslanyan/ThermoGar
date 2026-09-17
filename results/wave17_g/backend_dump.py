"""Пункт 4: выкладка исходов test_backend_calculations для сверки с tools/backend_reference.md.

Читает отчёты по ячейкам, записанные THERMOGAR_BACKEND_REPORT в двух прогонах
(-m "not slow" и -m slow), и пишет их в один текстовый файл в UTF-8 —
по ячейке на блок. Ничего не правит.

    python -B -X utf8 results/wave17_g/backend_dump.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
BACKEND = OUT / "backend"

lines = []
for tag in ("notslow", "slow"):
    path = BACKEND / f"backend_report_{tag}.json"
    lines.append(f"===== {path.name} =====")
    if not path.exists():
        lines.append("(нет файла)")
        continue
    data = json.loads(path.read_text(encoding="utf-8"))
    lines.append(f"ячеек: {len(data)}")
    for rec in data:
        lines.append("")
        lines.append(f"[{rec.get('section')}] {rec.get('cell')} | db={rec.get('db')} | "
                     f"{rec.get('status')} | {rec.get('seconds')} c")
        if rec.get("error"):
            lines.append(f"  error: {rec['error']}")
        for key, value in (rec.get("numbers") or {}).items():
            lines.append(f"  {key} = {value!r}")
    lines.append("")

(BACKEND / "cells_dump.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"записано: {BACKEND / 'cells_dump.txt'}")
