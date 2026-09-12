# Волна 11R — отчёт

**Ветка:** `wave11-release`, рабочее дерево `C:\Users\gareg\Desktop\ThermoGar-w11r`.
**Python:** `C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe`, `PYTHONHASHSEED=0`.
**Порядок:** 11R-1 → 11R-2 → 11R-3 → 11R-4 → 11R-5 → 11R-6, с одним названным отступлением
(версия поднята до сборки установщика, см. 11R-4).

---

## Готов ли выпуск

**Да.** Регрессия прошла, установщик собран и проверен дымовым прогоном 8/8, версия поднята,
журнал изменений написан. Подробности — по пунктам ниже; всё, что упало по дороге, разобрано и
названо, ничего не пропущено молча.

Три вещи, которые мастеру стоит знать до пуша:

1. **`pytest tools\` одной командой на этой машине не проходит** — не из-за дефекта продукта, а
   из-за двух свойств прогона (таймаут kwn-ячейки железа снимает весь процесс; набор целиком в
   одном процессе подвешивает `test_parallel_engine`). Регрессия выполнена пофайлово, как в
   релизном прогоне 0.3.1. Разбор — 11R-3.
2. **Найден и починен дефект установщика:** удаление оставляло каталог `licenses\`.
3. **Полный интервал кристаллизации заменён интервалом хрупкости** — 11R-2.

---

## 11R-1. Слияние 11Q

### Предмержевая проверка

В `tasks\` лежало шесть неотслеживаемых файлов. Из них слиянию мешал один —
`tasks/WAVE11Q_REPORT.md`, он есть в `wave11-final`. По `RULES.md`, раздел «Концы строк»,
сравнивалось нормализованное содержание:

| | Размер | Строк | SHA-256 |
|---|---|---|---|
| блоб `wave11-final:tasks/WAVE11Q_REPORT.md` | 23893 | 332 | `aa84f5a2…ba42` |
| местная копия, CR сняты | 23893 | 332 | `aa84f5a2…ba42` — совпал |

Размеры совпали и без нормализации: местная копия уже в LF. Побайтовый дубль отслеживаемого
файла — удалён по исключению из раздела «Удаление» `RULES.md`; слияние вернуло те же байты.

`tasks/WAVE11N_LIGHT_OPUS.md`, `tasks/WAVE11Q_OPUS.md`, `tasks/WAVE11R_RELEASE_OPUS.md`,
`REPORT_APP-576.md`, `ZADACHA_APP-576_TERMOGAR_SOLIDUS_VJ159.md` и `uliki_576/` ни в одной ветке
не отслеживаются и не тронуты. Посторонние файлы задачи APP-576 не трогались.

### Слияние и рабочее дерево

```
Merge made by the 'ort' strategy.
 docs/HN62M_STUDY.md                           | 116 +++++++--
 results/hn62m_tech/_progress.json             |  10 +
 results/hn62m_tech/cache/a1_eq_pdens500.jsonl |  48 ++++
 results/hn62m_tech/j4_memory_q1_1.json        |  16 ++
 results/hn62m_tech/q1_residual_solidus.csv    |   4 +
 results/hn62m_tech/q1_summary.json            | 133 +++++++++++
 tasks/REGISTER.md                             |  37 ++-
 tasks/WAVE11Q_REPORT.md                       | 332 ++++++++++++++++++++++++++
 tools/study_hn62m_wave11.py                   | 284 +++++++++++++++++++++-
 9 files changed, 954 insertions(+), 26 deletions(-)
