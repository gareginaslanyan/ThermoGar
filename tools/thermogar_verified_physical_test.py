"""Non-scientific fake-seam tests for the B4B1 physical adapter."""
from __future__ import annotations

import atexit
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from thermogar_paths import ThermoGarPaths


_TEMP_PARENT = Path(os.environ["TEMP"]).resolve(strict=True)
_OWNED_ROOT = Path(
    tempfile.mkdtemp(prefix="thermogar-verified-physical-", dir=_TEMP_PARENT)
).resolve(strict=True)
if _OWNED_ROOT.parent != _TEMP_PARENT:
    raise RuntimeError("Physical test fixture escaped its TEMP parent.")
ThermoGarPaths(_OWNED_ROOT).configure_process_environment()


def _cleanup() -> None:
    if _OWNED_ROOT.exists():
        if _OWNED_ROOT.is_symlink() or _OWNED_ROOT.resolve() != _OWNED_ROOT:
            raise RuntimeError("Refusing to clean a redirected physical fixture.")
        shutil.rmtree(_OWNED_ROOT)


atexit.register(_cleanup)

import pandas as pd
import thermogar_physical as physical
import thermogar_verified_loaders as vl
import thermogar_verified_physical as adapter


FIXED_TIME = "2026-08-29T12:34:56.123456Z"
PHASES = ("BCC_A2", "C15_LAVES", "FCC_A1", "LIQUID")


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


class FakePhysical:
    sha256 = "4cf81c992b57263c50b370ea47eb0d5bb4f622cf23c18479bab54267762f20bd"

    def self_test(self) -> pd.DataFrame:
        return pd.DataFrame([{"Статус": "пройдена", "Проверка": "fake"}])

    def resolve_phase(
        self,
        _database: object,
        phase_name: str,
    ) -> physical.PhaseModelResolution:
        return physical.PhaseModelResolution(
            requested_phase=phase_name,
            physical_phase=phase_name,
            quality="direct",
            note="fake",
        )


class Counters:
    def __init__(self) -> None:
        self.tdb = 0
        self.pdb = 0
        self.backend_calls = 0
        self.calls: list[adapter.PhysicalCall] = []
        self.active = 0
        self.max_active = 0

    def tdb_parser(self, stream: object) -> FakeDatabase:
        self.tdb += 1
        if not stream.read(1):
            raise AssertionError("empty verified TDB")
        return FakeDatabase()

    def pdb_parser(self, data: bytes) -> FakePhysical:
        self.pdb += 1
        if not data:
            raise AssertionError("empty verified PDB")
        return FakePhysical()

    @staticmethod
    def projection(call: adapter.PhysicalCall) -> dict[str, object]:
        return {
            "alloy_density_g_cm3": 7.8,
            "alloy_density_kg_m3": 7800.0 + call.call_index,
            "direct_mole_pct": 100.0,
            "inherited_mole_pct": 0.0,
            "mass_coverage_pct": 100.0,
            "missing_rows": [],
            "mole_coverage_pct": 100.0,
            "phase_rows": [{"Фаза": "FCC_A1"}],
            "physical_database_sha256": FakePhysical.sha256,
            "physical_database_version": "1.03",
            "quality_label": "fake",
            "warnings": [],
        }

    def backend(
        self,
        _database: object,
        _physical: object,
        call: adapter.PhysicalCall,
    ) -> dict[str, object]:
        self.backend_calls += 1
        self.calls.append(call)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            return self.projection(call)
        finally:
            self.active -= 1


def _catalog() -> vl.ArtifactCatalog:
    return vl.ArtifactCatalog.from_policy(
        ROOT,
        vl.canonical_release_manifest(),
        phase_provider=lambda artifact: PHASES
        if artifact.evidence.logical_path.startswith("databases/converted/fe/")
        else tuple(phase for phase in PHASES if phase != "C15_LAVES"),
    )


def _bind(database_key: str = "ni") -> vl.BoundDatabaseContext:
    selector: dict[str, object] = {
        "database_key": database_key,
        "include_physical_pdb": True,
    }
    if database_key == "fe":
        selector["profile_key"] = "thermogar_patch"
    return vl.bind_selected_database(selector, _catalog(), DummyPaths())


