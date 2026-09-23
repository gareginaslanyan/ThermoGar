# Отчёт 19-Д — выпуск 0.4.4

**Итог: выпуск 0.4.4 сделан, приёмка на установленной программе пройдена по всем шести пунктам (а)–(е). Регрессия — 57 заданий, 0 красных. Эталон — 57 из 57 `PASS`. Слияние `cd9da3b`, тег `v0.4.4`, пуш подтверждён. Установщик — sha256 `C9B33FB3…5590`, установлен поверх 0.4.3 с 0 расхождений.**

Ничего не удалено: чужой байткод и мои лишние файлы перенесены в `_to_delete/19d_*` с описью sha256. Байты баз не менялись: `git diff --stat 6e535ff main -- databases` пуст. В `D:\Pets\Lilith` сессия не заходила и в поиск его не включала. Поиск шёл только в `D:\Pets\ThermoGar`, `D:\Pets\_archive`, `C:\Program Files\ThermoGar` и `C:\Program Files (x86)\NSIS`. Все pytest шли с `-B` и окружением `MPLBACKEND=Agg`, `PYTHONHASHSEED=0`, `THERMOGAR_STATE_ROOT=results\validation\wave19_d_state`.

## Замер времени

Время по часам ноутбука, 2026-09-23.

| этап | начало | конец | длительность |
|---|---|---|---|
| шаг 0: проверки, ветка, задание | 11:42:39 | 11:43 | 1 мин |
| шаги 1–4, 6а–6в: версия, NOTICES, CHANGELOG, LIMITS, BL-59, реестр | 11:43 | 11:56 | 13 мин |
| шаг 5: регрессия (`results/wave19_d/regress_time.txt`) | 11:56:29 | 14:05:46 | 129,3 мин |
| шаг 5: сверка эталона, коммит | 14:05:53 | 14:06:50 | 1 мин |
| шаг 7: слияние, тег, пуш | 14:06:55 | 14:07:13 | 18 с |
| шаг 8: снимок, сборка | 14:07:15 | 14:14:46 | 7,5 мин (сборка 430,8 с) |
| шаг 9: установка | 14:15:49 | 14:16:20 | 31 с |
| шаг 9: проверка установки, приёмка (а)–(е) | 14:16:30 | 14:22:34 | 6,1 мин |
| шаг 10: реестр, отчёт, коммит, пуш | 14:22:40 | 14:26 | 3,5 мин |

* Прогноз в 13:15: пройдено 44 задания из 57, темп 1,28 от 18-Г. Ожидался конец регрессии около 14:13, всего выпуска — около 14:50.
* Факт: регрессия кончилась в 14:05:46, выпуск — в 14:26, 2 ч 43 мин от начала (11:42:39).
* Регрессия шла на 23 % дольше, чем в 18-Г (129,3 против 105,4 мин). Темп ровный по всем заданиям, красных и снятий по памяти нет. Вероятная причина — фоновая нагрузка ноутбука. Это не проверялось.

## 0. Исходное состояние

* `git ls-remote origin main` — `6e535ffc7466d05323cd73613772eb1b96f027ce refs/heads/main`, совпадает с заданием.
* Свободная память — 7 369 196 КБ (7,03 ГиБ) из 16 470 588 КБ.
* `$env:CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP` = `1`.
* `app\__pycache__` не было, переносить нечего. Про `tools\__pycache__` — п. 5.
* Ветка `wave19-d` создана от `6e535ff`. Первый коммит — `c830602`, задание в `tasks/WAVE19_D_OPUS.md`.

`git status --short` (изменений в отслеживаемых файлах нет), дословно:

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

## 1. Версия 0.4.4

Коммиты `236f3d1` (версия) и `c55c7bf` (NOTICES).

* Первыми подняты `app/thermogar_release_policy.py` (`APP_VERSION` = `APP_STAGE` = "0.4.4") и `packaging/product-version.json` (0.4.4 / 0.4.4.0).
* `tools/test_version_consistency.py`, красный прогон: `10 failed, 81 passed`. Вывод — `results/wave19_d/version_test_red.txt`. Места по тесту:
  * заголовки `QUICK_START_THERMOGAR.md`, `README.md` (и имя установщика в строке 101), `USER_GUIDE_THERMOGAR.md`, `docs/FEATURES.md`, `docs/guide/README.md` (и имя HTML в строке 23);
  * подпись боковой панели `app/ThermoGar_app.py:6832`;
  * `tools/make_guide_screens.py`: `HTML_NAME`, `HTML_TITLE`;
  * `docs/guide/ThermoGar_Guide_0.4.4.html`. Пересобран `make_guide_screens.py --html`, без новых снимков. От HTML 0.4.3 отличается только версией: три вхождения, одно из них — якорь заголовка `thermogar-044-…`.
  * `test_payload_list_is_complete`: `assert 76 == 75`. Это не место версии, разбор — «Отступления», п. 2.
