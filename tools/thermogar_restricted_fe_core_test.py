"""Pure verifier cards for the restricted Fe execution boundary."""
from __future__ import annotations

import atexit
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
import os
from pathlib import Path
import stat
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from thermogar_paths import ThermoGarPaths
from thermogar_secure_io import assert_plain_path


_PROCESS_TEMP_TEXT = os.environ.get("TEMP")
if not _PROCESS_TEMP_TEXT:
    raise RuntimeError("TEMP is required for the isolated Core1 test fixture.")
_FIXTURE_PARENT = Path(os.path.abspath(_PROCESS_TEMP_TEXT)).resolve(strict=True)
_FIXTURE_ROOT = Path(
    tempfile.mkdtemp(prefix="thermogar-restricted-fe-core-", dir=_FIXTURE_PARENT)
).resolve(strict=True)


def _validate_owned_fixture_location() -> None:
    parent = Path(os.path.abspath(_FIXTURE_PARENT))
    root = Path(os.path.abspath(_FIXTURE_ROOT))
    if root.parent != parent:
        raise RuntimeError("Core1 test fixture is not a direct child of its owner root.")
    if os.path.commonpath((str(parent), str(root))) != str(parent):
        raise RuntimeError("Core1 test fixture escaped its owner root.")


def _is_reparse(info: os.stat_result) -> bool:
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & reparse_attribute)


def _remove_plain_owned_tree(directory: Path) -> None:
    assert_plain_path(directory, leaf_must_be_directory=True)
    with os.scandir(directory) as iterator:
        entries = tuple(iterator)
    for entry in entries:
        child = Path(entry.path)
        info = entry.stat(follow_symlinks=False)
        if _is_reparse(info):
            raise RuntimeError(f"Refusing to clean a reparse fixture entry: {child}")
        if stat.S_ISDIR(info.st_mode):
            _remove_plain_owned_tree(child)
        elif stat.S_ISREG(info.st_mode):
            child.unlink()
        else:
            raise RuntimeError(f"Refusing to clean a non-regular fixture entry: {child}")
    directory.rmdir()


def _cleanup_owned_fixture() -> None:
    _validate_owned_fixture_location()
    try:
        _FIXTURE_ROOT.lstat()
    except FileNotFoundError:
        return
    assert_plain_path(_FIXTURE_PARENT, leaf_must_be_directory=True)
    assert_plain_path(_FIXTURE_ROOT, leaf_must_be_directory=True)
    _remove_plain_owned_tree(_FIXTURE_ROOT)
    try:
        _FIXTURE_ROOT.lstat()
    except FileNotFoundError:
        return
    raise RuntimeError(f"Core1 test fixture cleanup left residue: {_FIXTURE_ROOT}")


_validate_owned_fixture_location()
atexit.register(_cleanup_owned_fixture)
try:
    assert_plain_path(_FIXTURE_PARENT, leaf_must_be_directory=True)
    assert_plain_path(_FIXTURE_ROOT, leaf_must_be_directory=True)
    _TEST_PATHS = ThermoGarPaths(_FIXTURE_ROOT)
    _TEST_PATHS.configure_process_environment()

    import thermogar_restricted_fe_core as core
    import thermogar_verified_loaders as vl
    from thermogar_verified_artifact import VerifiedTextArtifact, duplicate_reject_json
except BaseException:
    try:
        _cleanup_owned_fixture()
    finally:
        atexit.unregister(_cleanup_owned_fixture)
    raise


VERIFIER_CARDS = (
    "pins_and_immutability",
    "fresh_verified_database",
    "c15_predispatch_denial",
    "serial_1_3_3",
    "receipt_envelope",
    "drift_invalidation",
    "failure_no_retry",
    "tamper_stop",
    "default_runner_shape_boundary",
    "b2_bound_equivalence",
    "b2_fresh_generation_lane",
)

FIXED_TIME = "2026-08-29T12:34:56.123456Z"


class DummyPaths:
    __slots__ = ()


class FakeDatabase:
    refstates = {
        "FE": {"mass": 55.845},
        "C": {"mass": 12.011},
        "CR": {"mass": 51.9961},
    }


