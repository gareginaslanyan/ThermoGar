Задание 20-Ж: BL-57, шаг 4 разреза — общие помощники головного сценария → новый app\thermogar_app_common.py (46 определений, дословно, в прежнем порядке); слияние 20-Е в main; четыре теста; сверка вкладок с эталоном 0.5.0; полная регрессия; реестр (приёмка 20-Е, ошибка мастера). Мастер ThermoGar, 29.09.2026. Машина — ноутбук Windows 10, дерево D:\Pets\ThermoGar-w21b. Тяжёлый поток, параллельных задач нет. Это санкция мастера на слияние wave20-e в main (ШАГ 1); wave20-zh в main не вливать. Порядок сверки — tasks\WAVE20_V_REPORT.md, раздел «Как сверять шаг разреза с эталоном 0.5.0»; образец шага — tasks\WAVE20_D_OPUS.md.

ЗАПРЕТЫ
- Исключить до обхода: D:\Pets\Lilith — не открывать, не обходить, исключать из любого поиска/glob/rg/dir по диску. Поиск — только внутри D:\Pets\ThermoGar-w21b.
- D:\Pets\ThermoGar и D:\Pets\ThermoGar-w21a не трогать. Интерпретатор — D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe (не python3 и не python из PATH); пакеты не ставить и не менять.
- После слияния ШАГА 1 меняются только: app\ThermoGar_app.py и новый app\thermogar_app_common.py (ШАГ 2), tools\test_version_consistency.py, tools\test_chart_theme_21e.py, tools\test_user_errors_21zh.py, tools\test_wave21_u.py (ШАГ 3), results\wave20_zh\, tasks\WAVE20_ZH_OPUS.md, tasks\WAVE20_ZH_REPORT.md, tasks\REGISTER.md. Нужно другое — СТОП.
- Перенос — только перенос: определения, комментарии, строки с BL- — байт в байт; переформатирование, замена кавычек, склейка строк запрещены. Новых слов на экране нет.
- Каталоги прогонов, состояния и журналы — только в results\validation\ (вне git).
- Ничего не удалять: rm, del, Remove-Item, rmdir не применять — и к своим пробным файлам тоже; лишнее — D:\Pets\ThermoGar-w21b\_to_delete\20zh_<что>\ + опись sha256.
- Все запуски Python — с -B -X utf8; MPLBACKEND=Agg, PYTHONHASHSEED=0, PYTHONDONTWRITEBYTECODE=1; свободно не меньше 3 ГиБ на входе; снимок вкладок и регрессия — по очереди.
- Номера строк и хеши — замер мастера, сверить; тексты — дословно, иначе СТОП. На любом СТОП: остановиться, доложить, не подгонять. Время начала и конца каждого шага — в отчёт.

ШАГ 0. git status --short — только «?? _to_delete/»; любое другое — СТОП. git fetch origin. git ls-remote origin main wave20-e: main — 6a51512610a6a61f4b189ac058124be56c80de00, wave20-e — ecbbfed14b012cf548279b3aae7298ebdf9a53f2; иначе СТОП. Эталон results\validation\wave20_v\run1 — 130 каталогов случаев, иначе СТОП. Свободная память — в отчёт.

ШАГ 1. Слияние 20-Е. git switch --detach origin/main; git merge --no-ff origin/wave20-e -m "Merge wave20-e: контекст боковой панели ThermoGar_app.py (20-Е)" — дерево 1df2d388eb82908df110823fed1fbedc2de2ec7c, иначе СТОП. git push origin HEAD:refs/heads/main; git switch -c wave20-zh. Это задание без первой строки «/caveman ultra» — дословно в tasks\WAVE20_ZH_OPUS.md; коммит.

