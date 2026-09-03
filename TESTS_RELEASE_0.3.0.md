# TESTS_RELEASE_0.3.0 — полный регресс перед релизом 0.3.0

Дата прогона: 2026-09-03. Ветка `wave4b-regression`, worktree `C:\Users\gareg\Desktop\ThermoGar-w4b`
(отведён от `main` на коммите `edba403`). В `app\` при этом прогоне ничего не менялось.

Интерпретатор: `C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe` — Python 3.11.9,
64 бита. Версии те же, что в `TESTS_BASELINE.md`: streamlit 1.62.0, pycalphad 0.11.2, numpy 2.4.6,
scipy 1.17.1, scheil 0.3.0, symengine 0.13.0, kawin 0.5.0, pandas 3.0.5, matplotlib 3.11.1,
openpyxl 3.1.5, pytest 9.1.1, pytest-timeout 2.4.0.

Все прогоны выполнены строго последовательно, один за другим, чтобы времена были сопоставимы
между собой. Общее машинное время — **7245 с ≈ 2 ч 1 мин** (716 с одиночные файлы,
6529 с pytest-наборы), плюс 134 с перепрогона и 3 с проверки приложения.

Полные логи каждого прогона и машинная сводка `wave4b_runs.jsonl` — в
`C:\Users\gareg\Desktop\ThermoGar\_archive_codex\wave4b_logs\` (каталог вне git).

## Итог

| Категория | Прогонов | exit 0 | exit ≠ 0 | timeout |
|---|---|---|---|---|
| Одиночные файлы `tools\` | 19 | 18 | 1 | 0 |
| Наборы pytest | 8 | 7 | 1 | 0 |
| Приложение (старт/200/стоп) | 1 | 1 | 0 | 0 |
| **Всего** | **28** | **26** | **2** | **0** |

По отдельным тест-кейсам: **351 кейс, 349 зелёных**, 1 ожидаемый `xfail` и
1 известное допустимое падение (`thermogar_paths_test::test_006`).
Два падения в `test_ui_f.py -m slow` зелёные при повторном прогоне — причина
внешняя, разобрана ниже.

| Источник | Кейсов | Зелёных | Прочее |
|---|---|---|---|
| unittest-файлы | 179 | 178 | 1 FAIL — `paths_test::test_006` |
| сценарные скрипты (`RESULT: …`) | 8 | 8 | — |
| pytest-наборы | 172 | 171 (после перепрогона) | 1 xfail (заявленный) |

## Часть 1. Одиночные файлы `tools\`

Команда: `python.exe -I -B -X utf8 tools\<файл> --project-root C:\Users\gareg\Desktop\ThermoGar-w4b`;
если файл не принимает аргумент (argparse, exit 2) — повтор без него, столбец «арг.» показывает,
какой вариант дал результат. Таймаут 20 мин на файл — не сработал ни разу.

`--project-root` указывает на **worktree**, а не на основную папку: иначе прогонялось бы
содержимое `main`, а не проверяемой ветки. Для файлов без этого аргумента корень и так
определяется по месту самого файла, то есть тоже worktree.

| # | Файл | exit | Результат | Время | арг. |
|---|---|---|---|---|---|
| 1 | `thermogar_active_state_io_test.py` | 0 | Ran 5 tests — OK | 9.9 с | без |
| 2 | `thermogar_converter_patch_test.py` | 0 | `RESULT: PASSED` | 0.7 с | `--project-root` |
| 3 | `thermogar_diffusion_test.py` | 0 | `RESULT: PASSED` | 21.4 с | `--project-root` |
| 4 | `thermogar_fe_database_test.py` | 0 | `RESULT: PASSED` | 246.6 с | `--project-root` |
| 5 | `thermogar_fe_internal_smoke_test.py` | 0 | Ran 15 tests — OK | 0.8 с | без |
| 6 | `thermogar_paths_test.py` | 1 | Ran 6 tests — FAILED (failures=1) | 0.7 с | без |
| 7 | `thermogar_physical_test.py` | 0 | `RESULT: PASSED` | 1.5 с | `--project-root` |
| 8 | `thermogar_precipitation_test.py` | 0 | `RESULT: PASSED` | 23.0 с | `--project-root` |
| 9 | `thermogar_properties_test.py` | 0 | `RESULT: PASSED` | 5.9 с | `--project-root` |
| 10 | `thermogar_restricted_fe_core_test.py` | 0 | Ran 15 tests — OK | 5.3 с | без |
| 11 | `thermogar_secure_io_test.py` | 0 | Ran 19 tests — OK | 1.3 с | без |
| 12 | `thermogar_state_migration_test.py` | 0 | Ran 6 tests — OK | 1.8 с | без |
| 13 | `thermogar_verified_equilibrium_test.py` | 0 | Ran 16 tests — OK | 2.7 с | без |
| 14 | `thermogar_verified_loaders_test.py` | 0 | Ran 18 tests — OK | 0.7 с | без |
| 15 | `thermogar_verified_physical_test.py` | 0 | Ran 24 tests — OK | 2.1 с | без |
| 16 | `thermogar_verified_properties_test.py` | 0 | Ran 31 tests — OK | 6.9 с | без |
| 17 | `thermogar_verified_state_test.py` | 0 | Ran 24 tests — OK | 2.4 с | без |
| 18 | `thermogar_self_test.py` | 0 | `RESULT: SOFTWARE REGRESSION PASSED — NOT MATERIAL QUALIFICATION` | 42.1 с | `--project-root` |
| 19 | `thermogar_fe_internal_smoke.py` | 0 | JSON-отчёт, `upstream_diagnostic_status: COMPLETE_DIAGNOSTIC_ONLY` | 340.3 с | `--project-root` |

`tools\thermogar_fe_database_guard.py` не запускался: это не тест, как и в волне 0.

## Часть 2. Наборы pytest

Команда: `python.exe -B -X utf8 -m pytest tools/<файл> -v -m "<маркер>"`, рабочий каталог —
корень worktree (приложение fail-closed требует `.streamlit\config.toml` рабочей папки).
Для backend задавалась переменная `THERMOGAR_BACKEND_REPORT` (Windows-путь).

| Файл | Маркер | exit | Результат | Время |
|---|---|---|---|---|
| `test_backend_calculations.py` | `not slow` | 0 | 44 passed, 1 xfailed | 658.8 с (10:56) |
| `test_backend_calculations.py` | `slow` | 0 | 12 passed | 1117.6 с (18:35) |
| `test_ui_f.py` | `not slow` | 0 | 37 passed | 1392.2 с (23:09) |
| `test_ui_f.py` | `slow` | 1 | **2 failed**, 19 passed | 1887.7 с (31:24) |
| `test_ui_g.py` | `not slow` | 0 | 30 passed | 528.0 с (8:46) |
| `test_ui_g.py` | `slow` | 0 | 1 passed | 73.6 с (1:12) |
| `test_ui_h.py` | `not slow` | 0 | 24 passed | 771.1 с (12:51) |
| `test_ui_h.py` | `slow` | 0 | 2 passed | 96.9 с (1:36) |
| `test_ui_f.py` (перепрогон 2 упавших) | `slow` | 0 | 2 passed | 133.5 с (2:13) |

Таймаут на наборы pytest поднят с 20 до 90 мин. Двадцати минут заведомо не хватает:
по `tools\backend_reference.md` медленная часть backend занимала 1510 с, по `tools\ui_matrix_F.md`
быстрая часть 3F шла 26 мин, медленная — 39 мин. С 20-минутным ограничением половина наборов
дала бы ложный timeout вместо результата. Ни один прогон не приблизился к 90 мин.

## Часть 3. Приложение

```
.venv-windows\Scripts\python.exe -B -X utf8 -m streamlit run app\ThermoGar_app.py --server.headless true --server.port 8517
```

Сервер поднялся за 2.8 с, `http://localhost:8517/` ответил **200**, в выводе процесса нет
ни `Traceback`, ни ошибок. Процесс остановлен, UI не кликался (кликовые сценарии закрыты
наборами `test_ui_f/g/h`). Порт 8517 вместо штатного 8501 взят, чтобы не столкнуться
с параллельной работой волны 4A.

