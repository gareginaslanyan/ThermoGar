"""Сборка ``app/thermogar_phase_descriptions.py`` из разметки 19-В (19-В2, шаг 3).

Источник пар — ``results/wave19_v/razmetka_ispolnitel.csv``, столбец ``klyuchi``
(решение мастера 23.09.2026). Пустые ключи в таблицу не идут. Сверка: пар 80,
непустых 77, пустые — CHI_A12, TRID, SPINEL; каждая пара есть в справочнике ДО
(``results/wave19_v2/do``) строкой с заглушкой.

Запуск (из корня дерева):
    .venv-windows/Scripts/python.exe -B -X utf8 results/wave19_v2/scripts/gen_stub_keys.py
"""
from __future__ import annotations

import ast
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MARKUP = ROOT / "results" / "wave19_v" / "razmetka_ispolnitel.csv"
BEFORE = HERE.parent / "do"
TARGET = ROOT / "app" / "thermogar_phase_descriptions.py"

STUB = "Русская расшифровка для этой специализированной фазы ещё не добавлена."

PHRASES = (
    ("S_CUB", "Кубическая структура."),
    ("S_TET", "Тетрагональная структура."),
    ("S_ORT", "Ромбическая структура."),
    ("S_MON", "Моноклинная структура."),
    ("S_HEX", "Гексагональная структура."),
    ("S_RHO", "Ромбоэдрическая структура."),
    ("S_BCC", "Объёмно-центрированная кубическая (ОЦК) структура."),
    ("S_FCC", "Гранецентрированная кубическая (ГЦК) структура."),
    ("S_HCP", "Гексагональная плотноупакованная (ГПУ) структура."),
    ("C_INT", "Интерметаллидная фаза."),
    ("C_SIL", "Силицидная фаза."),
    ("C_GAS", "Газовая фаза."),
    ("C_OX", "Оксидная фаза."),
    ("C_BOR", "Боридная фаза."),
    ("C_SUL", "Сульфидная фаза."),
    ("C_CAR", "Карбидная фаза."),
    ("C_NIT", "Нитридная фаза."),
    ("C_LAV", "Фаза Лавеса."),
    ("R_DISP", "Дисперсоид."),
    ("R_DISPU", "Упрочняющий дисперсоид."),
    ("R_UPR", "Упрочняющая фаза."),
    ("R_TPU", "Топологически плотноупакованная (ТПУ) фаза."),
    ("R_OXR", "Может охрупчивать сплав."),
    ("R_TVXR", "Твёрдая и хрупкая фаза."),
    ("U_EQ", "Равновесная фаза."),
    ("U_MET", "Метастабильная фаза."),
    ("T_HIGH", "Высокотемпературная модификация."),
    ("T_LOW", "Низкотемпературная модификация."),
    ("SL_EQ", "Служебная фаза базы: только для расчёта равновесия."),
    ("SL_TD", "Служебная фаза базы: только для расчёта термодинамических свойств."),
)
KEY_ORDER = tuple(key for key, _ in PHRASES)

HEADER = '''"""Русские описания фаз из утверждённых фраз по ключам (BL-58).

Источник: BL-58; разметка 19-В (исполнитель; сверка Jev jev-1.13.0, совпало
44 из 80, расхождения решены мастером 23.09.2026 в пользу исполнителя);
фразы утверждены владельцем 23.09.2026; вызова модели в программе нет.

Таблица ``STUB_KEYS`` собрана скриптом
``results/wave19_v2/scripts/gen_stub_keys.py`` из
``results/wave19_v/razmetka_ispolnitel.csv``; руками не править.
"""

from __future__ import annotations
'''

FUNCTION = '''

def phrases_for(phase_name: str, description: str) -> str | None:
    """Фразы по ключам пары (имя фазы, описание) через пробел; нет пары — None."""
    keys = STUB_KEYS.get((phase_name, description))
    if not keys:
        return None
    return " ".join(PHRASES[key] for key in keys)
'''


def _q(value: str) -> str:
    """Строковый литерал в двойных кавычках, как в остальном коде app/."""
    literal = json.dumps(value, ensure_ascii=False)
    if ast.literal_eval(literal) != value:
        sys.exit(f"literal mismatch: {value!r}")
    return literal


def _tuple(keys: tuple[str, ...]) -> str:
    inner = ", ".join(_q(key) for key in keys)
    return f"({inner},)" if len(keys) == 1 else f"({inner})"


def _stub_pairs() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for key in ("ni", "al", "fe"):
        with (BEFORE / f"phase_reference_{key}.csv").open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["Описание по-русски"] == STUB:
                    pairs.add((row["Код фазы"], row["Оригинал из базы (англ.)"].strip()))
    return pairs


def main() -> None:
    with MARKUP.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    table: dict[tuple[str, str], tuple[str, ...]] = {}
    empty: list[str] = []
    for row in rows:
        pair = (row["faza"], row["opisanie_en"])
        if pair[1] != pair[1].strip():
            sys.exit(f"description has outer spaces: {pair}")
        if pair in table or row["faza"] in empty:
            sys.exit(f"duplicate pair: {pair}")
        keys = tuple(row["klyuchi"].split())
        if not keys:
            empty.append(row["faza"])
            continue
        unknown = [key for key in keys if key not in KEY_ORDER]
        if unknown:
            sys.exit(f"unknown keys {unknown} for {pair}")
        table[pair] = keys
    if len(rows) != 80 or len(table) != 77 or sorted(empty) != ["CHI_A12", "SPINEL", "TRID"]:
        sys.exit(f"counts: rows {len(rows)}, non-empty {len(table)}, empty {empty}")
    stub_pairs = _stub_pairs()
    missing = sorted(set(table) - stub_pairs)
    if missing or len(stub_pairs) != 80:
        sys.exit(f"stub pairs {len(stub_pairs)}, not found: {missing}")

    lines = [HEADER, "", "PHRASES: dict[str, str] = {"]
    lines += [f"    {_q(key)}: {_q(phrase)}," for key, phrase in PHRASES]
    lines += ["}", "", "KEY_ORDER: tuple[str, ...] = ("]
    lines += [f"    {_q(key)}," for key in KEY_ORDER]
    lines += [")", "", "STUB_KEYS: dict[tuple[str, str], tuple[str, ...]] = {"]
    for pair in sorted(table):
        lines.append(f"    ({_q(pair[0])}, {_q(pair[1])}): {_tuple(table[pair])},")
    lines += ["}"]
    text = "\n".join(lines) + "\n" + FUNCTION
    TARGET.write_bytes(text.encode("utf-8"))
    print(f"pairs {len(table)}, empty {empty}, written {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
