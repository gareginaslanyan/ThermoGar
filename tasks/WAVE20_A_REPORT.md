# 20-А — отчёт: BL-57, шаг 0, эталон вкладок

Задание — `tasks/WAVE20_A_OPUS.md`. Ветка `wave20-a` от `5ed5d88`. Дерево `D:\Pets\ThermoGar`, `.venv-windows`, ноутбук Windows 10. Код приложения не менялся.

**Итог.** 130 случаев, 3913 файлов на прогон (+130 `sha256.txt`). Прогоны 1–2: 3454 файла равны байт в байт, 459 равны с 13 исключениями, различий 0, без пары 0 — полное равенство. Прогон 3 против прогона 1: то же самое, полное равенство. **BL-51 на разрез не влияет.**

## Шаг 0

* `git ls-remote origin main` → `5ed5d887f95d96d7a0e94978483a2103554e7e9e	refs/heads/main`. Совпадает.
* `git diff --stat v0.4.4 5ed5d88 -- app databases configs packaging tools` — пусто. По заданию опора регрессии — 19-Д (57 заданий, 0 красных), полная регрессия не гонялась.
* `app\__pycache__` и `tools\__pycache__` на входе отсутствовали, переносить было нечего.
* `git status --short` на входе, дословно (изменений в отслеживаемых нет):

```
?? "Claude outputs/"
?? PEREDACHA_MASTERA.md
?? PRAVILA_VZAIMODEYSTVIYA_VLADELEC_MASTER.md
?? _to_delete/
?? results/wave17_b/
?? results/wave18_a/p4/log_density_base_fecrc_off.txt
?? results/wave18_a/p4/log_density_base_fecrc_on.txt
?? results/wave18_a/p4/log_density_base_nialcr_off.txt
?? results/wave18_a/p4/log_density_base_nialcr_on.txt
?? results/wave18_a/p4/log_density_base_nicr_off.txt
?? results/wave18_a/p4/log_density_base_nicr_on.txt
?? results/wave18_a/p4/log_density_head_fecrc_off.txt
?? results/wave18_a/p4/log_density_head_fecrc_on.txt
?? results/wave18_a/p4/log_density_head_nialcr_off.txt
?? results/wave18_a/p4/log_density_head_nialcr_on.txt
?? results/wave18_a/p4/log_density_head_nicr_off.txt
?? results/wave18_a/p4/log_density_head_nicr_on.txt
?? results/wave18_a/p4/log_elastic_base_fecrc_off.txt
?? results/wave18_a/p4/log_elastic_base_fecrc_on.txt
?? results/wave18_a/p4/log_elastic_base_nialcr_off.txt
?? results/wave18_a/p4/log_elastic_base_nialcr_on.txt
?? results/wave18_a/p4/log_elastic_base_nicr_off.txt
?? results/wave18_a/p4/log_elastic_base_nicr_on.txt
?? results/wave18_a/p4/log_elastic_head_fecrc_off.txt
?? results/wave18_a/p4/log_elastic_head_fecrc_on.txt
?? results/wave18_a/p4/log_elastic_head_nialcr_off.txt
?? results/wave18_a/p4/log_elastic_head_nialcr_on.txt
?? results/wave18_a/p4/log_elastic_head_nicr_off.txt
?? results/wave18_a/p4/log_elastic_head_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_off_r2.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_density_ctrl_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_density_head_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_density_head_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nicr_on.txt
?? tasks/WAVE17_A_REPORT.md
?? tasks/WAVE17_B_REPORT.md
?? tasks/WAVE17_V_REPORT.md
?? tasks/WAVE17_ZH_OPUS.md
?? tasks/WAVE17_ZH_REPORT.md
```

## Шаг 1. Инструменты

`tools/tab_snapshot.py` снимает эталон, `tools/tab_snapshot_compare.py` сверяет два каталога. Имена не попадают под глобы регрессии `tools/test_*.py` и `tools/thermogar_*_test.py`.

* Каждый случай — отдельный процесс `python -B -X utf8` с `MPLBACKEND=Agg`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`, из корня дерева.
* Папка состояния — `results\wave20_a\state\<прогон>\<случай>\state` (второе приложение сценария — `…\state2`).
* Пул — `thermogar_parallel_ui._WORKER_COUNT = test_ui_f.UI_TEST_POOL_WORKERS` (2). После случая, как в фикстуре `_bounded_memory`: `close_shared_engines()`, `plt.close("all")`, `gc.collect()`.
* Выгрузки — перехват `st.download_button`, как в `test_ui_f`. Редактор упругих свойств подменяется так же, как в `test_ui_f.start(fill_elastic_editor=True)`.
* Профили и помощники импортируются из `tools/test_ui_*.py`: `BASES`, `TZERO_WINDOWS`, `ELASTIC_ROW_VALUES`, `_phases_without_bcc_b2`, `set_number`, `set_select`, `SIDEBAR_ALLOY`, `DIFFUSION_COUPLE`, `KWN_CELL`, `CASES`, `batch_csv`, `labelled`, `widget` и другие. Сами файлы не менялись.
* Сценарии `test_ui_h` идут по самому `app/ThermoGar_app.py`: инструмент проверяет, что ни один образец `UPSTREAM_PATCHES` не совпал, и иначе отказывается. Патченую копию в `app/` он не пишет.
* Прогон — случаи по одному. Порог входа — 3,0 ГиБ свободной памяти (ждать до 30 мин, затем СТОП). Аварийный порог по ходу — 1,0 ГиБ. Пик — по дереву процессов раз в 0,5 с.

Что пишется на случай (`<вывод>\<случай>\`):

* `karkas.txt` — элементы экрана (боковая, затем основная часть) после запуска и после каждого действия. В строке: путь вложенности (`вкладка[…]`, `раскрытие[…]`, `колонка#n`, `форма[…]`), тип, подпись, ключ, disabled, подсказка, варианты списков, min/max/step числовых полей, значение поля, текст markdown/caption/alert/заголовков/code/metric, столбцы и число строк таблиц со ссылкой на файл. Картинки `st.pyplot` — адресом media (хэш PNG).
* `ekran/tNNN.csv` — таблицы экрана, одна копия на содержимое; номер — по первому появлению.
* `sostoyanie/<прил>.json` и `sostoyanie/<прил>/*.csv` — весь `session_state` (без безключевых виджетов) после последнего шага. DataFrame → CSV, объекты `thermogar*` и dataclass — по полям, байты — длиной и sha256, чужие объекты — именем класса.
* `vygruzki/` — CSV, JSON, PNG, MD, прочее — байты как есть. XLSX — `*.listy.txt` и лист в CSV. ZIP и NPZ — `*.sostav.txt` (имена членов) и члены по тем же правилам. `vygruzki.txt` — перечень выгрузок с шагом первого появления.
* `texts.txt` — error/warning/info/success/toast/exception по шагам, с путём.
* `meta.json` — случай, группа, источник, шаги с длительностью, версии пакетов, sha256 `ThermoGar_app.py`, время, папка состояния.
* `sha256.txt` — по всем файлам каталога.

