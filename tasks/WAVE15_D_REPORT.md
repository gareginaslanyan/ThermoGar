# Волна 15-Д — BL-35: внятный отказ расчёта выделений вместо ZeroDivisionError

Задание — `tasks/WAVE15_D_OPUS.md`. Дерево `C:\Users\gareg\Desktop\ThermoGar-w15d`, ветка `wave15-bl35`
от `wave15-718` (`1880d81`). В `main` и `wave15-limits` ничего не вливалось, ничего не пушилось. Дерево
`ThermoGar-w15a` не трогалось.

Интерпретатор — `C:\Users\gareg\Desktop\ThermoGar\.venv-windows` (kawin и pycalphad оттуда же). Все расчёты
шли по одному, `PYTHONHASHSEED=0`. Перед каждым запуском проверялась свободная физическая память
(`Win32_OperatingSystem.FreePhysicalMemory`), порог 2,0 ГиБ. Ни разу ждать не пришлось: свободно было
2,04…3,16 ГиБ. Пик одного расчёта KWN на 718 — 0,345…0,356 ГиБ.

## Итог

* **6 случаев из 6 завершились без traceback.** В пяти сработало условие остановки (п. 2). В одном
  (750 °C, 95 мДж/м²) pycalphad упал раньше проверки, и его перехватила страховка (п. 4).
* **Побайтовая сверка сошлась.** Все таблицы совпали с `1880d81`, кроме строки «Файл базы».
* **На 718 проверка тоже ничего не изменила в расчёте.** Посчитанная часть каждого из шести случаев
  совпала с первыми строками прогонов 15-В значение в значение (кинетика и состав матрицы).
* Тесты — см. п. 7.

**Одна неточность в исходных записях** (к сути задания не относится, но её стоит поправить): в
`tasks/WAVE15_V_REPORT.md` (п. 7) и в строке BL-35 реестра путь обрыва записан как
`Thermodynamics._getDrivingForceTangent → getLocalEq`. В случае 750 °C, 95 мДж/м² traceback снят
целиком, и путь другой: `_calcNucleationRate → betaMulti → impingementFactor → curvatureFactor →
_getCompositionSetsEq → local_equilibrium`. Движущая сила на том же составе к этому моменту уже
посчитана без ошибки. Конечная точка та же — `minimizer.pyx:145`. Реестр я не правил: он вне файлов
волны.

---

## 1. Как устроены условия остановки в kawin

Версия — kawin из `.venv-windows`. Номера строк — по установленным файлам.

### Что принимает `addStoppingCondition`

`kawin/precipitation/KWNBase.py`:

```
220:    def addStoppingCondition(self, condition, mode = 'or'):
...
226:        condition: PrecipitateStoppingCondition
...
232:        self._stoppingConditions.append(condition)
233:        if mode == 'or':
234:            self._stopConditionMode.append(True)
235:        else:
236:            self._stopConditionMode.append(False)
```

Тип объекта не проверяется. У объекта вызываются только три метода:

* `testCondition(model)` и `isSatisfied()` — в `postProcess`, строки 381–385 (цитата ниже);
* `reset()` — в `KWNBase.reset`: `100:        for sc in self._stoppingConditions:` /
  `101:            sc.reset()`.

Готовые классы из `kawin/precipitation/StoppingConditions.py` здесь не подходят. `CompositionCondition`
сравнивает один элемент с одним порогом, а нужна проверка всего состава и основы. Поэтому в
приложении написан свой объект `_MatrixCompositionStop` с теми же тремя методами и `satisfiedTime()`.

### Когда вызывается проверка

`kawin/solver/Solver.py`, цикл `DESolver.solve`:

```
177:        while currTime < tf and not stop:
...
182:            self.preProcess()
...
192:            X0_flat, dt = self.iterator(self._getdXdt, currTime, self._flattenX(X0), self._updateX)
193:            X0 = self._unflattenX(X0_flat, self._X0)
194:            
195:            currTime += dt
196:            X0, stop = self.postProcess(currTime, X0)
```

`kawin/GenericModel.py` — итератор по умолчанию RK4, приложение его не меняет
(`model.solve(final_time, verbose=False)`):

```
289:    def solve(self, simTime, iterator = rk4Iterator, verbose=False, vIt=10, minDtFrac = 1e-8, maxDtFrac = 1):
...
316:        solver = DESolver(iterator, minDtFrac = minDtFrac, maxDtFrac = maxDtFrac)
317:        solver.setFunctions(preProcess=self.preProcess, postProcess=self.postProcess, printHeader=self.printHeader, printStatus=self.printStatus)
318:        solver.setdXdtFunctions(self.getdXdt, self.correctdXdt, self.getDt, self.flattenX, self.unflattenX)
```

