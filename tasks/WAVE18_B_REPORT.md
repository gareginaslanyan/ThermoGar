# Отчёт 18-Б — доводки перед 0.4.3

**Итог: сделано.** BL-53 и BL-49 закрыты, BL-54 заведён и закрыт. Регрессия: 52 задания, **0 красных**.

**Ответ по BL-54: установленную 0.4.2 задевало.** Воркер пула в установленной программе исполняет весь
сценарий `ThermoGar_app.py` и вместе с ним миграцию состояния. Сам отказ `PermissionError` на
установленном рантайме я не воспроизвёл. Доказательство — в п. 2.

Работа шла в ветке `wave18-a`, в `main` не вливалось. Ничего не удалено: два каталога первых проб
перенесены в `_to_delete/`. Байты баз не менялись. `D:\Pets\Lilith` не открывался. Работал в один поток,
прогоны запускались из PowerShell.

## ETA — замер

Прогноз при старте — около 100 мин: сумма времени тех же заданий в регрессии 18-А (94,7 мин) плюс
новый файл. Промежуточный замер в 15:43 дал коэффициент 1,10 к 18-А и конец около 17:10. Факт:
**15:12:09 → 16:51:26, 99,3 мин.** Время по часам ноутбука, `results/wave18_b/regress_time.txt`.

## 1. BL-53 (тест)

* `tools/test_parallel_integration.py`: после стандартных импортов стоит `import matplotlib;
  matplotlib.use("Agg")`, до `pycalphad`, как в `test_ui_g.py`.
* `results/wave18_a/run_regress.py`: `MPLBACKEND=Agg` задан в окружении каждого процесса.
  `tools/conftest.py` окружение не задаёт, поэтому не менялся.
* **Отступление.** Регрессия 18-Б шла копией раннера `results/wave18_b/run_regress.py` с той же
  правкой. Причина: исходный раннер перезаписал бы логи 18-А в `results/wave18_a/regress_logs/`.
  Состав заданий и `STATE_ROOT` те же.
* Проверка с базовым окружением 18-А: без `MPLBACKEND`, `STATE_ROOT=results\validation\wave18_a_state`,
  `PYTHONHASHSEED=0`, `THERMOGAR_MEMLOG`. Результат: **`6 passed in 60.82s`**
  (`results/wave18_b/bl53_base_env.log.txt`).

## 2. BL-54 (продукт)

### Задевало ли установленную программу

Целевая функция пула — `thermogar_parallel._worker_solve`, `initializer` — `_worker_init`
(`app/thermogar_parallel.py:558, 586, 688–691`). Сам модуль `ThermoGar_app` воркер не импортирует.
Но spawn исполняет в воркере главный модуль родителя заново, как `__mp_main__`
(`multiprocessing/spawn.py`, `_fixup_main_from_path`). Под `streamlit run` главный модуль — сценарий
приложения. Streamlit перед исполнением ставит в `sys.modules["__main__"]` модуль с
`__file__ = <сценарий>` (`streamlit/runtime/scriptrunner/script_runner.py:697`, та же строка есть в
установленном рантайме). Папку сценария он кладёт в `sys.path` (`exec_code.py:62–63`). Пул поднимается
изнутри сценария и наследует то и другое. Установленный `launcher.pyw:879` запускает
`python -m streamlit run app`: механизм тот же.

Проба `results/wave18_b/bl54_probe.py` повторяет эти два шага streamlit. Затем она поднимает
`ProcessPoolExecutor` на spawn, как `thermogar_parallel.py`, и спрашивает воркер, что в нём
исполнилось. Везде задан временный `THERMOGAR_STATE_ROOT`.

| проба | интерпретатор | сценарий | результат |
|---|---|---|---|
| `venv_marker` | venv | сценарий-метка | метка исполнена в воркере |
| `installed_marker` | `C:\Program Files\ThermoGar\runtime\python.exe` | сценарий-метка | метка исполнена в воркере |
| `venv_app` | venv | `app\ThermoGar_app.py` | в `__mp_main__` есть `LEGACY_MIGRATION_RECEIPT` (dict) |
| `installed_app` | установленный рантайм | `C:\Program Files\ThermoGar\app\ThermoGar_app.py` | то же: 2 воркера из 2 |
| `installed_race4…8` | установленный рантайм | установленное приложение, 5 воркеров | 25 разных PID, во всех сценарий исполнен |

Что исполняет каждый воркер установленной программы:

* весь `ThermoGar_app.py` — 11 895 строк;
* 25 модулей `thermogar*` (`thermogar_paths`, `thermogar_workspace`, `thermogar_stage14` и другие);
* всего ≈2 340 модулей, включая `streamlit` и `pycalphad`;
* строку 612 — `migrate_legacy_state`, то есть запись `migration_receipt.json`.

Streamlit пишет в лог воркера около 4 000 строк `missing ScriptRunContext`.

Сам отказ. В 8 пробах на установленном рантайме по 5 воркеров со свежим `STATE_ROOT` отказа
`PermissionError` не было. Гон на уровне функции (см. ниже) на старом коде даёт 10 падений из 10.
Значит, 0.4.2 могла терять пул: при отказе воркера пул отказывает, и точки досчитываются
последовательно с пометкой «Пул процессов отказал…». Числа не менялись, росло только время. Как часто
это случалось у пользователя, не установлено.