* Зелёный прогон: `91 passed`. Вывод — `results/wave19_d/version_test_green.txt`.
* `HANDOFF.md`: заголовок 0.4.4 и «**Выпущено:** 0.4.4 от 2026-09-23; предыдущий выпуск 0.4.3 от 2026-09-19.»
* `THIRD_PARTY_NOTICES.txt` перевыпущен скриптом `packaging/generate_notices.ps1` с runtime из п. 8 (99 пакетов). Результат совпал с ожиданием:
  * `git diff` — одна строка: `Generated: 2026-09-19` → `Generated: 2026-09-23`;
  * `git hash-object` рабочей копии равен блобу HEAD с заменённой строкой;
  * байты рабочей копии отличаются от блоба ещё и CRLF — это `core.autocrlf`, в хранимые байты он не попадает.

## 2–3. CHANGELOG и LIMITS

Коммит `8f0ca62`.

* `CHANGELOG.md`: раздел «## 0.4.4 — 2026-09-23» сверху, текст мастера дословно. Пункты не перенесены по ширине, как в тексте мастера.
* `docs/LIMITS_OF_APPLICABILITY.md`: абзац мастера добавлен дословно в конец раздела «Плотность фазы без своей модели: правило смеси», перед `---`.
* Ссылки текста реестра на строки базы сверены: `physical_data_v103.pdb:114` — `D0_DELTA … 8827.0 … 0.25*(3*D0FCC_NI + D0BCC_NB)`, `:361` — `DP(LAVES_PHASE,FE:NB) … 0.66*D0BCC_FE+0.34*D0BCC_NB`, `:422-423` — `DP(M23C6,FE:CR:C) … 0.69*D0BCC_FE+0.1*D0BCC_CR+0.21*D0DIAM_C`.

## 4. BL-59

Коммит `75fa84f`. Файлы — `results/wave19_d/csv_*.txt`.

* В `.gitattributes` добавлена строка `*.csv -text`. В коммите ровно одна вставка, прежние байты файла сохранены.
* `git status --short -- "*.csv"` сразу после правки — **пусто** (`csv_status_literal.txt`). Пусто и после `git update-index --really-refresh`.
* Пустой статус — эффект stat-кэша индекса: git не перехэширует файл, у которого не менялись размер и время. Сверка по сути (`csv_check.txt`) — `git hash-object` каждого CSV с новыми атрибутами против блоба:
  * CSV в индексе — 1285;
  * отличаются от блоба — 1033, все `i/lf w/crlf`;
  * после CRLF → LF равны блобу — **1033**, отличаются не только CR — **0**. СТОПа нет.
* Восстановление:
  * `.gitattributes` внесён в индекс: checkout берёт атрибуты из индекса;
  * времена 1033 файлов обновлены (`os.utime`, содержимое не менялось). После этого `git status` показал 1033 × ` M` (`csv_status_after_touch.txt`);
  * перед восстановлением повторно сверено с HEAD: 1033 файла, отличий кроме CR — 0;
  * `git checkout --pathspec-from-file` по списку `csv_restore_list.txt`.
* Итог (`csv_restore_result.txt`):
  * **восстановлено 1033 файла**, все побайтно равны блобам HEAD;
  * `git status --short -- "*.csv"` пуст;
  * `ls-files --eol`: `i/crlf w/crlf` — 123, `i/lf w/lf` — 1162;
  * хранимые байты CSV не менялись: в коммите нет ни одного CSV.

## 5. Регрессия и сверка эталона

**Раннер** — `results/wave19_d/run_regress.py`, копия `results/wave18_g/run_regress.py`. Отличий два: шапка и `THERMOGAR_STATE_ROOT` = `results/validation/wave19_d_state`. Логи — в `results/wave19_d/`. Список файлов раннер собирает глобом `tools/test_*.py` и `tools/thermogar_*_test.py`. Поэтому `test_phase_description_order_words.py` и `test_phase_description_stub_keys.py` вошли в список без правки. Медленных тестов в них нет, список `SLOW_FILES` полон.

