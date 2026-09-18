"""14-Б, пункт 1: лестница Б до 10 добавок — копия ``results/wave14_a/p3_ladder.py``.

Отличия от 14-А: выход в ``p1/`` (каталог создаётся при старте), лестница по умолчанию Б, ступени 8…10 в
``kwn_parts.LADDER_B_EXTRA``. Расчёт, проверки и баланс масс — без изменений.

    p1_ladder.py <число добавок> <метка прогона> [<время, с>]

Один и тот же расчёт на ступени лестницы ``kwn_parts.LADDER_WT``: γ′
(``GAMMA_PRIME``) в ``FCC_A1`` при 750 °C, физические входы пункта 5 отчёта
13-Р2 (γ = 0,023 Дж/м², Vm = 6,5662724928 см³/моль у обеих фаз, объёмные
центры 1e30 м⁻³), сетка умолчаний раздела (0,2…10 нм, 80 классов), 10 с
модельного времени. Ступень 4 — ровно случай «основа 718 без Fe и Mo» 13-Р2;
его числа на 0.4.1 известны, по ним сверяется, что сборка из частей считает
то же, что ``run_precipitation``.

Порядок шагов — как в ``run_precipitation`` на 0.4.1: модель расчёта; вторая
модель со своей термодинамикой и на ней оценка зародыша; проверка сетки;
``setPSDrecording(False)``, ``cacheCalculations(True)``, ``solve``; проверки
качества приложения ``_quality``.

Баланс масс (пункт 4) сверяется двумя путями:

* **по записи kawin** — x0 = (1 − fv)·x + fconc по записанным ``volFrac`` и
  ``fconc``; по построению kawin это равенство для добавок выполняется всегда,
  кроме срезки отрицательного состава в ноль, поэтому оно ловит только срезку;
* **независимо, из распределения** — fv и содержание каждого элемента в
  выделениях заново сложены numpy из конечного распределения по размерам
  (``PBM.PSD``, ``PBM.PSDsize``) и составов выделения по классам
  (``PSDXbeta``), основа NI — как остаток 1 − Σ добавок в каждом классе. Это
  ловит потерю элемента: неверный индекс, отрицательную долю в выделении,
  расхождение записи с состоянием модели.
"""

from __future__ import annotations

import sys
import time
import json
import os
import threading
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kwn_parts as parts  # noqa: E402

N_SOLUTES = int(sys.argv[1])
RUN = sys.argv[2]
DURATION_S = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
# Потолок стены на solve, с: по нему процесс пишет частичное состояние и
# выходит с кодом 4. 0 — без потолка.
CAP_S = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
# Лестница: A — FE=18, MO=3 (как задумано), B — FE, MO, CO по 0,5 (контроль),
# C — один состав на четырёх добавках с FE=18 (контроль ловушки внутри предела).
LADDER = sys.argv[5].upper() if len(sys.argv) > 5 else "B"
OUT = HERE / "p1"
OUT.mkdir(parents=True, exist_ok=True)  # 14-Б: каталог нужен потоку опроса до первой записи
TAG = f"{LADDER}{N_SOLUTES}_{RUN}"
parts.setup_state(OUT, TAG)

record: dict = {
    "добавок": N_SOLUTES,
    "прогон": RUN,
    "лестница": LADDER,
    "свободно при старте потомка, ГиБ": round(parts.free_gib(), 3),
}
t0 = time.perf_counter()

import numpy as np  # noqa: E402
import thermogar_precipitation as tp  # noqa: E402

CASE = dict(
    matrix_phase="FCC_A1", precipitate_phase="GAMMA_PRIME", temperature_c=750.0,
    gamma=0.023, matrix_vm=6.5662724928, precip_vm=6.5662724928,
    nucleation_type="BULK", bulk_n0=1e30, grain_size_um=100.0,
    dislocation_density=5e12, gb_energy=0.3, cmin_nm=0.2, cmax_nm=10.0, bins=80,
)
record["случай"] = dict(CASE, duration_s=DURATION_S)
record["секунды импорта"] = round(time.perf_counter() - t0, 2)


