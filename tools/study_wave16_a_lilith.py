#!/usr/bin/env python3
"""Волна 16, задача 16-А — контрольная таблица солидуса и ликвидуса по маркам «Лилит».

Задание `tasks/WAVE16_A_OPUS.md`, отчёт `tasks/WAVE16_A_REPORT.md`.
Входы — пакет «Лилит» `tasks/lilith_16A/` (марки, составы, их скрипт метода).

Два метода на одних и тех же файлах баз:

* ``ThermoGar`` — путь модуля затвердевания приложения. Функции берутся из
  ``app/ThermoGar_app.py`` исходным текстом (модуль — сценарий Streamlit, он не
  импортируется): ``prepare_calculation``, ``compatible_phases_for_components``,
  ``resolve_solidification_start_temperature``, ``equilibrium_liquidus_c``,
  ``liquidus_bracket_c``, ``equilibrium_solid_fraction_at``; солидус — конец
  ``scheil.simulate_equilibrium_solidification`` с параметрами интерфейса по
  умолчанию (шаг, адаптивное уточнение, ``binary_search_tol`` 0,1 °C).
  Порог признака (решение мастера, остановка 2): ликвидус — ``SOLID_PRESENCE_FLOOR``
  в пространстве имён этих функций; солидус при пороге p — ``bisect_transition_temperature``
  приложения по «доля жидкости > p». При p = 1e-6 в ``T_sol_K`` идёт солидус scheil
  (путь приложения), бисекция — столбцом ``T_sol_bisekciya_K``.
* ``Lilit-skript`` — ``tasks/lilith_16A/metod_solidus_lilit.py`` без правок, отдельным
  процессом; одна марка — один процесс, строка подаётся отфильтрованной копией CSV
  (ключ ``--marki`` режет по запятой, а в именах марок есть запятые).

Fe: варианты с C15_LAVES в наборе — вне штатного пути приложения (там фаза снята
всегда, ``FE_EXCLUDED_PHASES``); плюс опорная строка ``ThermoGar-app`` без неё.

Шаги::

    set PYTHONHASHSEED=0
    set THERMOGAR_STATE_ROOT=D:\\Pets\\ThermoGar\\results\\validation\\wave16_a_state
    .venv-windows\\Scripts\\python.exe -B -X utf8 tools\\study_wave16_a_lilith.py plan
    ... run [--only-marki A,B] [--tier N] [--min-free-gib 3.0] [--min-free-gib-full 5.0]
    ... table          # 16A_thermogar.csv из сохранённых результатов, без счёта

Память: порог входа — ключи ``--min-free-gib`` (3,0) и ``--min-free-gib-full`` (5,0,
полный набор на Ni/Fe); аварийный — ``study_hn62m_wave12.E1_ABORT_FREE_GIB``, читается
из исходника и не меняется. Снятый по памяти вариант ``ThermoGar`` повторяется с
меньшим pdens (200→100→50→25), а не тем же.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import math
import os
import platform
import subprocess
import sys
import threading
import time
import traceback
import warnings
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
APP = ROOT / "app"
PAKET = ROOT / "tasks" / "lilith_16A"
MARKI_CSV = PAKET / "marki_16A.csv"
LILIT_SCRIPT = PAKET / "metod_solidus_lilit.py"
OUT = ROOT / "results" / "wave16_a"
RAW = OUT / "raw"
LOGS = OUT / "logs"
STATE_ROOT_DEFAULT = ROOT / "results" / "validation" / "wave16_a_state"

NE_SCHITAT = ("CuCrZr", "БрХ08", "Copper", "Ti6Al4V", "RS553", "IN738")

# Файлы баз: sha — из вычисления (results/wave16_b/rodoslovnaya_16B.md, раздел 0),
# перед счётом сверяются заново.
BAZY: dict[str, dict[str, str]] = {
    "mc_al_2037": {
        "sistema": "Al", "app_key": "al", "lilit_key": "mc_al", "balance": "AL",
        "fajl": "databases/converted/al/mc_al_v2037.thermogar.tdb",
        "sha": "f02bda0e42ff0733e4b647cbc904643a46c46fc996c57383815ade032a750c45",
    },
    "mc_ni_2036": {
        "sistema": "Ni", "app_key": "ni", "lilit_key": "mc_ni", "balance": "NI",
        "fajl": "databases/converted/mc_ni_v2036.garcalc.tdb",
        "sha": "1dc72c5501eb2d9a1778c5a5622728257572a1dcd0ee218c9b4f9a00e0ad08f8",
    },
    "mc_fe_2062_patch": {
        "sistema": "Fe", "app_key": "fe", "lilit_key": "mc_fe", "balance": "FE",
        "fajl": "databases/converted/fe/mc_fe_v2062.thermogar.tdb",
        "sha": "def6c6862458e879b75cabb32e3bfc93a674f981df7c89e5f0e6e40c246620ed",
    },
    "mc_fe_2062_bez_patcha": {
        "sistema": "Fe", "app_key": "fe", "lilit_key": "mc_fe", "balance": "FE",
        "fajl": "databases/diagnostic/fe/mc_fe_v2062_unpatched.thermogar.tdb",
        "sha": "99b5cd56a52b857521122e93f61baf3caed120d1a37e562902ee6aa12f10692c",
    },
}
BAZY_SISTEMY = {
    "Al": ("mc_al_2037",),
    "Ni": ("mc_ni_2036",),
    "Fe": ("mc_fe_2062_patch", "mc_fe_2062_bez_patcha"),
}

POROGI_NASHI = (1e-6, 1e-4)
POROGI_LILIT = (1e-9, 1e-6, 1e-4)
PDENS_LESENKA = (200, 100, 50, 25)
# Пять марок первой сводки, по одной каждого типа: четыре группы файла «Лилит»
# (kartochka, z26_Al, dobor_Ni, z26_Fe) и строка с отказом слоя по пределам шапки.
PERVYE_PYAT = ("RS320", "В96ц1оч", "INCONEL 600", "40Х10С2М", "17-4 PH")

MEMORY_POLL_S = 1.0
JOB_TIMEOUT_S = 4 * 3600
WAIT_FOR_MEMORY_S = 3600


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_gib() -> float:
    import psutil

    return psutil.virtual_memory().available / 1024.0**3


def abort_free_gib() -> float:
    """Аварийный порог модуля волны 12, прочитанный из исходника без импорта."""

    tree = ast.parse((TOOLS / "study_hn62m_wave12.py").read_text("utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "E1_ABORT_FREE_GIB" for t in node.targets
        ):
            return float(ast.literal_eval(node.value))
    raise RuntimeError("E1_ABORT_FREE_GIB не найден")


# --------------------------------------------------------------------------- #
# Марки
# --------------------------------------------------------------------------- #


def read_marki() -> list[dict[str, str]]:
    with MARKI_CSV.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [row for row in rows if row["marka"] not in NE_SCHITAT]


def sostav_mass(row: dict[str, str]) -> dict[str, float]:
    return {k[2:]: float(v) for k, v in row.items() if k.startswith("w_") and v}


def vne_predelov(row: dict[str, str], lilit_key: str) -> str:
    """Проверка шапки базы кодом слоя «Лилит» (granicy), без расчёта.

    Для mc_fe пределы — из манифеста 2.059 (README «Лилит»: у легирующих они те
    же, что у 2.062).
    """

    sys.path.insert(0, str(PAKET))
    from calphad_layer import granicy as gr, raschet

    res = raschet.proverit_granicy(sostav_mass(row), gr.BAZY[lilit_key])
    if isinstance(res, raschet.Otkaz):
        return f"да: {res.kod} — {res.prichina}"
    return "нет"


# --------------------------------------------------------------------------- #
# Задания
# --------------------------------------------------------------------------- #


def job_id(job: dict[str, Any]) -> str:
    text = json.dumps(
        {k: job[k] for k in ("marka", "baza", "metod", "nabor", "c15", "porogi", "pdens")},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def plan_jobs(marki: list[dict[str, str]]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for row in marki:
        sistema = row["sistema"]
        polnyj_tyazhelyj = sistema in ("Ni", "Fe")
        for baza in BAZY_SISTEMY[sistema]:
            c15 = sistema == "Fe"
            for nabor, pdens in (("bystryj", 50), ("polnyj", 50), ("polnyj", 200)):
                jobs.append({
                    "marka": row["marka"], "baza": baza, "metod": "ThermoGar",
                    "nabor": nabor, "c15": c15, "porogi": list(POROGI_NASHI),
                    "pdens": pdens, "tier": 4 if pdens == 200 else 1,
                    "polnyj_tyazhelyj": nabor == "polnyj" and polnyj_tyazhelyj,
                })
            if baza == "mc_fe_2062_patch":
                jobs.append({
                    "marka": row["marka"], "baza": baza, "metod": "ThermoGar-app",
                    "nabor": "polnyj", "c15": False, "porogi": [1e-6],
                    "pdens": 50, "tier": 1, "polnyj_tyazhelyj": True,
                })
            for nabor in ("sloj", "polnyj"):
                for porog in POROGI_LILIT:
                    jobs.append({
                        "marka": row["marka"], "baza": baza, "metod": "Lilit-skript",
                        "nabor": nabor, "c15": None, "porogi": [porog], "pdens": None,
                        "tier": (1 if porog == 1e-9 else 2) if nabor == "sloj" else 3,
                        "polnyj_tyazhelyj": nabor == "polnyj" and polnyj_tyazhelyj,
                    })
    first = {name: i for i, name in enumerate(PERVYE_PYAT)}
    jobs.sort(key=lambda j: (
        0 if j["marka"] in first else 1,
        first.get(j["marka"], 0) if j["marka"] in first else j["tier"],
        [r["marka"] for r in marki].index(j["marka"]),
    ))
    for job in jobs:
        job["id"] = job_id(job)
    return jobs


def raw_path(job: dict[str, Any]) -> Path:
    return RAW / f"{job['id']}.json"


def job_done(job: dict[str, Any]) -> bool:
    path = raw_path(job)
    if not path.is_file():
        return False
    data = json.loads(path.read_text("utf-8"))
    # Снятый по памяти или не дождавшийся памяти вариант досчитывается заново.
    return data.get("status") not in ("snyat_po_pamyati", "net_pamyati", "timeout")


# --------------------------------------------------------------------------- #
# Потомок ThermoGar: функции приложения из исходного текста
# --------------------------------------------------------------------------- #

APP_NAMES = (
    "SOLIDIFICATION_DEFAULTS", "SOLID_PRESENCE_FLOOR", "LIQUIDUS_TOLERANCE_C",
    "LIQUIDUS_BRACKET_STEP_C", "LIQUIDUS_BRACKET_MARGIN_C", "_SCHEIL_STATE",
    "PROJECT_ROOT", "UNBUILDABLE_PHASES_STATE_KEY",
    "load_scheil", "find_project_root", "normalize", "mole_to_mass", "build_input",
    "filter_for_mode", "available_phase_presets", "compatible_phases_for_components",
    "_remember_unbuildable_phases", "unbuildable_phase_note",
    "unbuildable_order_disorder", "drop_unbuildable_order_disorder",
    "rejected_release_phases", "excluded_phase_message", "prepare_calculation",
    "aggregate_phase_fractions", "resolve_solidification_start_temperature",
    "equilibrium_solid_fraction_at", "equilibrium_liquidus_c", "liquidus_bracket_c",
    "solidification_end_index", "_parse_database_snapshot",
)


def app_namespace() -> dict[str, Any]:
    """Импорты верхнего уровня приложения и нужные определения — его же текстом."""

    for entry in (APP, TOOLS):
        if str(entry) not in sys.path:
            sys.path.insert(0, str(entry))
    source_path = APP / "ThermoGar_app.py"
    tree = ast.parse(source_path.read_text("utf-8"))
    ns: dict[str, Any] = {"__file__": str(source_path), "__name__": "thermogar_app_extract"}
    wanted = set(APP_NAMES)
    header: list[ast.stmt] = []
    definitions: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            header.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "THERMOGAR_PATHS" for t in node.targets
        ):
            header.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted:
            definitions.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id in wanted for t in targets):
                definitions.append(node)
    # Порядок исходника: умолчания аргументов вычисляются при def.
    module = ast.Module(body=header + definitions, type_ignores=[])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        exec(compile(module, str(source_path), "exec"), ns)
    missing = wanted - set(ns)
    if missing:
        raise RuntimeError(f"в приложении не найдены: {sorted(missing)}")
    ns["THERMOGAR_PATHS"].configure_process_environment()
    return ns


def load_db(ns: dict[str, Any], baza: str) -> Any:
    info = BAZY[baza]
    data = (ROOT / info["fajl"]).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if sha != info["sha"]:
        raise RuntimeError(f"{info['fajl']}: sha256 {sha}, ожидался {info['sha']}")
    return ns["_parse_database_snapshot"](sha, sha, data)


def child_thermogar(job: dict[str, Any], out_path: Path) -> None:
    started = time.perf_counter()
    result: dict[str, Any] = {"job": job, "status": "ok", "stroki": []}
    timings: dict[str, float] = {}
    try:
        ns = app_namespace()
        from pycalphad.core.utils import filter_phases, unpack_species

        info = BAZY[job["baza"]]
        key = info["app_key"]
        row = next(r for r in read_marki() if r["marka"] == job["marka"])
        mass = sostav_mass(row)
        balance = info["balance"]
        entered = {el: val for el, val in mass.items() if el != balance}
        t0 = time.perf_counter()
        db = load_db(ns, job["baza"])
        timings["razbor_bazy_s"] = time.perf_counter() - t0

        c15 = bool(job["c15"])
        if c15:
            # Вне штатного пути: шаг effective_release_phases снят (решение мастера 16-А).
            ns["effective_release_phases"] = lambda database_key, phases: list(phases)
        available = sorted(el for el in db.elements if el != "VA")
        components, _, _, _ = ns["build_input"](db, available, entered, "wt", balance)
        all_phases = ns["compatible_phases_for_components"](
            db, key, components, "metastable", ns["PHASE_MODE_ALL"])
        if job["nabor"] == "bystryj":
            selected = ns["preset_phases"](ns["available_phase_presets"](), key, all_phases)
            selected = ns["effective_release_phases"](key, selected)
            if c15 and "C15_LAVES" in all_phases and "C15_LAVES" not in selected:
                selected = sorted(set(selected) | {"C15_LAVES"})
        else:
            selected = list(all_phases)
        components, conditions, overall_x, overall_w, phases = ns["prepare_calculation"](
            db, key, entered, "wt", balance, "metastable", selected)
        compatible = sorted(filter_phases(db, unpack_species(db, components)))
        removed = sorted(set(compatible) - set(ns["filter_for_mode"](compatible, key, "metastable")))
        _, unbuildable = ns["drop_unbuildable_order_disorder"](db, components, compatible)
        result.update({
            "components": components,
            "fazy_v_nabore": list(phases),
            "c15_v_nabore": "C15_LAVES" in phases,
            "snyato_detektorom_pary": sorted(unbuildable),
            "snyato_rezhimom_stali": removed,
        })

        pdens = int(job["pdens"])
        defaults = ns["SOLIDIFICATION_DEFAULTS"][key]
        if key == "fe":
            max_start_c = float(ns["FE_DATABASE_MAX_T_C"])
        else:
            max_start_c = 3000.0

        # Равновесия доли твёрдого запоминаются между порогами: значение в точке
        # от порога не зависит, меняется только решение «твёрдое есть/нет».
        original_solid = ns["equilibrium_solid_fraction_at"]
        memo: dict[tuple[float, int], float] = {}
        counter = {"n": 0}

        def solid_at(db_, comps, phs, conds, temperature_c, pdens_):
            k = (round(float(temperature_c), 6), int(pdens_))
            if k not in memo:
                counter["n"] += 1
                memo[k] = original_solid(db_, comps, phs, conds, temperature_c, pdens_)
            return memo[k]

        ns["equilibrium_solid_fraction_at"] = solid_at

        t0 = time.perf_counter()
        start_k, _check = ns["resolve_solidification_start_temperature"](
            db, components, phases, conditions,
            float(defaults["start_temperature_c"]) + 273.15, True, 50.0,
            max_start_c + 273.15, pdens)
        timings["start_s"] = time.perf_counter() - t0
        result["T_start_K"] = start_k

        scheil_module = ns["load_scheil"]()
        if scheil_module["package"] is None:
            raise RuntimeError(f"scheil не импортирован: {scheil_module['error']}")
        t0 = time.perf_counter()
        scheil_error = ""
        traj = None
        try:
            traj = scheil_module["equilibrium"](
                db, components, phases, conditions, start_k,
                step_temperature=float(defaults["step_temperature_c"]),
                liquid_phase_name="LIQUID", adaptive=True,
                eq_kwargs={"calc_opts": {"pdens": pdens}},
                binary_search_tol=0.1, verbose=False,
            )
        except Exception as error:  # как в приложении: метод не завершён
            scheil_error = f"{type(error).__name__}: {error}"
        timings["scheil_s"] = time.perf_counter() - t0

        T_sol_scheil_c = None
        fazy_scheil: list[str] = []
        if traj is not None:
            import numpy as np

            temps = np.asarray(traj.temperatures, dtype=float)
            end = ns["solidification_end_index"](traj)
            T_sol_scheil_c = float(temps[end]) - 273.15
            result["scheil_converged"] = bool(traj.converged)
            result["scheil_tochek"] = int(len(temps))
            fazy_scheil = sorted(
                name for name, values in traj.cum_phase_amounts.items()
                if len(values) > end and float(values[end]) > 1e-10
            )
            fs = np.asarray(traj.fraction_solid, dtype=float)
            result["scheil_hvost"] = [
                [round(float(t) - 273.15, 4), float(1.0 - f)]
                for t, f in zip(temps[-8:], fs[-8:])
            ]
            result["scheil_dolya_tverdogo_v_konce"] = float(fs[end])
        result["scheil_oshibka"] = scheil_error

        if traj is not None:
            bracket_low_c, bracket_high_c = ns["liquidus_bracket_c"](
                traj, T_sol_scheil_c, start_k - 273.15)
        else:
            bracket_low_c, bracket_high_c = start_k - 273.15 - 100.0, start_k - 273.15

        def liquid_fraction(temperature_c: float) -> float:
            return 1.0 - solid_at(db, components, phases, conditions, temperature_c, pdens)

        def phases_at(temperature_c: float) -> list[str]:
            from pycalphad import equilibrium, variables as v

            conds = {v.N: 1.0, v.P: 101325.0, v.T: float(temperature_c) + 273.15}
            conds.update(conditions)
            eq = equilibrium(db, components, phases, conds, calc_opts={"pdens": pdens})
            return sorted(ns["aggregate_phase_fractions"](eq))

        for porog in job["porogi"]:
            stroka: dict[str, Any] = {"porog": porog}
            t_l0 = time.perf_counter()
            n0 = counter["n"]
            ns["SOLID_PRESENCE_FLOOR"] = float(porog)
            try:
                liq_c = ns["equilibrium_liquidus_c"](
                    db, components, phases, conditions, bracket_low_c, bracket_high_c, pdens)
                stroka["T_liq_K"] = liq_c + 273.15
            except Exception as error:
                liq_c = None
                stroka["otkaz_liq"] = f"{type(error).__name__}: {error}"
            stroka["likvidus_s"] = time.perf_counter() - t_l0
            stroka["likvidus_ravnovesij"] = counter["n"] - n0

            t_b0 = time.perf_counter()
            n0 = counter["n"]
            try:
                stroka.update(solidus_bisection(
                    ns, liquid_fraction, phases_at, traj, T_sol_scheil_c,
                    liq_c if liq_c is not None else bracket_high_c, porog))
            except Exception as error:
                stroka["otkaz_bisekcii"] = f"{type(error).__name__}: {error}"
            stroka["bisekciya_s"] = time.perf_counter() - t_b0
            stroka["bisekciya_ravnovesij"] = counter["n"] - n0

            if porog == 1e-6:
                stroka["kriterij_solidusa"] = (
                    "scheil: LIQUID нет в eq.Phase (порог решателя pycalphad)")
                # Как в приложении: конец траектории — «равновесный солидус»
                # и при converged=False (тогда в сводке «Расчёт завершён: нет»).
                stroka["T_sol_K"] = (
                    T_sol_scheil_c + 273.15 if T_sol_scheil_c is not None else None)
                stroka["fazy_pod_solidusom"] = fazy_scheil
                if stroka["T_sol_K"] is None:
                    stroka["otkaz_sol"] = scheil_error or "scheil не дал солидуса"
            else:
                stroka["kriterij_solidusa"] = f"бисекция: доля жидкости ≤ {porog:g}"
                stroka["T_sol_K"] = stroka.get("T_sol_bisekciya_K")
                stroka["fazy_pod_solidusom"] = stroka.get("fazy_pod_bisekciej", [])
                if stroka["T_sol_K"] is None:
                    stroka["otkaz_sol"] = stroka.get("otkaz_bisekcii", "бисекция не дала солидуса")
            result["stroki"].append(stroka)
        timings["ravnovesij_vsego"] = counter["n"]
    except Exception as error:
        result["status"] = "oshibka"
        result["oshibka"] = f"{type(error).__name__}: {error}"
        result["traceback"] = traceback.format_exc()
    timings["vsego_s"] = time.perf_counter() - started
    result["vremya"] = timings
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), "utf-8")


def solidus_bisection(ns, liquid_fraction, phases_at, traj, T_sol_scheil_c, liq_c, porog):
    """Солидус при пороге p: bisect_transition_temperature по «доля жидкости > p».

    Вилка — по траектории scheil: снизу её конец (жидкости нет), сверху первый
    узел траектории с долей жидкости > p. Оба края проверяются настоящими
    равновесиями и раскрываются шагом приложения (10 °C, не дальше 120 °C), как
    у ``equilibrium_liquidus_c``.
    """

    import numpy as np

    step = float(ns["LIQUIDUS_BRACKET_STEP_C"])
    margin = float(ns["LIQUIDUS_BRACKET_MARGIN_C"])
    upper = None
    if traj is not None:
        temps = np.asarray(traj.temperatures, dtype=float) - 273.15
        fl = np.asarray(traj.fraction_liquid, dtype=float)
        lower = float(T_sol_scheil_c)
        above = [float(t) for t, f in zip(temps, fl) if f > porog and t > lower]
        upper = min(above) if above else float(liq_c)
    else:
        lower = float(liq_c) - step
    upper = min(upper, float(liq_c)) if upper is not None else float(liq_c)

    floor = lower - margin
    while liquid_fraction(lower) > porog:
        lower -= step
        if lower < floor:
            raise ValueError(f"солидус не найден: жидкость > {porog:g} до {floor:.1f} °C")
    ceiling = upper + margin
    while not liquid_fraction(upper) > porog:
        upper += step
        if upper > ceiling:
            raise ValueError(f"солидус не найден: жидкость ≤ {porog:g} до {ceiling:.1f} °C")
    if not lower < upper:
        raise ValueError("вилка солидуса вырождена")
    found = ns["bisect_transition_temperature"](
        lambda t: bool(liquid_fraction(float(t)) > porog), lower, upper, 0.1)
    return {
        "T_sol_bisekciya_K": found.value + 273.15,
        "fazy_pod_bisekciej": phases_at(found.low),
        "bisekciya_vilka_C": [lower, upper],
    }


# --------------------------------------------------------------------------- #
# Родитель: процессы, память, кэш
# --------------------------------------------------------------------------- #


def watch(proc, stop: threading.Event, record: dict[str, Any], abort_gib: float) -> None:
    import psutil

    record.update({"pik_MiB": 0.0, "min_svobodno_GiB": free_gib(), "snyat": False})
    while not stop.is_set():
        try:
            rss = 0
            peak = 0
            for p in [proc] + proc.children(recursive=True):
                info = p.memory_info()
                rss += info.rss
                peak = max(peak, getattr(info, "peak_wset", 0))
            record["pik_MiB"] = max(record["pik_MiB"], rss / 2**20, peak / 2**20)
        except psutil.Error:
            pass
        free = free_gib()
        record["min_svobodno_GiB"] = min(record["min_svobodno_GiB"], free)
        if free < abort_gib and not record["snyat"]:
            record["snyat"] = True
            record["svobodno_pri_snyatii_GiB"] = free
            try:
                for p in proc.children(recursive=True):
                    p.kill()
                proc.kill()
            except psutil.Error:
                pass
        stop.wait(MEMORY_POLL_S)


def run_process(command: list[str], log_path: Path, abort_gib: float) -> dict[str, Any]:
    import psutil

    env = dict(os.environ, PYTHONHASHSEED="0")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as handle:
        popen = subprocess.Popen(command, env=env, cwd=str(ROOT), stdout=handle,
                                 stderr=subprocess.STDOUT)
        record: dict[str, Any] = {"svobodno_do_GiB": free_gib()}
        stop = threading.Event()
        thread = threading.Thread(target=watch, args=(psutil.Process(popen.pid), stop, record,
                                                      abort_gib), daemon=True)
        thread.start()
        try:
            code = popen.wait(timeout=JOB_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            popen.kill()
            code = popen.wait()
            record["timeout"] = True
        stop.set()
        thread.join(timeout=5)
    record["kod"] = code
    record["sekund"] = time.perf_counter() - started
    return record


def wait_for_memory(need_gib: float) -> float | None:
    deadline = time.time() + WAIT_FOR_MEMORY_S
    free = free_gib()
    announced = False
    while free < need_gib:
        if time.time() > deadline:
            return None
        if not announced:
            log(f"ждём память: свободно {free:.2f} ГиБ, нужно {need_gib:.1f}")
            announced = True
        time.sleep(30)
        free = free_gib()
    return free


def run_thermogar_job(job: dict[str, Any], args, abort_gib: float) -> dict[str, Any]:
    pdens_list = [job["pdens"]] + [p for p in PDENS_LESENKA if p < job["pdens"]]
    history: list[dict[str, Any]] = []
    for pdens in pdens_list:
        attempt = dict(job, pdens_fakt=pdens)
        need = args.min_free_gib_full if job["polnyj_tyazhelyj"] else args.min_free_gib
        free = wait_for_memory(need)
        if free is None:
            return {"job": job, "status": "net_pamyati", "popytki": history,
                    "prichina": f"свободно меньше {need:.1f} ГиБ дольше {WAIT_FOR_MEMORY_S} с"}
        child_out = RAW / f"{job['id']}.child.json"
        if child_out.exists():
            child_out.unlink()
        spec = dict(attempt, pdens=pdens)
        command = [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()),
                   "child", "--job", json.dumps(spec, ensure_ascii=False),
                   "--out", str(child_out)]
        record = run_process(command, LOGS / f"{job['id']}_pd{pdens}.log", abort_gib)
        record["pdens"] = pdens
        record["porog_vhoda_GiB"] = need
        history.append(record)
        if record.get("snyat"):
            log(f"  снят по памяти при pdens {pdens}, пик {record['pik_MiB']:.0f} МиБ; "
                f"уменьшаем pdens")
            continue
        if record.get("timeout"):
            return {"job": job, "status": "timeout", "popytki": history}
        if not child_out.is_file():
            tail = (LOGS / f"{job['id']}_pd{pdens}.log").read_text("utf-8", errors="replace")[-3000:]
            return {"job": job, "status": "oshibka", "popytki": history,
                    "oshibka": f"потомок завершился с кодом {record['kod']} без результата",
                    "traceback": tail}
        data = json.loads(child_out.read_text("utf-8"))
        child_out.unlink()
        data["popytki"] = history
        data["pdens_fakt"] = pdens
        data["job"] = job
        return data
    return {"job": job, "status": "snyat_po_pamyati", "popytki": history}


def run_lilit_job(job: dict[str, Any], args, abort_gib: float) -> dict[str, Any]:
    info = BAZY[job["baza"]]
    row = next(r for r in read_marki() if r["marka"] == job["marka"])
    need = args.min_free_gib_full if job["polnyj_tyazhelyj"] else args.min_free_gib
    free = wait_for_memory(need)
    if free is None:
        return {"job": job, "status": "net_pamyati"}
    work = RAW / f"{job['id']}_lilit"
    work.mkdir(parents=True, exist_ok=True)
    one_csv = work / "marka.csv"
    with MARKI_CSV.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        src = [r for r in reader if r["marka"] == row["marka"]]
    with one_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(src)
    vyvod = work / "vyvod.csv"
    if vyvod.exists():
        vyvod.unlink()
    command = [sys.executable, "-X", "utf8", "-W", "default", str(LILIT_SCRIPT),
               "--csv", str(one_csv), "--tdb", f"{info['lilit_key']}={ROOT / info['fajl']}",
               "--porog", repr(job["porogi"][0]), "--nabor", job["nabor"], "--bez-granic",
               "--vyvod", str(vyvod)]
    log_path = LOGS / f"{job['id']}_lilit.log"
    record = run_process(command, log_path, abort_gib)
    record["porog_vhoda_GiB"] = need
    out: dict[str, Any] = {"job": job, "popytki": [record], "komanda": command,
                           "log": log_path.read_text("utf-8", errors="replace")}
    if record.get("snyat"):
        out["status"] = "snyat_po_pamyati_lilit"
    elif record.get("timeout"):
        out["status"] = "timeout"
    elif vyvod.is_file():
        with vyvod.open(encoding="utf-8", newline="") as handle:
            out["stroki"] = list(csv.DictReader(handle))
        out["status"] = "ok"
    else:
        out["status"] = "oshibka"
        out["oshibka"] = f"скрипт завершился с кодом {record['kod']}, вывода нет"
    return out


def command_run(args) -> None:
    os.environ.setdefault("THERMOGAR_STATE_ROOT", str(STATE_ROOT_DEFAULT))
    Path(os.environ["THERMOGAR_STATE_ROOT"]).mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    for baza, info in BAZY.items():
        actual = sha256_file(ROOT / info["fajl"])
        if actual != info["sha"]:
            raise SystemExit(f"{baza}: sha256 {actual} ≠ {info['sha']}")
    abort_gib = abort_free_gib()
    marki = read_marki()
    jobs = plan_jobs(marki)
    if args.only_marki:
        wanted = {m.strip() for m in args.only_marki.split(";") if m.strip()}
        jobs = [j for j in jobs if j["marka"] in wanted]
    if args.tier:
        jobs = [j for j in jobs if j["tier"] <= args.tier]
    if args.metod:
        jobs = [j for j in jobs if j["metod"] in args.metod.split(",")]
    todo = [j for j in jobs if not job_done(j)]
    log(f"заданий {len(jobs)}, из кэша {len(jobs) - len(todo)}, считать {len(todo)}; "
        f"аварийный порог {abort_gib:.1f} ГиБ, вход {args.min_free_gib:.1f} / "
        f"{args.min_free_gib_full:.1f} ГиБ")
    for index, job in enumerate(todo, 1):
        log(f"{index}/{len(todo)} {job['marka']} · {job['baza']} · {job['metod']} · "
            f"{job['nabor']} · {job['porogi']} · pdens {job['pdens']}")
        if job["metod"] == "Lilit-skript":
            data = run_lilit_job(job, args, abort_gib)
        else:
            data = run_thermogar_job(job, args, abort_gib)
        raw_path(job).write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str),
                                 "utf-8")
        pik = max((p.get("pik_MiB", 0) for p in data.get("popytki", [])), default=0)
        sek = sum(p.get("sekund", 0) for p in data.get("popytki", []))
        brief = data.get("status")
        if data.get("stroki"):
            brief += " · " + " ; ".join(
                f"{s.get('T_sol_K')} / {s.get('T_liq_K')}" for s in data["stroki"])
        log(f"   {brief} · {sek:.0f} с · пик {pik:.0f} МиБ")


# --------------------------------------------------------------------------- #
# Таблица
# --------------------------------------------------------------------------- #

COLUMNS = (
    "marka", "klyuch_zamorozki", "gruppa", "sistema", "baza", "fajl_tdb", "sha256_tdb",
    "metod", "nabor", "c15_laves_v_nabore", "porog", "kriterij_solidusa", "pdens",
    "pdens_zaproshen", "T_sol_K", "T_liq_K", "T_sol_bisekciya_K", "T_sol_zamorozka_K",
    "T_liq_zamorozka_K", "vremya_s", "pik_pamyati_MiB", "otkaz", "prichina",
    "vne_predelov_shapki", "chislo_faz_v_nabore", "fazy_v_nabore", "fazy_pod_solidusom",
    "zamechaniya", "job_id",
)


def fnum(value: Any, digits: int = 2) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def build_rows() -> list[dict[str, Any]]:
    marki = {r["marka"]: r for r in read_marki()}
    predely: dict[tuple[str, str], str] = {}
    rows: list[dict[str, Any]] = []
    for job in plan_jobs(list(marki.values())):
        path = raw_path(job)
        if not path.is_file():
            continue
        data = json.loads(path.read_text("utf-8"))
        row = marki[job["marka"]]
        info = BAZY[job["baza"]]
        key = (job["marka"], info["lilit_key"])
        if key not in predely:
            predely[key] = vne_predelov(row, info["lilit_key"])
        popytki = data.get("popytki", [])
        pik = max((p.get("pik_MiB", 0) for p in popytki), default=0)
        base = {
            "marka": job["marka"], "klyuch_zamorozki": row["klyuch_zamorozki"],
            "gruppa": row["gruppa"], "sistema": row["sistema"], "baza": job["baza"],
            "fajl_tdb": info["fajl"], "sha256_tdb": info["sha"], "metod": job["metod"],
            "nabor": job["nabor"], "T_sol_zamorozka_K": row["T_sol_K"],
            "T_liq_zamorozka_K": row["T_liq_K"], "pik_pamyati_MiB": f"{pik:.0f}",
            "vne_predelov_shapki": predely[key], "job_id": job["id"],
        }
        status = data.get("status")
        if job["metod"] == "Lilit-skript":
            base["kriterij_solidusa"] = "каскад свипов NP(LIQUID) (скрипт «Лилит»)"
            sek = sum(p.get("sekund", 0) for p in popytki)
            stroki = data.get("stroki") or []
            if status == "ok" and stroki:
                for s in stroki:
                    out = dict(base)
                    out.update({
                        "porog": job["porogi"][0], "pdens": s.get("pdens", ""),
                        "T_sol_K": s.get("T_sol_K", ""), "T_liq_K": s.get("T_liq_K", ""),
                        "vremya_s": s.get("vremya_s", f"{sek:.1f}"),
                        "otkaz": s.get("otkaz", ""), "prichina": s.get("prichina", ""),
                        "fazy_v_nabore": s.get("nabor_faz", ""),
                        "chislo_faz_v_nabore": len(s.get("nabor_faz", "").split())
                        if s.get("nabor_faz") else "",
                        "fazy_pod_solidusom": s.get("fazy_pod_solidusom", ""),
                        "c15_laves_v_nabore": (
                            "да" if "C15_LAVES" in s.get("nabor_faz", "").split() else "нет")
                        if s.get("nabor_faz") else "",
                        "zamechaniya": s.get("zamechaniya", ""),
                    })
                    rows.append(out)
            else:
                out = dict(base)
                log_text = data.get("log", "")
                tail = log_text.strip().splitlines()[-1] if log_text.strip() else ""
                out.update({
                    "porog": job["porogi"][0], "vremya_s": f"{sek:.1f}",
                    "otkaz": status,
                    "prichina": (data.get("oshibka", "") + (f" | {tail}" if tail else "")).strip(" |"),
                })
                rows.append(out)
            continue

        pdens_fakt = data.get("pdens_fakt", job["pdens"])
        vremya = data.get("vremya", {})
        shared = sum(vremya.get(k, 0) for k in ("razbor_bazy_s", "start_s", "scheil_s"))
        fazy = data.get("fazy_v_nabore", [])
        for porog in job["porogi"]:
            out = dict(base)
            out.update({
                "porog": porog, "pdens": pdens_fakt if status == "ok" or data.get("stroki")
                else "", "pdens_zaproshen": job["pdens"],
                "c15_laves_v_nabore": "да" if data.get("c15_v_nabore") else (
                    "нет" if fazy else ""),
                "chislo_faz_v_nabore": len(fazy) if fazy else "",
                "fazy_v_nabore": " ".join(fazy),
            })
            s = next((x for x in data.get("stroki", []) if float(x["porog"]) == porog), None)
            zam = []
            if data.get("snyato_detektorom_pary"):
                zam.append("детектор пары снял: " + " ".join(data["snyato_detektorom_pary"]))
            if data.get("scheil_oshibka"):
                zam.append("scheil: " + data["scheil_oshibka"])
            if data.get("scheil_converged") is False:
                zam.append("scheil converged=False (в приложении: «Расчёт завершён: нет»), "
                           f"доля твёрдого в конце {data.get('scheil_dolya_tverdogo_v_konce')}")
            if pdens_fakt != job["pdens"]:
                zam.append(f"pdens снижен {job['pdens']}→{pdens_fakt} после снятия по памяти")
            if s is None:
                out.update({"otkaz": status, "prichina": data.get("oshibka") or data.get(
                    "prichina", ""), "vremya_s": fnum(sum(p.get("sekund", 0) for p in popytki), 1)})
            else:
                out.update({
                    "kriterij_solidusa": s.get("kriterij_solidusa", ""),
                    "T_sol_K": fnum(s.get("T_sol_K")), "T_liq_K": fnum(s.get("T_liq_K")),
                    "T_sol_bisekciya_K": fnum(s.get("T_sol_bisekciya_K")),
                    "vremya_s": fnum(shared + s.get("likvidus_s", 0) + s.get("bisekciya_s", 0), 1),
                    "fazy_pod_solidusom": " ".join(s.get("fazy_pod_solidusom", [])),
                })
                reasons = [s[k] for k in ("otkaz_sol", "otkaz_liq") if s.get(k)]
                if reasons:
                    out["otkaz"] = "da"
                    out["prichina"] = " | ".join(reasons)
                if porog == 1e-6 and s.get("otkaz_bisekcii"):
                    zam.append("бисекция 1e-6: " + s["otkaz_bisekcii"])
            out["zamechaniya"] = " | ".join(zam)
            rows.append(out)
    return rows


def command_table(args) -> None:
    rows = build_rows()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "16A_thermogar.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, COLUMNS, quoting=csv.QUOTE_ALL, lineterminator="\r\n",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log(f"{path}: строк {len(rows)}")


def command_plan(args) -> None:
    jobs = plan_jobs(read_marki())
    done = sum(job_done(j) for j in jobs)
    by: dict[str, int] = {}
    for j in jobs:
        by[j["metod"]] = by.get(j["metod"], 0) + 1
    log(f"марок {len(read_marki())}, заданий {len(jobs)} ({by}), готово {done}")


def command_env(args) -> None:
    import importlib.metadata as md

    payload = {
        "python": sys.version, "platform": platform.platform(),
        "packages": {name: md.version(name) for name in (
            "pycalphad", "numpy", "scipy", "symengine", "scheil", "xarray", "psutil")},
        "E1_ABORT_FREE_GIB": abort_free_gib(),
        "sha256": {b: sha256_file(ROOT / i["fajl"]) for b, i in BAZY.items()},
        "calphad_layer": {p.name: sha256_file(p) for p in sorted(
            (PAKET / "calphad_layer").iterdir()) if p.is_file()},
        "metod_solidus_lilit.py": sha256_file(LILIT_SCRIPT),
        "marki_16A.csv": sha256_file(MARKI_CSV),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "okruzhenie.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                        "utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--only-marki", default="", help="через ;")
    run.add_argument("--tier", type=int, default=0)
    run.add_argument("--metod", default="")
    run.add_argument("--min-free-gib", type=float, default=3.0)
    run.add_argument("--min-free-gib-full", type=float, default=5.0)
    child = sub.add_parser("child")
    child.add_argument("--job", required=True)
    child.add_argument("--out", required=True)
    sub.add_parser("table")
    sub.add_parser("plan")
    sub.add_parser("env")
    args = parser.parse_args()
    if args.command == "run":
        command_run(args)
    elif args.command == "child":
        child_thermogar(json.loads(args.job), Path(args.out))
    elif args.command == "table":
        command_table(args)
    elif args.command == "plan":
        command_plan(args)
    elif args.command == "env":
        command_env(args)


if __name__ == "__main__":
    main()
