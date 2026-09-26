"""21-O, step 7: frames and measurements after the changes of 21-O.

The app must run on port 8651 (run_app.cmd of this folder); it is restarted
before every case (restart_app, as kadry_21m.py of 21-M: the worker pool keeps
about 1 GiB per worker). Window 1440x900; light theme in a default session,
dark with ``?embed_options=dark_theme`` (as kadry.py). Every case opens a new
browser context and chooses the database in the sidebar.

Cases (argument, default all), theme in brackets:

    vyd_fe_yacheyka   «Выделения» fe: the cell of test_ui_g::test_kwn_precipitation[fe]
                      (BCC_A2 / M23C6, 700 °C, 0.001 h, 40 classes) [light]
    vyd_fe_umolch     «Выделения» fe by default (0.01 h, 80 classes) [light]
    vyd_ni_umolch     «Выделения» ni by default (100 h) [light]
    vyd_al_umolch     «Выделения» al by default (24 h) [light]
    vyd_718           «Выделения» 718 (base ni, balance Fe) [light, dark]
    tzero_fe_umolch   «Энергии → T₀» fe by default (200–950 °C) [light, dark]
    tzero_fe_300_1700 «Энергии → T₀» fe, window 300–1700 °C [light]

The time of a calculation is counted from the click to the idle script
(make_guide_screens.wait_idle), limit 15 minutes. After a KWN run the Excel
of «Экспорт и ограничения» is downloaded: rows of «Кинетика», final fraction
and mean radius, headers of «Состав матрицы» and «Межфазные составы» (12Б).
After T₀ the Excel is downloaded: rows, points found, empty compositions.

Frames: results/wave21_o/kadry/; records: results/wave21_o/kadry_21o.json.

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_o\\scripts\\kadry_21o.py [case ...]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kadry  # noqa: E402  (21-O copy: port 8651, state tg21o_state)
import formy  # noqa: E402  (21-O copy of 21-M)

mgs = kadry.mgs
KADRY = kadry.KADRY
RECORD = kadry.REPO_ROOT / "results" / "wave21_o" / "kadry_21o.json"
DOWNLOADS = Path(os.environ["TEMP"]) / "tg21o_downloads"
LOGS = Path(os.environ["TEMP"]) / "tg21o_logs"
LIMIT_S = 900
BASE_LABEL = {"ni": mgs.DB_NI, "al": mgs.DB_AL, "fe": mgs.DB_FE}
KWN_BUTTON = "Рассчитать кинетику выделений"
ALLOY_718 = "NI=54.2, CR=17.9, NB=5.3, MO=2.99, TI=0.97, AL=0.5"

ALERTS_JS = """
() => [...document.querySelectorAll('[data-testid="stMain"] [data-testid^="stAlertContent"]')]
  .filter(e => e.offsetParent !== null)
  .map(e => ({kind: e.dataset.testid.replace('stAlertContent', '').toLowerCase(),
              text: e.innerText.trim()}))
