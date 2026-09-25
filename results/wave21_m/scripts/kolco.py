"""21-M, step 6/8 (decision 14): focus ring by pixels — primary button and switch.

The app must run on port 8640 (run_app.cmd of this folder). Window 1440x900,
database ni; light theme in a default session, dark with
``?embed_options=dark_theme``. Screen «Кинетика → Диффузия и гомогенизация»:

    knopka          «Рассчитать однофазную диффузию» (primary, in the sticky row)
    pereklyuchatel  selected option «Однофазная пара» of the switch

Per control: a focus frame (focus() on the focusable element before the
control, then Tab until the control has the focus; mouse away) and a rest
frame with the same clip after blur(). The ring is measured as in 21-I (pereklyuchatel.ring): pixels
around the control, outside its box up to 6 px, that differ from the rest
frame; the most frequent of them and its contrast to the window pixel.
Computed box-shadow and outline are stored next to it.

Output: results/wave21_m/kadry/kolco_<control>_<state>_<theme>.png and rows
of results/wave21_m/kolco.json; the table zamery.csv is built by zamery.py.

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_m\\scripts\\kolco.py [suffix]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kadry  # noqa: E402  (21-M copy: port 8640, state tg21m_state)
import pereklyuchatel as px  # noqa: E402  (21-I pixel functions: ring, clip_of, rest)

mgs = kadry.mgs
KADRY = kadry.REPO_ROOT / "results" / "wave21_m" / "kadry"
OUT_JSON = kadry.REPO_ROOT / "results" / "wave21_m" / "kolco.json"

FOCUS_PREVIOUS_JS = """
el => {
  const all = [...document.querySelectorAll(
    'a[href], button, input, textarea, select, [tabindex]:not([tabindex="-1"])'
  )].filter(e => !e.disabled && e.offsetParent !== null && e.tabIndex >= 0);
  const index = all.indexOf(el);
  for (let i = index - 1; i >= 0; i--) {
    all[i].focus();
    if (document.activeElement === all[i]) return true;
  }
  return false;
}
"""


def controls(page):
    main = mgs.main_area(page)
    return {
        "knopka": main.get_by_role("button", name="Рассчитать однофазную диффузию", exact=True),
        "pereklyuchatel": page.get_by_role("radiogroup", name="Диффузия и гомогенизация", exact=True)
        .get_by_role("radio", name="Однофазная пара", exact=True),
    }


def focus_by_tab(page, target) -> None:
    handle = target.element_handle()
    if not page.evaluate(FOCUS_PREVIOUS_JS, handle):
        raise RuntimeError("no focusable element before the control")
    for _ in range(12):
        page.keyboard.press("Tab")
        page.wait_for_timeout(150)
        if page.evaluate("el => document.activeElement === el", handle):
            return
    raise RuntimeError("Tab did not reach the control")


def shoot(page, target, name: str) -> tuple[Path, dict, dict, dict]:
    box = target.bounding_box()
    clip = px.clip_of(box)
    # A clip below the window makes Playwright enlarge the viewport, and the
    # sticky row then moves: the clip is cut at the bottom edge of the window.
    clip["height"] = min(clip["height"], kadry.VIEWPORT["height"] - clip["y"])
    path = KADRY / f"{name}.png"
    page.screenshot(path=str(path), clip=clip)
    style = target.evaluate(px.STYLE_JS)
    return path, box, clip, style


def main() -> int:
    suffix = sys.argv[1] if len(sys.argv) > 1 else ""
    if kadry.free_gib() < kadry.MIN_FREE_GIB:
        print("STOP: free memory below 3 GiB", file=sys.stderr)
        return 3
    KADRY.mkdir(parents=True, exist_ok=True)
    rows = []
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        try:
            for theme in kadry.THEMES:
                slug = kadry.THEME_SLUG[theme]
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
                if kadry.current_theme(page) != theme:
                    raise RuntimeError(f"theme {kadry.current_theme(page)} != {theme}")
                mgs.open_tab(page, "Кинетика")
                mgs.open_tab(page, "Диффузия и гомогенизация")
                mgs.wait_idle(page)
                for name, target in controls(page).items():
                    target.scroll_into_view_if_needed()
                    px.rest(page)
                    # Tab may scroll the page: the focus frame first, then the
                    # focus is removed (no scrolling) and the rest frame is taken
                    # with the same clip.
                    focus_by_tab(page, target)
                    page.mouse.move(5, 5)
                    page.wait_for_timeout(300)
                    focus_path, box, clip, focus_style = shoot(page, target, f"kolco_{name}_fokus_{slug}{suffix}")
                    page.evaluate("() => document.activeElement && document.activeElement.blur()")
                    page.wait_for_timeout(400)
                    rest_path = KADRY / f"kolco_{name}_pokoi_{slug}{suffix}.png"
                    page.screenshot(path=str(rest_path), clip=clip)
                    measured = px.ring(focus_path, rest_path, box, clip)
                    row = {
                        "theme": theme, "control": name,
                        "frames": [rest_path.name, focus_path.name],
                        "focus_visible": focus_style["focus_visible"],
                        "box_shadow": focus_style["box_shadow"],
                        "outline": focus_style["outline"],
                        **measured,
                    }
                    rows.append(row)
                    print(f"[{theme}] {name}: ring {row.get('ring_px')} to window "
                          f"{row.get('window_px')} {row.get('ring_to_window')}:1, "
                          f"box-shadow {row['box_shadow']}", flush=True)
                    px.rest(page)
                context.close()
        finally:
            browser.close()
    OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bad = [row for row in rows if not row.get("ring_to_window") or row["ring_to_window"] < 3.0]
    return 4 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