ШАГ 2. Перенос. app\ThermoGar_app.py до правки — блоб f281d4c2900c9fbc6a809ba71ef9c4523b8ed4ef, 12 259 строк, LF. Номера строк ниже — по этому файлу.
Замер мастера. Определений верхнего уровня, нужных больше чем одной вкладке (или вкладке и боковой панели, по транзитивному замыканию), — 60. Переносятся 46. Остаются 14: THERMOGAR_PATHS, render_friendly_error, log_error (пути состояния), _SCHEIL_STATE, scheil_available (ленивая загрузка scheil), _DATABASE_SNAPSHOT_CACHE, _DATABASE_SNAPSHOT_CACHE_LOCK, _parse_database_snapshot, _database_cache_get, _database_cache_commit, load_database (кэш баз) — это состояние в головном сценарии живёт один прогон страницы, а в модуле жило бы весь процесс; FE_PROFILE_RELATIVE_PATHS, FE_PROFILE_SHA256 — сверка по хешу, лежит рядом с load_database (ревью 21.09, п. 4); dataframe_to_excel — берёт CURRENT_CONTEXT через globals(), в модуле лист «Происхождение» пропал бы из всех выгрузок Excel. PROJECT_ROOT переносится: find_project_root ищет корень от своего файла, оба файла лежат в app\ — значение то же, считается один раз при импорте.
а) Новый app\thermogar_app_common.py — LF, в конце один перевод строки. Строка документации — дословно:
```
"""Общие помощники головного сценария ThermoGar.

BL-57, разрез app/ThermoGar_app.py, шаг «общие помощники» (20-Ж). Здесь —
определения, нужные больше чем одной вкладке: разбор состава и подготовка
расчёта, списки фаз и примечания к ним, равновесие по точкам, графики и
выгрузка. Перенесены из головного сценария без изменений, в прежнем порядке.
Состояние прогона здесь не хранится: пути состояния, кэш баз и ленивая
загрузка scheil остаются в головном сценарии.
"""
```
Дальше: пустая строка; «from __future__ import annotations»; пустая строка; импорты — дословно (те же операторы головного сценария в его порядке, только имена, нужные перенесённому коду):
```
from collections import defaultdict
from io import BytesIO
from pathlib import Path
import hashlib
import re
from typing import Any, Callable, Mapping
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from pycalphad import Database, variables as v
from pycalphad.core.utils import filter_phases, unpack_species
from thermogar_palette import (
    ThemedFigure,
    annotate_line_ends,
    chart_roles,
    element_case_text,
    normalize_theme,
    phase_styles,
    place_legend_below,
    resolve_figure,
)
import thermogar_parallel_ui as parallel_ui
import thermogar_restricted_fe_core as restricted_fe
import thermogar_verified_equilibrium as verified_equilibrium
import thermogar_verified_loaders as verified_loaders
import thermogar_verified_physical as verified_physical
import thermogar_verified_properties as verified_properties
from thermogar_release_policy import (
    DROPPED_PHASES_SHOWN,
    FE_EXCLUDED_PHASES,
    PHASE_MODE_ALL,
    PHASE_MODE_FAST,
    PHASE_MODE_HELP,
    PHASE_MODE_LABELS,
    RELEASE_DATABASE_LABELS,
    PhasePresetError,
    dropped_phases_expander_label,
    dropped_phases_full_list,
    dropped_phases_warning,
    effective_release_phases,
    load_phase_presets,
    phase_mode_note,
    preset_phases,
)
from thermogar_release_ui import (
    BLOCK_PHASES,
    FoldedFields,
    folded_block,
)
from thermogar_user_errors import (
    EMPTY_CELL_TEXT,
    UserRuntimeError,
    UserValueError,
    element_symbol,
    element_symbols,
)
from thermogar_app_texts import (
    PHASE_EXPLANATIONS,
)
from thermogar_app_context import SidebarContext
```
Дальше две пустые строки и 46 определений в порядке головного сценария — строки файла подряд, байт в байт (для 4 — вместе с шестью строками комментария над ним); между определениями — ровно две пустые строки: 1) acquire_b3_execution :298; 2) find_project_root :377–390; 3) PROJECT_ROOT :393; 4) _TDB_PHASE_DECLARATION :397–405; 5) _verified_tdb_declared_phases :408–420; 6) clear_b4b_physical_session_results :620–624; 7) verified_b3_candidate_phases :627–634; 8) verified_b3_refresh_result :637–652; 9) verified_b3_store_result :655–672; 10) parse_composition :2203–2230; 11) units_suffix :2233–2235; 12) normalize :2238–2247; 13) mole_to_mass :2250–2267; 14) build_input :2270–2323; 15) filter_for_mode :2326–2338; 16) rejected_release_phases :2342–2348; 17) excluded_phase_message :2351–2356; 18) available_phase_presets :2359–2368; 19) compatible_phases_for_components :2371–2409; 20) UNBUILDABLE_PHASES_STATE_KEY :2412; 21) _remember_unbuildable_phases :2415–2425; 22) unbuildable_order_disorder :2428–2441; 23) drop_unbuildable_order_disorder :2444–2456; 24) unbuildable_phase_note :2459–2467; 25) phase_model_note :2470–2490; 26) phase_selection_editor :2493–2688; 27) render_phase_set_note :2691–2703; 28) release_exclusion_note :2706–2727; 29) database_key_from_settings :2730–2745; 30) render_release_exclusion_note :2801–2810; 31) render_engine_note :2813–2822; 32) requested_phase_tuple :2825–2839; 33) phase_candidates_for_standard_composition :2842–2867; 34) prepare_calculation :2906–2952; 35) summarize_equilibrium :2955–3055; 36) aggregate_phase_fractions :3058–3071; 37) mole_fraction_map :3095–3116; 38) run_equilibrium_points :3119–3175; 39) require_successful_points :3178–3180; 40) direct_equilibrium_scan :3183–3233; 41) current_theme_type :3391–3396; 42) chart_figure :3399–3401; 43) build_themed_figure :3404–3417; 44) style_chart_axes :3420–3444; 45) plot_phase_fraction_scan :3503–3558; 46) figure_to_png :5337–5341.
б) app\ThermoGar_app.py, правки по номерам до правки, снизу вверх:
1) удалить строки перенесённых определений вместе с пустыми строками после каждого: :5337–5343, :3503–3562, :3391–3446, :3095–3235, :2906–3073, :2801–2869, :2203–2747, :620–674, :397–422, :377–393, :298;
2) после :296 «from thermogar_app_context import SidebarContext» — дословно:
```
from thermogar_app_common import (
    PROJECT_ROOT,
    _verified_tdb_declared_phases,
    acquire_b3_execution,
    aggregate_phase_fractions,
    build_input,
    build_themed_figure,
    chart_figure,
    clear_b4b_physical_session_results,
    compatible_phases_for_components,
    current_theme_type,
    direct_equilibrium_scan,
    figure_to_png,
    mole_fraction_map,
    mole_to_mass,
    normalize,
    parse_composition,
    phase_candidates_for_standard_composition,
    phase_selection_editor,
    plot_phase_fraction_scan,
    prepare_calculation,
    render_engine_note,
    render_phase_set_note,
    render_release_exclusion_note,
    requested_phase_tuple,
    run_equilibrium_points,
    style_chart_axes,
    summarize_equilibrium,
    units_suffix,
    verified_b3_candidate_phases,
    verified_b3_refresh_result,
    verified_b3_store_result,
)
```
3) импорты, которые после переноса нужны только новому модулю: в импорте из thermogar_release_policy удалить :237–244 (от «    PhasePresetError,» до «    preset_phases,»), :223–224 («    PHASE_MODE_HELP,», «    PHASE_MODE_LABELS,») и :219 «    DROPPED_PHASES_SHOWN,»; в импорте из thermogar_palette удалить :147 «    resolve_figure,» и :142 «    element_case_text,»; удалить :79 «from pycalphad.core.utils import filter_phases, unpack_species»; :60 «from typing import Any, Callable, Mapping» → «from typing import Any»; удалить :50 «from collections import defaultdict».
Других правок нет.
в) Ждать (замер мастера на модели шага — сверить): app\ThermoGar_app.py — 11 132 строки, git diff --stat — 34 вставки, 1161 удаление, sha256 40c5f58618bd6ffcdee3c8ff348d3da1a56643e425bbf3b94c450169e67b463b, после git add блоб 42196e1402e8cbebe8315a1e5ea5004732a979c1; app\thermogar_app_common.py — 1219 строк, sha256 d33dc25f0a35518b15c7cca7290f499373d79918d85e9eb8d1daf14bfafd4380, блоб 53f940a8be6c0cabb6cc2857b60631c6eeb9d3ac. По AST: в новом модуле строка документации, 25 операторов импорта (с __future__) и 46 определений — те же узлы (ast.dump), что в файле до правки, в том же порядке; текст каждого определения с декораторами — байт в байт прежний. В головном сценарии 188 узлов верхнего уровня, кроме импортов, прежние по ast.dump и в том же порядке; операторов импорта 52 → 51. Иначе — СТОП.
г) Проверки нового модуля, свой скрипт results\wave20_zh\scripts\proverka_common.py (только стандартная библиотека), вывод — results\wave20_zh\proverka_common.txt:
- по symtable: каждое имя, которое модуль читает как глобальное (в том числе в аннотациях и декораторах), определено в модуле, импортировано или встроено — неопределённых 0; то же для головного сценария — 0;
- скрытые обращения: в новом модуле нет вызовов globals, vars, locals, eval, exec, __import__ и слов __main__, sys.modules — 0 (в головном сценарии остаётся один globals() — в dataframe_to_excel);
- импорт: python -B -X utf8 -c "import sys; sys.path.insert(0, 'app'); import thermogar_app_common as c; print(c.PROJECT_ROOT)" из корня дерева — код 0, путь — D:\Pets\ThermoGar-w21b.
Иначе — СТОП. Коммит (оба файла app, скрипт, вывод).

