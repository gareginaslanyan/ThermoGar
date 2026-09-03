# Задача 3H — Проекты и данные + документация (Э3 + Э4)
Сначала прочитай `tasks\WAVE3_COMMON.md`. Worktree `C:\Users\gareg\Desktop\ThermoGar-w3h`, ветка `wave3h-projects-docs`.
Твои файлы: `app\thermogar_workspace.py`, `app\thermogar_stage14.py`, `app\thermogar_secure_io.py`, `app\thermogar_paths.py`,
`README.md`, `USER_GUIDE_THERMOGAR.md`, `QUICK_START_THERMOGAR.md`, `USER_DATA_README.txt`.

## Часть 1 — раздел «Проекты и данные» (× Ni/Al/Fe где применимо)
UI: `render_alloy_library` (workspace:903), `render_projects_and_history` (:1422), `render_batch_calculation` (:2185),
`render_quick_examples` (stage14:1071), диагностика/паспорт.
1. Библиотека сплавов: сохранить текущий состав под именем → появился в списке → загрузить обратно в сайдбар → экспорт JSON →
   импорт JSON (файл-uploader через AppTest или напрямую функцией) → корректно. Для Fe — с профилем thermogar_patch.
2. Пакетный расчёт: скачать шаблон CSV/XLSX → заполнить 3 состава → загрузить → расчёт → таблица результатов → экспорт.
   Для Fe — колонка «Фазы» без C15 (2B). Проверить CSV с `;` и `,`, UTF-8 и UTF-8-SIG.
3. Проекты: сохранить проект (14 ключей) → новый сеанс → загрузить → состояние восстановлено. История расчётов: запись
   появляется после расчёта в любом разделе (сверить с 3F/3G — им ничего не надо, только `record_calculation_history`),
   экспорт истории CSV, очистка с подтверждением.
4. Пути/состояние: `THERMOGAR_STATE_ROOT`/`%LOCALAPPDATA%\ThermoGar` — данные пишутся туда, не в папку программы (это критично для
   установленной версии в Program Files). Проверить, что при чистом `%LOCALAPPDATA%` первый запуск создаёт структуру без ошибок.
5. Импорт: `IMPORTS_ENABLED=True` с 1A — проверить, что uploader'ы реально принимают файлы, а «строгая схема» отклоняет мусор
   понятным сообщением, а не traceback. Лишние Codex-«receipt»-тексты в UI убрать; сами проверки схемы оставить.
6. Быстрые примеры (`render_quick_examples`): заполняют сайдбар для всех трёх баз; для Fe — пример стали.

## Часть 2 — документация (Э4)
Переписать `README.md`, `USER_GUIDE_THERMOGAR.md`, `QUICK_START_THERMOGAR.md` под ThermoGar 0.3.0:
что это, три базы (версии MatCalc, лицензия — см. `THIRD_PARTY_NOTICES.txt` и заголовки TDB), что считает каждый из 7 разделов,
как вводить состав, экспорт, где хранятся данные пользователя, как запускать из папки (`RUN_THERMOGAR_WINDOWS.cmd`) и через
установщик, как запускать тесты. Один абзац-дисклеймер: исследовательское ПО, экспериментальная валидация не проводилась,
Fe-база — патч с исключённой C15_LAVES. Ни слова про NE/gate/Stage/Codex. Опираться на `backend_reference.md` для реальных
времён расчёта (предупредить, что Al-диаграммы медленные). Объём: README ≤ 2 страниц, USER_GUIDE ≤ 8, QUICK_START ≤ 1.
`SOURCES.txt`, `PHYSICAL_DATA_README.md` — проверить актуальность, править минимально.

## Тесты
`tools\test_ui_h.py` (pytest, AppTest): библиотека/batch/проект/история по кейсу; существующие `thermogar_secure_io_test`,
`thermogar_state_migration_test`, `thermogar_active_state_io_test`, `thermogar_paths_test` — зелёные (кроме известного
test_006 про venv внутри worktree).
