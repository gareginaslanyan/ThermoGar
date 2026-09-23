# Отчёт 19-В (BL-58, часть 1 — разметка)

Исполнитель: Claude Opus 5.5, 23.09.2026. Дерево `D:\Pets\ThermoGar`, ветка `wave19-v` от `dd2f13d`. Код не правился, приложение и расчёты не запускались. `D:\Pets\Lilith` не открывался; поиск шёл только внутри `D:\Pets\ThermoGar`.

## Итог

Список сошёлся (99 строк, 80 пар, 72 описания); разметки исполнителя и Jev (`jev-1.13.0`, 80 запросов) совпали в 44 парах из 80; без ключей у исполнителя 3 пары (5 строк из 99), у Jev тоже 3 пары.

## Шаг 0

- `git ls-remote origin main`: `dd2f13dfb27fcce3e297276327033290a8a2ad70	refs/heads/main` — совпало.
- Ветка `wave19-v` создана от `dd2f13dfb27fcce3e297276327033290a8a2ad70`.
- `git status --short` до начала работы — изменений в отслеживаемых файлах нет, только неотслеживаемые:

```
?? "Claude outputs/"
?? PEREDACHA_MASTERA.md
?? PRAVILA_VZAIMODEYSTVIYA_VLADELEC_MASTER.md
?? _to_delete/
?? results/wave17_b/
?? results/wave18_a/p4/log_density_base_fecrc_off.txt
?? results/wave18_a/p4/log_density_base_fecrc_on.txt
?? results/wave18_a/p4/log_density_base_nialcr_off.txt
?? results/wave18_a/p4/log_density_base_nialcr_on.txt
?? results/wave18_a/p4/log_density_base_nicr_off.txt
?? results/wave18_a/p4/log_density_base_nicr_on.txt
?? results/wave18_a/p4/log_density_head_fecrc_off.txt
?? results/wave18_a/p4/log_density_head_fecrc_on.txt
?? results/wave18_a/p4/log_density_head_nialcr_off.txt
?? results/wave18_a/p4/log_density_head_nialcr_on.txt
?? results/wave18_a/p4/log_density_head_nicr_off.txt
?? results/wave18_a/p4/log_density_head_nicr_on.txt
?? results/wave18_a/p4/log_elastic_base_fecrc_off.txt
?? results/wave18_a/p4/log_elastic_base_fecrc_on.txt
?? results/wave18_a/p4/log_elastic_base_nialcr_off.txt
?? results/wave18_a/p4/log_elastic_base_nialcr_on.txt
?? results/wave18_a/p4/log_elastic_base_nicr_off.txt
?? results/wave18_a/p4/log_elastic_base_nicr_on.txt
?? results/wave18_a/p4/log_elastic_head_fecrc_off.txt
?? results/wave18_a/p4/log_elastic_head_fecrc_on.txt
?? results/wave18_a/p4/log_elastic_head_nialcr_off.txt
?? results/wave18_a/p4/log_elastic_head_nialcr_on.txt
?? results/wave18_a/p4/log_elastic_head_nicr_off.txt
?? results/wave18_a/p4/log_elastic_head_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_off_r2.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_density_ctrl_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_density_head_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_density_head_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nicr_on.txt
?? tasks/WAVE17_A_REPORT.md
?? tasks/WAVE17_B_REPORT.md
?? tasks/WAVE17_V_REPORT.md
?? tasks/WAVE17_ZH_OPUS.md
?? tasks/WAVE17_ZH_REPORT.md
```

## Шаг 1. Список

Скрипт `results/wave19_v/scripts/shag1_spisok.py` (pandas, `dtype=str`, `keep_default_na=False`). Отбор: «Описание по-русски» содержит «Русская расшифровка» и «Оригинал из базы (англ.)» непустой после `strip`.

| Проверка | Ожидание | Факт |
|---|---|---|
| Ni / Al / Fe | 28 / 27 / 44 | 28 / 27 / 44 (из 99 / 195 / 132 строк справочника) |
| Всего | 99 | 99 |
| Уникальных пар (фаза, описание) | 80 | 80 |
| Уникальных описаний | 72 | 72 |
| «Простыми словами» пусто | у всех 99 | у всех 99 |

