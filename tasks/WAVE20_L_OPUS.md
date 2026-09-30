Задание 20-Л: BL-57, шаг 8 разреза — вкладка «Свойства» в своём модуле: 25 определений контура B4B/B4B2, нужных только ей, и тело вкладки → новый app\thermogar_tab_properties.py, функция render_properties_tab (параметры sidebar и services); определения и тело переносятся без правок, имена головного сценария — прологом из SidebarContext и RunServices; слияние 20-К в main; пять тестов берут перенесённый код из нового модуля; сверка вкладок с эталоном 0.5.0; полная регрессия; реестр (приёмка 20-К, ошибка мастера). Мастер ThermoGar, 30.09.2026. Машина — ноутбук Windows 10, дерево D:\Pets\ThermoGar-w21b. Тяжёлый поток, параллельных задач нет. Это санкция мастера на слияние wave20-k в main (ШАГ 1); wave20-l в main не вливать. Порядок сверки — tasks\WAVE20_V_REPORT.md, раздел «Как сверять шаг разреза с эталоном 0.5.0»; образец шага — tasks\WAVE20_K_OPUS.md, образец переноса определений — tasks\WAVE20_ZH_OPUS.md.

ЗАПРЕТЫ
- Исключить до обхода: D:\Pets\Lilith — не открывать, не обходить, исключать из любого поиска/glob/rg/dir по диску. Поиск — только внутри D:\Pets\ThermoGar-w21b; вне дерева ничего не искать и не читать, в том числе при СТОПе.
- D:\Pets\ThermoGar и D:\Pets\ThermoGar-w21a не трогать. Интерпретатор — D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe (не python3 и не python из PATH); пакеты не ставить и не менять. Интерпретатор не запускается — СТОП и доклад дословным сообщением, без поиска причины.
- После слияния ШАГА 1 меняются только: app\ThermoGar_app.py и новый app\thermogar_tab_properties.py (ШАГ 2), tools\test_version_consistency.py, tools\test_wave21_m.py, tools\test_wave21_ts.py, tools\test_chart_theme_21e.py, tools\test_wave21_u.py (ШАГ 3), results\wave20_l\, tasks\WAVE20_L_OPUS.md, tasks\WAVE20_L_REPORT.md, tasks\REGISTER.md. Нужно другое — СТОП.
- Перенос — только перенос: определения, тело вкладки и прочие строки — байт в байт; переформатирование запрещено. Новых слов на экране нет.
- Каталоги прогонов, состояния и журналы — только в results\validation\ (вне git).
- Ничего не удалять: rm, del, Remove-Item, rmdir не применять — и к своим пробным файлам тоже; лишнее — D:\Pets\ThermoGar-w21b\_to_delete\20l_<что>\ + опись sha256.
- Все запуски Python — с -B -X utf8; MPLBACKEND=Agg, PYTHONHASHSEED=0, PYTHONDONTWRITEBYTECODE=1; свободно не меньше 3 ГиБ на входе; снимок вкладок и регрессия — по очереди. Длинные прогоны (снимок, регрессия) — сразу отдельным процессом, не фоновой задачей оболочки с пределом времени.
- Номера строк и хеши — замер мастера, сверить; тексты — дословно, иначе СТОП. На любом СТОП: остановиться, доложить, не подгонять. Время начала и конца каждого шага — в отчёт.

ШАГ 0. git status --short — только «?? _to_delete/»; любое другое — СТОП. git fetch origin. git ls-remote origin main wave20-k: main — 45eb7e08406e85fe826d5d0897ca61ca0a75d845, wave20-k — 66c5debe93a720b729173c7736ad069458be229b; иначе СТОП. Эталон results\validation\wave20_v\run1 — 130 каталогов случаев, иначе СТОП. Свободная память — в отчёт.

ШАГ 1. Слияние 20-К. git switch --detach origin/main; git merge --no-ff origin/wave20-k -m "Merge wave20-k: вкладка «Кинетика» в своём модуле (20-К)" — дерево 4e2fb63e2fbf4bf51de7527ae53c1b9d1b527e2a, иначе СТОП. git push origin HEAD:refs/heads/main; git switch -c wave20-l. Это задание без первой строки «/caveman ultra» — дословно в tasks\WAVE20_L_OPUS.md; коммит.

