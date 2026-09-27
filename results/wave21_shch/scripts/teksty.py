"""21-Щ, ШАГ 6: тексты мастера в главах руководства, FEATURES.md и USER_GUIDE_THERMOGAR.md.

Каждая правка — замена точного прежнего текста (иначе AssertionError) и строка
в results/wave21_shch/teksty.csv (UTF-8 с BOM, «;»): файл:строка прежнего
текста (до правок, по заданию), было, стало, откуда число. Числа — из
results/wave21_shch/zamer/*.xlsx (выгрузки тех же расчётов, что на кадрах,
scripts/zamer_tablicy.py) и readings docs/guide/img/_manifest.json.

Запуск из корня дерева:

    python -X utf8 results/wave21_shch/scripts/teksty.py
"""

from __future__ import annotations

import csv
import json
import math
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
ZAMER = ROOT / "results" / "wave21_shch" / "zamer"
MANIFEST = json.loads((ROOT / "docs/guide/img/_manifest.json").read_text(encoding="utf-8"))
READINGS = {frame["image"]: frame.get("readings", {}) for frame in MANIFEST["frames"]}
EMPTY = READINGS["soobshcheniya-02.png"]["empty_solution"]
STOP = READINGS["soobshcheniya-03.png"]["stop_note"]
NUCLEUS = READINGS["soobshcheniya-05.png"]["nucleus_warning"]
assert "ушла ниже нуля" in STOP and "баланс масс нарушен" not in STOP


def ru(value: str) -> str:
    return value.replace(".", ",")


# --- числа ------------------------------------------------------------------
solid = pd.read_excel(ZAMER / "zatverdevanie.xlsx", sheet_name=None)
LIQUIDUS = float(solid["Сводка"]["Расчётный ликвидус, °C"].iloc[0])
path = solid["Scheil путь"]
T_HALF = float(path.loc[path["Доля расплава, %"] < 50.0, "Температура, °C"].iloc[0])
TL = f"{LIQUIDUS:.0f}"
TH = f"{T_HALF:.0f}"

kin_book = pd.read_excel(ZAMER / "kinetika.xlsx", sheet_name=None)
kin = kin_book["Кинетика"]
summary = dict(zip(kin_book["Итоги"]["Показатель"], kin_book["Итоги"]["Значение"]))
X_AT_1E4 = float(np.interp(1e-4, kin["Время, ч"], kin["Объёмная доля, %"]))
MAX_DENSITY = float(kin["Плотность частиц, 1/м³"].max())
N_POW = round(math.log10(MAX_DENSITY))
F = float(summary["Итоговая объёмная доля"])
R = float(summary["Итоговый средний радиус"])
P = float(summary["Итоговая плотность частиц"])
SUP = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
X_TXT = f"{X_AT_1E4:.0f}"
F_TXT = ru(f"{F:.1f}")
R_TXT = f"{R:.0f}"
P_MANT, P_EXP = f"{P:.1e}".split("e")
P_TXT = f"{ru(P_MANT)}·10{str(int(P_EXP)).translate(SUP)}"
N_TXT = str(N_POW).translate(SUP)

prof = pd.read_excel(ZAMER / "diffuziya.xlsx", sheet_name="Профили")
delta = (prof["Cr, итог, ат.%"] - prof["Cr, нач., ат.%"]).abs()
changed = prof.loc[delta > 1.0, "Расстояние, мкм"]
A_UM = int(round(changed.min() / 50.0) * 50)
B_UM = int(round(changed.max() / 50.0) * 50)
ends = {}
for column in ("Ni", "Al", "Cr"):
    first = prof[f"{column}, итог, ат.%"].iloc[0] - prof[f"{column}, нач., ат.%"].iloc[0]
    last = prof[f"{column}, итог, ат.%"].iloc[-1] - prof[f"{column}, нач., ат.%"].iloc[-1]
    ends[column] = (first, last)
END_MAX = max(abs(v) for pair in ends.values() for v in pair)
assert END_MAX < 0.05, ends  # «у торцов остаётся исходным»