Расхождений нет. Результат — `results/wave19_v/spisok_99.csv` (`baza, faza, opisanie_en`).

## Шаг 2. Разметка исполнителя

Сделана до Jev и без Jev, закоммичена отдельно (`85c5810`) до первого запроса к Jev. Файл `results/wave19_v/razmetka_ispolnitel.csv` (`faza, opisanie_en, klyuchi, osnovanie`). Разметка ручная; скрипт `shag2_razmetka_ispolnitel.py` записывает её и проверяет закрытый список, порядок ключей и ограничения набора (все 80 наборов проходят).

- С ключами — 77 пар, без ключей — 3 пары: CHI_A12, TRID, SPINEL.
- В колонке `osnovanie` для каждого ключа — цитата и номер правила. Отдельно, после «прочее:», записаны места, где текст мог навести на ключ, а ключ не поставлен.

Спорные места правил. Решения приняты по правилам, но мастеру стоит их проверить:

1. **SITI** «oP8 Pnma FeB» и **SITI3** «tP30 P42_n PTi3». FeB и PTi3 здесь — прототип структурного типа после символа Пирсона и пространственной группы, а не формула фазы. Класс взят из имени (TiSi, Ti3Si): C_SIL. При буквальном чтении п. 4 «формула в тексте» SITI получила бы C_BOR.
2. **AL8FEMNSI2**. «cubic» в тексте относится к другой фазе («cubic alpha-phase ALCRFEMNSI_A»), поэтому S_CUB не поставлен.
3. **SIO2** «Low Quartz». «Low» — не «low T» и не «low-temperature», поэтому T_LOW не поставлен (п. 10, п. 12).
4. **SPINEL** «Fe-Cr-Spinel». «Fe-Cr» — обозначение системы, а не формула фазы, поэтому класса нет.
5. Приставки и суффиксы вне примеров п. 4 я снял по аналогии с «вида D_, _H …»: `_C`, `_M`, `_T`, `_A`, `_D`, `_ZP`, `_EPL`, `_ETH`, `_ETL`, `_G`, `_TAU`, `PI_`, `O_`. Важный случай — **O_MN2B**: без снятия `O_` получился бы C_OX, со снятием — C_BOR (Mn2B).
6. **CHI_A12**. «interstitials (carbon)» — слово, а не формула, поэтому класса нет.

## Шаг 3. Jev

- Ключ `TYPESAFE_API_KEY` есть в окружении. Скрипт его не печатает и не пишет; проверка всех файлов `results/wave19_v/` на вхождение ключа — 0 файлов.
- `POST https://api.typesafe.ai/v1/systemone`. Запрошена `jev-1.13.0`, отказа не было. Поле `model` во всех 80 ответах — `jev-1.13.0`.
- 80 запросов, один на пару, последовательно, без повторов. Состояние — только `{"faza": …, "opisanie_en": …}`. 9 вопросов по заданию: 7 Choice (везде есть `not_stated`) и 2 Noul (R_UPR и R_TPU при `noul >= 0,5`).
- Токены: 732 177 входных, 38 120 выходных. Время всего прогона — 58,3 с, включая первый запрос, по которому выбиралась модель.
- Результат — `results/wave19_v/razmetka_jev.csv`: выбор и `confidence` по каждому Choice, `noul` по каждому Noul, поле `model`. Сырые ответы лежат в `results/wave19_v/jev_otvety.jsonl`.
- Без ключей у Jev — 3 пары: CRB («relevance in bracing filler alloy»), TRID, SPINEL.
- Уверенность Jev, минимум / медиана: struktura 0,38 / 0,97; klass 0,21 / 0,69; dispersoid 0,28 / 0,94; khrupkost 0,61 / 0,97; ustojchivost 0,37 / 0,97; temperatura 0,21 / 0,93; sluzhebnaya 0,41 / 0,95.
- Ровно на пороге 0,50 два значения: `uprochnenie` у MU_PHASE_I (R_UPR поставлен) и `tpu` у R_PHASE из Fe (R_TPU поставлен). Оба совпадают с разметкой исполнителя.

## Шаг 4. Сверка