Числа с плавающей точкой везде через `repr` (CSV таблиц — своим писателем, не `to_csv`).

## Шаги 2–4. Время по прогонам

| прогон | начало | конец | сумма случаев, мин | А | Б | В | Г | пик дерева, ГиБ | мин. свободно, ГиБ | ждал памяти |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 (эталон) | 23.09 15:03:31 | 16:19:38 | 76,1 | 42,6 | 11,6 | 10,9 | 11,0 | 3,09 (`f_tmap_al`) | 3,46 | 0 с |
| 2 (повтор) | 16:20:41 | 17:26:24 | 65,7 | 35,9 | 10,2 | 8,9 | 10,7 | 3,12 (`f_tmap_al`) | 4,50 | 0 с |
| 3 (после `os.utime`) | 17:29:58 | 18:33:24 | 63,4 | 35,4 | 9,8 | 8,4 | 9,9 | 3,12 (`f_tmap_al`) | 4,72 | 0 с |

Все 390 запусков случаев завершились с кодом 0. Ошибок сценария нет, исключений (`st.exception`) на экране — 0 во всех случаях. По случаям — `results/wave20_a/run{1,2,3}_time.csv`.

**Прогноз после первых пяти случаев прогона 1** (`results/wave20_a/prognoz_run1.txt`). Первые пять — 78,4 с против 57,9 с тех же тестов в 19-Д, накладные ~4 с на процесс. Опора — тесты UI 19-Д: 117 тестов, 46,4 мин. Прогноз ~68 мин, конец около 16:12. Факт — 76,1 мин, конец 16:19:38. Промах +8 мин: диаграммы Al в отдельном процессе без тёплого кэша дороже, чем в 19-Д (`f_isopleth_al` 230 с против 200 с, `f_ternary_al` 139 против 115).

Проверка по месту, что действия дали результат:

* ключи результата есть в `session_state` у всех расчётных случаев: равновесия, сканы, затвердевание, диаграммы, карты, KWN трёх баз, диффузия, упругость, упрочнение, пакет;
* галочка поправок `physical_overrides_enabled` в случаях 15-Ш стоит как задано. Ni-20Cr, 700 °C: 8256,92979779211 кг/м³ с поправками и 8192,363455935654 без;
* пакет Fe–0,8C через экран даёт те же доли, что приёмка 19-Д через функции (`results/wave19_d/priemka/b_batch_*.csv`). «Пусто» и «метастабильный» — BCC_B2 0,8577531064096179 / CEMENTITE 0,1422468935902007, «стабильный» — BCC_B2 0,9643462664947882 / GRAPHITE 0,0356537…. «metastabe» — «ошибка» с текстом «Неизвестный режим стали: «metastabe». Используйте «стабильный» или «метастабильный».»

## Шаг 3. Сравнение 1–2

* Без исключений (`results/wave20_a/sravnenie_1_2_syroe.txt`): 3914 путей, равны 3454, различаются 458, без пары 2 (файл отчёта об ошибке `g_kwn_grid` с кодом ошибки в имени).
* Разбор по месту: различий в числах результата, в таблицах, PNG, текстах экрана и в порядке элементов `karkas.txt` нет. Все 458 различий — время, пути папки состояния прогона, случайные id и digest-поля, производные от часов. Причина каждого класса найдена в исходнике и записана в `isklyucheniya.txt`.
* С исключениями (`results/wave20_a/sravnenie_1_2.txt`): 3913 пар, равны 3454, равны с исключениями 459, различаются 0, без пары 0, целостность `sha256.txt` обеих сторон не нарушена — **полное равенство**. Все 13 правил сработали. Число файлов по номерам правил: 1 — 416, 2 — 130, 3 — 143, 4 — 4, 5 — 1, 6 — 135, 7 — 3, 8 — 3, 9 — 3, 10 — 27, 11 — 9, 12 — 18, 13 — 2.

### `results/wave20_a/isklyucheniya.txt` целиком

