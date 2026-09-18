**Итог 15-О.** `test_ui_f -m slow` одним процессом: до правки — 8,14 ГиБ у 13-Р2 (в 15-О одним процессом не запускался по заданию; половина файла снята средой по памяти при оценке 1,94 + 4,2 ≈ 6,1 ГиБ), после — **4,91 ГиБ, `21 passed`**; цель 4,0 ГиБ **не достигнута**. **Всплеск, не утечка:** основной процесс выходит на плато 2,0 ГиБ и дальше не растёт; пик дают воркеры пула на `test_ternary_phase_map`, их число бралось из свободной памяти (2 → 3,15 ГиБ, 3 → 4,53, 5 → 7,2). BL-17: метод `thread` у pytest-timeout заменён в `tools/conftest.py` — тест по таймауту падает, файл доходит до итоговой строки (`1 failed, 5 passed, 53 deselected`).

# Волна 15-О — BL-27 и BL-17

Дерево `C:\Users\gareg\Desktop\ThermoGar-w15o`, ветка `wave15-tests` от `wave15-release` (`cc6c188`).
Задание — `tasks/WAVE15_O_OPUS.md`. В `main` и `wave15-release` ничего не влито, не пушено. Деревья
`w15d`, `w15e` не менялись (из `w15d` прочитан только `tasks/WAVE15_Z_REPORT.md`, в этой ветке его нет).

Файлы, которые менялись: `tools/conftest.py`, `tools/test_ui_f.py`, `results/wave15_o/`,
`tasks/WAVE15_O_OPUS.md`, `tasks/WAVE15_O_REPORT.md`. `app/` не менялся.

## 0. Где посылка задания расходится с тем, что найдено

1. **«Плотная сетка карты» — сетка не плотная.** Карта в тесте строится на шаге по умолчанию
   `TERNARY_PHASE_MAP_DEFAULTS[...]["step"] = 20.0` (`app/ThermoGar_app.py:553-584`) — 21 узел. Это
   самый грубый шаг, какой допускает поле (`max_value=20.0`, `app/ThermoGar_app.py:9087`). Уменьшать
   нечего. Всплеск даёт не сетка, а пул воркеров (п. 2).
2. **Фигуры matplotlib в `test_ui_f` не копятся.** После каждого из 59 тестов `plt.get_fignums()` пуст.
   Streamlit сам закрывает все фигуры после каждого прогона скрипта:
   `streamlit/runtime/scriptrunner/script_runner.py:958` — `cast("Any", plt).close("all")` в
   `_clean_problem_modules()`. Предупреждение «более 20 открытых фигур» из п. 9 отчёта 15-З относится к
   тестам, которые зовут модуль выделения фаз напрямую, без AppTest (`test_precipitation_grid`,
   `test_ui_g` в ветке `wave15-bl35`). И строка `app/thermogar_precipitation.py:506` — это строка ветки
   `wave15-bl35`; в `cc6c188` та же функция `_single_figure` стоит на строках 396–399. Фигуры там
   возвращаются наружу (`figures: dict[str, plt.Figure]`, строка 133), под разрешённую правку
   «`plt.close` там, где фигура не отдаётся наружу» они не подходят. **`app/` не правился, п. 6
   отчёта 15-Д (побайтовая сверка KWN) не нужен.** В моём прогоне `test_ui_g` на `cc6c188`
   предупреждения о фигурах нет — только два `RuntimeWarning: divide by zero` из kawin.
3. **Настроек pytest нет.** В дереве нет `pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini`;
   глобального `timeout` нет. Таймауты стоят только метками: `tools/test_backend_calculations.py`
   (`DEFAULT_TIMEOUT = 120`, `SLOW_TIMEOUT = 600`, строки 71–72) и `tools/test_phase_presets.py:385`.
   В `tools/test_ui_g.py` меток `timeout` больше нет, хотя запись BL-17 их там называет (там только
   `AppTest.from_file(..., default_timeout=1800)`, строка 105 — это таймаут AppTest, не pytest-timeout).
4. **Цель «пик меньше 4,0 ГиБ» не достигнута:** 4,91 ГиБ (п. 4). По заданию — не подгонялось.

## 1. Замер памяти по тестам (до правки)

