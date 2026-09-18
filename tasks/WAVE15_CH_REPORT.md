**Итог: сделано.** Подготовка упругих свойств на Ni-20Cr-0,3C масс. % при 700 °C больше не падает.

* **Причина.** Это та самая ошибка pycalphad с парой BCC_B2/BCC_A2 и межузельным углеродом. Подготовка отдавала в `equilibrium` набор фаз политики мимо структурного детектора.
* **Починка.** Набор фаз проведён через тот же `verified_physical.buildable_phases`, что у плотности (он вызывает `thermogar_database_repair.drop_broken_order_disorder`). Второго механизма нет.
* **Результат на Ni-20Cr-0,3C.** BCC_B2 снята и названа в `warnings` сразу после отметки поправок, текстом плотности. Равновесие — FCC_A1 + M7C3, VRH считается.
* **Сверка с `be1fe81`.** Ni-20Cr при 700 °C и Fe-15Cr-0,4C при 950 °C побайтово совпадают по всем 10 файлам в режимах on и off.
* **Аудит.** Других пользовательских разделов мимо детектора нет.
* **Тесты.** Все три прогона зелёные.
* **Хеши и ветка.** Закреплённых хешей правка не касается. Ветка `wave15-bl38` не влита и не запушена.

# Волна 15-Ч — BL-40: подготовка упругих свойств падает на никелевом составе с углеродом

* Задание — `tasks/WAVE15_CH_OPUS.md`.
* Дерево — `C:\Users\gareg\Desktop\ThermoGar-w15d`, ветка `wave15-bl38`, продолжена от `be1fe81`.
* Интерпретатор — `C:\Users\gareg\Desktop\ThermoGar\.venv-windows`.
* Деревья w15e и w15o не тронуты.

---

## 0. Где посылка задания неточна

1. **Строка пользователю.** Задание просит «ту же строку, что у плотности», и цитирует её как «Фазы, несовместимые с составом, исключены: …». Это разные тексты:
   * процитированный текст — `thermogar_database_repair.excluded_phases_note`, и он уходит только в лог (`_log`);
   * плотность с 11N-2 и основной расчёт показывают пользователю другой текст — `thermogar_verified_physical.excluded_phases_note`: «Из расчёта исключены фазы, модель которых не строится на выбранном наборе элементов: BCC_B2 (связана с BCC_A2: …). Это ограничение описания базы, а не отказ расчёта: остальные фазы считаются как обычно.»

   Я остановился и спросил. Мастер выбрал **текст плотности** — он и стоит в подготовке.
2. **`prepare_calculation`** находится на `ThermoGar_app.py:3033`, а не на ~`:2386`. Детектор вызывается не в ней самой, а в `compatible_phases_for_components` (`:2515`), через которую она идёт:
   * там же вызывается `effective_release_phases`;
   * детектор подключён через обёртку приложения `drop_unbuildable_order_disorder`: она делает только структурную проверку (`broken_order_disorder_phases`), без проверки построением `Model`.

   Разделы плотности и теперь упругости зовут `drop_broken_order_disorder` с проверкой `Model`. Условие pycalphad у обоих путей одно и то же. Разницу я не трогал: она вне задания.
3. **Строка `BL-13`** в `REGISTER.md` ветки `wave15-release` и п. 11N-2 прочитаны. Класс дефекта тот же, починка повторяет 11N-2.

## 1. Воспроизведение и причина

* Скрипт — `results/wave15_ch/scripts/repro_trace.py`. Это AppTest на снимке `git archive be1fe81 app databases`, вкладка «Упругие свойства», кнопка «Получить фазовые доли».
* Бэкенд обёрнут, чтобы снять traceback: пользователю приложение показывает только имя класса.
* Выход — `results/wave15_ch/probe/repro_be1fe81.json`.

Пользователь видит:

```
ThermoGar не завершил расчёт. … Причина: BACKEND_FAILED: ValueError
```

