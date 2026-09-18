# Родословная конвертации баз MatCalc в ThermoGar — пакет 16-Б для «Лилит»

Составлено 17.09.2026, волна 16-Б, ветка `wave15-release` дерева `ThermoGar-w15e`
(вершина на входе `e859429`). Расчётов равновесий и запуска приложения не было.
Байты `databases/` не менялись.

**Итог.**

* Конвертер изменил числа в **двух** параметрах: `G(PDMN_B2,MN:PD;0)` и
  `G(PDMN_B2,PD:MN;0)` базы `mc_fe` 2.062 (раздел 3). Это касается только систем
  с Pd на стальной базе. На `mc_ni` 2.036 и `mc_al` 2.037 изменённых чисел нет.
* Ещё семь мест — синтаксический ремонт числовых токенов, значений он не меняет
  (раздел 4).
* Патч `TG-FE-2062-C15-001` есть и в чистом Fe-файле, не только в слитом
  (раздел 5).
* Скрипт каждого из шести файлов установлен **воспроизведением байт в байт**,
  а не по признакам (раздел 1).

Все sha256 ниже взяты из вычисления (`sha256sum`), не из документов.

---

## 0. Файлы и отпечатки

| роль | файл | байт | sha256 |
|---|---|---|---|
| исходник Ni | `databases/original/ni/mc_ni_v2036.tdb` | 416720 | `84ba813156e1f7d8bde495d74420319afec03572b981f6b56103807f305313ab` |
| исходник Al | `databases/original/al/mc_al_v2037.tdb` | 308711 | `87ec595f2caae189227ed11d5598c899b436b866ccfefea91304ca57188817c4` |
| исходник Fe | `databases/original/fe/mc_fe_v2062.tdb` | 489296 | `aa02077eac3f602dd7479cbeafb09b450e282716752b3ae2b1fc3a57d9c64865` |
| чистый Ni | `databases/converted/mc_ni_v2036.garcalc.tdb` | 410655 | `1dc72c5501eb2d9a1778c5a5622728257572a1dcd0ee218c9b4f9a00e0ad08f8` |
| чистый Al | `databases/converted/al/mc_al_v2037.thermogar.tdb` | 314577 | `f02bda0e42ff0733e4b647cbc904643a46c46fc996c57383815ade032a750c45` |
| чистый Fe | `databases/converted/fe/mc_fe_v2062.thermogar.tdb` | 483426 | `def6c6862458e879b75cabb32e3bfc93a674f981df7c89e5f0e6e40c246620ed` |
| слитый Ni | `databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb` | 466074 | `1882d841a337063e0585d261c690ae7e565838234e231e21b8541a5cb0dba391` |
| слитый Al | `databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb` | 351241 | `f9bdf21d434fbe78b5ef3f7f2de69763fa40b81335cdc58889907d41c80cd717` |
| слитый Fe | `databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb` | 568690 | `236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612` |

### Концы строк и кодировка

Диффы раздела 2 сделаны по **нормализованным** копиям: CRLF заменён на LF, текст
перекодирован в UTF-8. Без нормализации каждая строка Ni и Fe отличалась бы только
переводом строки.

| файл | концы строк | кодировка | BOM |
|---|---|---|---|
| исходник Ni | CRLF, все 10687 строк | cp1252 (4 байта вне ASCII) | нет |
| исходник Al | LF, все 7818 строк | UTF-8 | нет |
| исходник Fe | CRLF, все 12629 строк | cp1252 (9 байт вне ASCII) | нет |
| все шесть конвертированных | LF | UTF-8 | нет |

То есть конвертер у Ni и Fe дополнительно сменил CRLF на LF и cp1252 на UTF-8. В
диффах это не видно: смена кодировки не меняет ни одного символа, смена концов
строк — ни одного символа, кроме самого перевода строки.

---

## 1. Какой скрипт и какой коммит породил каждый файл

### 1.1 Таблица