**Задания: 57** — 54 из 18-Г и три новых файла:

| файл | откуда | итог |
|---|---|---|
| `test_phase_description_order_words.py` | 19-А | `11 passed` |
| `test_phase_description_stub_keys.py` | 19-В2 | `9 passed` |
| `test_version_consistency.py` | 18-Г2, после 18-Г | `91 passed` |

Задание ждало 54 + 2 = 56. Разница — третий файл, см. «Отступления», п. 8.

* Итоги: выход 0 — 48, выход 5 (`no tests ran` / `deselected`, тот же состав, что в 18-Г) — 9, выход 1 — 0. Снятий по памяти нет.
* `slow__test_ui_f.py` шёл одним процессом: свободно 7,61 ГиБ ≥ 6,0. Итог — `21 passed, 38 deselected in 1264.81s`.
* **0 красных.** Сводка — `results/wave19_d/regress_summary.jsonl`.

**Байткод.**

* Перед регрессией в `tools\__pycache__` лежали 9 чужих `.pyc` от 18–19.09. Они перенесены в `_to_delete/19d_pycache_tools/` (опись `_opis.txt`).
* Во время регрессии в `app\__pycache__` появились 3 файла: `thermogar_parallel`, `thermogar_db_cache`, `thermogar_database_repair`. Время записи — 12:15:35–12:15:45, это внутри задания `notslow__test_parallel_engine.py` (12:15:23–12:16:52). Вероятно, их пишут дочерние процессы пула, запущенные без `-B`. Это не проверялось.
* Красных они не дали: `thermogar_paths_test` прошёл в 12:48. Файлы перенесены в `_to_delete/19d_pycache_regress/` с описью.
* Класс тот же, что в 18-А/18-Г. Отличие: байткод пишет среда теста, а не мои прогоны.

**Сверка эталона.** Сценарий `results/wave19_d/backend_compare.py` — копия из 18-Г, подписи «18-Г» заменены на «19-Д». Вывод — `backend_compare.txt`.

* Прогоны: `43 passed, 14 deselected in 493.64s` и `14 passed, 43 deselected in 879.30s`.
* **57 из 57 ячеек `PASS`**, по отношению к исходам 17-Г.
* Разница — только в трёх ячейках «[Проекты/batch] 3 состава подряд» (al, fe, ni), в полях `с/точку` и `всего, с`. Это времена, как в 18-Г. Числа прежние. СТОПа нет.

## 6. Реестр `tasks/REGISTER.md`

* До слияния, коммит `fdfd22c`:
  * 6а — начало ячейки «Состояние» BL-52 заменено текстом мастера, остальной текст сохранён;
  * 6б — BL-59 закрыт;
  * 6в — «войдёт в 0.4.4» → «в выпуске 0.4.4», **5 вхождений** (BL-55, BL-56, BL-58, строки 19-А и 19-В2).
* После приёмки, на `main`, коммитом этого отчёта: 6г — строка 19-Д в таблице волны 19; 6д — строка «**Выпуск 0.4.4 — 2026-09-23, тег `v0.4.4`.**».

## 7. Слияние, тег, пуш

```
git checkout main                      # Your branch is up to date with 'origin/main'.
git merge --ff-only origin/main        # Already up to date.
git merge --no-ff wave19-d -m "Merge wave19-d: release 0.4.4"
 135 files changed, 5812 insertions(+), 25 deletions(-)
git diff --stat 6e535ff main -- databases        # пусто
git tag -a v0.4.4 -m "ThermoGar 0.4.4 — 2026-09-23"
git push origin main --tags
   6e535ff..cd9da3b  main -> main
 * [new tag]         v0.4.4 -> v0.4.4
```

`git ls-remote origin refs/heads/main "refs/tags/v0.4.4*"`, дословно:

```
cd9da3bb060c52873bf0b1692756f2b13c3f7cf3	refs/heads/main
2dd82db27faf5d6e7e46e8a4970fa7149d7a8bc3	refs/tags/v0.4.4
cd9da3bb060c52873bf0b1692756f2b13c3f7cf3	refs/tags/v0.4.4^{}
```