def mass_balance(model, p: int, solutes: list[str]) -> dict:
    data = model.data
    n = int(data.n)
    x0 = np.asarray(data.composition[0], float)
    x = np.asarray(data.composition[n], float)
    fv = float(data.volFrac[n, p])
    fconc = np.asarray(data.fconc[n, p], float)
    elements = ["NI"] + solutes
    x0_all = np.concatenate([[1 - x0.sum()], x0])
    x_all = np.concatenate([[1 - x.sum()], x])
    fconc_all = np.concatenate([[fv - fconc.sum()], fconc])

    pbm = model.PBM[p]
    psd = np.asarray(pbm.PSD, float)
    size = np.asarray(pbm.PSDsize, float)
    xbeta = np.asarray(model.PSDXbeta[p], float)
    comp_avg = 0.5 * (xbeta[:-1] + xbeta[1:])
    vol_ratio = model.matrix.volume.Vm / model.precipitates[p].volume.Vm
    factor = model.precipitates[p].nucleation.volumeFactor
    weight = vol_ratio * factor * psd * size**3
    fv_ind = float(np.sum(weight))
    fconc_ind = np.array([np.sum(weight * comp_avg[:, e]) for e in range(len(solutes))])
    fconc_ind_all = np.concatenate([[np.sum(weight * (1 - comp_avg.sum(axis=1)))], fconc_ind])

    rows = []
    for i, element in enumerate(elements):
        in_matrix = (1 - fv) * x_all[i]
        recorded_sum = in_matrix + fconc_all[i]
        independent_sum = (1 - fv_ind) * x_all[i] + fconc_ind_all[i]
        rows.append({
            "элемент": element,
            "x0, мольная доля": float(x0_all[i]),
            "матрица в конце, мольная доля": float(x_all[i]),
            "в матрице (1−fv)·x": float(in_matrix),
            "в выделениях, запись kawin": float(fconc_all[i]),
            "в выделениях, из распределения": float(fconc_ind_all[i]),
            "невязка по записи, x0 − сумма": float(x0_all[i] - recorded_sum),
            "невязка независимая, x0 − сумма": float(x0_all[i] - independent_sum),
            "невязка независимая, доля x0": float((x0_all[i] - independent_sum) / x0_all[i]),
            "изменение fconc за последний шаг (для масштаба)": (
                float(data.fconc[n, p].sum() - data.fconc[n - 1, p].sum()) if i == 0
                else float(data.fconc[n, p, i - 1] - data.fconc[n - 1, p, i - 1])
            ) if n > 0 else None,
            "средний состав выделения": float(fconc_ind_all[i] / fv_ind) if fv_ind > 0 else None,
            "равновесный состав выделения xEqBeta в конце": (
                float(1 - np.sum(data.xEqBeta[n, p])) if i == 0 else float(data.xEqBeta[n, p, i - 1])
            ),
        })
    return {
        "шаг": n,
        "fv записанная": fv,
        "fv из распределения": fv_ind,
        "fv: разность": fv - fv_ind,
        "классов в конце": int(len(psd)),
        "PSDXbeta: минимум доли элемента в классах": float(xbeta.min()),
        "PSDXbeta: максимум суммы добавок в классе": float(xbeta.sum(axis=1).max()),
        "состав матрицы по ходу: минимум по добавкам": {
            element: float(np.min(data.composition[: n + 1, i])) for i, element in enumerate(solutes)
        },
        "срезка в ноль по ходу (composition ≤ 0)": bool(np.any(data.composition[: n + 1] <= 0)),
        "невязка по записи на всех шагах, максимум |x0 − сумма|": float(np.max(np.abs(
            data.composition[0][None, :]
            - ((1 - data.volFrac[: n + 1, p])[:, None] * data.composition[: n + 1] + data.fconc[: n + 1, p])
        ))),
        "сумма мольных долей: 1 − Σ(матрица + выделения)": float(
            1 - np.sum([(1 - fv_ind) * x_all[i] + fconc_ind_all[i] for i in range(len(elements))])
        ),
        "по элементам": rows,
    }