`kawin/precipitation/KWNBase.py`, `postProcess`:

```
365:        super().postProcess(t, x)
366:        self._calculateDependentTerms(t, x)
367:        self._appendArrays(self._currY)
368:
369:        #Update particle size distribution (this includes adding bins, resizing bins, etc)
370:        #Should be agnostic of eulerian or lagrangian implementations
371:        self._updateParticleSizeDistribution(t, x)
372:
373:        #Update coupled models
374:        self.updateCoupledModels()
375:
376:        #Check stopping conditions
377:        orCondition = False
378:        andCondition = True
379:        numAndCondition = 0
380:        for i in range(len(self._stoppingConditions)):
381:            self._stoppingConditions[i].testCondition(self)
382:            if self._stopConditionMode[i]:
383:                orCondition = orCondition or self._stoppingConditions[i].isSatisfied()
...
392:        stop = orCondition or andCondition
```

### Где считается локальное равновесие

`kawin/precipitation/KWNBase.py`:

```
325:        self._processX(x)
326:        if self._currY is None:
327:            #print('start iteration')
328:            self._currY = self.data.copySlice(self.data.n)
329:        else:
330:            self._currY.time = np.array([t])
331:            self._currY.temperature = np.array([self.temperatureParameters(t)])
332:            self._currY = self._calcMassBalance(t, x, self._currY)
333:            self._currY = self._calcNucleationRate(t, x, self._currY)
334:            self.growth, self._currY = self._growthRate(self._currY)
```

Строка 332 — баланс масс, из него получается новый состав матрицы. Строки 333–334 — движущая сила,
множитель присоединения (`betaMulti`) и скорость роста. Все три считают равновесия pycalphad на этом
новом составе.

`_calculateDependentTerms` вызывается в двух местах:

* **внутри шага** — из `getdXdt` (`345:        self._calculateDependentTerms(t, x)`). Итератор RK4 вызывает
  его четыре раза (`kawin/solver/Iterators.py`, строки 66, 72, 76, 80: `f(t, X_old, True)`,
  `f(t, X_k1)`, `f(t, X_k2)`, `f(t, X_k3)`). Первый вызов после `preProcess` (`self._currY = None`)
  ничего не считает (стр. 326–328). Остальные три считают равновесия на промежуточных X;
* **после шага** — из `postProcess`, строка 366. Здесь баланс масс и равновесия считаются на новом X
  **до** записи шага (стр. 367) и **до** проверки условий (стр. 381).

Баланс масс в `kawin/precipitation/KWNEuler.py` не даёт составу уйти ниже нуля, зато выше единицы и в
отрицательную основу — даёт:

```
474:        if np.sum(Y.volFrac[0]) < 1:
475:            Y.composition[0] = (self.data.composition[0] - np.sum(Y.fconc[0], axis=0)) / (1 - np.sum(Y.volFrac[0]))
476:            Y.composition[0,Y.composition[0] < 0] = self.constraints.minComposition
```

`kawin/precipitation/PrecipitationParameters.py:241: self.minComposition = 0`. Значит, вычерпанная
добавка записывается ровно нулём, а не отрицательным числом. Поэтому условие п. 2 «добавка стала
≤ 0» ловит именно это.

Место деления на ноль — `pycalphad/core/minimizer.pyx`:

```
144:            out_row[free_variable_column_offset + i] += prefactor * \
145:                (phase_amt[idx]/current_system_amount) * mass_jac[component_idx, num_statevars+j] * c_component[chempot_idx, j]
```

### Вывод: может ли остановка сработать раньше падения

**Может, но не всегда.** Проверка видит только состав, который уже прошёл через pycalphad: строки 333–334
идут раньше строки 381. Состав первого «плохого» шага сначала попадает в pycalphad. Дальше два
варианта:

* **pycalphad досчитал** — шаг записывается, и условие останавливает расчёт до следующего шага. Так в
  пяти случаях из шести. Прогноз по данным 15-В перед запуском: в пяти случаях в записанных данных
  есть плохой шаг, после которого расчёт шёл дальше. Прогноз совпал с прогоном до строки.
