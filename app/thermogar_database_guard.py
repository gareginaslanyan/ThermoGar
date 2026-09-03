"""ThermoGar legacy mc_fe v2.062 passport and diagnostic guard.

The unchanged upstream-derived pycalphad copy and a patched diagnostic profile
are both kept outside the release calculation surface. The patched diagnostic
profile applies exactly one documented compatibility change,
TG-FE-2062-C15-001: one active reciprocal C15_LAVES parameter is commented
out, never replaced by a guessed numeric value. Neither profile is a release
baseline or a qualified material database.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
from typing import Any

import numpy as np
import pandas as pd
from pycalphad import Database, equilibrium, variables as v


FE_DATABASE_MAX_T_K = 2000.0
FE_DATABASE_MAX_T_C = FE_DATABASE_MAX_T_K - 273.15
PATCH_ID = "TG-FE-2062-C15-001"
FE_PATCH_ID = PATCH_ID
SUSPECT_PHASE = "C15_LAVES"
SUSPECT_PARAMETER_SIGNATURE = "G(C15_LAVES,FE,NI:MN,SI;0)"

FE_PROFILE_WORKING = "thermogar_patch"
FE_PROFILE_UPSTREAM = "upstream_original"

# Backward-compatible names used by Stage 13.1 projects and the main app.
FE_PROFILE_CANONICAL = FE_PROFILE_WORKING
FE_PROFILE_EXPERIMENTAL = FE_PROFILE_UPSTREAM

FE_PROFILE_LABELS = {
    FE_PROFILE_WORKING: "mc_fe 2.062, профиль thermogar_patch (патч TG-FE-2062-C15-001, C15_LAVES исключена)",
    FE_PROFILE_UPSTREAM: (
        "Исходная mc_fe 2.062 без патча (не используется в расчётах)"
    ),
}

WORKING_FE_RELATIVE_PATH = Path(
    "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb"
)
UPSTREAM_FE_RELATIVE_PATH = Path(
    "databases/diagnostic/fe/"
    "mc_fe_v2062_unpatched_with_mobility.thermogar.tdb"
)
WORKING_THERMO_RELATIVE_PATH = Path(
    "databases/converted/fe/mc_fe_v2062.thermogar.tdb"
)
UPSTREAM_THERMO_RELATIVE_PATH = Path(
    "databases/diagnostic/fe/mc_fe_v2062_unpatched.thermogar.tdb"
)


@dataclass(frozen=True)
class ActiveCommand:
    start_line: int
    end_line: int
    text: str


@dataclass(frozen=True)
class FeHighTemperatureCheck:
    temperature_k: float
    temperature_c: float
    liquid_fraction: float
    c15_laves_fraction: float
    stable_phases: dict[str, float]
    triggered: bool
    criterion: str

    def dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "Фаза": phase,
                    "Мольная доля, %": 100.0 * fraction,
                }
                for phase, fraction in sorted(
                    self.stable_phases.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ]
        )


class KnownFeDatabaseIssue(ValueError):
    """Blocking high-temperature issue in the selected Fe profile."""

    def __init__(
        self,
        message: str,
        check: FeHighTemperatureCheck | None = None,
    ) -> None:
        super().__init__(message)
        self.check = check


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_text(path: str | Path) -> tuple[str, str]:
    data = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace"), "latin-1"


def iter_active_commands(text: str) -> list[ActiveCommand]:
    """Return active TDB commands, excluding `$` comment lines."""
    lines = text.splitlines(keepends=True)
    commands: list[ActiveCommand] = []
    buffer: list[str] = []
    start_line: int | None = None

    for line_number, line in enumerate(lines):
        stripped = line.lstrip()
        if not buffer and (not stripped.strip() or stripped.startswith("$")):
            continue
        if start_line is None:
            start_line = line_number
        buffer.append(line)
        if "!" in line:
            commands.append(
                ActiveCommand(
                    start_line=start_line,
                    end_line=line_number,
                    text="".join(buffer),
                )
            )
            buffer = []
            start_line = None
    return commands


def normalize_tdb_command(command: str) -> str:
    return re.sub(r"\s+", " ", command.strip().upper())


def parameter_phase(command: str) -> tuple[str, str] | None:
    match = re.match(
        r"(?is)^\s*PARAMETER\s+([A-Za-z]+)\s*\(\s*"
        r"([A-Za-z0-9_:+-]+)\s*[,;]",
        command,
    )
    if not match:
        return None
    return match.group(1).upper(), match.group(2).split(":", 1)[0].upper()


def is_c15_reciprocal_command(command: str) -> bool:
    return normalize_tdb_command(command).startswith(
        "PARAMETER G(C15_LAVES,FE,NI:MN,SI;0)"
    )


def is_exact_suspect_command(command: str) -> bool:
    normalized = normalize_tdb_command(command)
    if not is_c15_reciprocal_command(normalized):
        return False
    return bool(
        re.search(
            r"PARAMETER G\(C15_LAVES,FE,NI:MN,SI;0\)\s+"
            r"273(?:\.0+)?\s+-9(?:\.0+)?E\+?6\s*;\s*"
            r"6000(?:\.0+)?\s+N\b",
            normalized,
        )
    )


def profile_paths(project_root: str | Path) -> dict[str, Path]:
    root = Path(project_root)
    working = root / WORKING_FE_RELATIVE_PATH
    upstream = root / UPSTREAM_FE_RELATIVE_PATH
    working_thermo = root / WORKING_THERMO_RELATIVE_PATH
    upstream_thermo = root / UPSTREAM_THERMO_RELATIVE_PATH
    passport = working.with_suffix(".passport.json")
    return {
        FE_PROFILE_WORKING: working,
        FE_PROFILE_UPSTREAM: upstream,
        "working_thermo": working_thermo,
        "upstream_thermo": upstream_thermo,
        "passport": passport,
        # Legacy alias used by older tools.
        "manifest": passport,
        "merge_report": working.with_suffix(working.suffix + ".json"),
        "thermo_report": working_thermo.with_suffix(
            working_thermo.suffix + ".json"
        ),
        "upstream_merge_report": upstream.with_suffix(
            upstream.suffix + ".json"
        ),
        "upstream_thermo_report": upstream_thermo.with_suffix(
            upstream_thermo.suffix + ".json"
        ),
    }


def normalize_profile_key(value: str | None) -> str:
    mapping = {
        None: FE_PROFILE_WORKING,
        # Stage 13.1 naming. `canonical` meant unmodified upstream profile.
        "canonical": FE_PROFILE_UPSTREAM,
        "c15_laves_parameter_disabled": FE_PROFILE_WORKING,
        "c15_compat": FE_PROFILE_WORKING,
        "original": FE_PROFILE_UPSTREAM,
        "patched_working": FE_PROFILE_WORKING,
        "unpatched_diagnostic": FE_PROFILE_UPSTREAM,
        FE_PROFILE_WORKING: FE_PROFILE_WORKING,
        FE_PROFILE_UPSTREAM: FE_PROFILE_UPSTREAM,
    }
    if value not in mapping:
        raise ValueError(f"Неизвестный диагностический Fe-профиль: {value!r}.")
    return mapping[value]


def available_fe_profiles(project_root: str | Path) -> list[str]:
    paths = profile_paths(project_root)
    profiles: list[str] = []
    if paths[FE_PROFILE_WORKING].is_file():
        profiles.append(FE_PROFILE_WORKING)
    if paths[FE_PROFILE_UPSTREAM].is_file():
        profiles.append(FE_PROFILE_UPSTREAM)
    return profiles or [FE_PROFILE_WORKING]


def fe_database_path(project_root: str | Path, profile_key: str) -> Path:
    key = normalize_profile_key(profile_key)
    path = profile_paths(project_root)[key]
    if not path.is_file():
        raise FileNotFoundError(f"Профиль Fe-базы не найден: {path}")
    return path


def load_profile_manifest(project_root: str | Path) -> dict[str, Any] | None:
    path = profile_paths(project_root)["passport"]
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def compatibility_patch_record(
    project_root_or_manifest: str | Path | dict[str, Any],
) -> dict[str, Any] | None:
    """Return TG-FE-2062-C15-001 from a project or loaded passport."""
    if isinstance(project_root_or_manifest, dict):
        passport = project_root_or_manifest
    else:
        passport = load_profile_manifest(project_root_or_manifest) or {}
    patches = passport.get("compatibility_patches", [])
    if not isinstance(patches, list):
        return None
    for item in patches:
        if (
            isinstance(item, dict)
            and item.get("patch_id") == PATCH_ID
            and item.get("applied") is True
        ):
            result = dict(item)
            result["working_profile"] = True
            return result
    return None


def _active_commands(path: str | Path) -> list[ActiveCommand]:
    text, _ = read_text(path)
    return iter_active_commands(text)


def find_c15_reciprocal_commands(path: str | Path) -> list[str]:
    return [
        command.text.strip()
        for command in _active_commands(path)
        if is_c15_reciprocal_command(command.text)
    ]


def find_exact_suspect_commands(path: str | Path) -> list[str]:
    return [
        command.text.strip()
        for command in _active_commands(path)
        if is_exact_suspect_command(command.text)
    ]


def phase_parameter_commands(path: str | Path, phase_name: str) -> list[str]:
    result: list[str] = []
    for command in _active_commands(path):
        parsed = parameter_phase(command.text)
        if parsed is not None and parsed == ("G", phase_name.upper()):
            result.append(normalize_tdb_command(command.text))
    return sorted(result)


def command_list_sha256(commands: list[str]) -> str:
    return hashlib.sha256(
        "\n".join(sorted(commands)).encode("utf-8")
    ).hexdigest().upper()


def aggregate_phase_fractions(eq: Any) -> dict[str, float]:
    names = np.asarray(eq.Phase.values, dtype=str).ravel()
    fractions = np.asarray(eq.NP.values, dtype=float).ravel()
    result: dict[str, float] = {}
    for name, fraction in zip(names, fractions):
        if name and np.isfinite(fraction) and fraction > 1e-12:
            result[str(name)] = result.get(str(name), 0.0) + float(fraction)
    return result


def check_fe_high_temperature_behavior(
    db: Database,
    components: list[str],
    phases: list[str],
    composition_conditions: dict[Any, float],
    *,
    temperature_k: float = FE_DATABASE_MAX_T_K,
    pdens: int = 100,
    liquid_threshold: float = 0.999,
    c15_threshold: float = 1e-4,
) -> FeHighTemperatureCheck:
    conditions = {
        v.N: 1.0,
        v.P: 101325.0,
        v.T: float(temperature_k),
    }
    conditions.update(composition_conditions)
    eq = equilibrium(
        db,
        components,
        phases,
        conditions,
        calc_opts={"pdens": int(pdens)},
    )
    fractions = aggregate_phase_fractions(eq)
    liquid = float(fractions.get("LIQUID", 0.0))
    c15 = float(fractions.get("C15_LAVES", 0.0))
    triggered = bool(liquid < liquid_threshold and c15 > c15_threshold)
    return FeHighTemperatureCheck(
        temperature_k=float(temperature_k),
        temperature_c=float(temperature_k) - 273.15,
        liquid_fraction=liquid,
        c15_laves_fraction=c15,
        stable_phases=fractions,
        triggered=triggered,
        criterion=(
            f"LIQUID < {liquid_threshold:.4f} и "
            f"C15_LAVES > {c15_threshold:.1e} при {temperature_k:.1f} K"
        ),
    )


def assert_fe_solidification_safe(
    profile_key: str,
    check: FeHighTemperatureCheck,
    *,
    allow_canonical_override: bool = False,
) -> None:
    del allow_canonical_override  # API compatibility; silent override forbidden.
    if not check.triggered:
        return
    key = normalize_profile_key(profile_key)
    if key == FE_PROFILE_UPSTREAM:
        message = (
            "Исходная mc_fe 2.062 воспроизвела известную аномалию: "
            f"при {check.temperature_k:.0f} K LIQUID = "
            f"{100.0 * check.liquid_fraction:.4f} %, C15_LAVES = "
            f"{100.0 * check.c15_laves_fraction:.4f} %. ThermoGar не "
            "выдаёт такой ликвидус как достоверный. Оба Fe-профиля имеют "
            "диагностический статус; патчированный профиль можно использовать "
            f"только для сравнения по паспорту {PATCH_ID}."
        )
    else:
        message = (
            f"Даже после патча {PATCH_ID} текущий состав не достигает "
            "однофазной жидкости на верхней температуре базы и сохраняет "
            "C15_LAVES. Проверьте область применимости базы, полный набор "
            "фаз и независимый расчёт. Ликвидус заблокирован."
        )
    raise KnownFeDatabaseIssue(message, check)


def passport_dataframe(
    project_root: str | Path,
    selected_profile: str,
) -> pd.DataFrame:
    paths = profile_paths(project_root)
    working = paths[FE_PROFILE_WORKING]
    upstream = paths[FE_PROFILE_UPSTREAM]
    passport = load_profile_manifest(project_root) or {}
    patch = compatibility_patch_record(passport) or {}

    working_c15 = (
        phase_parameter_commands(working, "C15_LAVES")
        if working.is_file()
        else []
    )
    upstream_c15 = (
        phase_parameter_commands(upstream, "C15_LAVES")
        if upstream.is_file()
        else []
    )
    working_laves = (
        phase_parameter_commands(working, "LAVES_PHASE")
        if working.is_file()
        else []
    )
    upstream_laves = (
        phase_parameter_commands(upstream, "LAVES_PHASE")
        if upstream.is_file()
        else []
    )

    rows = [
        (
            "Выбранный профиль",
            FE_PROFILE_LABELS.get(
                normalize_profile_key(selected_profile), selected_profile
            ),
        ),
        ("Рабочая база (thermogar_patch)", str(working)),
        (
            "SHA-256 рабочей базы",
            file_sha256(working) if working.is_file() else "не найдена",
        ),
        ("Патч", PATCH_ID),
        ("Статус патча", patch.get("status", "не найден")),
        ("Действие", patch.get("action", "не найдено")),
        ("Совпавших активных команд", patch.get("matched_active_commands", "—")),
        (
            "Активных G-параметров C15_LAVES в рабочей базе",
            len(working_c15),
        ),
        (
            "Активна команда -9e6 в рабочей базе",
            "да" if working.is_file() and find_exact_suspect_commands(working) else "нет",
        ),
        ("Исходная база без патча (в расчётах не используется)", str(upstream)),
        (
            "SHA-256 непатченной базы",
            file_sha256(upstream) if upstream.is_file() else "не найдена",
        ),
        (
            "Активных G-параметров C15_LAVES в непатченной базе",
            len(upstream_c15),
        ),
        (
            "Активна команда -9e6 в непатченной базе",
            "да" if upstream.is_file() and find_exact_suspect_commands(upstream) else "нет",
        ),
        (
            "LAVES_PHASE не изменена",
            "да"
            if command_list_sha256(working_laves)
            == command_list_sha256(upstream_laves)
            else "нет / не проверено",
        ),
        ("Проверка в нативном MatCalc", "не проводилась"),
    ]
    return pd.DataFrame([(k, str(v)) for k, v in rows], columns=["Поле", "Значение"])
