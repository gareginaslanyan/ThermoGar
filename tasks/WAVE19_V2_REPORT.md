# Отчёт 19-В2 (BL-58, часть 2 — описания фаз в программе)

Исполнитель: Claude Opus 5.5, 23.09.2026. Дерево `D:\Pets\ThermoGar`, ветка `wave19-v2` от `70616e2`.

**Итог:** справочник фаз 99/195/132 строк — у 94 строк (Ni 26, Al 27, Fe 41) заглушка заменена сборкой утверждённых фраз по разметке 19-В (77 пар, 30 фраз), остальные 332 строки побайтно прежние, заглушка осталась у 5 строк (Ni 2, Al 0, Fe 3); тест шага 2 красный на `70616e2` (3 passed, 1 failed, 5 errors), зелёный после (9 passed); регрессия 2 файла — 20 passed, 0 failed.

## Шаг 0

- `git ls-remote origin wave19-v` = `70616e2cb2c4f994f252f115d8c9fe5dffd0cd8b`, `origin main` = `dd2f13dfb27fcce3e297276327033290a8a2ad70` — совпало.
- Ветка `wave19-v2` создана от `70616e2`. `app\__pycache__` нет — переносить нечего.
- `git status --short` до начала — дословно в конце отчёта (раздел «git status --short, шаг 0»).

## Шаг 1. Замер ДО

`results/wave19_v2/scripts/measure.py do` — `phase_reference_dataframe` и `load_database` через `results/wave19_a/scripts/app_extract.py`, как в 19-А. Файлы `results/wave19_v2/do/phase_reference_{ni,al,fe}.csv`, `sha256.txt`.

| База | Строк | sha256 |
|---|---|---|
| Ni | 99 | `33935f37de8dabf66c3ba9b1de69366c49a546a0a6fe811ab69bb48bd30e9dfc` |
| Al | 195 | `56d9f4c1e0ca42c71c930e2dbe5cc708a7b52276189c6993e1983a0bdc749f60` |
| Fe | 132 | `451b379837ce6f16a8a7f1d92acd90444f676e327e2ad9d4e09126fd93218b25` |

Сверка: равны sha256 файлов `results/wave19_a/posle/1v_phase_reference_{ni,al,fe}.csv` в коммите `70616e2` и столбцу `sha256` в `results/wave19_a/posle/1v_summary.csv`. Рабочие копии этих файлов на ноутбуке дают другие суммы только из-за CRLF (см. отступление 1). Запись — `results/wave19_v2/do/sverka_19a.txt`.

## Шаг 2. Тест до правки

`tools/test_phase_description_stub_keys.py`, 9 тестов: а) 19 новых фраз побайтно; ключи и порядок `KEY_ORDER`, 30 ключей; б) 11 прежних фраз — строковые литералы `translate_phase_description` (`ast`); в) 77 записей, ключи из списка, порядок, ограничения «не больше одного»; `phrases_for` на паре из таблицы и на отсутствующей паре; г) четыре вызова `translate_phase_description` из задания (извлечение через `ast`, как в `tools/test_phase_description_order_words.py`).

На `70616e2` (приложение без правки): **3 passed, 1 failed, 5 errors** — `results/wave19_v2/tests_red.txt`. Ошибки — `ModuleNotFoundError: thermogar_phase_descriptions`; падение — `("CR2B", "Orthorhombic.", "")` даёт заглушку. Прошли три проверки прежнего поведения (ZZZ и SPINEL — заглушка, Ferrite — прежний путь). Отдельный коммит `515210b`.

## Шаг 3. Модуль

`app/thermogar_phase_descriptions.py` целиком собран скриптом `results/wave19_v2/scripts/gen_stub_keys.py` (коммит `7df3252`): `PHRASES` — 30 ключей, `KEY_ORDER` — порядок списка 19-В, `STUB_KEYS` — 77 пар, сортировка по (имя, описание), `phrases_for(phase_name, description) -> str | None`. Шапка — источник по заданию.

Скрипт перед записью проверяет: строк разметки 80, непустых 77, пустые — CHI_A12, TRID, SPINEL; все ключи из списка; нет повторов пар; описания без внешних пробелов; каждая из 77 пар есть в справочнике ДО строкой с заглушкой; всего пар с заглушкой в ДО 80.

