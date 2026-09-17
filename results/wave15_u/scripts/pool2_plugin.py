"""15-У: фикстура _bounded_memory из tools/test_ui_f.py ветки wave15-tests (8a44f39), плагином."""
import gc
import pytest

UI_TEST_POOL_WORKERS = 2


@pytest.fixture(autouse=True)
def _bounded_memory_w15u(monkeypatch):
    import matplotlib.pyplot as plt
    import thermogar_parallel_ui

    monkeypatch.setattr(thermogar_parallel_ui, "_WORKER_COUNT", UI_TEST_POOL_WORKERS)
    yield
    thermogar_parallel_ui.close_shared_engines()
    plt.close("all")
    gc.collect()