ШАГ 2. Вкладка «Свойства». app\ThermoGar_app.py до правки — блоб f169d98ce6491c0773e83c479e3e0b8e7bb8c7ac, 11 151 строка, LF. Номера строк ниже — по этому файлу.
Замер мастера.
- Вкладка — :10577 «with physical_tab:» и 122 строки тела :10578–:10699 (10 операторов).
- Определений, нужных только этой вкладке (по замыканию от тела; боковой панели, другим вкладкам и остальному коду они не нужны), — 25, 1260 строк: три псевдонима :316, :318, :319 (:317 execute_bound_fe_batch не нужен никому и остаётся на месте); :863–:2130 — PHYSICAL_DATABASE_PATH и 20 функций контура подряд (от _load_physical_database_cached до render_b4b2_strengthening); :2425–:2453 plot_density_temperature. Перенесённые читают только друг друга, импорты и встроенные имена — ни одного имени головного сценария (после 20-Е…20-И боковая панель и службы приходят параметрами sidebar и services).
- Тело читает 22 имени: 9 — головного сценария (database_key, definition, balance, units, composition_text, pressure_pa, render_friendly_error и сами SIDEBAR и SERVICES: тело передаёт их дальше как sidebar=SIDEBAR, services=SERVICES); 8 — перенесённые функции; 3 — импорты (st, PHYSICAL_BINDING_ERROR_TITLE, PHYSICAL_DATABASE_VERSION); 2 — встроенные (Exception, float). Имена, которые связывает тело (b4b_physical_context, b4b_physical_error, physical_overrides, error и пять переменных подвкладок), головной сценарий как глобальные больше не читает (error встречается только внутри своих «except … as error»). b4b_physical_error присваивается и нигде не читается — и раньше не читалось; тело не правим, pyflakes по новому модулю даст об этом одно сообщение.
- Проверено: _load_physical_database_cached под @st.cache_resource — ключ кэша включает имя модуля, кэш живёт в памяти процесса; после переноса первый вызов в процессе загрузит базу заново, результат тот же. «Магии» Streamlit (показ голых выражений) в головном сценарии нет ни одного случая — перенос её не касается. Подмены в тестах (st.download_button, st.data_editor) идут через модуль streamlit и доходят до перенесённого кода как прежде.
- 22 имени импорта головному сценарию после переноса не нужны — убираются; прежние неиспользуемые импорты остаются как были.
а) Новый app\thermogar_tab_properties.py — создать скриптом Python (UTF-8 без BOM, LF). Строка документации — дословно:
```
"""Вкладка «Свойства» головного сценария ThermoGar.

BL-57, разрез app/ThermoGar_app.py (20-Л). Плотность в точке и по
температуре, упругие свойства, вклады упрочнения и покрытие физической
базы (контур B4B/B4B2): привязка физической базы, галочка поправок,
расчёт, показ и выгрузка. Определения, нужные только этой вкладке,
перенесены из головного сценария без изменений, в прежнем порядке; тело
вкладки — тоже без изменений. Имена головного сценария, которые читает
тело, связываются в начале функции из SidebarContext и RunServices — это
те же объекты, без копий.
"""
```
Дальше: пустая строка; «from __future__ import annotations»; пустая строка; импорты — дословно (те же операторы головного сценария в его порядке, только имена, нужные перенесённому коду):
```
from pathlib import Path
from typing import Any
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from thermogar_palette import (
    ThemedFigure,
    chart_roles,
    normalize_theme,
)
import thermogar_parallel_ui as parallel_ui
from thermogar_workspace import (
    file_sha256,
    record_calculation_history,
)
from thermogar_physical import (
    OVERRIDES_OFF_BY_USER,
    PHYSICAL_DATABASE_VERSION,
    PhysicalDensityDatabase,
    calculate_physical_properties,
    overrides_enabled_by_environment,
)
from thermogar_database_guard import (
    FE_PROFILE_CANONICAL,
)
import thermogar_restricted_fe_core as restricted_fe
import thermogar_verified_loaders as verified_loaders
import thermogar_verified_physical as verified_physical
import thermogar_verified_properties as verified_properties
from thermogar_release_policy import (
    PHYSICAL_DATABASE_RELATIVE_PATH,
    PHYSICAL_DATABASE_SHA256,
)
from thermogar_properties import (
    STRENGTHENING_CONFIRMATION_TEXT,
    STRENGTHENING_PROVENANCE_TEXT,
    elastic_rows_missing_text,
)
from thermogar_release_ui import (
    BLOCK_PHASES,
    FoldedFields,
    action_row,
    folded_block,
    release_download_button,
    verified_feature_button,
)
from thermogar_user_errors import (
    EMPTY_CELL_TEXT,
    UserRuntimeError,
    UserValueError,
    element_columns_for_display,
)
from thermogar_app_texts import (
    ELASTIC_EDITOR_COLUMN_LABELS,
    ELASTIC_FRACTION_LABELS,
    PHYSICAL_BINDING_ERROR_TITLE,
    PHYSICAL_OVERRIDES_ENV_LOCKED_DETAILS,
    PHYSICAL_OVERRIDES_ENV_LOCKED_NOTE,
    PHYSICAL_OVERRIDES_TOGGLE_HELP,
    PHYSICAL_OVERRIDES_TOGGLE_KEY,
    PHYSICAL_OVERRIDES_TOGGLE_LABEL,
)
from thermogar_app_context import RunServices, SidebarContext
from thermogar_app_common import (
    PROJECT_ROOT,
    _verified_tdb_declared_phases,
    chart_figure,
    clear_b4b_physical_session_results,
    current_theme_type,
    figure_to_png,
    parse_composition,
    run_equilibrium_points,
    style_chart_axes,
)
```
Дальше две пустые строки и перенесённые строки файла до правки байт в байт, между блоками — ровно две пустые строки: 1) :316, :318, :319 — три строки подряд, без :317; 2) :863–:2130 — как есть, с пустыми строками между определениями; 3) :2425–:2453. Дальше две пустые строки и функция — текст ниже дословно, затем одна пустая строка, затем строки :10578–:10699 байт в байт; в конце файла один перевод строки.
```
def render_properties_tab(*, sidebar: SidebarContext, services: RunServices) -> None:
    """Вкладка «Свойства»; головной сценарий вызывает её в ``with physical_tab:``."""

    # Имена головного сценария, которые читает тело вкладки.
    database_key = sidebar.database_key
    definition = sidebar.definition
    balance = sidebar.balance
    units = sidebar.units
    composition_text = sidebar.composition_text
    pressure_pa = sidebar.pressure_pa
    render_friendly_error = services.render_friendly_error
    SIDEBAR = sidebar
    SERVICES = services
```
б) app\ThermoGar_app.py, правки по номерам до правки:
1) импорты — удалить: :152 «    file_sha256,»; :175–:179 (от «    OVERRIDES_OFF_BY_USER,» до «    overrides_enabled_by_environment,»); :208 «import thermogar_verified_physical as verified_physical» и :209 «import thermogar_verified_properties as verified_properties»; :217 «    PHYSICAL_DATABASE_RELATIVE_PATH,» и :218 «    PHYSICAL_DATABASE_SHA256,»; :230–:234 — весь импорт из thermogar_properties (от «from thermogar_properties import (» до «)»); :245 «    verified_feature_button,»; :261 «    ELASTIC_EDITOR_COLUMN_LABELS,» и :262 «    ELASTIC_FRACTION_LABELS,»; :268–:273 (от «    PHYSICAL_BINDING_ERROR_TITLE,» до «    PHYSICAL_OVERRIDES_TOGGLE_LABEL,»);
2) после :314 «from thermogar_tab_kinetics import render_kinetics_tab» — строка «from thermogar_tab_properties import render_properties_tab»;
3) удалить :316, :318 и :319; :317 «execute_bound_fe_batch = restricted_fe.execute_bound_restricted_fe» остаётся;
4) удалить :863–:2132 (перенесённые определения и две пустые строки после них; :2133 «DATABASE_ATTRIBUTION…» остаётся);
5) удалить :2425–:2455 (plot_density_temperature и две пустые строки после неё; :2456 «# ---…» остаётся);
6) 122 строки тела :10578–:10699 заменить одной строкой «    render_properties_tab(sidebar=SIDEBAR, services=SERVICES)»; :10577 «with physical_tab:» и комментарий над ней — прежние.
Других правок нет.
в) Ждать (замер мастера на модели шага — сверить): app\ThermoGar_app.py — 9 703 строки, git diff --numstat — 2 вставки, 1450 удалений, sha256 3c54b8b1b547189c9bf1c35f7d8fe09e7c80755fe405c71b398d38010e897dea, после git add блоб 55c7678b4a460ff4b6b2e2cb286b2fc84fc601d5; app\thermogar_tab_properties.py — 1533 строки, sha256 0def004db4ddc810a94477dc08741c27b081fd313f8613967667e57648437d53, блоб 785dab87dfe2a4cc6221411c79876965502d7796. Иначе — СТОП.
г) Проверка шага — results\wave20_l\scripts\proverka_vkladki.py: копия results\wave20_k\scripts\proverka_vkladki.py с дополнениями ниже (только стандартная библиотека; параметры и запуск прежние; дополнения общие для следующих вкладок). Запуск из корня дерева с параметрами f169d98ce6491c0773e83c479e3e0b8e7bb8c7ac app\ThermoGar_app.py app\thermogar_tab_properties.py render_properties_tab physical_tab; вывод — results\wave20_l\proverka_vkladki.txt. Дополнения и чего ждать:
- пролог: кроме «имя = sidebar.поле» и «имя = services.поле» — «SIDEBAR = sidebar» и «SERVICES = services» (тот же объект: вызов в головном сценарии передаёт sidebar=SIDEBAR, services=SERVICES). Ждать 9 присваиваний: database_key, definition, balance, units, composition_text, pressure_pa (sidebar), render_friendly_error (services), SIDEBAR, SERVICES; отклонений 0; каждое имя пролога тело читает;
- тело: 122 строки, 10 операторов — байт в байт и по ast.dump; вложенных областей 0;
- перенесённые определения (новый раздел): все узлы верхнего уровня модуля, кроме строки документации, импортов и функции вкладки. Каждый — узел верхнего уровня файла до правки, текст с декораторами байт в байт и ast.dump равны, порядок прежний; ни одно их имя в головном сценарии после правки не связано. Имена, которые они читают как глобальные (в том числе в аннотациях), — перенесённые, импорты модуля с тем же источником, что в файле до правки, или встроенные; прочих 0. Ждать: 25 узлов, 1260 строк (строки самих узлов, без пустых между ними);
- импорты модуля (новый раздел): каждый оператор — оператор импорта файла до правки: тот же модуль, те же псевдонимы, имена — подмножество в прежнем порядке; операторы — в порядке файла до правки; импортированных, но не читаемых модулем имён 0. Ждать 22 оператора и from __future__;
- имена тела: 22 = пролог 9 + перенесённые 8 + импорты 3 (с другим источником 0) + встроенные 2 (Exception, float) — встроенные отдельной строкой; прочих 0. Связывание телом — в том числе имя «except … as error» (в 20-К except не было);
- имена, которые тело связывает (9), головной сценарий после правки не читает как глобальные: на уровне модуля — вне тел def, lambda и включений и вне своих «except … as <имя>»; в функциях — как глобальные по symtable. Ждать 0 (простой поиск по всему файлу нашёл бы error в чужих except — это не чтение);
- symtable: неопределённых 0 в модуле и в головном сценарии; скрытых обращений в модуле 0;
- головной сценарий по AST: узлов верхнего уровня 242 → 215, операторов импорта 53 → 51; убраны из импортов 22 имени, из них целиком 3 оператора (thermogar_verified_physical, thermogar_verified_properties, thermogar_properties); добавлен render_properties_tab; вызов — render_properties_tab(sidebar=SIDEBAR, services=SERVICES). Откат: из файла до правки убрать 25 перенесённых узлов; в обоих файлах не считать убранных имён и опустевших операторов импорта, импорт из thermogar_tab_properties убрать, тело вкладки вернуть — 214 и 214 узлов, равны по ast.dump;
- импорт модуля из корня — код 0, вывод thermogar_tab_properties;
- три отрицательные пробы на копиях в _to_delete\20l_proba\ (не в git): лишний пробел в перенесённом определении, перенесённое определение оставлено и в головном сценарии, из модуля убран один импорт — каждая даёт код 1 и FAIL своего раздела.
Иначе — СТОП. Коммит (оба файла app, скрипт, вывод).