def passport() -> dict[str, object]:
    return {
        "schema_version": 2,
        "profile_id": "mc_fe_v2062_thermogar_working",
        "patch_id": core.PATCH_ID,
        "working_profile": {
            "thermodynamic_plus_mobility_database": {
                "sha256": core.DATABASE_SHA256.upper(),
            }
        },
        "compatibility_patches": [
            {
                "patch_id": core.PATCH_ID,
                "phase": core.C15_PHASE,
                "applied": True,
                "matched_active_commands": 1,
            }
        ],
    }


@contextmanager
def fake_artifacts(_root: Path, _context: core.RestrictedFeContext):
    yield core._VerifiedArtifacts(
        database=VerifiedTextArtifact(
            text="$ fake tdb\n",
            sha256=core.DATABASE_SHA256,
            size=11,
        ),
        passport=passport(),
    )


def request(feature_id: str) -> core.RestrictedFeRequest:
    common = {
        "balance": "FE",
        "units": "wt",
        "composition_pct": {"C": 0.2},
        "pressure_pa": 101325.0,
        "requested_phases": ("BCC_B2", "LIQUID"),
    }
    if feature_id == "equilibrium_single":
        return core.make_restricted_fe_request(
            feature_id,
            temperatures_k=(973.15,),
            **common,
        )
    if feature_id == "equilibrium_temperature_scan":
        return core.make_restricted_fe_request(
            feature_id,
            temperatures_k=(873.15, 973.15, 1073.15),
            **common,
        )
    return core.make_restricted_fe_request(
        feature_id,
        temperatures_k=(973.15,),
        variable_element="CR",
        concentrations_pct=(0.0, 5.0, 10.0),
        **common,
    )


def bind_bound_request(
    feature_id: str,
) -> tuple[
    vl.BoundDatabaseContext,
    core.RestrictedFeRequest,
    vl.FeatureRequest,
]:
    vl.invalidate_binding_generation()
    catalog = vl.ArtifactCatalog.from_policy(
        ROOT,
        vl.canonical_release_manifest(),
        phase_provider=lambda _artifact: (
            "BCC_B2", "C15_LAVES", "LIQUID",
        ),
    )
    context = vl.bind_selected_database(
        {"database_key": "fe", "profile_key": "thermogar_patch"},
        catalog,
        DummyPaths(),
    )
    core_request = request(feature_id)
    decision = core.prepare_bound_restricted_fe_request(
        context,
        core_request,
        ("BCC_B2", "C15_LAVES", "LIQUID"),
        clock=lambda: FIXED_TIME,
    )
    if type(decision) is not vl.FeatureRequest:
        raise AssertionError(decision)
    return context, core_request, decision


