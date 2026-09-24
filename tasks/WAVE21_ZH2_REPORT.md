# Отчёт 21-Ж2: доводка 21-Ж по приёмке мастера

Исполнитель — сессия Claude Code, 24.09.2026, ноутбук Windows 10, дерево `D:\Pets\ThermoGar-w21a`, ветка `wave21-zh` (продолжение от `02a5967`). Задание — `tasks/WAVE21_ZH2_OPUS.md` (коммит `cb6db40`).
Лёгкий поток: приложение не запускалось (ни streamlit, ни AppTest), равновесия не считались. `D:\Pets\ThermoGar`, `D:\Pets\ThermoGar-w21b`, `D:\Pets\Lilith`, `%LOCALAPPDATA%\ThermoGar` не открывались. `configs\`, `packaging\`, `docs\`, `.streamlit\`, `tasks\REGISTER.md` не менялись; в `databases\` — одно поле одного файла, `.tdb` и `.pdb` не тронуты. Не свои места 21-Е не менялись.

## ШАГ 0

`git status --short` — `?? _to_delete/`; `git fetch origin`; `git ls-remote origin wave21-zh` — `02a596790093e5971c044c1543c16e54be483c07`; ветка `wave21-zh` на этом коммите. Задание записано дословно (без строки `/caveman ultra` — команда сессии).

## ШАГ 1. Строка 2 части 1 (А2б) — поправка плотности хрома

- Закреплён ли sha256 файла: sha256 `databases/physical/overrides/physical_data_v103.overrides.json` до правки — `d6f4d7f83f3383c703dad6a14b75aa8b8e246762233dabac0ac2dc4467cb1982`; поиск этого значения по `app\`, `tools\`, `configs\`, `packaging\` — совпадений нет. Файл читается по пути (`app/thermogar_physical.py:48`), `target_sha256` внутри файла — это SHA-256 самой `.pdb`, не файла поправок. Не закреплён — продолжено.
- Поле `user_message` поправки хрома (строка 63) заменено на «предлагается» строки 2 дословно (из `git show 152a4b0…:tasks/NA_UTVERZHDENIE_21.md`). Кодировка UTF-8 без BOM, отступы, порядок ключей, концы строк LF — прежние; JSON разбирается. `git diff` файла — одна строка:

```
diff --git a/databases/physical/overrides/physical_data_v103.overrides.json b/databases/physical/overrides/physical_data_v103.overrides.json
index 20bcfa4..d5478ec 100644
--- a/databases/physical/overrides/physical_data_v103.overrides.json
+++ b/databases/physical/overrides/physical_data_v103.overrides.json
@@ -60,7 +60,7 @@
       "source_queue": "tasks/SOURCES_WANTED.md, позиция S-1 — закрыта, мастер достал оба источника",
       "date": "2026-09-11",
       "wave": "11M-2 (BL-9), механизм — 11K-2",
