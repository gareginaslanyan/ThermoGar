#!/usr/bin/env python3
"""D1. Наклон ρ(T): база против кода приложения.

Вопрос волны 11D. Опорная точка плотности (8,481 г/см³ при 25 °C) проверена в
A2 независимо, а наклон ρ(T) выглядит завышенным: на участке 1100…1300 °C, где
99,93 % молей считаются прямой DP-моделью, падение 1,85 % на 200 K отвечает
среднему линейному коэффициенту расширения около 31e-6 /K при справочных для
Ni–Cr–Mo примерно 18e-6.

Две причины различаются одной проверкой: либо такие данные лежат в самой PDB,
либо код приложения применяет тепловое расширение поверх уже температурной
функции базы, то есть учитывает его дважды.

Проверка разводит их так же, как волна 10 разводила корень плотности: выражение
``D0FCC_NI + DTNIFCC`` берётся прямо из текста базы — строка вырезается из файла
регулярным выражением и вычисляется собственным разбором, минуя весь код
приложения, — и сравнивается с тем, что на тех же температурах выдаёт
``PhysicalDensityDatabase``. Расхождение наклонов означало бы двойной учёт;
совпадение означает, что наклон таков в базе.

Запуск:
    <venv>/Scripts/python.exe -X utf8 tools/d1_density_expansion_check.py

Считает секунды, равновесий не решает: числа сплава берутся из готовой
``results/hn62m_tech/a2_density.csv``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

PDB_PATH = ROOT / "databases" / "physical" / "original" / "physical_data_v103.pdb"
OUT = ROOT / "results" / "hn62m_tech"
A2_TABLE = OUT / "a2_density.csv"
CSV_WRITE = {"index": False, "sep": ";", "decimal": ",", "encoding": "utf-8-sig"}
CSV_READ = {"sep": ";", "decimal": ",", "encoding": "utf-8-sig"}

# Температуры проверки названы постановкой D1.
CHECK_TEMPERATURES_K = (298.15, 1400.0)
# Промежуточные точки — чтобы сравнивался наклон, а не две крайние точки:
# расширение, учтённое дважды, совпало бы при 298 K и разошлось бы выше.
SLOPE_TEMPERATURES_K = (298.15, 500.0, 800.0, 1100.0, 1400.0)

# Справочные линейные коэффициенты расширения чистых металлов, 1e-6 /K,
# усреднённые по 25…1100 °C (Touloukian, Thermophysical Properties of Matter).
REFERENCE_ALPHA = {"NI": 13.4, "CR": 6.2, "MO": 4.8}
# Физически ожидаемое окно для сплава Ni-Cr-Mo, 1e-6 /K (постановка D1).
PHYSICAL_ALPHA_WINDOW = (12.0, 20.0)
ATOMIC_MASS = {"NI": 58.693, "CR": 51.996, "MO": 95.95}
# Матрица контрольного состава при 1100…1300 °C, мольные доли подрешётки
# замещения: округление расчётного состава FCC_A1 из A2. Нужна только для того,
# чтобы показать вклад каждого конечного члена в расширение смеси.
MATRIX_Y = {"NI": 0.66, "CR": 0.26, "MO": 0.08}


# --------------------------------------------------------------------------- #
# Разбор базы без кода приложения
# --------------------------------------------------------------------------- #


def active_text() -> str:
    """Текст базы без строк-комментариев.

    Комментарии отбрасываются заранее, иначе закомментированные старые версии
    ``DTCRBCC`` перебили бы действующую: в файле их три, работает последняя.
    """

    return "\n".join(
        line for line in PDB_PATH.read_text("utf-8", errors="replace").splitlines()
        if not line.lstrip().startswith("$")
    )


def extract_function(text: str, name: str) -> str:
    """Тело ``FUNCTION <name>`` из текста базы, как оно там записано."""

    pattern = re.compile(
        r"FUNCTION\s+" + re.escape(name) + r"\s+[0-9.E+\-]+\s+(.*?);",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        raise RuntimeError(f"В {PDB_PATH.name} не найдена FUNCTION {name}.")
    return " ".join(match.group(1).split())


def extract_parameter(text: str, phase: str, constituents: str) -> str:
    pattern = re.compile(
        r"PARAMETER\s+DP\(\s*" + re.escape(phase) + r"\s*,\s*"
        + re.escape(constituents) + r"\s*\)\s+[0-9.E+\-]+\s+(.*?);",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        raise RuntimeError(
            f"В {PDB_PATH.name} не найден PARAMETER DP({phase},{constituents})."
        )
    return " ".join(match.group(1).split())


# Полиномы, выписанные из базы вручную. Сверяются с текстом файла ниже:
# расхождение — ошибка переписывания, и проверка обязана о ней сказать.
HAND_FUNCTIONS: dict[str, Callable[[float], float]] = {
    "D0FCC_NI": lambda t: 8914.0,
    "D0BCC_CR": lambda t: 7200.0,
    "D0BCC_MO": lambda t: 10223.8,
    "DTNIFCC": lambda t: 103.38 - 0.3432863 * t - 0.0000627364 * t ** 2,
    "DTCRBCC": lambda t: (
        73.9748 - 0.263244367 * t - 0.00013071 * t ** 2 - 0.000000073784 * t ** 3
    ),
    "DTMOBCC": lambda t: (
        49.966 - 0.17146 * t + 0.0000161584 * t ** 2 - 0.0000000151 * t ** 3
    ),
}
HAND_TEXT = {
    "D0FCC_NI": "8914.0",
    "D0BCC_CR": "7200.0",
    "D0BCC_MO": "10223.8",
    "DTNIFCC": "+103.38-0.3432863*T-0.0000627364*T**(+2)",
    "DTCRBCC": "+73.9748-0.263244367*T-0.00013071*T**(+2)-0.000000073784*T**(+3)",
    "DTMOBCC": "+49.966-0.17146*T+0.0000161584*T**(+2)-0.0000000151*T**(+3)",
}
# Конечные члены FCC_A1, как они записаны параметрами DP.
ENDMEMBERS: dict[str, tuple[str, tuple[str, str]]] = {
    "NI": ("NI:VA", ("D0FCC_NI", "DTNIFCC")),
    "CR": ("CR:VA", ("D0BCC_CR", "DTCRBCC")),
    "MO": ("MO:VA", ("D0BCC_MO", "DTMOBCC")),
}


def hand_density(element: str, temperature_k: float) -> float:
    _constituents, parts = ENDMEMBERS[element]
    return sum(HAND_FUNCTIONS[name](temperature_k) for name in parts)


def linear_alpha(density_hot: float, density_cold: float,
                 temperature_hot: float, temperature_cold: float) -> float:
    """Средний линейный коэффициент расширения из пары плотностей, 1/K.

    Объём обратен плотности, линейный размер — кубический корень объёма,
    поэтому ρ_хол/ρ_гор = (1 + α·ΔT)³, и при малом α·ΔT это 1 + 3α·ΔT.
    """

    return (density_cold / density_hot - 1.0) / (
        3.0 * (temperature_hot - temperature_cold)
    )


def mixture_density(functions: dict[str, Callable[[float], float]],
                    temperature_k: float) -> float:
    """Плотность смеси конечных членов по объёмной аддитивности."""

    mass = sum(MATRIX_Y[name] * ATOMIC_MASS[name] for name in MATRIX_Y)
    volume = sum(
        MATRIX_Y[name] * ATOMIC_MASS[name] / functions[name](temperature_k)
        for name in MATRIX_Y
    )
    return mass / volume


def normalized(expression: str) -> str:
    return expression.replace("**(+", "**(").replace(" ", "").lstrip("+").upper()


def main() -> int:
    text = active_text()
    OUT.mkdir(parents=True, exist_ok=True)

    # 1. Переписанные полиномы против текста базы.
    transcription: list[dict[str, Any]] = []
    for name, expected in HAND_TEXT.items():
        found = extract_function(text, name)
        transcription.append({
            "выражение базы": name,
            "в базе": found,
            "переписано": expected,
            "совпало": normalized(found) == normalized(expected),
        })
    for element, (constituents, parts) in ENDMEMBERS.items():
        found = extract_parameter(text, "FCC_A1", constituents)
        expected = "+".join(parts)
        transcription.append({
            "выражение базы": f"DP(FCC_A1,{constituents})",
            "в базе": found,
            "переписано": expected,
            "совпало": normalized(found) == normalized(expected),
        })
    transcription_table = pd.DataFrame(transcription)
    transcription_table.to_csv(OUT / "d1_base_transcription.csv", **CSV_WRITE)
    if not transcription_table["совпало"].all():
        raise RuntimeError(
            "Полиномы переписаны из базы неточно, см. d1_base_transcription.csv"
        )

    # 2. База против приложения на одних и тех же температурах.
    from thermogar_physical import PhysicalDensityDatabase

    physical_db = PhysicalDensityDatabase(str(PDB_PATH))
    rows: list[dict[str, Any]] = []
    for temperature_k in sorted(set(CHECK_TEMPERATURES_K) | set(SLOPE_TEMPERATURES_K)):
        for element in ENDMEMBERS:
            direct = hand_density(element, temperature_k)
            through_app, coverage, warnings = physical_db.density_from_site_fractions(
                "FCC_A1", [{element: 1.0}, {"VA": 1.0}], temperature_k
            )
            rows.append({
                "T, K": temperature_k,
                "T, °C": round(temperature_k - 273.15, 2),
                "элемент": element,
                "ρ из функции базы, кг/м³": round(direct, 4),
                "ρ через код приложения, кг/м³": (
                    None if through_app is None else round(float(through_app), 4)
                ),
                "разность, кг/м³": (
                    None if through_app is None
                    else round(float(through_app) - direct, 9)
                ),
                "покрытие эндмемберов": round(float(coverage), 6),
                "предупреждения": "; ".join(warnings) or "нет",
            })
    comparison = pd.DataFrame(rows)
    comparison.to_csv(OUT / "d1_pure_endmembers.csv", **CSV_WRITE)

    max_gap = float(comparison["разность, кг/м³"].astype(float).abs().max())
    double_counting = max_gap > 1.0e-6

    # 3. Коэффициенты расширения конечных членов базы против справочных.
    alpha_rows: list[dict[str, Any]] = []
    for element in ENDMEMBERS:
        alpha = linear_alpha(
            hand_density(element, 1400.0), hand_density(element, 298.15),
            1400.0, 298.15,
        ) * 1.0e6
        alpha_rows.append({
            "элемент": element,
            "ρ(298,15 K) из базы, кг/м³": round(hand_density(element, 298.15), 2),
            "ρ(1400 K) из базы, кг/м³": round(hand_density(element, 1400.0), 2),
            "α базы, 1e-6 /K": round(alpha, 2),
            "α справочный, 1e-6 /K": REFERENCE_ALPHA[element],
            "во сколько раз завышен": round(alpha / REFERENCE_ALPHA[element], 2),
        })
    alpha_table = pd.DataFrame(alpha_rows)
    alpha_table.to_csv(OUT / "d1_endmember_alpha.csv", **CSV_WRITE)

    # 4. Расширение матрицы по базе и с подставленным литературным хромом.
    #    Вторая цифра показывает, весь ли избыток идёт от хрома.
    base_functions: dict[str, Callable[[float], float]] = {
        name: (lambda t, element=name: hand_density(element, t)) for name in MATRIX_Y
    }
    as_is = linear_alpha(
        mixture_density(base_functions, 1573.15),
        mixture_density(base_functions, 1373.15),
        1573.15, 1373.15,
    ) * 1.0e6
    cold_cr = hand_density("CR", 298.15)
    repaired_functions = dict(base_functions)
    repaired_functions["CR"] = lambda t: cold_cr * (
        1.0 - 3.0 * REFERENCE_ALPHA["CR"] * 1.0e-6 * (t - 298.15)
    )
    repaired = linear_alpha(
        mixture_density(repaired_functions, 1573.15),
        mixture_density(repaired_functions, 1373.15),
        1573.15, 1373.15,
    ) * 1.0e6

    # 5. Сплав: числа A2, посчитанные полным путём приложения.
    alloy: dict[str, Any] = {"источник": str(A2_TABLE.relative_to(ROOT))}
    if A2_TABLE.is_file():
        table = pd.read_csv(A2_TABLE, **CSV_READ)
        density_by_t = {
            round(float(record["T, °C"]), 1): float(record["плотность, кг/м³"])
            for record in table.to_dict("records")
            if pd.notna(record.get("плотность, кг/м³"))
        }
        for cold_c, hot_c in ((25.0, 1100.0), (1100.0, 1300.0)):
            if cold_c in density_by_t and hot_c in density_by_t:
                alpha = linear_alpha(
                    density_by_t[hot_c], density_by_t[cold_c],
                    hot_c + 273.15, cold_c + 273.15,
                ) * 1.0e6
                alloy[f"ρ({cold_c:.0f} °C), кг/м³"] = density_by_t[cold_c]
                alloy[f"ρ({hot_c:.0f} °C), кг/м³"] = density_by_t[hot_c]
                alloy[f"α сплава {cold_c:.0f}…{hot_c:.0f} °C, 1e-6 /K"] = round(alpha, 1)

    verdict = (
        "двойной учёт расширения в коде приложения"
        if double_counting else
        "наклон ρ(T) целиком из базы; код приложения расширения не добавляет"
    )
    summary = {
        "подпункт": "D1. Наклон ρ(T): база против кода приложения",
        "база": str(PDB_PATH.relative_to(ROOT)),
        "метод": (
            "выражение DP(FCC_A1,<элемент>:VA) вырезано из текста базы "
            "регулярным выражением, вычислено собственным разбором и сверено "
            "с PhysicalDensityDatabase на тех же температурах"
        ),
        "температуры проверки, K": list(SLOPE_TEMPERATURES_K),
        "макс. расхождение база/приложение, кг/м³": max_gap,
        "двойной учёт расширения": bool(double_counting),
        "вердикт": verdict,
        "конечные члены": alpha_table.to_dict("records"),
        "матрица (мольные доли подрешётки замещения)": MATRIX_Y,
        "α матрицы 1100…1300 °C по базе, 1e-6 /K": round(as_is, 1),
        "α матрицы с литературным хромом, 1e-6 /K": round(repaired, 1),
        "физическое окно, 1e-6 /K": list(PHYSICAL_ALPHA_WINDOW),
        "сплав": alloy,
        "шапка базы о хроме": (
            "densities from ref 14 are based on molar volume data, except Cr "
            "(based on density data)"
        ),
    }
    (OUT / "d1_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), "utf-8"
    )

    print(f"макс. расхождение база/приложение: {max_gap:.3e} кг/м³")
    print(f"вердикт: {verdict}")
    print(alpha_table.to_string(index=False))
    print(f"α матрицы по базе {as_is:.1f}e-6 /K, "
          f"с литературным хромом {repaired:.1f}e-6 /K")
    print(json.dumps(alloy, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
