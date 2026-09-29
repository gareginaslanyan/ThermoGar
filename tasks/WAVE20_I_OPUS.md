Задание 20-И: BL-57, шаг 6 разреза — проверенная привязка базы: вместо глобальных vlb_bound_context и vlb_active_context, которые функции переписывали через global, — изменяемый объект VerifiedBinding (в app\thermogar_app_context.py), объект VLB в головном сценарии и поле binding в RunServices; VerifiedB3BatchBroker и bind_b4b_physical_context получают службы параметром; слияние 20-З в main; сверка вкладок с эталоном 0.5.0; полная регрессия; реестр (приёмка 20-З). Мастер ThermoGar, 29.09.2026. Машина — ноутбук Windows 10, дерево D:\Pets\ThermoGar-w21b. Тяжёлый поток, параллельных задач нет. Это санкция мастера на слияние wave20-z в main (ШАГ 1); wave20-i в main не вливать. Порядок сверки — tasks\WAVE20_V_REPORT.md, раздел «Как сверять шаг разреза с эталоном 0.5.0»; образец шага — tasks\WAVE20_Z_OPUS.md.

ЗАПРЕТЫ
- Исключить до обхода: D:\Pets\Lilith — не открывать, не обходить, исключать из любого поиска/glob/rg/dir по диску. Поиск — только внутри D:\Pets\ThermoGar-w21b; вне дерева ничего не искать и не читать, в том числе при СТОПе.
- D:\Pets\ThermoGar и D:\Pets\ThermoGar-w21a не трогать. Интерпретатор — D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe (не python3 и не python из PATH); пакеты не ставить и не менять. Интерпретатор не запускается — СТОП и доклад дословным сообщением, без поиска причины.
- После слияния ШАГА 1 меняются только: app\ThermoGar_app.py и app\thermogar_app_context.py (ШАГ 2), results\wave20_i\, tasks\WAVE20_I_OPUS.md, tasks\WAVE20_I_REPORT.md, tasks\REGISTER.md. Нужно другое — СТОП.
- Правка — только описанная в ШАГЕ 2: прочие строки — байт в байт; прежние параметры функций не убирать, не переименовывать и не переставлять; переформатирование запрещено. Новых слов на экране нет.
- Каталоги прогонов, состояния и журналы — только в results\validation\ (вне git).
- Ничего не удалять: rm, del, Remove-Item, rmdir не применять — и к своим пробным файлам тоже; лишнее — D:\Pets\ThermoGar-w21b\_to_delete\20i_<что>\ + опись sha256.
- Все запуски Python — с -B -X utf8; MPLBACKEND=Agg, PYTHONHASHSEED=0, PYTHONDONTWRITEBYTECODE=1; свободно не меньше 3 ГиБ на входе; снимок вкладок и регрессия — по очереди.
- Номера строк и хеши — замер мастера, сверить; тексты — дословно, иначе СТОП. На любом СТОП: остановиться, доложить, не подгонять. Время начала и конца каждого шага — в отчёт.

ШАГ 0. git status --short — только «?? _to_delete/»; любое другое — СТОП. git fetch origin. git ls-remote origin main wave20-z: main — 8d2147c523fce6c764d56f7e2e9716f284d4f0fc, wave20-z — a293c6ae441c74ec79203a8dc88d2f0bc0820bd7; иначе СТОП. Эталон results\validation\wave20_v\run1 — 130 каталогов случаев, иначе СТОП. Свободная память — в отчёт.

ШАГ 1. Слияние 20-З. git switch --detach origin/main; git merge --no-ff origin/wave20-z -m "Merge wave20-z: службы прогона ThermoGar_app.py (20-З)" — дерево 3208bfe8736da209cb3c057534ca775eccd3f320, иначе СТОП. git push origin HEAD:refs/heads/main; git switch -c wave20-i. Это задание без первой строки «/caveman ultra» — дословно в tasks\WAVE20_I_OPUS.md; коммит.

