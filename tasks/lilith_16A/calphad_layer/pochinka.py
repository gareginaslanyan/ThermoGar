"""APP-304: слой починки скачанных TDB. Правится СИНТАКСИС, не данные.

Урок APP-299: «открытая база ≠ готовая». Ни один из скачанных файлов не
читается pycalphad 0.11.2 как есть. Каждая починка здесь:
  - строго синтаксическая (числовые параметры не трогаются);
  - с assert на якорь и на ожидаемое число вхождений (правило проекта
    «правки скриптом — только с assert на якорь»);
  - с комментарием, ПОЧЕМУ она нужна и почему безопасна.

Починенные файлы кладутся рядом, в tdb_pochinennye/, и в репозиторий не
идут: они выводимы из исходников этим скриптом. Скрипт идемпотентен.

Запуск вручную:  python3 -m calphad_layer.pochinka
"""
import hashlib
import logging
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISHODNIKI = HERE / "tdb"
POCHINENNYE = HERE / "tdb_pochinennye"

# Журнал слоя. Экранных слов у починки нет и быть не должно: она работает
# до и вне показа. Останов уходит сюда и в исключение, не на экран.
# NullHandler — чтобы logging не печатал сообщение на stderr сам
# (обработчик последней надежды), когда приложение журнал не настроило.
ZHURNAL = logging.getLogger(__name__)
ZHURNAL.addHandler(logging.NullHandler())


class IshodnikIzmenilsya(RuntimeError):
    """Предусловие починки не сошлось. Правка НЕ применяется — ни частично."""


class BazaNeChitaema(RuntimeError):
    """Файл базы не прошёл закалку чтения (потолок размера, символьная ссылка)."""


def _ostanov(klass, kod, soobshchenie):
    ZHURNAL.error("%s: %s", kod, soobshchenie)
    raise klass(f"{kod}: {soobshchenie}")


# APP-502 п. 2 (закалка чтения). Потолок размера файла базы. Самая большая
# наша база — mc_ni, 0,42 МБ; 8 МиБ это двадцатикратный запас на будущие
# версии и одновременно отказ читать в память подсунутый большой файл.
# (ThermoGar держит 16 МиБ; нам столько не нужно.)
POTOLOK_BAJT = 8 * 1024 * 1024


def prochitat_bajty(put):
    """Единственное место, где байты TDB попадают в слой.

    Отказы именованные, в журнал: (а) путь базы — символьная ссылка (файл
    мог быть подменён мимо sha256 манифеста, и сам sha считается уже по
    подменённому), (б) файл больше потолка.
    """
    put = Path(put)
    if put.is_symlink():
        _ostanov(BazaNeChitaema, "put_bazy_simvolnaya_ssylka",
                 f"{put} — символьная ссылка; база читается только как файл")
    if not put.is_file():
        _ostanov(BazaNeChitaema, "put_bazy_ne_fajl", f"{put} — не обычный файл")
    razmer = put.stat().st_size
    if razmer > POTOLOK_BAJT:
        _ostanov(BazaNeChitaema, "baza_bolshe_potolka",
                 f"{put}: {razmer} байт, потолок {POTOLOK_BAJT}")
    return put.read_bytes()


def sha256_fajla(put):
    return hashlib.sha256(prochitat_bajty(put)).hexdigest()


