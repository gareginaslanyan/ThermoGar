# 20-И — отчёт: BL-57, шаг 6 разреза — проверенная привязка базы (`VerifiedBinding`, `VLB`, `RunServices.binding`), сверка с эталоном 0.5.0, регрессия

**Итог.** 20-З влита в `main`: коммит `11eabbc`, дерево `3208bfe` сошлось. Привязка базы — в изменяемом объекте `VLB` (`9638fbf`). Строки, sha256, блобы и `numstat` обоих файлов сошлись с замером мастера. AST: 241 → 241, после отката 239 из 240 равны, отличается только импорт `:282` (правка б1, см. отступление 1). `proverka_bokovoy`: функций 2 → 0, имён 46 и 46. `proverka_sluzhb`: функций 12 → 8. `global` 0, `vlb_active_context` 0. Тесты: 7 файлов зелёные. Сверка вкладок: 130 из 130 чистые; 4036 файлов, 3573 равны, 463 равны с 14 исключениями, различий 0 — полное равенство. Регрессия: 78 заданий, 69 выход 0, 9 выход 5 (список 20-З), 1090 passed, 1 xfailed; эталон расчётов PASS. СТОПов не было.

## Время по шагам

| Шаг | Начало | Конец | Что |
|---|---|---|---|
| 0 | 20:24:11 | ≈20:24:20 | `git status`, fetch, ссылки, эталон, память |
| 1 | 20:24:24 | 20:24:59 | слияние, пуш в `main`, ветка `wave20-i`, `WAVE20_I_OPUS.md` (`7adc2a1`) |
| 2 | 20:24:59 | 20:27:20 | сверка файлов до правки, правка, AST, четыре вывода проверок, коммит `9638fbf` |
| 3 | 20:28:00 | 20:35:59 | прогон 7 файлов, коммита нет (тесты не менялись) |
| 4 | 20:36:15 | 21:31:50 | снимок (20:36:15–21:30:37), сводка, суммы, сверка (21:31:02–21:31:37), коммит `0adfedf` |
| 5 | 21:31:56 | 23:23:30 | регрессия (21:31:56–23:22:52), сверка эталона расчётов (23:23:21), коммит `a50242a` |
| 6 | ≈20:28 | 23:23:51 | реестр: (а), (в), (г) — во время ШАГА 3, (б) — после регрессии; коммит `613e392` |
| 7 | 23:24 | см. раздел git | отчёт, пуш |

Все даты — 29.09.2026, время местное (UTC+3).

## Шаг 0

* `git status --short` на входе:

  ```
  ?? _to_delete/
  ```

* `git ls-remote origin main wave20-z`: `main` — `8d2147c523fce6c764d56f7e2e9716f284d4f0fc`, `wave20-z` — `a293c6ae441c74ec79203a8dc88d2f0bc0820bd7`. Сошлось.
* Эталон `results\validation\wave20_v\run1` — 130 каталогов случаев.
* Интерпретатор запускается: `3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]`.
* Свободная память на входе — 7,32 ГиБ из 15,71. Перед ШАГОМ 4 — 7,35 ГиБ, перед ШАГОМ 5 — 7,33 ГиБ.

## Шаг 1. Слияние 20-З

* `git switch --detach origin/main` (`8d2147c`), `git merge --no-ff origin/wave20-z -m "Merge wave20-z: службы прогона ThermoGar_app.py (20-З)"`.
* Коммит слияния — `11eabbc07521b3cfb1d5d02e32610ffbc64a925c`, родители `8d2147c` и `a293c6a`, дерево — `3208bfe8736da209cb3c057534ca775eccd3f320`. Совпало с заданием.
* `git push origin HEAD:refs/heads/main` — `8d2147c..11eabbc  HEAD -> main`.
* `git switch -c wave20-i`. Задание без первой строки «/caveman ultra» — `tasks/WAVE20_I_OPUS.md`, 87 строк, LF; коммит `7adc2a1`.

## Шаг 2. Привязка базы

До правки: `app/ThermoGar_app.py` — блоб `3b77bab54c6915ee5f0954fa2a1ed9f75c59fbbe`, 11 177 строк; `app/thermogar_app_context.py` — блоб `5f4c3de51aaf68f6e886934ffdbd9e786b582e74`, 50 строк; CR 0 в обоих. Совпало с заданием.

Правку внёс скрипт по номерам строк файла до правки, снизу вверх. Перед записью он сверил дословно текст каждой заменяемой и удаляемой строки и строк-якорей вставок:

