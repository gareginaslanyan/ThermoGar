"""``ordered``/``disordered`` в описании фазы — по целому слову (BL-55, 19-А).

``translate_phase_description`` искала подстроку ``ordered``, а она входит в
``disordered``: разупорядоченная фаза получала обе фразы. Теперь обе проверки
идут по целому слову и независимы друг от друга.

Функция берётся из исходника приложения без запуска Streamlit тем же путём,
что фикстура ``app`` в ``tools/test_equilibrium_solidus_fallback.py``.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -m pytest tools/test_phase_description_order_words.py -v
"""

from __future__ import annotations

import ast
import sys
import warnings
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "app" / "ThermoGar_app.py"
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

APP_NAMES = ("EXACT_DESCRIPTION_TRANSLATIONS", "translate_phase_description")

ORDERED = "Упорядоченная фаза."
DISORDERED = "Разупорядоченная фаза."


@pytest.fixture(scope="module")
def translate() -> Any:
    tree = ast.parse(APP_PATH.read_text("utf-8"))
    wanted = set(APP_NAMES)
    header: list[ast.stmt] = []
    definitions: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            header.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted:
            definitions.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id in wanted for t in targets):
                definitions.append(node)
    namespace: dict[str, Any] = {"__file__": str(APP_PATH), "__name__": "thermogar_app_extract"}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        exec(
            compile(ast.Module(body=header + definitions, type_ignores=[]), str(APP_PATH), "exec"),
            namespace,
        )
    missing = wanted - set(namespace)
    assert not missing, sorted(missing)
    return namespace["translate_phase_description"]


def _parts(text: str) -> list[str]:
    return [part if part.endswith(".") else part + "." for part in text.split(". ")]


@pytest.mark.parametrize(
    "description",
    (
        "Disordered part of the sigma model.",
        "disordered FCC solid solution",
        "Chemically DISORDERED phase",
    ),
)
def test_disordered_gives_only_disordered_phrase(translate, description):
    result = translate("X", description, "")
    parts = _parts(result)
    assert DISORDERED in parts
    assert ORDERED not in parts


@pytest.mark.parametrize(
    "description",
    (
        "Ordered L12 phase.",
        "chemically ordered compound",
        "ORDERED intermetallic",
    ),
)
def test_ordered_gives_only_ordered_phrase(translate, description):
    result = translate("X", description, "")
    parts = _parts(result)
    assert ORDERED in parts
    assert DISORDERED not in parts


@pytest.mark.parametrize(
    "description",
    (
        "Ordered phase with a disordered counterpart.",
        "disordered and ordered parts of one model",
    ),
)
def test_both_words_give_both_phrases(translate, description):
    result = translate("X", description, "")
    parts = _parts(result)
    assert ORDERED in parts
    assert DISORDERED in parts
    assert parts.index(ORDERED) < parts.index(DISORDERED)


@pytest.mark.parametrize(
    "description",
    ("Unordered list of sites.", "reordered sublattice", "orderedness"),
)
def test_word_inside_another_word_gives_neither_phrase(translate, description):
    parts = _parts(translate("X", description, ""))
    assert ORDERED not in parts
    assert DISORDERED not in parts