NUMBERS = {
    "Тл": (TL, f"«Расчётный ликвидус» кадра zatverdevanie-04 и zamer/zatverdevanie.xlsx, лист «Сводка»: {LIQUIDUS:.4f} °C, до 1 °C"),
    "Т½": (TH, f"zamer/zatverdevanie.xlsx, лист «Scheil путь»: первая температура с долей расплава < 50 % — {T_HALF:.0f} °C ({path.loc[path['Доля расплава, %'] < 50.0, 'Доля расплава, %'].iloc[0]:.2f} %)"),
    "X": (X_TXT, f"zamer/kinetika.xlsx, лист «Кинетика»: доля при 10⁻⁴ ч (линейно между соседними строками) {X_AT_1E4:.2f} %"),
    "N": (N_TXT, f"zamer/kinetika.xlsx, лист «Кинетика»: максимум плотности частиц {MAX_DENSITY:.3e} 1/м³, log10 = {math.log10(MAX_DENSITY):.2f}, порядок — 10^{N_POW}"),
    "F": (F_TXT, f"сводка «Итоги»: итоговая объёмная доля {F:.4f} %"),
    "R": (R_TXT, f"сводка «Итоги»: итоговый средний радиус {R:.4f} нм"),
    "P": (P_TXT, f"сводка «Итоги»: итоговая плотность частиц {P:.5e} 1/м³ (кадр kinetika-05)"),
    "А": (str(A_UM), f"zamer/diffuziya.xlsx, лист «Профили»: |Cr итог − Cr нач.| > 1 ат.% с {changed.min()} мкм, до 50 мкм"),
    "Б": (str(B_UM), f"zamer/diffuziya.xlsx, лист «Профили»: |Cr итог − Cr нач.| > 1 ат.% по {changed.max()} мкм, до 50 мкм; у торцов отличие от исходного не больше {END_MAX:.3f} ат.%"),
}

# --- правки -----------------------------------------------------------------
originals: dict[str, str] = {}
texts: dict[str, str] = {}
rows: list[tuple[str, str, str, str]] = []


def load(rel: str) -> str:
    if rel not in texts:
        raw = (ROOT / rel).read_bytes().decode("utf-8")
        assert "\r" not in raw
        originals[rel] = raw
        texts[rel] = raw
    return texts[rel]


def old_line(rel: str, old: str, expect: str) -> str:
    original = originals[rel]
    assert original.count(old) == 1, (rel, old[:60])
    first = original.count("\n", 0, original.index(old)) + 1
    last = first + old.rstrip("\n").count("\n")
    where = f"{first}" if first == last else f"{first}–{last}"
    assert where == expect, (rel, where, expect)
    return f"{rel}:{where}"


def edit(rel: str, expect: str, old: str, new: str, source: str) -> None:
    text = load(rel)
    where = old_line(rel, old, expect)
    assert text.count(old) == 1, (rel, old[:60])
    texts[rel] = text.replace(old, new)
    rows.append((where, old, new, source))


def wrap(text: str, prefix: str = "", width: int = 100) -> str:
    # Жирный фрагмент **…** не разрывается переносом строки.
    parts = text.split("**")
    for index in range(1, len(parts), 2):
        parts[index] = parts[index].replace(" ", "\x00")
    filled = textwrap.fill(
        "**".join(parts), width=width, initial_indent=prefix, subsequent_indent=prefix,
        break_long_words=False, break_on_hyphens=False,
    )
    return filled.replace("\x00", " ")


def quote_width(block: str) -> int:
    return max(len(line) for line in block.split("\n"))


MASTER = "текст мастера (ШАГ 6, п. {})"

# 1) 01-raschety.md:3
edit("docs/guide/01-raschety.md", "3",
     "`C=0.2, CR=11.5, NI=0.7` (масс.%, основа FE)",
     "`C=0.2, Cr=11.5, Ni=0.7` (масс.%, основа Fe)", MASTER.format(1))

