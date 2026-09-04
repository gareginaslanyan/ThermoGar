# 0.3.1 — общие правила волны 5

Цель релиза 0.3.1: диаграммы и сканы быстрее в разы без потери корректности; закрыть backlog 0.3.0.
Численные модели (pycalphad/scheil/kawin) и базы TDB/PDB не трогаем. Все правки — обычные коммиты в своей ветке,
файлы с LF, тесты до/после, отчёт ≤ 30 строк в `tasks\WAVE5<X>_REPORT.md`. Python —
`C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe`; базы/архив/рантайм — абсолютными путями.

| | worktree / ветка | владеет |
|---|---|---|
| 5A | `ThermoGar-w5a` / `wave5a-phase-presets` | `app\ThermoGar_app.py` (только функции фаз: `compatible_phases_for_components`, `phase_selection_editor`, `prepare_calculation`, `*_phase_candidates`), `app\thermogar_release_policy.py`, `configs\phase_presets.json` (новый), `tools\test_phase_presets.py` (новый) |
| 5B | `ThermoGar-w5b` / `wave5b-parallel-engine` | `app\thermogar_parallel.py` (новый), `tools\test_parallel_engine.py` (новый), `tools\bench_parallel.md` (новый). **`ThermoGar_app.py` не трогать** — интеграция в волне 6 |
| 5C | `ThermoGar-w5c` / `wave5c-backlog` | `packaging\*`, `HANDOFF.md`, `CHANGELOG.md`, `README.md`, `app\thermogar_release_policy.py` — ТОЛЬКО строка FEATURES про stage12 (согласовано с 5A: 5A не трогает таблицу FEATURES) |

Замеры делать на одних и тех же кейсах из `tools\backend_reference.md` (Ni–15Al 700 °C; Al–4Cu–1Mg 500 °C;
Fe–0.2C–11.5Cr–0.7Ni 700 °C) и писать «было → стало» с числом фаз/точек.
