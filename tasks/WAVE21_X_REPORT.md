# Отчёт 21-Х: подготовка выпуска 0.5.0

Задание — `tasks/WAVE21_X_OPUS.md`. Дерево `D:\Pets\ThermoGar-w21b`, ветка `wave21-x`, ноутбук Windows 10,
26.09.2026. Интерпретатор — `D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe`. Все прогоны —
`PYTHONHASHSEED=0`, `MPLBACKEND=Agg`, `THERMOGAR_STATE_ROOT` во временной папке, приложение и AppTest —
`PYTHONDONTWRITEBYTECODE=1`; свободной памяти перед тяжёлыми прогонами — 8,08–8,20 ГиБ; одновременно один
тяжёлый прогон.

## ШАГ 0. Слияния

`git status --short` — только `?? _to_delete/`. `git ls-remote`: `main` `3e2e318…`, `wave21-u` `e8a7aba…`,
`wave21-f` `f98e853…` — как в задании. От `origin/main`, `git merge --no-ff`, конфликтов нет:

| Слияние | Коммит | Родители | Дерево | Модель мастера |
|---|---|---|---|---|
| `wave21-u` | `5a9dcd59038d093ab9d30c1e663011d5ca895587` | `3e2e318`, `e8a7aba` | `922c00bc0382919dfd3e869a874d522192337b37` | совпадает |
| `wave21-f` | `e27c36c7954c97d0f284346d79c8838c7cc5272c` | `5a9dcd5`, `f98e853` | `411ca8afe682d0283515a428bd360493c7be1856` | совпадает |

Тесты на `e27c36c` (7 файлов: `test_version_consistency`, `test_wave21_u`, `test_wave21_o`, `test_switch_21i`,
`test_precipitation_bl35`, `test_kwn_step_cap_22b`, `test_tab_snapshot_compare`) — `152 passed, 3 warnings in
340.38s`. `git push origin HEAD:refs/heads/main` — `3e2e318..e27c36c`. Ветка `wave21-x` от `e27c36c`; первый
коммит `1b9c5c6` — задание без строки «/caveman ultra».

## ШАГ 1. Реестр (`e277b58`)

`tasks/REGISTER.md`, тексты мастера дословно, хеши слияний — `5a9dcd5` (21-У), `e27c36c` (21-Ф):

- а) строки 21-У (`:1032`) и 21-Ф (`:1033`) — состояние; новые строки 21-Х (`:1034`) и 21-Ц (`:1035`);
- б) приёмка 21-У (`:1085`), приёмка 21-Ф (`:1087`), решения владельца 26.09.2026, продолжение (`:1089`);
- в) «Ошибка мастера (21-Ф)» (`:1127`), «(3В)» (`:1131`), «(21-П, документы)» (`:1135`), «(22-А, число)» (`:1139`),
  перед «## Волна 22»;
- г) BL-62 (`:322`), BL-68 (`:328`), BL-70–BL-72 (`:330–332`), новые BL-73–BL-76 (`:333–336`).

## ШАГ 2. Текст остановки — вариант А (`e9fb7ff`)

`app/thermogar_precipitation.py`:

- `_composition_stop_note` (`:371`) получила четвёртый аргумент `kind`; слова «, баланс масс нарушен»
  (`:377`) — только при `kind == "разрыв"`, в обеих ветках. Остальные слова, `KWN_COMPOSITION_STOP_CAUSE`,
  `_solver_failure_note` не менялись;
- `run_precipitation` (`:1346–1355`): сначала `_stop_diagnostics(…)`, потом
  `_composition_stop_note(…, stop_diagnostics["kind"])`.

Было → стало (Ti −9.864·10⁻⁵, 3.885 с; `KWN_COMPOSITION_STOP_CAUSE` — «Причина: …» без изменений):

