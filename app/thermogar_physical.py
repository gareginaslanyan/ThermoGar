"""ThermoGar Stage 11: density and phase-volume calculations.

The module reads the open MatCalc ``physical_data.pdb`` density database
(version 1.03), evaluates its ``FUNCTION`` and ``PARAMETER DP`` expressions,
and combines phase densities with pycalphad equilibrium results.

Three levels of data quality are kept separate:

* ``direct`` — the phase name and its DP model are present in the PDB;
* ``inherited`` — an ordered/structurally related phase uses the density model
  of its disordered parent (for example BCC_B2 -> BCC_A2);
* ``missing`` — no physical model is available and no number is invented.

The implementation intentionally does not claim to reproduce every internal
MatCalc property-model detail. Direct phases use the PDB compound-energy style
endmember and binary interaction expressions with equilibrium site fractions.
Inherited phases are clearly marked as estimates.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from functools import lru_cache
from itertools import product
from pathlib import Path
import ast
import hashlib
import json
import math
import os
import re
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd


PHYSICAL_DATABASE_VERSION = "1.03"
REFERENCE_TEMPERATURE_K = 298.15

# Перекрывающий слой к физической базе. Байты ``.pdb`` не меняются никогда
# (правило проекта), поэтому наши правки живут отдельным файлом рядом с базой и
# накладываются при разборе. Применённая правка обязана быть видна пользователю:
# молча подменять данные источника нельзя.
PHYSICAL_OVERRIDES_RELATIVE_PATH = (
    "databases/physical/overrides/physical_data_v103.overrides.json"
)
PHYSICAL_OVERRIDES_FORMAT = "thermogar-physical-override"
PHYSICAL_OVERRIDES_ENV = "THERMOGAR_PHYSICAL_OVERRIDES"
_OVERRIDES_OFF_WORDS = {"0", "off", "no", "false", "нет", "выкл"}

# A small, explicit alias table. Dynamic order/disorder mappings from the
# thermodynamic database are checked before these aliases.
PHASE_ALIASES: dict[str, tuple[str, str, str]] = {
    "FCCAL": (
        "FCC_A1",
        "inherited",
        "Плотность оценена по ГЦК-модели FCC_A1.",
    ),
    "GAMMA_PRIME": (
        "FCC_A1",
        "inherited",
        "Плотность оценена по разупорядоченной ГЦК-модели FCC_A1.",
    ),
    "GP_MAT": (
        "FCC_A1",
        "inherited",
        "Плотность оценена по связанной ГЦК-модели FCC_A1.",
    ),
    "BCC_B2": (
        "BCC_A2",
        "inherited",
        "Плотность оценена по разупорядоченной ОЦК-модели BCC_A2.",
    ),
    "NIAL": (
        "BCC_A2",
        "inherited",
        "Плотность B2-фазы оценена по ОЦК-модели BCC_A2.",
    ),
    "LAVES": (
        "LAVES_PHASE",
        "structural",
        "Использована общая модель фазы Лавеса из physical_data.pdb.",
    ),
    "LAV_C14": (
        "LAVES_PHASE",
        "structural",
        "Использована общая модель фазы Лавеса; политип C14 отдельно не параметризован.",
    ),
    "LAV_C15": (
        "LAVES_PHASE",
        "structural",
        "Использована общая модель фазы Лавеса; политип C15 отдельно не параметризован.",
    ),
    "LAV_C36": (
        "LAVES_PHASE",
        "structural",
        "Использована общая модель фазы Лавеса; политип C36 отдельно не параметризован.",
    ),
    "ALN_EQU": (
        "ALN",
        "structural",
        "Использована модель плотности AlN.",
    ),
    "M23C6_WY": (
        "M23C6",
        "structural",
        "Использована общая модель карбида M23C6.",
    ),
    "M6C_WY": (
        "M6C",
        "structural",
        "Использована общая модель карбида M6C.",
    ),
    # 18-А (BL-48): растворная фаза кремния mc_al (AL,CR,CU,MG,SI%,TI,ZN).
    "SI_DIAMOND_A4": (
        "DIAMOND_A4",
        "inherited",
        "Плотность оценена по модели DIAMOND_A4 той же структуры.",
    ),
}

# PDB conventions for a bare wildcard in matrix phases. The original file has
# DP(BCC_A2,*) together with DP(BCC_A2,*:C) and DP(BCC_A2,*:N), so the bare
# wildcard represents the vacancy endmember of the interstitial sublattice.
MATRIX_PHASES = {"BCC_A2", "FCC_A1", "HCP_A3"}
DEFAULT_MATRIX_SITE_RATIOS: dict[str, tuple[float, float]] = {
    "BCC_A2": (1.0, 3.0),
    "FCC_A1": (1.0, 1.0),
    "HCP_A3": (1.0, 0.5),
}
INTERSTITIAL_NAMES = {"C", "N", "H", "O", "B", "VA"}

# Атомные массы, г/моль. Нужны здесь потому, что смешение плотностей идёт по
# массе: ``1/ρ = Σ wᵢ/ρᵢ``. Вакансия массы не несёт и в сумму не входит.
_ATOMIC_MASSES: dict[str, float] = {
    "VA": 0.0, "H": 1.008, "B": 10.811, "C": 12.011, "N": 14.007, "O": 15.999,
    "MG": 24.305, "AL": 26.982, "SI": 28.085, "P": 30.974, "S": 32.06,
    "TI": 47.867, "V": 50.942, "CR": 51.996, "MN": 54.938, "FE": 55.845,
    "CO": 58.933, "NI": 58.693, "CU": 63.546, "ZN": 65.38, "Y": 88.906,
    "ZR": 91.224, "NB": 92.906, "MO": 95.95, "PD": 106.42, "AG": 107.868,
    "SN": 118.71, "LA": 138.905, "HF": 178.49, "TA": 180.948, "W": 183.84,
    "RE": 186.207, "PT": 195.084, "AU": 196.967, "PB": 207.2,
}


@dataclass(frozen=True)
class FunctionDefinition:
    name: str
    lower_temperature: float
    expression: str
    upper_temperature: float


@dataclass(frozen=True)
class DensityParameter:
    phase: str
    constituent_array: tuple[tuple[str, ...], ...]
    order: int
    lower_temperature: float
    expression: str
    upper_temperature: float
    raw_command: str

    @property
    def is_interaction(self) -> bool:
        return any(len(sublattice) > 1 for sublattice in self.constituent_array)


@dataclass(frozen=True)
class PhaseModelResolution:
    requested_phase: str
    physical_phase: str | None
    quality: str
    note: str


@dataclass
class PhysicalCalculationResult:
    phase_table: pd.DataFrame
    missing_table: pd.DataFrame
    alloy_density_kg_m3: float | None
    alloy_density_g_cm3: float | None
    mole_coverage_pct: float
    mass_coverage_pct: float
    direct_mole_pct: float
    inherited_mole_pct: float
    estimated_mole_pct: float
    quality_label: str
    warnings: list[str]
    physical_database_sha256: str
    physical_database_version: str
    # BL-39: тексты о моделях плотности элементов, взятых в правиле смеси
    # (они же стоят в ``warnings``); нужны подготовке весов VRH.
    element_density_notes: list[str] = field(default_factory=list)


class _SafeExpression:
    """Evaluate the small arithmetic language used in physical_data.pdb."""

    _binary_operators = {
        ast.Add: lambda left, right: left + right,
        ast.Sub: lambda left, right: left - right,
        ast.Mult: lambda left, right: left * right,
        ast.Div: lambda left, right: left / right,
        ast.Pow: lambda left, right: left**right,
    }
    _unary_operators = {
        ast.UAdd: lambda value: value,
        ast.USub: lambda value: -value,
    }
    _allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Name,
        ast.Load,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.UAdd,
        ast.USub,
    )

    def __init__(self, expression: str):
        self.expression = expression
        tree = ast.parse(expression, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, self._allowed_nodes):
                raise ValueError(
                    "Неподдерживаемая конструкция в физической базе: "
                    f"{expression!r} ({type(node).__name__})"
                )
        self.root = tree.body

    def evaluate(
        self,
        temperature_k: float,
        function_resolver: Any,
    ) -> float:
        def visit(node: ast.AST) -> float:
            if isinstance(node, ast.Constant):
                return float(node.value)
            if isinstance(node, ast.Name):
                name = node.id.upper()
                if name == "T":
                    return float(temperature_k)
                return float(function_resolver(name, temperature_k))
            if isinstance(node, ast.UnaryOp):
                return self._unary_operators[type(node.op)](visit(node.operand))
            if isinstance(node, ast.BinOp):
                return self._binary_operators[type(node.op)](
                    visit(node.left),
                    visit(node.right),
                )
            raise TypeError(type(node).__name__)

        return float(visit(self.root))


@dataclass(frozen=True)
class DensityOverride:
    """Одна наша правка поверх физической базы.

    ``expression`` и ``source`` могут быть пустыми: по правилу «Источники» из
    ``tasks/RULES.md`` число без прослеживаемого первоисточника в проект не
    попадает. Незаполненная правка описывает, что и почему подменяется, но
    ничего не подменяет — она видна как отложенная и ждёт статьи.
    """

    identifier: str
    kind: str
    name: str
    quantity: str
    expression: str | None
    original_expression: str
    reason: str
    source: str | None
    date: str
    wave: str
    user_message: str
    status: str

    @property
    def is_filled(self) -> bool:
        return bool(self.expression) and bool(self.source)


@dataclass(frozen=True)
class PhysicalOverrideSet:
    """Разобранный файл-дополнение к physical_data.pdb."""

    source_path: Path | None
    sha256: str
    enabled: bool
    notice: str
    target_sha256: str
    entries: tuple[DensityOverride, ...]

    @property
    def filled(self) -> tuple[DensityOverride, ...]:
        return tuple(entry for entry in self.entries if entry.is_filled)

    @property
    def pending(self) -> tuple[DensityOverride, ...]:
        return tuple(entry for entry in self.entries if not entry.is_filled)


def default_overrides_path() -> Path:
    """Штатное место файла перекрытий: рядом с базой, внутри дерева проекта."""

    return Path(__file__).resolve().parent.parent / PHYSICAL_OVERRIDES_RELATIVE_PATH


def overrides_enabled_by_environment(
    environment: Mapping[str, str] | None = None,
) -> bool:
    """``THERMOGAR_PHYSICAL_OVERRIDES=off`` отключает все наши правки."""

    source = os.environ if environment is None else environment
    value = str(source.get(PHYSICAL_OVERRIDES_ENV, "")).strip().lower()
    return value not in _OVERRIDES_OFF_WORDS if value else True


def _override_text(entry: Mapping[str, Any], key: str) -> str:
    value = entry.get(key)
    return "" if value is None else str(value)


def load_physical_overrides(path: str | Path) -> PhysicalOverrideSet:
    """Разобрать файл-дополнение. Формат наш, не MatCalc."""

    path = Path(path)
    data = path.read_bytes()
    document = json.loads(data.decode("utf-8"))
    if document.get("format") != PHYSICAL_OVERRIDES_FORMAT:
        raise ValueError(
            "Не файл перекрытий физической базы: " + str(path)
        )
    if int(document.get("format_version", 0)) != 1:
        raise ValueError(
            "Неизвестная версия формата перекрытий: "
            f"{document.get('format_version')!r}"
        )
    entries: list[DensityOverride] = []
    for item in document.get("overrides", ()):
        expression = item.get("expression")
        source = item.get("source")
        entries.append(
            DensityOverride(
                identifier=_override_text(item, "id"),
                kind=_override_text(item, "kind"),
                name=_override_text(item, "name"),
                quantity=_override_text(item, "quantity"),
                expression=None if expression is None else str(expression),
                original_expression=_override_text(item, "original_expression"),
                reason=_override_text(item, "reason"),
                source=None if source is None else json.dumps(
                    source, ensure_ascii=False, sort_keys=True
                ) if not isinstance(source, str) else source,
                date=_override_text(item, "date"),
                wave=_override_text(item, "wave"),
                user_message=_override_text(item, "user_message"),
                status=_override_text(item, "status") or "filled",
            )
        )
    return PhysicalOverrideSet(
        source_path=path,
        sha256=hashlib.sha256(data).hexdigest(),
        enabled=bool(document.get("enabled", False)),
        notice=_override_text(document, "notice"),
        target_sha256=str(document.get("applies_to", {}).get("sha256", "")),
        entries=tuple(entries),
    )


class _AutoOverrides:
    """Метка «взять штатный файл перекрытий, если он есть и не выключен»."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - диагностика
        return "AUTO_OVERRIDES"


