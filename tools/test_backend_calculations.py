#!/usr/bin/env python3
"""Backend calculation matrix for ThermoGar: 7 sections x 3 databases (Ni / Al / Fe).

Purpose (wave 1C, foundation for stage E3): answer, without the Streamlit UI,
which calculation of every application section actually runs on the project's own
databases for nickel, aluminium and steel, how long it takes, and where the
result is blocked by the database, by the library or by a hard reject in the
application code.

Two levels are covered, as required by the task:

* level (a) -- direct pycalphad / scheil / kawin calls on the project databases,
  i.e. what the application does under the hood;
* level (b) -- public functions of the importable modules (``thermogar_*``).
  ``app/ThermoGar_app.py`` itself is a top-level Streamlit script and cannot be
  imported, so it is never touched here. Modules that import ``streamlit`` are
  imported (that works in bare mode), but no Streamlit session, widget or
  ``AppTest`` is used.

Product rule: the phase ``C15_LAVES`` is always removed from the Fe phase list.

Expected numbers below are NOT reference physics. They are regression anchors
measured on this machine on 2026-09-02 with the versions recorded by
``TESTS_BASELINE.md`` (pycalphad 0.11.2, scheil 0.3.0, kawin 0.5.0). Every
tolerance is deliberately wide; the point is to detect that a calculation stopped
working, not to qualify a material.

Run:
    <root>/.venv-windows/Scripts/python.exe -m pytest tools/test_backend_calculations.py -v -m "not slow"
    <root>/.venv-windows/Scripts/python.exe -m pytest tools/test_backend_calculations.py -v -m slow

Timings and key numbers of every test are appended to a JSON file so that
``tools/backend_reference.md`` can be regenerated; the destination is taken from
the environment variable ``THERMOGAR_BACKEND_REPORT`` and defaults to
``<temp>/thermogar_backend_reference.json``.
"""

from __future__ import annotations

import atexit
import json
import os
import sys
import tempfile
import time
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from pycalphad import Database, calculate, equilibrium, variables as v
from pycalphad.core.utils import filter_phases, unpack_species

DB_KEYS = ("ni", "al", "fe")

# Fe product rule: C15_LAVES never participates in a calculation.
FE_EXCLUDED_PHASES = frozenset({"C15_LAVES"})

DEFAULT_TIMEOUT = 120
SLOW_TIMEOUT = 600

# --------------------------------------------------------------------------- #
# Cases
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Case:
    """One database plus the alloy the whole matrix is measured on."""

    key: str
    relative_path: str
    label: str
    balance: str
    components: tuple[str, ...]
    composition_pct: dict[str, float]
    units: str
    temperature_c: float
    # matrix phase names accepted at ``temperature_c``; several names appear
    # because pycalphad's ``filter_phases`` keeps the ordered half of an
    # order/disorder pair and drops the disordered half.
    matrix_phases: frozenset[str]
    liquidus_window_k: tuple[float, float]
    scan_temperatures_c: tuple[float, ...]
    scan_element: str
    scan_mole_fractions: tuple[float, ...]
    binary_components: tuple[str, ...]
    binary_element: str
    binary_x: tuple[float, float, float]
    binary_t: tuple[float, float, float]
    isopleth_components: tuple[str, ...]
    isopleth_element: str
    isopleth_x: tuple[float, float, float]
    isopleth_fixed: dict[str, float]
    isopleth_t: tuple[float, float, float]
    ternary_components: tuple[str, ...]
    ternary_temperature_k: float
    map_components: tuple[str, ...]
    map_axes: tuple[tuple[str, float, float], tuple[str, float, float]]
    map_temperature_k: float
    map_target_phase: str
    solidification_scan_k: tuple[float, float]
    scheil_start_k: float
    energy_pair: tuple[str, str]
    t0_pair: tuple[str, str]
    t0_window_k: tuple[float, float]
    t0_expected_k: float
    diffusion_phase: str
    diffusion_elements: tuple[str, ...]
    diffusion_left: str
    diffusion_right: str
    diffusion_temperature_c: float
    diffusion_left_x: tuple[float, ...]
    diffusion_right_x: tuple[float, ...]
    kwn_matrix: str
    kwn_precipitate: str
    kwn_temperature_c: float
    kwn_composition_pct: dict[str, float]
    kwn_units: str
    kwn_solutes: tuple[str, ...]
    kwn_solute_x: tuple[float, ...]
    kwn_gamma: float
    kwn_molar_volume_cm3: float
    kwn_size_nm: tuple[float, float]
    elastic_rows: tuple[dict[str, Any], ...] = field(default=())


