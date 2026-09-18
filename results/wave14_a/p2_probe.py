"""14-А, пункт 2: что мешает снять предел.

    p2_probe.py static            — вопросы 2а и 2б: подвижности FCC_A1, фазы γ″/δ/γ′
    p2_probe.py build <N> [<фаза>] — вопрос 2в: MulticomponentThermodynamics на N добавках

База — тем же путём, что ``run_precipitation`` (SHA-256, разбор, правки 0.4.1).
"""

from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import kwn_parts as parts  # noqa: E402

OUT = HERE / "p2"
parts.setup_state(OUT, sys.argv[1])

import numpy as np  # noqa: E402
import thermogar_precipitation as tp  # noqa: E402
from thermogar_diffusion import _phase_mobility_coverage  # noqa: E402

ELEMENTS_718 = ["NI", "FE", "CR", "NB", "MO", "TI", "AL"]
T_K = 750.0 + 273.15


def mobility_records(db, phase: str, element: str) -> list[str]:
    rows = []
    for record in db._parameters.all():
        if record.get("parameter_type") not in ("MQ", "MF", "DQ", "DF"):
            continue
        if str(record.get("phase_name")) != phase:
            continue
        diffusing = str(getattr(record.get("diffusing_species"), "name", "") or "").upper()
        if diffusing != element:
            continue
        constituents = ":".join(
            ",".join(sorted(str(getattr(s, "name", s)) for s in sub)) for sub in record["constituent_array"]
        )
        rows.append(f"{record['parameter_type']}({phase}&{element},{constituents};{record['parameter_order']}) = {record['parameter']}")
    return rows


def static() -> None:
    started = time.perf_counter()
    db = parts.load_database()
    coverage = _phase_mobility_coverage(db)
    fcc = sorted(coverage.get("FCC_A1", set()))
    mob = {}
    for element in ELEMENTS_718:
        rows = mobility_records(db, "FCC_A1", element)
        mob[element] = {"строк MQ/MF/DQ/DF": len(rows), "строки": rows}
    phases = {}
    for name in ("GAMMA_DP", "DELTA", "GAMMA_PRIME"):
        present = name in db.phases
        entry = {"есть в базе": present}
        if present:
            phase = db.phases[name]
            entry["подрешётки"] = [float(v) for v in phase.sublattices]
            entry["конституенты"] = [sorted(str(getattr(s, "name", s)) for s in sub) for sub in phase.constituents]
            entry["model_hints"] = {k: str(v) for k, v in (phase.model_hints or {}).items()}
        phases[name] = entry
    ladder = {}
    for n in range(2, 7):
        elements, x_at, x_wt = parts.composition_vectors_unlimited(db, "NI", parts.ladder_text(n), "wt")
        compatible = tp._compatible_phases(db, elements)
        ladder[str(n)] = {
            "состав, масс. %": parts.ladder_text(n),
            "элементы": elements,
            "мольные доли": [float(v) for v in x_at],
            "кандидаты в матрицу (_matrix_candidates)": tp._matrix_candidates(db, elements),
            "GAMMA_DP совместима": "GAMMA_DP" in compatible,
            "DELTA совместима": "DELTA" in compatible,
            "GAMMA_PRIME совместима": "GAMMA_PRIME" in compatible,
        }
    # Как ведёт себя штатная функция на 5 добавках — дословный отказ.
    try:
        tp._composition_vectors(db, "NI", parts.ladder_text(5), "wt")
        stock = "пропустила"
    except Exception as error:  # noqa: BLE001
        stock = f"{type(error).__name__}: {error}"
    payload = {
        "база": str(parts.DB_PATH.name),
        "элементы базы": sorted(str(e) for e in db.elements),
        "FCC_A1: диффундирующие элементы (_phase_mobility_coverage)": fcc,
        "элементы 718 без подвижности FCC_A1": sorted(set(ELEMENTS_718) - set(fcc)),
        "подвижности FCC_A1 по элементам 718": mob,
        "сообщения о правках базы для 718": tp._database_override_warnings(db, ELEMENTS_718),
        "_matrix_candidates на элементах 718": tp._matrix_candidates(db, ELEMENTS_718),
        "фазы": phases,
        "лестница": ladder,
        "штатная _composition_vectors на 5 добавках": stock,
        "с": round(time.perf_counter() - started, 1),
        "память": parts.mem(),
    }
    parts.write_json(OUT / "static.json", payload)
    print(stock)
    print("FCC_A1 coverage:", fcc)