**Как мерилось.** В `tools/conftest.py` добавлен хук `pytest_runtest_protocol`, он включается
переменной `THERMOGAR_MEMLOG=<файл.jsonl>` и без неё ничего не делает. На каждый тест пишется
рабочий набор основного процесса до и после теста (setup + call + teardown), пик рабочего набора
**дерева** процессов (основной + воркеры пула) по опросу раз в 0,2 с, число открытых фигур. С
`THERMOGAR_MEMLOG_DEEP=1` — ещё число живых `AppTest` и рабочий набор после `gc.collect()`.

Раннер — `results/wave15_o/run_groups.py`, сокращённая копия раннера 14-Д: порог входа 3,0 ГиБ
свободной памяти (для прогонов одним процессом поднят ключом, см. ниже), аварийный порог
`E1_ABORT_FREE_GIB` = 1,0 ГиБ читается из `tools/study_hn62m_wave12.py`, пик дерева раз в 2 с,
`PYTHONHASHSEED=0`, интерпретатор `C:\Users\gareg\Desktop\ThermoGar\.venv-windows`. Сводка всех
попыток — `results/wave15_o/summary.jsonl`, логи — `results/wave15_o/<этап>/*.log.txt`, замеры —
`*.memlog.jsonl`. Другой расчётный поток на машине не шёл.

Группы: обычные — две (`notslow_a`: семь функций от `test_startup_is_clean` до
`test_tzero_in_narrow_window`, 21 тест; `notslow_b`: остальные 17), медленные — пять групп `-k`, как в
14-Д. Покрытие проверено `--collect-only`: 21 + 17 = 38 обычных, 21 медленный.

| группа (этап `before`) | свободно на старте | итог | пик дерева | минимум свободной |
|---|---|---|---|---|
| `notslow_a` | 5,16 | `21 passed, 38 deselected in 472.84s` | 4,14 | 1,28 |
| `notslow_b` | 5,84 | `17 passed, 42 deselected in 373.43s` | 4,84 | 1,36 |
| `-k test_solidification` | 6,01 | `9 passed, 50 deselected in 513.26s` | 1,98 | 4,00 |
| `-k test_binary_diagram` | 5,99 | `3 passed, 56 deselected in 121.45s` | 1,38 | 4,55 |
| `-k test_isopleth_diagram` | 5,94 | `3 passed, 56 deselected in 364.30s` | 2,09 | 3,89 |
| `-k test_ternary_diagram` | 5,97 | `3 passed, 56 deselected in 224.77s` | 1,77 | 4,12 |
| `-k test_ternary_phase_map` | 5,89 | `3 passed, 56 deselected in 154.07s` | 4,53 | 1,56 |

Таблица по тестам. «Прирост» — рабочий набор основного процесса после теста минус до теста; «после
теста» — рабочий набор основного процесса; «пик» — пик дерева процессов за время теста. ГиБ.

`before/notslow_a.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_startup_is_clean[ni]` | 14 | 0,13 | 0,24 | 0,24 |
| `test_startup_is_clean[al]` | 5 | 0,01 | 0,25 | 0,25 |
| `test_startup_is_clean[fe]` | 8 | 0,02 | 0,27 | 0,27 |
| `test_single_equilibrium[ni]` | 15 | 0,16 | 0,42 | 0,42 |
| `test_single_equilibrium[al]` | 17 | 0,63 | 1,05 | 1,14 |
| `test_single_equilibrium[fe]` | 16 | 0,34 | 1,39 | 1,43 |
| `test_temperature_scan[ni]` | 18 | 0,03 | 1,42 | 2,47 |
| `test_temperature_scan[al]` | 33 | 0,01 | 1,43 | 4,28 |
| `test_temperature_scan[fe]` | 38 | 0,01 | 1,44 | 4,12 |
| `test_concentration_scan[ni]` | 35 | 0,01 | 1,44 | 3,57 |
| `test_concentration_scan[al]` | 68 | 0,01 | 1,45 | 3,24 |
| `test_concentration_scan[fe]` | 38 | 0,00 | 1,45 | 3,23 |
| `test_energy_curve[ni]` | 12 | 0,02 | 1,47 | 2,66 |
| `test_energy_curve[al]` | 10 | 0,10 | 1,57 | 1,62 |
| `test_energy_curve[fe]` | 13 | 0,00 | 1,57 | 1,58 |
| `test_driving_force[ni]` | 13 | 0,08 | 1,65 | 1,66 |
| `test_driving_force[al]` | 16 | 0,07 | 1,72 | 1,80 |
| `test_driving_force[fe]` | 19 | -0,01 | 1,71 | 1,73 |
| `test_tzero_in_narrow_window[ni]` | 14 | 0,00 | 1,71 | 1,74 |
| `test_tzero_in_narrow_window[al]` | 10 | 0,01 | 1,73 | 1,74 |
| `test_tzero_in_narrow_window[fe]` | 59 | -0,01 | 1,72 | 1,73 |

