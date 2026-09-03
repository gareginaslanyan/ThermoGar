"""Authoritative release identity and feature inventory.

This module is intentionally independent of Streamlit and scientific runtime
packages so that packaging, UI and verification code read the same policy.
Legacy module names containing ``stage12``/``stage14``/``stage15`` remain only
as implementation provenance; they are not release or qualification claims.
Experimental qualification of the scientific results has not been performed.
"""

from __future__ import annotations

from collections.abc import Iterable
from types import MappingProxyType
from typing import Final


APP_NAME: Final = "ThermoGar"
APP_LINEAGE: Final = "SWR"
APP_GATE: Final = "-"
APP_STAGE: Final = "0.3.0"
APP_VERSION: Final = "0.3.0"
FEATURE_FREEZE_SCHEMA_VERSION: Final = "SWR-NE02-INVENTORY-1"
RELEASE_CLASS: Final = (
    "Исследовательское ПО — экспериментальная валидация не проводилась"
)
SOFTWARE_RELEASE_STATUS: Final = "RESEARCH_SOFTWARE"
SCIENTIFIC_MATERIAL_STATUS: Final = "EXPERIMENTAL_QUALIFICATION_NOT_PERFORMED"
PRODUCTION_USE: Final = "NOT_ASSESSED"
RELEASE_DATABASE_KEYS: Final = ("ni", "al", "fe")
DIAGNOSTIC_DATABASE_KEYS: Final = ()
RELEASE_DATABASE_ELEMENTS: Final = MappingProxyType(
    {
        "ni": frozenset(
            {
                "AL", "B", "C", "CO", "CR", "CU", "FE", "HF", "LA",
                "MN", "MO", "N", "NB", "NI", "O", "S", "SI", "TI",
                "V", "W", "Y", "ZR",
            }
        ),
        "al": frozenset(
            {
                "AL", "CR", "CU", "FE", "MG", "MN", "NI", "SC", "SI",
                "TI", "ZN", "ZR",
            }
        ),
        "fe": frozenset(
            {
                "AL", "B", "C", "CO", "CR", "CU", "FE", "H", "HF", "LA",
                "MN", "MO", "N", "NB", "NI", "O", "P", "PD", "S", "SI",
                "TA", "TI", "V", "W", "Y",
            }
        ),
    }
)
RELEASE_DATABASE_FILENAMES: Final = MappingProxyType(
    {
        "ni": "mc_ni_v2036_with_mobility.garcalc.tdb",
        "al": "mc_al_v2037_with_mobility.thermogar.tdb",
        "fe": "mc_fe_v2062_with_mobility.thermogar.tdb",
    }
)
RELEASE_DATABASE_LABELS: Final = MappingProxyType(
    {
        "ni": "Никелевые сплавы — mc_ni 2.036",
        "al": "Алюминиевые сплавы — mc_al 2.037",
        "fe": "Стали и Fe-сплавы — mc_fe 2.062",
    }
)
RELEASE_DATABASE_RELATIVE_PATHS: Final = MappingProxyType(
    {
        "ni": "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
        "al": (
            "databases/converted/al/"
            "mc_al_v2037_with_mobility.thermogar.tdb"
        ),
        "fe": (
            "databases/converted/fe/"
            "mc_fe_v2062_with_mobility.thermogar.tdb"
        ),
    }
)
RELEASE_DATABASE_SHA256: Final = MappingProxyType(
    {
        "ni": "1882d841a337063e0585d261c690ae7e565838234e231e21b8541a5cb0dba391",
        "al": "f9bdf21d434fbe78b5ef3f7f2de69763fa40b81335cdc58889907d41c80cd717",
        "fe": "236ec4d9b0540de04e4e6305faa208672f31fbdf45b2ae84e92f80bd98053612",
    }
)
FE_EXCLUDED_PHASES: Final = frozenset({"C15_LAVES"})


def effective_release_phases(
    database_key: str,
    phases: Iterable[str],
) -> list[str]:
    """Список фаз для расчёта: для Fe (thermogar_patch) убирает C15_LAVES."""

    result = [
        phase
        for phase in phases
        if not (database_key == "fe" and phase in FE_EXCLUDED_PHASES)
    ]
    return result