# --------------------------------------------------------------------------
# Предусловия и постусловия починок (APP-502 п. 1)
# --------------------------------------------------------------------------
# Дисциплина взята из ThermoGar (thermogar_convert_matcalc_tdb.py:140-280,
# разбор 04.09.2026, п. 2): sha256 исходника ловит смену версии базы, но
# НЕ говорит, куда именно ляжет правка, если версия сменилась, а sha
# перепинули не глядя. Поэтому каждая починка объявляет ЗДЕСЬ, что именно
# она ищет в тексте, сколько активных вхождений обязано быть ДО правки и
# сколько остаться ПОСЛЕ. Несовпадение любого числа — останов
# (`IshodnikIzmenilsya`, «починка на пересмотр»), а не частичная правка.
#
# Строка таблицы: (что ищется, шаблон, сколько до, сколько после).
# «Активное вхождение» = не закомментированное: шаблоны с `^` считают
# команды в начале строки, закомментированные начинаются с '$'.
PREDUSLOVIYA = {
    "mc_fe_v2.059.tdb": (
        ("ссылка с пробелом в имени", r"REF:test koze10", 4, 0),
        ("та же ссылка с подчёркиванием", r"REF:test_koze10", 0, 4),
    ),
    "mc_al_v2.036.tdb": (
        ("TeX-директива первой строкой", r"(?m)^% !TEX\b", 1, 0),
        ("REFERENCE_ELEMENT", r"(?m)^REFERENCE_ELEMENT\b", 1, 0),
        ("ATTACH_CONTRIBUTION", r"(?m)^ATTACH_CONTRIBUTION\b", 1, 0),
        ("ADD_COMPOSITION_SET", r"(?m)^ADD_COMPOSITION_SET\b", 1, 0),
        ("PARAMETER HMVA/SE", r"(?mi)^PARAMETER +(?:HMVA|SE)\(", 8, 0),
    ),
    "mc_ni_v2036.tdb": (
        ("REFERENCE_ELEMENT", r"(?m)^REFERENCE_ELEMENT\b", 1, 0),
        ("ATTACH_CONTRIBUTION", r"(?m)^ATTACH_CONTRIBUTION\b", 1, 0),
        ("ADD_COMPOSITION_SET", r"(?m)^ADD_COMPOSITION_SET\b", 9, 0),
        ("PARAMETER HMVA", r"(?mi)^PARAMETER +HMVA\(", 13, 0),
        ("предел `6000.00.00` (две точки)", r"6000\.00\.00", 2, 0),
        ("LIST_OF_REFERENCES", r"(?m)^LIST_OF_REFERENCES\b", 0, 1),
    ),
    # COST507 разбирается как есть, починок нет — и предусловий нет.
    "COST507.tdb": (),
}


def _sverit(imya, tekst, kogda):
    """Сверить текст с таблицей. `kogda` — "до" или "после" правки."""
    for chto, shablon, do, posle in PREDUSLOVIYA[imya]:
        ozhid = do if kogda == "до" else posle
        fakt = len(re.findall(shablon, tekst))
        if fakt != ozhid:
            _ostanov(IshodnikIzmenilsya, "ishodnik_izmenilsya",
                     f"{imya}: «{chto}» — активных вхождений {fakt} "
                     f"{kogda} правки, объявлено {ozhid}; починка на пересмотр")


# --------------------------------------------------------------------------
# mc_fe
# --------------------------------------------------------------------------
# Починка mc_fe-1: имя ссылки с пробелом.
#   pycalphad ждёт после REF: ОДИН токен, а в базе стоит `REF:test koze10`.
#   Парсер падает на строке 4110 (ParseException). Пробел внутри имени
#   ссылки заменяется подчёркиванием. Имена ссылок в расчёт не входят
#   вообще — это библиография параметров, поэтому правка не может изменить
#   ни одного числа. Длина файла не меняется (проверяется assert'ом).
MC_FE_YAKOR = "REF:test koze10"
MC_FE_ZAMENA = "REF:test_koze10"
MC_FE_VHOZHDENIY = 4

# sha256 исходника (зеркало A) и ожидаемый sha256 результата.
# Ожидаемый результат — это НЕЗАВИСИМОЕ зеркало B (копия pycalphad),
# то есть починка проверяется не нашим же кодом, а чужим файлом:
# после правки мы обязаны получить зеркало B байт в байт.
MC_FE_SHA_ISHODNIKA = "1b12f7dcd1ec511735a486ca2c6dc3228db81bb3da5e7a36f819ef89d934914c"
MC_FE_SHA_REZULTATA = "467211ab854400ac6d247bdfb97069d37e021cfced6b8dbb30c0334b74ee1508"