ШАГ 2. Привязка базы. До правки: app\ThermoGar_app.py — блоб 3b77bab54c6915ee5f0954fa2a1ed9f75c59fbbe, 11 177 строк; app\thermogar_app_context.py — блоб 5f4c3de51aaf68f6e886934ffdbd9e786b582e74, 50 строк; LF. Номера строк ниже — по этим файлам.
Замер мастера. Боковая панель привязывает базу (vlb_bound_context) и кладёт то же в vlb_active_context; проба StateStore (выгрузка и загрузка проектов, библиотеки, пакета) читает vlb_bound_context при каждом вызове. VerifiedB3BatchBroker._restore_sidebar через global перепривязывает vlb_bound_context на место, чтобы проба видела новое поколение привязки; bind_b4b_physical_context через global пишет vlb_active_context. vlb_active_context нигде не читается — во всех трёх местах только запись; читающего кода нет ни в app\, ни через globals(). Вынесенный в модуль класс писал бы уже в свой модуль, и проба головного сценария осталась бы на старой привязке. Поэтому: привязка — в одном изменяемом объекте VLB, его видят проба, вкладки и брокер (через RunServices.binding); vlb_active_context убирается; global в головном сценарии — 0.
а) app\thermogar_app_context.py:
1) строки документации :1–12 заменить дословно на:
```
"""Контекст прогона головного сценария ThermoGar.

BL-57, разрез app/ThermoGar_app.py. Объекты, которые головной сценарий собирает
на каждом прогоне страницы; вкладки и помощники получают их параметром, а не
читают глобальные имена головного сценария:

* SidebarContext (20-Е) — то, что выбрано в боковой панели;
* RunServices (20-З) — службы этого прогона: пути состояния, показ и запись
  ошибок, выгрузка Excel, загрузка баз, ленивая загрузка scheil, привязка базы;
* VerifiedBinding (20-И) — проверенная привязка базы этого прогона; пакетный
  расчёт и проекты перепривязывают её на месте, поэтому объект изменяемый.

Значения — те же объекты, что в головном сценарии, без копий.
"""
```
2) перед строкой «@dataclass(frozen=True)» класса RunServices — строки «@dataclass», «class VerifiedBinding:», «    bound: Any» и две пустые строки;
3) после последнего поля RunServices «    fe_profile_sha256: dict[str, str]» — строка «    binding: VerifiedBinding». В конце файла — один перевод строки.
б) app\ThermoGar_app.py, правки по номерам до правки:
1) :282 «from thermogar_app_context import RunServices, SidebarContext» → «from thermogar_app_context import RunServices, SidebarContext, VerifiedBinding»;
2) VerifiedB3BatchBroker: :639 «    def __init__(self, sidebar_selector: dict[str, Any]) -> None:» → «    def __init__(self, sidebar_selector: dict[str, Any], *, services: RunServices) -> None:»; после :640 — строка «        self._services = services»; :663, :672 и :828 «            THERMOGAR_PATHS,» → «            self._services.paths,»; удалить :667 «        global vlb_bound_context, vlb_active_context»; :669 «        vlb_bound_context = verified_loaders.bind_selected_database(» → «        self._services.binding.bound = verified_loaders.bind_selected_database(»; пять строк комментария :674–678 заменить дословно на четыре:
```
        # Пересвязывание сдвигает поколение привязки в рантайме. Проба
        # StateStore читает привязку из self._services.binding, поэтому новая
        # привязка кладётся туда же: иначе любой экспорт состояния отклонялся
        # бы ложным BINDING_STALE ещё до каких-либо действий пользователя.
```
удалить :679 «        vlb_active_context = vlb_bound_context»; на :684, :692, :693, :696 «vlb_bound_context» → «self._services.binding.bound»;
3) bind_b4b_physical_context: перед :991 «) -> verified_loaders.BoundDatabaseContext:» — строки «    *,» и «    services: RunServices,»; удалить :994 «    global vlb_active_context»; :1009 «        THERMOGAR_PATHS,» → «        services.paths,»; удалить :1030 «    vlb_active_context = context»;
4) :5633 «vlb_active_context = vlb_bound_context» заменить дословно на три строки:
```
# BL-57 (20-И): проверенная привязка базы — в изменяемом объекте: пакетный
# расчёт и проекты перепривязывают её на месте, проба StateStore и вкладки читают её.
VLB = VerifiedBinding(bound=vlb_bound_context)
```
5) проба StateStore: :5638 «        vlb_bound_context.binding_digest,» → «        VLB.bound.binding_digest,»; :5639 «        vlb_bound_context.binding_generation,» → «        VLB.bound.binding_generation,»;
6) в SERVICES после :5939 «    fe_profile_sha256=FE_PROFILE_SHA256,» — строка «    binding=VLB,»;
7) код вкладок «Расчёты»: «vlb_bound_context,» → «VLB.bound,» на :6004, :6051, :6149, :6339, :6410, :6718, :6790 (отступы прежние);
8) :10585 «bind_b4b_physical_context(database_key)» → «bind_b4b_physical_context(database_key, services=SERVICES)»; :10740 «VerifiedB3BatchBroker(vlb_selector)» → «VerifiedB3BatchBroker(vlb_selector, services=SERVICES)».
Других правок нет. После правки vlb_bound_context остаётся только в коде боковой панели, где привязка создаётся.
в) Ждать (замер мастера на модели шага — сверить): app\ThermoGar_app.py — 11 178 строк, git diff --numstat — 33 вставки, 32 удаления, sha256 954cdeb506823084abe90ec08d9b7aa976cbd809d8fe1cd63381c4bfad24837b, после git add блоб 6ce2bb2d53372c734406d21d436f5c7303b889fa; app\thermogar_app_context.py — 58 строк, sha256 83405251ed5d1414d3e2399ede1d9256aa1c8b441855af024a0f58ca0784afb2, блоб 79bdac23cfbb3d8adb972bf4e0eb97d75ae041d1. По AST: узлов верхнего уровня 241 → 241; если в обоих файлах убрать параметры и аргументы services, аргумент binding=VLB, присваивания VLB и self._services, в файле до правки — операторы global и три записи в vlb_active_context, а self._services.paths и services.paths вернуть в THERMOGAR_PATHS, self._services.binding.bound и VLB.bound — в vlb_bound_context, остальные узлы равны по ast.dump. Иначе — СТОП.
г) Проверки — скриптами прежних шагов, без правки скриптов, выводы в results\wave20_i\:
- results\wave20_e\scripts\proverka_bokovoy.py на файле до и после правки → bokovaya_do.txt, bokovaya_posle.txt: функций, читающих имена боковой панели как глобальные или объявляющих global, до — 2 (VerifiedB3BatchBroker._restore_sidebar, bind_b4b_physical_context), после — 0; имён боковой панели 46 и 46;
- results\wave20_z\scripts\proverka_sluzhb.py на файле до и после правки → sluzhby_do.txt, sluzhby_posle.txt: до — 12 функций, после — 8: load_scheil :95, scheil_available :126, render_friendly_error :323, log_error :339, _database_cache_get :501, _database_cache_commit :506, load_database :514, solidification_error_record :9224; переприсваиваний после SERVICES 0;
- в головном сценарии операторов global — 0, имени vlb_active_context — 0.
Иначе — СТОП. Коммит (оба файла app, четыре вывода).

