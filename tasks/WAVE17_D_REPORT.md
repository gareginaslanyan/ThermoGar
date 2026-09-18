**Итог: всё по заданию сделано, красного нет.** Четыре файла тестов зелёные: `29 passed`, `3 passed`, `6 passed`, `11 passed`. Установщик 0.4.2 собран, sha256 `DF08800828B32F86CE1CD17BDA8EE1EC3B39A925F65520EB0B6993F09913D8EF`. Смоук нагрузки — `PAYLOAD SMOKE OK`, смоук установленной копии — `OVERALL: PASS`, 8/8. Деинсталлятор каталогов не оставляет. На установленной 0.4.2 сплав 718 с шестью добавками даёт результат с остановкой BL-35, на 0.4.1 — отказ по пределу четырёх добавок. В `main` не вливалось, тег не ставился, ничего не пушилось.

# Отчёт 17-Д — выпуск 0.4.2, часть 2

Задание — `tasks/WAVE17_D_OPUS.md`. Дерево `D:\Pets\ThermoGar`, ветка `wave15-release`, начало работы — `fc08084`
(HEAD после 17-Г). Интерпретатор — `.venv-windows`, Python 3.11.9. Результаты — `results/wave17_d/`.
`app/` и `databases/` не менялись.

---

## 0. Проверка среды

Сессия запущена из обычного терминала: `CLAUDE_CODE_ENTRYPOINT=cli`, а в 17-Г было `claude-desktop`.
`GetFinalPathNameByHandle` вернул для `%LOCALAPPDATA%` и для пробного каталога в нём неперенаправленные пути
(`results/wave17_d/localappdata_probe.json`):

```
"LOCALAPPDATA": "\\\\?\\C:\\Users\\gareg\\AppData\\Local",
"probe_dir": "\\\\?\\C:\\Users\\gareg\\AppData\\Local\\ThermoGar_probe17d",
"ThermoGar": "err 6"
```

`err 6` значит, что настоящего `%LOCALAPPDATA%\ThermoGar` на момент проверки не было. Прежний каталог жил в
`LocalCache` контейнера. Путь не ведёт в `…\Packages\Claude_…\LocalCache`, поэтому остановки нет. Пробный
каталог удалён сразу после проверки.

## Где посылка задания разошлась с найденным

Остановок не было. Ниже расхождения и отступления, каждое с причиной.

1. **17Д-1. Среды для сборки после переустановки не было.** Не хватало NSIS (`makensis.exe`), `runtime-clean-3119`
   в рабочем дереве, `playwright` и `markdown` в `.venv-windows`. Что сделано:
   * NSIS 3.12 поставлен через `winget install NSIS.NSIS --version 3.12` с разрешения владельца, которое он дал в
     сессии. 0.4.1 собиралась той же версией: `MakeNSIS v3.12` в `makensis.log` архива.
   * Runtime взят из архива `D:\Pets\ThermoGar_arhiv_2026-09-17\ThermoGar-Installer-Assets\runtime-clean-3119`
     ключом `-RuntimeSource`. Архив не менялся.
   * `playwright==1.62.0` — та же версия, что в архивном venv; Chromium поставлен через `playwright install chromium`.
   * `markdown==3.10.3` — в архивном venv его не было, версию сверить не с чем. В requirements проекта ни
     `playwright`, ни `markdown` не записаны.
2. **17Д-2. При поиске NSIS нарушен запрет «в `D:\Pets\Lilith` не заходить».** Рекурсивный
   `Get-ChildItem D:\ -Recurse -Depth 6 -Filter makensis.exe` прошёл и по этому каталогу. Путь `Lilith*` отсекался
   только в выводе, а не при обходе. Файлы оттуда не открывались и не читались. В выводе нет ни одного пути из
   Lilith. Ошибка моя: исключать каталог надо было до обхода.
