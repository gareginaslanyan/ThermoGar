"""Параллельный движок равновесий ThermoGar: точки скана/карты/batch в пуле процессов.

Точки скана, узлы карты и строки пакетного расчёта независимы, поэтому их можно
считать в пуле процессов. Модуль импортируемый и самодостаточный: на Windows
``multiprocessing`` работает через ``spawn``, а значит функция-воркер обязана
жить в модуле, который дочерний процесс может импортировать по имени
(``app\\ThermoGar_app.py`` — top-level Streamlit-скрипт, он для этого непригоден).

Численный бэкенд тот же, что и в приложении: ``pycalphad.equilibrium`` с
``calc_opts={"pdens": …}`` (по умолчанию 500, как в ``direct_equilibrium_scan``
и в ``thermogar_verified_equilibrium._default_backend``). Одна и та же функция
``_solve_point`` выполняется и в последовательном режиме (``workers=1``), и в
воркере, поэтому числа режимов совпадают побайтово — при условии одинаковой
хеш-затравки процессов (см. ``DEFAULT_HASH_SEED``).

База данных разбирается в каждом воркере ровно один раз, в ``initializer``:
разбор TDB стоит 3–7 с, повторять его на каждую точку нельзя. Перед разбором
воркер сверяет SHA-256 файла с тем, что объявил вызывающий; родитель делает ту же
проверку до создания пула, поэтому несовпадение базы отказывает до запуска.

Через ``pickle`` не передаются ни ``Database``, ни объекты ``xarray``: наружу
возвращаются только простые словари и списки.

Интеграции в UI в этой волне нет — ``ThermoGar_app.py`` модуль не импортирует.
"""

from __future__ import annotations

import atexit
import concurrent.futures
import hashlib
import json
import multiprocessing
import os
import time
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

DEFAULT_PRESSURE_PA = 101325.0
DEFAULT_SYSTEM_SIZE = 1.0
DEFAULT_PDENS = 500
PHASE_FRACTION_FLOOR = 1e-10
# Хеш-затравка воркеров. pycalphad местами обходит множества строк, а порядок
# обхода зависит от PYTHONHASHSEED, поэтому у процессов с разной затравкой
# порядок суммирования отличается и числа расходятся в последних битах.
# Фиксированная затравка делает воркеры воспроизводимыми между собой и от
# запуска к запуску; с последовательным режимом они совпадают побайтово,
# если родительский процесс запущен с тем же PYTHONHASHSEED.
DEFAULT_HASH_SEED = "0"

_SHA_CHUNK_BYTES = 1 << 20


class ParallelEngineError(RuntimeError):
    """Отказ движка до запуска расчёта (не ошибка отдельной точки)."""


class DatabaseIdentityError(ParallelEngineError):
    """Файл базы не совпал с объявленным SHA-256 либо недоступен."""


class WorkerLostError(ParallelEngineError):
    """Воркер умер вместе с заданием: чаще всего это нехватка памяти."""


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------


