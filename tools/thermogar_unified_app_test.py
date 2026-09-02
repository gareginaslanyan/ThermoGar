from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
SUBJECT = APP / "ThermoGar_app.py"
WORKSPACE = APP / "thermogar_workspace.py"
COMPATIBILITY_ENTRYPOINT = APP / "ThermoGar_unified_app.py"
LAUNCHER = ROOT / "RUN_THERMOGAR_WINDOWS.cmd"
TOP_LEVEL_TABS = [
    "Расчёты",
    "Диаграммы",
    "Затвердевание",
    "Энергии",
    "Свойства",
    "Кинетика",
    "Проекты и данные",
]
TOP_LEVEL_APPTEST_INDICES = [0, 4, 9, 10, 14, 20, 26]


def _literal_tab_lists(source: str) -> list[list[str]]:
    tree = ast.parse(source)
    result: list[list[str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "tabs":
            continue
        if not node.args or not isinstance(node.args[0], (ast.List, ast.Tuple)):
            continue
        values: list[str] = []
        for item in node.args[0].elts:
            if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
                break
            values.append(item.value)
        else:
            result.append(values)
    return result


def _rendered_text(app) -> str:
    return " ".join(
        str(item.value)
        for kind in (
            "title", "caption", "markdown", "subheader",
            "warning", "info", "error",
        )
        for item in app.get(kind)
    )


class OnePageProductTests(unittest.TestCase):
    def test_001_one_page_entrypoint_and_launcher_have_no_product_routes(self):
        main_source = SUBJECT.read_text("utf-8")
        workspace_source = WORKSPACE.read_text("utf-8")
        compatibility_source = COMPATIBILITY_ENTRYPOINT.read_text("utf-8")
        launcher_source = LAUNCHER.read_text("utf-8")
        self.assertIn(TOP_LEVEL_TABS, _literal_tab_lists(main_source))
        self.assertNotIn("thermogar_steel_section", main_source)
        self.assertNotIn("render_steel_section", main_source)
        self.assertNotIn("steel_tab", main_source)
        self.assertNotIn("Сталь", TOP_LEVEL_TABS)
        self.assertIn('initial_sidebar_state="collapsed"', main_source)
        self.assertIn('"Настройки расчётных разделов"', main_source)
        self.assertIn('"Стали и Fe-сплавы — mc_fe 2.062"', main_source)
        self.assertIn(
            'st.session_state["thermogar_database_key"] = "fe"',
            main_source,
        )
        self.assertIn(
            'st.session_state["thermogar_fe_profile"] = FE_PROFILE_CANONICAL',
            main_source,
        )
        self.assertIn(
            'st.session_state.get("thermogar_fe_profile") '
            '!= FE_PROFILE_CANONICAL',
            main_source,
        )
        database_loader_source = main_source[
            main_source.index("_DATABASE_SNAPSHOT_CACHE:"):
            main_source.index("PHYSICAL_DATABASE_PATH =")
        ]
        for token in (
            "with held_verified_snapshot(",
            "MAX_TDB_SNAPSHOT_BYTES",
            "snapshot.sha256",
            "snapshot.data",
            "parse_verified_utf8_snapshot(",
            'Database.from_file(source, fmt="tdb")',
            "cache_key = (expected_sha256, snapshot.sha256)",
            "database = _database_cache_commit(cache_key, database)",
        ):
            self.assertIn(token, database_loader_source)
        self.assertNotIn("Database(str(database_path))", database_loader_source)
        self.assertNotIn("file_sha256(database_path)", database_loader_source)
        self.assertNotIn(".resolve()", database_loader_source)
        self.assertNotIn("FE_PROFILE_EXPERIMENTAL", main_source)
        self.assertNotIn('"upstream_original"', main_source)
        self.assertIn("read_verified_utf8_text(", main_source)
        self.assertNotIn("def read_text(path: Path)", main_source)
        self.assertIn("restricted_fe_calculation_button(", main_source)
        self.assertEqual(main_source.count("restricted_fe_calculation_button("), 4)
        self.assertFalse(
            any("Статус функций" in tabs for tabs in _literal_tab_lists(main_source))
        )
        for source in (main_source, compatibility_source, launcher_source):
            self.assertNotIn("st.navigation", source)
            self.assertNotIn("st.Page", source)
            self.assertNotIn("/legacy", source)
            self.assertNotIn("Основная ThermoGar", source)
        self.assertIn(r"app\ThermoGar_app.py", launcher_source)
        self.assertNotIn("ThermoGar_unified_app.py", launcher_source)
        self.assertNotIn("ThermoGar_steel_app.py", launcher_source)
        for token in (
            "with held_verified_snapshot(",
            "snapshot.data.decode(\"utf-8-sig\")",
            "selected_snapshot_bytes",
            "data=selected_snapshot_bytes",
            "secure_move_no_overwrite(",
            "secure_archive_and_clear(",
        ):
            self.assertIn(token, workspace_source)
        for forbidden in (
            "selected_path.read_text(",
            "selected_path.replace(",
            "source.replace(backup)",
        ):
            self.assertNotIn(forbidden, workspace_source)

    def test_002_initial_apptest_has_exact_seven_sections_and_no_solver(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Streamlit AppTest unavailable")
        import pycalphad

        with mock.patch.object(
            pycalphad,
            "equilibrium",
            side_effect=AssertionError("initial render attempted equilibrium"),
        ) as equilibrium:
            app = AppTest.from_file(str(SUBJECT), default_timeout=120).run(
                timeout=120
            )
            self.assertFalse(app.exception)
            self.assertEqual([item.value for item in app.title], ["ThermoGar"])
            self.assertEqual(
                [app.tabs[index].label for index in TOP_LEVEL_APPTEST_INDICES],
                TOP_LEVEL_TABS,
            )
            self.assertEqual(len(app.get("page_link")), 0)
            self.assertNotIn(
                "Рассчитать локально", [button.label for button in app.button]
            )
            self.assertNotIn("Сталь", [tab.label for tab in app.tabs])
            database = next(
                item for item in app.selectbox if item.label == "База материалов"
            )
            self.assertEqual(database.value, "fe")
            self.assertEqual(
                app.session_state["thermogar_fe_profile"],
                "thermogar_patch",
            )
            app.run(timeout=120)
        equilibrium.assert_not_called()
        self.assertFalse(app.exception)
        self.assertEqual(
            next(
                item for item in app.selectbox if item.label == "База материалов"
            ).value,
            "fe",
        )
        self.assertEqual(
            app.session_state["thermogar_fe_profile"],
            "thermogar_patch",
        )
        rendered = _rendered_text(app)
        self.assertEqual(
            rendered.count("Fe-база thermogar_patch · C15_LAVES отключена"),
            1,
        )
        for forbidden in (
            "RESEARCH SOFTWARE",
            "NO EXPERIMENTAL VALIDATION",
            "production_use=DENIED",
            "Диагностическая mc_fe",
            "diagnostic-only",
            "NE-02",
            "NE-03",
            "NE-04",
            "inventory",
            "release surface",
            "Статус функций",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_003_fe_selection_is_patched_only_and_wires_all_seven_sections(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Streamlit AppTest unavailable")
        import pycalphad

        app = AppTest.from_file(str(SUBJECT), default_timeout=120)
        app.session_state["_thermogar_pending_context"] = {
            "database_key": "fe",
            "balance": "FE",
            "units": "wt",
            "composition": "C=0.20, CR=11.5, NI=0.7",
            "pressure_pa": 101325.0,
            "steel_mode": "metastable",
            "database_sha256": (
                "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612"
            ),
            "fe_profile_key": "thermogar_patch",
        }
        app.session_state["_thermogar_pending_context_label"] = "Fe project"
        with mock.patch.object(
            pycalphad,
            "equilibrium",
            side_effect=AssertionError("Fe selection attempted equilibrium"),
        ) as equilibrium:
            app.run(timeout=120)
        equilibrium.assert_not_called()
        self.assertFalse(app.exception)
        self.assertEqual(
            [app.tabs[index].label for index in TOP_LEVEL_APPTEST_INDICES],
            TOP_LEVEL_TABS,
        )
        self.assertEqual(
            next(item for item in app.selectbox if item.label == "База материалов").value,
            "fe",
        )
        self.assertNotIn("Профиль стальной базы", [item.label for item in app.selectbox])
        self.assertEqual(
            app.session_state["_thermogar_loaded_context"]["fe_profile_key"],
            "thermogar_patch",
        )
        self.assertEqual(
            app.session_state["_thermogar_loaded_context"]["database_sha256"],
            "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612",
        )
        rendered = _rendered_text(app)
        self.assertIn("Fe-база thermogar_patch · C15_LAVES отключена", rendered)
        self.assertNotIn("Фаза C15_LAVES и остальные её параметры сохранены", rendered)
        self.assertNotIn("модификация не квалифицирована", rendered)
        self.assertNotIn("апстрим без патча", rendered)

    def test_004_stale_database_falls_back_to_fe_and_profile_tamper_stops(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Streamlit AppTest unavailable")
        import pycalphad

        stale = AppTest.from_file(str(SUBJECT), default_timeout=120)
        stale.session_state["thermogar_database_key"] = "stale_database"
        with mock.patch.object(
            pycalphad,
            "equilibrium",
            side_effect=AssertionError("stale fallback attempted equilibrium"),
        ) as equilibrium:
            stale.run(timeout=120)
        equilibrium.assert_not_called()
        self.assertFalse(stale.exception)
        self.assertEqual(
            next(
                item for item in stale.selectbox if item.label == "База материалов"
            ).value,
            "fe",
        )
        self.assertEqual(
            stale.session_state["thermogar_fe_profile"],
            "thermogar_patch",
        )
        self.assertTrue(
            any(
                "Сохранённый выбор базы не распознан" in item.value
                for item in stale.warning
            )
        )

        tampered = AppTest.from_file(str(SUBJECT), default_timeout=120)
        tampered.session_state["thermogar_database_key"] = "fe"
        tampered.session_state["thermogar_fe_profile"] = "upstream_original"
        with mock.patch.object(
            pycalphad,
            "equilibrium",
            side_effect=AssertionError("tampered profile attempted equilibrium"),
        ) as tampered_equilibrium:
            tampered.run(timeout=120)
        tampered_equilibrium.assert_not_called()
        self.assertFalse(tampered.exception)
        self.assertTrue(
            any("Fe-контекст отклонён" in item.value for item in tampered.error)
        )
        self.assertEqual(len(tampered.tabs), 0)

    def test_005_main_export_guard_stays_fail_closed(self):
        main_source = SUBJECT.read_text("utf-8")
        self.assertLess(
            main_source.index('st.get_option("client.disableDataExport")'),
            main_source.index("st.title(DISPLAY_APP_NAME)"),
        )
        try:
            import streamlit as st
            from streamlit import config
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Streamlit AppTest unavailable")
        previous = st.get_option("client.disableDataExport")
        try:
            config.set_option("client.disableDataExport", False)
            app = AppTest.from_file(str(SUBJECT), default_timeout=120).run(
                timeout=120
            )
        finally:
            config.set_option("client.disableDataExport", previous)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 1)
        self.assertIn("Запуск остановлен", app.error[0].value)
        self.assertEqual(len(app.title), 0)
        self.assertEqual(len(app.dataframe), 0)
        self.assertEqual(len(app.button), 0)

    def test_006_global_policy_stays_frozen_while_exact_fe_core_is_independent(self):
        sys.path.insert(0, str(APP))
        import thermogar_release_policy as policy

        self.assertFalse(policy.CALCULATIONS_ENABLED)
        self.assertEqual(policy.PRODUCTION_USE, "DENIED")
        domain_contract = json.loads(
            (ROOT / "configs" / "ne04_database_domains.json").read_text("utf-8")
        )
        self.assertFalse(domain_contract["calculations_enabled"])
        self.assertEqual(domain_contract["diagnostic_database_keys"], ["fe"])
        self.assertEqual(
            domain_contract["databases"]["fe"]["diagnostic_identity"]["working_profile"],
            "thermogar_patch",
        )
        witness = json.loads(
            (ROOT / "configs" / "ne04_fe_equilibrium_witness_v1.json").read_text(
                "utf-8"
            )
        )
        patched = witness["runtime_profiles"]["thermogar_patch"]
        self.assertEqual(
            patched["relative_path"],
            "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb",
        )
        self.assertEqual(
            patched["sha256"],
            "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612",
        )
        phase_contract = witness["request_contract"]["phase_selection"]
        self.assertTrue(phase_contract["c15_laves_mandatory"])
        self.assertEqual(phase_contract["exclusions"], [])
        self.assertIn("C15_LAVES", phase_contract["phases"])
        guard_source = (APP / "thermogar_database_guard.py").read_text("utf-8")
        self.assertIn('SUSPECT_PHASE = "C15_LAVES"', guard_source)
        self.assertIn("one active reciprocal C15_LAVES parameter is commented", guard_source)
        release_ui = (APP / "thermogar_release_ui.py").read_text("utf-8")
        self.assertIn("if not CALCULATIONS_ENABLED:", release_ui)
        main_source = SUBJECT.read_text("utf-8")
        self.assertIn("restricted_fe_calculation_button(", main_source)
        self.assertIn(
            'if database_key == "fe":',
            main_source[
                main_source.index("def restricted_fe_calculation_button"):
                main_source.index("def restricted_fe_three_axis_points")
            ],
        )

    def test_007_exact_fe_clicks_use_only_the_restricted_executor(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Streamlit AppTest unavailable")
        import pycalphad

        sys.path.insert(0, str(APP))
        import thermogar_restricted_fe_core as core

        def fake_execute(_root, context, request):
            if request.feature_id == "equilibrium_composition_scan":
                specs = tuple(
                    (value, request.temperatures_k[0])
                    for value in request.concentrations_pct
                )
            else:
                specs = tuple((value, value) for value in request.temperatures_k)
            points = tuple(
                core.RestrictedFePointReceipt(
                    call_index=index,
                    axis_value=axis,
                    temperature_k=temperature,
                    pressure_pa=request.pressure_pa,
                    atomic_fractions=(("FE", 1.0),),
                    phase_fractions=(("LIQUID", 1.0),),
                )
                for index, (axis, temperature) in enumerate(specs, start=1)
            )
            return core.RestrictedFeReceipt(
                schema="thermogar.restricted_fe.receipt.v2",
                feature_id=request.feature_id,
                context_digest=core.context_digest(context),
                request_digest=core.request_digest(request),
                ordered_phases=("LIQUID",),
                ordered_phases_digest=core.canonical_digest(["LIQUID"]),
                source_hashes=(
                    ("database_sha256", core.DATABASE_SHA256),
                    ("passport_sha256", core.PASSPORT_SHA256),
                ),
                calls=len(points),
                points=points,
                outcome="success",
                error_code=None,
                material_base="STEEL",
                experimental_qualification="NOT_PERFORMED",
            )

        app = AppTest.from_file(str(SUBJECT), default_timeout=120)
        with mock.patch.object(
            pycalphad,
            "equilibrium",
            side_effect=AssertionError("direct solver path used"),
        ) as direct_solver, mock.patch.object(
            core,
            "execute_restricted_fe",
            side_effect=fake_execute,
        ) as restricted_executor:
            app.run(timeout=120)
            for label in (
                "Рассчитать равновесие",
                "Построить график по температуре",
                "Построить график по составу",
            ):
                next(button for button in app.button if button.label == label).click()
                app.run(timeout=120)
            app.run(timeout=120)
        direct_solver.assert_not_called()
        self.assertEqual(
            [
                len(call.args[2].concentrations_pct)
                or len(call.args[2].temperatures_k)
                for call in restricted_executor.call_args_list
            ],
            [1, 3, 3],
        )
        self.assertEqual(
            [call.args[2].feature_id for call in restricted_executor.call_args_list],
            [
                "equilibrium_single",
                "equilibrium_temperature_scan",
                "equilibrium_composition_scan",
            ],
        )
        self.assertIn(
            "_thermogar_restricted_fe_result_equilibrium_single",
            app.session_state.filtered_state,
        )

    def test_008_restricted_result_is_invalidated_by_input_drift(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Streamlit AppTest unavailable")
        import pycalphad

        sys.path.insert(0, str(APP))
        import thermogar_restricted_fe_core as core

        def fake_execute(_root, context, request):
            return core.RestrictedFeReceipt(
                schema="thermogar.restricted_fe.receipt.v2",
                feature_id="equilibrium_single",
                context_digest=core.context_digest(context),
                request_digest=core.request_digest(request),
                ordered_phases=("LIQUID",),
                ordered_phases_digest=core.canonical_digest(["LIQUID"]),
                source_hashes=(
                    ("database_sha256", core.DATABASE_SHA256),
                    ("passport_sha256", core.PASSPORT_SHA256),
                ),
                calls=1,
                points=(
                    core.RestrictedFePointReceipt(
                        call_index=1,
                        axis_value=request.temperatures_k[0],
                        temperature_k=request.temperatures_k[0],
                        pressure_pa=request.pressure_pa,
                        atomic_fractions=(("FE", 1.0),),
                        phase_fractions=(("LIQUID", 1.0),),
                    ),
                ),
                outcome="success",
                error_code=None,
                material_base="STEEL",
                experimental_qualification="NOT_PERFORMED",
            )
        app = AppTest.from_file(str(SUBJECT), default_timeout=120)
        with mock.patch.object(pycalphad, "equilibrium") as direct_solver, mock.patch.object(
            core, "execute_restricted_fe", side_effect=fake_execute
        ) as restricted_executor:
            app.run(timeout=120)
            next(
                button
                for button in app.button
                if button.label == "Рассчитать равновесие"
            ).click()
            app.run(timeout=120)
            state_key = "_thermogar_restricted_fe_result_equilibrium_single"
            self.assertIn(state_key, app.session_state.filtered_state)
            next(
                item
                for item in app.number_input
                if item.key == "single_temperature_fe"
            ).set_value(710.0)
            app.run(timeout=120)
        direct_solver.assert_not_called()
        self.assertEqual(restricted_executor.call_count, 1)
        self.assertNotIn(state_key, app.session_state.filtered_state)

    def test_009_ni_and_al_buttons_remain_frozen(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Streamlit AppTest unavailable")
        sys.path.insert(0, str(APP))
        import thermogar_restricted_fe_core as core

        for database_key in ("ni", "al"):
            app = AppTest.from_file(str(SUBJECT), default_timeout=120).run(timeout=120)
            selector = next(
                item for item in app.selectbox if item.label == "База материалов"
            )
            selector.set_value(database_key)
            with mock.patch.object(core, "execute_restricted_fe") as executor:
                app.run(timeout=120)
            executor.assert_not_called()
            for label in (
                "Рассчитать равновесие",
                "Построить график по температуре",
                "Построить график по составу",
            ):
                button = next(item for item in app.button if item.label == label)
                self.assertTrue(button.disabled)


if __name__ == "__main__":
    unittest.main(verbosity=2)