| файл | sha256 | появился (коммит, дата) | последняя правка | скрипт | улика |
|---|---|---|---|---|---|
| чистый Ni | `1dc72c55…e0ad08f8` | `7271446`, 02.09.2026 15:26 +0300 | тот же `7271446` | `scripts/garcalc_convert_matcalc_tdb.py` | воспроизведён байт в байт из исходника Ni; 10 ключей `changes`; метки `GARCALC_*` |
| чистый Al | `f02bda0e…2a750c45` | `7271446`, 02.09.2026 | тот же | `scripts/thermogar_convert_matcalc_tdb_v2.py` | воспроизведён байт в байт; 18 ключей `changes` |
| чистый Fe | `def6c686…c246620ed` | `7271446`, 02.09.2026 | тот же | `scripts/thermogar_convert_matcalc_tdb.py`, профиль по умолчанию `thermogar` (патч включён) | воспроизведён байт в байт; 19 ключей `changes`; в паспорте `compatibility_profile: thermogar` и запись патча |
| слитый Ni | `1882d841…b0dba391` | `7271446`, 02.09.2026 | тот же | `scripts/garcalc_merge_matcalc_ddb.py` + `mc_ni_v2012.ddb` | воспроизведён байт в байт из чистого Ni; метки `GARCALC MOBILITY BLOCK` |
| слитый Al | `f9bdf21d…41c80cd717` | `7271446`, 02.09.2026 | тот же | `scripts/thermogar_merge_matcalc_ddb.py` или `_v3` (дают одинаковый файл) + `mc_al_v2008.ddb` | воспроизведён байт в байт из чистого Al; `_v2` и `garcalc_merge` дают другие байты |
| слитый Fe | `236ec4d9…bd98053612` | `7271446`, 02.09.2026 | тот же | `scripts/thermogar_merge_matcalc_ddb.py`, `_v2` или `_v3` (дают одинаковый файл) + `mc_fe_v2016.ddb` | воспроизведён байт в байт из чистого Fe |

**Что даёт git и чего не даёт.** Команда
`git log --follow --format='%h %ad %s' -- <файл>` для каждого из шести файлов и
шести паспортов `.tdb.json` выдаёт одну строку:

```
7271446 2026-09-02 15:26:27 +0300 Inherited ThermoGar state from Codex, root cleaned (wave 0)
```

Это корневой коммит репозитория (`727144635656cd620aec905be5d54b72222c6ea0`).
Файлы пришли в него готовыми из прежнего состояния проекта и с тех пор не менялись.
Сообщение коммита скрипта не называет. Пути в паспортах (`/Volumes/Disk/Pet/ThermoGar/…`)
говорят, что конвертация шла на другой машине до 02.09. Поэтому атрибуция выше
опирается не на историю git, а на воспроизведение.

### 1.2 Воспроизведение

Каждый конвертер прогнан на каждом исходнике, каждый скрипт слияния — на каждом
чистом файле. Вывод шёл во временный каталог, вне репозитория. Совпавшие sha:

| вход | скрипт | sha256 результата | совпадает с |
|---|---|---|---|
| исходник Ni | `garcalc_convert_matcalc_tdb.py` | `1dc72c55…` | чистым Ni |
| исходник Ni | `thermogar_convert_matcalc_tdb.py` | `6d166c92…` | — |
| исходник Ni | `thermogar_convert_matcalc_tdb_v2.py` | `e4c2bb03…` | — |
| исходник Al | `garcalc_convert_matcalc_tdb.py` | `d1b2adb5…` | — |
| исходник Al | `thermogar_convert_matcalc_tdb.py` | `4414707f…` | — |
| исходник Al | `thermogar_convert_matcalc_tdb_v2.py` | `f02bda0e…` | чистым Al |
| исходник Fe | `garcalc_convert_matcalc_tdb.py` | `acc0a182…` | — |
| исходник Fe | `thermogar_convert_matcalc_tdb.py` (профиль по умолчанию) | `def6c686…` | чистым Fe |
| исходник Fe | `thermogar_convert_matcalc_tdb.py --compatibility-profile upstream` | `99b5cd56…` | `databases/diagnostic/fe/mc_fe_v2062_unpatched.thermogar.tdb` |
| исходник Fe | `thermogar_convert_matcalc_tdb_v2.py` | `319a92b0…` | — (см. раздел 5.3) |
| чистый Ni + `mc_ni_v2012.ddb` | `garcalc_merge_matcalc_ddb.py` | `1882d841…` | слитым Ni |
| чистый Al + `mc_al_v2008.ddb` | `thermogar_merge_matcalc_ddb.py`, `_v3` | `f9bdf21d…` | слитым Al |
| чистый Fe + `mc_fe_v2016.ddb` | `thermogar_merge_matcalc_ddb.py`, `_v2`, `_v3` | `236ec4d9…` | слитым Fe |
| диагностический Fe без патча + `mc_fe_v2016.ddb` | `thermogar_merge_matcalc_ddb.py`, `_v2`, `_v3` | `f9375c3a…` | `databases/diagnostic/fe/mc_fe_v2062_unpatched_with_mobility.thermogar.tdb` |
| Fe после `_v2` (`319a92b0…`) + `mc_fe_v2016.ddb` | `garcalc_merge_matcalc_ddb.py` | `be09d445…` | источником из манифеста `experimental/fe` (раздел 5.3) |

