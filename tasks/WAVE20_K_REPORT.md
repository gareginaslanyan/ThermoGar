# 20-К — отчёт: BL-57, шаг 7 разреза — вкладка «Кинетика» в своём модуле

**Итог:** 20-И влита в `main` (`45eb7e0`, дерево `e7aa768` = модель мастера). Вкладка «Кинетика» перенесена в `app/thermogar_tab_kinetics.py` (`render_kinetics_tab`). Файлы байт в байт равны модели мастера: `ThermoGar_app.py` — 11 151 строка, блоб `f169d98`; модуль — 63 строки, блоб `b115bf9`. `proverka_vkladki` — PASS. Тесты зелёные: 97 / 29 / 22 / 13 passed. Сверка вкладок с эталоном 0.5.0 — полное равенство (3573 + 463, 14 правил — те же числа, что у 20-И). Регрессия — 78 заданий: 69 выход 0, 9 выход 5; 1091 passed, 1 xfailed. Эталон расчётов — PASS.

Исполнитель — Claude Opus 5.5, ноутбук Windows 10, дерево `D:\Pets\ThermoGar-w21b`, 30.09.2026. Интерпретатор — `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe` (3.11.9).

## Время по шагам

| Шаг | Начало | Конец |
|---|---|---|
| 0. Проверки входа | 12:39:12 | 12:39:25 |
| 1. Слияние 20-И, задание | 12:39:25 | 12:40:47 |
| 2. Вкладка «Кинетика» | 12:40:52 | 12:44:03 |
| 3. Тесты | 12:44:08 | 12:49:21 |
| 4. Сверка вкладок | 12:49:40 | 13:56:27 |
| 5. Полная регрессия | 13:56:27 | 16:10:49 |
| 6. Реестр | 16:10:49 | 16:11:37 |
| 7. Отчёт, пуш | 16:11:37 | см. раздел «git» |

## Шаг 0

`git status --short`:

```
?? _to_delete/
```

Ветка на входе — `wave20-i`. `git fetch origin` — без вывода. `git ls-remote origin main wave20-i`:

```
11eabbc07521b3cfb1d5d02e32610ffbc64a925c	refs/heads/main
4c9151f3167e84e24c874b3b46cbfb0decd96614	refs/heads/wave20-i
```

Оба хэша совпали с заданием. Эталон `results\validation\wave20_v\run1` — 130 каталогов случаев. Свободно памяти — 6,42 ГиБ из 15,71. Интерпретатор запустился (`3.11.9`).

## Шаг 1

* `git switch --detach origin/main` → `11eabbc`.
* `git merge --no-ff origin/wave20-i -m "Merge wave20-i: привязка базы ThermoGar_app.py (20-И)"`:
  * коммит слияния — `45eb7e08406e85fe826d5d0897ca61ca0a75d845`;
  * родители — `11eabbc` и `4c9151f`;
  * дерево — `e7aa768853c76efb1261518903d6a3fbf53db0ad`, совпало с заданием.
* `git push origin HEAD:refs/heads/main` — `11eabbc..45eb7e0  HEAD -> main`.
* `git switch -c wave20-k`.
* Задание без первой строки «/caveman ultra» — в `tasks/WAVE20_K_OPUS.md` (UTF-8, LF). Коммит `bb0db73`.

## Шаг 2. Вкладка «Кинетика»

До правки `app/ThermoGar_app.py` — блоб `6ce2bb2d53372c734406d21d436f5c7303b889fa`, 11 178 строк, LF (CR — 0). Строки `:185`, `:190`, `:315`, `:10707`, `:10708–:10734` совпали с текстом задания.

Модуль и правку сделал один скрипт Python (stdin, без файла). Скрипт сверял каждую строку по номеру перед правкой:

* (а) модуль: текст задания + пустая строка + байты строк `:10708–:10734` + один `\n`; UTF-8 без BOM, LF;
* (б1) удалены `:185` и `:190`;
* (б2) после `:315` — `from thermogar_tab_kinetics import render_kinetics_tab`;
* (б3) `:10708–:10734` заменены на `    render_kinetics_tab(sidebar=SIDEBAR, services=SERVICES)`.

Сверка с замером мастера (в) — всё совпало:

| Файл | Строк | sha256 | Блоб |
|---|---|---|---|
| `app/ThermoGar_app.py` | 11 151 | `60392a2163c89ce64d108cbae4f6c1be7383563529d67002475737aec3df1503` | `f169d98ce6491c0773e83c479e3e0b8e7bb8c7ac` |
| `app/thermogar_tab_kinetics.py` | 63 | `b881c8f37e04976b4d7baa1b599dad9f104d7919f13de4ec77e3385ed9ae8405` | `b115bf9c33f5e8255ac4bc2e02ea71e1e823d1da` |

