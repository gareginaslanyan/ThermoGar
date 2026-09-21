# Ревью структуры кода ThermoGar

Дата: 21.09.2026. Репозиторий `D:\Pets\ThermoGar`, ветка `main`, коммит `22ddf20`
(`docs(16): закрытие волны 16 — S-8 сверен байтами, ответ и письмо «Лилит»`) — головной
на момент обхода. Область: `app/` — разбор; `tools/`, `scripts/`, `packaging/` — только
замер. Каталог `D:\Pets\Lilith` не открывался. Код не менялся, файлы не удалялись,
коммитов нет, этот файл оставлен неотслеживаемым.

Предыдущее ревью `tasks/REVIEW_JEV_21_09_2026.md` прочитано. Его вывод — «применять Jev
в работающей программе нельзя ни на одном пути» (`tasks/REVIEW_JEV_21_09_2026.md:64-65`) —
принят и здесь не пересматривается. В этой работе Jev — инструмент разработчика:
он отвечал на вопросы о коде на моей машине, в поставку ничего из его ответов не идёт.

Инструменты замера (`radon`, `pylint`) поставлены во временный каталог сессии через
`pip install --target`; ни `.venv-windows`, ни окружение проекта не менялись.

---

## 1. Замер

### 1.1. Объём

| Область | Файлов `.py`/`.pyw` | Строк |
|---|---|---|
| `app/` | 28 | 39 230 |
| `tools/` | 65 | 44 124 |
| `scripts/` | 10 | 4 588 |
| `packaging/` | 3 | 2 625 |

`app/ThermoGar_app.py` — 12 180 строк. Внутри тел `def`/`class` — 5 835 строк,
на уровне модуля — 6 345. Определений верхнего уровня: 139 функций и классов
(158 функций с вложенными), 68 присваиваний-имён. Импортов на верхнем уровне — 47
(53 с вложенными внутри функций).

### 1.2. `radon cc -s app/` — распределение рангов

1 081 блок (классы, функции, методы), средняя сложность **B (5,71)**.

| Ранг | Блоков |
|---|---|
| A | 739 |
| B | 177 |
| C | 122 |
| D | 24 |
| E | 9 |
| F | 10 |

Совпадает с замером мастера до блока.

### 1.3. Ранги D, E, F поимённо

Строка — начало блока, как его печатает `radon`. `C` — класс, `F` — функция, `M` — метод.

| # | Файл:строка | Блок | Тип | Ранг (cc) |
|---|---|---|---|---|
| 1 | `app/thermogar_physical.py:1278` | `calculate_physical_properties` | F | **F (71)** |
| 2 | `app/thermogar_fe_equilibrium_worker.py:812` | `_normalize_dataset` | F | **F (58)** |
| 3 | `app/thermogar_restricted_fe_core.py:117` | `RestrictedFeRequest` | C | **F (51)** |
| 4 | `app/thermogar_stage14.py:106` | `_friendly_error_text` | F | **F (51)** |
| 5 | `app/thermogar_restricted_fe_core.py:128` | `RestrictedFeRequest.__post_init__` | M | **F (50)** |
| 6 | `app/thermogar_physical.py:995` | `PhysicalDensityDatabase.density_from_site_fractions` | M | **F (48)** |
| 7 | `app/thermogar_workspace.py:435` | `validate_context_payload` | F | **F (48)** |
| 8 | `app/thermogar_precipitation.py:988` | `run_precipitation` | F | **F (42)** |
| 9 | `app/ThermoGar_app.py:5538` | `translate_phase_description` | F | **F (42)** |
| 10 | `app/thermogar_fe_equilibrium_worker.py:566` | `_validate_request` | F | **F (41)** |
| 11 | `app/thermogar_physical.py:1915` | `_site_fractions_from_composition` | F | E (40) |
| 12 | `app/thermogar_precipitation.py:1300` | `render_precipitation_section` | F | E (39) |
| 13 | `app/thermogar_workspace.py:1622` | `render_projects_and_history` | F | E (36) |
| 14 | `app/thermogar_fe_equilibrium_worker.py:994` | `_execute_request` | F | E (36) |
| 15 | `app/thermogar_verified_equilibrium.py:292` | `_default_backend` | F | E (34) |
| 16 | `app/thermogar_workspace.py:2228` | `run_batch_calculations` | F | E (34) |
| 17 | `app/thermogar_verified_physical.py:557` | `execute_verified_physical` | F | E (34) |
| 18 | `app/thermogar_restricted_fe_core.py:862` | `execute_bound_restricted_fe` | F | E (33) |
| 19 | `app/thermogar_properties.py:573` | `vrh_homogenization` | F | E (32) |
| 20 | `app/thermogar_restricted_fe_core.py:297` | `RestrictedFeReceipt` | C | D (30) |
| 21 | `app/thermogar_verified_properties.py:1139` | `execute_verified_properties` | F | D (30) |
| 22 | `app/thermogar_restricted_fe_core.py:312` | `RestrictedFeReceipt.__post_init__` | M | D (29) |
| 23 | `app/thermogar_verified_loaders.py:1608` | `FeatureReceipt.__post_init__` | M | D (29) |
| 24 | `app/thermogar_equilibrium_core.py:558` | `find_monotonic_linear_crossings` | F | D (27) |
| 25 | `app/thermogar_physical.py:703` | `PhysicalDensityDatabase.element_density_model` | M | D (26) |
| 26 | `app/ThermoGar_app.py:2037` | `render_b4b2_elastic_properties` | F | D (25) |
| 27 | `app/ThermoGar_app.py:3420` | `batch_engine_runner` | F | D (25) |
| 28 | `app/thermogar_verified_properties.py:472` | `_default_backend` | F | D (25) |
| 29 | `app/thermogar_database_repair.py:318` | `repair_mobility_defaults` | F | D (24) |
| 30 | `app/thermogar_verified_equilibrium.py:460` | `execute_verified_equilibrium` | F | D (24) |
| 31 | `app/thermogar_parallel.py:772` | `ParallelEquilibrium.map_points` | M | D (24) |
| 32 | `app/thermogar_verified_physical.py:83` | `make_physical_inputs` | F | D (24) |
| 33 | `app/thermogar_diffusion.py:1356` | `render_kinetics_section` | F | D (23) |
| 34 | `app/thermogar_secure_io.py:598` | `_atomic_replace_locked` | F | D (23) |
| 35 | `app/thermogar_workspace.py:2445` | `render_batch_calculation` | F | D (22) |
| 36 | `app/thermogar_secure_io.py:381` | `held_verified_snapshot` | F | D (22) |
| 37 | `app/thermogar_verified_properties.py:1063` | `_strengthening_inputs` | F | D (22) |
| 38 | `app/thermogar_verified_loaders.py:977` | `bind_selected_database` | F | D (22) |
| 39 | `app/thermogar_diffusion.py:765` | `_run_model` | F | D (21) |
| 40 | `app/ThermoGar_app.py:1735` | `render_b4b_density_temperature` | F | D (21) |
| 41 | `app/thermogar_verified_loaders.py:1214` | `prepare_feature_request` | F | D (21) |
| 42 | `app/thermogar_secure_io.py:839` | `secure_move_no_overwrite` | F | D (21) |
| 43 | `app/thermogar_verified_equilibrium.py:105` | `make_equilibrium_inputs` | F | D (21) |

43 строки = 24 D + 9 E + 10 F.

### 1.4. `radon mi -s app/` по файлам

| Файл | Ранг MI | MI |
|---|---|---|
| `app/ThermoGar_app.py` | C | 0,00 |
| `app/thermogar_fe_equilibrium_worker.py` | C | 0,00 |
| `app/thermogar_physical.py` | C | 0,00 |
| `app/thermogar_precipitation.py` | C | 0,00 |
| `app/thermogar_properties.py` | C | 0,00 |
| `app/thermogar_restricted_fe_core.py` | C | 0,00 |
| `app/thermogar_secure_io.py` | C | 0,00 |
| `app/thermogar_verified_loaders.py` | C | 0,00 |
| `app/thermogar_verified_properties.py` | C | 0,00 |
| `app/thermogar_verified_state.py` | C | 0,00 |
| `app/thermogar_workspace.py` | C | 0,00 |
| `app/thermogar_equilibrium_core.py` | C | 0,05 |
| `app/thermogar_verified_equilibrium.py` | C | 4,53 |
| `app/thermogar_diffusion.py` | C | 6,06 |
| `app/thermogar_stage14.py` | C | 6,62 |
| `app/thermogar_verified_physical.py` | B | 12,45 |
| `app/thermogar_paths.py` | B | 14,94 |
| `app/thermogar_parallel.py` | A | 24,73 |
| `app/thermogar_database_repair.py` | A | 27,63 |
| `app/thermogar_numerical_grid.py` | A | 28,93 |
| `app/thermogar_database_guard.py` | A | 30,46 |
| `app/thermogar_release_policy.py` | A | 45,92 |
| `app/thermogar_verified_artifact.py` | A | 49,51 |
| `app/thermogar_parallel_ui.py` | A | 51,41 |
| `app/thermogar_db_cache.py` | A | 64,26 |
| `app/thermogar_release_ui.py` | A | 65,70 |
| `app/ThermoGar_unified_app.py` | A | 74,17 |
| `app/thermogar_palette.py` | A | 79,05 |

Одиннадцать файлов стоят на нуле MI. Ноль — это пол шкалы `radon` (значение
обрезается снизу), а не «в 11 файлах одинаковая поддерживаемость»: он говорит
только, что показатель вышел за нижнюю границу. Различать эти файлы по MI нельзя;
для них работает `cc` и длина.

