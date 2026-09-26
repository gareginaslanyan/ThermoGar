# 21-О. Отчёт

Задание — `tasks/WAVE21_O_OPUS.md`. Дерево `D:\Pets\ThermoGar-w21b`, ветка `wave21-o`, 26.09.2026, ноутбук Windows 10. Интерпретатор — `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe`. Все прогоны — `PYTHONHASHSEED=0`, `MPLBACKEND=Agg`, `THERMOGAR_STATE_ROOT` во временной папке (`%TEMP%\tg21o_*`); приложение и прогоны через AppTest — ещё с `PYTHONDONTWRITEBYTECODE=1`. Перед каждым тяжёлым прогоном свободно 7.5–8.4 ГиБ; тяжёлый прогон — всегда один. `databases/`, `configs/`, `packaging/`, `docs/`, `CHANGELOG.md`, `tools/study_*.py`, `tools/make_guide_screens.py`, `tools/tab_snapshot.py` не менялись; `.tdb` и `.pdb` не трогались. `D:\Pets\ThermoGar`, `D:\Pets\ThermoGar-w21a` и `D:\Pets\Lilith` не открывались. Ничего не удалялось.

## ШАГ 0. Слияния

- `git status --short` — только `?? _to_delete/`.
- `git fetch origin` прошёл без обрыва.
- `git ls-remote origin main wave21-m wave21-n wave22-a wave22-b` — все пять хешей как в задании: `main` `10c25ae…`, `wave21-m` `22b83ba…`, `wave21-n` `9a29302…`, `wave22-a` `4074041…`, `wave22-b` `085b0f2…`.
- `git switch --detach origin/main`; четыре `git merge --no-ff` с сообщениями задания. Конфликтов нет; `app/thermogar_precipitation.py` в четвёртом слиянии слит автоматически (`Auto-merging`).

| № | Коммит слияния | Родители | Дерево | Модель мастера |
|---|---|---|---|---|
| 1 | `b487026699b53aa803743c7b5a5f67d780907a14` | `10c25ae`, `22b83ba` | `113249532ea71f014a34d30d8a0719c4df62a2de` | совпало |
| 2 | `dd75b129412f45eac789f7c8c1c6129b85fd431a` | `b487026`, `9a29302` | `044786159caa0627de5022298a0aae50b41c90ab` | совпало |
| 3 | `7b02eb85079673b6298786ce53be15ce7aedeeb3` | `dd75b12`, `4074041` | `6eb353ad407351631bea5db08ce370ab1cbc6f01` | совпало |
| 4 | `a68a41704f4db6053d8c073c96c30938251be930` | `7b02eb8`, `085b0f2` | `39fa388dde8a8975baeca2725e32be8ef7f990ee` | совпало |

Тесты после слияний (свободно 8.27 ГиБ): `test_version_consistency` — 92 passed; `test_switch_21i` — 13 passed; `test_wave21_m` — 22 passed (с AppTest, Windows); `test_precipitation_bl35` — 11 passed; `test_kwn_step_cap_22b` — 9 passed.

`git push origin HEAD:refs/heads/main` — `10c25ae..a68a417  HEAD -> main`. Ветка `wave21-o` — от `a68a417`; первый коммит — задание без строки «/caveman ultra» (`5c18016`).

## ШАГ 1. Реестр

Коммит `6d519f3`. Тексты мастера вставлены программой; каждая строка текста задания сверена как подстрока реестра (14 строк и 5 ячеек — совпадение), хеши: `b487026` (21-М), `dd75b12` (21-Н), `7b02eb8` (22-А, 22-А2), `a68a417` (22-Б).
- таблица волны 21: 21-М, 21-Н; строки 21-О и 21-П — после 21-Н;
- три абзаца («Приёмка 21-Н…», «Приёмка 21-М…», «Решения владельца по стали, 26.09.2026…») — после «Решения владельца по дизайну, 25.09.2026…», перед «### Ошибка мастера (21-В)»;
- «### Ошибка мастера (BL-66)» — после «### Ошибка мастера (9Б)», перед «## Волна 22 …»;
- волна 22: фраза про облачную сессию, ячейки 22-А и 22-А2, строка 22-Б, два абзаца приёмок перед «### Ошибка мастера (22-А)», «### Ошибка мастера (22-Б)» — перед «## Завершённые волны»;
- бэклог: BL-43, BL-65, BL-66 (описание и ячейка), BL-67; BL-68 и BL-69 — после BL-67.

