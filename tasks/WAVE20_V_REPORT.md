# 20-В — отчёт: BL-57, шаг 0 заново, эталон вкладок на коде 0.5.0

Задание — `tasks/WAVE20_V_OPUS.md`. Ветка `wave20-v` от `origin/main` (`620d88e`). Дерево `D:\Pets\ThermoGar-w21b`, интерпретатор `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe`, ноутбук Windows 10. Код приложения не менялся.

**Итог.** 130 случаев (А 59, Б 26, В 24, Г 21), 4036 файлов на прогон (+130 `sha256.txt`). Прогоны 1–2: 3573 файла равны байт в байт, 463 равны с исключениями, различий 0, без пары 0 — полное равенство. Правил 13 — правила 20-А, новых нет.

## Время по шагам

| шаг | начало | конец | что |
|---|---|---|---|
| 0 | 11:54:15 | 11:55:20 | проверки, ветка, `WAVE20_V_OPUS.md` (`9f9674b`) |
| 1 | 11:55:27 | 12:02:27 | `list`, пилот (упал), правка (`40485e6`), пилот 2 |
| 2 | 12:03:13 | 13:59:17 | прогоны 1 и 2, сводки |
| 3 | 13:59:17 | 14:00:20 | сверка без исключений и с исключениями |
| 4 | 13:02:30 | 14:01:10 | `run1_sha256.txt`, архив и его сверка (во время прогона 2), `run2_sha256.txt`, коммит `4aa71c8` |
| 5 | 13:04 | 14:01:28 | реестр: правки (а), (б), (в), (д) — во время прогона 2, (г) — после сверки; коммит `84137d7` |
| 6 | 14:02 | см. раздел git | отчёт, пуш |

Все времена — 28.09.2026, по часам ноутбука.

## Шаг 0

* `git status --short` на входе — ровно `?? _to_delete/`. HEAD был отсоединён на `620d88e`.
* `git ls-remote origin main "refs/tags/v0.5.0*"`:

```
620d88eac942d59e0716a28d46aa164d12b8e500	refs/heads/main
eb9bd45eea552c8cbe7e0e8972a02e145e1062db	refs/tags/v0.5.0
077e7323931fbf9a60c52a64c405a24f6c935185	refs/tags/v0.5.0^{}
```

  Совпадает с заданием.
* `git diff --stat v0.5.0 origin/main -- app .streamlit databases configs packaging tools licenses` — пусто.
* `app\__pycache__` и `tools\__pycache__` на входе отсутствовали, переносить было нечего. После всех прогонов их тоже нет, `*.pyc` в `app`, `tools`, `configs`, `packaging` — 0.
* Свободная память на входе — 6,81 ГиБ из 15,71 ГиБ.

## Шаг 1. Пилот и правка инструмента

* `tools\tab_snapshot.py list` — 130 случаев: А 59, Б 26, В 24, Г 21. Как в 20-А.
* Пилот (`results\validation\wave20_v\pilot`, 11:55:33–11:57:51): все 12 случаев — код 1. В журнале у каждого `"ошибка": "TypeError: Object of type Option is not JSON serializable"`, `"исключений_на_экране": 0`.
* Разбор. Ошибка в инструменте, а не в приложении. Переключатель вида `st.segmented_control` (21-И) в AppTest — элемент `button_group`. Его поле `options` в Streamlit 1.62.0 — сообщения `ButtonGroup.Option` (поля `content`, `content_icon`), а не строки. Инструмент писал `json.dumps(list(proto.options))` — строка `tools/tab_snapshot.py:233` на `620d88e`. Такой переключатель есть на стартовом экране («Кинетика», «Затвердевание»), поэтому падали все случаи. Правка 21-Р добавила только выбор вида (`select_view`) и на коде 0.5.0 не прогонялась.
* Правка (`40485e6`, `tools/tab_snapshot.py:232–235`): у `button_group` в «варианты» пишется `option.content`, у остальных видов — как было. Что снимается и какие входы — не менялось.
* Пилот 2 (`pilot2`, 11:58:28–12:02:27): 12 из 12 — код 0, `"ошибка": null`, `"исключений_на_экране": 0`. Проверка по месту: в `karkas.txt` переключатели пишутся как `button_group | … | варианты=["Однофазная пара", "Многофазная гомогенизация", …]`. Ключи результата в `session_state` есть у равновесия, упругости, диффузии, пакета. Упрочнение Al — «Итог, МПа» 49.623. У затвердевания и KWN выгрузки появляются на шаге после выбора вида.

## Шаг 2. Прогоны

Оба прогона — кодом `40485e6` (последняя правка `tools/tab_snapshot.py`).

