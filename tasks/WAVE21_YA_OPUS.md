Задание 21-Я: BL-79 — русские надписи вместо английских надписей самого Streamlit 1.62 (загрузчики файлов, число вне границ поля, списки выбора); предел загрузки 64 МБ; тест-сторож. Мастер ThermoGar, 27.09.2026. Машина — ноутбук Windows 10, дерево D:\Pets\ThermoGar-w21a, ветка wave21-ya от main 47282dc. Лёгкий поток; параллельно тяжёлый 21-Ю2 в D:\Pets\ThermoGar-w21b — с ним не пересекаться. Кадры руководства, HTML, CHANGELOG и реестр не трогать: их делает задача выпуска после слияния этой ветки.

Решения владельца 27.09.2026 (холст «ThermoGar: английские надписи Streamlit — на «да»» — «согласен с рекомендациями»; два вопроса мастера — «Выбрать все», «одна фраза на оба»): 0Б — заменить надписи оформлением, отступление от правила S-4, как 1Г, 2Б, 4Б от 24.09; 1–8 — А; 9 — оставить (подсказки кнопок над таблицами и графиками не трогать); 10 — «Выбрать все»; 11 — «Ничего не найдено или уже выбрано восемь фаз.». Любой другой новый текст на экране — СТОП.

ЗАПРЕТЫ
- Исключить до обхода: D:\Pets\Lilith — не открывать, не обходить, исключать из любого поиска/glob/rg/dir по диску. Поиск — только внутри D:\Pets\ThermoGar-w21a и пакета streamlit интерпретатора.
- D:\Pets\ThermoGar и D:\Pets\ThermoGar-w21b не трогать. Интерпретатор — D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe; пакеты не ставить и не менять.
- Меняются только: .streamlit\config.toml, app\style.css, app\ThermoGar_app.py, app\thermogar_diffusion.py, app\thermogar_workspace.py (только ШАГ 3 — параметр placeholder), новый tools\test_wave21_ya.py, tasks\WAVE21_YA_OPUS.md, tasks\WAVE21_YA_REPORT.md, results\wave21_ya\. Нужно другое — СТОП. В main не вливать.
- Ничего не удалять: rm, del, Remove-Item, rmdir не применять; лишнее — D:\Pets\ThermoGar-w21a\_to_delete\21ya_<что>\ + опись sha256. Временные файлы (в том числе файл 65 МБ ШАГА 5) — во временной папке сессии вне дерева.
- Все прогоны — PYTHONHASHSEED=0, MPLBACKEND=Agg, PYTHONDONTWRITEBYTECODE=1, THERMOGAR_STATE_ROOT во временной папке; pytest с -B; одновременно один прогон.
- Номера строк — замер мастера на 47282dc, сверить; тексты — дословно, иначе СТОП.
- На любом СТОП: остановиться, доложить.

ШАГ 0. git status --short — только «?? _to_delete/», иначе СТОП. git fetch origin; git ls-remote origin main — 47282dcb2dc8f213be361769c4ed8691f989c0a0, иначе СТОП. git switch --detach 47282dc; git switch -c wave21-ya. Это задание без первой строки «/caveman ultra» — дословно в tasks\WAVE21_YA_OPUS.md, первый коммит. python -c "import streamlit; print(streamlit.__version__)" — 1.62.0, иначе СТОП.