def pochinit_mc_fe(tekst):
    _sverit("mc_fe_v2.059.tdb", tekst, "до")
    n = tekst.count(MC_FE_YAKOR)
    assert n == MC_FE_VHOZHDENIY, (
        f"mc_fe: якорь '{MC_FE_YAKOR}' встречается {n} раз, "
        f"ожидалось {MC_FE_VHOZHDENIY} — база не та, что описана в манифесте")
    out = tekst.replace(MC_FE_YAKOR, MC_FE_ZAMENA)
    assert len(out) == len(tekst), "mc_fe: длина изменилась — правка не только пробел"
    assert out.count(MC_FE_ZAMENA) == MC_FE_VHOZHDENIY
    _sverit("mc_fe_v2.059.tdb", out, "после")
    return out


# --------------------------------------------------------------------------
# mc_al
# --------------------------------------------------------------------------
# Починка mc_al-1: директива TeX-редактора в первой строке.
#   Файл начинается со строки `% !TEX encoding = UTF-8 Unicode` — это
#   служебная строка текстового редактора автора, к TDB отношения не имеет.
#   Парсер падает на ней (line 1, col 2). Строка КОММЕНТИРУЕТСЯ ('$' —
#   символ комментария TDB), а не удаляется: нумерация строк сохраняется,
#   и файл остаётся сличимым с исходником построчно.
MC_AL_TEX_YAKOR = "% !TEX encoding = UTF-8 Unicode"

# Починка mc_al-2: MatCalc-специфичные команды.
#   REFERENCE_ELEMENT / ATTACH_CONTRIBUTION / ADD_COMPOSITION_SET — команды
#   самого MatCalc, не входящие в набор команд TDB; pycalphad их не знает и
#   падает. Комментируются. Ни одна из них не задаёт термодинамических
#   параметров: REFERENCE_ELEMENT объявляет элемент отсчёта, две другие —
#   указания GUI MatCalc, какую фазу присоединить и какой композиционный
#   набор добавить. На энергии Гиббса они не влияют.
#   (В mc_fe строка REFERENCE_ELEMENT уже закомментирована апстримом —
#   сверено: mc_fe строка 158 начинается с '$'.)
MC_AL_KOMANDY = ("REFERENCE_ELEMENT", "ATTACH_CONTRIBUTION", "ADD_COMPOSITION_SET")
MC_AL_KOMAND_VHOZHDENIY = {"REFERENCE_ELEMENT": 1, "ATTACH_CONTRIBUTION": 1,
                           "ADD_COMPOSITION_SET": 1}

# Починка mc_al-3: типы параметров, которых нет в стандарте TDB.
#   HMVA (энтальпия образования вакансии) и SE (поверхностная энергия) —
#   расширения MatCalc. Список допустимых типов у pycalphad —
#   pycalphad.io.tdb_keywords.TDB_PARAM_TYPES, и этих двух там нет.
#   Комментируются. Обе величины НЕ входят в энергию Гиббса фаз и потому
#   не могут сдвинуть солидус/ликвидус: HMVA используется MatCalc в
#   кинетике диффузии, SE — в расчёте зародышеобразования. Наш слой ни
#   кинетики, ни зародышеобразования не считает.
MC_AL_TIPY = ("HMVA", "SE")
MC_AL_TIPOV_VHOZHDENIY = 8          # 7 строк HMVA + 1 строка SE

MC_AL_SHA_ISHODNIKA = "d68f46b039fa3d869693c52636beb3de1029a7758ea921b5989b5a3f41e43d2c"
MC_AL_SHA_REZULTATA = "8f87bbd03bc35c616239148f381c052890e95285db2ae51e8188669ac404af36"