Файл `results/wave19_v/razmetka_svodka.csv`. **Совпало 44 из 80.** Без ключей у исполнителя остаются **3 пары, то есть 5 строк из 99**: ni:CHI_A12, ni:TRID, fe:CHI_A12, fe:SPINEL, fe:TRID.

Все 36 расхождений (фаза | описание | исполнитель | Jev):

| Фаза | Описание | Исполнитель | Jev |
|---|---|---|---|
| BETA_MN | Simple cubic Manganese modification between 1000 K and 1370 K. | S_CUB | S_CUB T_HIGH |
| CHI_A12 | Alpha-Mn structure closely related to topologically close-packed sigma, Mu, and R-Phase. Unit cell contains 58 atoms plus interstitials (carbon). | — | C_CAR |
| CR2B | Orthorhombic. | S_ORT C_BOR | S_ORT |
| CR3MN5 | Also called "alpha prime Phase" | C_INT | C_NIT |
| CRB | relevance in bracing filler alloy | C_BOR | — |
| HF1O2_C | cubic | S_CUB C_OX | S_CUB C_OX T_HIGH |
| HF1O2_T | tetragonal | S_TET C_OX | S_TET C_OX T_HIGH |
| P_PHASE | closely related to Sigma. Can form as topologically close-packed structure in superalloys; affecting brittleness. | R_TPU R_OXR | C_INT R_TPU R_OXR |
| R_PHASE | closely related to Sigma and Mu-phase. Can form as topologically close-packed structure in superalloys; affecting brittleness. | R_TPU R_OXR | C_INT R_TPU R_OXR |
| SIO2 | Low Quartz | C_OX | C_OX T_LOW |
| AL3TI_H | Tetragonal high temperature modification with space group I4/mmm. | S_TET C_INT T_HIGH | S_TET T_HIGH |
| AL3TI_L | Tetragonal low-temperature modification, space group I4/mmm. | S_TET C_INT T_LOW | S_TET T_LOW |
| ALCU_EPL | epsilon prime phase low T | C_INT T_LOW | T_LOW |
| ALCU_ETL | eta prime phase low T | C_INT T_LOW | T_LOW |
| ALFENI_T1 | Ternary compound Al9FeNi. Al9Co2-type monoclinic structure with 22 atoms per form,ula unit. Contributes to hardening, reported for alloy 2618, with a high thermal stability of particles up to 600C. [REF:C19,C20,C21] | S_MON C_INT R_UPR | S_MON C_INT R_DISPU R_UPR T_HIGH |
| ALFESI_T5 | hexagonal alpha-AlFeSi end-member | S_HEX C_INT | S_HEX C_SIL |
| ALFESI_T6 | Monoclinic AlFeSi-Beta phase, roughly given as Al5FeSi. Important dispersoid in Fe-containing Al-alloys | S_MON C_INT R_DISP | S_MON C_SIL R_DISP |
| BCC_A2 | relevant in Al-Cu | S_BCC | C_INT |
| SI2TI | oF24 Fddd TiSi2 | S_ORT C_SIL | S_TET C_SIL |
| SITI | oP8 Pnma FeB | S_ORT C_SIL | S_ORT C_BOR |
| SITI3 | tP30 P42_n PTi3 | S_TET C_SIL | S_TET C_NIT |
| TIALSI_TAU | orthorhombic. | S_ORT C_INT | S_ORT |
| BETA_MN | Simple cubic Manganese modification between around 1000 K and 1370 K. | S_CUB | S_CUB T_HIGH |
| CR3MN5 | Also named "alpha Phase" | C_INT | C_NIT |
| CRB | Orthorhombic, space group Cmcm. | S_ORT C_BOR | S_ORT |
| FEB | Orthorhombic, space group Pnma. | S_ORT C_BOR | S_ORT |
| MNB2 | Hexagonal, space group P6/mmm. | S_HEX C_BOR | S_HEX |
| MNNI | cubic | S_CUB C_INT | S_CUB |
| MO2M1B2 | tetragonal, space group P4/mbm | S_TET C_BOR | S_TET C_OX |
| O_MN2B | Orthorhombic. | S_ORT C_BOR | S_ORT C_OX |
| PD2MN | orthorhombic | S_ORT C_INT | S_ORT |
| PD5MN3 | orthorhombic | S_ORT C_INT | S_ORT |
| TI3B4 | Orthorhombic, space group Immm. | S_ORT C_BOR | S_ORT |
| TIB | Orthorhombic, space group Pnma. | S_ORT C_BOR | S_ORT |
| WC | simple hexagonal | S_HEX C_CAR | S_HEX |
| YALO3 | strengthening dispersoid, perovskite structure | C_OX R_DISPU | R_DISPU |