-      "user_message": "Плотность хрома посчитана по поправке проекта ThermoGar, а не по данным physical_data_v103.pdb: тепловая функция DTCRBCC заменена. Это не наша оценка величины, а восстановление источника — статья REF 14 самой базы (Lu, Selleby, Sundman, Calphad 29 (2005) 68-89, doi:10.1016/j.calphad.2005.05.001) даёт правильные коэффициенты, сломан их перенос в базу: активный полином завышает тепловое расширение хрома в 2,5-3 раза против измерений (Hidnert, NBS RP1407, 1941). Опорная плотность при 25 °C не изменена. Чтобы считать по чистой базе, запустите программу с переменной окружения THERMOGAR_PHYSICAL_OVERRIDES=off — тогда ни одна наша правка не применяется. Подробности: docs/DATABASES.md, раздел «Поправки проекта к физической базе».",
+      "user_message": "Плотность хрома посчитана по поправке проекта ThermoGar. Коэффициенты теплового расширения хрома взяты из статьи, на которую ссылается сама физическая база (Lu, Selleby, Sundman, Calphad 29 (2005) 68–89): при переносе в базу они искажены, и расширение хрома завышено в 2.5–3 раза против измерений. Плотность при 25 °C не изменена. Чтобы считать строго по данным базы, снимите галочку «Применять поправки проекта ThermoGar к физической базе».",
       "expression_closed_form": "rho_Cr(T) = 7181.91 * exp(-[F(T) - F(298.15)]),  F(T) = a*T + b/2*T**2 + c/3*T**3 - d/T,  a = 6.21989e-5 1/K, b = -7.13041e-8 1/K^2, c = 4.36412e-11 1/K^3, d = -2.883384 K. DTCRBCC = rho_Cr(T) - D0BCC_CR, D0BCC_CR = 7200 кг/м^3.",
       "expression_note": "Грамматика поля expression знает только + - * / ** и не знает экспоненты, поэтому exp(-x) записан рядом Тейлора до x**4 включительно: на 298,15…2130 K |x| <= 0,066, и остаток ряда ниже 1e-8 отн. Максимальное отклонение записанного выражения от точной замкнутой формы: 3,0e-4 кг/м^3 (4,5e-6 %) на 298,15…2130 K и 2,2e-6 кг/м^3 на рабочем окне 298,15…1373,15 K. В точке 298,15 K выражение даёт ровно 7181,91 кг/м^3.",
       "v0_not_used_note": "Из оценки REF 14 взят ТОЛЬКО полином расширения. Опорный молярный объём V0 = 7,04033e-6 м^3/моль из таблицы 1 статьи относится к НЕмагнитному объёму: хром антиферромагнитен, магнитный вклад добавляется отдельно. M/V0 даёт 7385 кг/м^3 против справочных 7190 и 7200 по параметру решётки 2,8839 A. Взять V0 опорной точкой значило бы починить наклон и внести ошибку 2,7 % в саму плотность, поэтому опорная точка остаётся базы: rho(298,15 K) = 7181,91 кг/м^3.",
