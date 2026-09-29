# 20-З — отчёт: BL-57, шаг 5 разреза — службы прогона (`RunServices`, `SERVICES`), сверка с эталоном 0.5.0, регрессия

**Итог.** 20-Ж влита в `main`: коммит `8d2147c`, дерево `2a671ce` сошлось. Службы прогона собраны в неизменяемый объект (`ebd8a71`). Строки, sha256, блобы, `numstat` и AST обоих файлов сошлись с замером мастера. `proverka_sluzhb`: функций 22 → 12, переприсваиваний 0. Тесты: 8 файлов зелёные. Сверка вкладок: 130 из 130 чистые; 4036 файлов, 3573 равны, 463 равны с 14 исключениями, различий 0 — полное равенство. Регрессия: 78 заданий, 69 выход 0, 9 выход 5 (список 20-Ж), 1090 passed, 1 xfailed; эталон расчётов PASS. СТОПов не было.

## Время по шагам

| Шаг | Начало | Конец | Что |
|---|---|---|---|
| 0 | 16:24:36 | ≈16:24:45 | `git status`, fetch, ссылки, эталон, память |
| 1 | 16:24:48 | 16:26:13 | слияние, пуш в `main`, ветка `wave20-z`, `WAVE20_Z_OPUS.md` (`5f11744`) |
| 2 | 16:26:18 | 16:34:58 | сверка файлов до правки, `proverka_sluzhb` до правки, правка, проверки, коммит `ebd8a71` |
| 3 | 16:35:32 | 16:40:13 | прогон 8 файлов, коммита нет (тесты не менялись) |
| 4 | 16:40:42 | 17:37:04 | снимок (16:40:42–17:35:49), сводка, суммы, сверка (17:36:12–17:36:45), коммит `4e5396d` |
| 5 | 17:37:10 | 19:29:01 | регрессия (17:37:10–19:28:35), сверка эталона расчётов (19:28:54), коммит `ebc0b98` |
| 6 | ≈16:45 | 19:29:19 | реестр: (а), (в), (г) — во время снимка, (б) — после регрессии; коммит `6f67b49` |
| 7 | 19:30 | см. раздел git | отчёт, пуш |

Все даты — 29.09.2026, время местное (UTC+3).

## Шаг 0

* `git status --short` на входе:

  ```
  ?? _to_delete/
  ```

* `git ls-remote origin main wave20-zh`: `main` — `d15774b06c21f659f94131faeaa684ab365491aa`, `wave20-zh` — `70bf9835104e6b52dcef6e1f64006037d093881e`. Сошлось.
* Эталон `results\validation\wave20_v\run1` — 130 каталогов случаев.
* Интерпретатор запускается: `3.11.9 (tags/v3.11.9:de54cf5, Apr  2 2024, 10:12:12) [MSC v.1938 64 bit (AMD64)]`.
* Свободная память на входе — 5,72 ГиБ из 15,71. Перед ШАГОМ 4 — 6,29 ГиБ, перед ШАГОМ 5 — 7,24 ГиБ (раннер на входе — 7,24 ГиБ).

## Шаг 1. Слияние 20-Ж

* `git switch --detach origin/main` (`d15774b`), `git merge --no-ff origin/wave20-zh -m "Merge wave20-zh: общие помощники ThermoGar_app.py (20-Ж)"`.
* Коммит слияния — `8d2147c523fce6c764d56f7e2e9716f284d4f0fc`, родители `d15774b` и `70bf983`, дерево — `2a671ce3ab77c79111b8fc92dafb00ce28bc6c52`. Совпало с заданием.
* `git push origin HEAD:refs/heads/main` — `d15774b..8d2147c  HEAD -> main`.
* `git switch -c wave20-z`. Задание без первой строки «/caveman ultra» — `tasks/WAVE20_Z_OPUS.md`, 74 строки, LF; коммит `5f11744`.

## Шаг 2. Службы прогона

До правки: `app/ThermoGar_app.py` — блоб `42196e1402e8cbebe8315a1e5ea5004732a979c1`, 11 132 строки; `app/thermogar_app_context.py` — блоб `a92a54ab6b25798a7777283eab8d12adc0e24ff9`, 30 строк; CR 0 в обоих. Совпало с заданием.

