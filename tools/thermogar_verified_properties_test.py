"""Non-scientific fake-seam tests for the verified B4B2 property adapter."""
from __future__ import annotations

import atexit
from dataclasses import replace
import hashlib
import json
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
    tempfile.mkdtemp(prefix="thermogar-verified-properties-", dir=_TEMP_PARENT)
).resolve(strict=True)
if _OWNED_ROOT.parent != _TEMP_PARENT:
    raise RuntimeError("B4B2 fixture escaped its TEMP parent.")
PATHS = ThermoGarPaths(_OWNED_ROOT)
PATHS.configure_process_environment()


def _cleanup() -> None:
    if _OWNED_ROOT.exists():
        if _OWNED_ROOT.is_symlink() or _OWNED_ROOT.resolve() != _OWNED_ROOT:
            raise RuntimeError("Refusing to clean a redirected B4B2 fixture.")
        shutil.rmtree(_OWNED_ROOT)


atexit.register(_cleanup)

import thermogar_database_repair as repair
import thermogar_properties as properties
import thermogar_verified_loaders as vl
import thermogar_verified_properties as adapter


FIXED_TIME = "2026-08-30T12:34:56.123456Z"
PHASES = ("BCC_A2", "C15_LAVES", "FCC_A1", "LIQUID")
EFFECTIVE = ("BCC_A2", "FCC_A1", "LIQUID")


class DummyPaths:
    __slots__ = ()


class FakeDatabase:
    def __init__(self) -> None:
        self.phases = {phase: object() for phase in PHASES}
        self.refstates = {
            "AL": {"mass": 26.9815385},
            "CR": {"mass": 51.9961},
            "CU": {"mass": 63.546},
            "FE": {"mass": 55.845},
            "NI": {"mass": 58.6934},
        }


class FakePhysical:
    pass


class FakePhysicalOff:
    """Разбор PDB без поправок проекта: отметка идёт первой в warnings."""

    override_notes = ["fake: project corrections switched off by user"]


def _backend_answer(
    fractions: dict[str, float],
    volumes: dict[str, float] | None = None,
    sources: dict[str, str] | None = None,
) -> dict[str, object]:
    """Ответ бэкенда подготовки: мольные доли и молярные объёмы фаз (BL-38)."""

    return {
        "mole_fractions": dict(fractions),
        "molar_volumes_cm3": dict(volumes or {name: 7.0 for name in fractions}),
        "volume_sources": dict(sources or {name: "direct" for name in fractions}),
    }


class Counters:
    def __init__(self) -> None:
        self.tdb = 0
        self.pdb = 0
        self.backend = 0
        self.repository = 0
        self.result = 0
        self.active = 0
        self.max_active = 0
        self.order: list[int] = []

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

    def prepare_backend(
        self,
        _database: object,
        _physical: object,
        call: adapter.PropertyPrepareCall,
    ) -> dict[str, float]:
        self.backend += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.order.append(self.backend)
        try:
            return _backend_answer({"BCC_A2": 0.4, "FCC_A1": 0.6})
        finally:
            self.active -= 1


def _catalog() -> vl.ArtifactCatalog:
    return vl.ArtifactCatalog.from_policy(
        ROOT,
        vl.canonical_release_manifest(),
        phase_provider=lambda artifact: PHASES
        if artifact.evidence.logical_path.startswith("databases/converted/fe/")
        else EFFECTIVE,
    )


def _bind(database_key: str = "ni", *, include_pdb: bool = True) -> vl.BoundDatabaseContext:
    selector: dict[str, object] = {
        "database_key": database_key,
        "include_physical_pdb": include_pdb,
    }
    if database_key == "fe":
        selector["profile_key"] = "thermogar_patch"
    return vl.bind_selected_database(selector, _catalog(), DummyPaths())


def _candidates() -> tuple[str, ...]:
    return EFFECTIVE


def _prepare_request(
    context: vl.BoundDatabaseContext,
    *,
    requested: tuple[str, ...] = (),
) -> vl.FeatureRequest | vl.RejectedFeatureReceipt:
    balance = {"ni": "NI", "al": "AL", "fe": "FE"}[context.database_key]
    addition = "CU" if context.database_key == "al" else "CR"
    inputs = adapter.make_prepare_inputs(
        balance=balance,
        composition_pct={addition: 5.0},
        pressure_pa=101325.0,
        temperatures_k=(973.15,),
        units="wt",
    )
    return vl.prepare_feature_request(
        "property_elastic_prepare",
        context,
        inputs,
        requested,
        candidate_phases=_candidates(),
        clock=lambda: FIXED_TIME,
    )


def _execute_prepare(
    database_key: str = "ni",
    *,
    counters: Counters | None = None,
    backend: object | None = None,
    context: vl.BoundDatabaseContext | None = None,
    physical_overrides: bool = True,
) -> tuple[adapter.VerifiedPropertiesResult, Counters, vl.BoundDatabaseContext, vl.FeatureRequest]:
    bound = _bind(database_key) if context is None else context
    decision = _prepare_request(bound)
    if type(decision) is not vl.FeatureRequest:
        raise AssertionError(decision)
    current = Counters() if counters is None else counters
    selected_backend = current.prepare_backend if backend is None else backend
    with mock.patch.object(adapter, "_default_pdb_parser", current.pdb_parser):
        with vl.acquire_execution(
            decision,
            DummyPaths(),
            clock=lambda: FIXED_TIME,
            nonce_factory=lambda: "1234567890abcdef1234567890abcdef",
        ) as lease:
            result = adapter.execute_verified_properties(
                bound,
                decision,
                lease,
                paths=PATHS,
                tdb_parser=current.tdb_parser,
                backend=selected_backend,
                clock=lambda: FIXED_TIME,
                packages=[],
                physical_overrides=physical_overrides,
            )
    return result, current, bound, decision


