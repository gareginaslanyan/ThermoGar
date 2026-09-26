"""Кадры и замеры пробы 21-С: варианты показа пустых ячеек.

Запуск: python kadry.py <папка кадров> <файл json замеров> <папка черновых кадров>
Черновые кадры (для поиска столбцов) пишутся вне результатов и перезаписываются.
Приложение-проба должно работать на http://localhost:8765.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8765/"
KADRY = Path(sys.argv[1])
ZAMERY = Path(sys.argv[2])
TMP = Path(sys.argv[3])
KADRY.mkdir(parents=True, exist_ok=True)
VARIANTS = ["a", "a2", "b", "c", "g0", "g1"]
THEMES = {"svet": "light_theme", "tyomn": "dark_theme"}
GRID = "[data-testid='stDataFrame']"

# Chromium даёт showSaveFilePicker; без него Streamlit скачивает через <a download>,
# и Playwright ловит файл.
NO_PICKER = "delete window.showSaveFilePicker;"


def url(page_name: str, variant: str, theme: str) -> str:
    return f"{BASE}?page={page_name}&v={variant}&embed=true&embed_options={THEMES[theme]}"


def open_page(page, page_name, variant, theme):
    page.goto(url(page_name, variant, theme))
    page.wait_for_selector(GRID, timeout=30000)
    page.wait_for_timeout(1200)


def rows(page) -> list[list[str]]:
    table = page.locator(f"{GRID} table[role='grid'] tbody tr")
    result = []
    for i in range(table.count()):
        cells = table.nth(i).locator("td")
        result.append([cells.nth(j).inner_text() for j in range(cells.count())])
    return result


def headers(page) -> list[str]:
    heads = page.locator(f"{GRID} [role='columnheader']")
    return [heads.nth(i).inner_text() for i in range(heads.count())]


def column_centers(page, shot: Path) -> list[float]:
    """Середины столбцов по разделителям в строке заголовка кадра."""
    box = page.locator(GRID).bounding_box()
    image = Image.open(shot).convert("RGB")
    y = int(box["y"] + 4)
    left, right = int(box["x"]) + 2, int(box["x"] + box["width"]) - 2
    background = image.getpixel((left + 3, y))
    edges = [left]
    for x in range(left + 3, right - 1):
        pixel = image.getpixel((x, y))
        if sum(abs(a - b) for a, b in zip(pixel, background)) > 12:
            if x - edges[-1] > 8:
                edges.append(x)
    edges.append(right)
    return [(a + b) / 2 for a, b in zip(edges, edges[1:])], box


def click_header(page, shot: Path, index: int):
    centers, box = column_centers(page, shot)
    x = centers[index]
    page.mouse.click(x, box["y"] + 18)
    page.wait_for_timeout(800)
    return centers


def download_csv(page) -> str | None:
    page.locator(GRID).hover()
    page.wait_for_timeout(400)
    button = page.locator("[data-testid='stElementToolbar'] button[aria-label='Download as CSV']")
    if button.count() == 0:
        return None
    with page.expect_download(timeout=15000) as info:
        button.first.click()
    path = info.value.path()
    return Path(path).read_bytes().decode("utf-8-sig", errors="replace")


def cell_center(page, shot: Path, col: int, row: int):
    centers, box = column_centers(page, shot)
    row_height = 35
    return centers[col], box["y"] + row_height * (row + 1) + row_height / 2


def editor_result(page) -> str:
    code = page.locator("[data-testid='stCode'] code")
    return code.inner_text() if code.count() else ""


zamery: dict = {}
with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in THEMES:
        context = browser.new_context(
            viewport={"width": 900, "height": 600},
            locale="ru-RU",
            color_scheme="dark" if theme == "tyomn" else "light",
            accept_downloads=True,
        )
        context.add_init_script(NO_PICKER)
        page = context.new_page()
        for page_name in ("t0", "el"):
            for variant in VARIANTS:
                key = f"{page_name}_{variant}_{theme}"
                open_page(page, page_name, variant, theme)
                shot = KADRY / f"{key}.png"
                page.screenshot(path=str(shot))
                zamery[key] = {"headers": headers(page), "rows_a11y": rows(page)}
                if theme != "svet":
                    continue
                # скачивание с панели таблицы
                try:
                    zamery[key]["csv"] = download_csv(page)
                except Exception as error:  # noqa: BLE001 — замер, не код приложения
                    zamery[key]["csv_error"] = repr(error)
                # сортировка щелчком по заголовку: T₀, °C (t0) или E, ГПа (el)
                open_page(page, page_name, variant, theme)
                page.screenshot(path=str(TMP / "tmp.png"))
                index = 1 if page_name == "t0" else 3
                centers = click_header(page, TMP / "tmp.png", index)
                page.screenshot(path=str(KADRY / f"{key}_sort1.png"))
                zamery[key]["centers"] = centers
                zamery[key]["sort1"] = rows(page)
                page.mouse.click(centers[index], page.locator(GRID).bounding_box()["y"] + 18)
                page.wait_for_timeout(800)
                page.screenshot(path=str(KADRY / f"{key}_sort2.png"))
                zamery[key]["sort2"] = rows(page)
                if page_name != "el":
                    continue
                # ввод в ячейку E, ГПа строки FCC_A1 (строка 1, столбец 3) и очистка E у BCC_A2
                open_page(page, page_name, variant, theme)
                tmp = TMP / "tmp.png"
                page.screenshot(path=str(tmp))
                x, y = cell_center(page, tmp, 3, 1)
                page.mouse.click(x, y)
                page.wait_for_timeout(400)
                page.keyboard.press("Enter")  # открыть редактор ячейки
                page.wait_for_timeout(500)
                page.keyboard.type("200", delay=80)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1500)
                x0, y0 = cell_center(page, tmp, 3, 0)
                page.mouse.click(x0, y0)
                page.keyboard.press("Delete")
                page.wait_for_timeout(1500)
                page.mouse.click(5, 590)
                page.wait_for_timeout(800)
                page.screenshot(path=str(KADRY / f"{key}_vvod.png"))
                zamery[key]["vvod_rows"] = rows(page)
                zamery[key]["vvod_vozvrat"] = editor_result(page)
        context.close()
    browser.close()

ZAMERY.write_text(json.dumps(zamery, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(zamery))
