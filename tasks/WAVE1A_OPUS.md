# Задача Волна 1A — снять политику-заморозку (Э1)

Исполнитель: Opus (терминал, Windows). Корень: `C:\Users\gareg\Desktop\ThermoGar`.
Прочитай `PLAN_CLAUDE_2026-09-02.md` (разделы 0, 1, Э1, 3) и `TESTS_BASELINE.md`.
Python: `.venv-windows\Scripts\python.exe` (запуск тестов: `-I -B -X utf8`).

Параллельно работают ещё два исполнителя: 1B — только `packaging\` и `ThermoGar-Installer-Assets\`;
1C — только новый файл `tools\test_backend_calculations.py`. Не трогай их зоны.

## Ветка
`git checkout -b wave1a-unfreeze` от `main`. Коммиты по шагам. В конце — не мержить, оставить ветку.

## Цель
Все кнопки расчёта, скачивания и загрузки файлов становятся активными; баннеры
«DEVELOPMENT_NOT_RELEASED / PRODUCTION DENIED / research-only» убраны; тесты-sentinel убраны;
оставшиеся тесты зелёные. Поведение расчётов НЕ менять.

## Шаги

### 1. Архивировать 5 падающих тестов (решение мастера по итогам волны 0)
В `_archive_codex\tools\`: `thermogar_fe_steel_ui_test.py`, `thermogar_fe_equilibrium_witness_test.py`,
`thermogar_fe_local_witness_test.py`, `thermogar_unified_app_test.py`, `thermogar_workspace_fe_context_test.py`.
Коммит.

### 2. `app\thermogar_release_policy.py`
- `CALCULATIONS_ENABLED = EXPORTS_ENABLED = IMPORTS_ENABLED = True`.
- `APP_VERSION = "0.3.0"`, `APP_STAGE = "0.3.0"`, `APP_GATE` — удалить или `"-"`; `APP_NAME = "ThermoGar"`.
- `SOFTWARE_RELEASE_STATUS = "RESEARCH_SOFTWARE"`, `RELEASE_CLASS = "Исследовательское ПО — экспериментальная валидация не проводилась"`.
  `SCIENTIFIC_MATERIAL_STATUS`, `PRODUCTION_USE` — оставить как строки-метаданные (они попадают в паспорт), формулировки нейтральные:
  `"EXPERIMENTAL_QUALIFICATION_NOT_PERFORMED"`, `"NOT_ASSESSED"`.
- `RELEASE_DATABASE_KEYS = ("ni", "al", "fe")`; `DIAGNOSTIC_DATABASE_KEYS = ()`. Добавить `fe` в
  `RELEASE_DATABASE_ELEMENTS/FILENAMES/LABELS/RELATIVE_PATHS/SHA256` — данные взять из
  `DATABASE_DEFINITIONS` в `app\ThermoGar_app.py` (строки ~224–260) и `app\thermogar_restricted_fe_core.py`
  (файл `databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb`, SHA там же). Элементы Fe-базы — из заголовка TDB.
- `GATED_NUMERICAL_FEATURES` и логика `_feature`, подменяющая disposition на `DISABLED_PENDING`, — убрать
  (disposition = target). `*_BLOCK_REASON` — оставить строки, они больше не показываются.
- `RUNTIME_POLICY_GENERATION` — пересчитается сам.

### 3. `app\thermogar_release_ui.py` — обёртки становятся тонкими
- `release_download_button(*a, **kw)` → `return bool(st.download_button(*a, **kw))`.
- `release_calculation_button(*a, domain_request=None, project_root=None, **kw)` → `return bool(st.button(*a, **kw))`.
  Импорт `thermogar_ne04_domain` и вызов `evaluate_domain_request` удалить.
- `release_file_uploader` → `st.file_uploader(*a, **kw)`.
- `verified_feature_button`, `verified_equilibrium_button`, `verified_batch_*`, `verified_state_uploader`:
  посмотреть, что они делают; если внутри есть проверка `CALCULATIONS_ENABLED`/`EXPORTS_ENABLED`/`IMPORTS_ENABLED` —
  убрать, остальную логику (принятие `FeatureRequest`/`RejectedFeatureReceipt`) оставить.
- `render_result_evidence` — оставить, но проверить, что не печатает «PRODUCTION DENIED»-баннер (если печатает — свести к одной `st.caption`).

### 4. Остальные обращения к флагам
`grep -n "CALCULATIONS_ENABLED\|EXPORTS_ENABLED\|IMPORTS_ENABLED" app\*.py tools\*.py`.
Известные места: `ThermoGar_app.py:5735` (`if context_or_release_changed or not CALCULATIONS_ENABLED:`),
`thermogar_diffusion.py`, `thermogar_precipitation.py`, `thermogar_stage14.py`, `thermogar_workspace.py`,
`thermogar_verified_state.py`, `thermogar_stage12.py`. В каждом месте: ветка «флаг выключен» должна стать
недостижимой без изменения ветки «флаг включён». Не удалять сами импорты, если они используются в других местах.
`thermogar_ne04_domain.py` и `thermogar_ne04_fe_diagnostic_domain.py` больше никем не импортируются? Проверить `grep`;
если да — оставить файлы (удалим позже), ничего не делать.

### 5. Баннеры и тексты в `app\ThermoGar_app.py`
- Найти все `st.error/st.warning/st.info/st.caption`, содержащие «NE-0», «gate», «DEVELOPMENT_NOT_RELEASED»,
  «PRODUCTION», «DENIED», «заморож», «research-only», «диагностический режим», «не входит в release surface».
  Убрать или заменить одной строкой в сайдбаре: `st.sidebar.caption("ThermoGar 0.3.0 — исследовательское ПО. Экспериментальная квалификация: NOT_PERFORMED.")`.
- Таблица паспорта (строки ~4090–4100) — оставить, с новыми формулировками из шага 2.
- Заголовок страницы/`page_title` — «ThermoGar».
- Помощь/справка внутри (вкладка «Проекты и данные» → справка, строки ~10660–10810): убрать упоминания gate/NE/Stage,
  если есть. Не переписывать справку целиком — это Э4.

### 6. Тесты
- `grep -n "CALCULATIONS_ENABLED\|EXPORTS_ENABLED\|IMPORTS_ENABLED\|APP_VERSION\|0.2.0-ne02\|SWR-NE02\|sha256" tools\*_test.py tools\thermogar_self_test.py`.
  Ассерты вида «флаг == False», «версия == 0.2.0-ne02», «SHA файла app\… == …» — удалить или инвертировать.
  Проверки SHA **баз данных** (TDB/PDB) — оставить, это правильные пины.
- Прогнать все оставшиеся `tools\*_test.py` + `thermogar_self_test.py` (как в волне 0, таймаут 10 мин).
  Цель: все OK. Если тест падает из-за изменившегося поведения (кнопка теперь активна) — править тест.
  Если падает по другой причине — не чинить, описать в отчёте.
- `thermogar_fe_database_test.py` (193 с) и `thermogar_fe_internal_smoke.py` (175 с) можно прогнать один раз в конце.

### 7. Ручная проверка запуска
`streamlit run app\ThermoGar_app.py --server.headless true` → без traceback; открыть `http://localhost:8501`
через `curl`/`Invoke-WebRequest` (200). Дополнительно через `streamlit.testing.v1.AppTest`
(`AppTest.from_file("app/ThermoGar_app.py", default_timeout=120).run()`) убедиться, что `at.exception` пуст,
и что среди `at.button` нет ни одной с `disabled=True` кроме тех, что зависят от пользовательского ввода
(Hall–Petch/Taylor/Orowan переключатели). Записать число кнопок и число `disabled`.

