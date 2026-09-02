"""ThermoGar trust, diagnostics and friendly-error implementation.

Имя файла сохранено для совместимости с историческим Stage 14. Текущая
release identity импортируется из ``thermogar_release_policy`` и не означает
научную квалификацию материала.
"""

from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from pathlib import Path
import hashlib
import json
import platform
import sys
import traceback
import uuid
from typing import Any, Callable

import numpy as np
import pandas as pd
import streamlit as st
from pycalphad import Database, equilibrium, variables as v
from pycalphad.core.utils import filter_phases, unpack_species
from thermogar_release_policy import (
    APP_STAGE,
    APP_VERSION,
    PRODUCTION_USE,
    RELEASE_DATABASE_KEYS,
    RELEASE_CLASS,
    SCIENTIFIC_MATERIAL_STATUS,
    SOFTWARE_RELEASE_STATUS,
    release_status,
)
from thermogar_release_ui import (
    release_calculation_button,
    release_download_button,
)
from thermogar_paths import ThermoGarPaths
from thermogar_secure_io import atomic_update_bytes, ensure_plain_directory


VALIDATION_SCHEMA_VERSION = 1
MAX_ERROR_LOG_BYTES = 8 * 1024 * 1024
MAX_ERROR_LOG_ENTRY_BYTES = 512 * 1024


# ---------------------------------------------------------------------------
# Общие служебные функции
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "не установлен"


def json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        default=str,
    ).encode("utf-8-sig")


def dataframe_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, dataframe in sheets.items():
            dataframe.to_excel(writer, sheet_name=name[:31], index=False)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Ошибки без traceback на основном экране
# ---------------------------------------------------------------------------


def _friendly_error_text(error: Exception, context: str) -> tuple[str, str]:
    raw = str(error).strip()
    lower = raw.lower()

    if isinstance(error, FileNotFoundError):
        return (
            "Не найден необходимый файл.",
            "Проверьте, что папки app и databases находятся внутри одной "
            "папки ThermoGar, затем запустите программу снова.",
        )

    if isinstance(error, MemoryError):
        return (
            "Для расчёта не хватило памяти.",
            "Увеличьте шаг сетки, уменьшите диапазон или оставьте меньше фаз.",
        )

    if "сумма добавок" in lower or "меньше 100" in lower:
        return (
            "Сумма добавок должна быть меньше 100 %.",
            "Уменьшите содержание одного или нескольких элементов. Остаток "
            "до 100 % ThermoGar автоматически отдаёт элементу-основе.",
        )

    if "не удалось прочитать состав" in lower or "непонятный фрагмент" in lower:
        return (
            "ThermoGar не смог прочитать химический состав.",
            "Используйте запись вида AL=15, CR=10, C=0,2. Элемент-основу "
            "повторно указывать не нужно.",
        )

    if "отсутствуют элементы" in lower or "элемент отсутствует" in lower:
        return (
            "В выбранной базе нет одного из введённых элементов.",
            "Уберите этот элемент либо выберите другую базу материалов.",
        )

    if "хотя бы одну фазу" in lower or "не осталось допустимых фаз" in lower:
        return (
            "Для расчёта не осталось разрешённых фаз.",
            "Верните хотя бы одну галочку в блоке управления фазами. Для "
            "затвердевания обязательно оставьте LIQUID.",
        )

    if (
        "известная проблема mc_fe 2.062" in lower
        or "c15_laves" in lower and "ликвидус" in lower
    ):
        return (
            "ThermoGar заблокировал недостоверный ликвидус стальной базы.",
            raw + " Откройте «Проекты и данные → Паспорт базы», чтобы "
            "посмотреть патч TG-FE-2062-C15-001 и двустороннюю приёмку. "
            "Исходная TDB сохранена; непатченная копия доступна только для "
            "диагностики.",
        )

    if "liquid" in lower and context.lower().startswith("затверд"):
        return (
            "Не удалось начать расчёт затвердевания из расплава.",
            "Оставьте фазу LIQUID и включите автоматический поиск начальной "
            "температуры либо увеличьте её вручную.",
        )

    if "конечная температура" in lower or "выше начальной" in lower:
        return (
            "Диапазон температур задан неверно.",
            "Конечная температура должна быть выше начальной, а шаг — больше нуля.",
        )

    if "слишком много точек" in lower:
        return (
            "Расчётная сетка слишком подробная для одного запуска.",
            "Увеличьте шаг или уменьшите диапазон. Сначала постройте обзорную "
            "карту, затем уточняйте только интересующую область.",
        )

    if "мобильност" in lower or "mobility" in lower:
        return (
            "Для выбранной матрицы не хватает данных о диффузионной подвижности.",
            "Выберите другую матричную фазу, уменьшите набор элементов или "
            "проверьте, что используется база с подключённой DDB.",
        )

    if "grain boundary to interfacial energy ratio" in lower or "nucleation barrer" in lower:
        return (
            "Параметры гетерогенного зарождения несовместимы.",
            "Уменьшите энергию границы зерна либо увеличьте межфазную энергию. "
            "Для первичной проверки используйте объёмные центры зарождения.",
        )

    if "interfacial energy" in lower or "gamma is not set" in lower:
        return (
            "Не задана допустимая межфазная энергия.",
            "Введите положительное значение в Дж/м². Для реального материала "
            "параметр нужно брать из открытого источника и явно указывать область применимости.",
        )

    if "molar volume" in lower or "vmalpha" in lower:
        return (
            "Не задан допустимый молярный объём.",
            "Введите положительные молярные объёмы матрицы и выделения в см³/моль.",
        )

    if (
        "не заданы e и ν" in lower
        or "объёмные доли недоступны" in lower
        or "сначала обеспечьте плотностями" in lower
    ):
        return (
            "Для упругой гомогенизации не хватает исходных данных.",
            raw + " Задайте E и ν каждой равновесной фазы и убедитесь, что "
            "physical_data.pdb покрывает все фазовые объёмные доли.",
        )

    if "коэффициент hall" in lower or "размер зерна" in lower:
        return (
            "Не удалось рассчитать вклад Hall–Petch.",
            raw + " Проверьте alloy-specific k_y и положительный размер зерна.",
        )

    if "вектор бюргерса" in lower or "плотность дислокаций" in lower:
        return (
            "Не удалось рассчитать дислокационный вклад.",
            raw + " Проверьте G, b, ρ_d, Taylor factor и коэффициент α.",
        )

    if "межчастичное расстояние" in lower or "радиус частицы" in lower:
        return (
            "Не удалось рассчитать вклад Orowan.",
            raw + " Радиус должен быть больше b, а λ — положительным.",
        )

    if "precipitate" in lower and "phase" in lower:
        return (
            "Не удалось собрать модель кинетики выбранного выделения.",
            "Проверьте код матричной фазы, код фазы-выделения и параметры KWN. "
            "Для первой проверки используйте учебный Ni–Al–Cr пример.",
        )

    if "не заданы e и ν" in lower or "не заданы e и" in lower:
        return (
            "Не заданы упругие свойства всех фаз.",
            raw + " Заполните E и ν в таблице фаз либо загрузите значения из "
            "локальной библиотеки с указанием источника.",
        )

    if "объёмные доли" in lower and "100" in lower:
        return (
            "Для упругой гомогенизации не хватает полных объёмных долей.",
            "Откройте «Свойства → Покрытие PDB» и проверьте, что каждая "
            "равновесная фаза обеспечена плотностью.",
        )

    if any(
        phrase in lower
        for phrase in (
            "модуль юнга",
            "коэффициент пуассона",
            "размер зерна",
            "плотность дислокаций",
            "вектор бюргерса",
            "межчастичное расстояние",
        )
    ):
        return (
            "Один из параметров свойств задан неверно.",
            raw,
        )

    if "converg" in lower or "solver" in lower or "сходим" in lower:
        return (
            "Решатель не сошёлся для выбранной точки.",
            "Увеличьте плотность поиска, уменьшите шаг, верните автоматический "
            "набор фаз либо немного измените границы расчёта.",
        )

    if isinstance(error, ValueError) and raw:
        return (
            "Расчёт не выполнен из-за неверных исходных данных.",
            raw,
        )

    if raw:
        return (
            "ThermoGar не завершил расчёт.",
            "Проверьте состав, диапазон и набор фаз. Если ошибка повторяется, "
            "скачайте технический отчёт ниже. Причина: " + raw,
        )

    return (
        "ThermoGar не завершил расчёт.",
        "Проверьте исходные данные и повторите попытку. Если ошибка сохраняется, "
        "скачайте технический отчёт.",
    )


