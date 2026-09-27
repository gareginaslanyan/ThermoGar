#!/usr/bin/env python3
"""21-Ю, BL-78: «Предварительный просмотр» пакетного расчёта — теми же словами,
что сводка расчёта и боковая панель.

База, основа и единицы — как в ``batch_summary_display``; режим стали у строк
стали — подписью боковой панели (``steel_mode_label``), у строк Ni и Al —
пусто (на экране прочерк), нераспознанное значение — как в файле. Входная
таблица не меняется: разбор, ``batch_source_digest``, расчёт и выгрузки
берут её.

Запуск (пофайлово):
    <root>/.venv-windows/Scripts/python.exe -B -X utf8 -m pytest tools/test_wave21_yu.py -q
"""

from __future__ import annotations

import csv
import sys
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
for entry in (ROOT / "app", ROOT / "tools"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import thermogar_verified_state as verified_state
from thermogar_release_policy import RELEASE_DATABASE_LABELS
from thermogar_workspace import (
    BATCH_PREVIEW_LABELS,
    batch_preview_dataframe,
    batch_table_dataframe,
    steel_mode_label,
)

ROWS = (
    {"Название": "Ni–12Al", "База": "ni", "Основа": "Ni", "Единицы": "ат.%",
     "Температура, °C": "700", "Добавки": "Al=12", "Режим стали": ""},
    {"Название": "Fe-мета", "База": "fe", "Основа": "FE", "Единицы": "мас.%",
     "Температура, °C": "700", "Добавки": "C=0.8", "Режим стали": "метастабильный"},
    {"Название": "Fe-стаб", "База": "fe", "Основа": "Fe", "Единицы": "мас.%",
     "Температура, °C": "700", "Добавки": "C=0.8", "Режим стали": "стабильный"},
    {"Название": "Fe-опечатка", "База": "fe", "Основа": "FE", "Единицы": "мас.%",
     "Температура, °C": "700", "Добавки": "C=0.8", "Режим стали": "metastabe"},
    {"Название": "Al-стаб", "База": "al", "Основа": "AL", "Единицы": "ат.%",
     "Температура, °C": "500", "Добавки": "CU=4", "Режим стали": "stable"},
)


def _source() -> pd.DataFrame:
    output = StringIO(newline="")
    writer = csv.writer(output, delimiter=",", lineterminator="\n")
    writer.writerow(verified_state.TEMPLATE_HEADERS)
    for row in ROWS:
        writer.writerow([row.get(header, "") for header in verified_state.TEMPLATE_HEADERS])
    table = verified_state._parse_csv(output.getvalue().encode("utf-8"))
    return batch_table_dataframe(table)


@pytest.fixture(scope="module")
def source() -> pd.DataFrame:
    return _source()


@pytest.fixture(scope="module")
def preview(source: pd.DataFrame) -> pd.DataFrame:
    return batch_preview_dataframe(source)


def test_column_labels_unchanged(source: pd.DataFrame, preview: pd.DataFrame) -> None:
    expected = [BATCH_PREVIEW_LABELS.get(str(column), column) for column in source.columns]
    assert list(preview.columns) == expected


def test_database_labels(preview: pd.DataFrame) -> None:
    assert list(preview["База"]) == [
        RELEASE_DATABASE_LABELS[key] for key in ("ni", "fe", "fe", "fe", "al")
    ]


def test_balance_symbols(preview: pd.DataFrame) -> None:
    assert list(preview["Основа"]) == ["Ni", "Fe", "Fe", "Fe", "Al"]


def test_units_words(preview: pd.DataFrame) -> None:
    assert list(preview["Единицы"]) == ["ат.%", "мас.%", "мас.%", "мас.%", "ат.%"]


def test_steel_mode(preview: pd.DataFrame) -> None:
    modes = list(preview["Режим стали"])
    assert pd.isna(modes[0])
    assert modes[1] == steel_mode_label("metastable")
    assert modes[2] == steel_mode_label("stable")
    assert modes[3] == "metastabe"
    assert pd.isna(modes[4])


def test_composition_symbols(preview: pd.DataFrame) -> None:
    assert list(preview["Добавки"]) == ["Al=12", "C=0.8", "C=0.8", "C=0.8", "Cu=4"]


def test_source_table_unchanged() -> None:
    source = _source()
    before = source.copy(deep=True)
    batch_preview_dataframe(source)
    pd.testing.assert_frame_equal(source, before)