`before/notslow_b.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_density_single[ni]` | 21 | 0,30 | 0,41 | 0,41 |
| `test_density_single[al]` | 34 | 0,64 | 1,05 | 1,14 |
| `test_density_single[fe]` | 40 | 0,37 | 1,42 | 1,46 |
| `test_density_estimated_warning_is_shown_to_user` | 60 | 0,72 | 2,14 | 2,56 |
| `test_density_temperature_scan[ni]` | 14 | -0,21 | 1,93 | 2,14 |
| `test_density_temperature_scan[al]` | 34 | 0,01 | 1,94 | 4,88 |
| `test_density_temperature_scan[fe]` | 32 | -0,17 | 1,77 | 4,61 |
| `test_elastic_vrh[ni]` | 17 | 0,02 | 1,78 | 1,79 |
| `test_elastic_vrh[al]` | 20 | 0,00 | 1,78 | 1,83 |
| `test_elastic_vrh[fe]` | 23 | 0,01 | 1,80 | 1,84 |
| `test_strengthening[ni]` | 8 | 0,00 | 1,80 | 1,80 |
| `test_strengthening[al]` | 6 | 0,00 | 1,80 | 1,80 |
| `test_strengthening[fe]` | 14 | 0,00 | 1,80 | 1,81 |
| `test_phase_map_needs_three_elements[ni]` | 13 | 0,00 | 1,80 | 1,81 |
| `test_phase_map_needs_three_elements[al]` | 6 | -0,00 | 1,80 | 1,80 |
| `test_phase_map_needs_three_elements[fe]` | 8 | 0,00 | 1,80 | 1,81 |
| `test_results_do_not_survive_a_database_change` | 22 | -0,00 | 1,80 | 1,81 |

`before/slow__test_solidification.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_solidification[Сравнить равновесное и Scheil–Gulliver-ni]` | 32 | 0,35 | 0,46 | 0,47 |
| `test_solidification[Сравнить равновесное и Scheil–Gulliver-al]` | 93 | 1,17 | 1,63 | 1,64 |
| `test_solidification[Сравнить равновесное и Scheil–Gulliver-fe]` | 65 | 0,32 | 1,95 | 1,96 |
| `test_solidification[Только равновесное затвердевание-ni]` | 18 | -0,94 | 1,02 | 1,96 |
| `test_solidification[Только равновесное затвердевание-al]` | 95 | 0,69 | 1,71 | 1,72 |
| `test_solidification[Только равновесное затвердевание-fe]` | 59 | 0,25 | 1,96 | 1,97 |
| `test_solidification[Только Scheil–Gulliver-ni]` | 19 | -0,85 | 1,11 | 1,96 |
| `test_solidification[Только Scheil–Gulliver-al]` | 69 | 0,62 | 1,73 | 1,74 |
| `test_solidification[Только Scheil–Gulliver-fe]` | 62 | 0,25 | 1,97 | 1,99 |

`before/slow__test_binary_diagram.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_binary_diagram[ni]` | 28 | 0,31 | 0,41 | 0,44 |
| `test_binary_diagram[al]` | 64 | 0,86 | 1,27 | 1,29 |
| `test_binary_diagram[fe]` | 29 | 0,09 | 1,37 | 1,38 |

`before/slow__test_isopleth_diagram.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_isopleth_diagram[ni]` | 76 | 1,12 | 1,22 | 1,29 |
| `test_isopleth_diagram[al]` | 214 | 0,72 | 1,95 | 2,11 |
| `test_isopleth_diagram[fe]` | 73 | 0,10 | 2,04 | 2,09 |

`before/slow__test_ternary_diagram.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_ternary_diagram[ni]` | 52 | 0,68 | 0,78 | 0,79 |
| `test_ternary_diagram[al]` | 124 | 0,94 | 1,72 | 1,76 |
| `test_ternary_diagram[fe]` | 47 | 0,04 | 1,76 | 1,78 |

