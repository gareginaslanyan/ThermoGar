# Отчёт 21-У

Задание — `tasks/WAVE21_U_OPUS.md` (дословно, первый коммит ветки `ff7713c`). Машина — ноутбук Windows 10, дерево `D:\Pets\ThermoGar-w21b`, интерпретатор `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe` (Python 3.11, Streamlit 1.62.0, pandas 3.0.5). Все прогоны — `PYTHONHASHSEED=0`, `MPLBACKEND=Agg`, `PYTHONDONTWRITEBYTECODE=1`, `python -B`, `THERMOGAR_STATE_ROOT` во временной папке (`%TEMP%\tg21u_*`). Свободной памяти перед тяжёлыми прогонами — 8.0–8.4 ГиБ.

## ШАГ 0. Слияния

`git status --short` — только `?? _to_delete/`. `git fetch origin` прошёл без обрыва. `git ls-remote origin main wave21-t wave21-s` — `976e7075c980add6002957ad54cdc36dd290771c`, `b8d27471a272994066ad7b736344a775c8e766a5`, `8ff14346696554728ba8ce867f8f2fd4f016fff8` = задание. От `origin/main` (detached), `git merge --no-ff`, конфликтов нет:

| Слияние | Коммит | Родители | Дерево |
|---|---|---|---|
| 1) `origin/wave21-t` — «Merge wave21-t: слияния 21-О, 21-П, 21-Р; реестр; BL-69 (21-Т)» | `5b046d9588be3a4b0cb89fec718abdb3d565b6f3` | `976e7075…`, `b8d27471…` | `e5c34448f3cfd44004311f5c5f03ce52d5cb29e4` = модель мастера |
| 2) `origin/wave21-s` — «Merge wave21-s: BL-68 — опись таблиц и проба показа пустых ячеек (21-С)» | `3e2e31877e66a3c5f6144f707287369dcf990b22` | `5b046d95…`, `8ff14346…` | `6bede719245037572c523f63edc911d43f4fd2f2` = модель мастера |

Тесты на `3e2e318` (7 файлов: `test_version_consistency`, `test_switch_21i`, `test_wave21_m`, `test_wave21_o`, `test_precipitation_bl35`, `test_kwn_step_cap_22b`, `test_tab_snapshot_compare`) — `166 passed, 3 warnings in 316.51s`. `git push origin HEAD:refs/heads/main` — `976e707..3e2e318  HEAD -> main`. `git switch -c wave21-u`; задание без первой строки — `tasks/WAVE21_U_OPUS.md`, коммит `ff7713c`.

## ШАГ 1. Реестр

Коммит `dbb3949`. Тексты мастера — дословно, хеши слияний — `5b046d9` (21-Т), `3e2e318` (21-С):

- таблица волны 21: строка 21-Т — начало ячейки состояния заменено; строка 21-С — ячейка состояния заменена; после строки 21-Т — строки 21-У и 21-Ф;
- после абзаца «Приёмка 21-Р мастером…» — абзацы «Приёмка 21-Т мастером», «Приёмка 21-С мастером», «Решения владельца, 26.09.2026: номер выпуска и пустые ячейки»;
- перед «## Волна 22 …» — раздел «### Ошибка мастера (21-С)»;
- бэклог: BL-68 — «**в работе, 21-У** (…)»; BL-69 — «**закрыт 21-Т (принята мастером 26.09.2026).**»; после BL-69 — строки BL-70, BL-71, BL-72.

## ШАГ 2. BL-68 — прочерк в пустых ячейках

Коммит `5a9fe66`.