try:
    t1 = time.perf_counter()
    db = parts.load_database()
    record["база: SHA-256, разбор, правки, с"] = round(time.perf_counter() - t1, 2)
    record["после базы"] = parts.mem()

    if LADDER == "C":
        # Контроль: четыре добавки с FE=18 — состав p3_stock4.py.
        text = "CR=19, NB=5.1, TI=0.9, FE=18"
    elif LADDER == "B":
        text = parts.ladder_b_text(N_SOLUTES)
    else:
        text = parts.ladder_text(N_SOLUTES) if N_SOLUTES <= 6 else parts.ladder_text(6, with_seventh=True)
    elements, x_at, _x_wt = parts.composition_vectors_unlimited(db, "NI", text, "wt")
    solutes = elements[1:]
    record["состав, масс. %"] = text
    record["элементы"] = elements
    record["мольные доли"] = [float(v) for v in x_at]
    record["сообщения о правках базы"] = tp._database_override_warnings(db, elements)
    coverage = tp._phase_mobility_coverage(db).get(CASE["matrix_phase"], set())
    record["нет подвижностей матрицы"] = sorted(set(elements) - coverage)

    t2 = time.perf_counter()
    model, therm_s = parts.build_model(db, elements, x_at, CASE)
    record["сборка термодинамики (модель расчёта), с"] = round(therm_s, 3)
    record["сборка модели расчёта всего, с"] = round(time.perf_counter() - t2, 3)
    record["после модели расчёта"] = parts.mem()

    t3 = time.perf_counter()
    try:
        estimate_model, estimate_therm_s = parts.build_model(db, elements, x_at, CASE)
        record["сборка термодинамики (модель оценки), с"] = round(estimate_therm_s, 3)
        estimates = tp._nucleus_estimates(estimate_model, CASE["precipitate_phase"], [CASE["temperature_c"] + 273.15])
    except Exception as error:  # noqa: BLE001 — как в run_precipitation
        estimates = []
        record["оценка зародыша: отказ"] = f"{type(error).__name__}: {error}"
    record["оценка зародыша (вторая модель + движущая сила), с"] = round(time.perf_counter() - t3, 3)
    record["оценка: T, K; r*, нм; r_nuc, нм"] = estimates
    record["после оценки"] = parts.mem()
    tp._check_size_grid(estimates, CASE["cmin_nm"], CASE["cmax_nm"], CASE["bins"])

    model.setPSDrecording(False)
    if hasattr(model, "cacheCalculations"):
        model.cacheCalculations(True)
    t4 = time.perf_counter()
    progress_path = OUT / f"{TAG}_progress.jsonl"
    progress_path.unlink(missing_ok=True)
    stop_watch = threading.Event()

    def watch_solve() -> None:
        # Опрос состояния решателя из соседнего потока раз в 10 с: шаг,
        # модельное время, доля, r*, скорость зарождения, классов. На ходу
        # расчёта ничего не меняет.
        while not stop_watch.wait(10.0):
            elapsed = time.perf_counter() - t4
            try:
                d = model.data
                i = int(d.n)
                pp = model.phaseIndex(CASE["precipitate_phase"])
                row = {
                    "стена solve, с": round(elapsed, 1), "шаг": i,
                    "модельное время, с": float(d.time[i]),
                    "шаг по времени последний, с": float(d.time[i] - d.time[i - 1]) if i > 0 else None,
                    "доля, %": 100 * float(d.volFrac[i, pp]),
                    "r*, нм": 1e9 * float(d.Rcrit[i, pp]),
                    "скорость зарождения": float(d.nucRate[i, pp]),
                    "классов": int(len(model.PBM[pp].PSD)),
                    "рабочий набор, ГиБ": parts.mem()["rss_gib"],
                }
            except Exception as error:  # noqa: BLE001
                row = {"стена solve, с": round(elapsed, 1), "опрос": f"{type(error).__name__}: {error}"}
            with progress_path.open("a", encoding="utf-8") as sink:
                sink.write(json.dumps(row, ensure_ascii=False) + chr(10))
            if CAP_S and elapsed > CAP_S:
                record["исход"] = f"ПОТОЛОК: solve не закончен за {CAP_S:.0f} с стены"
                record["расчёт solve, с"] = f"> {CAP_S:.0f}"
                record["состояние на потолке"] = row
                # Баланс масс в момент потолка. Решатель в ловушке почти не
                # двигается, но снимок берётся на ходу из соседнего потока.
                try:
                    record["баланс масс на потолке (снимок на ходу)"] = mass_balance(
                        model, model.phaseIndex(CASE["precipitate_phase"]), solutes
                    )
                except Exception as error:  # noqa: BLE001
                    record["баланс масс на потолке (снимок на ходу)"] = f"{type(error).__name__}: {error}"
                record["память в конце"] = parts.mem()
                parts.write_json(OUT / f"{TAG}.json", record)
                print({"добавок": N_SOLUTES, "исход": record["исход"], "состояние": row}, flush=True)
                os._exit(4)

    threading.Thread(target=watch_solve, daemon=True).start()
    model.solve(DURATION_S, verbose=False)
    stop_watch.set()
    record["расчёт solve, с"] = round(time.perf_counter() - t4, 3)
    record["после расчёта"] = parts.mem()

    data = model.data
    p = model.phaseIndex(CASE["precipitate_phase"])
    n = int(data.n)
    record["строк кинетики"] = n + 1
    record["модельное время в конце, с"] = float(data.time[n])
    record["итоговая объёмная доля, %"] = 100 * float(data.volFrac[n, p])
    record["итоговый средний радиус, нм"] = 1e9 * float(data.Ravg[n, p])
    record["итоговая плотность частиц, 1/м³"] = float(data.precipitateDensity[n, p])
    record["движущая сила в начале, Дж/м³"] = float(data.drivingForce[0, p])
    quality = tp._quality(data, p, len(solutes), CASE["cmin_nm"], CASE["cmax_nm"], CASE["bins"])
    record["проверки качества"] = dict(zip(quality["Проверка"], quality["Статус"]))
    record["проверки качества все пройдены"] = bool((quality["Статус"] == "пройдена").all())
    t5 = time.perf_counter()
    record["баланс масс"] = mass_balance(model, p, solutes)
    record["баланс масс, с"] = round(time.perf_counter() - t5, 3)
    record["исход"] = "PASS" if record["проверки качества все пройдены"] else "расчёт прошёл, проверки качества не все"
except Exception as error:  # noqa: BLE001 — отказ и есть результат
    record["исход"] = "FAIL"
    record["отказ дословно"] = f"{type(error).__name__}: {error}"
    record["traceback, хвост"] = traceback.format_exc().strip().splitlines()[-10:]

record["всего в процессе, с"] = round(time.perf_counter() - t0, 2)
record["память в конце"] = parts.mem()
parts.write_json(OUT / f"{TAG}.json", record)
print({k: record.get(k) for k in (
    "добавок", "исход", "отказ дословно", "сборка термодинамики (модель расчёта), с",
    "оценка зародыша (вторая модель + движущая сила), с", "расчёт solve, с",
    "строк кинетики", "итоговая объёмная доля, %", "итоговый средний радиус, нм",
)}, record["память в конце"], flush=True)