`before/slow__test_ternary_phase_map.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_ternary_phase_map[ni]` | 28 | 0,16 | 0,26 | 1,80 |
| `test_ternary_phase_map[al]` | 75 | 0,03 | 0,30 | 4,54 |
| `test_ternary_phase_map[fe]` | 50 | 0,02 | 0,31 | 4,52 |

**Ответ: всплеск, не утечка.**

* Основной процесс растёт только на первых тестах каждой базы (загрузка базы и моделей: 0,13–1,17 ГиБ
  за тест) и выходит на плато: 1,72 ГиБ к концу `notslow_a`, 1,80 — `notslow_b`, 1,97 —
  затвердевание, 2,04 — изоплеты. Дальше приросты — от −0,94 до +0,10 ГиБ. Отрицательные приросты
  (−0,94 при переходе с Fe на Ni) — память возвращается системе при смене базы.
* Две медленные группы подряд одним процессом (`deep/slow_half1`, затвердевание + бинарные, 12 тестов)
  дают плато 1,98 ГиБ, а не сумму плато групп (1,97 + 1,37): **память не накапливается от группы к
  группе.** Живой `AppTest` после каждого теста — 1 (текущий, на следующем тесте прежний уже собран),
  `gc.collect()` почти ничего не освобождает (не больше 0,05 ГиБ).
* Всплески — только там, где работает пул воркеров: сканы по температуре и составу, плотность по
  температуре, карта. На карте основной процесс держит 0,26–0,31 ГиБ, а дерево — 4,54 ГиБ (Al) и
  4,52 ГиБ (Fe): 4,2 ГиБ — это три воркера по ~1,4 ГиБ. После теста пул закрывается и память уходит.
* Три воркера — не константа. `thermogar_parallel_ui.pool_worker_count()` один раз на процесс берёт
  `auto_worker_count()` = `min(cpu_count − 1, свободно // 1,5 ГБ, 6)` (`app/thermogar_parallel.py:142-146`).
  Это сводит расходившиеся замеры карты из записи BL-27: 14-Б/14-Д мерили при 4,45 ГиБ свободных — 2
  воркера, 2 × 1,4 + 0,3 ≈ 3,15 ГиБ; 15-О — 5,89 ГиБ, 3 воркера, 4,53; 7,20 ГиБ у 13-Р2 соответствует
  5 воркерам (5 × 1,4 + 0,3), то есть 7,5–9 ГиБ свободных на старте — свободную память того прогона
  отчёт 13-Р2 не приводит, известно только 8,25 ГиБ на старте второй попытки всего файла. Число
  воркеров в 13-Р2 и 14-Д не записано — это расчёт по формуле, не замер.
* **Отсюда 8 ГиБ одним процессом:** плато основного процесса (~2 ГиБ) плюс пул карты, размер которого
  определён свободной памятью на первом рендере. Проверено: половина медленных кейсов одним процессом
  (`deep/slow_half2`: изоплеты, тернарные, карта; перед ней при 5,88 ГиБ свободных прошла `slow_half1`) — на `test_ternary_phase_map[al]`
  **весь прогон снят средой Claude Code** («stopped because the system is running low on memory»),
  плато 1,94 ГиБ + три воркера. Итоговой строки у этой попытки нет, в `summary.jsonl` её нет, свободная память на её старте не
  записана (раннер снят вместе с pytest); замер по тестам до снятия — `deep/slow_half2.memlog.jsonl`, посторонних
  процессов python после снятия не осталось.

## 2. Что держит память

| кандидат | проверка | результат |
|---|---|---|
| фигуры matplotlib | `plt.get_fignums()` после каждого теста | 0 во всех 59 тестах (Streamlit закрывает сам, п. 0.2) |
| `AppTest` / `session_state` | число живых `AppTest` после теста, `gc.collect()` | 1 живой (текущий) / 0 после выхода из фикстур; gc — не больше 0,05 ГиБ |
| `st.cache_resource` (`_cached_database`, `_load_physical_database_cached`), `st.cache_data` | сброс после каждого теста, этап `fix1`, изоплеты | плато 2,04 → 2,04 ГиБ, не изменилось |
| lru-кэши pycalphad (`build_functions`, `build_constraint_functions`, `_sample_phase_constitution`, по 100 записей) | сброс после каждого теста вместе с предыдущим, этап `fix2`, изоплеты | 2,04 → 1,95 ГиБ, в пределах разброса |
| пул воркеров (`_SHARED_ENGINES`) | число воркеров и пик дерева | **источник всплеска**; пул прежнего теста живёт до первого рендера следующего (закрывается при «смене базы» в новой сессии, `app/ThermoGar_app.py:6551`) |

