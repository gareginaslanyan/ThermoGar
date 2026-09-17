"""15-З, пункты 4–5: узел BL-24 штатным путём приложения.

Запуск (один вариант — один процесс, PYTHONHASHSEED=0, из корня дерева):
    python -B -X utf8 p4_node.py <pdens> <вариант бора> <каталог вывода> [температура, °C; по умолчанию 750]

Вариант бора: ``none`` — бора в составе нет (пользователь его не вводит);
``trace`` — след 1e-6 масс. %, как в 12-4 (`ZERO_BORON_WT`).

Состав — ЭК199-ВИ по `tools/study_hn62m_wave12.py` (`CONTROL_WT`) с Si = 5
масс. %, 750 °C. Приложение `app/ThermoGar_app.py` исполняется через
`streamlit.testing.v1.AppTest`: база Ni, состав в боковой панели, вкладка
«Одна температура», кнопка «Рассчитать равновесие». Плотность выборки в
приложении зашита (`calc_opts={"pdens": 500}` в
`thermogar_verified_equilibrium._default_backend`); для pdens 100 обёртка
`pycalphad.equilibrium` меняет только это значение. Обёртка же записывает
сырой результат: Phase, NP и сумму мольных долей фаз.

Всё, что приложение показало (ошибки, предупреждения, подписи, таблицы),
пишется в `screen.json`.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import psutil

pdens = int(sys.argv[1])
boron = sys.argv[2]
temperature_c = float(sys.argv[4]) if len(sys.argv) > 4 else 750.0
out = Path(sys.argv[3]).resolve()
out.mkdir(parents=True, exist_ok=True)
ROOT = Path(__file__).resolve().parents[3]
os.environ["THERMOGAR_STATE_ROOT"] = os.environ.get("P4_STATE_ROOT") or tempfile.mkdtemp(prefix="tg-p4-")
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "tools"))

proc = psutil.Process()
record: dict = {
    "pdens": pdens,
    "boron": boron,
    "temperature_c": temperature_c,
    "si_wt": float(os.environ.get("P4_SI_WT", "5.0")),
    "free_at_start_gib": round(psutil.virtual_memory().available / 2**30, 3),
    "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
}
peak = {"rss": 0, "min_free": record["free_at_start_gib"]}
stop = threading.Event()


def watch() -> None:
    while not stop.is_set():
        peak["rss"] = max(peak["rss"], proc.memory_info().rss)
        peak["min_free"] = min(peak["min_free"], psutil.virtual_memory().available / 2**30)
        time.sleep(0.2)


threading.Thread(target=watch, daemon=True).start()

import numpy as np  # noqa: E402
import pycalphad  # noqa: E402

import study_hn62m_wave12 as w12  # noqa: E402

wt = dict(w12.CONTROL_WT)
wt["SI"] = float(os.environ.get("P4_SI_WT", "5.0"))
if boron == "trace":
    wt["B"] = 1.0e-6
elif boron != "none":
    raise SystemExit(f"вариант бора: none или trace, не {boron!r}")
# Парсер состава приложения не читает экспоненту: след бора пишется десятичной дробью.
composition_text = ", ".join(f"{element}={value:.6f}".rstrip("0").rstrip(".") for element, value in wt.items())
record["composition_text"] = composition_text

raw_calls: list[dict] = []
original_equilibrium = pycalphad.equilibrium


def equilibrium(*args, **kwargs):
    calc_opts = dict(kwargs.get("calc_opts") or {})
    record_call = {"pdens_app": calc_opts.get("pdens")}
    calc_opts["pdens"] = pdens
    kwargs["calc_opts"] = calc_opts
    started = time.perf_counter()
    result = original_equilibrium(*args, **kwargs)
    names = [str(name) for name in np.asarray(result.Phase.values, dtype=str).ravel()]
    fractions = np.asarray(result.NP.values, dtype=float).ravel()
    record_call.update({
        "pdens_used": pdens,
        "seconds": round(time.perf_counter() - started, 2),
        "components": list(args[1]) if len(args) > 1 else None,
        "phases_count": len(args[2]) if len(args) > 2 else None,
        "Phase": names,
        "NP": [None if not np.isfinite(value) else float(value) for value in fractions],
        "NP_nansum": float(np.nansum(fractions)),
        "NP_all_nan": bool(np.all(np.isnan(fractions))),
        "GM": [None if not np.isfinite(value) else float(value)
               for value in np.asarray(result.GM.values, dtype=float).ravel()],
    })
    raw_calls.append(record_call)
    return result


pycalphad.equilibrium = equilibrium

from streamlit.testing.v1 import AppTest  # noqa: E402

os.chdir(ROOT)
app = AppTest.from_file(str(ROOT / "app" / "ThermoGar_app.py"), default_timeout=3600)
app.session_state["thermogar_database_key"] = "ni"
app.session_state["thermogar_balance_ni"] = "NI"
app.session_state["thermogar_units_ni"] = "массовые %"
app.session_state["thermogar_composition_ni"] = composition_text
app.run()
before = {
    "errors": [element.value for element in app.error],
    "warnings": [element.value for element in app.warning],
}
app.number_input(key="single_temperature_ni").set_value(temperature_c)
app.run()
started = time.perf_counter()
app.button(key="single_calculate").click()
app.run()
record["seconds"] = round(time.perf_counter() - started, 2)


def texts(elements) -> list[str]:
    return [str(element.value) for element in elements]


state_key = "_thermogar_vlb_b3_result_equilibrium_single"
stored = app.session_state[state_key] if state_key in app.session_state else None
record["screen"] = {
    "before_click": before,
    "errors": texts(app.error),
    "warnings": texts(app.warning),
    "infos": texts(app.info),
    "successes": texts(app.success),
    "captions": [value for value in texts(app.caption) if "Код ошибки" in value],
    "exceptions": [str(element.value) for element in app.exception],
    "result_stored": stored is not None,
}
if stored is not None:
    display = stored["display"]
    record["screen"]["summary"] = display["summary"].to_dict(orient="records")
    record["screen"]["quality"] = json.loads(json.dumps(display["quality"], ensure_ascii=False, default=str))
record["raw_calls"] = raw_calls
stop.set()
record["peak_rss_gib"] = round(peak["rss"] / 2**30, 3)
record["min_free_during_run_gib"] = round(peak["min_free"], 3)
(out / "screen.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({key: record[key] for key in record if key != "raw_calls"}, ensure_ascii=False, indent=1))
for call in raw_calls:
    print(json.dumps({key: call[key] for key in ("pdens_app", "pdens_used", "seconds", "components",
                                                   "phases_count", "NP_nansum", "NP_all_nan")},
                     ensure_ascii=False))
