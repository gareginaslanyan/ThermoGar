"""Сверка исходов test_backend_calculations выпуска 0.5.0 с эталоном 17-Г и вердикт (сценарий 21-Э
для задачи выпуска 21-Ю). Копия results/wave19_d/backend_compare.py; отличия:

* каталог вывода — одна переменная RELEASE_OUT в начале скрипта (results/wave21_yu/); исходы берутся
  из RELEASE_OUT/regress_backend, сверка пишется в RELEASE_OUT/backend_compare.txt. Для холостого
  прогона оба пути задаются аргументами: каталог исходов и файл вывода;
* времена («с/точку», «всего, с» в ячейках «Проекты/batch») при сличении отбрасываются: эталон
  времена исходами не считает (так сказано и в шапке 19-Д, но в 19-Д они сличались — три ячейки
  batch выходили «с разницей» из-за одних времён);
* вердикт. 22-Б законно сменил число строк кинетики KWN стали 2391 на 1123
  (tools/backend_reference.md:238, коммит c1577ca). «PASS» — если разница ровно в одной ячейке
  «[Кинетика] KWN (модуль) | fe» и «строк кинетики» в ней 1123; иначе «FAIL» со списком ячеек.

    python -B -X utf8 results/wave21_eh/scripts/backend_compare.py [каталог исходов] [файл вывода]

Прежняя шапка 19-Д:
19-Д, шаг 5: копия results/wave18_g/backend_compare.py (18-Г в подписях заменён на 19-Д). Сверка исходов test_backend_calculations с эталоном tools/backend_reference.md.

Эталон сверен побайтово в 17-Г (results/wave17_g/backend/reference_check.md: «ни одна
строка не изменилась»), его исходы — results/wave17_g/backend/backend_report_*.json.
Здесь обе пары отчётов разворачиваются одним кодом в строки «ячейка | ключ = repr(значение)»
без времён (эталон времена исходами не считает) и сличаются построчно.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RELEASE_OUT = ROOT / "results" / "wave21_yu"  # каталог вывода задачи выпуска 21-Ю
NEW_DIR = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else RELEASE_OUT / "regress_backend"
REPORT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else RELEASE_OUT / "backend_compare.txt"
SOURCES = {"17-Г": ROOT / "results/wave17_g/backend", "0.5.0": NEW_DIR}
TIME_KEYS = {"с/точку", "всего, с"}
KWN_FE = "[Кинетика] KWN (модуль) | fe"
KWN_ROWS_KEY = "строк кинетики"
KWN_FE_ROWS = 1123  # 22-Б: было 2391


def flat(folder: Path) -> tuple[dict[str, list[str]], dict[str, dict]]:
    cells: dict[str, list[str]] = {}
    numbers: dict[str, dict] = {}
    for tag in ("notslow", "slow"):
        for rec in json.loads((folder / f"backend_report_{tag}.json").read_text("utf-8")):
            name = f"[{rec.get('section')}] {rec.get('cell')} | {rec.get('db')}"
            lines = [f"status = {rec.get('status')!r}", f"error = {rec.get('error')!r}"]
            lines += [f"{k} = {v!r}" for k, v in (rec.get("numbers") or {}).items() if k not in TIME_KEYS]
            cells[name] = lines
            numbers[name] = rec.get("numbers") or {}
    return cells, numbers


(old, _), (new, new_numbers) = (flat(p) for p in SOURCES.values())
report = [f"исходы 0.5.0: {NEW_DIR}",
          f"ячеек: 17-Г {len(old)}, 0.5.0 {len(new)}",
          f"статусы 0.5.0: {sorted({l for c in new.values() for l in c if l.startswith('status')})}"]
differ: list[str] = []
for name in sorted(set(old) | set(new)):
    a, b = old.get(name), new.get(name)
    if a == b:
        continue
    differ.append(name)
    report.append("")
    report.append(f"РАЗНИЦА {name}")
    if a is None or b is None:
        report.append(f"  нет в {'17-Г' if a is None else '0.5.0'}")
        continue
    for line in a:
        if line not in b:
            report.append(f"  - {line}")
    for line in b:
        if line not in a:
            report.append(f"  + {line}")
report.insert(3, f"ячеек с разницей: {len(differ)}")

kwn_rows = new_numbers.get(KWN_FE, {}).get(KWN_ROWS_KEY)
report.append("")
report.append(f"{KWN_FE}: {KWN_ROWS_KEY} = {kwn_rows!r} (ожидается {KWN_FE_ROWS}, 22-Б)")
if differ == [KWN_FE] and kwn_rows == KWN_FE_ROWS:
    report.append("ВЕРДИКТ: PASS")
else:
    report.append("ВЕРДИКТ: FAIL")
    wrong = [name for name in differ if name != KWN_FE]
    if kwn_rows != KWN_FE_ROWS:
        wrong.append(f"{KWN_FE} ({KWN_ROWS_KEY} {kwn_rows!r}, нужно {KWN_FE_ROWS})")
    report += [f"  {name}" for name in wrong]
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_bytes(("\n".join(report) + "\n").encode("utf-8"))
print("\n".join(report))
