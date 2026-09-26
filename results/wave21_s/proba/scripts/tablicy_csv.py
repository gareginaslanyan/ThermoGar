"""Опись 64 вызовов st.dataframe / st.data_editor в tablicy.csv (UTF-8 с BOM, «;»).

Строки ROW собраны чтением кода (шаг 1 задания 21-С); здесь только сборка
и столбцы «серое None» и «пример».
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(sys.argv[1])  # папка с A.txt … E.txt
REPO = ROOT.parents[1]

rows = []
for name in ("A", "B", "C", "D", "E"):
    for line in (SOURCE / f"{name}.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("ROW;"):
            parts = re.split(r";(?! )", line)[1:]  # «; » внутри текста поля — не разделитель
            assert len(parts) == 7, line
            rows.append(parts)

# Проверка: список вызовов совпадает с кодом.
calls = []
for path in sorted((REPO / "app").glob("*.py")):
    for number, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(r"st\.(dataframe|data_editor|table)\(", text):
            calls.append(f"app/{path.name}:{number}")
assert sorted(calls) == sorted(r[0] for r in rows), set(calls) ^ {r[0] for r in rows}

EXAMPLES = dict(line.split("\t", 1) for line in (SOURCE / "primery.tsv").read_text(encoding="utf-8").splitlines() if "\t" in line)
NONE_KIND = dict(line.split("\t", 1) for line in (SOURCE / "none.tsv").read_text(encoding="utf-8").splitlines() if "\t" in line)

order = {call: index for index, call in enumerate(calls)}
rows.sort(key=lambda r: order[r[0]])
HEAD = [
    "№", "файл:строка", "экран (раздел → вкладка / вид)", "таблица, столбцы", "редактируемая",
    "столбцы с возможной пустой ячейкой", "когда пусто и чем (по коду)", "обработка показа сейчас",
    "серое «None» на экране возможно", "пример (кадр / тест) или «по коду»",
]
with (ROOT / "tablicy.csv").open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.writer(handle, delimiter=";")
    writer.writerow(HEAD)
    for index, row in enumerate(rows, 1):
        writer.writerow([index, *row, NONE_KIND[row[0]], EXAMPLES.get(row[0], "по коду")])
print(len(rows))
