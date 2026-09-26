"""Сводка замеров пробы 21-С в proba.csv (UTF-8 с BOM, «;»).

Источник: proba/zamery.json (kadry.py) и просмотр кадров results/wave21_s/kadry/.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
zamery = json.loads((ROOT / "zamery.json").read_text(encoding="utf-8"))


def column(key, name, index):
    return " | ".join(row[index] if row[index] != "" else "·" for row in zamery[key][name])


def csv_one_line(key):
    text = zamery[key].get("csv") or zamery[key].get("csv_error", "")
    return text.strip().replace("\n", " ⏎ ")


VIEW = {
    "a": ("серое «None»", "вправо", "по умолчанию Streamlit: до 4 знаков, хвостовые нули убраны (702.4637)"),
    "a2": ("серое «None» (na_rep не действует)", "вправо", "формат Styler: 6 знаков (0.200000, 702.463712)"),
    "b": ("пустая ячейка", "влево (столбец текстовый)", "текст в виде как в а (702.4637)"),
    "c": ("«—» обычным цветом, не серым", "влево (столбец текстовый)", "текст в виде как в а (702.4637)"),
    "g0": ("пустая ячейка (placeholder=\"\")", "вправо", "как в а"),
    "g1": ("серое «—» (placeholder=\"—\")", "вправо", "как в а"),
}
SORT = {
    "a": "числовая", "a2": "числовая", "b": "по тексту: 98.7 после 702.4637",
    "c": "по тексту: 98.7 после 702.4637", "g0": "числовая", "g1": "числовая",
}
DOWNLOAD = {
    "a": "исходные числа полностью, пусто — пустое поле",
    "a2": "исходные числа полностью (Styler не влияет), пусто — пустое поле",
    "b": "текст как на экране (округлён до 4 знаков), пусто — пустое поле",
    "c": "текст как на экране, в пустых — «—»",
    "g0": "исходные числа полностью, пусто — пустое поле (placeholder в файл не идёт)",
    "g1": "исходные числа полностью, пусто — пустое поле (placeholder в файл не идёт)",
}
EDIT = {
    "a": ("принят: 200.0 (float64)", "ячейка снова серое «None», в данных NaN"),
    "a2": ("как а: Styler в st.data_editor действует только на нередактируемые столбцы (streamlit/elements/widgets/data_editor.py:813), в пробе для редактора а2 = а", "как а"),
    "b": ("принят строкой '200' (object)", "ячейка показывает серое «None», в данных None"),
    "c": ("принят строкой '200' (object); «—» в других строках остаётся в данных строкой '—'", "ячейка показывает серое «None», в данных None"),
    "g0": ("принят: 200.0 (float64)", "ячейка пустая (placeholder), в данных NaN"),
    "g1": ("принят: 200.0 (float64)", "ячейка серое «—» (placeholder), в данных NaN"),
}

HEAD = [
    "вариант", "таблица", "кадр светлый", "кадр тёмный", "кадры сортировки", "кадр ввода",
    "вид пустой ячейки", "выравнивание чисел", "вид чисел", "сортировка щелчком",
    "по возрастанию (столбец)", "по убыванию (столбец)", "скачивание с панели таблицы",
    "файл скачивания (дословно)", "ввод 200 в E у FCC_A1", "очистка E у BCC_A2",
    "что вернул редактор (дословно)",
]
rows = []
for page, title, index in (("t0", "как T₀: столбец «T₀, °C»", 1), ("el", "как «Упругие свойства» (st.data_editor): столбец «E, ГПа»", 3)):
    for variant in ("a", "a2", "b", "c", "g0", "g1"):
        key = f"{page}_{variant}_svet"
        view = VIEW[variant]
        if page == "el" and variant == "a2":
            view = ("серое «None» (Styler к редактору не применялся)", "вправо", "как а")
        edit = EDIT[variant] if page == "el" else ("—", "—")
        rows.append([
            variant, title,
            f"kadry/{page}_{variant}_svet.png", f"kadry/{page}_{variant}_tyomn.png",
            f"kadry/{key}_sort1.png, kadry/{key}_sort2.png",
            f"kadry/{key}_vvod.png" if page == "el" else "—",
            view[0], view[1], view[2], SORT[variant] if page == "t0" else (
                "по тексту" if variant in ("b", "c") else "числовая"),
            column(key, "sort1", index), column(key, "sort2", index),
            DOWNLOAD[variant] + ("; заголовки — ключи данных (young_gpa…), не подписи столбцов" if page == "el" else ""),
            csv_one_line(key), edit[0], edit[1],
            zamery[key].get("vvod_vozvrat", "—").replace("\n", " ⏎ "),
        ])

with (ROOT.parent / "proba.csv").open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.writer(handle, delimiter=";")
    writer.writerow(HEAD)
    writer.writerows(rows)
print(len(rows))
