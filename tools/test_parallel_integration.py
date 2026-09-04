#!/usr/bin/env python3
"""Интеграция параллельного движка в приложение (волна 6).

Проверяется главное обещание волны: числа не зависят от того, считались
точки в пуле процессов или последовательно. Сравнение побайтовое — через
``float.hex()``, а не через округление.

Два уровня:

* переходник ``EquilibriumSnapshot`` против настоящего объекта ``equilibrium``
  на одной точке Fe: имена фаз, ``NP`` и составы вершин совпадают, поэтому
  любая функция приложения, читающая ``eq.Phase``/``eq.NP``/``eq.X``, получит
  на переходнике те же числа;
* таблицы разделов из интерфейса (``AppTest``) с движком и без него: пять
  точек температурного скана Fe, все ячейки и байты выгрузок.

Запуск:

    python -m pytest tools/test_parallel_integration.py -m "not slow"
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from pycalphad import Database, equilibrium, variables as v  # noqa: E402

import thermogar_parallel as tp  # noqa: E402
import thermogar_parallel_ui as parallel_ui  # noqa: E402

import test_ui_f  # noqa: E402


# Канонический Fe-профиль приложения (ThermoGar_app.FE_PROFILE_RELATIVE_PATHS);
# сам ``ThermoGar_app.py`` — скрипт Streamlit и импортироваться не должен.
FE_RELATIVE_PATH = (
    "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb"
)

FE_COMPOSITION = {"C": 0.2, "CR": 11.5, "NI": 0.7}
FE_BALANCE = "FE"
FE_TEMPERATURE_K = 973.15
FE_PHASES = ("FCC_A1", "BCC_A2", "M23C6", "M7C3", "LIQUID")


@pytest.fixture(scope="module")
def fe_database_path() -> Path:
    return (ROOT / FE_RELATIVE_PATH).resolve()


@pytest.fixture(scope="module")
def fe_sha256(fe_database_path: Path) -> str:
    return tp.file_sha256(fe_database_path)


@pytest.fixture(scope="module")
def fe_database(fe_database_path: Path, fe_sha256: str) -> Database:
    # Тем же путём, что и приложение с воркером: объект после ``pickle``
    # обходит составляющие подрешёток в другом порядке, чем только что
    # разобранный, и равновесие расходится в последних знаках.
    return tp.load_database(fe_database_path, fe_sha256)


def _fe_point(database: Database) -> tuple[list[str], list[str], dict[str, float]]:
    """Точка Fe–0.2C–11.5Cr–0.7Ni при 700 °C в мольных долях."""
    mass_conditions = {
        v.W(element): value / 100.0 for element, value in FE_COMPOSITION.items()
    }
    mole = dict(v.get_mole_fractions(mass_conditions, FE_BALANCE, database))
    components = sorted(set(FE_COMPOSITION) | {FE_BALANCE}) + ["VA"]
    phases = [phase for phase in FE_PHASES if phase in database.phases]
    fractions = {
        str(getattr(variable, "species", variable)): float(value)
        for variable, value in mole.items()
    }
    return components, phases, fractions


def _hex_values(values: Any) -> list[str]:
    return [float(item).hex() for item in np.asarray(values, dtype=float).ravel()]


def test_snapshot_reproduces_equilibrium_object(
    fe_database: Database,
    fe_database_path: Path,
    fe_sha256: str,
) -> None:
    """Переходник отдаёт те же числа, что и объект ``equilibrium``."""

    components, phases, mole = _fe_point(fe_database)
    conditions: dict[Any, float] = {
        v.N: 1.0,
        v.P: 101325.0,
        v.T: FE_TEMPERATURE_K,
    }
    conditions.update({v.X(element): value for element, value in mole.items()})
    reference = equilibrium(
        fe_database,
        components,
        phases,
        conditions,
        calc_opts={"pdens": 500},
    )

    point = {"N": 1.0, "P": 101325.0, "T": FE_TEMPERATURE_K, "X": mole}
    with tp.ParallelEquilibrium(fe_database_path, fe_sha256, workers=2) as engine:
        results = engine.map_points(
            [point],
            components,
            phases,
            pdens=500,
            capture=("X", "Y"),
        )
    assert results[0].ok, results[0].error
    snapshot = parallel_ui.snapshot_of(results[0])

    assert list(np.asarray(snapshot.Phase.values, dtype=str).ravel()) == list(
        np.asarray(reference.Phase.values, dtype=str).ravel()
    )
    assert _hex_values(snapshot.NP.values) == _hex_values(reference.NP.values)
    for element in components:
        if element == "VA":
            continue
        assert _hex_values(
            snapshot.X.sel(component=element).values
        ) == _hex_values(reference.X.sel(component=element).values), element

    # Доли узлов подрешёток нужны разделу «Свойства»; в них штатно есть NaN,
    # поэтому сравнение идёт по точному представлению, а не по равенству.
    expected = np.asarray(reference.Y.values, dtype=float)
    got = np.asarray(snapshot.Y.values, dtype=float)
    expected_rows = expected.reshape((-1, expected.shape[-1]))
    got_rows = got.reshape((-1, got.shape[-1]))
    assert got_rows.shape == expected_rows.shape
    assert _hex_values(got_rows) == _hex_values(expected_rows)


def test_engine_matches_in_process_bytewise(
    fe_database: Database,
    fe_database_path: Path,
    fe_sha256: str,
) -> None:
    """Пул и счёт в текущем процессе дают одни и те же биты на пяти точках."""

    components, phases, mole = _fe_point(fe_database)
    points = [
        {"N": 1.0, "P": 101325.0, "T": 773.15 + 100.0 * step, "X": mole}
        for step in range(5)
    ]
    local = tp.solve_points_in_process(
        fe_database,
        points,
        components,
        phases,
        pdens=500,
        capture=("X",),
    )
    with tp.ParallelEquilibrium(fe_database_path, fe_sha256, workers=3) as engine:
        pooled = engine.map_points(
            points,
            components,
            phases,
            pdens=500,
            capture=("X",),
        )
    assert tp.canonical_digest(local) == tp.canonical_digest(pooled)
    for one, other in zip(local, pooled):
        assert one.arrays is not None and other.arrays is not None
        assert one.arrays["phase"] == other.arrays["phase"]
        assert _hex_values(one.arrays["np"]) == _hex_values(other.arrays["np"])
        for element, column in one.arrays["x"].items():
            assert _hex_values(column) == _hex_values(other.arrays["x"][element])


# ---------------------------------------------------------------------------
# Таблицы разделов из интерфейса
# ---------------------------------------------------------------------------


def _frame_hex(frame: pd.DataFrame) -> list[list[str]]:
    """Таблица в виде точных представлений чисел, столбец за столбцом."""
    payload: list[list[str]] = [list(frame.columns)]
    for _index, row in frame.iterrows():
        payload.append(
            [
                float(value).hex() if isinstance(value, (int, float)) else str(value)
                for value in row.tolist()
            ]
        )
    return payload


def _temperature_scan(mode: str) -> tuple[pd.DataFrame, str, bytes]:
    profile = test_ui_f.BASES["fe"]
    t_min, t_max, t_step = profile["scan"]
    session = test_ui_f.start(
        "fe",
        session={
            "t_min_fe": t_min,
            "t_max_fe": t_max,
            "t_step_fe": t_step,
            parallel_ui.SIDEBAR_STATE_KEY: mode,
        },
    )
    session.click("temperature_calculate")
    session.assert_clean()
    display = session.state(
        "_thermogar_vlb_b3_result_equilibrium_temperature_scan"
    )["display"]
    settings = display["settings"]
    note = str(
        settings.loc[
            settings["Параметр"] == "Параллельный расчёт", "Значение"
        ].iloc[0]
    )
    return (
        display["data"],
        note,
        session.download("ThermoGar_temperature_scan.csv"),
    )


def test_temperature_scan_tables_match_with_and_without_pool() -> None:
    """Пять точек Fe: таблица и CSV из интерфейса совпадают побайтово."""

    if not tp.parent_hash_seed_is_fixed():
        pytest.skip(
            "Сравнение режимов требует PYTHONHASHSEED=0 у процесса тестов "
            "(RUN_TESTS_WINDOWS.cmd задаёт её)."
        )
    pooled_data, pooled_note, pooled_csv = _temperature_scan(parallel_ui.MODE_AUTO)
    plain_data, plain_note, plain_csv = _temperature_scan(parallel_ui.MODE_OFF)

    assert len(pooled_data) == 5
    assert plain_note == "Последовательный расчёт в одном процессе."
    if parallel_ui.pool_worker_count() > 1:
        assert pooled_note.startswith("Параллельный расчёт:"), pooled_note
    assert list(pooled_data.columns) == list(plain_data.columns)
    assert _frame_hex(pooled_data) == _frame_hex(plain_data)
    assert pooled_csv == plain_csv


# ---------------------------------------------------------------------------
# Выбор числа воркеров, порог и досчёт после отказа пула
# ---------------------------------------------------------------------------


def test_worker_count_follows_free_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """``min(cpu_count-1, свободная память // 1.5 ГБ, 6)``, но не меньше 1."""

    monkeypatch.setattr(tp.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(tp, "available_memory_gb", lambda: 16.0)
    assert tp.auto_worker_count() == 6  # потолок
    monkeypatch.setattr(tp, "available_memory_gb", lambda: 4.6)
    assert tp.auto_worker_count() == 3  # 4.6 // 1.5
    monkeypatch.setattr(tp, "available_memory_gb", lambda: 0.5)
    assert tp.auto_worker_count() == 1  # не меньше одного
    monkeypatch.setattr(tp.os, "cpu_count", lambda: 3)
    monkeypatch.setattr(tp, "available_memory_gb", lambda: 16.0)
    assert tp.auto_worker_count() == 2  # ограничивает уже число ядер


def test_pool_threshold_is_lower_for_aluminium() -> None:
    """Точка Al дороже, поэтому пул окупается уже на двух точках."""

    assert parallel_ui.pool_threshold("al") == 2
    assert parallel_ui.pool_threshold("fe") == 4
    assert parallel_ui.pool_threshold("ni") == 4


class _LostPool:
    """Пул, который отдаёт часть точек и умирает на остальных."""

    def __init__(self, survived: int) -> None:
        self.survived = survived

    def map_points(self, points, components, phases, **options):
        results = [
            tp.PointResult(index=index, ok=True, phase_fractions={"FCC_A1": 1.0})
            for index in range(self.survived)
        ]
        raise tp.WorkerLostError("WorkerLostError: воркер умер", results)


def test_pool_failure_keeps_finished_points_and_counts_the_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Отказ пула не теряет расчёт: остаток досчитывается последовательно."""

    calls: dict[str, Any] = {}

    def fake_shared_engine(*_args: Any, **_kwargs: Any) -> _LostPool:
        return _LostPool(survived=2)

    def fake_local(database, points, components, phases, **options):
        calls["indices"] = list(options["indices"])
        results = [
            tp.PointResult(index=index, ok=True, phase_fractions={"BCC_A2": 1.0})
            for index in options["indices"]
        ]
        report = options.get("progress_callback")
        if report is not None:
            for position, item in enumerate(results, start=1):
                report(position, len(results), item)
        return results

    monkeypatch.setattr(parallel_ui.parallel_engine, "shared_engine", fake_shared_engine)
    monkeypatch.setattr(
        parallel_ui.parallel_engine, "solve_points_in_process", fake_local
    )
    monkeypatch.setattr(parallel_ui, "pool_worker_count", lambda: 4)
    monkeypatch.setattr(parallel_ui, "parallel_mode", lambda: parallel_ui.MODE_AUTO)

    seen: list[tuple[int, int]] = []
    run = parallel_ui.run_points(
        database=None,
        database_path="database.tdb",
        sha256="0" * 64,
        database_key="fe",
        points=[{"T": 800.0 + index} for index in range(5)],
        components=["FE", "VA"],
        phases=["FCC_A1"],
        progress=lambda completed, total: seen.append((completed, total)),
    )

    assert calls["indices"] == [2, 3, 4]
    assert [item.index for item in run.results] == [0, 1, 2, 3, 4]
    assert [item.phase_fractions for item in run.results] == [
        {"FCC_A1": 1.0},
        {"FCC_A1": 1.0},
        {"BCC_A2": 1.0},
        {"BCC_A2": 1.0},
        {"BCC_A2": 1.0},
    ]
    assert run.fallback_reason == "WorkerLostError"
    assert "досчитаны последовательно" in run.note
    assert seen[-1] == (5, 5)
