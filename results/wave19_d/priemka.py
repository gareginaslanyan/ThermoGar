"""19-Д, шаг 9: приёмка 0.4.4 на установленном рантайме.

Основа — ``results/wave18_g/priemka.py`` (AppTest, случаи версии, плотности и пула) и
``results/wave19_a/scripts/app_extract.py`` (функции приложения без запуска Streamlit), а для
пакета — ``step_1g_batch`` из ``results/wave19_a/scripts/measure.py``. Запускается
интерпретатором установленной программы и берёт установленное приложение (корень — первый
аргумент); в нём ничего не пишет (``-B``, папка состояния — временная):

    "C:\\Program Files\\ThermoGar\\runtime\\python.exe" -B -X utf8 priemka.py <корень> <случай> <каталог вывода>

Случаи:

* ``version`` — (а) подпись версии на экране и ``APP_VERSION``;
* ``batch`` — (б) пакет Fe–0,8C мас. %, 700 °C, 101325 Па: четыре строки через ``_parse_csv``,
  ``batch_table_dataframe``, ``run_batch_calculations`` и настоящий ``batch_engine_runner``;
* ``phase_reference`` — (в) справочник фаз трёх баз (``phase_reference_dataframe``);
* ``density`` — (г) RS320, «Плотность», 25 °C;
* ``quick_start`` — (д) первое упоминание версии в установленном ``QUICK_START_THERMOGAR.md``;
* ``pool`` — (е) температурный скан Fe (профиль test_ui_f) с пулом и без.

Побайтовая сверка выходов (б) и (в) с байтами из git — ``results/wave19_d/priemka_compare.py``.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import time
import warnings
from pathlib import Path
from typing import Any
from unittest import mock

import matplotlib

matplotlib.use("Agg")

ROOT = Path(sys.argv[1]).resolve()
CASE = sys.argv[2]
OUT = Path(sys.argv[3]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
APP_PATH = ROOT / "app" / "ThermoGar_app.py"
sys.path.insert(0, str(ROOT / "app"))
os.environ["THERMOGAR_STATE_ROOT"] = tempfile.mkdtemp(prefix="w19d_state_")

import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

VERSION = "0.4.4"
RS320 = ("FE=0.2503755633450175, MG=0.500751126690035, "
         "MN=0.1502253380070105, SI=8.01201802704056")  # tasks/lilith_16A/marki_16A.csv, как 18-В
SINGLE_STATE = "_thermogar_vlb_b4b_result_property_density_single"
UNKNOWN_MODE = "Неизвестный режим стали: «metastabe». Используйте «стабильный» или «метастабильный»."


def app(state: dict) -> AppTest:
    at = AppTest.from_file(str(APP_PATH), default_timeout=3600)
    for name, value in state.items():
        at.session_state[name] = value
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    return at


# --- загрузчик функций приложения: results/wave19_a/scripts/app_extract.py, корень — аргумент ---

def _defined(node: ast.stmt) -> set[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, ast.Assign):
        names: set[str] = set()
        for target in node.targets:
            for sub in ast.walk(target):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
        return names
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    return set()


def _free_names(node: ast.stmt) -> set[str]:
    loads: set[str] = set()
    local: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            (loads if isinstance(sub.ctx, ast.Load) else local).add(sub.id)
        elif isinstance(sub, ast.arg):
            local.add(sub.arg)
        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and sub is not node:
            local.add(sub.name)
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return loads
    return loads - local


def extract(names: tuple[str, ...]) -> dict[str, Any]:
    tree = ast.parse(APP_PATH.read_text("utf-8"))
    header: list[ast.stmt] = []
    candidates: list[tuple[int, ast.stmt, set[str]]] = []
    for index, node in enumerate(tree.body):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            header.append(node)
            continue
        defined = _defined(node)
        if defined:
            candidates.append((index, node, defined))
    wanted = set(names)
    chosen: dict[int, ast.stmt] = {}
    changed = True
    while changed:
        changed = False
        for index, node, defined in candidates:
            if index in chosen or not (defined & wanted):
                continue
            chosen[index] = node
            changed = True
            wanted |= _free_names(node)
    body = header + [chosen[index] for index in sorted(chosen)]
    namespace: dict[str, Any] = {"__file__": str(APP_PATH), "__name__": "thermogar_app_extract"}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        exec(compile(ast.Module(body=body, type_ignores=[]), str(APP_PATH), "exec"), namespace)
    missing = set(names) - set(namespace)
    if missing:
        raise RuntimeError(f"missing {sorted(missing)}")
    return namespace


# --- случаи ---

def case_version() -> dict:
    import thermogar_release_policy as policy

    at = app({})
    captions = [c.value for c in at.sidebar.caption]
    shown = [c for c in captions if c.startswith("ThermoGar ")]
    return {"app_version": policy.APP_VERSION, "sidebar": shown,
            "ok": policy.APP_VERSION == VERSION and any(c.startswith(f"ThermoGar {VERSION} ") for c in shown)}


class FakeProgress:  # tools/thermogar_verified_equilibrium_test.py
    def progress(self, *_args: object, **_kwargs: object) -> None:
        return None

    def empty(self) -> None:
        return None


class FakeBatchBroker:  # tools/thermogar_verified_equilibrium_test.py
    def __init__(self) -> None:
        self.finished = None

    def finish(self, children):
        self.finished = children
        return {"receipt_digest": "a" * 64, "envelope_digest": "b" * 64}


def _table(header: tuple[str, ...], rows: list[tuple[object, ...]]) -> str:
    out = io.StringIO(newline="")
    writer = csv.writer(out, delimiter=",", lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def case_batch() -> dict:
    import thermogar_verified_state as vs
    import thermogar_workspace as workspace

    engine = extract(("batch_engine_runner",))["batch_engine_runner"]
    rows = [("Fe-пусто", ""), ("Fe-метастабильный", "метастабильный"),
            ("Fe-стабильный", "стабильный"), ("Fe-metastabe", "metastabe")]
    out = io.StringIO(newline="")
    writer = csv.writer(out, delimiter=",", lineterminator="\n")
    writer.writerow(vs.TEMPLATE_HEADERS)
    for name, mode in rows:
        writer.writerow((name, "fe", "FE", "мас.%", 700, "C=0.8", mode, 101325, ""))
    source_csv = out.getvalue().encode("utf-8")
    (OUT / "batch_input.csv").write_bytes(source_csv)
    table = vs._parse_csv(source_csv)
    source = workspace.batch_table_dataframe(table)
    seen: list[dict] = []
    outcomes: list[dict] = []

    def runner(canonical_rows, progress):
        seen.extend(dict(row) for row in canonical_rows)
        outcomes.extend(engine(canonical_rows, progress))
        return outcomes

    with mock.patch.object(workspace.st, "progress", return_value=FakeProgress()):
        result = workspace.run_batch_calculations(source, FakeBatchBroker(), {}, runner)
    files = {}
    # Строка с непонятным режимом — последняя: в runner она не попадает, первые три идут по порядку.
    for (label, _value), row, outcome in zip(rows, seen, outcomes):
        text = _table(("фаза", "доля"), [(p, repr(v)) for p, v in outcome["phase_fractions"]])
        (OUT / f"b_batch_{label}.csv").write_bytes(text.encode("utf-8"))
        files[label] = {"row_index": row.get("row_index"), "steel_mode": row["steel_mode"],
                        "status": outcome["status"], "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    summary = result["Сводка"][["Название", "Статус", "Ошибка"]]
    records = [{k: (None if v != v else v) for k, v in r.items()} for r in summary.to_dict("records")]
    last = records[-1]
    return {"runner_rows": len(seen), "files": files, "summary": records,
            "ok": (len(seen) == 3 and last["Название"] == "Fe-metastabe" and last["Статус"] == "ошибка"
                   and last["Ошибка"] == UNKNOWN_MODE)}


def case_phase_reference() -> dict:
    app_ns = extract(("phase_reference_dataframe", "load_database"))
    files = {}
    for key in ("ni", "al", "fe"):
        db, path = app_ns["load_database"](key)
        frame = app_ns["phase_reference_dataframe"](db, path, key)
        data = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
        (OUT / f"v_phase_reference_{key}.csv").write_bytes(data)
        files[key] = {"rows": len(frame), "sha256": hashlib.sha256(data).hexdigest()}
    return {"files": files}


def case_density() -> dict:
    at25 = app({"thermogar_database_key": "al", "thermogar_composition_al": RS320,
                "thermogar_units_al": "массовые %", "thermogar_balance_al": "AL",
                "physical_temperature_al": 25.0})
    at25.button(key="physical_single_calculate").click().run()
    assert not at25.exception, [str(e.value) for e in at25.exception]
    projection = at25.session_state[SINGLE_STATE]["projections"][0]
    rho = projection["alloy_density_kg_m3"]
    return {"25C_errors": [e.value for e in at25.error], "25C_temperature_k": projection.get("temperature_k"),
            "25C_density_kg_m3": rho, "25C_density_2dp": f"{rho:.2f}",
            "ok": f"{rho:.2f}" == "2663.72" and not [e.value for e in at25.error]}


def case_quick_start() -> dict:
    text = (ROOT / "QUICK_START_THERMOGAR.md").read_bytes().decode("utf-8", errors="ignore")
    match = re.search(r"ThermoGar[ _-](?:Guide_)?(\d+\.\d+\.\d+)", text)
    first_any = re.search(r"\d+\.\d+\.\d+", text)
    return {"first_line": text.splitlines()[0], "first_mention": match.group(1) if match else None,
            "first_version_like": first_any.group(0) if first_any else None,
            "ok": bool(match) and match.group(1) == VERSION and first_any.group(0) == VERSION}


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
    csv_bytes = downloads["ThermoGar_temperature_scan.csv"]
    (OUT / f"e_scan_{mode}.csv").write_bytes(csv_bytes)
    return {"note": note, "seconds": round(seconds, 1), "rows": len(data), "columns": list(data.columns),
            "cells_sha256": hashlib.sha256(json.dumps(cells).encode()).hexdigest(),
            "csv_sha256": hashlib.sha256(csv_bytes).hexdigest()}


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
t_start = time.perf_counter()
result.update({"version": case_version, "batch": case_batch, "phase_reference": case_phase_reference,
               "density": case_density, "quick_start": case_quick_start, "pool": case_pool}[CASE]())
result["case_seconds"] = round(time.perf_counter() - t_start, 1)
(OUT / f"{CASE}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), "utf-8")
print(json.dumps(result, ensure_ascii=False))