```
# 20-А: исключения при сверке эталона вкладок (tools/tab_snapshot_compare.py --isklyucheniya).
# Формат: правило | где | почему | пример различия (прогон 1 / прогон 2).
# re:… — совпадение в строке заменяется с обеих сторон, остальная строка сравнивается.
# путь:… — то же для поля в имени файла; содержимое файла сравнивается.
# Правила выведены из sravnenie_1_2_syroe.txt: каждое различие прогонов 1 и 2 разобрано по исходнику.
re:\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|[+-]\d\d:\d\d) | * | метка времени ISO 8601: начало и конец случая (meta.json), created_at/updated_at/exported_at выгрузок и записей, время события истории и изменения проекта — часы в момент прогона | "начало": "2026-09-23T15:03:46+03:00" / "2026-09-23T16:20:56+03:00"
re:"секунд": [0-9.]+ | */meta.json | длительность случая и шагов — время счёта | "секунд": 12.2 / 11.4
re:state\\\\run\d+ | */meta.json, */karkas.txt, */sostoyanie/*.json | папка состояния своя на каждый прогон (results\wave20_a\state\<прогон>\<случай>) — временный путь | "project_selected_path": "…\\state\\run1\\h_project_ni\\…" / "…\\state\\run2\\h_project_ni\\…"
re:\d{8}-\d{6}-[0-9a-f]{8} | * | код ошибки = дата-время + 8 случайных hex (app/thermogar_stage14.py:408, render_friendly_error); подпись «Код ошибки», ключ кнопки, JSON отчёта | Код ошибки: 20260923-155600-d0912443 / 20260923-170515-46c236b9
путь:\d{8}-\d{6}-[0-9a-f]{8} | */vygruzki/ThermoGar_error_* | тот же код ошибки в имени файла отчёта (app/thermogar_stage14.py:419); файл ставится в пару, содержимое сравнивается | ThermoGar_error_20260923-155600-d0912443.json / ThermoGar_error_20260923-170515-46c236b9.json
re:"sha256": ?"[0-9a-f]{64}" | */vygruzki/*.json | сумма конверта выгрузки считается по содержимому вместе с exported_at, то есть по времени; ключ ровно "sha256" (database_sha256 не затрагивается) | "sha256":"3a2b605a…" / "sha256":"51de92f1…"
re:"id": ?"[0-9a-f]{32}" | */vygruzki/*.json | id записи марки — uuid.uuid4().hex (app/thermogar_workspace.py:948), случаен | "id":"472e9f36…" / другой
re:alloy_(delete_confirm|delete_button)_[0-9a-f]{32} | */karkas.txt, */sostoyanie/*.json | ключи флажка и кнопки удаления марки несут тот же uuid записи | alloy_delete_button_7c36e321… / другой
re:значение="[0-9a-f]{32}"$ | */karkas.txt | значение списка «Выберите запись» (alloy_selected_id) — uuid записи | значение="7c36e321d2884cc9baa7e75849fe9e1c" / другой
re:"(receipt_digest|envelope_digest)": "[0-9a-f]{64}" | */sostoyanie/*.json | квитанция и конверт расчёта содержат время по системным часам (clock → _system_clock, app/thermogar_verified_properties.py:712 и загрузчики B3), поэтому их digest от прогона к прогону разный; числа результата лежат рядом и сравниваются | "receipt_digest": "ebee8e75…" / "a73f9ab3…"
re:"(prepared_witness_digest|hill_witness_digest|request_digest)": "[0-9a-f]{64}" | *elastic*/sostoyanie/*.json | упругость: witness — digest от receipt_digest и envelope_digest (app/thermogar_verified_properties.py:1249-1260), request_digest VRH несёт prepared_witness_digest во входах; только случаи упругости | "prepared_witness_digest": "6399c479…" / "8acd1d78…"
re:b4b2_elastic_(editor|update)_[0-9a-f]{64} | *elastic*/karkas.txt, *elastic*/sostoyanie/*.json | ключи редактора упругости и флажка «Обновить локальную библиотеку» несут prepared_witness_digest | ключ="b4b2_elastic_editor_6399c479…" / "b4b2_elastic_editor_8acd1d78…"
re:(?<=[0-9a-f]{64},)[0-9a-f]{64}$ | */vygruzki/ThermoGar_history.csv, */ekran/*.csv | «Запись SHA-256» истории — цепочка сумм по записи с её временем; столбец «База SHA-256» перед ней не затрагивается | …,236ec4d9…,eb6ebc98… / …,236ec4d9…,<другой>
```

## Шаг 4. Прогон 3 — BL-51

* Всем 29 файлам `app/*.py` время изменения обновлено `os.utime` на 23.09.2026 17:29:45. Содержимое то же, sha256 до и после совпали — `results/wave20_a/utime_app.txt`.
* `git status --short` после: изменений в отслеживаемых нет, кроме моего `tools/tab_snapshot_compare.py`, который тут же ушёл в коммит `5caedd1`.
* Прогон 3 — тем же кодом `tools/tab_snapshot.py`, что прогоны 1 и 2 (коммит `0620f43`).
* Сравнение 1–3 с исключениями (`results/wave20_a/sravnenie_1_3.txt`): 3913 пар, равны 3454, равны с исключениями 459, различаются 0, без пары 0 — **полное равенство**. Таблицы различий (файл, поле, было, стало) нет: различающихся полей нет.
* Отдельно, без исключений, случай BL-51 (Ni-20Cr, «Плотность по T», 100–1100 °C, поправки выкл.) — `sh_density_t_nicr_off`. Из 24 файлов байтово отличаются только `meta.json`, `sha256.txt`, `vygruzki/ThermoGar_alloys.json`, `vygruzki/ThermoGar_diagnostics.json` (время). Таблицы `session_state`, листы XLSX и CSV экрана — байт в байт. То же у `sh_density_t_nicr_on`.

**BL-51 на разрез не влияет.** Обновление mtime файлов `app/*.py` на месте не меняет ни одного числа на 130 случаях. Оговорка: в 18-А различие было между разными каталогами (снимок `git archive` против побайтной копии). Здесь каталог тот же, менялось только время файлов — как требует задание. Для разреза это и есть рабочий случай: файлы правятся на месте.

