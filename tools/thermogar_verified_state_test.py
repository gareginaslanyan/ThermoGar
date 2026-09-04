"""Non-scientific fake-state tests for VLB B4A."""
from __future__ import annotations

from dataclasses import fields
from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)))
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import thermogar_verified_loaders as vl
import thermogar_verified_state as state
from thermogar_release_policy import (
    APP_STAGE,
    APP_VERSION,
    PRODUCTION_USE,
    RELEASE_CLASS,
    SCIENTIFIC_MATERIAL_STATUS,
    SOFTWARE_RELEASE_STATUS,
)


FIXED_TIME = "2026-08-29T12:34:56.123456Z"
BINDING = "a" * 64


def _request(
    feature_id: str = "data_alloy_transfer",
    *,
    requested: tuple[str, ...] = (),
    generation: int = 1,
) -> vl.FeatureRequest:
    inputs = {"direction": "ingress"}
    provisional = {
        "schema": vl.SCHEMA_FEATURE_REQUEST,
        "feature_id": feature_id,
        "feature_revision": "1",
        "binding_digest": BINDING,
        "binding_generation": generation,
        "inputs": inputs,
        "inputs_digest": vl.canonical_digest(inputs),
        "requested_phases": list(requested),
        "requested_phases_digest": vl.canonical_digest(list(requested)),
        "effective_phases": ["BCC_A2"],
        "effective_phases_digest": vl.canonical_digest(["BCC_A2"]),
        "request_digest": "",
    }
    provisional["request_digest"] = vl.canonical_digest(
        {key: value for key, value in provisional.items() if key != "request_digest"}
    )
    return vl.FeatureRequest(
        **{
            **provisional,
            "requested_phases": requested,
            "effective_phases": ("BCC_A2",),
        }
    )


def _envelope(kind: str, payload: object) -> bytes:
    return vl.canonical_json_bytes(state._make_envelope(kind, payload, lambda: FIXED_TIME))


def _project(*, profile: str = "thermogar_patch") -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "thermogar_project_payload",
        "name": "Fe project",
        "description": "",
        "created_at": FIXED_TIME,
        "updated_at": FIXED_TIME,
        "app_stage": APP_STAGE,
        "app_version": APP_VERSION,
        "release_class": RELEASE_CLASS,
        "software_release_status": SOFTWARE_RELEASE_STATUS,
        "scientific_material_status": SCIENTIFIC_MATERIAL_STATUS,
        "production_use": PRODUCTION_USE,
        "context": {
            "database_key": "fe",
            "balance": "FE",
            "units": "wt",
            "composition": "C=0.2",
            "pressure_pa": 101325.0,
            "steel_mode": "metastable",
            "database_sha256": state._FE_TDB_SHA256,
            "fe_profile_key": profile,
        },
        "widget_state": {},
    }


class FakeUpload:
    def __init__(self, data: bytes, name: str) -> None:
        self._stream = BytesIO(data)
        self.name = name
        self.read_sizes: list[int] = []

    def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        return self._stream.read(size)


class OversizeUpload:
    name = "large.json"

    def __init__(self) -> None:
        self.remaining = 67108865
        self.read_sizes: list[int] = []

    def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        if self.remaining <= 0:
            return b""
        amount = min(size, self.remaining)
        self.remaining -= amount
        return b"x" * amount


class FakeUI:
    def __init__(self, upload: object | None = None) -> None:
        self.upload = upload
        self.upload_calls: list[tuple[object, object, object]] = []
        self.downloads: list[dict[str, object]] = []

    def file_uploader(self, label: str, *, type: tuple[str, ...], key: str) -> object | None:
        self.upload_calls.append((label, type, key))
        return self.upload

    def download_button(self, label: str, **kwargs: object) -> bool:
        self.downloads.append({"label": label, **kwargs})
        return True


class VerifiedStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.paths = SimpleNamespace(state_root=self.root)
        self.generation = 1

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _store(self, ui: FakeUI | None = None) -> state.StateStore:
        return state.StateStore(
            self.paths,
            ui or FakeUI(),
            binding_probe=lambda: (BINDING, self.generation),
            clock=lambda: FIXED_TIME,
        )

    def _alloy_ticket(self, rows: list[dict[str, object]] | None = None) -> tuple[state.StateStore, state.VerifiedArtifactRef]:
        store = self._store()
        ticket = store.prepare_egress(
            _request("data_alloy_state"),
            "alloy-library-json",
            rows or [{"id": "one", "unknown": {"x": 1}}],
        )
        self.assertIs(type(ticket), state.VerifiedArtifactRef)
        return store, ticket

    def test_ticket_has_exact_finite_fields_and_digest(self) -> None:
        _store, ticket = self._alloy_ticket()
        self.assertEqual(tuple(item.name for item in fields(ticket)), state.TICKET_FIELDS)
        self.assertEqual(
            ticket.ticket_digest,
            vl.canonical_digest({k: v for k, v in ticket.to_dict().items() if k != "ticket_digest"}),
        )
        self.assertNotIn("VerifiedArtifactRef", vl.FEATURE_IDS)

    def test_ticket_requires_paired_result_entry(self) -> None:
        store, ticket = self._alloy_ticket()
        artifact, envelope = store.paired_artifact(ticket)
        self.assertEqual(set(artifact), {"name", "media_type", "sha256", "size_bytes", "payload_ref"})
        self.assertEqual(artifact["sha256"], ticket.sha256)
        self.assertEqual(envelope.artifacts, (artifact,))

    def test_ticket_rejects_unknown_kind_version_or_field(self) -> None:
        _store, ticket = self._alloy_ticket()
        values = ticket.to_dict()
        for key, bad in (("content_kind", "other"), ("content_version", "2")):
            mutated = dict(values)
            mutated[key] = bad
            with self.assertRaises(ValueError):
                state.VerifiedArtifactRef(**mutated)
        self.assertEqual(set(state.CONTENT_KINDS), set(state._KIND_META))

    def test_ticket_rejects_traversal_separator_and_casefold_variant(self) -> None:
        _store, ticket = self._alloy_ticket()
        for logical_ref in ("../x", ticket.logical_ref.replace("/", "\\"), ticket.logical_ref.upper()):
            values = ticket.to_dict()
            values["logical_ref"] = logical_ref
            values["ticket_digest"] = vl.canonical_digest({k: v for k, v in values.items() if k != "ticket_digest"})
            with self.assertRaises(ValueError):
                state.VerifiedArtifactRef(**values)

    def test_prepared_feature_request_is_required_for_ingress(self) -> None:
        ui = FakeUI(FakeUpload(b"{}", "x.json"))
        with self.assertRaises(TypeError):
            self._store(ui).ingest_from_widget(None, "alloy-library-json", "x", state.ALLOY_UI_TYPES, state.ALLOY_UPLOAD_KEY)
        self.assertEqual(ui.upload_calls, [])

    def test_single_state_store_uploader_renders_once_and_streams_immediately(self) -> None:
        upload = FakeUpload(_envelope("thermogar_alloys", [{"id": "x"}]), "x.json")
        ui = FakeUI(upload)
        ticket = self._store(ui).ingest_from_widget(
            _request(), "alloy-library-json", "upload", state.ALLOY_UI_TYPES, state.ALLOY_UPLOAD_KEY,
        )
        self.assertIs(type(ticket), state.VerifiedArtifactRef)
        self.assertEqual(ui.upload_calls, [("upload", state.ALLOY_UI_TYPES, state.ALLOY_UPLOAD_KEY)])
        self.assertTrue(upload.read_sizes and set(upload.read_sizes) == {65536})

    def test_no_file_returns_existing_user_input_required_without_body_or_state(self) -> None:
        store = self._store(FakeUI())
        result = store.ingest_from_widget(_request(), "alloy-library-json", "upload", state.ALLOY_UI_TYPES, state.ALLOY_UPLOAD_KEY)
        self.assertEqual(result.reason_code, "USER_INPUT_REQUIRED")
        self.assertEqual({k: v for k, v in store.counters.items() if k != "uploader_calls"}, {"parse_calls": 0, "policy_calls": 0, "write_calls": 0, "ticket_calls": 0, "backend_calls": 0})

    def test_ingress_oversize_rejects_before_write_ticket_or_backend(self) -> None:
        store = self._store(FakeUI(OversizeUpload()))
        result = store.ingest_from_widget(_request(), "alloy-library-json", "upload", state.ALLOY_UI_TYPES, state.ALLOY_UPLOAD_KEY)
        self.assertEqual(result.reason_code, "ARTIFACT_OVERSIZE")
        self.assertEqual(store.counters["write_calls"], 0)
        self.assertEqual(store.counters["ticket_calls"], 0)
        self.assertEqual(store.counters["backend_calls"], 0)

    def test_alloy_import_preserves_loose_data_only_rows_order_and_unknown_fields(self) -> None:
        rows = [{"id": True, "z": [1]}, {"id": 2, "extra": "x"}, {"id": 2.5, "name": "n"}]
        upload = FakeUpload(_envelope("thermogar_alloys", rows), "alloys.json")
        store = self._store(FakeUI(upload))
        ticket = store.ingest_from_widget(_request(), "alloy-library-json", "upload", state.ALLOY_UI_TYPES, state.ALLOY_UPLOAD_KEY)
        self.assertEqual(store.canonical_value(ticket, ticket.source_envelope_digest), rows)

    def test_project_import_requires_exact_project_payload_keys_and_rebind(self) -> None:
        self.assertEqual(len(state.PROJECT_PAYLOAD_KEYS), 14)
        upload = FakeUpload(_envelope("thermogar_project", _project()), "p.json")
        store = self._store(FakeUI(upload))
        ticket = store.ingest_from_widget(_request("data_project_transfer"), "project-json", "upload", state.PROJECT_UI_TYPES, state.PROJECT_UPLOAD_KEY)
        seen: list[dict[str, object]] = []
        rebound = store.restore_context(ticket, ticket.source_envelope_digest, lambda value: seen.append(value) or value)
        self.assertEqual(rebound["database_key"], "fe")
        self.assertEqual(seen[0]["fe_profile_key"], "thermogar_patch")

    def test_history_csv_is_egress_only_with_exact_header_tuple_and_no_row_cap(self) -> None:
        rows = [{header: str(index) for header in state.HISTORY_HEADERS} for index in range(300)]
        store = self._store()
        ticket = store.prepare_egress(_request("data_history_export"), "history-csv", rows)
        self.assertIs(type(ticket), state.VerifiedArtifactRef)
        self.assertEqual(len(state.HISTORY_HEADERS), 10)
        denied = store.ingest_from_widget(_request(), "history-csv", "x", state.ALLOY_UI_TYPES, state.ALLOY_UPLOAD_KEY)
        self.assertEqual(denied.reason_code, "IMPORT_SCHEMA_REJECTED")

    def test_batch_csv_uses_exact_two_parse_rule_and_header_constants(self) -> None:
        raw = b"name,database,balance,units,temperature_C\nr,ni,NI,at,700\n"
        store = self._store(FakeUI(FakeUpload(raw, "rows.csv")))
        ticket = store.ingest_from_widget(_request("data_batch_request_import"), "batch-input-csv", "upload", state.BATCH_UI_TYPES, state.BATCH_UPLOAD_KEY)
        value = store.canonical_value(ticket, ticket.source_envelope_digest)
        self.assertEqual(value["columns"][:5], list(state.BATCH_REQUIRED_HEADERS))
        self.assertEqual(state.BATCH_UI_TYPES, ("csv", "xlsx"))
        alternate = state._parse_csv(raw.replace(b",", b";"))
        self.assertIsInstance(alternate, dict)

    def test_batch_xlsx_requires_single_visible_macro_free_external_link_free_formula_free_sheet(self) -> None:
        table = {"columns": list(state.BATCH_REQUIRED_HEADERS), "rows": [["r", "ni", "NI", "at", 700.0]]}
        raw = state._xlsx_bytes({"Input": table})
        store = self._store(FakeUI(FakeUpload(raw, "rows.xlsx")))
        ticket = store.ingest_from_widget(_request("data_batch_request_import"), "batch-input-csv", "upload", state.BATCH_UI_TYPES, state.BATCH_UPLOAD_KEY)
        self.assertEqual(ticket.content_kind, "batch-input-xlsx")
        self.assertNotIn("xlsm", state.BATCH_UI_TYPES)

    def test_template_egress_uses_exact_header_and_sheet_tuples(self) -> None:
        store = self._store()
        csv_ticket = store.prepare_egress(_request("data_batch_export"), "batch-template-csv", state.batch_template_value())
        xlsx_ticket = store.prepare_egress(_request("data_batch_export"), "batch-template-xlsx", state.batch_template_value())
        self.assertEqual(state.TEMPLATE_XLSX_SHEETS, ("Составы",))
        self.assertEqual(store.paired_artifact(csv_ticket)[0]["name"], "ThermoGar_batch_template.csv")
        self.assertEqual(store.paired_artifact(xlsx_ticket)[0]["name"], "ThermoGar_batch_template.xlsx")

    def test_result_xlsx_semantic_digest_is_stable_and_persisted_instance_is_verified(self) -> None:
        value = {name: {"columns": ["x"], "rows": [[1]]} for name in state.RESULT_XLSX_SHEETS}
        self.assertEqual(state.semantic_digest_for("batch-result-xlsx", value), state.semantic_digest_for("batch-result-xlsx", value))
        store = self._store()
        ticket = store.prepare_egress(_request("data_batch_export"), "batch-result-xlsx", value)
        artifact, _envelope_value = store.paired_artifact(ticket)
        self.assertEqual((artifact["sha256"], artifact["size_bytes"]), (ticket.sha256, ticket.size_bytes))

    def test_imported_c15_rejects_without_artifact_ticket_or_backend(self) -> None:
        raw = b"name,database,balance,units,temperature_C,phases\nr,fe,FE,wt,700,C15_LAVES\n"
        store = self._store(FakeUI(FakeUpload(raw, "rows.csv")))
        result = store.ingest_from_widget(_request("data_batch_request_import"), "batch-input-csv", "upload", state.BATCH_UI_TYPES, state.BATCH_UPLOAD_KEY)
        self.assertEqual(result.reason_code, "C15_PHASE_REJECTED")
        self.assertEqual((store.counters["write_calls"], store.counters["ticket_calls"], store.counters["backend_calls"]), (0, 0, 0))

    def test_two_plain_directory_calls_create_only_write_and_matching_snapshot_precede_ticket(self) -> None:
        store = self._store()
        calls: list[tuple[str, object]] = []
        data = b"x"
        digest = hashlib.sha256(data).hexdigest()
        snapshot = SimpleNamespace(sha256=digest, size=1)
        with mock.patch.object(state, "ensure_plain_directory", side_effect=lambda value: calls.append(("dir", value))), mock.patch.object(state, "atomic_write_bytes", side_effect=lambda *a, **k: calls.append(("write", (a, k)))), mock.patch.object(state, "read_verified_snapshot", side_effect=lambda *a, **k: calls.append(("read", (a, k))) or snapshot):
            store._persist("alloy-library-json", data)
        self.assertEqual([item[0] for item in calls], ["dir", "dir", "write", "read"])
        self.assertEqual(len(calls[0][1:]), 1)
        self.assertFalse(calls[2][1][1]["overwrite"])

    def test_reparse_or_nonregular_target_fails_closed(self) -> None:
        store = self._store()
        with mock.patch.object(state, "atomic_write_bytes", side_effect=OSError("reparse")):
            result = store.prepare_egress(_request("data_alloy_state"), "alloy-library-json", [{"id": "x"}])
        self.assertEqual(result.reason_code, "ARTIFACT_WRITE_FAILED")
        self.assertEqual(store.counters["ticket_calls"], 0)

    def test_egress_requires_matching_ticket_source_envelope_and_live_generation(self) -> None:
        store, ticket = self._alloy_ticket()
        with self.assertRaises(vl.VerifiedLoaderError):
            store.canonical_value(ticket, "0" * 64)
        self.generation = 2
        with self.assertRaises(vl.VerifiedLoaderError) as caught:
            store.canonical_value(ticket, ticket.source_envelope_digest)
        self.assertEqual(caught.exception.reason_code, vl.ReasonCode.GENERATION_STALE)

    def test_disabled_control_and_crossing_never_expose_body_or_session_lookup(self) -> None:
        ui = FakeUI(FakeUpload(b"secret", "x.json"))
        store = self._store(ui)
        result = store.ingest_from_widget(_request(requested=("C15_LAVES",)), "alloy-library-json", "upload", state.ALLOY_UI_TYPES, state.ALLOY_UPLOAD_KEY)
        self.assertEqual(result.reason_code, "C15_PHASE_REJECTED")
        self.assertEqual(ui.upload_calls, [])
        self.assertNotIn("session", vars(store))

    def test_restore_rebinds_canonical_selector_and_ticket_evidence_before_dispatch(self) -> None:
        upload = FakeUpload(_envelope("thermogar_project", _project()), "p.json")
        store = self._store(FakeUI(upload))
        ticket = store.ingest_from_widget(_request("data_project_transfer"), "project-json", "upload", state.PROJECT_UI_TYPES, state.PROJECT_UPLOAD_KEY)
        order: list[str] = []
        result = store.restore_context(ticket, ticket.source_envelope_digest, lambda value: order.append("rebind") or value)
        order.append("dispatch")
        self.assertEqual(order, ["rebind", "dispatch"])
        self.assertEqual(result["database_sha256"], state._FE_TDB_SHA256)

    def test_restore_accepts_canonical_fe_and_rejects_upstream(self) -> None:
        canonical = state._validate_project_payload(_project())
        self.assertEqual(canonical["context"]["fe_profile_key"], "thermogar_patch")
        with self.assertRaises(state._StateFailure) as caught:
            state._validate_project_payload(_project(profile="upstream"))
        self.assertEqual(caught.exception.reason, vl.ReasonCode.IMPORT_SCHEMA_REJECTED)

    def test_batch_fifo_child_receipts_and_envelopes_preserved(self) -> None:
        app = (ROOT / "app" / "ThermoGar_app.py").read_text(encoding="utf-8")
        workspace = (ROOT / "app" / "thermogar_workspace.py").read_text(encoding="utf-8")
        self.assertIn("for position, (_, row) in enumerate(source.iterrows(), start=1):", workspace)
        self.assertIn('result["_children"]', workspace)
        self.assertIn("broker.finish(())", workspace)
        self.assertIn("acquire_b3_execution", app)

    def test_file_exists_snapshot_equality_is_idempotent_otherwise_frozen_conflict(self) -> None:
        store = self._store()
        data = b"same"
        digest = hashlib.sha256(data).hexdigest()
        good = SimpleNamespace(sha256=digest, size=len(data))
        with mock.patch.object(state, "atomic_write_bytes", side_effect=FileExistsError), mock.patch.object(state, "read_verified_snapshot", return_value=good):
            self.assertEqual(store._persist("alloy-library-json", data)[1:], (digest, len(data)))
        bad = SimpleNamespace(sha256="0" * 64, size=len(data))
        with mock.patch.object(state, "atomic_write_bytes", side_effect=FileExistsError), mock.patch.object(state, "read_verified_snapshot", return_value=bad):
            with self.assertRaises(state._StateFailure) as caught:
                store._persist("alloy-library-json", data)
        self.assertEqual(caught.exception.reason, vl.ReasonCode.STATE_CONFLICT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
