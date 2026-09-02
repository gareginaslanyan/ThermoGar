# TESTS_BASELINE — ThermoGar, волна 0

Дата прогона: 2026-09-02. Состояние: как унаследовано от Codex, после переноса
sentinel/gate-тестов в `_archive_codex\tools\` (волна 0, шаг 2). Ничего не чинилось.

Интерпретатор: `.venv-windows\Scripts\python.exe` — Python 3.11.9
(streamlit 1.62.0, pycalphad 0.11.2, numpy 2.4.6, scipy 1.17.1, scheil 0.3.0,
symengine 0.13.0, kawin 0.5.0, pandas 3.0.5, matplotlib 3.11.1, openpyxl 3.1.5).

Команда: `.venv-windows\Scripts\python.exe -I -B -X utf8 tools\<файл> --project-root C:\Users\gareg\Desktop\ThermoGar`.
Если файл не принимает `--project-root` (ошибка argparse, exit 2) — повтор без него;
столбец «арг.» показывает, какой вариант дал результат. Таймаут 10 мин на файл — не сработал ни разу.

Полные логи: `_archive_codex\baseline_logs\<файл>.out.txt`, машинная сводка — `_archive_codex\baseline_runs.jsonl`.

## Итог

| Всего | OK | FAIL | timeout |
|---|---|---|---|
| 24 | 19 | 5 | 0 |

Из 5 падений: **2 вызваны самим архивированием волны 0** (тесты пинят пути к файлам,
перенесённым в `_archive_codex\`), **3 — реальные расхождения теста и кода**, они падали
и до архивирования (проверено контрольным прогоном с временно возвращёнными файлами,
см. раздел «Контрольный прогон»).

## Таблица

| # | Файл | exit | Результат | Время | арг. | Комментарий |
|---|---|---|---|---|---|---|
| 1 | `thermogar_active_state_io_test.py` | 0 | Ran 5 tests — OK | 5.9 с | без | |
| 2 | `thermogar_converter_patch_test.py` | 0 | `RESULT: PASSED` | 0.3 с | `--project-root` | не unittest, свой формат |
| 3 | `thermogar_diffusion_test.py` | 0 | `RESULT: PASSED` | 18.9 с | `--project-root` | реальный расчёт диффузии |
| 4 | `thermogar_fe_database_test.py` | 0 | `RESULT: PASSED` | 193.1 с | `--project-root` | самый долгий; пишет отчёт в `results\validation\stage13_2` (каталог перенесён в архив, тест это переживает) |
| 5 | `thermogar_fe_equilibrium_witness_test.py` | 1 | Ran 35 tests — FAILED (errors=1) | 1.5 с | без | **FAIL из-за архивирования.** `ContractFailure: pinned path crosses reparse point` — пин на `tools/verify_ne04_fe_local_witness.py` (`configs\ne04_fe_equilibrium_witness_v1.json`). До архивирования: OK (35/35) |
| 6 | `thermogar_fe_internal_smoke_test.py` | 0 | Ran 15 tests — OK | 0.5 с | без | |
| 7 | `thermogar_fe_internal_smoke.py` | 0 | JSON-отчёт, `upstream_diagnostic_status: COMPLETE_DIAGNOSTIC_ONLY` | 174.5 с | `--project-root` | не тест, диагностический прогон Fe |
| 8 | `thermogar_fe_local_witness_test.py` | 1 | Ran 0 tests — FAILED (errors=1) | 0.4 с | без | **FAIL из-за архивирования.** `WitnessContractError: pinned path crosses a symlink/reparse point` — пин на `tools/thermogar_ne03_wave2_adapter_test.py` (`configs\ne04_fe_local_witness_profiles.json`). Падает в `setUpClass`, поэтому 0 тестов. До архивирования: OK (16, 1 skipped) |
| 9 | `thermogar_fe_steel_ui_test.py` | 1 | `FileNotFoundError: tools\run_ne04_fe_steel_diagnostic.py` (импорт на модульном уровне) | 0.3 с | `--project-root` | **Реальный FAIL + эффект архивирования.** Файл-мост перенесён в архив по шагу 2 задачи. С возвращённым мостом: Ran 24 — FAILED (failures=2, errors=3), т.е. тест падал и раньше |
| 10 | `thermogar_paths_test.py` | 0 | Ran 6 tests — OK | 0.4 с | без | |
| 11 | `thermogar_physical_test.py` | 0 | `RESULT: PASSED` | 0.9 с | `--project-root` | плотности Al/Fe/Ni/Fe3C сходятся со справочными |
| 12 | `thermogar_precipitation_test.py` | 0 | `RESULT: PASSED` | 15.7 с | `--project-root` | kawin 0.5.0 |
| 13 | `thermogar_properties_test.py` | 0 | `RESULT: PASSED` | 4.2 с | `--project-root` | упругие модули, упрочнение |
| 14 | `thermogar_restricted_fe_core_test.py` | 0 | Ran 15 tests — OK | 3.6 с | без | |
| 15 | `thermogar_secure_io_test.py` | 0 | Ran 19 tests — OK | 1.0 с | без | |
| 16 | `thermogar_self_test.py` | 0 | `RESULT: SOFTWARE REGRESSION PASSED — NOT MATERIAL QUALIFICATION` | 27.8 с | `--project-root` | главный регрессионный прогон, входит в `RUN_TESTS_WINDOWS.cmd` |
| 17 | `thermogar_state_migration_test.py` | 0 | Ran 6 tests — OK | 1.2 с | без | |
| 18 | `thermogar_unified_app_test.py` | 1 | Ran 9 tests — FAILED (failures=1, errors=5) | 13.3 с | без | **Реальный FAIL, не связан с архивированием** (идентичен до и после). `AssertionError: 1 != 4` — тест ждёт 4 вызова `restricted_fe_calculation_button(` в исходнике, в коде 1; ещё 5 ошибок `IndexError: list index out of range` в AppTest-сценариях. Тест пинит структуру исходника — sentinel-подобный |
| 19 | `thermogar_verified_equilibrium_test.py` | 0 | Ran 16 tests — OK | 1.8 с | без | |
| 20 | `thermogar_verified_loaders_test.py` | 0 | Ran 19 tests — OK | 0.5 с | без | |
| 21 | `thermogar_verified_physical_test.py` | 0 | Ran 24 tests — OK | 1.4 с | без | |
| 22 | `thermogar_verified_properties_test.py` | 0 | Ran 31 tests — OK | 4.7 с | без | |
| 23 | `thermogar_verified_state_test.py` | 0 | Ran 24 tests — OK | 1.9 с | без | |
| 24 | `thermogar_workspace_fe_context_test.py` | 1 | Ran 15 tests — FAILED (errors=15) | 1.6 с | без | **Реальный FAIL, не связан с архивированием.** `AttributeError: module 'thermogar_workspace' does not have the attribute 'equilibrium'` — все 15 тестов падают в `mock.patch`; API модуля разошёлся с тестом |

`tools\thermogar_fe_database_guard.py` не запускался: это не тест и он не входит в список шага 5.

## Контрольный прогон (проверка, что именно сломало архивирование)

Пять падавших файлов прогнаны повторно после временного возврата из `_archive_codex\`
файлов `tools\verify_ne04_fe_local_witness.py`, `tools\thermogar_ne03_wave2_adapter_test.py`,
`tools\run_ne04_fe_steel_diagnostic.py` и каталога `results\validation\`. После прогона
всё возвращено в `_archive_codex\`, рабочее дерево не изменилось.

| Файл | до архивирования | после архивирования | вывод |
|---|---|---|---|
| `thermogar_fe_equilibrium_witness_test.py` | exit 0, Ran 35 — OK | exit 1, errors=1 | регрессия от архивирования |
| `thermogar_fe_local_witness_test.py` | exit 0, Ran 16 — OK (skipped=1) | exit 1, errors=1 | регрессия от архивирования |
| `thermogar_fe_steel_ui_test.py` | exit 1, Ran 24 — FAILED (failures=2, errors=3) | exit 1, ошибка импорта | падал и раньше |
| `thermogar_unified_app_test.py` | exit 1, Ran 9 — FAILED (failures=1, errors=5) | то же | падал и раньше |
| `thermogar_workspace_fe_context_test.py` | exit 1, Ran 15 — FAILED (errors=15) | то же | падал и раньше |

Сырые данные контрольного прогона: `_archive_codex\baseline_rerun_prearchive.json`.

## Пины на перенесённые файлы (для мастера проекта)

Конфиги в `configs\` ссылаются на пути, которых в рабочем дереве больше нет
(проверено сканом `configs\*.json`):

| Конфиг | Отсутствующий путь |
|---|---|
| `ne03_wave0_harness.json` | `results/validation/swr_ne02_feature_freeze/run_r1_20260824_023443/API_INVENTORY.csv` |
| `ne03_wave0_harness.json` | `results/validation/swr_ne03_numerical_verification/run_r0_plan_20260824_023443/NE03_COVERAGE_MATRIX.csv` |
| `ne03_wave0_harness.json` | `results/validation/swr_ne03_numerical_verification/run_r0_plan_20260824_023443/NE03_ENTRY_PLAN.md` |
| `ne03_wave2a_adapter_foundation.json` | `tools/thermogar_ne03_wave2_adapter_test.py` |
| `ne04_fe_diagnostic_domain_v4.json` | `results/validation/stage13_2/fe_internal_smoke_20260827_132243.json` |
| `ne04_fe_equilibrium_witness_v1.json` | `tools/verify_ne04_fe_local_witness.py` |
| `ne04_fe_local_witness_profiles.json` | `tools/thermogar_ne03_wave2_adapter_test.py` |

Механика: `app\thermogar_fe_local_witness_receipts.py:118-124` в `_is_symlink_or_reparse()`
возвращает `True` при любой `OSError`, поэтому отсутствующий файл диагностируется как
«pinned path crosses a symlink/reparse point» — сообщение об ошибке вводит в заблуждение,
реальная причина — файла нет.

## Отдельно: приложение

`.venv-windows\Scripts\python.exe -m streamlit run app\ThermoGar_app.py --server.headless true`
поднимается без traceback, `http://localhost:8501/` отвечает 200. Процесс остановлен, UI не кликался.
