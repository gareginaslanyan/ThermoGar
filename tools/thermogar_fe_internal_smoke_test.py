"""Focused unit tests for the internal Fe smoke harness (no equilibrium run)."""
from __future__ import annotations

import hashlib
import json
import numpy as np
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import thermogar_fe_internal_smoke as smoke


class ThermoGarFeInternalSmokeTests(unittest.TestCase):
    def valid_worker(
        self,
        profile: str,
        temperature: float,
        *,
        liquid: float = 1.0,
        c15: float = 0.0,
    ) -> dict[str, object]:
        stable: dict[str, float] = {}
        if liquid > 0.0:
            stable["LIQUID"] = liquid
        if c15 > 0.0:
            stable["C15_LAVES"] = c15
        return {
            "schema": smoke.WORKER_SCHEMA,
            **smoke._worker_identity(PROJECT_ROOT, profile),
            "point": {
                "temperature_k": temperature,
                "pressure_pa": smoke.PRESSURE_PA,
                "stable_phase_fractions": stable,
                "liquid_fraction": liquid,
                "c15_laves_fraction": c15,
                "patched_assertions": {
                    "liquid_gte_0_999999": liquid >= smoke.LIQUID_MINIMUM,
                    "c15_laves_lte_1e-8": c15 <= smoke.C15_LAVES_MAXIMUM,
                },
            },
        }

    def valid_profile(
        self,
        profile: str,
        *,
        liquid: float = 1.0,
        c15: float = 0.0,
    ) -> dict[str, object]:
        workers = [
            self.valid_worker(profile, temperature, liquid=liquid, c15=c15)
            for temperature in smoke.TEMPERATURES_K
        ]
        return {
            "schema": smoke.PROFILE_SCHEMA,
            **smoke._worker_identity(PROJECT_ROOT, profile),
            "complete": True,
            "points": [worker["point"] for worker in workers],
        }

    def test_witness_scope_and_atomic_pin(self) -> None:
        weights = smoke.witness_weights()
        self.assertAlmostEqual(sum(weights.values()), 100.0)
        self.assertEqual(weights["FE"], 84.875)
        self.assertEqual(tuple(sorted(weights)) + ("VA",), smoke.EXPECTED_COMPONENTS)
        self.assertAlmostEqual(
            sum(dict(smoke.EXPECTED_WITNESS_ATOMIC_FRACTIONS).values()), 1.0
        )

    def test_weight_to_atomic_conversion_closes(self) -> None:
        atomic = smoke.wt_pct_to_atomic_fractions(
            {"FE": 90.0, "C": 10.0}, {"FE": 55.845, "C": 12.011}
        )
        self.assertAlmostEqual(sum(atomic.values()), 1.0)
        self.assertGreater(atomic["C"], 0.10)

    def test_aggregate_uses_builtin_phase_keys_and_validates_receipt(self) -> None:
        equilibrium_result = SimpleNamespace(
            Phase=SimpleNamespace(
                values=np.array(["LIQUID", "LIQUID", "", "C15_LAVES"], dtype=str)
            ),
            NP=SimpleNamespace(values=np.array([0.4, 0.2, float("nan"), 0.4])),
        )
        stable = smoke.aggregate_phase_fractions(equilibrium_result)
        self.assertEqual(stable, {"C15_LAVES": 0.4, "LIQUID": 0.6000000000000001})
        self.assertTrue(all(type(phase) is str for phase in stable))
        self.assertNotIn("", stable)

        payload = self.valid_worker(
            "patched", 1800.0, liquid=stable["LIQUID"], c15=stable["C15_LAVES"]
        )
        payload["point"]["stable_phase_fractions"] = stable
        rebuilt = smoke.validate_worker_receipt(
            PROJECT_ROOT, "patched", 1800.0, payload
        )
        self.assertEqual(rebuilt["point"]["stable_phase_fractions"], stable)

    def test_full_phase_pin_keeps_liquid_and_c15(self) -> None:
        phases = smoke.EXPECTED_ELIGIBLE_PHASES
        self.assertEqual(phases, tuple(sorted(set(phases))))
        self.assertIn("LIQUID", phases)
        self.assertIn("C15_LAVES", phases)

    def test_identity_verification_is_pinned_and_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = Path("profiles/patched.tdb")
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(b"pinned")
            original = smoke.PROFILES["patched"]
            smoke.PROFILES["patched"] = {
                "relative_path": relative,
                "sha256": hashlib.sha256(b"pinned").hexdigest().upper(),
                "role": "test",
            }
            try:
                self.assertEqual(smoke.verify_profile_identity(root, "patched"), path.resolve())
                path.write_bytes(b"changed")
                with self.assertRaises(RuntimeError):
                    smoke.verify_profile_identity(root, "patched")
            finally:
                smoke.PROFILES["patched"] = original

    def test_only_exact_fixed_temperatures_are_accepted(self) -> None:
        for temperature in smoke.TEMPERATURES_K:
            self.assertEqual(smoke._fixed_temperature(temperature), temperature)
        for invalid in (1799.0, 1800.5, float("nan"), True, "1800"):
            with self.assertRaises(ValueError):
                smoke._fixed_temperature(invalid)

    def test_patched_rejects_empty_partial_duplicate_and_false_gate(self) -> None:
        valid = self.valid_profile("patched")
        self.assertTrue(smoke.patched_profile_passed(valid, PROJECT_ROOT))
        for forged in (
            {**valid, "points": []},
            {**valid, "points": valid["points"][:2]},
            {**valid, "complete": False},
            {**valid, "points": [valid["points"][0]] * 3},
        ):
            self.assertFalse(smoke.patched_profile_passed(forged, PROJECT_ROOT))
        false_gate = self.valid_profile("patched", liquid=0.999998, c15=0.000002)
        self.assertFalse(smoke.patched_profile_passed(false_gate, PROJECT_ROOT))

    def test_worker_rejects_schema_and_identity_forgery(self) -> None:
        valid = self.valid_worker("patched", 1800.0)
        smoke.validate_worker_receipt(PROJECT_ROOT, "patched", 1800.0, valid)
        for key, replacement in (
            ("schema", "arbitrary"),
            ("profile", "upstream"),
            ("database_sha256", "0" * 64),
            ("eligible_phases", ["LIQUID", "C15_LAVES"]),
        ):
            forged = dict(valid)
            forged[key] = replacement
            with self.assertRaises(RuntimeError):
                smoke.validate_worker_receipt(PROJECT_ROOT, "patched", 1800.0, forged)

    def test_worker_rejects_point_and_gate_forgery(self) -> None:
        valid = self.valid_worker("patched", 1800.0)
        for point in (
            {**valid["point"], "pressure_pa": 101324.0},
            {**valid["point"], "temperature_k": 1900.0},
            {**valid["point"], "liquid_fraction": 0.5},
            {
                **valid["point"],
                "patched_assertions": {
                    "liquid_gte_0_999999": False,
                    "c15_laves_lte_1e-8": True,
                },
            },
        ):
            with self.assertRaises(RuntimeError):
                smoke.validate_worker_receipt(
                    PROJECT_ROOT, "patched", 1800.0, {**valid, "point": point}
                )

    def test_upstream_is_strictly_validated_and_never_accepted(self) -> None:
        upstream = self.valid_profile("upstream", liquid=0.5, c15=0.5)
        self.assertEqual(
            smoke.upstream_diagnostic_interpretation(upstream, PROJECT_ROOT),
            "EXPECTED_DIAGNOSTIC_SYMPTOM_OBSERVED",
        )
        with self.assertRaises(RuntimeError):
            smoke.upstream_diagnostic_interpretation({"points": []}, PROJECT_ROOT)

    def test_parent_launches_one_temperature_with_90_second_limit(self) -> None:
        payload = self.valid_worker("patched", 1800.0)
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(payload), stderr=""
        )
        with patch.object(smoke, "verify_profile_identity"), patch.object(
            smoke.subprocess, "run", return_value=completed
        ) as run_mock:
            observed = smoke.evaluate_profile_in_worker(PROJECT_ROOT, "patched", 1800.0)
        self.assertEqual(observed["point"]["temperature_k"], 1800.0)
        command = run_mock.call_args.args[0]
        self.assertEqual(command.count("--temperature-k"), 1)
        self.assertEqual(command[command.index("--temperature-k") + 1], "1800.0")
        self.assertEqual(run_mock.call_args.kwargs["timeout"], 90.0)
        self.assertEqual(command[1:5], ["-I", "-B", "-X", "utf8"])

    def test_timeout_and_native_exit_fail_closed(self) -> None:
        with patch.object(smoke, "verify_profile_identity"), patch.object(
            smoke.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["python"], 90.0),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out after 90 seconds"):
                smoke.evaluate_profile_in_worker(PROJECT_ROOT, "patched", 1800.0)
        failed = SimpleNamespace(returncode=3221225477, stdout="", stderr="native exit")
        with patch.object(smoke, "verify_profile_identity"), patch.object(
            smoke.subprocess, "run", return_value=failed
        ):
            with self.assertRaisesRegex(RuntimeError, "3221225477"):
                smoke.evaluate_profile_in_worker(PROJECT_ROOT, "patched", 1800.0)

    def test_run_uses_sequential_one_temperature_workers(self) -> None:
        calls: list[tuple[str, float]] = []

        def worker(root: Path, profile: str, temperature: float) -> dict[str, object]:
            calls.append((profile, temperature))
            if profile == "patched":
                return self.valid_worker(profile, temperature)
            return self.valid_worker(profile, temperature, liquid=0.5, c15=0.5)

        with patch.object(smoke, "evaluate_profile_in_worker", side_effect=worker):
            receipt = smoke.run(PROJECT_ROOT)
        self.assertEqual(
            calls,
            [("patched", temperature) for temperature in smoke.TEMPERATURES_K]
            + [("upstream", temperature) for temperature in smoke.TEMPERATURES_K],
        )
        self.assertTrue(receipt["passed"])
        self.assertFalse(receipt["profiles"]["upstream"]["accepted_output"])

    def test_run_stops_after_native_error_and_preserves_prior_point(self) -> None:
        calls: list[tuple[str, float]] = []

        def worker(root: Path, profile: str, temperature: float) -> dict[str, object]:
            calls.append((profile, temperature))
            if temperature == 1900.0:
                raise RuntimeError("native termination")
            return self.valid_worker(profile, temperature)

        with patch.object(smoke, "evaluate_profile_in_worker", side_effect=worker):
            receipt = smoke.run(PROJECT_ROOT)
        self.assertEqual(calls, [("patched", 1800.0), ("patched", 1900.0)])
        self.assertFalse(receipt["passed"])
        self.assertFalse(receipt["profiles"]["patched"]["complete"])
        self.assertEqual(len(receipt["profiles"]["patched"]["points"]), 1)
        self.assertEqual(
            receipt["upstream_diagnostic_status"], "NOT_RUN_PATCHED_WORKER_ERROR"
        )

    def test_arbitrary_child_json_stops_before_next_worker(self) -> None:
        with patch.object(smoke, "evaluate_profile_in_worker", return_value={}) as worker:
            receipt = smoke.run(PROJECT_ROOT)
        self.assertEqual(worker.call_count, 1)
        self.assertFalse(receipt["passed"])
        self.assertIn("schema mismatch", receipt["patched_error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