def file_sha256(path: str | os.PathLike[str]) -> str:
    """SHA-256 файла базы; читается кусками, TDB бывает на десятки мегабайт."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_SHA_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def resolve_worker_count(workers: int | None = None) -> int:
    """Число воркеров: явное значение либо ``cpu_count() - 1``, но не меньше 1."""
    if workers is None:
        return max(1, (os.cpu_count() or 1) - 1)
    value = int(workers)
    if value < 1:
        raise ValueError("Число воркеров не может быть меньше 1.")
    return value


def _verify_database(database_path: str | os.PathLike[str], sha256: str) -> Path:
    path = Path(database_path)
    expected = str(sha256).strip().lower()
    if len(expected) != 64 or any(symbol not in "0123456789abcdef" for symbol in expected):
        raise DatabaseIdentityError(
            f"SHA-256 базы задан неверно: {sha256!r} (нужны 64 шестнадцатеричных символа)."
        )
    if not path.is_file():
        raise DatabaseIdentityError(f"Файл базы не найден: {path}")
    actual = file_sha256(path)
    if actual != expected:
        raise DatabaseIdentityError(
            "SHA-256 базы не совпал: объявлено "
            f"{expected}, у файла {actual} ({path})."
        )
    return path


# ---------------------------------------------------------------------------
# Результат точки
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PointResult:
    """Результат одной точки. Только простые типы — уходит через ``pickle``."""

    index: int
    ok: bool
    phase_fractions: dict[str, float] = field(default_factory=dict)
    phase_compositions: dict[str, dict[str, float]] = field(default_factory=dict)
    conditions: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None
    seconds: float = 0.0
    pid: int = 0

    def canonical(self) -> dict[str, Any]:
        """Каноническая форма для побитового сравнения режимов.

        Времена и pid исключены: они по определению разные. Числа выводятся
        через ``float.hex()`` — это точное представление, а не округление.
        """
        return {
            "index": self.index,
            "ok": self.ok,
            "error_type": self.error_type,
            "conditions": {
                key: float(value).hex()
                for key, value in sorted(self.conditions.items())
            },
            "phase_fractions": {
                phase: float(value).hex()
                for phase, value in sorted(self.phase_fractions.items())
            },
            "phase_compositions": {
                phase: {
                    element: float(value).hex()
                    for element, value in sorted(composition.items())
                }
                for phase, composition in sorted(self.phase_compositions.items())
            },
        }


def canonical_digest(results: Iterable[PointResult]) -> str:
    """SHA-256 канонической формы списка результатов: одно число для сравнения прогонов."""
    payload = json.dumps(
        [result.canonical() for result in results],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _Job:
    """Неизменная часть задания, одинаковая для всех точек одного вызова."""

    components: tuple[str, ...]
    phases: tuple[str, ...]
    pdens: int
    conditions_builder: Callable[[Mapping[str, Any], Any], Mapping[Any, float]]
    reuse_models: bool


# ---------------------------------------------------------------------------
# Условия точки
# ---------------------------------------------------------------------------


def default_conditions_builder(
    point: Mapping[str, Any],
    database: Any,
) -> dict[Any, float]:
    """Условия ``pycalphad`` из простого описания точки.

    Точка — обычный словарь (он же уходит в воркер через ``pickle``):

    ``{"T": 973.15}`` — температура в кельвинах, обязательна;
    ``{"P": 101325.0, "N": 1.0}`` — необязательные, значения по умолчанию те же,
    что в приложении;
    ``{"X": {"AL": 0.15}}`` — мольные доли независимых компонентов;
    ``{"W": {"CU": 0.04, "MG": 0.01}, "balance": "AL"}`` — массовые доли, перевод
    тот же, что в ``ThermoGar_app.scan_axis_conditions`` (``v.get_mole_fractions``).

    ``X`` и ``W`` одновременно не допускаются.
    """
    from pycalphad import variables as v

    if "T" not in point:
        raise ValueError("В описании точки нет температуры 'T' (К).")

    conditions: dict[Any, float] = {
        v.N: float(point.get("N", DEFAULT_SYSTEM_SIZE)),
        v.P: float(point.get("P", DEFAULT_PRESSURE_PA)),
        v.T: float(point["T"]),
    }

    mole = point.get("X") or {}
    mass = point.get("W") or {}
    if mole and mass:
        raise ValueError("В описании точки заданы сразу 'X' и 'W'.")

    if mole:
        conditions.update(
            {v.X(str(element)): float(value) for element, value in mole.items()}
        )
    elif mass:
        balance = str(point.get("balance", "")).strip().upper()
        if not balance:
            raise ValueError("Для массовых долей 'W' нужен 'balance'.")
        mass_conditions = {
            v.W(str(element)): float(value) for element, value in mass.items()
        }
        conditions.update(dict(v.get_mole_fractions(mass_conditions, balance, database)))

    return conditions


def _plain_conditions(conditions: Mapping[Any, float]) -> dict[str, float]:
    """Условия в виде строковых ключей — обратно через ``pickle`` идёт только это."""
    return {str(key): float(value) for key, value in conditions.items()}


# ---------------------------------------------------------------------------
# Решение одной точки (общее для последовательного режима и воркера)
# ---------------------------------------------------------------------------


def _aggregate(
    equilibrium_result: Any,
    components: Sequence[str],
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Доли фаз и составы фаз из результата ``equilibrium``.

    Свёртка долей повторяет ``ThermoGar_app.aggregate_phase_fractions``: одинаковые
    имена фаз складываются, пустые имена и нефизичные доли отбрасываются. Состав
    фазы усредняется по её вершинам с весами долей.
    """
    import numpy as np

    names = np.asarray(equilibrium_result.Phase.values, dtype=str).ravel()
    fractions = np.asarray(equilibrium_result.NP.values, dtype=float).ravel()
    elements = [element for element in components if element != "VA"]
    phase_x = {
        element: np.asarray(
            equilibrium_result.X.sel(component=element).values, dtype=float
        ).ravel()
        for element in elements
    }

    aggregated: dict[str, float] = {}
    weighted: dict[str, dict[str, float]] = {}
    for position, (raw_name, raw_fraction) in enumerate(zip(names, fractions)):
        name = str(raw_name)
        fraction = float(raw_fraction)
        if name == "" or not np.isfinite(fraction) or fraction <= PHASE_FRACTION_FLOOR:
            continue
        aggregated[name] = aggregated.get(name, 0.0) + fraction
        bucket = weighted.setdefault(name, {element: 0.0 for element in elements})
        for element in elements:
            value = float(phase_x[element][position])
            if np.isfinite(value):
                bucket[element] += fraction * value

    compositions = {
        name: {
            element: (value / aggregated[name] if aggregated[name] > 0.0 else 0.0)
            for element, value in bucket.items()
        }
        for name, bucket in weighted.items()
    }
    return aggregated, compositions