### 1.5. Функции длиннее 100 строк

Все `app/`, по убыванию длины. Длина = `end_lineno − lineno + 1` по AST.

| # | Строк | Файл:строки | Функция | Ранг cc |
|---|---|---|---|---|
| 1 | 428 | `app/thermogar_physical.py:1278-1705` | `calculate_physical_properties` | F (71) |
| 2 | 417 | `app/thermogar_workspace.py:1622-2038` | `render_projects_and_history` | E (36) |
| 3 | 415 | `app/thermogar_properties.py:1769-2183` | `render_strengthening_section` | C (20) |
| 4 | 359 | `app/thermogar_precipitation.py:1300-1658` | `render_precipitation_section` | E (39) |
| 5 | 337 | `app/thermogar_diffusion.py:1356-1692` | `render_kinetics_section` | D (23) |
| 6 | 315 | `app/thermogar_properties.py:1452-1766` | `render_elastic_section` | C (11) |
| 7 | 291 | `app/thermogar_precipitation.py:988-1278` | `run_precipitation` | F (42) |
| 8 | 278 | `app/ThermoGar_app.py:6012-6289` | `plot_ternary_thermogar` | C (19) |
| 9 | 268 | `app/thermogar_diffusion.py:765-1032` | `_run_model` | D (21) |
| 10 | 236 | `app/thermogar_workspace.py:1081-1316` | `render_alloy_library` | C (18) |
| 11 | 231 | `app/ThermoGar_app.py:6574-6804` | `plot_ternary_phase_fraction_map` | B (9) |
| 12 | 226 | `app/thermogar_verified_properties.py:1139-1364` | `execute_verified_properties` | D (30) |
| 13 | 215 | `app/thermogar_workspace.py:2228-2442` | `run_batch_calculations` | E (34) |
| 14 | 214 | `app/thermogar_properties.py:941-1154` | `calculate_strengthening` | C (14) |
| 15 | 209 | `app/thermogar_restricted_fe_core.py:862-1070` | `execute_bound_restricted_fe` | E (33) |
| 16 | 205 | `app/thermogar_stage14.py:106-310` | `_friendly_error_text` | F (51) |
| 17 | 204 | `app/ThermoGar_app.py:2037-2240` | `render_b4b2_elastic_properties` | D (25) |
| 18 | 196 | `app/ThermoGar_app.py:1735-1930` | `render_b4b_density_temperature` | D (21) |
| 19 | 195 | `app/thermogar_physical.py:995-1189` | `PhysicalDensityDatabase.density_from_site_fractions` | F (48) |
| 20 | 192 | `app/thermogar_properties.py:573-764` | `vrh_homogenization` | E (32) |
| 21 | 190 | `app/thermogar_workspace.py:2445-2634` | `render_batch_calculation` | D (22) |
| 22 | 187 | `app/thermogar_fe_equilibrium_worker.py:994-1180` | `_execute_request` | E (36) |
| 23 | 187 | `app/thermogar_verified_physical.py:557-743` | `execute_verified_physical` | E (34) |
| 24 | 183 | `app/ThermoGar_app.py:2686-2868` | `phase_selection_editor` | C (13) |
| 25 | 163 | `app/thermogar_fe_equilibrium_worker.py:812-974` | `_normalize_dataset` | F (58) |
| 26 | 161 | `app/ThermoGar_app.py:2243-2403` | `render_b4b2_strengthening` | C (19) |
| 27 | 158 | `app/ThermoGar_app.py:1575-1732` | `render_b4b_density_single` | C (16) |
| 28 | 155 | `app/thermogar_workspace.py:435-589` | `validate_context_payload` | F (48) |
| 29 | 152 | `app/ThermoGar_app.py:5220-5371` | `plot_binary_thermogar` | C (16) |
| 30 | 152 | `app/ThermoGar_app.py:5763-5914` | `plot_isopleth_thermogar` | C (15) |
| 31 | 151 | `app/thermogar_database_repair.py:318-468` | `repair_mobility_defaults` | D (24) |
| 32 | 151 | `app/thermogar_paths.py:709-859` | `migrate_legacy_state` | C (15) |
| 33 | 145 | `app/thermogar_paths.py:562-706` | `_legacy_candidates` | C (12) |
| 34 | 143 | `app/thermogar_stage14.py:463-605` | `validate_single_equilibrium` | C (15) |
| 35 | 142 | `app/ThermoGar_app.py:3420-3561` | `batch_engine_runner` | D (25) |
| 36 | 137 | `app/ThermoGar_app.py:4078-4214` | `tzero_path_table` | C (19) |
| 37 | 133 | `app/ThermoGar_app.py:6439-6571` | `calculate_ternary_phase_fraction_map` | B (10) |
| 38 | 133 | `app/thermogar_verified_equilibrium.py:460-592` | `execute_verified_equilibrium` | D (24) |
| 39 | 132 | `app/ThermoGar_app.py:5538-5669` | `translate_phase_description` | F (42) |
| 40 | 127 | `app/thermogar_properties.py:1256-1382` | `_calculate_elastic_from_editor` | C (17) |
| 41 | 125 | `app/thermogar_database_guard.py:456-580` | `passport_dataframe` | C (20) |
| 42 | 122 | `app/thermogar_stage14.py:1181-1302` | `render_diagnostics` | C (16) |
| 43 | 118 | `app/thermogar_diffusion.py:1236-1353` | `_common_inputs` | B (7) |
| 44 | 118 | `app/thermogar_fe_equilibrium_worker.py:566-683` | `_validate_request` | F (41) |
| 45 | 117 | `app/thermogar_stage14.py:608-724` | `validate_phase_scan` | C (11) |
| 46 | 116 | `app/thermogar_physical.py:1915-2030` | `_site_fractions_from_composition` | E (40) |
| 47 | 110 | `app/thermogar_verified_loaders.py:1214-1323` | `prepare_feature_request` | D (21) |
| 48 | 106 | `app/thermogar_diffusion.py:1128-1233` | `_result_display` | C (11) |
| 49 | 104 | `app/thermogar_restricted_fe_core.py:621-724` | `execute_restricted_fe` | C (18) |
| 50 | 104 | `app/thermogar_stage14.py:1005-1108` | `run_smoke_tests` | B (10) |
| 51 | 102 | `app/thermogar_stage14.py:727-828` | `validate_solidification_paths` | B (9) |
| 52 | 101 | `app/ThermoGar_app.py:3131-3231` | `summarize_equilibrium` | C (12) |

Итого 52. Из них в `ThermoGar_app.py` — 14; длиннее 200 строк во всём `app/` — 17,
длиннее 300 — 6, и в `ThermoGar_app.py` таких нет ни одной.

### 1.6. Карта модуля `app/ThermoGar_app.py`

Разбито по верхним элементам файла, подряд, без пропусков.

| Строки | Строк | Что это |
|---|---|---|
| 1-46 | 46 | Модульная строка документации |
| 48-81 | 34 | Импорты (первая группа), плюс `THERMOGAR_PATHS` и правка `sys.path` |
| 87-136 | 50 | `_SCHEIL_STATE` и две функции ленивой загрузки Scheil |
| 138-236 | 99 | Импорты (вторая группа, 20 операторов) |
| 238-246 | 9 | Псевдонимы функций Fe-контура, `render_friendly_error` |
| 253-273 | 21 | `DISPLAY_APP_NAME`, `st.set_page_config`, проверка `client.disableDataExport` |
| **275-587** | **313** | **Константы и умолчания вкладок** (`DATABASE_DEFINITIONS`, `FE_PROFILE_*`, `SOLIDIFICATION_DEFAULTS`, `ENERGY_DEFAULTS`, `PHASE_EXPLANATIONS`, `BINARY_DIAGRAM_DEFAULTS`, `ISOPLETH_DEFAULTS`, `TERNARY_DIAGRAM_DEFAULTS`, `TERNARY_PHASE_MAP_DEFAULTS`) |
| 594-655 | 62 | Корень проекта, стиль, кэш снимков баз — определения |
| **658-983** | **326** | **Определения:** загрузка и кэш баз, 17 функций |
| 986-1213 | 228 | Класс `VerifiedB3BatchBroker` |
| 1216-1322 | 107 | Физическая база: загрузка, тексты-константы галочки поправок |
| **1325-2602** | **1 278** | **Определения:** физический контур B4B/B4B2, 26 функций |
| 2605-2925 | 321 | «Непостроимые» фазы: ключ состояния и 9 функций |
| 2928-4439 | 1 512 | Атрибуция баз, 38 функций общего назначения (расчёт, выгрузка, графики) |
| 4444-4618 | 175 | Пороги ликвидуса и 4 функции поиска ликвидуса |
| 4623-5513 | 891 | Пороги солидуса (BL-44) и 22 функции солидуса и затвердевания |
| 5517-5535 | 19 | `EXACT_DESCRIPTION_TRANSLATIONS` |
| **5538-6804** | **1 267** | **Определения:** описания фаз, справочник, бинарные и тройные диаграммы, 13 функций |
| 6813-7158 | 346 | **Исполняемая разметка: заголовок и боковая панель** — выбор базы, режим стали, основа, единицы, состав, давление, `CURRENT_CONTEXT` |
| 7165-7183 | 19 | `st.tabs(...)` — семь вкладок верхнего уровня |
| 7185-7192 | 8 | `with calculation_tab:` — три подвкладки |
| **7199-7488** | **290** | **Вкладка «Расчёты» → «Одна температура»** |
| **7495-7801** | **307** | **Вкладка «Расчёты» → «Температурный диапазон»** |
| **7808-8158** | **351** | **Вкладка «Расчёты» → «Изменение состава»** |
| **8165-9919** | **1 755** | **Вкладка «Диаграммы»** (подвкладки: бинарная, многокомпонентная, тройная, карта доли фазы) |
| **9927-10666** | **740** | **Вкладка «Затвердевание»** |
| **10673-11403** | **731** | **Вкладка «Энергии»** (подвкладки: кривые энергии, движущая сила, T0) |
| **11411-11519** | **109** | **Вкладка «Свойства»** |
| **11526-11553** | **28** | **Вкладка «Кинетика»** (две подвкладки, обе рисуются чужими модулями) |
| 11560-11768 | 209 | `USER_GUIDE_MD` — текст руководства одной строковой константой |
| 11771 | 1 | `workspace_broker` |
| **11774-12180** | **407** | **Вкладка «Проекты и данные»** |