- `app/thermogar_user_errors.py:151–156` — комментарий (решение владельца 26.09.2026, BL-68, вариант Б; ГОСТ 2.105-95, п. 4.4.18; только показ, данные и выгрузки не меняются) и `EMPTY_CELL_TEXT = "—"` (U+2014, байты `e2 80 94`).
- Импорт постоянной: `app/ThermoGar_app.py:264`, `app/thermogar_workspace.py:80`, `app/thermogar_precipitation.py:51`, `app/thermogar_diffusion.py:53`, `app/thermogar_stage14.py:46` (первой строкой в существующем `from thermogar_user_errors import (…)`), `app/thermogar_properties.py:48` (`from thermogar_user_errors import EMPTY_CELL_TEXT, UserMessage, UserValueError`).
- Во все 64 вызова `st.dataframe` / `st.data_editor` добавлен только аргумент `placeholder=EMPTY_CELL_TEXT`: в однострочном вызове — перед закрывающей скобкой, в многострочном — последней строкой аргументов. Данные таблиц, ключи, `column_config`, выгрузки — не тронуты. `placeholder=` у `st.text_input` / `st.text_area` (9 мест) — не тронуты.

### 64 вызова — файл:строка (wave21-u)

Сверено по коду (ast): на `976e707` — те же 64 вызова, то же разбиение по файлам (37 / 7 / 6 / 5 / 5 / 4); строки описи 21-С (`a68a417`) сопоставлены по порядку внутри файла. Полная таблица — `results/wave21_u/vyzovy_64.csv` (№ описи 21-С, строки на `a68a417`, `976e707`, `wave21-u`, экран и оценка «None» из описи).

- `app/ThermoGar_app.py` (37): 1866, 1894, 1896, 2086, 2153, 2187, 2330 (`data_editor`, «Упругие свойства»), 2423, 2615, 3075 (`data_editor`, выбор фаз), 7767, 7788, 8092, 8482, 8899, 9406, 9805, 10369, 10380, 11109, 11130, 11169, 11176, 11183, 11235, 11518, 11527, 11534, 11770, 11776, 12066 (T₀), 12533, 12546, 12567, 12575, 12801, 12892.
- `app/thermogar_workspace.py` (7): 1122, 1187, 1845, 2071, 2780, 2856, 2861.
- `app/thermogar_precipitation.py` (6): 1850, 1853, 1857, 1859, 1860, 1863.
- `app/thermogar_diffusion.py` (5): 1290, 1300, 1303, 1304, 1871.
- `app/thermogar_stage14.py` (5): 932, 1270, 1274, 1297, 1405.
- `app/thermogar_properties.py` (4, мёртвые по 21-С): 1664 (`data_editor`), 1807, 1808, 2231.

## ШАГ 3. BL-70–BL-72

Коммит `18e4be2`. Новых слов на экране нет. Сначала — тесты ШАГА 4 на коде до правки (`5a9fe66`): 4 failed, 4 passed (`results/wave21_u/testy/test_wave21_u_do_pravki.log`); после правки — 8 passed.

| BL | Правка (файл:строка после правки) | Тест до правки (красный) | После |
|---|---|---|---|
| BL-70 | `app/ThermoGar_app.py:2352–2366`: строка `row` из редактора; у `origin`, `source`, `note` строка — `.strip()`; `note` = None → `""`. Остальные поля не тронуты; `app/thermogar_verified_properties.py` не менялся | `test_elastic_vrh_accepts_editor_text[note-none]` и `[trailing-space]`: кнопка активна (`disabled` = False), после нажатия — «ThermoGar не завершил расчёт. …»; техническая причина (`results/wave21_u/scripts/diag_bl70.py`, вывод `results/wave21_u/testy/diag_bl70_do_pravki.log`): `INPUT_INVALID: note is invalid.` и `INPUT_INVALID: origin is invalid.` | passed: VRH посчитан, фаза FCC_A1, E Hill = 200 ГПа |
| BL-71 | `app/thermogar_workspace.py:2401–2404`: пустая строка (после strip) в столбце элемента пропускается, как NaN | `test_batch_empty_element_cell_is_no_addition`: статусы `['готово', 'ошибка']`, у второй строки — «расчёт строки не выполнен» | passed: обе строки «готово»; у «NI-AL» в «Составе» Al=15, Cr нет |
| BL-72 | `app/thermogar_database_guard.py:615–619`: `None if v is None else str(v)` | `test_passport_empty_patch_fields_are_empty_cells`: `('Статус поправки', 'None')` | passed: три ячейки пустые, строки «None» в «Значении» нет |

