Задание 20-К: BL-57, шаг 7 разреза — первая вкладка в своём модуле: «Кинетика» → новый app\thermogar_tab_kinetics.py, функция render_kinetics_tab (параметры sidebar и services); тело вкладки переносится без правок, имена головного сценария — прологом из SidebarContext и RunServices; слияние 20-И в main; тест нагрузки; сверка вкладок с эталоном 0.5.0; полная регрессия; реестр (приёмка 20-И, ошибка мастера). Мастер ThermoGar, 30.09.2026. Машина — ноутбук Windows 10, дерево D:\Pets\ThermoGar-w21b. Тяжёлый поток, параллельных задач нет. Это санкция мастера на слияние wave20-i в main (ШАГ 1); wave20-k в main не вливать. Порядок сверки — tasks\WAVE20_V_REPORT.md, раздел «Как сверять шаг разреза с эталоном 0.5.0»; образец шага — tasks\WAVE20_I_OPUS.md, образец нового модуля — tasks\WAVE20_ZH_OPUS.md.

ЗАПРЕТЫ
- Исключить до обхода: D:\Pets\Lilith — не открывать, не обходить, исключать из любого поиска/glob/rg/dir по диску. Поиск — только внутри D:\Pets\ThermoGar-w21b; вне дерева ничего не искать и не читать, в том числе при СТОПе.
- D:\Pets\ThermoGar и D:\Pets\ThermoGar-w21a не трогать. Интерпретатор — D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe (не python3 и не python из PATH); пакеты не ставить и не менять. Интерпретатор не запускается — СТОП и доклад дословным сообщением, без поиска причины.
- После слияния ШАГА 1 меняются только: app\ThermoGar_app.py и новый app\thermogar_tab_kinetics.py (ШАГ 2), tools\test_version_consistency.py (ШАГ 3), results\wave20_k\, tasks\WAVE20_K_OPUS.md, tasks\WAVE20_K_REPORT.md, tasks\REGISTER.md. Нужно другое — СТОП.
- Перенос — только перенос: тело вкладки и прочие строки — байт в байт; переформатирование запрещено. Новых слов на экране нет.
- Каталоги прогонов, состояния и журналы — только в results\validation\ (вне git).
- Ничего не удалять: rm, del, Remove-Item, rmdir не применять — и к своим пробным файлам тоже; лишнее — D:\Pets\ThermoGar-w21b\_to_delete\20k_<что>\ + опись sha256.
- Все запуски Python — с -B -X utf8; MPLBACKEND=Agg, PYTHONHASHSEED=0, PYTHONDONTWRITEBYTECODE=1; свободно не меньше 3 ГиБ на входе; снимок вкладок и регрессия — по очереди.
- Номера строк и хеши — замер мастера, сверить; тексты — дословно, иначе СТОП. На любом СТОП: остановиться, доложить, не подгонять. Время начала и конца каждого шага — в отчёт.

ШАГ 0. git status --short — только «?? _to_delete/»; любое другое — СТОП. git fetch origin. git ls-remote origin main wave20-i: main — 11eabbc07521b3cfb1d5d02e32610ffbc64a925c, wave20-i — 4c9151f3167e84e24c874b3b46cbfb0decd96614; иначе СТОП. Эталон results\validation\wave20_v\run1 — 130 каталогов случаев, иначе СТОП. Свободная память — в отчёт.

ШАГ 1. Слияние 20-И. git switch --detach origin/main; git merge --no-ff origin/wave20-i -m "Merge wave20-i: привязка базы ThermoGar_app.py (20-И)" — дерево e7aa768853c76efb1261518903d6a3fbf53db0ad, иначе СТОП. git push origin HEAD:refs/heads/main; git switch -c wave20-k. Это задание без первой строки «/caveman ultra» — дословно в tasks\WAVE20_K_OPUS.md; коммит.