Исполняемая разметка вкладок — 4 726 строк (7 185–11 553 и 11 774–12 180), боковая
панель и заголовок — 346 строк.

Внутри вкладок:

| Вкладка | Строки | Всего | Строковые литералы | Комментарии | Пустые | Остальной код |
|---|---|---|---|---|---|---|
| «Одна температура» | 7199-7488 | 290 | 76 | 5 | 11 | 198 |
| «Температурный диапазон» | 7495-7801 | 307 | 87 | 3 | 16 | 201 |
| «Изменение состава» | 7808-8158 | 351 | 91 | 2 | 21 | 237 |
| «Диаграммы» | 8165-9919 | 1 755 | 556 | 3 | 122 | 1 074 |
| «Затвердевание» | 9927-10666 | 740 | 248 | 13 | 26 | 453 |
| «Энергии» | 10673-11403 | 731 | 283 | 0 | 38 | 410 |
| «Свойства» | 11411-11519 | 109 | 18 | 0 | 8 | 83 |
| «Кинетика» | 11526-11553 | 28 | 3 | 0 | 0 | 25 |
| «Проекты и данные» | 11774-12180 | 407 | 219 | 0 | 30 | 158 |

Тексты в файле: строковых литералов — 3 771 строка на файл, из них 2 251 вне тел
функций. Литеральных констант верхнего уровня — 564 строки в 37 присваиваниях;
крупнейшие: `USER_GUIDE_MD` 209 (`app/ThermoGar_app.py:11560-11768`),
`PHASE_EXPLANATIONS` 48 (`:404-451`), `DATABASE_DEFINITIONS` 46 (`:275-320`),
`ENERGY_DEFAULTS` 41 (`:362-402`), `BINARY_DIAGRAM_DEFAULTS` 35 (`:454-488`),
`ISOPLETH_DEFAULTS` 32 (`:494-525`), `TERNARY_PHASE_MAP_DEFAULTS` 32 (`:556-587`),
`TERNARY_DIAGRAM_DEFAULTS` 26 (`:528-553`), `EXACT_DESCRIPTION_TRANSLATIONS` 19 (`:5517-5535`).

### 1.7. Связность вкладок: что с какой вкладкой уедет

Посчитано по AST: от тела каждой вкладки взяты все имена верхнего уровня, затем
транзитивно — имена, которые они используют.

| Вкладка | Строк во вкладке | Имён нужно (транзитивно) | Из них только у неё | Строк в этих именах |
|---|---|---|---|---|
| «Диаграммы» | 1 755 | 65 | 19 | 1 417 |
| «Свойства» | 109 | 63 | 33 | 1 171 |
| «Проекты и данные» | 407 | 62 | 18 | 932 |
| «Затвердевание» | 740 | 86 | 35 | 915 |
| «Энергии» | 731 | 53 | 11 | 563 |
| «Изменение состава» | 351 | 60 | 2 | 53 |
| «Одна температура» | 290 | 52 | 1 | 39 |
| «Температурный диапазон» | 307 | 59 | 0 | 0 |
| «Кинетика» | 28 | 21 | 0 | 0 |

Имён, нужных больше чем одной вкладке, — 65, в них 1 221 строка. Это и есть будущий
общий модуль. Вот они:

`CURRENT_CONTEXT`, `DATABASE_DEFINITIONS`, `FE_PROFILE_SHA256`, `PHASE_EXPLANATIONS`,
`PROJECT_ROOT`, `THERMOGAR_PATHS`, `UNBUILDABLE_PHASES_STATE_KEY`, `_TDB_PHASE_DECLARATION`,
`_remember_unbuildable_phases`, `_verified_tdb_declared_phases`, `acquire_b3_execution`,
`aggregate_phase_fractions`, `available_elements`, `available_phase_presets`, `balance`,
`balance_key`, `build_input`, `compatible_phases_for_components`, `composition_key`,
`composition_text`, `current_theme_type`, `database_key`, `database_key_from_settings`,
`dataframe_to_excel`, `definition`, `direct_equilibrium_scan`, `drop_unbuildable_order_disorder`,
`excluded_phase_message`, `fe_profile_key`, `figure_to_png`, `filter_for_mode`,
`find_project_root`, `mole_fraction_map`, `mole_to_mass`, `normalize`, `parse_composition`,
`phase_candidates_for_standard_composition`, `phase_model_note`, `phase_selection_editor`,
`plot_phase_fraction_scan`, `prepare_calculation`, `pressure_pa`, `rejected_release_phases`,
`release_exclusion_note`, `render_engine_note`, `render_friendly_error`,
`render_phase_set_note`, `render_release_exclusion_note`, `requested_phase_tuple`,
`require_successful_points`, `run_equilibrium_points`, `scheil_available`, `steel_mode`,
`style_chart_axes`, `summarize_equilibrium`, `unbuildable_order_disorder`,
`unbuildable_phase_note`, `units`, `units_key`, `units_label`, `units_options`,
`verified_b3_candidate_phases`, `verified_b3_refresh_result`, `verified_b3_store_result`,
`vlb_active_context`.

Среди них девять — не функции, а **переменные боковой панели**: `database_key`
(`app/ThermoGar_app.py:6846`), `balance` (`:7026`), `units` и `units_label` (`:7038-7045`),
`composition_text` (`:7050`), `pressure_pa` (`:7061`), `steel_mode` (`:6975`),
`available_elements` (`:6959`), `CURRENT_CONTEXT` (`:7074`). Вкладки читают их как
глобальные. Любой разрез по вкладкам упирается в это первым: пока они глобальные,
вынесенная вкладка их не увидит.

### 1.8. Мёртвый код в `ThermoGar_app.py`

Девять функций определены и ни разу не вызваны ни в `app/`, ни в `tools/`,
`scripts/`, `packaging/` — единственное вхождение имени это её собственный `def`:

| Функция | Строки | Строк |
|---|---|---|
| `restricted_fe_calculation_button` | `app/ThermoGar_app.py:752-763` | 12 |
| `restricted_fe_refresh_session_result` | `:766-780` | 15 |
| `restricted_fe_b2_fingerprint` | `:812-826` | 15 |
| `restricted_fe_prepare_b2_decision` | `:829-849` | 21 |
| `restricted_fe_store_result` | `:852-877` | 26 |
| `restricted_fe_result_dataframe` | `:880-894` | 15 |
| `_legacy_b2_single_equilibrium_oracle` | `:3567-3568` | 2 |
| `_legacy_b2_temperature_equilibrium_oracle` | `:3571-3572` | 2 |
| `_legacy_b2_composition_equilibrium_oracle` | `:3575-3576` | 2 |

Итого 110 строк. Это запись для сведения: ничего не удалено.

### 1.9. `pylint duplicate-code`

`pylint --disable=all --enable=duplicate-code --min-similarity-lines=12 app/` —
**0 срабатываний**, оценка 10,00/10. Совпадает с замером мастера.

### 1.10. `tools/`, `scripts/`, `packaging/` — только замер

`radon cc -s` по трём каталогам: 1 674 блока, средняя сложность **A (4,44)**;
A 1 273, B 269, C 101, D 20, E 7, F 4. Тестовых функций (`def test_…`) в `tools/` — 473
в 41 файле.

### 1.11. Расхождения с замером мастера

| Величина мастера | Замер здесь | Вердикт |
|---|---|---|
| `app/` 39 230 строк | 39 230 | совпало |
| `ThermoGar_app.py` 12 180 строк | 12 180 | совпало |
| 158 функций | 158 (с вложенными; 139 на верхнем уровне) | совпало |
| 47 импортов | 47 операторов импорта на верхнем уровне (53 со вложенными) | совпало |
| `radon cc`: A 739, B 177, C 122, D 24, E 9, F 10 | то же | совпало |
| `pylint duplicate-code ≥ 12` = 0 | 0 | совпало |
| длины шести функций > 300 строк | все шесть совпали до строки | совпало |
| **6 346 строк на уровне модуля** | **6 345** | расхождение 1 строка |
| **20 файлов `tools/` импортируют из него** | 20 файлов **упоминают** его, импортирует **ни один** | расхождение по существу |
| **«функций > 100 строк — 52, > 300 — 6»** — в контексте абзаца про `ThermoGar_app.py` | это цифры по всему `app/`; в самом `ThermoGar_app.py` — 14 и **0** | расхождение по области |
| **«самые тяжёлые»: шесть функций F** | F-блоков десять, и список мастера пропускает три самых тяжёлых | расхождение по существу |

