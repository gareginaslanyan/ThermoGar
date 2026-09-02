#!/usr/bin/env python3
"""Minimal SWR software regression for the legacy diffusion component."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "не установлен"


def find_root() -> Path:
    candidates = [Path.cwd(), Path.cwd().parent, Path(__file__).resolve().parent.parent]
    for candidate in candidates:
        if (candidate / "app").exists() and (candidate / "databases").exists():
            return candidate.resolve()
    raise FileNotFoundError("Запустите тест из корня ThermoGar.")


def main() -> int:
    root = find_root()
    sys.path.insert(0, str(root / "app"))

    print("=" * 78)
    print("THERMOGAR SWR — DIFFUSION SOFTWARE REGRESSION")
    print("=" * 78)
    print("Project:", root)
    print("kawin:", package_version("kawin"))

    if package_version("kawin") == "не установлен":
        print("RESULT: FAILED")
        print("Установите: python -m pip install kawin==0.5.0 espei==0.9.1")
        return 1

    from thermogar_diffusion import run_diffusion
    from thermogar_release_policy import (
        RELEASE_DATABASE_LABELS,
        RELEASE_DATABASE_SHA256,
    )

    database_path = (
        root
        / "databases"
        / "converted"
        / "mc_ni_v2036_with_mobility.garcalc.tdb"
    )
    if not database_path.exists():
        print("RESULT: FAILED")
        print("Не найдена Ni-база:", database_path)
        return 1

    scenario = {
        # Deliberately untrusted: the API must ignore this object and reload
        # the hash-pinned canonical database itself.
        "db": object(),
        "database_key": "ni",
        "database_path": database_path,
        "database_label": RELEASE_DATABASE_LABELS["ni"],
        "balance": "NI",
        "units": "at",
        "left_text": "CR=7.7, AL=5.4",
        "right_text": "CR=35.9, AL=6.2",
        "temperature_c": 1200.0,
        "time_h": 0.001,
        "length_um": 100.0,
        "interface_percent": 50.0,
        "nodes": 20,
        "phases": ["FCC_A1"],
        "model_kind": "single",
        "input_provenance": "SYNTHETIC_SOFTWARE_REGRESSION_NOT_MATERIAL_INPUT",
        "input_confirmation": True,
    }

    def expect_rejected(
        label: str,
        exception: type[Exception],
        message_fragment: str,
        **overrides: object,
    ) -> None:
        arguments = dict(scenario)
        arguments.update(overrides)
        try:
            run_diffusion(**arguments)
        except exception as error:
            if message_fragment not in str(error):
                raise AssertionError(
                    f"Wrong rejection reason for {label}: {type(error).__name__}: {error}"
                ) from error
            print("PASS:", label)
        else:
            raise AssertionError(f"Expected {exception.__name__}: {label}")

    expect_rejected(
        "Fe database rejected",
        RuntimeError,
        "Fe diffusion отклонён",
        database_key=" fe ",
    )
    expect_rejected(
        "unknown database rejected",
        ValueError,
        "не входит в SWR release surface",
        database_key="cu",
    )
    expect_rejected(
        "non-string database key rejected",
        ValueError,
        "должен быть строкой",
        database_key=7,
    )
    expect_rejected(
        "key/path mismatch rejected",
        RuntimeError,
        "путь базы не соответствует",
        database_key="al",
        database_label=RELEASE_DATABASE_LABELS["al"],
    )
    expect_rejected(
        "database label mismatch rejected",
        RuntimeError,
        "название базы не соответствует",
        database_label="Железные сплавы",
    )
    expect_rejected(
        "non-string database label rejected",
        ValueError,
        "должно быть строкой",
        database_label=7,
    )
    expect_rejected(
        "non-string input provenance rejected",
        ValueError,
        "должен быть строкой",
        input_provenance=123,
    )
    expect_rejected(
        "blank input provenance rejected",
        ValueError,
        "обязателен источник",
        input_provenance="  ",
    )
    expect_rejected(
        "unconfirmed input rejected",
        ValueError,
        "явное подтверждение",
        input_confirmation=False,
    )
    expect_rejected(
        "unknown model kind rejected",
        ValueError,
        "model_kind diffusion должен быть строго",
        model_kind="typo",
    )
    expect_rejected(
        "unknown homogenization function rejected",
        ValueError,
        "Неизвестная модель эффективной подвижности",
        model_kind="homogenization",
        homogenization_function="typo",
    )
    with patch("thermogar_diffusion._sha256", return_value="0" * 64):
        expect_rejected(
            "database SHA mismatch rejected",
            RuntimeError,
            "SHA-256 базы не соответствует",
        )
    with patch(
        "thermogar_diffusion._sha256",
        side_effect=[RELEASE_DATABASE_SHA256["ni"], "0" * 64],
    ):
        expect_rejected(
            "post-load database change rejected",
            RuntimeError,
            "изменился во время загрузки",
        )
    with tempfile.TemporaryDirectory(prefix="thermogar-diffusion-db-copy-") as temporary:
        copied_database = Path(temporary) / database_path.name
        shutil.copyfile(database_path, copied_database)
        expect_rejected(
            "byte-identical noncanonical copy rejected",
            RuntimeError,
            "путь базы не соответствует",
            database_path=copied_database,
        )

    result = run_diffusion(**scenario)

    print()
    print(result.quality.to_string(index=False))
    print()
    print("Actual time, s:", result.actual_time_s)
    print("Profile rows:", len(result.profile_table))
    print("Max balance error:", result.max_balance_error)

    passed = bool(
        (result.quality["Статус"] == "пройдена").all()
        and abs(result.actual_time_s - 3.6) <= 1e-4
        and len(result.profile_table) == 20
        and result.database_key == "ni"
        and result.database_sha256 == RELEASE_DATABASE_SHA256["ni"]
        and result.input_provenance
        == "SYNTHETIC_SOFTWARE_REGRESSION_NOT_MATERIAL_INPUT"
        and result.input_confirmation is True
        and result.provenance["database_key"] == "ni"
        and result.provenance["release_status"]["production_use"] == "DENIED"
        and result.provenance["result_scope"]
        == "SOFTWARE_MODEL_OUTPUT_NOT_EXPERIMENTAL_VALIDATION_OR_MATERIAL_QUALIFICATION"
    )

    plt.close(result.profile_figure)
    if result.phase_figure is not None:
        plt.close(result.phase_figure)

    print()
    print("RESULT:", "PASSED" if passed else "FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