ШАГ 2. Вкладка «Кинетика». app\ThermoGar_app.py до правки — блоб 6ce2bb2d53372c734406d21d436f5c7303b889fa, 11 178 строк, LF. Номера строк ниже — по этому файлу.
Замер мастера. Вкладка — :10707 «with diffusion_tab:» и 27 строк тела :10708–:10734: две подвкладки, обе рисуют чужие модули (thermogar_diffusion, thermogar_precipitation); своих определений у вкладки нет. Тело читает 13 имён. 8 — имена головного сценария, и это те же объекты, что лежат в SIDEBAR и SERVICES: database_key, definition, db, database_path, CURRENT_CONTEXT (поле current_context), THERMOGAR_PATHS (поле paths), render_friendly_error, dataframe_to_excel; после SIDEBAR и SERVICES ни одно из них не переприсваивается (по AST, вместе с кодом вкладок). dataframe_to_excel берёт CURRENT_CONTEXT через globals() головного сценария: через services вызывается та же функция, её globals() прежние. 5 — импорты: st, figure_to_png, record_calculation_history, render_kinetics_section, render_precipitation_section; два последних головному сценарию после переноса не нужны. Поэтому: тело — в функцию нового модуля без правок (отступ тот же, 4 пробела), в начале функции — пролог: те же 8 имён из sidebar и services; в головном сценарии вместо тела — вызов. Так же пойдут следующие вкладки.
а) Новый app\thermogar_tab_kinetics.py — создать скриптом Python (UTF-8 без BOM, LF): текст ниже дословно, затем одна пустая строка, затем строки :10708–:10734 файла до правки байт в байт; в конце файла один перевод строки.
```
"""Вкладка «Кинетика» головного сценария ThermoGar.

BL-57, разрез app/ThermoGar_app.py (20-К): первая вкладка в своём модуле.
Подвкладки «Диффузия и гомогенизация» и «Выделения» рисуют модули
thermogar_diffusion и thermogar_precipitation; вкладка передаёт им базу,
контекст боковой панели и службы прогона.

Тело вкладки перенесено из головного сценария без изменений. Имена, которые
оно читало из головного сценария, связываются в начале функции из
SidebarContext и RunServices — это те же объекты, без копий.
"""

from __future__ import annotations

import streamlit as st

from thermogar_app_common import figure_to_png
from thermogar_app_context import RunServices, SidebarContext
from thermogar_diffusion import render_kinetics_section
from thermogar_precipitation import render_precipitation_section
from thermogar_workspace import record_calculation_history


def render_kinetics_tab(*, sidebar: SidebarContext, services: RunServices) -> None:
    """Вкладка «Кинетика»; головной сценарий вызывает её в ``with diffusion_tab:``."""

    # Имена головного сценария, которые читает тело вкладки.
    database_key = sidebar.database_key
    definition = sidebar.definition
    db = sidebar.db
    database_path = sidebar.database_path
    CURRENT_CONTEXT = sidebar.current_context
    THERMOGAR_PATHS = services.paths
    render_friendly_error = services.render_friendly_error
    dataframe_to_excel = services.dataframe_to_excel
```
б) app\ThermoGar_app.py, правки по номерам до правки:
1) удалить :185 «    render_kinetics_section,» (импорт из thermogar_diffusion) и :190 «    render_precipitation_section,» (импорт из thermogar_precipitation);
2) после :315 «)» — конца импорта из thermogar_app_common — строка «from thermogar_tab_kinetics import render_kinetics_tab»;
3) 27 строк тела :10708–:10734 заменить одной строкой «    render_kinetics_tab(sidebar=SIDEBAR, services=SERVICES)»; :10707 «with diffusion_tab:» и комментарий над ней — прежние.
Других правок нет.
в) Ждать (замер мастера на модели шага — сверить): app\ThermoGar_app.py — 11 151 строка, git diff --numstat — 2 вставки, 29 удалений, sha256 60392a2163c89ce64d108cbae4f6c1be7383563529d67002475737aec3df1503, после git add блоб f169d98ce6491c0773e83c479e3e0b8e7bb8c7ac; app\thermogar_tab_kinetics.py — 63 строки, sha256 b881c8f37e04976b4d7baa1b599dad9f104d7919f13de4ec77e3385ed9ae8405, блоб b115bf9c33f5e8255ac4bc2e02ea71e1e823d1da. Иначе — СТОП.
г) Проверка шага вкладки — свой скрипт results\wave20_k\scripts\proverka_vkladki.py (только стандартная библиотека: ast, symtable, subprocess), общий для следующих вкладок. Параметры: блоб головного сценария до правки (скрипт читает его сам: git cat-file blob <блоб>, байты), головной сценарий после правки, модуль вкладки, имя функции, переменная вкладки. Запуск из корня дерева с параметрами 6ce2bb2d53372c734406d21d436f5c7303b889fa app\ThermoGar_app.py app\thermogar_tab_kinetics.py render_kinetics_tab diffusion_tab; вывод — results\wave20_k\proverka_vkladki.txt. Ждать:
- тело: операторы функции после строки документации и пролога — байт в байт текст тела «with diffusion_tab:» до правки (27 строк, 3 оператора) и равны ему по ast.dump;
- пролог: 8 присваиваний «имя = sidebar.поле» или «имя = services.поле»; у каждого в файле до правки SIDEBAR = SidebarContext(…) или SERVICES = RunServices(…) передаёт «поле=имя» — тот же объект; каждое имя пролога тело читает;
- имена, которые тело читает и само не связывает, — 13: 8 из пролога и 5 импортом нового модуля — st (streamlit), figure_to_png (thermogar_app_common), record_calculation_history (thermogar_workspace), render_kinetics_section (thermogar_diffusion), render_precipitation_section (thermogar_precipitation); модуль и исходное имя — те же, что в импорте файла до правки; прочих 0;
- имена, которые тело связывает (diffusion_subtab, precipitation_subtab), головной сценарий после правки не читает — 0;
- по symtable: каждое имя, которое новый модуль читает как глобальное (в том числе в аннотациях), определено в нём, импортировано или встроено — неопределённых 0; то же для головного сценария после правки — 0; скрытых обращений в новом модуле (globals, vars, locals, eval, exec, __import__, __main__, sys.modules) — 0;
- головной сценарий по AST: узлов верхнего уровня 241 → 242, операторов импорта 52 → 53; из импортов убраны ровно render_kinetics_section и render_precipitation_section, добавлен render_kinetics_tab; если убрать импорт из thermogar_tab_kinetics, вернуть тело «with diffusion_tab:» из файла до правки и в обоих файлах не считать двух убранных имён, все 241 узел равны файлу до правки по ast.dump;
- импорт: python -B -X utf8 -c "import sys; sys.path.insert(0, 'app'); import thermogar_tab_kinetics as k; print(k.render_kinetics_tab.__module__)" из корня дерева — код 0, вывод thermogar_tab_kinetics.
Иначе — СТОП. Коммит (оба файла app, скрипт, вывод).

