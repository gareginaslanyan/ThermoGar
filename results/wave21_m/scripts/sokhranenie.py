"""21-I, step 3c: widget values survive a view switch in the browser.

The app must run on port 8638 (run_app.cmd of this folder). Light theme,
window 1440x900. A view is chosen by a click on its option (role="radio").

1. «Кинетика / Диффузия и гомогенизация / Однофазная пара»: the field
   «Левая сторона» is changed, then «Покрытие базы подвижностей», then back to
   «Однофазная пара»: the value is read again.
2. «Затвердевание»: the calculation of the guide scenario (Al–4Cu–1Mg,
   Scheil, 700 °C, step 10 °C; make_guide_screens.scenario_zatverdevanie,
   no frames from it); view «Остаточный расплав», «Элемент в остаточном
   расплаве» is changed, then «Сводка», then back: the value is read again.

Frames before and after -> results/wave21_i/sokhranenie/, JSON next to them.
On every frame the page text is searched for the Streamlit warnings about a
default value and the Session State API.

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_i\\scripts\\sokhranenie.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kadry  # noqa: E402  (21-I copy: port 8638, state tg21i_state, role tab -> radio)

mgs = kadry.mgs
OUT = kadry.REPO_ROOT / "results" / "wave21_i" / "sokhranenie"
LEFT_NEW = "Cr=12, Al=4"
WARNING_MARKERS = ("Session State", "default value", "session state")


class QuietShooter:
    """No frames from the guide scenario."""

    def __init__(self, page, slug, log) -> None:
        self.log = log
        self.slug = slug

    def shot(self, targets, title, *, tall=False):
        self.log.append({"scenario": self.slug, "title": title})


def warnings_on_page(page) -> list[str]:
    text = page.locator('[data-testid="stAppViewContainer"]').inner_text()
    return [line for line in text.splitlines() if any(m in line for m in WARNING_MARKERS)]


def frame(page, name: str, record: dict, key: str) -> None:
    page.mouse.move(5, 5)
    page.wait_for_timeout(300)
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    record.setdefault("frames", []).append(path.name)
    record.setdefault("warnings", {})[path.name] = warnings_on_page(page)
    print(f"  {name}: warnings {record['warnings'][path.name]}", flush=True)


def checked(page, group: str) -> str:
    return page.get_by_role("radiogroup", name=group, exact=True).locator(
        '[role="radio"][aria-checked="true"]'
    ).inner_text().strip()


def pick(page, group: str, option: str) -> None:
    page.get_by_role("radiogroup", name=group, exact=True).get_by_role(
        "radio", name=option, exact=True
    ).click()
    mgs.wait_idle(page)


def selectbox_value(root, label: str) -> str:
    control = mgs.widget(root, "stSelectbox", label)
    return control.locator('input[role="combobox"]').first.input_value() or control.inner_text()


def diffusion(page, result: dict) -> None:
    print("[diffusion]", flush=True)
    mgs.open_tab(page, "Кинетика")
    mgs.open_tab(page, "Диффузия и гомогенизация")
    group = "Диффузия и гомогенизация"
    root = mgs.main_area(page)
    field = mgs.widget(root, "stTextArea", "Левая сторона").locator("textarea")
    initial = field.input_value()
    mgs.set_text_area(root, "Левая сторона", LEFT_NEW)
    mgs.wait_idle(page)
    before = mgs.widget(root, "stTextArea", "Левая сторона").locator("textarea").input_value()
    mgs.widget(root, "stTextArea", "Левая сторона").scroll_into_view_if_needed()
    frame(page, "s1_diffuziya_do", result, "diffusion")
    pick(page, group, "Покрытие базы подвижностей")
    away = {
        "checked": checked(page, group),
        "left_fields": mgs.main_area(page).locator('[data-testid="stTextArea"]:visible')
        .filter(has_text="Левая сторона").count(),
    }
    frame(page, "s2_diffuziya_pokrytie", result, "diffusion")
    pick(page, group, "Однофазная пара")
    root = mgs.main_area(page)
    after = mgs.widget(root, "stTextArea", "Левая сторона").locator("textarea").input_value()
    mgs.widget(root, "stTextArea", "Левая сторона").scroll_into_view_if_needed()
    frame(page, "s3_diffuziya_posle", result, "diffusion")
    result["diffusion"] = {
        "field": "Левая сторона", "initial": initial, "set": LEFT_NEW, "before": before,
        "away": away, "after": after, "checked_after": checked(page, group),
        "same": before == after == LEFT_NEW,
    }
    print(f"  {result['diffusion']}", flush=True)


def solidification(page, result: dict) -> None:
    print("[solidification]", flush=True)
    log: list[dict] = []
    saved = mgs.Shooter
    mgs.Shooter = QuietShooter
    try:
        started = time.monotonic()
        mgs.scenario_zatverdevanie(page, log)
        print(f"  calculation {time.monotonic() - started:.0f} s", flush=True)
    finally:
        mgs.Shooter = saved
    group = "Затвердевание"
    pick(page, group, "Остаточный расплав")
    root = mgs.main_area(page)
    label = "Элемент в остаточном расплаве"
    initial = selectbox_value(root, label)
    control = mgs.widget(root, "stSelectbox", label)
    combo = control.locator('input[role="combobox"]').first
    combo.scroll_into_view_if_needed(timeout=mgs.UI_TIMEOUT_MS)
    page.mouse.move(5, 5)
    page.wait_for_timeout(300)
    combo.click()
    page.get_by_role("option").first.wait_for(timeout=mgs.UI_TIMEOUT_MS)
    options = [text.strip() for text in page.get_by_role("option").all_inner_texts()]
    choice = next(option for option in options if option and option != initial)
    page.get_by_role("option", name=choice, exact=True).first.click()
    mgs.wait_idle(page)
    root = mgs.main_area(page)
    before = selectbox_value(root, label)
    mgs.widget(root, "stSelectbox", label).scroll_into_view_if_needed()
    frame(page, "s4_zatverdevanie_do", result, "solidification")
    pick(page, group, "Сводка")
    away = {"checked": checked(page, group),
            "selects": mgs.main_area(page).locator('[data-testid="stSelectbox"]:visible')
            .filter(has_text=label).count()}
    frame(page, "s5_zatverdevanie_svodka", result, "solidification")
    pick(page, group, "Остаточный расплав")
    root = mgs.main_area(page)
    after = selectbox_value(root, label)
    mgs.widget(root, "stSelectbox", label).scroll_into_view_if_needed()
    frame(page, "s6_zatverdevanie_posle", result, "solidification")
    result["solidification"] = {
        "field": label, "options": options, "initial": initial, "set": choice,
        "before": before, "away": away, "after": after,
        "checked_after": checked(page, group), "same": before == after == choice,
    }
    print(f"  {result['solidification']}", flush=True)


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
    result: dict = {}
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=dict(kadry.VIEWPORT), device_scale_factor=1, color_scheme="light",
            locale="ru-RU", timezone_id="Europe/Moscow",
        )
        context.set_default_timeout(mgs.UI_TIMEOUT_MS)
        page = context.new_page()
        try:
            page.goto(f"http://127.0.0.1:{kadry.PORT}/", wait_until="domcontentloaded")
            page.get_by_role("tab", name="Расчёты", exact=True).wait_for(
                timeout=mgs.CALC_TIMEOUT_MS
            )
            mgs.wait_idle(page)
            # As kadry.py: the sidebar opens collapsed in a new session.
            expand = page.locator('[data-testid="stExpandSidebarButton"]')
            if expand.count() and expand.first.is_visible():
                expand.first.click()
                mgs.wait_idle(page)
            diffusion(page, result)
            solidification(page, result)
        finally:
            (OUT / "sokhranenie.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            browser.close()
    ok = all(result.get(part, {}).get("same") for part in ("diffusion", "solidification"))
    ok = ok and not any(result.get("warnings", {}).values())
    print("OK" if ok else "FAILED", flush=True)
    return 0 if ok else 5


if __name__ == "__main__":
    raise SystemExit(main())
