"""Общие настройки pytest для tools/.

Замер памяти по тестам (волна 15-О, BL-27) включается переменной
``THERMOGAR_MEMLOG=<путь к .jsonl>``: после каждого теста в файл пишется
строка с рабочим набором процесса до и после теста, пиком по ходу теста
(опрос дерева процессов раз в 0,2 с) и числом открытых фигур matplotlib.
Поле ``peak_wset_process_gib`` на Linux и macOS — пик RSS процесса.
Без переменной хуки ничего не делают.
"""

from __future__ import annotations

import gc
import json
import os
import sys
import threading
import time

import pytest

GIB = 2**30


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: длительные расчёты диаграмм")


# ---------------------------------------------------------------------------
# Замер памяти по тестам
# ---------------------------------------------------------------------------


def _tree_rss(process) -> int:
    import psutil

    total = 0
    for member in [process] + process.children(recursive=True):
        try:
            total += member.memory_info().rss
        except psutil.Error:
            pass
    return total


def _open_figures() -> int | None:
    pyplot = sys.modules.get("matplotlib.pyplot")
    return None if pyplot is None else len(pyplot.get_fignums())


def _process_peak(process) -> int:
    """Пик памяти процесса в байтах: Windows — peak_wset, иначе — ru_maxrss."""
    if sys.platform == "win32":
        return process.memory_info().peak_wset
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux отдаёт ru_maxrss в КиБ, macOS — в байтах.
    return peak if sys.platform == "darwin" else peak * 1024


class _Sampler(threading.Thread):
    def __init__(self, process) -> None:
        super().__init__(name="thermogar-memlog", daemon=True)
        self.process = process
        self.peak = _tree_rss(process)
        self.stop = threading.Event()

    def run(self) -> None:
        while not self.stop.wait(0.2):
            self.peak = max(self.peak, _tree_rss(self.process))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    path = os.environ.get("THERMOGAR_MEMLOG")
    if not path:
        yield
        return
    import psutil

    process = psutil.Process()
    before = process.memory_info().rss
    sampler = _Sampler(process)
    sampler.start()
    started = time.time()
    yield
    sampler.stop.set()
    sampler.join()
    after = process.memory_info().rss
    record = {
        "test": item.nodeid,
        "seconds": round(time.time() - started, 1),
        "rss_before_gib": round(before / GIB, 3),
        "rss_after_gib": round(after / GIB, 3),
        "growth_gib": round((after - before) / GIB, 3),
        "peak_tree_gib": round(max(sampler.peak, after) / GIB, 3),
        "peak_wset_process_gib": round(_process_peak(process) / GIB, 3),
        "open_figures": _open_figures(),
        "pool_workers": getattr(sys.modules.get("thermogar_parallel_ui"), "_WORKER_COUNT", None),
    }
    if os.environ.get("THERMOGAR_MEMLOG_DEEP"):
        # Диагностика: сколько объектов AppTest живо и что даёт сборка мусора.
        record["apptest_alive"] = sum(
            1 for obj in gc.get_objects() if type(obj).__name__ == "AppTest"
        )
        gc.collect()
        record["rss_after_gc_gib"] = round(process.memory_info().rss / GIB, 3)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Таймаут без снятия процесса (волна 15-О, BL-17)
# ---------------------------------------------------------------------------
#
# На Windows нет SIGALRM, и pytest-timeout работает методом ``thread``: по
# срабатыванию таймер печатает стеки и зовёт ``os._exit(1)``
# (pytest_timeout.timeout_timer). Процесс pytest умирает целиком, итоговой
# строки у файла нет. Здесь метод ``thread`` заменён: таймер поднимает
# исключение TestTimeout в главном потоке (PyThreadState_SetAsyncExc), тест
# падает как обычный failed, файл идёт дальше. Исключение доставляется, когда
# главный поток исполняет байткод Python. Если за TIMEOUT_GRACE_S секунд этого
# не случилось (главный поток встал в C-коде), срабатывает прежнее поведение
# pytest-timeout — дамп стеков и os._exit(1): настоящее зависание по-прежнему
# снимается.

TIMEOUT_GRACE_S = float(os.environ.get("THERMOGAR_TIMEOUT_GRACE_S", "60"))


class TestTimeout(BaseException):
    """Тест превысил @pytest.mark.timeout; поднято таймером в главном потоке.

    Наследник BaseException, чтобы ``except Exception`` в коде теста не
    проглотил его.
    """

    __test__ = False


def _raise_in_thread(thread_id: int, exc_type) -> int:
    import ctypes

    return ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(thread_id), ctypes.py_object(exc_type) if exc_type else None
    )


@pytest.hookimpl(tryfirst=True)
def pytest_timeout_set_timer(item, settings):
    if settings.method != "thread" or os.environ.get("THERMOGAR_TIMEOUT_EXIT"):
        return None
    import pytest_timeout

    main_id = threading.main_thread().ident
    lock = threading.Lock()
    state = {"phase": "armed"}

    def expire() -> None:
        if not settings.disable_debugger_detection and pytest_timeout.is_debugging():
            return
        with lock:
            if state["phase"] != "armed":
                return
            state["phase"] = "raised"
            terminal = item.config.get_terminal_writer()
            terminal.sep(
                "+",
                title=f"Timeout (>{settings.timeout}s): {item.nodeid} — тест снят, файл продолжается",
            )
            terminal.flush()
            _raise_in_thread(main_id, TestTimeout)
        if not delivered.wait(TIMEOUT_GRACE_S):
            with lock:
                if state["phase"] != "raised":
                    return
            pytest_timeout.timeout_timer(item, settings)

    delivered = threading.Event()
    timer = threading.Timer(settings.timeout, expire)
    timer.name = f"thermogar-timeout {item.nodeid}"
    timer.daemon = True

    def cancel() -> None:
        with lock:
            if state["phase"] == "raised":
                # Исключение уже доставлено (тест упал) либо ещё висит —
                # во втором случае снять его, чтобы не попасть в pytest.
                _raise_in_thread(main_id, None)
            state["phase"] = "cancelled"
        delivered.set()
        timer.cancel()

    item.cancel_timeout = cancel
    timer.start()
    return True


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    if call.excinfo is not None and call.excinfo.errisinstance(TestTimeout):
        import pytest_timeout

        timeout = pytest_timeout._get_item_settings(item).timeout
        report = outcome.get_result()
        report.longrepr = (
            f"Timeout (>{timeout}s) from pytest-timeout: тест снят без остановки "
            f"файла (tools/conftest.py, BL-17)\n\n{report.longrepr}"
        )
