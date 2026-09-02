from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))
import thermogar_fe_steel_adapter as adapter

BRIDGE_SPEC = importlib.util.spec_from_file_location("steel_bridge_subject", ROOT / "tools/run_ne04_fe_steel_diagnostic.py")
bridge = importlib.util.module_from_spec(BRIDGE_SPEC)
assert BRIDGE_SPEC.loader is not None
BRIDGE_SPEC.loader.exec_module(bridge)
CONTROL_RECEIPT = json.loads(adapter.CONTROL_RECEIPT.read_text("ascii"))


def request_payload(values=None, temperature=1200.0):
    wt = dict(adapter.DEFAULT_WT_PERCENT if values is None else values)
    return adapter.build_request(wt, temperature)


class FakeResult:
    def __init__(self, value): self.value = value
    def as_dict(self): return copy.deepcopy(self.value)


class FakeController:
    def __init__(self, value=None, error=None): self.value, self.error, self.calls = value, error, []
    def run_fe_equilibrium_witness(self, *args):
        self.calls.append(args)
        if self.error is not None: raise RuntimeError(self.error)
        return FakeResult(self.value)


class BridgeTests(unittest.TestCase):
    def test_001_exact_one_patch_call(self):
        payload, mass, temperature = request_payload()
        controller = FakeController(CONTROL_RECEIPT)
        output = bridge.process(payload, lambda: controller)
        self.assertEqual(output["status"], "SUCCESS")
        self.assertEqual(len(controller.calls), 1)
        profile, called_mass, called_temperature = controller.calls[0]
        self.assertEqual(profile, "thermogar_patch")
        self.assertEqual(called_mass, mass)
        self.assertEqual(called_temperature, temperature)

    def test_002_invalid_input_zero_loader_or_call(self):
        valid, _mass, _temperature = request_payload()
        variants = [b"{}\n", valid.replace(b'"AL",0.0', b'"AL",NaN'), valid[:-1], valid.replace(b'"AL",0.0', b'"AL",true')]
        for payload in variants:
            count = [0]
            def loader(): count[0] += 1; return FakeController(CONTROL_RECEIPT)
            with self.assertRaises(bridge.BridgeReject): bridge.process(payload, loader)
            self.assertEqual(count[0], 0)

    def test_003_loader_failure_zero_calls_binds_input(self):
        payload, _mass, _temperature = request_payload()
        output = bridge.process(payload, lambda: (_ for _ in ()).throw(RuntimeError("secret path")))
        self.assertEqual(output["status"], "FAILURE")
        self.assertEqual(output["controller_call_count"], 0)
        self.assertEqual(output["input_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertNotIn("secret", json.dumps(output))

    def test_004_call_exception_one_no_retry_or_leak(self):
        payload, _mass, _temperature = request_payload()
        controller = FakeController(error=r"secret C:\private\file")
        output = bridge.process(payload, lambda: controller)
        self.assertEqual(len(controller.calls), 1)
        self.assertEqual(output["controller_call_count"], 1)
        self.assertEqual(output["input_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertNotIn("secret", json.dumps(output))

    def test_005_returned_failure_one_no_receipt(self):
        payload, _mass, _temperature = request_payload()
        failed = copy.deepcopy(CONTROL_RECEIPT); failed["status"] = "FAILURE"
        controller = FakeController(failed)
        output = bridge.process(payload, lambda: controller)
        self.assertEqual(output["controller_call_count"], 1)
        self.assertIsNone(output["receipt"])
        self.assertEqual(len(controller.calls), 1)

    def test_006_canonical_output_and_overflow_fallback(self):
        output = bridge.safe_failure("STEEL_DIAGNOSTIC_UNAVAILABLE", input_sha256="a" * 64, call_count=1)
        encoded = bridge.canonical(output)
        self.assertEqual(encoded, json.dumps(output, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n")
        huge = {**output, "receipt": "x" * (bridge.MAX_STDOUT_BYTES + 1)}
        fallback = bridge.canonical(bridge.safe_failure("STEEL_DIAGNOSTIC_UNAVAILABLE", input_sha256=huge["input_sha256"], call_count=huge["controller_call_count"]))
        self.assertLess(len(fallback), bridge.MAX_STDOUT_BYTES)
        self.assertNotIn(b"xxxx", fallback)

    def test_007_strict_order_bounds_sum_temperature(self):
        payload, _mass, _temperature = request_payload()
        value = json.loads(payload)
        for mutate in (
            lambda x: x["mass_fractions"].reverse(),
            lambda x: x["mass_fractions"].__setitem__(0, ["AL", 0.03]),
            lambda x: x.__setitem__("temperature_k", 2001.0),
            lambda x: x["mass_fractions"].__setitem__(6, ["FE", 0.0]),
        ):
            changed = copy.deepcopy(value); mutate(changed)
            with self.assertRaises(bridge.BridgeReject): bridge.parse_request(bridge.canonical(changed))


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.payload, self.mass, self.temperature = request_payload()
        self.envelope = {
            "schema_version": adapter.OUTPUT_SCHEMA, "status": "SUCCESS", "failure_code": None,
            "input_sha256": hashlib.sha256(self.payload).hexdigest(), "profile_id": "thermogar_patch",
            "controller_call_count": 1, "receipt": copy.deepcopy(CONTROL_RECEIPT),
            "acceptance": False, "release_eligible": False, "production_use": "DENIED",
        }

    def test_008_fe_balance_and_exact_defaults(self):
        self.assertEqual(self.mass["C"], 0.002)
        self.assertEqual(self.mass["CR"], 0.115)
        self.assertEqual(self.mass["FE"], 0.883)
        self.assertEqual(math.fsum(self.mass.values()), 1.0)

    def test_009_adapter_success_terminal_only(self):
        result = adapter.validate_success_envelope(self.envelope, self.payload, self.mass, self.temperature)
        self.assertEqual(set(result), {"terminal_rows", "c15_observed", "control_point_proof"})
        self.assertFalse(result["c15_observed"])
        self.assertFalse(result["control_point_proof"])

    def test_010_dynamic_limitation_tamper(self):
        for path in (("receipt", "limitations"), ("receipt", "worker_response", "limitations")):
            changed = copy.deepcopy(self.envelope)
            target = changed
            for key in path: target = target[key]
            target[0] = "NUMERICAL_ZERO_FLOOR_NOT_APPLIED_TO_THIS_REQUEST"
            with self.assertRaises(adapter.SteelAdapterError): adapter.validate_success_envelope(changed, self.payload, self.mass, self.temperature)

    def test_011_phase_fraction_c15_tamper(self):
        for change in ("fraction", "order", "c15", "count", "sum", "scope"):
            changed = copy.deepcopy(self.envelope)
            worker = changed["receipt"]["worker_response"]
            if change == "fraction": worker["terminal_phase_rows"][0]["fraction"] = -1.0
            elif change == "order": worker["terminal_phase_rows"].reverse()
            elif change == "c15": worker["c15_present_in_terminal_rows"] = True
            elif change == "count": worker["terminal_phase_row_count"] += 1
            elif change == "sum": worker["phase_fraction_sum"] = 0.5
            else: worker["c15_scope_included"] = False
            with self.assertRaises(adapter.SteelAdapterError): adapter.validate_success_envelope(changed, self.payload, self.mass, self.temperature)

    def test_011b_recomputed_delta_and_numeric_rows_tamper(self):
        changed = copy.deepcopy(self.envelope)
        changed["receipt"]["worker_response"]["runtime_effective_mole_fractions"][0][1] = 1e-6
        with self.assertRaises(adapter.SteelAdapterError):
            adapter.validate_success_envelope(changed, self.payload, self.mass, self.temperature)
        with self.assertRaises(adapter.SteelAdapterError):
            adapter.parse_canonical(b'{"x":1e999}\n')

    def test_011c_science_axis_projection_tamper(self):
        mutations = {
            "api": lambda w: w.__setitem__("scientific_api", "other"),
            "pdens": lambda w: w.__setitem__("pdens", 50),
            "solver_order": lambda w: w["solver_component_axis"].reverse(),
            "solver_count": lambda w: w.__setitem__("solver_component_count", 99),
            "solver_hash": lambda w: w.__setitem__("solver_component_sha256", "0" * 64),
            "dataset_axis": lambda w: w["dataset_nonvacant_component_axis"].reverse(),
            "dataset_count": lambda w: w.__setitem__("dataset_nonvacant_component_count", 99),
            "dataset_hash": lambda w: w.__setitem__("dataset_nonvacant_component_sha256", "0" * 64),
            "phase_order": lambda w: w["projected_active_phases"].reverse(),
            "phase_count": lambda w: w.__setitem__("projected_active_phase_count", 99),
            "phase_hash": lambda w: w.__setitem__("projected_active_phase_sha256", "0" * 64),
            "phase_unknown": lambda w: w["projected_active_phases"].__setitem__(0, "UNKNOWN"),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                changed = copy.deepcopy(self.envelope)
                mutate(changed["receipt"]["worker_response"])
                with self.assertRaises(adapter.SteelAdapterError):
                    adapter.validate_success_envelope(changed, self.payload, self.mass, self.temperature)

    def test_011d_coordinates_simplex_bulk_residual_tamper(self):
        mutations = {
            "coordinate_order": lambda w: w["terminal_phase_rows"][0]["chemical_coordinates"].reverse(),
            "inactive_nonzero": lambda w: w["terminal_phase_rows"][0]["chemical_coordinates"][0].__setitem__(1, 1e-6),
            "simplex": lambda w: w["terminal_phase_rows"][0]["chemical_coordinates"][2].__setitem__(1, 0.5),
            "bulk": lambda w: w["runtime_effective_bulk_mole_fractions"][2].__setitem__(1, 0.5),
            "residual": lambda w: w["component_bulk_absolute_residuals"][2].__setitem__(1, 0.5),
            "max_residual": lambda w: w.__setitem__("max_component_bulk_absolute_residual", 0.5),
            "vacancy": lambda w: w["terminal_phase_rows"][0].__setitem__("vacancy_coordinate", 0.1),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                changed = copy.deepcopy(self.envelope)
                mutate(changed["receipt"]["worker_response"])
                with self.assertRaises(adapter.SteelAdapterError):
                    adapter.validate_success_envelope(changed, self.payload, self.mass, self.temperature)

    def test_012_fake_subprocess_and_stale_late_reject(self):
        output = adapter.canonical(self.envelope)
        def runner(*args, **kwargs):
            self.assertFalse(kwargs["shell"]); self.assertLessEqual(len(kwargs["input"]), 16384)
            self.assertEqual(len(adapter.ACTIVE_HELD_PINS), 2)
            self.assertTrue(all(not pin.closed for pin in adapter.ACTIVE_HELD_PINS))
            with self.assertRaises(OSError):
                open(adapter.BRIDGE, "r+b").close()
            return subprocess.CompletedProcess(args[0], 0, output, b"")
        pin = adapter.verify_pins()
        expected = adapter.input_signature(dict(adapter.DEFAULT_WT_PERCENT), 1200.0, pin)
        result = adapter.run_diagnostic(dict(adapter.DEFAULT_WT_PERCENT), 1200.0, process_runner=runner, current_signature=lambda: expected)
        self.assertEqual(result["signature"], expected)
        with self.assertRaises(adapter.SteelAdapterError):
            adapter.run_diagnostic(dict(adapter.DEFAULT_WT_PERCENT), 1200.0, process_runner=runner, current_signature=lambda: "0" * 64)
        self.assertEqual(adapter.ACTIVE_HELD_PINS, [])

    def test_012b_held_pin_fail_before_spawn_and_close_on_runner_error(self):
        calls = [0]
        def runner(*_args, **_kwargs):
            calls[0] += 1
            raise subprocess.SubprocessError("secret")
        with self.assertRaises(adapter.SteelAdapterError):
            adapter.run_diagnostic(dict(adapter.DEFAULT_WT_PERCENT), 1200.0, process_runner=runner)
        self.assertEqual(calls[0], 1)
        self.assertEqual(adapter.ACTIVE_HELD_PINS, [])
        calls[0] = 0
        with mock.patch.object(adapter, "HeldPin", side_effect=adapter.SteelAdapterError("blocked")):
            with self.assertRaises(adapter.SteelAdapterError):
                adapter.run_diagnostic(dict(adapter.DEFAULT_WT_PERCENT), 1200.0, process_runner=runner)
        self.assertEqual(calls[0], 0)
        self.assertEqual(adapter.ACTIVE_HELD_PINS, [])

    def test_013_busy_lock_rejects(self):
        adapter.RUN_LOCK.acquire()
        try:
            with self.assertRaises(adapter.SteelAdapterError): adapter.run_diagnostic(dict(adapter.DEFAULT_WT_PERCENT), 1200.0)
        finally: adapter.RUN_LOCK.release()

    def test_014_output_duplicate_nonfinite_extra_and_binding_tamper(self):
        with self.assertRaises(adapter.SteelAdapterError): adapter.parse_canonical(b'{"x":1,"x":2}\n')
        with self.assertRaises(adapter.SteelAdapterError): adapter.parse_canonical(b'{"x":NaN}\n')
        for field, bad in (("input_sha256", "0" * 64), ("controller_call_count", 2), ("profile_id", "x"), ("release_eligible", True)):
            changed = copy.deepcopy(self.envelope); changed[field] = bad
            with self.assertRaises(adapter.SteelAdapterError): adapter.validate_success_envelope(changed, self.payload, self.mass, self.temperature)

    def test_015_gate_control_point_view_only(self):
        result = adapter.load_control_point_view()
        self.assertTrue(result["control_point_proof"])
        self.assertTrue(result["terminal_rows"])
        changed = dict(adapter.DEFAULT_WT_PERCENT); changed["C"] = 0.21
        self.assertNotEqual(adapter.build_request(changed, 1200.0)[0], self.payload)

    def test_016_pin_and_gate_card_exact(self):
        signature = adapter.verify_pins()
        self.assertEqual(len(signature), 64)
        gate_card = [card for card in adapter.PIN_CARDS if card[0] == adapter.GATE]
        self.assertEqual(gate_card[0][1:], (11436, "30351cd5a563ca1ccab844ca0984feb1e82a0b89a0c0dcbb04ac21278ba1b1ce"))


class UiStaticAndAppTests(unittest.TestCase):
    def test_017_ui_compact_and_old_blocks_absent(self):
        wrapper = (APP / "ThermoGar_steel_app.py").read_text("utf-8")
        component = (APP / "thermogar_steel_section.py").read_text("utf-8")
        self.assertIn("ThermoGar · Сталь", wrapper)
        self.assertIn("Рассчитать локально", component)
        for forbidden in ("RESEARCH SOFTWARE", "NO EXPERIMENTAL", "Статус выпуска", "NE-02", "inventory"):
            self.assertNotIn(forbidden, wrapper)
            self.assertNotIn(forbidden, component)

    def test_018_initial_ast_has_no_bridge_or_science_call(self):
        wrapper = (APP / "ThermoGar_steel_app.py").read_text("utf-8")
        component = (APP / "thermogar_steel_section.py").read_text("utf-8")
        trees = (ast.parse(wrapper), ast.parse(component))
        calls = [
            node
            for tree in trees
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        ]
        self.assertFalse(any(isinstance(node.func, ast.Name) and node.func.id == "run_fe_equilibrium_witness" for node in calls))
        self.assertNotIn("subprocess", wrapper + component)
        self.assertNotIn("st.set_page_config", component)
        self.assertNotIn("st.title", component)
        self.assertEqual(component.count("steel.run_diagnostic("), 1)

    def test_019_streamlit_apptest_initial_compact(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Streamlit AppTest unavailable")
        app = AppTest.from_file(str(APP / "ThermoGar_steel_app.py")).run(timeout=20)
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "ThermoGar · Сталь")
        self.assertEqual(app.caption[0].value, "Локальный диагностический расчёт; не является квалификацией материала, производственным режимом или подтверждением свойств.")
        self.assertEqual(app.button[0].label, "Рассчитать локально")
        self.assertEqual(len(app.number_input), 25)
        rendered = " ".join(str(item.value) for item in (*app.title, *app.caption, *app.markdown))
        self.assertNotIn("NE-02", rendered)
        self.assertEqual(len(app.dataframe), 1)
        table = app.dataframe[0].value
        self.assertEqual(list(table["Фаза"]), ["FCC_A1", "M23C6"])
        self.assertEqual(list(table["Доля"]), [0.9954977144229682, 0.004502285653343282])
        self.assertIn("C15_LAVES не наблюдается", rendered)
        carbon = next(item for item in app.number_input if item.label == "C, wt%")
        carbon.set_value(0.21).run(timeout=20)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe), 0)

    def test_020_streamlit_apptest_export_guard_fails_closed(self):
        try:
            import streamlit as st
            from streamlit import config
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Streamlit AppTest unavailable")
        previous = st.get_option("client.disableDataExport")
        try:
            config.set_option("client.disableDataExport", False)
            app = AppTest.from_file(str(APP / "ThermoGar_steel_app.py")).run(
                timeout=20
            )
        finally:
            config.set_option("client.disableDataExport", previous)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 1)
        self.assertIn("Запуск остановлен", app.error[0].value)
        self.assertEqual(len(app.title), 0)
        self.assertEqual(len(app.number_input), 0)
        self.assertEqual(len(app.dataframe), 0)
        self.assertEqual(len(app.button), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
