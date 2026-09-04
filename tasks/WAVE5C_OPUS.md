# Задача 5C — backlog 0.3.0: установщик, документы, мелочи

Прочитай `tasks\WAVE5_COMMON.md`, `tasks\WAVE4A_REPORT.md` (раздел «Открытые вопросы»), `HANDOFF.md`.

1. `packaging\ThermoGar.nsi`: `${GetSize}` по 15 тыс. файлов занимает ~2 мин при установке — заменить на константу
   `EstimatedSize`, которую `build_installer.ps1` вычисляет на этапе stage и передаёт через `/D`. Проверить, что
   «Программы и компоненты» показывает размер.
2. Первый старт ~40 с: разобрать, из чего складывается (импорт pycalphad/symengine, парсинг TDB, `filter_phases`,
   привязка PDB). Что можно дёшево: кэш разобранной базы на диске (`pycalphad` умеет `Database.to_file` в pickle-формат?
   проверить; либо свой pickle разобранного `Database` рядом в `%LOCALAPPDATA%\ThermoGar\cache\` с ключом SHA),
   ленивый импорт kawin/scheil до первого обращения к разделу. Не ломать fail-closed проверки SHA баз. Замер до/после.
3. `thermogar_release_policy.py`: строка `FEATURES` с `app/thermogar_stage12.py` — убрать (модуль удалён).
   Заодно проверить остальные строки таблицы на ссылки на удалённые модули (`thermogar_ne04_domain`, witness и т.д.);
   таблица не отображается — можно либо почистить, либо удалить целиком вместе с `feature_rows()`, если grep
   подтверждает, что нет потребителей. Не трогать константы выше таблицы (их правит 5A).
4. `smoke_installed.ps1`: сейчас 5 UAC-запросов на прогон — свести к 2 (один elevated-скрипт на install+uninstall
   в начале/конце, либо `Start-Process -Verb RunAs` один раз на elevated helper, который делает всё). Если не выходит
   без риска — оставить, описать.
5. Документы: `HANDOFF.md` и `README.md` — раздел «Производительность» (что медленно, почему, что придёт в 0.3.1);
   `CHANGELOG.md` — заготовка раздела 0.3.1 (Unreleased). `docs\FEATURES.md` уже есть — ссылку из README.
6. `product-version.json` → 0.3.1 / 0.3.1.0.
Тесты: `thermogar_self_test`, `verified_loaders_test`, пробная сборка exe + smoke 8/8 (UAC — Gar).
Отчёт: замер первого старта до/после, размер exe, время установки.
