"""21-M copy (port 8640, output results/wave21_m/formy). 21-I, step 4: long forms for 9B — where the primary button stands.

The app must run on port 8638 (run_app.cmd of this folder). Light theme,
window 1440x900, the sidebar as it opens, no calculations. For every database
(ni, al, fe) every screen is opened — top tab / subtab / nested tab / option
of a switch (st.segmented_control, role="radio") — and scrolled to the top.
A screen counts when it shows a primary button (data-testid
stBaseButton-primary or stBaseButton-primaryFormSubmit).

For such a screen, every element of the main area of the screen, in page
order, from the top of the active panel to the first primary button
inclusive: data-testid, key (class st-key-…), label (up to 80 characters), for
an expander — open or closed, top and bottom in px from the top of the window
(the page scrolled to the top). Elements inside a closed expander are not
shown and not listed. The button: text, top, bottom; «on the first screen» —
bottom of the button ≤ 900.

Output: results/wave21_i/formy/formy_<base>.json.

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_i\\scripts\\formy.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kadry  # noqa: E402  (21-I copy: port 8638, state tg21i_state)

mgs = kadry.mgs
OUT = kadry.REPO_ROOT / "results" / "wave21_m" / "formy"
BASES = {"ni": mgs.DB_NI, "al": mgs.DB_AL, "fe": mgs.DB_FE}
FIRST_SCREEN = kadry.VIEWPORT["height"]

PRIMARY = ('button[data-testid="stBaseButton-primary"], '
           'button[data-testid="stBaseButton-primaryFormSubmit"]')

# Scroll every scrolled container of the page back to the top.
SCROLL_TOP_JS = """
() => {
  window.scrollTo(0, 0);
  for (const el of document.querySelectorAll('*')) {
    if (el.scrollTop) el.scrollTop = 0;
  }
  return true;
}
"""

ELEMENTS_JS = """
(primarySelector) => {
  const main = document.querySelector('[data-testid="stMain"]');
  const shown = e => e.offsetParent !== null && e.getBoundingClientRect().height > 0;
  const panels = [...main.querySelectorAll('[role="tabpanel"]')].filter(shown);
  const inner = panels.filter(p => !panels.some(q => q !== p && p.contains(q)));
  const panel = inner.length ? inner[0] : main;
  // Content of a closed expander keeps its box in 1.62 but is clipped: skip it.
  const inClosed = el => {
    for (let e = el.parentElement; e && e !== panel; e = e.parentElement) {
      if (e.dataset && e.dataset.testid === 'stExpander') {
        const d = e.querySelector('details');
        if (d && !d.open) return true;
      }
    }
    return false;
  };
  const buttons = [...panel.querySelectorAll(primarySelector)].filter(shown)
    .filter(b => !inClosed(b));
  if (!buttons.length) return {buttons: [], elements: []};
  const first = buttons[0];
  const cut = s => (s || '').replace(/\\s+/g, ' ').trim().slice(0, 80);
  const keyOf = el => {
    for (let e = el; e && e !== panel; e = e.parentElement) {
      const k = [...e.classList].find(c => c.startsWith('st-key-'));
      if (k) return k;
    }
    return null;
  };
  const labelOf = (el, testid) => {
    if (testid === 'stExpander') {
      const s = el.querySelector('summary');
      return cut(s ? s.innerText.replace('keyboard_arrow_down', '').replace('keyboard_arrow_right', '') : '');
    }
    const l = el.querySelector('[data-testid="stWidgetLabel"]');
    if (l && cut(l.innerText)) return cut(l.innerText);
    const g = el.querySelector('[role="radiogroup"][aria-label], [role="tablist"]');
    if (g && g.getAttribute('aria-label')) return cut(g.getAttribute('aria-label'));
    if (testid === 'stDataFrame' || testid === 'stImage' || testid === 'stPlotlyChart') return '';
    return cut(el.innerText);
  };
  const expanderOf = el => {
    const x = el.parentElement && el.parentElement.closest('[data-testid="stExpander"]');
    return x && panel.contains(x) ? labelOf(x, 'stExpander') : null;
  };
  const items = [...panel.querySelectorAll(
    '[data-testid="stElementContainer"], [data-testid="stExpander"], [data-testid="stForm"], ' +
    '[data-testid="stTabs"]'
  )].filter(shown);
  const out = [];
  for (const el of items) {
    if (inClosed(el)) continue;
    const position = el.compareDocumentPosition(first);
    const containsButton = el.contains(first);
    const before = (position & Node.DOCUMENT_POSITION_FOLLOWING) || containsButton;
    if (!before) continue;
    let testid = el.dataset.testid;
    let target = el;
    if (testid === 'stElementContainer') {
      const child = el.querySelector('[data-testid]');
      if (child) { testid = child.dataset.testid; target = child; }
      // A container with other elements inside is listed by its children.
      if (testid === 'stVerticalBlock' || testid === 'stHorizontalBlock' ||
          testid === 'stLayoutWrapper' || testid === 'stColumn') continue;
    }
    if (testid === 'stTabs') continue;
    const r = el.getBoundingClientRect();
    const entry = {testid, key: keyOf(el), label: labelOf(target, testid),
                   top: Math.round(r.top), bottom: Math.round(r.bottom)};
    if (testid === 'stExpander') entry.open = !!el.querySelector('details[open]');
    const inside = expanderOf(el);
    if (inside) entry.in_expander = inside;
    if (el.closest('[data-testid="stForm"]') && testid !== 'stForm') entry.in_form = true;
    if (containsButton && testid !== 'stExpander' && testid !== 'stForm') entry.primary = true;
    out.push(entry);
  }
  const box = first.getBoundingClientRect();
  return {
    buttons: buttons.map(b => ({text: cut(b.innerText), testid: b.dataset.testid,
                                disabled: b.disabled,
                                top: Math.round(b.getBoundingClientRect().top),
                                bottom: Math.round(b.getBoundingClientRect().bottom)})),
    button: {text: cut(first.innerText), testid: first.dataset.testid, disabled: first.disabled,
             top: Math.round(box.top), bottom: Math.round(box.bottom)},
    elements: out,
  };
}
"""

# Tabs of the innermost visible tab list that is not a top or a known subtab row.
NESTED_TABS_JS = """
(known) => {
  const main = document.querySelector('[data-testid="stMain"]');
  const shown = e => e.offsetParent !== null && e.getBoundingClientRect().height > 0;
  const lists = [...main.querySelectorAll('[role="tablist"]')].filter(shown);
  const names = [];
  for (const list of lists) {
    const tabs = [...list.querySelectorAll('[role="tab"]')].map(t => t.innerText.trim());
    if (tabs.some(t => known.includes(t))) continue;
    names.push(tabs);
  }
  return names;
}
"""

SWITCHES_JS = """
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const shown = e => e.offsetParent !== null && e.getBoundingClientRect().height > 0;
  return [...main.querySelectorAll('[role="radiogroup"][aria-label]')].filter(shown)
    .filter(g => g.querySelector('button[data-variant="segmented_control"]'))
    .map(g => ({label: g.getAttribute('aria-label'),
                options: [...g.querySelectorAll('[role="radio"]')].map(e => e.innerText.trim())}));
}
"""


def measure(page, path: list[str]) -> dict | None:
    page.mouse.move(5, 5)
    page.evaluate(SCROLL_TOP_JS)
    page.wait_for_timeout(300)
    data = page.evaluate(ELEMENTS_JS, PRIMARY)
    if not data["buttons"]:
        print(f"  {' / '.join(path)}: no primary button", flush=True)
        return None
    data["screen"] = " / ".join(path)
    data["path"] = path
    data["first_screen"] = data["button"]["bottom"] <= FIRST_SCREEN
    print(f"  {data['screen']}: «{data['button']['text']}» {data['button']['top']}–"
          f"{data['button']['bottom']} first screen {data['first_screen']}, "
          f"{len(data['elements'])} elements", flush=True)
    return data


def open_view(page, group: str, option: str) -> None:
    page.get_by_role("radiogroup", name=group, exact=True).get_by_role(
        "radio", name=option, exact=True
    ).click()
    mgs.wait_idle(page)


def screens_of(page, path: list[str], known: list[str], out: list) -> None:
    """Measure the open screen; go down into nested tabs and switches."""

    # A switch already walked (its options are in ``known``) is not walked again.
    switches = [
        switch for switch in page.evaluate(SWITCHES_JS)
        if not set(switch["options"]) <= set(known)
    ]
    nested = page.evaluate(NESTED_TABS_JS, known)
    if switches:
        switch = switches[0]
        for option in switch["options"]:
            open_view(page, switch["label"], option)
            screens_of(page, path + [option], known + switch["options"], out)
        open_view(page, switch["label"], switch["options"][0])
        return
    if nested:
        tabs = nested[0]
        for tab in tabs:
            mgs.open_tab(page, tab)
            screens_of(page, path + [tab], known + tabs, out)
        mgs.open_tab(page, tabs[0])
        return
    data = measure(page, path)
    if data:
        out.append(data)


SIDEBAR_JS = """
() => {
  const s = document.querySelector('[data-testid="stSidebar"]');
  if (!s) return {present: false};
  const r = s.getBoundingClientRect();
  return {present: true, expanded: s.getAttribute('aria-expanded'),
          right: Math.round(r.right), width: Math.round(r.width)};
}
"""


def sidebar_open(page) -> bool:
    expand = page.locator('[data-testid="stExpandSidebarButton"]')
    return not (expand.count() and expand.first.is_visible())


def run_base(page, base: str, label: str) -> tuple[list[dict], dict]:
    print(f"[{base}] {label}", flush=True)
    mgs.open_tab(page, "Расчёты")
    initial = {"open": sidebar_open(page), **page.evaluate(SIDEBAR_JS)}
    # The database is chosen in the sidebar; afterwards the sidebar goes back
    # to the state the page opened with.
    if not initial["open"]:
        page.locator('[data-testid="stExpandSidebarButton"]').first.click()
        mgs.wait_idle(page)
    mgs.set_database(page, label)
    mgs.wait_idle(page)
    if not initial["open"]:
        page.locator('[data-testid="stSidebar"]').hover()
        page.locator('[data-testid="stSidebarCollapseButton"] button').first.click()
        mgs.wait_idle(page)
        page.wait_for_timeout(500)
    initial["after_database"] = {"open": sidebar_open(page), **page.evaluate(SIDEBAR_JS)}
    print(f"  sidebar {initial}", flush=True)
    screens: list[dict] = []
    top_names = list(kadry.TOP_TABS)
    for top, subtabs in kadry.TOP_TABS.items():
        mgs.open_tab(page, top)
        if not subtabs:
            screens_of(page, [top], top_names, screens)
            continue
        for subtab in subtabs:
            mgs.open_tab(page, subtab)
            screens_of(page, [top, subtab], top_names + subtabs, screens)
    return screens, initial


def main() -> int:
    free = kadry.free_gib()
    print(f"free memory {free:.2f} GiB", flush=True)
    if free < kadry.MIN_FREE_GIB:
        print(f"STOP: free memory below {kadry.MIN_FREE_GIB} GiB", file=sys.stderr)
        return 3
    if not mgs.app_is_ready(kadry.PORT):
        print(f"STOP: no app on port {kadry.PORT}", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        try:
            for base, label in BASES.items():
                context = browser.new_context(
                    viewport=dict(kadry.VIEWPORT), device_scale_factor=1, color_scheme="light",
                    locale="ru-RU", timezone_id="Europe/Moscow",
                )
                context.set_default_timeout(mgs.UI_TIMEOUT_MS)
                page = context.new_page()
                page.goto(f"http://127.0.0.1:{kadry.PORT}/", wait_until="domcontentloaded")
                page.get_by_role("tab", name="Расчёты", exact=True).wait_for(
                    timeout=mgs.CALC_TIMEOUT_MS
                )
                mgs.wait_idle(page)
                page.wait_for_timeout(500)
                if kadry.current_theme(page) != "Light":
                    raise RuntimeError(f"not light: {page.evaluate(kadry.APP_BG_JS)}")
                screens, sidebar = run_base(page, base, label)
                payload = {
                    "base": base, "database": label, "viewport": kadry.VIEWPORT,
                    "theme": "Light", "first_screen_px": FIRST_SCREEN, "sidebar": sidebar,
                    "screens": screens,
                }
                (OUT / f"formy_{base}.json").write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                page.screenshot(path=str(OUT / f"_last_state_{base}.png"))
                context.close()
        finally:
            browser.close()
    print(f"done in {time.monotonic() - started:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
