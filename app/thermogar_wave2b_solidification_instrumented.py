"""Append-only INTERNAL solidification instrumentation for scheil 0.3.0.

This module is deliberately import-safe.  The scientific stack is imported
only after an exact active ``ExecutionLease``/PRE/domain binding has passed.
The numerical loop is a small callback-oriented port of the two algorithms in
``scheil.simulate`` 0.3.0.  The installed upstream file and license are hashed
before every public execution; source drift fails closed before a database is
opened.

Steel is mandatory product scope.  The two Fe profiles remain separate,
neither is selected as a baseline, and C15_LAVES must remain candidate,
requested, effective, and unexcluded while the product decision is pending.

This file contains a modified/ported substantial portion of scheil 0.3.0.
The required upstream MIT notice is preserved verbatim below.

The MIT License (MIT)

Copyright (c) 2017-2020 Richard Otis
Copyright (c) 2018-2020 Brandon Bocklund
Copyright (c) 2019-2020 Materials Genome Foundation

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass, field as _field
import hashlib as _hashlib
import importlib as _importlib
import importlib.metadata as _metadata
import json as _json
import math as _math
from pathlib import Path as _Path
import re as _re
import struct as _struct
import unicodedata as _unicodedata
from types import MappingProxyType as _MappingProxyType
from typing import Mapping as _Mapping, Protocol as _Protocol

import thermogar_wave2b_path_adapters as _path
import thermogar_wave2b_receipts as _receipts
import thermogar_wave2b_solidification_backend as _binding


TRACE_SCHEMA = "THERMOGAR-WAVE2B-SOLIDIFICATION-INSTRUMENTED-TRACE-2"
EVENT_SCHEMA = "THERMOGAR-WAVE2B-SOLIDIFICATION-INSTRUMENTED-EVENT-2"
INSTRUMENTATION_ID = "thermogar-scheil-0.3.0-callback-port"
INSTRUMENTATION_VERSION = "1.8.0-internal"
INSTRUMENTATION_NORMALIZED_SOURCE_SHA256 = "5959270fb197d64e7f005740dc03705c86705d05615f880c54b3d058d54125e1"
UPSTREAM_PACKAGE = "scheil"
UPSTREAM_VERSION = "0.3.0"
UPSTREAM_SOURCE_RELATIVE_PATH = "scheil/simulate.py"
UPSTREAM_SOURCE_SHA256 = (
    "cfa993ee23db7c32c6870f61b25ce20536e7397ba9b6e745609c107757fb3d17"
)
UPSTREAM_ORDERING_RELATIVE_PATH = "scheil/ordering.py"
UPSTREAM_ORDERING_SHA256 = (
    "14fe3d4864aa4b082be4c546bf4e603ecdc8b843124406291529c842639c91ab"
)
UPSTREAM_UTILS_RELATIVE_PATH = "scheil/utils.py"
UPSTREAM_UTILS_SHA256 = (
    "c63a2bf89fd4c6d59f48f372606095b00eb39eb6eb00bf8bf0186852845695ce"
)
UPSTREAM_LICENSE_RELATIVE_PATH = "scheil-0.3.0.dist-info/licenses/LICENSE"
UPSTREAM_LICENSE_SHA256 = (
    "e5efe65c159d82cbef7bdac6916f057daacefff1b50a9de83519e8a3ade12e08"
)
PYCALPHAD_VERSION = "0.11.2"
NUMPY_VERSION = "2.4.6"
SCHEIL_PAYLOAD_FILE_COUNT = 12
SCHEIL_PAYLOAD_TOTAL_BYTES = 53_742
SCHEIL_PAYLOAD_MANIFEST_SHA256 = (
    "f5fefd3817841284be2235d9766e0e146324fb41848ffe8f4330c785f7d424f6"
)
PYCALPHAD_PAYLOAD_FILE_COUNT = 142
PYCALPHAD_PAYLOAD_TOTAL_BYTES = 12_487_300
PYCALPHAD_PAYLOAD_MANIFEST_SHA256 = (
    "c3bae5af766d1065b690aa66913d2beb232ec9db1733a5aba539ce4f2c702e03"
)
PYCALPHAD_DIRECT_SOURCE_PINS = _MappingProxyType(
    {
        "pycalphad/__init__.py": "08ea9d333b2c24a227aba4f00b80cd79c15e5096056c1976e7b75ce48d209ac4",
        "pycalphad/io/database.py": "d17626502e4f8e18aeb2152fe68091de05d2885cf5b732d376cd1635e7e5893e",
        "pycalphad/core/workspace.py": "b567955bc03fc2d9977976c02abefbed3221e1ddda2e91662ad5a81726a31a4d",
        "pycalphad/variables.py": "a65dfdb3d669d93b4293ee53eef9fa0981db38566c74a0a239883108f0844224",
        "pycalphad/core/utils.py": "1705991a0984401993805e7231278b1005ff7d1da984704132d28e163d3af258",
        "pycalphad/codegen/phase_record_factory.py": "227bcc476f17984297fc6a9c2e963169bebd3f4c77bd6101fb5b2f4a7b90dd93",
        "pycalphad/core/cache.py": "7579546d84338d7b3541bbaba07c067b7f237193e3f0083a49f398a49c219cfb",
    }
)
RUNTIME_TRUST_BOUNDARY = "PYTHON_SAME_PROCESS_MUTATION_NOT_A_SECURITY_BOUNDARY"
RNG_ALGORITHM = "NONE_ADAPTIVE_DISABLED"
RNG_SEED = None
ADAPTIVE_SAMPLE_SHA256 = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)
# Absolute binary64 bookkeeping tolerance for endpoint bounds and exact
# raw-instance partition/aggregation replay.  It is not a raw-normalization,
# solver, or stop tolerance.  Raw values are never clamped or normalized.
FRACTION_ROUNDOFF_POLICY_ID = (
    "SCHEIL-0.3.0-PYCALPHAD-0.11.2-BINARY64-FRACTION-RESIDUAL-1"
)
FRACTION_ROUNDOFF_ABS_TOLERANCE = 1e-12
# Frozen core path-contract physical balance tolerance.  This classifies
# whether a raw solver partition can support a terminal physical witness.
PHYSICAL_BALANCE_ABS_TOLERANCE = 1e-10
# A separately named solver-observation cap, never a physical tolerance.  It
# only permits the pinned upstream algorithm to retain/use finite raw rows
# whose normalization residual is too large for a physical-balance claim.
RAW_NORMALIZATION_OBSERVATION_CAP = 1e-8
SCHEIL_CLOSURE_EVIDENCE_POLICY_ID = (
    "SCHEIL-0.3.0-PYCALPHAD-0.11.2-PARTIAL-CLOSURE-RAW-EVIDENCE-1"
)
PHASE_MAPPING_POLICY_ID = (
    "SCHEIL-0.3.0-PYCALPHAD-0.11.2-RAW-INSTANCE-EFFECTIVE-PHASE-MAP-1"
)
ORDERING_RENAME_AUTHORITY_POLICY_ID = (
    "SCHEIL-0.3.0-NONEMPTY-ORDERING-MAPPING-FAIL-CLOSED-1"
)
SOLIDIFICATION_PRESSURE_PA = 101325.0
SUPPORTED_FE_PROFILE_IDS = ("thermogar_patch", "upstream_original")
STEEL_REQUIRED_PRODUCT_SCOPE = True
FE_BASELINE_PROFILE = None
FE_EXCLUSION_DECISION_MADE = False
COUNTS_TOWARD_FEATURE_COVERAGE = False
ACCEPTANCE_CLAIM = False
PRODUCTION_USE = "DENIED"
TRACE_SCOPE = "INTERNAL_QUALIFICATION_DIAGNOSTIC_ONLY"

_SHA256_RE = _re.compile(r"[0-9a-f]{64}")
_TOKEN_RE = _re.compile(r"[A-Z0-9][A-Z0-9_.:#-]{0,127}")
_PHASE_INSTANCE_RE = _re.compile(
    r"(?P<base>[A-Z0-9][A-Z0-9_.:-]{0,119})(?:#(?P<ordinal>[1-9][0-9]{0,6}))?"
)
_ID_RE = _re.compile(r"(?:point|step|probe|solver)-[0-9]{6}")
_MAX_CANONICAL_BYTES = 64 * 1024 * 1024
_MAX_FILE_BYTES = 2 * 1024 * 1024
_MAX_RUNTIME_FILE_BYTES = 8 * 1024 * 1024
_MAX_RUNTIME_PAYLOAD_BYTES = 64 * 1024 * 1024
_STEP_SCALE_FACTOR = 1.2
_MAXIMUM_STEP_SIZE_REDUCTION = 5.0
_INSTRUMENTATION_PIN_RE = _re.compile(
    rb'(?m)^INSTRUMENTATION_NORMALIZED_SOURCE_SHA256 = "[0-9a-f]{64}"$'
)
_PROFILE_ROLE_BY_ID = _MappingProxyType(
    {
        ("ni", "mc_ni_v2036"): "RELEASE_CANDIDATE_PENDING_NE04",
        ("al", "mc_al_v2037"): "RELEASE_CANDIDATE_PENDING_NE04",
        ("fe", "thermogar_patch"): "EVALUATION_PROFILE",
        ("fe", "upstream_original"): "DIAGNOSTIC_CONTROL",
    }
)
_ORDERING_MODEL_AUTHORITY_BY_RUNTIME_SHA256 = _MappingProxyType(
    {
        # Exact create_ordering_records results for the receipt-bound effective
        # solidification domains.  Serialization independently re-derives and
        # compares these rows through the pinned scheil primitive.
        "1882d841a337063e0585d261c690ae7e565838234e231e21b8541a5cb0dba391": (),
        "f9bdf21d434fbe78b5ef3f7f2de69763fa40b81335cdc58889907d41c80cd717": (),
        "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612": (),
        "f9375c3a7a8649bace698e2177f2cc964bce3f8a19f08ae05d88840abd77b112": (),
    }
)

_EVENT_KINDS = frozenset(
    {
        "RUN_START",
        "DATABASE_LOAD_BEGIN",
        "DATABASE_LOAD_RESULT",
        "SOLVER_PREPARE_BEGIN",
        "SOLVER_PREPARE_RESULT",
        "RUN_ERROR",
        "SYNTHETIC_INITIAL_INSERTION",
        "SOLVER_CALL_BEGIN",
        "SOLVER_CALL_RESULT",
        "SOLVER_CALL_ERROR",
        "NO_LIQUID_FAILURE",
        "PHYSICAL_VALIDATION_FAILURE",
        "NO_CALCULATION_FAILURE",
        "ACCEPTED_PHYSICAL_POINT",
        "COOLING_STEP",
        "BINARY_SEARCH_BEGIN",
        "BINARY_SEARCH_PROBE",
        "BINARY_SEARCH_DIRECTION",
        "BINARY_SEARCH_END",
        "BACKTRACK",
        "STEP_REDUCTION",
        "STEP_REDUCTION_LIMIT",
        "SERVICE_CLOSURE",
        "BUDGET_EXHAUSTED",
        "TERMINATION",
    }
)
_STAGES = frozenset(
    {
        "RUN",
        "DATABASE_LOAD",
        "SOLVER_PREPARE",
        "DISPATCH",
        "FINALIZE",
        "INITIAL",
        "COOLING",
        "BINARY_SEARCH",
        "SERVICE_CLOSURE",
        "TERMINATION",
    }
)
_OUTCOMES = frozenset(
    {
        "BEGIN",
        "SUCCESS",
        "ERROR",
        "INSERTED",
        "LIQUID_PRESENT",
        "NO_LIQUID",
        "NO_PHASES",
        "ACCEPTED",
        "ALGORITHM_ACCEPTED_WITH_RAW_NORMALIZATION_RESIDUAL",
        "DECREASED",
        "STARTED",
        "PROBED",
        "UPDATE_HIGH",
        "UPDATE_LOW",
        "FINISHED",
        "BACKTRACKED",
        "REDUCED",
        "LIMIT_REACHED",
        "CLOSED",
        "CONVERGED",
        "STOP_CRITERION_REACHED_PARTIAL",
        "NOT_CONVERGED",
        "BUDGET_EXHAUSTED",
        "BOUND_REACHED",
    }
)

_REASONS = {
    "W2B_INSTRUMENT_CONTEXT_INVALID": "Exact INTERNAL receipt/domain/PRE/lease binding required.",
    "W2B_INSTRUMENT_SOURCE_DRIFT": "Installed scheil 0.3.0 source identity differs from the pinned port source.",
    "W2B_INSTRUMENT_LICENSE_DRIFT": "Installed scheil license identity differs from the preserved notice.",
    "W2B_INSTRUMENT_RUNTIME_VERSION": "Exact scheil 0.3.0 and pycalphad 0.11.2 runtimes are required.",
    "W2B_INSTRUMENT_REQUEST_INVALID": "Solidification request is invalid or differs from the bound domain.",
    "W2B_INSTRUMENT_FE_POLICY": "Fe requires one explicit profile with C15_LAVES retained and no baseline decision.",
    "W2B_INSTRUMENT_DATABASE_LOAD": "The locked runtime database snapshot could not be loaded.",
    "W2B_INSTRUMENT_SOLVER_ERROR": "A solver call raised; the failure is retained in the trace.",
    "W2B_INSTRUMENT_OBSERVATION_INVALID": "A solver observation cannot be represented without inference.",
    "W2B_INSTRUMENT_EVENT_BUDGET": "The deterministic event budget was exhausted.",
    "W2B_INSTRUMENT_SOLVER_BUDGET": "The deterministic solver-call budget was exhausted.",
    "W2B_INSTRUMENT_COOLING_BUDGET": "The deterministic cooling-step budget was exhausted.",
    "W2B_INSTRUMENT_BINARY_BUDGET": "The deterministic binary-probe budget was exhausted.",
    "W2B_INSTRUMENT_TEMPERATURE_BOUND": "The receipt-bound minimum temperature was reached before termination.",
    "W2B_INSTRUMENT_NO_CALCULATION": "No Scheil workspace calculation converged before service closure.",
    "W2B_INSTRUMENT_INITIAL_LIQUID_REQUIRED": "The receipt maximum/start temperature did not contain the required liquid phase.",
    "W2B_INSTRUMENT_STEP_REDUCTION_LIMIT": "The scheil 0.3.0 step-reduction limit was exceeded.",
    "W2B_INSTRUMENT_ADAPTIVE_UNSUPPORTED": "Adaptive sampling is denied because no isolated explicit RNG contract exists.",
    "W2B_INSTRUMENT_AMBIENT_RNG_MUTATION": "The scientific execution changed ambient NumPy RNG state.",
    "W2B_INSTRUMENT_RUN_ERROR": "A non-solver execution stage raised; the original bounded exception card is retained.",
    "W2B_INSTRUMENT_STOP_CRITERION_REACHED_PARTIAL": "The requested Scheil liquid-fraction stop criterion was reached; this is partial, not complete phase balance.",
        "W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID": "A raw phase-fraction bound or balance residual exceeds the pinned finite binary64 roundoff tolerance.",
    "W2B_INSTRUMENT_PHYSICAL_WITNESS_INVALID": "A solver result is retained but cannot be accepted as physical phase-domain/conservation evidence.",
    "W2B_INSTRUMENT_ORDERING_MAPPING_UNREPRESENTABLE": "A non-empty order/disorder rename requires exact Y/site-fraction replay evidence not present in this trace schema.",
}
INSTRUMENTATION_REASON_CODES: _Mapping[str, str] = _MappingProxyType(_REASONS)
del _REASONS


def _capture_fixed_authority() -> tuple[object, ...]:
    """Capture immutable policy/schema authority once during import.

    Exported constants remain compatibility names.  Ordinary module rebinding
    can neither authorize a different grammar/policy nor change serialized
    bytes: public constructors and canonical serialization verify the captured
    exports, while emitters read only these closure-owned values.
    """

    values = {
        "trace_schema": "THERMOGAR-WAVE2B-SOLIDIFICATION-INSTRUMENTED-TRACE-2",
        "event_schema": "THERMOGAR-WAVE2B-SOLIDIFICATION-INSTRUMENTED-EVENT-2",
        "instrumentation_id": "thermogar-scheil-0.3.0-callback-port",
        "instrumentation_version": "1.8.0-internal",
        "instrumentation_normalized_source_sha256": (
            INSTRUMENTATION_NORMALIZED_SOURCE_SHA256
        ),
        "upstream_package": "scheil",
        "upstream_version": "0.3.0",
        "upstream_source_relative_path": "scheil/simulate.py",
        "upstream_source_sha256": (
            "cfa993ee23db7c32c6870f61b25ce20536e7397ba9b6e745609c107757fb3d17"
        ),
        "upstream_ordering_relative_path": "scheil/ordering.py",
        "upstream_ordering_sha256": (
            "14fe3d4864aa4b082be4c546bf4e603ecdc8b843124406291529c842639c91ab"
        ),
        "upstream_utils_relative_path": "scheil/utils.py",
        "upstream_utils_sha256": (
            "c63a2bf89fd4c6d59f48f372606095b00eb39eb6eb00bf8bf0186852845695ce"
        ),
        "upstream_license_relative_path": (
            "scheil-0.3.0.dist-info/licenses/LICENSE"
        ),
        "upstream_license_sha256": (
            "e5efe65c159d82cbef7bdac6916f057daacefff1b50a9de83519e8a3ade12e08"
        ),
        "pycalphad_version": "0.11.2",
        "numpy_version": "2.4.6",
        "scheil_payload_file_count": 12,
        "scheil_payload_total_bytes": 53_742,
        "scheil_payload_manifest_sha256": (
            "f5fefd3817841284be2235d9766e0e146324fb41848ffe8f4330c785f7d424f6"
        ),
        "pycalphad_payload_file_count": 142,
        "pycalphad_payload_total_bytes": 12_487_300,
        "pycalphad_payload_manifest_sha256": (
            "c3bae5af766d1065b690aa66913d2beb232ec9db1733a5aba539ce4f2c702e03"
        ),
        "runtime_trust_boundary": (
            "PYTHON_SAME_PROCESS_MUTATION_NOT_A_SECURITY_BOUNDARY"
        ),
        "rng_algorithm": "NONE_ADAPTIVE_DISABLED",
        "rng_seed": None,
        "adaptive_sample_sha256": (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ),
        "fraction_roundoff_policy_id": (
            "SCHEIL-0.3.0-PYCALPHAD-0.11.2-BINARY64-FRACTION-RESIDUAL-1"
        ),
        "fraction_roundoff_abs_tolerance": 1e-12,
        "physical_balance_abs_tolerance": 1e-10,
        "raw_normalization_observation_cap": 1e-8,
        "scheil_closure_evidence_policy_id": (
            "SCHEIL-0.3.0-PYCALPHAD-0.11.2-PARTIAL-CLOSURE-RAW-EVIDENCE-1"
        ),
        "scheil_closure_evidence_classifications": frozenset(
            {
                "POSITIVE_ZERO",
                "NEGATIVE_ZERO",
                "POSITIVE_IN_UNIT_INTERVAL",
                "NEGATIVE_WITHIN_ACCEPTED_POINT_OBSERVATION_BUDGET",
                "ABOVE_ONE_WITHIN_ACCEPTED_POINT_OBSERVATION_BUDGET",
            }
        ),
        "phase_mapping_policy_id": (
            "SCHEIL-0.3.0-PYCALPHAD-0.11.2-RAW-INSTANCE-EFFECTIVE-PHASE-MAP-1"
        ),
        "ordering_rename_authority_policy_id": (
            "SCHEIL-0.3.0-NONEMPTY-ORDERING-MAPPING-FAIL-CLOSED-1"
        ),
        "solidification_pressure_pa": 101325.0,
        "supported_fe_profile_ids": ("thermogar_patch", "upstream_original"),
        "steel_required_product_scope": True,
        "fe_baseline_profile": None,
        "fe_exclusion_decision_made": False,
        "counts_toward_feature_coverage": False,
        "acceptance_claim": False,
        "production_use": "DENIED",
        "trace_scope": "INTERNAL_QUALIFICATION_DIAGNOSTIC_ONLY",
        "c15_phase": "C15_LAVES",
    }
    profile_roles = {
        ("ni", "mc_ni_v2036"): "RELEASE_CANDIDATE_PENDING_NE04",
        ("al", "mc_al_v2037"): "RELEASE_CANDIDATE_PENDING_NE04",
        ("fe", "thermogar_patch"): "EVALUATION_PROFILE",
        ("fe", "upstream_original"): "DIAGNOSTIC_CONTROL",
    }
    feature_ids = frozenset(
        ("equilibrium_solidification", "scheil_solidification")
    )
    event_kinds = frozenset(_EVENT_KINDS)
    stages = frozenset(_STAGES)
    outcomes = frozenset(_OUTCOMES)
    ordering_models = {
        key: tuple(value)
        for key, value in _ORDERING_MODEL_AUTHORITY_BY_RUNTIME_SHA256.items()
    }
    reason_codes = frozenset(INSTRUMENTATION_REASON_CODES)
    expected_exports = {
        "TRACE_SCHEMA": TRACE_SCHEMA,
        "EVENT_SCHEMA": EVENT_SCHEMA,
        "INSTRUMENTATION_ID": INSTRUMENTATION_ID,
        "INSTRUMENTATION_VERSION": INSTRUMENTATION_VERSION,
        "INSTRUMENTATION_NORMALIZED_SOURCE_SHA256": (
            INSTRUMENTATION_NORMALIZED_SOURCE_SHA256
        ),
        "UPSTREAM_PACKAGE": UPSTREAM_PACKAGE,
        "UPSTREAM_VERSION": UPSTREAM_VERSION,
        "UPSTREAM_SOURCE_RELATIVE_PATH": UPSTREAM_SOURCE_RELATIVE_PATH,
        "UPSTREAM_SOURCE_SHA256": UPSTREAM_SOURCE_SHA256,
        "UPSTREAM_ORDERING_RELATIVE_PATH": UPSTREAM_ORDERING_RELATIVE_PATH,
        "UPSTREAM_ORDERING_SHA256": UPSTREAM_ORDERING_SHA256,
        "UPSTREAM_UTILS_RELATIVE_PATH": UPSTREAM_UTILS_RELATIVE_PATH,
        "UPSTREAM_UTILS_SHA256": UPSTREAM_UTILS_SHA256,
        "UPSTREAM_LICENSE_RELATIVE_PATH": UPSTREAM_LICENSE_RELATIVE_PATH,
        "UPSTREAM_LICENSE_SHA256": UPSTREAM_LICENSE_SHA256,
        "PYCALPHAD_VERSION": PYCALPHAD_VERSION,
        "NUMPY_VERSION": NUMPY_VERSION,
        "SCHEIL_PAYLOAD_FILE_COUNT": SCHEIL_PAYLOAD_FILE_COUNT,
        "SCHEIL_PAYLOAD_TOTAL_BYTES": SCHEIL_PAYLOAD_TOTAL_BYTES,
        "SCHEIL_PAYLOAD_MANIFEST_SHA256": SCHEIL_PAYLOAD_MANIFEST_SHA256,
        "PYCALPHAD_PAYLOAD_FILE_COUNT": PYCALPHAD_PAYLOAD_FILE_COUNT,
        "PYCALPHAD_PAYLOAD_TOTAL_BYTES": PYCALPHAD_PAYLOAD_TOTAL_BYTES,
        "PYCALPHAD_PAYLOAD_MANIFEST_SHA256": (
            PYCALPHAD_PAYLOAD_MANIFEST_SHA256
        ),
        "PYCALPHAD_DIRECT_SOURCE_PINS": PYCALPHAD_DIRECT_SOURCE_PINS,
        "RUNTIME_TRUST_BOUNDARY": RUNTIME_TRUST_BOUNDARY,
        "RNG_ALGORITHM": RNG_ALGORITHM,
        "RNG_SEED": RNG_SEED,
        "ADAPTIVE_SAMPLE_SHA256": ADAPTIVE_SAMPLE_SHA256,
        "FRACTION_ROUNDOFF_POLICY_ID": FRACTION_ROUNDOFF_POLICY_ID,
        "FRACTION_ROUNDOFF_ABS_TOLERANCE": FRACTION_ROUNDOFF_ABS_TOLERANCE,
        "PHYSICAL_BALANCE_ABS_TOLERANCE": PHYSICAL_BALANCE_ABS_TOLERANCE,
        "RAW_NORMALIZATION_OBSERVATION_CAP": (
            RAW_NORMALIZATION_OBSERVATION_CAP
        ),
        "SCHEIL_CLOSURE_EVIDENCE_POLICY_ID": (
            SCHEIL_CLOSURE_EVIDENCE_POLICY_ID
        ),
        "PHASE_MAPPING_POLICY_ID": PHASE_MAPPING_POLICY_ID,
        "ORDERING_RENAME_AUTHORITY_POLICY_ID": (
            ORDERING_RENAME_AUTHORITY_POLICY_ID
        ),
        "SOLIDIFICATION_PRESSURE_PA": SOLIDIFICATION_PRESSURE_PA,
        "SUPPORTED_FE_PROFILE_IDS": SUPPORTED_FE_PROFILE_IDS,
        "STEEL_REQUIRED_PRODUCT_SCOPE": STEEL_REQUIRED_PRODUCT_SCOPE,
        "FE_BASELINE_PROFILE": FE_BASELINE_PROFILE,
        "FE_EXCLUSION_DECISION_MADE": FE_EXCLUSION_DECISION_MADE,
        "COUNTS_TOWARD_FEATURE_COVERAGE": COUNTS_TOWARD_FEATURE_COVERAGE,
        "ACCEPTANCE_CLAIM": ACCEPTANCE_CLAIM,
        "PRODUCTION_USE": PRODUCTION_USE,
        "TRACE_SCOPE": TRACE_SCOPE,
        "_PROFILE_ROLE_BY_ID": _PROFILE_ROLE_BY_ID,
        "_ORDERING_MODEL_AUTHORITY_BY_RUNTIME_SHA256": (
            _ORDERING_MODEL_AUTHORITY_BY_RUNTIME_SHA256
        ),
        "_EVENT_KINDS": _EVENT_KINDS,
        "_STAGES": _STAGES,
        "_OUTCOMES": _OUTCOMES,
        "INSTRUMENTATION_REASON_CODES": INSTRUMENTATION_REASON_CODES,
    }
    namespace = globals()

    def value(name: str) -> object:
        return values[name]

    def profile_role(family: str, profile: str) -> str | None:
        return profile_roles.get((family, profile))

    def feature_allowed(feature_id: object) -> bool:
        return type(feature_id) is str and feature_id in feature_ids

    def event_allowed(kind: object, stage: object, outcome: object) -> bool:
        return (
            type(kind) is str
            and kind in event_kinds
            and type(stage) is str
            and stage in stages
            and type(outcome) is str
            and outcome in outcomes
        )

    def ordering_model(runtime_sha256: str) -> tuple[tuple[str, str], ...] | None:
        return ordering_models.get(runtime_sha256)

    def reason_allowed(reason_code: object) -> bool:
        return type(reason_code) is str and reason_code in reason_codes

    def exports_intact() -> bool:
        for name, expected in expected_exports.items():
            current = namespace.get(name)
            if type(current) is not type(expected):
                return False
            if type(expected) is _MappingProxyType:
                if dict(current) != dict(expected):
                    return False
            elif current != expected:
                return False
        return True

    return (
        value,
        profile_role,
        feature_allowed,
        event_allowed,
        ordering_model,
        reason_allowed,
        exports_intact,
    )


(
    _fixed_value,
    _fixed_profile_role,
    _fixed_feature_allowed,
    _fixed_event_allowed,
    _fixed_ordering_model,
    _fixed_reason_allowed,
    _fixed_exports_intact,
) = _capture_fixed_authority()
del _capture_fixed_authority


class SolidificationInstrumentationError(ValueError):
    """Fail-closed public error carrying one stable reason code."""

    __slots__ = ("reason_code",)

    def __init__(self, reason_code: str) -> None:
        if not _fixed_reason_allowed(reason_code):
            raise RuntimeError("Unknown solidification instrumentation reason")
        self.reason_code = reason_code
        super().__init__(reason_code)


def _fail(reason_code: str) -> None:
    raise SolidificationInstrumentationError(reason_code)


def _require_fixed_authority() -> None:
    if not _fixed_exports_intact():
        _fail("W2B_INSTRUMENT_CONTEXT_INVALID")


def _sha256(value: object) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
    return value


def _token(value: object, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    if type(value) is not str or _TOKEN_RE.fullmatch(value) is None:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    return value


def _optional_id(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str or _ID_RE.fullmatch(value) is None:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    return value


def _f64(value: object, *, allow_nonfinite: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise SolidificationInstrumentationError(
            "W2B_INSTRUMENT_OBSERVATION_INVALID"
        ) from error
    if not allow_nonfinite and not _math.isfinite(number):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    return number


def _optional_f64(value: object) -> float | None:
    return None if value is None else _f64(value)


def _names(value: object) -> tuple[str, ...]:
    if type(value) is not tuple:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    result: list[str] = []
    for item in value:
        checked = _token(item)
        assert checked is not None
        result.append(checked)
    return tuple(result)


def _numeric_pairs(value: object) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    result: list[tuple[str, float]] = []
    for item in value:
        if type(item) is not tuple or len(item) != 2:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        name = _token(item[0])
        assert name is not None
        result.append((name, _f64(item[1])))
    return tuple(result)


def _name_pairs(value: object) -> tuple[tuple[str, str], ...]:
    if type(value) is not tuple:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    result: list[tuple[str, str]] = []
    for item in value:
        if type(item) is not tuple or len(item) != 2:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        source = _token(item[0])
        target = _token(item[1])
        assert source is not None and target is not None
        result.append((source, target))
    return tuple(result)


def _ordering_authority_pairs(
    value: object,
) -> tuple[tuple[str, str], ...]:
    pairs = _name_pairs(value)
    if (
        pairs != tuple(sorted(pairs))
        or len(pairs) != len(set(pairs))
        or len({source for source, _target in pairs}) != len(pairs)
        or any(source == target for source, target in pairs)
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    return pairs


def _phase_instance_sort_key(value: str) -> tuple[str, int, int]:
    parsed = _phase_instance_parts(value)
    if parsed is None:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    base, ordinal = parsed
    return (
        base,
        0 if ordinal is None else 1,
        0 if ordinal is None else ordinal,
    )


def _ordering_instance_authority_pairs(
    value: object,
) -> tuple[tuple[str, str], ...]:
    pairs = _name_pairs(value)
    expected = tuple(
        sorted(pairs, key=lambda pair: _phase_instance_sort_key(pair[0]))
    )
    if (
        pairs != expected
        or len(pairs) != len(set(pairs))
        or len({source for source, _target in pairs}) != len(pairs)
        or any(
            _phase_instance_sort_key(source)[0] == target
            for source, target in pairs
        )
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    return pairs


def _ordering_authority_digest(
    *,
    profile_receipt_digest: str,
    domain_receipt_digest: str,
    pairs: tuple[tuple[str, str], ...],
) -> str:
    return _hashlib.sha256(
        _canonical_bytes(
            {
                "policy_id": _fixed_value(
                    "ordering_rename_authority_policy_id"
                ),
                "upstream_ordering_sha256": _fixed_value(
                    "upstream_ordering_sha256"
                ),
                "profile_receipt_digest": profile_receipt_digest,
                "domain_receipt_digest": domain_receipt_digest,
                "allowed_ordered_to_disordered_pairs": [
                    {"ordered_phase": source, "disordered_phase": target}
                    for source, target in pairs
                ],
            }
        )
    ).hexdigest()


def _same_optional_f64(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return left is right
    return _struct.pack(">d", left) == _struct.pack(">d", right)


def _same_f64(left: float, right: float) -> bool:
    return _struct.pack(">d", left) == _struct.pack(">d", right)


def _same_numeric_pairs(
    left: tuple[tuple[str, float], ...],
    right: tuple[tuple[str, float], ...],
) -> bool:
    return len(left) == len(right) and all(
        left_name == right_name
        and _struct.pack(">d", left_value) == _struct.pack(">d", right_value)
        for (left_name, left_value), (right_name, right_value) in zip(left, right)
    )


def _exception_card(error: Exception) -> tuple[str, str, str]:
    error_type = type(error)
    try:
        module_name = getattr(error_type, "__module__", "UNKNOWN")
    except BaseException:
        module_name = "UNKNOWN"
    try:
        qualified_name = getattr(error_type, "__qualname__", "UNKNOWN")
    except BaseException:
        qualified_name = "UNKNOWN"
    if type(module_name) is not str:
        module_name = "UNKNOWN"
    if type(qualified_name) is not str:
        qualified_name = "UNKNOWN"
    raw_name = f"{module_name}.{qualified_name}"
    type_digest = _hashlib.sha256(
        raw_name.encode("utf-8", errors="backslashreplace")
    ).hexdigest()
    safe_name = _re.sub(r"[^A-Za-z0-9_.:-]", "_", raw_name)
    if not safe_name:
        safe_name = "UNKNOWN_EXCEPTION"
    if len(safe_name) > 160:
        safe_name = f"{safe_name[:128]}#{type_digest[:16]}"
    try:
        message = str(error)
    except BaseException:
        message = "<UNPRINTABLE_EXCEPTION_MESSAGE>"
    encoded = message.encode("utf-8", errors="backslashreplace")
    return safe_name, type_digest, _hashlib.sha256(encoded).hexdigest()


def _canonical_value(value: object, depth: int = 0) -> object:
    if depth > 32:
        _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        if not -(2**63) <= value < 2**63:
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        return value
    if type(value) is float:
        # Every binary64 bit pattern, including signed zero and NaN payloads,
        # is retained as bytes.  No arithmetic normalization occurs here.
        return {"$f64": _struct.pack(">d", value).hex()}
    if type(value) is str:
        if len(value) > _MAX_FILE_BYTES or _unicodedata.normalize("NFC", value) != value:
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        return value
    if type(value) in (tuple, list):
        return [_canonical_value(item, depth + 1) for item in value]
    if type(value) is dict:
        result: dict[str, object] = {}
        for key, item in value.items():
            if type(key) is not str or key == "$f64":
                _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
            result[key] = _canonical_value(item, depth + 1)
        return result
    _fail("W2B_INSTRUMENT_CONTEXT_INVALID")


def _canonical_bytes(value: object) -> bytes:
    encoded = (
        _json.dumps(
            _canonical_value(value),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    if len(encoded) > _MAX_CANONICAL_BYTES:
        _fail("W2B_INSTRUMENT_EVENT_BUDGET")
    return encoded


def _hash_regular_file(path: _Path, *, maximum: int, reason: str) -> tuple[str, int]:
    try:
        resolved = path.resolve(strict=True)
        before = resolved.stat()
        if not resolved.is_file() or before.st_nlink != 1 or before.st_size > maximum:
            _fail(reason)
        digest = _hashlib.sha256()
        size = 0
        with resolved.open("rb") as stream:
            while True:
                block = stream.read(65_536)
                if not block:
                    break
                size += len(block)
                if size > maximum:
                    _fail(reason)
                digest.update(block)
        after = resolved.stat()
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_nlink,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_nlink,
        )
        if identity_before != identity_after or size != before.st_size:
            _fail(reason)
        return digest.hexdigest(), size
    except SolidificationInstrumentationError:
        raise
    except Exception as error:
        raise SolidificationInstrumentationError(reason) from error


def _read_regular_file(path: _Path, *, maximum: int, reason: str) -> bytes:
    try:
        resolved = path.resolve(strict=True)
        before = resolved.stat()
        if not resolved.is_file() or before.st_nlink != 1 or before.st_size > maximum:
            _fail(reason)
        with resolved.open("rb") as stream:
            payload = stream.read(maximum + 1)
        after = resolved.stat()
        if (
            len(payload) > maximum
            or len(payload) != before.st_size
            or (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_nlink,
            )
            != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_nlink,
            )
        ):
            _fail(reason)
        return payload
    except SolidificationInstrumentationError:
        raise
    except Exception as error:
        raise SolidificationInstrumentationError(reason) from error


def _verify_instrumentation_source_pin(
    expected_raw_sha256: str | None = None,
) -> tuple[str, str]:
    _require_fixed_authority()
    payload = _read_regular_file(
        _Path(__file__),
        maximum=_MAX_FILE_BYTES,
        reason="W2B_INSTRUMENT_SOURCE_DRIFT",
    )
    replacement = (
        b'INSTRUMENTATION_NORMALIZED_SOURCE_SHA256 = "'
        + (b"0" * 64)
        + b'"'
    )
    normalized, substitutions = _INSTRUMENTATION_PIN_RE.subn(replacement, payload)
    if substitutions != 1:
        _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
    raw_digest = _hashlib.sha256(payload).hexdigest()
    normalized_digest = _hashlib.sha256(normalized).hexdigest()
    if normalized_digest != _fixed_value(
        "instrumentation_normalized_source_sha256"
    ):
        _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
    if expected_raw_sha256 is not None:
        _sha256(expected_raw_sha256)
        if raw_digest != expected_raw_sha256:
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
    return raw_digest, normalized_digest


def _distribution_payload_manifest(
    distribution: object,
    *,
    prefixes: tuple[str, ...],
    reason: str,
) -> tuple[str, int, int]:
    try:
        distribution_root = _Path(distribution.locate_file("")).resolve(strict=True)
        files = distribution.files
        if files is None:
            _fail(reason)
        rows: list[tuple[str, int, str]] = []
        total_bytes = 0
        for entry in files:
            relative = str(entry).replace("\\", "/")
            if not any(relative.startswith(prefix) for prefix in prefixes):
                continue
            if (
                relative.endswith((".pyc", ".pyo"))
                or "/__pycache__/" in relative
                or relative.startswith("/")
                or ".." in relative.split("/")
            ):
                continue
            relative.encode("ascii")
            path = _Path(distribution.locate_file(entry)).resolve(strict=True)
            if not path.is_relative_to(distribution_root) or not path.is_file():
                _fail(reason)
            digest, size = _hash_regular_file(
                path,
                maximum=_MAX_RUNTIME_FILE_BYTES,
                reason=reason,
            )
            total_bytes += size
            if total_bytes > _MAX_RUNTIME_PAYLOAD_BYTES:
                _fail(reason)
            rows.append((relative, size, digest))
        rows.sort()
        manifest = b"".join(
            relative.encode("ascii")
            + b"\0"
            + str(size).encode("ascii")
            + b"\0"
            + digest.encode("ascii")
            + b"\n"
            for relative, size, digest in rows
        )
        return _hashlib.sha256(manifest).hexdigest(), len(rows), total_bytes
    except SolidificationInstrumentationError:
        raise
    except Exception as error:
        raise SolidificationInstrumentationError(reason) from error


@_dataclass(frozen=True, slots=True)
class InstrumentationBudget:
    max_events: int = 20_000
    max_solver_calls: int = 5_000
    max_cooling_steps: int = 5_000
    max_binary_probes: int = 2_000

    def __post_init__(self) -> None:
        limits = (
            (self.max_events, 16, 50_000),
            (self.max_solver_calls, 1, 20_000),
            (self.max_cooling_steps, 1, 20_000),
            (self.max_binary_probes, 1, 20_000),
        )
        if any(
            type(value) is not int or isinstance(value, bool) or not low <= value <= high
            for value, low, high in limits
        ):
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")


def _copy_budget(value: object) -> InstrumentationBudget:
    if type(value) is not InstrumentationBudget:
        _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
    try:
        return InstrumentationBudget(
            max_events=value.max_events,
            max_solver_calls=value.max_solver_calls,
            max_cooling_steps=value.max_cooling_steps,
            max_binary_probes=value.max_binary_probes,
        )
    except Exception as error:
        raise SolidificationInstrumentationError("W2B_INSTRUMENT_CONTEXT_INVALID") from error


_BOUND_CLASSIFICATIONS = frozenset(
    {
        "IN_RANGE",
        "BELOW_ZERO_WITHIN_TOLERANCE",
        "ABOVE_ONE_WITHIN_TOLERANCE",
        "BELOW_ZERO_WITHIN_OBSERVATION_CAP",
        "ABOVE_ONE_WITHIN_OBSERVATION_CAP",
    }
)
_BALANCE_CLASSIFICATIONS = frozenset({"EXACT", "WITHIN_TOLERANCE"})


def _fraction_bound_classification(value: float, tolerance: float) -> str:
    if not _math.isfinite(value):
        _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
    if value < 0.0:
        excursion = abs(value)
        if excursion > _fixed_value("raw_normalization_observation_cap"):
            _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
        return (
            "BELOW_ZERO_WITHIN_TOLERANCE"
            if excursion <= tolerance
            else "BELOW_ZERO_WITHIN_OBSERVATION_CAP"
        )
    if value > 1.0:
        excursion = abs(value - 1.0)
        if excursion > _fixed_value("raw_normalization_observation_cap"):
            _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
        return (
            "ABOVE_ONE_WITHIN_TOLERANCE"
            if excursion <= tolerance
            else "ABOVE_ONE_WITHIN_OBSERVATION_CAP"
        )
    return "IN_RANGE"


def _closure_evidence_excursion_cap(accepted_point_count: int) -> float:
    """Return the explicit raw-evidence excursion budget for Scheil closure.

    Each accepted algorithm point may carry at most the pinned raw
    normalization observation residual. Closure replays that append-only
    history, so its signed excursion budget is the sum of those per-point
    budgets plus one binary64 bookkeeping tolerance. This is evidence
    retention only, never a physical-balance tolerance.
    """

    if (
        type(accepted_point_count) is not int
        or isinstance(accepted_point_count, bool)
        or not 1 <= accepted_point_count <= 20_000
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    cap = (
        _fixed_value("fraction_roundoff_abs_tolerance")
        + accepted_point_count
        * _fixed_value("raw_normalization_observation_cap")
    )
    if not _math.isfinite(cap) or cap <= 0.0:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    return cap


def _closure_evidence_classification(value: float, excursion_cap: float) -> str:
    """Classify one exact signed raw closure value without changing it."""

    if (
        type(value) is not float
        or type(excursion_cap) is not float
        or not _math.isfinite(value)
        or not _math.isfinite(excursion_cap)
        or excursion_cap <= 0.0
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    if value == 0.0:
        classification = (
            "NEGATIVE_ZERO"
            if _struct.pack(">d", value)[0] & 0x80
            else "POSITIVE_ZERO"
        )
    elif 0.0 < value <= 1.0:
        classification = "POSITIVE_IN_UNIT_INTERVAL"
    elif value < 0.0 and abs(value) <= excursion_cap:
        classification = (
            "NEGATIVE_WITHIN_ACCEPTED_POINT_OBSERVATION_BUDGET"
        )
    elif value > 1.0 and value - 1.0 <= excursion_cap:
        classification = (
            "ABOVE_ONE_WITHIN_ACCEPTED_POINT_OBSERVATION_BUDGET"
        )
    else:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    if classification not in _fixed_value(
        "scheil_closure_evidence_classifications"
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    return classification


@_dataclass(frozen=True, slots=True)
class FractionResidualCard:
    policy_id: str
    solver_package: str
    solver_version: str
    upstream_package: str
    upstream_version: str
    feature_id: str
    absolute_tolerance: float
    solid_fraction_raw: float
    liquid_fraction_raw: float
    balance_residual_raw: float
    solid_bound_classification: str
    liquid_bound_classification: str
    balance_classification: str
    bounded_roundoff_present: bool

    def __post_init__(self) -> None:
        _require_fixed_authority()
        if (
            type(self.policy_id) is not str
            or type(self.solver_package) is not str
            or type(self.solver_version) is not str
            or type(self.upstream_package) is not str
            or type(self.upstream_version) is not str
            or type(self.feature_id) is not str
            or type(self.solid_bound_classification) is not str
            or type(self.liquid_bound_classification) is not str
            or type(self.balance_classification) is not str
            or self.policy_id != _fixed_value("fraction_roundoff_policy_id")
            or self.solver_package != "pycalphad"
            or self.solver_version != _fixed_value("pycalphad_version")
            or self.upstream_package != _fixed_value("upstream_package")
            or self.upstream_version != _fixed_value("upstream_version")
            or not _fixed_feature_allowed(self.feature_id)
            or self.solid_bound_classification not in _BOUND_CLASSIFICATIONS
            or self.liquid_bound_classification not in _BOUND_CLASSIFICATIONS
            or self.balance_classification not in _BALANCE_CLASSIFICATIONS
            or type(self.bounded_roundoff_present) is not bool
            or type(self.absolute_tolerance) is not float
            or type(self.solid_fraction_raw) is not float
            or type(self.liquid_fraction_raw) is not float
            or type(self.balance_residual_raw) is not float
        ):
            _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
        tolerance = _f64(self.absolute_tolerance, allow_nonfinite=False)
        solid = _f64(self.solid_fraction_raw, allow_nonfinite=False)
        liquid = _f64(self.liquid_fraction_raw, allow_nonfinite=False)
        residual = _f64(self.balance_residual_raw, allow_nonfinite=False)
        if not _same_f64(
            tolerance,
            _fixed_value("fraction_roundoff_abs_tolerance"),
        ):
            _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
        solid_classification = _fraction_bound_classification(solid, tolerance)
        liquid_classification = _fraction_bound_classification(liquid, tolerance)
        computed_residual = (solid + liquid) - 1.0
        if (
            not _math.isfinite(computed_residual)
            or abs(computed_residual) > tolerance
            or not _same_f64(residual, computed_residual)
        ):
            _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
        balance_classification = (
            "EXACT" if computed_residual == 0.0 else "WITHIN_TOLERANCE"
        )
        bounded = (
            solid_classification != "IN_RANGE"
            or liquid_classification != "IN_RANGE"
            or balance_classification != "EXACT"
        )
        if (
            self.solid_bound_classification != solid_classification
            or self.liquid_bound_classification != liquid_classification
            or self.balance_classification != balance_classification
            or self.bounded_roundoff_present is not bounded
        ):
            _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
        object.__setattr__(self, "absolute_tolerance", tolerance)
        object.__setattr__(self, "solid_fraction_raw", solid)
        object.__setattr__(self, "liquid_fraction_raw", liquid)
        object.__setattr__(self, "balance_residual_raw", residual)

    def as_dict(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "solver_package": self.solver_package,
            "solver_version": self.solver_version,
            "upstream_package": self.upstream_package,
            "upstream_version": self.upstream_version,
            "feature_id": self.feature_id,
            "absolute_tolerance": self.absolute_tolerance,
            "solid_fraction_raw": self.solid_fraction_raw,
            "liquid_fraction_raw": self.liquid_fraction_raw,
            "balance_residual_raw": self.balance_residual_raw,
            "solid_bound_classification": self.solid_bound_classification,
            "liquid_bound_classification": self.liquid_bound_classification,
            "balance_classification": self.balance_classification,
            "bounded_roundoff_present": self.bounded_roundoff_present,
        }


def _fraction_residual_card(
    feature_id: str,
    solid_fraction_raw: float,
    liquid_fraction_raw: float,
) -> FractionResidualCard:
    _require_fixed_authority()
    tolerance = _fixed_value("fraction_roundoff_abs_tolerance")
    assert type(tolerance) is float
    solid = _f64(solid_fraction_raw, allow_nonfinite=False)
    liquid = _f64(liquid_fraction_raw, allow_nonfinite=False)
    residual = (solid + liquid) - 1.0
    solid_classification = _fraction_bound_classification(solid, tolerance)
    liquid_classification = _fraction_bound_classification(liquid, tolerance)
    if not _math.isfinite(residual) or abs(residual) > tolerance:
        _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
    balance_classification = "EXACT" if residual == 0.0 else "WITHIN_TOLERANCE"
    return FractionResidualCard(
        policy_id=_fixed_value("fraction_roundoff_policy_id"),
        solver_package="pycalphad",
        solver_version=_fixed_value("pycalphad_version"),
        upstream_package=_fixed_value("upstream_package"),
        upstream_version=_fixed_value("upstream_version"),
        feature_id=feature_id,
        absolute_tolerance=tolerance,
        solid_fraction_raw=solid,
        liquid_fraction_raw=liquid,
        balance_residual_raw=residual,
        solid_bound_classification=solid_classification,
        liquid_bound_classification=liquid_classification,
        balance_classification=balance_classification,
        bounded_roundoff_present=(
            solid_classification != "IN_RANGE"
            or liquid_classification != "IN_RANGE"
            or balance_classification != "EXACT"
        ),
    )


def _copy_fraction_residual_card(value: object) -> FractionResidualCard:
    if type(value) is not FractionResidualCard:
        _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
    try:
        return FractionResidualCard(
            policy_id=value.policy_id,
            solver_package=value.solver_package,
            solver_version=value.solver_version,
            upstream_package=value.upstream_package,
            upstream_version=value.upstream_version,
            feature_id=value.feature_id,
            absolute_tolerance=value.absolute_tolerance,
            solid_fraction_raw=value.solid_fraction_raw,
            liquid_fraction_raw=value.liquid_fraction_raw,
            balance_residual_raw=value.balance_residual_raw,
            solid_bound_classification=value.solid_bound_classification,
            liquid_bound_classification=value.liquid_bound_classification,
            balance_classification=value.balance_classification,
            bounded_roundoff_present=value.bounded_roundoff_present,
        )
    except SolidificationInstrumentationError:
        raise
    except Exception as error:
        raise SolidificationInstrumentationError(
            "W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID"
        ) from error


def _fraction_card_is_complete(card: FractionResidualCard) -> bool:
    checked = _copy_fraction_residual_card(card)
    tolerance = checked.absolute_tolerance
    return (
        abs(checked.solid_fraction_raw - 1.0) <= tolerance
        and abs(checked.liquid_fraction_raw) <= tolerance
        and abs(checked.balance_residual_raw) <= tolerance
    )


def _phase_instance_parts(value: str) -> tuple[str, int | None] | None:
    if type(value) is not str:
        return None
    matched = _PHASE_INSTANCE_RE.fullmatch(value)
    if matched is None:
        return None
    ordinal_text = matched.group("ordinal")
    return (
        matched.group("base"),
        None if ordinal_text is None else int(ordinal_text),
    )


@_dataclass(frozen=True, slots=True)
class PhaseMappingCard:
    """Exact raw-instance/domain card retained for every solver result.

    Invalid solver physics remains representable: the derived classifications
    say whether the exact raw rows may support a physical point.  No value is
    clamped, renormalized, dropped, or renamed by this card.
    """

    policy_id: str
    feature_id: str
    effective_phases: tuple[str, ...]
    independent_components: tuple[str, ...]
    liquid_phase: str
    raw_phase_fractions: tuple[tuple[str, float], ...]
    raw_instance_mapping: tuple[tuple[str, str], ...]
    ordering_model_authority: tuple[tuple[str, str], ...]
    ordering_rename_authority: tuple[tuple[str, str], ...]
    mapped_phase_fractions: tuple[tuple[str, float], ...] = _field(init=False)
    raw_total_fraction: float = _field(init=False)
    raw_liquid_fraction: float = _field(init=False)
    raw_solid_fraction: float = _field(init=False)
    raw_balance_residual: float = _field(init=False)
    derived_partition_liquid_fraction: float = _field(init=False)
    event_fraction_semantics: str = _field(init=False)
    partition_residual: float = _field(init=False)
    aggregation_residual: float = _field(init=False)
    mapping_classification: str = _field(init=False)
    raw_balance_classification: str = _field(init=False)
    observation_cap_satisfied: bool = _field(init=False)
    physical_balance_satisfied: bool = _field(init=False)
    physical_valid: bool = _field(init=False)

    def __post_init__(self) -> None:
        _require_fixed_authority()
        if (
            type(self.policy_id) is not str
            or self.policy_id != _fixed_value("phase_mapping_policy_id")
            or type(self.feature_id) is not str
            or not _fixed_feature_allowed(self.feature_id)
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        effective = _names(self.effective_phases)
        independent = _names(self.independent_components)
        liquid = _token(self.liquid_phase)
        assert liquid is not None
        raw = _numeric_pairs(self.raw_phase_fractions)
        mapping = _name_pairs(self.raw_instance_mapping)
        ordering_model_authority = _ordering_authority_pairs(
            self.ordering_model_authority
        )
        ordering_rename_authority = _ordering_instance_authority_pairs(
            self.ordering_rename_authority
        )
        if (
            not effective
            or len(effective) != len(set(effective))
            or liquid not in effective
            or len(independent) != len(set(independent))
            or "VA" in independent
            or liquid in independent
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

        raw_total = 0.0
        values_valid = True
        for _name, value in raw:
            raw_total += value
            if (
                not _math.isfinite(value)
                or value <= 0.0
                or value
                > 1.0 + _fixed_value("raw_normalization_observation_cap")
            ):
                values_valid = False

        raw_names = tuple(name for name, _value in raw)
        mapping_sources = tuple(source for source, _target in mapping)
        source_order_exact = (
            len(raw_names) == len(mapping_sources)
            and raw_names == mapping_sources
            and len(raw_names) == len(set(raw_names))
        )
        parsed_rows: list[tuple[str, int | None]] = []
        mapping_exact = source_order_exact
        for index, raw_name in enumerate(raw_names):
            parsed = _phase_instance_parts(raw_name)
            if parsed is None:
                mapping_exact = False
                parsed_rows.append((raw_name, None))
                continue
            base, instance_ordinal = parsed
            parsed_rows.append(parsed)
            if index >= len(mapping):
                mapping_exact = False
                continue
            source, target = mapping[index]
            actual_target = dict(ordering_rename_authority).get(
                raw_name,
                base,
            )
            if (
                source != raw_name
                or target != actual_target
                or target not in effective
                or base not in effective
                or (
                    target != base
                    and dict(ordering_model_authority).get(base)
                    != target
                )
                or (target == liquid and raw_name != liquid)
                or (target != liquid and base == liquid)
            ):
                mapping_exact = False

        expected_rename_sources = tuple(
            raw_name
            for raw_name, parsed in zip(raw_names, parsed_rows)
            if dict(ordering_rename_authority).get(raw_name, parsed[0])
            != parsed[0]
        )
        if (
            tuple(source for source, _target in ordering_rename_authority)
            != tuple(
                sorted(expected_rename_sources, key=_phase_instance_sort_key)
            )
            or any(source not in raw_names for source, _target in ordering_rename_authority)
        ):
            mapping_exact = False

        groups: dict[str, list[str]] = {}
        for raw_name, parsed in zip(raw_names, parsed_rows):
            groups.setdefault(parsed[0], []).append(raw_name)
        for base, names in groups.items():
            expected = (
                (base,)
                if len(names) == 1
                else tuple(f"{base}#{index}" for index in range(1, len(names) + 1))
            )
            if (
                tuple(names) != expected
                if len(names) == 1
                else set(names) != set(expected)
            ):
                mapping_exact = False

        if mapping_exact:
            phase_index = {name: index for index, name in enumerate(effective)}

            def _raw_source_key(index: int) -> tuple[int, int, int, str]:
                base, instance_ordinal = parsed_rows[index]
                return (
                    0 if base == liquid else 1,
                    phase_index[base],
                    0 if instance_ordinal is None else instance_ordinal,
                    base,
                )

            if tuple(range(len(raw))) != tuple(
                sorted(range(len(raw)), key=_raw_source_key)
            ):
                mapping_exact = False

        target_order = (liquid,) + tuple(
            phase for phase in effective if phase != liquid
        )
        mapped: list[tuple[str, float]] = []
        for target in target_order:
            found = False
            total = 0.0
            for index, (_raw_name, value) in enumerate(raw):
                if index < len(mapping) and mapping[index][1] == target:
                    found = True
                    total += value
            if found:
                mapped.append((target, total))
        for _source, target in mapping:
            if target in target_order or any(name == target for name, _value in mapped):
                continue
            total = 0.0
            found = False
            for index, (_raw_name, value) in enumerate(raw):
                if index < len(mapping) and mapping[index][1] == target:
                    found = True
                    total += value
            if found:
                mapped.append((target, total))
        mapped_tuple = tuple(mapped)

        raw_liquid = 0.0
        raw_solid = 0.0
        for name, value in mapped_tuple:
            if name == liquid:
                raw_liquid += value
            else:
                raw_solid += value
        partition_residual = (raw_liquid + raw_solid) - raw_total
        mapped_total = _sequential_sum(mapped_tuple)
        aggregation_residual = mapped_total - raw_total
        balance_residual = raw_total - 1.0
        derived_partition_liquid = 1.0 - raw_solid
        finite_residuals = all(
            _math.isfinite(value)
            for value in (
                raw_total,
                raw_liquid,
                raw_solid,
                partition_residual,
                aggregation_residual,
                balance_residual,
            )
        )
        raw_balance_within = (
            finite_residuals
            and abs(balance_residual)
            <= _fixed_value("fraction_roundoff_abs_tolerance")
        )
        observation_cap_satisfied = (
            finite_residuals
            and abs(balance_residual)
            <= _fixed_value("raw_normalization_observation_cap")
        )
        physical_balance_satisfied = (
            finite_residuals
            and abs(balance_residual)
            <= _fixed_value("physical_balance_abs_tolerance")
        )
        physical_valid = (
            bool(raw)
            and mapping_exact
            and values_valid
            and not ordering_model_authority
            and not ordering_rename_authority
            and observation_cap_satisfied
            and abs(partition_residual)
            <= _fixed_value("fraction_roundoff_abs_tolerance")
            and abs(aggregation_residual)
            <= _fixed_value("fraction_roundoff_abs_tolerance")
        )
        object.__setattr__(self, "effective_phases", effective)
        object.__setattr__(self, "independent_components", independent)
        object.__setattr__(self, "liquid_phase", liquid)
        object.__setattr__(self, "raw_phase_fractions", raw)
        object.__setattr__(self, "raw_instance_mapping", mapping)
        object.__setattr__(
            self,
            "ordering_model_authority",
            ordering_model_authority,
        )
        object.__setattr__(
            self,
            "ordering_rename_authority",
            ordering_rename_authority,
        )
        object.__setattr__(self, "mapped_phase_fractions", mapped_tuple)
        object.__setattr__(self, "raw_total_fraction", raw_total)
        object.__setattr__(self, "raw_liquid_fraction", raw_liquid)
        object.__setattr__(self, "raw_solid_fraction", raw_solid)
        object.__setattr__(self, "raw_balance_residual", balance_residual)
        object.__setattr__(
            self,
            "derived_partition_liquid_fraction",
            derived_partition_liquid,
        )
        object.__setattr__(
            self,
            "event_fraction_semantics",
            (
                "DERIVED_PARTITION_FROM_MAPPED_SOLID"
                if self.feature_id == "equilibrium_solidification"
                else "SEQUENTIAL_REMAINING_LIQUID_REPLAY"
            ),
        )
        object.__setattr__(self, "partition_residual", partition_residual)
        object.__setattr__(self, "aggregation_residual", aggregation_residual)
        object.__setattr__(
            self,
            "mapping_classification",
            (
                "UNREPRESENTABLE_ORDERING_MAPPING"
                if ordering_model_authority or ordering_rename_authority
                else "EXACT_EFFECTIVE_IDENTITY"
                if mapping_exact
                else "INVALID"
            ),
        )
        object.__setattr__(
            self,
            "raw_balance_classification",
            (
                "NONFINITE"
                if not finite_residuals
                else "EXACT"
                if balance_residual == 0.0
                else "WITHIN_TOLERANCE"
                if raw_balance_within
                else "WITHIN_PHYSICAL_BALANCE_TOLERANCE"
                if physical_balance_satisfied
                else "WITHIN_OBSERVATION_CAP_NOT_PHYSICAL_BALANCE"
                if observation_cap_satisfied
                else "OUTSIDE_TOLERANCE"
            ),
        )
        object.__setattr__(
            self,
            "observation_cap_satisfied",
            observation_cap_satisfied,
        )
        object.__setattr__(
            self,
            "physical_balance_satisfied",
            physical_balance_satisfied,
        )
        object.__setattr__(self, "physical_valid", physical_valid)

    def as_dict(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "partition_aggregation_abs_tolerance": _fixed_value(
                "fraction_roundoff_abs_tolerance"
            ),
            "physical_balance_abs_tolerance": _fixed_value(
                "physical_balance_abs_tolerance"
            ),
            "raw_normalization_observation_cap": _fixed_value(
                "raw_normalization_observation_cap"
            ),
            "feature_id": self.feature_id,
            "effective_phases": list(self.effective_phases),
            "independent_components": list(self.independent_components),
            "liquid_phase": self.liquid_phase,
            "raw_phase_fractions": [
                {"raw_instance": name, "value": value}
                for name, value in self.raw_phase_fractions
            ],
            "raw_instance_mapping": [
                {"raw_instance": source, "effective_phase": target}
                for source, target in self.raw_instance_mapping
            ],
            "ordering_rename_authority_policy_id": _fixed_value(
                "ordering_rename_authority_policy_id"
            ),
            "ordering_model_authority": [
                {"ordered_phase": source, "disordered_phase": target}
                for source, target in self.ordering_model_authority
            ],
            "ordering_rename_authority": [
                {"raw_instance": source, "effective_phase": target}
                for source, target in self.ordering_rename_authority
            ],
            "mapped_phase_fractions": [
                {"phase": name, "value": value}
                for name, value in self.mapped_phase_fractions
            ],
            "raw_total_fraction": self.raw_total_fraction,
            "raw_liquid_fraction": self.raw_liquid_fraction,
            "raw_solid_fraction": self.raw_solid_fraction,
            "raw_balance_residual": self.raw_balance_residual,
            "derived_partition_liquid_fraction": self.derived_partition_liquid_fraction,
            "event_fraction_semantics": self.event_fraction_semantics,
            "partition_residual": self.partition_residual,
            "aggregation_residual": self.aggregation_residual,
            "mapping_classification": self.mapping_classification,
            "raw_balance_classification": self.raw_balance_classification,
            "observation_cap_satisfied": self.observation_cap_satisfied,
            "physical_balance_satisfied": self.physical_balance_satisfied,
            "physical_valid": self.physical_valid,
        }


def _copy_phase_mapping_card(value: object) -> PhaseMappingCard:
    if type(value) is not PhaseMappingCard:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    try:
        rebuilt = PhaseMappingCard(
            policy_id=value.policy_id,
            feature_id=value.feature_id,
            effective_phases=value.effective_phases,
            independent_components=value.independent_components,
            liquid_phase=value.liquid_phase,
            raw_phase_fractions=value.raw_phase_fractions,
            raw_instance_mapping=value.raw_instance_mapping,
            ordering_model_authority=value.ordering_model_authority,
            ordering_rename_authority=value.ordering_rename_authority,
        )
        if _canonical_bytes(value.as_dict()) != _canonical_bytes(rebuilt.as_dict()):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        return rebuilt
    except SolidificationInstrumentationError:
        raise
    except Exception as error:
        raise SolidificationInstrumentationError(
            "W2B_INSTRUMENT_OBSERVATION_INVALID"
        ) from error


def _same_phase_mapping_card(left: object, right: object) -> bool:
    try:
        checked_left = _copy_phase_mapping_card(left)
        checked_right = _copy_phase_mapping_card(right)
        return _canonical_bytes(checked_left.as_dict()) == _canonical_bytes(
            checked_right.as_dict()
        )
    except SolidificationInstrumentationError:
        return False


def _require_exact_finite_physical_pairs(value: object) -> None:
    """Reject coercion and non-finite numerics at a physical-point boundary.

    Solver attempt/result events intentionally remain able to retain arbitrary
    binary64 evidence.  Once an event is presented as a physical point, every
    numeric that can support a convergence/stop witness must already be an
    exact built-in float and finite; it is never repaired by this layer.
    """

    if type(value) is not tuple:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    for item in value:
        if (
            type(item) is not tuple
            or len(item) != 2
            or type(item[0]) is not str
            or type(item[1]) is not float
            or not _math.isfinite(item[1])
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")


@_dataclass(frozen=True, slots=True)
class TraceProvenance:
    instrumentation_id: str
    instrumentation_version: str
    instrumentation_source_sha256: str
    instrumentation_normalized_source_sha256: str
    upstream_package: str
    upstream_version: str
    upstream_source_relative_path: str
    upstream_source_sha256: str
    upstream_ordering_relative_path: str
    upstream_ordering_sha256: str
    upstream_utils_relative_path: str
    upstream_utils_sha256: str
    upstream_license_relative_path: str
    upstream_license_sha256: str
    scheil_payload_file_count: int
    scheil_payload_total_bytes: int
    scheil_payload_manifest_sha256: str
    pycalphad_version: str
    pycalphad_payload_file_count: int
    pycalphad_payload_total_bytes: int
    pycalphad_payload_manifest_sha256: str
    numpy_version: str
    runtime_trust_boundary: str
    family: str
    profile: str
    profile_role: str
    profile_receipt_digest: str
    domain_receipt_digest: str
    execution_lease_id: str
    execution_snapshot_digest: str
    profile_receipt_card: object
    domain_receipt_card: object
    pre_snapshot_card: object
    fe_baseline_decision: str
    c15_exclusion_decision: str
    c15_retained: bool
    adaptive: bool
    pdens: int
    rng_algorithm: str
    rng_seed: int | None
    adaptive_sample_sha256: str
    binary_search_tolerance_k: float | None
    stop_liquid_fraction: float | None
    fraction_roundoff_policy_id: str
    fraction_roundoff_solver_package: str
    fraction_roundoff_solver_version: str
    fraction_roundoff_upstream_package: str
    fraction_roundoff_upstream_version: str
    fraction_roundoff_feature_id: str
    fraction_roundoff_abs_tolerance: float
    phase_mapping_policy_id: str
    phase_mapping_partition_aggregation_abs_tolerance: float
    phase_mapping_physical_balance_abs_tolerance: float
    phase_mapping_raw_normalization_observation_cap: float
    ordering_rename_authority_policy_id: str
    ordering_rename_authority: tuple[tuple[str, str], ...]
    ordering_rename_authority_sha256: str
    trace_scope: str = "INTERNAL_QUALIFICATION_DIAGNOSTIC_ONLY"
    acceptance_claim: bool = False
    counts_toward_feature_coverage: bool = False
    production_use: str = "DENIED"

    def __post_init__(self) -> None:
        _require_fixed_authority()
        try:
            profile_card = _receipts._rebuild_profile_receipt(
                self.profile_receipt_card
            )
            domain_card = _receipts._rebuild_domain_receipt(
                self.domain_receipt_card
            )
            pre_card = _receipts._rebuild_pre_snapshot(
                self.pre_snapshot_card,
                "W2B_RECEIPT_PRE_REHASH_MISMATCH",
            )
        except Exception as error:
            raise SolidificationInstrumentationError(
                "W2B_INSTRUMENT_CONTEXT_INVALID"
            ) from error
        string_fields = (
            self.instrumentation_id,
            self.instrumentation_version,
            self.instrumentation_source_sha256,
            self.instrumentation_normalized_source_sha256,
            self.upstream_package,
            self.upstream_version,
            self.upstream_source_relative_path,
            self.upstream_source_sha256,
            self.upstream_ordering_relative_path,
            self.upstream_ordering_sha256,
            self.upstream_utils_relative_path,
            self.upstream_utils_sha256,
            self.upstream_license_relative_path,
            self.upstream_license_sha256,
            self.scheil_payload_manifest_sha256,
            self.pycalphad_version,
            self.pycalphad_payload_manifest_sha256,
            self.numpy_version,
            self.runtime_trust_boundary,
            self.family,
            self.profile,
            self.profile_role,
            self.profile_receipt_digest,
            self.domain_receipt_digest,
            self.execution_lease_id,
            self.execution_snapshot_digest,
            self.fe_baseline_decision,
            self.c15_exclusion_decision,
            self.rng_algorithm,
            self.adaptive_sample_sha256,
            self.fraction_roundoff_policy_id,
            self.fraction_roundoff_solver_package,
            self.fraction_roundoff_solver_version,
            self.fraction_roundoff_upstream_package,
            self.fraction_roundoff_upstream_version,
            self.fraction_roundoff_feature_id,
            self.phase_mapping_policy_id,
            self.ordering_rename_authority_policy_id,
            self.ordering_rename_authority_sha256,
            self.trace_scope,
            self.production_use,
        )
        if (
            any(type(value) is not str for value in string_fields)
            or self.instrumentation_id != _fixed_value("instrumentation_id")
            or self.instrumentation_version
            != _fixed_value("instrumentation_version")
            or self.instrumentation_normalized_source_sha256
            != _fixed_value("instrumentation_normalized_source_sha256")
            or self.upstream_package != _fixed_value("upstream_package")
            or self.upstream_version != _fixed_value("upstream_version")
            or self.upstream_source_relative_path
            != _fixed_value("upstream_source_relative_path")
            or self.upstream_source_sha256
            != _fixed_value("upstream_source_sha256")
            or self.upstream_ordering_relative_path
            != _fixed_value("upstream_ordering_relative_path")
            or self.upstream_ordering_sha256
            != _fixed_value("upstream_ordering_sha256")
            or self.upstream_utils_relative_path
            != _fixed_value("upstream_utils_relative_path")
            or self.upstream_utils_sha256
            != _fixed_value("upstream_utils_sha256")
            or self.upstream_license_relative_path
            != _fixed_value("upstream_license_relative_path")
            or self.upstream_license_sha256
            != _fixed_value("upstream_license_sha256")
            or self.scheil_payload_file_count
            != _fixed_value("scheil_payload_file_count")
            or self.scheil_payload_total_bytes
            != _fixed_value("scheil_payload_total_bytes")
            or self.scheil_payload_manifest_sha256
            != _fixed_value("scheil_payload_manifest_sha256")
            or self.pycalphad_version != _fixed_value("pycalphad_version")
            or self.pycalphad_payload_file_count
            != _fixed_value("pycalphad_payload_file_count")
            or self.pycalphad_payload_total_bytes
            != _fixed_value("pycalphad_payload_total_bytes")
            or self.pycalphad_payload_manifest_sha256
            != _fixed_value("pycalphad_payload_manifest_sha256")
            or self.numpy_version != _fixed_value("numpy_version")
            or self.runtime_trust_boundary
            != _fixed_value("runtime_trust_boundary")
            or self.family not in ("ni", "al", "fe")
            or type(self.profile) is not str
            or not self.profile
            or self.profile_role != _fixed_profile_role(self.family, self.profile)
            or self.trace_scope != _fixed_value("trace_scope")
            or self.acceptance_claim is not False
            or self.counts_toward_feature_coverage is not False
            or self.production_use != _fixed_value("production_use")
            or type(self.c15_retained) is not bool
            or self.adaptive is not False
            or type(self.pdens) is not int
            or isinstance(self.pdens, bool)
            or not 1 <= self.pdens <= 100_000
            or self.rng_algorithm != _fixed_value("rng_algorithm")
            or self.rng_seed is not _fixed_value("rng_seed")
            or self.adaptive_sample_sha256
            != _fixed_value("adaptive_sample_sha256")
            or self.fraction_roundoff_policy_id
            != _fixed_value("fraction_roundoff_policy_id")
            or self.fraction_roundoff_solver_package != "pycalphad"
            or self.fraction_roundoff_solver_version
            != _fixed_value("pycalphad_version")
            or self.fraction_roundoff_upstream_package
            != _fixed_value("upstream_package")
            or self.fraction_roundoff_upstream_version
            != _fixed_value("upstream_version")
            or self.phase_mapping_policy_id
            != _fixed_value("phase_mapping_policy_id")
            or self.ordering_rename_authority_policy_id
            != _fixed_value("ordering_rename_authority_policy_id")
        ):
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        if (
            profile_card.canonical_digest != self.profile_receipt_digest
            or domain_card.canonical_digest != self.domain_receipt_digest
            or domain_card.profile_receipt.canonical_digest
            != profile_card.canonical_digest
            or pre_card.lease_id != self.execution_lease_id
            or pre_card.execution_snapshot_digest
            != self.execution_snapshot_digest
            or pre_card.domain_receipt_digest != domain_card.canonical_digest
            or pre_card.profile_receipt_digest != profile_card.canonical_digest
            or profile_card.family != self.family
            or profile_card.profile != self.profile
            or profile_card.profile_role != self.profile_role
            or profile_card.baseline_decision != self.fe_baseline_decision
            or profile_card.c15_exclusion_decision
            != self.c15_exclusion_decision
        ):
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        try:
            ordering_authority = _ordering_authority_pairs(
                self.ordering_rename_authority
            )
        except SolidificationInstrumentationError as error:
            raise SolidificationInstrumentationError(
                "W2B_INSTRUMENT_CONTEXT_INVALID"
            ) from error
        effective_phase_set = set(domain_card.effective_phases)
        pinned_ordering_authority = _fixed_ordering_model(
            profile_card.runtime.sha256
        )
        if (
            pinned_ordering_authority is None
            or ordering_authority != pinned_ordering_authority
            or any(
                source not in effective_phase_set
                or target not in effective_phase_set
                for source, target in ordering_authority
            )
            or self.ordering_rename_authority_sha256
            != _ordering_authority_digest(
                profile_receipt_digest=profile_card.canonical_digest,
                domain_receipt_digest=domain_card.canonical_digest,
                pairs=ordering_authority,
            )
        ):
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        object.__setattr__(
            self,
            "ordering_rename_authority",
            ordering_authority,
        )
        try:
            solver_card = domain_card.solver_options.value()
            full_request_card = domain_card.full_request.value()
            request_card = full_request_card["request"]
            request_database = request_card["database_identity"]
            request_phases = request_card["phases"]
            expected_outer_database = _receipts.request_database_binding(
                profile_card
            )
        except Exception as error:
            raise SolidificationInstrumentationError(
                "W2B_INSTRUMENT_CONTEXT_INVALID"
            ) from error
        expected_solver_card = {
            "adaptive": False,
            "pdens": self.pdens,
        }
        if self.binary_search_tolerance_k is not None:
            expected_solver_card["binary_search_tolerance_k"] = (
                self.binary_search_tolerance_k
            )
            expected_feature = "equilibrium_solidification"
        else:
            expected_solver_card["stop_liquid_fraction"] = (
                self.stop_liquid_fraction
            )
            expected_feature = "scheil_solidification"
        expected_request_database = {
            "family": profile_card.family,
            "database_id": profile_card.profile,
            "database_sha256": profile_card.runtime.sha256,
            "profile_id": profile_card.profile,
            "profile_role": profile_card.profile_role,
            "fe_baseline_decision": profile_card.baseline_decision,
            "c15_exclusion_decision": (
                profile_card.c15_exclusion_decision
            ),
        }
        expected_request_phases = {
            "candidate": list(domain_card.candidate_phases),
            "requested": list(domain_card.requested_phases),
            "excluded": list(domain_card.excluded_phases),
            "effective": list(domain_card.effective_phases),
        }
        if (
            type(solver_card) is not dict
            or solver_card != _receipts._canonicalize(expected_solver_card)
            or type(full_request_card) is not dict
            or full_request_card.get("feature_id") != expected_feature
            or full_request_card.get("database")
            != expected_outer_database
            or type(request_card) is not dict
            or type(request_database) is not dict
            or request_database != expected_request_database
            or type(request_phases) is not dict
            or request_phases != expected_request_phases
            or request_card.get("method")
            != (
                "EQUILIBRIUM"
                if expected_feature == "equilibrium_solidification"
                else "SCHEIL_GULLIVER"
            )
            or request_card.get("adaptive") is not False
            or request_card.get("pdens") != self.pdens
            or domain_card.feature_id != expected_feature
            or self.fraction_roundoff_feature_id != expected_feature
        ):
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        tolerance = (
            None
            if self.binary_search_tolerance_k is None
            else _f64(self.binary_search_tolerance_k, allow_nonfinite=False)
        )
        stop = (
            None
            if self.stop_liquid_fraction is None
            else _f64(self.stop_liquid_fraction, allow_nonfinite=False)
        )
        if (tolerance is None) == (stop is None):
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        if tolerance is not None and tolerance <= 0.0:
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        if stop is not None and not 0.0 < stop < 1.0:
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        object.__setattr__(self, "binary_search_tolerance_k", tolerance)
        object.__setattr__(self, "stop_liquid_fraction", stop)
        roundoff_tolerance = _f64(
            self.fraction_roundoff_abs_tolerance,
            allow_nonfinite=False,
        )
        if not _same_f64(
            roundoff_tolerance,
            _fixed_value("fraction_roundoff_abs_tolerance"),
        ):
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        object.__setattr__(
            self,
            "fraction_roundoff_abs_tolerance",
            roundoff_tolerance,
        )
        mapping_tolerance = _f64(
            self.phase_mapping_partition_aggregation_abs_tolerance,
            allow_nonfinite=False,
        )
        physical_tolerance = _f64(
            self.phase_mapping_physical_balance_abs_tolerance,
            allow_nonfinite=False,
        )
        observation_cap = _f64(
            self.phase_mapping_raw_normalization_observation_cap,
            allow_nonfinite=False,
        )
        if (
            not _same_f64(
                mapping_tolerance,
                _fixed_value("fraction_roundoff_abs_tolerance"),
            )
            or not _same_f64(
                physical_tolerance,
                _fixed_value("physical_balance_abs_tolerance"),
            )
            or not _same_f64(
                observation_cap,
                _fixed_value("raw_normalization_observation_cap"),
            )
            or mapping_tolerance <= 0.0
            or physical_tolerance < mapping_tolerance
            or observation_cap < physical_tolerance
        ):
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        object.__setattr__(
            self,
            "phase_mapping_partition_aggregation_abs_tolerance",
            mapping_tolerance,
        )
        object.__setattr__(
            self,
            "phase_mapping_physical_balance_abs_tolerance",
            physical_tolerance,
        )
        object.__setattr__(
            self,
            "phase_mapping_raw_normalization_observation_cap",
            observation_cap,
        )
        for digest in (
            self.instrumentation_source_sha256,
            self.instrumentation_normalized_source_sha256,
            self.upstream_source_sha256,
            self.upstream_ordering_sha256,
            self.upstream_utils_sha256,
            self.upstream_license_sha256,
            self.scheil_payload_manifest_sha256,
            self.pycalphad_payload_manifest_sha256,
            self.adaptive_sample_sha256,
            self.profile_receipt_digest,
            self.domain_receipt_digest,
            self.execution_lease_id,
            self.execution_snapshot_digest,
            self.ordering_rename_authority_sha256,
        ):
            _sha256(digest)
        if self.family == "fe":
            if (
                self.profile not in _fixed_value("supported_fe_profile_ids")
                or self.fe_baseline_decision != _receipts.FE_POLICY_UNDECIDED
                or self.c15_exclusion_decision != _receipts.FE_POLICY_UNDECIDED
                or not self.c15_retained
            ):
                _fail("W2B_INSTRUMENT_FE_POLICY")
        elif (
            self.fe_baseline_decision != _receipts.POLICY_NOT_APPLICABLE
            or self.c15_exclusion_decision != _receipts.POLICY_NOT_APPLICABLE
            or self.c15_retained
        ):
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        object.__setattr__(self, "profile_receipt_card", profile_card)
        object.__setattr__(self, "domain_receipt_card", domain_card)
        object.__setattr__(self, "pre_snapshot_card", pre_card)

    def as_dict(self) -> dict[str, object]:
        return {
            "instrumentation_id": self.instrumentation_id,
            "instrumentation_version": self.instrumentation_version,
            "instrumentation_source_sha256": self.instrumentation_source_sha256,
            "instrumentation_normalized_source_sha256": self.instrumentation_normalized_source_sha256,
            "upstream_package": self.upstream_package,
            "upstream_version": self.upstream_version,
            "upstream_source_relative_path": self.upstream_source_relative_path,
            "upstream_source_sha256": self.upstream_source_sha256,
            "upstream_ordering_relative_path": self.upstream_ordering_relative_path,
            "upstream_ordering_sha256": self.upstream_ordering_sha256,
            "upstream_utils_relative_path": self.upstream_utils_relative_path,
            "upstream_utils_sha256": self.upstream_utils_sha256,
            "upstream_license_relative_path": self.upstream_license_relative_path,
            "upstream_license_sha256": self.upstream_license_sha256,
            "scheil_payload_file_count": self.scheil_payload_file_count,
            "scheil_payload_total_bytes": self.scheil_payload_total_bytes,
            "scheil_payload_manifest_sha256": self.scheil_payload_manifest_sha256,
            "pycalphad_version": self.pycalphad_version,
            "pycalphad_payload_file_count": self.pycalphad_payload_file_count,
            "pycalphad_payload_total_bytes": self.pycalphad_payload_total_bytes,
            "pycalphad_payload_manifest_sha256": self.pycalphad_payload_manifest_sha256,
            "numpy_version": self.numpy_version,
            "runtime_trust_boundary": self.runtime_trust_boundary,
            "family": self.family,
            "profile": self.profile,
            "profile_role": self.profile_role,
            "profile_receipt_digest": self.profile_receipt_digest,
            "domain_receipt_digest": self.domain_receipt_digest,
            "execution_lease_id": self.execution_lease_id,
            "execution_snapshot_digest": self.execution_snapshot_digest,
            "profile_receipt_card_canonical_json": (
                _receipts.canonical_json_bytes(
                    self.profile_receipt_card.as_dict()
                ).decode("utf-8")
            ),
            "domain_receipt_card_canonical_json": (
                _receipts.canonical_json_bytes(
                    self.domain_receipt_card.as_dict()
                ).decode("utf-8")
            ),
            "pre_snapshot_card_canonical_json": (
                _receipts.canonical_json_bytes(
                    self.pre_snapshot_card.as_dict()
                ).decode("utf-8")
            ),
            "fe_baseline_decision": self.fe_baseline_decision,
            "c15_exclusion_decision": self.c15_exclusion_decision,
            "c15_retained": self.c15_retained,
            "adaptive": self.adaptive,
            "pdens": self.pdens,
            "rng_algorithm": self.rng_algorithm,
            "rng_seed": self.rng_seed,
            "adaptive_sample_sha256": self.adaptive_sample_sha256,
            "binary_search_tolerance_k": self.binary_search_tolerance_k,
            "stop_liquid_fraction": self.stop_liquid_fraction,
            "fraction_roundoff_policy_id": self.fraction_roundoff_policy_id,
            "fraction_roundoff_solver_package": self.fraction_roundoff_solver_package,
            "fraction_roundoff_solver_version": self.fraction_roundoff_solver_version,
            "fraction_roundoff_upstream_package": self.fraction_roundoff_upstream_package,
            "fraction_roundoff_upstream_version": self.fraction_roundoff_upstream_version,
            "fraction_roundoff_feature_id": self.fraction_roundoff_feature_id,
            "fraction_roundoff_abs_tolerance": self.fraction_roundoff_abs_tolerance,
            "phase_mapping_policy_id": self.phase_mapping_policy_id,
            "phase_mapping_partition_aggregation_abs_tolerance": self.phase_mapping_partition_aggregation_abs_tolerance,
            "phase_mapping_physical_balance_abs_tolerance": self.phase_mapping_physical_balance_abs_tolerance,
            "phase_mapping_raw_normalization_observation_cap": self.phase_mapping_raw_normalization_observation_cap,
            "ordering_rename_authority_policy_id": self.ordering_rename_authority_policy_id,
            "ordering_rename_authority": [
                {"ordered_phase": source, "disordered_phase": target}
                for source, target in self.ordering_rename_authority
            ],
            "ordering_rename_authority_sha256": self.ordering_rename_authority_sha256,
            "trace_scope": _fixed_value("trace_scope"),
            "acceptance_claim": False,
            "counts_toward_feature_coverage": False,
            "production_use": "DENIED",
        }


def _bound_phase_contract(
    provenance: TraceProvenance,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    str,
    tuple[tuple[str, float], ...],
]:
    """Rebuild phase/component facts only from the immutable receipt card."""

    if type(provenance) is not TraceProvenance:
        _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
    try:
        full_request = provenance.domain_receipt_card.full_request.value()
        request_card = full_request["request"]
        components_raw = request_card["components"]
        composition_raw = request_card["composition"]
        phases_raw = request_card["phases"]
        liquid_phase = request_card["liquid_phase"]
        effective = tuple(provenance.domain_receipt_card.effective_phases)
        request_effective = tuple(phases_raw["effective"])
        components = tuple(components_raw)
        pure_components = tuple(name for name in components if name != "VA")
        dependent = pure_components[-1]
        bulk = tuple(
            (
                row["component"],
                _receipts._decode_f64(row["mole_fraction"]),
            )
            for row in composition_raw
        )
        independent = tuple(
            sorted(name for name, _value in bulk if name != dependent)
        )
    except Exception as error:
        raise SolidificationInstrumentationError(
            "W2B_INSTRUMENT_CONTEXT_INVALID"
        ) from error
    if (
        type(full_request) is not dict
        or type(request_card) is not dict
        or type(components_raw) is not list
        or type(composition_raw) is not list
        or type(phases_raw) is not dict
        or type(liquid_phase) is not str
        or not pure_components
        or request_effective != effective
        or len(effective) != len(set(effective))
        or liquid_phase not in effective
        or tuple(name for name, _value in bulk) != pure_components
        or len(independent) != len(set(independent))
        or "VA" in independent
    ):
        _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
    return effective, independent, liquid_phase, bulk


def _phase_mapping_card_from_bound(
    provenance: TraceProvenance,
    raw_phase_fractions: tuple[tuple[str, float], ...],
    raw_instance_mapping: tuple[tuple[str, str], ...],
    ordering_rename_authority: tuple[tuple[str, str], ...] = (),
) -> PhaseMappingCard:
    _require_fixed_authority()
    effective, independent, liquid, _bulk = _bound_phase_contract(provenance)
    return PhaseMappingCard(
        policy_id=_fixed_value("phase_mapping_policy_id"),
        feature_id=provenance.fraction_roundoff_feature_id,
        effective_phases=effective,
        independent_components=independent,
        liquid_phase=liquid,
        raw_phase_fractions=raw_phase_fractions,
        raw_instance_mapping=raw_instance_mapping,
        ordering_model_authority=provenance.ordering_rename_authority,
        ordering_rename_authority=ordering_rename_authority,
    )


def _mapped_present_phases(card: PhaseMappingCard) -> tuple[str, ...]:
    return tuple(name for name, _value in card.mapped_phase_fractions)


def _mapped_solid_amounts(card: PhaseMappingCard) -> tuple[tuple[str, float], ...]:
    return tuple(
        (name, value)
        for name, value in card.mapped_phase_fractions
        if name != card.liquid_phase
    )


def _liquid_composition_matches_card(
    values: tuple[tuple[str, float], ...],
    card: PhaseMappingCard,
) -> bool:
    names = tuple(name for name, _value in values)
    expected = (
        card.independent_components
        if card.raw_liquid_fraction > 0.0
        else ()
    )
    return names == expected


@_dataclass(frozen=True, slots=True)
class SolidificationTraceEvent:
    ordinal: int
    event_kind: str
    stage: str
    outcome: str
    temperature_k: float | None = None
    pressure_pa: float | None = None
    step_temperature_k: float | None = None
    bracket_low_k: float | None = None
    bracket_high_k: float | None = None
    composition: tuple[tuple[str, float], ...] = ()
    phases: tuple[str, ...] = ()
    raw_phase_fractions: tuple[tuple[str, float], ...] = ()
    raw_instance_mapping: tuple[tuple[str, str], ...] = ()
    phase_amounts: tuple[tuple[str, float], ...] = ()
    liquid_composition: tuple[tuple[str, float], ...] = ()
    solid_fraction: float | None = None
    liquid_fraction: float | None = None
    solver_converged: bool | None = None
    gm_converged: bool | None = None
    point_id: str | None = None
    parent_point_id: str | None = None
    step_id: str | None = None
    solver_call_id: str | None = None
    synthetic: bool = False
    service: bool = False
    reason_code: str | None = None
    exception_type: str | None = None
    exception_type_sha256: str | None = None
    exception_message_sha256: str | None = None
    budget_limit: int | None = None
    budget_used: int | None = None
    budget_required: int | None = None
    closure_residual_fraction: float | None = None
    closure_unfilled_gap: float | None = None
    closure_evidence_policy_id: str | None = None
    closure_accepted_point_count: int | None = None
    closure_excursion_abs_cap: float | None = None
    closure_residual_classification: str | None = None
    closure_gap_classification: str | None = None
    fraction_residual_card: FractionResidualCard | None = None
    phase_mapping_card: PhaseMappingCard | None = None

    def __post_init__(self) -> None:
        _require_fixed_authority()
        if type(self.ordinal) is not int or isinstance(self.ordinal, bool) or self.ordinal < 0:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if (
            not _fixed_event_allowed(
                self.event_kind,
                self.stage,
                self.outcome,
            )
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        point_kinds = (
            "SYNTHETIC_INITIAL_INSERTION",
            "ACCEPTED_PHYSICAL_POINT",
            "SERVICE_CLOSURE",
        )
        if self.event_kind in point_kinds:
            for name in (
                "temperature_k",
                "pressure_pa",
                "step_temperature_k",
                "solid_fraction",
                "liquid_fraction",
                "closure_residual_fraction",
                "closure_unfilled_gap",
                "closure_excursion_abs_cap",
            ):
                value = getattr(self, name)
                if value is not None and (
                    type(value) is not float or not _math.isfinite(value)
                ):
                    _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            for name in (
                "composition",
                "raw_phase_fractions",
                "phase_amounts",
                "liquid_composition",
            ):
                _require_exact_finite_physical_pairs(getattr(self, name))
        for name in (
            "temperature_k",
            "pressure_pa",
            "step_temperature_k",
            "bracket_low_k",
            "bracket_high_k",
            "solid_fraction",
            "liquid_fraction",
            "closure_residual_fraction",
            "closure_unfilled_gap",
            "closure_excursion_abs_cap",
        ):
            object.__setattr__(self, name, _optional_f64(getattr(self, name)))
        object.__setattr__(self, "composition", _numeric_pairs(self.composition))
        object.__setattr__(self, "phases", _names(self.phases))
        object.__setattr__(self, "raw_phase_fractions", _numeric_pairs(self.raw_phase_fractions))
        object.__setattr__(self, "raw_instance_mapping", _name_pairs(self.raw_instance_mapping))
        object.__setattr__(self, "phase_amounts", _numeric_pairs(self.phase_amounts))
        object.__setattr__(self, "liquid_composition", _numeric_pairs(self.liquid_composition))
        object.__setattr__(self, "point_id", _optional_id(self.point_id))
        object.__setattr__(self, "parent_point_id", _optional_id(self.parent_point_id))
        object.__setattr__(self, "step_id", _optional_id(self.step_id))
        object.__setattr__(self, "solver_call_id", _optional_id(self.solver_call_id))
        if type(self.synthetic) is not bool or type(self.service) is not bool:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.solver_converged is not None and type(self.solver_converged) is not bool:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.gm_converged is not None and type(self.gm_converged) is not bool:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.reason_code is not None and (
            type(self.reason_code) is not str
            or self.reason_code not in INSTRUMENTATION_REASON_CODES
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        budget_values = (self.budget_limit, self.budget_used, self.budget_required)
        if self.event_kind == "BUDGET_EXHAUSTED":
            if any(
                type(value) is not int
                or isinstance(value, bool)
                or value < 0
                for value in budget_values
            ) or self.budget_required < 1:
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        elif any(value is not None for value in budget_values):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.event_kind == "SERVICE_CLOSURE":
            expected_cap = _closure_evidence_excursion_cap(
                self.closure_accepted_point_count
            )
            if (
                self.closure_residual_fraction is None
                or self.closure_unfilled_gap is None
                or self.closure_evidence_policy_id
                != _fixed_value("scheil_closure_evidence_policy_id")
                or self.closure_excursion_abs_cap is None
                or not _same_f64(
                    self.closure_excursion_abs_cap,
                    expected_cap,
                )
                or self.closure_residual_classification
                != _closure_evidence_classification(
                    self.closure_residual_fraction,
                    expected_cap,
                )
                or self.closure_gap_classification
                != _closure_evidence_classification(
                    self.closure_unfilled_gap,
                    expected_cap,
                )
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        elif (
            self.closure_residual_fraction is not None
            or self.closure_unfilled_gap is not None
            or self.closure_evidence_policy_id is not None
            or self.closure_accepted_point_count is not None
            or self.closure_excursion_abs_cap is not None
            or self.closure_residual_classification is not None
            or self.closure_gap_classification is not None
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.event_kind in point_kinds:
            if (
                self.solid_fraction is None
                or self.liquid_fraction is None
                or self.fraction_residual_card is None
            ):
                _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
            fraction_card = _copy_fraction_residual_card(
                self.fraction_residual_card
            )
            if (
                not _same_f64(
                    fraction_card.solid_fraction_raw,
                    self.solid_fraction,
                )
                or not _same_f64(
                    fraction_card.liquid_fraction_raw,
                    self.liquid_fraction,
                )
            ):
                _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
            object.__setattr__(self, "fraction_residual_card", fraction_card)
        elif self.fraction_residual_card is not None:
            _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
        if self.event_kind in point_kinds or self.event_kind == "SOLVER_CALL_RESULT":
            if self.phase_mapping_card is None:
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            mapping_card = _copy_phase_mapping_card(self.phase_mapping_card)
            if (
                not _same_numeric_pairs(
                    mapping_card.raw_phase_fractions,
                    self.raw_phase_fractions,
                )
                or mapping_card.raw_instance_mapping
                != self.raw_instance_mapping
                or (
                    self.event_kind in point_kinds
                    and not mapping_card.physical_valid
                )
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            object.__setattr__(self, "phase_mapping_card", mapping_card)
        elif self.phase_mapping_card is not None:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.event_kind == "ACCEPTED_PHYSICAL_POINT":
            assert self.phase_mapping_card is not None
            expected_outcome = (
                "ACCEPTED"
                if self.phase_mapping_card.physical_balance_satisfied
                else "ALGORITHM_ACCEPTED_WITH_RAW_NORMALIZATION_RESIDUAL"
            )
            if self.outcome != expected_outcome:
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if len(
            {
                self.exception_type is None,
                self.exception_type_sha256 is None,
                self.exception_message_sha256 is None,
            }
        ) != 1:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.exception_type is not None:
            if (
                type(self.exception_type) is not str
                or not self.exception_type
                or len(self.exception_type) > 160
                or _re.fullmatch(r"[A-Za-z0-9_.:#-]+", self.exception_type) is None
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            _sha256(self.exception_type_sha256)
            _sha256(self.exception_message_sha256)
        if self.event_kind == "SOLVER_CALL_BEGIN":
            if (
                self.solver_call_id is None
                or self.solver_converged is not None
                or self.gm_converged is not None
                or self.exception_type is not None
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        elif self.event_kind == "SOLVER_CALL_RESULT":
            if (
                self.solver_call_id is None
                or self.solver_converged is None
                or self.gm_converged is None
                or self.exception_type is not None
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        elif self.event_kind == "SOLVER_CALL_ERROR":
            if (
                self.solver_call_id is None
                or self.exception_type is None
                or self.reason_code != "W2B_INSTRUMENT_SOLVER_ERROR"
                or self.solver_converged is not None
                or self.gm_converged is not None
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        elif self.event_kind == "RUN_ERROR":
            if (
                self.stage not in (
                    "DATABASE_LOAD",
                    "SOLVER_PREPARE",
                    "DISPATCH",
                    "FINALIZE",
                )
                or self.outcome != "ERROR"
                or self.exception_type is None
                or self.reason_code != "W2B_INSTRUMENT_RUN_ERROR"
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        elif self.solver_converged is not None or self.gm_converged is not None:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.solver_call_id is not None and self.event_kind not in (
            "SOLVER_CALL_BEGIN",
            "SOLVER_CALL_RESULT",
            "SOLVER_CALL_ERROR",
            "NO_LIQUID_FAILURE",
            "PHYSICAL_VALIDATION_FAILURE",
            "ACCEPTED_PHYSICAL_POINT",
            "BINARY_SEARCH_DIRECTION",
            "SERVICE_CLOSURE",
            "TERMINATION",
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.event_kind == "ACCEPTED_PHYSICAL_POINT" and self.solver_call_id is None:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.event_kind == "RUN_ERROR" and self.solver_call_id is not None:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.exception_type is not None and self.event_kind not in (
            "SOLVER_CALL_ERROR",
            "RUN_ERROR",
            "TERMINATION",
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": _fixed_value("event_schema"),
            "ordinal": self.ordinal,
            "event_kind": self.event_kind,
            "stage": self.stage,
            "outcome": self.outcome,
            "temperature_k": self.temperature_k,
            "pressure_pa": self.pressure_pa,
            "step_temperature_k": self.step_temperature_k,
            "bracket_low_k": self.bracket_low_k,
            "bracket_high_k": self.bracket_high_k,
            "composition": [{"component": k, "value": v} for k, v in self.composition],
            "phases": list(self.phases),
            "raw_phase_fractions": [{"phase": k, "value": v} for k, v in self.raw_phase_fractions],
            "raw_instance_mapping": [
                {"raw_instance": source, "effective_phase": target}
                for source, target in self.raw_instance_mapping
            ],
            "phase_amounts": [{"phase": k, "value": v} for k, v in self.phase_amounts],
            "liquid_composition": [{"component": k, "value": v} for k, v in self.liquid_composition],
            "solid_fraction": self.solid_fraction,
            "liquid_fraction": self.liquid_fraction,
            "solver_converged": self.solver_converged,
            "gm_converged": self.gm_converged,
            "point_id": self.point_id,
            "parent_point_id": self.parent_point_id,
            "step_id": self.step_id,
            "solver_call_id": self.solver_call_id,
            "synthetic": self.synthetic,
            "service": self.service,
            "reason_code": self.reason_code,
            "exception_type": self.exception_type,
            "exception_type_sha256": self.exception_type_sha256,
            "exception_message_sha256": self.exception_message_sha256,
            "budget_limit": self.budget_limit,
            "budget_used": self.budget_used,
            "budget_required": self.budget_required,
            "closure_residual_fraction": self.closure_residual_fraction,
            "closure_unfilled_gap": self.closure_unfilled_gap,
            "closure_evidence_policy_id": self.closure_evidence_policy_id,
            "closure_accepted_point_count": self.closure_accepted_point_count,
            "closure_excursion_abs_cap": self.closure_excursion_abs_cap,
            "closure_residual_classification": self.closure_residual_classification,
            "closure_gap_classification": self.closure_gap_classification,
            "fraction_residual_card": (
                None
                if self.fraction_residual_card is None
                else self.fraction_residual_card.as_dict()
            ),
            "phase_mapping_card": (
                None
                if self.phase_mapping_card is None
                else self.phase_mapping_card.as_dict()
            ),
        }


def _copy_event(value: object, ordinal: int) -> SolidificationTraceEvent:
    if type(value) is not SolidificationTraceEvent:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    try:
        rebuilt = SolidificationTraceEvent(
            ordinal=value.ordinal,
            event_kind=value.event_kind,
            stage=value.stage,
            outcome=value.outcome,
            temperature_k=value.temperature_k,
            pressure_pa=value.pressure_pa,
            step_temperature_k=value.step_temperature_k,
            bracket_low_k=value.bracket_low_k,
            bracket_high_k=value.bracket_high_k,
            composition=value.composition,
            phases=value.phases,
            raw_phase_fractions=value.raw_phase_fractions,
            raw_instance_mapping=value.raw_instance_mapping,
            phase_amounts=value.phase_amounts,
            liquid_composition=value.liquid_composition,
            solid_fraction=value.solid_fraction,
            liquid_fraction=value.liquid_fraction,
            solver_converged=value.solver_converged,
            gm_converged=value.gm_converged,
            point_id=value.point_id,
            parent_point_id=value.parent_point_id,
            step_id=value.step_id,
            solver_call_id=value.solver_call_id,
            synthetic=value.synthetic,
            service=value.service,
            reason_code=value.reason_code,
            exception_type=value.exception_type,
            exception_type_sha256=value.exception_type_sha256,
            exception_message_sha256=value.exception_message_sha256,
            budget_limit=value.budget_limit,
            budget_used=value.budget_used,
            budget_required=value.budget_required,
            closure_residual_fraction=value.closure_residual_fraction,
            closure_unfilled_gap=value.closure_unfilled_gap,
            closure_evidence_policy_id=value.closure_evidence_policy_id,
            closure_accepted_point_count=value.closure_accepted_point_count,
            closure_excursion_abs_cap=value.closure_excursion_abs_cap,
            closure_residual_classification=value.closure_residual_classification,
            closure_gap_classification=value.closure_gap_classification,
            fraction_residual_card=value.fraction_residual_card,
            phase_mapping_card=value.phase_mapping_card,
        )
    except Exception as error:
        raise SolidificationInstrumentationError("W2B_INSTRUMENT_OBSERVATION_INVALID") from error
    if rebuilt.ordinal != ordinal:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    return rebuilt


def _event_exception_card(
    event: SolidificationTraceEvent,
) -> tuple[str | None, str | None, str | None]:
    return (
        event.exception_type,
        event.exception_type_sha256,
        event.exception_message_sha256,
    )


def _validate_event_state_machine(
    *,
    events: tuple[SolidificationTraceEvent, ...],
    feature_id: str,
    provenance: TraceProvenance,
    budget: InstrumentationBudget,
    termination_outcome: str,
    termination_reason_code: str | None,
    solver_call_count: int,
    cooling_step_count: int,
    binary_probe_count: int,
) -> None:
    """Replay the append-only trace as a strict deterministic state machine."""

    if (
        sum(event.event_kind == "RUN_START" for event in events) != 1
        or sum(event.event_kind == "TERMINATION" for event in events) != 1
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    try:
        (
            effective_phases,
            independent_components,
            liquid_phase,
            bound_bulk_composition,
        ) = _bound_phase_contract(provenance)
    except Exception as error:
        raise SolidificationInstrumentationError(
            "W2B_INSTRUMENT_OBSERVATION_INVALID"
        ) from error
    run_start = events[0]
    if (
        run_start.phases != effective_phases
        or not _same_numeric_pairs(
            run_start.composition,
            bound_bulk_composition,
        )
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    result_by_call: dict[str, SolidificationTraceEvent] = {}
    expected_solver = 1
    for index, event in enumerate(events):
        if event.event_kind != "SOLVER_CALL_BEGIN":
            continue
        expected_id = f"solver-{expected_solver:06d}"
        if (
            event.solver_call_id != expected_id
            or index + 1 >= len(events)
            or tuple(name for name, _value in event.composition)
            != independent_components
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        terminal = events[index + 1]
        if (
            terminal.event_kind not in ("SOLVER_CALL_RESULT", "SOLVER_CALL_ERROR")
            or terminal.solver_call_id != expected_id
            or terminal.stage != event.stage
            or terminal.parent_point_id != event.parent_point_id
            or terminal.step_id != event.step_id
            or not _same_optional_f64(terminal.temperature_k, event.temperature_k)
            or not _same_optional_f64(terminal.pressure_pa, event.pressure_pa)
            or not _same_numeric_pairs(terminal.composition, event.composition)
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if terminal.event_kind == "SOLVER_CALL_RESULT":
            if terminal.phase_mapping_card is None:
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            expected_mapping_card = _phase_mapping_card_from_bound(
                provenance,
                terminal.raw_phase_fractions,
                terminal.raw_instance_mapping,
                terminal.phase_mapping_card.ordering_rename_authority,
            )
            if not _same_phase_mapping_card(
                terminal.phase_mapping_card,
                expected_mapping_card,
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        result_by_call[expected_id] = terminal
        expected_solver += 1
    if expected_solver - 1 != solver_call_count:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

    cooling_events = [event for event in events if event.event_kind == "COOLING_STEP"]
    if [event.step_id for event in cooling_events] != [
        f"step-{index:06d}" for index in range(1, cooling_step_count + 1)
    ]:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    probe_events = [
        event for event in events if event.event_kind == "BINARY_SEARCH_PROBE"
    ]
    if [event.step_id for event in probe_events] != [
        f"probe-{index:06d}" for index in range(1, binary_probe_count + 1)
    ]:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

    current_point: str | None = None
    expected_point = 1
    physical_points: list[SolidificationTraceEvent] = []
    service_events: list[SolidificationTraceEvent] = []
    scheil_current_solid = 0.0
    scheil_cumulative_phase_amounts: tuple[tuple[str, float], ...] = ()
    synthetic_events = [
        event
        for event in events
        if event.event_kind == "SYNTHETIC_INITIAL_INSERTION"
    ]
    if feature_id == "scheil_solidification":
        synthetic = synthetic_events[0] if len(synthetic_events) == 1 else None
        if (
            synthetic is None
            or synthetic.point_id != "point-000000"
            or synthetic.parent_point_id is not None
            or not synthetic.synthetic
            or synthetic.service
            or synthetic.temperature_k is None
            or synthetic.temperature_k <= 0.0
            or synthetic.pressure_pa is None
            or synthetic.pressure_pa <= 0.0
            or synthetic.solid_fraction is None
            or synthetic.liquid_fraction is None
            or not _same_f64(synthetic.solid_fraction, 0.0)
            or not _same_f64(synthetic.liquid_fraction, 1.0)
            or synthetic.phases != (liquid_phase,)
            or not _same_numeric_pairs(
                synthetic.raw_phase_fractions,
                ((liquid_phase, 1.0),),
            )
            or synthetic.raw_instance_mapping
            != ((liquid_phase, liquid_phase),)
            or synthetic.phase_amounts
            or not _same_numeric_pairs(
                synthetic.composition,
                bound_bulk_composition,
            )
            or tuple(name for name, _value in synthetic.liquid_composition)
            != independent_components
            or any(
                event.event_kind == "SOLVER_CALL_BEGIN"
                and event.ordinal < synthetic.ordinal
                for event in events
            )
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        _require_physical_composition_domain(synthetic.composition)
        _require_physical_pair_domain(
            synthetic.raw_phase_fractions,
            normalized_total=True,
            unique_names=True,
        )
        if (
            synthetic.fraction_residual_card is None
            or synthetic.phase_mapping_card is None
            or not _same_phase_mapping_card(
                synthetic.phase_mapping_card,
                _phase_mapping_card_from_bound(
                    provenance,
                    synthetic.raw_phase_fractions,
                    synthetic.raw_instance_mapping,
                ),
            )
            or not _same_f64(
                synthetic.fraction_residual_card.solid_fraction_raw,
                0.0,
            )
            or not _same_f64(
                synthetic.fraction_residual_card.liquid_fraction_raw,
                1.0,
            )
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        current_point = "point-000000"
    elif synthetic_events:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

    for event in events:
        if event.fraction_residual_card is not None:
            card = event.fraction_residual_card
            if (
                card.feature_id != feature_id
                or card.policy_id != provenance.fraction_roundoff_policy_id
                or card.solver_package
                != provenance.fraction_roundoff_solver_package
                or card.solver_version
                != provenance.fraction_roundoff_solver_version
                or card.upstream_package
                != provenance.fraction_roundoff_upstream_package
                or card.upstream_version
                != provenance.fraction_roundoff_upstream_version
                or not _same_f64(
                    card.absolute_tolerance,
                    provenance.fraction_roundoff_abs_tolerance,
                )
            ):
                _fail("W2B_INSTRUMENT_FRACTION_ROUNDOFF_INVALID")
        if event.event_kind == "ACCEPTED_PHYSICAL_POINT":
            call = result_by_call.get(event.solver_call_id or "")
            if (
                service_events
                or
                event.point_id != f"point-{expected_point:06d}"
                or event.parent_point_id != current_point
                or call is None
                or call.event_kind != "SOLVER_CALL_RESULT"
                or call.ordinal >= event.ordinal
                or call.stage != event.stage
                or call.parent_point_id != event.parent_point_id
                or not _same_optional_f64(call.temperature_k, event.temperature_k)
                or not _same_optional_f64(call.pressure_pa, event.pressure_pa)
                or not _same_numeric_pairs(call.composition, event.composition)
                or call.phases != event.phases
                or not _same_numeric_pairs(
                    call.raw_phase_fractions, event.raw_phase_fractions
                )
                or call.raw_instance_mapping != event.raw_instance_mapping
                or not _same_numeric_pairs(
                    call.liquid_composition, event.liquid_composition
                )
                or any(
                    item.event_kind == "SOLVER_CALL_BEGIN"
                    for item in events[call.ordinal + 1 : event.ordinal]
                )
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            if call.solver_converged is not True:
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            call_mapping_card = _validated_solver_result_card(
                provenance,
                call,
            )
            if (
                event.phase_mapping_card is None
                or not _same_phase_mapping_card(
                    event.phase_mapping_card,
                    call_mapping_card,
                )
                or tuple(name for name, _value in event.composition)
                != independent_components
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            if (
                not event.phases
                or not event.raw_phase_fractions
                or (
                    feature_id == "equilibrium_solidification"
                    and event.stage != "BINARY_SEARCH"
                    and call.outcome != "LIQUID_PRESENT"
                )
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            _require_linked_physical_domain(event, call)
            solid_call_amounts = _mapped_solid_amounts(call_mapping_card)
            if event.solid_fraction is None or event.liquid_fraction is None:
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            if feature_id == "equilibrium_solidification":
                expected_solid = call_mapping_card.raw_solid_fraction
                expected_liquid = (
                    call_mapping_card.derived_partition_liquid_fraction
                )
                if (
                    call_mapping_card.event_fraction_semantics
                    != "DERIVED_PARTITION_FROM_MAPPED_SOLID"
                    or not _same_numeric_pairs(
                        event.phase_amounts,
                        solid_call_amounts,
                    )
                    or not _same_f64(event.solid_fraction, expected_solid)
                    or not _same_f64(event.liquid_fraction, expected_liquid)
                ):
                    _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            else:
                if (
                    call.outcome != "LIQUID_PRESENT"
                    or _fraction_card_is_complete(
                        _fraction_residual_card(
                            feature_id,
                            scheil_current_solid,
                            1.0 - scheil_current_solid,
                        )
                    )
                ):
                    _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
                expected_increment_tuple, replay_solid = (
                    _scheil_mapped_increments(
                        call_mapping_card,
                        scheil_current_solid,
                    )
                )
                expected_liquid = 1.0 - replay_solid
                if (
                    not _same_numeric_pairs(
                        event.phase_amounts,
                        expected_increment_tuple,
                    )
                    or not _same_f64(event.solid_fraction, replay_solid)
                    or not _same_f64(event.liquid_fraction, expected_liquid)
                ):
                    _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
                scheil_cumulative_phase_amounts = (
                    _accumulate_scheil_phase_amounts(
                        scheil_cumulative_phase_amounts,
                        expected_increment_tuple,
                    )
                )
                cumulative_sum = _sequential_sum(
                    scheil_cumulative_phase_amounts
                )
                if (
                    not _math.isfinite(cumulative_sum)
                    or abs(cumulative_sum - replay_solid)
                    > FRACTION_ROUNDOFF_ABS_TOLERANCE
                ):
                    _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
                scheil_current_solid = replay_solid
            physical_points.append(event)
            current_point = event.point_id
            expected_point += 1
        elif event.event_kind == "NO_LIQUID_FAILURE":
            call = result_by_call.get(event.solver_call_id or "")
            if (
                call is None
                or call.event_kind != "SOLVER_CALL_RESULT"
                or call.outcome not in ("NO_LIQUID", "NO_PHASES")
                or call.ordinal >= event.ordinal
                or call.parent_point_id != event.parent_point_id
                or call.stage != event.stage
                or not _same_optional_f64(call.temperature_k, event.temperature_k)
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        elif event.event_kind == "PHYSICAL_VALIDATION_FAILURE":
            call = result_by_call.get(event.solver_call_id or "")
            if (
                call is None
                or call.event_kind != "SOLVER_CALL_RESULT"
                or call.ordinal >= event.ordinal
                or call.parent_point_id != event.parent_point_id
                or call.stage != event.stage
                or event.reason_code
                != "W2B_INSTRUMENT_PHYSICAL_WITNESS_INVALID"
                or not _same_optional_f64(call.temperature_k, event.temperature_k)
                or call.phases != event.phases
                or not _same_numeric_pairs(
                    call.raw_phase_fractions,
                    event.raw_phase_fractions,
                )
                or call.raw_instance_mapping != event.raw_instance_mapping
                or not _same_numeric_pairs(
                    call.phase_amounts,
                    event.phase_amounts,
                )
                or not _same_numeric_pairs(
                    call.liquid_composition,
                    event.liquid_composition,
                )
                or any(
                    point.event_kind == "ACCEPTED_PHYSICAL_POINT"
                    and point.solver_call_id == call.solver_call_id
                    for point in events
                )
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            try:
                _validated_solver_result_card(provenance, call)
            except SolidificationInstrumentationError:
                pass
            else:
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        elif event.event_kind == "SERVICE_CLOSURE":
            call = result_by_call.get(event.solver_call_id or "")
            if (
                feature_id != "scheil_solidification"
                or service_events
                or event.point_id != f"point-{expected_point:06d}"
                or event.parent_point_id != current_point
                or call is None
                or call.event_kind != "SOLVER_CALL_RESULT"
                or call.ordinal >= event.ordinal
                or call.gm_converged is not True
                or not event.synthetic
                or not event.service
                or event.solid_fraction is None
                or event.liquid_fraction is None
                or not _same_optional_f64(
                    event.closure_residual_fraction, event.liquid_fraction
                )
                or event.fraction_residual_card is None
                or abs(event.fraction_residual_card.balance_residual_raw)
                > provenance.fraction_roundoff_abs_tolerance
                or call.phases != event.phases
                or not _same_numeric_pairs(
                    call.raw_phase_fractions, event.raw_phase_fractions
                )
                or call.raw_instance_mapping != event.raw_instance_mapping
                or not _same_numeric_pairs(
                    call.liquid_composition, event.liquid_composition
                )
                or any(
                    result.event_kind == "SOLVER_CALL_BEGIN"
                    and result.ordinal > event.ordinal
                    for result in events
                )
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            converged_results = sorted(
                (
                    result
                    for result in result_by_call.values()
                    if result.ordinal < event.ordinal
                    and result.gm_converged is True
                ),
                key=lambda result: result.ordinal,
            )
            if not converged_results or converged_results[-1] is not call:
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            _require_linked_physical_domain(event, call)
            call_mapping_card = _validated_solver_result_card(
                provenance,
                call,
            )
            if (
                event.phase_mapping_card is None
                or not _same_phase_mapping_card(
                    event.phase_mapping_card,
                    call_mapping_card,
                )
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            remaining = 1.0 - scheil_current_solid
            expected_closure = _mapped_service_closure(
                call_mapping_card,
                remaining,
            )
            if (
                event.solid_fraction is None
                or event.liquid_fraction is None
                or event.closure_residual_fraction is None
                or event.closure_unfilled_gap is None
                or not _same_numeric_pairs(
                    event.phase_amounts,
                    expected_closure,
                )
                or not _same_f64(
                    event.solid_fraction,
                    scheil_current_solid,
                )
                or not _same_f64(event.liquid_fraction, remaining)
                or not _same_f64(
                    event.closure_residual_fraction,
                    remaining,
                )
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            closure_sum = _sequential_sum(expected_closure)
            closure_gap = remaining - closure_sum
            closure_cap = _closure_evidence_excursion_cap(
                len(physical_points)
            )
            # The service row is explicitly non-physical: preserve the exact
            # raw closure contribution and the unfilled gap.  Never rescale it
            # to make the phase amounts add to the residual liquid fraction.
            if (
                not _math.isfinite(closure_sum)
                or not _math.isfinite(closure_gap)
                or event.closure_evidence_policy_id
                != _fixed_value("scheil_closure_evidence_policy_id")
                or event.closure_accepted_point_count
                != len(physical_points)
                or event.closure_excursion_abs_cap is None
                or not _same_f64(
                    event.closure_excursion_abs_cap,
                    closure_cap,
                )
                or event.closure_residual_classification
                != _closure_evidence_classification(
                    remaining,
                    closure_cap,
                )
                or event.closure_gap_classification
                != _closure_evidence_classification(
                    closure_gap,
                    closure_cap,
                )
                or not _same_f64(event.closure_unfilled_gap, closure_gap)
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            service_events.append(event)
            current_point = event.point_id
            expected_point += 1
    terminal = events[-1]
    if terminal.parent_point_id != current_point:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

    if termination_outcome == "BUDGET_EXHAUSTED":
        witness = events[-2]
        if witness.event_kind != "BUDGET_EXHAUSTED":
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        expected_limit = {
            "W2B_INSTRUMENT_EVENT_BUDGET": budget.max_events,
            "W2B_INSTRUMENT_SOLVER_BUDGET": budget.max_solver_calls,
            "W2B_INSTRUMENT_COOLING_BUDGET": budget.max_cooling_steps,
            "W2B_INSTRUMENT_BINARY_BUDGET": budget.max_binary_probes,
        }.get(termination_reason_code)
        if witness.budget_limit != expected_limit:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if termination_reason_code == "W2B_INSTRUMENT_EVENT_BUDGET":
            exhausted = (
                witness.budget_used == witness.ordinal
                and witness.budget_used + witness.budget_required
                > budget.max_events - 2
            )
        else:
            actual_used = {
                "W2B_INSTRUMENT_SOLVER_BUDGET": solver_call_count,
                "W2B_INSTRUMENT_COOLING_BUDGET": cooling_step_count,
                "W2B_INSTRUMENT_BINARY_BUDGET": binary_probe_count,
            }.get(termination_reason_code)
            exhausted = (
                witness.budget_used == actual_used
                and witness.budget_used + witness.budget_required
                > witness.budget_limit
            )
        if not exhausted:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

    run_errors = [event for event in events if event.event_kind == "RUN_ERROR"]
    if run_errors:
        if (
            len(run_errors) != 1
            or events[-2] is not run_errors[0]
            or termination_outcome != "ERROR"
            or termination_reason_code != "W2B_INSTRUMENT_RUN_ERROR"
            or _event_exception_card(terminal)
            != _event_exception_card(run_errors[0])
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

    solver_errors = [
        event for event in events if event.event_kind == "SOLVER_CALL_ERROR"
    ]
    if termination_reason_code == "W2B_INSTRUMENT_SOLVER_ERROR":
        if not solver_errors:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        failed = solver_errors[-1]
        if (
            termination_outcome != "ERROR"
            or terminal.solver_call_id != failed.solver_call_id
            or terminal.step_id != failed.step_id
            or terminal.parent_point_id != failed.parent_point_id
            or not _same_optional_f64(terminal.temperature_k, failed.temperature_k)
            or _event_exception_card(terminal) != _event_exception_card(failed)
            or any(
                event.event_kind == "SOLVER_CALL_BEGIN"
                for event in events[failed.ordinal + 1 :]
            )
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

    if termination_outcome == "ERROR" and termination_reason_code not in (
        "W2B_INSTRUMENT_SOLVER_ERROR",
        "W2B_INSTRUMENT_RUN_ERROR",
        "W2B_INSTRUMENT_INITIAL_LIQUID_REQUIRED",
        "W2B_INSTRUMENT_NO_CALCULATION",
        "W2B_INSTRUMENT_PHYSICAL_WITNESS_INVALID",
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    if termination_reason_code == "W2B_INSTRUMENT_INITIAL_LIQUID_REQUIRED":
        witness = events[-2]
        if (
            witness.event_kind != "NO_LIQUID_FAILURE"
            or witness.parent_point_id != terminal.parent_point_id
            or witness.solver_call_id is None
            or not _same_optional_f64(witness.temperature_k, terminal.temperature_k)
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    if termination_reason_code == "W2B_INSTRUMENT_NO_CALCULATION":
        witness = events[-2]
        if (
            witness.event_kind != "NO_CALCULATION_FAILURE"
            or witness.reason_code != termination_reason_code
            or witness.parent_point_id != terminal.parent_point_id
            or not _same_optional_f64(witness.temperature_k, terminal.temperature_k)
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    if termination_reason_code == "W2B_INSTRUMENT_PHYSICAL_WITNESS_INVALID":
        witness = events[-2]
        if (
            witness.event_kind != "PHYSICAL_VALIDATION_FAILURE"
            or witness.reason_code != termination_reason_code
            or witness.parent_point_id != terminal.parent_point_id
            or not _same_optional_f64(
                witness.temperature_k,
                terminal.temperature_k,
            )
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

    if termination_outcome == "BOUND_REACHED":
        if termination_reason_code != "W2B_INSTRUMENT_TEMPERATURE_BOUND":
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        witness = events[-2]
        if feature_id == "equilibrium_solidification":
            valid_bound = (
                witness.event_kind == "ACCEPTED_PHYSICAL_POINT"
                and witness.point_id == terminal.parent_point_id
            )
        else:
            valid_bound = (
                witness.event_kind == "SERVICE_CLOSURE"
                and witness.reason_code == termination_reason_code
                and witness.point_id == terminal.parent_point_id
            )
        if not valid_bound:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

    if termination_outcome == "NOT_CONVERGED":
        witness = events[-2]
        if feature_id == "equilibrium_solidification":
            valid_nonconverged = (
                witness.event_kind == "BINARY_SEARCH_END"
                and physical_points
                and witness.parent_point_id == physical_points[-1].point_id
                and physical_points[-1].fraction_residual_card is not None
                and physical_points[-1].phase_mapping_card is not None
                and (
                    not _fraction_card_is_complete(
                        physical_points[-1].fraction_residual_card
                    )
                    or not physical_points[
                        -1
                    ].phase_mapping_card.physical_balance_satisfied
                )
            )
        else:
            valid_nonconverged = (
                witness.event_kind == "SERVICE_CLOSURE"
                and witness.reason_code == termination_reason_code
                and termination_reason_code
                == "W2B_INSTRUMENT_STEP_REDUCTION_LIMIT"
            )
        if not valid_nonconverged:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

    if termination_outcome == "CONVERGED":
        if feature_id != "equilibrium_solidification":
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if not physical_points or solver_call_count == 0 or solver_errors:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        witness = physical_points[-1]
        result = result_by_call[witness.solver_call_id or ""]
        if result.solver_converged is not True:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if (
            events[-2].event_kind != "BINARY_SEARCH_END"
            or events[-2].parent_point_id != witness.point_id
            or witness.stage != "BINARY_SEARCH"
            or witness.fraction_residual_card is None
            or witness.phase_mapping_card is None
            or not witness.phase_mapping_card.physical_balance_satisfied
            or not _fraction_card_is_complete(
                witness.fraction_residual_card
            )
            or not any(
                event.event_kind == "BINARY_SEARCH_BEGIN" for event in events
            )
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")

    if termination_outcome == "STOP_CRITERION_REACHED_PARTIAL":
        stop = provenance.stop_liquid_fraction
        if (
            feature_id != "scheil_solidification"
            or termination_reason_code
            != "W2B_INSTRUMENT_STOP_CRITERION_REACHED_PARTIAL"
            or stop is None
            or not physical_points
            or not service_events
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        witness = physical_points[-1]
        closure = service_events[0]
        result = result_by_call[witness.solver_call_id or ""]
        if (
            witness.liquid_fraction is None
            or not witness.liquid_fraction < stop
            or witness.phase_mapping_card is None
            or witness.phase_mapping_card.raw_liquid_fraction <= 0.0
            or result.solver_converged is not True
            or closure.parent_point_id != witness.point_id
            or not _same_optional_f64(
                closure.closure_residual_fraction, witness.liquid_fraction
            )
            or events[-2] is not closure
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")


@_dataclass(frozen=True, slots=True)
class InstrumentedSolidificationTrace:
    provenance: TraceProvenance
    feature_id: str
    events: tuple[SolidificationTraceEvent, ...]
    budget: InstrumentationBudget
    termination_outcome: str
    termination_reason_code: str | None
    solver_call_count: int
    cooling_step_count: int
    binary_probe_count: int
    canonical_digest: str = _field(init=False)

    def __post_init__(self) -> None:
        try:
            _require_fixed_authority()
            self._validate_and_finalize()
        except SolidificationInstrumentationError:
            raise
        except Exception as error:
            raise SolidificationInstrumentationError(
                "W2B_INSTRUMENT_OBSERVATION_INVALID"
            ) from error

    def _validate_and_finalize(self) -> None:
        if type(self.provenance) is not TraceProvenance:
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        provenance = TraceProvenance(**self.provenance.__dict__) if hasattr(self.provenance, "__dict__") else TraceProvenance(
            **{name: getattr(self.provenance, name) for name in self.provenance.__slots__}
        )
        if not _fixed_feature_allowed(self.feature_id):
            _fail("W2B_INSTRUMENT_REQUEST_INVALID")
        if type(self.events) is not tuple or not self.events:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        events = tuple(_copy_event(item, ordinal) for ordinal, item in enumerate(self.events))
        if events[0].event_kind != "RUN_START" or events[-1].event_kind != "TERMINATION":
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if type(self.termination_outcome) is not str or self.termination_outcome not in (
            "CONVERGED",
            "STOP_CRITERION_REACHED_PARTIAL",
            "NOT_CONVERGED",
            "ERROR",
            "BUDGET_EXHAUSTED",
            "BOUND_REACHED",
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if events[-1].outcome != self.termination_outcome:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.termination_reason_code is not None and (
            type(self.termination_reason_code) is not str
            or self.termination_reason_code not in INSTRUMENTATION_REASON_CODES
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if events[-1].reason_code != self.termination_reason_code:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        budget_reasons = {
            "W2B_INSTRUMENT_EVENT_BUDGET",
            "W2B_INSTRUMENT_SOLVER_BUDGET",
            "W2B_INSTRUMENT_COOLING_BUDGET",
            "W2B_INSTRUMENT_BINARY_BUDGET",
        }
        if (
            (self.termination_outcome == "CONVERGED" and self.termination_reason_code is not None)
            or (
                self.termination_outcome == "BUDGET_EXHAUSTED"
                and self.termination_reason_code not in budget_reasons
            )
            or (
                self.termination_outcome == "BOUND_REACHED"
                and self.termination_reason_code != "W2B_INSTRUMENT_TEMPERATURE_BOUND"
            )
            or (
                self.termination_outcome == "NOT_CONVERGED"
                and self.termination_reason_code
                not in (None, "W2B_INSTRUMENT_STEP_REDUCTION_LIMIT")
            )
            or (self.termination_outcome == "ERROR" and self.termination_reason_code is None)
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        budget = _copy_budget(self.budget)
        counts = (self.solver_call_count, self.cooling_step_count, self.binary_probe_count)
        if any(type(item) is not int or isinstance(item, bool) or item < 0 for item in counts):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if (
            self.solver_call_count != sum(item.event_kind == "SOLVER_CALL_BEGIN" for item in events)
            or self.cooling_step_count != sum(item.event_kind == "COOLING_STEP" for item in events)
            or self.binary_probe_count != sum(item.event_kind == "BINARY_SEARCH_PROBE" for item in events)
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if (
            len(events) > budget.max_events
            or self.solver_call_count > budget.max_solver_calls
            or self.cooling_step_count > budget.max_cooling_steps
            or self.binary_probe_count > budget.max_binary_probes
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.termination_outcome == "BUDGET_EXHAUSTED":
            if (
                len(events) < 2
                or events[-2].event_kind != "BUDGET_EXHAUSTED"
                or events[-2].outcome != "BUDGET_EXHAUSTED"
                or events[-2].reason_code != self.termination_reason_code
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        begin_events = [item for item in events if item.event_kind == "SOLVER_CALL_BEGIN"]
        end_events = [
            item
            for item in events
            if item.event_kind in ("SOLVER_CALL_RESULT", "SOLVER_CALL_ERROR")
        ]
        begin_ids = [item.solver_call_id for item in begin_events]
        end_ids = [item.solver_call_id for item in end_events]
        if (
            any(item is None for item in begin_ids + end_ids)
            or len(set(begin_ids)) != len(begin_ids)
            or set(begin_ids) != set(end_ids)
            or len(end_ids) != len(begin_ids)
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        terminal_by_id = {item.solver_call_id: item for item in end_events}
        if any(
            terminal_by_id[item.solver_call_id].ordinal <= item.ordinal
            for item in begin_events
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        for begin in begin_events:
            terminal = terminal_by_id[begin.solver_call_id]
            if (
                begin.stage != terminal.stage
                or not _same_optional_f64(begin.temperature_k, terminal.temperature_k)
                or not _same_optional_f64(begin.pressure_pa, terminal.pressure_pa)
                or not _same_numeric_pairs(begin.composition, terminal.composition)
                or begin.parent_point_id != terminal.parent_point_id
                or begin.step_id != terminal.step_id
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        probes = [item for item in events if item.event_kind == "BINARY_SEARCH_PROBE"]
        directions = [
            item for item in events if item.event_kind == "BINARY_SEARCH_DIRECTION"
        ]
        probe_ids = [item.step_id for item in probes]
        if (
            any(item is None for item in probe_ids)
            or len(set(probe_ids)) != len(probe_ids)
            or len(directions) != len(probes)
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        for probe in probes:
            matching_begins = [item for item in begin_events if item.step_id == probe.step_id]
            matching_directions = [
                item for item in directions if item.step_id == probe.step_id
            ]
            if len(matching_begins) != 1 or len(matching_directions) != 1:
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            begin = matching_begins[0]
            terminal = terminal_by_id[begin.solver_call_id]
            direction = matching_directions[0]
            if not (probe.ordinal < begin.ordinal < terminal.ordinal < direction.ordinal):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            if (
                probe.stage != "BINARY_SEARCH"
                or begin.stage != "BINARY_SEARCH"
                or direction.stage != "BINARY_SEARCH"
                or not _same_optional_f64(probe.temperature_k, begin.temperature_k)
                or not _same_optional_f64(begin.temperature_k, direction.temperature_k)
                or probe.parent_point_id != begin.parent_point_id
                or begin.parent_point_id != direction.parent_point_id
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            if terminal.event_kind == "SOLVER_CALL_ERROR":
                if direction.outcome != "ERROR":
                    _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            elif terminal.outcome == "LIQUID_PRESENT":
                if direction.outcome != "UPDATE_HIGH":
                    _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            elif direction.outcome != "UPDATE_LOW":
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        accepted = [
            item for item in events if item.event_kind == "ACCEPTED_PHYSICAL_POINT"
        ]
        for point in accepted:
            if (
                point.point_id is None
                or point.synthetic
                or point.service
                or point.solid_fraction is None
                or point.liquid_fraction is None
                or not _math.isfinite(point.solid_fraction)
                or not _math.isfinite(point.liquid_fraction)
                or point.fraction_residual_card is None
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if self.termination_outcome == "CONVERGED":
            if self.feature_id != "equilibrium_solidification":
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            if self.solver_call_count == 0 or any(
                item.event_kind == "SOLVER_CALL_ERROR" for item in events
            ):
                _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            if self.feature_id == "equilibrium_solidification":
                search_ends = [
                    item for item in events if item.event_kind == "BINARY_SEARCH_END"
                ]
                if (
                    provenance.binary_search_tolerance_k is None
                    or provenance.stop_liquid_fraction is not None
                    or len(search_ends) != 1
                ):
                    _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
                search_end = search_ends[0]
                witnesses = [
                    item
                    for item in accepted
                    if item.stage == "BINARY_SEARCH"
                    and item.point_id == search_end.parent_point_id
                    and item.fraction_residual_card is not None
                    and _fraction_card_is_complete(
                        item.fraction_residual_card
                    )
                ]
                if (
                    len(witnesses) != 1
                    or search_end.bracket_low_k is None
                    or search_end.bracket_high_k is None
                    or search_end.bracket_high_k < search_end.bracket_low_k
                    or search_end.bracket_high_k - search_end.bracket_low_k
                    > provenance.binary_search_tolerance_k
                ):
                    _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
            else:
                stop = provenance.stop_liquid_fraction
                if (
                    stop is None
                    or provenance.binary_search_tolerance_k is not None
                    or not any(
                        point.stage == "COOLING"
                        and point.liquid_fraction is not None
                        and point.liquid_fraction < stop
                        for point in accepted
                    )
                ):
                    _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        _validate_event_state_machine(
            events=events,
            feature_id=self.feature_id,
            provenance=provenance,
            budget=budget,
            termination_outcome=self.termination_outcome,
            termination_reason_code=self.termination_reason_code,
            solver_call_count=self.solver_call_count,
            cooling_step_count=self.cooling_step_count,
            binary_probe_count=self.binary_probe_count,
        )
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "budget", budget)
        object.__setattr__(self, "canonical_digest", _hashlib.sha256(_canonical_bytes(self._payload())).hexdigest())

    def _payload(self) -> dict[str, object]:
        return {
            "schema_version": _fixed_value("trace_schema"),
            "provenance": self.provenance.as_dict(),
            "feature_id": self.feature_id,
            "events": [item.as_dict() for item in self.events],
            "budget": {
                "max_events": self.budget.max_events,
                "max_solver_calls": self.budget.max_solver_calls,
                "max_cooling_steps": self.budget.max_cooling_steps,
                "max_binary_probes": self.budget.max_binary_probes,
            },
            "termination_outcome": self.termination_outcome,
            "termination_reason_code": self.termination_reason_code,
            "solver_call_count": self.solver_call_count,
            "cooling_step_count": self.cooling_step_count,
            "binary_probe_count": self.binary_probe_count,
            "acceptance_claim": False,
            "counts_toward_feature_coverage": False,
            "production_use": "DENIED",
        }

    def as_dict(self) -> dict[str, object]:
        _require_fixed_authority()
        rebuilt = _copy_trace(self)
        _verify_trace_environment(rebuilt.provenance)
        payload = rebuilt._payload()
        payload["canonical_digest"] = rebuilt.canonical_digest
        return payload


def _copy_trace(value: object) -> InstrumentedSolidificationTrace:
    if type(value) is not InstrumentedSolidificationTrace:
        _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
    try:
        provenance = TraceProvenance(
            **{name: getattr(value.provenance, name) for name in value.provenance.__slots__}
        )
        rebuilt = InstrumentedSolidificationTrace(
            provenance=provenance,
            feature_id=value.feature_id,
            events=value.events,
            budget=value.budget,
            termination_outcome=value.termination_outcome,
            termination_reason_code=value.termination_reason_code,
            solver_call_count=value.solver_call_count,
            cooling_step_count=value.cooling_step_count,
            binary_probe_count=value.binary_probe_count,
        )
        original_digest = value.canonical_digest
        if (
            type(original_digest) is not str
            or original_digest != rebuilt.canonical_digest
        ):
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
    except SolidificationInstrumentationError:
        raise
    except Exception as error:
        raise SolidificationInstrumentationError("W2B_INSTRUMENT_CONTEXT_INVALID") from error
    return rebuilt


def trace_canonical_bytes(trace: object) -> bytes:
    """Return canonical trace bytes; all floats are exact big-endian binary64 hex."""

    _require_fixed_authority()
    rebuilt = _copy_trace(trace)
    _verify_trace_environment(rebuilt.provenance)
    payload = rebuilt._payload()
    payload["canonical_digest"] = rebuilt.canonical_digest
    return _canonical_bytes(payload)


@_dataclass(frozen=True, slots=True)
class _SolverObservation:
    converged: bool
    gm_converged: bool
    stable_phases: tuple[str, ...]
    raw_phase_fractions: tuple[tuple[str, float], ...]
    phase_amounts: tuple[tuple[str, float], ...]
    liquid_composition: tuple[tuple[str, float], ...]
    raw_instance_mapping: tuple[tuple[str, str], ...] = ()
    ordering_rename_authority: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if type(self.converged) is not bool or type(self.gm_converged) is not bool:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        object.__setattr__(self, "stable_phases", _names(self.stable_phases))
        object.__setattr__(self, "raw_phase_fractions", _numeric_pairs(self.raw_phase_fractions))
        object.__setattr__(self, "phase_amounts", _numeric_pairs(self.phase_amounts))
        object.__setattr__(self, "liquid_composition", _numeric_pairs(self.liquid_composition))
        object.__setattr__(self, "raw_instance_mapping", _name_pairs(self.raw_instance_mapping))
        object.__setattr__(
            self,
            "ordering_rename_authority",
            _ordering_instance_authority_pairs(
                self.ordering_rename_authority
            ),
        )


class _AttemptSolver(_Protocol):
    liquid_phase: str

    def solve(
        self,
        *,
        temperature_k: float,
        pressure_pa: float,
        composition: tuple[tuple[str, float], ...],
        stage: str,
        call_id: str,
    ) -> _SolverObservation: ...


@_dataclass(frozen=True, slots=True)
class _RunSpec:
    feature_id: str
    components: tuple[str, ...]
    bulk_composition: tuple[tuple[str, float], ...]
    solver_composition: tuple[tuple[str, float], ...]
    phases: tuple[str, ...]
    liquid_phase: str
    pressure_pa: float
    start_temperature_k: float
    minimum_temperature_k: float
    step_temperature_k: float
    adaptive: bool
    pdens: int
    binary_search_tolerance_k: float | None
    stop_liquid_fraction: float | None

    def __post_init__(self) -> None:
        _require_fixed_authority()
        if not _fixed_feature_allowed(self.feature_id):
            _fail("W2B_INSTRUMENT_REQUEST_INVALID")
        object.__setattr__(self, "components", _names(self.components))
        object.__setattr__(self, "bulk_composition", _numeric_pairs(self.bulk_composition))
        object.__setattr__(self, "solver_composition", _numeric_pairs(self.solver_composition))
        object.__setattr__(self, "phases", _names(self.phases))
        liquid = _token(self.liquid_phase)
        assert liquid is not None
        object.__setattr__(self, "liquid_phase", liquid)
        for name in ("pressure_pa", "start_temperature_k", "minimum_temperature_k", "step_temperature_k"):
            object.__setattr__(self, name, _f64(getattr(self, name), allow_nonfinite=False))
        if (
            self.pressure_pa != _fixed_value("solidification_pressure_pa")
            or self.minimum_temperature_k <= 0.0
            or self.start_temperature_k <= self.minimum_temperature_k
            or self.step_temperature_k <= 0.0
        ):
            _fail("W2B_INSTRUMENT_REQUEST_INVALID")
        if self.adaptive is not False:
            _fail("W2B_INSTRUMENT_ADAPTIVE_UNSUPPORTED")
        if (
            type(self.pdens) is not int
            or isinstance(self.pdens, bool)
            or not 1 <= self.pdens <= 100_000
        ):
            _fail("W2B_INSTRUMENT_REQUEST_INVALID")
        if self.feature_id == "equilibrium_solidification":
            tolerance = _f64(self.binary_search_tolerance_k, allow_nonfinite=False)
            if tolerance <= 0.0 or tolerance > self.step_temperature_k or self.stop_liquid_fraction is not None:
                _fail("W2B_INSTRUMENT_REQUEST_INVALID")
            object.__setattr__(self, "binary_search_tolerance_k", tolerance)
        else:
            stop = _f64(self.stop_liquid_fraction, allow_nonfinite=False)
            if not 0.0 < stop < 1.0 or self.binary_search_tolerance_k is not None:
                _fail("W2B_INSTRUMENT_REQUEST_INVALID")
            object.__setattr__(self, "stop_liquid_fraction", stop)


class _BudgetExceeded(Exception):
    __slots__ = ("reason_code", "budget_limit", "budget_used", "budget_required")

    def __init__(
        self,
        reason_code: str,
        budget_limit: int,
        budget_used: int,
        budget_required: int,
    ) -> None:
        self.reason_code = reason_code
        self.budget_limit = budget_limit
        self.budget_used = budget_used
        self.budget_required = budget_required
        super().__init__(reason_code)


class _SolverRaised(Exception):
    __slots__ = (
        "temperature_k",
        "parent_point_id",
        "step_id",
        "solver_call_id",
        "exception_type",
        "exception_type_sha256",
        "exception_message_sha256",
    )

    def __init__(
        self,
        *,
        temperature_k: float,
        parent_point_id: str | None,
        step_id: str | None,
        solver_call_id: str,
        exception_card: tuple[str, str, str],
    ) -> None:
        self.temperature_k = temperature_k
        self.parent_point_id = parent_point_id
        self.step_id = step_id
        self.solver_call_id = solver_call_id
        (
            self.exception_type,
            self.exception_type_sha256,
            self.exception_message_sha256,
        ) = exception_card
        super().__init__(solver_call_id)


class _Recorder:
    __slots__ = (
        "budget",
        "events",
        "solver_calls",
        "cooling_steps",
        "binary_probes",
        "last_solver_call_id",
        "finalization_guard",
    )

    def __init__(self, budget: InstrumentationBudget) -> None:
        self.budget = _copy_budget(budget)
        self.events: list[SolidificationTraceEvent] = []
        self.solver_calls = 0
        self.cooling_steps = 0
        self.binary_probes = 0
        self.last_solver_call_id: str | None = None
        self.finalization_guard: object | None = None

    def emit(self, *, reserved: bool = False, **kwargs: object) -> SolidificationTraceEvent:
        event = self.prepare_event(reserved=reserved, **kwargs)
        self.events.append(event)
        return event

    def prepare_event(
        self,
        *,
        reserved: bool = False,
        **kwargs: object,
    ) -> SolidificationTraceEvent:
        limit = self.budget.max_events if reserved else self.budget.max_events - 2
        if len(self.events) >= limit:
            raise _BudgetExceeded(
                "W2B_INSTRUMENT_EVENT_BUDGET",
                self.budget.max_events,
                len(self.events),
                1,
            )
        event = SolidificationTraceEvent(ordinal=len(self.events), **kwargs)
        return event

    def _require_ordinary_slots(self, count: int = 1) -> None:
        if len(self.events) + count > self.budget.max_events - 2:
            raise _BudgetExceeded(
                "W2B_INSTRUMENT_EVENT_BUDGET",
                self.budget.max_events,
                len(self.events),
                count,
            )

    def consume_solver(self) -> str:
        # BEGIN and its matching RESULT/ERROR are admitted atomically.  A trace
        # can therefore never end with an unpaired solver invocation merely
        # because the event budget was reached between the two records.
        self._require_ordinary_slots(2)
        if self.solver_calls >= self.budget.max_solver_calls:
            raise _BudgetExceeded(
                "W2B_INSTRUMENT_SOLVER_BUDGET",
                self.budget.max_solver_calls,
                self.solver_calls,
                1,
            )
        self.solver_calls += 1
        return f"solver-{self.solver_calls:06d}"

    def consume_cooling(self) -> str:
        self._require_ordinary_slots()
        if self.cooling_steps >= self.budget.max_cooling_steps:
            raise _BudgetExceeded(
                "W2B_INSTRUMENT_COOLING_BUDGET",
                self.budget.max_cooling_steps,
                self.cooling_steps,
                1,
            )
        self.cooling_steps += 1
        return f"step-{self.cooling_steps:06d}"

    def allocate_binary_probe_unit(self) -> tuple[str, str]:
        # One admitted probe owns enough ordinary-event capacity for PROBE,
        # solver BEGIN, solver RESULT/ERROR, the worst-case NO_LIQUID record,
        # and the mandatory direction/decision.  Both counters advance only
        # after every budget check succeeds.
        self._require_ordinary_slots(5)
        if self.solver_calls >= self.budget.max_solver_calls:
            raise _BudgetExceeded(
                "W2B_INSTRUMENT_SOLVER_BUDGET",
                self.budget.max_solver_calls,
                self.solver_calls,
                1,
            )
        if self.binary_probes >= self.budget.max_binary_probes:
            raise _BudgetExceeded(
                "W2B_INSTRUMENT_BINARY_BUDGET",
                self.budget.max_binary_probes,
                self.binary_probes,
                1,
            )
        self.binary_probes += 1
        self.solver_calls += 1
        return (
            f"probe-{self.binary_probes:06d}",
            f"solver-{self.solver_calls:06d}",
        )


def _liquid_present(observation: _SolverObservation, liquid_phase: str) -> bool:
    return any(
        parsed is not None and parsed[0] == liquid_phase
        for parsed in (
            _phase_instance_parts(name) for name in observation.stable_phases
        )
    )


def _solid_amounts(observation: _SolverObservation, liquid_phase: str) -> tuple[tuple[str, float], ...]:
    return tuple(
        (name, value)
        for name, value in observation.phase_amounts
        if name != liquid_phase and not name.startswith(liquid_phase + "#")
    )


def _sequential_sum(values: tuple[tuple[str, float], ...]) -> float:
    total = 0.0
    for _name, value in values:
        total += value
    return total


def _solid_pair_amounts(
    values: tuple[tuple[str, float], ...],
    liquid_phase: str,
) -> tuple[tuple[str, float], ...]:
    return tuple(
        (name, value)
        for name, value in values
        if name != liquid_phase and not name.startswith(liquid_phase + "#")
    )


def _require_physical_pair_domain(
    values: tuple[tuple[str, float], ...],
    *,
    normalized_total: bool = False,
    unique_names: bool = False,
    observation_bounds: bool = False,
) -> float:
    """Validate raw physical binary64 values without clamping or rewriting."""

    tolerance = _fixed_value(
        "raw_normalization_observation_cap"
        if observation_bounds
        else "fraction_roundoff_abs_tolerance"
    )
    names: list[str] = []
    total = 0.0
    for name, value in values:
        if (
            type(name) is not str
            or type(value) is not float
            or not _math.isfinite(value)
            or value < -tolerance
            or value > 1.0 + tolerance
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        names.append(name)
        total += value
        if not _math.isfinite(total):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    if unique_names and len(names) != len(set(names)):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    if normalized_total and abs(total - 1.0) > tolerance:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    return total


def _require_physical_composition_domain(
    values: tuple[tuple[str, float], ...],
) -> None:
    total = _require_physical_pair_domain(values, unique_names=True)
    if total < -FRACTION_ROUNDOFF_ABS_TOLERANCE or total > (
        1.0 + FRACTION_ROUNDOFF_ABS_TOLERANCE
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")


def _require_linked_physical_domain(
    point: SolidificationTraceEvent,
    call: SolidificationTraceEvent,
) -> None:
    for value in (
        point.temperature_k,
        point.pressure_pa,
        point.step_temperature_k,
        point.solid_fraction,
        point.liquid_fraction,
        point.closure_residual_fraction,
    ):
        if value is not None and (
            type(value) is not float or not _math.isfinite(value)
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    if (
        point.temperature_k is None
        or point.temperature_k <= 0.0
        or point.pressure_pa is None
        or point.pressure_pa <= 0.0
        or (
            point.step_temperature_k is not None
            and point.step_temperature_k <= 0.0
        )
        or len(point.phases) != len(set(point.phases))
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    _require_physical_composition_domain(point.composition)
    _require_physical_pair_domain(
        point.raw_phase_fractions,
        unique_names=True,
        observation_bounds=True,
    )
    _require_physical_pair_domain(
        point.phase_amounts,
        observation_bounds=True,
    )
    _require_physical_composition_domain(point.liquid_composition)
    _require_physical_pair_domain(
        call.raw_phase_fractions,
        unique_names=True,
        observation_bounds=True,
    )
    _require_physical_pair_domain(
        call.phase_amounts,
        observation_bounds=True,
    )
    _require_physical_composition_domain(call.liquid_composition)


def _validated_solver_result_card(
    provenance: TraceProvenance,
    call: SolidificationTraceEvent,
) -> PhaseMappingCard:
    if (
        call.event_kind != "SOLVER_CALL_RESULT"
        or call.phase_mapping_card is None
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    card = _copy_phase_mapping_card(call.phase_mapping_card)
    if card.ordering_model_authority or card.ordering_rename_authority:
        _fail("W2B_INSTRUMENT_ORDERING_MAPPING_UNREPRESENTABLE")
    expected = _phase_mapping_card_from_bound(
        provenance,
        call.raw_phase_fractions,
        call.raw_instance_mapping,
        card.ordering_rename_authority,
    )
    if (
        not _same_phase_mapping_card(card, expected)
        or not card.physical_valid
        or call.phases != _mapped_present_phases(card)
        or not _same_numeric_pairs(
            call.phase_amounts,
            card.mapped_phase_fractions,
        )
        or not _liquid_composition_matches_card(
            call.liquid_composition,
            card,
        )
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    _require_physical_pair_domain(
        call.raw_phase_fractions,
        observation_bounds=True,
    )
    _require_physical_pair_domain(
        call.phase_amounts,
        observation_bounds=True,
    )
    _require_physical_composition_domain(call.liquid_composition)
    return card


def _scheil_mapped_increments(
    card: PhaseMappingCard,
    current_solid: float,
) -> tuple[tuple[tuple[str, float], ...], float]:
    replay = current_solid
    increments: list[tuple[str, float]] = []
    tolerance = _fixed_value("raw_normalization_observation_cap")
    for (raw_name, raw_amount), (mapped_source, mapped_phase) in zip(
        card.raw_phase_fractions,
        card.raw_instance_mapping,
    ):
        if raw_name != mapped_source:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        if mapped_phase == card.liquid_phase:
            continue
        increment = (1.0 - replay) * raw_amount
        if (
            not _math.isfinite(increment)
            or increment < -tolerance
            or increment > 1.0 + tolerance
        ):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        replay += increment
        if not _math.isfinite(replay):
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        increments.append((mapped_phase, increment))
    return tuple(increments), replay


def _mapped_service_closure(
    card: PhaseMappingCard,
    remaining: float,
) -> tuple[tuple[str, float], ...]:
    return tuple(
        (mapped_phase, raw_amount * remaining)
        for (raw_name, raw_amount), (mapped_source, mapped_phase) in zip(
            card.raw_phase_fractions,
            card.raw_instance_mapping,
        )
        if raw_name == mapped_source and mapped_phase != card.liquid_phase
    )


def _accumulate_scheil_phase_amounts(
    cumulative: tuple[tuple[str, float], ...],
    increments: tuple[tuple[str, float], ...],
) -> tuple[tuple[str, float], ...]:
    replay = list(cumulative)
    tolerance = _fixed_value("raw_normalization_observation_cap")
    for name, increment in increments:
        for index, (existing_name, existing_amount) in enumerate(replay):
            if existing_name == name:
                amount = existing_amount + increment
                if (
                    not _math.isfinite(amount)
                    or amount < -tolerance
                    or amount > 1.0 + tolerance
                ):
                    _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
                replay[index] = (existing_name, amount)
                break
        else:
            replay.append((name, increment))
    return tuple(replay)


def _same_value_sequence(
    left: tuple[tuple[str, float], ...],
    right: tuple[tuple[str, float], ...],
) -> bool:
    return len(left) == len(right) and all(
        _same_f64(left_value, right_value)
        for (_left_name, left_value), (_right_name, right_value) in zip(
            left, right
        )
    )


def _call_solver(
    recorder: _Recorder,
    solver: _AttemptSolver,
    provenance: TraceProvenance,
    *,
    temperature_k: float,
    pressure_pa: float,
    composition: tuple[tuple[str, float], ...],
    stage: str,
    parent_point_id: str | None,
    step_id: str | None,
    allocated_call_id: str | None = None,
) -> _SolverObservation:
    if allocated_call_id is None:
        call_id = recorder.consume_solver()
    else:
        call_id = allocated_call_id
        if (
            call_id != f"solver-{recorder.solver_calls:06d}"
            or any(item.solver_call_id == call_id for item in recorder.events)
        ):
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
    recorder.emit(
        event_kind="SOLVER_CALL_BEGIN",
        stage=stage,
        outcome="BEGIN",
        temperature_k=temperature_k,
        pressure_pa=pressure_pa,
        composition=composition,
        parent_point_id=parent_point_id,
        step_id=step_id,
        solver_call_id=call_id,
    )
    try:
        observed = solver.solve(
            temperature_k=temperature_k,
            pressure_pa=pressure_pa,
            composition=composition,
            stage=stage,
            call_id=call_id,
        )
        if type(observed) is not _SolverObservation:
            _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
        observation = _SolverObservation(
            converged=observed.converged,
            gm_converged=observed.gm_converged,
            stable_phases=observed.stable_phases,
            raw_phase_fractions=observed.raw_phase_fractions,
            phase_amounts=observed.phase_amounts,
            liquid_composition=observed.liquid_composition,
            raw_instance_mapping=observed.raw_instance_mapping,
            ordering_rename_authority=observed.ordering_rename_authority,
        )
    except Exception as error:
        exception_type, type_digest, message_digest = _exception_card(error)
        recorder.emit(
            event_kind="SOLVER_CALL_ERROR",
            stage=stage,
            outcome="ERROR",
            temperature_k=temperature_k,
            pressure_pa=pressure_pa,
            composition=composition,
            parent_point_id=parent_point_id,
            step_id=step_id,
            solver_call_id=call_id,
            reason_code="W2B_INSTRUMENT_SOLVER_ERROR",
            exception_type=exception_type,
            exception_type_sha256=type_digest,
            exception_message_sha256=message_digest,
        )
        raise _SolverRaised(
            temperature_k=temperature_k,
            parent_point_id=parent_point_id,
            step_id=step_id,
            solver_call_id=call_id,
            exception_card=(exception_type, type_digest, message_digest),
        ) from error
    mapping_card = _phase_mapping_card_from_bound(
        provenance,
        observation.raw_phase_fractions,
        observation.raw_instance_mapping,
        observation.ordering_rename_authority,
    )
    present = _liquid_present(observation, solver.liquid_phase)
    outcome = "LIQUID_PRESENT" if present else ("NO_PHASES" if not observation.stable_phases else "NO_LIQUID")
    recorder.emit(
        event_kind="SOLVER_CALL_RESULT",
        stage=stage,
        outcome=outcome,
        temperature_k=temperature_k,
        pressure_pa=pressure_pa,
        composition=composition,
        phases=observation.stable_phases,
        raw_phase_fractions=observation.raw_phase_fractions,
        raw_instance_mapping=observation.raw_instance_mapping,
        phase_amounts=observation.phase_amounts,
        liquid_composition=observation.liquid_composition,
        solver_converged=observation.converged,
        gm_converged=observation.gm_converged,
        parent_point_id=parent_point_id,
        step_id=step_id,
        solver_call_id=call_id,
        phase_mapping_card=mapping_card,
    )
    recorder.last_solver_call_id = call_id
    return observation


def _emit_linked_physical_event(
    recorder: _Recorder,
    provenance: TraceProvenance,
    **kwargs: object,
) -> SolidificationTraceEvent:
    """Validate a runtime physical witness before the append-only commit."""

    point = recorder.prepare_event(**kwargs)
    call_id = point.solver_call_id
    call = next(
        (
            event
            for event in reversed(recorder.events)
            if event.event_kind == "SOLVER_CALL_RESULT"
            and event.solver_call_id == call_id
        ),
        None,
    )
    if call is None:
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    call_card = _validated_solver_result_card(provenance, call)
    if (
        point.phase_mapping_card is None
        or not _same_phase_mapping_card(point.phase_mapping_card, call_card)
        or point.raw_instance_mapping != call.raw_instance_mapping
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    _require_linked_physical_domain(point, call)
    recorder.events.append(point)
    return point


def _runtime_physical_card_or_failure(
    recorder: _Recorder,
    provenance: TraceProvenance,
    *,
    stage: str,
    temperature_k: float,
    pressure_pa: float,
    step_temperature_k: float | None,
    composition: tuple[tuple[str, float], ...],
    parent_point_id: str | None,
    step_id: str | None = None,
) -> PhaseMappingCard | None:
    call = next(
        (
            event
            for event in reversed(recorder.events)
            if event.event_kind == "SOLVER_CALL_RESULT"
            and event.solver_call_id == recorder.last_solver_call_id
        ),
        None,
    )
    if (
        type(call) is not SolidificationTraceEvent
        or call.event_kind != "SOLVER_CALL_RESULT"
        or call.solver_call_id != recorder.last_solver_call_id
    ):
        _fail("W2B_INSTRUMENT_OBSERVATION_INVALID")
    try:
        return _validated_solver_result_card(provenance, call)
    except SolidificationInstrumentationError:
        recorder.emit(
            event_kind="PHYSICAL_VALIDATION_FAILURE",
            stage=stage,
            outcome="ERROR",
            temperature_k=temperature_k,
            pressure_pa=pressure_pa,
            step_temperature_k=step_temperature_k,
            composition=composition,
            phases=call.phases,
            raw_phase_fractions=call.raw_phase_fractions,
            raw_instance_mapping=call.raw_instance_mapping,
            phase_amounts=call.phase_amounts,
            liquid_composition=call.liquid_composition,
            parent_point_id=parent_point_id,
            step_id=step_id,
            solver_call_id=call.solver_call_id,
            reason_code="W2B_INSTRUMENT_PHYSICAL_WITNESS_INVALID",
        )
        return None


def _finish(
    recorder: _Recorder,
    provenance: TraceProvenance,
    spec: _RunSpec,
    *,
    outcome: str,
    reason_code: str | None,
    temperature_k: float | None,
    parent_point_id: str | None,
    step_id: str | None = None,
    solver_call_id: str | None = None,
    exception_card: tuple[str, str, str] | None = None,
) -> InstrumentedSolidificationTrace:
    if (
        recorder.finalization_guard is not None
        and (
            not recorder.events
            or recorder.events[-1].event_kind
            not in ("RUN_ERROR", "BUDGET_EXHAUSTED")
        )
    ):
        try:
            recorder.finalization_guard()
        except Exception as error:
            exception_card = _exception_card(error)
            recorder.emit(
                reserved=True,
                event_kind="RUN_ERROR",
                stage="FINALIZE",
                outcome="ERROR",
                temperature_k=temperature_k,
                pressure_pa=spec.pressure_pa,
                parent_point_id=parent_point_id,
                reason_code="W2B_INSTRUMENT_RUN_ERROR",
                exception_type=exception_card[0],
                exception_type_sha256=exception_card[1],
                exception_message_sha256=exception_card[2],
            )
            outcome = "ERROR"
            reason_code = "W2B_INSTRUMENT_RUN_ERROR"
            step_id = None
            solver_call_id = None
    exception_kwargs: dict[str, object] = {}
    if exception_card is not None:
        exception_kwargs = {
            "exception_type": exception_card[0],
            "exception_type_sha256": exception_card[1],
            "exception_message_sha256": exception_card[2],
        }
    terminal_event = recorder.prepare_event(
        reserved=True,
        event_kind="TERMINATION",
        stage="TERMINATION",
        outcome=outcome,
        temperature_k=temperature_k,
        pressure_pa=spec.pressure_pa,
        parent_point_id=parent_point_id,
        step_id=step_id,
        solver_call_id=solver_call_id,
        reason_code=reason_code,
        **exception_kwargs,
    )
    trace = InstrumentedSolidificationTrace(
        provenance=provenance,
        feature_id=spec.feature_id,
        events=tuple(recorder.events) + (terminal_event,),
        budget=recorder.budget,
        termination_outcome=outcome,
        termination_reason_code=reason_code,
        solver_call_count=recorder.solver_calls,
        cooling_step_count=recorder.cooling_steps,
        binary_probe_count=recorder.binary_probes,
    )
    # Commit is deliberately last: no TERMINATION is visible in the mutable
    # append-only recorder until the complete nested trace/state validation and
    # canonical digest construction have succeeded.
    recorder.events.append(terminal_event)
    return trace


def _budget_finish(
    recorder: _Recorder,
    provenance: TraceProvenance,
    spec: _RunSpec,
    error: _BudgetExceeded,
    temperature_k: float | None,
    parent_point_id: str | None,
) -> InstrumentedSolidificationTrace:
    recorder.emit(
        reserved=True,
        event_kind="BUDGET_EXHAUSTED",
        stage="TERMINATION",
        outcome="BUDGET_EXHAUSTED",
        temperature_k=temperature_k,
        pressure_pa=spec.pressure_pa,
        parent_point_id=parent_point_id,
        reason_code=error.reason_code,
        budget_limit=error.budget_limit,
        budget_used=error.budget_used,
        budget_required=error.budget_required,
    )
    return _finish(
        recorder,
        provenance,
        spec,
        outcome="BUDGET_EXHAUSTED",
        reason_code=error.reason_code,
        temperature_k=temperature_k,
        parent_point_id=parent_point_id,
    )


def _run_error_finish(
    recorder: _Recorder,
    provenance: TraceProvenance,
    spec: _RunSpec,
    *,
    stage: str,
    error: Exception,
    temperature_k: float | None,
    parent_point_id: str | None,
) -> InstrumentedSolidificationTrace:
    card = _exception_card(error)
    recorder.emit(
        reserved=True,
        event_kind="RUN_ERROR",
        stage=stage,
        outcome="ERROR",
        temperature_k=temperature_k,
        pressure_pa=spec.pressure_pa,
        parent_point_id=parent_point_id,
        reason_code="W2B_INSTRUMENT_RUN_ERROR",
        exception_type=card[0],
        exception_type_sha256=card[1],
        exception_message_sha256=card[2],
    )
    return _finish(
        recorder,
        provenance,
        spec,
        outcome="ERROR",
        reason_code="W2B_INSTRUMENT_RUN_ERROR",
        temperature_k=temperature_k,
        parent_point_id=parent_point_id,
        exception_card=card,
    )


def _last_run_context(
    recorder: _Recorder,
) -> tuple[float | None, str | None]:
    temperature: float | None = None
    parent: str | None = None
    for event in recorder.events:
        if event.temperature_k is not None:
            temperature = event.temperature_k
        if event.event_kind in (
            "SYNTHETIC_INITIAL_INSERTION",
            "ACCEPTED_PHYSICAL_POINT",
            "SERVICE_CLOSURE",
        ):
            parent = event.point_id
    return temperature, parent


def _run_equilibrium_port(
    spec: _RunSpec,
    solver: _AttemptSolver,
    provenance: TraceProvenance,
    recorder: _Recorder,
) -> InstrumentedSolidificationTrace:
    current_temperature = spec.start_temperature_k
    current_composition = spec.solver_composition
    parent_point_id: str | None = None
    point_count = 0
    try:
        while True:
            observation = _call_solver(
                recorder,
                solver,
                provenance,
                temperature_k=current_temperature,
                pressure_pa=spec.pressure_pa,
                composition=current_composition,
                stage="INITIAL" if parent_point_id is None else "COOLING",
                parent_point_id=parent_point_id,
                step_id=None,
            )
            if _liquid_present(observation, spec.liquid_phase):
                mapping_card = _runtime_physical_card_or_failure(
                    recorder,
                    provenance,
                    stage="INITIAL" if parent_point_id is None else "COOLING",
                    temperature_k=current_temperature,
                    pressure_pa=spec.pressure_pa,
                    step_temperature_k=None,
                    composition=current_composition,
                    parent_point_id=parent_point_id,
                )
                if mapping_card is None and parent_point_id is None:
                    return _finish(
                        recorder,
                        provenance,
                        spec,
                        outcome="ERROR",
                        reason_code="W2B_INSTRUMENT_PHYSICAL_WITNESS_INVALID",
                        temperature_k=current_temperature,
                        parent_point_id=None,
                    )
                point_count += 1
                if mapping_card is not None:
                    point_id = f"point-{point_count:06d}"
                    solid_amounts = _mapped_solid_amounts(mapping_card)
                    solid_fraction = mapping_card.raw_solid_fraction
                    liquid_fraction = (
                        mapping_card.derived_partition_liquid_fraction
                    )
                    fraction_card = _fraction_residual_card(
                        spec.feature_id,
                        solid_fraction,
                        liquid_fraction,
                    )
                    _emit_linked_physical_event(
                        recorder,
                        provenance,
                        event_kind="ACCEPTED_PHYSICAL_POINT",
                        stage="INITIAL" if parent_point_id is None else "COOLING",
                        outcome=(
                            "ACCEPTED"
                            if mapping_card.physical_balance_satisfied
                            else "ALGORITHM_ACCEPTED_WITH_RAW_NORMALIZATION_RESIDUAL"
                        ),
                        temperature_k=current_temperature,
                        pressure_pa=spec.pressure_pa,
                        composition=current_composition,
                        phases=observation.stable_phases,
                        raw_phase_fractions=observation.raw_phase_fractions,
                        raw_instance_mapping=observation.raw_instance_mapping,
                        phase_amounts=solid_amounts,
                        liquid_composition=observation.liquid_composition,
                        solid_fraction=solid_fraction,
                        liquid_fraction=liquid_fraction,
                        point_id=point_id,
                        parent_point_id=parent_point_id,
                        solver_call_id=recorder.last_solver_call_id,
                        fraction_residual_card=fraction_card,
                        phase_mapping_card=mapping_card,
                    )
                    parent_point_id = point_id
                else:
                    point_count -= 1
                next_temperature = current_temperature - spec.step_temperature_k
                if next_temperature < spec.minimum_temperature_k:
                    return _finish(
                        recorder,
                        provenance,
                        spec,
                        outcome="BOUND_REACHED",
                        reason_code="W2B_INSTRUMENT_TEMPERATURE_BOUND",
                        temperature_k=current_temperature,
                        parent_point_id=parent_point_id,
                    )
                step_id = recorder.consume_cooling()
                recorder.emit(
                    event_kind="COOLING_STEP",
                    stage="COOLING",
                    outcome="DECREASED",
                    temperature_k=next_temperature,
                    pressure_pa=spec.pressure_pa,
                    step_temperature_k=spec.step_temperature_k,
                    composition=current_composition,
                    parent_point_id=parent_point_id,
                    step_id=step_id,
                )
                current_temperature = next_temperature
                continue

            recorder.emit(
                event_kind="NO_LIQUID_FAILURE",
                stage="COOLING" if parent_point_id is not None else "INITIAL",
                outcome="NO_PHASES" if not observation.stable_phases else "NO_LIQUID",
                temperature_k=current_temperature,
                pressure_pa=spec.pressure_pa,
                composition=current_composition,
                phases=observation.stable_phases,
                raw_phase_fractions=observation.raw_phase_fractions,
                phase_amounts=observation.phase_amounts,
                parent_point_id=parent_point_id,
                solver_call_id=recorder.last_solver_call_id,
            )
            if parent_point_id is None:
                # Upstream defines start_temperature as the liquid-side bound.
                # Its fallback high=start+step would leave the receipt domain
                # when the very first point has no liquid, so fail closed.
                return _finish(
                    recorder,
                    provenance,
                    spec,
                    outcome="ERROR",
                    reason_code="W2B_INSTRUMENT_INITIAL_LIQUID_REQUIRED",
                    temperature_k=current_temperature,
                    parent_point_id=None,
                )
            low = current_temperature
            high = current_temperature + spec.step_temperature_k
            recorder.emit(
                event_kind="BINARY_SEARCH_BEGIN",
                stage="BINARY_SEARCH",
                outcome="STARTED",
                temperature_k=current_temperature,
                pressure_pa=spec.pressure_pa,
                bracket_low_k=low,
                bracket_high_k=high,
                composition=current_composition,
                parent_point_id=parent_point_id,
            )
            assert spec.binary_search_tolerance_k is not None
            while (high - low) > spec.binary_search_tolerance_k:
                probe_id, probe_call_id = recorder.allocate_binary_probe_unit()
                probe_temperature = (high - low) * 0.5 + low
                recorder.emit(
                    event_kind="BINARY_SEARCH_PROBE",
                    stage="BINARY_SEARCH",
                    outcome="PROBED",
                    temperature_k=probe_temperature,
                    pressure_pa=spec.pressure_pa,
                    bracket_low_k=low,
                    bracket_high_k=high,
                    composition=current_composition,
                    parent_point_id=parent_point_id,
                    step_id=probe_id,
                )
                try:
                    probe = _call_solver(
                        recorder,
                        solver,
                        provenance,
                        temperature_k=probe_temperature,
                        pressure_pa=spec.pressure_pa,
                        composition=current_composition,
                        stage="BINARY_SEARCH",
                        parent_point_id=parent_point_id,
                        step_id=probe_id,
                        allocated_call_id=probe_call_id,
                    )
                except _SolverRaised as error:
                    recorder.emit(
                        event_kind="BINARY_SEARCH_DIRECTION",
                        stage="BINARY_SEARCH",
                        outcome="ERROR",
                        temperature_k=probe_temperature,
                        pressure_pa=spec.pressure_pa,
                        bracket_low_k=low,
                        bracket_high_k=high,
                        composition=current_composition,
                        parent_point_id=parent_point_id,
                        step_id=probe_id,
                        solver_call_id=error.solver_call_id,
                        reason_code="W2B_INSTRUMENT_SOLVER_ERROR",
                    )
                    raise
                if _liquid_present(probe, spec.liquid_phase):
                    high = probe_temperature
                    direction = "UPDATE_HIGH"
                else:
                    recorder.emit(
                        event_kind="NO_LIQUID_FAILURE",
                        stage="BINARY_SEARCH",
                        outcome="NO_PHASES" if not probe.stable_phases else "NO_LIQUID",
                        temperature_k=probe_temperature,
                        pressure_pa=spec.pressure_pa,
                        composition=current_composition,
                        phases=probe.stable_phases,
                        raw_phase_fractions=probe.raw_phase_fractions,
                        phase_amounts=probe.phase_amounts,
                        parent_point_id=parent_point_id,
                        step_id=probe_id,
                        solver_call_id=recorder.last_solver_call_id,
                    )
                    low = probe_temperature
                    direction = "UPDATE_LOW"
                recorder.emit(
                    event_kind="BINARY_SEARCH_DIRECTION",
                    stage="BINARY_SEARCH",
                    outcome=direction,
                    temperature_k=probe_temperature,
                    pressure_pa=spec.pressure_pa,
                    bracket_low_k=low,
                    bracket_high_k=high,
                    composition=current_composition,
                    phases=probe.stable_phases,
                    raw_phase_fractions=probe.raw_phase_fractions,
                    phase_amounts=probe.phase_amounts,
                    liquid_composition=probe.liquid_composition,
                    parent_point_id=parent_point_id,
                    step_id=probe_id,
                    solver_call_id=recorder.last_solver_call_id,
                )
            final_observation = _call_solver(
                recorder,
                solver,
                provenance,
                temperature_k=low,
                pressure_pa=spec.pressure_pa,
                composition=current_composition,
                stage="BINARY_SEARCH",
                parent_point_id=parent_point_id,
                step_id=None,
            )
            if not _liquid_present(final_observation, spec.liquid_phase):
                recorder.emit(
                    event_kind="NO_LIQUID_FAILURE",
                    stage="BINARY_SEARCH",
                    outcome="NO_PHASES" if not final_observation.stable_phases else "NO_LIQUID",
                    temperature_k=low,
                    pressure_pa=spec.pressure_pa,
                    composition=current_composition,
                    phases=final_observation.stable_phases,
                    raw_phase_fractions=final_observation.raw_phase_fractions,
                    phase_amounts=final_observation.phase_amounts,
                    parent_point_id=parent_point_id,
                    solver_call_id=recorder.last_solver_call_id,
                )
            mapping_card = _runtime_physical_card_or_failure(
                recorder,
                provenance,
                stage="BINARY_SEARCH",
                temperature_k=low,
                pressure_pa=spec.pressure_pa,
                step_temperature_k=None,
                composition=current_composition,
                parent_point_id=parent_point_id,
            )
            if mapping_card is None:
                return _finish(
                    recorder,
                    provenance,
                    spec,
                    outcome="ERROR",
                    reason_code="W2B_INSTRUMENT_PHYSICAL_WITNESS_INVALID",
                    temperature_k=low,
                    parent_point_id=parent_point_id,
                )
            point_count += 1
            point_id = f"point-{point_count:06d}"
            solid_amounts = _mapped_solid_amounts(mapping_card)
            solid_fraction = mapping_card.raw_solid_fraction
            liquid_fraction = mapping_card.derived_partition_liquid_fraction
            fraction_card = _fraction_residual_card(
                spec.feature_id,
                solid_fraction,
                liquid_fraction,
            )
            _emit_linked_physical_event(
                recorder,
                provenance,
                event_kind="ACCEPTED_PHYSICAL_POINT",
                stage="BINARY_SEARCH",
                outcome=(
                    "ACCEPTED"
                    if mapping_card.physical_balance_satisfied
                    else "ALGORITHM_ACCEPTED_WITH_RAW_NORMALIZATION_RESIDUAL"
                ),
                temperature_k=low,
                pressure_pa=spec.pressure_pa,
                composition=current_composition,
                phases=final_observation.stable_phases,
                raw_phase_fractions=final_observation.raw_phase_fractions,
                raw_instance_mapping=final_observation.raw_instance_mapping,
                phase_amounts=solid_amounts,
                liquid_composition=final_observation.liquid_composition,
                solid_fraction=solid_fraction,
                liquid_fraction=liquid_fraction,
                point_id=point_id,
                parent_point_id=parent_point_id,
                solver_call_id=recorder.last_solver_call_id,
                fraction_residual_card=fraction_card,
                phase_mapping_card=mapping_card,
            )
            recorder.emit(
                event_kind="BINARY_SEARCH_END",
                stage="BINARY_SEARCH",
                outcome="FINISHED",
                temperature_k=low,
                pressure_pa=spec.pressure_pa,
                bracket_low_k=low,
                bracket_high_k=high,
                composition=current_composition,
                parent_point_id=point_id,
            )
            converged = (
                _fraction_card_is_complete(fraction_card)
                and mapping_card.physical_balance_satisfied
            )
            return _finish(
                recorder,
                provenance,
                spec,
                outcome="CONVERGED" if converged else "NOT_CONVERGED",
                reason_code=None,
                temperature_k=low,
                parent_point_id=point_id,
            )
    except _BudgetExceeded as error:
        return _budget_finish(recorder, provenance, spec, error, current_temperature, parent_point_id)
    except _SolverRaised as error:
        return _finish(
            recorder,
            provenance,
            spec,
            outcome="ERROR",
            reason_code="W2B_INSTRUMENT_SOLVER_ERROR",
            temperature_k=error.temperature_k,
            parent_point_id=error.parent_point_id,
            step_id=error.step_id,
            solver_call_id=error.solver_call_id,
            exception_card=(
                error.exception_type,
                error.exception_type_sha256,
                error.exception_message_sha256,
            ),
        )


def _run_scheil_port(
    spec: _RunSpec,
    solver: _AttemptSolver,
    provenance: TraceProvenance,
    recorder: _Recorder,
) -> InstrumentedSolidificationTrace:
    temperature = spec.start_temperature_k
    step_temperature = spec.step_temperature_k
    original_step = spec.step_temperature_k
    current_composition = spec.solver_composition
    current_solid = 0.0
    point_count = 0
    parent_point_id = "point-000000"
    last_converged: _SolverObservation | None = None
    last_converged_card: PhaseMappingCard | None = None
    last_converged_call_id: str | None = None
    stop_criterion_reached = False
    physical_complete = False
    termination_reason: str | None = None
    synthetic_raw = ((spec.liquid_phase, 1.0),)
    synthetic_mapping = ((spec.liquid_phase, spec.liquid_phase),)
    synthetic_mapping_card = _phase_mapping_card_from_bound(
        provenance,
        synthetic_raw,
        synthetic_mapping,
    )
    recorder.emit(
        event_kind="SYNTHETIC_INITIAL_INSERTION",
        stage="INITIAL",
        outcome="INSERTED",
        temperature_k=temperature,
        pressure_pa=spec.pressure_pa,
        step_temperature_k=step_temperature,
        composition=spec.bulk_composition,
        phases=(spec.liquid_phase,),
        raw_phase_fractions=synthetic_raw,
        raw_instance_mapping=synthetic_mapping,
        phase_amounts=(),
        liquid_composition=spec.solver_composition,
        solid_fraction=0.0,
        liquid_fraction=1.0,
        point_id=parent_point_id,
        synthetic=True,
        fraction_residual_card=_fraction_residual_card(
            spec.feature_id,
            0.0,
            1.0,
        ),
        phase_mapping_card=synthetic_mapping_card,
    )
    try:
        while current_solid < 1.0:
            attempt_composition = current_composition
            observation = _call_solver(
                recorder,
                solver,
                provenance,
                temperature_k=temperature,
                pressure_pa=spec.pressure_pa,
                composition=attempt_composition,
                stage="COOLING",
                parent_point_id=parent_point_id,
                step_id=None,
            )
            if not _liquid_present(observation, spec.liquid_phase):
                recorder.emit(
                    event_kind="NO_LIQUID_FAILURE",
                    stage="COOLING",
                    outcome="NO_PHASES" if not observation.stable_phases else "NO_LIQUID",
                    temperature_k=temperature,
                    pressure_pa=spec.pressure_pa,
                    step_temperature_k=step_temperature,
                    composition=attempt_composition,
                    phases=observation.stable_phases,
                    raw_phase_fractions=observation.raw_phase_fractions,
                    phase_amounts=observation.phase_amounts,
                    parent_point_id=parent_point_id,
                    solver_call_id=recorder.last_solver_call_id,
                )
                if point_count == 0:
                    return _finish(
                        recorder,
                        provenance,
                        spec,
                        outcome="ERROR",
                        reason_code="W2B_INSTRUMENT_INITIAL_LIQUID_REQUIRED",
                        temperature_k=temperature,
                        parent_point_id=parent_point_id,
                    )
                if original_step / step_temperature > _MAXIMUM_STEP_SIZE_REDUCTION:
                    recorder.emit(
                        event_kind="STEP_REDUCTION_LIMIT",
                        stage="COOLING",
                        outcome="LIMIT_REACHED",
                        temperature_k=temperature,
                        pressure_pa=spec.pressure_pa,
                        step_temperature_k=step_temperature,
                        composition=current_composition,
                        parent_point_id=parent_point_id,
                        reason_code="W2B_INSTRUMENT_STEP_REDUCTION_LIMIT",
                    )
                    termination_reason = "W2B_INSTRUMENT_STEP_REDUCTION_LIMIT"
                    break
                backtrack_temperature = temperature + step_temperature
                recorder.emit(
                    event_kind="BACKTRACK",
                    stage="COOLING",
                    outcome="BACKTRACKED",
                    temperature_k=backtrack_temperature,
                    pressure_pa=spec.pressure_pa,
                    step_temperature_k=step_temperature,
                    composition=current_composition,
                    parent_point_id=parent_point_id,
                )
                reduced_step = step_temperature / _STEP_SCALE_FACTOR
                temperature = backtrack_temperature - reduced_step
                step_temperature = reduced_step
                recorder.emit(
                    event_kind="STEP_REDUCTION",
                    stage="COOLING",
                    outcome="REDUCED",
                    temperature_k=temperature,
                    pressure_pa=spec.pressure_pa,
                    step_temperature_k=step_temperature,
                    composition=current_composition,
                    parent_point_id=parent_point_id,
                )
                continue

            mapping_card = _runtime_physical_card_or_failure(
                recorder,
                provenance,
                stage="COOLING",
                temperature_k=temperature,
                pressure_pa=spec.pressure_pa,
                step_temperature_k=step_temperature,
                composition=attempt_composition,
                parent_point_id=parent_point_id,
            )
            if mapping_card is None:
                if point_count == 0:
                    return _finish(
                        recorder,
                        provenance,
                        spec,
                        outcome="ERROR",
                        reason_code="W2B_INSTRUMENT_PHYSICAL_WITNESS_INVALID",
                        temperature_k=temperature,
                        parent_point_id=parent_point_id,
                    )
                if original_step / step_temperature > _MAXIMUM_STEP_SIZE_REDUCTION:
                    recorder.emit(
                        event_kind="STEP_REDUCTION_LIMIT",
                        stage="COOLING",
                        outcome="LIMIT_REACHED",
                        temperature_k=temperature,
                        pressure_pa=spec.pressure_pa,
                        step_temperature_k=step_temperature,
                        composition=current_composition,
                        parent_point_id=parent_point_id,
                        reason_code="W2B_INSTRUMENT_STEP_REDUCTION_LIMIT",
                    )
                    termination_reason = "W2B_INSTRUMENT_STEP_REDUCTION_LIMIT"
                    break
                backtrack_temperature = temperature + step_temperature
                recorder.emit(
                    event_kind="BACKTRACK",
                    stage="COOLING",
                    outcome="BACKTRACKED",
                    temperature_k=backtrack_temperature,
                    pressure_pa=spec.pressure_pa,
                    step_temperature_k=step_temperature,
                    composition=current_composition,
                    parent_point_id=parent_point_id,
                )
                reduced_step = step_temperature / _STEP_SCALE_FACTOR
                temperature = backtrack_temperature - reduced_step
                step_temperature = reduced_step
                recorder.emit(
                    event_kind="STEP_REDUCTION",
                    stage="COOLING",
                    outcome="REDUCED",
                    temperature_k=temperature,
                    pressure_pa=spec.pressure_pa,
                    step_temperature_k=step_temperature,
                    composition=current_composition,
                    parent_point_id=parent_point_id,
                )
                continue

            if observation.gm_converged:
                last_converged = observation
                last_converged_card = mapping_card
                last_converged_call_id = recorder.last_solver_call_id
            if observation.liquid_composition:
                current_composition = observation.liquid_composition
            increments, current_solid = _scheil_mapped_increments(
                mapping_card,
                current_solid,
            )
            liquid_fraction = 1.0 - current_solid
            fraction_card = _fraction_residual_card(
                spec.feature_id,
                current_solid,
                liquid_fraction,
            )
            point_count += 1
            point_id = f"point-{point_count:06d}"
            _emit_linked_physical_event(
                recorder,
                provenance,
                event_kind="ACCEPTED_PHYSICAL_POINT",
                stage="COOLING",
                outcome=(
                    "ACCEPTED"
                    if mapping_card.physical_balance_satisfied
                    else "ALGORITHM_ACCEPTED_WITH_RAW_NORMALIZATION_RESIDUAL"
                ),
                temperature_k=temperature,
                pressure_pa=spec.pressure_pa,
                step_temperature_k=step_temperature,
                composition=attempt_composition,
                phases=observation.stable_phases,
                raw_phase_fractions=observation.raw_phase_fractions,
                raw_instance_mapping=observation.raw_instance_mapping,
                phase_amounts=increments,
                liquid_composition=observation.liquid_composition,
                solid_fraction=current_solid,
                liquid_fraction=liquid_fraction,
                point_id=point_id,
                parent_point_id=parent_point_id,
                solver_call_id=recorder.last_solver_call_id,
                fraction_residual_card=fraction_card,
                phase_mapping_card=mapping_card,
            )
            parent_point_id = point_id
            assert spec.stop_liquid_fraction is not None
            if _fraction_card_is_complete(fraction_card):
                stop_criterion_reached = True
                termination_reason = (
                    "W2B_INSTRUMENT_STOP_CRITERION_REACHED_PARTIAL"
                )
                break
            if liquid_fraction < spec.stop_liquid_fraction:
                stop_criterion_reached = True
                termination_reason = (
                    "W2B_INSTRUMENT_STOP_CRITERION_REACHED_PARTIAL"
                )
                break
            next_temperature = temperature - step_temperature
            if next_temperature < spec.minimum_temperature_k:
                termination_reason = "W2B_INSTRUMENT_TEMPERATURE_BOUND"
                break
            step_id = recorder.consume_cooling()
            recorder.emit(
                event_kind="COOLING_STEP",
                stage="COOLING",
                outcome="DECREASED",
                temperature_k=next_temperature,
                pressure_pa=spec.pressure_pa,
                step_temperature_k=step_temperature,
                composition=current_composition,
                parent_point_id=parent_point_id,
                step_id=step_id,
            )
            temperature = next_temperature

        if not physical_complete:
            if (
                last_converged is None
                or last_converged_card is None
                or last_converged_call_id is None
            ):
                recorder.emit(
                    event_kind="NO_CALCULATION_FAILURE",
                    stage="COOLING",
                    outcome="ERROR",
                    temperature_k=temperature,
                    pressure_pa=spec.pressure_pa,
                    step_temperature_k=step_temperature,
                    composition=current_composition,
                    parent_point_id=parent_point_id,
                    reason_code="W2B_INSTRUMENT_NO_CALCULATION",
                )
                return _finish(
                    recorder,
                    provenance,
                    spec,
                    outcome="ERROR",
                    reason_code="W2B_INSTRUMENT_NO_CALCULATION",
                    temperature_k=temperature,
                    parent_point_id=parent_point_id,
                )
            remaining = 1.0 - current_solid
            closure_amounts = _mapped_service_closure(
                last_converged_card,
                remaining,
            )
            closure_gap = remaining - _sequential_sum(closure_amounts)
            closure_accepted_point_count = point_count
            closure_cap = _closure_evidence_excursion_cap(
                closure_accepted_point_count
            )
            point_count += 1
            closure_id = f"point-{point_count:06d}"
            _emit_linked_physical_event(
                recorder,
                provenance,
                event_kind="SERVICE_CLOSURE",
                stage="SERVICE_CLOSURE",
                outcome="CLOSED",
                temperature_k=temperature,
                pressure_pa=spec.pressure_pa,
                step_temperature_k=step_temperature,
                composition=current_composition,
                phases=last_converged.stable_phases,
                raw_phase_fractions=last_converged.raw_phase_fractions,
                raw_instance_mapping=last_converged.raw_instance_mapping,
                phase_amounts=closure_amounts,
                liquid_composition=last_converged.liquid_composition,
                solid_fraction=current_solid,
                liquid_fraction=remaining,
                point_id=closure_id,
                parent_point_id=parent_point_id,
                solver_call_id=last_converged_call_id,
                synthetic=True,
                service=True,
                reason_code=termination_reason,
                closure_residual_fraction=remaining,
                closure_unfilled_gap=closure_gap,
                closure_evidence_policy_id=_fixed_value(
                    "scheil_closure_evidence_policy_id"
                ),
                closure_accepted_point_count=closure_accepted_point_count,
                closure_excursion_abs_cap=closure_cap,
                closure_residual_classification=(
                    _closure_evidence_classification(
                        remaining,
                        closure_cap,
                    )
                ),
                closure_gap_classification=(
                    _closure_evidence_classification(
                        closure_gap,
                        closure_cap,
                    )
                ),
                fraction_residual_card=_fraction_residual_card(
                    spec.feature_id,
                    current_solid,
                    remaining,
                ),
                phase_mapping_card=last_converged_card,
            )
            parent_point_id = closure_id
        outcome = (
            "STOP_CRITERION_REACHED_PARTIAL"
            if stop_criterion_reached
            else (
                "BOUND_REACHED"
                if termination_reason == "W2B_INSTRUMENT_TEMPERATURE_BOUND"
                else "NOT_CONVERGED"
            )
        )
        return _finish(
            recorder,
            provenance,
            spec,
            outcome=outcome,
            reason_code=termination_reason,
            temperature_k=temperature,
            parent_point_id=parent_point_id,
        )
    except _BudgetExceeded as error:
        return _budget_finish(recorder, provenance, spec, error, temperature, parent_point_id)
    except _SolverRaised as error:
        return _finish(
            recorder,
            provenance,
            spec,
            outcome="ERROR",
            reason_code="W2B_INSTRUMENT_SOLVER_ERROR",
            temperature_k=error.temperature_k,
            parent_point_id=error.parent_point_id,
            step_id=error.step_id,
            solver_call_id=error.solver_call_id,
            exception_card=(
                error.exception_type,
                error.exception_type_sha256,
                error.exception_message_sha256,
            ),
        )


def _start_recorder(spec: _RunSpec, budget: InstrumentationBudget) -> _Recorder:
    recorder = _Recorder(budget)
    recorder.emit(
        event_kind="RUN_START",
        stage="RUN",
        outcome="BEGIN",
        temperature_k=spec.start_temperature_k,
        pressure_pa=spec.pressure_pa,
        step_temperature_k=spec.step_temperature_k,
        composition=spec.bulk_composition,
        phases=spec.phases,
    )
    return recorder


def _dispatch_port(
    spec: _RunSpec,
    solver: _AttemptSolver,
    provenance: TraceProvenance,
    recorder: _Recorder,
) -> InstrumentedSolidificationTrace:
    effective, independent, liquid, bulk = _bound_phase_contract(provenance)
    if (
        provenance.adaptive is not spec.adaptive
        or provenance.pdens != spec.pdens
        or not _same_optional_f64(
            provenance.binary_search_tolerance_k,
            spec.binary_search_tolerance_k,
        )
        or not _same_optional_f64(
            provenance.stop_liquid_fraction,
            spec.stop_liquid_fraction,
        )
        or spec.phases != effective
        or spec.liquid_phase != liquid
        or not _same_numeric_pairs(spec.bulk_composition, bulk)
        or tuple(name for name, _value in spec.solver_composition)
        != independent
    ):
        _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
    if spec.feature_id == "equilibrium_solidification":
        return _run_equilibrium_port(spec, solver, provenance, recorder)
    return _run_scheil_port(spec, solver, provenance, recorder)


def _run_port(
    spec: _RunSpec,
    solver: _AttemptSolver,
    provenance: TraceProvenance,
    budget: InstrumentationBudget,
) -> InstrumentedSolidificationTrace:
    return _dispatch_port(
        spec,
        solver,
        provenance,
        _start_recorder(spec, budget),
    )


@_dataclass(frozen=True, slots=True)
class _RuntimeModules:
    Database: object
    Workspace: object
    N: object
    P: object
    T: object
    X: object
    filter_phases: object
    unpack_species: object
    instantiate_models: object
    PhaseRecordFactory: object
    create_ordering_records: object
    wks_ordering_rename_map: object
    is_converged: object
    get_stable_phases_with_multiplicities: object
    numpy: object
    numpy_isnan: object
    numpy_get_state: object
    pycalphad_module: object
    database_module: object
    workspace_module: object
    variables_module: object
    core_utils_module: object
    phase_record_factory_module: object
    scheil_module: object
    simulate_module: object
    ordering_module: object
    workspace_init: object
    workspace_get: object
    workspace_detect_phase_multiplicity: object
    workspace_conditions_descriptor: object
    workspace_calc_opts_descriptor: object
    callable_code_bindings: tuple[tuple[object, object], ...]
    direct_source_paths: tuple[tuple[str, _Path, str], ...]
    source_sha256: str
    ordering_sha256: str
    utils_sha256: str
    license_sha256: str
    instrumentation_source_sha256: str
    instrumentation_normalized_source_sha256: str
    scheil_payload_manifest_sha256: str
    pycalphad_payload_manifest_sha256: str


def _require_function_origin(
    function: object,
    *,
    module_name: str,
    qualified_name: str,
    source_path: _Path,
) -> None:
    code = getattr(function, "__code__", None)
    if (
        getattr(function, "__module__", None) != module_name
        or getattr(function, "__qualname__", None) != qualified_name
        or code is None
        or _Path(code.co_filename).resolve(strict=True) != source_path
    ):
        _fail("W2B_INSTRUMENT_SOURCE_DRIFT")


def _verify_runtime_at_use(modules: _RuntimeModules) -> None:
    _require_fixed_authority()
    """Recheck stored primitive identity and direct source immediately at use."""

    try:
        if (
            getattr(modules.pycalphad_module, "Database") is not modules.Database
            or getattr(modules.database_module, "Database") is not modules.Database
            or getattr(modules.pycalphad_module, "Workspace") is not modules.Workspace
            or getattr(modules.workspace_module, "Workspace") is not modules.Workspace
            or getattr(modules.variables_module, "N") is not modules.N
            or getattr(modules.variables_module, "P") is not modules.P
            or getattr(modules.variables_module, "T") is not modules.T
            or getattr(modules.variables_module, "X") is not modules.X
            or getattr(modules.simulate_module, "filter_phases") is not modules.filter_phases
            or getattr(modules.core_utils_module, "filter_phases") is not modules.filter_phases
            or getattr(modules.simulate_module, "unpack_species") is not modules.unpack_species
            or getattr(modules.core_utils_module, "unpack_species") is not modules.unpack_species
            or getattr(modules.simulate_module, "instantiate_models")
            is not modules.instantiate_models
            or getattr(modules.core_utils_module, "instantiate_models")
            is not modules.instantiate_models
            or getattr(modules.simulate_module, "PhaseRecordFactory")
            is not modules.PhaseRecordFactory
            or getattr(modules.phase_record_factory_module, "PhaseRecordFactory")
            is not modules.PhaseRecordFactory
            or getattr(modules.simulate_module, "create_ordering_records")
            is not modules.create_ordering_records
            or getattr(modules.ordering_module, "create_ordering_records")
            is not modules.create_ordering_records
            or getattr(modules.simulate_module, "_wks_ordering_rename_map")
            is not modules.wks_ordering_rename_map
            or getattr(modules.ordering_module, "_wks_ordering_rename_map")
            is not modules.wks_ordering_rename_map
            or getattr(modules.simulate_module, "is_converged") is not modules.is_converged
            or getattr(modules.simulate_module, "_get_stable_phases_with_multiplicities")
            is not modules.get_stable_phases_with_multiplicities
            or getattr(modules.Workspace, "__init__") is not modules.workspace_init
            or getattr(modules.Workspace, "get") is not modules.workspace_get
            or getattr(modules.Workspace, "_detect_phase_multiplicity")
            is not modules.workspace_detect_phase_multiplicity
            or vars(modules.Workspace).get("conditions")
            is not modules.workspace_conditions_descriptor
            or vars(modules.Workspace).get("calc_opts")
            is not modules.workspace_calc_opts_descriptor
            or getattr(modules.numpy, "isnan") is not modules.numpy_isnan
            or getattr(getattr(modules.numpy, "random"), "get_state")
            is not modules.numpy_get_state
        ):
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        if any(
            getattr(function, "__code__", None) is not code
            for function, code in modules.callable_code_bindings
        ):
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        direct_by_relative = {
            relative: path
            for relative, path, _expected_digest in modules.direct_source_paths
        }
        if (
            _Path(modules.pycalphad_module.__file__).resolve(strict=True)
            != direct_by_relative["pycalphad/__init__.py"]
            or _Path(modules.database_module.__file__).resolve(strict=True)
            != direct_by_relative["pycalphad/io/database.py"]
            or _Path(modules.workspace_module.__file__).resolve(strict=True)
            != direct_by_relative["pycalphad/core/workspace.py"]
            or _Path(modules.variables_module.__file__).resolve(strict=True)
            != direct_by_relative["pycalphad/variables.py"]
            or _Path(modules.core_utils_module.__file__).resolve(strict=True)
            != direct_by_relative["pycalphad/core/utils.py"]
            or _Path(modules.phase_record_factory_module.__file__).resolve(strict=True)
            != direct_by_relative[
                "pycalphad/codegen/phase_record_factory.py"
            ]
            or _Path(modules.simulate_module.__file__).resolve(strict=True)
            != direct_by_relative[UPSTREAM_SOURCE_RELATIVE_PATH]
            or _Path(modules.ordering_module.__file__).resolve(strict=True)
            != direct_by_relative[UPSTREAM_ORDERING_RELATIVE_PATH]
        ):
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        for _relative, path, expected_digest in modules.direct_source_paths:
            digest, _size = _hash_regular_file(
                path,
                maximum=_MAX_RUNTIME_FILE_BYTES,
                reason="W2B_INSTRUMENT_SOURCE_DRIFT",
            )
            if digest != expected_digest:
                _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        raw_digest, normalized_digest = _verify_instrumentation_source_pin(
            modules.instrumentation_source_sha256
        )
        if (
            raw_digest != modules.instrumentation_source_sha256
            or normalized_digest != modules.instrumentation_normalized_source_sha256
        ):
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
    except SolidificationInstrumentationError:
        raise
    except Exception as error:
        raise SolidificationInstrumentationError("W2B_INSTRUMENT_SOURCE_DRIFT") from error


def _ambient_numpy_rng_digest(modules: _RuntimeModules) -> str:
    try:
        _verify_runtime_at_use(modules)
        state = modules.numpy_get_state()
        if type(state) is not tuple or len(state) != 5 or type(state[0]) is not str:
            _fail("W2B_INSTRUMENT_AMBIENT_RNG_MUTATION")
        keys = state[1]
        key_bytes = keys.tobytes(order="C")
        position = state[2]
        has_gauss = state[3]
        cached_gaussian = _f64(state[4])
        if (
            type(position) is not int
            or isinstance(position, bool)
            or type(has_gauss) is not int
            or isinstance(has_gauss, bool)
        ):
            _fail("W2B_INSTRUMENT_AMBIENT_RNG_MUTATION")
        payload = (
            state[0].encode("ascii")
            + b"\0"
            + str(getattr(keys, "dtype", "")).encode("ascii")
            + b"\0"
            + key_bytes
            + _struct.pack(">qqd", position, has_gauss, cached_gaussian)
        )
        return _hashlib.sha256(payload).hexdigest()
    except SolidificationInstrumentationError:
        raise
    except Exception as error:
        raise SolidificationInstrumentationError(
            "W2B_INSTRUMENT_AMBIENT_RNG_MUTATION"
        ) from error


def _verify_exact_runtime(
    expected_instrumentation_source_sha256: str | None = None,
) -> _RuntimeModules:
    _require_fixed_authority()
    """Import lazily and pin exact upstream version, source file, and license."""

    try:
        pycalphad = _importlib.import_module("pycalphad")
        database_module = _importlib.import_module("pycalphad.io.database")
        workspace_module = _importlib.import_module("pycalphad.core.workspace")
        variables_module = _importlib.import_module("pycalphad.variables")
        core_utils_module = _importlib.import_module("pycalphad.core.utils")
        phase_record_factory_module = _importlib.import_module(
            "pycalphad.codegen.phase_record_factory"
        )
        scheil = _importlib.import_module("scheil")
        simulate = _importlib.import_module("scheil.simulate")
        ordering_module = _importlib.import_module("scheil.ordering")
        numpy = _importlib.import_module("numpy")
        scheil_distribution = _metadata.distribution(UPSTREAM_PACKAGE)
        pycalphad_distribution = _metadata.distribution("pycalphad")
        if (
            getattr(pycalphad, "__version__", None) != PYCALPHAD_VERSION
            or getattr(scheil, "__version__", None) != UPSTREAM_VERSION
            or getattr(numpy, "__version__", None) != NUMPY_VERSION
            or scheil_distribution.version != UPSTREAM_VERSION
            or pycalphad_distribution.version != PYCALPHAD_VERSION
        ):
            _fail("W2B_INSTRUMENT_RUNTIME_VERSION")
        source_path = _Path(getattr(simulate, "__file__")).resolve(strict=True)
        expected_source = _Path(
            scheil_distribution.locate_file(UPSTREAM_SOURCE_RELATIVE_PATH)
        ).resolve(strict=True)
        if source_path != expected_source:
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        source_digest, _source_size = _hash_regular_file(
            source_path,
            maximum=_MAX_FILE_BYTES,
            reason="W2B_INSTRUMENT_SOURCE_DRIFT",
        )
        if source_digest != UPSTREAM_SOURCE_SHA256:
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        ordering_path = _Path(
            scheil_distribution.locate_file(UPSTREAM_ORDERING_RELATIVE_PATH)
        ).resolve(strict=True)
        ordering_digest, _ordering_size = _hash_regular_file(
            ordering_path,
            maximum=_MAX_FILE_BYTES,
            reason="W2B_INSTRUMENT_SOURCE_DRIFT",
        )
        if ordering_digest != UPSTREAM_ORDERING_SHA256:
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        utils_path = _Path(
            scheil_distribution.locate_file(UPSTREAM_UTILS_RELATIVE_PATH)
        ).resolve(strict=True)
        utils_digest, _utils_size = _hash_regular_file(
            utils_path,
            maximum=_MAX_FILE_BYTES,
            reason="W2B_INSTRUMENT_SOURCE_DRIFT",
        )
        if utils_digest != UPSTREAM_UTILS_SHA256:
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        license_path = _Path(
            scheil_distribution.locate_file(UPSTREAM_LICENSE_RELATIVE_PATH)
        ).resolve(strict=True)
        license_digest, _license_size = _hash_regular_file(
            license_path,
            maximum=_MAX_FILE_BYTES,
            reason="W2B_INSTRUMENT_LICENSE_DRIFT",
        )
        if license_digest != UPSTREAM_LICENSE_SHA256:
            _fail("W2B_INSTRUMENT_LICENSE_DRIFT")
        for function_name in (
            "simulate_scheil_solidification",
            "simulate_equilibrium_solidification",
            "is_converged",
            "_update_points",
            "_get_stable_phases_with_multiplicities",
        ):
            function = getattr(simulate, function_name)
            code_path = _Path(function.__code__.co_filename).resolve(strict=True)
            if function.__module__ != "scheil.simulate" or code_path != source_path:
                _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        for function_name in ("create_ordering_records", "_wks_ordering_rename_map"):
            function = getattr(simulate, function_name)
            code_path = _Path(function.__code__.co_filename).resolve(strict=True)
            if function.__module__ != "scheil.ordering" or code_path != ordering_path:
                _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        local_sample = getattr(simulate, "local_sample")
        if (
            local_sample.__module__ != "scheil.utils"
            or _Path(local_sample.__code__.co_filename).resolve(strict=True) != utils_path
        ):
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        scheil_manifest, scheil_count, scheil_bytes = _distribution_payload_manifest(
            scheil_distribution,
            prefixes=("scheil/", "scheil-0.3.0.dist-info/"),
            reason="W2B_INSTRUMENT_SOURCE_DRIFT",
        )
        pycalphad_manifest, pycalphad_count, pycalphad_bytes = (
            _distribution_payload_manifest(
                pycalphad_distribution,
                prefixes=("pycalphad/",),
                reason="W2B_INSTRUMENT_SOURCE_DRIFT",
            )
        )
        if (
            (scheil_manifest, scheil_count, scheil_bytes)
            != (
                SCHEIL_PAYLOAD_MANIFEST_SHA256,
                SCHEIL_PAYLOAD_FILE_COUNT,
                SCHEIL_PAYLOAD_TOTAL_BYTES,
            )
            or (pycalphad_manifest, pycalphad_count, pycalphad_bytes)
            != (
                PYCALPHAD_PAYLOAD_MANIFEST_SHA256,
                PYCALPHAD_PAYLOAD_FILE_COUNT,
                PYCALPHAD_PAYLOAD_TOTAL_BYTES,
            )
        ):
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        direct_paths: list[tuple[str, _Path, str]] = [
            (UPSTREAM_SOURCE_RELATIVE_PATH, source_path, UPSTREAM_SOURCE_SHA256),
            (UPSTREAM_ORDERING_RELATIVE_PATH, ordering_path, UPSTREAM_ORDERING_SHA256),
            (UPSTREAM_UTILS_RELATIVE_PATH, utils_path, UPSTREAM_UTILS_SHA256),
            (UPSTREAM_LICENSE_RELATIVE_PATH, license_path, UPSTREAM_LICENSE_SHA256),
        ]
        for relative, expected_digest in PYCALPHAD_DIRECT_SOURCE_PINS.items():
            direct_path = _Path(
                pycalphad_distribution.locate_file(relative)
            ).resolve(strict=True)
            actual_digest, _direct_size = _hash_regular_file(
                direct_path,
                maximum=_MAX_RUNTIME_FILE_BYTES,
                reason="W2B_INSTRUMENT_SOURCE_DRIFT",
            )
            if actual_digest != expected_digest:
                _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
            direct_paths.append((relative, direct_path, expected_digest))
        direct_by_relative = {
            relative: path for relative, path, _digest in direct_paths
        }
        database = getattr(pycalphad, "Database")
        workspace = getattr(pycalphad, "Workspace")
        if (
            database is not getattr(database_module, "Database")
            or workspace is not getattr(workspace_module, "Workspace")
            or getattr(database, "__module__", None) != "pycalphad.io.database"
            or getattr(database, "__qualname__", None) != "Database"
            or getattr(workspace, "__module__", None) != "pycalphad.core.workspace"
            or getattr(workspace, "__qualname__", None) != "Workspace"
            or getattr(variables_module, "X").__module__ != "pycalphad.variables"
            or getattr(variables_module, "X").__qualname__ != "MoleFraction"
            or getattr(phase_record_factory_module, "PhaseRecordFactory").__module__
            != "pycalphad.codegen.phase_record_factory"
            or getattr(phase_record_factory_module, "PhaseRecordFactory").__qualname__
            != "PhaseRecordFactory"
            or _Path(pycalphad.__file__).resolve(strict=True)
            != direct_by_relative["pycalphad/__init__.py"]
            or _Path(database_module.__file__).resolve(strict=True)
            != direct_by_relative["pycalphad/io/database.py"]
            or _Path(workspace_module.__file__).resolve(strict=True)
            != direct_by_relative["pycalphad/core/workspace.py"]
            or _Path(variables_module.__file__).resolve(strict=True)
            != direct_by_relative["pycalphad/variables.py"]
            or _Path(core_utils_module.__file__).resolve(strict=True)
            != direct_by_relative["pycalphad/core/utils.py"]
            or _Path(phase_record_factory_module.__file__).resolve(strict=True)
            != direct_by_relative[
                "pycalphad/codegen/phase_record_factory.py"
            ]
        ):
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        workspace_path = _Path(
            workspace_module.__file__
        ).resolve(strict=True)
        core_utils_path = _Path(core_utils_module.__file__).resolve(strict=True)
        phase_record_factory_path = _Path(
            phase_record_factory_module.__file__
        ).resolve(strict=True)
        database_path = direct_by_relative["pycalphad/io/database.py"]
        variables_path = direct_by_relative["pycalphad/variables.py"]
        cache_path = direct_by_relative["pycalphad/core/cache.py"]
        x_class = getattr(variables_module, "X")
        phase_record_factory = getattr(
            phase_record_factory_module, "PhaseRecordFactory"
        )
        conditions_descriptor = vars(workspace)["conditions"]
        calc_opts_descriptor = vars(workspace)["calc_opts"]
        origin_rows = (
            (getattr(core_utils_module, "filter_phases"), "pycalphad.core.utils", "filter_phases", core_utils_path),
            (getattr(core_utils_module, "unpack_species"), "pycalphad.core.utils", "unpack_species", core_utils_path),
            (getattr(core_utils_module, "instantiate_models"), "pycalphad.core.utils", "instantiate_models", core_utils_path),
            (getattr(ordering_module, "create_ordering_records"), "scheil.ordering", "create_ordering_records", ordering_path),
            (getattr(ordering_module, "_wks_ordering_rename_map"), "scheil.ordering", "_wks_ordering_rename_map", ordering_path),
            (getattr(simulate, "is_converged"), "scheil.simulate", "is_converged", source_path),
            (getattr(simulate, "_get_stable_phases_with_multiplicities"), "scheil.simulate", "_get_stable_phases_with_multiplicities", source_path),
            (getattr(workspace, "__init__"), "pycalphad.core.workspace", "Workspace.__init__", workspace_path),
            (getattr(workspace, "get"), "pycalphad.core.workspace", "Workspace.get", workspace_path),
            (getattr(workspace, "_detect_phase_multiplicity"), "pycalphad.core.workspace", "Workspace._detect_phase_multiplicity", workspace_path),
            (getattr(database, "__new__"), "pycalphad.io.database", "Database.__new__", database_path),
            (getattr(x_class, "__new__"), "pycalphad.variables", "StateVariable.__new__", cache_path),
            (getattr(x_class, "__init__"), "pycalphad.variables", "MoleFraction.__init__", variables_path),
            (getattr(phase_record_factory, "__init__"), "pycalphad.codegen.phase_record_factory", "PhaseRecordFactory.__init__", phase_record_factory_path),
            (getattr(type(conditions_descriptor), "__set__"), "pycalphad.core.workspace", "ConditionsField.__set__", workspace_path),
            (getattr(type(calc_opts_descriptor), "__get__"), "pycalphad.core.workspace", "DictField.__get__", workspace_path),
            (getattr(type(calc_opts_descriptor), "get_proxy"), "pycalphad.core.workspace", "DictField.get_proxy", workspace_path),
        )
        for function, module_name, qualified_name, path in origin_rows:
            _require_function_origin(
                function,
                module_name=module_name,
                qualified_name=qualified_name,
                source_path=path,
            )
        code_bindings = tuple(
            (function, function.__code__)
            for function, _module_name, _qualified_name, _path in origin_rows
        )
        instrumentation_digest, normalized_digest = _verify_instrumentation_source_pin(
            expected_instrumentation_source_sha256
        )
        runtime = _RuntimeModules(
            Database=database,
            Workspace=workspace,
            N=getattr(variables_module, "N"),
            P=getattr(variables_module, "P"),
            T=getattr(variables_module, "T"),
            X=x_class,
            filter_phases=getattr(core_utils_module, "filter_phases"),
            unpack_species=getattr(core_utils_module, "unpack_species"),
            instantiate_models=getattr(core_utils_module, "instantiate_models"),
            PhaseRecordFactory=phase_record_factory,
            create_ordering_records=getattr(ordering_module, "create_ordering_records"),
            wks_ordering_rename_map=getattr(ordering_module, "_wks_ordering_rename_map"),
            is_converged=getattr(simulate, "is_converged"),
            get_stable_phases_with_multiplicities=getattr(
                simulate, "_get_stable_phases_with_multiplicities"
            ),
            numpy=numpy,
            numpy_isnan=getattr(numpy, "isnan"),
            numpy_get_state=getattr(getattr(numpy, "random"), "get_state"),
            pycalphad_module=pycalphad,
            database_module=database_module,
            workspace_module=workspace_module,
            variables_module=variables_module,
            core_utils_module=core_utils_module,
            phase_record_factory_module=phase_record_factory_module,
            scheil_module=scheil,
            simulate_module=simulate,
            ordering_module=ordering_module,
            workspace_init=getattr(workspace, "__init__"),
            workspace_get=getattr(workspace, "get"),
            workspace_detect_phase_multiplicity=getattr(
                workspace, "_detect_phase_multiplicity"
            ),
            workspace_conditions_descriptor=conditions_descriptor,
            workspace_calc_opts_descriptor=calc_opts_descriptor,
            callable_code_bindings=code_bindings,
            direct_source_paths=tuple(direct_paths),
            source_sha256=source_digest,
            ordering_sha256=ordering_digest,
            utils_sha256=utils_digest,
            license_sha256=license_digest,
            instrumentation_source_sha256=instrumentation_digest,
            instrumentation_normalized_source_sha256=normalized_digest,
            scheil_payload_manifest_sha256=scheil_manifest,
            pycalphad_payload_manifest_sha256=pycalphad_manifest,
        )
        _verify_runtime_at_use(runtime)
        return runtime
    except SolidificationInstrumentationError:
        raise
    except Exception as error:
        raise SolidificationInstrumentationError("W2B_INSTRUMENT_RUNTIME_VERSION") from error


def _verify_trace_environment(provenance: TraceProvenance) -> _RuntimeModules:
    _require_fixed_authority()
    modules = _verify_exact_runtime(provenance.instrumentation_source_sha256)
    if (
        modules.instrumentation_source_sha256
        != provenance.instrumentation_source_sha256
        or modules.instrumentation_normalized_source_sha256
        != provenance.instrumentation_normalized_source_sha256
        or modules.source_sha256 != provenance.upstream_source_sha256
        or modules.ordering_sha256 != provenance.upstream_ordering_sha256
        or modules.utils_sha256 != provenance.upstream_utils_sha256
        or modules.license_sha256 != provenance.upstream_license_sha256
        or modules.scheil_payload_manifest_sha256
        != provenance.scheil_payload_manifest_sha256
        or modules.pycalphad_payload_manifest_sha256
        != provenance.pycalphad_payload_manifest_sha256
    ):
        _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
    try:
        runtime_card = provenance.profile_receipt_card.runtime
        runtime_path = (
            _Path(__file__).resolve().parents[1]
            / runtime_card.relative_path
        )
        runtime_digest, runtime_size = _hash_regular_file(
            runtime_path,
            maximum=_MAX_RUNTIME_FILE_BYTES,
            reason="W2B_INSTRUMENT_SOURCE_DRIFT",
        )
        full_request = provenance.domain_receipt_card.full_request.value()
        request_card = full_request["request"]
        components = list(request_card["components"])
        effective = tuple(provenance.domain_receipt_card.effective_phases)
        if (
            runtime_digest != runtime_card.sha256
            or runtime_size != runtime_card.size_bytes
            or tuple(request_card["phases"]["effective"]) != effective
        ):
            _fail("W2B_INSTRUMENT_SOURCE_DRIFT")
        _verify_runtime_at_use(modules)
        database = modules.Database(str(runtime_path))
        filtered = modules.filter_phases(
            database,
            modules.unpack_species(database, components),
            list(effective),
        )
        records = modules.create_ordering_records(
            database,
            components,
            filtered,
        )
        effective_set = set(effective)
        rederived_ordering_authority = _ordering_authority_pairs(
            tuple(
                sorted(
                    (
                        _token(record.ordered_phase_name),
                        _token(record.disordered_phase_name),
                    )
                    for record in records
                    if record.ordered_phase_name in effective_set
                    and record.disordered_phase_name in effective_set
                )
            )
        )
        _verify_runtime_at_use(modules)
    except SolidificationInstrumentationError:
        raise
    except Exception as error:
        raise SolidificationInstrumentationError(
            "W2B_INSTRUMENT_CONTEXT_INVALID"
        ) from error
    if rederived_ordering_authority != provenance.ordering_rename_authority:
        _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
    return modules


class _NativeAttemptSolver:
    """One logical callback per Workspace solve in the pinned port."""

    __slots__ = (
        "liquid_phase",
        "_feature",
        "_modules",
        "_dbf",
        "_components",
        "_phases",
        "_solid_phases",
        "_eq_kwargs",
        "_ordering_records",
        "ordering_model_authority",
        "_workspace",
        "_independent_components",
    )

    def __init__(self, modules: _RuntimeModules, dbf: object, request: object) -> None:
        if request.adaptive is not False:
            _fail("W2B_INSTRUMENT_ADAPTIVE_UNSUPPORTED")
        _verify_runtime_at_use(modules)
        self.liquid_phase = request.liquid_phase
        self._feature = request.feature
        self._modules = modules
        self._dbf = dbf
        self._components = list(request.components)
        try:
            self._phases = modules.filter_phases(
                dbf,
                modules.unpack_species(dbf, self._components),
                list(request.phases),
            )
            self._ordering_records = modules.create_ordering_records(
                dbf, self._components, self._phases
            )
            effective_phase_set = set(request.phases)
            self.ordering_model_authority = _ordering_authority_pairs(
                tuple(
                    sorted(
                        (
                            _token(record.ordered_phase_name),
                            _token(record.disordered_phase_name),
                        )
                        for record in self._ordering_records
                        if record.ordered_phase_name in effective_phase_set
                        and record.disordered_phase_name in effective_phase_set
                    )
                )
            )
            if self.ordering_model_authority:
                # Exact per-call ordering decisions depend on Workspace Y
                # site-fraction vectors plus ordering-record sublattice
                # metadata.  This trace schema intentionally carries neither,
                # so a non-empty model cannot be represented authentically.
                # Fail before constructing any solver-backed physical point.
                _fail("W2B_INSTRUMENT_ORDERING_MAPPING_UNREPRESENTABLE")
            self._solid_phases = tuple(
                phase
                for phase in request.phases
                if phase != self.liquid_phase
            )
            models = modules.instantiate_models(dbf, self._components, self._phases)
            self._eq_kwargs = {
                "models": models,
                "phase_record_factory": modules.PhaseRecordFactory(
                    dbf,
                    self._components,
                    [modules.N, modules.P, modules.T],
                    models,
                ),
                "calc_opts": {"pdens": request.pdens},
            }
            self._workspace = None
            pure_in_request_order = tuple(
                name for name in request.components if name != "VA"
            )
            dependent = pure_in_request_order[-1]
            self._independent_components = tuple(
                sorted(name for name, _value in request.composition if name != dependent)
            )
        except Exception:
            # The public stage recorder captures the original bounded
            # exception identity before any stable public wrapping.
            raise

    def solve(
        self,
        *,
        temperature_k: float,
        pressure_pa: float,
        composition: tuple[tuple[str, float], ...],
        stage: str,
        call_id: str,
    ) -> _SolverObservation:
        del stage, call_id
        _verify_runtime_at_use(self._modules)
        conditions = {
            self._modules.T: temperature_k,
            self._modules.P: pressure_pa,
            self._modules.N: 1.0,
        }
        conditions.update(
            {self._modules.X(name): value for name, value in composition}
        )
        if self._feature == "equilibrium_solidification":
            workspace = self._modules.Workspace(
                self._dbf,
                self._components,
                self._phases,
                conditions,
                **self._eq_kwargs,
            )
        else:
            if self._workspace is None:
                self._workspace = self._modules.Workspace(
                    self._dbf,
                    self._components,
                    self._phases,
                    calc_opts=self._eq_kwargs.get("calc_opts"),
                )
            workspace = self._workspace
            workspace.conditions = conditions
            workspace.calc_opts.update(self._eq_kwargs["calc_opts"])
        converged = bool(self._modules.is_converged(workspace))
        gm_converged = True
        if self._feature == "scheil_solidification":
            gm_converged = not bool(
                self._modules.numpy_isnan(
                    self._modules.workspace_get(workspace, "GM")
                )
            )
        rename = self._modules.wks_ordering_rename_map(
            workspace, self._ordering_records
        )
        if rename:
            # Do not trust or serialize a per-instance rename as authority.
            # Full Y/site-fraction replay evidence is required before this can
            # ever become an accepted physical witness.
            _fail("W2B_INSTRUMENT_ORDERING_MAPPING_UNREPRESENTABLE")
        multiplicity_names = tuple(
            self._modules.get_stable_phases_with_multiplicities(workspace)
        )
        rows: list[tuple[str, str, float]] = []
        for phase_name in multiplicity_names:
            if not phase_name:
                continue
            amount = float(
                self._modules.workspace_get(workspace, f"NP({phase_name})")
            )
            display_name = rename.get(phase_name, phase_name)
            rows.append((phase_name, display_name, amount))
        request_phase_index = {
            name: index
            for index, name in enumerate(self._solid_phases)
        }

        def _native_raw_source_key(
            row: tuple[str, str, float],
        ) -> tuple[int, int, int, str]:
            base, ordinal = _phase_instance_parts(row[0]) or (row[0], None)
            return (
                0 if base == self.liquid_phase else 1,
                request_phase_index.get(base, len(request_phase_index)),
                0 if ordinal is None else ordinal,
                base,
            )

        # Canonicalize only by the exact raw source identity.  The mapped
        # target never influences raw evidence order, so mixed ordering
        # decisions cannot reorder or erase source instances.
        rows.sort(key=_native_raw_source_key)
        raw = tuple((raw_name, amount) for raw_name, _mapped, amount in rows)
        raw_mapping = tuple(
            (raw_name, mapped) for raw_name, mapped, _amount in rows
        )
        ordering_rename_authority = _ordering_instance_authority_pairs(
            tuple(
                sorted(
                    (
                        (raw_name, mapped)
                        for raw_name, mapped, _amount in rows
                        if mapped != _phase_instance_sort_key(raw_name)[0]
                    ),
                    key=lambda pair: _phase_instance_sort_key(pair[0]),
                )
            )
        )
        mapped_sequence: list[tuple[str, float]] = []
        for target in (self.liquid_phase,) + self._solid_phases:
            found = False
            total = 0.0
            for _raw_name, mapped, amount in rows:
                if mapped == target:
                    found = True
                    total += amount
            if found:
                mapped_sequence.append((target, total))
        stable = tuple(name for name, _amount in mapped_sequence)
        liquid_composition: list[tuple[str, float]] = []
        if self.liquid_phase in stable:
            for component in self._independent_components:
                liquid_composition.append(
                    (
                        component,
                        float(
                            self._modules.workspace_get(
                                workspace,
                                f"X({self.liquid_phase},{component})",
                            )
                        ),
                    )
                )
        return _SolverObservation(
            converged=converged,
            gm_converged=gm_converged,
            stable_phases=stable,
            raw_phase_fractions=raw,
            phase_amounts=tuple(mapped_sequence),
            liquid_composition=tuple(liquid_composition),
            raw_instance_mapping=raw_mapping,
            ordering_rename_authority=ordering_rename_authority,
        )


def _provenance(
    modules: _RuntimeModules,
    domain: object,
    pre_snapshot: object,
    lease: object,
    request: object,
    ordering_rename_authority: tuple[tuple[str, str], ...] = (),
) -> TraceProvenance:
    _require_fixed_authority()
    profile = domain.profile_receipt
    if (
        request.database.family != profile.family
        or request.database.profile_id != profile.profile
        or request.database.profile_role != profile.profile_role
    ):
        _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
    is_fe = profile.family == "fe"
    c15_phase = _fixed_value("c15_phase")
    assert type(c15_phase) is str
    c15_retained = (
        c15_phase in domain.candidate_phases
        and c15_phase in domain.requested_phases
        and c15_phase in domain.effective_phases
        and c15_phase not in domain.excluded_phases
    )
    checked_ordering_authority = _ordering_authority_pairs(
        ordering_rename_authority
    )
    return TraceProvenance(
        instrumentation_id=_fixed_value("instrumentation_id"),
        instrumentation_version=_fixed_value("instrumentation_version"),
        instrumentation_source_sha256=modules.instrumentation_source_sha256,
        instrumentation_normalized_source_sha256=(
            modules.instrumentation_normalized_source_sha256
        ),
        upstream_package=_fixed_value("upstream_package"),
        upstream_version=_fixed_value("upstream_version"),
        upstream_source_relative_path=_fixed_value(
            "upstream_source_relative_path"
        ),
        upstream_source_sha256=modules.source_sha256,
        upstream_ordering_relative_path=_fixed_value(
            "upstream_ordering_relative_path"
        ),
        upstream_ordering_sha256=modules.ordering_sha256,
        upstream_utils_relative_path=_fixed_value(
            "upstream_utils_relative_path"
        ),
        upstream_utils_sha256=modules.utils_sha256,
        upstream_license_relative_path=_fixed_value(
            "upstream_license_relative_path"
        ),
        upstream_license_sha256=modules.license_sha256,
        scheil_payload_file_count=_fixed_value("scheil_payload_file_count"),
        scheil_payload_total_bytes=_fixed_value("scheil_payload_total_bytes"),
        scheil_payload_manifest_sha256=modules.scheil_payload_manifest_sha256,
        pycalphad_version=_fixed_value("pycalphad_version"),
        pycalphad_payload_file_count=_fixed_value(
            "pycalphad_payload_file_count"
        ),
        pycalphad_payload_total_bytes=_fixed_value(
            "pycalphad_payload_total_bytes"
        ),
        pycalphad_payload_manifest_sha256=(
            modules.pycalphad_payload_manifest_sha256
        ),
        numpy_version=_fixed_value("numpy_version"),
        runtime_trust_boundary=_fixed_value("runtime_trust_boundary"),
        family=profile.family,
        profile=profile.profile,
        profile_role=profile.profile_role,
        profile_receipt_digest=profile.canonical_digest,
        domain_receipt_digest=domain.canonical_digest,
        execution_lease_id=lease.lease_id,
        execution_snapshot_digest=lease.execution_snapshot_digest,
        profile_receipt_card=profile,
        domain_receipt_card=domain,
        pre_snapshot_card=pre_snapshot,
        fe_baseline_decision=profile.baseline_decision,
        c15_exclusion_decision=profile.c15_exclusion_decision,
        c15_retained=c15_retained if is_fe else False,
        adaptive=request.adaptive,
        pdens=request.pdens,
        rng_algorithm=_fixed_value("rng_algorithm"),
        rng_seed=_fixed_value("rng_seed"),
        adaptive_sample_sha256=_fixed_value("adaptive_sample_sha256"),
        binary_search_tolerance_k=(
            request.binary_search_tolerance_k
            if type(request) is _path.EquilibriumSolidificationRequest
            else None
        ),
        stop_liquid_fraction=(
            request.stop_liquid_fraction
            if type(request) is _path.ScheilSolidificationRequest
            else None
        ),
        fraction_roundoff_policy_id=_fixed_value(
            "fraction_roundoff_policy_id"
        ),
        fraction_roundoff_solver_package="pycalphad",
        fraction_roundoff_solver_version=_fixed_value("pycalphad_version"),
        fraction_roundoff_upstream_package=_fixed_value("upstream_package"),
        fraction_roundoff_upstream_version=_fixed_value("upstream_version"),
        fraction_roundoff_feature_id=request.feature,
        fraction_roundoff_abs_tolerance=_fixed_value(
            "fraction_roundoff_abs_tolerance"
        ),
        phase_mapping_policy_id=_fixed_value("phase_mapping_policy_id"),
        phase_mapping_partition_aggregation_abs_tolerance=(
            _fixed_value("fraction_roundoff_abs_tolerance")
        ),
        phase_mapping_physical_balance_abs_tolerance=(
            _fixed_value("physical_balance_abs_tolerance")
        ),
        phase_mapping_raw_normalization_observation_cap=(
            _fixed_value("raw_normalization_observation_cap")
        ),
        ordering_rename_authority_policy_id=(
            _fixed_value("ordering_rename_authority_policy_id")
        ),
        ordering_rename_authority=checked_ordering_authority,
        ordering_rename_authority_sha256=_ordering_authority_digest(
            profile_receipt_digest=profile.canonical_digest,
            domain_receipt_digest=domain.canonical_digest,
            pairs=checked_ordering_authority,
        ),
    )


def _spec_from_bound_request(request: object, bounds: dict[str, object]) -> _RunSpec:
    pure = tuple(name for name in request.components if name != "VA")
    dependent = pure[-1]
    solver_composition = tuple(
        (name, value) for name, value in request.composition if name != dependent
    )
    temperature = bounds["temperature_k"]
    return _RunSpec(
        feature_id=request.feature,
        components=tuple(request.components),
        bulk_composition=tuple(request.composition),
        solver_composition=solver_composition,
        phases=tuple(request.phases),
        liquid_phase=request.liquid_phase,
        pressure_pa=request.pressure_pa,
        start_temperature_k=request.start_temperature_k,
        minimum_temperature_k=temperature["minimum"],
        step_temperature_k=request.step_temperature_k,
        adaptive=request.adaptive,
        pdens=request.pdens,
        binary_search_tolerance_k=(
            request.binary_search_tolerance_k
            if type(request) is _path.EquilibriumSolidificationRequest
            else None
        ),
        stop_liquid_fraction=(
            request.stop_liquid_fraction
            if type(request) is _path.ScheilSolidificationRequest
            else None
        ),
    )


def _finalize_public_trace(
    *,
    context: object,
    trace: InstrumentedSolidificationTrace,
    modules: _RuntimeModules,
    ambient_rng_before: str,
) -> InstrumentedSolidificationTrace:
    _require_fixed_authority()
    context._guard()
    if _ambient_numpy_rng_digest(modules) != ambient_rng_before:
        _fail("W2B_INSTRUMENT_AMBIENT_RNG_MUTATION")
    _verify_trace_environment(trace.provenance)
    return _copy_trace(trace)


def _public_end_guard(
    context: object,
    modules: _RuntimeModules,
    ambient_rng_before: str,
    provenance: TraceProvenance,
) -> None:
    _require_fixed_authority()
    context._guard()
    if _ambient_numpy_rng_digest(modules) != ambient_rng_before:
        _fail("W2B_INSTRUMENT_AMBIENT_RNG_MUTATION")
    _verify_trace_environment(provenance)


class ReceiptBoundInstrumentedSolidification:
    """Single-use INTERNAL runner bound to one active lease PRE window."""

    __slots__ = ("_context", "_domain", "_pre", "_lease", "_budget", "_used")

    def __init__(
        self,
        *,
        domain_receipt: object,
        pre_snapshot: object,
        execution_lease: object,
        budget: object = InstrumentationBudget(),
    ) -> None:
        try:
            _require_fixed_authority()
            self._context = _binding.ReceiptBoundSolidificationBackend(
                domain_receipt=domain_receipt,
                pre_snapshot=pre_snapshot,
                execution_lease=execution_lease,
            )
            # Keep an authoritative deep reconstruction for provenance.  The
            # caller-owned frozen object can still be attacked with
            # object.__setattr__; it is never read for trace metadata again.
            self._domain = _receipts._rebuild_domain_receipt(domain_receipt)
            self._pre = _receipts._rebuild_pre_snapshot(pre_snapshot)
            self._lease = execution_lease
            self._budget = _copy_budget(budget)
            self._used = False
        except SolidificationInstrumentationError:
            raise
        except Exception as error:
            raise SolidificationInstrumentationError("W2B_INSTRUMENT_CONTEXT_INVALID") from error

    def simulate(self, request: object) -> InstrumentedSolidificationTrace:
        _require_fixed_authority()
        if self._used:
            _fail("W2B_INSTRUMENT_CONTEXT_INVALID")
        self._used = True
        modules: _RuntimeModules | None = None
        ambient_rng_before: str | None = None
        try:
            checked = self._context._bind_request(request)
            if checked.adaptive is not False:
                _fail("W2B_INSTRUMENT_ADAPTIVE_UNSUPPORTED")
            runtime_path = self._context._guard()
            modules = _verify_exact_runtime()
            ambient_rng_before = _ambient_numpy_rng_digest(modules)
            provenance = _provenance(
                modules, self._domain, self._pre, self._lease, checked
            )
            spec = _spec_from_bound_request(checked, self._context._bounds)
            recorder = _start_recorder(spec, self._budget)
            recorder.finalization_guard = lambda: _public_end_guard(
                self._context,
                modules,
                ambient_rng_before,
                provenance,
            )
            recorder.emit(
                event_kind="DATABASE_LOAD_BEGIN",
                stage="DATABASE_LOAD",
                outcome="BEGIN",
                pressure_pa=spec.pressure_pa,
                phases=spec.phases,
            )
            try:
                _verify_runtime_at_use(modules)
                database = modules.Database(str(runtime_path))
            except Exception as error:
                trace = _run_error_finish(
                    recorder,
                    provenance,
                    spec,
                    stage="DATABASE_LOAD",
                    error=error,
                    temperature_k=None,
                    parent_point_id=None,
                )
                return _finalize_public_trace(
                    context=self._context,
                    trace=trace,
                    modules=modules,
                    ambient_rng_before=ambient_rng_before,
                )
            recorder.emit(
                event_kind="DATABASE_LOAD_RESULT",
                stage="DATABASE_LOAD",
                outcome="SUCCESS",
                pressure_pa=spec.pressure_pa,
                phases=spec.phases,
            )
            recorder.emit(
                event_kind="SOLVER_PREPARE_BEGIN",
                stage="SOLVER_PREPARE",
                outcome="BEGIN",
                pressure_pa=spec.pressure_pa,
                phases=spec.phases,
            )
            try:
                solver = _NativeAttemptSolver(modules, database, checked)
            except Exception as error:
                trace = _run_error_finish(
                    recorder,
                    provenance,
                    spec,
                    stage="SOLVER_PREPARE",
                    error=error,
                    temperature_k=None,
                    parent_point_id=None,
                )
                return _finalize_public_trace(
                    context=self._context,
                    trace=trace,
                    modules=modules,
                    ambient_rng_before=ambient_rng_before,
                )
            provenance = _provenance(
                modules,
                self._domain,
                self._pre,
                self._lease,
                checked,
                ordering_rename_authority=solver.ordering_model_authority,
            )
            recorder.emit(
                event_kind="SOLVER_PREPARE_RESULT",
                stage="SOLVER_PREPARE",
                outcome="SUCCESS",
                pressure_pa=spec.pressure_pa,
                phases=spec.phases,
            )
            try:
                trace = _dispatch_port(spec, solver, provenance, recorder)
            except Exception as error:
                if recorder.events[-1].event_kind == "TERMINATION":
                    raise
                temperature_k, parent_point_id = _last_run_context(recorder)
                trace = _run_error_finish(
                    recorder,
                    provenance,
                    spec,
                    stage="DISPATCH",
                    error=error,
                    temperature_k=temperature_k,
                    parent_point_id=parent_point_id,
                )
            return _finalize_public_trace(
                context=self._context,
                trace=trace,
                modules=modules,
                ambient_rng_before=ambient_rng_before,
            )
        except SolidificationInstrumentationError:
            raise
        except _binding.Wave2BSolidificationBackendError as error:
            raise SolidificationInstrumentationError("W2B_INSTRUMENT_REQUEST_INVALID") from error
        except Exception as error:
            raise SolidificationInstrumentationError(
                "W2B_INSTRUMENT_CONTEXT_INVALID"
            ) from error
        finally:
            if modules is not None and ambient_rng_before is not None:
                if _ambient_numpy_rng_digest(modules) != ambient_rng_before:
                    _fail("W2B_INSTRUMENT_AMBIENT_RNG_MUTATION")


__all__ = (
    "TRACE_SCHEMA",
    "EVENT_SCHEMA",
    "INSTRUMENTATION_ID",
    "INSTRUMENTATION_VERSION",
    "UPSTREAM_VERSION",
    "UPSTREAM_SOURCE_SHA256",
    "UPSTREAM_ORDERING_SHA256",
    "UPSTREAM_UTILS_SHA256",
    "UPSTREAM_LICENSE_SHA256",
    "FRACTION_ROUNDOFF_POLICY_ID",
    "FRACTION_ROUNDOFF_ABS_TOLERANCE",
    "PHASE_MAPPING_POLICY_ID",
    "ORDERING_RENAME_AUTHORITY_POLICY_ID",
    "PHYSICAL_BALANCE_ABS_TOLERANCE",
    "RAW_NORMALIZATION_OBSERVATION_CAP",
    "SCHEIL_CLOSURE_EVIDENCE_POLICY_ID",
    "STEEL_REQUIRED_PRODUCT_SCOPE",
    "FE_BASELINE_PROFILE",
    "FE_EXCLUSION_DECISION_MADE",
    "COUNTS_TOWARD_FEATURE_COVERAGE",
    "ACCEPTANCE_CLAIM",
    "PRODUCTION_USE",
    "INSTRUMENTATION_REASON_CODES",
    "SolidificationInstrumentationError",
    "InstrumentationBudget",
    "FractionResidualCard",
    "PhaseMappingCard",
    "TraceProvenance",
    "SolidificationTraceEvent",
    "InstrumentedSolidificationTrace",
    "ReceiptBoundInstrumentedSolidification",
    "trace_canonical_bytes",
)
