"""Разведка: калибровка показа чисел и DOM сетки (без записи в результаты)."""
import sys
from playwright.sync_api import sync_playwright

OUT = sys.argv[1]
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 900, "height": 600}, locale="ru-RU")
    page.goto("http://localhost:8765/?page=kal&embed=true")
    page.wait_for_selector("[data-testid='stDataFrame']", timeout=30000)
    page.wait_for_timeout(1500)
    page.screenshot(path=OUT + "/kal.png")
    page.goto("http://localhost:8765/?page=t0&v=a&embed=true")
    page.wait_for_selector("[data-testid='stDataFrame']", timeout=30000)
    page.wait_for_timeout(1500)
    html = page.locator("[data-testid='stDataFrame']").inner_html()
    open(OUT + "/dom_t0.html", "w", encoding="utf-8").write(html)
    for sel in ["table[role='grid']", "th", "td", "[role='columnheader']", "[role='gridcell']", "canvas"]:
        print(sel, page.locator("[data-testid='stDataFrame'] " + sel).count())
    heads = page.locator("[data-testid='stDataFrame'] [role='columnheader']")
    for i in range(heads.count()):
        print("H", i, repr(heads.nth(i).inner_text()), heads.nth(i).bounding_box())
    cells = page.locator("[data-testid='stDataFrame'] [role='gridcell']")
    print([cells.nth(i).inner_text() for i in range(min(cells.count(), 30))])
    print("grid box", page.locator("[data-testid='stDataFrame']").bounding_box())
    browser.close()
