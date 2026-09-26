# Отчёт 21-Т: слияния 21-О, 21-П, 21-Р в `main`; реестр; BL-69

Задание — `tasks/WAVE21_T_OPUS.md`. Дерево `D:\Pets\ThermoGar-w21b`, ветка `wave21-t`, 26.09.2026, ноутбук Windows 10. Интерпретатор — `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe`. Все прогоны — `PYTHONHASHSEED=0`, `MPLBACKEND=Agg`, `PYTHONDONTWRITEBYTECODE=1`, `THERMOGAR_STATE_ROOT` во временной папке (`%TEMP%\tg21t_*`); перед тяжёлым прогоном свободно 7.93 ГиБ из 15.71. Изменены только `tasks/REGISTER.md` и `tools/conftest.py`; новые — `tasks/WAVE21_T_OPUS.md`, `tasks/WAVE21_T_REPORT.md`. `app/`, другие `tools/`, `docs/`, `databases/`, `configs/`, `packaging/`, `CHANGELOG.md` не менялись; `.tdb` и `.pdb` не трогались. `D:\Pets\ThermoGar`, `D:\Pets\ThermoGar-w21a` и `D:\Pets\Lilith` не открывались. Ничего не удалялось; `_to_delete/` не понадобился.

## ШАГ 0. Слияния

До начала: `git status --short` — только `?? _to_delete/` (ветка `wave21-o`). `git fetch origin` — без обрыва.

`git ls-remote origin main wave21-o wave21-p wave21-r` — все четыре совпали с заданием:

```
a68a41704f4db6053d8c073c96c30938251be930	refs/heads/main
689d9b3eb5edabba5a5a49732e95252a2e9d4eaf	refs/heads/wave21-o
71827714552b05ddb241e178e05edc216c8eb151	refs/heads/wave21-p
7f6a64660df5f8a45152afb7326cbd5a720283e8	refs/heads/wave21-r
```

`git switch --detach origin/main`, затем три `git merge --no-ff` по порядку. Конфликтов нет, все три слияния чистые.

| № | Коммит слияния | Родители | Дерево | Модель мастера |
|---|---|---|---|---|
| 1 | `a6df161d3dd04657c8ed111f35a54ed296ca570c` «Merge wave21-o: сталь (1Б, 2В, 3В), BL-66, 12Б, тесты под 22-Б (21-О)» | `a68a417` + `689d9b3` | `c353a08fe5dcfc0ff3a85d72c322afbd470f9dbb` | совпало |
| 2 | `65030028e4625f5705ea534680b6553f0456d722` «Merge wave21-p: опись для пересборки руководства (21-П)» | `a6df161` + `7182771` | `2fb686bded9d08ac21ea20ebe8731adc50401a02` | совпало |
| 3 | `976e7075c980add6002957ad54cdc36dd290771c` «Merge wave21-r: подготовка пересборки руководства (21-Р)» | `6503002` + `7f6a646` | `11c5874c5f1390d34fae8d0ca91fd97f77c87053` | совпало |

Тесты на `976e707` — один прогон pytest (`-p no:cacheprovider`, `python -B`): **166 passed, 3 warnings, 299.52 с**; красных нет.

| Файл | Тестов | Итог |
|---|---|---|
| `tools/test_version_consistency.py` | 92 | passed |
| `tools/test_switch_21i.py` | 13 | passed |
| `tools/test_wave21_m.py` | 22 | passed |
| `tools/test_wave21_o.py` | 11 | passed |
| `tools/test_precipitation_bl35.py` | 11 | passed |
| `tools/test_kwn_step_cap_22b.py` | 9 | passed |
| `tools/test_tab_snapshot_compare.py` | 8 | passed |

Предупреждения — 3 одинаковых `RuntimeWarning: divide by zero encountered in divide` из `kawin/precipitation/NucleationRate.py:190` (`test_wave21_o::test_precipitation_excel_ni`, `test_precipitation_bl35::test_718_run_ends_with_quality_error_not_exception`, `test_kwn_step_cap_22b::test_run_uses_step_limit_and_min_composition`) — внутри kawin, на итог не влияют.

Синтаксис — `compile()` в памяти (`python -B -c "compile(open(p, encoding='utf-8').read(), p, 'exec')"`), без `py_compile`: `tools/make_guide_screens.py` — ok, `tools/tab_snapshot.py` — ok. `__pycache__` не появился (`git status --short` — только `?? _to_delete/`).

`git push origin HEAD:refs/heads/main` — `a68a417..976e707  HEAD -> main`. Затем `git switch -c wave21-t`. Задание без первой строки «/caveman ultra» — дословно в `tasks/WAVE21_T_OPUS.md`, первый коммит ветки `e600977`.

## ШАГ 1. Реестр

Коммит `46bbc1a`. Тексты мастера вставлены дословно, `<…>` заполнены хешами ШАГА 0: `a6df161` (21-О), `6503002` (21-П), `976e707` (21-Р). Правка — скриптом с проверкой, что каждое заменяемое место в файле ровно одно.

