Задание 21-Ч: BL-74 по-новому — ошибка чтения марок в «Проекты и данные → Марки и составы» перехвачена, «Код ошибки» и технический отчёт, без «Техническая причина» в тексте; документы пользователя под 0.5.0 — встроенное краткое руководство (опись 21-Ц), USER_GUIDE_THERMOGAR.md, QUICK_START_THERMOGAR.md, README.md. Мастер ThermoGar, 26.09.2026. Машина — ноутбук Windows 10, дерево D:\Pets\ThermoGar-w21a. Лёгкий поток; параллельно тяжёлый 21-Х (D:\Pets\ThermoGar-w21b) — с ним не пересекаться.

ЗАПРЕТЫ
- Исключить до обхода: D:\Pets\Lilith — не открывать, не обходить, исключать из любого поиска/glob/rg/dir по диску. Поиск — только внутри D:\Pets\ThermoGar-w21a.
- D:\Pets\ThermoGar и D:\Pets\ThermoGar-w21b не трогать. Интерпретатор — D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe; все прогоны — PYTHONHASHSEED=0, MPLBACKEND=Agg, PYTHONDONTWRITEBYTECODE=1, python -B, THERMOGAR_STATE_ROOT во временной папке.
- Приложение, streamlit run, AppTest, браузер, tools\make_guide_screens.py, tools\tab_snapshot.py и полную регрессию не запускать: поток лёгкий. Разрешены только pytest-файлы ШАГА 4.
- Менять можно только: app\thermogar_workspace.py (ШАГ 1), строку USER_GUIDE_MD в app\ThermoGar_app.py (ШАГ 2), USER_GUIDE_THERMOGAR.md, QUICK_START_THERMOGAR.md, README.md (ШАГ 3), tools\test_wave21_ts.py (снять xfail, ШАГ 4); новое — tools\test_wave21_ch.py, tasks\WAVE21_CH_OPUS.md, tasks\WAVE21_CH_REPORT.md, results\wave21_ch\. В USER_GUIDE_THERMOGAR.md, QUICK_START_THERMOGAR.md, README.md не трогать строки 1–3 и README.md:99–103 (номер версии — 21-Х); docs\, tasks\REGISTER.md, databases\, configs\, packaging\, CHANGELOG.md не менять; байты баз не меняются.
- Новых слов на экране нет: ШАГ 1 — только уже существующие тексты. В документах (ШАГИ 2–3) — по правилам ниже.
- Ничего не удалять: rm, del, Remove-Item, rmdir не применять; лишнее — в D:\Pets\ThermoGar-w21a\_to_delete\21ch_<что>\ + опись sha256.
- В main не вливать.
- На любом СТОП: остановиться, доложить.

ШАГ 0. В D:\Pets\ThermoGar-w21a: git status --short — только «?? _to_delete/», иначе СТОП. git fetch origin (при обрыве сети — адресный git fetch origin wave21-ts). git ls-remote origin wave21-ts — 06386fc1ccfd4372551269ee99ccecc0d20c04df, иначе СТОП. git switch --detach 06386fc1ccfd4372551269ee99ccecc0d20c04df; git switch -c wave21-ch. Это задание без первой строки «/caveman ultra» — дословно в tasks\WAVE21_CH_OPUS.md, первый коммит ветки.

ШАГ 1. BL-74 (по находке 21-Ц, отчёт tasks\WAVE21_TS_REPORT.md, ШАГ 2): ошибка read_json в «Марки и составы» не перехвачена — Streamlit показывает исключение с трассировкой, «Кода ошибки» и технического отчёта нет. app\thermogar_workspace.py:
- render_alloy_library (:1096): обе загрузки марок (:1123 и :1178, user_alloys = load_user_alloys(paths)) — через новый помощник: при UserRuntimeError — st.error(user_message_text(error)) и render_error_details(error, context="Марки и составы", paths=paths) (импорт из thermogar_stage14), список своих марок — пустой; остальная вкладка строится (учебные марки, форма). Ошибка на экране — один раз за прогон, не дважды. Новых текстов нет.
- read_json (:378–383): из своего сообщения убрать « Техническая причина: {error}». Стало: «Файл {source.name} не читается. Не заменяйте его пустым файлом: восстановите резервную копию или исправьте JSON.» `from error` оставить — причина уходит в технический отчёт (traceback с цепочкой).
Коммит.

