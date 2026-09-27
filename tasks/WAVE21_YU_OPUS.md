Задание 21-Ю: выпуск 0.5.0 — слияния 21-Щ и 21-Э в main; BL-78 (предварительный просмотр пакета); пересъёмка кадров «Проектов», HTML; CHANGELOG, HANDOFF, NOTICES, комментарий установщика; реестр; регрессия и сверка эталона; слияние, тег v0.5.0; установщик; установка поверх 0.4.4; приёмка на установленной программе и ярлык на рабочем столе. Мастер ThermoGar, 27.09.2026. Машина — ноутбук Windows 10, дерево D:\Pets\ThermoGar-w21b. Тяжёлый поток, параллельных задач нет. Это санкция мастера на слияния wave21-shch, wave21-eh (ШАГ 1) и wave21-yu (ШАГ 8) в main, тег v0.5.0 и пуш. Образец порядка — tasks\WAVE19_D_OPUS.md и tasks\WAVE19_D_REPORT.md (выпуск 0.4.4). Сценарии — results\wave21_eh\scripts\ (21-Э), вывод — results\wave21_yu\.

ЗАПРЕТЫ
- Исключить до обхода: D:\Pets\Lilith — не открывать, не обходить, исключать из любого поиска/glob/rg/dir по диску (в т. ч. при поиске makensis и runtime). Поиск — только внутри D:\Pets\ThermoGar-w21b, D:\Pets\_archive, C:\Program Files\ThermoGar, C:\Program Files (x86)\NSIS.
- D:\Pets\ThermoGar и D:\Pets\ThermoGar-w21a не трогать. Интерпретатор — D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe. Архивы D:\Pets\_archive не менять.
- Байты databases\ не менять. Код приложения — только BL-78 (ШАГ 3). Новых слов на экране нет: BL-78 берёт готовые подписи сводки и боковой панели; любой другой новый текст на экране — СТОП.
- После слияний ШАГА 1 меняются только: app\thermogar_workspace.py, tools\test_wave21_yu.py, docs\guide\img\ (кадры, _manifest.json), docs\guide\ThermoGar_Guide_0.5.0.html, CHANGELOG.md, HANDOFF.md, packaging\ThermoGar.nsi, THIRD_PARTY_NOTICES.txt, tasks\REGISTER.md, tasks\WAVE21_YU_OPUS.md, tasks\WAVE21_YU_REPORT.md, results\wave21_yu\. Нужно другое — СТОП.
- Ничего не удалять: rm, del, Remove-Item, rmdir не применять; лишнее — D:\Pets\ThermoGar-w21b\_to_delete\21yu_<что>\ + опись sha256. (Прежние кадры сценария стирает сам make_guide_screens.py, свою папку stage — сам build_installer.ps1.)
- Все прогоны — PYTHONHASHSEED=0, MPLBACKEND=Agg, THERMOGAR_STATE_ROOT во временной папке (раннер ШАГА 7 ставит свою — results\validation\wave21_yu_state, вне git); pytest — с -B; приложение и AppTest — с PYTHONDONTWRITEBYTECODE=1; перед тяжёлым прогоном свободно не меньше 3 ГиБ; одновременно один тяжёлый прогон.
- Номера строк — замер мастера на модели слияния ШАГА 1, сверить; тексты «было» — дословно, иначе СТОП.
- На любом СТОП: остановиться, доложить, не подгонять.
- Время начала и конца каждого шага — в отчёт.

ШАГ 0. В D:\Pets\ThermoGar-w21b: git status --short — только «?? _to_delete/», иначе СТОП. git fetch origin --tags (при обрыве сети — адресный git fetch origin main wave21-shch wave21-eh и git fetch origin --tags). git ls-remote origin main wave21-shch wave21-eh: main — 062b97503bb1142c38020c33c17b0de30fd15a88, wave21-shch — 7a73ee081d1414840cb59c2bde14fb63f347c602, wave21-eh — 5ab5bf1f9dd76b4b3035702fa7b1171efe5202af, иначе СТОП. Свободная память и $env:CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP — в отчёт (переменной нет — записать, не СТОП). Чужой байткод app\__pycache__ и tools\__pycache__ — в _to_delete\21yu_pycache\ с описью.

