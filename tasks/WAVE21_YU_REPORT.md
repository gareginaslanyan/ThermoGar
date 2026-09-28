# Отчёт 21-Ю и 21-Ю2 — выпуск 0.5.0 (до слияния)

**Итог.** 21-Ю: ШАГИ 0–6 сделаны, все сверки сошлись. ШАГ 7 — СТОП: в регрессии 77 заданий, 1 красное (`test_ui_h`, 4 теста ждали предпросмотр пакета до BL-78). Сверка эталона — PASS. 21-Ю2: ожидания `tools/test_ui_h.py` поправлены, повтор задания — 24 passed, 2 deselected; в реестре — решение владельца по загрузчикам файлов, ошибка мастера (21-Ю), BL-79. Ветка `wave21-yu` запушена. Слияние в `main`, тег, установщик, установка и приёмка — не делались (задание 21-Ю2: сначала BL-79).

Дерево — `D:\Pets\ThermoGar-w21b`, интерпретатор — `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe`. Все прогоны — `PYTHONHASHSEED=0`, `MPLBACKEND=Agg`, `PYTHONDONTWRITEBYTECODE=1`, pytest с `-B`.

## Время по шагам (27.09.2026, местное)

| задание | шаг | начало | конец |
|---|---|---|---|
| 21-Ю | 0 | 16:09:48 | 16:10:10 |
| 21-Ю | 1 | 16:10:12 | 16:12:40 |
| 21-Ю | 2 | 16:12:52 | 16:16:10 |
| 21-Ю | 3 | 16:16:19 | 16:18:21 |
| 21-Ю | 4 | 16:18:42 | 16:22:02 |
| 21-Ю | 5 | 16:19:30 | 16:22:40 |
| 21-Ю | 6 | 16:22:40 | 16:23:15 |
| 21-Ю | 7 (регрессия) | 16:23:41 | 18:38:16 |
| 21-Ю | 7 (сверка эталона, СТОП) | 18:39 | 18:41 |
| 21-Ю2 | 0 | 19:39:42 | 19:39:50 |
| 21-Ю2 | 1 | 19:39:50 | 19:40:00 |
| 21-Ю2 | 2 | 19:40:00 | 19:40:11 |
| 21-Ю2 | 3 | 19:40:20 | 19:46:25 |
| 21-Ю2 | 4 | 19:46:30 | 19:46:44 |
| 21-Ю2 | 5 | 19:46:50 | см. «Git» |

ШАГ 5 21-Ю шёл во время съёмки ШАГА 4 (правки текстов не трогают приложение); коммиты — по порядку шагов (отступление 5).

## 21-Ю, ШАГ 0

* `git status --short` — `?? _to_delete/`.
* `git fetch origin --tags` — без обрыва.
* `git ls-remote origin main wave21-shch wave21-eh`:

```
062b97503bb1142c38020c33c17b0de30fd15a88	refs/heads/main
5ab5bf1f9dd76b4b3035702fa7b1171efe5202af	refs/heads/wave21-eh
7a73ee081d1414840cb59c2bde14fb63f347c602	refs/heads/wave21-shch
```