def _write_error_log(
    paths: ThermoGarPaths,
    error: Exception,
    context: str,
    extra: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    error_id = (
        datetime.now().strftime("%Y%m%d-%H%M%S")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    payload = {
        "schema_version": 1,
        "error_id": error_id,
        "created_at": now_iso(),
        "context": context,
        "exception_type": type(error).__name__,
        "message": str(error),
        "traceback": "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        ),
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": {
            "thermogar": APP_VERSION,
            "pycalphad": package_version("pycalphad"),
            "streamlit": package_version("streamlit"),
            "scheil": package_version("scheil"),
            "numpy": package_version("numpy"),
            "scipy": package_version("scipy"),
            "pandas": package_version("pandas"),
        },
        "release_status": release_status(),
        "extra": extra or {},
    }

    if not isinstance(paths, ThermoGarPaths):
        raise TypeError("paths must be a ThermoGarPaths instance")
    directory = ensure_plain_directory(paths.stage14_errors_path.parent)
    log_path = paths.stage14_errors_path
    encoded_entry = (
        json.dumps(payload, ensure_ascii=False, default=str) + "\n"
    ).encode("utf-8")
    if len(encoded_entry) > MAX_ERROR_LOG_ENTRY_BYTES:
        payload["message"] = str(error)[:16384]
        payload["traceback"] = payload["traceback"][:65536]
        payload["extra"] = {
            "omitted": "Diagnostic extra exceeded the bounded log entry size."
        }
        encoded_entry = (
            json.dumps(payload, ensure_ascii=False, default=str) + "\n"
        ).encode("utf-8")
    if len(encoded_entry) > MAX_ERROR_LOG_ENTRY_BYTES:
        raise RuntimeError("Технический отчёт превысил допустимый размер.")

    def append_bounded(existing_bytes: bytes) -> bytes:
        existing = existing_bytes
        separator = b"" if not existing or existing.endswith(b"\n") else b"\n"
        while len(existing) + len(separator) + len(encoded_entry) > MAX_ERROR_LOG_BYTES:
            boundary = existing.find(b"\n")
            if boundary < 0:
                existing = b""
            else:
                existing = existing[boundary + 1 :]
            separator = b"" if not existing or existing.endswith(b"\n") else b"\n"
        return existing + separator + encoded_entry

    atomic_update_bytes(
        log_path,
        append_bounded,
        maximum_bytes=MAX_ERROR_LOG_BYTES,
        canonical_root=paths.state_root,
    )

    return error_id, payload


def render_user_error(
    error: Exception,
    *,
    context: str,
    paths: ThermoGarPaths,
    extra: dict[str, Any] | None = None,
) -> None:
    """Показать понятную ошибку и сохранить полный технический отчёт локально."""
    title, action = _friendly_error_text(error, context)
    error_id, payload = _write_error_log(
        paths,
        error,
        context,
        extra,
    )

    st.error(f"{title}\n\n{action}")
    st.caption(f"Код ошибки: {error_id}")
    with st.expander("Технические сведения", expanded=False):
        st.write(f"Тип: {payload['exception_type']}")
        st.write(f"Раздел: {context}")
        st.caption(
            "Полный traceback не выводится на основной экран. Он сохранён "
            "локально и доступен в отчёте ниже."
        )
        release_download_button(
            "Скачать технический отчёт",
            data=json_bytes(payload),
            file_name=f"ThermoGar_error_{error_id}.json",
            mime="application/json",
            key=f"download_error_{error_id}",
        )


# ---------------------------------------------------------------------------
# Автоматическая проверка результата
# ---------------------------------------------------------------------------


def _check_row(
    name: str,
    value: Any,
    criterion: str,
    passed: bool,
    note: str,
) -> dict[str, Any]:
    return {
        "Проверка": name,
        "Значение": value,
        "Критерий": criterion,
        "Статус": "пройдена" if passed else "не пройдена",
        "Пояснение": note,
    }


def _validation_report(
    checks: list[dict[str, Any]],
    *,
    title: str,
    limitations: str,
) -> dict[str, Any]:
    failed = sum(row["Статус"] != "пройдена" for row in checks)
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "title": title,
        "status": "passed" if failed == 0 else "failed",
        "failed_checks": failed,
        "checks": pd.DataFrame(checks),
        "limitations": limitations,
    }


