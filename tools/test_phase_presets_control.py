#!/usr/bin/env python3
"""Быстрый набор фаз на контрольном сплаве (пункт A1 волны 10).

Приёмочная проверка: на сетке 400…1200 °C с шагом 50 °C множество стабильных
фаз в быстром наборе должно совпадать с множеством в полном, а мольные доли —
до 1e-6. Именно этот тест падал на прежнем ``configs/phase_presets.json``:
ниже 540 °C быстрый набор терял NI2CR с мольной долей 0,80.

Тест долгий (два прогона по 17 точек на десятикомпонентном составе), поэтому
помечен ``slow``.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -X utf8 -m pytest ^
        tools/test_phase_presets_control.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from pycalphad import Database, equilibrium, variables as v
from pycalphad.core.utils import filter_phases, unpack_species

import thermogar_database_repair as repair
from thermogar_release_policy import load_phase_presets, preset_phases

NI_TDB = ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb"

CONTROL_COMPONENTS = (
    "NI", "CR", "MO", "C", "SI", "MN", "S", "NB", "AL", "TI", "FE", "VA",
)
CONTROL_X = {
    "AL": 0.005522, "C": 0.000248, "CR": 0.269357, "FE": 0.005336,
    "MN": 0.005424, "MO": 0.080756, "NB": 0.000385, "S": 0.000372,
    "SI": 0.002122, "TI": 0.001245,
}
GRID_C = tuple(float(400 + 50 * step) for step in range(17))  # 400…1200 °C

PRESENT = 1.0e-6


def _fractions(database: Any, phases: list[str], temperature_c: float) -> dict[str, float]:
    conditions: dict[Any, float] = {
        v.N: 1.0, v.P: 101325.0, v.T: temperature_c + 273.15,
    }
    conditions.update(
        {v.X(element): value for element, value in sorted(CONTROL_X.items())}
    )
    result = equilibrium(
        database, list(CONTROL_COMPONENTS), phases, conditions,
        calc_opts={"pdens": 100},
    )
    names = np.asarray(result.Phase.values, dtype=str).ravel()
    amounts = np.asarray(result.NP.values, dtype=float).ravel()
    aggregated: dict[str, float] = {}
    for name, amount in zip(names, amounts):
        if not name or not np.isfinite(amount) or float(amount) <= PRESENT:
            continue
        aggregated[str(name)] = aggregated.get(str(name), 0.0) + float(amount)
    return aggregated


@pytest.mark.slow
def test_fast_preset_matches_full_set_on_control_alloy() -> None:
    """Быстрый набор не теряет фаз и не смещает доли на контрольном сплаве."""

    if not NI_TDB.is_file():
        pytest.skip(f"Нет базы: {NI_TDB}")
    database = Database(str(NI_TDB))
    repair.repair_database(database, database_label=NI_TDB.name)

    components = list(CONTROL_COMPONENTS)
    all_phases = sorted(filter_phases(database, unpack_species(database, components)))
    all_phases, removed = repair.drop_broken_order_disorder(
        database, components, all_phases
    )
    fast_phases = preset_phases(load_phase_presets(ROOT), "ni", all_phases)
    assert len(fast_phases) < len(all_phases), "Быстрый набор ничего не сузил"

    lost: dict[float, set[str]] = {}
    worst_difference = 0.0
    worst_place = ""
    for temperature_c in GRID_C:
        full = _fractions(database, all_phases, temperature_c)
        fast = _fractions(database, fast_phases, temperature_c)
        missing = set(full) - set(fast)
        if missing:
            lost[temperature_c] = missing
        for phase in set(full) | set(fast):
            difference = abs(full.get(phase, 0.0) - fast.get(phase, 0.0))
            if difference > worst_difference:
                worst_difference = difference
                worst_place = f"{phase} при {temperature_c:.0f} °C"

    assert not lost, (
        "Быстрый набор потерял фазы: "
        + "; ".join(
            f"{temperature:.0f} °C — {', '.join(sorted(names))}"
            for temperature, names in sorted(lost.items())
        )
    )
    assert worst_difference < 1.0e-6, (
        f"Максимальное расхождение мольной доли {worst_difference:.3g} "
        f"({worst_place}) больше 1e-6"
    )
    del removed
