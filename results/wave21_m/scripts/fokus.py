"""21-M, step 6 (decision 14): focus ring — walk by Tab, computed style.

The app must run on port 8640 (run_app.cmd of this folder). Window 1440x900,
database ni, light theme in a default session and dark with
``?embed_options=dark_theme`` (as kadry.py). Screens:

    «Расчёты → Одна температура», «Затвердевание»,
    «Кинетика → Диффузия и гомогенизация» (the view «Однофазная пара»),
    «Кинетика → Выделения»; extra — «Свойства → Покрытие физической базы»
    (secondary buttons).

On a screen the focus is put on the selected tab of the screen (the last
tab row), then Tab is pressed until the focus leaves the main area or
returns to an element already seen (at most 120 presses). For every focused
element: tag, role, data-testid of the element and of the nearest ancestor
with data-testid, key (st-key-…), label (up to 60 characters), computed
box-shadow and outline of the element and of the ancestors up to the
nearest data-testid wrapper (the ring of BaseWeb inputs lies on a wrapper).

A ring is «semi-transparent primary» when a box-shadow or outline colour of
the element or a wrapper is rgba(31, 96, 193, a<1) (light) or
rgba(92, 151, 232, a<1) (dark), or the same colours with alpha.

Output: results/wave21_m/fokus/fokus_<theme>.json and a summary table
fokus_svodka.csv (UTF-8 with BOM, «;»): screen; element; testid; key; label;
box-shadow; outline; ring class.

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_m\\scripts\\fokus.py [stage]

``stage`` is only a suffix of the output files (do / posle).
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kadry  # noqa: E402  (21-M copy: port 8640, state tg21m_state)

mgs = kadry.mgs
OUT = kadry.REPO_ROOT / "results" / "wave21_m" / "fokus"
MAX_TABS = 120

SCREENS = [
    ("Расчёты / Одна температура", ["Расчёты", "Одна температура"], None),
    ("Затвердевание", ["Затвердевание"], None),
    ("Кинетика / Диффузия и гомогенизация / Однофазная пара", ["Кинетика", "Диффузия и гомогенизация"], None),
    ("Кинетика / Выделения", ["Кинетика", "Выделения"], None),
    # Extra, not in the task list: secondary buttons (st.button without type).
    ("Свойства / Покрытие физической базы", ["Свойства", "Покрытие физической базы"], None),
]

ACTIVE_JS = """
() => {
  const el = document.activeElement;
  if (!el || el === document.body) return null;
  const main = document.querySelector('[data-testid="stMain"]');
  const cut = s => (s || '').replace(/\\s+/g, ' ').trim().slice(0, 60);
  const style = e => {
    const s = getComputedStyle(e);
    return {box_shadow: s.boxShadow,
            outline: `${s.outlineStyle} ${s.outlineWidth} ${s.outlineColor}`,
            outline_offset: s.outlineOffset,
            border: `${s.borderTopStyle} ${s.borderTopWidth} ${s.borderTopColor}`};
  };
  const chain = [];
  let wrapper = null;
  for (let e = el, depth = 0; e && depth < 6; e = e.parentElement, depth++) {
    chain.push({tag: e.tagName.toLowerCase(), testid: e.dataset ? e.dataset.testid || null : null,
                cls: (e.className && e.className.baseVal === undefined ? String(e.className) : '').slice(0, 60),
                ...style(e)});
    if (depth > 0 && e.dataset && e.dataset.testid) { wrapper = e.dataset.testid; break; }
  }
  let key = null;
  for (let e = el; e && e !== main; e = e.parentElement) {
    const k = e.classList && [...e.classList].find(c => c.startsWith('st-key-'));
    if (k) { key = k; break; }
  }
  let label = el.getAttribute('aria-label') || '';
  const container = el.closest('[data-testid="stElementContainer"]');
  if (!label && container) {
    const l = container.querySelector('[data-testid="stWidgetLabel"]');
    if (l) label = l.innerText;
  }
  if (!label) label = el.innerText || el.value || '';
  const r = el.getBoundingClientRect();
  return {in_main: main.contains(el), tag: el.tagName.toLowerCase(), role: el.getAttribute('role'),
          type: el.getAttribute('type'), testid: el.dataset.testid || null, wrapper, key,
          label: cut(label), focus_visible: el.matches(':focus-visible'),
          box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
          chain,
          uid: (el.id || '') + '|' + (key || '') + '|' + cut(label) + '|' + el.tagName + '|' +
               Math.round(r.x) + ',' + Math.round(r.y + window.scrollY)};
}
"""

PRIMARY = {"Light": (31, 96, 193), "Dark": (92, 151, 232)}
RGBA = re.compile(r"rgba?\((\d+), (\d+), (\d+)(?:, ([\d.]+))?\)")


def ring_class(entry: dict, theme: str) -> str:
    """Semi-transparent primary / solid primary / other / none."""

    target = PRIMARY[theme]
    found = []
    for item in entry["chain"]:
        for prop in ("box_shadow", "outline"):
            value = item[prop]
            if prop == "outline" and value.startswith("none"):
                continue
            if prop == "box_shadow" and value == "none":
                continue
            for match in RGBA.finditer(value):
                rgb = tuple(int(match.group(i)) for i in (1, 2, 3))
                alpha = float(match.group(4)) if match.group(4) is not None else 1.0
                if alpha == 0:
                    continue
                if rgb == target:
                    found.append("primary_poluprozrachnyi" if alpha < 1 else "primary_sploshnoi")
                else:
                    found.append("drugoi")
    if not found:
        return "net"
    for kind in ("primary_poluprozrachnyi", "primary_sploshnoi", "drugoi"):
        if kind in found:
            return kind
    return found[0]


def open_screen(page, path: list[str]) -> None:
    for name in path:
        mgs.open_tab(page, name)
    mgs.wait_idle(page)
    page.mouse.move(5, 5)


def walk(page, screen: str, path: list[str], theme: str) -> list[dict]:
    open_screen(page, path)
    tab = page.get_by_role("tab", name=path[-1], exact=True)
    tab.focus()
    entries = []
    seen = set()
    # The tab of the screen itself, reached by keyboard: Shift+Tab, then Tab.
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    page.wait_for_timeout(120)
    first = page.evaluate(ACTIVE_JS)
    if first is not None and first["in_main"]:
        first.update(step=0, screen=screen, ring=ring_class(first, theme))
        entries.append(first)
        seen.add(first["uid"])
    for step in range(MAX_TABS):
        page.keyboard.press("Tab")
        page.wait_for_timeout(120)
        entry = page.evaluate(ACTIVE_JS)
        if entry is None or not entry["in_main"]:
            break
        if entry["uid"] in seen:
            break
        seen.add(entry["uid"])
        entry["step"] = step + 1
        entry["screen"] = screen
        entry["ring"] = ring_class(entry, theme)
        entries.append(entry)
    # Leave no focus behind.
    page.evaluate("() => document.activeElement && document.activeElement.blur()")
    return entries


def main() -> int:
    stage = sys.argv[1] if len(sys.argv) > 1 else "posle"
    free = kadry.free_gib()
    print(f"free memory {free:.2f} GiB", flush=True)
    if free < kadry.MIN_FREE_GIB:
        print(f"STOP: free memory below {kadry.MIN_FREE_GIB} GiB", file=sys.stderr)
        return 3
    if not mgs.app_is_ready(kadry.PORT):
        print(f"STOP: no app on port {kadry.PORT}", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        try:
            for theme in kadry.THEMES:
                context = browser.new_context(
                    viewport=dict(kadry.VIEWPORT), device_scale_factor=1,
                    color_scheme="light", locale="ru-RU", timezone_id="Europe/Moscow",
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
                result = []
                for screen, path, _view in SCREENS:
                    entries = walk(page, screen, path, theme)
                    print(f"[{theme}] {screen}: {len(entries)} focus stops", flush=True)
                    result.extend(entries)
                (OUT / f"fokus_{stage}_{kadry.THEME_SLUG[theme]}.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                for entry in result:
                    own = entry["chain"][0]
                    ringed = next(
                        (item for item in entry["chain"]
                         if item["box_shadow"] != "none" or not item["outline"].startswith("none")),
                        own,
                    )
                    rows.append([
                        theme, entry["screen"], entry["step"], entry["tag"], entry["role"] or "",
                        entry["testid"] or entry["wrapper"] or "", entry["key"] or "", entry["label"],
                        ringed["tag"] + (f"[{ringed['testid']}]" if ringed["testid"] else ""),
                        ringed["box_shadow"], ringed["outline"], entry["ring"],
                    ])
                context.close()
        finally:
            browser.close()
    with (OUT / f"fokus_{stage}_svodka.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["тема", "экран", "шаг Tab", "тег", "role", "testid", "key", "подпись",
                         "элемент с кольцом", "box-shadow", "outline", "класс кольца"])
        writer.writerows(rows)
    print(f"rows {len(rows)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