3. **17Д-3. `tools/make_guide_screens.py` не менялся.** Задание не разрешает правку `tools/` кроме `test_ui_g.py`,
   а новых сценариев скрипт не знает. Поэтому съёмка идёт через обёртку `results/wave17_d/guide_screens_042.py`.
   Обёртка берёт из скрипта запуск приложения, `Shooter`, сжатие и сборку HTML. Она добавляет сценарий
   `soobshcheniya`, ставит `STATE_ROOT` = `results\validation\wave17_d_state` (путь п. 1) и дописывает
   `_manifest.json`, а не перезаписывает его. Перед каждым кадром она прокручивает боковую панель к началу, чтобы
   подпись «ThermoGar 0.4.2» была видна. HTML собран штатным `tools/make_guide_screens.py --html`.
4. **17Д-4. Кадр остановки BL-35 снят на сетке раздела по умолчанию (0,2…10 нм, 80 классов), а не на сетке 15-В
   (0,1…50 нм, 800 классов).** Ползунок «Классов размеров» в приложении ограничен 20…200. Остановка на
   снимке — 3,888 с. Для п. 6 сетка 15-В взята полностью: там 3,844 с и 212 шагов, строка в строку как у 15-Д
   (`tasks/WAVE15_D_REPORT.md`, таблица п. 5, случай 700 °C, 95).
5. **17Д-5. Пример текста в руководстве и CHANGELOG («2.011 с») — случай 78 мДж/м², а не 95.** Сначала подпись к
   снимкам в `06-kinetika.md` объясняла разницу 3,888 и 2,011 с сеткой, и это было неверно. Исправлено отдельным
   коммитом `4f956a3`: теперь подпись называет обе энергии. Сам пример не менялся: он дословно из 15-Д.
6. **17Д-6. HTML руководства в дереве был старее текстов 15-П и 15-Щ.** После пересборки в HTML впервые попали
   их абзацы (быстрый набор, пустое решение, две колонки долей). Поэтому дифф HTML больше пяти новых картинок.
7. **17Д-7. Для п. 6 0.4.2 поставлена заново после смоука.** Смоук удаляет программу шагами 7 и 8. Установка —
   `/S`, `exit 0`, в реестре удаления стоит `ThermoGar 0.4.2`. Программа оставлена установленной. Настоящий
   `%LOCALAPPDATA%\ThermoGar` создан смоуком и приложением (`cache`, `logs`, `migration_receipt.json`) и не
   тронут.
8. **17Д-8. `MPLBACKEND=Agg` в прогонах п. 1.** Как в контроле 17-Г (17Г-2), чтобы `test_parallel_integration` не
   падал на Tk.
9. **17Д-9. Реестр.** Строк 17-А, 17-Б и 17-В в `tasks/REGISTER.md` не было. Раздел «Волна 17» заведён со строками
   17-Г и 17-Д, это сказано в его шапке. Строка 17-Г записана формулировкой задания («принята…»).
10. **Вне задания, не правилось.** `HANDOFF.md:4` называет рабочим корнем несуществующий
    `C:\Users\gareg\Desktop\ThermoGar`. `docs/HN62M_STUDY.md:722` и `docs/screenshots/README.md` ссылаются на
    прежний `01-fast-preset-warning.png`. Это история исследования, файл оставлен. Копия отчёта на Рабочий стол не
    положена: дерева `Desktop\ThermoGar` нет (как 17Г-4).

---

## 1. Тест и регрессия

`tools/test_ui_g.py::test_kwn_precipitation`, коммит `22d0816`:

* **Ячейка `fe`.** Проверяется, что результат есть и что строка «Состав матрицы допустим» имеет статус `ошибка`,
  а её примечание равно `stop_note`. `stop_note` начинается с «Расчёт остановлен». Остальные восемь проверок
  пройдены. Текст `stop_note` стоит среди `st.warning`. Ошибки экрана — ровно
  `["Одна или несколько внутренних проверок не пройдены."]`. Комментарий теста ссылается на BL-43.
