"""Скриншоты иллюстрированного руководства ThermoGar (docs/guide).

Скрипт поднимает приложение из этого worktree на отдельном порту с чистым
``THERMOGAR_STATE_ROOT`` и ``PYTHONHASHSEED=0``, проходит браузером сценарии
каждой вкладки и после каждого шага сохраняет кадр с подсветкой целевого
элемента в ``docs/guide/img``.

Скрипт перезапускаемый: состояние приложения стирается перед прогоном,
виджеты ищутся по подписям, ожидание результата — по появлению таблицы или
графика, а не по таймеру. Повторный запуск даёт тот же набор кадров.

Запуск (основной venv проекта):

    "C:/Users/gareg/Desktop/ThermoGar/.venv-windows/Scripts/python.exe" \
        -X utf8 tools/make_guide_screens.py

Полезные ключи:

    --only start,raschety     снять только указанные сценарии
    --port 8601               порт приложения
    --html                    только пересобрать docs/guide/*.html из md
    --no-html                 не пересобирать html после съёмки
    --keep-server             использовать уже запущенное приложение
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GUIDE_ROOT = REPO_ROOT / "docs" / "guide"
IMG_ROOT = GUIDE_ROOT / "img"
HTML_NAME = "ThermoGar_Guide_0.3.1.html"
HTML_TITLE = "ThermoGar 0.3.1 — иллюстрированное руководство"

# Отдельное состояние только для съёмки: установленная программа и
# %LOCALAPPDATA%\ThermoGar не затрагиваются. Путь короткий намеренно —
# длинный путь состояния упирается в лимит MAX_PATH и приложение зависает.
STATE_ROOT = Path(os.environ.get("TEMP", r"C:\Windows\Temp")) / "thermogar_guide_state"

VIEWPORT = {"width": 1440, "height": 900}
# Один цвет подсветки на всё руководство.
ACCENT = "#C93425"
# Максимальная высота кадра: выше руководство читать неудобно.
MAX_SHOT_HEIGHT = 1700

CALC_TIMEOUT_MS = 600_000
UI_TIMEOUT_MS = 60_000


# ---------------------------------------------------------------------------
# Запуск приложения
# ---------------------------------------------------------------------------


def elastic_library_payload() -> dict[str, object]:
    """Пример модулей упругости для раздела «Свойства».

    Таблица VRH заполняется из локальной библиотеки, поэтому её содержимое
    задаётся здесь, а не вводится в сетку руками: ввод в ``st.data_editor``
    зависит от точки клика и не воспроизводится при перезапуске.
    """

    entries: dict[str, object] = {}
    demo = (
        ("ni", "FCC_A1", 200.0, 0.31, "Учебное значение γ-матрицы"),
        ("ni", "GAMMA_PRIME", 240.0, 0.28, "Учебное значение γ′"),
    )
    for database_key, phase, young, poisson, source in demo:
        entries[f"{database_key}::{phase}"] = {
            "database_key": database_key,
            "phase": phase,
            "young_gpa": young,
            "poisson": poisson,
            "bulk_gpa": young / (3.0 * (1.0 - 2.0 * poisson)),
            "shear_gpa": young / (2.0 * (1.0 + poisson)),
            "origin": "справочно",
            "source": source,
            "reference_temperature_c": 700.0,
            "note": "",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    return {
        "schema_version": 1,
        "updated_at": "2026-01-01T00:00:00+00:00",
        "entries": entries,
    }


def prepare_state_root() -> None:
    if STATE_ROOT.exists():
        shutil.rmtree(STATE_ROOT)
    (STATE_ROOT / "properties").mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        elastic_library_payload(),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    (STATE_ROOT / "properties" / "elastic_phase_properties.json").write_bytes(payload)


def port_is_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(1.0)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def app_is_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/_stcore/health", timeout=5
        ) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def start_app(port: int) -> subprocess.Popen[bytes]:
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
    deadline = time.monotonic() + 180.0
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Приложение завершилось до готовности.")
        if app_is_ready(port):
            return process
        time.sleep(1.0)
    process.terminate()
    raise RuntimeError("Приложение не поднялось за 180 с.")


# ---------------------------------------------------------------------------
# Работа со страницей
# ---------------------------------------------------------------------------

HIGHLIGHT_JS = """
(items) => {
  const layer = document.createElement('div');
  layer.id = '__tg_highlight__';
  layer.style.cssText =
    'position:fixed;left:0;top:0;right:0;bottom:0;z-index:2147483000;pointer-events:none;';
  for (const item of items) {
    const box = document.createElement('div');
    box.style.cssText =
      'position:absolute;box-sizing:border-box;border:3px solid ' + item.color +
      ';border-radius:8px;left:' + item.x + 'px;top:' + item.y +
      'px;width:' + item.w + 'px;height:' + item.h + 'px;';
    layer.appendChild(box);
    if (item.number) {
      const badge = document.createElement('div');
      badge.textContent = String(item.number);
      const size = 34;
      // Номер садится на верхний левый угол рамки, а у самого края окна —
      // на правый, иначе он уезжает за кадр и закрывает подпись поля.
      let bx = item.x < 44 ? item.x + item.w - size / 2 : item.x - size / 2;
      let by = item.y - size / 2;
      if (by < 2) { by = 2; }
      if (bx < 2) { bx = 2; }
      badge.style.cssText =
        'position:absolute;display:flex;align-items:center;justify-content:center;' +
        'box-sizing:border-box;width:' + size + 'px;height:' + size + 'px;' +
        'left:' + bx + 'px;top:' + by + 'px;border-radius:50%;background:' +
        item.color + ';color:#FFFFFF;border:2px solid #FFFFFF;' +
        'font:700 18px/1 Arial,Helvetica,sans-serif;';
      layer.appendChild(badge);
    }
  }
  document.body.appendChild(layer);
}
"""

CLEAR_JS = """
() => {
  const layer = document.getElementById('__tg_highlight__');
  if (layer) { layer.remove(); }
}
"""

CONTENT_BOTTOM_JS = """
() => {
  let bottom = 0;
  const roots = document.querySelectorAll(
    '[data-testid="stMainBlockContainer"], [data-testid="stSidebarUserContent"]'
  );
  for (const root of roots) {
    for (const node of root.querySelectorAll('[data-testid="stElementContainer"]')) {
      const rect = node.getBoundingClientRect();
      if (rect.height > 0 && rect.bottom > bottom) { bottom = rect.bottom; }
    }
  }
  return Math.ceil(bottom);
}
"""

NEEDED_HEIGHT_JS = """
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const side = document.querySelector('[data-testid="stSidebarContent"]');
  const mainNeed = main ? main.scrollHeight : 0;
  const sideNeed = side ? side.scrollHeight : 0;
  return Math.max(mainNeed, sideNeed);
}
"""


class Shooter:
    """Съёмка кадров с нумерацией внутри одного сценария."""

    def __init__(self, page, slug: str, log: list[dict[str, str]]) -> None:
        self.page = page
        self.slug = slug
        self.log = log
        self.number = 0

    def shot(self, targets, title: str, *, tall: bool = False) -> Path:
        """Снять очередной кадр, подсветив ``targets``.

        ``targets`` — локатор или список локаторов. Номер шага рисуется на
        первом из них.
        """

        self.number += 1
        page = self.page
        if not isinstance(targets, (list, tuple)):
            targets = [targets]
        first = targets[0]
        first.scroll_into_view_if_needed(timeout=UI_TIMEOUT_MS)
        page.wait_for_timeout(250)

        limit = MAX_SHOT_HEIGHT if tall else 1100
        needed = int(page.evaluate(NEEDED_HEIGHT_JS))
        height = max(VIEWPORT["height"], min(needed + 16, limit))
        if height != VIEWPORT["height"]:
            page.set_viewport_size({"width": VIEWPORT["width"], "height": height})
            page.wait_for_timeout(300)
            first.scroll_into_view_if_needed(timeout=UI_TIMEOUT_MS)
            page.wait_for_timeout(250)

        items = []
        for index, target in enumerate(targets):
            box = target.bounding_box()
            if box is None:
                continue
            items.append(
                {
                    "x": round(box["x"] - 4, 1),
                    "y": round(box["y"] - 4, 1),
                    "w": round(box["width"] + 8, 1),
                    "h": round(box["height"] + 8, 1),
                    "color": ACCENT,
                    "number": self.number if index == 0 else 0,
                }
            )
        page.evaluate(HIGHLIGHT_JS, items)

        bottom = int(page.evaluate(CONTENT_BOTTOM_JS))
        clip_height = max(320, min(height, bottom + 24))
        path = IMG_ROOT / f"{self.slug}-{self.number:02d}.png"
        page.screenshot(
            path=str(path),
            clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": clip_height},
        )
        page.evaluate(CLEAR_JS)
        page.set_viewport_size(dict(VIEWPORT))
        page.wait_for_timeout(200)
        self.log.append({"image": path.name, "title": title})
        print(f"  {path.name}  {title}")
        return path


SCRIPT_STATE_JS = """
() => {
  const app = document.querySelector('[data-testid="stApp"]');
  return app ? app.getAttribute('data-test-script-state') : 'missing';
}
"""


def wait_idle(page) -> None:
    """Дождаться конца пересчёта Streamlit.

    Опорный признак — собственный атрибут Streamlit ``data-test-script-state``
    на контейнере приложения. Индикатор в панели инструментов для этого не
    годится: в релизной сборке ``toolbarMode = "minimal"`` и его нет вовсе.
    """

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
    """Виджет Streamlit по подписи, только среди видимых панелей вкладок."""

    return root.locator(f'[data-testid="{testid}"]:visible').filter(has_text=label).first


def set_number(root, label: str, value: str) -> None:
    field = widget(root, "stNumberInput", label).locator("input")
    field.click()
    field.press("Control+a")
    field.fill(value)
    field.press("Enter")


def set_text_area(root, label: str, value: str) -> None:
    field = widget(root, "stTextArea", label).locator("textarea")
    field.click()
    field.press("Control+a")
    field.fill(value)
    field.press("Control+Enter")


def set_text_input(root, label: str, value: str) -> None:
    field = widget(root, "stTextInput", label).locator("input")
    field.click()
    field.press("Control+a")
    field.fill(value)
    # Значение снимается по потере фокуса. Enter здесь нельзя: поля названий
    # стоят внутри st.form и Enter отправил бы форму раньше времени.
    field.press("Tab")


def set_selectbox(page, root, label: str, option: str) -> None:
    control = widget(root, "stSelectbox", label)
    field = control.locator('input[role="combobox"]').first
    field.scroll_into_view_if_needed(timeout=UI_TIMEOUT_MS)
    field.click()
    page.get_by_role("option").first.wait_for(timeout=UI_TIMEOUT_MS)
    page.get_by_role("option", name=option, exact=False).first.click()
    wait_idle(page)


def set_radio(root, label: str, option: str) -> None:
    control = widget(root, "stRadio", label)
    control.locator('[data-testid="stRadioOption"]').filter(has_text=option).first.click()


def set_checkbox(root, label: str, checked: bool) -> None:
    control = widget(root, "stCheckbox", label)
    box = control.locator('input[type="checkbox"]')
    if box.is_checked() == checked:
        return
    target = control.locator("label")
    (target.first if target.count() else control).click()


def set_multiselect(page, root, label: str, values: list[str]) -> None:
    control = widget(root, "stMultiSelect", label)
    clear = control.locator('[aria-label="Clear all"], [title="Clear all"]')
    if clear.count():
        clear.first.click()
        wait_idle(page)
    field = control.locator("input").first
    for value in values:
        field.click()
        field.fill(value)
        page.wait_for_timeout(250)
        page.get_by_role("option", name=value, exact=True).first.click()
        page.wait_for_timeout(150)
    page.keyboard.press("Escape")
    wait_idle(page)


def click_button(page, root, name: str, *, wait: bool = True):
    button = root.get_by_role("button", name=name, exact=True).first
    button.scroll_into_view_if_needed(timeout=UI_TIMEOUT_MS)
    button.click()
    if wait:
        wait_idle(page)
    return button


def open_tab(page, name: str) -> None:
    tab = page.get_by_role("tab", name=name, exact=True).first
    tab.scroll_into_view_if_needed(timeout=UI_TIMEOUT_MS)
    tab.click()
    wait_idle(page)


def expander(root, title: str):
    return root.locator('[data-testid="stExpander"]:visible').filter(has_text=title).first


def open_expander(page, root, title: str):
    block = expander(root, title)
    header = block.locator("summary, details > div").first
    if block.locator('[data-testid="stExpanderDetails"]:visible').count() == 0:
        header.click()
        wait_idle(page)
    return block


def set_database(page, label: str) -> None:
    set_selectbox(page, sidebar(page), "База материалов", label)


# ---------------------------------------------------------------------------
# Сценарии
# ---------------------------------------------------------------------------

DB_NI = "Никелевые сплавы"
DB_FE = "Стали и Fe-сплавы"
DB_AL = "Алюминиевые сплавы"


def scenario_start(page, log):
    """Первый запуск: ярлык, боковая панель, первый расчётный экран."""

    shooter = Shooter(page, "start", log)
    side = sidebar(page)

    shooter.shot(
        page.get_by_role("tab", name="Расчёты", exact=True).first,
        "Окно программы: заголовок и семь вкладок",
    )
    shooter.shot(
        widget(side, "stSelectbox", "База материалов"),
        "Боковая панель: выбор базы «Стали и Fe-сплавы»",
    )
    shooter.shot(
        widget(side, "stSelectbox", "Элемент-основа"),
        "Элемент-основа FE",
    )
    shooter.shot(
        widget(side, "stRadio", "Единицы состава"),
        "Единицы состава — массовые %",
    )
    set_text_area(side, "Добавки", "C=0.2, CR=11.5, NI=0.7")
    wait_idle(page)
    shooter.shot(
        widget(side, "stTextArea", "Добавки"),
        "Поле «Добавки»: C=0.2, CR=11.5, NI=0.7",
    )
    shooter.shot(
        widget(side, "stRadio", "Параллельный расчёт"),
        "Боковая панель: «Параллельный расчёт: авто»",
    )
    set_number(main_area(page), "Температура, °C", "700")
    wait_idle(page)
    shooter.shot(
        widget(main_area(page), "stNumberInput", "Температура, °C"),
        "Температура расчёта 700 °C на вкладке «Расчёты»",
    )


def scenario_raschety(page, log):
    """Расчёты: равновесие в точке, скан по температуре, набор фаз."""

    shooter = Shooter(page, "raschety", log)
    open_tab(page, "Расчёты")
    open_tab(page, "Одна температура")
    root = main_area(page)

    shooter.shot(
        page.get_by_role("tab", name="Расчёты", exact=True).first,
        "Вкладка «Расчёты», подвкладка «Одна температура»",
    )
    button = root.get_by_role("button", name="Рассчитать равновесие", exact=True).first
    shooter.shot(button, "Кнопка «Рассчитать равновесие»")
    button.click()
    root.get_by_text("Фазовые доли", exact=True).first.wait_for(timeout=CALC_TIMEOUT_MS)
    wait_idle(page)
    shooter.shot(
        root.locator('[data-testid="stDataFrame"]:visible').first,
        "Таблица устойчивых фаз и их долей",
        tall=True,
    )

    block = open_expander(page, root, "Управление фазами / метастабильный расчёт")
    shooter.shot(
        [
            widget(block, "stRadio", "Набор фаз"),
            root.get_by_text("Набор фаз:").first,
        ],
        "Переключатель «Быстрый набор / Все фазы базы» и строка «Набор фаз»",
        tall=True,
    )

    open_tab(page, "Температурный диапазон")
    root = main_area(page)
    set_number(root, "От, °C", "500")
    wait_idle(page)
    set_number(root, "До, °C", "900")
    wait_idle(page)
    set_number(root, "Шаг, °C", "100")
    wait_idle(page)
    shooter.shot(
        [
            widget(root, "stNumberInput", "От, °C"),
            widget(root, "stNumberInput", "До, °C"),
            widget(root, "stNumberInput", "Шаг, °C"),
        ],
        "Скан по температуре: 500–900 °C с шагом 100 °C",
    )
    button = root.get_by_role(
        "button", name="Построить график по температуре", exact=True
    ).first
    button.click()
    root.locator("img:visible").first.wait_for(timeout=CALC_TIMEOUT_MS)
    wait_idle(page)
    shooter.shot(
        root.locator("img:visible").first,
        "График долей фаз по температуре",
        tall=True,
    )
    shooter.shot(
        root.get_by_role("button", name="Excel", exact=True).first,
        "Выгрузка результата скана в Excel",
        tall=True,
    )


def scenario_diagrammy(page, log):
    """Диаграммы: бинарная Ni–Al."""

    shooter = Shooter(page, "diagrammy", log)
    set_database(page, DB_NI)
    open_tab(page, "Диаграммы")
    open_tab(page, "Бинарная T–X")
    root = main_area(page)

    shooter.shot(
        [
            widget(root, "stSelectbox", "Первый элемент системы"),
            widget(root, "stSelectbox", "Второй элемент"),
        ],
        "Система Ni–Al: первый и второй элементы",
    )
    set_number(root, "AL: до, %", "35")
    wait_idle(page)
    set_number(root, "Шаг по составу", "5")
    wait_idle(page)
    set_number(root, "Температура от, °C", "600")
    wait_idle(page)
    set_number(root, "Температура до, °C", "1600")
    wait_idle(page)
    set_number(root, "Шаг по температуре, °C", "50")
    wait_idle(page)
    shooter.shot(
        [
            widget(root, "stNumberInput", "AL: до, %"),
            widget(root, "stNumberInput", "Шаг по составу"),
            widget(root, "stNumberInput", "Шаг по температуре, °C"),
        ],
        "Диапазон по составу и по температуре, шаг сетки",
        tall=True,
    )
    button = root.get_by_role(
        "button", name="Построить диаграмму состояния", exact=True
    ).first
    shooter.shot(button, "Кнопка «Построить диаграмму состояния»", tall=True)
    button.click()
    root.locator("img:visible").first.wait_for(timeout=CALC_TIMEOUT_MS)
    wait_idle(page)
    shooter.shot(
        root.locator("img:visible").first,
        "Готовая бинарная диаграмма Ni–Al",
        tall=True,
    )
    shooter.shot(
        root.get_by_role("button", name="Скачать PNG", exact=True).first,
        "Выгрузка диаграммы в PNG",
        tall=True,
    )


def scenario_zatverdevanie(page, log):
    """Затвердевание: Scheil для Al–4Cu–1Mg."""

    shooter = Shooter(page, "zatverdevanie", log)
    set_database(page, DB_AL)
    side = sidebar(page)
    set_radio(side, "Единицы состава", "массовые %")
    wait_idle(page)
    set_text_area(side, "Добавки", "CU=4, MG=1")
    wait_idle(page)
    shooter.shot(
        widget(side, "stTextArea", "Добавки"),
        "База «Алюминиевые сплавы», состав Al–4Cu–1Mg в массовых %",
    )

    open_tab(page, "Затвердевание")
    root = main_area(page)
    set_radio(root, "Метод расчёта", "Только Scheil–Gulliver")
    wait_idle(page)
    shooter.shot(
        widget(root, "stRadio", "Метод расчёта"),
        "Метод расчёта — «Только Scheil–Gulliver»",
    )
    set_number(root, "Начальная температура, °C", "700")
    wait_idle(page)
    set_number(root, "Шаг охлаждения, °C", "10")
    wait_idle(page)
    shooter.shot(
        [
            widget(root, "stNumberInput", "Начальная температура, °C"),
            widget(root, "stNumberInput", "Шаг охлаждения, °C"),
        ],
        "Старт 700 °C, шаг охлаждения 10 °C",
    )
    button = root.get_by_role("button", name="Рассчитать затвердевание", exact=True).first
    button.click()
    page.get_by_role("tab", name="Сводка", exact=True).first.wait_for(
        timeout=CALC_TIMEOUT_MS
    )
    wait_idle(page)
    root = main_area(page)
    shooter.shot(
        root.locator('[data-testid="stDataFrame"]:visible').first,
        "Сводка: ликвидус, солидус и последовательность фаз",
        tall=True,
    )
    shooter.shot(
        root.locator("img:visible").first,
        "Кривая доли твёрдой фазы",
        tall=True,
    )
    open_tab(page, "Выгрузка")
    root = main_area(page)
    shooter.shot(
        root.get_by_role("button", name="Скачать Excel", exact=True).first,
        "Подвкладка «Выгрузка»: результат в Excel",
        tall=True,
    )


def scenario_energii(page, log):
    """Энергии: движущая сила FCC_A1 → GAMMA_PRIME для Ni–15Al."""

    shooter = Shooter(page, "energii", log)
    set_database(page, DB_NI)
    open_tab(page, "Энергии")
    open_tab(page, "Движущая сила")
    root = main_area(page)

    shooter.shot(
        widget(root, "stSelectbox", "Фаза, движущую силу которой рассчитываем"),
        "Фаза-продукт: GAMMA_PRIME",
    )
    set_multiselect(page, root, "Фазы исходного равновесия", ["FCC_A1"])
    root = main_area(page)
    shooter.shot(
        widget(root, "stMultiSelect", "Фазы исходного равновесия"),
        "Исходное равновесие — только матрица FCC_A1",
    )
    set_number(root, "Температура от, °C", "600")
    wait_idle(page)
    set_number(root, "Температура до, °C", "800")
    wait_idle(page)
    set_number(root, "Шаг температуры, °C", "50")
    wait_idle(page)
    shooter.shot(
        [
            widget(root, "stNumberInput", "Температура от, °C"),
            widget(root, "stNumberInput", "Температура до, °C"),
            widget(root, "stNumberInput", "Шаг температуры, °C"),
        ],
        "Окно температур 600–800 °C с шагом 50 °C",
    )
    button = root.get_by_role("button", name="Рассчитать движущую силу", exact=True).first
    button.click()
    root.locator("img:visible").first.wait_for(timeout=CALC_TIMEOUT_MS)
    wait_idle(page)
    shooter.shot(
        root.locator("img:visible").first,
        "График движущей силы; при 700 °C она положительна",
        tall=True,
    )
    shooter.shot(
        root.locator('[data-testid="stDataFrame"]:visible').last,
        "Таблица движущей силы по температурам",
        tall=True,
    )


def scenario_svoystva(page, log):
    """Свойства: плотность стали и модули по Фойгту–Ройссу–Хиллу для Ni."""

    shooter = Shooter(page, "svoystva", log)
    set_database(page, DB_FE)
    open_tab(page, "Свойства")
    open_tab(page, "Плотность")
    root = main_area(page)

    button = root.get_by_role(
        "button", name="Рассчитать плотность и объёмные доли", exact=True
    ).first
    shooter.shot(button, "Сталь Fe–0,2C–11,5Cr–0,7Ni: расчёт плотности при 700 °C")
    button.click()
    root.locator('[data-testid="stDataFrame"]:visible').first.wait_for(
        timeout=CALC_TIMEOUT_MS
    )
    wait_idle(page)
    root = main_area(page)
    shooter.shot(
        [
            root.locator('[data-testid="stMetric"]').first,
            root.locator('[data-testid="stDataFrame"]:visible').first,
        ],
        "Плотность сплава и покрытие физической базы",
        tall=True,
    )

    set_database(page, DB_NI)
    open_tab(page, "Свойства")
    open_tab(page, "Упругие свойства")
    root = main_area(page)
    button = root.get_by_role("button", name="Получить фазовые доли", exact=True).first
    shooter.shot(button, "Ni–15Al: шаг 1 — получить фазовые доли")
    button.click()
    root.locator('[data-testid="stDataFrame"]:visible').first.wait_for(
        timeout=CALC_TIMEOUT_MS
    )
    wait_idle(page)
    root = main_area(page)
    shooter.shot(
        root.locator('[data-testid="stDataFrame"]:visible').first,
        "Таблица модулей по фазам заполнена примером из библиотеки",
        tall=True,
    )
    button = root.get_by_role(
        "button", name="Рассчитать Voigt–Reuss–Hill", exact=True
    ).first
    button.click()
    root.locator('[data-testid="stMetric"]').first.wait_for(timeout=CALC_TIMEOUT_MS)
    wait_idle(page)
    root = main_area(page)
    metrics = root.locator('[data-testid="stMetric"]')
    shooter.shot(
        [metrics.nth(index) for index in range(metrics.count())],
        "E, G и ν по Хиллу для многофазного сплава",
        tall=True,
    )


def scenario_kinetika(page, log):
    """Кинетика: KWN γ′ и однофазная диффузия на никелевой базе."""

    shooter = Shooter(page, "kinetika", log)
    set_database(page, DB_NI)
    open_tab(page, "Кинетика")
    open_tab(page, "Выделения")
    root = main_area(page)

    # Учебный пресет (Ni–9,8Al–8,3Cr, 800 °C) на своей же паре фаз даёт
    # нулевую скорость зарождения: пересыщение слишком мало. Поэтому здесь
    # обычный пользовательский режим с составом Ni–15Al из боковой панели.
    shooter.shot(
        widget(root, "stSelectbox", "Набор исходных параметров"),
        "Режим «Параметры пользователя»: состав берётся из боковой панели",
    )
    shooter.shot(
        [
            widget(root, "stSelectbox", "Матричная фаза"),
            widget(root, "stSelectbox", "Фаза-выделение"),
        ],
        "Пара «матрица — выделение»: FCC_A1 и GAMMA_PRIME",
    )
    set_number(root, "Время выдержки, ч", "1")
    wait_idle(page)
    root = main_area(page)
    shooter.shot(
        [
            widget(root, "stNumberInput", "Температура, °C"),
            widget(root, "stNumberInput", "Время выдержки, ч"),
        ],
        "Короткая выдержка: 800 °C, 1 ч",
    )
    shooter.shot(
        [
            widget(root, "stNumberInput", "Межфазная энергия"),
            widget(root, "stNumberInput", "Молярный объём матрицы"),
            widget(root, "stNumberInput", "Плотность объёмных центров"),
        ],
        "Параметры KWN, которых нет в базе: γ, Vm и число центров зарождения",
        tall=True,
    )
    button = root.get_by_role(
        "button", name="Рассчитать кинетику выделений", exact=True
    ).first
    button.click()
    page.get_by_role("tab", name="Итоги", exact=True).first.wait_for(
        timeout=CALC_TIMEOUT_MS
    )
    wait_idle(page)
    root = main_area(page)
    shooter.shot(
        root.locator("img:visible").first,
        "Доля и средний размер частиц γ′ во времени",
        tall=True,
    )

    open_tab(page, "Диффузия и гомогенизация")
    open_tab(page, "Однофазная пара")
    root = main_area(page)
    shooter.shot(
        [
            widget(root, "stTextArea", "Левая сторона"),
            widget(root, "stTextArea", "Правая сторона"),
        ],
        "Диффузионная пара: составы левой и правой половин",
        tall=True,
    )
    # Сетка и время остаются штатными: на 2000 мкм и 80 ячейках численная
    # проверка сохранения состава проходит, а на 200 мкм тот же шаг по
    # времени уже даёт слишком большую невязку баланса.
    shooter.shot(
        [
            widget(root, "stNumberInput", "Температура выдержки, °C"),
            widget(root, "stNumberInput", "Длина области, мкм"),
            widget(root, "stNumberInput", "Время, ч"),
        ],
        "Режим выдержки: 1200 °C, 100 ч, 80 ячеек на 2000 мкм",
        tall=True,
    )
    button = root.get_by_role(
        "button", name="Рассчитать однофазную диффузию", exact=True
    ).first
    button.click()
    root.locator('[data-testid="stMetric"]').first.wait_for(timeout=CALC_TIMEOUT_MS)
    wait_idle(page)
    root = main_area(page)
    shooter.shot(
        root.locator("img:visible").first,
        "Профиль состава после выдержки",
        tall=True,
    )


def scenario_proekty(page, log):
    """Проекты и данные: библиотека, пакетный расчёт, сохранение проекта."""

    shooter = Shooter(page, "proekty", log)
    set_database(page, DB_NI)
    open_tab(page, "Проекты и данные")
    open_tab(page, "Марки и составы")
    root = main_area(page)

    set_text_input(root, "Название марки или состава", "Опытный Ni–15Al")
    wait_idle(page)
    root = main_area(page)
    # Галочка нужна только для повторных прогонов скрипта поверх уже
    # сохранённой записи: на чистом состоянии она ничего не меняет.
    set_checkbox(root, "Разрешить обновить одноимённую пользовательскую запись", True)
    wait_idle(page)
    root = main_area(page)
    shooter.shot(
        [
            widget(root, "stTextInput", "Название марки или состава"),
            root.get_by_role("button", name="Сохранить текущий состав", exact=True).first,
        ],
        "Сохранение текущего состава в библиотеку",
        tall=True,
    )
    click_button(page, root, "Сохранить текущий состав")
    root = main_area(page)
    shooter.shot(
        root.locator('[data-testid="stDataFrame"]:visible').last,
        "Запись появилась в списке «Доступные записи»",
        tall=True,
    )
    set_selectbox(page, root, "Выберите запись", "Опытный Ni–15Al")
    root = main_area(page)
    button = root.get_by_role(
        "button", name="Загрузить состав в программу", exact=True
    ).first
    shooter.shot(
        [widget(root, "stSelectbox", "Выберите запись"), button],
        "Возврат состава из библиотеки в боковую панель",
        tall=True,
    )
    button.click()
    wait_idle(page)

    open_tab(page, "Проекты и данные")
    open_tab(page, "Пакетный расчёт")
    root = main_area(page)
    button = root.get_by_role("button", name="Скачать шаблон CSV", exact=True).first
    shooter.shot(button, "Шаблон таблицы составов")
    button.click()
    wait_idle(page)
    root = main_area(page)

    batch_csv = STATE_ROOT / "guide_batch.csv"
    batch_csv.write_text(
        "Название,База,Основа,Единицы,\"Температура, °C\",Добавки,"
        "Режим стали,\"Давление, Па\",Фазы\n"
        "Ni–12Al,ni,NI,ат.%,700,AL=12,,101325,\n"
        "Ni–15Al,ni,NI,ат.%,700,AL=15,,101325,\n"
        "Ni–18Al,ni,NI,ат.%,700,AL=18,,101325,\n",
        encoding="utf-8-sig",
    )
    # На вкладке три загрузчика (библиотека, пакет, проект), и все три —
    # скрытые input[type=file], поэтому выбирать нужно по подписи виджета.
    widget(root, "stFileUploader", "Файл составов").locator(
        'input[type="file"]'
    ).set_input_files(str(batch_csv))
    root.get_by_text("Предварительный просмотр", exact=True).first.wait_for(
        timeout=CALC_TIMEOUT_MS
    )
    wait_idle(page)
    root = main_area(page)
    shooter.shot(
        root.locator('[data-testid="stFileUploader"]:visible').first,
        "Загрузка файла с тремя составами",
        tall=True,
    )
    button = root.get_by_role("button", name="Рассчитать все составы", exact=True).first
    button.click()
    wait_idle(page)
    root = main_area(page)
    shooter.shot(
        root.locator('[data-testid="stDataFrame"]:visible').last,
        "Сводка пакетного расчёта по трём составам",
        tall=True,
    )

    open_tab(page, "Проекты и данные")
    open_tab(page, "Проекты и история")
    root = main_area(page)
    set_text_input(root, "Название проекта", "Ni–Al, подбор старения")
    wait_idle(page)
    root = main_area(page)
    set_checkbox(root, "Разрешить заменить одноимённый локальный проект", True)
    wait_idle(page)
    root = main_area(page)
    shooter.shot(
        [
            widget(root, "stTextInput", "Название проекта"),
            root.get_by_role(
                "button", name="Сохранить проект в папке ThermoGar", exact=True
            ).first,
        ],
        "Сохранение проекта: контекст и настройки разделов",
        tall=True,
    )
    click_button(page, root, "Сохранить проект в папке ThermoGar")
    root = main_area(page)
    shooter.shot(
        root.locator('[data-testid="stAlert"]:visible').first,
        "Проект сохранён в папке ThermoGar",
        tall=True,
    )


SCENARIOS = {
    "start": scenario_start,
    "raschety": scenario_raschety,
    "diagrammy": scenario_diagrammy,
    "zatverdevanie": scenario_zatverdevanie,
    "energii": scenario_energii,
    "svoystva": scenario_svoystva,
    "kinetika": scenario_kinetika,
    "proekty": scenario_proekty,
}

# Порядок съёмки отличается от порядка вкладок: базы переключаются один раз,
# иначе каждый переход сбрасывает результаты и стоит лишнюю минуту.
SCENARIO_ORDER = [
    "start",
    "raschety",
    "svoystva",
    "zatverdevanie",
    "diagrammy",
    "energii",
    "kinetika",
    "proekty",
]


# ---------------------------------------------------------------------------
# Сжатие кадров и сборка HTML
# ---------------------------------------------------------------------------


def compress_images(paths: list[Path]) -> None:
    from PIL import Image

    for path in paths:
        with Image.open(path) as image:
            frame = image.convert("RGB")
            if frame.width > VIEWPORT["width"]:
                height = round(frame.height * VIEWPORT["width"] / frame.width)
                frame = frame.resize((VIEWPORT["width"], height), Image.LANCZOS)
            frame = frame.quantize(colors=192, method=Image.MEDIANCUT, dither=Image.NONE)
            frame.save(path, format="PNG", optimize=True)


HTML_CSS = """
:root { color-scheme: light; }
body {
  margin: 0 auto; padding: 32px 24px 64px; max-width: 1000px;
  background: #FFFFFF; color: #2A2722;
  font: 17px/1.6 "Segoe UI", Arial, Helvetica, sans-serif;
}
h1 { font-size: 32px; margin: 8px 0 24px; }
h2 { font-size: 25px; margin: 44px 0 12px; border-bottom: 2px solid #D8D4CC;
     padding-bottom: 6px; }
