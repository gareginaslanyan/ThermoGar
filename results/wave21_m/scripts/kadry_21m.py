"""21-M, step 8: frames and measurements after the changes of 21-M.

The app must run on port 8640 (run_app.cmd of this folder). Window 1440x900;
light theme in a default session, dark with ``?embed_options=dark_theme``
(as kadry.py). Every case opens a new browser context (a new session) and
chooses the database in the sidebar (make_guide_screens.set_database);
the sidebar is then collapsed back, as the page opens it.

Phases (argument, default all):

    pervyi        21 screens of ni (formy.run_base of 21-I): the first
                  primary button — bottom ≤ 900 px means «on the first
                  screen»; a window frame of every screen
    binarnaya     «Диаграммы → Бинарная T–X» ni: whole page; then
                  «Шаг по температуре, °C» = 20 — the caption «Не по умолчанию»
    knopki        «Вклады упрочнения» empty and with the source only;
                  «Упругие свойства», step 2 (after «Получить фазовые доли»)
    umolch        defaults 5–9 after pressing the button, time of each
    zatverdevanie «Затвердевание» with «Точность и критерии» open

Frames: results/wave21_m/kadry/; records: results/wave21_m/kadry_21m.json
(merged per phase). The time of a calculation is counted from the click to
the idle script (make_guide_screens.wait_idle), limit 15 minutes.

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_m\\scripts\\kadry_21m.py [phase ...]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kadry  # noqa: E402  (21-M copy: port 8640, state tg21m_state)
import formy  # noqa: E402  (21-M copy of 21-I: screens of a database)

mgs = kadry.mgs
KADRY = kadry.KADRY
RECORD = kadry.REPO_ROOT / "results" / "wave21_m" / "kadry_21m.json"
LIMIT_S = 900
BASE_LABEL = {"ni": mgs.DB_NI, "al": mgs.DB_AL, "fe": mgs.DB_FE}
ALL_PHASES = ("pervyi", "binarnaya", "knopki", "umolch", "zatverdevanie")

CAPTIONS_JS = """
() => [...document.querySelectorAll('[data-testid="stMain"] [data-testid="stCaptionContainer"]')]
  .filter(e => e.offsetParent !== null).map(e => e.innerText.trim())
"""
ROW_JS = """
(key) => {
  const row = document.querySelector(`[class*="st-key-${key}"]`);
  if (!row) return null;
  const wrapper = row.closest('[data-testid="stLayoutWrapper"]') || row;
  const s = getComputedStyle(wrapper);
  const r = wrapper.getBoundingClientRect();
  const button = row.querySelector('button');
  const b = button ? button.getBoundingClientRect() : null;
  return {position: s.position, top: Math.round(r.top), bottom: Math.round(r.bottom),
          captions: [...row.querySelectorAll('[data-testid="stCaptionContainer"]')].map(e => e.innerText.trim()),
          button: button ? {text: button.innerText.trim(), disabled: button.disabled,
                            top: Math.round(b.top), bottom: Math.round(b.bottom)} : null};
}
"""
METRICS_JS = """
() => [...document.querySelectorAll('[data-testid="stMain"] [data-testid="stMetric"]')]
  .filter(e => e.offsetParent !== null)
  .map(e => ({label: (e.querySelector('[data-testid="stMetricLabel"]') || {}).innerText,
              value: (e.querySelector('[data-testid="stMetricValue"]') || {}).innerText}))
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
        locale="ru-RU", timezone_id="Europe/Moscow",
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
    collapsed = bool(expand.count() and expand.first.is_visible())
    if collapsed:
        expand.first.click()
        mgs.wait_idle(page)
    mgs.set_database(page, BASE_LABEL[base])
    mgs.wait_idle(page)
    if collapsed:
        page.locator('[data-testid="stSidebar"]').hover()
        page.locator('[data-testid="stSidebarCollapseButton"] button').first.click()
        mgs.wait_idle(page)
        page.wait_for_timeout(500)
    return context, page


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


# --------------------------------------------------------------------------- #