def build(n: int, phase: str) -> None:
    record: dict = {"добавок": n, "фаза-выделение": phase, "свободно при старте потомка, ГиБ": round(parts.free_gib(), 3)}
    t0 = time.perf_counter()
    db = parts.load_database()
    record["база, с"] = round(time.perf_counter() - t0, 2)
    text = parts.ladder_text(min(n, 6), with_seventh=(n == 7))
    elements, x_at, _ = parts.composition_vectors_unlimited(db, "NI", text, "wt")
    record["состав, масс. %"] = text
    record["элементы"] = elements
    try:
        t1 = time.perf_counter()
        therm, label = tp._build_precipitation_thermodynamics(db, elements, ["FCC_A1", phase])
        record["класс"] = label
        record["сборка, с"] = round(time.perf_counter() - t1, 2)
        t2 = time.perf_counter()
        x = np.asarray(x_at[1:], float)
        dg, xb = therm.getDrivingForce(x, T_K, precPhase=phase, removeCache=True)
        record["движущая сила при 750 °C, Дж/моль"] = float(np.squeeze(dg))
        xb = np.asarray(xb, dtype=object)
        record["состав зародыша, мольные доли добавок"] = (
            None if any(v is None for v in xb.ravel()) else [float(v) for v in xb.ravel()]
        )
        record["движущая сила, с"] = round(time.perf_counter() - t2, 2)
        t3 = time.perf_counter()
        d = therm.getInterdiffusivity(x, T_K)
        d = np.asarray(d, float)
        record["взаимная диффузия FCC_A1, форма"] = list(d.shape)
        record["взаимная диффузия FCC_A1, диагональ, м²/с"] = [float(v) for v in np.diag(np.squeeze(d))]
        record["взаимная диффузия конечна"] = bool(np.all(np.isfinite(d)))
        record["диффузия, с"] = round(time.perf_counter() - t3, 2)
        t4 = time.perf_counter()
        growth = therm.getGrowthAndInterfacialComposition(
            x, T_K, float(np.squeeze(dg)), np.array([1e-9, 2e-9, 5e-9]), np.zeros(3), precPhase=phase, removeCache=True
        )
        record["рост: скорость на 1, 2, 5 нм, м/с"] = (
            None if growth is None else [float(v) for v in np.ravel(growth.growth_rate)]
        )
        record["рост, с"] = round(time.perf_counter() - t4, 2)
        record["исход"] = "собрана"
    except Exception as error:  # noqa: BLE001 — отказ и есть результат
        record["исход"] = "отказ"
        record["отказ дословно"] = f"{type(error).__name__}: {error}"
        record["traceback, хвост"] = traceback.format_exc().strip().splitlines()[-8:]
    record["всего, с"] = round(time.perf_counter() - t0, 2)
    record["память"] = parts.mem()
    parts.write_json(OUT / f"build_{n}_{phase}.json", record)
    print({k: record.get(k) for k in ("добавок", "фаза-выделение", "исход", "отказ дословно", "сборка, с", "движущая сила при 750 °C, Дж/моль")})


def driving_forces(texts: list[str] | None = None) -> None:
    """Выбор фазы для лестницы: движущая сила и оценка r* по ступеням 2…6.

    r* = 2·γ·Vm/ΔG — та же формула, что ``nucleationBarrier`` kawin для сферы;
    γ и Vm — входы пункта 5 отчёта 13-Р2 (0,023 Дж/м², 6,5662724928 см³/моль).
    Ширина класса сетки умолчаний раздела — (10 − 0,2)/80 = 0,1225 нм.
    """

    db = parts.load_database()
    gamma, vm = 0.023, 6.5662724928e-6
    width_nm = (10.0 - 0.2) / 80
    table = []
    cases = [(parts.ladder_text(n), ("GAMMA_PRIME", "GAMMA_DP", "DELTA")) for n in range(2, 7)]
    if texts:
        cases = [(text, ("GAMMA_PRIME",)) for text in texts]
    for text, candidates in cases:
        elements, x_at, _ = parts.composition_vectors_unlimited(db, "NI", text, "wt")
        n = len(elements) - 1
        x = np.asarray(x_at[1:], float)
        for phase in candidates:
            row = {"добавок": n, "состав, масс. %": text, "фаза": phase}
            try:
                therm, _ = tp._build_precipitation_thermodynamics(db, elements, ["FCC_A1", phase])
                dg, _xb = therm.getDrivingForce(x, T_K, precPhase=phase, removeCache=True)
                dg = float(np.squeeze(dg))
                row["ΔG, Дж/моль"] = dg
                if dg > 0:
                    rcrit_nm = 1e9 * 2 * gamma * vm / dg
                    row["r*, нм"] = rcrit_nm
                    row["r* больше ширины класса 0,1225 нм"] = bool(rcrit_nm > width_nm)
            except Exception as error:  # noqa: BLE001
                row["отказ"] = f"{type(error).__name__}: {error}"
            table.append(row)
            print(row, flush=True)
            therm = None
    parts.write_json(OUT / ("driving_forces_pairs.json" if texts else "driving_forces.json"), {"T, °C": 750.0, "ширина класса, нм": width_nm, "строки": table, "память": parts.mem()})


if __name__ == "__main__":
    if sys.argv[1] == "static":
        static()
    elif sys.argv[1] == "df":
        driving_forces(sys.argv[2:] or None)
    else:
        build(int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "GAMMA_DP")