## ШАГ 2. 22-Б на Windows — тесты интерфейса и справка

Коммит `c1577ca`.

- `tools/test_ui_g.py:414–419` — ветка `if database_key == "fe"` с ожиданием остановки убрана: у fe те же ожидания, что у ni и al (`new_errors(app) == []`, `stop_note == ""`, все проверки «пройдена»); комментарий — BL-43 исправлен 22-Б (шаг KWN растёт не больше 2× предыдущего), ячейка 40 классов не останавливается (Linux, зёрна 0–9 — `tasks/WAVE22_B_REPORT.md`).
- `tools/test_ui_g.py:368–374` — комментарий о времени ячеек: замер ноутбука после 22-Б — ni 30 с, al 20 с, fe 76 с (Linux: fe 44–48 с); марка `slow` у fe не менялась.
- Прогон `tools/test_ui_g.py::test_kwn_precipitation -v --durations=0`: `3 passed in 129.85s`; `[fe]` — 75.89 с, `[ni]` — 30.48 с, `[al]` — 20.34 с. fe на Windows не останавливается — СТОП не понадобился.

`tools/backend_reference.md` — прогон `tools/test_backend_calculations.py -v -k kwn` способом 13-Р2 (`THERMOGAR_BACKEND_REPORT` — Windows-путь, отчёт `results/wave21_o/testy/shag2_backend_kwn_report.json`): `6 passed in 85.79s`.

| Ячейка | Было | Стало | Linux 22-Б (для сверки) |
|---|---|---|---|
| `:75` KWN-модуль ni | PASS 18.1 | PASS 14.6 (22-Б; было 18.1) | 12.15 с |
| `:75` KWN-модуль al | PASS 10.3 | PASS 7.3 (22-Б; было 10.3) | 5.45 с |
| `:75` KWN-модуль fe | PASS 84.4 `slow` | PASS 37.8 `slow` (22-Б; было 84.4; 13-Р2 — было XFAIL 0.0) | 34.95 с |
| `:236` ni | 246 строк | без изменений (246) | 246 |
| `:237` al | 97 строк | без изменений (97) | 97 |
| `:238` fe | 2391 строка | 1123 строки (22-Б; было 2391), без остановки | 1249 |

## ШАГ 3. T₀ — BL-66 и решение 2В

Коммит `ab5d459`, `app/ThermoGar_app.py`.
- а) `:4511–4516` — столбец состава из кортежа условия пути: `start, stop, step = conditions[axis_variable]`, `composition_axis = np.round(100.0 * np.arange(start, stop, step), 10)`. Путь pycalphad, T₀ и «Решение найдено» (`np.isfinite(tzero_k)`) не менялись.
- б) `ENERGY_DEFAULTS` — ключи `tzero_t_min` / `tzero_t_max`: ni `:436–437` (300 / 1700), fe `:451–453` (200 / 950, с комментарием 2В), al `:467–468` (100 / 1000). Поля «Нижняя / Верхняя граница поиска T₀, °C» — `:11911`, `:11917`. «Энергии фаз» (`:11332`, `:11338`) и «Движущая сила» (`:11590`, `:11596`) — прежние `t_min` / `t_max`. Ключи виджетов не менялись.
- в) Сверка на ноутбуке — `results/wave21_o/scripts/tzero_sverka.py` (AppTest, умолчания стали), таблицы — `results/wave21_o/data/tzero_fe_200_950.csv`, `tzero_fe_300_1700.csv`.

| Окно | Строк | Найдено | Ноутбук | Мастер (Linux) | Состав |
|---|---|---|---|---|---|
| 200–950 °C (умолчание) | 21 | 18 (C 0…1.7) | C 0 — 911.62 °C, C 1.7 — 207.23 °C | 911.62 / 207.23 | 0.0…2.0 во всех 21 |
| 300–1700 °C | 21 | 15 | строки 0–2 — 911.70 / 801.34 / 735.89; 3–14 — 1563.10…1698.56 | те же | 0.0…2.0 во всех 21 |