```

Конфликтов нет. Коммит слияния — `834624f`. Рабочее дерево заведено:
`git worktree add C:\Users\gareg\Desktop\ThermoGar-w11r -b wave11-release main`.

---

## 11R-2. Интервал хрупкости

### Ответ одной фразой

**Главной величиной стал интервал хрупкости 64,6 K между долями твёрдого 0,90 (1328,2 °C) и
0,99 (1263,6 °C); полный интервал по Шейлю оставлен справочной оценкой снизу «не менее 112,9 K,
не сходится». Дешёвая проверка волны 11Q сошлась: равновесные солидусы остаточных жидкостей,
взятые на одной и той же доле твёрдого 0,95, дали 1264,78 / 1264,69 / 1264,78 °C — разброс
0,09 K, набор устойчивых фаз один и тот же.**

### Числа

Величины взяты из кривых трёх прогонов 11J-2 (`cache/child_j2_1_force.json`), пути не
пересчитывались. Температура при доле твёрдого — линейная интерполяция между двумя соседними
**посчитанными** точками, тем же правилом, что и `temperature_at_fraction`.

| Доля твёрдого | `pdens` 100 | 300 | 500 | Размах, K |
|---|---|---|---|---|
| 0,50 | 1364,04 | 1364,05 | 1364,04 | 0,013 |
| 0,90 | **1328,20** | **1328,21** | **1328,20** | **0,016** |
| 0,95 | 1310,44 | 1310,47 | 1310,44 | 0,023 |
| 0,98 | не достигнута | не достигнута | 1275,82 | — |
| 0,99 | не достигнута | не достигнута | **1263,63** | — |

```
T(доля твёрдого 0,90) = 1328,2 °C
T(доля твёрдого 0,99) = 1263,6 °C
интервал хрупкости    = 64,6 K
равновесный интервал  = 30,5 K
```

### Что сделано в документе

`docs/HN62M_STUDY.md`, разделы 3 и 10.1 переписаны:

* интервал хрупкости назван главной величиной, полный интервал — справочной оценкой снизу
  «не менее 112,9 K, ряд не сходится»;
* оговорено прямо, что **границы 0,90 и 0,99 — соглашение, а не физика**, что в любом разумном
  его варианте числа в этом окне устойчивы (размах трёх прогонов 0,03 K), а полный интервал
  такой устойчивостью не обладает;
* оговорено, что **верхняя граница подтверждена тремя прогонами** (размах 0,016 K), а **нижняя
  получена из одного**: уровень 0,99 достигнут только при `pdens` 500, поэтому 1263,6 °C, а с
  ней и 64,6 K, могут немного сдвинуться;
* равновесный интервал 30,5 K приведён рядом: разница с 64,6 K и есть мера неравновесности;
* история числа сохранена и продолжена: 94 → 79,0 → 83,0 → 112,9 K → интервал хрупкости 64,6 K,
  с отдельным абзацем «почему ряд оборван и заменён другой величиной» (приращения растут:
  +4,0 K, затем +29,9 K — ряд расходится).

Заодно приведены в соответствие `docs/HN62M_STUDY.md` (шапка, раздел 10.3, сводка для практики)
и `docs/LIMITS_OF_APPLICABILITY.md`, где интервал кристаллизации назывался как выживший вывод.

### Дешёвая проверка: три солидуса на одной доле твёрдого

Постановка волны 11Q выполнена: составы остаточных жидкостей взяты **на одной и той же доле
твёрдого 0,95**, где посчитаны все три прогона, и для каждого найден равновесный солидус — тем
же методом, что в 11Q (половинное деление, точность 0,1 K, вилка 700…1400 °C, `pdens` 500,
режим «все фазы»).

| `pdens` пути | T пути при доле 0,95, °C | Равновесный солидус, °C | Устойчивые фазы ниже него | Равновесий | Секунд |
|---|---|---|---|---|---|
| 100 | 1310,44 | **1264,78** | γ, σ, M6C, TI4C2S2, MNS_Q | 15 | 147,2 |
| 300 | 1310,47 | **1264,69** | γ, σ, M6C, TI4C2S2, MNS_Q | 15 | 146,0 |
| 500 | 1310,44 | **1264,78** | γ, σ, M6C, TI4C2S2, MNS_Q | 15 | 128,2 |

Вердикт программы дословно:

```
11R-2: три значения сошлись: разброс 0.09 K при пороге 5.0 K — метод исправен, а разъезд 56,7 K
в волне 11Q объясняется именно тем, что составы брались в разных точках пути
```

**Записано как подтверждение, что метод исправен.** Это проверка согласованности, а не ответ на
вопрос о конце затвердевания: на доле твёрдого 0,95 затвердевание ещё не кончилось, и 1264,8 °C
концом затвердевания не является.

Счёт: 460,5 с, пик набора 1,83 ГиБ, минимум свободной памяти 4,68 ГиБ, прирост подкачки 0,00 ГиБ.

Код — подпункт `r1` в `tools/study_hn62m_wave11.py` (тяжёлая часть в потомке, как у `q1`).
Результаты — `results/hn62m_tech/r1_summary.json`, `r1_fraction_check.csv`,
`r1_same_fraction_solidus.csv`.

---

## 11R-3. Полная регрессия

### Отступление от буквы задания и его причина

Задание требует «обычный прогон `pytest tools\` целиком». **Он на этой машине не доходит до
конца, и это воспроизводится.** Прогон запускался дважды и оба раза срывался:

1. **Первый срыв — на 55-м тесте, `test_kwn_module[fe]`.** Итоговой строки нет: вместо неё
   `pytest-timeout` напечатал дамп стека и снял весь процесс. Дословно последняя строка:

   ```
   +++++++++++++++++++++++++++++++++++ Timeout +++++++++++++++++++++++++++++++++++
   ```

   Причина названа комментарием в самом тесте (волны 11L и 11P): ячейка железа переваливает за
   `SLOW_TIMEOUT = 600` с, а на Windows `pytest-timeout` работает методом `thread` и по
   срабатыванию снимает весь процесс pytest, а не один тест. Пометка `slow`, поставленная
   волной 11P, спасает обычный прогон `-m "not slow"`, но прогон **целиком** включает и
   медленные, поэтому упирается в ту же ячейку. Exit 1.

2. **Второй срыв — зависание на 128-м тесте**,
   `test_parallel_engine.py::test_sequential_and_parallel_agree_bytewise`, в прогоне
   `pytest tools\ -m "not slow"`. Тест 49 минут стоял на месте при собственном
   `subprocess.run(..., timeout=900)`, который так и не сработал; процесс pytest в это время
   держал 3,1 ГиБ и жёг ядро. Тот же файл **отдельным прогоном идёт 70 с и даёт 15 passed**,
   поэтому дело не в тесте, а в том, что весь набор живёт в одном процессе. Прогон снят вручную.

По `RULES.md` («Если пункт падает по памяти — уменьшать сетку, а не повторять то же самое»)
регрессия выполнена **пофайлово** — ровно так, как её гнал релизный прогон 0.3.1
(`TESTS_RELEASE_0.3.1.md`, часть 2). Команда на файл:

```
python.exe -B -X utf8 -m pytest tools/<файл> -q -m "not slow"
python.exe -B -X utf8 -m pytest tools/<файл> -q -m slow
```

### 1. Обычный прогон (`-m "not slow"`), пофайлово

Итоговые строки дословно:

| Файл | exit | Итоговая строка |
|---|---|---|
| `test_backend_calculations` | 0 | `43 passed, 14 deselected, 4 warnings in 382.32s (0:06:22)` |
| `test_database_repair` | 0 | `34 passed in 280.55s (0:04:40)` |
| `test_density` | 0 | `35 passed in 197.74s (0:03:17)` |
| `test_density_thermal_expansion` | 1 → 0 | `1 failed, 9 passed, 2 deselected in 0.75s` → после правки `10 passed, 2 deselected in 1.04s` |
| `test_liquidus_bisection` | 5 | `2 deselected in 0.13s` |
| `test_parallel_engine` | 0 | `15 passed in 69.02s (0:01:09)` |
| `test_parallel_integration` | 0 | `6 passed in 68.89s (0:01:08)` |
| `test_phase_presets` | 0 | `15 passed, 6 deselected in 38.48s` |
| `test_phase_presets_control` | 5 | `1 deselected in 2.32s` |
| `test_ui_f` | 0 | `38 passed, 21 deselected in 755.83s (0:12:35)` |
| `test_ui_g` | 0 | `28 passed, 3 deselected, 2 warnings in 205.17s (0:03:25)` |
| `test_ui_h` | 0 | `24 passed, 2 deselected in 323.21s (0:05:23)` |
| `thermogar_active_state_io_test` | 0 | `5 passed, 2 warnings in 4.26s` |
| `thermogar_db_cache_test` | 0 | `10 passed, 3 subtests passed in 0.16s` |
| `thermogar_fe_internal_smoke_test` | 0 | `15 passed in 0.22s` |
| `thermogar_paths_test` | 1 → 0 | `1 failed, 5 passed in 0.19s` → с ключом `-B` `6 passed in 0.12s` |
| `thermogar_restricted_fe_core_test` | 0 | `15 passed, 17 subtests passed in 2.94s` |
| `thermogar_secure_io_test` | 0 | `19 passed in 0.51s` |
| `thermogar_state_migration_test` | 0 | `6 passed in 0.80s` |
| `thermogar_verified_equilibrium_test` | 0 | `16 passed, 8 subtests passed in 1.22s` |
| `thermogar_verified_loaders_test` | 0 | `18 passed in 0.30s` |
| `thermogar_verified_physical_test` | 0 | `24 passed in 0.97s` |
| `thermogar_verified_properties_test` | 0 | `31 passed in 3.85s` |
| `thermogar_verified_state_test` | 0 | `24 passed in 1.05s` |

Семь файлов вернули exit 5 «не собрано ни одного теста» (`thermogar_converter_patch_test`,
`thermogar_diffusion_test`, `thermogar_fe_database_test`, `thermogar_physical_test`,
`thermogar_precipitation_test`, `thermogar_properties_test`, `thermogar_self_test`): это
сценарные скрипты, pytest в них тест-кейсов не видит. Они прогнаны своим способом — ниже.

### 2. Прогон помеченных `slow`, пофайлово

| Файл | exit | Итоговая строка |
|---|---|---|
| `test_backend_calculations` | 1 | **итоговой строки нет: процесс снят `pytest-timeout` на `test_kwn_module[fe]` через 1405 с, до него 12 кейсов прошли** |
| `test_backend_calculations` без двух fe-ячеек kwn | 0 | `12 passed, 45 deselected in 807.93s (0:13:27)` |
| `test_density_thermal_expansion` | 0 | `1 passed, 10 deselected, 1 xfailed in 36.12s` |
| `test_liquidus_bisection` | 0 | `2 passed in 287.72s (0:04:47)` |
| `test_phase_presets` | 0 | `6 passed, 15 deselected in 255.83s (0:04:15)` |
| `test_phase_presets_control` | 0 | `1 passed in 829.26s (0:13:49)` |
| `test_ui_f` | 0 | `21 passed, 38 deselected in 1370.56s (0:22:50)` |
| `test_ui_g` | 0 | `3 passed, 28 deselected, 3 warnings in 2515.81s (0:41:55)` |
| `test_ui_h` | 0 | `2 passed, 24 deselected in 49.94s` |

Остальные файлы медленных кейсов не содержат (exit 5, «deselected»).

### 3. Сценарные тесты, которые pytest не собирает

`python.exe -P -s -B -X utf8 tools/<файл>.py --project-root C:\Users\gareg\Desktop\ThermoGar-w11r`:

| Файл | exit | Результат | Время |
|---|---|---|---|
| `thermogar_converter_patch_test` | 0 | `RESULT: PASSED` | 0,3 с |
| `thermogar_diffusion_test` | 0 | `RESULT: PASSED` | 14 с |
| `thermogar_fe_database_test` | 0 | `RESULT: PASSED` | 194 с |
| `thermogar_physical_test` | 0 | `RESULT: PASSED` | 1 с |
| `thermogar_precipitation_test` | 0 | `RESULT: PASSED` | 20 с |
| `thermogar_properties_test` | 0 | `RESULT: PASSED` | 3 с |
| `thermogar_self_test` | 0 | `RESULT: SOFTWARE REGRESSION PASSED — NOT MATERIAL QUALIFICATION` | 28 с |

### Разбор каждого падения

**(а) `test_density_thermal_expansion::test_alloy_matrix_follows_volume_additivity` — наше,
починено здесь.** Дословно:

```
E           AssertionError: 298.15 K: приложение 8584.9846, объёмная аддитивность 8584.9858
E           assert 8584.984603668945 == 8584.985793987964 ± 8.6e-06
```

Расхождение 1,4·10⁻⁷ — не ошибка расчёта. Тесты этого файла отвечают на вопрос «приложение
добавило своё или так написано в базе», а с волны `11M-2` конструктор `PhysicalDensityDatabase`
по умолчанию подхватывает перекрытие плотности хрома. Проверено прямым замером:

```
AUTO (с перекрытием)     T=  298.15  rho=8584.984604      T= 1373.15  rho=8202.787209
overrides=None           T=  298.15  rho=8584.985794      T= 1373.15  rho=8045.010106
```

С `overrides=None` приложение воспроизводит функции базы точно; 1,4·10⁻⁷ при 298,15 K — остаток
опорной точки перекрытия, при 1373,15 K расхождение уже 2 %. Тест волны 11D просто старше
перекрытия. Правка одна: фикстура строит базу с `overrides=None`, причина записана её
докстрокой. Само перекрытие проверяется своими тестами в `tools/test_density.py`, раздел
«11K-2». Коммит `f5e32f3`.

**(б) `thermogar_paths_test::test_005` — не дефект, артефакт моего запуска.** Падал не
`test_006`, за которым велено смотреть, а `test_005_module_is_stdlib_only_and_minus_b_creates_no_bytecode`:
в `app\__pycache__` лежали четыре `.pyc`, потому что первые прогоны шли без ключа `-B`.
Релизный порядок 0.3.1 требует `-B`. После очистки `__pycache__` и с `-B` — `6 passed in 0.12s`.
**Починка волны 11M держится: `test_006` проходит из рабочего дерева.**

**(в) `test_kwn_module[fe]` по `-m slow` — известное, в бэклоге, здесь не чинится.** Ячейка
железа считается дольше 600 с, `pytest-timeout` на Windows снимает весь процесс. Это `BL-19`
(«обязателен ли `drivingForceMethod='tangent'` для пары Fe-C-Cr с M23C6»), заведённый волной
11P; чинить его в релизной волне не стал — это правка расчётного пути, а не релиза. Что важно
для задания: **прогон не срывается целиком** — пофайлово отказ заперт в своём файле, а
остальные 12 медленных кейсов того же файла проходят (`12 passed, 45 deselected in 807.93s`).

**(г) `test_density.py` — сюрпризов не дал:** `35 passed in 197.74s`.

---

## 11R-4. Сборка установщика и дымовой запуск

### Отступление от порядка и его причина

Версия поднята до сборки (пункт 11R-5 выполнен в части «поднять версию» раньше 11R-4). Иначе
установщик получил бы имя `ThermoGar-0.3.1-win64.exe` и `DisplayVersion` 0.3.1, и выпуск 0.4.0
пришлось бы пересобирать. Названо здесь отдельным пунктом, как требует `RULES.md`.

### 1. Полезная нагрузка

`packaging\stage_payload.ps1`:

```
  project files staged: 76
  staged 15078 files, 554,2 MB