* **Ячейки `ni` и `al`.** Как было: ошибок нет, все проверки пройдены. Добавлено ещё `stop_note == ""`.

Прогоны шли по одному: `THERMOGAR_STATE_ROOT=D:\Pets\ThermoGar\results\validation\wave17_d_state`,
`PYTHONHASHSEED=0`, `MPLBACKEND=Agg`. Раннер — `results/wave17_d/run_tests.sh`, логи — `results/wave17_d/logs/`.
Перед стартом было свободно 7,07 ГиБ.

| файл | режим | exit | итоговая строка | ожидание |
|---|---|---:|---|---|
| `test_ui_g.py` | `-m "not slow"` | 0 | `29 passed, 3 deselected, 2 warnings in 208.62s (0:03:28)` | 29 passed |
| `test_ui_g.py` | `-m slow` | 0 | `3 passed, 29 deselected, 3 warnings in 225.72s (0:03:45)` | 3 passed |
| `test_parallel_integration.py` | все | 0 | `6 passed in 74.64s (0:01:14)` | 6 passed |
| `test_precipitation_bl35.py` | все | 0 | `11 passed, 1 warning in 33.80s` | 11 passed |

## 2–3. Реестр, RULES, документы

Коммит `ab3e16b`:

* `tasks/REGISTER.md` — строка BL-43 после BL-42 с формулировкой задания и ссылками. Раздел «Волна 17» со
  строками 17-Г и 17-Д. Подраздел «Ошибка мастера (17-Г)»: «новые с волны 14» — это файлы волны 15.
* `tasks/RULES.md`, «Память и параллельность» — правило о регрессии и смоуке только с папкой данных вне
  MSIX-контейнера.
* `docs/LIMITS_OF_APPLICABILITY.md`, раздел «Кинетика: обрыв расчёта…» — один абзац. В нём: C в феррите, BL-43,
  ячейка Fe на 40 и на 30 классах, совет «пересчитайте с другой сеткой размеров».
* `CHANGELOG.md` — заголовок «## 0.4.2 — 2026-09-18». В подразделе BL-35 — одна фраза-оговорка со ссылкой на
  BL-43.
* `HANDOFF.md:10` — «**Выпущено:** 0.4.2 от 2026-09-18; предыдущий выпуск 0.4.1 от 2026-09-14.». Строка
  «Готовится» убрана.
* `USER_GUIDE:389` не тронут.

## 4. Снимки

Сняты на живом приложении рабочего дерева. Коммиты `a6e0325` и `4f956a3`. Каждый кадр просмотрен. Подпись
«ThermoGar 0.4.2 — исследовательское ПО» видна в боковой панели на всех десяти кадрах.