# 2) 01-raschety.md:57–59, FEATURES.md:62–64 — reading empty_solution кадра soobshcheniya-02
OLD_EMPTY = (
    "> Равновесие при 750.0 °C не найдено: pycalphad вернул пустое решение (сумма долей фаз равна нулю),\n"
    "> поэтому результата нет — попробуйте другую температуру или состав; решатель не сходится на части\n"
    "> составов, и соседние точки тоже могут оказаться пустыми."
)
NEW_EMPTY = wrap(EMPTY, "> ", quote_width(OLD_EMPTY))
for rel, where in (("docs/guide/01-raschety.md", "57–59"), ("docs/FEATURES.md", "62–64")):
    edit(rel, where, OLD_EMPTY, NEW_EMPTY,
         MASTER.format(2) + "; reading empty_solution кадра soobshcheniya-02 (_manifest.json)")

# 3) 02-diagrammy.md:14
edit("docs/guide/02-diagrammy.md", "14", "`NI`, **второй** — `AL`", "`Ni`, **второй** — `Al`", MASTER.format(3))

# 4) 03-zatverdevanie.md:12
edit("docs/guide/03-zatverdevanie.md", "12", "`CU=4, MG=1`. Основа `AL`", "`Cu=4, Mg=1`. Основа `Al`", MASTER.format(4))

# 5) 03-zatverdevanie.md:43 — абзац переносится по ширине главы
OLD_5 = (
    "График показывает долю расплава по температуре. Между 650 и 640 °C затвердевает больше половины\n"
    "объёма, дальше кривая идёт полого — это обогащённый медью и магнием остаточный расплав, из\n"
    "которого и вырастут междендритные интерметаллиды. Их список — на варианте\n"
)
text_03 = load("docs/guide/03-zatverdevanie.md")
start = text_03.index(OLD_5)
end = text_03.index("\n\n", start)
OLD_5 = text_03[start:end]
NEW_5 = wrap(" ".join(OLD_5.split("\n")).replace(
    "Между 650 и 640 °C затвердевает больше половины",
    f"От ликвидуса ({TL} °C) до {TH} °C затвердевает больше половины"))
edit("docs/guide/03-zatverdevanie.md", f"43–{42 + OLD_5.count(chr(10)) + 1}", OLD_5, NEW_5,
     MASTER.format(5) + f"; <Тл> = {TL}: {NUMBERS['Тл'][1]}; <Т½> = {TH}: {NUMBERS['Т½'][1]}")

# 6) «`AL=15`» → «`Al=15`»; 07-proekty.md:46
for rel, where in (
    ("docs/guide/04-energii.md", "7"),
    ("docs/guide/05-svoystva.md", "31"),
    ("docs/guide/06-kinetika.md", "8"),
):
    edit(rel, where, "`AL=15`", "`Al=15`", MASTER.format(6))
# в 07-proekty.md `AL=15` встречается и в строке 46 — место строки 6 по соседнему слову
edit("docs/guide/07-proekty.md", "6", "составом `AL=15`", "составом `Al=15`", MASTER.format(6))
edit("docs/guide/07-proekty.md", "46", "`AL=12`, `AL=15` и `AL=18`", "`Al=12`, `Al=15` и `Al=18`", MASTER.format(6))

# 7) 05-svoystva.md:3–4 — перенос строк абзаца по ширине главы
OLD_7 = (
    "Раздел считает свойства многофазного сплава по долям фаз: плотность — из базы физических данных\n"
    "`physical_data.pdb`, упругие модули — по Фойгту–Ройссу–Хиллу из модулей отдельных фаз, которые\n"
    "задаёт пользователь. Два примера: плотность стали и модули никелевого сплава."
)
NEW_7 = wrap(" ".join(OLD_7.split("\n")).replace(
    "плотность — из базы физических данных `physical_data.pdb`, упругие модули",
    "плотность — из физической базы, упругие модули"))
edit("docs/guide/05-svoystva.md", "3–5", OLD_7, NEW_7, MASTER.format(7))

# 8) `C=0.2, CR=11.5, NI=0.7`; README.md:51
for rel, where in (
    ("docs/guide/05-svoystva.md", "13"),
    ("docs/guide/README.md", "65"),
    ("docs/FEATURES.md", "30"),
):
    edit(rel, where, "`C=0.2, CR=11.5, NI=0.7`", "`C=0.2, Cr=11.5, Ni=0.7`", MASTER.format(8))
edit("docs/guide/README.md", "51", "Для стали это `FE`", "Для стали это `Fe`", MASTER.format(8))

