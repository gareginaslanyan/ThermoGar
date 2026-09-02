# Отчёт: волна 1C — бэкенд-автотесты расчётов Ni/Al/Fe

Ветка `wave1c-backend-tests` (worktree `ThermoGar-w1c`). Новые файлы: `tools\test_backend_calculations.py`, `tools\backend_reference.md`, `tasks\WAVE1C_REPORT.md`; `app\` и `packaging\` не тронуты. В `.venv-windows` поставлен `pytest-timeout 2.4.0` (разрешено задачей). `.git\index.lock` не существовал — удалять было нечего.
Прогоны: `-m "not slow"` — **42 passed, 3 xfailed, 712 с**; `-m slow` — **12 passed, 1510 с**. Матрица 19 ячеек × 3 базы заполнена целиком, FAIL нет. Не считаются три ячейки:

| Не считается | Причина | Категория |
|---|---|---|
| Fe, диффузия (модуль) | `thermogar_diffusion.py:167`, плюс `RELEASE_DATABASE_KEYS=("ni","al")` в `thermogar_release_policy.py:27` | hard-reject в коде |
| Fe, KWN (модуль) | `thermogar_precipitation.py:514` | hard-reject в коде |
| Al, плотность | нет модели `THETA_AL2CU` в `physical_data_v103.pdb`: покрытие 98.93 %, плотность `None` | данные PDB |

Ни библиотека, ни TDB-база ничего не блокируют: прямые вызовы kawin на Fe-базе проходят (диффузия 1.8 с,
KWN BCC_A2/M23C6 20.7 с) — Fe закрыт только политикой в коде, Э2 это снимает. Scheil на Fe риском не оказался:
29 с, 21 шаг, `fraction_solid` = 1.0. C15_LAVES исключена (35 фаз после `filter_phases` → 34 в расчёте),
и тест падает в обратном случае — если фаза исчезнет из базы и правило станет пустым.

Находки для UI: (1) `filter_phases` оставляет упорядоченную половину пары order/disorder — матрица зовётся
`GP_MAT` (Al) и `BCC_B2` (Fe), а не `FCC_A1`/`BCC_A2`: расчёт верный, имена в таблицах нет; (2) карта доли фазы
по двум составным осям требует систему ровно из трёх элементов + VA, иначе `Number of degrees of freedom is not
zero`; (3) T₀ ищется только в узком окне (Fe 900–1000 K → 956.39 K), на широком — `CROSSING_Y_NONMONOTONIC`.

Сетки: у Fe ограничивать надо изоплету (209 с) и карту (117 с), а не Scheil; лимит «ровно 3 точки» для Fe-сканов
по времени не оправдан (5 точек — 36–39 с). Дороже всех не Fe, а **Al** (64 активные фазы): тройное сечение 282 с,
карта 222 с, batch 13–19 с/точку. Ni: шаг по T в равновесном затвердевании нужен 5–10 K. Открытое: маркер `slow`
не зарегистрирован (нет `pytest.ini`/`conftest.py` в зоне задачи) — идёт `PytestUnknownMarkWarning`, фильтрация
работает; экспорт (Excel/PNG/CSV) не проверялся, он в Streamlit-обвязке. Числа и времена — `tools\backend_reference.md`.