Разбор трёх существенных расхождений.

**1. 6 346 против 6 345.** Разница в том, куда отнести строки декораторов.
Если строка `@st.cache_data` считается принадлежащей определению, тел `def`/`class` —
5 835 строк, на уровне модуля остаётся 6 345. Если декоратор считать строкой уровня
модуля, получается ровно 6 346. В файле ровно одна такая строка на верхнем уровне — декоратор
`_load_physical_database_cached` (`app/ThermoGar_app.py:1221`).
Расхождение методическое, а не фактическое.

**2. «20 файлов `tools/` импортируют из него».** Оператора `import ThermoGar_app`
или `from ThermoGar_app import …` нет ни в одном файле `tools/`, `scripts/`,
`packaging/` и `app/` — поиск по всем четырём каталогам даёт ноль. Модуль —
верхнеуровневый сценарий Streamlit, импортировать его нельзя, и это записано в самом
проекте (`tools/test_backend_calculations.py:15`: «`app/ThermoGar_app.py` itself is a top-level
Streamlit script and cannot be imported»).
Имя `ThermoGar_app` действительно встречается в 20 файлах `tools/`, но связь другая
и для разреза она важнее импорта:

* **7 файлов** гоняют файл через `AppTest.from_file(…)`, то есть держат путь
  `app/ThermoGar_app.py` строкой: `tools/test_ui_f.py:35`, `tools/test_ui_g.py`,
  `tools/test_ui_h.py:159`, `tools/test_backend_calculations.py`,
  `tools/test_physical_overrides_toggle.py`, `tools/test_parallel_integration.py`,
  `tools/bench_ui_parallel.py`.
* **1 файл** грузит его через `spec_from_file_location`.
* `tools/test_ui_h.py` идёт дальше: он **правит исходный текст файла подстановкой строк**
  (`UPSTREAM_PATCHES`, `tools/test_ui_h.py:52-73`) и запускает патченую копию
  `app/_test_ui_h_app.py`. Сейчас ни один из трёх образцов в файле не встречается
  (например, `rebound.tdb_evidence.sha256` отсутствует, зато есть уже исправленная форма
  `clean["database_sha256"] = rebound.tdb.sha256`, `app/ThermoGar_app.py:1138`), поэтому
  `patched == source` и тесты идут по настоящему файлу (`tools/test_ui_h.py:140-142`).
  Механизм молчит, но он жив и завязан на точный текст со значащими отступами.
* остальные — упоминания пути в сценариях-исследованиях и в комментариях.

Плюс пять мест в сборке держат путь строкой: `packaging/healthcheck.py:22`,
`packaging/launcher.pyw:27`, `packaging/launcher.pyw:870`,
`packaging/smoke_installed.ps1:370`, `packaging/stage_payload.ps1:169`.

Разница существенна. «Импортируют» означало бы, что разрез ловится импортами и
статическим анализом. На деле связь — путь и текст: новые модули статический анализ
у потребителей не заметит, зато сборка и тесты сломаются молча.

**3. Список «самых тяжёлых».** Мастер назвал шесть: `calculate_physical_properties` F 71,
`_normalize_dataset` F 58, `RestrictedFeRequest.__post_init__` F 50,
`density_from_site_fractions` F 48, `translate_phase_description` F 42,
`_validate_request` F 41. Все шесть подтверждаются. Но F-блоков десять, и в список не
попали три функции и один класс, причём два из них тяжелее половины списка:
`_friendly_error_text` **F (51)** (`app/thermogar_stage14.py:106`) — тяжелее
`__post_init__` (50); класс `RestrictedFeRequest` **F (51)**
(`app/thermogar_restricted_fe_core.py:117`); `validate_context_payload` **F (48)**
(`app/thermogar_workspace.py:435`) — вровень с `density_from_site_fractions`;
`run_precipitation` **F (42)** (`app/thermogar_precipitation.py:988`) — вровень с
`translate_phase_description`.

Четвёртое, не расхождение, а уточнение: пять из шести функций длиннее 300 строк лежат
**не** в `ThermoGar_app.py` (`thermogar_workspace.py`, `thermogar_properties.py` — две,
`thermogar_precipitation.py`, `thermogar_diffusion.py`), шестая —
`calculate_physical_properties` в `thermogar_physical.py`. В `ThermoGar_app.py` самая
длинная функция — `plot_ternary_thermogar`, 278 строк (`app/ThermoGar_app.py:6012-6289`).
Длина `ThermoGar_app.py` набрана не длинными функциями, а исполняемой разметкой и
текстами.

---

## 2. Разбор функций: Jev и моя оценка

### 2.1. Как прогонялось

Ключ `TYPESAFE_API_KEY` в окружении есть (108 символов). Прогон сделан: **47 функций,
по одному запросу на функцию, четыре вопроса в запросе**. Адрес —
`POST https://api.typesafe.ai/v1/systemone`, модель запрошена как `jev-latest`,
в ответах пришло `jev-1.13.0` — одна и та же во всех 47 ответах. Расход:
185 054 входных и 6 970 выходных токенов. Отказов и повторов не было.

Отбор: все блоки ранга D, E, F (43) плюс все функции длиннее 200 строк (17); объединение
даёт 47 после вычета пересечения. Два класса ранга D и F (`RestrictedFeRequest`,
`RestrictedFeReceipt`) в разбор не брались: их сложность — это сложность их
`__post_init__`, а он в списке есть.

Состояние на функцию: `fajl`, `imya_funkcii`, `stroki`, `dlina_strok`, `radon_cc`,
`kto_vyzyvaet` (места вызова по имени в `app/`, `tools/`, `scripts/`, `packaging/`) и
`ishodnik_funkcii` — исходный текст функции. Больше ничего: ни `results/`, ни
`tasks/lilith_16A/`, ни байтов баз в состояние не попало. Исходники ушли вендору —
это разрешено заданием, репозиторий открытый.

Вопросы (дословно, одним запросом на функцию):

* **Score «перегруженность»**, четыре уровня: 0 — «одна ясная задача»; 1 — «несколько
  задач, разрез очевиден»; 2 — «несколько задач, разрез потребует новых интерфейсов»;
  3 — «клубок: экран, расчёт и состояние вперемешку».
* **Choice «вид разреза»**: `vynesti_teksty` / `razbit_na_shagi` / `vynesti_modul` /
  `razdelit_ekran_i_raschet` / `ostavit`.
* **Noul** «функция влияет на числа результата, а не только на экран».
* **Noul** «внутри есть правило проекта с номером BL- либо физический критерий».

### 2.2. Таблица

Колонки «Моя» — моя оценка по тем же четырём вопросам, выставлена после чтения кода
и подсчёта признаков (число вызовов `st.*`, доля строк со строковыми литералами,
наличие `BL-`, наличие физических величин). В колонке «Сходится» — «нет», если
расходится хоть один из четырёх ответов; для Score расхождением считается разница
больше 0,75 уровня.