```

Новое в ней есть, проверено по манифесту и по дереву:

| Что | Где в нагрузке |
|---|---|
| каталог лицензий | `licenses/ODbL-1.0.txt`, `licenses/DbCL-1.0.txt`, `licenses/README.md` |
| отпечаток эталона стальной базы | `databases/converted/fe/mc_fe_v2062_unpatched_with_mobility.thermogar.fingerprint.json` |
| файл-дополнение с плотностью хрома | `databases/physical/overrides/physical_data_v103.overrides.json` |

### 2. Установщик

`packaging\build_installer.ps1` — **собрался; NSIS до этой волны не собирался ни разу.**
Вывод сводки дословно (окончательная сборка, после починки деинсталлятора):

```
schema             : 1
product            : ThermoGar
version            : 0.4.0
vi_product_version : 0.4.0.0
built_utc          : 2026-09-12T13:07:39Z
build_seconds      : 589
nsis               : C:\Program Files (x86)\NSIS\makensis.exe
payload_files      : 15078
payload_bytes      : 581114524
installer          : ThermoGar-0.4.0-win64.exe
installer_bytes    : 118483133
installer_sha256   : 2050C76AA396B301A018BD157C9ACBDC6AC3AA2C0572A11CC75912E067BACB73
estimated_size_kb  : 567495
```

### 3. Дымовой запуск — сначала нагрузки, потом установленной копии

**Сначала нагрузка во временном каталоге**, ничего не устанавливая
(`C:\Users\gareg\AppData\Local\Temp\tg-payload-smoke`, запуск из постороннего рабочего
каталога):

```
  processes before: 0
  launcher pid 7976, cwd C:\Users\gareg\AppData\Local\Temp\tg-foreign-23214243
  HEALTHY ui_port=58634 control_port=58631
  GET / -> 200 (11141 bytes, Streamlit shell: True); script-health-check -> 200 'ok'
  stop: {"schema":1,"status":"STOPPED","supervisor_pid":7976,...}
  processes after stop: 0
