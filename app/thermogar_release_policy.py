"""Authoritative release identity.

This module is intentionally independent of Streamlit and scientific runtime
packages so that packaging, UI and verification code read the same policy.
Legacy module names containing ``stage14`` remain only as implementation
provenance; they are not release or qualification claims.
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