CASES: dict[str, Case] = {
    "ni": Case(
        key="ni",
        relative_path="databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
        label="Никелевые сплавы — mc_ni 2.036",
        balance="NI",
        components=("NI", "AL", "VA"),
        composition_pct={"AL": 15.0},
        units="at",
        temperature_c=700.0,
        matrix_phases=frozenset({"FCC_A1"}),
        liquidus_window_k=(1698.0, 1723.0),
        scan_temperatures_c=(600.0, 700.0, 800.0, 900.0, 1000.0),
        scan_element="AL",
        scan_mole_fractions=(0.05, 0.10, 0.15, 0.20, 0.25),
        binary_components=("AL", "NI", "VA"),
        binary_element="AL",
        binary_x=(0.0, 1.0, 0.05),
        binary_t=(900.0, 2000.0, 50.0),
        isopleth_components=("NI", "AL", "CR", "VA"),
        isopleth_element="AL",
        isopleth_x=(0.0, 0.30, 0.02),
        isopleth_fixed={"CR": 0.08},
        isopleth_t=(900.0, 1900.0, 50.0),
        ternary_components=("AL", "CR", "NI", "VA"),
        ternary_temperature_k=1273.15,
        map_components=("NI", "AL", "CR", "VA"),
        map_axes=(("AL", 0.05, 0.20), ("CR", 0.02, 0.12)),
        map_temperature_k=1273.15,
        map_target_phase="GAMMA_PRIME",
        solidification_scan_k=(1750.0, 1600.0),
        scheil_start_k=1750.0,
        energy_pair=("FCC_A1", "GAMMA_PRIME"),
        t0_pair=("FCC_A1", "LIQUID"),
        t0_window_k=(1500.0, 1900.0),
        t0_expected_k=1701.1,
        diffusion_phase="FCC_A1",
        diffusion_elements=("NI", "AL", "CR"),
        diffusion_left="AL=10, CR=5",
        diffusion_right="AL=20, CR=9",
        diffusion_temperature_c=1200.0,
        diffusion_left_x=(0.10, 0.05),
        diffusion_right_x=(0.20, 0.09),
        kwn_matrix="FCC_A1",
        kwn_precipitate="GAMMA_PRIME",
        kwn_temperature_c=800.0,
        # KWN uses the project's own qualified gamma/gamma-prime preset
        # (PRESET_NI, Ni-9.8Al-8.3Cr at.%); the binary Ni-15Al of the rest of
        # the matrix has no KWN interface-energy / molar-volume parameters here.
        kwn_composition_pct={"AL": 9.8, "CR": 8.3},
        kwn_units="at",
        kwn_solutes=("AL", "CR"),
        kwn_solute_x=(0.098, 0.083),
        kwn_gamma=0.023,
        kwn_molar_volume_cm3=6.5662724928,
        kwn_size_nm=(0.2, 5.0),
        elastic_rows=(
            {"phase": "FCC_A1", "volume_fraction": 0.7, "bulk_gpa": 180.0, "shear_gpa": 80.0},
            {"phase": "GAMMA_PRIME", "volume_fraction": 0.3, "bulk_gpa": 175.0, "shear_gpa": 85.0},
        ),
    ),
    "al": Case(
        key="al",
        relative_path="databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb",
        label="Алюминиевые сплавы — mc_al 2.037",
        balance="AL",
        components=("AL", "CU", "MG", "VA"),
        composition_pct={"CU": 4.0, "MG": 1.0},
        units="wt",
        temperature_c=500.0,
        # GP_MAT is the ordered counterpart of FCC_A1 in mc_al 2.037; pycalphad
        # keeps GP_MAT and drops FCC_A1 from the active phase list.
        matrix_phases=frozenset({"GP_MAT", "FCC_A1"}),
        liquidus_window_k=(898.0, 923.0),
        scan_temperatures_c=(300.0, 400.0, 500.0, 550.0, 600.0),
        scan_element="CU",
        scan_mole_fractions=(0.005, 0.010, 0.017, 0.024, 0.030),
        binary_components=("AL", "CU", "VA"),
        binary_element="CU",
        binary_x=(0.0, 0.5, 0.05),
        binary_t=(600.0, 1400.0, 50.0),
        isopleth_components=("AL", "CU", "MG", "VA"),
        isopleth_element="CU",
        isopleth_x=(0.0, 0.10, 0.01),
        isopleth_fixed={"MG": 0.0113},
        isopleth_t=(600.0, 1000.0, 25.0),
        ternary_components=("AL", "CU", "MG", "VA"),
        ternary_temperature_k=773.15,
        map_components=("AL", "CU", "MG", "VA"),
        map_axes=(("CU", 0.005, 0.03), ("MG", 0.002, 0.02)),
        map_temperature_k=773.15,
        map_target_phase="THETA_AL2CU",
        solidification_scan_k=(950.0, 850.0),
        scheil_start_k=950.0,
        energy_pair=("GP_MAT", "THETA_AL2CU"),
        t0_pair=("GP_MAT", "LIQUID"),
        t0_window_k=(800.0, 1100.0),
        t0_expected_k=899.3,
        diffusion_phase="FCC_A1",
        diffusion_elements=("AL", "CU", "MG"),
        diffusion_left="CU=1, MG=1",
        diffusion_right="CU=5, MG=1",
        diffusion_temperature_c=500.0,
        diffusion_left_x=(0.0043, 0.0111),
        diffusion_right_x=(0.0218, 0.0111),
        kwn_matrix="FCC_A1",
        kwn_precipitate="THETA_AL2CU",
        kwn_temperature_c=200.0,
        kwn_composition_pct={"CU": 4.0, "MG": 1.0},
        kwn_units="wt",
        kwn_solutes=("CU", "MG"),
        kwn_solute_x=(0.0174, 0.0113),
        kwn_gamma=0.15,
        kwn_molar_volume_cm3=10.0,
        kwn_size_nm=(0.2, 5.0),
        elastic_rows=(
            {"phase": "GP_MAT", "volume_fraction": 0.98, "bulk_gpa": 76.0, "shear_gpa": 26.0},
            {"phase": "THETA_AL2CU", "volume_fraction": 0.02, "bulk_gpa": 110.0, "shear_gpa": 45.0},
        ),
    ),
    "fe": Case(
        key="fe",
        relative_path="databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb",
        label="Стали и Fe-сплавы — mc_fe 2.062",
        balance="FE",
        components=("FE", "C", "CR", "NI", "VA"),
        composition_pct={"C": 0.2, "CR": 11.5, "NI": 0.7},
        units="wt",
        temperature_c=700.0,
        # BCC_B2 is the ordered counterpart of BCC_A2 in mc_fe 2.062; pycalphad
        # keeps BCC_B2 and drops BCC_A2 from the active phase list.
        matrix_phases=frozenset({"BCC_B2", "BCC_A2", "FCC_A1"}),
        liquidus_window_k=(1773.0, 1798.0),
        scan_temperatures_c=(500.0, 600.0, 700.0, 800.0, 900.0),
        scan_element="C",
        scan_mole_fractions=(0.002, 0.005, 0.009, 0.015, 0.020),
        binary_components=("FE", "C", "VA"),
        binary_element="C",
        binary_x=(0.0, 0.25, 0.02),
        binary_t=(900.0, 2000.0, 50.0),
        isopleth_components=("FE", "C", "CR", "NI", "VA"),
        isopleth_element="C",
        isopleth_x=(0.0, 0.05, 0.005),
        isopleth_fixed={"CR": 0.1216, "NI": 0.00656},
        isopleth_t=(900.0, 1900.0, 50.0),
        ternary_components=("FE", "CR", "C", "VA"),
        ternary_temperature_k=1273.15,
        # Ni is dropped from the map system on purpose: both map axes are
        # composition axes, so a fourth element would leave a free degree of
        # freedom and pycalphad refuses the point.
        map_components=("FE", "C", "CR", "VA"),
        map_axes=(("C", 0.002, 0.02), ("CR", 0.05, 0.15)),
        map_temperature_k=973.15,
        map_target_phase="M23C6",
        solidification_scan_k=(1820.0, 1700.0),
        scheil_start_k=1820.0,
        energy_pair=("BCC_B2", "FCC_A1"),
        t0_pair=("BCC_B2", "FCC_A1"),
        t0_window_k=(900.0, 1000.0),
        t0_expected_k=956.4,
        # BCC_A2 and FCC_A1 are the only Fe phases with mobility data.
        diffusion_phase="FCC_A1",
        diffusion_elements=("FE", "C", "CR"),
        diffusion_left="C=0.1, CR=8",
        diffusion_right="C=0.3, CR=14",
        diffusion_temperature_c=900.0,
        diffusion_left_x=(0.005, 0.10),
        diffusion_right_x=(0.010, 0.14),
        kwn_matrix="BCC_A2",
        kwn_precipitate="M23C6",
        kwn_temperature_c=700.0,
        kwn_composition_pct={"C": 0.2, "CR": 11.5},
        kwn_units="wt",
        kwn_solutes=("C", "CR"),
        kwn_solute_x=(0.0092, 0.1216),
        kwn_gamma=0.3,
        kwn_molar_volume_cm3=7.09,
        kwn_size_nm=(0.5, 20.0),
        elastic_rows=(
            {"phase": "BCC_B2", "volume_fraction": 0.95, "bulk_gpa": 170.0, "shear_gpa": 82.0},
            {"phase": "M23C6", "volume_fraction": 0.05, "bulk_gpa": 260.0, "shear_gpa": 130.0},
        ),
    ),
}