| Ветка | Было (любой `kind`) | Стало, «перелёт» | Стало, «разрыв» |
|---|---|---|---|
| ниже нуля | «Расчёт остановлен на 3.885 с модельного времени (0.001079 ч): доля Ti в матрице ушла ниже нуля, баланс масс нарушен. Показана часть расчёта до остановки. Причина: …» | «… доля Ti в матрице ушла ниже нуля. Показана часть расчёта до остановки. Причина: …» | как было |
| «стала … ат.%» | «… доля Nb в матрице стала 0 ат.%, баланс масс нарушен. Показана часть расчёта до остановки. Причина: …» | «… доля Nb в матрице стала 0 ат.%. Показана часть расчёта до остановки. Причина: …» | как было |

Тесты: `tools/test_wave21_o.py` — `test_composition_stop_note_below_zero` (`:128`) и
`test_composition_stop_note_zero_keeps_the_number` (`:151`) вызываются с `"перелёт"` и ждут новый текст; отдельные
проверки «разрыв» с прежним текстом — `test_composition_stop_note_below_zero_broken_balance` (`:140`),
`test_composition_stop_note_zero_broken_balance` (`:160`). Было: вызов без `kind`, ожидание «ушла ниже нуля,
баланс масс нарушен. Показана часть…» и «стала 0 ат.%» без проверки хвоста. `tools/test_wave15_z.py:324` — вызов с
`"разрыв"` (отступление 1).

## ШАГ 3. Номер 0.5.0 (`9882fd6`)

14 строк в 9 файлах, на дереве ШАГА 0 номера строк совпали с `results/wave21_f/versiya.csv` (кроме подписи панели:
там `:7111`, на дереве — `:7121`, как в задании):

| Файл:строка | Стало |
|---|---|
| `app/thermogar_release_policy.py:25` | `APP_STAGE: Final = "0.5.0"` |
| `app/thermogar_release_policy.py:26` | `APP_VERSION: Final = "0.5.0"` |
| `app/ThermoGar_app.py:7121` | `"ThermoGar 0.5.0 — исследовательское ПО. "` |
| `packaging/product-version.json:6` | `"display_version": "0.5.0",` |
| `packaging/product-version.json:7` | `"vi_product_version": "0.5.0.0",` |
| `README.md:1` | `# ThermoGar 0.5.0` |
| `README.md:101` | `` `ThermoGar-0.5.0-win64.exe` `` |
| `QUICK_START_THERMOGAR.md:1` | `# ThermoGar 0.5.0 — быстрый старт` |
| `USER_GUIDE_THERMOGAR.md:1` | `# ThermoGar 0.5.0 — руководство пользователя` |
| `docs/FEATURES.md:1` | `# ThermoGar 0.5.0 — что умеет программа` |
| `docs/guide/README.md:1` | `# ThermoGar 0.5.0 — иллюстрированное руководство` |
| `docs/guide/README.md:23` | `` `ThermoGar_Guide_0.5.0.html` `` |
| `tools/make_guide_screens.py:46` | `HTML_NAME = "ThermoGar_Guide_0.5.0.html"` |
| `tools/make_guide_screens.py:47` | `HTML_TITLE = "ThermoGar 0.5.0 — иллюстрированное руководство"` |

`HANDOFF.md`, `CHANGELOG.md`, `packaging/build_installer.ps1`, исторические упоминания — не тронуты.

## ШАГ 4. Съёмка (`05e1490`, журнал — `7436ddb`)

`python -X utf8 tools/make_guide_screens.py --no-html` — 9 сценариев, **56 кадров** в `docs/guide/img/`,
`_manifest.json` перезаписан целиком; 683 с, папка `img` — 4,0 МБ. Журнал прогона —
`results/wave21_x/zhurnal_semki.txt`.

Сбои и правки `tools/make_guide_screens.py` по месту:

1. Первый полный прогон упал в сценарии `soobshcheniya` на первом шаге: `set_composition` искал в списке основы
   пункт `FE`, а с 21-Ж список показывает символ элемента — `Fe`
   (`TimeoutError: … waiting for get_by_role("option", name="FE", exact=True)`). Правка — `:1088`:
   `name=balance.capitalize()` (в поле по-прежнему вводится `FE`).
