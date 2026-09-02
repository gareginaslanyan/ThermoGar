# Задача Волна 2A — единый фильтр C15 в приложении (Э2, часть 1)

Исполнитель: Opus, Windows, worktree `C:\Users\gareg\Desktop\ThermoGar-w2a`, ветка `wave2a-c15-app`.
Прочитай `PLAN_CLAUDE_2026-09-02.md` (Э2, раздел 3) и `tools\backend_reference.md` (что реально считается).
Python: `C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe`.
Зона: ТОЛЬКО `app\ThermoGar_app.py` и `app\thermogar_release_policy.py`. Другие файлы не трогать
(модули diffusion/precipitation/workspace правит 2B параллельно).

## Цель
Фаза `C15_LAVES` для базы Fe (`thermogar_patch`) исключается из КАЖДОГО расчёта единообразно, в одном месте;
автоматические списки фаз её не содержат, явный ручной выбор — отклоняется понятной ошибкой без запуска расчёта.
Убрать искусственные ограничения, оставшиеся от Codex-диагностики. Численные алгоритмы не менять.

## Правило C15 (канон)
- Применяется только к `database_key == "fe"`. Для Ni/Al ничего не меняется.
- Исключаемый набор: `frozenset({"C15_LAVES"})`. Не «зашивать» больше фаз.
- Бэкенд это уже переживает (проверено 1C: Fe считает равновесие/диаграммы/затвердевание/энергии/плотность
  без C15). Мы только гарантируем, что C15 не попадает в расчёт нигде в UI.

## Шаги

### 1. Канонический хелпер в `thermogar_release_policy.py`
Добавить (рядом с другими Final/функциями):
```python
FE_EXCLUDED_PHASES: Final = frozenset({"C15_LAVES"})

def effective_release_phases(database_key: str, phases) -> list[str]:
    """Список фаз для расчёта: для Fe (thermogar_patch) убирает C15_LAVES."""
    result = [p for p in phases if not (database_key == "fe" and p in FE_EXCLUDED_PHASES)]
    return result
```
(Именно здесь, потому что модуль импортируют все; 2B этот файл не трогает.)

### 2. Единая точка фильтра в `ThermoGar_app.py`
- В `compatible_phases_for_components` (≈2214) — это чокпоинт для диаграмм, prepare_calculation и т.д. —
  после `filter_phases` и `filter_for_mode` прогнать результат через `effective_release_phases(database_key, phases)`.
  Импортировать `effective_release_phases`, `FE_EXCLUDED_PHASES` из `thermogar_release_policy`.
- Проверить, что через `compatible_phases_for_components` идут ВСЕ авто-списки: `binary_phase_candidates` (≈3841),
  `isopleth_phase_candidates` (≈4379), `ternary_phase_candidates` (≈4631), `prepare_calculation` (≈2427),
  карта доли фазы. Если какой-то маршрут строит список фаз в обход (напрямую `filter_phases`/`db.phases`) —
  добавить туда тот же `effective_release_phases`. Составить список всех мест в отчёте.

### 3. Явный ручной выбор C15 — отклонять
- В `phase_selection_editor` (≈2257) и/или `prepare_calculation`: если для Fe пользователь вручную отметил
  `C15_LAVES`, расчёт не запускать — показать `st.error` («C15_LAVES исключена для стали thermogar_patch и не может
  быть выбрана») и вернуть пустой/None результат так, чтобы дальше не пошёл backend. Не давать C15 в список галочек
  для Fe вообще (проще: не показывать её как опцию, а если пришла из session_state — игнорировать + сообщение).

### 4. Снять лимит «ровно 3 точки» для Fe-сканов
- `restricted_fe_three_axis_points` (≈696) и её вызовы (≈6255 T-скан, ≈6720 X-скан): 1C показала, что Fe спокойно
  считает 5+ точек (36–39 с). Сделать так, чтобы Fe-сканы по T и по составу использовали ту же сетку точек, что Ni/Al
  (число точек из UI), а не жёсткие 3. Если проще всего — заменить вызовы на общий путь построения точек скана,
  сохранив для Fe корректный контекст (профиль thermogar_patch, receipt/инвалидацию, если есть). Backend Fe — тот же
  `equilibrium`, фильтр C15 из шага 2 уже применён. Не ломать Ni/Al.

### 5. Удалить ветку «2000 K / высокотемпературная проверка C15»
- Диагностический артефакт: `≈8846–9031` (в разделе Затвердевание, спец-обработка при 2000 K с расчётом C15) и
  `≈10577–10637` (кнопка «Проверить текущий состав при 2000 K» в справке/паспорте, `fe_guard_status`, строка
  «Высокотемпературная проверка C15_LAVES» ≈9187). Удалить эти блоки целиком; на их месте ничего диагностического
  не оставлять. Обычное затвердевание для Fe должно работать штатно (1C: равновесное 93 с, Scheil 29 с) — с фильтром C15.
- Проверить, что удаление не оставило висящих переменных/ключей session_state и не сломало соседний код.

### 6. Тексты
- Строки-подписи про C15 оставить нейтральными и правдивыми (например «Fe-база thermogar_patch · C15_LAVES исключена»),
  но без диагностических формулировок «проверка/2000 K».

### 7. Проверка
- `.venv-windows\Scripts\python.exe -I -B -X utf8 tools\thermogar_self_test.py --project-root C:\Users\gareg\Desktop\ThermoGar` — PASS.
- `tools\thermogar_verified_loaders_test.py`, `tools\thermogar_restricted_fe_core_test.py` — OK.
- `tools\test_backend_calculations.py -m "not slow"` — по-прежнему 42 passed / 3 xfailed (2B снимет 2 из xfail; на 2A
  ветке они остаются xfail — это ок).
- AppTest: `AppTest.from_file("app/ThermoGar_app.py", default_timeout=300).run()` для базы Fe и для Ni — `at.exception` пуст.
  Проверить, что в списках фаз Fe нет `C15_LAVES` (можно ассертом в одноразовом скрипте, не коммитить его).
- Приложение стартует (`streamlit run ... --server.headless true`, порт отвечает 200).

### 8. Отчёт `tasks\WAVE2A_REPORT.md` (≤ 25 строк) + в ответе
Все места, где применён фильтр; как отклоняется ручной C15; что стало со сканами и веткой 2000 K; результаты тестов;
коммиты в ветке; открытые вопросы. Коммиты по шагам, ветку не мержить.

## Запрещено
Трогать модули 2B (diffusion/precipitation/workspace) и любые другие файлы; менять численные алгоритмы, TDB/PDB;
вводить SHA-пины/sentinel; добавлять C15 обратно; удалять файлы (только в _archive_codex, но в этой задаче удалений нет).
