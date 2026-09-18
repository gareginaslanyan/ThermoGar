"""Снимки выпуска 0.4.2 (задача 17-Д, п. 4).

Обёртка над ``tools/make_guide_screens.py``: берёт оттуда запуск приложения,
съёмку и сборку HTML, добавляет один сценарий «soobshcheniya» с сообщениями
0.4.2 (места 15-П и 15-Щ) и пересъёмку «svoystva» (шаги 4 и 5 главы 05).
Сам ``tools/make_guide_screens.py`` не меняется.

Состояние приложения — ``THERMOGAR_STATE_ROOT`` задачи 17-Д, вне
``%LOCALAPPDATA%``. Манифест кадров дописывается, а не перезаписывается.

Запуск:
    .venv-windows/Scripts/python.exe -X utf8 results/wave17_d/guide_screens_042.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import make_guide_screens as mgs  # noqa: E402

mgs.STATE_ROOT = ROOT / "results" / "validation" / "wave17_d_state"
OUT = Path(__file__).resolve().parent / "screens"

# Сплав 718 и входы случая 15-В (700 °C, 95 мДж/м²) — см. main(): молярные
# объёмы и N0 считаются тем же study_wave15_v_718.case_arguments.
ALLOY_718 = "NI=54.2, CR=17.9, NB=5.3, MO=2.99, TI=0.97, AL=0.5"
# Узел BL-24 (15-З, п. 4): CONTROL_WT 12-2 с Si 5 масс. %, 750 °C.
EK199_SI5 = "C=0.005, SI=5, MN=0.5, S=0.02, CR=23.5, MO=13, NB=0.06, AL=0.25, TI=0.1, FE=0.5"

_original_shot = mgs.Shooter.shot


def _shot_with_version(self, targets, title, *, tall=False):
    """Боковая панель — в начало, чтобы в кадр попала подпись «ThermoGar 0.4.2»."""

    self.page.evaluate(
        "() => { const s = document.querySelector('[data-testid=\"stSidebarContent\"]');"
        " if (s) { s.scrollTop = 0; } }"
    )
    return _original_shot(self, targets, title, tall=tall)


mgs.Shooter.shot = _shot_with_version

KWN_718: dict[str, str] = {}
NAMES = sys.argv[1:] or ["svoystva", "soobshcheniya"]
READINGS: dict[str, object] = {}


def alerts(root, text: str):
    return root.locator('[data-testid="stAlert"]:visible').filter(has_text=text).first


def set_composition(page, balance: str, units: str, additions: str) -> None:
    side = mgs.sidebar(page)
    # Сначала добавки: основа не предлагается, пока стоит среди добавок.
    mgs.set_text_area(side, "Добавки", additions)
    mgs.wait_idle(page)
    # Список основ длинный и виртуализован: значение вводится в поле.
    field = mgs.widget(side, "stSelectbox", "Элемент-основа").locator('input[role="combobox"]').first
    field.click()
    field.fill(balance)
    page.get_by_role("option", name=balance, exact=True).first.click()
    mgs.wait_idle(page)
    mgs.set_radio(side, "Единицы состава", units)
    mgs.wait_idle(page)
    mgs.set_text_area(side, "Добавки", additions)
    mgs.wait_idle(page)


def kwn_inputs(page, values: dict[str, str]) -> None:
    for label, value in values.items():
        mgs.set_number(mgs.main_area(page), label, value)
        mgs.wait_idle(page)


def scenario_soobshcheniya(page, log):
    shooter = mgs.Shooter(page, "soobshcheniya", log)

    # 1. Быстрый набор: предупреждение и раскрытый полный перечень (BL-8).
    mgs.set_database(page, mgs.DB_FE)
    set_composition(page, "FE", "массовые %", "C=0.2, CR=11.5, NI=0.7")
    mgs.open_tab(page, "Расчёты")
    mgs.open_tab(page, "Одна температура")
    root = mgs.main_area(page)
    mgs.set_number(root, "Температура, °C", "700")
    mgs.wait_idle(page)
    block = mgs.open_expander(page, root, "Управление фазами / метастабильный расчёт")
    mgs.set_radio(block, "Набор фаз", "Быстрый набор")
    mgs.wait_idle(page)
    root = mgs.main_area(page)
    block = mgs.expander(root, "Управление фазами / метастабильный расчёт")
    # Блок вложен в «Управление фазами»; искать по своему заголовку.
    full = block.locator('[data-testid="stExpander"]').filter(
        has=page.locator("summary", has_text="Все фазы вне быстрого набора")
    ).last
    full.locator("summary").first.click()
    mgs.wait_idle(page)
    shooter.shot(
        [alerts(block, "Быстрый набор не рассматривает"), full],
        "Предупреждение о фазах вне быстрого набора и раскрытый полный перечень",
        tall=True,
    )

    # 2. Пустое решение pycalphad (BL-24).
    mgs.set_database(page, mgs.DB_NI)
    set_composition(page, "NI", "массовые %", EK199_SI5)
    mgs.open_tab(page, "Расчёты")
    mgs.open_tab(page, "Одна температура")
    root = mgs.main_area(page)
    mgs.set_number(root, "Температура, °C", "750")
    mgs.wait_idle(page)
    button = root.get_by_role("button", name="Рассчитать равновесие", exact=True).first
    button.click()
    root.get_by_text("не найдено").first.wait_for(timeout=mgs.CALC_TIMEOUT_MS)
    mgs.wait_idle(page)
    message = alerts(mgs.main_area(page), "не найдено")
    READINGS["empty_solution"] = message.inner_text()
    shooter.shot([message, button], "Равновесие при 750 °C не найдено", tall=True)

    # 3–4. Остановка расчёта выделений по составу матрицы (BL-35), 718.
    set_composition(page, "FE", "массовые %", ALLOY_718)
    mgs.open_tab(page, "Кинетика")
    mgs.open_tab(page, "Выделения")
    root = mgs.main_area(page)
    mgs.set_selectbox(page, root, "Матричная фаза", "FCC_A1")
    mgs.set_selectbox(page, mgs.main_area(page), "Фаза-выделение", "GAMMA_DP")
    kwn_inputs(page, KWN_718)
    root = mgs.main_area(page)
    root.get_by_role("button", name="Рассчитать кинетику выделений", exact=True).first.click()
    page.get_by_role("tab", name="Итоги", exact=True).first.wait_for(timeout=mgs.CALC_TIMEOUT_MS)
    mgs.wait_idle(page)
    root = mgs.main_area(page)
    stop = alerts(root, "Расчёт остановлен")
    READINGS["stop_note"] = stop.inner_text()
    shooter.shot(
        [stop, alerts(root, "Одна или несколько внутренних проверок")],
        "Текст остановки расчёта выделений над вкладками",
        tall=True,
    )
    shooter.shot(
        root.locator('[data-testid="stDataFrame"]:visible').last,
        "Таблица проверок: «Состав матрицы допустим» — ошибка",
        tall=True,
    )

    # 5. Зародыш крупнее начальной сетки (BL-26), постановка 13-Ф.
    set_composition(page, "NI", "атомные %", "AL=9.8, CR=8.3")
    mgs.open_tab(page, "Кинетика")
    mgs.open_tab(page, "Выделения")
    root = mgs.main_area(page)
    mgs.set_selectbox(page, root, "Матричная фаза", "FCC_A1")
    mgs.set_selectbox(page, mgs.main_area(page), "Фаза-выделение", "GAMMA_PRIME")
    kwn_inputs(
        page,
        {
            "Температура, °C": "800",
            "Время выдержки, ч": "0.000001",
            "Межфазная энергия, Дж/м²": "0.023",
            "Молярный объём матрицы, см³/моль": "6.5662724928",
            "Молярный объём выделения, см³/моль": "6.5662724928",
            "Плотность объёмных центров, 1/м³": "1e30",
        },
    )
    mgs.open_expander(page, mgs.main_area(page), "Численная сетка размеров")
    kwn_inputs(
        page,
        {"Минимальный радиус, нм": "0.05", "Начальный максимальный радиус, нм": "0.5"},
    )
    root = mgs.main_area(page)
    root.get_by_role("button", name="Рассчитать кинетику выделений", exact=True).first.click()
    page.get_by_role("tab", name="Итоги", exact=True).first.wait_for(timeout=mgs.CALC_TIMEOUT_MS)
    mgs.wait_idle(page)
    warning = alerts(mgs.main_area(page), "больше начального максимального радиуса")
    READINGS["nucleus_warning"] = warning.inner_text()
    shooter.shot(warning, "Зародыш крупнее начальной сетки размеров", tall=True)


def read_svoystva(page, log):
    mgs.scenario_svoystva(page, log)
    metrics = mgs.main_area(page).locator('[data-testid="stMetric"]')
    READINGS["vrh_metrics"] = [metrics.nth(i).inner_text() for i in range(metrics.count())]


def main() -> int:
    import study_wave15_v_718 as study

    arguments = study.case_arguments(700.0, 95.0, study.GRID)
    KWN_718.update(
        {
            "Температура, °C": "700",
            "Время выдержки, ч": "100",
            "Межфазная энергия, Дж/м²": f"{arguments['gamma']:.6g}",
            "Молярный объём матрицы, см³/моль": f"{arguments['matrix_vm']:.6g}",
            "Молярный объём выделения, см³/моль": f"{arguments['precip_vm']:.6g}",
            "Плотность объёмных центров, 1/м³": f"{arguments['bulk_n0']:.6e}",
        }
    )
    READINGS["kwn_718_inputs"] = dict(KWN_718)

    mgs.SCENARIOS["soobshcheniya"] = scenario_soobshcheniya
    mgs.SCENARIOS["svoystva"] = read_svoystva
    OUT.mkdir(exist_ok=True)
    port = 8617
    if mgs.port_is_open(port):
        print(f"Порт {port} занят.", file=sys.stderr)
        return 2
    mgs.prepare_state_root()
    process = mgs.start_app(port)
    started = time.monotonic()
    try:
        log = mgs.run_scenarios(NAMES, port)
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except Exception:
            process.kill()

    mgs.compress_images([mgs.IMG_ROOT / item["image"] for item in log])
    manifest_path = mgs.IMG_ROOT / "_manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    taken = {item["image"]: item for item in log}
    known = {item["image"] for item in manifest["frames"]}
    frames = [taken.get(item["image"], item) for item in manifest["frames"]]
    frames += [item for item in log if item["image"] not in known]
    manifest = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "frames": frames}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    OUT.mkdir(exist_ok=True)
    (OUT / "readings.json").write_text(
        json.dumps({"frames": log, "readings": READINGS}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Кадров: {len(log)} за {time.monotonic() - started:.0f} с")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