Расхождений нет (до 0.01 °C). Время счёта: 12.6 с и 41.4 с.

## ШАГ 4. «Выделения» — решения 1Б и 3В

Коммит `60e67e0`, `app/thermogar_precipitation.py`.
- 1Б: `DEFAULTS["fe"]` (`:92`) — выдержка 0.05 → 0.01 ч; остальное в кортеже без изменений.
- 3В: `_composition_stop_note` (`:370–383`) — при конечном `value < 0`: «Расчёт остановлен на {время}: доля {Эл} в матрице ушла ниже нуля, баланс масс нарушен. Показана часть расчёта до остановки. {причина}» (`:373–378`); при 0, больше 1 и не числе — прежний текст «стала … ат.%» (`:379–383`). `_solver_failure_note` и `KWN_COMPOSITION_STOP_CAUSE` не менялись. Новых слов экрана, кроме «ушла ниже нуля», нет.

## ШАГ 5. Решение 12Б — символы элементов в выгрузках

Коммит `466299d`. 7 вызовов `element_columns_for_display` при записи файла:

| № | Выгрузка | Файл:строка | Заголовки до → после (замер ШАГА 7) |
|---|---|---|---|
| 1 | `dataframe_to_excel` — все листы всех Excel приложения | `app/ThermoGar_app.py:5772–5773` | «Составы фаз ат» ni: `NI, ат.% \| AL, ат.%` → `Ni, ат.% \| Al, ат.%`; T₀ ni: `AL, ат.%` → `Al, ат.%` |
| 2 | CSV «Изменение состава» | `app/ThermoGar_app.py:8483` | al: `CU, атомные %` → `Cu, атомные %` |
| 3 | CSV «Карта доли фазы» | `app/ThermoGar_app.py:10375` | тем же помощником, что лист «Расчётная сетка» |
| 4 | ZIP затвердевания, `*_liquid_composition.csv` | `app/ThermoGar_app.py:5471–5475` | `NI, ат.% \| NI, мас.%` → `Ni, ат.% \| Ni, мас.%` |
| 5 | Excel выделений, «Состав матрицы» | `app/thermogar_precipitation.py:1484–1487` | `AL, матрица, ат.% \| NI, матрица, ат.%` → `Al, …`, `Ni, …` |
| 6 | Excel выделений, «Межфазные составы» | `app/thermogar_precipitation.py:1488–1490` | `AL, матрица на границе, ат.%` → `Al, …` |
| 7 | Пакет, «Составы фаз ат» и «Составы фаз мас» | `app/thermogar_workspace.py:2868–2874` | `NI, ат.% \| AL, ат.%` → `Ni, ат.% \| Al, ат.%` |

Без изменений (замер `results/wave21_o/data/vygruzki_12b.csv`, «совпадает — да»): листы «Равновес raw», «Scheil raw» (`Temperature (°C)`, `NP(LIQUID)`, `X(FCC_A1,AL)` — помощник эту форму не берёт); «Исходные данные» пакета (`name | database | balance | …`); «Сводка», «Фазовые доли» пакета; имена листов, файлов и членов архива; значения ячеек. Исходные таблицы после записи файла не меняются (проверено тестами).

Докстринги: `app/thermogar_user_errors.py:65` и `:115` — тексты задания; `:136` не менялся. Комментарий `tools/test_user_errors_21zh.py:247` — текст задания.

## ШАГ 6. Тесты и регрессия

Коммит `7f04aef`.

### Поправленные ожидания

| Файл:строка | Было | Стало |
|---|---|---|
| `tools/test_ui_g.py:414–419` (ШАГ 2) | fe: ждать остановку — статус «ошибка» у «Состав матрицы допустим», `stop_note` в `st.error`, `new_errors == [stop_note, QUALITY_FAILED_ERROR]` | fe как ni и al: ошибок нет, `stop_note == ""`, все проверки «пройдена» |
| `tools/test_user_errors_21zh.py:247` (ШАГ 5) | комментарий «Сама таблица (данные и выгрузки) не меняется.» | комментарий задания; ожидания теста не менялись |

