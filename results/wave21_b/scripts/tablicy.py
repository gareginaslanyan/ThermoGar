"""21-B: markdown tables for the design-audit report from izmereniya.json and
the frame manifest. Prints to stdout; the report quotes the output.

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 results\\wave21_b\\scripts\\tablicy.py
"""

from __future__ import annotations

import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[1]
M = json.loads((RESULTS / "izmereniya.json").read_text(encoding="utf-8"))
FRAMES = json.loads((RESULTS / "kadry" / "_manifest.json").read_text(encoding="utf-8"))["frames"]
THEMES = ("Light", "Dark")
NAME = {"Light": "светлая", "Dark": "тёмная"}


def ratio_str(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}".replace(".", ",") + ":1"


def verdict(value: float | None, limit: float) -> str:
    if value is None:
        return "нет замера"
    return "проходит" if value >= limit else "**нет**"


def styles(theme):
    return M[theme]["styles"]


def first(theme, getter):
    for key, entry in styles(theme).items():
        value = getter(entry)
        if value:
            return key, value
    return None, None


def colour_table() -> None:
    rows = [
        ("Фон окна", lambda e: e["colours"]["window_bg"] and e["colours"]["window_bg"]["value"]),
        ("Боковая панель", lambda e: e["colours"]["sidebar_bg"] and e["colours"]["sidebar_bg"]["value"]),
        ("Раскрытие: фон", lambda e: e["colours"]["expander_bg"] and e["colours"]["expander_bg"]["value"]),
        ("Раскрытие: рамка", lambda e: e["colours"]["expander_border"] and e["colours"]["expander_border"]["value"]),
        ("Контейнер/форма с рамкой: фон", lambda e: e["colours"]["bordered_container_bg"] and e["colours"]["bordered_container_bg"]["value"]),
        ("Контейнер/форма с рамкой: рамка", lambda e: e["colours"]["bordered_container_border"] and e["colours"]["bordered_container_border"]["value"]),
        ("Основной текст", lambda e: painted(e, "body_text")),
        ("st.caption", lambda e: painted(e, "caption")),
        ("Подпись виджета", lambda e: painted(e, "widget_label")),
        ("Поле ввода: заливка", lambda e: e["colours"]["input_bg"] and e["colours"]["input_bg"]["value"]),
        ("Поле ввода: рамка", lambda e: e["colours"]["input_border"] and e["colours"]["input_border"]["value"]),
        ("Ссылка", lambda e: painted(e, "link")),
    ]
    print("| Элемент | Светлая | Тёмная |")
    print("|---|---|---|")
    for title, getter in rows:
        cells = []
        for theme in THEMES:
            _, value = first(theme, getter)
            cells.append(value or "не найден")
        print(f"| {title} | {cells[0]} | {cells[1]} |")
    cells = []
    for theme in THEMES:
        head = M[theme].get("dataframe_header") or {}
        cells.append(f"фон {head.get('header_bg')}, текст ≈{head.get('header_text')}")
    print(f"| Заголовок таблицы (st.dataframe, canvas; по пикселям) | {cells[0]} | {cells[1]} |")


def painted(entry, key):
    item = entry["colours"].get(key)
    if not item:
        return None
    if item.get("opacity", 1) < 1:
        return f"{item['value']} × opacity {item['opacity']} = {item['painted']}"
    return item["value"]


def font_table() -> None:
    print("| Уровень | Кегль | Насыщенность | Интерлиньяж | Где взят |")
    print("|---|---|---|---|---|")
    for level, title in (
        ("h1", "Заголовок экрана (h1)"),
        ("h2", "Заголовок блока h2"),
        ("h3", "Заголовок блока h3"),
        ("h4", "Заголовок блока h4"),
        ("body", "Основной текст"),
        ("caption", "st.caption"),
        ("widget_label", "Подпись виджета"),
    ):
        key, value = first("Light", lambda e: e["fonts"].get(level))
        if value is None:
            print(f"| {title} | — | — | — | на экранах нет |")
            continue
        print(f"| {title} | {value['size']} | {value['weight']} | {value['lineHeight']} | {key}: «{value['text'][:30]}» |")


def min_pair(theme, what):
    best = None
    for key, entry in styles(theme).items():
        for item in entry["contrast"]:
            if item["what"] == what and (best is None or item["ratio"] < best[1]["ratio"]):
                best = (key, item)
    return best


def alert_pair(theme, kind):
    for key, entry in styles(theme).items():
        item = (entry.get("alerts") or {}).get(kind)
        if item:
            return key, item
    messages = (M[theme].get("messages") or {}).get("alerts") or {}
    if messages.get(kind):
        return "сообщение об ошибке состава", messages[kind]
    return None


