"""Сверка замеров 21-Я: zamer_do.json и zamer_posle.json → sravnenie.md.

Для замены: прежний текст (элемент до правки) против ::after после правки —
размер ±0.5 px, насыщенность, цвет и высота строки равны; сам элемент после
правки — font-size 0px (английский текст не виден). Для мест сравнения
(вариант списка, подсказка «?», подсказка кнопки над таблицей) — текст и стиль
элемента до и после совпадают.

Запуск: python -X utf8 results/wave21_ya/scripts/sravnenie.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1]
TOLERANCE_PX = 0.5


def px(value: str) -> float | None:
    return float(value[:-2]) if value.endswith("px") else None


def first_visible(record: dict) -> dict | None:
    visible = [item for item in record["found"] if item["visible"]]
    return visible[0] if visible else None


def check(before: dict, after: dict) -> tuple[str, str, bool]:
    """(было, стало, совпало) для одной пары записей."""

    old = first_visible(before)
    new = first_visible(after)
    if before["place"].endswith("итог"):
        return before["note"], after["note"], True
    if old is None:
        return "не найдено", "—", False
    style = old["element"]
    was = f'«{old["text"]}» {style["fontSize"]} {style["fontWeight"]} {style["color"]} {style["lineHeight"]}'
    comparison = before["place"].startswith("сравнение")
    if comparison or before["selector"] == "input::placeholder":
        if new is None:
            return was, "не найдено", False
        cur = new["element"]
        became = f'«{new["text"]}» {cur["fontSize"]} {cur["fontWeight"]} {cur["color"]} {cur["lineHeight"]}'
        same_style = all(style[key] == cur[key] for key in ("fontSize", "fontWeight", "color", "lineHeight"))
        if not comparison:
            return was, became, same_style and new["text"] != old["text"]
        return was, became, same_style and new["text"] == old["text"]
    if new is None:
        # Размер файла у карточки: display: none — текста нет.
        hidden = all(item["element"]["display"] == "none" for item in after["found"])
        return was, "скрыто (display: none)" if hidden else "не найдено", hidden
    pseudo = new["after"]
    became = (
        f'{pseudo["content"]} {pseudo["fontSize"]} {pseudo["fontWeight"]} '
        f'{pseudo["color"]} {pseudo["lineHeight"]}; элемент {new["element"]["fontSize"]}'
    )
    ok = (
        new["element"]["fontSize"] == "0px"
        and pseudo["content"] not in ("none", "normal")
        and abs(px(pseudo["fontSize"]) - px(style["fontSize"])) <= TOLERANCE_PX
        and pseudo["fontWeight"] == style["fontWeight"]
        and pseudo["color"] == style["color"]
        and pseudo["lineHeight"] == style["lineHeight"]
    )
    return was, became, ok


def main() -> int:
    before = json.loads((OUT / "zamer_do.json").read_text("utf-8"))
    after = json.loads((OUT / "zamer_posle.json").read_text("utf-8"))
    lines = [
        "| Тема | Место | Было: текст, размер, насыщенность, цвет, высота строки | "
        "Стало (::after) | Кадры до / после | Итог |",
        "|---|---|---|---|---|---|",
    ]
    failures = 0
    for theme, data in before["themes"].items():
        new_records = {
            record["place"]: record for record in after["themes"][theme]["records"]
        }
        for record in data["records"]:
            pair = new_records.get(record["place"])
            if pair is None:
                continue
            was, became, ok = check(record, pair)
            failures += not ok
            frames = f'{record["frame"]} / {pair["frame"]}'
            lines.append(
                f'| {theme} | {record["place"]} | {was} | {became} | {frames} | '
                f'{"да" if ok else "НЕТ"} |'
            )
        # Места, которых до правки не было (подсказка к 65 МБ).
        old_places = {record["place"] for record in data["records"]}
        for place, pair in new_records.items():
            if place in old_places:
                continue
            new = first_visible(pair)
            pseudo = new["after"] if new else {}
            became = (
                f'{pseudo.get("content")} {pseudo.get("fontSize")} {pseudo.get("fontWeight")} '
                f'{pseudo.get("color")} {pseudo.get("lineHeight")}; элемент '
                f'{new["element"]["fontSize"] if new else "—"}; под ним «{new["text"] if new else ""}»'
            )
            ok = bool(new) and new["element"]["fontSize"] == "0px"
            failures += not ok
            lines.append(
                f'| {theme} | {place} | до правки подсказки не было | {became} | '
                f'— / {pair["frame"]} | {"да" if ok else "НЕТ"} |'
            )
    text = "\n".join(lines) + "\n"
    (OUT / "sravnenie.md").write_text(text, encoding="utf-8", newline="\n")
    print(text)
    print(f"расхождений: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
