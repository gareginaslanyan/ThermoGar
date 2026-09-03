# ui_matrix_H — раздел «Проекты и данные» × Ni/Al/Fe

Дата прогона: 2026-09-03. Ветка `wave3h-projects-docs`, worktree
`C:\Users\gareg\Desktop\ThermoGar-w3h`.
Интерпретатор: `C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe`
(Python 3.11.9, streamlit 1.62.0, pycalphad 0.11.2, pandas 3.0.5, pytest 9.1.1).

Тесты: `tools\test_ui_h.py` — `streamlit.testing.v1.AppTest`, `default_timeout=900`,
приватный `THERMOGAR_STATE_ROOT` на каждый тест.

```bat
.venv-windows\Scripts\python.exe -X utf8 -B -m pytest tools/test_ui_h.py -q -m "not slow"
.venv-windows\Scripts\python.exe -X utf8 -B -m pytest tools/test_ui_h.py -q -m slow
```

Составы: Ni–15Al ат.% при 700 °C; Al–4Cu–1Mg мас.% при 500 °C;
Fe–0,2C–11,5Cr–0,7Ni мас.% при 700 °C (профиль `thermogar_patch`).

## Важно: два дефекта в чужом файле

Раздел целиком не работает из-за двух ошибок в `app\ThermoGar_app.py`
(владелец 3F). Подробности и предлагаемые правки — в `tasks\WAVE3H_REPORT.md`.
Пока они не исправлены, `tools\test_ui_h.py` запускает приложение из
патченной копии (`UPSTREAM_PATCHES` в шапке теста); после исправления копия
перестаёт создаваться сама собой. **Матрица ниже описывает поведение с этими
двумя правками.** Без них колонки «загрузить», «экспорт» и «импорт» — FAIL.

## Матрица

| Действие | Ni | Al | Fe | Тест |
|---|---|---|---|---|
| Библиотека: сохранить текущий состав | OK | OK | OK | `test_library_save_appears_in_the_list_and_loads_back` |
| Библиотека: запись появилась в списке | OK | OK | OK | там же |
| Библиотека: загрузить обратно в сайдбар | OK | OK | OK | там же |
| Библиотека: экспорт JSON | OK | OK | OK | `test_library_export_and_import_round_trip` |
| Библиотека: импорт JSON | OK | OK | OK | там же |
| Библиотека: удаление записи | OK | OK | OK | ручная проверка |
| Проект: сохранить (14 ключей) | OK | OK | OK | `test_project_saves_fourteen_keys_and_restores_state` |
| Проект: новый сеанс → загрузить → состояние восстановлено | OK | OK | OK | там же |
| Проект: экспорт JSON | OK | OK | OK-с-оговоркой | `test_project_export_is_portable_and_imports_back` |
| Проект: импорт JSON | OK | OK | OK | там же |
| Проект: удаление | OK | OK | OK | ручная проверка |
| История: запись после сохранения состава/проекта | OK | OK | OK | `test_history_records_events_exports_csv_and_clears` |
| История: запись после расчёта | OK-с-оговоркой | OK-с-оговоркой | OK-с-оговоркой | см. ниже |
| История: цепочка контрольных сумм | OK | OK | OK | там же |
| История: экспорт CSV | OK | OK | OK | там же |
| История: восстановить материал из записи | OK | OK | OK | там же |
| История: очистка с подтверждением | OK | OK | OK | там же |
| Batch: шаблон CSV | OK | OK | OK | `test_batch_template_downloads_open_as_excel_and_csv` |
| Batch: шаблон XLSX | OK | OK | OK | там же |
| Batch: загрузка CSV `,` / `;`, UTF-8 / UTF-8-SIG | OK | OK | OK | `test_batch_accepts_both_separators_and_both_encodings` |
| Batch: расчёт трёх составов | OK | OK | OK | `test_batch_calculates_three_databases_and_exports_excel` (`slow`) |
| Batch: таблица результатов | OK | OK | OK | там же |
| Batch: колонка «Фазы» без C15 | — | — | OK | `test_batch_rejects_c15_for_steel_before_any_calculation` (`slow`) |
| Batch: экспорт XLSX | OK | OK | OK | `test_batch_calculates_three_databases_and_exports_excel` |
| Импорт: мусор отклоняется понятным сообщением | OK | OK | OK | `test_batch_rejects_a_junk_file_with_a_readable_message` |
| Пути: чистый `%LOCALAPPDATA%` — первый запуск | OK | OK | OK | `test_first_run_creates_the_profile_and_writes_nothing_into_the_program` |
| Пути: программа ничего не пишет в свою папку | OK | OK | OK | там же |
| Быстрые примеры: заполняют сайдбар | OK | OK | OK | `test_quick_examples_cover_three_databases_and_carry_a_steel` |
| Быстрые примеры: показаны в приложении | FAIL | FAIL | FAIL | недостижимый код в `ThermoGar_app.py:10464` |