ШАГ 1. Замер до правки — results\wave21_ya\zamer_do.json и кадры results\wave21_ya\kadry\do_*.png. Запустить приложение дерева (streamlit run app\ThermoGar_app.py, свой порт, папка состояния — временная) и сценарием Playwright (как tools\make_guide_screens.py; сценарий — results\wave21_ya\scripts\) в светлой и тёмной теме снять и записать getComputedStyle (font-size, font-weight, color, line-height) английского текста в каждом месте ниже. Места:
- «Проекты и данные»: «Марки и составы» — загрузчик «Импортировать библиотеку JSON»; «Пакетный расчёт» — «Файл составов»; «Проекты и история» — «Импортировать проект». В каждом: пустой загрузчик (кнопка «Upload», строка «200MB per file • …»); файл тянут на загрузчик (DragEvent dragenter/dragover с файлом в DataTransfer) — «Drag and drop a file here»; выбран файл CSV (у «Файла составов») — карточка с размером вида «132.0B»; файл не того типа (.txt) — красная карточка, при наведении подсказка «text/plain files are not allowed.»; файл 65 МБ — подсказка «File must be 200.0MB or smaller.» не появится (Streamlit примет до 200 МБ) — записать, что показала программа.
- Числовое поле с границами, например «Шаг поиска границ, ат.% (0.5–10)»: ввести 20 и Enter — значок и подсказка «Error: Number is outside the allowed range. …».
- Список выбора нескольких значений, например «Энергии → Энергии фаз», «Фазы для сравнения — не более восьми» (ключ energy_curve_phases_<база>): раскрыть — первая строка «Select all»; напечатать часть имени, чтобы совпало ≥2 фазы, — первая строка «Select N matches»; снять все фазы — «Choose options»; выбрать восемь и раскрыть — «You can only select up to 8 options. Remove an option first.»; напечатать «zzz» (при выбранных меньше восьми) — «No results».
- Список выбора одного значения, например «Элемент-основа» в боковой панели: напечатать «zzz» — «No results».
- Для сравнения после правки: обычный раскрытый список с вариантами; подсказка «?» у любого поля; подсказка кнопки над таблицей (например «Search»).

ШАГ 2. Предел загрузки: в .streamlit\config.toml в конец файла — пустая строка и
```
[server]
maxUploadSize = 64
```
(64 МБ Streamlit = 64 · 1024 · 1024 байт = MAX_WORKSPACE_FILE_BYTES, app\thermogar_secure_io.py:19). Остальное в файле не менять. Коммит.

ШАГ 3. Пустой список выбора нескольких значений (решение 7А): у пяти вызовов st.multiselect — параметр placeholder="Выберите из списка": app\ThermoGar_app.py :1602 («Фазы»), :11355 («Фазы для сравнения — не более восьми»), :11672 («Фазы исходного равновесия»); app\thermogar_diffusion.py :1724 («Фазы локального равновесия»); app\thermogar_workspace.py :2124 («Показывать события»). Других вызовов st.multiselect в app\ нет — сверить. Коммит.

ШАГ 4. app\style.css — в конец файла один блок с комментарием: «BL-79, решения владельца 27.09.2026 (холст «ThermoGar: английские надписи Streamlit — на «да»»: 0Б, 1–8 А, 10, 11): отступление от S-4 — надписи самого Streamlit 1.62 заменяются оформлением; сторож — tools/test_wave21_ya.py.» Приём везде один: у элемента с английским текстом font-size: 0, новый текст — ::after { content: "…" } с размером, насыщенностью и цветом прежнего текста по замеру ШАГА 1 (расхождение — не больше 0.5 px; цвет — наследуется); подсказки — те же, что проверил мастер на Streamlit 1.62 (селекторы — сверить на приложении). Тексты — дословно:
1) кнопка загрузчика — `[data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"] [data-testid="stMarkdownContainer"] p` → «Выбрать файл»;
2) строка рядом с кнопкой — `[data-testid="stFileUploaderDropzoneInstructions"] span`, по загрузчику: `.st-key-batch_file_uploader …` → «CSV или XLSX, до 64 МБ»; `.st-key-project_uploader …` и `.st-key-alloy_library_uploader …` → «JSON, до 64 МБ»;
3) при перетаскивании — `[data-testid="stFileUploaderDropzone"] > div:not([data-testid]) > span` → «Отпустите файл здесь»;
4) размер выбранного файла — `[data-testid="stFileChipName"] + *` → display: none (текста нет);
5) подсказка у отклонённого файла — `[data-testid="stTooltipErrorContent"]:not(:has([data-testid="stMarkdownContainer"]))` → «Файл не принят: не тот тип или больше 64 МБ.»;
6) подсказка у числа вне границ — `[data-testid="stTooltipErrorContent"]:has([data-testid="stMarkdownContainer"]) p` (дочерние элементы p — display: none) → «Число вне допустимых границ поля.»;
8) поиск без совпадений — `[role="option"][style*="display: contents"] > span` → «Ничего не найдено»;
10) первая строка раскрытого списка выбора нескольких значений — `[role="option"][data-key="__select_all__"] > div` и `[role="option"][data-key="__select_matches__"] > div` → «Выбрать все» (при поиске Streamlit пишет «Select N matches»; строка выбирает все найденные — тот же утверждённый текст, нового слова нет);
11) в списке «Фазы для сравнения — не более восьми» — `[role="listbox"][aria-label="Фазы для сравнения — не более восьми"] [role="option"][style*="display: contents"] > span` → «Ничего не найдено или уже выбрано восемь фаз.» (правило сильнее п. 8: здесь «No results» и «You can only select up to 8 options. Remove an option first.» одинаковы по разметке).
Другое не трогать: подсказки кнопок над таблицами, графиками и блоками кода остаются (решение 9А), подсказки «?» полей программы — тоже. Коммит.

