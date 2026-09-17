"""Синтетическая проверка BL-17: таймаут одного теста не снимает файл.

    python -m pytest results/wave15_o/timeout_check/check_timeout_bl17.py -p no:cacheprovider

Имя файла не начинается с test_, чтобы pytest из корня не собрал его сам:
три теста здесь падают намеренно. Логи old/new/grace сняты до переименования,
под прежним именем test_timeout_check.py.
"""
import time

import pytest


def test_before():
    assert True


@pytest.mark.timeout(2)
def test_python_loop_times_out():
    deadline = time.time() + 30
    while time.time() < deadline:
        sum(range(1000))


@pytest.mark.timeout(2)
def test_swallowing_except_exception_still_times_out():
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            sum(range(1000))
        except Exception:
            pass


@pytest.mark.timeout(2)
def test_sleep_in_c_is_taken_after_it_returns():
    time.sleep(5)


@pytest.mark.timeout(5)
def test_fast_under_timeout():
    time.sleep(0.1)


def test_after():
    assert True