def pochinit_mc_al(tekst):
    _sverit("mc_al_v2.036.tdb", tekst, "до")
    assert tekst.startswith(MC_AL_TEX_YAKOR), (
        "mc_al: первая строка не TeX-директива — база не та, что в манифесте")
    out = "$ " + tekst[1:]

    for cmd in MC_AL_KOMANDY:
        bylo = len(re.findall(r"(?m)^%s\b" % cmd, out))
        ozhid = MC_AL_KOMAND_VHOZHDENIY[cmd]
        assert bylo == ozhid, (
            f"mc_al: команд {cmd} найдено {bylo}, ожидалось {ozhid}")
        out = re.sub(r"(?m)^(%s\b)" % cmd, r"$\1", out)
        assert len(re.findall(r"(?m)^%s\b" % cmd, out)) == 0

    shablon = r"(?mi)^(PARAMETER +(?:%s)\()" % "|".join(MC_AL_TIPY)
    out, n = re.subn(shablon, r"$\1", out)
    assert n == MC_AL_TIPOV_VHOZHDENIY, (
        f"mc_al: параметров {'/'.join(MC_AL_TIPY)} закомментировано {n}, "
        f"ожидалось {MC_AL_TIPOV_VHOZHDENIY}")
    _sverit("mc_al_v2.036.tdb", out, "после")
    return out


# --------------------------------------------------------------------------
# mc_ni (APP-304а)
# --------------------------------------------------------------------------
# Починка mc_ni-1: кодировка. Файл НЕ в UTF-8 — в нём ровно 4 байта latin-1
#   (0xF6 = 'ö', 0xFC = 'ü'), и все четыре стоят в БИБЛИОГРАФИИ: фамилия
#   «Markström» дважды и журнал «Z. für Metallkde» дважды. `read_text(utf-8)`
#   на этом падает. Файл перекодируется latin-1 -> UTF-8: символы
#   сохраняются как есть, ни одного числа правка коснуться не может — все
#   четыре места лежат в строках списка литературы.
MC_NI_NE_ASCII = 4

# Починка mc_ni-2: MatCalc-специфичные команды (те же, что в mc_al).
#   REFERENCE_ELEMENT (1), ATTACH_CONTRIBUTION (1), ADD_COMPOSITION_SET (9).
#   Ни одна не задаёт термодинамических параметров; pycalphad их не знает и
#   падает на первой же (ParseException, строка 167).
MC_NI_KOMANDY = {"REFERENCE_ELEMENT": 1, "ATTACH_CONTRIBUTION": 1,
                 "ADD_COMPOSITION_SET": 9}

# Починка mc_ni-3: параметры типа HMVA (13 штук).
#   Как и в mc_al — тип не из стандарта TDB (нет в
#   pycalphad.io.tdb_keywords.TDB_PARAM_TYPES). Энтальпия образования
#   вакансии в энергию Гиббса фаз не входит, слой кинетики не считает.
#
#   ВАЖНОЕ ОТЛИЧИЕ ОТ mc_al: здесь запись HMVA занимает ТРИ строки —
#       PARAMETER HMVA(FCC_A1,*;0)
#        273.00 +170000; 6000.00  N
#       REF:151 !
#   Закомментировать только первую (как сделано в mc_al, где запись в две
#   строки) нельзя: осиротевшая числовая строка сама по себе не разбирается
#   (ParseException, строка 198). Поэтому комментируется ЗАПИСЬ ЦЕЛИКОМ — от
#   `PARAMETER HMVA(` до строки с завершающим `!`.
MC_NI_HMVA_ZAPISEJ = 13

# Починка mc_ni-4: опечатка апстрима в верхнем пределе температуры.
#   Две записи SIGMA несут `6000.00.00` вместо `6000.00` — число с двумя
#   точками, pycalphad падает на нём (ParseException, строка 7676). Тот же
#   дефект есть и в оригинале mc_fe на matcalc.at, у тех же двух параметров
#   G(SIGMA,FE:CR:FE;0) и G(SIGMA,FE:CR:MN;0); в mc_fe он к нам не приехал
#   только потому, что слой берёт починенное общиной зеркало
#   (steel_database_fix.tdb). Здесь исходник взят с первоисточника, и
#   чинить приходится самим.
#
#   Правка синтаксическая: `6000.00.00` -> `6000.00`. Верхний предел и без
#   того 6000 K по всей базе; коэффициенты не трогаются. Якорь `6000.00.00`
#   в файле встречается ровно дважды и только в строках PARAMETER — это
#   проверяется assert'ом, иначе правка могла бы задеть даты в шапке
#   (в комментариях есть `20.08.2024` и `5.44.0`, тоже с двумя точками).
MC_NI_TOCHKA_YAKOR = "6000.00.00"
MC_NI_TOCHKA_ZAMENA = "6000.00"
MC_NI_TOCHKA_VHOZHDENIJ = 2

