"""18-В (BL-44): один прогон вкладки «Затвердевание» через AppTest, снимок всех таблиц.

Каждый состав — отдельный процесс:

    python -B -X utf8 results/wave18_v/run_case.py <случай> <каталог вывода>

В каталог пишутся CSV всех таблиц состояния ``solidification_result`` (to_csv,
float — repr, то есть до последнего бита), ``meta.json`` (значения сводки repr,
тексты st.warning/st.error, время) и ``sha256.txt`` по файлам. Сверка до/после —
``compare.py``.
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

ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "app" / "ThermoGar_app.py"
sys.path.insert(0, str(ROOT / "app"))

RS320 = ("FE=0.2503755633450175, MG=0.500751126690035, "
         "MN=0.1502253380070105, SI=8.01201802704056")  # tasks/lilith_16A/marki_16A.csv, w_*

CASES = {
    # 15-Ш: умолчания вкладки (оба метода, быстрый набор, pdens 50).
    "nicr": {"db": "ni", "composition": "CR=20", "units": "массовые %", "balance": "NI"},
    "nialcr": {"db": "ni", "composition": "AL=9.8, CR=8.3", "units": "атомные %", "balance": "NI"},
    "fecrc": {"db": "fe", "composition": "CR=15, C=0.4", "units": "массовые %", "balance": "FE"},
    # 16-А: полный набор, pdens 50, только равновесный путь.
    "inconel600": {"db": "ni", "composition": "CR=15.0, FE=8.0", "units": "массовые %",
                   "balance": "NI", "full": True, "method": "Только равновесное затвердевание"},
    "rs320": {"db": "al", "composition": RS320, "units": "массовые %", "balance": "AL",
              "full": True, "method": "Только равновесное затвердевание"},
}


def main(case: str, out: Path) -> None:
    from streamlit.testing.v1 import AppTest

    spec = CASES[case]
    out.mkdir(parents=True, exist_ok=True)
    os.environ["THERMOGAR_STATE_ROOT"] = tempfile.mkdtemp(prefix="w18v_state_")
    key = spec["db"]
    at = AppTest.from_file(str(APP_PATH), default_timeout=3600)
    at.session_state["thermogar_database_key"] = key
    at.session_state[f"thermogar_composition_{key}"] = spec["composition"]
    at.session_state[f"thermogar_units_{key}"] = spec["units"]
    at.session_state[f"thermogar_balance_{key}"] = spec["balance"]
    at.session_state[f"solidification_pdens_{key}"] = 50
    if spec.get("full"):
        at.session_state[f"solidification_phase_set_{key}"] = "all"
    if spec.get("method"):
        at.session_state[f"solidification_method_{key}"] = spec["method"]
    at.run()
    before = {"warning": [w.value for w in at.warning], "error": [e.value for e in at.error]}
    t0 = time.perf_counter()
    at.button(key="solidification_calculate").click().run()
    seconds = time.perf_counter() - t0
    assert not at.exception, [str(e.value) for e in at.exception]
    state = at.session_state["solidification_result"]

    frames = {"summary": state["summary"], "settings": state["settings"],
              "start_check": state["start_check"]}
    for name in ("paths", "raw_tables", "liquid_tables", "sequences", "final_phases"):
        for method, frame in state[name].items():
            frames[f"{name}_{method}"] = frame
    sums = {}
    for name, frame in frames.items():
        data = frame.to_csv(index=False).encode("utf-8")
        (out / f"{name}.csv").write_bytes(data)
        sums[name] = hashlib.sha256(data).hexdigest()
    (out / "sha256.txt").write_text(
        "".join(f"{sums[n]}  {n}.csv\n" for n in sorted(sums)), "utf-8")

    summary = state["summary"]
    meta = {
        "case": case, "spec": spec, "seconds": round(seconds, 1),
        "summary": [{k: repr(v) for k, v in row.items()} for row in summary.to_dict("records")],
        "phases": next(v for p, v in state["settings"].itertuples(index=False)
                       if p == "Выбранные фазы"),
        "errors": state["errors"],
        "converged": {m: bool(r.converged) for m, r in state["results"].items()},
        "warning_before_click": before["warning"],
        "warning": [w.value for w in at.warning],
        "error": [e.value for e in at.error],
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps({"case": case, "seconds": meta["seconds"], "summary": meta["summary"],
                      "converged": meta["converged"]}, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