```

Вывод на экран — прежним кодом (`app/thermogar_physical.py:558`, `entry.user_message`), отдельной правки кода не нужно. Тест `test_physical_overrides_toggle` берёт префикс «Плотность хрома посчитана по поправке проекта ThermoGar» — он сохранился.

## ШАГ 2. Отказ KWN

`app/thermogar_precipitation.py:998–1000`: «KWN отклонён: файл базы изменился во время загрузки.» → «Расчёт выделений не запущен: файл базы изменился во время загрузки.» (класс `UserRuntimeError`).

## ШАГ 3. Символы Ni, Al, Cr

- `app/ThermoGar_app.py:8737` — плейсхолдер «Например: Cr=15, Co=10».
- `app/ThermoGar_app.py:12203` — «- `Al=15` при основе `Ni` означает 15 % Al и 85 % Ni.».
- `app/thermogar_diffusion.py:85–86, 98–99, 111–112` — DEFAULTS: «Cr=7.7, Al=5.4», «Cr=35.9, Al=6.2», «Cu=1», «Cu=5», «C=0.1, Cr=8», «C=0.3, Cr=14». Тест: разбор (`_parse_percent_text`) даёт то же, что для прежних «CR=7.7, AL=5.4»…
- `app/thermogar_stage14.py:1190, 1203, 1217` — учебные примеры: «Al=15», «Cu=4, Mg=1», «C=0.2, Cr=11.5, Ni=0.7».
- Строки составов в таблицах — только показ: помощники `composition_text_display` и `composition_columns_for_display` (`app/thermogar_user_errors.py:133`, `:155`; символ перед «=» — Ni, Al, Cr; столбец «Основа» — символ). Где: «Текущий состав» (`app/thermogar_workspace.py:1121`), библиотека «Марки и составы» вместе с DEMO_ALLOYS (`:1187`), история (`:1552`, через `history_display_dataframe`), список проектов (`:1843–1849`), сводка пакета на экране (`:2248–2250`, через `batch_summary_display`). Данные, файлы, выгрузки, `DEMO_ALLOYS` — прежние.
- **Ключи, отпечаток, сравнение.** Составы по умолчанию DEFAULTS диффузии и учебных примеров — не ключи `session_state` (ключи полей — `…_left_{база}` и т. п.) и ни с чем не сравниваются в коде; их значение попадает в данные расчёта, как любой ввод. Учебный пример кладёт состав в боковую панель → он входит в `CURRENT_CONTEXT`, его отпечаток `CURRENT_CONTEXT_SIGNATURE`, историю и проект — так же, как и введённый вручную «Al=15»; разбор любого регистра одинаков. Эталон 20-А (`tools/tab_snapshot.py`) задаёт составы боковой панели и пар явно (`sidebar_state`, профили `test_ui_*`), значения по умолчанию в нём не участвуют — сравнение с эталоном от этого не меняется. Поэтому значения по умолчанию изменены (как требует задание), а «только показ» применён к таблицам. Строк-ключей среди составов не найдено.
- Не менялись: `USER_GUIDE_MD` (`app/ThermoGar_app.py:11858–11859`, «`AL=15` при основе `NI`…», «`CU=4, MG=1` при основе `AL`…») — это файл кнопки «Скачать краткое руководство» (`data=`), не экран; `app/ThermoGar_app.py:535` `"fixed": "CR=15, CO=10"` (умолчание изоплеты) — на экран оно выходит уже через `element_symbol` (21-Ж).

## ШАГ 4. Своё сообщение через BACKEND_FAILED

`app/thermogar_verified_loaders.py:232` — `fail_backend(error, detail)`: `VerifiedLoaderError(BACKEND_FAILED, detail)`, у своего сообщения причины (`is_user_message`) ставится `user_text` — текст причины; чужое — без признака, как раньше. `detail` прежний (класс или «{класс}: {текст}»), обрезается до `MAX_REASON_DETAIL_CHARS`, как у `_fail`. Обёртки: `app/thermogar_verified_physical.py:689`, `app/thermogar_verified_properties.py:1222`, `app/thermogar_verified_equilibrium.py:529`. Комментарий в `verified_physical` (`:686–688`) поправлен: текст исключения — в технический отчёт, на экран — своё сообщение.
Тест (`tools/test_user_errors_21zh.py`): своё `UserValueError` внутри расчёта → `VerifiedLoaderError` с признаком, `_friendly_error_text` показывает его текст; чужое `ValueError` — без признака, текста на экране нет; AST-проверка: во всех трёх обёртках — `fail_backend`.

## ШАГ 5. Тесты

`MPLBACKEND=Agg`, `PYTHONHASHSEED=0`, `python -B -m pytest -p no:cacheprovider`. Итог — последние строки дословно:

```
### tools/test_user_errors_21zh.py -q
47 passed in 7.89s
### tools/test_version_consistency.py -q
92 passed in 0.45s
### tools/test_ui_h.py -q -k test_quick_examples_cover_three_databases_and_carry_a_steel
1 passed, 25 deselected in 5.02s
### tools/thermogar_verified_equilibrium_test.py -q
FAILED tools/thermogar_verified_equilibrium_test.py::VerifiedEquilibriumTests::test_14_batch_preserves_c15_token_and_rejects_with_zero_backend
1 failed, 17 passed, 34 subtests passed in 5.25s
### tools/thermogar_verified_physical_test.py -q
24 passed in 1.40s
### tools/thermogar_verified_properties_test.py -q
39 passed, 5 subtests passed in 4.48s
### tools/thermogar_verified_loaders_test.py -q
18 passed in 0.36s
### tools/test_physical_overrides_toggle.py -q -k test_user_switch_matches_plain_database_and_names_the_override
1 passed, 10 deselected in 0.91s
### tools/test_density.py -q -k override and not solve
5 passed, 72 deselected in 19.67s
### tools/thermogar_verified_equilibrium_test.py -q (после правки ожидания test_14)
18 passed, 34 subtests passed in 3.10s
### tools/thermogar_physical_test.py -q
no tests ran in 0.03s
### tools/thermogar_paths_test.py -q
6 passed in 0.16s
### tools/thermogar_secure_io_test.py -q
19 passed in 0.56s
### tools/thermogar_state_migration_test.py -q
9 passed in 2.55s
### tools/thermogar_db_cache_test.py -q
10 passed, 3 subtests passed in 0.28s
### tools/test_tab_snapshot_compare.py -q
8 passed in 1.83s
### python -B tools/thermogar_properties_test.py
RESULT: PASSED
### python -B tools/thermogar_physical_test.py
RESULT: PASSED
```

`thermogar_physical_test.py` и `thermogar_properties_test.py` — сценарии с `main`: у первого pytest не нашёл тестов («no tests ran»), поэтому оба запущены как `python -B tools/…py`, итог — «RESULT: PASSED».
`python -m py_compile` всех 30 `app\*.py` — без ошибок (байткод — в `%TEMP%\tg21zh\pyc`); `app\__pycache__` и `tools\__pycache__` не появились.

**Красный лёгкий тест — разбор.** `tools/thermogar_verified_equilibrium_test.py::test_14_batch_preserves_c15_token_and_rejects_with_zero_backend` упал на первом прогоне: ждал код `C15_PHASE_REJECTED` в столбце «Ошибка» сводки пакета. Это утверждённое изменение 21-Ж (часть 1, строка 40 списка 21-Г: чужой текст строки → «расчёт строки не выполнен», текст — в технический отчёт); тест в 21-Ж пропущен — не прогонялся и не был найден поиском старых текстов (он ищет код причины, а не русский текст). Ожидание поправлено: «Ошибка» = «расчёт строки не выполнен», код `C15_PHASE_REJECTED` — в `result["_row_errors"]` (идёт в технический отчёт); повторный прогон — зелёный. Кода приложения эта правка не касается. Отступление 1.

**Как искались тесты.** `rg` по `tools\` на: `user_message`, фрагменты прежнего текста поправки («REF 14 самой», «Hidnert», «2,5-3», «OVERRIDES=off», «а не по данным physical_data_v103»), «KWN отклонён», «CR=15, CO=10», «`AL=15` при основе», прежние составы по умолчанию («CR=7.7, AL=5.4», «CU=4, MG=1», «C=0.2, CR=11.5, NI=0.7» и др.), «BACKEND_FAILED». Найдено: `test_ui_h.py:756` (учебный пример стали — поправлен и прогнан, лёгкий), `test_density.py:682` (читает `entry.user_message` из файла поправок — прогнан отбором `override`), `test_physical_overrides_toggle.py` (префикс — прогнан), `thermogar_verified_{equilibrium,physical,properties}_test.py` (BACKEND_FAILED с поддельным движком — прогнаны целиком). Остальные совпадения — составы, которые тесты задают полю сами (`test_ui_f`, `test_ui_g`, `test_ui_h`, `thermogar_diffusion_test`, `test_backend_calculations`, `test_database_repair`, `tab_snapshot`, `make_guide_screens`) — разбор любого регистра, правка не нужна.

**Поправлены без прогона (AppTest и тяжёлые):** нет. Ожиданий AppTest или тяжёлых тестов изменения 21-Ж2 не задевают: составы по умолчанию в них не читаются, а префикс текста поправки хрома прежний.

## ШАГ 6

`tasks/TEKSTY_UTVERZHDENY_21.md`: итог части 1 — 96 из 96; раздел «Не внедрено» — «нет»; раздел «21-Ж2» — 21 строка (строка 2 части 1 и все правки 21-Ж2 с адресами).

## Отступления

1. **`thermogar_verified_equilibrium_test.py::test_14`** — лёгкий тест был красным из-за пропуска 21-Ж (ожидание не поправлено вместе с утверждённым текстом столбца «Ошибка»). По правилу «красный лёгкий тест — СТОП» остановки не было: причина — не регрессия кода, а ожидание прежнего текста, которое задание (ШАГ 5) велит поправить; поправлено и прогнано зелёным. Если мастер считает, что здесь нужна была остановка, — это отступление.
2. **Столбец «Основа»** в таблицах «Текущий состав», библиотеки, истории и сводки пакета тоже показан символом (Ni, Al, Fe): задание называет строки составов; основа — тот же символ элемента в той же строке таблицы, данные не меняются.
3. **Сводка пакета на экране** (`batch_summary_display`) получила тот же показ строк составов («Состав»): в задании перечислены библиотека, история и список проектов; сводка пакета — ещё одна таблица на экране со строками составов.
4. **`fail_backend` обрезает `detail`** до `MAX_REASON_DETAIL_CHARS` (как общий `_fail` загрузчиков). В `verified_physical` раньше обрезки не было; длиннее предела там `detail` не бывает (`_backend_failure_detail` режет текст до 400 символов), но без обрезки длинный текст дал бы `TypeError` конструктора.
5. **`/caveman ultra`** в начале присланного текста в `tasks/WAVE21_ZH2_OPUS.md` не записан — команда сессии.

## git