# --------------------------------------------------------------------------- #
# Measurement log
# --------------------------------------------------------------------------- #

_RECORDS: list[dict[str, Any]] = []


def _report_path() -> Path:
    override = os.environ.get("THERMOGAR_BACKEND_REPORT")
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / "thermogar_backend_reference.json"


def _flush_records() -> None:
    if not _RECORDS:
        return
    path = _report_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_RECORDS, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except OSError:
        pass


atexit.register(_flush_records)


@contextmanager
def measure(section: str, cell: str, db_key: str) -> Iterator[dict[str, Any]]:
    """Time one matrix cell and store its key numbers, whatever the outcome."""

    entry: dict[str, Any] = {
        "section": section,
        "cell": cell,
        "db": db_key,
        "status": "FAIL",
        "error": "",
        "numbers": {},
        "seconds": None,
    }
    _RECORDS.append(entry)
    started = time.perf_counter()
    try:
        yield entry["numbers"]
    except BaseException as error:  # noqa: BLE001 - the outcome is the payload
        entry["status"] = type(error).__name__
        entry["error"] = str(error).strip().replace("\n", " ")[:400]
        raise
    else:
        entry["status"] = "PASS"
    finally:
        entry["seconds"] = round(time.perf_counter() - started, 2)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

_DB_CACHE: dict[str, Database] = {}


def database_path(case: Case) -> Path:
    path = ROOT / case.relative_path
    if not path.is_file():
        pytest.skip(f"База {case.key} не найдена: {path}")
    return path


def load_database(case: Case) -> Database:
    """Parse a TDB once per session -- parsing costs 3-7 s per database."""

    if case.key not in _DB_CACHE:
        _DB_CACHE[case.key] = Database(str(database_path(case)))
    return _DB_CACHE[case.key]


def effective_phases(db: Database, db_key: str, components: tuple[str, ...]) -> list[str]:
    """Active phases for the components, with the Fe C15_LAVES rule applied."""

    phases = set(filter_phases(db, unpack_species(db, list(components))))
    if db_key == "fe":
        phases -= FE_EXCLUDED_PHASES
    return sorted(phases)


def mole_fractions(db: Database, case: Case) -> dict[str, float]:
    """Alloy composition as mole fractions, wt.% converted via equilibrium_core."""

    percent = dict(case.composition_pct)
    percent[case.balance] = 100.0 - sum(case.composition_pct.values())
    elements = sorted(percent)
    if case.units != "wt":
        return {element: percent[element] / 100.0 for element in elements}

    from thermogar_equilibrium_core import mass_to_mole_fractions

    mass = tuple((element, percent[element] / 100.0) for element in elements)
    masses = tuple((element, float(db.refstates[element]["mass"])) for element in elements)
    return {element: value for element, value in mass_to_mole_fractions(mass, masses)}


def composition_conditions(db: Database, case: Case) -> dict[Any, float]:
    fractions = mole_fractions(db, case)
    return {
        v.X(element): fractions[element]
        for element in sorted(fractions)
        if element != case.balance
    }


def phase_fractions(eq: Any) -> dict[str, float]:
    """Aggregate NP over composition sets, exactly like the application does."""

    names = np.asarray(eq.Phase.values, dtype=str).ravel()
    amounts = np.asarray(eq.NP.values, dtype=float).ravel()
    aggregate: dict[str, float] = {}
    for name, amount in zip(names, amounts):
        if not name or amount != amount:  # noqa: PLR0124 - NaN filter
            continue
        aggregate[name] = aggregate.get(name, 0.0) + float(amount)
    return {name: value for name, value in aggregate.items() if value > 1e-9}


def solve_point(
    db: Database,
    case: Case,
    phases: list[str],
    temperature_k: float,
    overrides: dict[Any, float] | None = None,
    pdens: int = 100,
) -> dict[str, float]:
    conditions: dict[Any, float] = {v.N: 1.0, v.P: 101325.0, v.T: float(temperature_k)}
    conditions.update(composition_conditions(db, case))
    if overrides:
        conditions.update(overrides)
    return phase_fractions(
        equilibrium(db, list(case.components), phases, conditions, calc_opts={"pdens": pdens})
    )