Команды, из корня дерева:

```
python scripts/<конвертер>.py databases/original/<база>.tdb <каталог>/<имя>.tdb
python scripts/thermogar_convert_matcalc_tdb.py --compatibility-profile upstream databases/original/fe/mc_fe_v2062.tdb <каталог>/fe_up.tdb
python scripts/<скрипт слияния>.py <чистый>.tdb databases/original/<база>.ddb <каталог>/<имя>.tdb
```

### 1.3 Ключи `changes` в паспорте

| конвертер | число ключей `changes` | файлы |
|---|---|---|
| `scripts/garcalc_convert_matcalc_tdb.py` | 10 | `mc_ni_v2036.garcalc.tdb` |
| `scripts/thermogar_convert_matcalc_tdb_v2.py` | 18 | `mc_al_v2037.thermogar.tdb` |
| `scripts/thermogar_convert_matcalc_tdb.py` | 19 (те же 18 плюс `known_compatibility_parameters_disabled`) | `mc_fe_v2062.thermogar.tdb`; `databases/diagnostic/fe/mc_fe_v2062_unpatched.thermogar.tdb` |

Ключ `known_compatibility_parameters_disabled` пишет только
`thermogar_convert_matcalc_tdb.py` (`scripts/thermogar_convert_matcalc_tdb.py:414`).
`_v2` его не пишет, то есть у `_v2` 18 ключей, а не 19.

**Утверждение «алюминиевый и стальной — `_v2` (19 ключей)» в ответах мастера
ThermoGar от 16.09.2026 (раздел А, вопрос 1) неверно.** Алюминиевый файл сделан
`_v2`, но ключей у него 18. Стальной сделан не `_v2`, а
`thermogar_convert_matcalc_tdb.py`, и 19 ключей — это его признак.

---

## 2. Машинный дифф «исходник → конвертация»

Файлы диффов — рядом, `diff -u` по нормализованным копиям (раздел 0), в заголовках
настоящие пути:

* `diff_mc_ni_v2036.garcalc.patch` — исходник Ni → чистый Ni;
* `diff_mc_al_v2037.thermogar.patch` — исходник Al → чистый Al;
* `diff_mc_fe_v2062.thermogar.patch` — исходник Fe → чистый Fe;
* `diff_mc_ni_v2036_with_mobility.garcalc.patch` — чистый Ni → слитый Ni;
* `diff_mc_al_v2037_with_mobility.thermogar.patch` — чистый Al → слитый Al;
* `diff_mc_fe_v2062_with_mobility.thermogar.patch` — чистый Fe → слитый Fe.

Сводку ниже печатает `proverka_diffov.py` (только стандартная библиотека, базы не
загружает); её вывод лежит в `proverka_diffov_vyvod.txt`.

**Как считалось.** Смежные строки `-`/`+` образуют блок. Каждый блок отнесён к
одному из трёх видов:

* «только комментарии» — добавлены или сняты только строки `$` и пустые;
* «отключённые команды» — активные строки сняты и дословно вернулись комментарием,
  активного не добавлено;
* «синтаксис» — активные строки переписаны или добавлены.

Отдельно в каждом блоке сравнивались числовые токены активных строк. Токен,
который ушёл из активного текста и не вернулся ни в новый активный текст, ни в
добавленный комментарий, — находка. Находкой считается и токен, появившийся в
активном тексте ниоткуда. «Изменено» — сумма по блокам меньшего из чисел снятых и
добавленных строк.