- а) Таблица волны 21: строка 21-О — начало ячейки состояния заменено на «**принята мастером 26.09.2026 (ниже); влита в `main` (`a6df161`).**», остальное в ячейке не менялось; строка 21-П — ячейка состояния заменена текстом мастера с `6503002`; после неё — строки 21-Р (с `976e707`), 21-С, 21-Т.
- б) Три абзаца «Приёмка 21-О / 21-П / 21-Р мастером (26.09.2026)» — после абзаца «Решения владельца по стали, 26.09.2026. …», перед «### Ошибка мастера (21-В)».
- в) Раздел «### Ошибка мастера (21-П)» — после «### Ошибка мастера (BL-66)», перед «## Волна 22 …».
- г) «### Опечатки в сданных отчётах» — строка `tasks/WAVE21_P_REPORT.md` в конец таблицы (после строки `tasks/WAVE15_L_REPORT.md`).
- д) Бэклог: BL-43 и BL-66 — «**закрывается 21-О (сдано, мастер не смотрел).**» заменено на «**закрыт 21-О (принята мастером 26.09.2026).**», остальное не менялось; BL-68 — описание дописано («; шире (замер мастера 26.09.2026, Streamlit 1.62.0): …; вызовов таблиц в `app/` — 64»), состояние — «**открыт, заведён 21-О; опись и пробы — 21-С; как показывать пустое (пусто или «—») — решение владельца.**»; BL-69 — «**в работе, 21-Т.**».

Итог правки: `tasks/REGISTER.md | 26 ++++++++++++++++++++------` (20 вставок, 6 удалений — 6 изменённых строк: 21-О, 21-П, BL-43, BL-66, BL-68, BL-69).

## ШАГ 2. BL-69

Коммит `c78be3c`. Diff `tools/conftest.py`:

```diff
@@ -4,6 +4,7 @@
 ``THERMOGAR_MEMLOG=<путь к .jsonl>``: после каждого теста в файл пишется
 строка с рабочим набором процесса до и после теста, пиком по ходу теста
 (опрос дерева процессов раз в 0,2 с) и числом открытых фигур matplotlib.
+Поле ``peak_wset_process_gib`` на Linux и macOS — пик RSS процесса.
 Без переменной хуки ничего не делают.
 """
 
@@ -47,6 +48,17 @@ def _open_figures() -> int | None:
     return None if pyplot is None else len(pyplot.get_fignums())
 
 
+def _process_peak(process) -> int:
+    """Пик памяти процесса в байтах: Windows — peak_wset, иначе — ru_maxrss."""
+    if sys.platform == "win32":
+        return process.memory_info().peak_wset
+    import resource
+
+    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
+    # Linux отдаёт ru_maxrss в КиБ, macOS — в байтах.
+    return peak if sys.platform == "darwin" else peak * 1024
+
+
 class _Sampler(threading.Thread):
     def __init__(self, process) -> None:
         super().__init__(name="thermogar-memlog", daemon=True)
@@ -83,7 +95,7 @@ def pytest_runtest_protocol(item, nextitem):
         "rss_after_gib": round(after / GIB, 3),
         "growth_gib": round((after - before) / GIB, 3),
         "peak_tree_gib": round(max(sampler.peak, after) / GIB, 3),
-        "peak_wset_process_gib": round(process.memory_info().peak_wset / GIB, 3),
+        "peak_wset_process_gib": round(_process_peak(process) / GIB, 3),
         "open_figures": _open_figures(),
         "pool_workers": getattr(sys.modules.get("thermogar_parallel_ui"), "_WORKER_COUNT", None),
     }
```

Ключ `"peak_wset_process_gib"` не менялся.

Проверка на ноутбуке:

- `THERMOGAR_MEMLOG=%TEMP%\tg21t_E47I\memlog.jsonl`, `tools/test_version_consistency.py` — 92 passed за 0.97 с; в журнале 92 строки, поле `"peak_wset_process_gib"` есть во всех 92, значения 0.038…0.055 ГиБ. Первая строка: `{"test": "tools/test_version_consistency.py::test_payload_list_is_complete", "seconds": 0.1, "rss_before_gib": 0.038, "rss_after_gib": 0.037, "growth_gib": -0.0, "peak_tree_gib": 0.038, "peak_wset_process_gib": 0.038, "open_figures": null, "pool_workers": null}`.
- Без переменной — 92 passed за 0.31 с, новых файлов нет (во временной папке только журнал первого прогона).
- Ветка не-Windows на ноутбуке не исполнима (модуля `resource` на Windows нет), поэтому проверена в памяти, с подменой: `sys.platform` = `linux` / `darwin`, модуль `resource` — заглушка с `ru_maxrss=2048`. Итог: `linux 2097152` (2048 КиБ × 1024), `darwin 2048` (байты); на `win32` `_process_peak(psutil.Process())` равен `memory_info().peak_wset` — `True`. Файлы при этой проверке не писались.

## Отступления

1. `PYTHONDONTWRITEBYTECODE=1` и `python -B`, `-p no:cacheprovider` — во всех прогонах, сверх задания: чтобы в дереве не появлялись `__pycache__` и `.pytest_cache` (так же делали 21-О и 21-М).
2. Проверка ветки не-Windows `_process_peak` подменой `sys.platform` и `resource` — сверх задания: на Linux исполнитель прогнать не может; настоящий прогон `THERMOGAR_MEMLOG` на Linux — за мастером.
3. Счёт тестов по файлам в таблице ШАГА 0 — из `pytest --co -q` по каждому файлу (сумма 166 = итог прогона); сам прогон был один, общим списком.

## Вывод git

(ниже — после пуша ветки)