def _solve_point(
    database: Any,
    job: _Job,
    index: int,
    point: Mapping[str, Any],
    models: Any | None,
) -> PointResult:
    """Одна точка равновесия. Ошибка точки не поднимается наружу, а возвращается."""
    from pycalphad import equilibrium

    started = time.perf_counter()
    try:
        conditions = dict(job.conditions_builder(point, database))
        options: dict[str, Any] = {"calc_opts": {"pdens": int(job.pdens)}}
        if models is not None:
            options["model"] = models
        equilibrium_result = equilibrium(
            database,
            list(job.components),
            list(job.phases),
            conditions,
            **options,
        )
        fractions, compositions = _aggregate(equilibrium_result, job.components)
        return PointResult(
            index=index,
            ok=True,
            phase_fractions=fractions,
            phase_compositions=compositions,
            conditions=_plain_conditions(conditions),
            seconds=time.perf_counter() - started,
            pid=os.getpid(),
        )
    except Exception as error:  # одна упавшая точка не валит остальные
        return PointResult(
            index=index,
            ok=False,
            error=f"{type(error).__name__}: {error}",
            error_type=type(error).__name__,
            seconds=time.perf_counter() - started,
            pid=os.getpid(),
        )


# ---------------------------------------------------------------------------
# Воркер (spawn: импортируется дочерним процессом по имени модуля)
# ---------------------------------------------------------------------------

_WORKER_DATABASE: Any | None = None
_WORKER_SHA256: str = ""
_WORKER_MODELS: dict[tuple[Any, ...], Any] = {}


def _worker_init(database_path: str, sha256: str) -> None:
    """``initializer`` пула: сверить SHA-256 и разобрать базу ровно один раз."""
    global _WORKER_DATABASE, _WORKER_SHA256, _WORKER_MODELS

    path = _verify_database(database_path, sha256)
    from pycalphad import Database

    _WORKER_DATABASE = Database(str(path))
    _WORKER_SHA256 = str(sha256).strip().lower()
    _WORKER_MODELS = {}