ШАГ 1. Слияния. git switch --detach origin/main; по порядку, git merge --no-ff:
1) origin/wave21-shch -m "Merge wave21-shch: BL-77, краткое руководство, пересъёмка руководства 0.5.0 (21-Щ)" — дерево 34b3b0d2b256c139eeddd0267a5e5b90b9a48d4f;
2) origin/wave21-eh -m "Merge wave21-eh: ярлык на рабочем столе (BL-62), BL-61, CHANGELOG 0.5.0, сценарии выпуска (21-Э)" — дерево 0c729080b772fadc4659f5dcfa9904f1d95c5511.
Другое дерево или конфликт — СТОП (модель мастера: оба слияния чистые). Зелёные, иначе СТОП; числа — СВЕРИТЬ: tools\test_version_consistency.py (93), tools\test_installer_shortcut_bl62.py (5), tools\test_wave21_shch.py (16), tools\test_wave21_ts.py (9), tools\test_wave21_ch.py (5), tools\test_wave21_x.py (6). git push origin HEAD:refs/heads/main; git switch -c wave21-yu. Это задание без первой строки «/caveman ultra» — дословно в tasks\WAVE21_YU_OPUS.md, первый коммит ветки.

ШАГ 2. Runtime. Из D:\Pets\_archive\ThermoGar.zip каталог ThermoGar/ThermoGar-Installer-Assets/runtime-clean-3119/ — во временную папку сессии вне дерева, через Python zipfile (unzip из Git Bash архив 3,2 ГБ zip64 не распаковывает — 19-Д, отступление 11). Сверить с C:\Program Files\ThermoGar\manifests\payload-manifest.json установленной 0.4.4 все файлы runtime/ по sha256: СВЕРИТЬ 15 003 файла, расхождений 0 — иначе СТОП. Вывод — results\wave21_yu\runtime_check.txt.

ШАГ 3. BL-78. «Проекты и данные → Пакетный расчёт», таблица «Предварительный просмотр» показывает внутренние обозначения ni, NI, at, metastable; сводка под ней — подпись базы, символ основы, «ат.%». Правка — только показ, теми же словами, что сводка и боковая панель:
- app\thermogar_workspace.py, batch_preview_dataframe (:2296): подписи столбцов — как сейчас; значения:
  - «База» — подпись RELEASE_DATABASE_LABELS, как в batch_summary_display (:2309);
  - «Основа» и «Добавки» — composition_columns_for_display, как в сводке;
  - «Единицы» — "at" → «ат.%», "wt" → «мас.%», как в сводке;
  - «Режим стали»: у строк базы fe значения "metastable" и "stable" → steel_mode_label (:739); у строк ni и al "metastable" и "stable" → None (на экране прочерк: placeholder у таблицы уже стоит, :2841–2846); любое другое значение — как есть (такая строка потом падает своим сообщением «Неизвестный режим стали: …»).
  - Входную таблицу не менять: разбор, batch_source_digest, расчёт и выгрузки берут её.
- Новый tools\test_wave21_yu.py, без AppTest. CSV с заголовками TEMPLATE_HEADERS → thermogar_verified_state._parse_csv → batch_table_dataframe; пять строк: «Ni–12Al» (ni, Ni, ат.%, 700, Al=12, режим пусто); «Fe-мета» (fe, FE, мас.%, 700, C=0.8, метастабильный); «Fe-стаб» (fe, Fe, мас.%, 700, C=0.8, стабильный); «Fe-опечатка» (fe, FE, мас.%, 700, C=0.8, metastabe); «Al-стаб» (al, AL, ат.%, 500, CU=4, stable). От batch_preview_dataframe ждать: подписи столбцов прежние; «База» — подписи RELEASE_DATABASE_LABELS для ni, fe, fe, fe, al; «Основа» — Ni, Fe, Fe, Fe, Al; «Единицы» — ат.%, мас.%, мас.%, мас.%, ат.%; «Режим стали» — пусто (isna), steel_mode_label("metastable"), steel_mode_label("stable"), «metastabe», пусто; «Добавки» — Al=12, C=0.8, C=0.8, C=0.8, Cu=4; входная таблица равна своей копии до вызова. Сначала — красный на коде до правки (число failed — в отчёт), потом зелёный.
Коммит.

