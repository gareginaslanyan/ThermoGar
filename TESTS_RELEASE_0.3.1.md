# TESTS_RELEASE_0.3.1 — полный регресс перед релизом 0.3.1

Дата прогона: 2026-09-04. Ветка `wave7-release-0.3.1`, worktree `C:\Users\gareg\Desktop\ThermoGar-w7`
(отведён от `main` на коммите `15296ac`). В `app\` при этом прогоне ничего не менялось; единственная
правка кода — одна строка `assertIn` в `tools\thermogar_verified_state_test.py`, разобрана ниже.

Интерпретатор: `C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe` — Python 3.11.9,
64 бита; pytest 9.1.1, pytest-timeout 2.4.0, pytest-cov 7.1.0, anyio 4.14.2. Остальные версии —
те же, что в `TESTS_RELEASE_0.3.0.md`: streamlit 1.62.0, pycalphad 0.11.2, numpy 2.4.6, scipy 1.17.1,
scheil 0.3.0, symengine 0.13.0, kawin 0.5.0, pandas 3.0.5, matplotlib 3.11.1, openpyxl 3.1.5.

**`PYTHONHASHSEED=0` задана в окружении всех без исключения прогонов** — этого требует волна 6:
тесты, сравнивающие параллельный и последовательный режимы побайтово, без затравки пропускаются
с объяснением. По той же причине одиночные файлы запускались с `-P -s -B -X utf8`, а не с `-I`,
как в 0.3.0: `-I` включает `-E` и отменяет все переменные `PYTHON*`, то есть съел бы затравку.
Ни один тест на изоляцию интерпретатора этим не затронут.

Все прогоны выполнены строго последовательно, один за другим, чтобы времена были сопоставимы
между собой. Общее машинное время — **4960 с ≈ 1 ч 23 мин** (503 с одиночные файлы, 4457 с наборы pytest),
плюс 3 с проверки приложения. В эту сумму входит перепрогон `test_backend_calculations -m slow`
(888 с) вместо первого прогона того же набора, испорченного сном ноутбука, — см. оговорку ниже.

Полные логи каждого прогона и машинная сводка `wave7_runs.jsonl` — в
`C:\Users\gareg\Desktop\ThermoGar\_archive_codex\wave7_logs\` (каталог вне git).

## Итог

| Категория | Прогонов | exit 0 | exit ≠ 0 | timeout |
|---|---|---|---|---|
| Одиночные файлы `tools\` | 20 | 19 | 1 | 0 |
| Наборы pytest | 16 | 16 | 0 | 0 |
| Приложение (старт/200/стоп) | 1 | 1 | 0 | 0 |
| **Всего** | **37** | **36** | **1** | **0** |

Три набора pytest (`test_parallel_engine`, `test_parallel_integration`, `thermogar_db_cache_test`
с маркером `slow`) вернули exit 5 «не собрано ни одного теста»: в этих файлах медленных кейсов нет.
Это не отказ, в таблице выше они посчитаны как успешные.

По отдельным тест-кейсам: **413 кейсов, 411 зелёных**, 1 ожидаемый `xfail` и
1 известное допустимое падение (`thermogar_paths_test::test_006`). Кейсы
`thermogar_db_cache_test` посчитаны дважды — задание требует этот файл и как
`tools\thermogar_*_test.py`, и как набор pytest; уникальных кейсов 403.

| Источник | Кейсов | Зелёных | Прочее |
|---|---|---|---|
| unittest-файлы | 189 | 188 | 1 FAIL — `paths_test::test_006` |
| сценарные скрипты (`RESULT: …`) | 8 | 8 | — |
| pytest-наборы | 224 | 223 | 1 xfail (заявленный) |

Неожиданных падений на момент публикации нет.

## Часть 1. Одиночные файлы `tools\`

Команда: `python.exe -P -s -B -X utf8 tools\<файл> --project-root C:\Users\gareg\Desktop\ThermoGar-w7`;
если файл не принимает аргумент (argparse, exit 2) — повтор без него, столбец «арг.» показывает,
какой вариант дал результат. Таймаут 90 мин на файл — не сработал ни разу.

`--project-root` указывает на **worktree**, а не на основную папку: иначе прогонялось бы
содержимое `main`, а не проверяемой ветки.

| # | Файл | exit | Результат | Время | арг. |
|---|---|---|---|---|---|
| 1 | `thermogar_active_state_io_test.py` | 0 | Ran 5 tests — OK | 5.7 с | без |
| 2 | `thermogar_converter_patch_test.py` | 0 | `RESULT: PASSED` | 0.3 с | `--project-root` |
| 3 | `thermogar_db_cache_test.py` | 0 | Ran 10 tests — OK | 0.5 с | без |
| 4 | `thermogar_diffusion_test.py` | 0 | `RESULT: PASSED` | 14.4 с | `--project-root` |
| 5 | `thermogar_fe_database_test.py` | 0 | `RESULT: PASSED` | 184.8 с | `--project-root` |
| 6 | `thermogar_fe_internal_smoke_test.py` | 0 | Ran 15 tests — OK | 0.6 с | без |
| 7 | `thermogar_paths_test.py` | 1 | Ran 6 tests — FAILED (failures=1) | 0.5 с | без |
| 8 | `thermogar_physical_test.py` | 0 | `RESULT: PASSED` | 1.1 с | `--project-root` |
| 9 | `thermogar_precipitation_test.py` | 0 | `RESULT: PASSED` | 18.0 с | `--project-root` |
| 10 | `thermogar_properties_test.py` | 0 | `RESULT: PASSED` | 4.3 с | `--project-root` |
| 11 | `thermogar_restricted_fe_core_test.py` | 0 | Ran 15 tests — OK | 3.8 с | без |
| 12 | `thermogar_secure_io_test.py` | 0 | Ran 19 tests — OK | 1.1 с | без |
| 13 | `thermogar_state_migration_test.py` | 0 | Ran 6 tests — OK | 1.3 с | без |
| 14 | `thermogar_verified_equilibrium_test.py` | 0 | Ran 16 tests — OK | 1.9 с | без |
| 15 | `thermogar_verified_loaders_test.py` | 0 | Ran 18 tests — OK | 0.5 с | без |
| 16 | `thermogar_verified_physical_test.py` | 0 | Ran 24 tests — OK | 1.6 с | без |
| 17 | `thermogar_verified_properties_test.py` | 0 | Ran 31 tests — OK | 5.0 с | без |
| 18 | `thermogar_verified_state_test.py` | 1 → 0 | FAILED (failures=1) → Ran 24 tests — OK после правки теста | 2.2 → 2.3 с | без |
| 19 | `thermogar_self_test.py` | 0 | `RESULT: SOFTWARE REGRESSION PASSED — NOT MATERIAL QUALIFICATION` | 31.5 с | `--project-root` |
| 20 | `thermogar_fe_internal_smoke.py` | 0 | JSON-отчёт, `upstream_diagnostic_status: COMPLETE_DIAGNOSTIC_ONLY` | 204.0 с | `--project-root` |

`tools\thermogar_fe_database_guard.py`, `bench_ui_parallel.py`, `installed_parallel_check.py` и
`job_containment_check.py` не запускались: это не тесты.

## Часть 2. Наборы pytest

Команда: `python.exe -B -X utf8 -m pytest tools/<файл> -v -m "<маркер>"`, рабочий каталог —
корень worktree (приложение fail-closed требует `.streamlit\config.toml` рабочей папки).
Для backend задавалась переменная `THERMOGAR_BACKEND_REPORT` (Windows-путь). Таймаут 90 мин
на набор — не сработал ни разу.

| Файл | Маркер | exit | Результат | Время |
|---|---|---|---|---|
| `test_backend_calculations.py` | `not slow` | 0 | 44 passed, 1 xfailed | 382.4 с (6:22) |
| `test_backend_calculations.py` | `slow` | 0 | 12 passed | 887.8 с (14:48), перепрогон |
| `test_ui_f.py` | `not slow` | 0 | 37 passed | 788.8 с (13:09) |
| `test_ui_f.py` | `slow` | 0 | 21 passed | 1137.5 с (18:58) |
| `test_ui_g.py` | `not slow` | 0 | 30 passed | 257.1 с (4:17) |
| `test_ui_g.py` | `slow` | 0 | 1 passed | 60.8 с (1:01) |
| `test_ui_h.py` | `not slow` | 0 | 24 passed | 383.4 с (6:23) |
| `test_ui_h.py` | `slow` | 0 | 2 passed | 64.4 с (1:04) |
| `test_phase_presets.py` | `not slow` | 0 | 15 passed | 48.5 с |
| `test_phase_presets.py` | `slow` | 0 | 6 passed | 279.6 с (4:40) |
| `test_parallel_engine.py` | `not slow` | 0 | 15 passed | 75.0 с (1:15) |
| `test_parallel_engine.py` | `slow` | 5 | 15 deselected — медленных кейсов в файле нет | 1.0 с |
| `test_parallel_integration.py` | `not slow` | 0 | 6 passed | 83.7 с (1:24) |
| `test_parallel_integration.py` | `slow` | 5 | 6 deselected — медленных кейсов в файле нет | 5.0 с |
| `thermogar_db_cache_test.py` | `not slow` | 0 | 10 passed, 3 subtests passed | 1.1 с |
| `thermogar_db_cache_test.py` | `slow` | 5 | 10 deselected — медленных кейсов в файле нет | 1.0 с |

## Часть 3. Приложение

```
.venv-windows\Scripts\python.exe -B -X utf8 -m streamlit run app\ThermoGar_app.py --server.headless true --server.port 8517
```

Сервер поднялся, `http://localhost:8517/` ответил **200** через 2.9 с после запуска процесса,
`/_stcore/script-health-check` — тоже 200. В выводе процесса нет ни `Traceback`, ни ошибок.
Процесс остановлен, ни одного `python.exe` не осталось, порт 8517 свободен (только `TIME_WAIT`
на клиентском сокете). UI не кликался — кликовые сценарии закрыты наборами `test_ui_f/g/h`.
Порт 8517 вместо штатного 8501 взят, как и в 0.3.0.