def _worker_models(job: _Job) -> Any | None:
    """Кэш ``Model`` внутри воркера для карт: модели строятся один раз на задание."""
    if not job.reuse_models:
        return None

    key = (job.components, job.phases)
    cached = _WORKER_MODELS.get(key)
    if cached is None:
        from pycalphad import Model

        cached = {
            phase: Model(_WORKER_DATABASE, list(job.components), phase)
            for phase in job.phases
        }
        _WORKER_MODELS[key] = cached
    return cached


def _worker_solve(payload: tuple[str, _Job, int, Mapping[str, Any]]) -> PointResult:
    """Задание воркера: SHA сверяется до расчёта, база уже разобрана инициализатором."""
    sha256, job, index, point = payload
    if _WORKER_DATABASE is None:
        raise ParallelEngineError("Воркер не инициализирован: база не разобрана.")
    if _WORKER_SHA256 != str(sha256).strip().lower():
        raise DatabaseIdentityError("SHA-256 базы воркера не совпал с заданием.")
    return _solve_point(_WORKER_DATABASE, job, index, point, _worker_models(job))


# ---------------------------------------------------------------------------
# Движок
# ---------------------------------------------------------------------------


class ParallelEquilibrium:
    """Пул процессов для независимых точек равновесия.

    ``workers=1`` — последовательный режим в текущем процессе, пул не создаётся;
    ``workers=None`` — ``cpu_count() - 1``. Пул создаётся лениво при первом
    ``map_points`` и переиспользуется всеми последующими вызовами до ``close()``.

    ``hash_seed`` — значение ``PYTHONHASHSEED`` для воркеров (по умолчанию ``"0"``,
    ``None`` — наследовать родительское). Совпадение чисел с последовательным
    режимом побайтово требует, чтобы родительский процесс был запущен с тем же
    значением; при разной затравке расхождение появляется в последних битах
    (порядок обхода множеств строк внутри pycalphad).

        with ParallelEquilibrium(path, sha, workers=None) as engine:
            results = engine.map_points(points, components, phases)
    """

    def __init__(
        self,
        database_path: str | os.PathLike[str],
        sha256: str,
        workers: int | None = None,
        hash_seed: str | None = DEFAULT_HASH_SEED,
    ) -> None:
        # Проверка до запуска: несовпадение базы отказывает здесь, а не в воркере.
        self._database_path = _verify_database(database_path, sha256)
        self._sha256 = str(sha256).strip().lower()
        self._workers = resolve_worker_count(workers)
        self._hash_seed = None if hash_seed is None else str(hash_seed)
        self._saved_hash_seed: str | None = None
        self._hash_seed_applied = False
        self._pool: Any | None = None
        self._local_database: Any | None = None
        self._local_models: dict[tuple[Any, ...], Any] = {}
        self._closed = False
        _LIVE_ENGINES.add(self)

    # -- свойства ---------------------------------------------------------

    @property
    def database_path(self) -> Path:
        return self._database_path

    @property
    def sha256(self) -> str:
        return self._sha256

    @property
    def workers(self) -> int:
        return self._workers

    @property
    def hash_seed(self) -> str | None:
        return self._hash_seed

    @property
    def pool_is_open(self) -> bool:
        return self._pool is not None

    def worker_pids(self) -> list[int]:
        """PID поднятых воркеров; пустой список, если пула нет.

        Воркеры поднимаются по мере поступления заданий, поэтому сразу после
        создания движка список пуст, а после расчёта из ``k`` точек в нём не
        больше ``min(k, workers)`` процессов.
        """
        if self._pool is None:
            return []
        return sorted(int(pid) for pid in self._pool._processes)  # noqa: SLF001

    # -- жизненный цикл ---------------------------------------------------

    def _ensure_pool(self) -> Any:
        if self._closed:
            raise ParallelEngineError("Движок закрыт, пул больше не создаётся.")
        if self._pool is None:
            # Затравка ставится на всё время жизни пула: spawn читает окружение
            # родителя при старте воркера, в том числе когда пул поднимает
            # очередной процесс по мере поступления заданий.
            self._apply_hash_seed()
            try:
                # ProcessPoolExecutor, а не multiprocessing.Pool: у Pool смерть
                # воркера (нехватка памяти) и падение initializer оборачиваются
                # бесконечным перезапуском и подвисанием, а executor в обоих
                # случаях отдаёт BrokenProcessPool.
                self._pool = concurrent.futures.ProcessPoolExecutor(
                    max_workers=self._workers,
                    mp_context=multiprocessing.get_context("spawn"),
                    initializer=_worker_init,
                    initargs=(str(self._database_path), self._sha256),
                )
            except BaseException:
                self._restore_hash_seed()
                raise
        return self._pool

    def _apply_hash_seed(self) -> None:
        if self._hash_seed is None or self._hash_seed_applied:
            return
        self._saved_hash_seed = os.environ.get("PYTHONHASHSEED")
        os.environ["PYTHONHASHSEED"] = self._hash_seed
        self._hash_seed_applied = True

    def _drop_broken_pool(self) -> None:
        """Снять сломанный пул, не закрывая сам движок."""
        pool, self._pool = self._pool, None
        self._restore_hash_seed()
        if pool is not None:
            # wait=True, чтобы потоки executor'а закончились до возврата: при
            # wait=False служебный поток очереди заданий ещё какое-то время
            # шлёт в закрытый канал и сыпет в stderr "OSError: handle is closed"
            # (замерено: 10 трейсбеков против 2). Полностью этот шум CPython не
            # убирает ни в одном из режимов; на результат он не влияет.
            pool.shutdown(wait=True, cancel_futures=True)

    def _restore_hash_seed(self) -> None:
        if not self._hash_seed_applied:
            return
        if self._saved_hash_seed is None:
            os.environ.pop("PYTHONHASHSEED", None)
        else:
            os.environ["PYTHONHASHSEED"] = self._saved_hash_seed
        self._hash_seed_applied = False
        self._saved_hash_seed = None

    def _ensure_local_database(self) -> Any:
        """База для последовательного режима: разбирается один раз на движок."""
        if self._local_database is None:
            _verify_database(self._database_path, self._sha256)
            from pycalphad import Database

            self._local_database = Database(str(self._database_path))
        return self._local_database

    def _local_models_for(self, job: _Job) -> Any | None:
        if not job.reuse_models:
            return None
        key = (job.components, job.phases)
        cached = self._local_models.get(key)
        if cached is None:
            from pycalphad import Model

            database = self._ensure_local_database()
            cached = {
                phase: Model(database, list(job.components), phase)
                for phase in job.phases
            }
            self._local_models[key] = cached
        return cached

    def close(self) -> None:
        """Закрыть пул и дождаться воркеров. Идемпотентно, зомби не остаются."""
        pool, self._pool = self._pool, None
        self._closed = True
        self._local_database = None
        self._local_models = {}
        self._restore_hash_seed()
        if pool is None:
            return
        pool.shutdown(wait=True, cancel_futures=True)

    def __enter__(self) -> "ParallelEquilibrium":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    # -- расчёт -----------------------------------------------------------

    def map_points(
        self,
        points: Iterable[Mapping[str, Any]],
        components: Sequence[str],
        phases: Sequence[str],
        conditions_builder: Callable[[Mapping[str, Any], Any], Mapping[Any, float]] | None = None,
        pdens: int = DEFAULT_PDENS,
        progress_callback: Callable[[int, int, PointResult], None] | None = None,
        reuse_models: bool = False,
    ) -> list[PointResult]:
        """Посчитать точки и вернуть результаты в исходном порядке.

        ``points`` — описания точек для ``conditions_builder`` (по умолчанию
        ``default_conditions_builder``). Builder выполняется там же, где расчёт,
        поэтому при ``workers>1`` он обязан быть picklable, то есть функцией
        уровня модуля, а не lambda или замыканием.

        ``progress_callback(completed, total, result)`` вызывается в родительском
        процессе по мере готовности точек — порядок вызовов не совпадает с
        порядком точек, индекс точки лежит в ``result.index``.

        ``reuse_models=True`` строит ``Model`` один раз на задание и передаёт их
        в ``equilibrium`` — так же, как ``calculate_ternary_phase_fraction_map``
        в приложении; для сканов не нужно.

        Ошибка отдельной точки возвращается в ``PointResult.error``, остальные
        точки при этом считаются.
        """
        if self._closed:
            raise ParallelEngineError("Движок закрыт, новые расчёты не принимаются.")

        job = _Job(
            components=tuple(str(item) for item in components),
            phases=tuple(str(item) for item in phases),
            pdens=int(pdens),
            conditions_builder=conditions_builder or default_conditions_builder,
            reuse_models=bool(reuse_models),
        )
        if not job.components:
            raise ValueError("Пустой список компонентов.")
        if not job.phases:
            raise ValueError("Пустой список фаз.")

        prepared = [dict(point) for point in points]
        total = len(prepared)
        results: list[PointResult | None] = [None] * total
        if total == 0:
            return []

        completed = 0
        if self._workers == 1:
            database = self._ensure_local_database()
            models = self._local_models_for(job)
            for index, point in enumerate(prepared):
                result = _solve_point(database, job, index, point, models)
                results[index] = result
                completed += 1
                if progress_callback is not None:
                    progress_callback(completed, total, result)
        else:
            pool = self._ensure_pool()
            # По одному заданию на точку: точки стоят от секунды до минуты,
            # крупные куски перекашивают загрузку воркеров и портят прогресс.
            futures = {
                pool.submit(_worker_solve, (self._sha256, job, index, point)): index
                for index, point in enumerate(prepared)
            }
            try:
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    results[result.index] = result
                    completed += 1
                    if progress_callback is not None:
                        progress_callback(completed, total, result)
            except concurrent.futures.process.BrokenProcessPool as error:
                # Воркер не вернулся: пул после этого нерабочий, его нужно снять,
                # чтобы следующий вызов поднял новый.
                self._drop_broken_pool()
                raise WorkerLostError(
                    "Воркер завершился, не вернув результат "
                    f"(вероятно, не хватило памяти на {self._workers} процессов): {error}"
                ) from error

        missing = [index for index, item in enumerate(results) if item is None]
        if missing:
            raise ParallelEngineError(f"Пул не вернул точки: {missing}.")
        return [item for item in results if item is not None]