* Свободная память — 8,07 ГиБ. `$env:CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP` = `1`.
* Чужой байткод: `app\__pycache__` — 4 файла, `tools\__pycache__` — 1 файл. Перенесены в `_to_delete\21yu_pycache\` (`app\__pycache__\`, `tools\__pycache__\`), опись — `_to_delete\21yu_pycache\OPIS_SHA256.txt`:

```
d770cf4ef587471f4c9a453c09eea3084bc78b2911144e3afaeb4458f13c4879 *app/__pycache__/thermogar_database_repair.cpython-311.pyc
7ce1166283c198f59e52f6eac59dcb6c4ff7ef172258e8fa9d9e3ca06588679c *app/__pycache__/thermogar_db_cache.cpython-311.pyc
437df58399acb3420cd89aa924c18d86fb5c9d59b87cd6fe2fb71e97583310f2 *app/__pycache__/thermogar_parallel.cpython-311.pyc
feb8b0bb3d162a2b23b67ddc3d564f0cfd869f0c96e398adcf7bc8a2f8c5fab0 *app/__pycache__/thermogar_user_errors.cpython-311.pyc
93b5ff0c37075cf820055be582a2465890accdb726a47fdeb893128fbc8ed0dd *tools/__pycache__/make_guide_screens.cpython-311.pyc
```

## 21-Ю, ШАГ 1. Слияния

От `origin/main` (`062b975`), `git merge --no-ff`, оба слияния без конфликтов:

| слияние | коммит | дерево | модель мастера |
|---|---|---|---|
| `origin/wave21-shch` | `ac5be77` | `34b3b0d2b256c139eeddd0267a5e5b90b9a48d4f` | = |
| `origin/wave21-eh` | `47282dc` (`47282dcb2dc8f213be361769c4ed8691f989c0a0`) | `0c729080b772fadc4659f5dcfa9904f1d95c5511` | = |

Тесты на `47282dc` (один прогон pytest, 134 passed; число тестов по файлам — `--collect-only`):

| файл | ожидание | собрано | итог |
|---|---|---|---|
| `test_version_consistency.py` | 93 | 93 | passed |
| `test_installer_shortcut_bl62.py` | 5 | 5 | passed |
| `test_wave21_shch.py` | 16 | 16 | passed |
| `test_wave21_ts.py` | 9 | 9 | passed |
| `test_wave21_ch.py` | 5 | 5 | passed |
| `test_wave21_x.py` | 6 | 6 | passed |

`134 passed, 1 warning in 88.24s`. `git push origin HEAD:refs/heads/main` — `062b975..47282dc  HEAD -> main`. Ветка `wave21-yu` от `47282dc`; первый коммит — `38986d3` (задание дословно, без строки `/caveman ultra`).

## 21-Ю, ШАГ 2. Runtime

`D:\Pets\_archive\ThermoGar.zip`, каталог `ThermoGar/ThermoGar-Installer-Assets/runtime-clean-3119/` — распакован Python `zipfile` во временную папку сессии (`…\scratchpad\rt\runtime-clean-3119`). Архив не менялся. Вывод — `results/wave21_yu/runtime_check.txt`:

* файлов на диске — 17 048;
* файлов `runtime/` в `payload-manifest.json` установленной 0.4.4 (`generated_utc 2026-09-23T11:10:09Z`, `file_count 15079`) — 15 003;
* все 15 003 найдены, sha256 равны — 15 003, **расхождений 0**, отсутствующих 0;
* лишние на диске — 2045, все `__pycache__/*.pyc` (как в 19-Д: 17 048 распаковано, 15 003 сверено). `stage_payload.ps1` каталоги `__pycache__` в нагрузку не берёт (`/XD __pycache__`). Отступление 1.

## 21-Ю, ШАГ 3. BL-78

Номера строк мастера сверены до правки — совпали: `batch_preview_dataframe` `:2296`, `batch_summary_display` `:2309`, `steel_mode_label` `:739`, `placeholder=EMPTY_CELL_TEXT` у таблицы предпросмотра — `:2845` (в `:2841–2846`).

Правка — `app/thermogar_workspace.py`, коммит `8db1d94`:

* `:2296` — новая `batch_preview_steel_mode(database, mode)`: `metastable` / `stable` у базы `fe` — `steel_mode_label(mode)`, у `ni` и `al` — `None` (на экране прочерк); другое значение — как есть;
* `:2305` — `batch_preview_dataframe`: подписи столбцов прежние (`BATCH_PREVIEW_LABELS`, символы элементов); затем `composition_columns_for_display` («Основа», «Добавки»), режим стали по строке через `batch_preview_steel_mode`, «База» — `RELEASE_DATABASE_LABELS`, «Единицы» — «ат.%» / «мас.%», как в `batch_summary_display` (`:2338`). Входная таблица не меняется: работа идёт на копии (`rename`, `composition_columns_for_display`).

Новых слов на экране нет: подписи баз, «ат.%» / «мас.%», подписи режима стали и прочерк уже есть в программе.

`tools/test_wave21_yu.py`, без AppTest: CSV с заголовками `TEMPLATE_HEADERS` → `_parse_csv` → `batch_table_dataframe`, пять строк задания; 7 тестов (подписи столбцов, база, основа, единицы, режим стали, добавки, неизменность входной таблицы).

* до правки — **5 failed, 2 passed** (прошли подписи столбцов и неизменность входной таблицы);
* после правки — **7 passed**.

Попутно: `tools/thermogar_verified_equilibrium_test.py` (читает «Режим стали») — 18 тестов, OK.

## 21-Ю, ШАГ 4. Кадры «Проектов» и HTML

`python -X utf8 tools/make_guide_screens.py --only proekty --no-html` — 8 кадров за 81 с, без сбоев (приложение — своя папка состояния скрипта `%TEMP%\thermogar_guide_state`).

Сличение с кадрами 21-Щ (`HEAD`) попиксельно:

| кадр | отличие от 21-Щ | что на кадре |
|---|---|---|
| proekty-01 | 6 пикселей (сглаживание) | сохранение состава «Опытный Ni–15Al»; в боковой панели Ni, «атомные %», «Al=15» |
| proekty-02 | нет, байт в байт | запись появилась в «Доступных записях» |
| proekty-03 | 188 пикселей (сглаживание) | выбор «Опытный Ni–15Al», подсвечена кнопка «Загрузить состав в программу» |
| proekty-04 | нет, байт в байт | шаблон CSV; кадр высотой 1100 px |
| proekty-05 | предпросмотр | «Предварительный просмотр»: «Никелевые сплавы — mc_ni 2.036», Ni, ат.%, в «Режиме стали» — прочерк, у трёх строк; «Загружено: Опытный Ni–15Al» |
| proekty-06 | предпросмотр | то же в предпросмотре; сводка — как у 21-Щ; «Загружено: Опытный Ni–15Al» |
| proekty-07 | нет, байт в байт | сохранение проекта; «Загружено: Опытный Ni–15Al» |
| proekty-08 | время «Изменён» | проект сохранён; время сохранения 2026-09-27T16:20:16+03:00 вместо 10:17:55; «Загружено: Опытный Ni–15Al» |

Во всех кадрах в боковой панели Ni, «атомные %», «Al=15». «Загружено: Опытный Ni–15Al» видно на proekty-05…08, на proekty-03 и proekty-04 — нет, как и у 21-Щ (отступление 3). Кроме предпросмотра и времени, расхождений с 21-Щ нет, поэтому полная пересъёмка не запускалась.

`_manifest.json`: после `--only` в нём 8 записей. Полный собран из `git show HEAD:docs/guide/img/_manifest.json`: 8 записей `proekty-*` заменены новыми по `image`, `generated_utc` — новый. Сверено: **56 записей**; у `proekty-*` `image` и `title` прежние; записи остальных 48 кадров равны прежним (как JSON). Итоговый файл байт в байт равен прежнему: `generated_utc` у 21-Щ уже `2026-09-27`, а заголовки кадров те же (отступление 4).

`python -X utf8 tools/make_guide_screens.py --html` → `docs/guide/ThermoGar_Guide_0.5.0.html`, 5,4 МБ: встроено **56 картинок**, набор sha256 = 56 кадрам `docs/guide/img/*.png`. В HTML изменились 5 строк — картинки proekty-01, 03, 05, 06, 08. `ThermoGar_Guide_0.4.*.html` не трогались. Коммит `560f0ee`.

## 21-Ю, ШАГ 5. Тексты выпуска

Дата выпуска — 2026-09-27. Коммит `bfe362c`.

* а) `CHANGELOG.md:3` — «## 0.5.0 — 2026-09-27»; после `:51` (пункт BL-77) — пункт BL-78, текст мастера.
* б) `HANDOFF.md:1` — «# HANDOFF — ThermoGar 0.5.0»; `:10` — «**Выпущено:** 0.5.0 от 2026-09-27; предыдущий выпуск 0.4.4 от 2026-09-23.»
* в) `packaging/ThermoGar.nsi:5–6` — «было» совпало дословно, заменено текстом мастера; остальное не менялось. `test_installer_shortcut_bl62.py` — 5 passed.
* г) `THIRD_PARTY_NOTICES.txt` — `packaging/generate_notices.ps1 -RepoRoot D:\Pets\ThermoGar-w21b -RuntimeSource <runtime ШАГА 2>`: 99 пакетов, 696 801 байт. `git diff` — одна строка: `-Generated: 2026-09-23` / `+Generated: 2026-09-27`.

`test_version_consistency.py` + `test_installer_shortcut_bl62.py` — 98 passed.

## 21-Ю, ШАГ 6. Реестр

Коммит `f047101`, тексты мастера дословно, проверка каждого «было» — скриптом:

* а) строка 21-Щ — «**принята мастером 27.09.2026 (ниже); влита в `main` (`ac5be77`).**», остальное в ячейке прежнее; строка 21-Э — ячейка состояния текстом мастера, хеш `47282dc`;
* б) после «Решения владельца, 26.09.2026 (краткое руководство). …» — абзацы «Приёмка 21-Щ мастером» и «Приёмка 21-Э мастером»;
* в) после «### Ошибка мастера (21-Ц)», перед «## Волна 22 …» — «### Ошибка мастера (21-Ж, предпросмотр пакета)»;
* г) BL-61, BL-62, BL-77 — закрыты текстами мастера; после BL-77 — строка BL-78.

## 21-Ю, ШАГ 7. Регрессия и сверка эталона

`D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe -B -X utf8 results\wave21_eh\scripts\run_regress.py`, 16:23:41–18:38:16. Раннер взял `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe`: своего `.venv-windows` в дереве нет, взят запустивший интерпретатор. Папка состояния — `results/validation/wave21_yu_state` (вне git).

* **77 заданий** = 41 `tools/test_*.py` + 19 `tools/thermogar_*_test.py` (not slow) + 9 slow + `test_ui_f -m slow` + 7 сценариев.
* Выход 0 — 67, выход 5 — 9, выход 1 — 1.
* `test_ui_f -m slow` — одним процессом (свободно 8,14 ГиБ ≥ 6,0): 21 passed, 38 deselected, 1260 с.
* Итог по строкам pytest: 1052 passed, 4 failed, 1 xfailed, 242 deselected. 7 сценариев — PASSED (`thermogar_self_test` — «RESULT: SOFTWARE REGRESSION PASSED — NOT MATERIAL QUALIFICATION»).
* Память: пик дерева процессов — 4,92 ГиБ, минимум свободной — 3,57 ГиБ, аварийных остановок нет.
* После регрессии `app\__pycache__` и `tools\__pycache__` нет.

Выход 5 (все тесты отобраны `-m` или их нет в файле):

```
notslow__test_liquidus_bisection.py        2 deselected in 0.14s
notslow__test_phase_presets_control.py     1 deselected in 2.35s
notslow__thermogar_converter_patch_test.py no tests ran in 0.04s
notslow__thermogar_diffusion_test.py       no tests ran in 0.61s
notslow__thermogar_fe_database_test.py     no tests ran in 2.30s
notslow__thermogar_physical_test.py        no tests ran in 0.03s
notslow__thermogar_precipitation_test.py   no tests ran in 0.04s
notslow__thermogar_properties_test.py      no tests ran in 0.13s
notslow__thermogar_self_test.py            no tests ran in 2.29s
```

Красное — `notslow__test_ui_h.py`, выход 1, «4 failed, 20 passed, 2 deselected in 355.48s (0:05:55)». Дословно из лога (`results/wave21_yu/regress_logs/notslow__test_ui_h.py.run1.log.txt`):

```
>       assert list(preview["База"]) == ["ni", "al", "fe"]
E       AssertionError: assert ['Никелевые с... mc_fe 2.062'] == ['ni', 'al', 'fe']
E         
E         At index 0 diff: 'Никелевые сплавы — mc_ni 2.036' != 'ni'
E         Use -v to get more diff

tools\test_ui_h.py:552: AssertionError
...
FAILED tools/test_ui_h.py::test_batch_accepts_both_separators_and_both_encodings[comma]
FAILED tools/test_ui_h.py::test_batch_accepts_both_separators_and_both_encodings[semicolon]
FAILED tools/test_ui_h.py::test_batch_accepts_both_separators_and_both_encodings[comma-bom]
FAILED tools/test_ui_h.py::test_batch_accepts_both_separators_and_both_encodings[semicolon-bom]
```

Сверка эталона: `python -B -X utf8 results\wave21_eh\scripts\backend_compare.py` → `results/wave21_yu/backend_compare.txt`:

```
[Кинетика] KWN (модуль) | fe: строк кинетики = 1123 (ожидается 1123, 22-Б)
ВЕРДИКТ: PASS
```

### СТОП, как доложен

> Остановился на ШАГЕ 7 (СТОП): после моей правки BL-78 упал старый тест test_ui_h.py, а этот файл менять нельзя.
>
> **Что упало.** В test_ui_h.py (не медленные тесты) 4 failed, 20 passed. Это `test_batch_accepts_both_separators_and_both_encodings`, все четыре варианта: запятая и точка с запятой, с BOM и без. Тест в `tools/test_ui_h.py:552–553` ждёт от предпросмотра внутренние обозначения:
> ```
> assert list(preview["База"]) == ["ni", "al", "fe"]
> assert list(preview["Единицы"]) == ["at", "wt", "wt"]
> ```
> После BL-78 там «Никелевые сплавы — mc_ni 2.036» и «ат.%» / «мас.%», как требует задание. Ошибка своя, но `tools/test_ui_h.py` нет в списке разрешённых файлов. Подгонять не стал.
>
> **Чем можно исправить (нужна ваша санкция).** Разрешить правку `tools/test_ui_h.py:552–553`:
> - «База» — `[RELEASE_DATABASE_LABELS[k] for k in ("ni", "al", "fe")]`;
> - «Единицы» — `["ат.%", "мас.%", "мас.%"]`;
> - комментарий над проверкой: «значения — как в сводке (BL-78)».
>
> После этого перепрогоню test_ui_h.py и продолжу с коммита ШАГА 7.
>
> **Остальная регрессия** (`results\wave21_yu\regress_summary.jsonl`):
> - 77 заданий = 41 + 19 + 9 медленных + test_ui_f slow + 7 сценариев: 67 зелёных, 9 выходов 5, 1 красный (test_ui_h).
> - Выходы 5 («no tests ran» или всё отобрано `-m`): test_liquidus_bisection, test_phase_presets_control и все 7 файлов thermogar_*_test (converter_patch, diffusion, fe_database, physical, precipitation, properties, self_test) в не медленном прогоне.
> - test_ui_f slow шёл одним процессом, свободно было 8,14 ГиБ. Пик — 4,92 ГиБ, минимум свободной памяти — 3,57 ГиБ, аварийных остановок нет.
> - Раннер взял `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe`, своего venv в дереве нет.
> - Сверка эталона `backend_compare.py`: «ВЕРДИКТ: PASS», разница только в ячейке «[Кинетика] KWN (модуль) | fe», строк кинетики 1123.
>
> **Сделано до остановки:**
> - **ШАГ 0.** Хеши origin верны, свободно 8,07 ГиБ, `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1`. Пять чужих `.pyc` перенесены в `_to_delete\21yu_pycache\` с описью.
> - **ШАГ 1.** Слияния чистые, деревья `34b3b0d` и `0c72908` совпали с моделью. Тесты 93 / 5 / 16 / 9 / 5 / 6 — 134 passed. `main` = `47282dc` запушен.
> - **ШАГ 2.** Все 15 003 файла runtime совпали по sha256, расхождений 0. Лишние 2045 файлов на диске — байткод `__pycache__`, как у 19-Д.
> - **ШАГ 3.** BL-78 сделан: до правки тест давал 5 failed, после — 7 passed.
> - **ШАГ 4.** Кадры сняты, `_manifest.json` — 56 записей, в HTML встроено 56 кадров = 56 на диске.
> - **ШАГ 5.** Тексты внесены; в NOTICES изменилась одна строка Generated.
> - **ШАГ 6.** Реестр внесён.
>
> **Отступление по кадрам.** Задание говорит, что «Загружено: Опытный Ni–15Al» видно начиная с proekty-03. На деле надпись видна на 05–08. Кадр 03 снят до нажатия «Загрузить», кадр 04 обрезан по высоте 1100 px. У 21-Щ так же: мой 03 отличается от кадра 21-Щ лишь 188 пикселями сглаживания. Поэтому все 9 сценариев не переснимал.
>
> Ветка `wave21-yu` (`f047101`) не запушена. `results\wave21_yu\` ещё не закоммичен, остальное дерево чистое.

## 21-Ю2

### ШАГ 0

`git branch --show-current` — `wave21-yu`. `git status --short`:

```
?? _to_delete/
?? results/wave21_yu/
```

`git log --oneline 47282dc..HEAD`:

```
f047101 docs(21-Ю): реестр — приёмки 21-Щ и 21-Э, ошибка мастера (21-Ж, предпросмотр пакета), BL-61, BL-62, BL-77, BL-78
bfe362c docs(21-Ю): тексты выпуска 0.5.0 — CHANGELOG (дата, BL-78), HANDOFF, комментарий установщика, NOTICES
560f0ee docs(21-Ю): пересъёмка кадров «Проектов» (proekty-01…08), HTML 0.5.0
8db1d94 fix(21-Ю): BL-78 — предпросмотр пакета теми же словами, что сводка и боковая панель
38986d3 docs(21-Ю): задание WAVE21_YU_OPUS.md
```

Задание без строки `/caveman ultra` — `tasks/WAVE21_YU2_OPUS.md`, коммит `5db7ceb`.

### ШАГ 1

Выходы ШАГА 7 21-Ю как есть — коммит `75c6314` «test(21-Ю): регрессия — 77 заданий, 1 красное (test_ui_h, ожидания до BL-78); сверка эталона PASS»: 144 файла (`regress_logs/` 77, `regress_memlog/` 61, `regress_backend/` 2, `regress_summary.jsonl`, `backend_compare.txt`, `runtime_check.txt`, `regress_start.txt`).

### ШАГ 2. Правка теста

Строки до правки сверены — совпали: блок импорта из `thermogar_workspace` `:33–40`, комментарий `:544`, проверки `:552`, `:553`. Коммит `81199d6`, дифф:

```
+from thermogar_release_policy import RELEASE_DATABASE_LABELS  # noqa: E402
+    # BL-78 (21-Ю): база и единицы — подписями сводки.
-    assert list(preview["База"]) == ["ni", "al", "fe"]
-    assert list(preview["Единицы"]) == ["at", "wt", "wt"]
+    assert list(preview["База"]) == [RELEASE_DATABASE_LABELS[key] for key in ("ni", "al", "fe")]
+    assert list(preview["Единицы"]) == ["ат.%", "мас.%", "мас.%"]
```

### ШАГ 3. Повтор задания регрессии

Прежний лог скопирован (`cp -p`, копия побайтно равна): `results/wave21_yu/regress_logs/notslow__test_ui_h.py.run1.log.txt`. Затем `run_regress.py notslow__test_ui_h.py`, свободно 8,03 ГиБ; раннер дописал запись в `regress_summary.jsonl` (78-я строка):

```
{"job": "notslow__test_ui_h.py", ..., "free_at_start_gib": 8.03, "waited_s": 0, "memlog": "notslow__test_ui_h.py.memlog.jsonl", "exit": 0, "last_line": "24 passed, 2 deselected in 357.44s (0:05:57)", "seconds": 359.9, "peak_tree_gib": 0.49, "min_free_gib": 7.58, "aborted_low_memory": false}
```

Выход 0, «24 passed, 2 deselected» — сошлось. Коммит `247928a`.

С повтором регрессия 21-Ю — 77 заданий, 0 красных: 68 с выходом 0, 9 с выходом 5.

### ШАГ 4. Реестр

Коммит `a5e8399`, тексты мастера дословно:

* а) после «Приёмка 21-Э мастером (27.09.2026). …» — абзац «Решение владельца, 27.09.2026 (загрузчики файлов). …»;
* б) после раздела «### Ошибка мастера (21-Ж, предпросмотр пакета)», перед «## Волна 22 …» — «### Ошибка мастера (21-Ю, тест предпросмотра)»;
* в) после строки BL-78 — строка BL-79.

## Отступления

1. **Runtime: 17 048 файлов, а не 15 003.** Первая сверка считала лишние файлы расхождением и дала `FAIL`. Лишние 2045 — все `__pycache__/*.pyc`, в манифесте их нет, в нагрузку их не берёт `stage_payload.ps1`. Сверка переписана: все 15 003 файла манифеста есть и равны по sha256, отсутствующих 0, лишние — отдельной строкой. Так же в 19-Д.
2. **Моя ошибка: путь вывода runtime.** Путь `results\\wave21_yu\\runtime_check.txt` в Git Bash дошёл до Python как `resultswave21_yuruntime_check.txt` в корне дерева. Файл перенесён (`mv`) в `results/wave21_yu/runtime_check.txt`; вторая запись перезаписала первую, итог — сверка из п. 1. Ничего не удалялось.
3. **«Загружено: Опытный Ni–15Al» — не «с proekty-03».** Надпись видна на proekty-05…08. proekty-03 снят до нажатия «Загрузить состав в программу» (кнопка подсвечена как следующий шаг); proekty-04 обрезан по высоте 1100 px, низа боковой панели на нём нет. Кадры 21-Щ такие же: proekty-03 отличается на 188 пикселей сглаживания, proekty-04 — байт в байт. Расхождения с 21-Щ сверх предпросмотра нет, поэтому полная пересъёмка не запускалась.
4. **`_manifest.json` в коммит ШАГА 4 не вошёл.** Собранный файл байт в байт равен прежнему: `generated_utc` у 21-Щ — тоже `2026-09-27`, заголовки кадров прежние. Все сверки ШАГА 4 по нему выполнены.
5. **ШАГ 5 шёл во время съёмки ШАГА 4.** Правки `CHANGELOG.md`, `HANDOFF.md`, `packaging/ThermoGar.nsi` и `THIRD_PARTY_NOTICES.txt` не касаются приложения; в коммиты они вошли по порядку шагов (`560f0ee` — кадры, `bfe362c` — тексты).
6. **Файл `results/wave21_yu/regress_start.txt`** — время начала регрессии, записан мною. Остальные файлы `results/wave21_yu/` пишут раннер и сценарии.
7. **Сверка эталона снята до доклада СТОПа.** Она только пишет `results/wave21_yu/backend_compare.txt`, и мастеру нужен полный итог ШАГА 7. Коммит — в ШАГЕ 1 21-Ю2.
8. **Мой зависший процесс.** При докладе статуса я запустил проверку с лишним `python -`: оболочка вызвала `WindowsApps\python.exe -` (и дочерний `pythoncore-3.11-64\python.exe -`). Оба ждали stdin с 17:49:57, на регрессию не влияли (8–13 МБ). Сняты `Stop-Process` в 19:47, после этого процессов `python.exe` нет.
9. **Интерпретатор тестов ШАГА 1** — `D:\Pets\ThermoGar\.venv-windows`, `THERMOGAR_STATE_ROOT` — временная папка сессии. Съёмка ШАГА 4 задаёт своё состояние сама (`%TEMP%\thermogar_guide_state`), как в 21-Щ.
10. **`tasks/WAVE21_YU_OPUS.md` и `tasks/WAVE21_YU2_OPUS.md`** — задания от второй строки до конца, строка `/caveman ultra` — команда сессии.

## Git

Перед коммитом этого отчёта `git log --oneline 47282dc..wave21-yu`:

```
a5e8399 docs(21-Ю2): реестр — решение владельца по загрузчикам файлов, ошибка мастера (21-Ю, тест предпросмотра), BL-79
247928a test(21-Ю2): повтор задания регрессии notslow__test_ui_h.py — 24 passed, 2 deselected
81199d6 test(21-Ю2): test_ui_h — ожидания предпросмотра пакета под BL-78
75c6314 test(21-Ю): регрессия — 77 заданий, 1 красное (test_ui_h, ожидания до BL-78); сверка эталона PASS
5db7ceb docs(21-Ю2): задание WAVE21_YU2_OPUS.md
f047101 docs(21-Ю): реестр — приёмки 21-Щ и 21-Э, ошибка мастера (21-Ж, предпросмотр пакета), BL-61, BL-62, BL-77, BL-78
bfe362c docs(21-Ю): тексты выпуска 0.5.0 — CHANGELOG (дата, BL-78), HANDOFF, комментарий установщика, NOTICES
560f0ee docs(21-Ю): пересъёмка кадров «Проектов» (proekty-01…08), HTML 0.5.0
8db1d94 fix(21-Ю): BL-78 — предпросмотр пакета теми же словами, что сводка и боковая панель
38986d3 docs(21-Ю): задание WAVE21_YU_OPUS.md
```

Вывод после пуша — следующим коммитом.

### После пуша (19:49)

`git push -u origin wave21-yu` — `* [new branch]      wave21-yu -> wave21-yu`.

`git ls-remote origin main wave21-yu`, дословно:

```
47282dcb2dc8f213be361769c4ed8691f989c0a0	refs/heads/main
a78aa104da403ab14551dda8beaa7b75a48d5379	refs/heads/wave21-yu
```

`main` = `47282dcb2dc8f213be361769c4ed8691f989c0a0` — сошлось.

`git log --oneline 47282dc..wave21-yu`, дословно:

```
a78aa10 docs(21-Ю): отчёт 21-Ю (ШАГИ 0–7, СТОП) и 21-Ю2
a5e8399 docs(21-Ю2): реестр — решение владельца по загрузчикам файлов, ошибка мастера (21-Ю, тест предпросмотра), BL-79
247928a test(21-Ю2): повтор задания регрессии notslow__test_ui_h.py — 24 passed, 2 deselected
81199d6 test(21-Ю2): test_ui_h — ожидания предпросмотра пакета под BL-78
75c6314 test(21-Ю): регрессия — 77 заданий, 1 красное (test_ui_h, ожидания до BL-78); сверка эталона PASS
5db7ceb docs(21-Ю2): задание WAVE21_YU2_OPUS.md
f047101 docs(21-Ю): реестр — приёмки 21-Щ и 21-Э, ошибка мастера (21-Ж, предпросмотр пакета), BL-61, BL-62, BL-77, BL-78
bfe362c docs(21-Ю): тексты выпуска 0.5.0 — CHANGELOG (дата, BL-78), HANDOFF, комментарий установщика, NOTICES
560f0ee docs(21-Ю): пересъёмка кадров «Проектов» (proekty-01…08), HTML 0.5.0
8db1d94 fix(21-Ю): BL-78 — предпросмотр пакета теми же словами, что сводка и боковая панель
38986d3 docs(21-Ю): задание WAVE21_YU_OPUS.md
```

`git status --short`, дословно:

```
?? _to_delete/
```

Дальше задание 21-Ю2 не идёт: слияние, тег, установщик, установка и приёмка — после BL-79.

## 21-Ю3

**Итог.** Выпуск 0.5.0 сделан, все сверки сошлись, СТОПов нет. Слияние 21-Я — `a61b68f`, дерево `902a6d4`, 262 passed. Регрессия — 78 заданий: 69 выход 0, 9 выход 5, красных нет. Сверка эталона — PASS. `main` — `077e732`, тег `v0.5.0`, дата выпуска 2026-09-28. Установщик — 118 535 338 байт, sha256 `3cd28483…c3b3`. Установка поверх 0.4.4: 15 080 файлов, расхождений 0. Приёмка (а)–(з) — 8 из 8, «равных: 6 из 6».

Дерево — `D:\Pets\ThermoGar-w21b`. Интерпретатор дерева — `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe`. Все прогоны — с `PYTHONHASHSEED=0`, `MPLBACKEND=Agg`, `PYTHONDONTWRITEBYTECODE=1`, у pytest — `-B`. `THERMOGAR_STATE_ROOT` — во временной папке сессии; раннер ставит свою папку.

### Время по шагам (местное)

| шаг | начало | конец |
|---|---|---|
| 0 | 27.09 22:20:23 | 22:20:45 |
| 1 | 22:20:48 | 22:22:04 |
| 2 | 22:22:10 | 22:22:52 |
| 3 | 22:22:58 | 22:23:26 |
| 4 | 22:23:26 | 22:24:20 |
| 5 | 22:24:28 | 22:27:31 |
| 6 (регрессия) | 22:28:02 | 28.09 00:40:39 |
| 6 (сверка эталона, коммит, пуш) | 00:41:16 | 00:41:33 |
| 7 | 00:41:39 | 00:42:16 |
| 8 | 00:42:23 | 00:49:30 |
| 9 (до установки — во время сборки ШАГА 8) | 00:45 | 00:46 |
| 9 (установка, ждала UAC) | 00:49:42 | 08:59:46 |
| 9 (сверка после) | 09:00 | 09:02:18 |
| 10 | 09:02:32 | 09:06:11 |
| 11 | 09:06:11 | см. «Git» |

### ШАГ 0

* `git branch --show-current` — `wave21-yu`. `git status --short` — `?? _to_delete/`.
* `git fetch origin` — без обрыва. `git ls-remote origin main wave21-yu wave21-ya`:

```
47282dcb2dc8f213be361769c4ed8691f989c0a0	refs/heads/main
8fa98766da624b210b1b9076c70887380fd2f5f1	refs/heads/wave21-ya
9db6412a43cb714dad39614d3060d5ba1345ec4b	refs/heads/wave21-yu
```

* `git rev-parse HEAD` — `9db6412a43cb714dad39614d3060d5ba1345ec4b`.
* Свободная память — 7,91 ГиБ. `$env:CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP` = `1`.
* Папок `app\__pycache__` и `tools\__pycache__` нет, переносить было нечего. Папка `_to_delete\21yu3_pycache\` не создавалась.

### ШАГ 1. Слияние 21-Я

`git merge --no-ff origin/wave21-ya` прошёл чисто, без конфликтов: коммит `a61b68f104a211e4effcb158310078e87b24bc14`, дерево `902a6d49b74d185bc9ec97ba4c252d219e411b0f` = модель мастера. В слиянии 105 файлов, 7410 вставок.

| файл | ожидание | собрано |
|---|---|---|
| `test_wave21_ya.py` | 31 | 31 |
| `test_wave21_yu.py` | 7 | 7 |
| `test_style_21z.py` | 11 | 11 |
| `test_version_consistency.py` | 93 | 93 |
| `test_user_errors_21zh.py` | 47 | 47 |
| `test_chart_theme_21e.py` | 73 | 73 |

Все шесть файлов — одним прогоном: `262 passed in 28.49s`. Задание без первой строки, байт в байт, — `tasks/WAVE21_YU3_OPUS.md`, коммит `a42ca20`.

### ШАГ 2. Runtime и Streamlit

Взят каталог ШАГА 2 21-Ю: `…\2f65e74c-…\scratchpad\rt\runtime-clean-3119`. Он на месте, заново не распаковывался. Вывод — `results/wave21_yu/runtime_check_2.txt`:

* в `payload-manifest.json` установленной 0.4.4 файлов `runtime/` — 15 003. На диске все 15 003, sha256 равны у 15 003. Расхождений 0, отсутствующих 0;
* сверх манифеста на диске 2045 файлов, все — `__pycache__/*.pyc`, как у 21-Ю. Всего на диске 17 048 файлов, после проверки — столько же;
* `python.exe -B -c "import streamlit; print(streamlit.__version__)"` — `1.62.0`;
* шесть файлов `streamlit\static\static\js` runtime по sha256 равны тем же файлам `.venv-windows`, начала sha256 совпали с замером мастера: `FileUploader.2io2eK1d.js` 817d426034f9…, `utils.CZ73KiS-.js` 8232642e6b5d…, `Tooltip.CcubhKj6.js` 9e90fde41b3f…, `NumberInput.MwtTRR2O.js` 9869802d22b0…, `Multiselect.DafPXziM.js` 623c04561afb…, `Selectbox.DTwsqAB2.js` e52ba8811980…;
* `VERDICT: PASS`.

### ШАГ 3. Тексты

Коммит `9559296`. `CHANGELOG.md:52` — пункт BL-78 на месте, после него (`:53`) — пункт BL-79. `HANDOFF.md:278` — строка «Ожидаемые числа и времена — …» на месте, после неё пустая строка и строка о `tools\test_wave21_ya.py`. Строки вставлены скриптом из файла задания и сверены с ним — равны.

### ШАГ 4. Реестр

Коммит `4955e3f`. Тексты взяты скриптом из `tasks/WAVE21_YU3_OPUS.md`, каждое место и каждое «было» проверено до правки:

* а) после строки 21-Э — строки 21-Ю, 21-Ю2, 21-Я. В строке 21-Я `<7 знаков коммита слияния ШАГА 1>` заменён на `a61b68f`;
* б) после абзаца «Решение владельца, 27.09.2026 (загрузчики файлов). …» — три абзаца: решения владельца (BL-79), приёмка 21-Ю2, приёмка 21-Я;
* в) в абзаце «Приёмка 21-Щ мастером» заменено одно место: `proekty-03…08` → `proekty-05…08` с поправкой. Остальное в абзаце не менялось;
* г) после «### Ошибка мастера (21-Ю, тест предпросмотра)», перед «## Волна 22 …», — разделы «(приёмка 21-Щ, кадры)» и «(BL-79, решение 24.09)»;
* д) BL-79 — ячейка состояния заменена текстом мастера.

### ШАГ 5. Кадры «Проектов» и HTML

`make_guide_screens.py --only proekty --no-html` — 8 кадров за 76 с, без сбоев. Все 8 кадров я посмотрел:

| кадр | что на кадре |
|---|---|
| proekty-01 | сохранение «Опытный Ni–15Al»; у «Импортировать библиотеку JSON» — «Выбрать файл» и «JSON, до 64 МБ» |
| proekty-02 | запись в «Доступных записях»; загрузчик — «Выбрать файл», «JSON, до 64 МБ» |
| proekty-03 | выбран «Опытный Ni–15Al», подсвечена «Загрузить состав в программу»; загрузчик — «Выбрать файл», «JSON, до 64 МБ» |
| proekty-04 | «Файл составов» — «Выбрать файл» и «CSV или XLSX, до 64 МБ»; кадр высотой 1100 px |
| proekty-05 | карточка `guide_batch.csv` без размера; «Предварительный просмотр» — «Никелевые сплавы — mc_ni 2.036», Ni, ат.%, в «Режиме стали» прочерк |
| proekty-06 | то же, плюс «Все составы рассчитаны: 3.» и сводка |
| proekty-07 | «Импортировать проект» — «Выбрать файл» и «JSON, до 64 МБ» |
| proekty-08 | проект сохранён, время 2026-09-27T22:25:42+03:00; загрузчик — «Выбрать файл», «JSON, до 64 МБ» |

Во всех кадрах в боковой панели Ni, «атомные %», «Al=15». «Загружено: Опытный Ni–15Al» видно на proekty-05…08. Английских надписей Streamlit («Upload», «200MB per file», размер вида «288.0B») нет. Попиксельно с кадрами 21-Ю: содержание изменилось только в загрузчиках (кнопка, строка, карточка файла без размера) и во времени на proekty-08. Остальное — слабое сглаживание текста по всей странице, до 85 из 765 по сумме каналов, не содержание (отступление 2). Расхождений сверх ожидания нет, поэтому полная пересъёмка не запускалась.

`_manifest.json` собран из `git show HEAD:…`: 8 записей `proekty-*` заменены новыми. Сверено: **56 записей**, у `proekty-*` `image` и `title` прежние, остальные 48 записей равны прежним (как JSON). `generated_utc` — `2026-09-27`, как и прежний, поэтому файл байт в байт равен прежнему и в коммит не вошёл (как у 21-Ю, отступление 4).

`make_guide_screens.py --html` → `docs/guide/ThermoGar_Guide_0.5.0.html`, 5 401 472 байта. Встроено **56 картинок**, их набор sha256 равен 56 кадрам `docs/guide/img/*.png`. В HTML изменились 8 строк (картинки proekty-01…08). `ThermoGar_Guide_0.4.*.html` не менялись. Коммит `5610dc9`.

### ШАГ 6. Регрессия и сверка эталона

`run_regress.py` работал 22:28:02–00:40:39 (сумма заданий — 7956 с). Раннер взял `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe`: своего `.venv-windows` в дереве нет, поэтому взят запустивший интерпретатор.

* **78 заданий** = 42 `tools/test_*.py` + 19 `tools/thermogar_*_test.py` (not slow) + 9 slow + `test_ui_f -m slow` + 7 сценариев.
* Выход 0 — **69**, выход 5 — **9**, красных нет.
* По строкам pytest: 1087 passed, 1 xfailed, 242 deselected. 7 сценариев — PASSED, у `thermogar_self_test` — «RESULT: SOFTWARE REGRESSION PASSED — NOT MATERIAL QUALIFICATION».
* `test_ui_f -m slow` шёл одним процессом (свободно 7,90 ≥ 6,0 ГиБ): 21 passed, 38 deselected, 1251 с.
* Память: пик дерева процессов — 4,84 ГиБ, минимум свободной — 3,36 ГиБ. Аварийных остановок нет.
* После регрессии папок `app\__pycache__` и `tools\__pycache__` нет.

Выход 5 — тот же список, что у 21-Ю:

```
notslow__test_liquidus_bisection.py        2 deselected in 0.14s
notslow__test_phase_presets_control.py     1 deselected in 2.35s
notslow__thermogar_converter_patch_test.py no tests ran in 0.06s
notslow__thermogar_diffusion_test.py       no tests ran in 0.61s
notslow__thermogar_fe_database_test.py     no tests ran in 2.30s
notslow__thermogar_physical_test.py        no tests ran in 0.04s
notslow__thermogar_precipitation_test.py   no tests ran in 0.05s
notslow__thermogar_properties_test.py      no tests ran in 0.16s
notslow__thermogar_self_test.py            no tests ran in 2.31s
```

Раннер переписал логи и memlog 21-Ю. `regress_summary.jsonl` он дописывает: строки 1–78 — прежние (21-Ю и повтор 21-Ю2), строки 79–156 — этот прогон. Лог `notslow__test_ui_h.py.run1.log.txt` (21-Ю) остался, как был.

Сверка эталона: `backend_compare.py` → `results/wave21_yu/backend_compare.txt`. Ячеек 57 и 57, разница в одной:

```
РАЗНИЦА [Кинетика] KWN (модуль) | fe
  - строк кинетики = 2391
  + строк кинетики = 1123

[Кинетика] KWN (модуль) | fe: строк кинетики = 1123 (ожидается 1123, 22-Б)
ВЕРДИКТ: PASS
```

Коммит `aaf4594`, `git push origin wave21-yu` — `9db6412..aaf4594`.

### ШАГ 7. Дата, слияние, тег

Местная дата — 2026-09-28, не 2026-09-27. Коммит `22fada9` на `wave21-yu`: `CHANGELOG.md:3` — «## 0.5.0 — 2026-09-28», `HANDOFF.md:10` — «0.5.0 от 2026-09-28». Пуш `aaf4594..22fada9`.

`git ls-remote origin main` — `47282dcb2dc8f213be361769c4ed8691f989c0a0`. От `origin/main`: `git merge --no-ff wave21-yu -m "Merge wave21-yu: release 0.5.0"` — коммит `077e7323931fbf9a60c52a64c405a24f6c935185`, дерево `8a93af55e47d215761f98b7093e1c662f8c7e827` = дерево `wave21-yu`.

`git diff --stat 47282dc HEAD -- databases` — пусто.

`git diff --stat v0.4.4 HEAD -- databases`:

```
 databases/physical/overrides/physical_data_v103.overrides.json | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
```

`git tag -a v0.5.0 -m "ThermoGar 0.5.0 — 2026-09-28"`. Пуш: `47282dc..077e732  HEAD -> main`, `* [new tag]         v0.5.0 -> v0.5.0`. `git ls-remote origin refs/heads/main "refs/tags/v0.5.0*"`:

```
077e7323931fbf9a60c52a64c405a24f6c935185	refs/heads/main
eb9bd45eea552c8cbe7e0e8972a02e145e1062db	refs/tags/v0.5.0
077e7323931fbf9a60c52a64c405a24f6c935185	refs/tags/v0.5.0^{}
```

### ШАГ 8. Установщик

Снимок: `git -c core.autocrlf=false archive --format=tar v0.5.0 --` плюс пути нагрузки `stage_payload.ps1` и `packaging`, распакован во временную папку сессии (`…\scratchpad\snap050`). **83 файла**, все 83 байт в байт равны блобам `v0.5.0`, набор файлов = `git ls-tree`.

Сборка: `packaging\build_installer.ps1 -RepoRoot <снимок> -RuntimeSource <runtime ШАГА 2> -OutputDir D:\Pets\ThermoGar-w21b\dist\release-0.5.0`, makensis — `C:\Program Files (x86)\NSIS\makensis.exe` (v3.12). Шла 392,4 с. Лог — `results/wave21_yu/build.log`.

* «project files staged: 78»; staged 15 080 файлов, 554,4 МБ.
* `ThermoGar-0.5.0-win64.exe` — **118 535 338 байт**, sha256 `3cd28483cccffa4f309f052c1a49eb3aeef652e899686ad089d0a6c84f6bc3b3`.
* ProductVersion — `0.5.0`, FileVersion — `0.5.0` (vi 0.5.0.0).
* `THIRD_PARTY_NOTICES.txt` снимка после сборки байт в байт равен блобу `v0.5.0` (696 801 байт). Сборка шла в те же сутки UTC (`built_utc 2026-09-27T21:42:39Z`), поэтому строка Generated не изменилась.

### ШАГ 9. Установка поверх 0.4.4

До установки (`results/wave21_yu/installed_044_before.txt`):

* DisplayVersion — `0.4.4`;
* `Uninstall.exe` — `60ca53dc18970a09f099c426b2e19921e71686fbad3c8d19ab8fbaca4f6fd94c`;
* `runtime\python.exe` — `5f7b89a612c9b8af1d6456cdfcd1dbe5ca630849e79aebced9bee9a6694952ec`;
* `app\ThermoGar_app.py` — `1231073340c9…`, равен блобу `v0.4.4`.

Запущенной ThermoGar не было. Владельцу написано «Сейчас будет запрос UAC — подтвердите». `ThermoGar-0.5.0-win64.exe /S` запущен в 00:49:42, запрос UAC был один. Владелец подтвердил его утром, установка закончилась в 08:59:46 с выходом 0 (отступление 4).

После установки (`results/wave21_yu/installed_050_check.txt`):

* DisplayVersion — `0.5.0`;
* `payload-manifest.json` (`generated_utc 2026-09-27T21:45:03Z`) — **15 080** записей = 15 003 в `runtime/` + 77. По sha256 равны все 15 080, расхождений 0;
* 77 файлов вне `runtime/` байт в байт равны блобам `v0.5.0`, включая `THIRD_PARTY_NOTICES.txt` (без отличий в Generated);
* `runtime\python.exe` — прежний, `5f7b89a6…`;
* `app\ThermoGar_app.py` — `c90d33d875dd7160cabbf1a7ef2ef9dead6c4ce5e48bb2a91bcb4299dc5eca21`, равен блобу `v0.5.0`;
* `Uninstall.exe` — `109fd6619197c4e24e30cd3531ecdd26d50ea87fa792804f56707e88d1c10e7b`.

### ШАГ 10. Приёмка на установленной программе

Интерпретатор — `"C:\Program Files\ThermoGar\runtime\python.exe" -B -X utf8`, файлы app — установленные. Выходы — `results/wave21_yu/priemka/`.

| проверка | ожидание | получено | итог |
|---|---|---|---|
| (а) version | подпись «ThermoGar 0.5.0 — исследовательское ПО. Экспериментальная квалификация не проводилась.», APP_VERSION 0.5.0 | та же подпись; `app_version` 0.5.0 | сошлось |
| (б) batch | в runner 3 строки; CSV = блобы `1g_batch_Fe-*`; четвёртая строка — «ошибка» с текстом мастера | 3 строки, CSV `57dc1b94…`, `57dc1b94…`, `bd7984c2…`; «Fe-metastabe» — «ошибка», «Неизвестный режим стали: «metastabe». Используйте «стабильный» или «метастабильный».» | сошлось |
| (в) phase_reference | CSV = блобы `spravochnik_faz`, 99 / 195 / 132 строки | 99 / 195 / 132, sha256 равны | сошлось |
| (г) density | RS320, 25 °C — 2663,72 кг/м³ | 2663,716… → 2663,72, ошибок нет | сошлось |
| (д) quick_start | первое упоминание версии — 0.5.0 | «# ThermoGar 0.5.0 — быстрый старт», 0.5.0 | сошлось |
| (е) pool | «Параллельный расчёт: …» без отказа и «Последовательный расчёт.»; таблицы и CSV равны | «Параллельный расчёт: по 4 точки одновременно.» (31,1 с) и «Последовательный расчёт.» (25,8 с); 5 строк, ячейки и CSV по sha256 равны | сошлось |
| побайтовая сверка (б), (в) | «равных: 6 из 6» | `priemka_compare.py v0.5.0` — «равных: 6 из 6» | сошлось |
| (ж) ярлыки | оба есть; TargetPath, Arguments, IconLocation, Description одинаковые | оба есть; `C:\Program Files\ThermoGar\runtime\pythonw.exe`, `"C:\Program Files\ThermoGar\launcher.pyw"`, `C:\Program Files\ThermoGar\ThermoGar.ico,0`, «ThermoGar Research Desktop» у обоих | сошлось |
| (з) BL-79 | в `config.toml` есть `[server]` и `maxUploadSize = 64`; Streamlit 1.62.0; шесть JS = ШАГ 2 | обе строки есть; `1.62.0`; шесть файлов есть, sha256 = ШАГ 2 | сошлось |

Ярлыки прочитаны через `WScript.Shell.CreateShortcut` без `Save`, вывод — `priemka/shortcuts.txt`. BL-79 — `priemka/bl79.txt`. После приёмки папки `C:\Program Files\ThermoGar\app\__pycache__` нет.

### ШАГ 11

На `main` после тега, тег остаётся на `077e732`. В `tasks/REGISTER.md` после строки 21-Ю2 — строка 21-Ю3, итог числами заполнен. После таблицы волны 21, перед «Решения владельца по дизайну. 24.09.2026: …», — абзац «Выпуск 0.5.0 — 2026-09-28, тег `v0.5.0`»: полный хеш `077e7323931fbf9a60c52a64c405a24f6c935185`, sha256 заглавными, как у выпуска 0.4.4.

### Отступления

1. **Runtime заново не распаковывался.** Каталог ШАГА 2 21-Ю был на месте, задание разрешает его взять. Сверка — `runtime_check_2.txt`, PASS.
2. **Кадры отличаются от кадров 21-Ю сглаживанием текста по всей странице.** Отличия — до 85 из 765 по сумме каналов, по контурам букв, у всех 8 кадров. Содержание изменилось только в загрузчиках BL-79 и во времени proekty-08. Считаю это отличием отрисовки шрифта при съёмке, не расхождением по содержанию, поэтому полной пересъёмки не было.
3. **`results/wave21_yu/build.log` добавлен в git через `git add -f`.** `.gitignore:9` (`*.log`) его исключает, а задание велит положить лог туда. `.gitignore` не менялся. `build_installer.ps1` запущен из дерева на `077e732` (дерево = `v0.5.0`), `-RepoRoot` — снимок.
4. **Запрос UAC ждал подтверждения ночью, с 00:49 до утра.** Установщик ждал сам, я ничего не закрывал и не перезапускал. Владелец подтвердил, установка закончилась в 08:59:46 с выходом 0.
5. **Интерпретатор тестов ШАГА 1 и съёмки** — `D:\Pets\ThermoGar\.venv-windows`. Pytest шёл с `-p no:cacheprovider`, как у раннера. Съёмка ставит своё состояние сама.
6. **`tasks/WAVE21_YU3_OPUS.md`** — задание со второй строки до конца, байт в байт. Строка `/caveman ultra` — команда сессии.
7. **Ничего не удалялось.** Пробные файлы, снимок, состояние приложения и прежние кадры для сличения лежат во временной папке сессии, вне дерева. `dist/release-0.5.0/` (в `.gitignore`) — только вывод сборки.

### Git

Перед коммитом отчёта `git log --oneline --first-parent 062b975..HEAD`, `git status --short` и `git ls-remote` — в следующем подразделе, после пуша.