| снимок | что на нём | куда вставлен (прежняя пометка) |
|---|---|---|
| `docs/guide/img/soobshcheniya-01.png` | Fe–0,2C–11,5Cr–0,7Ni, 700 °C, быстрый набор: «всего 12: ALPHA_MN, BETA_MN, FE24C10, H_BCC, KSI_CARBIDE и ещё 7» и раскрытый блок «Все фазы вне быстрого набора (12)» | `01-raschety.md:50`, `USER_GUIDE_THERMOGAR.md:115` (заменил и прежний `docs/screenshots/01-fast-preset-warning.png` в этом месте) |
| `docs/guide/img/soobshcheniya-02.png` | ЭК199 с Si 5 масс. % (состав 15-З, п. 4), 750 °C: «Равновесие при 750.0 °C не найдено: …» под кнопкой | `01-raschety.md:69`, `USER_GUIDE_THERMOGAR.md:178` |
| `docs/guide/img/soobshcheniya-03.png` | 718, 700 °C, 95 мДж/м²: «Расчёт остановлен на 3.888 с модельного времени (0.00108 ч): доля NB в матрице стала 0 ат. %…» над вкладками и «Одна или несколько внутренних проверок не пройдены.» | `06-kinetika.md:96`, `USER_GUIDE_THERMOGAR.md:307` |
| `docs/guide/img/soobshcheniya-04.png` | таблица проверок на вкладке «Итоги»: «Состав матрицы допустим — ошибка», остальные восемь пройдены | `06-kinetika.md:96`, `USER_GUIDE_THERMOGAR.md:307` |
| `docs/guide/img/soobshcheniya-05.png` | постановка 13-Ф с cMax 0,5 нм: «Радиус зародыша 1.02 нм (оценка при 800.0 °C) больше начального максимального радиуса сетки 0.5 нм…» | `06-kinetika.md:99` |
| `docs/guide/img/svoystva-04.png` | таблица модулей со столбцами «Мольная доля фаз» (0,6958 / 0,3042) и «Объёмная доля фаз» (0,682 / 0,318) | `05-svoystva.md:43` (пометка снята, абзац переписан) |
| `docs/guide/img/svoystva-05.png` | Хилл: E 212,037 ГПа, G 81,500 ГПа, ν 0,30084; Ройсс 211,1916, Фойгт 212,8814 | шаг 5 главы 05 |
| `docs/guide/img/svoystva-01…03.png` | пересняты тем же сценарием: плотность стали 7575,7 кг/м³ (как в эталоне 13-Р2, 7575,68), кнопки шагов 1 и 3 | без изменений в тексте |

Шаг 5 главы 05 был: «E = 211,5 ГПа, G = 81,3 ГПа, ν = 0,301 … около 1,6 ГПа». Стал: «**E = 212,0 ГПа,
G = 81,5 ГПа, ν = 0,301** … около **1,7 ГПа**». Шаг 4: «в этом примере `FCC_A1` 0,682 и `GAMMA_PRIME` 0,318
(мольные — 0,696 и 0,304)».

В `docs/` и в `USER_GUIDE_THERMOGAR.md` не осталось ни одной пометки «[снимок: …]». `ThermoGar_Guide_0.4.2.html`
пересобран: 6,4 МБ, 56 встроенных картинок (было 51), пометок в нём нет.

## 5. Установщик и смоук

`packaging\build_installer.ps1 -OutputDir dist\release-0.4.2 -RuntimeSource <архив>`, лог —
`results/wave17_d/build.log`:

```
BUILD OK  D:\Pets\ThermoGar\dist\release-0.4.2\ThermoGar-0.4.2-win64.exe
  payload  : 15078 files, 554,3 MB
  installer: 113,0 MB
  sha256   : DF08800828B32F86CE1CD17BDA8EE1EC3B39A925F65520EB0B6993F09913D8EF
  elapsed  : 399,2 s
```

Версия 0.4.2 (`vi_product_version` 0.4.2.0), `installer_bytes` 118511244, `payload_bytes` 581216858, NSIS
`C:\Program Files (x86)\NSIS\makensis.exe`. Сборка перевыпустила `THIRD_PARTY_NOTICES.txt`, и изменилась только
строка `Generated: 2026-09-14` → `2026-09-18` (коммит `c99eff2`).

**Смоук нагрузки во временном каталоге.** Скрипт — `results/wave17_d/payload_smoke.ps1` (копия скрипта 13-Р2),
лог — `payload_smoke.log`:

```
  staged 15078 files, 554,3 MB
  processes before: 0
  launcher pid 15380, cwd C:\Users\gareg\AppData\Local\Temp\tg-foreign-1722598878
  HEALTHY ui_port=54346 control_port=54343 after 22,5s
  GET / -> 200 (11141 bytes, Streamlit shell: True); script-health-check -> 200 'ok'
  stop exit 0 : {"schema":1,"status":"STOPPED","supervisor_pid":15380,...}
  processes after stop: 0
PAYLOAD SMOKE OK
```