ШАГ 4. Кадры «Проектов» и HTML.
- python -X utf8 tools\make_guide_screens.py --only proekty --no-html — 8 кадров proekty-01…08.
- После --only в docs\guide\img\_manifest.json только 8 записей. Собрать полный: записи прежнего (git show HEAD:docs/guide/img/_manifest.json) по порядку, 8 записей proekty-* заменить новыми (по image), generated_utc — новый. СВЕРИТЬ: 56 записей; image и title у proekty-* прежние; записи остальных 48 кадров равны прежним (сравнение как JSON).
- Каждый из 8 кадров посмотреть. На proekty-05 и proekty-06 в «Предварительном просмотре»: «Никелевые сплавы — mc_ni 2.036», Ni, ат.%, в «Режиме стали» — прочерк. В остальном кадры — как у 21-Щ: в боковой панели Ni, «атомные %», «Al=15»; «Загружено: Опытный Ni–15Al» — с proekty-03. Расхождение сверх предпросмотра — переснять все 9 сценариев одним прогоном без --only (как 21-Щ, ШАГ 5; _manifest.json тогда пишется целиком) и доложить.
- python -X utf8 tools\make_guide_screens.py --html → docs\guide\ThermoGar_Guide_0.5.0.html: встроено 56 картинок, набор sha256 = кадры docs\guide\img\*.png; ThermoGar_Guide_0.4.*.html не трогать.
Коммит (кадры, _manifest.json, HTML).

ШАГ 5. Тексты выпуска — мастера дословно. <дата выпуска> — сегодняшняя местная дата ГГГГ-ММ-ДД; если к ШАГУ 8 дата сменится — поправить CHANGELOG.md, HANDOFF.md и реестр отдельным коммитом до слияния.
а) CHANGELOG.md:3 — в «## 0.5.0 — <дата выпуска>» вместо «<дата выпуска>» дата. После строки :51 (пункт «* **«Загружено: …» в боковой панели (BL-77 / 21-Щ).** …») — строка:
* **Пакетный расчёт: «Предварительный просмотр» (BL-78).** Таблица показывала внутренние обозначения — ni, NI, at, metastable. Теперь база, основа и единицы — как в сводке расчёта («Никелевые сплавы — mc_ni 2.036», Ni, ат.%), режим стали — как в боковой панели; у строк никелевых и алюминиевых сплавов режима стали нет — прочерк.
б) HANDOFF.md:1 «# HANDOFF — ThermoGar 0.4.4» → «# HANDOFF — ThermoGar 0.5.0»; :10 «**Выпущено:** 0.4.4 от 2026-09-23; предыдущий выпуск 0.4.3 от 2026-09-19.» → «**Выпущено:** 0.5.0 от <дата выпуска>; предыдущий выпуск 0.4.4 от 2026-09-23.»
в) packaging\ThermoGar.nsi:5–6
было:
```
; installer copies the staged tree, drops one Start Menu shortcut and
; registers an uninstaller.
```
стало:
```
; installer copies the staged tree, drops a Start Menu shortcut and a
; desktop shortcut (BL-62) and registers an uninstaller.
```
Остальное в файле не менять; tools\test_installer_shortcut_bl62.py — зелёный.
г) THIRD_PARTY_NOTICES.txt — перевыпустить: packaging\generate_notices.ps1 -RuntimeSource <runtime ШАГА 2>. СВЕРИТЬ: git diff — одна строка «Generated: …» (UTC-дата); иначе СТОП.
tools\test_version_consistency.py — зелёный. Коммит.