## Шаг 4. `translate_phase_description`

Коммит `def1f49`, 4 строки: импорт `import thermogar_phase_descriptions as phase_descriptions` после `import thermogar_parallel_ui as parallel_ui`; в ветке `if original:` перед заглушкой — `phrases_for(phase_name, original)`, при не-`None` возврат фраз. Ключ — `original`, то есть описание после `strip()`, как в функции. Больше в функции ничего не менялось.

## Шаг 5. Замер ПОСЛЕ

`measure.py posle` -> `results/wave19_v2/posle/`; `results/wave19_v2/scripts/compare.py` -> `sravnenie.csv` (94 строки + заголовок), `sravnenie_itog.txt`.

| База | Строк | Изменилось | Прежние побайтно | Заглушка осталась | sha256 ПОСЛЕ |
|---|---|---|---|---|---|
| Ni | 99 | 26 | 73 | 2 (CHI_A12, TRID) | `0a711620043487ea2f33d1f05a019bed0605a70887010ce6455e1e870ad61e74` |
| Al | 195 | 27 | 168 | 0 | `6b849fc8a2bd932f8e8febecaaa467798432644fff9a8373bda359ca0fc14d30` |
| Fe | 132 | 41 | 91 | 3 (CHI_A12, SPINEL, TRID) | `5689f2e67a1b1350ce060319d5045e1efdc26a21bd9671ff36e3b4728851d552` |
| Всего | 426 | 94 | 332 | 5 | |

Все проверки шага 5 прошли (`problems: none`): у 94 изменённых строк отличается только «Описание по-русски»; до — заглушка; после — сборка фраз по ключам `razmetka_ispolnitel.csv` (ожидание в `compare.py` строится из разметки, не из модуля программы).

Тест шага 2 после правки: **9 passed** — `results/wave19_v2/tests_green.txt`.

## Шаг 6. Регрессия