Оговорка: 200 от `script-health-check` пришло на 3.0 с, то есть раньше, чем приложение успевает
импортировать расчётные библиотеки (одни импорты стоят 4,3 с). Значит, этот эндпоинт ответил до
конца первого прогона скрипта, и как замер «готовности» здесь он не годится; честные цифры
готовности — в `HANDOFF.md`, раздел «Производительность». Для целей этой части важно другое:
сервер поднимается, отдаёт 200 и корректно останавливается.

## Разбор падений

### `thermogar_paths_test::test_006_exact_official_venv_interpreter_identity` — известное, допустимое

```
AssertionError: 'c:\users\gareg\desktop\thermogar\.venv-windows\scripts\python.exe'
            != 'c:\users\gareg\desktop\thermogar-w7\.venv-windows\scripts\python.exe'
```

Тест требует, чтобы интерпретатор лежал внутри проверяемого дерева (`ROOT / ".venv-windows"`).
В worktree своего venv нет — он один на всю машину и лежит в основной папке. Остальные
5 тестов файла проходят. То же падение и по той же причине было в 0.3.0; из основной папки,
откуда собирается релиз, файл зелёный (`Ran 6 tests — OK`). Чинить нечего.

### `thermogar_verified_state_test::test_batch_fifo_child_receipts_and_envelopes_preserved` — устаревший тест, поправлен

