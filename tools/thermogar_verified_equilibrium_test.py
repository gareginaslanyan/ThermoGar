"""Non-scientific fake-seam tests for the Wave-B3 equilibrium adapter."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _pyc_manifest() -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for base in (ROOT / "app", ROOT / "tools"):
        for candidate in base.rglob("*.pyc"):
            data = candidate.read_bytes()
            result[candidate.relative_to(ROOT).as_posix()] = (len(data), hashlib.sha256(data).hexdigest())
    return result


PYC_BEFORE = _pyc_manifest()

import thermogar_verified_equilibrium as adapter
import thermogar_verified_loaders as vl
import thermogar_workspace as workspace


FIXED_TIME = "2026-08-29T12:34:56.123456Z"
FIXED_NONCE = "fedcba9876543210fedcba9876543210"
PHASES = ("BCC_A2", "FCC_A1", "LIQUID")


class DummyPaths:
    __slots__ = ()


class FakeDatabase:
    def __init__(self) -> None:
        self.phases = {phase: object() for phase in PHASES}
        self.refstates = {
            "AL": {"mass": 26.9815385},
            "CR": {"mass": 51.9961},
            "FE": {"mass": 55.845},
            "NI": {"mass": 58.6934},
        }


def _catalog() -> vl.ArtifactCatalog:
    return vl.ArtifactCatalog.from_policy(
        ROOT,
        vl.canonical_release_manifest(),
        phase_provider=lambda _artifact: PHASES,
    )


def _bind(database_key: str = "ni") -> vl.BoundDatabaseContext:
    return vl.bind_selected_database({"database_key": database_key}, _catalog(), DummyPaths())


def _inputs(
    feature_id: str,
    *,
    units: str = "wt",
) -> dict[str, object]:
    if feature_id == "equilibrium_single":
        return adapter.make_equilibrium_inputs(
            feature_id,
            balance="NI",
            units=units,
            composition_pct={"CR": 5.0},
            pressure_pa=101325.0,
            temperatures_k=(973.15,),
        )
    if feature_id == "equilibrium_temperature_scan":
        return adapter.make_equilibrium_inputs(
            feature_id,
            balance="NI",
            units=units,
            composition_pct={"CR": 5.0},
            pressure_pa=101325.0,
            temperatures_k=(900.0, 1000.0, 1100.0),
        )
    return adapter.make_equilibrium_inputs(
        feature_id,
        balance="NI",
        units=units,
        composition_pct={},
        pressure_pa=101325.0,
        temperatures_k=(973.15,),
        variable_element="CR",
        concentrations_pct=(0.0, 5.0, 10.0),
    )


def _request(
    context: vl.BoundDatabaseContext,
    feature_id: str,
    *,
    requested: tuple[str, ...] = (),
) -> vl.FeatureRequest | vl.RejectedFeatureReceipt:
    return vl.prepare_feature_request(
        feature_id,
        context,
        _inputs(feature_id),
        requested,
        candidate_phases=PHASES,
        clock=lambda: FIXED_TIME,
    )


class FakeRun:
    def __init__(self) -> None:
        self.parse_calls = 0
        self.backend_calls = 0
        self.calls: list[adapter.EquilibriumCall] = []
        self.active = 0
        self.max_active = 0

    def parser(self, stream: object) -> FakeDatabase:
        self.parse_calls += 1
        if not getattr(stream, "read")(1):
            raise AssertionError("verified snapshot was empty")
        return FakeDatabase()

    def backend(self, _database: object, call: adapter.EquilibriumCall) -> dict[str, object]:
        self.backend_calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            self.calls.append(call)
            return {
                "display_value": {"call_index": call.call_index},
                "phase_atomic": {
                    "FCC_A1": {"CR": 0.1, "NI": 0.9},
                    "LIQUID": {"CR": 0.2, "NI": 0.8},
                },
                "phase_fractions": {"FCC_A1": 0.25, "LIQUID": 0.75},
                "phase_mass": {
                    "FCC_A1": {"CR": 0.09, "NI": 0.91},
                    "LIQUID": {"CR": 0.18, "NI": 0.82},
                },
            }
        finally:
            self.active -= 1


def _execute(
    feature_id: str,
    *,
    database_key: str = "ni",
    run: FakeRun | None = None,
) -> tuple[adapter.VerifiedEquilibriumResult, FakeRun, vl.BoundDatabaseContext, vl.FeatureRequest]:
    context = _bind(database_key)
    decision = _request(context, feature_id)
    if type(decision) is not vl.FeatureRequest:
        raise AssertionError(decision)
    current = FakeRun() if run is None else run
    with vl.acquire_execution(
        decision,
        DummyPaths(),
        clock=lambda: FIXED_TIME,
        nonce_factory=lambda: FIXED_NONCE,
    ) as lease:
        result = adapter.execute_verified_equilibrium(
            context,
            decision,
            lease,
            parser=current.parser,
            backend=current.backend,
            clock=lambda: FIXED_TIME,
        )
    return result, current, context, decision


def _evidence_for(database_key: str) -> tuple[vl.FeatureReceipt, vl.ResultEnvelope]:
    if database_key == "fe":
        context = vl.bind_selected_database(
            {"database_key": "fe", "profile_key": "thermogar_patch"},
            _catalog(),
            DummyPaths(),
        )
    else:
        context = _bind(database_key)
    decision = vl.prepare_feature_request(
        "equilibrium_single",
        context,
        {"database_key": database_key, "row": 1},
        (),
        candidate_phases=PHASES,
        clock=lambda: FIXED_TIME,
    )
    if type(decision) is not vl.FeatureRequest:
        raise AssertionError(decision)
    settings = {"database_key": database_key, "phase_fractions": [["LIQUID", 1.0]]}
    result_digest = vl.canonical_digest(
        {
            "settings_digest": vl.canonical_digest(settings),
            "tables_digest": vl.canonical_digest([]),
            "figures_digest": vl.canonical_digest([]),
            "artifacts_digest": vl.canonical_digest([]),
        }
    )
    with vl.acquire_execution(
        decision,
        DummyPaths(),
        clock=lambda: FIXED_TIME,
        nonce_factory=lambda: FIXED_NONCE,
    ) as lease:
        receipt = vl.make_feature_receipt(
            context,
            decision,
            lease,
            outcome="success",
            reason_code=None,
            reason_detail=None,
            backend={
                "adapter_id": "fake.verified-batch",
                "adapter_revision": "1",
                "backend_id": "fake-no-science",
                "backend_version": "1",
            },
            packages=[],
            point_count=1,
            result_digest=result_digest,
            started_at_utc=FIXED_TIME,
            finished_at_utc=FIXED_TIME,
        )
        envelope = vl.make_result_envelope(
            context,
            decision,
            receipt,
            settings=settings,
            clock=lambda: FIXED_TIME,
        )
    return receipt, envelope


class FakeProgress:
    def progress(self, *_args: object, **_kwargs: object) -> None:
        return None

    def empty(self) -> None:
        return None


class FakeBatchBroker:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []
        self.active = 0
        self.max_active = 0
        self.finished: tuple[dict[str, object], ...] | None = None

    def execute_row(self, row: dict[str, object]) -> dict[str, object]:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            self.rows.append(dict(row))
            if "C15_LAVES" in row["requested_phases"]:
                context = _bind(str(row["database_key"]))
                rejection = vl.prepare_feature_request(
                    "equilibrium_single",
                    context,
                    _inputs("equilibrium_single"),
                    ("C15_LAVES",),
                    candidate_phases=PHASES,
                    clock=lambda: FIXED_TIME,
                )
                if type(rejection) is not vl.RejectedFeatureReceipt:
                    raise AssertionError(rejection)
                return {
                    "status": "rejected", "rejection": rejection,
                    "feature_receipt": None, "result_envelope": None,
                    "phase_fractions": [], "phase_atomic": [], "phase_mass": [],
                }
            receipt, envelope = _evidence_for(str(row["database_key"]))
            return {
                "status": "success",
                "rejection": None,
                "feature_receipt": receipt,
                "result_envelope": envelope,
                "phase_fractions": [["LIQUID", 1.0]],
                "phase_atomic": [],
                "phase_mass": [],
            }
        finally:
            self.active -= 1

    def finish(self, children: tuple[dict[str, object], ...]) -> dict[str, str]:
        self.finished = children
        return {"receipt_digest": "a" * 64, "envelope_digest": "b" * 64}


class VerifiedEquilibriumTests(unittest.TestCase):
    def assert_reason(self, reason: vl.ReasonCode, operation, *args, **kwargs) -> None:
        with self.assertRaises(vl.VerifiedLoaderError) as caught:
            operation(*args, **kwargs)
        self.assertEqual(caught.exception.reason_code, reason)

    def test_01_single_ni_has_exact_verified_receipt_and_path_free_boundary(self) -> None:
        result, run, context, request = _execute("equilibrium_single")
        self.assertEqual((run.parse_calls, run.backend_calls, run.max_active), (1, 1, 1))
        self.assertEqual(len(result.points), 1)
        self.assertEqual(result.feature_receipt.backend_calls, 1)
        self.assertEqual(result.feature_receipt.point_count, 1)
        self.assertEqual(result.feature_receipt.tdb_evidence, context.tdb)
        self.assertEqual(result.feature_receipt.request_digest, request.request_digest)
        self.assertEqual(result.result_envelope.receipt_digest, result.feature_receipt.receipt_digest)
        boundary = repr((context.to_dict(), request.to_dict(), result.feature_receipt.to_dict(), result.result_envelope.to_dict())).lower()
        for forbidden in ("database_path", "project_root", "stringio", "database("):
            self.assertNotIn(forbidden, boundary)

    def test_02_al_uses_the_same_verified_adapter_contract(self) -> None:
        result, run, context, _request_value = _execute("equilibrium_single", database_key="al")
        self.assertEqual(context.database_key, "al")
        self.assertEqual((run.parse_calls, run.backend_calls), (1, 1))
        self.assertEqual(result.feature_receipt.backend["adapter_id"], adapter.ADAPTER_ID)

    def test_03_temperature_scan_is_three_serial_calls_without_retry(self) -> None:
        result, run, _context, _request_value = _execute("equilibrium_temperature_scan")
        self.assertEqual((run.parse_calls, run.backend_calls, run.max_active), (1, 3, 1))
        self.assertEqual([point.call.axis_value for point in result.points], [900.0, 1000.0, 1100.0])
        self.assertEqual(result.feature_receipt.backend_calls, 3)
        self.assertEqual(result.feature_receipt.point_count, 3)

    def test_04_composition_zero_is_retained_as_native_atomic_fraction(self) -> None:
        result, run, _context, _request_value = _execute("equilibrium_composition_scan")
        self.assertEqual((run.parse_calls, run.backend_calls, run.max_active), (1, 3, 1))
        self.assertEqual([point.call.axis_value for point in result.points], [0.0, 5.0, 10.0])
        first_atomic = dict(result.points[0].call.atomic_fractions)
        self.assertIn("CR", first_atomic)
        self.assertEqual(first_atomic["CR"], 0.0)
        self.assertIn("CR", result.points[0].call.components)

    def test_05_each_execution_uses_a_fresh_verified_parser_object(self) -> None:
        run = FakeRun()
        _execute("equilibrium_single", run=run)
        _execute("equilibrium_single", run=run)
        self.assertEqual(run.parse_calls, 2)
        self.assertEqual(run.backend_calls, 2)

    def test_06_fe_is_rejected_by_generic_adapter_before_parser_or_backend(self) -> None:
        context = vl.bind_selected_database(
            {"database_key": "fe", "profile_key": "thermogar_patch"},
            _catalog(),
            DummyPaths(),
        )
        decision = vl.prepare_feature_request(
            "equilibrium_single",
            context,
            _inputs("equilibrium_single"),
            (),
            candidate_phases=("BCC_A2", "FCC_A1", "LIQUID"),
            clock=lambda: FIXED_TIME,
        )
        self.assertIs(type(decision), vl.FeatureRequest)
        run = FakeRun()
        with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: FIXED_NONCE) as lease:
            self.assert_reason(
                vl.ReasonCode.DATABASE_KEY_REJECTED,
                adapter.execute_verified_equilibrium,
                context,
                decision,
                lease,
                parser=run.parser,
                backend=run.backend,
            )
        self.assertEqual((run.parse_calls, run.backend_calls), (0, 0))

    def test_07_c15_request_is_rejected_before_lease_parser_or_backend(self) -> None:
        context = _bind()
        rejected = _request(context, "equilibrium_single", requested=("C15_LAVES",))
        self.assertIs(type(rejected), vl.RejectedFeatureReceipt)
        self.assertEqual(rejected.reason_code, vl.ReasonCode.C15_PHASE_REJECTED.value)
        self.assertEqual(rejected.backend_calls, 0)

    def test_08_stale_generation_and_dead_lease_fail_closed(self) -> None:
        context = _bind()
        decision = _request(context, "equilibrium_single")
        self.assertIs(type(decision), vl.FeatureRequest)
        run = FakeRun()
        lease = vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: FIXED_NONCE)
        self.assert_reason(
            vl.ReasonCode.LEASE_IDENTITY_MISMATCH,
            adapter.execute_verified_equilibrium,
            context,
            decision,
            lease,
            parser=run.parser,
            backend=run.backend,
        )
        self.assertEqual((run.parse_calls, run.backend_calls), (0, 0))
        _bind("al")
        self.assert_reason(
            vl.ReasonCode.GENERATION_STALE,
            vl.acquire_execution,
            decision,
            DummyPaths(),
        )

    def test_09_backend_exception_is_one_call_and_maps_to_closed_reason(self) -> None:
        context = _bind()
        decision = _request(context, "equilibrium_temperature_scan")
        self.assertIs(type(decision), vl.FeatureRequest)
        run = FakeRun()

        def failing_backend(_database: object, _call: adapter.EquilibriumCall) -> dict[str, object]:
            run.backend_calls += 1
            raise RuntimeError("fake")

        with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: FIXED_NONCE) as lease:
            self.assert_reason(
                vl.ReasonCode.BACKEND_FAILED,
                adapter.execute_verified_equilibrium,
                context,
                decision,
                lease,
                parser=run.parser,
                backend=failing_backend,
                clock=lambda: FIXED_TIME,
            )
        self.assertEqual((run.parse_calls, run.backend_calls, lease.backend_calls), (1, 1, 1))

    def test_10_invalid_result_shape_unknown_phase_and_sum_fail_closed(self) -> None:
        invalid_results = (
            {
                "display_value": {}, "phase_atomic": {},
                "phase_fractions": [], "phase_mass": {},
            },
            {
                "display_value": {}, "phase_atomic": {"UNKNOWN": {"NI": 1.0}},
                "phase_fractions": {"UNKNOWN": 1.0},
                "phase_mass": {"UNKNOWN": {"NI": 1.0}},
            },
            {
                "display_value": {}, "phase_atomic": {"FCC_A1": {"NI": 1.0}},
                "phase_fractions": {"FCC_A1": 0.5},
                "phase_mass": {"FCC_A1": {"NI": 1.0}},
            },
        )
        for raw in invalid_results:
            with self.subTest(raw=raw):
                context = _bind()
                decision = _request(context, "equilibrium_single")
                self.assertIs(type(decision), vl.FeatureRequest)
                with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: FIXED_NONCE) as lease:
                    self.assert_reason(
                        vl.ReasonCode.RESULT_INVALID,
                        adapter.execute_verified_equilibrium,
                        context,
                        decision,
                        lease,
                        parser=lambda _stream: FakeDatabase(),
                        backend=lambda _database, _call, value=raw: value,
                        clock=lambda: FIXED_TIME,
                    )
                self.assertEqual(lease.backend_calls, 1)

    def test_11_live_phase_drift_is_rejected_before_backend(self) -> None:
        context = _bind()
        decision = _request(context, "equilibrium_single")
        self.assertIs(type(decision), vl.FeatureRequest)
        run = FakeRun()
        drift = FakeDatabase()
        drift.phases = {"BCC_A2": object()}
        with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: FIXED_NONCE) as lease:
            self.assert_reason(
                vl.ReasonCode.PHASE_POLICY_MISMATCH,
                adapter.execute_verified_equilibrium,
                context,
                decision,
                lease,
                parser=lambda _stream: drift,
                backend=run.backend,
                clock=lambda: FIXED_TIME,
            )
        self.assertEqual(run.backend_calls, 0)

    def test_12_export_control_is_capability_unavailable_without_dispatch(self) -> None:
        context = _bind()
        receipt = adapter.capability_unavailable_receipt(
            context,
            "data_batch_export",
            detail="Batch export is deferred until Wave B4.",
            clock=lambda: FIXED_TIME,
        )
        self.assertEqual(receipt.outcome, "unavailable")
        self.assertEqual(receipt.reason_code, vl.ReasonCode.CAPABILITY_UNAVAILABLE.value)
        self.assertEqual(receipt.backend_calls, 0)

    def test_13_mixed_batch_is_fifo_ni_al_fe_with_canonical_fe_profile(self) -> None:
        source = workspace.pd.DataFrame(
            [
                {"name": "Ni", "database": "ni", "balance": "NI", "units": "wt", "temperature_C": 700.0, "composition": "CR=5"},
                {"name": "Al", "database": "al", "balance": "AL", "units": "at", "temperature_C": 500.0, "composition": "CR=1"},
                {"name": "Fe", "database": "fe", "balance": "FE", "units": "wt", "temperature_C": 700.0, "composition": "CR=0"},
            ]
        )
        broker = FakeBatchBroker()
        with mock.patch.object(workspace.st, "progress", return_value=FakeProgress()):
            result = workspace.run_batch_calculations(source, broker, {})
        self.assertEqual([row["database_key"] for row in broker.rows], ["ni", "al", "fe"])
        self.assertEqual([row["profile_key"] for row in broker.rows], [None, None, "thermogar_patch"])
        self.assertEqual(broker.rows[2]["composition_pct"]["CR"], 0.0)
        self.assertEqual(broker.max_active, 1)
        self.assertEqual(len(broker.finished), 3)
        self.assertEqual(result["_receipt_digest"], "a" * 64)
        self.assertTrue((result["Сводка"]["Статус"] == "готово").all())

    def test_14_batch_preserves_c15_token_and_rejects_with_zero_backend(self) -> None:
        source = workspace.pd.DataFrame(
            [
                {
                    "name": "Rejected", "database": "ni", "balance": "NI",
                    "units": "wt", "temperature_C": 700.0,
                    "composition": "CR=5", "phases": "LIQUID; C15_LAVES",
                }
            ]
        )
        broker = FakeBatchBroker()
        with mock.patch.object(workspace.st, "progress", return_value=FakeProgress()):
            result = workspace.run_batch_calculations(source, broker, {})
        self.assertEqual(broker.rows[0]["requested_phases"], ["LIQUID", "C15_LAVES"])
        rejection = broker.finished[0]["rejection"]
        self.assertEqual(rejection.reason_code, vl.ReasonCode.C15_PHASE_REJECTED.value)
        self.assertEqual(rejection.backend_calls, 0)
        self.assertEqual(result["Сводка"].iloc[0]["Статус"], "ошибка")

    def test_15_batch_database_keys_are_exact_without_steel_alias(self) -> None:
        self.assertEqual(workspace.normalize_database_key("fe"), "fe")
        for rejected in ("steel", "iron", "сталь", "nickel", "aluminum"):
            with self.subTest(rejected=rejected):
                with self.assertRaises(ValueError):
                    workspace.normalize_database_key(rejected)

    def test_16_live_automatic_candidates_omit_c15_before_backend(self) -> None:
        context = _bind()
        decision = _request(context, "equilibrium_single")
        self.assertIs(type(decision), vl.FeatureRequest)
        database = FakeDatabase()
        database.phases["C15_LAVES"] = object()
        run = FakeRun()
        with vl.acquire_execution(
            decision,
            DummyPaths(),
            clock=lambda: FIXED_TIME,
            nonce_factory=lambda: FIXED_NONCE,
        ) as lease:
            result = adapter.execute_verified_equilibrium(
                context,
                decision,
                lease,
                parser=lambda _stream: database,
                backend=run.backend,
                clock=lambda: FIXED_TIME,
            )
        self.assertNotIn("C15_LAVES", result.points[0].call.phases)
        self.assertEqual(run.backend_calls, 1)

    @classmethod
    def tearDownClass(cls) -> None:
        if _pyc_manifest() != PYC_BEFORE:
            raise AssertionError("B3 fake tests changed the app/tools pyc manifest")


if __name__ == "__main__":
    unittest.main(verbosity=2)
