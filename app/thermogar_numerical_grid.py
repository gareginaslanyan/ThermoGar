"""Deterministic, fail-closed numerical grids for ThermoGar.

This module is deliberately independent of NumPy, pandas, plotting, files and
solver libraries.  It turns an explicitly ordered Cartesian grid into one
immutable record per requested node.  Expected numerical-domain failures are
retained as ``FAIL`` records; programming errors are never swallowed.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
import math as _math
from types import MappingProxyType as _MappingProxyType
from typing import Mapping as _Mapping


_REASONS = {
    "NODE_OK": "The requested node completed successfully.",
    "GRID_AXIS_CONTAINER_INVALID": "Grid axes must be an immutable tuple.",
    "GRID_AXES_EMPTY": "A Cartesian grid requires at least one axis.",
    "GRID_AXIS_NAME_INVALID": "Axis names must be canonical identifiers.",
    "GRID_AXIS_DUPLICATE_NAME": "Axis names must be unique.",
    "GRID_AXIS_VALUES_INVALID": "Axis values must be a non-empty immutable tuple.",
    "GRID_AXIS_VALUE_INVALID": "Axis values must be binary64-compatible numbers.",
    "GRID_AXIS_VALUE_NONFINITE": "Axis values must be finite.",
    "GRID_AXIS_VALUE_OVERFLOW": "An axis value is outside binary64 range.",
    "GRID_AXIS_VALUE_NEGATIVE": "Axis values must be non-negative.",
    "GRID_AXIS_VALUE_DUPLICATE": "Axis values must not be duplicated.",
    "GRID_AXIS_VALUE_UNSORTED": "Axis values must be strictly increasing.",
    "GRID_MAX_NODES_INVALID": "The node ceiling must be a bounded positive integer.",
    "GRID_NODE_LIMIT_EXCEEDED": "The Cartesian product exceeds the node ceiling.",
    "GRID_EVALUATOR_INVALID": "A grid evaluator must be callable.",
    "GRID_OUTPUT_INVALID": "Node output must be an immutable tuple of named numbers.",
    "GRID_OUTPUT_KEY_INVALID": "Node output names must be canonical identifiers.",
    "GRID_OUTPUT_KEY_DUPLICATE": "Node output names must not be duplicated.",
    "GRID_OUTPUT_KEY_UNSORTED": "Node output names must be strictly ordered.",
    "GRID_OUTPUT_VALUE_INVALID": "Node output values must be binary64-compatible numbers.",
    "GRID_OUTPUT_VALUE_NONFINITE": "Node output values must be finite.",
    "GRID_OUTPUT_VALUE_OVERFLOW": "A node output is outside binary64 range.",
    "EQ_TEMPERATURE_INVALID": "Temperature must be a binary64-compatible number.",
    "EQ_TEMPERATURE_NONFINITE": "Temperature must be finite.",
    "EQ_TEMPERATURE_OVERFLOW": "Temperature is outside binary64 range.",
    "EQ_TEMPERATURE_NONPOSITIVE": "Temperature must be strictly positive.",
    "EQ_PRESSURE_INVALID": "Pressure must be a binary64-compatible number.",
    "EQ_PRESSURE_NONFINITE": "Pressure must be finite.",
    "EQ_PRESSURE_OVERFLOW": "Pressure is outside binary64 range.",
    "EQ_PRESSURE_NONPOSITIVE": "Pressure must be strictly positive.",
    "EQ_COMPONENTS_INVALID": "Components must be a non-empty immutable tuple.",
    "EQ_COMPONENT_INVALID": "Component names must be canonical identifiers.",
    "EQ_COMPONENT_DUPLICATE": "Component names must be unique.",
    "EQ_PHASES_INVALID": "Phases must be a non-empty immutable tuple.",
    "EQ_PHASE_INVALID": "Phase names must be canonical identifiers.",
    "EQ_PHASE_DUPLICATE": "Phase names must be unique.",
    "EQ_COMPOSITION_INVALID": "Composition must be an immutable tuple of named numbers.",
    "EQ_COMPOSITION_NAME_MISMATCH": "Composition names must exactly match component order.",
    "EQ_COMPOSITION_VALUE_INVALID": "Composition values must be binary64-compatible numbers.",
    "EQ_COMPOSITION_VALUE_NONFINITE": "Composition values must be finite.",
    "EQ_COMPOSITION_VALUE_OVERFLOW": "A composition value is outside binary64 range.",
    "EQ_COMPOSITION_VALUE_NEGATIVE": "Composition values must be non-negative.",
    "EQ_COMPOSITION_SUM_INVALID": "Composition values must sum to one.",
    "EQ_BACKEND_INVALID": "The equilibrium backend must expose a callable solve method.",
    "EQ_RAW_RESULT_INVALID": "The backend returned an invalid raw result.",
    "EQ_RAW_PHASES_INVALID": "The raw result must contain immutable phase rows.",
    "EQ_RAW_PHASE_INVALID": "A raw phase row is invalid.",
    "EQ_RAW_PHASE_NOT_REQUESTED": "A raw phase was not present in the request.",
    "EQ_PHASE_FRACTION_INVALID": "Phase fractions must be binary64-compatible numbers.",
    "EQ_PHASE_FRACTION_NONFINITE": "Phase fractions must be finite.",
    "EQ_PHASE_FRACTION_OVERFLOW": "A phase fraction is outside binary64 range.",
    "EQ_PHASE_FRACTION_NEGATIVE": "Phase fractions must be non-negative.",
    "EQ_PHASE_SUM_INVALID": "Phase fractions must sum to one.",
    "EQ_CONSERVATION_INVALID": "The phase aggregate does not conserve bulk composition.",
    "EQ_ARITHMETIC_INVALID": "Equilibrium aggregation left the finite binary64 domain.",
    "CONVERSION_FRACTIONS_INVALID": "Conversion fractions must be an immutable named tuple.",
    "CONVERSION_MASSES_INVALID": "Atomic masses must be an immutable named tuple.",
    "CONVERSION_NAME_MISMATCH": "Atomic-mass names must exactly match fraction order.",
    "CONVERSION_MASS_VALUE_INVALID": "Atomic masses must be binary64-compatible numbers.",
    "CONVERSION_MASS_NONFINITE": "Atomic masses must be finite.",
    "CONVERSION_MASS_OVERFLOW": "An atomic mass is outside binary64 range.",
    "CONVERSION_MASS_NONPOSITIVE": "Atomic masses must be strictly positive.",
    "CONVERSION_ARITHMETIC_INVALID": "Composition conversion left the finite binary64 domain.",
    "CROSSING_SHAPE_INVALID": "Crossing inputs must be equal immutable tuples of length two or more.",
    "CROSSING_X_INVALID": "Crossing abscissae must be binary64-compatible numbers.",
    "CROSSING_X_NONFINITE": "Crossing abscissae must be finite.",
    "CROSSING_X_OVERFLOW": "A crossing abscissa is outside binary64 range.",
    "CROSSING_X_NEGATIVE": "Crossing abscissae must be non-negative.",
    "CROSSING_X_UNSORTED": "Crossing abscissae must be strictly increasing.",
    "CROSSING_Y_INVALID": "Crossing ordinates must be binary64-compatible numbers.",
    "CROSSING_Y_NONFINITE": "Crossing ordinates must be finite.",
    "CROSSING_Y_OVERFLOW": "A crossing ordinate is outside binary64 range.",
    "CROSSING_Y_NONMONOTONIC": "Crossing ordinates must be strictly monotonic.",
    "CROSSING_TARGET_INVALID": "The crossing target must be a binary64-compatible number.",
    "CROSSING_TARGET_NONFINITE": "The crossing target must be finite.",
    "CROSSING_TARGET_OVERFLOW": "The crossing target is outside binary64 range.",
    "CROSSING_NOT_FOUND": "The target is outside the sampled monotonic range.",
    "CROSSING_ARITHMETIC_INVALID": "Crossing interpolation left the finite binary64 domain.",
    "SOLIDIFICATION_SHAPE_INVALID": "Solidification arrays must be equal immutable tuples.",
    "SOLIDIFICATION_DIRECTION_INVALID": "Solidification direction must be cooling or heating.",
    "SOLIDIFICATION_TEMPERATURE_INVALID": "Solidification temperatures must be binary64-compatible numbers.",
    "SOLIDIFICATION_TEMPERATURE_NONFINITE": "Solidification temperatures must be finite.",
    "SOLIDIFICATION_TEMPERATURE_OVERFLOW": "A solidification temperature is outside binary64 range.",
    "SOLIDIFICATION_TEMPERATURE_NONPOSITIVE": "Solidification temperatures must be positive.",
    "SOLIDIFICATION_TEMPERATURE_DIRECTION": "Temperatures do not follow the declared direction.",
    "SOLIDIFICATION_FRACTION_INVALID": "Solidification fractions must be binary64-compatible numbers.",
    "SOLIDIFICATION_FRACTION_NONFINITE": "Solidification fractions must be finite.",
    "SOLIDIFICATION_FRACTION_OVERFLOW": "A solidification fraction is outside binary64 range.",
    "SOLIDIFICATION_FRACTION_RANGE": "Solidification fractions must be within zero and one.",
    "SOLIDIFICATION_BALANCE_INVALID": "Solid and liquid fractions must sum to one.",
    "SOLIDIFICATION_PHASES_INVALID": "Per-node phase fractions must be immutable named tuples.",
    "SOLIDIFICATION_PHASE_INVALID": "Solidification phase names must be canonical identifiers.",
    "SOLIDIFICATION_PHASE_DUPLICATE": "Solidification phase names must be unique per node.",
    "SOLIDIFICATION_PHASE_SUM_INVALID": "Per-node phase fractions must sum to the solid fraction.",
    "SOLIDIFICATION_PROGRESS_INVALID": "Solidification fractions contradict the declared direction.",
}

NUMERICAL_ADAPTER_REASON_CODES: _Mapping[str, str] = _MappingProxyType(_REASONS)
del _REASONS

_NAME_CHARACTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_#:+-.")
_ABSOLUTE_MAX_NODES = 1_000_000


class NumericalAdapterError(ValueError):
    """Fail-closed numerical error with a stable machine-readable reason."""

    __slots__ = ("reason_code",)

    def __init__(self, reason_code: str) -> None:
        if reason_code not in NUMERICAL_ADAPTER_REASON_CODES:
            raise RuntimeError("Unknown numerical-adapter reason code")
        self.reason_code = reason_code
        super().__init__(reason_code)


class ExpectedNodeFailure(NumericalAdapterError):
    """Explicit evaluator signal for an expected solver/domain node failure.

    Structural adapter errors and programming faults must use their native
    exception channel so the complete grid case aborts instead of recording a
    misleading ordinary failed node.
    """

    __slots__ = ()


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
        result = float(value)
    except OverflowError as error:
        raise NumericalAdapterError(overflow_reason) from error
    if not _math.isfinite(result):
        _fail(nonfinite_reason)
    return 0.0 if result == 0.0 else result


@_dataclass(frozen=True, slots=True)
class AxisSpec:
    """One canonical, strictly increasing non-negative grid axis."""

    name: str
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        name = _canonical_name(self.name, "GRID_AXIS_NAME_INVALID")
        if type(self.values) is not tuple or not self.values:
            _fail("GRID_AXIS_VALUES_INVALID")
        normalized = tuple(
            _binary64(
                value,
                invalid_reason="GRID_AXIS_VALUE_INVALID",
                nonfinite_reason="GRID_AXIS_VALUE_NONFINITE",
                overflow_reason="GRID_AXIS_VALUE_OVERFLOW",
            )
            for value in self.values
        )
        for index, value in enumerate(normalized):
            if value < 0.0:
                _fail("GRID_AXIS_VALUE_NEGATIVE")
            if index:
                if value == normalized[index - 1]:
                    _fail("GRID_AXIS_VALUE_DUPLICATE")
                if value < normalized[index - 1]:
                    _fail("GRID_AXIS_VALUE_UNSORTED")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "values", normalized)


@_dataclass(frozen=True, slots=True)
class GridNode:
    """A zero-based ordinal and its axis coordinates."""

    ordinal: int
    coordinates: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        if isinstance(self.ordinal, bool) or type(self.ordinal) is not int or self.ordinal < 0:
            _fail("GRID_OUTPUT_INVALID")
        if type(self.coordinates) is not tuple or not self.coordinates:
            _fail("GRID_OUTPUT_INVALID")
        names: set[str] = set()
        normalized: list[tuple[str, float]] = []
        for pair in self.coordinates:
            if type(pair) is not tuple or len(pair) != 2:
                _fail("GRID_OUTPUT_INVALID")
            name = _canonical_name(pair[0], "GRID_AXIS_NAME_INVALID")
            if name in names:
                _fail("GRID_AXIS_DUPLICATE_NAME")
            names.add(name)
            value = _binary64(
                pair[1],
                invalid_reason="GRID_AXIS_VALUE_INVALID",
                nonfinite_reason="GRID_AXIS_VALUE_NONFINITE",
                overflow_reason="GRID_AXIS_VALUE_OVERFLOW",
            )
            if value < 0.0:
                _fail("GRID_AXIS_VALUE_NEGATIVE")
            normalized.append((name, value))
        object.__setattr__(self, "coordinates", tuple(normalized))


@_dataclass(frozen=True, slots=True)
class NodeRecord:
    """Immutable retained outcome for exactly one requested grid node."""

    node: GridNode
    outcome: str
    reason_code: str
    outputs: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.node, GridNode):
            _fail("GRID_OUTPUT_INVALID")
        if self.outcome not in ("PASS", "FAIL"):
            _fail("GRID_OUTPUT_INVALID")
        if self.reason_code not in NUMERICAL_ADAPTER_REASON_CODES:
            _fail("GRID_OUTPUT_INVALID")
        if type(self.outputs) is not tuple:
            _fail("GRID_OUTPUT_INVALID")
        if self.outcome == "PASS":
            if self.reason_code != "NODE_OK":
                _fail("GRID_OUTPUT_INVALID")
            normalized_outputs = _validated_outputs(self.outputs)
            object.__setattr__(self, "outputs", normalized_outputs)
        elif self.reason_code == "NODE_OK" or self.outputs:
            _fail("GRID_OUTPUT_INVALID")


@_dataclass(frozen=True, slots=True)
class GridEvaluation:
    """Complete retained grid evidence with explicit count invariants."""

    records: tuple[NodeRecord, ...]
    requested_nodes: int
    pass_count: int
    fail_count: int

    def __post_init__(self) -> None:
        if type(self.records) is not tuple or any(
            not isinstance(record, NodeRecord) for record in self.records
        ):
            _fail("GRID_OUTPUT_INVALID")
        if tuple(record.node.ordinal for record in self.records) != tuple(range(len(self.records))):
            _fail("GRID_OUTPUT_INVALID")
        if any(
            isinstance(value, bool) or type(value) is not int or value < 0
            for value in (self.requested_nodes, self.pass_count, self.fail_count)
        ):
            _fail("GRID_OUTPUT_INVALID")
        observed_passes = sum(record.outcome == "PASS" for record in self.records)
        observed_failures = sum(record.outcome == "FAIL" for record in self.records)
        if (
            self.requested_nodes != len(self.records)
            or self.pass_count != observed_passes
            or self.fail_count != observed_failures
            or self.pass_count + self.fail_count != self.requested_nodes
        ):
            _fail("GRID_OUTPUT_INVALID")


def build_axis(name: object, values: object) -> AxisSpec:
    """Build one validated axis without coercing mutable containers."""

    return AxisSpec(name=name, values=values)  # type: ignore[arg-type]


def _validated_axes(axes: object) -> tuple[AxisSpec, ...]:
    if type(axes) is not tuple:
        _fail("GRID_AXIS_CONTAINER_INVALID")
    if not axes:
        _fail("GRID_AXES_EMPTY")
    names: set[str] = set()
    for axis in axes:
        if not isinstance(axis, AxisSpec):
            _fail("GRID_AXIS_CONTAINER_INVALID")
        if axis.name in names:
            _fail("GRID_AXIS_DUPLICATE_NAME")
        names.add(axis.name)
    return axes


def _validated_max_nodes(max_nodes: object) -> int:
    if (
        isinstance(max_nodes, bool)
        or type(max_nodes) is not int
        or max_nodes <= 0
        or max_nodes > _ABSOLUTE_MAX_NODES
    ):
        _fail("GRID_MAX_NODES_INVALID")
    return max_nodes


def build_cartesian_nodes(
    axes: object,
    *,
    max_nodes: object,
) -> tuple[GridNode, ...]:
    """Build a bounded Cartesian product; the final axis advances fastest."""

    validated_axes = _validated_axes(axes)
    ceiling = _validated_max_nodes(max_nodes)
    node_count = 1
    for axis in validated_axes:
        node_count *= len(axis.values)
        if node_count > ceiling:
            _fail("GRID_NODE_LIMIT_EXCEEDED")

    coordinates: list[tuple[tuple[str, float], ...]] = [tuple()]
    for axis in validated_axes:
        coordinates = [
            prefix + ((axis.name, value),)
            for prefix in coordinates
            for value in axis.values
        ]
    return tuple(
        GridNode(ordinal=ordinal, coordinates=coordinate)
        for ordinal, coordinate in enumerate(coordinates)
    )


def _validated_outputs(value: object) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple or not value:
        _fail("GRID_OUTPUT_INVALID")
    result: list[tuple[str, float]] = []
    previous_name: str | None = None
    seen: set[str] = set()
    for pair in value:
        if type(pair) is not tuple or len(pair) != 2:
            _fail("GRID_OUTPUT_INVALID")
        name = _canonical_name(pair[0], "GRID_OUTPUT_KEY_INVALID")
        if name in seen:
            _fail("GRID_OUTPUT_KEY_DUPLICATE")
        if previous_name is not None:
            if name < previous_name:
                _fail("GRID_OUTPUT_KEY_UNSORTED")
        number = _binary64(
            pair[1],
            invalid_reason="GRID_OUTPUT_VALUE_INVALID",
            nonfinite_reason="GRID_OUTPUT_VALUE_NONFINITE",
            overflow_reason="GRID_OUTPUT_VALUE_OVERFLOW",
        )
        result.append((name, number))
        seen.add(name)
        previous_name = name
    return tuple(result)


def evaluate_cartesian_grid(
    axes: object,
    evaluator: object,
    *,
    max_nodes: object,
) -> GridEvaluation:
    """Evaluate every requested node while retaining expected failures.

    The evaluator receives a :class:`GridNode` and must return an immutable,
    strictly name-sorted tuple of ``(name, finite_number)`` pairs.  Only
    :class:`NumericalAdapterError` is converted into a ``FAIL`` record.
    Unexpected exceptions propagate to the caller.
    """

    if not callable(evaluator):
        _fail("GRID_EVALUATOR_INVALID")
    nodes = build_cartesian_nodes(axes, max_nodes=max_nodes)
    records: list[NodeRecord] = []
    callback = evaluator  # keep the dynamic boundary in one local name
    for node in nodes:
        try:
            raw_outputs = callback(node)  # type: ignore[operator]
        except ExpectedNodeFailure as error:
            records.append(
                NodeRecord(
                    node=node,
                    outcome="FAIL",
                    reason_code=error.reason_code,
                    outputs=tuple(),
                )
            )
        else:
            # Output/schema corruption is a case-level contract breach, not an
            # expected solver-domain node failure.  Validate outside the catch.
            outputs = _validated_outputs(raw_outputs)
            records.append(
                NodeRecord(
                    node=node,
                    outcome="PASS",
                    reason_code="NODE_OK",
                    outputs=outputs,
                )
            )
    immutable_records = tuple(records)
    pass_count = sum(record.outcome == "PASS" for record in immutable_records)
    fail_count = len(immutable_records) - pass_count
    return GridEvaluation(
        records=immutable_records,
        requested_nodes=len(nodes),
        pass_count=pass_count,
        fail_count=fail_count,
    )


__all__ = (
    "NUMERICAL_ADAPTER_REASON_CODES",
    "NumericalAdapterError",
    "ExpectedNodeFailure",
    "AxisSpec",
    "GridNode",
    "NodeRecord",
    "GridEvaluation",
    "build_axis",
    "build_cartesian_nodes",
    "evaluate_cartesian_grid",
)
