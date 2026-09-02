# Задача Волна 1B — конвейер Windows-установщика (Э5, подготовка)

Исполнитель: Opus (терминал, Windows). Корень: `C:\Users\gareg\Desktop\ThermoGar`.
Прочитай `PLAN_CLAUDE_2026-09-02.md` (разделы 0, 1, Э5, 3).
Зона: только `packaging\`, `ThermoGar-Installer-Assets\`, `dist\`, `tasks\`. Код в `app\` не трогать
(параллельно его правит другой исполнитель). Для пробной сборки брать `app\` как есть.

## Ветка
`git checkout -b wave1b-installer` от `main`. Коммиты по шагам. Не мержить.

## Цель
Рабочий, воспроизводимый конвейер: одна команда собирает `dist\ThermoGar-<версия>-win64.exe`,
который ставится/удаляется на этом ПК, ярлык из Start Menu запускает приложение, `healthcheck` зелёный,
`stop` останавливает. Без trust-manifest/SBOM/evidence-гейтов Codex. Пробная сборка — из текущего кода
(функциональность приложения на этом этапе не важна, важен конвейер).

## Что уже есть (использовать, не переписывать с нуля)
`packaging\launcher.pyw` (65 КБ, stdlib: LocalAppData-роты, loopback health, Job object), `stop.pyw`, `healthcheck.py`,
`ThermoGar.nsi`, `build_installer.ps1`, `stage_payload.ps1`, `stage_runtime_helpers.ps1`, `payload-policy.json`,
`product-version.json`, `assets\ThermoGar.ico`, `verify_installed_payload.ps1`, `clean_smoke.ps1`.
Рантайм: `ThermoGar-Installer-Assets\runtime-clean-3119\` (CPython 3.11.9 embeddable + site-packages).
Старая сборка `dist\ThermoGar-0.2.0-ne02-win64.exe` — эталон того, что конвейер когда-то работал.

## Шаги

### 1. Разведка (30 мин, без правок)
- NSIS: `C:\Program Files (x86)\NSIS\makensis.exe` есть? Если нет — скачать **zip-дистрибутив** NSIS 3.x
  (`nsis-3.xx.zip` с sourceforge, без установщика/UAC), распаковать в `ThermoGar-Installer-Assets\nsis\`,
  в `build_installer.ps1` сделать путь параметром с этим fallback.
- Прочитать `build_installer.ps1`, `stage_payload.ps1`, `ThermoGar.nsi`, `launcher.pyw`: выписать в
  `tasks\WAVE1B_NOTES.md` цепочку шагов сборки и все места, где проверяются hard-coded корни/SHA
  (`P0_ROOT`, `RUNTIME_ROOT`, `NATIVE_ROOT`, `_validate_trust`, `ExpectedRuntimeFileCount` и т.п.).
- Проверить, что в `runtime-clean-3119\Lib\site-packages` есть pycalphad, kawin, scheil, streamlit, symengine, numpy, scipy,
  matplotlib, pandas, openpyxl, xarray. Если чего-то нет — сверить с `.venv-windows\Lib\site-packages` и скопировать
  недостающие пакеты (только копирование, без pip в рантайм).

### 2. Упростить конвейер
- `launcher.pyw`: `_validate_trust` и проверку anchors заменить простой проверкой присутствия обязательных файлов
  (`runtime\python.exe`, `app\ThermoGar_app.py`, `databases\...`). Остальное (LocalAppData, `THERMOGAR_STATE_ROOT`,
  `MPLCONFIGDIR`, `TMP/TEMP`, `-B`, health/stop, Job) — сохранить. `stop.pyw`/`healthcheck.py` — согласовать.
- `stage_payload.ps1`: убрать обязательные `-Expected*` параметры/гейты; политика payload — простой allowlist:
  `app\*.py`, `app\style.css`, `configs\`, `databases\converted\`, `databases\physical\`, `databases\converted\fe\*.passport.json`,
  `.streamlit\config.toml`, `packaging\launcher.pyw|stop.pyw|healthcheck.py`, `README.md`, `USER_GUIDE_THERMOGAR.md`,
  `QUICK_START_THERMOGAR.md`, `THIRD_PARTY_NOTICES.txt`, рантайм целиком. Исключить `__pycache__`, `tools\`, `_archive_codex\`,
  `.venv-windows\`, `user_data\`, `results\`, `scripts\`, `docs\`, `databases\original|diagnostic|experimental`.
- Генерировать `manifests\payload-manifest.json` (path, bytes, sha256) — один файл, без receipt/trust.
- `generate_*.ps1` (sbom/notices/payload_manifest — сейчас заглушки 226 байт): SBOM не нужен;
  `THIRD_PARTY_NOTICES.txt` сгенерировать один раз скриптом из `*.dist-info\METADATA|LICENSE*` рантайма + отдельно
  абзац про базы MatCalc open databases (mc_ni/mc_al/mc_fe — лицензия из заголовков TDB в `databases\original`).
- `ThermoGar.nsi`: версия и имя — из `product-version.json`; установка в `$PROGRAMFILES64\ThermoGar`, один ярлык в Start Menu,
  uninstall из «Программы и компоненты», LocalAppData при uninstall сохраняется. Убрать зависимости от receipt-файлов.
- `build_installer.ps1`: один вход `-Version` (по умолчанию из `product-version.json`); шаги: stage → manifest → makensis → sha256 → `dist\`.
  Убрать `verify_distribution_evidence`, `verify_runtime_trust_manifest`, `verify_native_closure` из обязательной цепочки
  (файлы не удалять, просто не вызывать).
- `product-version.json`: `display_version` → `0.3.0`, `vi_product_version` → `0.3.0.0`.

### 3. Реальный smoke вместо синтетического P2
Написать `packaging\smoke_installed.ps1` (без admin, кроме самих install/uninstall — их запускать через `Start-Process -Verb RunAs`
с `/S` silent-режимом NSIS; если UAC-запрос блокирует автоматизацию — остановиться и написать в отчёт, что нужен клик):
1) silent install exe; 2) проверить файлы, ярлык, запись uninstall в реестре; 3) запустить `pythonw.exe launcher.pyw` из внешней папки;
4) `healthcheck.py --json` каждые 0.5 с до 60 с → `ok`; 5) `Invoke-WebRequest` на loopback-порт из health → 200 и в HTML есть «ThermoGar»;
6) `stop.pyw` → процессов/порта нет; 7) silent uninstall → Program Files пуст, `%LOCALAPPDATA%\ThermoGar` сохранён.
Результат — PASS/FAIL по каждому пункту в stdout и в `dist\smoke-<timestamp>.json`.
Старый `test_lifecycle_synthetic.ps1` и `clean_smoke.ps1` — перенести в `_archive_codex\packaging\`.

### 4. Пробная сборка и прогон
`build_installer.ps1` → `dist\ThermoGar-0.3.0-win64.exe` → `smoke_installed.ps1`. Добиться PASS по всем пунктам.
Записать размер и SHA-256 exe. Старый `dist\ThermoGar-0.2.0-ne02-win64.exe` и папку `P4_R13_*` — в `_archive_codex\dist\`.

### 5. Отчёт → `tasks\WAVE1B_REPORT.md` (≤ 25 строк) + в ответе
Что изменено в каждом скрипте, где NSIS, состав payload (число файлов/МБ), результат smoke по пунктам,
время сборки, коммиты, что требует ручного действия (UAC и т.п.), открытые вопросы.

## Запрещено
Править `app\`, `databases\`, `configs\`, `tools\`; пересобирать рантайм через pip; удалять файлы (только `_archive_codex\`);
вводить обратно trust/receipt/evidence-гейты.

## ДОПОЛНЕНИЕ (после инцидента с общим рабочим деревом)
- Работай ТОЛЬКО в своём worktree: 1A → `C:\Users\gareg\Desktop\ThermoGar-w1a`, 1B → `...\ThermoGar-w1b`, 1C → `...\ThermoGar-w1c`.
  Ветка там уже выбрана; `git checkout` других веток — запрещён. Папку `C:\Users\gareg\Desktop\ThermoGar` не трогать.
- Python всегда по абсолютному пути: `C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe`.
- Архив: `C:\Users\gareg\Desktop\ThermoGar\_archive_codex\` (абсолютный путь; в worktree этой папки нет).
- Рантайм для 1B: `C:\Users\gareg\Desktop\ThermoGar\ThermoGar-Installer-Assets\`; сборки класть в `<worktree>\dist\`.
- Перед стартом: `git -C <worktree> log --oneline -3` — убедись, что видишь свою ветку и коммит «Wave 1 task files».
