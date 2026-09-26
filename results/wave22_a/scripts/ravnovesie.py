#!/usr/bin/env python3
"""22-А, шаг 2 в: равновесная растворимость C в BCC_A2 рядом с M23C6 при 700 °C.

База — та же, что берёт расчёт: ``thermogar_precipitation._bind_release_database``
(сверка SHA-256 и правки загрузчика над разобранным объектом). Фазы — те же две,
что kawin получает от ``run_precipitation``: ``[BCC_A2, M23C6]``.

Считается двумя путями:

* ``pycalphad.equilibrium`` на двух фазах — глобальное равновесие сплава;
* ``MulticomponentThermodynamics.getEq`` kawin — тот же объект термодинамики,
  что строит ``run_precipitation`` (к выделению добавлен сдвиг kawin
  ``gOffset`` = 1 Дж/моль).

Для каждой ячейки (``vhody.py``) печатается и пишется в JSON: доли фаз, состав
BCC_A2 и M23C6, растворимость C в феррите, предельная доля выделения.

    python -B ravnovesie.py [--out ../data/ravnovesie.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for entry in (ROOT / "app", HERE):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import numpy as np  # noqa: E402
from pycalphad import equilibrium, variables as v  # noqa: E402

import vhody  # noqa: E402


def _pycalphad(db: Any, elements: list[str], x_at: np.ndarray, phases: list[str], temperature_k: float) -> dict[str, Any]:
    conditions = {v.T: temperature_k, v.P: 101325, v.N: 1}
    for element, value in zip(elements[1:], x_at[1:]):
        conditions[v.X(element)] = float(value)
    result = equilibrium(db, elements + ["VA"], phases, conditions, calc_opts={"pdens": 2000})
    names = [str(name) for name in np.squeeze(result.Phase.values)]
    amounts = np.squeeze(result.NP.values)
    compositions = np.squeeze(result.X.values)
    components = [str(c) for c in result.component.values]
    out: dict[str, Any] = {"phases": {}}
    for index, name in enumerate(names):
        if not name:
            continue
        out["phases"].setdefault(name, []).append({
            "NP": float(amounts[index]),
            "X": {c: float(compositions[index, k]) for k, c in enumerate(components)},
        })
    out["GM"] = float(np.squeeze(result.GM.values))
    out["MU"] = {c: float(value) for c, value in zip(components, np.squeeze(result.MU.values))}
    return out


def _kawin(db: Any, elements: list[str], x_at: np.ndarray, phases: list[str], temperature_k: float) -> dict[str, Any]:
    import thermogar_precipitation as tp

    therm, class_label = tp._build_precipitation_thermodynamics(db, elements, phases)
    workspace = therm.getEq(np.asarray(x_at[1:], float), temperature_k, 0, phases[1])
    out: dict[str, Any] = {"class": class_label, "gOffset_J_mol": float(therm.gOffset), "phases": {}}
    for composition_set in workspace.get_composition_sets():
        name = composition_set.phase_record.phase_name
        elements_in = list(composition_set.phase_record.nonvacant_elements)
        out["phases"].setdefault(name, []).append({
            "NP": float(composition_set.NP),
            "X": {e: float(x) for e, x in zip(elements_in, composition_set.X)},
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(HERE.parent / "data" / "ravnovesie.json"))
    args = parser.parse_args()

    import thermogar_precipitation as tp
    from thermogar_release_policy import RELEASE_DATABASE_LABELS, RELEASE_DATABASE_RELATIVE_PATHS

    _key, path, sha256, label, db = tp._bind_release_database(
        "fe", ROOT / RELEASE_DATABASE_RELATIVE_PATHS["fe"], RELEASE_DATABASE_LABELS["fe"]
    )
    report: dict[str, Any] = {"database": str(path.relative_to(ROOT)), "sha256": sha256, "label": label, "cells": {}}
    for cell_name, build in vhody.CELLS.items():
        arguments = build()["arguments"]
        elements, x_at, x_wt = tp._composition_vectors(
            db, arguments["balance"], arguments["composition_text"], arguments["units"]
        )
        phases = [arguments["matrix_phase"], arguments["precipitate_phase"]]
        temperature_k = float(arguments["temperature_c"]) + 273.15
        entry: dict[str, Any] = {
            "composition_text": arguments["composition_text"],
            "units": arguments["units"],
            "elements": elements,
            "x_at": [float(x) for x in x_at],
            "x_wt": [float(x) for x in x_wt],
            "phases": phases,
            "temperature_k": temperature_k,
            "pycalphad": _pycalphad(db, elements, x_at, phases, temperature_k),
            "kawin_getEq": _kawin(db, elements, x_at, phases, temperature_k),
        }
        report["cells"][cell_name] = entry
        for source in ("pycalphad", "kawin_getEq"):
            matrix = entry[source]["phases"].get(phases[0], [{}])[0]
            precipitate = entry[source]["phases"].get(phases[1], [{}])[0]
            x_c_matrix = matrix.get("X", {}).get("C")
            x_c_precipitate = precipitate.get("X", {}).get("C")
            print(
                f"{cell_name:8s} {source:12s} X(C) в {phases[0]} = {x_c_matrix!r}; "
                f"доля {phases[1]} = {precipitate.get('NP')!r}; X(C) в {phases[1]} = {x_c_precipitate!r}; "
                f"X(CR) в {phases[0]} = {matrix.get('X', {}).get('CR')!r}"
            )
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
