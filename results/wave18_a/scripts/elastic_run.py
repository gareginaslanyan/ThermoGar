"""18-А, п. 4 (копия 15-Ф, добавлен nialcr в ат. %): подготовка упругих свойств и VRH через приложение.

Запуск приложения из снимка исходников через AppTest, как в tools/test_ui_f.py
и results/wave15_u/scripts/density_run.py. Выходы — проекции подготовки и
VRH в каноническом JSON (поле warnings подготовки — отдельным файлом) и листы
выгрузки ThermoGar_elastic_vrh.xlsx в CSV.

    python elastic_run.py <корень снимка> <каталог вывода> <on|off|env> <случай>

on  — галочка по умолчанию;
off — галочка снята (session_state physical_overrides_enabled=False);
env — THERMOGAR_PHYSICAL_OVERRIDES=off.

Случаи (масс. %): nicr — Ni-20Cr, 700 °C; fec — Fe-1C, 700 °C; nicrc —
Ni-20Cr-0,3C, 700 °C; fecrc — Fe-15Cr-0,4C, 950 °C; fec800 — Fe-1C, 800 °C.

Модули фаз — условные числа для проверки весов, а не данные о фазах:
редактор подменяется, как в tools/test_ui_f.py. Первой по порядку фазе
достаётся E = 100 ГПа, второй — 300 ГПа, всем ν = 0,25; при одинаковых
модулях веса фаз на результат не влияли бы.
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
    "nicr": {"key": "ni", "composition": "CR=20", "balance": "NI"},
    "fec": {"key": "fe", "composition": "C=1", "balance": "FE"},
    "nicrc": {"key": "ni", "composition": "CR=20, C=0.3", "balance": "NI"},
    "fecrc": {"key": "fe", "composition": "CR=15, C=0.4", "balance": "FE", "t_c": 950.0},
    "fec800": {"key": "fe", "composition": "C=1", "balance": "FE", "t_c": 800.0},
    "nialcr": {"key": "ni", "composition": "AL=9.8, CR=8.3", "balance": "NI", "t_c": 800.0, "units": "атомные %"},
}
if case in CASES:
    spec = dict(CASES[case])
else:
    # Пробный случай: «база|состав|основа|T, °C».
    key, composition, balance, temperature = case.split("|")
    spec = {"key": key, "composition": composition, "balance": balance, "t_c": float(temperature)}
out.mkdir(parents=True, exist_ok=True)

if mode == "env":
    os.environ["THERMOGAR_PHYSICAL_OVERRIDES"] = "off"
else:
    os.environ.pop("THERMOGAR_PHYSICAL_OVERRIDES", None)
os.environ["THERMOGAR_STATE_ROOT"] = tempfile.mkdtemp(prefix="w18a_state_")
sys.path.insert(0, str(root / "app"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

KEY = spec["key"]
T_C = float(spec.get("t_c", 700.0))
YOUNG_BY_ORDER = (100.0, 300.0)

downloads: dict[str, bytes] = {}
original_button = st.download_button
original_editor = st.data_editor


def capture(label, data=None, *args, **kwargs):
    name = str(kwargs.get("file_name") or label)
    if isinstance(data, (bytes, bytearray)):
        downloads[name] = bytes(data)
    return original_button(label, data, *args, **kwargs)


def filled_editor(frame, *args, **kwargs):
    original_editor(frame, *args, **kwargs)
    edited = frame.copy()
    edited["young_gpa"] = [YOUNG_BY_ORDER[i % 2] for i in range(len(edited))]
    edited["poisson"] = 0.25
    edited["origin"] = "measured"
    edited["source"] = "условное значение для проверки весов VRH"
    edited["reference_temperature_c"] = 25.0
    return edited


st.download_button = capture
st.data_editor = filled_editor

at = AppTest.from_file(str(root / "app" / "ThermoGar_app.py"), default_timeout=1800)
state = {
    "thermogar_database_key": KEY,
    f"thermogar_composition_{KEY}": spec["composition"],
    f"thermogar_units_{KEY}": spec.get("units", "массовые %"),
    f"thermogar_balance_{KEY}": spec["balance"],
    f"b4b2_elastic_temperature_{KEY}": T_C,
}
if mode == "off":
    state["physical_overrides_enabled"] = False
for name, value in state.items():
    at.session_state[name] = value
at.run()
at.button(key="b4b2_elastic_prepare_calculate").click().run()
assert not at.exception, [str(e.value) for e in at.exception]
if "_thermogar_vlb_b4b_result_property_elastic_prepare" not in at.session_state:
    print(json.dumps({"prepare_failed": [e.value for e in at.error]}, ensure_ascii=False))
    sys.exit(4)
at.button(key="b4b2_elastic_vrh_calculate").click().run()
assert not at.exception, [str(e.value) for e in at.exception]

errors = [e.value for e in at.error]
shown_warnings = [e.value for e in at.warning]


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8")


prepare = dict(at.session_state["_thermogar_vlb_b4b_result_property_elastic_prepare"]["projection"])
vrh = dict(at.session_state["_thermogar_vlb_b4b_result_property_elastic_vrh"]["projection"])
prepare_warnings = prepare.pop("warnings", None)
(out / "prepare_projection.json").write_bytes(canonical(prepare))
(out / "prepare_warnings.json").write_bytes(canonical(prepare_warnings))
(out / "vrh_projection.json").write_bytes(canonical(vrh))
(out / "vrh_bounds.json").write_bytes(canonical(vrh["bounds_rows"]))
(out / "vrh_summary.json").write_bytes(canonical(vrh["summary"]))
(out / "vrh_phase_rows.json").write_bytes(canonical(vrh["phase_rows"]))

sheets = pd.read_excel(io.BytesIO(downloads["ThermoGar_elastic_vrh.xlsx"]), sheet_name=None)
for sheet, frame in sheets.items():
    target = out / f"xlsx_sheet_{sheet}.csv"
    target.write_bytes(frame.to_csv(index=False, lineterminator="\n").encode("utf-8"))

summary = {
    "mode": mode,
    "case": case,
    "errors": errors,
    "shown_warnings": shown_warnings,
    "prepare_state_overrides": at.session_state[
        "_thermogar_vlb_b4b_result_property_elastic_prepare"
    ].get("physical_overrides"),
    "prepare_phase_rows": prepare["phase_rows"],
    "summary": vrh["summary"],
}
(out / "summary.json").write_bytes(canonical(summary))
print(json.dumps(summary, ensure_ascii=False))