PAYLOAD SMOKE OK
```

Чисто — и только после этого установка. **Правило «не трогать установленную программу» снято
мастером на время релиза**, ссылка на решение — задание 11R-4, пункт 3.

**Дымовой прогон установленной копии** (`packaging\smoke_installed.ps1`). Первый прогон дал
`OVERALL: FAIL` — два шага из восьми:

```
[FAIL] step 6: stop: no processes, ports free (2,5s)
        stop exit 9, remaining processes 0, ports free True, out={"schema":1,"status":"INTERNAL_ERROR","detail_code":9}
[FAIL] step 7: silent uninstall, LOCALAPPDATA kept (8,8s)
        uninstaller exit 0, leftover files 3, registry gone True, shortcut gone True, LOCALAPPDATA kept True
```

Разбор:

* **Шаг 7 — настоящий дефект продукта, починен.** Три оставшихся файла — это
  `C:\Program Files\ThermoGar\licenses\`: каталог добавлен в поставку волной 11, а в списки
  `RMDir` установщика (и в секции замены прежней нагрузки, и в секции удаления) не попал.
  Правка — `packaging/ThermoGar.nsi`, коммит `f4b9015`.
* **Шаг 6 — не воспроизвелось.** `stop` вернул `INTERNAL_ERROR`, при этом процессов не
  осталось и порты освободились, то есть остановка сработала, а код ответа — нет. На повторном
  прогоне (и на шаге 8 того же первого прогона, где тот же цикл выполняется дважды)
  `stop exit 0`. Наиболее вероятная причина — мой же предшествующий дымовой запуск нагрузки из
  временного каталога: он писал запись о прогоне в тот же `%LOCALAPPDATA%\ThermoGar`, но под
  другой идентичностью установки. Утверждать это как установленный факт не берусь; в бэклог
  волны 12 стоит записать пункт «`stop.pyw` глотает исключение и отдаёт `INTERNAL_ERROR` без
  текста — добавить причину в вывод».

Прогон после починки — **`OVERALL: PASS`, 8 шагов из 8**:

```
[PASS] step 1: silent install (28,9s) — installer exit 0
[PASS] step 2: files, shortcut, registry (0s) — missing=0 database=True shortcut=True registry=True version=0.4.0
[PASS] step 3: launcher started (3s) — pid=21384 alive=True
[PASS] step 4: healthcheck HEALTHY (34,1s) — ui_port=54576 control_port=50920
[PASS] step 5: UI 200, app script runs clean (1s) — GET / -> 200 (11141 bytes, Streamlit shell: True); script-health-check -> 200 'ok'
[PASS] step 6: stop: no processes, ports free (1s) — stop exit 0, remaining processes 0, ports free True
[PASS] step 7: silent uninstall, LOCALAPPDATA kept (5,6s) — leftover files 0, registry gone True, shortcut gone True, LOCALAPPDATA kept True
[PASS] step 8: upgrade over existing install, user project kept (153,6s) — project kept across upgrade True, identical True
OVERALL: PASS
report: dist\smoke-20260912T132143Z.json
```

### 4. Проверка на установленной копии того, что добавила волна 11

Выпуск установлен (`exit=0`) и проверен её собственным интерпретатором
(`C:\Program Files\ThermoGar\runtime\python.exe`), то есть по установленным файлам, а не по
рабочему дереву:

```
[PASS] 11R-4.1: автоматический набор фаз строится: 99 фаз базы, оставлено 98, снято ['BCC_B2']
[PASS] 11R-4.2: панель читает отпечаток: Источник сверки с эталоном — эталонная база не
       поставляется, сверка по отпечатку mc_fe_v2062_unpatched_with_mobility.thermogar.fingerprint.json
