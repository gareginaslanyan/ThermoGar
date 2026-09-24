"""Признак своего сообщения ThermoGar у исключения (21-Ж, шаг 1).

Решение владельца 24.09.2026: текст исключений сторонних библиотек не
выводится на основной экран — он уходит в свёрнутый блок «Технические
сведения» и в технический отчёт. Свои русские сообщения ThermoGar остаются на
экране. Различить их помогает примесь :class:`UserMessage`.

``UserValueError`` и ``UserRuntimeError`` — наследники ``ValueError`` и
``RuntimeError``: существующие ``except ValueError`` / ``except RuntimeError``
ловят их как раньше.

Здесь же — показ символов элементов вне графиков (21-Ж, шаг 4):
``element_symbol`` и подписи столбцов таблиц на экране.
"""

from __future__ import annotations

import re
from typing import Any


class UserMessage:
    """Примесь: текст исключения — своё сообщение ThermoGar для экрана."""

    @property
    def user_text(self) -> str:
        return str(self)


class UserValueError(UserMessage, ValueError):
    """Неверные исходные данные; текст — своё русское сообщение."""


class UserRuntimeError(UserMessage, RuntimeError):
    """Действие не выполнено; текст — своё русское сообщение."""


def is_user_message(error: BaseException | None) -> bool:
    """Истинно, если текст исключения — своё сообщение ThermoGar."""

    if error is None:
        return False
    if isinstance(error, UserMessage):
        return True
    # VerifiedLoaderError несёт признак полем: класс ошибки загрузчика один,
    # признак ставится только у своих русских текстов.
    return getattr(error, "user_message", False) is True


def user_message_text(error: BaseException) -> str:
    """Своё сообщение для экрана; пустая строка, если исключение чужое."""

    if not is_user_message(error):
        return ""
    text = getattr(error, "user_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    return str(error).strip()


def element_symbol(element: object) -> str:
    """Символ элемента для показа: первая буква заглавная, остальные строчные.

    Решение владельца 24.09.2026 (21-Ж, шаг 4): NI → Ni, AL → Al, CR → Cr,
    C → C. Только показ: данные, ключи и выгрузки хранят символ как есть.
    Имена фаз (FCC_A1, NI3AL) сюда не передаются.
    """

    text = str(element).strip()
    return text[:1].upper() + text[1:].lower()


def element_symbols(elements: object) -> str:
    """Перечень символов через запятую для текста на экране."""

    return ", ".join(element_symbol(element) for element in elements)  # type: ignore[union-attr]


# Символы химических элементов в верхнем регистре, как их хранят базы.
_ELEMENT_TOKENS = frozenset(
    (
        "H HE LI BE B C N O F NE NA MG AL SI P S CL AR K CA SC TI V CR MN FE "
        "CO NI CU ZN GA GE AS SE BR KR RB SR Y ZR NB MO TC RU RH PD AG CD IN "
        "SN SB TE I XE CS BA LA CE PR ND PM SM EU GD TB DY HO ER TM YB LU HF "
        "TA W RE OS IR PT AU HG TL PB BI PO AT RN FR RA AC TH PA U NP PU AM CM "
        "BK CF ES FM MD NO LR"
    ).split()
)
# «NI, ат.%», «CR, матрица, ат.%», «X(AL)»: символ стоит в начале подписи
# столбца. Голые имена столбцов («NP», «P», «T») не трогаются — это могут
# быть не элементы.
_ELEMENT_COLUMN_RE = re.compile(r"^(?P<prefix>X\()?(?P<symbol>[A-Z]{1,2})(?P<rest>\)|, .*)$")


def element_column_label(column: object) -> object:
    """Подпись столбца для экрана: символ элемента — Ni, Al, Cr (шаг 4)."""

    if not isinstance(column, str):
        return column
    match = _ELEMENT_COLUMN_RE.match(column)
    if match is None or match.group("symbol") not in _ELEMENT_TOKENS:
        return column
    if (match.group("prefix") is None) != (match.group("rest") != ")"):
        return column
    return (
        (match.group("prefix") or "")
        + element_symbol(match.group("symbol"))
        + match.group("rest")
    )


def element_columns_for_display(table: Any) -> Any:
    """Таблица для ``st.dataframe``: символы элементов в заголовках — Ni, Al, Cr.

    Только показ: сама таблица, выгрузки и ключи хранят прежние названия.
    """

    columns = getattr(table, "columns", None)
    if columns is None:
        return table
    mapping = {
        column: element_column_label(column)
        for column in columns
        if element_column_label(column) != column
    }
    return table.rename(columns=mapping) if mapping else table