* **pycalphad упал на этом же составе** — условие не успевает, и нужна страховка п. 4. Так в случае
  750 °C, 95 мДж/м². Traceback (`results/wave15_d/trace_750_95.txt`):

  ```
  File "...\kawin\solver\Solver.py", line 196, in solve
  File "...\kawin\precipitation\KWNBase.py", line 366, in postProcess
  File "...\kawin\precipitation\KWNBase.py", line 333, in _calculateDependentTerms
  File "...\kawin\precipitation\KWNBase.py", line 435, in _calcNucleationRate
  File "...\kawin\precipitation\NucleationRate.py", line 120, in betaMulti
  File "...\kawin\thermo\MultiTherm.py", line 448, in impingementFactor
  File "...\kawin\thermo\MultiTherm.py", line 326, in curvatureFactor
  File "...\kawin\thermo\Thermodynamics.py", line 1006, in _getCompositionSetsEq
  File "...\kawin\thermo\Thermodynamics.py", line 994, in _update_composition_sets
  File "...\kawin\thermo\LocalEquilibrium.py", line 86, in local_equilibrium
  File "...\pycalphad\core\solver.py", line 168, in solve
  File "pycalphad/core/minimizer.pyx", line 145, in pycalphad.core.minimizer.write_row_fixed_mole_fraction
  ZeroDivisionError: float division
  ```

  Состав, на котором упал pycalphad, в `model.data` не записан. Его сняла обёртка диагностического
  скрипта `results/wave15_d/scripts/trace_750_95.py`: t = 19,21 с, доля выделения 0,996, мольные доли
  AL 2,82, CR 0, MO 0, NB 8,69, NI 34,6, TI 3,09, основа −48,2. Условие п. 2 такой состав поймало бы,
  но pycalphad получает его раньше.

Условие STOP из п. 1 («ни в одном из шести») не выполнено: остановка срабатывает в пяти случаях.
Поэтому работа продолжена.

---

## 2–4. Что сделано в `app/thermogar_precipitation.py`

* `_matrix_composition_violation(composition, solutes, balance, initial)` находит первый элемент, который
  нарушил баланс масс. Нарушение — доля любого элемента, включая основу (1 − Σ добавок), вне [0; 1] или
  нечисловая, либо добавка, которой в исходном составе было больше нуля, стала ≤ 0. Порогов и допусков
  нет. Сначала проверяется выход за [0; 1], потом ноль, в порядке добавок.
* `_MatrixCompositionStop` — условие остановки kawin с методами `testCondition`, `isSatisfied`,
  `reset` и `satisfiedTime`. Условие только читает `model.data.composition[n]` и `model.data.time[n]`.
  Подключается в `run_precipitation` через `model.addStoppingCondition(...)` перед `model.solve`.
* Страховка: `model.solve` обёрнут в `try/except ZeroDivisionError`. Перехватывается только ошибка, в
  traceback которой есть кадр из `pycalphad` (`_raised_in_pycalphad`). Любая другая ошибка деления
  пробрасывается дальше. После перехвата результат собирается штатно из `model.data` до последнего
  записанного шага.
* `PrecipitationResult.stop_note` — новое поле, по умолчанию `""`. `_quality(..., stop_note)`: если текст
  есть, строка «Состав матрицы допустим» получает статус «ошибка» и этот текст в «Примечании». Если
  текста нет, строка считается как раньше, байт в байт.
* Больше ничего не менялось: параметры, `warnings`, provenance, графики и таблицы остались прежними.

На экране отказ виден так: общий `st.error("Одна или несколько внутренних проверок не пройдены.")` над
вкладками и строка в таблице проверок на вкладке «Итоги». Отдельного `st.warning` с текстом отказа нет:
задание просит строку в quality, и я его не добавлял. Если владелец хочет видеть текст отказа сразу, а
не в таблице, достаточно одной строки в `render_precipitation_section`. Это решение за мастером.

### Тексты на экране — на согласование

Числа печатаются в формате `.4g` с точкой, как в соседних примечаниях проверок (`_quality`). Имена
элементов — как в базе, заглавными.

**Остановка по условию (п. 2):**

> Расчёт остановлен на {t} с модельного времени ({t/3600} ч): доля {ЭЛЕМЕНТ} в матрице стала {x} ат. %,
> баланс масс нарушен. Показана часть расчёта до остановки. Причина: при движущей силе по базе
> зарождение практически безбарьерное, и выделение вычерпывает добавки из матрицы быстрее, чем модель
> это выдерживает; см. docs/LIMITS_OF_APPLICABILITY.md.

**Перехват деления на ноль (п. 4):**