Плато основного процесса около 2 ГиБ ограничено и сбросом кэшей не снимается. Что именно его держит
(скомпилированный код моделей, фрагментация кучи), я не выяснил — это нативная память, ни gc, ни сброс
Python-кэшей её не отдают. Поскольку плато не растёт от теста к тесту, дальше не копал.

## 3. Правка

`tools/test_ui_f.py`, фикстура `_bounded_memory` (autouse):

* `thermogar_parallel_ui._WORKER_COUNT` = `UI_TEST_POOL_WORKERS = 2` на время теста (`monkeypatch`).
  Пик файла перестаёт зависеть от свободной памяти в момент старта. Два воркера — это по-прежнему пул,
  путь приложения тот же. Числа от числа воркеров не зависят (это проверяет `test_parallel_engine`), а
  тесты `test_ui_f` проверяют поведение разделов: наличие результата, чистоту экрана и выгрузки по
  байтам.
* после теста — `close_shared_engines()` (пул не доживает до следующего теста), `plt.close("all")`,
  `gc.collect()`.

Сброс `st.cache_resource`/`st.cache_data` и lru-кэшей pycalphad в правку **не вошёл**: этапы `fix1`/`fix2`
показали, что он не помогает (п. 2). Логи `fix1` сняты с фикстурой, где был сброс st-кэшей, `fix2` — со
сбросом st-кэшей и кэшей pycalphad; итоговая фикстура — без них.

Проверка на карте отдельно (`fix1/slow__test_ternary_phase_map`, 6,01 ГиБ свободных — раньше при таких
условиях было бы 3 воркера): пик 4,53 → **3,16 ГиБ**, `3 passed`.

## 4. `test_ui_f -m slow` одним процессом после правки

Запущен при 6,01 ГиБ свободных; порог входа поднят ключом до 6,0 ГиБ (задание требует не меньше 4,5),
потому что ожидался пик около 4,9 и снятие средой, как в п. 1.

`results/wave15_o/after/slow.log.txt`: **`21 passed, 38 deselected in 1434.14s (0:23:54)`**, exit 0,
**пик дерева 4,91 ГиБ**, минимум свободной 1,06 ГиБ, аварийный порог не сработал.

`after/slow.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_solidification[Сравнить равновесное и Scheil–Gulliver-ni]` | 22 | 0,35 | 0,46 | 0,47 |
| `test_solidification[Сравнить равновесное и Scheil–Gulliver-al]` | 75 | 1,17 | 1,63 | 1,65 |
| `test_solidification[Сравнить равновесное и Scheil–Gulliver-fe]` | 92 | 0,32 | 1,95 | 1,96 |
| `test_solidification[Только равновесное затвердевание-ni]` | 18 | -0,90 | 1,05 | 1,96 |
| `test_solidification[Только равновесное затвердевание-al]` | 68 | 0,66 | 1,71 | 1,72 |
| `test_solidification[Только равновесное затвердевание-fe]` | 61 | 0,25 | 1,96 | 1,97 |
| `test_solidification[Только Scheil–Gulliver-ni]` | 37 | -0,86 | 1,10 | 1,97 |
| `test_solidification[Только Scheil–Gulliver-al]` | 95 | 0,63 | 1,73 | 1,74 |
| `test_solidification[Только Scheil–Gulliver-fe]` | 74 | 0,25 | 1,97 | 1,99 |
| `test_binary_diagram[ni]` | 29 | -0,35 | 1,63 | 1,98 |
| `test_binary_diagram[al]` | 40 | 0,03 | 1,66 | 1,72 |
| `test_binary_diagram[fe]` | 34 | 0,04 | 1,69 | 1,71 |
| `test_isopleth_diagram[ni]` | 96 | 0,26 | 1,95 | 2,02 |
| `test_isopleth_diagram[al]` | 213 | 0,11 | 2,06 | 2,24 |
| `test_isopleth_diagram[fe]` | 91 | 0,09 | 2,15 | 2,19 |
| `test_ternary_diagram[ni]` | 40 | -0,14 | 2,01 | 2,17 |
| `test_ternary_diagram[al]` | 134 | 0,01 | 2,01 | 2,09 |
| `test_ternary_diagram[fe]` | 51 | -0,00 | 2,01 | 2,03 |
| `test_ternary_phase_map[ni]` | 28 | 0,00 | 2,02 | 3,13 |
| `test_ternary_phase_map[al]` | 83 | 0,00 | 2,02 | 4,91 |
| `test_ternary_phase_map[fe]` | 50 | 0,00 | 2,02 | 4,65 |

