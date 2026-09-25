"""21-I, step 3b: the switch (st.segmented_control) by pixels, both themes.

Made after knopka.py of 21-Z (the same pixel method). The app must run on
port 8638 (run_app.cmd of this folder). One run takes both themes: light in a
default session, dark with ``?embed_options=dark_theme`` (as kadry.py).

Switch: «Кинетика / Диффузия и гомогенизация», radiogroup
«Диффузия и гомогенизация»; selected option «Однофазная пара» (the default),
not selected option «Многофазная гомогенизация». States:

    1 nevybrannyi            not selected, rest: mouse away, no focus
    2 nevybrannyi_navedenie  not selected, mouse over it
    3 vybrannyi              selected, rest
    4 vybrannyi_navedenie    selected, mouse over it
    5 vybrannyi_fokus        selected, keyboard focus: focus() on the focusable
                             element before it, then Tab until it has the focus

Per frame: background = the most frequent colour inside the option (border
excluded), text = the pixel inside with the largest contrast to that
background, contrast text / background. Window = pixel of the page next to the
control. Border of the selected option: the pixel of its top edge line with
the largest contrast to the window; its contrast to the window. Focus ring:
pixels around the option (outside its box, up to 6 px) that differ from the
rest frame; the most frequent of them, its contrast to the window. The
computed style is stored next to it. Text below 4.5:1 in any state: exit 4
(STOP of the task).

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_i\\scripts\\pereklyuchatel.py
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kadry  # noqa: E402  (21-I copy: port 8638, state tg21i_state)

mgs = kadry.mgs
OUT = kadry.REPO_ROOT / "results" / "wave21_i" / "pereklyuchatel"
PAD = 24
RING = 6
GROUP = "Диффузия и гомогенизация"
SELECTED = "Однофазная пара"
OTHER = "Многофазная гомогенизация"
NORM = 4.5

STYLE_JS = """
el => {
  const s = getComputedStyle(el);
  const p = el.querySelector('p') || el;
  return {bg: s.backgroundColor, border: s.borderTopColor, color: getComputedStyle(p).color,
          outline: `${s.outlineStyle} ${s.outlineWidth} ${s.outlineColor}`,
          outline_offset: s.outlineOffset, box_shadow: s.boxShadow,
          testid: el.dataset.testid, kind: el.getAttribute('kind'),
          role: el.getAttribute('role'), checked: el.getAttribute('aria-checked'),
          focus_visible: el.matches(':focus-visible'), hover: el.matches(':hover'),
          text: el.innerText.trim()};
}
"""

FOCUS_PREVIOUS_JS = """
el => {
  const all = [...document.querySelectorAll(
    'a[href], button, input, textarea, select, [tabindex]:not([tabindex="-1"])'
  )].filter(e => !e.disabled && e.offsetParent !== null && e.tabIndex >= 0);
  let index = all.indexOf(el);
  if (index < 0) {
    const group = el.closest('[role="radiogroup"]');
    index = all.findIndex(e => group.contains(e));
  }
  for (let i = index - 1; i >= 0; i--) {
    all[i].focus();
    if (document.activeElement === all[i]) return all[i].outerHTML.slice(0, 120);
  }
  return false;
}
"""


def luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def hex_of(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def rest(page) -> None:
    page.mouse.move(5, 5)
    page.evaluate("() => document.activeElement && document.activeElement.blur()")
    page.wait_for_timeout(400)


def clip_of(box: dict) -> dict:
    return {
        "x": max(0, box["x"] - PAD),
        "y": max(0, box["y"] - PAD),
        "width": box["width"] + 2 * PAD,
        "height": box["height"] + 2 * PAD,
    }


def load(path: Path):
    from PIL import Image

    with Image.open(path) as image:
        return image.convert("RGB")


def measure(path: Path, box: dict, clip: dict) -> dict:
    rgb = load(path)
    left = round(box["x"] - clip["x"])
    top = round(box["y"] - clip["y"])
    right = round(box["x"] - clip["x"] + box["width"])
    bottom = round(box["y"] - clip["y"] + box["height"])
    inner = list(rgb.crop((left + 3, top + 3, right - 3, bottom - 3)).get_flattened_data())
    background = Counter(inner).most_common(1)[0][0]
    text = max(set(inner), key=lambda value: contrast(value, background))
    window = rgb.getpixel((2, 2))
    edge = [rgb.getpixel((x, top)) for x in range(left + 8, right - 8)]
    edge += [rgb.getpixel((x, top + 1)) for x in range(left + 8, right - 8)]
    border = max(set(edge), key=lambda value: contrast(value, window))
    return {
        "bg_px": hex_of(background),
        "text_px": hex_of(text),
        "contrast_px": round(contrast(text, background), 2),
        "window_px": hex_of(window),
        "border_px": hex_of(border),
        "border_to_window": round(contrast(border, window), 2),
    }


def ring(path: Path, rest_path: Path, box: dict, clip: dict) -> dict:
    now, before = load(path), load(rest_path)
    left = round(box["x"] - clip["x"])
    top = round(box["y"] - clip["y"])
    right = round(box["x"] - clip["x"] + box["width"])
    bottom = round(box["y"] - clip["y"] + box["height"])
    changed = []
    for x in range(left - RING, right + RING):
        for y in list(range(top - RING, top)) + list(range(bottom, bottom + RING)):
            if now.getpixel((x, y)) != before.getpixel((x, y)):
                changed.append(now.getpixel((x, y)))
    for y in range(top - RING, bottom + RING):
        for x in list(range(left - RING, left)) + list(range(right, right + RING)):
            if now.getpixel((x, y)) != before.getpixel((x, y)):
                changed.append(now.getpixel((x, y)))
    window = now.getpixel((2, 2))
    if not changed:
        return {"ring_px": None, "ring_pixels": 0, "window_px": hex_of(window)}
    common = Counter(changed).most_common(3)
    colour = common[0][0]
    strongest = max(set(changed), key=lambda value: contrast(value, window))
    return {
        "ring_px": hex_of(colour),
        "ring_to_window": round(contrast(colour, window), 2),
        "ring_strongest_px": hex_of(strongest),
        "ring_strongest_to_window": round(contrast(strongest, window), 2),
        "ring_pixels": len(changed),
        "ring_top3": [[hex_of(c), n] for c, n in common],
        "window_px": hex_of(window),
    }


def shoot(page, option, stem: str, record: list, what: str, theme: str) -> dict:
    option.scroll_into_view_if_needed()
    page.wait_for_timeout(250)
    box = option.bounding_box()
    clip = clip_of(box)
    path = OUT / f"{stem}.png"
    page.screenshot(path=str(path), clip=clip)
    style = option.evaluate(STYLE_JS)
    entry = {"file": path.name, "theme": theme, "what": what, **style,
             **measure(path, box, clip), "_box": box, "_clip": clip}
    record.append(entry)
    print(f"  {stem}: bg {entry['bg_px']} text {entry['text_px']} {entry['contrast_px']}:1; "
          f"border {entry['border_px']} to window {entry['window_px']} {entry['border_to_window']}:1 "
          f"(css bg {style['bg']}, color {style['color']}, border {style['border']}, "
          f"hover={style['hover']} focus-visible={style['focus_visible']})", flush=True)
    return entry


def run_theme(browser, theme: str, record: list) -> None:
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
        raise RuntimeError(f"Session did not open in {theme}: {page.evaluate(kadry.APP_BG_JS)}")
    slug = kadry.THEME_SLUG[theme]
    mgs.open_tab(page, "Кинетика")
    mgs.open_tab(page, "Диффузия и гомогенизация")
    group = page.get_by_role("radiogroup", name=GROUP, exact=True)
    selected = group.get_by_role("radio", name=SELECTED, exact=True)
    other = group.get_by_role("radio", name=OTHER, exact=True)
    if selected.get_attribute("aria-checked") != "true":
        raise RuntimeError(f"«{SELECTED}» is not selected")
    rest(page)
    shoot(page, other, f"p1_nevybrannyi_{slug}", record,
          f"«{OTHER}»: не выбран, покой", theme)
    other.hover()
    page.wait_for_timeout(400)
    shoot(page, other, f"p2_nevybrannyi_navedenie_{slug}", record,
          f"«{OTHER}»: не выбран, наведение", theme)
    rest(page)
    rest_entry = shoot(page, selected, f"p3_vybrannyi_{slug}", record,
                       f"«{SELECTED}»: выбран, покой", theme)
    selected.hover()
    page.wait_for_timeout(400)
    shoot(page, selected, f"p4_vybrannyi_navedenie_{slug}", record,
          f"«{SELECTED}»: выбран, наведение", theme)
    rest(page)
    previous = selected.evaluate(FOCUS_PREVIOUS_JS)
    if not previous:
        raise RuntimeError("no focusable element before the switch")
    print(f"    Tab from: {previous}", flush=True)
    for presses in range(1, 31):
        page.keyboard.press("Tab")
        page.wait_for_timeout(150)
        if selected.evaluate("el => document.activeElement === el"):
            break
    else:
        raise RuntimeError("Tab did not reach the selected option")
    print(f"    Tab pressed {presses} time(s)", flush=True)
    page.mouse.move(5, 5)
    page.wait_for_timeout(300)
    focus_entry = shoot(page, selected, f"p5_vybrannyi_fokus_{slug}", record,
                        f"«{SELECTED}»: выбран, фокус с клавиатуры (Tab)", theme)
    focus_entry.update(ring(OUT / focus_entry["file"], OUT / rest_entry["file"],
                            focus_entry["_box"], focus_entry["_clip"]))
    print(f"    ring {focus_entry.get('ring_px')} to window {focus_entry.get('ring_to_window')}:1, "
          f"strongest {focus_entry.get('ring_strongest_px')} "
          f"{focus_entry.get('ring_strongest_to_window')}:1, pixels {focus_entry['ring_pixels']}; "
          f"css outline {focus_entry['outline']} offset {focus_entry['outline_offset']}, "
          f"box-shadow {focus_entry['box_shadow']}", flush=True)
    rest(page)
    # Wider frame: the whole switch at rest.
    group.scroll_into_view_if_needed()
    box = group.bounding_box()
    page.screenshot(path=str(OUT / f"p0_pereklyuchatel_{slug}.png"), clip=clip_of(box))
    context.close()


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
    record: list[dict] = []
    started = time.monotonic()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        try:
            for theme in kadry.THEMES:
                run_theme(browser, theme, record)
        finally:
            for entry in record:
                entry.pop("_box", None)
                entry.pop("_clip", None)
            (OUT / "pereklyuchatel.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            browser.close()
    print(f"done in {time.monotonic() - started:.0f} s", flush=True)
    low = [entry["file"] for entry in record if entry["contrast_px"] < NORM]
    if low:
        print(f"STOP: text below {NORM}:1 in {low}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
