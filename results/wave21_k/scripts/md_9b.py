"""21-К: таблицы раздела 9Б по экранам из results/wave21_k/predlozhenie_9b.csv.

Печатает Markdown в results/wave21_k/9b_po_ekranam.md; этот текст вставлен в
tasks/PREDLOZHENIE_9B_10B_21.md без правки чисел.

Запуск из корня дерева:
    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe results\\wave21_k\\scripts\\md_9b.py
"""

from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "results" / "wave21_k" / "predlozhenie_9b.csv"
FORMY = ROOT / "results" / "wave21_k" / "formy.csv"
OUT = ROOT / "results" / "wave21_k" / "9b_po_ekranam.md"


def cell(text: str) -> str:
    if text.startswith("ni: "):
        text = text[4:]
    return text.replace("|", "\\|").replace("\n", " ")


def main() -> None:
    rows = list(csv.DictReader(SRC.open(encoding="utf-8-sig"), delimiter=";"))
    screens: "OrderedDict[str, list[dict[str, str]]]" = OrderedDict()
    for row in rows:
        screens.setdefault(row["экран"], []).append(row)
    formy = list(csv.DictReader(FORMY.open(encoding="utf-8-sig"), delimiter=";"))
    info: dict[str, dict[str, str]] = {}
    expanders: dict[str, list[str]] = {}
    for row in formy:
        info.setdefault(row["экран"], row)
        # Блоки ветки «модуль недоступен» (условие начинается с not …) не считаются.
        if row["вид элемента"] == "раскрывающийся блок" and not row["условие показа"].startswith("not "):
            label = row["подпись"].split(" (expanded=")[0]
            if label.startswith("dropped_phases") or label == "Технические сведения":
                continue
            if label not in expanders.setdefault(row["экран"], []):
                expanders[row["экран"]].append(label)

    lines: list[str] = []
    order = [row["экран"] for row in formy]
    seen: list[str] = []
    for screen in order:
        if screen not in seen:
            seen.append(screen)
    for screen in seen:
        head = info[screen]
        title = f"{head['вкладка']} → {head['подвкладка']}"
        if head["вид (переключатель)"]:
            title += f" → {head['вид (переключатель)']}"
        lines.append(f"#### {screen}. {title}")
        lines.append("")
        lines.append(f"Кнопка: «{head['основная кнопка']}», `{head['кнопка файл:строка']}`. "
                     f"Блоки сейчас: {', '.join('«' + e + '»' for e in expanders.get(screen, [])) or 'нет'}.")
        lines.append("")
        items = screens.get(screen, [])
        if not items:
            lines.append("Полей ввода до кнопки нет — сворачивать нечего.")
            lines.append("")
            continue
        opened = [r for r in items if r["решение 9Б"] == "открыто"]
        folded = [r for r in items if r["решение 9Б"] == "свернуть"]
        already = [r for r in items if r["решение 9Б"].startswith("уже в блоке")]
        parts: list[str] = []
        for r in opened:
            text = (f"«{cell(r['подпись'].split(' | ')[0])}» — {cell(r['причина по коду'])}"
                    + (" **(обязательное)**" if r["обязательное"].startswith("да") else ""))
            if text not in parts:  # две ветки одного поля (галочка поправок) — одна запись
                parts.append(text)
        lines.append("Остаётся открытым: " + "; ".join(parts) + ".")
        lines.append("")
        if folded:
            lines.append("| Поле | В блок | Ранг | Причина по коду | Строка st.columns | Адрес |")
            lines.append("|---|---|---|---|---|---|")
            for r in sorted(folded, key=lambda item: (item["ранг (1 — сворачивать первым)"], item["файл:строка"])):
                lines.append(
                    f"| {cell(r['подпись'].split(' | ')[0])} | «{r['блок']}» | {r['ранг (1 — сворачивать первым)']} | "
                    f"{cell(r['причина по коду'])} | {cell(r['в одной строке (st.columns)'].replace('st.columns@', '')) or '—'} | "
                    f"`{r['файл:строка']}` |")
            lines.append("")
        if already:
            groups: "OrderedDict[str, list[str]]" = OrderedDict()
            for r in already:
                groups.setdefault(r["блок"], []).append(r["подпись"].split(" | ")[0])
            lines.append("Уже свёрнуто: " + "; ".join(
                f"«{block}» — полей: {len(labels)}" for block, labels in groups.items()) + ".")
            lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{OUT}: {len(lines)} строк")


if __name__ == "__main__":
    main()