**Пик 4,91 ГиБ больше цели 4,0.** Он складывается так: плато основного процесса 2,02 ГиБ плюс два
воркера карты по ~1,45 ГиБ на Al. Уложиться в 4,0 можно либо одним воркером (тогда карта считается
последовательно в основном процессе, и тест перестаёт проверять путь через пул), либо снижением плато
основного процесса, которое тестом не снимается (п. 2). Ни то, ни другое я не делал.

Сравнение «до/после» одним процессом:

| | до | после |
|---|---|---|
| одним процессом | 8,14 ГиБ, снят на 19-м кейсе из 21 (13-Р2); в 15-О не запускался; половина файла снята средой (п. 1) | **4,91 ГиБ, `21 passed`** |
| только группа карты | 3,15 (14-Д, 2 воркера) / 4,53 (15-О, 3) / 7,20 (13-Р2) | 3,16 (2 воркера всегда) |

Обычные тесты тоже стали легче: `test_ui_f -m "not slow"` одним процессом — пик 4,93 ГиБ в 14-Д,
**4,33 ГиБ** здесь (п. 6).

## 5. BL-17: таймаут, который снимает весь процесс

**Почему.** На Windows нет `SIGALRM`, поэтому pytest-timeout 2.4.0 берёт метод `thread`
(`.venv-windows\Lib\site-packages\pytest_timeout.py`):

```python
HAVE_SIGALRM = hasattr(signal, "SIGALRM")
if HAVE_SIGALRM:
    DEFAULT_METHOD = "signal"
else:
    DEFAULT_METHOD = "thread"
```

(строки 26–30). Таймер этого метода по срабатыванию печатает стеки и завершает процесс целиком:

```python
def timeout_timer(item, settings):
    """Dump stack of threads and call os._exit().

    This disables the capturemanager and dumps stdout and stderr.
    Then the stacks are dumped and os._exit(1) is called.
    """
    ...
        dump_stacks(terminal)
        terminal.sep("+", title="Timeout")
    except Exception:
        traceback.print_exc()
    finally:
        terminal.flush()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)
```

(строки 505–542). `os._exit` не даёт pytest дописать отчёт — итоговой строки у файла нет.

**Варианты.**

* (а) убрать `timeout` и держать медленные ячейки под `slow`. Метки стоят в
  `tools/test_backend_calculations.py` и `tools/test_phase_presets.py` — это не файлы волны. К тому же
  без таймаута настоящее зависание (как пул в 11K-4) висит бесконечно.
* (б) kwn-тесты в подпроцессе — правка тех же чужих файлов и отдельный механизм на каждый тест.
* (в) поднять порог — срабатывание всё равно убивает процесс, меняется только частота.
* **(г) — выбран, это отступление от списка задания.** Заменить сам метод `thread` в
  `tools/conftest.py`: у pytest-timeout для этого есть хук `pytest_timeout_set_timer`
  (`firstresult=True`, строки 114–121, «Can be overridden by plugins for alternative timeout
  implementation strategies»). Моя реализация (`tryfirst`) по срабатыванию поднимает в главном потоке
  исключение `TestTimeout` (наследник `BaseException`, чтобы `except Exception` в тесте его не
  проглотил) через `ctypes.pythonapi.PyThreadState_SetAsyncExc`. Тест падает как обычный `failed`,
  файл идёт дальше. Метки в чужих файлах не трогаются и продолжают работать. Если главный поток за
  `TIMEOUT_GRACE_S = 60` с исключение не принял (встал в C-коде), вызывается прежний
  `pytest_timeout.timeout_timer` — дамп стеков и `os._exit(1)`, так что настоящее зависание
  по-прежнему снимается. Для метода `signal` (не Windows) хук ничего не делает. Прежнее поведение
  включается переменной `THERMOGAR_TIMEOUT_EXIT=1`.