ШАГ 3. Тесты не меняются. Зелёные, иначе СТОП: tools\test_version_consistency.py (96 passed), tools\test_ui_h.py (без slow — проекты, библиотека и пакет через VerifiedB3BatchBroker и пробу StateStore), tools\test_physical_overrides_toggle.py, tools\test_density_below_pdb.py, tools\test_sidebar_composition_error.py, tools\thermogar_verified_state_test.py и tools\thermogar_paths_test.py (оба unittest). Замер мастера на Linux (все tools\test_*.py и thermogar_*_test.py без slow, до и после правки): итоги одинаковые.

ШАГ 4. Сверка вкладок с эталоном 0.5.0 (как 20-З, ШАГ 4).
- python -B -X utf8 tools\tab_snapshot.py run --out results\validation\wave20_i\posle --state results\validation\wave20_v\state\run8 --time-csv results\wave20_i\posle_time.csv; консоль — results\wave20_i\posle_stdout.txt; сводка — results\wave20_i\posle_svodka.txt (130 из 130: код 0, «ошибка» null, «исключений_на_экране» 0); posle_sha256.txt — как у 20-З.
- Правила — results\wave20_g\isklyucheniya.txt без изменений (14 правил; копию не делать). python -B -X utf8 tools\tab_snapshot_compare.py results\validation\wave20_v\run1 results\validation\wave20_i\posle --isklyucheniya results\wave20_g\isklyucheniya.txt --otchet results\wave20_i\sravnenie.txt — ждать код 0, «ИТОГ: полное равенство», срабатывания правил — те же 14 чисел, что у 20-З. Любое «различаются» или «нет пары» — разобрать; не от хеша ThermoGar_app.py — СТОП; новых правил не вводить.
Коммит (posle_time.csv, posle_stdout.txt, posle_svodka.txt, posle_sha256.txt, sravnenie.txt).

ШАГ 5. Полная регрессия — после ШАГА 4. Копия раннера results\wave20_z\scripts\run_regress.py → results\wave20_i\scripts\run_regress.py; в копии две правки: :68 «RELEASE_OUT = ROOT / "results" / "wave20_z"  # каталог вывода 20-З» → «RELEASE_OUT = ROOT / "results" / "wave20_i"  # каталог вывода 20-И»; :141 «results/validation/wave20_z_state» → «results/validation/wave20_i_state». python -B -X utf8 results\wave20_i\scripts\run_regress.py — СВЕРИТЬ 78 заданий; ждать 69 выход 0 и 9 выход 5 (тот же список, что у 20-З); итоговые строки — как у 20-З; всего 1090 passed, 1 xfailed. test_ui_f -m slow одним процессом только при ≥ 6,0 ГиБ. Красное — разобрать; следствие правки — СТОП. python -B -X utf8 results\wave21_eh\scripts\backend_compare.py results\wave20_i\regress_backend results\wave20_i\backend_compare.txt — «ВЕРДИКТ: PASS». Коммит results\wave20_i\.

