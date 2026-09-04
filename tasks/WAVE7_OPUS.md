# Задача 7 — релиз 0.3.1: регресс, документы, тег

Worktree `C:\Users\gareg\Desktop\ThermoGar-w7`, ветка `wave7-release-0.3.1`. Python — основной venv по абсолютному пути.
Прочитай `tasks\WAVE4B_OPUS.md` (как гоняли регресс 0.3.0), `TESTS_RELEASE_0.3.0.md`, `tasks\WAVE5A/5B/5C/6_REPORT.md`.
Установщик уже собран волной 6 из этого же кода: `C:\Users\gareg\Desktop\ThermoGar-w6\dist\ThermoGar-0.3.1-win64.exe`
(SHA-256 A5750C15…AA09), smoke 8/8 — пересобирать не нужно, если код main не менялся (проверить `git diff` main vs
коммит сборки bd606b5 по `app\`, `configs\`, `databases\`, `packaging\`, `.streamlit\`; если пусто — exe валиден).

1. **Регресс** серийно, `PYTHONHASHSEED=0` в окружении: все `tools\thermogar_*_test.py` + `thermogar_self_test.py`,
   pytest-наборы `test_backend_calculations`, `test_ui_f/g/h`, `test_phase_presets`, `test_parallel_engine`,
   `test_parallel_integration`, `thermogar_db_cache_test` — `not slow` и `slow`. Таймаут 90 мин на набор.
   Результат — `TESTS_RELEASE_0.3.1.md` (та же форма, что 0.3.0) со сравнением: было 351/349.
   Ничего в `app\` не чинить; неожиданный FAIL — описать и остановиться.
2. **Документы**: `CHANGELOG.md` — раздел 0.3.1 закрыть датой, перечислить по отчётам 5A/5B/5C/6 (быстрые наборы
   фаз, параллельный движок с цифрами ускорения, кэш базы и первый старт, установщик, удалённый брокер, ленивый scheil);
   `HANDOFF.md` — раздел «Производительность» привести к факту (что параллелится, переключатель, пороги, память,
   `PYTHONHASHSEED`), таблица времён из `bench_parallel.md`; `docs\FEATURES.md` — обновить «Типичное время расчёта»
   и упомянуть переключатель «быстрый набор / все фазы»; `README.md` — версия и одна строка про ускорение.
3. Скопировать артефакты в `C:\Users\gareg\Desktop\ThermoGar\dist\release-0.3.1\` (exe, build.json, smoke json, отчёты).
   Рядом собрать **zip для раздачи**: `ThermoGar-0.3.1-win64.zip` с `ThermoGar-0.3.1-win64.exe`, `ThermoGar-0.3.1-win64.build.json`
   (SHA-256 внутри), `docs\FEATURES.md`, `QUICK_START_THERMOGAR.md`, `THIRD_PARTY_NOTICES.txt` и короткий `УСТАНОВКА.txt`
   (запуск exe, предупреждение SmartScreen «Подробнее → Выполнить в любом случае», ярлык в меню «Пуск», первый старт ~25 с,
   данные в `%LOCALAPPDATA%\ThermoGar`, как удалить). Записать размер и SHA-256 zip.
3a. **Установить 0.3.1 на этот ноутбук** как рабочую копию Gar'а: если стоит 0.3.0 — обновить поверх (silent-режим не нужен,
   обычная установка, один UAC у Gar), проверить, что проекты/история в `%LOCALAPPDATA%\ThermoGar` на месте и в
   «Программы и компоненты» версия 0.3.1; запустить с ярлыка, дождаться UI, сделать Fe T-скан 5 точек, оставить программу
   установленной (не удалять!).
4. `git tag -a v0.3.1 -m "ThermoGar 0.3.1"` на своём финальном коммите; отчёт `tasks\WAVE7_REPORT.md` ≤ 20 строк.
   Ветку не мержить.