> Расчёт прерван после {t} с модельного времени ({t/3600} ч): на следующем шаге pycalphad не смог
> посчитать локальное равновесие для состава матрицы, полученного из баланса масс (деление на ноль).
> Последний посчитанный состав матрицы, ат. %: {ЭЛ x, …, ОСНОВА x}. Показана часть расчёта до обрыва.
> Причина: при движущей силе по базе зарождение практически безбарьерное, и выделение вычерпывает
> добавки из матрицы быстрее, чем модель это выдерживает; см. docs/LIMITS_OF_APPLICABILITY.md.

Фраза о причине вынесена в константу `KWN_COMPOSITION_STOP_CAUSE`. Ссылка на
`docs/LIMITS_OF_APPLICABILITY.md` подразумевает раздел, который появится с выпуском 0.4.2; в этой ветке
`docs/` не менялся.

---

## 5. Шесть случаев 718

Скрипт — `results/wave15_d/scripts/run_718.py`. Входы — `study_wave15_v_718.case_arguments(T, γ, GRID)`,
без изменений. Вызов — штатный `run_precipitation`, без обёрток. Потомок ловит любое исключение
только для того, чтобы записать его в сводку как «traceback»; таких записей нет. Выходы —
`results/wave15_d/runs/<случай>/` (`run.json`, `kinetics.csv`, `matrix.csv`, `quality.csv`,
`child.log.txt`), память — `results/wave15_d/runs/memory.jsonl`.

| случай | исход | что сработало | элемент | шагов | остановка, с модельного времени | макс. доля, % | 15-В: шагов / обрыв, с | счёт, с | пик, ГиБ |
|---|---|---|---|---|---|---|---|---|---|
| 700 °C, 78 | результат | п. 2 | NB = 0 | 168 | 2,011 | 11,23 | 341 / 2,94 | 44 | 0,352 |
| 700 °C, 95 | результат | п. 2 | NB = 0 | 212 | 3,844 | 13,62 | 370 / 4,66 | 54 | 0,351 |
| 700 °C, 112 | результат | п. 2 | TI = 0 | 265 | 14,55 | 6,12 | 598 / 15,81 | 33 | 0,354 |
| 750 °C, 78 | результат | п. 2 | TI = 0 | 448 | 13,01 | 22,69 | 451 / 13,02 | 66 | 0,352 |
| 750 °C, 95 | результат | **п. 4** | — | 416 | 19,18 (последний записанный шаг) | 13,55 | 416 / 19,18 | 46 | 0,345 |
| 750 °C, 112 | результат | п. 2 | MO = 0 | 339 | 24,18 | 13,59 | 345 / 24,20 | 52 | 0,356 |

Во всех шести случаях строка «Состав матрицы допустим» имеет статус «ошибка», остальные восемь проверок
пройдены. Предупреждения прежние: правка подвижности ниобия и шесть добавок.

Случаи 700 °C теперь считаются 33…54 с вместо 822…1416 с в 15-В: почти всё время 15-В уходило на шаги
после разрыва баланса масс.

**Проверка делает только одно — останавливает расчёт.** Для каждого случая `kinetics.csv` и
`matrix.csv` 15-Д совпали (`DataFrame.equals`) с первыми строками тех же файлов 15-В
(`results/wave15_v/runs/`).

Полные тексты сообщений:

* **700 °C, 78:** Расчёт остановлен на 2.011 с модельного времени (0.0005586 ч): доля NB в матрице стала 0 ат. %, баланс масс нарушен. Показана часть расчёта до остановки. Причина: при движущей силе по базе зарождение практически безбарьерное, и выделение вычерпывает добавки из матрицы быстрее, чем модель это выдерживает; см. docs/LIMITS_OF_APPLICABILITY.md.
* **700 °C, 95:** Расчёт остановлен на 3.844 с модельного времени (0.001068 ч): доля NB в матрице стала 0 ат. %, баланс масс нарушен. Показана часть расчёта до остановки. Причина: при движущей силе по базе зарождение практически безбарьерное, и выделение вычерпывает добавки из матрицы быстрее, чем модель это выдерживает; см. docs/LIMITS_OF_APPLICABILITY.md.
* **700 °C, 112:** Расчёт остановлен на 14.55 с модельного времени (0.004042 ч): доля TI в матрице стала 0 ат. %, баланс масс нарушен. Показана часть расчёта до остановки. Причина: при движущей силе по базе зарождение практически безбарьерное, и выделение вычерпывает добавки из матрицы быстрее, чем модель это выдерживает; см. docs/LIMITS_OF_APPLICABILITY.md.
* **750 °C, 78:** Расчёт остановлен на 13.01 с модельного времени (0.003613 ч): доля TI в матрице стала 0 ат. %, баланс масс нарушен. Показана часть расчёта до остановки. Причина: при движущей силе по базе зарождение практически безбарьерное, и выделение вычерпывает добавки из матрицы быстрее, чем модель это выдерживает; см. docs/LIMITS_OF_APPLICABILITY.md.
* **750 °C, 95:** Расчёт прерван после 19.18 с модельного времени (0.005329 ч): на следующем шаге pycalphad не смог посчитать локальное равновесие для состава матрицы, полученного из баланса масс (деление на ноль). Последний посчитанный состав матрицы, ат. %: AL 1.245, CR 23.15, MO 1.986, NB 0.7175, NI 50.66, TI 0.6225, FE 21.62. Показана часть расчёта до обрыва. Причина: при движущей силе по базе зарождение практически безбарьерное, и выделение вычерпывает добавки из матрицы быстрее, чем модель это выдерживает; см. docs/LIMITS_OF_APPLICABILITY.md.
* **750 °C, 112:** Расчёт остановлен на 24.18 с модельного времени (0.006717 ч): доля MO в матрице стала 0 ат. %, баланс масс нарушен. Показана часть расчёта до остановки. Причина: при движущей силе по базе зарождение практически безбарьерное, и выделение вычерпывает добавки из матрицы быстрее, чем модель это выдерживает; см. docs/LIMITS_OF_APPLICABILITY.md.

Замечание к таблице. В 750 °C, 112 элемент — MO, хотя NB в том же шаге тоже 0. Проверка называет первую
вычерпанную добавку в порядке состава (AL, CR, MO, NB, NI, TI). В 700 °C, 112 и 750 °C, 78 первым
вычерпывается титан, а не ниобий.

---

## 6. Побайтовая сверка

Способ — как 14-Б, п. 6.

* Скрипт `results/wave13_r/p1/scripts/p1_run.py` — без изменений. Раннер —
  `results/wave15_d/scripts/p6_run.sh`.
* Снимки — `git archive <ревизия> app databases` во временный каталог, для `1880d81` (`wave15-718`) и
  `5ff155a` (код 15-Д). `git diff --stat 1880d81 5ff155a -- app databases` показывает один файл:
  `app/thermogar_precipitation.py | 136 +++…-`.
* Каждый снимок считался дважды, отдельными процессами, по одному, `PYTHONHASHSEED=0`, с пустым каталогом
  состояния. Свободно перед стартом — 2,51…2,72 ГиБ, пик — 0,35 ГиБ.
* Как и в 14-Б, KWN — ячейка `test_kwn_module[ni]`: Ni–9,8Al–8,3Cr ат. %, γ/γ′, 800 °C, горизонт 1 с,
  сетка 0,2…5 нм × 30. Равновесие — Ni–15Al ат. %, 500…1300 °C шагом 25 °C.
* Выходы — `results/wave15_d/p6/out_*`, таблица — `results/wave15_d/p6/sha256_table.txt`. Каталоги
  состояния `state` (кэш базы, 11 МБ) перенесены из `results` в scratchpad сессии и в ветку не попали.

SHA-256, первые 12 знаков:

| файл | `1880d81` | `1880d81`, повтор | `5ff155a` | `5ff155a`, повтор | 14-Б `main` |
|---|---|---|---|---|---|
| записи параметров базы | `78f3853e1768` | `78f3853e1768` | `78f3853e1768` | `78f3853e1768` | `78f3853e1768` |
| **равновесие Ni-15Al** | `a84a20231415` | `a84a20231415` | **`a84a20231415`** | `a84a20231415` | `a84a20231415` |
| **KWN: кинетика** | `3ac535ee450a` | `3ac535ee450a` | **`3ac535ee450a`** | `3ac535ee450a` | `3ac535ee450a` |
| **KWN: сводка** | `2dd22f58327c` | `2dd22f58327c` | **`2dd22f58327c`** | `2dd22f58327c` | `2dd22f58327c` |
| **KWN: состав матрицы** | `23eb50c201aa` | `23eb50c201aa` | **`23eb50c201aa`** | `23eb50c201aa` | `23eb50c201aa` |
| **KWN: состав на границе** | `8e57b5e90e3b` | `8e57b5e90e3b` | **`8e57b5e90e3b`** | `8e57b5e90e3b` | `8e57b5e90e3b` |
| **KWN: распределение размеров** | `224751ed6982` | `224751ed6982` | **`224751ed6982`** | `224751ed6982` | `224751ed6982` |
| **KWN: массивы модели** | `c925384ae3cd` | `c925384ae3cd` | **`c925384ae3cd`** | `c925384ae3cd` | `c925384ae3cd` |
| **KWN: проверки качества** | `dcd1812d1699` | `dcd1812d1699` | **`dcd1812d1699`** | `dcd1812d1699` | `dcd1812d1699` |
| KWN: параметры | `e9229029dbb9` | `e9229029dbb9` | `9c1828562743` | `9c1828562743` | `5d0e6f2d5d2b` |
| **KWN: поле `warnings`** | `4f53cda18c2b` | `4f53cda18c2b` | **`4f53cda18c2b`** | `4f53cda18c2b` | `4f53cda18c2b` |