ШАГ 6. tasks\REGISTER.md — тексты мастера дословно, <…> заполнить (хеш — 7 знаков коммита слияния ШАГА 1). Коммит.
а) Таблица волны 21.
- Строка 21-Щ: в начале ячейки состояния «**сдано, мастер не смотрел.**» → «**принята мастером 27.09.2026 (ниже); влита в `main` (`<хеш слияния wave21-shch>`).**», остальное в ячейке не менять.
- Строка 21-Э: ячейку состояния «**в работе.**» → «**принята мастером 27.09.2026 (ниже); влита в `main` (`<хеш слияния wave21-eh>`).** BL-62 — ярлык `$DESKTOP\ThermoGar.lnk` в `packaging/ThermoGar.nsi` (создаётся после ярлыка «Пуска», удаляется вместе с ним), `README.md`, `QUICK_START_THERMOGAR.md`, `tools/test_installer_shortcut_bl62.py` — 5 passed (до правки 3 failed); BL-61 — `-Version 0.5.0` в `packaging/build_installer.ps1`, тест в `tools/test_version_consistency.py`; `HANDOFF.md:83`; раздел CHANGELOG 0.5.0; сценарии выпуска `results/wave21_eh/scripts/` — раннер, сверка эталона, приёмка; эталон справочника фаз `results/wave21_eh/spravochnik_faz/` — 99 / 195 / 132 строки. Отчёт `tasks/WAVE21_EH_REPORT.md`».
б) После абзаца «Решения владельца, 26.09.2026 (краткое руководство). …» — два абзаца:

Приёмка 21-Щ мастером (27.09.2026). Замер мастера по `main` (`062b975`) и `wave21-shch` (`7a73ee0`, от `062b975`): слияния 21-Х (`27e1e98`) и 21-Ш (`062b975`) — деревья `5861b1c`, `3de0080` = модель мастера; задание дословно, тексты реестра — на своих местах (проверка скриптом); четыре текста краткого руководства — дословно. BL-77: `_thermogar_loaded_context` хранит значения основы, единиц, добавок, давления и режима стали, `loaded_context_is_current` снимает «Загружено: …» при любом расхождении; режим стали сравнивается только у стали (у Ni и Al его виджета нет, Streamlit стирает ключ). Сценарии съёмки — символы элементов; 56 кадров: в `soobshcheniya-02…05` «Загружено: …» нет, на `proekty-03…08` есть (поля после загрузки не менялись). Числа глав сверены с выгрузками замера исполнителя: доля γ′ к 10⁻⁴ ч — 21,9 %, максимум плотности частиц — 8,69·10²⁴ 1/м³, Cr отличается от исходного больше чем на 1 ат.% в полосе 687,5–1312,5 мкм (оценка мастера на глаз — около 600 и 1500 мкм; по правилу задания верно 700 и 1300). HTML 0.5.0 — 56 встроенных кадров = 56 на диске, прежних текстов нет. На Linux `test_wave21_shch` — 14 passed, 2 теста с AppTest идут только на Windows; `test_wave21_ts`, `test_wave21_ch`, `test_wave21_x` — 20 passed. Регрессия исполнителя: 39 файлов pytest — 840 passed, 1 xfailed; 12 unittest — 203 OK; 7 сценариев — PASSED. Попутно исполнитель доложил внутренние обозначения в предварительном просмотре пакета — BL-78.