Других тестов, державших прежнее (окно T₀ стали, выдержку стали, текст остановки, заголовки выгрузок), не нашлось. `tools/test_wave15_z.py:323–340` (`_composition_stop_note(2.011, "NB", 0.0)`) — зелёный без правки.

### Новые тесты — `tools/test_wave21_o.py`, 11

| Тест | Что проверяет |
|---|---|
| `test_composition_stop_note_below_zero` | `_composition_stop_note(3.885, "TI", -9.864e-5)` — дословно «Расчёт остановлен на 3.885 с модельного времени (0.001079 ч): доля Ti в матрице ушла ниже нуля, баланс масс нарушен. Показана часть расчёта до остановки. » + `KWN_COMPOSITION_STOP_CAUSE` |
| `test_composition_stop_note_zero_keeps_the_number` | при 0.0 — «стала 0 ат.%», без «ниже нуля» |
| `test_steel_windows_and_holding_time` (AppTest) | сталь: окно T₀ 200 / 950; «Энергии фаз» и «Движущая сила» — 300 / 1700; «Время выдержки, ч» «Выделений» — 0.01 |
| `test_tzero_steel[200-950]` (AppTest) | 21 строка, найдено 18, состав 0.0…2.0 без пустых, счётчик «T₀ найдено в 18 точках из 21. …» (текст существующий), заголовок Excel `C, мас.%` |
| `test_tzero_steel[300-1700]` (AppTest) | 21 строка, найдено 15, состав без пустых, счётчик 15 из 21 |
| `test_helper_leaves_raw_and_bare_columns` | помощник не трогает `X(FCC_A1,CR)`, `NP(FCC_A1)`, `T` и голые `CR`, `NI`, `C` |
| `test_single_equilibrium_excel_ni` (AppTest) | «Составы фаз ат» — `Ni, ат.%`, `Al, ат.%`; таблица в сессии — прежние `NI, ат.%` |
| `test_concentration_csv_al` (AppTest) | CSV и лист Excel «Изменение состава» al — `Cu, атомные %`; таблица — `CU, атомные %` |
| `test_precipitation_excel_ni` (AppTest) | Excel выделений ni — `Al, матрица, ат.%`, `Ni, матрица, ат.%`, межфазные `Al, …`; таблица результата не меняется |
| `test_solidification_zip_and_raw_sheets_ni` (AppTest, `slow`) | листы raw = столбцы `raw_tables`; «… расплав» и члены ZIP — `Ni, ат.%` |
| `test_batch_export_ni` (AppTest, `slow`) | пакет ni: «Составы фаз ат/мас» — Ni/Al; «Сводка», «Фазовые доли», «Исходные данные» — как таблицы; таблицы после записи прежние |

`11 passed` отдельно (после двух правок самих тестов: три списка «Изменяемый элемент» на странице; кнопки Excel выделений — в виде «Экспорт и ограничения») и `11 passed, 1 warning in 196.62s` в регрессии.

### Полная регрессия

`results/wave21_o/scripts/run_regressiya.sh` (копия 21-М: изменены только папка вывода `results/wave21_o/testy` и состояние `tg21o_tests_state`, строка заголовка). Один поток, 11:09–13:17; `test_ui_f` — одним процессом (свободно 7.53 ГиБ), журнал памяти — `results/wave21_o/testy/memlog_test_ui_f.jsonl`.

| Файл | Итог |
|---|---|
| `test_backend_calculations` | 57 passed, 6 warnings in 1201.43s |
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
| `test_ui_f` | 59 passed in 1989.05s |
| `test_ui_g` | 32 passed, 5 warnings in 405.19s |
| `test_ui_h` | 26 passed |
| `test_user_errors_21zh` | 47 passed |
| `test_version_consistency` | 92 passed |
| `test_wave15_z` | 15 passed, 2 warnings |
| `test_wave21_m` | 22 passed |
| `test_wave21_o` | 11 passed, 1 warning |
| 12 файлов unittest (`thermogar_active_state_io`, `db_cache`, `fe_internal_smoke`, `paths`, `restricted_fe_core`, `secure_io`, `state_migration`, `verified_equilibrium`, `verified_loaders`, `verified_physical`, `verified_properties`, `verified_state`) | Ran 203 tests / OK |
| 7 сценариев (`converter_patch`, `diffusion`, `fe_database`, `physical`, `precipitation`, `properties`, `self_test`) | RESULT: PASSED (`thermogar_precipitation_test` — Final volume fraction 6.599577401641879 %) |