ШАГ 3. Тесты — только эти правки, остальное не менять:
- tools\test_version_consistency.py, test_payload_list_is_complete: «    assert len(payload) == 79, len(payload)» → «    assert len(payload) == 80, len(payload)» (новый модуль входит в нагрузку установщика: app\*.py).
- tools\test_wave21_u.py, TABLE_CALLS: «    "ThermoGar_app.py": 37,» → две строки «    "ThermoGar_app.py": 36,» и «    "thermogar_app_common.py": 1,» (один st.data_editor уехал с phase_selection_editor; всего по-прежнему 64).
- tools\test_user_errors_21zh.py, _app_function (там берётся только parse_composition): в трёх строках «ThermoGar_app.py» → «thermogar_app_common.py» — строка документации «    """Функция из ThermoGar_app.py без запуска страницы Streamlit."""», «    source = (APP / "ThermoGar_app.py").read_text("utf-8")» и подпись в compile(…, "ThermoGar_app.py", "exec").
- tools\test_chart_theme_21e.py — функции берутся из обоих файлов в одно пространство имён, как раньше из одного (иначе подмена current_theme_type в тестах тем не доходит до перенесённых функций):
  1) после строки «APP_PATH = ROOT / "app" / "ThermoGar_app.py"» — две строки:
```
# 20-Ж (BL-57): общие помощники головного сценария — в thermogar_app_common.py.
APP_SOURCES = (APP_PATH, ROOT / "app" / "thermogar_app_common.py")
```
  2) в фикстуре app строки от «    tree = ast.parse(APP_PATH.read_text("utf-8"))» до «            definitions.append(node)» (9 строк) заменить на:
