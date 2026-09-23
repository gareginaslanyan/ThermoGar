# Отчёт 19-А (BL-56, BL-55)

Исполнитель — Claude Opus 5.5, 23.09.2026. Дерево `D:\Pets\ThermoGar`, ветка `wave19-a` от `main` `e14b3e3`. Задание — `tasks/WAVE19_A_OPUS.md`.

## Итог

BL-56 и BL-55 закрыты, СТОПов нет. На `e14b3e3` все 11 строк Fe из файла уходили в движок как `stable`. После правки 10 известных значений доходят своим режимом, а `metastabe` даёт «ошибку» текстом владельца. Справочник фаз трёх баз побайтно прежний. Fe–0,8C через пакет побайтно равен замеру ДО. Регрессия: 80 passed, 0 failed. Задеты выпуски 0.3.0–0.4.3.

## Шаг 0. Вход

* `git ls-remote origin main` → `e14b3e3e60bc35712c0c6d151582e5d7eda5d67d refs/heads/main` — совпадает.
* Свободная память на входе: 4 927 720 КиБ = **4,70 ГиБ** (порог 3,0). Перед регрессией было 6,55 ГиБ.
* Чужой байткод `app/__pycache__`: 17 файлов перенесены в `_to_delete/19a_pycache/app__pycache__/`, опись sha256 лежит в `_to_delete/19a_pycache/_opis.txt`.
* Окружение каждого прогона: `python -B -X utf8`, `MPLBACKEND=Agg`, `PYTHONHASHSEED=0`, `THERMOGAR_STATE_ROOT=results\validation\wave19_a_state`. Расчётный поток один, прогоны шли последовательно.
* `git status --short` на входе, дословно (`results/wave19_a/step0_git_status.txt` записан в уже созданную `results/wave19_a/`, поэтому в нём на одну строку больше — `?? results/wave19_a/`):

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

## Шаг 1. Замер ДО (`results/wave19_a/do/`, код `e14b3e3`)

Скрипты лежат в `results/wave19_a/scripts/`. `measure.py` — замеры. `app_extract.py` — загрузка функций главного файла, путь описан в 1в.

### 1а. Цепочка режима стали в пакете

Строки прошли через настоящие `_parse_csv`, `batch_table_dataframe` и `run_batch_calculations`. Runner поддельный — `FakeBatchRunner` из `tools/thermogar_verified_equilibrium_test.py`. Одиннадцать строк Fe, заголовки шаблона, ячейка «Режим стали». Файл `1a_steel_mode_chain.csv`.

| значение | после `_steel_mode` | в runner |
|---|---|---|
| пусто | metastable | **stable** |
| metastable | stable | stable |
| метастабильный | stable | stable |
| практический | metastable | **stable** |
| цементит | metastable | **stable** |
| cementite | metastable | **stable** |
| stable | stable | stable |
| стабильный | stable | stable |
| графит | stable | stable |
| graphite | stable | stable |
| metastabe | metastable | **stable** |

Сверка с мастером: **11 из 11 доходят до runner как `stable`**. Ожидание подтверждено, СТОПа нет. Хранилище и каноническая таблица значение не отклоняют. `_steel_mode` при приёме сводит его к stable/metastable, а `normalize_steel_mode` читает `metastable` как `stable`.

### 1б. Выпуски

Файл `1b_tags.txt`. `_steel_mode` и `normalize_steel_mode` побайтно одинаковы во всех шести тегах и в `e14b3e3`: sha256 текста функции `39cebef0b16e…` и `ffbebc100a5b…`. Путь файл → `_parse_csv` → `batch_table_dataframe` → `run_batch_calculations` → `normalize_steel_mode` есть в каждом теге.

**Задевает выпуски 0.3.0, 0.3.1, 0.4.0, 0.4.1, 0.4.2, 0.4.3.**

### 1в. Справочник фаз

Функции главного файла загружены так же, как фикстура `app` в `tools/test_equilibrium_solidus_fallback.py`: разбор `ast`, импорты верхнего уровня плюс нужные определения, `exec`. Отличие одно — набор имён дополняется замыканием по свободным именам. Вызов тот же, что во вкладке (`app/ThermoGar_app.py:12120`): `load_database(key)`, затем `phase_reference_dataframe(db, path, key)`. Для Fe берётся профиль по умолчанию `thermogar_patch`.

| база | фаз (мастер / замер) | описание непусто | слово `disordered` | слово `ordered` | sha256 CSV |
|---|---|---|---|---|---|
| Ni | 103 / **99** | 64 / 64 | 0 / 0 | 2 / 2 | `33935f37…d30e9dfc` |
| Al | 196 / **195** | 87 / 87 | 0 / 0 | 6 / 6 | `56d9f4c1…dc749f60` |
| Fe | 136 / **132** | 94 / 94 | 0 / 0 | 7 / 7 | `451b3798…93218b25` |
| всего | 435 / **426** | | | | |