## Перечень случаев

Группы: А — `tools/test_ui_f.py` (59), Б — `tools/test_ui_g.py` (26), В — `tools/test_ui_h.py`, справочник фаз, пакет Fe–0,8C (24), Г — составы 15-Ш (21). Файлов — в каталоге прогона 1 вместе с `sha256.txt`; время и пик — прогон 1.

| группа | случай | источник | шагов | файлов | с | пик, ГиБ |
|---|---|---|---|---|---|---|
| А | `f_startup_ni` | tools/test_ui_f.py::test_startup_is_clean[ni] | 1 | 19 | 12.2 | 0.24 |
| А | `f_startup_al` | tools/test_ui_f.py::test_startup_is_clean[al] | 1 | 19 | 10.2 | 0.23 |
| А | `f_startup_fe` | tools/test_ui_f.py::test_startup_is_clean[fe] | 1 | 19 | 13.2 | 0.25 |
| А | `f_single_ni` | tools/test_ui_f.py::test_single_equilibrium[ni] | 2 | 35 | 19.9 | 0.41 |
| А | `f_single_al` | tools/test_ui_f.py::test_single_equilibrium[al] | 2 | 35 | 22.9 | 0.99 |
| А | `f_single_fe` | tools/test_ui_f.py::test_single_equilibrium[fe] | 2 | 35 | 21.9 | 0.70 |
| А | `f_tscan_ni` | tools/test_ui_f.py::test_temperature_scan[ni] | 2 | 30 | 22.4 | 0.95 |
| А | `f_tscan_al` | tools/test_ui_f.py::test_temperature_scan[al] | 2 | 30 | 39.2 | 2.64 |
| А | `f_tscan_fe` | tools/test_ui_f.py::test_temperature_scan[fe] | 2 | 30 | 42.2 | 2.06 |
| А | `f_cscan_ni` | tools/test_ui_f.py::test_concentration_scan[ni] | 4 | 30 | 28.6 | 0.98 |
| А | `f_cscan_al` | tools/test_ui_f.py::test_concentration_scan[al] | 4 | 30 | 40.3 | 1.70 |
| А | `f_cscan_fe` | tools/test_ui_f.py::test_concentration_scan[fe] | 4 | 30 | 40.8 | 1.09 |
| А | `f_solid_ni_sravn` | tools/test_ui_f.py::test_solidification[ni-Сравнить равновесное и Scheil–Gulliver] | 2 | 82 | 25.9 | 0.47 |
| А | `f_solid_ni_ravn` | tools/test_ui_f.py::test_solidification[ni-Только равновесное затвердевание] | 2 | 64 | 23.4 | 0.44 |
| А | `f_solid_ni_scheil` | tools/test_ui_f.py::test_solidification[ni-Только Scheil–Gulliver] | 2 | 64 | 23.9 | 0.45 |
| А | `f_solid_al_sravn` | tools/test_ui_f.py::test_solidification[al-Сравнить равновесное и Scheil–Gulliver] | 2 | 82 | 84.5 | 1.55 |
| А | `f_solid_al_ravn` | tools/test_ui_f.py::test_solidification[al-Только равновесное затвердевание] | 2 | 64 | 92.4 | 1.52 |
| А | `f_solid_al_scheil` | tools/test_ui_f.py::test_solidification[al-Только Scheil–Gulliver] | 2 | 64 | 95.0 | 1.52 |
| А | `f_solid_fe_sravn` | tools/test_ui_f.py::test_solidification[fe-Сравнить равновесное и Scheil–Gulliver] | 2 | 82 | 90.8 | 1.75 |
| А | `f_solid_fe_ravn` | tools/test_ui_f.py::test_solidification[fe-Только равновесное затвердевание] | 2 | 64 | 80.0 | 1.73 |
| А | `f_solid_fe_scheil` | tools/test_ui_f.py::test_solidification[fe-Только Scheil–Gulliver] | 2 | 64 | 65.6 | 1.73 |
| А | `f_energy_ni` | tools/test_ui_f.py::test_energy_curve[ni] | 2 | 31 | 13.7 | 0.32 |
| А | `f_energy_al` | tools/test_ui_f.py::test_energy_curve[al] | 2 | 32 | 13.7 | 0.41 |
| А | `f_energy_fe` | tools/test_ui_f.py::test_energy_curve[fe] | 2 | 32 | 17.8 | 0.35 |
| А | `f_driving_ni` | tools/test_ui_f.py::test_driving_force[ni] | 2 | 28 | 17.3 | 0.43 |
| А | `f_driving_al` | tools/test_ui_f.py::test_driving_force[al] | 2 | 28 | 21.4 | 1.03 |
| А | `f_driving_fe` | tools/test_ui_f.py::test_driving_force[fe] | 2 | 29 | 25.5 | 0.68 |
| А | `f_tzero_ni` | tools/test_ui_f.py::test_tzero_in_narrow_window[ni] | 2 | 26 | 21.4 | 0.30 |
| А | `f_tzero_al` | tools/test_ui_f.py::test_tzero_in_narrow_window[al] | 2 | 26 | 18.4 | 0.29 |
| А | `f_tzero_fe` | tools/test_ui_f.py::test_tzero_in_narrow_window[fe] | 2 | 26 | 59.2 | 0.32 |
| А | `f_density_ni` | tools/test_ui_f.py::test_density_single[ni] | 2 | 25 | 28.6 | 0.41 |
| А | `f_density_al` | tools/test_ui_f.py::test_density_single[al] | 2 | 25 | 31.7 | 0.99 |
| А | `f_density_fe` | tools/test_ui_f.py::test_density_single[fe] | 2 | 25 | 39.9 | 0.72 |
| А | `f_density_warning_ni` | tools/test_ui_f.py::test_density_estimated_warning_is_shown_to_user | 2 | 25 | 71.0 | 1.75 |
| А | `f_density_t_ni` | tools/test_ui_f.py::test_density_temperature_scan[ni] | 2 | 24 | 23.5 | 0.44 |
| А | `f_density_t_al` | tools/test_ui_f.py::test_density_temperature_scan[al] | 2 | 24 | 52.2 | 2.58 |
| А | `f_density_t_fe` | tools/test_ui_f.py::test_density_temperature_scan[fe] | 2 | 24 | 39.7 | 1.34 |
| А | `f_elastic_ni` | tools/test_ui_f.py::test_elastic_vrh[ni] | 3 | 25 | 20.8 | 0.43 |
| А | `f_elastic_al` | tools/test_ui_f.py::test_elastic_vrh[al] | 3 | 25 | 23.4 | 0.99 |
| А | `f_elastic_fe` | tools/test_ui_f.py::test_elastic_vrh[fe] | 3 | 25 | 34.7 | 0.73 |
| А | `f_strength_ni` | tools/test_ui_f.py::test_strengthening[ni] | 2 | 23 | 13.2 | 0.25 |
| А | `f_strength_al` | tools/test_ui_f.py::test_strengthening[al] | 2 | 23 | 10.7 | 0.24 |
| А | `f_strength_fe` | tools/test_ui_f.py::test_strengthening[fe] | 2 | 23 | 16.3 | 0.26 |
| А | `f_binary_ni` | tools/test_ui_f.py::test_binary_diagram[ni] | 2 | 26 | 33.6 | 0.42 |
| А | `f_binary_al` | tools/test_ui_f.py::test_binary_diagram[al] | 2 | 26 | 54.1 | 1.19 |
| А | `f_binary_fe` | tools/test_ui_f.py::test_binary_diagram[fe] | 2 | 26 | 44.9 | 0.96 |
| А | `f_isopleth_ni` | tools/test_ui_f.py::test_isopleth_diagram[ni] | 2 | 26 | 102.6 | 1.28 |
| А | `f_isopleth_al` | tools/test_ui_f.py::test_isopleth_diagram[al] | 2 | 26 | 230.3 | 1.92 |
| А | `f_isopleth_fe` | tools/test_ui_f.py::test_isopleth_diagram[fe] | 2 | 26 | 84.0 | 1.50 |
| А | `f_ternary_ni` | tools/test_ui_f.py::test_ternary_diagram[ni] | 2 | 26 | 52.0 | 0.80 |
| А | `f_ternary_al` | tools/test_ui_f.py::test_ternary_diagram[al] | 2 | 26 | 139.2 | 1.59 |
| А | `f_ternary_fe` | tools/test_ui_f.py::test_ternary_diagram[fe] | 2 | 26 | 55.1 | 0.92 |
| А | `f_tmap_ni` | tools/test_ui_f.py::test_ternary_phase_map[ni] | 2 | 30 | 33.2 | 1.37 |
| А | `f_tmap_al` | tools/test_ui_f.py::test_ternary_phase_map[al] | 2 | 30 | 87.4 | 3.09 |
| А | `f_tmap_fe` | tools/test_ui_f.py::test_ternary_phase_map[fe] | 2 | 30 | 57.7 | 2.90 |
| А | `f_phasemap3_ni` | tools/test_ui_f.py::test_phase_map_needs_three_elements[ni] | 1 | 19 | 13.8 | 0.24 |
| А | `f_phasemap3_al` | tools/test_ui_f.py::test_phase_map_needs_three_elements[al] | 1 | 19 | 11.2 | 0.23 |
| А | `f_phasemap3_fe` | tools/test_ui_f.py::test_phase_map_needs_three_elements[fe] | 1 | 19 | 15.8 | 0.25 |
| А | `f_db_change` | tools/test_ui_f.py::test_results_do_not_survive_a_database_change | 3 | 35 | 32.6 | 0.44 |
| Б | `g_render_ni` | tools/test_ui_g.py::test_kinetics_section_renders[ni] | 1 | 19 | 12.7 | 0.24 |
| Б | `g_render_al` | tools/test_ui_g.py::test_kinetics_section_renders[al] | 1 | 19 | 10.2 | 0.23 |
| Б | `g_render_fe` | tools/test_ui_g.py::test_kinetics_section_renders[fe] | 1 | 19 | 13.7 | 0.25 |
| Б | `g_run_gate` | tools/test_ui_g.py::test_run_gate_is_identical_for_all_databases | 3 | 33 | 28.5 | 0.28 |
| Б | `g_single_ni` | tools/test_ui_g.py::test_diffusion_single_phase[ni] | 4 | 35 | 25.5 | 0.30 |
| Б | `g_single_al` | tools/test_ui_g.py::test_diffusion_single_phase[al] | 4 | 35 | 21.4 | 0.29 |
| Б | `g_single_fe` | tools/test_ui_g.py::test_diffusion_single_phase[fe] | 4 | 35 | 30.6 | 0.33 |
| Б | `g_hom_ni` | tools/test_ui_g.py::test_diffusion_homogenization[ni] | 4 | 35 | 28.6 | 0.33 |
| Б | `g_hom_fe` | tools/test_ui_g.py::test_diffusion_homogenization[fe] | 4 | 35 | 31.1 | 0.34 |
| Б | `g_hom_al` | tools/test_ui_g.py::test_homogenization_unavailable_on_al_is_explained | 2 | 19 | 11.2 | 0.25 |
| Б | `g_kwn_ni` | tools/test_ui_g.py::test_kwn_precipitation[ni] | 3 | 66 | 34.6 | 0.37 |
| Б | `g_kwn_al` | tools/test_ui_g.py::test_kwn_precipitation[al] | 3 | 66 | 24.9 | 0.40 |
| Б | `g_kwn_fe` | tools/test_ui_g.py::test_kwn_precipitation[fe] | 3 | 66 | 82.5 | 0.41 |
| Б | `g_kwn_fe_provenance` | tools/test_ui_g.py::test_fe_kwn_provenance_status_is_neutral | 3 | 66 | 80.6 | 0.43 |
| Б | `g_kwn_matrix_al` | tools/test_ui_g.py::test_kwn_matrix_offers_the_disordered_half[al] | 1 | 19 | 11.2 | 0.23 |
| Б | `g_kwn_matrix_fe` | tools/test_ui_g.py::test_kwn_matrix_offers_the_disordered_half[fe] | 1 | 19 | 15.3 | 0.25 |
| Б | `g_kwn_too_long` | tools/test_ui_g.py::test_kwn_reports_a_too_long_composition_without_a_traceback | 1 | 19 | 14.8 | 0.25 |
| Б | `g_kwn_eight` | tools/test_ui_g.py::test_kwn_accepts_the_eight_solute_steel_since_bl21 | 1 | 19 | 14.8 | 0.25 |
| Б | `g_bounded_kin_single` | tools/test_ui_g.py::test_diffusion_number_inputs_are_bounded[kin_single] | 1 | 19 | 13.3 | 0.24 |
| Б | `g_bounded_kin_hom` | tools/test_ui_g.py::test_diffusion_number_inputs_are_bounded[kin_hom] | 1 | 19 | 13.3 | 0.24 |
| Б | `g_bad_couple_1` | tools/test_ui_g.py::test_bad_couple_composition_is_reported | 3 | 19 | 15.8 | 0.25 |
| Б | `g_bad_couple_2` | tools/test_ui_g.py::test_bad_couple_composition_is_reported | 3 | 19 | 15.8 | 0.26 |
| Б | `g_bad_couple_3` | tools/test_ui_g.py::test_bad_couple_composition_is_reported | 3 | 19 | 15.8 | 0.25 |
| Б | `g_kwn_grid` | tools/test_ui_g.py::test_kwn_size_grid_is_validated | 3 | 20 | 26.0 | 0.26 |
| Б | `g_ni_kwn_hour` | tools/test_ui_g.py::test_ni_kwn_reaches_a_precipitated_state | 3 | 66 | 90.7 | 0.40 |
| Б | `g_fe_defaults` | tools/test_ui_g.py::test_fe_shipped_defaults_are_the_declared_ones | 1 | 19 | 14.8 | 0.25 |
| В | `h_library_ni` | tools/test_ui_h.py::test_library_save_appears_in_the_list_and_loads_back[ni] | 9 | 32 | 40.3 | 0.30 |
| В | `h_library_al` | tools/test_ui_h.py::test_library_save_appears_in_the_list_and_loads_back[al] | 9 | 33 | 44.4 | 0.30 |
| В | `h_library_fe` | tools/test_ui_h.py::test_library_save_appears_in_the_list_and_loads_back[fe] | 9 | 27 | 45.4 | 0.31 |
| В | `h_library_roundtrip` | tools/test_ui_h.py::test_library_export_and_import_round_trip | 5 | 21 | 39.9 | 0.31 |
| В | `h_project_ni` | tools/test_ui_h.py::test_project_saves_fourteen_keys_and_restores_state[ni] | 6 | 28 | 37.8 | 0.29 |
| В | `h_project_al` | tools/test_ui_h.py::test_project_saves_fourteen_keys_and_restores_state[al] | 6 | 28 | 35.8 | 0.29 |
| В | `h_project_fe` | tools/test_ui_h.py::test_project_saves_fourteen_keys_and_restores_state[fe] | 6 | 22 | 33.2 | 0.30 |
| В | `h_project_export` | tools/test_ui_h.py::test_project_export_is_portable_and_imports_back | 8 | 22 | 45.4 | 0.31 |
| В | `h_confirmations` | tools/test_ui_h.py::test_confirmations_survive_the_rerun_and_stay_in_their_own_section | 3 | 22 | 23.0 | 0.28 |
| В | `h_history` | tools/test_ui_h.py::test_history_records_events_exports_csv_and_clears | 7 | 22 | 34.2 | 0.30 |
| В | `h_batch_comma` | tools/test_ui_h.py::test_batch_accepts_both_separators_and_both_encodings[comma] | 2 | 20 | 17.8 | 0.26 |
| В | `h_batch_semicolon` | tools/test_ui_h.py::test_batch_accepts_both_separators_and_both_encodings[semicolon] | 2 | 20 | 14.7 | 0.26 |
| В | `h_batch_comma_bom` | tools/test_ui_h.py::test_batch_accepts_both_separators_and_both_encodings[comma_bom] | 2 | 20 | 15.8 | 0.26 |
| В | `h_batch_semicolon_bom` | tools/test_ui_h.py::test_batch_accepts_both_separators_and_both_encodings[semicolon_bom] | 2 | 20 | 14.8 | 0.26 |
| В | `h_batch_junk` | tools/test_ui_h.py::test_batch_rejects_a_junk_file_with_a_readable_message | 2 | 19 | 14.2 | 0.26 |
| В | `h_batch_template` | tools/test_ui_h.py::test_batch_template_downloads_open_as_excel_and_csv | 3 | 22 | 15.8 | 0.28 |
| В | `h_batch_summary` | tools/test_ui_h.py::test_batch_summary_has_no_receipt_columns | 3 | 26 | 24.4 | 0.42 |
| В | `h_batch_three` | tools/test_ui_h.py::test_batch_calculates_three_databases_and_exports_excel | 4 | 32 | 43.2 | 1.41 |
| В | `h_batch_c15` | tools/test_ui_h.py::test_batch_rejects_c15_for_steel_before_any_calculation | 2 | 19 | 17.3 | 0.26 |
| В | `h_first_run` | tools/test_ui_h.py::test_first_run_creates_the_profile_and_writes_nothing_into_the_program | 1 | 19 | 15.3 | 0.25 |
| В | `h_phase_reference_ni` | справочник фаз | 2 | 20 | 14.8 | 0.26 |
| В | `h_phase_reference_al` | справочник фаз | 2 | 20 | 12.8 | 0.24 |
| В | `h_phase_reference_fe` | справочник фаз | 2 | 20 | 17.3 | 0.26 |
| В | `h_batch_fe08` | results/wave19_d/priemka.py::case_batch (через экран) | 4 | 33 | 35.2 | 0.84 |
| Г | `sh_density_nicr_on` | results/wave15_sh/scripts/density_run.py | 2 | 25 | 25.5 | 0.43 |
| Г | `sh_density_t_nicr_on` | results/wave15_sh/scripts/density_run.py (скан) | 2 | 24 | 31.6 | 1.09 |
| Г | `sh_elastic_nicr_on` | results/wave15_f/scripts/elastic_run.py | 3 | 25 | 22.9 | 0.45 |
| Г | `sh_density_nicr_off` | results/wave15_sh/scripts/density_run.py | 2 | 25 | 19.8 | 0.43 |
| Г | `sh_density_t_nicr_off` | results/wave15_sh/scripts/density_run.py (скан) | 2 | 24 | 29.5 | 1.09 |
| Г | `sh_elastic_nicr_off` | results/wave15_f/scripts/elastic_run.py | 3 | 25 | 20.3 | 0.45 |
| Г | `sh_density_nialcr_on` | results/wave15_sh/scripts/density_run.py | 2 | 25 | 19.8 | 0.49 |
| Г | `sh_density_t_nialcr_on` | results/wave15_sh/scripts/density_run.py (скан) | 2 | 24 | 37.7 | 2.41 |
| Г | `sh_elastic_nialcr_on` | results/wave15_f/scripts/elastic_run.py | 3 | 25 | 23.4 | 0.51 |
| Г | `sh_density_nialcr_off` | results/wave15_sh/scripts/density_run.py | 2 | 25 | 21.9 | 0.49 |
| Г | `sh_density_t_nialcr_off` | results/wave15_sh/scripts/density_run.py (скан) | 2 | 24 | 37.2 | 2.41 |
| Г | `sh_elastic_nialcr_off` | results/wave15_f/scripts/elastic_run.py | 3 | 25 | 22.9 | 0.51 |
| Г | `sh_density_fecrc_on` | results/wave15_sh/scripts/density_run.py | 2 | 25 | 25.4 | 0.61 |
| Г | `sh_density_t_fecrc_on` | results/wave15_sh/scripts/density_run.py (скан) | 2 | 24 | 59.1 | 2.88 |
| Г | `sh_elastic_fecrc_on` | results/wave15_f/scripts/elastic_run.py | 3 | 25 | 27.5 | 0.63 |
| Г | `sh_density_fecrc_off` | results/wave15_sh/scripts/density_run.py | 2 | 25 | 27.5 | 0.61 |
| Г | `sh_density_t_fecrc_off` | results/wave15_sh/scripts/density_run.py (скан) | 2 | 24 | 61.6 | 2.88 |
| Г | `sh_elastic_fecrc_off` | results/wave15_f/scripts/elastic_run.py | 3 | 25 | 29.0 | 0.63 |
| Г | `sh_solid_nicr` | results/wave18_v/run_case.py::nicr | 2 | 82 | 28.0 | 0.49 |
| Г | `sh_solid_nialcr` | results/wave18_v/run_case.py::nialcr | 2 | 82 | 34.1 | 0.61 |
| Г | `sh_solid_fecrc` | results/wave18_v/run_case.py::fecrc | 2 | 82 | 53.9 | 1.44 |
Итого 130 случаев, 4043 файла в `run1` (3913 + 130 `sha256.txt`).