Поиск по `tools\` строк «phase_reference», «Справочник фаз» (в том числе без учёта регистра), «translate_phase_description» нашёл два файла: `tools/test_phase_description_order_words.py`, `tools/test_phase_description_stub_keys.py`. Прогон — `results/wave19_v2/scripts/regress.py` (копия скрипта 19-А), по файлу на процесс, логи в `results/wave19_v2/regress/`.

| Файл | passed/failed | Время, с | Пик памяти, МиБ |
|---|---|---|---|
| `tools/test_phase_description_stub_keys.py` | 9 / 0 | 7,3 | 216 |
| `tools/test_phase_description_order_words.py` | 11 / 0 | 6,7 | 214 |

## Шаг 7. Реестр

`tasks/REGISTER.md` правлен скриптом `results/wave19_v2/scripts/register_edit.py` (каждая замена — ровно одно вхождение): 7а строка 19-В; 7б строка 19-В2; 7в начало ячейки «Состояние» BL-58, остальной текст ячейки сохранён; 7г 19 строк в «Тексты владельца — опись»; 7д подраздел «Ошибка мастера (19-В)» в конце волны 19.

## Примеры «было -> стало»

У всех строк «было» — «Русская расшифровка для этой специализированной фазы ещё не добавлена.».

| База | Фаза | Оригинал из базы | Стало |
|---|---|---|---|
| Ni | CR2B | Orthorhombic. | Ромбическая структура. Боридная фаза. |
| Ni | MU_PHASE | can form as topologically close-packed structure in superalloys; affecting brittleness. | Топологически плотноупакованная (ТПУ) фаза. Может охрупчивать сплав. |
| Ni | O1_GAS | for thermodynamic properties calculations only | Газовая фаза. Служебная фаза базы: только для расчёта термодинамических свойств. |
| Al | AL12MG2CR | dispersoid in AA7xxx | Интерметаллидная фаза. Дисперсоид. |
| Al | AL3TI_H | Tetragonal high temperature modification with space group I4/mmm. | Тетрагональная структура. Интерметаллидная фаза. Высокотемпературная модификация. |
| Al | SITI | oP8 Pnma FeB | Ромбическая структура. Силицидная фаза. |
| Fe | MO2M1B2 | tetragonal, space group P4/mbm | Тетрагональная структура. Боридная фаза. |
| Fe | O_MN2B | Orthorhombic. | Ромбическая структура. Боридная фаза. |
| Fe | WC | simple hexagonal | Гексагональная структура. Карбидная фаза. |
| Fe | Y2TIO5 | orthorhombic, strengthening dispersoid | Ромбическая структура. Оксидная фаза. Упрочняющий дисперсоид. |

## Черновик абзаца для CHANGELOG 0.4.4

(в `CHANGELOG.md` не записан)

> **Справочник фаз: русские описания вместо заглушки (BL-58).** В разделе «Проекты и данные» → справочник фаз трёх баз 94 строки из 99, которые раньше получали заглушку «Русская расшифровка для этой специализированной фазы ещё не добавлена», теперь имеют описание в столбце «Описание по-русски»: структура, класс соединения, роль и устойчивость. Описание собирается из 30 фраз, утверждённых владельцем, по заранее составленной таблице (фаза, описание из базы); модель в работающей программе не вызывается. У 5 строк (фазы CHI_A12, TRID, SPINEL) текст в базе не называет ни структуры, ни класса — заглушка осталась. Остальные строки справочника не изменились.

## Отступления от задания

1. **Шаг 1, сверка sha256.** Рабочие копии `results/wave19_a/posle/1v_phase_reference_{ni,al,fe}.csv` на ноутбуке дают суммы `169767d7…`, `2fae6fb2…`, `35aa4fc4…`, не равные замеру ДО. Причина — `core.autocrlf=true`, для `*.csv` в `.gitattributes` нет `eol=lf`: при checkout строки получили CRLF. Суммы байтов этих файлов в коммите `70616e2` (`git show`), суммы в `1v_summary.csv` 19-А и суммы рабочих копий после удаления CR равны замеру ДО. СТОП не объявлял: байты, записанные 19-А, совпадают. Новые CSV 19-В2 записаны с LF; в рабочей копии Git при следующем checkout тоже даст им CRLF.
2. **Шаг 3, генерация.** Скрипт `gen_stub_keys.py` пишет весь модуль, не только `STUB_KEYS`: фразы и шапка — константы скрипта. Причина — один источник для модуля; ручной правки файла нет. 11 прежних фраз в скрипте набраны как копии литералов функции, побайтное совпадение проверяет тест б).
3. **Шаг 2, тест.** Кроме пунктов а)–г) в тесте проверены `KEY_ORDER` (30 ключей, порядок списка) и `phrases_for` на паре из таблицы и на отсутствующей паре. Причина — шаг 3 задаёт эти имена; без проверки они не покрыты.
4. **Задание в `tasks/WAVE19_V2_OPUS.md`.** Сохранено дословно без первой строки вставки `/caveman ultra` — это команда исполнителю, не текст задания.
5. **Отчёт и лог.** `git log` и `git status` ниже сняты до коммита этого отчёта; коммит отчёта идёт следующим поверх `b3c5bd1` и тоже отправлен в `origin`.
6. **Строка BL-58.** В сохранённом тексте ячейки осталась ссылка `app/ThermoGar_app.py:5662-5666`; после правки заглушка на строках 5668-5671. По заданию текст ячейки не менял.

## Шаг 8. Git

`git push -u origin wave19-v2` — новая ветка. `git ls-remote origin wave19-v2` после пуша коммита реестра:

```
b3c5bd13d947da5478686e2ea2562827a979322d	refs/heads/wave19-v2
```

`git log --oneline 70616e2..wave19-v2` (до коммита отчёта):

```
b3c5bd1 docs(register): accept 19-V, add 19-V2 row, close BL-58, owner texts, master error 19-V
365a29e results(wave19-v2): phase reference after change, comparison, green test
def1f49 feat(app): phase reference uses stub keys table instead of placeholder (BL-58)
7df3252 feat(phase-descriptions): add approved phrases and stub keys table (BL-58)
515210b test(phase-descriptions): stub keys table test, red before change (BL-58)
4f28746 results(wave19-v2): phase reference before change (step 1)
3fb47fd docs(tasks): add wave 19-V2 task
```

`git status --short` (до коммита отчёта; совпадает с шагом 0 построчно):

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

### git status --short, шаг 0

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