Группировка для мастера. Это счёт, а не правка: своя разметка по Jev не менялась.

- **17 пар.** Jev не дал класс, который исполнитель взял из формулы в имени: CR2B, CRB (оба описания), AL3TI_H, AL3TI_L, ALCU_EPL, ALCU_ETL, TIALSI_TAU, FEB, MNB2, MNNI, PD2MN, PD5MN3, TI3B4, TIB, WC, YALO3.
- **12 пар.** Классы различаются:
  - CR3MN5 ×2 — у Jev C_NIT;
  - MO2M1B2 и O_MN2B — у Jev C_OX;
  - SITI — у Jev C_BOR по прототипу FeB;
  - SITI3 — у Jev C_NIT по прототипу PTi3;
  - ALFESI_T5 и ALFESI_T6 — у Jev C_SIL при двух металлах Al и Fe;
  - CHI_A12 — у Jev C_CAR по слову «carbon»;
  - P_PHASE и R_PHASE (Ni) — у Jev C_INT при имени без формулы;
  - BCC_A2 — у Jev C_INT вместо S_BCC по п. 3.
- **6 пар.** Температура или роль, которых нет в тексте по п. 5 и п. 10:
  - BETA_MN ×2 — T_HIGH по интервалу в кельвинах;
  - HF1O2_C и HF1O2_T — T_HIGH, в тексте только «cubic» / «tetragonal»;
  - SIO2 — T_LOW по «Low Quartz»;
  - ALFENI_T1 — T_HIGH и R_DISPU.
- **1 пара.** Структура: SI2TI «oF24» — у исполнителя S_ORT по первой букве «o», у Jev S_TET.

## Шаг 5. REGISTER

- 5а: в таблицу волны 19 добавлена строка 19-В с итогом числами.
- 5б: в строке BL-58 колонка «Состояние» заменена по заданию. Остальной текст колонки не менялся.

## Шаг 6. Git

Итоговые `git log`, `git ls-remote origin wave19-v` и `git status --short` приведены в конце отчёта.

## Отступления от задания

1. **Файл задания.** `tasks/WAVE19_V_OPUS.md` сохранён дословно, начиная со строки «Задание 19-В …». Стоявшая перед ней строка `/caveman ultra` — команда режима ответа исполнителю, а не текст задания, поэтому в файл не вошла.
2. **Форма вопросов Jev.** Задание не задаёт форму полностью, поэтому решения такие:
   - `instructions` каждого вопроса — «Судить только по полям состояния.»;
   - критерий каждого варианта — объект `{ключ, фраза, правила}`: фраза ключа дословно из закрытого списка и правила дословно;
   - struktura получает п. 2 и п. 3, klass — п. 4, dispersoid — п. 5, uprochnenie — п. 6, tpu — п. 7, khrupkost — п. 8, ustojchivost — п. 9, temperatura — п. 10, sluzhebnaya — п. 11;
   - `not_stated` и ответ `false` у Noul — п. 12;
   - п. 1 не отправлялся: задание называет только п. 2–12;
   - вопросы целиком — в `results/wave19_v/scripts/shag3_jev.py`.
3. **Сырые ответы Jev.** Они сохранены в `results/wave19_v/jev_otvety.jsonl` (состояние и ответ, без ключа). Задание этого не требовало; файл нужен, чтобы сверку можно было проверить без повторного запроса.
4. **Побочный `__pycache__`.** Импорт `shag3_jev` из `shag4_svodka` создал `results/wave19_v/scripts/__pycache__`. Папка перенесена в `_to_delete/19v_pycache/`, опись sha256 — `_to_delete/19v_pycache/opis_sha256.txt`. Ничего не удалено.
5. **Кодировка.** CSV волны записаны в UTF-8 без BOM, как исходные CSV 19-А.
6. **Время Jev.** 58,3 с — стеночное время всего прогона одним процессом, включая первый запрос. Время отдельных запросов не замерялось.
7. **Git в отчёте.** `git log` и `git status` ниже сняты перед коммитом отчёта. Сам коммит отчёта в этот `git log` не входит: он идёт следом, его хеш есть в `git ls-remote` после пуша.