Правку внёс скрипт по номерам строк файла до правки. Перед записью он сверил текст каждой строки:

* `:53`, `:281`, `:2232`, `:10734` — дословно;
* `:5903`–`:5905` — `)`, две пустые, дальше строка `# ---`;
* начала 12 сигнатур — `def <имя>(`;
* у шести функций — строка `    sidebar: SidebarContext,` внутри сигнатуры;
* у пяти функций — строка `) -> …:` на `:1595`, `:2246`, `:3854`, `:3880`, `:4381`, и `*` в их сигнатурах нет;
* 26 строк замен — на каждой ровно одно имя службы (границы слова, без точки перед именем);
* 13 строк `)` вызовов — одни на строке, строка перед ними кончается запятой.

Вставок 45 строк, заменённых строк 32.

После правки всё совпало с замером мастера:

* `app/ThermoGar_app.py` — 11 177 строк, LF, в конце один перевод строки. sha256 `f28157e3d2bc30d43c4c12e0e74249fec731b6f01452e294ffe7f1040f35efde`, после `git add` — блоб `3b77bab54c6915ee5f0954fa2a1ed9f75c59fbbe`. `git diff --numstat` — `77	32`.
* `app/thermogar_app_context.py` — 50 строк, LF, в конце один перевод строки. sha256 `fd1bedc4de160864b7cdd883d7a16f31cc7c0787d0610b2004b2b093f4c0f812`, блоб `5f4c3de51aaf68f6e886934ffdbd9e786b582e74`. `numstat` — `26	6`.
* AST головного сценария: узлов верхнего уровня 239 → 241. Лишние два — `import functools` (`:53`) и `SERVICES = RunServices(…)` (`:5930`).
* Обратная замена в новом файле убрала параметров `services` 12, аргументов `services=…` 16, вернула `services.<поле>` прежним именем 26 раз и `functools.partial(batch_engine_runner, services=SERVICES)` → `batch_engine_runner` 1 раз. Импорт из `thermogar_app_context` вернулся к прежнему. После этого 239 из 239 узлов равны прежним по `ast.dump`, различий 0.

Проверка — `results/wave20_z/scripts/proverka_sluzhb.py`, только `ast` и `symtable`.

До правки — `results/wave20_z/sluzhby_do.txt`:

```
файл: app/ThermoGar_app.py до правки (блоб 42196e1402e8cbebe8315a1e5ea5004732a979c1)
имён служб прогона: 15
имена: THERMOGAR_PATHS, render_friendly_error, log_error, dataframe_to_excel, load_database, load_scheil, scheil_available, _SCHEIL_STATE, FE_PROFILE_SHA256, FE_PROFILE_RELATIVE_PATHS, _DATABASE_SNAPSHOT_CACHE, _DATABASE_SNAPSHOT_CACHE_LOCK, _parse_database_snapshot, _database_cache_get, _database_cache_commit
функций, читающих их как глобальные или объявляющих global: 22
94 | load_scheil | _SCHEIL_STATE
125 | scheil_available | _SCHEIL_STATE
322 | render_friendly_error | THERMOGAR_PATHS
338 | log_error | THERMOGAR_PATHS
500 | _database_cache_get | _DATABASE_SNAPSHOT_CACHE, _DATABASE_SNAPSHOT_CACHE_LOCK
505 | _database_cache_commit | _DATABASE_SNAPSHOT_CACHE, _DATABASE_SNAPSHOT_CACHE_LOCK
513 | load_database | FE_PROFILE_RELATIVE_PATHS, FE_PROFILE_SHA256, _database_cache_commit, _database_cache_get, _parse_database_snapshot
649 | VerifiedB3BatchBroker._bind | THERMOGAR_PATHS
665 | VerifiedB3BatchBroker._restore_sidebar | THERMOGAR_PATHS
790 | VerifiedB3BatchBroker.finish | THERMOGAR_PATHS
988 | bind_b4b_physical_context | THERMOGAR_PATHS
1151 | _b4b_render_result_downloads | THERMOGAR_PATHS, dataframe_to_excel
1211 | render_b4b_density_single | THERMOGAR_PATHS, render_friendly_error
1379 | render_b4b_density_temperature | render_friendly_error
1592 | render_b4b_pdb_self_test | THERMOGAR_PATHS, render_friendly_error
1625 | render_b4b_coverage | THERMOGAR_PATHS, render_friendly_error
1699 | render_b4b2_elastic_properties | THERMOGAR_PATHS, render_friendly_error
1940 | render_b4b2_strengthening | THERMOGAR_PATHS, render_friendly_error
2232 | batch_database_identity | FE_PROFILE_SHA256, load_database
3852 | solidification_excel_bytes | dataframe_to_excel
4377 | phase_reference_dataframe | FE_PROFILE_SHA256
9186 | solidification_error_record | log_error
строка SERVICES: нет
```

