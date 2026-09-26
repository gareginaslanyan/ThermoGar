Задание 21-С: BL-68 — где на экране пустые ячейки таблиц показываются словом «None» и как их можно показывать; опись по коду и кадрам, пробы на отдельном маленьком приложении Streamlit; код ThermoGar не менять. Мастер ThermoGar, 26.09.2026. Машина — ноутбук Windows 10, дерево D:\Pets\ThermoGar-w21a. Лёгкий поток; параллельно тяжёлый 21-О (D:\Pets\ThermoGar-w21b) — с ним не пересекаться.

ЗАПРЕТЫ
- Исключить до обхода: D:\Pets\Lilith — не открывать, не обходить, исключать из любого поиска/glob/rg/dir по диску. Поиск — только внутри D:\Pets\ThermoGar-w21a.
- D:\Pets\ThermoGar и D:\Pets\ThermoGar-w21b не трогать. Интерпретатор — D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe, PYTHONHASHSEED=0.
- ThermoGar (app\ThermoGar_app.py), AppTest и тесты не запускать. Можно: отдельное маленькое приложение-проба из results\wave21_s\proba\ (streamlit run на своём порту, один процесс, остановить после съёмки) и Playwright для его кадров.
- Менять ничего нельзя, кроме нового: tasks\WAVE21_S_OPUS.md, tasks\WAVE21_S_REPORT.md, results\wave21_s\. app\, tools\, docs\, databases\, configs\, packaging\, CHANGELOG.md, tasks\REGISTER.md не менять.
- Ничего не удалять: rm, del, Remove-Item, rmdir не применять; лишнее — в D:\Pets\ThermoGar-w21a\_to_delete\21s_<что>\ + опись sha256.
- В main не вливать.
- На любом СТОП: остановиться, доложить.

ЧТО УЖЕ ИЗВЕСТНО (замер мастера: Streamlit 1.62.0, Linux, Chromium, locale ru-RU — сверить на ноутбуке)
- st.dataframe: пустое значение (NaN или None) и в числовом, и в текстовом столбце показывается серым словом «None»; df.style.format(na_rep="—") его не меняет (формат чисел при этом действует).
- st.data_editor: None в числовом столбце — «None»; в текстовом столбце пустая строка "" — пустая ячейка.
- На кадрах: results\wave21_l\10b\S11_fe_umolch_ch1.png — таблица T₀, столбец состава «None» в строках без состава; results\wave21_m\kadry\uprugie_shag2_svet.png — таблица фаз «Упругих свойств» (E, ν, происхождение, источник, температура источника) — «None».
- После 21-О (идёт) строки T₀ без решения (сталь, окно 200–950 °C: C 1.8–2.0 мас.%) дадут «None» в столбцах «T₀, °C» и «T₀, K».
- В app\*.py 64 вызова st.dataframe / st.data_editor / st.table: ThermoGar_app.py — 37, thermogar_workspace.py — 7, thermogar_precipitation.py — 6, thermogar_diffusion.py — 5, thermogar_stage14.py — 5, thermogar_properties.py — 4.

ШАГ 0. В D:\Pets\ThermoGar-w21a: git status --short — только «?? _to_delete/», иначе СТОП. git fetch origin (при обрыве сети — адресный git fetch origin main). git ls-remote origin main — a68a41704f4db6053d8c073c96c30938251be930, иначе СТОП (если 21-О уже влил что-то ещё — СТОП, доложить хеш). git switch --detach origin/main; git switch -c wave21-s. Это задание без первой строки «/caveman ultra» — дословно в tasks\WAVE21_S_OPUS.md, первый коммит ветки.

ШАГ 1. Опись по коду: каждый из 64 вызовов — файл:строка; экран (раздел → вкладка / вид); что за таблица; редактируемая или нет; какие столбцы могут быть пустыми и когда (по коду сборки таблицы: NaN из расчёта, None по умолчанию, пропуск в данных); пример — тест или кадр, где это видно (results\wave21_l\, results\wave21_m\, docs\guide\img\ — открыть и посмотреть), иначе «по коду». Отдельно — выгрузки: пустые значения в Excel/CSV остаются пустыми (сверить по коду записи), показ на экране их не касается. Таблица — results\wave21_s\tablicy.csv (UTF-8 с BOM, «;»).

ШАГ 2. Проба — results\wave21_s\proba\app.py (Streamlit 1.62 из venv проекта): одна таблица, похожая на T₀ (число, число, галочка, есть NaN), и одна, похожая на таблицу фаз «Упругих свойств» (st.data_editor: текст, числа, None). Варианты:
а) как сейчас — «None»;
б) пусто — копия для показа: числа переведены в текст в том же виде, что сейчас на экране, NaN → "";
в) «—» — то же, NaN → «—»;
г) средства самого Streamlit 1.62 для пустых значений — по установленному пакету (site-packages\streamlit\elements\lib\column_types.py и соседние: параметры st.column_config.*, в том числе выравнивание и значение по умолчанию); для st.data_editor — можно ли показать пустую числовую ячейку без «None».
Для каждого варианта: кадр 900×600, светлая и тёмная тема (тёмная — ?embed_options=dark_theme), Playwright, locale ru-RU; выравнивание чисел; сортировка щелчком по заголовку (числовая или по тексту); что попадает в файл через кнопку скачивания на панели таблицы; ввод в ячейку data_editor (для б и в). Кадры — results\wave21_s\kadry\, замеры — results\wave21_s\proba.csv (UTF-8 с BOM, «;»).

ШАГ 3. Предложение — текстом, кода ThermoGar не менять: по видам таблиц (таблицы результатов; таблицы-редакторы) — какой вариант и почему; где один помощник показа (по образцу element_columns_for_display, app\thermogar_user_errors.py:112 — только показ, данные и выгрузки не меняются) и сколько вызовов; какие тесты держат вид таблиц; какие кадры руководства и глав это меняет. Новых слов на экране варианты б и в не добавляют; выбор между ними — вопрос владельцу, не решать.

ШАГ 4. Отчёт tasks\WAVE21_S_REPORT.md: итоги числами (вызовов всего; с возможной пустой ячейкой; где «None» видно на кадрах); проба — по вариантам; предложение; отступления — отдельными пунктами с причиной. Коммиты на wave21-s; git push -u origin wave21-s; git ls-remote origin wave21-s; git log --oneline origin/main..wave21-s и git status --short — дословно в отчёт.
