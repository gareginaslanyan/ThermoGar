# Отчёт 21-И: слияние 21-З в main; «Кинетика» и «Затвердевание» — переключатель вместо вкладок (N-4); замер длинных форм для 9Б; полная регрессия

Работа шла в `D:\Pets\ThermoGar-w21b`, ветка `wave21-i` от слияния ШАГА 0. В `D:\Pets\ThermoGar` ничего не менялось: оттуда запускался только интерпретатор `.venv-windows\Scripts\python.exe`. `D:\Pets\ThermoGar-w21a`, `D:\Pets\Lilith`, установленная программа и `%LOCALAPPDATA%\ThermoGar` не открывались. `databases\`, `configs\`, `packaging\`, `docs\`, `tools\make_guide_screens.py`, `tools\tab_snapshot.py`, `tools\study_*.py` не менялись. Файлов в `app\` не добавлено. Новых слов на экране нет: подписи переключателей — заголовки разделов, которые уже стоят на экране, варианты — прежние названия вкладок. Ничего не удалялось: всё лишнее — в `_to_delete\21i_*\` с описью sha256 (перечень — в отступлениях).

## Итог одной строкой

Слияние 21-З в `main` — `ce3bd53`, дерево совпало. Три ряда вкладок заменены переключателем; 20 виджетов внутри видов сохраняют значение при смене вида. Текст выбранного варианта — 4.87:1 / 5.23:1 во всех состояниях. Кадры 11–14 и 22–28 сняты в двух темах. Длинные формы: основная кнопка на первом экране только на 2 экранах из 21. Регрессия 50 файлов зелёная; тест, ждавший вкладки, поправлен в 2 файлах.

## ШАГ 0. Слияние 21-З

- `git status --short` до начала: только `?? _to_delete/`.
- `git ls-remote origin main wave21-z`: `8fbd0c02bd366acd9a272cbce863a95386b6d148`, `28993752ad5ba64c540c48b9273fbc5da13e409c` — совпали с заданием.
- `git switch --detach origin/main`, `git merge --no-ff origin/wave21-z -m "Merge wave21-z: …"` — без конфликтов.
- **Хеш слияния: `ce3bd5365e7a71f8c29a485be4f313c815907eb2` (`ce3bd53`).**
- **Дерево:** `git rev-parse "HEAD^{tree}"` = `401561e5d4ff2eac992d42d3037dc39079bd3dcd` — совпало с деревом `wave21-z`.
- `git push origin HEAD:refs/heads/main`: `8fbd0c0..ce3bd53`.
- Ветка `wave21-i` от `ce3bd53`. Первый коммит — задание дословно (`tasks/WAVE21_I_OPUS.md`, `c974fc2`).

## ШАГ 1. Реестр (`2e27f6b`)

- Строка 21-З: начало ячейки состояния — «**принята мастером 25.09.2026 с замечанием (ниже); влита в `main` (`ce3bd53`).**», остальное в ячейке прежнее.
- После неё — строки 21-И («**в работе.**») и 21-К, как в задании.
- После абзаца «Приёмка 21-Ж2 мастером…», перед «### Ошибка мастера (21-В)», — два абзаца: «Решение владельца по дизайну, 24.09.2026 (после приёмки 21-Е)…» и «Приёмка 21-З мастером (25.09.2026)…».
- В таблице бэклога после BL-63 — строка BL-64.

Тексты взяты из задания дословно. Правка — скриптом, концы строк файла (LF) прежние.

## ШАГ 2. Переключатель вместо вкладок (`b84301f`, `f8272da`)

### Что изменено

| Место | Было | Стало (файл:строка) |
|---|---|---|
| «Кинетика» → «Диффузия и гомогенизация» | `st.tabs([...])`, `app/thermogar_diffusion.py:1499` | `st.segmented_control("Диффузия и гомогенизация", […], default="Однофазная пара", required=True, label_visibility="collapsed", key="kinetics_diffusion_view", persist_state="session")` — `app/thermogar_diffusion.py:1510–1522`; виды — `if` / `elif` по значению: `:1524`, `:1632`, `:1797` |
| «Кинетика» → «Выделения», после расчёта | `st.tabs([...])`, `app/thermogar_precipitation.py:1674` | `st.segmented_control("Кинетика выделений", […], default="Итоги", …, key="precipitation_result_view", persist_state="session")` — `app/thermogar_precipitation.py:1675–1683`; виды — `:1684`, `:1689`, `:1696`, `:1699` |
| «Затвердевание», после расчёта | `st.tabs([...])`, `app/ThermoGar_app.py:10807` | `st.segmented_control("Затвердевание", […], default="Сводка", …, key="solidification_result_view", persist_state="session")` — `app/ThermoGar_app.py:10807–10820`; виды — `:10822`, `:10866`, `:10900`, `:10955` |
| Выбранный вариант, наведение и фокус | фон primary с альфой 0.2 (Streamlit) | `app/style.css:65–72`: `div[data-testid="stButtonGroup"] button[data-variant="segmented_control"][aria-checked="true"]:not(:disabled):hover` и `…:focus-visible` — `background-color: light-dark(rgba(31, 96, 193, 0.1), rgba(92, 151, 232, 0.1))`. Кольцо фокуса не трогал |
| Комментарий BL-35 | «над вкладками» | «над переключателем видов (21-И; до того вкладки)», `app/thermogar_precipitation.py:1667–1668` |

Варианты — те же названия в том же порядке. В каждом из трёх мест исполняется только выбранный вид: цепочка `if` / `elif` заменила `with <вкладка>:` без изменения отступов тела.

**Переменные видов ниже переключателя не используются — сверено.**
- «Диффузия»: цепочка видов — последний оператор `render_kinetics_section`.
- «Выделения»: цепочка видов — последний оператор `render_precipitation_section`.
- «Затвердевание»: цепочка видов — последний оператор блока `if "solidification_result" in st.session_state …`; дальше идёт `with energy_tab:` на уровне модуля.

Тест `test_only_selected_view_runs` проверяет по AST: значение переключателя читается ровно столько раз, сколько вариантов.

**Селектор выбранного варианта взят по DOM Streamlit 1.62.** У варианта нет `data-testid`. Это `<button data-variant="segmented_control" role="radio" aria-checked="true" data-selected="true">` внутри `role="radiogroup"` с `aria-label` = подпись, в `div[data-testid="stButtonGroup"]`. Первый вариант правила (`b84301f`) выбирал `stBaseButton-segmented_controlActive` по строке бандла и не действовал. Замер ШАГА 3б это показал; селектор поправлен в `f8272da` (отступление 2).

### Виджеты внутри видов с `persist_state="session"` (20)

Все 20 уже имели `key`; виджетов без `key` не было, новых ключей нет.

| Файл:строка | Виджет | key | Вид |
|---|---|---|---|
| `app/thermogar_diffusion.py:1252` | `st.radio` «Единицы графика состава» (`_result_display`) | `{state_key}_output_units` → `kin_single_<база>_output_units`, `kin_hom_<база>_output_units` | «Однофазная пара», «Многофазная гомогенизация» (после расчёта) |
| `app/thermogar_diffusion.py:1349` | `st.selectbox` «Элемент-основа» (`_common_inputs`) | `{prefix}_balance_<база>` | оба вида пары |
| `app/thermogar_diffusion.py:1357` | `st.radio` «Единицы исходных составов» | `{prefix}_units_<база>` | оба |
| `app/thermogar_diffusion.py:1369` | `st.text_area` «Левая сторона» | `{prefix}_left_<база>` | оба |
| `app/thermogar_diffusion.py:1377` | `st.text_area` «Правая сторона» | `{prefix}_right_<база>` | оба |
| `app/thermogar_diffusion.py:1385` | `st.number_input` «Температура выдержки, °C» | `{prefix}_temperature_<база>` | оба |
| `app/thermogar_diffusion.py:1395` | `st.number_input` «Длина области, мкм» | `{prefix}_length_<база>` | оба |
| `app/thermogar_diffusion.py:1404` | `st.number_input` «Граница пары, % (1–99)» | `{prefix}_interface_<база>` | оба |
| `app/thermogar_diffusion.py:1414` | `st.number_input` «Время, ч» | `{prefix}_time_<база>` | оба |
| `app/thermogar_diffusion.py:1423` | `st.number_input` «Ячеек (12–160)» | `{prefix}_nodes_<база>` | оба |
| `app/thermogar_diffusion.py:1433` | `st.text_area` «Источник и назначение исходных данных диффузии» | `{prefix}_input_provenance_<база>` | оба |
| `app/thermogar_diffusion.py:1562` | `st.selectbox` «Фаза для всего профиля» | `kin_single_phase_<база>` | «Однофазная пара» |
| `app/thermogar_diffusion.py:1683` | `st.multiselect` «Фазы локального равновесия» | `kin_hom_phases_<база>` | «Многофазная гомогенизация» |
| `app/thermogar_diffusion.py:1695` | `st.selectbox` «Модель эффективной подвижности» | `kin_hom_function_<база>` | «Многофазная гомогенизация» |
| `app/thermogar_diffusion.py:1704` | `st.number_input` «Сглаживающий коэффициент ε (0–0.2)» | `kin_hom_eps_<база>` | «Многофазная гомогенизация» |
| `app/thermogar_diffusion.py:1715` | `st.number_input` «Лабиринтный фактор (1–2)» | `kin_hom_lab_<база>` | «Многофазная гомогенизация» |
| `app/ThermoGar_app.py:10867` | `st.selectbox` «Какой метод показать» | `solidification_phase_method` | «Твёрдые фазы» |
| `app/ThermoGar_app.py:10906` | `st.selectbox` «Элемент в остаточном расплаве» | `solidification_liquid_element` | «Остаточный расплав» |
| `app/ThermoGar_app.py:10913` | `st.radio` «Единицы состава расплава» | `solidification_liquid_units` | «Остаточный расплав» |
| `app/ThermoGar_app.py:10935` | `st.selectbox` «Таблица для метода» | `solidification_liquid_method` | «Остаточный расплав» |

`_common_inputs` вызывается в двух видах с `prefix` `kin_single` и `kin_hom`. В «Выделениях» внутри видов только таблицы, графики, раскрывающийся блок и 6 кнопок выгрузки: виджетов с `persist_state` нет. «Покрытие базы подвижностей» и «Выгрузка» — тоже без таких виджетов. Кнопки, кнопки выгрузки, `data_editor` и `file_uploader` не трогал. Функции других модулей, вызываемые из видов, сверены вручную — виджетов в них нет: `render_quality_panel`, `render_validation_report`, `render_error_record`, `render_friendly_error`, `release_calculation_button`, `release_download_button`.

### Тест `tools/test_switch_21i.py` (13)

- `test_switch_replaces_tabs` ×3 — по AST: `st.tabs` с этими названиями нет; `st.segmented_control` с подписью, вариантами, `default` = первый, `required=True`, `label_visibility="collapsed"`, ключом и `persist_state="session"`.
- `test_only_selected_view_runs` ×3 — цепочка `if` / `elif` по значению переключателя: все варианты по порядку, без `else`. Значение больше нигде не читается.
- `test_widgets_inside_views_persist` ×3 — у каждого `st.<виджет с persist_state>` внутри видов есть `key` и `persist_state="session"`. Виджеты ищутся и в функциях своего модуля, которые вызываются из видов.
- `test_persistent_widget_count` — 16 / 0 / 4.
- `test_selected_option_keeps_rest_background_on_hover_and_focus` — правило `style.css`: только `:hover` и `:focus-visible` выбранного варианта, только `background-color`. Правил на невыбранный вариант, `outline`, `box-shadow`, `color`, `border-color` нет.
- `test_rest_background_is_primary_with_alpha_01` — `primaryColor` в `config.toml`: #1F60C1 и #5C97E8 = rgb(31, 96, 193) и rgb(92, 151, 232).
- `test_value_survives_view_switch_and_switch_cannot_be_cleared` — AppTest, база ni. В «Однофазная пара» «Левая сторона» меняется на `CR=12, AL=4`. Затем «Покрытие базы подвижностей»: поля и кнопки однофазной пары нет. Затем «Однофазная пара»: значение то же. `set_value(None)` оставляет «Однофазная пара» и значение. Предупреждений про Session State и значение по умолчанию нет.

**Проверка, что тест ловит ошибку.** Без `persist_state` у «Левой стороны» (временная правка, файл восстановлен побайтно) два теста красные. Значение вернулось к умолчанию: `'Cr=7.7, Al=5.4' == 'CR=12, AL=4'`.

### Тесты, которые ждали вкладки: выбор вида перед проверкой

Ожидания по содержимому не менялись.

| Файл:строка | Тест | Что добавлено |
|---|---|---|
| `tools/test_ui_g.py:141–148` | — | `DIFFUSION_VIEW_KEY`, `HOMOGENIZATION_VIEW`, `select_view(app, key, view)` — `app.segmented_control(key=…).set_value(view).run()` |
| `tools/test_ui_g.py:228–241` | `test_kinetics_section_renders[ni, al, fe]` | кнопка однофазной пары — в виде по умолчанию; затем `select_view(… «Многофазная гомогенизация»)`, кнопка гомогенизации. Проверка лишних галочек — по галочкам обоих видов |
| `tools/test_ui_g.py:311` | `test_diffusion_homogenization[ni, fe]` | `select_view` перед вводом |
| `tools/test_ui_g.py:352` | `test_homogenization_unavailable_on_al_is_explained` | `select_view` перед вводом |
| `tools/test_ui_g.py:570–572` | `test_diffusion_number_inputs_are_bounded[kin_hom]` | `select_view`, если `prefix == "kin_hom"` |
| `tools/test_ui_g.py:722–723` | `test_fe_shipped_defaults_are_the_declared_ones` | `select_view` перед проверкой `kin_hom_phases_fe` |
| `tools/test_ui_f.py:436–439` | `test_solidification` (9 случаев) | после расчёта — вид «Выгрузка» (`solidification_result_view`), затем проверка трёх выгрузок |

`tools/test_wave15_z.py:333` (`test_stop_note_is_shown_above_the_tabs`) не правил: он зелёный. Но `for tab in app.tabs` теперь пустой: вкладок у результата «Выделений» нет, и эта часть проверки стала пустой. Порядок «над видами» тест по-прежнему проверяет через `app.main.error`.

### Места `make_guide_screens` и `tab_snapshot`, зависящие от прежних вкладок (не правились)

`tools/make_guide_screens.py` — все четыре места ищут `role="tab"`; теперь вариант — `role="radio"` внутри `role="radiogroup"`:
- `:662` — после «Рассчитать затвердевание» ждёт `get_by_role("tab", name="Сводка")`: ожидание до `CALC_TIMEOUT_MS` и сбой сценария «zatverdevanie».
- `:677` — `open_tab(page, "Выгрузка")`: вкладки нет, сбой по `UI_TIMEOUT_MS`.
- `:841` — после «Рассчитать кинетику выделений» ждёт `get_by_role("tab", name="Итоги")`: то же.
- `:853` — `open_tab(page, "Однофазная пара")`: то же.
- Общая функция `open_tab` (`:432–436`) выбирает только `role="tab"`.

В `results/wave21_i/scripts/kadry.py` для этих имён `Page.get_by_role` подменяет `tab` на `radio`. Сам генератор руководства не трогал.

`tools/tab_snapshot.py`, случаи с кнопками и выгрузками внутри переключаемых видов:
- `case_f_solid` (`:602–611`, 9 случаев `f_solid_<база>_<метод>`) — Excel, PNG и ZIP «Затвердевания» в виде «Выгрузка» не выводятся и не перехватываются. Виджетов «Твёрдых фаз» и «Остаточного расплава» в `karkas.txt` нет.
- `case_sh_solid` (`:1075–1078`, 3 случая `sh_solid_*`) — то же.
- `case_g_hom` (`:731–737`, `g_hom_ni`, `g_hom_fe`) — `app.click("kin_hom_run_<база>")` не находит кнопку: вид «Многофазная гомогенизация» не выбран.
- `case_g_hom_al` (`:740–742`) — поля `kin_hom_*` не выводятся; предупреждения про одну фазу нет.
- `g_bounded_kin_hom` (`:1162–1163`, через `case_g_render`) — поля `kin_hom_*` не выводятся.
- `case_g_kwn` (`:757–763`, `g_kwn_ni/al/fe`), `case_g_fe_provenance` (`:766–772`), `case_g_ni_kwn_hour` (`:775–781`) — 6 выгрузок «Выделений» в виде «Экспорт и ограничения» не перехватываются. Графики и таблицы видов «Кинетика и состав» и «Распределение размеров» в `karkas.txt` и `ekran/` не попадают.
- Все случаи: `karkas.txt` вкладки «Кинетика» теперь содержит только вид «Однофазная пара». «Многофазная гомогенизация» и «Покрытие базы подвижностей» больше не исполняются в каждом прогоне, так что с эталоном 20-А расходится каждый случай. После расчётов то же относится к видам «Выделений» и «Затвердевания».

## ШАГ 3. Кадры

Приложение — `results/wave21_i/scripts/run_app.cmd`: копия 21-З, порт 8638, `THERMOGAR_STATE_ROOT=%TEMP%\tg21i_state`, `PYTHONHASHSEED=0`, `--client.toolbarMode auto`. Состояние подготовлено `prepare_state.py`. Окно 1440×900. Один процесс приложения. Свободной памяти при входе — 7.33 ГиБ (порог 3.0).

Скрипты — копии `results/wave21_z/scripts/*` в `results/wave21_i/scripts/`. Поправлены `run_app.cmd`, `prepare_state.py`, `kadry.py`, `run_regressiya.sh`. Новые — `pereklyuchatel.py`, `sokhranenie.py`, `formy.py`. Остальные копии (`knopka.py`, `bylo_stalo.py`, `dom_polya.py`, `sem_faz.py`, `smena_temy.py`, `tablicy.py`, `run_kadry.sh`, `run_tests*.sh`, `run_app_base.cmd`) не запускались и не правились.

`kadry.py`, отличия копии 21-И:
- `results/wave21_i`, `tg21i_state`, порт 8638;
- для 11 имён вариантов переключателей `Page.get_by_role("tab", name=…)` ищет `role="radio"`: вид выбирается щелчком по варианту;
- в данных кадра — выбранный вариант каждого переключателя (`switches`).

### а) Состояния 11–14 и 22–28

Команда: `kadry.py --theme Light|Dark --phases kadry --only zatverdevanie,kinetika --keep 11,12,13,14,22,…,28`. Действия — сценарии руководства, как в 21-Б. Итог — `results/wave21_i/kadry/`: 32 кадра (16 на тему) и 22 серые копии. Имена совпали с `results/wave21_b/kadry/` для этих номеров (сверено `diff`). У каждого кадра в `_manifest.json` выбран нужный вариант: 11–14 — «Затвердевание» / «Сводка» … «Выгрузка»; 22–25 — «Кинетика выделений» / «Итоги» … «Экспорт и ограничения»; 26–28 — «Диффузия и гомогенизация» / три вида.

В 27 (обе темы) — `st.error` «Расчёт не выполнен из-за неверных исходных данных. Для многофазной гомогенизации выберите…». Это как в 21-Б: сценарий нажимает кнопку со значениями по умолчанию.

### б) Переключатель по пикселям

Скрипт `pereklyuchatel.py`. Переключатель «Диффузия и гомогенизация»: выбранный вариант «Однофазная пара», невыбранный — «Многофазная гомогенизация». Метод — как у кнопки 21-З: фон — самый частый цвет внутри варианта, текст — пиксель с наибольшим контрастом к фону. Фокус — Tab с предыдущего элемента (1 нажатие). Кольцо — пиксели вокруг варианта (до 6 px), которые отличаются от кадра покоя. Кадры и `pereklyuchatel.json` — в `results/wave21_i/pereklyuchatel/`.

| Состояние | Светлая: фон / текст / контраст | Тёмная: фон / текст / контраст |
|---|---|---|
| невыбранный, покой | #F8F8F9 / #232529 / 14.46:1 | #17181B / #ECEDEF / 15.15:1 |
| невыбранный, наведение | #EBECEE / #232529 / 12.99:1 | #2D2F32 / #ECEDEF / 11.46:1 |
| выбранный, покой | #E1E8F3 / #1F60C1 / 4.87:1 | #1D2430 / #5C97E8 / 5.23:1 |
| выбранный, наведение | #E1E8F3 / #1F60C1 / 4.87:1 | #1D2430 / #5C97E8 / 5.23:1 |
| выбранный, фокус с клавиатуры | #E1E8F3 / #1F60C1 / 4.87:1 | #1D2430 / #5C97E8 / 5.23:1 |

- Стиль по вычислению: фон выбранного во всех трёх состояниях — `rgba(31, 96, 193, 0.1)` / `rgba(92, 151, 232, 0.1)`. Невыбранный при наведении — штатный `rgba(159, 166, 173, 0.15)` / `rgba(176, 181, 191, 0.15)`.
- Рамка выбранного к окну: #1F60C1 на #F8F8F9 — 5.65:1; #5C97E8 на #17181B — 5.96:1. Рамка невыбранного — #CFD1D5 (1.44:1) и #33373E (1.49:1).
- Кольцо фокуса, штатное: `box-shadow: 0 0 0 3.6px` primary с прозрачностью 0.5, `outline: none`. По пикселям самый частый цвет кольца — #8CACDD, 2.18:1 к окну; самый контрастный пиксель — #7798CB, 2.77:1. В тёмной теме: #395881, 2.44:1; самый контрастный — #476793, 3.07:1. Только замер, правки нет.
- **Текст ниже 4.5:1 — нет ни в одном состоянии:** минимум 4.87:1 (светлая) и 5.23:1 (тёмная). Мастер считал 4.91:1 и 5.17:1.
- До правки селектора (первый прогон, `_to_delete\21i_pereklyuchatel_proba\`) при наведении и фокусе было 4.21:1 и 4.42:1: фон `rgba(…, 0.2)`, как у мастера.

### в) Сохранение значений в браузере

Скрипт `sokhranenie.py`, светлая тема, кадры и `sokhranenie.json` — `results/wave21_i/sokhranenie/`.
- «Кинетика / Диффузия и гомогенизация / Однофазная пара». «Левая сторона»: было `C=0.1, Cr=8` (сеанс открылся на стали), введено `Cr=12, Al=4` (кадр `s1_diffuziya_do`). Затем «Покрытие базы подвижностей»: поля нет (`s2`). Затем «Однофазная пара»: `Cr=12, Al=4` (`s3_diffuziya_posle`) — то же.
- «Затвердевание»: расчёт сценария руководства (Al–4Cu–1Mg, Scheil, 700 °C, шаг 10 °C), 76 с. Вид «Остаточный расплав», «Элемент в остаточном расплаве»: Al → Cu (`s4`). Затем «Сводка»: поля нет (`s5`). Затем «Остаточный расплав»: Cu (`s6_zatverdevanie_posle`) — то же.
- Строк со словами «Session State», «session state», «default value» на странице нет ни на одном из 6 кадров. В журнале сервера (`results/wave21_i/zhurnal/app_shag3.log`) предупреждений нет, «missing ScriptRunContext» — 0.

Приложение закрыто (`taskkill /PID 12376 /T`), порт 8638 свободен. Браузеры закрывали сами скрипты. `%TEMP%\tg21i_state` перенесена в `_to_delete\21i_state\` с описью (113 файлов).

## ШАГ 4. Длинные формы для 9Б

Скрипт `formy.py`: приложение ШАГА 3, светлая тема, окно 1440×900, расчётов нет. Данные — `results/wave21_i/formy/formy_<база>.json`, сводка — `results/wave21_i/formy_tablica.md`.
- Каждый экран: вкладка / подвкладка / вид переключателя, прокрутка в начало.
- Элементы — от начала активной панели до первой основной кнопки включительно. Для каждого: `data-testid`, класс `st-key-…`, подпись до 80 знаков, для раскрывающегося блока — `open`, верх и низ в px от верха окна.
- Содержимое свёрнутых блоков не выводится и в перечень не входит: в 1.62 оно сохраняет размеры, но обрезано.

**Боковая панель в исходном виде — свёрнута.** В новом сеансе при 1440×900 `stSidebar` имеет `aria-expanded="false"` и ширину 0. Базу `formy.py` выбирает, раскрыв панель, затем сворачивает её обратно. Состояние до и после записано в JSON (`sidebar`).

| Экран | Кнопка | ni верх–низ | al верх–низ | fe верх–низ | На первом экране (ni / al / fe) | Элементов до кнопки (ni / al / fe) |
|---|---|---|---|---|---|---|
| Расчёты / Одна температура | Рассчитать равновесие | 535–580 | 535–580 | 535–580 | да / да / да | 3 / 3 / 3 |
| Расчёты / Температурный диапазон | Построить график по температуре | 628–673 | 628–673 | 628–673 | да / да / да | 6 / 6 / 6 |
| Расчёты / Изменение состава | Построить график по составу | 1020–1065 | 1020–1065 | 1020–1065 | нет / нет / нет | 10 / 10 / 10 |
| Диаграммы / Бинарная T–X | Построить диаграмму состояния | 1622–1667 | 1622–1667 | 1622–1667 | нет / нет / нет | 15 / 15 / 15 |
| Диаграммы / Многокомпонентное T–X | Построить многокомпонентное сечение | 1611–1656 | 1611–1656 | 1611–1656 | нет / нет / нет | 13 / 13 / 13 |
| Диаграммы / Тройная при T = const | Построить тройную диаграмму | 1530–1575 | 1530–1575 | 1530–1575 | нет / нет / нет | 13 / 13 / 13 |
| Диаграммы / Карта доли фазы | Построить карту доли фазы | 1785–1830 | 1945–1990 | 1945–1990 | нет / нет / нет | 14 / 15 / 15 |
| Затвердевание | Рассчитать затвердевание | 1052–1097 | 1052–1097 | 1052–1097 | нет / нет / нет | 9 / 9 / 9 |
| Энергии / Энергии фаз | Рассчитать энергии фаз | 1083–1128 | 1083–1128 | 1083–1128 | нет / нет / нет | 7 / 7 / 7 |
| Энергии / Движущая сила | Рассчитать движущую силу | 1189–1234 | 1264–1309 | 1226–1271 | нет / нет / нет | 8 / 8 / 8 |
| Энергии / T₀ | Рассчитать T₀ | 1762–1807 | 1762–1807 | 1762–1807 | нет / нет / нет | 13 / 13 / 13 |
| Свойства / Плотность | Рассчитать плотность и объёмные доли | 1027–1072 | 1480–1525 | 1153–1198 | нет / нет / нет | 4 / 4 / 4 |
| Свойства / Плотность по T | Построить плотность по температуре | 1027–1072 | 1480–1525 | 1153–1198 | нет / нет / нет | 6 / 6 / 6 |
| Свойства / Упругие свойства | Получить фазовые доли | 1093–1138 | 1547–1592 | 1219–1264 | нет / нет / нет | 5 / 5 / 5 |
| Свойства / Вклады упрочнения | Рассчитать вклады | 1508–1553 | 1508–1553 | 1508–1553 | нет / нет / нет | 14 / 14 / 14 |
| Кинетика / Диффузия и гомогенизация / Однофазная пара | Рассчитать однофазную диффузию | 1576–1621 | 1576–1621 | 1576–1621 | нет / нет / нет | 17 / 17 / 17 |
| Кинетика / Диффузия и гомогенизация / Многофазная гомогенизация | Рассчитать гомогенизацию (в al — неактивна) | 1786–1831 | 1946–1991 | 1786–1831 | нет / нет / нет | 20 / 21 / 20 |
| Кинетика / Выделения | Рассчитать кинетику выделений | 2200–2245 | 2317–2362 | 2317–2362 | нет / нет / нет | 21 / 22 / 22 |
| Проекты и данные / Марки и составы | Сохранить текущий состав (кнопка формы) | 929–974 | 929–974 | 929–974 | нет / нет / нет | 8 / 8 / 8 |
| Проекты и данные / Проекты и история | Сохранить проект в папке ThermoGar | 861–906 | 861–906 | 861–906 | нет / нет / нет | 7 / 7 / 7 |
| Проекты и данные / Проверка установки | Проверить базы и запустить три контрольных расчёта | 1541–1586 | 1541–1586 | 1541–1586 | нет / нет / нет | 10 / 10 / 10 |

- «Элементов до кнопки» — без самой кнопки. Раскрывающиеся блоки — отдельными строками; в исходном виде все свёрнуты, кроме «Параметры модели KWN» в «Выделениях» (`expanded=True`, его поля входят в счёт).
- Без основной кнопки (в таблицу не входят): «Свойства / Покрытие физической базы», «Кинетика / … / Покрытие базы подвижностей», «Проекты и данные / Пакетный расчёт», «Паспорт базы», «Как пользоваться», «Справочник фаз».
- Итог: основная кнопка на первом экране (низ ≤ 900) — на 2 экранах из 21, на всех трёх базах одинаково. Дальше всего — «Выделения»: низ 2245 / 2362 px, 2.5–2.6 высоты окна.

## ШАГ 5. Полная регрессия

`results/wave21_i/scripts/run_regressiya.sh` (копия 21-З), среда: `MPLBACKEND=Agg`, `PYTHONHASHSEED=0`, `PYTHONUTF8=1`, `THERMOGAR_STATE_ROOT=%TEMP%\tg21i_tests_state`.
- Все `tools/test_*.py` — `python -B -m pytest -p no:cacheprovider`.
- Все `tools/*_test.py` — `python -B файл`.
- Один поток, файл за файлом, 08:13–10:20. Логи — `results/wave21_i/testy/<файл>.log`, ход — `_hod.log`.

Красных, которые ждали вкладки, в регрессии не было: `test_ui_g` и `test_ui_f` поправлены в ШАГЕ 2, до прогона. Их перечень — выше. Один красный в первом прогоне — `thermogar_paths_test::test_005`, из-за среды (отступление 4). Лог первого прогона — `testy/pervyi_progon/thermogar_paths_test.log`.

**Итог дословно (последняя строка каждого файла):**

| Файл | Итог |
|---|---|
| `test_backend_calculations` | 57 passed, 6 warnings in 1244.49s (0:20:44) |
| `test_chart_celsius_ticks` | 17 passed in 4.83s |
| `test_chart_legend_theme` | 12 passed in 4.16s |
| `test_chart_theme_21e` | 73 passed in 23.72s |
| `test_database_repair` | 44 passed in 261.56s (0:04:21) |
| `test_density` | 77 passed in 204.15s (0:03:24) |
| `test_density_below_pdb` | 5 passed in 44.70s |
| `test_density_thermal_expansion` | 11 passed, 1 xfailed in 38.43s |
| `test_dropped_phases_text` | 2 passed in 0.04s |
| `test_equilibrium_solidus_fallback` | 19 passed in 562.20s (0:09:22) |
| `test_error_log_worker_21z` | 4 passed in 8.19s |
| `test_liquidus_bisection` | 2 passed in 278.48s (0:04:38) |
| `test_parallel_engine` | 15 passed in 65.33s (0:01:05) |
| `test_parallel_integration` | 6 passed in 71.64s (0:01:11) |
| `test_phase_description_order_words` | 11 passed in 3.05s |
| `test_phase_description_stub_keys` | 9 passed in 2.94s |
| `test_phase_presets` | 21 passed in 292.11s (0:04:52) |
| `test_phase_presets_control` | 1 passed in 819.66s (0:13:39) |
| `test_physical_overrides_toggle` | 11 passed in 203.26s (0:03:23) |
| `test_precipitation_bl35` | 11 passed, 1 warning in 34.16s |
| `test_precipitation_grid` | 32 passed, 12 warnings in 149.57s (0:02:29) |
| `test_sidebar_composition_error` | 9 passed in 22.22s |
| `test_style_21z` | 11 passed in 3.51s |
| `test_switch_21i` | 13 passed in 11.56s |
| `test_tab_snapshot_compare` | 8 passed in 1.22s |
| `test_ui_f` | 59 passed in 2104.77s (0:35:04) |
| `test_ui_g` | 32 passed, 5 warnings in 384.99s (0:06:24) |
| `test_ui_h` | 26 passed in 409.14s (0:06:49) |
| `test_user_errors_21zh` | 47 passed in 5.57s |
| `test_version_consistency` | 92 passed in 0.89s |
| `test_wave15_z` | 15 passed, 2 warnings in 21.34s |
| `thermogar_active_state_io_test` | Ran 5 tests in 1.091s / OK |
| `thermogar_converter_patch_test` | PASS: merged TDB has no active -9e6 / RESULT: PASSED |
| `thermogar_db_cache_test` | Ran 10 tests in 0.240s / OK |
| `thermogar_diffusion_test` | Max balance error: 5.999999985739635e-08 / RESULT: PASSED |
| `thermogar_fe_database_test` | RESULT: PASSED / Reports: D:\Pets\ThermoGar-w21b\results\validation\stage13_2 |
| `thermogar_fe_internal_smoke_test` | Ran 15 tests in 0.051s / OK |
| `thermogar_paths_test` | Ran 6 tests in 0.081s / OK (повторный прогон; первый — FAILED (failures=1), отступление 4) |
| `thermogar_physical_test` | RESULT: PASSED |
| `thermogar_precipitation_test` | Final volume fraction, %: 6.599577401641879 / RESULT: PASSED |
| `thermogar_properties_test` | PASS: elastic library round-trip / RESULT: PASSED |
| `thermogar_restricted_fe_core_test` | Ran 15 tests in 0.141s / OK |
| `thermogar_secure_io_test` | Ran 19 tests in 0.430s / OK |
| `thermogar_self_test` | RESULT: SOFTWARE REGRESSION PASSED — NOT MATERIAL QUALIFICATION |
| `thermogar_state_migration_test` | Ran 9 tests in 2.233s / OK |
| `thermogar_verified_equilibrium_test` | Ran 18 tests in 0.180s / OK |
| `thermogar_verified_loaders_test` | Ran 18 tests in 0.194s / OK |
| `thermogar_verified_physical_test` | Ran 24 tests in 0.325s / OK |
| `thermogar_verified_properties_test` | Ran 39 tests in 0.861s / OK |
| `thermogar_verified_state_test` | Ran 25 tests in 0.815s / OK |

Сумма: 31 файл pytest — 752 passed, 1 xfailed (в 21-З — 739; плюс 13 новых `test_switch_21i`). 12 файлов unittest — 203 теста OK. 7 сценариев — RESULT: PASSED.

`test_version_consistency`: счётчик нагрузки 77 (`tools/test_version_consistency.py:95`) не менялся, 92 passed. Файлов в `app/` не добавлено. Новый `tools/test_switch_21i.py` в нагрузку не входит.

**`test_ui_f`** — одним процессом: при входе свободно 6.97 ГиБ, правило ≥ 6.0 ГиБ. `THERMOGAR_MEMLOG=results/wave21_i/testy/memlog_test_ui_f.jsonl`, 59 строк. Пики:

| Тест | Пик дерева процессов, ГиБ | с |
|---|---|---|
| `test_ternary_phase_map[al]` | 4.93 | 63.6 |
| `test_ternary_phase_map[fe]` | 4.70 | 40.4 |
| `test_density_temperature_scan[al]` | 4.52 | 36.0 |
| `test_temperature_scan[al]` | 3.83 | 36.0 |
| `test_temperature_scan[fe]` | 3.24 | 39.4 |
| `test_ternary_phase_map[ni]` | 3.19 | 22.5 |

Пик рабочего набора самого процесса pytest — 3.03 ГиБ. Открытых фигур matplotlib после каждого теста — 0. Всего 2103 с. Пик 4.93 ГиБ — как в 21-З (4.97) и 15-О (4.91).

## ШАГ 6

Реестр — строка 21-И: «**сдано, мастер не смотрел.** …», строка 21-К не менялась. Коммиты на `wave21-i`, `git push -u origin wave21-i`. Вывод `git ls-remote`, `git log` и `git status` — в конце отчёта.

## Отступления

1. **Пустой файл в `%TEMP%`.** Первая команда правки `thermogar_diffusion.py` содержала лишнее `cat > "$TEMP/x.py"` и повисла на чтении ввода. Команда остановлена, правка тогда не прошла. Создался пустой `%TEMP%\x.py`. Он перенесён в `_to_delete\21i_temp_x\` с описью.
2. **Селектор правила `style.css` поправлен вторым коммитом (`f8272da`).** Первый вариант (`b84301f`) выбирал `button[data-testid="stBaseButton-segmented_controlActive"]`. Этот `kind` есть в бандле 1.62, но на странице у варианта `data-testid` нет — правило не действовало. Замер ШАГА 3б показал 4.21:1 / 4.42:1 и остановку скрипта по порогу 4.5:1. По DOM страницы селектор заменён на `div[data-testid="stButtonGroup"] button[data-variant="segmented_control"][aria-checked="true"]`, тест поправлен, замер повторён: 4.87:1 / 5.23:1. Кадры и JSON первого прогона — `_to_delete\21i_pereklyuchatel_proba\`.
3. **Пробные прогоны скриптов перенесены, а не перезаписаны.**
   - `sokhranenie.py`: первый — не раскрыта боковая панель, второй — список не раскрылся вне окна. Файлы — `_to_delete\21i_sokhranenie_proba\` и `\21i_sokhranenie_proba2\`.
   - `formy.py`: первый — рекурсия по переключателю зациклилась, процесс остановлен. Второй — в перечень попадали элементы свёрнутых блоков, остановлен на базе al. Файлы — `_to_delete\21i_formy_proba\` и `\21i_formy_proba2\`.
   - Везде опись sha256.
4. **`thermogar_paths_test::test_005` в первом прогоне красный из-за среды, не из-за кода — как в 21-З (отступление 4).** Тест требует, чтобы в `app/__pycache__` не было байт-кода `thermogar_paths` и других модулей. Там было 27 файлов:
   - 23 от 07:18 — запуск приложения ШАГА 3: `streamlit run` без `-B`, как в `run_app.cmd` 21-З;
   - 4 от 22:27 24.09 — воркеры пула в регрессии 21-З.

   `app/__pycache__` перенесена в `_to_delete\21i_pycache_app\` с описью. Повторный прогон — `Ran 6 tests in 0.081s / OK`. После прогона `app/__pycache__` нет.
5. **`tools/test_wave15_z.py:333` не правил** — тест зелёный, но цикл по `app.tabs` теперь пустой (см. ШАГ 2).
6. **Боковая панель в исходном виде в ШАГЕ 4 — свёрнута.** Так открывается новый сеанс при 1440×900. Для выбора базы её пришлось раскрыть и затем свернуть снова. В кадрах ШАГА 3 `kadry.py` раскрывает панель, как в 21-Б и 21-З.
7. **`thermogar_fe_database_test` пишет отчёты в `results/validation/stage13_2`.** `git status` изменений там не показывает.

## Папки `_to_delete` этой задачи

`21i_temp_x`, `21i_pereklyuchatel_proba`, `21i_sokhranenie_proba`, `21i_sokhranenie_proba2`, `21i_formy_proba`, `21i_formy_proba2`, `21i_state`, `21i_pycache_app` — в каждой `OPIS_sha256.txt`.

## git
