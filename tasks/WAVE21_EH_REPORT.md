# Отчёт 21-Э: к выпуску 0.5.0 — ярлык на рабочем столе, BL-61, CHANGELOG 0.5.0, сценарии выпуска

Задание — `tasks/WAVE21_EH_OPUS.md`. Дерево `D:\Pets\ThermoGar-w21a`, ветка `wave21-eh` от `e27c36c`, 27.09.2026. Лёгкий поток.

Интерпретатор — `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe`, все прогоны с `PYTHONHASHSEED=0`, `MPLBACKEND=Agg`, `PYTHONDONTWRITEBYTECODE=1`, `python -B`, `THERMOGAR_STATE_ROOT` во временной папке. Приложение, `streamlit run`, браузер, `packaging\build_installer.ps1`, makensis, установщик, `tools\make_guide_screens.py`, `tools\tab_snapshot.py` и полная регрессия не запускались. AppTest работал только внутри случая `version` сценария `priemka.py` (ШАГ 5 его разрешает).

Не менялись: `app\`, `docs\`, `databases\`, `configs\`, `tools\make_guide_screens.py`, `tasks\REGISTER.md`, `results\wave19_d\`. Байты баз не менялись. Удалённых файлов нет, в `_to_delete` ничего не переносилось. `D:\Pets\Lilith`, `D:\Pets\ThermoGar` (кроме интерпретатора) и `D:\Pets\ThermoGar-w21b` не открывались. Поиск шёл только внутри `D:\Pets\ThermoGar-w21a`.

## ШАГ 0

- `git status --short` — только `?? _to_delete/`.
- `git fetch origin` прошёл целиком.
- `git cat-file -e e27c36c7954c97d0f284346d79c8838c7cc5272c` — коммит есть.
- `git switch --detach e27c36c…`; `git switch -c wave21-eh`.
- `git ls-remote origin main` в начале работы:
  `e27c36c7954c97d0f284346d79c8838c7cc5272c	refs/heads/main`.
- Первый коммит — задание без строки «/caveman ultra» (`6863939`).

Номера строк мастера на `e27c36c` сверены: `ThermoGar.nsi:54, :99, :130–132, :154, :162`, `README.md:103–104`, `QUICK_START_THERMOGAR.md:11`, `build_installer.ps1:14`, `HANDOFF.md:83`, `priemka.py:55, :291`, `run_regress.py:80–82`, `app\thermogar_parallel_ui.py:219`, `tools\backend_reference.md:238`. Текст «было» везде совпал дословно.

## ШАГ 1. BL-62 — ярлык на рабочем столе

`packaging\ThermoGar.nsi` (CRLF сохранён):
- `:55` — новая строка `!define DESKTOP_LNK "$DESKTOP\ThermoGar.lnk"` после `!define SHORTCUT_LNK` (`:54`).
- `:134–136` — после `CreateShortcut "${SHORTCUT_LNK}" …` (`:131–133`):
  ```
    CreateShortcut "${DESKTOP_LNK}" \
      "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\launcher.pyw"' \
      "$INSTDIR\ThermoGar.ico" 0 SW_SHOWNORMAL "" "${PRODUCT_DESCRIPTION}"
  ```
  Цель, аргумент, значок, режим окна и описание — те же, что у ярлыка в меню «Пуск».
- `:167` — `Delete "${DESKTOP_LNK}"` после `Delete "${SHORTCUT_LNK}"` (`:166`).
- `SetShellVarContext all` на прежних местах (`:100`, `:157`), в обоих разделах раньше работы с ярлыками.

`README.md:103–104`:
- было: «…Запуск — ярлык **ThermoGar** в меню\n«Пуск». Пользовательские данные…»;
- стало: «…Запуск — ярлык **ThermoGar** на рабочем\nстоле или в меню «Пуск». Пользовательские данные…».

Строки `:101–102` не менялись.

`QUICK_START_THERMOGAR.md:11`:
- было: «Из установленной программы — ярлык **ThermoGar** в меню «Пуск».»;
- стало: «Из установленной программы — ярлык **ThermoGar** на рабочем столе или в меню «Пуск».».

Новый `tools\test_installer_shortcut_bl62.py` (104 строки) разбирает текст .nsi и ничего не собирает. В нём 4 теста, с параметром — 5 прогонов:
- `test_desktop_lnk_defined_on_desktop` — `DESKTOP_LNK` = `$DESKTOP\ThermoGar.lnk`;
- `test_desktop_shortcut_same_as_start_menu` — в разделе «ThermoGar» аргументы `CreateShortcut "${DESKTOP_LNK}"` равны аргументам `"${SHORTCUT_LNK}"`. Продолжения строк `\` склеиваются;
- `test_uninstall_deletes_desktop_shortcut` — в разделе «Uninstall» есть `Delete "${SHORTCUT_LNK}"` и `Delete "${DESKTOP_LNK}"`;
- `test_shell_var_context_all_before_shortcuts[ThermoGar|Uninstall]` — `SetShellVarContext all` стоит раньше первой строки с `_LNK}` или `SHORTCUT_DIR}`.

Прогоны:
- **До правки** (дерево `e27c36c` + новый тест): `3 failed, 2 passed in 0.13s`. Упали `test_desktop_lnk_defined_on_desktop`, `test_desktop_shortcut_same_as_start_menu` и `test_uninstall_deletes_desktop_shortcut`. Оба теста `SetShellVarContext` прошли: в .nsi это уже было.
- **После правки**: `5 passed in 0.05s` (`results/wave21_eh/holostoy/bl62_posle.txt`).

Коммит `be13501`.

## ШАГ 2. BL-61 и пример в HANDOFF

- `packaging\build_installer.ps1:14` (CRLF сохранён):
  - было: `  .\packaging\build_installer.ps1 -Version 0.4.3 -KeepStage`;
  - стало: `  .\packaging\build_installer.ps1 -Version 0.5.0 -KeepStage`.
- `tools\test_version_consistency.py:128–137` — новый тест `test_build_installer_example_version`. Регулярное выражение `-Version (\d+\.\d+\.\d+)`: первое совпадение в `build_installer.ps1` должно равняться `APP_VERSION`. Строка `#requires -Version 5.1` (`:1`) не совпадает: в ней два числа, а не три.
- `HANDOFF.md:83`:
  - было: «`dist\ThermoGar-0.4.3-win64.exe` и `dist\ThermoGar-0.4.3-win64.build.json`»;
  - стало: «`dist\ThermoGar-0.5.0-win64.exe` и `dist\ThermoGar-0.5.0-win64.build.json`».

  Остальной текст строки не менялся.