2. Прогон `--only soobshcheniya` упал дальше: список «Фаза-выделение» (718) после пересчёта от соседнего списка
   не раскрылся по щелчку — фокус стоял, вариантов не было (`Locator.wait_for: Timeout … get_by_role("option")`).
   Правка — `set_selectbox`, `:387–395`: если за 5 с варианты не появились, список раскрывается клавишей
   `ArrowDown`. После неё `--only soobshcheniya` прошёл.
3. Затем — снова полный прогон всех 9 сценариев (чтобы `_manifest.json` был целым), без сбоев. Пересъёмок
   отдельных кадров после него нет.

Каждый кадр просмотрен: цели в рамках, чужих ошибок нет. Пустой результат — только на `soobshcheniya-05`, как и
задумано сценарием (выдержка 10⁻⁶ ч; цель кадра — предупреждение о зародыше).

Readings, дословно (`_manifest.json`):

- `soobshcheniya-03`, `stop_note`: «Расчёт остановлен на 3.773 с модельного времени (0.001048 ч): доля Ti в
  матрице ушла ниже нуля. Показана часть расчёта до остановки. Причина: при движущей силе по базе зарождение
  практически безбарьерное, и выделение вычерпывает добавки из матрицы быстрее, чем модель это выдерживает.» —
  без «баланс масс нарушен», то есть `kind` «перелёт» (в `tools/test_wave21_x.py` проверено и по
  `stop_diagnostics["kind"]`). `kwn_718_inputs`: `{'Температура, °C': '700', 'Время выдержки, ч': '100',
  'Межфазная энергия, Дж/м²': '0.095', 'Молярный объём матрицы, см³/моль': '7.14562', 'Молярный объём выделения,
  см³/моль': '7.3', 'Плотность объёмных центров, 1/м³': '8.427732e+28'}`.
- `soobshcheniya-05`, `nucleus_warning`: «Радиус зародыша 1.02 нм (оценка при 800.0 °C) больше начального
  максимального радиуса сетки 0.5 нм, поэтому первые зародыши записываются мельче своего размера, пока модель не
  расширит сетку размеров. Итоговые доля, радиус и число частиц от этого почти не меняются, но начало зарождения на
  графиках искажено: доля и радиус занижены, число частиц завышено. Задайте «Начальный максимальный радиус» больше
  1.02 нм.»

Замер времени kinetika (Ni, `AL=15` ат.%, 800 °C, 1 ч, умолчания раздела): в журнале съёмки времени отдельного
расчёта нет, поэтому — отдельный прогон с перезапуском приложения,
`results/wave21_x/scripts/zamer_kinetika.py` (`make_guide_screens.py --only kinetika`, кадры — во временную
папку). От нажатия «Рассчитать кинетику выделений» до варианта «Итоги» — 58,2 с, до конца пересчёта — **60,6 с**;
второй прогон — те же 58,2 и 60,6 с. Округлено до 5 с — **60 с**. Итог — `results/wave21_x/zamer/zamer_kinetika.json`,
сводка «Итоги» над графиками (в кадр `kinetika-05` не входит) — `results/wave21_x/zamer/kinetika_svodka.png`:
итоговая объёмная доля 25.8079 %, средний радиус 19.9199 нм, плотность частиц 6.31042e+21 1/м³, «Укрупнение на
плато» — да.

## ШАГ 5. Тексты (`fabf8d2`)

Скрипт — `results/wave21_x/scripts/teksty.py` (каждая замена — по точному прежнему тексту), опись —
`results/wave21_x/teksty.csv`: **17 правок в 5 файлах** — `docs/guide/03-zatverdevanie.md` 2,
`docs/guide/05-svoystva.md` 2, `docs/guide/06-kinetika.md` 8, `docs/FEATURES.md` 3,
`docs/LIMITS_OF_APPLICABILITY.md` 2. Из них по пунктам 1–13 мастера — 15 (п. 4 — три числа), по п. 14 — 2 числа.

