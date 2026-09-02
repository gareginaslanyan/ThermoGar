"""Focused non-equilibrium tests for the S2 Fe witness."""

from __future__ import annotations

import ast
import base64
import hashlib
import importlib.util
import inspect
import io
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import sys
import types
import unittest
from unittest import mock

import numpy as np


ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


worker = _load("_s2_worker_test_subject", "app/thermogar_fe_equilibrium_worker.py")
controller = _load("_s2_controller_test_subject", "app/thermogar_fe_equilibrium_witness.py")
CONFIG = json.loads((ROOT / "configs/ne04_fe_equilibrium_witness_v1.json").read_text(encoding="utf-8"))
PHASES = tuple(CONFIG["request_contract"]["phase_selection"]["phases"])
RAW_PHASES = tuple(sorted((*PHASES, "BCC_A2")))
ATOMIC_ROWS = tuple(tuple(row) for row in CONFIG["atomic_mass_contract"]["ordered_rows"])
PURE_FE_PHASES = (
    "ALPHA_MN", "BCC_B2", "BCC_DISL", "BETA_MN", "C15_LAVES", "EPS_CARB",
    "ETA", "ETA_CARB", "FCC_A1", "FE24C10", "GAMMA_PRIME", "HCP_A3",
    "H_BCC", "KSI_CARBIDE", "KSI_FE5C2", "LAVES_PHASE", "LIQUID",
    "MU_PHASE_I", "PDFE_L12", "PDMN_B2", "PDMN_P", "TIB2",
)
FIXED_STEEL_PHASES = (
    "ALPHA_MN", "BCC_B2", "BCC_DISL", "BETA_MN", "C15_LAVES", "CEMENTITE",
    "CHI_A12", "DIAMOND_A4", "EPS_CARB", "ETA", "ETA_CARB", "FCC_A1",
    "FE24C10", "GAMMA_PRIME", "GRAPHITE", "HCP_A3", "H_BCC", "KSI_CARBIDE",
    "KSI_FE5C2", "LAVES_PHASE", "LIQUID", "M23C6", "M3C2", "M6C", "M7C3",
    "MU_PHASE_I", "PDFE_L12", "PDMN_B2", "PDMN_P", "SIGMA", "TIB2", "ZET",
)


class _Values:
    def __init__(self, values):
        self.values = np.asarray(values)


class _Dataset:
    def __init__(self, phase, fractions, coordinates, components=worker.MASS_ORDER):
        self._values = {
            "Phase": _Values(np.asarray(phase, dtype=object)),
            "NP": _Values(np.asarray(fractions, dtype=float)),
            "X": _Values(np.asarray(coordinates, dtype=float)),
        }
        self.coords = {"component": _Values(np.asarray(components, dtype=object))}

    def __getitem__(self, key):
        return self._values[key]


class _Variables:
    N = "N"
    P = "P"
    T = "T"

    @staticmethod
    def X(element):
        return f"X({element})"


class _Database:
    elements = tuple((*worker.MASS_ORDER, "VA"))
    phases = {name: object() for name in RAW_PHASES}
    refstates = {name: {"mass": mass} for name, mass in ATOMIC_ROWS}

    def __init__(self, stream):
        assert stream.__class__.__name__ == "StringIO"


class _DofError(Exception):
    pass


class _EquilibriumError(Exception):
    pass


class _ConditionError(_EquilibriumError):
    pass


class _LinAlgError(Exception):
    pass


FAKE_SCIENTIFIC_EXCEPTION_TYPES = (
    _DofError,
    _ConditionError,
    _EquilibriumError,
    _LinAlgError,
)


def _pure_fe_mass():
    return tuple((name, 1.0 if name == "FE" else 0.0) for name in worker.MASS_ORDER)


def _mass_with(**values):
    normalized = {name: 0.0 for name in worker.MASS_ORDER}
    normalized.update({key.upper(): value for key, value in values.items()})
    return tuple((name, normalized[name]) for name in worker.MASS_ORDER)


def _request(profile="thermogar_patch", temperature=1000.0, mass=None):
    profile_card = CONFIG["runtime_profiles"][profile]
    runtime = (ROOT / profile_card["relative_path"]).read_bytes()
    body = {
        "schema_version": worker.REQUEST_SCHEMA,
        "profile_id": profile,
        "runtime_size_bytes": len(runtime),
        "runtime_sha256": hashlib.sha256(runtime).hexdigest(),
        "runtime_base64": base64.b64encode(runtime).decode("ascii"),
        "mass_fractions": [list(row) for row in (mass or _pure_fe_mass())],
        "temperature_k": temperature,
        "pressure_pa": worker.PRESSURE_PA,
        "solver_components": list(
            worker._solver_components_for_mass(mass or _pure_fe_mass())
        ),
        "solver_component_count": len(
            worker._solver_components_for_mass(mass or _pure_fe_mass())
        ),
        "solver_component_sha256": worker._phase_digest(
            worker._solver_components_for_mass(mass or _pure_fe_mass())
        ),
        "component_projection_algorithm": worker.COMPONENT_PROJECTION_ALGORITHM,
        "eligible_phases": list(PHASES),
        "eligible_phase_sha256": worker.ELIGIBLE_PHASE_SHA256,
        "pdens": worker.PDENS,
        "atomic_mass_sha256": worker.ATOMIC_MASS_SHA256,
        "workspace_effective_x_floor": worker.ZERO_FLOOR,
    }
    return {**body, "request_id": worker._digest(body)}


def _effective_pure_fe():
    values = {name: 0.0 for name in worker.NON_FE_ORDER}
    values["FE"] = 1.0
    return [values[name] for name in worker.MASS_ORDER]


