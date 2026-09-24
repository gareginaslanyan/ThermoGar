"""21-D: frames 04, 15, 16, 17, 36 again, light and dark theme.

Copy of results/wave21_b/scripts/kadry.py (the original is not changed).
Changes of the copy: own results folder, state root and port 8641; only the
frames in ``SELECTED`` are taken, under their 21-B numbers; scenarios
start, raschety, diagrammy and the message frame; the rectangles of the
chart images go into the manifest (pixel measurements of the legend).
The text below is the 21-B original.


The app must already be running (like ``make_guide_screens.py --keep-server``):

    results\\wave21_d\\scripts\\run_app.cmd      (port 8641, --client.toolbarMode auto)

Tab scenarios are imported from ``tools/make_guide_screens.py`` unchanged.
Its ``Shooter`` is replaced at import time with ``AuditShooter``: no target
highlight, and only the scenario steps listed in ``CAPTURE`` produce a frame.
One run takes one theme (``--theme``). Matplotlib charts take the theme that
is active while the script runs and keep it: switching the theme in the main
menu (System / Light / Dark) repaints the page but not the charts, and a plain
rerun does not rebuild them either. So the scenario is repeated per theme:
light in a default session, dark with ``?embed_options=dark_theme``.

Phases (``--phases``, default all):

    kadry   scenario frames, extra subtabs, expanded blocks, messages
    izmer   computed-style measurements -> results/wave21_d/izmereniya.json
    s5      900x800 window: horizontal scroll per top tab, sidebar collapse

Run from the w21b root, once per theme:

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 results\\wave21_d\\scripts\\kadry.py --theme Light
    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -X utf8 results\\wave21_d\\scripts\\kadry.py --theme Dark
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import make_guide_screens as mgs  # noqa: E402

RESULTS = REPO_ROOT / "results" / "wave21_d"
KADRY = RESULTS / "kadry"
MEASUREMENTS = RESULTS / "izmereniya.json"
MANIFEST = KADRY / "_manifest.json"

# The batch CSV of the "proekty" scenario is written into mgs.STATE_ROOT:
# point it at this task's own state root, not the guide one.
STATE_ROOT = Path(os.environ["TEMP"]) / "tg21d_state"
mgs.STATE_ROOT = STATE_ROOT

PORT = 8641
VIEWPORT = {"width": 1440, "height": 900}
S5_VIEWPORT = {"width": 900, "height": 800}
MAX_PART = 3000
THEMES = ("Light", "Dark")
THEME_SLUG = {"Light": "svet", "Dark": "tyomn"}
MIN_FREE_GIB = 3.0

# 21-D: frames to take again; the number is the one of the same frame in 21-B.
SELECTED = (
    "raschety_temperaturnyi_diapazon",
    "diagrammy_binarnaya",
    "diagrammy_mnogokomponentnoe",
    "diagrammy_troynaya",
    "soobshchenie_error",
)
SLUG_NUMBER = {
    frame["slug"]: int(frame["files"][0][:2])
    for frame in json.loads(
        (REPO_ROOT / "results" / "wave21_b" / "kadry" / "_manifest.json")
        .read_text(encoding="utf-8")
    )["frames"]
}
DEFAULT_SCENARIOS = "start,raschety,diagrammy,soobshcheniya"

TOP_TABS = {
    "Расчёты": ["Одна температура", "Температурный диапазон", "Изменение состава"],
    "Диаграммы": [
        "Бинарная T–X",
        "Многокомпонентное T–X",
        "Тройная при T = const",
        "Карта доли фазы",
    ],
    "Затвердевание": [],
    "Энергии": ["Энергии фаз", "Движущая сила", "T₀"],
    "Свойства": [
        "Плотность",
        "Плотность по T",
        "Упругие свойства",
        "Вклады упрочнения",
        "Покрытие PDB",
    ],
    "Кинетика": ["Диффузия и гомогенизация", "Выделения"],
    "Проекты и данные": [
        "Марки и составы",
        "Пакетный расчёт",
        "Проекты и история",
        "Паспорт базы",
        "Как пользоваться",
        "Справочник фаз",
        "Проверка установки",
    ],
}


# ---------------------------------------------------------------------------
# Memory gate
# ---------------------------------------------------------------------------


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def free_gib() -> float:
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return status.ullAvailPhys / 2**30


# ---------------------------------------------------------------------------
# Theme switching and full-height capture
# ---------------------------------------------------------------------------

APP_BG_JS = """
() => getComputedStyle(document.querySelector('[data-testid="stApp"]')).backgroundColor
"""
THEME_BG = {"Light": "rgb(255, 255, 255)", "Dark": "rgb(26, 24, 22)"}

HEIGHTS_JS = """
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const side = document.querySelector('[data-testid="stSidebarContent"]');
  const sideShown = side && side.getBoundingClientRect().right > 0 &&
    getComputedStyle(document.querySelector('[data-testid="stSidebar"]')).visibility !== 'hidden';
  return {main: main ? main.scrollHeight : 0, side: sideShown ? side.scrollHeight : 0};
}
"""

FRAME_INFO_JS = """
() => {
  const shown = e => e.offsetParent !== null && e.getBoundingClientRect().height > 0;
  const main = document.querySelector('[data-testid="stMain"]');
  const charts = [...main.querySelectorAll(
    '[data-testid="stImage"] img, [data-testid="stPlotlyChart"], ' +
    '[data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"]'
  )].filter(shown).length;
  const tables = [...main.querySelectorAll('[data-testid="stDataFrame"], [data-testid="stTable"]')]
    .filter(shown).length;
  const alerts = [...document.querySelectorAll('[data-testid^="stAlertContent"]')]
    .filter(e => shown(e) && e.getBoundingClientRect().top < window.innerHeight)
    .map(e => ({kind: e.dataset.testid.replace('stAlertContent', '').toLowerCase(),
                text: e.innerText.trim().slice(0, 90)}));
  const tabs = [...main.querySelectorAll('[role="tab"][aria-selected="true"]')]
    .filter(shown).map(e => e.innerText.trim());
  const expanded = [...main.querySelectorAll('[data-testid="stExpander"] details[open] > summary')]
    .filter(shown).map(e => e.innerText.replace('keyboard_arrow_down', '').trim());
  const chartRects = [...main.querySelectorAll('[data-testid="stImage"] img')].filter(shown)
    .map(e => { const r = e.getBoundingClientRect();
      return {x: r.left + window.scrollX, y: r.top + window.scrollY, width: r.width, height: r.height,
              naturalWidth: e.naturalWidth, naturalHeight: e.naturalHeight}; });
  return {charts, tables, alerts, tabs, expanded, chartRects};
}
"""


def current_theme(page) -> str:
    background = page.evaluate(APP_BG_JS)
    for theme, expected in THEME_BG.items():
        if background == expected:
            return theme
    return background


def set_theme(page, theme: str) -> None:
    if current_theme(page) == theme:
        return
    page.locator('[data-testid="stMainMenuButton"]').first.click()
    page.locator(f'[data-testid="stMainMenuItem-theme-{theme}"]').first.click()
    page.wait_for_timeout(300)
    if page.locator('[data-testid="stMainMenuPopover"]:visible').count():
        page.keyboard.press("Escape")
    deadline = time.monotonic() + 15
    while current_theme(page) != theme:
        if time.monotonic() > deadline:
            raise RuntimeError(f"Theme {theme} did not apply: {page.evaluate(APP_BG_JS)}")
        page.wait_for_timeout(100)
    page.wait_for_timeout(400)


def capture(page, stem: str, *, with_sidebar: bool) -> tuple[list[Path], dict]:
    """Full-height frame; taller than MAX_PART is cut into parts."""

    heights = page.evaluate(HEIGHTS_JS)
    need = max(heights["main"], heights["side"] if with_sidebar else 0, VIEWPORT["height"])
    page.set_viewport_size({"width": VIEWPORT["width"], "height": need})
    page.wait_for_timeout(900)
    heights = page.evaluate(HEIGHTS_JS)
    need2 = max(heights["main"], heights["side"] if with_sidebar else 0, VIEWPORT["height"])
    if need2 != need:
        need = need2
        page.set_viewport_size({"width": VIEWPORT["width"], "height": need})
        page.wait_for_timeout(900)
    info = page.evaluate(FRAME_INFO_JS)
    info["height_px"] = need
    paths: list[Path] = []
    parts = (need + MAX_PART - 1) // MAX_PART
    for index in range(parts):
        top = index * MAX_PART
        height = min(MAX_PART, need - top)
        suffix = "" if parts == 1 else f"_ch{index + 1}"
        path = KADRY / f"{stem}{suffix}.png"
        page.screenshot(
            path=str(path),
            clip={"x": 0, "y": top, "width": VIEWPORT["width"], "height": height},
        )
        paths.append(path)
    page.set_viewport_size(dict(VIEWPORT))
    page.wait_for_timeout(300)
    return paths, info


def grey_copy(path: Path) -> Path:
    from PIL import Image

    target = path.with_name(path.stem + "_seroe.png")
    with Image.open(path) as image:
        image.convert("L").save(target, format="PNG", optimize=True)
    return target


class Recorder:
    def __init__(self) -> None:
        self.frames: list[dict] = []
        self.counter = 0
        self.theme = "Light"

    def snap(self, page, slug: str, what: str, *, with_sidebar: bool = False) -> None:
        """Take the frame in the theme of this run."""

        self.counter += 1
        if slug not in SELECTED:
            print(f"  skip {slug}", flush=True)
            return
        for theme in (self.theme,):
            if current_theme(page) != theme:
                raise RuntimeError(f"Page left theme {theme}: {page.evaluate(APP_BG_JS)}")
            stem = f"{SLUG_NUMBER[slug]:02d}_{slug}_{THEME_SLUG[theme]}"
            paths, info = capture(page, stem, with_sidebar=with_sidebar)
            greys = [grey_copy(path) for path in paths] if info["charts"] else []
            self.frames.append(
                {
                    "files": [path.name for path in paths],
                    "grey": [path.name for path in greys],
                    "slug": slug,
                    "theme": theme,
                    "what": what,
                    **info,
                }
            )
            print(f"  {stem}: {len(paths)} part(s), h={info['height_px']}, "
                  f"charts={info['charts']}, alerts={[a['kind'] for a in info['alerts']]}",
                  flush=True)
        self.save()

    def save(self) -> None:
        MANIFEST.write_text(
            json.dumps({"frames": self.frames}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


RECORDER = Recorder()
PAGE = None

# Scenario step title -> (slug, description, hook before the frame, hook after it).
CAPTURE: dict[str, tuple] = {}


def audit_step(title: str, slug: str, what: str, *, before=None, after=None, sidebar=False):
    CAPTURE[title] = (slug, what, before, after, sidebar)


class AuditShooter:
    """Stand-in for mgs.Shooter: no highlight, frame only on listed steps."""

    def __init__(self, page, slug, log) -> None:
        self.page = page
        self.slug = slug
        self.log = log

    def shot(self, targets, title, *, tall=False):
        self.log.append({"scenario": self.slug, "title": title})
        if title not in CAPTURE:
            return None
        slug, what, before, after, sidebar = CAPTURE[title]
        mgs.wait_idle(self.page)
        if before:
            before(self.page)
        RECORDER.snap(self.page, slug, what, with_sidebar=sidebar)
        if after:
            after(self.page)
        return None


mgs.Shooter = AuditShooter


# ---------------------------------------------------------------------------
# Extra subtabs not covered by the guide scenarios
# ---------------------------------------------------------------------------


def run_subtab(page, subtab: str, button: str | None, slug: str, what: str) -> None:
    mgs.open_tab(page, subtab)
    root = mgs.main_area(page)
    if button:
        started = time.monotonic()
        mgs.click_button(page, root, button)
        print(f"  [{subtab}] «{button}» {time.monotonic() - started:.0f} s", flush=True)
    RECORDER.snap(page, slug, what)


def open_result_subtabs(names_slugs):
    def hook(page):
        for name, slug, what in names_slugs:
            mgs.open_tab(page, name)
            RECORDER.snap(page, slug, what)
    return hook


def back_to(name):
    def hook(page):
        mgs.open_tab(page, name)
    return hook


def open_batch_columns(page):
    mgs.open_expander(page, mgs.main_area(page), "Требуемые столбцы")


audit_step(
    "Окно программы: заголовок и семь вкладок",
    "zapusk",
    "Запуск: боковая панель целиком и первая вкладка «Расчёты / Одна температура»",
    sidebar=True,
)
audit_step(
    "Таблица устойчивых фаз и их долей",
    "raschety_odna_temperatura",
    "Расчёты / Одна температура: результат (таблица фазовых долей)",
)
audit_step(
    "Переключатель «Быстрый набор / Все фазы базы» и строка «Набор фаз»",
    "raschety_upravlenie_fazami",
    "Расчёты / Одна температура: раскрыт блок «Управление фазами / метастабильный расчёт»",
)
audit_step(
    "График долей фаз по температуре",
    "raschety_temperaturnyi_diapazon",
    "Расчёты / Температурный диапазон: график и таблица скана 500–900 °C",
)
audit_step(
    "Плотность сплава и покрытие физической базы",
    "svoystva_plotnost",
    "Свойства / Плотность: сталь, метрика плотности и таблица",
)
audit_step(
    "E, G и ν по Хиллу для многофазного сплава",
    "svoystva_uprugie",
    "Свойства / Упругие свойства: Ni–15Al, метрики E, G, ν по Хиллу",
)
audit_step(
    "Сводка: ликвидус, солидус и последовательность фаз",
    "zatverdevanie_svodka",
    "Затвердевание / Сводка: Al–4Cu–1Mg, Scheil",
)
audit_step(
    "Подвкладка «Выгрузка»: результат в Excel",
    "zatverdevanie_vygruzka",
    "Затвердевание / Выгрузка",
)
audit_step(
    "Готовая бинарная диаграмма Ni–Al",
    "diagrammy_binarnaya",
    "Диаграммы / Бинарная T–X: Ni–Al 600–1600 °C",
)
audit_step(
    "Таблица движущей силы по температурам",
    "energii_dvizhushchaya_sila",
    "Энергии / Движущая сила: GAMMA_PRIME из FCC_A1, 600–800 °C",
)
audit_step(
    "Доля и средний размер частиц γ′ во времени",
    "kinetika_vydeleniya_itogi",
    "Кинетика / Выделения / Итоги: KWN γ′, 800 °C, 1 ч",
)
audit_step(
    "Профиль состава после выдержки",
    "kinetika_diffuziya_odnofaznaya",
    "Кинетика / Диффузия и гомогенизация / Однофазная пара: профиль после 100 ч",
)
audit_step(
    "Запись появилась в списке «Доступные записи»",
    "proekty_marki",
    "Проекты и данные / Марки и составы: запись сохранена (st.success)",
)
audit_step(
    "Сводка пакетного расчёта по трём составам",
    "proekty_paketnyi",
    "Проекты и данные / Пакетный расчёт: три состава рассчитаны, раскрыт блок «Требуемые столбцы»",
    before=open_batch_columns,
)
audit_step(
    "Проект сохранён в папке ThermoGar",
    "proekty_proekty_istoriya",
    "Проекты и данные / Проекты и история: проект сохранён",
)

# Solidification result subtabs: the "Кривая доли твёрдой фазы" step is used
# only as the moment when the result exists; frames go per subtab.
CAPTURE["Кривая доли твёрдой фазы"] = (
    None, None,
    open_result_subtabs([
        ("Твёрдые фазы", "zatverdevanie_tvyordye_fazy", "Затвердевание / Твёрдые фазы"),
        ("Остаточный расплав", "zatverdevanie_ostatochnyi_rasplav",
         "Затвердевание / Остаточный расплав"),
    ]),
    back_to("Сводка"),
    False,
)
CAPTURE["Доля и средний размер частиц γ′ во времени"] = (
    "kinetika_vydeleniya_itogi",
    "Кинетика / Выделения / Итоги: KWN γ′, 800 °C, 1 ч",
    None,
    open_result_subtabs([
        ("Кинетика и состав", "kinetika_vydeleniya_kinetika",
         "Кинетика / Выделения / Кинетика и состав"),
        ("Распределение размеров", "kinetika_vydeleniya_raspredelenie",
         "Кинетика / Выделения / Распределение размеров"),
        ("Экспорт и ограничения", "kinetika_vydeleniya_eksport",
         "Кинетика / Выделения / Экспорт и ограничения"),
    ]),
    False,
)


_original_shot = AuditShooter.shot


def _shot(self, targets, title, *, tall=False):
    entry = CAPTURE.get(title)
    if entry and entry[0] is None:
        self.log.append({"scenario": self.slug, "title": title})
        mgs.wait_idle(self.page)
        entry[2](self.page)
        entry[3](self.page)
        return None
    return _original_shot(self, targets, title, tall=tall)


AuditShooter.shot = _shot


KINETIKA_WAIT = {"armed": False, "saved": mgs.CALC_TIMEOUT_MS}


def arm_short_wait(page):
    """The guide waits for ``stMetric``.first, which resolves to a hidden metric
    of another tab and never becomes visible. Cut that one wait short; the
    diffusion result is then awaited with wait_idle in ``run_kinetika``."""

    KINETIKA_WAIT["armed"] = True
    mgs.CALC_TIMEOUT_MS = 3000


def run_kinetika(page, log):
    from playwright.sync_api import TimeoutError as PlaywrightTimeout

    try:
        mgs.scenario_kinetika(page, log)
    except PlaywrightTimeout:
        if not KINETIKA_WAIT["armed"]:
            raise
        mgs.CALC_TIMEOUT_MS = KINETIKA_WAIT["saved"]
        KINETIKA_WAIT["armed"] = False
        print("  guide wait for stMetric cut short; waiting with wait_idle", flush=True)
        mgs.wait_idle(page)
        mgs.main_area(page).locator('[data-testid="stMetric"]:visible').first.wait_for(
            timeout=mgs.CALC_TIMEOUT_MS
        )
        mgs.wait_idle(page)
        RECORDER.snap(
            page,
            "kinetika_diffuziya_odnofaznaya",
            "Кинетика / Диффузия и гомогенизация / Однофазная пара: профиль после 100 ч",
        )
    finally:
        mgs.CALC_TIMEOUT_MS = KINETIKA_WAIT["saved"]


CAPTURE["Режим выдержки: 1200 °C, 100 ч, 80 ячеек на 2000 мкм"] = (
    None, None, arm_short_wait, lambda page: None, False,
)


def extras_raschety(page):
    mgs.open_tab(page, "Расчёты")
    run_subtab(page, "Изменение состава", "Построить график по составу",
               "raschety_izmenenie_sostava",
               "Расчёты / Изменение состава: график по составу, значения по умолчанию")


def extras_svoystva(page):
    mgs.open_tab(page, "Свойства")
    run_subtab(page, "Плотность по T", "Построить плотность по температуре",
               "svoystva_plotnost_po_t", "Свойства / Плотность по T: значения по умолчанию")
    run_subtab(page, "Вклады упрочнения", "Рассчитать вклады",
               "svoystva_vklady", "Свойства / Вклады упрочнения: значения по умолчанию")
    run_subtab(page, "Покрытие PDB", "Обновить проверенное покрытие PDB",
               "svoystva_pokrytie_pdb", "Свойства / Покрытие PDB: после обновления")


def extras_diagrammy(page):
    mgs.open_tab(page, "Диаграммы")
    run_subtab(page, "Многокомпонентное T–X", "Построить многокомпонентное сечение",
               "diagrammy_mnogokomponentnoe",
               "Диаграммы / Многокомпонентное T–X: значения по умолчанию")
    run_subtab(page, "Тройная при T = const", "Построить тройную диаграмму",
               "diagrammy_troynaya", "Диаграммы / Тройная при T = const: значения по умолчанию")
    run_subtab(page, "Карта доли фазы", "Построить карту доли фазы",
               "diagrammy_karta", "Диаграммы / Карта доли фазы: значения по умолчанию")


def extras_energii(page):
    mgs.open_tab(page, "Энергии")
    run_subtab(page, "Энергии фаз", "Рассчитать энергии фаз",
               "energii_energii_faz", "Энергии / Энергии фаз: значения по умолчанию")
    run_subtab(page, "T₀", "Рассчитать T₀", "energii_t0", "Энергии / T₀: значения по умолчанию")


def extras_kinetika(page):
    mgs.open_tab(page, "Кинетика")
    mgs.open_tab(page, "Диффузия и гомогенизация")
    for name, slug in (
        ("Многофазная гомогенизация", "kinetika_diffuziya_mnogofaznaya"),
        ("Покрытие базы подвижностей", "kinetika_diffuziya_pokrytie"),
    ):
        mgs.open_tab(page, name)
        root = mgs.main_area(page)
        buttons = [
            text for text in root.locator("button:visible").all_inner_texts()
            if text.strip().startswith(("Рассчитать", "Построить", "Проверить", "Обновить"))
        ]
        button = buttons[0].strip() if buttons else None
        run_subtab(page, name, button, slug,
                   f"Кинетика / Диффузия и гомогенизация / {name}"
                   + (f": «{button}», значения по умолчанию" if button else ""))


def extras_proekty(page):
    mgs.open_tab(page, "Проекты и данные")
    run_subtab(page, "Паспорт базы", None, "proekty_pasport", "Проекты и данные / Паспорт базы")
    run_subtab(page, "Как пользоваться", None, "proekty_kak_polzovatsya",
               "Проекты и данные / Как пользоваться")
    run_subtab(page, "Справочник фаз", None, "proekty_spravochnik_faz",
               "Проекты и данные / Справочник фаз")
    run_subtab(page, "Проверка установки",
               "Проверить базы и запустить три контрольных расчёта",
               "proekty_proverka_ustanovki",
               "Проекты и данные / Проверка установки: три контрольных расчёта выполнены")


ERROR_INPUTS = ("QQ=5", "AL=150", "AL=abc")


def error_frame(page) -> dict:
    """st.error on screen: an invalid additive in the sidebar, then restore."""

    side = mgs.sidebar(page)
    field = mgs.widget(side, "stTextArea", "Добавки").locator("textarea")
    original = field.input_value()
    mgs.open_tab(page, "Расчёты")
    mgs.open_tab(page, "Одна температура")
    used = None
    for value in ERROR_INPUTS:
        mgs.set_text_area(side, "Добавки", value)
        mgs.wait_idle(page)
        errors = page.locator('[data-testid="stAlertContentError"]:visible')
        if errors.count():
            used = value
            break
    if used:
        page.locator('[data-testid="stAlertContentError"]:visible').first.scroll_into_view_if_needed()
        RECORDER.snap(page, "soobshchenie_error",
                      f"st.error: неверная добавка «{used}» в боковой панели", with_sidebar=True)
    alert_colours = page.evaluate(ALERTS_JS)
    mgs.set_text_area(side, "Добавки", original)
    mgs.wait_idle(page)
    return {"error_input": used, "restored": original, "alerts": alert_colours}


# ---------------------------------------------------------------------------
# Measurements (step 2)
# ---------------------------------------------------------------------------

COMMON_JS = r"""
window.__tg = (() => {
  const parse = s => {
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const over = (top, bottom) => {
    const a = top.a + bottom.a * (1 - top.a);
    if (a === 0) return {r: 0, g: 0, b: 0, a: 0};
    const mix = k => (top[k] * top.a + bottom[k] * bottom.a * (1 - top.a)) / a;
    return {r: mix('r'), g: mix('g'), b: mix('b'), a};
  };
  // Effective opaque background: composite ancestor backgrounds bottom-up.
  const effBg = el => {
    const layers = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; }
    }
    let colour = {r: 255, g: 255, b: 255, a: 1};
    if (layers.length && layers[layers.length - 1].a >= 1) colour = layers.pop();
    while (layers.length) colour = over(layers.pop(), colour);
    return colour;
  };
  const hex = c => c ? '#' + [c.r, c.g, c.b].map(v => Math.round(v).toString(16).padStart(2, '0'))
    .join('').toUpperCase() + (c.a < 1 ? ' a=' + c.a.toFixed(2) : '') : null;
  const lum = c => {
    const f = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (fg, bg) => {
    const f = fg.a < 1 ? over(fg, bg) : fg;
    const a = lum(f), b = lum(bg);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  };
  const shown = e => e && e.offsetParent !== null && e.getBoundingClientRect().height > 0;
  const firstShown = sel => [...document.querySelectorAll(sel)].find(shown) || null;
  const font = e => {
    if (!e) return null;
    const s = getComputedStyle(e);
    return {size: s.fontSize, weight: s.fontWeight, lineHeight: s.lineHeight,
            family: s.fontFamily.split(',')[0].replace(/"/g, ''), text: e.innerText.trim().slice(0, 50)};
  };
  const opacity = e => {
    let o = 1;
    for (let n = e; n && n.nodeType === 1; n = n.parentElement) o *= parseFloat(getComputedStyle(n).opacity);
    return o;
  };
  // Colour as painted: CSS colour with alpha times ancestor opacity, over the background.
  const painted = (e, bg) => {
    const c = parse(getComputedStyle(e).color);
    const op = opacity(e);
    return over({r: c.r, g: c.g, b: c.b, a: c.a * op}, bg);
  };
  const textOn = (e, label) => {
    if (!e) return null;
    const s = getComputedStyle(e);
    const bg = effBg(e);
    const fg = painted(e, bg);
    return {what: label, css_color: hex(parse(s.color)), opacity: +opacity(e).toFixed(2),
            fg: hex(fg), bg: hex(bg), ratio: +ratio(fg, bg).toFixed(2),
            fontSize: s.fontSize, fontWeight: s.fontWeight, sample: e.innerText.trim().slice(0, 50)};
  };
  return {parse, over, effBg, hex, lum, ratio, shown, firstShown, font, textOn, opacity, painted};
})();
"""

ALERTS_JS = COMMON_JS + r"""
(() => {
  const t = window.__tg;
  const out = {};
  for (const kind of ['Error', 'Warning', 'Info', 'Success']) {
    const all = [...document.querySelectorAll('[data-testid="stAlertContent' + kind + '"]')];
    const el = all.find(t.shown) || all[0];
    if (!el) { out[kind.toLowerCase()] = null; continue; }
    const text = el.querySelector('p') || el;
    const box = el.closest('[data-testid="stAlertContainer"]') || el;
    const s = getComputedStyle(text);
    const bg = t.effBg(box), fg = t.painted(text, bg);
    const icon = box.querySelector('[data-testid="stAlertDynamicIcon"], [data-testid="stIconMaterial"], span[role="img"]');
    const iconColour = icon ? t.parse(getComputedStyle(icon).color) : null;
    out[kind.toLowerCase()] = {
      fg: t.hex(fg), bg: t.hex(bg), ratio: +t.ratio(fg, bg).toFixed(2),
      icon: iconColour ? t.hex(iconColour) : null,
      iconRatio: iconColour ? +t.ratio(iconColour, bg).toFixed(2) : null,
      shownOnScreen: t.shown(el), sample: el.innerText.trim().slice(0, 60),
      fontSize: s.fontSize,
    };
  }
  return out;
})()
"""

STYLE_JS = COMMON_JS + r"""
(() => {
  const t = window.__tg;
  const q = t.firstShown;
  const app = document.querySelector('[data-testid="stApp"]');
  const side = document.querySelector('[data-testid="stSidebar"]');
  const colours = {};
  const put = (key, el, prop) => {
    if (!el) { colours[key] = null; return; }
    const s = getComputedStyle(el);
    const bg = t.effBg(el);
    const entry = {value: t.hex(t.parse(s[prop])), prop, effective_bg: t.hex(bg)};
    if (prop === 'color') {
      entry.opacity = +t.opacity(el).toFixed(2);
      entry.painted = t.hex(t.painted(el, bg));
    }
    colours[key] = entry;
  };
  put('window_bg', app, 'backgroundColor');
  put('sidebar_bg', side, 'backgroundColor');
  const exp = q('[data-testid="stMain"] [data-testid="stExpander"] details');
  put('expander_bg', exp, 'backgroundColor');
  put('expander_border', exp, 'borderTopColor');
  const bordered = [...document.querySelectorAll('[data-testid="stMain"] [data-testid="stVerticalBlock"], [data-testid="stMain"] [data-testid="stForm"]')]
    .find(e => t.shown(e) && parseFloat(getComputedStyle(e).borderTopWidth) > 0);
  put('bordered_container_bg', bordered, 'backgroundColor');
  put('bordered_container_border', bordered, 'borderTopColor');
  const plain = e => t.shown(e) && e.innerText.trim().length > 20 &&
    !e.closest('[role="tab"], h1, h2, h3, h4, h5, h6, [data-testid="stAlert"], summary, ' +
               '[data-testid="stWidgetLabel"], [data-testid="stCaptionContainer"], button');
  const qText = sel => [...document.querySelectorAll(sel)].find(plain) || null;
  const qCap = sel => [...document.querySelectorAll(sel)]
    .filter(e => t.shown(e) && e.innerText.trim().length > 0)
    .map(e => e.querySelector('p') || e)[0] || null;
  const bodyText = qText('[data-testid="stMain"] [data-testid="stMarkdownContainer"] p, ' +
                         '[data-testid="stMain"] [data-testid="stMarkdownContainer"] li');
  put('body_text', bodyText, 'color');
  const caption = qCap('[data-testid="stMain"] [data-testid="stCaptionContainer"]');
  put('caption', caption, 'color');
  const label = [...document.querySelectorAll('[data-testid="stMain"] [data-testid="stWidgetLabel"] p')]
    .find(e => t.shown(e) && e.innerText.trim().length > 0) || null;
  put('widget_label', label, 'color');
  const input = q('[data-testid="stMain"] [data-testid="stNumberInputContainer"]') ||
                q('[data-testid="stMain"] [data-baseweb="input"]');
  put('input_border', input, 'borderTopColor');
  put('input_bg', input, 'backgroundColor');
  const linkOk = e => t.shown(e) && e.innerText.trim().length > 0 && !e.closest('h1, h2, h3, h4, h5, h6');
  const link = [...document.querySelectorAll('[data-testid="stMain"] [data-testid="stMarkdownContainer"] a')].find(linkOk) ||
               [...document.querySelectorAll('[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] a')].find(linkOk) || null;
  put('link', link, 'color');
  const th = q('[data-testid="stMain"] [data-testid="stMarkdownContainer"] th, [data-testid="stMain"] [data-testid="stTable"] th');
  put('html_table_header_text', th, 'color');
  put('html_table_header_bg', th, 'backgroundColor');

  const fonts = {
    h1: t.font(q('[data-testid="stMain"] h1')),
    h2: t.font(q('[data-testid="stMain"] h2')),
    h3: t.font(q('[data-testid="stMain"] h3')),
    h4: t.font(q('[data-testid="stMain"] h4')),
    body: t.font(bodyText),
    caption: t.font(caption),
    widget_label: t.font(label),
  };

  const sideCaption = qCap('[data-testid="stSidebar"] [data-testid="stCaptionContainer"]');
  const expCaption = qCap('[data-testid="stMain"] [data-testid="stExpanderDetails"] [data-testid="stCaptionContainer"]');
  const contrast = [
    t.textOn(bodyText, 'основной текст / фон окна'),
    t.textOn(caption, 'caption / фон окна'),
    t.textOn(sideCaption, 'caption / боковая панель'),
    t.textOn(expCaption, 'caption / раскрытие'),
    t.textOn(label, 'подпись виджета / фон окна'),
    t.textOn(link, 'ссылка / фон'),
  ].filter(Boolean);
  if (input) {
    const b = t.parse(getComputedStyle(input).borderTopColor);
    const inputBg = t.effBg(input);
    const pageBg = t.effBg(input.parentElement);
    contrast.push({what: 'поле ввода: заливка / фон окна (граница, 3:1)', fg: t.hex(inputBg),
                   bg: t.hex(pageBg), ratio: +t.ratio(inputBg, pageBg).toFixed(2)});
    if (b && b.a > 0) contrast.push({what: 'рамка поля ввода / фон окна (3:1)', fg: t.hex(b),
                   bg: t.hex(pageBg), ratio: +t.ratio(b, pageBg).toFixed(2)});
  }
  if (exp) {
    const b = t.parse(getComputedStyle(exp).borderTopColor);
    const bg = t.effBg(exp.parentElement);
    contrast.push({what: 'рамка раскрытия / фон окна (3:1)', fg: t.hex(b), bg: t.hex(bg),
                   ratio: +t.ratio(b, bg).toFixed(2)});
  }
  return {colours, fonts, contrast};
})()
"""

MEASURE_JS = r"""
(() => {
  const shown = e => e.offsetParent !== null && e.getBoundingClientRect().height > 0;
  const blocks = [...document.querySelectorAll(
    '[data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] > *, ' +
    '[data-testid="stCaptionContainer"] > *, [data-testid="stCaptionContainer"]'
  )].filter(e => shown(e) && ['P', 'LI', 'UL', 'OL', 'DIV', 'BLOCKQUOTE'].includes(e.tagName));
  const seen = new Set();
  const out = [];
  const range = document.createRange();
  for (const block of blocks) {
    // Paragraph-level units: <p> and <li>; a caption container without <p> counts as one.
    const units = block.matches('ul, ol') ? [...block.querySelectorAll('li')] : [block];
    for (const unit of units) {
      if (seen.has(unit)) continue;
      if (unit.querySelector('p, li') && unit.tagName !== 'LI') continue;
      seen.add(unit);
      const text = unit.innerText.replace(/\s+/g, ' ').trim();
      if (text.length <= 80) continue;
      const lines = [];
      const walker = document.createTreeWalker(unit, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const value = node.nodeValue;
        for (let i = 0; i < value.length; i++) {
          if (value[i] === '\n') continue;
          range.setStart(node, i); range.setEnd(node, i + 1);
          const rect = range.getClientRects()[0];
          if (!rect || rect.width === 0 && value[i] !== ' ') continue;
          const mid = rect.top + rect.height / 2;
          let line = lines.find(l => Math.abs(l.mid - mid) < 6);
          if (!line) { line = {mid, chars: 0}; lines.push(line); }
          line.chars += 1;
        }
      }
      const longest = lines.reduce((m, l) => Math.max(m, l.chars), 0);
      const rect = unit.getBoundingClientRect();
      const inSidebar = !!unit.closest('[data-testid="stSidebar"]');
      const isCaption = !!unit.closest('[data-testid="stCaptionContainer"]');
      out.push({
        where: inSidebar ? 'sidebar' : 'main', kind: isCaption ? 'caption' : 'markdown',
        tag: unit.tagName, chars_total: text.length, width_px: Math.round(rect.width),
        lines: lines.length, longest_line_chars: longest,
        font_size: getComputedStyle(unit).fontSize, sample: text.slice(0, 70),
      });
    }
  }
  return out;
})()
"""

SIDEBAR_TEXT_MARK = "sidebar"


def wrap_js(body: str) -> str:
    return "() => " + body.strip()


def measure_phase(page) -> dict:
    """Styles and paragraph measures of every subtab, results still on screen."""

    styles, paragraphs = {}, {}
    for top, subs in TOP_TABS.items():
        mgs.open_tab(page, top)
        for sub in subs or [None]:
            if sub:
                mgs.open_tab(page, sub)
            key = f"{top} / {sub}" if sub else top
            styles[key] = page.evaluate(STYLE_JS)
            styles[key]["alerts"] = page.evaluate(ALERTS_JS)
            paragraphs[key] = page.evaluate(MEASURE_JS)
            print(f"  izmer {key}", flush=True)
    first = next(iter(paragraphs))
    paragraphs["Боковая панель"] = [
        item for item in paragraphs[first] if item["where"] == "sidebar"
    ]
    for key in list(paragraphs):
        if key != "Боковая панель":
            paragraphs[key] = [item for item in paragraphs[key] if item["where"] == "main"]
    return {
        "styles": styles,
        "paragraphs": paragraphs,
        "dataframe_header": dataframe_header_colours(page),
    }


def measure_only(page, mine: dict) -> None:
    """Style pass in a fresh session; paragraphs from the full run are kept."""

    fresh = measure_phase(page)
    if "paragraphs" in mine:
        fresh["paragraphs_fresh_session"] = fresh.pop("paragraphs")
    fresh["styles_session"] = "fresh session, no calculation results on screen"
    mine.update(fresh)


def dataframe_header_colours(page) -> dict:
    """st.dataframe draws on canvas: sample header pixels from a screenshot."""

    from io import BytesIO

    from PIL import Image

    mgs.open_tab(page, "Проекты и данные")
    mgs.open_tab(page, "Справочник фаз")
    frame = mgs.main_area(page).locator('[data-testid="stDataFrame"]:visible').first
    if not frame.count():
        return {"error": "no visible dataframe"}
    if True:
        frame.scroll_into_view_if_needed()
        page.wait_for_timeout(400)
        image = Image.open(BytesIO(frame.screenshot())).convert("RGB")
        header = image.crop((2, 2, image.width - 2, 34))
        body = image.crop((2, 40, image.width - 2, min(image.height - 2, 72)))

        def dominant(crop):
            colours = crop.getcolors(crop.width * crop.height)
            colours.sort(reverse=True)
            background = colours[0][1]
            # Text colour: the most frequent colour far from the background.
            frequent = [c for count, c in colours[1:] if count >= 15]
            text = max(
                frequent,
                key=lambda c: sum(abs(a - b) for a, b in zip(c, background)),
                default=None,
            )
            return background, text

        header_bg, header_text = dominant(header)
        body_bg, body_text = dominant(body)
        hexed = lambda c: None if c is None else "#%02X%02X%02X" % c  # noqa: E731
        return {
            "method": "st.dataframe is a canvas: dominant colours of a screenshot, "
                      "header band y=2..34 px, first rows y=40..72 px",
            "header_bg": hexed(header_bg),
            "header_text": hexed(header_text),
            "body_bg": hexed(body_bg),
            "body_text": hexed(body_text),
        }


# ---------------------------------------------------------------------------
# S-5: narrow window
# ---------------------------------------------------------------------------

SCROLL_JS = """
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const wide = [...main.querySelectorAll('*')].filter(e => {
    if (e.offsetParent === null) return false;
    const r = e.getBoundingClientRect();
    return r.right > window.innerWidth + 1 && r.width > 0;
  }).slice(0, 5).map(e => (e.dataset.testid || e.tagName) + ' right=' + Math.round(e.getBoundingClientRect().right));
  return {
    doc_scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    doc_hscroll: document.documentElement.scrollWidth > window.innerWidth,
    main_scrollWidth: main.scrollWidth,
    main_clientWidth: main.clientWidth,
    main_hscroll: main.scrollWidth > main.clientWidth,
    overflowing: wide,
  };
}
"""


def s5_phase(page) -> dict:
    out = {"tabs": {}, "sidebar": {}}
    page.set_viewport_size(dict(S5_VIEWPORT))
    page.wait_for_timeout(800)
    for theme in (RECORDER.theme,):
        for top in TOP_TABS:
            mgs.open_tab(page, top)
            page.wait_for_timeout(500)
            numbers = page.evaluate(SCROLL_JS)
            name = f"s5_{list(TOP_TABS).index(top) + 1}_{THEME_SLUG[theme]}.png"
            page.screenshot(path=str(KADRY / name))
            numbers["frame"] = name
            out["tabs"][top] = numbers
            print(f"  s5 {theme} {top}: {numbers['doc_scrollWidth']}/{numbers['innerWidth']} "
                  f"main {numbers['main_scrollWidth']}/{numbers['main_clientWidth']}", flush=True)
        mgs.open_tab(page, "Расчёты")
        collapse = page.locator('[data-testid="stSidebarCollapseButton"] button, '
                                '[data-testid="stSidebarCollapseButton"]').first
        page.locator('[data-testid="stSidebar"]').hover()
        page.wait_for_timeout(300)
        collapse.click(force=True)
        page.wait_for_timeout(1000)
        expand = page.locator('[data-testid="stExpandSidebarButton"]').first
        box = expand.bounding_box() if expand.count() else None
        page.mouse.move(600, 500)
        page.wait_for_timeout(400)
        visible_idle = expand.is_visible() if expand.count() else False
        style = page.evaluate(
            """() => { const e = document.querySelector('[data-testid="stExpandSidebarButton"]');
                       if (!e) return null; const s = getComputedStyle(e);
                       return {opacity: s.opacity, visibility: s.visibility, color: s.color}; }"""
        )
        name = f"s5_panel_svyornuta_{THEME_SLUG[theme]}.png"
        page.screenshot(path=str(KADRY / name))
        doc = page.evaluate(SCROLL_JS)
        out["sidebar"] = {
            "expand_button_count": expand.count(),
            "expand_button_visible": visible_idle,
            "expand_button_box": box,
            "expand_button_style": style,
            "hscroll_after_collapse": doc,
            "frame": name,
        }
        print(f"  s5 {theme} collapse: visible={visible_idle} box={box}", flush=True)
        expand.click()
        page.wait_for_timeout(800)
    page.set_viewport_size(dict(VIEWPORT))
    page.wait_for_timeout(500)
    return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def extras_diagrammy_21d(page):
    """21-D: frames 16 and 17 only; the phase-fraction map (18) is not taken."""

    mgs.open_tab(page, "Диаграммы")
    run_subtab(page, "Многокомпонентное T–X", "Построить многокомпонентное сечение",
               "diagrammy_mnogokomponentnoe",
               "Диаграммы / Многокомпонентное T–X: значения по умолчанию")
    run_subtab(page, "Тройная при T = const", "Построить тройную диаграмму",
               "diagrammy_troynaya", "Диаграммы / Тройная при T = const: значения по умолчанию")


SCENARIO_EXTRAS = {
    "diagrammy": extras_diagrammy_21d,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--phases", default="kadry")
    parser.add_argument("--only", default=DEFAULT_SCENARIOS, help="scenario names, as in make_guide_screens")
    parser.add_argument("--out", default="", help="trial runs: write frames and JSON here")
    parser.add_argument("--theme", choices=THEMES, required=True)
    arguments = parser.parse_args()
    global KADRY, MANIFEST, MEASUREMENTS
    if arguments.out:
        KADRY = Path(arguments.out)
        MANIFEST = KADRY / "_manifest.json"
        MEASUREMENTS = KADRY / "izmereniya.json"
    phases = [item.strip() for item in arguments.phases.split(",") if item.strip()]

    free = free_gib()
    print(f"free memory {free:.2f} GiB", flush=True)
    if free < MIN_FREE_GIB:
        print(f"STOP: free memory below {MIN_FREE_GIB} GiB", file=sys.stderr)
        return 3
    if not mgs.app_is_ready(arguments.port):
        print(f"STOP: no app on port {arguments.port}", file=sys.stderr)
        return 2
    KADRY.mkdir(parents=True, exist_ok=True)
    theme = arguments.theme
    RECORDER.theme = theme
    if MANIFEST.exists():
        # Frames of the other theme stay; this theme is taken again from 01.
        RECORDER.frames = [
            frame
            for frame in json.loads(MANIFEST.read_text(encoding="utf-8"))["frames"]
            if frame["theme"] != theme
        ]

    names = mgs.SCENARIO_ORDER
    if arguments.only:
        wanted = {item.strip() for item in arguments.only.split(",")}
        names = [name for name in names if name in wanted]

    from playwright.sync_api import sync_playwright

    measurements = (
        json.loads(MEASUREMENTS.read_text(encoding="utf-8")) if MEASUREMENTS.exists() else {}
    )
    mine = measurements.setdefault(theme, {})
    mine["theme_method"] = (
        "default session (System theme, browser prefers light)" if theme == "Light"
        else "URL query ?embed_options=dark_theme"
    )

    def save_measurements() -> None:
        MEASUREMENTS.write_text(
            json.dumps(measurements, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    log: list[dict] = []
    started = time.monotonic()
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
        context.set_default_timeout(mgs.UI_TIMEOUT_MS)
        page = context.new_page()
        query = "?embed_options=dark_theme" if theme == "Dark" else ""
        page.goto(f"http://127.0.0.1:{arguments.port}/{query}", wait_until="domcontentloaded")
        page.get_by_role("tab", name="Расчёты", exact=True).wait_for(timeout=mgs.CALC_TIMEOUT_MS)
        mgs.wait_idle(page)
        expand = page.locator('[data-testid="stExpandSidebarButton"]')
        if expand.count() and expand.first.is_visible():
            expand.first.click()
            mgs.wait_idle(page)
        page.wait_for_timeout(500)
        if current_theme(page) != theme:
            raise RuntimeError(f"Session did not open in {theme}: {page.evaluate(APP_BG_JS)}")
        mine["app_background"] = page.evaluate(APP_BG_JS)

        try:
            if "kadry" in phases:
                for name in names:
                    print(f"[{name}] free {free_gib():.2f} GiB", flush=True)
                    step = time.monotonic()
                    try:
                        if name == "kinetika":
                            run_kinetika(page, log)
                        else:
                            mgs.SCENARIOS[name](page, log)
                        if name in SCENARIO_EXTRAS:
                            SCENARIO_EXTRAS[name](page)
                    except Exception as error:  # noqa: BLE001
                        # One broken scenario must not cost the other frames.
                        print(f"  SCENARIO FAILED {name}: {type(error).__name__}: "
                              f"{str(error).splitlines()[0]}", flush=True)
                        page.screenshot(path=str(KADRY / f"_sboy_{name}.png"))
                        mgs.CALC_TIMEOUT_MS = KINETIKA_WAIT["saved"]
                    print(f"  -- {time.monotonic() - step:.0f} s", flush=True)
                if not arguments.only or "soobshcheniya" in arguments.only:
                    print("[soobshcheniya]", flush=True)
                    mine["messages"] = error_frame(page)
                    save_measurements()
            if "izmer" in phases:
                print("[izmer]", flush=True)
                if "kadry" in phases:
                    mine.update(measure_phase(page))
                else:
                    measure_only(page, mine)
                save_measurements()
            if "s5" in phases:
                print("[s5]", flush=True)
                mine["s5"] = s5_phase(page)
                save_measurements()
        finally:
            if log:
                (KADRY.parent / f"scenario_log_{THEME_SLUG[theme]}.json").write_text(
                    json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            try:
                page.screenshot(path=str(KADRY / f"_last_state_{THEME_SLUG[theme]}.png"))
            except Exception:  # noqa: BLE001
                pass
            browser.close()
    print(f"done in {time.monotonic() - started:.0f} s; frames {len(RECORDER.frames)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