## ШАГ 4. Тесты и регрессия

Коммит `55dfe83`.

### Новые тесты — `tools/test_wave21_u.py`, 8

| Тест | Что проверяет |
|---|---|
| `test_empty_cell_text_is_em_dash` (`:123`) | `EMPTY_CELL_TEXT == "\u2014"` |
| `test_every_table_call_has_the_placeholder` (`:138`) | ast по `app/*.py`: вызовов 64, по файлам 37 / 7 / 6 / 5 / 5 / 4, у каждого ровно один `placeholder=EMPTY_CELL_TEXT` |
| `test_tzero_steel_table_shows_dash_and_keeps_nan` (`:159`, AppTest) | сталь по умолчанию, «Рассчитать T₀»: одна таблица с «T₀, °C», `proto.placeholder == "—"`; 21 строка; в строках C 1.8, 1.9, 2.0 мас.% «T₀, °C» и «T₀, K» — NaN, столбцы числовые; в `tzero_result["data"]` NaN — 3 |
| `test_elastic_editor_placeholder` (`:181`, AppTest) | Ni-20Cr, «Получить фазовые доли»: у редактора (в `at.dataframe`, столбец `young_gpa`) `proto.placeholder == "—"` |
| `test_elastic_vrh_accepts_editor_text[note-none]`, `[trailing-space]` (`:209`, AppTest) | BL-70: подмена `st.data_editor`, как фикстура `elastic_capture`; «Примечание» None; «Происхождение» и «Источник» с пробелом в конце — кнопка активна, VRH посчитан без ошибок |
| `test_batch_empty_element_cell_is_no_addition` (`:237`, AppTest) | BL-71: CSV `Название,База,Основа,Единицы,"Температура, °C",Добавки,AL,CR`, строки `NI-AL-CR` (15, 5) и `NI-AL` (15, пусто), «Добавки» пусты — обе строки «готово», в составе `NI-AL` нет Cr |
| `test_passport_empty_patch_fields_are_empty_cells` (`:270`) | BL-72: подмена `compatibility_patch_record` (status, action, matched_active_commands = None) — «Статус поправки», «Действие», «Совпавших активных команд» пустые, «None» в «Значении» нет |

`8 passed in 95.68s` в регрессии.

### Поправленные ожидания

Нет: тестов, державших прежнее (слово «None» в ячейке, отказ VRH, отказ строки пакета, `str(v)` в паспорте), не нашлось; вся регрессия зелёная без правки чужих тестов.

### Полная регрессия

`results/wave21_u/scripts/run_regressiya.sh` — копия 21-О: изменены только строка заголовка, папка вывода `results/wave21_u/testy` и состояние `tg21u_tests_state`. Один поток, 17:30–19:38; `test_ui_f` — одним процессом (свободно 8.43 ГиБ), журнал памяти — `results/wave21_u/testy/memlog_test_ui_f.jsonl`.