def contrast_table() -> None:
    print("| Пара | Тема | Цвет / фон | Контраст | Порог | Итог | Где (худший случай) |")
    print("|---|---|---|---|---|---|---|")
    pairs = [
        ("основной текст / фон окна", 4.5),
        ("caption / фон окна", 4.5),
        ("caption / боковая панель", 4.5),
        ("caption / раскрытие", 4.5),
        ("подпись виджета / фон окна", 4.5),
        ("ссылка / фон", 4.5),
        ("рамка поля ввода / фон окна (3:1)", 3.0),
        ("поле ввода: заливка / фон окна (граница, 3:1)", 3.0),
        ("рамка раскрытия / фон окна (3:1)", 3.0),
    ]
    for what, limit in pairs:
        for theme in THEMES:
            found = min_pair(theme, what)
            if not found:
                print(f"| {what} | {NAME[theme]} | — | — | {ratio_str(limit)} | нет замера | — |")
                continue
            key, item = found
            print(f"| {what} | {NAME[theme]} | {item['fg']} / {item['bg']} | {ratio_str(item['ratio'])} "
                  f"| {ratio_str(limit)} | {verdict(item['ratio'], limit)} | {key} |")
    for kind in ("error", "warning", "info", "success"):
        for theme in THEMES:
            found = alert_pair(theme, kind)
            if not found:
                print(f"| текст st.{kind} / подложка | {NAME[theme]} | — | — | 4,50:1 | нет замера | — |")
                continue
            key, item = found
            print(f"| текст st.{kind} / подложка | {NAME[theme]} | {item['fg']} / {item['bg']} "
                  f"| {ratio_str(item['ratio'])} | 4,50:1 | {verdict(item['ratio'], 4.5)} | {key} |")
    for theme in THEMES:
        head = M[theme].get("dataframe_header") or {}
        if head.get("header_text"):
            ratio = contrast_hex(head["header_text"], head["header_bg"])
            print(f"| заголовок st.dataframe / его фон (по пикселям) | {NAME[theme]} | "
                  f"{head['header_text']} / {head['header_bg']} | {ratio_str(ratio)} | 4,50:1 | "
                  f"{verdict(ratio, 4.5)} | Проекты и данные / Справочник фаз |")


def contrast_hex(fg: str, bg: str) -> float:
    def lum(value):
        channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    a, b = lum(fg), lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def paragraph_table() -> None:
    print("| Вкладка | Абзацев > 80 знаков | Самая длинная строка, знаков | Ширина этого абзаца, px | Абзацев со строкой > 75 | Пример |")
    print("|---|---|---|---|---|---|")
    data = M["Light"]["paragraphs"]
    groups: dict[str, list] = {}
    for key, items in data.items():
        top = key.split(" / ")[0]
        groups.setdefault(top, []).extend(items)
    for top, items in groups.items():
        if not items:
            print(f"| {top} | 0 | — | — | 0 | — |")
            continue
        worst = max(items, key=lambda item: item["longest_line_chars"])
        over = sum(1 for item in items if item["longest_line_chars"] > 75)
        print(f"| {top} | {len(items)} | {worst['longest_line_chars']} | {worst['width_px']} | {over} "
              f"| {worst['kind']}: «{worst['sample'][:50]}…» |")


def s5_table() -> None:
    print("| Вкладка | Тема | scrollWidth / innerWidth | Гориз. прокрутка документа | stMain scrollWidth / clientWidth | Кадр |")
    print("|---|---|---|---|---|---|")
    for theme in THEMES:
        s5 = M[theme].get("s5") or {}
        for top, numbers in (s5.get("tabs") or {}).items():
            print(f"| {top} | {NAME[theme]} | {numbers['doc_scrollWidth']} / {numbers['innerWidth']} "
                  f"| {'да' if numbers['doc_hscroll'] else 'нет'} | {numbers['main_scrollWidth']} / "
                  f"{numbers['main_clientWidth']} | {numbers['frame']} |")
    for theme in THEMES:
        side = (M[theme].get("s5") or {}).get("sidebar")
        if side:
            print(f"\nПанель свёрнута ({NAME[theme]}): стрелка раскрытия видна — "
                  f"{'да' if side['expand_button_visible'] else 'нет'}, рамка {side['expand_button_box']}, "
                  f"стиль {side['expand_button_style']}; кадр {side['frame']}.")


def frame_table() -> None:
    print("| № | Что на кадре | Светлая | Тёмная | Серые копии | Сообщения в кадре |")
    print("|---|---|---|---|---|---|")
    by_number: dict[str, dict] = {}
    for frame in FRAMES:
        number = frame["files"][0][:2]
        by_number.setdefault(number, {})[frame["theme"]] = frame
    for number in sorted(by_number):
        pair = by_number[number]
        any_frame = pair.get("Light") or pair.get("Dark")
        files = {theme: ", ".join(pair[theme]["files"]) if theme in pair else "—" for theme in THEMES}
        greys = sum(len(pair[theme]["grey"]) for theme in pair)
        kinds = sorted({alert["kind"] for theme in pair for alert in pair[theme]["alerts"]})
        print(f"| {number} | {any_frame['what']} | {files['Light']} | {files['Dark']} "
              f"| {greys or '—'} | {', '.join(kinds) or '—'} |")


if __name__ == "__main__":
    for title, function in (
        ("ЦВЕТА", colour_table),
        ("ШРИФТЫ", font_table),
        ("КОНТРАСТ", contrast_table),
        ("АБЗАЦЫ", paragraph_table),
        ("S-5", s5_table),
        ("КАДРЫ", frame_table),
    ):
        print(f"\n### {title}\n")
        function()