Число фаз расходится на 9. Это не СТОП, расхождение записано в `1v_sverka.txt`. Причину проверил: 103/196/136 — число совпадений `^\s*PHASE\s+(\S+)` в тексте TDB. В этот счёт попадают строки комментариев: для Ni и Fe это DIAGRAM, EQUILBRIA, EQUILIBRIA, STABILITY, для Al — RELATIONS. В `db.phases` этих имён нет. Таблица строится по `sorted(db.phases)`, поэтому в ней 99/195/132 строки.

### 1г. Fe–0,8C мас. %, 700 °C, 101325 Па, полный набор фаз `thermogar_patch`

Расчёт шёл через `batch_engine_runner` (`app/ThermoGar_app.py:3420`), загруженный как в 1в. Строки пакета собраны напрямую в форме `run_batch_calculations`. Доли фаз:

| режим | BCC_B2 | GRAPHITE | CEMENTITE | sha256 CSV |
|---|---|---|---|---|
| stable | 0.9643462664947882 | 0.035653733505094175 | — | `bd7984c2…9aff66` |
| metastable | 0.8577531064096179 | — | 0.1422468935902007 | `57dc1b94…eab8b` |

Ожидание подтверждено, СТОПа нет.

Одиночное равновесие считалось как ветка Fe вкладки «Одна температура» (`app/ThermoGar_app.py:7308-7345`): `prepare_calculation` (режим metastable), затем `pycalphad.equilibrium` с pdens 500. Доли совпали с пакетом: набор фаз тот же, **max |разность| = 0.0**. CSV одиночного расчёта побайтно равен CSV пакета.

## Шаг 2. Тесты до правки

* `tools/thermogar_verified_state_test.py::test_batch_steel_mode_closed_list_on_ingress` — приём через `StateStore.ingest_from_widget` и точный перечень.
* `tools/thermogar_verified_equilibrium_test.py::test_17_…` — одна константа, таблица шага 3, текст владельца. `test_18_…` — путь файл → `run_batch_calculations`, где `metastabe` даёт «ошибка», а остальные 10 строк «готово».
* `tools/test_phase_description_order_words.py` (новый) — BL-55, 11 случаев.

Красный прогон на коде `e14b3e3` (`results/wave19_a/tests_red.txt`): **9 failed, 5 passed**. Пять зелёных — «только ordered» (3) и «оба слова» (2). Старый код их уже проходил, они стерегут сохраняемое поведение.

## Шаги 3–4. Правка

* `app/thermogar_verified_state.py:63` — `STEEL_MODE_ALIASES`, единственный закрытый перечень.
* `app/thermogar_verified_state.py:352` — `steel_mode_or_none`, единственный разбор: равенство после `strip` + `casefold`, для None, `""` и NaN возвращает `metastable`.
* `app/thermogar_verified_state.py:367` — `_steel_mode`: неизвестное значение превращается в текст ячейки после `strip`.
* `app/thermogar_workspace.py:2137` — `normalize_steel_mode`: неизвестное значение даёт `ValueError` с текстом владельца. `STEEL_MODE_ALIASES` и `steel_mode_or_none` импортируются из `thermogar_verified_state`. Текст попадает в «Ошибку» сводки существующим путём (`:2331`).
* `app/ThermoGar_app.py:5585-5588` — `re.search(r"\bordered\b", lower)` и `re.search(r"\bdisordered\b", lower)`, проверки независимы.

Хранилище состояния и проверка канонической таблицы пропускают неизвестное значение до `normalize_steel_mode`: это видно в строке `metastabe` таблицы 5. Стоп-условие шага 3 не сработало.

## Шаг 5. Замер ПОСЛЕ (`results/wave19_a/posle/`)

### 1а

| значение | после `_steel_mode` | в runner | Статус | Ошибка |
|---|---|---|---|---|
| пусто | metastable | metastable | готово | |
| metastable | metastable | metastable | готово | |
| метастабильный | metastable | metastable | готово | |
| практический | metastable | metastable | готово | |
| цементит | metastable | metastable | готово | |
| cementite | metastable | metastable | готово | |
| stable | stable | stable | готово | |
| стабильный | stable | stable | готово | |
| графит | stable | stable | готово | |
| graphite | stable | stable | готово | |
| metastabe | metastabe | — (в движок не ушла) | ошибка | Неизвестный режим стали: «metastabe». Используйте «стабильный» или «метастабильный». |

Результат совпадает с таблицей шага 3.

### 1в

CSV справочника ПОСЛЕ побайтно равны ДО по всем трём базам (`posle/1v_cmp.txt`, те же sha256).

### 1г через пакет

Путь: файл → `_parse_csv` → `batch_table_dataframe` → `run_batch_calculations` с настоящим `batch_engine_runner`.

| строка | в runner | эталон ДО | побайтно |
|---|---|---|---|
| пусто | metastable | metastable | да |
| метастабильный | metastable | metastable | да |
| стабильный | stable | stable | да |

### Тесты шага 2

Зелёный прогон (`results/wave19_a/tests_green.txt`): **14 passed**, 28 subtests passed.

Байты `databases/` не менялись: `sha256sum databases/*` до и после совпадает, `git status databases` пуст. `packaging/`, `APP_VERSION` и `CHANGELOG.md` не тронуты.

