"""21-E, step 6g: charts after a theme switch in the main menu.

State 04 (Расчёты → Температурный диапазон, 500–900 °C, step 100 °C) is
calculated once in the light theme. Then the theme is switched
light → dark → light through the main menu (⋮). For every switch the script
records what the user sees:

* ``srazu``  — right after the page has taken the new theme, no other action;
* ``pozzhe`` — 3 s later, still no action;
* ``posle_deystviya`` — after the next action (a click on the subtab
  «Температурный диапазон» that is already open).

For each moment: a frame of the page, the chart image and the colour of its
corner pixel (chart background), the PNG from the «PNG» download button and
its corner pixel, and the number of «Скан по температуре» entries in the
calculation history of the state root (a new calculation adds one).

The app must run on port 8637 (run_app.cmd of this folder).

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_z\\scripts\\smena_temy.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kadry  # noqa: E402  (copy of the 21-B script, 21-E paths)

mgs = kadry.mgs
REPO_ROOT = kadry.REPO_ROOT
OUT = REPO_ROOT / "results" / "wave21_z" / "smena_temy"
STATE_ROOT = Path(os.environ["TEMP"]) / "tg21z_state"
PORT = kadry.PORT
CHART_BG = {"Light": (255, 255, 255), "Dark": (31, 34, 38)}


def history_count() -> int:
    count = 0
    for path in STATE_ROOT.rglob("*"):
        if path.is_file() and path.suffix in {".jsonl", ".json", ".log"}:
            try:
                text = path.read_text("utf-8", errors="ignore")
            except OSError:
                continue
            count += text.count("Скан по температуре")
    return count


def corner(png: bytes) -> tuple[int, int, int]:
    from PIL import Image

    with Image.open(io.BytesIO(png)) as image:
        rgb = image.convert("RGB")
        return rgb.getpixel((20, rgb.height - 20))


def chart_theme(pixel: tuple[int, int, int]) -> str:
    for theme, colour in CHART_BG.items():
        if all(abs(a - b) <= 2 for a, b in zip(pixel, colour)):
            return theme
    return f"other {pixel}"


def chart_now(root) -> bytes:
    return root.locator('[data-testid="stImage"] img:visible').first.screenshot()


def observe(page, root, stem: str, download: bool = False) -> dict:
    """Frame and chart; the PNG download only when asked (the button reruns)."""

    chart_png = chart_now(root)
    (OUT / f"{stem}_grafik.png").write_bytes(chart_png)
    page.screenshot(path=str(OUT / f"{stem}_kadr.png"))
    record = {
        "page_theme": kadry.current_theme(page),
        "chart_corner": corner(chart_png),
        "chart_theme": chart_theme(corner(chart_png)),
    }
    if download:
        with page.expect_download() as download_info:
            root.get_by_role("button", name="PNG", exact=True).first.click()
        png_path = OUT / f"{stem}_vygruzka.png"
        download_info.value.save_as(str(png_path))
        exported = png_path.read_bytes()
        record["png_corner"] = corner(exported)
        record["png_theme"] = chart_theme(corner(exported))
        mgs.wait_idle(page)
    record["history_scans"] = history_count()
    print(f"  {stem}: {record}", flush=True)
    return record


def wait_chart_theme(root, theme: str, limit_s: float = 15.0) -> float | None:
    """Seconds from now until the chart shows the theme, None if it does not."""

    started = time.monotonic()
    while time.monotonic() - started < limit_s:
        if chart_theme(corner(chart_now(root))) == theme:
            return round(time.monotonic() - started, 2)
        time.sleep(0.2)
    return None


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

    result: dict = {"free_gib_at_start": round(free, 2)}
    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=dict(kadry.VIEWPORT),
            device_scale_factor=1,
            color_scheme="light",
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            accept_downloads=True,
        )
        context.set_default_timeout(mgs.UI_TIMEOUT_MS)
        page = context.new_page()
        page.goto(f"http://127.0.0.1:{PORT}/", wait_until="domcontentloaded")
        page.get_by_role("tab", name="Расчёты", exact=True).wait_for(timeout=mgs.CALC_TIMEOUT_MS)
        mgs.wait_idle(page)
        try:
            result["history_before_calculation"] = history_count()
            mgs.open_tab(page, "Расчёты")
            mgs.open_tab(page, "Температурный диапазон")
            root = mgs.main_area(page)
            mgs.set_number(root, "От, °C", "500")
            mgs.wait_idle(page)
            mgs.set_number(root, "До, °C", "900")
            mgs.wait_idle(page)
            mgs.set_number(root, "Шаг, °C", "100")
            mgs.wait_idle(page)
            root.get_by_role("button", name="Построить график по температуре", exact=True).first.click()
            root.locator('[data-testid="stImage"] img:visible').first.wait_for(timeout=mgs.CALC_TIMEOUT_MS)
            mgs.wait_idle(page)
            page.wait_for_timeout(1000)
            steps: list[dict] = []
            steps.append({"moment": "posle_rascheta",
                          **observe(page, root, "00_svet_posle_rascheta", download=True)})
            for index, theme in enumerate(("Dark", "Light"), start=1):
                slug = kadry.THEME_SLUG[theme]
                # Page frame right after the switch, before anything else.
                kadry.set_theme(page, theme)
                steps.append({"moment": "srazu", "to": theme,
                              **observe(page, root, f"{index:02d}_{slug}_srazu")})
                redraw_s = wait_chart_theme(root, theme)
                steps.append({"moment": "bez_deystviy", "to": theme,
                              "chart_in_new_theme_after_s": redraw_s,
                              **observe(page, root, f"{index:02d}_{slug}_bez_deystviy")})
                page.wait_for_timeout(3000)
                steps.append({"moment": "pozzhe_3s", "to": theme,
                              **observe(page, root, f"{index:02d}_{slug}_pozzhe")})
                page.get_by_role("tab", name="Температурный диапазон", exact=True).first.click()
                mgs.wait_idle(page)
                page.wait_for_timeout(800)
                steps.append({"moment": "posle_deystviya", "to": theme,
                              **observe(page, root, f"{index:02d}_{slug}_posle_deystviya", download=True)})
            result["steps"] = steps
            result["history_after_switches"] = history_count()
        finally:
            browser.close()
    (OUT / "smena_temy.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
