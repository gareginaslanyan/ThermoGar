# Задача Волна 1C — бэкенд-автотесты расчётов для Ni/Al/Fe (фундамент Э3)

Исполнитель: Opus (терминал, Windows). Корень: `C:\Users\gareg\Desktop\ThermoGar`.
Прочитай `PLAN_CLAUDE_2026-09-02.md` (разделы 1, Э3, 3) и `TESTS_BASELINE.md`.
Python: `.venv-windows\Scripts\python.exe`. Зона: только новые файлы `tools\test_backend_calculations.py`,
`tools\backend_reference.md`, `tasks\`. Код в `app\` и `packaging\` не трогать — их правят другие исполнители.

## Ветка
`git checkout -b wave1c-backend-tests` от `main`. Не мержить.

## Цель
Набор быстрых pytest-тестов **без Streamlit**, которые на реальных базах проекта проверяют, что каждый вид расчёта
из 7 разделов приложения выполним для Ni, Al и Fe, и фиксируют время выполнения. Это ответит на вопрос
«какие разделы для стали/алюминия реально считаются, а где база/библиотека не тянет» ДО того, как мы включим кнопки.
Ожидаемые числа — не «истина», а reference для регрессии.

## Важно про архитектуру
`app\ThermoGar_app.py` — Streamlit-скрипт верхнего уровня, его нельзя импортировать. Поэтому тесты пишутся
на двух уровнях:
- (a) прямые вызовы pycalphad/scheil/kawin на базах проекта — то, что приложение делает под капотом;
- (b) публичные функции импортируемых модулей: `thermogar_equilibrium_core`, `thermogar_physical`, `thermogar_properties`,
  `thermogar_diffusion`, `thermogar_precipitation`, `thermogar_verified_equilibrium`, `thermogar_restricted_fe_core`
  (посмотри их `def`/`class`, используй то, что не требует `st`). Для Fe в diffusion/precipitation сейчас стоит
  hard-reject (`RuntimeError`) — тест на Fe помечай `xfail(strict=True, reason="Fe hard-reject, снимается в Э2")`,
  и рядом сделай прямой kawin/pycalphad-вариант (уровень a), чтобы знать, работает ли база.

## Базы и составы
- Ni: `databases\converted\mc_ni_v2036_with_mobility.garcalc.tdb`, состав Ni–15Al (ат.%) или Ni-8Cr-6Al-… (см. `results\*.csv`, там есть готовые сканы для сверки).
- Al: `databases\converted\al\mc_al_v2037_with_mobility.thermogar.tdb`, Al–4Cu–1Mg (масс.%).
- Fe: `databases\converted\fe\mc_fe_v2062_with_mobility.thermogar.tdb`, Fe–0.2C–11.5Cr–0.7Ni (масс.%). **Фаза `C15_LAVES` исключается из списка фаз всегда** (это правило продукта).
Пересчёт масс.%→мол. доли — через `thermogar_equilibrium_core.mass_to_mole_fractions` или pycalphad.
Список фаз: `Database.phases`, отфильтровать по элементам (`pycalphad.core.utils.filter_phases`), для Fe убрать C15_LAVES.

## Матрица тестов (по одному быстрому кейсу на ячейку; общий бюджет прогона ≤ 15 мин)
| Раздел | Кейс |
|---|---|
| Равновесие | точка при T; T-скан 5 точек; X-скан 5 точек (`equilibrium`) — доли фаз суммируются в 1, есть ожидаемая матричная фаза (FCC_A1 для Ni/Al, BCC_A2/FCC_A1 для Fe при 700 °C) |
| Диаграммы | бинарная T–X (`pycalphad.mapping` `BinaryStrategy` или `binplot` на грубой сетке): Ni–Al, Al–Cu, Fe–C; изоплета по одному элементу для тройного состава; тройное сечение при T (`TernaryStrategy` на грубой сетке); карта доли фазы — сетка 4×4 точек `equilibrium` |
| Затвердевание | равновесное: T-скан от ликвидуса вниз, доля LIQUID монотонно убывает; Scheil: `scheil.simulate_scheil_solidification` с шагом 5–10 K, `fraction_solid` доходит до ≥0.95 |
| Энергии | `calculate(..., output="GM")` для двух фаз; движущая сила = разница GM при одинаковом составе; T₀ — пересечение GM двух фаз по T (`find_monotonic_linear_crossings` из equilibrium_core, если применимо) |
| Свойства | `thermogar_physical.calculate_physical_properties` (плотность) с `databases\physical\original\physical_data_v103.pdb`; `thermogar_properties` — VRH и вклады упрочнения на тестовых числах |
| Кинетика | `thermogar_diffusion` — 1D-диффузия короткая (то, что уже делает `thermogar_diffusion_test.py`, но для всех 3 баз); `thermogar_precipitation` / kawin — KWN на 1 фазу, короткое время (Ni: GAMMA_PRIME, Al: THETA/S-фаза, Fe: M23C6 или CEMENTITE) |
| Проекты/batch | 3 состава подряд через `equilibrium` — время на точку |

Для каждой ячейки: `@pytest.mark.parametrize("db_key", ["ni","al","fe"])`, таймаут через `pytest-timeout` (если нет в venv —
поставить в venv `pip install pytest pytest-timeout`, это допустимо), 120 с на тест. Медленные (диаграммы Fe) — маркер `slow`.
Записывать в `tools\backend_reference.md`: таблица раздел × база → PASS/FAIL/XFAIL, время, ключевые числа
(T ликвидуса, доли фаз при T, плотность), текст ошибки при FAIL.

## Шаги
1. Разведка: `def`/`class` в перечисленных модулях, сигнатуры; как `ThermoGar_app.py` вызывает mapping/scheil/kawin
   (`grep -n "Strategy\|scheil\|kawin\|simulate_" app\ThermoGar_app.py`) — воспроизвести те же параметры.
2. Написать тесты уровня (a) для всех 3 баз, прогнать, зафиксировать.
3. Добавить уровень (b) там, где модуль импортируем.
4. Прогон целиком: `python -m pytest tools\test_backend_calculations.py -v -m "not slow"` и отдельно `-m slow`.
5. `tools\backend_reference.md` + `tasks\WAVE1C_REPORT.md` (≤ 25 строк): итоговая матрица, где Fe/Al не считается и почему
   (библиотека / база / hard-reject в коде / время), рекомендации по сеткам по умолчанию для Fe. Коммиты в ветке.

## Запрещено
Правки в `app\`, `packaging\`, существующих тестах; изменение TDB/PDB; включение C15_LAVES для Fe; «подгонка» ожидаемых чисел
без пометки, откуда они.

## ДОПОЛНЕНИЕ (после инцидента с общим рабочим деревом)
- Работай ТОЛЬКО в своём worktree: 1A → `C:\Users\gareg\Desktop\ThermoGar-w1a`, 1B → `...\ThermoGar-w1b`, 1C → `...\ThermoGar-w1c`.
  Ветка там уже выбрана; `git checkout` других веток — запрещён. Папку `C:\Users\gareg\Desktop\ThermoGar` не трогать.
- Python всегда по абсолютному пути: `C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe`.
- Архив: `C:\Users\gareg\Desktop\ThermoGar\_archive_codex\` (абсолютный путь; в worktree этой папки нет).
- Рантайм для 1B: `C:\Users\gareg\Desktop\ThermoGar\ThermoGar-Installer-Assets\`; сборки класть в `<worktree>\dist\`.
- Перед стартом: `git -C <worktree> log --oneline -3` — убедись, что видишь свою ветку и коммит «Wave 1 task files».
