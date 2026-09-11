"""Снимки живого интерфейса, отложенные волнами 10, 11E и 11G (пункт 11K-3).

Скрипт поднимает приложение из этого рабочего дерева на отдельном порту с
собственным ``THERMOGAR_STATE_ROOT`` во временном каталоге: установленная копия
и ``%LOCALAPPDATA%\\ThermoGar`` не затрагиваются.

Снимается:

* предупреждение об оценочной плотности — фазы без модели в физической базе
  (никелевая база, контрольный состав ХН62М(Sc)-ВИ);
* панель «Паспорт базы» для стали **в установленной конфигурации**, то есть без
  каталога ``databases/diagnostic``: панель обязана читать отпечаток эталона.
  Каталог на время съёмки переименовывается и возвращается на место в
  ``finally`` — ничего не удаляется.

Запуск:

    "C:/Users/gareg/Desktop/ThermoGar/.venv-windows/Scripts/python.exe" \\
        -X utf8 tools/make_wave11k_screens.py

Ключи: ``--port``, ``--only``, ``--keep-diagnostic``.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHOTS = REPO_ROOT / "docs" / "screenshots"
DIAGNOSTIC_DIR = REPO_ROOT / "databases" / "diagnostic"
HIDDEN_DIAGNOSTIC_DIR = REPO_ROOT / "databases" / "_diagnostic_hidden_11k"

# Путь состояния короткий намеренно: длинный упирается в MAX_PATH и приложение
# зависает (замечено волной 11B).
STATE_ROOT = Path(os.environ.get("TEMP", r"C:\Windows\Temp")) / "thermogar_11k_state"

VIEWPORT = {"width": 1500, "height": 1000}
UI_TIMEOUT_MS = 60_000
CALC_TIMEOUT_MS = 900_000

DB_NI = "Никелевые сплавы"
DB_FE = "Стали и Fe-сплавы"

# Контрольный состав ХН62М(Sc)-ВИ, массовые %, основа Ni.
CONTROL_COMPOSITION = (
    "C=0.005, SI=0.10, MN=0.50, S=0.020, CR=23.5, MO=13.0, "
    "NB=0.06, AL=0.25, TI=0.10, FE=0.50"
)


# --------------------------------------------------------------------------- #
# Приложение
# --------------------------------------------------------------------------- #


def app_is_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/_stcore/health", timeout=5
        ) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def port_is_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(1.0)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def start_app(port: int) -> subprocess.Popen:
    if STATE_ROOT.exists():
        shutil.rmtree(STATE_ROOT)
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["THERMOGAR_STATE_ROOT"] = str(STATE_ROOT)
    environment["PYTHONHASHSEED"] = "0"
    environment["PYTHONUTF8"] = "1"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(REPO_ROOT / "app" / "ThermoGar_app.py"),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--server.address",
            "127.0.0.1",
        ],
        cwd=str(REPO_ROOT),
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 240.0
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Приложение завершилось до готовности.")
        if app_is_ready(port):
            return process
        time.sleep(1.0)
    process.terminate()
    raise RuntimeError("Приложение не поднялось за 240 с.")


# --------------------------------------------------------------------------- #
# Работа со страницей
# --------------------------------------------------------------------------- #

SCRIPT_STATE_JS = """
() => {
  const app = document.querySelector('[data-testid="stApp"]');
  return app ? app.getAttribute('data-test-script-state') : 'missing';
}
"""


def wait_idle(page) -> None:
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        if page.evaluate(SCRIPT_STATE_JS) != "notRunning":
            break
        page.wait_for_timeout(100)
    deadline = time.monotonic() + CALC_TIMEOUT_MS / 1000.0
    quiet = 0
    while time.monotonic() < deadline:
        if page.evaluate(SCRIPT_STATE_JS) == "notRunning":
            quiet += 1
            if quiet >= 3:
                return
        else:
            quiet = 0
        page.wait_for_timeout(200)
    raise TimeoutError("Приложение не завершило пересчёт.")


def main_area(page):
    return page.locator('[data-testid="stMain"]')


def sidebar(page):
    return page.locator('[data-testid="stSidebar"]')


def widget(root, testid: str, label: str):
    return root.locator(f'[data-testid="{testid}"]:visible').filter(has_text=label).first


def reveal(locator) -> None:
    """Подтащить элемент к центру окна.

    ``scroll_into_view_if_needed`` спотыкается о собственную прокрутку боковой
    панели Streamlit: он докручивает страницу, а элемент остаётся за кадром.
    Поэтому прокрутка делается самим браузером.
    """

    locator.evaluate(
        "element => element.scrollIntoView({block: 'center', inline: 'center'})"
    )


def set_number(root, label: str, value: str) -> None:
    field = widget(root, "stNumberInput", label).locator("input")
    reveal(field)
    field.click()
    field.press("Control+a")
    field.fill(value)
    field.press("Enter")


def set_text_area(root, label: str, value: str) -> None:
    field = widget(root, "stTextArea", label).locator("textarea")
    reveal(field)
    field.click()
    field.press("Control+a")
    field.fill(value)
    field.press("Control+Enter")


def set_selectbox(page, root, label: str, option: str) -> None:
    control = widget(root, "stSelectbox", label)
    field = control.locator('input[role="combobox"]').first
    reveal(field)
    if (field.input_value() or "").startswith(option):
        return
    field.click()
    page.get_by_role("option").first.wait_for(timeout=UI_TIMEOUT_MS)
    page.get_by_role("option", name=option, exact=False).first.click()
    wait_idle(page)


def set_checkbox(page, root, label: str, checked: bool) -> None:
    control = widget(root, "stCheckbox", label)
    reveal(control)
    box = control.locator('input[type="checkbox"]')
    if box.is_checked() == checked:
        return
    target = control.locator("label")
    (target.first if target.count() else control).click()
    wait_idle(page)


def set_multiselect(page, root, label: str, values: list[str]) -> None:
    control = widget(root, "stMultiSelect", label)
    reveal(control)
    clear = control.locator('[aria-label="Clear all"], [title="Clear all"]')
    if clear.count():
        clear.first.click()
        wait_idle(page)
    field = control.locator("input").first
    for value in values:
        field.click()
        field.fill(value)
        page.wait_for_timeout(300)
        page.get_by_role("option", name=value, exact=True).first.click()
        page.wait_for_timeout(200)
    page.keyboard.press("Escape")
    wait_idle(page)


def open_tab(page, name: str) -> None:
    tab = page.get_by_role("tab", name=name, exact=True).first
    reveal(tab)
    tab.click()
    wait_idle(page)


def ensure_sidebar(page) -> None:
    """Раскрыть боковую панель: приложение стартует с закрытой."""

    box = sidebar(page).bounding_box()
    if box and box["width"] > 10:
        return
    for selector in (
        '[data-testid="stExpandSidebarButton"]',
        '[data-testid="stSidebarCollapsedControl"]',
    ):
        control = page.locator(selector).first
        if control.count():
            control.click()
            break
    else:
        raise RuntimeError("Не нашлась кнопка раскрытия боковой панели.")
    page.wait_for_timeout(800)
    wait_idle(page)
    box = sidebar(page).bounding_box()
    if not box or box["width"] <= 10:
        raise RuntimeError("Боковая панель не раскрылась.")


def set_database(page, label: str) -> None:
    ensure_sidebar(page)
    set_selectbox(page, sidebar(page), "База материалов", label)


EXPAND_GRID_JS = """
(element, height) => {
  // Таблица Streamlit рисуется на canvas и виртуализирована: строки ниже
  // видимой части просто не существуют в DOM. Поэтому контейнеру задаётся
  // высота, и таблица перерисовывается целиком.
  element.style.height = height + 'px';
  element.style.maxHeight = 'none';
  const inner = element.querySelector('[data-testid="stDataFrameResizable"]');
  if (inner) {
    inner.style.height = height + 'px';
    inner.style.maxHeight = 'none';
  }
  window.dispatchEvent(new Event('resize'));
}
"""


def expand_grid(page, frame, height: int) -> None:
    frame.evaluate(EXPAND_GRID_JS, height)
    page.wait_for_timeout(900)


def shoot(page, targets, name: str) -> Path:
    """Кадр по объединяющей рамке нескольких элементов."""

    if not isinstance(targets, (list, tuple)):
        targets = [targets]
    boxes = []
    for target in targets:
        reveal(target)
        page.wait_for_timeout(150)
        box = target.bounding_box()
        if box:
            boxes.append(box)
    if not boxes:
        raise RuntimeError(f"{name}: не нашлось ни одного элемента для кадра")
    left = min(box["x"] for box in boxes)
    top = min(box["y"] for box in boxes)
    right = max(box["x"] + box["width"] for box in boxes)
    bottom = max(box["y"] + box["height"] for box in boxes)
    margin = 14
    x = max(0.0, left - margin)
    y = max(0.0, top - margin)
    clip = {
        "x": x,
        "y": y,
        "width": min(float(VIEWPORT["width"]) - x, right - x + margin),
        "height": min(2200.0, bottom - y + margin),
    }
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / name
    page.screenshot(path=str(path), clip=clip)
    print(f"  {name}")
    return path


# --------------------------------------------------------------------------- #
# Сценарии
# --------------------------------------------------------------------------- #


def shot_estimated_density(page) -> None:
    """Предупреждение об оценочной плотности на контрольном сплаве."""

    set_database(page, DB_NI)
    ensure_sidebar(page)
    side = sidebar(page)
    set_text_area(side, "Добавки", CONTROL_COMPOSITION)
    wait_idle(page)

    open_tab(page, "Свойства")
    open_tab(page, "Плотность")
    root = main_area(page)
    set_number(root, "Температура, °C", "400")
    wait_idle(page)
    # Автоматический набор — это сотня фаз базы, и pycalphad на нём валит
    # Workspace ещё до расчёта (BACKEND_FAILED: ValueError, дефект найден этой
    # волной, см. отчёт). Берётся ручной набор: матрица плюс те самые фазы, у
    # которых в физической базе нет модели плотности.
    root = main_area(page)
    set_checkbox(page, root, "Выбрать фазы вручную", True)
    root = main_area(page)
    set_multiselect(
        page,
        root,
        "Фазы",
        ["FCC_A1", "NI2CR", "MNS_Q", "P_PHASE", "MU_PHASE", "DELTA"],
    )
    root = main_area(page)
    button = root.get_by_role(
        "button", name="Рассчитать плотность и объёмные доли", exact=True
    ).first
    reveal(button)
    print("  кнопка отключена:", button.is_disabled(), flush=True)
    button.click()

    frames = root.locator('[data-testid="stDataFrame"]:visible')
    deadline = time.monotonic() + CALC_TIMEOUT_MS / 1000.0
    while not frames.count():
        if time.monotonic() > deadline:
            print("  таблица так и не появилась", flush=True)
            print(main_area(page).inner_text()[:1500], flush=True)
            raise TimeoutError("Плотность не посчиталась")
        alerts = main_area(page).locator('[data-testid="stAlert"]:visible')
        print(
            "  ждём: state=%s, таблиц=%d, сообщений=%d"
            % (page.evaluate(SCRIPT_STATE_JS), frames.count(), alerts.count()),
            flush=True,
        )
        for index in range(alerts.count()):
            print("   !", alerts.nth(index).inner_text()[:300], flush=True)
        page.wait_for_timeout(30_000)
    wait_idle(page)

    root = main_area(page)
    alerts = root.locator('[data-testid="stAlert"]:visible')
    count = alerts.count()
    print(f"  сообщений в результате: {count}", flush=True)
    for index in range(count):
        print("   -", alerts.nth(index).inner_text()[:300], flush=True)
    # Кадр берётся одним куском: метрика, таблица покрытия и предупреждение.
    # По одному элементу снимать нельзя — каждый reveal прокручивает страницу,
    # и рамки, снятые при разной прокрутке, не складываются.
    page.set_viewport_size({"width": VIEWPORT["width"], "height": 1400})
    page.wait_for_timeout(400)
    root = main_area(page)
    metric = root.locator('[data-testid="stMetric"]').first
    metric.evaluate("element => element.scrollIntoView({block: 'start'})")
    page.wait_for_timeout(600)
    top = metric.bounding_box()
    alerts = root.locator('[data-testid="stAlert"]:visible')
    bottom = alerts.nth(alerts.count() - 1).bounding_box() if alerts.count() else top
    x = max(0.0, top["x"] - 20)
    y = max(0.0, top["y"] - 20)
    height = min(1380.0, bottom["y"] + bottom["height"] - y + 20)
    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / "08-estimated-density-warning.png"
    page.screenshot(
        path=str(path),
        clip={
            "x": x,
            "y": y,
            "width": min(float(VIEWPORT["width"]) - x, 1360.0),
            "height": height,
        },
    )
    print("  08-estimated-density-warning.png", flush=True)
    page.set_viewport_size(dict(VIEWPORT))


def shot_steel_passport(page) -> None:
    """Панель «Паспорт базы» для стали в установленной конфигурации."""

    set_database(page, DB_FE)
    open_tab(page, "Проекты и данные")
    open_tab(page, "Паспорт базы")
    wait_idle(page)
    root = main_area(page)
    frame = root.locator('[data-testid="stDataFrame"]:visible').first
    frame.wait_for(timeout=UI_TIMEOUT_MS)
    page.set_viewport_size({"width": VIEWPORT["width"], "height": 1500})
    page.wait_for_timeout(400)
    expand_grid(page, frame, 700)
    caption = root.get_by_text("Steel/Fe · thermogar_patch", exact=False).first
    targets = [caption, frame] if caption.count() else [frame]
    shoot(page, targets, "09-steel-passport-installed.png")
    page.set_viewport_size(dict(VIEWPORT))


SCENARIOS = {
    "density": shot_estimated_density,
    "passport": shot_steel_passport,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8611)
    parser.add_argument("--only", default="")
    parser.add_argument(
        "--keep-diagnostic",
        action="store_true",
        help="не прятать databases/diagnostic (панель покажет эталонную базу)",
    )
    arguments = parser.parse_args()

    selected = [name.strip() for name in arguments.only.split(",") if name.strip()]
    scenarios = selected or list(SCENARIOS)
    for name in scenarios:
        if name not in SCENARIOS:
            raise SystemExit(f"Нет сценария {name}; есть: {', '.join(SCENARIOS)}")

    from playwright.sync_api import sync_playwright

    hidden = False
    if not arguments.keep_diagnostic and DIAGNOSTIC_DIR.is_dir():
        if HIDDEN_DIAGNOSTIC_DIR.exists():
            raise SystemExit(
                f"Каталог {HIDDEN_DIAGNOSTIC_DIR} уже существует — прошлый прогон "
                "не вернул его на место. Разобраться вручную."
            )
        DIAGNOSTIC_DIR.rename(HIDDEN_DIAGNOSTIC_DIR)
        hidden = True
        print(f"databases/diagnostic временно убран в {HIDDEN_DIAGNOSTIC_DIR.name}")

    process = None
    try:
        if port_is_open(arguments.port):
            raise SystemExit(f"Порт {arguments.port} занят.")
        print(f"Запуск приложения на порту {arguments.port}…")
        process = start_app(arguments.port)
        print("Приложение готово.")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport=dict(VIEWPORT))
            page.set_default_timeout(UI_TIMEOUT_MS)
            page.goto(f"http://127.0.0.1:{arguments.port}", wait_until="load")
            wait_idle(page)
            for name in scenarios:
                print(f"Сценарий {name}:")
                SCENARIOS[name](page)
            browser.close()
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
        if hidden:
            HIDDEN_DIAGNOSTIC_DIR.rename(DIAGNOSTIC_DIR)
            print("databases/diagnostic возвращён на место")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