def _inputs(feature_id: str, database_key: str = "ni", count: int = 1) -> dict[str, object]:
    if feature_id in ("property_pdb_self_test", "property_coverage_view"):
        return adapter.make_physical_inputs(feature_id)
    balance = {"ni": "NI", "al": "AL", "fe": "FE"}[database_key]
    addition = "CR" if database_key != "al" else "CU"
    temperatures = tuple(900.0 + 100.0 * index for index in range(count))
    return adapter.make_physical_inputs(
        feature_id,
        balance=balance,
        units="wt",
        composition_pct={addition: 5.0},
        pressure_pa=101325.0,
        temperatures_k=temperatures,
    )


def _request(
    context: vl.BoundDatabaseContext,
    feature_id: str,
    *,
    count: int = 1,
    requested: tuple[str, ...] = (),
) -> vl.FeatureRequest | vl.RejectedFeatureReceipt:
    return vl.prepare_feature_request(
        feature_id,
        context,
        _inputs(feature_id, context.database_key, count),
        requested,
        candidate_phases=tuple(phase for phase in PHASES if phase != "C15_LAVES"),
        clock=lambda: FIXED_TIME,
    )


def _execute(
    feature_id: str,
    *,
    database_key: str = "ni",
    count: int = 1,
    counters: Counters | None = None,
) -> tuple[adapter.VerifiedPhysicalResult, Counters, vl.BoundDatabaseContext, vl.FeatureRequest]:
    context = _bind(database_key)
    decision = _request(context, feature_id, count=count)
    if type(decision) is not vl.FeatureRequest:
        raise AssertionError(decision)
    current = Counters() if counters is None else counters
    with mock.patch.object(adapter, "_default_pdb_parser", current.pdb_parser):
        with vl.acquire_execution(
            decision,
            DummyPaths(),
            clock=lambda: FIXED_TIME,
            nonce_factory=lambda: "1234567890abcdef1234567890abcdef",
        ) as lease:
            result = adapter.execute_verified_physical(
                context,
                decision,
                lease,
                tdb_parser=current.tdb_parser,
                backend=current.backend,
                clock=lambda: FIXED_TIME,
                packages=[],
            )
    return result, current, context, decision


def _forged_c15(request: vl.FeatureRequest) -> vl.FeatureRequest:
    value = request.to_dict()
    value["requested_phases"] = ["C15_LAVES"]
    value["requested_phases_digest"] = vl.canonical_digest(["C15_LAVES"])
    value["effective_phases"] = ["C15_LAVES"]
    value["effective_phases_digest"] = vl.canonical_digest(["C15_LAVES"])
    value["request_digest"] = ""
    value["request_digest"] = vl.canonical_digest(
        {key: item for key, item in value.items() if key != "request_digest"}
    )
    return vl.FeatureRequest.from_json_bytes(vl.canonical_json_bytes(value))


