Задание 21-Р: подготовка пересборки руководства без съёмки — tools/make_guide_screens.py (переключатели 21-И, свёрнутые блоки 21-М, подписи, сценарий «soobshcheniya» из 17-Д), tools/tab_snapshot.py (случаи, которые сломал 21-И), главы docs/guide/ — места, не зависящие от чисел 21-О; без запуска приложения. Мастер ThermoGar, 26.09.2026. Машина — ноутбук Windows 10, дерево D:\Pets\ThermoGar-w21a. Лёгкий поток; параллельно тяжёлый 21-О (D:\Pets\ThermoGar-w21b) — с ним не пересекаться.

ЗАПРЕТЫ
- Исключить до обхода: D:\Pets\Lilith — не открывать, не обходить, исключать из любого поиска/glob/rg/dir по диску. Поиск — только внутри D:\Pets\ThermoGar-w21a.
- D:\Pets\ThermoGar и D:\Pets\ThermoGar-w21b не трогать. Интерпретатор — D:\Pets\ThermoGar\.venv-windows\Scripts\python.exe, PYTHONHASHSEED=0.
- Приложение, streamlit, AppTest, браузер, съёмку и тесты не запускать (на ноутбуке идёт тяжёлый поток). Можно: python -B -m py_compile, python -B tools\make_guide_screens.py --help, python -B -m pytest -p no:cacheprovider tools\test_tab_snapshot_compare.py (без приложения, секунды).
- Менять можно только tools\make_guide_screens.py, tools\tab_snapshot.py, docs\guide\*.md. Новое — tasks\WAVE21_R_OPUS.md, tasks\WAVE21_R_REPORT.md, results\wave21_r\. app\, другие tools\, docs\FEATURES.md, docs\LIMITS_OF_APPLICABILITY.md, docs\guide\img\, docs\guide\*.html, results\wave17_d\, databases\, configs\, packaging\, CHANGELOG.md, tasks\REGISTER.md не менять. HTML_NAME и HTML_TITLE (tools\make_guide_screens.py:46–47) не менять — номер выпуска решает владелец.
- Названия на экране (блоки, кнопки, варианты переключателей, подписи полей) — дословно по коду app\ на origin/main; новых терминов в главах не вводить.
- Ничего не удалять: rm, del, Remove-Item, rmdir не применять; лишнее — в D:\Pets\ThermoGar-w21a\_to_delete\21r_<что>\ + опись sha256.
- В main не вливать.
- На любом СТОП: остановиться, доложить.

ИСХОДНЫЕ (сверено мастером по коду)
- Опись 21-П — ветка origin/wave21-p (принята мастером 26.09.2026): tasks/WAVE21_P_REPORT.md (ШАГ 4 — предложение), results/wave21_p/scenarii.csv, rukovodstvo.csv, kadry.csv, snimki.csv; читать через git show, номера строк make_guide_screens.py и tab_snapshot.py в описи — те же, что на origin/main (файлы с wave21-m не менялись). Поправка мастера к описи: буквы решений 21-О — 1Б = выдержка «Выделений» стали 0.01 ч, 2В = окно T₀ стали 200–950 °C, 3В = «ушла ниже нуля» (в описи 1Б и 2В переставлены).
- Переключатели (st.segmented_control, подпись скрыта): «Затвердевание» — ключ solidification_result_view, варианты «Сводка», «Твёрдые фазы», «Остаточный расплав», «Выгрузка» (app\ThermoGar_app.py:11063–11074); «Кинетика выделений» — precipitation_result_view, «Итоги», «Кинетика и состав», «Распределение размеров», «Экспорт и ограничения» (app\thermogar_precipitation.py:1826–1832); «Диффузия и гомогенизация» — kinetics_diffusion_view, «Однофазная пара», «Многофазная гомогенизация», «Покрытие базы подвижностей» (app\thermogar_diffusion.py:1537–1547). Выбор в браузере — как pick в results\wave21_i\scripts\sokhranenie.py:69–73 (get_by_role("radiogroup", name=…).get_by_role("radio", name=…)).
- Названия блоков — app\thermogar_release_ui.py:51–53: «Точность и критерии», «Управление фазами / метастабильный расчёт», «Параметры модели».
- widget() (tools\make_guide_screens.py:350–353) ищет поле по подстроке подписи среди видимых.
- 718 для кадров «soobshcheniya-03, 04»: на сетке раздела по умолчанию (0.2…10 нм, 80 классов), 700 °C, γ = 0.095 Дж/м² после 22-Б расчёт по-прежнему останавливается (мастер, Linux: на 3.824 с) — сценарий годится.

ШАГ 0. В D:\Pets\ThermoGar-w21a: git status --short — только «?? _to_delete/», иначе СТОП. git fetch origin (при обрыве сети — адресный git fetch origin main wave21-p). git ls-remote origin main wave21-p: main — a68a41704f4db6053d8c073c96c30938251be930 (слияния 21-О), wave21-p — 71827714552b05ddb241e178e05edc216c8eb151, иначе СТОП. git switch --detach origin/main; git switch -c wave21-r. Это задание без первой строки «/caveman ultra» — дословно в tasks\WAVE21_R_OPUS.md, первый коммит ветки.