ШАГ 6. tasks\REGISTER.md — тексты мастера дословно, <…> заполнить. Коммит.
а) Таблица волны 20, строка 20-З: в ячейке состояния «**сдано, мастер не смотрел.**» → «**принята мастером 29.09.2026 (ниже); влита в `main` (`<7 знаков коммита слияния ШАГА 1>`).**», остальное не менять.
б) После строки 20-З:
| 20-И | `WAVE20_I_OPUS.md` | `ThermoGar-w21b` / `wave20-i` | шаг 6 разреза: слияние 20-З в `main`; проверенная привязка базы — изменяемый объект `VerifiedBinding` (`VLB`, поле `binding` в `RunServices`) вместо глобальных `vlb_bound_context`/`vlb_active_context`; `VerifiedB3BatchBroker` и `bind_b4b_physical_context` получают службы параметром; `global` в головном сценарии — 0; сверка вкладок с эталоном 0.5.0; полная регрессия | **сдано, мастер не смотрел.** <итог числами>. Отчёт `tasks/WAVE20_I_REPORT.md` |
в) После абзаца «Приёмка 20-Ж мастером (29.09.2026). …» — абзац:

Приёмка 20-З мастером (29.09.2026). Замер мастера по `main` (`8d2147c`) и `wave20-z` (`a293c6a`, от `8d2147c`): задание дословно; слияние 20-Ж — родители `d15774b` и `70bf983`, дерево `2a671ce` = модель мастера; изменены только `app/ThermoGar_app.py` (блоб `3b77bab` = модель мастера) и `app/thermogar_app_context.py` (блоб `5f4c3de` = модель мастера), `results/wave20_z/` и `tasks/`; скрипт `proverka_sluzhb.py`, запущенный мастером, дал `sluzhby_do.txt` и `sluzhby_posle.txt` байт в байт; по AST после отката правок 239 узлов равны прежним; копия раннера — две строки, как в задании. Прогоны на Linux всех файлов тестов до и после правки — одинаковые итоги. Сверка вкладок: сводка 130 из 130 — код 0, ошибок 0, исключений на экране 0; 3573 файла байт в байт равны эталону (по спискам сумм), 463 — те же файлы, что у 20-Ж, с 14 правилами; полное равенство. Регрессия — 78 заданий: 69 выход 0, 9 выход 5 (тот же список), итоговые строки равны 20-Ж; 1090 passed, 1 xfailed; сверка эталона расчётов PASS. Реестр совпал с моделью мастера целиком. Отступления исполнителя приняты.

г) Строка BL-57, ячейка состояния: «**в работе, волна 20; шаг 0 — 20-А; эталон 0.5.0 — 20-В; шаг 1 — удаление неиспользуемого кода (20-Г); шаг 2 — тексты и умолчания (20-Д); шаг 3 — контекст боковой панели (20-Е); шаг 4 — общие помощники (20-Ж); шаг 5 — службы прогона (20-З).**» → «**в работе, волна 20; шаг 0 — 20-А; эталон 0.5.0 — 20-В; шаг 1 — удаление неиспользуемого кода (20-Г); шаг 2 — тексты и умолчания (20-Д); шаг 3 — контекст боковой панели (20-Е); шаг 4 — общие помощники (20-Ж); шаг 5 — службы прогона (20-З); шаг 6 — привязка базы (20-И).**», остальное не менять.

ШАГ 7. Отчёт tasks\WAVE20_I_REPORT.md: итог одной строкой; время по шагам; ШАГ 0 — вывод git status; ШАГ 1 — коммит и дерево слияния, пуш; ШАГ 2 — числа проверки (строки, sha256, блобы, AST, выводы проверок до и после, global и vlb_active_context); ШАГ 3 — прогоны; ШАГ 4 — время и пик снимка, сводка, итог сверки с числами по правилам; ШАГ 5 — 78 заданий, выходы, список выходов 5, passed, сверка эталона расчётов; отступления — отдельными пунктами с причиной. Коммит. git push -u origin wave20-i; git ls-remote origin main wave20-i, git log --oneline origin/main..wave20-i и git status --short — дословно в отчёт (вывод после пуша — следующим коммитом, тоже запушить).