## Шаг 6. Что где лежит

* Каталоги на диске: `results/wave20_a/run1` 92 МБ, `run2` 92 МБ, `run3` 92 МБ, `state` 1,1 ГБ (после трёх прогонов), журналы `run{1,2,3}_logs`. Вместе больше 50 МБ, в git не положены.
* `results/wave20_a/etalon_run1.zip` — `run1` целиком: 4043 файла, 24,8 МиБ, sha256 `3f2f1eec160ab5195c06af7cbdd8c7c2742a8d142dd4504a95ebe1eb0083b26c`. Даты внутри архива фиксированы (1980-01-01). Распакован в scratchpad и сверен с `run1` инструментом: 3913 из 3913 равны байт в байт. В git.
* Эталон на диске — `D:\Pets\ThermoGar\results\wave20_a\run1\`.
* Также в git: `sha256.txt` всех 130 случаев трёх прогонов (`run{1,2,3}/*/sha256.txt`), `isklyucheniya.txt`, `sravnenie_1_2_syroe.txt`, `sravnenie_1_2.txt`, `sravnenie_1_3.txt`, `run{1,2,3}_time.csv`, `run{1,2,3}_stdout.txt`, `run{1,2,3}_start.txt`/`_end.txt`, `prognoz_run1.txt`, `utime_app.txt`.

## Как снять эталон и сравнить на следующем шаге разреза

1. На ветке шага, из корня: `.venv-windows\Scripts\python.exe -B -X utf8 tools\tab_snapshot.py run --out results\<волна>\posle --state results\<волна>\state\posle --time-csv results\<волна>\posle_time.csv` (~65–76 мин, пик ~3,1 ГиБ, порог входа 3,0 ГиБ).
2. Эталон: `results\wave20_a\run1\` на диске или распаковка `results\wave20_a\etalon_run1.zip` в `results\<волна>\` (даёт `run1\`).
3. Сверка: `.venv-windows\Scripts\python.exe -B -X utf8 tools\tab_snapshot_compare.py results\wave20_a\run1 results\<волна>\posle --isklyucheniya results\wave20_a\isklyucheniya.txt --otchet results\<волна>\sravnenie.txt`.
4. Приёмка шага — код выхода 0 и строка «ИТОГ: полное равенство». Любое «различаются» или «нет пары» разбирается по строкам отчёта.
5. Исключения не расширять без разбора по исходнику. Число правил в шапке отчёта должно остаться 13. Каталог вывода не перезаписывается — для повтора нужен новый каталог.

## Отступления от задания

1. **«Затвердевание»: три метода, а не два.** Задание говорит «оба метода», а `test_ui_f.py::test_solidification` параметризован тремя: «Сравнить…», «Только равновесное», «Только Scheil–Gulliver». Взяты все три — по правилу «все сценарии test_ui_f».
2. **Б — все сценарии `test_ui_g` через AppTest (26 случаев), а не только 3 × 3.** Кроме девяти ячеек (пара, гомогенизация — на Al это случай с выключенной кнопкой и объяснением, KWN) взяты отрисовка, ворота запуска, матрица KWN, длинный состав, восемь добавок, границы полей, неверные пары, сетка радиусов, KWN Ni 1 ч, Fe KWN на 30 классах, умолчания Fe. Не взяты 6 вариантов `test_absurd_diffusion_values_raise_a_readable_message`: они вызывают `run_diffusion` напрямую, экрана нет.
3. **В — не взяты 6 функциональных тестов `test_ui_h`** (`test_widget_state_*` ×3, `test_portable_project_drops_the_settings_only`, `test_rejections_are_plain_language_not_reason_codes`, `test_quick_examples_cover_three_databases_and_carry_a_steel`): приложение в них не запускается.
4. **`h_first_run` без `THERMOGAR_STATE_ROOT`.** Сценарий проверяет первый запуск в `%LOCALAPPDATA%`, поэтому `LOCALAPPDATA` указывает на `results\wave20_a\state\<прогон>\h_first_run\LocalAppData`, а `THERMOGAR_STATE_ROOT` снят. Папка всё равно под `state\<прогон>\<случай>`; настоящий `%LOCALAPPDATA%\ThermoGar` не тронут.
5. **Пакет Fe–0,8C — через экран, а не через функции.** Файл из 4 строк с `TEMPLATE_HEADERS`, как в 19-Д; затем «Файл составов», расчёт, подготовка выгрузки. Числа совпали с 19-Д (см. выше).
6. **Г — упругость Ni–9,8Al–8,3Cr.** В `results/wave15_f/scripts/elastic_run.py` такого случая нет, и единицы там зашиты «массовые %». Взяты состав и 800 °C из `density_run.py` (ат. %), модули редактора — как в `elastic_run.py` (100/300 ГПа по порядку фаз, ν = 0,25). «Плотность по T» на всех трёх составах — скан 100–1100 °C шаг 100 (в `density_run.py` скан был только у `nicr`).
7. **Пул из двух воркеров — во всех случаях,** включая группы Б, В, Г. В `test_ui_g` и `test_ui_h` такой фикстуры нет; задание требует пул «как в test_ui_f».
8. **Порог памяти.** Каждый случай — свой процесс, то есть slow-сценарии идут «по одной». Порог входа 3,0 ГиБ одинаков для всех. Пик прогона 3,12 ГиБ, свободной меньше 3,46 не бывало.
9. **Формат сравнения расширен правилом `путь:`.** Код ошибки (время + случайные hex) стоит в имени файла отчёта об ошибке. Правило маскирует это поле в имени, чтобы поставить файлы в пару; содержимое сравнивается с исключениями полей. Файл целиком не исключён.
10. **`sha256.txt` попарно не сравнивается.** Вместо этого каждая сторона проверяется на целостность — суммы сходятся с файлами. Иначе любое исключённое поле давало бы различие в строке суммы.
11. **Пилот до эталона.** До прогона 1 инструмент дважды прогнан на 11 случаях в scratchpad (вне дерева). По итогам исправлено: имена таблиц экрана — порядковые, а не по хэшу (метка времени в таблице меняла имя файла, поле нельзя было исключить); из `vygruzki.txt` и состава архивов убраны байты, размеры и CRC (в XLSX дата). Эталон снят исправленным кодом (`0620f43`), тем же сняты прогоны 2 и 3.
12. **Мой байткод.** `py_compile` для проверки `tab_snapshot_compare.py` создал `tools/__pycache__/tab_snapshot_compare.cpython-311.pyc` (флаг `-B` на `py_compile` не действует). Перенесён в `_to_delete/20a_pycache/` с описью `opis_sha256.txt`. После трёх прогонов `__pycache__` и `*.pyc` в `app`, `tools`, `configs`, `packaging` нет.
13. **Границы эталона.** Не снимаются: PNG картинок на экране (в `karkas.txt` — адрес media, это хэш PNG; байты PNG — в выгрузках), данные `st.line_chart`, переходные элементы (спиннер, прогресс). Значения редактора `st.data_editor` подставляются подменой, как в тестах.

## git

`git ls-remote origin wave20-a`, `git log --oneline 5ed5d88..wave20-a` и `git status --short` — ниже, после пуша.
