# 20-Д — отчёт: BL-57, шаг 2 разреза — тексты и умолчания головного сценария в `app/thermogar_app_texts.py`, сверка с эталоном 0.5.0, регрессия

**Итог.** 20-Г влита в `main`: коммит `b719976`, дерево `702a770` сошлось. 23 константы перенесены дословно (`34fd3f1`): строки, sha256, блобы и AST обоих файлов сошлись с замером мастера, значения 23 из 23 равны. Сверка вкладок с эталоном 0.5.0: 130 из 130 случаев чистые; 4036 файлов, 3573 равны, 463 равны с 14 исключениями, различий 0 — полное равенство. Регрессия: 78 заданий, 69 выход 0, 9 выход 5 (список 20-Г); эталон расчётов PASS. СТОПов не было.

## Время по шагам

| Шаг | Начало | Конец | Что |
|---|---|---|---|
| 0 | 20:43:32 | ≈20:43:55 | `git status`, fetch, ссылки, эталон, память |
| 1 | 20:43:57 | 20:44:33 | слияние, пуш в `main`, ветка `wave20-d`, `WAVE20_D_OPUS.md` (`b672102`), `.gitignore` (`ef7458a`) |
| 2 | 20:44:39 | 20:46:07 | перенос, проверки, коммит `34fd3f1` |
| 3 | 20:46:32 | 20:56:09 | три строки в тестах, прогон 9 файлов (20:46:32–20:55:56), коммит `5ea5638` |
| 4 | 20:56:18 | 21:51:50 | снимок (20:56:18–21:50:37), сводка, суммы, сверка (21:51:31–21:51:36), коммит `ef18553` |
| 5 | 21:52:05 | 23:42:14 | регрессия (21:52:05–23:41:33), сверка эталона расчётов, коммит `4789da9` |
| 6 | ≈21:05 | 23:42:31 | реестр: (а), (в), (г) — во время снимка, (б) — после регрессии; коммит `883a156` |
| 7 | 23:43 | см. раздел git | отчёт, пуш |

Все даты — 28.09.2026, время местное (UTC+3).

## Шаг 0

* `git status --short` на входе — одна строка `?? _to_delete/`. Папки `Claude outputs/` не было, переносить нечего.
* `git ls-remote origin main wave20-g`: `main` — `4e905b3771fea1cc1386a7b1ef7936626708e835`, `wave20-g` — `af69796956b59e6989bb1848048c760544dc38b0`. Сошлось.
* Эталон `results\validation\wave20_v\run1` — 130 каталогов случаев.
* Свободная память на входе — 8,65 ГиБ из 15,71 (перед ШАГОМ 4 — 8,65 ГиБ, перед ШАГОМ 5 — 8,57 ГиБ). Диск D: — свободно 494 ГиБ.

## Шаг 1. Слияние 20-Г и `.gitignore`

* `git switch --detach origin/main` (`4e905b3`), `git merge --no-ff origin/wave20-g -m "Merge wave20-g: удаление неиспользуемого кода ThermoGar_app.py (20-Г)"`.
* Коммит слияния — `b71997640a3a445be631d0d0b46f54a9e2e0a8a7`, родители `4e905b3` и `af69796`, дерево — `702a77059ef845b13ad23d2ecf2670cb6739a619`. Совпало с заданием.
* `git push origin HEAD:refs/heads/main` — `4e905b3..b719976  HEAD -> main`; `git ls-remote origin main` после пуша — `b71997640a3a445be631d0d0b46f54a9e2e0a8a7`.
* `git switch -c wave20-d`. Задание без первой строки «/caveman ultra» — `tasks/WAVE20_D_OPUS.md`, 102 строки, LF; коммит `b672102`.
* `.gitignore` — в конец две строки задания; коммит `ef7458a`. `git check-ignore -v "Claude outputs/x"` — `.gitignore:18:Claude outputs/	Claude outputs/x`, код 0: правило найдено.

## Шаг 2. Перенос

До правки: блоб `f52095b7a5b4954df85e57098e858acfc85bab68`, 12 818 строк, CR 0. Совпало с заданием.

