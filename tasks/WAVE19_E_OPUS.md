Задание 19-Е: реестр и правила после выпуска 0.4.4. Мастер ThermoGar, 23.09.2026. Машина — ноутбук Windows 10, дерево D:\Pets\ThermoGar. Коммит прямо в main — санкция мастера (только tasks\).

ЗАПРЕТЫ
- Исключить до обхода: D:\Pets\Lilith — не открывать, не обходить, исключать из любого поиска/glob/rg/dir по диску.
- Ничего не удалять. Менять только tasks\REGISTER.md, tasks\RULES.md, tasks\WAVE19_E_*.md. Расчётов и приложения не запускать.
- На любом СТОП: остановиться, доложить.

ШАГ 0. git status --short — дословно в отчёт; изменения в отслеживаемых — СТОП. git fetch; git ls-remote origin main == 31f2f174a7868a0c4a370db074deea8f8372d2a8, иначе СТОП. git checkout main; git merge --ff-only origin/main.

ШАГ 1. tasks\REGISTER.md, тексты мастера дословно:
1а. Строка 19-Д: «**сдано, мастер не смотрел.**» -> «**принята мастером 23.09.2026.**»
1б. В бэклог после BL-59 две строки:
| BL-60 | `19-Д` | во время регрессии в `app/__pycache__` появился байткод трёх модулей (`thermogar_parallel`, `thermogar_db_cache`, `thermogar_database_repair`) внутри задания `tools/test_parallel_engine.py`, хотя родительский pytest шёл с `-B` (`tasks/WAVE19_D_REPORT.md`, п. 5); вероятно, пишут дочерние процессы пула, не проверено. Мешает `tools/thermogar_paths_test.py::test_005` в дереве разработки; у установленной программы после приёмки 19-Д `app/__pycache__` нет | **открыт, заведён 19-Е, мелочь** |
| BL-61 | `19-Д` | пример в шапке `packaging/build_installer.ps1` держит номер версии (`-Version 0.4.3`), а `tools/test_version_consistency.py` этот файл не проверяет (`tasks/WAVE19_D_REPORT.md`, отступление 3) | **открыт, заведён 19-Е.** В следующем выпуске поднять и внести файл в тест |
1в. В раздел волны 19, в конец, подраздел:
### Ошибка мастера (19-В2)
В задании 19-В2 регрессия ограничена двумя файлами (`tools/test_phase_description_order_words.py`, `tools/test_phase_description_stub_keys.py`). Новый модуль `app/thermogar_phase_descriptions.py` входит в нагрузку установщика (`packaging/stage_payload.ps1` берёт `app/*.py`), и тест состава поставки `tools/test_version_consistency.py::test_payload_list_is_complete` (ждал 75 файлов) после слияния 19-В2 в `main` стал красным (76). Поймала полная регрессия 19-Д, тест поправлен там же (`tasks/WAVE19_D_REPORT.md`, отступление 2). Правило записано в `tasks/RULES.md` 19-Е.

ШАГ 2. tasks\RULES.md, раздел «Ветки и слияния», в конец раздела пункт дословно:
* Задача, которая добавляет, убирает или переименовывает файл в нагрузке установщика (`app/*.py`, `configs/`, `databases/converted/`, `databases/physical/`, `licenses/`), обязательно прогоняет `tools/test_version_consistency.py` — он сверяет состав поставки. Причина — 19-В2.

ШАГ 3. Это задание сохранить дословно в tasks\WAVE19_E_OPUS.md. Один коммит; git push origin main; git ls-remote origin main — в отчёт.
Отчёт tasks\WAVE19_E_REPORT.md (тем же или следующим коммитом, пуш):
- итог одной строкой;
- отступления от задания;
- git log --oneline 31f2f17..main и git status --short — дословно.