После правки — `results/wave20_z/sluzhby_posle.txt`:

```
файл: app/ThermoGar_app.py после правки (блоб 3b77bab54c6915ee5f0954fa2a1ed9f75c59fbbe)
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

До правки — 22 функции, после — 12. Список, имена и номера строк после правки совпали с заданием. Десять функций ушли из списка. Строки `def` с номерами из задания (`:1595` и др.) — это строки `) -> …:` конца сигнатуры; сверено по тексту.

Коммит `ebd8a71`: оба файла `app`, скрипт, два вывода.

## Шаг 3. Тесты

Тесты не менялись. Прогоны шли 16:35:32–16:40:13. Команды: pytest — каждый файл целиком, `-q -p no:cacheprovider`; `test_equilibrium_solidus_fallback.py` — с `-m "not slow"`; `thermogar_paths_test.py` — запуском файла. Все зелёные:

| Файл | Итог |
|---|---|
| `test_version_consistency.py` | 96 passed |
| `test_wave21_ts.py` | 9 passed |
| `test_wave21_m.py` | 22 passed |
| `test_density_below_pdb.py` | 5 passed |
| `test_physical_overrides_toggle.py` | 11 passed, 167 с |
| `test_sidebar_composition_error.py` | 9 passed |
| `test_equilibrium_solidus_fallback.py` (без slow) | 17 passed, 2 deselected |
| `thermogar_paths_test.py` (unittest) | Ran 6 tests, OK |

## Шаг 4. Сверка вкладок с эталоном 0.5.0

* Команда: `tools\tab_snapshot.py run --out results\validation\wave20_z\posle --state results\validation\wave20_v\state\run7 --time-csv results\wave20_z\posle_time.csv`.
  * Окружение — `MPLBACKEND=Agg`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`.
  * Каталоги `run7` и `results\validation\wave20_z` до прогона не существовали.
* Прогон — 16:40:42–17:35:49, 55,1 мин по сумме случаев (20-Ж — 54,8).
  * Пик дерева процессов — 3,14 ГиБ.
  * Минимум свободной памяти — 3,79 ГиБ.
  * Снятых по памяти 0.
  * Код выхода 0, stderr пуст (0 байт).
* `posle_svodka.txt` — 130 из 130: код 0, «ошибка» null, «исключений_на_экране» 0. Состав и порядок случаев — как у 20-Ж.
* `posle_sha256.txt` — 4036 строк.
  * Имена файлов отличаются от 20-Ж в 2 строках: это файлы ошибок с отметкой времени, `g_kwn_grid/vygruzki/ThermoGar_error_20260929-171900-142dfffd.json` и `g_kwn_too_long/vygruzki/ThermoGar_error_20260929-171738-a1f738f2.json`. У 20-Ж против 20-Е — те же 2.
  * Сумм отличается от 20-Ж 463.
  * Во всех 130 `meta.json` поле `ThermoGar_app.py_sha256` равно `f28157e3…` — это файл после правки.
* Сводку и суммы строит тот же способ, что у 20-Ж. Скрипт проверен на прогоне 20-Ж: он даёт `posle_svodka.txt` и `posle_sha256.txt` 20-Ж с теми же блобами (`00d4062`, `2b960b5`).
* Правила — `results\wave20_g\isklyucheniya.txt` без изменений, 14 правил, копии нет.
* Сверка: `tools\tab_snapshot_compare.py results\validation\wave20_v\run1 results\validation\wave20_z\posle --isklyucheniya results\wave20_g\isklyucheniya.txt --otchet results\wave20_z\sravnenie.txt` (17:36:12–17:36:45).
  * Код выхода 0, «правил 14».
  * `ИТОГ: файлов 4036; равны 3573; равны с исключениями 463; различаются 0; нет пары 0; нарушений целостности A 0, B 0` — **«ИТОГ: полное равенство»**.
