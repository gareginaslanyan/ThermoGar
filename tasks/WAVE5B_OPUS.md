# Задача 5B — параллельный движок для сканов и карт (модуль + бенчмарк, без интеграции в UI)

Прочитай `tasks\WAVE5_COMMON.md`, `tools\backend_reference.md`, как сканы/карта считают точки сейчас
(`ThermoGar_app.py`: `temperature_calculate`, `concentration_calculate`, `calculate_ternary_phase_fraction_map`,
плотность по T, batch в `thermogar_workspace.py`) — только читать.

## Идея
Точки скана/карты/batch независимы → считать их в пуле процессов. Ограничения Windows: `spawn`, поэтому воркер —
в импортируемом модуле (не в `ThermoGar_app.py`, он top-level Streamlit-скрипт); `Database` парсится в каждом воркере
один раз через `initializer` (путь + SHA-256, проверка SHA перед использованием); результаты — plain dict/списки
(без xarray-объектов через pickle). Число воркеров = `os.cpu_count()-1` (мин. 1), настраивается.

## Шаги
1. `app\thermogar_parallel.py`: `ParallelEquilibrium(database_path, sha256, workers)` с методами `map_points(points,
   components, phases, conditions_builder, pdens)` → список результатов в исходном порядке с полем ошибки на точку
   (одна упавшая точка не валит остальные); `close()`; контекст-менеджер. Прогресс — callback с индексом точки
   (Streamlit-прогрессбар подключит волна 6). Fallback: при `workers=1` — последовательно в текущем процессе, без пула.
   Логика самого равновесия — та же `pycalphad.equilibrium` с теми же `calc_opts`, что в приложении (`pdens=500`).
2. Бенчмарк `tools\bench_parallel.md`: T-скан 20 точек и карта 5×5 на трёх базах, workers=1 vs cpu_count-1; учесть
   стоимость инициализации воркеров (парсинг базы 3–7 с). Замерить, при каком числе точек параллель окупается.
3. Тест `tools\test_parallel_engine.py`: результаты `workers=1` и `workers=N` совпадают побайтово (доли фаз, составы),
   ошибка в одной точке изолируется, SHA-несовпадение базы → отказ до запуска, пул закрывается без зомби-процессов
   (проверить `psutil`/`tasklist` до/после), повторный запуск в одной сессии переиспользует пул.
4. Заметка для волны 6 (в отчёте): точные места вызова в `ThermoGar_app.py`/`thermogar_workspace.py`, что нужно
   поменять, как прокинуть прогресс, где хранить пул (`st.session_state` нельзя — пул не pickle; предложить
   module-level singleton с ключом (path, sha, workers)).
Отчёт: таблица ускорения, порог окупаемости, ограничения.
