Задание 20-Д: BL-57, шаг 2 разреза — тексты и умолчания головного сценария → app\thermogar_app_texts.py; слияние 20-Г в main; .gitignore «Claude outputs/»; три теста — константы из нового модуля; сверка вкладок с эталоном 0.5.0; полная регрессия; реестр. Мастер ThermoGar, 28.09.2026. Машина — ноутбук Windows 10, дерево D:\Pets\ThermoGar-w21b. Тяжёлый поток, параллельных задач нет. Это санкция мастера на слияние wave20-g в main (ШАГ 1); wave20-d в main не вливать. Порядок сверки — tasks\WAVE20_V_REPORT.md, раздел «Как сверять шаг разреза с эталоном 0.5.0»; образец шага — tasks\WAVE20_G_OPUS.md.

ЗАПРЕТЫ
- Исключить до обхода: D:\Pets\Lilith — не открывать, не обходить, исключать из любого поиска/glob/rg/dir по диску. Поиск — только внутри D:\Pets\ThermoGar-w21b.
- D:\Pets\ThermoGar и D:\Pets\ThermoGar-w21a не трогать. Интерпретатор — D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe; пакеты не ставить и не менять.
- После слияния ШАГА 1 меняются только: .gitignore (ШАГ 1), app\ThermoGar_app.py и новый app\thermogar_app_texts.py (ШАГ 2), tools\test_wave21_m.py, tools\test_wave21_ts.py, tools\test_version_consistency.py (ШАГ 3), results\wave20_d\, tasks\WAVE20_D_OPUS.md, tasks\WAVE20_D_REPORT.md, tasks\REGISTER.md. Нужно другое — СТОП.
- Перенос — только перенос: тексты, числа, комментарии и строки с BL- — байт в байт; переформатирование, замена кавычек, склейка строк запрещены. Новых слов на экране нет.
- Каталоги прогонов, состояния и журналы — только в results\validation\ (вне git).
- Ничего не удалять: rm, del, Remove-Item, rmdir не применять — и к своим пробным файлам тоже; лишнее — D:\Pets\ThermoGar-w21b\_to_delete\20d_<что>\ + опись sha256.
- Все запуски Python — с -B -X utf8; MPLBACKEND=Agg, PYTHONHASHSEED=0, PYTHONDONTWRITEBYTECODE=1; свободно не меньше 3 ГиБ на входе; снимок вкладок и регрессия — по очереди.
- Номера строк и хеши — замер мастера, сверить; тексты — дословно, иначе СТОП. На любом СТОП: остановиться, доложить, не подгонять. Время начала и конца каждого шага — в отчёт.

ШАГ 0. git status --short — только «?? _to_delete/». Если есть ещё «?? "Claude outputs/"» — это файл задания, сохранённый приложением Claude (к разговору мастера подключена эта папка): перенести папку в _to_delete\20d_claude_outputs\ с описью sha256 и продолжить (в отчёт — sha256 файла); любое другое — СТОП. git fetch origin. git ls-remote origin main wave20-g: main — 4e905b3771fea1cc1386a7b1ef7936626708e835, wave20-g — af69796956b59e6989bb1848048c760544dc38b0; иначе СТОП. Эталон results\validation\wave20_v\run1 — 130 каталогов случаев, иначе СТОП. Свободная память — в отчёт.

ШАГ 1. Слияние 20-Г и .gitignore. git switch --detach origin/main; git merge --no-ff origin/wave20-g -m "Merge wave20-g: удаление неиспользуемого кода ThermoGar_app.py (20-Г)" — дерево 702a77059ef845b13ad23d2ecf2670cb6739a619, иначе СТОП. git push origin HEAD:refs/heads/main; git switch -c wave20-d. Это задание без первой строки «/caveman ultra» — дословно в tasks\WAVE20_D_OPUS.md; коммит. .gitignore — в конец две строки:
# 20-Д: папка файлов, которые приложение Claude сохраняет в подключённую папку
Claude outputs/
Коммит; git check-ignore -v "Claude outputs/x" — правило найдено.

