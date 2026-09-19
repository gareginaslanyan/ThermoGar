"""18-Г, п. 5: приёмка 0.4.3 на установленном рантайме через AppTest.

Запускается интерпретатором установленной программы и гоняет установленное
приложение (корень — первый аргумент), ничего в нём не пишет (``-B``, папка
состояния — временная):

    "C:\\Program Files\\ThermoGar\\runtime\\python.exe" -B -X utf8 priemka.py <корень> <случай> <каталог вывода>

Случаи:

* ``version`` — (а) подпись версии на экране и ``APP_VERSION``;
* ``density`` — (б) RS320, «Плотность»: 20 °C — текст отказа владельца, 25 °C — число;
* ``solidus`` — (в) RS320, только равновесное затвердевание, полный набор, pdens 50;
* ``pool`` — (д) температурный скан Fe (профиль test_ui_f) с пулом и без.

(г) — ``results/wave18_a/scripts/density_run.py`` с тем же корнем, отдельно.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

ROOT = Path(sys.argv[1]).resolve()
CASE = sys.argv[2]
OUT = Path(sys.argv[3]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
APP_PATH = ROOT / "app" / "ThermoGar_app.py"
sys.path.insert(0, str(ROOT / "app"))
os.environ["THERMOGAR_STATE_ROOT"] = tempfile.mkdtemp(prefix="w18g_state_")

import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

RS320 = ("FE=0.2503755633450175, MG=0.500751126690035, "
         "MN=0.1502253380070105, SI=8.01201802704056")  # tasks/lilith_16A/marki_16A.csv, как 18-В
OWNER_DENSITY = "Физическая база задаёт плотность с 25 °C; введите 25 °C или выше."
OWNER_SOLIDUS_WARNING = ("Равновесное затвердевание не сошлось; солидус найден половинным "
                         "делением по доле жидкости.")
SINGLE_STATE = "_thermogar_vlb_b4b_result_property_density_single"


def app(state: dict) -> AppTest:
    at = AppTest.from_file(str(APP_PATH), default_timeout=3600)
    for name, value in state.items():
        at.session_state[name] = value
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


def rs320(extra: dict) -> dict:
    state = {"thermogar_database_key": "al", "thermogar_composition_al": RS320,
             "thermogar_units_al": "массовые %", "thermogar_balance_al": "AL"}
    state.update(extra)
    return state


def case_version() -> dict:
    import thermogar_release_policy as policy

    at = app({})
    captions = [c.value for c in at.sidebar.caption]
    shown = [c for c in captions if c.startswith("ThermoGar ")]
    return {"app_version": policy.APP_VERSION, "sidebar": shown,
            "ok": policy.APP_VERSION == "0.4.3" and any(c.startswith("ThermoGar 0.4.3 ") for c in shown)}


def case_density() -> dict:
    at20 = app(rs320({"physical_temperature_al": 20.0}))
    errors20 = [e.value for e in at20.error]
    disabled20 = at20.button(key="physical_single_calculate").disabled
    at25 = app(rs320({"physical_temperature_al": 25.0}))
    at25.button(key="physical_single_calculate").click().run()
    assert not at25.exception, [str(e.value) for e in at25.exception]
    projection = at25.session_state[SINGLE_STATE]["projections"][0]
    rho = projection["alloy_density_kg_m3"]
    return {"20C_errors": errors20, "20C_button_disabled": disabled20,
            "20C_result_absent": SINGLE_STATE not in at20.session_state,
            "25C_errors": [e.value for e in at25.error],
            "25C_temperature_k": projection.get("temperature_k"),
            "25C_density_kg_m3": rho, "25C_vs_datasheet_2659_pct": 100.0 * (rho - 2659.0) / 2659.0,
            "ok": errors20 == [OWNER_DENSITY] and disabled20 and abs(rho - 2663.0) <= 3.0}


def case_solidus() -> dict:
    at = app(rs320({"solidification_pdens_al": 50,
                    "solidification_phase_set_al": "all",
                    "solidification_method_al": "Только равновесное затвердевание"}))
    t0 = time.perf_counter()
    at.button(key="solidification_calculate").click().run()
    seconds = time.perf_counter() - t0
    assert not at.exception, [str(e.value) for e in at.exception]
    state = at.session_state["solidification_result"]
    row = state["summary"].to_dict("records")[0]
    end_c = float(row["Температура окончания, °C"])
    settings = dict(state["settings"].itertuples(index=False))
    warnings = [w.value for w in at.warning]
    return {"seconds": round(seconds, 1), "summary": {k: repr(v) for k, v in row.items()},
            "solidus_k": end_c + 273.15, "criterion": settings.get("Критерий солидуса"),
            "warning": warnings, "converged": {m: bool(r.converged) for m, r in state["results"].items()},
            "ok": abs(end_c + 273.15 - 838.1) <= 0.3 and OWNER_SOLIDUS_WARNING in warnings}


def scan(mode: str) -> dict:
    downloads: dict[str, bytes] = {}
    original = st.download_button

    def capture(label, data=None, *args, **kwargs):
        name = str(kwargs.get("file_name") or label)
        if isinstance(data, (bytes, bytearray)):
            downloads[name] = bytes(data)
        elif isinstance(data, str):
            downloads[name] = data.encode("utf-8")
        return original(label, data, *args, **kwargs)

    st.download_button = capture
    try:
        at = app({"thermogar_database_key": "fe", "thermogar_composition_fe": "C=0.2, CR=11.5, NI=0.7",
                  "thermogar_units_fe": "массовые %", "thermogar_balance_fe": "FE",
                  "t_min_fe": 500.0, "t_max_fe": 900.0, "t_step_fe": 100.0,
                  "thermogar_parallel_mode": mode})
        t0 = time.perf_counter()
        at.button(key="temperature_calculate").click().run()
        seconds = time.perf_counter() - t0
    finally:
        st.download_button = original
    assert not at.exception, [str(e.value) for e in at.exception]
    display = at.session_state["_thermogar_vlb_b3_result_equilibrium_temperature_scan"]["display"]
    settings = display["settings"]
    note = str(settings.loc[settings["Параметр"] == "Параллельный расчёт", "Значение"].iloc[0])
    data = display["data"]
    cells = [[v.hex() if isinstance(v, float) else repr(v) for v in row] for row in data.itertuples(index=False)]
    csv = downloads["ThermoGar_temperature_scan.csv"]
    (OUT / f"scan_{mode}.csv").write_bytes(csv)
    return {"note": note, "seconds": round(seconds, 1), "rows": len(data), "columns": list(data.columns),
            "cells_sha256": hashlib.sha256(json.dumps(cells).encode()).hexdigest(),
            "csv_sha256": hashlib.sha256(csv).hexdigest()}


def case_pool() -> dict:
    assert os.environ.get("PYTHONHASHSEED") == "0", "нужен PYTHONHASHSEED=0"
    pooled = scan("auto")
    plain = scan("off")
    return {"auto": pooled, "off": plain,
            "ok": (pooled["note"].startswith("Параллельный расчёт:")
                   and "отказал" not in pooled["note"]
                   and plain["note"] == "Последовательный расчёт в одном процессе."
                   and pooled["rows"] == 5
                   and pooled["columns"] == plain["columns"]
                   and pooled["cells_sha256"] == plain["cells_sha256"]
                   and pooled["csv_sha256"] == plain["csv_sha256"])}


result = {"python": sys.executable, "app": str(APP_PATH), "case": CASE}
result.update({"version": case_version, "density": case_density,
               "solidus": case_solidus, "pool": case_pool}[CASE]())
(OUT / f"{CASE}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), "utf-8")
print(json.dumps(result, ensure_ascii=False))