ШАГ 3. Тесты — только эти правки (перенесённый код тесты теперь берут из нового модуля), остальное не менять:
- tools\test_version_consistency.py: «    assert len(payload) == 81, len(payload)» → «    assert len(payload) == 82, len(payload)» (новый модуль входит в нагрузку установщика).
- tools\test_wave21_m.py: в test_action_rows_in_code строка «        "ThermoGar_app.py", "thermogar_diffusion.py",» → «        "ThermoGar_app.py", "thermogar_tab_properties.py", "thermogar_diffusion.py",»; в test_density_scan_shows_the_png_figure и в test_density_axis_formatter_plain строка «    tree = ast.parse((APP / "ThermoGar_app.py").read_text("utf-8"))» → «    tree = ast.parse((APP / "thermogar_tab_properties.py").read_text("utf-8"))» (в этих двух функциях; в других — не трогать); строка документации test_density_axis_formatter_plain — две строки «    """Ось плотности без смещения: ThermoGar_app — сценарий, проверка по коду» и «    и тем же вызовом matplotlib на узком диапазоне."""» → «    """Ось плотности без смещения: проверка по коду thermogar_tab_properties.py» и «    и тем же вызовом matplotlib на узком диапазоне."""».
- tools\test_wave21_ts.py: строку «APP_SOURCE = (APP / "ThermoGar_app.py").read_text(encoding="utf-8")» заменить двумя:
```
# 20-Л (BL-57): выгрузка покрытия физической базы — в thermogar_tab_properties.py.
APP_SOURCE = (APP / "thermogar_tab_properties.py").read_text(encoding="utf-8")
```
- tools\test_chart_theme_21e.py: 1) две строки «# 20-Ж (BL-57): общие помощники головного сценария — в thermogar_app_common.py.» и «APP_SOURCES = (APP_PATH, ROOT / "app" / "thermogar_app_common.py")» заменить на:
```
# 20-Ж (BL-57): общие помощники головного сценария — в thermogar_app_common.py;
# 20-Л: контур вкладки «Свойства» — в thermogar_tab_properties.py.
APP_SOURCES = (
    APP_PATH,
    ROOT / "app" / "thermogar_app_common.py",
    ROOT / "app" / "thermogar_tab_properties.py",
)
```
2) в test_titles_have_no_thermogar_prefix и test_content_width_instead_of_use_container_width в перечнях модулей после «"thermogar_app_common.py", » вставить «"thermogar_tab_properties.py", » (по одному разу в каждой).
- tools\test_wave21_u.py, TABLE_CALLS: «    "ThermoGar_app.py": 36,» → «    "ThermoGar_app.py": 27,»; после строки «    "thermogar_app_common.py": 1,» — строка «    "thermogar_tab_properties.py": 9,» (восемь st.dataframe и один st.data_editor уехали с контуром; всего по-прежнему 64).
Блобы после (замер мастера — сверить): test_version_consistency 5fe9f0a6530b9a1636cd8199263b566c3b4bebf8, test_wave21_m 180e2022b40358280647d2dcdcc3d9714ae8cb9a, test_wave21_ts 2f400f8936950649d2529e05b67c62e33e401da2, test_chart_theme_21e 8762194af061ed8bd753b25a5dc6c6c3c24be2ab, test_wave21_u ad97516e5fcddc0ac295efb46190adfc2281399c; иначе СТОП. Зелёные, иначе СТОП: test_version_consistency (98 passed), test_wave21_m (22), test_wave21_ts (9), test_wave21_u без slow (8), test_chart_theme_21e (73), test_physical_overrides_toggle (11), test_density_below_pdb (5). Замер мастера на Linux (все tools\test_*.py и thermogar_*_test.py без slow): без правки тестов после переноса падают ровно эти пять файлов; с правкой итоги до и после одинаковые, кроме +1 теста нагрузки. Коммит.