# 9) 05-svoystva.md:23 — дописать предложение, абзац переносится по ширине главы
OLD_9 = (
    "Плотность сплава 7575,7 кг/м³. Ниже — важные строки: **покрытие физической базы по массе 100 %** (для всех\n"
    "равновесных фаз есть модель плотности) и **качество оценки** — «оценочная: есть плотности\n"
    "связанных фаз». Если покрытие меньше 100 %, поле плотности останется пустым: программа не\n"
    "достраивает недостающие данные."
)
NEW_9 = wrap(" ".join(OLD_9.split("\n")) + (
    " Галочка «Применять поправки проекта ThermoGar к физической базе» над вкладками раздела "
    "включена по умолчанию: плотность хрома считается по поправке, об этом — сообщение под "
    "таблицей «Плотность хрома посчитана по поправке проекта ThermoGar. …»."))
edit("docs/guide/05-svoystva.md", "20–23", OLD_9, NEW_9, MASTER.format(9))

# 10) 06-kinetika.md:48–52
OLD_10 = (
    "Нажмите **«Рассчитать кинетику выделений»**. Верхний график — объёмная доля γ′ по времени\n"
    "(логарифмическая шкала): до 0,01 ч ничего не происходит, за следующие несколько минут доля\n"
    "выходит на 25,8 %. Нижний график — средний радиус (около 20 нм к концу выдержки) и плотность\n"
    "частиц 6,3·10²¹ 1/м³. В сводке над графиками отмечено «Укрупнение на плато: да» — начался рост\n"
    "крупных частиц за счёт мелких."
)
NEW_10 = wrap(
    "Нажмите **«Рассчитать кинетику выделений»**. Верхний график — объёмная доля γ′ по времени "
    f"(логарифмическая шкала): выделение начинается почти сразу — к 10⁻⁴ ч (0,4 с) доля уже около {X_TXT} %, "
    f"дальше до конца выдержки медленно растёт до {F_TXT} %. Нижний график — средний радиус (около {R_TXT} нм "
    f"к концу выдержки) и плотность частиц: в первые доли секунды она доходит примерно до 10{N_TXT} 1/м³, "
    f"к концу выдержки падает до {P_TXT} 1/м³. В сводке над графиками отмечено «Укрупнение на плато: да» — "
    "начался рост крупных частиц за счёт мелких."
)
edit("docs/guide/06-kinetika.md", "48–52", OLD_10, NEW_10,
     MASTER.format(10) + "; " + "; ".join(f"<{k}> = {NUMBERS[k][0]}: {NUMBERS[k][1]}" for k in ("X", "N", "F", "R", "P")))

# 11) 06-kinetika.md:67–68
edit("docs/guide/06-kinetika.md", "67–68",
     "и kawin считает зарождение от\n  предела».**",
     "и модель считает зарождение\n  от этого предела».**",
     MASTER.format(11) + "; текст на экране — app/thermogar_precipitation.py:960")

# 12) 06-kinetika.md:75–78, FEATURES.md:113–116 — reading nucleus_warning кадра soobshcheniya-05
OLD_12 = (
    "  > Радиус зародыша 1.02 нм (оценка при 800.0 °C) больше начального максимального радиуса сетки 0.5 нм,\n"
    "  > поэтому первые зародыши записываются мельче своего размера, пока kawin не достроит сетку. Итоговые\n"
    "  > доля, радиус и число частиц от этого почти не меняются, но начало зарождения на графиках искажено:\n"
    "  > доля и радиус занижены, число частиц завышено. Задайте «Начальный максимальный радиус» больше 1.02 нм."
)
NEW_12 = wrap(NUCLEUS, "  > ", quote_width(OLD_12))
for rel, where in (("docs/guide/06-kinetika.md", "75–78"), ("docs/FEATURES.md", "113–116")):
    edit(rel, where, OLD_12, NEW_12,
         MASTER.format(12) + "; reading nucleus_warning кадра soobshcheniya-05 (_manifest.json)")

# 13) 06-kinetika.md:114, :157
edit("docs/guide/06-kinetika.md", "114",
     "`CR=7.7, AL=5.4`, справа `CR=35.9, AL=6.2` (ат.%, основа NI)",
     "`Cr=7.7, Al=5.4`, справа `Cr=35.9, Al=6.2` (ат.%, основа Ni)", MASTER.format(13))
