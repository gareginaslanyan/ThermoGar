from __future__ import annotations

import gc
import json
import os
import sys
import threading
import time

import pytest

GIB = 2**30



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
        "peak_wset_process_gib": round(process.memory_info().peak_wset / GIB, 3),
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