Скрипт переноса перед записью сверил границы по тексту: первая и последняя строка каждого из 15 блоков; `:564` `CONCENTRATION_SCAN_DEFAULTS`, `:572` `ISOPLETH_DEFAULTS`, `:1327` и `:1346` — первая и последняя константы блока 12, `:1352` — комментарий BL-38, `:1354–1356` — `ELASTIC_*`; `:385`/`:391`/`:395` — `FE_PROFILE_RELATIVE_PATHS`, `FE_PROFILE_SHA256` и их конец остаются; `:273` — `)`, `:180` — `    PHYSICAL_OVERRIDES_ENV,`. Все удаляемые строки вне блоков — пустые. Новый модуль собран склейкой шапки и блоков через две пустые строки. Правки головного сценария — снизу вверх, затем вставка импорта после `:273` и удаление `:180`.

После правки (всё совпало с замером мастера):

* `app/ThermoGar_app.py` — 12 208 строк, sha256 `1bc0e905bd101966b90c1a9857cb218649e41549e3fd9555d0fa4baa25427cc0`, после `git add` — блоб `35b309b1da7cf6ece7a9ddf6fabde722fb16fc77`;
* `app/thermogar_app_texts.py` — 644 строки, sha256 `567930ef5ae67b07b985d2dc62dd6ade57f88f6014fbfa0d835f7ce7888c1a99`, блоб `cc8864e743c134afef9479bad4ab13b7c096a8b7`;
* AST нового модуля: 25 узлов верхнего уровня — строка документации, `from thermogar_physical import PHYSICAL_OVERRIDES_ENV` и 23 присваивания. Все 23 равны узлам файла до правки по `ast.dump` и по `ast.get_source_segment`, порядок тот же;
* значения: 23 константы, выполненные из нового модуля (`import thermogar_app_texts`), равны значениям прежних узлов, выполненных с тем же `PHYSICAL_OVERRIDES_ENV`; типы те же. 23 из 23;
* AST головного сценария: 306 узлов до правки, 284 после. Без 23 перенесённых — 283 прежних узла, в том же порядке; по `ast.dump` отличается только импорт `thermogar_physical` (без `PHYSICAL_OVERRIDES_ENV`). Добавлен один импорт `from thermogar_app_texts import (…)` — 21 имя. `PHYSICAL_OVERRIDES_ENV`, `ELASTIC_MOLE_FRACTION_LABEL`, `ELASTIC_VOLUME_FRACTION_LABEL` в головном сценарии не используются;
* `git diff --cached --stat` — `app/ThermoGar_app.py | 656 ++-----`, `app/thermogar_app_texts.py | 644 +++++`; 667 вставок, 633 удаления.

Коммит `34fd3f1`.

## Шаг 3. Тесты

Три строки — по заданию, остальное не менялось. Блобы после `git add` совпали с заданием:

* `tools/test_wave21_m.py` — `b3e8dc7f8380dd3360321851c5b862a298a95103` (`:265`);
* `tools/test_wave21_ts.py` — `1bf33882be0d1419ee84f56d0f9ba78f6cbf7ef2` (`:69`, только `_user_guide_md`);
* `tools/test_version_consistency.py` — `3c8cd5f66df03377ba38741c59645bac743eff0f` (`:95`, 77 → 78).

Прогоны (каждый файл целиком, без отбора по `slow`; `-q -p no:cacheprovider`) — все зелёные:

| Файл | Итог |
|---|---|
| `test_wave21_m.py` | 22 passed |
| `test_wave21_ts.py` | 9 passed |
| `test_version_consistency.py` | 94 passed |
| `test_phase_description_order_words.py` | 11 passed |
| `test_phase_description_stub_keys.py` | 9 passed |
| `test_equilibrium_solidus_fallback.py` | 19 passed (с 2 slow), 478 с |
| `test_chart_theme_21e.py` | 73 passed |
| `test_user_errors_21zh.py` | 47 passed |
| `thermogar_paths_test.py` (unittest) | Ran 6 tests, OK |

Коммит `5ea5638`.

## Шаг 4. Сверка вкладок с эталоном 0.5.0