edit("docs/guide/06-kinetika.md", "157", "(пара FE–C–CR)", "(пара Fe–C–Cr)", MASTER.format(13))

# 14) 06-kinetika.md:131–135
OLD_14 = (
    "Пунктир — исходный ступенчатый профиль, сплошная линия — состав после выдержки. За 100 ч при\n"
    "1200 °C перемешивание захватывает лишь несколько десятков микрон около границы: на длине 2000 мкм\n"
    "это узкая полоса, а ликвация масштаба сотен микрон за такую выдержку не выравнивается. Над\n"
    "графиком метрика **«Макс. ошибка баланса»** и зелёная полоса «проверка сохранения среднего\n"
    "состава пройдена» — без неё результат использовать нельзя."
)
NEW_14 = wrap(
    "Точечная линия — исходный ступенчатый профиль, линии с маркерами — состав после выдержки. "
    "За 100 ч при 1200 °C перемешивание захватывает несколько сотен микрон около границы: состав "
    f"заметно меняется примерно от {A_UM} до {B_UM} мкм, у торцов области он остаётся исходным. "
    "Над графиком — метрика **«Макс. ошибка баланса, u-доля»** и зелёная полоса «Численная "
    "проверка сохранения среднего состава пройдена.» — без неё результат использовать нельзя."
)
edit("docs/guide/06-kinetika.md", "131–135", OLD_14, NEW_14,
     MASTER.format(14) + f"; <А> = {A_UM}: {NUMBERS['А'][1]}; <Б> = {B_UM}: {NUMBERS['Б'][1]}; "
     "подписи — app/thermogar_diffusion.py:1247, :1251")

# 15) USER_GUIDE_THERMOGAR.md, пример остановки (:305–321)
UG = "USER_GUIDE_THERMOGAR.md"
edit(UG, "305–307",
     "Если по ходу счёта доля\nкакой-то добавки в матрице становится нулевой, расчёт останавливается,\n"
     "показывает посчитанную часть и выводит над вкладками объяснение, например:",
     "Если по ходу счёта доля\nкакой-то добавки в матрице уходит ниже нуля, расчёт останавливается,\n"
     "показывает посчитанную часть и выводит над переключателем видов объяснение, например:",
     MASTER.format(15))
OLD_15 = (
    "> Расчёт остановлен на 2.011 с модельного времени (0.0005586 ч): доля NB в\n"
    "> матрице стала 0 ат. %, баланс масс нарушен. Показана часть расчёта до\n"
    "> остановки. Причина: при движущей силе по базе зарождение практически\n"
    "> безбарьерное, и выделение вычерпывает добавки из матрицы быстрее, чем модель\n"
    "> это выдерживает; см. docs/LIMITS_OF_APPLICABILITY.md."
)
NEW_15 = (
    wrap(STOP, "> ", quote_width(OLD_15)) + "\n\n"
    + wrap("Если программа видит, что баланс масс до остановки нарушен, текст говорит и это: "
           "«баланс масс нарушен».", width=quote_width(OLD_15))
)
edit(UG, "309–313", OLD_15, NEW_15,
     MASTER.format(15) + "; reading stop_note кадра soobshcheniya-03 (_manifest.json)")
edit(UG, "318", "а над вкладками стоит «Одна или", "а над переключателем видов стоит «Одна или", MASTER.format(15))
edit(UG, "321",
     "![Текст остановки расчёта выделений над вкладками]",
     "![Текст остановки расчёта выделений над переключателем видов]", MASTER.format(15))

# --- запись -----------------------------------------------------------------
for rel, text in texts.items():
    (ROOT / rel).write_bytes(text.encode("utf-8"))
out = ROOT / "results" / "wave21_shch" / "teksty.csv"
with out.open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.writer(handle, delimiter=";", lineterminator="\n")
    writer.writerow(["файл:строка", "было", "стало", "откуда число"])
    writer.writerows(rows)
print(f"правок: {len(rows)} в {len(texts)} файлах")
for key, (value, source) in NUMBERS.items():
    print(f"<{key}> = {value} — {source}")
