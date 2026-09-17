#!/usr/bin/env python3
"""Волна 15, задача 15-А — первая сверка расчёта с измеренным.

Задание `tasks/WAVE15_A_OPUS.md`, отчёт `tasks/WAVE15_A_REPORT.md`.

Два сплава, оба состарены при 873 K, измерены атомно-зондовой томографией:

* A — Ni-7,5Al-8,5Cr ат. %, Booth-Morrison и др., arXiv:0706.3916;
* Б — Ni-5,2Al-14,2Cr ат. %, Sudbrack и др., Acta Mater 54 (2006) 3199.

Измеренные числа ниже перенесены из задания мастера, а не из статей: сами
файлы у мастера (`tasks/RULES.md`, «Источники»).

Шаги:

* ``eq`` — пункт 0: равновесие без кинетики. Доля и составы γ′ и матрицы при
  873 K на базе mc_ni 2.036 двумя наборами фаз: всеми фазами, которые база
  строит на Ni-Al-Cr (путь волны 11), и одной парой FCC_A1 + GAMMA_PRIME,
  которую решает KWN. Молярные объёмы фаз — из `physical_data_v103.pdb` тем же
  путём, которым их считает приложение (`calculate_physical_properties`).
* ``kwn`` — пункты 1–5: расчёт выделений штатным путём приложения
  (`thermogar_precipitation.run_precipitation`) на шести случаях, по одному
  процессу-потомку на случай.
* ``estimate`` — оценка зародыша приложения до расчёта, по ней выбрана сетка.
* ``inputs`` — все входы KWN одним файлом.
* ``report`` — таблицы и графики из сохранённых выходов, без счёта.

Ничего не подгоняется. Все входы объявлены в этом файле (``ALLOYS``, ``GRID``,
``case_arguments``) и записаны шагом ``inputs`` в ``results/wave15_a/inputs.json``
до первого прогона KWN.

Запуск (интерпретатор — venv основного репозитория):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 ^
        tools\\study_wave15_validation.py --only eq
    ... --only kwn --min-free-gib 3.0
    ... --only report

Память. Порог входа — ключ ``--min-free-gib`` (по заданию 3,0 ГиБ). Аварийный
порог по ходу — `study_hn62m_wave12.E1_ABORT_FREE_GIB`, читается из исходника, не меняется.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
for entry in (ROOT / "app", TOOLS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

OUT = ROOT / "results" / "wave15_a"
DB_REL = "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"
PDB_REL = "databases/physical/original/physical_data_v103.pdb"

TEMPERATURE_K = 873.0
TEMPERATURE_C = TEMPERATURE_K - 273.15
COMPONENTS = ("AL", "CR", "NI", "VA")
MATRIX_PHASE = "FCC_A1"
PRECIPITATE_PHASE = "GAMMA_PRIME"
# Плотность выборки приложения (`ThermoGar_app`, pdens=500) и контроль на 100.
EQ_PDENS = (500, 100)

AVOGADRO = 6.02214076e23  # 1/моль, точное значение SI 2019

# --------------------------------------------------------------------------- #
# Измеренное — из задания мастера
# --------------------------------------------------------------------------- #

ALLOYS: dict[str, dict[str, Any]] = {
    "A": {
        "название": "Ni-7,5Al-8,5Cr",
        "источник": "Booth-Morrison и др., arXiv:0706.3916",
        "состав, ат. доли": {"AL": 0.075, "CR": 0.085},
        "межфазная энергия, мДж/м²": (18.0, 24.0, 30.0),
        "центр, мДж/м²": 24.0,
        "равновесная доля, %": (16.4, 0.6),
        "чужие базы, доля γ′, %": (16.69, 14.90),
        "γ′ равновесный, ат. %": {"NI": 76.33, "AL": 17.82, "CR": 5.85},
        "матрица на бесконечности, ат. %": None,
        "критический радиус авторов, нм": 0.76,
        "время, ч": (1/6, 1/4, 1, 4, 16, 64, 256, 1024),
        "R, нм": (0.90, 1.00, 1.24, 1.70, 2.80, 3.59, 5.54, 8.30),
        "Nv, 1e24 м⁻³": (0.26, 1.89, 2.21, 1.02, 0.60, 0.34, 0.20, 0.13),
        "доля, %": (0.31, 1.36, 2.48, 5.98, 9.12, 11.8, 14.6, 16.0),
    },
    "Б": {
        "название": "Ni-5,2Al-14,2Cr",
        "источник": "Sudbrack и др., Acta Mater 54 (2006) 3199",
        "состав, ат. доли": {"AL": 0.052, "CR": 0.142},
        "межфазная энергия, мДж/м²": (15.5, 22.5, 29.5),
        "центр, мДж/м²": 22.5,
        "равновесная доля, %": (15.6, 0.4),
        "чужие базы, доля γ′, %": (12.83, 12.34),
        "γ′ равновесный, ат. %": None,
        "матрица на бесконечности, ат. %": {"NI": 81.26, "AL": 3.13, "CR": 15.61},
        "критический радиус авторов, нм": 0.55,
        "время инкубации, с": (540.0, 120.0),
        "время, ч": (0.167, 0.25, 1, 4, 16, 64, 256, 1024),
        "R, нм": (0.74, 0.75, 0.89, 1.27, 2.1, 2.8, 4.1, 7.7),
        "Nv, 1e24 м⁻³": (0.36, 2.1, 2.5, 3.2, 1.49, 0.49, 0.24, 0.11),
        "доля, %": (0.11, 0.55, 2.33, 5.2, 8.8, 10.0, 13.3, 15.6),
        "матрица по времени, ат. %": {
            "NI": (80.59, 80.73, 80.88, 81.01, 81.10, 81.22, 81.22, 81.16),
            "AL": (5.19, 5.07, 4.75, 3.97, 3.61, 3.45, 3.30, 3.27),
            "CR": (14.22, 14.20, 14.36, 15.02, 15.28, 15.33, 15.47, 15.57),
        },
    },
}

# Показатели степенного закона огрубления, измеренные авторами (пункт 5).
MEASURED_EXPONENTS = {"радиус": (0.29, 0.05), "плотность": (-0.64, 0.06)}
CLASSICAL_EXPONENTS = {"радиус": 1.0/3.0, "плотность": -1.0}
COARSENING_FROM_H = 16.0

OUTPUT_TIMES_H = (1/6, 1/4, 1.0, 4.0, 16.0, 64.0, 256.0, 1024.0)
HORIZON_H = 1024.0


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def write_json(payload: Any, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=float) + "\n",
        encoding="utf-8",
    )
    return path


def read_json(name: str) -> Any:
    return json.loads((OUT / name).read_text("utf-8"))


def free_gib() -> float:
    import psutil

    return psutil.virtual_memory().available / 1024.0**3


# --------------------------------------------------------------------------- #
# Пункт 0. Равновесие
# --------------------------------------------------------------------------- #


def _database() -> tuple[Any, list[str], list[str]]:
    """База приложения с его правками загрузки и список фаз Ni-Al-Cr.

    Путь волны 11 (`study_hn62m_wave11.Context`): все фазы, которые
    `filter_phases` допускает для набора компонентов, минус фазы с моделью
    упорядочения, не строящейся на этом составе.
    """

    from pycalphad import Database
    from pycalphad.core.utils import filter_phases, unpack_species
    import thermogar_database_repair as repair

    db = Database(str(ROOT / DB_REL))
    repair.repair_database(db, database_label=Path(DB_REL).name)
    phases = sorted(filter_phases(db, unpack_species(db, list(COMPONENTS))))
    phases, removed = repair.drop_broken_order_disorder(db, list(COMPONENTS), phases)
    return db, list(phases), sorted(removed)


def _phase_rows(db: Any, result: Any, physical_db: Any) -> dict[str, Any]:
    from thermogar_parallel import _aggregate
    from thermogar_physical import calculate_physical_properties

    fractions, compositions = _aggregate(result, list(COMPONENTS))
    physical = calculate_physical_properties(
        db, result, list(COMPONENTS), TEMPERATURE_K, physical_db
    )
    table = physical.phase_table
    phases: dict[str, Any] = {}
    for name in sorted(fractions):
        row = table[table["Фаза"] == name]
        record: dict[str, Any] = {
            "мольная доля, %": 100.0 * float(fractions[name]),
            "состав, ат. %": {
                element: 100.0 * float(value)
                for element, value in sorted(compositions[name].items())
            },
        }
        if not row.empty:
            first = row.iloc[0]
            for key in (
                "Объёмная доля, %", "Плотность фазы, кг/м³",
                "Молярный объём, см³/моль атомов",
                "Средняя молярная масса, г/моль атомов",
                "Модель плотности", "Статус данных", "Примечание",
            ):
                value = first[key]
                record[key] = (
                    None if value is None or (isinstance(value, float) and not np.isfinite(value))
                    else (float(value) if isinstance(value, (int, float, np.floating)) else str(value))
                )
        phases[name] = record
    return phases


def step_eq(**_ignored: Any) -> None:
    from pycalphad import equilibrium, variables as v
    from thermogar_physical import PhysicalDensityDatabase

    started = time.perf_counter()
    db, phases, removed = _database()
    physical_db = PhysicalDensityDatabase(str(ROOT / PDB_REL))
    log(f"фаз Ni-Al-Cr: {len(phases)}; исключено: {removed or 'нет'}")

    payload: dict[str, Any] = {
        "T, K": TEMPERATURE_K,
        "база": DB_REL,
        "база плотностей": PDB_REL,
        "SHA-256 базы плотностей": physical_db.sha256,
        "фазы полного набора": phases,
        "исключены при сборке": removed,
        "сплавы": {},
    }
    for key, alloy in ALLOYS.items():
        conditions = {v.N: 1.0, v.P: 101325.0, v.T: TEMPERATURE_K}
        conditions.update({v.X(el): x for el, x in alloy["состав, ат. доли"].items()})
        record: dict[str, Any] = {}
        for label, phase_set in (("все фазы", phases), ("FCC_A1 + GAMMA_PRIME", [MATRIX_PHASE, PRECIPITATE_PHASE])):
            for pdens in EQ_PDENS:
                result = equilibrium(db, list(COMPONENTS), phase_set, conditions,
                                     calc_opts={"pdens": pdens})
                rows = _phase_rows(db, result, physical_db)
                record[f"{label}, pdens={pdens}"] = rows
                gp = rows.get(PRECIPITATE_PHASE, {})
                log(f"{key} {label} pdens={pdens}: "
                    + "; ".join(f"{n} {r['мольная доля, %']:.3f} мол.% / "
                                f"{r.get('Объёмная доля, %') or float('nan'):.3f} об.%"
                                for n, r in rows.items()))
                del result
        payload["сплавы"][key] = record
    payload["секунд"] = time.perf_counter() - started
    path = write_json(payload, "eq_873K.json")
    log(f"записано {path}")


# --------------------------------------------------------------------------- #
# Входы KWN
# --------------------------------------------------------------------------- #

# Параметры, которые при объёмном зарождении в kawin не участвуют
# (`setNucleationDensity` берёт для BULK только bulkN0), но обязательны в
# сигнатуре `run_precipitation`. Значения — из штатного вызова
# `tools/test_precipitation_grid.py::_run_demo`.
UNUSED_FOR_BULK = {"grain_size_um": 100.0, "dislocation_density": 5e12, "gb_energy": 0.3}

# Сетка размеров. Выбирается шагом ``estimate`` по оценке зародыша приложения
# до первого прогона и объявляется здесь; после объявления не меняется.
#
# Объявлено до первого прогона KWN по пробной оценке (`estimate_probe.json`):
# наименьший критический радиус по шести случаям — 0,651 нм (A, 18 мДж/м²),
# наименьший радиус зародыша — больше 0,65 нм, предел kawin Rmin — 0,3 нм.
# Ширина класса (10 − 0,1)/400 = 0,02475 нм, в 26 раз меньше наименьшего r*;
# cMin 0,1 нм ниже и зародыша, и Rmin. cMax 10 нм выше измеренного радиуса
# на 1024 ч (8,3 нм у A); дальше kawin расширяет сетку сам. Сетка одна на
# все шесть случаев.
GRID: dict[str, float] = {"cmin_nm": 0.1, "cmax_nm": 10.0, "bins": 400}

EQ_KEY = "все фазы, pdens=500"


def molar_volumes(alloy: str) -> dict[str, Any]:
    """Молярные объёмы фаз из пункта 0: база плотностей приложения, 873 K."""

    rows = read_json("eq_873K.json")["сплавы"][alloy][EQ_KEY]
    payload = {}
    for phase in (MATRIX_PHASE, PRECIPITATE_PHASE):
        row = rows[phase]
        payload[phase] = {
            "молярный объём, см³/моль": float(row["Молярный объём, см³/моль атомов"]),
            "плотность, кг/м³": float(row["Плотность фазы, кг/м³"]),
            "статус": row["Статус данных"],
            "модель плотности": row["Модель плотности"],
            "примечание": row["Примечание"],
            "состав фазы, ат. %": row["состав, ат. %"],
        }
    return payload


def bulk_sites(matrix_vm_cm3: float) -> float:
    """N0 = N_A / Vm: атомных узлов матрицы в кубическом метре."""

    return AVOGADRO / (matrix_vm_cm3 * 1e-6)


def case_id(alloy: str, gamma_mj: float) -> str:
    return f"{'A' if alloy == 'A' else 'B'}_g{gamma_mj:g}".replace(".", "_")


def case_arguments(alloy: str, gamma_mj: float, grid: Mapping[str, float]) -> dict[str, Any]:
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    volumes = molar_volumes(alloy)
    matrix_vm = volumes[MATRIX_PHASE]["молярный объём, см³/моль"]
    precip_vm = volumes[PRECIPITATE_PHASE]["молярный объём, см³/моль"]
    composition = ALLOYS[alloy]["состав, ат. доли"]
    return dict(
        db=object(),
        database_path=ROOT / DB_REL,
        database_label=RELEASE_DATABASE_LABELS["ni"],
        database_key="ni",
        balance="NI",
        composition_text=", ".join(f"{el}={100*x:g}" for el, x in composition.items()),
        units="at",
        matrix_phase=MATRIX_PHASE,
        precipitate_phase=PRECIPITATE_PHASE,
        schedule_mode="isothermal",
        temperature_c=TEMPERATURE_C,
        duration_h=HORIZON_H,
        profile_text="",
        gamma=gamma_mj * 1e-3,
        matrix_vm=matrix_vm,
        precip_vm=precip_vm,
        nucleation_type="BULK",
        bulk_n0=bulk_sites(matrix_vm),
        **UNUSED_FOR_BULK,
        cmin_nm=float(grid["cmin_nm"]),
        cmax_nm=float(grid["cmax_nm"]),
        bins=int(grid["bins"]),
        input_provenance=(
            f"WAVE15_A: {ALLOYS[alloy]['источник']}; межфазная энергия измерена; "
            "Vm — physical_data_v103.pdb при 873 K; N0 = N_A/Vm(FCC_A1)"
        ),
        input_confirmation=True,
    )


class _StopBeforeSolve(Exception):
    pass


def estimate_case(alloy: str, gamma_mj: float, grid: Mapping[str, float]) -> dict[str, Any]:
    """Оценка зародыша приложения и время инкубации kawin по начальному составу.

    Идёт штатный `run_precipitation` до `solve`: проверки BL-32 и BL-22
    выполняются как в расчёте, `solve` заменён исключением только здесь.
    Оценку перехватывает обёртка над `_nucleus_estimates`; на её отдельной
    модели (см. docstring функции) теми же функциями kawin считаются фактор
    Зельдовича, частота присоединения и время инкубации τ = 1/(θ·β·Z²).
    """

    import kawin.precipitation.NucleationRate as nr
    import thermogar_precipitation as precipitation

    captured: dict[str, Any] = {}
    original_estimates = precipitation._nucleus_estimates
    original_solve = precipitation.PrecipitateModel.solve

    def estimates(model, phase, temperatures):
        result = original_estimates(model, phase, temperatures)
        p = model.phaseIndex(phase)
        parameters = model.precipitates[p]
        x = np.squeeze(model.data.composition[0])
        _chem, dgv, _b = nr.volumetricDrivingForce(model.therm, x, TEMPERATURE_K, parameters, removeCache=True)
        rcrit, gcrit = nr.nucleationBarrier(float(np.squeeze(dgv)), parameters)
        z = nr.zeldovich(TEMPERATURE_K, rcrit, parameters)
        beta = nr.betaMulti(model.therm, x, TEMPERATURE_K, rcrit, model.matrix, parameters, removeCache=True)
        tau = nr.incubationTime(beta, z, model.matrix)
        rate = nr.nucleationRate(z, beta, gcrit, TEMPERATURE_K, tau, time=np.inf)
        captured.update({
            "движущая сила, Дж/м³": float(np.squeeze(dgv)),
            "химическая движущая сила, Дж/моль": float(np.squeeze(_chem)),
            "критический радиус kawin, нм": 1e9*float(np.squeeze(rcrit)),
            "барьер, kT": float(np.squeeze(gcrit)) / (1.380649e-23*TEMPERATURE_K),
            "Rmin kawin, нм": 1e9*float(parameters.Rmin),
            "время инкубации τ, с": float(np.squeeze(tau)),
            "стационарная скорость зарождения на узел, 1/с": float(np.squeeze(rate)),
            "стационарная скорость зарождения, 1/(м³·с)": float(np.squeeze(rate)) * float(model.matrix.nucleationSites.bulkN0),
            "оценка приложения": [list(map(float, row)) for row in result],
        })
        return result

    def solve(*_a, **_k):
        raise _StopBeforeSolve()

    precipitation._nucleus_estimates = estimates
    precipitation.PrecipitateModel.solve = solve
    try:
        precipitation.run_precipitation(**case_arguments(alloy, gamma_mj, grid))
    except _StopBeforeSolve:
        captured["проверки до расчёта"] = "пройдены"
    except ValueError as error:
        captured["проверки до расчёта"] = f"отказ: {error}"
    finally:
        precipitation._nucleus_estimates = original_estimates
        precipitation.PrecipitateModel.solve = original_solve
    return captured


def step_estimate(**_ignored: Any) -> None:
    probe = {"cmin_nm": 0.05, "cmax_nm": 5.0, "bins": 1000}
    payload = {}
    for alloy in ALLOYS:
        for gamma in ALLOYS[alloy]["межфазная энергия, мДж/м²"]:
            record = estimate_case(alloy, gamma, probe)
            payload[case_id(alloy, gamma)] = record
            log(f"{alloy} γ={gamma}: " + json.dumps(
                {k: v for k, v in record.items() if k != "оценка приложения"},
                ensure_ascii=False))
    write_json({"пробная сетка": probe, "случаи": payload}, "estimate_probe.json")


def cases() -> list[tuple[str, float]]:
    """Порядок прогонов: центр, затем края погрешности."""

    order = []
    for alloy, data in ALLOYS.items():
        low, centre, high = data["межфазная энергия, мДж/м²"]
        order += [(alloy, centre), (alloy, low), (alloy, high)]
    return order


def step_inputs(**_ignored: Any) -> None:
    """Все входы KWN одним файлом — до первого прогона."""

    probe = read_json("estimate_probe.json")["случаи"]
    payload: dict[str, Any] = {
        "T, K": TEMPERATURE_K,
        "горизонт, ч": HORIZON_H,
        "узлы вывода, ч": list(OUTPUT_TIMES_H),
        "зарождение": "BULK",
        "сетка размеров": GRID,
        "ширина класса, нм": (GRID["cmax_nm"] - GRID["cmin_nm"]) / GRID["bins"],
        "не участвуют при BULK": UNUSED_FOR_BULK,
        "N0": "N0 = N_A / Vm(FCC_A1), N_A = 6,02214076e23 1/моль",
        "сплавы": {},
    }
    for alloy in ALLOYS:
        volumes = molar_volumes(alloy)
        vm = volumes[MATRIX_PHASE]["молярный объём, см³/моль"]
        payload["сплавы"][alloy] = {
            "молярные объёмы": volumes,
            "N0, 1/м³": bulk_sites(vm),
            "случаи": {},
        }
        for gamma in ALLOYS[alloy]["межфазная энергия, мДж/м²"]:
            arguments = case_arguments(alloy, gamma, GRID)
            estimate = probe[case_id(alloy, gamma)]
            payload["сплавы"][alloy]["случаи"][case_id(alloy, gamma)] = {
                "межфазная энергия, Дж/м²": arguments["gamma"],
                "состав": arguments["composition_text"],
                "критический радиус на старте, нм": estimate["критический радиус kawin, нм"],
                "запас сетки r*/ширина": estimate["критический радиус kawin, нм"]
                / payload["ширина класса, нм"],
            }
    write_json(payload, "inputs.json")
    log("входы записаны в inputs.json")


# --------------------------------------------------------------------------- #
# Прогоны KWN, по одному процессу на случай
# --------------------------------------------------------------------------- #


def abort_free_gib() -> float:
    """Аварийный порог модуля волны 12, прочитанный из исходника без импорта."""

    import ast

    tree = ast.parse((TOOLS / "study_hn62m_wave12.py").read_text("utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "E1_ABORT_FREE_GIB" for t in node.targets
        ):
            return float(ast.literal_eval(node.value))
    raise RuntimeError("E1_ABORT_FREE_GIB не найден")


def run_dir(case: str) -> Path:
    return OUT / "runs" / case


def child_run(alloy: str, gamma_mj: float) -> None:
    """Один расчёт штатным `run_precipitation`; выходы — на диск."""

    import thermogar_precipitation as precipitation

    case = case_id(alloy, gamma_mj)
    folder = run_dir(case)
    folder.mkdir(parents=True, exist_ok=True)
    arguments = case_arguments(alloy, gamma_mj, GRID)
    started = time.perf_counter()
    result = precipitation.run_precipitation(**arguments)
    seconds = time.perf_counter() - started
    write = dict(index=False, encoding="utf-8")
    result.kinetics.to_csv(folder / "kinetics.csv", **write)
    result.matrix_composition.to_csv(folder / "matrix.csv", **write)
    result.interface_composition.to_csv(folder / "interface.csv", **write)
    result.psd.to_csv(folder / "psd_final.csv", **write)
    result.quality.to_csv(folder / "quality.csv", **write)
    result.summary.to_csv(folder / "summary.csv", **write)
    result.settings.to_csv(folder / "settings.csv", **write)
    (folder / "provenance.json").write_bytes(result.provenance)
    meta = {
        "случай": case,
        "сплав": alloy,
        "межфазная энергия, мДж/м²": gamma_mj,
        "секунд": seconds,
        "шагов": int(len(result.kinetics)),
        "предупреждения": list(result.warnings),
        "проверки": result.quality.to_dict(orient="records"),
    }
    (folder / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")
    print("CHILD_DONE", json.dumps(meta, ensure_ascii=False), flush=True)


def step_kwn(min_free_gib: float = 3.0, only_case: str | None = None, force: bool = False, **_ignored: Any) -> None:
    import psutil

    abort_gib = abort_free_gib()
    log(f"порог входа {min_free_gib} ГиБ (ключ), аварийный {abort_gib} ГиБ (модуль волны 12)")
    summary_path = OUT / "runs" / "memory.jsonl"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    for alloy, gamma in cases():
        case = case_id(alloy, gamma)
        if only_case and case != only_case:
            continue
        if (run_dir(case) / "run.json").is_file() and not force:
            log(f"{case}: уже посчитан")
            continue
        waited = 0.0
        while free_gib() < min_free_gib:
            if waited > 900:
                raise RuntimeError(f"{case}: свободной памяти меньше {min_free_gib} ГиБ 900 с")
            time.sleep(5)
            waited += 5
        free_start = free_gib()
        log(f"{case}: старт, свободно {free_start:.2f} ГиБ")
        run_dir(case).mkdir(parents=True, exist_ok=True)
        log_file = (run_dir(case) / "child.log.txt").open("w", encoding="utf-8")
        env = dict(os.environ, PYTHONHASHSEED="0")
        process = subprocess.Popen(
            [sys.executable, "-B", "-X", "utf8", str(Path(__file__)), "--child", alloy, str(gamma)],
            stdout=log_file, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT),
        )
        handle = psutil.Process(process.pid)
        record = {"случай": case, "порог входа, ГиБ": min_free_gib, "аварийный порог, ГиБ": abort_gib,
                  "свободно на старте, ГиБ": free_start, "пик рабочего набора, ГиБ": 0.0,
                  "минимум свободной, ГиБ": free_start, "снят": False}
        started = time.perf_counter()
        while process.poll() is None:
            try:
                family = [handle] + handle.children(recursive=True)
                rss = sum(member.memory_info().rss for member in family) / 1024.0**3
            except psutil.Error:
                rss = 0.0
            free = free_gib()
            record["пик рабочего набора, ГиБ"] = max(record["пик рабочего набора, ГиБ"], rss)
            record["минимум свободной, ГиБ"] = min(record["минимум свободной, ГиБ"], free)
            if free < abort_gib:
                record["снят"] = True
                process.kill()
                log(f"{case}: СНЯТ по памяти, свободно {free:.2f} ГиБ")
                break
            time.sleep(2)
        process.wait()
        log_file.close()
        record["exit"] = process.returncode
        record["секунд"] = time.perf_counter() - started
        with summary_path.open("a", encoding="utf-8") as handle_out:
            handle_out.write(json.dumps(record, ensure_ascii=False) + "\n")
        log(f"{case}: exit {process.returncode}, {record['секунд']:.0f} с, "
            f"пик {record['пик рабочего набора, ГиБ']:.2f} ГиБ")
        if process.returncode != 0:
            raise RuntimeError(f"{case}: потомок завершился с кодом {process.returncode}")


# --------------------------------------------------------------------------- #
# Сверка: таблицы, показатели огрубления, графики. Без счёта.
# --------------------------------------------------------------------------- #

QUANTITIES = (
    # ключ, колонка расчёта, множитель к единицам опыта, ключ опыта, подпись
    ("R", "Средний радиус, нм", 1.0, "R, нм", "Средний радиус, нм"),
    ("Nv", "Плотность частиц, 1/м³", 1e-24, "Nv, 1e24 м⁻³", "Плотность частиц, 10²⁴ м⁻³"),
    ("f", "Объёмная доля, %", 1.0, "доля, %", "Объёмная доля γ′, %"),
)


def load_kinetics(case: str):
    import pandas as pd

    return pd.read_csv(run_dir(case) / "kinetics.csv", encoding="utf-8")


def at_times(time_h: np.ndarray, values: np.ndarray, nodes: Sequence[float]) -> np.ndarray:
    """Значение в узле: линейно по логарифму времени между шагами решателя."""

    mask = time_h > 0
    return np.interp(np.log10(nodes), np.log10(time_h[mask]), values[mask],
                     left=np.nan, right=np.nan)


def power_exponent(time_h: np.ndarray, values: np.ndarray, start_h: float) -> dict[str, float]:
    """Наклон log(value) от log(t) на t ≥ start_h: все шаги и четыре узла опыта."""

    mask = (time_h >= start_h) & (values > 0)
    slope_all = float(np.polyfit(np.log10(time_h[mask]), np.log10(values[mask]), 1)[0])
    nodes = [t for t in OUTPUT_TIMES_H if t >= start_h]
    node_values = at_times(time_h, values, nodes)
    slope_nodes = float(np.polyfit(np.log10(nodes), np.log10(node_values), 1)[0])
    return {"по шагам решателя": slope_all, "по узлам опыта": slope_nodes}


def fmt(value: float, digits: int = 3) -> str:
    if value is None or not np.isfinite(value):
        return "—"
    text = f"{value:.{digits}g}"
    if "e" in text:
        mantissa, exponent = text.split("e")
        text = f"{mantissa}·10^{int(exponent)}"
    return text.replace(".", ",")


def step_report(**_ignored: Any) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = OUT / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    probe = read_json("estimate_probe.json")["случаи"]
    eq = read_json("eq_873K.json")["сплавы"]
    lines: list[str] = []
    summary: dict[str, Any] = {}
    for alloy, data in ALLOYS.items():
        low, centre, high = data["межфазная энергия, мДж/м²"]
        order = (centre, low, high)
        runs = {g: load_kinetics(case_id(alloy, g)) for g in order
                if (run_dir(case_id(alloy, g)) / "kinetics.csv").is_file()}
        if centre not in runs:
            log(f"{alloy}: центральный прогон не посчитан, пропуск")
            continue
        meta = {g: json.loads((run_dir(case_id(alloy, g)) / "run.json").read_text("utf-8")) for g in runs}
        nodes = list(data["время, ч"])
        summary[alloy] = {"прогоны": {}, "показатели": {}, "отношения": {}}
        lines.append(f"\n## Сплав {alloy} — {data['название']}\n")
        for g in order:
            if g not in runs:
                continue
            m = meta[g]
            failed = [c["Проверка"] for c in m["проверки"] if c["Статус"] != "пройдена"]
            lines.append(
                f"* γ = {fmt(g)} мДж/м²: шагов {m['шагов']}, {m['секунд']:.0f} с; "
                f"проверки: {'все пройдены' if not failed else 'ошибка — ' + ', '.join(failed)}; "
                f"предупреждений: {len(m['предупреждения'])}"
            )
            summary[alloy]["прогоны"][g] = {"проверки не пройдены": failed, "предупреждения": m["предупреждения"]}
        for key, column, scale, measured_key, label in QUANTITIES:
            measured = np.asarray(data[measured_key], float)
            calc = {g: scale*at_times(runs[g]["Время, ч"].to_numpy(float), runs[g][column].to_numpy(float), nodes)
                    for g in runs}
            ratio = calc[centre] / measured
            band_lo = np.nanmin(np.vstack([calc[g] for g in runs]), axis=0) / measured
            band_hi = np.nanmax(np.vstack([calc[g] for g in runs]), axis=0) / measured
            summary[alloy]["отношения"][key] = {
                "центр": ratio.tolist(), "полоса min": band_lo.tolist(), "полоса max": band_hi.tolist()}
            lines.append(f"\n### {label}\n")
            head = [f"расчёт при {fmt(g)}" for g in order if g in runs]
            lines.append("| t, ч | измерено | " + " | ".join(head) + " | расчёт/опыт при "
                         f"{fmt(centre)} | расчёт/опыт по полосе |")
            lines.append("|---" * (4 + len(head)) + "|")
            for i, t in enumerate(nodes):
                cells = [fmt(calc[g][i]) for g in order if g in runs]
                lines.append(f"| {t:.4g} | {fmt(measured[i])} | " + " | ".join(cells)
                             + f" | {fmt(ratio[i], 2)} | {fmt(band_lo[i], 2)}…{fmt(band_hi[i], 2)} |")
            # график
            fig, ax = plt.subplots(figsize=(6.4, 4.8), dpi=150)
            t_all = {g: runs[g]["Время, ч"].to_numpy(float) for g in runs}
            y_all = {g: scale*runs[g][column].to_numpy(float) for g in runs}
            if low in runs and high in runs:
                grid_t = np.logspace(-2, np.log10(HORIZON_H), 400)
                y_low = at_times(t_all[low], y_all[low], grid_t)
                y_high = at_times(t_all[high], y_all[high], grid_t)
                ax.fill_between(grid_t, np.fmin(y_low, y_high), np.fmax(y_low, y_high),
                                color="#9ec5f4", alpha=0.55, linewidth=0,
                                label=f"расчёт, γ от {fmt(low)} до {fmt(high)} мДж/м²")
            mask = t_all[centre] > 0
            ax.plot(t_all[centre][mask], y_all[centre][mask], color="#2a78d6", linewidth=2,
                    label=f"расчёт, γ = {fmt(centre)} мДж/м²")
            ax.plot(nodes, measured, "o", color="#0b0b0b", markersize=6,
                    label="опыт (погрешность по точкам не передана)")
            if key == "f":
                value, error = data["равновесная доля, %"]
                ax.axhspan(value - error, value + error, color="#52514e", alpha=0.15, linewidth=0)
                ax.axhline(value, color="#52514e", linewidth=1, linestyle="--",
                           label=f"равновесная доля по опыту {fmt(value)} ± {fmt(error)} %")
                calc_eq = eq[alloy][EQ_KEY][PRECIPITATE_PHASE]["Объёмная доля, %"]
                ax.axhline(calc_eq, color="#2a78d6", linewidth=1, linestyle=":",
                           label=f"равновесная доля по базе {fmt(calc_eq)} %")
            ax.set_xscale("log")
            if key == "Nv":
                ax.set_yscale("log")
                # Край полосы Б при 29,5 мДж/м² уходит к 10⁻¹² — ось обрезана,
                # иначе опыт и центр сжимаются в одну линию.
                ax.set_ylim(1e-3, 3e1)
            ax.set_xlim(1e-2, 2e3)
            ax.set_xlabel("Время старения при 600 °C, ч")
            ax.set_ylabel(label)
            ax.set_title(f"Сплав {data['название']}: {label.split(',')[0].lower()}")
            ax.grid(True, which="major", color="#e4e3df", linewidth=0.6)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
            ax.legend(fontsize=7.5, frameon=False, loc="upper center",
                      bbox_to_anchor=(0.5, -0.16), ncol=2)
            fig.tight_layout()
            fig.savefig(figures / f"{'A' if alloy == 'A' else 'B'}_{key}.png")
            plt.close(fig)
        # показатели огрубления (пункт 5)
        lines.append(f"\n### Показатели огрубления на t ≥ {fmt(COARSENING_FROM_H)} ч\n")
        lines.append("| γ, мДж/м² | радиус: по шагам | радиус: по узлам | плотность: по шагам | плотность: по узлам |")
        lines.append("|---|---|---|---|---|")
        for g in order:
            if g not in runs:
                continue
            t = runs[g]["Время, ч"].to_numpy(float)
            er = power_exponent(t, runs[g]["Средний радиус, нм"].to_numpy(float), COARSENING_FROM_H)
            en = power_exponent(t, runs[g]["Плотность частиц, 1/м³"].to_numpy(float), COARSENING_FROM_H)
            summary[alloy]["показатели"][g] = {"радиус": er, "плотность": en}
            lines.append(f"| {fmt(g)} | {fmt(er['по шагам решателя'])} | {fmt(er['по узлам опыта'])} | "
                         f"{fmt(en['по шагам решателя'])} | {fmt(en['по узлам опыта'])} |")
        er = power_exponent(np.asarray(nodes), np.asarray(data["R, нм"]), COARSENING_FROM_H)
        en = power_exponent(np.asarray(nodes), np.asarray(data["Nv, 1e24 м⁻³"]), COARSENING_FROM_H)
        lines.append(f"| опыт этой таблицы, по узлам | — | {fmt(er['по узлам опыта'])} | — | {fmt(en['по узлам опыта'])} |")
        summary[alloy]["показатели опыта по узлам таблицы"] = {"радиус": er, "плотность": en}
        # зародыш и инкубация (пункт 4)
        lines.append("\n### Зародыш и инкубация\n")
        lines.append("| γ, мДж/м² | r* на старте, нм | r* авторов, нм | барьер, kT | τ kawin, с | пик скорости зарождения, ч | пик скорости, 1/(м³·с) |")
        lines.append("|---|---|---|---|---|---|---|")
        for g in order:
            if g not in runs:
                continue
            est = probe[case_id(alloy, g)]
            k = runs[g]
            peak = int(np.nanargmax(k["Скорость зарождения, 1/(м³·с)"].to_numpy(float)))
            lines.append(
                f"| {fmt(g)} | {fmt(est['критический радиус kawin, нм'])} | {fmt(data['критический радиус авторов, нм'])} | "
                f"{fmt(est['барьер, kT'])} | {fmt(est['время инкубации τ, с'])} | "
                f"{fmt(float(k['Время, ч'].iloc[peak]))} | {fmt(float(k['Скорость зарождения, 1/(м³·с)'].iloc[peak]))} |")
        # состав матрицы Б (пункт 3)
        if "матрица по времени, ат. %" in data:
            import pandas as pd

            lines.append("\n### Состав матрицы, ат. %\n")
            lines.append("| t, ч | Ni опыт | Ni расчёт | Al опыт | Al расчёт | Al полоса | Cr опыт | Cr расчёт | Cr полоса |")
            lines.append("|---|---|---|---|---|---|---|---|---|")
            matrices = {g: pd.read_csv(run_dir(case_id(alloy, g)) / "matrix.csv", encoding="utf-8") for g in runs}
            calc = {el: {g: at_times(matrices[g]["Время, ч"].to_numpy(float),
                                     matrices[g][f"{el}, матрица, ат.%"].to_numpy(float), nodes)
                         for g in runs} for el in ("NI", "AL", "CR")}
            measured = data["матрица по времени, ат. %"]
            for i, t in enumerate(nodes):
                row = [f"{t:.4g}".replace(".", ",")]
                for el in ("NI", "AL", "CR"):
                    row += [fmt(measured[el][i], 4), fmt(calc[el][centre][i], 4)]
                    if el != "NI":
                        vals = [calc[el][g][i] for g in runs]
                        row.append(f"{fmt(min(vals), 3)}…{fmt(max(vals), 3)}")
                lines.append("| " + " | ".join(row) + " |")
            final = {el: float(matrices[centre][f"{el}, матрица, ат.%"].iloc[-1]) for el in ("NI", "AL", "CR")}
            inf = data["матрица на бесконечности, ат. %"]
            eqm = eq[alloy][EQ_KEY][MATRIX_PHASE]["состав, ат. %"]
            lines.append(f"| ∞ (опыт) / равновесие базы | {fmt(inf['NI'], 4)} | {fmt(eqm['NI'], 4)} | "
                         f"{fmt(inf['AL'], 3)} | {fmt(eqm['AL'], 3)} | — | {fmt(inf['CR'], 4)} | {fmt(eqm['CR'], 4)} | — |")
            summary[alloy]["матрица на 1024 ч при центре"] = final
    (OUT / "tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(summary, "comparison.json")
    log(f"таблицы: {OUT / 'tables.md'}; графики: {figures}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

STEPS = {"eq": step_eq, "estimate": step_estimate, "inputs": step_inputs, "kwn": step_kwn,
         "report": step_report}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", choices=sorted(STEPS))
    parser.add_argument("--child", nargs=2, metavar=("ALLOY", "GAMMA_MJ"))
    parser.add_argument("--min-free-gib", type=float, default=3.0)
    parser.add_argument("--case")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.child:
        child_run(args.child[0], float(args.child[1]))
        return 0
    if not args.only:
        parser.error("нужен --only или --child")
    STEPS[args.only](min_free_gib=args.min_free_gib, only_case=args.case, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
