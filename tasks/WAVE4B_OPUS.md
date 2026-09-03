# Задача 4B — полный регресс main перед релизом

Worktree `C:\Users\gareg\Desktop\ThermoGar-w4b`, ветка `wave4b-regression`. Python — `C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe`.
Ничего не чинить в `app\` — только прогонять, фиксировать и (если нужно) править тесты, которые устарели по формулировкам.
Прочитай `TESTS_BASELINE.md`, `tools\backend_reference.md`, `tools\ui_matrix_F.md`, `ui_matrix_G.md`, `ui_matrix_H.md`.

## Прогоны (все с `-B -X utf8`, `--project-root C:\Users\gareg\Desktop\ThermoGar` где нужно; таймаут 20 мин на файл)
1. Все `tools\thermogar_*_test.py` + `thermogar_self_test.py` + `thermogar_fe_internal_smoke.py` — как в волне 0.
2. `pytest tools\test_backend_calculations.py -m "not slow"` и `-m slow`.
3. `pytest tools\test_ui_f.py`, `test_ui_g.py`, `test_ui_h.py` — обе части (`not slow` и `slow`).
   Итого ~2–2,5 ч машинного времени; гнать серийно, чтобы времена были честными.
4. Приложение: `streamlit run app\ThermoGar_app.py --server.headless true` — старт, 200, стоп.

## Результат
`TESTS_RELEASE_0.3.0.md` в корне: таблица «файл | exit | результат | время» + сравнение с `TESTS_BASELINE.md`
(было 19 OK / 5 FAIL из 24; сейчас — сколько тестов всего и сколько зелёных). Известные допустимые падения: только
`thermogar_paths_test::test_006` (venv внутри worktree) — и то проверить, проходит ли из основной папки.
Любой другой FAIL — не чинить, а описать: тест, ошибка, вероятная причина, чей файл.
`tasks\WAVE4B_REPORT.md` (≤ 20 строк). Коммит: `TESTS_RELEASE_0.3.0.md` + отчёт. Ветку не мержить.