Сумма: 34 файла pytest — 794 passed, 1 xfailed (в 21-М — 774 и 1 xfailed; плюс 9 `test_kwn_step_cap_22b` из 22-Б и 11 новых). 12 файлов unittest — 203 OK. 7 сценариев — PASSED. Красных — 0.

## ШАГ 7. Кадры и замеры

Коммит `1fb4cb6`. Скрипты 21-М скопированы в `results/wave21_o/scripts/`: `kadry.py`, `formy.py`, `run_app.cmd` — изменены только папка `results/wave21_o`, состояние `tg21o_state` и порт 8651 (помечено в заголовках). Новые: `kadry_21o.py` (случаи ниже; приложение перезапускается перед каждым), `vygruzki_12b.py` (заголовки выгрузок через AppTest), `tzero_sverka.py` (ШАГ 3). Окно 1440×900; светлая тема — сеанс по умолчанию, тёмная — `?embed_options=dark_theme`. Кадры — `results/wave21_o/kadry/` (18, у каждого случая две части `_ch1`, `_ch2`); записи — `results/wave21_o/kadry_21o.json`; таблица — `results/wave21_o/zamery.csv` (UTF-8 с BOM, «;», 67 строк). Числа выделений — из выгруженного Excel («Кинетика», последняя строка).

| Случай | Тема | Время, с | Строк | Доля, % | R, нм | Остановка | Мастер / было |
|---|---|---|---|---|---|---|---|
| fe, ячейка `test_ui_g[fe]` (40 классов, 0.001 ч) | светлая | 59.6 | 1601 | 4.4095 | 9.517 | нет, проверки пройдены | Linux: 1470 строк, 4.4095 %, 9.519 нм |
| fe по умолчанию (0.01 ч на экране, 80 классов) | светлая | 299.2 | 9881 | 4.4104 | 12.142 | нет | Linux: 4.4104 %, 12.14 нм, 254 с |
| ni по умолчанию (100 ч) | светлая | 176.5 | 10 314 | 26.0338 | 92.256 | нет | 21-Л: 26.00 %, 92.3 нм, 315 с; 22-Б Linux: 26.0335 %, 92.187 нм, 10 605 строк |
| al по умолчанию (24 ч) | светлая | 16.8 | 407 | 0.0000 | 0.000 | нет | 21-Л: выделений нет |
| 718 (ni, основа Fe, 700 °C, 100 ч, 200 классов) | светлая / тёмная | 25.5 / 25.3 | 237 | 4.9657 | 0.514 | 4.130 с по Ti | Linux: 4.153 с по Ti |

Текст над видами у 718 (обе темы, и в таблице проверок): «Расчёт остановлен на 4.13 с модельного времени (0.001147 ч): доля Ti в матрице ушла ниже нуля, баланс масс нарушен. Показана часть расчёта до остановки. Причина: при движущей силе по базе зарождение практически безбарьерное, и выделение вычерпывает добавки из матрицы быстрее, чем модель это выдерживает.» Входы 718 в «Параметрах» Excel — дословно задания (Vm 7.145624 и 7.3, N0 8.4277e+28, сетка 0.1–50 нм × 200).

| T₀ стали | Тема | Окно на экране | Время, с | Строк | Найдено | Пустой состав | Счётчик |
|---|---|---|---|---|---|---|---|
| по умолчанию | светлая / тёмная | 200 / 950 | 13.4 / 13.6 | 21 | 18 | 0 | «T₀ найдено в 18 точках из 21. …» |
| окно 300–1700 °C | светлая | 300 / 1700 | 41.6 | 21 | 15 | 0 | «T₀ найдено в 15 точках из 21. …» |

Заголовки выгрузок 12Б, шесть видов (`results/wave21_o/data/vygruzki_12b.csv`, 15 строк): Excel «Одна температура» ni, CSV «Изменение состава» al, ZIP затвердевания ni (2 члена CSV, 2 листа «расплав», 2 листа raw), T₀ ni, выделения ni (2 листа), пакет ni (3 листа) — таблица ШАГА 5.

## Отступления