* `thermogar_app_context.py`: `:1`, `:12` (границы документации), `:40`–`:41` (`@dataclass(frozen=True)`, `class RunServices:`), `:50` (последнее поле);
* `ThermoGar_app.py`: `:282`, `:639`, `:640`, `:663`, `:667`, `:669`, `:672`, `:674`, `:678`, `:679`, `:684`, `:692`, `:693`, `:696`, `:828`, `:990`, `:991`, `:994`, `:1009`, `:1030`, `:5633`, `:5638`, `:5639`, `:5939`, `:10740`; на `:6004`, `:6051`, `:6149`, `:6339`, `:6410`, `:6718`, `:6790` — строка без отступа равна `vlb_bound_context,`; `:10585` кончается на `bind_b4b_physical_context(database_key)`.

Строка `:683` (`st.session_state["_thermogar_vlb_bound_context_v1"] = (`) — ключ сессии, в задании её нет, не менялась.

После правки всё совпало с замером мастера:

* `app/ThermoGar_app.py` — 11 178 строк, LF, в конце один перевод строки. sha256 `954cdeb506823084abe90ec08d9b7aa976cbd809d8fe1cd63381c4bfad24837b`, после `git add` — блоб `6ce2bb2d53372c734406d21d436f5c7303b889fa`. `git diff --numstat` — `33	32`.
* `app/thermogar_app_context.py` — 58 строк, LF, в конце один перевод строки. sha256 `83405251ed5d1414d3e2399ede1d9256aa1c8b441855af024a0f58ca0784afb2`, блоб `79bdac23cfbb3d8adb972bf4e0eb97d75ae041d1`. `numstat` — `12	4`.
* AST головного сценария: узлов верхнего уровня 241 → 241.
* Откат по заданию. В обоих файлах убраны: параметры `services`, аргументы `services=…`, аргумент `binding=VLB`, присваивания `VLB` и `self._services`. В файле до правки убраны операторы `global` и три записи в `vlb_active_context`. `self._services.paths` и `services.paths` возвращены в `THERMOGAR_PATHS`, `self._services.binding.bound` и `VLB.bound` — в `vlb_bound_context`.
* После отката — 240 и 240 узлов. Равны по `ast.dump` 239. Отличается один узел — импорт `:282`: `from thermogar_app_context import RunServices, SidebarContext, VerifiedBinding` (правка б1). Если вернуть и импорт прежним — 240 из 240 равны, различий 0. Разбор — отступление 1.
* `thermogar_app_context.py`: узлов верхнего уровня 8 → 9 (новый класс `VerifiedBinding`); меняются документация и `RunServices` (поле `binding`).

Проверки — скриптами прежних шагов без правки, выводы в `results/wave20_i/`.

`proverka_bokovoy.py` до правки — `bokovaya_do.txt`:

```
файл: app/ThermoGar_app.py до правки (блоб 3b77bab54c6915ee5f0954fa2a1ed9f75c59fbbe)
раздел боковой панели: :5522–:5944
имён боковой панели: 46
имена: CURRENT_CONTEXT, CURRENT_CONTEXT_SIGNATURE, SERVICES, SIDEBAR, available_elements, balance, balance_key, composition_key, composition_text, context_or_release_changed, database_identity, database_key, database_path, db, default_balance, definition, error, expected_hash, fe_profile_key, loaded_context, loaded_database_key, loaded_label, pending_context_error, pressure_pa, previous_context_signature, previous_database_identity, previous_release_generation, rejected_balance, rejected_key, stale_key, stale_result_keys, state_key, steel_mode, steel_mode_label, steel_options, stored_vlb_context, stored_vlb_selector, units, units_key, units_label, units_options, vlb_active_context, vlb_bound_context, vlb_catalog, vlb_selector, workspace_state_store
функций, читающих их как глобальные или объявляющих global: 2
666 | VerifiedB3BatchBroker._restore_sidebar | vlb_active_context, vlb_bound_context
989 | bind_b4b_physical_context | vlb_active_context
```

После правки — `bokovaya_posle.txt`:

```
файл: app/ThermoGar_app.py после правки (блоб 6ce2bb2d53372c734406d21d436f5c7303b889fa)
раздел боковой панели: :5520–:5945
имён боковой панели: 46
имена: CURRENT_CONTEXT, CURRENT_CONTEXT_SIGNATURE, SERVICES, SIDEBAR, VLB, available_elements, balance, balance_key, composition_key, composition_text, context_or_release_changed, database_identity, database_key, database_path, db, default_balance, definition, error, expected_hash, fe_profile_key, loaded_context, loaded_database_key, loaded_label, pending_context_error, pressure_pa, previous_context_signature, previous_database_identity, previous_release_generation, rejected_balance, rejected_key, stale_key, stale_result_keys, state_key, steel_mode, steel_mode_label, steel_options, stored_vlb_context, stored_vlb_selector, units, units_key, units_label, units_options, vlb_bound_context, vlb_catalog, vlb_selector, workspace_state_store
функций, читающих их как глобальные или объявляющих global: 0
```

Имён 46 и 46: `vlb_active_context` ушло, `VLB` пришло. Функций 2 → 0.

`proverka_sluzhb.py` до правки — `sluzhby_do.txt`:

```
файл: app/ThermoGar_app.py до правки (блоб 3b77bab54c6915ee5f0954fa2a1ed9f75c59fbbe)
имён служб прогона: 15
имена: THERMOGAR_PATHS, render_friendly_error, log_error, dataframe_to_excel, load_database, load_scheil, scheil_available, _SCHEIL_STATE, FE_PROFILE_SHA256, FE_PROFILE_RELATIVE_PATHS, _DATABASE_SNAPSHOT_CACHE, _DATABASE_SNAPSHOT_CACHE_LOCK, _parse_database_snapshot, _database_cache_get, _database_cache_commit
функций, читающих их как глобальные или объявляющих global: 12
95 | load_scheil | _SCHEIL_STATE
126 | scheil_available | _SCHEIL_STATE
323 | render_friendly_error | THERMOGAR_PATHS
339 | log_error | THERMOGAR_PATHS
501 | _database_cache_get | _DATABASE_SNAPSHOT_CACHE, _DATABASE_SNAPSHOT_CACHE_LOCK
506 | _database_cache_commit | _DATABASE_SNAPSHOT_CACHE, _DATABASE_SNAPSHOT_CACHE_LOCK
514 | load_database | FE_PROFILE_RELATIVE_PATHS, FE_PROFILE_SHA256, _database_cache_commit, _database_cache_get, _parse_database_snapshot
650 | VerifiedB3BatchBroker._bind | THERMOGAR_PATHS
666 | VerifiedB3BatchBroker._restore_sidebar | THERMOGAR_PATHS
791 | VerifiedB3BatchBroker.finish | THERMOGAR_PATHS
989 | bind_b4b_physical_context | THERMOGAR_PATHS
9223 | solidification_error_record | log_error
строка SERVICES: :5930–:5940
переприсваиваний имён служб и SERVICES после неё: 0
```

После правки — `sluzhby_posle.txt`:

```
файл: app/ThermoGar_app.py после правки (блоб 6ce2bb2d53372c734406d21d436f5c7303b889fa)
имён служб прогона: 15
имена: THERMOGAR_PATHS, render_friendly_error, log_error, dataframe_to_excel, load_database, load_scheil, scheil_available, _SCHEIL_STATE, FE_PROFILE_SHA256, FE_PROFILE_RELATIVE_PATHS, _DATABASE_SNAPSHOT_CACHE, _DATABASE_SNAPSHOT_CACHE_LOCK, _parse_database_snapshot, _database_cache_get, _database_cache_commit
функций, читающих их как глобальные или объявляющих global: 8
95 | load_scheil | _SCHEIL_STATE
126 | scheil_available | _SCHEIL_STATE
323 | render_friendly_error | THERMOGAR_PATHS
339 | log_error | THERMOGAR_PATHS
501 | _database_cache_get | _DATABASE_SNAPSHOT_CACHE, _DATABASE_SNAPSHOT_CACHE_LOCK
506 | _database_cache_commit | _DATABASE_SNAPSHOT_CACHE, _DATABASE_SNAPSHOT_CACHE_LOCK
514 | load_database | FE_PROFILE_RELATIVE_PATHS, FE_PROFILE_SHA256, _database_cache_commit, _database_cache_get, _parse_database_snapshot
9224 | solidification_error_record | log_error
строка SERVICES: :5930–:5941
переприсваиваний имён служб и SERVICES после неё: 0
```

Функций 12 → 8. Список и номера строк после правки совпали с заданием. Переприсваиваний 0.

