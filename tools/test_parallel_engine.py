#!/usr/bin/env python3
"""Тесты параллельного движка равновесий ``app/thermogar_parallel.py`` (волна 5B).

Проверяется ровно то, ради чего движок и делается:

* ``workers=1`` и ``workers=N`` дают одинаковые числа — доли фаз и составы фаз
  совпадают побайтово (сравниваются точные представления ``float.hex()``);
* упавшая точка изолирована: соседние точки считаются, ошибка приходит в поле
  результата, порядок точек сохраняется;
* несовпадение SHA-256 базы отказывает до запуска, ни один процесс не создаётся;
* пул закрывается без зомби-процессов (проверка через ``psutil``);
* повторный вызов в одной сессии переиспользует уже поднятый пул.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -X utf8 -m pytest tools/test_parallel_engine.py -v

Бенчмарк (в тесты не входит, результаты — в ``tools/bench_parallel.md``):
    <root>/.venv-windows/Scripts/python.exe -X utf8 tools/test_parallel_engine.py --bench
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

import thermogar_parallel as tp  # noqa: E402

# Fe: правило продукта — C15_LAVES никогда не участвует в расчёте.
FE_EXCLUDED_PHASES = frozenset({"C15_LAVES"})


@dataclass(frozen=True)
class BenchCase:
    """База и её кейсы из ``tools/backend_reference.md`` — общие для тестов и бенчмарка."""

    key: str
    relative_path: str
    label: str
    balance: str
    units: str
    components: tuple[str, ...]
    composition_pct: dict[str, float]
    scan_temperature_c: tuple[float, float]
    map_components: tuple[str, ...]
    map_axes: tuple[tuple[str, float, float], tuple[str, float, float]]
    map_temperature_k: float


CASES: dict[str, BenchCase] = {
    "ni": BenchCase(
        key="ni",
        relative_path="databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
        label="Ni — mc_ni 2.036, Ni–15Al ат.%",
        balance="NI",
        units="at",
        components=("AL", "NI", "VA"),
        composition_pct={"AL": 15.0},
        scan_temperature_c=(600.0, 1000.0),
        map_components=("NI", "AL", "CR", "VA"),
        map_axes=(("AL", 0.05, 0.20), ("CR", 0.02, 0.12)),
        map_temperature_k=1273.15,
    ),
    "al": BenchCase(
        key="al",
        relative_path="databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb",
        label="Al — mc_al 2.037, Al–4Cu–1Mg масс.%",
        balance="AL",
        units="wt",
        components=("AL", "CU", "MG", "VA"),
        composition_pct={"CU": 4.0, "MG": 1.0},
        scan_temperature_c=(300.0, 600.0),
        map_components=("AL", "CU", "MG", "VA"),
        map_axes=(("CU", 0.005, 0.03), ("MG", 0.002, 0.02)),
        map_temperature_k=773.15,
    ),
    "fe": BenchCase(
        key="fe",
        relative_path="databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb",
        label="Fe — mc_fe 2.062, Fe–0.2C–11.5Cr–0.7Ni масс.%",
        balance="FE",
        units="wt",
        components=("FE", "C", "CR", "NI", "VA"),
        composition_pct={"C": 0.2, "CR": 11.5, "NI": 0.7},
        scan_temperature_c=(500.0, 900.0),
        # Обе оси карты — составные, поэтому в системе карты должно остаться
        # ровно на один элемент больше, чем осей: Ni убран намеренно.
        map_components=("FE", "C", "CR", "VA"),
        map_axes=(("C", 0.002, 0.02), ("CR", 0.05, 0.15)),
        map_temperature_k=973.15,
    ),
}

TEST_CASE = CASES["ni"]  # самая быстрая база, на ней идут все функциональные тесты


# --------------------------------------------------------------------------- #
# Общие помощники
# --------------------------------------------------------------------------- #


def database_path(case: BenchCase) -> Path:
    path = ROOT / case.relative_path
    if not path.is_file():
        pytest.skip(f"Нет файла базы: {path}")
    return path


def effective_phases(database: Any, case: BenchCase, components: Sequence[str]) -> list[str]:
    """Список фаз тот же, что в приложении: ``filter_phases`` плюс правило Fe."""
    from pycalphad.core.utils import filter_phases, unpack_species

    phases = set(filter_phases(database, unpack_species(database, list(components))))
    if case.key == "fe":
        phases -= FE_EXCLUDED_PHASES
    return sorted(phases)


def scan_points(case: BenchCase, count: int) -> list[dict[str, Any]]:
    """Точки T-скана: состав сплава фиксирован, меняется только температура."""
    low, high = case.scan_temperature_c
    step = (high - low) / (count - 1) if count > 1 else 0.0
    composition_key = "X" if case.units == "at" else "W"
    composition = {
        element: value / 100.0 for element, value in case.composition_pct.items()
    }
    points: list[dict[str, Any]] = []
    for index in range(count):
        point: dict[str, Any] = {"T": low + step * index + 273.15, composition_key: composition}
        if case.units == "wt":
            point["balance"] = case.balance
        points.append(point)
    return points


def map_points(case: BenchCase, side: int) -> list[dict[str, Any]]:
    """Узлы карты доли фазы: квадратная сетка ``side × side`` по двум составным осям."""
    (x_element, x_min, x_max), (y_element, y_min, y_max) = case.map_axes
    x_step = (x_max - x_min) / (side - 1) if side > 1 else 0.0
    y_step = (y_max - y_min) / (side - 1) if side > 1 else 0.0
    return [
        {
            "T": float(case.map_temperature_k),
            "X": {
                x_element: x_min + x_step * x_index,
                y_element: y_min + y_step * y_index,
            },
        }
        for x_index in range(side)
        for y_index in range(side)
    ]


def parse_database(case: BenchCase) -> Any:
    from pycalphad import Database

    return Database(str(ROOT / case.relative_path))


# --------------------------------------------------------------------------- #
# Фикстуры
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def case() -> BenchCase:
    return TEST_CASE


@pytest.fixture(scope="module")
def db_path(case: BenchCase) -> Path:
    return database_path(case)


@pytest.fixture(scope="module")
def db_sha(db_path: Path) -> str:
    return tp.file_sha256(db_path)


@pytest.fixture(scope="module")
def phases(case: BenchCase, db_path: Path) -> list[str]:
    return effective_phases(parse_database(case), case, case.components)


@pytest.fixture(scope="module")
def engine(db_path: Path, db_sha: str) -> Iterable[tp.ParallelEquilibrium]:
    """Один пул на весь модуль: подъём воркеров стоит разбора базы в каждом."""
    instance = tp.ParallelEquilibrium(db_path, db_sha, workers=2)
    try:
        yield instance
    finally:
        instance.close()


# --------------------------------------------------------------------------- #
# Отказы до запуска
# --------------------------------------------------------------------------- #


def test_worker_count_resolution() -> None:
    """``workers=None`` — ``cpu_count()-1``, но не меньше единицы."""
    assert tp.resolve_worker_count() == max(1, (os.cpu_count() or 1) - 1)
    assert tp.resolve_worker_count(1) == 1
    assert tp.resolve_worker_count(4) == 4
    with pytest.raises(ValueError):
        tp.resolve_worker_count(0)


def test_sha_mismatch_rejected_before_start(db_path: Path) -> None:
    """Несовпадение SHA-256 — отказ в конструкторе, до создания единственного процесса."""
    import psutil

    before = {child.pid for child in psutil.Process().children(recursive=True)}
    wrong = "0" * 64
    with pytest.raises(tp.DatabaseIdentityError) as failure:
        tp.ParallelEquilibrium(db_path, wrong, workers=2)
    after = {child.pid for child in psutil.Process().children(recursive=True)}

    assert "SHA-256" in str(failure.value)
    assert after == before, "Отказ по SHA не должен порождать процессы"


def test_missing_database_rejected(db_sha: str) -> None:
    """Отсутствующий файл базы — тот же отказ до запуска."""
    with pytest.raises(tp.DatabaseIdentityError):
        tp.ParallelEquilibrium(ROOT / "databases" / "нет-такой-базы.tdb", db_sha, workers=2)


def test_malformed_sha_rejected(db_path: Path) -> None:
    """Мусор вместо SHA-256 тоже отказывается до запуска, а не в воркере."""
    with pytest.raises(tp.DatabaseIdentityError):
        tp.ParallelEquilibrium(db_path, "не-хеш", workers=2)


def test_empty_points_return_empty(engine: tp.ParallelEquilibrium, case: BenchCase, phases: list[str]) -> None:
    """Пустой список точек не поднимает пул и возвращает пустой результат."""
    assert engine.map_points([], case.components, phases) == []


# --------------------------------------------------------------------------- #
# Совпадение режимов побайтово
# --------------------------------------------------------------------------- #


def test_sequential_and_parallel_agree_bytewise(db_path: Path, db_sha: str) -> None:
    """``workers=1`` и ``workers=3`` дают одинаковые доли фаз и составы фаз.

    Оба режима считаются в дочернем процессе с фиксированным ``PYTHONHASHSEED``:
    порядок обхода множеств строк внутри pycalphad зависит от хеш-затравки, а от
    него — порядок суммирования и последние биты чисел. Воркерам затравку ставит
    сам движок (``DEFAULT_HASH_SEED``), родителю её может задать только запуск
    интерпретатора, поэтому тест и запускает отдельный процесс.
    """
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = tp.DEFAULT_HASH_SEED
    environment["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--identity"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        timeout=900,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    payload = json.loads(completed.stdout)

    assert payload["sequential"]["ok"] == [True] * payload["point_count"]
    assert payload["parallel"]["ok"] == [True] * payload["point_count"]
    assert payload["sequential"]["canonical"] == payload["parallel"]["canonical"], (
        "Числа режимов разошлись:\n"
        f"workers=1: {json.dumps(payload['sequential']['canonical'], ensure_ascii=False)[:800]}\n"
        f"workers=N: {json.dumps(payload['parallel']['canonical'], ensure_ascii=False)[:800]}"
    )
    assert payload["sequential"]["digest"] == payload["parallel"]["digest"]
    # Физика на месте: Ni–15Al при 600–800 °C — это FCC_A1 + GAMMA_PRIME,
    # доля γ′ падает с нагревом (backend_reference: 0.33871 → 0.26115).
    assert payload["gamma_prime"] == sorted(payload["gamma_prime"], reverse=True)
    assert 0.25 < payload["gamma_prime"][0] < 0.40


def test_parallel_repeats_bytewise(engine: tp.ParallelEquilibrium, case: BenchCase, phases: list[str]) -> None:
    """Повторный расчёт тех же точек тем же пулом даёт тот же результат побайтово."""
    points = scan_points(case, 2)
    first = engine.map_points(points, case.components, phases)
    second = engine.map_points(points, case.components, phases)
    assert tp.canonical_digest(first) == tp.canonical_digest(second)


# --------------------------------------------------------------------------- #
# Изоляция ошибок, порядок, прогресс
# --------------------------------------------------------------------------- #


def test_failed_point_is_isolated(engine: tp.ParallelEquilibrium, case: BenchCase, phases: list[str]) -> None:
    """Одна упавшая точка не валит остальные и не рушит пул."""
    good = scan_points(case, 2)
    # Первая плохая точка переопределена по составу (заданы обе доли бинарной
    # системы) — pycalphad отказывает по числу степеней свободы; вторая вовсе без
    # температуры — отказывает билдер условий, ещё до солвера.
    points = [
        good[0],
        {"T": 973.15, "X": {"AL": 0.15, "NI": 0.85}},
        good[1],
        {"P": 101325.0},
    ]

    results = engine.map_points(points, case.components, phases)

    assert [result.index for result in results] == [0, 1, 2, 3]
    assert [result.ok for result in results] == [True, False, True, False]
    assert results[0].phase_fractions and results[2].phase_fractions
    assert results[1].error and results[1].error_type
    # Точка без температуры отбивается билдером условий, а не солвером.
    assert results[3].error_type == "ValueError"
    assert "T" in str(results[3].error)
    # Пул остался рабочим.
    assert engine.pool_is_open
    assert engine.map_points(good[:1], case.components, phases)[0].ok


def test_order_preserved_and_progress_reported(
    engine: tp.ParallelEquilibrium,
    case: BenchCase,
    phases: list[str],
) -> None:
    """Результаты идут в порядке точек, прогресс приходит на каждую точку."""
    points = scan_points(case, 4)
    seen: list[tuple[int, int, int]] = []

    results = engine.map_points(
        points,
        case.components,
        phases,
        progress_callback=lambda completed, total, result: seen.append(
            (completed, total, result.index)
        ),
    )

    assert [result.index for result in results] == [0, 1, 2, 3]
    assert [completed for completed, _total, _index in seen] == [1, 2, 3, 4]
    assert {total for _completed, total, _index in seen} == {4}
    assert sorted(index for _completed, _total, index in seen) == [0, 1, 2, 3]
    # Температуры в условиях точек — те, что были заданы, и в том же порядке.
    assert [round(result.conditions["T"], 6) for result in results] == [
        round(float(point["T"]), 6) for point in points
    ]


# --------------------------------------------------------------------------- #
# Жизненный цикл пула
# --------------------------------------------------------------------------- #


def _still_running(pids: Sequence[int]) -> list[int]:
    """PID из списка, которые ещё живы: не завершены и не зомби.

    На Windows зомби как состояния нет — процесс либо есть, либо нет; проверка
    статуса оставлена ради переносимости на POSIX, где ``join()`` обязан пожать
    завершившегося воркера.
    """
    import psutil

    alive: list[int] = []
    for pid in pids:
        try:
            process = psutil.Process(pid)
            if process.status() != psutil.STATUS_ZOMBIE:
                alive.append(pid)
        except psutil.NoSuchProcess:
            continue
    return alive


def test_pool_is_reused_between_calls(engine: tp.ParallelEquilibrium, case: BenchCase, phases: list[str]) -> None:
    """Второй вызов в той же сессии не поднимает новых воркеров."""
    points = scan_points(case, 2)
    engine.map_points(points, case.components, phases)
    first_pids = engine.worker_pids()
    engine.map_points(points, case.components, phases)
    second_pids = engine.worker_pids()

    # Воркеры поднимаются по мере поступления заданий, поэтому их не больше,
    # чем точек в первом вызове.
    assert 0 < len(first_pids) <= engine.workers == 2
    assert first_pids == second_pids


def test_pool_closes_without_zombies(db_path: Path, db_sha: str, case: BenchCase, phases: list[str]) -> None:
    """После ``close()`` воркеров не остаётся: ни живых, ни зомби."""
    import psutil

    parent = psutil.Process()
    before = {child.pid for child in parent.children(recursive=True)}

    instance = tp.ParallelEquilibrium(db_path, db_sha, workers=2)
    instance.map_points(scan_points(case, 2), case.components, phases)
    pids = instance.worker_pids()
    assert 0 < len(pids) <= 2
    during = {child.pid for child in parent.children(recursive=True)}
    assert set(pids) <= during

    instance.close()

    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        after = {child.pid for child in parent.children(recursive=True)}
        if not (after - before) and not _still_running(pids):
            break
        time.sleep(0.2)

    after = {child.pid for child in parent.children(recursive=True)}
    assert after - before == set(), f"Остались дочерние процессы: {sorted(after - before)}"
    assert _still_running(pids) == [], f"Воркеры пережили close(): {_still_running(pids)}"
    assert not instance.pool_is_open
    instance.close()  # повторный close идемпотентен


def test_dead_worker_is_reported_and_pool_recovers(
    db_path: Path,
    db_sha: str,
    case: BenchCase,
    phases: list[str],
) -> None:
    """Смерть воркера — понятная ошибка и новый пул, а не подвисание.

    Ради этого пул и построен на ``ProcessPoolExecutor``: у ``multiprocessing.Pool``
    убитый воркер уносит задание с собой, а пул молча поднимает замену и ждёт
    результат, которого уже не будет.
    """
    import psutil

    with tp.ParallelEquilibrium(db_path, db_sha, workers=2) as instance:
        points = scan_points(case, 2)
        instance.map_points(points, case.components, phases)
        pids = instance.worker_pids()
        assert pids
        psutil.Process(pids[0]).kill()

        deadline = time.monotonic() + 60.0
        lost: tp.WorkerLostError | None = None
        while time.monotonic() < deadline:
            try:
                instance.map_points(points, case.components, phases)
            except tp.WorkerLostError as error:
                lost = error
                break
        assert lost is not None, "Смерть воркера не была замечена"
        assert not instance.pool_is_open

        # Следующий вызов поднимает новый пул и считает как ни в чём не бывало.
        recovered = instance.map_points(points, case.components, phases)
        assert [result.ok for result in recovered] == [True, True]
        assert set(instance.worker_pids()).isdisjoint(pids)


def test_context_manager_closes_pool(db_path: Path, db_sha: str, case: BenchCase, phases: list[str]) -> None:
    """Контекст-менеджер закрывает пул и запрещает новые расчёты."""
    with tp.ParallelEquilibrium(db_path, db_sha, workers=2) as instance:
        instance.map_points(scan_points(case, 1), case.components, phases)
        assert instance.pool_is_open
    assert not instance.pool_is_open
    with pytest.raises(tp.ParallelEngineError):
        instance.map_points(scan_points(case, 1), case.components, phases)


def test_shared_engine_is_a_singleton(db_path: Path, db_sha: str) -> None:
    """``shared_engine`` отдаёт один и тот же движок на ключ (путь, SHA, воркеры)."""
    try:
        first = tp.shared_engine(db_path, db_sha, workers=2)
        second = tp.shared_engine(db_path, db_sha, workers=2)
        other = tp.shared_engine(db_path, db_sha, workers=3)
        assert first is second
        assert other is not first
    finally:
        tp.close_shared_engines()


def test_hash_seed_restored_after_close(db_path: Path, db_sha: str, case: BenchCase, phases: list[str]) -> None:
    """Движок возвращает ``PYTHONHASHSEED`` родителя в исходное состояние."""
    before = os.environ.get("PYTHONHASHSEED")
    with tp.ParallelEquilibrium(db_path, db_sha, workers=2) as instance:
        instance.map_points(scan_points(case, 1), case.components, phases)
        assert os.environ.get("PYTHONHASHSEED") == tp.DEFAULT_HASH_SEED
    assert os.environ.get("PYTHONHASHSEED") == before


# --------------------------------------------------------------------------- #
# Прогон совпадения режимов (дочерний процесс) и бенчмарк
# --------------------------------------------------------------------------- #


def _identity_report(point_count: int = 4, workers: int = 3) -> dict[str, Any]:
    """Посчитать одни и те же точки в двух режимах и вернуть канонические числа."""
    case = TEST_CASE
    path = ROOT / case.relative_path
    sha = tp.file_sha256(path)
    phase_list = effective_phases(parse_database(case), case, case.components)
    points = scan_points(case, point_count)

    with tp.ParallelEquilibrium(path, sha, workers=1) as sequential:
        first = sequential.map_points(points, case.components, phase_list)
    with tp.ParallelEquilibrium(path, sha, workers=workers) as parallel:
        second = parallel.map_points(points, case.components, phase_list)

    return {
        "point_count": point_count,
        "workers": workers,
        "gamma_prime": [result.phase_fractions.get("GAMMA_PRIME", 0.0) for result in first],
        "sequential": {
            "ok": [result.ok for result in first],
            "canonical": [result.canonical() for result in first],
            "digest": tp.canonical_digest(first),
        },
        "parallel": {
            "ok": [result.ok for result in second],
            "canonical": [result.canonical() for result in second],
            "digest": tp.canonical_digest(second),
        },
    }


def _worker_rss_mb(engine: tp.ParallelEquilibrium) -> list[int]:
    """RSS воркеров в мегабайтах: цена памяти у параллельного режима своя."""
    import psutil

    sizes: list[int] = []
    for pid in engine.worker_pids():
        try:
            sizes.append(round(psutil.Process(pid).memory_info().rss / 2**20))
        except psutil.Error:
            continue
    return sorted(sizes, reverse=True)


def _bench_leg(
    path: Path,
    sha: str,
    workers: int,
    points: list[dict[str, Any]],
    components: Sequence[str],
    phase_list: Sequence[str],
    pdens: int,
    reuse_models: bool,
) -> dict[str, Any]:
    """Один замер: холодный прогон (с подъёмом пула) и тёплый (пул уже поднят)."""
    engine = tp.ParallelEquilibrium(path, sha, workers=workers)
    try:
        cold_started = time.perf_counter()
        results = engine.map_points(
            points, components, phase_list, pdens=pdens, reuse_models=reuse_models
        )
        cold = time.perf_counter() - cold_started

        # Тёплый прогон только у параллельного режима: он показывает цену точек
        # без подъёма пула. Последовательному режиму пул не нужен, его «тёплое»
        # время — то же холодное за вычетом разбора базы.
        warm: float | None = None
        if workers > 1:
            warm_started = time.perf_counter()
            engine.map_points(
                points, components, phase_list, pdens=pdens, reuse_models=reuse_models
            )
            warm = time.perf_counter() - warm_started
        worker_rss_mb = _worker_rss_mb(engine)
    finally:
        engine.close()

    failures = [result.index for result in results if not result.ok]
    return {
        "workers": workers,
        "cold_s": cold,
        "warm_s": warm,
        "cold_point_s": cold / len(points),
        "warm_point_s": None if warm is None else warm / len(points),
        "worker_rss_mb": worker_rss_mb,
        "worker_rss_sum_mb": sum(worker_rss_mb),
        "failures": failures,
        "digest": tp.canonical_digest(results),
    }


def _run_bench() -> dict[str, Any]:
    """T-скан 20 точек и карта 5×5 на трёх базах, ``workers=1`` против ``cpu_count()-1``."""
    import psutil

    parallel_workers = int(
        os.environ.get("THERMOGAR_PARALLEL_BENCH_WORKERS") or tp.resolve_worker_count()
    )
    selected_databases = tuple(
        key.strip().lower()
        for key in (os.environ.get("THERMOGAR_PARALLEL_BENCH_DBS") or ",".join(CASES)).split(",")
        if key.strip()
    )
    legs = tuple(
        int(value)
        for value in (
            os.environ.get("THERMOGAR_PARALLEL_BENCH_LEGS") or f"1,{parallel_workers}"
        ).split(",")
        if value.strip()
    )
    report: dict[str, Any] = {
        "cpu_count": os.cpu_count(),
        "workers": parallel_workers,
        "databases": list(selected_databases),
        "legs": list(legs),
        "python": sys.version.split()[0],
        "memory_total_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "memory_available_gb": round(psutil.virtual_memory().available / 2**30, 1),
        "scenarios": [],
    }

    for key, case in CASES.items():
        if key not in selected_databases:
            continue
        path = ROOT / case.relative_path
        if not path.is_file():
            continue
        sha = tp.file_sha256(path)

        parse_started = time.perf_counter()
        database = parse_database(case)
        parse_s = time.perf_counter() - parse_started

        scenarios = (
            ("T-скан 20 точек", scan_points(case, 20), case.components, 500, False),
            ("карта 5×5", map_points(case, 5), case.map_components, 50, True),
        )
        for name, points, components, pdens, reuse_models in scenarios:
            phase_list = effective_phases(database, case, components)
            entry: dict[str, Any] = {
                "database": key,
                "label": case.label,
                "scenario": name,
                "points": len(points),
                "phases": len(phase_list),
                "pdens": pdens,
                "parse_s": parse_s,
            }
            for workers in legs:
                try:
                    leg = _bench_leg(
                        path, sha, workers, points, components, phase_list, pdens, reuse_models
                    )
                except tp.ParallelEngineError as error:
                    # Чаще всего это нехватка памяти на N процессов: замер ломается,
                    # но остальные сценарии считать имеет смысл.
                    entry[f"w{workers}"] = {"workers": workers, "error": str(error)}
                    print(f"{key:>2} | {name:<16} | workers={workers:>2} | ОТКАЗ: {error}", flush=True)
                    continue
                entry[f"w{workers}"] = leg
                warm_text = "—" if leg["warm_s"] is None else f"{leg['warm_s']:.1f} с"
                print(
                    f"{key:>2} | {name:<16} | workers={workers:>2} | "
                    f"холодный {leg['cold_s']:8.1f} с | тёплый {warm_text:>9} | "
                    f"RSS×{len(leg['worker_rss_mb'])} {leg['worker_rss_sum_mb']} МБ | "
                    f"ошибок {len(leg['failures'])}",
                    flush=True,
                )
            sequential = entry.get("w1")
            parallel = entry.get(f"w{parallel_workers}")
            if (
                sequential is None
                or parallel is None
                or "error" in sequential
                or "error" in parallel
            ):
                report["scenarios"].append(entry)
                continue
            entry["speedup_cold"] = sequential["cold_s"] / parallel["cold_s"]
            entry["speedup_warm"] = sequential["cold_s"] / parallel["warm_s"]
            entry["same_numbers"] = sequential["digest"] == parallel["digest"]
            # Порог окупаемости: n·t1 = init + n·tN. init — цена подъёма пула
            # (разность холодного и тёплого прогонов), tN — тёплая цена точки.
            init_s = max(0.0, parallel["cold_s"] - parallel["warm_s"])
            per_point_gain = sequential["cold_point_s"] - parallel["warm_point_s"]
            entry["init_s"] = init_s
            entry["breakeven_points"] = (
                init_s / per_point_gain if per_point_gain > 0 else float("inf")
            )
            report["scenarios"].append(entry)

    return report


def _main(argv: list[str]) -> int:
    if "--identity" in argv:
        print(json.dumps(_identity_report(), ensure_ascii=False))
        return 0
    if "--bench" in argv:
        report = _run_bench()
        destination = os.environ.get("THERMOGAR_PARALLEL_BENCH_JSON")
        if destination:
            Path(destination).write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