### Оговорки

- **Проект: экспорт JSON (Fe и остальные).** Переносимый файл несёт материал,
  но не числовые настройки разделов: общая схема
  (`thermogar_verified_state.py:285`, владелец 3F) требует `widget_state == {}`.
  Локальное сохранение и открытие проекта настройки восстанавливает —
  проверено тестом. Под кнопкой стоит подпись, что настройки в переносимый
  файл не попадают.
- **История: запись после расчёта.** `record_calculation_history` вызывается
  из диаграмм, затвердевания, энергий, свойств и кинетики. Разделы
  «Расчёты → Одна температура / Температурный диапазон / Изменение состава»
  историю не пишут — вызова в `ThermoGar_app.py` нет. Это правка 3F.
- **Быстрые примеры.** Сам `render_quick_examples` исправлен и проверен
  напрямую (три базы, стальной пример Fe–0,2C–11,5Cr–0,7Ni, температура
  доезжает до сайдбара). В приложении функция не вызывается: в
  `ThermoGar_app.py:10464` стоит `raise _CompactHelpRendered`, и всё тело
  вкладки «Как пользоваться» после этой строки недостижимо.

## Ключевые числа пакетного расчёта

Совпадают с `tools\backend_reference.md` (допуск 0,05 п.п.):

| Состав | Фазы | Доли, % | Σ |
|---|---|---|---|
| Ni–15Al, 700 °C | FCC_A1 + GAMMA_PRIME | 69,578 + 30,422 | 100,000 |
| Al–4Cu–1Mg, 500 °C | GP_MAT + THETA_AL2CU | 99,234 + 0,766 | 100,000 |
| Fe–0,2C–11,5Cr–0,7Ni, 700 °C | BCC_B2 + M23C6 | 95,587 + 4,413 | 100,000 |

Три состава подряд через UI — 95 с (бэкенд-эталон 3,4 + 48,4 + 49,9 = 102 с).
Тест под маркером `slow`.

## Проверка выгрузок

Байты проверены, а не только наличие кнопки:

| Файл | Проверка |
|---|---|
| Шаблон XLSX | `openpyxl.load_workbook`, лист `Составы` |
| Шаблон CSV | начинается с `EF BB BF`, `pandas.read_csv` даёт 9 колонок и 2 строки |
| Результат batch XLSX | `openpyxl`, 5 листов: Сводка, Фазовые доли, Составы фаз ат, Составы фаз мас, Исходные данные |
| История CSV | `pandas.read_csv`, колонка «Событие» |
| Библиотека JSON | `json.loads`, `kind == "thermogar_alloys"`, импортируется в чистый профиль |
| Проект JSON | `json.loads`, `kind == "thermogar_project"`, импортируется в чистый профиль |

## Что осталось за границей проверки

- Диалог скачивания браузера не эмулируется: проверяются байты, которые
  `StateStore` кладёт в `state\<kind>\<sha>.<ext>` перед показом кнопки.
- Пакетные файлы XLSX на вход проверены схемой, но не прогоном расчёта
  (расчёт идёт тем же путём, что и CSV).
- Разделы «Расчёты», «Диаграммы», «Затвердевание», «Энергии», «Свойства»,
  «Кинетика» — зона 3F и 3G; здесь они затронуты только как источник записей
  в истории.
