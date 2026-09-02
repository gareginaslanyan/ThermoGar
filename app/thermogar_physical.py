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
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from pathlib import Path
import ast
import hashlib
import math
import re
from typing import Any, Iterable

import numpy as np
import pandas as pd


PHYSICAL_DATABASE_VERSION = "1.03"
REFERENCE_TEMPERATURE_K = 298.15

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
    quality_label: str
    warnings: list[str]
    physical_database_sha256: str
    physical_database_version: str


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


class PhysicalDensityDatabase:
    """Parsed MatCalc physical_data.pdb density model."""

    def __init__(self, source_path: str | Path):
        self.source_path = Path(source_path)
        if not self.source_path.exists():
            raise FileNotFoundError(
                "Не найдена физическая база: " + str(self.source_path)
            )
        self.sha256 = _file_sha256(self.source_path)
        self._initialize(
            self.source_path.read_text(encoding="utf-8", errors="replace")
        )

    @classmethod
    def from_verified_bytes(cls, data: bytes) -> "PhysicalDensityDatabase":
        """Parse one already-verified PDB snapshot without path authority."""

        if type(data) is not bytes:
            raise TypeError("Verified physical database snapshot must be bytes.")
        text = data.decode("utf-8", errors="strict")
        database = cls.__new__(cls)
        database.source_path = None
        database.sha256 = hashlib.sha256(data).hexdigest()
        database._initialize(text)
        return database

    def _initialize(self, text: str) -> None:
        self.functions: dict[str, FunctionDefinition] = {}
        self.parameters: list[DensityParameter] = []
        self.parameters_by_phase: dict[str, list[DensityParameter]] = defaultdict(list)
        self._expression_cache: dict[str, _SafeExpression] = {}
        self._function_value_cache: dict[tuple[str, float], float] = {}
        self._parse(text)

    @property
    def phases(self) -> set[str]:
        return set(self.parameters_by_phase)

    @property
    def direct_phase_models(self) -> list[str]:
        return sorted(self.parameters_by_phase)

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
            density += weight * value
            covered_weight += weight

        # Add explicit binary interaction terms (Redlich-Kister form).
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
                density += multiplier * self.parameter_value(
                    parameter,
                    temperature_k,
                )

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
    covered_mass = 0.0
    covered_volume = 0.0

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

    if full_volume_available:
        alloy_density = total_mass / covered_volume
        if inherited_phase_amount > 1e-8:
            quality_label = "оценочная: есть плотности связанных фаз"
        else:
            quality_label = "полная по доступным прямым DP-моделям"
    else:
        alloy_density = None
        quality_label = "неполная: не все равновесные фазы обеспечены плотностью"

    warnings: list[str] = []
    if not missing_table.empty:
        warnings.append(
            "Для части равновесных фаз нет физической модели; общая плотность "
            "сплава и полные объёмные доли не выводятся."
        )
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
    from pycalphad import Model

    model = Model(thermodynamic_db, components, phase_name)
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
    for sublattice in result:
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
