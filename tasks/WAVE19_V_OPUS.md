Задание 19-В (BL-58, часть 1 — разметка; код не правится). Мастер ThermoGar, 23.09.2026. Машина — ноутбук Windows 10, дерево D:\Pets\ThermoGar, .venv-windows.

ЗАПРЕТЫ
- Исключить до обхода: D:\Pets\Lilith — не открывать, не обходить, исключать из любого поиска/glob/rg/dir по диску. Любой поиск — только внутри D:\Pets\ThermoGar.
- Ничего не удалять (лишнее -> D:\Pets\ThermoGar\_to_delete\19v_<что>\ + опись sha256).
- app\, tools\, databases\, packaging\, CHANGELOG.md не трогать. Приложение и расчёты не запускать.
- В main не вливать. Ветка wave19-v, пуш на GitHub — да.
- Вендору Jev отправлять только имя фазы и английское описание (открытые базы MatCalc, открытый репозиторий). Ни файлов, ни путей, ни результатов, ни ключа в логах.
- На любом СТОП: остановиться, доложить, не подгонять.
- Это задание сохранить дословно в tasks\WAVE19_V_OPUS.md — первый коммит ветки.
Файлы волны: results\wave19_v\ (в т. ч. scripts\ — без ключа), tasks\WAVE19_V_*.md, tasks\REGISTER.md (только шаг 5).

ЦЕЛЬ. В справочнике фаз 99 фаз получают заглушку «Русская расшифровка для этой специализированной фазы ещё не добавлена» при непустом английском описании (BL-58). Каждой фазе — набор ключей из закрытого списка; по ключам программа потом соберёт русское описание (часть 2, отдельное задание). Размечают двое независимо: ты и Jev. Расхождения решает мастер; свою разметку по Jev не править.

КЛЮЧИ (закрытый список; фразы дословно, утверждены владельцем 23.09.2026 или уже есть в программе):
структура:
 S_CUB Кубическая структура.
 S_TET Тетрагональная структура.
 S_ORT Ромбическая структура.
 S_MON Моноклинная структура.
 S_HEX Гексагональная структура.
 S_RHO Ромбоэдрическая структура.
 S_BCC Объёмно-центрированная кубическая (ОЦК) структура.
 S_FCC Гранецентрированная кубическая (ГЦК) структура.
 S_HCP Гексагональная плотноупакованная (ГПУ) структура.
класс:
 C_INT Интерметаллидная фаза.
 C_SIL Силицидная фаза.
 C_GAS Газовая фаза.
 C_OX Оксидная фаза.
 C_BOR Боридная фаза.
 C_SUL Сульфидная фаза.
 C_CAR Карбидная фаза.
 C_NIT Нитридная фаза.
 C_LAV Фаза Лавеса.
роль и свойства:
 R_DISP Дисперсоид.
 R_DISPU Упрочняющий дисперсоид.
 R_UPR Упрочняющая фаза.
 R_TPU Топологически плотноупакованная (ТПУ) фаза.
 R_OXR Может охрупчивать сплав.
 R_TVXR Твёрдая и хрупкая фаза.
устойчивость:
 U_EQ Равновесная фаза.
 U_MET Метастабильная фаза.
 T_HIGH Высокотемпературная модификация.
 T_LOW Низкотемпературная модификация.
служебные:
 SL_EQ Служебная фаза базы: только для расчёта равновесия.
 SL_TD Служебная фаза базы: только для расчёта термодинамических свойств.
Ограничения набора: порядок — как в списке; не больше одного S_*, одного C_*, одного из R_DISP/R_DISPU, одного из R_OXR/R_TVXR, одного из U_EQ/U_MET, одного из T_HIGH/T_LOW, одного SL_*.

ПРАВИЛА РАЗМЕТКИ (одни для тебя и для Jev):
1. Судить по тексту описания. Имя фазы — только по п. 3 и п. 4.
2. Структура — только если текст называет кристаллическую систему (cubic, simple cubic, tetragonal, orthorhombic, monoclinic, hexagonal, rhombohedral, bcc, fcc, hcp) или даёт символ Пирсона (первая буква: c -> S_CUB, t -> S_TET, o -> S_ORT, m -> S_MON, hP -> S_HEX, hR -> S_RHO). Структурный тип или минерал (halite, corundum, pyrite, perovskite, pyrochlore, spinel, quartz, tridymite, alpha-Mn, W6Fe7-type, Al9Co2-type) структуры не даёт.
3. Структура по имени — только если имя BCC_A2, FCC_A1 или HCP_A3; такие имена класса не дают.
4. Класс, по порядку проверок: GAS в имени или gas в тексте -> C_GAS; слово intermetallic в тексте -> C_INT; Laves -> C_LAV; иначе по химической формуле в тексте или в имени (имя — формула без приставок и суффиксов вида D_, _H, _L, _Z, _WY, _T1; M = металл): есть O -> C_OX; есть S -> C_SUL; есть B -> C_BOR; есть C -> C_CAR; есть N -> C_NIT; Si и ровно один металл -> C_SIL; только металлы или Si с несколькими металлами -> C_INT. Модификация одного элемента (Mn, B, S) — класса нет. Минерал или имя без формулы (SPINEL, TRID, DIGENITE, MU_PHASE, CHI_A12) — класса нет, если формулы нет и в тексте.
5. R_DISPU — «strengthening dispersoid»; R_DISP — «dispersoid» без «strengthening».
6. R_UPR — текст прямо говорит, что фаза упрочняет (hardening, strengthening), кроме «strengthening dispersoid».
7. R_TPU — текст называет саму фазу топологически плотноупакованной или говорит, что она образуется как ТПУ-структура; одно «closely related to … TCP» — нет.
8. R_OXR — «affecting brittleness», «embrittle», «influencing ductility». R_TVXR — «hard, brittle».
9. U_EQ — текст называет фазу равновесной («equilibrium … phase»); «Use for equilibrium calculation only» — это SL_EQ, не U_EQ. U_MET — «metastable».
10. T_HIGH — «high T», «high temperature», «stable as high T»; T_LOW — «low T», «low-temperature». Интервал температур числами ключа не даёт.
11. SL_EQ — «Use for equilibrium calculation only»; SL_TD — «for thermodynamic properties calculations only».
12. Ничего не подходит — пустой набор (заглушка останется). Не додумывать по знанию о фазе.