PHYSICAL_DATABASE_RELATIVE_PATH: Final = (
    "databases/physical/original/physical_data_v103.pdb"
)
PHYSICAL_DATABASE_SHA256: Final = (
    "4cf81c992b57263c50b370ea47eb0d5bb4f622cf23c18479bab54267762f20bd"
)
EXPORTS_ENABLED: Final = True
IMPORTS_ENABLED: Final = True
CALCULATIONS_ENABLED: Final = True
RUNTIME_POLICY_GENERATION: Final = (
    f"{APP_VERSION}|release-surface|"
    f"calculations={int(CALCULATIONS_ENABLED)}|"
    f"imports={int(IMPORTS_ENABLED)}|exports={int(EXPORTS_ENABLED)}"
)
EXPORT_BLOCK_REASON: Final = (
    "Выгрузка заморожена до NE-06: артефакты ещё не получили обязательный "
    "evidence-envelope, связанный manifest и защиту от устаревшего контекста."
)
IMPORT_BLOCK_REASON: Final = (
    "Импорт внешних файлов заморожен до NE-07: миграция, строгая схема и "
    "восстановление точной версии базы ещё не квалифицированы."
)
CALCULATION_BLOCK_REASON: Final = (
    "Численный путь заморожен после NE-02 до прохождения обязательных "
    "software-verification и database-domain gates NE-03/NE-04."
)

EVIDENCE_FIELDS: Final = (
    "execution_status",
    "evidence_basis",
    "material_relation",
    "evaluation_mode",
    "claim_level",
    "production_use",
)

ENABLED_INSIDE_DOMAIN: Final = "ENABLED_INSIDE_DECLARED_DOMAIN"
USER_INPUT_REQUIRED: Final = "USER_INPUT_REQUIRED_RESEARCH_SCENARIO"
DIAGNOSTIC_ONLY: Final = "DISABLED_DIAGNOSTIC_ONLY_NOT_RELEASE_BASELINE"
DISABLED: Final = "DISABLED_NOT_IN_RELEASE"
DISABLED_PENDING: Final = "DISABLED_PENDING_REQUIRED_GATE"
INFORMATIONAL: Final = "ENABLED_INFORMATIONAL_SOFTWARE_ONLY"

def _feature(
    feature_id: str,
    owner: str,
    disposition: str,
    required_gates: str,
    data_source: str,
    domain: str,
    failure_policy: str,
    claim_boundary: str,
) -> MappingProxyType:
    target_release_disposition = disposition
    if disposition.startswith("USER_INPUT_REQUIRED"):
        disposition_class = "USER_INPUT_REQUIRED"
    elif disposition.startswith("ENABLED"):
        disposition_class = "ENABLE"
    else:
        disposition_class = "DISABLE"
    return MappingProxyType(
        {
            "feature_id": feature_id,
            "owner": owner,
            "component_version": APP_VERSION,
            "disposition": disposition,
            "disposition_class": disposition_class,
            "target_release_disposition": target_release_disposition,
            "required_gates": required_gates,
            "data_source": data_source,
            "domain": domain,
            "failure_policy": failure_policy,
            "claim_boundary": claim_boundary,
        }
    )