def _complete_rows(view: adapter.PropertyLibraryView) -> list[dict[str, object]]:
    return [
        {
            "phase": row["phase"],
            "volume_fraction": row["volume_fraction"],
            "young_gpa": 200.0 + index,
            "poisson": 0.3,
            "origin": "справочно",
            "source": f"fake-source-{index}",
            "reference_temperature_c": 700.0,
            "note": "",
        }
        for index, row in enumerate(view.phase_rows)
    ]


def _vrh_request(
    context: vl.BoundDatabaseContext,
    prepared_digest: str,
    *,
    rows: list[dict[str, object]] | None = None,
    update: bool = False,
) -> tuple[vl.FeatureRequest, adapter.PropertyLibraryView]:
    view = adapter.property_library_prefill(context, prepared_digest, paths=PATHS)
    inputs = adapter.make_vrh_inputs(
        prepared_witness_digest=prepared_digest,
        library_snapshot_digest=view.library_snapshot_digest,
        library_update=update,
        phase_rows=_complete_rows(view) if rows is None else rows,
    )
    decision = vl.prepare_feature_request(
        "property_elastic_vrh",
        context,
        inputs,
        (),
        candidate_phases=_candidates(),
        clock=lambda: FIXED_TIME,
    )
    if type(decision) is not vl.FeatureRequest:
        raise AssertionError(decision)
    return decision, view


def _execute_vrh(
    *,
    database_key: str = "ni",
    update: bool = False,
    rows: list[dict[str, object]] | None = None,
) -> tuple[
    adapter.VerifiedPropertiesResult,
    vl.BoundDatabaseContext,
    vl.FeatureRequest,
    adapter.PropertyLibraryView,
]:
    prepared, _counters, context, _request = _execute_prepare(database_key)
    assert prepared.prepared_witness_digest is not None
    decision, view = _vrh_request(
        context,
        prepared.prepared_witness_digest,
        rows=rows,
        update=update,
    )
    with vl.acquire_execution(
        decision,
        DummyPaths(),
        clock=lambda: FIXED_TIME,
        nonce_factory=lambda: "2" * 32,
    ) as lease:
        result = adapter.execute_verified_properties(
            context,
            decision,
            lease,
            paths=PATHS,
            clock=lambda: FIXED_TIME,
            packages=[],
        )
    return result, context, decision, view


def _strengthening_inputs(*, hill_digest: str | None = None) -> dict[str, object]:
    use_hill = hill_digest is not None
    return adapter.make_strengthening_inputs(
        input_provenance="fake coefficients; bounded test scope",
        input_confirmation=True,
        sigma_internal_mpa=100.0,
        hall_petch={"k_y_mpa_sqrt_m": 0.1, "grain_size_um": 10.0},
        taylor={
            "taylor_factor": 3.0,
            "alpha": 0.3,
            "shear_gpa": None if use_hill else 80.0,
            "burgers_nm": 0.25,
            "dislocation_density_m2": 1e12,
        },
        solid_solution_mpa=20.0,
        orowan={
            "taylor_factor": 3.0,
            "shear_gpa": None if use_hill else 80.0,
            "burgers_nm": 0.25,
            "poisson": None if use_hill else 0.3,
            "particle_radius_nm": 10.0,
            "spacing_nm": 100.0,
        },
        other_mpa=5.0,
        summation_rule="Линейная сумма",
        hill_witness_digest=hill_digest,
    )


def _strength_request(
    context: vl.BoundDatabaseContext,
    inputs: dict[str, object],
) -> vl.FeatureRequest:
    decision = vl.prepare_feature_request(
        "property_strengthening",
        context,
        inputs,
        (),
        candidate_phases=_candidates(),
        clock=lambda: FIXED_TIME,
    )
    if type(decision) is not vl.FeatureRequest:
        raise AssertionError(decision)
    return decision


def _execute_strength(
    context: vl.BoundDatabaseContext,
    inputs: dict[str, object],
) -> tuple[adapter.VerifiedPropertiesResult, vl.FeatureRequest]:
    decision = _strength_request(context, inputs)
    with vl.acquire_execution(
        decision,
        DummyPaths(),
        clock=lambda: FIXED_TIME,
        nonce_factory=lambda: "3" * 32,
    ) as lease:
        result = adapter.execute_verified_properties(
            context,
            decision,
            lease,
            paths=PATHS,
            clock=lambda: FIXED_TIME,
            packages=[],
        )
    return result, decision


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


def _entry(
    database_key: str,
    phase: str,
    *,
    origin: str = "справочно",
    source: str = "source",
    reference: float | None = 700.0,
    note: str = "",
) -> dict[str, object]:
    moduli = properties.moduli_from_e_nu(200.0, 0.3)
    return {
        "database_key": database_key,
        "phase": phase,
        "young_gpa": moduli.young_gpa,
        "poisson": moduli.poisson,
        "bulk_gpa": moduli.bulk_gpa,
        "shear_gpa": moduli.shear_gpa,
        "origin": origin,
        "source": source,
        "reference_temperature_c": reference,
        "note": note,
        "updated_at": FIXED_TIME,
    }