ШАГ 0. git ls-remote origin main == dd2f13dfb27fcce3e297276327033290a8a2ad70, иначе СТОП. git status --short — дословно в отчёт; изменения в отслеживаемых — СТОП. Ветка wave19-v от dd2f13d.

ШАГ 1. Список. Из results\wave19_a\posle\1v_phase_reference_{ni,al,fe}.csv (pandas, dtype=str, keep_default_na=False) — строки, где «Описание по-русски» содержит «Русская расшифровка», а «Оригинал из базы (англ.)» непустой после strip.
СВЕРИТЬ: 28/27/44, всего 99 (не сошлось — СТОП); уникальных пар (фаза, описание) 80; уникальных описаний 72; «Простыми словами» пусто у всех 99. Расхождение, кроме 99, — записать, не СТОП.
results\wave19_v\spisok_99.csv: baza, faza, opisanie_en.

ШАГ 2. Своя разметка, до Jev и без Jev, по 80 уникальным парам. results\wave19_v\razmetka_ispolnitel.csv: faza, opisanie_en, klyuchi (через пробел, порядок списка), osnovanie (для каждого ключа — цитата из текста или имени и номер правила). Отдельный коммит до шага 3.

ШАГ 3. Jev. Ключ TYPESAFE_API_KEY в окружении; нет — СТОП, ключ по диску не искать. Модель запросить jev-1.13.0; если отказ — jev-latest; поле model из ответа — в CSV. Один запрос на пару (80 запросов), состояние только {"faza": ..., "opisanie_en": ...}. Вопросы (в Choice везде есть not_stated; instructions — «судить только по полям состояния»; критерии вариантов — правила 2–12 дословно):
 struktura — Choice: S_CUB, S_TET, S_ORT, S_MON, S_HEX, S_RHO, S_BCC, S_FCC, S_HCP, not_stated
 klass — Choice: C_GAS, C_INT, C_LAV, C_OX, C_SUL, C_BOR, C_CAR, C_NIT, C_SIL, not_stated
 dispersoid — Choice: R_DISPU, R_DISP, not_stated
 uprochnenie — Noul (R_UPR при noul >= 0,5)
 tpu — Noul (R_TPU при noul >= 0,5)
 khrupkost — Choice: R_OXR, R_TVXR, not_stated
 ustojchivost — Choice: U_EQ, U_MET, not_stated
 temperatura — Choice: T_HIGH, T_LOW, not_stated
 sluzhebnaya — Choice: SL_EQ, SL_TD, not_stated
results\wave19_v\razmetka_jev.csv: faza, opisanie_en, klyuchi, по каждому вопросу — выбор и confidence (у Noul — noul), model. Токены и время — в отчёт.

ШАГ 4. Сверка. results\wave19_v\razmetka_svodka.csv: faza, opisanie_en, klyuchi_ispolnitel, klyuchi_jev, sovpalo (да/нет), tekst_ispolnitel (фразы по ключам исполнителя через пробел), pusto_ispolnitel (да/нет).
В отчёт: совпало N из 80; все расхождения списком (фаза, описание, оба набора); сколько пар и сколько из 99 строк остаются без ключей у исполнителя.

ШАГ 5. tasks\REGISTER.md.
5а. В таблицу волны 19 строка: | 19-В | `WAVE19_V_OPUS.md` | `ThermoGar` / `wave19-v` | BL-58, часть 1: разметка 99 фаз справочника закрытым списком ключей — исполнитель и Jev независимо | **сдано, мастер не смотрел.** <итог числами>. Отчёт `tasks/WAVE19_V_REPORT.md` |
5б. Строка BL-58, колонка «Состояние»: «**открыт, решение владельца.**» -> «**в работе 19-В: вариант А владельца — описания собираются из утверждённых фраз по разметке; фразы утверждены 23.09.2026.**»

ШАГ 6. Коммиты на wave19-v; git push -u origin wave19-v; git ls-remote origin wave19-v — в отчёт.
Отчёт tasks\WAVE19_V_REPORT.md:
- итог одной строкой;
- шаги 1–4 с числами;
- отступления от задания — отдельными пунктами с причиной;
- git log --oneline dd2f13d..wave19-v и git status --short — дословно.