AUTO_OVERRIDES = _AutoOverrides()


class _OverridesOffByUser:
    """Метка «пользователь выключил поправки галочкой в интерфейсе» (BL-14).

    Считается ровно как ``overrides=None``, но запоминает, какие правки были
    бы применены штатным путём, чтобы результат назвал их выключенными.
    Переменная окружения сильнее: при ``THERMOGAR_PHYSICAL_OVERRIDES=off``
    выключать нечего, и отметки нет.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - диагностика
        return "OVERRIDES_OFF_BY_USER"


OVERRIDES_OFF_BY_USER = _OverridesOffByUser()

# Текст для пользователя, когда поправки выключены галочкой раздела «Свойства».
# Стоит там же, где текст применённой поправки: первым в warnings результата.
OVERRIDES_OFF_BY_USER_NOTE = (
    "Поправки проекта ThermoGar к физической базе выключены пользователем: "
    "плотность посчитана строго по данным physical_data_v103.pdb. "
    "Не применены: {names}. У сплавов с хромом плотность при нагреве выходит "
    "ниже, чем с поправкой, — до 1 % при 700 °C и до 2 % при 1300 °C. "
    "Подробности: docs/DATABASES.md, раздел «Поправки проекта к физической базе»."
)


class PhysicalDensityDatabase:
    """Parsed MatCalc physical_data.pdb density model."""

    def __init__(
        self,
        source_path: str | Path,
        overrides: Any = AUTO_OVERRIDES,
    ):
        self.source_path = Path(source_path)
        if not self.source_path.exists():
            raise FileNotFoundError(
                "Не найдена физическая база: " + str(self.source_path)
            )
        self.sha256 = _file_sha256(self.source_path)
        self._initialize(
            self.source_path.read_text(encoding="utf-8", errors="replace"),
            overrides,
        )

    @classmethod
    def from_verified_bytes(
        cls,
        data: bytes,
        overrides: Any = AUTO_OVERRIDES,
    ) -> "PhysicalDensityDatabase":
        """Parse one already-verified PDB snapshot without path authority."""

        if type(data) is not bytes:
            raise TypeError("Verified physical database snapshot must be bytes.")
        text = data.decode("utf-8", errors="strict")
        database = cls.__new__(cls)
        database.source_path = None
        database.sha256 = hashlib.sha256(data).hexdigest()
        database._initialize(text, overrides)
        return database

    def _initialize(
        self,
        text: str,
        overrides: Any = AUTO_OVERRIDES,
    ) -> None:
        self.functions: dict[str, FunctionDefinition] = {}
        self.parameters: list[DensityParameter] = []
        self.parameters_by_phase: dict[str, list[DensityParameter]] = defaultdict(list)
        self._expression_cache: dict[str, _SafeExpression] = {}
        self._function_value_cache: dict[tuple[str, float], float] = {}
        self._parse(text)
        self._apply_overrides(overrides)

    def _resolve_overrides(self, overrides: Any) -> PhysicalOverrideSet | None:
        if overrides is None:
            return None
        if isinstance(overrides, _OverridesOffByUser):
            automatic = self._resolve_overrides(AUTO_OVERRIDES)
            if automatic is not None and automatic.enabled:
                self.suppressed_overrides = automatic.filled
            return None
        if isinstance(overrides, PhysicalOverrideSet):
            return overrides
        if isinstance(overrides, (str, Path)):
            return load_physical_overrides(overrides)
        if isinstance(overrides, _AutoOverrides):
            if not overrides_enabled_by_environment():
                return None
            path = default_overrides_path()
            return load_physical_overrides(path) if path.is_file() else None
        raise TypeError(
            "Непонятный аргумент overrides: " + type(overrides).__name__
        )

    def _apply_overrides(self, overrides: Any) -> None:
        """Наложить наши правки поверх разобранной базы.

        Незаполненные правки (нет выражения или нет источника) не применяются
        никогда: они ждут первоисточника и видны в ``pending_overrides``.
        Выключенный файл не применяется целиком.
        """

        self.suppressed_overrides: tuple[DensityOverride, ...] = ()
        self.overrides: PhysicalOverrideSet | None = self._resolve_overrides(overrides)
        self.applied_overrides: tuple[DensityOverride, ...] = ()
        self.pending_overrides: tuple[DensityOverride, ...] = ()
        if self.overrides is None:
            return

        self.pending_overrides = self.overrides.pending
        if not self.overrides.enabled:
            return
        if (
            self.overrides.target_sha256
            and self.overrides.target_sha256 != self.sha256
        ):
            raise ValueError(
                "Файл перекрытий рассчитан на другую физическую базу: "
                f"ожидался SHA-256 {self.overrides.target_sha256}, "
                f"загружена база {self.sha256}."
            )

        applied: list[DensityOverride] = []
        for entry in self.overrides.filled:
            if entry.kind != "function":
                raise ValueError(
                    f"Перекрытие {entry.identifier}: неизвестный вид "
                    f"{entry.kind!r}; поддержан только 'function'."
                )
            key = entry.name.upper()
            definition = self.functions.get(key)
            if definition is None:
                raise ValueError(
                    f"Перекрытие {entry.identifier} ссылается на функцию "
                    f"{entry.name}, которой нет в физической базе."
                )
            self.functions[key] = replace(
                definition,
                expression=_normalize_expression(str(entry.expression)),
            )
            applied.append(entry)

        self.applied_overrides = tuple(applied)
        self._function_value_cache.clear()

    @property
    def override_notes(self) -> list[str]:
        """Тексты для пользователя обо всех применённых правках.

        Если правки выключены пользователем, вместо них — одна строка о том,
        что именно не применено.
        """

        if self.suppressed_overrides and not self.applied_overrides:
            return [
                OVERRIDES_OFF_BY_USER_NOTE.format(
                    names=", ".join(
                        entry.name for entry in self.suppressed_overrides
                    )
                )
            ]
        return [
            entry.user_message
            or (
                f"Величина {entry.name} заменена поправкой проекта ThermoGar "
                "поверх данных физической базы."
            )
            for entry in self.applied_overrides
        ]

    @property
    def phases(self) -> set[str]:
        return set(self.parameters_by_phase)

    @property
    def direct_phase_models(self) -> list[str]:
        return sorted(self.parameters_by_phase)

    @property
    def density_lower_temperature_k(self) -> float:
        """Нижняя граница, с которой база задаёт плотность: минимум нижних
        границ DP-параметров (BL-49). Ниже неё ``parameter_value`` отказывает."""

        return min(parameter.lower_temperature for parameter in self.parameters)

    def _parse(self, text: str) -> None:
        for command in _active_commands(text):
            upper = command.upper()
            if upper.startswith("FUNCTION "):
                definition = _parse_function(command)
                self.functions[definition.name] = definition
            elif upper.startswith("PARAMETER DP("):
                parameter = _parse_density_parameter(command)
                self.parameters.append(parameter)
                self.parameters_by_phase[parameter.phase].append(parameter)

        if not self.functions or not self.parameters:
            raise ValueError(
                "Физическая база не содержит распознанных FUNCTION/DP параметров."
            )

    def expression(self, expression: str) -> _SafeExpression:
        if expression not in self._expression_cache:
            self._expression_cache[expression] = _SafeExpression(expression)
        return self._expression_cache[expression]

    def function_value(self, name: str, temperature_k: float) -> float:
        key = (name.upper(), round(float(temperature_k), 10))
        if key in self._function_value_cache:
            return self._function_value_cache[key]
        definition = self.functions.get(key[0])
        if definition is None:
            raise KeyError(f"В physical_data.pdb не найдена функция {name}.")
        if not (
            definition.lower_temperature <= float(temperature_k)
            <= definition.upper_temperature
        ):
            raise ValueError(
                f"Температура {float(temperature_k):.2f} K вне диапазона "
                f"функции {definition.name}: "
                f"{definition.lower_temperature:.2f}–"
                f"{definition.upper_temperature:.2f} K."
            )
        value = self.expression(definition.expression).evaluate(
            float(temperature_k),
            self.function_value,
        )
        self._function_value_cache[key] = float(value)
        return float(value)

    def parameter_value(
        self,
        parameter: DensityParameter,
        temperature_k: float,
    ) -> float:
        if not (
            parameter.lower_temperature <= float(temperature_k)
            <= parameter.upper_temperature
        ):
            raise ValueError(
                f"Температура {float(temperature_k):.2f} K вне диапазона "
                f"DP-параметра {parameter.phase}: "
                f"{parameter.lower_temperature:.2f}–"
                f"{parameter.upper_temperature:.2f} K."
            )
        return self.expression(parameter.expression).evaluate(
            float(temperature_k),
            self.function_value,
        )

    # Фазы, из которых берётся плотность чистого элемента для оценки по правилу
    # смеси. Сначала твёрдые матрицы, затем прочие фазы с однокомпонентной
    # записью элемента (например DIAMOND_A4), жидкость — последней; берётся
    # первая, где у элемента есть собственный конечный член.
    ELEMENT_DENSITY_PHASES = ("FCC_A1", "BCC_A2", "HCP_A3")
    ELEMENT_DENSITY_LAST_PHASE = "LIQUID"

    # BL-47: эталонная фаза элемента из записи ELEMENT термодинамической базы
    # пробуется первой. Имена, которые в PDB записаны иначе; имя без модели в
    # PDB (например BCC_A12) эталонной фазы не даёт — остаётся прежний порядок.
    _REFERENCE_PHASE_NAMES = {"DIA_A4": "DIAMOND_A4", "DIAMOND_A4": "DIAMOND_A4"}

    def reference_density_phase(self, reference_phase: str | None) -> str | None:
        """Фаза PDB, соответствующая эталонной фазе элемента, или ``None``."""

        name = str(reference_phase or "").upper()
        name = self._REFERENCE_PHASE_NAMES.get(name, name)
        return name if name and name in self.phases else None

    # Структура в имени D0-функции элемента и суффикс его DT-функции:
    # D0HCP_SC + DTSCHCP.
    _D0_STRUCTURE_TO_DT = {"FCC": "FCC", "BCC": "BCC", "HCP": "HCP", "DIAM": "DIAM"}

    def _own_element_parameters(
        self,
        phase: str,
        element: str,
    ) -> list[DensityParameter]:
        """Явные DP-записи чистого элемента в фазе, выраженные через его D0.

        Годится только запись, где элемент стоит в первой подрешётке, остальные
        подрешётки — вакансия или тот же элемент, и выражение ссылается на
        D0-функцию самого элемента. Запись-умолчание ``DP(фаза,*)`` сюда не
        попадает: в этой базе она задаёт плотность железа, и подставлять её
        вместо плотности элемента нельзя (BL-39). По той же причине
        отбрасываются явные записи через чужую D0, например
        ``DP(DIAMOND_A4,B) = D0BCC_FE+…`` и ``DP(LIQUID,N) = D0DIAM_C+…``.
        """

        own_d0 = re.compile(rf"\bD0[A-Z]+_{re.escape(element)}\b")
        parameters = self.parameters_by_phase.get(phase, [])
        n_sublattices = _phase_sublattice_count(phase, parameters)
        selected: list[DensityParameter] = []
        for parameter in parameters:
            array = parameter.constituent_array
            if parameter.is_interaction or len(array) != n_sublattices:
                continue
            if array[0] != (element,):
                continue
            if any(group not in {("VA",), (element,)} for group in array[1:]):
                continue
            if not own_d0.search(parameter.expression.upper()):
                continue
            selected.append(parameter)
        return selected

    def element_density_model(
        self,
        element: str,
        temperature_k: float,
        reference_phase: str | None = None,
    ) -> tuple[float, str, str] | None:
        """Плотность чистого элемента и откуда она взята.

        Возвращает ``(плотность, вид, модель)`` или ``None``, если в физической
        базе плотности элемента нет ни в каком виде. ``reference_phase`` —
        эталонная фаза элемента из записи ELEMENT термодинамической базы; если
        у неё есть модель в PDB, она пробуется первой (BL-47). Вид:

        * ``matrix`` — собственная запись элемента в FCC_A1;
        * ``reference`` — собственная запись элемента в его эталонной фазе
          (кроме FCC_A1: там вид прежний, ``matrix``). ``matrix`` и
          ``reference`` — один главный путь, примечания у них нет (18-А);
        * ``phase`` — собственная запись элемента в другой фазе базы;
        * ``function`` — только D0-функция элемента (плюс его DT-функция, если
          она есть в базе).

        Плотность другого элемента (матрицы) вместо искомого не подставляется
        ни при каких условиях (BL-39).
        """

        element = str(element).upper()
        if element in {"VA", ""}:
            return None
        others = sorted(
            phase
            for phase in self.phases
            if phase not in self.ELEMENT_DENSITY_PHASES
            and phase != self.ELEMENT_DENSITY_LAST_PHASE
        )
        order = [
            *self.ELEMENT_DENSITY_PHASES,
            *others,
            self.ELEMENT_DENSITY_LAST_PHASE,
        ]
        reference = self.reference_density_phase(reference_phase)
        if reference is not None:
            order = [reference, *(phase for phase in order if phase != reference)]
        for phase in order:
            for parameter in self._own_element_parameters(phase, element):
                site_fractions = [
                    {group[0]: 1.0} for group in parameter.constituent_array
                ]
                try:
                    value, coverage, _warnings = self.density_from_site_fractions(
                        phase, site_fractions, temperature_k
                    )
                except Exception:
                    continue
                if value is not None and coverage > 0.999 and value > 0.0:
                    array = ":".join(
                        ",".join(group) for group in parameter.constituent_array
                    )
                    if phase == "FCC_A1":
                        kind = "matrix"
                    elif phase == reference:
                        kind = "reference"
                    else:
                        kind = "phase"
                    return float(value), kind, f"DP({phase},{array})"

        # Записей нет — остаётся D0-функция элемента (плотность при 298,15 K).
        pattern = re.compile(rf"D0([A-Z]+)_{re.escape(element)}")
        for name in sorted(self.functions):
            match = pattern.fullmatch(name)
            if match is None:
                continue
            dt_suffix = self._D0_STRUCTURE_TO_DT.get(match.group(1))
            dt_name = f"DT{element}{dt_suffix}" if dt_suffix else None
            try:
                value = self.function_value(name, temperature_k)
                label = name
                if dt_name and dt_name in self.functions:
                    value += self.function_value(dt_name, temperature_k)
                    label = f"{name}+{dt_name}"
            except Exception:
                continue
            if math.isfinite(value) and value > 0.0:
                return float(value), "function", label
        return None

    def element_density(
        self,
        element: str,
        temperature_k: float,
        reference_phase: str | None = None,
    ) -> float | None:
        """Плотность чистого элемента по модели PDB этого элемента."""

        model = self.element_density_model(element, temperature_k, reference_phase)
        return None if model is None else model[0]

    def element_density_note(
        self,
        element: str,
        temperature_k: float,
        reference_phase: str | None = None,
    ) -> str | None:
        """Текст для пользователя: по какой модели взята плотность элемента.

        Для собственной записи элемента в FCC_A1 или в его эталонной фазе
        текста нет — это основной путь правила смеси; текст есть только у
        обходных путей (``phase`` не по эталону и ``function``). Для элемента без плотности в базе — тоже ``None``:
        об этом говорит :func:`mixture_unavailable_message`.
        """

        element = str(element).upper()
        model = self.element_density_model(element, temperature_k, reference_phase)
        if model is None:
            return None
        _value, kind, label = model
        if kind in {"matrix", "reference"}:
            return None
        if element == "C" and label.startswith("DP(DIAMOND_A4,"):
            return (
                "Объём углерода — по алмазной модели базы "
                f"({label}); для графита это завышение плотности."
            )
        if kind == "phase":
            return (
                f"Плотность элемента {element} в правиле смеси взята по "
                f"модели {label} физической базы."
            )
        if "+" in label:
            return (
                f"Плотность элемента {element} в правиле смеси взята по "
                f"функциям {label} физической базы: модели фазы для него в "
                "базе нет."
            )
        return (
            f"Плотность элемента {element} в правиле смеси взята по функции "
            f"{label} физической базы — это плотность при 298,15 K; теплового "
            "расширения этого элемента в базе нет, и при других температурах "
            "оно не учтено; при рабочих температурах ошибка объёма может "
            "превышать 10 %."
        )

    def estimate_density_by_mixture(
        self,
        composition: Mapping[str, float],
        temperature_k: float,
        atomic_masses: Mapping[str, float] | None = None,
        reference_phases: Mapping[str, str] | None = None,
    ) -> tuple[float | None, float, list[str]]:
        """Плотность фазы по правилу смеси из плотностей элементов.

        Используется там, где собственной DP-модели у фазы нет. Аддитивен
        объём, поэтому смешение идёт по массе: ``1/ρ = Σ wᵢ/ρᵢ``. Оценка грубая
        — она не знает ни структуры фазы, ни объёмного эффекта образования, —
        и вызывающая сторона обязана пометить результат как оценочный.

        Если плотности или массы хотя бы одного элемента фазы нет, оценки нет:
        объём такой фазы не выдумывается (BL-39). ``atomic_masses`` — массы из
        термодинамической базы для элементов, которых нет в
        ``_ATOMIC_MASSES``. ``reference_phases`` — эталонные фазы элементов из
        записей ELEMENT той же базы (BL-47), см. :func:`element_reference_phases`.

        Возвращает ``(плотность, покрытие по массе, предупреждения)``.
        """

        masses: dict[str, float] = {}
        unknown: list[str] = []
        for element, fraction in composition.items():
            name = str(element).upper()
            if name in {"VA", ""} or not np.isfinite(fraction) or fraction <= 0.0:
                continue
            atomic_mass = _ATOMIC_MASSES.get(name)
            if not atomic_mass and atomic_masses:
                atomic_mass = atomic_masses.get(name)
            if not atomic_mass:
                unknown.append(name)
                continue
            masses[name] = float(fraction) * float(atomic_mass)
        total_mass = sum(masses.values())
        if total_mass <= 0.0:
            return None, 0.0, ["Состав фазы пуст: оценка невозможна."]

        volume = 0.0
        covered_mass = 0.0
        for element, mass in masses.items():
            density = self.element_density(
                element, temperature_k, (reference_phases or {}).get(element)
            )
            if density is None or density <= 0.0:
                unknown.append(element)
                continue
            volume += mass / density
            covered_mass += mass

        coverage = covered_mass / total_mass
        warnings: list[str] = []
        if unknown:
            warnings.append(
                "Нет плотности элементов: " + ", ".join(sorted(unknown))
            )
            return None, coverage, warnings
        if volume <= 0.0 or coverage < 0.9:
            return None, coverage, warnings
        return covered_mass / volume, coverage, warnings

    def mixture_missing_elements(
        self,
        composition: Mapping[str, float],
        temperature_k: float,
        reference_phases: Mapping[str, str] | None = None,
    ) -> list[str]:
        """Элементы фазы, плотности которых в физической базе нет."""

        references = reference_phases or {}
        return sorted(
            {
                str(element).upper()
                for element, fraction in composition.items()
                if str(element).upper() not in {"VA", ""}
                and np.isfinite(fraction)
                and fraction > 0.0
                and self.element_density(
                    element, temperature_k, references.get(str(element).upper())
                ) is None
            }
        )

    def mixture_element_notes(
        self,
        composition: Mapping[str, float],
        temperature_k: float,
        reference_phases: Mapping[str, str] | None = None,
    ) -> list[str]:
        """Тексты о моделях плотности элементов фазы, кроме основного пути."""

        notes: list[str] = []
        for element in sorted(
            str(name).upper()
            for name, fraction in composition.items()
            if str(name).upper() not in {"VA", ""}
            and np.isfinite(fraction)
            and fraction > 0.0
        ):
            note = self.element_density_note(
                element, temperature_k, (reference_phases or {}).get(element)
            )
            if note and note not in notes:
                notes.append(note)
        return notes

    def resolve_phase(self, thermodynamic_db: Any, phase_name: str) -> PhaseModelResolution:
        phase_name = str(phase_name).upper()
        if phase_name in self.phases:
            return PhaseModelResolution(
                requested_phase=phase_name,
                physical_phase=phase_name,
                quality="direct",
                note="Прямая DP-модель из physical_data.pdb.",
            )

        phase_obj = getattr(thermodynamic_db, "phases", {}).get(phase_name)
        if phase_obj is not None:
            disordered = str(
                phase_obj.model_hints.get("disordered_phase", "")
            ).upper()
            if disordered and disordered != phase_name and disordered in self.phases:
                return PhaseModelResolution(
                    requested_phase=phase_name,
                    physical_phase=disordered,
                    quality="inherited",
                    note=(
                        f"Упорядоченная фаза использует плотность связанной "
                        f"разупорядоченной фазы {disordered}."
                    ),
                )

        if phase_name in PHASE_ALIASES:
            physical_phase, quality, note = PHASE_ALIASES[phase_name]
            if physical_phase in self.phases:
                return PhaseModelResolution(
                    requested_phase=phase_name,
                    physical_phase=physical_phase,
                    quality=quality,
                    note=note,
                )

        return PhaseModelResolution(
            requested_phase=phase_name,
            physical_phase=None,
            quality="missing",
            note="В physical_data.pdb нет модели плотности для этой фазы.",
        )

    def density_from_site_fractions(
        self,
        physical_phase: str,
        site_fractions: list[dict[str, float]],
        temperature_k: float,
    ) -> tuple[float | None, float, list[str]]:
        """Evaluate a DP phase model.

        Returns ``(density_kg_m3, endmember_coverage, warnings)``.
        ``endmember_coverage`` is the sum of products of site fractions for
        endmembers that found an explicit or fallback PDB parameter.
        """
        physical_phase = physical_phase.upper()
        parameters = self.parameters_by_phase.get(physical_phase, [])
        if not parameters:
            return None, 0.0, ["DP-параметры отсутствуют."]

        n_sublattices = _phase_sublattice_count(physical_phase, parameters)
        if len(site_fractions) != n_sublattices:
            return (
                None,
                0.0,
                [
                    "Число подрешёток не совпало: "
                    f"ожидалось {n_sublattices}, получено {len(site_fractions)}."
                ],
            )

        normalized_y: list[dict[str, float]] = []
        for sublattice in site_fractions:
            values = {
                str(species).upper(): max(0.0, float(value))
                for species, value in sublattice.items()
                if np.isfinite(value) and float(value) > 1e-14
            }
            total = sum(values.values())
            if total <= 0:
                return None, 0.0, ["Пустая подрешётка в расчётной точке."]
            normalized_y.append(
                {species: value / total for species, value in values.items()}
            )

        pure_parameters = [
            parameter
            for parameter in parameters
            if not parameter.is_interaction
        ]
        interaction_parameters = [
            parameter
            for parameter in parameters
            if parameter.is_interaction
        ]

        density = 0.0
        mass_sum = 0.0
        volume_sum = 0.0
        covered_weight = 0.0
        missing_endmembers: list[str] = []

        constituent_lists = [
            list(sublattice.keys())
            for sublattice in normalized_y
        ]

        for endmember in product(*constituent_lists):
            weight = math.prod(
                normalized_y[index][species]
                for index, species in enumerate(endmember)
            )
            if weight <= 1e-14:
                continue

            candidates: list[tuple[int, int, DensityParameter]] = []
            for parameter_index, parameter in enumerate(pure_parameters):
                pattern, global_default = _normalized_pattern(
                    physical_phase,
                    parameter.constituent_array,
                    n_sublattices,
                )
                if global_default:
                    candidates.append((0, parameter_index, parameter))
                    continue
                if pattern is None:
                    continue
                if all(
                    pattern[index][0] in {"*", endmember[index]}
                    for index in range(n_sublattices)
                ):
                    specificity = sum(
                        pattern[index][0] != "*"
                        for index in range(n_sublattices)
                    )
                    candidates.append((specificity, parameter_index, parameter))

            if not candidates:
                missing_endmembers.append(":".join(endmember))
                continue

            # Most specific parameter wins. Later duplicates win, matching the
            # usual "last assessment" convention in text databases.
            _specificity, _index, selected = max(candidates)
            value = self.parameter_value(selected, temperature_k)
            if not math.isfinite(value) or value <= 0.0:
                missing_endmembers.append(":".join(endmember))
                continue
            # Плотности не аддитивны — аддитивны объёмы. Правильное смешение
            # конечных членов: 1/ρ = Σ wᵢ/ρᵢ по массовым долям, что для
            # мольных долей ``weight`` записывается как
            # ρ = Σ wᵢMᵢ / Σ (wᵢMᵢ/ρᵢ). Прежняя формула ρ = Σ wᵢρᵢ завышала
            # плотность тем сильнее, чем больше разброс плотностей
            # составляющих.
            endmember_mass = sum(
                _ATOMIC_MASSES.get(species, 0.0) for species in endmember
            )
            if endmember_mass <= 0.0:
                missing_endmembers.append(":".join(endmember))
                continue
            mass_sum += weight * endmember_mass
            volume_sum += weight * endmember_mass / value
            covered_weight += weight

        # Собранная по объёмам плотность конечных членов.
        density = mass_sum / volume_sum if volume_sum > 0.0 else 0.0

        # Add explicit binary interaction terms (Redlich-Kister form).
        interaction_density = 0.0
        for parameter in interaction_parameters:
            pattern, global_default = _normalized_pattern(
                physical_phase,
                parameter.constituent_array,
                n_sublattices,
            )
            if global_default or pattern is None:
                continue

            multiplier = 1.0
            valid = True
            for sublattice_index, species_group in enumerate(pattern):
                y = normalized_y[sublattice_index]
                if species_group == ("*",):
                    multiplier *= sum(y.values())
                elif len(species_group) == 1:
                    species = species_group[0]
                    if species not in y:
                        valid = False
                        break
                    multiplier *= y[species]
                elif len(species_group) == 2:
                    first, second = species_group
                    if first not in y or second not in y:
                        valid = False
                        break
                    multiplier *= (
                        y[first]
                        * y[second]
                        * (y[first] - y[second]) ** parameter.order
                    )
                else:
                    valid = False
                    break

            if valid and abs(multiplier) > 1e-18:
                interaction_density += multiplier * self.parameter_value(
                    parameter,
                    temperature_k,
                )

        density += interaction_density

        warnings: list[str] = []
        if missing_endmembers:
            preview = ", ".join(missing_endmembers[:6])
            suffix = "…" if len(missing_endmembers) > 6 else ""
            warnings.append(
                "Не покрыты эндмемберы: " + preview + suffix
            )

        if covered_weight < 0.999999:
            warnings.append(
                "Покрытие эндмемберов модели: "
                f"{100.0 * covered_weight:.3f} %."
            )

        if covered_weight <= 1e-12:
            return None, covered_weight, warnings

        # Do not silently renormalize a materially incomplete model.
        if covered_weight < 0.999:
            return None, covered_weight, warnings

        if not math.isfinite(density) or density <= 0:
            warnings.append("DP-модель вернула неположительную плотность.")
            return None, covered_weight, warnings

        return float(density), float(covered_weight), warnings

    def self_test(self) -> pd.DataFrame:
        """Run parser and pure-endmember checks independent of CALPHAD DBs."""
        tests = [
            ("FCC_A1", [{"AL": 1.0}, {"VA": 1.0}], "Al, FCC", 2698.15),
            ("BCC_A2", [{"FE": 1.0}, {"VA": 1.0}], "Fe, BCC", 7874.0),
            ("FCC_A1", [{"NI": 1.0}, {"VA": 1.0}], "Ni, FCC", 8914.0),
            ("LIQUID", [{"AL": 1.0}], "Al, liquid model", None),
            ("CEMENTITE", [{"FE": 1.0}, {"C": 1.0}], "Fe3C", 7685.0),
        ]
        rows: list[dict[str, Any]] = []
        for phase, site_fractions, label, reference in tests:
            density, coverage, warnings = self.density_from_site_fractions(
                phase,
                site_fractions,
                REFERENCE_TEMPERATURE_K,
            )
            passed = density is not None and coverage > 0.999
            if reference is not None and density is not None:
                # Polynomial thermal corrections are not exactly zero at 298.15 K.
                passed = passed and abs(density - reference) < 5.0
            rows.append(
                {
                    "Проверка": label,
                    "Фаза": phase,
                    "Плотность, кг/м³": density,
                    "Покрытие, %": 100.0 * coverage,
                    "Ожидалось около, кг/м³": reference,
                    "Статус": "пройдена" if passed else "ошибка",
                    "Примечание": "; ".join(warnings),
                }
            )
        return pd.DataFrame(rows)


MIXTURE_UNAVAILABLE_TEMPLATE = (
    "Объём фазы {phase} не оценён: в физической базе нет плотности "
    "{noun} {elements}."
)


def mixture_unavailable_message(phase: str, elements: Iterable[str]) -> str:
    """Текст о фазе, выпавшей из покрытия: плотности элемента в базе нет."""

    names = sorted({str(element).upper() for element in elements})
    return MIXTURE_UNAVAILABLE_TEMPLATE.format(
        phase=phase,
        noun="элемента" if len(names) == 1 else "элементов",
        elements=", ".join(names),
    )


def _refstate_masses(
    thermodynamic_db: Any,
    composition: Mapping[str, float],
) -> dict[str, float]:
    """Атомные массы из термодинамической базы для элементов вне ``_ATOMIC_MASSES``."""

    refstates = getattr(thermodynamic_db, "refstates", None) or {}
    masses: dict[str, float] = {}
    for element in composition:
        name = str(element).upper()
        if name in _ATOMIC_MASSES:
            continue
        try:
            mass = float(refstates[name]["mass"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(mass) and mass > 0.0:
            masses[name] = mass
    return masses


def element_reference_phases(thermodynamic_db: Any) -> dict[str, str]:
    """Эталонные фазы элементов из записей ELEMENT термодинамической базы (BL-47)."""

    refstates = getattr(thermodynamic_db, "refstates", None) or {}
    phases: dict[str, str] = {}
    for element, record in refstates.items():
        try:
            phase = str(record["phase"]).strip().upper()
        except (KeyError, TypeError):
            continue
        if phase:
            phases[str(element).upper()] = phase
    return phases


def calculate_physical_properties(
    thermodynamic_db: Any,
    equilibrium_result: Any,
    components: list[str],
    temperature_k: float,
    physical_db: PhysicalDensityDatabase,
) -> PhysicalCalculationResult:
    """Calculate phase densities, mass fractions and volume fractions."""
    phase_names = np.asarray(
        equilibrium_result.Phase.values,
        dtype=str,
    ).ravel()
    phase_amounts = np.asarray(
        equilibrium_result.NP.values,
        dtype=float,
    ).ravel()

    y_values = np.asarray(equilibrium_result.Y.values, dtype=float)
    if y_values.ndim == 0:
        y_rows = np.empty((len(phase_names), 0), dtype=float)
    else:
        y_rows = y_values.reshape((-1, y_values.shape[-1]))

    real_components = [
        str(component).upper()
        for component in components
        if str(component).upper() != "VA"
    ]
    phase_x = {
        component: np.asarray(
            equilibrium_result.X.sel(component=component).values,
            dtype=float,
        ).ravel()
        for component in real_components
    }

    aggregates: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "phase_amount": 0.0,
            "mass": 0.0,
            "volume": 0.0,
            "covered_amount": 0.0,
            "covered_mass": 0.0,
            "direct_amount": 0.0,
            "inherited_amount": 0.0,
            "estimated_amount": 0.0,
            "physical_phases": set(),
            "qualities": set(),
            "notes": set(),
            "warnings": set(),
            "molar_mass_weighted": 0.0,
        }
    )

    total_mass = 0.0
    total_phase_amount = 0.0
    covered_phase_amount = 0.0
    direct_phase_amount = 0.0
    inherited_phase_amount = 0.0
    estimated_phase_amount = 0.0
    covered_mass = 0.0
    covered_volume = 0.0
    # BL-39: какие модели плотности элементов взяты в правиле смеси и какие
    # фазы выпали, потому что плотности элемента в базе нет.
    element_notes: list[str] = []
    unavailable_notes: list[str] = []
    reference_phases = element_reference_phases(thermodynamic_db)

    for index, (phase_name, phase_amount) in enumerate(
        zip(phase_names, phase_amounts)
    ):
        if (
            phase_name == ""
            or not np.isfinite(phase_amount)
            or float(phase_amount) <= 1e-10
        ):
            continue

        phase_name = str(phase_name).upper()
        phase_amount = float(phase_amount)
        composition = _normalized_phase_composition(
            phase_x,
            index,
        )
        molar_mass_kg_mol = _average_molar_mass_kg_mol(
            thermodynamic_db,
            composition,
        )
        phase_mass = phase_amount * molar_mass_kg_mol

        total_phase_amount += phase_amount
        total_mass += phase_mass

        resolution = physical_db.resolve_phase(
            thermodynamic_db,
            phase_name,
        )

        aggregate = aggregates[phase_name]
        aggregate["phase_amount"] += phase_amount
        aggregate["mass"] += phase_mass
        aggregate["molar_mass_weighted"] += (
            phase_amount * molar_mass_kg_mol
        )
        aggregate["qualities"].add(resolution.quality)
        aggregate["notes"].add(resolution.note)

        if resolution.physical_phase is None:
            # Своей DP-модели нет. Молчать нельзя: на контрольном никелевом
            # составе всегда есть хотя бы MnS, и из-за одной непокрытой фазы
            # плотность сплава не выдавалась вовсе. Берём оценку по правилу
            # смеси и помечаем её как оценочную.
            estimate, estimate_coverage, estimate_warnings = (
                physical_db.estimate_density_by_mixture(
                    composition,
                    temperature_k,
                    _refstate_masses(thermodynamic_db, composition),
                    reference_phases,
                )
            )
            for warning in estimate_warnings:
                aggregate["warnings"].add(warning)
            if estimate is None or estimate <= 0.0:
                missing_elements = physical_db.mixture_missing_elements(
                    composition, temperature_k, reference_phases
                )
                if missing_elements:
                    unavailable_notes.append(
                        mixture_unavailable_message(phase_name, missing_elements)
                    )
                continue
            for note in physical_db.mixture_element_notes(
                composition, temperature_k, reference_phases
            ):
                element_notes.append(note)
            aggregate["qualities"].add("mixture")
            aggregate["notes"].add(
                "Плотность оценена по правилу смеси из плотностей элементов; "
                "погрешность до 10 %."
            )
            phase_volume = phase_mass / estimate
            aggregate["volume"] += phase_volume
            aggregate["covered_amount"] += phase_amount
            aggregate["covered_mass"] += phase_mass
            aggregate["estimated_amount"] += phase_amount
            covered_phase_amount += phase_amount
            covered_mass += phase_mass
            covered_volume += phase_volume
            estimated_phase_amount += phase_amount
            del estimate_coverage
            continue

        aggregate["physical_phases"].add(resolution.physical_phase)

        site_fractions: list[dict[str, float]] | None = None
        if resolution.quality == "direct" and resolution.physical_phase == phase_name:
            try:
                site_fractions = _site_fractions_from_equilibrium(
                    thermodynamic_db,
                    components,
                    phase_name,
                    y_rows[index],
                )
                expected = _phase_sublattice_count(
                    resolution.physical_phase,
                    physical_db.parameters_by_phase[resolution.physical_phase],
                )
                if len(site_fractions) != expected:
                    site_fractions = None
            except Exception as error:
                aggregate["warnings"].add(
                    "Не удалось прочитать подрешётки: " + str(error)
                )
                site_fractions = None

        if site_fractions is None:
            site_fractions = _site_fractions_from_composition(
                thermodynamic_db,
                resolution.physical_phase,
                composition,
                physical_db,
            )

        if site_fractions is None:
            aggregate["warnings"].add(
                "Не удалось восстановить подрешёточный состав для DP-модели."
            )
            continue

        density, endmember_coverage, density_warnings = (
            physical_db.density_from_site_fractions(
                resolution.physical_phase,
                site_fractions,
                temperature_k,
            )
        )
        for warning in density_warnings:
            aggregate["warnings"].add(warning)

        if density is None:
            continue

        phase_volume = phase_mass / density
        aggregate["volume"] += phase_volume
        aggregate["covered_amount"] += phase_amount
        aggregate["covered_mass"] += phase_mass

        covered_phase_amount += phase_amount
        covered_mass += phase_mass
        covered_volume += phase_volume

        if resolution.quality == "direct":
            aggregate["direct_amount"] += phase_amount
            direct_phase_amount += phase_amount
        else:
            aggregate["inherited_amount"] += phase_amount
            inherited_phase_amount += phase_amount

    rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []

    full_volume_available = (
        total_phase_amount > 0
        and covered_phase_amount / total_phase_amount >= 0.999999
        and total_mass > 0
        and covered_volume > 0
    )

    for phase_name, values in aggregates.items():
        phase_amount = float(values["phase_amount"])
        phase_mass = float(values["mass"])
        phase_volume = float(values["volume"])
        covered_amount = float(values["covered_amount"])
        covered_phase_mass = float(values["covered_mass"])
        density = (
            covered_phase_mass / phase_volume
            if phase_volume > 0 and covered_phase_mass > 0
            else None
        )
        molar_mass = (
            float(values["molar_mass_weighted"]) / phase_amount
            if phase_amount > 0
            else None
        )
        molar_volume_cm3 = (
            phase_volume / covered_amount * 1e6
            if phase_volume > 0 and covered_amount > 0
            else None
        )
        mass_fraction = (
            100.0 * phase_mass / total_mass
            if total_mass > 0
            else None
        )
        if full_volume_available and phase_volume > 0:
            volume_fraction = 100.0 * phase_volume / covered_volume
            conditional_volume_fraction = volume_fraction
        elif phase_volume > 0 and covered_volume > 0:
            volume_fraction = None
            conditional_volume_fraction = 100.0 * phase_volume / covered_volume
        else:
            volume_fraction = None
            conditional_volume_fraction = None

        qualities = set(values["qualities"])
        if covered_amount <= 0:
            status = "нет данных"
        elif qualities == {"direct"}:
            status = "прямая модель"
        elif "mixture" in qualities:
            status = "оценка по правилу смеси"
        elif "inherited" in qualities or "structural" in qualities:
            status = "оценка по связанной фазе"
        else:
            status = ", ".join(sorted(qualities))

        row = {
            "Фаза": phase_name,
            "Мольная доля, %": 100.0 * phase_amount,
            "Массовая доля, %": mass_fraction,
            "Объёмная доля, %": volume_fraction,
            "Объёмная доля среди покрытых, %": conditional_volume_fraction,
            "Плотность фазы, кг/м³": density,
            "Плотность фазы, г/см³": density / 1000.0 if density else None,
            "Молярный объём, см³/моль атомов": molar_volume_cm3,
            "Средняя молярная масса, г/моль атомов": (
                molar_mass * 1000.0 if molar_mass is not None else None
            ),
            "Модель плотности": ", ".join(sorted(values["physical_phases"])),
            "Статус данных": status,
            "Примечание": " ".join(sorted(values["notes"])),
            "Диагностика": "; ".join(sorted(values["warnings"])),
        }
        rows.append(row)

        if covered_amount <= 0:
            missing_rows.append(
                {
                    "Фаза": phase_name,
                    "Мольная доля, %": 100.0 * phase_amount,
                    "Массовая доля, %": mass_fraction,
                    "Причина": " ".join(sorted(values["notes"])),
                    "Диагностика": "; ".join(sorted(values["warnings"])),
                }
            )

    phase_table = pd.DataFrame(rows)
    if not phase_table.empty:
        phase_table = phase_table.sort_values(
            "Мольная доля, %",
            ascending=False,
        ).reset_index(drop=True)

    missing_table = pd.DataFrame(missing_rows)
    if not missing_table.empty:
        missing_table = missing_table.sort_values(
            "Мольная доля, %",
            ascending=False,
        ).reset_index(drop=True)

    mole_coverage = (
        100.0 * covered_phase_amount / total_phase_amount
        if total_phase_amount > 0
        else 0.0
    )
    mass_coverage = (
        100.0 * covered_mass / total_mass
        if total_mass > 0
        else 0.0
    )
    direct_mole = (
        100.0 * direct_phase_amount / total_phase_amount
        if total_phase_amount > 0
        else 0.0
    )
    inherited_mole = (
        100.0 * inherited_phase_amount / total_phase_amount
        if total_phase_amount > 0
        else 0.0
    )

    estimated_share = (
        100.0 * estimated_phase_amount / total_phase_amount
        if total_phase_amount > 0
        else 0.0
    )

    if full_volume_available:
        alloy_density = total_mass / covered_volume
        if estimated_phase_amount > 1e-8:
            quality_label = (
                "с оценкой по правилу смеси для "
                f"{estimated_share:.2f} % мольной доли фаз"
            )
        elif inherited_phase_amount > 1e-8:
            quality_label = "оценочная: есть плотности связанных фаз"
        else:
            quality_label = "полная по доступным прямым DP-моделям"
    else:
        alloy_density = None
        quality_label = "неполная: не все равновесные фазы обеспечены плотностью"

    warnings: list[str] = []
    # Наши правки поверх физической базы обязаны быть названы прямо в
    # результате расчёта: молча подменять данные источника нельзя. Поэтому
    # сообщение идёт первым, до всех прочих предупреждений.
    warnings.extend(getattr(physical_db, "override_notes", ()) or ())
    if estimated_phase_amount > 1e-8:
        estimated_names = sorted(
            name
            for name, values in aggregates.items()
            if float(values["estimated_amount"]) > 1e-12
        )
        if estimated_share < 1.0:
            # Меньше процента мольной доли — на плотность сплава такие фазы
            # практически не влияют. Говорим об этом прямо, а не пугаем.
            warnings.append(
                "Плотность фаз " + ", ".join(estimated_names)
                + " оценена по правилу смеси; их суммарная мольная доля "
                f"{estimated_share:.2f} % — влияние на плотность сплава "
                "пренебрежимо."
            )
        else:
            warnings.append(
                "Плотность фаз " + ", ".join(estimated_names)
                + " оценена по правилу смеси; погрешность до 10 %. "
                f"Суммарная мольная доля таких фаз {estimated_share:.2f} %."
            )
    for note in element_notes:
        if note not in warnings:
            warnings.append(note)
    if not missing_table.empty:
        warnings.append(
            "Для части равновесных фаз нет физической модели; общая плотность "
            "сплава и полные объёмные доли не выводятся."
        )
    for note in unavailable_notes:
        if note not in warnings:
            warnings.append(note)
    if inherited_phase_amount > 1e-8:
        warnings.append(
            "Для упорядоченных или структурно родственных фаз использованы "
            "плотности связанных базовых моделей; такие значения являются оценочными."
        )
    if mole_coverage < 99.999 and covered_volume > 0:
        warnings.append(
            "Колонка «объёмная доля среди покрытых» нормирована только по фазам "
            "с доступной плотностью и не является полной объёмной долей сплава."
        )

    return PhysicalCalculationResult(
        phase_table=phase_table,
        missing_table=missing_table,
        estimated_mole_pct=float(estimated_share),
        alloy_density_kg_m3=float(alloy_density) if alloy_density else None,
        alloy_density_g_cm3=(
            float(alloy_density) / 1000.0 if alloy_density else None
        ),
        mole_coverage_pct=float(mole_coverage),
        mass_coverage_pct=float(mass_coverage),
        direct_mole_pct=float(direct_mole),
        inherited_mole_pct=float(inherited_mole),
        quality_label=quality_label,
        warnings=warnings,
        physical_database_sha256=physical_db.sha256,
        physical_database_version=PHYSICAL_DATABASE_VERSION,
        element_density_notes=list(dict.fromkeys(element_notes)),
    )


def physical_coverage_dataframe(
    thermodynamic_db: Any,
    physical_db: PhysicalDensityDatabase,
    phase_explanations: dict[str, str] | None = None,
) -> pd.DataFrame:
    phase_explanations = phase_explanations or {}
    rows: list[dict[str, Any]] = []
    for phase_name in sorted(thermodynamic_db.phases):
        resolution = physical_db.resolve_phase(thermodynamic_db, phase_name)
        if resolution.quality == "direct":
            status = "прямая модель"
        elif resolution.quality in {"inherited", "structural"}:
            status = "оценка по связанной фазе"
        else:
            status = "нет данных"
        rows.append(
            {
                "Фаза": phase_name,
                "Что это": phase_explanations.get(phase_name, ""),
                "Статус плотности": status,
                "Используемая модель": resolution.physical_phase or "",
                "Примечание": resolution.note,
            }
        )
    return pd.DataFrame(rows)


def _active_commands(text: str) -> list[str]:
    commands: list[str] = []
    buffer = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("$"):
            continue
        buffer += (" " if buffer else "") + line
        while "!" in buffer:
            command, buffer = buffer.split("!", 1)
            command = command.strip()
            if command:
                commands.append(command)
            buffer = buffer.strip()
    return commands


def _normalize_expression(expression: str) -> str:
    # The source has one decimal comma: +120,331 in DTMNBCC.
    expression = re.sub(r"(?<=\d),(?=\d)", ".", expression)
    return expression.strip()


def _parse_function(command: str) -> FunctionDefinition:
    match = re.match(
        r"FUNCTION\s+(\S+)\s+([+\-0-9.Ee]+)\s+(.+?)\s*;\s*"
        r"([+\-0-9.Ee]+)\s+[NY]\b",
        command,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise ValueError("Не удалось разобрать FUNCTION: " + command)
    name, lower, expression, upper = match.groups()
    return FunctionDefinition(
        name=name.upper(),
        lower_temperature=float(lower),
        expression=_normalize_expression(expression),
        upper_temperature=float(upper),
    )


def _parse_density_parameter(command: str) -> DensityParameter:
    start = command.upper().index("DP(") + 3
    depth = 1
    end = start
    while end < len(command) and depth:
        if command[end] == "(":
            depth += 1
        elif command[end] == ")":
            depth -= 1
            if depth == 0:
                break
        end += 1
    signature = command[start:end]
    tail = command[end + 1 :].strip()
    match = re.match(
        r"([+\-0-9.Ee]+)\s+(.+?)\s*;\s*([+\-0-9.Ee]+)\s+[NY]\b",
        tail,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise ValueError("Не удалось разобрать PARAMETER DP: " + command)
    lower, expression, upper = match.groups()
    phase, constituent_text = signature.split(",", 1)
    order = 0
    if ";" in constituent_text:
        constituent_text, order_text = constituent_text.rsplit(";", 1)
        order = int(order_text.strip())
    constituent_array = tuple(
        tuple(item.strip().upper() for item in sublattice.split(","))
        for sublattice in constituent_text.split(":")
    )
    return DensityParameter(
        phase=phase.strip().upper(),
        constituent_array=constituent_array,
        order=order,
        lower_temperature=float(lower),
        expression=_normalize_expression(expression),
        upper_temperature=float(upper),
        raw_command=command,
    )


def _phase_sublattice_count(
    phase: str,
    parameters: Iterable[DensityParameter],
) -> int:
    maximum = max(
        (len(parameter.constituent_array) for parameter in parameters),
        default=1,
    )
    return int(maximum)


def _normalized_pattern(
    phase: str,
    constituent_array: tuple[tuple[str, ...], ...],
    n_sublattices: int,
) -> tuple[tuple[tuple[str, ...], ...] | None, bool]:
    if len(constituent_array) == n_sublattices:
        return constituent_array, False

    if constituent_array == (("*",),):
        if phase in MATRIX_PHASES and n_sublattices == 2:
            return (("*",), ("VA",)), False
        return None, True

    return None, False


def _site_fractions_from_equilibrium(
    thermodynamic_db: Any,
    components: list[str],
    phase_name: str,
    y_row: np.ndarray,
) -> list[dict[str, float]]:
    """Разложить строку ``Y`` равновесия по подрешёткам фазы.

    Вакансия обязана быть в списке компонентов модели. Равновесие всегда
    считается с ``VA``, поэтому строка ``Y`` содержит её долю; если же
    ``Model`` построить без ``VA``, среди его ``site_fractions`` вакансии не
    будет, доли сдвинутся по индексам, а межузельная подрешётка после
    нормировки выродится в чистый внедрённый элемент.

    Именно это и происходило на никелевом сплаве с углеродом: подрешётка
    ``(C,VA)`` с долей углерода 2,5·10⁻⁴ превращалась в ``(C)``, модель
    плотности считала карбидный конечный член, и плотность матрицы выходила
    4,9 г/см³ вместо 8,5. Вызывающая сторона обычно передаёт список элементов
    без вакансии, поэтому ``VA`` добавляется здесь.
    """

    from pycalphad import Model

    model_components = [str(name).upper() for name in components]
    if "VA" not in model_components:
        model_components.append("VA")

    model = Model(thermodynamic_db, model_components, phase_name)
    symbols = list(model.site_fractions)
    if len(symbols) > len(y_row):
        raise ValueError("В результате недостаточно внутренних степеней свободы.")

    result: list[dict[str, float]] = [
        {} for _ in range(len(model.constituents))
    ]
    for index, symbol in enumerate(symbols):
        value = float(y_row[index])
        if not np.isfinite(value):
            continue
        sublattice_index = int(symbol.sublattice_index)
        result[sublattice_index][symbol.species.name.upper()] = value

    normalized: list[dict[str, float]] = []
    for sublattice_index, sublattice in enumerate(result):
        expected = {
            str(species).upper()
            for species in model.constituents[sublattice_index]
        }
        missing = expected - set(sublattice)
        if missing:
            # Подрешётка разобрана не полностью — нормировать по неполному
            # набору нельзя, доли получатся завышенными. Пусть сработает
            # запасной путь по составу фазы.
            raise ValueError(
                "В Y-координатах нет составляющих подрешётки "
                f"{sublattice_index + 1}: {', '.join(sorted(missing))}."
            )
        total = sum(max(0.0, value) for value in sublattice.values())
        if total <= 0:
            raise ValueError("Пустая подрешётка в Y-координатах.")
        normalized.append(
            {
                species: max(0.0, value) / total
                for species, value in sublattice.items()
                if value > 1e-14
            }
        )
    return normalized


def _site_fractions_from_composition(
    thermodynamic_db: Any,
    physical_phase: str,
    composition: dict[str, float],
    physical_db: PhysicalDensityDatabase,
) -> list[dict[str, float]] | None:
    physical_phase = physical_phase.upper()
    parameters = physical_db.parameters_by_phase.get(physical_phase, [])
    if not parameters:
        return None
    n_sublattices = _phase_sublattice_count(physical_phase, parameters)

    if n_sublattices == 1:
        values = {
            element: fraction
            for element, fraction in composition.items()
            if fraction > 1e-14
        }
        total = sum(values.values())
        if total <= 0:
            return None
        return [{element: fraction / total for element, fraction in values.items()}]

    if physical_phase in MATRIX_PHASES and n_sublattices == 2:
        site_ratios = DEFAULT_MATRIX_SITE_RATIOS[physical_phase]
        phase_obj = getattr(thermodynamic_db, "phases", {}).get(physical_phase)
        if phase_obj is not None and len(phase_obj.sublattices) >= 2:
            try:
                site_ratios = (
                    float(phase_obj.sublattices[0]),
                    float(phase_obj.sublattices[1]),
                )
            except Exception:
                pass

        substitutional = {
            element: fraction
            for element, fraction in composition.items()
            if element not in INTERSTITIAL_NAMES and fraction > 1e-14
        }
        interstitial = {
            element: fraction
            for element, fraction in composition.items()
            if element in INTERSTITIAL_NAMES - {"VA"} and fraction > 1e-14
        }
        substitutional_total = sum(substitutional.values())
        if substitutional_total <= 0:
            return None

        first = {
            element: fraction / substitutional_total
            for element, fraction in substitutional.items()
        }

        r_sub, r_int = site_ratios
        atom_count = r_sub / substitutional_total
        second = {
            element: fraction * atom_count / r_int
            for element, fraction in interstitial.items()
        }
        occupied = sum(second.values())
        if occupied > 1.0 + 1e-6:
            return None
        second["VA"] = max(0.0, 1.0 - occupied)
        second_total = sum(second.values())
        if second_total <= 0:
            return None
        second = {
            element: fraction / second_total
            for element, fraction in second.items()
            if fraction > 1e-14
        }
        return [first, second]

    # Build allowed-species sets from explicit PDB endmembers. This handles
    # Laves and several carbide models. If the same metal can occupy multiple
    # sublattices, the same normalized phase composition is used on each; the
    # result is therefore marked as structural/inherited by the caller.
    allowed: list[set[str]] = [set() for _ in range(n_sublattices)]
    for parameter in parameters:
        pattern, global_default = _normalized_pattern(
            physical_phase,
            parameter.constituent_array,
            n_sublattices,
        )
        if global_default or pattern is None:
            continue
        for index, species_group in enumerate(pattern):
            for species in species_group:
                if species != "*":
                    allowed[index].add(species)

    result: list[dict[str, float]] = []
    for index, species_set in enumerate(allowed):
        if not species_set:
            # A global default makes the exact distribution irrelevant.
            result.append({"*": 1.0})
            continue
        values = {
            species: composition.get(species, 0.0)
            for species in species_set
            if composition.get(species, 0.0) > 1e-14
        }
        if not values:
            # Fixed C/N sublattices may have exact occupancy even when the
            # phase composition was rounded to zero in the flattened output.
            if species_set <= {"C", "N", "VA"}:
                preferred = "C" if "C" in species_set else sorted(species_set)[0]
                values = {preferred: 1.0}
            else:
                return None
        total = sum(values.values())
        result.append(
            {species: fraction / total for species, fraction in values.items()}
        )
    return result


def _normalized_phase_composition(
    phase_x: dict[str, np.ndarray],
    index: int,
) -> dict[str, float]:
    values = {
        component: float(array[index])
        for component, array in phase_x.items()
        if index < len(array)
        and np.isfinite(array[index])
        and float(array[index]) > 1e-14
    }
    total = sum(values.values())
    if total <= 0:
        return {}
    return {
        component: value / total
        for component, value in values.items()
    }


def _average_molar_mass_kg_mol(
    thermodynamic_db: Any,
    composition: dict[str, float],
) -> float:
    mass_g_mol = 0.0
    for element, fraction in composition.items():
        refstate = thermodynamic_db.refstates.get(element)
        if refstate is None:
            raise KeyError(f"Нет атомной массы для {element}.")
        mass_g_mol += float(fraction) * float(refstate["mass"])
    return mass_g_mol / 1000.0


def _file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