ШАГ 5. Проверка на приложении — тем же сценарием ШАГА 1, после правки, обе темы; кадры results\wave21_ya\kadry\posle_*.png, замер results\wave21_ya\zamer_posle.json. Ждать: во всех местах ШАГА 1 — тексты ШАГОВ 2–4 вместо английских; размер, насыщенность, цвет ::after = прежнему тексту (±0.5 px); размер у карточки файла не виден; файл 65 МБ теперь отклоняет сам Streamlit — красная карточка и «Файл не принят: не тот тип или больше 64 МБ.» при наведении; «Выберите из списка» у пустого списка; обычные варианты списков, подсказки «?» и подсказки кнопок над таблицами — как до правки (кадры рядом). Английский текст в этих местах остался — править ШАГ 4; не выходит — СТОП.

ШАГ 6. Новый tools\test_wave21_ya.py, без AppTest:
- style.css: блок BL-79 есть; каждый текст ШАГА 4 стоит в content дословно при своём селекторе (п. 1–6, 8, 10, 11);
- config.toml: [server] maxUploadSize = 64, и 64 · 1024 · 1024 == MAX_WORKSPACE_FILE_BYTES;
- по AST: вызовов st.multiselect в app\*.py — 5, у каждого placeholder="Выберите из списка";
- сторож Streamlit: streamlit.__version__ == "1.62.0"; в файлах streamlit\static\static\js\ есть строки, на которые опираются селекторы и замены: FileUploader*.js — «stFileUploaderDropzoneInstructions», «`Upload`», « per file», «`Drag and drop a file here`»; utils*.js, где есть «stFileChipName», — «stFileChipName», « files are not allowed.», «File must be »; Tooltip*.js — «stTooltipErrorContent»; NumberInput*.js — «Number is outside the allowed range», «**Error**: »; Multiselect*.js — «`Select all`», «__select_all__», «__select_matches__», «`No results`», «You can only select up to», «display:`contents`»; Selectbox*.js — «`No results`» (строки — замер мастера на 1.62.0, сверить; нет строки — СТОП). В строке документа теста: при обновлении Streamlit тест падает — замены ШАГА 4 проверить заново.
Сначала — красный на 47282dc (число failed — в отчёт), потом зелёный. Зелёные, иначе СТОП: tools\test_wave21_ya.py, tools\test_style_21z.py, tools\test_chart_theme_21e.py, tools\test_version_consistency.py, tools\test_user_errors_21zh.py, tools\test_ui_h.py. Коммит.

ШАГ 7. Отчёт tasks\WAVE21_YA_REPORT.md: замер ШАГА 1 (где, что за текст, размер и цвет) и ШАГА 5 (стало) — таблицей; селекторы, если отличаются от ШАГА 4, — с причиной; список кадров; тесты до и после; отступления — отдельными пунктами с причиной. Коммиты на wave21-ya; git push -u origin wave21-ya; git ls-remote origin main wave21-ya; git log --oneline 47282dc..wave21-ya и git status --short — дословно в отчёт (вывод после пуша — следующим коммитом, тоже запушить).