| П. | Файл:строка после правки | Что |
|---|---|---|
| 1 | `03-zatverdevanie.md:52` | «Вариант **«Выгрузка»** переключателя → …» |
| 2 | `05-svoystva.md:20` | «покрытие физической базы по массе 100 %» |
| 3 | `06-kinetika.md:31–33` | «… считается около 60 с …» (замер ШАГА 4) |
| 4 | `06-kinetika.md:50–51` | 24,7 % → 25,8 %; около 4 нм → около 20 нм; 6,6·10²³ → 6,3·10²¹ 1/м³; «Укрупнение на плато: да» — сходится |
| 5 | `06-kinetika.md:81–85` | пункт «… ушла ниже нуля» |
| 6 | `06-kinetika.md:87–89` | цитата — `stop_note` кадра `soobshcheniya-03` |
| 7 | `06-kinetika.md:98–99` | «… (0,2…10 нм, 80 классов) — остановка на 3,773 с»; сетка — `app/thermogar_precipitation.py:1732–1752` (0.2, 10.0, 80) |
| 8 | `06-kinetika.md:101` | подпись «… на 3.773 с модельного времени» над переключателем видов» |
| 9 | `FEATURES.md:118–126` | абзац и цитата `stop_note` |
| 10 | `FEATURES.md:152–154` | T₀ 200–950 °C; KWN стали 0,01 ч — около 5 мин |
| 11 | `FEATURES.md:175` | KWN на Ni 100 ч — около 3 мин |
| 12 | `LIMITS_OF_APPLICABILITY.md:170–176` | абзац BL-35 и 0.5.0 |
| 13 | `LIMITS_OF_APPLICABILITY.md:178–183` | абзац «До выпуска 0.5.0 …» |
| 14 | `05-svoystva.md:20` | плотность 7555,1 → 7575,7 кг/м³ (`svoystva-02`) |
| 14 | `03-zatverdevanie.md:35` | расчётный ликвидус 650,0 → 645,0 °C (`zatverdevanie-04`: 644.9609) |

Остальные числа глав с кадрами сходятся: `raschety-03/06` (95,59 / 4,41 %, 60,6 и 9,9 ат.% Cr, 20 из 32,
95,6 / 74,5 %, 4,43 → 1,24 %), `svoystva-04/05` (0,682 / 0,318, 0,696 / 0,304, 212,0 ГПа, 81,5 ГПа, 0,301, разброс
1,7 ГПа), `zatverdevanie-04` (529,7 °C), `diagrammy-02/04` (35 ат.%, 600–1600 °C, шаги 5 и 50), `energii-04/05`
(1937, 1129, 1526,9 Дж/моль), `soobshcheniya-01` (12 фаз).

Расхождения по сути — не переписаны, докладываю (кадры — в `docs/guide/img/`):

1. **`06-kinetika.md:48–49`, кадр `kinetika-05`.** «до 0,01 ч ничего не происходит, за следующие несколько минут
   доля выходит на …» — на новом графике первое обнаружение выделений 1,5·10⁻⁵ ч, к 10⁻⁴ ч (0,4 с) доля уже около
   22 %, дальше до 1 ч медленно растёт до 25,8 %. Средний радиус к концу — около 20 нм (было около 4). Прежний кадр
   снят в 0.3.1; ход поменялся с тех пор (кадр 0.3.1: рост около 0,01–0,02 ч).
2. **`03-zatverdevanie.md:43`, кадр `zatverdevanie-05`.** «Между 650 и 640 °C затвердевает больше половины
   объёма» — на кривой при 640 °C расплава ещё около 70 %, половина проходит около 633 °C. Так было и на кадре
   0.3.1. Там же: в сводке `zatverdevanie-04` теперь два столбца — «Расчётный ликвидус» 644.96 °C и «T при доле
   твёрдого 0.01 % по траектории» 649.9966 °C (прежний «ликвидус»); число в тексте поправлено по первому (п. 14).
3. **`06-kinetika.md:129–131`, кадр `kinetika-08`.** «За 100 ч при 1200 °C перемешивание захватывает лишь несколько
   десятков микрон около границы … узкая полоса» — на новом профиле состав меняется примерно от 600 до 1500 мкм,
   то есть на сотни микрон. На кадре 0.3.1 полоса была узкой (десятки микрон).