def phase_pervyi(browser, record: dict) -> None:
    out = record.setdefault("pervyi", {})
    for theme in kadry.THEMES:
        slug = kadry.THEME_SLUG[theme]
        context, page = new_page(browser, theme, "ni")
        counter = {"n": 0}
        original = formy.measure

        def measure(page_, path, _slug=slug):
            data = original(page_, path)
            counter["n"] += 1
            name = f"pervyi_{counter['n']:02d}_{_slug}"
            if data is not None:
                data["frame"] = window_frame(page_, name)
            return data

        formy.measure = measure
        try:
            screens: list[dict] = []
            top_names = list(kadry.TOP_TABS)
            for top, subtabs in kadry.TOP_TABS.items():
                mgs.open_tab(page, top)
                if not subtabs:
                    formy.screens_of(page, [top], top_names, screens)
                    continue
                for subtab in subtabs:
                    mgs.open_tab(page, subtab)
                    formy.screens_of(page, [top, subtab], top_names + subtabs, screens)
        finally:
            formy.measure = original
        out[theme] = [
            {"screen": s["screen"], "button": s["button"], "first_screen": s["first_screen"],
             "frame": s.get("frame")}
            for s in screens
        ]
        on_first = sum(1 for s in screens if s["first_screen"])
        print(f"[{theme}] screens {len(screens)}, button on the first screen {on_first}", flush=True)
        context.close()


def open_binary(page) -> None:
    mgs.open_tab(page, "Диаграммы")
    mgs.open_tab(page, "Бинарная T–X")


def phase_binarnaya(browser, record: dict) -> None:
    out = record.setdefault("binarnaya", {})
    for theme in kadry.THEMES:
        slug = kadry.THEME_SLUG[theme]
        context, page = new_page(browser, theme, "ni")
        open_binary(page)
        to_top(page)
        entry = {"row_before": page.evaluate(ROW_JS, "tg_action_binary")}
        entry["first_screen"] = window_frame(page, f"binarnaya_ni_nachalo_{slug}")
        entry["page"] = page_frame(page, f"binarnaya_ni_stranica_{slug}")
        root = mgs.main_area(page)
        mgs.open_expander(page, root, "Точность и критерии")
        mgs.set_number(root, "Шаг по температуре, °C", "20")
        mgs.wait_idle(page)
        to_top(page)
        entry["row_after"] = page.evaluate(ROW_JS, "tg_action_binary")
        entry["first_screen_changed"] = window_frame(page, f"binarnaya_ni_shag20_nachalo_{slug}")
        entry["page_changed"] = page_frame(page, f"binarnaya_ni_shag20_stranica_{slug}")
        out[theme] = entry
        print(f"[{theme}] binary: {entry['row_after']['captions']}", flush=True)
        context.close()


def phase_knopki(browser, record: dict) -> None:
    out = record.setdefault("knopki", {})
    for theme in kadry.THEMES:
        slug = kadry.THEME_SLUG[theme]
        entry = {}
        context, page = new_page(browser, theme, "ni")
        mgs.open_tab(page, "Свойства")
        mgs.open_tab(page, "Вклады упрочнения")
        to_top(page)
        entry["vklady_pusto"] = {"row": page.evaluate(ROW_JS, "tg_action_strengthening"),
                                 "frame": window_frame(page, f"vklady_pusto_{slug}")}
        root = mgs.main_area(page)
        mgs.set_text_area(root, "Источник и область применимости входов", "Проверка 21-М")
        mgs.wait_idle(page)
        to_top(page)
        entry["vklady_istochnik"] = {"row": page.evaluate(ROW_JS, "tg_action_strengthening"),
                                     "frame": window_frame(page, f"vklady_istochnik_bez_galochki_{slug}")}
        mgs.open_tab(page, "Упругие свойства")
        seconds, idle = press(page, "Получить фазовые доли")
        vrh = mgs.main_area(page).get_by_role("button", name="Рассчитать Voigt–Reuss–Hill", exact=True)
        vrh.scroll_into_view_if_needed()
        page.mouse.move(5, 5)
        page.wait_for_timeout(300)
        entry["uprugie_shag2"] = {"seconds_step1": round(seconds, 1), "idle": idle,
                                  "row": page.evaluate(ROW_JS, "b4b2_elastic_vrh_action"),
                                  "frame": window_frame(page, f"uprugie_shag2_{slug}")}
        out[theme] = entry
        print(f"[{theme}] knopki: {entry['vklady_pusto']['row']['captions']} / "
              f"{entry['vklady_istochnik']['row']['captions']} / "
              f"{entry['uprugie_shag2']['row']['captions']}", flush=True)
        context.close()


