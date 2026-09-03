# Волна 4B — отчёт

Ветка `wave4b-regression`, worktree `C:\Users\gareg\Desktop\ThermoGar-w4b`, от `main` (`edba403`).
В `app\` и в тестах ничего не менялось: правки не понадобились.

1. Прогнано серийно 28 запусков за ~2 ч 1 мин: 19 одиночных файлов `tools\`, 8 наборов pytest
   (backend, F, G, H — по частям `not slow` и `slow`), старт приложения. Результат — в
   `TESTS_RELEASE_0.3.0.md`, полные логи и `wave4b_runs.jsonl` — в
   `C:\Users\gareg\Desktop\ThermoGar\_archive_codex\wave4b_logs\` (вне git).
2. Итог: 351 тест-кейс, 349 зелёных, 0 timeout. Одно допустимое падение и один заявленный `xfail`.
3. Допустимое падение — `thermogar_paths_test::test_006`: венв лежит вне worktree.
   Из основной папки файл проходит целиком (`Ran 6 tests — OK`), как и просила задача проверить.
4. Заявленный `xfail` — `test_backend_calculations::test_alloy_density[al]`: у `THETA_AL2CU`
   нет модели плотности в `physical_data_v103.pdb`, это описано в `tools\backend_reference.md`.
5. Два падения в `test_ui_f.py -m slow` (`test_binary_diagram[fe]`, `test_isopleth_diagram[ni]`) —
   не регрессия. В общий профиль `%LOCALAPPDATA%\ThermoGar\workspace\projects\` параллельно
   работавшая волна 4A положила `wave4a-upgrade-probe.thermogar.json` с неполным envelope;
   приложение честно его отклонило и показало `st.error`, а тест считает любой неожиданный
   `st.error` падением. Перепрогон этих двух тестов после исчезновения файла — 2 passed.
6. Замечание для мастера проекта, чужой файл: `tools\test_ui_f.py` не изолирует
   `THERMOGAR_STATE_ROOT` и работает в общем профиле пользователя (в отличие от
   `tools\test_ui_h.py`, который заводит приватный корень на каждый тест). Пока это так,
   наборы 3F нельзя гонять одновременно с чем-либо, что пишет в `%LOCALAPPDATA%\ThermoGar\`.
7. Сравнение с `TESTS_BASELINE.md`: было 24 файла, 19 OK / 5 FAIL. Пять падавших файлов волна 1A
   перенесла в `_archive_codex\tools\` (`982ef57`), осталось 19 — из них 18 exit 0 и 1 известное
   падение. Плюс появились 8 наборов pytest, которых в baseline не было.
8. Единственное изменение состава кейсов среди уцелевших файлов:
   `thermogar_verified_loaders_test.py` — 19 тестов было, 18 стало (волна 3F+3H сняла
   sentinel-тест на SHA, `0c29669`).
9. Приложение: `streamlit run app\ThermoGar_app.py --server.headless true` поднялось за 2.8 с,
   `http://localhost:8517/` ответил 200, `Traceback` в выводе нет, процесс остановлен.
   Порт 8517 взят вместо 8501, чтобы не пересечься с волной 4A.
10. Отклонения от текста задачи, оба сознательные и описаны в `TESTS_RELEASE_0.3.0.md`:
    - `--project-root` указан на worktree, а не на основную папку, иначе проверялось бы
      содержимое `main`, а не ветки;
    - таймаут на наборы pytest поднят с 20 до 90 мин: по отчётам волн 1C и 3F медленные части
      идут 25 и 39 мин, при 20 минутах половина наборов дала бы ложный timeout. Фактический
      максимум — 31:24 (`test_ui_f.py -m slow`).
11. Времена по отношению к `TESTS_BASELINE.md` — верхняя оценка: волна 4A работала на этой же
    машине параллельно. Внутри регресса всё шло строго по одному, поэтому между собой
    времена сопоставимы.
12. Побочные файлы: `thermogar_fe_database_test.py` записал 3 файла в
    `results\validation\stage13_2\`. Оставлены как untracked, в коммит не входят.
13. Коммит волны: `TESTS_RELEASE_0.3.0.md` и этот отчёт. Ветка не мержится.
