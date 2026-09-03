# Задача 3G — Кинетика: диффузия/гомогенизация и KWN-выделения (Э3)
Сначала прочитай `tasks\WAVE3_COMMON.md`. Worktree `C:\Users\gareg\Desktop\ThermoGar-w3g`, ветка `wave3g-kinetics`.
Твои файлы: `app\thermogar_diffusion.py`, `app\thermogar_precipitation.py`, `app\thermogar_numerical_grid.py`.
UI разделов рендерится функциями `render_kinetics_section` (diffusion.py:1220) и `render_precipitation_section`
(precipitation.py:749); кнопки `kin_single_run_*`, `kin_hom_run_*` и кнопка KWN — найти ключи в коде.

## Матрица (× Ni/Al/Fe)
1. Диффузия одной фазы: задать геометрию/время/температуру → расчёт → профиль, mass balance, экспорт Excel/PNG.
2. Гомогенизация (многофазная) → расчёт → результат + экспорт.
3. KWN-выделения: матрица/выделение по умолчанию (Ni: FCC_A1/GAMMA_PRIME; Al: FCC_A1(GP_MAT)/THETA или S; Fe: FCC_A1 или
   BCC/M23C6) → расчёт короткого времени → доля, размер, PSD, экспорт Excel/NPZ/JSON/PNG.

## Известные точки внимания
1. Кнопки `kin_*_run_fe` были disabled по «input_provenance + подтверждение» (1A): проверить, что для Fe этот gate такой же,
   как для Ni/Al, и что он объяснён пользователю; лишние подтверждения-«галочки Codex» — убрать, оставить нормальные
   валидации ввода.
2. KWN для Fe: 2B отметила, что в UI матрица предлагается только `FCC_A1`, т.к. `filter_phases` оставляет `BCC_B2` вместо
   `BCC_A2`, а ordered-фаза матрицей быть не может. Решить на уровне UI: предлагать пользователю `BCC_A2` как матрицу, если
   в базе есть пара `BCC_A2/BCC_B2` (бэкенд `BCC_A2` принимает — модульный тест 1C проходит). Не менять kawin-логику.
3. `fe_kwn_publication_status = BLOCKED` в провенансе (2B): заменить на нейтральный `NOT_PERFORMED`/`NOT_ASSESSED` в духе
   остальной метаинформации — это не функциональный gate.
4. Дефолты Fe (2B добавила: C/CR 900 °C, BCC_A2/M23C6 700 °C) — проверить, что они реально считаются в UI за разумное время.
5. Предупреждение kawin `divide by zero` в NucleationRate — известное, из внешней библиотеки; не глушить глобально, но
   пользователю в UI не показывать как ошибку.
6. Time/step контролы: проверить, что защита от абсурдных значений (0 шагов, отрицательное время) даёт сообщение, не traceback.

## Тесты
`tools\test_ui_g.py` (pytest, AppTest на `app/ThermoGar_app.py` с переходом в раздел Кинетика; либо прямой рендер
`render_*_section` через AppTest-скрипт-обёртку) — по кейсу на ячейку. `thermogar_diffusion_test`, `thermogar_precipitation_test`,
`test_backend_calculations -k "diffusion or kwn"` остаются зелёными.
