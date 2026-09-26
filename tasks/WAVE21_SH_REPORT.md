# Отчёт 21-Ш: документы пользователя под 0.5.0 — попутные места 21-Ч

Ветка `wave21-sh` от `96ea05bb706482cc04ac3cc1af121be3eb38d258` (`origin/wave21-ch`,
сверено `git ls-remote`). Дерево `D:\Pets\ThermoGar-w21a`. Исполнитель — Claude Opus 5.5,
26.09.2026.

## ШАГ 0

- `git status --short` до начала — только `?? _to_delete/`.
- `git fetch origin` — без ошибок; `git ls-remote origin wave21-ch` —
  `96ea05bb706482cc04ac3cc1af121be3eb38d258`.
- `git switch --detach 96ea05b…; git switch -c wave21-sh`.
- Задание без первой строки «/caveman ultra» — `tasks/WAVE21_SH_OPUS.md`, первый коммит
  ветки `e77bf86`.

## ШАГ 1. Правки

Одним скриптом Python: «было»/«стало» взяты разбором блоков из `tasks/WAVE21_SH_OPUS.md`
(дословно, с переносами строк), файлы — UTF-8 без BOM, концы строк LF (как в файлах,
`.gitattributes` — `text eol=lf`). До записи для каждой правки проверено: «было»
встречается ровно один раз. Номера строк «было» на `96ea05b` — замер скрипта.

| Метка | Файл:строка после правки | Строки «было» на 96ea05b | Сверка с номером мастера |
|---|---|---|---|
| У1 | USER_GUIDE_THERMOGAR.md:106–110 | 106–109 | сверено |
| У2 | USER_GUIDE_THERMOGAR.md:214–217 | 213 | сверено (вставка после :213) |
| У3 | USER_GUIDE_THERMOGAR.md:259 | 255 | сверено |
| У4 | USER_GUIDE_THERMOGAR.md:347 | 343 | сверено |
| У5 | USER_GUIDE_THERMOGAR.md:353–354 | 349–350 | сверено |
| У6 | USER_GUIDE_THERMOGAR.md:452 | 448 | сверено |
| У7 | USER_GUIDE_THERMOGAR.md:463 | 459 | сверено |
| У8 | USER_GUIDE_THERMOGAR.md:476–479 | 472–473 | сверено |
| К1 | QUICK_START_THERMOGAR.md:19–21 | 19–21 | сверено |
| К2 | QUICK_START_THERMOGAR.md:26–27 | 26–27 | сверено |
| Р1 | README.md:20 | 20 | сверено |
| Р2 | README.md:30 | 30 | сверено |
| Р3 | README.md:32 | 32 | сверено |
| Р4 | README.md:201–204 | 201–203 | сверено |
| Р5 | README.md:207 | 206 | сверено |

Коммит правок — `93b7f4b`.

## ШАГ 2. Проверка

Скрипт после записи:

```
У1 | USER_GUIDE_THERMOGAR.md:106–110 | стало×1 | было×0 | OK
У2 | USER_GUIDE_THERMOGAR.md:214–217 | стало×1 | было×1 (внутри «стало») | OK
У3 | USER_GUIDE_THERMOGAR.md:259–259 | стало×1 | было×0 | OK
У4 | USER_GUIDE_THERMOGAR.md:347–347 | стало×1 | было×0 | OK
У5 | USER_GUIDE_THERMOGAR.md:353–354 | стало×1 | было×0 | OK
У6 | USER_GUIDE_THERMOGAR.md:452–452 | стало×1 | было×0 | OK
У7 | USER_GUIDE_THERMOGAR.md:463–463 | стало×1 | было×0 | OK
У8 | USER_GUIDE_THERMOGAR.md:476–479 | стало×1 | было×0 | OK
К1 | QUICK_START_THERMOGAR.md:19–21 | стало×1 | было×0 | OK
К2 | QUICK_START_THERMOGAR.md:26–27 | стало×1 | было×0 | OK
Р1 | README.md:20–20 | стало×1 | было×0 | OK
Р2 | README.md:30–30 | стало×1 | было×0 | OK
Р3 | README.md:32–32 | стало×1 | было×0 | OK
Р4 | README.md:201–204 | стало×1 | было×0 | OK
Р5 | README.md:207–207 | стало×1 | было×0 | OK
ИТОГ: OK
```

«Было» У2 целиком входит в «стало» и встречается один раз — внутри него. «Было» У8
(две строки) в «стало» целиком не входит: вторая строка дописана, поэтому «было»×0.

`git diff --stat 96ea05b` (после коммита правок):

```
 QUICK_START_THERMOGAR.md |  10 +--
 README.md                |  13 +--
 USER_GUIDE_THERMOGAR.md  |  28 ++++---
 tasks/WAVE21_SH_OPUS.md  | 205 +++++++++++++++++++++++++++++++++++++++++++++++
 4 files changed, 234 insertions(+), 22 deletions(-)
```

Только три файла и `tasks\` (отчёт добавлен следующим коммитом).

Заголовки `git diff -U0 96ea05b` по трём файлам:

```
QUICK_START_THERMOGAR.md: @@ -19,3 +19,3 @@   @@ -26,2 +26,2 @@
README.md:                @@ -20 +20 @@  @@ -30 +30 @@  @@ -32 +32 @@  @@ -202,2 +202,3 @@  @@ -206 +207 @@
USER_GUIDE_THERMOGAR.md:  @@ -106,4 +106,5 @@  @@ -214,0 +216,3 @@  @@ -255 +259 @@  @@ -343 +347 @@
                          @@ -349,2 +353,2 @@  @@ -448 +452 @@  @@ -459 +463 @@  @@ -473 +477,3 @@
```

- Строки 1–3 трёх файлов — не затронуты.
- README.md:99–104 — не затронуты.
- QUICK_START_THERMOGAR.md:11 — не затронута.
- Пример остановки расчёта выделений (на 96ea05b — USER_GUIDE_THERMOGAR.md:301–319,
  от «**Расчёт остановлен: добавка вычерпана из матрицы.**» до кадра
  `soobshcheniya-04.png`; после правок — :305–323) — не затронут.

Git показывает вставку У2 как `@@ -214,0 +216,3 @@` (после пустой строки :214), а
первую строку Р4 — как неизменную (`-202,2`): это выравнивание diff, текст файла
совпадает с «стало».

## ШАГ 3. Тест

`tools/test_version_consistency.py` (`python -B -m pytest -p no:cacheprovider`,
PYTHONHASHSEED=0, MPLBACKEND=Agg, PYTHONDONTWRITEBYTECODE=1, THERMOGAR_STATE_ROOT —
временная папка, интерпретатор `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe`):

- до правок (на `e77bf86`): `92 passed`;
- после правок (на `93b7f4b`): `92 passed`.

## Отступления

- Прогон теста «до правок» сделан дополнительно к ШАГУ 3 — для строки «тест до и
  после» в ШАГЕ 4; это тот же единственный разрешённый тест.
- `pytest` запущен с `-p no:cacheprovider`, чтобы не создавать `.pytest_cache` в дереве.
- Вывод `git log`/`git status`/`git ls-remote` ниже снят после пуша коммита с отчётом;
  коммит, который дописывает этот вывод, в него не входит по построению.

## Git
