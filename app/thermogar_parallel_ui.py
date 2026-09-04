"""Мост между приложением и параллельным движком равновесий.

Движок (``thermogar_parallel``) не знает ни про Streamlit, ни про таблицы
приложения: он считает точки и отдаёт словари. Здесь собрано всё, что нужно
приложению, чтобы этими точками пользоваться:

* переходник ``EquilibriumSnapshot`` — объект с ``Phase``/``NP``/``X``/``Y``,
  который принимают уже существующие функции сборки результата
  (``summarize_equilibrium``, ``aggregate_phase_fractions``,
  ``thermogar_physical.calculate_physical_properties``). Сами функции не
  меняются, поэтому таблицы с движком и без него совпадают побайтово;
* выбор числа воркеров и переключатель в сайдбаре;
* порог, ниже которого пул не окупается и точки считаются в процессе;
* прогресс «точка i из N» и досчёт остатка, если пул отказал.

Пул не сериализуется и в ``st.session_state`` лежать не может: он живёт
одиночкой на процесс (``thermogar_parallel.shared_engine``) и переживает
перезапуск скрипта Streamlit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import streamlit as st

import thermogar_parallel as parallel_engine
from thermogar_parallel import (
    DEFAULT_PDENS,
    ParallelEngineError,
    PointResult,
    close_shared_engines,
)


# Порог окупаемости пула (замеры волны 5B, tools/bench_parallel.md): подъём
# пула стоит 14–30 с, поэтому он оправдан тем раньше, чем дороже одна точка.
# Точка Al стоит 12–19 с, точка Fe 4–11 с, точка Ni 1.5–3 с.
POOL_THRESHOLD_POINTS = 4
POOL_THRESHOLD_BY_DATABASE = {"al": 2}

MODE_AUTO = "auto"
MODE_OFF = "off"
SIDEBAR_STATE_KEY = "thermogar_parallel_mode"

_WORKER_COUNT: int | None = None


# ---------------------------------------------------------------------------
# Переходник: результат движка там, где приложение ждёт объект equilibrium
# ---------------------------------------------------------------------------


class _Array:
    """Обёртка ``.values``: у ``xarray`` результат равновесия читается так."""

    __slots__ = ("values",)

    def __init__(self, values: Any) -> None:
        self.values = values


class _Compositions:
    """``eq.X.sel(component=…)`` — составы вершин по одному компоненту."""

    __slots__ = ("_columns",)

    def __init__(self, columns: Mapping[str, Sequence[float]]) -> None:
        self._columns = columns

    def sel(self, component: str) -> _Array:
        name = str(component)
        if name not in self._columns:
            raise KeyError(f"В результате нет компонента {name!r}.")
        return _Array(np.asarray(self._columns[name], dtype=float))


class EquilibriumSnapshot:
    """Сырые массивы точки в виде, который принимают функции приложения.

    Движок возвращает списки чисел, а ``summarize_equilibrium``,
    ``aggregate_phase_fractions`` и ``calculate_physical_properties`` читают
    ``eq.Phase.values``, ``eq.NP.values``, ``eq.X.sel(component=…).values`` и
    ``eq.Y.values``. Переходник отдаёт ровно эти четыре имени и ничего больше:
    числа те же самые, поэтому таблицы совпадают побайтово.
    """

    __slots__ = ("Phase", "NP", "X", "Y")

    def __init__(self, arrays: Mapping[str, Any]) -> None:
        self.Phase = _Array(np.asarray(arrays["phase"], dtype=str))
        self.NP = _Array(np.asarray(arrays["np"], dtype=float))
        self.X = _Compositions(arrays["x"])
        rows = arrays.get("y")
        self.Y = _Array(
            np.asarray(float("nan"))
            if rows is None
            else np.asarray(rows, dtype=float)
        )


def snapshot_of(result: PointResult) -> EquilibriumSnapshot:
    """Переходник для успешной точки; на упавшей точке поднимает её ошибку."""
    if not result.ok:
        raise RuntimeError(result.error or "Точка не рассчитана.")
    if result.arrays is None:
        raise RuntimeError(
            "Движок не вернул массивы равновесия: расчёт запрошен без capture."
        )
    return EquilibriumSnapshot(result.arrays)


# ---------------------------------------------------------------------------
# Число воркеров и переключатель в сайдбаре
# ---------------------------------------------------------------------------


def pool_worker_count() -> int:
    """Число воркеров: считается один раз на процесс, при первом обращении."""
    global _WORKER_COUNT
    if _WORKER_COUNT is None:
        _WORKER_COUNT = parallel_engine.auto_worker_count()
    return int(_WORKER_COUNT)


def workers_label(workers: int) -> str:
    tail = workers % 10
    hundred = workers % 100
    if tail == 1 and hundred != 11:
        word = "воркер"
    elif tail in (2, 3, 4) and hundred not in (12, 13, 14):
        word = "воркера"
    else:
        word = "воркеров"
    return f"{workers} {word}"


def parallel_mode() -> str:
    return (
        MODE_OFF
        if st.session_state.get(SIDEBAR_STATE_KEY, MODE_AUTO) == MODE_OFF
        else MODE_AUTO
    )


def render_sidebar_control() -> str:
    """Переключатель «Параллельный расчёт»: авто или выкл., без ручного числа."""
    workers = pool_worker_count()
    if st.session_state.get(SIDEBAR_STATE_KEY) not in (MODE_AUTO, MODE_OFF):
        st.session_state[SIDEBAR_STATE_KEY] = MODE_AUTO
    mode = st.sidebar.radio(
        "Параллельный расчёт",
        options=[MODE_AUTO, MODE_OFF],
        format_func=lambda value: (
            f"авто ({workers_label(workers)})" if value == MODE_AUTO else "выкл."
        ),
        horizontal=True,
        key=SIDEBAR_STATE_KEY,
    )
    if mode == MODE_AUTO and workers > 1:
        st.sidebar.caption(
            "Сканы, карта, плотность по температуре и пакетный расчёт считают "
            "точки в пуле процессов. Число воркеров выбрано по свободной "
            "памяти; числа в обоих режимах одинаковы."
        )
    elif mode == MODE_AUTO:
        st.sidebar.caption(
            "Свободной памяти хватает только на один процесс — точки "
            "считаются последовательно."
        )
    return mode


def pool_threshold(database_key: str) -> int:
    return POOL_THRESHOLD_BY_DATABASE.get(str(database_key), POOL_THRESHOLD_POINTS)


# ---------------------------------------------------------------------------
# Расчёт набора точек
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PointRun:
    """Результаты набора точек вместе с тем, как они были получены."""

    results: list[PointResult]
    workers: int
    used_pool: bool
    fallback_reason: str = ""
    seconds: float = 0.0

    @property
    def note(self) -> str:
        if self.fallback_reason:
            return (
                f"Пул процессов отказал ({self.fallback_reason}); "
                "оставшиеся точки досчитаны последовательно."
            )
        if self.used_pool:
            return f"Параллельный расчёт: {workers_label(self.workers)}."
        return "Последовательный расчёт в одном процессе."


def _progress_bridge(
    progress: Callable[[int, int], None] | None,
) -> Callable[[int, int, PointResult], None] | None:
    if progress is None:
        return None

    def report(completed: int, total: int, _result: PointResult) -> None:
        progress(completed, total)

    return report


def run_points(
    *,
    database: Any,
    database_path: str | Path,
    sha256: str,
    database_key: str,
    points: Sequence[Mapping[str, Any]],
    components: Sequence[str],
    phases: Sequence[str],
    pdens: int = DEFAULT_PDENS,
    reuse_models: bool = False,
    capture: Sequence[str] = ("X",),
    progress: Callable[[int, int], None] | None = None,
    models: Any | None = None,
) -> PointRun:
    """Посчитать точки: в пуле, если он окупается, иначе в текущем процессе.

    ``database`` — уже разобранная база приложения: последовательный режим не
    должен платить за повторный разбор TDB (3–7 с). Пул разбирает базу у себя
    сам и сверяет её SHA-256.

    Любой отказ пула (нехватка памяти, ``WorkerLostError``) не теряет расчёт:
    вернувшиеся точки сохраняются, остальные досчитываются последовательно.
    """
    prepared = [dict(point) for point in points]
    total = len(prepared)
    started = time.perf_counter()
    if total == 0:
        return PointRun([], workers=1, used_pool=False)

    workers = pool_worker_count() if parallel_mode() == MODE_AUTO else 1
    if workers < 2 or total < pool_threshold(database_key):
        results = parallel_engine.solve_points_in_process(
            database,
            prepared,
            components,
            phases,
            pdens=pdens,
            reuse_models=reuse_models,
            capture=capture,
            models=models,
            progress_callback=_progress_bridge(progress),
        )
        return PointRun(
            results,
            workers=1,
            used_pool=False,
            seconds=time.perf_counter() - started,
        )

    engine = parallel_engine.shared_engine(database_path, sha256, workers=workers)
    try:
        results = engine.map_points(
            prepared,
            components,
            phases,
            pdens=pdens,
            reuse_models=reuse_models,
            capture=capture,
            progress_callback=_progress_bridge(progress),
        )
        return PointRun(
            results,
            workers=workers,
            used_pool=True,
            seconds=time.perf_counter() - started,
        )
    except ParallelEngineError as error:
        done = {item.index: item for item in getattr(error, "partial", [])}
        missing = [index for index in range(total) if index not in done]
        already = len(done)

        def report(position: int, _total: int, _result: PointResult) -> None:
            if progress is not None:
                progress(already + position, total)

        rest = parallel_engine.solve_points_in_process(
            database,
            [prepared[index] for index in missing],
            components,
            phases,
            pdens=pdens,
            reuse_models=reuse_models,
            capture=capture,
            models=models,
            indices=missing,
            progress_callback=report,
        )
        for item in rest:
            done[item.index] = item
        reason = str(error).split(":", 1)[0].strip() or type(error).__name__
        return PointRun(
            [done[index] for index in range(total)],
            workers=workers,
            used_pool=True,
            fallback_reason=reason,
            seconds=time.perf_counter() - started,
        )


__all__ = (
    "EquilibriumSnapshot",
    "MODE_AUTO",
    "MODE_OFF",
    "POOL_THRESHOLD_BY_DATABASE",
    "POOL_THRESHOLD_POINTS",
    "PointRun",
    "close_shared_engines",
    "parallel_mode",
    "pool_threshold",
    "pool_worker_count",
    "render_sidebar_control",
    "run_points",
    "snapshot_of",
    "workers_label",
)