| дифф | +строк | −строк | изменено | только комментарии: блоков (+строк) | отключённые команды: блоков / активных строк отключено* | синтаксис: блоков | мест с числовыми токенами | изменённых чисел |
|---|---|---|---|---|---|---|---|---|
| Ni: исходник → чистый | 349 | 278 | 248 | 1 (+4) | 10 / 50 | 106 | 2 | **0** |
| Al: исходник → чистый | 521 | 426 | 357 | 1 (+4) | 7 / 21 | 200 | 0 | **0** |
| Fe: исходник → чистый | 503 | 428 | 369 | 1 (+5) | 9 / 79 | 151 | 7 | **2** (`PDMN_B2`, раздел 3) |
| Ni: чистый → слитый | 1751 | 0 | 0 | 1 (+1035) | 0 / 0 | 1 (вставка блока подвижностей, +716) | — | **0** |
| Al: чистый → слитый | 1145 | 0 | 0 | 1 (+634) | 0 / 0 | 1 (вставка, +511) | — | **0** |
| Fe: чистый → слитый | 2781 | 1 | 1 | 1 (+1622, −1) | 0 / 0 | 1 (вставка, +1159) | — | **0** |

\* Активные строки, дословно сохранённые комментарием, считаются по всем блокам,
включая «синтаксис» (например, `ATTACH_CONTRIBUTION` рядом с новым
`TYPE_DEFINITION`). Сверка с паспортами: Ni — 1 `REFERENCE_ELEMENT` +
1 `ATTACH_CONTRIBUTION` + 9 `ADD_COMPOSITION_SET` + 13 `HMVA` × 3 строки = 50;
Fe — 1 + 1 + 12 + 21 × 3 + 2 строки команды C15 = 79.

**Что в «синтаксисе».**

* Описания фаз MatCalc (`> … >> n`) сняты с активной строки `PHASE` и сохранены
  комментарием. Их числа (приоритет `n`) — в комментарии, находкой они не
  считаются.
* Добавлены `TYPE_DEFINITION` и символы типа фазы.
* У Fe исправлены разделитель в `G(G_PHASE;…)` и недостающий `!` в
  `L(LAVES_PHASE,MN,TI:NI;0)`.
* Нормализованы ключи ссылок, добавлен маркер списка литературы.
* Места с числовыми токенами — разделы 3 и 4.

**Слои подвижностей.** Все три диффа «чистый → слитый» состоят из двух вставок:
блок подвижностей перед `LIST_OF_REFERENCES` и архив исходного `.ddb` комментариями
в конце. Из термодинамической части не снято ни одной строки. Единственная снятая
строка в Fe — пустая строка в конце списка литературы, на её месте начинается
архив `.ddb`.

---

## 3. Изменённые числа

**Где.** Только `mc_fe` 2.062, фаза `PDMN_B2`, два параметра. Номера строк в слитом
Fe-файле те же, что в чистом: блок подвижностей вставлен ниже, с строки 12116.

| параметр | строка исходника | строка чистого и слитого Fe | до конвертации | после |
|---|---|---|---|---|
| `G(PDMN_B2,MN:PD;0)` | 8232 | 8261 | `PARAMETER G(PDMN_B2,MN:PD;0) 273.00 273 +46000-23*T` | `PARAMETER G(PDMN_B2,MN:PD;0) 273.00 +46000-23*T` |
| `G(PDMN_B2,PD:MN;0)` | 8236 | 8265 | `PARAMETER G(PDMN_B2,PD:MN;0) 273.00 273 +46000-23*T` | `PARAMETER G(PDMN_B2,PD:MN;0) 273.00 +46000-23*T` |

**Кто снял.** Токен `273` снимает правило
`re.subn(r"\b273\.00\s+273\b", "273.00", line)` с комментарием «Known duplicated
tokens in the PDMN_B2 expression» (`scripts/thermogar_convert_matcalc_tdb.py:583–585`).
Паспорт считает это в `duplicated_temperature_tokens_repaired: 2`.

**Два чтения исходной строки.**

1. **`273` — дубль нижней границы температуры.** Выражение начинается с `+46000`,
   свободный член 46000 Дж/моль. Так прочёл конвертер; тогда конвертация значения
   не изменила.
2. **`273 +46000` — одно выражение.** Свободный член 273 + 46000 = 46273 Дж/моль.
   Тогда конвертация сдвинула свободный член обоих параметров на −273 Дж/моль.

**Какое чтение делает MatCalc — неизвестно.** Проверить без MatCalc нельзя. Вопрос
записан к апстриму: `tasks/SOURCES_WANTED.md`, позиция S-8.

**Следствие.** Касается только расчётов на `mc_fe` 2.062, в которых есть и Pd, и
Mn: оба параметра — конечные члены фазы `PDMN_B2` с Mn и Pd на разных подрешётках.
На `mc_ni` 2.036 и `mc_al` 2.037 изменённых чисел нет. Байты базы не правятся
(`tasks/RULES.md`, «Работа с базами»); реестр — BL-42.

