"""ThermoGar guarded research adapter for precipitation kinetics.

Расчёт использует KWN-модель пакета Kawin. TDB/DDB дают термодинамику и
подвижности, а межфазная энергия, молярные объёмы и центры зарождения
задаются явно и сохраняются вместе с результатом. Все три release-базы
(Ni, Al, Fe) считаются одним и тем же путём; научная квалификация пары
матрица–выделение не проводилась ни для одной из них.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from pathlib import Path
import hashlib
import json
import re
from typing import Any, Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from pycalphad import Database
from pycalphad.core.utils import filter_phases, unpack_species

from thermogar_diffusion import _atomic_masses, _phase_mobility_coverage
from thermogar_palette import chart_roles, phase_styles, style_legend
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
from thermogar_user_errors import (
    UserRuntimeError,
    UserValueError,
    element_columns_for_display,
    element_symbol,
    element_symbols,
)

try:
    from kawin.precipitation import (
        MatrixParameters,
        PrecipitateModel,
        PrecipitateParameters,
        TemperatureParameters,
    )
    from kawin.thermo import BinaryThermodynamics, MulticomponentThermodynamics
    PRECIPITATION_AVAILABLE = True
    PRECIPITATION_IMPORT_ERROR = ""
except Exception as import_error:  # pragma: no cover
    MatrixParameters = PrecipitateModel = PrecipitateParameters = None
    TemperatureParameters = BinaryThermodynamics = MulticomponentThermodynamics = None
    PRECIPITATION_AVAILABLE = False
    PRECIPITATION_IMPORT_ERROR = str(import_error)


PRESET_NI_DISPLAY_LABEL = "Учебный Ni–9.8Al–8.3Cr / γ′"
PRESET_NI = {
    "label": "Учебный Ni–9,8Al–8,3Cr / γ′",
    "composition": "AL=9.8, CR=8.3",
    "matrix": "FCC_A1",
    "precipitate": "GAMMA_PRIME",
    "temperature_c": 800.0,
    "duration_h": 100.0,
    "gamma": 0.023,
    "matrix_vm": 6.5662724928,
    "precip_vm": 6.5662724928,
    "bulk_n0": 1e30,
}

DEFAULTS = {
    "ni": ("FCC_A1", "GAMMA_PRIME", 800.0, 100.0, 0.023, 6.57, 6.57),
    "al": ("FCC_A1", "THETA_AL2CU", 200.0, 24.0, 0.15, 10.0, 10.0),
    "fe": ("BCC_A2", "M23C6", 700.0, 0.05, 0.3, 7.09, 7.09),
}

# Fe-профиль исключает C15_LAVES из фаз, предлагаемых пользователю.
EXCLUDED_PHASES = {"fe": ("C15_LAVES",)}

# Строка происхождения физических входов по умолчанию. Поле остаётся
# редактируемым и попадает в Excel, историю расчётов и JSON происхождения,
# но пустое поле больше не выключает кнопку расчёта.
DEFAULT_INPUT_PROVENANCE = "Объявленный сценарий, не данные материала"

NUCLEATION_TYPES = {
    "Объёмные центры": "BULK",
    "Дислокации": "DISLOCATIONS",
    "Границы зёрен": "GRAIN BOUNDARIES",
    "Рёбра зёрен": "GRAIN EDGES",
    "Углы зёрен": "GRAIN CORNERS",
}

# Максимальное допустимое отношение gamma_gb / (2*gamma_interface)
# для геометрических моделей гетерогенного зарождения Kawin.
HETEROGENEOUS_RATIO_LIMITS = {
    "GRAIN BOUNDARIES": 1.0,
    "GRAIN EDGES": float(np.sqrt(3.0) / 2.0),
    "GRAIN CORNERS": float(np.sqrt(2.0 / 3.0)),
}

KWN_ADAPTER_IMPLEMENTATION_REVISION = "legacy-15.2-r1"
# Расчёт KWN для Fe выполняется штатно. Научная квалификация пары
# матрица–выделение и физических параметров не проводилась; провенанс
# сообщает это тем же нейтральным языком, что и остальная метаинформация,
# и не является программным ограничением.
FE_KWN_PUBLICATION_STATUS = "NOT_ASSESSED"

# BL-21. Наибольшее число добавок, на котором расчёт выделений измерен
# (волны 14-А и 14-Б: сборка, время шага, баланс масс на 2…10 добавках).
# Это предел измеренного, а не физический: выше 10 добавок не проверялось.
KWN_MAX_SOLUTES = 10
# До этого числа добавок расчёт шёл и до 14-Б; сверх него — предупреждение о
# времени: по замеру 14-А каждая добавка удлиняет шаг решателя примерно на 15 %.
KWN_SOLUTES_WITHOUT_TIME_WARNING = 4
KWN_LONG_COMPOSITION_WARNING = (
    "В составе {count} добавок. Расчёт идёт в этой же вкладке и не отменяется; "
    "каждая добавка удлиняет его примерно на 15 %."
)


@dataclass
class PrecipitationResult:
    database_key: str
    phase: str
    settings: pd.DataFrame
    summary: pd.DataFrame
    kinetics: pd.DataFrame
    matrix_composition: pd.DataFrame
    interface_composition: pd.DataFrame
    psd: pd.DataFrame
    quality: pd.DataFrame
    figures: dict[str, plt.Figure]
    npz: bytes
    provenance: bytes
    # Сообщения о правках базы, касающихся элементов расчёта (BL-20), и
    # предупреждение о времени на длинном составе (BL-21).
    warnings: list[str] = field(default_factory=list)
    # BL-35. Текст отказа, если расчёт остановлен до конца выдержки из-за
    # недопустимого состава матрицы; пустая строка — расчёт дошёл до конца.
    stop_note: str = ""


# BL-35. Одна фраза о причине отказа — общая для остановки по составу и для
# перехваченного деления на ноль в pycalphad.
KWN_COMPOSITION_STOP_CAUSE = (
    "Причина: при движущей силе по базе зарождение практически безбарьерное, "
    "и выделение вычерпывает добавки из матрицы быстрее, чем модель это "
    "выдерживает."
)


def _matrix_composition_violation(
    composition: Any, solutes: list[str], balance: str, initial: Any
) -> tuple[str, float] | None:
    """Первый элемент матрицы, нарушивший баланс масс, и его мольная доля.

    Нарушение — доля любого элемента, включая основу, вне [0; 1] или
    нечисловая, либо добавка, которой в исходном составе было больше нуля,
    дошла до нуля. Порога нет: это баланс масс, а не настройка.
    """

    x = np.asarray(composition, float).ravel()
    values = list(zip(solutes, x.tolist())) + [(balance, 1.0 - float(np.sum(x)))]
    for element, value in values:
        if not np.isfinite(value) or value < 0.0 or value > 1.0:
            return element, float(value)
    for element, value, start in zip(solutes, x.tolist(), np.asarray(initial, float).ravel()):
        if start > 0.0 and value <= 0.0:
            return element, float(value)
    return None


class _MatrixCompositionStop:
    """Условие остановки kawin по составу матрицы (BL-35).

    ``KWNBase.postProcess`` после каждого принятого шага дописывает шаг в
    ``model.data`` и вызывает у условия ``testCondition(model)`` и
    ``isSatisfied()``; ``reset()`` вызывает ``KWNBase.reset``. Условие только
    читает последний записанный состав и расчёт не меняет.
    """

    def __init__(self, solutes: list[str], balance: str, initial: Any) -> None:
        self._solutes = list(solutes)
        self._balance = balance
        self._initial = np.asarray(initial, float)
        self.reset()

    def reset(self) -> None:
        self._isSatisfied = False
        self._satisfiedTime = -1
        self.element: str | None = None
        self.value: float | None = None

    def testCondition(self, model: Any) -> None:
        if self._isSatisfied:
            return
        n = int(model.data.n)
        found = _matrix_composition_violation(
            model.data.composition[n], self._solutes, self._balance, self._initial
        )
        if found is not None:
            self._isSatisfied = True
            self._satisfiedTime = float(model.data.time[n])
            self.element, self.value = found

    def isSatisfied(self) -> bool:
        return self._isSatisfied

    def satisfiedTime(self) -> float:
        return self._satisfiedTime


def _raised_in_pycalphad(error: BaseException) -> bool:
    trace = error.__traceback__
    while trace is not None:
        if "pycalphad" in trace.tb_frame.f_code.co_filename.replace("\\", "/"):
            return True
        trace = trace.tb_next
    return False


def _time_text(time_s: float) -> str:
    return f"{time_s:.4g} с модельного времени ({time_s/3600:.4g} ч)"


def _composition_stop_note(time_s: float, element: str, value: float) -> str:
    return (
        f"Расчёт остановлен на {_time_text(time_s)}: доля {element_symbol(element)} в матрице "
        f"стала {100*value:.4g} ат.%, баланс масс нарушен. Показана часть "
        f"расчёта до остановки. {KWN_COMPOSITION_STOP_CAUSE}"
    )


def _solver_failure_note(time_s: float, composition: Any, solutes: list[str], balance: str) -> str:
    x = np.asarray(composition, float).ravel()
    parts = [
        f"{element_symbol(element)} {100*value:.4g}"
        for element, value in zip(solutes, x.tolist())
    ]
    parts.append(f"{element_symbol(balance)} {100*(1.0 - float(np.sum(x))):.4g}")
    return (
        f"Расчёт прерван после {_time_text(time_s)}: на следующем шаге не "
        "удалось посчитать локальное равновесие для состава матрицы из "
        "баланса масс. Последний посчитанный состав матрицы, ат.%: "
        f"{', '.join(parts)}. Показана часть расчёта до обрыва. "
        f"{KWN_COMPOSITION_STOP_CAUSE}"
    )


def _pkg(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "не установлен"


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_composition(text: str) -> dict[str, float]:
    text = str(text).strip()
    if not text:
        return {}
    pattern = re.compile(
        r"([A-Za-z]{1,2})\s*=\s*([+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+))"
    )
    matches = list(pattern.finditer(text))
    if not matches:
        raise UserValueError("Не удалось прочитать состав. Пример: Al=9.8, Cr=8.3")
    remainder = re.sub(r"[\s,;]+", "", pattern.sub("", text))
    if remainder:
        raise UserValueError(f"Непонятный фрагмент в составе: {remainder!r}")
    result: dict[str, float] = {}
    for match in matches:
        element = match.group(1).upper()
        value = float(match.group(2).replace(",", "."))
        if element in result:
            raise UserValueError(f"Элемент {element_symbol(element)} указан повторно.")
        if value <= 0:
            raise UserValueError(
                f"Содержание {element_symbol(element)} должно быть больше нуля."
            )
        result[element] = value
    return result


def _composition_vectors(
    db: Any,
    balance: str,
    text: str,
    units: str,
) -> tuple[list[str], np.ndarray, np.ndarray]:
    balance = str(balance).upper()
    entered = _parse_composition(text)
    if balance in entered:
        raise UserValueError(
            f"Не указывайте элемент-основу {element_symbol(balance)} в добавках."
        )
    available = {str(e).upper() for e in db.elements if str(e).upper() != "VA"}
    unknown = sorted(set(entered) - available)
    if unknown:
        raise UserValueError("В базе отсутствуют: " + ", ".join(unknown))
    total = float(sum(entered.values()))
    if total >= 100:
        raise UserValueError("Сумма добавок должна быть меньше 100 %.")
    solutes = sorted(entered)
    if not solutes:
        raise UserValueError("Укажите хотя бы одну добавку.")
    if len(solutes) > KWN_MAX_SOLUTES:
        raise UserValueError(
            f"Расчёт выделений KWN принимает не более {KWN_MAX_SOLUTES} добавок "
            f"одновременно, в составе {len(solutes)}. Это предел измеренного, а не "
            f"физический: больше {KWN_MAX_SOLUTES} добавок расчёт не проверялся."
        )
    elements = [balance] + solutes
    percentages = np.array([100 - total] + [entered[e] for e in solutes], float)
    masses = _atomic_masses(db, elements)
    if units == "at":
        x_at = percentages / 100
        weighted = x_at * masses
        x_wt = weighted / weighted.sum()
    elif units == "wt":
        x_wt = percentages / 100
        moles = x_wt / masses
        x_at = moles / moles.sum()
    else:
        raise UserValueError("Неизвестные единицы состава.")
    return elements, x_at, x_wt


def _selectable_phases(database_key: str, phases: list[str]) -> list[str]:
    """Убрать из списка фазы, недоступные пользователю для данной базы."""
    excluded = EXCLUDED_PHASES.get(str(database_key).strip().casefold(), ())
    return [phase for phase in phases if phase not in excluded]


def _compatible_phases(db: Any, elements: list[str]) -> list[str]:
    components = list(elements) + (["VA"] if "VA" in db.elements else [])
    return list(filter_phases(db, unpack_species(db, components)))


def _build_precipitation_thermodynamics(
    database: Database,
    elements: list[str],
    phases: list[str],
) -> tuple[Any, str]:
    """Создать класс термодинамики Kawin, совместимый с KWN-моделью.

    Kawin разделяет бинарные и многокомпонентные задачи. Базовый
    GeneralThermodynamics используется диффузионным модулем, но не содержит
    методов роста и межфазных составов, которые вызывает PrecipitateModel.
    """
    if len(elements) < 2:
        raise UserValueError("Для кинетики выделений нужны как минимум два элемента.")
    if len(elements) == 2:
        therm = BinaryThermodynamics(database, elements, phases)
        required = ("getInterfacialComposition", "getInterdiffusivity")
        class_label = "BinaryThermodynamics"
    else:
        therm = MulticomponentThermodynamics(database, elements, phases)
        required = ("getGrowthAndInterfacialComposition",)
        class_label = "MulticomponentThermodynamics"
    missing = [name for name in required if not hasattr(therm, name)]
    if missing:
        raise UserRuntimeError(
            f"Класс {class_label} не содержит обязательные методы Kawin: "
            + ", ".join(missing)
        )
    return therm, class_label


def _phase_order_disorder_role(db: Any, phase: str) -> dict[str, str]:
    """Вернуть роль фазы в order/disorder-модели без автоматического remap.

    Kawin принимает первой фазой матрицу и для order/disorder-моделей ожидает
    её разупорядоченную часть. ThermoGar поэтому выявляет ordered-имя явно и
    запрещает использовать его как матрицу, но не подменяет выбор пользователя.
    """
    phase = str(phase)
    if phase not in db.phases:
        raise UserValueError(f"Фаза {phase} отсутствует в базе.")
    raw_hints = getattr(db.phases[phase], "model_hints", {}) or {}
    ordered = str(raw_hints.get("ordered_phase", "") or "")
    disordered = str(raw_hints.get("disordered_phase", "") or "")
    role = "independent"
    if ordered and disordered and ordered != disordered:
        if phase == ordered:
            role = "ordered"
        elif phase == disordered:
            role = "disordered"
        else:
            role = "related"
    return {
        "phase": phase,
        "role": role,
        "ordered_phase": ordered,
        "disordered_phase": disordered,
    }


def _order_disorder_partner(db: Any, phase: str) -> str:
    """Вернуть вторую половину пары order/disorder или пустую строку."""
    try:
        role = _phase_order_disorder_role(db, phase)
    except ValueError:
        return ""
    if role["role"] == "ordered":
        return role["disordered_phase"]
    if role["role"] == "disordered":
        return role["ordered_phase"]
    return ""


def _compatible_matrix_phases(db: Any, elements: list[str]) -> set[str]:
    """Список фаз-кандидатов в матрицу с восстановленной disordered-половиной.

    ``filter_phases`` оставляет из пары order/disorder только упорядоченную
    фазу (``GP_MAT`` для Al, ``BCC_B2`` для Fe), а Kawin принимает матрицей
    только разупорядоченную. Возвращаем разупорядоченного партнёра в список,
    если он есть в базе; сама логика Kawin при этом не меняется.
    """
    compatible = set(_compatible_phases(db, elements))
    for phase in sorted(compatible):
        role = _phase_order_disorder_role(db, phase)
        if role["role"] != "ordered":
            continue
        disordered = role["disordered_phase"]
        if disordered and disordered in db.phases:
            compatible.add(disordered)
    return compatible


def _validate_matrix_phase_role(db: Any, matrix_phase: str) -> dict[str, str]:
    info = _phase_order_disorder_role(db, matrix_phase)
    if info["role"] == "ordered":
        disordered = info["disordered_phase"] or "разупорядоченную фазу"
        raise UserValueError(
            f"Фаза {matrix_phase} — упорядоченная половина модели "
            f"порядок/беспорядок и не может быть матрицей. Выберите {disordered}."
        )
    return info


def _matrix_candidates(db: Any, elements: list[str]) -> list[str]:
    coverage = _phase_mobility_coverage(db)
    required = set(elements)
    compatible = _compatible_matrix_phases(db, elements)
    candidates: list[str] = []
    for phase, species in coverage.items():
        if phase not in compatible or not required.issubset(species):
            continue
        if _phase_order_disorder_role(db, phase)["role"] == "ordered":
            continue
        candidates.append(phase)
    return sorted(candidates)


def _temperature_profile(text: str) -> tuple[np.ndarray, np.ndarray]:
    rows: list[tuple[float, float]] = []
    for number, raw in enumerate(str(text).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip().replace(",", ".") for p in re.split(r"[;\t ]+", line) if p.strip()]
        if len(parts) != 2:
            raise UserValueError(f"Строка {number}: нужны время, ч и температура, °C.")
        rows.append((float(parts[0]), float(parts[1])))
    if len(rows) < 2:
        raise UserValueError("Нужно не менее двух точек температурного цикла.")
    rows.sort(key=lambda item: item[0])
    times = np.array([r[0] for r in rows], float)
    temperatures = np.array([r[1] for r in rows], float)
    if not np.isclose(times[0], 0):
        raise UserValueError("Первая точка должна иметь время 0 ч.")
    if np.any(np.diff(times) <= 0):
        raise UserValueError("Время должно строго возрастать.")
    return times, temperatures


def _theme() -> str:
    try:
        return str(st.context.theme.type)
    except Exception:
        return "light"


def _chrome(axis: Any, roles: dict[str, str]) -> None:
    axis.set_facecolor(roles["background"])
    axis.grid(True, color=roles["grid"], alpha=0.35)
    axis.tick_params(colors=roles["axis"])
    axis.xaxis.label.set_color(roles["axis"])
    axis.yaxis.label.set_color(roles["axis"])
    axis.title.set_color(roles["text"])
    for spine in axis.spines.values():
        spine.set_color(roles["grid"])


def _time_axis(axis: Any) -> None:
    axis.set_xscale("symlog", linthresh=1e-4)
    axis.set_xlabel("Время, ч")


def _single_figure(x: np.ndarray, y: np.ndarray, ylabel: str, title: str, key: str, log_y: bool = False) -> plt.Figure:
    roles = chart_roles(_theme())
    style = phase_styles([key], _theme())[key]
    figure, axis = plt.subplots(figsize=(10, 5.4))
    figure.patch.set_facecolor(roles["background"])
    axis.plot(x, y, color=style["color"], linestyle=style["linestyle"], marker=style["marker"], markevery=max(1, len(x)//14), markersize=4)
    _time_axis(axis)
    if log_y and np.any(np.asarray(y) > 0):
        axis.set_yscale("symlog", linthresh=max(float(np.nanmax(y))*1e-12, 1e-30))
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    _chrome(axis, roles)
    figure.tight_layout()
    return figure


def _radius_density_figure(time_h: np.ndarray, radius_nm: np.ndarray, density: np.ndarray, phase: str) -> plt.Figure:
    roles = chart_roles(_theme())
    styles = phase_styles(["Радиус", "Плотность"], _theme())
    figure, left = plt.subplots(figsize=(10, 5.6))
    right = left.twinx()
    figure.patch.set_facecolor(roles["background"])
    left.plot(time_h, radius_nm, color=styles["Радиус"]["color"], linewidth=2)
    right.plot(time_h, density, color=styles["Плотность"]["color"], linestyle="--", linewidth=1.8)
    _time_axis(left)
    right.set_xscale("symlog", linthresh=1e-4)
    if np.any(density > 0):
        right.set_yscale("symlog", linthresh=max(float(np.nanmax(density))*1e-12, 1e-30))
    left.set_ylabel("Средний радиус, нм")
    right.set_ylabel("Плотность частиц, 1/м³")
    left.set_title(f"Размер и плотность выделений {phase}")
    _chrome(left, roles)
    right.tick_params(colors=roles["axis"])
    right.yaxis.label.set_color(roles["axis"])
    figure.tight_layout()
    return figure


def _composition_figure(table: pd.DataFrame, solutes: list[str]) -> plt.Figure:
    roles = chart_roles(_theme())
    styles = phase_styles(solutes, _theme())
    figure, axis = plt.subplots(figsize=(10, 5.4))
    figure.patch.set_facecolor(roles["background"])
    x = table["Время, ч"].to_numpy(float)
    for element in solutes:
        style = styles[element]
        axis.plot(x, table[f"{element}, матрица, ат.%"], label=element, color=style["color"], linestyle=style["linestyle"])
    _time_axis(axis)
    axis.set_ylabel("Содержание в матрице, ат.%")
    axis.set_title("Изменение состава матрицы")
    _chrome(axis, roles)
    style_legend(axis.legend(frameon=False), roles)
    figure.tight_layout()
    return figure


def _psd_figure(table: pd.DataFrame, phase: str) -> plt.Figure:
    roles = chart_roles(_theme())
    style = phase_styles([phase], _theme())[phase]
    figure, axis = plt.subplots(figsize=(10, 5.4))
    figure.patch.set_facecolor(roles["background"])
    x = table["Радиус класса, нм"].to_numpy(float)
    y = table["Число частиц в классе, 1/м³"].to_numpy(float)
    axis.step(x, y, where="mid", color=style["color"])
    axis.fill_between(x, y, step="mid", color=style["color"], alpha=0.18)
    if np.any(y > 0):
        axis.set_yscale("symlog", linthresh=max(float(np.nanmax(y))*1e-12, 1e-30))
    axis.set_xlabel("Радиус, нм")
    axis.set_ylabel("Число частиц в классе, 1/м³")
    axis.set_title(f"Итоговое распределение {phase}")
    _chrome(axis, roles)
    figure.tight_layout()
    return figure


# Доля, начиная с которой считаем, что kawin упёрся в свой потолок 1.
VOLUME_FRACTION_CEILING = 1.0 - 1e-6


def _size_class_width_nm(cmin_nm: float, cmax_nm: float, bins: int) -> float:
    """Ширина класса начальной сетки: kawin строит её линейно по радиусу."""

    return (float(cmax_nm) - float(cmin_nm)) / int(bins)


def _quality(
    data: Any,
    pindex: int,
    solute_count: int,
    cmin_nm: float | None = None,
    cmax_nm: float | None = None,
    bins: int | None = None,
    stop_note: str = "",
) -> pd.DataFrame:
    checks: list[dict[str, str]] = []
    def add(name: str, ok: bool, note: str) -> None:
        checks.append({"Проверка": name, "Статус": "пройдена" if ok else "ошибка", "Примечание": note})
    time = np.asarray(data.time, float)
    temperature = np.asarray(data.temperature, float)
    fraction = np.asarray(data.volFrac[:, pindex], float)
    radius = np.asarray(data.Ravg[:, pindex], float)
    density = np.asarray(data.precipitateDensity[:, pindex], float)
    composition = np.asarray(data.composition, float)
    add("Время возрастает", bool(np.all(np.diff(time) >= 0)), "Нет обратного хода времени.")
    add("Температура конечна", bool(np.all(np.isfinite(temperature))), "Все точки температуры числовые.")
    add("Объёмная доля 0–1", bool(np.all((fraction >= -1e-10) & (fraction <= 1+1e-8))), "Физический диапазон доли.")
    add("Радиус неотрицателен", bool(np.all(radius >= -1e-20)), "Средний радиус неотрицателен.")
    add("Плотность неотрицательна", bool(np.all(density >= -1e-6)), "Количество частиц неотрицательно.")
    if stop_note:
        add("Состав матрицы допустим", False, stop_note)
    else:
        add("Состав матрицы допустим", bool(composition.shape[1] == solute_count and np.all(np.isfinite(composition)) and np.all((composition >= -1e-8) & (composition <= 1+1e-8))), "Проверка независимых компонентов.")
    # BL-22. kawin обрезает долю единицей и после этого перестаёт пересчитывать
    # состав матрицы (KWNEuler: volFrac = min(..., 1), при сумме долей 1 состав
    # не обновляется). Доля 100 % — след зародышей, записанных в класс шире их
    # самих, а не результат расчёта.
    add(
        "Объёмная доля не упёрлась в 100 %",
        bool(not fraction.size or np.nanmax(fraction) < VOLUME_FRACTION_CEILING),
        "Доля 100 % означает негодную сетку размеров, а не полное превращение.",
    )
    if cmin_nm is not None and cmax_nm is not None and bins is not None:
        width_nm = _size_class_width_nm(cmin_nm, cmax_nm, bins)
        nucleation = np.asarray(data.nucRate[:, pindex], float)
        rcrit_nm = 1e9*np.asarray(data.Rcrit[:, pindex], float)
        rnuc_nm = 1e9*np.asarray(data.Rnuc[:, pindex], float)
        nucleating = (nucleation > 0) & (rnuc_nm > 0)
        coarse = nucleating & (rcrit_nm <= width_nm)
        below = nucleating & (rnuc_nm < float(cmin_nm))
        coarse_note = f"Ширина класса начальной сетки {width_nm:.4g} нм"
        if np.any(coarse):
            coarse_note += (
                f", критический радиус на шагах зарождения — от "
                f"{np.min(rcrit_nm[coarse]):.4g} нм: зародыши шире не разрешены."
            )
        else:
            coarse_note += "."
        add("Ширина класса меньше критического радиуса", not bool(np.any(coarse)), coarse_note)
        below_note = f"Минимальный радиус сетки {float(cmin_nm):.4g} нм"
        if np.any(below):
            below_note += (
                f", радиус зародыша — от {np.min(rnuc_nm[below]):.4g} нм: kawin "
                "кладёт такие зародыши в последний, самый крупный класс сетки."
            )
        else:
            below_note += "."
        add("Зародыш не меньше минимального радиуса сетки", not bool(np.any(below)), below_note)
    return pd.DataFrame(checks)


def _nucleus_estimates(
    model: Any,
    precipitate_phase: str,
    temperatures_k: list[float],
) -> list[tuple[float, float, float, float]]:
    """Критический радиус и радиус зародыша на первом шаге, нм, по температурам.

    Кортеж: температура, K; критический радиус kawin, нм (после зажима снизу
    ``Rmin``); радиус зародыша, нм; критический радиус до зажима, нм (BL-32).

    Считается теми же функциями kawin, что и в самом расчёте
    (``KWNBase._calcNucleationRate``), по начальному составу матрицы.
    Температуры без положительной движущей силы пропускаются: зарождения там
    нет, и сетке нечего разрешать.

    Функция вызывает ``model.setup()`` и движущую силу на переданной модели и
    меняет её состояние. ``removeCache=True`` от этого не защищает: волна 13-Р
    показала, что такой вызов на объектах самого расчёта сдвигает его числа
    (до 6·10⁻⁸ относительных на Ni–9,8Al–8,3Cr при 800 °C). Поэтому
    ``run_precipitation`` передаёт сюда отдельную модель со своим объектом
    термодинамики, собранную теми же параметрами, а расчёт идёт на другой;
    кинетика с оценкой и без неё совпадает побайтово
    (``tools/test_precipitation_grid.py``). Модель, переданную сюда, для
    расчёта не использовать.
    """

    import kawin.precipitation.NucleationRate as nucleation_functions

    model.setup()
    p = model.phaseIndex(precipitate_phase)
    parameters = model.precipitates[p]
    composition = np.squeeze(model.data.composition[0])
    estimates: list[tuple[float, float, float, float]] = []
    for temperature_k in sorted({float(value) for value in temperatures_k}):
        _chemical, volume_dg, _beta = nucleation_functions.volumetricDrivingForce(
            model.therm, composition, temperature_k, parameters,
            removeCache=True,
        )
        volume_dg = float(np.squeeze(volume_dg))
        if not np.isfinite(volume_dg) or volume_dg <= 0:
            continue
        rcrit, _gcrit = nucleation_functions.nucleationBarrier(volume_dg, parameters)
        rnuc = nucleation_functions.nucleationRadius(temperature_k, rcrit, parameters)
        # Радиус до зажима — теми же выражениями, что ``nucleationBarrier``
        # берёт в своих двух ветках до ``max(..., Rmin)``.
        if parameters.nucleation.isGrainBoundaryNucleation:
            free_rcrit = parameters.nucleation.Rcrit(volume_dg)
        else:
            free_rcrit = (
                2*parameters.shapeFactor.description.thermoFactor(1)
                * parameters.gamma / volume_dg
            )
        estimates.append((
            temperature_k, 1e9*float(rcrit), 1e9*float(rnuc),
            1e9*float(np.squeeze(free_rcrit)),
        ))
    return estimates


# BL-32. Отношение u = Rmin / r*, начиная с которого расчёт не пускается.
#
# Ветка kawin для границ, рёбер и углов зёрен считает барьер полным выражением
# ΔG(R) = R²·(A − c·ΔGv·R), A = b·γ − a·γ_gb (``NucleationBarrierParameters.Gcrit``),
# подставляя в него зажатый радиус R = Rmin. Максимум ΔG(R) — при
# r* = 2A/(3c·ΔGv), G* = ΔG(r*). В долях максимума, u = R/r*:
#     ΔG(R)/G* = 3u² − 2u³ = u²·(3 − 2u),
# ноль при 3 − 2u = 0, отсюда порог ниже. При u ≥ 3/2 барьер kawin
# неположителен, а ``nucleationRate`` берёт exp(−Gcrit/kT) при любом
# Gcrit ≠ 0, так что отрицательный барьер входит в скорость как exp(+|G|/kT),
# и скорость зарождения расходится. Здесь порог выведен.
#
# Ветка kawin для объёма и дислокаций считает барьер как (4π/3)·γ·Rcrit², и при
# зажиме он равен u²·G* — положителен при любом u (14-В). Здесь порог
# ЭМПИРИЧЕСКИЙ: на пяти случаях 14-А (u = 2,01…2,43) расчёт не сходился, на
# умолчании Ni-раздела (u = 1,12) сошёлся (14-Б, 14-В); механизм зависания не
# установлен (BL-33), граница лежит где-то между 1,12 и 2,01 и взята той же,
# что у ветки границ зёрен, по аналогии.
CRITICAL_RADIUS_REFUSAL_RATIO = 3.0 / 2.0


def _check_critical_radius_floor(
    estimates: list[tuple[float, float, float, float]],
    radius_floor_nm: float | None,
    grain_boundary_nucleation: bool,
) -> list[str]:
    """BL-32: критический радиус до зажима против нижнего предела kawin ``Rmin``.

    kawin берёт критический радиус как ``max(r*, Rmin)``. По наибольшему по
    температурам профиля u = Rmin / r*:

    * u ≥ ``CRITICAL_RADIUS_REFUSAL_RATIO`` — отказ ``ValueError``; обоснование
      и текст разные для границ зёрен и для объёма/дислокаций (см. комментарий
      к порогу);
    * 1 < u < порога — возвращается предупреждение для ``warnings``;
    * u ≤ 1 — зажима нет, пустой список.

    ``grain_boundary_nucleation`` — ``nucleation.isGrainBoundaryNucleation``
    параметров выделения kawin.
    """

    if not estimates or radius_floor_nm is None:
        return []
    floor_nm = float(radius_floor_nm)

    def ratio(item: tuple[float, ...]) -> float:
        free_nm = float(item[3])
        return floor_nm/free_nm if free_nm > 0 else float("inf")

    worst = max(estimates, key=ratio)
    u = ratio(worst)
    temperature_c = worst[0] - 273.15
    free_nm = float(worst[3])
    radius_text = (
        f"Критический радиус зародыша {free_nm:.3g} нм (оценка при {temperature_c:.1f} °C "
        f"по начальному составу) меньше предела модели {floor_nm:.3g} нм"
        if free_nm > 0 else
        f"Критический радиус зародыша (оценка при {temperature_c:.1f} °C по начальному "
        f"составу) не положителен и меньше предела модели {floor_nm:.3g} нм"
    )
    if u >= CRITICAL_RADIUS_REFUSAL_RATIO:
        if grain_boundary_nucleation:
            raise UserValueError(
                f"{radius_text} более чем в полтора раза. При таком радиусе барьер "
                "зарождения на границах зёрен обращается в ноль, и скорость зарождения "
                "расходится. Поднимите межфазную энергию либо температуру."
            )
        raise UserValueError(
            f"{radius_text} более чем в полтора раза. На таких входах расчёт в наших "
            "опытах не сходился. Поднимите межфазную энергию либо температуру."
        )
    if u > 1.0:
        return [
            f"{radius_text}, и модель считает зарождение от этого предела. "
            "Поэтому скорость зарождения на начальной стадии не классическая для "
            "этой движущей силы, и начало выделения на графиках может быть искажено."
        ]
    return []


def _check_size_grid(
    estimates: list[tuple[float, ...]],
    cmin_nm: float,
    cmax_nm: float,
    bins: int,
) -> None:
    """BL-22: не пускать в расчёт сетку, на которой зародыш не разрешён.

    kawin кладёт зародыш радиусом ``Rnuc`` в класс
    ``argmax(PSDbounds > Rnuc) - 1`` (``PopulationBalance.getdXdtEuler``).
    Если класс не уже критического радиуса, зародыш записывается частицей с
    радиусом центра класса, и объём выделений завышается на порядки — вплоть
    до ложной доли 100 %. Если зародыш меньше ``cMin``, индекс становится -1,
    и зародыш уходит в последний, самый крупный класс.

    На первом шаге движущая сила наибольшая, а критический радиус
    наименьший, поэтому оценка по начальному составу — самая строгая.
    """

    if not estimates:
        return
    lowest_nucleus = min(estimates, key=lambda item: item[2])
    temperature_k, rnuc_nm = lowest_nucleus[0], lowest_nucleus[2]
    if rnuc_nm < float(cmin_nm):
        raise UserValueError(
            f"Сетка размеров не принимает зародыши: радиус зародыша {rnuc_nm:.3g} нм "
            f"(оценка при {temperature_k - 273.15:.1f} °C по начальному составу) "
            f"меньше минимального радиуса сетки {float(cmin_nm):.3g} нм. kawin "
            "записал бы такие зародыши в последний, самый крупный класс сетки, и "
            "результат был бы неверным. Уменьшите «Минимальный радиус» ниже "
            f"{rnuc_nm:.3g} нм."
        )
    width_nm = _size_class_width_nm(cmin_nm, cmax_nm, bins)
    lowest_radius = min(estimates, key=lambda item: item[1])
    temperature_k, rcrit_nm = lowest_radius[0], lowest_radius[1]
    if width_nm >= rcrit_nm:
        needed_bins = int(np.floor((float(cmax_nm) - float(cmin_nm)) / rcrit_nm)) + 1
        raise UserValueError(
            f"Сетка размеров слишком грубая: ширина класса {width_nm:.3g} нм не "
            f"меньше критического радиуса зародыша {rcrit_nm:.3g} нм (оценка при "
            f"{temperature_k - 273.15:.1f} °C по начальному составу). Зародыши "
            "попали бы в класс шире себя, объём выделений был бы завышен, и расчёт "
            "показал бы ложную объёмную долю вплоть до 100 %. Уменьшите «Начальный "
            "максимальный радиус» или возьмите больше классов: при этом диапазоне "
            f"нужно не меньше {needed_bins}."
        )


def _check_nucleus_above_grid(
    estimates: list[tuple[float, ...]],
    cmax_nm: float,
) -> list[str]:
    """BL-26: зародыш крупнее начального ``cMax`` — предупреждение, не отказ.

    kawin кладёт такой зародыш в последний класс (индекс -1) и достраивает
    сетку вверх, пока последний класс заполнен (13-Ф). Итоговые числа почти не
    меняются, искажена стадия зарождения. Берётся наибольший радиус зародыша по
    температурам режима: при нагреве зародыш крупнее, а сетка к этому шагу
    может быть ещё не достроена. Парной проверки после расчёта нет: ``Rnuc``
    растёт по мере обеднения матрицы вместе с сеткой, и такая проверка
    срабатывала бы на годной сетке (решение мастера 13-Ф2).
    """

    if not estimates:
        return []
    largest_nucleus = max(estimates, key=lambda item: item[2])
    temperature_k, rnuc_nm = largest_nucleus[0], largest_nucleus[2]
    if rnuc_nm <= float(cmax_nm):
        return []
    return [
        f"Радиус зародыша {rnuc_nm:.3g} нм (оценка при {temperature_k - 273.15:.1f} °C) "
        f"больше начального максимального радиуса сетки {float(cmax_nm):.3g} нм, поэтому "
        "первые зародыши записываются мельче своего размера, пока модель не расширит "
        "сетку размеров. Итоговые доля, радиус и число частиц от этого почти не меняются, но "
        "начало зарождения на графиках искажено: доля и радиус занижены, число частиц "
        f"завышено. Задайте «Начальный максимальный радиус» больше {rnuc_nm:.3g} нм."
    ]


def _summary(time_h: np.ndarray, fraction: np.ndarray, radius_nm: np.ndarray, density: np.ndarray, nuc_rate: np.ndarray) -> pd.DataFrame:
    imax = int(np.nanargmax(fraction)) if len(fraction) else 0
    inuc = int(np.nanargmax(nuc_rate)) if len(nuc_rate) else 0
    present = np.where(fraction > 1e-8)[0]
    first_time = float(time_h[present[0]]) if len(present) else np.nan
    fmax = float(fraction[imax]) if len(fraction) else 0.0
    ffinal = float(fraction[-1]) if len(fraction) else 0.0
    dissolution = fmax > 1e-8 and ffinal < 0.98*fmax
    coarsening = False
    plateau = np.where(fraction >= 0.9*fmax)[0] if fmax > 0 else np.array([], int)
    if len(plateau) >= 3:
        a, b = plateau[0], plateau[-1]
        coarsening = radius_nm[b] > 1.05*max(radius_nm[a], 1e-30) and density[b] < 0.98*max(density[a], 1e-30)
    # Числа и словесные ответы стоят в одной колонке, поэтому она текстовая:
    # смешанный object-столбец не переводится в Arrow.
    rows = [
        ("Первое обнаружение выделений", first_time, "ч"),
        ("Максимальная объёмная доля", 100*fmax, "%"),
        ("Итоговая объёмная доля", 100*ffinal, "%"),
        ("Итоговый средний радиус", float(radius_nm[-1]) if len(radius_nm) else 0, "нм"),
        ("Итоговая плотность частиц", float(density[-1]) if len(density) else 0, "1/м³"),
        ("Пик скорости зарождения", float(nuc_rate[inuc]) if len(nuc_rate) else 0, "1/(м³·с)"),
        ("Растворение после максимума", "да" if dissolution else "нет", "—"),
        ("Укрупнение на плато", "да" if coarsening else "не выявлено", "—"),
    ]
    return pd.DataFrame(
        [
            (
                name,
                ("не обнаружены" if isinstance(value, float) and not np.isfinite(value)
                 else f"{value:.6g}" if isinstance(value, float) else str(value)),
                unit,
            )
            for name, value, unit in rows
        ],
        columns=["Показатель", "Значение", "Единица"],
    )


def _npz(model: Any) -> bytes:
    buffer = BytesIO()
    np.savez_compressed(buffer, **model.toDict())
    return buffer.getvalue()


def _repair_loaded_database(database: Any) -> None:
    """Правки, которые нельзя внести в байты TDB.

    Байты релизной базы привязаны к SHA-256 и неприкосновенны, поэтому
    умолчания подвижности снимаются над уже разобранным объектом; подробности —
    в ``thermogar_database_repair``. Вызов идемпотентен и не должен мешать
    расчёту, поэтому отказ модуля правок проглатывается.
    """

    try:
        import thermogar_database_repair as repair

        repair.repair_database(database)
    except Exception:
        pass


def _database_override_warnings(database: Any, elements: list[str]) -> list[str]:
    """Сообщения о правках базы, которые касаются элементов расчёта."""

    try:
        import thermogar_database_repair as repair

        return repair.override_warnings(database, elements)
    except Exception:
        return []


def _bind_release_database(
    database_key: str,
    database_path: str | Path,
    database_label: str,
) -> tuple[str, Path, str, str, Database]:
    """Load exactly one canonical hash-pinned SWR database into memory."""

    if not isinstance(database_label, str):
        raise UserValueError("Название базы KWN должно быть строкой.")
    supplied_label = database_label.strip()
    canonical_label = RELEASE_DATABASE_LABELS[database_key]
    if supplied_label and supplied_label != canonical_label:
        raise UserRuntimeError(
            "Расчёт выделений не запущен: файл базы не совпадает с поставкой "
            "ThermoGar."
        )
    candidate_path = Path(database_path).resolve()
    expected_path = (
        Path(__file__).resolve().parent.parent
        / RELEASE_DATABASE_RELATIVE_PATHS[database_key]
    ).resolve()
    if (
        candidate_path != expected_path
        or candidate_path.name != RELEASE_DATABASE_FILENAMES[database_key]
        or not candidate_path.is_file()
    ):
        raise UserRuntimeError(
            "Расчёт выделений не запущен: файл базы не совпадает с поставкой "
            "ThermoGar."
        )
    expected_sha256 = RELEASE_DATABASE_SHA256[database_key]
    database_sha256 = _sha256(candidate_path)
    if database_sha256 != expected_sha256:
        raise UserRuntimeError(
            "Расчёт выделений не запущен: файл базы не совпадает с поставкой "
            "ThermoGar."
        )
    database = Database(str(candidate_path))
    _repair_loaded_database(database)
    if _sha256(candidate_path) != expected_sha256:
        raise UserRuntimeError("KWN отклонён: файл базы изменился во время загрузки.")
    return database_key, candidate_path, database_sha256, canonical_label, database


def run_precipitation(
    *, db: Any, database_path: str | Path, database_label: str, database_key: str,
    balance: str, composition_text: str, units: str, matrix_phase: str,
    precipitate_phase: str, schedule_mode: str, temperature_c: float,
    duration_h: float, profile_text: str, gamma: float, matrix_vm: float,
    precip_vm: float, nucleation_type: str, bulk_n0: float, grain_size_um: float,
    dislocation_density: float, gb_energy: float, cmin_nm: float, cmax_nm: float,
    bins: int, input_provenance: str, input_confirmation: bool,
) -> PrecipitationResult:
    if not isinstance(database_key, str):
        raise UserValueError("База не подключена. Выберите базу в боковой панели.")
    database_key = database_key.strip().casefold()
    if database_key not in RELEASE_DATABASE_KEYS:
        raise UserValueError("База не подключена. Выберите базу в боковой панели.")
    if not isinstance(input_provenance, str) or not input_provenance.strip():
        raise UserValueError(
            "Укажите источник физических входов."
        )
    if input_confirmation is not True:
        raise UserValueError(
            "Для KWN требуется явное подтверждение исследовательского сценария."
        )
    if not isinstance(schedule_mode, str) or schedule_mode not in {
        "isothermal",
        "profile",
    }:
        raise UserValueError(
            "Введённые значения не проходят проверку."
        )
    allowed_nucleation_types = set(NUCLEATION_TYPES.values())
    if (
        not isinstance(nucleation_type, str)
        or nucleation_type not in allowed_nucleation_types
    ):
        raise UserValueError("Неизвестный тип центров зарождения KWN.")
    # Bind composition and mobility inspection to the verified bytes rather
    # than trusting an independently supplied Database object.
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
    if not PRECIPITATION_AVAILABLE:
        raise UserRuntimeError(
            "Модуль кинетики выделений недоступен."
        ) from ImportError(PRECIPITATION_IMPORT_ERROR)
    elements, x_at, _x_wt = _composition_vectors(db, balance, composition_text, units)
    solutes = elements[1:]
    database_warnings = _database_override_warnings(db, elements)
    if matrix_phase == precipitate_phase:
        raise UserValueError("Матрица и выделение должны различаться.")
    if matrix_phase not in db.phases or precipitate_phase not in db.phases:
        raise UserValueError("Выбранная фаза отсутствует в базе.")
    matrix_role = _validate_matrix_phase_role(db, matrix_phase)
    coverage = _phase_mobility_coverage(db).get(matrix_phase, set())
    missing = sorted(set(elements) - coverage)
    if missing:
        raise UserValueError(
            f"Для матрицы {matrix_phase} нет параметров подвижности: "
            + element_symbols(missing)
        )
    if gamma <= 0 or matrix_vm <= 0 or precip_vm <= 0:
        raise UserValueError("Межфазная энергия и молярные объёмы должны быть больше нуля.")
    if cmin_nm <= 0 or cmax_nm <= cmin_nm:
        raise UserValueError("Проверьте диапазон радиусов.")
    if bins < 20:
        raise UserValueError("Нужно не менее 20 классов размеров.")
    ratio_limit = HETEROGENEOUS_RATIO_LIMITS.get(nucleation_type)
    if ratio_limit is not None:
        ratio = float(gb_energy) / (2.0 * float(gamma))
        if ratio >= ratio_limit:
            raise ValueError(
                "Grain boundary to interfacial energy ratio is too large: "
                f"{ratio:.3f} >= {ratio_limit:.3f}."
            )

    if schedule_mode == "isothermal":
        if duration_h <= 0:
            raise UserValueError("Время выдержки должно быть больше нуля.")
        final_time = float(duration_h)*3600
        profile = [{"time_h": 0.0, "temperature_c": float(temperature_c)}, {"time_h": float(duration_h), "temperature_c": float(temperature_c)}]
    else:
        times_h, temperatures_c = _temperature_profile(profile_text)
        final_time = float(times_h[-1])*3600
        profile = [{"time_h": float(t), "temperature_c": float(T)} for t, T in zip(times_h, temperatures_c)]

    def build_model() -> tuple[Any, str]:
        if schedule_mode == "isothermal":
            temperature = TemperatureParameters(float(temperature_c)+273.15)
        else:
            temperature = TemperatureParameters(times_h.tolist(), (temperatures_c+273.15).tolist())
        therm, thermodynamics_class = _build_precipitation_thermodynamics(
            db,
            elements,
            [matrix_phase, precipitate_phase],
        )
        matrix = MatrixParameters(solutes)
        matrix.initComposition = np.asarray(x_at[1:], float)
        matrix.volume.setVolume(float(matrix_vm)*1e-6, "VM", 1)
        matrix.GBenergy = float(gb_energy)
        matrix.nucleationSites.setNucleationDensity(
            grainSize=float(grain_size_um), aspectRatio=1,
            dislocationDensity=float(dislocation_density), bulkN0=float(bulk_n0),
        )
        precip = PrecipitateParameters(precipitate_phase)
        precip.gamma = float(gamma)
        precip.volume.setVolume(float(precip_vm)*1e-6, "VM", 1)
        precip.nucleation.setNucleationType(nucleation_type)

        built = PrecipitateModel(matrix, [precip], therm, temperature)
        built.setPBMParameters(
            cMin=float(cmin_nm)*1e-9, cMax=float(cmax_nm)*1e-9, bins=int(bins),
            minBins=max(20, int(bins)//2), maxBins=max(80, int(bins)*2), adaptive=True,
        )
        return built, thermodynamics_class

    model, thermodynamics_class = build_model()
    try:
        # Своя модель и своя термодинамика: вызов движущей силы после setup()
        # на объектах расчёта сдвигал сам расчёт в 8-м знаке (13-Р).
        estimate_model, _estimate_class = build_model()
        nucleus_estimates = _nucleus_estimates(
            estimate_model,
            precipitate_phase,
            [float(item["temperature_c"]) + 273.15 for item in profile],
        )
        # Предел и ветка барьера берутся у самого kawin — у параметров
        # выделения той же модели.
        estimate_precipitate = estimate_model.precipitates[
            estimate_model.phaseIndex(precipitate_phase)
        ]
        radius_floor_nm = 1e9*float(estimate_precipitate.Rmin)
        grain_boundary_nucleation = bool(
            estimate_precipitate.nucleation.isGrainBoundaryNucleation
        )
    except Exception:
        # Оценка не удалась — решение остаётся за проверками после расчёта.
        nucleus_estimates = []
        radius_floor_nm = None
        grain_boundary_nucleation = False
    # Радиус до зажима — первым: при зажиме оценка сетки считается от предела.
    radius_warnings = _check_critical_radius_floor(
        nucleus_estimates, radius_floor_nm, grain_boundary_nucleation
    )
    _check_size_grid(nucleus_estimates, cmin_nm, cmax_nm, int(bins))
    grid_warnings = _check_nucleus_above_grid(nucleus_estimates, cmax_nm)
    model.setPSDrecording(False)
    if hasattr(model, "cacheCalculations"):
        model.cacheCalculations(True)
    # BL-35. Баланс масс может вывести состав матрицы за границы: условие
    # останавливает расчёт после такого шага, а деление на ноль внутри
    # pycalphad, случившееся раньше проверки, превращается в тот же отказ.
    composition_stop = _MatrixCompositionStop(solutes, balance, x_at[1:])
    model.addStoppingCondition(composition_stop)
    stop_note = ""
    try:
        model.solve(final_time, verbose=False)
    except ZeroDivisionError as error:
        if not _raised_in_pycalphad(error):
            raise
        last = int(model.data.n)
        stop_note = _solver_failure_note(
            float(model.data.time[last]), model.data.composition[last], solutes, balance
        )
    if composition_stop.isSatisfied():
        stop_note = _composition_stop_note(
            composition_stop.satisfiedTime(), composition_stop.element, composition_stop.value
        )

    data = model.data
    p = model.phaseIndex(precipitate_phase)
    n = int(data.n)+1
    time_s = np.asarray(data.time[:n], float)
    time_h = time_s/3600
    T_c = np.asarray(data.temperature[:n], float)-273.15
    fraction = np.asarray(data.volFrac[:n, p], float)
    radius_nm = 1e9*np.asarray(data.Ravg[:n, p], float)
    density = np.asarray(data.precipitateDensity[:n, p], float)
    nuc_rate = np.asarray(data.nucRate[:n, p], float)
    dg_m3 = np.asarray(data.drivingForce[:n, p], float)
    kinetics = pd.DataFrame({
        "Время, с": time_s, "Время, ч": time_h, "Температура, °C": T_c,
        "Объёмная доля, %": 100*fraction, "Средний радиус, нм": radius_nm,
        "Плотность частиц, 1/м³": density,
        "Скорость зарождения, 1/(м³·с)": nuc_rate,
        "Движущая сила, Дж/м³": dg_m3,
        "Движущая сила, Дж/моль": dg_m3*float(precip_vm)*1e-6,
        "Критический радиус, нм": 1e9*np.asarray(data.Rcrit[:n, p], float),
        "Радиус зародыша, нм": 1e9*np.asarray(data.Rnuc[:n, p], float),
    })
    composition = np.asarray(data.composition[:n], float)
    matrix_dict: dict[str, Any] = {"Время, ч": time_h}
    for i, element in enumerate(solutes):
        matrix_dict[f"{element}, матрица, ат.%"] = 100*composition[:, i]
    matrix_dict[f"{balance}, матрица, ат.%"] = 100*np.clip(1-composition.sum(axis=1), 0, 1)
    matrix_table = pd.DataFrame(matrix_dict)
    alpha = np.asarray(data.xEqAlpha[:n, p], float)
    beta = np.asarray(data.xEqBeta[:n, p], float)
    interface_dict: dict[str, Any] = {"Время, ч": time_h}
    for i, element in enumerate(solutes):
        interface_dict[f"{element}, матрица на границе, ат.%"] = 100*alpha[:, i]
        interface_dict[f"{element}, выделение на границе, ат.%"] = 100*beta[:, i]
    interface_table = pd.DataFrame(interface_dict)
    pbm = model.getPBM(precipitate_phase)
    psd = pd.DataFrame({
        "Радиус класса, нм": 1e9*np.asarray(pbm.PSDsize, float),
        "Число частиц в классе, 1/м³": np.asarray(pbm.PSD, float),
    })
    quality = _quality(data, p, len(solutes), cmin_nm, cmax_nm, int(bins), stop_note)
    summary = _summary(time_h, fraction, radius_nm, density, nuc_rate)
    settings_rows = [
        ("База", database_label), ("Файл базы", str(database_path)),
        ("SHA-256 базы", database_sha256), ("Kawin", _pkg("kawin")),
        ("pycalphad", _pkg("pycalphad")),
        ("Класс термодинамики Kawin", thermodynamics_class),
        ("Состав", composition_text),
        ("Единицы исходного состава", "атомные %" if units == "at" else "массовые %"),
        ("Элемент-основа", balance),
        ("Температурный режим", "изотермический" if schedule_mode == "isothermal" else "пользовательский цикл"),
        ("Элементы", ", ".join(elements)), ("Матрица", matrix_phase),
        ("Роль матрицы в order/disorder-модели", matrix_role["role"]),
        ("Фаза-выделение", precipitate_phase), ("Межфазная энергия, Дж/м²", gamma),
        ("Молярный объём матрицы, см³/моль", matrix_vm),
        ("Молярный объём выделения, см³/моль", precip_vm),
        ("Центры зарождения", nucleation_type), ("Bulk N0, 1/м³", bulk_n0),
        ("Размер зерна, мкм", grain_size_um),
        ("Плотность дислокаций, 1/м²", dislocation_density),
        ("Энергия границы зерна, Дж/м²", gb_energy),
        ("Минимальный радиус, нм", cmin_nm), ("Максимальный радиус, нм", cmax_nm),
        ("Классов размеров", bins),
        ("Источник физических входов", input_provenance.strip()),
        ("Правки базы ThermoGar", "; ".join(database_warnings) or "нет"),
        ("Класс расчёта", "исследовательский сценарий, не прогноз материала"),
    ]
    # Колонка значений намеренно текстовая: смесь строк и чисел в одном
    # столбце object не переводится в Arrow, и Streamlit печатает
    # ArrowTypeError при каждом показе таблицы параметров.
    settings = pd.DataFrame(
        [
            (name, f"{value:.10g}" if isinstance(value, float) else str(value))
            for name, value in settings_rows
        ],
        columns=["Параметр", "Значение"],
    )
    provenance = {
        "schema_version": 2,
        "implementation_revision": KWN_ADAPTER_IMPLEMENTATION_REVISION,
        "release_status": release_status(),
        "adapter_revision": KWN_ADAPTER_IMPLEMENTATION_REVISION,
        "database_key": database_key, "database_sha256": database_sha256,
        "packages": {"kawin": _pkg("kawin"), "pycalphad": _pkg("pycalphad")},
        "model": "KWN; one homogeneous matrix; one spherical precipitate phase",
        "thermodynamics_class": thermodynamics_class,
        "matrix_order_disorder_role": matrix_role,
        "fe_kwn_publication_status": (
            FE_KWN_PUBLICATION_STATUS
            if str(database_key).lower() == "fe" else "NOT_APPLICABLE"
        ),
        "temperature_profile": profile,
        "parameters": {key: value for key, value in settings_rows},
        "input_confirmation": True,
        "database_overrides": database_warnings,
        "limitations": [
            "user-supplied interfacial energy and molar volumes",
            "spherical particles and homogeneous matrix",
            "no automatic fitting or uncertainty estimate",
        ],
    }
    figures = {
        "fraction": _single_figure(time_h, 100*fraction, "Объёмная доля, %", f"Доля {precipitate_phase}", precipitate_phase),
        "radius_density": _radius_density_figure(time_h, radius_nm, density, precipitate_phase),
        "nucleation": _single_figure(time_h, nuc_rate, "Скорость зарождения, 1/(м³·с)", f"Зарождение {precipitate_phase}", precipitate_phase, True),
        "composition": _composition_figure(matrix_table, solutes),
        "psd": _psd_figure(psd, precipitate_phase),
    }
    buffer = BytesIO()
    np.savez_compressed(buffer, **model.toDict())
    return PrecipitationResult(
        database_key=database_key, phase=precipitate_phase, settings=settings, summary=summary,
        kinetics=kinetics, matrix_composition=matrix_table,
        interface_composition=interface_table, psd=psd, quality=quality,
        figures=figures, npz=buffer.getvalue(),
        provenance=json.dumps(provenance, ensure_ascii=False, indent=2, default=str).encode("utf-8-sig"),
        warnings=list(database_warnings) + radius_warnings + grid_warnings + (
            [KWN_LONG_COMPOSITION_WARNING.format(count=len(solutes))]
            if len(solutes) > KWN_SOLUTES_WITHOUT_TIME_WARNING else []
        ),
        stop_note=stop_note,
    )


def _excel(result: PrecipitationResult) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        result.settings.to_excel(writer, sheet_name="Параметры", index=False)
        result.summary.to_excel(writer, sheet_name="Итоги", index=False)
        result.kinetics.to_excel(writer, sheet_name="Кинетика", index=False)
        result.matrix_composition.to_excel(writer, sheet_name="Состав матрицы", index=False)
        result.interface_composition.to_excel(writer, sheet_name="Межфазные составы", index=False)
        result.psd.to_excel(writer, sheet_name="Итоговое PSD", index=False)
        result.quality.to_excel(writer, sheet_name="Проверки", index=False)
    return buffer.getvalue()


def _png(figure: plt.Figure) -> bytes:
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=200, bbox_inches="tight")
    return buffer.getvalue()


def render_precipitation_section(
    *, db: Any, database_key: str, database_path: str | Path,
    database_label: str, project_root: str | Path,
    current_context: dict[str, Any], render_error: Callable[..., Any],
    record_history: Callable[..., Any] | None = None,
) -> None:
    st.subheader("Кинетика выделений")
    st.caption("Зарождение, рост, растворение и укрупнение одной фазы по модели KWN.")
    if not PRECIPITATION_AVAILABLE:
        st.error("Модуль кинетики выделений недоступен. Остальные функции работают.")
        with st.expander("Технические сведения", expanded=False):
            st.code(PRECIPITATION_IMPORT_ERROR or "kawin не установлен")
        return
    st.info(
        "Межфазную энергию, молярные объёмы и центры зарождения база не "
        "задаёт: введите их ниже по источнику или по калибровке."
    )

    default = DEFAULTS.get(database_key, DEFAULTS["ni"])
    widget_prefix = f"precipitation_{database_key}"
    preset_options = ["Параметры пользователя — значения нужно подтвердить"]
    if database_key == "ni":
        preset_options.append(PRESET_NI["label"])
    preset_label = st.selectbox(
        "Набор исходных параметров",
        preset_options,
        # Название набора — значение виджета (ключ session_state), поэтому
        # точка вместо запятой только при показе (21-Ж, шаг 2 д).
        format_func=lambda option: (
            PRESET_NI_DISPLAY_LABEL if option == PRESET_NI["label"] else option
        ),
        key=f"{widget_prefix}_preset",
    )
    demo = database_key == "ni" and preset_label == PRESET_NI["label"]
    mode_key = "demo" if demo else "user"
    if demo:
        st.info(
            "Учебный пример автоматически использует Ni–9.8Al–8.3Cr, "
            "800 °C, γ=0.023 Дж/м² и Vm=6.566 см³/моль. "
            "Он нужен для проверки программы и не является паспортом материала."
        )
    else:
        st.caption(
            "Начальные числа в полях — только удобные стартовые значения. "
            "Перед интерпретацией укажите их источник."
        )

    # Учебный набор должен быть воспроизводимым и не зависеть от того,
    # какой состав остался в глобальной боковой панели. Пользовательский
    # режим, напротив, всегда читает текущий глобальный контекст.
    if demo:
        balance = "NI"
        composition = PRESET_NI["composition"]
        units = "at"
        effective_context = dict(current_context)
        effective_context.update(
            {
                "database_key": "ni",
                "balance": balance,
                "composition": composition,
                "units": units,
            }
        )
    else:
        balance = str(current_context.get("balance", "NI")).upper()
        composition = str(current_context.get("composition", ""))
        units = str(current_context.get("units", "at"))
        effective_context = current_context
    try:
        elements, _x_at, _x_wt = _composition_vectors(db, balance, composition, units)
        matrices = _selectable_phases(database_key, _matrix_candidates(db, elements))
    except Exception as error:
        render_error(error, context="кинетика выделений", title="Состав не принят.")
        st.caption(
            "Состав раздела берётся из поля «Добавки» в боковой панели. "
            f"KWN-модель принимает не более {KWN_MAX_SOLUTES} добавок одновременно. "
            "Это предел измеренного, а не физический: больше "
            f"{KWN_MAX_SOLUTES} добавок расчёт не проверялся. Если добавок больше, "
            "оставьте в составе только элементы, определяющие выделение "
            "(например, C и Cr для карбида M23C6 в стали)."
        )
        return
    if not matrices:
        st.error("Нет матричной фазы с полным набором параметров подвижности для состава.")
        st.caption(
            "Матрицей может быть только фаза, у которой в базе есть "
            "параметры подвижности для всех элементов состава: "
            + element_symbols(elements)
            + ". Сократите состав в боковой панели до элементов, "
            "покрытых параметрами подвижности."
        )
        return

    matrix_default = PRESET_NI["matrix"] if demo else default[0]
    matrix_default = matrix_default if matrix_default in matrices else matrices[0]
    matrix_phase = st.selectbox(
        "Матричная фаза",
        matrices,
        index=matrices.index(matrix_default),
        key=f"{widget_prefix}_{mode_key}_matrix",
    )
    matrix_partner = _order_disorder_partner(db, matrix_phase)
    if matrix_partner:
        st.caption(
            f"{matrix_phase} и {matrix_partner} — разупорядоченная и "
            "упорядоченная половины одной модели порядок/беспорядок. Kawin "
            f"принимает матрицей только {matrix_phase}; {matrix_partner} "
            "поэтому не предлагается как отдельная фаза-выделение."
        )
    compatible_phases = _selectable_phases(
        database_key, _compatible_phases(db, elements)
    )
    excluded_precipitates = {matrix_phase, "LIQUID"}
    if matrix_partner:
        excluded_precipitates.add(matrix_partner)
    precipitates = sorted(
        phase for phase in compatible_phases
        if phase not in excluded_precipitates
    )
    if not precipitates:
        st.error("Для выбранного состава нет совместимых фаз-выделений.")
        return
    precip_default = PRESET_NI["precipitate"] if demo else default[1]
    precip_default = precip_default if precip_default in precipitates else precipitates[0]
    precipitate_phase = st.selectbox(
        "Фаза-выделение",
        precipitates,
        index=precipitates.index(precip_default),
        key=f"{widget_prefix}_{mode_key}_precipitate",
    )

    mode_label = st.radio(
        "Температурный режим",
        ["Изотермическая выдержка", "Пользовательский температурный цикл"],
        horizontal=True,
        key=f"{widget_prefix}_{mode_key}_temperature_mode",
    )
    schedule_mode = "isothermal" if mode_label.startswith("Изотермическая") else "profile"
    temperature_c = PRESET_NI["temperature_c"] if demo else default[2]
    duration_h = PRESET_NI["duration_h"] if demo else default[3]
    profile_text = "0; 800\n20; 800\n20.1; 1100\n40; 1100"
    if schedule_mode == "isothermal":
        temperature_c = st.number_input(
            "Температура, °C",
            value=float(temperature_c),
            step=10.0,
            key=f"{widget_prefix}_{mode_key}_temperature_c",
        )
        duration_h = st.number_input(
            "Время выдержки, ч",
            min_value=1e-6,
            value=float(duration_h),
            step=10.0,
            key=f"{widget_prefix}_{mode_key}_duration_h",
        )
    else:
        profile_text = st.text_area(
            "Время, ч; температура, °C",
            value=profile_text,
            height=145,
            help="Точки соединяются линейно. Первая точка — 0 ч.",
            key=f"{widget_prefix}_{mode_key}_temperature_profile",
        )

    with st.expander("Параметры модели KWN", expanded=True):
        gamma = st.number_input(
            "Межфазная энергия, Дж/м²",
            min_value=1e-6,
            value=float(PRESET_NI["gamma"] if demo else default[4]),
            step=0.005,
            format="%.6g",
            key=f"{widget_prefix}_{mode_key}_gamma",
        )
        matrix_vm = st.number_input(
            "Молярный объём матрицы, см³/моль",
            min_value=0.01,
            value=float(PRESET_NI["matrix_vm"] if demo else default[5]),
            step=0.1,
            key=f"{widget_prefix}_{mode_key}_matrix_vm",
        )
        precip_vm = st.number_input(
            "Молярный объём выделения, см³/моль",
            min_value=0.01,
            value=float(PRESET_NI["precip_vm"] if demo else default[6]),
            step=0.1,
            key=f"{widget_prefix}_{mode_key}_precip_vm",
        )
        nucleation_label = st.selectbox(
            "Центры зарождения",
            list(NUCLEATION_TYPES),
            key=f"{widget_prefix}_{mode_key}_nucleation_type",
        )
        nucleation_type = NUCLEATION_TYPES[nucleation_label]
        bulk_n0 = st.number_input(
            "Плотность объёмных центров, 1/м³",
            min_value=1.0,
            value=float(PRESET_NI["bulk_n0"] if demo else 1e28),
            format="%.6e",
            key=f"{widget_prefix}_{mode_key}_bulk_n0",
        )
        grain_size_um = st.number_input(
            "Средний размер зерна, мкм",
            min_value=0.01,
            value=100.0,
            step=10.0,
            key=f"{widget_prefix}_{mode_key}_grain_size_um",
        )
        dislocation_density = st.number_input(
            "Плотность дислокаций, 1/м²",
            min_value=1.0,
            value=5e12,
            format="%.6e",
            key=f"{widget_prefix}_{mode_key}_dislocation_density",
        )
        gb_energy = st.number_input(
            "Энергия границы зерна, Дж/м²",
            min_value=0.0,
            value=0.3,
            step=0.05,
            key=f"{widget_prefix}_{mode_key}_gb_energy",
        )

    with st.expander("Численная сетка размеров"):
        cmin_nm = st.number_input(
            "Минимальный радиус, нм",
            min_value=0.01,
            value=0.2,
            step=0.05,
            key=f"{widget_prefix}_{mode_key}_cmin_nm",
        )
        cmax_nm = st.number_input(
            "Начальный максимальный радиус, нм",
            min_value=0.1,
            value=10.0,
            step=1.0,
            key=f"{widget_prefix}_{mode_key}_cmax_nm",
        )
        bins = st.slider(
            "Классов размеров",
            20,
            200,
            80,
            10,
            key=f"{widget_prefix}_{mode_key}_bins",
        )
        st.caption("Сетка адаптивная и может расширяться при росте частиц.")

    if demo:
        input_provenance = "SYNTHETIC_EDUCATIONAL_DEMO_NOT_MATERIAL_INPUT"
    else:
        input_provenance = st.text_area(
            "Источник и применимость физических входов",
            value=DEFAULT_INPUT_PROVENANCE,
            help=(
                "Строка попадает в Excel, в JSON происхождения и в историю "
                "расчётов. Впишите DOI, таблицу или страницу, откуда взяты "
                "γ, Vm и параметры зарождения; значение по умолчанию помечает "
                "их как объявленный сценарий, не данные материала."
            ),
            key=f"{widget_prefix}_{mode_key}_input_provenance",
        )
    input_provenance = str(input_provenance).strip() or DEFAULT_INPUT_PROVENANCE
    # Раздел целиком объявлен исследовательским: постоянное предупреждение в
    # начале вкладки, блок «Ограничения исследовательского KWN mode» в конце и
    # строка сценария в листе «Параметры». Отдельная галочка ничего к этому не
    # добавляла и лишь держала кнопку расчёта выключенной, поэтому убрана;
    # содержательные проверки ввода (состав, фазы, γ, Vm, сетка) на месте.
    research_scenario_declared = True

    if release_calculation_button(
        "Рассчитать кинетику выделений",
        type="primary",
        key=f"{widget_prefix}_{mode_key}_calculate",
    ):
        try:
            with st.spinner("Расчёт KWN может занять несколько минут…"):
                result = run_precipitation(
                    db=db, database_path=database_path, database_label=database_label,
                    database_key=database_key, balance=balance,
                    composition_text=composition, units=units,
                    matrix_phase=matrix_phase, precipitate_phase=precipitate_phase,
                    schedule_mode=schedule_mode, temperature_c=float(temperature_c),
                    duration_h=float(duration_h), profile_text=profile_text,
                    gamma=float(gamma), matrix_vm=float(matrix_vm),
                    precip_vm=float(precip_vm), nucleation_type=nucleation_type,
                    bulk_n0=float(bulk_n0), grain_size_um=float(grain_size_um),
                    dislocation_density=float(dislocation_density),
                    gb_energy=float(gb_energy), cmin_nm=float(cmin_nm),
                    cmax_nm=float(cmax_nm), bins=int(bins),
                    input_provenance=str(input_provenance),
                    input_confirmation=research_scenario_declared,
                )
            st.session_state["thermogar_precipitation_result"] = result
            if record_history is not None:
                try:
                    record_history(
                        project_root,
                        "Кинетика выделений KWN",
                        effective_context,
                        {
                            "database": database_label,
                            "matrix": matrix_phase,
                            "precipitate": precipitate_phase,
                            "gamma_J_m2": float(gamma),
                            "temperature_mode": schedule_mode,
                            "kawin": _pkg("kawin"),
                            "summary": result.summary.to_dict(orient="records"),
                        },
                    )
                except Exception:
                    pass
        except Exception as error:
            render_error(error, context="кинетика выделений")

    result = st.session_state.get("thermogar_precipitation_result")
    if not isinstance(result, PrecipitationResult):
        return
    if result.database_key != database_key:
        st.info("Результат относится к другой базе. Выполните расчёт заново.")
        return
    for warning in getattr(result, "warnings", ()) or ():
        st.warning(warning)
    # BL-35. Текст отказа — и над вкладками, и строкой в таблице проверок.
    if getattr(result, "stop_note", ""):
        st.error(result.stop_note)
    if (result.quality["Статус"] == "пройдена").all():
        st.success("Внутренние численные проверки пройдены.")
    else:
        st.error("Одна или несколько внутренних проверок не пройдены.")
    overview, kinetics_tab, psd_tab, export_tab = st.tabs(
        ["Итоги", "Кинетика и состав", "Распределение размеров", "Экспорт и ограничения"]
    )
    with overview:
        st.dataframe(element_columns_for_display(result.summary), width="stretch", hide_index=True)
        st.pyplot(result.figures["fraction"])
        st.pyplot(result.figures["radius_density"])
        st.dataframe(result.quality, width="stretch", hide_index=True)
    with kinetics_tab:
        st.pyplot(result.figures["nucleation"])
        st.pyplot(result.figures["composition"])
        st.dataframe(element_columns_for_display(result.kinetics), width="stretch", hide_index=True)
        with st.expander("Составы матрицы и межфазного равновесия"):
            st.dataframe(element_columns_for_display(result.matrix_composition), width="stretch", hide_index=True)
            st.dataframe(element_columns_for_display(result.interface_composition), width="stretch", hide_index=True)
    with psd_tab:
        st.pyplot(result.figures["psd"])
        st.dataframe(result.psd, width="stretch", hide_index=True)
    with export_tab:
        release_download_button("Скачать Excel", data=_excel(result), file_name=f"ThermoGar_precipitation_{result.phase}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"{widget_prefix}_download_excel")
        release_download_button("Скачать состояние модели, NPZ", data=result.npz, file_name=f"ThermoGar_precipitation_{result.phase}.npz", mime="application/octet-stream", key=f"{widget_prefix}_download_npz")
        release_download_button("Скачать происхождение, JSON", data=result.provenance, file_name=f"ThermoGar_precipitation_{result.phase}_provenance.json", mime="application/json", key=f"{widget_prefix}_download_json")
        release_download_button("Скачать график доли, PNG", data=_png(result.figures["fraction"]), file_name=f"ThermoGar_{result.phase}_fraction.png", mime="image/png", key=f"{widget_prefix}_download_fraction_png")
        release_download_button("Скачать график размера и плотности, PNG", data=_png(result.figures["radius_density"]), file_name=f"ThermoGar_{result.phase}_size_density.png", mime="image/png", key=f"{widget_prefix}_download_size_png")
        release_download_button("Скачать график распределения размеров, PNG", data=_png(result.figures["psd"]), file_name=f"ThermoGar_{result.phase}_PSD.png", mime="image/png", key=f"{widget_prefix}_download_psd_png")
        st.markdown(
            """
### Ограничения расчёта выделений (KWN)

- Одна однородная матрица и одна сферическая фаза-выделение.
- Межфазная энергия, молярные объёмы и центры зарождения задаются пользователем.
- Нет автоматической калибровки, упругой энергии, изменения формы и градиентов состава.
- Зелёная проверка означает численную согласованность, а не совпадение с экспериментом.
- Автоматический прогноз прочности, твёрдости и пластичности отключён; результат KWN не заменяет проверку на материале.
"""
        )
