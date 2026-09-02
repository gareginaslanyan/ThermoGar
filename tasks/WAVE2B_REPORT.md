# Отчёт: волна 2B — Fe в модулях кинетики и в пакетном расчёте

Ветка `wave2b-fe-modules` (worktree `ThermoGar-w2b`), не смержена. Тронуты `app\thermogar_diffusion.py`, `app\thermogar_precipitation.py`, `app\thermogar_workspace.py`, `tools\test_backend_calculations.py`, `tools\thermogar_diffusion_test.py`; `ThermoGar_app.py` и `thermogar_release_policy.py` — нет. Коммиты: 602f63e (диффузия), 396912f (KWN), a336692 (workspace), 29fe9cd (тесты).

Удалено:
- `thermogar_diffusion.py:168-169` — `if canonical_key == "fe": raise RuntimeError(FE_DIFFUSION_BLOCK_MESSAGE)`, вместе с константой `:99`;
- `thermogar_precipitation.py:514-515` — `if database_key == "fe": raise RuntimeError(FE_KWN_BLOCK_MESSAGE)`, вместе с константой `:95`;
- `thermogar_precipitation.py:754-756` — заглушка UI «Steel: расчёт KWN не входит в текущий этап Core1»;
- `tools\thermogar_diffusion_test.py:108-113` — кейс, ожидавший снятый текст отказа; остальные 10 кейсов отказа целы.

Fe проходит штатной проверкой `RELEASE_DATABASE_KEYS`: ключ, путь и SHA-256 профиля `thermogar_patch` уже были в release policy. Дефолты Fe добавлены рядом с Ni/Al — `thermogar_diffusion.py:97` (FE, C/CR, 900 °C, FCC_A1, гомогенизация FCC_A1+BCC_A2) и `thermogar_precipitation.py:75` (BCC_A2/M23C6, 700 °C, γ=0,3 Дж/м², Vm=7,09 см³/моль); логика та же, что у Ni/Al: дефолт применяется, если он есть в отфильтрованном списке, иначе берётся первый кандидат.

Фильтр C15: локальные `EXCLUDED_PHASES = {"fe": ("C15_LAVES",)}` + `_selectable_phases()` в `thermogar_diffusion.py:445` (списки фаз подвижностей, 1284 и 1391), `thermogar_precipitation.py:198` (матрица 813, выделения 829) и `thermogar_workspace.py:77` (колонка «Фазы» пакетной таблицы, 2045). Проверено на Fe-базе: `_compatible_phases` даёт 32 фазы с `C15_LAVES`, после фильтра — без неё; матрица (`FCC_A1`) и фазы подвижностей (`BCC_A2`, `FCC_A1`) C15 и так не содержали; для `ni` фильтр ничего не меняет.

Пакетный расчёт блокировок Fe не имел: `run_batch_calculations` уже шёл общим путём через `broker.execute_row` с `profile_key="thermogar_patch"`, собственного списка фаз у него нет — фильтр применён только к пользовательской колонке «Фазы».

Тесты (`.venv-windows`, project-root = worktree): `thermogar_diffusion_test.py`, `thermogar_precipitation_test.py`, `thermogar_self_test.py` — PASSED. `test_backend_calculations.py -m "not slow"` — **44 passed, 1 xfailed, 674 с** (было 42 passed / 3 xfailed).
Сняты ровно два `xfail(strict)` — `test_diffusion_module[fe]` и `test_kwn_module[fe]`, оба PASS (вместе 17,6 с). Al-плотность осталась `xfail(strict=True)`, прочие кейсы и ожидаемые числа не тронуты.

Открытые вопросы:
- провенанс KWN по-прежнему ставит `fe_kwn_publication_status = BLOCKED`: снят программный блок, научная квалификация пары матрица–выделение не проводилась — менять статус вне задачи 2B;
- в UI KWN для Fe матрица предлагается только `FCC_A1`: `filter_phases` оставляет `BCC_B2` вместо `BCC_A2`, а ordered-фаза матрицей быть не может; дефолт `BCC_A2` сработает, когда это изменится (бэкенд `BCC_A2` принимает — модульный тест проходит именно на нём);
- фильтр C15 в `thermogar_workspace.py` продублирован локально: если 2A отфильтрует C15 в `compatible_phases_for_components`, дубль можно снять при мерже.