### Починка (`app/thermogar_paths.py`)

* `migrate_legacy_state` в дочернем процессе сразу возвращает `None`
  (`multiprocessing.parent_process() is not None`). `LEGACY_MIGRATION_RECEIPT` в приложении больше
  нигде не читается.
* `_atomic_write_receipt` при `PermissionError` на `os.replace`, если назначение уже есть, делает одну
  повторную попытку через 50 мс. Если и она не удалась, функция перечитывает назначение и возвращает
  его. Если назначения нет, исключение пробрасывается, как раньше. Функция возвращает содержимое
  квитанции; `migrate_legacy_state` отдаёт его. При конфликте `LegacyMigrationConflict` несёт
  собственную квитанцию вызова, как раньше.

### Тесты (`tools/thermogar_state_migration_test.py`)

* 007 — пять независимых процессов разом, по 20 миграций каждый, в один временный `STATE_ROOT`.
  Результат: ни одного исключения, квитанция одна, `.tmp` не остаётся. Тот же сценарий на
  `thermogar_paths.py` из `7df123c` падает 10 раз из 10, на новом коде — 0 из 10
  (`results/wave18_b/bl54_race_old_vs_new.log.txt`).
* 008 — вызов в воркере spawn возвращает `None`, квитанции и копий нет.
* 009 — `os.replace` отказал дважды: 2 вызова, возвращена прежняя квитанция, байты файла те же.

Ожидание задания: `test_parallel_integration` со штатным `STATE_ROOT` и `Agg`. Результат:
**`6 passed in 59.62s`**, включая `test_temperature_scan_tables_match_with_and_without_pool`
(`results/wave18_b/bl54_default_state_root_agg.log.txt`). В 18-А2 тот же прогон дал `1 failed`.

## 3. BL-49 (экран)

* `thermogar_physical.PhysicalDensityDatabase.density_lower_temperature_k` — минимум нижних границ
  DP-параметров. Для v103 это 298,15.
* `ThermoGar_app.density_below_pdb_text`. Текст строится от границы из базы: при 298,15 K это
  дословно «Физическая база задаёт плотность с 25 °C; введите 25 °C или выше.». Сравнение то же, что в
  `parameter_value`, на той же температуре `T °C + 273.15`.
* «Плотность»: ниже границы показывается `st.error` с этим текстом, кнопка неактивна, дальше вкладка не
  строится.
* «Плотность по T»: то же, если ниже границы начало диапазона. Счёт не запускается.
* Если PDB не загружается, проверка молчит, и об ошибке сообщает сам расчёт, как раньше.
* Тест `tools/test_density_below_pdb.py`, Ni-20Cr, 5 кейсов: граница базы; 20 °C — текст, кнопка
  неактивна, результата нет, нет `BACKEND_FAILED` и `ValueError`; 25 °C — плотность посчитана; скан от
  20 °C — отказ; скан 25–125 °C — две точки. Результат: `5 passed`. Соседний
  `test_physical_overrides_toggle.py`: `11 passed`.

## 4. Регрессия

Раннер `results/wave18_b/run_regress.py`: каждый файл — отдельный процесс, `MPLBACKEND=Agg`,
`PYTHONHASHSEED=0`, `STATE_ROOT=results\validation\wave18_a_state`. Сводка —
`results/wave18_b/regress_summary.jsonl`, логи — `results/wave18_b/regress_logs/`.

* 52 задания. Выход 0 у 45 заданий. Выход 5 у 7 заданий (`no tests ran` / `deselected`): это файлы
  без не-slow тестов или сценарии, так же как в 18-А.
* Красные в 18-А теперь зелёные: `test_parallel_integration` — `6 passed` (в 18-А — выход
  2147483651) и `thermogar_paths_test` — `6 passed` (в 18-А — выход 1, устаревший `.pyc`, 18-А2).
  `thermogar_state_migration_test` — `9 passed`.
* `test_ui_f -m slow` шёл одним процессом (свободно 9,34 ГиБ ≥ 6,0): `21 passed in 1084.01s`, пик
  дерева процессов 4,88 ГиБ.
* Аварийных снятий по памяти нет.
* Сверка `backend_report_*.json` с `tools/backend_reference.md` в этой задаче не делалась.

## Побочные эффекты

* Прогон BL-54 со штатным `STATE_ROOT` писал в настоящий `C:\Users\gareg\AppData\Local\ThermoGar`, как
  вариант (а) 18-А2. Так задано условием.
* Пробы писали в `results\validation\wave18_b_probe_*`. Первые два каталога (`venv_app`,
  `installed_app`) перед повтором перенесены в `_to_delete\`.
* Установленная программа не менялась: пробы запускали её рантайм с `-B` и только читали файлы.

## Git

Ветка `wave18-a`:

```
0f430d9 test(18-Б): BL-53 — Agg в test_parallel_integration и в раннере регрессии
af56b28 fix(18-Б): BL-54 — миграция состояния не исполняется в воркере пула
2523a99 fix(18-Б): BL-49 — отказ плотности ниже границы PDB текстом владельца
<этот>  docs(18-Б): регрессия, реестр, отчёт
```

Реестр: BL-49 и BL-53 закрыты, BL-54 заведён и закрыт с оценкой «задевало установленную 0.4.2».
Добавлена строка 18-Б; состояние 18-А2 не трогал.