Прогоны `tools\test_version_consistency.py`:

| Когда | Итог |
|---|---|
| До ШАГА 2, без нового теста | `92 passed in 0.35s` |
| Новый тест, `-Version 0.4.3` | `1 failed, 92 passed in 0.37s` — `build_installer.ps1: -Version 0.4.3, APP_VERSION 0.4.4` |
| После ШАГА 2 | `1 failed, 92 passed in 0.39s` — `AssertionError: build_installer.ps1: -Version 0.5.0, APP_VERSION 0.4.4` |

Красный после правки ожидаем: на этой ветке `APP_VERSION` ещё 0.4.4. Остальные 92 зелёные. Вывод — `results/wave21_eh/holostoy/version_posle.txt`. Коммит `2cc09b0`.

## ШАГ 3. CHANGELOG 0.5.0

`CHANGELOG.md:3–58` — новый раздел над «## 0.4.4 — 2026-09-23» (теперь `:60`). Разделы:
- `:3` — `## 0.5.0 — <дата выпуска>`;
- `:7` — «Что меняет числа результата — пересчитайте»;
- `:19` — «Новое поведение экрана»;
- `:35` — «Вид»;
- `:41` — «Исправления»;
- `:53` — «Установка, проекты и документы».

Копия раздела — `results/wave21_eh/changelog_0.5.0.md`. Правки мастера к черновику `results/wave21_f/changelog_0.5.0.md`:

1. Убраны 24 ссылки на строки описи 21-Ф, каждая вместе с пробелом или «; » перед ней: ` (100, 101, 102)`, ` (105)`, ` (107, 108)`, `; (87, 88)`, `; (90)`, `; (91)`, `; (92)`, ` (93)`, ` (9)`, ` (36, 37, 48, 60–65)`, ` (49)`, ` (82)`, ` (83, 84)`, ` (85, 86)`, ` (73–76, 78)`, ` (33)`, ` (109–113)`, ` (45, 54–57)`, ` (106)`, ` (89)`, ` (46, 47)`, ` (14–21, 69, 70, 77, 96)`, ` (10–12, 22–32, 34)`, ` (38–44, 50–53, 58, 59, 66, 94, 95)`. Скобок только из номеров не осталось. Прочие скобки не тронуты: «(BL-43 / 22-Б)», «(было 400–1200 °C …)», «(600, 800 … 1600 …)» и другие.
2. Первый пункт: «; раньше он вырастал в 5–42 раза, …» заменено на «; раньше до остановки предел по критическому радиусу периодически отпускал его в 5–17 раз, а на шаге остановки шаг вырастал в 6–42 раза, …».
3. Пункт «Остановка расчёта выделений: текст» заменён целиком, текст — по заданию.
4. «### После 21-У (идёт параллельно, по тексту задания, по коду не проверено)» заменено на «### Исправления». Четыре пункта — как были, за ними пять пунктов BL-73–BL-77.
5. Новый раздел «### Установка, проекты и документы» — четыре пункта.

