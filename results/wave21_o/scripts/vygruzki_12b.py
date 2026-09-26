"""21-O, step 7: headers of the export files after 12Б, six kinds.

AppTest of the whole app (as tools/test_wave21_o.py), default inputs of each
screen, bytes of every download button. For every file: the header the file
has now («после») and the column names of the table in the session state
(«до» — what the file carried before 12Б; the table itself is unchanged).

    Excel     «Одна температура» ni — ThermoGar_equilibrium.xlsx, «Составы фаз ат», «Составы фаз мас»
    CSV       «Изменение состава» al — ThermoGar_concentration_scan.csv
    ZIP       «Затвердевание» ni — members *_liquid_composition.csv; xlsx sheets «… расплав», «… raw»
    T₀        «Энергии → T₀» ni — ThermoGar_T0.xlsx, sheet «T0»
    Выделения ni, 0.001 h, 40 classes — ThermoGar_precipitation_GAMMA_PRIME.xlsx
    Пакет     ni — batch-result-xlsx, «Составы фаз ат», «Составы фаз мас», «Исходные данные»

Run from the w21b root (PYTHONHASHSEED=0, MPLBACKEND=Agg, THERMOGAR_STATE_ROOT
in a temp folder, PYTHONDONTWRITEBYTECODE=1):
    python -B results/wave21_o/scripts/vygruzki_12b.py
Output: results/wave21_o/data/vygruzki_12b.csv (UTF-8 with BOM, «;»).
"""

from __future__ import annotations

import csv
import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "app"
TOOLS = ROOT / "tools"
sys.path[:0] = [str(APP), str(TOOLS)]
OUT = ROOT / "results" / "wave21_o" / "data" / "vygruzki_12b.csv"

import openpyxl  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

ROWS: list[dict[str, str]] = []


def start(base: str, state: dict[str, Any] | None = None):
    downloads: dict[str, bytes] = {}
    original = st.download_button

    def capture(label: Any, data: Any = None, *args: Any, **kwargs: Any) -> Any:
        name = str(kwargs.get("file_name") or label)
        if isinstance(data, (bytes, bytearray)):
            downloads[name] = bytes(data)
        return original(label, data, *args, **kwargs)

    st.download_button = capture
    app = AppTest.from_file(str(APP / "ThermoGar_app.py"), default_timeout=1800)
    app.session_state["thermogar_database_key"] = base
    for key, value in (state or {}).items():
        app.session_state[key] = value
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]
    return app, downloads


def sheet_header(payload: bytes, sheet: str) -> list[str]:
    book = openpyxl.load_workbook(io.BytesIO(payload), read_only=True)
    return [str(c.value) for c in next(book[sheet].iter_rows(max_row=1))]


def add(kind: str, file_name: str, part: str, before: list[str], after: list[str]) -> None:
    ROWS.append({
        "вид": kind, "файл": file_name, "лист / член": part,
        "до (таблица)": " | ".join(map(str, before)), "после (файл)": " | ".join(after),
        "совпадает": "да" if list(map(str, before)) == after else "нет",
    })
    print(kind, part, "->", " | ".join(after)[:120], flush=True)


def excel_single() -> None:
    app, downloads = start("ni")
    app.button(key="single_calculate").click().run()
    display = app.session_state["_thermogar_vlb_b3_result_equilibrium_single"]["display"]
    payload = downloads["ThermoGar_equilibrium.xlsx"]
    for sheet, key in (("Составы фаз ат", "phase_at"), ("Составы фаз мас", "phase_wt")):
        add("Excel", "ThermoGar_equilibrium.xlsx", sheet, list(display[key].columns), sheet_header(payload, sheet))


def csv_concentration() -> None:
    app, downloads = start("al")
    app.button(key="concentration_calculate").click().run()
    data = app.session_state["_thermogar_vlb_b3_result_equilibrium_composition_scan"]["display"]["data"]
    frame = pd.read_csv(io.BytesIO(downloads["ThermoGar_concentration_scan.csv"]))
    add("CSV", "ThermoGar_concentration_scan.csv", "заголовок", list(data.columns), [str(c) for c in frame.columns])


