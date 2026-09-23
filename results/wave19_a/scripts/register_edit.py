"""Правки tasks/REGISTER.md по шагу 7 задания 19-А (тексты мастера дословно)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / "tasks" / "REGISTER.md"
ITOG = sys.argv[1]

text = PATH.read_text("utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{count} matches: {old[:80]!r}")
    text = text.replace(old, new)


# 7д. Устаревшие записи.
replace_once(
    "**закрыт волной 18-В (BL-44); ветка `wave18-a`, в `main` не влито.**",
    "**закрыт волной 18-В (BL-44); влито в `main` `7745df8`, выпуск 0.4.3.**",
)
for stream in ("16-Б", "18-А2", "18-Б", "18-В", "18-Г", "18-Г2"):
    lines = text.split("\n")
    hits = [i for i, line in enumerate(lines) if line.startswith(f"| {stream} | ")]
    if len(hits) != 1 or lines[hits[0]].count("**сдано, мастер не смотрел.**") != 1:
        raise SystemExit(f"row {stream}: {hits}")
    lines[hits[0]] = lines[hits[0]].replace(
        "**сдано, мастер не смотрел.**",
        "**принята (статус по передаче мастера 23.09.2026).**",
    )
    text = "\n".join(lines)

# 7б. Строки BL-55 и BL-56.
lines = text.split("\n")
for index, line in enumerate(lines):
    if line.startswith("| BL-55 | "):
        cells = line.split(" | ")
        assert len(cells) == 4 and cells[3].startswith("**открыт, заведён ревью 21.09.**")
        cells[3] = (
            "**закрыт 19-А; ветка `wave19-a`, в `main` не влито.** "
            "`ordered` и `disordered` в `translate_phase_description` ищутся по целому слову "
            "(`re`, `\\b`), проверки независимы. Замер 19-А: справочник фаз трёх баз "
            "(`phase_reference_dataframe`) — 99/195/132 строк (Ni/Al/Fe), описаний `MATCALC_DESCRIPTION` "
            "64/87/94, слово `disordered` 0/0/0, слово `ordered` 2/6/7; CSV справочника до и после "
            "правки побайтово равны — на отгруженных базах вывод не меняется. Тест "
            "`tools/test_phase_description_order_words.py` (на `e14b3e3` — 6 из 11 красные). "
            "Отчёт `tasks/WAVE19_A_REPORT.md`. Прежняя запись: " + cells[3]
        )
        lines[index] = " | ".join(cells)
    elif line.startswith("| BL-56 | "):
        cells = line.split(" | ")
        assert len(cells) == 4 and cells[3].startswith("**открыт, заведён ревью 21.09.**")
        cells[2] = cells[2] + (
            " Уточнение 19-А (23.09): разборов режима стали два — `_steel_mode` при приёме файла "
            "(`app/thermogar_verified_state.py:339-343`) и `normalize_steel_mode` в строке пакета "
            "(`app/thermogar_workspace.py:2135-2139`); оба ищут подстроки «стаб»/«stable», которые "
            "входят в «метастабильный»/«metastable». Первый сводит любое значение к `stable`/`metastable`, "
            "второй читает `metastable` как `stable`: каждая строка Fe из файла доходила до движка в "
            "стабильном режиме (графит разрешён) при любом значении ячейки, включая пустую."
        )
        cells[3] = (
            "**закрыт 19-А; ветка `wave19-a`, в `main` не влито.** "
            "Один закрытый перечень `STEEL_MODE_ALIASES` в `app/thermogar_verified_state.py`, разбор "
            "`steel_mode_or_none` (равенство после `strip` + `casefold`, пусто/None/NaN — `metastable`); "
            "`thermogar_workspace` импортирует оба. Приём файла: неизвестное — текст ячейки после `strip`, "
            "файл не отклоняется; строка пакета: неизвестное — `ValueError` текстом владельца в столбец "
            "«Ошибка» сводки, остальные строки считаются. Замер 19-А на `e14b3e3`: 11 значений из 11 "
            "(пусто, `metastable`, «метастабильный», «практический», «цементит», `cementite`, `stable`, "
            "«стабильный», «графит», `graphite`, `metastabe`) доходили до движка как `stable`; после "
            "правки — 10 известных своим режимом, `metastabe` — «ошибка» с текстом владельца. "
            "Fe–0,8C мас. %, 700 °C, полный набор `thermogar_patch`: `stable` — BCC_B2 0,96435 + "
            "GRAPHITE 0,03565; `metastable` — BCC_B2 0,85775 + CEMENTITE 0,14225 (одиночное равновесие "
            "«Расчётов» совпадает с пакетом, разность 0,0). Через пакет после правки: пусто и "
            "«метастабильный» — числа `metastable`, «стабильный» — `stable`, побайтно. Задевает выпуски "
            "0.3.0, 0.3.1, 0.4.0, 0.4.1, 0.4.2, 0.4.3. Тесты: `tools/thermogar_verified_state_test.py`, "
            "`tools/thermogar_verified_equilibrium_test.py` (test_17, test_18). Отчёт "
            "`tasks/WAVE19_A_REPORT.md`. Прежняя запись: " + cells[3]
        )
        lines[index] = " | ".join(cells)
text = "\n".join(lines)

# 7в. Тексты владельца — опись.
replace_once(
    "| «Ищем солидус половинным делением…» | «Затвердевание», окно состояния на время поиска солидуса | 18-Г | да, 2026-09-19 |\n",
    "| «Ищем солидус половинным делением…» | «Затвердевание», окно состояния на время поиска солидуса | 18-Г | да, 2026-09-19 |\n"
    "| «Неизвестный режим стали: «{значение}». Используйте «стабильный» или «метастабильный».» | «Проекты и данные» → пакетный расчёт, столбец «Ошибка» сводки (BL-56) | 19-А | да, 2026-09-23 |\n",
)

# 7а и 7г. Раздел волны 19 перед «## Завершённые волны».
section = (
    "## Волна 19 — BL-55, BL-56\n"
    "\n"
    "Дерево `D:\\Pets\\ThermoGar`, ветка `wave19-a` от `main` `e14b3e3`. Задание 19-А от 21.09 не запускалось и заменено заданием 19-А от 23.09 (см. «Ошибка мастера (BL-56, 19-А)»).\n"
    "\n"
    "| Поток | Файл задачи | Дерево / ветка | Что | Состояние |\n"
    "|---|---|---|---|---|\n"
    "| 19-А | `WAVE19_A_OPUS.md` | `ThermoGar` / `wave19-a` | BL-56: один закрытый перечень режима стали для приёма файла и строки пакета, текст владельца на неизвестное значение; BL-55: `ordered`/`disordered` по целому слову | **сдано, мастер не смотрел.** "
    + ITOG
    + ". Отчёт `tasks/WAVE19_A_REPORT.md` |\n"
    "\n"
    "### Ошибка мастера (BL-56, 19-А)\n"
    "\n"
    "Запись BL-56 внесена со слов ревью 21.09 без прогона кода: «на нераспознанном значении молча возвращает `metastable`». Прогоном обеих функций на `e14b3e3` мастер 23.09 установил обратное: при приёме пакета из файла все строки Fe уходят в движок как `stable` (уточнение в строке BL-56). Задание 19-А от 21.09 стояло на неверной записи, не запускалось и заменено. Утверждение о данных проверять прогоном кода, который их читает, — по всей цепочке, а не одной функции.\n"
    "\n"
    "Исполнитель 19-А: задевает выпуски 0.3.0, 0.3.1, 0.4.0, 0.4.1, 0.4.2, 0.4.3 — `_steel_mode` и `normalize_steel_mode` побайтно одинаковы во всех шести тегах, путь файл → `batch_table_dataframe` → `run_batch_calculations` есть в каждом (`results/wave19_a/do/1b_tags.txt`).\n"
    "\n"
)
replace_once("\n## Завершённые волны\n", "\n" + section + "## Завершённые волны\n")

PATH.write_text(text, "utf-8", newline="\n")
print("ok")