ШАГ 2. Перенос. app\ThermoGar_app.py до правки — блоб f52095b7a5b4954df85e57098e858acfc85bab68, 12 818 строк, LF. Номера строк ниже — по этому файлу.
а) Блоки — строки файла подряд, границы сверить по тексту:
1) :337–383 DATABASE_DEFINITIONS;
2) :398–401 три строки комментария «# thermogar_database_guard.FE_PROFILE_LABELS …» и FE_PROFILE_UI_LABEL;
3) :404–417 SOLIDIFICATION_DEFAULTS;
4) :419–422 SOLIDIFICATION_METHOD_LABELS;
5) :425–472 ENERGY_DEFAULTS;
6) :474–521 PHASE_EXPLANATIONS;
7) :524–558 BINARY_DIAGRAM_DEFAULTS;
8) :561–567 три строки комментария «# «Изменение состава»: …» и CONCENTRATION_SCAN_DEFAULTS;
9) :569–605 три строки комментария «# Шаги по умолчанию подобраны так, …» и ISOPLETH_DEFAULTS;
10) :608–633 TERNARY_DIAGRAM_DEFAULTS;
11) :636–667 TERNARY_PHASE_MAP_DEFAULTS;
12) :1326–1349 комментарий «# Строка 34 части 1 списка 21-Г: …», PHYSICAL_BINDING_ERROR_TITLE, PHYSICAL_OVERRIDES_TOGGLE_KEY, PHYSICAL_OVERRIDES_TOGGLE_LABEL, PHYSICAL_OVERRIDES_TOGGLE_HELP, PHYSICAL_OVERRIDES_ENV_LOCKED_NOTE, PHYSICAL_OVERRIDES_ENV_LOCKED_DETAILS;
13) :1352–1370 комментарий BL-38, ELASTIC_MOLE_FRACTION_LABEL, ELASTIC_VOLUME_FRACTION_LABEL, ELASTIC_FRACTION_LABELS, комментарий 21-Ж, ELASTIC_EDITOR_COLUMN_LABELS;
14) :5692–5710 EXACT_DESCRIPTION_TRANSLATIONS;
15) :12139–12379 USER_GUIDE_MD.
Не переносятся (остаются): FE_PROFILE_RELATIVE_PATHS и FE_PROFILE_SHA256 (:385–395 — сверка по хешу, ревью 21.09, п. 4), DISPLAY_APP_NAME, физические пороги и тексты затвердевания (SOLIDUS_FALLBACK_WARNING, SOLIDUS_SEARCH_STATUS_LABEL уедут с вкладкой «Затвердевание»).
б) Новый app\thermogar_app_texts.py = шапка (дословно, ниже) + блоки 1–15 по порядку; между шапкой и блоком 1 и между блоками — ровно две пустые строки; в конце файла — один перевод строки после строки «"""» блока 15. Шапка:
```
"""Тексты и умолчания головного сценария ThermoGar.

