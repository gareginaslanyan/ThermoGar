"""21-E, step 6d: a chart with 7 phase lines, light and dark, grey copies.

None of the 36 states of 21-B draws 7 or more phase lines (the binary
diagram of frame 15 has 4). This script takes «Энергии → Энергии фаз» on the
training defaults of the Ni database (base NI, additives as the app opens,
600–1300 °C as the tab opens) with the first 8 phases of the phase list (limit of the field; one of them, DIAMOND_A4, gives no curve),
view «Абсолютная молярная энергия GM», in a light session and in a dark
session (``?embed_options=dark_theme``). For each theme: the chart image,
its grey copy and the PNG of the download button.

The app must run on port 8635 (run_app.cmd of this folder).

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_e\\scripts\\sem_faz.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kadry  # noqa: E402  (copy of the 21-B script, 21-E paths)

mgs = kadry.mgs
OUT = kadry.REPO_ROOT / "results" / "wave21_e" / "sem_faz"
PORT = kadry.PORT
LABEL = "Фазы для сравнения — не более восьми"


def pick_first_phases(page, root, count: int) -> list[str]:
    control = mgs.widget(root, "stMultiSelect", LABEL)
    clear = control.locator('[aria-label="Clear all"], [title="Clear all"]')
    if clear.count():
        clear.first.click()
        mgs.wait_idle(page)
    field = control.locator("input").first
    field.click()
    page.wait_for_timeout(400)
    names = [
        text.strip()
        for text in page.get_by_role("option").all_inner_texts()
        if text.strip() and text.strip() != "Select all"
    ][:count]
    page.keyboard.press("Escape")
    for name in names:
        field.click()
        field.fill(name)
        page.wait_for_timeout(250)
        page.get_by_role("option", name=name, exact=True).first.click()
        page.wait_for_timeout(150)
    page.keyboard.press("Escape")
    mgs.wait_idle(page)
    return names


def run_theme(driver, theme: str) -> dict:
    browser = driver.chromium.launch(headless=True)
    try:
        context = browser.new_context(
            viewport=dict(kadry.VIEWPORT), device_scale_factor=1, color_scheme="light",
            locale="ru-RU", timezone_id="Europe/Moscow", accept_downloads=True,
        )
        context.set_default_timeout(mgs.UI_TIMEOUT_MS)
        page = context.new_page()
        query = "?embed_options=dark_theme" if theme == "Dark" else ""
        page.goto(f"http://127.0.0.1:{PORT}/{query}", wait_until="domcontentloaded")
        page.get_by_role("tab", name="Расчёты", exact=True).wait_for(timeout=mgs.CALC_TIMEOUT_MS)
        mgs.wait_idle(page)
        expand = page.locator('[data-testid="stExpandSidebarButton"]')
        if expand.count() and expand.first.is_visible():
            expand.first.click()
            mgs.wait_idle(page)
        mgs.set_database(page, mgs.DB_NI)
        mgs.open_tab(page, "Энергии")
        mgs.open_tab(page, "Энергии фаз")
        root = mgs.main_area(page)
        phases = pick_first_phases(page, root, 8)
        root.get_by_text("Абсолютная молярная энергия GM", exact=True).first.click()
        mgs.wait_idle(page)
        root.get_by_role("button", name="Рассчитать энергии фаз", exact=True).first.click()
        image = root.locator('[data-testid="stImage"] img:visible').first
        image.wait_for(timeout=mgs.CALC_TIMEOUT_MS)
        mgs.wait_idle(page)
        page.wait_for_timeout(800)
        slug = kadry.THEME_SLUG[theme]
        chart = OUT / f"sem_faz_{slug}.png"
        image.screenshot(path=str(chart))
        grey = kadry.grey_copy(chart)
        with page.expect_download() as info:
            root.get_by_role("button", name="Скачать PNG", exact=True).first.click()
        exported = OUT / f"sem_faz_{slug}_vygruzka.png"
        info.value.save_as(str(exported))
        kadry.grey_copy(exported)
        settings = {}
        for label in ("Температура от, °C", "Температура до, °C", "Шаг температуры, °C"):
            settings[label] = mgs.widget(root, "stNumberInput", label).locator("input").first.input_value()
        side = page.locator('[data-testid="stSidebar"]')
        settings["Добавки"] = side.locator("textarea").first.input_value()
        return {"theme": theme, "phases": phases, "settings": settings,
                "files": [chart.name, grey.name, exported.name]}
    finally:
        browser.close()


def main() -> int:
    free = kadry.free_gib()
    print(f"free memory {free:.2f} GiB", flush=True)
    if free < kadry.MIN_FREE_GIB:
        print("STOP: free memory below threshold", file=sys.stderr)
        return 3
    if not mgs.app_is_ready(PORT):
        print(f"STOP: no app on port {PORT}", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    runs = []
    with sync_playwright() as driver:
        for theme in kadry.THEMES:
            runs.append(run_theme(driver, theme))
            print(json.dumps(runs[-1], ensure_ascii=False), flush=True)
    (OUT / "sem_faz.json").write_text(json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