def top_phase(fractions: dict[str, float]) -> str:
    return max(fractions, key=fractions.get) if fractions else ""


@pytest.fixture(scope="session", params=DB_KEYS, ids=DB_KEYS)
def db_key(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture(scope="session")
def case(db_key: str) -> Case:
    return CASES[db_key]


@pytest.fixture(scope="session")
def db(case: Case) -> Database:
    return load_database(case)


@pytest.fixture(scope="session")
def phases(db: Database, case: Case) -> list[str]:
    return effective_phases(db, case.key, case.components)


# --------------------------------------------------------------------------- #
# Section 0: database contract (phase lists, C15_LAVES rule)
# --------------------------------------------------------------------------- #


@pytest.mark.timeout(DEFAULT_TIMEOUT)
def test_phase_list_and_c15_rule(db: Database, case: Case, phases: list[str]) -> None:
    """The active phase list is non-empty and Fe never carries C15_LAVES."""

    with measure("База", "список фаз", case.key) as numbers:
        unfiltered = sorted(filter_phases(db, unpack_species(db, list(case.components))))
        numbers["фаз в базе"] = len(db.phases)
        numbers["фаз после filter_phases"] = len(unfiltered)
        numbers["фаз в расчёте"] = len(phases)
        numbers["C15_LAVES в базе"] = "C15_LAVES" in db.phases
        numbers["C15_LAVES отфильтрована"] = (
            "C15_LAVES" in unfiltered and "C15_LAVES" not in phases
        )
        assert phases, "Пустой список фаз"
        assert "LIQUID" in phases
        if case.key == "fe":
            assert "C15_LAVES" in unfiltered, (
                "C15_LAVES исчезла из filter_phases — правило продукта больше "
                "ничего не исключает, проверьте базу"
            )
        assert "C15_LAVES" not in phases


# --------------------------------------------------------------------------- #
# Section 1: equilibrium -- point, T-scan, X-scan
# --------------------------------------------------------------------------- #


@pytest.mark.timeout(DEFAULT_TIMEOUT)
def test_equilibrium_point(db: Database, case: Case, phases: list[str]) -> None:
    """One equilibrium point: fractions sum to 1 and the matrix phase is stable."""

    with measure("Равновесие", "точка при T", case.key) as numbers:
        temperature_k = case.temperature_c + 273.15
        fractions = solve_point(db, case, phases, temperature_k)
        numbers["T, °C"] = case.temperature_c
        numbers["фазы"] = {name: round(value, 5) for name, value in fractions.items()}
        numbers["сумма долей"] = round(sum(fractions.values()), 8)
        numbers["матрица"] = top_phase(fractions)
        assert fractions
        assert abs(sum(fractions.values()) - 1.0) < 1e-5
        assert case.matrix_phases & set(fractions), (
            f"Ожидалась матричная фаза из {sorted(case.matrix_phases)}, "
            f"получены {sorted(fractions)}"
        )


@pytest.mark.timeout(DEFAULT_TIMEOUT)
def test_equilibrium_temperature_scan(db: Database, case: Case, phases: list[str]) -> None:
    """Five-point temperature scan; every point closes the phase balance."""

    with measure("Равновесие", "T-скан 5 точек", case.key) as numbers:
        rows: dict[str, dict[str, float]] = {}
        for temperature_c in case.scan_temperatures_c:
            fractions = solve_point(db, case, phases, temperature_c + 273.15)
            rows[f"{temperature_c:g} °C"] = {
                name: round(value, 5) for name, value in fractions.items()
            }
            assert abs(sum(fractions.values()) - 1.0) < 1e-5
            assert case.matrix_phases & set(fractions)
        numbers["точки"] = rows
        assert len(rows) == len(case.scan_temperatures_c)


@pytest.mark.timeout(DEFAULT_TIMEOUT)
def test_equilibrium_composition_scan(db: Database, case: Case, phases: list[str]) -> None:
    """Five-point composition scan along one element at the working temperature."""

    with measure("Равновесие", "X-скан 5 точек", case.key) as numbers:
        temperature_k = case.temperature_c + 273.15
        element = case.scan_element
        rows: dict[str, dict[str, float]] = {}
        for fraction in case.scan_mole_fractions:
            override = {v.X(element): float(fraction)}
            fractions = solve_point(db, case, phases, temperature_k, override)
            rows[f"x({element})={fraction:g}"] = {
                name: round(value, 5) for name, value in fractions.items()
            }
            assert abs(sum(fractions.values()) - 1.0) < 1e-5
        numbers["ось"] = element
        numbers["точки"] = rows
        assert len(rows) == len(case.scan_mole_fractions)


# --------------------------------------------------------------------------- #
# Section 2: diagrams -- binary, isopleth, ternary, phase-fraction map
# --------------------------------------------------------------------------- #


@pytest.mark.slow
@pytest.mark.timeout(SLOW_TIMEOUT)
def test_binary_diagram(db: Database, case: Case) -> None:
    """Binary T-X map on a coarse grid, same call shape as the application."""

    from pycalphad.mapping import BinaryStrategy

    with measure("Диаграммы", "бинарная T–X", case.key) as numbers:
        components = list(case.binary_components)
        phase_list = effective_phases(db, case.key, case.binary_components)
        conditions = {
            v.N: 1.0,
            v.P: 101325.0,
            v.T: case.binary_t,
            v.X(case.binary_element): case.binary_x,
        }
        strategy = BinaryStrategy(db, components, phases=phase_list, conditions=conditions)
        strategy.do_map()
        numbers["система"] = "–".join(e for e in components if e != "VA")
        numbers["фаз"] = len(phase_list)
        numbers["zpf-линий"] = len(strategy.zpf_lines)
        numbers["узлов"] = len(strategy.node_queue.nodes)
        assert strategy.zpf_lines, "Границы фазовых областей не построены"


@pytest.mark.slow
@pytest.mark.timeout(SLOW_TIMEOUT)
def test_isopleth_diagram(db: Database, case: Case) -> None:
    """Isopleth along one element with the remaining additions fixed."""

    from pycalphad.mapping import IsoplethStrategy

    with measure("Диаграммы", "изоплета", case.key) as numbers:
        components = list(case.isopleth_components)
        phase_list = effective_phases(db, case.key, case.isopleth_components)
        conditions: dict[Any, Any] = {
            v.N: 1.0,
            v.P: 101325.0,
            v.T: case.isopleth_t,
            v.X(case.isopleth_element): case.isopleth_x,
        }
        for element, value in case.isopleth_fixed.items():
            conditions[v.X(element)] = float(value)
        strategy = IsoplethStrategy(db, components, phases=phase_list, conditions=conditions)
        strategy.do_map()
        numbers["ось"] = case.isopleth_element
        numbers["фиксировано"] = case.isopleth_fixed
        numbers["фаз"] = len(phase_list)
        numbers["zpf-линий"] = len(strategy.zpf_lines)
        numbers["узлов"] = len(strategy.node_queue.nodes)
        assert strategy.zpf_lines, "Сечение пустое"


@pytest.mark.slow
@pytest.mark.timeout(SLOW_TIMEOUT)
def test_ternary_section(db: Database, case: Case) -> None:
    """Ternary isothermal section on a coarse 0.1 grid."""

    from pycalphad.mapping import TernaryStrategy

    with measure("Диаграммы", "тройное сечение", case.key) as numbers:
        components = list(case.ternary_components)
        phase_list = effective_phases(db, case.key, case.ternary_components)
        elements = [e for e in components if e != "VA"]
        conditions = {
            v.N: 1.0,
            v.P: 101325.0,
            v.T: float(case.ternary_temperature_k),
            v.X(elements[1]): (0.0, 1.0, 0.1),
            v.X(elements[2]): (0.0, 1.0, 0.1),
        }
        strategy = TernaryStrategy(db, components, phases=phase_list, conditions=conditions)
        strategy.generate_automatic_starting_points()
        strategy.do_map()
        numbers["система"] = "–".join(elements)
        numbers["T, K"] = case.ternary_temperature_k
        numbers["фаз"] = len(phase_list)
        numbers["zpf-линий"] = len(strategy.zpf_lines)
        numbers["узлов"] = len(strategy.node_queue.nodes)
        assert strategy.zpf_lines, "Тройное сечение пустое"


@pytest.mark.slow
@pytest.mark.timeout(SLOW_TIMEOUT)
def test_phase_fraction_map(db: Database, case: Case) -> None:
    """Phase-fraction map: 4x4 equilibrium grid over two composition axes."""

    with measure("Диаграммы", "карта доли фазы 4×4", case.key) as numbers:
        components = list(case.map_components)
        phase_list = effective_phases(db, case.key, case.map_components)
        (x_element, x_min, x_max), (y_element, y_min, y_max) = case.map_axes
        values: list[float] = []
        for x_value in np.linspace(x_min, x_max, 4):
            for y_value in np.linspace(y_min, y_max, 4):
                conditions = {
                    v.N: 1.0,
                    v.P: 101325.0,
                    v.T: float(case.map_temperature_k),
                    v.X(x_element): float(x_value),
                    v.X(y_element): float(y_value),
                }
                fractions = phase_fractions(
                    equilibrium(
                        db, components, phase_list, conditions, calc_opts={"pdens": 50}
                    )
                )
                assert abs(sum(fractions.values()) - 1.0) < 1e-4
                values.append(fractions.get(case.map_target_phase, 0.0))
        numbers["оси"] = f"{x_element} × {y_element}"
        numbers["фаза"] = case.map_target_phase
        numbers["T, K"] = case.map_temperature_k
        numbers["доля min"] = round(min(values), 5)
        numbers["доля max"] = round(max(values), 5)
        assert len(values) == 16
        assert max(values) > 0.0, (
            f"{case.map_target_phase} не появилась ни в одной из 16 точек сетки"
        )


# --------------------------------------------------------------------------- #
# Section 3: solidification -- equilibrium scan and Scheil
# --------------------------------------------------------------------------- #


@pytest.mark.timeout(DEFAULT_TIMEOUT)
def test_equilibrium_solidification_scan(db: Database, case: Case, phases: list[str]) -> None:
    """Cooling from above the liquidus: the liquid fraction never increases."""

    with measure("Затвердевание", "равновесное (T-скан)", case.key) as numbers:
        start_k, stop_k = case.solidification_scan_k
        liquid: list[float] = []
        temperatures = [float(t) for t in np.linspace(start_k, stop_k, 6)]
        for temperature_k in temperatures:
            fractions = solve_point(db, case, phases, temperature_k)
            liquid.append(fractions.get("LIQUID", 0.0))
            assert abs(sum(fractions.values()) - 1.0) < 1e-5
        numbers["T, K"] = [round(t, 1) for t in temperatures]
        numbers["доля LIQUID"] = [round(value, 5) for value in liquid]
        assert liquid[0] > 0.9, "Стартовая точка не является расплавом"
        assert liquid[-1] < 0.5, "Расплав не убывает к нижней точке скана"
        for previous, current in zip(liquid, liquid[1:]):
            assert current <= previous + 1e-6, "Доля LIQUID выросла при охлаждении"


@pytest.mark.timeout(SLOW_TIMEOUT)
def test_scheil_solidification(db: Database, case: Case, phases: list[str]) -> None:
    """Scheil-Gulliver with a 10 K step reaches at least 95 % solid."""

    scheil = pytest.importorskip("scheil")

    with measure("Затвердевание", "Scheil", case.key) as numbers:
        result = scheil.simulate_scheil_solidification(
            db,
            list(case.components),
            phases,
            composition_conditions(db, case),
            float(case.scheil_start_k),
            step_temperature=10.0,
            liquid_phase_name="LIQUID",
            eq_kwargs={"calc_opts": {"pdens": 100}},
            stop=0.05,
            verbose=False,
        )
        solid = float(max(result.fraction_solid))
        numbers["старт, K"] = case.scheil_start_k
        numbers["fraction_solid max"] = round(solid, 4)
        numbers["T конца, K"] = round(float(min(result.temperatures)), 1)
        numbers["точек"] = len(result.temperatures)
        numbers["фазы"] = sorted(
            name
            for name, amounts in result.cum_phase_amounts.items()
            if float(amounts[-1]) > 1e-6
        )
        assert solid >= 0.95, f"fraction_solid дошёл только до {solid:.4f}"


# --------------------------------------------------------------------------- #
# Section 4: energies -- GM curves, driving force, T0
# --------------------------------------------------------------------------- #


@pytest.mark.timeout(DEFAULT_TIMEOUT)
def test_phase_energies_and_driving_force(db: Database, case: Case) -> None:
    """GM of two phases at the working temperature plus their difference.

    ``calculate`` samples the internal degrees of freedom of one phase, so the
    number recorded is the minimum molar Gibbs energy of that phase over its own
    composition space -- a stable regression anchor, not a thermodynamic claim
    about the alloy composition.
    """

    with measure("Энергии", "GM двух фаз, движущая сила", case.key) as numbers:
        first, second = case.energy_pair
        temperature_k = case.temperature_c + 273.15
        energies: dict[str, float] = {}
        for phase in (first, second):
            sampled = calculate(
                db,
                list(case.components),
                phase,
                T=temperature_k,
                P=101325.0,
                N=1.0,
                pdens=200,
                output="GM",
            )
            energies[phase] = float(np.asarray(sampled.GM.values).min())
        driving_force = energies[first] - energies[second]
        numbers["T, °C"] = case.temperature_c
        numbers[f"min GM({first}), Дж/моль"] = round(energies[first], 1)
        numbers[f"min GM({second}), Дж/моль"] = round(energies[second], 1)
        numbers["движущая сила, Дж/моль"] = round(driving_force, 1)
        assert all(np.isfinite(value) for value in energies.values())
        assert abs(driving_force) > 1.0, "Фазы неразличимы по энергии"


@pytest.mark.timeout(DEFAULT_TIMEOUT)
def test_t0_temperature(db: Database, case: Case) -> None:
    """T0: the temperature where two single-phase GM values cross.

    Each phase is solved on its own at the alloy composition (``equilibrium``
    with a one-element phase list), so the comparison is made at equal
    composition, and the crossing is located by
    ``thermogar_equilibrium_core.find_monotonic_linear_crossings``.
    """

    from thermogar_equilibrium_core import find_monotonic_linear_crossings

    with measure("Энергии", "T₀", case.key) as numbers:
        first, second = case.t0_pair
        low, high = case.t0_window_k
        base = composition_conditions(db, case)
        temperatures: list[float] = []
        differences: list[float] = []
        for temperature_k in np.linspace(low, high, 5):
            values: dict[str, float] = {}
            for phase in (first, second):
                conditions: dict[Any, float] = {
                    v.N: 1.0,
                    v.P: 101325.0,
                    v.T: float(temperature_k),
                }
                conditions.update(base)
                solved = equilibrium(
                    db, list(case.components), [phase], conditions, calc_opts={"pdens": 100}
                )
                values[phase] = float(np.asarray(solved.GM.values).ravel()[0])
            temperatures.append(float(temperature_k))
            differences.append(values[first] - values[second])
        crossings = find_monotonic_linear_crossings(
            tuple(temperatures), tuple(differences), target=0.0
        )
        crossing_k = float(crossings[0].x)
        numbers["пара"] = f"{first} / {second}"
        numbers["окно, K"] = [low, high]
        numbers["ΔGM, Дж/моль"] = [round(value, 1) for value in differences]
        numbers["T₀, K"] = round(crossing_k, 2)
        numbers["T₀, °C"] = round(crossing_k - 273.15, 2)
        assert low <= crossing_k <= high
        assert abs(crossing_k - case.t0_expected_k) < 25.0, (
            f"T₀ = {crossing_k:.1f} K против опорных {case.t0_expected_k} K "
            "(прогон 2026-09-02 на этой машине)"
        )


# --------------------------------------------------------------------------- #
# Section 5: properties -- density, VRH, strengthening
# --------------------------------------------------------------------------- #


@pytest.mark.timeout(DEFAULT_TIMEOUT)
def test_alloy_density(request: pytest.FixtureRequest, db: Database, case: Case, phases: list[str]) -> None:
    """Density of the equilibrium phase assembly from physical_data_v103.pdb."""

    if case.key == "al":
        request.node.add_marker(
            pytest.mark.xfail(
                strict=True,
                reason=(
                    "PDB v1.03 не покрывает THETA_AL2CU: плотность сплава не "
                    "выдаётся, покрытие < 100 %"
                ),
            )
        )

    from thermogar_physical import PhysicalDensityDatabase, calculate_physical_properties

    with measure("Свойства", "плотность", case.key) as numbers:
        pdb_path = ROOT / "databases/physical/original/physical_data_v103.pdb"
        if not pdb_path.is_file():
            pytest.skip(f"Нет PDB: {pdb_path}")
        physical_db = PhysicalDensityDatabase(pdb_path)
        temperature_k = case.temperature_c + 273.15
        conditions: dict[Any, float] = {
            v.N: 1.0,
            v.P: 101325.0,
            v.T: temperature_k,
        }
        conditions.update(composition_conditions(db, case))
        eq = equilibrium(
            db, list(case.components), phases, conditions, calc_opts={"pdens": 100}
        )
        elements = [element for element in case.components if element != "VA"]
        result = calculate_physical_properties(db, eq, elements, temperature_k, physical_db)
        numbers["T, °C"] = case.temperature_c
        numbers["плотность, кг/м³"] = result.alloy_density_kg_m3
        numbers["покрытие по массе, %"] = round(float(result.mass_coverage_pct), 2)
        numbers["качество"] = result.quality_label
        assert result.mass_coverage_pct > 50.0
        assert result.alloy_density_kg_m3 is not None, (
            "Плотность сплава не рассчитана: не все равновесные фазы покрыты PDB"
        )
        assert 1000.0 < float(result.alloy_density_kg_m3) < 20000.0


@pytest.mark.timeout(DEFAULT_TIMEOUT)
def test_vrh_and_strengthening(case: Case) -> None:
    """VRH bounds and the strengthening sum on declared test numbers."""

    from thermogar_properties import calculate_strengthening, vrh_homogenization

    with measure("Свойства", "VRH и упрочнение", case.key) as numbers:
        table, summary = vrh_homogenization([dict(row) for row in case.elastic_rows])
        assert len(table) >= len(case.elastic_rows)
        assert summary["K_Reuss_GPa"] <= summary["K_Hill_GPa"] <= summary["K_Voigt_GPa"]
        assert summary["G_Reuss_GPa"] <= summary["G_Hill_GPa"] <= summary["G_Voigt_GPa"]
        numbers["E_Hill, ГПа"] = round(float(summary["E_Hill_GPa"]), 3)
        numbers["G_Hill, ГПа"] = round(float(summary["G_Hill_GPa"]), 3)
        numbers["nu_Hill"] = round(float(summary["nu_Hill"]), 4)

        strengthening = calculate_strengthening(
            input_provenance="SYNTHETIC_BACKEND_REGRESSION_NOT_MATERIAL_INPUT",
            input_confirmation=True,
            sigma_internal_mpa=50.0,
            hall_petch={"k_y_mpa_sqrt_m": 0.5, "grain_size_um": 25.0},
            taylor={
                "taylor_factor": 3.06,
                "alpha": 0.3,
                "shear_gpa": float(summary["G_Hill_GPa"]),
                "burgers_nm": 0.25,
                "dislocation_density_m2": 1e14,
            },
            solid_solution_mpa=60.0,
            orowan={
                "taylor_factor": 3.06,
                "shear_gpa": float(summary["G_Hill_GPa"]),
                "burgers_nm": 0.25,
                "poisson": float(summary["nu_Hill"]),
                "particle_radius_nm": 20.0,
                "spacing_nm": 150.0,
            },
            other_mpa=None,
            summation_rule="Квадратичное объединение вкладов",
        )
        total = strengthening.total_mpa
        numbers["σ суммарное, МПа"] = None if total is None else round(float(total), 2)
        numbers["механизмов"] = len(strengthening.contribution_table)
        assert total is not None and total > 0.0


# --------------------------------------------------------------------------- #
# Section 6: kinetics -- diffusion and KWN, module level (b) and direct (a)
# --------------------------------------------------------------------------- #


@pytest.mark.timeout(DEFAULT_TIMEOUT)
def test_diffusion_module(request: pytest.FixtureRequest, case: Case) -> None:
    """Level (b): short 1D diffusion couple through ``thermogar_diffusion``."""

    if case.key == "fe":
        request.node.add_marker(
            pytest.mark.xfail(
                strict=True,
                reason="Fe hard-reject в thermogar_diffusion.py:167, снимается в Э2",
            )
        )

    from thermogar_diffusion import run_diffusion
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    with measure("Кинетика", "диффузия (модуль)", case.key) as numbers:
        result = run_diffusion(
            # The API deliberately ignores this object and reloads the pinned
            # canonical database itself.
            db=object(),
            database_key=case.key,
            database_path=database_path(case),
            database_label=RELEASE_DATABASE_LABELS.get(case.key, case.label),
            balance=case.balance,
            units=case.units,
            left_text=case.diffusion_left,
            right_text=case.diffusion_right,
            temperature_c=case.diffusion_temperature_c,
            time_h=0.001,
            length_um=100.0,
            interface_percent=50.0,
            nodes=20,
            phases=[case.diffusion_phase],
            model_kind="single",
            input_provenance="SYNTHETIC_BACKEND_REGRESSION_NOT_MATERIAL_INPUT",
            input_confirmation=True,
        )
        numbers["фаза"] = case.diffusion_phase
        numbers["T, °C"] = case.diffusion_temperature_c
        numbers["узлов профиля"] = len(result.profile_table)
        numbers["время модели, с"] = float(result.actual_time_s)
        numbers["макс. невязка баланса"] = float(result.max_balance_error)
        assert len(result.profile_table) == 20
        assert result.max_balance_error < 1e-4


@pytest.mark.timeout(DEFAULT_TIMEOUT)
def test_diffusion_direct_kawin(db: Database, case: Case) -> None:
    """Level (a): the same 1D couple straight through kawin, no ThermoGar code.

    This is what tells Fe apart: if this passes while ``test_diffusion_module``
    is xfail, the database and the library are fine and only the application's
    hard reject stands in the way.
    """

    pytest.importorskip("kawin")
    from kawin.diffusion import SinglePhaseModel
    from kawin.diffusion.mesh import Cartesian1D, ProfileBuilder, StepProfile1D
    from kawin.solver import explicitEulerIterator
    from kawin.thermo import GeneralThermodynamics

    with measure("Кинетика", "диффузия (kawin напрямую)", case.key) as numbers:
        elements = list(case.diffusion_elements)
        independent = elements[1:]
        mesh = Cartesian1D(independent, [0.0, 100e-6], 20)
        builder = ProfileBuilder()
        builder.addBuildStep(
            StepProfile1D(50e-6, list(case.diffusion_left_x), list(case.diffusion_right_x)),
            independent,
        )
        mesh.setResponseProfile(builder)
        thermodynamics = GeneralThermodynamics(db, elements, [case.diffusion_phase])
        model = SinglePhaseModel(
            mesh,
            elements,
            [case.diffusion_phase],
            thermodynamics=thermodynamics,
            temperature=case.diffusion_temperature_c + 273.15,
            record=False,
        )
        model.solve(3.6, iterator=explicitEulerIterator, verbose=False, vIt=500, minDtFrac=1e-10)
        profile = np.asarray(model.getCompositions(), dtype=float)
        numbers["фаза"] = case.diffusion_phase
        numbers["элементы"] = elements
        numbers["T, °C"] = case.diffusion_temperature_c
        numbers["форма профиля"] = list(profile.shape)
        assert profile.shape[0] == 20
        assert np.isfinite(profile).all()


@pytest.mark.timeout(SLOW_TIMEOUT)
def test_kwn_module(request: pytest.FixtureRequest, case: Case) -> None:
    """Level (b): short KWN run through ``thermogar_precipitation``."""

    if case.key == "fe":
        request.node.add_marker(
            pytest.mark.xfail(
                strict=True,
                reason="Fe hard-reject в thermogar_precipitation.py:514, снимается в Э2",
            )
        )

    pytest.importorskip("kawin")
    from thermogar_precipitation import run_precipitation
    from thermogar_release_policy import RELEASE_DATABASE_LABELS

    with measure("Кинетика", "KWN (модуль)", case.key) as numbers:
        composition_text = ", ".join(
            f"{element}={value:g}" for element, value in case.kwn_composition_pct.items()
        )
        result = run_precipitation(
            db=object(),
            database_path=database_path(case),
            database_label=RELEASE_DATABASE_LABELS.get(case.key, case.label),
            database_key=case.key,
            balance=case.balance,
            composition_text=composition_text,
            units=case.kwn_units,
            matrix_phase=case.kwn_matrix,
            precipitate_phase=case.kwn_precipitate,
            schedule_mode="isothermal",
            temperature_c=case.kwn_temperature_c,
            duration_h=1.0 / 3600.0,
            profile_text="",
            gamma=case.kwn_gamma,
            matrix_vm=case.kwn_molar_volume_cm3,
            precip_vm=case.kwn_molar_volume_cm3,
            nucleation_type="BULK",
            bulk_n0=1e30,
            grain_size_um=100.0,
            dislocation_density=5e12,
            gb_energy=0.3,
            cmin_nm=case.kwn_size_nm[0],
            cmax_nm=case.kwn_size_nm[1],
            bins=30,
            input_provenance="SYNTHETIC_BACKEND_REGRESSION_NOT_MATERIAL_INPUT",
            input_confirmation=True,
        )
        numbers["пара"] = f"{case.kwn_matrix} / {case.kwn_precipitate}"
        numbers["T, °C"] = case.kwn_temperature_c
        numbers["строк кинетики"] = len(result.kinetics)
        numbers["проверки качества"] = bool(
            (result.quality["Статус"] == "пройдена").all()
        )
        assert len(result.kinetics) >= 1
        assert bool((result.quality["Статус"] == "пройдена").all())


@pytest.mark.timeout(SLOW_TIMEOUT)
def test_kwn_direct_kawin(case: Case) -> None:
    """Level (a): the same KWN model straight through kawin, no ThermoGar code."""

    pytest.importorskip("kawin")
    from kawin.precipitation import (
        MatrixParameters,
        PrecipitateModel,
        PrecipitateParameters,
        TemperatureParameters,
    )
    from kawin.thermo import MulticomponentThermodynamics

    with measure("Кинетика", "KWN (kawin напрямую)", case.key) as numbers:
        elements = [case.balance, *case.kwn_solutes]
        thermodynamics = MulticomponentThermodynamics(
            str(database_path(case)),
            elements,
            [case.kwn_matrix, case.kwn_precipitate],
        )
        matrix = MatrixParameters(list(case.kwn_solutes))
        matrix.initComposition = list(case.kwn_solute_x)
        matrix.volume.setVolume(case.kwn_molar_volume_cm3 * 1e-6, "VM", 1)
        precipitate = PrecipitateParameters(case.kwn_precipitate)
        precipitate.gamma = case.kwn_gamma
        precipitate.volume.setVolume(case.kwn_molar_volume_cm3 * 1e-6, "VM", 1)
        precipitate.nucleation.setNucleationType("BULK")
        model = PrecipitateModel(
            matrix,
            [precipitate],
            thermodynamics,
            TemperatureParameters(case.kwn_temperature_c + 273.15),
        )
        model.setPBMParameters(
            cMin=case.kwn_size_nm[0] * 1e-9,
            cMax=case.kwn_size_nm[1] * 1e-9,
            bins=30,
            minBins=20,
            maxBins=60,
            adaptive=True,
        )
        model.setup()
        model.solve(1.0, verbose=False)
        numbers["пара"] = f"{case.kwn_matrix} / {case.kwn_precipitate}"
        numbers["T, °C"] = case.kwn_temperature_c
        numbers["решено, с модельного времени"] = 1.0
        assert model is not None


# --------------------------------------------------------------------------- #
# Section 7: projects / batch
# --------------------------------------------------------------------------- #


@pytest.mark.timeout(SLOW_TIMEOUT)
def test_batch_three_compositions(db: Database, case: Case, phases: list[str]) -> None:
    """Batch: three compositions in a row, time per point recorded."""

    with measure("Проекты/batch", "3 состава подряд", case.key) as numbers:
        temperature_k = case.temperature_c + 273.15
        per_point: list[float] = []
        rows: dict[str, dict[str, float]] = {}
        for scale in (0.8, 1.0, 1.2):
            scaled = Case(**{**case.__dict__, "composition_pct": {
                element: value * scale for element, value in case.composition_pct.items()
            }})
            started = time.perf_counter()
            fractions = solve_point(db, scaled, phases, temperature_k)
            per_point.append(time.perf_counter() - started)
            rows[f"×{scale:g}"] = {name: round(value, 5) for name, value in fractions.items()}
            assert abs(sum(fractions.values()) - 1.0) < 1e-5
        numbers["точки"] = rows
        numbers["с/точку"] = [round(value, 2) for value in per_point]
        numbers["всего, с"] = round(sum(per_point), 2)
        assert len(rows) == 3


if __name__ == "__main__":  # pragma: no cover - convenience only
    warnings.filterwarnings("ignore")
    raise SystemExit(pytest.main([__file__, "-v"]))