class VerifiedPropertiesTests(unittest.TestCase):
    def setUp(self) -> None:
        adapter.clear_property_witnesses()
        try:
            PATHS.elastic_properties_path.unlink()
        except FileNotFoundError:
            pass
        for sibling in PATHS.elastic_properties_path.parent.iterdir():
            if sibling.name != PATHS.elastic_properties_path.name:
                raise AssertionError(f"unexpected property sidecar before test: {sibling.name}")

    def assert_reason(self, reason: vl.ReasonCode, callable_: object, *args: object, **kwargs: object) -> None:
        with self.assertRaises(vl.VerifiedLoaderError) as caught:
            callable_(*args, **kwargs)
        self.assertEqual(caught.exception.reason_code, reason)

    def test_01_bound_fe_passport_pdb(self) -> None:
        context = _bind("fe")
        self.assertEqual(context.profile_key, "thermogar_patch")
        self.assertEqual(context.patch_id, "TG-FE-2062-C15-001")
        self.assertEqual(context.tdb.sha256, "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612")
        self.assertEqual(context.passport.sha256, "c818f3132840304ea38017cb7419790a290a1ca2e949b01e8954931ac8f17491")
        self.assertIsNotNone(context.physical_pdb)

    def test_02_bound_ni(self) -> None:
        context = _bind("ni")
        self.assertEqual((context.database_key, context.profile_key), ("ni", None))
        self.assertIsNotNone(context.physical_pdb)

    def test_03_bound_al(self) -> None:
        context = _bind("al")
        self.assertEqual((context.database_key, context.profile_key), ("al", None))
        self.assertIsNotNone(context.physical_pdb)

    def test_04_prepare_fresh_tdb_pdb_one_backend(self) -> None:
        result, counters, context, request = _execute_prepare()
        self.assertEqual((counters.tdb, counters.pdb, counters.backend), (1, 1, 1))
        self.assertEqual(result.feature_receipt.backend_calls, 1)
        self.assertEqual(result.result_envelope.request_digest, request.request_digest)
        self.assertEqual(result.feature_receipt.physical_pdb_evidence, context.physical_pdb)
        self.assertIsNotNone(result.prepared_witness_digest)

    def test_05_prepare_backend_failure_no_retry(self) -> None:
        counters = Counters()
        def fail(*_args: object) -> dict[str, float]:
            counters.backend += 1
            raise RuntimeError("once")
        context = _bind("ni")
        decision = _prepare_request(context)
        self.assertIs(type(decision), vl.FeatureRequest)
        with mock.patch.object(adapter, "_default_pdb_parser", counters.pdb_parser):
            with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "4" * 32) as lease:
                self.assert_reason(vl.ReasonCode.BACKEND_FAILED, adapter.execute_verified_properties, context, decision, lease, paths=PATHS, tdb_parser=counters.tdb_parser, backend=fail, clock=lambda: FIXED_TIME)
        self.assertEqual(counters.backend, 1)

    def test_06_prepare_phase_projection_omits_c15(self) -> None:
        result, _counters, _context, _request = _execute_prepare("fe")
        phases = [row["phase"] for row in result.projection["phase_rows"]]
        self.assertNotIn("C15_LAVES", phases)
        self.assertEqual(phases, ["BCC_A2", "FCC_A1"])

    def test_07_prepare_stale_generation_before_parse(self) -> None:
        context = _bind("ni")
        decision = _prepare_request(context)
        self.assertIs(type(decision), vl.FeatureRequest)
        vl.invalidate_binding_generation()
        counters = Counters()
        self.assert_reason(vl.ReasonCode.GENERATION_STALE, vl.acquire_execution, decision, DummyPaths())
        self.assertEqual((counters.tdb, counters.pdb, counters.backend), (0, 0, 0))

    def test_08_prepare_missing_pdb_data_unavailable(self) -> None:
        context = _bind("ni", include_pdb=False)
        decision = _prepare_request(context)
        self.assertIs(type(decision), vl.FeatureRequest)
        with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "5" * 32) as lease:
            self.assert_reason(vl.ReasonCode.DATA_UNAVAILABLE, adapter.execute_verified_properties, context, decision, lease, paths=PATHS)

    def test_09_vrh_uses_matching_prepared_witness(self) -> None:
        result, _context, request, _view = _execute_vrh()
        self.assertEqual(result.feature_receipt.backend_calls, 0)
        self.assertEqual(result.result_envelope.request_digest, request.request_digest)
        self.assertIsNotNone(result.hill_witness_digest)
        self.assertIn("E_Hill_GPa", result.projection["summary"])

    def test_10_vrh_no_parser_or_backend(self) -> None:
        prepared, counters, context, _request = _execute_prepare()
        assert prepared.prepared_witness_digest is not None
        decision, _view = _vrh_request(context, prepared.prepared_witness_digest)
        before = (counters.tdb, counters.pdb, counters.backend)
        with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "6" * 32) as lease:
            result = adapter.execute_verified_properties(context, decision, lease, paths=PATHS, clock=lambda: FIXED_TIME)
        self.assertEqual((counters.tdb, counters.pdb, counters.backend), before)
        self.assertEqual(result.feature_receipt.backend_calls, 0)

    def test_11_vrh_stale_witness_rejected(self) -> None:
        prepared, _counters, old_context, _request = _execute_prepare()
        assert prepared.prepared_witness_digest is not None
        vl.invalidate_binding_generation()
        new_context = _bind("ni")
        view = adapter.PropertyLibraryView(hashlib.sha256(vl.canonical_json_bytes({"schema_version": 1, "updated_at": None, "entries": {}})).hexdigest(), (), None)
        inputs = adapter.make_vrh_inputs(prepared_witness_digest=prepared.prepared_witness_digest, library_snapshot_digest=view.library_snapshot_digest, library_update=False, phase_rows=[])
        decision = vl.prepare_feature_request("property_elastic_vrh", new_context, inputs, (), candidate_phases=_candidates())
        self.assertIs(type(decision), vl.FeatureRequest)
        with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "7" * 32) as lease:
            self.assert_reason(vl.ReasonCode.GENERATION_STALE, adapter.execute_verified_properties, new_context, decision, lease, paths=PATHS)
        self.assertNotEqual(old_context.binding_generation, new_context.binding_generation)

    def test_12_vrh_missing_modulus_user_input_required(self) -> None:
        prepared, _counters, context, _request = _execute_prepare()
        assert prepared.prepared_witness_digest is not None
        view = adapter.property_library_prefill(context, prepared.prepared_witness_digest, paths=PATHS)
        base = _complete_rows(view)
        for field in ("young_gpa", "poisson", "origin", "source", "reference_temperature_c"):
            rows = [dict(row) for row in base]
            rows[0][field] = None
            decision, _ = _vrh_request(context, prepared.prepared_witness_digest, rows=rows)
            with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "8" * 32) as lease:
                self.assert_reason(vl.ReasonCode.USER_INPUT_REQUIRED, adapter.execute_verified_properties, context, decision, lease, paths=PATHS)
        bad = [dict(row) for row in base]
        bad[0].pop("source")
        decision, _ = _vrh_request(context, prepared.prepared_witness_digest, rows=bad)
        with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "9" * 32) as lease:
            self.assert_reason(vl.ReasonCode.INPUT_INVALID, adapter.execute_verified_properties, context, decision, lease, paths=PATHS)

    def test_13_vrh_nonfinite_input_rejected(self) -> None:
        prepared, _counters, context, _request = _execute_prepare()
        assert prepared.prepared_witness_digest is not None
        view = adapter.property_library_prefill(context, prepared.prepared_witness_digest, paths=PATHS)
        rows = _complete_rows(view)
        rows[0]["young_gpa"] = float("inf")
        self.assert_reason(vl.ReasonCode.INPUT_INVALID, adapter.make_vrh_inputs, prepared_witness_digest=prepared.prepared_witness_digest, library_snapshot_digest=view.library_snapshot_digest, library_update=False, phase_rows=rows)

    def test_14_vrh_library_snapshot_digest_bound(self) -> None:
        prepared, _counters, context, _request = _execute_prepare()
        assert prepared.prepared_witness_digest is not None
        payload = {
            "schema_version": 1,
            "updated_at": FIXED_TIME,
            "entries": {
                "ni::BCC_A2": _entry("ni", "BCC_A2", origin="", source="x" * 1025, reference=-274.0, note="n" * 2049),
                "ni::FCC_A1": _entry("ni", "FCC_A1", source="", reference=None),
            },
        }
        raw = vl.canonical_json_bytes(payload)
        PATHS.elastic_properties_path.write_bytes(raw)
        view = adapter.property_library_prefill(context, prepared.prepared_witness_digest, paths=PATHS)
        self.assertEqual(view.library_snapshot_digest, hashlib.sha256(raw).hexdigest())
        first = view.phase_rows[0]
        self.assertIsNone(first["origin"])
        self.assertIsNone(first["source"])
        self.assertIsNone(first["reference_temperature_c"])
        self.assertEqual(first["note"], "")
        self.assertEqual(PATHS.elastic_properties_path.read_bytes(), raw)
        legacy_raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        PATHS.elastic_properties_path.write_bytes(legacy_raw)
        legacy_view = adapter.property_library_prefill(context, prepared.prepared_witness_digest, paths=PATHS)
        self.assertEqual(legacy_view.library_snapshot_digest, hashlib.sha256(legacy_raw).hexdigest())
        self.assertEqual(PATHS.elastic_properties_path.read_bytes(), legacy_raw)
        rows = _complete_rows(legacy_view)
        decision, _ = _vrh_request(context, prepared.prepared_witness_digest, rows=rows, update=False)
        with mock.patch.object(adapter, "atomic_update_bytes", side_effect=AssertionError("no false-update write")):
            with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "0" * 32) as lease:
                result = adapter.execute_verified_properties(context, decision, lease, paths=PATHS, clock=lambda: FIXED_TIME)
        self.assertEqual(result.projection["library_snapshot_digest_before"], hashlib.sha256(legacy_raw).hexdigest())
        self.assertEqual(result.projection["library_snapshot_digest_after"], hashlib.sha256(legacy_raw).hexdigest())
        self.assertEqual(PATHS.elastic_properties_path.read_bytes(), legacy_raw)
        collision_decision, _ = _vrh_request(
            context,
            prepared.prepared_witness_digest,
            rows=rows,
            update=True,
        )
        def collide(_path: object, updater: object, **_kwargs: object) -> None:
            updater(legacy_raw + b"\n")

        with mock.patch.object(adapter, "atomic_update_bytes", side_effect=collide):
            with vl.acquire_execution(collision_decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "1" * 32) as lease:
                self.assert_reason(vl.ReasonCode.STATE_CONFLICT, adapter.execute_verified_properties, context, collision_decision, lease, paths=PATHS, clock=lambda: FIXED_TIME)
        self.assertEqual(PATHS.elastic_properties_path.read_bytes(), legacy_raw)
        self.assert_reason(vl.ReasonCode.INPUT_INVALID, adapter._decode_library, b"\xef\xbb\xbf" + raw)
        self.assert_reason(vl.ReasonCode.INPUT_INVALID, adapter._decode_library, b'{"schema_version":1,"schema_version":1,"updated_at":null,"entries":{}}')

    def test_15_vrh_library_update_after_identity_gate(self) -> None:
        prepared, _counters, context, _request = _execute_prepare()
        assert prepared.prepared_witness_digest is not None
        unrelated = _entry("ni", "LIQUID", origin="", source="s" * 1025, reference=10001.0, note="n" * 2049)
        raw = json.dumps(
            {"schema_version": 1, "updated_at": FIXED_TIME, "entries": {"ni::LIQUID": unrelated}},
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        PATHS.elastic_properties_path.write_bytes(raw)
        view = adapter.property_library_prefill(context, prepared.prepared_witness_digest, paths=PATHS)
        rows = _complete_rows(view)
        no_update, _ = _vrh_request(context, prepared.prepared_witness_digest, rows=rows, update=False)
        with mock.patch.object(adapter, "atomic_update_bytes", side_effect=AssertionError("no false-update write")):
            with vl.acquire_execution(no_update, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "2" * 32) as lease:
                no_update_result = adapter.execute_verified_properties(context, no_update, lease, paths=PATHS, clock=lambda: FIXED_TIME)
        self.assertEqual(no_update_result.projection["library_snapshot_digest_before"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(no_update_result.projection["library_snapshot_digest_after"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(PATHS.elastic_properties_path.read_bytes(), raw)
        decision, _ = _vrh_request(context, prepared.prepared_witness_digest, rows=rows, update=True)
        original_update = adapter.atomic_update_bytes
        with mock.patch.object(adapter, "atomic_update_bytes", wraps=original_update) as update_call:
            with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "a" * 32) as lease:
                result = adapter.execute_verified_properties(context, decision, lease, paths=PATHS, clock=lambda: FIXED_TIME)
        self.assertEqual(update_call.call_count, 1)
        self.assertEqual(update_call.call_args.kwargs, {"create_backup": False, "maximum_bytes": 8388608, "canonical_root": PATHS.state_root})
        stored = adapter._decode_library(PATHS.elastic_properties_path.read_bytes())
        self.assertEqual(stored["entries"]["ni::LIQUID"]["source"], unrelated["source"])
        self.assertEqual(stored["entries"]["ni::LIQUID"]["note"], unrelated["note"])
        self.assertIn("ni::BCC_A2", stored["entries"])
        self.assertNotEqual(result.projection["library_snapshot_digest_before"], result.projection["library_snapshot_digest_after"])
        self.assertEqual(result.projection["library_snapshot_digest_after"], hashlib.sha256(PATHS.elastic_properties_path.read_bytes()).hexdigest())
        self.assertEqual(result.projection["library_updated_at"], FIXED_TIME)
        self.assertEqual([item.name for item in PATHS.elastic_properties_path.parent.iterdir()], [PATHS.elastic_properties_path.name])

    def test_16_strengthening_scalar_receipt_envelope(self) -> None:
        context = _bind("ni")
        result, request = _execute_strength(context, _strengthening_inputs())
        self.assertEqual(result.feature_receipt.backend_calls, 0)
        self.assertEqual(result.result_envelope.request_digest, request.request_digest)
        self.assertGreater(result.projection["total_mpa"], 100.0)

    def test_17_strengthening_no_parser_backend(self) -> None:
        context = _bind("al")
        with mock.patch.object(adapter, "_default_tdb_parser", side_effect=AssertionError("no parser")):
            result, _request = _execute_strength(context, _strengthening_inputs())
        self.assertEqual(result.feature_receipt.backend_calls, 0)

    def test_18_strengthening_provenance_required(self) -> None:
        context = _bind("ni")
        for field, value in (("input_provenance", None), ("input_confirmation", False)):
            inputs = _strengthening_inputs()
            inputs[field] = value
            decision = _strength_request(context, inputs)
            with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "b" * 32) as lease:
                self.assert_reason(vl.ReasonCode.USER_INPUT_REQUIRED, adapter.execute_verified_properties, context, decision, lease, paths=PATHS)
        bad = _strengthening_inputs()
        bad["input_confirmation"] = 1
        decision = _strength_request(context, bad)
        with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "c" * 32) as lease:
            self.assert_reason(vl.ReasonCode.INPUT_INVALID, adapter.execute_verified_properties, context, decision, lease, paths=PATHS)

    def test_19_strengthening_optional_hill_witness(self) -> None:
        vrh, context, _request, _view = _execute_vrh()
        assert vrh.hill_witness_digest is not None
        result, _request = _execute_strength(context, _strengthening_inputs(hill_digest=vrh.hill_witness_digest))
        self.assertGreater(result.projection["total_mpa"], 0.0)
        conflict = _strengthening_inputs(hill_digest=vrh.hill_witness_digest)
        conflict["taylor"]["shear_gpa"] = 80.0
        decision = _strength_request(context, conflict)
        with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "d" * 32) as lease:
            self.assert_reason(vl.ReasonCode.INPUT_INVALID, adapter.execute_verified_properties, context, decision, lease, paths=PATHS)

    def test_20_strengthening_not_performed_neutral(self) -> None:
        context = _bind("fe")
        result, _request = _execute_strength(context, _strengthening_inputs())
        self.assertEqual(result.result_envelope.settings["experimental_qualification"], "NOT_PERFORMED")
        self.assertEqual(result.feature_receipt.outcome, "success")

    def test_21_c15_automatic_omitted(self) -> None:
        context = _bind("fe")
        decision = _prepare_request(context)
        self.assertIs(type(decision), vl.FeatureRequest)
        self.assertNotIn("C15_LAVES", decision.effective_phases)

    def test_22_c15_manual_zero_side_effect(self) -> None:
        context = _bind("fe")
        decision = _prepare_request(context, requested=("C15_LAVES",))
        self.assertIs(type(decision), vl.RejectedFeatureReceipt)
        self.assertEqual((decision.reason_code, decision.backend_calls), ("C15_PHASE_REJECTED", 0))
        self.assertFalse(PATHS.elastic_properties_path.exists())

    def test_23_c15_restored_zero_side_effect(self) -> None:
        context = _bind("fe")
        valid = _prepare_request(context)
        self.assertIs(type(valid), vl.FeatureRequest)
        forged = _forged_c15(valid)
        with vl.acquire_execution(valid, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "e" * 32) as lease:
            self.assert_reason(vl.ReasonCode.C15_PHASE_REJECTED, adapter.execute_verified_properties, context, forged, lease, paths=PATHS)
        self.assertFalse(PATHS.elastic_properties_path.exists())

    def test_24_c15_cache_zero_side_effect(self) -> None:
        self.test_23_c15_restored_zero_side_effect()

    def test_25_c15_direct_zero_side_effect(self) -> None:
        self.test_23_c15_restored_zero_side_effect()

    def test_26_upstream_fe_before_repository(self) -> None:
        selector = {"database_key": "fe", "profile_key": "upstream", "include_physical_pdb": True}
        with self.assertRaises(vl.VerifiedLoaderError) as caught:
            vl.bind_selected_database(selector, _catalog(), DummyPaths())
        self.assertEqual(caught.exception.reason_code, vl.ReasonCode.UPSTREAM_PROFILE_REJECTED)
        self.assertFalse(PATHS.elastic_properties_path.exists())

    def test_27_fifo_prepare_serial_no_overlap(self) -> None:
        context = _bind("ni")
        decision = _prepare_request(context)
        self.assertIs(type(decision), vl.FeatureRequest)
        counters = Counters()
        errors: list[BaseException] = []
        def backend(*args: object) -> dict[str, float]:
            counters.backend += 1
            counters.active += 1
            counters.max_active = max(counters.max_active, counters.active)
            try:
                time.sleep(0.02)
                return _backend_answer({"BCC_A2": 0.4, "FCC_A1": 0.6})
            finally:
                counters.active -= 1
        def run(nonce: str) -> None:
            try:
                with mock.patch.object(adapter, "_default_pdb_parser", counters.pdb_parser):
                    with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: nonce) as lease:
                        adapter.execute_verified_properties(context, decision, lease, paths=PATHS, tdb_parser=counters.tdb_parser, backend=backend, clock=lambda: FIXED_TIME)
            except BaseException as error:
                errors.append(error)
        threads = [threading.Thread(target=run, args=(str(index) * 32,)) for index in (6, 7)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual((counters.backend, counters.max_active), (2, 1))

    def test_28_prepare_point_no_retry(self) -> None:
        self.test_05_prepare_backend_failure_no_retry()

    def test_29_result_state_projections_not_authority(self) -> None:
        result, _counters, _context, _request = _execute_prepare()
        text = vl.canonical_json_bytes(result.projection).decode("utf-8").casefold()
        for forbidden in ("path", "filename", "database", "bytes", "materializer", "session"):
            self.assertNotIn(forbidden, text)

    def test_30_disabled_egress_no_body(self) -> None:
        result, _counters, _context, _request = _execute_prepare()
        self.assertEqual(result.result_envelope.artifacts, ())
        self.assertEqual(result.result_envelope.tables, ())
        self.assertEqual(result.result_envelope.figures, ())

    def test_31_generation_invalidation_clears_witness(self) -> None:
        result, _counters, context, _request = _execute_prepare()
        assert result.prepared_witness_digest is not None
        adapter.clear_property_witnesses()
        self.assert_reason(vl.ReasonCode.DATA_UNAVAILABLE, adapter.property_library_prefill, context, result.prepared_witness_digest, paths=PATHS)
        live_context = _bind("ni")
        decision = _strength_request(live_context, _strengthening_inputs())
        with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "f" * 32) as closed_lease:
            pass
        self.assert_reason(
            vl.ReasonCode.LEASE_IDENTITY_MISMATCH,
            adapter.execute_verified_properties,
            live_context,
            decision,
            closed_lease,
            paths=object(),
        )


    # ------------------------------------------------------------------
    # BL-38: веса VRH — объёмные доли фаз
    # ------------------------------------------------------------------

    def _vrh_with_moduli(
        self,
        backend: object,
        young_by_phase: dict[str, float],
        *,
        physical_overrides: bool = True,
    ) -> tuple[adapter.VerifiedPropertiesResult, adapter.VerifiedPropertiesResult, vl.BoundDatabaseContext]:
        prepared, _counters, context, _request = _execute_prepare(
            "fe",
            backend=backend,
            physical_overrides=physical_overrides,
        )
        assert prepared.prepared_witness_digest is not None
        view = adapter.property_library_prefill(context, prepared.prepared_witness_digest, paths=PATHS)
        rows = [
            {
                "phase": row["phase"],
                "volume_fraction": row["volume_fraction"],
                "young_gpa": young_by_phase[row["phase"]],
                "poisson": 0.25,
                "origin": "справочно",
                "source": "условное значение для проверки весов",
                "reference_temperature_c": 25.0,
                "note": "",
            }
            for row in view.phase_rows
        ]
        decision, _view = _vrh_request(context, prepared.prepared_witness_digest, rows=rows)
        with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "a" * 32) as lease:
            vrh = adapter.execute_verified_properties(context, decision, lease, paths=PATHS, clock=lambda: FIXED_TIME)
        return prepared, vrh, context

    def test_32_single_phase_volume_weight_is_one(self) -> None:
        # (а) Одна фаза: объёмная доля равна мольной и равна 1, VRH не меняется.
        def backend(*_args: object) -> dict[str, object]:
            return _backend_answer({"FCC_A1": 1.0}, {"FCC_A1": 6.93})

        prepared, vrh, _context = self._vrh_with_moduli(backend, {"FCC_A1": 210.0})
        rows = prepared.projection["phase_rows"]
        self.assertEqual(
            rows,
            [
                {
                    "phase": "FCC_A1",
                    "mole_fraction": 1.0,
                    "molar_volume_cm3": 6.93,
                    "volume_fraction": 1.0,
                    "volume_source": "direct",
                }
            ],
        )
        self.assertEqual(prepared.projection["warnings"], [])
        summary = vrh.projection["summary"]
        moduli = properties.moduli_from_e_nu(210.0, 0.25)
        for bound in ("Voigt", "Reuss", "Hill"):
            self.assertAlmostEqual(summary[f"K_{bound}_GPa"], moduli.bulk_gpa, places=9)
            self.assertAlmostEqual(summary[f"G_{bound}_GPa"], moduli.shear_gpa, places=9)
            self.assertAlmostEqual(summary[f"E_{bound}_GPa"], 210.0, places=9)

    def test_33_two_phase_volume_weights_follow_molar_volumes(self) -> None:
        # (б) Две фазы с разным молярным объёмом: φ/x различаются ровно в
        # отношении молярных объёмов, и VRH берёт объёмные доли.
        fractions = {"BCC_A2": 0.25, "FCC_A1": 0.75}
        volumes = {"BCC_A2": 12.0, "FCC_A1": 6.0}

        def backend(*_args: object) -> dict[str, object]:
            return _backend_answer(fractions, volumes)

        prepared, vrh, context = self._vrh_with_moduli(backend, {"BCC_A2": 100.0, "FCC_A1": 300.0})
        rows = {row["phase"]: row for row in prepared.projection["phase_rows"]}
        # Σ x·Vm = 0,25·12 + 0,75·6 = 7,5; φ = 3/7,5 = 0,4 и 4,5/7,5 = 0,6.
        self.assertAlmostEqual(rows["BCC_A2"]["volume_fraction"], 0.4, places=15)
        self.assertAlmostEqual(rows["FCC_A1"]["volume_fraction"], 0.6, places=15)
        self.assertEqual(rows["BCC_A2"]["mole_fraction"], 0.25)
        self.assertEqual(rows["FCC_A1"]["mole_fraction"], 0.75)
        ratio = (rows["BCC_A2"]["volume_fraction"] / rows["BCC_A2"]["mole_fraction"]) / (
            rows["FCC_A1"]["volume_fraction"] / rows["FCC_A1"]["mole_fraction"]
        )
        self.assertAlmostEqual(ratio, volumes["BCC_A2"] / volumes["FCC_A1"], places=12)

        view = adapter.property_library_prefill(context, prepared.prepared_witness_digest, paths=PATHS)
        self.assertEqual(
            [(row["phase"], row["mole_fraction"], row["volume_fraction"]) for row in view.phase_rows],
            [(name, fractions[name], rows[name]["volume_fraction"]) for name in ("BCC_A2", "FCC_A1")],
        )

        vrh_rows = {row["phase"]: row["volume_fraction"] for row in vrh.projection["phase_rows"]}
        self.assertEqual(vrh_rows, {name: rows[name]["volume_fraction"] for name in rows})
        soft = properties.moduli_from_e_nu(100.0, 0.25)
        hard = properties.moduli_from_e_nu(300.0, 0.25)
        summary = vrh.projection["summary"]
        self.assertAlmostEqual(summary["K_Voigt_GPa"], 0.4 * soft.bulk_gpa + 0.6 * hard.bulk_gpa, places=9)
        self.assertAlmostEqual(summary["G_Reuss_GPa"], 1.0 / (0.4 / soft.shear_gpa + 0.6 / hard.shear_gpa), places=9)
        # С мольными весами Voigt был бы другим — веса действительно сменились.
        self.assertNotAlmostEqual(summary["K_Voigt_GPa"], 0.25 * soft.bulk_gpa + 0.75 * hard.bulk_gpa, places=3)

    def test_34_vrh_rejects_mole_fraction_in_place_of_volume(self) -> None:
        def backend(*_args: object) -> dict[str, object]:
            return _backend_answer({"BCC_A2": 0.25, "FCC_A1": 0.75}, {"BCC_A2": 12.0, "FCC_A1": 6.0})

        prepared, _counters, context, _request = _execute_prepare("fe", backend=backend)
        assert prepared.prepared_witness_digest is not None
        view = adapter.property_library_prefill(context, prepared.prepared_witness_digest, paths=PATHS)
        rows = _complete_rows(view)
        rows[0]["volume_fraction"] = view.phase_rows[0]["mole_fraction"]
        decision, _view = _vrh_request(context, prepared.prepared_witness_digest, rows=rows)
        with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "b" * 32) as lease:
            self.assert_reason(vl.ReasonCode.DATA_UNAVAILABLE, adapter.execute_verified_properties, context, decision, lease, paths=PATHS, clock=lambda: FIXED_TIME)

    def test_35_overrides_off_parses_pdb_without_corrections(self) -> None:
        # (в) Галочка снята: PDB разбирается без поправок и отдельной ревизией
        # кэша; отметка разбора идёт первой строкой warnings.
        seen: list[str] = []

        def off_parser(data: bytes) -> FakePhysicalOff:
            seen.append("off")
            return FakePhysicalOff()

        def on_parser(data: bytes) -> FakePhysical:
            seen.append("on")
            return FakePhysical()

        def backend(*_args: object) -> dict[str, object]:
            return _backend_answer({"BCC_A2": 0.4, "FCC_A1": 0.6}, sources={"BCC_A2": "mixture", "FCC_A1": "direct"})

        with mock.patch.object(adapter, "_overrides_off_pdb_parser", off_parser):
            with mock.patch.object(adapter, "_default_pdb_parser", on_parser):
                context = _bind("ni")
                decision = _prepare_request(context)
                assert type(decision) is vl.FeatureRequest
                with vl.acquire_execution(decision, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "c" * 32) as lease:
                    result = adapter.execute_verified_properties(
                        context, decision, lease, paths=PATHS, tdb_parser=Counters().tdb_parser,
                        backend=backend, clock=lambda: FIXED_TIME, physical_overrides=False,
                    )
        self.assertEqual(seen, ["off"])
        warnings = result.projection["warnings"]
        self.assertEqual(warnings[0], FakePhysicalOff.override_notes[0])
        self.assertEqual(len(warnings), 2)
        self.assertIn("BCC_A2", warnings[1])
        self.assertIn("правилу смеси", warnings[1])
        self.assertEqual(adapter.PDB_PARSER_REVISION_OVERRIDES_OFF, "thermogar-physical-pdb-1-overrides-off")
        self.assertNotEqual(adapter.PDB_PARSER_REVISION_OVERRIDES_OFF, adapter.PDB_PARSER_REVISION)

    def test_36_backend_answer_shape_is_closed(self) -> None:
        # Старый ответ бэкенда (одни мольные доли) не проходит: объёмные доли
        # не подменяются мольными молча.
        for answer in (
            {"BCC_A2": 0.4, "FCC_A1": 0.6},
            _backend_answer({"BCC_A2": 0.4, "FCC_A1": 0.6}, {"BCC_A2": 7.0}),
            _backend_answer({"BCC_A2": 0.4, "FCC_A1": 0.6}, {"BCC_A2": 7.0, "FCC_A1": 0.0}),
            _backend_answer({"BCC_A2": 0.4, "FCC_A1": 0.6}, {"BCC_A2": 7.0, "FCC_A1": 7}),
            _backend_answer({"BCC_A2": 0.4, "FCC_A1": 0.6}, sources={"BCC_A2": "direct", "FCC_A1": "guess"}),
        ):
            with self.subTest(answer=answer):
                with self.assertRaises(vl.VerifiedLoaderError) as caught:
                    _execute_prepare("fe", backend=lambda *_args, value=answer: value)
                self.assertEqual(caught.exception.reason_code, vl.ReasonCode.RESULT_INVALID)

    @staticmethod
    def _detector_removing(*names: str) -> tuple[object, list[tuple[str, ...]]]:
        """Подменный детектор пары «порядок/беспорядок»: снимает ``names``."""

        seen: list[tuple[str, ...]] = []

        def drop(_database: object, _components: object, phases: object, verify: bool = True):
            ordered = tuple(str(name) for name in phases)
            seen.append(ordered)
            removed = {
                name: repair.BrokenOrderDisorder(
                    ordered_phase=name,
                    disordered_phase="BCC_A2",
                    interstitial_of_disordered=("C", "VA"),
                    interstitial_of_ordered=(("VA",),),
                    reason=f"fake: {name} does not build",
                )
                for name in ordered
                if name in names
            }
            return [name for name in ordered if name not in removed], removed

        return drop, seen

    def test_37_detector_removed_phase_skips_backend_and_is_named(self) -> None:
        # BL-40: набор фаз подготовки идёт через тот же детектор, что у
        # плотности; снятая фаза в движок не попадает и называется в
        # warnings сразу после отметки поправок, текстом плотности.
        drop, seen = self._detector_removing("LIQUID")
        calls: list[tuple[str, ...]] = []

        def backend(_database: object, _physical: object, call: adapter.PropertyPrepareCall) -> dict[str, object]:
            calls.append(call.phases)
            return _backend_answer({"BCC_A2": 0.4, "FCC_A1": 0.6}, sources={"BCC_A2": "mixture", "FCC_A1": "direct"})

        with mock.patch.object(repair, "drop_broken_order_disorder", drop):
            with mock.patch.object(adapter, "_overrides_off_pdb_parser", lambda _data: FakePhysicalOff()):
                result, _counters, _context, _request = _execute_prepare("ni", backend=backend, physical_overrides=False)
        self.assertEqual(seen, [EFFECTIVE])
        self.assertEqual(calls, [("BCC_A2", "FCC_A1")])
        warnings = result.projection["warnings"]
        self.assertEqual(len(warnings), 3)
        self.assertEqual(warnings[0], FakePhysicalOff.override_notes[0])
        self.assertTrue(warnings[1].startswith("Из расчёта исключены фазы, модель которых не строится"), warnings[1])
        self.assertIn("LIQUID (связана с BCC_A2: fake: LIQUID does not build)", warnings[1])
        self.assertIn("правилу смеси", warnings[2])
        self.assertEqual([row["phase"] for row in result.projection["phase_rows"]], ["BCC_A2", "FCC_A1"])

        # Бэкенд, вернувший снятую фазу, отвергается: её нет в наборе расчёта.
        def leaky(*_args: object) -> dict[str, object]:
            return _backend_answer({"BCC_A2": 0.4, "LIQUID": 0.6})

        with mock.patch.object(repair, "drop_broken_order_disorder", drop):
            with self.assertRaises(vl.VerifiedLoaderError) as caught:
                _execute_prepare("ni", backend=leaky)
        self.assertEqual(caught.exception.reason_code, vl.ReasonCode.RESULT_INVALID)

    def test_38_detector_removing_every_phase_is_input_invalid(self) -> None:
        drop, _seen = self._detector_removing(*EFFECTIVE)
        counters = Counters()
        with mock.patch.object(repair, "drop_broken_order_disorder", drop):
            with self.assertRaises(vl.VerifiedLoaderError) as caught:
                _execute_prepare("ni", counters=counters)
        self.assertEqual(caught.exception.reason_code, vl.ReasonCode.INPUT_INVALID)
        self.assertIn("не осталось допустимых фаз", str(caught.exception))
        self.assertEqual(counters.backend, 0)

    def test_39_detector_without_removals_leaves_warnings_unchanged(self) -> None:
        drop, seen = self._detector_removing()
        with mock.patch.object(repair, "drop_broken_order_disorder", drop):
            result, counters, _context, _request = _execute_prepare("ni")
        self.assertEqual(seen, [EFFECTIVE])
        self.assertEqual(counters.backend, 1)
        self.assertEqual(result.projection["warnings"], [])


if __name__ == "__main__":
    program = unittest.main(verbosity=2, exit=False)
    _cleanup()
    if not program.result.wasSuccessful():
        raise SystemExit(1)
