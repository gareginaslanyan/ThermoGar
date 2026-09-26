"""21-M, step 8: the table results/wave21_m/zamery.csv (UTF-8 with BOM, «;»).

Sources: kadry_21m.json (kadry_21m.py), kolco.json (kolco.py),
fokus/fokus_do_svodka.csv and fokus/fokus_posle_svodka.csv (fokus.py),
umolch8/itog.json (progon_umolch8.py). One row per measurement:

    замер; тема; экран / элемент; величина; значение; кадр

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_m\\scripts\\zamery.py
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
THEME = {"Light": "светлая", "Dark": "тёмная"}


def main() -> int:
    rows: list[list[str]] = []
    record = json.loads((OUT / "kadry_21m.json").read_text("utf-8"))

    for theme, screens in record.get("pervyi", {}).items():
        for item in screens:
            button = item["button"]
            rows.append([
                "первый экран", THEME[theme], item["screen"],
                f"«{button['text']}»: низ кнопки, px (окно 900)",
                f"{button['bottom']} — {'да' if item['first_screen'] else 'нет'}",
                item.get("frame") or "",
            ])
        total = sum(1 for item in screens if item["first_screen"])
        rows.append(["первый экран", THEME[theme], "итого (ni)",
                     "основная кнопка на первом экране, экранов из 21", f"{total} из {len(screens)}", ""])

    for theme, entry in record.get("binarnaya", {}).items():
        for key, what in (("row_before", "по умолчанию"), ("row_after", "«Шаг по температуре, °C» = 20")):
            row = entry[key]
            rows.append([
                "Бинарная T–X ni", THEME[theme], f"строка кнопки, {what}",
                "position; верх–низ строки, px; подписи",
                f"{row['position']}; {row['top']}–{row['bottom']}; {' | '.join(row['captions']) or '—'}",
                entry["first_screen" if key == "row_before" else "first_screen_changed"],
            ])

    for theme, entry in record.get("knopki", {}).items():
        for key, what in (
            ("vklady_pusto", "«Вклады упрочнения», пусто"),
            ("vklady_istochnik", "«Вклады упрочнения», источник без галочки"),
            ("uprugie_shag2", "«Упругие свойства», шаг 2"),
        ):
            row = entry[key]["row"]
            button = row["button"]
            rows.append([
                "неактивная кнопка", THEME[theme], what,
                f"«{button['text']}»: неактивна; подпись под кнопкой",
                f"{'да' if button['disabled'] else 'нет'}; {' | '.join(row['captions']) or '—'}",
                entry[key]["frame"],
            ])

    for key, entry in record.get("umolch", {}).items():
        theme = "светлая" if key.endswith("_svet") else "тёмная"
        metrics = "; ".join(f"{m['label']} = {m['value']}" for m in entry["metrics"]) or "—"
        rows.append([
            f"умолчание {entry['decision']}", theme, f"{entry['screen']} ({entry['base']})",
            "время расчёта, с; плитки результата",
            f"{entry['seconds']}{'' if entry['idle'] else ' (не завершён)'}; {metrics}",
            ", ".join(entry["frames"]),
        ])

    for theme, entry in record.get("zatverdevanie", {}).items():
        labels = [label for label in entry["labels"] if "0.0001–5" in label]
        rows.append(["подписи 13", THEME[theme], "Затвердевание, «Точность и критерии»",
                     "подписи с «(0.0001–5)»", " | ".join(labels), ", ".join(entry["frames"])])

    kolco = OUT / "kolco.json"
    if kolco.exists():
        for item in json.loads(kolco.read_text("utf-8")):
            what = {"knopka": "основная кнопка «Рассчитать однофазную диффузию»",
                    "pereklyuchatel": "переключатель, «Однофазная пара»"}[item["control"]]
            rows.append([
                "кольцо фокуса", THEME[item["theme"]], what,
                "кольцо по пикселям : окно; box-shadow",
                f"{item.get('ring_px')} : {item.get('window_px')} = {item.get('ring_to_window')}:1; "
                f"{item['box_shadow']}",
                ", ".join(item["frames"]),
            ])

    for stage, name in (("до", "fokus_do_svodka.csv"), ("после", "fokus_posle_svodka.csv")):
        path = OUT / "fokus" / name
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig") as handle:
            data = list(csv.DictReader(handle, delimiter=";"))
        for theme in ("Light", "Dark"):
            counts = Counter(row["класс кольца"] for row in data if row["тема"] == theme)
            rows.append([
                "кольцо фокуса, обход Tab", THEME[theme], f"5 экранов, {stage} правки",
                "остановок фокуса по классу кольца",
                "; ".join(f"{k} {v}" for k, v in sorted(counts.items())), name,
            ])

    itog = OUT / "umolch8" / "itog.json"
    if itog.exists():
        data = json.loads(itog.read_text("utf-8"))
        rows.append([
            "умолчание 8Б (AppTest)", "—", "Диаграммы / Многокомпонентное T–X (ni)",
            "время, с; линий границ; узлов; фазы линий",
            f"{data['seconds']}; {data['lines']}; {data['nodes']}; {', '.join(data['line_phases'])}",
            "umolch8/umolch8_ni.png",
        ])

    with (OUT / "zamery.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["замер", "тема", "экран / элемент", "величина", "значение", "кадр"])
        writer.writerows(rows)
    print(f"rows {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