UMOLCH = [
    # (id, base, path, button, decision)
    ("temperaturnyi_fe", "fe", ["Расчёты", "Температурный диапазон"], "Построить график по температуре", "5"),
    ("plotnost_t_fe", "fe", ["Свойства", "Плотность по T"], "Построить плотность по температуре", "5"),
    ("plotnost_t_al", "al", ["Свойства", "Плотность по T"], "Построить плотность по температуре", "15Б"),
    ("sostav_fe", "fe", ["Расчёты", "Изменение состава"], "Построить график по составу", "6"),
    ("sostav_al", "al", ["Расчёты", "Изменение состава"], "Построить график по составу", "7"),
    ("mnogokomp_ni", "ni", ["Диаграммы", "Многокомпонентное T–X"], "Построить многокомпонентное сечение", "8Б"),
    ("gomogenizaciya_ni", "ni", ["Кинетика", "Диффузия и гомогенизация", "Многофазная гомогенизация"],
     "Рассчитать гомогенизацию", "9, 16Б"),
]


def phase_umolch(browser, record: dict) -> None:
    out = record.setdefault("umolch", {})
    for theme in kadry.THEMES:
        slug = kadry.THEME_SLUG[theme]
        for case, base, path, button, decision in UMOLCH:
            if kadry.free_gib() < kadry.MIN_FREE_GIB:
                raise RuntimeError("STOP: free memory below 3 GiB")
            context, page = new_page(browser, theme, base)
            for name in path:
                if name == "Многофазная гомогенизация":
                    formy.open_view(page, "Диффузия и гомогенизация", name)
                else:
                    mgs.open_tab(page, name)
            seconds, idle = press(page, button)
            page.mouse.move(5, 5)
            entry = {
                "base": base, "screen": " / ".join(path), "button": button, "decision": decision,
                "seconds": round(seconds, 1), "idle": idle,
                "metrics": page.evaluate(METRICS_JS),
                "alerts": page.evaluate(kadry.FRAME_INFO_JS)["alerts"],
                "frames": page_frame(page, f"umolch_{case}_{slug}"),
            }
            out[f"{case}_{slug}"] = entry
            print(f"[{theme}] {case}: {entry['seconds']} s, idle {idle}, metrics {entry['metrics']}",
                  flush=True)
            context.close()


def phase_zatverdevanie(browser, record: dict) -> None:
    out = record.setdefault("zatverdevanie", {})
    for theme in kadry.THEMES:
        slug = kadry.THEME_SLUG[theme]
        context, page = new_page(browser, theme, "ni")
        mgs.open_tab(page, "Затвердевание")
        root = mgs.main_area(page)
        mgs.open_expander(page, root, "Точность и критерии")
        labels = page.evaluate(
            """() => [...document.querySelectorAll('[data-testid="stMain"] [data-testid="stExpander"] details[open] [data-testid="stWidgetLabel"]')]
              .filter(e => e.offsetParent !== null).map(e => e.innerText.trim())"""
        )
        block = mgs.expander(root, "Точность и критерии")
        block.scroll_into_view_if_needed()
        page.mouse.move(5, 5)
        out[theme] = {"labels": labels, "frames": page_frame(page, f"zatverdevanie_tochnost_{slug}")}
        print(f"[{theme}] zatverdevanie: {[l for l in labels if '0.0001' in l]}", flush=True)
        context.close()


PHASES = {
    "pervyi": phase_pervyi,
    "binarnaya": phase_binarnaya,
    "knopki": phase_knopki,
    "umolch": phase_umolch,
    "zatverdevanie": phase_zatverdevanie,
}


def main() -> int:
    phases = sys.argv[1:] or list(ALL_PHASES)
    free = kadry.free_gib()
    print(f"free memory {free:.2f} GiB", flush=True)
    if free < kadry.MIN_FREE_GIB:
        print(f"STOP: free memory below {kadry.MIN_FREE_GIB} GiB", file=sys.stderr)
        return 3
    if not mgs.app_is_ready(kadry.PORT):
        print(f"STOP: no app on port {kadry.PORT}", file=sys.stderr)
        return 2
    KADRY.mkdir(parents=True, exist_ok=True)
    record = load_record()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        try:
            for phase in phases:
                started = time.monotonic()
                PHASES[phase](browser, record)
                record.setdefault("_hod", {})[phase] = round(time.monotonic() - started, 1)
                save_record(record)
        finally:
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
