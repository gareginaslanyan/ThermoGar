"""21-Х, ШАГ 4: время расчёта сценария kinetika (Ni, 800 °C, 1 ч, умолчания раздела).

Прогон ``tools/make_guide_screens.py --only kinetika`` с перезапуском
приложения; кадры — во временную папку (``docs/guide/img`` не трогается).
Время — от нажатия «Рассчитать кинетику выделений» (вход в первый
``view_ready`` вида «Кинетика выделений») до конца ``wait_idle`` после него.
Там же — текст основной области и снимок страницы (сводка над графиками).

Запуск из корня дерева:

    python -X utf8 results/wave21_x/scripts/zamer_kinetika.py <папка кадров> [порт]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import make_guide_screens as m  # noqa: E402

out = Path(sys.argv[1])
port = sys.argv[2] if len(sys.argv) > 2 else "8602"
out.mkdir(parents=True, exist_ok=True)
m.IMG_ROOT = out

marks: dict[str, float] = {}
_view_ready = m.view_ready
_wait_idle = m.wait_idle


def view_ready(page, group, option, *args, **kwargs):
    if group == "Кинетика выделений" and "click" not in marks:
        marks["click"] = time.monotonic()
    _view_ready(page, group, option, *args, **kwargs)
    if group == "Кинетика выделений" and "view" not in marks:
        marks["view"] = time.monotonic()


def wait_idle(page):
    _wait_idle(page)
    if "view" in marks and "idle" not in marks:
        marks["idle"] = time.monotonic()
        # Сводка над графиками kinetika-05 (в кадр не входит) — текстом и снимком.
        (out / "svodka.txt").write_text(m.main_area(page).inner_text(), encoding="utf-8")
        tables = m.main_area(page).locator('[data-testid="stDataFrame"]:visible')
        for index in range(tables.count()):
            tables.nth(index).screenshot(path=str(out / f"svodka_{index}.png"))


m.view_ready = view_ready
m.wait_idle = wait_idle
sys.argv = [sys.argv[0], "--only", "kinetika", "--no-html", "--port", port]
code = m.main()
result = {
    "view_s": round(marks["view"] - marks["click"], 1),
    "idle_s": round(marks["idle"] - marks["click"], 1),
}
print(json.dumps(result, ensure_ascii=False))
sys.exit(code)