ШАГ 4. Сверка вкладок с эталоном 0.5.0 (как 20-К, ШАГ 4).
- python -B -X utf8 tools\tab_snapshot.py run --out results\validation\wave20_l\posle --state results\validation\wave20_v\state\run10 --time-csv results\wave20_l\posle_time.csv; консоль — results\wave20_l\posle_stdout.txt; сводка — results\wave20_l\posle_svodka.txt (130 из 130: код 0, «ошибка» null, «исключений_на_экране» 0); posle_sha256.txt — как у 20-К.
- Правила — results\wave20_g\isklyucheniya.txt без изменений (14 правил; копию не делать). python -B -X utf8 tools\tab_snapshot_compare.py results\validation\wave20_v\run1 results\validation\wave20_l\posle --isklyucheniya results\wave20_g\isklyucheniya.txt --otchet results\wave20_l\sravnenie.txt — ждать код 0, «ИТОГ: полное равенство», срабатывания правил — те же 14 чисел, что у 20-К (плотность и упругость на трёх составах с галочкой поправок и без — в группе F). Любое «различаются» или «нет пары» — разобрать; не от хеша ThermoGar_app.py — СТОП; новых правил не вводить.
Коммит (posle_time.csv, posle_stdout.txt, posle_svodka.txt, posle_sha256.txt, sravnenie.txt).