class VerifiedPhysicalTests(unittest.TestCase):
    def assert_reason(
        self,
        reason: vl.ReasonCode,
        callable_: object,
        *args: object,
        **kwargs: object,
    ) -> None:
        with self.assertRaises(vl.VerifiedLoaderError) as caught:
            callable_(*args, **kwargs)
        self.assertEqual(caught.exception.reason_code, reason)

    def test_01_bound_fe_pdb_evidence(self) -> None:
        context = _bind("fe")
        self.assertEqual(context.profile_key, "thermogar_patch")
        self.assertEqual(context.tdb.sha256, "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612")
        self.assertEqual(context.physical_pdb.sha256, FakePhysical.sha256)

    def test_02_bound_ni_pdb_evidence(self) -> None:
        context = _bind("ni")
        self.assertEqual(context.database_key, "ni")
        self.assertEqual(context.physical_pdb.sha256, FakePhysical.sha256)

    def test_03_bound_al_pdb_evidence(self) -> None:
        context = _bind("al")
        self.assertEqual(context.database_key, "al")
        self.assertEqual(context.physical_pdb.sha256, FakePhysical.sha256)

    def test_04_verified_pdb_bytes_parser_only(self) -> None:
        data = (ROOT / "databases/physical/original/physical_data_v103.pdb").read_bytes()
        parsed = physical.PhysicalDensityDatabase.from_verified_bytes(data)
        self.assertEqual(parsed.sha256, hashlib.sha256(data).hexdigest())
        self.assertIsNone(parsed.source_path)

    def test_05_invalid_utf8_rejects_before_backend(self) -> None:
        with self.assertRaises(UnicodeDecodeError):
            physical.PhysicalDensityDatabase.from_verified_bytes(b"\xff")

    def test_06_invalid_pdb_rejects_before_backend(self) -> None:
        with self.assertRaises(ValueError):
            physical.PhysicalDensityDatabase.from_verified_bytes(b"$ COMMENT !\n")

    def test_07_pdb_hash_rejects_before_backend(self) -> None:
        evidence = _bind("ni").physical_pdb
        self.assertIsNotNone(evidence)
        with self.assertRaises(vl.VerifiedLoaderError):
            vl.VerifiedBinaryArtifact(replace(evidence, sha256="0" * 64), b"verified")

    def test_08_density_single_fresh_parse_one_backend(self) -> None:
        result, counters, _context, _request_value = _execute("property_density_single")
        self.assertEqual((counters.tdb, counters.pdb, counters.backend_calls), (1, 1, 1))
        self.assertEqual(len(result.points), 1)

    def test_09_density_single_failure_has_no_retry(self) -> None:
        counters = Counters()
        def fail(*_args: object) -> dict[str, object]:
            counters.backend_calls += 1
            raise RuntimeError("once")
        context = _bind("ni")
        decision = _request(context, "property_density_single")
        self.assertIs(type(decision), vl.FeatureRequest)
        with mock.patch.object(adapter, "_default_pdb_parser", counters.pdb_parser):
            with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "1" * 32) as lease:
                self.assert_reason(vl.ReasonCode.BACKEND_FAILED, adapter.execute_verified_physical, context, decision, lease, tdb_parser=counters.tdb_parser, backend=fail, clock=lambda: FIXED_TIME, packages=[])
        self.assertEqual(counters.backend_calls, 1)

    def test_10_density_scan_ascending_serial_receipts(self) -> None:
        result, counters, _context, _request_value = _execute("property_density_temperature", count=3)
        self.assertEqual([call.temperature_k for call in counters.calls], [900.0, 1000.0, 1100.0])
        self.assertEqual(result.feature_receipt.backend_calls, 3)

    def test_11_density_scan_stops_on_first_failure(self) -> None:
        counters = Counters()
        def fail_second(_db: object, _pdb: object, call: adapter.PhysicalCall) -> dict[str, object]:
            counters.backend_calls += 1
            if call.call_index == 2:
                raise RuntimeError("stop")
            return Counters.projection(call)
        context = _bind("ni")
        decision = _request(context, "property_density_temperature", count=3)
        self.assertIs(type(decision), vl.FeatureRequest)
        with mock.patch.object(adapter, "_default_pdb_parser", counters.pdb_parser):
            with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "2" * 32) as lease:
                self.assert_reason(vl.ReasonCode.BACKEND_FAILED, adapter.execute_verified_physical, context, decision, lease, tdb_parser=counters.tdb_parser, backend=fail_second, clock=lambda: FIXED_TIME, packages=[])
        self.assertEqual(counters.backend_calls, 2)

    def test_12_density_scan_rejects_over_100_points(self) -> None:
        with self.assertRaises(vl.VerifiedLoaderError) as caught:
            adapter.make_physical_inputs("property_density_temperature", balance="NI", units="wt", composition_pct={}, pressure_pa=101325.0, temperatures_k=tuple(range(1, 102)))
        self.assertEqual(caught.exception.reason_code, vl.ReasonCode.INPUT_INVALID)

    def test_13_density_receipt_and_envelope_bind_pdb(self) -> None:
        result, _counters, context, request = _execute("property_density_single", database_key="fe")
        self.assertEqual(result.feature_receipt.physical_pdb_evidence, context.physical_pdb)
        self.assertEqual(result.result_envelope.request_digest, request.request_digest)
        self.assertEqual(result.result_envelope.receipt_digest, result.feature_receipt.receipt_digest)

    def test_14_result_state_has_projections_not_authority(self) -> None:
        result, _counters, _context, _request_value = _execute("property_density_single")
        payload = result.result_envelope.to_dict()
        text = vl.canonical_json_bytes(payload).decode("utf-8").casefold()
        for forbidden in ("database_path", "filename", "snapshot_bytes", "materializer"):
            self.assertNotIn(forbidden, text)

    def test_15_pdb_self_test_is_bound_and_backend_free(self) -> None:
        vl.invalidate_binding_generation()
        result, counters, _context, _request_value = _execute("property_pdb_self_test")
        self.assertEqual((counters.tdb, counters.pdb, counters.backend_calls), (0, 1, 0))
        self.assertEqual(result.points[0].projection["rows"][0]["Статус"], "пройдена")

    def test_16_coverage_is_bound_and_backend_free(self) -> None:
        result, counters, _context, _request_value = _execute("property_coverage_view")
        self.assertEqual((counters.tdb, counters.backend_calls), (1, 0))
        self.assertTrue(result.points[0].projection["rows"])

    def test_17_c15_automatic_zero_side_effect(self) -> None:
        context = _bind("fe")
        decision = _request(context, "property_density_single")
        self.assertIs(type(decision), vl.FeatureRequest)
        self.assertNotIn("C15_LAVES", decision.effective_phases)

    def test_18_c15_manual_zero_side_effect(self) -> None:
        context = _bind("fe")
        decision = _request(context, "property_density_single", requested=("C15_LAVES",))
        self.assertIs(type(decision), vl.RejectedFeatureReceipt)
        self.assertEqual(decision.reason_code, vl.ReasonCode.C15_PHASE_REJECTED.value)
        self.assertEqual(decision.backend_calls, 0)

    def test_19_c15_restored_zero_side_effect(self) -> None:
        context = _bind("ni")
        forged = _forged_c15(_request(context, "property_density_single"))
        counters = Counters()
        with vl.acquire_execution(forged, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "3" * 32) as lease:
            self.assert_reason(vl.ReasonCode.C15_PHASE_REJECTED, adapter.execute_verified_physical, context, forged, lease, tdb_parser=counters.tdb_parser, backend=counters.backend, clock=lambda: FIXED_TIME, packages=[])
        self.assertEqual((counters.tdb, counters.pdb, counters.backend_calls), (0, 0, 0))

    def test_20_c15_cache_zero_side_effect(self) -> None:
        context = _bind("ni")
        decision = _request(context, "property_density_single", requested=("C15_LAVES",))
        self.assertIs(type(decision), vl.RejectedFeatureReceipt)
        self.assertEqual(decision.backend_calls, 0)

    def test_21_c15_direct_api_zero_side_effect(self) -> None:
        context = _bind("ni")
        forged = _forged_c15(_request(context, "property_density_single"))
        counters = Counters()
        with vl.acquire_execution(forged, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "4" * 32) as lease:
            self.assert_reason(vl.ReasonCode.C15_PHASE_REJECTED, adapter.execute_verified_physical, context, forged, lease, tdb_parser=counters.tdb_parser, backend=counters.backend, clock=lambda: FIXED_TIME, packages=[])
        self.assertEqual(counters.backend_calls, 0)

    def test_22_upstream_fe_profile_rejected_before_pdb(self) -> None:
        with self.assertRaises(vl.VerifiedLoaderError) as caught:
            vl.bind_selected_database({"database_key": "fe", "profile_key": "upstream", "include_physical_pdb": True}, _catalog(), DummyPaths())
        self.assertEqual(caught.exception.reason_code, vl.ReasonCode.UPSTREAM_PROFILE_REJECTED)

    def test_23_stale_generation_rejects_before_parse(self) -> None:
        context = _bind("ni")
        decision = _request(context, "property_density_single")
        self.assertIs(type(decision), vl.FeatureRequest)
        _bind("al")
        self.assert_reason(vl.ReasonCode.GENERATION_STALE, vl.acquire_execution, decision, DummyPaths())

    def test_24_fifo_lease_prevents_overlap(self) -> None:
        context = _bind("ni")
        first = _request(context, "property_density_single")
        second = _request(context, "property_density_single")
        self.assertIs(type(first), vl.FeatureRequest)
        self.assertIs(type(second), vl.FeatureRequest)
        active = 0
        maximum = 0
        lock = threading.Lock()
        errors: list[BaseException] = []
        def worker(request: vl.FeatureRequest, nonce: str) -> None:
            nonlocal active, maximum
            try:
                with vl.acquire_execution(request, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: nonce) as lease:
                    with lock:
                        active += 1
                        maximum = max(maximum, active)
                    time.sleep(0.03)
                    with lock:
                        active -= 1
                    self.assertEqual(lease.identity.lane_id, "steel-numerical-v1")
            except BaseException as error:
                errors.append(error)
        threads = [threading.Thread(target=worker, args=(first, "a" * 32)), threading.Thread(target=worker, args=(second, "b" * 32))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(maximum, 1)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2, exit=False)
    finally:
        _cleanup()
        atexit.unregister(_cleanup)