# ---------------------------------------------------------------------------
# Общий пул на процесс приложения
# ---------------------------------------------------------------------------

_LIVE_ENGINES: "weakref.WeakSet[ParallelEquilibrium]" = weakref.WeakSet()
_SHARED_ENGINES: dict[tuple[str, str, int], ParallelEquilibrium] = {}


def shared_engine(
    database_path: str | os.PathLike[str],
    sha256: str,
    workers: int | None = None,
    hash_seed: str | None = DEFAULT_HASH_SEED,
) -> ParallelEquilibrium:
    """Движок-одиночка на ключ ``(путь, SHA, воркеры)``.

    Пул не сериализуется, поэтому в ``st.session_state`` он лежать не может;
    для Streamlit это единственный корректный способ пережить перезапуск скрипта.
    """
    key = (str(Path(database_path).resolve()), str(sha256).strip().lower(), resolve_worker_count(workers))
    engine = _SHARED_ENGINES.get(key)
    if engine is None or engine._closed:  # noqa: SLF001
        engine = ParallelEquilibrium(database_path, sha256, workers=key[2], hash_seed=hash_seed)
        _SHARED_ENGINES[key] = engine
    return engine


def close_shared_engines() -> None:
    """Закрыть все общие движки (смена базы, выход, конец теста)."""
    for engine in list(_SHARED_ENGINES.values()):
        engine.close()
    _SHARED_ENGINES.clear()


@atexit.register
def _close_live_engines() -> None:
    for engine in list(_LIVE_ENGINES):
        try:
            engine.close()
        except Exception:
            pass
    _LIVE_ENGINES.clear()