| Файл | Итог |
|---|---|
| `test_backend_calculations` | 57 passed, 6 warnings in 1194.62s |
| `test_chart_celsius_ticks` | 17 passed |
| `test_chart_legend_theme` | 12 passed |
| `test_chart_theme_21e` | 73 passed |
| `test_database_repair` | 44 passed |
| `test_density` | 77 passed |
| `test_density_below_pdb` | 5 passed |
| `test_density_thermal_expansion` | 11 passed, 1 xfailed |
| `test_dropped_phases_text` | 2 passed |
| `test_equilibrium_solidus_fallback` | 19 passed |
| `test_error_log_worker_21z` | 4 passed |
| `test_kwn_step_cap_22b` | 9 passed, 1 warning |
| `test_liquidus_bisection` | 2 passed |
| `test_parallel_engine` | 15 passed |
| `test_parallel_integration` | 6 passed |
| `test_phase_description_order_words` | 11 passed |
| `test_phase_description_stub_keys` | 9 passed |
| `test_phase_presets` | 21 passed |
| `test_phase_presets_control` | 1 passed |
| `test_physical_overrides_toggle` | 11 passed |
| `test_precipitation_bl35` | 11 passed, 1 warning |
| `test_precipitation_grid` | 32 passed, 12 warnings |
| `test_sidebar_composition_error` | 9 passed |
| `test_style_21z` | 11 passed |
| `test_switch_21i` | 13 passed |
| `test_tab_snapshot_compare` | 8 passed |
| `test_ui_f` | 59 passed in 1951.92s |
| `test_ui_g` | 32 passed, 5 warnings in 399.82s |
| `test_ui_h` | 26 passed |
| `test_user_errors_21zh` | 47 passed |
| `test_version_consistency` | 92 passed |
| `test_wave15_z` | 15 passed, 2 warnings |
| `test_wave21_m` | 22 passed |
| `test_wave21_o` | 11 passed, 1 warning |
| `test_wave21_u` | 8 passed |
| 12 файлов unittest (`thermogar_active_state_io`, `db_cache`, `fe_internal_smoke`, `paths`, `restricted_fe_core`, `secure_io`, `state_migration`, `verified_equilibrium`, `verified_loaders`, `verified_physical`, `verified_properties`, `verified_state`) | Ran 203 tests / OK |
| 7 сценариев (`converter_patch`, `diffusion`, `fe_database`, `physical`, `precipitation`, `properties`, `self_test`) | RESULT: PASSED (`thermogar_precipitation_test` — Final volume fraction 6.599577401641879 %) |

Сумма: 35 файлов pytest — 802 passed, 1 xfailed (в 21-О — 794 и 1 xfailed; плюс 8 новых). 12 файлов unittest — 203 OK. 7 сценариев — PASSED. Красных — 0.

## ШАГ 5. Кадры и замеры

Коммит `6556f0c`. Скрипты 21-О — копией в `results/wave21_u/scripts/`: `kadry.py`, `formy.py`, `run_app.cmd` (изменены только строка заголовка, папка `results/wave21_u`, состояние `tg21u_state`, порт 8661); сами кадры — `kadry_21u.py` (помощники из `kadry_21o.py`), замеры — `zamery.py`. Окно 1440×900, обе темы, приложение перезапускается перед каждым прогоном.

| Кадр | Что на нём |
|---|---|
| `results/wave21_u/kadry/tzero_fe_umolch_svet.png`, `_tyomn.png` (окно) и `_svet_tablica.png`, `_tyomn_tablica.png` (таблица) | «Энергии → T₀», сталь по умолчанию (200–950 °C): сетка прокручена к концу, строки C 1.8, 1.9, 2 мас.% — серый прочерк «—» в «T₀, °C» и «T₀, K», «Решение найдено» снято; 1.1–1.7 — числа |
| `results/wave21_u/kadry/uprugie_shag2_svet.png`, `_tyomn.png` и `_tablica` | «Свойства → Упругие свойства», Ni по умолчанию, шаг 2: FCC_A1 и GAMMA_PRIME — прочерк в E, ν, «Происхождение», «Источник», «Температура источника, °C»; «Примечание» — пустая ячейка (там пустая строка `""`, не пустое значение — как в описи 21-С) |

Замеры — `results/wave21_u/zamery.csv` (UTF-8 с BOM, «;», 20 строк), записи — `results/wave21_u/kadry_21u.json`. T₀ стали: счёт 13.6 с (обе темы), Excel T0 — 21 строка, найдено 18, в строках C 1.8–2.0 пустых «T₀, °C» / «T₀, K» — 3 / 3 (данные и выгрузка не меняются). «Упругие свойства»: «Получить фазовые доли» — 9.5 / 9.6 с, фаз 2.

