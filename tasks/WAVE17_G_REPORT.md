**Регрессия красная: 2 файла** — `test_parallel_integration.py` и `test_ui_g.py`. **56 прогонов, суммарно 1,88 ч, максимальный пик дерева 4,86 ГиБ** (`test_ui_f -m slow` одним процессом). Снятий по памяти нет, не запущенных по порогу нет.

**Из двух красных один целиком от среды, второй — на девять десятых от среды.** Сессия идёт внутри MSIX-контейнера Claude Desktop, где `%LOCALAPPDATA%` виртуализован; проверка `app/thermogar_secure_io.py:239` это видит и отказывается работать. Контрольные прогоны со штатным ключом `THERMOGAR_STATE_ROOT` на непереадресуемом пути: `test_parallel_integration` — `6 passed`, `test_ui_g -m "not slow"` — `29 passed, 3 deselected`, оба ровно как в 14-Д. **После отделения среды красным остаётся один кейс: `test_ui_g::test_kwn_precipitation[fe]`, и это устаревшее ожидание теста, а не дефект продукта** (разбор — п. 3.3). Решение о выпуске — за мастером.

**Побайтовая сверка эталона `tools/backend_reference.md` — совпало полностью, ни одной изменившейся строки** (п. 4).

# Отчёт 17-Г — выпуск 0.4.2, часть 1: полная регрессия

Задание — `tasks/WAVE17_G_OPUS.md`. Дерево `D:\Pets\ThermoGar`, ветка `wave15-release`, HEAD `d3f3d1c`
(заморожено решением владельца 18.09.2026). Интерпретатор — `.venv-windows`, Python 3.11.9.
Результаты — `results/wave17_g/`.

**Код не менялся.** `app/`, `databases/`, `tools/` не тронуты: `git status --short` не показывает ни
одного `M` (см. «Git»). Дефект не чинился. `D:\Pets\Lilith` не открывался и в поиски не включался.
Ничего расчётного параллельно не запускалось.

---

## 0. Где посылка задания разошлась с тем, что найдено

1. **«Новые с волны 14» — файлы не с 14-й волны, а с 15-й.** По их собственным заголовкам:
   `test_precipitation_bl35.py` — BL-35, волны 15-В/15-Д; `test_wave15_z.py` — волна 15-З;
   `test_dropped_phases_text.py` — BL-8, волна 15-Л; `test_physical_overrides_toggle.py` — 15-У,
   BL-14. На состав регрессии это не повлияло: список собран заново по маске, а не по перечислению.
2. **Изменились ещё два файла, которых задание не называет.** `test_database_repair.py` — 41 кейс
   в 14-Д, сейчас 44; `thermogar_verified_properties_test.py` — 31 в 14-Д, сейчас 39 (последнее
   подтверждено и в 17-В, п. 2.3). `test_density.py` 35 → 66 — это и есть «расширен».
3. **14-Д гоняла `test_ui_f -m slow` пятью группами, а не по правилу 15-Т.** Правило заведено после
   14-Д. Правка 15-О (пул в два воркера, `tools/test_ui_f.py:200`) в дереве есть, поэтому правило
   применимо; свободной памяти на старте было 9,00 ГиБ, и раннер пошёл одним процессом.