[PASS] 11R-4.3: Плотность хрома посчитана по поправке проекта ThermoGar, а не по данным
       physical_data_v103.pdb: тепловая функция DTCRBCC заменена. Это не наша оценка величины,
       а восстановление источника — статья REF 14 самой базы (Lu, Selleby, Sundman, Calphad 29
       (2005) 68-89, doi:10.1016/j.calphad.2005.05.001)…
[PASS] 11R-4.4: Из расчёта исключены фазы, модель которых не строится на выбранном наборе
       элементов: BCC_B2 (связана с BCC_A2: внедрённая подрешётка BCC_A2 на этом составе —
       {C, VA}, а у BCC_B2 совпадающих подрешёток 0, нужна ровно одна). Это ограничение
       описания базы, а не отказ расчёта…
OVERALL: PASS
```

---

## 11R-5. Версия, журнал изменений, паспорт выпуска

### Версия 0.4.0 — все места, где она зашита

Искались все, не одно:

| Файл | Что |
|---|---|
| `app/thermogar_release_policy.py` | `APP_STAGE`, `APP_VERSION` |
| `app/ThermoGar_app.py` | подпись в боковой панели |
| `packaging/product-version.json` | `display_version`, `vi_product_version` |
| `packaging/build_installer.ps1` | пример вызова в справке |
| `README.md` | заголовок и имя exe |
| `docs/FEATURES.md` | заголовок |
| `docs/guide/README.md` | заголовок и имя одностраничного руководства |
| `docs/guide/ThermoGar_Guide_0.3.1.html` → `…_0.4.0.html` | `git mv`, `<title>` и `<h1>` внутри |
| `tools/make_guide_screens.py` | `HTML_NAME`, `HTML_TITLE` — иначе генератор вернул бы старое имя |
| `HANDOFF.md` | заголовок, строка «Выпущено», имена файлов сборки |
| `tools/bench_ui_parallel.py` | строка называла 0.3.1 «текущей версией» — переписана |

Упоминания вида «с 0.3.1 стало быстрее», «до 0.3.1 обходил всё дерево» оставлены: это история, а
не версия продукта. Отчёты волн и старые разделы `CHANGELOG.md` не трогались.

`THIRD_PARTY_NOTICES.txt` перевыпущен сборкой — изменилась только строка `Generated`.

### `CHANGELOG.md`, раздел 0.4.0

Написан для человека, решающего, обновляться ли. Первым абзацем — не список правок, а
предупреждение: **числа изменятся**, тот же проект на той же базе даст другие значения
плотности, коэффициентов диффузии, ликвидуса и солидуса, и если на числах 0.3.1 построены
выводы, их надо пересчитать. Дальше — четыре группы «что именно изменится в результатах»
(плотность, диффузия и кинетика, ликвидус и солидус, фазовый набор), «что снято», «добавлено»,
«установщик» и прежний разбор волны 10 подразделом.

Отдельной строкой названо снятое: **вывод волны 10 о влиянии марганца на горячие трещины снят,
влияние состава на склонность к трещинам этим расчётом не установлено** — ни для марганца, ни
для серы.

---

## 11R-6. Пуш на GitHub

Выполняется последним и только потому, что 11R-3, 11R-4 и 11R-5 прошли.

Предмержевая проверка: неотслеживаемых файлов волн в дереве `main` не осталось. Задания
`WAVE11N_LIGHT_OPUS.md`, `WAVE11Q_OPUS.md` и `WAVE11R_RELEASE_OPUS.md` закоммичены веткой
(`9620387`); их местные копии в `main` сверены с блобами по нормализованному содержанию
(10022 / 10163 / 13605 байт, 103 / 100 / 140 строк, SHA-256 `b3442101...`, `ac13afc3...`,
`da1157f3...` — все три совпали) и сняты как побайтовые дубли. Посторонние файлы задачи APP-576
(`REPORT_APP-576.md`, `ZADACHA_APP-576_TERMOGAR_SOLIDUS_VJ159.md`, `uliki_576/`) не тронуты:
решения по ним нет.

**Слияние своей ветки в `main` сделано по прямому указанию мастера** (задание 11R-6): релиз
завершает волну 11. Это единственное место в проекте, где волна мержит свою ветку, и оно
названо отступлением от `RULES.md`, раздел «Ветки и слияния».

```
git merge --no-ff wave11-release -m "Merge wave 11R: release 0.4.0"
Merge made by the 'ort' strategy.
 27 files changed, 1688 insertions(+), 122 deletions(-)
 rename docs/guide/{ThermoGar_Guide_0.3.1.html => ThermoGar_Guide_0.4.0.html} (99%)