Приёмка 21-Э мастером (27.09.2026). Замер мастера по `wave21-eh` (`5ab5bf1`, от `e27c36c`): задание дословно; изменены `packaging/ThermoGar.nsi` (ярлык `$DESKTOP\ThermoGar.lnk` при `SetShellVarContext all` — общий рабочий стол; создаётся после ярлыка «Пуска», удаляется вместе с ним), `README.md:103–104`, `QUICK_START_THERMOGAR.md:11`, `packaging/build_installer.ps1:14`, `HANDOFF.md:83`, `tools/test_version_consistency.py` (пример `-Version` в `build_installer.ps1` сверяется с `APP_VERSION`), `CHANGELOG.md` (раздел 0.5.0 = черновик 21-Ф с правками мастера), новые `tools/test_installer_shortcut_bl62.py` и `results/wave21_eh/`. Слияние смоделировано мастером: `062b975` + `wave21-shch` → дерево `34b3b0d`, + `wave21-eh` → `0c72908`, конфликтов нет; на модели `test_version_consistency` и `test_installer_shortcut_bl62` — 98 passed. Сценарии выпуска: раннер на модели — 76 заданий; сверка эталона без времён, «PASS» — только при разнице в одной ячейке «KWN (модуль) | fe» с 1123 строками кинетики (число ноутбука, 21-О); приёмка — 0.5.0, «Последовательный расчёт.», эталон (в) — новые CSV справочника фаз (99 / 195 / 132 строки; от CSV 19-В2 отличаются одной строкой на базу — «модель порядок/беспорядок», 21-Ж). Холостые прогоны — как ожидалось. Отступления исполнителя приняты; комментарий `packaging/ThermoGar.nsi:5` правит 21-Ю.

в) После раздела «### Ошибка мастера (21-Ц)» (перед «## Волна 22 …»):

### Ошибка мастера (21-Ж, предпросмотр пакета)

В дополнении к 21-Ж мастер дал столбцам «Предварительного просмотра» пакетного расчёта подписи словами «Требуемых столбцов», а значения не тронул: база, основа, единицы и режим стали остались внутренними обозначениями `ni`, `NI`, `at`, `metastable`, хотя сводку под таблицей 21-Ж и 21-Ж2 перевели на подпись базы, символ основы и «ат.%» / «мас.%». При приёмке 21-Х мастер смотрел кадры `proekty-05`, `proekty-06` и этого не заметил; доложил исполнитель 21-Щ (отступление 8). Исправлено 21-Ю (BL-78).

г) Таблица бэклога.
- BL-61: ячейку состояния → «**закрыт 21-Э (принята мастером 27.09.2026).**».
- BL-62: в ячейке состояния «**В работе, 21-Э.**» → «**Закрыт 21-Э (принята мастером 27.09.2026).**», остальное не менять.
- BL-77: ячейку состояния → «**закрыт 21-Щ (принята мастером 27.09.2026).**».
- После строки BL-77:
| BL-78 | `21-Щ` | «Проекты и данные → Пакетный расчёт», таблица «Предварительный просмотр»: база, основа, единицы и режим стали — внутренние обозначения `ni`, `NI`, `at`, `metastable` (кадры `proekty-05`, `proekty-06` 21-Щ; отчёт 21-Щ, отступление 8): `batch_preview_dataframe` (`app/thermogar_workspace.py`) меняет только подписи столбцов, а сводка под таблицей (`batch_summary_display`) показывает подпись базы, символ основы и «ат.%» / «мас.%»; режим стали стоит и у строк Ni и Al, где он не действует | **закрыт 21-Ю.** База, основа и единицы — как в сводке; режим стали у строк стали — подписью боковой панели, у строк Ni и Al — прочерк, нераспознанное значение — как в файле; данные, разбор файла и выгрузки прежние. |

ШАГ 7. Регрессия и сверка эталона.
- D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe -B -X utf8 results\wave21_eh\scripts\run_regress.py — каждый файл отдельным процессом; test_ui_f -m slow одним процессом только при ≥ 6,0 ГиБ свободных. СВЕРИТЬ: 77 заданий (41 tools\test_*.py, 19 tools\thermogar_*_test.py, 9 slow, test_ui_f slow, 7 сценариев). Выход 5 («no tests ran», всё отобрано -m) допустим — списком в отчёт; остальные ненулевые — красные: разобрать; своё — чинить, чужое и не от среды — СТОП. Какой интерпретатор взял раннер — в отчёт.
- Тем же интерпретатором: python -B -X utf8 results\wave21_eh\scripts\backend_compare.py → results\wave21_yu\backend_compare.txt. Ожидание — «ВЕРДИКТ: PASS»: разница только в ячейке «[Кинетика] KWN (модуль) | fe», строк кинетики 1123. Иначе — СТОП.
Коммит results\wave21_yu\.

