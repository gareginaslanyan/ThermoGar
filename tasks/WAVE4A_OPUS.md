# Задача 4A — релиз ThermoGar 0.3.0: сборка, установка, чистая машина, тег (Э5 + Э6)

Worktree `C:\Users\gareg\Desktop\ThermoGar-w4a`, ветка `wave4a-release`. Python/рантайм/NSIS — абсолютными путями из
основного репо (`C:\Users\gareg\Desktop\ThermoGar\.venv-windows`, `...\ThermoGar-Installer-Assets`). Сборки класть в
`<worktree>\dist\`. Прочитай `PLAN_CLAUDE_2026-09-02.md` (Э5, Э6), `tasks\WAVE1B_REPORT.md`, `tasks\WAVE1B_NOTES.md`,
`packaging\build_installer.ps1`, `packaging\smoke_installed.ps1`.
Gar рядом: install/uninstall требуют два UAC-клика на прогон — перед каждым smoke написать ему «нужен клик».

## Шаги
1. **Предполётная проверка** (без правок): `git log -1` = main; `product-version.json` = 0.3.0; `payload`-allowlist в
   `stage_payload.ps1` включает всё, что появилось после 1B: проверить, что в payload попадают `THIRD_PARTY_NOTICES.txt`,
   обновлённые `README.md`/`USER_GUIDE_THERMOGAR.md`/`QUICK_START_THERMOGAR.md`, `app\*.py` целиком, `configs\`,
   `databases\converted\` + `physical\` + fe passport, `.streamlit\config.toml`; и НЕ попадают `tools\`, `tasks\`, `_archive_codex`,
   `user_data`, `__pycache__`. Если allowlist отстал — поправить `stage_payload.ps1`.
2. **Мёртвый код в payload**: модули `app\thermogar_fe_*witness*.py`, `thermogar_ne04_*.py`, `thermogar_stage12.py`,
   `ThermoGar_steel_app.py`, `thermogar_steel_section.py`, `thermogar_wave2b_*.py`, `thermogar_fe_steel_adapter.py` —
   проверить `grep`-ом, что их не импортирует ни `ThermoGar_app.py`, ни модули, которые он импортирует (транзитивно).
   Неимпортируемые — перенести в `C:\Users\gareg\Desktop\ThermoGar\_archive_codex\app_dead\` (`git rm` из репо — это
   единственное разрешённое удаление из git; на диске файлы остаются в архиве). Прогнать `thermogar_self_test.py` и
   `tools\test_ui_f.py -m "not slow" -k "fe and single"` — зелёные. Если модуль всё же где-то импортируется — оставить.
3. **Сборка**: `packaging\build_installer.ps1` → `dist\ThermoGar-0.3.0-win64.exe`. Записать размер, SHA-256, время.
4. **Smoke на этом ПК**: `packaging\smoke_installed.ps1` → 7/7 PASS. Добавить в smoke 8-й шаг «обновление поверх
   установленной»: install → start → stop → install той же версии поверх (silent) → start → health OK → stop → uninstall,
   `%LOCALAPPDATA%\ThermoGar` с проектом пользователя переживает обновление (положить туда тестовый файл до, проверить после).
5. **Функциональный smoke установленной копии** (не из репо!): запустить установленную программу с ярлыка Start Menu,
   через браузер (или `Invoke-WebRequest` + AppTest нельзя — только реальный UI) на порту из health: открыть три базы,
   сделать по одному расчёту равновесия (Ni/Al/Fe), одну диаграмму (Ni бинарную), скачать один Excel. Скриншоты в
   `dist\smoke-screens\`. Если UI-автоматизации нет — сделать руками и приложить скриншоты; попросить Gar кликнуть.
6. **Чистая машина**: варианты по убыванию предпочтения — Windows Sandbox (`Get-WindowsOptionalFeature -Online
   -FeatureName Containers-DisposableClientVM`; если Disabled — сказать Gar, включение = галочка + перезагрузка),
   Hyper-V VM, второй ПК. В песочнице/VM: скопировать exe, установить, запустить с ярлыка, дождаться UI, расчёт Fe-равновесия,
   stop, uninstall. Зафиксировать: версия Windows, отсутствие Python в системе (`where python` пусто), время первого старта.
   Скриншот UI. Если ни один вариант недоступен — записать как открытый пункт, не блокировать тег.
7. **Тег и документы**: `CHANGELOG.md` (0.3.0: что изменилось относительно унаследованной 0.2.0-ne02 — по отчётам
   `tasks\WAVE*_REPORT.md`, 15–25 строк, по-русски); `HANDOFF.md` (1 страница: как запустить из папки, как собрать exe,
   как прогнать тесты — быстрые/медленные, структура репо, где данные пользователя, известные ограничения из
   `tools\backend_reference.md` и отчётов: Al-диаграммы медленные, Al-плотность без THETA_AL2CU, T₀ в узком окне, Fe KWN
   дорогой); обновить `PLAN_CLAUDE_2026-09-02.md` шапкой «Статус: 0.3.0 выпущен <дата>». `git tag -a v0.3.0 -m "ThermoGar 0.3.0"`
   в ветке — мастер перенесёт на main при мерже.
8. **Отчёт** `tasks\WAVE4A_REPORT.md` (≤ 30 строк): exe (путь/байты/SHA), smoke 8/8, чистая машина (что/как/результат),
   что удалено как мёртвый код, что требует Gar'а, открытые вопросы. Коммиты по шагам.

## Запрещено
Менять расчётный код и базы; возвращать trust/evidence-гейты; удалять что-либо кроме мёртвых модулей из шага 2 (и только с
переносом в архив); ставить пакеты в рантайм через pip.