Полный traceback:

```
Traceback (most recent call last):
  File "C:\Users\gareg\Desktop\ThermoGar-w15d\results\wave15_ch\scripts\repro_trace.py", line 37, in traced_backend
    return original_backend(database, physical_database, call)
  File "…\scratchpad\snap\src_be1fe81\app\thermogar_verified_properties.py", line 470, in _default_backend
    result = equilibrium(
  File "C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Lib\site-packages\pycalphad\core\equilibrium.py", line 65, in equilibrium
    wks = Workspace(database=dbf, components=comps, phases=phases, conditions=conditions, models=model, parameters=parameters,
  File "…\pycalphad\core\workspace.py", line 338, in __init__
    setattr(self, kwarg_name, kwargs[kwarg_name])
  File "…\pycalphad\core\workspace.py", line 241, in __set__
    value = instantiate_models(obj.database, obj.components, obj.phases, model=value, parameters=obj.parameters)
  File "…\pycalphad\core\utils.py", line 404, in instantiate_models
    models_dict[name] = mod(dbf, comps, name, parameters=parameters)
  File "…\pycalphad\model.py", line 245, in __init__
    phase = _extend_ordered_if_subset_of_disorder(dbe, active_species, phase)
  File "…\pycalphad\model.py", line 85, in _extend_ordered_if_subset_of_disorder
    raise ValueError(f"Order ({phase.name}) and disorder ({disordered_phase_name}) model must have no interstitial sublattice or a single matching one")
ValueError: Order (BCC_B2) and disorder (BCC_A2) model must have no interstitial sublattice or a single matching one
```

(Строки-подчёркивания `^^^` Python убраны, пути в site-packages сокращены. Полный текст — в JSON.)

Там же снято:
* `is_order_disorder_model_error(error)` = **True**;
* `broken_order_disorder_phases` = `['BCC_B2']`;
* на входе 99 фаз, компоненты `C, CR, NI, VA`.

**Причина по исходнику.** `execute_verified_properties` брал набор фаз из `_phase_identity`. Это набор политики привязки: `phase_policy.eligible_phases` — все фазы базы без фильтра по составу. Кандидаты подготовки строит `_b4b_prepare_decision` (`ThermoGar_app.py:1410`), тоже из `eligible_phases`. `_default_backend` (`thermogar_verified_properties.py:452`) отдавал этот набор прямо в `pycalphad.equilibrium`, и детектор его не видел. Ошибка та, что предполагало задание, — остановки нет.

## 2. Аудит вызовов `pycalphad.equilibrium` в `app/`

Строки — по `be1fe81`. Колонки:
* «детектор пары» — снимается ли пара «порядок/беспорядок» до движка;
* «исключения release» — C15_LAVES и прочее по `effective_release_phases` или политике привязки;
* «быстрый набор» — применяется ли переключатель «быстрый набор / все фазы».

### Разделы, куда доходит пользовательский состав

