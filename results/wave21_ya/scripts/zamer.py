"""Замер английских надписей Streamlit 1.62 в ThermoGar (21-Я, BL-79).

Сценарий Playwright для ШАГОВ 1 и 5 задания tasks/WAVE21_YA_OPUS.md. Приложение
уже запущено (streamlit run app/ThermoGar_app.py, своя папка состояния) на
порту ``--port``. В светлой и тёмной теме сценарий проходит места с надписями
самого Streamlit, снимает кадры и записывает getComputedStyle текста
(font-size, font-weight, color, line-height) и его ::after.

Запуск:

    python -X utf8 results/wave21_ya/scripts/zamer.py --phase do --port 8631 \
        --tmp <временная папка вне дерева>

``--phase do`` — до правки (zamer_do.json, kadry/do_*.png),
``--phase posle`` — после (zamer_posle.json, kadry/posle_*.png).
Кнопки и подписи ищутся как в tools/make_guide_screens.py.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPO_ROOT = OUT.parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import make_guide_screens as g  # noqa: E402

UPLOADERS = (
    ("alloy_library_uploader", "Марки и составы", "Импортировать библиотеку JSON", ".json"),
    ("batch_file_uploader", "Пакетный расчёт", "Файл составов", ".csv"),
    ("project_uploader", "Проекты и история", "Импортировать проект", ".json"),
)

DROPZONE = '[data-testid="stFileUploaderDropzone"]'
SEL_BUTTON = DROPZONE + ' button[data-testid="stBaseButton-secondary"] [data-testid="stMarkdownContainer"] p'
SEL_INSTRUCTIONS = '[data-testid="stFileUploaderDropzoneInstructions"] span'
SEL_DRAG = DROPZONE + " > div:not([data-testid]) > span"
SEL_SIZE = '[data-testid="stFileChipName"] + *'
SEL_TIP_FILE = '[data-testid="stTooltipErrorContent"]:not(:has([data-testid="stMarkdownContainer"]))'
SEL_TIP_NUMBER = '[data-testid="stTooltipErrorContent"]:has([data-testid="stMarkdownContainer"]) p'
SEL_NO_RESULTS = '[role="option"][style*="display: contents"] > span'
SEL_SELECT_ALL = '[role="option"][data-key="__select_all__"] > div'
SEL_SELECT_MATCHES = '[role="option"][data-key="__select_matches__"] > div'
SEL_OPTION = '[role="option"]:not([data-key^="__"]):not([style*="display: contents"]) > div'
SEL_TOOLTIP = '[data-testid="stTooltipContent"]'

ENERGY_LABEL = "Фазы для сравнения — не более восьми"
NUMBER_LABEL = "Шаг поиска границ, ат.% (0.5–10)"

MEASURE_JS = """
(selector) => {
  const pick = (s) => ({
    content: s.content,
    display: s.display,
    fontSize: s.fontSize,
    fontWeight: s.fontWeight,
    color: s.color,
    lineHeight: s.lineHeight,
  });
  return Array.from(document.querySelectorAll(selector)).map((e) => {
    const r = e.getBoundingClientRect();
    return {
      text: e.innerText,
      visible: r.width > 0 && r.height > 0,
      box: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
      element: pick(getComputedStyle(e)),
      after: pick(getComputedStyle(e, '::after')),
    };
  });
}
"""

PLACEHOLDER_JS = """
(e) => {
  const input = e.querySelector('input');
  const s = getComputedStyle(input, '::placeholder');
  return {
    text: input.getAttribute('placeholder'),
    visible: true,
    element: {
      content: '', display: '', fontSize: s.fontSize, fontWeight: s.fontWeight,
      color: s.color, lineHeight: s.lineHeight,
    },
    after: null,
  };
}
"""

DRAG_JS = """
() => {
  const dt = new DataTransfer();
  dt.items.add(new File(['x'], 'a.csv', {type: 'text/csv'}));
  return dt;
}
"""


class Run:
    def __init__(self, page, phase: str, theme: str) -> None:
        self.page = page
        self.phase = phase
        self.theme = theme
        self.records: list[dict] = []
        self.frames: list[str] = []

    def shot(self, name: str, target=None) -> str:
        if target is not None:
            try:
                target.scroll_into_view_if_needed(timeout=10_000)
            except Exception:
                pass
        self.page.wait_for_timeout(300)
        path = OUT / "kadry" / f"{self.phase}_{self.theme}_{name}.png"
        self.page.screenshot(path=str(path))
        self.frames.append(path.name)
        return path.name

    def measure(self, place: str, where: str, english: str, selector: str, frame: str,
                note: str = "") -> list[dict]:
        found = self.page.evaluate(MEASURE_JS, selector)
        self.records.append(
            {
                "theme": self.theme,
                "place": place,
                "where": where,
                "english": english,
                "selector": selector,
                "frame": frame,
                "found": found,
                "note": note,
            }
        )
        visible = [item for item in found if item["visible"]]
        text = visible[0]["text"] if visible else (found[0]["text"] if found else None)
        print(f"  {place:28s} {len(found)} найд., {len(visible)} видим.: {text!r}")
        return found

    def note(self, place: str, where: str, text: str, frame: str) -> None:
        self.records.append(
            {"theme": self.theme, "place": place, "where": where, "english": "",
             "selector": "", "frame": frame, "found": [], "note": text}
        )
        print(f"  {place:28s} {text}")


def open_uploader(page, tab: str, key: str):
    g.open_tab(page, "Проекты и данные")
    g.open_tab(page, tab)
    box = page.locator(f".st-key-{key}")
    box.wait_for(timeout=g.UI_TIMEOUT_MS)
    box.scroll_into_view_if_needed()
    return box


def remove_files(page, box) -> None:
    for _ in range(3):
        remove = box.locator('[data-testid="stFileChipDeleteBtn"] button')
        if not remove.count():
            return
        remove.first.click()
        g.wait_idle(page)


def visible_alerts(page) -> list[str]:
    return [
        text.strip()
        for text in page.locator('[data-testid="stAlert"]:visible').all_inner_texts()
    ]


def uploaders(run: Run, tmp: Path, big: Path) -> None:
    page = run.page
    for key, tab, label, suffix in UPLOADERS:
        short = key.split("_")[0]
        scope = f".st-key-{key} "
        box = open_uploader(page, tab, key)
        remove_files(page, box)
        where = f"Проекты и данные → {tab} → «{label}»"

        frame = run.shot(f"{short}_pustoy", box)
        run.measure(f"{short}: кнопка", where, "Upload", scope + SEL_BUTTON, frame)
        run.measure(f"{short}: строка", where, "200MB per file • …",
                    scope + SEL_INSTRUCTIONS, frame)

        zone = box.locator(DROPZONE)
        data = page.evaluate_handle(DRAG_JS)
        zone.dispatch_event("dragenter", {"dataTransfer": data})
        zone.dispatch_event("dragover", {"dataTransfer": data})
        page.wait_for_timeout(400)
        frame = run.shot(f"{short}_peretaskivanie", box)
        run.measure(f"{short}: перетаскивание", where, "Drag and drop a file here",
                    scope + SEL_DRAG, frame)
        zone.dispatch_event("dragleave", {"dataTransfer": data})
        page.wait_for_timeout(300)

        field = box.locator('input[type="file"]')
        if key == "batch_file_uploader":
            csv_path = tmp / "sostavy.csv"
            field.set_input_files(str(csv_path))
            g.wait_idle(page)
            box.locator('[data-testid="stFileChip"]').first.wait_for()
            frame = run.shot(f"{short}_csv", box)
            run.measure(f"{short}: размер файла", where, "132.0B",
                        scope + SEL_SIZE, frame)
            remove_files(page, box)

        field.set_input_files(str(tmp / "nevernyy.txt"))
        page.wait_for_timeout(800)
        box.locator('[data-testid="stFileChip"]').first.wait_for()
        box.locator('[data-testid="stTooltipErrorHoverTarget"]').first.hover()
        page.locator('[data-testid="stTooltipErrorContent"]').first.wait_for()
        page.wait_for_timeout(400)
        frame = run.shot(f"{short}_txt", box)
        run.measure(f"{short}: .txt подсказка", where, "text/plain files are not allowed.",
                    SEL_TIP_FILE, frame)
        page.mouse.move(5, 5)
        remove_files(page, box)

        field.set_input_files(str(big.with_suffix(suffix)))
        page.wait_for_timeout(1500)
        g.wait_idle(page)
        chip = box.locator('[data-testid="stFileChip"]')
        chip.first.wait_for(timeout=g.CALC_TIMEOUT_MS)
        invalid = chip.first.get_attribute("aria-invalid") == "true"
        tip_text = ""
        if invalid:
            box.locator('[data-testid="stTooltipErrorHoverTarget"]').first.hover()
            page.locator('[data-testid="stTooltipErrorContent"]').first.wait_for()
            page.wait_for_timeout(400)
        frame = run.shot(f"{short}_65mb", box)
        if invalid:
            found = run.measure(f"{short}: 65 МБ подсказка", where,
                                "File must be 200.0MB or smaller.", SEL_TIP_FILE, frame)
            tip_text = found[0]["text"] if found else ""
        alerts = visible_alerts(page)
        run.note(
            f"{short}: 65 МБ итог",
            where,
            json.dumps(
                {
                    "chip": chip.first.get_attribute("aria-label"),
                    "streamlit_rejected": invalid,
                    "tooltip": tip_text,
                    "alerts": alerts,
                },
                ensure_ascii=False,
            ),
            frame,
        )
        page.mouse.move(5, 5)
        remove_files(page, box)


def number_out_of_range(run: Run) -> None:
    page = run.page
    g.open_tab(page, "Диаграммы")
    g.open_tab(page, "Тройная при T = const")
    block = g.open_expander(page, g.main_area(page), g.BLOCK_PRECISION)
    control = g.widget(block, "stNumberInput", NUMBER_LABEL)
    field = control.locator("input")
    original = field.input_value()
    g.set_number(block, NUMBER_LABEL, "20")
    page.wait_for_timeout(500)
    control.locator('[data-testid="stTooltipErrorHoverTarget"]').first.hover()
    page.locator('[data-testid="stTooltipErrorContent"]').first.wait_for()
    page.wait_for_timeout(400)
    where = f"Диаграммы → Тройная при T = const → «{NUMBER_LABEL}» = 20"
    frame = run.shot("chislo_vne_granits", control)
    run.measure("число вне границ", where,
                "Error: Number is outside the allowed range. …", SEL_TIP_NUMBER, frame)
    page.mouse.move(5, 5)

    # Для сравнения: подсказка «?» того же поля — остаётся как была.
    control.locator('[data-testid="stTooltipHoverTarget"] button').first.hover()
    page.locator(SEL_TOOLTIP).first.wait_for()
    page.wait_for_timeout(400)
    frame = run.shot("podskazka_polya", control)
    run.measure("сравнение: подсказка «?»", f"«{NUMBER_LABEL}», кнопка «?»",
                "", SEL_TOOLTIP + " p", frame)
    page.mouse.move(5, 5)
    g.set_number(block, NUMBER_LABEL, original)
    g.wait_idle(page)


def listbox_options(page) -> list[str]:
    return [
        text.strip()
        for text in page.locator(
            '[role="listbox"] [role="option"]:not([data-key^="__"]):not([style*="display: contents"])'
        ).all_inner_texts()
    ]


def energy_multiselect(run: Run) -> None:
    page = run.page
    g.open_tab(page, "Энергии")
    g.open_tab(page, "Энергии фаз")
    root = g.main_area(page)
    control = g.widget(root, "stMultiSelect", ENERGY_LABEL)
    where = f"Энергии → Энергии фаз → «{ENERGY_LABEL}»"
    field = control.locator("input").first

    field.click()
    page.locator(SEL_SELECT_ALL).first.wait_for()
    frame = run.shot("spisok_raskryt", control)
    run.measure("мультивыбор: первая строка", where, "Select all", SEL_SELECT_ALL, frame)
    run.measure("сравнение: вариант списка", where, "", SEL_OPTION, frame)
    options = listbox_options(page)

    # Часть имени, совпадающая с двумя и более фазами.
    fragment = ""
    for candidate in ("BCC", "FCC", "_", "A"):
        if sum(candidate in option for option in options) >= 2:
            fragment = candidate
            break
    field.fill(fragment)
    page.locator(SEL_SELECT_MATCHES).first.wait_for()
    frame = run.shot("spisok_poisk", control)
    run.measure("мультивыбор: найдено", where, "Select N matches",
                SEL_SELECT_MATCHES, frame, note=f"поиск «{fragment}»")
    field.fill("")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    clear = control.locator('[aria-label="Clear all"], [title="Clear all"]')
    if clear.count():
        clear.first.click()
    else:
        for _ in range(10):
            remove = control.locator('button[aria-label^="Remove "]')
            if not remove.count():
                break
            remove.first.click()
            g.wait_idle(page)
    g.wait_idle(page)
    page.mouse.move(5, 5)
    control = g.widget(g.main_area(page), "stMultiSelect", ENERGY_LABEL)
    frame = run.shot("spisok_pustoy", control)
    record = control.evaluate(PLACEHOLDER_JS)
    run.records.append(
        {"theme": run.theme, "place": "мультивыбор: пустой", "where": where,
         "english": "Choose options", "selector": "input::placeholder", "frame": frame,
         "found": [record], "note": ""}
    )
    print(f"  {'мультивыбор: пустой':28s} placeholder={record['text']!r}")

    field = control.locator("input").first
    for option in options[:8]:
        field.click()
        field.fill(option)
        page.wait_for_timeout(250)
        page.get_by_role("option", name=option, exact=True).first.click()
        page.wait_for_timeout(200)
        page.keyboard.press("Escape")
    g.wait_idle(page)
    control = g.widget(g.main_area(page), "stMultiSelect", ENERGY_LABEL)
    field = control.locator("input").first
    field.click()
    page.locator(SEL_NO_RESULTS).first.wait_for()
    frame = run.shot("spisok_vosem", control)
    run.measure("мультивыбор: восемь выбрано", where,
                "You can only select up to 8 options. Remove an option first.",
                SEL_NO_RESULTS, frame)
    page.keyboard.press("Escape")

    control.locator('button[aria-label^="Remove "]').last.click()
    g.wait_idle(page)
    control = g.widget(g.main_area(page), "stMultiSelect", ENERGY_LABEL)
    field = control.locator("input").first
    field.click()
    field.fill("zzz")
    page.locator(SEL_NO_RESULTS).first.wait_for()
    frame = run.shot("spisok_zzz", control)
    run.measure("мультивыбор: zzz", where, "No results", SEL_NO_RESULTS, frame)
    field.fill("")
    page.keyboard.press("Escape")


def base_selectbox(run: Run) -> None:
    page = run.page
    control = g.widget(g.sidebar(page), "stSelectbox", "Элемент-основа")
    field = control.locator('input[role="combobox"]').first
    where = "Боковая панель → «Элемент-основа»"
    field.click()
    # Как в make_guide_screens.set_selectbox: щелчок иногда только ставит фокус.
    page.wait_for_timeout(1000)
    if not page.locator('[role="listbox"]').count():
        field.press("ArrowDown")
    page.locator(SEL_OPTION).first.wait_for()
    frame = run.shot("osnova_raskryt", control)
    run.measure("сравнение: вариант одиночного", where, "", SEL_OPTION, frame)
    field.fill("zzz")
    page.locator(SEL_NO_RESULTS).first.wait_for()
    frame = run.shot("osnova_zzz", control)
    run.measure("одиночный выбор: zzz", where, "No results", SEL_NO_RESULTS, frame)
    page.keyboard.press("Escape")
    page.keyboard.press("Escape")
    g.wait_idle(page)


def table_toolbar(run: Run) -> None:
    page = run.page
    g.open_tab(page, "Проекты и данные")
    g.open_tab(page, "Марки и составы")
    table = g.main_area(page).locator('[data-testid="stDataFrame"]:visible').first
    table.scroll_into_view_if_needed()
    table.hover()
    toolbar = page.locator('[data-testid="stElementToolbar"]:visible').first
    toolbar.wait_for()
    buttons = toolbar.locator("button")
    target = None
    for index in range(buttons.count()):
        label = buttons.nth(index).get_attribute("aria-label") or ""
        if label == "Search":
            target = buttons.nth(index)
            break
    target = target or buttons.first
    target.hover()
    page.locator(SEL_TOOLTIP).first.wait_for()
    page.wait_for_timeout(400)
    frame = run.shot("tablitsa_knopka", table)
    run.measure("сравнение: кнопка над таблицей", "Марки и составы → таблица, кнопка",
                "Search", SEL_TOOLTIP + " p", frame)
    page.mouse.move(5, 5)


def prepare_files(tmp: Path) -> Path:
    tmp.mkdir(parents=True, exist_ok=True)
    # Небольшой CSV: карточка с размером вида «132.0B».
    csv_text = (
        "Название,База,Основа,Единицы,\"Температура, °C\",Добавки\n"
        "Ni–15Al,ni,Ni,ат.%,700,Al=15\n"
        "Ni–18Al,ni,Ni,ат.%,700,Al=18\n"
    )
    (tmp / "sostavy.csv").write_text(csv_text, encoding="utf-8")
    (tmp / "nevernyy.txt").write_text("не тот тип\n", encoding="utf-8")
    big = tmp / "bolshoy_65mb"
    size = 65 * 1024 * 1024
    for suffix in (".csv", ".json"):
        path = big.with_suffix(suffix)
        if not path.exists() or path.stat().st_size != size:
            with path.open("wb") as handle:
                handle.truncate(size)
    return big


def run_theme(driver, phase: str, theme: str, port: int, tmp: Path, big: Path) -> Run:
    browser = driver.chromium.launch(headless=True)
    context = browser.new_context(
        viewport=dict(g.VIEWPORT),
        device_scale_factor=1,
        color_scheme=theme,
        locale="ru-RU",
        timezone_id="Europe/Moscow",
    )
    context.set_default_timeout(g.UI_TIMEOUT_MS)
    page = context.new_page()
    page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded")
    page.get_by_role("tab", name="Расчёты", exact=True).wait_for(timeout=g.CALC_TIMEOUT_MS)
    g.wait_idle(page)
    expand = page.locator('[data-testid="stExpandSidebarButton"]')
    if expand.count():
        expand.first.click()
        g.wait_idle(page)
    page.wait_for_timeout(500)
    background = page.evaluate(
        "getComputedStyle(document.querySelector('[data-testid=\"stApp\"]')).backgroundColor"
    )
    print(f"[{phase} / {theme}] фон приложения {background}")
    run = Run(page, phase, theme)
    run.background = background
    for step in (uploaders, number_out_of_range, energy_multiselect, base_selectbox,
                 table_toolbar):
        started = time.monotonic()
        if step is uploaders:
            step(run, tmp, big)
        else:
            step(run)
        print(f"  — {step.__name__}: {time.monotonic() - started:.0f} с")
    browser.close()
    return run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("do", "posle"), required=True)
    parser.add_argument("--port", type=int, default=8631)
    parser.add_argument("--tmp", type=Path, required=True)
    parser.add_argument("--themes", default="light,dark")
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright
    import streamlit

    (OUT / "kadry").mkdir(parents=True, exist_ok=True)
    big = prepare_files(args.tmp)
    result = {
        "phase": args.phase,
        "streamlit": streamlit.__version__,
        "port": args.port,
        "themes": {},
    }
    with sync_playwright() as driver:
        for theme in args.themes.split(","):
            run = run_theme(driver, args.phase, theme, args.port, args.tmp, big)
            result["themes"][theme] = {
                "background": run.background,
                "frames": run.frames,
                "records": run.records,
            }
    path = OUT / f"zamer_{args.phase}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"записано {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
