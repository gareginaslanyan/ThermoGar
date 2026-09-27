#!/usr/bin/env python3
"""21-Я, BL-79: русские надписи вместо английских надписей самого Streamlit 1.62.

Решения владельца 27.09.2026 (холст «ThermoGar: английские надписи Streamlit —
на «да»»): 0Б — надписи заменяются оформлением в app/style.css (отступление
от S-4), 1–8 — А, 10 — «Выбрать все», 11 — одна фраза на оба сообщения
списка «Фазы для сравнения — не более восьми». Проверяется:

* style.css: блок BL-79 есть; у каждого селектора — свой текст в ``content``
  дословно; английский текст скрыт ``font-size: 0``;
* .streamlit/config.toml: ``[server] maxUploadSize = 64`` и
  64 · 1024 · 1024 == MAX_WORKSPACE_FILE_BYTES;
* по AST: вызовов ``st.multiselect`` в app/*.py пять, у каждого
  ``placeholder="Выберите из списка"``;
* сторож Streamlit: версия 1.62.0 и строки в собранных файлах
  streamlit/static/static/js, на которые опираются селекторы и замены.

При обновлении Streamlit тест падает — замены из style.css (21-Я, ШАГ 4)
проверить заново на приложении.

Запуск (пофайлово):
    <root>/.venv-windows/Scripts/python.exe -B -X utf8 -m pytest tools/test_wave21_ya.py -q
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STYLE_PATH = ROOT / "app" / "style.css"
CONFIG_PATH = ROOT / ".streamlit" / "config.toml"
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

BL79_COMMENT = (
    "/* BL-79, решения владельца 27.09.2026 (холст «ThermoGar: английские надписи "
    "Streamlit — на «да»»: 0Б, 1–8 А, 10, 11): отступление от S-4 — надписи самого "
    "Streamlit 1.62 заменяются оформлением; сторож — tools/test_wave21_ya.py. */"
)

DROPZONE = '[data-testid="stFileUploaderDropzone"]'
INSTRUCTIONS = '[data-testid="stFileUploaderDropzoneInstructions"] span'
BUTTON_TEXT = (
    DROPZONE + ' button[data-testid="stBaseButton-secondary"] '
    '[data-testid="stMarkdownContainer"] p'
)
DRAG_TEXT = DROPZONE + " > div:not([data-testid]) > span"
FILE_TIP = '[data-testid="stTooltipErrorContent"]:not(:has([data-testid="stMarkdownContainer"]))'
NUMBER_TIP = '[data-testid="stTooltipErrorContent"]:has([data-testid="stMarkdownContainer"]) p'
NO_RESULTS = '[role="option"][style*="display: contents"] > span'
SELECT_ALL = '[role="option"][data-key="__select_all__"] > div'
SELECT_MATCHES = '[role="option"][data-key="__select_matches__"] > div'
ENERGY_NO_RESULTS = (
    '[role="listbox"][aria-label="Фазы для сравнения — не более восьми"] ' + NO_RESULTS
)

# Пункты решения владельца: селектор ::after и текст дословно.
REPLACEMENTS = (
    ("1", BUTTON_TEXT, "Выбрать файл"),
    ("2", ".st-key-batch_file_uploader " + INSTRUCTIONS, "CSV или XLSX, до 64 МБ"),
    ("2", ".st-key-project_uploader " + INSTRUCTIONS, "JSON, до 64 МБ"),
    ("2", ".st-key-alloy_library_uploader " + INSTRUCTIONS, "JSON, до 64 МБ"),
    ("3", DRAG_TEXT, "Отпустите файл здесь"),
    ("5", FILE_TIP, "Файл не принят: не тот тип или больше 64 МБ."),
    ("6", NUMBER_TIP, "Число вне допустимых границ поля."),
    ("8", NO_RESULTS, "Ничего не найдено"),
    ("10", SELECT_ALL, "Выбрать все"),
    ("10", SELECT_MATCHES, "Выбрать все"),
    ("11", ENERGY_NO_RESULTS, "Ничего не найдено или уже выбрано восемь фаз."),
)

# Элементы с английским текстом: сам текст — font-size: 0, новый — ::after.
HIDDEN_TEXT = (
    BUTTON_TEXT,
    INSTRUCTIONS,
    DRAG_TEXT,
    FILE_TIP,
    NUMBER_TIP,
    NO_RESULTS,
    SELECT_ALL,
    SELECT_MATCHES,
)

PLACEHOLDER = "Выберите из списка"

STREAMLIT_VERSION = "1.62.0"
# Строки собранного фронтенда Streamlit 1.62.0 (замер мастера), на которые
# опираются селекторы и замены style.css.
STREAMLIT_JS_STRINGS = (
    (
        "FileUploader*.js",
        None,
        (
            "stFileUploaderDropzoneInstructions",
            "`Upload`",
            " per file",
            "`Drag and drop a file here`",
        ),
    ),
    (
        "utils*.js",
        "stFileChipName",
        ("stFileChipName", " files are not allowed.", "File must be "),
    ),
    ("Tooltip*.js", None, ("stTooltipErrorContent",)),
    ("NumberInput*.js", None, ("Number is outside the allowed range", "**Error**: ")),
    (
        "Multiselect*.js",
        None,
        (
            "`Select all`",
            "__select_all__",
            "__select_matches__",
            "`No results`",
            "You can only select up to",
            "display:`contents`",
        ),
    ),
    ("Selectbox*.js", None, ("`No results`",)),
)


def css_text() -> str:
    return STYLE_PATH.read_text("utf-8")


def css_rules() -> list[tuple[list[str], dict[str, str]]]:
    """Правила style.css: (селекторы, объявления)."""

    css = re.sub(r"/\*.*?\*/", "", css_text(), flags=re.S)
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


def declared(selector: str, name: str) -> list[str]:
    """Значения свойства ``name`` у всех правил, где есть ``selector``."""

    return [
        declarations[name]
        for selectors, declarations in css_rules()
        if selector in selectors and name in declarations
    ]


def test_bl79_block_is_last_in_style_css() -> None:
    text = css_text()
    assert text.count(BL79_COMMENT) == 1
    tail = text.split(BL79_COMMENT, 1)[1]
    assert "/*" not in tail, "блок BL-79 — последний в style.css, одним куском"


@pytest.mark.parametrize(
    ("point", "selector", "text"),
    REPLACEMENTS,
    ids=[f"p{point}-{index}" for index, (point, _, _) in enumerate(REPLACEMENTS)],
)
def test_replacement_text_is_verbatim(point: str, selector: str, text: str) -> None:
    assert declared(selector + "::after", "content") == [f'"{text}"'], point


@pytest.mark.parametrize("selector", HIDDEN_TEXT, ids=range(len(HIDDEN_TEXT)))
def test_english_text_is_hidden_and_after_keeps_size(selector: str) -> None:
    assert declared(selector, "font-size") == ["0"]
    # Прежний текст — 0.875rem (15.75 px при baseFontSize 18), замер 21-Я.
    assert declared(selector + "::after", "font-size") == ["0.875rem"]


def test_file_size_and_error_word_are_not_shown() -> None:
    assert declared('[data-testid="stFileChipName"] + *', "display") == ["none"]
    assert declared(NUMBER_TIP + " > *", "display") == ["none"]


def test_energy_phrase_overrides_no_results() -> None:
    rules = [
        (index, selector)
        for index, (selectors, declarations) in enumerate(css_rules())
        for selector in selectors
        if "content" in declarations
        and selector in (NO_RESULTS + "::after", ENERGY_NO_RESULTS + "::after")
    ]
    order = [selector for _, selector in sorted(rules)]
    assert order == [NO_RESULTS + "::after", ENERGY_NO_RESULTS + "::after"]


def test_upload_limit_matches_workspace_limit() -> None:
    from thermogar_secure_io import MAX_WORKSPACE_FILE_BYTES

    config = tomllib.loads(CONFIG_PATH.read_text("utf-8"))
    assert config["server"] == {"maxUploadSize": 64}
    assert 64 * 1024 * 1024 == MAX_WORKSPACE_FILE_BYTES


def multiselect_calls() -> list[tuple[str, ast.Call]]:
    calls = []
    for path in sorted((ROOT / "app").glob("*.py")):
        tree = ast.parse(path.read_text("utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "multiselect"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "st"
            ):
                calls.append((f"{path.name}:{node.lineno}", node))
    return calls


def test_every_multiselect_has_russian_placeholder() -> None:
    calls = multiselect_calls()
    assert len(calls) == 5, [where for where, _ in calls]
    for where, call in calls:
        placeholders = [
            keyword.value for keyword in call.keywords if keyword.arg == "placeholder"
        ]
        assert len(placeholders) == 1, where
        value = placeholders[0]
        assert isinstance(value, ast.Constant) and value.value == PLACEHOLDER, where


def streamlit_js_dir() -> Path:
    import streamlit

    return Path(streamlit.__file__).resolve().parent / "static" / "static" / "js"


def test_streamlit_version_is_pinned() -> None:
    import streamlit

    assert streamlit.__version__ == STREAMLIT_VERSION, (
        "Streamlit обновлён: замены BL-79 в style.css проверить заново (21-Я, ШАГ 4)."
    )


@pytest.mark.parametrize(
    ("pattern", "marker", "strings"),
    STREAMLIT_JS_STRINGS,
    ids=[pattern for pattern, _, _ in STREAMLIT_JS_STRINGS],
)
def test_streamlit_bundle_keeps_strings(pattern: str, marker: str | None, strings) -> None:
    files = sorted(streamlit_js_dir().glob(pattern))
    if marker is not None:
        files = [path for path in files if marker in path.read_text("utf-8")]
    assert files, pattern
    text = "".join(path.read_text("utf-8") for path in files)
    missing = [value for value in strings if value not in text]
    assert not missing, f"{pattern}: нет строк {missing}"