* `tools\tab_snapshot.py run --out results\validation\wave20_d\posle --state results\validation\wave20_v\state\run4 --time-csv results\wave20_d\posle_time.csv`. Окружение — `MPLBACKEND=Agg`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`. Папка `results\wave20_d\` создана заранее.
* Прогон — 20:56:18–21:50:37, 54,3 мин (20-Г — 56,0). Пик дерева процессов — 3,09 ГиБ, минимум свободной памяти — 5,57 ГиБ, снятых по памяти 0. Код выхода 0, stderr пуст.
* `posle_svodka.txt` — 130 из 130: код 0, «ошибка» null, «исключений_на_экране» 0.
* `posle_sha256.txt` — 4036 строк. От `run1_sha256.txt` 20-В и от `posle_sha256.txt` 20-Г он отличается в 463 строках — это файлы «равны с исключениями». Во всех 130 `meta.json` — `ThermoGar_app.py_sha256` = `1bc0e905…` (файл после переноса).
* Правила — `results\wave20_g\isklyucheniya.txt` без изменений, 14 правил, копии нет.
* `tools\tab_snapshot_compare.py results\validation\wave20_v\run1 results\validation\wave20_d\posle --isklyucheniya results\wave20_g\isklyucheniya.txt --otchet results\wave20_d\sravnenie.txt` — код выхода 0, «правил 14»:
  `ИТОГ: файлов 4036; равны 3573; равны с исключениями 463; различаются 0; нет пары 0; нарушений целостности A 0, B 0` — **«ИТОГ: полное равенство»**.
* Срабатывания правил (сколько файлов): 1 — 418, 2 — 130, 3 — 143, 4 — 8, 5 — 2, 6 — 135, 7 — 3, 8 — 3, 9 — 3, 10 — 27, 11 — 9, 12 — 18, 13 — 1, 14 — 130 (все 130 `meta.json`). Все 14 чисел равны числам сверки 20-Г. «Различаются» и «нет пары» — 0; разбирать нечего, новых правил нет.

Коммит `ef18553`: `posle_time.csv`, `posle_stdout.txt`, `posle_svodka.txt`, `posle_sha256.txt`, `sravnenie.txt`.

## Шаг 5. Полная регрессия

* Раннер — `results/wave20_d/scripts/run_regress.py`, копия `results/wave20_g/scripts/run_regress.py` с двумя правками по заданию: :68 (`RELEASE_OUT` — `results/wave20_d`, «каталог вывода 20-Д») и :141 (`results/validation/wave20_d_state`). `diff` с источником — только эти две строки.
* Прогон — 21:52:05–23:41:33, 109,5 мин (20-Г — 137,1). Свободно на входе — 8,57 ГиБ. Пик — 4,87 ГиБ (`test_ui_f -m slow`), минимум свободной памяти — 3,87 ГиБ, прерванных по памяти 0.
* **78 заданий** — состав и порядок равны 20-Г; новый модуль не тест и в задания не входит.
* Выход 0 — **69**, выход 5 — **9**, других выходов нет, красных нет.
* Выход 5 (тестов с отметкой not slow нет), список равен списку 20-Г:
  `notslow__test_liquidus_bisection.py`, `notslow__test_phase_presets_control.py`, `notslow__thermogar_converter_patch_test.py`, `notslow__thermogar_diffusion_test.py`, `notslow__thermogar_fe_database_test.py`, `notslow__thermogar_physical_test.py`, `notslow__thermogar_precipitation_test.py`, `notslow__thermogar_properties_test.py`, `notslow__thermogar_self_test.py`.
* `test_ui_f -m slow` — одним процессом (свободно 8,60 ≥ 6,0 ГиБ): 21 passed, 1065,3 с.
* Итоговые строки 78 заданий без времени и числа предупреждений равны строкам 20-Г, кроме одной: `notslow__test_version_consistency.py` — 94 passed против 93. Лишний тест — `test_first_version_mention_is_app_version[app/thermogar_app_texts.py]`: тест параметризован по файлам `app/*.py`, новый модуль дал ещё один случай. Всего 1088 passed, 1 xfailed, 242 deselected. 7 сценариев — выход 0.
* `results\wave21_eh\scripts\backend_compare.py results\wave20_d\regress_backend results\wave20_d\backend_compare.txt` — ячеек 57 / 57, статусы `PASS`. Разница в одной ячейке — `[Кинетика] KWN (модуль) | fe`, «строк кинетики» 1123 (законная, 22-Б; как у 20-Г). **«ВЕРДИКТ: PASS»**. Файл отличается от 20-Г только путём в первой строке.

Коммит `4789da9`: копия раннера, `regress_logs` (78), `regress_memlog` (62), `regress_backend` (2), `regress_summary.jsonl`, `backend_compare.txt`.

## Шаг 6. Реестр

Тексты мастера — дословно (абзац (в) и шаблон строки (б) скрипт взял из `tasks/WAVE20_D_OPUS.md`). Правки:

* (а) строка 20-Г — «**принята мастером 28.09.2026 (ниже); влита в `main` (`b719976`).**»;
* (б) строка 20-Д после строки 20-Г; итог числами — из этого отчёта;
* (в) абзац «Приёмка 20-Г мастером (28.09.2026). …» после абзаца «Решение владельца, 28.09.2026 (BL-57, неиспользуемый код). …»;
* (г) BL-57 — «… шаг 1 — удаление неиспользуемого кода (20-Г); шаг 2 — тексты и умолчания (20-Д).**».

Остальное в ячейках не менялось. `git diff --stat` — 5 вставок, 2 удаления. Коммит `883a156`.

## Что где лежит

* В git (`results/wave20_d/`): `posle_time.csv`, `posle_stdout.txt`, `posle_svodka.txt`, `posle_sha256.txt`, `sravnenie.txt`, `scripts/run_regress.py`, `regress_logs/`, `regress_memlog/`, `regress_backend/`, `regress_summary.jsonl`, `backend_compare.txt`.
* Вне git: снимок — `results\validation\wave20_d\posle\` (130 случаев), состояние снимка — `results\validation\wave20_v\state\run4\`, состояние регрессии — `results\validation\wave20_d_state\`.
* В `_to_delete\` в этой задаче ничего не добавлено.

## Отступления от задания

1. **Лёгкая работа во время снимка.** Пока шёл снимок, сделаны копия раннера с двумя правками, правки реестра (а), (в), (г) и проверка скрипта сводки на данных 20-Г. Во время регрессии ничего не делалось. Тяжёлых прогонов параллельно не было. Время снимка (54,3 мин) брать с этой оговоркой.
2. **Вспомогательные скрипты вне дерева.** Перенос с проверкой границ, проверка AST и значений, сводка и `posle_sha256.txt`, правки реестра — скрипты во временной папке сессии, не в репозитории. Скрипт сводки проверен на прогоне 20-Г: он даёт `posle_svodka.txt` и `posle_sha256.txt` 20-Г байт в байт (по блобам).
3. **Потоки вывода вне списка.** stderr снимка (0 байт), вывод сверки в консоль и консоль раннера регрессии записаны во временную папку сессии. Задание их в список файлов не включает.
4. **pyflakes не запускался.** В `.venv-windows` пакета `pyflakes` нет, ставить пакеты нельзя. Задание pyflakes не требует; мастер в приёмке 20-Г сверял его сам. Замена — проверка AST: `PHYSICAL_OVERRIDES_ENV` и два имени `ELASTIC_*` в головном сценарии не используются, все 21 импортированное имя — ровно перенесённые.
5. **Концы строк.** В рабочей копии `core.autocrlf=true`. Новые текстовые файлы в индексе с LF. Две строки `.gitignore` дописаны в рабочую копию с CRLF, как остальной файл; в индексе — LF. `app/ThermoGar_app.py` и `app/thermogar_app_texts.py` записаны с LF и в рабочей копии.
6. **Тестов на один больше.** 1088 passed против 1087 у 20-Г — не отступление исполнителя, а следствие нового файла в `app/` (разбор в шаге 5). Число заданий и список выходов 5 — прежние.

## git