### 8. Отчёт → `tasks\WAVE1A_REPORT.md` (≤ 25 строк) + в ответе
Изменённые файлы, что убрано, результаты тестов (таблица OK/FAIL), AppTest-счётчики, коммиты в ветке, открытые вопросы.

## Запрещено
Менять численные алгоритмы, TDB/PDB, `packaging\`, `tools\test_backend_calculations.py`; вводить SHA-пины;
удалять файлы (только `_archive_codex\`); рефакторить «для чистоты».

## ДОПОЛНЕНИЕ (после инцидента с общим рабочим деревом)
- Работай ТОЛЬКО в своём worktree: 1A → `C:\Users\gareg\Desktop\ThermoGar-w1a`, 1B → `...\ThermoGar-w1b`, 1C → `...\ThermoGar-w1c`.
  Ветка там уже выбрана; `git checkout` других веток — запрещён. Папку `C:\Users\gareg\Desktop\ThermoGar` не трогать.
- Python всегда по абсолютному пути: `C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe`.
- Архив: `C:\Users\gareg\Desktop\ThermoGar\_archive_codex\` (абсолютный путь; в worktree этой папки нет).
- Рантайм для 1B: `C:\Users\gareg\Desktop\ThermoGar\ThermoGar-Installer-Assets\`; сборки класть в `<worktree>\dist\`.
- Перед стартом: `git -C <worktree> log --oneline -3` — убедись, что видишь свою ветку и коммит «Wave 1 task files».