| раздел | файл:строка | детектор пары | исключения release | быстрый набор |
|---|---|---|---|---|
| Равновесие в точке, Ni и Al | `thermogar_verified_equilibrium.py:299` | да: кандидаты запроса — `phase_candidates_for_standard_composition` (`ThermoGar_app.py:6969`) → `compatible_phases_for_components`; политика сужает набор до них (`verified_loaders.py:771`) | да, `compatible_phases_for_components:2546` и политика | да, `phase_selection_editor` (`:6987`) |
| Равновесие в точке, Fe | `ThermoGar_app.py:7093` | да, `prepare_calculation` (`:7078`) | да | да (`:6987`) |
| Скан по температуре | `thermogar_parallel.py:468` через `direct_equilibrium_scan` | да, `prepare_calculation` (`:7418`) | да | да (`:7312`) |
| Скан по концентрации | `thermogar_parallel.py:468` через `run_equilibrium_points` | да, `prepare_calculation` (`:7766`) | да | да (`:7657`) |
| Пакетный расчёт | `thermogar_parallel.py:468` через `ThermoGar_app.py:3449` | да, `prepare_calculation` (`:3404`) | да | нет: набор берётся из строки запроса |
| Бинарная T–X | `pycalphad.mapping.BinaryStrategy` (`ThermoGar_app.py:8164`) | да, `compatible_phases_for_components` (`:8099`) | да | да (`:8055`) |
| Многокомпонентное T–X | `IsoplethStrategy` (`:8627`) | да (`:8576`) | да | да (`:8456`) |
| Тройная при T = const | `TernaryStrategy` (`:8978`) | да (`:8938`) | да | да (`:8898`) |
| Карта доли фазы | `thermogar_parallel.py:468` через `calculate_ternary_phase_fraction_map` | да (`:9365`) | да | да (`:9287`) |
| Затвердевание: старт, доля твёрдого, Шейль и равновесное | `ThermoGar_app.py:4231`, `:4419`; `scheil.simulate_*` | да, `prepare_calculation` (`:9902`) | да | да (`:9864`) |
| Энергии фаз | `Workspace`, `ThermoGar_app.py:3764` | да: `prepare_calculation` (`:10486`), список фаз из `phase_candidates_for_standard_composition` (`:10413`) | да | нет, свой выбор фаз |
| Движущая сила | `Workspace`, `:3910`, `:3916` | да, `:10735` и `:10638` | да | нет, свой выбор фаз |
| T₀ | `Workspace`, `:4113`, `:4122`, `:4123` | да, `compatible_phases_for_components` (`:4075`, `:10913`) | да | нет |
| Плотность, точка | `thermogar_verified_physical.py:373` | да, `buildable_phases` (`:367`) с проверкой `Model` | политика привязки, C15 отвергается (`:591`) | нет; ручной выбор — `_b4b_requested_phases` |
| Плотность, скан по T | `thermogar_parallel.py:468` через `ThermoGar_app.py:1772` | да, `buildable_phases` | политика привязки | нет |
| **Упругие свойства, подготовка** | **`thermogar_verified_properties.py:470`** | **нет — BL-40; с `d755d0d` да, `buildable_phases`** | политика привязки, C15 отвергается (`:772`) | нет |
| Упрочнение | — | равновесия нет | — | — |

### Места мимо детектора, куда пользовательский состав не доходит

| место | файл:строка | детектор пары | исключения release | быстрый набор | почему не раздел того же класса |
|---|---|---|---|---|---|
| Диагностика: быстрые проверки баз | `thermogar_stage14.py:988` | нет, `filter_phases` | нет | нет | составы зашиты: Al-Ni, Fe-C, Al-Cu; нестроящихся пар на них нет |
| `check_fe_high_temperature_behavior` | `thermogar_database_guard.py:356` | фазы от вызывающего | — | — | вызовов в коде нет |
| Fe-worker S2 | `thermogar_fe_equilibrium_worker.py:1094` | нет | набор из запроса | нет | ссылок в коде нет, внутренняя диагностика |
| `execute_restricted_fe` | `thermogar_restricted_fe_core.py:583` | нет, `filter_phases` | свой фильтр C15 | нет | вызывается только из `tools/thermogar_restricted_fe_core_test.py` |
| `_legacy_b2_*_oracle` | `ThermoGar_app.py:3519`, `:3523`, `:3527` | — | — | — | недостижимы, оставлены для статических регрессий B2 |
| `thermogar_properties.render_elastic_section` | `thermogar_properties.py:1537` | да, `prepare_calculation` (`:1521`) | да | нет | вызовов нет |

**Ответ на вопрос задания.** Среди пользовательских разделов мимо детектора шла только подготовка упругих свойств. Других разделов по п. 3 чинить не пришлось, п. 4в пуст.

## 3. Что сделано