## Шаг 6. Регрессия (`results/wave19_a/regress/`, по файлу на процесс)

| файл | passed / failed | время, с | пик памяти, МиБ |
|---|---|---|---|
| `tools/thermogar_verified_state_test.py` | 25 / 0 | 2,1 | 57 |
| `tools/thermogar_verified_equilibrium_test.py` | 18 / 0 | 2,3 | 114 |
| `tools/test_phase_description_order_words.py` | 11 / 0 | 4,8 | 212 |
| `tools/test_ui_h.py` (весь файл, включая `slow`) | 26 / 0 | 358,2 | 1575 |

Всего 80 passed, 0 failed. Пик памяти — сумма RSS процесса pytest и его потомков, опрос `psutil` раз в 0,2 с.

## Шаг 7. Реестр и правила

Сделаны 7а–7е. BL-44: проверка `git merge-base --is-ancestor 7745df8 main` вернула «да».

## Отступления от задания

1. В `tasks/WAVE19_A_OPUS.md` не вошла первая строка вставки `/caveman ultra`. Причина: это команда исполнителю, а не текст задания. Задание сохранено начиная с «Задание 19-А…», дальше дословно.
2. Число фаз в 1в — 99/195/132, мастер ждал 103/196/136. Причина: у мастера в счёт вошли 9 совпадений `PHASE …` из комментариев TDB. Записано, это не СТОП.
3. Пять из 14 тестов шага 2 зелёные уже на `e14b3e3`. Причина: они проверяют поведение, которое правка обязана сохранить («только ordered», «оба слова»). Красный прогон всего набора — 9 failed.
4. `thermogar_workspace` импортирует не только константу `STEEL_MODE_ALIASES`, но и функцию разбора `steel_mode_or_none`. Причина: иначе в `normalize_steel_mode` пришлось бы повторить разбор пустых значений и `strip`/`casefold`, а задание требует «второй копии разбора нет».
5. Номера строк после правки сдвинулись: `_steel_mode` теперь `app/thermogar_verified_state.py:367`, `normalize_steel_mode` — `app/thermogar_workspace.py:2137`. В строке BL-56 номера оставлены по `e14b3e3`, как в тексте мастера.
6. Главный файл загружался через `ast` с замыканием по свободным именам (`results/wave19_a/scripts/app_extract.py`), а не через AppTest. Причина: `phase_reference_dataframe` и `batch_engine_runner` тянут цепочку определений, а список имён вручную, как в фикстуре `app`, неполон. Одиночное равновесие 1г посчитано кодом ветки Fe вкладки, без запуска Streamlit.
7. В `tools/__pycache__/` лежит байткод от 18–19.09 (9 файлов, раньше этой волны). Задание называет только `app\__pycache__`, поэтому байткод в `tools/` не перенесён. Эта волна байткода не создавала (`-B`).
8. Отчёт не может содержать хэш собственного коммита. `git log` ниже снят до коммита отчёта, а `git ls-remote` — после первого пуша. Последний хэш ветки назван в сообщении мастеру.

## Черновик абзаца для CHANGELOG 0.4.4 (в `CHANGELOG.md` не вносился)

> **Исправлено.** Пакетный расчёт («Проекты и данные»): режим стали из файла теперь читается по закрытому перечню. Метастабильный режим — пустая ячейка, «метастабильный», «практический», «цементит», `metastable`, `cementite`. Стабильный режим — «стабильный», «графит», `stable`, `graphite`. Регистр и пробелы по краям не важны. В выпусках 0.3.0–0.4.3 каждая строка стали из файла считалась в стабильном режиме (с графитом) при любом значении ячейки, включая пустую. Например, Fe–0,8C при 700 °C давал 3,6 мол. % графита вместо 14,2 мол. % цементита. Неизвестное значение теперь даёт в сводке ошибку строки «Неизвестный режим стали: «…». Используйте «стабильный» или «метастабильный».», остальные строки считаются (BL-56). Справочник фаз: слова `ordered` и `disordered` в описании фазы распознаются по целому слову, разупорядоченная фаза больше не получает пометку «Упорядоченная фаза.». На поставляемых базах текст справочника не меняется (BL-55).

## git

`git log --oneline e14b3e3..wave19-a` (до коммита этого отчёта):

```
06219d8 docs(19-А): реестр волны 19, BL-55/BL-56, ошибка мастера, правила; регрессия
37ef3d6 fix(19-А): BL-56 закрытый перечень режима стали; BL-55 ordered/disordered по слову
3f82bc6 test(19-А): тесты BL-56 и BL-55 до правки (красные на e14b3e3)
3194f66 test(19-А): замер ДО — цепочка режима стали, выпуски, справочник фаз, Fe–0,8C
142c49d docs(19-А): задание 19-А (BL-56, BL-55) дословно
```

`git status --short` на конец работы (до коммита отчёта) — тот же набор неотслеживаемого, что на входе (см. шаг 0), плюс ` ?? tasks/WAVE19_A_REPORT.md`; отслеживаемых изменений нет.

`git ls-remote origin wave19-a` — ниже, после пуша.
