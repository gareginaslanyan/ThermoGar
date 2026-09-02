"""ThermoGar legacy one-dimensional diffusion and homogenization engine.

Модуль использует открытый пакет kawin поверх pycalphad и уже подключённых
параметров диффузионной подвижности MQ/MF. На экране показываются только те возможности,
которые реально реализованы: изотермическая 1D диффузионная пара с закрытыми
границами и локально-равновесная модель гомогенизации.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import hashlib
import re
from typing import Any, Callable

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import streamlit as st
from pycalphad import Database

from thermogar_palette import chart_roles, phase_styles
from thermogar_release_policy import (
    RELEASE_DATABASE_FILENAMES,
    RELEASE_DATABASE_KEYS,
    RELEASE_DATABASE_LABELS,
    RELEASE_DATABASE_RELATIVE_PATHS,
    RELEASE_DATABASE_SHA256,
    release_status,
)
from thermogar_release_ui import (
    release_calculation_button,
    release_download_button,
)


try:
    from kawin.diffusion import (
        HomogenizationModel,
        HomogenizationParameters,
        SinglePhaseModel,
    )
    from kawin.diffusion.DiffusionParameters import HashTable, computeMobility
    from kawin.diffusion.mesh import Cartesian1D, ProfileBuilder, StepProfile1D
    from kawin.solver import explicitEulerIterator
    from kawin.thermo import GeneralThermodynamics

    KAWIN_AVAILABLE = True
    KAWIN_IMPORT_ERROR = ""
except Exception as import_error:  # pragma: no cover - зависит от окружения
    HomogenizationModel = None
    HomogenizationParameters = None
    SinglePhaseModel = None
    HashTable = None
    computeMobility = None
    Cartesian1D = None
    ProfileBuilder = None
    StepProfile1D = None
    explicitEulerIterator = None
    GeneralThermodynamics = None
    KAWIN_AVAILABLE = False
    KAWIN_IMPORT_ERROR = str(import_error)


KINETIC_PARAMETER_TYPES = {"MQ", "MF", "DQ", "DF"}

DEFAULTS = {
    "ni": {
        "balance": "NI",
        "left": "CR=7.7, AL=5.4",
        "right": "CR=35.9, AL=6.2",
        "units": "at",
        "temperature_C": 1200.0,
        "length_um": 2000.0,
        "interface_pct": 50.0,
        "time_h": 100.0,
        "nodes": 80,
        "single_phase": "FCC_A1",
        "homogenization_phases": ["FCC_A1", "BCC_A2"],
    },
    "al": {
        "balance": "AL",
        "left": "CU=1",
        "right": "CU=5",
        "units": "at",
        "temperature_C": 500.0,
        "length_um": 200.0,
        "interface_pct": 50.0,
        "time_h": 24.0,
        "nodes": 80,
        "single_phase": "FCC_A1",
        "homogenization_phases": ["FCC_A1", "LIQUID"],
    },
    "fe": {
        "balance": "FE",
        "left": "C=0.1, CR=8",
        "right": "C=0.3, CR=14",
        "units": "wt",
        "temperature_C": 900.0,
        "length_um": 100.0,
        "interface_pct": 50.0,
        "time_h": 1.0,
        "nodes": 80,
        "single_phase": "FCC_A1",
        "homogenization_phases": ["FCC_A1", "BCC_A2"],
    },
}

# Fe-профиль исключает C15_LAVES из фаз, предлагаемых пользователю.
EXCLUDED_PHASES = {"fe": ("C15_LAVES",)}

HOMOGENIZATION_FUNCTIONS = {
    "Нижняя граница Хашина—Штрикмана": "hashin lower",
    "Верхняя граница Хашина—Штрикмана": "hashin upper",
    "Нижняя граница Винера": "wiener lower",
    "Верхняя граница Винера": "wiener upper",
    "Лабиринтная модель": "lab",
}


@dataclass
class CoupleDefinition:
    elements: list[str]
    independent_elements: list[str]
    left_at: np.ndarray
    right_at: np.ndarray
    left_wt: np.ndarray
    right_wt: np.ndarray


@dataclass
class DiffusionResult:
    database_key: str
    database_sha256: str
    input_provenance: str
    input_confirmation: bool
    provenance: dict[str, Any]
    method_key: str
    method_label: str
    elements: list[str]
    phases: list[str]
    z_um: np.ndarray
    initial_at: np.ndarray
    final_at: np.ndarray
    initial_wt: np.ndarray
    final_wt: np.ndarray
    phase_fractions: pd.DataFrame
    profile_table: pd.DataFrame
    balance_table: pd.DataFrame
    settings: pd.DataFrame
    profile_figure: plt.Figure
    phase_figure: plt.Figure | None
    max_balance_error: float
    actual_time_s: float
    quality: pd.DataFrame


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bind_release_database(
    database_key: str,
    database_path: str | Path,
    database_label: str,
) -> tuple[str, Path, str, str, Database]:
    """Resolve and reload exactly one hash-pinned SWR release database."""

    if not isinstance(database_key, str):
        raise ValueError("Ключ базы diffusion должен быть строкой.")
    canonical_key = database_key.strip().casefold()
    if canonical_key not in RELEASE_DATABASE_KEYS:
        raise ValueError(
            f"База {canonical_key!r} не входит в SWR release surface."
        )
    if not isinstance(database_label, str):
        raise ValueError("Название базы diffusion должно быть строкой.")
    supplied_label = database_label.strip()
    canonical_label = RELEASE_DATABASE_LABELS[canonical_key]
    if supplied_label and supplied_label != canonical_label:
        raise RuntimeError(
            "Diffusion отклонён: название базы не соответствует закреплённому "
            f"профилю {canonical_key!r}."
        )

    candidate_path = Path(database_path).resolve()
    expected_path = (
        Path(__file__).resolve().parent.parent
        / RELEASE_DATABASE_RELATIVE_PATHS[canonical_key]
    ).resolve()
    if (
        candidate_path != expected_path
        or candidate_path.name != RELEASE_DATABASE_FILENAMES[canonical_key]
        or not candidate_path.is_file()
    ):
        raise RuntimeError(
            "Diffusion отклонён: путь базы не соответствует закреплённому "
            f"профилю {canonical_key!r}."
        )

    expected_sha256 = RELEASE_DATABASE_SHA256[canonical_key]
    database_sha256 = _sha256(candidate_path)
    if database_sha256 != expected_sha256:
        raise RuntimeError(
            "Diffusion отклонён: SHA-256 базы не соответствует закреплённому "
            f"профилю {canonical_key!r}."
        )

    database = Database(str(candidate_path))
    if _sha256(candidate_path) != expected_sha256:
        raise RuntimeError(
            "Diffusion отклонён: файл базы изменился во время загрузки."
        )
    return (
        canonical_key,
        candidate_path,
        database_sha256,
        canonical_label,
        database,
    )


def _theme_type() -> str:
    try:
        return str(st.context.theme.type)
    except Exception:
        return "light"


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "не установлен"


def _parse_percent_text(text: str) -> dict[str, float]:
    text = str(text).strip()
    if not text:
        return {}

    pattern = re.compile(
        r"([A-Za-z]{1,2})\s*=\s*([+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+))"
    )
    matches = list(pattern.finditer(text))
    if not matches:
        raise ValueError("Не удалось прочитать состав. Пример: CR=18, NI=8")

    remainder = pattern.sub("", text)
    remainder = re.sub(r"[\s,;]+", "", remainder)
    if remainder:
        raise ValueError(f"Непонятный фрагмент в составе: {remainder!r}")

    result: dict[str, float] = {}
    for match in matches:
        element = match.group(1).upper()
        value = float(match.group(2).replace(",", "."))
        if element in result:
            raise ValueError(f"Элемент {element} указан более одного раза.")
        if value < 0:
            raise ValueError(f"Содержание {element} не может быть отрицательным.")
        result[element] = value
    return result


def _atomic_masses(db: Any, elements: list[str]) -> np.ndarray:
    masses = []
    for element in elements:
        try:
            masses.append(float(db.refstates[element]["mass"]))
        except Exception as error:
            raise ValueError(
                f"В базе не найдена атомная масса для {element}."
            ) from error
    return np.asarray(masses, dtype=float)


def _percent_to_vectors(
    db: Any,
    entered: dict[str, float],
    balance: str,
    elements: list[str],
    units: str,
) -> tuple[np.ndarray, np.ndarray]:
    if balance in entered:
        raise ValueError(
            f"{balance} выбран как элемент-основа; не указывайте его в добавках."
        )

    unknown = sorted(set(entered) - set(elements))
    if unknown:
        raise ValueError("Элементы отсутствуют в выбранной базе: " + ", ".join(unknown))

    total_added = float(sum(entered.values()))
    if total_added >= 100.0:
        raise ValueError("Сумма добавок на каждой стороне должна быть меньше 100 %.")

    percentages = np.zeros(len(elements), dtype=float)
    for index, element in enumerate(elements):
        if element == balance:
            percentages[index] = 100.0 - total_added
        else:
            percentages[index] = float(entered.get(element, 0.0))

    if units == "at":
        x_at = percentages / 100.0
        masses = _atomic_masses(db, elements)
        weighted = x_at * masses
        x_wt = weighted / np.sum(weighted)
    elif units == "wt":
        x_wt = percentages / 100.0
        masses = _atomic_masses(db, elements)
        moles = x_wt / masses
        x_at = moles / np.sum(moles)
    else:
        raise ValueError("Неизвестные единицы состава.")

    return x_at, x_wt


def _build_couple(
    db: Any,
    balance: str,
    left_text: str,
    right_text: str,
    units: str,
) -> CoupleDefinition:
    balance = str(balance).upper()
    available = {str(element).upper() for element in db.elements if str(element) != "VA"}
    if balance not in available:
        raise ValueError(f"Элемент-основа {balance} отсутствует в базе.")

    left_entered = _parse_percent_text(left_text)
    right_entered = _parse_percent_text(right_text)
    used = sorted((set(left_entered) | set(right_entered)) - {balance})

    if not used:
        raise ValueError("Левая и правая стороны должны различаться хотя бы одной добавкой.")

    elements = [balance] + used
    if len(elements) > 4:
        raise ValueError(
            "В исследовательском diffusion mode разрешено не более четырёх элементов одновременно "
            "(основа + три добавки). Это ограничение первого кинетического релиза."
        )

    unknown = sorted(set(elements) - available)
    if unknown:
        raise ValueError("Элементы отсутствуют в базе: " + ", ".join(unknown))

    left_at, left_wt = _percent_to_vectors(
        db,
        left_entered,
        balance,
        elements,
        units,
    )
    right_at, right_wt = _percent_to_vectors(
        db,
        right_entered,
        balance,
        elements,
        units,
    )

    if np.allclose(left_at, right_at, atol=1e-12):
        raise ValueError("Левый и правый составы совпадают — диффузионной пары нет.")

    return CoupleDefinition(
        elements=elements,
        independent_elements=elements[1:],
        left_at=left_at,
        right_at=right_at,
        left_wt=left_wt,
        right_wt=right_wt,
    )


def _profile_at_to_wt(db: Any, profile_at: np.ndarray, elements: list[str]) -> np.ndarray:
    masses = _atomic_masses(db, elements)
    weighted = np.asarray(profile_at, dtype=float) * masses[np.newaxis, :]
    denominator = np.sum(weighted, axis=1, keepdims=True)
    return np.divide(
        weighted,
        denominator,
        out=np.zeros_like(weighted),
        where=denominator > 0,
    )


def _kinetic_summary(db: Any) -> tuple[pd.DataFrame, list[str], list[str]]:
    records = db._parameters.all() if hasattr(db, "_parameters") else []
    rows = [
        record
        for record in records
        if record.get("parameter_type") in KINETIC_PARAMETER_TYPES
    ]

    phase_counts: dict[tuple[str, str], int] = {}
    species: set[str] = set()
    for record in rows:
        phase = str(record.get("phase_name", ""))
        parameter_type = str(record.get("parameter_type", ""))
        phase_counts[(phase, parameter_type)] = phase_counts.get((phase, parameter_type), 0) + 1
        diffusing = record.get("diffusing_species")
        name = str(getattr(diffusing, "name", "") or "")
        if name:
            species.add(name.upper())

    table_rows = [
        {
            "Фаза": phase,
            "Тип параметра": parameter_type,
            "Количество": count,
        }
        for (phase, parameter_type), count in sorted(phase_counts.items())
    ]
    table = pd.DataFrame(table_rows)
    phases = sorted({phase for phase, _ptype in phase_counts if phase})
    return table, sorted(species), phases


def _phase_mobility_coverage(db: Any) -> dict[str, set[str]]:
    """Собрать диффундирующие элементы отдельно для каждой фазы."""
    coverage: dict[str, set[str]] = {}
    records = db._parameters.all() if hasattr(db, "_parameters") else []
    for record in records:
        if record.get("parameter_type") not in KINETIC_PARAMETER_TYPES:
            continue
        phase = str(record.get("phase_name", ""))
        diffusing = record.get("diffusing_species")
        species = str(getattr(diffusing, "name", "") or "").upper()
        if phase and species:
            coverage.setdefault(phase, set()).add(species)
    return coverage


def _selectable_phases(database_key: str, phases: list[str]) -> list[str]:
    """Убрать из списка фазы, недоступные пользователю для данной базы."""
    excluded = EXCLUDED_PHASES.get(str(database_key).strip().casefold(), ())
    return [phase for phase in phases if phase not in excluded]


def _compatible_mobility_phases(db: Any, elements: list[str]) -> list[str]:
    required = set(elements)
    coverage = _phase_mobility_coverage(db)
    return sorted(
        phase
        for phase, species in coverage.items()
        if phase in db.phases and required.issubset(species)
    )


def _validate_mobility_coverage(
    couple: CoupleDefinition,
    species: list[str],
    db: Any | None = None,
    phases: list[str] | None = None,
) -> None:
    missing = [element for element in couple.elements if element not in species]
    if missing:
        raise ValueError(
            "В базе подвижностей нет параметров для: " + ", ".join(missing)
        )

    if db is not None and phases:
        phase_coverage = _phase_mobility_coverage(db)
        incomplete: list[str] = []
        for phase in phases:
            missing_in_phase = sorted(set(couple.elements) - phase_coverage.get(phase, set()))
            if missing_in_phase:
                incomplete.append(f"{phase}: {', '.join(missing_in_phase)}")
        if incomplete:
            raise ValueError(
                "Не все выбранные фазы имеют полный набор параметров подвижности: "
                + "; ".join(incomplete)
            )


def _make_initial_profile(
    z_m: np.ndarray,
    interface_m: float,
    left_at: np.ndarray,
    right_at: np.ndarray,
) -> np.ndarray:
    result = np.empty((len(z_m), len(left_at)), dtype=float)
    # StepProfile1D assigns the right composition at z >= interface.
    # Keep the reconstructed initial profile identical to the solver input,
    # including meshes with a cell centre exactly on the interface.
    mask = z_m < interface_m
    result[mask, :] = left_at
    result[~mask, :] = right_at
    return result


def _phase_fraction_dataframe(model: Any, phases: list[str], z_um: np.ndarray) -> pd.DataFrame:
    full_x = np.asarray(model.getCompositions(), dtype=float)
    mesh_z = np.asarray(model.mesh.z)
    temperature = model.temperatureParameters(mesh_z, model.currentTime)
    mobility_data = computeMobility(
        model.therm,
        full_x[:, 1:],
        temperature,
        HashTable(),
    )

    result: dict[str, Any] = {"Расстояние, мкм": z_um}
    for phase in phases:
        fractions: list[float] = []
        for labels, values in zip(
            mobility_data.phases,
            mobility_data.phase_fractions,
        ):
            labels_array = np.asarray(labels)
            values_array = np.asarray(values, dtype=float)
            fractions.append(float(np.sum(values_array[labels_array == phase])))
        result[f"{phase}, локальная доля, %"] = 100.0 * np.asarray(fractions)

    return pd.DataFrame(result)


def _profile_dataframe(
    z_um: np.ndarray,
    elements: list[str],
    initial_at: np.ndarray,
    final_at: np.ndarray,
    initial_wt: np.ndarray,
    final_wt: np.ndarray,
) -> pd.DataFrame:
    data: dict[str, Any] = {"Расстояние, мкм": z_um}
    for index, element in enumerate(elements):
        data[f"{element}, нач., ат.%"] = 100.0 * initial_at[:, index]
        data[f"{element}, итог, ат.%"] = 100.0 * final_at[:, index]
        data[f"{element}, нач., мас.%"] = 100.0 * initial_wt[:, index]
        data[f"{element}, итог, мас.%"] = 100.0 * final_wt[:, index]
    return pd.DataFrame(data)


def _balance_dataframe(
    elements: list[str],
    initial_at: np.ndarray,
    final_at: np.ndarray,
) -> tuple[pd.DataFrame, float]:
    initial_mean = np.mean(initial_at, axis=0)
    final_mean = np.mean(final_at, axis=0)
    difference = final_mean - initial_mean
    maximum = float(np.max(np.abs(difference)))
    table = pd.DataFrame(
        {
            "Элемент": elements,
            "Среднее начальное, ат.%": 100.0 * initial_mean,
            "Среднее итоговое, ат.%": 100.0 * final_mean,
            "Разница, ат.%": 100.0 * difference,
        }
    )
    return table, maximum


def _apply_chart_chrome(axis: Any, roles: dict[str, str]) -> None:
    axis.set_facecolor(roles["background"])
    axis.grid(True, color=roles["grid"], alpha=0.35)
    axis.tick_params(colors=roles["axis"])
    axis.xaxis.label.set_color(roles["axis"])
    axis.yaxis.label.set_color(roles["axis"])
    axis.title.set_color(roles["text"])
    for spine in axis.spines.values():
        spine.set_color(roles["grid"])


def _profile_figure(
    z_um: np.ndarray,
    elements: list[str],
    initial: np.ndarray,
    final: np.ndarray,
    units_label: str,
    title: str,
) -> plt.Figure:
    theme = _theme_type()
    roles = chart_roles(theme)
    styles = phase_styles(elements, theme)
    figure, axis = plt.subplots(figsize=(10, 6))
    figure.patch.set_facecolor(roles["background"])

    for index, element in enumerate(elements):
        style = styles[element]
        axis.plot(
            z_um,
            100.0 * initial[:, index],
            linestyle="--",
            linewidth=1.2,
            color=style["color"],
            alpha=0.65,
        )
        axis.plot(
            z_um,
            100.0 * final[:, index],
            linestyle=style["linestyle"],
            linewidth=2.0,
            color=style["color"],
            marker=style["marker"],
            markevery=max(1, len(z_um) // 12),
            markersize=4,
        )
        axis.text(
            float(z_um[-1]),
            float(100.0 * final[-1, index]),
            f"  {element}",
            color=style["color"],
            va="center",
        )

    axis.set_xlabel("Расстояние, мкм")
    axis.set_ylabel(f"Содержание, {units_label}")
    axis.set_title(title)
    _apply_chart_chrome(axis, roles)

    legend_items = [
        Line2D([0], [0], color=roles["axis"], linestyle="--", label="Начальный профиль"),
        Line2D([0], [0], color=roles["axis"], linestyle="-", label="После выдержки"),
    ]
    axis.legend(handles=legend_items, frameon=False, labelcolor=roles["axis"])
    figure.tight_layout()
    return figure


def _phase_figure(phase_table: pd.DataFrame, phases: list[str]) -> plt.Figure | None:
    if phase_table.empty or not phases:
        return None

    theme = _theme_type()
    roles = chart_roles(theme)
    styles = phase_styles(phases, theme)
    figure, axis = plt.subplots(figsize=(10, 5.5))
    figure.patch.set_facecolor(roles["background"])
    x = phase_table["Расстояние, мкм"].to_numpy(dtype=float)

    for phase in phases:
        column = f"{phase}, локальная доля, %"
        if column not in phase_table:
            continue
        style = styles[phase]
        y = phase_table[column].to_numpy(dtype=float)
        axis.plot(
            x,
            y,
            color=style["color"],
            linestyle=style["linestyle"],
            marker=style["marker"],
            markevery=max(1, len(x) // 12),
            markersize=4,
            linewidth=2.0,
            label=phase,
        )
        axis.text(float(x[-1]), float(y[-1]), f"  {phase}", color=style["color"], va="center")

    axis.set_xlabel("Расстояние, мкм")
    axis.set_ylabel("Локальная равновесная доля фазы, %")
    axis.set_title("Локальное фазовое состояние после диффузии")
    _apply_chart_chrome(axis, roles)
    axis.set_ylim(-1.0, 101.0)
    axis.legend(frameon=False, labelcolor=roles["axis"])
    figure.tight_layout()
    return figure


def _run_model(
    *,
    db: Any,
    database_path: Path,
    database_key: str,
    database_sha256: str,
    database_label: str,
    input_provenance: str,
    input_confirmation: bool,
    couple: CoupleDefinition,
    method_key: str,
    phases: list[str],
    temperature_C: float,
    length_um: float,
    interface_pct: float,
    time_h: float,
    nodes: int,
    homogenization_function: str = "hashin lower",
    eps: float = 0.01,
    labyrinth_factor: float = 1.5,
) -> DiffusionResult:
    if not KAWIN_AVAILABLE:
        raise RuntimeError(
            "Пакет kawin не установлен или не загрузился: " + KAWIN_IMPORT_ERROR
        )
    if length_um <= 0:
        raise ValueError("Длина области должна быть больше нуля.")
    if not (1.0 <= interface_pct <= 99.0):
        raise ValueError("Граница пары должна находиться между 1 и 99 % длины.")
    if time_h <= 0:
        raise ValueError("Время выдержки должно быть больше нуля.")
    if not (12 <= int(nodes) <= 160):
        raise ValueError("Число ячеек должно быть от 12 до 160.")
    if not phases:
        raise ValueError("Выберите хотя бы одну фазу.")

    length_m = float(length_um) * 1e-6
    interface_m = length_m * float(interface_pct) / 100.0
    temperature_K = float(temperature_C) + 273.15
    time_s = float(time_h) * 3600.0

    mesh = Cartesian1D(couple.independent_elements, [0.0, length_m], int(nodes))
    profile = ProfileBuilder()
    profile.addBuildStep(
        StepProfile1D(
            interface_m,
            couple.left_at[1:].tolist(),
            couple.right_at[1:].tolist(),
        ),
        couple.independent_elements,
    )
    mesh.setResponseProfile(profile)

    if _sha256(database_path) != database_sha256:
        raise RuntimeError(
            "Diffusion отклонён: release-база изменилась перед запуском Kawin."
        )
    thermodynamics = GeneralThermodynamics(
        db,
        couple.elements,
        phases,
    )
    if _sha256(database_path) != database_sha256:
        raise RuntimeError(
            "Diffusion отклонён: release-база изменилась при загрузке Kawin."
        )

    if method_key == "single":
        if len(phases) != 1:
            raise ValueError("Однофазная модель требует ровно одну фазу.")
        model = SinglePhaseModel(
            mesh,
            couple.elements,
            phases,
            thermodynamics=thermodynamics,
            temperature=temperature_K,
            record=False,
        )
        method_label = "Однофазная диффузионная пара"
    elif method_key == "homogenization":
        parameters = HomogenizationParameters(
            homogenizationFunction=homogenization_function,
            labyrinthFactor=float(labyrinth_factor),
            eps=float(eps),
            postProcessFunction="none",
        )
        model = HomogenizationModel(
            mesh,
            couple.elements,
            phases,
            thermodynamics=thermodynamics,
            temperature=temperature_K,
            homogenizationParameters=parameters,
            record=False,
        )
        method_label = "Многофазная гомогенизация"
    else:
        raise ValueError("Неизвестный метод диффузии.")

    if hasattr(model, "useCache"):
        model.useCache(True)
    if hasattr(model, "setHashSensitivity"):
        model.setHashSensitivity(4)

    model.solve(
        time_s,
        iterator=explicitEulerIterator,
        verbose=False,
        vIt=500,
        minDtFrac=1e-10,
    )

    z_m = np.asarray(model.mesh.z, dtype=float).reshape(-1)
    z_um = z_m * 1e6
    final_at = np.asarray(model.getCompositions(), dtype=float)
    initial_at = _make_initial_profile(
        z_m,
        interface_m,
        couple.left_at,
        couple.right_at,
    )
    initial_wt = _profile_at_to_wt(db, initial_at, couple.elements)
    final_wt = _profile_at_to_wt(db, final_at, couple.elements)

    phase_table = _phase_fraction_dataframe(model, phases, z_um)
    profile_table = _profile_dataframe(
        z_um,
        couple.elements,
        initial_at,
        final_at,
        initial_wt,
        final_wt,
    )
    balance_table, max_balance_error = _balance_dataframe(
        couple.elements,
        initial_at,
        final_at,
    )

    settings_rows: list[tuple[str, Any]] = [
        ("Метод", method_label),
        ("Ключ release-базы", database_key),
        ("Название release-базы", database_label),
        ("Термодинамическая база и подвижности", str(database_path)),
        ("SHA-256 release-базы", database_sha256),
        ("Kawin", _package_version("kawin")),
        ("Температура, °C", float(temperature_C)),
        ("Время, ч", float(time_h)),
        ("Длина области, мкм", float(length_um)),
        ("Граница пары, % длины", float(interface_pct)),
        ("Число конечных объёмов", int(nodes)),
        ("Граничные условия", "нулевой поток на обоих концах"),
        ("Система отсчёта", "объёмно-фиксированная" if method_key == "single" else "локальное равновесие + эффективная подвижность"),
        ("Элементы", ", ".join(couple.elements)),
        ("Фазы", ", ".join(phases)),
        ("Источник/назначение входов", input_provenance),
        ("Research-only сценарий подтверждён", "да"),
        ("Материальная квалификация", "отсутствует; production use denied"),
    ]
    if method_key == "homogenization":
        settings_rows.extend(
            [
                ("Усреднение подвижности", homogenization_function),
                ("Сглаживающий коэффициент eps", float(eps)),
                ("Лабиринтный фактор", float(labyrinth_factor)),
            ]
        )
    settings = pd.DataFrame(settings_rows, columns=["Параметр", "Значение"])

    profile_figure = _profile_figure(
        z_um,
        couple.elements,
        initial_at,
        final_at,
        "ат.%",
        f"{method_label}: профиль состава",
    )
    phase_figure = _phase_figure(phase_table, phases)
    composition_sum_error = float(
        np.max(np.abs(np.sum(final_at, axis=1) - 1.0))
    )
    quality = pd.DataFrame(
        [
            {
                "Проверка": "Сумма состава в каждом узле",
                "Значение": composition_sum_error,
                "Допуск": 1e-8,
                "Статус": "пройдена" if composition_sum_error <= 1e-8 else "не пройдена",
            },
            {
                "Проверка": "Сохранение среднего состава",
                "Значение": max_balance_error,
                "Допуск": 1e-6,
                "Статус": "пройдена" if max_balance_error <= 1e-6 else "не пройдена",
            },
        ]
    )

    provenance = {
        "schema_version": 1,
        "release_status": release_status(),
        "database_key": database_key,
        "database_path": str(database_path),
        "database_sha256": database_sha256,
        "database_label": database_label,
        "input_provenance": input_provenance,
        "input_confirmation": input_confirmation,
        "result_scope": (
            "SOFTWARE_MODEL_OUTPUT_NOT_EXPERIMENTAL_VALIDATION_OR_"
            "MATERIAL_QUALIFICATION"
        ),
    }

    return DiffusionResult(
        database_key=database_key,
        database_sha256=database_sha256,
        input_provenance=input_provenance,
        input_confirmation=input_confirmation,
        provenance=provenance,
        method_key=method_key,
        method_label=method_label,
        elements=couple.elements,
        phases=phases,
        z_um=z_um,
        initial_at=initial_at,
        final_at=final_at,
        initial_wt=initial_wt,
        final_wt=final_wt,
        phase_fractions=phase_table,
        profile_table=profile_table,
        balance_table=balance_table,
        settings=settings,
        profile_figure=profile_figure,
        phase_figure=phase_figure,
        max_balance_error=max_balance_error,
        actual_time_s=float(model.currentTime),
        quality=quality,
    )


def run_diffusion(
    *,
    db: Any,
    database_key: str,
    database_path: str | Path,
    database_label: str = "",
    balance: str,
    units: str,
    left_text: str,
    right_text: str,
    temperature_c: float,
    time_h: float,
    length_um: float,
    interface_percent: float,
    nodes: int,
    phases: list[str],
    model_kind: str = "single",
    homogenization_function: str = "hashin lower",
    eps: float = 0.01,
    labyrinth_factor: float = 1.5,
    input_provenance: str,
    input_confirmation: bool,
) -> DiffusionResult:
    """Run a declared SWR scenario against one canonical, hash-pinned database."""

    if not isinstance(input_provenance, str):
        raise ValueError("Источник/назначение diffusion inputs должен быть строкой.")
    input_provenance = input_provenance.strip()
    if not input_provenance:
        raise ValueError(
            "Для diffusion обязателен источник или явная маркировка declared "
            "scenario inputs."
        )
    if input_confirmation is not True:
        raise ValueError(
            "Для diffusion требуется явное подтверждение research-only сценария."
        )
    if not isinstance(model_kind, str) or model_kind not in {
        "single",
        "homogenization",
    }:
        raise ValueError(
            "model_kind diffusion должен быть строго 'single' или "
            "'homogenization'."
        )
    if (
        model_kind == "homogenization"
        and (
            not isinstance(homogenization_function, str)
            or homogenization_function not in set(HOMOGENIZATION_FUNCTIONS.values())
        )
    ):
        raise ValueError("Неизвестная модель эффективной подвижности diffusion.")

    # Never trust the independently supplied Database object: reload the
    # canonical bytes after key/path/SHA validation and bind every downstream
    # inspection and calculation to that same object.
    (
        database_key,
        database_path,
        database_sha256,
        database_label,
        db,
    ) = _bind_release_database(
        database_key,
        database_path,
        database_label,
    )
    couple = _build_couple(db, balance, left_text, right_text, units)
    _table, species, _phases = _kinetic_summary(db)
    _validate_mobility_coverage(couple, species, db, list(phases))
    return _run_model(
        db=db,
        database_path=database_path,
        database_key=database_key,
        database_sha256=database_sha256,
        database_label=database_label,
        input_provenance=input_provenance,
        input_confirmation=True,
        couple=couple,
        method_key=model_kind,
        phases=list(phases),
        temperature_C=float(temperature_c),
        length_um=float(length_um),
        interface_pct=float(interface_percent),
        time_h=float(time_h),
        nodes=int(nodes),
        homogenization_function=homogenization_function,
        eps=float(eps),
        labyrinth_factor=float(labyrinth_factor),
    )


def _result_display(
    result: DiffusionResult,
    state_key: str,
    dataframe_to_excel: Callable[[dict[str, pd.DataFrame]], bytes],
    figure_to_png: Callable[[plt.Figure], bytes],
) -> None:
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.metric("Метод", result.method_label)
    with metric_col2:
        st.metric("Время выдержки, ч", f"{float(result.settings.loc[result.settings['Параметр'] == 'Время, ч', 'Значение'].iloc[0]):.3g}")
    with metric_col3:
        st.metric("Макс. ошибка баланса, ат.%", f"{100.0 * result.max_balance_error:.3e}")

    if result.max_balance_error <= 1e-6:
        st.success("Численная проверка сохранения среднего состава пройдена.")
    elif result.max_balance_error <= 1e-4:
        st.warning("Баланс состава выполнен с повышенной численной погрешностью.")
    else:
        st.error("Ошибка сохранения состава слишком велика. Увеличьте число ячеек или уменьшите время шага задачи.")

    output_units = st.radio(
        "Единицы графика состава",
        ["атомные %", "массовые %"],
        horizontal=True,
        key=f"{state_key}_output_units",
    )

    if output_units == "атомные %":
        figure = result.profile_figure
        table_columns = ["Расстояние, мкм"] + [
            column for column in result.profile_table.columns if "ат.%" in column
        ]
    else:
        figure = _profile_figure(
            result.z_um,
            result.elements,
            result.initial_wt,
            result.final_wt,
            "мас.%",
            f"{result.method_label}: профиль состава",
        )
        table_columns = ["Расстояние, мкм"] + [
            column for column in result.profile_table.columns if "мас.%" in column
        ]

    st.pyplot(figure, use_container_width=False)
    st.dataframe(
        result.profile_table[table_columns],
        width="stretch",
        hide_index=True,
    )

    if result.phase_figure is not None:
        st.markdown("### Локальные равновесные доли фаз")
        st.pyplot(result.phase_figure, use_container_width=False)
        st.dataframe(result.phase_fractions, width="stretch", hide_index=True)

    with st.expander("Проверка баланса и параметры расчёта"):
        st.dataframe(result.balance_table, width="stretch", hide_index=True)
        st.dataframe(result.settings, width="stretch", hide_index=True)

    excel_bytes = dataframe_to_excel(
        {
            "Параметры": result.settings,
            "Профили": result.profile_table,
            "Фазовые доли": result.phase_fractions,
            "Баланс": result.balance_table,
        }
    )
    download_col1, download_col2, download_col3 = st.columns(3)
    with download_col1:
        release_download_button(
            "Скачать Excel",
            data=excel_bytes,
            file_name=f"ThermoGar_{result.method_key}_diffusion.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{state_key}_excel",
        )
    with download_col2:
        release_download_button(
            "Скачать профиль PNG",
            data=figure_to_png(figure),
            file_name=f"ThermoGar_{result.method_key}_profile.png",
            mime="image/png",
            key=f"{state_key}_profile_png",
        )
    with download_col3:
        if result.phase_figure is not None:
            release_download_button(
                "Скачать фазы PNG",
                data=figure_to_png(result.phase_figure),
                file_name=f"ThermoGar_{result.method_key}_phases.png",
                mime="image/png",
                key=f"{state_key}_phase_png",
            )


def _common_inputs(
    *,
    db: Any,
    database_key: str,
    prefix: str,
) -> dict[str, Any]:
    defaults = DEFAULTS.get(database_key, DEFAULTS["ni"])
    available = sorted(str(element) for element in db.elements if str(element) != "VA")
    default_balance = defaults["balance"] if defaults["balance"] in available else available[0]

    balance = st.selectbox(
        "Элемент-основа",
        available,
        index=available.index(default_balance),
        key=f"{prefix}_balance_{database_key}",
    )
    units_label = st.radio(
        "Единицы исходных составов",
        ["атомные %", "массовые %"],
        index=0 if defaults["units"] == "at" else 1,
        horizontal=True,
        key=f"{prefix}_units_{database_key}",
    )
    units = "at" if units_label == "атомные %" else "wt"

    left_col, right_col = st.columns(2)
    with left_col:
        left_text = st.text_area(
            "Левая сторона",
            value=defaults["left"],
            help="Остаток до 100 % считается элементом-основой.",
            key=f"{prefix}_left_{database_key}",
        )
    with right_col:
        right_text = st.text_area(
            "Правая сторона",
            value=defaults["right"],
            help="Используйте тот же набор элементов; отсутствующий элемент считается равным 0 %.",
            key=f"{prefix}_right_{database_key}",
        )

    temperature_C = st.number_input(
        "Температура выдержки, °C",
        value=float(defaults["temperature_C"]),
        step=10.0,
        key=f"{prefix}_temperature_{database_key}",
    )

    length_col, interface_col, time_col, nodes_col = st.columns(4)
    with length_col:
        length_um = st.number_input(
            "Длина области, мкм",
            min_value=1.0,
            value=float(defaults["length_um"]),
            step=10.0,
            key=f"{prefix}_length_{database_key}",
        )
    with interface_col:
        interface_pct = st.number_input(
            "Граница пары, %",
            min_value=1.0,
            max_value=99.0,
            value=float(defaults["interface_pct"]),
            step=1.0,
            key=f"{prefix}_interface_{database_key}",
        )
    with time_col:
        time_h = st.number_input(
            "Время, ч",
            min_value=0.001,
            value=float(defaults["time_h"]),
            step=1.0,
            key=f"{prefix}_time_{database_key}",
        )
    with nodes_col:
        nodes = st.number_input(
            "Ячеек",
            min_value=12,
            max_value=160,
            value=int(defaults["nodes"]),
            step=4,
            key=f"{prefix}_nodes_{database_key}",
        )

    input_provenance = st.text_area(
        "Источник и назначение diffusion inputs",
        value="",
        help=(
            "Укажите источник состава, температуры и времени либо явно "
            "пометьте синтетический software-сценарий. Это не является "
            "экспериментальной валидацией."
        ),
        key=f"{prefix}_input_provenance_{database_key}",
    )
    input_confirmation = st.checkbox(
        "Подтверждаю: это research-only сценарий без материальной квалификации",
        value=False,
        key=f"{prefix}_input_confirmation_{database_key}",
    )

    return {
        "balance": balance,
        "units": units,
        "units_label": units_label,
        "left_text": left_text,
        "right_text": right_text,
        "temperature_C": float(temperature_C),
        "length_um": float(length_um),
        "interface_pct": float(interface_pct),
        "time_h": float(time_h),
        "nodes": int(nodes),
        "input_provenance": input_provenance,
        "input_confirmation": bool(input_confirmation),
    }


def render_kinetics_section(
    *,
    db: Any,
    database_key: str,
    database_path: str | Path,
    database_label: str,
    project_root: str | Path,
    current_context: dict[str, Any],
    dataframe_to_excel: Callable[[dict[str, pd.DataFrame]], bytes],
    figure_to_png: Callable[[plt.Figure], bytes],
    render_error: Callable[..., None],
    record_history: Callable[..., None],
) -> None:
    """Показать исследовательский раздел диффузии и гомогенизации."""
    database_path = Path(database_path)
    defaults = DEFAULTS.get(database_key, DEFAULTS["ni"])

    st.subheader("Диффузия и гомогенизация")
    st.caption(
        "ThermoGar использует параметры диффузионной подвижности текущей базы и открытый "
        "решатель Kawin. Исследовательский режим рассчитывает изотермическую одномерную "
        "диффузию; это модель, а не экспериментально аттестованная технология."
    )

    if not KAWIN_AVAILABLE:
        st.error(
            "Для этого раздела не установлен пакет kawin. Установите его в "
            "окружение ThermoGar и перезапустите приложение."
        )
        st.code(
            "./.venv-mac/bin/python -m pip install 'kawin==0.5.0' 'espei==0.9.1'\n"
            ".\\.venv-windows\\Scripts\\python.exe -m pip install kawin==0.5.0 espei==0.9.1",
            language="bash",
        )
        if KAWIN_IMPORT_ERROR:
            st.caption(f"Техническая причина: {KAWIN_IMPORT_ERROR}")
        return

    kinetics_table, diffusing_species, kinetic_phases = _kinetic_summary(db)

    single_tab, homogenization_tab, coverage_tab = st.tabs(
        [
            "Однофазная пара",
            "Многофазная гомогенизация",
            "Покрытие базы подвижностей",
        ]
    )

    with single_tab:
        st.markdown("### Однофазная диффузионная пара")
        st.caption(
            "Во всей области принудительно используется одна выбранная фаза. "
            "Модель не создаёт новую фазу при пересечении фазовой границы."
        )
        common = _common_inputs(db=db, database_key=database_key, prefix="kin_single")

        try:
            preview_couple = _build_couple(
                db,
                common["balance"],
                common["left_text"],
                common["right_text"],
                common["units"],
            )
            phase_options = _selectable_phases(
                database_key,
                _compatible_mobility_phases(db, preview_couple.elements),
            )
        except Exception as preview_error:
            preview_couple = None
            phase_options = []
            st.warning(f"Исправьте составы пары: {preview_error}")

        if not phase_options:
            st.error(
                "Для выбранной системы нет фазы с полным набором "
                "MQ/MF/DQ/DF-параметров."
            )
        else:
            preferred = defaults["single_phase"]
            default_index = phase_options.index(preferred) if preferred in phase_options else 0
            phase = st.selectbox(
                "Фаза для всего профиля",
                phase_options,
                index=default_index,
                key=f"kin_single_phase_{database_key}",
            )

            st.info(
                "Границы закрыты: поток через левый и правый торцы равен нулю. "
                "Составы задаются в ат.% или мас.%, внутри решателя используются атомные доли."
            )

            if release_calculation_button(
                "Рассчитать однофазную диффузию",
                type="primary",
                key=f"kin_single_run_{database_key}",
                disabled=(
                    not bool(str(common["input_provenance"]).strip())
                    or not common["input_confirmation"]
                ),
            ):
                try:
                    with st.spinner("Расчёт диффузионного профиля…"):
                        result = run_diffusion(
                            db=db,
                            database_key=database_key,
                            database_path=database_path,
                            database_label=database_label,
                            balance=common["balance"],
                            units=common["units"],
                            left_text=common["left_text"],
                            right_text=common["right_text"],
                            temperature_c=common["temperature_C"],
                            time_h=common["time_h"],
                            length_um=common["length_um"],
                            interface_percent=common["interface_pct"],
                            nodes=common["nodes"],
                            phases=[phase],
                            model_kind="single",
                            input_provenance=common["input_provenance"],
                            input_confirmation=common["input_confirmation"],
                        )
                    st.session_state[f"kin_single_result_{database_key}"] = result
                    record_history(
                        project_root,
                        "Однофазная диффузионная пара",
                        current_context,
                        {
                            "database": database_label,
                            "elements": result.elements,
                            "phase": phase,
                            "temperature_C": common["temperature_C"],
                            "time_h": common["time_h"],
                            "length_um": common["length_um"],
                            "nodes": common["nodes"],
                            "kawin": _package_version("kawin"),
                            "database_sha256": result.database_sha256,
                            "input_provenance": result.input_provenance,
                            "input_confirmation": result.input_confirmation,
                        },
                    )
                except Exception as error:
                    render_error(error, context="однофазная диффузионная пара")

            result = st.session_state.get(f"kin_single_result_{database_key}")
            if isinstance(result, DiffusionResult):
                _result_display(
                    result,
                    f"kin_single_{database_key}",
                    dataframe_to_excel,
                    figure_to_png,
                )

    with homogenization_tab:
        st.markdown("### Многофазная гомогенизация")
        st.caption(
            "Каждая ячейка считается локально равновесной. Поток определяется "
            "градиентом химического потенциала и эффективной подвижностью, зависящей "
            "от выбранной геометрической модели фаз."
        )
        common = _common_inputs(db=db, database_key=database_key, prefix="kin_hom")

        try:
            preview_couple = _build_couple(
                db,
                common["balance"],
                common["left_text"],
                common["right_text"],
                common["units"],
            )
            phase_options = _selectable_phases(
                database_key,
                _compatible_mobility_phases(db, preview_couple.elements),
            )
        except Exception as preview_error:
            preview_couple = None
            phase_options = []
            st.warning(f"Исправьте составы пары: {preview_error}")

        default_phases = [
            phase for phase in defaults["homogenization_phases"] if phase in phase_options
        ]
        if not default_phases and phase_options:
            default_phases = phase_options[: min(2, len(phase_options))]

        phases = st.multiselect(
            "Фазы локального равновесия",
            phase_options,
            default=default_phases,
            key=f"kin_hom_phases_{database_key}",
            help=(
                "Исследовательский режим разрешает только фазы, для которых в объединённой "
                "базе найдены параметры подвижности."
            ),
        )

        hom_label = st.selectbox(
            "Модель эффективной подвижности",
            list(HOMOGENIZATION_FUNCTIONS),
            index=0,
            key=f"kin_hom_function_{database_key}",
        )
        parameter_col1, parameter_col2 = st.columns(2)
        with parameter_col1:
            eps = st.number_input(
                "Сглаживающий коэффициент ε",
                min_value=0.0,
                max_value=0.2,
                value=0.01,
                step=0.01,
                format="%.3f",
                key=f"kin_hom_eps_{database_key}",
            )
        with parameter_col2:
            labyrinth_factor = st.number_input(
                "Лабиринтный фактор",
                min_value=1.0,
                max_value=2.0,
                value=1.5,
                step=0.1,
                key=f"kin_hom_lab_{database_key}",
                disabled=HOMOGENIZATION_FUNCTIONS[hom_label] != "lab",
            )

        st.info(
            "Рекомендуемый первый вариант — нижняя граница Хашина—Штрикмана. "
            "Разница между верхней и нижней границами показывает чувствительность "
            "к неизвестной геометрии фаз."
        )

        if release_calculation_button(
            "Рассчитать гомогенизацию",
            type="primary",
            key=f"kin_hom_run_{database_key}",
            disabled=(
                not bool(str(common["input_provenance"]).strip())
                or not common["input_confirmation"]
            ),
        ):
            try:
                if len(phases) < 2:
                    raise ValueError("Для многофазной гомогенизации выберите минимум две фазы.")
                with st.spinner("Расчёт локально-равновесной гомогенизации…"):
                    result = run_diffusion(
                        db=db,
                        database_key=database_key,
                        database_path=database_path,
                        database_label=database_label,
                        balance=common["balance"],
                        units=common["units"],
                        left_text=common["left_text"],
                        right_text=common["right_text"],
                        temperature_c=common["temperature_C"],
                        time_h=common["time_h"],
                        length_um=common["length_um"],
                        interface_percent=common["interface_pct"],
                        nodes=common["nodes"],
                        phases=list(phases),
                        model_kind="homogenization",
                        homogenization_function=HOMOGENIZATION_FUNCTIONS[hom_label],
                        eps=float(eps),
                        labyrinth_factor=float(labyrinth_factor),
                        input_provenance=common["input_provenance"],
                        input_confirmation=common["input_confirmation"],
                    )
                st.session_state[f"kin_hom_result_{database_key}"] = result
                record_history(
                    project_root,
                    "Многофазная гомогенизация",
                    current_context,
                    {
                        "database": database_label,
                        "elements": result.elements,
                        "phases": list(phases),
                        "temperature_C": common["temperature_C"],
                        "time_h": common["time_h"],
                        "length_um": common["length_um"],
                        "nodes": common["nodes"],
                        "homogenization": HOMOGENIZATION_FUNCTIONS[hom_label],
                        "eps": float(eps),
                        "kawin": _package_version("kawin"),
                        "database_sha256": result.database_sha256,
                        "input_provenance": result.input_provenance,
                        "input_confirmation": result.input_confirmation,
                    },
                )
            except Exception as error:
                render_error(error, context="многофазная гомогенизация")

        result = st.session_state.get(f"kin_hom_result_{database_key}")
        if isinstance(result, DiffusionResult):
            _result_display(
                result,
                f"kin_hom_{database_key}",
                dataframe_to_excel,
                figure_to_png,
            )

    with coverage_tab:
        st.markdown("### Что доступно в базе подвижностей")
        metric_col1, metric_col2, metric_col3 = st.columns(3)
        with metric_col1:
            st.metric("Kawin", _package_version("kawin"))
        with metric_col2:
            st.metric("Диффундирующих элементов", len(diffusing_species))
        with metric_col3:
            st.metric("Фаз с параметрами подвижности", len(kinetic_phases))

        st.markdown("#### Элементы")
        st.write(", ".join(diffusing_species) if diffusing_species else "Нет данных")
        st.markdown("#### Параметры по фазам")
        if kinetics_table.empty:
            st.warning("Параметры подвижности MQ/MF/DQ/DF не найдены.")
        else:
            st.dataframe(kinetics_table, width="stretch", hide_index=True)

        st.markdown("#### Ограничения исследовательского diffusion mode")
        st.markdown(
            """
- только **одномерная декартова область** и постоянная температура;
- не более **четырёх элементов** одновременно;
- закрытые границы с нулевым потоком;
- нет диффузии по границам зёрен, конвекции, напряжений и пористости;
- однофазная модель не меняет фазу автоматически;
- гомогенизация предполагает локальное равновесие и усреднённую геометрию;
- численный результат требует открытого benchmark или независимого
  программного сопоставления; это не квалифицирует материал.
            """
        )