## 8. Установщик

**Runtime.** Взят из `D:\Pets\_archive\ThermoGar.zip`, каталог `ThermoGar/ThermoGar-Installer-Assets/runtime-clean-3119/`. Распакован во временную папку сессии: 17 048 файлов. Архив не менялся. Сверка (`results/wave19_d/runtime_check.txt`): все 15 003 файла `runtime/` из `payload-manifest.json` установленной 0.4.3 совпали по sha256, **расхождений 0**.

**Снимок.** `git -c core.autocrlf=false archive v0.4.4` — пути нагрузки и `packaging/`, 82 файла (в 18-Г — 81; добавился `app/thermogar_phase_descriptions.py`). Все 82 равны блобам `v0.4.4` байт в байт.

**Сборка.**

```
packaging\build_installer.ps1 -RepoRoot <снимок> -RuntimeSource <runtime> -OutputDir D:\Pets\ThermoGar\dist\release-0.4.4
  project files staged: 77
  staged 15079 files, 554,3 MB
BUILD OK  D:\Pets\ThermoGar\dist\release-0.4.4\ThermoGar-0.4.4-win64.exe
  installer: 113,0 MB
  sha256   : C9B33FB3E2785933AA8774CCAC95443D0C5FFD6A1793E7B198FE65A50BDC5590
  elapsed  : 430,8 s
```

* Размер — **118 504 100 байт**. Рядом лежит `ThermoGar-0.4.4-win64.exe.sha256`, в том же формате, что у 0.4.3.
* Ресурс версии exe: `ProductVersion 0.4.4`, `FileVersion 0.4.4`, `vi_product_version` 0.4.4.0.
* NSIS — `C:\Program Files (x86)\NSIS\makensis.exe` (v3.12). Лог — `results/wave19_d/build.log`, по `.gitignore` (`*.log`) в git не входит.
* `THIRD_PARTY_NOTICES.txt` снимка после сборки байт в байт равен тегу.

## 9. Установка и приёмка

**До установки** (`results/wave19_d/installed_043_before.txt`):

| что | sha256 |
|---|---|
| `Uninstall.exe` | `1a09a7b800cfbe40a50e215bfe917dfd66333edb48372c129d46afe67200fb2a` (как после установки 0.4.3 в 18-Г) |
| `runtime\python.exe` | `5f7b89a612c9b8af1d6456cdfcd1dbe5ca630849e79aebced9bee9a6694952ec` |
| `app\ThermoGar_app.py` | `47fda67252b12e2e226c64468fcbc3a9f73a2b1b5573e2f1bc442999ab92c1f9` = блоб `v0.4.3` |

Реестр удаления показывал `DisplayVersion 0.4.3`.

**Установка.** Команда `ThermoGar-0.4.4-win64.exe /S`, один запрос UAC, `exit 0`, 31 с. Проверка после неё (`results/wave19_d/installed_044_check.txt`):

* `DisplayVersion 0.4.4`;
* `payload-manifest.json`: 15 079 файлов, **расхождений 0**;
* 76 файлов тега в нагрузке (всё вне `runtime/`) — **байт в байт с блобами `v0.4.4`**. Файлов вне `runtime/` не из тега нет;
* `Uninstall.exe` `60ca53dc…`, `runtime\python.exe` `5f7b89a6…` (прежний), `app\ThermoGar_app.py` `12310733…` = блоб `v0.4.4`.

**Приёмка.**

* Интерпретатор — `C:\Program Files\ThermoGar\runtime\python.exe -B -X utf8`, файлы `app` — установленные.
* Окружение: `PYTHONHASHSEED=0`, `MPLBACKEND=Agg`, папка состояния временная (`tempfile`).
* Сценарий `results/wave19_d/priemka.py`: основа — `results/wave18_g/priemka.py`, загрузчик функций приложения из `results/wave19_a/scripts/app_extract.py` (корень берётся из аргумента), пакет — по `step_1g_batch` 19-А.
* Выходы — `results/wave19_d/priemka/`, лог — `priemka_log.txt`.
* Побайтовая сверка (б) и (в) с блобами `v0.4.4` — `results/wave19_d/priemka_compare.py`, вывод `priemka/compare.txt`.
* После приёмки `C:\Program Files\ThermoGar\app\__pycache__` нет.