ШАГ 8. Слияние и тег. git fetch origin; git ls-remote origin main — коммит слияния wave21-eh ШАГА 1, иначе СТОП. git switch --detach origin/main; git merge --no-ff wave21-yu -m "Merge wave21-yu: release 0.5.0" — дерево = дерево wave21-yu, иначе СТОП. Проверки, вывод дословно: git diff --stat <коммит слияния wave21-eh> HEAD -- databases — пусто; git diff --stat v0.4.4 HEAD -- databases — один файл databases/physical/overrides/physical_data_v103.overrides.json (21-Ж2); иначе СТОП. git tag -a v0.5.0 -m "ThermoGar 0.5.0 — <дата выпуска>"; git push origin HEAD:refs/heads/main; git push origin v0.5.0; git ls-remote origin refs/heads/main "refs/tags/v0.5.0*" — дословно в отчёт.

ШАГ 9. Установщик. Снимок — только git -c core.autocrlf=false archive v0.5.0 (пути нагрузки и packaging\) во временную папку сессии: СВЕРИТЬ 83 файла (у 0.4.4 — 82, добавился app/thermogar_user_errors.py), все байт в байт = блобам v0.5.0. Сборка: packaging\build_installer.ps1 -RepoRoot <снимок> -RuntimeSource <runtime ШАГА 2> -OutputDir D:\Pets\ThermoGar-w21b\dist\release-0.5.0 (makensis — C:\Program Files (x86)\NSIS). СВЕРИТЬ «project files staged: 78». В отчёт: размер в байтах, sha256, ProductVersion и FileVersion exe — 0.5.0. THIRD_PARTY_NOTICES.txt снимка после сборки = блобу v0.5.0; отличие только в строке Generated (сборка в другие сутки UTC) — доложить; другое — СТОП. Лог — results\wave21_yu\build.log.

ШАГ 10. Установка поверх 0.4.4.
- До (results\wave21_yu\installed_044_before.txt): DisplayVersion в HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\ThermoGar — 0.4.4; sha256 C:\Program Files\ThermoGar\Uninstall.exe (СВЕРИТЬ 60ca53dc…), runtime\python.exe (5f7b89a6…), app\ThermoGar_app.py (= блоб v0.4.4, 12310733…).
- Если установленная программа запущена (процессы из C:\Program Files\ThermoGar\runtime) — написать владельцу «Закройте ThermoGar» и ждать; самому не закрывать.
- Перед запуском написать владельцу: «Сейчас будет запрос UAC — подтвердите». dist\release-0.5.0\ThermoGar-0.5.0-win64.exe /S — один запрос UAC, подтверждает владелец.
- После (results\wave21_yu\installed_050_check.txt): DisplayVersion 0.5.0; payload-manifest.json — все файлы по sha256, расхождений 0 (СВЕРИТЬ 15 080 = 15 003 в runtime/ + 77); 77 файлов вне runtime/ — байт в байт с блобами v0.5.0; runtime\python.exe — прежний; app\ThermoGar_app.py = блоб v0.5.0 (СВЕРИТЬ 69a92d4d…).