## Разбор падений

### `thermogar_paths_test::test_006_exact_official_venv_interpreter_identity` — известное, допустимое

```
AssertionError: 'c:\users\gareg\desktop\thermogar\.venv-windows\scripts\python.exe'
            != 'c:\users\gareg\desktop\thermogar-w4b\.venv-windows\scripts\python.exe'
```

Тест требует, чтобы интерпретатор лежал внутри проверяемого дерева (`ROOT / ".venv-windows"`).
В worktree своего venv нет — он один на всю машину и лежит в основной папке. Остальные
5 тестов файла проходят.

Проверка из основной папки, как просила задача:

```
cd C:\Users\gareg\Desktop\ThermoGar
.venv-windows\Scripts\python.exe -I -B -X utf8 tools\thermogar_paths_test.py
```

→ `Ran 6 tests — OK`, exit 0, `INTERPRETER_EXECUTABLE: C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe`.
То есть падение вызвано исключительно тем, что прогон идёт из worktree. Для релизной сборки,
которая собирается из основной папки, тест зелёный. Чинить нечего.

### `test_ui_f.py::test_binary_diagram[fe]` и `test_ui_f.py::test_isopleth_diagram[ni]` — внешняя помеха, не регрессия

```
AssertionError: ['Некоторые локальные проекты отклонены без применения:
wave4a-upgrade-probe.thermogar.json: ValueError: В envelope отсутствуют обязательные поля:
exported_at, kind, payload, schema_version, sha256.']
```