**Ограничения (г).** Исключение доставляется, только когда главный поток исполняет байткод Python;
`time.sleep` и долгий вызов C-кода его откладывают (до 60 с, потом срабатывает прежнее снятие).
Скрипт AppTest выполняется в своём потоке и после снятия теста досчитывает в фоне. Если таймер
сработает ровно на границе конца теста, отмена снимает ещё не доставленное исключение
(`PyThreadState_SetAsyncExc(id, NULL)`), но узкое окно гонки остаётся.

**Проверка.**

Синтетический файл `results/wave15_o/timeout_check/check_timeout_bl17.py` (шесть тестов: цикл Python
под таймаутом 2 с, тот же цикл с `except Exception`, `time.sleep(5)` под таймаутом 2 с, быстрый тест
под таймаутом, два теста без таймаута). Имя без `test_`, чтобы pytest из корня не собрал его сам; логи
ниже сняты до переименования, под именем `test_timeout_check.py`.

| режим | лог | итог |
|---|---|---|
| прежний (`THERMOGAR_TIMEOUT_EXIT=1`) | `old_behaviour.log.txt` | exit 1, лог кончается строкой `+++ Timeout +++` после первого же снятого теста, **итоговой строки нет** |
| новый | `new_behaviour.log.txt` | exit 1, **`3 failed, 3 passed in 9.33s`** |
| зависание в C дольше запаса (`THERMOGAR_TIMEOUT_GRACE_S=1`, `sleep(5)`) | `grace_fallback.log.txt` | exit 1, дамп стеков и `+++ Timeout +++`, итоговой строки нет — запасное снятие работает |

На настоящем файле — плагин `results/wave15_o/timeout_check/one_test_timeout.py` вешает таймаут 2 с на
один быстрый тест `test_startup_is_clean[ni]` (без таймаута он идёт 14 с), остальные тесты — без
таймаута:

```
PYTHONPATH=results/wave15_o/timeout_check THERMOGAR_TIMEOUT_ONE='test_startup_is_clean[ni]=2'
python -B -X utf8 -m pytest tools/test_ui_f.py -q -p no:cacheprovider -p one_test_timeout
    -k "test_startup_is_clean or test_phase_map_needs_three_elements"
```

`results/wave15_o/timeout_check/test_ui_f_one_timeout.log.txt`, exit 1:

```
FAILED tools/test_ui_f.py::test_startup_is_clean[ni] - Timeout (>2.0s) from p...
1 failed, 5 passed, 53 deselected in 55.26s
```

Исключение пришло в цикл ожидания AppTest (`streamlit/testing/v1/local_script_runner.py:195`,
`time.sleep(0.001)`), следующие пять тестов прошли.

Что осталось от BL-17: механизм снятия всего процесса закрыт для метода `thread` в `tools/`. Прогона
всего `tools/` одной командой в этой волне не было (п. 6 его не требует), и зависание пула из 11K-4 не
перепроверялось.

## 6. Пофайловые прогоны

Итоговый код ветки, по одному процессу на файл, `-m "not slow"`, порог входа 5,0 ГиБ.

| файл | свободно на старте | exit | итог | пик дерева | минимум свободной |
|---|---|---|---|---|---|
| `tools/test_ui_f.py` | 5,81 | 0 | **`38 passed, 21 deselected in 761.66s (0:12:41)`** | 4,33 | 1,64 |
| `tools/test_ui_g.py` | 5,94 | 0 | **`29 passed, 3 deselected, 2 warnings in 210.89s (0:03:30)`** | 0,60 | 5,34 |

Оба зелёные. Предупреждения `test_ui_g` — `RuntimeWarning: divide by zero` из
`kawin/precipitation/NucleationRate.py:190`, как в 15-Д и 15-З.

Замер по тестам `test_ui_f -m "not slow"` после правки (`final/notslow.memlog.jsonl`):

`final/notslow.memlog.jsonl`

| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |
|---|---|---|---|---|
| `test_startup_is_clean[ni]` | 24 | 0,13 | 0,24 | 0,24 |
| `test_startup_is_clean[al]` | 5 | 0,01 | 0,25 | 0,25 |
| `test_startup_is_clean[fe]` | 9 | 0,02 | 0,27 | 0,27 |
| `test_single_equilibrium[ni]` | 18 | 0,16 | 0,42 | 0,43 |
| `test_single_equilibrium[al]` | 19 | 0,62 | 1,04 | 1,14 |
| `test_single_equilibrium[fe]` | 16 | 0,34 | 1,39 | 1,43 |
| `test_temperature_scan[ni]` | 18 | 0,03 | 1,42 | 2,15 |
| `test_temperature_scan[al]` | 37 | 0,01 | 1,43 | 3,82 |
| `test_temperature_scan[fe]` | 39 | 0,00 | 1,43 | 3,24 |
| `test_concentration_scan[ni]` | 21 | 0,00 | 1,43 | 2,15 |
| `test_concentration_scan[al]` | 31 | 0,01 | 1,44 | 2,90 |
| `test_concentration_scan[fe]` | 61 | 0,00 | 1,44 | 2,27 |
| `test_energy_curve[ni]` | 9 | 0,02 | 1,46 | 1,47 |
| `test_energy_curve[al]` | 9 | 0,10 | 1,56 | 1,61 |
| `test_energy_curve[fe]` | 11 | 0,00 | 1,56 | 1,58 |
| `test_driving_force[ni]` | 10 | 0,07 | 1,64 | 1,65 |
| `test_driving_force[al]` | 14 | 0,07 | 1,71 | 1,80 |
| `test_driving_force[fe]` | 17 | -0,00 | 1,71 | 1,73 |
| `test_tzero_in_narrow_window[ni]` | 12 | 0,00 | 1,71 | 1,72 |
| `test_tzero_in_narrow_window[al]` | 9 | 0,00 | 1,71 | 1,72 |
| `test_tzero_in_narrow_window[fe]` | 57 | 0,01 | 1,72 | 1,73 |
| `test_density_single[ni]` | 14 | -0,01 | 1,70 | 1,72 |
| `test_density_single[al]` | 16 | 0,01 | 1,71 | 1,76 |
| `test_density_single[fe]` | 22 | 0,01 | 1,72 | 1,77 |
| `test_density_estimated_warning_is_shown_to_user` | 66 | 0,52 | 2,24 | 2,82 |
| `test_density_temperature_scan[ni]` | 12 | -0,23 | 2,01 | 2,25 |
| `test_density_temperature_scan[al]` | 35 | 0,01 | 2,02 | 4,37 |
| `test_density_temperature_scan[fe]` | 28 | -0,15 | 1,87 | 2,08 |
| `test_elastic_vrh[ni]` | 15 | 0,02 | 1,89 | 1,89 |
| `test_elastic_vrh[al]` | 17 | 0,01 | 1,90 | 1,95 |
| `test_elastic_vrh[fe]` | 22 | 0,02 | 1,92 | 1,96 |
| `test_strengthening[ni]` | 8 | 0,00 | 1,92 | 1,92 |
| `test_strengthening[al]` | 6 | -0,00 | 1,92 | 1,92 |
| `test_strengthening[fe]` | 10 | 0,00 | 1,92 | 1,92 |
| `test_phase_map_needs_three_elements[ni]` | 6 | -0,00 | 1,92 | 1,92 |
| `test_phase_map_needs_three_elements[al]` | 5 | -0,00 | 1,92 | 1,92 |
| `test_phase_map_needs_three_elements[fe]` | 8 | 0,00 | 1,92 | 1,92 |
| `test_results_do_not_survive_a_database_change` | 22 | 0,00 | 1,92 | 1,92 |

## 7. Git

`git log --oneline cc6c188..HEAD` — снят перед коммитом этого отчёта; сам коммит отчёта в список не
попал:

```
2fcd15a test(15-О): синтетическая проверка таймаута — имя без test_, таблицы замеров
6176e6d test(15-О): замеры памяти test_ui_f, проверка таймаута, логи
8a44f39 test(15-О): BL-27 — два воркера пула и закрытие пула после теста в test_ui_f
f38fb37 test(15-О): BL-17 — таймаут без снятия процесса, замер памяти по тестам
df3b151 docs(15-О): задание волны
```

`git status --short` в тот же момент:

```
?? tasks/WAVE15_O_REPORT.md
```

Копия отчёта — `C:\Users\gareg\Desktop\ThermoGar\tasks\WAVE15_O_REPORT.md`.
