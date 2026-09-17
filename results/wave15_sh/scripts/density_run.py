"""15-Ш, п. 3 (копия 15-У с выбором случая): плотность через приложение.

Запуск приложения из снимка исходников через AppTest, как в tools/test_ui_f.py.
Выходы — таблицы раздела «Свойства» (листы выгрузок Excel в CSV) и проекции
результата в каноническом JSON; поле warnings пишется отдельным файлом,
потому что отметка о поправках живёт именно там.

    python density_run.py <корень снимка> <каталог вывода> <on|off|env> <случай>

Случаи: nicr — Ni-20Cr масс. %, 700 °C, со сканом 100…1100 °C (как 15-У);
fecrc — Fe-15Cr-0,4C масс. %, 950 °C; nialcr — Ni–9,8Al–8,3Cr ат. %, 800 °C;
fec800 — Fe-1C масс. %, 800 °C; fewc — Fe-10W-1C масс. %, 800 °C.

on  — галочка по умолчанию;
off — галочка снята (session_state physical_overrides_enabled=False);
env — THERMOGAR_PHYSICAL_OVERRIDES=off.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
mode = sys.argv[3]
case = sys.argv[4]
assert mode in ("on", "off", "env"), mode
CASES = {
    "nicr": ("ni", "CR=20", "массовые %", "NI", 700.0, True),
    "fecrc": ("fe", "CR=15, C=0.4", "массовые %", "FE", 950.0, False),
    "nialcr": ("ni", "AL=9.8, CR=8.3", "атомные %", "NI", 800.0, False),
    "fec800": ("fe", "C=1", "массовые %", "FE", 800.0, False),
    "fewc": ("fe", "W=10, C=1", "массовые %", "FE", 800.0, False),
}
KEY, COMPOSITION, UNITS, BALANCE, T_SINGLE, WITH_SCAN = CASES[case]
out.mkdir(parents=True, exist_ok=True)

if mode == "env":
    os.environ["THERMOGAR_PHYSICAL_OVERRIDES"] = "off"
else:
    os.environ.pop("THERMOGAR_PHYSICAL_OVERRIDES", None)
os.environ["THERMOGAR_STATE_ROOT"] = tempfile.mkdtemp(prefix="w15sh_state_")
sys.path.insert(0, str(root / "app"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

SCAN = (100.0, 1100.0, 100.0)

downloads: dict[str, bytes] = {}
original = st.download_button


def capture(label, data=None, *args, **kwargs):
    name = str(kwargs.get("file_name") or label)
    if isinstance(data, (bytes, bytearray)):
        downloads[name] = bytes(data)
    return original(label, data, *args, **kwargs)


st.download_button = capture

at = AppTest.from_file(str(root / "app" / "ThermoGar_app.py"), default_timeout=1800)
state = {
    "thermogar_database_key": KEY,
    f"thermogar_composition_{KEY}": COMPOSITION,
    f"thermogar_units_{KEY}": UNITS,
    f"thermogar_balance_{KEY}": BALANCE,
    f"physical_temperature_{KEY}": T_SINGLE,
    f"physical_t_min_{KEY}": SCAN[0],
    f"physical_t_max_{KEY}": SCAN[1],
    f"physical_t_step_{KEY}": SCAN[2],
}
if mode == "off":
    state["physical_overrides_enabled"] = False
for name, value in state.items():
    at.session_state[name] = value
at.run()
at.button(key="physical_single_calculate").click().run()
if WITH_SCAN:
    at.button(key="physical_scan_calculate").click().run()
assert not at.exception, [str(e.value) for e in at.exception]

toggles = [
    {"label": w.label, "value": w.value, "disabled": w.disabled, "key": w.key}
    for w in at.checkbox
    if "поправки" in str(w.label).lower()
]
errors = [e.value for e in at.error]


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8")


summary = {"mode": mode, "case": case, "shown_warnings": [w.value for w in at.warning], "toggles": toggles, "errors": errors, "files": {}}
for tag, key in (
    ("single", "_thermogar_vlb_b4b_result_property_density_single"),
    ("scan", "_thermogar_vlb_b4b_result_property_density_temperature"),
)[: 2 if WITH_SCAN else 1]:
    result = at.session_state[key]
    projections = [dict(p) for p in result["projections"]]
    warnings = [p.pop("warnings") for p in projections]
    (out / f"{tag}_projections.json").write_bytes(canonical(projections))
    (out / f"{tag}_warnings.json").write_bytes(canonical(warnings))
    summary[f"{tag}_state_overrides"] = result.get("physical_overrides")
    summary[f"{tag}_density_kg_m3"] = [p["alloy_density_kg_m3"] for p in projections]

for file_name in ("ThermoGar_density_single.xlsx", "ThermoGar_density_scan.xlsx")[: 2 if WITH_SCAN else 1]:
    stem = file_name.split("_")[-1].split(".")[0]
    sheets = pd.read_excel(io.BytesIO(downloads[file_name]), sheet_name=None)
    for sheet, frame in sheets.items():
        target = out / f"{stem}_sheet_{sheet}.csv"
        target.write_bytes(frame.to_csv(index=False, lineterminator="\n").encode("utf-8"))

(out / "summary.json").write_bytes(canonical(summary))
print(json.dumps(summary, ensure_ascii=False))
