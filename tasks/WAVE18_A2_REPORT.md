# Отчёт 18-А2 — доводка 18-А

**Итог: сделано.** Устаревшие `.pyc` перенесены в `_to_delete/`, `tools/thermogar_paths_test.py` зелёный.
Причина BL-53 установлена: **среда теста, а не `THERMOGAR_STATE_ROOT` и не код приложения.** Из всех
прогонов с одним отличием от базы 18-А проходит только прогон с `MPLBACKEND=Agg` (`6 passed`). Код не
менялся. Попутно найден гон миграции состояния в воркерах пула при штатном `STATE_ROOT` — это код
приложения, не разбирал, выношу на решение мастера (п. 4).

Ветка `wave18-a`, в `main` не вливалось. Ничего не удалено, байты баз не менялись, `D:\Pets\Lilith` не
открывался. Один поток; прогоны — из PowerShell, каждый — отдельный процесс, по одному.

## 1. Устаревший байткод

Git не отслеживает `app/__pycache__/` (`git ls-files app/__pycache__` — пусто; `.gitignore:2:__pycache__/`).

Перенесено в `D:\Pets\ThermoGar\_to_delete\pycache_18_09\`:

| файл | время | размер | основание |
|---|---|---:|---|
| `thermogar_paths.cpython-311.pyc` | 18.09 11:11:35 | 34917 | задание |
| `thermogar_properties.cpython-311.pyc` | 18.09 11:11:38 | 98173 | задание |
| `thermogar_stage14.cpython-311.pyc` | 18.09 11:11:38 | — | **отступление**: без него тест красный |
| `thermogar_workspace.cpython-311.pyc` | 18.09 11:11:38 | — | **отступление**: без него тест красный |
| `thermogar_paths.cpython-311.pyc.regen_19_09_1426` | 19.09 14:26 | — | создан моим первым прогоном без `-B` |

**Отступление.** `test_005_module_is_stdlib_only_and_minus_b_creates_no_bytecode` запрещает в
`app/__pycache__` любой `.pyc` с префиксами `thermogar_paths.`, `thermogar_workspace.`,
`thermogar_properties.`, `thermogar_stage14.`, `ThermoGar_app.` (`tools/thermogar_paths_test.py:256`). После переноса двух файлов тест называл ещё `stage14` и `workspace` той же даты. Мой
первый прогон шёл без `-B` и заново создал `thermogar_paths.cpython-311.pyc`; этот файл тоже перенесён,
под другим именем. Тест рассчитан на `-B`.

Итог: `python -B tools\thermogar_paths_test.py` — `Ran 6 tests`, `OK`, exit 0.

## 2. BL-53: разведение средой

База — задание `notslow__test_parallel_integration.py` раннера 18-А (`results/wave18_a/run_regress.py`):

```
python -B -X utf8 -m pytest tools/test_parallel_integration.py -q -m "not slow" -p no:cacheprovider
PYTHONHASHSEED=0, THERMOGAR_MEMLOG=<файл>, THERMOGAR_STATE_ROOT=results\validation\wave18_a_state
```

Раннер — `results/wave18_a2/run_bl53.py`, сводка — `results/wave18_a2/summary.jsonl`, логи —
`results/wave18_a2/logs/`. Каждый вариант меняет относительно базы ровно одно. `MPLBACKEND` в
окружении сессии не задан.

| вариант | отличие от базы | exit | первая строка падения | итог |
|---|---|---:|---|---|
| (б) база | `STATE_ROOT=results\validation\wave18_a_state` | 2147483651 (`0x80000003`) | `..Windows fatal exception: code 0x80000003` | сбой на 3-м кейсе |
| (а) | без `THERMOGAR_STATE_ROOT` (штатный `%LOCALAPPDATA%\ThermoGar`) | 2147483651 | `..FWindows fatal exception: code 0x80000003` | 3-й кейс `F`, сбой на 4-м |
| (в) | пустой временный `STATE_ROOT` (`results\validation\wave18_a2_empty_1789817475`) | 2147483651 | `..Windows fatal exception: code 0x80000003` | сбой на 3-м кейсе |
| (г1) | `-p no:timeout` | 3 | `INTERNALERROR> … PluginValidationError: unknown hook 'pytest_timeout_set_timer'` | до тестов не дошло |
| (г2) | `THERMOGAR_TIMEOUT_EXIT=1` (хук conftest возвращает `None`) | 2147483651 | `..Windows fatal exception: code 0x80000003` | сбой на 3-м кейсе |
| (г3) | `--noconftest` (нет ни хука таймаута, ни замера памяти) | 2147483651 | `..Windows fatal exception: code 0x80000003` | сбой на 3-м кейсе |
| (д) | `PYTHONHASHSEED` не задан | 1 | `E AssertionError: assert ['0x1.698cc0a... ] == ['0x1.698cc08... ]` | `2 failed, 3 passed, 1 skipped`; кейс BL-53 **пропущен** (`skip` без сида) |
| (е) | без `THERMOGAR_MEMLOG` | 2147483651 | `..Windows fatal exception: code 0x80000003` | сбой на 3-м кейсе |
| **(ж)** | **`MPLBACKEND=Agg`** | **0** | — | **`6 passed in 54.14s`** |
| (б′) | `python -X faulthandler` | 2147483651 | `..Windows fatal exception: code 0x80000003` | сбой на 3-м кейсе |

(г1): без плагина `pytest-timeout` conftest не грузится вовсе — поэтому «без хука» проверено через
(г2) и (г3). (д): вариант не свидетельствует о причине — кейс BL-53 без `PYTHONHASHSEED=0` не
выполняется, а падения двух первых кейсов — ожидаемое расхождение в последних знаках без сида.
Варианты (е) и (ж) добавлены сверх списка задания, тоже по одному отличию.

**Проходит ровно при одном отличии — `MPLBACKEND=Agg`.** `STATE_ROOT` (а, в) и хук таймаута (г2, г3)
на сбой не влияют.

## 3. Стек и механизм

**Python-стек** (faulthandler, `results/wave18_a2/logs/b_faulthandler.log.txt`): главный поток —
в `_pytest/unraisableexception.py:83 collect_unraisable` (там `gc.collect()` после теста); второй
поток — `tools/conftest.py:58` (сэмплер памяти, ждёт на `Event`). В (г3) и (е) сэмплера нет, сбой тот же.

**Нативный стек** — из журнала приложений Windows (событие 1000, по одной записи на каждый сбой
этой сессии):

```
Имя сбойного модуля: tcl86t.dll, версия: 8.6.2.12
Код исключения: 0x80000003
Смещение ошибки: 0x00000000000f8bbd
Путь сбойного модуля: C:\Users\gareg\AppData\Local\Python\pythoncore-3.11-64\DLLs\tcl86t.dll
```

По таблице экспорта `tcl86t.dll` смещение `0xf8bbd` = `Tcl_PanicVA+0x13d`. Это паника Tcl: после
вывода сообщения Tcl зовёт точку останова. Полного нативного стека нет: отладчика (`cdb`, `procdump`)
в системе нет, а `LocalDumps` WER — ключ `HKLM`, его не трогал. Текст паники в лог не попал; в
17-Г тот же сбой шёл с `Tcl_AsyncDelete: async handler deleted by the wrong thread`
(`tasks/WAVE17_G_REPORT.md`, п. 3.2).

**Почему TkAgg.** Проверено отдельными командами:

```
import pycalphad        -> 'matplotlib' in sys.modules: True
import streamlit        -> os.environ['MPLBACKEND'] == 'Agg'
matplotlib.get_backend() -> tkagg
```

`streamlit/__init__.py:57` ставит `MPLBACKEND=Agg` при импорте, но matplotlib к этому моменту уже
загружен и переменную не перечитывает. `tools/test_parallel_integration.py` импортирует `pycalphad`
(строка 38) раньше `test_ui_f` и через него `streamlit` (строка 43), `matplotlib.use("Agg")` не
делает. `tools/test_ui_g.py:36` и `tools/test_backend_calculations.py:54` делают. Фигуры приложения
(`plt.subplots` в `app/ThermoGar_app.py`) создаются в потоке сценария AppTest; объекты Tk,
созданные в том потоке, освобождаются сборкой мусора в главном — Tcl паникует.

**Почему это не код приложения.** Под `streamlit run` модуль `streamlit` импортируется до сценария
приложения, бэкенд — `Agg`, Tk не создаётся. Сбой — свойство порядка импорта в тестовом файле.

**Почему 18-А связала сбой со `STATE_ROOT`.** Контроль 17-Г с `6 passed` шёл с `Agg`
(`tasks/WAVE17_G_REPORT.md`, таблица п. 3.1, столбец «matplotlib»). Раннер 18-А `MPLBACKEND` не ставит.
Отличались два условия, а сравнивалось одно. Момент сбоя зависит от сборки мусора: в основном прогоне
17-Г он пришёл после итоговой строки, в 18-А и здесь — на 3-м кейсе.

**Чинить (не делалось):** `matplotlib.use("Agg")` в начале `tools/test_parallel_integration.py` до
импорта `pycalphad`, как в `test_ui_g.py`; либо `MPLBACKEND=Agg` в раннере регрессии.

## 4. Попутно: гон миграции состояния в воркерах пула (код приложения)

В (а) 3-й кейс падает (`F`) ещё до сбоя Tk. Чтобы прочитать причину, сделан вспомогательный прогон
с **двумя** отличиями — штатный `STATE_ROOT` и `MPLBACKEND=Agg`
(`results/wave18_a2/logs/aux_a_default_state_root_agg_file.log.txt`): exit 1,
`1 failed, 5 passed in 73.22s`. Тот же кейс в одиночку (`-k`) — `1 passed` (`aux_a_default_state_root_agg.log.txt`).

```
E  AssertionError: Пул процессов отказал (Воркер завершился, не вернув результат (вероятно, не хватило
   памяти на 5 процессов)); оставшиеся точки досчитаны последовательно.