FEATURES: Final = (
    _feature("application_shell_and_global_inputs", "app/ThermoGar_app.py", USER_INPUT_REQUIRED, "NE-02_AND_NE-04", "explicit_user_selection_plus_release_policy", "Ni_or_Al_release_database_surface", "unknown_database_or_invalid_context_fails_closed", "research_software_input_context_only"),
    _feature("equilibrium_single", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "selected_native_database", "declared_database_composition_temperature_phase_domain", "invalid_or_OOD_input_fails_closed", "software_calculation_not_material_validation"),
    _feature("equilibrium_temperature_scan", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "selected_native_database", "declared_database_composition_temperature_phase_domain", "any_failed_grid_point_is_reported_not_hidden", "software_calculation_not_material_validation"),
    _feature("equilibrium_composition_scan", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "selected_native_database", "declared_database_composition_temperature_phase_domain", "invalid_grid_or_OOD_input_fails_closed", "software_calculation_not_material_validation"),
    _feature("binary_phase_diagram", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "selected_native_database", "binary_database_domain_only", "mapping_failure_is_explicit", "numerical_diagram_not_experimental_phase_boundary"),
    _feature("multicomponent_isopleth", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "selected_native_database", "declared_database_domain_only", "mapping_failure_is_explicit", "numerical_diagram_not_experimental_phase_boundary"),
    _feature("ternary_phase_diagram", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "selected_native_database", "ternary_database_domain_only", "mapping_failure_is_explicit", "numerical_diagram_not_experimental_phase_boundary"),
    _feature("ternary_phase_fraction_map", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "selected_native_database", "discrete_ternary_grid_inside_database_domain", "failed_nodes_and_interpolation_limit_are_reported", "interpolated_scenario_map_not_measurement"),
    _feature("manual_phase_selection_metastable", "app/ThermoGar_app.py", USER_INPUT_REQUIRED, "NE-03_AND_NE-04", "user_phase_selection_plus_database", "selected_phase_subset_only", "empty_or_incompatible_phase_set_fails_closed", "user_conditioned_metastable_scenario"),
    _feature("equilibrium_solidification", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "selected_native_database", "database_domain_and_liquid_phase_required", "missing_liquid_or_failed_path_fails_closed", "equilibrium_scenario_not_process_validation"),
    _feature("scheil_solidification", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "selected_native_database_plus_scheil", "Scheil_Gulliver_assumptions_and_database_domain", "missing_dependency_or_invalid_path_fails_closed", "model_scenario_not_time_resolved_process_prediction"),
    _feature("phase_gibbs_energy", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "selected_native_database", "single_phase_models_inside_database_domain", "incompatible_phase_or_state_fails_closed", "relative_model_energy_only"),
    _feature("phase_driving_force", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "selected_native_database", "declared_reference_and_target_phase_models", "invalid_reference_or_target_fails_closed", "thermodynamic_model_quantity_not_kinetic_validation"),
    _feature("tzero_temperature", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "selected_native_database", "two_phase_same_composition_model_domain", "missing_crossing_is_reported_as_no_result", "model_equality_not_solvus_measurement"),
    _feature("density_single", "app/thermogar_physical.py", USER_INPUT_REQUIRED, "NE-03_AND_NE-06", "physical_data_v103_plus_equilibrium", "only_phases_with_direct_or_declared_related_model", "missing_phase_density_suppresses_total_density", "source_conditioned_estimate"),
    _feature("density_temperature_scan", "app/thermogar_physical.py", USER_INPUT_REQUIRED, "NE-03_AND_NE-06", "physical_data_v103_plus_equilibrium", "covered_phases_and_declared_temperature_domain", "uncovered_phase_or_failed_node_is_explicit", "source_conditioned_estimate"),
    _feature("elastic_vrh", "app/thermogar_properties.py", USER_INPUT_REQUIRED, "NE-03_AND_NE-06", "user_or_local_sourced_phase_moduli", "isotropic_Voigt_Reuss_Hill_assumptions", "missing_phase_modulus_blocks_total", "transparent_homogenization_not_material_property_validation"),
    _feature("strengthening_contributions", "app/thermogar_properties.py", USER_INPUT_REQUIRED, "NE-03_AND_NE-06", "explicit_user_coefficients", "equation_specific_assumptions_only", "missing_or_invalid_coefficient_fails_closed", "mechanism_contributions_not_yield_UTS_hardness_or_ductility_prediction"),
    _feature("automatic_strength_UTS_hardness_ductility", "none", DISABLED, "NONE", "none", "none", "no_runtime_path", "material_specific_prediction_denied"),
    _feature("single_phase_diffusion", "app/thermogar_diffusion.py", USER_INPUT_REQUIRED, "NE-03_AND_NE-04", "selected_database_mobility_plus_user_geometry", "one_dimensional_single_phase_declared_boundary_conditions", "mass_balance_or_solver_failure_fails_closed", "research_scenario_not_process_validation"),
    _feature("multiphase_homogenization", "app/thermogar_diffusion.py", USER_INPUT_REQUIRED, "NE-03_AND_NE-04", "selected_database_mobility_plus_user_geometry", "local_equilibrium_homogenization_assumptions", "unsupported_phase_or_balance_failure_fails_closed", "research_scenario_not_process_validation"),
    _feature("diffusion_shared_engine", "app/thermogar_diffusion.py", USER_INPUT_REQUIRED, "NE-03_AND_NE-04", "selected_database_mobility_plus_explicit_model_kind_and_user_geometry", "shared_one_dimensional_diffusion_engine_with_explicit_single_or_homogenization_mode", "unknown_model_kind_or_invariant_failure_fails_closed", "research_scenario_not_process_validation"),
    _feature("generic_KWN_precipitation", "app/thermogar_precipitation.py", USER_INPUT_REQUIRED, "NE-03_TO_NE-06", "database_plus_explicit_user_physical_inputs", "qualified_engine_domain_excluding_Fe_target_branch", "missing_input_or_guarded_profile_fails_closed", "model_conditioned_research_scenario_not_material_prediction"),
    _feature("Fe_target_KWN", "app/thermogar_precipitation.py", DISABLED, "NONE", "unqualified", "none", "hard_guard_blocks_UI_and_API", "exact_target_KWN_denied"),
    _feature("Cu_VA_exact_multistate_branch", "sealed_Stage15_lineage", DISABLED, "NONE", "sealed_fail_closed_evidence", "none", "not_reachable_from_release_runtime", "production_and_exact_witness_claims_denied"),
    _feature("Ni_database_runtime", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-04", "mc_ni_open_converted_database", "machine_card_fail_closed_pending_accepted_numeric_domain", "OOD_fails_closed", "database_domain_calculation_only"),
    _feature("Al_database_runtime", "app/ThermoGar_app.py", ENABLED_INSIDE_DOMAIN, "NE-04", "mc_al_open_converted_database", "machine_card_fail_closed_pending_accepted_numeric_domain", "OOD_fails_closed", "database_domain_calculation_only"),
    _feature("Fe_C15_patched_database_runtime", "app/thermogar_database_guard.py", DIAGNOSTIC_ONLY, "NE-04", "mc_fe_with_unqualified_C15_modification", "diagnostic_comparison_only", "never_selected_as_release_baseline", "not_qualified_for_release_calculations"),
    _feature("Fe_upstream_unpatched_profile", "app/thermogar_database_guard.py", DIAGNOSTIC_ONLY, "NE-04", "mc_fe_unpatched", "diagnostic_comparison_only", "known_C15_high_temperature_anomaly_is_explicit", "not_qualified_for_release_calculations"),
    _feature("Fe_database_diagnostic_guard", "app/thermogar_database_guard.py", DIAGNOSTIC_ONLY, "NE-04", "paired_patched_and_unpatched_mc_fe_profiles_plus_passport", "diagnostic_comparison_only_outside_release_surface", "unknown_profile_missing_manifest_or_guard_failure_fails_closed", "software_diagnostic_not_database_or_material_qualification"),
    _feature("alloy_library", "app/thermogar_workspace.py", INFORMATIONAL, "NE-07", "local_user_input", "local_workspace_schema", "invalid_import_or_overwrite_fails_closed", "data_management_only"),
    _feature("batch_calculation", "app/thermogar_workspace.py", ENABLED_INSIDE_DOMAIN, "NE-03_NE-04_NE-07", "uploaded_CSV_or_XLSX_plus_database", "none_until_import_schema_and_database_domain_gates_pass", "uploader_returns_no_bytes_and_calculation_path_is_unreachable", "batch_software_calculation_not_validation"),
    _feature("projects_and_history", "app/thermogar_workspace.py", INFORMATIONAL, "NE-07", "local_user_data", "local_workspace_schema", "atomic_write_backup_and_import_validation_required", "data_management_only"),
    _feature("external_file_imports", "app/thermogar_workspace.py", USER_INPUT_REQUIRED, "NE-07", "untrusted_user_JSON_CSV_XLSX", "none_until_schema_migration_and_restore_contract_pass", "visible_controls_disabled_and_no_bytes_consumed", "no_import_claim_before_gate"),
    _feature("local_file_exports", "app/thermogar_release_ui.py", INFORMATIONAL, "NE-06", "computed_or_diagnostic_artifact", "none_until_evidence_envelope_and_stale_guard_pass", "visible_controls_disabled_and_no_artifact_emitted", "no_export_claim_before_gate"),
    _feature("numerical_calculation_actions", "app/thermogar_release_ui.py", ENABLED_INSIDE_DOMAIN, "NE-03_AND_NE-04", "declared_UI_context_plus_underlying_producer", "none_until_software_verification_and_database_domain_gates_pass", "visible_controls_disabled_and_click_state_never_crosses_policy_boundary", "no_numerical_result_before_required_gates"),
    _feature("local_scenario_input_helpers", "app/thermogar_stage14.py_and_app/thermogar_properties.py", USER_INPUT_REQUIRED, "NE-02", "bundled_example_or_already_verified_local_result", "input_population_only_no_solver_execution", "helper_never_executes_solver_or_emits_result", "declared_scenario_input_only"),
    _feature("database_passport", "app/ThermoGar_app.py", INFORMATIONAL, "NE-04", "database_files_manifests_and_hashes", "identity_and_documented_scope_only", "missing_passport_fails_closed", "provenance_not_database_qualification"),
    _feature("help_phase_reference_diagnostics", "app/ThermoGar_app.py", INFORMATIONAL, "NE-07", "bundled_documentation_and_runtime_checks", "software_information_only", "missing_or_failed_check_is_explicit", "software_support_only"),
    _feature("hybrid_or_ML_material_prediction", "none", DISABLED, "NONE", "none", "none", "no_runtime_path", "no_qualified_corpus_and_no_material_claim"),
    _feature("production_process_certification", "none", DISABLED, "NONE", "none", "none", "no_runtime_path", "production_safety_regulatory_and_certification_use_denied"),
    _feature("legacy_notebook_interfaces", "notebooks", DISABLED, "NONE", "historical_unsealed_UI", "outside_release_surface", "excluded_from_release_manifest", "archive_only"),
    _feature("legacy_stage_modules", "app/thermogar_stage12.py", DISABLED, "NONE", "historical_implementation", "outside_release_entrypoints", "not_imported_by_canonical_application", "implementation_history_only"),
    _feature("developer_maintenance_tools", "scripts_and_tools", DIAGNOSTIC_ONLY, "NONE", "local_sources_or_network_maintenance", "developer_environment_only", "excluded_from_runtime_and_never_runs_implicitly", "software_maintenance_not_material_qualification"),
)

FEATURES_BY_ID: Final = MappingProxyType(
    {str(item["feature_id"]): item for item in FEATURES}
)


def release_status() -> dict[str, str | bool]:
    """Return a fresh serializable copy of the two-axis release status."""

    return {
        "app_name": APP_NAME,
        "lineage": APP_LINEAGE,
        "gate": APP_GATE,
        "version": APP_VERSION,
        "release_class": RELEASE_CLASS,
        "software_release_status": SOFTWARE_RELEASE_STATUS,
        "scientific_material_status": SCIENTIFIC_MATERIAL_STATUS,
        "production_use": PRODUCTION_USE,
        "exports_enabled": EXPORTS_ENABLED,
        "imports_enabled": IMPORTS_ENABLED,
        "calculations_enabled": CALCULATIONS_ENABLED,
    }


def feature_rows() -> list[dict[str, str]]:
    """Return mutable serializable copies for manifests and UI tables."""

    return [dict(item) for item in FEATURES]


def research_result_evidence(
    *,
    execution_succeeded: bool,
    software_diagnostic: bool = False,
) -> dict[str, str]:
    """Return all six canonical labels for an on-screen software result."""

    if not execution_succeeded:
        return {
            "execution_status": "EXECUTED_FAILED",
            "evidence_basis": (
                "SOFTWARE_ACCEPTANCE_TEST"
                if software_diagnostic
                else "MIXED_OPEN_DATA_AND_DECLARED_SCENARIO"
            ),
            "material_relation": (
                "NOT_MATERIAL_SPECIFIC"
                if software_diagnostic
                else "USER_DECLARED_UNVALIDATED"
            ),
            "evaluation_mode": (
                "NOT_APPLICABLE_SOFTWARE_VERIFICATION"
                if software_diagnostic
                else "NOT_APPLICABLE_DECLARED_INPUT"
            ),
            "claim_level": "NO_CLAIM_EXECUTION_FAILED",
            "production_use": PRODUCTION_USE,
        }
    return {
        "execution_status": "EXECUTED_REPRODUCIBLE",
        "evidence_basis": (
            "SOFTWARE_ACCEPTANCE_TEST"
            if software_diagnostic
            else "MIXED_OPEN_DATA_AND_DECLARED_SCENARIO"
        ),
        "material_relation": (
            "NOT_MATERIAL_SPECIFIC"
            if software_diagnostic
            else "USER_DECLARED_UNVALIDATED"
        ),
        "evaluation_mode": (
            "NOT_APPLICABLE_SOFTWARE_VERIFICATION"
            if software_diagnostic
            else "NOT_APPLICABLE_DECLARED_INPUT"
        ),
        "claim_level": (
            "SOFTWARE_ACCEPTANCE_VERIFIED"
            if software_diagnostic
            else "COMPUTATIONALLY_PREDICTED_UNVALIDATED"
        ),
        "production_use": PRODUCTION_USE,
    }
