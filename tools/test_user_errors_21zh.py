#!/usr/bin/env python3
"""21-Ж: своё сообщение ThermoGar против чужого исключения; символы элементов.

Лёгкий тест: приложение не запускается, равновесия не считаются.

* ``is_user_message`` истинно на своих исключениях (``UserValueError``,
  ``UserRuntimeError``, классы со своими русскими текстами,
  ``VerifiedLoaderError`` с признаком) и ложно на чужих.
* Новые классы — наследники ``ValueError`` / ``RuntimeError``: прежние
  ``except`` их ловят.
* Русские тексты ``VerifiedLoaderError`` (21-Ж, шаг 1 в) идут через
  ``_fail_user``; английские — через ``_fail`` без признака.
* Текст чужого исключения не попадает в подсказку ``_friendly_error_text``.
* ``element_symbol``: NI → Ni, AL → Al, CR → Cr, C → C.
* Разбор «Добавок» не зависит от регистра: «Al=15, cr=10» и «AL=15, CR=10».

Запуск:
    <root>/.venv-windows/Scripts/python.exe -B -m pytest tools/test_user_errors_21zh.py -v
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

import thermogar_verified_loaders as verified_loaders  # noqa: E402
from thermogar_user_errors import (  # noqa: E402
    UserMessage,
    UserRuntimeError,
    UserValueError,
    element_column_label,
    element_columns_for_display,
    element_symbol,
    element_symbols,
    is_user_message,
    user_message_text,
)

APP = ROOT / "app"
CYRILLIC = re.compile("[А-Яа-яЁё]")


# ---------------------------------------------------------------------------
# is_user_message и наследование
# ---------------------------------------------------------------------------


def test_new_classes_inherit_previous_ones() -> None:
    assert issubclass(UserValueError, ValueError)
    assert issubclass(UserRuntimeError, RuntimeError)
    assert issubclass(UserValueError, UserMessage)
    assert issubclass(UserRuntimeError, UserMessage)
    with pytest.raises(ValueError):
        raise UserValueError("Сумма добавок должна быть меньше 100 %.")
    with pytest.raises(RuntimeError):
        raise UserRuntimeError("Параллельный расчёт прерван. Повторите действие.")


def test_old_except_clauses_still_catch() -> None:
    caught = []
    for error in (UserValueError("свой"), UserRuntimeError("свой")):
        try:
            raise error
        except (ValueError, RuntimeError) as exception:
            caught.append(exception)
    assert caught and all(is_user_message(item) for item in caught)


@pytest.mark.parametrize(
    "error",
    [
        UserValueError("Сумма добавок должна быть меньше 100 %."),
        UserRuntimeError("Модуль Scheil–Gulliver недоступен."),
    ],
)
def test_own_messages(error: Exception) -> None:
    assert is_user_message(error)
    assert user_message_text(error) == str(error)


@pytest.mark.parametrize(
    "error",
    [
        ValueError("Number of degrees of freedom is not zero"),
        RuntimeError("Singular matrix"),
        KeyError("NI"),
        ZeroDivisionError("division by zero"),
        verified_loaders.VerifiedLoaderError(
            verified_loaders.ReasonCode.INPUT_INVALID,
            "composition_pct must be a plain object.",
        ),
        None,
    ],
)
def test_foreign_exceptions(error: Exception | None) -> None:
    assert not is_user_message(error)
    if error is not None:
        assert user_message_text(error) == ""


def test_classes_with_own_russian_texts_are_marked() -> None:
    from thermogar_database_guard import KnownFeDatabaseIssue
    from thermogar_parallel import DatabaseIdentityError, ParallelEngineError, WorkerLostError
    from thermogar_properties import PropertyCalculationError
    from thermogar_release_policy import PhasePresetError

    for cls in (
        KnownFeDatabaseIssue,
        ParallelEngineError,
        DatabaseIdentityError,
        WorkerLostError,
        PropertyCalculationError,
        PhasePresetError,
    ):
        assert issubclass(cls, UserMessage), cls
    error = PropertyCalculationError(
        "STRENGTHENING_PROVENANCE_REQUIRED",
        "Укажите источник и область применимости всех коэффициентов.",
    )
    assert isinstance(error, ValueError)
    assert is_user_message(error)


# ---------------------------------------------------------------------------
# VerifiedLoaderError: признак у русских текстов
# ---------------------------------------------------------------------------


def test_verified_loader_error_user_flag() -> None:
    reason = verified_loaders.ReasonCode.INPUT_INVALID
    own = verified_loaders.VerifiedLoaderError(
        reason, "На выбранном наборе элементов не осталось допустимых фаз: …", user_message=True
    )
    assert is_user_message(own)
    # На экран — текст без кода причины; str() для отчёта прежний.
    assert user_message_text(own) == "На выбранном наборе элементов не осталось допустимых фаз: …"
    assert str(own).startswith("INPUT_INVALID: ")
    service = verified_loaders.VerifiedLoaderError(
        verified_loaders.ReasonCode.USER_INPUT_REQUIRED,
        "Strengthening input provenance is required.",
        user_text="Укажите источник и область применимости всех коэффициентов.",
    )
    assert is_user_message(service)
    assert user_message_text(service) == "Укажите источник и область применимости всех коэффициентов."
    assert str(service) == "USER_INPUT_REQUIRED: Strengthening input provenance is required."


def _fail_calls(module: str) -> list[tuple[str, int, bool]]:
    """(имя вызова, строка, русский ли текст) для _fail / _fail_user модуля."""

    source = (APP / module).read_text("utf-8")
    calls = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("_fail", "_fail_user")
            and len(node.args) == 2
        ):
            text = ast.get_source_segment(source, node.args[1]) or ""
            calls.append((node.func.id, node.lineno, bool(CYRILLIC.search(text))))
    return calls


def test_russian_verified_texts_carry_user_flag() -> None:
    physical = _fail_calls("thermogar_verified_physical.py")
    properties = _fail_calls("thermogar_verified_properties.py")
    own = [call for call in physical + properties if call[0] == "_fail_user"]
    # Пять текстов по заданию и шестой — правило смеси (thermogar_physical
    # .mixture_unavailable_message, тоже русский) — отступление в отчёте.
    assert len(own) == 6, own
    for name, line, russian in physical + properties:
        if name == "_fail":
            assert not russian, f"русский текст без признака, строка {line}"


@pytest.mark.parametrize(
    "module", ["thermogar_verified_physical", "thermogar_verified_properties"]
)
def test_fail_user_sets_flag(module: str) -> None:
    imported = __import__(module)
    with pytest.raises(verified_loaders.VerifiedLoaderError) as caught:
        imported._fail_user(
            verified_loaders.ReasonCode.DATA_UNAVAILABLE,
            "Объём фазы X не получен: объёмные доли фаз для VRH посчитать нельзя.",
        )
    assert is_user_message(caught.value)
    with pytest.raises(verified_loaders.VerifiedLoaderError) as caught:
        imported._fail(verified_loaders.ReasonCode.INPUT_INVALID, "Composition units must be wt or at.")
    assert not is_user_message(caught.value)


# ---------------------------------------------------------------------------
# Подсказка ошибки: чужой текст не выходит на экран
# ---------------------------------------------------------------------------


def test_friendly_text_hides_foreign_message() -> None:
    import thermogar_stage14 as stage14

    foreign = ValueError("Number of degrees of freedom is not zero")
    title, action = stage14._friendly_error_text(foreign, "равновесие при одной температуре")
    assert "degrees of freedom" not in title + action
    own = UserValueError("Конечная температура должна быть выше начальной.")
    title, action = stage14._friendly_error_text(own, "сканирование по температуре")
    assert title == "Диапазон температур задан неверно."
    own_other = UserValueError("Выбранная для карты фаза исключена галочками.")
    title, action = stage14._friendly_error_text(own_other, "карта")
    assert action == "Выбранная для карты фаза исключена галочками."


# ---------------------------------------------------------------------------
# Символы элементов
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "shown"),
    [("NI", "Ni"), ("AL", "Al"), ("CR", "Cr"), ("C", "C"), ("FE", "Fe"),
     ("ni", "Ni"), ("Cr", "Cr"), ("MO", "Mo"), ("W", "W"), (" nb ", "Nb")],
)
def test_element_symbol(raw: str, shown: str) -> None:
    assert element_symbol(raw) == shown


def test_element_symbols_and_columns() -> None:
    assert element_symbols(["AL", "CR", "NI"]) == "Al, Cr, Ni"
    assert element_column_label("NI, ат.%") == "Ni, ат.%"
    assert element_column_label("X(AL)") == "X(Al)"
    assert element_column_label("CR, матрица, ат.%") == "Cr, матрица, ат.%"
    # Имена фаз и голые короткие имена столбцов не трогаются.
    for column in ("FCC_A1", "NI3AL", "NP", "P", "T", "Фаза", "LIQUID"):
        assert element_column_label(column) == column
    import pandas as pd

    table = pd.DataFrame({"Фаза": ["FCC_A1"], "NI, ат.%": [80.0], "AL, ат.%": [20.0]})
    shown = element_columns_for_display(table)
    assert list(shown.columns) == ["Фаза", "Ni, ат.%", "Al, ат.%"]
    # Сама таблица (данные и выгрузки) не меняется.
    assert list(table.columns) == ["Фаза", "NI, ат.%", "AL, ат.%"]


def _app_function(name: str):
    """Функция из ThermoGar_app.py без запуска страницы Streamlit."""

    source = (APP / "ThermoGar_app.py").read_text("utf-8")
    tree = ast.parse(source)
    node = next(
        item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name
    )
    namespace = {
        "re": re,
        "UserValueError": UserValueError,
        "element_symbol": element_symbol,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), "ThermoGar_app.py", "exec"), namespace)
    return namespace[name]


def test_sidebar_composition_parse_is_case_insensitive() -> None:
    parse_composition = _app_function("parse_composition")
    assert parse_composition("Al=15, cr=10") == parse_composition("AL=15, CR=10") == {
        "AL": 15.0,
        "CR": 10.0,
    }
    with pytest.raises(UserValueError) as caught:
        parse_composition("Cr=5, cr=3")
    assert str(caught.value) == "Элемент Cr указан более одного раза."


def test_context_validation_is_case_insensitive() -> None:
    import thermogar_workspace as workspace

    base = {
        "database_key": "ni",
        "balance": "NI",
        "units": "at",
        "pressure_pa": 101325.0,
        "steel_mode": "metastable",
    }
    lower = workspace.validate_context_payload({**base, "composition": "Al=15, cr=10"})
    upper = workspace.validate_context_payload({**base, "composition": "AL=15, CR=10"})
    assert {key: value for key, value in lower.items() if key != "composition"} == {
        key: value for key, value in upper.items() if key != "composition"
    }
    with pytest.raises(UserValueError) as caught:
        workspace.validate_context_payload({**base, "composition": "ZN=1"})
    assert str(caught.value) == "Элемента Zn нет в базе «Никелевые сплавы — mc_ni 2.036»."


# ---------------------------------------------------------------------------
# Подписи 21-Ж: «точки одновременно», подсказки недоступных кнопок
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("count", "at_once", "per"),
    [
        (1, "1 точка одновременно", "по 1 точке одновременно"),
        (2, "2 точки одновременно", "по 2 точки одновременно"),
        (4, "4 точки одновременно", "по 4 точки одновременно"),
        (5, "5 точек одновременно", "по 5 точек одновременно"),
        (11, "11 точек одновременно", "по 11 точек одновременно"),
        (12, "12 точек одновременно", "по 12 точек одновременно"),
        (14, "14 точек одновременно", "по 14 точек одновременно"),
        (21, "21 точка одновременно", "по 21 точке одновременно"),
        (22, "22 точки одновременно", "по 22 точки одновременно"),
        (25, "25 точек одновременно", "по 25 точек одновременно"),
    ],
)
def test_parallel_point_forms(count: int, at_once: str, per: str) -> None:
    import thermogar_parallel_ui as parallel_ui

    assert parallel_ui.points_at_once_label(count) == at_once
    assert parallel_ui.points_per_label(count) == per


def test_rejection_help_has_no_reason_code() -> None:
    import thermogar_release_ui as release_ui

    class Receipt:
        def __init__(self, code: str) -> None:
            self.reason_code = code
            self.reason_detail = "Feature inputs must be a plain object."

    assert release_ui.rejection_help_text(Receipt("INPUT_INVALID")) == (
        "Введённые значения не проходят проверку."
    )
    assert release_ui.rejection_help_text(Receipt("SOMETHING_NEW")) == (
        "Действие недоступно: исходные данные не прошли проверку."
    )
    for code, text in release_ui.REJECTION_HELP_TEXTS.items():
        assert code not in text and not re.search("[A-Z]{2,}_[A-Z]", text)


def test_batch_row_error_text() -> None:
    import thermogar_workspace as workspace

    collected: list[Exception] = []
    assert workspace.batch_row_error_text(UserValueError("Таблица пуста."), collected) == "Таблица пуста."
    assert collected == []
    foreign = RuntimeError("ValueError: Singular matrix")
    assert workspace.batch_row_error_text(foreign, collected) == "расчёт строки не выполнен"
    assert collected == [foreign]