# Починка mc_ni-5: у списка литературы нет открывающего ключевого слова.
#   В mc_al блок ссылок начинается строкой `LIST_OF_REFERENCES` (строка
#   6968), и pycalphad по ней понимает, что дальше идёт библиография. В
#   mc_ni этого слова НЕТ: блок начинается сразу с первой ссылки после
#   комментария «$ E) List of references». Без ключевого слова парсер
#   читает всю библиографию как одну команду и падает.
#   Слово вставляется перед первой ссылкой — ровно то же место и та же
#   структура, что в mc_al. Ни одного параметра правка не касается:
#   библиография в расчёт не входит.
MC_NI_REF_YAKOR = "A00201-0    unary               A.T. Dinsdale,"
MC_NI_REF_SLOVO = "LIST_OF_REFERENCES"

MC_NI_SHA_ISHODNIKA = "84ba813156e1f7d8bde495d74420319afec03572b981f6b56103807f305313ab"
MC_NI_SHA_REZULTATA = "51d2445aa8e2951834878be9e7f9a667b88d09eed248f9907052e05503128322"


def pochinit_mc_ni(tekst):
    _sverit("mc_ni_v2036.tdb", tekst, "до")
    # mc_ni-2: команды MatCalc
    out = tekst
    for cmd, ozhid in MC_NI_KOMANDY.items():
        bylo = len(re.findall(r"(?m)^%s\b" % cmd, out))
        assert bylo == ozhid, (
            f"mc_ni: команд {cmd} найдено {bylo}, ожидалось {ozhid} — "
            f"база не та, что описана в манифесте")
        out = re.sub(r"(?m)^(%s\b)" % cmd, r"$\1", out)
        assert len(re.findall(r"(?m)^%s\b" % cmd, out)) == 0

    # mc_ni-3: записи HMVA целиком
    stroki = out.split("\n")
    zakommentirovano = 0
    i = 0
    while i < len(stroki):
        if stroki[i].upper().startswith("PARAMETER HMVA("):
            j = i
            while j < len(stroki) and "!" not in stroki[j]:
                stroki[j] = "$" + stroki[j]
                j += 1
            assert j < len(stroki), (
                "mc_ni: запись HMVA не закрыта '!' — файл оборван")
            stroki[j] = "$" + stroki[j]
            zakommentirovano += 1
            i = j + 1
            continue
        i += 1
    assert zakommentirovano == MC_NI_HMVA_ZAPISEJ, (
        f"mc_ni: записей HMVA закомментировано {zakommentirovano}, "
        f"ожидалось {MC_NI_HMVA_ZAPISEJ}")
    out = "\n".join(stroki)
    assert not re.search(r"(?mi)^PARAMETER +HMVA\(", out)

    # mc_ni-4: опечатка `6000.00.00`
    n = out.count(MC_NI_TOCHKA_YAKOR)
    assert n == MC_NI_TOCHKA_VHOZHDENIJ, (
        f"mc_ni: якорь '{MC_NI_TOCHKA_YAKOR}' встречается {n} раз, "
        f"ожидалось {MC_NI_TOCHKA_VHOZHDENIJ}")
    # Якорь стоит на строке ПРОДОЛЖЕНИЯ записи, а не на той, что начинается
    # словом PARAMETER. Поэтому проверяем запись целиком: отматываем вверх до
    # начала записи (предыдущая строка с завершающим '!') и требуем, чтобы
    # запись начиналась с PARAMETER и не была комментарием.
    stroki_out = out.split("\n")
    for nomer, s in enumerate(stroki_out):
        if MC_NI_TOCHKA_YAKOR not in s:
            continue
        assert not s.lstrip().startswith("$"), (
            f"mc_ni: якорь '{MC_NI_TOCHKA_YAKOR}' в строке-комментарии "
            f"{nomer + 1} — правка задела бы не то")
        k = nomer
        while k > 0 and "!" not in stroki_out[k - 1]:
            k -= 1
        assert stroki_out[k].upper().lstrip().startswith("PARAMETER"), (
            f"mc_ni: якорь '{MC_NI_TOCHKA_YAKOR}' в строке {nomer + 1} "
            f"принадлежит записи {stroki_out[k].strip()[:60]!r}, а не PARAMETER")
    out = out.replace(MC_NI_TOCHKA_YAKOR, MC_NI_TOCHKA_ZAMENA)
    assert out.count(MC_NI_TOCHKA_YAKOR) == 0

    # mc_ni-5: открывающее слово списка литературы
    assert MC_NI_REF_SLOVO not in out, (
        f"mc_ni: '{MC_NI_REF_SLOVO}' уже есть — база не та, что в манифесте")
    n = out.count(MC_NI_REF_YAKOR)
    assert n == 1, (
        f"mc_ni: якорь первой ссылки встречается {n} раз, ожидалась 1")
    out = out.replace(MC_NI_REF_YAKOR,
                      f"{MC_NI_REF_SLOVO}\n\n{MC_NI_REF_YAKOR}", 1)
    assert out.count(MC_NI_REF_SLOVO) == 1
    _sverit("mc_ni_v2036.tdb", out, "после")
    return out