* Срабатывания правил (сколько файлов): 1 — 418, 2 — 130, 3 — 143, 4 — 8, 5 — 2, 6 — 135, 7 — 3, 8 — 3, 9 — 3, 10 — 27, 11 — 9, 12 — 18, 13 — 1, 14 — 130.
  * Все 14 чисел равны числам сверки 20-Ж.
  * `sravnenie.txt` отличается от файла 20-Ж только строкой `B:` (путь каталога).
  * «Различаются» и «нет пары» — 0; разбирать нечего, новых правил нет.

Коммит `4e5396d`: `posle_time.csv`, `posle_stdout.txt`, `posle_svodka.txt`, `posle_sha256.txt`, `sravnenie.txt`.

## Шаг 5. Полная регрессия

* Раннер — `results/wave20_z/scripts/run_regress.py`: копия `results/wave20_zh/scripts/run_regress.py` с двумя правками по заданию, :68 (`RELEASE_OUT` — `results/wave20_z`, «каталог вывода 20-З») и :141 (`results/validation/wave20_z_state`). `diff` с источником — только эти две строки.
* Прогон — 17:37:10–19:28:35, 111,4 мин по сумме заданий (20-Ж — 142,8, 20-Е — 110,8).
  * Свободно на входе — 7,24 ГиБ.
  * Пик — 4,88 ГиБ (`test_ui_f -m slow`).
  * Минимум свободной памяти — 2,28 ГиБ, на `slow__test_ui_f.py`. Прерванных по памяти 0.
  * Код выхода раннера 0, stderr пуст (0 байт).
* **78 заданий**. Состав и порядок равны 20-Ж.
* Выход 0 — **69**, выход 5 — **9**. Других выходов нет, красных нет.
* Выход 5 означает, что в файле нет тестов с отметкой not slow. Список равен списку 20-Ж:
  `notslow__test_liquidus_bisection.py`, `notslow__test_phase_presets_control.py`, `notslow__thermogar_converter_patch_test.py`, `notslow__thermogar_diffusion_test.py`, `notslow__thermogar_fe_database_test.py`, `notslow__thermogar_physical_test.py`, `notslow__thermogar_precipitation_test.py`, `notslow__thermogar_properties_test.py`, `notslow__thermogar_self_test.py`.
* `test_ui_f -m slow` шёл одним процессом (свободно на старте 7,15 ≥ 6,0 ГиБ): 21 passed, 1088,0 с.
* Итоговые строки всех 78 заданий (без времени и числа предупреждений) равны строкам 20-Ж. Всего 1090 passed, 1 xfailed, 242 deselected.
* Пакетный расчёт через `functools.partial` проверен регрессией: `notslow__test_ui_h.py` и `slow__test_ui_h.py` зелёные, итоги как у 20-Ж.
* Сверка эталона расчётов: `results\wave21_eh\scripts\backend_compare.py results\wave20_z\regress_backend results\wave20_z\backend_compare.txt`.
  * Ячеек 57 / 57, статусы `PASS`.
  * Разница в одной ячейке — `[Кинетика] KWN (модуль) | fe`, «строк кинетики» 1123. Разница законная (22-Б), как у 20-Ж.
  * **«ВЕРДИКТ: PASS»**. Файл отличается от файла 20-Ж только путём в первой строке.

Коммит `ebc0b98`: копия раннера, `regress_logs` (78), `regress_memlog` (62), `regress_backend` (2), `regress_summary.jsonl`, `backend_compare.txt` — 145 файлов.

## Шаг 6. Реестр

Тексты мастера — дословно: абзац (в), шаблон строки (б) и строки (г) скрипт взял из `tasks/WAVE20_Z_OPUS.md`. Правки:

* (а) строка 20-Ж — «**принята мастером 29.09.2026, с замечанием (ниже); влита в `main` (`8d2147c`).**»;
* (б) строка 20-З после строки 20-Ж; итог числами — из этого отчёта;
* (в) абзац «Приёмка 20-Ж мастером (29.09.2026). …» после абзаца «Ошибка мастера (20-Е, проверка боковой панели). …»;
* (г) BL-57 — «… шаг 4 — общие помощники (20-Ж); шаг 5 — службы прогона (20-З).**».