| | проверка | ожидание | получено | итог |
|---|---|---|---|---|
| (а) | версия на экране | подпись панели и `APP_VERSION` — 0.4.4 | «ThermoGar 0.4.4 — исследовательское ПО. …», `APP_VERSION` 0.4.4 | да |
| (б) | пакет Fe–0,8C мас. %, 700 °C, 101325 Па, 4 строки через `_parse_csv` и `batch_engine_runner` | строки 1–3 побайтно = `results/wave19_a/posle/1g_batch_Fe-{пусто,метастабильный,стабильный}.csv` из git; строка 4 — «ошибка» с текстом владельца | в runner пошли 3 строки: `metastable`, `metastable`, `stable`. CSV долей равны блобам: sha256 `57dc1b94…` (пусто, метастабильный — BCC_B2 0,8578 / CEMENTITE 0,1422) и `bd7984c2…` (стабильный — BCC_B2 0,9643 / GRAPHITE 0,0357). Fe-metastabe — «ошибка», «Неизвестный режим стали: «metastabe». Используйте «стабильный» или «метастабильный».» | да |
| (в) | справочник фаз ni, al, fe (`phase_reference_dataframe`) | побайтно = `results/wave19_v2/posle/phase_reference_{ni,al,fe}.csv` из git | 99 / 195 / 132 строки; sha256 `0a711620…`, `6b849fc8…`, `5689f2e6…` — равны блобам, 3 из 3 | да |
| (г) | RS320, «Плотность», 25 °C | 2663,72 кг/м³ | **2663,72** кг/м³ (2663,716441…; 298,15 K), ошибок экрана нет | да |
| (д) | установленный `QUICK_START_THERMOGAR.md` | первое упоминание версии — 0.4.4 | первая строка «# ThermoGar 0.4.4 — быстрый старт»; первое число вида x.y.z в файле — 0.4.4 | да |
| (е) | скан температур Fe (профиль `test_ui_f`, 500–900 °C, 5 точек), с пулом и без | таблицы равны, отказа пула нет | с пулом — «Параллельный расчёт: 4 воркера.», 34,7 с; без — «Последовательный расчёт в одном процессе.», 26,2 с; 5 строк, ячейки (`float.hex`) и CSV равны: `108e8b97…` и `10811ed8…` у обоих, как в 18-Г | да |

## Отступления и замечания

1. **Файл задания без первой строки.** В `tasks/WAVE19_D_OPUS.md` задание сохранено дословно, от «Задание 19-Д…» до конца. Строка `/caveman ultra` перед ним — команда сессии, а не текст задания.
2. **Правка теста, не кода приложения.** В `tools/test_version_consistency.py` проверка `assert len(payload) == 75` заменена на `== 76`.
   * Тест был красным уже на `6e535ff`, без моих правок: это проверено через `git stash`.
   * Причина: 19-В2 добавила модуль `app/thermogar_phase_descriptions.py`. `stage_payload.ps1` берёт `app/*.py`, поэтому модуль входит в нагрузку. Это подтверждают «project files staged: 77» и 76 файлов тега в установке.
   * Строка в шапке теста «75 файлов, их сверял 18-Г» оставлена: она описывает 18-Г.
3. **`packaging/build_installer.ps1` не менялся.** В примере шапки осталось `-Version 0.4.3`. Задание велит искать места версии по тесту, а этот файл тест не проверяет. В 18-Г пример поднимали.
4. **BL-59: статус и восстановление.**
   * Буквальный `git status -- "*.csv"` был пуст, но 1033 рабочих копии отличались от блобов CRLF (stat-кэш, п. 4). Поэтому сверка шла через `git hash-object`.
   * `git checkout --` и `git checkout-index -f` пропускают файл с неизменным stat. Две первые попытки ничего не переписали: одна на одном файле, вторая на списке до внесения `.gitattributes` в индекс.
   * Байты при этом не менялись. Сработало после обновления времён файлов.
5. **Моя ошибка: 1033 пустых файла.** Список для `touch` был записан с CRLF, и `touch` создал 1033 пустых файла с именами `…csv` + U+F00D (так Git Bash передаёт CR).
   * Все 1033 пустые. Они перенесены в `_to_delete/19d_touch_stray/`, опись с sha256 — в `_opis.txt`. В дереве их нет.
   * Настоящие CSV эта ошибка не задела: их времена потом обновлены через `os.utime` по тому же списку, прочитанному правильно.