# --------------------------------------------------------------------------
# COST507 — починок не требует (разбирается как есть, проверено).
# --------------------------------------------------------------------------
COST507_SHA_ISHODNIKA = "6565f4d67695fbbf779d68b9eeeb83e86e44a1a3dde9bafd612d99daffb9c34d"


# Кодировка исходника. Умолчание — UTF-8; отступления записаны ЯВНО и
# поимённо. Молчаливого «попробуем utf-8, не вышло — latin-1» здесь нет
# нарочно: тихий откат к другой кодировке — это ровно то подставление
# правдоподобного вместо пробела, которое слою запрещено.
KODIROVKA_ISHODNIKA = {
    "mc_ni_v2036.tdb": "latin-1",       # починка mc_ni-1, 4 байта в библиографии
}


# Базы ThermoGar (APP-504, вариант Б решения владельца 04.09 07:12).
# Починок на них НЕТ, и это не пропуск, а замер: обе читаются pycalphad
# 0.11.2 начисто (APP-492, п.1), а конвертер ThermoGar не отключил НИ
# ОДНОГО термодинамического параметра — сличены закомментированные
# PARAMETER G/L/TC/BMAGN в исходнике и в результате: 72 против 72 у
# mc_al, 2 против 2 у mc_ni (APP-500, §4.4). Ровно поэтому у обеих
# записей `fn is None`: `pochinit()` отдаёт исходник из `tdb/` как есть,
# в `tdb_pochinennye/` они не попадают, и третьего sha у них нет —
# эффективные байты равны исходным.
MC_AL_TG_SHA = "f02bda0e42ff0733e4b647cbc904643a46c46fc996c57383815ade032a750c45"
MC_NI_TG_SHA = "1dc72c5501eb2d9a1778c5a5622728257572a1dcd0ee218c9b4f9a00e0ad08f8"

POCHINKI = {
    "mc_fe_v2.059.tdb": (pochinit_mc_fe, MC_FE_SHA_ISHODNIKA, MC_FE_SHA_REZULTATA),
    "mc_al_v2037.thermogar.tdb": (None, MC_AL_TG_SHA, None),
    "mc_ni_v2036.garcalc.tdb": (None, MC_NI_TG_SHA, None),
    # Базы, с которых слой ушёл в APP-504. Записи и сами функции починки
    # ОСТАВЛЕНЫ, а не сняты, и причина названа, чтобы через полгода никто
    # не гадал, чинится что-то или нет: (1) файлы `tdb/mc_al_v2.036.tdb` и
    # `tdb/mc_ni_v2036.tdb` лежат в слое и остаются единственным описанием
    # того, ЧТО именно правилось в исходниках MatCalc; (2) на них стоят
    # собственные сторожа `proverki/test_calphad_layer.py`, и снятие
    # починок сняло бы проверку без замены. В расчёт эти записи больше не
    # попадают: `granicy.BAZY` их не называет (APP-504).
    "mc_al_v2.036.tdb": (pochinit_mc_al, MC_AL_SHA_ISHODNIKA, MC_AL_SHA_REZULTATA),
    "mc_ni_v2036.tdb": (pochinit_mc_ni, MC_NI_SHA_ISHODNIKA, MC_NI_SHA_REZULTATA),
    "COST507.tdb": (None, COST507_SHA_ISHODNIKA, None),
}