```
    wanted = set(APP_NAMES)
    header: list[ast.stmt] = []
    definitions: list[ast.stmt] = []
    for path in APP_SOURCES:
        for node in ast.parse(path.read_text("utf-8")).body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if header and isinstance(node, ast.ImportFrom) and node.module == "__future__":
                    continue
                header.append(node)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted:
                definitions.append(node)
```
  3) в test_nine_charts_go_through_style_chart_axes строки «    source = APP_PATH.read_text("utf-8")», «    tree = ast.parse(source)», «    callers = sorted(», «        node.name», «        for node in tree.body» заменить на:
```
    callers = sorted(
        node.name
        for path in APP_SOURCES
        for node in ast.parse(path.read_text("utf-8")).body
```
  4) в test_titles_have_no_thermogar_prefix и test_content_width_instead_of_use_container_width в кортеж файлов после "ThermoGar_app.py" добавить "thermogar_app_common.py" (запреты проверяют и перенесённый код); в test_screens_store_builders_not_pictures «    source = APP_PATH.read_text("utf-8")» → «    source = "\n".join(path.read_text("utf-8") for path in APP_SOURCES)».
Ждать блобы (сверить): test_version_consistency.py c4160f5ce36ac9b566495988f309425d4f5d400e, test_wave21_u.py c7246c7e0b03cb67c23ecdddebb06664d474c9e3, test_user_errors_21zh.py adcec7a06413666d330bd3cd1d417d73c553d6db, test_chart_theme_21e.py f25f1e7b32a4838f5f38a33aec8fb3d7d2c6fe95. Зелёные, иначе СТОП: tools\test_version_consistency.py (96 passed), tools\test_chart_theme_21e.py, tools\test_user_errors_21zh.py, tools\test_wave21_u.py, tools\test_chart_legend_theme.py, tools\test_chart_celsius_ticks.py, tools\test_phase_description_order_words.py, tools\test_phase_description_stub_keys.py, tools\test_sidebar_composition_error.py, tools\thermogar_paths_test.py и tools\thermogar_verified_state_test.py (оба unittest). Замер мастера на Linux (все tools\test_*.py и thermogar_*_test.py без slow, до и после правки): без правок test_chart_theme_21e.py, test_user_errors_21zh.py и test_wave21_u.py падают 7 тестов (5, 1 и 1), с ними итоги совпадают с деревом до правки, кроме +1 теста нагрузки. Коммит.