### `app/thermogar_verified_properties.py` (коммит `d755d0d`)

* В ветке `property_elastic_prepare` функции `execute_verified_properties` набор фаз политики проходит через `verified_physical.buildable_phases(database, components, policy_phases)` до сборки `PropertyPrepareCall`. Это та же функция, что у плотности; внутри она зовёт `thermogar_database_repair.drop_broken_order_disorder`. Второго механизма нет.
* Порядок проверок прежний: `_phase_identity`, затем `_atomic_fractions`.
* В бэкенд уходят только оставшиеся фазы. Ответ бэкенда проверяется по ним же: если снятая фаза вернётся, будет `RESULT_INVALID`.
* Если детектор снял всё, подготовка отказывает с `INPUT_INVALID`: «На выбранном наборе элементов не осталось допустимых фаз: …». Так же сделано у плотности.
* Порядок `warnings`:
  1. `override_notes` физической базы;
  2. `verified_physical.excluded_phases_note(removed)`, если что-то снято;
  3. отметки об оценочных объёмах.

  На экране строка показывается тем же `st.warning`, что и остальные предупреждения подготовки.
* Детектор поставлен в исполнитель, а не в `_default_backend`, как у плотности. Причина: ответ бэкенда подготовки имеет закрытую форму `PREPARE_BACKEND_FIELDS`, и снятые фазы через неё не передать без смены формы. Механизм и вызов те же.
* Если не снято ничего, проекция не меняется ни в одном байте (п. 4б).

### Закреплённые хеши

Правка не трогает ни дайджесты квитанций и привязки, ни `effective_phases` запроса. Детектор сужает только набор, который уходит в движок. Переподписывать ничего не пришлось.

## 4. Доказательства

* Скрипты:
  * `results/wave15_ch/scripts/p4_run.sh` — по образцу `results/wave15_f/scripts/p4_run.sh`;
  * сам прогон — `results/wave15_f/scripts/elastic_run.py`, без изменений;
  * `p4_compare.sh` — сверка.
* Снимки — `git archive be1fe81 app databases` и `git archive d755d0d app databases` в scratchpad сессии. `git diff --stat be1fe81 d755d0d -- app databases` показывает один файл — `app/thermogar_verified_properties.py`.
* Прогоны идут отдельными процессами, по одному, `PYTHONHASHSEED=0`, со свежим `THERMOGAR_STATE_ROOT`.
* Модули фаз для VRH — условные числа проверки весов, как в 15-Ф: первой фазе E = 100 ГПа, второй — 300 ГПа, ν = 0,25.
* Память (`results/wave15_ch/memory.jsonl`):
  * свободно на старте — 5,28…5,39 ГиБ, минимум по ходу — 4,72 ГиБ;
  * пик дерева процессов — 0,26…0,63 ГиБ;
  * 17…42 с на прогон.
* Выходы — `results/wave15_ch/p4/out_*`. Таблица — `sha256_table.tsv`, полные хеши — `sha256_full.txt`.

### (а) Ni-20Cr-0,3C масс. %, 700 °C

* **`be1fe81`, галочка включена.** Подготовка падает, `elastic_run.py` выходит с кодом 4:
  ```
  {"prepare_failed": ["ThermoGar не завершил расчёт.\n\nПроверьте состав, диапазон и набор фаз. Если ошибка повторяется, скачайте технический отчёт ниже. Причина: BACKEND_FAILED: ValueError"]}
  ```