ШАГ 2. Встроенное краткое руководство — строка USER_GUIDE_MD (app\ThermoGar_app.py:12260–12468). Места — опись 21-Ц results\wave21_ts\kratkoe_rukovodstvo.csv (20 строк). Правила:
- названия вкладок, видов, блоков, полей, кнопок и сообщений — дословно по коду (файл:строка — в таблицу правок);
- шаблоны фраз (из глав руководства, 21-Р): поле в блоке — «… — в свёрнутом блоке «<блок>»: раскройте его.»; вкладка, ставшая видом, — «вариант «<вид>» переключателя», «над переключателем видов»; строка кнопки — один раз на документ: «Строка с кнопкой расчёта держится у нижнего края окна, пока форма не прокручена до её места. Над кнопкой — подпись «Не по умолчанию: …»: она перечисляет поля свёрнутых блоков, которые вы изменили.»; неактивная кнопка — «кнопка «<кнопка>» неактивна, под ней сказано, что заполнить.»;
- правка, которую шаблоны не покрывают, — наименьшая по сути, словами с экрана; в таблице правок пометка «новая формулировка — на проверку мастера»;
- дробные запятые и остальной текст — как есть.
Таблица правок — results\wave21_ch\pravki_kratkoe.csv (UTF-8 с BOM, «;»): строка; было; стало; основание (строка описи 21-Ц, файл:строка кода); пометка. Коммит.

ШАГ 3. USER_GUIDE_THERMOGAR.md, QUICK_START_THERMOGAR.md, README.md — сначала опись, как 21-Ц: каждое место, где описан экран, изменённый волнами 20–22 (21-И, 21-М, 21-О, 21-Ж, 22-Б, 21-У), — results\wave21_ch\opis_dokumentov.csv (файл:строка; цитата до 200 знаков; что устарело; задание или решение). Потом правки по правилам ШАГА 2 — results\wave21_ch\pravki_dokumentov.csv. Не трогать: строки 1–3 этих файлов и README.md:99–103 (номер версии — 21-Х); место примера остановки расчёта выделений в USER_GUIDE_THERMOGAR.md (около :285–301) — его правит задача выпуска по текстам 21-Х; в описи — отдельной строкой. Коммит.

ШАГ 4. Тесты:
- tools\test_wave21_ts.py: снять xfail с test_bl74_broken_json_message_has_no_technical_reason (теперь зелёный).
- Новый tools\test_wave21_ch.py, без AppTest: помощник ШАГА 1 на битом alloys.json во временной папке (st.error и render_error_details подменить через monkeypatch) — список пустой; st.error вызван один раз, текст начинается с «Файл alloys.json не читается.», без «Техническая причина»; render_error_details получил исключение, у которого __cause__ — json.JSONDecodeError; при исправном файле — прежний список, st.error не вызывается. Сначала — красный на коде до правки ШАГА 1, итог в отчёт.
- Прогон: tools\test_wave21_ch.py, tools\test_wave21_ts.py, tools\test_user_errors_21zh.py, tools\test_version_consistency.py — зелёные, иначе СТОП (чужое красное — доложить).
Коммит.

ШАГ 5. Отчёт tasks\WAVE21_CH_REPORT.md: ШАГ 1 — файл:строка после правки, было → стало, путь показа ошибки до и после; ШАГИ 2–3 — итоги числами (мест в описи, правок по шаблонам, «новых формулировок» — списком с цитатами); тесты до и после; отступления — отдельными пунктами с причиной. Коммиты на wave21-ch; git push -u origin wave21-ch; git ls-remote origin wave21-ch; git log --oneline 06386fc..wave21-ch и git status --short — дословно в отчёт.