В головном сценарии после правки операторов `global` — 0, имени `vlb_active_context` — 0. `vlb_bound_context` остался только в коде боковой панели: `:5605`, `:5614`, `:5619` (создание привязки) и `:5633` (`VLB = VerifiedBinding(bound=vlb_bound_context)`); ещё три вхождения — внутри строкового ключа `"_thermogar_vlb_bound_context_v1"` (`:668`, `:681`, `:5597`). Вне `app/` имя `vlb_active_context` есть только в `tools/test_ui_h.py:54–60` — заплата теста для старого кода; она не совпадает с исходником и пропускается по правилу самого теста («an entry that no longer matches the source is simply skipped»).

Коммит `9638fbf`: оба файла `app`, четыре вывода.

## Шаг 3. Тесты

Тесты не менялись. Прогоны шли 20:28:00–20:35:59, окружение `MPLBACKEND=Agg`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`. Команды: pytest — `-q -p no:cacheprovider`, `test_ui_h.py` — с `-m "not slow"`; `thermogar_verified_state_test.py` и `thermogar_paths_test.py` — запуском файла (unittest). Журналы — `results\validation\wave20_i_shag3\`. Все зелёные:

| Файл | Итог |
|---|---|
| `test_version_consistency.py` | 96 passed |
| `test_ui_h.py` (без slow) | 24 passed, 2 deselected, 266,7 с |
| `test_physical_overrides_toggle.py` | 11 passed, 153,2 с |
| `test_density_below_pdb.py` | 5 passed |
| `test_sidebar_composition_error.py` | 9 passed |
| `thermogar_verified_state_test.py` (unittest) | Ran 25 tests, OK |
| `thermogar_paths_test.py` (unittest) | Ran 6 tests, OK |

`test_ui_h.py` без slow проходит проекты, библиотеку и пакет через `VerifiedB3BatchBroker` и пробу `StateStore` — ложного `BINDING_STALE` нет.

## Шаг 4. Сверка вкладок с эталоном 0.5.0

* Команда: `tools\tab_snapshot.py run --out results\validation\wave20_i\posle --state results\validation\wave20_v\state\run8 --time-csv results\wave20_i\posle_time.csv`.
  * Окружение — `MPLBACKEND=Agg`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`.
  * Каталоги `run8` и `results\validation\wave20_i` до прогона не существовали.
* Прогон — 20:36:15–21:30:37, 54,4 мин по сумме случаев (20-З — 55,1).
  * Пик дерева процессов — 3,11 ГиБ.
  * Минимум свободной памяти — 4,41 ГиБ.
  * Снятых по памяти 0.
  * Код выхода 0, stderr пуст (0 байт).
* `posle_svodka.txt` — 130 из 130: код 0, «ошибка» null, «исключений_на_экране» 0. Состав и порядок случаев — как у 20-З.
* `posle_sha256.txt` — 4036 строк.
  * Имена файлов отличаются от 20-З в 2 строках — файлы ошибок с отметкой времени: `g_kwn_grid/vygruzki/ThermoGar_error_20260929-211352-aa2d094c.json` и `g_kwn_too_long/vygruzki/ThermoGar_error_20260929-211231-25ac07e5.json`. У 20-З против 20-Ж — те же 2.
  * Во всех 130 `meta.json` поле `ThermoGar_app.py_sha256` равно `954cdeb5…` — это файл после правки.
* Сводку и суммы строит тот же способ, что у 20-З. Скрипт проверен на прогоне 20-З: он даёт `posle_svodka.txt` и `posle_sha256.txt` 20-З с теми же блобами (`43599cf`, `ce0a9e9`).
* Правила — `results\wave20_g\isklyucheniya.txt` без изменений, 14 правил, копии нет.
* Сверка: `tools\tab_snapshot_compare.py results\validation\wave20_v\run1 results\validation\wave20_i\posle --isklyucheniya results\wave20_g\isklyucheniya.txt --otchet results\wave20_i\sravnenie.txt` (21:31:02–21:31:37).
  * Код выхода 0, «правил 14».
  * `ИТОГ: файлов 4036; равны 3573; равны с исключениями 463; различаются 0; нет пары 0; нарушений целостности A 0, B 0` — **«ИТОГ: полное равенство»**.
* Срабатывания правил (сколько файлов): 1 — 418, 2 — 130, 3 — 143, 4 — 8, 5 — 2, 6 — 135, 7 — 3, 8 — 3, 9 — 3, 10 — 27, 11 — 9, 12 — 18, 13 — 1, 14 — 130.
  * Все 14 чисел равны числам сверки 20-З.
  * `sravnenie.txt` отличается от файла 20-З только строкой `B:` (путь каталога).
  * «Различаются» и «нет пары» — 0; разбирать нечего, новых правил нет.

