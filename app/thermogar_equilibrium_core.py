"""Pure, immutable equilibrium adapters and manufactured-oracle primitives.

The module contains no solver implementation.  A backend is injected through
the :class:`EquilibriumBackend` protocol and its raw phase rows are validated,
aggregated, and checked for phase balance and component conservation before an
answer is returned.  The remaining helpers cover composition-basis conversion,
monotonic linear crossings, and solidification-trajectory validation.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
import math as _math
from typing import Protocol as _Protocol

from thermogar_numerical_grid import (
    NUMERICAL_ADAPTER_REASON_CODES,
    NumericalAdapterError,
)


_NAME_CHARACTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_#:+-.")
_SIMPLEX_TOLERANCE = 1.0e-12
_BALANCE_TOLERANCE = 1.0e-10


def _fail(reason_code: str) -> None:
    raise NumericalAdapterError(reason_code)


def _canonical_name(value: object, reason_code: str) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 64
        or any(character not in _NAME_CHARACTERS for character in value)
    ):
        _fail(reason_code)
    return value


def _binary64(
    value: object,
    *,
    invalid_reason: str,
    nonfinite_reason: str,
    overflow_reason: str,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(invalid_reason)
    try:
        number = float(value)
    except OverflowError as error:
        raise NumericalAdapterError(overflow_reason) from error
    if not _math.isfinite(number):
        _fail(nonfinite_reason)
    return 0.0 if number == 0.0 else number


def _safe_fsum(values: object, reason_code: str) -> float:
    try:
        result = _math.fsum(values)  # type: ignore[arg-type]
    except (OverflowError, ValueError) as error:
        raise NumericalAdapterError(reason_code) from error
    if not _math.isfinite(result):
        _fail(reason_code)
    return 0.0 if result == 0.0 else result


def _validated_names(
    value: object,
    *,
    container_reason: str,
    name_reason: str,
    duplicate_reason: str,
) -> tuple[str, ...]:
    if type(value) is not tuple or not value:
        _fail(container_reason)
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        name = _canonical_name(item, name_reason)
        if name in seen:
            _fail(duplicate_reason)
        seen.add(name)
        result.append(name)
    return tuple(result)


def _validated_named_fractions(
    value: object,
    *,
    expected_names: tuple[str, ...] | None,
    container_reason: str,
    name_reason: str,
    duplicate_reason: str,
    mismatch_reason: str,
    invalid_reason: str,
    nonfinite_reason: str,
    overflow_reason: str,
    negative_reason: str,
    sum_reason: str,
) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple or not value:
        _fail(container_reason)
    result: list[tuple[str, float]] = []
    seen: set[str] = set()
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            _fail(container_reason)
        name = _canonical_name(pair[0], name_reason)
        if name in seen:
            _fail(duplicate_reason)
        seen.add(name)
        number = _binary64(
            pair[1],
            invalid_reason=invalid_reason,
            nonfinite_reason=nonfinite_reason,
            overflow_reason=overflow_reason,
        )
        if number < 0.0:
            _fail(negative_reason)
        result.append((name, number))
    immutable = tuple(result)
    names = tuple(name for name, _number in immutable)
    if expected_names is not None and names != expected_names:
        _fail(mismatch_reason)
    total = _safe_fsum(
        (number for _name, number in immutable),
        sum_reason,
    )
    if abs(total - 1.0) > _SIMPLEX_TOLERANCE:
        _fail(sum_reason)
    return immutable


def _temperature(value: object, *, solidification: bool = False) -> float:
    prefix = "SOLIDIFICATION_TEMPERATURE" if solidification else "EQ_TEMPERATURE"
    result = _binary64(
        value,
        invalid_reason=f"{prefix}_INVALID",
        nonfinite_reason=f"{prefix}_NONFINITE",
        overflow_reason=f"{prefix}_OVERFLOW",
    )
    if result <= 0.0:
        _fail(f"{prefix}_NONPOSITIVE")
    return result


def _phase_fraction(value: object) -> float:
    result = _binary64(
        value,
        invalid_reason="EQ_PHASE_FRACTION_INVALID",
        nonfinite_reason="EQ_PHASE_FRACTION_NONFINITE",
        overflow_reason="EQ_PHASE_FRACTION_OVERFLOW",
    )
    if result < 0.0:
        _fail("EQ_PHASE_FRACTION_NEGATIVE")
    return result


def _composition(
    value: object,
    *,
    expected_names: tuple[str, ...] | None,
) -> tuple[tuple[str, float], ...]:
    return _validated_named_fractions(
        value,
        expected_names=expected_names,
        container_reason="EQ_COMPOSITION_INVALID",
        name_reason="EQ_COMPONENT_INVALID",
        duplicate_reason="EQ_COMPONENT_DUPLICATE",
        mismatch_reason="EQ_COMPOSITION_NAME_MISMATCH",
        invalid_reason="EQ_COMPOSITION_VALUE_INVALID",
        nonfinite_reason="EQ_COMPOSITION_VALUE_NONFINITE",
        overflow_reason="EQ_COMPOSITION_VALUE_OVERFLOW",
        negative_reason="EQ_COMPOSITION_VALUE_NEGATIVE",
        sum_reason="EQ_COMPOSITION_SUM_INVALID",
    )


@_dataclass(frozen=True, slots=True)
class EquilibriumRequest:
    """Validated state and exact system selection supplied to a backend."""

    temperature_k: float
    pressure_pa: float
    components: tuple[str, ...]
    phases: tuple[str, ...]
    composition: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        temperature = _temperature(self.temperature_k)
        pressure = _binary64(
            self.pressure_pa,
            invalid_reason="EQ_PRESSURE_INVALID",
            nonfinite_reason="EQ_PRESSURE_NONFINITE",
            overflow_reason="EQ_PRESSURE_OVERFLOW",
        )
        if pressure <= 0.0:
            _fail("EQ_PRESSURE_NONPOSITIVE")
        components = _validated_names(
            self.components,
            container_reason="EQ_COMPONENTS_INVALID",
            name_reason="EQ_COMPONENT_INVALID",
            duplicate_reason="EQ_COMPONENT_DUPLICATE",
        )
        phases = _validated_names(
            self.phases,
            container_reason="EQ_PHASES_INVALID",
            name_reason="EQ_PHASE_INVALID",
            duplicate_reason="EQ_PHASE_DUPLICATE",
        )
        composition = _composition(self.composition, expected_names=components)
        object.__setattr__(self, "temperature_k", temperature)
        object.__setattr__(self, "pressure_pa", pressure)
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "phases", phases)
        object.__setattr__(self, "composition", composition)


@_dataclass(frozen=True, slots=True)
class RawPhaseState:
    """One backend phase row; repeated phase names are intentionally allowed."""

    phase: str
    phase_fraction: float
    composition: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        phase = _canonical_name(self.phase, "EQ_PHASE_INVALID")
        phase_fraction = _phase_fraction(self.phase_fraction)
        composition = _composition(self.composition, expected_names=None)
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "phase_fraction", phase_fraction)
        object.__setattr__(self, "composition", composition)


@_dataclass(frozen=True, slots=True)
class EquilibriumRawResult:
    """Immutable backend response before aggregation and conservation checks."""

    phase_states: tuple[RawPhaseState, ...]

    def __post_init__(self) -> None:
        if (
            type(self.phase_states) is not tuple
            or not self.phase_states
            or any(not isinstance(state, RawPhaseState) for state in self.phase_states)
        ):
            _fail("EQ_RAW_PHASES_INVALID")


@_dataclass(frozen=True, slots=True)
class PhaseAggregate:
    """One deterministically aggregated phase in the validated answer."""

    phase: str
    phase_fraction: float
    composition: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        phase = _canonical_name(self.phase, "EQ_PHASE_INVALID")
        phase_fraction = _phase_fraction(self.phase_fraction)
        if phase_fraction == 0.0:
            _fail("EQ_PHASE_SUM_INVALID")
        composition = _composition(self.composition, expected_names=None)
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "phase_fraction", phase_fraction)
        object.__setattr__(self, "composition", composition)


@_dataclass(frozen=True, slots=True)
class EquilibriumResult:
    """Validated equilibrium answer with sorted unique phase aggregates."""

    request: EquilibriumRequest
    phases: tuple[PhaseAggregate, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request, EquilibriumRequest):
            _fail("EQ_RAW_RESULT_INVALID")
        if (
            type(self.phases) is not tuple
            or not self.phases
            or any(not isinstance(phase, PhaseAggregate) for phase in self.phases)
        ):
            _fail("EQ_RAW_RESULT_INVALID")
        names = tuple(phase.phase for phase in self.phases)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            _fail("EQ_RAW_RESULT_INVALID")
        requested_phases = set(self.request.phases)
        for phase in self.phases:
            if phase.phase not in requested_phases:
                _fail("EQ_RAW_PHASE_NOT_REQUESTED")
            if tuple(name for name, _value in phase.composition) != self.request.components:
                _fail("EQ_COMPOSITION_NAME_MISMATCH")
        _check_phase_balance_and_conservation(self.request, self.phases)


class EquilibriumBackend(_Protocol):
    """Structural boundary implemented by a real or manufactured solver."""

    def solve(self, request: EquilibriumRequest) -> EquilibriumRawResult:
        """Return immutable raw phase states for one request."""


def _checked_product(left: float, right: float) -> float:
    result = left * right
    if not _math.isfinite(result) or (left > 0.0 and right > 0.0 and result == 0.0):
        _fail("EQ_ARITHMETIC_INVALID")
    return 0.0 if result == 0.0 else result


def _check_phase_balance_and_conservation(
    request: EquilibriumRequest,
    phases: tuple[PhaseAggregate, ...],
) -> None:
    phase_total = _safe_fsum(
        (phase.phase_fraction for phase in phases),
        "EQ_PHASE_SUM_INVALID",
    )
    if abs(phase_total - 1.0) > _BALANCE_TOLERANCE:
        _fail("EQ_PHASE_SUM_INVALID")
    requested = dict(request.composition)
    for component in request.components:
        contributions = sorted(
            _checked_product(phase.phase_fraction, dict(phase.composition)[component])
            for phase in phases
        )
        aggregate = _safe_fsum(contributions, "EQ_ARITHMETIC_INVALID")
        if abs(aggregate - requested[component]) > _BALANCE_TOLERANCE:
            _fail("EQ_CONSERVATION_INVALID")


def _aggregate_raw_result(
    request: EquilibriumRequest,
    raw_result: object,
) -> tuple[PhaseAggregate, ...]:
    if not isinstance(raw_result, EquilibriumRawResult):
        _fail("EQ_RAW_RESULT_INVALID")
    states = raw_result.phase_states
    requested_phases = set(request.phases)
    component_names = request.components
    for state in states:
        if not isinstance(state, RawPhaseState):
            _fail("EQ_RAW_PHASE_INVALID")
        if state.phase not in requested_phases:
            _fail("EQ_RAW_PHASE_NOT_REQUESTED")
        if tuple(name for name, _value in state.composition) != component_names:
            _fail("EQ_COMPOSITION_NAME_MISMATCH")

    sorted_states = tuple(
        sorted(
            states,
            key=lambda state: (
                state.phase,
                state.phase_fraction,
                state.composition,
            ),
        )
    )
    aggregates: list[PhaseAggregate] = []
    for phase_name in sorted({state.phase for state in sorted_states}):
        group = tuple(state for state in sorted_states if state.phase == phase_name)
        phase_fraction = _safe_fsum(
            (state.phase_fraction for state in group),
            "EQ_ARITHMETIC_INVALID",
        )
        if phase_fraction == 0.0:
            continue
        composition_rows: list[tuple[str, float]] = []
        for component_index, component in enumerate(component_names):
            contributions = sorted(
                _checked_product(
                    state.phase_fraction,
                    state.composition[component_index][1],
                )
                for state in group
            )
            numerator = _safe_fsum(contributions, "EQ_ARITHMETIC_INVALID")
            value = numerator / phase_fraction
            if not _math.isfinite(value) or (numerator > 0.0 and value == 0.0):
                _fail("EQ_ARITHMETIC_INVALID")
            composition_rows.append((component, 0.0 if value == 0.0 else value))
        aggregates.append(
            PhaseAggregate(
                phase=phase_name,
                phase_fraction=phase_fraction,
                composition=tuple(composition_rows),
            )
        )
    immutable = tuple(aggregates)
    if not immutable:
        _fail("EQ_PHASE_SUM_INVALID")
    return immutable


def evaluate_equilibrium(
    request: object,
    backend: object,
) -> EquilibriumResult:
    """Run one backend request and fail closed on any numerical contract breach."""

    if not isinstance(request, EquilibriumRequest):
        _fail("EQ_RAW_RESULT_INVALID")
    solve = getattr(backend, "solve", None)
    if not callable(solve):
        _fail("EQ_BACKEND_INVALID")
    raw_result = solve(request)
    phases = _aggregate_raw_result(request, raw_result)
    _check_phase_balance_and_conservation(request, phases)
    return EquilibriumResult(request=request, phases=phases)


def _conversion_inputs(
    fractions: object,
    atomic_masses: object,
) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, float], ...]]:
    validated_fractions = _validated_named_fractions(
        fractions,
        expected_names=None,
        container_reason="CONVERSION_FRACTIONS_INVALID",
        name_reason="EQ_COMPONENT_INVALID",
        duplicate_reason="EQ_COMPONENT_DUPLICATE",
        mismatch_reason="CONVERSION_NAME_MISMATCH",
        invalid_reason="EQ_COMPOSITION_VALUE_INVALID",
        nonfinite_reason="EQ_COMPOSITION_VALUE_NONFINITE",
        overflow_reason="EQ_COMPOSITION_VALUE_OVERFLOW",
        negative_reason="EQ_COMPOSITION_VALUE_NEGATIVE",
        sum_reason="EQ_COMPOSITION_SUM_INVALID",
    )
    if type(atomic_masses) is not tuple or not atomic_masses:
        _fail("CONVERSION_MASSES_INVALID")
    masses: list[tuple[str, float]] = []
    seen: set[str] = set()
    for pair in atomic_masses:
        if type(pair) is not tuple or len(pair) != 2:
            _fail("CONVERSION_MASSES_INVALID")
        name = _canonical_name(pair[0], "EQ_COMPONENT_INVALID")
        if name in seen:
            _fail("EQ_COMPONENT_DUPLICATE")
        seen.add(name)
        mass = _binary64(
            pair[1],
            invalid_reason="CONVERSION_MASS_VALUE_INVALID",
            nonfinite_reason="CONVERSION_MASS_NONFINITE",
            overflow_reason="CONVERSION_MASS_OVERFLOW",
        )
        if mass <= 0.0:
            _fail("CONVERSION_MASS_NONPOSITIVE")
        masses.append((name, mass))
    immutable_masses = tuple(masses)
    if tuple(name for name, _value in immutable_masses) != tuple(
        name for name, _value in validated_fractions
    ):
        _fail("CONVERSION_NAME_MISMATCH")
    return validated_fractions, immutable_masses


def _normalize_conversion(
    names: tuple[str, ...],
    unnormalized: tuple[float, ...],
) -> tuple[tuple[str, float], ...]:
    total = _safe_fsum(sorted(unnormalized), "CONVERSION_ARITHMETIC_INVALID")
    if total <= 0.0:
        _fail("CONVERSION_ARITHMETIC_INVALID")
    result: list[tuple[str, float]] = []
    for name, raw_value in zip(names, unnormalized):
        normalized = raw_value / total
        if not _math.isfinite(normalized) or (raw_value > 0.0 and normalized == 0.0):
            _fail("CONVERSION_ARITHMETIC_INVALID")
        result.append((name, 0.0 if normalized == 0.0 else normalized))
    immutable = tuple(result)
    if abs(
        _safe_fsum(
            (value for _name, value in immutable),
            "CONVERSION_ARITHMETIC_INVALID",
        )
        - 1.0
    ) > _SIMPLEX_TOLERANCE:
        _fail("CONVERSION_ARITHMETIC_INVALID")
    return immutable


def mass_to_mole_fractions(
    mass_fractions: object,
    atomic_masses: object,
) -> tuple[tuple[str, float], ...]:
    """Convert a strict mass-fraction simplex to a mole-fraction simplex."""

    fractions, masses = _conversion_inputs(mass_fractions, atomic_masses)
    raw: list[float] = []
    for (_name, fraction), (_mass_name, mass) in zip(fractions, masses):
        value = fraction / mass
        if not _math.isfinite(value) or (fraction > 0.0 and value == 0.0):
            _fail("CONVERSION_ARITHMETIC_INVALID")
        raw.append(0.0 if value == 0.0 else value)
    return _normalize_conversion(
        tuple(name for name, _value in fractions),
        tuple(raw),
    )


def mole_to_mass_fractions(
    mole_fractions: object,
    atomic_masses: object,
) -> tuple[tuple[str, float], ...]:
    """Convert a strict mole-fraction simplex to a mass-fraction simplex."""

    fractions, masses = _conversion_inputs(mole_fractions, atomic_masses)
    raw: list[float] = []
    for (_name, fraction), (_mass_name, mass) in zip(fractions, masses):
        value = fraction * mass
        if not _math.isfinite(value) or (fraction > 0.0 and value == 0.0):
            _fail("CONVERSION_ARITHMETIC_INVALID")
        raw.append(0.0 if value == 0.0 else value)
    return _normalize_conversion(
        tuple(name for name, _value in fractions),
        tuple(raw),
    )


@_dataclass(frozen=True, slots=True)
class LinearCrossing:
    """One exact sample hit or one linearly interpolated monotonic crossing."""

    x: float
    target: float
    left_index: int
    right_index: int

    def __post_init__(self) -> None:
        x = _binary64(
            self.x,
            invalid_reason="CROSSING_X_INVALID",
            nonfinite_reason="CROSSING_X_NONFINITE",
            overflow_reason="CROSSING_X_OVERFLOW",
        )
        target = _binary64(
            self.target,
            invalid_reason="CROSSING_TARGET_INVALID",
            nonfinite_reason="CROSSING_TARGET_NONFINITE",
            overflow_reason="CROSSING_TARGET_OVERFLOW",
        )
        if x < 0.0:
            _fail("CROSSING_X_NEGATIVE")
        if any(
            isinstance(index, bool) or type(index) is not int or index < 0
            for index in (self.left_index, self.right_index)
        ) or self.left_index > self.right_index:
            _fail("CROSSING_SHAPE_INVALID")
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "target", target)


def find_monotonic_linear_crossings(
    x_values: object,
    y_values: object,
    *,
    target: object = 0.0,
) -> tuple[LinearCrossing, ...]:
    """Return the sole crossing of a strictly monotonic sampled line."""

    if (
        type(x_values) is not tuple
        or type(y_values) is not tuple
        or len(x_values) < 2
        or len(x_values) != len(y_values)
    ):
        _fail("CROSSING_SHAPE_INVALID")
    xs = tuple(
        _binary64(
            value,
            invalid_reason="CROSSING_X_INVALID",
            nonfinite_reason="CROSSING_X_NONFINITE",
            overflow_reason="CROSSING_X_OVERFLOW",
        )
        for value in x_values
    )
    ys = tuple(
        _binary64(
            value,
            invalid_reason="CROSSING_Y_INVALID",
            nonfinite_reason="CROSSING_Y_NONFINITE",
            overflow_reason="CROSSING_Y_OVERFLOW",
        )
        for value in y_values
    )
    crossing_target = _binary64(
        target,
        invalid_reason="CROSSING_TARGET_INVALID",
        nonfinite_reason="CROSSING_TARGET_NONFINITE",
        overflow_reason="CROSSING_TARGET_OVERFLOW",
    )
    for index, value in enumerate(xs):
        if value < 0.0:
            _fail("CROSSING_X_NEGATIVE")
        if index and value <= xs[index - 1]:
            _fail("CROSSING_X_UNSORTED")
    increasing = all(ys[index] > ys[index - 1] for index in range(1, len(ys)))
    decreasing = all(ys[index] < ys[index - 1] for index in range(1, len(ys)))
    if not (increasing or decreasing):
        _fail("CROSSING_Y_NONMONOTONIC")

    for index, value in enumerate(ys):
        if value == crossing_target:
            return (
                LinearCrossing(
                    x=xs[index],
                    target=crossing_target,
                    left_index=index,
                    right_index=index,
                ),
            )
    lower = min(ys[0], ys[-1])
    upper = max(ys[0], ys[-1])
    if crossing_target < lower or crossing_target > upper:
        _fail("CROSSING_NOT_FOUND")
    for index in range(len(ys) - 1):
        left_y = ys[index]
        right_y = ys[index + 1]
        if min(left_y, right_y) < crossing_target < max(left_y, right_y):
            scale = max(abs(left_y), abs(right_y), abs(crossing_target), 1.0)
            denominator = right_y / scale - left_y / scale
            numerator = crossing_target / scale - left_y / scale
            if denominator == 0.0:
                _fail("CROSSING_ARITHMETIC_INVALID")
            ratio = numerator / denominator
            x = xs[index] + ratio * (xs[index + 1] - xs[index])
            if (
                not _math.isfinite(ratio)
                or not 0.0 < ratio < 1.0
                or not _math.isfinite(x)
                or not xs[index] < x < xs[index + 1]
            ):
                _fail("CROSSING_ARITHMETIC_INVALID")
            return (
                LinearCrossing(
                    x=0.0 if x == 0.0 else x,
                    target=crossing_target,
                    left_index=index,
                    right_index=index + 1,
                ),
            )
    _fail("CROSSING_NOT_FOUND")


def _solidification_fraction(value: object) -> float:
    result = _binary64(
        value,
        invalid_reason="SOLIDIFICATION_FRACTION_INVALID",
        nonfinite_reason="SOLIDIFICATION_FRACTION_NONFINITE",
        overflow_reason="SOLIDIFICATION_FRACTION_OVERFLOW",
    )
    if result < 0.0 or result > 1.0:
        _fail("SOLIDIFICATION_FRACTION_RANGE")
    return result


def _solid_phase_fractions(
    value: object,
    solid_fraction: float,
) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple:
        _fail("SOLIDIFICATION_PHASES_INVALID")
    result: list[tuple[str, float]] = []
    seen: set[str] = set()
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            _fail("SOLIDIFICATION_PHASES_INVALID")
        name = _canonical_name(pair[0], "SOLIDIFICATION_PHASE_INVALID")
        if name in seen:
            _fail("SOLIDIFICATION_PHASE_DUPLICATE")
        seen.add(name)
        fraction = _solidification_fraction(pair[1])
        result.append((name, fraction))
    immutable = tuple(sorted(result, key=lambda row: row[0]))
    total = _safe_fsum(
        (fraction for _name, fraction in immutable),
        "SOLIDIFICATION_PHASE_SUM_INVALID",
    )
    if abs(total - solid_fraction) > _BALANCE_TOLERANCE:
        _fail("SOLIDIFICATION_PHASE_SUM_INVALID")
    return immutable


@_dataclass(frozen=True, slots=True)
class SolidificationPoint:
    """One validated node of a solidification trajectory."""

    temperature_k: float
    solid_fraction: float
    liquid_fraction: float
    phase_fractions: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        temperature = _temperature(self.temperature_k, solidification=True)
        solid = _solidification_fraction(self.solid_fraction)
        liquid = _solidification_fraction(self.liquid_fraction)
        if abs(
            _safe_fsum(
                (solid, liquid),
                "SOLIDIFICATION_BALANCE_INVALID",
            )
            - 1.0
        ) > _BALANCE_TOLERANCE:
            _fail("SOLIDIFICATION_BALANCE_INVALID")
        phases = _solid_phase_fractions(self.phase_fractions, solid)
        object.__setattr__(self, "temperature_k", temperature)
        object.__setattr__(self, "solid_fraction", solid)
        object.__setattr__(self, "liquid_fraction", liquid)
        object.__setattr__(self, "phase_fractions", phases)


@_dataclass(frozen=True, slots=True)
class SolidificationTrajectory:
    """Direction-aware immutable sequence of solidification points."""

    direction: str
    points: tuple[SolidificationPoint, ...]

    def __post_init__(self) -> None:
        if self.direction not in ("cooling", "heating"):
            _fail("SOLIDIFICATION_DIRECTION_INVALID")
        if (
            type(self.points) is not tuple
            or len(self.points) < 2
            or any(not isinstance(point, SolidificationPoint) for point in self.points)
        ):
            _fail("SOLIDIFICATION_SHAPE_INVALID")
        for index in range(1, len(self.points)):
            previous = self.points[index - 1]
            current = self.points[index]
            if self.direction == "cooling":
                if current.temperature_k >= previous.temperature_k:
                    _fail("SOLIDIFICATION_TEMPERATURE_DIRECTION")
                if current.solid_fraction < previous.solid_fraction:
                    _fail("SOLIDIFICATION_PROGRESS_INVALID")
            else:
                if current.temperature_k <= previous.temperature_k:
                    _fail("SOLIDIFICATION_TEMPERATURE_DIRECTION")
                if current.solid_fraction > previous.solid_fraction:
                    _fail("SOLIDIFICATION_PROGRESS_INVALID")


def validate_solidification_trajectory(
    temperatures_k: object,
    solid_fractions: object,
    liquid_fractions: object,
    phase_fractions: object,
    *,
    direction: object = "cooling",
) -> SolidificationTrajectory:
    """Validate equal-shape balances and monotonic direction node by node."""

    if type(direction) is not str or direction not in ("cooling", "heating"):
        _fail("SOLIDIFICATION_DIRECTION_INVALID")
    if (
        type(temperatures_k) is not tuple
        or type(solid_fractions) is not tuple
        or type(liquid_fractions) is not tuple
        or type(phase_fractions) is not tuple
        or len(temperatures_k) < 2
        or not (
            len(temperatures_k)
            == len(solid_fractions)
            == len(liquid_fractions)
            == len(phase_fractions)
        )
    ):
        _fail("SOLIDIFICATION_SHAPE_INVALID")
    points = tuple(
        SolidificationPoint(
            temperature_k=temperature,
            solid_fraction=solid,
            liquid_fraction=liquid,
            phase_fractions=phases,
        )
        for temperature, solid, liquid, phases in zip(
            temperatures_k,
            solid_fractions,
            liquid_fractions,
            phase_fractions,
        )
    )
    return SolidificationTrajectory(direction=direction, points=points)


__all__ = (
    "NUMERICAL_ADAPTER_REASON_CODES",
    "NumericalAdapterError",
    "EquilibriumRequest",
    "RawPhaseState",
    "EquilibriumRawResult",
    "PhaseAggregate",
    "EquilibriumResult",
    "EquilibriumBackend",
    "LinearCrossing",
    "SolidificationPoint",
    "SolidificationTrajectory",
    "evaluate_equilibrium",
    "mass_to_mole_fractions",
    "mole_to_mass_fractions",
    "find_monotonic_linear_crossings",
    "validate_solidification_trajectory",
)