| прогон | начало | конец | сумма случаев, мин | А | Б | В | Г | пик дерева, ГиБ | мин. свободно, ГиБ | ждал памяти |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 (эталон) | 12:03:13 | 13:01:53 | 58,6 | 32,5 | 8,9 | 7,8 | 9,5 | 3,12 (`f_tmap_al`) | 3,95 | 0 с |
| 2 (повтор) | 13:02:14 | 13:59:02 | 56,8 | 32,0 | 8,8 | 7,3 | 8,7 | 3,13 (`f_tmap_al`) | 4,44 | 0 с |

* Все 260 запусков случаев — код 0, `"ошибка": null`, `"исключений_на_экране": 0` — `results/wave20_v/run{1,2}_svodka.txt`.
* Сверка с 20-А: 76,1 и 65,7 мин, пик 3,09 и 3,12 ГиБ. Сейчас на 17,5 и 8,9 мин быстрее, пик тот же. Быстрее прежде всего медленные случаи: `f_isopleth_al` 184 с против 230, `f_ternary_al` 107 против 139, `g_kwn_fe` 69 против 82,5, `f_tmap_al` 57 против 87.
* **Прогноз после первых пяти случаев прогона 1.** Первые пять (`f_startup_ni`, `f_startup_al`, `f_startup_fe`, `f_single_ni`, `f_single_al`) — 68,2 с против 78,4 с тех же случаев в прогоне 1 20-А, множитель 0,87. 76,1 × 0,87 ≈ 66 мин, конец около 13:10. Факт — 58,6 мин, конец 13:01:53. Промах −7 мин: медленные диаграммы ускорились сильнее, чем стартовые случаи.

## Шаг 3. Сверка 1–2

* Без исключений (`results/wave20_v/sravnenie_1_2_syroe.txt`): 4038 путей, равны 3573, различаются 461, без пары 4. Без пары — отчёты об ошибке с кодом ошибки в имени: `g_kwn_grid` и `g_kwn_too_long`, по одному на сторону.
* Различаются по видам файлов: `meta.json` 130, `vygruzki/ThermoGar_alloys.json` 130, `vygruzki/ThermoGar_diagnostics.json` 130, `sostoyanie/app.json` 34, `karkas.txt` 20, `ekran/t*.csv` 6, `vygruzki/Проект_H.thermogar.json` 5, `sostoyanie/app2.json` 3, `vygruzki.txt` 2, `vygruzki/ThermoGar_history.csv` 1.
* Все различия покрыты 13 правилами 20-А. Это время, папка состояния прогона, код ошибки, случайные id, digest-поля от часов и цепочка сумм истории. Различий в числах результата, таблицах, PNG, `texts.txt` и порядке элементов `karkas.txt` нет. Новых правил не понадобилось.
* С исключениями (`results/wave20_v/sravnenie_1_2.txt`, код выхода 0): 4036 пар, равны 3573, равны с исключениями 463, различаются 0, без пары 0. Нарушений целостности `sha256.txt` A 0, B 0 — **«ИТОГ: полное равенство»**.
* Все 13 правил сработали. Число файлов по номерам правил (в скобках — 20-А):

| правило | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| файлов | 418 (416) | 130 (130) | 143 (143) | 8 (4) | 2 (1) | 135 (135) | 3 (3) | 3 (3) | 3 (3) | 27 (27) | 9 (9) | 18 (18) | 1 (2) |

* Отличия от 20-А:
  * правила 4 и 5 — код ошибки теперь несёт и `g_kwn_too_long`: 4 файла против 0. Длинный состав KWN даёт сообщение с «Кодом ошибки» и отчёт об ошибке, как `g_kwn_grid`;
  * правило 13 — 1 файл (`h_history/vygruzki/ThermoGar_history.csv`). Таблица истории на экране (`h_history/ekran/*.csv`) сошлась без правила 13.

### `results/wave20_v/isklyucheniya.txt` целиком