ШАГ 1. tools\make_guide_screens.py — по предложению 21-П (tasks/WAVE21_P_REPORT.md, ШАГ 4, п. 1–7 и 9):
а) Помощники рядом с open_tab (:432–436): pick_view(page, group, option) — щелчок по варианту переключателя и wait_idle; view_ready(page, group, option, timeout) — ожидание варианта вместо ожидания вкладки. Константы BLOCK_PRECISION, BLOCK_PHASES, BLOCK_MODEL — копией строк app\thermogar_release_ui.py:51–53 (не импортом: скрипт не должен тянуть модули приложения). open_tab — только для настоящих вкладок.
б) diagrammy: :588 — подпись поля «Al: до, ат.%» (поиск по подстроке); перед :590 — open_expander(…, BLOCK_PRECISION), вводы :590 и :596 — в блоке; кадр :598 — с раскрытым блоком и подписью «Не по умолчанию: …» над кнопкой в числе целей кадра.
в) zatverdevanie: перед :649 — open_expander(…, BLOCK_PRECISION); :662 — view_ready(page, "Затвердевание", "Сводка"); :677 — pick_view(page, "Затвердевание", "Выгрузка").
г) energii: перед :699 — open_expander(…, BLOCK_PHASES); перед :709 — open_expander(…, BLOCK_PRECISION).
д) kinetika: :841 — view_ready(page, "Кинетика выделений", "Итоги"); :853 — pick_view(page, "Диффузия и гомогенизация", "Однофазная пара"); перед :866 — open_expander(…, BLOCK_MODEL), чтобы «Длина области, мкм» была на кадре.
е) Сценарий soobshcheniya: перенести из results\wave17_d\guide_screens_042.py (scenario_soobshcheniya :84–185, помощники alerts :57, set_composition :61, kwn_inputs :78, составы ALLOY_718 :33 и EK199_SI5 :35, заполнение KWN_718 из study_wave15_v_718.case_arguments(700.0, 95.0, …) в main) в tools\make_guide_screens.py девятым сценарием SCENARIOS; ожидание вкладки «Итоги» — view_ready(page, "Кинетика выделений", "Итоги"); кадры — прежние имена soobshcheniya-01…05; чтения READINGS — в журнал сценария. Подмену Shooter.shot из 17-Д (_shot_with_version, :40) не переносить, если она не нужна для кадров; решение — в отчёт. Файл results\wave17_d\ не менять.
ж) Проверка: py_compile; --help; сверка по коду, что каждый шаг сценариев 21-П с оценками «вкладки нет», «блок свёрнут», «подпись изменилась», «ломается» исправлен — таблица results\wave21_r\scenarii_pravki.csv (UTF-8 с BOM, «;»): № строки описи 21-П, файл:строка до и после, что сделано.
Коммит.

ШАГ 2. tools\tab_snapshot.py — случаи, которые сломал 21-И (отчёт 21-И, tasks/WAVE21_I_REPORT.md:108–123; опись 21-П, snimki.csv):
а) case_g_hom (:731–737) и case_g_hom_al (:740–742): до ввода полей — вид «Многофазная гомогенизация» (app.state["kinetics_diffusion_view"] и отдельный шаг app.run с подписью).
б) Выгрузки на невыбранных видах: после расчёта — отдельным шагом вид «Выгрузка» (solidification_result_view) у f_solid и sh_solid, вид «Экспорт и ограничения» (precipitation_result_view) у g_kwn* — чтобы перехват выгрузок их поймал.
в) Остальное в tab_snapshot.py не менять. Проверка — py_compile и tools\test_tab_snapshot_compare.py. Перечень правок (случай, файл:строка, что сделано) — в отчёт.
Коммит.

ШАГ 3. Главы docs\guide\*.md — места описи 21-П (results/wave21_p/rukovodstvo.csv), которые не зависят от чисел 21-О: строки 1–6, 8–12, 15, 20–23; и попутные находки 21-П: 01-raschety.md:89 — «**Скачать Excel**», «**Скачать CSV**», «**Скачать PNG**»; 05-svoystva.md:18 — «Покрытие физической базы» вместо «покрытие PDB»; 03-zatverdevanie.md:35 — «(по умолчанию 0,01 %)» вместо «(по умолчанию 5 %)» (умолчание поля — 0.01, 5 — верхняя граница, app\ThermoGar_app.py:10535–10538).
- Поле в свёрнутом блоке — одной фразой «… — в свёрнутом блоке «…»: раскройте его.»; вкладка, ставшая вариантом переключателя, — «вариант «…» переключателя» вместо «вкладка» / «подвкладка»; строка кнопки и подпись «Не по умолчанию: …» — по одной фразе в 02-diagrammy.md (строка 3 описи), дальше без повторов; неактивные кнопки (строки 11, 12) — «кнопка неактивна, под ней сказано, что заполнить».
- Числа в главах — десятичная запятая, как сейчас в тексте глав.
- Не трогать сейчас (после 21-О, с новыми кадрами и числами): строки 7, 13, 14, 16–19, 24–29 описи, docs\FEATURES.md, docs\LIMITS_OF_APPLICABILITY.md, подписи кадров с числами.
- Таблица results\wave21_r\glavy_pravki.csv: № строки описи (или «попутно»), файл:строка до и после, было (до 200 знаков), стало (до 200 знаков).
Коммит.

ШАГ 4. Отчёт tasks\WAVE21_R_REPORT.md: что сделано по шагам с файл:строка; что осталось на тяжёлую задачу после 21-О (съёмка 9 сценариев — 56 кадров; места глав 7, 13, 14, 16–19, 24–29 и документы FEATURES / LIMITS — числами с новых кадров; HTML_NAME / HTML_TITLE — по ответу владельца; новый эталон tab_snapshot); риски, которые видны только на съёмке; отступления — отдельными пунктами с причиной. Коммиты на wave21-r; git push -u origin wave21-r; git ls-remote origin wave21-r; git log --oneline origin/main..wave21-r и git status --short — дословно в отчёт.