Остальное в ячейках не менялось. `git diff --stat` — 5 вставок, 2 удаления. Коммит `6f67b49`.

## Что где лежит

* В git (`results/wave20_z/`): `scripts/proverka_sluzhb.py`, `sluzhby_do.txt`, `sluzhby_posle.txt`, `posle_time.csv`, `posle_stdout.txt`, `posle_svodka.txt`, `posle_sha256.txt`, `sravnenie.txt`, `scripts/run_regress.py`, `regress_logs/`, `regress_memlog/`, `regress_backend/`, `regress_summary.jsonl`, `backend_compare.txt`.
* Вне git: снимок — `results\validation\wave20_z\posle\` (130 случаев) и `posle_logs\`; состояние снимка — `results\validation\wave20_v\state\run7\`; состояние регрессии — `results\validation\wave20_z_state\`.
* В `_to_delete\` в этой задаче ничего не добавлено. Вне дерева `D:\Pets\ThermoGar-w21b` ничего не искалось и не читалось, кроме интерпретатора окружения и временной папки сессии.

## Отступления от задания

1. **Лёгкая работа во время снимка.** Пока шёл снимок, сделаны три вещи:
   * копия раннера с двумя правками;
   * проверка скрипта сводки на данных 20-Ж;
   * правки реестра (а), (в), (г).

   Кроме этого, во время снимка и регрессии шло только наблюдение за ходом: раз в 20–30 с считались строки вывода. Тяжёлых прогонов параллельно не было.
2. **Вспомогательные скрипты вне дерева.** Во временной папке сессии, не в репозитории, лежат скрипты:
   * правка по номерам со сверкой строк;
   * проверка AST;
   * прогон тестов ШАГА 3;
   * сводка и `posle_sha256.txt`;
   * сравнение итогов регрессии с 20-Ж;
   * правки реестра.

   В дереве только скрипты, которые названы в задании. Вспомогательные скрипты запускались с `-B -X utf8` и `PYTHONDONTWRITEBYTECODE=1`, но не всегда с `MPLBACKEND=Agg` и `PYTHONHASHSEED=0`. Они не импортируют matplotlib и не зависят от порядка хешей. Тесты, снимок, сверка, регрессия, сверка эталона расчётов и `proverka_sluzhb.py` шли с полным окружением.
3. **Потоки вывода вне списка.** Во временную папку сессии записаны stderr снимка (0 байт), консоль сверки, консоль и stderr раннера регрессии (stderr 0 байт). Задание их в список файлов не включает.
4. **Толкования в `proverka_sluzhb.py`.**
   * Лямбды и включения отдельными функциями не считаются, их чтения относятся к объемлющей `def` — как в `proverka_bokovoy.py` 20-Е.
   * «Переприсваивание после строки `SERVICES`» проверено по связываниям после конца инструкции `SERVICES` (`:5940`). Считались два вида связываний. Первый — код верхнего уровня: присваивания, `for`, `with … as`, `except … as`, `import`, `def`, `class`. Второй — присваивания в функциях, где имя объявлено `global`.
   * Номер строки функции в выводе — строка `def` из `symtable`. У пяти функций задание называет строку `) -> …:`; соответствие сверено по тексту (шаг 2).
5. **Итог числами в строке 20-З реестра** составлен исполнителем по образцу строки 20-Ж. Остальные тексты реестра — дословно из задания.
6. **Концы строк.** В рабочей копии `core.autocrlf=true`. Правленые файлы `app/`, `tasks/` и выводы `proverka_sluzhb.py` записаны с LF. `posle_stdout.txt`, `sravnenie.txt` и другие выводы под Windows в рабочей копии с CRLF, в индексе — LF, как у 20-Ж (`git ls-files --eol`).
7. **Регрессия быстрее, чем у 20-Ж.** 111,4 мин против 142,8. Машина не была занята другой работой: на входе 7,24 ГиБ свободно против 5,46. Время близко к 20-Е (110,8). Итоговые строки от времени не зависят и равны строкам 20-Ж.

## git

Снимается после пуша; раздел дописан следующим коммитом.