| # | Функция, файл:строки | ранг cc | длина | Jev: перегруженность | Jev: разрез | Jev: числа | Jev: BL/физика | Моя: перегруж. | Моя: разрез | Моя: числа | Моя: BL/физика | Сходится |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `app/thermogar_physical.py:1278-1705` `calculate_physical_properties` | F (71) | 428 | 1.52 (conf 0.51) | razbit_na_shagi (conf 0.41) | 0.98 | 0.93 | 2 | razbit_na_shagi | да | да | да |
| 2 | `app/thermogar_fe_equilibrium_worker.py:812-974` `_normalize_dataset` | F (58) | 163 | 1.42 (conf 0.41) | razbit_na_shagi (conf 0.73) | 0.97 | 0.85 | 1 | razbit_na_shagi | да | да | да |
| 3 | `app/thermogar_stage14.py:106-310` `_friendly_error_text` | F (51) | 205 | 0.30 (conf 0.70) | vynesti_teksty (conf 0.85) | 0.07 | 0.94 | 0 | vynesti_teksty | нет | да | да |
| 4 | `app/thermogar_restricted_fe_core.py:128-208` `RestrictedFeRequest.__post_init__` | F (50) | 81 | 0.89 (conf 0.51) | razbit_na_shagi (conf 0.61) | 0.81 | 0.89 | 1 | razbit_na_shagi | да | да | да |
| 5 | `app/thermogar_physical.py:995-1189` `PhysicalDensityDatabase.density_from_site_fractions` | F (48) | 195 | 1.39 (conf 0.39) | razbit_na_shagi (conf 0.63) | 0.98 | 0.95 | 1 | razbit_na_shagi | да | да | да |
| 6 | `app/thermogar_workspace.py:435-589` `validate_context_payload` | F (48) | 155 | 0.93 (conf 0.36) | razbit_na_shagi (conf 0.60) | 0.92 | 0.81 | 1 | razbit_na_shagi | да | да | да |
| 7 | `app/thermogar_precipitation.py:988-1278` `run_precipitation` | F (42) | 291 | 1.75 (conf 0.67) | vynesti_teksty (conf 0.35) | 0.97 | 0.95 | 2 | razbit_na_shagi | да | да | **нет** |
| 8 | `app/ThermoGar_app.py:5538-5669` `translate_phase_description` | F (42) | 132 | 0.85 (conf 0.78) | vynesti_teksty (conf 0.54) | 0.08 | 0.84 | 1 | vynesti_modul | нет | нет | **нет** |
| 9 | `app/thermogar_fe_equilibrium_worker.py:566-683` `_validate_request` | F (41) | 118 | 1.31 (conf 0.43) | razbit_na_shagi (conf 0.62) | 0.91 | 0.85 | 1 | razbit_na_shagi | да | да | да |
| 10 | `app/thermogar_physical.py:1915-2030` `_site_fractions_from_composition` | E (40) | 116 | 0.91 (conf 0.51) | razbit_na_shagi (conf 0.82) | 0.97 | 0.91 | 1 | razbit_na_shagi | да | да | да |
| 11 | `app/thermogar_precipitation.py:1300-1658` `render_precipitation_section` | E (39) | 359 | 2.47 (conf 0.47) | vynesti_teksty (conf 0.70) | 0.71 | 0.94 | 3 | razdelit_ekran_i_raschet | да | да | **нет** |
| 12 | `app/thermogar_workspace.py:1622-2038` `render_projects_and_history` | E (36) | 417 | 1.80 (conf 0.16) | vynesti_teksty (conf 0.58) | 0.51 | 0.09 | 2 | razdelit_ekran_i_raschet | да | нет | **нет** |
| 13 | `app/thermogar_fe_equilibrium_worker.py:994-1180` `_execute_request` | E (36) | 187 | 1.68 (conf 0.63) | razbit_na_shagi (conf 0.57) | 0.97 | 0.86 | 2 | razbit_na_shagi | да | да | да |
| 14 | `app/thermogar_workspace.py:2228-2442` `run_batch_calculations` | E (34) | 215 | 1.75 (conf 0.66) | razbit_na_shagi (conf 0.45) | 0.94 | 0.58 | 2 | razbit_na_shagi | да | да | да |
| 15 | `app/thermogar_verified_physical.py:557-743` `execute_verified_physical` | E (34) | 187 | 1.55 (conf 0.54) | razbit_na_shagi (conf 0.52) | 0.95 | 0.70 | 1 | razbit_na_shagi | да | да | да |
| 16 | `app/thermogar_verified_equilibrium.py:292-371` `_default_backend` | E (34) | 80 | 1.57 (conf 0.55) | razbit_na_shagi (conf 0.58) | 0.96 | 0.88 | 1 | razbit_na_shagi | да | нет | **нет** |
| 17 | `app/thermogar_restricted_fe_core.py:862-1070` `execute_bound_restricted_fe` | E (33) | 209 | 1.58 (conf 0.56) | razbit_na_shagi (conf 0.65) | 0.95 | 0.30 | 1 | razbit_na_shagi | да | нет | да |
| 18 | `app/thermogar_properties.py:573-764` `vrh_homogenization` | E (32) | 192 | 1.02 (conf 0.51) | razbit_na_shagi (conf 0.36) | 0.98 | 0.91 | 1 | razbit_na_shagi | да | да | да |
| 19 | `app/thermogar_verified_properties.py:1139-1364` `execute_verified_properties` | D (30) | 226 | 1.48 (conf 0.44) | razbit_na_shagi (conf 0.33) | 0.97 | 0.93 | 2 | razbit_na_shagi | да | да | да |
| 20 | `app/thermogar_restricted_fe_core.py:312-367` `RestrictedFeReceipt.__post_init__` | D (29) | 56 | 0.64 (conf 0.36) | razbit_na_shagi (conf 0.44) | 0.61 | 0.18 | 0 | ostavit | да | нет | **нет** |
| 21 | `app/thermogar_verified_loaders.py:1608-1647` `FeatureReceipt.__post_init__` | D (29) | 40 | 0.60 (conf 0.40) | razbit_na_shagi (conf 0.53) | 0.75 | 0.06 | 0 | ostavit | да | нет | **нет** |
| 22 | `app/thermogar_equilibrium_core.py:558-647` `find_monotonic_linear_crossings` | D (27) | 90 | 0.75 (conf 0.50) | razbit_na_shagi (conf 0.52) | 0.96 | 0.13 | 0 | ostavit | да | нет | **нет** |
| 23 | `app/thermogar_physical.py:703-786` `PhysicalDensityDatabase.element_density_model` | D (26) | 84 | 0.69 (conf 0.31) | razbit_na_shagi (conf 0.55) | 0.95 | 0.94 | 1 | razbit_na_shagi | да | да | да |
| 24 | `app/ThermoGar_app.py:2037-2240` `render_b4b2_elastic_properties` | D (25) | 204 | 2.45 (conf 0.45) | vynesti_teksty (conf 0.52) | 0.90 | 0.93 | 3 | razdelit_ekran_i_raschet | да | да | **нет** |
| 25 | `app/ThermoGar_app.py:3420-3561` `batch_engine_runner` | D (25) | 142 | 1.37 (conf 0.53) | razbit_na_shagi (conf 0.74) | 0.94 | 0.28 | 1 | razbit_na_shagi | да | нет | да |
| 26 | `app/thermogar_verified_properties.py:472-561` `_default_backend` | D (25) | 90 | 1.52 (conf 0.52) | razbit_na_shagi (conf 0.71) | 0.97 | 0.84 | 1 | razbit_na_shagi | да | да | да |
| 27 | `app/thermogar_database_repair.py:318-468` `repair_mobility_defaults` | D (24) | 151 | 1.24 (conf 0.24) | razbit_na_shagi (conf 0.76) | 0.97 | 0.57 | 1 | razbit_na_shagi | да | да | да |
| 28 | `app/thermogar_verified_equilibrium.py:460-592` `execute_verified_equilibrium` | D (24) | 133 | 1.52 (conf 0.50) | razbit_na_shagi (conf 0.61) | 0.95 | 0.39 | 1 | razbit_na_shagi | да | нет | да |
| 29 | `app/thermogar_parallel.py:772-861` `ParallelEquilibrium.map_points` | D (24) | 90 | 1.00 (conf 0.50) | razbit_na_shagi (conf 0.57) | 0.86 | 0.16 | 1 | razbit_na_shagi | да | нет | да |
| 30 | `app/thermogar_verified_physical.py:83-136` `make_physical_inputs` | D (24) | 54 | 0.73 (conf 0.27) | razbit_na_shagi (conf 0.57) | 0.92 | 0.86 | 0 | ostavit | да | да | **нет** |
| 31 | `app/thermogar_diffusion.py:1356-1692` `render_kinetics_section` | D (23) | 337 | 2.06 (conf 0.06) | vynesti_teksty (conf 0.66) | 0.55 | 0.88 | 3 | razdelit_ekran_i_raschet | да | да | **нет** |
| 32 | `app/thermogar_secure_io.py:598-675` `_atomic_replace_locked` | D (23) | 78 | 0.68 (conf 0.32) | razbit_na_shagi (conf 0.43) | 0.80 | 0.13 | 0 | ostavit | нет | нет | **нет** |
| 33 | `app/thermogar_workspace.py:2445-2634` `render_batch_calculation` | D (22) | 190 | 2.11 (conf 0.11) | vynesti_teksty (conf 0.60) | 0.35 | 0.80 | 2 | razdelit_ekran_i_raschet | да | да | **нет** |
| 34 | `app/thermogar_secure_io.py:381-458` `held_verified_snapshot` | D (22) | 78 | 0.89 (conf 0.11) | razbit_na_shagi (conf 0.58) | 0.95 | 0.09 | 0 | ostavit | нет | нет | **нет** |
| 35 | `app/thermogar_verified_properties.py:1063-1136` `_strengthening_inputs` | D (22) | 74 | 1.18 (conf 0.42) | razbit_na_shagi (conf 0.68) | 0.97 | 0.92 | 1 | vynesti_teksty | да | да | **нет** |
| 36 | `app/thermogar_verified_loaders.py:977-1044` `bind_selected_database` | D (22) | 68 | 1.50 (conf 0.49) | razbit_na_shagi (conf 0.61) | 0.93 | 0.19 | 1 | razbit_na_shagi | да | нет | да |
| 37 | `app/thermogar_diffusion.py:765-1032` `_run_model` | D (21) | 268 | 1.62 (conf 0.57) | vynesti_teksty (conf 0.27) | 0.97 | 0.87 | 2 | razbit_na_shagi | да | да | **нет** |
| 38 | `app/ThermoGar_app.py:1735-1930` `render_b4b_density_temperature` | D (21) | 196 | 2.66 (conf 0.66) | vynesti_teksty (conf 0.31) | 0.92 | 0.91 | 3 | razdelit_ekran_i_raschet | да | да | **нет** |
| 39 | `app/thermogar_verified_loaders.py:1214-1323` `prepare_feature_request` | D (21) | 110 | 1.06 (conf 0.49) | razbit_na_shagi (conf 0.35) | 0.92 | 0.08 | 1 | razbit_na_shagi | да | нет | да |
| 40 | `app/thermogar_secure_io.py:839-915` `secure_move_no_overwrite` | D (21) | 77 | 0.92 (conf 0.08) | razbit_na_shagi (conf 0.66) | 0.75 | 0.13 | 0 | ostavit | нет | нет | **нет** |
| 41 | `app/thermogar_verified_equilibrium.py:105-163` `make_equilibrium_inputs` | D (21) | 59 | 0.87 (conf 0.44) | razbit_na_shagi (conf 0.47) | 0.93 | 0.86 | 0 | ostavit | да | да | **нет** |
| 42 | `app/thermogar_properties.py:1769-2183` `render_strengthening_section` | C (20) | 415 | 2.29 (conf 0.29) | vynesti_teksty (conf 0.53) | 0.70 | 0.94 | 3 | razdelit_ekran_i_raschet | да | да | **нет** |
| 43 | `app/ThermoGar_app.py:6012-6289` `plot_ternary_thermogar` | C (19) | 278 | 0.75 (conf 0.56) | razbit_na_shagi (conf 0.45) | 0.17 | 0.83 | 1 | vynesti_modul | нет | нет | **нет** |
| 44 | `app/thermogar_workspace.py:1081-1316` `render_alloy_library` | C (18) | 236 | 1.75 (conf 0.21) | vynesti_teksty (conf 0.50) | 0.74 | 0.08 | 2 | razdelit_ekran_i_raschet | да | нет | **нет** |
| 45 | `app/thermogar_properties.py:941-1154` `calculate_strengthening` | C (14) | 214 | 1.13 (conf 0.49) | vynesti_teksty (conf 0.51) | 0.98 | 0.89 | 1 | razbit_na_shagi | да | да | **нет** |
| 46 | `app/thermogar_properties.py:1452-1766` `render_elastic_section` | C (11) | 315 | 2.59 (conf 0.59) | vynesti_teksty (conf 0.41) | 0.86 | 0.91 | 3 | razdelit_ekran_i_raschet | да | да | **нет** |
| 47 | `app/ThermoGar_app.py:6574-6804` `plot_ternary_phase_fraction_map` | B (9) | 231 | 0.80 (conf 0.45) | razbit_na_shagi (conf 0.27) | 0.28 | 0.88 | 1 | vynesti_modul | нет | нет | **нет** |


