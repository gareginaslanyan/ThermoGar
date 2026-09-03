"""Non-scientific fake-seam tests for the Wave-B1 verified loader foundation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest


ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _pyc_manifest() -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    for base in (ROOT / "app", ROOT / "tools"):
        for candidate in base.rglob("*.pyc"):
            relative = candidate.relative_to(ROOT).as_posix()
            data = candidate.read_bytes()
            result[relative] = (len(data), hashlib.sha256(data).hexdigest())
    return result


PYC_BEFORE = _pyc_manifest()

import thermogar_verified_loaders as vl
from thermogar_secure_io import SecureIOError


FIXED_TIME = "2026-08-29T12:34:56.123456Z"
FIXED_NONCE = "0123456789abcdef0123456789abcdef"

REASON_LITERALS = (
    "SCHEMA_INVALID", "CANONICAL_JSON_INVALID", "FEATURE_ID_UNKNOWN",
    "FEATURE_REVISION_UNSUPPORTED", "DATABASE_KEY_REJECTED", "PROFILE_KEY_REJECTED",
    "UPSTREAM_PROFILE_REJECTED", "ARTIFACT_PATH_REJECTED", "ARTIFACT_MISSING",
    "ARTIFACT_OVERSIZE", "ARTIFACT_IO_FAILED", "TDB_HASH_MISMATCH",
    "PASSPORT_REQUIRED", "PASSPORT_HASH_MISMATCH", "PASSPORT_INVALID",
    "PATCH_ID_MISMATCH", "PDB_HASH_MISMATCH", "PDB_INVALID",
    "BINDING_IDENTITY_MISMATCH", "BINDING_STALE", "GENERATION_STALE",
    "INPUT_INVALID", "USER_INPUT_REQUIRED", "PHASE_NOT_PRESENT", "PHASE_SET_EMPTY",
    "PHASE_POLICY_MISMATCH", "C15_PHASE_REJECTED", "LIQUID_PHASE_REQUIRED",
    "PACKAGE_UNAVAILABLE", "DATA_UNAVAILABLE", "CAPABILITY_UNAVAILABLE",
    "REQUEST_DIGEST_MISMATCH", "LEASE_BUSY", "LEASE_IDENTITY_MISMATCH",
    "BACKEND_FAILED", "RESULT_INVALID", "RESULT_DIGEST_MISMATCH", "RECEIPT_INVALID",
    "ENVELOPE_INVALID", "ENVELOPE_CONTEXT_MISMATCH", "RAW_PATH_REJECTED",
    "IMPORT_SCHEMA_REJECTED", "EXPORT_SOURCE_REJECTED", "STATE_CONFLICT",
    "ARTIFACT_WRITE_FAILED",
)

FEATURE_LITERALS = (
    "equilibrium_single", "equilibrium_temperature_scan", "equilibrium_composition_scan",
    "diagram_binary", "diagram_isopleth", "diagram_ternary", "diagram_phase_fraction_map",
    "solidification_equilibrium", "solidification_scheil", "solidification_compare",
    "energy_isolated_gm", "energy_driving_force", "energy_tzero",
    "property_density_single", "property_density_temperature", "property_elastic_prepare",
    "property_elastic_vrh", "property_strengthening", "property_pdb_self_test",
    "property_coverage_view", "kinetics_diffusion_single", "kinetics_homogenization",
    "kinetics_mobility_coverage", "kinetics_precipitation_kwn", "data_alloy_state",
    "data_alloy_transfer", "data_project_state", "data_project_transfer",
    "data_history_state", "data_history_export", "data_batch_request_import",
    "data_batch_execute", "data_batch_export", "data_result_artifact",
    "data_database_passport_view", "data_install_preflight_view", "data_reference_artifact",
)

FEATURE_RECEIPT_FIELD_LITERALS = (
    "schema", "feature_id", "feature_revision", "outcome", "reason_code",
    "reason_detail", "binding_digest", "binding_generation", "tdb_evidence",
    "passport_evidence", "physical_pdb_evidence", "phase_policy_id",
    "phase_policy_revision", "requested_phases", "requested_phases_digest",
    "effective_phases", "effective_phases_digest", "inputs_digest",
    "request_digest", "lease_id", "backend", "packages", "backend_calls",
    "point_count", "result_digest", "started_at_utc", "finished_at_utc",
    "receipt_digest",
)

RESULT_ENVELOPE_FIELD_LITERALS = (
    "schema", "feature_id", "feature_revision", "binding_digest",
    "binding_generation", "request_digest", "receipt_digest", "outcome",
    "settings", "settings_digest", "tables", "tables_digest", "figures",
    "figures_digest", "artifacts", "artifacts_digest", "result_digest",
    "created_at_utc", "envelope_digest",
)



class DummyPaths:
    __slots__ = ()


def _padded(prefix: bytes, size: int, fill: bytes = b" ") -> bytes:
    if len(prefix) > size:
        raise AssertionError("fixture prefix exceeds pinned size")
    return prefix + fill * (size - len(prefix))


def _passport_bytes(*, duplicate: bool = False, patch_id: str = vl.FE_PATCH_ID) -> bytes:
    payload = {
        "schema_version": 2,
        "profile_id": "mc_fe_v2062_thermogar_working",
        "patch_id": patch_id,
        "compatibility_patches": [
            {
                "patch_id": patch_id,
                "phase": "C15_LAVES",
                "applied": True,
                "matched_active_commands": 1,
            }
        ],
        "working_profile": {
            "thermodynamic_plus_mobility_database": {
                "sha256": "236EC4D9B0540DE04E4E6305FAA208672F31FBDF45B2AE84E92F80BD98053612"
            }
        },
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if duplicate:
        text = text.replace(
            '"schema_version":2',
            '"schema_version":2,"schema_version":2',
            1,
        )
    return _padded(text.encode("utf-8"), 12393)


class FakeWorld:
    def __init__(self) -> None:
        policy = vl.canonical_release_manifest()
        dbs = policy["databases"]
        self.paths = {
            dbs["ni"]["tdb"]["logical_path"]: _padded(b"NI-TDB\n", dbs["ni"]["tdb"]["size_bytes"]),
            dbs["al"]["tdb"]["logical_path"]: _padded(b"AL-TDB\n", dbs["al"]["tdb"]["size_bytes"]),
            dbs["fe"]["tdb"]["logical_path"]: _padded(b"FE-TDB\n", dbs["fe"]["tdb"]["size_bytes"]),
            dbs["fe"]["passport"]["logical_path"]: _passport_bytes(),
            policy["physical_pdb"]["logical_path"]: _padded(
                b"$thermo-physical\nDEFINE_PARAMETER DP density!\n",
                policy["physical_pdb"]["size_bytes"],
            ),
        }
        self.expected = {
            dbs["ni"]["tdb"]["logical_path"]: dbs["ni"]["tdb"]["sha256"],
            dbs["al"]["tdb"]["logical_path"]: dbs["al"]["tdb"]["sha256"],
            dbs["fe"]["tdb"]["logical_path"]: dbs["fe"]["tdb"]["sha256"],
            dbs["fe"]["passport"]["logical_path"]: dbs["fe"]["passport"]["sha256"],
            policy["physical_pdb"]["logical_path"]: policy["physical_pdb"]["sha256"],
        }
        self.digest_override: dict[str, str] = {}
        self.read_calls = 0
        self.phase_calls = 0
        self.read_error: Exception | None = None

    def _logical(self, path: object) -> str:
        normalized = os.fspath(path).replace("\\", "/")
        for logical in self.paths:
            if normalized.endswith(logical):
                return logical
        raise FileNotFoundError(normalized)

    def reader(self, path: object, **_kwargs: object) -> SimpleNamespace:
        self.read_calls += 1
        if self.read_error is not None:
            raise self.read_error
        logical = self._logical(path)
        return SimpleNamespace(data=self.paths[logical])

    def digest(self, data: bytes) -> str:
        for logical, current in self.paths.items():
            if data == current:
                return self.digest_override.get(logical, self.expected[logical])
        return hashlib.sha256(data).hexdigest()

    def phases(self, artifact: vl.VerifiedArtifact) -> tuple[str, ...]:
        self.phase_calls += 1
        if artifact.evidence.sha256 == self.expected[
            "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb"
        ]:
            return ("LIQUID", "FCC_A1", "C15_LAVES", "BCC_A2")
        return ("LIQUID", "FCC_A1", "BCC_A2")

    def catalog(self) -> vl.ArtifactCatalog:
        return vl.ArtifactCatalog.from_policy(
            ROOT,
            vl.canonical_release_manifest(),
            snapshot_reader=self.reader,
            digest_function=self.digest,
            phase_provider=self.phases,
        )


def _bind_fe(world: FakeWorld, *, physical: bool = False) -> vl.BoundDatabaseContext:
    selector = {"database_key": "fe", "profile_key": "thermogar_patch"}
    if physical:
        selector["include_physical_pdb"] = True
    return vl.bind_selected_database(selector, world.catalog(), DummyPaths())


def _request(context: vl.BoundDatabaseContext, requested: tuple[str, ...] = ()) -> vl.FeatureRequest:
    result = vl.prepare_feature_request(
        "equilibrium_single",
        context,
        {"composition": {"C": 0.2}, "pressure_pa": 101325.0, "temperature_k": 973.15},
        requested,
        clock=lambda: FIXED_TIME,
    )
    if type(result) is not vl.FeatureRequest:
        raise AssertionError(result)
    return result


class VerifiedLoadersTests(unittest.TestCase):
    def setUp(self) -> None:
        vl.invalidate_binding_generation()

    def assert_reason(self, expected: vl.ReasonCode, callable_obj, *args, **kwargs) -> vl.VerifiedLoaderError:
        with self.assertRaises(vl.VerifiedLoaderError) as caught:
            callable_obj(*args, **kwargs)
        self.assertEqual(caught.exception.reason_code, expected)
        return caught.exception

    def test_01_closed_registry_reason_and_schema_fields(self) -> None:
        self.assertEqual(tuple(item.value for item in vl.ReasonCode), REASON_LITERALS)
        self.assertEqual(vl.FEATURE_IDS, FEATURE_LITERALS)
        self.assertEqual(vl.FEATURE_REGISTRY, {item: "1" for item in FEATURE_LITERALS})
        self.assertEqual(len(vl.BOUND_CONTEXT_FIELDS), 11)
        self.assertEqual(len(vl.FEATURE_REQUEST_FIELDS), 12)
        self.assertEqual(len(vl.EXECUTION_LEASE_FIELDS), 12)
        self.assertEqual(len(vl.REJECTION_FIELDS), 15)
        self.assertEqual(len(vl.FEATURE_RECEIPT_FIELDS), 28)
        self.assertEqual(vl.FEATURE_RECEIPT_FIELDS, FEATURE_RECEIPT_FIELD_LITERALS)
        self.assertEqual(len(vl.RESULT_ENVELOPE_FIELDS), 19)
        self.assertEqual(vl.RESULT_ENVELOPE_FIELDS, RESULT_ENVELOPE_FIELD_LITERALS)

    def test_02_canonical_json_is_exact_and_fail_closed(self) -> None:
        value = {"z": [1, True, None, 1.25], "а": "UTF-8"}
        encoded = vl.canonical_json_bytes(value)
        self.assertEqual(encoded, '{"z":[1,true,null,1.25],"а":"UTF-8"}'.encode("utf-8"))
        self.assertEqual(vl.load_canonical_json(encoded), value)
        self.assert_reason(vl.ReasonCode.CANONICAL_JSON_INVALID, vl.load_canonical_json, b'{"b":1,"a":2}')
        self.assert_reason(vl.ReasonCode.CANONICAL_JSON_INVALID, vl.load_canonical_json, b'{"a":1,"a":2}')
        self.assert_reason(vl.ReasonCode.CANONICAL_JSON_INVALID, vl.load_canonical_json, b'{"a":NaN}')
        self.assert_reason(vl.ReasonCode.CANONICAL_JSON_INVALID, vl.canonical_json_bytes, {"x": float("inf")})
        self.assert_reason(vl.ReasonCode.CANONICAL_JSON_INVALID, vl.canonical_json_bytes, {"x": (1, 2)})

    def test_03_canonical_fe_bind_and_evidence_are_path_free(self) -> None:
        world = FakeWorld()
        context = _bind_fe(world, physical=True)
        self.assertEqual(context.database_key, "fe")
        self.assertEqual(context.profile_key, "thermogar_patch")
        self.assertEqual(context.patch_id, "TG-FE-2062-C15-001")
        self.assertEqual(context.tdb.sha256, "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612")
        self.assertEqual(context.passport.sha256, "c818f3132840304ea38017cb7419790a290a1ca2e949b01e8954931ac8f17491")
        self.assertEqual(context.physical_pdb.sha256, "4cf81c992b57263c50b370ea47eb0d5bb4f622cf23c18479bab54267762f20bd")
        self.assertEqual(context.phase_policy.eligible_phases, ("BCC_A2", "FCC_A1", "LIQUID"))
        self.assertNotIn("C15_LAVES", context.phase_policy.eligible_phases)
        encoded = context.to_json_bytes()
        self.assertEqual(vl.BoundDatabaseContext.from_json_bytes(encoded), context)
        lower = encoded.lower()
        for forbidden in (b"database_path", b"installation_root", b"project_root", b"fe-tdb"):
            self.assertNotIn(forbidden, lower)
        mutated = context.to_dict()
        mutated["unknown"] = 1
        self.assert_reason(
            vl.ReasonCode.SCHEMA_INVALID,
            vl.BoundDatabaseContext.from_json_bytes,
            vl.canonical_json_bytes(mutated),
        )

    def test_03b_canonical_fe_real_snapshots_bind_without_parser_or_backend(self) -> None:
        phase_calls = 0

        def phases(_artifact: vl.VerifiedArtifact) -> tuple[str, ...]:
            nonlocal phase_calls
            phase_calls += 1
            return ("LIQUID", "FCC_A1", "BCC_A2", "C15_LAVES")

        catalog = vl.ArtifactCatalog.from_policy(
            ROOT,
            vl.canonical_release_manifest(),
            phase_provider=phases,
        )
        context = vl.bind_selected_database(
            {
                "database_key": "fe",
                "profile_key": "thermogar_patch",
                "include_physical_pdb": True,
            },
            catalog,
            DummyPaths(),
        )
        self.assertEqual(phase_calls, 1)
        self.assertEqual(context.tdb.size_bytes, 568690)
        self.assertEqual(context.passport.size_bytes, 12393)
        self.assertEqual(context.physical_pdb.size_bytes, 28102)
        self.assertEqual(context.phase_policy.policy_id, "thermogar.fe-c15-exclusion@1")
        self.assertNotIn("C15_LAVES", context.phase_policy.eligible_phases)

    def test_04_ni_al_allowlist_binding_and_selection_invalidation(self) -> None:
        world = FakeWorld()
        catalog = world.catalog()
        ni = vl.bind_selected_database({"database_key": "ni"}, catalog, DummyPaths())
        self.assertIsNone(ni.profile_key)
        self.assertIsNone(ni.passport)
        self.assertEqual(ni.tdb.sha256, "1882d841a337063e0585d261c690ae7e565838234e231e21b8541a5cb0dba391")
        ni_request = _request(ni)
        al = vl.bind_selected_database({"database_key": "al"}, catalog, DummyPaths())
        self.assertEqual(al.tdb.sha256, "f9bdf21d434fbe78b5ef3f7f2de69763fa40b81335cdc58889907d41c80cd717")
        self.assertGreater(al.binding_generation, ni.binding_generation)
        self.assert_reason(vl.ReasonCode.GENERATION_STALE, vl.acquire_execution, ni_request, DummyPaths())

    def test_05_policy_paths_hashes_profiles_and_bytes_fail_before_phase_parser(self) -> None:
        policy = vl.canonical_release_manifest()
        bad_path = json.loads(json.dumps(policy))
        bad_path["databases"]["fe"]["tdb"]["logical_path"] = "databases/diagnostic/fe/unpatched.tdb"
        self.assert_reason(vl.ReasonCode.ARTIFACT_PATH_REJECTED, vl.ArtifactCatalog.from_policy, ROOT, bad_path)
        bad_hash = json.loads(json.dumps(policy))
        bad_hash["databases"]["fe"]["tdb"]["sha256"] = "0" * 64
        self.assert_reason(vl.ReasonCode.TDB_HASH_MISMATCH, vl.ArtifactCatalog.from_policy, ROOT, bad_hash)

        world = FakeWorld()
        catalog = world.catalog()
        self.assert_reason(
            vl.ReasonCode.UPSTREAM_PROFILE_REJECTED,
            vl.bind_selected_database,
            {"database_key": "fe", "profile_key": "upstream_original"}, catalog, DummyPaths(),
        )
        self.assertEqual(world.read_calls, 0)
        self.assert_reason(
            vl.ReasonCode.RAW_PATH_REJECTED,
            vl.bind_selected_database,
            {"database_key": "fe", "profile_key": "thermogar_patch", "database_path": "x"},
            catalog, DummyPaths(),
        )
        self.assertEqual(world.read_calls, 0)

        fe_path = "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb"
        world.paths[fe_path] = b"X" + world.paths[fe_path][1:]
        world.digest_override[fe_path] = hashlib.sha256(world.paths[fe_path]).hexdigest()
        self.assert_reason(vl.ReasonCode.TDB_HASH_MISMATCH, _bind_fe, world)
        self.assertEqual(world.phase_calls, 0)

        world = FakeWorld()
        world.read_error = SecureIOError("File exceeds the bounded snapshot limit.")
        self.assert_reason(vl.ReasonCode.ARTIFACT_OVERSIZE, _bind_fe, world)
        self.assertEqual(world.phase_calls, 0)

    def test_06_passport_and_pdb_shape_fail_before_phase_or_backend(self) -> None:
        passport_path = "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.passport.json"
        world = FakeWorld()
        world.paths[passport_path] = _passport_bytes(duplicate=True)
        self.assert_reason(vl.ReasonCode.PASSPORT_INVALID, _bind_fe, world)
        self.assertEqual(world.phase_calls, 0)

        world = FakeWorld()
        world.paths[passport_path] = _passport_bytes(patch_id="WRONG")
        self.assert_reason(vl.ReasonCode.PATCH_ID_MISMATCH, _bind_fe, world)
        self.assertEqual(world.phase_calls, 0)

        pdb_path = "databases/physical/original/physical_data_v103.pdb"
        world = FakeWorld()
        world.paths[pdb_path] = _padded(b"MALFORMED-PDB", len(world.paths[pdb_path]))
        self.assert_reason(vl.ReasonCode.PDB_INVALID, _bind_fe, world, physical=True)
        self.assertEqual(world.phase_calls, 0)

    def test_07_phase_policy_automatic_and_explicit_paths(self) -> None:
        world = FakeWorld()
        context = _bind_fe(world)
        automatic = _request(context)
        self.assertEqual(automatic.requested_phases, ())
        self.assertEqual(automatic.effective_phases, ("BCC_A2", "FCC_A1", "LIQUID"))
        explicit = _request(context, ("LIQUID", "FCC_A1"))
        self.assertEqual(explicit.requested_phases, ("LIQUID", "FCC_A1"))
        self.assertEqual(explicit.effective_phases, ("FCC_A1", "LIQUID"))
        rejected = vl.prepare_feature_request(
            "equilibrium_single", context, {"temperature_k": 973.15}, ("C15_LAVES",),
            clock=lambda: FIXED_TIME,
        )
        self.assertIsInstance(rejected, vl.RejectedFeatureReceipt)
        self.assertEqual(rejected.reason_code, "C15_PHASE_REJECTED")
        self.assertEqual(rejected.backend_calls, 0)
        self.assertEqual(vl.RejectedFeatureReceipt.from_json_bytes(rejected.to_json_bytes()), rejected)
        missing = vl.prepare_feature_request(
            "equilibrium_single", context, {"temperature_k": 973.15}, ("SIGMA",),
            clock=lambda: FIXED_TIME,
        )
        self.assertEqual(missing.reason_code, "PHASE_NOT_PRESENT")

    def test_08_request_feature_revision_raw_path_and_deterministic_digests(self) -> None:
        world = FakeWorld()
        context = _bind_fe(world)
        first = _request(context, ("LIQUID", "FCC_A1"))
        second = _request(context, ("LIQUID", "FCC_A1"))
        self.assertEqual(first, second)
        self.assertEqual(first, vl.FeatureRequest.from_json_bytes(first.to_json_bytes()))
        unknown = vl.prepare_feature_request("unknown", context, {}, (), clock=lambda: FIXED_TIME)
        self.assertEqual(unknown.reason_code, "FEATURE_ID_UNKNOWN")
        revision = vl.prepare_feature_request(
            "equilibrium_single", context, {}, (), feature_revision="2", clock=lambda: FIXED_TIME,
        )
        self.assertEqual(revision.reason_code, "FEATURE_REVISION_UNSUPPORTED")
        raw = vl.prepare_feature_request(
            "equilibrium_single", context, {"database_path": "C:/unsafe.tdb"}, (),
            clock=lambda: FIXED_TIME,
        )
        self.assertEqual(raw.reason_code, "RAW_PATH_REJECTED")
        self.assertEqual(raw.backend_calls, 0)

    def test_09_generation_stale_before_lease_and_during_backend(self) -> None:
        world = FakeWorld()
        context = _bind_fe(world)
        request = _request(context)
        vl.invalidate_binding_generation()
        self.assert_reason(vl.ReasonCode.GENERATION_STALE, vl.acquire_execution, request, DummyPaths())

        context = _bind_fe(FakeWorld())
        request = _request(context)
        lease = vl.acquire_execution(
            request, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: FIXED_NONCE,
        )
        with lease:
            self.assertEqual(lease.identity, vl.ExecutionLeaseIdentity.from_json_bytes(lease.identity.to_json_bytes()))

            def flip(_lease: vl.ExecutionLease) -> dict[str, bool]:
                vl.invalidate_binding_generation()
                return {"computed": True}

            self.assert_reason(vl.ReasonCode.GENERATION_STALE, lease.invoke_backend, flip)

    def test_10_fifo_two_request_lane_has_one_backend_at_a_time(self) -> None:
        context = _bind_fe(FakeWorld())
        request = _request(context)
        lock = threading.Lock()
        entered = threading.Event()
        release = threading.Event()
        order: list[str] = []
        active = 0
        maximum = 0
        errors: list[BaseException] = []

        def worker(name: str, nonce: str) -> None:
            nonlocal active, maximum
            try:
                with vl.acquire_execution(
                    request, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: nonce,
                ) as lease:
                    def backend(_lease: vl.ExecutionLease) -> str:
                        nonlocal active, maximum
                        with lock:
                            active += 1
                            maximum = max(maximum, active)
                            order.append(name + ":start")
                        if name == "first":
                            entered.set()
                            self.assertTrue(release.wait(3.0))
                        with lock:
                            order.append(name + ":end")
                            active -= 1
                        return name
                    self.assertEqual(lease.invoke_backend(backend), name)
            except BaseException as error:
                errors.append(error)

        first = threading.Thread(target=worker, args=("first", "1" * 32))
        second = threading.Thread(target=worker, args=("second", "2" * 32))
        first.start()
        self.assertTrue(entered.wait(3.0))
        second.start()
        time.sleep(0.05)
        release.set()
        first.join(3.0)
        second.join(3.0)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(maximum, 1)
        self.assertEqual(order, ["first:start", "first:end", "second:start", "second:end"])

    def test_11_in_memory_parser_cache_is_digest_revision_generation_scoped(self) -> None:
        def bind_verified_snapshot() -> vl.BoundDatabaseContext:
            catalog = vl.ArtifactCatalog.from_policy(
                ROOT,
                vl.canonical_release_manifest(),
                phase_provider=lambda _artifact: (
                    "LIQUID", "FCC_A1", "BCC_A2", "C15_LAVES",
                ),
            )
            return vl.bind_selected_database(
                {"database_key": "fe", "profile_key": "thermogar_patch"},
                catalog,
                DummyPaths(),
            )

        context = bind_verified_snapshot()
        request = _request(context)
        calls = 0

        def parser(stream) -> dict[str, int]:
            nonlocal calls
            calls += 1
            self.assertTrue(stream.read(1))
            return {"parse": calls}

        with vl.acquire_execution(
            request, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "3" * 32,
        ) as lease:
            self.assertIs(lease.parse_tdb(parser, "fake-parser-1"), lease.parse_tdb(parser, "fake-parser-1"))
        self.assertEqual(calls, 1)
        vl.invalidate_binding_generation()
        context = bind_verified_snapshot()
        request = _request(context)
        with vl.acquire_execution(
            request, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "4" * 32,
        ) as lease:
            self.assertEqual(lease.parse_tdb(parser, "fake-parser-1"), {"parse": 2})
        self.assertEqual(calls, 2)

    def test_12_materialization_seam_is_non_executable_and_path_free(self) -> None:
        context = _bind_fe(FakeWorld())
        request = _request(context)
        with vl.acquire_execution(
            request, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "5" * 32,
        ) as lease:
            error = self.assert_reason(vl.ReasonCode.CAPABILITY_UNAVAILABLE, lease.materialize_filename)
            self.assertIn("Wave B1", error.detail)
            self.assertNotIn("paths", vl.ExecutionLease.__slots__)

    def test_13_receipt_envelope_and_core1_bridge_codecs(self) -> None:
        context = _bind_fe(FakeWorld())
        request = _request(context)
        settings = {"temperature_k": 973.15}
        tables: list[dict[str, object]] = []
        figures: list[dict[str, object]] = []
        artifacts: list[dict[str, object]] = []
        result_digest = vl.canonical_digest(
            {
                "settings_digest": vl.canonical_digest(settings),
                "tables_digest": vl.canonical_digest(tables),
                "figures_digest": vl.canonical_digest(figures),
                "artifacts_digest": vl.canonical_digest(artifacts),
            }
        )
        with vl.acquire_execution(
            request, DummyPaths(), clock=lambda: FIXED_TIME, nonce_factory=lambda: "6" * 32,
        ) as lease:
            self.assertEqual(lease.invoke_backend(lambda _lease: {"ok": True}), {"ok": True})
            receipt = vl.make_feature_receipt(
                context, request, lease, outcome="success", reason_code=None, reason_detail=None,
                backend={
                    "adapter_id": "fake", "adapter_revision": "1",
                    "backend_id": "fake-backend", "backend_version": "1",
                },
                packages=[{"name": "fake", "version": "1", "status": "available"}],
                point_count=1, result_digest=result_digest,
                started_at_utc=FIXED_TIME, finished_at_utc=FIXED_TIME,
            )
        self.assertEqual(vl.FeatureReceipt.from_json_bytes(receipt.to_json_bytes()), receipt)
        envelope = vl.make_result_envelope(
            context, request, receipt, settings=settings, tables=tables, figures=figures,
            artifacts=artifacts, clock=lambda: FIXED_TIME,
        )
        self.assertEqual(vl.ResultEnvelope.from_json_bytes(envelope.to_json_bytes()), envelope)

        core1 = {
            "schema": "thermogar.restricted_fe.receipt.v2",
            "feature_id": "equilibrium_single",
            "context_digest": "0" * 64,
            "request_digest": "1" * 64,
            "ordered_phases": list(request.effective_phases),
            "ordered_phases_digest": vl.canonical_digest(list(request.effective_phases)),
            "source_hashes": [
                ["database_sha256", context.tdb.sha256],
                ["passport_sha256", context.passport.sha256],
            ],
            "calls": 1,
            "points": [{"call_index": 1, "phase_fractions": [["FCC_A1", 1.0]]}],
            "outcome": "success",
            "error_code": None,
            "material_base": "STEEL",
            "experimental_qualification": "NOT_PERFORMED",
        }
        bridge = vl.verified_core1_v2_evidence_bridge(core1, context, request)
        self.assertEqual(bridge["schema"], "thermogar.core1-v2-evidence-bridge.v1")
        self.assertEqual(bridge["core1_receipt"], core1)
        tampered = dict(core1)
        tampered["database_path"] = "C:/unsafe.tdb"
        self.assert_reason(
            vl.ReasonCode.RAW_PATH_REJECTED,
            vl.verified_core1_v2_evidence_bridge,
            tampered, context, request,
        )

    def test_14_static_dependency_and_deferred_path_boundary(self) -> None:
        source = (ROOT / "app" / "thermogar_verified_loaders.py").read_text(encoding="utf-8")
        for forbidden in (
            "import streamlit", "from streamlit", "import pycalphad", "from pycalphad",
            "import numpy", "from numpy", "import temp" + "file", "LOCAL" + "APPDATA",
            "THERMOGAR_STATE" + "_ROOT", "Path" + ".home", "PROJECT" + "_ROOT",
            "os" + ".environ",
            "shutil.copy", "copy2", "copyfile", "write_text(", "write_bytes(",
            "os.replace", "rmtree", "Database(", "PhysicalDensityDatabase(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("Filename materialization is deliberately non-executable", source)

    def test_16_component_candidates_narrow_policy_without_schema_change(self) -> None:
        context = _bind_fe(FakeWorld())
        decision = vl.prepare_feature_request(
            "equilibrium_single",
            context,
            {"pressure_pa": 101325.0, "temperature_k": 973.15},
            (),
            candidate_phases=("C15_LAVES", "FCC_A1", "LIQUID"),
            clock=lambda: FIXED_TIME,
        )
        self.assertIs(type(decision), vl.FeatureRequest)
        self.assertEqual(decision.effective_phases, ("FCC_A1", "LIQUID"))
        self.assertEqual(tuple(decision.to_dict()), vl.FEATURE_REQUEST_FIELDS)
        rejected = vl.prepare_feature_request(
            "equilibrium_single",
            context,
            {"pressure_pa": 101325.0, "temperature_k": 973.15},
            ("C15_LAVES",),
            candidate_phases=("C15_LAVES", "FCC_A1"),
            clock=lambda: FIXED_TIME,
        )
        self.assertIs(type(rejected), vl.RejectedFeatureReceipt)
        self.assertEqual(rejected.reason_code, "C15_PHASE_REJECTED")
        self.assertEqual(rejected.backend_calls, 0)
        invalid = vl.prepare_feature_request(
            "equilibrium_single",
            context,
            {"pressure_pa": 101325.0, "temperature_k": 973.15},
            (),
            candidate_phases=["FCC_A1"],
            clock=lambda: FIXED_TIME,
        )
        self.assertIs(type(invalid), vl.RejectedFeatureReceipt)
        self.assertEqual(invalid.reason_code, "PHASE_POLICY_MISMATCH")

    def test_17_fresh_tdb_parse_bypasses_cache_but_rehashes_and_rechecks(self) -> None:
        catalog = vl.ArtifactCatalog.from_policy(
            ROOT,
            vl.canonical_release_manifest(),
            phase_provider=lambda _artifact: (
                "BCC_A2", "C15_LAVES", "FCC_A1", "LIQUID",
            ),
        )
        context = vl.bind_selected_database(
            {"database_key": "fe", "profile_key": "thermogar_patch"},
            catalog,
            DummyPaths(),
        )
        decision = vl.prepare_feature_request(
            "equilibrium_single",
            context,
            {"pressure_pa": 101325.0, "temperature_k": 973.15},
            (),
            candidate_phases=("FCC_A1",),
            clock=lambda: FIXED_TIME,
        )
        self.assertIs(type(decision), vl.FeatureRequest)
        calls = 0

        def parser(stream) -> dict[str, int]:
            nonlocal calls
            calls += 1
            self.assertTrue(stream.read(1))
            return {"parse": calls}

        with vl.acquire_execution(
            decision,
            DummyPaths(),
            clock=lambda: FIXED_TIME,
            nonce_factory=lambda: "7" * 32,
        ) as lease:
            cached = lease.parse_tdb(parser, "b2-fresh-parser-1")
            self.assertIs(
                cached,
                lease.parse_tdb(parser, "b2-fresh-parser-1"),
            )
            first_fresh = lease.parse_tdb(
                parser,
                "b2-fresh-parser-1",
                fresh=True,
            )
            second_fresh = lease.parse_tdb(
                parser,
                "b2-fresh-parser-1",
                fresh=True,
            )
        self.assertEqual(calls, 3)
        self.assertEqual(cached, {"parse": 1})
        self.assertEqual(first_fresh, {"parse": 2})
        self.assertEqual(second_fresh, {"parse": 3})
        self.assertIsNot(first_fresh, second_fresh)

    def test_99_no_new_or_changed_python_cache(self) -> None:
        self.assertEqual(_pyc_manifest(), PYC_BEFORE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