4. **Дерева `C:\Users\gareg\Desktop\ThermoGar` больше нет** (переустановка, 17-Б). Правило RULES
   «копия отчёта кладётся и в `…\Desktop\ThermoGar\tasks\`» выполнить некуда — отчёт лежит только в
   рабочем дереве. На то же несуществующее дерево ссылаются раннер 14-Д и шапка
   `tools/backend_reference.md`.
5. **Окружение прогона отличается от 13-Р2 и 14-Д способом, который меняет исходы.** Подробно — в
   п. 3.2; коротко: `%LOCALAPPDATA%` виртуализован контейнером. До запуска это известно не было.

---

## 1. Состав регрессии и сверка с 14-Д

Список собран заново: `tools/test_*.py` и `tools/thermogar_*_test.py`. **36 файлов** — 29 pytest-файлов
и 7 сценарных скриптов. Наличие медленных кейсов проверено предполётным
`pytest --collect-only -q -m slow` по каждому файлу (`results/wave17_g/collect_preflight.jsonl`,
логи — `results/wave17_g/collect/`), а не поиском по тексту.

**Против 14-Д: добавилось 4 файла, не исчез ни один.**

| файл | 14-Д | 17-Г | что изменилось |
|---|---|---|---|
| `test_dropped_phases_text.py` | нет | 2 кейса | **добавлен** (BL-8, волна 15-Л) |
| `test_physical_overrides_toggle.py` | нет | 11 кейсов | **добавлен** (15-У, BL-14) |
| `test_precipitation_bl35.py` | нет | 11 кейсов | **добавлен** (BL-35, 15-В/15-Д) |
| `test_wave15_z.py` | нет | 15 кейсов | **добавлен** (волна 15-З) |
| `test_density.py` | 35 | 66 | расширен |
| `test_database_repair.py` | 41 | 44 | расширен |
| `thermogar_verified_properties_test.py` | 31 | 39 | расширен |
| остальные 29 | — | — | счёт кейсов совпал с 14-Д |

Счёт кейсов, совпавший с 14-Д дословно: `test_backend_calculations` 43 + 14, `test_ui_f` 38 + 21,
`test_ui_g` 29 + 3, `test_ui_h` 24 + 2, `test_precipitation_grid` 32, `test_parallel_engine` 15,
`test_parallel_integration` 6, `test_phase_presets` 15 + 6, `test_phase_presets_control` 0 + 1,
`test_density_thermal_expansion` 10 + 2, `test_liquidus_bisection` 0 + 2 и все `thermogar_*`, кроме
названного выше.

**Файлы с медленными кейсами — те же семь, что в 14-Д**, плюс `test_ui_f`:
`test_backend_calculations` (14 из 57), `test_density_thermal_expansion` (2 из 12),
`test_liquidus_bisection` (2 из 2), `test_phase_presets` (6 из 21), `test_phase_presets_control`
(1 из 1), `test_ui_g` (3 из 32), `test_ui_h` (2 из 26), `test_ui_f` (21 из 59).

**Сценарные скрипты — те же семь**, у них под pytest нет ни одного кейса (`no tests collected` без
`deselected`), поэтому они гоняются скриптами: `thermogar_converter_patch_test`,
`thermogar_diffusion_test`, `thermogar_fe_database_test`, `thermogar_physical_test`,
`thermogar_precipitation_test`, `thermogar_properties_test`, `thermogar_self_test`.

---

## 2. Порядок прогона

Раннер — `results/wave17_g/run_regress.py`, копия раннера 14-Д
(`results/wave14_d/regress/run_regress.py`) с тремя отличиями по заданию: логи и memlog в
`results/wave17_g/logs/` и `results/wave17_g/memlog/`, `THERMOGAR_MEMLOG` на каждый прогон,
`test_ui_f -m slow` по правилу 15-Т, и `THERMOGAR_BACKEND_REPORT` на два прогона
`test_backend_calculations` для пункта 4.

* каждый файл — отдельный процесс, по одному, `PYTHONHASHSEED=0`;
* `python.exe -B -X utf8 -m pytest tools/<файл> -q -m "not slow" -p no:cacheprovider`, отдельно
  `-m slow` по семи файлам;
* сценарии — `python.exe -P -s -B -X utf8 tools/<файл>.py --project-root D:\Pets\ThermoGar`;
* **порог входа 3,0 ГиБ — ключом раннера** (`REGRESS_ENTRY_GIB=3.0`), не константой; ожидание
  `REGRESS_WAIT_S=900`;
* **аварийный порог `E1_ABORT_FREE_GIB` = 1,0 ГиБ** читается из исходника
  `tools/study_hn62m_wave12.py` и **не менялся**; ни разу не сработал;
* `test_ui_f -m slow` — **одним процессом**: свободной памяти на старте 9,00 ГиБ при пороге правила
  15-Т 6,0 ГиБ. Делить на группы не понадобилось. Раннер решал это по факту в момент старта
  (`REGRESS_UI_F_SINGLE_GIB=6.0`); запасной путь на две группы `-k` в нём заведён и задействован не был;
* `THERMOGAR_MEMLOG` выставлялся на каждый прогон. У сценарных скриптов он ничего не пишет — хук
  живёт в `tools/conftest.py`, а pytest там не участвует; это ожидаемо, не сбой.

Замер памяти — рабочий набор **дерева** процессов, опрос раз в 2 с. Пик «—» означает, что процесс
кончился раньше первого опроса.

---

## 3. Итоги прогонов

Основной прогон: 51 прогон, 6226 с (1,73 ч). Сводка — `results/wave17_g/summary.jsonl`, логи —
`results/wave17_g/logs/`, замеры по тестам — `results/wave17_g/memlog/`.

| файл | режим | exit | итоговая строка pytest | итог | время, с | пик, ГиБ | мин. свободно, ГиБ |
|---|---|---:|---|---|---:|---:|---:|
| `test_backend_calculations.py` | -m "not slow" | 0 | `43 passed, 14 deselected, 4 warnings in 361.81s (0:06:01)` | зелёный | 365.2 | 1,73 | 7,04 |
| `test_database_repair.py` | -m "not slow" | 0 | `44 passed in 249.64s (0:04:09)` | зелёный | 252.8 | 2,89 | 6,14 |
| `test_density.py` | -m "not slow" | 0 | `66 passed in 182.61s (0:03:02)` | зелёный | 184.6 | 2,73 | 6,28 |
| `test_density_thermal_expansion.py` | -m "not slow" | 0 | `10 passed, 2 deselected in 0.58s` | зелёный | 2.0 | — | 9,03 |
| `test_dropped_phases_text.py` | -m "not slow" | 0 | `2 passed in 0.07s` | зелёный | 2.0 | — | 9,01 |
| `test_liquidus_bisection.py` | -m "not slow" | 5 | `2 deselected in 0.12s` | зелёный | 2.0 | — | 8,84 |
| `test_parallel_engine.py` | -m "not slow" | 0 | `15 passed in 62.42s (0:01:02)` | зелёный | 64.2 | 1,39 | 7,62 |
| `test_parallel_integration.py` | -m "not slow" | 2147483651 | `1 failed, 5 passed, 1 warning in 47.58s` | **КРАСНЫЙ** | 72.3 | 3,33 | 5,46 |
| `test_phase_presets.py` | -m "not slow" | 0 | `15 passed, 6 deselected in 46.23s` | зелёный | 48.2 | 1,52 | 5,84 |
| `test_phase_presets_control.py` | -m "not slow" | 5 | `1 deselected in 2.22s` | зелёный | 4.0 | 0,12 | 7,42 |
| `test_physical_overrides_toggle.py` | -m "not slow" | 0 | `11 passed in 187.88s (0:03:07)` | зелёный | 190.7 | 1,43 | 5,91 |
| `test_precipitation_bl35.py` | -m "not slow" | 0 | `11 passed, 1 warning in 36.33s` | зелёный | 38.2 | 0,37 | 7,65 |
| `test_precipitation_grid.py` | -m "not slow" | 0 | `32 passed, 13 warnings in 153.78s (0:02:33)` | зелёный | 156.6 | 0,84 | 7,34 |
| `test_ui_f.py` | -m "not slow" | 0 | `38 passed, 21 deselected in 624.15s (0:10:24)` | зелёный | 626.0 | 4,36 | 4,57 |
| `test_ui_g.py` | -m "not slow" | 1 | `8 failed, 21 passed, 3 deselected, 2 warnings in 170.13s (0:02:50)` | **КРАСНЫЙ** | 172.5 | 0,56 | 8,37 |
| `test_ui_h.py` | -m "not slow" | 0 | `24 passed, 2 deselected in 295.45s (0:04:55)` | зелёный | 296.9 | 0,54 | 8,23 |
| `test_wave15_z.py` | -m "not slow" | 0 | `15 passed, 2 warnings in 21.99s` | зелёный | 24.1 | 0,40 | 8,30 |
| `thermogar_active_state_io_test.py` | -m "not slow" | 0 | `5 passed, 2 warnings in 3.73s` | зелёный | 6.0 | 0,20 | 8,54 |
| `thermogar_converter_patch_test.py` | -m "not slow" | 5 | `no tests ran in 0.03s` | зелёный | 2.0 | — | 8,72 |
| `thermogar_db_cache_test.py` | -m "not slow" | 0 | `10 passed, 3 subtests passed in 0.30s` | зелёный | 2.0 | — | 8,71 |
| `thermogar_diffusion_test.py` | -m "not slow" | 5 | `no tests ran in 0.57s` | зелёный | 2.0 | — | 8,73 |
| `thermogar_fe_database_test.py` | -m "not slow" | 5 | `no tests ran in 1.92s` | зелёный | 4.0 | 0,15 | 8,56 |
| `thermogar_fe_internal_smoke_test.py` | -m "not slow" | 0 | `15 passed in 0.26s` | зелёный | 2.0 | — | 8,70 |
| `thermogar_paths_test.py` | -m "not slow" | 0 | `6 passed in 0.16s` | зелёный | 2.0 | — | 8,73 |
| `thermogar_physical_test.py` | -m "not slow" | 5 | `no tests ran in 0.02s` | зелёный | 2.0 | — | 8,73 |
| `thermogar_precipitation_test.py` | -m "not slow" | 5 | `no tests ran in 0.03s` | зелёный | 2.0 | — | 8,73 |
| `thermogar_properties_test.py` | -m "not slow" | 5 | `no tests ran in 0.10s` | зелёный | 2.0 | — | 8,71 |
| `thermogar_restricted_fe_core_test.py` | -m "not slow" | 0 | `15 passed, 17 subtests passed in 2.77s` | зелёный | 4.0 | 0,14 | 8,57 |
| `thermogar_secure_io_test.py` | -m "not slow" | 0 | `19 passed in 0.49s` | зелёный | 2.0 | — | 8,70 |
| `thermogar_self_test.py` | -m "not slow" | 5 | `no tests ran in 1.95s` | зелёный | 4.0 | 0,15 | 8,54 |
| `thermogar_state_migration_test.py` | -m "not slow" | 0 | `6 passed in 0.62s` | зелёный | 2.0 | — | 8,67 |
| `thermogar_verified_equilibrium_test.py` | -m "not slow" | 0 | `16 passed, 8 subtests passed in 1.07s` | зелёный | 2.0 | — | 8,70 |
| `thermogar_verified_loaders_test.py` | -m "not slow" | 0 | `18 passed in 0.36s` | зелёный | 2.0 | — | 8,69 |
| `thermogar_verified_physical_test.py` | -m "not slow" | 0 | `24 passed in 1.01s` | зелёный | 2.0 | — | 8,71 |
| `thermogar_verified_properties_test.py` | -m "not slow" | 0 | `39 passed, 5 subtests passed in 3.95s` | зелёный | 6.0 | 0,20 | 8,49 |
| `thermogar_verified_state_test.py` | -m "not slow" | 0 | `24 passed in 0.92s` | зелёный | 2.0 | — | 8,69 |
| `test_backend_calculations.py` | -m slow | 0 | `14 passed, 43 deselected, 2 warnings in 783.99s (0:13:03)` | зелёный | 786.4 | 1,77 | 7,15 |
| `test_density_thermal_expansion.py` | -m slow | 0 | `1 passed, 10 deselected, 1 xfailed in 36.75s` | зелёный | 38.1 | 1,35 | 7,54 |
| `test_liquidus_bisection.py` | -m slow | 0 | `2 passed in 262.42s (0:04:22)` | зелёный | 264.9 | 1,28 | 7,59 |
| `test_phase_presets.py` | -m slow | 0 | `6 passed, 15 deselected in 221.67s (0:03:41)` | зелёный | 224.7 | 1,70 | 7,12 |
| `test_phase_presets_control.py` | -m slow | 0 | `1 passed in 707.37s (0:11:47)` | зелёный | 710.2 | 3,03 | 5,87 |
| `test_ui_g.py` | -m slow | 1 | `2 failed, 1 passed, 29 deselected, 3 warnings in 176.91s (0:02:56)` | **КРАСНЫЙ** | 178.5 | 0,46 | 8,56 |
| `test_ui_h.py` | -m slow | 0 | `2 passed, 24 deselected in 47.80s` | зелёный | 50.1 | 1,44 | 7,58 |
| `test_ui_f.py` | -m slow, одним процессом | 0 | `21 passed, 38 deselected in 1156.50s (0:19:16)` | зелёный | 1159.5 | **4,86** | **4,40** |
| `thermogar_converter_patch_test.py` | сценарий | 0 | `RESULT: PASSED` | зелёный | 2.0 | — | 9,12 |
| `thermogar_diffusion_test.py` | сценарий | 0 | `RESULT: PASSED` | зелёный | 16.1 | 0,20 | 8,84 |
| `thermogar_fe_database_test.py` | сценарий | 0 | `RESULT: PASSED` (последняя строка вывода — путь отчётов в `results\validation\stage13_2`, каталог в `.gitignore`) | зелёный | 176.5 | 2,68 | 6,37 |
| `thermogar_physical_test.py` | сценарий | 0 | `RESULT: PASSED` | зелёный | 2.1 | — | 9,09 |
| `thermogar_precipitation_test.py` | сценарий | 0 | `RESULT: PASSED` | зелёный | 24.1 | 0,27 | 8,73 |
| `thermogar_properties_test.py` | сценарий | 0 | `RESULT: PASSED` | зелёный | 4.0 | 0,17 | 8,85 |
| `thermogar_self_test.py` | сценарий | 0 | `RESULT: SOFTWARE REGRESSION PASSED — NOT MATERIAL QUALIFICATION` (последняя строка вывода — разделитель) | зелёный | 34.1 | 0,90 | 8,06 |

У `test_parallel_integration` в столбце exit стоит `2147483651` (`0x80000003`) — процесс умер на
падении Tk **после** того, как pytest написал итоговую строку; в таблицу вынесена сама итоговая
строка, разбор — п. 3.2.

### 3.1. Контрольные прогоны (отступление 17Г-1)

Контроль понадобился, чтобы отделить среду от дефекта доказательно, а не на словах. Код не менялся;
менялись только переменные окружения, обе — штатные. `THERMOGAR_STATE_ROOT` читает
`app/thermogar_paths.py:180`. `MPLBACKEND=Agg` — то же, что `tools/thermogar_precipitation_test.py:17`,
`thermogar_properties_test.py:38` и `thermogar_self_test.py:23` делают сами; `tools/test_ui_g.py:36` и
`test_backend_calculations.py:54` ставят `matplotlib.use("Agg")` прямо в коде, а
`test_parallel_integration.py` и `test_ui_f.py` — нет. Контроль шёл **после** основного прогона, не
параллельно. Раннер — `results/wave17_g/run_control.py`, логи — `results/wave17_g/control/logs/`.

| прогон | `%LOCALAPPDATA%` | matplotlib | итоговая строка | exit | с |
|---|---|---|---|---:|---:|
| `test_parallel_integration -m "not slow"` (основной) | перенаправлен | TkAgg | `1 failed, 5 passed, 1 warning in 47.58s` | 2147483651 | 72,3 |
| `test_parallel_integration -m "not slow"` | перенаправлен | TkAgg | процесс убит `Windows fatal exception: code 0x80000003` на 3-м кейсе, итоговой строки нет | 2147483651 | 96,3 |
| `test_parallel_integration -m "not slow"` | перенаправлен | **Agg** | `1 failed, 5 passed in 32.29s` — тот же `SecureIOError` | 1 | 32,3 |
| `test_parallel_integration -m "not slow"` | **`D:` (`THERMOGAR_STATE_ROOT`)** | **Agg** | **`6 passed in 58.20s`** | **0** | 58,2 |
| `test_ui_g -m "not slow"` | **`D:`** | Agg (в коде файла) | **`29 passed, 3 deselected, 2 warnings in 180.76s`** | **0** | 182,6 |
| `test_ui_g -m slow` | **`D:`** | Agg (в коде файла) | `1 failed, 2 passed, 29 deselected, 3 warnings in 177.57s` | 1 | 180,5 |

Состояние контроля писалось в `results/validation/wave17_g_control_state` — путь закрыт
`.gitignore`, в репозиторий не попадает. Установленная программа и настоящий
`%LOCALAPPDATA%\ThermoGar` не трогались: контейнер и так пишет в свой `LocalCache`.

### 3.2. Разбор: среда

**Что происходит.** `app/thermogar_secure_io.py:239` сличает путь, который вернул
`GetFinalPathNameByHandle`, с запрошенным, и отказывается работать, если они разошлись. В этой
сессии они расходятся:

| проверка пути `C:\Users\gareg\AppData\Local\ThermoGar` | результат |
|---|---|
| `GetFileAttributesW` | `0x10` — бит `FILE_ATTRIBUTE_REPARSE_POINT` (`0x400`) **не** выставлен |
| `os.path.islink` | `False` |
| `GetFinalPathNameByHandle`, с `FILE_FLAG_OPEN_REPARSE_POINT` и без | `\\?\C:\Users\gareg\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\ThermoGar` |

Каталог не симлинк и не junction, но конечный путь у него другой. Это перенаправление файловой
системы MSIX: процессы тестов — потомки упакованного Claude Desktop 2.110.1
(`CLAUDE_CODE_ENTRYPOINT=claude-desktop`, семейство пакета `Claude_pzs8sxrjxfjjc`), и для них
`%LOCALAPPDATA%` виртуализован. Замер — `results/wave17_g/localappdata_probe.json`.

**Защита отрабатывает правильно.** Она и должна отказывать, когда дескриптор ведёт не туда, куда
просили. Косвенное подтверждение: `thermogar_secure_io_test` — `19 passed`, сам модуль на временных
каталогах работает без нареканий; спотыкается ровно путь `%LOCALAPPDATA%`.

**Что от этого упало.**

| файл, режим | падений от среды | тексты |
|---|---:|---|
| `test_parallel_integration`, `not slow` | 1 | `Windows handle escaped canonical path: …\ThermoGar` |
| `test_ui_g`, `not slow` | 8 | 6 × то же; 2 × `Библиотека не выгружена: Не удалось записать файл в папку данных ThermoGar.` |
| `test_ui_g`, `slow` | 1 | `Библиотека не выгружена: …` (`test_ni_kwn_reaches_a_precipitated_state`) |

Стек у всех один: `thermogar_workspace.record_history` → `thermogar_secure_io.atomic_update_bytes` →
`exclusive_writer` → `_win_open_handle:240`. **Доказано контролем:** при `THERMOGAR_STATE_ROOT` на
`D:` все десять падений исчезают, `test_parallel_integration` даёт `6 passed`,
`test_ui_g -m "not slow"` — `29 passed, 3 deselected` (счёт 14-Д).

**Побочный артефакт той же среды — падение Tk.** `Tcl_AsyncDelete: async handler deleted by the
wrong thread`, exit `2147483651` (`0x80000003`). Возникает в `test_parallel_integration`, потому что
этот файл не ставит `Agg`, matplotlib берёт TkAgg, а приложение рисует из рабочих потоков
(`UserWarning: Starting a Matplotlib GUI outside of the main thread will likely fail`,
`app/ThermoGar_app.py:3600`). В основном прогоне авария случилась **после** итоговой строки pytest и
результатов не скрыла; в первом контроле — до неё, и прогон пришлось повторить с `Agg`. Числа
регрессии от этого не зависят: с перенаправленным `%LOCALAPPDATA%` исход одинаков и с Tk, и с Agg
(`1 failed, 5 passed`).

### 3.3. Разбор: единственное падение, которое средой не объясняется

**`test_ui_g::test_kwn_precipitation[fe]`** (BCC_A2 / M23C6, 700 °C, 40 классов сетки, 0,001 ч).
В контроле, где папка данных исправна, на экране остаётся ровно одно сообщение:
`['Одна или несколько внутренних проверок не пройдены.']`.

Диагностика — `results/wave17_g/kwn_fe_quality_probe.py`, вывод — `kwn_fe_quality_probe.txt`; она
повторяет шаги теста один в один и печатает таблицу `PrecipitationResult.quality`, по которой
`app/thermogar_precipitation.py:1619` и решает, что писать на экран. Из девяти проверок **провалена
одна**:

| проверка | статус |
|---|---|
| Время возрастает | пройдена |
| Температура конечна | пройдена |
| Объёмная доля 0–1 | пройдена |
| Радиус неотрицателен | пройдена |
| Плотность неотрицательна | пройдена |
| **Состав матрицы допустим** | **ошибка** |
| Объёмная доля не упёрлась в 100 % | пройдена |
| Ширина класса меньше критического радиуса | пройдена (ширина 0,245 нм) |
| Зародыш не меньше минимального радиуса сетки | пройдена (минимум сетки 0,2 нм) |

И провалена она **не по числам, а по построению**: `app/thermogar_precipitation.py:610-612` ставит её
в «ошибка» всегда, когда выставлен `stop_note`:

```python
if stop_note:
    add("Состав матрицы допустим", False, stop_note)
