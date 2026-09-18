"""Плагин проверки BL-17: короткий таймаут на один тест настоящего файла.

    set PYTHONPATH=results\\wave15_o\\timeout_check
    set THERMOGAR_TIMEOUT_ONE=test_startup_is_clean[ni]=2
    python -m pytest tools/test_ui_f.py -p one_test_timeout ...

Остальные тесты файла идут без таймаута.
"""
import os

import pytest


def pytest_collection_modifyitems(config, items):
    name, _, seconds = os.environ["THERMOGAR_TIMEOUT_ONE"].rpartition("=")
    hits = [item for item in items if item.name == name]
    assert len(hits) == 1, (name, [item.name for item in items])
    hits[0].add_marker(pytest.mark.timeout(float(seconds)))