6. **`.gitattributes`: первая правка через `sed` сняла CR** с последней строки блоба (`*.pdb -text\r\n`). Файл переписан как байты блоба плюс строка `*.csv -text\n`. В коммите одна вставка.
7. **Два локальных коммита пересобраны.** `.gitattributes` уже лежал в индексе и попал в коммит CHANGELOG. Коммиты `b227374` и `22a8e94` пересобраны через `git reset --soft c55c7bf` в `8f0ca62` и `75fa84f`. Ветка тогда не была запушена. Ветка `wave19-d` не пушилась и сейчас: задание пушит `main` и теги.
8. **Заданий 57, а не 56.** Кроме новых файлов 19-А и 19-В2 после 18-Г добавился `test_version_consistency.py` (18-Г2). Раннер берёт его глобом.
9. **Байткод вне перечня задания** (п. 5). Задание называет только `app\__pycache__`. Дополнительно перенесены `tools\__pycache__` (9 файлов, до регрессии) и 3 файла `app\__pycache__`, появившиеся во время регрессии. Два опустевших каталога `__pycache__` сняты `rmdir`: в них не осталось ни одного файла.
10. **Мой временный файл.** При проверке кодировки я создал `app\thermogar_release_policy.py.tmp` и сразу удалил его. Это копия файла, записанная этой же командой; в git он не попадал.
11. **Runtime распакован через Python `zipfile`.** `unzip` из Git Bash извлёк из архива (3,2 ГБ, zip64) только 35 файлов. Эта неполная распаковка в папке сессии выброшена.
12. **Пул — 4 воркера, в 18-Г было 6.** Число воркеров зависит от состояния машины в момент расчёта. Отказа нет, таблицы равны.
13. **Заголовок раздела «Волна 19»** в реестре не менялся: задание этого не требует. В 18-Г там писали «Влита в `main` задачей …».
14. **Смоук `packaging/smoke_installed.ps1` не гонялся**: задание его не требует. Программа оставлена установленной.

## Git

`git log --oneline 6e535ff..main` перед коммитом этого отчёта, дословно:

```
cd9da3b Merge wave19-d: release 0.4.4
9cce4bf test(19-Д): регрессия 0.4.4 (57 заданий, 0 красных), сверка бэкенда с эталоном (57 из 57 PASS), скрипты приёмки
fdfd22c docs(19-Д): реестр до слияния — BL-52 закрыт как не дефект, BL-59 закрыт, «в выпуске 0.4.4»
75fa84f fix(19-Д): *.csv -text в .gitattributes (BL-59); хранимые байты CSV не менялись
8f0ca62 release(19-Д): CHANGELOG 0.4.4; LIMITS — эталонные структуры как соглашение физической базы (BL-52)
c55c7bf release(19-Д): перевыпуск THIRD_PARTY_NOTICES для 0.4.4
236f3d1 release(19-Д): версия 0.4.4 по тесту согласованности версии; HTML руководства 0.4.4; HANDOFF
c830602 docs(19-Д): задание 19-Д — выпуск 0.4.4
```

Следом на `main` идёт коммит `docs(19-Д)` с этим отчётом, реестром (6г–6д) и результатами приёмки. Тег остаётся на `cd9da3b`.

`git status --short` перед коммитом этого отчёта, дословно:

```
 M tasks/REGISTER.md
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
?? results/wave19_d/installed_043_before.txt
?? results/wave19_d/installed_044_check.txt
?? results/wave19_d/priemka/
?? tasks/WAVE17_A_REPORT.md
?? tasks/WAVE17_B_REPORT.md
?? tasks/WAVE17_V_REPORT.md
?? tasks/WAVE17_ZH_OPUS.md
?? tasks/WAVE17_ZH_REPORT.md
```

Пуш коммита отчёта: `cd9da3b..7add250  main -> main`. `git ls-remote origin refs/heads/main "refs/tags/v0.4.4*"` после него, дословно:

```
7add2505850e130fb5f1ce4ea0ddc7b8e692df18	refs/heads/main
2dd82db27faf5d6e7e46e8a4970fa7149d7a8bc3	refs/tags/v0.4.4
cd9da3bb060c52873bf0b1692756f2b13c3f7cf3	refs/tags/v0.4.4^{}
```

Строка `ls-remote` дописана отдельным коммитом `docs(19-Д)` следом за `7add250`.
