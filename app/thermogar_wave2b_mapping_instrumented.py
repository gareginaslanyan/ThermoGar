"""Deterministic INTERNAL instrumentation for pycalphad 0.11.2 mapping.

This module is deliberately import-safe: importing it does not import pycalphad,
NumPy, the Wave 2B receipt layer, or any thermodynamic database.  The public
edge :func:`bind_execution_context` accepts only an active receipt
``ExecutionLease`` in its PRE execution window.  The runtime database path is
therefore always the lease's locked, content-addressed ``runtime`` snapshot.

The implementation subclasses the exact upstream BinaryStrategy,
IsoplethStrategy and TernaryStrategy at run time.  Small portions of upstream
mapping control flow are reproduced so each actual solver boundary can be
observed without parsing stdout and without global monkeypatching.  Those
portions are pinned to the exact source files and hashes below.

Upstream license notice (retained as required by the MIT license):

    pycalphad, a Python library for the CALculation of PHAse Diagrams

    The MIT License (MIT)

    Copyright (c) 2014-2023 Richard Otis and Zi-Kui Liu
    Copyright (c) 2016-2023 Brandon Bocklund
    Copyright (c) 2016-2023 California Institute of Technology
    Copyright (c) 2018-2023 Materials Genome Foundation
    Copyright (c) 2020      David Walz

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.

This layer is diagnostic infrastructure only.  It does not grant release,
feature coverage, acceptance, production use, or any completion claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence
import copy
import importlib
import inspect
import json
import math
import os
import re
import struct
import threading
import types


_CONCRETE_PATH_TYPE = type(Path())


def _make_integrity_gate():
    """Return a one-shot closure gate for the import-time trust anchor.

    Critical entry points are wrapped with this exact closure before the
    helper manifest is captured.  Consequently, rebinding either exported
    verifier global cannot redirect an already-created constructor or
    serializer.  The cell is sealed once, after the helper/control root has
    been verified, and is never module-global authority.
    """

    state = [None]

    def gate(*, deep: bool = False, _install: object = None):
        if _install is not None:
            if state[0] is not None or type(_install) is not tuple or len(_install) != 4:
                raise RuntimeError("Instrumentation integrity gate is already sealed")
            verifier, namespace, error_type, source_pin = _install
            if (
                not callable(verifier)
                or type(namespace) is not dict
                or not isinstance(error_type, type)
                or type(source_pin) is not str
                or len(source_pin) != 64
                or any(character not in "0123456789abcdef" for character in source_pin)
            ):
                raise RuntimeError("Instrumentation integrity gate install is invalid")
            root, refs = verifier(deep=True)
            state[0] = (verifier, namespace, error_type, source_pin)
            return root, refs, source_pin
        if state[0] is None:
            raise RuntimeError("Instrumentation integrity gate is not sealed")
        verifier, namespace, error_type, source_pin = state[0]
        root, refs = verifier(deep=deep)
        if (
            namespace.get("_HELPER_TRUST_VERIFY") is not verifier
            or namespace.get("INSTRUMENTATION_SOURCE_PIN_SHA256") is not source_pin
        ):
            raise error_type("W2B_INSTRUMENT_SOURCE_MISMATCH")
        return root, refs, source_pin

    gate.__module__ = f"{__name__}.__integrity_gate__"
    return gate


_INTEGRITY_GATE = _make_integrity_gate()


def _make_session_identity_registry(graph_builder: object):
    """Return exact-identity session execution and evidence authorities."""

    if not isinstance(graph_builder, types.FunctionType):
        raise RuntimeError("Instrumentation session graph builder is invalid")
    records: dict[int, tuple[object, tuple[object, ...], object, object]] = {}
    issued_strategies: dict[int, object] = {}
    issued_recorders: dict[int, object] = {}
    issued_queues: dict[int, object] = {}
    metadata_records: dict[int, dict[str, object]] = {}
    recorder_records: dict[int, dict[str, object]] = {}
    trace_records: dict[int, dict[str, object]] = {}
    result_records: dict[int, dict[str, object]] = {}
    pending_by_thread: dict[int, list[dict[str, object]]] = {}
    lock = threading.RLock()

    def exact_record(table: dict[int, object], value: object) -> object:
        record = table.get(id(value))
        if type(record) is not dict or record.get("object") is not value:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return record

    def upstream_card(value: object) -> tuple[object, ...]:
        if type(value) is not UpstreamSourceMetadata:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return (
            object.__getattribute__(value, "package"),
            object.__getattribute__(value, "version"),
            object.__getattribute__(value, "package_root_sha256"),
            object.__getattribute__(value, "license_sha256"),
            object.__getattribute__(value, "sources"),
        )

    def metadata_card(value: object) -> tuple[object, ...]:
        if type(value) is not TraceMetadata:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return (
            object.__getattribute__(value, "feature_id"),
            object.__getattribute__(value, "execution_context"),
            object.__getattribute__(value, "family"),
            object.__getattribute__(value, "profile"),
            object.__getattribute__(value, "profile_role"),
            object.__getattribute__(value, "domain_receipt_digest"),
            object.__getattribute__(value, "profile_receipt_digest"),
            object.__getattribute__(value, "execution_snapshot_digest"),
            object.__getattribute__(value, "runtime_sha256"),
            object.__getattribute__(value, "strategy_state_initial_sha256"),
            object.__getattribute__(value, "strategy_state_terminal_sha256"),
            object.__getattribute__(value, "strategy_state_provenance_status"),
            object.__getattribute__(value, "effective_phases"),
            object.__getattribute__(value, "operation_budget"),
            object.__getattribute__(value, "event_budget"),
            object.__getattribute__(value, "instrumentation_source_sha256"),
            upstream_card(object.__getattribute__(value, "upstream")),
        )

    def metadata_kwargs_card(value: object) -> tuple[object, ...]:
        if type(value) is not dict or set(value) != {
            "feature_id", "execution_context", "family", "profile",
            "profile_role", "domain_receipt_digest", "profile_receipt_digest",
            "execution_snapshot_digest", "runtime_sha256",
            "strategy_state_initial_sha256", "strategy_state_terminal_sha256",
            "strategy_state_provenance_status", "effective_phases",
            "operation_budget", "event_budget",
            "instrumentation_source_sha256", "upstream",
        }:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return (
            value["feature_id"], value["execution_context"], value["family"],
            value["profile"], value["profile_role"],
            value["domain_receipt_digest"], value["profile_receipt_digest"],
            value["execution_snapshot_digest"], value["runtime_sha256"],
            value["strategy_state_initial_sha256"],
            value["strategy_state_terminal_sha256"],
            value["strategy_state_provenance_status"],
            value["effective_phases"], value["operation_budget"],
            value["event_budget"], value["instrumentation_source_sha256"],
            upstream_card(value["upstream"]),
        )

    def pending_top() -> dict[str, object]:
        stack = pending_by_thread.get(threading.get_ident())
        if type(stack) is not list or not stack:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return stack[-1]

    def provenance(action: str, *values: object):
        if type(action) is not str or type(values) is not tuple:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        runtime_guard = None
        owner_gate = None
        owner_session = None
        result = None
        delegate = None
        delegate_args: tuple[object, ...] = ()
        with lock:
            if action == "metadata_constructed":
                if len(values) != 1:
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                value = values[0]
                pending = pending_top()
                record = pending.get("record")
                if (
                    pending.get("kind") != "metadata"
                    or type(record) is not dict
                    or record.get("object") is not None
                    or metadata_card(value) != record.get("card")
                    or id(value) in metadata_records
                ):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                record["object"] = value
                metadata_records[id(value)] = record
                pending["constructed"] = value
                return None
            if action == "recorder_constructed":
                if len(values) != 2:
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                value, metadata = values
                pending = pending_top()
                metadata_record = exact_record(metadata_records, metadata)
                if (
                    pending.get("kind") != "recorder"
                    or pending.get("metadata") is not metadata
                    or metadata_record.get("state") != "ACTIVE"
                    or metadata_record.get("recorder") is not None
                    or id(value) in recorder_records
                ):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                record = {
                    "object": value,
                    "token": metadata_record["token"],
                    "binding": metadata_record["binding"],
                    "runtime_guard": metadata_record["runtime_guard"],
                    "issuer": pending["issuer"],
                    "metadata": metadata,
                    "session": metadata_record.get("session"),
                    "strategy": metadata_record.get("strategy"),
                    "session_gate": metadata_record.get("session_gate"),
                    "state": "ACTIVE",
                    "trace": None,
                }
                recorder_records[id(value)] = record
                metadata_record["recorder"] = value
                pending["constructed"] = value
                return None
            if action == "trace_constructed":
                if len(values) != 1:
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                value = values[0]
                pending = pending_top()
                recorder = pending.get("recorder")
                recorder_record = exact_record(recorder_records, recorder)
                metadata = object.__getattribute__(value, "metadata")
                events = object.__getattribute__(value, "events")
                if (
                    pending.get("kind") != "trace"
                    or recorder_record.get("state") != "ACTIVE"
                    or recorder_record.get("metadata") is not metadata
                    or recorder_record.get("session") is None
                    or recorder_record.get("strategy") is None
                    or recorder_record.get("trace") is not None
                    or object.__getattribute__(value, "halted") is not True
                    or type(events) is not tuple
                    or id(value) in trace_records
                ):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                record = {
                    "object": value,
                    "token": recorder_record["token"],
                    "binding": recorder_record["binding"],
                    "runtime_guard": recorder_record["runtime_guard"],
                    "recorder": recorder,
                    "metadata": metadata,
                    "events": events,
                    "event_identities": tuple(events),
                    "canonical_digest": object.__getattribute__(
                        value, "canonical_digest"
                    ),
                    "session": recorder_record["session"],
                    "strategy": recorder_record["strategy"],
                    "issuer": recorder_record["issuer"],
                    "state": "ACTIVE",
                    "result": None,
                }
                trace_records[id(value)] = record
                recorder_record["trace"] = value
                pending["constructed"] = value
                return None
            if action == "result_constructed":
                if len(values) != 1:
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                value = values[0]
                pending = pending_top()
                trace = object.__getattribute__(value, "trace")
                strategy = object.__getattribute__(value, "strategy")
                trace_record = exact_record(trace_records, trace)
                if (
                    pending.get("kind") != "result"
                    or pending.get("trace") is not trace
                    or pending.get("strategy") is not strategy
                    or trace_record.get("strategy") is not strategy
                    or trace_record.get("result") is not None
                    or id(value) in result_records
                ):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                result_records[id(value)] = {
                    "object": value,
                    "trace": trace,
                    "strategy": strategy,
                    "session": trace_record["session"],
                    "exception_type": object.__getattribute__(
                        value, "exception_type"
                    ),
                    "exception_message_sha256": object.__getattribute__(
                        value, "exception_message_sha256"
                    ),
                }
                trace_record["result"] = value
                pending["constructed"] = value
                return None
            if action == "metadata_registered":
                if len(values) != 1:
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                record = metadata_records.get(id(values[0]))
                if type(record) is not dict or record.get("object") is not values[0]:
                    return False
                if (
                    record.get("state") != "ACTIVE"
                    or metadata_card(values[0]) != record.get("card")
                ):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                runtime_guard = record.get("runtime_guard")
                result = True
            elif action in (
                "recorder_registered", "derive_metadata", "snapshot",
            ):
                expected_length = 1 if action in (
                    "recorder_registered", "snapshot"
                ) else 5
                if len(values) != expected_length:
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                recorder = values[0]
                if action == "recorder_registered":
                    record = recorder_records.get(id(recorder))
                    if (
                        type(record) is not dict
                        or record.get("object") is not recorder
                    ):
                        return False
                else:
                    record = exact_record(recorder_records, recorder)
                metadata = object.__getattribute__(recorder, "metadata")
                metadata_record = exact_record(metadata_records, metadata)
                if (
                    record.get("state") != "ACTIVE"
                    or record.get("metadata") is not metadata
                    or metadata_record.get("state") != "ACTIVE"
                    or metadata_record.get("recorder") is not recorder
                    or metadata_card(metadata) != metadata_record.get("card")
                ):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                runtime_guard = record.get("runtime_guard")
                owner_gate = record.get("session_gate")
                owner_session = record.get("session")
                if action == "recorder_registered":
                    result = True
                elif action == "derive_metadata":
                    delegate = record.get("issuer")
                    delegate_args = (
                        "derive_metadata", recorder, metadata,
                        values[1], values[2], values[3],
                    )
                    if values[4] is not metadata:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                elif action == "snapshot":
                    delegate = record.get("issuer")
                    delegate_args = ("trace", recorder)
            elif action == "trace_registered":
                if len(values) != 1:
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                trace = values[0]
                record = trace_records.get(id(trace))
                if (
                    type(record) is not dict
                    or record.get("object") is not trace
                ):
                    return False
                events = object.__getattribute__(trace, "events")
                if (
                    record.get("state") != "ACTIVE"
                    or object.__getattribute__(trace, "metadata")
                    is not record.get("metadata")
                    or events is not record.get("events")
                    or type(events) is not tuple
                    or len(events) != len(record.get("event_identities", ()))
                    or any(
                        observed is not expected
                        for observed, expected in zip(
                            events, record.get("event_identities", ())
                        )
                    )
                    or object.__getattribute__(trace, "canonical_digest")
                    != record.get("canonical_digest")
                ):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                metadata_record = exact_record(
                    metadata_records, record.get("metadata")
                )
                if (
                    metadata_record.get("state") != "ACTIVE"
                    or metadata_record.get("recorder")
                    is not record.get("recorder")
                    or metadata_card(record.get("metadata"))
                    != metadata_record.get("card")
                ):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                try:
                    observed_digest = canonical_trace_digest(
                        {
                            "schema_version": TRACE_SCHEMA,
                            "metadata": record.get("metadata").as_dict(),
                            "operation_count": object.__getattribute__(
                                trace, "operation_count"
                            ),
                            "event_count": len(events),
                            "halted": object.__getattribute__(trace, "halted"),
                            "terminal_reason": object.__getattribute__(
                                trace, "terminal_reason"
                            ),
                            "events": [event.as_dict() for event in events],
                            "acceptance_claim": False,
                            "counts_toward_feature_coverage": False,
                            "production_use": "DENIED",
                        }
                    )
                except BaseException as error:
                    if (
                        isinstance(error, MappingInstrumentationError)
                        and error.reason_code in (
                            "W2B_INSTRUMENT_SOURCE_MISMATCH",
                            "W2B_INSTRUMENT_UPSTREAM_MISMATCH",
                        )
                    ):
                        raise
                    raise MappingInstrumentationError(
                        "W2B_INSTRUMENT_TRACE_INVALID"
                    ) from error
                if observed_digest != record.get("canonical_digest"):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                runtime_guard = record.get("runtime_guard")
                result = True
            elif action == "result_registered":
                if len(values) != 1:
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                value = values[0]
                record = result_records.get(id(value))
                if (
                    type(record) is not dict
                    or record.get("object") is not value
                ):
                    return False
                if (
                    object.__getattribute__(value, "trace")
                    is not record.get("trace")
                    or object.__getattribute__(value, "strategy")
                    is not record.get("strategy")
                    or object.__getattribute__(value, "exception_type")
                    != record.get("exception_type")
                    or object.__getattribute__(value, "exception_message_sha256")
                    != record.get("exception_message_sha256")
                ):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                trace_record = exact_record(trace_records, record.get("trace"))
                if (
                    trace_record.get("state") != "ACTIVE"
                    or trace_record.get("result") is not value
                    or trace_record.get("strategy")
                    is not record.get("strategy")
                    or trace_record.get("session")
                    is not record.get("session")
                ):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                if provenance(
                    "trace_registered", record.get("trace")
                ) is not True:
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                runtime_guard = trace_record.get("runtime_guard")
                result = True
            else:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if runtime_guard is not None:
            if not isinstance(runtime_guard, types.FunctionType):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            runtime_guard(deep=True)
        if owner_gate is not None:
            if (
                not isinstance(owner_gate, types.FunctionType)
                or owner_session is None
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            owner_gate("assert_running", owner_session)
        if delegate is not None:
            if not isinstance(delegate, types.FunctionType):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            return delegate(*delegate_args)
        return result

    session_runner = InstrumentedMappingSession._run_owned

    def registry(action: str, session: object):
        if type(action) is not str or type(session) is not InstrumentedMappingSession:
            raise RuntimeError("Instrumentation session identity action is invalid")
        execution = None
        with lock:
            entry = records.get(id(session))
            if type(entry) is not tuple or len(entry) != 4 or entry[0] is not session:
                raise RuntimeError("Instrumentation session identity is unavailable")
            owner, record, execution_gate, provenance_issue = entry
            if (
                owner is not session
                or not isinstance(execution_gate, types.FunctionType)
                or not isinstance(provenance_issue, types.FunctionType)
            ):
                raise RuntimeError("Instrumentation session identity is unavailable")
            if action == "verify":
                execution_gate("verify_session", session)
                return record
            if action == "execute":
                execution_gate("claim_session", session)
                execution = (
                    record, provenance_issue, execution_gate
                )
            else:
                raise RuntimeError(
                    "Instrumentation session identity action is invalid"
                )
        record, provenance_issue, execution_gate = execution
        try:
            return session_runner(
                session, record, provenance_issue, execution_gate
            )
        finally:
            execution_gate("finish_session", session)

    def session_record(session: object) -> tuple[object, ...]:
        if type(session) is not InstrumentedMappingSession:
            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
        try:
            record = registry("verify", session)
        except BaseException as error:
            raise MappingInstrumentationError(
                "W2B_INSTRUMENT_SESSION_REQUIRED"
            ) from error
        if (
            type(record) is not tuple
            or len(record) != 19
            or type(record[1]) is not tuple
            or len(record[1]) != 20
            or type(record[2]) is not str
            or _SHA256.fullmatch(record[2]) is None
            or type(record[4]) is not _TraceRecorder
            or type(record[6]) is not ExecutionBinding
            or type(record[8]) is not _RuntimeModules
            or type(record[9]) is not str
            or type(record[10]) is not type
            or type(record[11]) is not tuple
            or type(record[12]) is not type(MappingProxyType({}))
            or type(record[13]) is not tuple
            or type(record[14]) is not bytes
            or type(record[15]) is not int
            or isinstance(record[15], bool)
            or type(record[16]) is not TraceMetadata
            or not isinstance(record[0], types.FunctionType)
            or not isinstance(record[17], types.FunctionType)
            or type(record[18]) is not ExecutionBinding
        ):
            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
        return record

    def session_run(session: object) -> object:
        if type(session) is not InstrumentedMappingSession:
            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
        try:
            result = registry("execute", session)
        except MappingInstrumentationError:
            raise
        except BaseException as error:
            raise MappingInstrumentationError(
                "W2B_INSTRUMENT_SESSION_REQUIRED"
            ) from error
        if type(result) is not InstrumentedRunResult:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        record = registry("verify", session)
        if provenance("result_registered", result) is not True:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        strategy = object.__getattribute__(result, "strategy")
        if (
            type(record) is not tuple
            or len(record) != 19
            or strategy is not record[3]
            or object.__getattribute__(result, "strategy") is not record[3]
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return result

    def mint(*factory_args: object, **factory_kwargs: object):
        committed = False
        factory_token = None
        issue = None
        phase = "UNINITIALIZED"
        run_thread = None
        root_depth = 0
        child_strategies: dict[int, list[object]] = {}
        consumed_children: dict[int, object] = {}
        try:
            if (
                type(factory_args) is not tuple
                or len(factory_args) != 3
                or type(factory_kwargs) is not dict
                or len(factory_kwargs) != 4
                or any(type(key) is not str for key in factory_kwargs)
                or set(factory_kwargs) != {
                    "operation_budget",
                    "event_budget",
                    "expected_instrumentation_sha256",
                    "strategy_options",
                }
            ):
                _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
            binding, components, conditions = factory_args
            factory_token = object()
            owner_session = None
            root_strategy = None
            phase = "BUILDING"
            final_trace = None
            final_result = None
            child_strategies = {}
            consumed_children = {}

            def strategy_gate(action: str, *values: object):
                nonlocal root_depth
                if type(action) is not str or type(values) is not tuple:
                    _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                with lock:
                    if action == "register_child":
                        if len(values) != 2 or values[0] is not root_strategy:
                            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                        principal = values[0]
                    elif action in ("enter_strategy", "assert_active"):
                        if len(values) != 1:
                            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                        principal = values[0]
                    elif action == "exit_strategy":
                        if len(values) != 2:
                            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                        principal = values[0]
                    else:
                        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                    child = child_strategies.get(id(principal))
                    consumed_child = consumed_children.get(id(principal))
                    known_principal = (
                        principal is root_strategy
                        or (
                            type(child) is list
                            and len(child) == 2
                            and child[0] is principal
                        )
                        or consumed_child is principal
                    )
                    if not known_principal:
                        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                    if phase == "TERMINAL":
                        _fail(
                            "W2B_INSTRUMENT_SESSION_CONSUMED"
                            if committed
                            else "W2B_INSTRUMENT_SESSION_REQUIRED"
                        )
                    if phase != "RUNNING" or run_thread != threading.get_ident():
                        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                    if action == "register_child":
                        if (
                            root_depth != 1
                            or id(values[1]) in child_strategies
                            or id(values[1]) in consumed_children
                            or values[1] is root_strategy
                        ):
                            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                        child_strategies[id(values[1])] = [values[1], "ARMED"]
                        return None
                    if action == "enter_strategy":
                        strategy = values[0]
                        if strategy is root_strategy:
                            if root_depth != 0:
                                _fail("W2B_INSTRUMENT_SESSION_CONSUMED")
                            root_depth = 1
                            return "ROOT"
                        child = child_strategies.get(id(strategy))
                        if (
                            type(child) is not list
                            or len(child) != 2
                            or child[0] is not strategy
                            or child[1] not in ("ARMED", "DONE")
                            or root_depth != 1
                        ):
                            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                        if child[1] == "DONE":
                            _fail("W2B_INSTRUMENT_SESSION_CONSUMED")
                        child[1] = "ACTIVE"
                        return "CHILD"
                    if action == "assert_active":
                        strategy = values[0]
                        if strategy is root_strategy:
                            if root_depth != 1:
                                _fail("W2B_INSTRUMENT_SESSION_CONSUMED")
                            return None
                        child = child_strategies.get(id(strategy))
                        if (
                            type(child) is not list
                            or len(child) != 2
                            or child[0] is not strategy
                            or root_depth != 1
                        ):
                            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                        if child[1] != "ACTIVE":
                            _fail("W2B_INSTRUMENT_SESSION_CONSUMED")
                        return None
                    if action == "exit_strategy":
                        strategy, marker = values
                        if marker == "ROOT" and strategy is root_strategy:
                            if root_depth != 1 or any(
                                child[1] != "DONE"
                                for child in child_strategies.values()
                            ):
                                _fail("W2B_INSTRUMENT_SESSION_CONSUMED")
                            root_depth = 0
                            return None
                        child = child_strategies.get(id(strategy))
                        if (
                            marker != "CHILD"
                            or type(child) is not list
                            or len(child) != 2
                            or child[0] is not strategy
                            or child[1] != "ACTIVE"
                        ):
                            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                        child[1] = "DONE"
                        return None
                    _fail("W2B_INSTRUMENT_SESSION_REQUIRED")

            def session_gate(action: str, *values: object):
                nonlocal owner_session, root_strategy, phase, run_thread, root_depth
                if type(action) is not str or type(values) is not tuple:
                    _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                with lock:
                    if action == "bind":
                        if (
                            phase != "BUILDING"
                            or len(values) != 2
                            or type(values[0]) is not InstrumentedMappingSession
                            or owner_session is not None
                            or root_strategy is not None
                        ):
                            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                        owner_session, root_strategy = values
                        phase = "FACTORY_BOUND"
                        return None
                    if len(values) != 1 or values[0] is not owner_session:
                        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                    if action == "verify_session":
                        return phase
                    if action == "assert_running":
                        if phase == "TERMINAL":
                            _fail("W2B_INSTRUMENT_SESSION_CONSUMED")
                        if (
                            phase != "RUNNING"
                            or run_thread != threading.get_ident()
                        ):
                            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                        return None
                    if action == "claim_session":
                        if phase != "FACTORY_BOUND":
                            _fail("W2B_INSTRUMENT_SESSION_CONSUMED")
                        phase = "RUNNING"
                        run_thread = threading.get_ident()
                        return None
                    if action == "finish_session":
                        if (
                            phase != "RUNNING"
                            or run_thread != threading.get_ident()
                        ):
                            _fail(
                                "W2B_INSTRUMENT_SESSION_CONSUMED"
                                if phase == "TERMINAL" and committed
                                else "W2B_INSTRUMENT_SESSION_REQUIRED"
                            )
                        valid_finish = (
                            root_depth == 0
                            and not any(
                                type(child) is not list
                                or len(child) != 2
                                or child[1] != "DONE"
                                for child in child_strategies.values()
                            )
                        )
                        try:
                            for key, child in tuple(child_strategies.items()):
                                if (
                                    type(child) is list
                                    and len(child) == 2
                                    and child[0] is not None
                                ):
                                    consumed_children[key] = child[0]
                        finally:
                            phase = "TERMINAL"
                            run_thread = None
                            root_depth = 0
                            child_strategies.clear()
                        if not valid_finish:
                            _fail("W2B_INSTRUMENT_SESSION_CONSUMED")
                        return None
                    _fail("W2B_INSTRUMENT_SESSION_REQUIRED")

            def build_authority(action: str, *values: object):
                if type(action) is not str or type(values) is not tuple:
                    _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                with lock:
                    if (
                        action != "authorize_build"
                        or phase != "BUILDING"
                        or values != (build_authority, strategy_gate)
                    ):
                        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                    return factory_token

            def issue(action: str, *values: object):
                nonlocal final_trace, final_result
                if type(action) is not str or type(values) is not tuple:
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")

                def require_issue_phase(expected: str) -> None:
                    with lock:
                        if (
                            phase != expected
                            or (
                                expected == "RUNNING"
                                and run_thread != threading.get_ident()
                            )
                        ):
                            _fail("W2B_INSTRUMENT_TRACE_INVALID")

                def push_pending(pending: dict[str, object]) -> None:
                    with lock:
                        thread = threading.get_ident()
                        stack = pending_by_thread.setdefault(thread, [])
                        if stack:
                            _fail("W2B_INSTRUMENT_TRACE_INVALID")
                        stack.append(pending)

                def pop_pending(
                    pending: dict[str, object], *, require_constructed: bool
                ) -> object:
                    with lock:
                        thread = threading.get_ident()
                        stack = pending_by_thread.get(thread)
                        if (
                            type(stack) is not list
                            or len(stack) != 1
                            or stack[-1] is not pending
                        ):
                            _fail("W2B_INSTRUMENT_TRACE_INVALID")
                        stack.pop()
                        del pending_by_thread[thread]
                        constructed = pending.get("constructed")
                    if require_constructed and constructed is None:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    return constructed

                def construct_metadata(
                    record: dict[str, object], kwargs: dict[str, object]
                ) -> object:
                    pending = {"kind": "metadata", "record": record}
                    push_pending(pending)
                    try:
                        value = TraceMetadata(**kwargs)
                    except BaseException:
                        pop_pending(pending, require_constructed=False)
                        raise
                    constructed = pop_pending(
                        pending, require_constructed=True
                    )
                    if constructed is not value:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    return value

                def construct_recorder(metadata: object) -> object:
                    pending = {
                        "kind": "recorder", "metadata": metadata,
                        "issuer": issue,
                    }
                    push_pending(pending)
                    try:
                        value = _TraceRecorder(metadata)
                    except BaseException:
                        constructed = pop_pending(
                            pending, require_constructed=False
                        )
                        if constructed is not None:
                            with lock:
                                record = recorder_records.get(id(constructed))
                                metadata_record = metadata_records.get(
                                    id(metadata)
                                )
                                if (
                                    type(record) is dict
                                    and record.get("object") is constructed
                                ):
                                    del recorder_records[id(constructed)]
                                if (
                                    type(metadata_record) is dict
                                    and metadata_record.get("object") is metadata
                                    and metadata_record.get("recorder")
                                    is constructed
                                ):
                                    metadata_record["recorder"] = None
                        raise
                    constructed = pop_pending(
                        pending, require_constructed=True
                    )
                    if constructed is not value:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    return value

                if action == "authorize_build":
                    require_issue_phase("BUILDING")
                    if values != (build_authority, strategy_gate):
                        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                    return factory_token
                if action == "metadata":
                    require_issue_phase("BUILDING")
                    if len(values) != 3:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    checked_binding, runtime_guard, kwargs = values
                    if (
                        type(checked_binding) is not ExecutionBinding
                        or not isinstance(runtime_guard, types.FunctionType)
                        or type(kwargs) is not dict
                        or kwargs.get("execution_context") != "INTERNAL_QUALIFICATION"
                        or kwargs.get("feature_id") != checked_binding.feature_id
                        or kwargs.get("family") != checked_binding.family
                        or kwargs.get("profile") != checked_binding.profile
                        or kwargs.get("profile_role") != checked_binding.profile_role
                        or kwargs.get("domain_receipt_digest")
                        != checked_binding.domain_receipt_digest
                        or kwargs.get("profile_receipt_digest")
                        != checked_binding.profile_receipt_digest
                        or kwargs.get("execution_snapshot_digest")
                        != checked_binding.execution_snapshot_digest
                        or kwargs.get("runtime_sha256")
                        != checked_binding.runtime_sha256
                        or kwargs.get("effective_phases")
                        != checked_binding.effective_phases
                    ):
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    record = {
                        "object": None,
                        "token": factory_token,
                        "binding": checked_binding,
                        "runtime_guard": runtime_guard,
                        "issuer": issue,
                        "card": metadata_kwargs_card(kwargs),
                        "state": "ACTIVE",
                        "recorder": None,
                        "session": None,
                        "strategy": None,
                        "session_gate": None,
                    }
                    return construct_metadata(record, kwargs)
                if action == "recorder":
                    require_issue_phase("BUILDING")
                    if len(values) != 1:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    metadata_record = exact_record(metadata_records, values[0])
                    if (
                        metadata_record.get("token") is not factory_token
                        or metadata_record.get("issuer") is not issue
                    ):
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    return construct_recorder(values[0])
                if action == "derive_metadata":
                    if len(values) != 5:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    recorder, source, initial, terminal, status = values
                    require_issue_phase(
                        "BUILDING" if status == "PRISTINE_BOUND" else "RUNNING"
                    )
                    recorder_record = exact_record(recorder_records, recorder)
                    source_record = exact_record(metadata_records, source)
                    if (
                        recorder_record.get("token") is not factory_token
                        or recorder_record.get("issuer") is not issue
                        or recorder_record.get("metadata") is not source
                        or source_record.get("state") != "ACTIVE"
                        or source_record.get("recorder") is not recorder
                    ):
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    _strict_sha(initial)
                    _strict_sha(terminal)
                    _strict_text(status, token=True)
                    zero = "0" * 64
                    source_status = object.__getattribute__(
                        source, "strategy_state_provenance_status"
                    )
                    source_initial = object.__getattribute__(
                        source, "strategy_state_initial_sha256"
                    )
                    source_terminal = object.__getattribute__(
                        source, "strategy_state_terminal_sha256"
                    )
                    if status == "PRISTINE_BOUND":
                        valid_transition = (
                            source_status == "FACTORY_PENDING"
                            and source_initial == zero
                            and source_terminal == zero
                            and initial != zero
                            and terminal == zero
                        )
                    elif status in (
                        "TERMINAL_OBSERVED", "TERMINAL_INVALID",
                        "PRE_RUN_INVALID",
                    ):
                        valid_transition = (
                            source_status == "PRISTINE_BOUND"
                            and source_initial == initial
                            and source_terminal == zero
                            and terminal != zero
                        )
                    else:
                        valid_transition = False
                    if not valid_transition:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    kwargs = {
                        "feature_id": source.feature_id,
                        "execution_context": source.execution_context,
                        "family": source.family,
                        "profile": source.profile,
                        "profile_role": source.profile_role,
                        "domain_receipt_digest": source.domain_receipt_digest,
                        "profile_receipt_digest": source.profile_receipt_digest,
                        "execution_snapshot_digest": source.execution_snapshot_digest,
                        "runtime_sha256": source.runtime_sha256,
                        "strategy_state_initial_sha256": initial,
                        "strategy_state_terminal_sha256": terminal,
                        "strategy_state_provenance_status": status,
                        "effective_phases": source.effective_phases,
                        "operation_budget": source.operation_budget,
                        "event_budget": source.event_budget,
                        "instrumentation_source_sha256": (
                            source.instrumentation_source_sha256
                        ),
                        "upstream": source.upstream,
                    }
                    record = {
                        **source_record,
                        "object": None,
                        "card": metadata_kwargs_card(kwargs),
                        "state": "ACTIVE",
                        "recorder": recorder,
                    }
                    value = construct_metadata(record, kwargs)
                    with lock:
                        source_record["state"] = "SUPERSEDED"
                        recorder_record["metadata"] = value
                    return value
                if action == "bind_session":
                    require_issue_phase("FACTORY_BOUND")
                    if len(values) != 5:
                        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                    session, strategy, recorder, observed_gate, checked_binding = values
                    recorder_record = exact_record(recorder_records, recorder)
                    if (
                        type(session) is not InstrumentedMappingSession
                        or session is not owner_session
                        or strategy is not root_strategy
                        or observed_gate is not session_gate
                        or checked_binding is not recorder_record.get("binding")
                        or recorder_record.get("token") is not factory_token
                        or recorder_record.get("issuer") is not issue
                        or recorder_record.get("session") is not None
                        or recorder_record.get("strategy") is not None
                    ):
                        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                    with lock:
                        for record in metadata_records.values():
                            if (
                                record.get("token") is factory_token
                                and record.get("issuer") is issue
                            ):
                                record["session"] = session
                                record["strategy"] = strategy
                                record["session_gate"] = session_gate
                        for record in recorder_records.values():
                            if (
                                record.get("token") is factory_token
                                and record.get("issuer") is issue
                            ):
                                record["session"] = session
                                record["strategy"] = strategy
                                record["session_gate"] = session_gate
                    return None
                if action == "recovery_recorder":
                    require_issue_phase("RUNNING")
                    if len(values) != 3:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    source_recorder, source_metadata, runtime_guard = values
                    recorder_record = exact_record(
                        recorder_records, source_recorder
                    )
                    metadata_record = exact_record(
                        metadata_records, source_metadata
                    )
                    if (
                        recorder_record.get("token") is not factory_token
                        or recorder_record.get("issuer") is not issue
                        or metadata_record.get("token") is not factory_token
                        or metadata_record.get("issuer") is not issue
                        or runtime_guard is not recorder_record.get("runtime_guard")
                        or recorder_record.get("session") is not owner_session
                        or recorder_record.get("strategy") is not root_strategy
                    ):
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    kwargs = {
                        name: object.__getattribute__(source_metadata, name)
                        for name in (
                            "feature_id", "execution_context", "family", "profile",
                            "profile_role", "domain_receipt_digest",
                            "profile_receipt_digest", "execution_snapshot_digest",
                            "runtime_sha256", "strategy_state_initial_sha256",
                            "strategy_state_terminal_sha256",
                            "strategy_state_provenance_status", "effective_phases",
                            "operation_budget", "event_budget",
                            "instrumentation_source_sha256", "upstream",
                        )
                    }
                    clone_record = {
                        **metadata_record,
                        "object": None,
                        "card": metadata_kwargs_card(kwargs),
                        "state": "ACTIVE",
                        "recorder": None,
                    }
                    cloned_metadata = construct_metadata(clone_record, kwargs)
                    recovery = construct_recorder(cloned_metadata)
                    recovery_record = exact_record(recorder_records, recovery)
                    recovery_record["session"] = recorder_record.get("session")
                    recovery_record["strategy"] = recorder_record.get("strategy")
                    recovery_record["session_gate"] = recorder_record.get(
                        "session_gate"
                    )
                    clone_record["session"] = recorder_record.get("session")
                    clone_record["strategy"] = recorder_record.get("strategy")
                    clone_record["session_gate"] = recorder_record.get(
                        "session_gate"
                    )
                    recovery.bind_runtime_guard(runtime_guard)
                    return recovery
                if action == "trace":
                    require_issue_phase("RUNNING")
                    if len(values) != 1:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    recorder = values[0]
                    recorder_record = exact_record(recorder_records, recorder)
                    existing_trace = recorder_record.get("trace")
                    if (
                        recorder_record.get("token") is not factory_token
                        or recorder_record.get("issuer") is not issue
                        or recorder_record.get("session") is not owner_session
                        or recorder_record.get("strategy") is not root_strategy
                        or object.__getattribute__(recorder, "halted") is not True
                    ):
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    if existing_trace is not None:
                        if existing_trace is not final_trace:
                            _fail("W2B_INSTRUMENT_TRACE_INVALID")
                        trace_record = exact_record(
                            trace_records, existing_trace
                        )
                        if (
                            trace_record.get("recorder") is not recorder
                            or object.__getattribute__(existing_trace, "metadata")
                            is not object.__getattribute__(recorder, "metadata")
                            or object.__getattribute__(
                                existing_trace, "operation_count"
                            ) != object.__getattribute__(
                                recorder, "operation_count"
                            )
                            or object.__getattribute__(existing_trace, "events")
                            != tuple(object.__getattribute__(recorder, "events"))
                            or object.__getattribute__(existing_trace, "halted")
                            is not object.__getattribute__(recorder, "halted")
                            or object.__getattribute__(
                                existing_trace, "terminal_reason"
                            ) != object.__getattribute__(
                                recorder, "terminal_reason"
                            )
                        ):
                            _fail("W2B_INSTRUMENT_TRACE_INVALID")
                        return existing_trace
                    pending = {"kind": "trace", "recorder": recorder}
                    push_pending(pending)
                    try:
                        value = InstrumentationTrace(
                            metadata=object.__getattribute__(recorder, "metadata"),
                            operation_count=object.__getattribute__(
                                recorder, "operation_count"
                            ),
                            events=tuple(object.__getattribute__(recorder, "events")),
                            halted=True,
                            terminal_reason=object.__getattribute__(
                                recorder, "terminal_reason"
                            ),
                        )
                    except BaseException:
                        pop_pending(pending, require_constructed=False)
                        raise
                    constructed = pop_pending(
                        pending, require_constructed=True
                    )
                    if constructed is not value:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    final_trace = value
                    return value
                if action == "result":
                    require_issue_phase("RUNNING")
                    if len(values) != 4:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    trace, strategy, exception_type, exception_digest = values
                    trace_record = exact_record(trace_records, trace)
                    existing_result = trace_record.get("result")
                    if (
                        trace_record.get("token") is not factory_token
                        or trace_record.get("issuer") is not issue
                        or trace_record.get("strategy") is not strategy
                        or trace_record.get("session") is not owner_session
                        or strategy is not root_strategy
                        or trace is not final_trace
                    ):
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    if existing_result is not None:
                        if existing_result is not final_result:
                            _fail("W2B_INSTRUMENT_TRACE_INVALID")
                        result_record = exact_record(
                            result_records, existing_result
                        )
                        if (
                            result_record.get("trace") is not trace
                            or result_record.get("strategy") is not strategy
                            or result_record.get("exception_type")
                            != exception_type
                            or result_record.get("exception_message_sha256")
                            != exception_digest
                        ):
                            _fail("W2B_INSTRUMENT_TRACE_INVALID")
                        return existing_result
                    pending = {
                        "kind": "result", "trace": trace,
                        "strategy": strategy,
                    }
                    push_pending(pending)
                    try:
                        value = InstrumentedRunResult(
                            trace=trace,
                            strategy=strategy,
                            exception_type=exception_type,
                            exception_message_sha256=exception_digest,
                        )
                    except BaseException:
                        pop_pending(pending, require_constructed=False)
                        raise
                    constructed = pop_pending(
                        pending, require_constructed=True
                    )
                    if constructed is not value:
                        _fail("W2B_INSTRUMENT_TRACE_INVALID")
                    final_result = value
                    return value
                _fail("W2B_INSTRUMENT_TRACE_INVALID")

            build_authority.__module__ = f"{__name__}.__integrity_gate__"
            strategy_gate.__module__ = f"{__name__}.__integrity_gate__"
            session_gate.__module__ = f"{__name__}.__integrity_gate__"
            issue.__module__ = f"{__name__}.__integrity_gate__"
            graph = graph_builder(
                binding,
                components,
                conditions,
                operation_budget=factory_kwargs["operation_budget"],
                event_budget=factory_kwargs["event_budget"],
                expected_instrumentation_sha256=(
                    factory_kwargs["expected_instrumentation_sha256"]
                ),
                strategy_options=factory_kwargs["strategy_options"],
                _factory_build_authority=build_authority,
                _factory_strategy_gate=strategy_gate,
                _factory_provenance_issue=issue,
            )
            if type(graph) is not tuple or len(graph) != 9:
                _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
            (
                strategy, recorder, binding, max_iterations,
                module_binding, helper_refs, runtime_guard,
                guard_identity, pristine_card,
            ) = graph
            if (
                type(recorder) is not _TraceRecorder
                or type(binding) is not ExecutionBinding
                or type(max_iterations) is not int
                or isinstance(max_iterations, bool)
                or type(module_binding) is not tuple
                or type(helper_refs) is not type(MappingProxyType({}))
                or not isinstance(runtime_guard, types.FunctionType)
                or not isinstance(guard_identity, types.FunctionType)
                or type(pristine_card) is not tuple
                or len(pristine_card) != 20
                or strategy is not pristine_card[0]
                or recorder is not pristine_card[1]
                or type(strategy) is not pristine_card[13]
            ):
                _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
            strategy_type = pristine_card[13]
            queue = pristine_card[2]
            modules = object.__getattribute__(strategy, "_tg_modules")
            kind = object.__getattribute__(strategy, "_tg_kind")
            database = object.__getattribute__(strategy, "dbf")
            if (
                type(strategy_type) is not type
                or type(modules) is not _RuntimeModules
                or type(kind) is not str
                or object.__getattribute__(strategy, "node_queue") is not queue
                or object.__getattribute__(strategy, "_tg_recorder") is not recorder
                or object.__getattribute__(strategy, "_tg_runtime_guard")
                is not runtime_guard
                or object.__getattribute__(strategy, "_tg_helpers")
                is not helper_refs
                or object.__getattribute__(recorder, "_runtime_guard")
                is not runtime_guard
            ):
                _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
            with lock:
                for issued, value in (
                    (issued_strategies, strategy),
                    (issued_recorders, recorder),
                    (issued_queues, queue),
                ):
                    if issued.get(id(value)) is not None:
                        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
            initial_digest = _verify_pristine_strategy_state_card(
                strategy, recorder, pristine_card
            )
            method_bindings = _strategy_method_bindings(strategy)
            configuration = _strategy_configuration_bytes(strategy)
            pristine_metadata = _copy_metadata(
                object.__getattribute__(recorder, "metadata")
            )
            if (
                pristine_metadata.strategy_state_provenance_status
                != "PRISTINE_BOUND"
            ):
                _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
            anchor_binding = _copy_and_validate_active_binding(binding)
            live_binding = _copy_and_validate_active_binding(binding)
            session = object.__new__(InstrumentedMappingSession)
            object.__setattr__(session, "strategy", strategy)
            object.__setattr__(session, "_recorder", recorder)
            object.__setattr__(session, "_binding", live_binding)
            object.__setattr__(session, "_max_iterations", max_iterations)
            object.__setattr__(session, "_strategy_type", strategy_type)
            object.__setattr__(session, "_database", database)
            object.__setattr__(session, "_node_queue", queue)
            object.__setattr__(session, "_modules", modules)
            object.__setattr__(session, "_kind", kind)
            object.__setattr__(session, "_method_bindings", method_bindings)
            object.__setattr__(session, "_configuration_bytes", configuration)
            object.__setattr__(session, "_module_binding", module_binding)
            object.__setattr__(session, "_helper_refs", helper_refs)
            object.__setattr__(session, "_runtime_guard", runtime_guard)
            object.__setattr__(session, "_guard_identity", guard_identity)
            record = (
                guard_identity, pristine_card, initial_digest,
                strategy, recorder, queue, anchor_binding, database, modules,
                kind, strategy_type, module_binding, helper_refs,
                method_bindings, configuration, max_iterations,
                pristine_metadata, runtime_guard, live_binding,
            )
            with lock:
                if id(session) in records:
                    _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                for issued, value in (
                    (issued_strategies, strategy),
                    (issued_recorders, recorder),
                    (issued_queues, queue),
                ):
                    if issued.get(id(value)) is not None:
                        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
                records[id(session)] = (
                    session, record, session_gate, issue
                )
                issued_strategies[id(strategy)] = strategy
                issued_recorders[id(recorder)] = recorder
                issued_queues[id(queue)] = queue
            session_gate("bind", session, strategy)
            issue("bind_session", session, strategy, recorder, session_gate, binding)
            committed = True
            return session
        except MappingInstrumentationError:
            raise
        except BaseException as error:
            raise MappingInstrumentationError(
                "W2B_INSTRUMENT_SESSION_REQUIRED"
            ) from error
        finally:
            if not committed and factory_token is not None:
                with lock:
                    owned_session_records = []
                    for key, entry in tuple(records.items()):
                        if (
                            type(entry) is tuple
                            and len(entry) == 4
                            and entry[3] is issue
                        ):
                            owned_session_records.append(entry[1])
                            del records[key]
                    for session_state in owned_session_records:
                        if type(session_state) is tuple and len(session_state) == 19:
                            for table, index in (
                                (issued_strategies, 3),
                                (issued_recorders, 4),
                                (issued_queues, 5),
                            ):
                                value = session_state[index]
                                if table.get(id(value)) is value:
                                    del table[id(value)]
                    owned_trace_ids = {
                        id(record.get("object"))
                        for record in trace_records.values()
                        if type(record) is dict
                        and record.get("token") is factory_token
                        and record.get("issuer") is issue
                    }
                    for table in (
                        metadata_records, recorder_records, trace_records,
                    ):
                        for key, record in tuple(table.items()):
                            if (
                                type(record) is dict
                                and record.get("token") is factory_token
                                and record.get("issuer") is issue
                            ):
                                del table[key]
                    for key, record in tuple(result_records.items()):
                        if (
                            type(record) is dict
                            and id(record.get("trace")) in owned_trace_ids
                        ):
                            del result_records[key]
                    for thread, stack in tuple(pending_by_thread.items()):
                        if type(stack) is list and any(
                            type(pending) is dict
                            and (
                                pending.get("issuer") is issue
                                or (
                                    type(pending.get("record")) is dict
                                    and pending["record"].get("token")
                                    is factory_token
                                )
                            )
                            for pending in stack
                        ):
                            del pending_by_thread[thread]
                    phase = "TERMINAL"
                    run_thread = None
                    root_depth = 0
                    child_strategies.clear()
                    consumed_children.clear()

    def public_factory(
        binding: object,
        components: object,
        conditions: object,
        *,
        operation_budget: object,
        event_budget: object,
        expected_instrumentation_sha256: object,
        strategy_options: Mapping[str, object] | None = None,
    ):
        return mint(
            binding,
            components,
            conditions,
            operation_budget=operation_budget,
            event_budget=event_budget,
            expected_instrumentation_sha256=expected_instrumentation_sha256,
            strategy_options=strategy_options,
        )

    provenance.__name__ = "_OPERATIONAL_PROVENANCE_AUTHORITY"
    provenance.__qualname__ = "_OPERATIONAL_PROVENANCE_AUTHORITY"
    provenance.__module__ = __name__
    session_record.__name__ = "_record"
    session_record.__qualname__ = "InstrumentedMappingSession._record"
    session_record.__module__ = __name__
    session_run.__name__ = "run"
    session_run.__qualname__ = "InstrumentedMappingSession.run"
    session_run.__module__ = __name__
    InstrumentedMappingSession._record = staticmethod(session_record)
    InstrumentedMappingSession.run = session_run
    public_factory.__name__ = "create_instrumented_mapping_session"
    public_factory.__qualname__ = "create_instrumented_mapping_session"
    public_factory.__module__ = __name__
    public_factory.__doc__ = (
        "Create one exact receipt-bound factory-owned mapping session."
    )
    return provenance, public_factory


TRACE_SCHEMA = "thermogar.wave2b.mapping.instrumentation.trace.v2"
EVENT_SCHEMA = "thermogar.wave2b.mapping.instrumentation.event.v1"
METADATA_SCHEMA = "thermogar.wave2b.mapping.instrumentation.metadata.v2"
INSTRUMENTATION_VERSION = "2026.08.26.1"
INSTRUMENTATION_SOURCE_PIN_SHA256 = "2683ba8a62d19e68908c695f950a8feca9d80520d48e41ad1d735cccfa967dba"
INSTRUMENTATION_SOURCE_PIN_NORMALIZATION = "SELF_PIN_LITERAL_ZEROED_V1"
PYCALPHAD_VERSION = "0.11.2"
PYCALPHAD_LICENSE_SHA256 = (
    "f7207933aed997b95769e636b4849e36fa40fe3cdae557a9c4e9d0a6dd48a000"
)

SUPPORTED_MAPPING_FEATURES = (
    "binary_phase_diagram",
    "multicomponent_isopleth",
    "ternary_phase_diagram",
)
SUPPORTED_FE_PROFILE_IDS = ("thermogar_patch", "upstream_original")
FE_BASELINE_PROFILE = None
STEEL_REQUIRED_PRODUCT_SCOPE = True
FE_EXCLUSION_DECISION_MADE = False
C15_EXCLUSION_DECISION_MADE = False
COUNTS_TOWARD_FEATURE_COVERAGE = False
ACCEPTANCE_CLAIM = False
PRODUCTION_USE = "DENIED"
EXECUTION_MODE = "INTERNAL_QUALIFICATION"

_STRATEGY_STATE_CARD_SCHEMA = "thermogar.wave2b.mapping.strategy-state.v2"
_STRATEGY_STATE_PROVENANCE_STATUSES = (
    "FACTORY_PENDING",
    "PRISTINE_BOUND",
    "TERMINAL_OBSERVED",
    "TERMINAL_INVALID",
    "PRE_RUN_INVALID",
    "MANUFACTURED_NOT_APPLICABLE",
)

_MAPPING_REQUEST_SCHEMAS = (
    "THERMOGAR-WAVE2B-MAPPING-REQUEST-1",
    "THERMOGAR-WAVE2B-MAPPING-REQUEST-V2-1",
)
_NUMPY_VERSION = "2.4.6"
_NUMPY_ORIGIN_CARD = MappingProxyType(
    {
        "relative": "numpy/__init__.py",
        "size": 27550,
        "sha256": "65d5e777b6d662ba19cb80800bef3eb999eda7aee51eea62c308feabf679dba4",
    }
)
_NUMPY_BINARY_ORIGIN_CARD = MappingProxyType(
    {
        "relative": "numpy/_core/_multiarray_umath.cp311-win_amd64.pyd",
        "size": 3703296,
        "sha256": "4fb4c5d62a6bd766eea716350eaf5396580e33cf7dc159e305488d1b7d72dad2",
    }
)
_NUMPY_CALLABLE_PINS = MappingProxyType(
    {
        "array": (
            "builtins", "builtin_function_or_method", "numpy", "array", "array",
            None,
            "f0d782f9d18dc54059ffc5c065bf58933a6e133e4313c50a2d1e58b9b7f103fd",
            "(object, dtype=None, *, copy=True, order='K', subok=False, ndmin=0, ndmax=0, like=None)",
            "builtins", "module",
        ),
        "allclose": (
            "numpy", "_ArrayFunctionDispatcher", "numpy", "allclose", "allclose",
            "b465040f50ce22cd18f0fbbea2640bf0227a0420464ee87693d386a2dab373f3",
            "904a3a61a35edc2e8dd57550fc9a0232df0f201b8a13d701303638ede2579476",
            "(a, b, rtol=1e-05, atol=1e-08, equal_nan=False)",
            "builtins", "NoneType",
        ),
        "amin": (
            "numpy", "_ArrayFunctionDispatcher", "numpy", "amin", "amin",
            "7953f72649e1ee0d58390d931be16aa62c6f884f4e369de5c3a379c3007a071e",
            "683854168553d8594a9932ba821f0905187a29c333da27c377d6ee55b8ba05fa",
            "(a, axis=None, out=None, keepdims=<no value>, initial=<no value>, where=<no value>)",
            "builtins", "NoneType",
        ),
        "amax": (
            "numpy", "_ArrayFunctionDispatcher", "numpy", "amax", "amax",
            "86e72fcba363da8913da9a84f19809874fc91b53cc4ac82726544b4c2e354a0c",
            "fc686d2b6c8e04fdbdf16149e83dbb46507394c550ca5d547f3b11c7bfab1dbb",
            "(a, axis=None, out=None, keepdims=<no value>, initial=<no value>, where=<no value>)",
            "builtins", "NoneType",
        ),
        "dot": (
            "numpy", "_ArrayFunctionDispatcher", "numpy", "dot", "dot",
            None,
            "b859b30020d449225f41dc9a3d4274c9c6efa7cefbc10cae714b548e0814aca3",
            "(a, b, out=None)",
            "builtins", "NoneType",
        ),
    }
)

OUTCOMES = ("ACCEPTED", "FAILED", "MERGED", "ABANDONED")

EVENT_KINDS = (
    "TRACE_STARTED",
    "OPERATION_STARTED",
    "OPERATION_ENDED",
    "SOLVER_INVOCATION",
    "SOLVER_RESULT",
    "DIRECTION_PROBE",
    "START_POINT",
    "START_POINT_SCAN",
    "NODE_QUEUE_TRANSITION",
    "DUPLICATE_MERGE",
    "ZPF_LINE_TRANSITION",
    "ZPF_RELATION",
    "INVARIANT_CHECK",
    "BACKTRACK",
    "ZPF_POINT_DELETED",
    "METASTABLE_LINE_DISCARD",
    "AXIS_TRANSITION",
    "TERMINATION",
    "ERROR",
    "BUDGET_EXHAUSTED",
)

# Closed trace authority.  The compatibility globals above remain public for
# callers that inspect scope, but constructors and serializers validate and
# consume the import-time closure snapshot of these exact values.
_TRACE_SCOPE_RULES = (
    (
        "INTERNAL_QUALIFICATION", "ni", "mc_ni_v2036",
        "RELEASE_CANDIDATE_PENDING_NE04",
    ),
    (
        "INTERNAL_QUALIFICATION", "al", "mc_al_v2037",
        "RELEASE_CANDIDATE_PENDING_NE04",
    ),
    (
        "INTERNAL_QUALIFICATION", "fe", "thermogar_patch",
        "EVALUATION_PROFILE",
    ),
    (
        "INTERNAL_QUALIFICATION", "fe", "upstream_original",
        "DIAGNOSTIC_CONTROL",
    ),
    (
        "MANUFACTURED_TEST_ONLY", "manufactured", "manufactured_hooks",
        "TEST_ONLY",
    ),
)
_CONTROL_EVENT_KINDS = (
    "TRACE_STARTED", "BUDGET_EXHAUSTED", "ERROR", "TERMINATION",
)
_CONTROL_EVENT_DETAIL_KEYS = MappingProxyType(
    {
        "TRACE_STARTED": ("instrumentation_version", "upstream_version"),
        "BUDGET_EXHAUSTED": (
            "attempted_unit_size", "event_budget", "operation_budget",
            "operation_count_at_exhaustion", "reason_code",
            "reserved_count", "retained_count",
        ),
        "ERROR": ("reason_code",),
        "TERMINATION_RUN": ("completion_claim", "reason_code"),
        "TERMINATION_SCOPE": ("completion_claim", "reason_code", "scope"),
    }
)
_CLAIM_DETAIL_KEY_MARKERS = (
    "acceptance", "claim", "complete", "completion", "coverage",
    "production", "release",
)

_UPSTREAM_SOURCE_PINS = (
    (
        "mapping/strategy/strategy_base.py",
        "85d60e0116952238b1e28dfb8c7c646d01162ceeeb240e173ea10e4a20842c49",
        31559,
    ),
    (
        "mapping/strategy/binary_strategy.py",
        "356a7727c316633606006ac40e0f641c23ca912d3bb81f0f12c154ba86fac1dc",
        15017,
    ),
    (
        "mapping/strategy/isopleth_strategy.py",
        "1248fe2ef03104cb5142364bb558f3815c4efdd80afa917167f3a35411433e18",
        20362,
    ),
    (
        "mapping/strategy/ternary_strategy.py",
        "f05a5ff73e0de88fc9dfd06a0b22887cc7e0c56689fde12f10f486456a2d0b03",
        20059,
    ),
    (
        "mapping/strategy/step_strategy.py",
        "6d50a17d4d41950ef233af08004be7a0db29d715985f1d774c7139e8c632d2d1",
        12257,
    ),
    (
        "mapping/strategy/strategy_data.py",
        "40e3aae9707336f33ada5875161d30fcc3ad13666a663ff2d884f2636d50bd6b",
        5710,
    ),
    (
        "mapping/starting_points.py",
        "7ceaa16ed10223919c58d8b9b825ead2104060f74e7bc4bfad52e612737c4fcb",
        1499,
    ),
    (
        "mapping/zpf_checks.py",
        "618e470a7c540b277f9f509ab8fe60a14f3bebf8a93cc537f5652d229d8b67eb",
        21184,
    ),
    (
        "mapping/zpf_equilibrium.py",
        "954048ef607c594cc43951abdee80b407ba0ce72952f46a8932bd8b3609565f4",
        17280,
    ),
    (
        "mapping/primitives.py",
        "7f843a83932268e7c5813423a6ea72fc3e055c366e54c7bce8325969b2b4c890",
        21223,
    ),
    (
        "mapping/utils.py",
        "4d5f2e94293e41037672387f96cb7d22c51c818ba968dc7e5bda1928ddff6646",
        5070,
    ),
)
UPSTREAM_SOURCE_PINS = tuple(
    MappingProxyType({"path": path, "sha256": digest, "size_bytes": size})
    for path, digest, size in _UPSTREAM_SOURCE_PINS
)

# Exact non-bytecode contents of the installed pycalphad 0.11.2 wheel.
# Mapping source pins above identify the small upstream control-flow ports;
# this package manifest closes every other Python/Cython/binary/data source.
_PYCALPHAD_PACKAGE_PINS = (
    ("pycalphad-0.11.2.dist-info/INSTALLER", "ceebae7b8927a3227e5303cf5e0f1f7b34bb542ad7250ac03fbcde36ec2f1508", 4),
    ("pycalphad-0.11.2.dist-info/licenses/LICENSE.txt", "f7207933aed997b95769e636b4849e36fa40fe3cdae557a9c4e9d0a6dd48a000", 1382),
    ("pycalphad-0.11.2.dist-info/METADATA", "bc456f766cd034c0d42c2240966a3e8b1795e051d4636f729f00eed8855d152e", 5137),
    ("pycalphad-0.11.2.dist-info/RECORD", "98b957f41eb399af7ad194daed91c3ef343a82894a5d54e17d59002d02379d52", 18560),
    ("pycalphad-0.11.2.dist-info/REQUESTED", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", 0),
    ("pycalphad-0.11.2.dist-info/top_level.txt", "1425abceafb2850a63088ac7a6a360d215957350107f9510c19a870dce1e33d8", 10),
    ("pycalphad-0.11.2.dist-info/WHEEL", "5c75cc289537ca8561d596a70574c9e5b0c66faee8118b45d52e9b77c6b88b32", 101),
    ("pycalphad/__init__.py", "08ea9d333b2c24a227aba4f00b80cd79c15e5096056c1976e7b75ce48d209ac4", 1693),
    ("pycalphad/codegen/__init__.py", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", 0),
    ("pycalphad/codegen/phase_record_factory.py", "227bcc476f17984297fc6a9c2e963169bebd3f4c77bd6101fb5b2f4a7b90dd93", 3769),
    ("pycalphad/codegen/sympydiff_utils.py", "de7f0a22cd730d640cf60b662fa6836e4bc20a2ab9a72e3acf8c87b1b9ae51a0", 9257),
    ("pycalphad/core/__init__.py", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", 0),
    ("pycalphad/core/cache.py", "7579546d84338d7b3541bbaba07c067b7f237193e3f0083a49f398a49c219cfb", 7723),
    ("pycalphad/core/calculate.py", "c3f15f40c52508562d6b7017c98c4afe4a36da0ba402c8b33c974e1dd95f7180", 32900),
    ("pycalphad/core/composition_set.cp311-win_amd64.pyd", "6ed26b03ef93eb23889bcb4b49db64b0aed11612220e8015a0f609962ac2d04e", 161280),
    ("pycalphad/core/composition_set.cpp", "fa5b7871f3c6c9f680a7964e1e981ba87b0da47bbbcdde383ff9f69c09b9a219", 1334716),
    ("pycalphad/core/composition_set.pxd", "09d21daaa15922e1c6b779d18c507cd5af8a570b16bafc15a567cbc326fc21a4", 743),
    ("pycalphad/core/composition_set.pyx", "7c9f789243f4edf103f9a38e24d584e81a256a517a6d08fdd0ddd93a269316a0", 3988),
    ("pycalphad/core/conditions.py", "52ccd457605c10188352685192b79771a8b48ffed1dbd96df584a8abf43113b4", 6422),
    ("pycalphad/core/constants.py", "cc96a41930688c7c5d60086cc5a06759631264d9c9a3d6a0acce4fff9ef7f206", 756),
    ("pycalphad/core/constraints.py", "38dcb98fcd70b8a067565858aa9bd09246d3f80ab8c771d8bf8dff20c4f4f89e", 2308),
    ("pycalphad/core/eqsolver.cp311-win_amd64.pyd", "eae153e8e73f34dda4ae931eb2e03893ae6704348dcfd658abcd8c2ba60abaaf", 210944),
    ("pycalphad/core/eqsolver.cpp", "e440455febc2dce9c7ccf844fadb82f3f13109d42d14efe09b8f7ad5c7bbc4ca", 1563678),
    ("pycalphad/core/eqsolver.pyx", "83ee635ea8b7ee16b0e79cde7f2a658b3bdaaa26619f408e6b53732a7797c102", 15404),
    ("pycalphad/core/equilibrium.py", "939696bd5f7a64dcde08591de66828988a8eb45964c3f9ebc1d74686301fdbb8", 4304),
    ("pycalphad/core/errors.py", "533b6c7da30a5e6466dc0f025d3df99a16d1aacee40b836c96e4a7ab85b9b40f", 410),
    ("pycalphad/core/halton.py", "c13e0a9e34766d469e51ab6c910bd0ccbf05f4bebf23b05974e3c2264c816aae", 8140),
    ("pycalphad/core/hyperplane.cp311-win_amd64.pyd", "bc506298e3fcbfebf3fe1c3a048052c10bd28a7ea1431efa1849645588eee6d6", 165888),
    ("pycalphad/core/hyperplane.cpp", "83876317053f09ce2c41d95a9219b0f788ba420a0eac7a828f32d221ff2ebdb6", 1360946),
    ("pycalphad/core/hyperplane.pxd", "e2d6cbb7977f84ef4247387fb3cc062cd8e5483dede1f6a70f0b7a438d3bf169", 494),
    ("pycalphad/core/hyperplane.pyx", "8a3e87d468a2a18b1ffde790effc759e2e35f8db548ec06d87108036348e0471", 15546),
    ("pycalphad/core/light_dataset.py", "1c637a5e95ee680b17f92508bf3a86ca2ec5c9410d3f221a1b810a6181ab6ff3", 3504),
    ("pycalphad/core/lower_convex_hull.py", "8c144fbb1b78ba5e1e01269c7dee4bae5f549b6b82d4471e94b3ed9ad8e6df8e", 9810),
    ("pycalphad/core/minimizer.cp311-win_amd64.pyd", "50b38aad1ddc3564442b0427a483c20c81470feed43cd2028697bed1724fd74e", 465408),
    ("pycalphad/core/minimizer.cpp", "000690f24f43d0c2f9a14fc6bb29b030e724cb9a0be37cb3ba6ff1a369990d0d", 2828610),
    ("pycalphad/core/minimizer.pxd", "1adbd2498a88d5d8ecfe7776189321f55c44f4bceadbec3fe7833fe5791b7058", 1868),
    ("pycalphad/core/minimizer.pyx", "98ddf63bd9181555bba9a4148601b814d0de7948ed1f5f8c8824370b2d7a42ce", 65407),
    ("pycalphad/core/phase_rec.cp311-win_amd64.pyd", "a1d0f50f95ec8ce9ad0b47f4eceec06618c93883fdd76f4d7745880442e8d887", 273408),
    ("pycalphad/core/phase_rec.cpp", "356efd3d79c07971aa1b0c5522d5247b581879cae91b55f2994f7ee954dd7c77", 1916896),
    ("pycalphad/core/phase_rec.pxd", "788adb7e5ba8811948fe56783fa890ad20fc6ceb7bf19c9ffc25d408b0293ede", 4565),
    ("pycalphad/core/phase_rec.pyx", "35a218961d15f452fbb7c11e71da1619822a9a78ba9dd2c8d33eebc5e1e945bc", 21254),
    ("pycalphad/core/polytope.py", "dcb613af1d661030710c75d9d1838653f70e546e014af531a07573928cae4154", 7825),
    ("pycalphad/core/solver.py", "308b844ad74929b7d46c093a197006167e0a2e88037d657ab5e3af667fdc2608", 9983),
    ("pycalphad/core/starting_point.py", "2e4376dae79e044547d2d24d6a8e158bdeb561a4c9cd7bdc01557ff847660cf0", 5080),
    ("pycalphad/core/utils.py", "1705991a0984401993805e7231278b1005ff7d1da984704132d28e163d3af258", 22838),
    ("pycalphad/core/workspace.py", "b567955bc03fc2d9977976c02abefbed3221e1ddda2e91662ad5a81726a31a4d", 27628),
    ("pycalphad/io/__init__.py", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", 0),
    ("pycalphad/io/cs_dat.py", "1ce276329906e2c2dbeb903fb3eebc600034d5168d3eaa4ae2fe5d3c8b5deaad", 59904),
    ("pycalphad/io/database.py", "d17626502e4f8e18aeb2152fe68091de05d2885cf5b732d376cd1635e7e5893e", 18750),
    ("pycalphad/io/grammar.py", "97bcbcf07c551ba23c9e3341f65872b3aae281a578874eb25ea12f7010da9036", 1273),
    ("pycalphad/io/tdb_keywords.py", "6b2e4111297f36a127041e5dd21076c82bfcc373405c6c57b78993438fc2c424", 3770),
    ("pycalphad/io/tdb.py", "29dba002760e4a7602d785624d3ec49a65a1bf8123bed0c4138e92678543f837", 51310),
    ("pycalphad/mapping/__init__.py", "0cf3c1e15518fa5de87b6850cb36c83e97e60fca11b0657a766fd098de5e7a60", 378),
    ("pycalphad/mapping/compat_api.py", "08effd81918f68584169badd07128c94a469e909ab26cd319e7e9bc16cf6ec0f", 5116),
    ("pycalphad/mapping/plotting.py", "fa7be6f1a2afcf6cccee3f90c1eddc0c8865d6580cb1d548e7bad0eef50d5992", 15554),
    ("pycalphad/mapping/primitives.py", "7f843a83932268e7c5813423a6ea72fc3e055c366e54c7bce8325969b2b4c890", 21223),
    ("pycalphad/mapping/starting_points.py", "7ceaa16ed10223919c58d8b9b825ead2104060f74e7bc4bfad52e612737c4fcb", 1499),
    ("pycalphad/mapping/strategy/__init__.py", "da55177af0ace76b05b4f16bcd122bf496eba6991bd2bdd6096bb6ae45537761", 352),
    ("pycalphad/mapping/strategy/binary_strategy.py", "356a7727c316633606006ac40e0f641c23ca912d3bb81f0f12c154ba86fac1dc", 15017),
    ("pycalphad/mapping/strategy/isopleth_strategy.py", "1248fe2ef03104cb5142364bb558f3815c4efdd80afa917167f3a35411433e18", 20362),
    ("pycalphad/mapping/strategy/step_strategy.py", "6d50a17d4d41950ef233af08004be7a0db29d715985f1d774c7139e8c632d2d1", 12257),
    ("pycalphad/mapping/strategy/strategy_base.py", "85d60e0116952238b1e28dfb8c7c646d01162ceeeb240e173ea10e4a20842c49", 31559),
    ("pycalphad/mapping/strategy/strategy_data.py", "40e3aae9707336f33ada5875161d30fcc3ad13666a663ff2d884f2636d50bd6b", 5710),
    ("pycalphad/mapping/strategy/ternary_strategy.py", "f05a5ff73e0de88fc9dfd06a0b22887cc7e0c56689fde12f10f486456a2d0b03", 20059),
    ("pycalphad/mapping/utils.py", "4d5f2e94293e41037672387f96cb7d22c51c818ba968dc7e5bda1928ddff6646", 5070),
    ("pycalphad/mapping/zpf_checks.py", "618e470a7c540b277f9f509ab8fe60a14f3bebf8a93cc537f5652d229d8b67eb", 21184),
    ("pycalphad/mapping/zpf_equilibrium.py", "954048ef607c594cc43951abdee80b407ba0ce72952f46a8932bd8b3609565f4", 17280),
    ("pycalphad/model.py", "c917535133104a138635547343d7b7ec0348bfe127b4b468fc207cd546bc5f4d", 86936),
    ("pycalphad/models/__init__.py", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", 0),
    ("pycalphad/models/model_mqmqa.py", "c02d3be710f689967099aecd97404bfc6dcf4543eb97ed37b97d933574c99757", 35364),
    ("pycalphad/plot/__init__.py", "b08a51e3d7c1b0aac364477098efec64b7c5d07b7583fb9b4a53d8902518ef41", 56),
    ("pycalphad/plot/binary/__init__.py", "e919bc8b39d53f0f22c39216b9482498b4bca2f87d96ff9457dad17e67a5ba1a", 75),
    ("pycalphad/plot/binary/compsets.py", "5f6635333caaed302ce8b33ea91771c089254a0648089f655d86de2cea00bbbe", 10792),
    ("pycalphad/plot/binary/map.py", "88248423d2a8bca43d1e0847cf70597245f1a4c8600bdd2b8a0e58bc6ddd8646", 8712),
    ("pycalphad/plot/binary/plot.py", "beb8a7aea5dbfb6edeb1226e08ca139f039f3faaf4f824f92149494aec36c437", 4701),
    ("pycalphad/plot/binary/zpf_boundary_sets.py", "c85b6ee20edf10d5d7b686b29613976947b41775e45b875504c132e60e3487e5", 11767),
    ("pycalphad/plot/eqplot.py", "37746163e248edeefc916a798a6dffcdf21dbf717c02e27f17d08ba909e9279b", 9523),
    ("pycalphad/plot/ternary.py", "4db16dbefcedd10022e6832ad02cd80e62a0c3f255eedfe7c2349ca9739292c8", 2225),
    ("pycalphad/plot/triangular.py", "61b7c2271f7b834816577ecb751a283ae4e6f896f23cc67a798aecb786d82c0e", 7854),
    ("pycalphad/plot/utils.py", "9e06dbae8387c61585f59b5071a3b8747b338def89d63a3912951ca35d24ec8d", 1708),
    ("pycalphad/property_framework/__init__.py", "2afd9f000ebd92acaeea0ba138b53f36ee10a0ca10fb2059e4761f7d4e295d5a", 353),
    ("pycalphad/property_framework/computed_property.py", "b0b35ccc1c1e89c5d0275a9e9836a9486362fbac2cb3a14e44820a2d35a3ca20", 13162),
    ("pycalphad/property_framework/metaproperties.py", "4a8aac4dbc7b1c6285790e9b6fda40346824e5dbd7d1a427ca65313c8e5ec440", 16498),
    ("pycalphad/property_framework/types.py", "d816c78073f8351a794c29038fcb1cf66dd9c019ba217ebac9911fa9c56794be", 1556),
    ("pycalphad/property_framework/tzero.py", "b121dd57858cf23ed2ad99ace61d5ca55f00f960fc0508667b8721b9918c0c56", 5108),
    ("pycalphad/property_framework/units.py", "1a33eda4f9ff8023f49ae2436688ac014fa76f1b9892aa00974d1d7d940acb3d", 5125),
    ("pycalphad/tests/__init__.py", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", 0),
    ("pycalphad/tests/databases/__init__.py", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", 0),
    ("pycalphad/tests/databases/2026-Dixon-Na-K-Cl-I.dat", "d1c4b5f52fba2e9c326da1a7ea1ad26b6f9db4d0f02646ea00088ce84c1d6f06", 30799),
    ("pycalphad/tests/databases/al_parameter.tdb", "6c251b8f7c0f31c910926e33c2c1d00b83318f657667cef863af368dedd5f601", 258),
    ("pycalphad/tests/databases/Al-Cu-Y.tdb", "8e8eee7e4149b385600f2e83225cda74a2bfdb29e2f01393e063c1e3957b1977", 17170),
    ("pycalphad/tests/databases/Al-Fe_sundman2009.tdb", "2c1c57431a231aabc384ce1154aea857c1499dd6771bb50349884dc70bbe224e", 23116),
    ("pycalphad/tests/databases/Al-Mg_Zhong.tdb", "602d00e98142eb25668436783ada88ac0e855f4aa869254905176a5f7b0241d2", 4775),
    ("pycalphad/tests/databases/al2o3_nd2o3_zro2.tdb", "9f8ff7ad2e3a211ec09a674e6020cc5306d78d4122319b7760c32877c66e8b94", 20042),
    ("pycalphad/tests/databases/alcfe_b2.tdb", "16614392a94c6158ee1aabd99e5de1994c9ef08cbd7bdd1859892392491f9e39", 6729),
    ("pycalphad/tests/databases/alcocrni.tdb", "f09d7f5ff556bad49646fdd2df0e5f2a61ba9365d7a66e7f07b352ce5ef30c2c", 61233),
    ("pycalphad/tests/databases/alcrni.tdb", "000e9e00d0b501b77a583f5c64e93cea1cf8658d38fb5e78afd6d7e9bce6d7de", 13577),
    ("pycalphad/tests/databases/alfe.tdb", "ef44949f74f6dde1921a8c3b30530649faf67acf75585a2916be383c88cbf071", 9038),
    ("pycalphad/tests/databases/alfeo.tdb", "d9ae5da1caa507ed47063771b639480b233a28f23dcc4bfbed6b37ae0f98d51e", 41875),
    ("pycalphad/tests/databases/alni_dupin_2001.tdb", "e77f53ef954614a3d471d39906f1f175de1b14eaa57f64f70fdf369c9424f392", 12291),
    ("pycalphad/tests/databases/alni_tough_chempot.tdb", "82c98e649603d71b26b0ab3effeb74d263c9d0dbc5d0f2062d51a7d8cb320572", 12650),
    ("pycalphad/tests/databases/alnifcc4sl.tdb", "50f36c096ca300876719dbad28f1a0ae5ff4ab16b64dc36e7f0496f9b8584ea6", 11081),
    ("pycalphad/tests/databases/alnipt.tdb", "cbe3312557e9da1e3d22bd1b79fe58c3034d417d2be5fbdffdb14ac9fb045023", 43702),
    ("pycalphad/tests/databases/alzn_mey.tdb", "36591722726fdaeb1e08b90da913e2533611f30ddd81469170e3f8c3c7f09568", 4972),
    ("pycalphad/tests/databases/AuSn-13Don.tdb", "0dee9c06782e47fffacb0e21fd9ea5d57419362adbb22208c02b7266a44b7705", 11429),
    ("pycalphad/tests/databases/cfe_broshe.tdb", "9db36c07371f16722ebbbf45096570776fbfd1336c3fa72259abc8600ec52a0e", 49286),
    ("pycalphad/tests/databases/COST507.tdb", "5b321bc8cf0eec17c1f204f72e82d048d864756c62ede84fb768b277def823ba", 305608),
    ("pycalphad/tests/databases/CoV-20Wan.tdb", "4c3b320e1a55ca3e9a20663b33e530488568edb246453d50aa11f59abb5f11ee", 11416),
    ("pycalphad/tests/databases/Cr-Fe-Ni_shallow_bcc.tdb", "e39dfda7b0f83e764dd75d2e2a0c47d8ae2504640fe803bfc513277c357f95e6", 3056),
    ("pycalphad/tests/databases/crfe_bcc_magnetic.tdb", "af0177e6c9931a66f73c3f061d8b691929a004ad99128b1a9710f94d53a2703b", 1134),
    ("pycalphad/tests/databases/CrFeNb_Jacob2016.tdb", "7ba606ffc16cbc0099a0af4891ca48675fb62ff5b1cd80d5ebf1bc212e795ad2", 14759),
    ("pycalphad/tests/databases/crtiv_ghosh.tdb", "8131bf968a193ca49d562ea16364947d2ae2c1156d1a66b22f8029972c5aff8f", 13663),
    ("pycalphad/tests/databases/cumg_parameters.tdb", "3d0c03ec75ded5f9b44fedd822d2cb07d2b453bb5383a9848c9022536c3eb5a8", 6652),
    ("pycalphad/tests/databases/cumg.tdb", "fc4b446dbcfb9da34efff79d5b5a41183ad0b2f960f551b647a1720a317ee64f", 4309),
    ("pycalphad/tests/databases/cuo.tdb", "0944ae3ad82b94402f2035c8beefdeacba44d01d0c25994d17e1d5c4950c1ffc", 5638),
    ("pycalphad/tests/databases/diffusion.tdb", "2317393142b4600e94e84d03dd305ca89ebe2b5e51af7738c355471cc48d7faf", 4917),
    ("pycalphad/tests/databases/femn.tdb", "a080b811a8545693beee40e09fe572e98c77e35dda579ff9a86c0ce278506b42", 4550),
    ("pycalphad/tests/databases/femns.tdb", "567e163f50363647407759118435f215af1e299401d42a7ec27f227af1d71cd6", 4211),
    ("pycalphad/tests/databases/FeNi_deep_branching.tdb", "9714f61a4b0ca6148aac720fcd97fe37c33fabbca71e589c300cb0e16545804e", 23198),
    ("pycalphad/tests/databases/gibbs_phase_rule.tdb", "2f729dc48a4e88b1baf320e47da5c9b146fc14ebe0ef709c896280940dbfbd17", 4109),
    ("pycalphad/tests/databases/issue43.tdb", "5ced5deaf0c278f83a7b2bbb4071ae9dea4d65d003457b5c141e0cec301525ad", 5107),
    ("pycalphad/tests/databases/Kaye_Pd-Ru-Tc-Mo.dat", "b6ad1d320b5be265548de5fe56599e0e557c9914616de593c90f5eaab0d8b3ef", 20355),
    ("pycalphad/tests/databases/KF-NIF2_switched.dat", "555880f4a475126237382e62eed441cd6ce6f43125d7365d9bbb73db3b26a51c", 9545),
    ("pycalphad/tests/databases/mc_fecocrnbti.tdb", "9a45cacdd5027ce94fc94765827aa540095d731a65a9bb5134e95dd43b710ae1", 55672),
    ("pycalphad/tests/databases/MQMQA-tern-tests.dat", "1085587af3698c6d46f5f3417d06ff803b76e3118e9bf4b1ec78000dcb920589", 15519),
    ("pycalphad/tests/databases/nbre_liu.tdb", "17aaf70ffadc55dbec9d94932ee95e1a6b9e450db2b57abc2fae5ef1a5fcab30", 6543),
    ("pycalphad/tests/databases/Ocadiz-Flores.dat", "bfce797b213674aa33012e86ded8694b10c040f95a7ba779e4f7c2007e69676e", 13114),
    ("pycalphad/tests/databases/parameter_filter_test.tdb", "00e194141857a34db10d0ae06e5ddcad288c4ac2548df52e97f1be4e61ea5570", 824),
    ("pycalphad/tests/databases/pbsn.tdb", "e9f4bdd926faa8240138e9a23d3500dbd0247de9c23d7581b9a3abbcba0237e5", 4557),
    ("pycalphad/tests/databases/rose.tdb", "657d1792d27877f4c287e335dacb040c16251624e0829d3bfd6d8aecfeee9fbf", 24488),
    ("pycalphad/tests/databases/Shishin_Fe-Sb-O-S_slag.dat", "9feef8188a6c41813b64c635657cd4d227bc89e4352726b4ce84cfc48df94d4e", 5484),
    ("pycalphad/tests/databases/Viitala.dat", "a6b3484ef486a6c71e99ae2410912f372d16f2d457dabcf313c4c1bd11bbf3cc", 18967),
    ("pycalphad/tests/databases/zrlayalo.tdb", "92441365543d0de8fc9749aed16cfda6217d15ed84cc57eb09a2fc9ffebb4adb", 30629),
    ("pycalphad/tests/fixtures.py", "ad3ba01392593ec87699b7fe4090fe15ac2ebe5b47153c7ea09c9431fd13eddc", 1556),
    ("pycalphad/tests/test_binary_mapping.py", "2c3717b01451eb44d7744378927c56b4bf369deb2cd7441f13a39cceab67095c", 8547),
    ("pycalphad/tests/test_calculate.py", "8d878c65e43587d073e283378e438619281524b463f86b6f5c85564e8eb24014", 23516),
    ("pycalphad/tests/test_codegen.py", "5b34953f0f04a5dd7332fc0671ac6f984e65faabfccae3a8b319f1ef38a9ea5e", 6082),
    ("pycalphad/tests/test_database.py", "242456e1569293af9c2719e0b6df37a57629ee200c700a9cd6ce3949aecc2367", 50867),
    ("pycalphad/tests/test_energy.py", "483d42a94ecceed96a10b717caea18cc470d4cf1b5d18d98aaefb5f4c75681a1", 61605),
    ("pycalphad/tests/test_equilibrium.py", "2c0aeea6744ed510caa825480a94f1913f1368ac0281b167297d30e880473b72", 52751),
    ("pycalphad/tests/test_mapping_strategy.py", "dbcd286cbb4c966fba31c2fe99d860eb129175919e41913dd8f3c91ee8612699", 32929),
    ("pycalphad/tests/test_mapping_zpf_checks.py", "b0ce93f8b08d93b5379a56649eae87a4fc423a6bcfd865e9cb1e7f0d2a63d158", 11913),
    ("pycalphad/tests/test_model.py", "b17dcbe043ab1b1cf38c4cf05d017b13852924658e6da94a5bde13dc4d68b870", 11387),
    ("pycalphad/tests/test_plot.py", "f2caced8e58568f6d048443c92bee916a25901f5a796533457b551d3735209af", 1754),
    ("pycalphad/tests/test_property_framework.py", "402805a309e584cbc2ca732f76abc880924587db02b7c82e78a50f1326e157a8", 11431),
    ("pycalphad/tests/test_utils.py", "65d64fbff71863856d6058a2d24445016189ca3f0ad19899161b4fd7a74f685b", 26452),
    ("pycalphad/tests/test_variables.py", "9d47a4414cd7e26b4f07bf6ea324d046dbb35dc39e41e8a2e8634270c00e1fef", 5288),
    ("pycalphad/tests/test_workspace.py", "9754940e731adac840446e5fb13e471a7b7f16daeb94b48e2b2e7784a79a53a5", 26194),
    ("pycalphad/variables.py", "a65dfdb3d669d93b4293ee53eef9fa0981db38566c74a0a239883108f0844224", 38446),
)
PYCALPHAD_PACKAGE_PINS = tuple(
    MappingProxyType({"path": path, "sha256": digest, "size_bytes": size})
    for path, digest, size in _PYCALPHAD_PACKAGE_PINS
)

_RUNTIME_PRIMITIVE_MODULES = (
    "pycalphad",
    "pycalphad.io.database",
    "pycalphad.core.calculate",
    "pycalphad.core.composition_set",
    "pycalphad.core.constants",
    "pycalphad.core.solver",
    "pycalphad.core.workspace",
    "pycalphad.mapping.primitives",
    "pycalphad.mapping.starting_points",
    "pycalphad.mapping.strategy.binary_strategy",
    "pycalphad.mapping.strategy.isopleth_strategy",
    "pycalphad.mapping.strategy.step_strategy",
    "pycalphad.mapping.strategy.strategy_base",
    "pycalphad.mapping.strategy.strategy_data",
    "pycalphad.mapping.strategy.ternary_strategy",
    "pycalphad.mapping.utils",
    "pycalphad.mapping.zpf_checks",
    "pycalphad.mapping.zpf_equilibrium",
)
_RUNTIME_TRANSIENT_BINDING_EXCLUSIONS = MappingProxyType(
    {
        # pycalphad's package import leaves the final pkgutil.iter_modules()
        # loop variables behind.  In particular, _name varies with sys.path
        # spelling/order and is never consumed by the mapping call graph.
        "pycalphad": (
            "_discovered_plugins", "_finder", "_ispkg", "_name",
        ),
    }
)
_RUNTIME_CRITICAL_LOCATORS = (
    "pycalphad:Database",
    "pycalphad:Workspace",
    "pycalphad:calculate",
    "pycalphad.io.database:Database",
    "pycalphad.core.calculate:calculate",
    "pycalphad.core.composition_set:CompositionSet",
    "pycalphad.core.solver:Solver",
    "pycalphad.core.solver:Solver.solve",
    "pycalphad.core.workspace:Workspace",
    "pycalphad.mapping.primitives:Node",
    "pycalphad.mapping.primitives:NodeQueue",
    "pycalphad.mapping.primitives:Point",
    "pycalphad.mapping.primitives:ZPFLine",
    "pycalphad.mapping.starting_points:Workspace",
    "pycalphad.mapping.starting_points:point_from_equilibrium",
    "pycalphad.mapping.strategy.binary_strategy:BinaryStrategy",
    "pycalphad.mapping.strategy.binary_strategy:BinaryStrategy._determine_start_direction",
    "pycalphad.mapping.strategy.isopleth_strategy:IsoplethStrategy",
    "pycalphad.mapping.strategy.isopleth_strategy:IsoplethStrategy._determine_start_direction",
    "pycalphad.mapping.strategy.step_strategy:StepStrategy",
    "pycalphad.mapping.strategy.step_strategy:StepStrategy.generate_automatic_starting_points",
    "pycalphad.mapping.strategy.strategy_base:MapStrategy",
    "pycalphad.mapping.strategy.strategy_base:MapStrategy.iterate",
    "pycalphad.mapping.strategy.strategy_base:MapStrategy._process_new_node",
    "pycalphad.mapping.strategy.ternary_strategy:TernaryStrategy",
    "pycalphad.mapping.strategy.ternary_strategy:TernaryStrategy._determine_start_direction",
    "pycalphad.mapping.zpf_equilibrium:CompositionSet",
    "pycalphad.mapping.zpf_equilibrium:Solver",
    "pycalphad.mapping.zpf_equilibrium:calculate",
)
RUNTIME_PRIMITIVE_MANIFEST_SHA256 = "c2f1d98e65829b2f2c04ec77ca6d196b85c4ca3d7d7b8e3b9dcdcd375feba2ea"
_RUNTIME_CRITICAL_PINS: tuple[tuple[str, str], ...] = (
    ("pycalphad:Database", "6a763785a9494221e6a06a078dc8f9e3d5c30e8067c8a297f00e708e07704959"),
    ("pycalphad:Workspace", "61d0191839ab463a6a61741bc849311140ba3f81921a29fd1349eed80a1399b3"),
    ("pycalphad:calculate", "20aba4cdf426adfab43bcc81e1e10581d247444160811db6a37e325cf31bef62"),
    ("pycalphad.io.database:Database", "6a763785a9494221e6a06a078dc8f9e3d5c30e8067c8a297f00e708e07704959"),
    ("pycalphad.core.calculate:calculate", "20aba4cdf426adfab43bcc81e1e10581d247444160811db6a37e325cf31bef62"),
    ("pycalphad.core.composition_set:CompositionSet", "dcc836c16787f12db73bc8d6051f8935a5ff70d3f585d7403db8f747a5eb8f0d"),
    ("pycalphad.core.solver:Solver", "4fc0aa4028476a785a0930f67bf51e1b1ac30cdbdf2da2b4253806f242dbe57b"),
    ("pycalphad.core.solver:Solver.solve", "c974b2072e249d222de5b4a3cf7643c55009569cba4d7bcabb44a7506cee0e55"),
    ("pycalphad.core.workspace:Workspace", "61d0191839ab463a6a61741bc849311140ba3f81921a29fd1349eed80a1399b3"),
    ("pycalphad.mapping.primitives:Node", "c588fcc9ea8fa543fd0ff3f4e245f4b3c416858e33826cb902b50e3c3daa94c8"),
    ("pycalphad.mapping.primitives:NodeQueue", "04ac5c0aa84871b7f0c686fbf02fac3648608d3a3aa8023efa39cebf592833df"),
    ("pycalphad.mapping.primitives:Point", "dd07ad7f68609243e3d277558df493df66ce9ab907f4e62f9e834c03654065f7"),
    ("pycalphad.mapping.primitives:ZPFLine", "7087f8ab2c88c52cd1e128161f00b05ca78080a1a701c5e2906eb03e6b978c9e"),
    ("pycalphad.mapping.starting_points:Workspace", "61d0191839ab463a6a61741bc849311140ba3f81921a29fd1349eed80a1399b3"),
    ("pycalphad.mapping.starting_points:point_from_equilibrium", "f81f18bb6703cd01bb071ba6cd9c23e18a9d9dc493c563790c2550af872187a1"),
    ("pycalphad.mapping.strategy.binary_strategy:BinaryStrategy", "f035e6923c838709d06598c1ae1f5e6c1dc0b8b2eaf92e3ba93fef34ddb3d971"),
    ("pycalphad.mapping.strategy.binary_strategy:BinaryStrategy._determine_start_direction", "e20b8891aa41852fdb5fceadfc02c70ab8fa023a426cf06b6b28e7e5e46b7752"),
    ("pycalphad.mapping.strategy.isopleth_strategy:IsoplethStrategy", "a130a7bba7d92be4c47f49c76aa4c5b6018b61a61b8923583f62325cd689c8a9"),
    ("pycalphad.mapping.strategy.isopleth_strategy:IsoplethStrategy._determine_start_direction", "82e47428dc5807eeef50ae55d73f7f168dda55cf77b35dd4ec7d0f76f367b5c4"),
    ("pycalphad.mapping.strategy.step_strategy:StepStrategy", "fc62ce6e9ef69af570e6fb9ab0654fe94452193780140e7978b7f04992b90afc"),
    ("pycalphad.mapping.strategy.step_strategy:StepStrategy.generate_automatic_starting_points", "c51a67de68c646ccd28508fc0c12c6843ae7306e947fa699e1d6d7858bdf726c"),
    ("pycalphad.mapping.strategy.strategy_base:MapStrategy", "ac58f6a07fab6702a2f565b2ee5d749d4da57f86d939c3c7f61afe99c1f728ce"),
    ("pycalphad.mapping.strategy.strategy_base:MapStrategy.iterate", "46bfc0eda01a78d605587f24bd083d1a1b7fe8bf33033844ac5286235313a574"),
    ("pycalphad.mapping.strategy.strategy_base:MapStrategy._process_new_node", "d7807cc8db5989f96fb44f480ac5063e1d5eff5a20f90a3f4cfe430c28cd4dae"),
    ("pycalphad.mapping.strategy.ternary_strategy:TernaryStrategy", "3ca9b934e161c23ee048d0cc17815f0c8d1d485b20e0e7e2426933569ccd1853"),
    ("pycalphad.mapping.strategy.ternary_strategy:TernaryStrategy._determine_start_direction", "b80cdd6327f39055289e4906f9c475e5ea4d6fcb3367126ca067ec474210ad9f"),
    ("pycalphad.mapping.zpf_equilibrium:CompositionSet", "dcc836c16787f12db73bc8d6051f8935a5ff70d3f585d7403db8f747a5eb8f0d"),
    ("pycalphad.mapping.zpf_equilibrium:Solver", "4fc0aa4028476a785a0930f67bf51e1b1ac30cdbdf2da2b4253806f242dbe57b"),
    ("pycalphad.mapping.zpf_equilibrium:calculate", "20aba4cdf426adfab43bcc81e1e10581d247444160811db6a37e325cf31bef62"),
)

_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:#/+\-]{0,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EVENT_ID = re.compile(r"^E[0-9]{8}$")
_RELATION_ID = re.compile(r"^R[0-9]{8}$")
_MAX_TEXT = 4096
_MAX_DEPTH = 24


_REASONS = MappingProxyType(
    {
        "W2B_INSTRUMENT_ARGUMENT_INVALID": "Instrumentation input is invalid.",
        "W2B_INSTRUMENT_CANONICAL_INVALID": "Trace payload is not canonical.",
        "W2B_INSTRUMENT_SOURCE_MISMATCH": "Instrumentation source hash mismatch.",
        "W2B_INSTRUMENT_UPSTREAM_MISMATCH": "Pinned pycalphad source/version mismatch.",
        "W2B_INSTRUMENT_LICENSE_MISMATCH": "Pinned pycalphad license mismatch.",
        "W2B_INSTRUMENT_LEASE_REQUIRED": "An active PRE-window ExecutionLease is required.",
        "W2B_INSTRUMENT_DOMAIN_MISMATCH": "Execution domain or PRE snapshot mismatch.",
        "W2B_INSTRUMENT_INTERNAL_ONLY": "Instrumentation is INTERNAL_QUALIFICATION only.",
        "W2B_INSTRUMENT_FE_SCOPE_INVALID": "Steel scope requires exact Fe profile and retained C15_LAVES.",
        "W2B_INSTRUMENT_EVENT_INVALID": "Trace event is invalid.",
        "W2B_INSTRUMENT_TRACE_INVALID": "Instrumentation trace is invalid.",
        "W2B_INSTRUMENT_EVENT_BUDGET": "Deterministic event budget exhausted.",
        "W2B_INSTRUMENT_OPERATION_BUDGET": "Deterministic operation budget exhausted.",
        "W2B_INSTRUMENT_RUNTIME_IMPORT_FAILED": "Pinned mapping runtime could not be imported.",
        "W2B_INSTRUMENT_STRATEGY_FAILED": "Instrumented mapping strategy failed.",
        "W2B_INSTRUMENT_SESSION_REQUIRED": "A factory-owned mapping session is required.",
        "W2B_INSTRUMENT_SESSION_CONSUMED": "The factory-owned mapping session was already consumed.",
        "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH": "The mapping strategy mutable state does not match its factory card.",
    }
)


class MappingInstrumentationError(ValueError):
    """Stable reason-coded instrumentation error."""

    def __init__(self, reason_code: str):
        if type(reason_code) is not str or reason_code not in (
            "W2B_INSTRUMENT_ARGUMENT_INVALID",
            "W2B_INSTRUMENT_CANONICAL_INVALID",
            "W2B_INSTRUMENT_SOURCE_MISMATCH",
            "W2B_INSTRUMENT_UPSTREAM_MISMATCH",
            "W2B_INSTRUMENT_LICENSE_MISMATCH",
            "W2B_INSTRUMENT_LEASE_REQUIRED",
            "W2B_INSTRUMENT_DOMAIN_MISMATCH",
            "W2B_INSTRUMENT_INTERNAL_ONLY",
            "W2B_INSTRUMENT_FE_SCOPE_INVALID",
            "W2B_INSTRUMENT_EVENT_INVALID",
            "W2B_INSTRUMENT_TRACE_INVALID",
            "W2B_INSTRUMENT_EVENT_BUDGET",
            "W2B_INSTRUMENT_OPERATION_BUDGET",
            "W2B_INSTRUMENT_RUNTIME_IMPORT_FAILED",
            "W2B_INSTRUMENT_STRATEGY_FAILED",
            "W2B_INSTRUMENT_SESSION_REQUIRED",
            "W2B_INSTRUMENT_SESSION_CONSUMED",
            "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH",
        ):
            raise RuntimeError("Unknown mapping instrumentation reason code")
        self.reason_code = reason_code
        super().__init__(reason_code)


class InstrumentationBudgetExceeded(MappingInstrumentationError):
    """Raised internally after an explicit budget event was retained."""


def _fail(reason: str) -> None:
    raise MappingInstrumentationError(reason)


def _strict_text(value: object, *, token: bool = False, nullable: bool = False) -> str | None:
    if nullable and value is None:
        return None
    if type(value) is not str or not value or len(value) > _MAX_TEXT:
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
    if token and _TOKEN.fullmatch(value) is None:
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
    return value


def _strict_sha(value: object) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
    return value


def _positive_budget(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or not 4 <= value <= 10_000_000:
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
    return value


def _canonical_value(value: object, depth: int = 0) -> object:
    if depth > _MAX_DEPTH:
        _fail("W2B_INSTRUMENT_CANONICAL_INVALID")
    if value is None or type(value) in (bool, str):
        if type(value) is str and len(value) > 1_000_000:
            _fail("W2B_INSTRUMENT_CANONICAL_INVALID")
        return value
    if type(value) is int:
        if abs(value) > 2**63 - 1:
            _fail("W2B_INSTRUMENT_CANONICAL_INVALID")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _fail("W2B_INSTRUMENT_CANONICAL_INVALID")
        return {"__f64__": struct.pack(">d", value).hex()}
    if type(value) in (tuple, list):
        return [_canonical_value(item, depth + 1) for item in value]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            _fail("W2B_INSTRUMENT_CANONICAL_INVALID")
        return {
            key: _canonical_value(value[key], depth + 1)
            for key in sorted(value)
        }
    _fail("W2B_INSTRUMENT_CANONICAL_INVALID")
    raise AssertionError("unreachable")


def _canonical_trace_bytes_internal(value: object) -> bytes:
    canonical = _canonical_value(value)
    return json.dumps(
        canonical,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _canonical_trace_digest_internal(value: object) -> str:
    return sha256(_canonical_trace_bytes_internal(value)).hexdigest()


def canonical_trace_bytes(value: object) -> bytes:
    """Encode trace data as deterministic UTF-8 JSON with binary64 tags."""

    return _canonical_trace_bytes_internal(value)


def canonical_trace_digest(value: object) -> str:
    return _canonical_trace_digest_internal(value)


def _fingerprint_constant(value: object) -> object:
    """Convert code/default constants without using address-bearing reprs."""

    if value is Ellipsis:
        return {"kind": "literal", "type": "ellipsis", "value": "Ellipsis"}
    if value is None or type(value) in (bool, int, str):
        return {"kind": "literal", "type": type(value).__name__, "value": value}
    if type(value) is float:
        return {"kind": "float", "binary64": struct.pack(">d", value).hex()}
    if type(value) is complex:
        return {
            "kind": "complex",
            "real": struct.pack(">d", value.real).hex(),
            "imag": struct.pack(">d", value.imag).hex(),
        }
    if type(value) is bytes:
        return {"kind": "bytes", "sha256": sha256(value).hexdigest(), "size": len(value)}
    if type(value) in (tuple, list):
        return {
            "kind": type(value).__name__,
            "items": [_fingerprint_constant(item) for item in value],
        }
    if type(value) in (set, frozenset):
        items = [_fingerprint_constant(item) for item in value]
        items.sort(key=_canonical_trace_bytes_internal)
        return {"kind": type(value).__name__, "items": items}
    if type(value) is dict:
        items = [
            (_fingerprint_constant(key), _fingerprint_constant(item))
            for key, item in value.items()
        ]
        items.sort(key=lambda pair: _canonical_trace_bytes_internal(pair[0]))
        return {"kind": "dict", "items": items}
    if isinstance(value, types.CodeType):
        return {"kind": "code", "record": _runtime_code_record(value)}
    name = getattr(value, "name", None)
    enum_value = getattr(value, "value", None)
    if type(name) is str and type(enum_value) in (bool, int, float, str):
        return {
            "kind": "enum_member",
            "type_module": type(value).__module__,
            "type_qualname": type(value).__qualname__,
            "name": name,
            "value": _fingerprint_constant(enum_value),
        }
    return {
        "kind": "opaque_type",
        "type_module": type(value).__module__,
        "type_qualname": type(value).__qualname__,
    }


def _runtime_code_record(code: types.CodeType) -> dict[str, object]:
    # co_filename is intentionally excluded.  A forged function compiled with
    # the pinned path must still differ by executable code/source semantics.
    return {
        "name": code.co_name,
        "qualname": code.co_qualname,
        "firstlineno": code.co_firstlineno,
        "argcount": code.co_argcount,
        "posonlyargcount": code.co_posonlyargcount,
        "kwonlyargcount": code.co_kwonlyargcount,
        "nlocals": code.co_nlocals,
        "stacksize": code.co_stacksize,
        "flags": code.co_flags,
        "code": code.co_code.hex(),
        "constants": [_fingerprint_constant(item) for item in code.co_consts],
        "names": list(code.co_names),
        "varnames": list(code.co_varnames),
        "freevars": list(code.co_freevars),
        "cellvars": list(code.co_cellvars),
        "linetable": code.co_linetable.hex(),
        "exceptiontable": code.co_exceptiontable.hex(),
    }


def _safe_source_sha256(value: object) -> str | None:
    try:
        source = inspect.getsource(value).encode("utf-8")
    except (OSError, TypeError, IOError):
        return None
    return sha256(source).hexdigest()


def _runtime_callable_record(value: object) -> dict[str, object]:
    code = getattr(value, "__code__", None)
    code_digest = None
    if isinstance(code, types.CodeType):
        code_digest = _canonical_trace_digest_internal(_runtime_code_record(code))
    defaults = getattr(value, "__defaults__", None)
    kwdefaults = getattr(value, "__kwdefaults__", None)
    # Python bytecode/source/defaults already encode the exact signature.
    # inspect's annotation rendering is not deterministic for union-like
    # classes, so retain a normalized textual signature only for C callables.
    signature = None
    if not isinstance(code, types.CodeType):
        try:
            signature = re.sub(
                r"0x[0-9A-Fa-f]+",
                "0xADDR",
                str(inspect.signature(value)),
            )
        except (TypeError, ValueError):
            signature = None
    return {
        "kind": "callable",
        "type_module": type(value).__module__,
        "type_qualname": type(value).__qualname__,
        "module": getattr(value, "__module__", None),
        "qualname": getattr(value, "__qualname__", None),
        "name": getattr(value, "__name__", None),
        "code_sha256": code_digest,
        "source_sha256": _safe_source_sha256(value),
        "defaults": _fingerprint_constant(defaults),
        "kwdefaults": _fingerprint_constant(kwdefaults),
        "signature": signature,
        "doc_sha256": sha256(
            (getattr(value, "__doc__", None) or "").encode("utf-8")
        ).hexdigest(),
    }


def _runtime_class_record(value: type) -> dict[str, object]:
    members: list[dict[str, object]] = []
    for name, member in sorted(vars(value).items()):
        if name in ("__dict__", "__weakref__", "__classcell__"):
            continue
        if isinstance(member, (staticmethod, classmethod)):
            members.append({
                "name": name,
                "wrapper": type(member).__name__,
                "value": _runtime_callable_record(member.__func__),
            })
        elif isinstance(member, property):
            members.append({
                "name": name,
                "wrapper": "property",
                "get": None if member.fget is None else _runtime_callable_record(member.fget),
                "set": None if member.fset is None else _runtime_callable_record(member.fset),
                "delete": None if member.fdel is None else _runtime_callable_record(member.fdel),
            })
        elif isinstance(getattr(member, "__code__", None), types.CodeType):
            members.append({"name": name, "value": _runtime_callable_record(member)})
        elif callable(member) or inspect.ismethoddescriptor(member) or inspect.isdatadescriptor(member):
            members.append({
                "name": name,
                "value": _runtime_callable_record(member),
            })
        elif type(member) in (type(None), bool, int, float, complex, str, bytes, tuple, frozenset):
            members.append({"name": name, "value": _fingerprint_constant(member)})
        elif getattr(type(member), "__module__", "").startswith("pycalphad"):
            members.append({"name": name, "value": _fingerprint_constant(member)})
    return {
        "kind": "class",
        "type_module": type(value).__module__,
        "type_qualname": type(value).__qualname__,
        "module": value.__module__,
        "qualname": value.__qualname__,
        "bases": [f"{base.__module__}:{base.__qualname__}" for base in value.__bases__],
        "metaclass": f"{type(value).__module__}:{type(value).__qualname__}",
        "source_sha256": _safe_source_sha256(value),
        "members": members,
    }


def _runtime_object_record(value: object) -> dict[str, object]:
    if isinstance(value, type):
        return _runtime_class_record(value)
    if callable(value):
        return _runtime_callable_record(value)
    if isinstance(value, types.ModuleType):
        return {"kind": "module", "module": value.__name__}
    return {"kind": "value", "value": _fingerprint_constant(value)}


def _runtime_module_manifest() -> tuple[tuple[dict[str, object], ...], str]:
    records: list[dict[str, object]] = []
    for module_name in _RUNTIME_PRIMITIVE_MODULES:
        module = importlib.import_module(module_name)
        if module.__name__ != module_name:
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        bindings: list[dict[str, object]] = []
        transient_names = _RUNTIME_TRANSIENT_BINDING_EXCLUSIONS.get(
            module_name, ()
        )
        for name, value in sorted(vars(module).items()):
            if name.startswith("__") or name in transient_names:
                continue
            include = False
            if isinstance(value, types.ModuleType):
                include = True
            elif isinstance(value, type):
                include = value.__module__.startswith("pycalphad")
            elif callable(value):
                include = str(getattr(value, "__module__", "")).startswith("pycalphad")
            elif type(value) in (type(None), bool, int, float, complex, str, bytes, tuple, frozenset):
                include = True
            if include:
                bindings.append({"name": name, "record": _runtime_object_record(value)})
        origin_path = Path(getattr(module, "__file__", "")).resolve()
        try:
            package_index = tuple(part.lower() for part in origin_path.parts).index(
                "pycalphad"
            )
            origin = Path(*origin_path.parts[package_index:]).as_posix()
        except ValueError:
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        records.append({
            "module": module_name,
            "origin": origin,
            "bindings": bindings,
        })
    frozen = tuple(records)
    return frozen, _canonical_trace_digest_internal(frozen)


def _resolve_runtime_locator(locator: str) -> object:
    module_name, separator, attribute_path = locator.partition(":")
    if not separator or not module_name or not attribute_path:
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    value: object = importlib.import_module(module_name)
    for name in attribute_path.split("."):
        try:
            value = getattr(value, name)
        except AttributeError as error:
            raise MappingInstrumentationError("W2B_INSTRUMENT_UPSTREAM_MISMATCH") from error
    return value


def _runtime_critical_manifest() -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            locator,
            canonical_trace_digest(_runtime_object_record(_resolve_runtime_locator(locator))),
        )
        for locator in _RUNTIME_CRITICAL_LOCATORS
    )


def _verify_runtime_primitive_manifest() -> str:
    _records, observed = _runtime_module_manifest()
    if observed != RUNTIME_PRIMITIVE_MANIFEST_SHA256:
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    if _runtime_critical_manifest() != _RUNTIME_CRITICAL_PINS:
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    # Exact aliases used by the mapping call graph.  Digest equality is not a
    # substitute for object identity at these live module boundaries.
    package = importlib.import_module("pycalphad")
    database = importlib.import_module("pycalphad.io.database")
    calculate = importlib.import_module("pycalphad.core.calculate")
    workspace = importlib.import_module("pycalphad.core.workspace")
    zeq = importlib.import_module("pycalphad.mapping.zpf_equilibrium")
    if (
        package.Database is not database.Database
        or package.calculate is not calculate.calculate
        or package.Workspace is not workspace.Workspace
        or zeq.CompositionSet is not importlib.import_module(
            "pycalphad.core.composition_set"
        ).CompositionSet
        or zeq.Solver is not importlib.import_module("pycalphad.core.solver").Solver
        or zeq.calculate is not calculate.calculate
    ):
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    return observed


def _normalized_instrumentation_source() -> bytes:
    try:
        payload = Path(__file__).read_bytes()
    except OSError as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_SOURCE_MISMATCH") from error
    prefix = b"INSTRUMENTATION_SOURCE_" + b'PIN_SHA256 = "'
    start = payload.find(prefix)
    if start < 0 or payload.find(prefix, start + 1) >= 0:
        _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
    digest_start = start + len(prefix)
    digest_end = digest_start + 64
    if (
        digest_end >= len(payload)
        or payload[digest_end:digest_end + 1] != b'"'
        or re.fullmatch(b"[0-9a-f]{64}", payload[digest_start:digest_end]) is None
    ):
        _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
    return payload[:digest_start] + (b"0" * 64) + payload[digest_end:]


def instrumentation_source_sha256() -> str:
    """Return the non-self-referential normalized source-manifest digest."""

    return sha256(_normalized_instrumentation_source()).hexdigest()


def verify_instrumentation_source(expected_sha256: object | None = None) -> str:
    actual = instrumentation_source_sha256()
    if actual != INSTRUMENTATION_SOURCE_PIN_SHA256:
        _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
    if expected_sha256 is not None and _strict_sha(expected_sha256) != actual:
        _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
    return actual


@dataclass(frozen=True, slots=True)
class UpstreamSourceMetadata:
    package: str
    version: str
    package_root_sha256: str
    license_sha256: str
    sources: tuple[tuple[str, str, int], ...]

    def __post_init__(self) -> None:
        authority = _HELPER_TRUST_VERIFY(deep=False)[1]
        if (
            type(self.package) is not str
            or type(self.version) is not str
            or self.package != "pycalphad"
            or self.version != authority["PYCALPHAD_VERSION"]
        ):
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        package_root_sha256 = _strict_sha(self.package_root_sha256)
        if _strict_sha(self.license_sha256) != authority["PYCALPHAD_LICENSE_SHA256"]:
            _fail("W2B_INSTRUMENT_LICENSE_MISMATCH")
        if type(self.sources) is not tuple:
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        rebuilt: list[tuple[str, str, int]] = []
        for item in self.sources:
            if type(item) is not tuple or len(item) != 3:
                _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
            path, digest, size = item
            if type(path) is not str or not path or "\\" in path or path.startswith("/"):
                _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
            if type(size) is not int or isinstance(size, bool) or size < 0:
                _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
            rebuilt.append((path, _strict_sha(digest), size))
        frozen_sources = tuple(rebuilt)
        pinned_sources = authority["_PYCALPHAD_PACKAGE_PINS"]
        if frozen_sources != pinned_sources:
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        if package_root_sha256 != _directory_pin(pinned_sources):
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        object.__setattr__(self, "sources", frozen_sources)

    def as_dict(self) -> dict[str, object]:
        _HELPER_TRUST_VERIFY(deep=False)
        try:
            self = UpstreamSourceMetadata(
                package=object.__getattribute__(self, "package"),
                version=object.__getattribute__(self, "version"),
                package_root_sha256=object.__getattribute__(
                    self, "package_root_sha256"
                ),
                license_sha256=object.__getattribute__(self, "license_sha256"),
                sources=object.__getattribute__(self, "sources"),
            )
            return {
                "package": self.package,
                "version": self.version,
                "package_root_sha256": self.package_root_sha256,
                "license_sha256": self.license_sha256,
                "sources": [
                    {"path": path, "sha256": digest, "size_bytes": size}
                    for path, digest, size in self.sources
                ],
            }
        except Exception as error:
            raise MappingInstrumentationError("W2B_INSTRUMENT_TRACE_INVALID") from error


def _directory_pin(sources: Sequence[tuple[str, str, int]]) -> str:
    return canonical_trace_digest(
        [
            {"path": path, "sha256": digest, "size_bytes": size}
            for path, digest, size in sources
        ]
    )


def verify_pinned_pycalphad() -> UpstreamSourceMetadata:
    """Lazily verify the exact installed pycalphad 0.11.2 wheel."""

    authority = _HELPER_TRUST_VERIFY(deep=True)[1]
    pinned_version = authority["PYCALPHAD_VERSION"]
    package_pins = authority["_PYCALPHAD_PACKAGE_PINS"]
    try:
        package = importlib.import_module("pycalphad")
        version = getattr(package, "__version__")
        package_file = getattr(package, "__file__")
        if type(version) is not str or type(package_file) is not str:
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        root = Path(package_file).resolve(strict=True).parent
        site_root = root.parent
    except Exception as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_RUNTIME_IMPORT_FAILED") from error
    if version != pinned_version:
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    observed: list[tuple[str, str, int]] = []
    try:
        package_dir = site_root / "pycalphad"
        dist_dir = site_root / f"pycalphad-{pinned_version}.dist-info"
        observed_paths = tuple(sorted(
            path.relative_to(site_root).as_posix()
            for directory in (package_dir, dist_dir)
            for path in directory.rglob("*")
            if (
                path.is_file()
                and path.suffix != ".pyc"
                and "__pycache__" not in path.parts
            )
        ))
        pinned_paths = tuple(item[0] for item in package_pins)
        if (
            len(observed_paths) != len(pinned_paths)
            or len(set(observed_paths)) != len(observed_paths)
            or set(observed_paths) != set(pinned_paths)
        ):
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        for relative, expected_digest, expected_size in package_pins:
            path = site_root.joinpath(*relative.split("/"))
            info = path.stat()
            payload = path.read_bytes()
            digest = sha256(payload).hexdigest()
            if not path.is_file() or info.st_size != expected_size or digest != expected_digest:
                _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
            observed.append((relative, digest, info.st_size))
        dist_root = site_root / f"pycalphad-{pinned_version}.dist-info"
        license_path = dist_root / "licenses" / "LICENSE.txt"
        license_payload = license_path.read_bytes()
    except MappingInstrumentationError:
        raise
    except OSError as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_UPSTREAM_MISMATCH") from error
    license_digest = sha256(license_payload).hexdigest()
    if license_digest != authority["PYCALPHAD_LICENSE_SHA256"]:
        _fail("W2B_INSTRUMENT_LICENSE_MISMATCH")
    sources = tuple(observed)
    return UpstreamSourceMetadata(
        package="pycalphad",
        version=version,
        package_root_sha256=_directory_pin(sources),
        license_sha256=license_digest,
        sources=sources,
    )


def _ordered_tokens(value: object, *, allow_empty: bool = True) -> tuple[str, ...]:
    if type(value) not in (tuple, list):
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
    result = tuple(_strict_text(item, token=True) for item in value)
    if (not allow_empty and not result) or len(set(result)) != len(result):
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
    return result  # type: ignore[return-value]


def _pairs(value: object, *, nullable: bool) -> tuple[tuple[str, object], ...] | None:
    if nullable and value is None:
        return None
    if type(value) is not tuple:
        _fail("W2B_INSTRUMENT_EVENT_INVALID")
    result: list[tuple[str, object]] = []
    seen: set[str] = set()
    for item in value:
        if type(item) is not tuple or len(item) != 2:
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        key = _strict_text(item[0], token=True)
        if key in seen:
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        seen.add(key)  # type: ignore[arg-type]
        _canonical_value(item[1])
        result.append((key, _primitive_copy(item[1])))  # type: ignore[arg-type]
    return tuple(sorted(result, key=lambda pair: pair[0]))


def _primitive_copy(value: object, depth: int = 0) -> object:
    if depth > _MAX_DEPTH:
        _fail("W2B_INSTRUMENT_CANONICAL_INVALID")
    if value is None or type(value) in (bool, int, float, str):
        return value
    if type(value) in (tuple, list):
        return tuple(_primitive_copy(item, depth + 1) for item in value)
    if type(value) is dict:
        return {
            key: _primitive_copy(value[key], depth + 1)
            for key in sorted(value)
        }
    _fail("W2B_INSTRUMENT_CANONICAL_INVALID")
    raise AssertionError("unreachable")


def _validate_detail_claim_safety(
    kind: str,
    details: tuple[tuple[str, object], ...],
    markers: tuple[str, ...],
    max_depth: int,
) -> None:
    """Reserve claim-bearing detail keys at every nested depth."""

    def visit(value: object, depth: int) -> None:
        if depth > max_depth:
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if type(value) is dict:
            for key, item in value.items():
                if type(key) is not str or not key.isascii():
                    _fail("W2B_INSTRUMENT_EVENT_INVALID")
                normalized = "".join(character for character in key.lower() if character.isalnum())
                if any(marker in normalized for marker in markers):
                    _fail("W2B_INSTRUMENT_EVENT_INVALID")
                visit(item, depth + 1)
        elif type(value) in (tuple, list):
            for item in value:
                visit(item, depth + 1)

    for key, value in details:
        normalized = "".join(character for character in key.lower() if character.isalnum())
        if key == "completion_claim" and kind == "TERMINATION" and value is False:
            continue
        if any(marker in normalized for marker in markers):
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        visit(value, 1)


@dataclass(frozen=True, slots=True)
class InstrumentationEvent:
    ordinal: int
    event_id: str
    operation_ordinal: int
    kind: str
    stage: str
    requested_conditions: tuple[tuple[str, object], ...]
    resolved_coordinates: tuple[tuple[str, object], ...] | None
    phases: tuple[str, ...]
    phase_instances: tuple[str, ...]
    exception_type: str | None
    exception_message_sha256: str | None
    parent_event_id: str | None
    relation_id: str | None
    outcome: str
    details: tuple[tuple[str, object], ...] = ()

    def __post_init__(self) -> None:
        authority = _HELPER_TRUST_VERIFY(deep=False)[1]
        if (
            type(self.ordinal) is not int
            or not 0 <= self.ordinal <= 9_999_999
        ):
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if (
            type(self.event_id) is not str
            or self.event_id != f"E{self.ordinal:08d}"
            or authority["_EVENT_ID"].fullmatch(self.event_id) is None
        ):
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if (
            type(self.operation_ordinal) is not int
            or not 0 <= self.operation_ordinal <= 10_000_000
        ):
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if type(self.kind) is not str or self.kind not in authority["EVENT_KINDS"]:
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if (
            (self.operation_ordinal == 0)
            != (self.kind in authority["_CONTROL_EVENT_KINDS"])
        ):
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        _strict_text(self.stage, token=True)
        if type(self.requested_conditions) is not tuple:
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if (
            self.resolved_coordinates is not None
            and type(self.resolved_coordinates) is not tuple
        ):
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if type(self.phases) is not tuple or type(self.phase_instances) is not tuple:
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        object.__setattr__(self, "requested_conditions", _pairs(self.requested_conditions, nullable=False))
        object.__setattr__(self, "resolved_coordinates", _pairs(self.resolved_coordinates, nullable=True))
        object.__setattr__(self, "phases", _ordered_tokens(self.phases))
        object.__setattr__(self, "phase_instances", _ordered_tokens(self.phase_instances))
        if type(self.outcome) is not str or self.outcome not in authority["OUTCOMES"]:
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if (self.exception_type is None) != (self.exception_message_sha256 is None):
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if self.exception_type is not None:
            _strict_text(self.exception_type)
            _strict_sha(self.exception_message_sha256)
            if self.outcome != "FAILED":
                _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if self.parent_event_id is not None:
            if (
                type(self.parent_event_id) is not str
                or authority["_EVENT_ID"].fullmatch(self.parent_event_id) is None
            ):
                _fail("W2B_INSTRUMENT_EVENT_INVALID")
            if int(self.parent_event_id[1:]) >= self.ordinal:
                _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if (
            self.relation_id is not None
            and (
                type(self.relation_id) is not str
                or authority["_RELATION_ID"].fullmatch(self.relation_id) is None
            )
        ):
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if type(self.details) is not tuple:
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        object.__setattr__(self, "details", _pairs(self.details, nullable=False))
        _validate_detail_claim_safety(
            self.kind,
            self.details,
            authority["_CLAIM_DETAIL_KEY_MARKERS"],
            authority["_MAX_DEPTH"],
        )
        phase_bases = {item.split("#", 1)[0] for item in self.phase_instances}
        if not phase_bases.issubset(set(self.phases)):
            _fail("W2B_INSTRUMENT_EVENT_INVALID")

    def as_dict(self) -> dict[str, object]:
        authority = _HELPER_TRUST_VERIFY(deep=False)[1]
        try:
            self = InstrumentationEvent(
                ordinal=object.__getattribute__(self, "ordinal"),
                event_id=object.__getattribute__(self, "event_id"),
                operation_ordinal=object.__getattribute__(
                    self, "operation_ordinal"
                ),
                kind=object.__getattribute__(self, "kind"),
                stage=object.__getattribute__(self, "stage"),
                requested_conditions=object.__getattribute__(
                    self, "requested_conditions"
                ),
                resolved_coordinates=object.__getattribute__(
                    self, "resolved_coordinates"
                ),
                phases=object.__getattribute__(self, "phases"),
                phase_instances=object.__getattribute__(self, "phase_instances"),
                exception_type=object.__getattribute__(self, "exception_type"),
                exception_message_sha256=object.__getattribute__(
                    self, "exception_message_sha256"
                ),
                parent_event_id=object.__getattribute__(self, "parent_event_id"),
                relation_id=object.__getattribute__(self, "relation_id"),
                outcome=object.__getattribute__(self, "outcome"),
                details=object.__getattribute__(self, "details"),
            )
            resolved = self.resolved_coordinates
            return {
                "schema_version": authority["EVENT_SCHEMA"],
                "ordinal": self.ordinal,
                "event_id": self.event_id,
                "operation_ordinal": self.operation_ordinal,
                "kind": self.kind,
                "stage": self.stage,
                "requested_conditions": dict(self.requested_conditions),
                "resolved_coordinates": (
                    None if resolved is None else dict(resolved)
                ),
                "phases": list(self.phases),
                "phase_instances": list(self.phase_instances),
                "exception_type": self.exception_type,
                "exception_message_sha256": self.exception_message_sha256,
                "parent_event_id": self.parent_event_id,
                "relation_id": self.relation_id,
                "outcome": self.outcome,
                "details": dict(self.details),
            }
        except Exception as error:
            raise MappingInstrumentationError("W2B_INSTRUMENT_TRACE_INVALID") from error


@dataclass(frozen=True, slots=True)
class TraceMetadata:
    feature_id: str
    execution_context: str
    family: str
    profile: str
    profile_role: str
    domain_receipt_digest: str
    profile_receipt_digest: str
    execution_snapshot_digest: str
    runtime_sha256: str
    strategy_state_initial_sha256: str
    strategy_state_terminal_sha256: str
    strategy_state_provenance_status: str
    effective_phases: tuple[str, ...]
    operation_budget: int
    event_budget: int
    instrumentation_source_sha256: str
    upstream: UpstreamSourceMetadata

    def __post_init__(self) -> None:
        if _OPERATIONAL_PROVENANCE_AUTHORITY(
            "metadata_registered", self
        ) is True:
            return
        authority = _HELPER_TRUST_VERIFY(deep=False)[1]
        if (
            _strict_text(self.feature_id, token=True)
            not in authority["SUPPORTED_MAPPING_FEATURES"]
        ):
            _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        _strict_text(self.execution_context, token=True)
        _strict_text(self.family, token=True)
        _strict_text(self.profile, token=True)
        _strict_text(self.profile_role, token=True)
        scope = (
            self.execution_context, self.family, self.profile,
            self.profile_role,
        )
        if scope not in authority["_TRACE_SCOPE_RULES"]:
            _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        _strict_sha(self.domain_receipt_digest)
        _strict_sha(self.profile_receipt_digest)
        _strict_sha(self.execution_snapshot_digest)
        _strict_sha(self.runtime_sha256)
        _strict_sha(self.strategy_state_initial_sha256)
        _strict_sha(self.strategy_state_terminal_sha256)
        _strict_text(self.strategy_state_provenance_status, token=True)
        zero = "0" * 64
        if self.strategy_state_provenance_status not in authority[
            "_STRATEGY_STATE_PROVENANCE_STATUSES"
        ]:
            _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        if self.execution_context == "MANUFACTURED_TEST_ONLY":
            if (
                self.strategy_state_provenance_status
                != "MANUFACTURED_NOT_APPLICABLE"
                or self.strategy_state_initial_sha256 != zero
                or self.strategy_state_terminal_sha256 != zero
            ):
                _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        elif self.strategy_state_provenance_status == "FACTORY_PENDING":
            if (
                self.strategy_state_initial_sha256 != zero
                or self.strategy_state_terminal_sha256 != zero
            ):
                _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        elif self.strategy_state_provenance_status == "PRISTINE_BOUND":
            if (
                self.strategy_state_initial_sha256 == zero
                or self.strategy_state_terminal_sha256 != zero
            ):
                _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        elif self.strategy_state_provenance_status in (
            "TERMINAL_OBSERVED", "TERMINAL_INVALID", "PRE_RUN_INVALID"
        ):
            if (
                self.strategy_state_initial_sha256 == zero
                or self.strategy_state_terminal_sha256 == zero
            ):
                _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        else:
            _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        if type(self.effective_phases) is not tuple:
            _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        phases = _ordered_tokens(self.effective_phases, allow_empty=False)
        object.__setattr__(self, "effective_phases", phases)
        _positive_budget(self.operation_budget)
        _positive_budget(self.event_budget)
        verify_instrumentation_source(self.instrumentation_source_sha256)
        object.__setattr__(self, "upstream", _copy_upstream(self.upstream))
        if self.family == "fe":
            if (
                self.profile not in ("thermogar_patch", "upstream_original")
                or "C15_LAVES" not in phases
            ):
                _fail("W2B_INSTRUMENT_FE_SCOPE_INVALID")
        if self.execution_context == EXECUTION_MODE:
            _OPERATIONAL_PROVENANCE_AUTHORITY("metadata_constructed", self)

    def __reduce__(self):
        registered = _OPERATIONAL_PROVENANCE_AUTHORITY(
            "metadata_registered", self
        )
        if (
            registered is True
            or object.__getattribute__(self, "execution_context")
            == EXECUTION_MODE
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return (
            TraceMetadata,
            tuple(
                object.__getattribute__(self, name)
                for name in (
                    "feature_id", "execution_context", "family", "profile",
                    "profile_role", "domain_receipt_digest",
                    "profile_receipt_digest", "execution_snapshot_digest",
                    "runtime_sha256", "strategy_state_initial_sha256",
                    "strategy_state_terminal_sha256",
                    "strategy_state_provenance_status", "effective_phases",
                    "operation_budget", "event_budget",
                    "instrumentation_source_sha256", "upstream",
                )
            ),
        )

    def __reduce_ex__(self, protocol: object):
        if type(protocol) is not int or protocol < 0:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return TraceMetadata.__reduce__(self)

    def __copy__(self):
        constructor, arguments = TraceMetadata.__reduce__(self)
        return constructor(*arguments)

    def __deepcopy__(self, memo: object):
        if type(memo) is not dict:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return TraceMetadata.__copy__(self)

    def as_dict(self) -> dict[str, object]:
        authority = _HELPER_TRUST_VERIFY(deep=False)[1]
        try:
            registered = _OPERATIONAL_PROVENANCE_AUTHORITY(
                "metadata_registered", self
            )
            if registered is not True:
                self = TraceMetadata(
                    feature_id=object.__getattribute__(self, "feature_id"),
                    execution_context=object.__getattribute__(
                        self, "execution_context"
                    ),
                    family=object.__getattribute__(self, "family"),
                    profile=object.__getattribute__(self, "profile"),
                    profile_role=object.__getattribute__(self, "profile_role"),
                    domain_receipt_digest=object.__getattribute__(
                        self, "domain_receipt_digest"
                    ),
                    profile_receipt_digest=object.__getattribute__(
                        self, "profile_receipt_digest"
                    ),
                    execution_snapshot_digest=object.__getattribute__(
                        self, "execution_snapshot_digest"
                    ),
                    runtime_sha256=object.__getattribute__(self, "runtime_sha256"),
                    strategy_state_initial_sha256=object.__getattribute__(
                        self, "strategy_state_initial_sha256"
                    ),
                    strategy_state_terminal_sha256=object.__getattribute__(
                        self, "strategy_state_terminal_sha256"
                    ),
                    strategy_state_provenance_status=object.__getattribute__(
                        self, "strategy_state_provenance_status"
                    ),
                    effective_phases=object.__getattribute__(self, "effective_phases"),
                    operation_budget=object.__getattribute__(
                        self, "operation_budget"
                    ),
                    event_budget=object.__getattribute__(self, "event_budget"),
                    instrumentation_source_sha256=object.__getattribute__(
                        self, "instrumentation_source_sha256"
                    ),
                    upstream=object.__getattribute__(self, "upstream"),
                )
            return {
                "schema_version": authority["METADATA_SCHEMA"],
                "feature_id": self.feature_id,
                "execution_context": self.execution_context,
                "family": self.family,
                "profile": self.profile,
                "profile_role": self.profile_role,
                "domain_receipt_digest": self.domain_receipt_digest,
                "profile_receipt_digest": self.profile_receipt_digest,
                "execution_snapshot_digest": self.execution_snapshot_digest,
                "runtime_sha256": self.runtime_sha256,
                "strategy_state_provenance": {
                    "schema": authority["_STRATEGY_STATE_CARD_SCHEMA"],
                    "initial_sha256": self.strategy_state_initial_sha256,
                    "terminal_sha256": self.strategy_state_terminal_sha256,
                    "status": self.strategy_state_provenance_status,
                },
                "effective_phases": list(self.effective_phases),
                "operation_budget": self.operation_budget,
                "event_budget": self.event_budget,
                "instrumentation": {
                    "version": authority["INSTRUMENTATION_VERSION"],
                    "source_sha256": self.instrumentation_source_sha256,
                    "source_pin_normalization": authority[
                        "INSTRUMENTATION_SOURCE_PIN_NORMALIZATION"
                    ],
                    "runtime_primitive_manifest_sha256": authority[
                        "RUNTIME_PRIMITIVE_MANIFEST_SHA256"
                    ],
                    "runtime_primitive_modules": list(
                        authority["_RUNTIME_PRIMITIVE_MODULES"]
                    ),
                    "runtime_critical_primitives": [
                        {"locator": locator, "sha256": digest}
                        for locator, digest in authority["_RUNTIME_CRITICAL_PINS"]
                    ],
                },
                "upstream": self.upstream.as_dict(),
                "steel_scope": {
                    # Compatibility globals are not serialization authority.
                    "required": True,
                    "supported_fe_profiles": [
                        "thermogar_patch", "upstream_original"
                    ],
                    "baseline_profile": None,
                    "fe_exclusion_decision_made": False,
                    "c15_exclusion_decision_made": False,
                    "baseline_decision": "UNDECIDED_USER_DECISION_REQUIRED",
                    "c15_exclusion_decision": "UNDECIDED_USER_DECISION_REQUIRED",
                },
                # Compatibility globals are deliberately not authority. These
                # denial literals are part of the serialized INTERNAL contract.
                "acceptance_claim": False,
                "counts_toward_feature_coverage": False,
                "production_use": "DENIED",
            }
        except Exception as error:
            if (
                isinstance(error, MappingInstrumentationError)
                and error.reason_code in (
                    "W2B_INSTRUMENT_TRACE_INVALID",
                    "W2B_INSTRUMENT_SOURCE_MISMATCH",
                    "W2B_INSTRUMENT_UPSTREAM_MISMATCH",
                )
            ):
                raise
            raise MappingInstrumentationError("W2B_INSTRUMENT_TRACE_INVALID") from error


_OPERATION_PAYLOAD_RULES = MappingProxyType(
    {
        "solver_invocation": (("SOLVER_INVOCATION", "SOLVER_RESULT"),),
        "node_queue_add": (
            ("NODE_QUEUE_TRANSITION", "NODE_QUEUE_TRANSITION"),
            ("NODE_QUEUE_TRANSITION", "DUPLICATE_MERGE"),
            ("NODE_QUEUE_TRANSITION", "NODE_QUEUE_TRANSITION", "START_POINT"),
            ("NODE_QUEUE_TRANSITION", "DUPLICATE_MERGE", "START_POINT"),
        ),
        "node_queue_get": (("NODE_QUEUE_TRANSITION",),),
        "starting_point": (("START_POINT",),),
        "axis_limit": (("AXIS_TRANSITION",),),
        "direction_probe": (("DIRECTION_PROBE", "DIRECTION_PROBE"),),
        "invariant_check": (("INVARIANT_CHECK",),),
        "zpf_start": (
            ("ZPF_LINE_TRANSITION",),
            ("ZPF_LINE_TRANSITION", "ZPF_RELATION"),
        ),
        "automatic_start_scan": (("START_POINT_SCAN", "START_POINT_SCAN"),),
        "strategy_iterate": (("ZPF_LINE_TRANSITION",),),
        "ternary_transfer_start": (("START_POINT",),),
        "ternary_recovery_start": (("START_POINT",),),
        "zpf_point_append": (
            ("ZPF_LINE_TRANSITION",),
            ("ZPF_LINE_TRANSITION", "ZPF_LINE_TRANSITION"),
        ),
        "zpf_transition": (
            ("ZPF_LINE_TRANSITION",),
            ("AXIS_TRANSITION",),
        ),
        "node_exit": (("INVARIANT_CHECK",),),
        "runtime_failure": (("INVARIANT_CHECK",),),
        # The backtrack and discard operations have a deterministic but
        # data-dependent number of deleted-point payloads.  Their exact
        # grammar is checked explicitly by _validate_trace_semantics.
        "zpf_backtrack": (),
        "metastable_discard": (),
        "manufactured_hook": tuple((kind,) for kind in EVENT_KINDS if kind not in {
            "TRACE_STARTED", "OPERATION_STARTED", "OPERATION_ENDED",
            "SOLVER_INVOCATION", "SOLVER_RESULT", "TERMINATION",
            "ERROR", "BUDGET_EXHAUSTED",
        }),
    }
)


def _validate_trace_semantics(
    metadata: TraceMetadata,
    operation_count: int,
    events: tuple[InstrumentationEvent, ...],
    halted: bool,
    terminal_reason: str,
) -> None:
    authority = _HELPER_TRUST_VERIFY(deep=False)[1]
    payload_rules = authority["_OPERATION_PAYLOAD_RULES"]
    control_kinds = authority["_CONTROL_EVENT_KINDS"]
    control_detail_keys = authority["_CONTROL_EVENT_DETAIL_KEYS"]
    first = events[0]
    if (
        first.kind != "TRACE_STARTED"
        or first.stage != "TRACE"
        or first.operation_ordinal != 0
        or first.outcome != "ACCEPTED"
        or first.requested_conditions
        or first.resolved_coordinates is not None
        or first.phases
        or first.phase_instances
        or first.exception_type is not None
        or first.parent_event_id is not None
        or first.relation_id is not None
        or dict(first.details) != {
            "instrumentation_version": authority["INSTRUMENTATION_VERSION"],
            "upstream_version": authority["PYCALPHAD_VERSION"],
        }
    ):
        _fail("W2B_INSTRUMENT_TRACE_INVALID")

    starts: dict[int, InstrumentationEvent] = {}
    ends: dict[int, InstrumentationEvent] = {}
    payloads: dict[int, list[InstrumentationEvent]] = {}
    solver_invocations: dict[str, InstrumentationEvent] = {}
    solver_results: dict[str, InstrumentationEvent] = {}
    budget_events: list[InstrumentationEvent] = []
    run_terminations: list[InstrumentationEvent] = []
    error_events: list[InstrumentationEvent] = []
    events_by_id = {event.event_id: event for event in events}

    for event in events:
        details = dict(event.details)
        if (
            (event.operation_ordinal == 0) != (event.kind in control_kinds)
            or (event.kind == "TRACE_STARTED" and event is not first)
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if event.exception_type is not None and event.outcome != "FAILED":
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if event.kind == "OPERATION_STARTED":
            if (
                event.operation_ordinal <= 0
                or event.operation_ordinal in starts
                or event.operation_ordinal in ends
                or event.parent_event_id is not None
                or event.exception_type is not None
                or event.outcome != "ACCEPTED"
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            operation_kind = details.get("operation_kind")
            if (
                operation_kind not in payload_rules
                or type(details.get("event_slots")) is not int
                or isinstance(details.get("event_slots"), bool)
                or details["event_slots"] < 1
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            starts[event.operation_ordinal] = event
            payloads[event.operation_ordinal] = []
            continue
        if event.kind == "OPERATION_ENDED":
            start = starts.get(event.operation_ordinal)
            if (
                start is None
                or event.operation_ordinal in ends
                or event.parent_event_id != start.event_id
                or event.stage != start.stage
                or event.relation_id != start.relation_id
                or details.get("operation_kind")
                != dict(start.details).get("operation_kind")
                or details.get("event_slots")
                != dict(start.details).get("event_slots")
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            ends[event.operation_ordinal] = event
            continue
        if event.operation_ordinal > 0:
            if (
                event.operation_ordinal not in starts
                or event.operation_ordinal in ends
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            start_relation = starts[event.operation_ordinal].relation_id
            if event.relation_id != start_relation:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            payloads[event.operation_ordinal].append(event)
        elif event.operation_ordinal != 0:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")

        if event.kind == "SOLVER_INVOCATION":
            if (
                event.outcome != "ACCEPTED"
                or event.exception_type is not None
                or event.parent_event_id is not None
                or event.operation_ordinal <= 0
                or event.relation_id is None
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            solver_invocations[event.event_id] = event
        elif event.kind == "SOLVER_RESULT":
            invocation = solver_invocations.get(event.parent_event_id or "")
            if (
                invocation is None
                or event.parent_event_id in solver_results
                or event.operation_ordinal != invocation.operation_ordinal
                or event.relation_id != invocation.relation_id
                or event.stage != invocation.stage
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            solver_results[event.parent_event_id] = event
        elif event.kind == "BUDGET_EXHAUSTED":
            if (
                event.operation_ordinal != 0
                or event.outcome != "ABANDONED"
                or event.exception_type is not None
                or event.parent_event_id is not None
                or event.relation_id is not None
                or details.get("reason_code") not in (
                    "W2B_INSTRUMENT_EVENT_BUDGET",
                    "W2B_INSTRUMENT_OPERATION_BUDGET",
                )
                or tuple(sorted(details))
                != control_detail_keys["BUDGET_EXHAUSTED"]
                or details["operation_budget"] != metadata.operation_budget
                or details["event_budget"] != metadata.event_budget
                or details["operation_count_at_exhaustion"] != operation_count
                or any(
                    type(details[name]) is not int
                    or isinstance(details[name], bool)
                    for name in (
                        "retained_count", "reserved_count",
                        "attempted_unit_size",
                    )
                )
                or details["retained_count"] < 1
                or details["retained_count"] > event.ordinal
                or details["reserved_count"] < 0
                or details["attempted_unit_size"] < 1
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            budget_events.append(event)
        elif event.kind == "ERROR":
            if (
                event.operation_ordinal != 0
                or event.outcome != "FAILED"
                or event.exception_type is None
                or tuple(sorted(details)) != control_detail_keys["ERROR"]
                or event.parent_event_id is None
                or event.relation_id is not None
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            error_events.append(event)
        elif event.kind == "TERMINATION":
            if (
                event.operation_ordinal != 0
                or event.exception_type is not None
                or details.get("completion_claim") is not False
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            if event.stage == "RUN":
                if tuple(sorted(details)) != control_detail_keys["TERMINATION_RUN"]:
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
                run_terminations.append(event)
            elif (
                event.stage != "SCOPE"
                or event.outcome not in ("ACCEPTED", "ABANDONED")
                or tuple(sorted(details))
                != control_detail_keys["TERMINATION_SCOPE"]
                or details.get("reason_code") not in (
                    "SCOPE_QUEUE_EXHAUSTED", "MAX_ITER_REACHED"
                )
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")

        if event.parent_event_id is not None:
            parent = events_by_id.get(event.parent_event_id)
            if parent is None or parent.ordinal >= event.ordinal:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            if (
                event.operation_ordinal > 0
                and dict(starts[event.operation_ordinal].details).get("operation_kind")
                != "manufactured_hook"
                and event.kind != "OPERATION_ENDED"
                and parent.operation_ordinal != event.operation_ordinal
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")

    if set(starts) != set(range(1, operation_count + 1)):
        _fail("W2B_INSTRUMENT_TRACE_INVALID")
    first_relations: list[str] = []
    for event in events:
        if event.relation_id is not None and event.relation_id not in first_relations:
            first_relations.append(event.relation_id)
    if first_relations != [
        f"R{ordinal:08d}" for ordinal in range(1, len(first_relations) + 1)
    ]:
        _fail("W2B_INSTRUMENT_TRACE_INVALID")
    if len(budget_events) > 1 or len(run_terminations) > 1 or len(error_events) > 1:
        _fail("W2B_INSTRUMENT_TRACE_INVALID")
    if set(solver_invocations) != set(solver_results):
        _fail("W2B_INSTRUMENT_TRACE_INVALID")

    for operation, start in starts.items():
        end = ends.get(operation)
        kinds = tuple(event.kind for event in payloads[operation])
        operation_kind = dict(start.details)["operation_kind"]
        event_slots = dict(start.details)["event_slots"]
        if end is None:
            if halted:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            continue
        end_reason = dict(end.details).get("reason_code")
        if (
            dict(end.details).get("payload_events") != len(kinds)
            or len(kinds) > event_slots
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        incomplete_terminal = (
            len(kinds) < event_slots
            and (
                (
                    end_reason in (
                        "W2B_INSTRUMENT_EVENT_BUDGET",
                        "W2B_INSTRUMENT_OPERATION_BUDGET",
                    )
                    and end.outcome == "ABANDONED"
                    and end.exception_type is None
                )
                or (
                    end_reason is not None
                    and end.outcome == "FAILED"
                    and end.exception_type is not None
                )
            )
        )
        if not kinds:
            if not incomplete_terminal:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
        elif operation_kind == "zpf_backtrack":
            if (
                len(kinds) < 3
                or kinds[0] != "BACKTRACK"
                or kinds[-2:] != ("ZPF_LINE_TRANSITION", "ZPF_RELATION")
                or any(kind != "ZPF_POINT_DELETED" for kind in kinds[1:-2])
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
        elif operation_kind == "metastable_discard":
            if (
                len(kinds) < 1
                or kinds[0] != "METASTABLE_LINE_DISCARD"
                or any(kind != "ZPF_POINT_DELETED" for kind in kinds[1:])
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
        elif kinds not in payload_rules[operation_kind]:
            if not incomplete_terminal:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if kinds and not incomplete_terminal and end.outcome != payloads[operation][-1].outcome:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if operation_kind == "solver_invocation":
            invocation, result = payloads[operation]
            if result.parent_event_id != invocation.event_id:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")

    if metadata.execution_context != "MANUFACTURED_TEST_ONLY":
        provenance_status = metadata.strategy_state_provenance_status
        mapping_evidence = tuple(
            event for event in events
            if event.kind in ("START_POINT_SCAN", "SOLVER_INVOCATION")
        )
        if provenance_status not in (
            "TERMINAL_OBSERVED", "TERMINAL_INVALID", "PRE_RUN_INVALID"
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if provenance_status == "PRE_RUN_INVALID" and (
            not error_events or mapping_evidence
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if provenance_status == "TERMINAL_INVALID" and not error_events:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if budget_events and provenance_status != "TERMINAL_OBSERVED":
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if any(
            event.outcome in ("ACCEPTED", "ABANDONED")
            for event in run_terminations
        ) and provenance_status != "TERMINAL_OBSERVED":
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if any(event.outcome == "ACCEPTED" for event in run_terminations):
            evidence_kinds = {event.kind for event in mapping_evidence}
            if evidence_kinds != {"START_POINT_SCAN", "SOLVER_INVOCATION"}:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")

    # RUN terminal modes are exclusive.  A budget stop is one exact final
    # sentinel; a failed run is one bound ERROR optionally followed by its
    # matching failed TERMINATION; a non-failed run has neither ERROR nor
    # BUDGET_EXHAUSTED anywhere in its chronology.
    if budget_events:
        budget = budget_events[0]
        details = dict(budget.details)
        reason = details["reason_code"]
        retained = details["retained_count"]
        reserved = details["reserved_count"]
        attempted = details["attempted_unit_size"]
        usable_limit = metadata.event_budget - 2
        terminal_closes = events[retained:budget.ordinal]
        if (
            not halted
            or budget is not events[-1]
            or run_terminations
            or error_events
            or terminal_reason != reason
            or retained + reserved > usable_limit
            or budget.ordinal != retained + len(terminal_closes)
            or any(
                event.kind != "OPERATION_ENDED"
                or event.outcome != "ABANDONED"
                or event.exception_type is not None
                or dict(event.details).get("reason_code") != reason
                for event in terminal_closes
            )
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        reconstructed_reserved = 0
        for close in terminal_closes:
            start = starts.get(close.operation_ordinal)
            if start is None:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            declared = dict(start.details)["event_slots"]
            retained_payloads = sum(
                1
                for event in events[:retained]
                if event.operation_ordinal == close.operation_ordinal
                and event.kind not in ("OPERATION_STARTED", "OPERATION_ENDED")
            )
            if retained_payloads > declared:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            reconstructed_reserved += declared - retained_payloads + 1
        if reconstructed_reserved != reserved:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if reason == "W2B_INSTRUMENT_OPERATION_BUDGET":
            if operation_count != metadata.operation_budget or attempted != 1:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
        elif retained + reserved + attempted <= usable_limit:
            # The rejected atomic unit must cross the exact usable boundary
            # at the pre-close snapshot, including every outer reservation.
            _fail("W2B_INSTRUMENT_TRACE_INVALID")

    if error_events:
        error = error_events[0]
        parent = events_by_id.get(error.parent_event_id or "")
        if (
            not halted
            or budget_events
            or parent is None
            or parent.kind != "OPERATION_ENDED"
            or parent.outcome != "FAILED"
            or parent.ordinal != error.ordinal - 1
            or parent.exception_type != error.exception_type
            or parent.exception_message_sha256 != error.exception_message_sha256
            or dict(error.details).get("reason_code") != terminal_reason
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if run_terminations:
            terminal = run_terminations[0]
            if (
                error.ordinal != terminal.ordinal - 1
                or terminal is not events[-1]
                or terminal.outcome != "FAILED"
                or dict(terminal.details).get("reason_code") != terminal_reason
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
        elif error is not events[-1]:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")

    if run_terminations and not error_events:
        terminal = run_terminations[0]
        expected = None
        if terminal.outcome == "ACCEPTED":
            expected = (
                "MANUFACTURED_HOOKS_ENDED"
                if metadata.execution_context == "MANUFACTURED_TEST_ONLY"
                else "QUEUE_EXHAUSTED"
            )
        elif terminal.outcome == "ABANDONED":
            expected = "ITERATION_BOUND_REACHED"
        if (
            budget_events
            or terminal is not events[-1]
            or expected is None
            or dict(terminal.details) != {
                "reason_code": expected,
                "completion_claim": False,
            }
            or terminal_reason != expected
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")

    if halted:
        if terminal_reason == "RUNNING" or set(ends) != set(starts):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        last = events[-1]
        if (
            last.kind not in ("ERROR", "BUDGET_EXHAUSTED", "TERMINATION")
            or last.operation_ordinal != 0
            or dict(last.details).get("reason_code") != terminal_reason
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if last.kind == "TERMINATION" and last.stage != "RUN":
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if last.kind == "TERMINATION":
            matching_errors = [
                event for event in error_events
                if dict(event.details).get("reason_code") == terminal_reason
            ]
            if last.outcome == "FAILED":
                if (
                    len(matching_errors) != 1
                    or matching_errors[0].ordinal != last.ordinal - 1
                ):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
            elif matching_errors:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
        elif last.kind == "ERROR" and last.outcome != "FAILED":
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
    elif terminal_reason != "RUNNING" or run_terminations or budget_events or error_events:
        _fail("W2B_INSTRUMENT_TRACE_INVALID")


@dataclass(frozen=True, slots=True)
class InstrumentationTrace:
    metadata: TraceMetadata
    operation_count: int
    events: tuple[InstrumentationEvent, ...]
    halted: bool
    terminal_reason: str
    canonical_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if _OPERATIONAL_PROVENANCE_AUTHORITY(
            "trace_registered", self
        ) is True:
            return
        _HELPER_TRUST_VERIFY(deep=False)
        try:
            metadata = _copy_metadata(object.__getattribute__(self, "metadata"))
            operation_count = object.__getattribute__(self, "operation_count")
            event_values = object.__getattribute__(self, "events")
            halted = object.__getattribute__(self, "halted")
            terminal_reason = object.__getattribute__(self, "terminal_reason")
            object.__setattr__(self, "metadata", metadata)
            if (
                type(operation_count) is not int
                or not 0 <= operation_count <= metadata.operation_budget
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            if (
                type(event_values) is not tuple
                or not event_values
                or len(event_values) > metadata.event_budget
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            rebuilt = tuple(_copy_event(event) for event in event_values)
            if tuple(event.ordinal for event in rebuilt) != tuple(range(len(rebuilt))):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            for event in rebuilt:
                if event.operation_ordinal > operation_count:
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
            if type(halted) is not bool:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            _strict_text(terminal_reason, token=True)
            _validate_trace_semantics(
                metadata, operation_count, rebuilt, halted, terminal_reason
            )
            object.__setattr__(self, "events", rebuilt)
            authority = _HELPER_TRUST_VERIFY(deep=False)[1]
            payload = {
                "schema_version": authority["TRACE_SCHEMA"],
                "metadata": metadata.as_dict(),
                "operation_count": operation_count,
                "event_count": len(rebuilt),
                "halted": halted,
                "terminal_reason": terminal_reason,
                "events": [event.as_dict() for event in rebuilt],
                "acceptance_claim": False,
                "counts_toward_feature_coverage": False,
                "production_use": "DENIED",
            }
            object.__setattr__(
                self, "canonical_digest", canonical_trace_digest(payload)
            )
            if metadata.execution_context == EXECUTION_MODE:
                _OPERATIONAL_PROVENANCE_AUTHORITY("trace_constructed", self)
        except Exception as error:
            if (
                isinstance(error, MappingInstrumentationError)
                and error.reason_code in (
                    "W2B_INSTRUMENT_TRACE_INVALID",
                    "W2B_INSTRUMENT_SOURCE_MISMATCH",
                    "W2B_INSTRUMENT_UPSTREAM_MISMATCH",
                )
            ):
                raise
            raise MappingInstrumentationError("W2B_INSTRUMENT_TRACE_INVALID") from error

    def _payload(self) -> dict[str, object]:
        try:
            return _validated_trace_payload(
                self, require_halted=False
            )[5]
        except Exception as error:
            if (
                isinstance(error, MappingInstrumentationError)
                and error.reason_code in (
                    "W2B_INSTRUMENT_TRACE_INVALID",
                    "W2B_INSTRUMENT_SOURCE_MISMATCH",
                    "W2B_INSTRUMENT_UPSTREAM_MISMATCH",
                )
            ):
                raise
            raise MappingInstrumentationError("W2B_INSTRUMENT_TRACE_INVALID") from error

    def as_dict(self) -> dict[str, object]:
        _HELPER_TRUST_VERIFY(deep=False)
        try:
            (
                _metadata, _operation_count, _events, _halted,
                _terminal_reason, payload, original_digest,
            ) = _validated_trace_payload(self, require_halted=False)
            payload["canonical_digest"] = original_digest
            return payload
        except Exception as error:
            if (
                isinstance(error, MappingInstrumentationError)
                and error.reason_code in (
                    "W2B_INSTRUMENT_TRACE_INVALID",
                    "W2B_INSTRUMENT_SOURCE_MISMATCH",
                    "W2B_INSTRUMENT_UPSTREAM_MISMATCH",
                )
            ):
                raise
            raise MappingInstrumentationError("W2B_INSTRUMENT_TRACE_INVALID") from error

    def canonical_bytes(self) -> bytes:
        return trace_json_bytes(self)

    def __reduce__(self):
        registered = _OPERATIONAL_PROVENANCE_AUTHORITY(
            "trace_registered", self
        )
        metadata = object.__getattribute__(self, "metadata")
        if (
            registered is True
            or object.__getattribute__(metadata, "execution_context")
            == EXECUTION_MODE
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        _validated_trace_payload(self, require_halted=False)
        return (
            InstrumentationTrace,
            (
                metadata,
                object.__getattribute__(self, "operation_count"),
                object.__getattribute__(self, "events"),
                object.__getattribute__(self, "halted"),
                object.__getattribute__(self, "terminal_reason"),
            ),
        )

    def __reduce_ex__(self, protocol: object):
        if type(protocol) is not int or protocol < 0:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return InstrumentationTrace.__reduce__(self)

    def __copy__(self):
        constructor, arguments = InstrumentationTrace.__reduce__(self)
        return constructor(*arguments)

    def __deepcopy__(self, memo: object):
        if type(memo) is not dict:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return InstrumentationTrace.__copy__(self)


def _validated_trace_payload(
    trace: object,
    *,
    require_halted: bool,
) -> tuple[object, ...]:
    if type(trace) is not InstrumentationTrace or type(require_halted) is not bool:
        _fail("W2B_INSTRUMENT_TRACE_INVALID")
    try:
        trace_registered = _OPERATIONAL_PROVENANCE_AUTHORITY(
            "trace_registered", trace
        )
        metadata = _copy_metadata(object.__getattribute__(trace, "metadata"))
        if (
            trace_registered is not True
            and _OPERATIONAL_PROVENANCE_AUTHORITY(
                "metadata_registered", metadata
            ) is True
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        operation_count = object.__getattribute__(trace, "operation_count")
        event_values = object.__getattribute__(trace, "events")
        halted = object.__getattribute__(trace, "halted")
        terminal_reason = object.__getattribute__(trace, "terminal_reason")
        original_digest = object.__getattribute__(trace, "canonical_digest")
        if (
            type(operation_count) is not int
            or not 0 <= operation_count <= metadata.operation_budget
            or type(event_values) is not tuple
            or not event_values
            or len(event_values) > metadata.event_budget
            or type(halted) is not bool
            or (require_halted and halted is not True)
            or type(original_digest) is not str
            or _SHA256.fullmatch(original_digest) is None
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        events = tuple(_copy_event(event) for event in event_values)
        if tuple(event.ordinal for event in events) != tuple(range(len(events))):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if any(event.operation_ordinal > operation_count for event in events):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        _strict_text(terminal_reason, token=True)
        _validate_trace_semantics(
            metadata, operation_count, events, halted, terminal_reason
        )
        authority = _HELPER_TRUST_VERIFY(deep=False)[1]
        payload = {
            "schema_version": authority["TRACE_SCHEMA"],
            "metadata": metadata.as_dict(),
            "operation_count": operation_count,
            "event_count": len(events),
            "halted": halted,
            "terminal_reason": terminal_reason,
            "events": [event.as_dict() for event in events],
            "acceptance_claim": False,
            "counts_toward_feature_coverage": False,
            "production_use": "DENIED",
        }
        if canonical_trace_digest(payload) != original_digest:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return (
            metadata, operation_count, events, halted, terminal_reason,
            payload, original_digest,
        )
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_TRACE_INVALID") from error


def _copy_event(value: object) -> InstrumentationEvent:
    if type(value) is not InstrumentationEvent:
        _fail("W2B_INSTRUMENT_TRACE_INVALID")
    try:
        return InstrumentationEvent(
            ordinal=value.ordinal,
            event_id=value.event_id,
            operation_ordinal=value.operation_ordinal,
            kind=value.kind,
            stage=value.stage,
            requested_conditions=value.requested_conditions,
            resolved_coordinates=value.resolved_coordinates,
            phases=value.phases,
            phase_instances=value.phase_instances,
            exception_type=value.exception_type,
            exception_message_sha256=value.exception_message_sha256,
            parent_event_id=value.parent_event_id,
            relation_id=value.relation_id,
            outcome=value.outcome,
            details=value.details,
        )
    except Exception as error:
        if (
            isinstance(error, MappingInstrumentationError)
            and error.reason_code in (
                "W2B_INSTRUMENT_SOURCE_MISMATCH",
                "W2B_INSTRUMENT_UPSTREAM_MISMATCH",
            )
        ):
            raise
        raise MappingInstrumentationError("W2B_INSTRUMENT_TRACE_INVALID") from error


def _copy_upstream(value: object) -> UpstreamSourceMetadata:
    if type(value) is not UpstreamSourceMetadata:
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
    try:
        return UpstreamSourceMetadata(
            package=value.package,
            version=value.version,
            package_root_sha256=value.package_root_sha256,
            license_sha256=value.license_sha256,
            sources=value.sources,
        )
    except MappingInstrumentationError:
        raise
    except Exception as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_ARGUMENT_INVALID") from error


def _copy_metadata(value: object) -> TraceMetadata:
    if type(value) is not TraceMetadata:
        _fail("W2B_INSTRUMENT_TRACE_INVALID")
    try:
        if _OPERATIONAL_PROVENANCE_AUTHORITY(
            "metadata_registered", value
        ) is True:
            return value
        return TraceMetadata(
            feature_id=value.feature_id,
            execution_context=value.execution_context,
            family=value.family,
            profile=value.profile,
            profile_role=value.profile_role,
            domain_receipt_digest=value.domain_receipt_digest,
            profile_receipt_digest=value.profile_receipt_digest,
            execution_snapshot_digest=value.execution_snapshot_digest,
            runtime_sha256=value.runtime_sha256,
            strategy_state_initial_sha256=(
                value.strategy_state_initial_sha256
            ),
            strategy_state_terminal_sha256=(
                value.strategy_state_terminal_sha256
            ),
            strategy_state_provenance_status=(
                value.strategy_state_provenance_status
            ),
            effective_phases=value.effective_phases,
            operation_budget=value.operation_budget,
            event_budget=value.event_budget,
            instrumentation_source_sha256=value.instrumentation_source_sha256,
            upstream=_copy_upstream(value.upstream),
        )
    except Exception as error:
        if (
            isinstance(error, MappingInstrumentationError)
            and error.reason_code in (
                "W2B_INSTRUMENT_SOURCE_MISMATCH",
            )
        ):
            raise
        raise MappingInstrumentationError("W2B_INSTRUMENT_TRACE_INVALID") from error


def trace_json_bytes(trace: object) -> bytes:
    helper_verifier = _HELPER_TRUST_VERIFY
    helper_verifier(deep=True)
    try:
        (
            metadata, _operation_count, _events, _halted,
            _terminal_reason, payload, original_digest,
        ) = _validated_trace_payload(trace, require_halted=True)
    except Exception as error:
        if (
            isinstance(error, MappingInstrumentationError)
            and error.reason_code in (
                "W2B_INSTRUMENT_TRACE_INVALID",
                "W2B_INSTRUMENT_SOURCE_MISMATCH",
                "W2B_INSTRUMENT_UPSTREAM_MISMATCH",
            )
        ):
            raise
        raise MappingInstrumentationError("W2B_INSTRUMENT_TRACE_INVALID") from error
    if metadata.instrumentation_source_sha256 != verify_instrumentation_source():
        _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
    actual_upstream = verify_pinned_pycalphad()
    _verify_runtime_primitive_manifest()
    if metadata.upstream.as_dict() != actual_upstream.as_dict():
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    payload = canonical_trace_bytes(payload)
    if sha256(payload).hexdigest() != original_digest:
        _fail("W2B_INSTRUMENT_TRACE_INVALID")
    helper_verifier(deep=True)
    return payload


def _metadata_with_strategy_state(
    recorder: object,
    metadata: object,
    initial_sha256: object,
    terminal_sha256: object,
    status: object,
) -> TraceMetadata:
    if type(recorder) is not _TraceRecorder or type(metadata) is not TraceMetadata:
        _fail("W2B_INSTRUMENT_TRACE_INVALID")
    _strict_sha(initial_sha256)
    _strict_sha(terminal_sha256)
    _strict_text(status, token=True)
    try:
        registered = _OPERATIONAL_PROVENANCE_AUTHORITY(
            "recorder_registered", recorder
        )
        if registered is True:
            return _OPERATIONAL_PROVENANCE_AUTHORITY(
                "derive_metadata",
                recorder,
                initial_sha256,
                terminal_sha256,
                status,
                metadata,
            )
        if (
            _OPERATIONAL_PROVENANCE_AUTHORITY(
                "metadata_registered", metadata
            ) is True
            or object.__getattribute__(metadata, "execution_context")
            == EXECUTION_MODE
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return TraceMetadata(
            feature_id=metadata.feature_id,
            execution_context=metadata.execution_context,
            family=metadata.family,
            profile=metadata.profile,
            profile_role=metadata.profile_role,
            domain_receipt_digest=metadata.domain_receipt_digest,
            profile_receipt_digest=metadata.profile_receipt_digest,
            execution_snapshot_digest=metadata.execution_snapshot_digest,
            runtime_sha256=metadata.runtime_sha256,
            strategy_state_initial_sha256=initial_sha256,
            strategy_state_terminal_sha256=terminal_sha256,
            strategy_state_provenance_status=status,
            effective_phases=metadata.effective_phases,
            operation_budget=metadata.operation_budget,
            event_budget=metadata.event_budget,
            instrumentation_source_sha256=metadata.instrumentation_source_sha256,
            upstream=metadata.upstream,
        )
    except MappingInstrumentationError:
        raise
    except Exception as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_TRACE_INVALID") from error


class _TraceRecorder:
    """Append-only recorder with atomic logical-operation reservations."""

    __slots__ = (
        "__weakref__",
        "metadata",
        "events",
        "operation_count",
        "relation_count",
        "halted",
        "terminal_reason",
        "_object_ids",
        "_object_counts",
        "_reservations",
        "_active_operations",
        "_reserved_events",
        "_runtime_guard",
    )

    def __init__(self, metadata: TraceMetadata):
        authority = _HELPER_TRUST_VERIFY(deep=True)[1]
        if type(metadata) is not TraceMetadata:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        metadata_registered = _OPERATIONAL_PROVENANCE_AUTHORITY(
            "metadata_registered", metadata
        )
        self.metadata = metadata
        self.events: list[InstrumentationEvent] = []
        self.operation_count = 0
        self.relation_count = 0
        self.halted = False
        self.terminal_reason = "RUNNING"
        # Retain a strong reference with each token. An id-only table can
        # silently alias a later object after CPython reuses a released id.
        self._object_ids: dict[tuple[str, int], tuple[object, str]] = {}
        self._object_counts: dict[str, int] = {}
        self._reservations: dict[int, dict[str, object]] = {}
        self._active_operations: list[int] = []
        self._reserved_events = 0
        self._runtime_guard = None
        if (
            metadata_registered is True
            or object.__getattribute__(metadata, "execution_context")
            == EXECUTION_MODE
        ):
            _OPERATIONAL_PROVENANCE_AUTHORITY(
                "recorder_constructed", self, metadata
            )
        self._append(
            kind="TRACE_STARTED",
            stage="TRACE",
            operation_ordinal=0,
            outcome="ACCEPTED",
            details={
                "instrumentation_version": authority["INSTRUMENTATION_VERSION"],
                "upstream_version": authority["PYCALPHAD_VERSION"],
            },
            terminal=True,
        )

    def bind_runtime_guard(self, guard: object) -> None:
        if self._runtime_guard is not None or not callable(guard):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        guard(deep=True)
        self._runtime_guard = guard
        self._verify_runtime_guard(deep=True)

    def bind_strategy_state_provenance(
        self,
        initial_sha256: object,
        terminal_sha256: object,
        status: object,
    ) -> None:
        self._verify_runtime_guard(deep=True)
        zero = "0" * 64
        current = self.metadata
        if type(status) is not str:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if status == "PRISTINE_BOUND":
            if (
                current.strategy_state_provenance_status != "FACTORY_PENDING"
                or current.strategy_state_initial_sha256 != zero
                or current.strategy_state_terminal_sha256 != zero
                or terminal_sha256 != zero
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
        elif status in (
            "TERMINAL_OBSERVED", "TERMINAL_INVALID", "PRE_RUN_INVALID"
        ):
            if (
                current.strategy_state_provenance_status != "PRISTINE_BOUND"
                or initial_sha256 != current.strategy_state_initial_sha256
                or current.strategy_state_terminal_sha256 != zero
            ):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
        else:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        self.metadata = _metadata_with_strategy_state(
            self, current, initial_sha256, terminal_sha256, status
        )

    def _verify_runtime_guard(self, *, deep: bool = False) -> Mapping[str, object]:
        metadata = object.__getattribute__(self, "metadata")
        registered = _OPERATIONAL_PROVENANCE_AUTHORITY(
            "recorder_registered", self
        )
        if registered is not True and (
            _OPERATIONAL_PROVENANCE_AUTHORITY(
                "metadata_registered", metadata
            ) is True
            or object.__getattribute__(metadata, "execution_context")
            == EXECUTION_MODE
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        guard = self._runtime_guard
        if guard is not None:
            authority = guard(deep=deep)
        else:
            authority = _HELPER_TRUST_VERIFY(deep=deep)[1]
        if not isinstance(authority, Mapping):
            _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
        return authority

    def object_token(self, kind: str, value: object) -> str:
        self._verify_runtime_guard()
        key = (kind, id(value))
        retained = self._object_ids.get(key)
        if retained is None:
            count = self._object_counts.get(kind, 0) + 1
            self._object_counts[kind] = count
            token = f"{kind}:{count:08d}"
            self._object_ids[key] = (value, token)
            return token
        retained_object, token = retained
        if retained_object is not value:
            # Unreachable while the strong reference is retained; fail closed
            # if a non-standard runtime violates that identity invariant.
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return token

    def relation(self) -> str:
        self._verify_runtime_guard()
        self.relation_count += 1
        return f"R{self.relation_count:08d}"

    def begin_operation(
        self,
        kind: str,
        stage: str,
        *,
        conditions: Mapping[object, object] | None = None,
        parent_event_id: str | None = None,
        relation_id: str | None = None,
        details: Mapping[str, object] | None = None,
        event_slots: int,
    ) -> int:
        authority = self._verify_runtime_guard(deep=True)
        if self.halted:
            reason = (
                self.terminal_reason
                if self.terminal_reason in (
                    "W2B_INSTRUMENT_OPERATION_BUDGET",
                    "W2B_INSTRUMENT_EVENT_BUDGET",
                )
                else "W2B_INSTRUMENT_OPERATION_BUDGET"
            )
            raise InstrumentationBudgetExceeded(reason)
        if (
            kind not in authority["_OPERATION_PAYLOAD_RULES"]
            or
            type(event_slots) is not int
            or isinstance(event_slots, bool)
            or not 1 <= event_slots <= self.metadata.event_budget
        ):
            _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        if self.operation_count >= self.metadata.operation_budget:
            self._budget(
                "W2B_INSTRUMENT_OPERATION_BUDGET", stage,
                attempted_event_slots=1,
            )
            raise InstrumentationBudgetExceeded("W2B_INSTRUMENT_OPERATION_BUDGET")
        # One start, all declared payload events and one end must fit while
        # preserving two terminal slots (budget/error or error/termination).
        required = 1 + event_slots + 1
        if (
            len(self.events) + self._reserved_events + required
            > self.metadata.event_budget - 2
        ):
            self._budget(
                "W2B_INSTRUMENT_EVENT_BUDGET", stage,
                attempted_event_slots=required,
            )
            raise InstrumentationBudgetExceeded("W2B_INSTRUMENT_EVENT_BUDGET")
        operation = self.operation_count + 1
        start_event_id = self._append(
            kind="OPERATION_STARTED",
            stage=stage,
            operation_ordinal=operation,
            requested_conditions=_condition_pairs(conditions),
            parent_event_id=parent_event_id,
            relation_id=relation_id,
            outcome="ACCEPTED",
            details={
                "operation_kind": kind,
                "event_slots": event_slots,
                **(dict(details or {})),
            },
            terminal=False,
        )
        self.operation_count = operation
        self._reservations[operation] = {
            "operation_kind": kind,
            "stage": stage,
            "start_event_id": start_event_id,
            "relation_id": relation_id,
            "payload_remaining": event_slots,
        }
        self._active_operations.append(operation)
        self._reserved_events += event_slots + 1
        return operation

    def emit(
        self,
        kind: str,
        stage: str,
        *,
        operation_ordinal: int = 0,
        requested_conditions: Sequence[tuple[str, object]] = (),
        resolved_coordinates: Sequence[tuple[str, object]] | None = None,
        phases: Sequence[str] = (),
        phase_instances: Sequence[str] = (),
        exception: BaseException | None = None,
        parent_event_id: str | None = None,
        relation_id: str | None = None,
        outcome: str,
        details: Mapping[str, object] | None = None,
    ) -> str:
        self._verify_runtime_guard()
        if self.halted:
            reason = (
                self.terminal_reason
                if self.terminal_reason in (
                    "W2B_INSTRUMENT_OPERATION_BUDGET",
                    "W2B_INSTRUMENT_EVENT_BUDGET",
                )
                else "W2B_INSTRUMENT_EVENT_BUDGET"
            )
            raise InstrumentationBudgetExceeded(reason)
        if kind in ("OPERATION_STARTED", "OPERATION_ENDED"):
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        if type(operation_ordinal) is not int or isinstance(operation_ordinal, bool):
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        reservation = None
        if operation_ordinal > 0:
            reservation = self._reservations.get(operation_ordinal)
            if reservation is None or reservation["payload_remaining"] <= 0:
                # Exceeding a declared logical-unit reservation is an invalid
                # producer call, not evidence that the trace-wide event
                # capacity was exhausted.
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
        elif (
            len(self.events) + self._reserved_events
            >= self.metadata.event_budget - 2
        ):
            self._budget(
                "W2B_INSTRUMENT_EVENT_BUDGET", stage,
                attempted_event_slots=1,
            )
            raise InstrumentationBudgetExceeded("W2B_INSTRUMENT_EVENT_BUDGET")
        event_id = self._append(
            kind=kind,
            stage=stage,
            operation_ordinal=operation_ordinal,
            requested_conditions=requested_conditions,
            resolved_coordinates=resolved_coordinates,
            phases=phases,
            phase_instances=phase_instances,
            exception=exception,
            parent_event_id=parent_event_id,
            relation_id=relation_id,
            outcome=outcome,
            details=details,
            terminal=False,
        )
        if reservation is not None:
            reservation["payload_remaining"] -= 1
            self._reserved_events -= 1
        return event_id

    def end_operation(
        self,
        operation_ordinal: int,
        *,
        outcome: str,
        exception: BaseException | None = None,
        details: Mapping[str, object] | None = None,
    ) -> str:
        self._verify_runtime_guard(deep=True)
        if self.halted:
            reason = (
                self.terminal_reason
                if self.terminal_reason in (
                    "W2B_INSTRUMENT_OPERATION_BUDGET",
                    "W2B_INSTRUMENT_EVENT_BUDGET",
                )
                else "W2B_INSTRUMENT_EVENT_BUDGET"
            )
            raise InstrumentationBudgetExceeded(reason)
        reservation = self._reservations.get(operation_ordinal)
        if reservation is None or operation_ordinal not in self._active_operations:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        payload_remaining = int(reservation["payload_remaining"])
        event_id = self._append(
            kind="OPERATION_ENDED",
            stage=str(reservation["stage"]),
            operation_ordinal=operation_ordinal,
            exception=exception,
            parent_event_id=str(reservation["start_event_id"]),
            relation_id=reservation["relation_id"],
            outcome=outcome,
            details={
                "operation_kind": reservation["operation_kind"],
                "event_slots": (
                    int(reservation["payload_remaining"]) +
                    sum(
                        1
                        for event in self.events
                        if event.operation_ordinal == operation_ordinal
                        and event.kind not in ("OPERATION_STARTED", "OPERATION_ENDED")
                    )
                ),
                "payload_events": sum(
                    1
                    for event in self.events
                    if event.operation_ordinal == operation_ordinal
                    and event.kind not in ("OPERATION_STARTED", "OPERATION_ENDED")
                ),
                **(dict(details or {})),
            },
            terminal=False,
        )
        self._reserved_events -= payload_remaining + 1
        del self._reservations[operation_ordinal]
        self._active_operations.remove(operation_ordinal)
        return event_id

    def _append(
        self,
        *,
        kind: str,
        stage: str,
        operation_ordinal: int,
        requested_conditions: Sequence[tuple[str, object]] = (),
        resolved_coordinates: Sequence[tuple[str, object]] | None = None,
        phases: Sequence[str] = (),
        phase_instances: Sequence[str] = (),
        exception: BaseException | None = None,
        parent_event_id: str | None = None,
        relation_id: str | None = None,
        outcome: str,
        details: Mapping[str, object] | None = None,
        terminal: bool,
    ) -> str:
        self._verify_runtime_guard()
        if len(self.events) >= self.metadata.event_budget:
            raise InstrumentationBudgetExceeded("W2B_INSTRUMENT_EVENT_BUDGET")
        ordinal = len(self.events)
        exception_type = None
        exception_digest = None
        if exception is not None:
            exception_type = f"{type(exception).__module__}.{type(exception).__qualname__}"
            exception_digest = _exception_message_digest(exception)
        event = InstrumentationEvent(
            ordinal=ordinal,
            event_id=f"E{ordinal:08d}",
            operation_ordinal=operation_ordinal,
            kind=kind,
            stage=stage,
            requested_conditions=tuple(requested_conditions),
            resolved_coordinates=(
                None if resolved_coordinates is None else tuple(resolved_coordinates)
            ),
            phases=tuple(phases),
            phase_instances=tuple(phase_instances),
            exception_type=exception_type,
            exception_message_sha256=exception_digest,
            parent_event_id=parent_event_id,
            relation_id=relation_id,
            outcome=outcome,
            details=tuple(sorted((details or {}).items())),
        )
        self.events.append(event)
        return event.event_id

    def _budget(
        self,
        reason: str,
        stage: str,
        *,
        attempted_event_slots: int,
    ) -> None:
        self._verify_runtime_guard()
        if self.halted:
            return
        # Preserve the exact rejection boundary before closing any nested
        # operations.  Their reserved payload/end slots remain material to
        # proving that the attempted atomic unit could not fit.
        retained_count = len(self.events)
        reserved_count = self._reserved_events
        self._close_open_operations(reason, outcome="ABANDONED")
        if len(self.events) < self.metadata.event_budget:
            self._append(
                kind="BUDGET_EXHAUSTED",
                stage=stage,
                operation_ordinal=0,
                outcome="ABANDONED",
                details={
                    "reason_code": reason,
                    "operation_budget": self.metadata.operation_budget,
                    "event_budget": self.metadata.event_budget,
                    "operation_count_at_exhaustion": self.operation_count,
                    "retained_count": retained_count,
                    "reserved_count": reserved_count,
                    "attempted_unit_size": attempted_event_slots,
                },
                terminal=True,
            )
        self.halted = True
        self.terminal_reason = reason

    def _close_open_operations(
        self,
        reason: str,
        *,
        outcome: str,
        exception: BaseException | None = None,
    ) -> tuple[str, ...]:
        closed: list[str] = []
        for operation in tuple(reversed(self._active_operations)):
            reservation = self._reservations[operation]
            closed.append(self._append(
                kind="OPERATION_ENDED",
                stage=str(reservation["stage"]),
                operation_ordinal=operation,
                exception=exception,
                parent_event_id=str(reservation["start_event_id"]),
                relation_id=reservation["relation_id"],
                outcome=outcome,
                details={
                    "operation_kind": reservation["operation_kind"],
                    "event_slots": int(reservation["payload_remaining"]) + sum(
                        1
                        for event in self.events
                        if event.operation_ordinal == operation
                        and event.kind not in ("OPERATION_STARTED", "OPERATION_ENDED")
                    ),
                    "payload_events": sum(
                        1
                        for event in self.events
                        if event.operation_ordinal == operation
                        and event.kind not in ("OPERATION_STARTED", "OPERATION_ENDED")
                    ),
                    "reason_code": reason,
                },
                terminal=True,
            ))
            self._reserved_events -= int(reservation["payload_remaining"]) + 1
            del self._reservations[operation]
            self._active_operations.remove(operation)
        return tuple(closed)

    def _bind_terminal_failure(
        self,
        reason: str,
        error: BaseException,
        closed: tuple[str, ...],
    ) -> str:
        expected_type = f"{type(error).__module__}.{type(error).__qualname__}"
        expected_digest = _exception_message_digest(error)
        if closed:
            candidate = self.events[-1]
            if (
                candidate.event_id == closed[-1]
                and candidate.kind == "OPERATION_ENDED"
                and candidate.outcome == "FAILED"
                and candidate.exception_type == expected_type
                and candidate.exception_message_sha256 == expected_digest
            ):
                return candidate.event_id
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        if self.events:
            candidate = self.events[-1]
            if (
                candidate.kind == "OPERATION_ENDED"
                and candidate.outcome == "FAILED"
                and candidate.exception_type == expected_type
                and candidate.exception_message_sha256 == expected_digest
            ):
                return candidate.event_id

        # Pre-operation failures (lease/domain/runtime validation) still need
        # an explicit failed logical operation for the terminal ERROR to bind.
        # Historical/suppressed failures are never reused: this envelope is
        # necessarily the immediate chronological predecessor of ERROR.
        operation = self.begin_operation(
            "runtime_failure",
            "RUNTIME_VALIDATION",
            details={"reason_code": reason},
            event_slots=1,
        )
        self.emit(
            "INVARIANT_CHECK",
            "RUNTIME_VALIDATION",
            operation_ordinal=operation,
            exception=error,
            outcome="FAILED",
            details={"check": "TERMINAL_EXCEPTION", "reason_code": reason},
        )
        return self.end_operation(
            operation,
            outcome="FAILED",
            exception=error,
            details={"reason_code": reason},
        )

    def terminate(self, reason: str, *, outcome: str, exception: BaseException | None = None) -> None:
        self._verify_runtime_guard(deep=True)
        if self.halted:
            return
        if (
            outcome not in ("ACCEPTED", "FAILED", "ABANDONED")
            or (exception is None) == (outcome == "FAILED")
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        closed = self._close_open_operations(
            reason,
            outcome=("FAILED" if exception is not None else "ABANDONED"),
            exception=exception,
        )
        failure_parent = None
        if exception is not None:
            failure_parent = self._bind_terminal_failure(reason, exception, closed)
        if exception is not None and len(self.events) < self.metadata.event_budget:
            self._append(
                kind="ERROR",
                stage="RUN",
                operation_ordinal=0,
                exception=exception,
                parent_event_id=failure_parent,
                outcome="FAILED",
                details={"reason_code": reason},
                terminal=True,
            )
        if len(self.events) < self.metadata.event_budget:
            self._append(
                kind="TERMINATION",
                stage="RUN",
                operation_ordinal=0,
                exception=None,
                outcome=outcome,
                details={"reason_code": reason, "completion_claim": False},
                terminal=True,
            )
        self.halted = True
        self.terminal_reason = reason

    def force_postcondition_failure(self, reason: str, error: BaseException) -> None:
        """Retain a lease/source postcondition failure even after budget stop."""

        # A retained BUDGET_EXHAUSTED sentinel is an exclusive terminal mode.
        # If its postcondition is no longer trustworthy, fail closed instead
        # of appending a contradictory second terminal lifecycle.
        raise MappingInstrumentationError(reason) from error

    def snapshot(self) -> InstrumentationTrace:
        registered = _OPERATIONAL_PROVENANCE_AUTHORITY(
            "recorder_registered", self
        )
        self._verify_runtime_guard(deep=True)
        if registered is True:
            return _OPERATIONAL_PROVENANCE_AUTHORITY("snapshot", self)
        return InstrumentationTrace(
            metadata=self.metadata,
            operation_count=self.operation_count,
            events=tuple(self.events),
            halted=self.halted,
            terminal_reason=self.terminal_reason,
        )


def _condition_pairs(conditions: Mapping[object, object] | None) -> tuple[tuple[str, object], ...]:
    if conditions is None:
        return ()
    pairs: list[tuple[str, object]] = []
    for key, value in conditions.items():
        name = str(key)
        if type(value) in (tuple, list):
            normalized = tuple(_solver_number(item) for item in value)
        else:
            normalized = _solver_number(value)
        pairs.append((name, normalized))
    pairs.sort(key=lambda item: item[0])
    if len({name for name, _ in pairs}) != len(pairs):
        _fail("W2B_INSTRUMENT_EVENT_INVALID")
    return tuple(pairs)


def _solver_number(value: object) -> object:
    if type(value) in (str, bool, int, float) or value is None:
        if type(value) is float and not math.isfinite(value):
            _fail("W2B_INSTRUMENT_EVENT_INVALID")
        return value
    try:
        converted = float(value)  # NumPy scalar, loaded lazily with pycalphad.
    except (TypeError, ValueError, OverflowError):
        return str(value)
    if not math.isfinite(converted):
        _fail("W2B_INSTRUMENT_EVENT_INVALID")
    return converted


def _exception_message_digest(error: BaseException) -> str:
    try:
        message = str(error)
    except BaseException as rendering_error:
        message = (
            "<UNRENDERABLE_EXCEPTION_MESSAGE:"
            f"{type(rendering_error).__module__}."
            f"{type(rendering_error).__qualname__}>"
        )
    return sha256(message.encode("utf-8", errors="replace")).hexdigest()


def _point_observation(strategy: object, point: object | None) -> tuple[
    tuple[tuple[str, object], ...] | None, tuple[str, ...], tuple[str, ...]
]:
    if point is None:
        return None, (), ()
    coordinates: list[tuple[str, object]] = []
    try:
        for axis in getattr(strategy, "axis_vars", ()):
            coordinates.append((str(axis), _solver_number(point.get_property(axis))))
    except Exception:
        return None, (), ()
    phases: tuple[str, ...]
    instances: tuple[str, ...]
    try:
        phases = tuple(sorted({str(item) for item in point.stable_phases}))
    except Exception:
        phases = ()
    try:
        instances = tuple(
            sorted({str(item) for item in point.stable_phases_with_multiplicity})
        )
    except Exception:
        instances = phases
    return tuple(sorted(coordinates)), phases, instances


@dataclass(frozen=True, slots=True)
class ExecutionBinding:
    feature_id: str
    family: str
    profile: str
    profile_role: str
    domain_receipt_digest: str
    profile_receipt_digest: str
    execution_snapshot_digest: str
    runtime_sha256: str
    effective_phases: tuple[str, ...]
    runtime_path: Path = field(repr=False, compare=False)
    _execution_lease: object = field(repr=False, compare=False)
    _pre_snapshot: object = field(repr=False, compare=False)
    _domain_receipt: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        authority = _HELPER_TRUST_VERIFY(deep=False)[1]
        if (
            _strict_text(self.feature_id, token=True)
            not in authority["SUPPORTED_MAPPING_FEATURES"]
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        _strict_text(self.family, token=True)
        _strict_text(self.profile, token=True)
        _strict_text(self.profile_role, token=True)
        if (
            authority["EXECUTION_MODE"], self.family, self.profile,
            self.profile_role,
        ) not in authority["_TRACE_SCOPE_RULES"]:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        _strict_sha(self.domain_receipt_digest)
        _strict_sha(self.profile_receipt_digest)
        _strict_sha(self.execution_snapshot_digest)
        _strict_sha(self.runtime_sha256)
        if type(self.effective_phases) is not tuple:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        phases = _ordered_tokens(self.effective_phases, allow_empty=False)
        object.__setattr__(self, "effective_phases", phases)
        if type(self.runtime_path) is not _CONCRETE_PATH_TYPE:
            _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
        runtime_path_text = os.fspath(self.runtime_path)
        if type(runtime_path_text) is not str or not self.runtime_path.is_absolute():
            _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
        if (
            self._execution_lease is None
            or self._pre_snapshot is None
            or self._domain_receipt is None
        ):
            _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
        if self.family == "fe" and (
            self.profile not in authority["SUPPORTED_FE_PROFILE_IDS"]
            or "C15_LAVES" not in phases
        ):
            _fail("W2B_INSTRUMENT_FE_SCOPE_INVALID")


def bind_execution_context(
    execution_lease: object,
    pre_snapshot: object,
    domain_receipt: object,
    *,
    expected_instrumentation_sha256: object,
) -> ExecutionBinding:
    """Bind instrumentation to one active PRE-window execution lease.

    The function intentionally has no project-path argument.  It accepts only
    the locked snapshot path exposed by ``ExecutionLease.file_path('runtime')``.
    """

    authority = _HELPER_TRUST_VERIFY(deep=True)[1]
    verify_instrumentation_source(expected_instrumentation_sha256)
    try:
        receipts = importlib.import_module("thermogar_wave2b_receipts")
        if (
            type(execution_lease) is not receipts.ExecutionLease
            or type(pre_snapshot) is not receipts.PreExecutionSnapshot
            or type(domain_receipt) is not receipts.DomainReceipt
        ):
            _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
        domain = receipts._rebuild_domain_receipt(domain_receipt)
        pre = receipts._rebuild_pre_snapshot(pre_snapshot)
        profile = domain.profile_receipt
        runtime_path = execution_lease.file_path("runtime")
        if type(runtime_path) is not _CONCRETE_PATH_TYPE:
            _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
        runtime_path_text = os.fspath(runtime_path)
        if type(runtime_path_text) is not str:
            _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
        snapshot_digest = execution_lease.execution_snapshot_digest
    except MappingInstrumentationError:
        raise
    except Exception as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_LEASE_REQUIRED") from error
    if (
        domain.execution_mode != authority["EXECUTION_MODE"]
        or domain.authorization_state != "INTERNAL_QUALIFICATION_ONLY_NOT_RELEASE"
    ):
        _fail("W2B_INSTRUMENT_INTERNAL_ONLY")
    if (
        pre.lease_id != execution_lease.lease_id
        or pre.domain_receipt_digest != domain.canonical_digest
        or pre.profile_receipt_digest != profile.canonical_digest
        or pre.execution_snapshot_digest != snapshot_digest
    ):
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    if profile.family == "fe" and (
        profile.profile not in authority["SUPPORTED_FE_PROFILE_IDS"]
        or profile.baseline_decision != "UNDECIDED_USER_DECISION_REQUIRED"
        or profile.c15_exclusion_decision != "UNDECIDED_USER_DECISION_REQUIRED"
        or "C15_LAVES" not in domain.candidate_phases
        or "C15_LAVES" not in domain.requested_phases
        or "C15_LAVES" in domain.excluded_phases
        or "C15_LAVES" not in domain.effective_phases
    ):
        _fail("W2B_INSTRUMENT_FE_SCOPE_INVALID")
    binding = ExecutionBinding(
        feature_id=domain.feature_id,
        family=profile.family,
        profile=profile.profile,
        profile_role=profile.profile_role,
        domain_receipt_digest=domain.canonical_digest,
        profile_receipt_digest=profile.canonical_digest,
        execution_snapshot_digest=snapshot_digest,
        runtime_sha256=profile.runtime.sha256,
        effective_phases=tuple(domain.effective_phases),
        runtime_path=runtime_path,
        _execution_lease=execution_lease,
        _pre_snapshot=pre_snapshot,
        _domain_receipt=domain_receipt,
    )
    _parse_mapping_request(binding, domain)
    return binding


def _copy_and_validate_active_binding(value: object) -> ExecutionBinding:
    if type(value) is not ExecutionBinding:
        _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
    try:
        rebuilt = ExecutionBinding(
            feature_id=value.feature_id,
            family=value.family,
            profile=value.profile,
            profile_role=value.profile_role,
            domain_receipt_digest=value.domain_receipt_digest,
            profile_receipt_digest=value.profile_receipt_digest,
            execution_snapshot_digest=value.execution_snapshot_digest,
            runtime_sha256=value.runtime_sha256,
            effective_phases=value.effective_phases,
            runtime_path=value.runtime_path,
            _execution_lease=value._execution_lease,
            _pre_snapshot=value._pre_snapshot,
            _domain_receipt=value._domain_receipt,
        )
        receipts = importlib.import_module("thermogar_wave2b_receipts")
        if (
            type(rebuilt._execution_lease) is not receipts.ExecutionLease
            or type(rebuilt._pre_snapshot) is not receipts.PreExecutionSnapshot
            or type(rebuilt._domain_receipt) is not receipts.DomainReceipt
        ):
            _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
        domain = receipts._rebuild_domain_receipt(rebuilt._domain_receipt)
        pre = receipts._rebuild_pre_snapshot(rebuilt._pre_snapshot)
        runtime_path = rebuilt._execution_lease.file_path("runtime")
        if type(runtime_path) is not _CONCRETE_PATH_TYPE:
            _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
        runtime_path_text = os.fspath(runtime_path)
        if type(runtime_path_text) is not str:
            _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
        rebuilt_runtime_path_text = os.fspath(rebuilt.runtime_path)
        if type(rebuilt_runtime_path_text) is not str:
            _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
        snapshot_digest = rebuilt._execution_lease.execution_snapshot_digest
    except MappingInstrumentationError:
        raise
    except Exception as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_LEASE_REQUIRED") from error
    if (
        runtime_path_text != rebuilt_runtime_path_text
        or snapshot_digest != rebuilt.execution_snapshot_digest
        or pre.lease_id != rebuilt._execution_lease.lease_id
        or pre.domain_receipt_digest != rebuilt.domain_receipt_digest
        or pre.profile_receipt_digest != rebuilt.profile_receipt_digest
        or pre.execution_snapshot_digest != rebuilt.execution_snapshot_digest
        or domain.canonical_digest != rebuilt.domain_receipt_digest
        or domain.profile_receipt.canonical_digest != rebuilt.profile_receipt_digest
        or domain.profile_receipt.runtime.sha256 != rebuilt.runtime_sha256
        or domain.feature_id != rebuilt.feature_id
        or domain.profile_receipt.family != rebuilt.family
        or domain.profile_receipt.profile != rebuilt.profile
        or domain.profile_receipt.profile_role != rebuilt.profile_role
        or tuple(domain.effective_phases) != rebuilt.effective_phases
    ):
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    _parse_mapping_request(rebuilt, domain)
    return rebuilt


def _same_binary64(left: object, right: object) -> bool:
    if type(left) not in (int, float) or type(right) not in (int, float):
        return False
    try:
        left_value = float(left)
        right_value = float(right)
    except (TypeError, ValueError, OverflowError):
        return False
    if not math.isfinite(left_value) or not math.isfinite(right_value):
        return False
    return struct.pack(">d", left_value) == struct.pack(">d", right_value)


def _same_condition_value(left: object, right: object) -> bool:
    if type(right) is tuple:
        return (
            type(left) is tuple
            and len(left) == len(right)
            and all(_same_binary64(a, b) for a, b in zip(left, right))
        )
    return _same_binary64(left, right)


def _same_conditions(left: object, right: dict[object, object]) -> bool:
    if type(left) is not dict or type(right) is not dict or len(left) != len(right):
        return False
    left_items = tuple(left.items())
    for expected_key, expected_value in right.items():
        matches = tuple(
            observed_value
            for observed_key, observed_value in left_items
            if observed_key is expected_key
        )
        if (
            len(matches) != 1
            or not _same_condition_value(matches[0], expected_value)
        ):
            return False
    return True


def _strict_mapping_request_mapping(
    value: object,
    expected_keys: tuple[str, ...],
) -> dict[str, object]:
    if type(value) is not dict or type(expected_keys) is not tuple:
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    keys = tuple(value.keys())
    if (
        any(type(key) is not str for key in keys)
        or len(keys) != len(expected_keys)
        or frozenset(keys) != frozenset(expected_keys)
    ):
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    return value


def _strict_primitive_equal(observed: object, expected: object) -> bool:
    if type(observed) is not type(expected):
        return False
    if type(expected) is float:
        return (
            math.isfinite(observed)
            and math.isfinite(expected)
            and struct.pack(">d", observed) == struct.pack(">d", expected)
        )
    if type(expected) is dict:
        observed_keys = tuple(observed.keys())
        expected_keys = tuple(expected.keys())
        if (
            any(type(key) is not str for key in observed_keys)
            or any(type(key) is not str for key in expected_keys)
            or len(observed_keys) != len(expected_keys)
            or frozenset(observed_keys) != frozenset(expected_keys)
        ):
            return False
        return all(
            _strict_primitive_equal(observed[key], expected[key])
            for key in expected_keys
        )
    if type(expected) in (tuple, list):
        return len(observed) == len(expected) and all(
            _strict_primitive_equal(left, right)
            for left, right in zip(observed, expected)
        )
    if expected is None or type(expected) in (bool, int, str):
        return observed == expected
    return False


def _strict_mapping_request_name(value: object) -> str:
    characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_#:+-."
    if (
        type(value) is not str
        or not value
        or len(value) > 64
        or any(character not in characters for character in value)
    ):
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    return value


def _strict_mapping_request_number(value: object, constraint: str) -> float:
    if (
        type(value) is not float
        or type(constraint) is not str
        or constraint not in ("FINITE", "POSITIVE", "NONNEGATIVE", "FRACTION")
        or not math.isfinite(value)
        or (
            value == 0.0
            and struct.pack(">d", value) != struct.pack(">d", 0.0)
        )
    ):
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    if constraint == "POSITIVE" and value <= 0.0:
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    if constraint == "NONNEGATIVE" and value < 0.0:
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    if constraint == "FRACTION" and not 0.0 <= value <= 1.0:
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    return value


def _strict_mapping_request_range(
    value: object,
    *,
    fraction: bool,
    temperature: bool,
) -> tuple[float, float, float]:
    if type(fraction) is not bool or type(temperature) is not bool:
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    card = _strict_mapping_request_mapping(
        value, ("minimum", "maximum", "seed_step")
    )
    lower = _strict_mapping_request_number(
        card["minimum"], "FRACTION" if fraction else "FINITE"
    )
    upper = _strict_mapping_request_number(
        card["maximum"], "FRACTION" if fraction else "FINITE"
    )
    step = _strict_mapping_request_number(card["seed_step"], "POSITIVE")
    width = upper - lower
    if (
        not math.isfinite(width)
        or upper <= lower
        or step > width
        or (temperature and lower <= 0.0)
    ):
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    return lower, upper, step


def _decode_receipt_value(value: object, depth: int = 0) -> object:
    if depth > _MAX_DEPTH:
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    if type(value) is dict:
        keys = tuple(value.keys())
        if any(type(key) is not str for key in keys):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if keys == ("$f64",):
            encoded = value["$f64"]
            if type(encoded) is not str or re.fullmatch(r"[0-9a-f]{16}", encoded) is None:
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            number = struct.unpack(">d", bytes.fromhex(encoded))[0]
            if not math.isfinite(number):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            return number
        return {
            key: _decode_receipt_value(item, depth + 1)
            for key, item in tuple(value.items())
        }
    if type(value) is list:
        return [_decode_receipt_value(item, depth + 1) for item in value]
    return value


def _parse_mapping_request(
    binding: ExecutionBinding,
    domain_receipt: object | None = None,
) -> tuple[object, ...]:
    """Reconstruct one receipt request without coercion or backend imports."""

    if type(binding) is not ExecutionBinding:
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    try:
        if domain_receipt is None:
            receipts = importlib.import_module("thermogar_wave2b_receipts")
            domain = receipts._rebuild_domain_receipt(binding._domain_receipt)
        else:
            domain = domain_receipt
        full_request = _decode_receipt_value(domain.full_request.value())
        bounds = _decode_receipt_value(domain.bounds.value())
        solver_options = _decode_receipt_value(domain.solver_options.value())
        outer = _strict_mapping_request_mapping(
            full_request, ("feature_id", "database", "mapping_request")
        )
        if (
            type(outer["feature_id"]) is not str
            or outer["feature_id"] != binding.feature_id
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        profile = domain.profile_receipt
        expected_database = {
            "family": binding.family,
            "profile": binding.profile,
            "runtime_sha256": binding.runtime_sha256,
            "profile_receipt_digest": binding.profile_receipt_digest,
            "baseline_decision": profile.baseline_decision,
            "c15_exclusion_decision": profile.c15_exclusion_decision,
        }
        database = _strict_mapping_request_mapping(
            outer["database"], tuple(expected_database)
        )
        if not _strict_primitive_equal(database, expected_database):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        request_value = outer["mapping_request"]
        if type(request_value) is not dict:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        request = _strict_mapping_request_mapping(
            request_value, tuple(request_value.keys())
        )
        schema = request.get("schema_version")
        if type(schema) is not str or schema not in _MAPPING_REQUEST_SCHEMAS:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        base_keys = (
            "schema_version", "feature_id", "database_identity", "components",
            "phase_selection", "pressure_pa", "total_moles",
        )
        feature_keys = {
            "binary_phase_diagram": (
                "left_component", "right_component", "right_fraction",
                "temperature_k",
            ),
            "multicomponent_isopleth": (
                "balance_component", "variable_component", "fixed_composition",
                "variable_fraction", "temperature_k",
            ),
            "ternary_phase_diagram": (
                "dependent_component", "x_component", "y_component",
                "temperature_k", "starting_point_step",
            ),
        }
        extras = feature_keys.get(binding.feature_id)
        if type(extras) is not tuple:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        _strict_mapping_request_mapping(request, base_keys + extras)
        if (
            type(request["feature_id"]) is not str
            or request["feature_id"] != binding.feature_id
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")

        if schema == "THERMOGAR-WAVE2B-MAPPING-REQUEST-1":
            database_id = binding.profile
            nested_role = (
                "DIAGNOSTIC_CONTROL"
                if binding.family == "fe" and binding.profile == "upstream_original"
                else "EVALUATION_PROFILE"
            )
        else:
            database_id = (
                "mc_fe_v2062" if binding.family == "fe" else binding.profile
            )
            nested_role = binding.profile_role
        decision = (
            "UNDECIDED_USER_DECISION_REQUIRED"
            if binding.family == "fe"
            else "NOT_APPLICABLE"
        )
        expected_identity = {
            "family": binding.family,
            "database_id": database_id,
            "database_sha256": binding.runtime_sha256,
            "profile_id": binding.profile,
            "profile_role": nested_role,
            "fe_baseline_decision": decision,
            "c15_exclusion_decision": decision,
        }
        identity = _strict_mapping_request_mapping(
            request["database_identity"], tuple(expected_identity)
        )
        if not _strict_primitive_equal(identity, expected_identity):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")

        expected_selection = {
            "candidate": list(domain.candidate_phases),
            "requested": list(domain.requested_phases),
            "excluded": list(domain.excluded_phases),
            "effective": list(domain.effective_phases),
        }
        selection = _strict_mapping_request_mapping(
            request["phase_selection"], tuple(expected_selection)
        )
        for key in expected_selection:
            observed = selection[key]
            if (
                type(observed) is not list
                or any(type(item) is not str for item in observed)
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if not _strict_primitive_equal(selection, expected_selection):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")

        component_values = request["components"]
        if type(component_values) is not list or not component_values:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        components = tuple(
            _strict_mapping_request_name(item) for item in component_values
        )
        if len(set(components)) != len(components):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        pressure = _strict_mapping_request_number(
            request["pressure_pa"], "POSITIVE"
        )
        total_moles = _strict_mapping_request_number(
            request["total_moles"], "POSITIVE"
        )
        if not _same_binary64(total_moles, 1.0):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        solver = _strict_mapping_request_mapping(
            solver_options, ("global_min_pdensity", "max_iterations")
        )
        pdensity = solver["global_min_pdensity"]
        max_iterations = solver["max_iterations"]
        if (
            type(pdensity) is not int
            or isinstance(pdensity, bool)
            or not 1 <= pdensity <= 10_000
            or type(max_iterations) is not int
            or isinstance(max_iterations, bool)
            or (max_iterations != -1 and not 1 <= max_iterations <= 1_000_000)
            or (
                schema == "THERMOGAR-WAVE2B-MAPPING-REQUEST-V2-1"
                and max_iterations == -1
            )
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if binding.feature_id == "binary_phase_diagram":
            left = _strict_mapping_request_name(request["left_component"])
            right = _strict_mapping_request_name(request["right_component"])
            if (
                left == right
                or "VA" in (left, right)
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            expected_components = tuple(sorted((left, right))) + ("VA",)
            right_range = _strict_mapping_request_range(
                request["right_fraction"], fraction=True, temperature=False
            )
            temperature = _strict_mapping_request_range(
                request["temperature_k"], fraction=False, temperature=True
            )
            geometry = (left, right, right_range, temperature)
            expected_bounds = {
                "pressure_pa": {"minimum": pressure, "maximum": pressure},
                "total_moles": {"minimum": total_moles, "maximum": total_moles},
                "right_fraction": {
                    "minimum": right_range[0], "maximum": right_range[1],
                    "seed_step": right_range[2],
                },
                "temperature_k": {
                    "minimum": temperature[0], "maximum": temperature[1],
                    "seed_step": temperature[2],
                },
            }
        elif binding.feature_id == "multicomponent_isopleth":
            balance = _strict_mapping_request_name(request["balance_component"])
            variable = _strict_mapping_request_name(request["variable_component"])
            if (
                balance == variable
                or "VA" in (balance, variable)
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            fixed_mapping = request["fixed_composition"]
            if type(fixed_mapping) is not dict or not fixed_mapping:
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            fixed_keys = tuple(fixed_mapping.keys())
            if any(type(key) is not str for key in fixed_keys):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            fixed: list[tuple[str, float]] = []
            for name in fixed_keys:
                checked_name = _strict_mapping_request_name(name)
                amount = _strict_mapping_request_number(
                    fixed_mapping[name], "NONNEGATIVE"
                )
                fixed.append((checked_name, amount))
            fixed.sort(key=lambda item: item[0])
            fixed_names = tuple(name for name, _amount in fixed)
            if (
                len(set(fixed_names)) != len(fixed_names)
                or balance in fixed_names
                or variable in fixed_names
                or "VA" in fixed_names
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            variable_range = _strict_mapping_request_range(
                request["variable_fraction"], fraction=True, temperature=False
            )
            temperature = _strict_mapping_request_range(
                request["temperature_k"], fraction=False, temperature=True
            )
            fixed_total = math.fsum(amount for _name, amount in fixed)
            combined = math.fsum((fixed_total, variable_range[1]))
            if (
                not math.isfinite(fixed_total)
                or not math.isfinite(combined)
                or fixed_total >= 1.0
                or combined >= 1.0
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            expected_components = tuple(
                sorted((balance, variable, *fixed_names))
            ) + ("VA",)
            geometry = (
                balance, variable, tuple(fixed), variable_range, temperature
            )
            expected_bounds = {
                "pressure_pa": {"minimum": pressure, "maximum": pressure},
                "total_moles": {"minimum": total_moles, "maximum": total_moles},
                "variable_fraction": {
                    "minimum": variable_range[0], "maximum": variable_range[1],
                    "seed_step": variable_range[2],
                },
                "temperature_k": {
                    "minimum": temperature[0], "maximum": temperature[1],
                    "seed_step": temperature[2],
                },
                "fixed_composition": {
                    name: {"minimum": amount, "maximum": amount}
                    for name, amount in fixed
                },
            }
        else:
            dependent = _strict_mapping_request_name(
                request["dependent_component"]
            )
            x_component = _strict_mapping_request_name(request["x_component"])
            y_component = _strict_mapping_request_name(request["y_component"])
            names = (dependent, x_component, y_component)
            if (
                len(set(names)) != 3
                or "VA" in names
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            temperature_value = _strict_mapping_request_number(
                request["temperature_k"], "POSITIVE"
            )
            step = _strict_mapping_request_number(
                request["starting_point_step"], "POSITIVE"
            )
            if step >= 0.25:
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            expected_components = tuple(sorted(names)) + ("VA",)
            geometry = (
                dependent, x_component, y_component, temperature_value, step
            )
            expected_bounds = {
                "pressure_pa": {"minimum": pressure, "maximum": pressure},
                "total_moles": {"minimum": total_moles, "maximum": total_moles},
                "temperature_k": {
                    "minimum": temperature_value,
                    "maximum": temperature_value,
                },
                "x_fraction": {"minimum": 0.0, "maximum": 1.0},
                "y_fraction": {"minimum": 0.0, "maximum": 1.0},
                "simplex_sum_maximum": 1.0,
                "starting_point_step": step,
            }
        if components != expected_components:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        _strict_mapping_request_mapping(bounds, tuple(expected_bounds))
        if not _strict_primitive_equal(bounds, expected_bounds):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        return (
            binding.feature_id, expected_components, pressure, total_moles,
            pdensity, max_iterations, geometry,
        )
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_DOMAIN_MISMATCH") from error


def _expected_strategy_inputs(
    binding: ExecutionBinding,
    modules: "_RuntimeModules",
) -> tuple[tuple[str, ...], dict[object, object], int, int]:
    """Derive solver inputs only from the receipt-bound full request."""

    try:
        (
            feature, components, pressure, total_moles, pdensity,
            max_iterations, geometry,
        ) = _parse_mapping_request(binding)
        variables = modules.variables
        conditions: dict[object, object] = {
            variables.P: pressure,
            variables.N: total_moles,
        }
        if feature == "binary_phase_diagram":
            _left, right, right_range, temperature = geometry
            conditions[variables.X(right)] = right_range
            conditions[variables.T] = temperature
        elif feature == "multicomponent_isopleth":
            _balance, variable, fixed, variable_range, temperature = geometry
            conditions[variables.X(variable)] = variable_range
            conditions[variables.T] = temperature
            for name, amount in fixed:
                conditions[variables.X(name)] = amount
        else:
            _dependent, x_component, y_component, temperature, step = geometry
            conditions[variables.T] = temperature
            conditions[variables.X(x_component)] = (0.0, 1.0, step)
            conditions[variables.X(y_component)] = (0.0, 1.0, step)
    except MappingInstrumentationError:
        raise
    except Exception as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_DOMAIN_MISMATCH") from error
    return components, conditions, pdensity, max_iterations


def _numpy_callable_identity_card(name: object, value: object) -> tuple[object, ...]:
    if type(name) is not str or name not in _NUMPY_CALLABLE_PINS:
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    expected = _NUMPY_CALLABLE_PINS[name]
    value_type = type(value)
    if (
        value_type.__module__ != expected[0]
        or value_type.__qualname__ != expected[1]
    ):
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    try:
        source_digest = None
        try:
            source_digest = sha256(inspect.getsource(value).encode("utf-8")).hexdigest()
        except (OSError, TypeError, IOError):
            source_digest = None
        card = (
            value_type.__module__,
            value_type.__qualname__,
            getattr(value, "__module__", None),
            getattr(value, "__qualname__", None),
            getattr(value, "__name__", None),
            source_digest,
            sha256((getattr(value, "__doc__", None) or "").encode("utf-8")).hexdigest(),
            str(inspect.signature(value)),
            type(getattr(value, "__self__", None)).__module__,
            type(getattr(value, "__self__", None)).__qualname__,
        )
    except BaseException as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_UPSTREAM_MISMATCH") from error
    if card != expected:
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    return card


def _verify_numpy_callable_authority(
    modules: object,
    *,
    deep: bool,
) -> None:
    if type(modules) is not _RuntimeModules or type(deep) is not bool:
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    np = object.__getattribute__(modules, "np")
    np_binary = object.__getattribute__(modules, "np_binary")
    if (
        not isinstance(np, types.ModuleType)
        or not isinstance(np_binary, types.ModuleType)
        or np.__name__ != "numpy"
        or np_binary.__name__ != "numpy._core._multiarray_umath"
        or type(getattr(np, "__version__", None)) is not str
        or getattr(np, "__version__") != _NUMPY_VERSION
    ):
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    expected_values = (
        ("array", object.__getattribute__(modules, "np_array")),
        ("allclose", object.__getattribute__(modules, "np_allclose")),
        ("amin", object.__getattribute__(modules, "np_amin")),
        ("amax", object.__getattribute__(modules, "np_amax")),
        ("dot", object.__getattribute__(modules, "np_dot")),
    )
    for name, expected in expected_values:
        if getattr(np, name, None) is not expected:
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        _numpy_callable_identity_card(name, expected)
    if not deep:
        return
    try:
        np_origin = Path(getattr(np, "__file__")).resolve(strict=True)
        binary_origin = Path(getattr(np_binary, "__file__")).resolve(strict=True)
        site_root = np_origin.parent.parent
        origin_cards = (
            (
                np_origin.relative_to(site_root).as_posix(),
                np_origin.stat().st_size,
                sha256(np_origin.read_bytes()).hexdigest(),
                _NUMPY_ORIGIN_CARD,
            ),
            (
                binary_origin.relative_to(site_root).as_posix(),
                binary_origin.stat().st_size,
                sha256(binary_origin.read_bytes()).hexdigest(),
                _NUMPY_BINARY_ORIGIN_CARD,
            ),
        )
    except BaseException as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_UPSTREAM_MISMATCH") from error
    for relative, size, digest, expected in origin_cards:
        if (
            relative != expected["relative"]
            or size != expected["size"]
            or digest != expected["sha256"]
        ):
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")


@dataclass(frozen=True, slots=True)
class _RuntimeModules:
    np: object
    np_binary: object
    np_array: object
    np_allclose: object
    np_amin: object
    np_amax: object
    np_dot: object
    variables: object
    Database: object
    BinaryStrategy: type
    IsoplethStrategy: type
    TernaryStrategy: type
    StepStrategy: type
    MapStrategy: type
    NodeQueue: type
    Node: type
    Point: type
    ZPFLine: type
    ZPFState: object
    Direction: object
    ExitHint: object
    MIN_COMPOSITION: float
    CompositionSet: type
    Solver: type
    COMP_DIFFERENCE_TOL: float
    starting_points: object
    zchk: object
    zeq: object
    map_utils: object


_RUNTIME_MODULE_FIELD_NAMES = (
    "np", "np_binary", "np_array", "np_allclose", "np_amin", "np_amax",
    "np_dot", "variables", "Database", "BinaryStrategy", "IsoplethStrategy",
    "TernaryStrategy", "StepStrategy", "MapStrategy", "NodeQueue", "Node",
    "Point", "ZPFLine", "ZPFState", "Direction", "ExitHint",
    "MIN_COMPOSITION", "CompositionSet", "Solver", "COMP_DIFFERENCE_TOL",
    "starting_points", "zchk", "zeq", "map_utils",
)


def _runtime_container_value_record(value: object) -> dict[str, object]:
    if isinstance(value, types.ModuleType):
        origin = Path(getattr(value, "__file__", "")).resolve(strict=True)
        payload = origin.read_bytes()
        return {
            "kind": "module",
            "name": value.__name__,
            "origin": str(origin),
            "origin_sha256": sha256(payload).hexdigest(),
            "origin_size": len(payload),
        }
    if type(value) is float:
        return {"kind": "float", "binary64": struct.pack(">d", value).hex()}
    return _runtime_object_record(value)


def _capture_runtime_modules_binding(
    modules: object,
) -> tuple[tuple[str, object, str], ...]:
    if type(modules) is not _RuntimeModules:
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    binding: list[tuple[str, object, str]] = [
        (
            "__container_type__",
            type(modules),
            canonical_trace_digest(_runtime_object_record(type(modules))),
        )
    ]
    for name in _RUNTIME_MODULE_FIELD_NAMES:
        try:
            value = getattr(modules, name)
        except AttributeError as error:
            raise MappingInstrumentationError("W2B_INSTRUMENT_UPSTREAM_MISMATCH") from error
        binding.append(
            (name, value, canonical_trace_digest(_runtime_container_value_record(value)))
        )
    return tuple(binding)


def _verify_runtime_modules_binding(
    modules: object,
    binding: object,
    *,
    deep: bool,
) -> None:
    if type(binding) is not tuple or len(binding) != len(_RUNTIME_MODULE_FIELD_NAMES) + 1:
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    container_name, container_type, container_digest = binding[0]
    if (
        container_name != "__container_type__"
        or type(modules) is not container_type
        or type(modules) is not _RuntimeModules
        or (deep and canonical_trace_digest(_runtime_object_record(type(modules))) != container_digest)
    ):
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    if tuple(item[0] for item in binding[1:]) != _RUNTIME_MODULE_FIELD_NAMES:
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    for name, expected, expected_digest in binding[1:]:
        try:
            observed = getattr(modules, name)
        except AttributeError as error:
            raise MappingInstrumentationError("W2B_INSTRUMENT_UPSTREAM_MISMATCH") from error
        if type(expected) is float:
            if type(observed) is not float or not _same_binary64(observed, expected):
                _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        elif observed is not expected:
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        if deep and canonical_trace_digest(
            _runtime_container_value_record(observed)
        ) != expected_digest:
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    _verify_numpy_callable_authority(modules, deep=deep)


def _verify_fresh_runtime_modules_against_binding(
    binding: tuple[tuple[str, object, str], ...],
) -> None:
    fresh = _load_runtime_modules()
    _verify_runtime_modules_binding(fresh, binding, deep=True)


def _load_runtime_modules() -> _RuntimeModules:
    verify_pinned_pycalphad()
    try:
        np = importlib.import_module("numpy")
        np_binary = importlib.import_module("numpy._core._multiarray_umath")
        np_array = getattr(np, "array", None)
        np_allclose = getattr(np, "allclose", None)
        np_amin = getattr(np, "amin", None)
        np_amax = getattr(np, "amax", None)
        np_dot = getattr(np, "dot", None)
        if any(
            value is None
            for value in (
                np_array, np_allclose, np_amin, np_amax, np_dot
            )
        ):
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        if (
            type(getattr(np, "__version__", None)) is not str
            or getattr(np, "__version__") != _NUMPY_VERSION
        ):
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        for name, value in (
            ("array", np_array),
            ("allclose", np_allclose),
            ("amin", np_amin),
            ("amax", np_amax),
            ("dot", np_dot),
        ):
            _numpy_callable_identity_card(name, value)
        pycalphad = importlib.import_module("pycalphad")
        variables = importlib.import_module("pycalphad.variables")
        binary = importlib.import_module("pycalphad.mapping.strategy.binary_strategy")
        isopleth = importlib.import_module("pycalphad.mapping.strategy.isopleth_strategy")
        ternary = importlib.import_module("pycalphad.mapping.strategy.ternary_strategy")
        base = importlib.import_module("pycalphad.mapping.strategy.strategy_base")
        step = importlib.import_module("pycalphad.mapping.strategy.step_strategy")
        primitives = importlib.import_module("pycalphad.mapping.primitives")
        composition = importlib.import_module("pycalphad.core.composition_set")
        solver = importlib.import_module("pycalphad.core.solver")
        constants = importlib.import_module("pycalphad.core.constants")
        starting = importlib.import_module("pycalphad.mapping.starting_points")
        zchk = importlib.import_module("pycalphad.mapping.zpf_checks")
        zeq = importlib.import_module("pycalphad.mapping.zpf_equilibrium")
        map_utils = importlib.import_module("pycalphad.mapping.utils")
        _verify_runtime_primitive_manifest()
        package_root = Path(getattr(pycalphad, "__file__")).resolve(strict=True).parent

        def expect_function(function: object, relative: str) -> None:
            code = getattr(function, "__code__", None)
            expected = package_root.joinpath(*relative.split("/")).resolve(strict=True)
            if code is None or Path(code.co_filename).resolve(strict=True) != expected:
                _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")

        class_checks = (
            (getattr(binary, "BinaryStrategy"), "pycalphad.mapping.strategy.binary_strategy"),
            (getattr(isopleth, "IsoplethStrategy"), "pycalphad.mapping.strategy.isopleth_strategy"),
            (getattr(ternary, "TernaryStrategy"), "pycalphad.mapping.strategy.ternary_strategy"),
            (getattr(step, "StepStrategy"), "pycalphad.mapping.strategy.step_strategy"),
            (getattr(base, "MapStrategy"), "pycalphad.mapping.strategy.strategy_base"),
            (getattr(primitives, "NodeQueue"), "pycalphad.mapping.primitives"),
        )
        if any(getattr(cls, "__module__", None) != module for cls, module in class_checks):
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        class_source_checks = (
            (base.MapStrategy, "mapping/strategy/strategy_base.py"),
            (binary.BinaryStrategy, "mapping/strategy/binary_strategy.py"),
            (isopleth.IsoplethStrategy, "mapping/strategy/isopleth_strategy.py"),
            (ternary.TernaryStrategy, "mapping/strategy/ternary_strategy.py"),
            (step.StepStrategy, "mapping/strategy/step_strategy.py"),
            (primitives.NodeQueue, "mapping/primitives.py"),
        )
        for cls, relative in class_source_checks:
            for member in vars(cls).values():
                targets = ()
                if isinstance(member, (staticmethod, classmethod)):
                    targets = (member.__func__,)
                elif isinstance(member, property):
                    targets = tuple(
                        function
                        for function in (member.fget, member.fset, member.fdel)
                        if function is not None
                    )
                elif getattr(member, "__code__", None) is not None:
                    targets = (member,)
                for target in targets:
                    expect_function(target, relative)
        function_checks = (
            (base.MapStrategy.iterate, "mapping/strategy/strategy_base.py"),
            (base.MapStrategy._step_conditions, "mapping/strategy/strategy_base.py"),
            (base.MapStrategy._process_new_node, "mapping/strategy/strategy_base.py"),
            (base.MapStrategy._start_zpf_line, "mapping/strategy/strategy_base.py"),
            (base.MapStrategy._find_node_exits, "mapping/strategy/strategy_base.py"),
            (binary.BinaryStrategy._determine_start_direction, "mapping/strategy/binary_strategy.py"),
            (binary._sort_point, "mapping/strategy/binary_strategy.py"),
            (isopleth.IsoplethStrategy._determine_start_direction, "mapping/strategy/isopleth_strategy.py"),
            (isopleth._point_slope, "mapping/strategy/isopleth_strategy.py"),
            (isopleth._composition_sets_with_phase_fractions, "mapping/strategy/isopleth_strategy.py"),
            (ternary.TernaryStrategy._determine_start_direction, "mapping/strategy/ternary_strategy.py"),
            (ternary._get_delta_cs_var, "mapping/strategy/ternary_strategy.py"),
            (ternary._get_norm, "mapping/strategy/ternary_strategy.py"),
            (ternary._create_linear_comb_conditions, "mapping/strategy/ternary_strategy.py"),
            (ternary._sort_point, "mapping/strategy/ternary_strategy.py"),
            (step.StepStrategy.generate_automatic_starting_points, "mapping/strategy/step_strategy.py"),
            (primitives._eq_compset, "mapping/primitives.py"),
            (primitives._get_phase_list_with_multiplicity, "mapping/primitives.py"),
            (primitives._get_phase_specific_variable, "mapping/primitives.py"),
            (primitives.NodeQueue.add_node, "mapping/primitives.py"),
            (primitives.NodeQueue.get_next_node, "mapping/primitives.py"),
            (primitives.ZPFLine.append, "mapping/primitives.py"),
            (starting.point_from_equilibrium, "mapping/starting_points.py"),
            (zchk.simple_check_valid_point, "mapping/zpf_checks.py"),
            (zchk.simple_check_change_in_phases, "mapping/zpf_checks.py"),
            (zchk.simple_check_global_min, "mapping/zpf_checks.py"),
            (zchk.check_valid_point, "mapping/zpf_checks.py"),
            (zchk._check_axis_values_within_limit, "mapping/zpf_checks.py"),
            (zchk._check_axis_values_by_distance, "mapping/zpf_checks.py"),
            (zchk.check_axis_values, "mapping/zpf_checks.py"),
            (zchk.check_change_in_phases, "mapping/zpf_checks.py"),
            (zchk.check_global_min, "mapping/zpf_checks.py"),
            (zchk.check_similar_phase_composition, "mapping/zpf_checks.py"),
            (zchk.check_circular_loop, "mapping/zpf_checks.py"),
            (zeq._find_global_min_cs, "mapping/zpf_equilibrium.py"),
            (zeq.compute_derivative, "mapping/zpf_equilibrium.py"),
            (map_utils.degrees_of_freedom, "mapping/utils.py"),
            (map_utils.is_state_variable, "mapping/utils.py"),
            (map_utils.get_statevars_array, "mapping/utils.py"),
            (map_utils.update_cs_phase_frac, "mapping/utils.py"),
            (map_utils._sort_axis_by_state_vars, "mapping/utils.py"),
            (map_utils._generate_point_with_fixed_cs, "mapping/utils.py"),
            (map_utils._generate_point_with_free_cs, "mapping/utils.py"),
        )
        for function, relative in function_checks:
            expect_function(function, relative)
        if any(
            getattr(module, "map_utils", map_utils) is not map_utils
            for module in (base, binary, isopleth, ternary, step, zeq)
        ) or any(
            getattr(module, "zeq", zeq) is not zeq
            for module in (base, binary, isopleth, ternary, zchk)
        ):
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        # Close the verify/import window: persistent source drift occurring
        # while modules were imported must not survive the runtime boundary.
        verify_pinned_pycalphad()
        _verify_runtime_primitive_manifest()
        modules = _RuntimeModules(
            np=np,
            np_binary=np_binary,
            np_array=np_array,
            np_allclose=np_allclose,
            np_amin=np_amin,
            np_amax=np_amax,
            np_dot=np_dot,
            variables=variables,
            Database=getattr(pycalphad, "Database"),
            BinaryStrategy=getattr(binary, "BinaryStrategy"),
            IsoplethStrategy=getattr(isopleth, "IsoplethStrategy"),
            TernaryStrategy=getattr(ternary, "TernaryStrategy"),
            StepStrategy=getattr(step, "StepStrategy"),
            MapStrategy=getattr(base, "MapStrategy"),
            NodeQueue=getattr(primitives, "NodeQueue"),
            Node=getattr(primitives, "Node"),
            Point=getattr(primitives, "Point"),
            ZPFLine=getattr(primitives, "ZPFLine"),
            ZPFState=getattr(primitives, "ZPFState"),
            Direction=getattr(primitives, "Direction"),
            ExitHint=getattr(primitives, "ExitHint"),
            MIN_COMPOSITION=float(getattr(primitives, "MIN_COMPOSITION")),
            CompositionSet=getattr(composition, "CompositionSet"),
            Solver=getattr(solver, "Solver"),
            COMP_DIFFERENCE_TOL=float(getattr(constants, "COMP_DIFFERENCE_TOL")),
            starting_points=starting,
            zchk=zchk,
            zeq=zeq,
            map_utils=map_utils,
        )
        _verify_numpy_callable_authority(modules, deep=True)
        return modules
    except MappingInstrumentationError:
        raise
    except Exception as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_RUNTIME_IMPORT_FAILED") from error


def _solver_call(
    strategy: object,
    name: str,
    conditions: Mapping[object, object],
    callback: object,
    *,
    point: object | None = None,
) -> object:
    guard = getattr(strategy, "_tg_runtime_guard", None)
    helpers = getattr(strategy, "_tg_helpers", None)
    if guard is not None:
        guard(deep=True)
    else:
        _verify_runtime_primitive_manifest()
    observe_point = (
        helpers["_point_observation"] if helpers is not None else _point_observation
    )
    normalize_conditions = (
        helpers["_condition_pairs"] if helpers is not None else _condition_pairs
    )
    try:
        condition_snapshot = copy.deepcopy(dict(conditions))
    except Exception as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_EVENT_INVALID") from error
    requested_pairs = normalize_conditions(condition_snapshot)
    recorder: _TraceRecorder = strategy._tg_recorder
    relation = recorder.relation()
    operation = recorder.begin_operation(
        "solver_invocation", "SOLVER", conditions=condition_snapshot, relation_id=relation,
        details={"solver_boundary": name},
        event_slots=2,
    )
    coordinates, phases, instances = observe_point(strategy, point)
    invocation_id = recorder.emit(
        "SOLVER_INVOCATION",
        "SOLVER",
        operation_ordinal=operation,
        requested_conditions=requested_pairs,
        resolved_coordinates=coordinates,
        phases=phases,
        phase_instances=instances,
        relation_id=relation,
        outcome="ACCEPTED",
        details={"solver_boundary": name},
    )
    try:
        result = callback()
        if guard is not None:
            guard(deep=True)
        else:
            _verify_runtime_primitive_manifest()
        suppressed_error = None
        if type(result) is _SuppressedSolverFailure:
            suppressed_error = result.error
            result = None
        result_point = result[0] if type(result) is tuple and result else result
        coordinates, phases, instances = observe_point(strategy, result_point)
    except BaseException as error:
        try:
            if guard is not None:
                guard(deep=True)
            else:
                _verify_runtime_primitive_manifest()
        except BaseException as identity_error:
            error = identity_error
        recorder.emit(
            "SOLVER_RESULT",
            "SOLVER",
            operation_ordinal=operation,
            requested_conditions=requested_pairs,
            resolved_coordinates=None,
            exception=error,
            parent_event_id=invocation_id,
            relation_id=relation,
            outcome="FAILED",
            details={"solver_boundary": name},
        )
        recorder.end_operation(
            operation,
            outcome="FAILED",
            exception=error,
            details={"solver_boundary": name},
        )
        raise error
    recorder.emit(
        "SOLVER_RESULT",
        "SOLVER",
        operation_ordinal=operation,
        requested_conditions=requested_pairs,
        resolved_coordinates=(coordinates if result is not None else None),
        phases=phases,
        phase_instances=instances,
        exception=suppressed_error,
        parent_event_id=invocation_id,
        relation_id=relation,
        outcome=("ACCEPTED" if result is not None else "FAILED"),
        details={"solver_boundary": name, "returned_none": result is None},
    )
    recorder.end_operation(
        operation,
        outcome=("ACCEPTED" if result is not None else "FAILED"),
        exception=suppressed_error,
        details={"solver_boundary": name},
    )
    return result


@dataclass(frozen=True, slots=True)
class _SuppressedSolverFailure:
    """Upstream-compatible swallowed failure retained by the event trace."""

    error: BaseException


def _update_equilibrium(strategy: object, point: object, new_conditions: dict, free_var: object = None):
    """Pinned port of zpf_equilibrium.update_equilibrium_with_new_conditions."""

    guard = getattr(strategy, "_tg_runtime_guard", None)
    helpers = getattr(strategy, "_tg_helpers", None)
    if guard is not None:
        guard(deep=True)
    m: _RuntimeModules = strategy._tg_modules
    working = copy.deepcopy(new_conditions)
    if free_var is not None:
        try:
            del working[free_var]
        except KeyError as error:
            raise MappingInstrumentationError("W2B_INSTRUMENT_DOMAIN_MISMATCH") from error

    def solve():
        comp_sets = copy.deepcopy(point.stable_composition_sets)
        for cs in comp_sets:
            state_variables = cs.phase_record.state_variables
            state = m.map_utils.get_statevars_array(new_conditions, state_variables)
            cs.update(cs.dof[len(state_variables):], cs.NP, state)
        orig_cs = [cs for cs in comp_sets]
        try:
            results = m.Solver(remove_metastable=True).solve(comp_sets, working)
            if not results.converged:
                return None
        except Exception as error:
            return _SuppressedSolverFailure(error)
        if free_var is not None:
            point_conditions = copy.deepcopy(working)
            point_conditions[free_var] = free_var.compute_property(
                comp_sets, working, results.chemical_potentials
            )
        else:
            point_conditions = copy.deepcopy(working)
        new_point = m.Point(
            point_conditions,
            m.np_array(results.chemical_potentials),
            [cs for cs in comp_sets if cs.fixed],
            [cs for cs in comp_sets if not cs.fixed],
        )
        return new_point, orig_cs

    solver_boundary = helpers["_solver_call"] if helpers is not None else _solver_call
    return solver_boundary(
        strategy,
        "Solver.solve:update_equilibrium_with_new_conditions",
        working,
        solve,
        point=point,
    )


def _detect_degenerate_phase(strategy: object, point: object, new_cs: object) -> bool:
    """Pinned port of zpf_equilibrium._detect_degenerate_phase."""

    guard = getattr(strategy, "_tg_runtime_guard", None)
    helpers = getattr(strategy, "_tg_helpers", None)
    if guard is not None:
        guard(deep=True)
    m: _RuntimeModules = strategy._tg_modules
    solver_boundary = helpers["_solver_call"] if helpers is not None else _solver_call
    num_sv = new_cs.phase_record.num_statevars
    for cs in point.stable_composition_sets:
        if new_cs.phase_record.phase_name != cs.phase_record.phase_name:
            continue
        if m.np_allclose(
            cs.dof[num_sv:],
            new_cs.dof[num_sv:],
            atol=10 * m.COMP_DIFFERENCE_TOL,
        ):
            return False
        _verify_runtime_primitive_manifest()
        ref_cs_copy = m.CompositionSet(cs.phase_record)
        ref_cs_copy.update(cs.dof[num_sv:], 1, cs.dof[:num_sv])
        _verify_runtime_primitive_manifest()
        new_cs_copy = m.CompositionSet(new_cs.phase_record)
        new_cs_copy.update(new_cs.dof[num_sv:], 1e-6, new_cs.dof[:num_sv])
        conds = {
            key: key.compute_property(
                [ref_cs_copy], point.global_conditions, point.chemical_potentials
            )
            for key in point.global_conditions
        }

        def solve():
            try:
                result = m.Solver(remove_metastable=True).solve(
                    [ref_cs_copy, new_cs_copy], conds
                )
                return result if result.converged else None
            except Exception as error:
                return _SuppressedSolverFailure(error)

        results = solver_boundary(
            strategy,
            "Solver.solve:detect_degenerate_phase",
            conds,
            solve,
            point=point,
        )
        if results is None:
            return False
        if m.np_allclose(
            ref_cs_copy.dof[num_sv:],
            new_cs_copy.dof[num_sv:],
            atol=10 * m.COMP_DIFFERENCE_TOL,
        ):
            return False
        if ref_cs_copy.NP < 1e-3:
            cs.update(new_cs_copy.dof[num_sv:], cs.NP, new_cs_copy.dof[:num_sv])
            return True
    return True


def _find_global_min_cs(strategy: object, point: object):
    guard = getattr(strategy, "_tg_runtime_guard", None)
    helpers = getattr(strategy, "_tg_helpers", None)
    if guard is not None:
        guard(deep=True)
    m: _RuntimeModules = strategy._tg_modules
    conditions = point.global_conditions
    solver_boundary = helpers["_solver_call"] if helpers is not None else _solver_call
    return solver_boundary(
        strategy,
        "calculate:find_global_min_cs",
        conditions,
        lambda: m.zeq._find_global_min_cs(
            point,
            system_info=strategy.system_info,
            pdens=strategy.GLOBAL_MIN_PDENS,
            tol=strategy.GLOBAL_MIN_TOL,
            num_candidates=strategy.GLOBAL_MIN_NUM_CANDIDATES,
        ),
        point=point,
    )


def _find_global_min_point(strategy: object, point: object):
    helpers = getattr(strategy, "_tg_helpers", None)
    find_cs = helpers["_find_global_min_cs"] if helpers is not None else _find_global_min_cs
    detect = (
        helpers["_detect_degenerate_phase"]
        if helpers is not None else _detect_degenerate_phase
    )
    result = find_cs(strategy, point)
    if result is None:
        return None
    cs, _driving_force = result
    if not detect(strategy, point, cs):
        return None
    m: _RuntimeModules = strategy._tg_modules
    new_point = m.Point(
        point.global_conditions,
        point.chemical_potentials,
        point.fixed_composition_sets,
        point.free_composition_sets,
    )
    m.map_utils.update_cs_phase_frac(cs, 1e-6)
    new_point._free_composition_sets.append(cs)
    return new_point


def _create_node_from_different_points(
    strategy: object, new_point: object, orig_cs: list[object], axis_vars: list[object]
):
    """Pinned port of zpf_equilibrium.create_node_from_different_points."""

    guard = getattr(strategy, "_tg_runtime_guard", None)
    helpers = getattr(strategy, "_tg_helpers", None)
    if guard is not None:
        guard(deep=True)
    m: _RuntimeModules = strategy._tg_modules
    solver_boundary = helpers["_solver_call"] if helpers is not None else _solver_call
    prev_cs = [cs for cs in orig_cs]
    new_cs = [cs for cs in new_point.stable_composition_sets]
    phases_added = list(set(new_cs) - set(prev_cs))
    phases_removed = list(set(prev_cs) - set(new_cs))
    if len(phases_added) + len(phases_removed) != 1:
        return None
    if len(phases_added) == 1:
        fixed_cs = phases_added[0]
    else:
        fixed_cs = phases_removed[0]
        new_cs.append(fixed_cs)
    fixed_cs.fixed = True
    m.map_utils.update_cs_phase_frac(fixed_cs, 0.0)
    if all(cs.NP == 0.0 for cs in new_cs):
        for cs in new_cs:
            if not cs.fixed:
                m.map_utils.update_cs_phase_frac(cs, 1.0)
                break
    solution_cs = [cs for cs in new_cs]
    new_conditions = copy.deepcopy(new_point.global_conditions)
    for axis in axis_vars:
        del new_conditions[axis]

    def solve():
        try:
            result = m.Solver(remove_metastable=True).solve(solution_cs, new_conditions)
            return result if result.converged else None
        except Exception as error:
            return _SuppressedSolverFailure(error)

    results = solver_boundary(
        strategy,
        "Solver.solve:create_node_from_different_points",
        new_conditions,
        solve,
        point=new_point,
    )
    if results is None:
        return None
    for axis in axis_vars:
        new_conditions[axis] = axis.compute_property(
            solution_cs, new_conditions, results.chemical_potentials
        )
    parent = m.Point(
        new_conditions,
        m.np_array(results.chemical_potentials),
        [cs for cs in orig_cs if cs.fixed],
        [cs for cs in orig_cs if not cs.fixed],
    )
    return m.Node(
        new_conditions,
        m.np_array(results.chemical_potentials),
        [cs for cs in solution_cs if cs.fixed],
        [cs for cs in solution_cs if not cs.fixed],
        parent,
    )


def _check_change_in_phases(strategy: object, zpf_line: object, step_results: object, axis_data: dict, **kwargs):
    if step_results is None:
        return None
    helpers = getattr(strategy, "_tg_helpers", None)
    m: _RuntimeModules = strategy._tg_modules
    axis_vars = axis_data["axis_vars"]
    new_point, orig_cs = step_results
    new_point_vars = {axis: new_point.get_property(axis) for axis in axis_vars}
    different = len(set(orig_cs).symmetric_difference(set(new_point.stable_composition_sets)))
    if different == 0:
        return None
    zpf_line.status = m.ZPFState.FAILED
    if different > 1:
        return None
    create_node = (
        helpers["_create_node_from_different_points"]
        if helpers is not None else _create_node_from_different_points
    )
    new_node = create_node(strategy, new_point, orig_cs, axis_vars)
    if new_node is not None:
        node_vars = {axis: new_node.get_property(axis) for axis in axis_vars}
        within = m.zchk._check_axis_values_within_limit(node_vars, axis_data)
        distance = m.zchk._check_axis_values_by_distance(
            new_point_vars, node_vars, axis_data, **kwargs
        )
        if within and distance:
            zpf_line.status = m.ZPFState.NEW_NODE_FOUND
            return new_node
    return None


def _check_global_min(strategy: object, zpf_line: object, step_results: object, axis_data: dict, **kwargs):
    if step_results is None:
        return None
    helpers = getattr(strategy, "_tg_helpers", None)
    m: _RuntimeModules = strategy._tg_modules
    interval = kwargs.get("global_check_interval", 1)
    if len(zpf_line.points) % interval != 0:
        return None
    axis_vars = axis_data["axis_vars"]
    new_point, _orig_cs = step_results
    new_point_vars = {axis: new_point.get_property(axis) for axis in axis_vars}
    find_point = (
        helpers["_find_global_min_point"]
        if helpers is not None else _find_global_min_point
    )
    create_node = (
        helpers["_create_node_from_different_points"]
        if helpers is not None else _create_node_from_different_points
    )
    global_point = find_point(strategy, new_point)
    if global_point is None:
        return None
    zpf_line.status = m.ZPFState.FAILED
    new_node = create_node(
        strategy, global_point, new_point.stable_composition_sets, axis_vars
    )
    if new_node is not None:
        node_vars = {axis: new_node.get_property(axis) for axis in axis_vars}
        within = m.zchk._check_axis_values_within_limit(node_vars, axis_data)
        distance = m.zchk._check_axis_values_by_distance(
            new_point_vars, node_vars, axis_data, **kwargs
        )
        if within and distance:
            zpf_line.status = m.ZPFState.NEW_NODE_FOUND
            return new_node
    return None


def _queue_class(modules: _RuntimeModules):
    class InstrumentedNodeQueue(modules.NodeQueue):
        def __init__(self, recorder: _TraceRecorder, strategy: object):
            super().__init__()
            self._tg_recorder = recorder
            self._tg_strategy = strategy

        def add_node(self, candidate_node, force=False, check_parent=False):
            relation = self._tg_recorder.relation()
            operation = self._tg_recorder.begin_operation(
                "node_queue_add", "NODE_QUEUE", relation_id=relation,
                details={"force": bool(force), "check_parent": bool(check_parent)},
                event_slots=3,
            )
            coordinates, phases, instances = _point_observation(
                self._tg_strategy, candidate_node
            )
            attempt = self._tg_recorder.emit(
                "NODE_QUEUE_TRANSITION",
                "NODE_QUEUE",
                operation_ordinal=operation,
                resolved_coordinates=coordinates,
                phases=phases,
                phase_instances=instances,
                relation_id=relation,
                outcome="ACCEPTED",
                details={
                    "transition": "ENQUEUE_ATTEMPT",
                    "queue_size_before": self.size(),
                    "node_id": self._tg_recorder.object_token("NODE", candidate_node),
                },
            )
            try:
                added = super().add_node(candidate_node, force, check_parent)
            except InstrumentationBudgetExceeded:
                raise
            except BaseException as error:
                self._tg_recorder.emit(
                    "NODE_QUEUE_TRANSITION",
                    "NODE_QUEUE",
                    operation_ordinal=operation,
                    resolved_coordinates=coordinates,
                    phases=phases,
                    phase_instances=instances,
                    exception=error,
                    parent_event_id=attempt,
                    relation_id=relation,
                    outcome="FAILED",
                    details={
                        "transition": "ENQUEUE_FAILED",
                        "queue_size_after": self.size(),
                        "node_id": self._tg_recorder.object_token("NODE", candidate_node),
                    },
                )
                self._tg_recorder.end_operation(
                    operation,
                    outcome="FAILED",
                    exception=error,
                    details={"transition": "ENQUEUE_FAILED"},
                )
                raise
            merged_into = None
            if not added:
                for other in self.nodes:
                    if other != candidate_node:
                        continue
                    if check_parent and not (
                        other.parent == candidate_node.parent
                        and other.axis_var == candidate_node.axis_var
                        and other.axis_direction == candidate_node.axis_direction
                    ):
                        continue
                    merged_into = self._tg_recorder.object_token("NODE", other)
                    break
            result_event = self._tg_recorder.emit(
                "NODE_QUEUE_TRANSITION" if added else "DUPLICATE_MERGE",
                "NODE_QUEUE",
                operation_ordinal=operation,
                resolved_coordinates=coordinates,
                phases=phases,
                phase_instances=instances,
                parent_event_id=attempt,
                relation_id=relation,
                outcome=("ACCEPTED" if added else "MERGED"),
                details={
                    "transition": "ENQUEUED" if added else "DUPLICATE_MERGED",
                    "queue_size_after": self.size(),
                    "node_id": self._tg_recorder.object_token("NODE", candidate_node),
                    "merged_into_node_id": merged_into,
                },
            )
            if getattr(self._tg_strategy, "_tg_start_transfer_active", False):
                self._tg_recorder.emit(
                    "START_POINT",
                    "START_POINT",
                    operation_ordinal=operation,
                    requested_conditions=_condition_pairs(
                        getattr(candidate_node, "global_conditions", {})
                    ),
                    resolved_coordinates=coordinates,
                    phases=phases,
                    phase_instances=instances,
                    parent_event_id=result_event,
                    relation_id=relation,
                    outcome=("ACCEPTED" if added else "MERGED"),
                    details={
                        "source": "AUTOMATIC_STEP_TRANSFER",
                        "node_id": self._tg_recorder.object_token("NODE", candidate_node),
                        "merged_into_node_id": merged_into,
                    },
                )
            self._tg_recorder.end_operation(
                operation,
                outcome=("ACCEPTED" if added else "MERGED"),
                details={"transition": "ENQUEUED" if added else "DUPLICATE_MERGED"},
            )
            return added

        def get_next_node(self):
            relation = self._tg_recorder.relation()
            operation = self._tg_recorder.begin_operation(
                "node_queue_get", "NODE_QUEUE", relation_id=relation,
                details={"queue_size_before": self.size()},
                event_slots=1,
            )
            try:
                node = super().get_next_node()
            except BaseException as error:
                self._tg_recorder.emit(
                    "NODE_QUEUE_TRANSITION", "NODE_QUEUE",
                    operation_ordinal=operation,
                    exception=error,
                    relation_id=relation,
                    outcome="FAILED",
                    details={"transition": "DEQUEUE_FAILED"},
                )
                self._tg_recorder.end_operation(
                    operation,
                    outcome="FAILED",
                    exception=error,
                    details={"transition": "DEQUEUE_FAILED"},
                )
                raise
            coordinates, phases, instances = _point_observation(self._tg_strategy, node)
            self._tg_recorder.emit(
                "NODE_QUEUE_TRANSITION", "NODE_QUEUE",
                operation_ordinal=operation,
                resolved_coordinates=coordinates,
                phases=phases,
                phase_instances=instances,
                relation_id=relation,
                outcome="ACCEPTED",
                details={
                    "transition": "DEQUEUED",
                    "queue_size_after": self.size(),
                    "node_id": self._tg_recorder.object_token("NODE", node),
                },
            )
            self._tg_recorder.end_operation(
                operation,
                outcome="ACCEPTED",
                details={"transition": "DEQUEUED"},
            )
            return node

    return InstrumentedNodeQueue


class _InstrumentedStrategyMixin:
    """Mixin whose methods are resolved before each exact upstream strategy."""

    def __init__(
        self,
        *args,
        _tg_recorder,
        _tg_modules,
        _tg_kind,
        _tg_runtime_guard,
        _tg_helpers,
        **kwargs,
    ):
        if len(args) < 4 or type(args[3]) is not dict:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        canonical_condition_items = tuple(args[3].items())
        self._tg_recorder = _tg_recorder
        self._tg_modules = _tg_modules
        self._tg_kind = _tg_kind
        self._tg_runtime_guard = _tg_runtime_guard
        self._tg_helpers = _tg_helpers
        self._tg_scope_depth = 0
        self._tg_start_transfer_active = False
        self._tg_last_finished = False
        self._tg_last_iteration_bound = False
        super().__init__(*args, **kwargs)
        # MapStrategy 0.11.2 deep-copies the whole conditions dictionary.
        # Its StateVariable singletons survive that copy, but MoleFraction
        # keys do not. Rebind every variable-keyed strategy structure to the
        # exact, already receipt-validated key objects supplied at this edge;
        # positional pairing is deterministic because dict deepcopy preserves
        # insertion order. No key equality or coercion establishes the match.
        if type(self.conditions) is not dict:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        copied_condition_items = tuple(self.conditions.items())
        if len(copied_condition_items) != len(canonical_condition_items):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        key_pairs: list[tuple[object, object]] = []
        rebuilt_conditions: dict[object, object] = {}
        for (canonical_key, canonical_value), (copied_key, copied_value) in zip(
            canonical_condition_items, copied_condition_items
        ):
            if (
                type(copied_key) is not type(canonical_key)
                or type(copied_value) is not type(canonical_value)
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            key_pairs.append((copied_key, canonical_key))
            rebuilt_conditions[canonical_key] = copied_value

        def exact_canonical_key(copied_key: object) -> object:
            matches = tuple(
                canonical_key
                for observed_key, canonical_key in key_pairs
                if copied_key is observed_key
            )
            if len(matches) != 1:
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            return matches[0]

        if (
            type(self.axis_vars) is not list
            or type(self.axis_lims) is not dict
            or type(self.axis_delta) is not dict
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        self.conditions = rebuilt_conditions
        self.axis_vars = [exact_canonical_key(key) for key in self.axis_vars]
        self.axis_lims = {
            exact_canonical_key(key): value for key, value in self.axis_lims.items()
        }
        self.axis_delta = {
            exact_canonical_key(key): value for key, value in self.axis_delta.items()
        }
        if hasattr(self, "all_vars"):
            if type(self.all_vars) is not list:
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            rebuilt_all_vars: list[object] = []
            for key in self.all_vars:
                matches = tuple(
                    canonical_key
                    for observed_key, canonical_key in key_pairs
                    if key is observed_key
                )
                if len(matches) > 1:
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
                rebuilt_all_vars.append(matches[0] if matches else key)
            self.all_vars = rebuilt_all_vars
        queue_type = _queue_class(_tg_modules)
        self.node_queue = queue_type(_tg_recorder, self)
        self._tg_runtime_method_bindings = _strategy_method_bindings(self)

    def _tg_verify_runtime(self):
        self._tg_runtime_guard(deep=True)
        verify_instrumentation_source(INSTRUMENTATION_SOURCE_PIN_SHA256)
        _verify_runtime_primitive_manifest()
        if _strategy_method_bindings(self) != self._tg_runtime_method_bindings:
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")

    def _tg_step_strategy(self, conditions):
        """Create an instrumented child StepStrategy sharing the same recorder."""

        step_type = self._tg_instrumented_classes()["step"]
        child = step_type(
            self.dbf,
            self.components,
            self.phases,
            conditions,
            _tg_recorder=self._tg_recorder,
            _tg_modules=self._tg_modules,
            _tg_kind="step",
            _tg_runtime_guard=self._tg_runtime_guard,
            _tg_helpers=self._tg_helpers,
            **self._constant_kwargs(),
        )
        self._tg_register_child(child)
        return child

    def generate_automatic_starting_points(self):
        """Pinned strategy scans using an instrumented child StepStrategy."""

        m = self._tg_modules
        if self._tg_kind == "step":
            return super().generate_automatic_starting_points()
        if self._tg_kind in ("binary", "isopleth"):
            for axis in self.axis_vars:
                for axis_value in self.axis_lims[axis]:
                    conditions = copy.deepcopy(self.conditions)
                    conditions[axis] = axis_value
                    if self._tg_kind == "binary":
                        other_axis = self._other_av(axis)
                        axis_range = (
                            m.np_amax(self.axis_lims[other_axis])
                            - m.np_amin(self.axis_lims[other_axis])
                        )
                        conditions[other_axis] = (
                            self.axis_lims[other_axis][0],
                            self.axis_lims[other_axis][1],
                            axis_range / 20,
                        )
                    if isinstance(axis, m.variables.X):
                        if conditions[axis] == 0:
                            conditions[axis] = m.MIN_COMPOSITION
                        elif conditions[axis] == 1:
                            conditions[axis] = 1 - m.MIN_COMPOSITION
                    child = self._tg_step_strategy(conditions)
                    child.do_map()
                    self.add_starting_points_from_step(child)
            return None
        if self._tg_kind == "ternary":
            for axis in self.axis_vars:
                conditions = copy.deepcopy(self.conditions)
                conditions[axis] = m.np_amin(self.axis_lims[axis])
                if isinstance(axis, m.variables.X) and conditions[axis] == 0:
                    conditions[axis] = m.MIN_COMPOSITION
                child = self._tg_step_strategy(conditions)
                child.do_map()
                self.add_starting_points_from_step(child)
            conditions = copy.deepcopy(self.conditions)
            conditions[self.all_vars[-1]] = m.MIN_COMPOSITION
            del conditions[self.axis_vars[0]]
            child = self._tg_step_strategy(conditions)
            child.do_map()
            self.add_starting_points_from_step(child)
            return None
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")

    def add_starting_points_from_step(self, step):
        previous_transfer_state = self._tg_start_transfer_active
        self._tg_start_transfer_active = True
        try:
            if self._tg_kind != "ternary":
                return super().add_starting_points_from_step(step)
            m = self._tg_modules
            for zpf_line in step.zpf_lines:
                if len(zpf_line.stable_phases) not in (2, 3):
                    continue
                phase_count = len(zpf_line.stable_phases)
                point_index = 0
                while len(zpf_line.points[point_index].stable_phases) != phase_count:
                    point_index += 1
                new_point = zpf_line.points[point_index]
                if self.all_vars[-1] in new_point.global_conditions:
                    del new_point.global_conditions[self.all_vars[-1]]
                    new_point.global_conditions[self.axis_vars[0]] = new_point.get_property(
                        self.axis_vars[0]
                    )
                free_point = m.map_utils._generate_point_with_free_cs(new_point)
                cs_result = self._tg_helpers["_find_global_min_cs"](self, free_point)
                if cs_result is None:
                    new_node = self._create_node_from_point(
                        free_point, None, None, None
                    )
                    self.node_queue.add_node(new_node)
                else:
                    coordinates, phases, instances = _point_observation(self, free_point)
                    operation = self._tg_recorder.begin_operation(
                        "ternary_transfer_start",
                        "START_POINT",
                        conditions=free_point.global_conditions,
                        event_slots=1,
                    )
                    self._tg_recorder.emit(
                        "START_POINT",
                        "START_POINT",
                        operation_ordinal=operation,
                        requested_conditions=_condition_pairs(free_point.global_conditions),
                        resolved_coordinates=coordinates,
                        phases=phases,
                        phase_instances=instances,
                        outcome="ABANDONED",
                        details={
                            "source": "AUTOMATIC_STEP_TRANSFER",
                            "reason": "METASTABLE_GLOBAL_MINIMUM",
                        },
                    )
                    self._tg_recorder.end_operation(
                        operation,
                        outcome="ABANDONED",
                        details={"reason": "METASTABLE_GLOBAL_MINIMUM"},
                    )
            return None
        finally:
            self._tg_start_transfer_active = previous_transfer_state

    def _add_starting_point_at_new_condition(self, point, normal, direction):
        """Pinned ternary recovery path with its Workspace call observed."""

        if self._tg_kind != "ternary":
            return super()._add_starting_point_at_new_condition(point, normal, direction)
        m = self._tg_modules
        free_point = m.map_utils._generate_point_with_free_cs(point)
        conditions = copy.deepcopy(free_point.global_conditions)
        for axis, normal_direction in zip(self.axis_vars, normal):
            conditions[axis] += 1e-3 * normal_direction * direction.value

        operation = self._tg_recorder.begin_operation(
            "ternary_recovery_start",
            "START_POINT",
            conditions=conditions,
            event_slots=1,
        )

        def solve_start():
            return m.starting_points.point_from_equilibrium(
                self.dbf,
                self.components,
                self.phases,
                conditions,
                models=self.models,
                phase_record_factory=self.phase_records,
            )

        new_point = self._tg_helpers["_solver_call"](
            self,
            "Workspace:ternary_recovery_starting_point",
            conditions,
            solve_start,
            point=point,
        )
        if new_point is None:
            self._tg_recorder.emit(
                "START_POINT",
                "START_POINT",
                operation_ordinal=operation,
                requested_conditions=_condition_pairs(conditions),
                resolved_coordinates=None,
                outcome="FAILED",
                details={
                    "source": "TERNARY_RECOVERY",
                    "reason": "EQUILIBRIUM_RETURNED_NONE",
                },
            )
            self._tg_recorder.end_operation(
                operation,
                outcome="FAILED",
                details={"reason": "EQUILIBRIUM_RETURNED_NONE"},
            )
            return None
        success = False
        if len(new_point.stable_composition_sets) == 3:
            new_node = self._create_node_from_point(new_point, point, None, None)
            success = self.node_queue.add_node(new_node)
        elif len(new_point.stable_composition_sets) == 2:
            new_node = self._create_node_from_point(
                new_point, None, None, None, m.ExitHint.POINT_IS_EXIT
            )
            success = self.node_queue.add_node(new_node)
        coordinates, phases, instances = _point_observation(self, new_point)
        self._tg_recorder.emit(
            "START_POINT",
            "START_POINT",
            operation_ordinal=operation,
            requested_conditions=_condition_pairs(conditions),
            resolved_coordinates=coordinates,
            phases=phases,
            phase_instances=instances,
            outcome=("ACCEPTED" if success else "ABANDONED"),
            details={
                "source": "TERNARY_RECOVERY",
                "reason": None if success else "INVALID_PHASE_COUNT_OR_DUPLICATE",
            },
        )
        self._tg_recorder.end_operation(
            operation,
            outcome=("ACCEPTED" if success else "ABANDONED"),
            details={
                "reason": None if success else "INVALID_PHASE_COUNT_OR_DUPLICATE"
            },
        )
        return None

    def add_nodes_from_conditions(self, conditions, direction=None, force_add=True):
        m = self._tg_modules

        def solve_start():
            return m.starting_points.point_from_equilibrium(
                self.dbf,
                self.components,
                self.phases,
                conditions,
                models=self.models,
                phase_record_factory=self.phase_records,
            )

        point = self._tg_helpers["_solver_call"](
            self, "Workspace:point_from_equilibrium", conditions, solve_start
        )
        relation = self._tg_recorder.relation()
        operation = self._tg_recorder.begin_operation(
            "starting_point", "START_POINT", conditions=conditions, relation_id=relation,
            event_slots=1,
        )
        if point is None:
            self._tg_recorder.emit(
                "START_POINT", "START_POINT", operation_ordinal=operation,
                requested_conditions=_condition_pairs(conditions),
                resolved_coordinates=None,
                relation_id=relation,
                outcome="FAILED",
                details={"reason": "EQUILIBRIUM_RETURNED_NONE"},
            )
            self._tg_recorder.end_operation(
                operation,
                outcome="FAILED",
                details={"reason": "EQUILIBRIUM_RETURNED_NONE"},
            )
            return False
        exit_hint, direction, reason = self._validate_custom_starting_point(point, direction)
        coordinates, phases, instances = _point_observation(self, point)
        if reason is not None:
            self._tg_recorder.emit(
                "START_POINT", "START_POINT", operation_ordinal=operation,
                requested_conditions=_condition_pairs(conditions),
                resolved_coordinates=coordinates,
                phases=phases,
                phase_instances=instances,
                relation_id=relation,
                outcome="ABANDONED",
                details={"reason_digest": sha256(str(reason).encode()).hexdigest()},
            )
            self._tg_recorder.end_operation(
                operation,
                outcome="ABANDONED",
                details={"reason": "START_POINT_VALIDATION_REJECTED"},
            )
            return False
        if exit_hint == m.ExitHint.NORMAL:
            self.node_queue.add_node(
                self._create_node_from_point(point, None, None, None, exit_hint),
                force_add,
            )
        elif direction is None:
            self.node_queue.add_node(
                self._create_node_from_point(
                    point, None, None, m.Direction.POSITIVE, m.ExitHint.POINT_IS_EXIT
                ),
                force_add,
            )
            self.node_queue.add_node(
                self._create_node_from_point(
                    point, None, None, m.Direction.NEGATIVE, m.ExitHint.POINT_IS_EXIT
                ),
                force_add,
            )
        else:
            self.node_queue.add_node(
                self._create_node_from_point(
                    point, None, None, direction, m.ExitHint.POINT_IS_EXIT
                ),
                force_add,
            )
        self._tg_recorder.emit(
            "START_POINT", "START_POINT", operation_ordinal=operation,
            requested_conditions=_condition_pairs(conditions),
            resolved_coordinates=coordinates,
            phases=phases,
            phase_instances=instances,
            relation_id=relation,
            outcome="ACCEPTED",
            details={"direction": None if direction is None else str(direction)},
        )
        self._tg_recorder.end_operation(
            operation,
            outcome="ACCEPTED",
            details={"result": "START_POINT_ACCEPTED"},
        )
        return True

    def _take_step(self, point, axis_var, axis_delta, axis_lims, direction):
        new_conditions, hit_limit = self._step_conditions(
            point, axis_var, axis_delta, axis_lims, direction
        )
        if hit_limit:
            operation = self._tg_recorder.begin_operation(
                "axis_limit", "STEP", conditions=new_conditions, event_slots=1
            )
            self._tg_recorder.emit(
                "AXIS_TRANSITION", "STEP", operation_ordinal=operation,
                requested_conditions=_condition_pairs(new_conditions),
                resolved_coordinates=None,
                outcome="ABANDONED",
                details={"axis": str(axis_var), "reason": "AXIS_LIMIT"},
            )
            self._tg_recorder.end_operation(
                operation,
                outcome="ABANDONED",
                details={"reason": "AXIS_LIMIT"},
            )
            return None
        return self._tg_helpers["_update_equilibrium"](
            self, point, new_conditions, self._other_av(axis_var)
        )

    def _test_direction(self, point, axis_var, direction):
        m = self._tg_modules
        relation = self._tg_recorder.relation()
        operation = self._tg_recorder.begin_operation(
            "direction_probe", "DIRECTION", relation_id=relation,
            details={"axis": str(axis_var), "direction": str(direction)},
            event_slots=2,
        )
        coordinates, phases, instances = _point_observation(self, point)
        begin = self._tg_recorder.emit(
            "DIRECTION_PROBE", "DIRECTION", operation_ordinal=operation,
            resolved_coordinates=coordinates,
            phases=phases,
            phase_instances=instances,
            relation_id=relation,
            outcome="ACCEPTED",
            details={"axis": str(axis_var), "direction": str(direction), "stage": "BEGIN"},
        )
        other_axis = self._other_av(axis_var) if len(self.axis_vars) > 1 else None
        other_value = point.get_property(other_axis) if other_axis is not None else None
        current_delta = self.axis_delta[axis_var] * self.MIN_DELTA_RATIO
        new_conditions, hit_limit = self._step_conditions(
            point, axis_var, current_delta, self.axis_lims[axis_var], direction
        )
        result = None
        probe_coordinates = None
        probe_phases: tuple[str, ...] = ()
        probe_instances: tuple[str, ...] = ()
        if not hit_limit:
            try:
                step_results = self._tg_helpers["_update_equilibrium"](
                    self, point, new_conditions, other_axis
                )
                if step_results is not None:
                    probe_coordinates, probe_phases, probe_instances = _point_observation(
                        self, step_results[0]
                    )
                valid = m.zchk.simple_check_valid_point(step_results)
                if valid:
                    valid = m.zchk.simple_check_change_in_phases(step_results)
                if valid:
                    global_point = self._tg_helpers["_find_global_min_point"](
                        self, step_results[0]
                    )
                    valid = global_point is None
                if valid:
                    other_delta = None
                    new_point, _orig = step_results
                    if other_axis is not None:
                        other_delta = abs(other_value - new_point.get_property(other_axis))
                    result = current_delta, other_delta
            except InstrumentationBudgetExceeded:
                raise
            except BaseException as error:
                self._tg_recorder.emit(
                    "DIRECTION_PROBE", "DIRECTION", operation_ordinal=operation,
                    requested_conditions=_condition_pairs(new_conditions),
                    resolved_coordinates=probe_coordinates,
                    phases=probe_phases,
                    phase_instances=probe_instances,
                    exception=error,
                    parent_event_id=begin,
                    relation_id=relation,
                    outcome="FAILED",
                    details={
                        "axis": str(axis_var),
                        "direction": str(direction),
                        "stage": "ERROR",
                    },
                )
                self._tg_recorder.end_operation(
                    operation,
                    outcome="FAILED",
                    exception=error,
                    details={"result": "DIRECTION_ERROR"},
                )
                raise
        self._tg_recorder.emit(
            "DIRECTION_PROBE", "DIRECTION", operation_ordinal=operation,
            requested_conditions=_condition_pairs(new_conditions),
            resolved_coordinates=probe_coordinates,
            phases=probe_phases,
            phase_instances=probe_instances,
            parent_event_id=begin,
            relation_id=relation,
            outcome=("ACCEPTED" if result is not None else "FAILED"),
            details={"axis": str(axis_var), "direction": str(direction), "stage": "END"},
        )
        self._tg_recorder.end_operation(
            operation,
            outcome=("ACCEPTED" if result is not None else "FAILED"),
            details={"result": "DIRECTION_ACCEPTED" if result is not None else "DIRECTION_REJECTED"},
        )
        return result

    def _attempt_to_add_point(self, zpf_line, step_results):
        m = self._tg_modules
        checks = (
            ("VALID_POINT", m.zchk.check_valid_point),
            (
                "CHANGE_IN_PHASES",
                lambda line, result, axes, **kw: self._tg_helpers[
                    "_check_change_in_phases"
                ](self, line, result, axes, **kw),
            ),
            (
                "GLOBAL_MINIMUM",
                lambda line, result, axes, **kw: self._tg_helpers[
                    "_check_global_min"
                ](self, line, result, axes, **kw),
            ),
            ("AXIS_VALUES", m.zchk.check_axis_values),
            ("SIMILAR_PHASE_COMPOSITION", m.zchk.check_similar_phase_composition),
            ("CIRCULAR_LOOP", m.zchk.check_circular_loop),
        )
        axis_data = {
            "axis_vars": self.axis_vars,
            "axis_delta": self.axis_delta,
            "axis_lims": self.axis_lims,
        }
        extra = {
            "delta_scale": self.DELTA_SCALE,
            "min_delta_ratio": self.MIN_DELTA_RATIO,
            "global_check_interval": self.GLOBAL_CHECK_INTERVAL,
            "global_num_candidates": self.GLOBAL_MIN_NUM_CANDIDATES,
            "normalize_factor": {axis: self.normalize_factor(axis) for axis in self.axis_vars},
            "system_info": self.system_info,
            "pdens": self.GLOBAL_MIN_PDENS,
            "tol": self.GLOBAL_MIN_TOL,
        }
        for name, check in checks:
            before = str(zpf_line.status)
            operation = self._tg_recorder.begin_operation(
                "invariant_check", "INVARIANT", details={"check": name}, event_slots=1
            )
            try:
                new_node = check(zpf_line, step_results, axis_data, **extra)
            except InstrumentationBudgetExceeded:
                raise
            except BaseException as error:
                self._tg_recorder.emit(
                    "INVARIANT_CHECK", "INVARIANT", operation_ordinal=operation,
                    exception=error,
                    outcome="FAILED",
                    details={
                        "check": name,
                        "status_before": before,
                        "status_after": str(zpf_line.status),
                    },
                )
                self._tg_recorder.end_operation(
                    operation,
                    outcome="FAILED",
                    exception=error,
                    details={"check": name},
                )
                raise
            after = str(zpf_line.status)
            self._tg_recorder.emit(
                "INVARIANT_CHECK", "INVARIANT", operation_ordinal=operation,
                outcome=("ACCEPTED" if after == before else "FAILED"),
                details={"check": name, "status_before": before, "status_after": after},
            )
            self._tg_recorder.end_operation(
                operation,
                outcome=("ACCEPTED" if after == before else "FAILED"),
                details={"check": name},
            )
            if zpf_line.status == m.ZPFState.NEW_NODE_FOUND:
                transition_operation = self._tg_recorder.begin_operation(
                    "zpf_transition", "ZPF", event_slots=1
                )
                self._tg_recorder.emit(
                    "ZPF_LINE_TRANSITION", "ZPF",
                    operation_ordinal=transition_operation,
                    outcome="ACCEPTED",
                    details={
                        "transition": "ENDED_AT_NEW_NODE",
                        "status": str(zpf_line.status),
                        "line_id": self._tg_recorder.object_token("LINE", zpf_line),
                    },
                )
                self._tg_recorder.end_operation(
                    transition_operation,
                    outcome="ACCEPTED",
                    details={"transition": "ENDED_AT_NEW_NODE"},
                )
                self._process_new_node(zpf_line, new_node)
                return
            if zpf_line.status == m.ZPFState.ATTEMPT_NEW_STEP:
                transition_operation = self._tg_recorder.begin_operation(
                    "zpf_transition", "ZPF", event_slots=1
                )
                self._tg_recorder.emit(
                    "AXIS_TRANSITION", "ZPF",
                    operation_ordinal=transition_operation,
                    outcome="ABANDONED",
                    details={
                        "transition": "RETRY_WITH_REDUCED_DELTA",
                        "line_id": self._tg_recorder.object_token("LINE", zpf_line),
                    },
                )
                zpf_line.status = m.ZPFState.NOT_FINISHED
                self._tg_recorder.end_operation(
                    transition_operation,
                    outcome="ABANDONED",
                    details={"transition": "RETRY_WITH_REDUCED_DELTA"},
                )
                return
            if zpf_line.status != m.ZPFState.NOT_FINISHED:
                break
        if zpf_line.status in (m.ZPFState.NOT_FINISHED, m.ZPFState.REACHED_LIMIT):
            new_point, _ = step_results
            append_slots = 2 if zpf_line.status == m.ZPFState.REACHED_LIMIT else 1
            append_operation = self._tg_recorder.begin_operation(
                "zpf_point_append", "ZPF", event_slots=append_slots
            )
            zpf_line.append(new_point)
            coordinates, phases, instances = _point_observation(self, new_point)
            self._tg_recorder.emit(
                "ZPF_LINE_TRANSITION", "ZPF", resolved_coordinates=coordinates,
                operation_ordinal=append_operation,
                phases=phases,
                phase_instances=instances,
                outcome="ACCEPTED",
                details={
                    "transition": "POINT_APPENDED",
                    "line_id": self._tg_recorder.object_token("LINE", zpf_line),
                    "point_id": self._tg_recorder.object_token("POINT", new_point),
                },
            )
            if zpf_line.current_delta < self.axis_delta[zpf_line.axis_var]:
                zpf_line.current_delta = m.np_amin(
                    [
                        self.axis_delta[zpf_line.axis_var],
                        zpf_line.current_delta / self.DELTA_SCALE,
                    ]
                )
            if zpf_line.status == m.ZPFState.REACHED_LIMIT:
                self._tg_recorder.emit(
                    "ZPF_LINE_TRANSITION", "ZPF",
                    operation_ordinal=append_operation,
                    outcome="ACCEPTED",
                    details={
                        "transition": "ENDED_AT_LIMIT",
                        "status": str(zpf_line.status),
                        "line_id": self._tg_recorder.object_token("LINE", zpf_line),
                    },
                )
            self._tg_recorder.end_operation(
                append_operation,
                outcome="ACCEPTED",
                details={"transition": "POINT_APPENDED"},
            )
        elif zpf_line.status != m.ZPFState.NOT_FINISHED:
            transition_operation = self._tg_recorder.begin_operation(
                "zpf_transition", "ZPF", event_slots=1
            )
            self._tg_recorder.emit(
                "ZPF_LINE_TRANSITION", "ZPF",
                operation_ordinal=transition_operation,
                outcome="FAILED",
                details={
                    "transition": "ENDED_WITH_FAILURE",
                    "status": str(zpf_line.status),
                    "line_id": self._tg_recorder.object_token("LINE", zpf_line),
                },
            )
            self._tg_recorder.end_operation(
                transition_operation,
                outcome="FAILED",
                details={"transition": "ENDED_WITH_FAILURE"},
            )
        if self._tg_kind == "step" and zpf_line.status == m.ZPFState.FAILED:
            # StepStrategy has a recovery tail beyond MapStrategy's common
            # invariant loop. Preserve it so automatic scans do not lose the
            # next forced starting point.
            self._add_starting_point_at_last_condition(
                zpf_line.points[-1].global_conditions,
                zpf_line.axis_direction,
            )

    def _tg_process_new_node_base(self, zpf_line, new_node):
        """Pinned MapStrategy._process_new_node port with ordered mutations."""

        m = self._tg_modules
        line_id = self._tg_recorder.object_token("LINE", zpf_line)
        relation = self._tg_recorder.relation()
        node_position = m.np_array(
            [new_node.get_property(axis) for axis in self.axis_vars]
        )
        removal_indices: list[int] = []
        for index in range(len(zpf_line.points) - 1, 0, -1):
            first = zpf_line.points[index]
            second = zpf_line.points[index - 1]
            first_position = m.np_array(
                [first.get_property(axis) for axis in self.axis_vars]
            )
            second_position = m.np_array(
                [second.get_property(axis) for axis in self.axis_vars]
            )
            if m.np_dot(
                first_position - second_position,
                node_position - first_position,
            ) < 0:
                removal_indices.append(index)
            else:
                break
        operation = self._tg_recorder.begin_operation(
            "zpf_backtrack",
            "ZPF",
            relation_id=relation,
            details={"line_id": line_id},
            event_slots=len(removal_indices) + 3,
        )
        backtrack = self._tg_recorder.emit(
            "BACKTRACK",
            "ZPF",
            operation_ordinal=operation,
            relation_id=relation,
            outcome="ACCEPTED",
            details={
                "line_id": line_id,
                "removed_count": len(removal_indices),
                "before_count": len(zpf_line.points),
                "after_count": len(zpf_line.points) - len(removal_indices),
            },
        )
        for index in removal_indices:
            point = zpf_line.points[index]
            del zpf_line.points[index]
            coordinates, phases, instances = _point_observation(self, point)
            self._tg_recorder.emit(
                "ZPF_POINT_DELETED",
                "ZPF",
                operation_ordinal=operation,
                resolved_coordinates=coordinates,
                phases=phases,
                phase_instances=instances,
                parent_event_id=backtrack,
                relation_id=relation,
                outcome="ABANDONED",
                details={
                    "line_id": line_id,
                    "point_id": self._tg_recorder.object_token("POINT", point),
                    "reason": "BACKTRACK",
                },
            )

        parent = new_node.parent
        zpf_line.append(parent)
        coordinates, phases, instances = _point_observation(self, parent)
        appended = self._tg_recorder.emit(
            "ZPF_LINE_TRANSITION",
            "ZPF",
            operation_ordinal=operation,
            resolved_coordinates=coordinates,
            phases=phases,
            phase_instances=instances,
            parent_event_id=backtrack,
            relation_id=relation,
            outcome="ACCEPTED",
            details={
                "transition": "NODE_PARENT_APPENDED",
                "line_id": line_id,
                "point_id": self._tg_recorder.object_token("POINT", parent),
            },
        )
        new_node.axis_var = zpf_line.axis_var
        new_node.axis_direction = zpf_line.axis_direction
        node_coordinates, node_phases, node_instances = _point_observation(
            self, new_node
        )
        self._tg_recorder.emit(
            "ZPF_RELATION",
            "ZPF",
            operation_ordinal=operation,
            resolved_coordinates=node_coordinates,
            phases=node_phases,
            phase_instances=node_instances,
            parent_event_id=appended,
            relation_id=relation,
            outcome="ACCEPTED",
            details={
                "relation": "ZPF_LINE_TO_NODE",
                "line_id": line_id,
                "node_id": self._tg_recorder.object_token("NODE", new_node),
            },
        )
        self._tg_recorder.end_operation(
            operation,
            outcome="ACCEPTED",
            details={"removed_count": len(removal_indices)},
        )
        if len(self.axis_vars) == 1:
            self.node_queue.add_node(new_node, check_parent=True)
        else:
            self.node_queue.add_node(new_node)

    def _process_new_node(self, zpf_line, new_node):
        m = self._tg_modules
        before_points = tuple(zpf_line.points)
        line_id = self._tg_recorder.object_token("LINE", zpf_line)
        if self._tg_kind in ("binary", "ternary"):
            cs_result = self._tg_helpers["_find_global_min_cs"](self, new_node)
            if cs_result is not None and not self._tg_helpers[
                "_detect_degenerate_phase"
            ](
                self, new_node, cs_result[0]
            ):
                cs_result = None
            if cs_result is None:
                self._tg_process_new_node_base(zpf_line, new_node)
            else:
                relation = self._tg_recorder.relation()
                operation = self._tg_recorder.begin_operation(
                    "metastable_discard",
                    "ZPF",
                    relation_id=relation,
                    details={"line_id": line_id},
                    event_slots=1 + len(before_points),
                )
                if self.zpf_lines and self.zpf_lines[-1] is zpf_line:
                    self.zpf_lines.pop(-1)
                coordinates, phases, instances = _point_observation(self, new_node)
                discard = self._tg_recorder.emit(
                    "METASTABLE_LINE_DISCARD", "ZPF",
                    operation_ordinal=operation,
                    resolved_coordinates=coordinates,
                    phases=phases,
                    phase_instances=instances,
                    relation_id=relation,
                    outcome="ABANDONED",
                    details={
                        "line_id": line_id,
                        "reason": "POST_NODE_GLOBAL_MINIMUM",
                        "discarded_point_count": len(before_points),
                    },
                )
                for point in before_points:
                    point_coordinates, point_phases, point_instances = _point_observation(
                        self, point
                    )
                    self._tg_recorder.emit(
                        "ZPF_POINT_DELETED", "ZPF",
                        operation_ordinal=operation,
                        resolved_coordinates=point_coordinates,
                        phases=point_phases,
                        phase_instances=point_instances,
                        parent_event_id=discard,
                        relation_id=relation,
                        outcome="ABANDONED",
                        details={
                            "line_id": line_id,
                            "point_id": self._tg_recorder.object_token("POINT", point),
                            "reason": "METASTABLE_LINE_DISCARD",
                        },
                    )
                self._tg_recorder.end_operation(
                    operation,
                    outcome="ABANDONED",
                    details={"reason": "POST_NODE_GLOBAL_MINIMUM"},
                )
                return
        else:
            self._tg_process_new_node_base(zpf_line, new_node)

    def _start_zpf_line(self):
        before = len(self.zpf_lines)
        relation = self._tg_recorder.relation()
        operation = self._tg_recorder.begin_operation(
            "zpf_start", "ZPF", relation_id=relation,
            details={"exit_index": self._exit_index},
            event_slots=2,
        )
        try:
            super()._start_zpf_line()
        except InstrumentationBudgetExceeded:
            raise
        except BaseException as error:
            self._tg_recorder.emit(
                "ZPF_LINE_TRANSITION",
                "ZPF",
                operation_ordinal=operation,
                exception=error,
                relation_id=relation,
                outcome="FAILED",
                details={"transition": "START_FAILED"},
            )
            self._tg_recorder.end_operation(
                operation,
                outcome="FAILED",
                exception=error,
                details={"transition": "START_FAILED"},
            )
            raise
        if len(self.zpf_lines) == before:
            self._tg_recorder.emit(
                "ZPF_LINE_TRANSITION", "ZPF", operation_ordinal=operation,
                relation_id=relation,
                outcome="ABANDONED",
                details={"transition": "START_REJECTED"},
            )
            self._tg_recorder.end_operation(
                operation,
                outcome="ABANDONED",
                details={"transition": "START_REJECTED"},
            )
            return
        line = self.zpf_lines[-1]
        point = line.points[-1] if line.points else None
        coordinates, phases, instances = _point_observation(self, point)
        start = self._tg_recorder.emit(
            "ZPF_LINE_TRANSITION", "ZPF", operation_ordinal=operation,
            resolved_coordinates=coordinates,
            phases=phases,
            phase_instances=instances,
            relation_id=relation,
            outcome="ACCEPTED",
            details={
                "transition": "STARTED",
                "line_id": self._tg_recorder.object_token("LINE", line),
            },
        )
        if self._current_node is not None:
            self._tg_recorder.emit(
                "ZPF_RELATION", "ZPF", operation_ordinal=operation,
                resolved_coordinates=coordinates,
                phases=phases,
                phase_instances=instances,
                parent_event_id=start,
                relation_id=relation,
                outcome="ACCEPTED",
                details={
                    "relation": "NODE_TO_ZPF_LINE",
                    "node_id": self._tg_recorder.object_token("NODE", self._current_node),
                    "line_id": self._tg_recorder.object_token("LINE", line),
                },
            )
        self._tg_recorder.end_operation(
            operation,
            outcome="ACCEPTED",
            details={"transition": "STARTED"},
        )

    def _find_node_exits(self):
        operation = self._tg_recorder.begin_operation(
            "node_exit", "NODE_EXIT", event_slots=1
        )
        try:
            super()._find_node_exits()
        except InstrumentationBudgetExceeded:
            raise
        except BaseException as error:
            self._tg_recorder.emit(
                "INVARIANT_CHECK",
                "NODE_EXIT",
                operation_ordinal=operation,
                exception=error,
                outcome="FAILED",
                details={"check": "NODE_EXITS"},
            )
            self._tg_recorder.end_operation(
                operation,
                outcome="FAILED",
                exception=error,
                details={"check": "NODE_EXITS"},
            )
            raise
        coordinates, phases, instances = _point_observation(self, self._current_node)
        self._tg_recorder.emit(
            "INVARIANT_CHECK", "NODE_EXIT",
            operation_ordinal=operation,
            resolved_coordinates=coordinates,
            phases=phases,
            phase_instances=instances,
            outcome="ACCEPTED",
            details={
                "check": "NODE_EXITS",
                "exit_count": len(self._exits),
                "node_id": self._tg_recorder.object_token("NODE", self._current_node),
            },
        )
        self._tg_recorder.end_operation(
            operation,
            outcome="ACCEPTED",
            details={"check": "NODE_EXITS"},
        )

    def _tg_do_map_core(self, max_iter=-1):
        self._tg_assert_strategy_active()
        self._tg_recorder._verify_runtime_guard(deep=True)
        self._tg_verify_runtime()
        self._tg_scope_depth += 1
        scope = self._tg_scope_depth
        self._tg_last_finished = False
        self._tg_last_iteration_bound = False
        try:
            if len(self.node_queue.nodes) == 0 and len(self.zpf_lines) == 0:
                operation = self._tg_recorder.begin_operation(
                    "automatic_start_scan", "START_POINT_SCAN", details={"scope": scope},
                    event_slots=2,
                )
                self._tg_recorder.emit(
                    "START_POINT_SCAN", "START_POINT_SCAN", operation_ordinal=operation,
                    outcome="ACCEPTED", details={"transition": "BEGIN", "scope": scope},
                )
                self._tg_verify_runtime()
                self.generate_automatic_starting_points()
                self._tg_recorder.emit(
                    "START_POINT_SCAN", "START_POINT_SCAN", operation_ordinal=operation,
                    outcome=("ACCEPTED" if self.node_queue.nodes else "ABANDONED"),
                    details={
                        "transition": "END",
                        "scope": scope,
                        "node_count": len(self.node_queue.nodes),
                    },
                )
                self._tg_recorder.end_operation(
                    operation,
                    outcome=("ACCEPTED" if self.node_queue.nodes else "ABANDONED"),
                    details={"scope": scope},
                )
            finished = False
            iterations = 0
            while not finished and (max_iter == -1 or iterations < max_iter):
                operation = self._tg_recorder.begin_operation(
                    "strategy_iterate", "ITERATE", details={"scope": scope, "iteration": iterations},
                    event_slots=1,
                )
                self._tg_verify_runtime()
                finished = self.iterate()
                self._tg_recorder.emit(
                    "ZPF_LINE_TRANSITION", "ITERATE", operation_ordinal=operation,
                    outcome="ACCEPTED",
                    details={
                        "transition": "ITERATION_END",
                        "scope": scope,
                        "iteration": iterations,
                        "queue_remaining": self.node_queue.size(),
                        "finished": bool(finished),
                    },
                )
                self._tg_recorder.end_operation(
                    operation,
                    outcome="ACCEPTED",
                    details={"scope": scope, "iteration": iterations},
                )
                iterations += 1
            self._tg_last_finished = bool(finished)
            if finished:
                self._tg_recorder.emit(
                    "TERMINATION", "SCOPE",
                    outcome="ACCEPTED",
                    details={
                        "reason_code": "SCOPE_QUEUE_EXHAUSTED",
                        "scope": scope,
                        "completion_claim": False,
                    },
                )
            elif max_iter != -1:
                self._tg_last_iteration_bound = True
                self._tg_recorder.emit(
                    "TERMINATION", "SCOPE",
                    outcome="ABANDONED",
                    details={"reason_code": "MAX_ITER_REACHED", "scope": scope, "completion_claim": False},
                )
            return None
        finally:
            self._tg_scope_depth -= 1

    def do_map(self, max_iter=-1):
        """Redispatch explicit mixin calls through the owned class gate."""

        try:
            target = vars(type(self)).get("do_map")
        except BaseException as error:
            raise MappingInstrumentationError(
                "W2B_INSTRUMENT_SESSION_REQUIRED"
            ) from error
        if (
            not isinstance(target, types.FunctionType)
            or target is _InstrumentedStrategyMixin.do_map
        ):
            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
        return target(self, max_iter=max_iter)


def _instrumented_classes(
    modules: _RuntimeModules,
    strategy_gate: object | None = None,
) -> Mapping[str, type]:
    if type(modules) is not _RuntimeModules:
        _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
    gate = strategy_gate
    if gate is None:
        def denied_gate(_action: str, *_values: object):
            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")

        gate = denied_gate
    if not isinstance(gate, types.FunctionType):
        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
    base_do_map = _InstrumentedStrategyMixin._tg_do_map_core

    def guarded_do_map(self, max_iter=-1):
        marker = gate("enter_strategy", self)
        try:
            return base_do_map(self, max_iter=max_iter)
        finally:
            gate("exit_strategy", self, marker)

    def register_child(self, child):
        return gate("register_child", self, child)

    def assert_strategy_active(self):
        return gate("assert_active", self)

    def child_classes(self):
        return _instrumented_classes(modules, gate)

    class InstrumentedBinary(_InstrumentedStrategyMixin, modules.BinaryStrategy):
        do_map = guarded_do_map
        _tg_register_child = register_child
        _tg_assert_strategy_active = assert_strategy_active
        _tg_instrumented_classes = child_classes

    class InstrumentedIsopleth(_InstrumentedStrategyMixin, modules.IsoplethStrategy):
        do_map = guarded_do_map
        _tg_register_child = register_child
        _tg_assert_strategy_active = assert_strategy_active
        _tg_instrumented_classes = child_classes

    class InstrumentedTernary(_InstrumentedStrategyMixin, modules.TernaryStrategy):
        do_map = guarded_do_map
        _tg_register_child = register_child
        _tg_assert_strategy_active = assert_strategy_active
        _tg_instrumented_classes = child_classes

    class InstrumentedStep(_InstrumentedStrategyMixin, modules.StepStrategy):
        do_map = guarded_do_map
        _tg_register_child = register_child
        _tg_assert_strategy_active = assert_strategy_active
        _tg_instrumented_classes = child_classes

    return MappingProxyType(
        {
            "binary": InstrumentedBinary,
            "isopleth": InstrumentedIsopleth,
            "ternary": InstrumentedTernary,
            "step": InstrumentedStep,
        }
    )


def _strategy_method_bindings(strategy: object) -> tuple[tuple[str, object], ...]:
    """Capture all resolved Python method identities across the strategy MRO."""

    names: set[str] = set()
    for cls in type(strategy).__mro__:
        for name, member in vars(cls).items():
            target = member.__func__ if isinstance(member, (staticmethod, classmethod)) else member
            if isinstance(member, property):
                continue
            if getattr(target, "__code__", None) is not None:
                names.add(name)
    bindings: list[tuple[str, object]] = []
    for name in sorted(names):
        try:
            resolved = getattr(strategy, name)
        except Exception as error:
            raise MappingInstrumentationError("W2B_INSTRUMENT_UPSTREAM_MISMATCH") from error
        function = getattr(resolved, "__func__", resolved)
        if getattr(function, "__code__", None) is None:
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        bindings.append((name, function))
    return tuple(bindings)


def _runtime_sequence(value: object) -> object:
    if hasattr(value, "tolist"):
        try:
            value = value.tolist()
        except Exception as error:
            raise MappingInstrumentationError("W2B_INSTRUMENT_DOMAIN_MISMATCH") from error
    if type(value) in (tuple, list):
        return tuple(_runtime_sequence(item) for item in value)
    return _solver_number(value)


def _capture_fixed_mutable_graph(
    roots: object,
) -> tuple[tuple[object, ...], ...]:
    """Capture exact identities and transitive mutable contents of fixed inputs."""

    try:
        if type(roots) is not tuple or not roots:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        records: list[tuple[object, ...]] = []
        seen: set[int] = set()

        def visit(value: object, depth: int) -> None:
            if depth > 64 or len(records) > 500_000:
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            if (
                value is None
                or type(value) in (bool, int, float, complex, str, bytes)
                or isinstance(value, (type, types.FunctionType, types.ModuleType))
            ):
                return
            marker = id(value)
            if marker in seen:
                return
            seen.add(marker)
            value_type = type(value)
            module_name = value_type.__module__
            if type(module_name) is not str:
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            if module_name.startswith("numpy") and all(
                hasattr(value, name)
                for name in ("dtype", "shape", "strides", "tobytes")
            ):
                dtype_text = str(value.dtype)
                shape = tuple(value.shape)
                strides = tuple(value.strides)
                payload = value.tobytes(order="C")
                if (
                    type(dtype_text) is not str
                    or type(shape) is not tuple
                    or any(type(item) is not int for item in shape)
                    or type(strides) is not tuple
                    or any(type(item) is not int for item in strides)
                    or type(payload) is not bytes
                ):
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
                records.append((
                    "array", value, value_type, dtype_text, shape, strides,
                    len(payload), sha256(payload).hexdigest(),
                ))
                return
            if type(value) is bytearray:
                payload = bytes(value)
                records.append((
                    "bytearray", value, value_type, len(payload),
                    sha256(payload).hexdigest(),
                ))
                return
            if (
                module_name == "tinydb.utils"
                and value_type.__qualname__ == "LRUCache"
            ):
                cache = object.__getattribute__(value, "cache")
                capacity = object.__getattribute__(value, "capacity")
                if (
                    type(cache).__module__ != "collections"
                    or type(cache).__qualname__ != "OrderedDict"
                    or type(capacity) is not int
                    or capacity < 0
                ):
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
                items = tuple(dict.items(cache))
                entry_roots = tuple(
                    entry
                    for key, cached_value in items
                    for entry in (key, cached_value)
                )
                entry_graph = (
                    ()
                    if not entry_roots
                    else _capture_fixed_mutable_graph(entry_roots)
                )
                records.append((
                    "tinydb_query_cache",
                    value,
                    value_type,
                    capacity,
                    cache,
                    type(cache),
                    items,
                    entry_roots,
                    entry_graph,
                ))
                # Query results and QueryInstance._hash are an explicitly
                # mutable optimization.  Their exact identities are checked
                # before mapping, but their transitive implementation state
                # is not treated as thermodynamic input state.
                return
            if isinstance(value, dict):
                # Bypass user-defined Mapping.items()/__iter__ hooks. Some
                # pinned cache mappings lazily mutate an OrderedDict while
                # their abstract-Mapping iterator runs; the concrete dict
                # view is a stable snapshot of the already-present entries.
                items = tuple(dict.items(value))
                if any(type(item) is not tuple or len(item) != 2 for item in items):
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
                records.append(("mapping", value, value_type, items))
                for key, item in items:
                    visit(key, depth + 1)
                    visit(item, depth + 1)
                # TinyDB Document is a dict subclass whose public ``doc_id``
                # is retained in the instance namespace rather than among
                # the document fields. Capture both views so an in-place
                # metadata mutation cannot preserve the mapping card.
                if (
                    value_type is not dict
                    and module_name.startswith(("pycalphad.", "tinydb."))
                ):
                    try:
                        namespace = object.__getattribute__(value, "__dict__")
                    except AttributeError:
                        namespace = None
                    if namespace is not None:
                        if type(namespace) is not dict:
                            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
                        records.append(("object", value, value_type, namespace))
                        visit(namespace, depth + 1)
                return
            if type(value) in (list, tuple):
                items = tuple(value)
                records.append(("sequence", value, value_type, items))
                for item in items:
                    visit(item, depth + 1)
                return
            if isinstance(value, Mapping):
                # Non-dict Mapping implementations are treated as objects;
                # their exact namespace and any concrete nested containers
                # are captured below without executing an overloadable
                # public iteration protocol.
                pass
            if type(value) in (set, frozenset):
                items = tuple(value)
                records.append(("set", value, value_type, items))
                for item in items:
                    visit(item, depth + 1)
                return
            if module_name.startswith(("pycalphad.", "tinydb.")):
                try:
                    namespace = object.__getattribute__(value, "__dict__")
                except AttributeError:
                    return
                if type(namespace) is not dict:
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
                records.append(("object", value, value_type, namespace))
                visit(namespace, depth + 1)

        for root in roots:
            visit(root, 0)
        return tuple(records)
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _same_fixed_graph_value(left: object, right: object) -> bool:
    """Compare immutable built-ins by exact value, everything else by identity."""

    if left is right:
        return True
    if type(left) is not type(right):
        return False
    if type(left) in (bool, int, str, bytes):
        return left == right
    if type(left) is float:
        try:
            return struct.pack(">d", left) == struct.pack(">d", right)
        except (OverflowError, struct.error):
            return False
    if type(left) is complex:
        try:
            return (
                struct.pack(">d", left.real) == struct.pack(">d", right.real)
                and struct.pack(">d", left.imag)
                == struct.pack(">d", right.imag)
            )
        except (OverflowError, struct.error):
            return False
    return False


def _verify_fixed_mutable_graph(
    roots: object,
    expected: object,
    *,
    allow_runtime_cache_changes: bool = False,
) -> None:
    """Verify a mutable graph without invoking value equality on its objects."""

    try:
        if (
            type(expected) is not tuple
            or type(allow_runtime_cache_changes) is not bool
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        observed = _capture_fixed_mutable_graph(roots)
        if len(observed) != len(expected):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        for observed_row, expected_row in zip(observed, expected):
            if (
                type(observed_row) is not tuple
                or type(expected_row) is not tuple
                or len(observed_row) != len(expected_row)
                or len(observed_row) < 3
                or type(observed_row[0]) is not str
                or observed_row[0] != expected_row[0]
                or observed_row[1] is not expected_row[1]
                or observed_row[2] is not expected_row[2]
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            kind = observed_row[0]
            if kind in ("mapping", "sequence"):
                observed_items = observed_row[3]
                expected_items = expected_row[3]
                if (
                    type(observed_items) is not tuple
                    or type(expected_items) is not tuple
                    or len(observed_items) != len(expected_items)
                ):
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
                if kind == "mapping":
                    if any(
                        not _same_fixed_graph_value(
                            observed_item[0], expected_item[0]
                        )
                        or not _same_fixed_graph_value(
                            observed_item[1], expected_item[1]
                        )
                        for observed_item, expected_item
                        in zip(observed_items, expected_items)
                    ):
                        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
                elif any(
                    not _same_fixed_graph_value(
                        observed_item, expected_item
                    )
                    for observed_item, expected_item
                    in zip(observed_items, expected_items)
                ):
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            elif kind == "set":
                observed_items = observed_row[3]
                expected_items = expected_row[3]
                if (
                    type(observed_items) is not tuple
                    or type(expected_items) is not tuple
                    or len(observed_items) != len(expected_items)
                    or any(
                        sum(
                            _same_fixed_graph_value(item, expected_item)
                            for item in observed_items
                        ) != 1
                        for expected_item in expected_items
                    )
                ):
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            elif kind == "object":
                if observed_row[3] is not expected_row[3]:
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            elif kind == "tinydb_query_cache":
                if (
                    observed_row[3] != expected_row[3]
                    or observed_row[4] is not expected_row[4]
                    or observed_row[5] is not expected_row[5]
                    or type(observed_row[6]) is not tuple
                    or type(expected_row[6]) is not tuple
                    or type(expected_row[7]) is not tuple
                    or type(expected_row[8]) is not tuple
                    or (
                        not allow_runtime_cache_changes
                        and (
                            len(observed_row[6]) != len(expected_row[6])
                            or any(
                                left[0] is not right[0]
                                or not _same_fixed_graph_value(
                                    left[1], right[1]
                                )
                                for left, right in zip(
                                    observed_row[6], expected_row[6]
                                )
                            )
                        )
                    )
                ):
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
                if not allow_runtime_cache_changes:
                    if expected_row[7]:
                        _verify_fixed_mutable_graph(
                            expected_row[7],
                            expected_row[8],
                            allow_runtime_cache_changes=False,
                        )
                    elif expected_row[8]:
                        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            elif kind in ("array", "bytearray"):
                if any(
                    observed_value != expected_value
                    for observed_value, expected_value
                    in zip(observed_row[3:], expected_row[3:])
                ):
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            else:
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _fixed_mutable_graph_shape(
    card: object,
) -> tuple[dict[str, object], ...]:
    """Build a deterministic, address-free shape commitment for metadata."""

    if type(card) is not tuple:
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    rows = []
    for record in card:
        if type(record) is not tuple or len(record) < 3:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        kind, _value, value_type = record[:3]
        if type(kind) is not str or not isinstance(value_type, type):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        row = {
            "kind": kind,
            "type": f"{value_type.__module__}.{value_type.__qualname__}",
        }
        if kind in ("mapping", "sequence", "set"):
            row["size"] = len(record[3])
        elif kind == "object":
            row["fields"] = sorted(record[3])
        elif kind == "array":
            row.update({
                "dtype": record[3],
                "shape": list(record[4]),
                "strides": list(record[5]),
                "size": record[6],
                "sha256": record[7],
            })
        elif kind == "bytearray":
            row.update({"size": record[3], "sha256": record[4]})
        elif kind == "tinydb_query_cache":
            row.update({
                "capacity": record[3],
                "entry_count": len(record[6]),
                "entry_graph_sha256": canonical_trace_digest(
                    _fixed_mutable_graph_shape(record[8])
                ),
            })
        else:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        rows.append(row)
    return tuple(rows)


def _capture_phase_record_row(
    phase_records: object,
    phase: object,
    record: object = None,
) -> tuple[object, ...]:
    """Capture one solver PhaseRecord, including Cython public state."""

    try:
        if type(phase) is not str:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if record is None:
            record = phase_records[phase]
        phase_record_factory = object.__getattribute__(
            record, "phase_record_factory"
        )
        function_factory = object.__getattribute__(
            record, "function_factory"
        )
        sequence_cards = []
        for field_name in (
            "variables",
            "state_variables",
            "components",
            "pure_elements",
            "nonvacant_elements",
        ):
            value = object.__getattribute__(record, field_name)
            if type(value) not in (list, tuple):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            sequence_cards.append((value, type(value), tuple(value)))
        phase_dof = object.__getattribute__(record, "phase_dof")
        num_statevars = object.__getattribute__(record, "num_statevars")
        num_internal_cons = object.__getattribute__(
            record, "num_internal_cons"
        )
        phase_name = object.__getattribute__(record, "phase_name")
        if (
            phase_record_factory is not phase_records
            or type(phase_dof) is not int
            or phase_dof < 0
            or type(num_statevars) is not int
            or num_statevars < 0
            or type(num_internal_cons) is not int
            or num_internal_cons < 0
            or type(phase_name) is not str
            or phase_name != phase
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        return (
            phase,
            record,
            type(record),
            phase_record_factory,
            function_factory,
            type(function_factory),
            tuple(sequence_cards),
            _terminal_numeric_vector(
                object.__getattribute__(record, "molar_masses")
            ),
            _terminal_numeric_vector(
                object.__getattribute__(record, "parameters")
            ),
            phase_dof,
            num_statevars,
            num_internal_cons,
            phase_name,
        )
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _capture_phase_record_rows(
    phase_records: object,
    phases: object,
) -> tuple[tuple[object, ...], ...]:
    """Eagerly retain every solver PhaseRecord hidden in the factory cache."""

    try:
        if type(phases) not in (list, tuple) or any(
            type(phase) is not str for phase in phases
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        return tuple(
            _capture_phase_record_row(phase_records, phase)
            for phase in phases
        )
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _verify_phase_record_rows(
    observed: object,
    expected: object,
) -> None:
    """Verify exact cached PhaseRecord identities and all public solver state."""

    try:
        if (
            type(observed) is not tuple
            or type(expected) is not tuple
            or len(observed) != len(expected)
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        for left, right in zip(observed, expected):
            if (
                type(left) is not tuple
                or type(right) is not tuple
                or len(left) != 13
                or len(right) != 13
                or type(left[0]) is not str
                or left[0] != right[0]
                or left[2] is not right[2]
                or left[3] is not right[3]
                or left[5] is not right[5]
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            if left[1] is right[1] and left[4] is not right[4]:
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            left_sequences = left[6]
            right_sequences = right[6]
            if (
                type(left_sequences) is not tuple
                or type(right_sequences) is not tuple
                or len(left_sequences) != 5
                or len(right_sequences) != 5
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            for left_card, right_card in zip(
                left_sequences, right_sequences
            ):
                if (
                    type(left_card) is not tuple
                    or type(right_card) is not tuple
                    or len(left_card) != 3
                    or len(right_card) != 3
                    or left_card[0] is not right_card[0]
                    or left_card[1] is not right_card[1]
                    or type(left_card[2]) is not tuple
                    or type(right_card[2]) is not tuple
                    or len(left_card[2]) != len(right_card[2])
                    or any(
                        not _same_fixed_graph_value(
                            left_item, right_item
                        )
                        for left_item, right_item
                        in zip(left_card[2], right_card[2])
                    )
                ):
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            for index in (7, 8):
                if not _same_condition_value(left[index], right[index]):
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            if any(left[index] != right[index] for index in (9, 10, 11, 12)):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _strategy_configuration_bytes(strategy: object) -> bytes:
    try:
        axis_vars = tuple(getattr(strategy, "axis_vars"))
        axis_lims = getattr(strategy, "axis_lims")
        axis_delta = getattr(strategy, "axis_delta")
        constants = {
            name: _solver_number(getattr(strategy, name))
            for name in (
                "GLOBAL_MIN_PDENS",
                "GLOBAL_MIN_TOL",
                "GLOBAL_MIN_NUM_CANDIDATES",
                "GLOBAL_CHECK_INTERVAL",
                "DELTA_SCALE",
                "MIN_DELTA_RATIO",
            )
        }
        payload = {
            "components": list(getattr(strategy, "components")),
            "phases": list(getattr(strategy, "phases")),
            "conditions": dict(_condition_pairs(getattr(strategy, "conditions"))),
            "axis_vars": [str(axis) for axis in axis_vars],
            "axis_lims": [
                {"axis": str(axis), "value": _runtime_sequence(axis_lims[axis])}
                for axis in axis_vars
            ],
            "axis_delta": [
                {"axis": str(axis), "value": _runtime_sequence(axis_delta[axis])}
                for axis in axis_vars
            ],
            "constants": constants,
        }
        return canonical_trace_bytes(payload)
    except MappingInstrumentationError:
        raise
    except Exception as error:
        raise MappingInstrumentationError("W2B_INSTRUMENT_DOMAIN_MISMATCH") from error


def _capture_fixed_strategy_state(strategy: object) -> tuple[object, ...]:
    """Retain exact mapping-critical constructor state outside session slots."""

    try:
        namespace = object.__getattribute__(strategy, "__dict__")
        components = object.__getattribute__(strategy, "components")
        elements = object.__getattribute__(strategy, "elements")
        phases = object.__getattribute__(strategy, "phases")
        conditions = object.__getattribute__(strategy, "conditions")
        axis_vars = object.__getattribute__(strategy, "axis_vars")
        axis_lims = object.__getattribute__(strategy, "axis_lims")
        axis_delta = object.__getattribute__(strategy, "axis_delta")
        models = object.__getattribute__(strategy, "models")
        phase_records = object.__getattribute__(strategy, "phase_records")
        system_info = object.__getattribute__(strategy, "system_info")
        database = object.__getattribute__(strategy, "dbf")
        num_potential = object.__getattribute__(
            strategy, "num_potential_condition"
        )
        if (
            type(namespace) is not dict
            or type(components) is not list
            or type(elements) is not list
            or type(phases) is not list
            or type(conditions) is not dict
            or type(axis_vars) is not list
            or type(axis_lims) is not dict
            or type(axis_delta) is not dict
            or type(models) is not dict
            or type(system_info) is not dict
            or type(num_potential) is not int
            or isinstance(num_potential, bool)
            or any(type(value) is not str for value in components)
            or any(type(value) is not str for value in elements)
            or any(type(value) is not str for value in phases)
            or any(type(key) is not str for key in models)
            or tuple(sorted(system_info))
            != ("comps", "dbf", "models", "phase_records", "phases")
            or system_info["dbf"] is not object.__getattribute__(strategy, "dbf")
            or system_info["comps"] is not components
            or system_info["phases"] is not phases
            or system_info["models"] is not models
            or system_info["phase_records"] is not phase_records
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if len(axis_lims) != len(axis_vars) or len(axis_delta) != len(axis_vars):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        axis_limit_rows = []
        axis_delta_rows = []
        for axis in axis_vars:
            limit_matches = tuple(
                value for key, value in axis_lims.items() if key is axis
            )
            delta_matches = tuple(
                value for key, value in axis_delta.items() if key is axis
            )
            if len(limit_matches) != 1 or len(delta_matches) != 1:
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            axis_limit_rows.append((axis, _runtime_sequence(limit_matches[0])))
            axis_delta_rows.append((axis, _runtime_sequence(delta_matches[0])))
        model_rows = []
        for name in sorted(models):
            model = models[name]
            model_namespace = object.__getattribute__(model, "__dict__")
            if type(model_namespace) is not dict or any(
                type(field_name) is not str for field_name in model_namespace
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            field_names = tuple(sorted(model_namespace))
            model_rows.append((
                name,
                model,
                type(model),
                field_names,
                tuple(model_namespace[field_name] for field_name in field_names),
            ))
        phase_namespace = object.__getattribute__(phase_records, "__dict__")
        if type(phase_namespace) is not dict or any(
            type(field_name) is not str for field_name in phase_namespace
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        phase_field_names = tuple(sorted(phase_namespace))
        phase_field_values = tuple(
            phase_namespace[field_name] for field_name in phase_field_names
        )
        if phase_namespace.get("models") is not models:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        all_vars_present = "all_vars" in namespace
        all_vars = namespace.get("all_vars")
        if all_vars_present and type(all_vars) is not list:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        phase_record_rows = _capture_phase_record_rows(
            phase_records, phases
        )
        mutable_graph = _capture_fixed_mutable_graph((
            database, models, phase_records,
        ))
        return (
            components, tuple(components),
            elements, tuple(elements),
            phases, tuple(phases),
            conditions, tuple(conditions.items()),
            axis_vars, tuple(axis_vars),
            axis_lims, tuple(axis_limit_rows),
            axis_delta, tuple(axis_delta_rows),
            models, tuple(model_rows),
            phase_records, type(phase_records),
            phase_field_names, phase_field_values,
            system_info, num_potential,
            all_vars_present, all_vars,
            (() if all_vars is None else tuple(all_vars)),
            mutable_graph,
            phase_record_rows,
        )
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _verify_fixed_strategy_state(
    strategy: object,
    expected: object,
    *,
    allow_runtime_cache_changes: bool = False,
) -> None:
    try:
        if (
            type(expected) is not tuple
            or len(expected) != 27
            or type(allow_runtime_cache_changes) is not bool
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        observed = _capture_fixed_strategy_state(strategy)
        identity_indices = (0, 2, 4, 6, 8, 10, 12, 14, 16, 20, 23)
        if any(observed[index] is not expected[index] for index in identity_indices):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        value_indices = (1, 3, 5, 17, 18, 21, 22)
        if any(observed[index] != expected[index] for index in value_indices):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        observed_conditions = observed[7]
        expected_conditions = expected[7]
        if (
            len(observed_conditions) != len(expected_conditions)
            or any(
                observed_key is not expected_key
                or not _same_condition_value(observed_value, expected_value)
                for (observed_key, observed_value),
                (expected_key, expected_value)
                in zip(observed_conditions, expected_conditions)
            )
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        _verify_fixed_mutable_graph(
            (
                object.__getattribute__(strategy, "dbf"),
                observed[14],
                observed[16],
            ),
            expected[25],
            allow_runtime_cache_changes=allow_runtime_cache_changes,
        )
        _verify_phase_record_rows(observed[26], expected[26])
        observed_axis_vars = observed[9]
        expected_axis_vars = expected[9]
        if len(observed_axis_vars) != len(expected_axis_vars) or any(
            left is not right
            for left, right in zip(observed_axis_vars, expected_axis_vars)
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        for observed_rows, expected_rows in (
            (observed[11], expected[11]),
            (observed[13], expected[13]),
        ):
            if len(observed_rows) != len(expected_rows):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            for observed_row, expected_row in zip(
                observed_rows, expected_rows
            ):
                if (
                    type(observed_row) is not tuple
                    or type(expected_row) is not tuple
                    or len(observed_row) != 2
                    or len(expected_row) != 2
                    or observed_row[0] is not expected_row[0]
                    or not _same_condition_value(
                        observed_row[1], expected_row[1]
                    )
                ):
                    _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        observed_models = observed[15]
        expected_models = expected[15]
        if len(observed_models) != len(expected_models):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        for observed_row, expected_row in zip(observed_models, expected_models):
            if (
                observed_row[0] != expected_row[0]
                or observed_row[1] is not expected_row[1]
                or observed_row[2] is not expected_row[2]
                or observed_row[3] != expected_row[3]
                or len(observed_row[4]) != len(expected_row[4])
                or any(
                    not _same_fixed_graph_value(left, right)
                    for left, right in zip(observed_row[4], expected_row[4])
                )
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if len(observed[19]) != len(expected[19]) or any(
            not _same_fixed_graph_value(left, right)
            for left, right in zip(observed[19], expected[19])
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if (
            type(observed[24]) is not tuple
            or type(expected[24]) is not tuple
            or len(observed[24]) != len(expected[24])
            or any(
                left is not right
                for left, right in zip(observed[24], expected[24])
            )
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _capture_pristine_strategy_state_card(
    strategy: object,
    recorder: object,
) -> tuple[object, ...]:
    """Capture the exact empty mutable graph owned by one factory session."""

    try:
        if type(recorder) is not _TraceRecorder:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        queue = object.__getattribute__(strategy, "node_queue")
        nodes = object.__getattribute__(queue, "nodes")
        zpf_lines = object.__getattribute__(strategy, "zpf_lines")
        exits = object.__getattribute__(strategy, "_exits")
        exit_dirs = object.__getattribute__(strategy, "_exit_dirs")
        recorder_events = object.__getattribute__(recorder, "events")
        recorder_object_ids = object.__getattribute__(recorder, "_object_ids")
        recorder_object_counts = object.__getattribute__(recorder, "_object_counts")
        recorder_reservations = object.__getattribute__(recorder, "_reservations")
        recorder_active_operations = object.__getattribute__(
            recorder, "_active_operations"
        )
        strategy_namespace = object.__getattribute__(strategy, "__dict__")
        queue_namespace = object.__getattribute__(queue, "__dict__")
        if (
            type(nodes) is not list
            or type(zpf_lines) is not list
            or type(exits) is not list
            or type(exit_dirs) is not list
            or type(recorder_events) is not list
            or type(recorder_object_ids) is not dict
            or type(recorder_object_counts) is not dict
            or type(recorder_reservations) is not dict
            or type(recorder_active_operations) is not list
            or type(strategy_namespace) is not dict
            or type(queue_namespace) is not dict
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if len({id(value) for value in (
            nodes, zpf_lines, exits, exit_dirs, recorder_events,
            recorder_active_operations,
        )}) != 6:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if (
            nodes
            or zpf_lines
            or exits
            or exit_dirs
            or len(recorder_events) != 1
            or recorder_object_ids
            or recorder_object_counts
            or recorder_reservations
            or recorder_active_operations
            or type(object.__getattribute__(queue, "_current_node_index")) is not int
            or object.__getattribute__(queue, "_current_node_index") != 0
            or object.__getattribute__(queue, "_tg_recorder") is not recorder
            or object.__getattribute__(queue, "_tg_strategy") is not strategy
            or object.__getattribute__(strategy, "_current_node") is not None
            or type(object.__getattribute__(strategy, "_exit_index")) is not int
            or object.__getattribute__(strategy, "_exit_index") != 0
            or type(object.__getattribute__(strategy, "_tg_scope_depth")) is not int
            or object.__getattribute__(strategy, "_tg_scope_depth") != 0
            or object.__getattribute__(strategy, "_tg_start_transfer_active") is not False
            or object.__getattribute__(strategy, "_tg_last_finished") is not False
            or object.__getattribute__(strategy, "_tg_last_iteration_bound") is not False
            or object.__getattribute__(recorder, "operation_count") != 0
            or object.__getattribute__(recorder, "relation_count") != 0
            or object.__getattribute__(recorder, "_reserved_events") != 0
            or object.__getattribute__(recorder, "halted") is not False
            or object.__getattribute__(recorder, "terminal_reason") != "RUNNING"
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        trace_started = recorder_events[0]
        if (
            type(trace_started) is not InstrumentationEvent
            or trace_started.kind != "TRACE_STARTED"
            or trace_started.ordinal != 0
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        strategy_fields = tuple(sorted(strategy_namespace))
        queue_fields = tuple(sorted(queue_namespace))
        if (
            any(type(name) is not str for name in strategy_fields)
            or any(type(name) is not str for name in queue_fields)
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        configuration = _strategy_configuration_bytes(strategy)
        fixed_state = _capture_fixed_strategy_state(strategy)
        fixed_shape = {
            "model_rows": [
                {
                    "name": row[0],
                    "type": f"{row[2].__module__}.{row[2].__qualname__}",
                    "fields": list(row[3]),
                }
                for row in fixed_state[15]
            ],
            "phase_record_type": (
                f"{fixed_state[17].__module__}."
                f"{fixed_state[17].__qualname__}"
            ),
            "phase_record_fields": list(fixed_state[18]),
            "num_potential_condition": fixed_state[21],
            "has_all_vars": fixed_state[22],
            "mutable_graph_sha256": canonical_trace_digest(
                _fixed_mutable_graph_shape(fixed_state[25])
            ),
            "phase_records": [
                {
                    "phase": row[0],
                    "type": f"{row[2].__module__}.{row[2].__qualname__}",
                    "function_factory_type": (
                        f"{row[5].__module__}.{row[5].__qualname__}"
                    ),
                    "phase_dof": row[9],
                    "num_statevars": row[10],
                    "num_internal_cons": row[11],
                }
                for row in fixed_state[26]
            ],
        }
        payload = {
            "schema": _STRATEGY_STATE_CARD_SCHEMA,
            "strategy_type": (
                f"{type(strategy).__module__}.{type(strategy).__qualname__}"
            ),
            "queue_type": f"{type(queue).__module__}.{type(queue).__qualname__}",
            "strategy_kind": object.__getattribute__(strategy, "_tg_kind"),
            "strategy_fields": list(strategy_fields),
            "queue_fields": list(queue_fields),
            "configuration_sha256": sha256(configuration).hexdigest(),
            "fixed_state_shape_sha256": canonical_trace_digest(fixed_shape),
            "queue_node_count": 0,
            "zpf_line_count": 0,
            "exit_count": 0,
            "scope_depth": 0,
            "status": "PRISTINE_BOUND",
        }
        digest = canonical_trace_digest(payload)
        return (
            strategy,
            recorder,
            queue,
            nodes,
            zpf_lines,
            exits,
            exit_dirs,
            recorder_events,
            trace_started,
            recorder_object_ids,
            recorder_object_counts,
            recorder_reservations,
            recorder_active_operations,
            type(strategy),
            type(queue),
            strategy_fields,
            queue_fields,
            configuration,
            digest,
            fixed_state,
        )
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _verify_pristine_strategy_state_card(
    strategy: object,
    recorder: object,
    card: object,
) -> str:
    """Verify the closure-owned factory card before any mapping action."""

    try:
        if type(card) is not tuple or len(card) != 20:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        (
            expected_strategy, expected_recorder, expected_queue,
            expected_nodes, expected_zpf_lines, expected_exits,
            expected_exit_dirs, expected_recorder_events,
            expected_trace_started, expected_object_ids,
            expected_object_counts, expected_reservations,
            expected_active_operations, expected_strategy_type,
            expected_queue_type, expected_strategy_fields,
            expected_queue_fields, expected_configuration, expected_digest,
            expected_fixed_state,
        ) = card
        if (
            strategy is not expected_strategy
            or recorder is not expected_recorder
            or type(strategy) is not expected_strategy_type
            or type(recorder) is not _TraceRecorder
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        queue = object.__getattribute__(strategy, "node_queue")
        if queue is not expected_queue or type(queue) is not expected_queue_type:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        nodes = object.__getattribute__(queue, "nodes")
        zpf_lines = object.__getattribute__(strategy, "zpf_lines")
        exits = object.__getattribute__(strategy, "_exits")
        exit_dirs = object.__getattribute__(strategy, "_exit_dirs")
        recorder_events = object.__getattribute__(recorder, "events")
        if (
            type(nodes) is not list
            or nodes is not expected_nodes
            or nodes
            or type(zpf_lines) is not list
            or zpf_lines is not expected_zpf_lines
            or zpf_lines
            or type(exits) is not list
            or exits is not expected_exits
            or exits
            or type(exit_dirs) is not list
            or exit_dirs is not expected_exit_dirs
            or exit_dirs
            or type(recorder_events) is not list
            or recorder_events is not expected_recorder_events
            or len(recorder_events) != 1
            or recorder_events[0] is not expected_trace_started
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if len({id(value) for value in (
            nodes, zpf_lines, exits, exit_dirs, recorder_events,
            expected_active_operations,
        )}) != 6:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if (
            object.__getattribute__(queue, "_tg_recorder") is not recorder
            or object.__getattribute__(queue, "_tg_strategy") is not strategy
            or type(object.__getattribute__(queue, "_current_node_index")) is not int
            or object.__getattribute__(queue, "_current_node_index") != 0
            or object.__getattribute__(strategy, "_current_node") is not None
            or type(object.__getattribute__(strategy, "_exit_index")) is not int
            or object.__getattribute__(strategy, "_exit_index") != 0
            or type(object.__getattribute__(strategy, "_tg_scope_depth")) is not int
            or object.__getattribute__(strategy, "_tg_scope_depth") != 0
            or object.__getattribute__(strategy, "_tg_start_transfer_active") is not False
            or object.__getattribute__(strategy, "_tg_last_finished") is not False
            or object.__getattribute__(strategy, "_tg_last_iteration_bound") is not False
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if (
            object.__getattribute__(recorder, "_object_ids")
            is not expected_object_ids
            or expected_object_ids
            or object.__getattribute__(recorder, "_object_counts")
            is not expected_object_counts
            or expected_object_counts
            or object.__getattribute__(recorder, "_reservations")
            is not expected_reservations
            or expected_reservations
            or object.__getattribute__(recorder, "_active_operations")
            is not expected_active_operations
            or expected_active_operations
            or object.__getattribute__(recorder, "operation_count") != 0
            or object.__getattribute__(recorder, "relation_count") != 0
            or object.__getattribute__(recorder, "_reserved_events") != 0
            or object.__getattribute__(recorder, "halted") is not False
            or object.__getattribute__(recorder, "terminal_reason") != "RUNNING"
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        strategy_namespace = object.__getattribute__(strategy, "__dict__")
        queue_namespace = object.__getattribute__(queue, "__dict__")
        if (
            type(strategy_namespace) is not dict
            or type(queue_namespace) is not dict
            or tuple(sorted(strategy_namespace)) != expected_strategy_fields
            or tuple(sorted(queue_namespace)) != expected_queue_fields
            or _strategy_configuration_bytes(strategy) != expected_configuration
            or type(expected_digest) is not str
            or len(expected_digest) != 64
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        _verify_fixed_strategy_state(strategy, expected_fixed_state)
        return expected_digest
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _terminal_numeric_vector(value: object) -> tuple[object, ...]:
    """Serialize a trusted one-dimensional ndarray/Cython view by index."""

    try:
        size = len(value)
        if type(size) is not int or not 0 <= size <= 1_000_000:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        result = []
        for index in range(size):
            item = _solver_number(value[index])
            if type(item) not in (int, float):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            result.append(item)
        return tuple(result)
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _terminal_object_token(
    recorder: object,
    modules: object,
    value: object,
) -> str:
    """Assign one role-independent token from the exact runtime object type."""

    if type(recorder) is not _TraceRecorder or type(modules) is not _RuntimeModules:
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    value_type = type(value)
    if value_type is modules.Node:
        kind = "NODE"
    elif value_type is modules.Point:
        kind = "POINT"
    elif value_type is modules.ZPFLine:
        kind = "LINE"
    elif value_type is modules.CompositionSet:
        kind = "COMPOSITION_SET"
    else:
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    return recorder.object_token(kind, value)


def _terminal_composition_set_state(
    modules: object,
    recorder: object,
    composition_set: object,
    phase_record_rows: object,
) -> dict[str, object]:
    """Return the thermodynamic state retained by one exact CompositionSet."""

    if type(modules) is not _RuntimeModules:
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    try:
        if (
            type(composition_set) is not modules.CompositionSet
            or type(phase_record_rows) is not tuple
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        phase_record = object.__getattribute__(composition_set, "phase_record")
        phase_name = object.__getattribute__(phase_record, "phase_name")
        fixed = object.__getattribute__(composition_set, "fixed")
        num_phase_local_conditions = object.__getattribute__(
            composition_set, "num_phase_local_conditions"
        )
        if (
            type(phase_name) is not str
            or type(fixed) is not bool
            or type(num_phase_local_conditions) is not int
            or num_phase_local_conditions != 0
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        matching_records = tuple(
            row for row in phase_record_rows
            if type(row) is tuple
            and len(row) == 13
            and row[0] == phase_name
        )
        if (
            len(matching_records) != 1
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        observed_phase_record = _capture_phase_record_row(
            matching_records[0][3], phase_name, phase_record
        )
        _verify_phase_record_rows(
            (observed_phase_record,), (matching_records[0],)
        )
        dof = _terminal_numeric_vector(
            object.__getattribute__(composition_set, "dof")
        )
        mole_fractions = _terminal_numeric_vector(
            object.__getattribute__(composition_set, "X")
        )
        expected_dof_count = matching_records[0][9] + matching_records[0][10]
        expected_component_count = len(matching_records[0][6][4][2])
        if (
            len(dof) != expected_dof_count
            or len(mole_fractions) != expected_component_count
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        return {
            "composition_set_id": _terminal_object_token(
                recorder, modules, composition_set
            ),
            "phase": phase_name,
            "phase_record": phase_name,
            "fixed": fixed,
            "num_phase_local_conditions": num_phase_local_conditions,
            "phase_fraction": _solver_number(
                object.__getattribute__(composition_set, "NP")
            ),
            "energy": _solver_number(
                object.__getattribute__(composition_set, "energy")
            ),
            "dof": dof,
            "mole_fractions": mole_fractions,
        }
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _terminal_point_state(
    modules: object,
    recorder: object,
    point: object,
    allowed_condition_keys: object,
    axis_vars: object,
    phase_record_rows: object,
) -> dict[str, object]:
    """Return canonical thermodynamic and node-axis state for one point."""

    if type(modules) is not _RuntimeModules:
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    try:
        point_type = type(point)
        if point_type not in (modules.Point, modules.Node):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if (
            type(allowed_condition_keys) is not tuple
            or type(axis_vars) is not tuple
            or type(phase_record_rows) is not tuple
            or not phase_record_rows
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        conditions = object.__getattribute__(point, "global_conditions")
        chemical_potentials = object.__getattribute__(
            point, "chemical_potentials"
        )
        fixed_sets = object.__getattribute__(
            point, "_fixed_composition_sets"
        )
        free_sets = object.__getattribute__(point, "_free_composition_sets")
        if (
            type(conditions) is not dict
            or type(fixed_sets) is not list
            or type(free_sets) is not list
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if any(
            not any(key is allowed for allowed in allowed_condition_keys)
            for key in conditions
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        component_counts = tuple(
            len(row[6][4][2])
            for row in phase_record_rows
            if type(row) is tuple
            and len(row) == 13
            and type(row[6]) is tuple
            and len(row[6]) == 5
            and type(row[6][4]) is tuple
            and len(row[6][4]) == 3
            and type(row[6][4][2]) is tuple
        )
        if (
            len(component_counts) != len(phase_record_rows)
            or len(set(component_counts)) != 1
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        chemical_potential_vector = _terminal_numeric_vector(
            chemical_potentials
        )
        if len(chemical_potential_vector) != component_counts[0]:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        payload: dict[str, object] = {
            "point_id": _terminal_object_token(recorder, modules, point),
            "kind": "NODE" if point_type is modules.Node else "POINT",
            "conditions": dict(_condition_pairs(conditions)),
            "chemical_potentials": chemical_potential_vector,
            "fixed_composition_sets": [
                _terminal_composition_set_state(
                    modules, recorder, value, phase_record_rows
                )
                for value in fixed_sets
            ],
            "free_composition_sets": [
                _terminal_composition_set_state(
                    modules, recorder, value, phase_record_rows
                )
                for value in free_sets
            ],
        }
        if point_type is modules.Node:
            axis_var = object.__getattribute__(point, "axis_var")
            direction = object.__getattribute__(point, "axis_direction")
            exit_hint = object.__getattribute__(point, "exit_hint")
            if (
                direction is not None
                and type(direction) is not modules.Direction
            ) or type(exit_hint) is not modules.ExitHint or (
                axis_var is not None
                and not any(axis_var is expected for expected in axis_vars)
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            axis_text = None if axis_var is None else str(axis_var)
            if axis_text is not None and type(axis_text) is not str:
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            payload["axis_var"] = axis_text
            payload["axis_direction"] = (
                None if direction is None else str(direction)
            )
            payload["exit_hint"] = str(exit_hint)
        return payload
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _terminal_strategy_state_digest(
    strategy: object,
    recorder: object,
    card: object,
) -> str:
    """Return deterministic terminal graph provenance without memory addresses."""

    try:
        if type(card) is not tuple or len(card) != 20:
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if (
            strategy is not card[0]
            or recorder is not card[1]
            or type(strategy) is not card[13]
            or type(recorder) is not _TraceRecorder
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        _verify_fixed_strategy_state(
            strategy,
            card[19],
            allow_runtime_cache_changes=True,
        )
        fixed_state = card[19]
        axis_vars = fixed_state[9]
        condition_keys = tuple(key for key, _value in fixed_state[7])
        all_vars = fixed_state[24]
        phase_record_rows = fixed_state[26]
        allowed_condition_keys_list = []
        for key in condition_keys + all_vars:
            if not any(key is retained for retained in allowed_condition_keys_list):
                allowed_condition_keys_list.append(key)
        allowed_condition_keys = tuple(allowed_condition_keys_list)
        if (
            type(axis_vars) is not tuple
            or not axis_vars
            or type(phase_record_rows) is not tuple
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        queue = object.__getattribute__(strategy, "node_queue")
        nodes = object.__getattribute__(queue, "nodes")
        zpf_lines = object.__getattribute__(strategy, "zpf_lines")
        exits = object.__getattribute__(strategy, "_exits")
        exit_dirs = object.__getattribute__(strategy, "_exit_dirs")
        modules = object.__getattribute__(strategy, "_tg_modules")
        recorder_events = object.__getattribute__(recorder, "events")
        if (
            queue is not card[2]
            or type(queue) is not card[14]
            or type(modules) is not _RuntimeModules
            or type(nodes) is not list
            or nodes is not card[3]
            or type(zpf_lines) is not list
            or zpf_lines is not card[4]
            or type(exits) is not list
            or type(exit_dirs) is not list
            or len(exits) != len(exit_dirs)
            or type(recorder_events) is not list
            or recorder_events is not card[7]
            or len({id(value) for value in (
                nodes, zpf_lines, exits, exit_dirs, recorder_events,
            )}) != 5
            or object.__getattribute__(queue, "_tg_recorder") is not recorder
            or object.__getattribute__(queue, "_tg_strategy") is not strategy
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        queue_index = object.__getattribute__(queue, "_current_node_index")
        exit_index = object.__getattribute__(strategy, "_exit_index")
        scope_depth = object.__getattribute__(strategy, "_tg_scope_depth")
        transfer_active = object.__getattribute__(
            strategy, "_tg_start_transfer_active"
        )
        finished = object.__getattribute__(strategy, "_tg_last_finished")
        iteration_bound = object.__getattribute__(
            strategy, "_tg_last_iteration_bound"
        )
        if (
            type(queue_index) is not int
            or not 0 <= queue_index <= len(nodes)
            or type(exit_index) is not int
            or not 0 <= exit_index <= len(exits)
            or type(scope_depth) is not int
            or scope_depth != 0
            or transfer_active is not False
            or type(finished) is not bool
            or type(iteration_bound) is not bool
            or (finished and iteration_bound)
            or type(object.__getattribute__(recorder, "_reservations"))
            is not dict
            or object.__getattribute__(recorder, "_reservations")
            or type(object.__getattribute__(recorder, "_active_operations"))
            is not list
            or object.__getattribute__(recorder, "_active_operations")
            or type(object.__getattribute__(recorder, "_reserved_events"))
            is not int
            or object.__getattribute__(recorder, "_reserved_events") != 0
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if any(type(node) is not modules.Node for node in nodes):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        node_rows = []
        for node in nodes:
            parent = object.__getattribute__(node, "parent")
            encountered = object.__getattribute__(node, "encountered_points")
            if (
                parent is not None
                and type(parent) not in (modules.Point, modules.Node)
            ) or type(encountered) is not list or any(
                point is not None
                and type(point) not in (modules.Point, modules.Node)
                for point in encountered
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            node_rows.append({
                "node_id": _terminal_object_token(recorder, modules, node),
                "state": _terminal_point_state(
                    modules, recorder, node, allowed_condition_keys,
                    axis_vars, phase_record_rows,
                ),
                "parent_id": (
                    None if parent is None
                    else _terminal_object_token(recorder, modules, parent)
                ),
                "parent_state": (
                    None if parent is None
                    else _terminal_point_state(
                        modules, recorder, parent,
                        allowed_condition_keys, axis_vars,
                        phase_record_rows,
                    )
                ),
                "encountered_point_ids": [
                    (
                        None if point is None
                        else _terminal_object_token(recorder, modules, point)
                    )
                    for point in encountered
                ],
                "encountered_point_states": [
                    (
                        None if point is None
                        else _terminal_point_state(
                            modules, recorder, point,
                            allowed_condition_keys, axis_vars,
                            phase_record_rows,
                        )
                    )
                    for point in encountered
                ],
            })
        line_rows = []
        for line in zpf_lines:
            if type(line) is not modules.ZPFLine:
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            points = object.__getattribute__(line, "points")
            status = object.__getattribute__(line, "status")
            fixed_phases = object.__getattribute__(line, "fixed_phases")
            free_phases = object.__getattribute__(line, "free_phases")
            axis_var = object.__getattribute__(line, "axis_var")
            direction = object.__getattribute__(line, "axis_direction")
            current_delta = object.__getattribute__(line, "current_delta")
            if (
                type(points) is not list
                or any(
                    type(point) not in (modules.Point, modules.Node)
                    for point in points
                )
                or type(status) is not modules.ZPFState
                or type(fixed_phases) is not list
                or any(type(value) is not str for value in fixed_phases)
                or type(free_phases) is not list
                or any(type(value) is not str for value in free_phases)
                or (
                    axis_var is not None
                    and not any(axis_var is expected for expected in axis_vars)
                )
                or (
                    direction is not None
                    and type(direction) is not modules.Direction
                )
            ):
                _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
            line_rows.append({
                "line_id": _terminal_object_token(recorder, modules, line),
                "status": str(status),
                "fixed_phases": list(fixed_phases),
                "free_phases": list(free_phases),
                "axis_var": None if axis_var is None else str(axis_var),
                "axis_direction": (
                    None if direction is None else str(direction)
                ),
                "current_delta": _solver_number(current_delta),
                "point_ids": [
                    _terminal_object_token(recorder, modules, point)
                    for point in points
                ],
                "point_states": [
                    _terminal_point_state(
                        modules, recorder, point,
                        allowed_condition_keys, axis_vars,
                        phase_record_rows,
                    )
                    for point in points
                ],
            })
        current_node = object.__getattribute__(strategy, "_current_node")
        if (
            current_node is not None
            and (
                type(current_node) is not modules.Node
                or not any(current_node is node for node in nodes)
            )
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        if any(
            type(value) not in (modules.Point, modules.Node) for value in exits
        ) or any(
            value is not None and type(value) is not modules.Direction
            for value in exit_dirs
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        payload = {
            "schema": _STRATEGY_STATE_CARD_SCHEMA,
            "initial_sha256": card[18],
            "strategy_kind": object.__getattribute__(strategy, "_tg_kind"),
            "nodes": node_rows,
            "zpf_lines": line_rows,
            "queue_index": queue_index,
            "current_node_id": (
                None if current_node is None
                else _terminal_object_token(recorder, modules, current_node)
            ),
            "exit_ids": [
                _terminal_object_token(recorder, modules, value)
                for value in exits
            ],
            "exit_states": [
                _terminal_point_state(
                    modules, recorder, value,
                    allowed_condition_keys, axis_vars,
                    phase_record_rows,
                )
                for value in exits
            ],
            "exit_directions": [str(value) for value in exit_dirs],
            "exit_index": exit_index,
            "scope_depth": scope_depth,
            "start_transfer_active": transfer_active,
            "finished": finished,
            "iteration_bound": iteration_bound,
            "status": "TERMINAL_OBSERVED",
        }
        return canonical_trace_digest(payload)
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_DOMAIN_MISMATCH"
        ) from error


def _invalid_strategy_state_digest(
    initial_sha256: object,
    status: object,
    retained_prefix_sha256: object,
) -> str:
    _strict_sha(initial_sha256)
    _strict_sha(retained_prefix_sha256)
    if type(status) is not str or status not in (
        "PRE_RUN_INVALID", "TERMINAL_INVALID"
    ):
        _fail("W2B_INSTRUMENT_TRACE_INVALID")
    return canonical_trace_digest({
        "schema": _STRATEGY_STATE_CARD_SCHEMA,
        "initial_sha256": initial_sha256,
        "retained_prefix_sha256": retained_prefix_sha256,
        "status": status,
    })


def _retained_recorder_prefix_digest(recorder: object) -> str:
    """Commit the exact validated live event prefix before failure recovery."""

    try:
        if type(recorder) is not _TraceRecorder:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        events = object.__getattribute__(recorder, "events")
        operation_count = object.__getattribute__(recorder, "operation_count")
        relation_count = object.__getattribute__(recorder, "relation_count")
        halted = object.__getattribute__(recorder, "halted")
        terminal_reason = object.__getattribute__(recorder, "terminal_reason")
        if (
            type(events) is not list
            or type(operation_count) is not int
            or isinstance(operation_count, bool)
            or type(relation_count) is not int
            or isinstance(relation_count, bool)
            or type(halted) is not bool
            or type(terminal_reason) is not str
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return canonical_trace_digest({
            "schema": _STRATEGY_STATE_CARD_SCHEMA,
            "operation_count": operation_count,
            "relation_count": relation_count,
            "halted": halted,
            "terminal_reason": terminal_reason,
            "events": [event.as_dict() for event in events],
        })
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_TRACE_INVALID"
        ) from error


def _instrumentation_helper_candidates() -> tuple[tuple[str, object], ...]:
    candidates = []
    for name, value in globals().items():
        if name.startswith("__"):
            continue
        if (
            (isinstance(value, type) or isinstance(value, types.FunctionType))
            and getattr(value, "__module__", None) == __name__
        ):
            candidates.append((name, value))
    candidates.sort(key=lambda item: item[0])
    return tuple(candidates)


def _capture_instrumentation_helper_manifest(
) -> tuple[tuple[str, object, str], ...]:
    return tuple(
        (
            name, value,
            _canonical_trace_digest_internal(_runtime_object_record(value)),
        )
        for name, value in _instrumentation_helper_candidates()
    )


def _instrumentation_helper_manifest_digest(
    binding: tuple[tuple[str, object, str], ...],
) -> str:
    return _canonical_trace_digest_internal(
        tuple((name, digest) for name, _value, digest in binding)
    )


def _verify_instrumentation_helper_manifest(
    binding: object,
    *,
    deep: bool,
) -> str:
    if type(binding) is not tuple or not binding:
        _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
    expected_names = tuple(item[0] for item in binding)
    current = _instrumentation_helper_candidates()
    if tuple(name for name, _value in current) != expected_names:
        _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
    current_by_name = dict(current)
    for item in binding:
        if type(item) is not tuple or len(item) != 3:
            _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
        name, expected, digest = item
        observed = current_by_name.get(name)
        if observed is not expected:
            _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
        if deep and canonical_trace_digest(_runtime_object_record(observed)) != digest:
            _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
    return _instrumentation_helper_manifest_digest(binding)


def _instrumentation_helper_refs(
    binding: tuple[tuple[str, object, str], ...],
) -> Mapping[str, object]:
    return MappingProxyType({name: value for name, value, _digest in binding})


def _build_instrumentation_helper_trust_anchor(
    module_namespace: object,
    expected_root_digest: str,
    helper_names: tuple[str, ...] = (
        "ExecutionBinding",
        "InstrumentationBudgetExceeded",
        "InstrumentationEvent",
        "InstrumentationTrace",
        "InstrumentedMappingSession",
        "InstrumentedRunResult",
        "MappingInstrumentationError",
        "TraceMetadata",
        "UpstreamSourceMetadata",
        "_InstrumentedStrategyMixin",
        "_OPERATIONAL_PROVENANCE_AUTHORITY",
        "_RuntimeModules",
        "_SuppressedSolverFailure",
        "_TraceRecorder",
        "_build_instrumentation_helper_trust_anchor",
        "_build_instrumented_mapping_graph",
        "_canonical_trace_bytes_internal",
        "_canonical_trace_digest_internal",
        "_canonical_value",
        "_capture_fixed_mutable_graph",
        "_capture_fixed_strategy_state",
        "_capture_instrumentation_helper_manifest",
        "_capture_phase_record_row",
        "_capture_phase_record_rows",
        "_capture_pristine_strategy_state_card",
        "_capture_runtime_modules_binding",
        "_check_change_in_phases",
        "_check_global_min",
        "_condition_pairs",
        "_copy_and_validate_active_binding",
        "_copy_event",
        "_copy_metadata",
        "_copy_upstream",
        "_create_node_from_different_points",
        "_decode_receipt_value",
        "_detect_degenerate_phase",
        "_directory_pin",
        "_exception_message_digest",
        "_expected_strategy_inputs",
        "_fail",
        "_find_global_min_cs",
        "_find_global_min_point",
        "_fingerprint_constant",
        "_fixed_mutable_graph_shape",
        "_install_integrity_wrappers",
        "_instrumentation_helper_candidates",
        "_instrumentation_helper_manifest_digest",
        "_instrumentation_helper_refs",
        "_instrumented_classes",
        "_invalid_strategy_state_digest",
        "_load_runtime_modules",
        "_make_integrity_gate",
        "_make_runtime_guard",
        "_make_session_identity_registry",
        "_manufactured_upstream",
        "_metadata_with_strategy_state",
        "_normalized_instrumentation_source",
        "_numpy_callable_identity_card",
        "_ordered_tokens",
        "_pairs",
        "_parse_mapping_request",
        "_point_observation",
        "_positive_budget",
        "_primitive_copy",
        "_queue_class",
        "_resolve_runtime_locator",
        "_retained_recorder_prefix_digest",
        "_runtime_callable_record",
        "_runtime_class_record",
        "_runtime_code_record",
        "_runtime_container_value_record",
        "_runtime_critical_manifest",
        "_runtime_module_manifest",
        "_runtime_object_record",
        "_runtime_sequence",
        "_safe_source_sha256",
        "_same_binary64",
        "_same_condition_value",
        "_same_conditions",
        "_same_fixed_graph_value",
        "_solver_call",
        "_solver_number",
        "_strategy_configuration_bytes",
        "_strategy_method_bindings",
        "_strict_mapping_request_mapping",
        "_strict_mapping_request_name",
        "_strict_mapping_request_number",
        "_strict_mapping_request_range",
        "_strict_primitive_equal",
        "_strict_sha",
        "_strict_text",
        "_terminal_composition_set_state",
        "_terminal_numeric_vector",
        "_terminal_object_token",
        "_terminal_point_state",
        "_terminal_strategy_state_digest",
        "_update_equilibrium",
        "_validate_detail_claim_safety",
        "_validate_trace_semantics",
        "_validated_trace_payload",
        "_verify_fixed_mutable_graph",
        "_verify_fixed_strategy_state",
        "_verify_fresh_runtime_modules_against_binding",
        "_verify_instrumentation_helper_manifest",
        "_verify_numpy_callable_authority",
        "_verify_phase_record_rows",
        "_verify_pristine_strategy_state_card",
        "_verify_runtime_modules_binding",
        "_verify_runtime_primitive_manifest",
        "bind_execution_context",
        "canonical_trace_bytes",
        "canonical_trace_digest",
        "create_instrumented_mapping_session",
        "instrumentation_source_sha256",
        "run_manufactured_strategy_hooks",
        "trace_json_bytes",
        "verify_instrumentation_source",
        "verify_pinned_pycalphad",
    ),
    control_names: tuple[str, ...] = (
        "EVENT_KINDS",
        "EVENT_SCHEMA",
        "EXECUTION_MODE",
        "INSTRUMENTATION_SOURCE_PIN_NORMALIZATION",
        "INSTRUMENTATION_VERSION",
        "METADATA_SCHEMA",
        "OUTCOMES",
        "PYCALPHAD_LICENSE_SHA256",
        "PYCALPHAD_VERSION",
        "RUNTIME_PRIMITIVE_MANIFEST_SHA256",
        "SUPPORTED_FE_PROFILE_IDS",
        "SUPPORTED_MAPPING_FEATURES",
        "TRACE_SCHEMA",
        "_CLAIM_DETAIL_KEY_MARKERS",
        "_CONTROL_EVENT_DETAIL_KEYS",
        "_CONTROL_EVENT_KINDS",
        "_EVENT_ID",
        "_MAPPING_REQUEST_SCHEMAS",
        "_MAX_DEPTH",
        "_MAX_TEXT",
        "_NUMPY_BINARY_ORIGIN_CARD",
        "_NUMPY_CALLABLE_PINS",
        "_NUMPY_ORIGIN_CARD",
        "_NUMPY_VERSION",
        "_OPERATION_PAYLOAD_RULES",
        "_PYCALPHAD_PACKAGE_PINS",
        "_REASONS",
        "_RELATION_ID",
        "_RUNTIME_CRITICAL_LOCATORS",
        "_RUNTIME_CRITICAL_PINS",
        "_RUNTIME_MODULE_FIELD_NAMES",
        "_RUNTIME_PRIMITIVE_MODULES",
        "_RUNTIME_TRANSIENT_BINDING_EXCLUSIONS",
        "_SHA256",
        "_STRATEGY_STATE_CARD_SCHEMA",
        "_STRATEGY_STATE_PROVENANCE_STATUSES",
        "_TOKEN",
        "_TRACE_SCOPE_RULES",
        "_UPSTREAM_SOURCE_PINS",
    ),
    dependency_names: tuple[str, ...] = (
        "Mapping",
        "MappingProxyType",
        "Path",
        "Sequence",
        "_CONCRETE_PATH_TYPE",
        "__file__",
        "copy",
        "importlib",
        "inspect",
        "json",
        "math",
        "os",
        "re",
        "sha256",
        "struct",
        "threading",
        "types",
    ),
    dependency_member_names: tuple[str, ...] = (
        "Path:__new__",
        "Path:__truediv__",
        "Path:as_posix",
        "Path:is_absolute",
        "Path:is_file",
        "Path:joinpath",
        "Path:parent",
        "Path:parts",
        "Path:read_bytes",
        "Path:relative_to",
        "Path:resolve",
        "Path:rglob",
        "Path:stat",
        "Path:suffix",
        "_CONCRETE_PATH_TYPE:__new__",
        "_CONCRETE_PATH_TYPE:__truediv__",
        "_CONCRETE_PATH_TYPE:as_posix",
        "_CONCRETE_PATH_TYPE:is_absolute",
        "_CONCRETE_PATH_TYPE:is_file",
        "_CONCRETE_PATH_TYPE:joinpath",
        "_CONCRETE_PATH_TYPE:parent",
        "_CONCRETE_PATH_TYPE:parts",
        "_CONCRETE_PATH_TYPE:read_bytes",
        "_CONCRETE_PATH_TYPE:relative_to",
        "_CONCRETE_PATH_TYPE:resolve",
        "_CONCRETE_PATH_TYPE:rglob",
        "_CONCRETE_PATH_TYPE:stat",
        "_CONCRETE_PATH_TYPE:suffix",
        "copy:deepcopy",
        "importlib:import_module",
        "inspect:getsource",
        "inspect:isdatadescriptor",
        "inspect:ismethoddescriptor",
        "inspect:signature",
        "json:dumps",
        "math:fsum",
        "math:isfinite",
        "os:fspath",
        "re:compile",
        "re:fullmatch",
        "re:sub",
        "struct:error",
        "struct:pack",
        "struct:unpack",
        "threading:RLock",
        "threading:get_ident",
        "types:CodeType",
        "types:FunctionType",
        "types:ModuleType",
    ),
):
    """Build the live helper verifier from one immutable import-time root.

    The returned closure owns the original namespace object, the literal name
    tuples, every original object/code identity, every critical control value,
    every full fingerprint and the expected root digest. Compatibility claim
    globals and compatibility manifest globals are deliberately absent from
    this authority path and are never serialization authority.
    """

    if type(module_namespace) is not dict:
        _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
    if (
        type(expected_root_digest) is not str
        or _SHA256.fullmatch(expected_root_digest) is None
        or type(helper_names) is not tuple
        or not helper_names
        or helper_names != tuple(sorted(set(helper_names)))
        or type(control_names) is not tuple
        or not control_names
        or control_names != tuple(sorted(set(control_names)))
        or type(dependency_names) is not tuple
        or not dependency_names
        or dependency_names != tuple(sorted(set(dependency_names)))
        or type(dependency_member_names) is not tuple
        or not dependency_member_names
        or dependency_member_names != tuple(sorted(set(dependency_member_names)))
        or set(helper_names).intersection(control_names)
        or set(helper_names).intersection(dependency_names)
        or set(control_names).intersection(dependency_names)
    ):
        _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")

    namespace = module_namespace
    names = helper_names
    controls = control_names
    dependencies = dependency_names
    dependency_members = dependency_member_names
    module_name = __name__
    function_type = types.FunctionType
    code_type = types.CodeType
    staticmethod_type = staticmethod
    classmethod_type = classmethod
    property_type = property
    record_object = _runtime_object_record
    digest_object = _canonical_trace_digest_internal
    error_type = MappingInstrumentationError
    value_error_type = ValueError
    mapping_proxy = MappingProxyType
    mapping_proxy_type = type(MappingProxyType({}))
    regex_type = type(re.compile(""))

    def fail_closed() -> None:
        error = value_error_type.__new__(
            error_type, "W2B_INSTRUMENT_SOURCE_MISMATCH"
        )
        error.reason_code = "W2B_INSTRUMENT_SOURCE_MISMATCH"
        value_error_type.__init__(error, "W2B_INSTRUMENT_SOURCE_MISMATCH")
        raise error

    def code_identities(value: object) -> tuple[tuple[str, object], ...]:
        identities: list[tuple[str, object]] = []
        retained_callables: set[int] = set()

        def retain_callable(path: str, target: object) -> None:
            code = getattr(target, "__code__", None)
            if not isinstance(code, code_type):
                fail_closed()
            identities.append((f"{path}.code", code))
            target_id = id(target)
            if target_id in retained_callables:
                return
            retained_callables.add(target_id)
            closure = getattr(target, "__closure__", None)
            if closure is None:
                return
            freevars = tuple(code.co_freevars)
            if len(freevars) != len(closure):
                fail_closed()
            for freevar, cell in zip(freevars, closure):
                try:
                    retained = cell.cell_contents
                except ValueError:
                    fail_closed()
                cell_path = f"{path}.closure.{freevar}"
                identities.append((cell_path, retained))
                retained_code = getattr(retained, "__code__", None)
                if isinstance(retained_code, code_type):
                    retain_callable(cell_path, retained)

        if isinstance(value, function_type):
            retain_callable("__call__", value)
        elif isinstance(value, type):
            for member_name, member in sorted(vars(value).items()):
                targets: tuple[tuple[str, object], ...]
                if isinstance(member, (staticmethod_type, classmethod_type)):
                    targets = ((f"{member_name}.__func__", member.__func__),)
                elif isinstance(member, property_type):
                    targets = tuple(
                        (f"{member_name}.{suffix}", target)
                        for suffix, target in (
                            ("fget", member.fget),
                            ("fset", member.fset),
                            ("fdel", member.fdel),
                        )
                        if target is not None
                    )
                else:
                    targets = ((member_name, member),)
                for path, target in targets:
                    code = getattr(target, "__code__", None)
                    if isinstance(code, code_type):
                        retain_callable(path, target)
        return tuple(identities)

    def same_identities(
        observed: tuple[tuple[str, object], ...],
        expected: tuple[tuple[str, object], ...],
    ) -> bool:
        return (
            len(observed) == len(expected)
            and all(
                observed_path == expected_path and observed_value is expected_value
                for (observed_path, observed_value), (expected_path, expected_value)
                in zip(observed, expected)
            )
        )

    def control_record(value: object, depth: int = 0) -> object:
        if depth > 64:
            fail_closed()
        if value is None or type(value) in (bool, int, str):
            return {"kind": type(value).__name__, "value": value}
        if type(value) is float:
            return {"kind": "float", "value": value.hex()}
        if type(value) in (tuple, list):
            return {
                "kind": type(value).__name__,
                "items": [control_record(item, depth + 1) for item in value],
            }
        if type(value) in (dict, mapping_proxy_type):
            if any(type(key) is not str for key in value):
                fail_closed()
            return {
                "kind": "mapping",
                "items": [
                    [key, control_record(value[key], depth + 1)]
                    for key in sorted(value)
                ],
            }
        if isinstance(value, regex_type):
            return {
                "kind": "regex",
                "pattern": value.pattern,
                "flags": int(value.flags),
            }
        fail_closed()
        raise AssertionError("unreachable")

    original_records: list[tuple[str, object, tuple[tuple[str, object], ...], str]] = []
    for name in names:
        observed = namespace.get(name)
        if (
            not (isinstance(observed, type) or isinstance(observed, function_type))
            or getattr(observed, "__module__", None) != module_name
        ):
            fail_closed()
        original_records.append((
            name,
            observed,
            code_identities(observed),
            digest_object(record_object(observed)),
        ))
    frozen_records = tuple(original_records)
    original_controls: list[tuple[str, object, str]] = []
    for name in controls:
        if name not in namespace:
            fail_closed()
        observed = namespace[name]
        original_controls.append((
            name,
            observed,
            digest_object(control_record(observed)),
        ))
    frozen_controls = tuple(original_controls)
    original_dependencies: list[tuple[str, object, str]] = []
    for name in dependencies:
        if name not in namespace:
            fail_closed()
        observed = namespace[name]
        original_dependencies.append((
            name,
            observed,
            digest_object(record_object(observed)),
        ))
    frozen_dependencies = tuple(original_dependencies)
    original_dependency_members: list[tuple[str, object, str]] = []
    for locator in dependency_members:
        container_name, separator, member_name = locator.partition(":")
        if (
            separator != ":"
            or container_name not in namespace
            or not member_name
        ):
            fail_closed()
        try:
            observed = getattr(namespace[container_name], member_name)
        except AttributeError:
            fail_closed()
        original_dependency_members.append((
            locator,
            observed,
            digest_object(record_object(observed)),
        ))
    frozen_dependency_members = tuple(original_dependency_members)
    observed_root = digest_object(tuple(
        [(f"helper:{name}", digest)
         for name, _value, _codes, digest in frozen_records]
        + [(f"control:{name}", digest)
           for name, _value, digest in frozen_controls]
        + [(f"dependency:{name}", digest)
           for name, _value, digest in frozen_dependencies]
        + [(f"dependency_member:{name}", digest)
           for name, _value, digest in frozen_dependency_members]
    ))
    if observed_root != expected_root_digest:
        fail_closed()
    refs = mapping_proxy({
        **{name: value for name, value, _codes, _digest in frozen_records},
        **{name: value for name, value, _digest in frozen_controls},
        **{name: value for name, value, _digest in frozen_dependencies},
        **{
            f"dependency_member:{name}": value
            for name, value, _digest in frozen_dependency_members
        },
    })

    def verify(*, deep: bool = False) -> tuple[str, Mapping[str, object]]:
        if type(deep) is not bool:
            fail_closed()
        # Primitive dependencies are authenticated before any fingerprint,
        # canonicalization, source read or import helper can consume them.
        for name, expected, _expected_digest in frozen_dependencies:
            if namespace.get(name) is not expected:
                fail_closed()
        for locator, expected, _expected_digest in frozen_dependency_members:
            container_name, _separator, member_name = locator.partition(":")
            try:
                observed = getattr(namespace[container_name], member_name)
            except (AttributeError, KeyError):
                fail_closed()
            if observed is not expected:
                fail_closed()
        # Direct namespace enumeration is closure-owned.  It never delegates
        # either discovery or validation to a replaceable module helper.
        current_names = tuple(sorted(
            name
            for name, value in namespace.items()
            if name != "_HELPER_TRUST_VERIFY"
            and not name.startswith("__")
            and (isinstance(value, type) or isinstance(value, function_type))
            and getattr(value, "__module__", None) == module_name
        ))
        if current_names != names:
            fail_closed()
        if namespace.get("_HELPER_TRUST_VERIFY") is not verify:
            fail_closed()
        live_root_items: list[tuple[str, str]] = []
        for name, expected, expected_codes, expected_digest in frozen_records:
            observed = namespace.get(name)
            if (
                observed is not expected
                or not same_identities(code_identities(observed), expected_codes)
            ):
                fail_closed()
            observed_digest = (
                digest_object(record_object(observed)) if deep else expected_digest
            )
            if observed_digest != expected_digest:
                fail_closed()
            live_root_items.append((f"helper:{name}", observed_digest))
        for name, expected, expected_digest in frozen_controls:
            observed = namespace.get(name)
            if observed is not expected:
                fail_closed()
            observed_digest = (
                digest_object(control_record(observed)) if deep else expected_digest
            )
            if observed_digest != expected_digest:
                fail_closed()
            live_root_items.append((f"control:{name}", observed_digest))
        for name, expected, expected_digest in frozen_dependencies:
            observed = namespace.get(name)
            if observed is not expected:
                fail_closed()
            observed_digest = (
                digest_object(record_object(observed)) if deep else expected_digest
            )
            if observed_digest != expected_digest:
                fail_closed()
            live_root_items.append((f"dependency:{name}", observed_digest))
        for locator, expected, expected_digest in frozen_dependency_members:
            container_name, _separator, member_name = locator.partition(":")
            try:
                observed = getattr(namespace[container_name], member_name)
            except (AttributeError, KeyError):
                fail_closed()
            if observed is not expected:
                fail_closed()
            observed_digest = (
                digest_object(record_object(observed)) if deep else expected_digest
            )
            if observed_digest != expected_digest:
                fail_closed()
            live_root_items.append((f"dependency_member:{locator}", observed_digest))
        if digest_object(tuple(live_root_items)) != expected_root_digest:
            fail_closed()
        return expected_root_digest, refs

    # Keep the closure out of module-helper discovery while pinning its code as
    # a nested code constant of this factory.  The verifier also checks its
    # exact module-global binding on every invocation.
    verify.__module__ = f"{module_name}.__integrity_anchor__"
    return verify


def _make_runtime_guard(
    modules: _RuntimeModules | None,
    module_binding: tuple[tuple[str, object, str], ...] | None,
    helper_verifier: object,
):
    # Capture verifier identities in the closure. Later rebinding a module
    # helper or a compatibility bootstrap cannot redirect this guard.
    verify_modules = _verify_runtime_modules_binding
    if not callable(helper_verifier):
        _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
    verify_helpers = helper_verifier
    _helper_root, expected_helper_refs = verify_helpers(deep=True)

    def guard(*, deep: bool = False) -> Mapping[str, object]:
        _root, helper_refs = verify_helpers(deep=deep)
        if helper_refs is not expected_helper_refs:
            _fail("W2B_INSTRUMENT_SOURCE_MISMATCH")
        if modules is not None:
            if module_binding is None:
                _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
            verify_modules(modules, module_binding, deep=deep)
        return expected_helper_refs

    def require_guard_identity(*observed: object):
        if not observed:
            return guard, expected_helper_refs
        if (
            len(observed) != 5
            or any(value is not guard for value in observed[:3])
            or any(value is not expected_helper_refs for value in observed[3:])
        ):
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        return guard, expected_helper_refs

    guard(deep=True)
    return guard, require_guard_identity


@dataclass(frozen=True, slots=True)
class InstrumentedRunResult:
    trace: InstrumentationTrace
    strategy: object = field(repr=False, compare=False)
    exception_type: str | None = None
    exception_message_sha256: str | None = None

    def __post_init__(self) -> None:
        if _OPERATIONAL_PROVENANCE_AUTHORITY(
            "result_registered", self
        ) is True:
            return
        _HELPER_TRUST_VERIFY(deep=False)
        try:
            trace = object.__getattribute__(self, "trace")
            (
                metadata, _operation_count, events, _halted,
                _terminal_reason, _payload, _original_digest,
            ) = _validated_trace_payload(trace, require_halted=True)
            strategy = object.__getattribute__(self, "strategy")
            exception_type = object.__getattribute__(self, "exception_type")
            exception_digest = object.__getattribute__(
                self, "exception_message_sha256"
            )
            if (exception_type is None) != (exception_digest is None):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            if exception_type is not None:
                _strict_text(exception_type)
                _strict_sha(exception_digest)
            failed = events[-1].outcome == "FAILED"
            if failed != (exception_type is not None):
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            if failed:
                terminal_error = events[-1]
                if terminal_error.kind == "TERMINATION":
                    terminal_error = events[-2]
                if (
                    terminal_error.kind != "ERROR"
                    or terminal_error.exception_type != exception_type
                    or terminal_error.exception_message_sha256 != exception_digest
                ):
                    _fail("W2B_INSTRUMENT_TRACE_INVALID")
            if _OPERATIONAL_PROVENANCE_AUTHORITY(
                "metadata_registered", metadata
            ) is True:
                _OPERATIONAL_PROVENANCE_AUTHORITY(
                    "result_constructed", self
                )
        except Exception as error:
            if (
                isinstance(error, MappingInstrumentationError)
                and error.reason_code in (
                    "W2B_INSTRUMENT_TRACE_INVALID",
                    "W2B_INSTRUMENT_SOURCE_MISMATCH",
                    "W2B_INSTRUMENT_UPSTREAM_MISMATCH",
                )
            ):
                raise
            raise MappingInstrumentationError("W2B_INSTRUMENT_TRACE_INVALID") from error

    def __reduce__(self):
        registered = _OPERATIONAL_PROVENANCE_AUTHORITY(
            "result_registered", self
        )
        trace = object.__getattribute__(self, "trace")
        metadata = object.__getattribute__(trace, "metadata")
        if (
            registered is True
            or object.__getattribute__(metadata, "execution_context")
            == EXECUTION_MODE
        ):
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        _validated_trace_payload(trace, require_halted=True)
        return (
            InstrumentedRunResult,
            (
                trace,
                object.__getattribute__(self, "strategy"),
                object.__getattribute__(self, "exception_type"),
                object.__getattribute__(self, "exception_message_sha256"),
            ),
        )

    def __reduce_ex__(self, protocol: object):
        if type(protocol) is not int or protocol < 0:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return InstrumentedRunResult.__reduce__(self)

    def __copy__(self):
        constructor, arguments = InstrumentedRunResult.__reduce__(self)
        return constructor(*arguments)

    def __deepcopy__(self, memo: object):
        if type(memo) is not dict:
            _fail("W2B_INSTRUMENT_TRACE_INVALID")
        return InstrumentedRunResult.__copy__(self)


class InstrumentedMappingSession:
    __slots__ = (
        "__weakref__",
        "strategy",
        "_recorder",
        "_binding",
        "_max_iterations",
        "_strategy_type",
        "_database",
        "_node_queue",
        "_modules",
        "_kind",
        "_method_bindings",
        "_configuration_bytes",
        "_module_binding",
        "_helper_refs",
        "_runtime_guard",
        "_guard_identity",
    )

    def __new__(cls, *args, **kwargs):
        # Sessions are minted only by the private factory after it has bound
        # closure-owned ownership/state anchors.  This public-looking class is
        # retained as a compatibility type only; calling it is never authority.
        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")

    def __init__(self, *args, **kwargs):
        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")

    @staticmethod
    def _record(session: object) -> tuple[object, ...]:
        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")

    def _validate_active_runtime(
        self, *, identity_only: bool = False
    ) -> ExecutionBinding | None:
        # Authenticate all three exposed guard references against an
        # independently closure-captured expected guard before invoking any
        # of them. A forged replacement therefore has call count zero.  The
        # pre-run state check deliberately stops at this safe boundary so a
        # pristine-state mutation is classified before full domain validation.
        record = InstrumentedMappingSession._record(self)
        (
            identity_check, _pristine_card, _initial_digest,
            strategy, recorder, expected_queue, expected_binding,
            expected_database, expected_modules, expected_kind,
            expected_strategy_type, expected_module_binding,
            expected_helper_refs, expected_method_bindings,
            expected_configuration, expected_max_iterations,
            expected_metadata, retained_guard, expected_live_binding,
        ) = record
        try:
            expected_guard, retained_helpers = identity_check()
            if (
                expected_guard is not retained_guard
                or retained_helpers is not expected_helper_refs
            ):
                _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
            try:
                live_strategy = object.__getattribute__(self, "strategy")
                live_recorder = object.__getattribute__(self, "_recorder")
                live_identity_check = object.__getattribute__(
                    self, "_guard_identity"
                )
                if live_identity_check is not identity_check:
                    _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
                session_guard = object.__getattribute__(self, "_runtime_guard")
                strategy_guard = object.__getattribute__(
                    strategy, "_tg_runtime_guard"
                )
                recorder_guard = object.__getattribute__(
                    recorder, "_runtime_guard"
                )
                session_helpers = object.__getattribute__(self, "_helper_refs")
                strategy_helpers = object.__getattribute__(strategy, "_tg_helpers")
                if (
                    live_strategy is not strategy
                    or live_recorder is not recorder
                    or object.__getattribute__(self, "_binding")
                    is not expected_live_binding
                    or object.__getattribute__(self, "_database")
                    is not expected_database
                    or object.__getattribute__(self, "_node_queue")
                    is not expected_queue
                    or object.__getattribute__(self, "_modules")
                    is not expected_modules
                    or object.__getattribute__(self, "_kind")
                    is not expected_kind
                    or object.__getattribute__(self, "_strategy_type")
                    is not expected_strategy_type
                    or object.__getattribute__(self, "_module_binding")
                    is not expected_module_binding
                    or object.__getattribute__(self, "_method_bindings")
                    is not expected_method_bindings
                    or object.__getattribute__(self, "_configuration_bytes")
                    is not expected_configuration
                    or object.__getattribute__(self, "_max_iterations")
                    != expected_max_iterations
                ):
                    _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
                identity_check(
                    session_guard, strategy_guard, recorder_guard,
                    session_helpers, strategy_helpers,
                )
            except Exception:
                # Restore the independently captured guard before the run()
                # error-retention path calls recorder.terminate(). No forged
                # guard is ever invoked, even if all three live slots changed.
                object.__setattr__(self, "_runtime_guard", expected_guard)
                object.__setattr__(self, "_guard_identity", identity_check)
                object.__setattr__(strategy, "_tg_runtime_guard", expected_guard)
                object.__setattr__(recorder, "_runtime_guard", expected_guard)
                object.__setattr__(self, "_helper_refs", expected_helper_refs)
                object.__setattr__(strategy, "_tg_helpers", expected_helper_refs)
                raise
        except MappingInstrumentationError:
            raise
        except Exception as error:
            raise MappingInstrumentationError(
                "W2B_INSTRUMENT_UPSTREAM_MISMATCH"
            ) from error
        if not callable(expected_guard):
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        if type(identity_only) is not bool:
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        if identity_only:
            return None
        if expected_guard(deep=True) is not expected_helper_refs:
            _fail("W2B_INSTRUMENT_UPSTREAM_MISMATCH")
        verify_instrumentation_source(
            expected_metadata.instrumentation_source_sha256
        )
        modules = _load_runtime_modules()
        _verify_runtime_modules_binding(
            expected_modules, expected_module_binding, deep=True
        )
        _verify_runtime_modules_binding(
            modules, expected_module_binding, deep=True
        )
        binding = _copy_and_validate_active_binding(expected_binding)
        live_binding = _copy_and_validate_active_binding(expected_live_binding)
        expected_components, expected_conditions, pdensity, max_iterations = (
            _expected_strategy_inputs(binding, modules)
        )
        expected_base = {
            "binary": modules.BinaryStrategy,
            "isopleth": modules.IsoplethStrategy,
            "ternary": modules.TernaryStrategy,
        }[expected_kind]
        current_components = object.__getattribute__(strategy, "components")
        current_phases = object.__getattribute__(strategy, "phases")
        current_metadata = object.__getattribute__(recorder, "metadata")
        if (
            type(strategy) is not expected_strategy_type
            or not issubclass(expected_strategy_type, expected_base)
            or object.__getattribute__(strategy, "dbf") is not expected_database
            or object.__getattribute__(strategy, "node_queue") is not expected_queue
            or object.__getattribute__(strategy, "_tg_recorder") is not recorder
            or object.__getattribute__(strategy, "_tg_modules") is not expected_modules
            or type(object.__getattribute__(strategy, "_tg_kind")) is not str
            or object.__getattribute__(strategy, "_tg_kind") != expected_kind
            or object.__getattribute__(strategy, "_tg_runtime_guard") is not expected_guard
            or object.__getattribute__(strategy, "_tg_helpers") is not expected_helper_refs
            or object.__getattribute__(recorder, "_runtime_guard") is not expected_guard
            or type(current_components) is not list
            or tuple(current_components) != expected_components
            or type(current_phases) is not list
            or tuple(current_phases) != binding.effective_phases
            or not _same_conditions(
                object.__getattribute__(strategy, "conditions"),
                expected_conditions,
            )
            or object.__getattribute__(strategy, "GLOBAL_MIN_PDENS") != pdensity
            or max_iterations != expected_max_iterations
            or _strategy_method_bindings(strategy) != expected_method_bindings
            or _strategy_configuration_bytes(strategy) != expected_configuration
            or type(current_metadata) is not TraceMetadata
            or current_metadata is not expected_metadata
            or live_binding.feature_id != binding.feature_id
            or live_binding.family != binding.family
            or live_binding.profile != binding.profile
            or live_binding.profile_role != binding.profile_role
            or live_binding.domain_receipt_digest != binding.domain_receipt_digest
            or live_binding.profile_receipt_digest != binding.profile_receipt_digest
            or live_binding.execution_snapshot_digest
            != binding.execution_snapshot_digest
            or live_binding.runtime_sha256 != binding.runtime_sha256
            or live_binding.effective_phases != binding.effective_phases
            or live_binding.runtime_path.as_posix()
            != binding.runtime_path.as_posix()
            or live_binding._execution_lease is not binding._execution_lease
            or live_binding._pre_snapshot is not binding._pre_snapshot
            or live_binding._domain_receipt is not binding._domain_receipt
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
        return binding

    def _validate_pristine_state(self) -> str:
        record = InstrumentedMappingSession._record(self)
        strategy = record[3]
        recorder = record[4]
        pristine_card = record[1]
        initial_digest = record[2]
        try:
            observed = _verify_pristine_strategy_state_card(
                strategy, recorder, pristine_card
            )
            if observed != initial_digest:
                _fail("W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH")
            return initial_digest
        except BaseException as error:
            if (
                isinstance(error, MappingInstrumentationError)
                and error.reason_code
                == "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH"
            ):
                raise
            raise MappingInstrumentationError(
                "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH"
            ) from error

    def _run_owned(
        self,
        record: object,
        provenance_issue: object,
        execution_gate: object,
    ) -> InstrumentedRunResult:
        if (
            type(self) is not InstrumentedMappingSession
            or type(record) is not tuple
            or not isinstance(provenance_issue, types.FunctionType)
            or not isinstance(execution_gate, types.FunctionType)
        ):
            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
        execution_gate("assert_running", self)
        if InstrumentedMappingSession._record(self) is not record:
            _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
        (
            _identity_check, pristine_card, initial_digest,
            strategy, recorder, _queue, _binding, _database, _modules,
            _kind, _strategy_type, _module_binding, _helper_refs,
            _method_bindings, _configuration, max_iterations,
            pristine_metadata, runtime_guard, _live_binding,
        ) = record

        def issued_result(
            trace: object,
            exception_type: object = None,
            exception_digest: object = None,
        ) -> InstrumentedRunResult:
            value = provenance_issue(
                "result", trace, strategy, exception_type, exception_digest
            )
            if type(value) is not InstrumentedRunResult:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            return value

        def failure_result(
            status: str,
            reason: str,
            error: BaseException,
            *,
            retain_live: bool = False,
            retained_prefix_sha256: str | None = None,
        ) -> InstrumentedRunResult:
            if retained_prefix_sha256 is None:
                retained_prefix_sha256 = canonical_trace_digest({
                    "schema": _STRATEGY_STATE_CARD_SCHEMA,
                    "status": "NO_MAPPING_ACTION",
                })
            terminal_digest = _invalid_strategy_state_digest(
                initial_digest, status, retained_prefix_sha256
            )
            if retain_live:
                try:
                    recorder.bind_strategy_state_provenance(
                        initial_digest, terminal_digest, status
                    )
                    recorder.terminate(
                        reason, outcome="FAILED", exception=error
                    )
                    return issued_result(
                        recorder.snapshot(),
                        (
                            f"{type(error).__module__}."
                            f"{type(error).__qualname__}"
                        ),
                        _exception_message_digest(error),
                    )
                except BaseException:
                    reason = "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH"
                    error = MappingInstrumentationError(reason)
            clean_recorder = provenance_issue(
                "recovery_recorder", recorder, pristine_metadata, runtime_guard
            )
            if type(clean_recorder) is not _TraceRecorder:
                _fail("W2B_INSTRUMENT_TRACE_INVALID")
            clean_recorder.bind_strategy_state_provenance(
                initial_digest, terminal_digest, status
            )
            clean_recorder.terminate(reason, outcome="FAILED", exception=error)
            return issued_result(
                clean_recorder.snapshot(),
                (
                    f"{type(error).__module__}.{type(error).__qualname__}"
                ),
                _exception_message_digest(error),
            )

        try:
            try:
                # This is intentionally not a call to the runtime guard: it
                # authenticates the captured guard/capability graph first,
                # then lets pristine-state provenance take precedence over
                # the full domain comparison below.
                self._validate_active_runtime(identity_only=True)
            except BaseException as error:
                reason = (
                    error.reason_code
                    if isinstance(error, MappingInstrumentationError)
                    else "W2B_INSTRUMENT_STRATEGY_FAILED"
                )
                return failure_result("PRE_RUN_INVALID", reason, error)
            try:
                self._validate_pristine_state()
            except BaseException:
                state_error = MappingInstrumentationError(
                    "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH"
                )
                return failure_result(
                    "PRE_RUN_INVALID",
                    "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH",
                    state_error,
                )
            try:
                self._validate_active_runtime()
            except BaseException as error:
                reason = (
                    error.reason_code
                    if isinstance(error, MappingInstrumentationError)
                    else "W2B_INSTRUMENT_STRATEGY_FAILED"
                )
                return failure_result("PRE_RUN_INVALID", reason, error)

            try:
                strategy.do_map(max_iter=max_iterations)
            except InstrumentationBudgetExceeded:
                try:
                    self._validate_active_runtime()
                    terminal_digest = _terminal_strategy_state_digest(
                        strategy, recorder, pristine_card
                    )
                    recorder.bind_strategy_state_provenance(
                        initial_digest, terminal_digest, "TERMINAL_OBSERVED"
                    )
                except BaseException as error:
                    reason = (
                        error.reason_code
                        if isinstance(error, MappingInstrumentationError)
                        else "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH"
                    )
                    try:
                        retained_prefix = _retained_recorder_prefix_digest(
                            recorder
                        )
                    except BaseException:
                        retained_prefix = canonical_trace_digest({
                            "schema": _STRATEGY_STATE_CARD_SCHEMA,
                            "status": "BUDGET_PREFIX_INVALID",
                        })
                    return failure_result(
                        "TERMINAL_INVALID",
                        reason,
                        error,
                        retained_prefix_sha256=retained_prefix,
                    )
                return issued_result(recorder.snapshot())
            except BaseException as error:
                reason = (
                    error.reason_code
                    if isinstance(error, MappingInstrumentationError)
                    else "W2B_INSTRUMENT_STRATEGY_FAILED"
                )
                try:
                    self._validate_active_runtime()
                    terminal_digest = _terminal_strategy_state_digest(
                        strategy, recorder, pristine_card
                    )
                    recorder.bind_strategy_state_provenance(
                        initial_digest, terminal_digest, "TERMINAL_OBSERVED"
                    )
                except BaseException:
                    try:
                        retained_prefix = _retained_recorder_prefix_digest(
                            recorder
                        )
                    except BaseException:
                        retained_prefix = canonical_trace_digest({
                            "schema": _STRATEGY_STATE_CARD_SCHEMA,
                            "status": "LIVE_PREFIX_INVALID",
                        })
                    return failure_result(
                        "TERMINAL_INVALID",
                        "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH",
                        MappingInstrumentationError(
                            "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH"
                        ),
                        retain_live=True,
                        retained_prefix_sha256=retained_prefix,
                    )
                recorder.terminate(reason, outcome="FAILED", exception=error)
                return issued_result(
                    recorder.snapshot(),
                    (
                        f"{type(error).__module__}.{type(error).__qualname__}"
                    ),
                    _exception_message_digest(error),
                )

            try:
                self._validate_active_runtime()
                terminal_digest = _terminal_strategy_state_digest(
                    strategy, recorder, pristine_card
                )
                recorder.bind_strategy_state_provenance(
                    initial_digest, terminal_digest, "TERMINAL_OBSERVED"
                )
            except BaseException:
                try:
                    retained_prefix = _retained_recorder_prefix_digest(recorder)
                except BaseException:
                    retained_prefix = canonical_trace_digest({
                        "schema": _STRATEGY_STATE_CARD_SCHEMA,
                        "status": "LIVE_PREFIX_INVALID",
                    })
                return failure_result(
                    "TERMINAL_INVALID",
                    "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH",
                    MappingInstrumentationError(
                        "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH"
                    ),
                    retain_live=True,
                    retained_prefix_sha256=retained_prefix,
                )
            finished = object.__getattribute__(strategy, "_tg_last_finished")
            iteration_bound = object.__getattribute__(
                strategy, "_tg_last_iteration_bound"
            )
            if type(finished) is not bool or type(iteration_bound) is not bool:
                return failure_result(
                    "TERMINAL_INVALID",
                    "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH",
                    MappingInstrumentationError(
                        "W2B_INSTRUMENT_STRATEGY_STATE_MISMATCH"
                    ),
                )
            if finished:
                recorder.terminate("QUEUE_EXHAUSTED", outcome="ACCEPTED")
            else:
                recorder.terminate(
                    "ITERATION_BOUND_REACHED", outcome="ABANDONED"
                )
            return issued_result(recorder.snapshot())
        finally:
            execution_gate("assert_running", self)

    def run(self) -> InstrumentedRunResult:
        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")


def _build_instrumented_mapping_graph(
    binding: object,
    components: object,
    conditions: object,
    *,
    operation_budget: object,
    event_budget: object,
    expected_instrumentation_sha256: object,
    strategy_options: Mapping[str, object] | None = None,
    _factory_build_authority: object = None,
    _factory_strategy_gate: object = None,
    _factory_provenance_issue: object = None,
) -> tuple[object, ...]:
    """Build a validated graph for the closure-owned session minter."""

    if (
        not isinstance(_factory_build_authority, types.FunctionType)
        or not isinstance(_factory_strategy_gate, types.FunctionType)
        or not isinstance(_factory_provenance_issue, types.FunctionType)
    ):
        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
    execution_token = _factory_build_authority(
        "authorize_build", _factory_build_authority, _factory_strategy_gate
    )
    provenance_token = _factory_provenance_issue(
        "authorize_build", _factory_build_authority, _factory_strategy_gate
    )
    if execution_token is not provenance_token:
        _fail("W2B_INSTRUMENT_SESSION_REQUIRED")
    helper_verifier = _HELPER_TRUST_VERIFY
    _helper_root, helper_refs = helper_verifier(deep=True)
    authority = helper_refs
    binding = _copy_and_validate_active_binding(binding)
    source_digest = verify_instrumentation_source(expected_instrumentation_sha256)
    operation_limit = _positive_budget(operation_budget)
    event_limit = _positive_budget(event_budget)
    if event_limit < 6:
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
    if type(components) not in (tuple, list) or not components:
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
    component_tuple = _ordered_tokens(components, allow_empty=False)
    if type(conditions) is not dict or not conditions:
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
    if strategy_options is not None and (
        type(strategy_options) is not dict or len(strategy_options) != 0
    ):
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
    upstream = verify_pinned_pycalphad()
    modules = _load_runtime_modules()
    module_binding = _capture_runtime_modules_binding(modules)
    runtime_guard, guard_identity = _make_runtime_guard(
        modules, module_binding, helper_verifier
    )
    metadata = _factory_provenance_issue(
        "metadata",
        binding,
        runtime_guard,
        {
            "feature_id": binding.feature_id,
            "execution_context": authority["EXECUTION_MODE"],
            "family": binding.family,
            "profile": binding.profile,
            "profile_role": binding.profile_role,
            "domain_receipt_digest": binding.domain_receipt_digest,
            "profile_receipt_digest": binding.profile_receipt_digest,
            "execution_snapshot_digest": binding.execution_snapshot_digest,
            "runtime_sha256": binding.runtime_sha256,
            "strategy_state_initial_sha256": "0" * 64,
            "strategy_state_terminal_sha256": "0" * 64,
            "strategy_state_provenance_status": "FACTORY_PENDING",
            "effective_phases": binding.effective_phases,
            "operation_budget": operation_limit,
            "event_budget": event_limit,
            "instrumentation_source_sha256": source_digest,
            "upstream": upstream,
        },
    )
    recorder = _factory_provenance_issue("recorder", metadata)
    recorder.bind_runtime_guard(runtime_guard)
    expected_components, expected_conditions, pdensity, max_iterations = (
        _expected_strategy_inputs(binding, modules)
    )
    if component_tuple != expected_components or not _same_conditions(
        conditions, expected_conditions
    ):
        _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    # Use the exact pinned pycalphad key objects from the receipt-derived
    # expectation. Values are already strict built-in scalars/tuples, so this
    # immutable snapshot needs no key-copying or user-defined coercion.
    strategy_conditions = {
        key: (tuple(value) if type(value) is tuple else value)
        for key, value in expected_conditions.items()
    }
    classes = _instrumented_classes(modules, _factory_strategy_gate)
    kind = {
        "binary_phase_diagram": "binary",
        "multicomponent_isopleth": "isopleth",
        "ternary_phase_diagram": "ternary",
    }[binding.feature_id]
    try:
        if type(binding.runtime_path) is not _CONCRETE_PATH_TYPE:
            _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
        runtime_path_text = os.fspath(binding.runtime_path)
        if type(runtime_path_text) is not str or not binding.runtime_path.is_absolute():
            _fail("W2B_INSTRUMENT_LEASE_REQUIRED")
        _verify_runtime_primitive_manifest()
        database = modules.Database(runtime_path_text)
        _verify_runtime_primitive_manifest()
        strategy = classes[kind](
            database,
            list(component_tuple),
            list(binding.effective_phases),
            strategy_conditions,
            _tg_recorder=recorder,
            _tg_modules=modules,
            _tg_kind=kind,
            _tg_runtime_guard=runtime_guard,
            _tg_helpers=helper_refs,
            GLOBAL_MIN_PDENS=pdensity,
        )
        if (
            strategy.dbf is not database
            or tuple(strategy.components) != expected_components
            or tuple(strategy.phases) != binding.effective_phases
            or not _same_conditions(strategy.conditions, expected_conditions)
            or strategy.GLOBAL_MIN_PDENS != pdensity
        ):
            _fail("W2B_INSTRUMENT_DOMAIN_MISMATCH")
    except BaseException as error:
        recorder.terminate("W2B_INSTRUMENT_STRATEGY_FAILED", outcome="FAILED", exception=error)
        raise MappingInstrumentationError("W2B_INSTRUMENT_STRATEGY_FAILED") from error
    try:
        pristine_card = _capture_pristine_strategy_state_card(
            strategy, recorder
        )
        initial_digest = pristine_card[18]
        recorder.bind_strategy_state_provenance(
            initial_digest, "0" * 64, "PRISTINE_BOUND"
        )
        return (
            strategy,
            recorder,
            binding,
            max_iterations,
            module_binding,
            helper_refs,
            runtime_guard,
            guard_identity,
            pristine_card,
        )
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        raise MappingInstrumentationError(
            "W2B_INSTRUMENT_SESSION_REQUIRED"
        ) from error


(
    _OPERATIONAL_PROVENANCE_AUTHORITY,
    create_instrumented_mapping_session,
) = (
    _make_session_identity_registry(_build_instrumented_mapping_graph)
)


def _manufactured_upstream() -> UpstreamSourceMetadata:
    authority = _HELPER_TRUST_VERIFY(deep=False)[1]
    return UpstreamSourceMetadata(
        package="pycalphad",
        version=authority["PYCALPHAD_VERSION"],
        package_root_sha256=_directory_pin(authority["_PYCALPHAD_PACKAGE_PINS"]),
        license_sha256=authority["PYCALPHAD_LICENSE_SHA256"],
        sources=authority["_PYCALPHAD_PACKAGE_PINS"],
    )


def run_manufactured_strategy_hooks(
    feature_id: object,
    hooks: object,
    *,
    operation_budget: object = 128,
    event_budget: object = 512,
) -> InstrumentationTrace:
    """Run deterministic manufactured hooks through the real trace recorder.

    This test-only driver performs no thermodynamic calculation.  Each hook is
    an exact primitive mapping with ``kind``, ``stage`` and ``outcome`` plus
    optional event fields.  ``raise_message`` injects an exception after the
    event so retention of both the event and the terminal error can be tested.
    """

    helper_verifier = _HELPER_TRUST_VERIFY
    _helper_root, authority = helper_verifier(deep=True)
    if (
        type(feature_id) is not str
        or feature_id not in authority["SUPPORTED_MAPPING_FEATURES"]
        or type(hooks) not in (tuple, list)
    ):
        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
    hooks = tuple(hooks)
    operation_limit = _positive_budget(operation_budget)
    event_limit = _positive_budget(event_budget)
    zero = "0" * 64
    metadata = TraceMetadata(
        feature_id=feature_id,
        execution_context="MANUFACTURED_TEST_ONLY",
        family="manufactured",
        profile="manufactured_hooks",
        profile_role="TEST_ONLY",
        domain_receipt_digest=zero,
        profile_receipt_digest=zero,
        execution_snapshot_digest=zero,
        runtime_sha256=zero,
        strategy_state_initial_sha256=zero,
        strategy_state_terminal_sha256=zero,
        strategy_state_provenance_status="MANUFACTURED_NOT_APPLICABLE",
        effective_phases=("MANUFACTURED_ALPHA", "MANUFACTURED_BETA"),
        operation_budget=operation_limit,
        event_budget=event_limit,
        instrumentation_source_sha256=verify_instrumentation_source(),
        upstream=_manufactured_upstream(),
    )
    recorder = _TraceRecorder(metadata)
    runtime_guard, _guard_identity = _make_runtime_guard(
        None, None, helper_verifier
    )
    recorder.bind_runtime_guard(runtime_guard)
    allowed_hook_keys = (
        "kind", "stage", "outcome", "requested_conditions",
        "resolved_coordinates", "phases", "phase_instances",
        "parent_event_id", "relation_id", "details", "raise_message",
    )

    def checked_hook(value: object) -> dict[str, object]:
        if type(value) is not dict:
            _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        if any(type(key) is not str for key in value):
            _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        keys = tuple(value)
        if (
            any(key not in allowed_hook_keys for key in keys)
            or any(key not in value for key in ("kind", "stage", "outcome"))
        ):
            _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        kind = value["kind"]
        stage = value["stage"]
        outcome = value["outcome"]
        manufactured_payload_kinds = tuple(
            row[0]
            for row in authority["_OPERATION_PAYLOAD_RULES"][
                "manufactured_hook"
            ]
        )
        if (
            type(kind) is not str
            or kind not in (
                "SOLVER_INVOCATION", "SOLVER_RESULT",
                *manufactured_payload_kinds,
            )
        ):
            _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        _strict_text(stage, token=True)
        if type(outcome) is not str or outcome not in authority["OUTCOMES"]:
            _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        for key in ("requested_conditions", "phases", "phase_instances"):
            if key in value and type(value[key]) is not tuple:
                _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        if (
            "resolved_coordinates" in value
            and value["resolved_coordinates"] is not None
            and type(value["resolved_coordinates"]) is not tuple
        ):
            _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
        for key in ("parent_event_id", "relation_id"):
            if key in value and value[key] is not None:
                _strict_text(value[key], token=True)
        if "details" in value:
            details = value["details"]
            if type(details) is not dict or any(
                type(key) is not str for key in details
            ):
                _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
            _canonical_value(details)
        if "raise_message" in value:
            _strict_text(value["raise_message"])
        return value

    try:
        index = 0
        while index < len(hooks):
            raw = checked_hook(hooks[index])
            kind = raw.get("kind")
            stage = raw.get("stage")
            outcome = raw.get("outcome")
            if kind == "SOLVER_INVOCATION":
                if index + 1 >= len(hooks):
                    _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
                result_raw = checked_hook(hooks[index + 1])
                if result_raw.get("kind") != "SOLVER_RESULT":
                    _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
                relation = raw.get("relation_id")
                if relation is None:
                    relation = result_raw.get("relation_id")
                if relation is None:
                    relation = recorder.relation()
                if (
                    raw.get("stage") != result_raw.get("stage")
                    or raw.get("outcome") != "ACCEPTED"
                    or raw.get("relation_id") not in (None, relation)
                    or result_raw.get("relation_id") not in (None, relation)
                ):
                    _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
                operation = recorder.begin_operation(
                    "solver_invocation",
                    stage,
                    relation_id=relation,
                    details={"manufactured": True},
                    event_slots=2,
                )
                invocation_id = recorder.emit(
                    "SOLVER_INVOCATION",
                    stage,
                    operation_ordinal=operation,
                    requested_conditions=raw.get("requested_conditions", ()),
                    resolved_coordinates=raw.get("resolved_coordinates"),
                    phases=raw.get("phases", ()),
                    phase_instances=raw.get("phase_instances", ()),
                    relation_id=relation,
                    outcome="ACCEPTED",
                    details=raw.get("details", {}),
                )
                injected = None
                if "raise_message" in result_raw:
                    if result_raw.get("outcome") != "FAILED":
                        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
                    injected = RuntimeError(result_raw["raise_message"])
                recorder.emit(
                    "SOLVER_RESULT",
                    stage,
                    operation_ordinal=operation,
                    requested_conditions=result_raw.get("requested_conditions", ()),
                    resolved_coordinates=result_raw.get("resolved_coordinates"),
                    phases=result_raw.get("phases", ()),
                    phase_instances=result_raw.get("phase_instances", ()),
                    exception=injected,
                    parent_event_id=invocation_id,
                    relation_id=relation,
                    outcome=result_raw.get("outcome"),
                    details=result_raw.get("details", {}),
                )
                recorder.end_operation(
                    operation,
                    outcome=result_raw.get("outcome"),
                    exception=injected,
                    details={"manufactured": True},
                )
                index += 2
                if injected is not None:
                    raise injected
                continue
            if kind == "SOLVER_RESULT":
                # A lone manufactured result still represents a complete
                # solver lifecycle: synthesize only the invocation envelope.
                relation = raw.get("relation_id")
                if relation is None:
                    relation = recorder.relation()
                operation = recorder.begin_operation(
                    "solver_invocation",
                    stage,
                    relation_id=relation,
                    details={"manufactured": True, "synthetic_invocation": True},
                    event_slots=2,
                )
                invocation_id = recorder.emit(
                    "SOLVER_INVOCATION",
                    stage,
                    operation_ordinal=operation,
                    requested_conditions=raw.get("requested_conditions", ()),
                    relation_id=relation,
                    outcome="ACCEPTED",
                    details={"manufactured": True, "synthetic": True},
                )
                injected = None
                if "raise_message" in raw:
                    if outcome != "FAILED":
                        _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
                    injected = RuntimeError(raw["raise_message"])
                recorder.emit(
                    "SOLVER_RESULT",
                    stage,
                    operation_ordinal=operation,
                    requested_conditions=raw.get("requested_conditions", ()),
                    resolved_coordinates=raw.get("resolved_coordinates"),
                    phases=raw.get("phases", ()),
                    phase_instances=raw.get("phase_instances", ()),
                    exception=injected,
                    parent_event_id=invocation_id,
                    relation_id=relation,
                    outcome=outcome,
                    details=raw.get("details", {}),
                )
                recorder.end_operation(
                    operation,
                    outcome=outcome,
                    exception=injected,
                    details={"manufactured": True},
                )
                index += 1
                if injected is not None:
                    raise injected
                continue
            operation = recorder.begin_operation(
                "manufactured_hook",
                stage,
                relation_id=raw.get("relation_id"),
                details={"manufactured": True},
                event_slots=1,
            )
            injected = None
            if "raise_message" in raw:
                if outcome != "FAILED":
                    _fail("W2B_INSTRUMENT_ARGUMENT_INVALID")
                injected = RuntimeError(raw["raise_message"])
            recorder.emit(
                kind,
                stage,
                operation_ordinal=operation,
                requested_conditions=raw.get("requested_conditions", ()),
                resolved_coordinates=raw.get("resolved_coordinates"),
                phases=raw.get("phases", ()),
                phase_instances=raw.get("phase_instances", ()),
                exception=injected,
                parent_event_id=raw.get("parent_event_id"),
                relation_id=raw.get("relation_id"),
                outcome=outcome,
                details=raw.get("details", {}),
            )
            if injected is not None:
                recorder.end_operation(
                    operation,
                    outcome="FAILED",
                    exception=injected,
                    details={"manufactured": True},
                )
                raise injected
            recorder.end_operation(
                operation,
                outcome=outcome,
                details={"manufactured": True},
            )
            index += 1
        recorder.terminate("MANUFACTURED_HOOKS_ENDED", outcome="ACCEPTED")
    except InstrumentationBudgetExceeded:
        pass
    except MappingInstrumentationError:
        raise
    except BaseException as error:
        recorder.terminate("MANUFACTURED_INJECTED_FAILURE", outcome="FAILED", exception=error)
    return recorder.snapshot()


def _install_integrity_wrappers(module_namespace: object, gate: object) -> None:
    """Bind critical entry points to the closure-owned integrity gate once."""

    if type(module_namespace) is not dict or not callable(gate):
        raise RuntimeError("Instrumentation integrity wrapper install is invalid")

    def protect(function: object):
        if not isinstance(function, types.FunctionType):
            raise RuntimeError("Instrumentation integrity target is invalid")

        def guarded(*args, **kwargs):
            gate(deep=False)
            return function(*args, **kwargs)

        guarded.__name__ = function.__name__
        guarded.__qualname__ = function.__qualname__
        guarded.__module__ = function.__module__
        guarded.__doc__ = function.__doc__
        guarded.__annotations__ = dict(function.__annotations__)
        return guarded

    top_level_names = (
        "_OPERATIONAL_PROVENANCE_AUTHORITY",
        "_manufactured_upstream",
        "_verify_runtime_primitive_manifest",
        "bind_execution_context",
        "canonical_trace_bytes",
        "canonical_trace_digest",
        "create_instrumented_mapping_session",
        "instrumentation_source_sha256",
        "run_manufactured_strategy_hooks",
        "trace_json_bytes",
        "verify_instrumentation_source",
        "verify_pinned_pycalphad",
    )
    method_specs = (
        ("ExecutionBinding", ("__post_init__",)),
        (
            "InstrumentationEvent",
            ("__post_init__", "as_dict"),
        ),
        (
            "InstrumentationTrace",
            (
                "__post_init__", "__copy__", "__deepcopy__", "__reduce__",
                "__reduce_ex__", "_payload", "as_dict", "canonical_bytes",
            ),
        ),
        (
            "InstrumentedMappingSession",
            (
                "__new__", "__init__", "_validate_active_runtime",
                "_validate_pristine_state", "_record", "run",
            ),
        ),
        (
            "InstrumentedRunResult",
            (
                "__post_init__", "__copy__", "__deepcopy__", "__reduce__",
                "__reduce_ex__",
            ),
        ),
        (
            "TraceMetadata",
            (
                "__post_init__", "__copy__", "__deepcopy__", "__reduce__",
                "__reduce_ex__", "as_dict",
            ),
        ),
        (
            "UpstreamSourceMetadata",
            ("__post_init__", "as_dict"),
        ),
        (
            "_InstrumentedStrategyMixin",
            (
                "_tg_do_map_core", "_tg_step_strategy",
                "_tg_verify_runtime", "do_map",
            ),
        ),
        (
            "_TraceRecorder",
            (
                "__init__", "bind_runtime_guard", "begin_operation", "emit",
                "bind_strategy_state_provenance", "end_operation",
                "force_postcondition_failure", "object_token", "relation",
                "snapshot", "terminate",
            ),
        ),
    )
    for name in top_level_names:
        module_namespace[name] = protect(module_namespace[name])
    for class_name, method_names in method_specs:
        target = module_namespace[class_name]
        for method_name in method_names:
            descriptor = vars(target)[method_name]
            if type(descriptor) is staticmethod:
                setattr(
                    target,
                    method_name,
                    staticmethod(protect(descriptor.__func__)),
                )
            else:
                setattr(target, method_name, protect(descriptor))


_install_integrity_wrappers(globals(), _INTEGRITY_GATE)
_INSTRUMENTATION_HELPER_BOOTSTRAP = _capture_instrumentation_helper_manifest()
_HELPER_TRUST_VERIFY = _build_instrumentation_helper_trust_anchor(
    globals(),
    "4d1f5b85683c73f853053ba359ef3b6a0cd4b5c900417f49cd1456cbf2423e6d",
)
_INTEGRITY_GATE(
    deep=True,
    _install=(
        _HELPER_TRUST_VERIFY,
        globals(),
        MappingInstrumentationError,
        INSTRUMENTATION_SOURCE_PIN_SHA256,
    ),
)
INSTRUMENTATION_HELPER_MANIFEST_SHA256 = _HELPER_TRUST_VERIFY(deep=True)[0]


__all__ = (
    "TRACE_SCHEMA",
    "EVENT_SCHEMA",
    "METADATA_SCHEMA",
    "INSTRUMENTATION_VERSION",
    "INSTRUMENTATION_SOURCE_PIN_SHA256",
    "INSTRUMENTATION_SOURCE_PIN_NORMALIZATION",
    "PYCALPHAD_VERSION",
    "PYCALPHAD_LICENSE_SHA256",
    "SUPPORTED_MAPPING_FEATURES",
    "SUPPORTED_FE_PROFILE_IDS",
    "FE_BASELINE_PROFILE",
    "STEEL_REQUIRED_PRODUCT_SCOPE",
    "FE_EXCLUSION_DECISION_MADE",
    "C15_EXCLUSION_DECISION_MADE",
    "COUNTS_TOWARD_FEATURE_COVERAGE",
    "ACCEPTANCE_CLAIM",
    "PRODUCTION_USE",
    "EXECUTION_MODE",
    "OUTCOMES",
    "EVENT_KINDS",
    "UPSTREAM_SOURCE_PINS",
    "PYCALPHAD_PACKAGE_PINS",
    "RUNTIME_PRIMITIVE_MANIFEST_SHA256",
    "INSTRUMENTATION_HELPER_MANIFEST_SHA256",
    "MappingInstrumentationError",
    "InstrumentationBudgetExceeded",
    "UpstreamSourceMetadata",
    "InstrumentationEvent",
    "TraceMetadata",
    "InstrumentationTrace",
    "ExecutionBinding",
    "InstrumentedRunResult",
    "canonical_trace_bytes",
    "canonical_trace_digest",
    "instrumentation_source_sha256",
    "verify_instrumentation_source",
    "verify_pinned_pycalphad",
    "trace_json_bytes",
    "bind_execution_context",
    "create_instrumented_mapping_session",
    "run_manufactured_strategy_hooks",
)
