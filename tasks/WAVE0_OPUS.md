# Задача Волна 0 — гигиена и baseline ThermoGar

Ты — исполнитель (Opus) в проекте ThermoGar. Мастер проекта — Claude, заказчик — Gar.
Работай в терминале на Windows. Корень проекта: `C:\Users\gareg\Desktop\ThermoGar`.
Прочитай сначала `PLAN_CLAUDE_2026-09-02.md` (раздел 0–1 и правила в разделе 3).

## Контекст (кратко)
ThermoGar — Streamlit-приложение CALPHAD (pycalphad) для Ni/Al/сталей. Предыдущий
исполнитель (Codex) оставил в корне сотни отчётов, evidence-папок, snapshot-копий и
тестов-«sentinel» с SHA-пинами. Git-репозитория нет. Цель этой задачи — сделать
чистый рабочий корень под git и зафиксировать, что работает СЕЙЧАС, ничего не чиня.

## Жёсткие правила
- НИЧЕГО не удалять. Только перемещать в `_archive_codex\`.
- Не менять код приложения (`app\`), базы (`databases\`), `configs\`, `packaging\`.
- Не трогать `.venv-windows\`. Python проекта: `.venv-windows\Scripts\python.exe` (3.11.9).
  Venv был создан в другом пути; если `pip` в нём не работает — не чинить, просто отметить в отчёте.
- Не ставить пакеты, не обновлять зависимости.
- Если что-то идёт не по плану (>2× времени, неожиданная структура) — остановись и опиши.

## Шаги

### 1. Битые имена файлов в корне
В корне 6 файлов с mojibake-именами (кириллица, отображается как `тХи╨│…`, `тАФ`):
`*_STAGE3.txt`, `*_STAGE4.txt` (три штуки), `*_THERMOGAR.md` (один с битым префиксом),
`HANDOFF*2026-08-24.md`. Найди их через PowerShell (`Get-ChildItem | ? { $_.Name -match '[^\x00-\x7F]' }`).
Переименуй в ASCII: `CODEX_STAGE3_NOTE.txt`, `CODEX_STAGE4_NOTE_1.txt` … `_3.txt`,
`CODEX_THERMOGAR_NOTE.md`, `HANDOFF_CODEX_2026-08-24.md`. Содержимое не менять.

### 2. Архивирование Codex-артефактов
Создай `_archive_codex\` и перемести туда (сохраняя имена):
- папки: `ThermoGar-Stage`, `ThermoGar-Stage-R2`, `ThermoGar-Stage-R2.R13-quarantine`,
  `ThermoGar-Stage.failed-json-overload-*`, `TG-NE02`, `TG-NE02-WINRUN`,
  `ThermoGar_Windows_*_bundle` (4 шт.), `ThermoGar-Evidence-R5`, `work`, `results\validation`,
  `docs\evidence`, `docs\stage15`, `projects` (если пустая), `templates`, `notebooks`;
- файлы корня: все `STAGE*`, `WHATS_NEW_*`, `INSTALL_STAGE*`, `CHECKSUMS_*`, `BUNDLE_CONTENTS_*`,
  `STATIC_AUDIT_*`, `PREBUILD_AUDIT_*`, `HIG_AUDIT_*`, `SECOND_BLOCK_*`, `FIRST_BLOCK_*`,
  `LEAD_RESPONSE_*`, `CURRENT_PROGRAM_PLAN.md`, `HANDOFF_CODEX_2026-08-24.md`,
  `CODEX_*` (из шага 1), `SPRAVKA_LILIT_SVERKA_BAZ.md`, `UPSTREAM_QUERY_C15_LAVES.md`,
  `FE_DATABASE_C15_LAVES_NOTICE.md`, `README_THERMOGAR.md` (дубликат README.md — сверь `fc`),
  `requirements-stage7.txt`, `INSTALL_STAGE12_MAC.command`, `RUN_TESTS_MAC.command`,
  `repair_thermogar_databases_mac.sh`, `docs\HIG_RULES.md`, `.DS_Store` (все);
- TDB из корня: `mc_ni_L (v1).tdb`, `mc_ni_L (v2).tdb`, `mc_ni_v2.034.original.tdb`,
  `mc_ni_v2.034.pycalphad.tdb` → `_archive_codex\root_tdb\`.
- `dist\` и `ThermoGar-Installer-Assets\` НЕ трогать (нужны для установщика).
- `tools\`: перемести в `_archive_codex\tools\` файлы: `thermogar_ne03*`, `thermogar_ne04*`,
  `verify_ne0*`, `thermogar_wave2b_*`, `thermogar_vlb_*`, `build_ne02_inventory.py`,
  `prebuild_audit.py`, `thermogar_c15_*`, `run_ne04_*`, `build_fe_patch_passport.py`,
  `finalize_fe_patch_acceptance.py`, `rebuild_fe_v2062_with_patch.py`, `tools\validation\`,
  `clean_smoke_*.ps1`, `launcher_job_descendant_test.py`. Остальные тесты оставить.
Перед перемещением сохрани полный листинг корня: `Get-ChildItem -Recurse -Exclude .venv-windows … > _archive_codex\INVENTORY_BEFORE.txt`
(без содержимого `.venv-windows`).

### 3. git
- `git init`, `.gitignore`: `.venv-windows/`, `__pycache__/`, `*.pyc`, `dist/`, `ThermoGar-Installer-Assets/`,
  `_archive_codex/`, `user_data/`, `.streamlit/secrets.toml`, `*.log`, `.DS_Store`.
- `git add -A`, коммит `"Inherited ThermoGar state from Codex, root cleaned (wave 0)"`.
- Проверь: `git status` чистый, `git ls-files | wc -l` разумный (сотни, не тысячи).

### 4. Baseline: приложение стартует
- Запусти `RUN_THERMOGAR_WINDOWS.cmd` (или `.venv-windows\Scripts\python.exe -m streamlit run app\ThermoGar_app.py --server.headless true`).
- Убедись, что сервер поднялся (лог Streamlit, `http://localhost:8501` отвечает 200).
  UI не кликать — достаточно старта без traceback. Останови процесс.

### 5. Baseline тестов
Для каждого оставшегося `tools\*_test.py` и `tools\thermogar_self_test.py`,
`tools\thermogar_fe_internal_smoke.py` запусти:
`.venv-windows\Scripts\python.exe -I -B -X utf8 tools\<file> --project-root C:\Users\gareg\Desktop\ThermoGar`
(если `--project-root` не поддерживается — без него; таймаут 10 минут на файл).
Запиши в `TESTS_BASELINE.md` таблицу: файл | exit code | «Ran N tests / OK|FAIL» или последняя строка |
время | комментарий (например «упал на проверке SHA файла — sentinel»).
Ничего не чинить.

### 6. Отчёт (≤ 25 строк, в конце ответа и в `tasks\WAVE0_REPORT.md`)
- что перемещено (счётчики файлов/папок), что переименовано;
- размер корня до/после, число файлов под git;
- стартовало ли приложение, версия Python/streamlit/pycalphad;
- итоги тестов: сколько OK / FAIL / timeout; какие FAIL похожи на sentinel (SHA), какие — на реальные баги;
- проблемы и вопросы мастеру проекта.
Второй коммит: `"Wave 0: tests baseline"`.