h3 { font-size: 20px; margin: 30px 0 8px; color: #133B8B; }
p { margin: 8px 0 14px; }
a { color: #133B8B; }
img { max-width: 100%; height: auto; display: block; margin: 10px 0 18px;
      border: 1px solid #D8D4CC; border-radius: 6px; }
table { border-collapse: collapse; margin: 12px 0 20px; }
th, td { border: 1px solid #D8D4CC; padding: 6px 12px; text-align: left; }
th { background: #F1EFEA; }
code { background: #F1EFEA; padding: 1px 5px; border-radius: 4px;
       font-family: Consolas, "Courier New", monospace; font-size: 15px; }
hr { border: 0; border-top: 1px solid #D8D4CC; margin: 40px 0; }
.toc { background: #F1EFEA; border-radius: 8px; padding: 4px 24px; }
"""


def inline_images(html: str, base: Path) -> str:
    import re

    def replace(match: "re.Match[str]") -> str:
        source = match.group(1)
        if source.startswith(("http:", "https:", "data:")):
            return match.group(0)
        path = (base / source).resolve()
        if not path.exists():
            return match.group(0)
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        payload = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'src="data:{mime};base64,{payload}"'

    return re.sub(r'src="([^"]+)"', replace, html)


def inline_links(html: str) -> str:
    """Перевести ссылки между файлами руководства на якоря одной страницы."""

    import re

    html = re.sub(r'href="README\.md#', 'href="#', html)
    html = re.sub(r'href="README\.md"', 'href="#README"', html)
    return re.sub(r'href="(\d\d-[a-z]+)\.md((?:#[^"]*)?)"', r'href="#\1"', html)


def build_html() -> Path:
    import markdown

    order = ["README.md"] + sorted(
        path.name
        for path in GUIDE_ROOT.glob("*.md")
        if path.name != "README.md"
    )
    from markdown.extensions.toc import slugify_unicode

    # Обычный slugify выбрасывает кириллицу, и все заголовки получают якоря
    # вида «1», «2», а ссылка «#первый-запуск» перестаёт работать.
    converter = markdown.Markdown(
        extensions=["tables", "toc", "sane_lists"],
        extension_configs={"toc": {"slugify": slugify_unicode}},
    )
    parts: list[str] = []
    for name in order:
        source = GUIDE_ROOT / name
        if not source.exists():
            continue
        converter.reset()
        body = converter.convert(source.read_text(encoding="utf-8"))
        parts.append(f'<section id="{source.stem}">\n{body}\n</section>')
    document = (
        "<!DOCTYPE html>\n<html lang=\"ru\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{HTML_TITLE}</title>\n<style>{HTML_CSS}</style>\n"
        "</head>\n<body>\n"
        + "\n<hr>\n".join(parts)
        + "\n</body>\n</html>\n"
    )
    document = inline_links(inline_images(document, GUIDE_ROOT))
    target = GUIDE_ROOT / HTML_NAME
    target.write_text(document, encoding="utf-8")
    print(f"HTML: {target.relative_to(REPO_ROOT)} — {target.stat().st_size / 1e6:.1f} МБ")
    return target


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------


def run_scenarios(names: list[str], port: int) -> list[dict[str, str]]:
    from playwright.sync_api import sync_playwright

    log: list[dict[str, str]] = []
    IMG_ROOT.mkdir(parents=True, exist_ok=True)
    for name in names:
        for stale in IMG_ROOT.glob(f"{name}-*.png"):
            stale.unlink()

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=dict(VIEWPORT),
            device_scale_factor=1,
            color_scheme="light",
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            accept_downloads=True,
        )
        context.set_default_timeout(UI_TIMEOUT_MS)
        page = context.new_page()
        page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded")
        page.get_by_role("tab", name="Расчёты", exact=True).wait_for(
            timeout=CALC_TIMEOUT_MS
        )
        wait_idle(page)
        expand = page.locator('[data-testid="stExpandSidebarButton"]')
        if expand.count():
            expand.first.click()
            wait_idle(page)
        page.wait_for_timeout(500)

        for name in names:
            print(f"[{name}]")
            started = time.monotonic()
            SCENARIOS[name](page, log)
            print(f"  — {time.monotonic() - started:.0f} с")
        browser.close()
    return log


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8601)
    parser.add_argument("--only", default="")
    parser.add_argument("--html", action="store_true", help="только пересобрать HTML")
    parser.add_argument("--no-html", action="store_true")
    parser.add_argument("--keep-server", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    if arguments.html:
        build_html()
        return 0

    names = SCENARIO_ORDER
    if arguments.only:
        requested = [item.strip() for item in arguments.only.split(",") if item.strip()]
        unknown = [item for item in requested if item not in SCENARIOS]
        if unknown:
            print(f"Неизвестные сценарии: {', '.join(unknown)}", file=sys.stderr)
            return 2
        names = [name for name in SCENARIO_ORDER if name in requested]

    process: subprocess.Popen[bytes] | None = None
    if arguments.keep_server:
        if not app_is_ready(arguments.port):
            print(f"На порту {arguments.port} нет готового приложения.", file=sys.stderr)
            return 2
    else:
        if port_is_open(arguments.port):
            print(f"Порт {arguments.port} занят.", file=sys.stderr)
            return 2
        prepare_state_root()
        print(f"Запуск приложения на порту {arguments.port}…")
        process = start_app(arguments.port)

    started = time.monotonic()
    try:
        log = run_scenarios(names, arguments.port)
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()

    paths = [IMG_ROOT / item["image"] for item in log]
    compress_images(paths)
    total = sum(path.stat().st_size for path in IMG_ROOT.glob("*.png"))
    print(
        f"Кадров: {len(log)} за {time.monotonic() - started:.0f} с; "
        f"папка img: {total / 1e6:.1f} МБ"
    )
    (IMG_ROOT / "_manifest.json").write_text(
        json.dumps(
            {
                "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "frames": log,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if not arguments.no_html:
        build_html()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