```

`git push origin main` дословно:

```
To https://github.com/gareginaslanyan/ThermoGar.git
   fc5011c..df15a0e  main -> main
```

`git tag -a v0.4.0 -m "ThermoGar 0.4.0"`, затем `git push origin v0.4.0` дословно:

```
To https://github.com/gareginaslanyan/ThermoGar.git
 * [new tag]         v0.4.0 -> v0.4.0
```

Теги в репозитории: `v0.3.0`, `v0.3.1`, **`v0.4.0`**. `main` ушёл вперёд от `origin/main` на
93 коммита — все они ушли одним пушем.

---

## Состояние ветки

`git log --oneline -12`:

```
df15a0e Merge wave 11R: release 0.4.0
9620387 docs(tasks): задания волн 11N (лёгкий поток), 11Q и 11R
e354b57 docs(11R): отчёт волны 11R
60d84e8 release(11R-5): версия 0.4.0, раздел CHANGELOG про изменение результатов
f4b9015 fix(11R-4): деинсталлятор снимает каталог licenses
f5e32f3 test(11R-3): фикстура плотности сравнивает приложение с базой без перекрытия
bceadd8 feat(11R-2): интервал хрупкости как главная величина, сверка метода на доле твёрдого 0,95
834624f Merge wave 11Q: branch integration, equilibrium solidus of the residual liquid
e4e705b docs(11Q): отчёт волны 11Q
cdc2f58 feat(11Q-2,11Q-3): равновесный солидус остаточной жидкости — три значения разъехались
8cf90f3 Merge wave 11N: density on the automatic phase set, BL-10 closed, per-test database isolation
7add6b7 Merge waves 11D/11J/11L/11P: density slope, homogenisation, Scheil tail, manganese withdrawn, u-fraction balance
```

`git status --short`:

```
?? REPORT_APP-576.md
?? ZADACHA_APP-576_TERMOGAR_SOLIDUS_VJ159.md
?? uliki_576/
```

Остались только посторонние файлы задачи APP-576, которые трогать не велено. Неотслеживаемых
файлов волн нет.

---

## Что стоит завести в бэклог

* `stop.pyw` глотает исключение и отдаёт `INTERNAL_ERROR` без текста — по такому ответу
  причину не разобрать (см. 11R-4, шаг 6 первого прогона).
* `pytest tools\` одной командой подвешивает `test_parallel_engine::test_sequential_and_parallel_agree_bytewise`,
  хотя отдельным файлом тот идёт 70 с. Либо разобраться, либо записать пофайловый порядок как
  единственный поддерживаемый и сказать это в `HANDOFF.md`.
* `BL-19` остаётся открытым: пока он открыт, `pytest tools\ -m slow` по
  `test_backend_calculations.py` снимается по таймауту.