ШАГ 3. Тесты — только эта правка: tools\test_version_consistency.py, test_payload_list_is_complete: «    assert len(payload) == 80, len(payload)» → «    assert len(payload) == 81, len(payload)» (новый модуль входит в нагрузку установщика: app\*.py); блоб после — 577efed83b4db509e76ea5c97dc3af3e5c8b77e4. Зелёные, иначе СТОП: tools\test_version_consistency.py (97 passed — новый модуль и в проверке версии), tools\test_ui_g.py без slow (29 passed — вкладка «Кинетика» на трёх базах: диффузионная пара, гомогенизация, KWN), tools\test_wave21_m.py (22 passed) и tools\test_switch_21i.py (13 passed). Замер мастера на Linux (все tools\test_*.py и thermogar_*_test.py без slow, до и после правки): итоги одинаковые, кроме +1 теста нагрузки. Коммит.

ШАГ 4. Сверка вкладок с эталоном 0.5.0 (как 20-И, ШАГ 4).
- python -B -X utf8 tools\tab_snapshot.py run --out results\validation\wave20_k\posle --state results\validation\wave20_v\state\run9 --time-csv results\wave20_k\posle_time.csv; консоль — results\wave20_k\posle_stdout.txt; сводка — results\wave20_k\posle_svodka.txt (130 из 130: код 0, «ошибка» null, «исключений_на_экране» 0); posle_sha256.txt — как у 20-И.
- Правила — results\wave20_g\isklyucheniya.txt без изменений (14 правил; копию не делать). python -B -X utf8 tools\tab_snapshot_compare.py results\validation\wave20_v\run1 results\validation\wave20_k\posle --isklyucheniya results\wave20_g\isklyucheniya.txt --otchet results\wave20_k\sravnenie.txt — ждать код 0, «ИТОГ: полное равенство», срабатывания правил — те же 14 чисел, что у 20-И. Любое «различаются» или «нет пары» — разобрать; не от хеша ThermoGar_app.py — СТОП; новых правил не вводить.
Коммит (posle_time.csv, posle_stdout.txt, posle_svodka.txt, posle_sha256.txt, sravnenie.txt).

ШАГ 5. Полная регрессия — после ШАГА 4. Копия раннера results\wave20_i\scripts\run_regress.py → results\wave20_k\scripts\run_regress.py; в копии две правки: :68 «RELEASE_OUT = ROOT / "results" / "wave20_i"  # каталог вывода 20-И» → «RELEASE_OUT = ROOT / "results" / "wave20_k"  # каталог вывода 20-К»; :141 «results/validation/wave20_i_state» → «results/validation/wave20_k_state». python -B -X utf8 results\wave20_k\scripts\run_regress.py — СВЕРИТЬ 78 заданий; ждать 69 выход 0 и 9 выход 5 (тот же список, что у 20-И); итоговые строки — как у 20-И, кроме test_version_consistency (96 → 97 passed); всего 1091 passed, 1 xfailed. test_ui_f -m slow одним процессом только при ≥ 6,0 ГиБ. Красное — разобрать; следствие правки — СТОП. python -B -X utf8 results\wave21_eh\scripts\backend_compare.py results\wave20_k\regress_backend results\wave20_k\backend_compare.txt — «ВЕРДИКТ: PASS». Коммит results\wave20_k\.

