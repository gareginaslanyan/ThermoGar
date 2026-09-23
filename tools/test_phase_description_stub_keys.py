"""Описания фаз вместо заглушки — по таблице разметки 19-В (BL-58, 19-В2).

Там, где ``translate_phase_description`` возвращала заглушку «Русская
расшифровка для этой специализированной фазы ещё не добавлена.», теперь
берётся сборка утверждённых фраз из ``app/thermogar_phase_descriptions.py``
по паре (имя фазы, описание). Нет пары в таблице — заглушка, как было.

Функция берётся из исходника приложения без запуска Streamlit тем же путём,
что в ``tools/test_phase_description_order_words.py``.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -m pytest tools/test_phase_description_stub_keys.py -v
"""

from __future__ import annotations

import ast
import importlib
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

STUB = "Русская расшифровка для этой специализированной фазы ещё не добавлена."

# Фразы, утверждённые владельцем 23.09.2026 (задание 19-В2, шаг 3).
NEW_PHRASES = {
    "S_CUB": "Кубическая структура.",
    "S_TET": "Тетрагональная структура.",
    "S_ORT": "Ромбическая структура.",
    "S_MON": "Моноклинная структура.",
    "S_HEX": "Гексагональная структура.",
    "S_RHO": "Ромбоэдрическая структура.",
    "C_INT": "Интерметаллидная фаза.",
    "C_SIL": "Силицидная фаза.",
    "C_GAS": "Газовая фаза.",
    "R_DISP": "Дисперсоид.",
    "R_DISPU": "Упрочняющий дисперсоид.",
    "R_UPR": "Упрочняющая фаза.",
    "R_TPU": "Топологически плотноупакованная (ТПУ) фаза.",
    "R_OXR": "Может охрупчивать сплав.",
    "R_TVXR": "Твёрдая и хрупкая фаза.",
    "T_HIGH": "Высокотемпературная модификация.",
    "T_LOW": "Низкотемпературная модификация.",
    "SL_EQ": "Служебная фаза базы: только для расчёта равновесия.",
    "SL_TD": "Служебная фаза базы: только для расчёта термодинамических свойств.",
}

# Фразы, которые уже есть литералами в translate_phase_description.
EXISTING_KEYS = (
    "S_BCC", "S_FCC", "S_HCP", "C_OX", "C_BOR", "C_SUL", "C_CAR", "C_NIT", "C_LAV", "U_EQ", "U_MET",
)

KEY_ORDER = (
    "S_CUB", "S_TET", "S_ORT", "S_MON", "S_HEX", "S_RHO", "S_BCC", "S_FCC", "S_HCP",
    "C_INT", "C_SIL", "C_GAS", "C_OX", "C_BOR", "C_SUL", "C_CAR", "C_NIT", "C_LAV",
    "R_DISP", "R_DISPU", "R_UPR", "R_TPU", "R_OXR", "R_TVXR",
    "U_EQ", "U_MET", "T_HIGH", "T_LOW", "SL_EQ", "SL_TD",
)

# Группы, из которых в наборе ключей пары не больше одного.
AT_MOST_ONE = (
    tuple(key for key in KEY_ORDER if key.startswith("S_")),
    tuple(key for key in KEY_ORDER if key.startswith("C_")),
    ("R_DISP", "R_DISPU"),
    ("R_OXR", "R_TVXR"),
    ("U_EQ", "U_MET"),
    ("T_HIGH", "T_LOW"),
    ("SL_EQ", "SL_TD"),
)


@pytest.fixture(scope="module")
def module() -> Any:
    return importlib.import_module("thermogar_phase_descriptions")


def _app_tree() -> ast.Module:
    return ast.parse(APP_PATH.read_text("utf-8"))


@pytest.fixture(scope="module")
def translate() -> Any:
    tree = _app_tree()
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


def _translate_literals() -> set[str]:
    for node in _app_tree().body:
        if isinstance(node, ast.FunctionDef) and node.name == "translate_phase_description":
            return {
                sub.value
                for sub in ast.walk(node)
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
            }
    raise AssertionError("translate_phase_description not found")


# а) новые фразы побайтно.
def test_new_phrases_bytewise(module):
    for key, phrase in NEW_PHRASES.items():
        assert module.PHRASES[key].encode("utf-8") == phrase.encode("utf-8"), key


def test_phrase_keys_and_order(module):
    assert tuple(module.KEY_ORDER) == KEY_ORDER
    assert set(module.PHRASES) == set(KEY_ORDER)
    assert len(module.PHRASES) == 30


# б) прежние фразы — литералы функции.
def test_existing_phrases_are_translate_literals(module):
    literals = _translate_literals()
    for key in EXISTING_KEYS:
        assert module.PHRASES[key] in literals, key


# в) таблица пар.
def test_stub_keys_table(module):
    table = module.STUB_KEYS
    assert len(table) == 77
    for pair, keys in table.items():
        assert isinstance(pair, tuple) and len(pair) == 2, pair
        assert keys, pair
        assert all(key in KEY_ORDER for key in keys), pair
        positions = [KEY_ORDER.index(key) for key in keys]
        assert positions == sorted(positions) and len(set(positions)) == len(positions), pair
        for group in AT_MOST_ONE:
            assert sum(key in group for key in keys) <= 1, (pair, group)


def test_phrases_for(module):
    pair, keys = next(iter(module.STUB_KEYS.items()))
    assert module.phrases_for(*pair) == " ".join(module.PHRASES[key] for key in keys)
    assert module.phrases_for("ZZZ", "Orthorhombic.") is None


# г) translate_phase_description.
def test_translate_uses_table(translate):
    assert translate("CR2B", "Orthorhombic.", "") == "Ромбическая структура. Боридная фаза."


@pytest.mark.parametrize(
    ("phase", "description"),
    (("ZZZ", "Orthorhombic."), ("SPINEL", "Fe-Cr-Spinel")),
)
def test_translate_without_pair_keeps_stub(translate, phase, description):
    assert translate(phase, description, "") == STUB


def test_translate_old_path_unchanged(translate):
    assert (
        translate("X", "Body-centered cubic Ferrite phase.", "")
        == "Объёмно-центрированная кубическая фаза феррита."
    )