def _fake_api(dataset, calls, *, failure=None, projected=PURE_FE_PHASES):
    def equilibrium(database, components, phases, conditions, *, calc_opts):
        calls.append((components, phases, conditions, calc_opts))
        if failure is not None:
            raise failure
        return dataset

    return (
        _Database,
        equilibrium,
        _Variables,
        lambda database, components, candidate_phases=None: (
            list(PHASES) if candidate_phases is None else list(projected)
        ),
        FAKE_SCIENTIFIC_EXCEPTION_TYPES,
    )


def _diagnostic_failure_response(error, request_id="a" * 64):
    diagnostic = worker._scientific_failure_diagnostic(
        error,
        FAKE_SCIENTIFIC_EXCEPTION_TYPES,
    )
    return worker._failure_response(
        "FE_EQ_WORKER_SCIENTIFIC_API_FAILED",
        request_id,
        scientific_api_invoked=True,
        scientific_failure_diagnostic=diagnostic,
        projection_provenance=(("FE", "VA"), PURE_FE_PHASES),
    )


class WorkerTests(unittest.TestCase):
    def _execute(self, dataset):
        calls = []
        with mock.patch.object(worker, "_load_scientific_api", return_value=_fake_api(dataset, calls)), mock.patch.object(
            worker,
            "_load_conversion_api",
            return_value=(lambda rows, masses: rows, lambda rows, masses: rows),
        ):
            response = worker._execute_request(_request())
        return response, calls

    def test_success_aggregates_duplicate_vertices_without_raw_serialization(self):
        effective = _effective_pure_fe()
        dataset = _Dataset(
            ["C15_LAVES", "C15_LAVES", ""],
            [0.4, 0.6, 0.0],
            [[1.0], [1.0], [0.0]],
            ("FE",),
        )
        response, calls = self._execute(dataset)
        self.assertEqual(response["status"], "SUCCESS")
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0][2]), 3)
        self.assertEqual(calls[0][0], ["FE", "VA"])
        self.assertEqual(calls[0][1], list(PURE_FE_PHASES))
        self.assertEqual(calls[0][3], {"pdens": 25})
        self.assertEqual(response["raw_active_phase_row_count"], 2)
        self.assertEqual(response["terminal_phase_row_count"], 1)
        self.assertNotIn("raw_active_phase_rows", response)
        self.assertFalse(response["raw_dataset_serialized"])
        self.assertTrue(response["c15_present_in_terminal_rows"])
        self.assertEqual(response["validation_status"], "STRUCTURALLY_AND_NUMERICALLY_VALIDATED")

    def test_blank_phase_nan_np_is_inactive_sentinel(self):
        dataset = _Dataset(
            ["C15_LAVES", ""],
            [1.0, float("nan")],
            [[1.0], [float("nan")]],
            ("FE",),
        )
        response, calls = self._execute(dataset)
        self.assertEqual(len(calls), 1)
        self.assertEqual(response["raw_result_row_count"], 2)
        self.assertEqual(response["raw_active_phase_row_count"], 1)
        self.assertEqual(response["terminal_phase_row_count"], 1)
        self.assertEqual(response["phase_fraction_sum"], 1.0)
        self.assertEqual(response["runtime_effective_bulk_mole_fractions"], [
            [element, 1.0 if element == "FE" else 0.0]
            for element in worker.MASS_ORDER
        ])
        self.assertEqual(response["max_component_bulk_absolute_residual"], 0.0)

    def test_blank_phase_zero_np_remains_inactive_sentinel(self):
        dataset = _Dataset(
            ["C15_LAVES", ""], [1.0, 0.0], [[1.0], [float("inf")]], ("FE",)
        )
        response, _calls = self._execute(dataset)
        self.assertEqual(response["raw_active_phase_row_count"], 1)
        self.assertEqual(response["terminal_phase_rows"][0]["fraction"], 1.0)

    def test_blank_phase_invalid_np_rejected(self):
        for invalid in (1.0, -1.0, float("inf"), float("-inf"), True, "0"):
            with self.subTest(invalid=invalid):
                dataset = _Dataset(
                    ["C15_LAVES", ""], [1.0, invalid], [[1.0], [0.0]], ("FE",)
                )
                dataset._values["NP"] = _Values(
                    np.asarray([1.0, invalid], dtype=object)
                )
                with self.assertRaisesRegex(worker.WorkerFailure, "PHASE_RESULT_INVALID"):
                    self._execute(dataset)

    def test_nonblank_projected_nan_np_rejected(self):
        dataset = _Dataset(["C15_LAVES"], [float("nan")], [[1.0]], ("FE",))
        with self.assertRaisesRegex(worker.WorkerFailure, "PHASE_RESULT_INVALID"):
            self._execute(dataset)

    def test_unknown_nonblank_nan_np_rejected(self):
        dataset = _Dataset(["UNKNOWN_PHASE"], [float("nan")], [[1.0]], ("FE",))
        with self.assertRaisesRegex(worker.WorkerFailure, "PHASE_RESULT_INVALID"):
            self._execute(dataset)

    def test_negative_and_non_simplex_rows_rejected(self):
        effective = _effective_pure_fe()
        negative = [1.0]
        negative[0] = -1e-4
        for coordinates in (negative, [0.5]):
            dataset = _Dataset(["C15_LAVES"], [1.0], [coordinates], ("FE",))
            with self.assertRaisesRegex(worker.WorkerFailure, "COMPONENT_RESULT_INVALID"):
                self._execute(dataset)

    def test_va_axis_is_validated(self):
        effective = _effective_pure_fe()
        dataset = _Dataset(
            ["C15_LAVES"],
            [1.0],
            [[1.0, -1e-4]],
            ("FE", "VA"),
        )
        with self.assertRaisesRegex(worker.WorkerFailure, "COMPONENT_RESULT_INVALID"):
            self._execute(dataset)

        valid = _Dataset(["C15_LAVES"], [1.0], [[1.0, -0.0]], ("FE", "VA"))
        response, _calls = self._execute(valid)
        self.assertTrue(response["dataset_vacancy_axis_present"])
        self.assertEqual(response["terminal_phase_rows"][0]["vacancy_coordinate"], 0.0)
        self.assertEqual(
            math.copysign(
                1.0, response["terminal_phase_rows"][0]["vacancy_coordinate"]
            ),
            1.0,
        )

    def test_request_scope_tamper_rejected_before_api(self):
        request = _request()
        request["pdens"] = 499
        body = dict(request)
        body.pop("request_id")
        request["request_id"] = worker._digest(body)
        with self.assertRaisesRegex(worker.WorkerFailure, "SCOPE_INVALID"):
            worker._validate_request(request)

    def test_fixed_steel_projects_exact_32_phases_and_one_active_call(self):
        mass = _mass_with(C=0.001, CR=0.02, FE=0.979)
        coordinates = [0.001, 0.02, 0.979]
        dataset = _Dataset(["C15_LAVES"], [1.0], [coordinates], ("C", "CR", "FE"))
        calls = []
        with mock.patch.object(
            worker, "_load_scientific_api",
            return_value=_fake_api(dataset, calls, projected=FIXED_STEEL_PHASES),
        ), mock.patch.object(
            worker, "_load_conversion_api",
            return_value=(lambda rows, masses: rows, lambda rows, masses: rows),
        ):
            response = worker._execute_request(_request(mass=mass))
        self.assertEqual(response["solver_component_axis"], ["C", "CR", "FE", "VA"])
        self.assertEqual(response["projected_active_phase_count"], 32)
        self.assertEqual(
            response["projected_active_phase_sha256"],
            "9db23731e485cd71066f86456bb1c9b75d7e967de6bc44d65708db201dfcf6e0",
        )
        self.assertIn("C15_LAVES", response["projected_active_phases"])
        self.assertIn("LIQUID", response["projected_active_phases"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], ["C", "CR", "FE", "VA"])
        self.assertEqual(calls[0][1], list(FIXED_STEEL_PHASES))
        self.assertEqual(set(calls[0][2]), {"N", "P", "T", "X(C)", "X(CR)"})

    def test_pure_fe_projection_digest_and_full_25_zero_outputs(self):
        dataset = _Dataset(["C15_LAVES"], [1.0], [[1.0]], ("FE",))
        response, calls = self._execute(dataset)
        self.assertEqual(response["solver_component_axis"], ["FE", "VA"])
        self.assertEqual(response["projected_active_phase_count"], 22)
        self.assertEqual(
            response["projected_active_phase_sha256"],
            "a21ce6fb6dd5fdd307518d0c859ae2cf8ef5b8a914e3515a70d2fffd7a23f3de",
        )
        self.assertEqual(response["dataset_nonvacant_component_axis"], ["FE"])
        for field in (
            "nominal_mass_fractions", "nominal_mole_fractions",
            "runtime_effective_mole_fractions", "round_trip_mass_fractions",
            "runtime_effective_bulk_mole_fractions",
        ):
            rows = dict(response[field])
            self.assertTrue(all(rows[name] == 0.0 for name in worker.NON_FE_ORDER))
        self.assertEqual(len(calls[0][2]), 3)

    def test_ni_after_fe_raw_axis_is_remapped_to_contract_axis(self):
        mass = _mass_with(FE=0.9, NI=0.1)
        dataset = _Dataset(["C15_LAVES"], [1.0], [[0.9, 0.1]], ("FE", "NI"))
        calls = []
        with mock.patch.object(
            worker, "_load_scientific_api",
            return_value=_fake_api(dataset, calls, projected=PURE_FE_PHASES),
        ), mock.patch.object(
            worker, "_load_conversion_api",
            return_value=(lambda rows, masses: rows, lambda rows, masses: rows),
        ):
            response = worker._execute_request(_request(mass=mass))
        self.assertEqual(response["solver_component_axis"], ["NI", "FE", "VA"])
        self.assertEqual(response["dataset_nonvacant_component_axis"], ["NI", "FE"])
        self.assertEqual(
            dict(response["terminal_phase_rows"][0]["chemical_coordinates"])["NI"],
            0.1,
        )

    def test_tiny_positive_is_active_floored_and_conversion_underflow_fails(self):
        tiny = 1e-300
        mass = _mass_with(FE=1.0 - tiny, NI=tiny)
        dataset = _Dataset(
            ["C15_LAVES"], [1.0],
            [[1.0 - worker.ZERO_FLOOR, worker.ZERO_FLOOR]], ("FE", "NI"),
        )
        calls = []
        with mock.patch.object(
            worker, "_load_scientific_api",
            return_value=_fake_api(dataset, calls, projected=PURE_FE_PHASES),
        ), mock.patch.object(
            worker, "_load_conversion_api",
            return_value=(lambda rows, masses: rows, lambda rows, masses: rows),
        ):
            response = worker._execute_request(_request(mass=mass))
        self.assertEqual(response["solver_component_axis"], ["NI", "FE", "VA"])
        self.assertEqual(dict(response["runtime_effective_mole_fractions"])["NI"], worker.ZERO_FLOOR)

        def underflow(rows, _masses):
            return tuple((name, 0.0 if name == "NI" else value) for name, value in rows)

        with mock.patch.object(
            worker, "_load_scientific_api",
            return_value=_fake_api(dataset, [], projected=PURE_FE_PHASES),
        ), mock.patch.object(
            worker, "_load_conversion_api", return_value=(underflow, lambda rows, masses: rows),
        ):
            with self.assertRaisesRegex(worker.WorkerFailure, "BASIS_CONVERSION_FAILED"):
                worker._execute_request(_request(mass=mass))

    def test_zero_normalization_nonfinite_bool_and_projection_tamper_fail_closed(self):
        mapping = dict(_pure_fe_mass())
        mapping["NI"] = -0.0
        normalized = controller._canonical_mass_mapping(mapping)
        self.assertEqual(math.copysign(1.0, dict(normalized)["NI"]), 1.0)
        self.assertEqual(controller._solver_components_for_mass(normalized), ("FE", "VA"))
        dataset = _Dataset(["C15_LAVES"], [1.0], [[1.0]], ("FE",))
        negative_zero_rows = tuple(
            (name, value if value != 0.0 else -0.0) for name, value in _pure_fe_mass()
        )
        with mock.patch.object(
            worker, "_load_scientific_api",
            return_value=_fake_api(dataset, [], projected=PURE_FE_PHASES),
        ), mock.patch.object(
            worker, "_load_conversion_api",
            return_value=(
                lambda rows, masses: negative_zero_rows,
                lambda rows, masses: negative_zero_rows,
            ),
        ):
            response = worker._execute_request(_request())
        for field in ("nominal_mole_fractions", "round_trip_mass_fractions"):
            self.assertTrue(
                all(
                    math.copysign(1.0, value) == 1.0
                    for _name, value in response[field]
                    if value == 0.0
                )
            )
        for bad in (True, float("nan")):
            request = _request()
            request["mass_fractions"][worker.MASS_ORDER.index("NI")][1] = bad
            with self.assertRaises(worker.WorkerFailure):
                worker._validate_request(request)
        for components in (
            ["VA", "FE"], ["FE"], ["FE", "VA", "VA"], ["NI", "FE", "VA"],
        ):
            request = _request()
            request["solver_components"] = components
            request["solver_component_count"] = len(components)
            request["solver_component_sha256"] = worker._phase_digest(tuple(components))
            body = dict(request)
            body.pop("request_id")
            request["request_id"] = worker._digest(body)
            with self.assertRaises(worker.WorkerFailure):
                worker._validate_request(request)

    def test_phase_filter_and_dataset_axis_tamper_fail_closed(self):
        dataset = _Dataset(["C15_LAVES"], [1.0], [[1.0]], ("FE",))
        for projected in (("NOT_PINNED",), (), ("C15_LAVES", "C15_LAVES")):
            calls = []
            with mock.patch.object(
                worker, "_load_scientific_api",
                return_value=_fake_api(dataset, calls, projected=projected),
            ):
                with self.assertRaisesRegex(worker.WorkerFailure, "PHASE_SCOPE_INVALID"):
                    worker._execute_request(_request())
        for components in ((), ("NI",), ("FE", "FE"), ("FE", "NI")):
            bad = _Dataset(["C15_LAVES"], [1.0], [[1.0] * len(components)], components)
            with self.assertRaises(worker.WorkerFailure):
                self._execute(bad)

    def test_verified_byte_conversion_loader(self):
        mass_to_mole, mole_to_mass = worker._load_conversion_api()
        self.assertTrue(callable(mass_to_mole))
        self.assertTrue(callable(mole_to_mass))

    def test_utils_filter_runtime_pin_size_hash_and_origin_fail_closed(self):
        exact = worker.RUNTIME_POLICY_IDENTITIES["utils"]
        for tampered in ((exact[0] - 1, exact[1]), (exact[0], "0" * 64)):
            with self.subTest(tampered=tampered), mock.patch.dict(
                worker.RUNTIME_POLICY_IDENTITIES, {"utils": tampered}
            ):
                with self.assertRaisesRegex(
                    worker.WorkerFailure, "RUNTIME_POLICY_INVALID"
                ):
                    worker._load_scientific_api()

        package_root = (
            ROOT / ".venv-windows/Lib/site-packages/pycalphad"
        ).resolve()
        policy_paths = {
            "equilibrium": package_root / "core/equilibrium.py",
            "utils": package_root / "core/utils.py",
        }

        def fake_equilibrium():
            return None

        def fake_filter():
            return None

        fake_equilibrium.__module__ = "_s2_fake_equilibrium_origin"
        fake_filter.__module__ = "_s2_fake_filter_origin"
        package = types.SimpleNamespace(__file__=str(package_root / "__init__.py"))
        modules = {
            fake_equilibrium.__module__: types.SimpleNamespace(
                __file__=str(policy_paths["equilibrium"])
            ),
            fake_filter.__module__: types.SimpleNamespace(
                __file__=str(policy_paths["utils"])
            ),
        }
        with mock.patch.dict(worker.sys.modules, modules):
            worker._validate_scientific_origins(
                package, fake_equilibrium, fake_filter, package_root, policy_paths
            )
            modules[fake_filter.__module__].__file__ = str(
                package_root / "core/not_utils.py"
            )
            with self.assertRaisesRegex(
                worker.WorkerFailure, "RUNTIME_POLICY_INVALID"
            ):
                worker._validate_scientific_origins(
                    package, fake_equilibrium, fake_filter, package_root, policy_paths
                )

    def _execute_scientific_failure(self, error):
        request = _request()
        calls = []
        with mock.patch.object(
            worker,
            "_load_scientific_api",
            return_value=_fake_api(None, calls, failure=error),
        ), mock.patch.object(
            worker,
            "_load_conversion_api",
            return_value=(lambda rows, masses: rows, lambda rows, masses: rows),
        ):
            with self.assertRaises(worker.WorkerFailure) as caught:
                worker._execute_request(request)
        failure = caught.exception
        self.assertEqual(failure.code, "FE_EQ_WORKER_SCIENTIFIC_API_FAILED")
        self.assertTrue(failure.scientific_api_invoked)
        response = worker._failure_response(
            failure.code,
            request["request_id"],
            scientific_api_invoked=failure.scientific_api_invoked,
            scientific_failure_diagnostic=failure.scientific_failure_diagnostic,
            projection_provenance=failure.projection_provenance,
        )
        return response, calls

    def test_scientific_failure_closed_classification_mapping(self):
        cases = (
            (MemoryError("private path one"), "MEMORY_ALLOCATION", "MEMORY_ERROR"),
            (_DofError("private path two"), "MODEL_CONSTRUCTION", "PYCALPHAD_DOF_ERROR"),
            (_ConditionError("private path three"), "CONDITION_CONTRACT", "PYCALPHAD_CONDITION_ERROR"),
            (_EquilibriumError("private path four"), "SOLVER_FAILURE", "PYCALPHAD_EQUILIBRIUM_ERROR"),
            (_LinAlgError("private path five"), "SOLVER_FAILURE", "NUMPY_LINALG_ERROR"),
            (ValueError("private path six"), "OTHER", "OTHER"),
            (RuntimeError("private path seven"), "OTHER", "OTHER"),
        )
        for error, category, token in cases:
            with self.subTest(token=token):
                response, calls = self._execute_scientific_failure(error)
                self.assertEqual(len(calls), 1)
                self.assertEqual(response["scientific_failure_stage"], "EQUILIBRIUM_CALL")
                self.assertEqual(response["scientific_api_invocation_count"], 1)
                self.assertFalse(response["dataset_returned"])
                self.assertEqual(response["scientific_failure_category"], category)
                self.assertEqual(response["scientific_exception_tokens"], [token])
                self.assertIn("DIAGNOSTIC_MESSAGE_REDACTED", response["limitations"])

    def test_scientific_failure_fingerprint_is_message_and_path_independent(self):
        first, _calls = self._execute_scientific_failure(
            MemoryError(r"C:\\secret\\alpha.tdb: allocation one")
        )
        second, _calls = self._execute_scientific_failure(
            MemoryError(r"D:\\other\\beta.tdb: allocation two")
        )
        self.assertEqual(
            first["scientific_failure_fingerprint_sha256"],
            second["scientific_failure_fingerprint_sha256"],
        )
        encoded = worker._canonical_bytes(first).decode("ascii")
        for forbidden in ("secret", "alpha", "other", "beta", "allocation"):
            self.assertNotIn(forbidden, encoded)

    def test_scientific_failure_chain_is_bounded_and_cycle_safe(self):
        outer = RuntimeError("outer")
        inner = _DofError("inner")
        outer.__cause__ = inner
        inner.__cause__ = outer
        response = _diagnostic_failure_response(outer)
        self.assertEqual(
            response["scientific_exception_tokens"],
            ["OTHER", "PYCALPHAD_DOF_ERROR"],
        )
        self.assertEqual(response["scientific_failure_category"], "MODEL_CONSTRUCTION")

        chain = [RuntimeError(str(index)) for index in range(6)]
        for current, following in zip(chain, chain[1:]):
            current.__cause__ = following
        bounded = _diagnostic_failure_response(chain[0])
        self.assertEqual(len(bounded["scientific_exception_tokens"]), 4)
        self.assertEqual(bounded["scientific_exception_tokens"], ["OTHER"] * 4)


