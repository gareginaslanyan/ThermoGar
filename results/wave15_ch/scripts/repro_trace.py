"""15-Ч, п. 1: воспроизвести падение подготовки упругих свойств и снять traceback.

Приложение запускается через AppTest, как в results/wave15_f/scripts/elastic_run.py.
Бэкенд подготовки оборачивается: исключение, которое приложение показывает
пользователю одним именем класса, здесь записывается с полным traceback.

    python repro_trace.py <корень снимка> <файл вывода>
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
os.environ.pop("THERMOGAR_PHYSICAL_OVERRIDES", None)
os.environ["THERMOGAR_STATE_ROOT"] = tempfile.mkdtemp(prefix="w15ch_state_")
sys.path.insert(0, str(root / "app"))

import thermogar_database_repair as repair  # noqa: E402
import thermogar_verified_properties as verified_properties  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

captured: dict[str, object] = {}
original_backend = verified_properties.execute_verified_properties.__kwdefaults__["backend"]


def traced_backend(database, physical_database, call):
    captured["phases_in"] = len(call.phases)
    captured["components"] = list(call.components)
    try:
        return original_backend(database, physical_database, call)
    except BaseException as error:
        captured["traceback"] = traceback.format_exc()
        captured["is_order_disorder_model_error"] = repair.is_order_disorder_model_error(error)
        captured["structural_detector"] = sorted(
            repair.broken_order_disorder_phases(database, call.components)
        )
        raise


verified_properties.execute_verified_properties.__kwdefaults__["backend"] = traced_backend

KEY = "ni"
at = AppTest.from_file(str(root / "app" / "ThermoGar_app.py"), default_timeout=1800)
for name, value in {
    "thermogar_database_key": KEY,
    f"thermogar_composition_{KEY}": "CR=20, C=0.3",
    f"thermogar_units_{KEY}": "массовые %",
    f"thermogar_balance_{KEY}": "NI",
    f"b4b2_elastic_temperature_{KEY}": 700.0,
}.items():
    at.session_state[name] = value
at.run()
at.button(key="b4b2_elastic_prepare_calculate").click().run()
captured["app_exceptions"] = [str(e.value) for e in at.exception]
captured["shown_errors"] = [e.value for e in at.error]
prepared = at.session_state["_thermogar_vlb_b4b_result_property_elastic_prepare"] if (
    "_thermogar_vlb_b4b_result_property_elastic_prepare" in at.session_state
) else None
captured["prepare_state"] = prepared if not isinstance(prepared, dict) else {
    "keys": sorted(prepared),
    "warnings": prepared.get("projection", {}).get("warnings"),
    "phase_rows": prepared.get("projection", {}).get("phase_rows"),
}
out.write_text(json.dumps(captured, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(captured.get("traceback", "нет traceback"))
print(json.dumps({k: v for k, v in captured.items() if k != "traceback"}, ensure_ascii=False, default=str))