class RestrictedFeCoreVerifierCards(unittest.TestCase):
    def execute(
        self,
        feature_id: str,
        runner=None,
    ) -> tuple[core.RestrictedFeReceipt, mock.Mock]:
        from_file = mock.Mock(return_value=FakeDatabase())
        selected_runner = runner or mock.Mock(return_value={"LIQUID": 1.0})
        with mock.patch.object(core, "_open_verified_artifacts", fake_artifacts), mock.patch.object(
            core.Database, "from_file", from_file
        ), mock.patch.object(
            core, "filter_phases", return_value=["LIQUID", "C15_LAVES", "BCC_B2"]
        ):
            receipt = core.execute_restricted_fe(
                ROOT,
                core.restricted_fe_context(),
                request(feature_id),
                runner=selected_runner,
            )
        return receipt, from_file

    def test_001_pins_types_and_duplicate_json_are_fail_closed(self) -> None:
        context = core.restricted_fe_context()
        self.assertEqual(context.database_key, "fe")
        self.assertEqual(context.profile_key, "thermogar_patch")
        self.assertEqual(context.database_sha256, core.DATABASE_SHA256)
        self.assertEqual(context.passport_sha256, core.PASSPORT_SHA256)
        self.assertEqual(context.patch_id, "TG-FE-2062-C15-001")
        with self.assertRaises(FrozenInstanceError):
            context.profile_key = "other"
        with self.assertRaises(core.RestrictedFeError):
            core.RestrictedFeContext(database_key="ni")
        with self.assertRaises(ValueError):
            duplicate_reject_json('{"a":1,"a":2}')

    def test_002_each_execution_parses_one_fresh_database_from_text(self) -> None:
        receipts = []
        from_file = mock.Mock(side_effect=[FakeDatabase(), FakeDatabase()])
        runner = mock.Mock(return_value={"LIQUID": 1.0})
        with mock.patch.object(core, "_open_verified_artifacts", fake_artifacts), mock.patch.object(
            core.Database, "from_file", from_file
        ), mock.patch.object(
            core, "filter_phases", return_value=["LIQUID", "C15_LAVES", "BCC_B2"]
        ):
            for _ in range(2):
                receipts.append(
                    core.execute_restricted_fe(
                        ROOT,
                        core.restricted_fe_context(),
                        request("equilibrium_single"),
                        runner=runner,
                    )
                )
        self.assertEqual(from_file.call_count, 2)
        for call in from_file.call_args_list:
            self.assertEqual(call.kwargs, {"fmt": "tdb"})
            self.assertEqual(call.args[0].read(), "$ fake tdb\n")
        self.assertTrue(all(receipt.outcome == "success" for receipt in receipts))

    def test_003_c15_is_denied_before_artifact_or_runner_dispatch(self) -> None:
        runner = mock.Mock()
        with self.assertRaises(core.RestrictedFeError):
            core.make_restricted_fe_request(
                "equilibrium_single",
                balance="FE",
                units="at",
                composition_pct={"C": 0.2},
                pressure_pa=101325.0,
                temperatures_k=(973.15,),
                requested_phases=("C15_LAVES",),
            )
        runner.assert_not_called()
        self.assertEqual(
            core.effective_phase_names(["C15_LAVES", "LIQUID", "BCC_B2"]),
            ("BCC_B2", "LIQUID"),
        )

    def test_004_runner_calls_are_strictly_serial_one_three_three(self) -> None:
        for feature_id, expected in (
            ("equilibrium_single", 1),
            ("equilibrium_temperature_scan", 3),
            ("equilibrium_composition_scan", 3),
        ):
            calls: list[int] = []

            def runner(_database, call):
                self.assertEqual(call.call_index, len(calls) + 1)
                self.assertNotIn("C15_LAVES", call.phases)
                calls.append(call.call_index)
                return {"LIQUID": 1.0}

            receipt, from_file = self.execute(feature_id, runner)
            self.assertEqual(calls, list(range(1, expected + 1)))
            self.assertEqual(receipt.calls, expected)
            self.assertEqual(len(receipt.points), expected)
            self.assertEqual(receipt.outcome, "success")
            self.assertEqual(from_file.call_count, 1)

    def test_005_receipt_has_digests_sources_and_neutral_metadata(self) -> None:
        receipt, _from_file = self.execute("equilibrium_temperature_scan")
        self.assertEqual(len(receipt.context_digest), 64)
        self.assertEqual(len(receipt.request_digest), 64)
        self.assertEqual(len(receipt.ordered_phases_digest), 64)
        self.assertEqual(receipt.ordered_phases, ("BCC_B2", "LIQUID"))
        self.assertEqual(
            dict(receipt.source_hashes),
            {
                "database_sha256": core.DATABASE_SHA256,
                "passport_sha256": core.PASSPORT_SHA256,
            },
        )
        self.assertEqual(receipt.material_base, "STEEL")
        self.assertEqual(
            receipt.experimental_qualification,
            "NOT_PERFORMED",
        )

    def test_006_fingerprint_retains_harmless_rerun_and_rejects_drift(self) -> None:
        original = request("equilibrium_single")
        context = core.restricted_fe_context()
        receipt, _from_file = self.execute("equilibrium_single")
        fingerprint = core.input_fingerprint(context, original)
        self.assertIs(
            core.retain_receipt_for_fingerprint(receipt, fingerprint, fingerprint),
            receipt,
        )
        variants = (
            replace(original, pressure_pa=101326.0),
            replace(original, temperatures_k=(974.15,)),
            replace(original, composition_pct=(("C", 0.3),)),
            replace(original, requested_phases=("LIQUID",)),
        )
        for changed in variants:
            self.assertIsNone(
                core.retain_receipt_for_fingerprint(
                    receipt,
                    fingerprint,
                    core.input_fingerprint(context, changed),
                )
            )

    def test_007_runner_failure_stops_without_retry_and_preserves_points(self) -> None:
        calls: list[int] = []

        def runner(_database, call):
            calls.append(call.call_index)
            if call.call_index == 2:
                raise RuntimeError("synthetic failure")
            return {"LIQUID": 1.0}

        receipt, _from_file = self.execute("equilibrium_temperature_scan", runner)
        self.assertEqual(calls, [1, 2])
        self.assertEqual(receipt.calls, 2)
        self.assertEqual(len(receipt.points), 1)
        self.assertEqual(receipt.outcome, "failure")
        self.assertEqual(receipt.error_code, "RuntimeError")

    def test_008_tampered_artifact_stops_before_database_and_runner(self) -> None:
        @contextmanager
        def tampered(_root, _context):
            raise RuntimeError("snapshot hash mismatch")
            yield

        runner = mock.Mock()
        from_file = mock.Mock()
        with mock.patch.object(core, "_open_verified_artifacts", tampered), mock.patch.object(
            core.Database, "from_file", from_file
        ):
            with self.assertRaisesRegex(RuntimeError, "hash mismatch"):
                core.execute_restricted_fe(
                    ROOT,
                    core.restricted_fe_context(),
                    request("equilibrium_single"),
                    runner=runner,
                )
        from_file.assert_not_called()
        runner.assert_not_called()

    def test_009_default_runner_canonicalizes_only_trusted_numpy_phase_keys(self) -> None:
        import numpy as np

        result = SimpleNamespace(
            Phase=SimpleNamespace(
                values=np.asarray(
                    [[[[["GRAPHITE", "BCC_B2", ""]]]]],
                    dtype=str,
                )
            ),
            NP=SimpleNamespace(
                values=np.asarray(
                    [[[[[0.008730034466287161, 0.9912699655338633, np.nan]]]]],
                    dtype=float,
                )
            ),
        )
        call = SimpleNamespace(
            atomic_fractions=(("C", 0.009223), ("FE", 0.990777)),
            pressure_pa=101325.0,
            temperature_k=973.15,
            balance="FE",
            components=("C", "FE", "VA"),
            phases=("BCC_B2", "GRAPHITE"),
        )
        with mock.patch("pycalphad.equilibrium", return_value=result):
            raw = core._default_runner(FakeDatabase(), call)

        self.assertEqual(set(raw), {"BCC_B2", "GRAPHITE"})
        self.assertTrue(all(type(phase) is str for phase in raw))
        self.assertEqual(
            core._validate_runner_result(raw, call.phases),
            (
                ("BCC_B2", 0.9912699655338633),
                ("GRAPHITE", 0.008730034466287161),
            ),
        )
        forged_external_shape = {
            np.str_("GRAPHITE"): 0.008730034466287161,
            np.str_("BCC_B2"): 0.9912699655338633,
        }
        with self.assertRaisesRegex(
            core.RestrictedFeError,
            "phase outside effective scope",
        ):
            core._validate_runner_result(forged_external_shape, call.phases)

        unequal = SimpleNamespace(
            Phase=SimpleNamespace(
                values=np.asarray([["GRAPHITE", "BCC_B2", ""]], dtype=str)
            ),
            NP=SimpleNamespace(
                values=np.asarray(
                    [[0.008730034466287161, 0.9912699655338633]],
                    dtype=float,
                )
            ),
        )
        with mock.patch("pycalphad.equilibrium", return_value=unequal):
            with self.assertRaisesRegex(
                core.RestrictedFeError,
                "Phase/NP cardinality mismatch",
            ):
                core._default_runner(FakeDatabase(), call)

    def test_010_default_runner_raw_rows_are_explicitly_fail_closed(self) -> None:
        import numpy as np

        call = SimpleNamespace(
            atomic_fractions=(("C", 0.009223), ("FE", 0.990777)),
            pressure_pa=101325.0,
            temperature_k=973.15,
            balance="FE",
            components=("C", "FE", "VA"),
            phases=("BCC_B2", "GRAPHITE"),
        )

        def default_result(phases, fractions):
            result = SimpleNamespace(
                Phase=SimpleNamespace(values=np.asarray(phases, dtype=str)),
                NP=SimpleNamespace(values=np.asarray(fractions, dtype=float)),
            )
            with mock.patch("pycalphad.equilibrium", return_value=result):
                return core._default_runner(FakeDatabase(), call)

        for label, fraction in (
            ("GRAPHITE", np.nan),
            ("GRAPHITE", np.inf),
            ("GRAPHITE", -0.1),
        ):
            with self.subTest(active_invalid=repr(fraction)):
                with self.assertRaisesRegex(
                    core.RestrictedFeError,
                    "invalid raw phase fraction",
                ):
                    default_result((label, "BCC_B2"), (fraction, 1.0))

        for label, fraction in (
            ("UNKNOWN_PHASE", 0.2),
            (core.C15_PHASE, 0.2),
            (core.C15_PHASE, 0.0),
        ):
            with self.subTest(out_of_scope=(label, fraction)):
                with self.assertRaisesRegex(
                    core.RestrictedFeError,
                    "phase outside effective scope",
                ):
                    default_result((label, "BCC_B2"), (fraction, 1.0))

        for fraction in (0.2, -0.1, np.inf):
            with self.subTest(unlabeled_invalid=repr(fraction)):
                with self.assertRaisesRegex(
                    core.RestrictedFeError,
                    "invalid unlabeled phase mass",
                ):
                    default_result(("", "BCC_B2"), (fraction, 1.0))

        for label, fraction in (
            ("GRAPHITE", 0.0),
            ("GRAPHITE", 1e-12),
            ("", np.nan),
            ("", 0.0),
            ("", 1e-12),
        ):
            with self.subTest(allowed_inactive=(label, repr(fraction))):
                raw = default_result((label, "BCC_B2"), (fraction, 1.0))
                self.assertEqual(raw, {"BCC_B2": 1.0})
                self.assertEqual(
                    core._validate_runner_result(raw, call.phases),
                    (("BCC_B2", 1.0),),
                )

    def test_011_zero_variable_composition_reaches_solver_as_native_zero(self) -> None:
        import numpy as np
        from pycalphad import variables as v

        result = SimpleNamespace(
            Phase=SimpleNamespace(
                values=np.asarray([["BCC_B2", ""]], dtype=str)
            ),
            NP=SimpleNamespace(
                values=np.asarray([[1.0, np.nan]], dtype=float)
            ),
        )
        captured: list[dict[object, float]] = []

        def equilibrium(
            _database,
            components,
            phases,
            conditions,
            *,
            calc_opts,
        ):
            self.assertEqual(components, ["C", "CR", "FE", "VA"])
            self.assertNotIn(core.C15_PHASE, phases)
            self.assertEqual(calc_opts, {"pdens": 500})
            captured.append(dict(conditions))
            return result

        from_file = mock.Mock(return_value=FakeDatabase())
        with mock.patch.object(
            core, "_open_verified_artifacts", fake_artifacts
        ), mock.patch.object(
            core.Database, "from_file", from_file
        ), mock.patch.object(
            core,
            "filter_phases",
            return_value=["BCC_B2", "C15_LAVES", "LIQUID"],
        ), mock.patch(
            "pycalphad.equilibrium", side_effect=equilibrium
        ):
            receipt = core.execute_restricted_fe(
                ROOT,
                core.restricted_fe_context(),
                request("equilibrium_composition_scan"),
            )

        self.assertEqual(len(captured), 3)
        self.assertEqual(receipt.calls, 3)
        self.assertEqual(len(receipt.points), 3)
        self.assertEqual(receipt.outcome, "success")
        self.assertEqual(
            [point.axis_value for point in receipt.points],
            [0.0, 5.0, 10.0],
        )
        cr = v.X("CR")
        cr_conditions = [conditions[cr] for conditions in captured]
        self.assertIs(type(cr_conditions[0]), float)
        self.assertEqual(cr_conditions[0], 0.0)
        self.assertGreater(cr_conditions[1], 0.0)
        self.assertGreater(cr_conditions[2], cr_conditions[1])
        for point, value in zip(receipt.points, cr_conditions):
            atomic = dict(point.atomic_fractions)
            self.assertIn("CR", atomic)
            self.assertIs(type(atomic["CR"]), float)
            self.assertEqual(atomic["CR"], value)

    def test_012_bound_bridge_matches_legacy_for_all_three_features(self) -> None:
        for feature_index, feature_id in enumerate(
            (
                "equilibrium_single",
                "equilibrium_temperature_scan",
                "equilibrium_composition_scan",
            ),
            start=1,
        ):
            with self.subTest(feature_id=feature_id):
                legacy, _legacy_parser = self.execute(feature_id)
                context, core_request, feature_request = bind_bound_request(
                    feature_id
                )
                parser = mock.Mock(return_value=FakeDatabase())
                runner_calls: list[core.RestrictedFeRunnerCall] = []

                def runner(_database, call):
                    runner_calls.append(call)
                    return {"LIQUID": 1.0}

                with mock.patch.object(
                    core.Database,
                    "from_file",
                    parser,
                ):
                    with vl.acquire_execution(
                        feature_request,
                        DummyPaths(),
                        clock=lambda: FIXED_TIME,
                        nonce_factory=lambda: f"{feature_index}" * 32,
                    ) as lease:
                        result = core.execute_bound_restricted_fe(
                            context,
                            feature_request,
                            core_request,
                            lease,
                            runner=runner,
                            clock=lambda: FIXED_TIME,
                        )

                self.assertEqual(parser.call_count, 1)
                self.assertEqual(
                    parser.call_args.kwargs,
                    {"fmt": "tdb"},
                )
                self.assertEqual(result.core1_receipt, legacy)
                self.assertEqual(
                    [call.call_index for call in runner_calls],
                    list(range(1, legacy.calls + 1)),
                )
                self.assertNotIn(
                    core.C15_PHASE,
                    result.core1_receipt.ordered_phases,
                )
                self.assertEqual(
                    result.feature_receipt.backend_calls,
                    legacy.calls,
                )
                self.assertEqual(
                    result.feature_receipt.request_digest,
                    feature_request.request_digest,
                )
                self.assertIsNotNone(result.result_envelope)
                bridge = result.result_envelope.settings[
                    "verified_core1_v2_evidence"
                ]
                self.assertEqual(
                    bridge["core1_receipt"],
                    core._core1_receipt_plain(legacy),
                )

    def test_013_bound_parse_is_fresh_per_execution_and_generation_is_live(self) -> None:
        context, core_request, feature_request = bind_bound_request(
            "equilibrium_single"
        )
        databases = [FakeDatabase(), FakeDatabase()]
        parser = mock.Mock(side_effect=databases)
        results = []
        with mock.patch.object(core.Database, "from_file", parser):
            for index in (4, 5):
                with vl.acquire_execution(
                    feature_request,
                    DummyPaths(),
                    clock=lambda: FIXED_TIME,
                    nonce_factory=lambda index=index: f"{index}" * 32,
                ) as lease:
                    results.append(
                        core.execute_bound_restricted_fe(
                            context,
                            feature_request,
                            core_request,
                            lease,
                            runner=lambda _database, _call: {"LIQUID": 1.0},
                            clock=lambda: FIXED_TIME,
                        )
                    )
        self.assertEqual(parser.call_count, 2)
        self.assertTrue(all(item.core1_receipt.outcome == "success" for item in results))
        vl.invalidate_binding_generation()
        with self.assertRaises(vl.VerifiedLoaderError) as caught:
            vl.acquire_execution(feature_request, DummyPaths())
        self.assertEqual(caught.exception.reason_code, vl.ReasonCode.GENERATION_STALE)

    def test_014_bound_failure_stops_without_retry_and_c15_never_leases(self) -> None:
        context, core_request, feature_request = bind_bound_request(
            "equilibrium_temperature_scan"
        )
        calls: list[int] = []

        def runner(_database, call):
            calls.append(call.call_index)
            if call.call_index == 2:
                raise RuntimeError("synthetic bound failure")
            return {"LIQUID": 1.0}

        with mock.patch.object(
            core.Database,
            "from_file",
            return_value=FakeDatabase(),
        ):
            with vl.acquire_execution(
                feature_request,
                DummyPaths(),
                clock=lambda: FIXED_TIME,
                nonce_factory=lambda: "6" * 32,
            ) as lease:
                result = core.execute_bound_restricted_fe(
                    context,
                    feature_request,
                    core_request,
                    lease,
                    runner=runner,
                    clock=lambda: FIXED_TIME,
                )
        self.assertEqual(calls, [1, 2])
        self.assertEqual(result.core1_receipt.calls, 2)
        self.assertEqual(len(result.core1_receipt.points), 1)
        self.assertEqual(result.core1_receipt.outcome, "failure")
        self.assertEqual(result.feature_receipt.reason_code, "BACKEND_FAILED")
        self.assertIsNone(result.result_envelope)

        safe = request("equilibrium_single")
        c15_inputs = core.restricted_fe_request_inputs(safe)
        c15_inputs["requested_phases"] = [core.C15_PHASE]
        rejected = vl.prepare_feature_request(
            safe.feature_id,
            context,
            c15_inputs,
            (core.C15_PHASE,),
            candidate_phases=("BCC_B2", core.C15_PHASE, "LIQUID"),
            clock=lambda: FIXED_TIME,
        )
        self.assertIs(type(rejected), vl.RejectedFeatureReceipt)
        self.assertEqual(rejected.reason_code, "C15_PHASE_REJECTED")
        self.assertEqual(rejected.backend_calls, 0)
        with self.assertRaises(vl.VerifiedLoaderError) as caught:
            vl.acquire_execution(rejected, DummyPaths())
        self.assertEqual(caught.exception.reason_code, vl.ReasonCode.SCHEMA_INVALID)

    def test_015_bound_composition_preserves_zero_cr_and_order(self) -> None:
        context, core_request, feature_request = bind_bound_request(
            "equilibrium_composition_scan"
        )
        calls: list[core.RestrictedFeRunnerCall] = []

        def runner(_database, call):
            calls.append(call)
            return {"LIQUID": 1.0}

        with mock.patch.object(
            core.Database,
            "from_file",
            return_value=FakeDatabase(),
        ):
            with vl.acquire_execution(
                feature_request,
                DummyPaths(),
                clock=lambda: FIXED_TIME,
                nonce_factory=lambda: "7" * 32,
            ) as lease:
                result = core.execute_bound_restricted_fe(
                    context,
                    feature_request,
                    core_request,
                    lease,
                    runner=runner,
                    clock=lambda: FIXED_TIME,
                )
        self.assertEqual([call.axis_value for call in calls], [0.0, 5.0, 10.0])
        self.assertEqual(result.core1_receipt.calls, 3)
        first_atomic = dict(calls[0].atomic_fractions)
        self.assertIn("CR", first_atomic)
        self.assertIs(type(first_atomic["CR"]), float)
        self.assertEqual(first_atomic["CR"], 0.0)
        self.assertEqual(calls[0].components, ("C", "CR", "FE", "VA"))


if __name__ == "__main__":
    try:
        _program = unittest.main(verbosity=2, exit=False)
    finally:
        try:
            _cleanup_owned_fixture()
        finally:
            atexit.unregister(_cleanup_owned_fixture)
    if _FIXTURE_ROOT.exists():
        raise RuntimeError(f"Core1 test fixture still exists: {_FIXTURE_ROOT}")
    raise SystemExit(0 if _program.result.wasSuccessful() else 1)