class ControllerTests(unittest.TestCase):
    @staticmethod
    def _cleanup_test_directory(path, identity):
        expected_parent = ROOT.resolve(strict=True)
        if (
            path.parent.resolve(strict=True) != expected_parent
            or not path.name.startswith(".s2-test-")
            or controller._path_chain_has_reparse(path)
            or controller._directory_identity(path) != identity
        ):
            raise AssertionError("unsafe DACL test cleanup target")
        shutil.rmtree(path)

    def _test_directory(self, label):
        path = ROOT / f".s2-test-{label}-{secrets.token_hex(12)}"
        path.mkdir()
        identity = controller._directory_identity(path)
        self.addCleanup(self._cleanup_test_directory, path, identity)
        return path

    def _directory_sddl(self, path):
        kernel32 = controller._kernel32_api()
        advapi32 = controller._advapi32_api()
        handle = controller._open_private_directory_security_handle(
            kernel32,
            path,
        )
        try:
            return controller._private_handle_sddl(kernel32, advapi32, handle)
        finally:
            controller._close_handle(kernel32, handle)

    def test_public_signature_has_only_three_inputs(self):
        signature = inspect.signature(controller.run_fe_equilibrium_witness)
        self.assertEqual(tuple(signature.parameters), ("profile_id", "mass_fractions", "temperature_k"))

    def test_contract_and_all_runtime_pins_are_green(self):
        contract = controller._load_contract(ROOT)
        self.assertEqual(len(contract.eligible_phases), 131)
        self.assertEqual(len(contract.cards), 18)
        utils_cards = [
            card for card in contract.cards if card.role == "pycalphad_utils_filter"
        ]
        self.assertEqual(len(utils_cards), 1)
        self.assertEqual(utils_cards[0].size_bytes, 22838)
        self.assertEqual(
            utils_cards[0].sha256,
            "1705991a0984401993805e7231278b1005ff7d1da984704132d28e163d3af258",
        )
        self.assertEqual(contract.worker_python.role, "worker_python")
        self.assertEqual(controller.PDENS, 25)
        self.assertEqual(worker.PDENS, 25)
        config = json.loads((ROOT / "configs" / "ne04_fe_equilibrium_witness_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(
            config["request_contract"]["solver_options"],
            {
                "pdens": 25,
                "arbitrary_input_allowed": False,
                "semantic": "LOW_RESOLUTION_LOCAL_NUMERICAL_DIAGNOSTIC_NOT_SOURCE_DOMAIN_CLAIM",
            },
        )
        self.assertEqual(
            config["process_contract"]["executable_code_read_locks"]["locked_roles"][-1],
            "pycalphad_utils_filter",
        )
        opened = []

        def fake_open(_kernel32, root, card):
            opened.append(card.role)
            return controller._LockedCodeFile(
                card.role, root / card.relative_path, io.BytesIO()
            )

        with mock.patch.object(
            controller, "_open_locked_code_file", side_effect=fake_open
        ):
            locked = controller._lock_executable_code(object(), ROOT, contract)
        try:
            self.assertEqual(opened[-1], "pycalphad_utils_filter")
            self.assertEqual(len(locked), 8)
        finally:
            for item in locked:
                item.file_object.close()

    def test_public_request_rejects_extra_missing_va_and_bad_temperature(self):
        composition = dict(_pure_fe_mass())
        for bad in (
            {**composition, "VA": 0.0},
            {key: value for key, value in composition.items() if key != "Y"},
        ):
            with self.assertRaises(controller.EquilibriumWitnessError):
                controller.run_fe_equilibrium_witness("thermogar_patch", bad, 1000.0)
        with self.assertRaises(controller.EquilibriumWitnessError):
            controller.run_fe_equilibrium_witness("thermogar_patch", composition, float("nan"))

    def _attempt(self, number, code, matched=False, execution="UNKNOWN_AFTER_TRANSPORT_OR_CONTAINMENT_FAILURE"):
        return controller._AttemptExecution(
            controller.AttemptReceipt(
                attempt_number=number,
                request_sha256="a" * 64,
                status="FAILURE",
                failure_code=code,
                return_code=70,
                duration_seconds=1.0,
                peak_observed_tree_rss_bytes=123,
                stdout_observed_bytes=0,
                stdout_sha256=hashlib.sha256(b"").hexdigest(),
                stderr_observed_bytes=0,
                stderr_tail_bytes=0,
                stderr_tail_sha256=hashlib.sha256(b"").hexdigest(),
                process_tree_terminated=True,
                matched_valid_response=matched,
                real_equilibrium_execution_status=execution,
            ),
            None,
        )

    def test_retry_only_two_transport_codes_and_identical_bytes(self):
        contract = mock.Mock()
        first = self._attempt(1, "FE_EQ_WORKER_PIPE_BROKEN")
        second = self._attempt(2, "FE_EQ_WORKER_CHILD_EXIT_NO_RESPONSE")
        with mock.patch.object(controller, "_spawn_win32_attempt", side_effect=[first, second]) as spawn:
            attempts = controller._attempt_sequence(ROOT, contract, b"fixed", "a" * 64)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(spawn.call_args_list[0].args[2], spawn.call_args_list[1].args[2])
        no_retry = self._attempt(1, "FE_EQ_WORKER_TIMEOUT")
        with mock.patch.object(controller, "_spawn_win32_attempt", return_value=no_retry) as spawn:
            self.assertEqual(len(controller._attempt_sequence(ROOT, contract, b"fixed", "a" * 64)), 1)
            self.assertEqual(spawn.call_count, 1)

    def test_receipt_blocks_forged_success_and_retry_match(self):
        with self.assertRaises(Exception):
            controller.AttemptReceipt(
                attempt_number=1, request_sha256="a" * 64, status="SUCCESS",
                failure_code=None, return_code=0, duration_seconds=0.1,
                peak_observed_tree_rss_bytes=0, stdout_observed_bytes=0,
                stdout_sha256="0" * 64, stderr_observed_bytes=0,
                stderr_tail_bytes=0, stderr_tail_sha256="0" * 64,
                process_tree_terminated=False, matched_valid_response=False,
                real_equilibrium_execution_status="CONFIRMED_NOT_INVOKED",
            )

    def test_controller_parses_worker_success_and_detects_tamper(self):
        dataset = _Dataset(["C15_LAVES"], [1.0], [[1.0]], ("FE",))
        calls = []
        with mock.patch.object(worker, "_load_scientific_api", return_value=_fake_api(dataset, calls)), mock.patch.object(
            worker, "_load_conversion_api", return_value=(lambda rows, masses: rows, lambda rows, masses: rows)
        ):
            response = worker._execute_request(_request())
        framed = worker._canonical_bytes(response) + b"\n"
        parsed = controller._parse_worker_response(framed, response["request_id"], PHASES)
        self.assertEqual(parsed["status"], "SUCCESS")
        mutations = (
            ("projected_active_phase_count", 21),
            ("projected_active_phase_sha256", "0" * 64),
            ("solver_component_axis", ["VA", "FE"]),
            ("dataset_nonvacant_component_axis", ["NI", "FE"]),
            ("dataset_nonvacant_component_count", 2),
            ("dataset_nonvacant_component_sha256", "0" * 64),
        )
        for key, changed in mutations:
            with self.subTest(key=key):
                tampered = json.loads(json.dumps(response))
                tampered[key] = changed
                with self.assertRaises(Exception):
                    controller._parse_worker_response(
                        worker._canonical_bytes(tampered) + b"\n",
                        response["request_id"],
                        PHASES,
                    )
        response["terminal_phase_rows"][0]["phase"] = "NOT_PINNED"
        with self.assertRaises(Exception):
            controller._parse_worker_response(worker._canonical_bytes(response) + b"\n", response["request_id"], PHASES)

    def test_controller_requires_exact_scientific_failure_diagnostic(self):
        request_id = "a" * 64
        response = _diagnostic_failure_response(MemoryError("redacted"), request_id)
        parsed = controller._parse_worker_response(
            worker._canonical_bytes(response) + b"\n",
            request_id,
            PHASES,
        )
        self.assertEqual(parsed["failure_code"], "FE_EQ_WORKER_SCIENTIFIC_API_FAILED")
        self.assertEqual(parsed["scientific_exception_tokens"], ["MEMORY_ERROR"])

        mutations = (
            ("scientific_failure_stage", "OTHER_STAGE"),
            ("scientific_api_invocation_count", True),
            ("scientific_api_invocation_count", 2),
            ("dataset_returned", True),
            ("scientific_failure_category", "UNBOUNDED"),
            ("scientific_exception_tokens", ["MemoryError"]),
            ("scientific_exception_tokens", ["OTHER"] * 5),
            ("scientific_failure_fingerprint_sha256", "0" * 64),
            ("raw_exception_included", True),
            ("path_included", True),
        )
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                tampered = json.loads(json.dumps(response))
                tampered[key] = value
                with self.assertRaises(Exception):
                    controller._parse_worker_response(
                        worker._canonical_bytes(tampered) + b"\n",
                        request_id,
                        PHASES,
                    )
        extra = json.loads(json.dumps(response))
        extra["raw_exception_message"] = "forbidden"
        with self.assertRaises(Exception):
            controller._parse_worker_response(
                worker._canonical_bytes(extra) + b"\n",
                request_id,
                PHASES,
            )

    def test_scientific_failure_worker_and_top_level_limitations_are_distinct(self):
        request_id = "a" * 64
        response = _diagnostic_failure_response(MemoryError("redacted"), request_id)
        worker_limitations = [
            "CONVERGENCE_STATUS_NOT_EXPORTED",
            "DIAGNOSTIC_MESSAGE_REDACTED",
            "PRESSURE_DOMAIN_UNKNOWN_BLOCKED",
            "NOT_NE04_ACCEPTANCE",
            "NOT_RELEASE_AUTHORIZATION",
        ]
        self.assertEqual(response["limitations"], worker_limitations)
        observation = controller.InputObservation("test", 0, "0" * 64)
        result = controller.EquilibriumWitnessResult(
            profile_id="thermogar_patch",
            temperature_k=1000.0,
            mass_fractions=_pure_fe_mass(),
            request_sha256=request_id,
            pre=controller.InputSnapshot("PRE", request_id, (observation,)),
            post=controller.InputSnapshot("POST", request_id, (observation,)),
            attempts=(
                controller.AttemptReceipt(
                    attempt_number=1,
                    request_sha256=request_id,
                    status="FAILURE",
                    failure_code="FE_EQ_WORKER_SCIENTIFIC_API_FAILED",
                    return_code=0,
                    duration_seconds=1.0,
                    peak_observed_tree_rss_bytes=1,
                    stdout_observed_bytes=1,
                    stdout_sha256="0" * 64,
                    stderr_observed_bytes=0,
                    stderr_tail_bytes=0,
                    stderr_tail_sha256="0" * 64,
                    process_tree_terminated=False,
                    matched_valid_response=True,
                    real_equilibrium_execution_status="CONFIRMED_EXECUTED",
                ),
            ),
            status="FAILURE",
            failure_code="FE_EQ_WORKER_SCIENTIFIC_API_FAILED",
            worker_response_json=worker._canonical_bytes(response).decode("ascii"),
            eligible_phases=PHASES,
        ).as_dict()
        self.assertEqual(
            result["limitations"],
            [*worker_limitations, "NO_EXPECTED_PHASE_OR_PHYSICS_CLAIM"],
        )

    def test_diagnostic_fields_are_forbidden_on_other_failures(self):
        request_id = "a" * 64
        response = worker._failure_response(
            "FE_EQ_WORKER_PROTOCOL_INVALID",
            request_id,
        )
        controller._parse_worker_response(
            worker._canonical_bytes(response) + b"\n",
            request_id,
            PHASES,
        )
        response["scientific_failure_stage"] = "EQUILIBRIUM_CALL"
        with self.assertRaises(Exception):
            controller._parse_worker_response(
                worker._canonical_bytes(response) + b"\n",
                request_id,
                PHASES,
            )

    @unittest.skipUnless(os.name == "nt", "Win32 DACL regression")
    def test_atomic_cold_existing_exact_and_polluted_fail_closed(self):
        kernel32 = controller._kernel32_api()
        parent = self._test_directory("dacl") / "inheriting-parent"
        parent.mkdir()

        cold = parent / "cold"
        self.assertTrue(
            controller._create_or_verify_private_directory(
                kernel32,
                cold,
                allow_existing=False,
                operation="test_cold_child",
            )
        )
        self.assertEqual(
            self._directory_sddl(cold),
            controller.PRIVATE_DIRECTORY_SDDL,
        )
        cold_identity = controller._directory_identity(cold)
        cold_sddl = self._directory_sddl(cold)
        self.assertFalse(
            controller._create_or_verify_private_directory(
                kernel32,
                cold,
                allow_existing=True,
                operation="test_existing_exact_child",
            )
        )
        self.assertEqual(controller._directory_identity(cold), cold_identity)
        self.assertEqual(self._directory_sddl(cold), cold_sddl)

        polluted = parent / "polluted"
        polluted.mkdir()
        polluted_sddl = self._directory_sddl(polluted)
        self.assertNotEqual(polluted_sddl, controller.PRIVATE_DIRECTORY_SDDL)
        polluted_identity = controller._directory_identity(polluted)
        with self.assertRaises(controller._ContainmentStageFailure) as caught:
            controller._create_or_verify_private_directory(
                kernel32,
                polluted,
                allow_existing=True,
                operation="test_existing_child",
            )
        self.assertEqual(caught.exception.operation, "existing_private_dacl_invalid")
        self.assertEqual(self._directory_sddl(polluted), polluted_sddl)
        self.assertEqual(controller._directory_identity(polluted), polluted_identity)

    @unittest.skipUnless(os.name == "nt", "Win32 DACL regression")
    def test_existing_run_collision_is_not_deleted_or_remediated(self):
        kernel32 = controller._kernel32_api()
        collision = self._test_directory("collision") / "run-collision"
        collision.mkdir()
        identity = controller._directory_identity(collision)
        with self.assertRaises(controller._ContainmentStageFailure) as caught:
            controller._create_or_verify_private_directory(
                kernel32,
                collision,
                allow_existing=False,
                operation="test_run_collision",
            )
        self.assertEqual(caught.exception.win32_code, 183)
        self.assertTrue(collision.is_dir())
        self.assertEqual(controller._directory_identity(collision), identity)

    def test_containment_stage_is_private_and_blocks_before_spawn(self):
        kernel32 = mock.Mock()
        stage = controller._ContainmentStageFailure(
            "existing_private_dacl_invalid",
            None,
        )
        with mock.patch.object(controller, "_kernel32_api", return_value=kernel32), mock.patch.object(
            controller,
            "_private_worker_directory",
            side_effect=stage,
        ), mock.patch.object(controller, "_minimal_environment_block") as environment, mock.patch.object(
            controller,
            "_lock_executable_code",
        ) as code_locks:
            with self.assertRaises(controller.EquilibriumWitnessError) as caught:
                controller._spawn_win32_attempt(
                    ROOT,
                    mock.Mock(),
                    b"{}",
                    "a" * 64,
                    1,
                )
        self.assertEqual(
            caught.exception.code,
            "FE_EQ_CONTROLLER_CONTAINMENT_UNAVAILABLE",
        )
        self.assertIs(caught.exception.__cause__, stage)
        self.assertEqual(stage.operation, "existing_private_dacl_invalid")
        self.assertIsNone(stage.win32_code)
        environment.assert_not_called()
        code_locks.assert_not_called()
        kernel32.CreateProcessW.assert_not_called()
        kernel32.ResumeThread.assert_not_called()

    def test_win32_stage_captures_code_without_public_detail(self):
        with mock.patch.object(controller.ctypes, "get_last_error", return_value=5):
            stage = controller._win_error("CreateDirectoryW.test")
        self.assertEqual(stage.operation, "CreateDirectoryW.test")
        self.assertEqual(stage.win32_code, 5)
        self.assertEqual(str(stage), "operation=CreateDirectoryW.test;win32_code=5")


class StaticTests(unittest.TestCase):
    def test_ast_has_one_scientific_call_and_no_forbidden_launches(self):
        worker_tree = ast.parse((ROOT / "app/thermogar_fe_equilibrium_worker.py").read_text(encoding="utf-8"))
        controller_tree = ast.parse((ROOT / "app/thermogar_fe_equilibrium_witness.py").read_text(encoding="utf-8"))
        worker_source = (ROOT / "app/thermogar_fe_equilibrium_worker.py").read_text(encoding="utf-8")
        equilibrium_calls = [
            node for node in ast.walk(worker_tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "equilibrium"
        ]
        self.assertEqual(len(equilibrium_calls), 1)
        for forbidden in (
            "str(error)",
            "repr(error)",
            "error.args",
            "error.__class__",
            "error.__module__",
            "type(error).__name__",
            "format_exception",
            "extract_tb",
        ):
            self.assertNotIn(forbidden, worker_source)
        for required in (
            'SCIENTIFIC_FAILURE_STAGE = "EQUILIBRIUM_CALL"',
            '"PYCALPHAD_DOF_ERROR"',
            '"PYCALPHAD_CONDITION_ERROR"',
            '"PYCALPHAD_EQUILIBRIUM_ERROR"',
            '"NUMPY_LINALG_ERROR"',
            '"DIAGNOSTIC_MESSAGE_REDACTED"',
        ):
            self.assertIn(required, worker_source)
        controller_source = (ROOT / "app/thermogar_fe_equilibrium_witness.py").read_text(encoding="utf-8")
        for forbidden in ("subprocess.Popen", "shell=True", "DETACHED_PROCESS", "CREATE_BREAKAWAY_FROM_JOB", "taskkill"):
            self.assertNotIn(forbidden, controller_source)
        for forbidden in (
            "fixed_root.mkdir",
            "path.mkdir",
            "pycache_directory.mkdir",
            "SetNamedSecurityInfoW",
            "SetSecurityInfo",
            "SetFileSecurityW",
            "SetKernelObjectSecurity",
            "GetKernelObjectSecurity",
        ):
            self.assertNotIn(forbidden, controller_source)
        for required in (
            "CreateDirectoryW",
            "_SECURITY_ATTRIBUTES",
            "GetSecurityInfo",
            "GetFinalPathNameByHandleW",
            "existing_private_dacl_invalid",
            "private_dacl_exact_readback",
        ):
            self.assertIn(required, controller_source)

    def test_no_product_or_old_wave_imports(self):
        combined = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "app/thermogar_fe_equilibrium_worker.py",
                "app/thermogar_fe_equilibrium_witness.py",
            )
        )
        for forbidden in (
            "ThermoGar_app", "thermogar_release_ui", "thermogar_release_policy",
            "thermogar_wave2b", "thermogar_fe_local_witness", "thermogar_ne04_fe_diagnostic_domain",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
