# Задача Волна 2B — снять hard-reject Fe в модулях (Э2, часть 2)

Исполнитель: Opus, Windows, worktree `C:\Users\gareg\Desktop\ThermoGar-w2b`, ветка `wave2b-fe-modules`.
Прочитай `PLAN_CLAUDE_2026-09-02.md` (Э2, раздел 3) и `tools\backend_reference.md`.
Python: `C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe`.
Зона: ТОЛЬКО `app\thermogar_diffusion.py`, `app\thermogar_precipitation.py`, `app\thermogar_workspace.py`.
НЕ трогать `thermogar_release_policy.py` и `ThermoGar_app.py` (их правит 2A параллельно).

## Цель
Сталь (Fe, thermogar_patch) работает в разделах Кинетика (диффузия, KWN) и в пакетном расчёте так же, как Ni/Al.
1C доказала прямыми вызовами kawin, что база и библиотека Fe тянут (диффузия 1.8 с, KWN BCC_A2/M23C6 20.7 с) —
блокирует только код. C15_LAVES для Fe исключается из списков фаз, предлагаемых пользователю.

## Правило C15 (локально, без общего хелпера — чтобы не пересекаться с 2A)
Там, где строится список фаз-кандидатов для выбора пользователем (матрица/выделение в KWN, фазы в диффузии),
для `database_key == "fe"` убрать `C15_LAVES`: `[p for p in phases if p != "C15_LAVES"]`. Набор — ровно эта одна фаза.

## Шаги

### 1. `thermogar_diffusion.py`
- Убрать hard-reject: `≈168 if canonical_key == "fe": raise RuntimeError(FE_DIFFUSION_BLOCK_MESSAGE)` — удалить.
  `RELEASE_DATABASE_KEYS` уже содержит `fe`, поэтому проверка `not in RELEASE_DATABASE_KEYS` пропустит Fe штатно.
- Мобильности Fe: база `mc_fe_v2062_with_mobility` их содержит (1C: диффузия Fe считается). Убедиться, что загрузка
  профиля Fe/thermogar_patch идёт корректно (тот же путь/SHA, что в других разделах).
- Если пользователю предлагается выбор фаз/фазы для диффузии и для Fe туда попадает C15_LAVES — отфильтровать (правило выше).
- `FE_DIFFUSION_BLOCK_MESSAGE` можно оставить в коде неиспользуемым или удалить; UI не должен его показывать.

### 2. `thermogar_precipitation.py`
- Убрать hard-reject: `≈514 if database_key == "fe": raise RuntimeError(FE_KWN_BLOCK_MESSAGE)` — удалить.
- Списки фаз матрицы и выделения (там, где `filter_phases`, ≈201, и построение опций для dropdown): для Fe убрать
  C15_LAVES (правило выше). Для Fe разумные дефолты матрицы/выделения — из 1C: матрица BCC_A2/FCC_A1, выделение
  M23C6 или CEMENTITE; но не «зашивать» жёстко — просто корректный отфильтрованный список, дефолт как у Ni/Al логики.
- Проверить, что KWN для Fe реально считает (kawin setup=True), как в 1C уровня (a).

### 3. `thermogar_workspace.py` (пакетный расчёт, библиотека, история)
- Найти, где batch/библиотека отклоняет Fe (ищи `== FE_DATABASE_KEY`, `"fe"`, `raise`, ветки вокруг ≈567/613 и в
  функции пакетного расчёта). Fe уже частично поддержан (профиль/валидация есть). Снять оставшиеся блокировки так,
  чтобы пакетный расчёт для Fe шёл тем же путём, что Ni/Al (через равновесие приложения), с фильтром C15.
- Если C15 фильтруется на стороне приложения (2A в `compatible_phases_for_components`), в workspace дублировать не надо —
  но проверить, что batch зовёт именно общий путь расчёта, а не собственный список фаз. Если собственный — отфильтровать C15 локально.

### 4. Проверка
- `tools\thermogar_diffusion_test.py --project-root ...` — PASS.
- `tools\thermogar_precipitation_test.py --project-root ...` — PASS.
- `tools\test_backend_calculations.py -m "not slow"`: раньше 3 xfail (Fe диффузия-модуль, Fe KWN-модуль, Al плотность).
  ПОСЛЕ 2B первые два xfail(strict) должны стать PASS и тест УПАДЁТ на strict-xfail — это ожидаемо и это сигнал успеха.
  Обнови в `tools\test_backend_calculations.py` ровно эти два кейса: снять маркер `xfail` (Fe диффузия-модуль и Fe
  KWN-модуль теперь должны просто PASS). Al-плотность (нет модели THETA_AL2CU в PDB) остаётся `xfail(strict=True)`.
  Не трогать другие кейсы и ожидаемые числа. Прогнать заново → 44 passed / 1 xfailed.
- `tools\thermogar_self_test.py` — PASS (self_test использует Ni/Al, не должен пострадать).

### 5. Отчёт `tasks\WAVE2B_REPORT.md` (≤ 25 строк) + в ответе
Что удалено (файл:строка), где применён фильтр C15, результаты тестов (в т.ч. что 2 xfail стали PASS), коммиты,
открытые вопросы (например, если workspace batch зависит от правки 2A в ThermoGar_app.py — отметить как зависимость мержа).
Коммиты по шагам, ветку не мержить.

## Запрещено
Трогать `ThermoGar_app.py`, `thermogar_release_policy.py`, любые другие файлы; менять численные алгоритмы, TDB/PDB;
вводить SHA-пины/sentinel; возвращать C15 для Fe; удалять исходные файлы.
