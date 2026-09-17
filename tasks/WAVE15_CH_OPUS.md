Задача 15-Ч — BL-40: подготовка упругих свойств падает на никелевом составе с углеродом. Терминал
расчётный; второй поток на машине — документный.

ЧТО ПРОЧИТАТЬ ПЕРЕД РАБОТОЙ
- tasks/RULES.md целиком
- tasks/WAVE15_F_REPORT.md, п. 0.1 (падение Ni-20Cr-0,3C, results/wave15_f/probe/log_nicrc_on.txt)
- tasks/REGISTER.md (ветка wave15-release), строка BL-13 — как тот же класс дефекта чинился для
  плотности в 11N-2; tasks/WAVE11N_REPORT.md, п. 11N-2
- app/thermogar_database_repair.py: drop_broken_order_disorder (:475), verify_phase_builds,
  excluded_phases_note
- app/ThermoGar_app.py: prepare_calculation (~:2386) — единственная точка, где набор фаз проходит
  детектор и effective_release_phases
- app/thermogar_verified_properties.py: _default_backend (:452), как строится список фаз для
  pycalphad.equilibrium
- app/thermogar_verified_physical.py и thermogar_verified_equilibrium.py — как эти два раздела
  получают список фаз (для сравнения)

ДЕРЕВО И ВЕТКА. C:\Users\gareg\Desktop\ThermoGar-w15d, ветка wave15-bl38, HEAD be1fe81. Продолжать
на ней. В main и wave15-release не вливать, не пушить. Деревья w15e, w15o не трогать.

ПАМЯТЬ. Свободно ≥ 3,0 ГиБ перед расчётами и тестами, останов при < 1,5 ГиБ. По одному процессу.

ЧТО СДЕЛАТЬ
1. Воспроизвести: Ni-20Cr-0,3C масс. %, 700 °C, вкладка «Упругие свойства», подготовка. Снять
   полный traceback. Установить причину по исходнику: та ли это ошибка pycalphad про
   BCC_B2/BCC_A2 с межузельным углеродом (is_order_disorder_model_error) или другая. Если другая —
   СТОП, доложить с traceback.
2. Аудит: перечислить все вызовы pycalphad.equilibrium в app/ и для каждого — проходит ли список
   фаз через drop_broken_order_disorder / prepare_calculation / effective_release_phases. Таблица
   «раздел | файл:строка | детектор пары | исключения release | быстрый набор» в отчёт. Это ответ
   на вопрос, есть ли ещё разделы того же класса.
3. Починить упругость тем же механизмом, что плотность в 11N-2: список фаз подготовки проводится
   через тот же детектор, второго механизма не заводить; снятая фаза называется пользователю той же
   строкой «Фазы, несовместимые с составом, исключены: …» (в warnings подготовки, после отметок
   поправок). Если аудит п. 2 нашёл другие разделы мимо детектора — починить и их тем же путём,
   каждый назвать в отчёте; если правка какого-то раздела тянет переподпись закреплённых хешей —
   СТОП по нему, остальные доделать.
4. Доказательства: (а) Ni-20Cr-0,3C, 700 °C — подготовка проходит, BCC_B2 снята с объяснением,
   VRH считается; (б) побайтово: Ni-20Cr 700 °C и Fe-15Cr-0,4C 950 °C (сверка по образцу
   results/wave15_f/scripts/p4_run.sh) совпадают с be1fe81 по всем файлам — расхождение хоть в
   байте СТОП; (в) для каждого раздела, тронутого по п. 3, — своя побайтовая сверка на составе
   без углерода против be1fe81.
5. Тесты: случай (а) в tools/test_physical_overrides_toggle.py или отдельном файле; для
   thermogar_verified_properties_test.py — подмена, где детектор снимает фазу. Прогнать пофайлово,
   без -m slow: thermogar_verified_properties_test.py, test_physical_overrides_toggle.py,
   tools/test_ui_f.py -k "test_elastic_vrh or test_single_equilibrium or test_density_single",
   плюс файлы разделов из п. 3. Красный — СТОП.
6. Коммиты в wave15-bl38. Отчёт tasks/WAVE15_CH_REPORT.md: первой строкой — итог; traceback п. 1;
   таблица п. 2; хеши п. 4; исходы п. 5 с пиками; git log --oneline be1fe81..HEAD и git status
   --short дословно. Копию отчёта — в C:\Users\gareg\Desktop\ThermoGar\tasks\. Этот промт
   сохранить как tasks/WAVE15_CH_OPUS.md.
Если посылка задания в чём-то неверна — остановиться и написать, в чём именно.