ШАГ 4. Сверка вкладок с эталоном 0.5.0 (как 20-Е, ШАГ 4).
- python -B -X utf8 tools\tab_snapshot.py run --out results\validation\wave20_zh\posle --state results\validation\wave20_v\state\run6 --time-csv results\wave20_zh\posle_time.csv; консоль — results\wave20_zh\posle_stdout.txt; сводка — results\wave20_zh\posle_svodka.txt (130 из 130: код 0, «ошибка» null, «исключений_на_экране» 0); posle_sha256.txt — как у 20-Е.
- Правила — results\wave20_g\isklyucheniya.txt без изменений (14 правил; копию не делать). python -B -X utf8 tools\tab_snapshot_compare.py results\validation\wave20_v\run1 results\validation\wave20_zh\posle --isklyucheniya results\wave20_g\isklyucheniya.txt --otchet results\wave20_zh\sravnenie.txt — ждать код 0, «ИТОГ: полное равенство», срабатывания правил — те же 14 чисел, что у 20-Е. Любое «различаются» или «нет пары» — разобрать; не от хеша ThermoGar_app.py — СТОП; новых правил не вводить.
Коммит (posle_time.csv, posle_stdout.txt, posle_svodka.txt, posle_sha256.txt, sravnenie.txt).

ШАГ 5. Полная регрессия — после ШАГА 4. Копия раннера results\wave20_e\scripts\run_regress.py → results\wave20_zh\scripts\run_regress.py; в копии две правки: :68 «RELEASE_OUT = ROOT / "results" / "wave20_e"  # каталог вывода 20-Е» → «RELEASE_OUT = ROOT / "results" / "wave20_zh"  # каталог вывода 20-Ж»; :141 «results/validation/wave20_e_state» → «results/validation/wave20_zh_state». python -B -X utf8 results\wave20_zh\scripts\run_regress.py — СВЕРИТЬ 78 заданий (новый модуль — не тест); ждать 69 выход 0 и 9 выход 5 (тот же список, что у 20-Е); итоговые строки — как у 20-Е, кроме notslow__test_version_consistency.py: 96 passed (+1 — test_first_version_mention_is_app_version[app/thermogar_app_common.py]); всего 1090 passed, 1 xfailed. test_ui_f -m slow одним процессом только при ≥ 6,0 ГиБ. Красное — разобрать; следствие переноса — СТОП. python -B -X utf8 results\wave21_eh\scripts\backend_compare.py results\wave20_zh\regress_backend results\wave20_zh\backend_compare.txt — «ВЕРДИКТ: PASS». Коммит results\wave20_zh\.

ШАГ 6. tasks\REGISTER.md — тексты мастера дословно, <…> заполнить. Коммит.
а) Таблица волны 20, строка 20-Е: в ячейке состояния «**сдано, мастер не смотрел.**» → «**принята мастером 29.09.2026 (ниже); влита в `main` (`<7 знаков коммита слияния ШАГА 1>`).**», остальное не менять.
б) После строки 20-Е:
| 20-Ж | `WAVE20_ZH_OPUS.md` | `ThermoGar-w21b` / `wave20-zh` | шаг 4 разреза: слияние 20-Е в `main`; общие помощники головного сценария → `app/thermogar_app_common.py` (46 определений, дословно); 14 общих определений с состоянием прогона и `dataframe_to_excel` остаются в головном сценарии; четыре теста; сверка вкладок с эталоном 0.5.0; полная регрессия | **сдано, мастер не смотрел.** <итог числами>. Отчёт `tasks/WAVE20_ZH_REPORT.md` |
в) После абзаца «Приёмка 20-Д мастером (29.09.2026). …» — два абзаца:

Приёмка 20-Е мастером (29.09.2026). Замер мастера по `main` (`6a51512`) и `wave20-e` (`ecbbfed`, от `6a51512`): задание дословно; слияние 20-Д — родители `b719976` и `df9ccd2`, дерево `675981a` = модель мастера; изменены только `app/ThermoGar_app.py` (блоб `f281d4c` = модель мастера), новый `app/thermogar_app_context.py` (блоб `a92a54a` = модель мастера), `tools/test_version_consistency.py` (блоб `517ad9e` = модель мастера), `results/wave20_e/` и `tasks/`; скрипт `proverka_bokovoy.py`, запущенный мастером, дал `bokovaya_do.txt` и `bokovaya_posle.txt` байт в байт; копия раннера — две строки, как в задании. Прогоны на Linux 30 файлов тестов, берущих головной сценарий, до и после правки — одинаковые итоги, кроме +1 теста нагрузки. Сверка вкладок: сводка 130 из 130 — код 0, ошибок 0, исключений на экране 0; 3573 файла байт в байт равны эталону (по спискам сумм), 463 — те же файлы, что у 20-Д, с 14 правилами; полное равенство. Регрессия — 78 заданий: 69 выход 0, 9 выход 5 (тот же список), итоговые строки равны 20-Д, кроме +1 теста нагрузки; 1089 passed, 1 xfailed; сверка эталона расчётов PASS. Реестр совпал с моделью мастера целиком. Отступления исполнителя приняты; вызов `python3` (заглушка Windows, отступление 5) файлов не менял.

Ошибка мастера (20-Е, проверка боковой панели). Проверка «функции не читают имён боковой панели» (symtable) не видит обращений через `globals()`: `dataframe_to_excel` (`app/ThermoGar_app.py:5292` на `ecbbfed`) берёт `CURRENT_CONTEXT` вызовом `globals().get("CURRENT_CONTEXT")` — для листа «Происхождение» всех выгрузок Excel. Функций, читающих имена боковой панели, после 20-Е три, а не две. На результат 20-Е не влияет: поведение прежнее, сверка — полное равенство. Найдено мастером при подготовке 20-Ж; с 20-Ж проверка шага разреза ищет и скрытые обращения (`globals`, `vars`, `locals`, `eval`, `exec`), `dataframe_to_excel` остаётся в головном сценарии до явной передачи контекста.

г) Строка BL-57, ячейка состояния: «**в работе, волна 20; шаг 0 — 20-А; эталон 0.5.0 — 20-В; шаг 1 — удаление неиспользуемого кода (20-Г); шаг 2 — тексты и умолчания (20-Д); шаг 3 — контекст боковой панели (20-Е).**» → «**в работе, волна 20; шаг 0 — 20-А; эталон 0.5.0 — 20-В; шаг 1 — удаление неиспользуемого кода (20-Г); шаг 2 — тексты и умолчания (20-Д); шаг 3 — контекст боковой панели (20-Е); шаг 4 — общие помощники (20-Ж).**», остальное не менять.

ШАГ 7. Отчёт tasks\WAVE20_ZH_REPORT.md: итог одной строкой; время по шагам; ШАГ 0 — вывод git status; ШАГ 1 — коммит и дерево слияния, пуш; ШАГ 2 — числа проверки (строки, sha256, блобы, AST, вывод proverka_common); ШАГ 3 — блобы тестов и прогоны; ШАГ 4 — время и пик снимка, сводка, итог сверки с числами по правилам; ШАГ 5 — 78 заданий, выходы, список выходов 5, passed, сверка эталона расчётов; отступления — отдельными пунктами с причиной. Коммит. git push -u origin wave20-zh; git ls-remote origin main wave20-zh, git log --oneline origin/main..wave20-zh и git status --short — дословно в отчёт (вывод после пуша — следующим коммитом, тоже запушить).