tools\test_parallel_integration.py:249: AssertionError
```

Воркер умер не от памяти (свободно ~10 ГиБ). Трасса из лога воркера:

```
File "...\multiprocessing\spawn.py", line 297, in _fixup_main_from_path
File "D:\Pets\ThermoGar\app\ThermoGar_app.py", line 612, in <module>
    LEGACY_MIGRATION_RECEIPT = migrate_legacy_state(THERMOGAR_PATHS, PROJECT_ROOT)
File "D:\Pets\ThermoGar\app\thermogar_paths.py", line 819, in migrate_legacy_state
    _atomic_write_receipt(paths, receipt)
File "D:\Pets\ThermoGar\app\thermogar_paths.py", line 412, in _atomic_write_receipt
    os.replace(temp, destination)
PermissionError: [WinError 5] Отказано в доступе:
  'C:\Users\gareg\AppData\Local\ThermoGar\.migration_receipt.json.migration-e9f7b8d92a07a2c986e2dd7b.tmp'
  -> 'C:\Users\gareg\AppData\Local\ThermoGar\migration_receipt.json'
```

Прочтение (не проверялось дальше): при `spawn` каждый воркер заново исполняет `ThermoGar_app.py`
как `__main__`, все пять разом пишут `migration_receipt.json`, и `os.replace` на Windows отказывает
при одновременной замене. С `THERMOGAR_STATE_ROOT` на `results\validation\…` этого не видно.
Под `streamlit run` `__main__` — не сценарий приложения, так что воспроизводится ли гон в
установленной программе, не установлено. **По правилу задания — стоп на этом месте**: код
приложения, не разбирал и не чинил. Решение мастера — заводить ли отдельный BL.

**Побочный эффект варианта (а):** прогоны писали в настоящий `C:\Users\gareg\AppData\Local\ThermoGar`
(так задано): обновлены `migration_receipt.json`, `workspace\history.jsonl`, 17 файлов
`state\alloy-library-json-v1\`, кэш `cache\tdb-…`. Виртуализацию `%LOCALAPPDATA%` (как в 17-Г) в
этой сессии не проверял; `CLAUDE_CODE_ENTRYPOINT=cli`.

## 5. Реестр

* BL-53 заведён с причиной и способом починки; состояние — открыт.
* 18-А — «принята, доводка 18-А2»; строка 18-А2 добавлена.