**Условие выполнено.** Параметры отличаются ровно одной строкой. `diff` (путь сокращён):

```
< 1,Файл базы,C:\…\scratchpad\p6\src_1880d81\databases\converted\mc_ni_v2036_with_mobility.garcalc.tdb
> 1,Файл базы,C:\…\scratchpad\p6\src_5ff155a\databases\converted\mc_ni_v2036_with_mobility.garcalc.tdb
```

Хеш параметров отличается и от 14-Б — там тоже был другой путь снимка. Все остальные хеши совпали и
с 14-Б.

---

## 7. Тесты

Новый файл — `tools/test_precipitation_bl35.py`:

* поиск нарушения: шесть составов, включая ноль, −1e−12, >1, отрицательную основу и NaN, плюс добавку,
  которой в исходном составе не было;
* условие остановки: срабатывает на первом плохом шаге, не перезаписывается следующими шагами,
  сбрасывается `reset()`;
* распознаётся только деление на ноль из `pycalphad`;
* `_quality` с текстом отказа и без него;
* **случай 718, 700 °C, 95 мДж/м²** — `run_precipitation` возвращает результат: «Состав матрицы
  допустим» = ошибка, текст совпадает с `stop_note`, строк больше 100, расчёт до 100 ч не дошёл.
  Отдельный замер `-m slow` до снятия метки: **42,57 с**. Это меньше 60 с, поэтому по заданию тест
  **не помечен slow** и идёт в обычном прогоне.

Прогон — каждый файл отдельным процессом,
`python.exe -B -X utf8 -m pytest tools/<файл> -q -m "not slow" -p no:cacheprovider`, `PYTHONHASHSEED=0`,
порог свободной памяти 2,0 ГиБ. Логи — `results/wave15_d/tests/*.log.txt`.

| файл | свободно на старте, ГиБ | exit | итог pytest | время |
|---|---|---|---|---|
| `tools/test_precipitation_bl35.py` | 2,73 | 0 | **11 passed**, 1 warning | 35,9 с |
| `tools/test_backend_calculations.py` | 2,78 | 0 | **43 passed**, 14 deselected, 4 warnings | 449,8 с |
| `tools/test_precipitation_grid.py` | 2,80 | 0 | **32 passed**, 13 warnings | 191,1 с |
| `tools/test_ui_g.py` | 2,29 | 0 | **29 passed**, 3 deselected, 2 warnings | 310,7 с |

Падений нет. Среди предупреждений — `RuntimeWarning: divide by zero` из
`kawin/precipitation/NucleationRate.py:190` (4 раза) и предупреждение matplotlib о более чем 20 открытых
фигурах (`app/thermogar_precipitation.py:506`, 1 раз). Строка 506 — это `_single_figure`, её правка не
касалась. Эти же файлы на `1880d81` для сравнения предупреждений не гонялись. Медленные кейсы
(`-m slow`) по заданию не запускались.

---

## 8. Git

`git log --oneline wave15-718..wave15-bl35`:

```
<последний коммит — сам этот отчёт; хеш его в тексте быть не может, см. `git log`>
03ed586 docs(15-Д): отчёт BL-35; тест 718 без метки slow (43 с), логи тестов, сверка п. 6
9b4034f test(15-Д): шесть случаев 718 без traceback; тест BL-35
5ff155a fix(15-Д): BL-35 — внятный отказ расчёта выделений вместо ZeroDivisionError
```

`git status --short` — пустой вывод (снят после коммита `03ed586`, до коммита отчёта; отчёт — единственный файл последнего коммита):

```
```