ШАГ 11. Приёмка на установленной программе. Интерпретатор — "C:\Program Files\ThermoGar\runtime\python.exe" -B -X utf8, файлы app — установленные; PYTHONHASHSEED=0, MPLBACKEND=Agg. Сценарий: results\wave21_eh\scripts\priemka.py "C:\Program Files\ThermoGar" <случай>; выходы — results\wave21_yu\priemka\.
(а) version — подпись боковой панели «ThermoGar 0.5.0 — исследовательское ПО. Экспериментальная квалификация не проводилась.», APP_VERSION 0.5.0;
(б) batch — в runner 3 строки; CSV долей фаз — блобы results/wave19_a/posle/1g_batch_Fe-{пусто,метастабильный,стабильный}.csv; четвёртая строка — «ошибка» с текстом «Неизвестный режим стали: «metastabe». Используйте «стабильный» или «метастабильный».»;
(в) phase_reference — CSV трёх баз = блобы results/wave21_eh/spravochnik_faz/phase_reference_{ni,al,fe}.csv (99 / 195 / 132 строки);
(г) density — RS320, 25 °C: СВЕРИТЬ 2663,72 кг/м³;
(д) quick_start — первое упоминание версии в установленном QUICK_START_THERMOGAR.md — 0.5.0;
(е) pool — скан Fe 500–900 °C, 5 точек, с пулом и без: «Параллельный расчёт: …» без отказа и «Последовательный расчёт.»; таблицы и CSV равны.
Побайтовая сверка (б) и (в) — интерпретатором дерева: python -B -X utf8 results\wave21_eh\scripts\priemka_compare.py v0.5.0 — «равных: 6 из 6».
(ж) ярлыки — PowerShell, WScript.Shell, только чтение (CreateShortcut без Save): C:\Users\Public\Desktop\ThermoGar.lnk и C:\ProgramData\Microsoft\Windows\Start Menu\Programs\ThermoGar\ThermoGar.lnk — оба есть; TargetPath «C:\Program Files\ThermoGar\runtime\pythonw.exe», Arguments «"C:\Program Files\ThermoGar\launcher.pyw"»; TargetPath, Arguments, IconLocation, Description у двух ярлыков одинаковые.
Любой из (а)–(ж) не сошёлся — СТОП. После приёмки папки C:\Program Files\ThermoGar\app\__pycache__ нет (есть — в отчёт).

ШАГ 12. На main после тега (тег остаётся на коммите слияния). tasks\REGISTER.md — тексты мастера дословно, <…> заполнить:
а) В таблицу волны 21 после строки 21-Э:
| 21-Ю | `WAVE21_YU_OPUS.md` | `ThermoGar-w21b` / `wave21-yu` → `main` | выпуск 0.5.0: слияния 21-Щ и 21-Э; BL-78; пересъёмка кадров «Проектов», HTML; CHANGELOG, HANDOFF, NOTICES; реестр; регрессия, сверка эталона; слияние, тег, установщик, установка поверх 0.4.4, приёмка, ярлык | **сдано, мастер не смотрел.** <итог числами>. Отчёт `tasks/WAVE21_YU_REPORT.md` |
б) После таблицы волны 21, отдельным абзацем перед «Решения владельца по дизайну. 24.09.2026: …»:
**Выпуск 0.5.0 — <дата выпуска>, тег `v0.5.0`.** Выделения: шаг по времени KWN растёт не больше чем вдвое (BL-43); сталь: выдержка по умолчанию 0,01 ч, окно T₀ 200–950 °C и состав в каждой строке (BL-66), текст остановки (3В, вариант А); новые умолчания пяти экранов; экран по правилам дизайна — палитра, графики, тексты, символы элементов, сообщения об ошибках с кодом ошибки (волна 21); BL-63, BL-65, BL-67–BL-78; ярлык на рабочем столе (BL-62), пример версии в `build_installer.ps1` (BL-61); руководство переснято — 56 кадров. Коммит слияния `<полный хеш>`; установщик `ThermoGar-0.5.0-win64.exe`, sha256 `<SHA256>`. Раздел `CHANGELOG.md`, 0.5.0.
Отчёт tasks\WAVE21_YU_REPORT.md: итог одной строкой; время по шагам; шаги 0–11 с числами; ШАГ 3 — файл:строка, тесты до и после; ШАГ 4 — кадры и что на них; регрессия — числа и список выходов 5; таблица приёмки (а)–(ж): проверка | ожидание | получено | итог; отступления — отдельными пунктами с причиной. Коммит на main; git push origin HEAD:refs/heads/main; git ls-remote origin refs/heads/main "refs/tags/v0.5.0*", git log --oneline 062b975..HEAD и git status --short — дословно в отчёт (вывод после пуша — следующим коммитом).