BL-57, разрез app/ThermoGar_app.py, шаг «тексты и умолчания» (20-Д). Константы
перенесены из головного сценария без изменений: строки — байт в байт,
комментарии — вместе со своими константами. Модуль только задаёт значения:
ни Streamlit, ни расчёта.
"""

from thermogar_physical import PHYSICAL_OVERRIDES_ENV
```
в) app\ThermoGar_app.py, правки снизу вверх по номерам файла до правки: удалить :12139–12381, :5691–5712, :1326–1372, :396–667, :337–384 (блоки и пустые строки вокруг них; FE_PROFILE_RELATIVE_PATHS и FE_PROFILE_SHA256 остаются на месте); после :273 (строка «)» импорта из thermogar_user_errors) вставить:
```
from thermogar_app_texts import (
    BINARY_DIAGRAM_DEFAULTS,
    CONCENTRATION_SCAN_DEFAULTS,
    DATABASE_DEFINITIONS,
    ELASTIC_EDITOR_COLUMN_LABELS,
    ELASTIC_FRACTION_LABELS,
    ENERGY_DEFAULTS,
    EXACT_DESCRIPTION_TRANSLATIONS,
    FE_PROFILE_UI_LABEL,
    ISOPLETH_DEFAULTS,
    PHASE_EXPLANATIONS,
    PHYSICAL_BINDING_ERROR_TITLE,
    PHYSICAL_OVERRIDES_ENV_LOCKED_DETAILS,
    PHYSICAL_OVERRIDES_ENV_LOCKED_NOTE,
    PHYSICAL_OVERRIDES_TOGGLE_HELP,
    PHYSICAL_OVERRIDES_TOGGLE_KEY,
    PHYSICAL_OVERRIDES_TOGGLE_LABEL,
    SOLIDIFICATION_DEFAULTS,
    SOLIDIFICATION_METHOD_LABELS,
    TERNARY_DIAGRAM_DEFAULTS,
    TERNARY_PHASE_MAP_DEFAULTS,
    USER_GUIDE_MD,
)
```
и удалить :180 «    PHYSICAL_OVERRIDES_ENV,» из импорта thermogar_physical (после переноса имя в головном сценарии не используется). ELASTIC_MOLE_FRACTION_LABEL и ELASTIC_VOLUME_FRACTION_LABEL не импортировать — головной сценарий берёт их только через ELASTIC_FRACTION_LABELS.
г) Ждать (замер мастера на модели переноса — сверить): app\ThermoGar_app.py — 12 208 строк, sha256 1bc0e905bd101966b90c1a9857cb218649e41549e3fd9555d0fa4baa25427cc0, после git add блоб 35b309b1da7cf6ece7a9ddf6fabde722fb16fc77; app\thermogar_app_texts.py — 644 строки, sha256 567930ef5ae67b07b985d2dc62dd6ade57f88f6014fbfa0d835f7ce7888c1a99, блоб cc8864e743c134afef9479bad4ab13b7c096a8b7. По AST: в новом модуле 23 присваивания — те же узлы (ast.dump) и тот же текст (ast.get_source_segment), что в файле до правки, в том же порядке; значения, выполненные из нового модуля, равны прежним; в головном сценарии остальные 283 узла верхнего уровня прежние, кроме импорта thermogar_physical (без PHYSICAL_OVERRIDES_ENV), и добавлен один импорт. Иначе — СТОП. Коммит.

ШАГ 3. Тесты читают константы из нового модуля — по одной строке, остальное не менять:
- tools\test_wave21_m.py, test_defaults_5_to_9: «    source = (APP / "ThermoGar_app.py").read_text("utf-8")» → «    source = (APP / "thermogar_app_texts.py").read_text("utf-8")» (строка сразу после «def test_defaults_5_to_9() -> None:»);
- tools\test_wave21_ts.py, _user_guide_md: «    for node in _app_tree().body:» → «    for node in ast.parse((APP / "thermogar_app_texts.py").read_text(encoding="utf-8")).body:» (только в этой функции; _app_tree в других местах не менять);
- tools\test_version_consistency.py, test_payload_list_is_complete: «    assert len(payload) == 77, len(payload)» → «    assert len(payload) == 78, len(payload)» (новый модуль входит в нагрузку установщика: app\*.py).
Ждать блобы (сверить): test_wave21_m.py b3e8dc7f8380dd3360321851c5b862a298a95103, test_wave21_ts.py 1bf33882be0d1419ee84f56d0f9ba78f6cbf7ef2, test_version_consistency.py 3c8cd5f66df03377ba38741c59645bac743eff0f. Зелёные, иначе СТОП: tools\test_wave21_m.py, tools\test_wave21_ts.py, tools\test_version_consistency.py, tools\test_phase_description_order_words.py, tools\test_phase_description_stub_keys.py, tools\test_equilibrium_solidus_fallback.py, tools\test_chart_theme_21e.py, tools\test_user_errors_21zh.py, tools\thermogar_paths_test.py (последний — unittest). Остальные тесты, что берут головной сценарий по AST, получают перенесённые имена через его импорты — сверено мастером на Linux. Коммит.

ШАГ 4. Сверка вкладок с эталоном 0.5.0 (как 20-Г, ШАГ 3). Папку results\wave20_d\ создать заранее.
- python -B -X utf8 tools\tab_snapshot.py run --out results\validation\wave20_d\posle --state results\validation\wave20_v\state\run4 --time-csv results\wave20_d\posle_time.csv; консоль — results\wave20_d\posle_stdout.txt; сводка — results\wave20_d\posle_svodka.txt (130 из 130: код 0, «ошибка» null, «исключений_на_экране» 0); posle_sha256.txt — как у 20-Г.
- Правила — results\wave20_g\isklyucheniya.txt без изменений (14 правил; копию не делать). python -B -X utf8 tools\tab_snapshot_compare.py results\validation\wave20_v\run1 results\validation\wave20_d\posle --isklyucheniya results\wave20_g\isklyucheniya.txt --otchet results\wave20_d\sravnenie.txt — ждать код 0, «ИТОГ: полное равенство». Любое «различаются» или «нет пары» — разобрать; не от хеша ThermoGar_app.py — СТОП; новых правил не вводить.
Коммит (posle_time.csv, posle_stdout.txt, posle_svodka.txt, posle_sha256.txt, sravnenie.txt).

ШАГ 5. Полная регрессия — после ШАГА 4. Копия раннера results\wave20_g\scripts\run_regress.py → results\wave20_d\scripts\run_regress.py; в копии две правки: :68 «RELEASE_OUT = ROOT / "results" / "wave20_g"  # каталог вывода 20-Г» → «RELEASE_OUT = ROOT / "results" / "wave20_d"  # каталог вывода 20-Д»; :141 «results/validation/wave20_g_state» → «results/validation/wave20_d_state». python -B -X utf8 results\wave20_d\scripts\run_regress.py — СВЕРИТЬ 78 заданий (новый модуль — не тест); ждать 69 выход 0 и 9 выход 5 (тот же список, что у 20-Г); test_ui_f -m slow одним процессом только при ≥ 6,0 ГиБ. Красное — разобрать; следствие переноса — СТОП. python -B -X utf8 results\wave21_eh\scripts\backend_compare.py results\wave20_d\regress_backend results\wave20_d\backend_compare.txt — «ВЕРДИКТ: PASS». Коммит results\wave20_d\.

ШАГ 6. tasks\REGISTER.md — тексты мастера дословно, <…> заполнить. Коммит.
а) Таблица волны 20, строка 20-Г: в ячейке состояния «**сдано, мастер не смотрел.**» → «**принята мастером 28.09.2026 (ниже); влита в `main` (`<7 знаков коммита слияния ШАГА 1>`).**», остальное не менять.
б) После строки 20-Г:
| 20-Д | `WAVE20_D_OPUS.md` | `ThermoGar-w21b` / `wave20-d` | шаг 2 разреза: слияние 20-Г в `main`; тексты и умолчания головного сценария → `app/thermogar_app_texts.py` (23 константы, дословно); `.gitignore` — `Claude outputs/`; три теста берут константы из нового модуля; сверка вкладок с эталоном 0.5.0; полная регрессия | **сдано, мастер не смотрел.** <итог числами>. Отчёт `tasks/WAVE20_D_REPORT.md` |
в) После абзаца «Решение владельца, 28.09.2026 (BL-57, неиспользуемый код). …» — абзац:

Приёмка 20-Г мастером (28.09.2026). Замер мастера по `main` (`4e905b3`) и `wave20-g` (`af69796`, от `4e905b3`): задание дословно; слияние 20-В — родители `620d88e` и `5f9cbb6`, дерево `d8a2c18` = модель мастера; изменены только `app/ThermoGar_app.py` (блоб `f52095b` = модель мастера: 132 строки удалены, 12 818 строк, остальные 306 узлов верхнего уровня по AST прежние, pyflakes — те же сообщения), `results/wave20_g/` и `tasks/`; копия раннера — две строки, как в задании. Сверка вкладок: сводка 130 из 130 — код 0, ошибок 0, исключений на экране 0; 3573 файла байт в байт равны эталону (по спискам сумм), 463 — с 14 правилами, правило 14 — в 130 `meta.json`; полное равенство. Регрессия — 78 заданий: 69 выход 0, 9 выход 5 (тот же список), 1087 passed, 1 xfailed; сверка эталона расчётов PASS. Реестр совпал с моделью мастера целиком. СТОП в ШАГЕ 0 верный: в дереве лежала папка `Claude outputs/` с файлом этого задания (sha256 = копии мастера) — её создало приложение Claude, потому что к разговору мастера подключена папка `ThermoGar-w21b`; по решению владельца папка перенесена в `_to_delete`, с 20-Д она в `.gitignore`. Отступления исполнителя приняты.

г) Строка BL-57, ячейка состояния: «**в работе, волна 20; шаг 0 — 20-А; эталон 0.5.0 — 20-В; шаг 1 — удаление неиспользуемого кода (20-Г).**» → «**в работе, волна 20; шаг 0 — 20-А; эталон 0.5.0 — 20-В; шаг 1 — удаление неиспользуемого кода (20-Г); шаг 2 — тексты и умолчания (20-Д).**», остальное не менять.

ШАГ 7. Отчёт tasks\WAVE20_D_REPORT.md: итог одной строкой; время по шагам; ШАГ 0 — было ли «Claude outputs/»; ШАГ 1 — коммит и дерево слияния, пуш, проверка .gitignore; ШАГ 2 — числа проверки (строки, sha256, блобы, AST, значения); ШАГ 3 — блобы тестов и прогоны; ШАГ 4 — время и пик снимка, сводка, итог сверки с числами по правилам; ШАГ 5 — 78 заданий, выходы, список выходов 5, сверка эталона расчётов; отступления — отдельными пунктами с причиной. Коммит. git push -u origin wave20-d; git ls-remote origin main wave20-d, git log --oneline origin/main..wave20-d и git status --short — дословно в отчёт (вывод после пуша — следующим коммитом, тоже запушить).
