"""19-Д, шаг 5: копия results/wave18_g/backend_compare.py (18-Г в подписях заменён на 19-Д). Сверка исходов test_backend_calculations с эталоном tools/backend_reference.md.

Эталон сверен побайтово в 17-Г (results/wave17_g/backend/reference_check.md: «ни одна
строка не изменилась»), его исходы — results/wave17_g/backend/backend_report_*.json.
Здесь обе пары отчётов разворачиваются одним кодом в строки «ячейка | ключ = repr(значение)»
без времён (эталон времена исходами не считает) и сличаются построчно.

    python -B -X utf8 results/wave19_d/backend_compare.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SOURCES = {"17-Г": ROOT / "results/wave17_g/backend", "19-Д": OUT / "regress_backend"}


def flat(folder: Path) -> dict[str, list[str]]:
    cells: dict[str, list[str]] = {}
    for tag in ("notslow", "slow"):
        for rec in json.loads((folder / f"backend_report_{tag}.json").read_text("utf-8")):
            name = f"[{rec.get('section')}] {rec.get('cell')} | {rec.get('db')}"
            lines = [f"status = {rec.get('status')!r}", f"error = {rec.get('error')!r}"]
            lines += [f"{k} = {v!r}" for k, v in (rec.get("numbers") or {}).items()]
            cells[name] = lines
    return cells


old, new = (flat(p) for p in SOURCES.values())
report = [f"ячеек: 17-Г {len(old)}, 19-Д {len(new)}",
          f"статусы 19-Д: {sorted({l for c in new.values() for l in c if l.startswith('status')})}"]
for name in sorted(set(old) | set(new)):
    a, b = old.get(name), new.get(name)
    if a == b:
        continue
    report.append("")
    report.append(f"РАЗНИЦА {name}")
    if a is None or b is None:
        report.append(f"  нет в {'17-Г' if a is None else '19-Д'}")
        continue
    for line in a:
        if line not in b:
            report.append(f"  - {line}")
    for line in b:
        if line not in a:
            report.append(f"  + {line}")
changed = sum(1 for line in report if line.startswith("РАЗНИЦА"))
report.insert(2, f"ячеек с разницей: {changed}")
(OUT / "backend_compare.txt").write_text("\n".join(report) + "\n", "utf-8")
print("\n".join(report))
