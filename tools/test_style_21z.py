"""Основная кнопка и карточки «Учебные примеры» в style.css (21-З).

* текст основной кнопки (#FFFFFF / #17181B) — только у активной кнопки;
  неактивную Streamlit рисует сам (фон прозрачный, текст fadedText40);
* наведение и фокус активной основной кнопки — фон и рамка #153F7F / #4587DE,
  текст к фону 10.25:1 и 4.88:1; в нажатии фон штатный;
* то же для stBaseButton-primaryFormSubmit;
* контейнер с рамкой «Учебные примеры» получает ключ по базе примера
  и белую поверхность А-8 (#FFFFFF / #1F2226) по классу ключа;
  других контейнеров с рамкой в app/*.py нет.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STYLE_PATH = ROOT / "app" / "style.css"
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

PRIMARY_KINDS = ("stBaseButton-primary", "stBaseButton-primaryFormSubmit")


def css_rules() -> list[tuple[list[str], dict[str, str]]]:
    """Правила style.css: (селекторы, объявления)."""

    css = re.sub(r"/\*.*?\*/", "", STYLE_PATH.read_text("utf-8"), flags=re.S)
    rules = []
    for block in css.split("}"):
        if "{" not in block:
            continue
        head, body = block.split("{", 1)
        selectors = [" ".join(part.split()) for part in head.split(",") if part.strip()]
        declarations = {}
        for item in body.split(";"):
            if ":" in item:
                name, value = item.split(":", 1)
                declarations[name.strip()] = value.strip()
        rules.append((selectors, declarations))
    return rules


def rules_for(testid: str) -> list[tuple[str, dict[str, str]]]:
    marker = f'button[data-testid="{testid}"]'
    return [
        (selector, declarations)
        for selectors, declarations in css_rules()
        for selector in selectors
        if selector.startswith(marker + ":") or selector.startswith(marker + " ")
        or selector == marker
    ]


def luminance(color: str) -> float:
    channels = [int(color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first: str, second: str) -> float:
    a, b = sorted((luminance(first), luminance(second)), reverse=True)
    return (a + 0.05) / (b + 0.05)


@pytest.mark.parametrize("testid", PRIMARY_KINDS)
def test_primary_text_rule_skips_disabled_button(testid):
    colored = [(s, d) for s, d in rules_for(testid) if "color" in d]
    assert colored, testid
    for selector, declarations in colored:
        assert ":not(:disabled)" in selector, selector
        assert declarations["color"] == "light-dark(#FFFFFF, #17181B) !important"
    selectors = {selector for selector, _ in colored}
    marker = f'button[data-testid="{testid}"]:not(:disabled)'
    assert {marker, marker + " *"} <= selectors
    # Ни одно правило не трогает неактивную кнопку.
    for selector, _ in rules_for(testid):
        assert ":disabled" not in selector.replace(":not(:disabled)", ""), selector


@pytest.mark.parametrize("testid", PRIMARY_KINDS)
@pytest.mark.parametrize("state", (":hover", ":focus-visible"))
def test_primary_hover_and_focus_colors(testid, state):
    selector = f'button[data-testid="{testid}"]:not(:disabled):not(:active){state}'
    found = [d for s, d in rules_for(testid) if s == selector]
    assert len(found) == 1, selector
    assert found[0]["background-color"] == "light-dark(#153F7F, #4587DE)"
    assert found[0]["border-color"] == "light-dark(#153F7F, #4587DE)"
    assert "color" not in found[0]


def test_primary_hover_contrast_values_of_the_master():
    assert round(contrast_ratio("#FFFFFF", "#153F7F"), 2) == 10.25
    assert round(contrast_ratio("#17181B", "#4587DE"), 2) == 4.88
    # Было: затемнение Streamlit на 15 % в тёмной теме.
    assert round(contrast_ratio("#17181B", "#1F6DDB"), 2) == 3.61


def test_pressed_primary_button_keeps_streamlit_background():
    for testid in PRIMARY_KINDS:
        for selector, declarations in rules_for(testid):
            if "background-color" in declarations:
                assert ":not(:active)" in selector, selector


def test_quick_example_card_gets_surface():
    surfaces = [
        d for selectors, d in css_rules()
        if 'div[class*="st-key-quick_example_card_"]' in selectors
    ]
    assert surfaces == [
        {"background-color": "light-dark(#FFFFFF, #1F2226)"}
    ]


def test_quick_example_cards_are_keyed_by_database():
    import thermogar_stage14

    containers: list[dict] = []

    class Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class FakeStreamlit:
        def markdown(self, *args, **kwargs) -> None: ...

        def caption(self, *args, **kwargs) -> None: ...

        def button(self, *args, **kwargs) -> bool:
            return False

        def container(self, *args, **kwargs):
            containers.append(kwargs)
            return Ctx()

    original = thermogar_stage14.st
    thermogar_stage14.st = FakeStreamlit()
    try:
        thermogar_stage14.render_quick_examples(lambda *args, **kwargs: None)
    finally:
        thermogar_stage14.st = original

    assert containers == [
        {"border": True, "key": f"quick_example_card_{key}"} for key in ("ni", "al", "fe")
    ]


def test_every_bordered_container_in_app_has_a_styled_key():
    """Контейнеры с рамкой в app/*.py: у каждого ключ, у ключа — поверхность."""

    found = []
    for path in sorted((ROOT / "app").glob("*.py")):
        tree = ast.parse(path.read_text("utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "container"):
                continue
            keywords = {kw.arg: kw.value for kw in node.keywords}
            border = keywords.get("border")
            if isinstance(border, ast.Constant) and border.value is True:
                key = keywords.get("key")
                found.append((path.name, node.lineno, ast.unparse(key) if key else None))
    assert [(name, key) for name, _line, key in found] == [
        ("thermogar_stage14.py", "f\"quick_example_card_{context['database_key']}\""),
    ]