4. **Цитаты с экрана разошлись словами:** `01-raschety.md:57–59` (пустое решение; на экране — «pycalphad не
   нашёл ни одной фазы … на части составов расчёт не сходится …», reading `empty_solution` кадра
   `soobshcheniya-02`); `06-kinetika.md:74–77` и `docs/FEATURES.md:112–116` (зародыш; на экране — «пока модель не
   расширит сетку размеров», в главах — «пока kawin не достроит сетку»).
5. **Обозначения элементов:** `docs/guide/README.md:51` (`FE`), `01-raschety.md:3` («основа FE»),
   `03-zatverdevanie.md:12` (`AL`), `06-kinetika.md:112` («основа NI») — на экране с 21-Ж `Fe`, `Al`, `Ni`.
6. **Не проверено по кадру:** `06-kinetika.md:132` («Над графиком метрика «Макс. ошибка баланса»») — в кадр
   `kinetika-08` не входит.

`USER_GUIDE_THERMOGAR.md`, `QUICK_START_THERMOGAR.md`, `README.md` (кроме номера версии) — не тронуты.

## ШАГ 6. HTML (`96c8c05`)

`python -X utf8 tools/make_guide_screens.py --html` → `docs/guide/ThermoGar_Guide_0.5.0.html`, 5,4 МБ. `<title>` и
заголовок — «ThermoGar 0.5.0 — иллюстрированное руководство»; встроенных картинок `data:image/png;base64` — 56,
внешних ссылок на картинки нет. HTML 0.4.1–0.4.4 не изменились. `tools/test_version_consistency.py` —
`92 passed`.

## ШАГ 7. Тесты и регрессия

Новый `tools/test_wave21_x.py` (`5c86027`), 6 тестов:

| Тест | Что проверяет |
|---|---|
| `test_overshoot_note_has_no_broken_balance[…]` ×2 (`:31`) | «перелёт», ниже нуля и «стала 0 ат.%»: «… . Показана часть расчёта до остановки.», без «баланс масс нарушен» |
| `test_broken_balance_note_keeps_the_words[…]` ×2 (`:39`) | «разрыв»: «…, баланс масс нарушен. Показана часть …» |
| `test_718_stop_is_overshoot_without_broken_balance` (`:44`) | 718, 700 °C, 95 мДж/м² (как `test_precipitation_bl35.py`): `stop_diagnostics["kind"] == "перелёт"`, в `stop_note` нет «баланс масс нарушен» |
| `test_release_number_and_guide` (`:56`) | `APP_VERSION == "0.5.0"`, есть `docs/guide/ThermoGar_Guide_0.5.0.html` |

Поправленные: `tools/test_wave21_o.py` (ШАГ 2), `tools/test_wave15_z.py:324` (отступление 1).

### Полная регрессия

`results/wave21_x/scripts/run_regressiya.sh` — копия 21-У: изменены только строка заголовка, папка вывода
`results/wave21_x/testy` и состояние `tg21x_tests_state`. Запуск — с `PYTHONDONTWRITEBYTECODE=1`. Один поток,
26.09 22:52 — 27.09 01:01; `test_ui_f` — одним процессом (свободно 8,24 ГиБ), журнал памяти —
`results/wave21_x/testy/memlog_test_ui_f.jsonl`. Полные журналы — `results/wave21_x/testy/*.log` (в `.gitignore`,
в коммит не входят).