ШАГ 6. tasks\REGISTER.md — тексты мастера дословно, <…> заполнить. Коммит.
а) Таблица волны 20, строка 20-И: в ячейке состояния «**сдано, мастер не смотрел.**» → «**принята мастером 30.09.2026 (ниже); влита в `main` (`<7 знаков коммита слияния ШАГА 1>`).**», остальное не менять.
б) После строки 20-И:
| 20-К | `WAVE20_K_OPUS.md` | `ThermoGar-w21b` / `wave20-k` | шаг 7 разреза: слияние 20-И в `main`; вкладка «Кинетика» — в новом модуле `app/thermogar_tab_kinetics.py`: функция `render_kinetics_tab` (параметры `sidebar`, `services`), тело вкладки перенесено без правок, имена головного сценария — прологом из `SidebarContext` и `RunServices`; сверка вкладок с эталоном 0.5.0; полная регрессия | **сдано, мастер не смотрел.** <итог числами>. Отчёт `tasks/WAVE20_K_REPORT.md` |
в) После абзаца «Приёмка 20-З мастером (29.09.2026). …» — два абзаца, каждый после пустой строки:

Приёмка 20-И мастером (30.09.2026). Замер мастера по `main` (`11eabbc`) и `wave20-i` (`4c9151f`, от `11eabbc`): задание дословно; слияние 20-З — родители `8d2147c` и `a293c6a`, дерево `3208bfe` = модель мастера; изменены только `app/ThermoGar_app.py` (блоб `6ce2bb2` = модель мастера) и `app/thermogar_app_context.py` (блоб `79bdac2` = модель мастера), `results/wave20_i/` и `tasks/`; четыре вывода проверок (`proverka_bokovoy.py` и `proverka_sluzhb.py`, до и после), запущенных мастером, — байт в байт; в головном сценарии `global` 0, `vlb_active_context` 0; копия раннера — две строки, как в задании. Прогоны на Linux всех файлов тестов до и после правки — одинаковые итоги. Сверка вкладок: сводка 130 из 130 — код 0, ошибок 0, исключений на экране 0; 3573 файла байт в байт равны эталону (по спискам сумм), 463 — те же файлы, что у 20-З, с 14 правилами; полное равенство. Регрессия — 78 заданий: 69 выход 0, 9 выход 5 (тот же список), итоговые строки равны 20-З; 1090 passed, 1 xfailed; сверка эталона расчётов PASS. Реестр совпал с моделью мастера целиком. Отступления исполнителя приняты; отступление 1 — пропуск в задании (ниже).

Ошибка мастера (20-И, откат AST). В задании 20-И (ШАГ 2в) в списке отката не назван импорт из `thermogar_app_context` (правка б1, добавлено `VerifiedBinding`), поэтому «остальные узлы равны» без его возврата не выполнялось; исполнитель сверил с возвратом импорта — 240 из 240, верно. На результат не влияет.

г) Строка BL-57, ячейка состояния: «**в работе, волна 20; шаг 0 — 20-А; эталон 0.5.0 — 20-В; шаг 1 — удаление неиспользуемого кода (20-Г); шаг 2 — тексты и умолчания (20-Д); шаг 3 — контекст боковой панели (20-Е); шаг 4 — общие помощники (20-Ж); шаг 5 — службы прогона (20-З); шаг 6 — привязка базы (20-И).**» → «**в работе, волна 20; шаг 0 — 20-А; эталон 0.5.0 — 20-В; шаг 1 — удаление неиспользуемого кода (20-Г); шаг 2 — тексты и умолчания (20-Д); шаг 3 — контекст боковой панели (20-Е); шаг 4 — общие помощники (20-Ж); шаг 5 — службы прогона (20-З); шаг 6 — привязка базы (20-И); шаг 7 — вкладка «Кинетика» (20-К).**», остальное не менять.

ШАГ 7. Отчёт tasks\WAVE20_K_REPORT.md: итог одной строкой; время по шагам; ШАГ 0 — вывод git status; ШАГ 1 — коммит и дерево слияния, пуш; ШАГ 2 — числа проверки (строки, sha256, блобы, вывод proverka_vkladki, импорт); ШАГ 3 — блоб теста и прогоны; ШАГ 4 — время и пик снимка, сводка, итог сверки с числами по правилам; ШАГ 5 — 78 заданий, выходы, список выходов 5, passed, сверка эталона расчётов; отступления — отдельными пунктами с причиной. Коммит. git push -u origin wave20-k; git ls-remote origin main wave20-k, git log --oneline origin/main..wave20-k и git status --short — дословно в отчёт (вывод после пуша — следующим коммитом, тоже запушить).