```
AssertionError: 'broker.finish(tuple(child_evidence))' not found in ...app\thermogar_workspace.py
```

Тест пинит текст исходника `app\thermogar_workspace.py`. Волна 6 увела пакетный расчёт с
verified-брокера в параллельный движок: `VerifiedB3BatchBroker.execute_row` удалён, дочерних
квитанций у пакета больше нет, и вместо `broker.finish(tuple(child_evidence))` в коде стоит
`broker.finish(())` — с комментарием ровно об этом (`thermogar_workspace.py:2436`). Квитанция
самого пакетного прогона осталась, её проверка (`set(aggregate) == {"receipt_digest",
"envelope_digest"}`) не изменилась. То есть падал устаревший тест, а не программа. В волне 6 этот
файл не прогонялся — в её отчёте его нет.

По решению мастера правка сделана в тесте, одной строкой, `app\` не тронут:

`tools\thermogar_verified_state_test.py:363`
`self.assertIn("broker.finish(tuple(child_evidence))", workspace)` →
`self.assertIn("broker.finish(())", workspace)`

Остальные три утверждения того же теста (`for position, (_, row) in enumerate(source.iterrows(),
start=1):`, `result["_children"]`, `acquire_b3_execution`) проходили и до правки и оставлены как
есть. Перепрогон файла после правки: `Ran 24 tests — OK`, exit 0, 2.3 с.

Других падений нет.

## Оговорка по времени `test_backend_calculations -m slow`

В первом прогоне этот набор показал 22 086 с (6:08:02). Реального счёта там столько не было:
ноутбук ушёл в сон посреди набора. Таймаут не сработал, потому что на Windows он считается
монотонными часами, которые во время сна стоят, а мой замер шёл по настенным. Набор был
перепрогнан целиком отдельно, в таблице выше — время перепрогона. Все остальные времена сняты
без перерывов.

## Сравнение с `TESTS_RELEASE_0.3.0.md`

### По числу тест-кейсов

| | Релиз 0.3.0 (2026-09-03) | Релиз 0.3.1 (2026-09-04) |
|---|---|---|
| Кейсов всего (unittest + pytest) | 351 | 413 |
| из них зелёных | 349 | 411 |
| ожидаемых `xfail` | 1 | 1 |
| известных допустимых падений | 1 | 1 |
| неожиданных падений | 0 (2 внешних, зелёные в перепрогоне) | 0 |
| сценарных скриптов сверх этого | 8, все PASSED | 8, все PASSED |

Прирост в 62 кейса — целиком новые наборы волн 5 и 6:

| Набор | Кейсов | Откуда |
|---|---|---|
| `test_phase_presets.py` | 21 | волна 5A, быстрые наборы фаз |
| `test_parallel_engine.py` | 15 | волна 5B, движок |
| `test_parallel_integration.py` | 6 | волна 6, интеграция движка в интерфейс |
| `thermogar_db_cache_test.py` | 10 + 10 | волна 5C, кэш базы; считается и как одиночный файл, и как набор pytest |

Состав старых наборов не изменился ни на один кейс: backend 44+1 xfail и 12, `test_ui_f` 37 и 21,
`test_ui_g` 30 и 1, `test_ui_h` 24 и 2 — ровно как в 0.3.0.

### Два внешних падения 0.3.0 не повторились

В 0.3.0 `test_ui_f.py -m slow` дал два падения из-за файла, который параллельно работавшая волна 4A
положила в общий профиль `%LOCALAPPDATA%\ThermoGar\workspace\projects\`. В этот раз профиль был
пуст, на машине ничего параллельно не считалось, и набор прошёл целиком с первого раза:
21 passed. Изоляции `THERMOGAR_STATE_ROOT` у `test_ui_f.py` по-прежнему нет — замечание волны 4B
остаётся в силе: этот набор нельзя гонять одновременно с чем-либо, что пишет в общий профиль.

### Времена

Все повторяющиеся наборы прошли быстрее, чем в 0.3.0:

| Набор | 0.3.0, с | 0.3.1, с |
|---|---|---|
| `test_backend_calculations` `not slow` | 658.8 | 382.4 |
| `test_backend_calculations` `slow` | 1117.6 | 887.8 |
| `test_ui_f.py` `not slow` | 1392.2 | 788.8 |
| `test_ui_f.py` `slow` | 1887.7 | 1137.5 |
| `test_ui_g.py` `not slow` | 528.0 | 257.1 |
| `test_ui_g.py` `slow` | 73.6 | 60.8 |
| `test_ui_h.py` `not slow` | 771.1 | 383.4 |
| `test_ui_h.py` `slow` | 96.9 | 64.4 |
| `thermogar_fe_database_test.py` | 246.6 | 184.8 |
| `thermogar_fe_internal_smoke.py` | 340.3 | 204.0 |
| `thermogar_self_test.py` | 42.1 | 31.5 |

Сумма по тем же самым прогонам, что были в 0.3.0 (без новых наборов волн 5 и 6, которые стоят
496 с): **7245 → 4465 с, в 1,6 раза быстрее.**

Приписывать всю разницу параллельному движку и кэшу базы нельзя. Прогон 0.3.0 шёл на машине,
занятой параллельно работавшей волной 4A, и сам отчёт 0.3.0 называет свои времена верхней оценкой;
этот прогон шёл на свободной машине. Часть выигрыша — от кода (кэш разобранной базы снимает
повторный разбор TDB в каждом тесте, параллельный движок ускоряет сканы, карты и batch внутри
`test_ui_*`), часть — от того, что машину никто не делил. Разделить эти две доли по имеющимся
данным нельзя. Честные замеры самого кода — `toolsench_parallel.md`, там обе версии считались
на одной и той же свободной машине.

## Вывод

Дерево `wave7-release-0.3.1` (`main` на `15296ac` плюс правка одного утверждения в
`tools\thermogar_verified_state_test.py` и документы) к релизу 0.3.1 готово по тестам: из 413
тест-кейсов 411 зелёных, единственное падение — `thermogar_paths_test::test_006`, вызванное
запуском из worktree и не воспроизводящееся из основной папки, откуда собирается релиз. Ещё один
`xfail` заявлен и объяснён в `tools\backend_reference.md`. Приложение стартует и отвечает 200.
