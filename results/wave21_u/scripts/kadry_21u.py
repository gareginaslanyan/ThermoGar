"""21-U, step 5: frames of the empty-cell dash (BL-68, owner decision 26.09.2026).

Copy of the helpers of kadry_21o.py (21-O): the app runs on port 8661
(run_app.cmd of this folder) and is restarted before every case. Window
1440x900; light theme in a default session, dark with
``?embed_options=dark_theme`` (as kadry.py). Every case opens a new browser
context and chooses the database in the sidebar.

Cases (argument, default all), both themes:

    tzero_fe_umolch  «Энергии → T₀» fe by default (200–950 °C): the result
                     table scrolled to the rows C 1.8–2.0 mas.% (dash in
                     «T₀, °C» and «T₀, K»); Excel T0 downloaded — rows, points
                     found, empty T₀ cells (the data keep NaN)
    uprugie_shag2    «Свойства → Упругие свойства» ni by default, step 2 after
                     «Получить фазовые доли»: dash in the empty editor cells

Frames: results/wave21_u/kadry/ (window 1440x900 and the table alone);
records: results/wave21_u/kadry_21u.json.

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_u\\scripts\\kadry_21u.py [case ...]
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
import kadry  # noqa: E402  (21-U copy: port 8661, state tg21u_state)
import formy  # noqa: E402  (21-U copy of 21-O)

mgs = kadry.mgs
KADRY = kadry.KADRY
RECORD = kadry.REPO_ROOT / "results" / "wave21_u" / "kadry_21u.json"
DOWNLOADS = Path(os.environ["TEMP"]) / "tg21u_downloads"
LOGS = Path(os.environ["TEMP"]) / "tg21u_logs"
LIMIT_S = 900
BASE_LABEL = {"ni": mgs.DB_NI, "al": mgs.DB_AL, "fe": mgs.DB_FE}
TABLES = '[data-testid="stMain"] [data-testid="stDataFrame"]'

ALERTS_JS = """
() => [...document.querySelectorAll('[data-testid="stMain"] [data-testid^="stAlertContent"]')]
  .filter(e => e.offsetParent !== null)
  .map(e => ({kind: e.dataset.testid.replace('stAlertContent', '').toLowerCase(),
              text: e.innerText.trim()}))
"""

# Text of the accessible grid glide-data-grid keeps next to its canvas:
# rows now in view, cell by cell.
GRID_JS = """
(el) => [...el.querySelectorAll('[role="row"]')]
  .map(r => [...r.querySelectorAll('[role="gridcell"], [role="columnheader"]')]
    .map(c => c.innerText.trim()))
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
    """A new app process before every case, as kadry_21o.restart_app (21-O)."""

    for pid in sorted(port_pids(kadry.PORT)):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    deadline = time.monotonic() + 30
    while port_pids(kadry.PORT) and time.monotonic() < deadline:
        time.sleep(1)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = open(LOGS / "app_8661.log", "ab")
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


def visible_table(page, index: int):
    tables = page.locator(f"{TABLES}:visible")
    count = tables.count()
    if count == 0:
        raise RuntimeError("no visible table")
    return tables.nth(index if index >= 0 else count + index), count


def frames(page, table, stem: str) -> list[str]:
    """Window 1440x900 with the table in the middle, and the table alone."""

    table.scroll_into_view_if_needed()
    box = table.bounding_box()
    page.mouse.wheel(0, box["y"] + box["height"] / 2 - kadry.VIEWPORT["height"] / 2)
    page.wait_for_timeout(600)
    window = KADRY / f"{stem}.png"
    page.screenshot(path=str(window))
    alone = KADRY / f"{stem}_tablica.png"
    table.screenshot(path=str(alone))
    return [window.name, alone.name]


def scroll_grid_to_end(page, table) -> None:
    # The wheel reaches the grid only while the grid is inside the window.
    table.scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    box = table.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    for _ in range(6):
        page.mouse.wheel(0, 400)
        page.wait_for_timeout(150)
    page.mouse.move(5, 5)
    page.wait_for_timeout(600)


# --------------------------------------------------------------------------- #


def run_tzero(browser, record: dict, theme: str) -> dict:
    context, page = new_page(browser, theme, "fe")
    try:
        collapse_sidebar(page)
        mgs.open_tab(page, "Энергии")
        mgs.open_tab(page, "T₀")
        seconds, idle = press(page, "Рассчитать T₀")
        entry = {"seconds": round(seconds, 1), "idle": idle}
        entry["alerts"] = page.evaluate(ALERTS_JS)
        page.evaluate(formy.SCROLL_TOP_JS)
        table, count = visible_table(page, -1)
        entry["visible_tables"] = count
        scroll_grid_to_end(page, table)
        entry["grid_rows_in_view"] = table.evaluate(GRID_JS)
        slug = kadry.THEME_SLUG[theme]
        entry["frames"] = frames(page, table, f"tzero_fe_umolch_{slug}")
        excel = download(page, "Скачать Excel", f"tzero_fe_umolch_{slug}")
        data = pd.read_excel(excel, sheet_name="T0")
        entry["header"] = [str(column) for column in data.columns]
        entry["rows"] = int(len(data))
        entry["found"] = int(data["Решение найдено"].sum())
        tail = data[data.iloc[:, 0].round(6).isin([1.8, 1.9, 2.0])]
        entry["tail_composition"] = [float(x) for x in tail.iloc[:, 0]]
        entry["tail_tzero_c_empty"] = int(tail["T₀, °C"].isna().sum())
        entry["tail_tzero_k_empty"] = int(tail["T₀, K"].isna().sum())
        entry["tzero_c_empty"] = int(data["T₀, °C"].isna().sum())
        entry["excel"] = excel.name
        return entry
    finally:
        context.close()


def run_uprugie(browser, record: dict, theme: str) -> dict:
    context, page = new_page(browser, theme, "ni")
    try:
        collapse_sidebar(page)
        mgs.open_tab(page, "Свойства")
        mgs.open_tab(page, "Упругие свойства")
        seconds, idle = press(page, "Получить фазовые доли")
        entry = {"seconds_step1": round(seconds, 1), "idle": idle}
        entry["alerts"] = page.evaluate(ALERTS_JS)
        page.evaluate(formy.SCROLL_TOP_JS)
        table, count = visible_table(page, -1)
        entry["visible_tables"] = count
        entry["grid_rows_in_view"] = table.evaluate(GRID_JS)
        slug = kadry.THEME_SLUG[theme]
        entry["frames"] = frames(page, table, f"uprugie_shag2_{slug}")
        return entry
    finally:
        context.close()


CASES = {"tzero_fe_umolch": run_tzero, "uprugie_shag2": run_uprugie}


def main() -> int:
    cases = sys.argv[1:] or list(CASES)
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
                for theme in kadry.THEMES:
                    slug = kadry.THEME_SLUG[theme]
                    restart_app()
                    free = kadry.free_gib()
                    if free < kadry.MIN_FREE_GIB:
                        raise RuntimeError(f"STOP: free memory {free:.2f} GiB below 3 GiB")
                    started = time.monotonic()
                    entry = CASES[case](browser, record, theme)
                    entry["theme"] = theme
                    entry["free_gib_before"] = round(free, 2)
                    entry["case_seconds"] = round(time.monotonic() - started, 1)
                    record[f"{case}_{slug}"] = entry
                    save_record(record)
                    print(f"[{theme}] {case}: {entry.get('seconds', entry.get('seconds_step1'))} s, "
                          f"frames {entry['frames']}", flush=True)
        finally:
            browser.close()
            for pid in sorted(port_pids(kadry.PORT)):
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