* **`d755d0d`, галочка включена.** Подготовка проходит, `errors` пуст:

  | фаза | мольная доля | Vm, см³/моль | объёмная доля | источник объёма |
  |---|---|---|---|---|
  | FCC_A1 | 0.9540395763815671 | 6.91508024232191 | 0.9598639433428573 | direct |
  | M7C3 | 0.04596042360639596 | 6.00211918698288 | 0.04013605665714268 | direct |

  `warnings` подготовки (`prepare_warnings.json`):
  1. текст поправки хрома («Плотность хрома посчитана по поправке проекта ThermoGar…»);
  2. «Из расчёта исключены фазы, модель которых не строится на выбранном наборе элементов: BCC_B2 (связана с BCC_A2: внедрённая подрешётка BCC_A2 на этом составе — {C, VA}, а у BCC_B2 совпадающих подрешёток 0, нужна ровно одна). Это ограничение описания базы, а не отказ расчёта: остальные фазы считаются как обычно.»

  Обе строки есть и в `st.warning` на экране.

  VRH (`vrh_summary.json`), ГПа:

  | | Voigt | Reuss | Hill |
  |---|---|---|---|
  | K | 72.01814088761903 | 68.49953412166332 | 70.25883750464118 |
  | G | 43.21088453257141 | 41.09972047299799 | 42.1553025027847 |
  | E | 108.02721133142852 | 102.74930118249496 | 105.38825625696175 |

  ν Хилла = 0,25.
* **Повтор** (`out_d755d0d_nicrc_on_repeat`) совпадает с первым прогоном по всем 10 файлам.
* **Галочка снята** (`out_d755d0d_nicrc_off`): первая строка — «Поправки проекта ThermoGar к физической базе выключены пользователем…», вторая — та же строка о BCC_B2. E Хилла = 105.35214699471543 ГПа.

SHA-256 (первые 12 знаков), `d755d0d` on: `prepare_projection.json` `22f827f7bb6b`, `prepare_warnings.json` `6f8660c9183e`, `vrh_summary.json` `f2859b57a1fc`, `vrh_bounds.json` `78ebe30f9620`, `vrh_phase_rows.json` `76c26e02bb8e`, `vrh_projection.json` `e86b32e76650`. На `be1fe81` файлов нет: подготовка упала.

### (б) Побайтово против `be1fe81`, SHA-256, первые 12 знаков

| файл | Ni-20Cr on | Ni-20Cr off | Fe-15Cr-0,4C on | Fe-15Cr-0,4C off |
|---|---|---|---|---|
| `prepare_projection.json` | `dee9a2b1cf76` = | `bafcdbaf7080` = | `2b7d6af2dea2` = | `aac3986d56df` = |
| `prepare_warnings.json` | `00ab9b1191cf` = | `0fe5bcb0ddd4` = | `00ab9b1191cf` = | `0fe5bcb0ddd4` = |
| `summary.json` | `831a7d82622c` = | `1de5440ff275` = | `a2481080f482` = | `13bbfa12ada8` = |
| `vrh_bounds.json` | `af372490fac5` = | `af372490fac5` = | `3e8faf4d3542` = | `503a4688c375` = |
| `vrh_phase_rows.json` | `0e3d080248d9` = | `0e3d080248d9` = | `fd23a0f9cf71` = | `a380c3fb85ab` = |
| `vrh_projection.json` | `a44b27d0ce2c` = | `a44b27d0ce2c` = | `ac10d089f4b4` = | `8dc4a37ea8fe` = |
| `vrh_summary.json` | `022bf8361c09` = | `022bf8361c09` = | `9ed41465509d` = | `8117b32c576c` = |
| лист «Voigt-Reuss-Hill» | `aee3dd0b4b9f` = | `aee3dd0b4b9f` = | `f9b1e0256902` = | `f15ee89508af` = |
| лист «Входные значения по фазам» | `3f864fea0d4a` = | `3f864fea0d4a` = | `9676b17dc96f` = | `47cd63789809` = |
| лист «Итог» | `35504f690ccc` = | `35504f690ccc` = | `087a07935713` = | `37ed07fbacff` = |

«=» — хеш `be1fe81` и `d755d0d` одинаков. **Все 40 пар совпали.** Хеши Ni-20Cr on совпадают и с таблицей 15-Ф для `3166def`.

### (в) Другие разделы