```

`stop_note` здесь — механизм BL-35 волны 15:

> Расчёт остановлен на 1.418 с модельного времени (0.0003938 ч): доля C в матрице стала 0 ат. %,
> баланс масс нарушен. Показана часть расчёта до остановки. Причина: при движущей силе по базе
> зарождение практически безбарьерное, и выделение вычерпывает добавки из матрицы быстрее, чем
> модель это выдерживает; см. `docs/LIMITS_OF_APPLICABILITY.md`.

Расчёт при этом дал 1435 строк кинетики, исключения нет, остальные восемь проверок пройдены.

**Это ровно то поведение, которое волна 15 и закладывала.** `tools/test_precipitation_bl35.py`
описывает его дословно — «приложение должно вернуть посчитанную часть и **ошибку проверки „Состав
матрицы допустим“**, а не исключение», — и этот файл в регрессии зелёный (`11 passed, 1 warning`).
А `test_ui_g::test_kwn_precipitation` требует `new_errors(app) == []` (`tools/test_ui_g.py:388`);
это ожидание написано до BL-35 и под новое поведение не обновлено. В 14-Д кейс проходил потому, что
14-Д гонялась на ветке `wave14-kwnlimit` (`eb4436f`), куда код волн 15–16 не входил.

**Классификация: дефект теста, не продукта.**

**Чего я не проверял и что оставляю мастеру.** Правильно ли, что ячейка Fe с этими параметрами вообще
упирается в остановку по балансу масс, — вопрос физики и границ применимости, а не регрессии.
Соседняя ячейка того же расчёта в `test_backend_calculations` (сетка (0,5; 10) нм × 30 по 13-Р2) в
остановку не упирается: `проверки качества = True`, 2391 строка кинетики, эталон совпал. Решать,
править тест или менять поведение, — мастеру; **я не менял ни того, ни другого.**

### 3.4. Падения и снятия — свод

**Снятий по памяти нет.** Аварийный порог 1,0 ГиБ ни разу не сработал, минимум свободной за всю
регрессию — 4,40 ГиБ (`test_ui_f -m slow`). Не запущенных по порогу входа нет. Это отличие от 14-Д,
где `thermogar_fe_database_test` снимался и требовал повтора; здесь он прошёл с первого раза
(`RESULT: PASSED`, 176,5 с, пик 2,68 ГиБ).

| № | кейс | файл, режим | разбор |
|---:|---|---|---|
| 1 | `test_temperature_scan_tables_match_with_and_without_pool` | `test_parallel_integration`, `not slow` | **среда** — доказано контролем (`6 passed`) |
| 2–4 | `test_diffusion_single_phase[ni/al/fe]` | `test_ui_g`, `not slow` | **среда** |
| 5–6 | `test_diffusion_homogenization[ni/fe]` | `test_ui_g`, `not slow` | **среда** |
| 7–8 | `test_kwn_precipitation[ni/al]` | `test_ui_g`, `not slow` | **среда** |
| 9 | `test_kwn_size_grid_is_validated` | `test_ui_g`, `not slow` | **среда** |
| 10 | `test_ni_kwn_reaches_a_precipitated_state` | `test_ui_g`, `slow` | **среда** |
| 11 | `test_kwn_precipitation[fe]` | `test_ui_g`, `slow` | **дефект теста** — устаревшее ожидание относительно BL-35 (п. 3.3) |

Единственный `xfailed` за регрессию — `test_density_thermal_expansion -m slow`
(`1 passed, 10 deselected, 1 xfailed`), тот же, что в 13-Р2 и 14-Д; ожидаемый, не падение.

Прогоны с exit 5 (`test_liquidus_bisection` и `test_phase_presets_control` в `not slow`, семь
сценариев под pytest) — штатный исход «нет кейсов под маркером», как в 11R, 13-Р2 и 14-Д.

---

## 4. Побайтовая сверка эталона `tools/backend_reference.md`

**Расхождений нет: ни одна строка эталона не изменилась, править нечего.**

Сличены все 57 ячеек матрицы (19 видов × Ni/Al/Fe) из отчётов по ячейкам, записанных
`THERMOGAR_BACKEND_REPORT` в двух прогонах: `43 passed, 14 deselected, 4 warnings in 361.81s` и
`14 passed, 43 deselected, 2 warnings in 783.99s`. Все 57 — `PASS`, ни одного `XFAIL`. Развёрнутые
числа — `results/wave17_g/backend/cells_flat.txt` и `cells_dump.txt`, разбор по разделам —
`results/wave17_g/backend/reference_check.md`.

Версии пакетов совпадают с записанными в шапке эталона: pycalphad 0.11.2, scheil 0.3.0, kawin 0.5.0,
numpy 2.4.6, scipy 1.17.1, symengine 0.13.0, pandas 3.0.5, pytest 9.1.1, pytest-timeout 2.4.0
(`results/wave17_g/pip_list.txt`).

| раздел эталона | исход |
|---|---|
| Списки фаз и правило C15_LAVES — ni 99/15/15, al 195/64/64, fe 132/35/**34** | совпало |
| Матричная фаза — ni `FCC_A1`, al `GP_MAT`, fe `BCC_B2` | совпало |
| Равновесие: точка при T, T-скан, X-скан — все три базы | совпало |
| Диаграммы: бинарные, изоплеты, тройные сечения, карты 4×4 | совпало, включая правки 13-Р2 (ni 8 zpf, fe 42 zpf, fe 12 zpf) |
| Затвердевание: равновесное и Scheil — все три базы | совпало |
| Энергии: min GM, движущая сила, T₀ | совпало |
| Свойства: плотность и VRH/упрочнение | совпало, включая правки 13-Р2 (ni 7310.91, al 2643.74, fe 7575.68) |
| Кинетика: диффузия и KWN | совпало, включая правки 13-Р2 (ni 246 строк, fe 2391 строка) |
| Проекты / batch | совпало |
| «Где Fe и Al не считаются» — ни одна из трёх ячеек не отказывает | совпало с состоянием 13-Р2 |

**Времена ячеек исходами не считались** — эталон сам объявляет их разброс до 1,5×, и 13-Р2 по той же
причине их не сличала.

---

## 5. Отступления и замечания

* **17Г-1. Контрольные прогоны сверх задания** (п. 3.1). Задание требует разобрать каждое падение как
  «дефект продукта / среда / тест». На логах основного прогона это было бы предположением; контроль
  делает это измерением. Код не менялся, аварийный порог не трогался, контроль шёл после основного
  прогона. Пять прогонов, 550 с.
* **17Г-2. `MPLBACKEND=Agg` в контроле** по `test_parallel_integration`. Без него падение Tk
  уничтожало итоговую строку pytest. Переменная штатная, её же ставят три сценарных скрипта проекта.
  На исход она не влияет: с перенаправленным `%LOCALAPPDATA%` результат одинаков с Tk и с Agg.
* **17Г-3. `test_ui_f -m slow` одним процессом, а не пятью группами, как в 14-Д** — по правилу 15-Т и
  по факту свободной памяти (9,00 ГиБ при пороге 6,0). Пик 4,86 ГиБ против замеренных 15-О 4,91.
* **17Г-4. Копия отчёта на Рабочий стол не положена** — дерева `C:\Users\gareg\Desktop\ThermoGar`
  не существует (п. 0.4).
* **17Г-5. Дефект не чинился.** По заданию: найден — стоп и доклад. `tools/test_ui_g.py` не правился.
* **Замечание.** Регрессия в виртуализованном `%LOCALAPPDATA%` не годится как основание для выпуска:
  десять кейсов из одиннадцати упавших проверяют не физику, а работу с папкой данных, и в этой среде
  они не проверяются вовсе. Полноценный прогон нужен вне контейнера — либо из обычного сеанса, либо
  с `THERMOGAR_STATE_ROOT`, как в контроле.

---

## 6. Git

`git log --oneline -3` — дословно:

```
d3f3d1c chore(17-В): зависимости стенда тестов (pytest-timeout), правило в RULES
adeed14 restore(17-Б): волны 14–16 из рабочего дерева ThermoGar-w15e (ed8f989), история коммитов утрачена при переустановке
8c1458e docs(13-Ф2): решения мастера по BL-26, BL-19/BL-29, BL-28; строки 13-Е и 13-Ф2 в реестре
```

`git status --short` перед коммитом — дословно:

```
?? "Claude outputs/"
?? PEREDACHA_MASTERA.md
?? PRAVILA_VZAIMODEYSTVIYA_VLADELEC_MASTER.md
?? results/wave17_b/
?? results/wave17_g/
?? tasks/WAVE17_A_REPORT.md
?? tasks/WAVE17_B_REPORT.md
?? tasks/WAVE17_G_OPUS.md
?? tasks/WAVE17_V_REPORT.md
?? tasks/lilith_16A/
```

Ни одного `M`: отслеживаемый код не тронут. В коммит идут только `results/wave17_g/`,
`tasks/WAVE17_G_OPUS.md` и этот отчёт. Ветка не пушилась, в `main` не вливалась, тег не ставился.