**Смоук установленной копии.** `packaging\smoke_installed.ps1 -InstallerPath dist\release-0.4.2\ThermoGar-0.4.2-win64.exe`,
один запрос UAC. Лог — `results/wave17_d/smoke_installed.log`, отчёт — `results/wave17_d/smoke-20260918T084536Z.json`:

```
[PASS] step 1: silent install (23s)
        installer exit 0
[PASS] step 2: files, shortcut, registry (0s)
        missing=0 database=True shortcut=True registry=True version=0.4.2
[PASS] step 3: launcher started (3s)
        pid=5992 alive=True cwd=C:\Users\gareg\AppData\Local\Temp\thermogar-smoke-588a8ab9
[PASS] step 4: healthcheck HEALTHY (29,9s)
        after 29.9s ui_port=54423 control_port=54418 last={"schema":1,"status":"HEALTHY",...}
[PASS] step 5: UI 200, app script runs clean (1s)
        GET / -> 200 (11141 bytes, Streamlit shell: True); script-health-check -> 200 'ok'
[PASS] step 6: stop: no processes, ports free (1,6s)
        stop exit 0, remaining processes 0, ports free True, out={"schema":1,"status":"STOPPED",...}
[PASS] step 7: silent uninstall, LOCALAPPDATA kept (4,6s)
        uninstaller exit 0, leftover files 0, registry gone True, shortcut gone True, LOCALAPPDATA kept True
[PASS] step 8: upgrade over existing install, user project kept (112,1s)
        install exit 0, files True; start healthy True, stop exit 0 clean True; upgrade install exit 0, files True; restart healthy True ui_port 54630, UI and script-health-check 200 True; stop exit 0 clean True; project kept across upgrade True, identical True; uninstall exit 0 removed True, project kept True

OVERALL: PASS
```

**Деинсталлятор каталогов не оставляет.** Шаг 7 насчитал 0 оставшихся файлов. После последнего удаления в
шаге 8 `Test-Path 'C:\Program Files\ThermoGar'` вернул `False`: каталога установки нет целиком.

## 6. «До/после» на установленной копии

