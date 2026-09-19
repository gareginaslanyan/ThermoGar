"""Функция-воркер пробы BL-54: что исполнилось в дочернем процессе spawn."""

import os
import sys
import time


def report(_: int) -> dict:
    # BL54_HOLD_S: держать задачу, чтобы каждый воркер взял свою (разные PID).
    time.sleep(float(os.environ.get("BL54_HOLD_S", "0")))
    mp_main = sys.modules.get("__mp_main__")
    return {
        "pid": os.getpid(),
        "mp_main_file": getattr(mp_main, "__file__", None),
        "mp_main_is_app": hasattr(mp_main, "LEGACY_MIGRATION_RECEIPT"),
        "receipt_in_worker": None if not hasattr(mp_main, "LEGACY_MIGRATION_RECEIPT")
        else str(type(getattr(mp_main, "LEGACY_MIGRATION_RECEIPT")).__name__),
        "marker": getattr(mp_main, "BL54_MARKER", None),
        "modules_total": len(sys.modules),
        "thermogar_modules": sorted(
            name for name in sys.modules if name.lower().startswith("thermogar")
        ),
        "streamlit_loaded": "streamlit" in sys.modules,
        "pycalphad_loaded": "pycalphad" in sys.modules,
    }