---

## 4. Синтаксический ремонт числовых токенов

Решение мастера 16-Б: правки ниже значений не меняют.

| база | параметр | строка исходника | строка чистого (и слитого) файла | до | после | что это |
|---|---|---|---|---|---|---|
| Ni | `G(SIGMA,FE:CR:FE;0)` | 7676 | 7702 | `+4*GHSERCR#+18*GHSERFE#; 6000.00.00  N` | `+4*GHSERCR#+18*GHSERFE#; 6000.00  N` | верхняя граница с лишним `.00`, осталась 6000 |
| Ni | `G(SIGMA,FE:CR:MN;0)` | 7679 | 7705 | `+4*GHSERCR#+18*GMNBCC#; 6000.00.00  N` | `+4*GHSERCR#+18*GMNBCC#; 6000.00  N` | то же |
| Fe | `G(SIGMA,FE:CR:FE;0)` | 7764 | 7787 | `…; 6000.00.00  N` | `…; 6000.00  N` | то же |
| Fe | `G(SIGMA,FE:CR:MN;0)` | 7767 | 7790 | `…; 6000.00.00  N` | `…; 6000.00  N` | то же |
| Fe | `G(PDMN_B2,MN:PD;0)`, хвост | 8234 | 8263 | `-5*T*LN(T)+0.5*GHSERPD#; 6000.00  N ; 6000.00  N` | `-5*T*LN(T)+0.5*GHSERPD#; 6000.00 N` | повтор хвоста `; 6000.00 N` снят |
| Fe | `G(PDMN_B2,PD:MN;0)`, хвост | 8238 | 8267 | `-5*T*LN(T)+0.5*GHSERMN#+0.5*GHSERPD#; 6000.00  N ; 6000.00  N` | `…; 6000.00 N` | то же |
| Fe | `CONSTITUENT MNB4` | 11305 | 11342 | `CONSTITUENT MNB4  : MN : B :  > >> 1 !` | `CONSTITUENT MNB4  : MN : B : !` | остаток описания фазы MatCalc; не параметр, в комментарии не сохранён |

Код правил:
* `6000.00.00` — `re.subn(r"\b(\d+\.\d+)\.\d+([ \t]+[NYny]\b)", …)`
  (`scripts/garcalc_convert_matcalc_tdb.py:249–252`, в паспортах
  `duplicated_decimal_temperatures_repaired: 2`);
* хвост и `MNB4` — `scripts/thermogar_convert_matcalc_tdb.py:588–598`
  (`duplicated_function_tails_repaired: 2`, `mnb4_constituent_relics_repaired: 1`).

В Al таких мест нет.

---

## 5. Патч C15 в чистом Fe-файле

### 5.1 Ответ

* **Строка 5778** чистого файла `databases/converted/fe/mc_fe_v2062.thermogar.tdb`
  закомментирована:
  `$ PARAMETER G(C15_LAVES,FE,NI:MN,SI;0) 273.00 -9e6; 6000.00  N `. Над ней
  блок `$ THERMOGAR_DISABLED: TG-FE-2062-C15-001` (строки 5773–5780), в шапке
  файла — `$ Compatibility patches applied: TG-FE-2062-C15-001`. В слитом файле
  то же, на той же строке 5778.
* **Каким коммитом.** `7271446` (02.09.2026), вместе с файлом. Отдельного коммита
  патча в репозитории нет: патч внесён конвертером `thermogar_convert_matcalc_tdb.py`
  при создании чистого файла, до перехода проекта в этот репозиторий. Паспорт патча
  датирован `2026-08-22T10:57:51+00:00`.
* **Паспорт патча для чистого файла есть, в двух местах.**
  - `databases/converted/fe/mc_fe_v2062.thermogar.tdb.json` содержит
    `compatibility_profile: thermogar`, полную запись патча в
    `compatibility_patches` и `disabled_thermodynamic_parameters`
    (sha исходной команды `E4BE3336…66BB4F4`) и
    `known_compatibility_parameters_disabled: 1`.
  - `databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.passport.json`
    в разделе `working_profile.thermodynamic_database` называет чистый файл
    (`DEF6C686…`) рабочим профилем патча наравне со слитым.