После смоука 0.4.2 поставлена заново (17Д-7). Файл `app\thermogar_precipitation.py` установленной копии совпал с
веткой по SHA-256 (`717486b5e7394a58…`). Скрипт — `results/wave17_d/demo_718.py`. Он запускается
интерпретатором установленной программы `C:\Program Files\ThermoGar\runtime\python.exe` и зовёт штатный
`run_precipitation` из `app\` проверяемой копии, с её базой `mc_ni`.

Входы — `study_wave15_v_718.case_arguments(700.0, 95.0, GRID)`, записанные в `demo_718_inputs.json` скриптом
`make_demo_inputs.py`: у 0.4.1 этого модуля нет, поэтому обе копии читают одни и те же входы из файла. Входы:
сетка 0,1…50 нм, 800 классов, горизонт 100 ч, Vm 7,1456 и 7,3 см³/моль, N0 8,4277·10²⁸ м⁻³.

**0.4.2, установленная копия** — `results/wave17_d/demo/installed_042.txt`, без строк предупреждений
streamlit и kawin о `ScriptRunContext` и `divide by zero`:

```
python      : C:\Program Files\ThermoGar\runtime\python.exe
app         : C:\Program Files\ThermoGar\app\thermogar_precipitation.py
APP_VERSION : 0.4.2
состав      : основа FE, NI=54.2, CR=17.9, NB=5.3, MO=2.99, TI=0.97, AL=0.5 (wt)
пара        : FCC_A1 / GAMMA_DP, 700 °C, γ = 0.095 Дж/м²
ИСХОД       : РЕЗУЛЬТАТ за 30.5 с
строк кинетики: 212; последнее время: 3.84371 с
«Состав матрицы допустим»: ошибка
stop_note   : Расчёт остановлен на 3.844 с модельного времени (0.001068 ч): доля NB в матрице стала 0 ат. %, баланс масс нарушен. Показана часть расчёта до остановки. Причина: при движущей силе по базе зарождение практически безбарьерное, и выделение вычерпывает добавки из матрицы быстрее, чем модель это выдерживает; см. docs/LIMITS_OF_APPLICABILITY.md.
warning     : Подвижность ниобия в FCC_A1: в базе записано LN(1,00E-4) с десятичной запятой, ThermoGar читает это как ln(1.00E-4). Правка сделана поверх разобранной базы, байты файла не менялись; число взято из той же строки, первоисточник строки (pov10) не опубликован и не сверен.
warning     : В составе 6 добавок. Расчёт идёт в этой же вкладке и не отменяется; каждая добавка удлиняет его примерно на 15 %.
```

**0.4.1** — тот же скрипт и тот же интерпретатор на снимке `git archive v0.4.1 app databases` во временном
каталоге сессии. Вывод — `results/wave17_d/demo/v041.txt`, дословно:

```
python      : C:\Program Files\ThermoGar\runtime\python.exe
app         : C:\Users\gareg\AppData\Local\Temp\claude\C--Users-gareg\359bac8b-443b-4edf-90c9-102f8ee3514b\scratchpad\v041_snapshot\app\thermogar_precipitation.py
APP_VERSION : 0.4.1
состав      : основа FE, NI=54.2, CR=17.9, NB=5.3, MO=2.99, TI=0.97, AL=0.5 (wt)
пара        : FCC_A1 / GAMMA_DP, 700 °C, γ = 0.095 Дж/м²
ИСХОД       : ОТКАЗ за 5.5 с
исключение  : ValueError: Research KWN mode допускает не более четырёх добавок одновременно.
```

Число шагов и время остановки 0.4.2 (212 и 3,844 с) совпали с 15-Д для случая 700 °C, 95.

---

## Git

`git log --oneline -8` перед коммитом этого отчёта, дословно:

```
4f956a3 docs(17-Д): подпись к снимкам остановки — пример 78 мДж/м², снимки 95 мДж/м²
c99eff2 release(17-Д): перевыпуск THIRD_PARTY_NOTICES сборкой 0.4.2
a6e0325 docs(17-Д): снимки 0.4.2 вместо пометок 15-П/15-Щ, шаг 5 главы 05 по новому расчёту, HTML руководства
ab3e16b docs(17-Д): BL-43 в реестре, LIMITS и CHANGELOG; 0.4.2 от 2026-09-18; правило о папке данных вне контейнера
22d0816 test(17-Д): test_kwn_precipitation[fe] — ожидание по BL-35, ссылка на BL-43
fc08084 test(17-Г): регрессия 0.4.2 на d3f3d1c
d3f3d1c chore(17-В): зависимости стенда тестов (pytest-timeout), правило в RULES
adeed14 restore(17-Б): волны 14–16 из рабочего дерева ThermoGar-w15e (ed8f989), история коммитов утрачена при переустановке
```

`git status --short` перед коммитом этого отчёта, дословно:

```
?? "Claude outputs/"
?? PEREDACHA_MASTERA.md
?? PRAVILA_VZAIMODEYSTVIYA_VLADELEC_MASTER.md
?? results/wave17_b/
?? results/wave17_d/
?? tasks/WAVE17_A_REPORT.md
?? tasks/WAVE17_B_REPORT.md
?? tasks/WAVE17_D_OPUS.md
?? tasks/WAVE17_V_REPORT.md
?? tasks/lilith_16A/
```

Ни одного `M`. Последним коммитом идут `results/wave17_d/`, `tasks/WAVE17_D_OPUS.md` и этот отчёт. `dist/` закрыт
`.gitignore`. Ветка не пушилась, в `main` не вливалась, тег не ставился.