ШАГ 5. Полная регрессия — после ШАГА 4. Копия раннера results\wave20_k\scripts\run_regress.py → results\wave20_l\scripts\run_regress.py; в копии две правки: :68 «RELEASE_OUT = ROOT / "results" / "wave20_k"  # каталог вывода 20-К» → «RELEASE_OUT = ROOT / "results" / "wave20_l"  # каталог вывода 20-Л»; :141 «results/validation/wave20_k_state» → «results/validation/wave20_l_state». python -B -X utf8 results\wave20_l\scripts\run_regress.py — СВЕРИТЬ 78 заданий; ждать 69 выход 0 и 9 выход 5 (тот же список, что у 20-К); итоговые строки — как у 20-К, кроме test_version_consistency (97 → 98 passed); всего 1092 passed, 1 xfailed. test_ui_f -m slow одним процессом только при ≥ 6,0 ГиБ. Красное — разобрать; следствие правки — СТОП. python -B -X utf8 results\wave21_eh\scripts\backend_compare.py results\wave20_l\regress_backend results\wave20_l\backend_compare.txt — «ВЕРДИКТ: PASS». Коммит results\wave20_l\.

ШАГ 6. tasks\REGISTER.md — тексты мастера дословно, <…> заполнить; <итог числами> — без точки в конце. Коммит.
а) Таблица волны 20, строка 20-К: в ячейке состояния «**сдано, мастер не смотрел.**» → «**принята мастером 30.09.2026 (ниже); влита в `main` (`<7 знаков коммита слияния ШАГА 1>`).**», остальное не менять.
б) После строки 20-К:
| 20-Л | `WAVE20_L_OPUS.md` | `ThermoGar-w21b` / `wave20-l` | шаг 8 разреза: слияние 20-К в `main`; вкладка «Свойства» — в новом модуле `app/thermogar_tab_properties.py`: 25 определений контура B4B/B4B2, нужных только ей, перенесены без правок, функция `render_properties_tab` (параметры `sidebar`, `services`), тело вкладки без правок, имена головного сценария — прологом из `SidebarContext` и `RunServices`; пять тестов берут перенесённый код из нового модуля; сверка вкладок с эталоном 0.5.0; полная регрессия | **сдано, мастер не смотрел.** <итог числами>. Отчёт `tasks/WAVE20_L_REPORT.md` |
в) После абзаца «Ошибка мастера (20-И, откат AST). …» — два абзаца, каждый после пустой строки:

Приёмка 20-К мастером (30.09.2026). Замер мастера по `main` (`45eb7e0`) и `wave20-k` (`66c5deb`, от `45eb7e0`): задание дословно; слияние 20-И — родители `11eabbc` и `4c9151f`, дерево `e7aa768` = модель мастера; изменены только `app/ThermoGar_app.py` (блоб `f169d98` = модель мастера), новый `app/thermogar_tab_kinetics.py` (блоб `b115bf9` = модель мастера), `tools/test_version_consistency.py` (блоб `577efed` = модель мастера), `results/wave20_k/` и `tasks/`; `proverka_vkladki.py`, запущенный мастером на Linux, дал тот же вывод байт в байт, три отрицательные пробы мастера (убран импорт, чужое поле в прологе, правка тела) — FAIL, как и должно; копия раннера — две строки, как в задании. Прогоны на Linux всех файлов тестов до и после правки — одинаковые итоги, кроме +1 теста нагрузки. Сверка вкладок: сводка 130 из 130 — код 0, ошибок 0, исключений на экране 0; 3573 файла байт в байт равны эталону (по спискам сумм), 463 — те же файлы, что у 20-И, с 14 правилами; полное равенство. Регрессия — 78 заданий: 69 выход 0, 9 выход 5 (тот же список), итоговые строки равны 20-И, кроме +1 теста нагрузки; 1091 passed, 1 xfailed; сверка эталона расчётов PASS. Снимок и регрессия шли на 15–20 % дольше 20-И равномерно по всем группам случаев, не только по «Кинетике», — загрузка машины, не правка. Реестр совпал с моделью мастера целиком. Отступления исполнителя приняты; замечание 8 (двойная точка в строке 20-Е) — ошибка мастера (ниже).

