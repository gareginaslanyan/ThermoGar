# Волна 1A — отчёт

Ветка `wave1a-unfreeze`, worktree `ThermoGar-w1a`, 7 коммитов от `f70aaa8`. Изменены `app\thermogar_release_policy.py`, `app\thermogar_release_ui.py`, `app\ThermoGar_app.py`, `tools\thermogar_diffusion_test.py`, `tools\thermogar_self_test.py`; 5 падавших тестов перенесены в `ThermoGar\_archive_codex\tools\`.

Убрано: флаги → `True`; версия `0.3.0`, `APP_GATE = "-"`, `APP_NAME = "ThermoGar"`; `fe` добавлен в release-поверхность (25 элементов из заголовка TDB без `VA`, путь/метка/SHA из существующих определений — новых пинов нет); `GATED_NUMERICAL_FEATURES` и подмена disposition на `DISABLED_PENDING`; NE-04-evaluator и проверки флагов в обёртках; `or not CALCULATIONS_ENABLED` в `ThermoGar_app.py`; тексты NE/gate/«заморожен» → одна строка в сайдбаре. Паспорт и `*_BLOCK_REASON` оставлены.

Тесты (`.venv-windows\Scripts\python.exe -I -B -X utf8`, project-root = worktree):

| Итог | Файлы |
|---|---|
| OK, 18 | active_state_io, converter_patch, diffusion, fe_internal_smoke_test, physical, precipitation, properties, restricted_fe_core, secure_io, self_test, state_migration, verified_equilibrium, verified_loaders, verified_physical, verified_properties, verified_state; отдельно fe_database (349 с, PASSED) и fe_internal_smoke (314 с, `COMPLETE_DIAGNOSTIC_ONLY`) |
| FAIL, 1 | `thermogar_paths_test.py::test_006` требует интерпретатор `<project_root>\.venv-windows`, которого в worktree нет (ДОПОЛНЕНИЕ предписывает venv основного репозитория). Артефакт worktree, не чинил. `test_005` падает дополнительно, если перед прогоном запускалось приложение — оно пишет `app\__pycache__`; после очистки проходит |

AppTest (`default_timeout=300`, база по умолчанию Fe): `at.exception` — 0 до и после. Кнопок 28 → 26, из них `disabled` 14 → 2; `download_button` 0 → 2 (0 disabled). Оставшиеся `kin_single_run_fe` и `kin_hom_run_fe` выключены пользовательским вводом (`input_provenance` + подтверждение) — разрешённое исключение. `streamlit run --server.headless true` — без traceback, порт 8511 отвечает 200.

Открытые вопросы:

1. Исправлен предсуществующий дефект `_TDB_PHASE_DECLARATION` (`ThermoGar_app.py:554`): регистронезависимый поиск ловил библиографию TDB («Phase diagram in the iron-rich corner…») и отдавал `diagram`, `equilbria`, `equilibria`, `relations`, `stability` как фазы — привязка базы падала, приложение останавливалось до отрисовки. Воспроизведено на `f70aaa8` без правок 1A. Без `(?i)` теряются ровно эти слова: Ni 103→99, Al 196→195 — совпадает с ожидаемым в `thermogar_self_test`. Выход за рамки задания, но без него шаг 7 невыполним.
2. `BINDING_STALE: State binding is stale.` при первом рендере — есть и до, и после 1A. Не трогал.
3. `RELEASE_DATABASE_KEYS` включает `fe`, но hard-reject Fe в `thermogar_diffusion.py` и `thermogar_precipitation.py` остался (у них своя проверка) — это Э2.
4. Зона 1B: `packaging\build_installer.ps1:731` и `packaging\verify_distribution_evidence.ps1:476` пинят `APP_STAGE = "SWR-NE02"` и `APP_VERSION = "0.2.0-ne02"` — сборка упадёт, пока пины не сняты.
5. Коммит шага 1 из прерванной первой сессии остался на ветке `wave1b-installer` как `343468f`.
6. `verified_batch_file_uploader` всегда рисует disabled-кнопку, но ниоткуда не вызывается и проверок флагов не содержит — оставлен как есть.