### 2.3. Где сходимся, где расходимся и почему

Сошлись полностью на 22 функциях из 47. Расхождений 25, и они не размазаны ровно:
**14 из 25 расходятся только по виду разреза**, при согласии по всем трём остальным
ответам.

**Где Jev оказался прав, а я сначала ответил иначе.** Пять функций я переоценил по
вопросу «есть ли внутри правило проекта или физический критерий» и поправил свой ответ
после чтения кода — привожу, потому что это меняет доверие к этому вопросу:

* `_normalize_dataset` (`app/thermogar_fe_equilibrium_worker.py:812-974`). Я поставил
  «нет» — имени `BL-` в функции нет. Но на `app/thermogar_fe_equilibrium_worker.py:873`
  стоит `number < 0.0 or number > 1.0 + 1e-8` — это проверка мольной доли фазы на
  физически допустимый отрезок с допуском. Jev: 0,85 — «да». Прав он.
* `validate_context_payload` (`app/thermogar_workspace.py:435-589`): на `:488`
  `units not in {"at", "wt"}`, на `:481` основа обязана быть элементом выбранной базы.
  Jev 0,81 — «да».
* `run_batch_calculations` (`app/thermogar_workspace.py:2228-2442`): на `:2284-2285`
  давление по умолчанию `101325.0` Па. Jev 0,58 — «да».
* `make_equilibrium_inputs` (`app/thermogar_verified_equilibrium.py:105-163`): единицы
  `wt`/`at` и давление проверяются как величины предметной области. Jev 0,86 — «да».
* `render_kinetics_section` (`app/thermogar_diffusion.py:1356-1692`): параметры кинетики
  на экране — величины предметной области, а не технические. Jev 0,88 — «да».

Обратное — Jev назвал физику там, где её нет, — случилось на четырёх функциях, и три
из них одного сорта: `translate_phase_description` (0,84), `plot_ternary_thermogar` (0,83),
`plot_ternary_phase_fraction_map` (0,88). Первая — подстроковый разбор английского
описания фазы: `if "bcc" in lower` (`app/ThermoGar_app.py:5569`) и ещё около двадцати
таких же проверок. Две вторые — рисование по уже посчитанным данным: в
`plot_ternary_thermogar` нет ни одного вызова расчёта, только `np.asarray`, маски
конечных значений и оси (`app/ThermoGar_app.py:6040-6102`). Причина промаха, на мой
взгляд, в моей же формулировке вопроса: «физический критерий — …или **условие из
материаловедения**». Под эту формулировку `if "bcc" in lower` подходит буквально.
Вопрос нужно было сузить до «порог или константа, от которых зависит **число**».
Четвёртый случай — `_default_backend` (`app/thermogar_verified_equilibrium.py:292-371`),
0,88 против моего «нет»: там диспетчеризация бэкендов, физических порогов я не нашёл.

**Где на том же вопросе Jev сработал точно.** В выборке восемь функций содержат
буквальный номер `BL-` в коде или комментарии. Все восемь получили ≥ 0,91:
`calculate_physical_properties` 0,93 (BL-39), `_friendly_error_text` 0,94 (BL-24),
`run_precipitation` 0,95 (BL-35), `render_precipitation_section` 0,94 (BL-35),
`execute_verified_properties` 0,93 (BL-40), `element_density_model` 0,94 (BL-39, BL-47),
`render_b4b2_elastic_properties` 0,93 (BL-38), `render_b4b_density_temperature` 0,91 (BL-49).
Ни одного пропуска. Чисто технические функции — `held_verified_snapshot` 0,09,
`prepare_feature_request` 0,08, `FeatureReceipt.__post_init__` 0,06,
`render_projects_and_history` 0,09 — сидят внизу. Разделение по этому вопросу рабочее;
ошибается он только в сторону «да».

**Главное расхождение — вид разреза.** Из пяти вариантов Jev выбрал два:
`razbit_na_shagi` 33 раза, `vynesti_teksty` 14 раз. Вариант `vynesti_modul` он не выбрал
**ни разу**, `razdelit_ekran_i_raschet` — тоже **ни разу**, и даже вторым местом
`razdelit_ekran_i_raschet` нигде не поднялся выше 0,25 (`_run_model`). Между тем в
выборке девять функций рисуют экран десятками вызовов и одновременно считают:
`render_strengthening_section` — 50 вызовов `st.*`, 28 виджетов, 10 обращений к
`session_state` (`app/thermogar_properties.py:1769-2183`); `render_precipitation_section` —
55 и 19 (`app/thermogar_precipitation.py:1300-1658`); `render_kinetics_section` — 36 и 5;
`render_projects_and_history` — 43 и 16; `render_elastic_section` — 24 и 3;
`render_alloy_library` — 29 и 10; `render_batch_calculation` — 15;
`render_b4b2_elastic_properties` — 11 и 3; `render_b4b_density_temperature` — 12 и 4.
На них же Jev ставит самый высокий Score перегруженности: 2,06…2,66, а два случая
(`render_b4b_density_temperature` 2,66, `render_elastic_section` 2,59) почти дотягивают
до уровня «клубок: экран, расчёт и состояние вперемешку». То есть **диагноз он ставит
тот же, а лечение предлагает другое**: «вынести тексты» вместо «разделить экран и
расчёт». Моя оценка на этих девяти — `razdelit_ekran_i_raschet`.

Возможное объяснение: `vynesti_teksty` — самый дешёвый и самый безопасный ход, и по
измеримому признаку он на этих функциях действительно оправдан. Доля строк со
строковыми литералами: `render_strengthening_section` 49 %, `render_kinetics_section` 44 %,
`render_precipitation_section` 44 %, `render_elastic_section` 38 %,
`render_projects_and_history` 33 %. Jev выбирает первый шаг, а я называю конечную цель.
Для плана это не спор: тексты выносятся первыми в любом случае, и шаг «вынести тексты»
не мешает последующему «разделить экран и расчёт». Но если читать его ответ как
единственный вердикт, разрез остановится на полпути.

Три функции я отнёс к `vynesti_modul`, а Jev — к `razbit_na_shagi`/`vynesti_teksty`:
`translate_phase_description` (`app/ThermoGar_app.py:5538-5669`),
`plot_ternary_thermogar` (`:6012-6289`), `plot_ternary_phase_fraction_map` (`:6574-6804`).
Причина у меня не в их устройстве, а в месте: это 641 строка тем «описания фаз» и
«тройные диаграммы» внутри головного сценария Streamlit, и вопрос к ним — не как их
порезать, а почему они там. У Jev в состоянии был только текст функции и имя файла;
судить о том, что файл — головной сценарий на 12 180 строк, ему было не из чего.
Это ограничение состояния, а не ошибка модели: чтобы такой вопрос имел смысл, в
состояние нужно класть карту модуля.

Ещё четыре расхождения по «влияет на числа»: `_atomic_replace_locked` (Jev 0,80),
`held_verified_snapshot` (0,95), `secure_move_no_overwrite` (0,75) и
`render_batch_calculation` (0,35). Первые три — атомарная запись файла, файловая
блокировка и перенос без перезаписи (`app/thermogar_secure_io.py:381-458`, `:598-675`,
`:839-915`). Они переносят байты, не меняя ни одного числа, — я ставлю «нет», Jev «да».
Здесь, думаю, срабатывает «…или сохраняемые данные» в моей формулировке вопроса:
функция действительно решает судьбу сохраняемых данных. Формулировка виновата,
а не ответ. `render_batch_calculation` — наоборот: Jev 0,35 при том, что функция ведёт
пакетный расчёт по файлу пользователя и пишет выгрузку.

### 2.4. Итог по применимости Jev в этой задаче

На вопросе про `BL-`/физику он даёт готовый фильтр «не трогать» без чтения кода:
восемь из восьми попаданий, ложные срабатывания все в безопасную сторону. На Score
перегруженности его порядок совпадает с тем, что видно по числу вызовов `st.*` и доле
текстов. На выборе действия он систематически занижает глубину разреза и не пользуется
двумя вариантами из пяти — его ответ на этот вопрос надо читать как «первый шаг»,
а не как «что делать». Стоимость прогона: 47 запросов, 185 054 входных токена,
6 970 выходных, около трёх минут.

