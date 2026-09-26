"""Разведка ввода в ячейку data_editor (черновые кадры — вне результатов)."""
import sys
from playwright.sync_api import sync_playwright

OUT = sys.argv[1]
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 900, "height": 600}, locale="ru-RU")
    page.goto("http://localhost:8765/?page=el&v=a&embed=true&embed_options=light_theme")
    page.wait_for_selector("[data-testid='stDataFrame']", timeout=30000)
    page.wait_for_timeout(1500)
    page.mouse.click(474, 167)
    page.wait_for_timeout(400)
    page.keyboard.press("Enter")
    page.wait_for_timeout(500)
    page.keyboard.type("200", delay=80)
    page.wait_for_timeout(600)
    page.screenshot(path=OUT + "/v1.png")
    page.keyboard.press("Enter")
    page.wait_for_timeout(2000)
    page.screenshot(path=OUT + "/v2.png")
    print(page.locator("[data-testid='stCode'] code").inner_text())
    browser.close()