Ошибка мастера (строка 20-Е реестра). В шаблоне строки задания «**сдано, мастер не смотрел.** <итог числами>. Отчёт …» точка стоит после места для итога; итог 20-Е кончался точкой — вышло «PASS.. Отчёт». При приёмке 20-Е мастер не заметил; заметил исполнитель 20-К. Исправлено в 20-Л; в шаблоне итог — без точки в конце.

г) Строка BL-57, ячейка состояния: «**в работе, волна 20; шаг 0 — 20-А; эталон 0.5.0 — 20-В; шаг 1 — удаление неиспользуемого кода (20-Г); шаг 2 — тексты и умолчания (20-Д); шаг 3 — контекст боковой панели (20-Е); шаг 4 — общие помощники (20-Ж); шаг 5 — службы прогона (20-З); шаг 6 — привязка базы (20-И); шаг 7 — вкладка «Кинетика» (20-К).**» → «**в работе, волна 20; шаг 0 — 20-А; эталон 0.5.0 — 20-В; шаг 1 — удаление неиспользуемого кода (20-Г); шаг 2 — тексты и умолчания (20-Д); шаг 3 — контекст боковой панели (20-Е); шаг 4 — общие помощники (20-Ж); шаг 5 — службы прогона (20-З); шаг 6 — привязка базы (20-И); шаг 7 — вкладка «Кинетика» (20-К); шаг 8 — вкладка «Свойства» (20-Л).**», остальное не менять.
д) Строка 20-Е: «PASS.. Отчёт `tasks/WAVE20_E_REPORT.md`» → «PASS. Отчёт `tasks/WAVE20_E_REPORT.md`», остальное не менять.

ШАГ 7. Отчёт tasks\WAVE20_L_REPORT.md: итог одной строкой; время по шагам; ШАГ 0 — вывод git status; ШАГ 1 — коммит и дерево слияния, пуш; ШАГ 2 — числа проверки (строки, sha256, блобы, вывод proverka_vkladki по разделам, отрицательные пробы, импорт); ШАГ 3 — блобы тестов и прогоны; ШАГ 4 — время и пик снимка, сводка, итог сверки с числами по правилам; ШАГ 5 — 78 заданий, выходы, список выходов 5, passed, сверка эталона расчётов; отступления — отдельными пунктами с причиной. Коммит. git push -u origin wave20-l; git ls-remote origin main wave20-l, git log --oneline origin/main..wave20-l и git status --short — дословно в отчёт (вывод после пуша — следующим коммитом, тоже запушить).