Остальной текст черновика — дословно. Коммит `d7d3a42`.

Раздел целиком:

````markdown
<<CHANGELOG>>
````

## ШАГ 4. Сценарии выпуска

Копии `results\wave19_d\*.py` лежат в `results\wave21_eh\scripts\`. `ROOT` — корень дерева, где лежит скрипт (`Path(__file__).resolve().parents[3]`). Каталог вывода — одна переменная `RELEASE_OUT = ROOT / "results" / "wave21_yu"` в начале каждого скрипта. В `priemka.py` корень приложения — первый аргумент, поэтому там `RELEASE_OUT` берётся от места скрипта.

**а) `run_regress.py`:**
- `SLOW_FILES` (`:98–101`) — добавлен `"test_wave21_o.py"`. В нём 2 теста `@pytest.mark.slow` (`tools/test_wave21_o.py:262, :285`);
- вывод — `RELEASE_OUT`: `regress_logs`, `regress_memlog`, `regress_backend`, `regress_summary.jsonl`;
- `THERMOGAR_STATE_ROOT` = `results/validation/wave21_yu_state`.

Число заданий по дереву — по `git ls-tree`, тем же отбором, что глоб раннера:

| Дерево | test_*.py | thermogar_*_test.py | slow | test_ui_f slow | сценарии | всего |
|---|---|---|---|---|---|---|
| `e27c36c` | 35 | 19 | 9 | 1 | 7 | **71** |
| `wave21-eh` (+ `test_installer_shortcut_bl62.py`) | 36 | 19 | 9 | 1 | 7 | **72** |

Оценка 21-Ф — 70, то есть на одно задание меньше, чем 71 на `e27c36c`. По подсчёту разница — это `slow__test_wave21_o.py`, добавленный в этом шаге. Файлы с `mark.slow` на `e27c36c`: 9 из `SLOW_FILES` и `test_ui_f.py`, других нет.

**б) `backend_compare.py`:**
- сверка с 17-Г, как в 19-Д;
- исходы: `RELEASE_OUT/regress_backend`, вывод: `RELEASE_OUT/backend_compare.txt`. Оба пути можно задать аргументами — так сделан холостой прогон;
- новый вердикт:
  - «PASS» — разница ровно в одной ячейке `[Кинетика] KWN (модуль) | fe`, и в ней `строк кинетики` = 1123. Ключ взят из отчёта `test_backend_calculations`;
  - иначе «FAIL» со списком ячеек.
- `tools/backend_reference.md:238` — «**PASS**, 1123 строки кинетики (22-Б; было 2391)». Коммит `c1577ca` есть.

**в) `priemka.py`:**
- `VERSION` (`:68`, было `:55`) = `"0.5.0"`;
- (е) `case_pool` (`:304`, было `:291`): `plain["note"] == "Последовательный расчёт."`. Это совпадает с `app\thermogar_parallel_ui.py:219`: `return "Последовательный расчёт."`;
- (а), (б), (г), (д) — как было;
- строка документа: «Приёмка 0.5.0 на установленном рантайме», прежняя шапка 19-Д сохранена ниже;
- третий аргумент (каталог вывода) стал необязательным, по умолчанию `RELEASE_OUT/priemka`;
- префикс временной папки состояния — `w21yu_state_`.

**г) Справочник фаз:**
- `results\wave21_eh\spravochnik_faz\phase_reference_{ni,al,fe}.csv` сняты `case_phase_reference` этого `priemka.py` на дереве `wave21-eh` (корень `D:\Pets\ThermoGar-w21a`). Вывод прогона — `spravochnik_faz/snyatie.json`;
- строк: ni 99, al 195, fe 132;
- sha256:
  - ni `de583b08d18878467e735324a23bfbde61087060d08f4c75cafc52b46ad99661`;
  - al `84a5be1dd27eadb2220a10969686d1a46fcb20702f3fe8ef15d846378b1115f1`;
  - fe `a7b63398d03a96c10de2f03dac16841a410cdd9c2a4d5c6fbc79108983332eb6`;
- со старыми CSV 19-В2 (`v0.4.4:results/wave19_v2/posle/`) расходится по одной строке на базу: ni `BCC_B2`, al `GP_MAT`, fe `BCC_B2`. Разница только в «Связанная order/disorder-модель» против «Связанная модель порядок/беспорядок» (21-Ж);
- `priemka_compare.py`:
  - (в) — с этими CSV;
  - (б) — как было;
  - ревизия по умолчанию — `wave21-eh`;
  - выходы приёмки — `RELEASE_OUT/priemka`.

Коммит `3a3b0f4`.

## ШАГ 5. Прогоны

**`tools\test_installer_shortcut_bl62.py`:**
- на `e27c36c` красный: `3 failed, 2 passed`;
- после ШАГА 1 зелёный: `5 passed`.

Подробности — ШАГ 1.

**`tools\test_version_consistency.py`:**
- до ШАГА 2: `92 passed`;
- после ШАГА 2: `1 failed, 92 passed`. Упал новый тест: 0.5.0 против `APP_VERSION` 0.4.4, это ожидаемо. Остальные 92 зелёные.

**`backend_compare.py`, холостой прогон на исходах 19-Д.** Команда: `python -B -X utf8 results/wave21_eh/scripts/backend_compare.py results/wave19_d/regress_backend results/wave21_eh/holostoy/backend_compare.txt`. Вывод:

```
исходы 0.5.0: D:\Pets\ThermoGar-w21a\results\wave19_d\regress_backend
ячеек: 17-Г 57, 0.5.0 57
статусы 0.5.0: ["status = 'PASS'"]
ячеек с разницей: 0