| Файл | Итог |
|---|---|
| `test_backend_calculations` | 57 passed, 6 warnings in 1197.02s |
| `test_chart_celsius_ticks` | 17 passed |
| `test_chart_legend_theme` | 12 passed |
| `test_chart_theme_21e` | 73 passed |
| `test_database_repair` | 44 passed |
| `test_density` | 77 passed |
| `test_density_below_pdb` | 5 passed |
| `test_density_thermal_expansion` | 11 passed, 1 xfailed |
| `test_dropped_phases_text` | 2 passed |
| `test_equilibrium_solidus_fallback` | 19 passed |
| `test_error_log_worker_21z` | 4 passed |
| `test_kwn_step_cap_22b` | 9 passed, 1 warning |
| `test_liquidus_bisection` | 2 passed |
| `test_parallel_engine` | 15 passed |
| `test_parallel_integration` | 6 passed |
| `test_phase_description_order_words` | 11 passed |
| `test_phase_description_stub_keys` | 9 passed |
| `test_phase_presets` | 21 passed |
| `test_phase_presets_control` | 1 passed |
| `test_physical_overrides_toggle` | 11 passed |
| `test_precipitation_bl35` | 11 passed, 1 warning |
| `test_precipitation_grid` | 32 passed, 12 warnings |
| `test_sidebar_composition_error` | 9 passed |
| `test_style_21z` | 11 passed |
| `test_switch_21i` | 13 passed |
| `test_tab_snapshot_compare` | 8 passed |
| `test_ui_f` | 59 passed in 1958.11s |
| `test_ui_g` | 32 passed, 5 warnings in 407.16s |
| `test_ui_h` | 26 passed |
| `test_user_errors_21zh` | 47 passed |
| `test_version_consistency` | 92 passed |
| `test_wave15_z` | 15 passed, 2 warnings |
| `test_wave21_m` | 22 passed |
| `test_wave21_o` | 13 passed, 1 warning |
| `test_wave21_u` | 8 passed |
| `test_wave21_x` | 6 passed, 1 warning |
| 12 файлов unittest (`thermogar_active_state_io`, `db_cache`, `fe_internal_smoke`, `paths`, `restricted_fe_core`, `secure_io`, `state_migration`, `verified_equilibrium`, `verified_loaders`, `verified_physical`, `verified_properties`, `verified_state`) | Ran 203 tests / OK |
| 7 сценариев (`converter_patch`, `diffusion`, `fe_database`, `physical`, `precipitation`, `properties`, `self_test`) | RESULT: PASSED (`thermogar_precipitation_test` — Final volume fraction 6.599577401641879 %) |

Сумма: 36 файлов pytest — 810 passed, 1 xfailed (в 21-У — 802 и 1 xfailed; плюс 6 в `test_wave21_x` и 2 в
`test_wave21_o`). 12 файлов unittest — 203 OK. 7 сценариев — PASSED. Красных — 0.

`app/__pycache__/` (4 файла, 26.09 11:54) и `tools/__pycache__/make_guide_screens.cpython-311.pyc` (24.09 09:18)
лежат в дереве с до начала 21-Х (BL-60 и 21-Р); в `.gitignore`, не трогал.

## Отступления

1. **`tools/test_wave15_z.py:324`** — вызов `_composition_stop_note` дополнен аргументом `"разрыв"`. В задании
   назван только `test_wave21_o.py`, но без четвёртого аргумента тест падал бы `TypeError`; «разрыв» сохраняет
   прежний текст, который тест выводит на экран через AppTest (место показа, не слова).
2. **Две правки `tools/make_guide_screens.py`** (`:387–395`, `:1088`) и повторный полный прогон съёмки — ШАГ 4.
3. **Время kinetika — отдельным прогоном**, а не по журналу: в журнале съёмки есть только время сценария целиком
   (116–118 с вместе с диффузией). Скрипт замера — `results/wave21_x/scripts/zamer_kinetika.py`.
4. **Журнал съёмки — `zhurnal_semki.txt`**, а не `.log`: `*.log` в `.gitignore`.
5. **`teksty.csv`: «файл:строка» — после правки** (строки прежнего текста — по заданию).
6. **П. 10 и абзацы п. 3, 5, 7, 9, 12, 13 перенесены по ширине главы** (около 100 знаков), текст — мастера дословно.
7. **Кадры удалялись и писались самим `make_guide_screens.py`** (прежние PNG сценария стираются перед съёмкой, как
   в 17-Д); неудачный первый прогон оставил несжатые кадры, их перезаписал второй полный прогон.

## Вывод git

Реестр: строка 21-Х — «**сдано, мастер не смотрел.**» и итоги числами. Вывод git — после пуша, ниже.