Коммит `0adfedf`: `posle_time.csv`, `posle_stdout.txt`, `posle_svodka.txt`, `posle_sha256.txt`, `sravnenie.txt`.

## Шаг 5. Полная регрессия

* Раннер — `results/wave20_i/scripts/run_regress.py`: копия `results/wave20_z/scripts/run_regress.py` с двумя правками по заданию, :68 (`RELEASE_OUT` — `results/wave20_i`, «каталог вывода 20-И») и :141 (`results/validation/wave20_i_state`). `diff` с источником — только эти две строки.
* Прогон — 21:31:56–23:22:52, 110,9 мин по сумме заданий (20-З — 111,4).
  * Свободно на входе — 7,33 ГиБ.
  * Пик — 4,90 ГиБ (`test_ui_f -m slow`).
  * Минимум свободной памяти — 2,65 ГиБ, на `slow__test_ui_f.py`. Прерванных по памяти 0.
  * Код выхода раннера 0, stderr пуст (0 байт).
* **78 заданий**. Состав и порядок равны 20-З.
* Выход 0 — **69**, выход 5 — **9**. Других выходов нет, красных нет.
* Выход 5 означает, что в файле нет тестов с отметкой not slow. Список равен списку 20-З:
  `notslow__test_liquidus_bisection.py`, `notslow__test_phase_presets_control.py`, `notslow__thermogar_converter_patch_test.py`, `notslow__thermogar_diffusion_test.py`, `notslow__thermogar_fe_database_test.py`, `notslow__thermogar_physical_test.py`, `notslow__thermogar_precipitation_test.py`, `notslow__thermogar_properties_test.py`, `notslow__thermogar_self_test.py`.
* `test_ui_f -m slow` шёл одним процессом (свободно на старте 7,27 ≥ 6,0 ГиБ): 21 passed, 1087,8 с.
* Итоговые строки всех 78 заданий (без времени и числа предупреждений) равны строкам 20-З. Всего 1090 passed, 1 xfailed, 242 deselected.
* Сверка эталона расчётов: `results\wave21_eh\scripts\backend_compare.py results\wave20_i\regress_backend results\wave20_i\backend_compare.txt`.
  * Ячеек 57 / 57, статусы `PASS`.
  * Разница в одной ячейке — `[Кинетика] KWN (модуль) | fe`, «строк кинетики» 1123. Разница законная (22-Б), как у 20-З.
  * **«ВЕРДИКТ: PASS»**. Файл отличается от файла 20-З только путём в первой строке.

Коммит `a50242a`: копия раннера, `regress_logs` (78), `regress_memlog` (62), `regress_backend` (2), `regress_summary.jsonl`, `backend_compare.txt` — 145 файлов.

## Шаг 6. Реестр

Тексты мастера — дословно: абзац (в), шаблон строки (б) и строки (г) скрипт взял из `tasks/WAVE20_I_OPUS.md`. Правки:

* (а) строка 20-З — «**принята мастером 29.09.2026 (ниже); влита в `main` (`11eabbc`).**»;
* (б) строка 20-И после строки 20-З; итог числами — из этого отчёта;
* (в) абзац «Приёмка 20-З мастером (29.09.2026). …» после абзаца «Приёмка 20-Ж мастером (29.09.2026). …»;
* (г) BL-57 — «… шаг 5 — службы прогона (20-З); шаг 6 — привязка базы (20-И).**».

Остальное в ячейках не менялось. `git diff --stat` — 5 вставок, 2 удаления. Коммит `613e392`.

## Что где лежит

