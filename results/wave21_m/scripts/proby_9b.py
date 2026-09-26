"""21-L, step 3: 9B probes by styles injected into the open page (Playwright
add_style_tag). The code and app/style.css are not changed.

App as in step 2 (progon_10b.start_app): a new process on port 8639, an empty
state root %TEMP%\\tg21l_state\\<run>, database ni, window 1440x900, the
sidebar as the page opens (collapsed), no calculations unless said.

    kompakt   (run 53, light) a) compact header: DOM of the primary button on
              21 screens; measurement without injected styles; search of the
              smallest top padding of the main area at which the top tab list
              stays below the Streamlit header; the same measurement with
              9b/kompakt.css; frames at the top of three screens.
    lipkaya   (run 54 light, 55 dark) b) sticky primary button: 9b/lipkaya.css;
              light: measurement on 21 screens, form and column buttons; both
              themes: frames of «Бинарная T–X» and «Выделения» at the top,
              «Бинарная T–X» after the default calculation, scrolled to the result.

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_l\\scripts\\proby_9b.py kompakt
    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_l\\scripts\\proby_9b.py lipkaya Light
    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_l\\scripts\\proby_9b.py lipkaya Dark
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import formy  # noqa: E402  (21-I copy: walk of the screens, measurement)
import kadry  # noqa: E402
import progon_10b as run10b  # noqa: E402

mgs = kadry.mgs
OUT = kadry.REPO_ROOT / "results" / "wave21_l" / "9b"
PORT = run10b.PORT
kadry.PORT = PORT
formy.kadry.PORT = PORT

HEADER_JS = """
() => {
  const header = document.querySelector('[data-testid="stHeader"]');
  const main = document.querySelector('[data-testid="stMain"]');
  const tabs = main.querySelector('[role="tablist"]');
  const block = document.querySelector('[data-testid="stMainBlockContainer"]');
  const h1 = [...main.querySelectorAll('h1')].map(h => ({text: h.innerText.trim(), id: h.id,
    shown: h.offsetParent !== null}));
  return {header_bottom: header ? header.getBoundingClientRect().bottom : null,
          tabs_top: tabs ? tabs.getBoundingClientRect().top : null,
          padding_top: block ? getComputedStyle(block).paddingTop : null, h1};
}
"""

# Ancestors of the first visible primary button up to stMain.
BUTTON_DOM_JS = """
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const shown = e => e.offsetParent !== null && e.getBoundingClientRect().height > 0;
  const all = [...main.querySelectorAll(
    'button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"]')]
    .filter(shown);
  return all.map(button => {
    const chain = [];
    for (let e = button.parentElement; e && e !== main; e = e.parentElement) {
      if (!e.dataset.testid && !e.className) continue;
      const key = [...e.classList].find(c => c.startsWith('st-key-'));
      const r = e.getBoundingClientRect();
      chain.push({testid: e.dataset.testid || null, key: key || null,
                  position: getComputedStyle(e).position,
                  height: Math.round(r.height)});
      if (chain.length > 14) break;
    }
    const b = button.getBoundingClientRect();
    return {text: button.innerText.trim(), testid: button.dataset.testid, disabled: button.disabled,
            top: Math.round(b.top), bottom: Math.round(b.bottom), chain};
  });
}
"""


def open_page(browser, theme: str):
    context = browser.new_context(viewport=dict(kadry.VIEWPORT), device_scale_factor=1,
                                  color_scheme="light", locale="ru-RU",
                                  timezone_id="Europe/Moscow")
    context.set_default_timeout(mgs.UI_TIMEOUT_MS)
    page = context.new_page()
    query = "?embed_options=dark_theme" if theme == "Dark" else ""
    page.goto(f"http://127.0.0.1:{PORT}/{query}", wait_until="domcontentloaded")
    page.get_by_role("tab", name="Расчёты", exact=True).wait_for(timeout=600_000)
    mgs.CALC_TIMEOUT_MS = 600_000
    mgs.wait_idle(page)
    page.wait_for_timeout(500)
    if kadry.current_theme(page) != theme:
        raise RuntimeError(f"not {theme}: {page.evaluate(kadry.APP_BG_JS)}")
    return context, page


def walk(page, extra=None) -> tuple[list[dict], dict]:
    """formy.run_base on ni: 21 screens, each measured at the top of the page."""

    original = formy.measure

    def measure(page_, path):
        data = original(page_, path)
        if data is not None and extra is not None:
            data.update(extra(page_))
        return data

    formy.measure = measure
    try:
        return formy.run_base(page, "ni", mgs.DB_NI)
    finally:
        formy.measure = original


def short(screens: list[dict]) -> list[dict]:
    rows = []
    for s in screens:
        rows.append({
            "screen": s["screen"],
            "first_element": (s["elements"][0]["testid"] + " " + s["elements"][0]["label"][:40])
            if s["elements"] else None,
            "first_top": s["elements"][0]["top"] if s["elements"] else None,
            "button": s["button"]["text"], "button_testid": s["button"]["testid"],
            "button_top": s["button"]["top"], "button_bottom": s["button"]["bottom"],
            "first_screen": s["first_screen"],
            **{k: s[k] for k in ("dom", "wrapper") if k in s},
        })
    return rows


def top_frame(page, path: list[str], name: str) -> str:
    for item in path:
        mgs.open_tab(page, item)
    page.mouse.move(5, 5)
    page.evaluate(formy.SCROLL_TOP_JS)
    page.wait_for_timeout(500)
    target = OUT / name
    page.screenshot(path=str(target))
    return target.name


def phase_kompakt(browser) -> dict:
    context, page = open_page(browser, "Light")
    result: dict = {"run": "53", "theme": "Light", "viewport": kadry.VIEWPORT}
    screens, sidebar = walk(page, extra=lambda p: {"dom": p.evaluate(BUTTON_DOM_JS)})
    result["sidebar"] = sidebar
    result["bez_stiley"] = short(screens)
    mgs.open_tab(page, "Расчёты")
    mgs.open_tab(page, "Одна температура")
    page.evaluate(formy.SCROLL_TOP_JS)
    result["header_before"] = page.evaluate(HEADER_JS)
    hide = (
        "/* 21-L 9B a): probe only, injected into the open page (not app/style.css).\n"
        "   The app title st.title (app/ThermoGar_app.py:7011) is hidden. */\n"
        '[data-testid="stMain"] [data-testid="stElementContainer"]:has(> [data-testid="stHeading"] h1) {\n'
        "    display: none;\n"
        "}\n"
    )
    handle = page.add_style_tag(content=hide)
    page.wait_for_timeout(300)
    search = []
    chosen = None
    for padding in range(0, 161, 2):
        css = hide + ('[data-testid="stMainBlockContainer"] {\n'
                      f"    padding-top: {padding}px;\n}}\n")
        handle.evaluate("(e, css) => { e.textContent = css; }", css)
        page.wait_for_timeout(120)
        page.evaluate(formy.SCROLL_TOP_JS)
        state = page.evaluate(HEADER_JS)
        search.append({"padding_px": padding, "tabs_top": state["tabs_top"],
                       "header_bottom": state["header_bottom"]})
        if chosen is None and state["tabs_top"] >= state["header_bottom"]:
            chosen = padding
            break
    result["padding_search"] = search
    result["chosen_padding_px"] = chosen
    css = hide + ('[data-testid="stMainBlockContainer"] {\n'
                  f"    padding-top: {chosen}px;\n}}\n")
    handle.evaluate("(e, css) => { e.textContent = css; }", css)
    (OUT / "kompakt.css").write_text(css, encoding="utf-8")
    result["css"] = css
    page.wait_for_timeout(300)
    result["header_after"] = page.evaluate(HEADER_JS)
    screens, _ = walk(page)
    result["kompakt"] = short(screens)
    result["frames"] = [
        top_frame(page, ["Расчёты", "Одна температура"], "kompakt_odna_temperatura_svet.png"),
        top_frame(page, ["Затвердевание"], "kompakt_zatverdevanie_svet.png"),
        top_frame(page, ["Диаграммы", "Бинарная T–X"], "kompakt_binarnaya_tx_svet.png"),
    ]
    context.close()
    return result


WRAPPER_JS = """
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const shown = e => e.offsetParent !== null && e.getBoundingClientRect().height > 0;
  return [...main.querySelectorAll(
    'button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"]')]
    .filter(shown).map(button => {
      let sticky = null;
      for (let e = button.parentElement; e && e !== main; e = e.parentElement) {
        if (getComputedStyle(e).position === 'sticky') { sticky = e; break; }
      }
      const b = button.getBoundingClientRect();
      const w = sticky ? sticky.getBoundingClientRect() : null;
      const form = !!button.closest('[data-testid="stForm"]');
      const column = !!button.closest('[data-testid="stColumn"]');
      return {text: button.innerText.trim(), testid: button.dataset.testid, form, column,
              sticky: !!sticky, sticky_testid: sticky ? sticky.dataset.testid : null,
              button_bottom: Math.round(b.bottom),
              wrapper: w ? {top: Math.round(w.top), bottom: Math.round(w.bottom),
                            bg: getComputedStyle(sticky).backgroundColor,
                            border_top: getComputedStyle(sticky).borderTopColor + ' ' +
                              getComputedStyle(sticky).borderTopWidth} : null};
    });
}
"""

RESULT_VIEW_JS = """
(buttonText) => {
  const main = document.querySelector('[data-testid="stMain"]');
  const shown = e => e.offsetParent !== null && e.getBoundingClientRect().height > 0;
  const button = [...main.querySelectorAll('button')].filter(shown)
    .find(b => b.innerText.trim() === buttonText);
  let wrapper = button;
  for (let e = button.parentElement; e && e !== main; e = e.parentElement) {
    if (getComputedStyle(e).position === 'sticky') { wrapper = e; break; }
  }
  const img = [...main.querySelectorAll('[data-testid="stImage"] img')].filter(shown)
    .find(i => button.compareDocumentPosition(i) & Node.DOCUMENT_POSITION_FOLLOWING);
  const w = wrapper.getBoundingClientRect();
  const r = img ? img.getBoundingClientRect() : null;
  const overlap = r ? Math.max(0, Math.min(w.bottom, r.bottom) - Math.max(w.top, r.top)) : null;
  return {viewport_h: window.innerHeight,
          wrapper: {top: Math.round(w.top), bottom: Math.round(w.bottom)},
          image: r ? {top: Math.round(r.top), bottom: Math.round(r.bottom)} : null,
          overlap_px: overlap === null ? null : Math.round(overlap),
          stuck_to_bottom: Math.abs(w.bottom - window.innerHeight) < 1.5};
}
"""


def phase_lipkaya(browser, theme: str) -> dict:
    slug = kadry.THEME_SLUG[theme]
    css = (OUT / "lipkaya.css").read_text(encoding="utf-8")
    context, page = open_page(browser, theme)
    result: dict = {"run": "54" if theme == "Light" else "55", "theme": theme, "css": css}
    page.add_style_tag(content=css)
    page.wait_for_timeout(300)
    if theme == "Light":
        screens, sidebar = walk(page, extra=lambda p: {"wrapper": p.evaluate(WRAPPER_JS)})
        result["sidebar"] = sidebar
        result["screens"] = short(screens)
        # Form and column buttons: all primary buttons of the two «Проекты и данные» screens.
        extra = {}
        for path in (["Проекты и данные", "Марки и составы"],
                     ["Проекты и данные", "Проекты и история"]):
            for item in path:
                mgs.open_tab(page, item)
            page.evaluate(formy.SCROLL_TOP_JS)
            page.wait_for_timeout(300)
            extra[" / ".join(path)] = page.evaluate(WRAPPER_JS)
        result["forms_columns"] = extra
    else:
        # Database ni as in formy.run_base: open the sidebar, choose, close it again.
        mgs.open_tab(page, "Расчёты")
        page.locator('[data-testid="stExpandSidebarButton"]').first.click()
        mgs.wait_idle(page)
        mgs.set_database(page, mgs.DB_NI)
        mgs.wait_idle(page)
        page.locator('[data-testid="stSidebar"]').hover()
        page.locator('[data-testid="stSidebarCollapseButton"] button').first.click()
        mgs.wait_idle(page)
        page.wait_for_timeout(500)
    frames = [
        top_frame(page, ["Диаграммы", "Бинарная T–X"], f"lipkaya_binarnaya_tx_nachalo_{slug}.png"),
        top_frame(page, ["Кинетика", "Выделения"], f"lipkaya_vydeleniya_nachalo_{slug}.png"),
    ]
    result["top_views"] = {}
    for path in (["Диаграммы", "Бинарная T–X"], ["Кинетика", "Выделения"]):
        for item in path:
            mgs.open_tab(page, item)
        page.evaluate(formy.SCROLL_TOP_JS)
        page.wait_for_timeout(300)
        result["top_views"][" / ".join(path)] = page.evaluate(WRAPPER_JS)
    for item in ("Диаграммы", "Бинарная T–X"):
        mgs.open_tab(page, item)
    button = "Построить диаграмму состояния"
    started = time.monotonic()
    mgs.main_area(page).get_by_role("button", name=button, exact=True).first.click()
    mgs.CALC_TIMEOUT_MS = run10b.LIMIT_S * 1000
    mgs.wait_idle(page)
    result["calc_s"] = round(time.monotonic() - started, 1)
    image = mgs.main_area(page).locator('[data-testid="stImage"] img:visible').first
    image.scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    result["after_calc"] = page.evaluate(RESULT_VIEW_JS, button)
    shot = OUT / f"lipkaya_binarnaya_tx_rezultat_{slug}.png"
    page.screenshot(path=str(shot))
    frames.append(shot.name)
    # The same result, the page scrolled back to the top: the button at the bottom edge again.
    page.evaluate(formy.SCROLL_TOP_JS)
    page.wait_for_timeout(400)
    result["after_calc_top"] = page.evaluate(RESULT_VIEW_JS, button)
    shot = OUT / f"lipkaya_binarnaya_tx_rezultat_nachalo_{slug}.png"
    page.screenshot(path=str(shot))
    frames.append(shot.name)
    result["frames"] = frames
    context.close()
    return result


def main() -> int:
    phase = sys.argv[1]
    theme = sys.argv[2] if len(sys.argv) > 2 else "Light"
    rid = "53" if phase == "kompakt" else ("54" if theme == "Light" else "55")
    OUT.mkdir(parents=True, exist_ok=True)
    run10b.LOGS.mkdir(parents=True, exist_ok=True)
    free = kadry.free_gib()
    print(f"[{rid}] {phase} {theme}: free {free:.2f} GiB", flush=True)
    if free < kadry.MIN_FREE_GIB:
        print("STOP: free memory below 3.0 GiB", file=sys.stderr)
        return 3
    if run10b.port_pids(PORT):
        print(f"STOP: port {PORT} busy", file=sys.stderr)
        return 2
    process, log, state = run10b.start_app(rid)
    print(f"  state {state}", flush=True)
    from playwright.sync_api import sync_playwright

    result = {}
    try:
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True)
            try:
                if phase == "kompakt":
                    result = phase_kompakt(browser)
                    name = "kompakt_ni.json"
                else:
                    result = phase_lipkaya(browser, theme)
                    name = f"lipkaya_{kadry.THEME_SLUG[theme]}.json"
                result["state_root"] = str(state)
                (OUT / name).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
            finally:
                browser.close()
    finally:
        print("  taskkill", run10b.stop_app(process, log), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