[Кинетика] KWN (модуль) | fe: строк кинетики = 2391 (ожидается 1123, 22-Б)
ВЕРДИКТ: FAIL
  [Кинетика] KWN (модуль) | fe (строк кинетики 2391, нужно 1123)
```

Как ожидалось: «ячеек с разницей: 0» и «FAIL» по ячейке KWN fe (2391). Подпись «0.5.0» в выводе — имя второй стороны сверки; здесь на её месте исходы 19-Д.

**`priemka.py`** на дереве `wave21-eh`, корень `D:\Pets\ThermoGar-w21a`, вывод — `results/wave21_eh/holostoy/priemka/`.

Случай `version` (12,1 с):
```
{"app_version": "0.4.4", "sidebar": ["ThermoGar 0.4.4 — исследовательское ПО. Экспериментальная квалификация не проводилась."], "ok": false, "case_seconds": 12.1}
```
`"ok": false` ожидаем: `APP_VERSION` ещё 0.4.4.

Случай `phase_reference` (20,6 с): ni 99 строк, al 195, fe 132. sha256 те же, что в ШАГЕ 4г. `cmp` с `results/wave21_eh/spravochnik_faz/phase_reference_{ni,al,fe}.csv` — **все три совпали байт в байт**.

## Отступления

1. **`backend_compare.py`: времена отброшены.** Ключи «с/точку» и «всего, с» ячеек «Проекты/batch» при сличении не учитываются. Причина: в копии 19-Д времена сличались, хотя шапка говорит «без времён». Тогда холостой прогон на исходах 19-Д дал бы 3 ячейки с разницей (`results/wave19_d/backend_compare.txt`), а не ожидаемые 0.
2. **Пути вывода можно задать аргументами.**
   - `backend_compare.py` принимает каталог исходов и файл вывода.
   - `priemka.py` принимает каталог вывода: как в 19-Д, но теперь необязательно.

   Без аргументов пути идут от `RELEASE_OUT` (`results/wave21_yu/`). Причина: холостые прогоны 21-Э не должны писать в `results\wave21_yu\` — его в списке разрешённого нет.
3. **`run_regress.py`: интерпретатор.** Берётся `ROOT\.venv-windows\Scripts\python.exe`, а если его в дереве нет — тот, что запустил раннер. Причина: в `D:\Pets\ThermoGar-w21a` нет `.venv-windows`, и раннер 19-Д в этом дереве не нашёл бы Python. Папка состояния — `results/validation/wave21_yu_state` вместо `wave19_d_state`.
4. **Число заданий — 71, оценка 21-Ф — 70.** Разница — `slow__test_wave21_o.py`, добавленный в ШАГЕ 4а. С `test_installer_shortcut_bl62.py` этой ветки — 72.
5. **CHANGELOG, подпункты умолчаний.** Ссылки `; (87, 88)`, `; (90)`, `; (91)`, `; (92)` убраны вместе с «; », как велит правка 1. Поэтому четыре подпункта «Новых умолчаний пяти экранов» теперь кончаются без «;».
6. **Лишние файлы в `results\wave21_eh\`.** Три группы:
   - `changelog_0.5.0.md` — копия раздела;
   - `spravochnik_faz/snyatie.json` — вывод снятия эталона;
   - `holostoy/` — выводы прогонов ШАГА 5 и тестов.
7. **Снятие эталона ШАГА 4г — отдельный прогон** `priemka.py phase_reference` с выводом в папку сессии, вне дерева. Этого требует ШАГ 4г; ШАГ 5 потом повторил тот же случай и сверил байты.
8. **Не сделано, на решение мастера:** комментарий `packaging\ThermoGar.nsi:5` («drops one Start Menu shortcut») после BL-62 неточен. Строку не менял: в списке правок ШАГА 1 её нет.
9. `README.md:104` после правки длиннее соседних строк: текст «было → стало» дан дословно, строки не переносил.

## Git

<<GIT>>