## git log --oneline dd2f13d..wave19-v (перед коммитом отчёта)

```
7db5df9 docs(register): add 19-V row, move BL-58 to in progress
a900fcc results(wave19-v): Jev key markup (jev-1.13.0, 80 requests) and comparison
85c5810 results(wave19-v): phase list (99) and executor key markup (80 pairs)
863b526 docs(tasks): add wave 19-V task (BL-58 part 1, phase key markup)
```

## git status --short (перед коммитом отчёта)

Совпадает со списком шага 0 построчно: изменений в отслеживаемых файлах нет, новых неотслеживаемых путей нет. Новый `_to_delete/19v_pycache/` лежит внутри уже неотслеживаемого `_to_delete/`.

```
?? "Claude outputs/"
?? PEREDACHA_MASTERA.md
?? PRAVILA_VZAIMODEYSTVIYA_VLADELEC_MASTER.md
?? _to_delete/
?? results/wave17_b/
?? results/wave18_a/p4/log_density_base_fecrc_off.txt
?? results/wave18_a/p4/log_density_base_fecrc_on.txt
?? results/wave18_a/p4/log_density_base_nialcr_off.txt
?? results/wave18_a/p4/log_density_base_nialcr_on.txt
?? results/wave18_a/p4/log_density_base_nicr_off.txt
?? results/wave18_a/p4/log_density_base_nicr_on.txt
?? results/wave18_a/p4/log_density_head_fecrc_off.txt
?? results/wave18_a/p4/log_density_head_fecrc_on.txt
?? results/wave18_a/p4/log_density_head_nialcr_off.txt
?? results/wave18_a/p4/log_density_head_nialcr_on.txt
?? results/wave18_a/p4/log_density_head_nicr_off.txt
?? results/wave18_a/p4/log_density_head_nicr_on.txt
?? results/wave18_a/p4/log_elastic_base_fecrc_off.txt
?? results/wave18_a/p4/log_elastic_base_fecrc_on.txt
?? results/wave18_a/p4/log_elastic_base_nialcr_off.txt
?? results/wave18_a/p4/log_elastic_base_nialcr_on.txt
?? results/wave18_a/p4/log_elastic_base_nicr_off.txt
?? results/wave18_a/p4/log_elastic_base_nicr_on.txt
?? results/wave18_a/p4/log_elastic_head_fecrc_off.txt
?? results/wave18_a/p4/log_elastic_head_fecrc_on.txt
?? results/wave18_a/p4/log_elastic_head_nialcr_off.txt
?? results/wave18_a/p4/log_elastic_head_nialcr_on.txt
?? results/wave18_a/p4/log_elastic_head_nicr_off.txt
?? results/wave18_a/p4/log_elastic_head_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_off_r2.txt
?? results/wave18_a/p4_pervyj/log_density_base_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_density_ctrl_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_density_head_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_density_head_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_density_head_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_base_nicr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_fecrc_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_fecrc_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nialcr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nialcr_on.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nicr_off.txt
?? results/wave18_a/p4_pervyj/log_elastic_head_nicr_on.txt
?? tasks/WAVE17_A_REPORT.md
?? tasks/WAVE17_B_REPORT.md
?? tasks/WAVE17_V_REPORT.md
?? tasks/WAVE17_ZH_OPUS.md
?? tasks/WAVE17_ZH_REPORT.md
```

## git ls-remote origin wave19-v

Снято после `git push -u origin wave19-v` четырёх коммитов выше, до коммита отчёта:

```
7db5df9789cb8b034437aeebf7877a0524a980c5	refs/heads/wave19-v
```

Коммит отчёта пушится следом отдельным `git push`. После него `origin/wave19-v` указывает на коммит отчёта, родитель которого — `7db5df9`.