---

## 3. План разреза `app/ThermoGar_app.py`

### 3.1. Что получается на выходе

Из 12 180 строк:

* 564 строки — литеральные константы верхнего уровня, из них 209 — `USER_GUIDE_MD`;
* 1 221 строка — 65 имён, нужных больше чем одной вкладке;
* 5 090 строк — определения, нужные ровно одной вкладке (по транзитивному замыканию,
  п. 1.7);
* 4 726 строк — исполняемая разметка девяти вкладок;
* 346 строк — заголовок и боковая панель;
* 110 строк — мёртвый код (п. 1.8).

Целевой состав: `app/thermogar_app_texts.py` (тексты и умолчания),
`app/thermogar_app_common.py` (общие помощники), по модулю на вкладку
(`app/thermogar_tab_diagrams.py`, `…_solidification.py`, `…_energy.py`,
`…_properties.py`, `…_kinetics.py`, `…_projects.py`, `…_calculation.py`),
и `ThermoGar_app.py` как точка входа: боковая панель, `st.tabs`, девять вызовов
`render_*_tab(context)`.

**Ограничение сборки, обязательное к соблюдению.** `packaging/stage_payload.ps1:50`
кладёт в поставку `app` с `Include = '*.py'` и `Recurse = $false`. Новые модули обязаны
лежать **плоско в `app/`**, без подкаталогов и без пакета. Модуль, убранный в
`app/tabs/`, в установщик не попадёт, и приложение упадёт только у пользователя:
проверка обязательных файлов (`packaging/stage_payload.ps1:166-171`,
`packaging/smoke_installed.ps1:366-371`) перечисляет `app\ThermoGar_app.py` поимённо
и отсутствия нового модуля не заметит.

### 3.2. Порядок шагов

Каждый шаг — отдельная задача, отдельный коммит, отдельная сверка. Ожидание для всех
шагов одно: **все вкладки побайтово прежние по сверке 15-Ш** — выгрузки на трёх составах
волны 15-Ш (Ni-20Cr, Ni–9,8Al–8,3Cr ат. %, Fe-15Cr-0,4C масс. %; плотность и упругость,
галочка поправок включена и снята) совпадают с опорными байт в байт, как в
`tasks/REGISTER.md:299`, где такая сверка дала 78 файлов из 78.

**Шаг 0. Опорная точка. Правок кода нет.**
Снять и зафиксировать в `results/` выгрузки всех девяти вкладок на трёх составах 15-Ш,
посчитать SHA-256 каждого файла, прогнать полную регрессию и записать её итог.
Без этого шага «побайтово прежние» не с чем сравнивать.
Ловит: ничего; даёт эталон.

**Шаг 1. Тексты и умолчания → `app/thermogar_app_texts.py`.**
Переносятся дословно, без переформатирования: `USER_GUIDE_MD` (`:11560-11768`),
`PHASE_EXPLANATIONS` (`:404-451`), `EXACT_DESCRIPTION_TRANSLATIONS` (`:5517-5535`),
`DATABASE_DEFINITIONS` (`:275-320`), `FE_PROFILE_RELATIVE_PATHS` (`:322-327`),
`FE_PROFILE_UI_LABEL` (`:338`), `SOLIDIFICATION_DEFAULTS` (`:341-354`), `ENERGY_DEFAULTS` (`:362-402`),
`BINARY_DIAGRAM_DEFAULTS` (`:454-488`), `ISOPLETH_DEFAULTS` (`:494-525`),
`TERNARY_DIAGRAM_DEFAULTS` (`:528-553`), `TERNARY_PHASE_MAP_DEFAULTS` (`:556-587`),
тексты галочки поправок (`:1295-1322`), подписи долей фаз BL-38 (`:1315`).
**`FE_PROFILE_SHA256` (`:328-332`) не переносится** — см. п. 4.
В `ThermoGar_app.py` остаётся `from thermogar_app_texts import *`-подобный явный импорт
именами. Минус около 520 строк.
Ожидание: побайтово прежние.
Ловят: `tools/test_ui_f.py` (38 «не slow» + 21 «slow»), `tools/test_ui_g.py` (16),
`tools/test_ui_h.py` (19), `tools/test_version_consistency.py` (90 проверок версии,
он читает тексты), `tools/test_dropped_phases_text.py`, `tools/test_wave15_z.py`
(тексты отказов BL-24, BL-26, BL-35).

**Шаг 2. Контекст боковой панели → явный объект.** Это единственный шаг с новым
интерфейсом, и он обязателен раньше любых вкладок.
Девять глобальных имён (`database_key` `:6846`, `steel_mode` `:6975`, `balance` `:7026`,
`units`/`units_label` `:7038-7045`, `composition_text` `:7050`, `pressure_pa` `:7061`,
`available_elements` `:6959`, `CURRENT_CONTEXT` `:7074`) собираются в один
неизменяемый объект, который дальше передаётся во вкладки параметром. Сами строки
боковой панели не трогаются, меняется только способ, которым их результат доходит до
вкладок.
Ожидание: побайтово прежние; `st.session_state` не меняется ни по одному ключу.
Ловят: все три матрицы UI; особенно `tools/test_ui_h.py`, который проверяет ключи
восстановления состояния (`WIDGET_STATE_VERSION`, `is_restorable_widget_key`,
`validate_widget_state`, `tools/test_ui_h.py:33-40`).

**Шаг 3. Общие помощники → `app/thermogar_app_common.py`.**
56 имён из списка п. 1.7 (девять переменных ушли на шаге 2), около 1 220 строк.
Тела функций не меняются ни на символ — только место.
Ожидание: побайтово прежние.
Ловят: все матрицы UI, `tools/test_backend_calculations.py` (19),
`tools/thermogar_self_test.py`.

**Шаг 4. Пробная вкладка: «Кинетика» → `app/thermogar_tab_kinetics.py`.**
28 строк разметки (`:11526-11553`), ноль собственных определений: вкладка целиком
делегирует в `thermogar_diffusion` и `thermogar_precipitation`. Самый дешёвый способ
проверить, что механизм шага 2 работает.
Ожидание: побайтово прежние.
Ловит: `tools/test_ui_g.py` (16 тестов, три базы × три действия).

**Шаг 5. «Свойства» → `app/thermogar_tab_properties.py`.**
109 строк разметки (`:11411-11519`) плюс 33 собственных имени на 1 171 строку —
весь контур B4B/B4B2 (`:1325-2602`). Разметки мало, определений много: перенос почти
механический.
Ожидание: побайтово прежние, в том числе выгрузки плотности и упругости на трёх составах.
Ловят: `tools/test_ui_f.py` (раздел «Свойства» на трёх базах),
`tools/test_physical_overrides_toggle.py`, `tools/test_density.py`,
`tools/test_density_below_pdb.py`, `tools/test_density_thermal_expansion.py`.
Осторожно: здесь живёт перепривязка `vlb_active_context`, из-за которой когда-то
появились `UPSTREAM_PATCHES` в `tools/test_ui_h.py:52-73`.

**Шаг 6. «Энергии» → `app/thermogar_tab_energy.py`.**
731 строка разметки (`:10673-11403`), 11 собственных имён на 563 строки.
Ловит: `tools/test_ui_f.py`, раздел «Энергии».

**Шаг 7. «Проекты и данные» → `app/thermogar_tab_projects.py`.**
407 строк разметки (`:11774-12180`), 18 собственных имён на 932 строки.
Ловит: `tools/test_ui_h.py` целиком (19 тестов: библиотека, пакет, проекты, история,
импорт и экспорт). Перед шагом проверить, не совпал ли снова какой-нибудь образец из
`UPSTREAM_PATCHES`: если совпадёт, тесты пойдут по патченой копии, и разрез будет
проверен не на том файле.

**Шаг 8. «Затвердевание» → `app/thermogar_tab_solidification.py`.**
740 строк разметки (`:9927-10666`), 35 собственных имён на 915 строк, включая весь
контур ликвидуса и солидуса и правило BL-44.
Ожидание: побайтово прежние, отдельно — поле «Критерий солидуса» в выгрузке и
предупреждение BL-44 слово в слово.
Ловят: `tools/test_ui_f.py`, `tools/test_equilibrium_solidus_fallback.py`,
`tools/test_liquidus_bisection.py`.

**Шаг 9. «Расчёты» → `app/thermogar_tab_calculation.py`.**
Три подвкладки, 948 строк разметки (`:7199-8158`), собственных определений почти нет
(3 имени, 92 строки) — вкладка почти целиком стоит на общем модуле шага 3.
Ловят: `tools/test_ui_f.py`, `tools/test_backend_calculations.py`,
`tools/test_parallel_integration.py`.

**Шаг 10. «Диаграммы» → `app/thermogar_tab_diagrams.py`.** Последней: самая большая
и самая дорогая по регрессии.
1 755 строк разметки (`:8165-9919`), 19 собственных имён на 1 417 строк —
бинарная, многокомпонентная, тройная диаграммы и карта доли фазы.
Ожидание: побайтово прежние PNG и CSV всех четырёх подвкладок.
Ловят: `tools/test_ui_f.py -m slow` (в нём же три самых тяжёлых кейса
`test_ternary_phase_map`, BL-27: 21 passed за 1 094 с, пик 4,83 ГиБ —
`tasks/WAVE18_V_REPORT.md:132-133`).