```
# 20-В: правила 20-А; новые — ниже, с разбором
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

Новых правил нет — ниже шапки ничего не добавлено. Адреса `файл:строка` в правилах 20-А указывают на код 23.09 и после волны 21 могли сдвинуться. Сами правила сверены по факту: каждое сработало, различий без правила нет.

## Шаг 4. Что где лежит

В git (`results/wave20_v/`, коммит `4aa71c8`):

| файл | байт |
|---|---|
| `etalon_run1.zip` | 26 888 447 (25,6 МиБ) |
| `run1_sha256.txt`, `run2_sha256.txt` | 476 174 каждый, по 4036 строк |
| `sravnenie_1_2_syroe.txt` | 571 886 |
| `sravnenie_1_2.txt` | 293 412 |
| `run1_stdout.txt` / `run2_stdout.txt` | 11 417 / 11 416 |
| `run1_time.csv` / `run2_time.csv` | 10 571 / 10 570 |
| `run1_svodka.txt` / `run2_svodka.txt` | 4 861 / 4 860 |
| `isklyucheniya.txt` | 4 962 |

* `etalon_run1.zip` — каталог `run1` целиком, внутри папка `run1/`: 4166 членов (4036 + 130 `sha256.txt`). Собран Python `zipfile` (DEFLATE), члены по алфавиту, даты членов 1980-01-01. sha256 `d4157fc722d1bdca63ad54c7a57f30ce25dc5045648551a3727890aaad2e62d4`. Архив распакован во временную папку сессии и сверен с `run1` инструментом без исключений: 4036 из 4036 равны, нарушений целостности 0 — полное равенство.
* `run<N>_sha256.txt` — строки `<случай>/<путь> <sha256>` из `sha256.txt` всех случаев, по алфавиту.
* Вне git, `D:\Pets\ThermoGar-w21b\results\validation\wave20_v\` (под `.gitignore`, правило `results/validation/`):
  * `run1` — 96 МБ, эталон;
  * `run2` — 96 МБ;
  * `state` — 745 МБ: `pilot`, `pilot2`, `run1`, `run2`;
  * `run1_logs`, `run2_logs` — по 8,1 МБ;
  * `pilot` — 2,3 МБ, неудачный первый пилот, оставлен как есть;
  * `pilot2` — 8,7 МБ;
  * `pilot_logs` — 43 КБ;
  * `pilot2_logs` — 534 КБ;
  * `pilot_time.csv`, `pilot2_time.csv`, `run{1,2}_start.txt`, `run{1,2}_end.txt`.

Эталон 0.5.0 против эталона 20-А — на 123 файла больше на прогон:

* +62 таблицы экрана (`ekran/t*.csv`: 113 новых имён, 51 ушло);
* +60 CSV в `sostoyanie/app/` — аргументы построения графиков, которые приложение теперь держит в `session_state` (`*.figure.args.0.csv`, `solidification_result.figure_cache.*`, `*.phase_chart.args.0.csv`, `thermogar_precipitation_result.figures.*`);
* +1 отчёт об ошибке (`g_kwn_too_long`).

Это следствие волны 21, а не инструмента: инструмент снимает то же, что в 20-А.

## Перечень случаев

Группы: А — `tools/test_ui_f.py` (59), Б — `tools/test_ui_g.py` (26), В — `tools/test_ui_h.py`, справочник фаз, пакет Fe–0,8C (24), Г — составы 15-Ш (21). Файлов — в каталоге прогона 1 вместе с `sha256.txt`, время и пик — прогон 1. Шагов больше, чем в 20-А, у случаев с выбором вида (затвердевание, гомогенизация, KWN): выбор вида — отдельный шаг (21-Р).

| группа | случай | источник | шагов | файлов | с | пик, ГиБ |
|---|---|---|---|---|---|---|
| А | `f_startup_ni` | tools/test_ui_f.py::test_startup_is_clean[ni] | 1 | 20 | 10.2 | 0.24 |
| А | `f_startup_al` | tools/test_ui_f.py::test_startup_is_clean[al] | 1 | 20 | 8.7 | 0.23 |
| А | `f_startup_fe` | tools/test_ui_f.py::test_startup_is_clean[fe] | 1 | 20 | 12.7 | 0.25 |
| А | `f_single_ni` | tools/test_ui_f.py::test_single_equilibrium[ni] | 2 | 36 | 17.3 | 0.41 |
| А | `f_single_al` | tools/test_ui_f.py::test_single_equilibrium[al] | 2 | 36 | 19.3 | 0.99 |
| А | `f_single_fe` | tools/test_ui_f.py::test_single_equilibrium[fe] | 2 | 36 | 18.8 | 0.70 |
| А | `f_tscan_ni` | tools/test_ui_f.py::test_temperature_scan[ni] | 2 | 32 | 18.8 | 0.97 |
| А | `f_tscan_al` | tools/test_ui_f.py::test_temperature_scan[al] | 2 | 32 | 33.0 | 2.63 |
| А | `f_tscan_fe` | tools/test_ui_f.py::test_temperature_scan[fe] | 2 | 32 | 34.5 | 2.06 |
| А | `f_cscan_ni` | tools/test_ui_f.py::test_concentration_scan[ni] | 4 | 32 | 20.8 | 0.99 |
| А | `f_cscan_al` | tools/test_ui_f.py::test_concentration_scan[al] | 4 | 32 | 25.9 | 1.72 |
| А | `f_cscan_fe` | tools/test_ui_f.py::test_concentration_scan[fe] | 4 | 32 | 29.0 | 1.10 |
| А | `f_solid_ni_sravn` | tools/test_ui_f.py::test_solidification[ni-Сравнить равновесное и Scheil–Gulliver] | 3 | 81 | 22.9 | 0.49 |
| А | `f_solid_ni_ravn` | tools/test_ui_f.py::test_solidification[ni-Только равновесное затвердевание] | 3 | 62 | 20.8 | 0.46 |
| А | `f_solid_ni_scheil` | tools/test_ui_f.py::test_solidification[ni-Только Scheil–Gulliver] | 3 | 62 | 21.8 | 0.47 |
| А | `f_solid_al_sravn` | tools/test_ui_f.py::test_solidification[al-Сравнить равновесное и Scheil–Gulliver] | 3 | 81 | 74.7 | 1.55 |
| А | `f_solid_al_ravn` | tools/test_ui_f.py::test_solidification[al-Только равновесное затвердевание] | 3 | 62 | 72.3 | 1.53 |
| А | `f_solid_al_scheil` | tools/test_ui_f.py::test_solidification[al-Только Scheil–Gulliver] | 3 | 62 | 79.6 | 1.53 |
| А | `f_solid_fe_sravn` | tools/test_ui_f.py::test_solidification[fe-Сравнить равновесное и Scheil–Gulliver] | 3 | 81 | 73.5 | 1.76 |
| А | `f_solid_fe_ravn` | tools/test_ui_f.py::test_solidification[fe-Только равновесное затвердевание] | 3 | 62 | 66.9 | 1.74 |
| А | `f_solid_fe_scheil` | tools/test_ui_f.py::test_solidification[fe-Только Scheil–Gulliver] | 3 | 62 | 67.3 | 1.74 |
| А | `f_energy_ni` | tools/test_ui_f.py::test_energy_curve[ni] | 2 | 33 | 12.7 | 0.32 |
| А | `f_energy_al` | tools/test_ui_f.py::test_energy_curve[al] | 2 | 34 | 12.2 | 0.41 |
| А | `f_energy_fe` | tools/test_ui_f.py::test_energy_curve[fe] | 2 | 34 | 14.7 | 0.35 |
| А | `f_driving_ni` | tools/test_ui_f.py::test_driving_force[ni] | 2 | 30 | 13.2 | 0.43 |
| А | `f_driving_al` | tools/test_ui_f.py::test_driving_force[al] | 2 | 30 | 16.3 | 1.02 |
| А | `f_driving_fe` | tools/test_ui_f.py::test_driving_force[fe] | 2 | 31 | 19.3 | 0.70 |
| А | `f_tzero_ni` | tools/test_ui_f.py::test_tzero_in_narrow_window[ni] | 2 | 28 | 14.2 | 0.31 |
| А | `f_tzero_al` | tools/test_ui_f.py::test_tzero_in_narrow_window[al] | 2 | 28 | 11.7 | 0.30 |
| А | `f_tzero_fe` | tools/test_ui_f.py::test_tzero_in_narrow_window[fe] | 2 | 28 | 41.2 | 0.32 |
| А | `f_density_ni` | tools/test_ui_f.py::test_density_single[ni] | 2 | 26 | 17.3 | 0.41 |
| А | `f_density_al` | tools/test_ui_f.py::test_density_single[al] | 2 | 26 | 19.3 | 0.99 |
| А | `f_density_fe` | tools/test_ui_f.py::test_density_single[fe] | 2 | 26 | 25.5 | 0.72 |
| А | `f_density_warning_ni` | tools/test_ui_f.py::test_density_estimated_warning_is_shown_to_user | 2 | 26 | 48.3 | 1.67 |
| А | `f_density_t_ni` | tools/test_ui_f.py::test_density_temperature_scan[ni] | 2 | 26 | 14.7 | 0.42 |
| А | `f_density_t_al` | tools/test_ui_f.py::test_density_temperature_scan[al] | 2 | 26 | 32.0 | 2.57 |
| А | `f_density_t_fe` | tools/test_ui_f.py::test_density_temperature_scan[fe] | 2 | 26 | 32.0 | 1.34 |
| А | `f_elastic_ni` | tools/test_ui_f.py::test_elastic_vrh[ni] | 3 | 26 | 18.8 | 0.42 |
| А | `f_elastic_al` | tools/test_ui_f.py::test_elastic_vrh[al] | 3 | 26 | 20.3 | 0.99 |
| А | `f_elastic_fe` | tools/test_ui_f.py::test_elastic_vrh[fe] | 3 | 26 | 24.9 | 0.72 |
| А | `f_strength_ni` | tools/test_ui_f.py::test_strengthening[ni] | 2 | 24 | 11.2 | 0.25 |
| А | `f_strength_al` | tools/test_ui_f.py::test_strengthening[al] | 2 | 24 | 9.7 | 0.24 |
| А | `f_strength_fe` | tools/test_ui_f.py::test_strengthening[fe] | 2 | 24 | 12.7 | 0.26 |
| А | `f_binary_ni` | tools/test_ui_f.py::test_binary_diagram[ni] | 2 | 27 | 25.9 | 0.43 |
| А | `f_binary_al` | tools/test_ui_f.py::test_binary_diagram[al] | 2 | 27 | 39.1 | 1.20 |
| А | `f_binary_fe` | tools/test_ui_f.py::test_binary_diagram[fe] | 2 | 27 | 31.0 | 0.97 |
| А | `f_isopleth_ni` | tools/test_ui_f.py::test_isopleth_diagram[ni] | 2 | 27 | 55.4 | 1.01 |
| А | `f_isopleth_al` | tools/test_ui_f.py::test_isopleth_diagram[al] | 2 | 27 | 184.3 | 1.92 |
| А | `f_isopleth_fe` | tools/test_ui_f.py::test_isopleth_diagram[fe] | 2 | 27 | 69.1 | 1.50 |
| А | `f_ternary_ni` | tools/test_ui_f.py::test_ternary_diagram[ni] | 2 | 27 | 38.1 | 0.80 |
| А | `f_ternary_al` | tools/test_ui_f.py::test_ternary_diagram[al] | 2 | 27 | 107.2 | 1.60 |
| А | `f_ternary_fe` | tools/test_ui_f.py::test_ternary_diagram[fe] | 2 | 27 | 39.1 | 0.94 |
| А | `f_tmap_ni` | tools/test_ui_f.py::test_ternary_phase_map[ni] | 2 | 32 | 22.4 | 1.38 |
| А | `f_tmap_al` | tools/test_ui_f.py::test_ternary_phase_map[al] | 2 | 32 | 56.9 | 3.12 |
| А | `f_tmap_fe` | tools/test_ui_f.py::test_ternary_phase_map[fe] | 2 | 32 | 37.1 | 2.90 |
| А | `f_phasemap3_ni` | tools/test_ui_f.py::test_phase_map_needs_three_elements[ni] | 1 | 20 | 9.7 | 0.24 |
| А | `f_phasemap3_al` | tools/test_ui_f.py::test_phase_map_needs_three_elements[al] | 1 | 20 | 8.1 | 0.23 |
| А | `f_phasemap3_fe` | tools/test_ui_f.py::test_phase_map_needs_three_elements[fe] | 1 | 20 | 11.2 | 0.24 |
| А | `f_db_change` | tools/test_ui_f.py::test_results_do_not_survive_a_database_change | 3 | 36 | 23.4 | 0.44 |
| Б | `g_render_ni` | tools/test_ui_g.py::test_kinetics_section_renders[ni] | 1 | 20 | 9.7 | 0.24 |
| Б | `g_render_al` | tools/test_ui_g.py::test_kinetics_section_renders[al] | 1 | 20 | 8.1 | 0.23 |
| Б | `g_render_fe` | tools/test_ui_g.py::test_kinetics_section_renders[fe] | 1 | 20 | 10.7 | 0.25 |
| Б | `g_run_gate` | tools/test_ui_g.py::test_run_gate_is_identical_for_all_databases | 3 | 34 | 20.8 | 0.28 |
| Б | `g_single_ni` | tools/test_ui_g.py::test_diffusion_single_phase[ni] | 4 | 37 | 18.8 | 0.32 |
| Б | `g_single_al` | tools/test_ui_g.py::test_diffusion_single_phase[al] | 4 | 37 | 15.2 | 0.31 |
| Б | `g_single_fe` | tools/test_ui_g.py::test_diffusion_single_phase[fe] | 4 | 37 | 21.8 | 0.32 |
| Б | `g_hom_ni` | tools/test_ui_g.py::test_diffusion_homogenization[ni] | 5 | 37 | 19.8 | 0.34 |
| Б | `g_hom_fe` | tools/test_ui_g.py::test_diffusion_homogenization[fe] | 5 | 37 | 23.9 | 0.34 |
| Б | `g_hom_al` | tools/test_ui_g.py::test_homogenization_unavailable_on_al_is_explained | 3 | 20 | 10.2 | 0.25 |
| Б | `g_kwn_ni` | tools/test_ui_g.py::test_kwn_precipitation[ni] | 4 | 65 | 31.5 | 0.37 |
| Б | `g_kwn_al` | tools/test_ui_g.py::test_kwn_precipitation[al] | 4 | 65 | 22.9 | 0.37 |
| Б | `g_kwn_fe` | tools/test_ui_g.py::test_kwn_precipitation[fe] | 4 | 65 | 69.1 | 0.41 |
| Б | `g_kwn_fe_provenance` | tools/test_ui_g.py::test_fe_kwn_provenance_status_is_neutral | 4 | 65 | 62.4 | 0.40 |
| Б | `g_kwn_matrix_al` | tools/test_ui_g.py::test_kwn_matrix_offers_the_disordered_half[al] | 1 | 20 | 7.6 | 0.23 |
| Б | `g_kwn_matrix_fe` | tools/test_ui_g.py::test_kwn_matrix_offers_the_disordered_half[fe] | 1 | 20 | 10.7 | 0.25 |
| Б | `g_kwn_too_long` | tools/test_ui_g.py::test_kwn_reports_a_too_long_composition_without_a_traceback | 1 | 21 | 10.2 | 0.25 |
| Б | `g_kwn_eight` | tools/test_ui_g.py::test_kwn_accepts_the_eight_solute_steel_since_bl21 | 1 | 20 | 10.7 | 0.25 |
| Б | `g_bounded_kin_single` | tools/test_ui_g.py::test_diffusion_number_inputs_are_bounded[kin_single] | 1 | 20 | 9.2 | 0.24 |
| Б | `g_bounded_kin_hom` | tools/test_ui_g.py::test_diffusion_number_inputs_are_bounded[kin_hom] | 1 | 20 | 9.2 | 0.24 |
| Б | `g_bad_couple_1` | tools/test_ui_g.py::test_bad_couple_composition_is_reported | 3 | 20 | 11.7 | 0.25 |
| Б | `g_bad_couple_2` | tools/test_ui_g.py::test_bad_couple_composition_is_reported | 3 | 20 | 11.2 | 0.27 |
| Б | `g_bad_couple_3` | tools/test_ui_g.py::test_bad_couple_composition_is_reported | 3 | 20 | 11.2 | 0.26 |
| Б | `g_kwn_grid` | tools/test_ui_g.py::test_kwn_size_grid_is_validated | 3 | 21 | 18.3 | 0.26 |
| Б | `g_ni_kwn_hour` | tools/test_ui_g.py::test_ni_kwn_reaches_a_precipitated_state | 4 | 65 | 68.0 | 0.37 |
| Б | `g_fe_defaults` | tools/test_ui_g.py::test_fe_shipped_defaults_are_the_declared_ones | 1 | 20 | 10.7 | 0.25 |
| В | `h_library_ni` | tools/test_ui_h.py::test_library_save_appears_in_the_list_and_loads_back[ni] | 9 | 33 | 29.5 | 0.30 |
| В | `h_library_al` | tools/test_ui_h.py::test_library_save_appears_in_the_list_and_loads_back[al] | 9 | 34 | 29.0 | 0.30 |
| В | `h_library_fe` | tools/test_ui_h.py::test_library_save_appears_in_the_list_and_loads_back[fe] | 9 | 28 | 29.5 | 0.30 |
| В | `h_library_roundtrip` | tools/test_ui_h.py::test_library_export_and_import_round_trip | 5 | 22 | 24.4 | 0.29 |
| В | `h_project_ni` | tools/test_ui_h.py::test_project_saves_fourteen_keys_and_restores_state[ni] | 6 | 29 | 23.9 | 0.29 |
| В | `h_project_al` | tools/test_ui_h.py::test_project_saves_fourteen_keys_and_restores_state[al] | 6 | 29 | 22.4 | 0.28 |
| В | `h_project_fe` | tools/test_ui_h.py::test_project_saves_fourteen_keys_and_restores_state[fe] | 6 | 23 | 20.9 | 0.28 |
| В | `h_project_export` | tools/test_ui_h.py::test_project_export_is_portable_and_imports_back | 8 | 23 | 30.0 | 0.29 |
| В | `h_confirmations` | tools/test_ui_h.py::test_confirmations_survive_the_rerun_and_stay_in_their_own_section | 3 | 23 | 14.7 | 0.28 |
| В | `h_history` | tools/test_ui_h.py::test_history_records_events_exports_csv_and_clears | 7 | 23 | 21.3 | 0.29 |
| В | `h_batch_comma` | tools/test_ui_h.py::test_batch_accepts_both_separators_and_both_encodings[comma] | 2 | 21 | 13.2 | 0.26 |
| В | `h_batch_semicolon` | tools/test_ui_h.py::test_batch_accepts_both_separators_and_both_encodings[semicolon] | 2 | 21 | 13.2 | 0.27 |
| В | `h_batch_comma_bom` | tools/test_ui_h.py::test_batch_accepts_both_separators_and_both_encodings[comma_bom] | 2 | 21 | 12.7 | 0.26 |
| В | `h_batch_semicolon_bom` | tools/test_ui_h.py::test_batch_accepts_both_separators_and_both_encodings[semicolon_bom] | 2 | 21 | 12.7 | 0.27 |
| В | `h_batch_junk` | tools/test_ui_h.py::test_batch_rejects_a_junk_file_with_a_readable_message | 2 | 20 | 12.7 | 0.27 |
| В | `h_batch_template` | tools/test_ui_h.py::test_batch_template_downloads_open_as_excel_and_csv | 3 | 23 | 14.2 | 0.28 |
| В | `h_batch_summary` | tools/test_ui_h.py::test_batch_summary_has_no_receipt_columns | 3 | 27 | 20.8 | 0.41 |
| В | `h_batch_three` | tools/test_ui_h.py::test_batch_calculates_three_databases_and_exports_excel | 4 | 33 | 37.6 | 1.40 |
| В | `h_batch_c15` | tools/test_ui_h.py::test_batch_rejects_c15_for_steel_before_any_calculation | 2 | 20 | 13.7 | 0.26 |
| В | `h_first_run` | tools/test_ui_h.py::test_first_run_creates_the_profile_and_writes_nothing_into_the_program | 1 | 20 | 11.2 | 0.24 |
| В | `h_phase_reference_ni` | справочник фаз | 2 | 21 | 11.7 | 0.26 |
| В | `h_phase_reference_al` | справочник фаз | 2 | 21 | 10.2 | 0.24 |
| В | `h_phase_reference_fe` | справочник фаз | 2 | 21 | 13.2 | 0.26 |
| В | `h_batch_fe08` | results/wave19_d/priemka.py::case_batch (через экран) | 4 | 34 | 24.9 | 0.82 |
| Г | `sh_density_nicr_on` | results/wave15_sh/scripts/density_run.py | 2 | 26 | 17.3 | 0.43 |
| Г | `sh_density_t_nicr_on` | results/wave15_sh/scripts/density_run.py (скан) | 2 | 26 | 23.4 | 1.08 |
| Г | `sh_elastic_nicr_on` | results/wave15_f/scripts/elastic_run.py | 3 | 26 | 19.3 | 0.45 |
| Г | `sh_density_nicr_off` | results/wave15_sh/scripts/density_run.py | 2 | 26 | 17.8 | 0.43 |
| Г | `sh_density_t_nicr_off` | results/wave15_sh/scripts/density_run.py (скан) | 2 | 26 | 23.4 | 1.07 |
| Г | `sh_elastic_nicr_off` | results/wave15_f/scripts/elastic_run.py | 3 | 26 | 18.8 | 0.44 |
| Г | `sh_density_nialcr_on` | results/wave15_sh/scripts/density_run.py | 2 | 26 | 19.3 | 0.49 |
| Г | `sh_density_t_nialcr_on` | results/wave15_sh/scripts/density_run.py (скан) | 2 | 26 | 30.0 | 2.41 |
| Г | `sh_elastic_nialcr_on` | results/wave15_f/scripts/elastic_run.py | 3 | 26 | 19.3 | 0.51 |
| Г | `sh_density_nialcr_off` | results/wave15_sh/scripts/density_run.py | 2 | 26 | 18.3 | 0.49 |
| Г | `sh_density_t_nialcr_off` | results/wave15_sh/scripts/density_run.py (скан) | 2 | 26 | 30.0 | 2.39 |
| Г | `sh_elastic_nialcr_off` | results/wave15_f/scripts/elastic_run.py | 3 | 26 | 19.3 | 0.51 |
| Г | `sh_density_fecrc_on` | results/wave15_sh/scripts/density_run.py | 2 | 26 | 22.9 | 0.62 |
| Г | `sh_density_t_fecrc_on` | results/wave15_sh/scripts/density_run.py (скан) | 2 | 26 | 46.8 | 2.86 |
| Г | `sh_elastic_fecrc_on` | results/wave15_f/scripts/elastic_run.py | 3 | 26 | 23.9 | 0.64 |
| Г | `sh_density_fecrc_off` | results/wave15_sh/scripts/density_run.py | 2 | 26 | 22.9 | 0.61 |
| Г | `sh_density_t_fecrc_off` | results/wave15_sh/scripts/density_run.py (скан) | 2 | 26 | 45.7 | 2.86 |
| Г | `sh_elastic_fecrc_off` | results/wave15_f/scripts/elastic_run.py | 3 | 26 | 22.8 | 0.64 |
| Г | `sh_solid_nicr` | results/wave18_v/run_case.py::nicr | 3 | 81 | 29.6 | 0.51 |
| Г | `sh_solid_nialcr` | results/wave18_v/run_case.py::nialcr | 3 | 81 | 36.9 | 0.63 |
| Г | `sh_solid_fecrc` | results/wave18_v/run_case.py::fecrc | 3 | 81 | 60.7 | 1.46 |

Итого 130 случаев, 4166 файлов в `run1` (4036 + 130 `sha256.txt`).

## Как сверять шаг разреза с эталоном 0.5.0

1. Дерево то же — `D:\Pets\ThermoGar-w21b` (путь дерева стоит в `karkas.txt`). На ветке шага из корня: `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe -B -X utf8 tools\tab_snapshot.py run --out results\validation\<волна>\posle --state results\validation\wave20_v\state\run<N> --time-csv results\<волна>\posle_time.csv`. Окружение `MPLBACKEND=Agg`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`. Прогон ~57–59 мин, пик ~3,1 ГиБ, порог входа 3,0 ГиБ.
2. `N` — следующий свободный номер (заняты `run1`, `run2`; следующий — `run3`). Правило `state\\run\d+` маскирует только такой путь, иначе папка состояния даст различия.
3. Эталон — `results\validation\wave20_v\run1\` или распаковка `results\wave20_v\etalon_run1.zip` (даёт папку `run1\`).
4. Сверка: `… tools\tab_snapshot_compare.py <эталон run1> results\validation\<волна>\posle --isklyucheniya results\wave20_v\isklyucheniya.txt --otchet results\<волна>\sravnenie.txt`. Приёмка — код выхода 0 и «ИТОГ: полное равенство».
5. Поле «ThermoGar_app.py_sha256» в `meta.json` на шагах разреза меняется законно — правило для него вводит первый шаг разреза. Другие исключения — только с разбором по исходнику. Каталог вывода не перезаписывается, для повтора нужен новый каталог.

## Отступления от задания

1. **Правка инструмента в ШАГЕ 1.** Одна, минимальная (`40485e6`, `tools/tab_snapshot.py:232–235`): варианты `st.segmented_control` пишутся текстом `Option.content`. Причина — экран волны 21 (21-И), разбор выше. Пилот повторён в новый каталог `pilot2`. Каталог первого пилота `pilot` оставлен на месте вне git, не удалялся.
2. **Часть работы ШАГОВ 4 и 5 — во время прогона 2.** Архив, его распаковка и сверка, `run1_sha256.txt`, правки реестра (а), (б), (в), (д) сделаны в 13:02–13:05, пока шёл прогон 2. Это не второй прогон, но нагрузка была: первые случаи прогона 2 шли дольше, чем в прогоне 1 (`f_single_al` 26,1 с против 19,3). Сумма прогона 2 всё равно меньше прогона 1. Время прогона 2 для опоры брать с этой оговоркой.
3. **Вспомогательный скрипт вне дерева.** Сводки, `run<N>_sha256.txt`, архив и распаковка сделаны скриптом `w20v_helpers.py` во временной папке сессии, не в репозитории. Задание называет только файлы результата, а файлы вне списка — не класть. Распаковка для сверки — там же. В дереве лишнего нет.
4. **Прогноз не отдельным файлом.** В 20-А был `results/wave20_a/prognoz_run1.txt`. Здесь его нет в списке ШАГА 4, поэтому прогноз — только в отчёте.
5. **Адреса `файл:строка` в правилах 20-А не обновлены.** Файл исключений — копия 20-А с одной строкой в шапке, как требует задание. Строки источников в правилах относятся к коду 23.09 и после волны 21 могли сдвинуться. Сами правила по факту сработали все 13.
6. **Концы строк.** В рабочей копии `core.autocrlf=true`. Сводки и `run<N>_sha256.txt` записаны с LF, в индексе они с LF, как остальные текстовые файлы. Строка шапки `isklyucheniya.txt` записана с CRLF, как остальной файл 20-А в рабочей копии.

## git

Снято после пуша коммита `f767038` (28.09.2026 14:05:33). Коммит, дописавший этот раздел, в выводе не виден — его хэш даёт `git log` ветки.

`git ls-remote origin main wave20-v`:

```
620d88eac942d59e0716a28d46aa164d12b8e500	refs/heads/main
f767038b8dbbe671d936b066114e74d563ec67c0	refs/heads/wave20-v
```

`git log --oneline origin/main..wave20-v`:

```
f767038 docs(20-В): отчёт — эталон вкладок 0.5.0
84137d7 docs(20-В): реестр — приёмка 21-Ю3, строка 20-В, эталон 0.5.0 для волны 20, BL-57
4aa71c8 results(20-В): эталон вкладок 0.5.0 — два прогона, сводки, сверка 1–2, etalon_run1.zip
40485e6 fix(tools): 20-В — tab_snapshot: варианты st.segmented_control (Option.content)
9f9674b docs(tasks): 20-В задание (BL-57, шаг 0 заново — эталон вкладок на коде 0.5.0)
```

`git status --short`:

```
?? _to_delete/
```
