#!/usr/bin/env python3
"""Волна 15, задача 15-Б — BL-34, неоднозначность подвижности Al в FCC_A1.

Задание `tasks/WAVE15_B_OPUS.md`, отчёт `tasks/WAVE15_B_REPORT.md`.
Повод — пункт «Объяснения не имеет», п. 1 отчёта 15-А: у сплава A начало
выделения идёт в 11–18 раз быстрее опыта, хотя пересыщение по базе меньше
измеренного.

Загрузчик приложения (`thermogar_database_repair.repair_mobility_defaults`)
помечает ключ ``('FCC_A1', 'MQ', 'AL', 0)`` как «умолчание и явная строка
различаются, решение за человеком». Два прочтения этой отметки:

* **первое** (работает сейчас): строка-умолчание ``MQ(FCC_A1&AL,*)`` —
  значение для тех конечных членов первой подрешётки, у которых своей строки
  нет, в том числе для NI. Ni-матрица получает ``-284000 + R*T*LN(7.5E-4)``;
* **второе**: явная строка ``MQ(FCC_A1&AL,AL:*)`` перекрывает умолчание, и
  подвижность Al во всей FCC_A1 берётся как ``-142000 + R*T*LN(1.71E-4)``.

Шаги:

* ``lines`` — дословные строки из обоих файлов и оба разобранных выражения;
* ``diff`` — коэффициент диффузии Al при 600, 750 и 900 °C по обоим прочтениям
  на составе сплава A, рядом — самодиффузия Ni из той же базы;
* ``kwn`` — сплав A волны 15-А (те же входы, та же сетка, gamma = 24 мДж/м²)
  до 1 ч модельного времени вторым прочтением подвижности;
* ``report`` — сверка с 15-А и с опытом на узлах 1/6 и 1/4 ч.

Код приложения не меняется. Второе прочтение ставится только здесь: обёртка
над ``thermogar_database_repair.repair_database`` переписывает выражения уже
разобранной базы в процессе-потомке этого скрипта.

Запуск (интерпретатор — venv основного репозитория):

    set PYTHONHASHSEED=0
    C:\\Users\\gareg\\Desktop\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 ^
        tools\\study_wave15_b_mobility.py --only lines
    ... --only diff
    ... --only kwn --min-free-gib 3.0
    ... --only report

Память. Порог входа — ключ ``--min-free-gib`` (по заданию 3,0 ГиБ). Аварийный
порог по ходу — ``study_hn62m_wave12.E1_ABORT_FREE_GIB``, читается из исходника
и не меняется. Прогон один.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
for entry in (ROOT / "app", TOOLS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import study_wave15_validation as wave15a  # noqa: E402 — входы и измеренное оттуда

OUT = ROOT / "results" / "wave15_b"

ALLOY = "A"
GAMMA_MJ = 24.0
HORIZON_H = 1.0
CASE = "A_g24_reading2"

RUNTIME_DB_REL = "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"
SOURCE_TDB_REL = "databases/original/ni/mc_ni_v2036.tdb"
SOURCE_DDB_REL = "databases/original/ni/mc_ni_v2012.ddb"
PASSPORT_REL = "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb.json"

# Температуры пункта 3.
DIFFUSION_TEMPERATURES_C = (600.0, 750.0, 900.0)

# Узлы сверки пункта 4.
COMPARE_NODES_H = (1 / 6, 1 / 4)


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
# Второе прочтение: подмена выражений в уже разобранной базе
# --------------------------------------------------------------------------- #

# Конечные члены первой подрешётки FCC_A1, у которых своя строка подвижности Al
# в базе есть. Их прочтение не касается — спор идёт только об умолчании.
EXPLICIT_ENDMEMBERS = ("AL", "CO", "CR", "FE")


def _al_mq_records(database: Any):
    table = database._parameters.table(  # noqa: SLF001 — публичного доступа нет
        database._parameters.default_table_name
    )
    rows = []
    for record in table.all():
        if str(record.get("parameter_type", "")) != "MQ":
            continue
        if str(record.get("phase_name", "")) != "FCC_A1":
            continue
        if str(record.get("diffusing_species", "")) != "AL":
            continue
        rows.append(record)
    return table, rows


def apply_second_reading(database: Any) -> dict[str, Any]:
    """Поставить выражение явной строки ``AL:*`` во все умолчаньи конечные члены.

    Вызывается после штатных правок загрузки, то есть уже по материализованным
    строкам: к этому моменту умолчание развёрнуто в отдельную запись на каждый
    непокрытый конечный член первой подрешётки (NI, TI, MO, …). Второе
    прочтение говорит, что явная строка перекрывает умолчание, поэтому во все
    эти записи ставится выражение ``MQ(FCC_A1&AL,AL:*)``.
    """

    table, rows = _al_mq_records(database)
    explicit = None
    for record in rows:
        array = record.get("constituent_array")
        if len(array[0]) == 1 and str(array[0][0]) == "AL":
            explicit = record.get("parameter")
    if explicit is None:
        raise RuntimeError("явная строка MQ(FCC_A1&AL,AL:*) не найдена")

    touched: list[str] = []
    for record in rows:
        array = record.get("constituent_array")
        if len(array[0]) != 1:
            continue  # взаимодействия прочтение не трогает
        name = str(array[0][0])
        if name in EXPLICIT_ENDMEMBERS:
            continue
        table.update({"parameter": explicit}, doc_ids=[int(record.doc_id)])
        touched.append(name)
    return {
        "выражение явной строки": str(explicit),
        "переписанные конечные члены": sorted(touched),
        "переписано записей": len(touched),
    }


def install_second_reading() -> dict[str, Any]:
    """Обернуть ``repair_database`` приложения; app/ при этом не меняется."""

    import thermogar_database_repair as repair

    original = repair.repair_database
    applied: dict[str, Any] = {}

    def patched(database: Any, database_label: str = "") -> dict[str, Any]:
        payload = original(database, database_label=database_label)
        if not getattr(database, "_wave15b_second_reading", False):
            applied.update(apply_second_reading(database))
            setattr(database, "_wave15b_second_reading", True)
        payload["wave15b_second_reading"] = dict(applied)
        return payload

    repair.repair_database = patched
    return applied


# --------------------------------------------------------------------------- #
# Пункт 1. Дословные строки и разобранные выражения
# --------------------------------------------------------------------------- #

def _read_text(path: Path) -> list[str]:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding).splitlines()
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"не прочитан {path}")


def _mobility_lines(path: Path, pattern: str) -> list[dict[str, Any]]:
    lines = _read_text(path)
    found: list[dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        if re.search(pattern, line):
            block = [line]
            index = number  # продолжение параметра до терминатора
            while "!" not in block[-1] and index < len(lines):
                block.append(lines[index])
                index += 1
            found.append({"строка файла": number, "текст": "\n".join(block)})
    return found


def step_lines(**_ignored: Any) -> None:
    payload: dict[str, Any] = {"файлы": {}}
    for rel in (SOURCE_TDB_REL, SOURCE_DDB_REL, RUNTIME_DB_REL):
        path = ROOT / rel
        entries = _mobility_lines(path, r"MQ\(FCC_A1&AL")
        payload["файлы"][rel] = {
            "существует": path.is_file(),
            "байт": path.stat().st_size if path.is_file() else None,
            "строк MQ(FCC_A1&AL": len(entries),
            "строки": entries,
        }
        log(f"{rel}: строк MQ(FCC_A1&AL — {len(entries)}")
    payload["паспорт базы"] = json.loads((ROOT / PASSPORT_REL).read_text("utf-8"))

    from pycalphad import Database
    import thermogar_database_repair as repair

    database = Database(str(ROOT / RUNTIME_DB_REL))
    _table, rows = _al_mq_records(database)
    payload["разобрано до правок загрузки"] = [
        {"составляющие": str(r.get("constituent_array")),
         "порядок": int(r.get("parameter_order", 0) or 0),
         "выражение": str(r.get("parameter"))}
        for r in rows
    ]
    report = repair.repair_mobility_defaults(database, database_label="ni")
    payload["отчёт дедупликации"] = {
        "строка лога": report.log_line(),
        "подозрительные ключи": [list(k) for k in report.suspicious_keys],
        "снятые ключи": [list(k) for k in report.removed_keys],
        "оставленные ключи": [list(k) for k in report.kept_keys],
    }
    _table, rows = _al_mq_records(database)
    payload["разобрано после правок загрузки"] = [
        {"составляющие": str(r.get("constituent_array")),
         "порядок": int(r.get("parameter_order", 0) or 0),
         "выражение": str(r.get("parameter"))}
        for r in rows
    ]
    payload["второе прочтение"] = apply_second_reading(database)
    del database

    # Отметки в остальных базах выпуска.
    from thermogar_release_policy import RELEASE_DATABASE_RELATIVE_PATHS

    other: dict[str, Any] = {}
    for key, rel in RELEASE_DATABASE_RELATIVE_PATHS.items():
        if key == "ni":
            continue
        db_other = Database(str(ROOT / rel))
        rep = repair.repair_mobility_defaults(db_other, database_label=key)
        other[key] = {
            "база": rel,
            "строка лога": rep.log_line(),
            "подозрительные ключи": [list(k) for k in rep.suspicious_keys],
        }
        log(f"{key}: подозрительных ключей {len(rep.suspicious_keys)}")
        del db_other
    payload["отметки в других базах"] = other

    path = write_json(payload, "mobility_lines.json")
    log(f"записано {path}")


# --------------------------------------------------------------------------- #
# Пункт 3. Коэффициент диффузии по обоим прочтениям
# --------------------------------------------------------------------------- #

def _thermodynamics(second_reading: bool):
    from pycalphad import Database
    import thermogar_database_repair as repair
    from kawin.thermo import GeneralThermodynamics

    database = Database(str(ROOT / RUNTIME_DB_REL))
    repair.repair_database(database, database_label="ni")
    applied = apply_second_reading(database) if second_reading else None
    elements = ["NI", "AL", "CR"]
    return GeneralThermodynamics(database, elements, ["FCC_A1"]), elements, applied


def step_diff(**_ignored: Any) -> None:
    composition = wave15a.ALLOYS[ALLOY]["состав, ат. доли"]
    x = [composition["AL"], composition["CR"]]  # порядок — как у elements[1:]
    payload: dict[str, Any] = {
        "база": RUNTIME_DB_REL,
        "фаза": "FCC_A1",
        "состав сплава A, ат. доли": {"NI": 1.0 - sum(x), **composition},
        "температуры, °C": list(DIFFUSION_TEMPERATURES_C),
        "определение": (
            "D = M·R·T, трассерный коэффициент kawin "
            "(GeneralThermodynamics.getTracerDiffusivity) при локальном "
            "равновесии одной FCC_A1 на этом составе"
        ),
        "прочтения": {},
    }
    for tag, second in (("первое (умолчание)", False), ("второе (явная строка)", True)):
        therm, elements, applied = _thermodynamics(second)
        record: dict[str, Any] = {"подмена": applied, "точки": {}}
        for t_c in DIFFUSION_TEMPERATURES_C:
            values = np.atleast_1d(
                therm.getTracerDiffusivity(x, t_c + 273.15, phase="FCC_A1")
            )
            record["точки"][f"{t_c:g}"] = {
                element: float(value) for element, value in zip(elements, values)
            }
            log(f"{tag} {t_c:g} °C: " + ", ".join(
                f"D({e}) = {v:.4g}" for e, v in zip(elements, values)))
        payload["прочтения"][tag] = record
        del therm

    # Эффективные Q и D0 смеси. Все строки MQ линейны по T, поэтому
    # ln D = A/(R·T) + B/R точно, и по двум температурам восстанавливаются
    # Q = −A и D0 = exp(B/R) того полинома Редлиха — Кистера, который
    # получается на этом составе.
    gas_constant = 8.314  # как в kawin.thermo.Mobility.tracer_diffusivity_from_mobility
    for tag, record in payload["прочтения"].items():
        keys = sorted(record["точки"], key=float)
        low, high = keys[0], keys[-1]
        record["Q и D0 смеси"] = {}
        for element in record["точки"][low]:
            t_low = float(low) + 273.15
            t_high = float(high) + 273.15
            d_low = record["точки"][low][element]
            d_high = record["точки"][high][element]
            slope = (np.log(d_high) - np.log(d_low)) / (1.0 / t_high - 1.0 / t_low)
            intercept = np.log(d_low) - slope / t_low
            record["Q и D0 смеси"][element] = {
                "Q, Дж/моль": float(-slope * gas_constant),
                "D0, м²/с": float(np.exp(intercept)),
            }
        log(f"{tag}: " + ", ".join(
            f"{e}: Q = {v['Q, Дж/моль']/1000:.1f} кДж/моль, D0 = {v['D0, м²/с']:.4g} м²/с"
            for e, v in record["Q и D0 смеси"].items()))

    first = payload["прочтения"]["первое (умолчание)"]["точки"]
    second_r = payload["прочтения"]["второе (явная строка)"]["точки"]
    payload["во сколько раз второе прочтение быстрее"] = {
        key: second_r[key]["AL"] / first[key]["AL"] for key in first
    }
    payload["D(Al) / D(Ni) самодиффузия"] = {
        key: {"первое": first[key]["AL"] / first[key]["NI"],
              "второе": second_r[key]["AL"] / second_r[key]["NI"]}
        for key in first
    }
    path = write_json(payload, "diffusion.json")
    log(f"записано {path}")


# --------------------------------------------------------------------------- #
# Пункт 4. Прогон KWN вторым прочтением
# --------------------------------------------------------------------------- #

def run_dir() -> Path:
    return OUT / "runs" / CASE


def child_run() -> None:
    """Один расчёт штатным `run_precipitation` при подменённой подвижности."""

    applied = install_second_reading()
    import thermogar_precipitation as precipitation

    folder = run_dir()
    folder.mkdir(parents=True, exist_ok=True)
    arguments = wave15a.case_arguments(ALLOY, GAMMA_MJ, wave15a.GRID)
    arguments["duration_h"] = HORIZON_H
    arguments["input_provenance"] = (
        arguments["input_provenance"]
        + "; WAVE15_B: подвижность Al в FCC_A1 — второе прочтение "
          "(MQ(FCC_A1&AL,AL:*) вместо умолчания MQ(FCC_A1&AL,*))"
    )
    started = time.perf_counter()
    result = precipitation.run_precipitation(**arguments)
    seconds = time.perf_counter() - started
    write = dict(index=False, encoding="utf-8")
    result.kinetics.to_csv(folder / "kinetics.csv", **write)
    result.matrix_composition.to_csv(folder / "matrix.csv", **write)
    result.quality.to_csv(folder / "quality.csv", **write)
    result.summary.to_csv(folder / "summary.csv", **write)
    result.settings.to_csv(folder / "settings.csv", **write)
    (folder / "provenance.json").write_bytes(result.provenance)
    meta = {
        "случай": CASE,
        "сплав": ALLOY,
        "межфазная энергия, мДж/м²": GAMMA_MJ,
        "горизонт, ч": HORIZON_H,
        "подмена подвижности": applied,
        "секунд": seconds,
        "шагов": int(len(result.kinetics)),
        "предупреждения": list(result.warnings),
        "проверки": result.quality.to_dict(orient="records"),
    }
    (folder / "run.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), "utf-8"
    )
    print("CHILD_DONE", json.dumps(meta, ensure_ascii=False), flush=True)


def step_kwn(min_free_gib: float = 3.0, force: bool = False, **_ignored: Any) -> None:
    import psutil

    abort_gib = wave15a.abort_free_gib()
    log(f"порог входа {min_free_gib} ГиБ (ключ), аварийный {abort_gib} ГиБ (модуль волны 12)")
    if (run_dir() / "run.json").is_file() and not force:
        log(f"{CASE}: уже посчитан")
        return
    waited = 0.0
    while free_gib() < min_free_gib:
        if waited > 900:
            raise RuntimeError(f"{CASE}: свободной памяти меньше {min_free_gib} ГиБ 900 с")
        time.sleep(5)
        waited += 5
    free_start = free_gib()
    log(f"{CASE}: старт, свободно {free_start:.2f} ГиБ")
    run_dir().mkdir(parents=True, exist_ok=True)
    log_file = (run_dir() / "child.log.txt").open("w", encoding="utf-8")
    env = dict(os.environ, PYTHONHASHSEED="0")
    process = subprocess.Popen(
        [sys.executable, "-B", "-X", "utf8", str(Path(__file__)), "--child"],
        stdout=log_file, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT),
    )
    handle = psutil.Process(process.pid)
    record = {"случай": CASE, "порог входа, ГиБ": min_free_gib,
              "аварийный порог, ГиБ": abort_gib, "свободно на старте, ГиБ": free_start,
              "пик рабочего набора, ГиБ": 0.0, "минимум свободной, ГиБ": free_start,
              "снят": False}
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
            log(f"{CASE}: СНЯТ по памяти, свободно {free:.2f} ГиБ")
            break
        time.sleep(2)
    process.wait()
    log_file.close()
    record["exit"] = process.returncode
    record["секунд"] = time.perf_counter() - started
    summary_path = OUT / "runs" / "memory.jsonl"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(record, ensure_ascii=False) + "\n")
    log(f"{CASE}: exit {process.returncode}, {record['секунд']:.0f} с, "
        f"пик {record['пик рабочего набора, ГиБ']:.2f} ГиБ")
    if process.returncode != 0:
        raise RuntimeError(f"{CASE}: потомок завершился с кодом {process.returncode}")


# --------------------------------------------------------------------------- #
# Пункт 4. Сверка
# --------------------------------------------------------------------------- #

def step_report(**_ignored: Any) -> None:
    import pandas as pd

    data = wave15a.ALLOYS[ALLOY]
    nodes = list(COMPARE_NODES_H)
    measured_index = [list(data["время, ч"]).index(t) for t in nodes]

    second = pd.read_csv(run_dir() / "kinetics.csv", encoding="utf-8")
    first_path = wave15a.run_dir(wave15a.case_id(ALLOY, GAMMA_MJ)) / "kinetics.csv"
    first = pd.read_csv(first_path, encoding="utf-8")

    payload: dict[str, Any] = {
        "случай": CASE,
        "прогон 15-А": str(first_path.relative_to(ROOT)),
        "узлы, ч": nodes,
        "величины": {},
    }
    for key, column, scale, measured_key, label in wave15a.QUANTITIES:
        measured = np.asarray([data[measured_key][i] for i in measured_index], float)
        values_first = scale * wave15a.at_times(
            first["Время, ч"].to_numpy(float), first[column].to_numpy(float), nodes)
        values_second = scale * wave15a.at_times(
            second["Время, ч"].to_numpy(float), second[column].to_numpy(float), nodes)
        payload["величины"][key] = {
            "подпись": label,
            "измерено": measured.tolist(),
            "15-А (первое прочтение)": values_first.tolist(),
            "15-Б (второе прочтение)": values_second.tolist(),
            "15-А / опыт": (values_first / measured).tolist(),
            "15-Б / опыт": (values_second / measured).tolist(),
            "15-Б / 15-А": (values_second / values_first).tolist(),
        }
    # Сдвиг по времени: когда каждый прогон набирает одну и ту же долю.
    levels = (0.5, 1.0, 2.0, 3.49)
    payload["время достижения доли, ч"] = {}
    for level in levels:
        row: dict[str, Any] = {}
        for tag, frame in (("15-А", first), ("15-Б", second)):
            time_h = frame["Время, ч"].to_numpy(float)
            fraction = frame["Объёмная доля, %"].to_numpy(float)
            reached = np.flatnonzero(fraction >= level)
            row[tag] = float(time_h[reached[0]]) if reached.size else None
        if row["15-А"] and row["15-Б"]:
            row["во сколько раз 15-Б раньше"] = row["15-А"] / row["15-Б"]
        payload["время достижения доли, ч"][f"{level:g}"] = row
        log(f"доля {level:g} %: 15-А {row['15-А']}, 15-Б {row['15-Б']} ч")

    payload["пик скорости зарождения"] = {}
    for tag, frame in (("15-А", first), ("15-Б", second)):
        rate = frame["Скорость зарождения, 1/(м³·с)"].to_numpy(float)
        index = int(np.nanargmax(rate))
        payload["пик скорости зарождения"][tag] = {
            "время, ч": float(frame["Время, ч"].to_numpy(float)[index]),
            "скорость, 1/(м³·с)": float(rate[index]),
        }
    log("пик скорости зарождения: " + json.dumps(
        payload["пик скорости зарождения"], ensure_ascii=False))

    meta = json.loads((run_dir() / "run.json").read_text("utf-8"))
    payload["прогон"] = {
        "шагов": meta["шагов"], "секунд": meta["секунд"],
        "предупреждения": meta["предупреждения"], "проверки": meta["проверки"],
        "подмена подвижности": meta["подмена подвижности"],
    }
    path = write_json(payload, "comparison.json")
    log(f"записано {path}")
    for key, block in payload["величины"].items():
        for i, t in enumerate(nodes):
            log(f"{block['подпись']} t={t:.4g} ч: опыт {block['измерено'][i]:.4g}; "
                f"15-А {block['15-А (первое прочтение)'][i]:.4g} "
                f"(x{block['15-А / опыт'][i]:.3g}); "
                f"15-Б {block['15-Б (второе прочтение)'][i]:.4g} "
                f"(x{block['15-Б / опыт'][i]:.3g})")


STEPS = {"lines": step_lines, "diff": step_diff, "kwn": step_kwn, "report": step_report}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", action="store_true", help="служебный режим потомка")
    parser.add_argument("--only", choices=sorted(STEPS), action="append")
    parser.add_argument("--min-free-gib", type=float, default=3.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.child:
        child_run()
        return
    for name in (args.only or list(STEPS)):
        log(f"шаг {name}")
        STEPS[name](min_free_gib=args.min_free_gib, force=args.force)


if __name__ == "__main__":
    main()