**Шаг 11 (по решению владельца). Мёртвый код.** 110 строк из п. 1.8 — удалять или
оставить. Своей волей не трогать: шесть функций `restricted_fe_*` выглядят заготовкой
контура, а не мусором.

### 3.3. Чего этот план не делает

Не трогает ни одной из 47 функций из п. 2 — ни одна из них не режется в рамках этого
плана. Разрез `ThermoGar_app.py` и разрез тяжёлых функций — две разные работы, и
смешивать их нельзя: первая целиком проверяется побайтовой сверкой, вторая — нет.
После шагов 1–10 в `ThermoGar_app.py` остаются четыре функции из списка ранга D
(`render_b4b2_elastic_properties`, `batch_engine_runner`, `render_b4b_density_temperature`,
`translate_phase_description`) — они уедут в свои модули вместе со вкладками, но
внутри не изменятся.

---

## 4. Что не трогать

**Правила проекта с номером `BL-`.** В `app/` 58 строк с такой пометкой в 10 файлах. В головном
сценарии девять: `app/ThermoGar_app.py:1273` (BL-49, DP-параметры PDB от 298,15 K),
`:1315` (BL-38, подписи долей фаз), `:1326` (BL-14, галочка поправок), `:1756` (BL-49,
нижняя граница скана), `:2080` (BL-38, объёмные доли), `:4621` (BL-44, доля твёрдого в
конце траектории), `:4688` (BL-44, солидус половинным делением), `:4893` (BL-44,
`solidus_c`), `:10314` (BL-44, конец несошедшейся траектории). Остальные —
`thermogar_precipitation.py` (15), `thermogar_physical.py` (12),
`thermogar_database_repair.py` (8), `thermogar_verified_properties.py` (8),
`thermogar_paths.py` (2), по одному в `thermogar_release_policy.py`,
`thermogar_stage14.py`, `thermogar_verified_equilibrium.py`,
`thermogar_verified_physical.py`. Строки с `BL-` переносятся дословно вместе с
комментарием: комментарий здесь — ссылка на реестр, а не пояснение.

**Физические пороги и константы.** `SOLID_PRESENCE_FLOOR`, `LIQUIDUS_TOLERANCE_C`,
`LIQUIDUS_BRACKET_STEP_C`, `LIQUIDUS_BRACKET_MARGIN_C` (`app/ThermoGar_app.py:4444-4450`),
`EQUILIBRIUM_SOLIDUS_MIN_SOLID_FRACTION` (`:4623-4631`), допуск мольной доли
`1.0 + 1e-8` (`app/thermogar_fe_equilibrium_worker.py:873`), давление по умолчанию
`101325.0` Па (`app/thermogar_workspace.py:2284-2285`). Значения не меняются, не
округляются и не «приводятся к единому стилю».

**Сверка по хэшам.** `RELEASE_DATABASE_SHA256` (`app/thermogar_release_policy.py:84`),
`PHYSICAL_DATABASE_SHA256` (`:272`), `FE_PROFILE_SHA256` (`app/ThermoGar_app.py:328-332`),
и весь путь сверки в `app/thermogar_verified_loaders.py` (`_validate_sha256` `:216`,
сверка байтов артефакта `:390`, `:406`, паспорта `:682-694`, отпечатка фаз `:722`).
`FE_PROFILE_SHA256` выглядит константой и просится в модуль текстов на шаге 1 — не
переносить: это не текст, а прошитая улика. Пусть лежит рядом с кодом, который её
сверяет.

**Тексты описи владельца — дословно, включая перевод строки и пробелы.** Они утверждены
поимённо и записаны в реестре: тексты 15-Ш, «символы элементов, а не названия», оговорка
«при рабочих температурах ошибка объёма может превышать 10 %»
(`tasks/REGISTER.md:299`, `tasks/WAVE15_E2_OPUS.md:17`), утверждённый текст BL-24
(`tasks/REGISTER.md:603`), предупреждение BL-44 «Равновесное затвердевание не сошлось;
солидус найден половинным делением по доле жидкости.» (`tasks/REGISTER.md:304`).
В коде это `USER_GUIDE_MD`, `PHASE_EXPLANATIONS`, `EXACT_DESCRIPTION_TRANSLATIONS`,
`SOLIDUS_FALLBACK_WARNING`, `SOLIDUS_SEARCH_STATUS_LABEL` (`app/ThermoGar_app.py:4623-4631`),
тексты галочки поправок (`:1295-1322`) и подписи BL-38 (`:1315`). При переносе — копия
байт в байт; переформатирование строк, замена кавычек, склейка переносов запрещены.
Правило «отчёт содержит вывод дословно» в проекте уже есть (`tasks/RULES.md:26`),
тексты на экране живут по тому же принципу.

**Байты баз.** `tasks/RULES.md:14`: «Байты `.tdb` и `.pdb` не меняются никогда.
Исправления идут в код загрузчиков.» Разрез головного сценария к базам не
прикасается вовсе.

**Путь `app/ThermoGar_app.py`.** Имя и место точки входа держат пять мест сборки
(`packaging/healthcheck.py:22`, `packaging/launcher.pyw:27`, `packaging/launcher.pyw:870`,
`packaging/smoke_installed.ps1:370`, `packaging/stage_payload.ps1:169`) и семь тестов
через `AppTest.from_file`. Файл остаётся на месте и остаётся точкой входа.

---

## 5. Оценка объёма и регрессии

Единица «задача» — одна волна в терминах проекта: одно задание, одна ветка, один отчёт.

| Шаг | Задач | Правка, строк | Регрессия |
|---|---|---|---|
| 0. Опорная точка | 1 | 0 | полная, 1 прогон |
| 1. Тексты и умолчания | 1 | ≈ 520 перенести | полная |
| 2. Контекст боковой панели | 1 | ≈ 60 новых, 9 имён | полная, дважды (до и после) |
| 3. Общие помощники | 1 | ≈ 1 220 перенести | полная |
| 4. «Кинетика» (проба) | 1 | ≈ 30 | `test_ui_g` + полная |
| 5. «Свойства» | 1 | ≈ 1 280 | полная |
| 6. «Энергии» | 1 | ≈ 1 290 | полная |
| 7. «Проекты и данные» | 1 | ≈ 1 340 | полная |
| 8. «Затвердевание» | 1 | ≈ 1 660 | полная |
| 9. «Расчёты» | 1 | ≈ 1 040 | полная |
| 10. «Диаграммы» | 1 | ≈ 3 170 | полная, самая долгая |
| 11. Мёртвый код (по решению владельца) | 0–1 | −110 | полная |
| **Итого** | **11–12** | **≈ 11 600 строк меняют место, ≈ 60 строк новых** | **12–13 полных прогонов** |

Опора для часов — измеренная регрессия последней волны: **104,1 мин**
(`tasks/WAVE18_V_REPORT.md:17`), вся задача от первого прогона — около 2 ч 10 мин
(`там же:23`). В эти 104 минуты входит `test_ui_f -m slow` одним процессом:
21 passed за 1 094 с при пике 4,83 ГиБ (`tasks/WAVE18_V_REPORT.md:132-133`).

* **Только регрессия:** 12–13 прогонов × 1,75 ч = **21–23 часа машинного времени.**
  Шаг 2 требует двух прогонов, шаг 10 может потребовать повтора из-за памяти —
  закладывать **24–26 часов.**
* **Работа помимо регрессии:** шаги 1, 3, 4 — механические, по 2–3 ч на задачу.
  Шаги 5–10 — по 4–6 ч: перенос, правка импортов, сверка выгрузок, отчёт.
  Шаг 2 — 6–8 ч: единственное место, где появляется новый интерфейс.
  Шаг 0 — 3–4 ч: снять и описать эталон.
  Итого **45–60 часов** ручной работы.
* **Всего: 11–12 задач, ориентировочно 70–85 часов,** из которых около трети —
  ожидание регрессии.

Оговорки к оценке, которые могут её сдвинуть:

* Весь `tools/` одной командой **не прогоняется** и не прогонялся с волны 11R
  (`tasks/REGISTER.md:277`, запись BL-17). Регрессия идёт по файлам, и её длительность
  — сумма прогонов, а не одна команда. 104,1 мин из 18-В получены именно так.
* `tools/test_ui_f.py -m slow` берёт до 4,9 ГиБ (BL-27, `tasks/REGISTER.md:287`).
  На машине с другими сессиями шаг 10 придётся гонять по группам, и он подорожает.
* Побайтовая сверка ловит изменение результата, но **не ловит** изменение порядка
  виджетов на экране, если выгрузка от него не зависит. На шагах 5–10 к сверке нужен
  просмотр вкладки глазами — это и есть та часть, которую нельзя автоматизировать.

---

## Приложение. Чем сделан замер

```
python -m radon cc -s app/
python -m radon cc -s --total-average app/
python -m radon mi -s app/
python -m radon cc -s tools/ scripts/ packaging/
python -m pylint --disable=all --enable=duplicate-code --min-similarity-lines=12 app/
```

Длины функций, карта модуля, транзитивное замыкание вкладок и доли строковых
литералов посчитаны разбором AST и токенов теми же файлами `.py`, что и исходники;
скрипты лежат во временном каталоге сессии и в репозиторий не клались.

Прогон Jev: `POST https://api.typesafe.ai/v1/systemone`, модель `jev-latest`,
в ответах `jev-1.13.0`, 47 запросов по 4 вопроса, 185 054 входных и 6 970 выходных
токенов.
