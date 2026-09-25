"""21-Z, step 4a, 4b: primary button states and the «Учебные примеры» cards.

The app must run on port 8637 (run_app.cmd of this folder). One run takes
both themes: light in a default session, dark with ``?embed_options=dark_theme``
(as kadry.py). Frames and pixel measurements go to results/wave21_z/knopka/.

Primary button (stBaseButton-primary), states:
    pokoy       rest: mouse away, no focus
    navedenie   hover: mouse over the button
    fokus       keyboard focus: focus() on a focusable element before it, then Tab
                until the button has the focus
    nazhatie    pressed: mouse down on the button, frame, mouse leaves, mouse up
                (up outside the button: no click, no calculation)
    neaktivnaya disabled: «Затвердевание», block «Управление фазами /
                метастабильный расчёт», «Вручную», LIQUID unchecked in the
                phase table: «Рассчитать затвердевание» is disabled
The same rest / hover / focus for the form button (stBaseButton-primaryFormSubmit)
«Сохранить текущий состав» in «Проекты и данные / Марки и составы».

Contrast by pixels: background = the most frequent colour inside the button
(border excluded), text = the pixel of the button with the largest contrast
to that background (glyph core). The computed style is stored next to it.

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_z\\scripts\\knopka.py
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kadry  # noqa: E402  (21-Z copy: port 8637, state tg21z_state)

mgs = kadry.mgs
OUT = kadry.REPO_ROOT / "results" / "wave21_z" / "knopka"
PAD = 24

STYLE_JS = """
el => {
  const s = getComputedStyle(el);
  const p = el.querySelector('p') || el;
  return {bg: s.backgroundColor, border: s.borderTopColor, color: getComputedStyle(p).color,
          disabled: el.disabled, focus_visible: el.matches(':focus-visible'),
          hover: el.matches(':hover'), active: el.matches(':active'),
          text: el.innerText.trim()};
}
"""

# Keyboard focus: focus() the focusable element right before the button, then Tab.
FOCUS_PREVIOUS_JS = """
el => {
  const all = [...document.querySelectorAll(
    'a[href], button, input, textarea, select, [tabindex]:not([tabindex="-1"])'
  )].filter(e => !e.disabled && e.offsetParent !== null && e.tabIndex >= 0);
  const index = all.indexOf(el);
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


def pixel_contrast(path: Path, box: dict, clip: dict) -> dict:
    from PIL import Image

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        left = round(box["x"] - clip["x"]) + 3
        top = round(box["y"] - clip["y"]) + 3
        right = round(box["x"] - clip["x"] + box["width"]) - 3
        bottom = round(box["y"] - clip["y"] + box["height"]) - 3
        inner = rgb.crop((left, top, right, bottom))
        pixels = list(inner.get_flattened_data())
    background = Counter(pixels).most_common(1)[0][0]
    text = max(set(pixels), key=lambda value: contrast(value, background))
    return {
        "bg_px": hex_of(background),
        "text_px": hex_of(text),
        "contrast_px": round(contrast(text, background), 2),
    }


def rest(page) -> None:
    page.mouse.move(5, 5)
    page.evaluate("() => document.activeElement && document.activeElement.blur()")
    page.wait_for_timeout(400)


def shoot(page, button, stem: str, record: list, what: str, theme: str) -> None:
    button.scroll_into_view_if_needed()
    page.wait_for_timeout(250)
    box = button.bounding_box()
    clip = {
        "x": max(0, box["x"] - PAD),
        "y": max(0, box["y"] - PAD),
        "width": box["width"] + 2 * PAD,
        "height": box["height"] + 2 * PAD,
    }
    path = OUT / f"{stem}.png"
    page.screenshot(path=str(path), clip=clip)
    style = button.evaluate(STYLE_JS)
    entry = {"file": path.name, "theme": theme, "what": what, **style,
             **pixel_contrast(path, box, clip)}
    record.append(entry)
    print(f"  {stem}: bg {entry['bg_px']} text {entry['text_px']} "
          f"{entry['contrast_px']}:1  (css bg {style['bg']}, color {style['color']}, "
          f"hover={style['hover']} focus-visible={style['focus_visible']} "
          f"active={style['active']} disabled={style['disabled']})", flush=True)


def states(page, button, prefix: str, record: list, what: str, theme: str,
           *, pressed: bool) -> None:
    slug = kadry.THEME_SLUG[theme]
    rest(page)
    shoot(page, button, f"{prefix}_1_pokoy_{slug}", record, f"{what}: покой", theme)
    button.hover()
    page.wait_for_timeout(400)
    shoot(page, button, f"{prefix}_2_navedenie_{slug}", record, f"{what}: наведение", theme)
    rest(page)
    previous = button.evaluate(FOCUS_PREVIOUS_JS)
    if not previous:
        raise RuntimeError("no focusable element before the button")
    print(f"    Tab from: {previous}", flush=True)
    for presses in range(1, 31):
        page.keyboard.press("Tab")
        page.wait_for_timeout(150)
        if button.evaluate("el => document.activeElement === el"):
            break
    else:
        raise RuntimeError("Tab did not reach the button")
    print(f"    Tab pressed {presses} time(s)", flush=True)
    page.wait_for_timeout(300)
    shoot(page, button, f"{prefix}_3_fokus_{slug}", record, f"{what}: фокус с клавиатуры (Tab)",
          theme)
    rest(page)
    if pressed:
        button.hover()
        page.mouse.down()
        page.wait_for_timeout(300)
        shoot(page, button, f"{prefix}_4_nazhatie_{slug}", record, f"{what}: нажатие", theme)
        page.mouse.move(5, 5, steps=5)
        page.mouse.up()
        page.wait_for_timeout(300)
        rest(page)


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
    main = mgs.main_area(page)

    print(f"[{theme}] Расчёты / Одна температура", flush=True)
    mgs.open_tab(page, "Расчёты")
    mgs.open_tab(page, "Одна температура")
    button = main.locator('button[data-testid="stBaseButton-primary"]:visible:enabled').first
    states(page, button, "k1_osnovnaya", record,
           f"Расчёты / Одна температура, «{button.inner_text().strip()}»", theme, pressed=True)

    print(f"[{theme}] Затвердевание: LIQUID снята", flush=True)
    mgs.open_tab(page, "Затвердевание")
    block = mgs.open_expander(page, main, "Управление фазами / метастабильный расчёт")
    block.locator('[data-testid="stRadioOption"]').filter(has_text="Вручную").first.click()
    mgs.wait_idle(page)
    grid = block.locator('[data-testid="stDataFrame"]').first
    grid.scroll_into_view_if_needed()
    box = grid.bounding_box()
    page.mouse.move(box["x"] + 300, box["y"] + 200)
    liquid = grid.locator('[role="gridcell"]').filter(has_text="LIQUID")
    for _ in range(12):
        if liquid.count():
            break
        page.mouse.wheel(0, 150)
        page.wait_for_timeout(300)
    # Glide grid: header 41 px, row 39 px; the a11y row index gives the row.
    row = int(liquid.first.evaluate("c => c.parentElement.getAttribute('aria-rowindex')")) - 2
    scroll = grid.evaluate("g => g.querySelector('.dvn-scroller').scrollTop")
    box = grid.bounding_box()
    page.mouse.click(box["x"] + 82, box["y"] + 60.5 + 39 * row - scroll)
    page.wait_for_timeout(500)
    mgs.wait_idle(page)
    errors = main.locator('[data-testid="stAlertContentError"]:visible').all_inner_texts()
    print(f"    errors: {errors}", flush=True)
    disabled = main.locator('button[data-testid="stBaseButton-primary"]:disabled').filter(
        has_text="Рассчитать затвердевание").first
    label = disabled.inner_text().strip()
    rest(page)
    shoot(page, disabled, f"k1_osnovnaya_5_neaktivnaya_{slug}", record,
          f"Затвердевание, LIQUID снята, «{label}»: неактивная", theme)
    disabled.hover()
    page.wait_for_timeout(400)
    shoot(page, disabled, f"k1_osnovnaya_6_neaktivnaya_navedenie_{slug}", record,
          f"Затвердевание, LIQUID снята, «{label}»: неактивная, наведение", theme)
    # Wider frame: the button with the error above it.
    disabled.scroll_into_view_if_needed()
    button_box = disabled.bounding_box()
    page.screenshot(path=str(OUT / f"k1_osnovnaya_5_neaktivnaya_mesto_{slug}.png"),
                    clip={"x": 0, "y": max(0, button_box["y"] - 260),
                          "width": kadry.VIEWPORT["width"], "height": 340})

    print(f"[{theme}] Проекты и данные / Марки и составы", flush=True)
    mgs.open_tab(page, "Проекты и данные")
    mgs.open_tab(page, "Марки и составы")
    form_button = main.locator(
        'button[data-testid="stBaseButton-primaryFormSubmit"]:visible:enabled'
    ).first
    states(page, form_button, "k2_forma", record,
           f"Проекты и данные / Марки и составы, «{form_button.inner_text().strip()}»", theme,
           pressed=False)

    print(f"[{theme}] Проекты и данные / Как пользоваться", flush=True)
    mgs.open_tab(page, "Как пользоваться")
    rest(page)
    cards = main.locator('div[class*="st-key-quick_example_card_"]:visible')
    # Three cards one under another: a taller window, as kadry.capture does.
    page.set_viewport_size({"width": kadry.VIEWPORT["width"], "height": 1800})
    page.wait_for_timeout(600)
    cards.first.scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    boxes = [cards.nth(i).bounding_box() for i in range(cards.count())]
    top = min(b["y"] for b in boxes) - 80
    bottom = max(b["y"] + b["height"] for b in boxes)
    clip = {"x": 0, "y": max(0, top), "width": kadry.VIEWPORT["width"],
            "height": bottom - max(0, top) + PAD}
    path = OUT / f"k3_uchebnye_primery_{slug}.png"
    page.screenshot(path=str(path), clip=clip)
    from PIL import Image

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        window = rgb.getpixel((5, 5))
        card_px = []
        for index, box in enumerate(boxes):
            inner = rgb.crop((round(box["x"] + 6), round(box["y"] - clip["y"] + 6),
                              round(box["x"] + box["width"] - 6),
                              round(box["y"] - clip["y"] + box["height"] - 6)))
            card_px.append(hex_of(Counter(inner.get_flattened_data()).most_common(1)[0][0]))
    css = [cards.nth(i).evaluate(
        "el => ({key: [...el.classList].find(c => c.startsWith('st-key-')),"
        " bg: getComputedStyle(el).backgroundColor, border: getComputedStyle(el).borderTopColor})"
    ) for i in range(cards.count())]
    entry = {"file": path.name, "theme": theme,
             "what": "Проекты и данные / Как пользоваться: «Учебные примеры»",
             "window_px": hex_of(window), "cards_px": card_px, "cards_css": css}
    record.append(entry)
    print(f"  {path.stem}: window {entry['window_px']} cards {card_px} css {css}", flush=True)
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
            (OUT / "knopka.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            browser.close()
    print(f"done in {time.monotonic() - started:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