* **Согласие с `SOURCES.txt`.** Нет. `SOURCES.txt`, раздел 4, описывает патч только
  у слитого файла, а чистого файла не называет вовсе.

### 5.2 Предлагаемая правка `SOURCES.txt` (не применена)

В раздел 4, после абзаца о `mc_fe_v2062_with_mobility.thermogar.tdb`:

```
The intermediate thermodynamic-only files the merged ones are built from sit
next to them and are not shipped in the installer:

databases/converted/mc_ni_v2036.garcalc.tdb
    from mc_ni_v2036.tdb
    SHA-256: 1DC72C5501EB2D9A1778C5A5622728257572A1DCD0EE218C9B4F9A00E0AD08F8

databases/converted/al/mc_al_v2037.thermogar.tdb
    from mc_al_v2037.tdb
    SHA-256: F02BDA0E42FF0733E4B647CBC904643A46C46FC996C57383815ADE032A750C45

databases/converted/fe/mc_fe_v2062.thermogar.tdb
    from mc_fe_v2062.tdb, already carrying compatibility patch
    TG-FE-2062-C15-001 (the same single C15_LAVES G parameter disabled and kept
    verbatim as a comment, line 5778); the merged steel file inherits the patch
    from it.
    SHA-256: DEF6C6862458E879B75CABB32E3BFC93A674F981DF7C89E5F0E6E40C246620ED
```

### 5.3 Откуда в манифесте `experimental/fe` sha `be09d445…`

Манифест `databases/experimental/fe/mc_fe_v2062_c15_laves_parameter_disabled.manifest.json`
(создан 22.08.2026 12:50 +03:00) называет источником
`databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb` с sha
`be09d4451b70efad3a2b7fc83bb859249b29dd6d963165b68c7cfcea462243a1`.
**Файла с таким sha в истории git нет**: все версии файлов под `databases/`
пришли корневым коммитом, и нынешний слитый Fe имеет `236ec4d9…`.

Файл восстановлен двумя независимыми путями, оба дают `be09d445…` (568368 байт):

1. **Обратно из экспериментального файла.** Из
   `mc_fe_v2062_c15_laves_parameter_disabled.thermogar.tdb` (`c15d51df…`) снята
   шапка экспериментального профиля (7 строк). Блок
   `THERMOGAR_EXPERIMENTAL_DISABLED_BEGIN … END` заменён исходной командой
   `PARAMETER G(C15_LAVES,FE,NI:MN,SI;0) 273.00 -9e6; 6000.00  N ` / `REF:287 !`
   (её sha совпадает с записанным в манифесте, `e4be3336…`).
2. **Прямо воспроизведением.** `thermogar_convert_matcalc_tdb_v2.py` на исходнике Fe
   (без патча, `319a92b0…`), затем `garcalc_merge_matcalc_ddb.py` с
   `mc_fe_v2016.ddb`.

**Какой это был файл.** Слитый Fe **до патча**, собранный ранней цепочкой: `_v2` и
слияние `garcalc`. Паспорт патча датирован 22.08 13:57 +03:00, то есть через час
после манифеста; это согласуется.

**Совпадает ли с нынешними за вычетом патча.** По параметрам — да, по байтам — нет.

* Против диагностического слитого файла без патча
  `databases/diagnostic/fe/mc_fe_v2062_unpatched_with_mobility.thermogar.tdb`
  (`f9375c3a…`) отличия только в комментариях:
  - одна строка шапки `$ Compatibility patches applied: none`;
  - шесть меток `GARCALC_*` / `GARCALC MOBILITY BLOCK` вместо `THERMOGAR_*`
    (строки 12114, 13256, 13261, 13266, 13857, 15476 файла `be09d445…`).
* Против нынешнего слитого `236ec4d9…` — те же комментарии плюс сам патч: две
  активные строки команды C15 заменены восемью строками блока
  `THERMOGAR_DISABLED` и добавлена строка шапки
  `$ Compatibility patches applied: TG-FE-2062-C15-001`.
* Ни одна активная строка, кроме команды C15, не отличается.

---

## 6. Состав пакета

`SHA256SUMS` рядом покрывает все файлы пакета, кроме самого себя.

* `rodoslovnaya_16B.md` — этот файл;
* шесть `diff_*.patch` — раздел 2;
* `proverka_diffov.py` — сводка диффов, `python proverka_diffov.py`;
* `proverka_diffov_vyvod.txt` — её вывод на этих диффах.
