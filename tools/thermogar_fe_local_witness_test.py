#!/usr/bin/env python3
"""Focused adversarial tests for the standalone Fe local witness S1."""

from __future__ import annotations

import ast
import inspect
import io
import json
import math
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import thermogar_fe_local_witness as service  # noqa: E402
import thermogar_fe_local_witness_backend as backend  # noqa: E402
import thermogar_fe_local_witness_receipts as receipts  # noqa: E402


def valid_mass_mapping(**changes: float) -> dict[str, float]:
    values = {element: 0.0 for element in receipts.MASS_ORDER}
    values["FE"] = 1.0
    for element, raw in changes.items():
        value = float(raw)
        if element != "FE":
            values["FE"] -= value
        values[element] = value
    return values


def copied_contract_root() -> tempfile.TemporaryDirectory[str]:
    holder: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory(
        prefix="thermogar_fe_witness_test_"
    )
    destination = Path(holder.name)
    config = json.loads(
        (ROOT / receipts.CONFIG_RELATIVE_PATH).read_text(encoding="utf-8")
    )
    relative_paths = [receipts.CONFIG_RELATIVE_PATH]
    relative_paths.extend(
        card["relative_path"] for card in config["profiles"].values()
    )
    relative_paths.extend(
        card["relative_path"] for card in config["pinned_inputs"].values()
    )
    for relative in relative_paths:
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return holder


class FakePreflight:
    def __init__(
        self,
        contract: receipts._WitnessContract,
        *,
        mass_element: str | None = None,
        raw_delta: str | None = None,
        eligible_delta: str | None = None,
        database_error: bool = False,
    ) -> None:
        self.contract = contract
        self.mass_element = mass_element
        self.raw_delta = raw_delta
        self.eligible_delta = eligible_delta
        self.database_error = database_error
        self.database_inputs: list[object] = []
        self.filter_components: list[tuple[str, ...]] = []
        self.filter_candidate_phases: list[object] = []

    def api(self) -> tuple[object, object]:
        owner = self

        class FakeDatabase:
            def __init__(self, source: object):
                owner.database_inputs.append(source)
                if owner.database_error:
                    raise RuntimeError("SECRET C:/raw/database/path")
                if not isinstance(source, io.StringIO):
                    raise AssertionError("Database input was not immutable StringIO")
                self.elements = set(receipts.DATABASE_ELEMENTS)
                masses = dict(owner.contract.observed_atomic_masses)
                if owner.mass_element is not None:
                    masses[owner.mass_element] += 0.001
                self.refstates = {
                    element: {"mass": masses[element]}
                    for element in receipts.MASS_ORDER
                }
                raw = list(owner.contract.eligible_phases) + ["BCC_A2"]
                if owner.raw_delta == "DROP":
                    raw.pop()
                elif owner.raw_delta == "DUPLICATE":
                    raw[-1] = raw[0]
                self.phases = {name: object() for name in raw}

        def fake_filter(
            database: object,
            components: list[str],
            candidate_phases: object = None,
        ) -> list[str]:
            del database
            owner.filter_components.append(tuple(components))
            owner.filter_candidate_phases.append(candidate_phases)
            values = list(owner.contract.eligible_phases)
            if owner.eligible_delta == "DROP_C15":
                values.remove("C15_LAVES")
            elif owner.eligible_delta == "DROP_LIQUID":
                values.remove("LIQUID")
            elif owner.eligible_delta == "DUPLICATE":
                values[-1] = values[0]
            return values

        return FakeDatabase, fake_filter


class FeLocalWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = receipts._load_witness_contract(ROOT)
        cls.mass = valid_mass_mapping(C=0.002, CR=0.115)

    def run_fake(
        self,
        profile: str = "thermogar_patch",
        **fake_options: object,
    ) -> tuple[service.LocalFeWitnessResult, FakePreflight]:
        fake = FakePreflight(self.contract, **fake_options)
        with mock.patch.object(backend, "_load_preflight_api", fake.api):
            result = service.run_local_fe_witness(profile, dict(self.mass), 1000.0)
        return result, fake

    def assert_safety(self, value: object) -> None:
        if isinstance(value, dict):
            if "receipt_kind" in value:
                self.assertEqual(
                    value["claim"],
                    "LOCAL_INTERNAL_DIAGNOSTIC_NOT_NE04_RELEASE",
                )
                self.assertIs(value["acceptance"], False)
                self.assertIs(value["execution_eligible"], False)
                self.assertIs(value["release_eligible"], False)
                self.assertEqual(value["production_use"], "DENIED")
            for nested in value.values():
                self.assert_safety(nested)
        elif isinstance(value, list):
            for nested in value:
                self.assert_safety(nested)

    def test_exact_public_api_and_module_surface(self) -> None:
        signature = inspect.signature(service.run_local_fe_witness)
        self.assertEqual(
            tuple(signature.parameters),
            ("profile_id", "mass_fractions", "temperature_k"),
        )
        self.assertTrue(
            all(
                parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
                and parameter.default is inspect.Parameter.empty
                for parameter in signature.parameters.values()
            )
        )
        self.assertEqual(
            service.__all__,
            [
                "LocalFeWitnessError",
                "LocalFeWitnessResult",
                "run_local_fe_witness",
            ],
        )
        self.assertFalse(hasattr(receipts, "__all__"))
        self.assertFalse(hasattr(backend, "__all__"))
        for forbidden in (
            "path",
            "sha256",
            "pressure_pa",
            "phases",
            "components",
            "backend",
            "callback",
            "options",
            "serializer",
        ):
            with self.assertRaises(TypeError):
                service.run_local_fe_witness(
                    "thermogar_patch",
                    dict(self.mass),
                    1000.0,
                    **{forbidden: object()},
                )
        with self.assertRaises(TypeError):
            service.LocalFeWitnessResult(execution_eligible=True)  # type: ignore[call-arg]

    def test_prepared_receipt_both_profiles_and_path_free(self) -> None:
        for profile in receipts.PROFILE_KEYS:
            with self.subTest(profile=profile):
                result, fake = self.run_fake(profile)
                self.assertIsNotNone(result.prepared)
                self.assertIsNone(result.failure)
                self.assertEqual(result.pre.stage, "PRE")
                self.assertEqual(result.post.stage, "POST_PREPARATION")
                self.assertEqual(
                    result.post.terminal_state,
                    "PREPARED_NOT_EXECUTED",
                )
                self.assertEqual(len(fake.database_inputs), 1)
                self.assertIsInstance(fake.database_inputs[0], io.StringIO)
                self.assertEqual(
                    fake.filter_components,
                    [receipts.SOLVER_COMPONENTS],
                )
                self.assertEqual(fake.filter_candidate_phases, [None])
                prepared = result.prepared
                assert prepared is not None
                self.assertEqual(len(prepared.atomic_masses), 25)
                self.assertEqual(len(prepared.derived_mole_fractions), 25)
                self.assertEqual(
                    tuple(name for name, _value in prepared.derived_mole_fractions),
                    receipts.MASS_ORDER,
                )
                self.assertNotIn("VA", dict(prepared.derived_mole_fractions))
                self.assertEqual(receipts.SOLVER_COMPONENTS[-2:], ("FE", "VA"))
                self.assertLessEqual(prepared.max_round_trip_abs_error, 1e-12)
                outward = result.as_dict()
                self.assertEqual(outward["outcome"], "PREPARED_NOT_EXECUTED")
                self.assertIs(outward["real_equilibrium_executed"], False)
                self.assertEqual(outward["pressure_domain_status"], "UNKNOWN_BLOCKED")
                self.assert_safety(outward)
                serialized = json.dumps(outward, sort_keys=True)
                self.assertNotIn("relative_path", serialized)
                self.assertNotIn("snapshot_path", serialized)
                self.assertNotIn(str(ROOT), serialized)

    def test_phase_and_mass_mutations_fail_closed(self) -> None:
        cases = (
            {"mass_element": "FE"},
            {"raw_delta": "DROP"},
            {"raw_delta": "DUPLICATE"},
            {"eligible_delta": "DROP_C15"},
            {"eligible_delta": "DROP_LIQUID"},
            {"eligible_delta": "DUPLICATE"},
        )
        for options in cases:
            with self.subTest(options=options):
                result, _fake = self.run_fake(**options)
                self.assertIsNone(result.prepared)
                self.assertIsNotNone(result.failure)
                self.assertEqual(result.post.stage, "POST_FAILURE")
                self.assertEqual(result.post.terminal_state, "FAILED")
                outward = result.as_dict()
                self.assertEqual(outward["outcome"], "PREPARATION_FAILED")
                self.assertIs(outward["real_equilibrium_executed"], False)

    def test_backend_exception_is_redacted(self) -> None:
        result, _fake = self.run_fake(database_error=True)
        self.assertIsNone(result.prepared)
        assert result.failure is not None
        outward = result.as_dict()
        self.assertEqual(
            result.failure.failure_code,
            "FE_LOCAL_WITNESS_DATABASE_LOAD_FAILED",
        )
        self.assertNotIn("SECRET", json.dumps(outward))
        self.assertNotIn("C:/raw", json.dumps(outward))

    def test_public_errors_have_no_cause_or_path_leak(self) -> None:
        with self.assertRaises(service.LocalFeWitnessError) as invalid:
            service.run_local_fe_witness(
                "thermogar_patch",
                {"FE": 1.0},
                1000.0,
            )
        self.assertIsNone(invalid.exception.__cause__)
        self.assertIsNone(invalid.exception.__context__)

        fake = FakePreflight(self.contract)
        with (
            mock.patch.object(backend, "_load_preflight_api", fake.api),
            mock.patch.object(
                receipts.shutil,
                "rmtree",
                side_effect=OSError("SECRET C:/snapshot/path"),
            ),
            self.assertRaises(service.LocalFeWitnessError) as cleanup,
        ):
            service.run_local_fe_witness(
                "thermogar_patch", dict(self.mass), 1000.0
            )
        self.assertIsNone(cleanup.exception.__cause__)
        self.assertIsNone(cleanup.exception.__context__)
        self.assertNotIn("SECRET", str(cleanup.exception))
        self.assertNotIn("C:/snapshot", str(cleanup.exception))

    def test_legacy_wave2b_files_are_not_runtime_dependencies(self) -> None:
        roles = tuple(identity.role for identity in self.contract.pinned_inputs)
        self.assertNotIn("wave2b_direct_reference", roles)
        self.assertNotIn("wave2b_direct_test", roles)
        holder = copied_contract_root()
        try:
            temporary_root = Path(holder.name)
            self.assertFalse(
                (temporary_root / "app" / "thermogar_wave2b_direct.py").exists()
            )
            fake = FakePreflight(self.contract)
            with (
                mock.patch.object(service, "_PROJECT_ROOT", temporary_root),
                mock.patch.object(backend, "_load_preflight_api", fake.api),
            ):
                result = service.run_local_fe_witness(
                    "thermogar_patch", dict(self.mass), 1000.0
                )
            self.assertIsNotNone(result.prepared)
        finally:
            holder.cleanup()

    def test_strict_source_bounds_all_24_elements(self) -> None:
        for element, upper_wt in receipts.STRICT_UPPER_BOUNDS_WT_PERCENT.items():
            limit = upper_wt * 0.01
            epsilon = min(1e-12, limit / 1000.0)
            with self.subTest(element=element, point="below"):
                canonical = receipts._canonicalize_mass_fraction_mapping(
                    valid_mass_mapping(**{element: limit - epsilon})
                )
                self.assertGreater(dict(canonical)["FE"], 0.0)
            for point in (limit, limit + epsilon):
                with self.subTest(element=element, point=point):
                    with self.assertRaises(receipts.WitnessContractError):
                        receipts._canonicalize_mass_fraction_mapping(
                            valid_mass_mapping(**{element: point})
                        )

    def test_mapping_input_adversarial_cases(self) -> None:
        bad: list[object] = []
        bad.append(tuple(self.mass.items()))
        missing = dict(self.mass)
        missing.pop("Y")
        bad.append(missing)
        unknown = dict(self.mass)
        unknown["ZZ"] = unknown.pop("Y")
        bad.append(unknown)
        vacancy = dict(self.mass)
        vacancy["VA"] = vacancy.pop("Y")
        bad.append(vacancy)
        for element, value in (
            ("C", float("nan")),
            ("C", float("inf")),
            ("C", -0.001),
            ("C", True),
        ):
            changed = dict(self.mass)
            changed[element] = value
            bad.append(changed)
        simplex = dict(self.mass)
        simplex["FE"] -= 0.1
        bad.append(simplex)
        zero_fe = valid_mass_mapping(C=1.0)
        bad.append(zero_fe)
        for value in bad:
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(service.LocalFeWitnessError) as captured:
                    service.run_local_fe_witness(
                        "thermogar_patch", value, 1000.0  # type: ignore[arg-type]
                    )
                self.assertEqual(
                    captured.exception.code,
                    "FE_LOCAL_WITNESS_COMPOSITION_INVALID",
                )

    def test_temperature_and_profile_boundaries(self) -> None:
        fake = FakePreflight(self.contract)
        with mock.patch.object(backend, "_load_preflight_api", fake.api):
            for point in (673.0, 2000.0):
                result = service.run_local_fe_witness(
                    "thermogar_patch", dict(self.mass), point
                )
                self.assertIsNotNone(result.prepared)
        for point in (672.999, 2000.001, float("nan"), float("inf"), True):
            with self.subTest(point=point):
                with self.assertRaises(service.LocalFeWitnessError):
                    service.run_local_fe_witness(
                        "thermogar_patch", dict(self.mass), point  # type: ignore[arg-type]
                    )
        with self.assertRaises(service.LocalFeWitnessError):
            service.run_local_fe_witness("unknown", dict(self.mass), 1000.0)

    def test_lease_exact_lifecycle_and_replay(self) -> None:
        contract, profile = receipts._load_profile_receipt(
            ROOT, "thermogar_patch"
        )
        composition = receipts._canonicalize_mass_fraction_mapping(self.mass)
        request = receipts.RequestReceipt("thermogar_patch", 1000.0, composition)
        domain = receipts._build_domain_receipt(
            contract, "thermogar_patch", 1000.0, composition
        )
        lease = receipts._open_local_witness_lease(
            ROOT, contract, profile, request, domain
        )
        self.assertFalse(hasattr(lease, "mark_executed"))
        with lease:
            pre = lease._preparation_rehash()
            with self.assertRaises(receipts.WitnessContractError):
                lease._post_rehash(pre)
            lease._mark_prepared_not_executed()
            with self.assertRaises(receipts.WitnessContractError):
                lease._mark_prepared_not_executed()
            post = lease._post_rehash(pre)
            self.assertEqual(post.stage, "POST_PREPARATION")
            with self.assertRaises(receipts.WitnessContractError):
                lease._post_rehash(pre)
        with self.assertRaises(receipts.WitnessContractError):
            with lease:
                pass

    def test_exception_exit_without_post_is_rejected(self) -> None:
        contract, profile = receipts._load_profile_receipt(
            ROOT, "thermogar_patch"
        )
        composition = receipts._canonicalize_mass_fraction_mapping(self.mass)
        request = receipts.RequestReceipt("thermogar_patch", 1000.0, composition)
        domain = receipts._build_domain_receipt(
            contract, "thermogar_patch", 1000.0, composition
        )
        lease = receipts._open_local_witness_lease(
            ROOT, contract, profile, request, domain
        )
        with self.assertRaisesRegex(
            receipts.WitnessContractError, "without terminal POST"
        ):
            with lease:
                lease._preparation_rehash()
                raise RuntimeError("attempted escape")

    def test_snapshot_same_size_tamper_is_rejected(self) -> None:
        contract, profile = receipts._load_profile_receipt(
            ROOT, "thermogar_patch"
        )
        composition = receipts._canonicalize_mass_fraction_mapping(self.mass)
        request = receipts.RequestReceipt("thermogar_patch", 1000.0, composition)
        domain = receipts._build_domain_receipt(
            contract, "thermogar_patch", 1000.0, composition
        )
        lease = receipts._open_local_witness_lease(
            ROOT, contract, profile, request, domain
        )
        lease.__enter__()
        lease._preparation_rehash()
        snapshot = next(iter(lease._snapshot_paths.values()))
        os.chmod(snapshot, stat.S_IREAD | stat.S_IWRITE)
        with snapshot.open("r+b") as target:
            first = target.read(1)
            target.seek(0)
            target.write(b"!" if first != b"!" else b"?")
        with self.assertRaises(receipts.WitnessContractError):
            lease._mark_failed()
        with self.assertRaises(receipts.WitnessContractError):
            lease.__exit__(RuntimeError, RuntimeError("tamper"), None)

    def test_same_size_source_tamper_and_symlink_rejected(self) -> None:
        holder = copied_contract_root()
        try:
            temporary_root = Path(holder.name)
            runtime_relative = self.contract.profile("thermogar_patch").runtime.relative_path
            runtime = temporary_root / runtime_relative
            with runtime.open("r+b") as target:
                first = target.read(1)
                target.seek(0)
                target.write(b"!" if first != b"!" else b"?")
            with mock.patch.object(service, "_PROJECT_ROOT", temporary_root):
                with self.assertRaises(service.LocalFeWitnessError):
                    service.run_local_fe_witness(
                        "thermogar_patch", dict(self.mass), 1000.0
                    )
        finally:
            holder.cleanup()

        holder = copied_contract_root()
        try:
            temporary_root = Path(holder.name)
            runtime_relative = self.contract.profile("thermogar_patch").runtime.relative_path
            runtime = temporary_root / runtime_relative
            runtime.unlink()
            try:
                os.symlink(ROOT / runtime_relative, runtime)
            except OSError as error:
                self.skipTest(f"symlink privilege unavailable: {error}")
            with self.assertRaises(receipts.WitnessContractError):
                receipts._load_witness_contract(temporary_root)
        finally:
            holder.cleanup()

    def test_safety_literals_and_low_level_mutation(self) -> None:
        result, _fake = self.run_fake()
        outward = result.as_dict()
        self.assert_safety(outward)
        overridden = receipts._safety_envelope(
            "SAFE",
            {
                "receipt_kind": "FORGED",
                "claim": "FORGED",
                "acceptance": True,
                "execution_eligible": True,
                "release_eligible": True,
                "production_use": "ALLOWED",
            },
        )
        self.assertEqual(overridden["receipt_kind"], "SAFE")
        self.assertIs(overridden["acceptance"], False)
        self.assertIs(overridden["execution_eligible"], False)
        self.assertIs(overridden["release_eligible"], False)
        self.assertEqual(overridden["production_use"], "DENIED")

        service.LocalFeWitnessResult.execution_eligible = True
        try:
            self.assertIs(result.as_dict()["execution_eligible"], False)
        finally:
            del service.LocalFeWitnessResult.execution_eligible

        assert result.prepared is not None
        object.__setattr__(result.prepared, "raw_phase_count", 999)
        with self.assertRaises(
            (receipts.WitnessContractError, service.LocalFeWitnessError)
        ):
            result.as_dict()

    def test_no_solver_call_and_database_consumes_stringio(self) -> None:
        backend_source = (APP / "thermogar_fe_local_witness_backend.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(backend_source)
        imported_names = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertNotIn("equilibrium", imported_names)
        self.assertNotIn("_PRIVATE_SOLVER_BOUNDARY", backend_source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        self.assertFalse(
            any(
                isinstance(node.func, ast.Name) and node.func.id == "equilibrium"
                for node in calls
            )
        )
        database_calls = [
            node
            for node in calls
            if isinstance(node.func, ast.Name) and node.func.id == "Database"
        ]
        self.assertEqual(len(database_calls), 1)
        argument = database_calls[0].args[0]
        self.assertIsInstance(argument, ast.Call)
        self.assertIsInstance(argument.func, ast.Attribute)
        self.assertEqual(argument.func.attr, "StringIO")

    def test_duplicate_json_and_safety_path_rules(self) -> None:
        with self.assertRaises(receipts.DuplicateJsonKeyError):
            json.loads('{"a":1,"a":2}', object_pairs_hook=receipts._strict_object)
        for bad in ("../x", "/x", "x\\y", "C:/x", "./x", "x/../y"):
            with self.subTest(bad=bad):
                with self.assertRaises(receipts.WitnessContractError):
                    receipts._relative_parts(bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