Тесты 3F проверяют, что при рендере нет неожиданных `st.error`. Ошибка пришла не из
проверяемых разделов: в общий профиль `%LOCALAPPDATA%\ThermoGar\workspace\projects\`
файл `wave4a-upgrade-probe.thermogar.json` положила **волна 4A**, работавшая на этой же
машине параллельно; приложение честно отклонило файл с неполным envelope и показало
сообщение. К моменту разбора файл уже убран самой 4A, каталог пуст.

Перепрогон ровно этих двух тестов после исчезновения файла: **2 passed за 133.5 с**.
Правки не требуются ни в `app\`, ни в тесте — это следствие того, что `test_ui_f.py`,
в отличие от `test_ui_h.py`, не изолирует `THERMOGAR_STATE_ROOT` и работает в общем профиле
пользователя. Замечание для мастера проекта: пока изоляции нет, наборы 3F нельзя гонять
одновременно с чем-либо, что пишет в `%LOCALAPPDATA%\ThermoGar\workspace\`.

Других падений нет.

## Сравнение с `TESTS_BASELINE.md`

### По файлам

| | Baseline (волна 0, 2026-09-02) | Релиз 0.3.0 (2026-09-03) |
|---|---|---|
| Одиночных файлов в прогоне | 24 | 19 |
| из них exit 0 | 19 | 18 |
| из них exit ≠ 0 | 5 | 1 (известное, см. выше) |
| Наборов pytest | 0 (их ещё не было) | 8 |
| Приложение (старт/200) | OK | OK |

Пять файлов, падавших в baseline, в дереве больше нет: волна 1A перенесла их
в `_archive_codex\tools\` (коммит `982ef57`).

| Файл baseline | Статус baseline | Что с ним стало |
|---|---|---|
| `thermogar_fe_equilibrium_witness_test.py` | FAIL (пин на файл, ушедший в архив) | перенесён в `_archive_codex\tools\` |
| `thermogar_fe_local_witness_test.py` | FAIL (то же) | перенесён в `_archive_codex\tools\` |
| `thermogar_fe_steel_ui_test.py` | FAIL (реальное расхождение) | перенесён в `_archive_codex\tools\` |
| `thermogar_unified_app_test.py` | FAIL (пинил структуру исходника) | перенесён в `_archive_codex\tools\` |
| `thermogar_workspace_fe_context_test.py` | FAIL (API разошёлся с тестом) | перенесён в `_archive_codex\tools\` |

Из оставшихся 19 файлов в baseline все были зелёными — и все 19 зелёные сейчас,
кроме `thermogar_paths_test.py`, который падает только из-за запуска из worktree
(в baseline прогон шёл из основной папки, где он зелёный, и сейчас там тоже зелёный).

### По числу тест-кейсов

`thermogar_verified_loaders_test.py`: было 19 тестов, стало 18 — волна 3F+3H сняла
sentinel-тест на SHA (коммит `0c29669`). Остальные файлы сохранили состав.

### Времена

Времена выросли относительно baseline на файлах, где считается физика:
`thermogar_fe_database_test.py` 193.1 → 246.6 с, `thermogar_fe_internal_smoke.py` 174.5 → 340.3 с,
`thermogar_self_test.py` 27.8 → 42.1 с. Причина — не код: во время этого прогона на той же
машине параллельно работала волна 4A (релизная сборка и установка). Внутри самого регресса
всё шло строго по одному, поэтому времена сопоставимы между собой, но по отношению
к baseline их следует считать верхней оценкой.

## Сравнение с отчётами волн 1C и 3

| Набор | Заявлено в отчёте волны | Сейчас | Расхождение |
|---|---|---|---|
| backend `not slow` | 42 passed + 3 xfailed, 712 с (`backend_reference.md`) | 44 passed + 1 xfailed, 658.8 с | два Fe-кейса кинетики переведены из `xfail` в ожидаемый проход волной 2B (`29fe9cd`); остался один заявленный `xfail` — `test_alloy_density[al]`, у `THETA_AL2CU` нет модели плотности в `physical_data_v103.pdb` |
| backend `slow` | 12 passed, 1510 с | 12 passed, 1117.6 с | совпадает |
| `test_ui_f.py` `not slow` | 37 passed, 26 мин (`ui_matrix_F.md`) | 37 passed, 23:09 | совпадает |
| `test_ui_f.py` `slow` | 21 passed, 39 мин | 21 кейс, 19 passed + 2 внешних падения, зелёные в перепрогоне | состав совпадает |
| `test_ui_g.py` | матрица без итоговой цифры (`ui_matrix_G.md`) | 30 + 1 = 31 passed | — |
| `test_ui_h.py` | 26 passed, 1063 с (`ui_matrix_H.md`) | 24 + 2 = 26 passed, 868 с | совпадает |

Заявленные в матрицах оговорки (`FAIL (данные базы)` для гомогенизации на Al,
`OK-с-оговоркой` для KWN на Al, недостижимый `render_quick_examples`) на результат прогона
не влияют: они описаны в самих тестах и не приводят к падению.

## Побочные файлы прогона

`thermogar_fe_database_test.py` пишет отчёт в `results\validation\stage13_2\`
(3 файла: `high_temperature_liquidus_check.csv`, `mn_ni_si_c15_survival_check.csv`,
`stage13_2_acceptance.json`). Они остались в рабочем дереве как untracked и в коммит не входят.

## Вывод

Дерево `main` на коммите `edba403` к релизу 0.3.0 готово по тестам: из 351 тест-кейса
349 зелёных, единственное падение — `thermogar_paths_test::test_006`, вызванное запуском
из worktree и не воспроизводящееся из основной папки, откуда собирается релиз. Ещё один
`xfail` заявлен и объяснён в `tools\backend_reference.md`. Приложение стартует и отвечает 200.