* В git (`results/wave20_i/`): `bokovaya_do.txt`, `bokovaya_posle.txt`, `sluzhby_do.txt`, `sluzhby_posle.txt`, `posle_time.csv`, `posle_stdout.txt`, `posle_svodka.txt`, `posle_sha256.txt`, `sravnenie.txt`, `scripts/run_regress.py`, `regress_logs/`, `regress_memlog/`, `regress_backend/`, `regress_summary.jsonl`, `backend_compare.txt`.
* Вне git: снимок — `results\validation\wave20_i\posle\` (130 случаев) и `posle_logs\`; состояние снимка — `results\validation\wave20_v\state\run8\`; состояние регрессии — `results\validation\wave20_i_state\`; журналы ШАГА 3 — `results\validation\wave20_i_shag3\`.
* В `_to_delete\` в этой задаче ничего не добавлено. Вне дерева `D:\Pets\ThermoGar-w21b` ничего не искалось и не читалось, кроме интерпретатора окружения и временной папки сессии.

## Отступления от задания

1. **AST: импорт `:282` не входит в список отката.** Задание требует равенства «остальных узлов» после отката перечисленных правок. Импорт из `thermogar_app_context` в список не входит, но меняется правкой б1 (добавлено имя `VerifiedBinding`). Поэтому после отката 239 из 240 узлов равны, отличается только этот импорт. С возвратом импорта прежним — 240 из 240. У 20-З задание прямо называло возврат импорта. Правка байт в байт равна модели мастера (sha256 и блоб обоих файлов сошлись), значит та же разница есть и в модели. Принял за пропуск в тексте задания, не за СТОП.
2. **Лёгкая работа во время тестов ШАГА 3.** Пока шли тесты, сделаны:
   * скрипт сводки и сумм и его проверка на данных 20-З;
   * копия раннера с двумя правками;
   * правки реестра (а), (в), (г).

   Во время снимка и регрессии шло только наблюдение за ходом: раз в 5–20 с считались строки вывода. Тяжёлых прогонов параллельно не было.
3. **Вспомогательные скрипты вне дерева.** Во временной папке сессии, не в репозитории, лежат скрипты:
   * правка по номерам со сверкой строк;
   * проверка AST;
   * прогон тестов ШАГА 3;
   * сводка и `posle_sha256.txt`;
   * сравнение итогов регрессии с 20-З;
   * правки реестра.

   В дереве только скрипты, которые названы в задании. Вспомогательные скрипты запускались с `-B -X utf8` и `PYTHONDONTWRITEBYTECODE=1`, но не всегда с `MPLBACKEND=Agg` и `PYTHONHASHSEED=0`. Они не импортируют matplotlib и не зависят от порядка хешей. Тесты, снимок, сверка, регрессия, сверка эталона расчётов, `proverka_bokovoy.py` и `proverka_sluzhb.py` шли с полным окружением.
4. **Файл «до правки» для проверок.** `proverka_bokovoy.py` и `proverka_sluzhb.py` до правки и проверка AST читали копию `git show HEAD:app/ThermoGar_app.py` (блоб `3b77bab`) во временной папке сессии. Подпись файла в выводах — третьим аргументом скрипта, как у 20-З.
5. **Потоки вывода вне списка.** Во временную папку сессии записаны stderr снимка (0 байт), консоль сверки, консоль и stderr раннера регрессии (stderr 0 байт). Задание их в список файлов не включает.
6. **Итог числами в строке 20-И реестра** составлен исполнителем по образцу строки 20-З. Остальные тексты реестра — дословно из задания.
7. **Концы строк.** В рабочей копии `core.autocrlf=true`. Правленые файлы `app/`, `tasks/`, выводы проверок, сводка и суммы записаны с LF. `posle_stdout.txt`, `sravnenie.txt` и другие выводы под Windows в рабочей копии с CRLF, в индексе — LF, как у 20-З (`git ls-files --eol`).

## git

Снято после пуша коммита `f2f3cb5` (29.09.2026 23:25:39). Коммит, дописавший этот раздел, в выводе не виден — его хэш даёт `git log` ветки.

`git ls-remote origin main wave20-i`:

```
11eabbc07521b3cfb1d5d02e32610ffbc64a925c	refs/heads/main
f2f3cb5474200e7110fc16f0191f010b167cd318	refs/heads/wave20-i
```

`git log --oneline origin/main..wave20-i`:

```
f2f3cb5 docs(20-И): отчёт — шаг 6 разреза BL-57
613e392 docs(20-И): реестр — приёмка 20-З, строка 20-И, BL-57
a50242a results(20-И): полная регрессия после привязки базы — 78 заданий, 69 выход 0, 9 выход 5; эталон расчётов PASS
0adfedf results(20-И): сверка вкладок с эталоном 0.5.0 после привязки базы — полное равенство (правил 14)
9638fbf refactor(app): 20-И — проверенная привязка базы в изменяемом объекте VerifiedBinding (VLB, RunServices.binding); global в головном сценарии — 0
7adc2a1 docs(tasks): 20-И задание (BL-57, шаг 6 разреза — проверенная привязка базы)
```

`git status --short`:

```
?? _to_delete/
```