"""


def load_record() -> dict:
    if RECORD.exists():
        return json.loads(RECORD.read_text("utf-8"))
    return {}


def save_record(record: dict) -> None:
    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def new_page(browser, theme: str, base: str):
    context = browser.new_context(
        viewport=dict(kadry.VIEWPORT), device_scale_factor=1, color_scheme="light",
        locale="ru-RU", timezone_id="Europe/Moscow", accept_downloads=True,
    )
    context.set_default_timeout(mgs.UI_TIMEOUT_MS)
    page = context.new_page()
    query = "?embed_options=dark_theme" if theme == "Dark" else ""
    page.goto(f"http://127.0.0.1:{kadry.PORT}/{query}", wait_until="domcontentloaded")
    page.get_by_role("tab", name="Расчёты", exact=True).wait_for(timeout=mgs.CALC_TIMEOUT_MS)
    mgs.wait_idle(page)
    page.wait_for_timeout(500)
    if kadry.current_theme(page) != theme:
        raise RuntimeError(f"theme {kadry.current_theme(page)} != {theme}")
    expand = page.locator('[data-testid="stExpandSidebarButton"]')
    if expand.count() and expand.first.is_visible():
        expand.first.click()
        mgs.wait_idle(page)
    mgs.set_database(page, BASE_LABEL[base])
    mgs.wait_idle(page)
    return context, page


def collapse_sidebar(page) -> None:
    page.locator('[data-testid="stSidebar"]').hover()
    page.locator('[data-testid="stSidebarCollapseButton"] button').first.click()
    mgs.wait_idle(page)
    page.wait_for_timeout(500)


def set_composition(page, balance: str, units: str, additions: str) -> None:
    """As results/wave17_d/guide_screens_042.py (17-D)."""

    side = mgs.sidebar(page)
    mgs.set_text_area(side, "Добавки", additions)
    mgs.wait_idle(page)
    field = mgs.widget(side, "stSelectbox", "Элемент-основа").locator('input[role="combobox"]').first
    field.click()
    # 21-Ж: the list shows element symbols as Fe, Ni (was FE in 17-D).
    shown = balance[:1] + balance[1:].lower()
    field.fill(shown)
    page.get_by_role("option", name=shown, exact=True).first.click()
    mgs.wait_idle(page)
    mgs.set_radio(side, "Единицы состава", units)
    mgs.wait_idle(page)
    mgs.set_text_area(side, "Добавки", additions)
    mgs.wait_idle(page)


def numbers(page, values: dict[str, str]) -> None:
    for label, value in values.items():
        mgs.set_number(mgs.main_area(page), label, value)
        mgs.wait_idle(page)


def set_bins(page, value: int) -> None:
    """«Классов размеров» is st.slider 20–200 step 10: keyboard on its thumb."""

    thumb = mgs.main_area(page).locator('[data-testid="stSlider"]:visible').filter(
        has_text="Классов размеров"
    ).first.get_by_role("slider")
    thumb.focus()
    thumb.press("Home")
    for _ in range((value - 20) // 10):
        thumb.press("ArrowRight")
    mgs.wait_idle(page)
    now = thumb.input_value()
    if now != str(value):
        raise RuntimeError(f"bins {now} != {value}")


def choose(page, label: str, option: str) -> None:
    """Type the option into the combobox and pick it: in the 718 case a click
    on the field did not open the list (mgs.set_selectbox waits for it)."""

    control = mgs.widget(mgs.main_area(page), "stSelectbox", label)
    field = control.locator('input[role="combobox"]').first
    field.scroll_into_view_if_needed()
    field.click()
    field.fill(option)
    page.get_by_role("option", name=option, exact=True).first.click()
    mgs.wait_idle(page)


def to_top(page) -> None:
    page.mouse.move(5, 5)
    page.evaluate(formy.SCROLL_TOP_JS)
    page.wait_for_timeout(300)


def window_frame(page, stem: str) -> str:
    path = KADRY / f"{stem}.png"
    page.screenshot(path=str(path))
    return path.name


def page_frame(page, stem: str) -> list[str]:
    to_top(page)
    paths, _info = kadry.capture(page, stem, with_sidebar=False)
    return [path.name for path in paths]


def press(page, name: str) -> tuple[float, bool]:
    root = mgs.main_area(page)
    button = root.get_by_role("button", name=name, exact=True).last
    button.scroll_into_view_if_needed()
    started = time.monotonic()
    button.click()
    mgs.CALC_TIMEOUT_MS = LIMIT_S * 1000
    try:
        mgs.wait_idle(page)
    except TimeoutError:
        return time.monotonic() - started, False
    return time.monotonic() - started, True


def download(page, label: str, stem: str) -> Path:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    button = mgs.main_area(page).get_by_role("button", name=label, exact=True).first
    button.scroll_into_view_if_needed()
    with page.expect_download() as info:
        button.click()
    path = DOWNLOADS / f"{stem}_{info.value.suggested_filename}"
    info.value.save_as(str(path))
    return path


def port_pids(port: int) -> set[int]:
    out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True,
                         encoding="oem", errors="replace").stdout
    return {
        int(parts[4]) for parts in (line.split() for line in out.splitlines())
        if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3] == "LISTENING"
    }


def restart_app() -> None:
    """A new app process before every case, as kadry_21m.restart_app (21-M)."""

    for pid in sorted(port_pids(kadry.PORT)):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    deadline = time.monotonic() + 30
    while port_pids(kadry.PORT) and time.monotonic() < deadline:
        time.sleep(1)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = open(LOGS / "app_8651.log", "ab")
    subprocess.Popen(
        ["cmd", "/c", str(Path(__file__).resolve().parent / "run_app.cmd")],
        stdout=log, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    deadline = time.monotonic() + 180
    while not mgs.app_is_ready(kadry.PORT):
        if time.monotonic() > deadline:
            raise RuntimeError("app did not start in 180 s")
        time.sleep(1)


def header(frame: pd.DataFrame) -> list[str]:
    return [str(column) for column in frame.columns]


# --------------------------------------------------------------------------- #


def kwn_case(page, stem: str, entry: dict) -> None:
    mgs.open_tab(page, "Кинетика")
    mgs.open_tab(page, "Выделения")
    values = {item: mgs.widget(mgs.main_area(page), "stNumberInput", item)
              .locator("input").first.input_value()
              for item in ("Температура, °C", "Время выдержки, ч")}
    entry["inputs_on_screen"] = values
    seconds, idle = press(page, KWN_BUTTON)
    entry.update({"seconds": round(seconds, 1), "idle": idle})
    to_top(page)
    entry["alerts"] = page.evaluate(ALERTS_JS)
    entry["frames"] = page_frame(page, stem)
    formy.open_view(page, "Кинетика выделений", "Экспорт и ограничения")
    excel = download(page, "Скачать Excel", stem)
    book = pd.read_excel(excel, sheet_name=None)
    kinetics = book["Кинетика"]
    entry["rows"] = int(len(kinetics))
    entry["final_time_s"] = float(kinetics.iloc[-1, 0]) if len(kinetics) else None
    entry["fraction_pct"] = float(kinetics["Объёмная доля, %"].iloc[-1])
    entry["radius_nm"] = float(kinetics["Средний радиус, нм"].iloc[-1])
    entry["quality"] = book["Проверки"].to_dict("records")
    entry["header_matrix"] = header(book["Состав матрицы"])
    entry["header_interface"] = header(book["Межфазные составы"])
    entry["excel"] = excel.name


def case_vyd(browser, theme: str, base: str, stem: str, setup=None) -> dict:
    context, page = new_page(browser, theme, base)
    try:
        if setup is not None:
            setup(page)
        collapse_sidebar(page)
        entry = {"base": base, "theme": theme}
        if setup is not None:
            mgs.open_tab(page, "Кинетика")
            mgs.open_tab(page, "Выделения")
            setup.after_tab(page)  # type: ignore[attr-defined]
        kwn_case(page, stem, entry)
        return entry
    finally:
        context.close()


class Setup:
    def __init__(self, sidebar=None, form=None) -> None:
        self.sidebar = sidebar
        self.form = form

    def __call__(self, page) -> None:
        if self.sidebar is not None:
            self.sidebar(page)

    def after_tab(self, page) -> None:
        if self.form is not None:
            self.form(page)


def form_fe_cell(page) -> None:
    root = mgs.main_area(page)
    mgs.set_selectbox(page, root, "Матричная фаза", "BCC_A2")
    mgs.set_selectbox(page, mgs.main_area(page), "Фаза-выделение", "M23C6")
    numbers(page, {"Температура, °C": "700", "Время выдержки, ч": "0.001"})
    mgs.open_expander(page, mgs.main_area(page), "Численная сетка размеров")
    set_bins(page, 40)


def sidebar_718(page) -> None:
    set_composition(page, "FE", "массовые %", ALLOY_718)


def form_718(page) -> None:
    root = mgs.main_area(page)
    choose(page, "Матричная фаза", "FCC_A1")
    choose(page, "Фаза-выделение", "GAMMA_DP")
    numbers(page, {
        "Температура, °C": "700",
        "Время выдержки, ч": "100",
        "Межфазная энергия, Дж/м²": "0.095",
        "Молярный объём матрицы, см³/моль": "7.145624",
        "Молярный объём выделения, см³/моль": "7.3",
        "Плотность объёмных центров, 1/м³": "8.4277e28",
    })
    mgs.open_expander(page, mgs.main_area(page), "Численная сетка размеров")
    numbers(page, {
        "Минимальный радиус, нм": "0.1",
        "Начальный максимальный радиус, нм": "50",
    })
    set_bins(page, 200)


KWN_CASES = {
    "vyd_fe_yacheyka": ("fe", ("Light",), Setup(form=form_fe_cell)),
    "vyd_fe_umolch": ("fe", ("Light",), None),
    "vyd_ni_umolch": ("ni", ("Light",), None),
    "vyd_al_umolch": ("al", ("Light",), None),
    "vyd_718": ("ni", ("Light", "Dark"), Setup(sidebar=sidebar_718, form=form_718)),
}


def run_kwn(browser, record: dict, case: str) -> None:
    base, themes, setup = KWN_CASES[case]
    for theme in themes:
        slug = kadry.THEME_SLUG[theme]
        restart_app()
        free = kadry.free_gib()
        if free < kadry.MIN_FREE_GIB:
            raise RuntimeError(f"STOP: free memory {free:.2f} GiB below 3 GiB")
        entry = case_vyd(browser, theme, base, f"{case}_{slug}", setup)
        entry["free_gib_before"] = round(free, 2)
        record[f"{case}_{slug}"] = entry
        save_record(record)
        print(f"[{theme}] {case}: {entry['seconds']} s, rows {entry['rows']}, "
              f"{entry['fraction_pct']:.4f} %, R {entry['radius_nm']:.3f} nm, "
              f"alerts {[a['text'][:60] for a in entry['alerts']]}", flush=True)


def run_tzero(browser, record: dict, case: str) -> None:
    window = None if case == "tzero_fe_umolch" else ("300", "1700")
    themes = ("Light", "Dark") if window is None else ("Light",)
    for theme in themes:
        slug = kadry.THEME_SLUG[theme]
        restart_app()
        free = kadry.free_gib()
        if free < kadry.MIN_FREE_GIB:
            raise RuntimeError(f"STOP: free memory {free:.2f} GiB below 3 GiB")
        context, page = new_page(browser, theme, "fe")
        try:
            collapse_sidebar(page)
            mgs.open_tab(page, "Энергии")
            mgs.open_tab(page, "T₀")
            if window is not None:
                numbers(page, {
                    "Нижняя граница поиска T₀, °C": window[0],
                    "Верхняя граница поиска T₀, °C": window[1],
                })
            root = mgs.main_area(page)
            entry = {"theme": theme, "free_gib_before": round(free, 2), "window_on_screen": [
                mgs.widget(root, "stNumberInput", label).locator("input").first.input_value()
                for label in ("Нижняя граница поиска T₀, °C", "Верхняя граница поиска T₀, °C")
            ]}
            seconds, idle = press(page, "Рассчитать T₀")
            entry.update({"seconds": round(seconds, 1), "idle": idle})
            entry["alerts"] = page.evaluate(ALERTS_JS)
            entry["frames"] = page_frame(page, f"{case}_{slug}")
            excel = download(page, "Скачать Excel", f"{case}_{slug}")
            data = pd.read_excel(excel, sheet_name="T0")
            entry["header"] = header(data)
            entry["rows"] = int(len(data))
            entry["found"] = int(data["Решение найдено"].sum())
            entry["composition_empty"] = int(data.iloc[:, 0].isna().sum())
            entry["composition"] = [float(x) for x in data.iloc[:, 0]]
            entry["tzero_c"] = [None if pd.isna(x) else round(float(x), 2) for x in data["T₀, °C"]]
            entry["excel"] = excel.name
        finally:
            context.close()
        record[f"{case}_{slug}"] = entry
        save_record(record)
        print(f"[{theme}] {case}: {entry['seconds']} s, rows {entry['rows']}, found {entry['found']}, "
              f"empty {entry['composition_empty']}", flush=True)


CASES = list(KWN_CASES) + ["tzero_fe_umolch", "tzero_fe_300_1700"]


def main() -> int:
    cases = sys.argv[1:] or CASES
    free = kadry.free_gib()
    print(f"free memory {free:.2f} GiB", flush=True)
    if free < kadry.MIN_FREE_GIB:
        print(f"STOP: free memory below {kadry.MIN_FREE_GIB} GiB", file=sys.stderr)
        return 3
    KADRY.mkdir(parents=True, exist_ok=True)
    record = load_record()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        try:
            for case in cases:
                started = time.monotonic()
                if case in KWN_CASES:
                    run_kwn(browser, record, case)
                else:
                    run_tzero(browser, record, case)
                record.setdefault("_hod", {})[case] = round(time.monotonic() - started, 1)
                save_record(record)
        finally:
            browser.close()
            for pid in sorted(port_pids(kadry.PORT)):
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