def effektivnye_bajty(imya):
    """Байты, которые получает парсер, — и ровно те, по которым взят sha256.

    APP-502 п. 2 (в): исходник читается ОДИН раз, починка идёт в памяти,
    хеш берётся по тем же байтам. Второго чтения с диска между проверкой
    хеша и разбором нет — подменить файл в этот зазор нечем.
    """
    if imya not in POCHINKI:
        raise KeyError(f"нет описания починки для {imya}")
    fn, sha_ish, sha_rez = POCHINKI[imya]
    syrye = prochitat_bajty(ISHODNIKI / imya)
    assert hashlib.sha256(syrye).hexdigest() == sha_ish
    if fn is None:
        effective = syrye
    else:
        kod = KODIROVKA_ISHODNIKA.get(imya, "utf-8")
        effective = fn(syrye.decode(kod)).encode("utf-8")
    if sha_rez is not None:
        assert hashlib.sha256(effective).hexdigest() == sha_rez
    return effective


def sha256_effektivnyh_bajt(imya):
    """Hash exact bytes that ``Database`` consumes, without writing a file."""
    return hashlib.sha256(effektivnye_bajty(imya)).hexdigest()


def pochinit(imya, peresobrat=False):
    """Вернуть путь к готовому к чтению TDB. Идемпотентно.

    Проверяет sha256 исходника ДО правки: чужой файл под знакомым именем
    не пройдёт. Если для базы известен ожидаемый sha256 результата —
    проверяет и его.
    """
    if imya not in POCHINKI:
        raise KeyError(f"нет описания починки для {imya}")
    fn, sha_ish, sha_rez = POCHINKI[imya]
    src = ISHODNIKI / imya
    if not src.exists():
        raise FileNotFoundError(f"нет исходника {src}")
    fakt = sha256_fajla(src)
    assert fakt == sha_ish, (
        f"{imya}: sha256 исходника {fakt}, в манифесте {sha_ish} — "
        f"файл подменён или скачан другой версией")
    if fn is None:
        return src

    POCHINENNYE.mkdir(exist_ok=True)
    dst = POCHINENNYE / imya
    if dst.exists() and not peresobrat and (sha_rez is None
                                            or sha256_fajla(dst) == sha_rez):
        return dst
    # Кодировка исходника — по имени файла, из явной таблицы (см. её
    # комментарий). Починка mc_ni-1 живёт здесь: перекодировка обязана
    # случиться ДО любых текстовых правок.
    kod = KODIROVKA_ISHODNIKA.get(imya, "utf-8")
    syrye = prochitat_bajty(src)
    if kod != "utf-8":
        ne_ascii = sum(1 for b in syrye if b > 0x7F)
        assert ne_ascii == MC_NI_NE_ASCII, (
            f"{imya}: не-ASCII байтов {ne_ascii}, ожидалось "
            f"{MC_NI_NE_ASCII} — файл не тот, что описан в манифесте")
    tekst = syrye.decode(kod)
    out = fn(tekst)
    dst.write_text(out, encoding="utf-8")
    if sha_rez is not None:
        fakt_rez = sha256_fajla(dst)
        assert fakt_rez == sha_rez, (
            f"{imya}: sha256 после починки {fakt_rez}, ожидался {sha_rez}")
    return dst


def main():
    for imya in POCHINKI:
        put = pochinit(imya, peresobrat=True)
        print(f"{imya}: готово -> {put.relative_to(HERE)}  sha256 {sha256_fajla(put)}")


if __name__ == "__main__":
    main()