По п. 3 других разделов не трогал, отдельных сверок нет.

## 5. Тесты

* Пофайлово, по одному процессу, без `-m slow` (`-m "not slow"`), `PYTHONHASHSEED=0`.
* Порог входа — 3,0 ГиБ свободной, останов — при < 1,5 ГиБ (`memwrap.py`).
* Раннер — `results/wave15_ch/scripts/tests_run.sh`. `test_ui_f.py` запускался той же командой вручную, с `-k`.
* Замеры по тестам — плагин `results/wave15_u/scripts/memlog_plugin.py`, логи — `results/wave15_ch/tests/`.

| файл | исход | время | пик дерева | мин. свободной |
|---|---|---|---|---|
| `tools/thermogar_verified_properties_test.py` | **39 passed, 5 subtests passed** | 5,6 с | 0,20 ГиБ | 5,08 ГиБ |
| `tools/test_physical_overrides_toggle.py` | **11 passed** | 205,6 с | 1,44 ГиБ | 3,90 ГиБ |
| `tools/test_ui_f.py -k "test_elastic_vrh or test_single_equilibrium or test_density_single"` | **9 passed, 50 deselected** | 163,9 с | 1,77 ГиБ | 3,57 ГиБ |

Новые тесты:

* **`tools/thermogar_verified_properties_test.py`** — детектор подменён: `thermogar_database_repair.drop_broken_order_disorder` заменён заглушкой, `buildable_phases` остаётся настоящим.
  * `test_37` — детектор снимает LIQUID:
    * детектор получил весь набор политики, в бэкенд ушли только BCC_A2 и FCC_A1;
    * `warnings` = [отметка «выключено пользователем», строка плотности с «LIQUID (связана с BCC_A2: …)», строка о правиле смеси];
    * бэкенд, вернувший снятую фазу, даёт `RESULT_INVALID`.
  * `test_38` — снято всё: `INPUT_INVALID` с «не осталось допустимых фаз», бэкенд не вызван.
  * `test_39` — ничего не снято: бэкенд вызван один раз, `warnings` пуст.
* **`tools/test_physical_overrides_toggle.py`** — `test_elastic_prepare_drops_unbuildable_order_disorder_pair`, настоящий расчёт Ni-20Cr-0,3C при 700 °C, пик 1,44 ГиБ, 44,5 с:
  * BCC_B2 нет среди фаз, FCC_A1 есть, фаз не меньше двух;
  * объёмные доли в сумме дают 1;
  * `warnings[0]` — поправка хрома, `warnings[1]` — строка плотности с «BCC_B2 (связана с BCC_A2», она одна и показана на экране;
  * VRH считается по тем же фазам, E Ройсса < E Хилла < E Фойгта;
  * при снятой галочке первой идёт отметка «выключены пользователем», второй — та же строка о BCC_B2.

Пики `test_ui_f.py` по тестам:

| тест | ni | al | fe |
|---|---|---|---|
| `test_single_equilibrium` | 0,41 ГиБ | 1,14 ГиБ | 1,44 ГиБ |
| `test_density_single` | 1,52 ГиБ | 1,70 ГиБ | 1,74 ГиБ |
| `test_elastic_vrh` | 1,70 ГиБ | 1,74 ГиБ | 1,76 ГиБ |

Пик растёт, потому что всё идёт одним процессом.

## 6. git

`git log --oneline be1fe81..HEAD` снят перед коммитом этого отчёта. Отчёт и промт уходят следующим коммитом, `docs(15-Ч)`:

```
de93f03 test(15-Ч): BL-40 — detector in elastic prepare, Ni-20Cr-0.3C evidence
d755d0d fix(15-Ч): BL-40 — elastic prepare passes the order/disorder detector
```

`git status --short`:

```
A  tasks/WAVE15_CH_OPUS.md
?? tasks/WAVE15_CH_REPORT.md
```