`git diff --numstat` — `2	29	app/ThermoGar_app.py`. Блобы после `git add` — те же.

### proverka_vkladki

Скрипт — `results/wave20_k/scripts/proverka_vkladki.py`. Только стандартная библиотека: `ast`, `builtins`, `symtable`, `subprocess`. Он общий для следующих вкладок: пять параметров (блоб до правки, головной сценарий, модуль вкладки, функция, переменная вкладки). Файл до правки скрипт читает сам: `git cat-file blob`, байты.

Запуск из корня:

```
python -B -X utf8 results\wave20_k\scripts\proverka_vkladki.py 6ce2bb2d53372c734406d21d436f5c7303b889fa app\ThermoGar_app.py app\thermogar_tab_kinetics.py render_kinetics_tab diffusion_tab > results\wave20_k\proverka_vkladki.txt
```

Код выхода 0. Вывод (`results/wave20_k/proverka_vkladki.txt`) — главное:

* тело: `:10708–:10734` до правки (27 строк, 3 оператора) = строки `37–63` функции (27 строк, 3 оператора); текст байт в байт — равен, `ast.dump` — равен; после тела в модуле — ничего; параметры — только именованные `sidebar`, `services`;
* пролог — 8 присваиваний, отклонений 0. У каждого `SIDEBAR = SidebarContext(…)` (`:5911`) или `SERVICES = RunServices(…)` (`:5930`) передаёт `поле=имя` — тот же объект. Переприсваиваний на уровне модуля после `SIDEBAR` / `SERVICES` — 0, `global` — 0. Тело читает каждое имя пролога;
* имён, которые тело читает и не связывает, — 13: из пролога 8, импортом нового модуля 5 (`st` — `streamlit`, `figure_to_png` — `thermogar_app_common`, `record_calculation_history` — `thermogar_workspace`, `render_kinetics_section` — `thermogar_diffusion`, `render_precipitation_section` — `thermogar_precipitation`; источник в файле до правки тот же у всех 5), прочих 0. Вложенных областей в теле 0;
* `diffusion_subtab`, `precipitation_subtab` в головном сценарии после правки читаются 0 раз;
* symtable: `thermogar_tab_kinetics.py` — глобальных чтений 5, имён в аннотациях 2, неопределённых 0; `ThermoGar_app.py` — 795, 32, неопределённых 0. Скрытых обращений в новом модуле 0. Для сведения: в головном сценарии их 2, прежние (`:4193` `globals()`, `:4213` `__import__()` в `dataframe_to_excel`);
* AST головного сценария: узлов верхнего уровня 241 → 242, операторов импорта 52 → 53. Убраны `render_kinetics_section`, `render_precipitation_section`, добавлен `render_kinetics_tab`. Тело `with diffusion_tab:` после правки — `render_kinetics_tab(sidebar=SIDEBAR, services=SERVICES)`. Откат — 241 и 241 узел, равны по `ast.dump` 241;
* импорт: `python -B -X utf8 -c "import sys; sys.path.insert(0, 'app'); import thermogar_tab_kinetics as k; print(k.render_kinetics_tab.__module__)"` — код 0, вывод `thermogar_tab_kinetics`.

`ИТОГ: PASS — тело 3 операторов, 27 строк; пролог 8; свободных имён 13 (8 + 5, прочих 0); узлов 241 → 242, импортов 52 → 53; откат 241 из 241`.