def validate_single_equilibrium(
    summary: pd.DataFrame,
    phase_at: pd.DataFrame,
    overall: pd.DataFrame,
    *,
    fraction_tolerance_percent: float = 1e-4,
    composition_tolerance_percent: float = 1e-4,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    if summary.empty:
        checks.append(
            _check_row(
                "Получены устойчивые фазы",
                0,
                "> 0",
                False,
                "Решатель не вернул фазовый состав.",
            )
        )
        return _validation_report(
            checks,
            title="Проверка равновесия",
            limitations=(
                "Это проверка численной целостности, а не сравнение с "
                "открытым benchmark или независимым программным комплексом."
            ),
        )

    fractions = pd.to_numeric(
        summary["Мольная доля фазы, %"],
        errors="coerce",
    )
    finite = bool(np.isfinite(fractions).all())
    checks.append(
        _check_row(
            "Фазовые доли являются числами",
            "да" if finite else "нет",
            "все конечны",
            finite,
            "NaN или бесконечность указывают на незавершённый расчёт.",
        )
    )

    fraction_sum = float(fractions.sum())
    fraction_error = abs(fraction_sum - 100.0)
    checks.append(
        _check_row(
            "Сумма фазовых долей",
            f"{fraction_sum:.8f} %",
            f"|Σ−100| ≤ {fraction_tolerance_percent:g} %",
            fraction_error <= fraction_tolerance_percent,
            "Сумма должна быть равна 100 % с учётом численного округления.",
        )
    )

    bounds_ok = bool(
        ((fractions >= -fraction_tolerance_percent) &
         (fractions <= 100.0 + fraction_tolerance_percent)).all()
    )
    checks.append(
        _check_row(
            "Границы фазовых долей",
            "0–100 %" if bounds_ok else "есть выход за границы",
            "0 ≤ NP ≤ 100 %",
            bounds_ok,
            "Отрицательная доля или доля больше 100 % физически невозможна.",
        )
    )

    composition_columns = [
        column for column in phase_at.columns if column.endswith(", ат.%")
    ]
    if composition_columns:
        phase_sums = phase_at[composition_columns].apply(
            pd.to_numeric,
            errors="coerce",
        ).sum(axis=1)
        max_phase_sum_error = float(np.nanmax(np.abs(phase_sums - 100.0)))
        phase_sum_ok = bool(
            np.isfinite(phase_sums).all()
            and max_phase_sum_error <= composition_tolerance_percent
        )
        checks.append(
            _check_row(
                "Сумма составов каждой фазы",
                f"макс. ошибка {max_phase_sum_error:.3e} %",
                f"≤ {composition_tolerance_percent:g} %",
                phase_sum_ok,
                "Содержание элементов внутри каждой фазы должно давать 100 %.",
            )
        )

        phase_fraction_by_name = {
            str(row["Фаза"]): float(row["Мольная доля фазы, %"]) / 100.0
            for _, row in summary.iterrows()
        }
        phase_at_indexed = phase_at.set_index("Фаза")
        reconstructed: dict[str, float] = {}
        for column in composition_columns:
            element = column.split(",", 1)[0]
            value = 0.0
            for phase_name, fraction in phase_fraction_by_name.items():
                if phase_name not in phase_at_indexed.index:
                    continue
                phase_value = float(phase_at_indexed.loc[phase_name, column])
                value += fraction * phase_value
            reconstructed[element] = value

        overall_map = {
            str(row["Элемент"]): float(row["Содержание, ат.%"])
            for _, row in overall.iterrows()
        }
        common_elements = sorted(set(reconstructed) & set(overall_map))
        if common_elements:
            errors = {
                element: reconstructed[element] - overall_map[element]
                for element in common_elements
            }
            max_element = max(errors, key=lambda key: abs(errors[key]))
            max_balance_error = abs(errors[max_element])
            checks.append(
                _check_row(
                    "Материальный баланс по элементам",
                    (
                        f"макс. ошибка {max_balance_error:.3e} % "
                        f"для {max_element}"
                    ),
                    f"≤ {composition_tolerance_percent:g} %",
                    max_balance_error <= composition_tolerance_percent,
                    "Состав всего сплава восстановлен из долей и составов фаз.",
                )
            )

    return _validation_report(
        checks,
        title="Проверка равновесия",
        limitations=(
            "Проверка подтверждает численную целостность: фазовые доли, "
            "составы и материальный баланс. Она не доказывает точность "
            "термодинамической оценки для конкретного промышленного сплава."
        ),
    )


def validate_phase_scan(
    dataframe: pd.DataFrame,
    x_column: str,
    *,
    sum_tolerance_percent: float = 1e-3,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    if dataframe.empty or x_column not in dataframe.columns:
        checks.append(
            _check_row(
                "Расчётная таблица",
                "пусто",
                "есть точки",
                False,
                "Сканирование не вернуло расчётных точек.",
            )
        )
        return _validation_report(
            checks,
            title="Проверка сканирования",
            limitations=(
                "Проверка относится к сетке расчёта и не оценивает точность "
                "положения фазовых границ между узлами."
            ),
        )

    metadata = {
        x_column,
        "Сумма фазовых долей",
        "Температура, K",
    }
    phase_columns = [
        column
        for column in dataframe.columns
        if column not in metadata
        and pd.api.types.is_numeric_dtype(dataframe[column])
    ]

    x_values = pd.to_numeric(dataframe[x_column], errors="coerce").to_numpy()
    finite_x = bool(np.isfinite(x_values).all())
    monotonic = bool(finite_x and np.all(np.diff(x_values) > 0))
    checks.append(
        _check_row(
            "Расчётная сетка",
            f"{len(dataframe)} точек",
            "координата строго возрастает",
            monotonic,
            "Повторяющиеся или перепутанные точки затрудняют чтение графика.",
        )
    )

    if not phase_columns:
        checks.append(
            _check_row(
                "Фазовые столбцы",
                0,
                "> 0",
                False,
                "В таблице нет рассчитанных фазовых долей.",
            )
        )
    else:
        phase_values = dataframe[phase_columns].apply(
            pd.to_numeric,
            errors="coerce",
        )
        finite = bool(np.isfinite(phase_values.to_numpy()).all())
        checks.append(
            _check_row(
                "Фазовые доли являются числами",
                "да" if finite else "нет",
                "все конечны",
                finite,
                "NaN или бесконечность указывают на незавершённую точку.",
            )
        )

        bounds_ok = bool(
            ((phase_values >= -sum_tolerance_percent) &
             (phase_values <= 100.0 + sum_tolerance_percent)).all().all()
        )
        checks.append(
            _check_row(
                "Границы фазовых долей",
                "0–100 %" if bounds_ok else "есть выход за границы",
                "0 ≤ NP ≤ 100 %",
                bounds_ok,
                "Все фазовые доли должны находиться в физическом диапазоне.",
            )
        )

        row_sums = phase_values.sum(axis=1).to_numpy(dtype=float)
        max_error = float(np.nanmax(np.abs(row_sums - 100.0)))
        sum_ok = bool(
            np.isfinite(row_sums).all()
            and max_error <= sum_tolerance_percent
        )
        checks.append(
            _check_row(
                "Сумма фазовых долей в каждой точке",
                f"макс. ошибка {max_error:.3e} %",
                f"≤ {sum_tolerance_percent:g} %",
                sum_ok,
                "Каждая точка сетки должна содержать 100 % фаз.",
            )
        )

    return _validation_report(
        checks,
        title="Проверка сканирования",
        limitations=(
            "Проверка подтверждает целостность сетки. Фазовая граница между "
            "узлами остаётся приближённой; её неопределённость порядка "
            "половины шага сетки."
        ),
    )


def validate_solidification_paths(
    paths: dict[str, pd.DataFrame],
    *,
    tolerance_percent: float = 1e-3,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    for method, dataframe in paths.items():
        label = str(method)
        if dataframe.empty:
            checks.append(
                _check_row(
                    f"{label}: траектория",
                    "пусто",
                    "есть точки",
                    False,
                    "Метод не вернул траекторию затвердевания.",
                )
            )
            continue

        temperature = pd.to_numeric(
            dataframe["Температура, °C"],
            errors="coerce",
        ).to_numpy()
        liquid = pd.to_numeric(
            dataframe["Доля расплава, %"],
            errors="coerce",
        ).to_numpy()
        solid = pd.to_numeric(
            dataframe["Доля твёрдого, %"],
            errors="coerce",
        ).to_numpy()

        finite = bool(
            np.isfinite(temperature).all()
            and np.isfinite(liquid).all()
            and np.isfinite(solid).all()
        )
        checks.append(
            _check_row(
                f"{label}: значения являются числами",
                "да" if finite else "нет",
                "все конечны",
                finite,
                "Траектория не должна содержать NaN или бесконечность.",
            )
        )

        cooling = bool(np.all(np.diff(temperature) <= 1e-8))
        checks.append(
            _check_row(
                f"{label}: направление температуры",
                "охлаждение" if cooling else "есть рост температуры",
                "T не возрастает",
                cooling,
                "Затвердевание рассчитывается по мере охлаждения.",
            )
        )

        liquid_monotonic = bool(np.all(np.diff(liquid) <= tolerance_percent))
        solid_monotonic = bool(np.all(np.diff(solid) >= -tolerance_percent))
        checks.append(
            _check_row(
                f"{label}: доля расплава",
                "не возрастает" if liquid_monotonic else "есть обратный рост",
                "не возрастает при охлаждении",
                liquid_monotonic,
                "Небольшие численные колебания допускаются в пределах допуска.",
            )
        )
        checks.append(
            _check_row(
                f"{label}: доля твёрдого",
                "не убывает" if solid_monotonic else "есть обратное уменьшение",
                "не убывает при охлаждении",
                solid_monotonic,
                "Небольшие численные колебания допускаются в пределах допуска.",
            )
        )

        phase_sum = liquid + solid
        max_sum_error = float(np.nanmax(np.abs(phase_sum - 100.0)))
        checks.append(
            _check_row(
                f"{label}: расплав + твёрдое",
                f"макс. ошибка {max_sum_error:.3e} %",
                f"≤ {tolerance_percent:g} %",
                max_sum_error <= tolerance_percent,
                "Доли расплава и твёрдого вместе должны давать 100 %.",
            )
        )

    return _validation_report(
        checks,
        title="Проверка затвердевания",
        limitations=(
            "Проверка подтверждает внутреннюю согласованность траектории. "
            "Она не подтверждает допущения Scheil–Gulliver для конкретной "
            "скорости охлаждения и размера отливки."
        ),
    )


def validation_dataframe(report: dict[str, Any]) -> pd.DataFrame:
    dataframe = report.get("checks")
    if isinstance(dataframe, pd.DataFrame):
        return dataframe.copy()
    return pd.DataFrame()


def render_validation_report(
    report: dict[str, Any],
    *,
    expanded: bool = False,
) -> None:
    status = report.get("status")
    title = str(report.get("title", "Проверка результата"))
    failed = int(report.get("failed_checks", 0))

    if status == "passed":
        st.success(f"{title}: все проверки пройдены.")
    else:
        st.error(
            f"{title}: не пройдено проверок — {failed}. "
            "Не используйте результат до устранения причины."
        )

    with st.expander("Что именно проверено", expanded=expanded):
        dataframe = validation_dataframe(report)
        if not dataframe.empty:
            st.dataframe(dataframe, width="stretch", hide_index=True)
        st.info(str(report.get("limitations", "")))
        st.caption(
            "Неопределённость термодинамической базы и расхождение с "
            "материальная точность находится вне текущей no-experiment программы."
        )


# ---------------------------------------------------------------------------
# Диагностика установки и контрольные расчёты
# ---------------------------------------------------------------------------


def environment_table(project_root: str | Path) -> pd.DataFrame:
    root = Path(project_root)
    rows = [
        ("ThermoGar", APP_VERSION),
        ("Python", platform.python_version()),
        ("Архитектура", platform.machine()),
        ("Операционная система", platform.platform()),
        ("Корень проекта", str(root)),
        ("pycalphad", package_version("pycalphad")),
        ("Streamlit", package_version("streamlit")),
        ("scheil", package_version("scheil")),
        ("NumPy", package_version("numpy")),
        ("SciPy", package_version("scipy")),
        ("pandas", package_version("pandas")),
        ("matplotlib", package_version("matplotlib")),
        ("xarray", package_version("xarray")),
        ("openpyxl", package_version("openpyxl")),
    ]
    return pd.DataFrame(rows, columns=["Компонент", "Значение"])


@st.cache_resource(show_spinner=False)
def _cached_database(path_text: str, file_size: int, modified_ns: int) -> Database:
    """Загрузить базу один раз; размер и mtime входят в ключ кэша."""
    del file_size, modified_ns
    return Database(path_text)


def database_file_table(
    project_root: str | Path,
    database_definitions: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    root = Path(project_root)
    rows = []
    for key, definition in database_definitions.items():
        path = root / definition["relative_path"]
        rows.append(
            {
                "Ключ": key,
                "База": definition["label"],
                "Файл": str(path),
                "Существует": "да" if path.exists() else "нет",
                "Размер, байт": path.stat().st_size if path.exists() else np.nan,
                "SHA-256": file_sha256(path) if path.exists() else "",
            }
        )
    return pd.DataFrame(rows)


def database_diagnostic_table(
    project_root: str | Path,
    database_definitions: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    root = Path(project_root)
    rows: list[dict[str, Any]] = []

    for key, definition in database_definitions.items():
        path = root / definition["relative_path"]
        row: dict[str, Any] = {
            "Ключ": key,
            "База": definition["label"],
            "Файл": str(path),
            "Существует": "да" if path.exists() else "нет",
            "Размер, байт": path.stat().st_size if path.exists() else np.nan,
            "SHA-256": file_sha256(path) if path.exists() else "",
            "Элементов": np.nan,
            "Фаз": np.nan,
            "Статус": "файл не найден",
        }
        if path.exists():
            try:
                stat = path.stat()
                db = _cached_database(
                    str(path),
                    int(stat.st_size),
                    int(stat.st_mtime_ns),
                )
                row["Элементов"] = len(db.elements) - (1 if "VA" in db.elements else 0)
                row["Фаз"] = len(db.phases)
                row["Статус"] = "загружена"
            except Exception as error:
                row["Статус"] = f"ошибка: {type(error).__name__}: {error}"
        rows.append(row)

    return pd.DataFrame(rows)


def _smoke_equilibrium(
    db: Database,
    components: list[str],
    conditions: dict[Any, float],
    *,
    excluded_phases: set[str] | None = None,
) -> tuple[dict[str, float], float]:
    phases = filter_phases(db, unpack_species(db, components))
    if excluded_phases:
        phases = [phase for phase in phases if phase not in excluded_phases]

    eq = equilibrium(
        db,
        components,
        phases,
        conditions,
        calc_opts={"pdens": 300},
    )

    names = np.asarray(eq.Phase.values, dtype=str).ravel()
    fractions = np.asarray(eq.NP.values, dtype=float).ravel()
    result: dict[str, float] = {}
    for name, fraction in zip(names, fractions):
        if name and np.isfinite(fraction) and fraction > 1e-9:
            result[str(name)] = result.get(str(name), 0.0) + float(fraction)
    return result, float(sum(result.values()))


def run_smoke_tests(
    project_root: str | Path,
    database_definitions: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    root = Path(project_root)
    rows: list[dict[str, Any]] = []

    cases = [
        {
            "key": "ni",
            "name": "Ni–15 ат.% Al, 700 °C",
            "components": ["AL", "NI", "VA"],
            "conditions": {
                v.N: 1.0,
                v.P: 101325.0,
                v.T: 973.15,
                v.X("AL"): 0.15,
            },
            "expected": {"FCC_A1", "GAMMA_PRIME"},
            "excluded": set(),
        },
        {
            "key": "fe",
            "name": "Fe–1 мас.% C, 700 °C, Fe–Fe₃C",
            "components": ["C", "FE", "VA"],
            "conditions_factory": "fe_1wtc",
            "expected": {"BCC_B2", "CEMENTITE"},
            "excluded": {"GRAPHITE", "DIAMOND_A4"},
        },
        {
            "key": "al",
            "name": "Al–4 ат.% Cu, 500 °C",
            "components": ["AL", "CU", "VA"],
            "conditions": {
                v.N: 1.0,
                v.P: 101325.0,
                v.T: 773.15,
                v.X("CU"): 0.04,
            },
            "expected": {"GP_MAT", "THETA_AL2CU"},
            "excluded": set(),
        },
    ]
    cases = [case for case in cases if case["key"] in database_definitions]

    for case in cases:
        definition = database_definitions[case["key"]]
        path = root / definition["relative_path"]
        row: dict[str, Any] = {
            "Проверка": case["name"],
            "База": definition["label"],
            "Фазы": "",
            "Сумма долей": np.nan,
            "Ожидались": ", ".join(sorted(case["expected"])),
            "Статус": "не выполнена",
            "Пояснение": "",
        }
        try:
            stat = path.stat()
            db = _cached_database(
                str(path),
                int(stat.st_size),
                int(stat.st_mtime_ns),
            )
            conditions = case.get("conditions")
            if case.get("conditions_factory") == "fe_1wtc":
                mass_conditions = {v.W("C"): 0.01}
                mole_conditions = dict(v.get_mole_fractions(
                    mass_conditions,
                    "FE",
                    db,
                ))
                conditions = {
                    v.N: 1.0,
                    v.P: 101325.0,
                    v.T: 973.15,
                }
                conditions.update(mole_conditions)

            fractions, fraction_sum = _smoke_equilibrium(
                db,
                case["components"],
                conditions,
                excluded_phases=case["excluded"],
            )
            stable = set(fractions)
            expected_ok = case["expected"].issubset(stable)
            sum_ok = abs(fraction_sum - 1.0) <= 1e-6
            row["Фазы"] = ", ".join(sorted(stable))
            row["Сумма долей"] = fraction_sum
            row["Статус"] = "пройдена" if expected_ok and sum_ok else "не пройдена"
            if not expected_ok:
                missing = sorted(case["expected"] - stable)
                row["Пояснение"] = "Не найдены ожидаемые фазы: " + ", ".join(missing)
            elif not sum_ok:
                row["Пояснение"] = "Сумма фазовых долей отличается от 1."
            else:
                row["Пояснение"] = "Контрольный расчёт согласован с эталоном ThermoGar."
        except Exception as error:
            row["Статус"] = "ошибка"
            row["Пояснение"] = f"{type(error).__name__}: {error}"
        rows.append(row)

    return pd.DataFrame(rows)


def render_quick_examples(queue_context_load: Callable[..., None]) -> None:
    st.markdown("### Учебные примеры")
    st.caption(
        "Кнопка заполняет боковую панель. После загрузки откройте нужный "
        "расчёт и нажмите его синюю кнопку."
    )

    examples = [
        (
            "Ni–15Al: γ/γ′ при 700 °C",
            "Ni-база · основа NI · 15 ат.% AL.",
            {
                "database_key": "ni",
                "balance": "NI",
                "units": "at",
                "composition": "AL=15",
                "pressure_pa": 101325.0,
                "steel_mode": "stable",
            },
            {"single_temperature_ni": 700.0},
        ),
        (
            "Fe–1C: практический Fe–Fe₃C при 700 °C",
            "Fe-база · основа FE · 1 мас.% C · графит исключён.",
            {
                "database_key": "fe",
                "balance": "FE",
                "units": "wt",
                "composition": "C=1",
                "pressure_pa": 101325.0,
                "steel_mode": "metastable",
            },
            {"single_temperature_fe": 700.0},
        ),
        (
            "Al–4Cu при 500 °C",
            "Al-база · основа AL · 4 ат.% CU.",
            {
                "database_key": "al",
                "balance": "AL",
                "units": "at",
                "composition": "CU=4",
                "pressure_pa": 101325.0,
                "steel_mode": "stable",
            },
            {"single_temperature_al": 500.0},
        ),
    ]
    examples = [
        item for item in examples
        if item[2]["database_key"] in RELEASE_DATABASE_KEYS
    ]

    for label, description, context, widget_state in examples:
        with st.container(border=True):
            st.markdown(f"#### {label}")
            st.caption(description)
            if st.button(
                f"Загрузить пример {label.split(':', 1)[0]}",
                key=f"stage10_example_{context['database_key']}",
            ):
                queue_context_load(
                    context,
                    widget_state,
                    label=f"пример {label}",
                )
                st.rerun()


def render_diagnostics(
    project_root: str | Path,
    database_definitions: dict[str, dict[str, Any]],
    *,
    scheil_available: bool,
    scheil_import_error: str,
    kawin_available: bool = False,
    kawin_import_error: str = "",
    precipitation_available: bool = False,
    precipitation_import_error: str = "",
) -> None:
    st.subheader("Проверка установки и контрольные расчёты")
    st.caption(
        "Этот экран проверяет окружение, целостность release-баз и короткие "
        "эталонных расчёта. Он не заменяет экспериментальную валидацию."
    )

    st.markdown("### Окружение")
    env = environment_table(project_root)
    st.dataframe(env, width="stretch", hide_index=True)

    if scheil_available:
        st.success("Модуль Scheil–Gulliver доступен.")
    else:
        st.warning(
            "Модуль Scheil–Gulliver недоступен. Остальные функции работают. "
            f"Причина: {scheil_import_error or 'пакет scheil не установлен'}"
        )

    if kawin_available:
        st.success("Модуль диффузии Kawin доступен.")
    else:
        st.warning(
            "Модуль диффузии Kawin недоступен. Равновесные функции работают. "
            f"Причина: {kawin_import_error or 'пакет kawin не установлен'}"
        )

    if precipitation_available:
        st.success("Модуль кинетики выделений Kawin доступен.")
    else:
        st.warning(
            "Модуль кинетики выделений недоступен. Остальные функции работают. "
            f"Причина: {precipitation_import_error or 'Kawin precipitation не импортирован'}"
        )

    st.markdown("### Файлы баз")
    file_table = database_file_table(project_root, database_definitions)
    st.dataframe(file_table, width="stretch", hide_index=True)

    if release_calculation_button(
        "Проверить базы и запустить три контрольных расчёта",
        type="primary",
        key="stage10_run_smoke_tests",
    ):
        with st.status(
            "Загружаем базы и выполняем контрольные расчёты…",
            expanded=True,
        ) as status:
            database_table = database_diagnostic_table(
                project_root,
                database_definitions,
            )
            smoke = run_smoke_tests(project_root, database_definitions)
            st.session_state["stage10_database_diagnostics"] = database_table
            st.session_state["stage10_smoke_tests"] = smoke
            passed = bool(
                (database_table["Статус"] == "загружена").all()
                and (smoke["Статус"] == "пройдена").all()
            )
            status.update(
                label=(
                    "Базы и контрольные расчёты пройдены"
                    if passed
                    else "Есть ошибки в базах или контрольных расчётах"
                ),
                state="complete" if passed else "error",
                expanded=False,
            )

    database_table = st.session_state.get("stage10_database_diagnostics")
    if isinstance(database_table, pd.DataFrame):
        st.markdown("### Результат загрузки баз")
        st.dataframe(database_table, width="stretch", hide_index=True)

    smoke = st.session_state.get("stage10_smoke_tests")
    if isinstance(smoke, pd.DataFrame):
        if bool((smoke["Статус"] == "пройдена").all()):
            st.success("Все три контрольных расчёта пройдены.")
        else:
            st.error(
                "Хотя бы один контрольный расчёт не пройден. Не переходите "
                "к рабочим расчётам, пока причина не устранена."
            )
        st.dataframe(smoke, width="stretch", hide_index=True)

    diagnostic_payload = {
        "schema_version": 1,
        "created_at": now_iso(),
        "thermogar_version": APP_VERSION,
        "release_status": release_status(),
        "environment": env.to_dict(orient="records"),
        "databases": (
            database_table.to_dict(orient="records")
            if isinstance(database_table, pd.DataFrame)
            else file_table.to_dict(orient="records")
        ),
        "smoke_tests": (
            smoke.to_dict(orient="records")
            if isinstance(smoke, pd.DataFrame)
            else []
        ),
        "scheil_available": scheil_available,
        "scheil_import_error": scheil_import_error,
        "kawin_available": kawin_available,
        "kawin_import_error": kawin_import_error,
    }
    release_download_button(
        "Скачать отчёт диагностики",
        data=json_bytes(diagnostic_payload),
        file_name="ThermoGar_diagnostics.json",
        mime="application/json",
    )


# ---------------------------------------------------------------------------
# Происхождение и область применимости
# ---------------------------------------------------------------------------


def provenance_table(
    database_label: str,
    database_path: str | Path,
    calculation_kind: str,
    *,
    phase_mode: str = "",
) -> pd.DataFrame:
    path = Path(database_path)
    rows = [
        ("ThermoGar", APP_VERSION),
        ("Линия / gate", APP_STAGE),
        ("Класс выпуска", RELEASE_CLASS),
        ("Статус программы", SOFTWARE_RELEASE_STATUS),
        ("Статус материала", SCIENTIFIC_MATERIAL_STATUS),
        ("Производственное использование", PRODUCTION_USE),
        ("Дата расчёта", now_iso()),
        ("Вид расчёта", calculation_kind),
        ("База", database_label),
        ("Файл базы", str(path)),
        ("SHA-256 базы", file_sha256(path) if path.exists() else "файл не найден"),
        ("pycalphad", package_version("pycalphad")),
        ("Python", platform.python_version()),
        ("ОС", platform.platform()),
    ]
    if phase_mode:
        rows.append(("Выбор фаз", phase_mode))
    rows.extend(
        [
            (
                "Неопределённость",
                "не оценена: база не содержит универсальной доверительной вилки",
            ),
            (
                "Статус",
                "исследовательский расчёт; производственное использование запрещено",
            ),
        ]
    )
    return pd.DataFrame(rows, columns=["Параметр", "Значение"])


def render_scope_notice(*, calculation_kind: str) -> None:
    st.info(
        f"{calculation_kind}: ThermoGar показывает результат выбранной "
        "термодинамической модели. Численная проверка не оценивает ошибку "
        "базы и не заменяет аттестацию материала или расчёт в другой "
        "независимой системе."
    )

# ---------------------------------------------------------------------------
# Совместимые имена для основного приложения ThermoGar
# ---------------------------------------------------------------------------


def validate_single_result(
    summary: pd.DataFrame,
    overall: pd.DataFrame,
    phase_at: pd.DataFrame,
) -> dict[str, Any]:
    """Совместимый вызов: summary, overall, phase_at."""
    return validate_single_equilibrium(summary, phase_at, overall)


def validate_scan_result(
    dataframe: pd.DataFrame,
    coordinate_columns: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    if not coordinate_columns:
        raise ValueError("Не указана координата расчётной сетки.")
    return validate_phase_scan(dataframe, str(coordinate_columns[0]))


def render_quality_panel(report: dict[str, Any]) -> None:
    render_validation_report(report, expanded=False)


def render_friendly_error(
    error: Exception,
    *,
    context: str,
    paths: ThermoGarPaths,
) -> None:
    render_user_error(
        error,
        context=context,
        paths=paths,
    )


def render_preflight(
    project_root: str | Path,
    database_definitions: dict[str, dict[str, Any]],
    _load_database: Callable[..., Any] | None = None,
    _prepare_calculation: Callable[..., Any] | None = None,
    _summarize_equilibrium: Callable[..., Any] | None = None,
    scheil_available: bool = False,
    kawin_available: bool = False,
    kawin_import_error: str = "",
    precipitation_available: bool = False,
    precipitation_import_error: str = "",
) -> None:
    render_diagnostics(
        project_root,
        database_definitions,
        scheil_available=scheil_available,
        scheil_import_error=(
            ""
            if scheil_available
            else "пакет scheil не импортирован"
        ),
        kawin_available=kawin_available,
        kawin_import_error=kawin_import_error,
        precipitation_available=precipitation_available,
        precipitation_import_error=precipitation_import_error,
    )
