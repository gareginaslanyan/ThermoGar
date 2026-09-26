"""Проба 21-С (BL-68): показ пустых ячеек в st.dataframe и st.data_editor.

Отдельное маленькое приложение; код ThermoGar не импортирует и не меняет.
Адрес: ?page=t0|el|kal&v=a|a2|b|c|g0|g1
  a  — как сейчас (NaN/None показываются серым «None»);
  a2 — как сейчас + df.style.format(na_rep="—") (сверка замера мастера);
  b  — копия для показа: числа текстом, пусто — "";
  c  — то же, пусто — «—»;
  g0 — средство Streamlit 1.62: placeholder="" (данные не меняются);
  g1 — средство Streamlit 1.62: placeholder="—".
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Проба 21-С", layout="wide")

params = st.query_params
page = params.get("page", "t0")
variant = params.get("v", "a")

DASH = "—"


def shown_number(value: object) -> str:
    """Число текстом так, как его сейчас рисует st.dataframe без format.

    Правило Streamlit 1.62 (static/js/formatNumber.*.js): знаков после
    точки 4, а для 0 < |x| < 1e-4 — столько, каков порядок числа; хвостовые
    нули убираются; точка — десятичный знак; без разделителя тысяч.
    """
    number = float(value)
    if number == 0 or abs(number) >= 1e-4:
        decimals = 4
    else:
        decimals = abs(int(f"{number:e}".split("e")[1]))
    text = f"{number:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def display_copy(table: pd.DataFrame, empty: str) -> pd.DataFrame:
    """Копия для показа: числа — текстом, NaN/None — ``empty``; bool как есть."""
    shown = table.copy()
    for column in shown.columns:
        series = shown[column]
        if pd.api.types.is_bool_dtype(series):
            continue
        shown[column] = [
            empty
            if item is None or (isinstance(item, float) and math.isnan(item))
            else (
                shown_number(item)
                if isinstance(item, (int, float, np.floating, np.integer))
                and not isinstance(item, bool)
                else str(item)
            )
            for item in series.tolist()
        ]
        shown[column] = shown[column].astype(object)
    return shown


def t0_table() -> pd.DataFrame:
    """Похожа на таблицу T₀ (ThermoGar_app.py:4509–4516): C, T₀ °C, T₀ K, галочка."""
    carbon = np.array([0.2, 0.6, 1.0, 1.4, 1.8, 2.0])
    tzero_c = np.array([702.463712, 583.1172, 452.9, 98.70004, np.nan, np.nan])
    tzero_k = tzero_c + 273.15
    return pd.DataFrame(
        {
            "C, мас.%": carbon,
            "T₀, °C": tzero_c,
            "T₀, K": tzero_k,
            "Решение найдено": np.isfinite(tzero_k),
        }
    )


def elastic_table() -> pd.DataFrame:
    """Похожа на редактор «Упругих свойств» (ThermoGar_app.py:2321–2337)."""
    rows = [
        {
            "phase": "BCC_A2",
            "mole_fraction": 78.123456,
            "volume_fraction": 77.9,
            "young_gpa": 210.0,
            "poisson": 0.29,
            "origin": "справочно",
            "source": "ASM Handbook",
            "reference_temperature_c": 20.0,
            "note": "",
        },
        {
            "phase": "FCC_A1",
            "mole_fraction": 20.5,
            "volume_fraction": 20.71,
            "young_gpa": None,
            "poisson": None,
            "origin": None,
            "source": None,
            "reference_temperature_c": None,
            "note": "",
        },
        {
            "phase": "CEMENTITE",
            "mole_fraction": 1.376544,
            "volume_fraction": 1.39,
            "young_gpa": None,
            "poisson": None,
            "origin": None,
            "source": None,
            "reference_temperature_c": None,
            "note": "",
        },
    ]
    return pd.DataFrame(rows)


ELASTIC_LABELS = {
    "phase": "Фаза",
    "young_gpa": "E, ГПа",
    "poisson": "ν",
    "origin": "Происхождение",
    "source": "Источник",
    "reference_temperature_c": "Температура источника, °C",
    "note": "Примечание",
}


def elastic_config(text_numbers: bool) -> dict:
    fractions = {
        "mole_fraction": "Мольная доля фаз",
        "volume_fraction": "Объёмная доля фаз",
    }
    if text_numbers:
        return {
            **{key: st.column_config.TextColumn(label) for key, label in fractions.items()},
            **ELASTIC_LABELS,
        }
    return {
        **{key: st.column_config.NumberColumn(label) for key, label in fractions.items()},
        **ELASTIC_LABELS,
    }


def placeholder_kwargs() -> dict:
    if variant == "g0":
        return {"placeholder": ""}
    if variant == "g1":
        return {"placeholder": DASH}
    return {}


st.markdown(f"**Проба 21-С** · страница `{page}` · вариант `{variant}`")

if page == "kal":
    values = [702.463712, 98.70004, 0.000012345, 0.00056789, 1234567.891, 850.0, 1e-9, 0.1 + 0.2, -3.00005, 2.99996, 0.0]
    calib = pd.DataFrame({"x": values, "shown_number(x)": [shown_number(v) for v in values]})
    st.dataframe(calib, hide_index=True)
elif page == "t0":
    table = t0_table()
    if variant == "a":
        st.dataframe(table, width="stretch", hide_index=True)
    elif variant == "a2":
        st.dataframe(table.style.format(na_rep=DASH), width="stretch", hide_index=True)
    elif variant == "b":
        st.dataframe(display_copy(table, ""), width="stretch", hide_index=True)
    elif variant == "c":
        st.dataframe(display_copy(table, DASH), width="stretch", hide_index=True)
    else:
        st.dataframe(table, width="stretch", hide_index=True, **placeholder_kwargs())
elif page == "el":
    table = elastic_table()
    text_numbers = variant in ("b", "c")
    if variant == "b":
        shown = display_copy(table, "")
    elif variant == "c":
        shown = display_copy(table, DASH)
    else:
        shown = table
    edited = st.data_editor(
        shown,
        width="stretch",
        hide_index=True,
        disabled=["phase", "mole_fraction", "volume_fraction"],
        column_config=elastic_config(text_numbers),
        key=f"editor_{variant}",
        **placeholder_kwargs(),
    )
    st.caption("Что вернул редактор (repr по строкам BCC_A2, FCC_A1, CEMENTITE):")
    st.code(
        "\n".join(
            f"{column}: {edited[column].tolist()!r} dtype={edited[column].dtype}"
            for column in ("young_gpa", "poisson", "origin", "reference_temperature_c")
        ),
        language=None,
    )