def zip_solidification() -> None:
    app, downloads = start("ni")
    app.button(key="solidification_calculate").click().run()
    state = app.session_state["solidification_result"]
    app.segmented_control(key="solidification_result_view").set_value("Выгрузка").run()
    archive = zipfile.ZipFile(io.BytesIO(downloads["ThermoGar_solidification_results.zip"]))
    xlsx = archive.read("ThermoGar_solidification.xlsx")
    for method_key in state["results"]:
        short = "Равновес" if method_key == "equilibrium" else "Scheil"
        member = f"{method_key}_liquid_composition.csv"
        frame = pd.read_csv(archive.open(member))
        add("ZIP", "ThermoGar_solidification_results.zip", member,
            list(state["liquid_tables"][method_key].columns), [str(c) for c in frame.columns])
        add("ZIP", "ThermoGar_solidification_results.zip", f"xlsx, «{short} расплав»",
            list(state["liquid_tables"][method_key].columns), sheet_header(xlsx, f"{short} расплав"))
        add("ZIP", "ThermoGar_solidification_results.zip", f"xlsx, «{short} raw»",
            list(state["raw_tables"][method_key].columns), sheet_header(xlsx, f"{short} raw"))


def tzero() -> None:
    app, downloads = start("ni")
    app.button(key="tzero_calculate").click().run()
    data = app.session_state["tzero_result"]["data"]
    add("T₀", "ThermoGar_T0.xlsx", "T0", list(data.columns), sheet_header(downloads["ThermoGar_T0.xlsx"], "T0"))


def precipitation() -> None:
    app, downloads = start("ni", {"precipitation_ni_user_duration_h": 0.001, "precipitation_ni_user_bins": 40})
    app.button(key="precipitation_ni_user_calculate").click().run()
    result = app.session_state["thermogar_precipitation_result"]
    app.segmented_control(key="precipitation_result_view").set_value("Экспорт и ограничения").run()
    payload = downloads["ThermoGar_precipitation_GAMMA_PRIME.xlsx"]
    add("Выделения", "ThermoGar_precipitation_GAMMA_PRIME.xlsx", "Состав матрицы",
        list(result.matrix_composition.columns), sheet_header(payload, "Состав матрицы"))
    add("Выделения", "ThermoGar_precipitation_GAMMA_PRIME.xlsx", "Межфазные составы",
        list(result.interface_composition.columns), sheet_header(payload, "Межфазные составы"))


def batch() -> None:
    import test_ui_h

    state_root = Path(tempfile.mkdtemp(prefix="tg21o_batch_"))
    os.environ["THERMOGAR_STATE_ROOT"] = str(state_root)
    app = AppTest.from_file(str(APP / "ThermoGar_app.py"), default_timeout=1800)
    app.run()
    uploader = [item for item in app.file_uploader if item.label == "Файл составов"][0]
    uploader.set_value(("batch.csv", test_ui_h.batch_csv(("ni",)), "text/csv"))
    app.run()
    test_ui_h.widget(app.button, "batch_calculate_button").click()
    app.run()
    result = app.session_state["workspace_batch_result"]["display"]
    test_ui_h.widget(app.button, "batch_result_export_prepare").click()
    app.run()
    payload = test_ui_h.stored_artifacts(state_root)["batch-result-xlsx-v1"]
    for sheet in ("Составы фаз ат", "Составы фаз мас", "Исходные данные"):
        add("Пакет", "ThermoGar_batch_result.xlsx", sheet, list(result[sheet].columns), sheet_header(payload, sheet))


def main() -> int:
    for step in (excel_single, csv_concentration, zip_solidification, tzero, precipitation, batch):
        step()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ROWS[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(ROWS)
    print("rows", len(ROWS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