Отрицательная проба: копия модуля с лишним пробелом в теле (`_to_delete\20k_proba\`) → код 1, «текст тела байт в байт: НЕ равен», `ИТОГ: FAIL — тело`.

Коммит `e29fda3`: оба файла `app`, скрипт, вывод.

## Шаг 3. Тесты

`tools/test_version_consistency.py:95` — `    assert len(payload) == 80, len(payload)` → `    assert len(payload) == 81, len(payload)`. Блоб после — `577efed83b4db509e76ea5c97dc3af3e5c8b77e4`, совпал. `git diff --numstat` — `1	1`.

Прогоны 12:44:26–12:49:02, окружение `MPLBACKEND=Agg`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`. Команда — `-m pytest -q -p no:cacheprovider`, у `test_ui_g.py` ещё `-m "not slow"`. Журналы — `results\validation\wave20_k_shag3\`.

| Файл | Итог |
|---|---|
| `test_version_consistency.py` | 97 passed in 1.08s |
| `test_ui_g.py` (без slow) | 29 passed, 3 deselected, 2 warnings in 221.12s |
| `test_wave21_m.py` | 22 passed in 38.70s |
| `test_switch_21i.py` | 13 passed in 10.68s |

Два предупреждения `test_ui_g` — `RuntimeWarning: divide by zero` внутри `kawin/precipitation/NucleationRate.py:190` (`test_kwn_precipitation[ni]`, `[al]`), внешняя библиотека.

Коммит `c78af57`.

## Шаг 4. Сверка вкладок с эталоном 0.5.0

* Команда: `tools\tab_snapshot.py run --out results\validation\wave20_k\posle --state results\validation\wave20_v\state\run9 --time-csv results\wave20_k\posle_time.csv`.
  * Окружение — `MPLBACKEND=Agg`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`.
  * `run9` и `results\validation\wave20_k` до прогона не существовали. Свободно на входе — 6,51 ГиБ.
* Прогон — 12:49:40–13:54:39, 65,0 мин по сумме случаев (20-И — 54,4; см. отступление 5).
  * Пик дерева процессов — 3,09 ГиБ.
  * Минимум свободной памяти — 3,79 ГиБ.
  * Снятых по памяти 0.
  * Код выхода 0, stderr пуст (0 байт).
* `posle_svodka.txt` — 130 из 130: код 0, «ошибка» null, «исключений_на_экране» 0. Состав и порядок случаев — как у 20-И.
* `posle_sha256.txt` — 4036 строк.
  * Имена файлов отличаются от 20-И в 2 строках. Это файлы ошибок с отметкой времени: `g_kwn_grid/vygruzki/ThermoGar_error_20260930-133448-bd047268.json` и `g_kwn_too_long/vygruzki/ThermoGar_error_20260930-133313-3c393dd5.json`. У 20-И — те же 2.
  * Во всех 130 `meta.json` поле `ThermoGar_app.py_sha256` — `60392a21…`, файл после правки.
* Сводку и суммы строит скрипт `_to_delete\20k_skripty\svodka_sha256.py`. Проверка на прогоне 20-И: скрипт дал `posle_svodka.txt` и `posle_sha256.txt` 20-И с теми же блобами (`7182fe0`, `7dc9a7c`).
* Правила — `results\wave20_g\isklyucheniya.txt` без изменений, 14 правил, копии нет.
* Сверка: `tools\tab_snapshot_compare.py results\validation\wave20_v\run1 results\validation\wave20_k\posle --isklyucheniya results\wave20_g\isklyucheniya.txt --otchet results\wave20_k\sravnenie.txt` (13:54:58–13:56:04).
  * Код выхода 0, «правил 14».
  * `ИТОГ: файлов 4036; равны 3573; равны с исключениями 463; различаются 0; нет пары 0; нарушений целостности A 0, B 0` — **«ИТОГ: полное равенство»**.
* Срабатывания правил (сколько файлов): 1 — 418, 2 — 130, 3 — 143, 4 — 8, 5 — 2, 6 — 135, 7 — 3, 8 — 3, 9 — 3, 10 — 27, 11 — 9, 12 — 18, 13 — 1, 14 — 130.
  * Все 14 чисел равны числам 20-И.
  * `sravnenie.txt` отличается от файла 20-И только строкой `B:` (путь каталога).
  * «Различаются» и «нет пары» — 0; разбирать нечего, новых правил нет.

Коммит `c8d5a98`: `posle_time.csv`, `posle_stdout.txt`, `posle_svodka.txt`, `posle_sha256.txt`, `sravnenie.txt`.

## Шаг 5. Полная регрессия

* Раннер — `results/wave20_k/scripts/run_regress.py`, копия `results/wave20_i/scripts/run_regress.py` с двумя правками по заданию: `:68` (`RELEASE_OUT` — `results/wave20_k`, «каталог вывода 20-К») и `:141` (`results/validation/wave20_k_state`). `diff` с источником — только эти две строки.
* Первый запуск (13:56:3x) остановлен примерно через 30 с, см. отступление 1. Засчитан второй запуск.
* Прогон — 13:57:21–16:10:05, 132,7 мин по сумме заданий (20-И — 110,9; см. отступление 5).
  * Свободно на входе — 7,21 ГиБ.
  * Пик — 4,87 ГиБ (`test_ui_f -m slow`).
  * Минимум свободной памяти — 2,76 ГиБ, на `slow__test_ui_f.py`. Прерванных по памяти 0.
  * stderr раннера пуст (0 байт).
* **78 заданий**. Состав и порядок равны 20-И.
* Выход 0 — **69**, выход 5 — **9**. Других выходов нет, красных нет.
* Выход 5 означает, что в файле нет тестов с отметкой not slow. Список равен списку 20-И:
  `notslow__test_liquidus_bisection.py`, `notslow__test_phase_presets_control.py`, `notslow__thermogar_converter_patch_test.py`, `notslow__thermogar_diffusion_test.py`, `notslow__thermogar_fe_database_test.py`, `notslow__thermogar_physical_test.py`, `notslow__thermogar_precipitation_test.py`, `notslow__thermogar_properties_test.py`, `notslow__thermogar_self_test.py`.
* `test_ui_f -m slow` шёл одним процессом (свободно на старте 8,09 ≥ 6,0 ГиБ): 21 passed, 1206,3 с.
* Итоговые строки всех 78 заданий (без времени и числа предупреждений) равны строкам 20-И, кроме `notslow__test_version_consistency.py`: 96 → 97 passed. Всего **1091 passed, 1 xfailed**, 242 deselected.
* Сверка эталона расчётов: `results\wave21_eh\scripts\backend_compare.py results\wave20_k\regress_backend results\wave20_k\backend_compare.txt` — код 0.
  * Ячеек 57 / 57, статусы `PASS`.
  * Разница в одной ячейке — `[Кинетика] KWN (модуль) | fe`, «строк кинетики» 1123. Разница законная (22-Б), как у 20-И.
  * **«ВЕРДИКТ: PASS»**. Файл отличается от файла 20-И только путём в первой строке.

Коммит `fdb1ea7`: копия раннера, `regress_logs` (78), `regress_memlog` (62), `regress_backend` (2), `regress_summary.jsonl`, `backend_compare.txt` — 145 файлов.

## Шаг 6. Реестр

Тексты мастера — дословно: скрипт `_to_delete\20k_skripty\reestr.py` взял строку (а), шаблон строки (б), абзацы (в) и строки (г) из `tasks/WAVE20_K_OPUS.md`. Правки:

* (а) строка 20-И — «**принята мастером 30.09.2026 (ниже); влита в `main` (`45eb7e0`).**»;
* (б) строка 20-К после строки 20-И; итог числами — из этого отчёта;
* (в) абзацы «Приёмка 20-И мастером (30.09.2026). …» и «Ошибка мастера (20-И, откат AST). …» после абзаца «Приёмка 20-З мастером (29.09.2026). …», каждый после пустой строки;
* (г) BL-57 — «… шаг 6 — привязка базы (20-И); шаг 7 — вкладка «Кинетика» (20-К).**».

Остальное в ячейках не менялось. `git diff --stat` — 7 вставок, 2 удаления. Коммит `14a4d2d`.

## Что где лежит

* В git (`results/wave20_k/`): `scripts/proverka_vkladki.py`, `proverka_vkladki.txt`, `posle_time.csv`, `posle_stdout.txt`, `posle_svodka.txt`, `posle_sha256.txt`, `sravnenie.txt`, `scripts/run_regress.py`, `regress_logs/`, `regress_memlog/`, `regress_backend/`, `regress_summary.jsonl`, `backend_compare.txt`.
* Вне git (`results\validation\`):
  * снимок — `wave20_k\posle\` (130 случаев) и `wave20_k\posle_logs\`;
  * состояние снимка — `wave20_v\state\run9\`;
  * состояние регрессии — `wave20_k_state\`;
  * журналы ШАГА 3 — `wave20_k_shag3\`;
  * потоки вывода — `wave20_k_potoki\`: stderr снимка (0 байт), консоль сверки, консоль и stderr раннера (stderr 0 байт), консоль сверки эталона расчётов.
* `_to_delete\` (вне git), у каждой папки опись `opis_sha256.txt`:
  * `20k_proba\` — отрицательная проба `proverka_vkladki`;
  * `20k_skripty\` — `svodka_sha256.py`, его проверочные выходы на 20-И, `reestr.py`, `itog.txt`;
  * `20k_regress_prervan\` — вывод остановленного первого запуска регрессии.
* Вне дерева `D:\Pets\ThermoGar-w21b` ничего не искалось и не читалось, кроме интерпретатора окружения и выходных файлов фоновых задач сессии.

## Отступления от задания

1. **Регрессия запущена дважды.** Первый запуск шёл фоновой задачей оболочки. Её предел — 2 ч, а снимок ШАГА 4 шёл на 20 % дольше 20-И: регрессия могла выйти за 2 ч и быть убитой посередине. Поэтому первый запуск остановлен примерно через 30 с. Он успел только начать `notslow__test_backend_calculations.py`, в `regress_summary.jsonl` записей не было. Частичный вывод перенесён в `_to_delete\20k_regress_prervan\` (опись sha256), не удалялся. Второй запуск — отдельным процессом (`Start-Process`), с тем же окружением. Состояние регрессии `wave20_k_state` первый запуск не создал. Код выхода раннера во втором запуске не записан (`Start-Process` без ожидания). Раннер завершился сам: 78 записей из 78, stderr 0 байт.
2. **Лёгкая работа во время тестов ШАГА 3.** Пока шли тесты, сделаны скрипт сводки и сумм и его проверка на данных 20-И, копия раннера с двумя правками, чтение реестра. Во время снимка и регрессии шло только наблюдение: два запроса хода по просьбе мастера и ожидание конца процесса (проверка раз в 30–60 с). Тяжёлых прогонов параллельно не было.
3. **Вспомогательные скрипты.** Правка ШАГА 2 — скрипт Python через stdin, без файла. Сводка, суммы и правки реестра — скрипты в `_to_delete\20k_skripty\`, не в git. В git только скрипты, названные в задании. Вспомогательные скрипты шли с `-B -X utf8`, но не всегда с `MPLBACKEND=Agg` и `PYTHONHASHSEED=0`: они не импортируют matplotlib и не зависят от порядка хешей. Тесты, снимок, сверка, регрессия, сверка эталона расчётов и `proverka_vkladki` шли с полным окружением.
4. **Вывод `proverka_vkladki`.** Параметров — пять, как в задании; вывод идёт в stdout байтами UTF-8 с LF и перенаправлен в `results\wave20_k\proverka_vkladki.txt`.
5. **Машина медленнее, чем у 20-И.** Снимок — 65,0 мин против 54,4, регрессия — 132,7 против 110,9. Задержка равномерная, +15–20 % на тяжёлых заданиях (`slow__test_backend_calculations` 871,8 с против 710,6, `slow__test_ui_f` 1209,2 против 1089,9). Памяти хватало, снятых и прерванных 0. Причину не искал. Итоги от этого не зависят.
6. **Итог числами в строке 20-К реестра** составлен исполнителем по образцу строки 20-И. Остальные тексты реестра — дословно из задания.
7. **Концы строк.** В рабочей копии `core.autocrlf=true`. Правленые файлы `app/`, `tools/`, `tasks/`, вывод проверки, сводка и суммы записаны с LF. `posle_stdout.txt` и `sravnenie.txt` в рабочей копии с CRLF, в индексе — LF, как у 20-И (`git ls-files --eol`).
8. **Для сведения, вне задачи.** В строке 20-Е реестра — двойная точка «PASS.. Отчёт `tasks/WAVE20_E_REPORT.md`». Не правил: правка вне списка задания.

## git

Снято после пуша коммита `8c7c78f` (30.09.2026 16:13:30). Коммит, который дописал этот раздел, в выводе не виден — его хэш даёт `git log` ветки.

`git ls-remote origin main wave20-k`:

```
45eb7e08406e85fe826d5d0897ca61ca0a75d845	refs/heads/main
8c7c78f5648dd432352e43801f0f26fed33d619b	refs/heads/wave20-k
```

`git log --oneline origin/main..wave20-k`:

```
8c7c78f docs(20-К): отчёт — шаг 7 разреза BL-57
14a4d2d docs(20-К): реестр — приёмка 20-И, ошибка мастера, строка 20-К, BL-57
fdb1ea7 results(20-К): полная регрессия после переноса вкладки «Кинетика» — 78 заданий, 69 выход 0, 9 выход 5; эталон расчётов PASS
c8d5a98 results(20-К): сверка вкладок с эталоном 0.5.0 после переноса вкладки «Кинетика» — полное равенство (правил 14)
c78af57 test(tools): 20-К — нагрузка установщика 80 → 81 (новый модуль app/thermogar_tab_kinetics.py)
e29fda3 refactor(app): 20-К — вкладка «Кинетика» в своём модуле thermogar_tab_kinetics.py (render_kinetics_tab; тело без правок, пролог из SidebarContext и RunServices)
bb0db73 docs(tasks): 20-К задание (BL-57, шаг 7 разреза — вкладка «Кинетика» в своём модуле)
```

`git status --short`:

```
?? _to_delete/
```