1. `tools/test_ui_g.py`: константы `COMPOSITION_CHECK` и `QUALITY_FAILED_ERROR` (`:61–62`) после ШАГА 2 больше не используются; оставлены, чтобы не трогать лишнего.
2. Справка KWN fe на Windows — 1123 строки, на Linux 22-Б — 1249 (прежде 2391 на Windows, 2496 на Linux). Задание даёт числа Linux «для сверки»; СТОП на расхождение не предусмотрен, в справку записано число ноутбука. Так же ячейка `test_ui_g[fe]`: 1601 строка против 1470 на Linux, доля 4.4095 % совпала; ni 100 ч — 10 314 строк против 10 605, доля 26.0338 % против 26.0335 %.
3. 718 остановился на 4.130 с, на Linux — 4.153 с (разница 0.023 с); элемент (Ti) и текст — ожидаемые.
4. Прогон `test_ui_g::test_kwn_precipitation` ШАГА 2 шёл на рабочем дереве, где уже были незакоммиченные правки ШАГОВ 3 и 4 (T₀ и умолчание/текст «Выделений»); ячейка задаёт время выдержки сама и текст остановки не задевает. Полная регрессия ШАГА 6 — на итоговом коде.
5. `run_regressiya.sh` в рабочем дереве — с концами строк CRLF (как у 21-М); запускался `bash -o igncr`.
6. Скрипт кадров: «Классов размеров» — ползунок `st.slider`, задаётся клавишами на его бегунке; список основ в боковой панели показывает «Fe» (21-Ж), а не «FE», как в сценарии 17-Д; в случае 718 список «Фаза-выделение» не раскрывался щелчком — вариант вводится в поле. Два отладочных кадра (`_dbg_718.png`, `_dbg_718b.png`) перенесены в `_to_delete/21o_dbg/`, опись sha256 — `_to_delete/21o_dbg/opis_sha256.txt`.
7. `tools/test_wave21_o.py` берёт фикстуры пакетного расчёта (`app`, `patched_app_source`) и помощников из `tools/test_ui_h.py` импортом, а не копией.
8. Журналы прогонов (`*.log`) — на ноутбуке (`.gitignore`), как в 21-И и 21-М; в ветку вошли `memlog_test_ui_f.jsonl`, `_run_stdout.txt` и JSON справки KWN.

## Git

Коммиты на `wave21-o`: `5c18016` задание, `6d519f3` реестр, `c1577ca` ШАГ 2, `ab5d459` ШАГ 3, `60e67e0` ШАГ 4, `466299d` ШАГ 5, `7f04aef` ШАГ 6, `1fb4cb6` ШАГ 7, далее — отчёт и строка 21-О в реестре.

`git push -u origin wave21-o` — `* [new branch]      wave21-o -> wave21-o`.

`git ls-remote origin main wave21-o` (после пуша отчёта с выводом ниже `wave21-o` на один коммит новее):

```
a68a41704f4db6053d8c073c96c30938251be930	refs/heads/main
5219e33a7fa0ab578dc0ce2d3471db2274068bc1	refs/heads/wave21-o
```

`git log --oneline a68a417..wave21-o`:

```
5219e33 docs(21-О): отчёт, строка 21-О в реестре, BL-43 и BL-66
1fb4cb6 docs(21-О): кадры и замеры — выделения fe/ni/al/718, T₀ стали, заголовки выгрузок 12Б
7f04aef test(21-О): тесты решений по стали и 12Б, полная регрессия
466299d feat(21-О): символы элементов в заголовках выгрузок Excel и CSV (12Б), 7 вызовов
60e67e0 feat(21-О): «Выделения» — выдержка стали 0.01 ч (1Б), «ушла ниже нуля» в тексте остановки (3В)
ab5d459 fix(21-О): T₀ — состав из заданной сетки (BL-66), окно стали 200–950 °C (2В)
c1577ca test(21-О): ячейка KWN fe без остановки после 22-Б; справка KWN по прогону ноутбука
6d519f3 docs(21-О): реестр — приёмки 21-М, 21-Н, 22-А/22-А2, 22-Б, решения владельца по стали, BL-68, BL-69
5c18016 docs(21-О): задание
```

`git status --short`:

```
?? _to_delete/
```