## Отступления

1. BL-72, тест: задание — «ячейки … пустые (None)». В pandas 3.0.5 столбец «Значение» получает строковый тип, и None в нём хранится как NaN (`StringDtype(na_value=nan)`); правка кода — дословно по заданию (`None if v is None else str(v)`). Тест проверяет `pd.isna(...)` и отсутствие строки «None»; на экране ячейка пустая — прочерк. Первый прогон теста после правки (с `is None`) был красным только по этой причине.
2. BL-70, до правки: русский текст ошибки на экране общий («ThermoGar не завершил расчёт. …»), причина `note is invalid.` / `origin is invalid.` видна только в технических сведениях. Её снял отдельный скрипт `results/wave21_u/scripts/diag_bl70.py` (та же подмена редактора, тот же AppTest); вывод — `results/wave21_u/testy/diag_bl70_do_pravki.log`.
3. Журналы прогонов (`*.log`) в `results/wave21_u/testy/` исключены `.gitignore` (как в 21-О) и лежат только на ноутбуке; в коммите — `memlog_test_ui_f.jsonl`.
4. Проверка синтаксиса `kadry_21u.py` через `py_compile` создала `results/wave21_u/scripts/__pycache__/` — перенесён в `_to_delete/21u_pycache_scripts/`, опись sha256 — `_to_delete/21u_pycache_scripts/opis_sha256.txt`. Ничего не удалялось.
5. Кадры T₀: в первом прогоне колёсико мыши не дошло до сетки (сетка была вне окна), строки 1.8–2.0 в кадр не попали. Скрипт поправлен (сетка сначала в окно, потом колёсико), случай T₀ переснят в обеих темах с перезапуском приложения; файлы первого прогона перезаписаны.
6. Замечено, не менялось (вне задания): предпросмотр загруженного пакетного CSV со строкой `""` в числовом столбце элемента даёт в журнале Streamlit «Serialization of dataframe to Arrow table was unsuccessful…» (автоисправление типов Streamlit); на экране это пустая ячейка, не «None».

## Git

Вывод после `git push -u origin wave21-u` (коммит отчёта `ad1f49b`; этот раздел добавлен следующим коммитом «docs(21-У): отчёт — вывод git после пуша», в список ниже он не входит).

`git push -u origin wave21-u`:

```
To https://github.com/gareginaslanyan/ThermoGar.git
 * [new branch]      wave21-u -> wave21-u
branch 'wave21-u' set up to track 'origin/wave21-u'.
```

`git ls-remote origin main wave21-u`:

```
3e2e31877e66a3c5f6144f707287369dcf990b22	refs/heads/main
ad1f49b6d3df47cdb848fe861d111efb9e9d9af7	refs/heads/wave21-u
```

`git log --oneline 3e2e318..wave21-u`:

```
ad1f49b docs(21-У): отчёт, строка 21-У в реестре, BL-68, BL-70–BL-72
6556f0c docs(21-У): кадры и замеры прочерка в пустых ячейках (T₀ стали, «Упругие свойства»)
55dfe83 test(21-У): тесты BL-68 и BL-70–BL-72, полная регрессия
18e4be2 fix(21-У): BL-70 — текст «Упругих свойств» без пробелов по краям, пустое «Примечание»; BL-71 — пустая ячейка элемента в пакете; BL-72 — None в паспорте базы стали
5a9fe66 feat(21-У): BL-68 — прочерк «—» в пустых ячейках всех таблиц экрана (placeholder)
dbb3949 docs(21-У): реестр — приёмки 21-Т и 21-С, решения владельца, ошибка мастера (21-С), BL-68–BL-72
ff7713c docs(21-У): задание волны 21-У
```

`git status --short`:

```
?? _to_delete/
```
