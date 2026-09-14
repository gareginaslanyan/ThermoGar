"""Живой расчёт выделений на составах с ниобием (13-Р2, пункт 5).

Запуск интерпретатором проверяемой копии:
    <python.exe> -B -X utf8 nb_kwn_check.py <корень копии: там app\ и databases\> <каталог вывода>

Идёт штатным путём приложения — ``thermogar_precipitation.run_precipitation``
из каталога ``app`` проверяемой копии, с её базой ``mc_ni``.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
os.environ["THERMOGAR_STATE_ROOT"] = str(out / "state")
sys.path.insert(0, str(root / "app"))

import thermogar_precipitation as tp  # noqa: E402
from thermogar_release_policy import APP_VERSION, RELEASE_DATABASE_LABELS  # noqa: E402

CASES = {
    "ni_al_cr_nb": dict(
        label="Ni–9,8Al–8,3Cr–1Nb ат. %, γ/γ′, 800 °C",
        composition_text="AL=9.8, CR=8.3, NB=1.0", units="at",
        matrix_phase="FCC_A1", precipitate_phase="GAMMA_PRIME", temperature_c=800.0,
        gamma=0.023, matrix_vm=6.5662724928, precip_vm=6.5662724928,
    ),
    "alloy718_base": dict(
        label="Ni–19Cr–5,1Nb–0,5Al–0,9Ti масс. % (основа 718 без Fe и Mo), γ/γ′, 750 °C",
        composition_text="CR=19, NB=5.1, AL=0.5, TI=0.9", units="wt",
        matrix_phase="FCC_A1", precipitate_phase="GAMMA_PRIME", temperature_c=750.0,
        gamma=0.023, matrix_vm=6.5662724928, precip_vm=6.5662724928,
    ),
}

report = {
    "python": sys.executable,
    "app_dir": str(root / "app"),
    "APP_VERSION": APP_VERSION,
    "thermogar_precipitation": tp.__file__,
    "cases": {},
}
for key, case in CASES.items():
    started = time.perf_counter()
    entry: dict = {"label": case["label"]}
    try:
        result = tp.run_precipitation(
            db=object(),
            database_path=root / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
            database_label=RELEASE_DATABASE_LABELS["ni"],
            database_key="ni",
            balance="NI",
            composition_text=case["composition_text"],
            units=case["units"],
            matrix_phase=case["matrix_phase"],
            precipitate_phase=case["precipitate_phase"],
            schedule_mode="isothermal",
            temperature_c=case["temperature_c"],
            duration_h=10.0 / 3600.0,
            profile_text="",
            gamma=case["gamma"],
            matrix_vm=case["matrix_vm"],
            precip_vm=case["precip_vm"],
            nucleation_type="BULK",
            bulk_n0=1e30,
            grain_size_um=100.0,
            dislocation_density=5e12,
            gb_energy=0.3,
            cmin_nm=0.2,
            cmax_nm=10.0,
            bins=80,
            input_provenance="SYNTHETIC_RELEASE_CHECK_NOT_MATERIAL_INPUT",
            input_confirmation=True,
        )
    except Exception as error:  # noqa: BLE001 — исход и есть результат
        entry["status"] = "FAIL"
        entry["error"] = f"{type(error).__name__}: {error}"
        entry["traceback_tail"] = traceback.format_exc().strip().splitlines()[-6:]
    else:
        entry["status"] = "PASS"
        entry["kinetics_rows"] = int(len(result.kinetics))
        entry["summary"] = {
            str(row["Показатель"]): f"{row['Значение']} {row['Единица']}"
            for _, row in result.summary.iterrows()
        }
        entry["quality_all_passed"] = bool((result.quality["Статус"] == "пройдена").all())
        entry["quality"] = dict(zip(result.quality["Проверка"], result.quality["Статус"]))
        entry["warnings"] = list(result.warnings)
        entry["settings_database_overrides"] = str(
            result.settings.set_index("Параметр")["Значение"].get("Правки базы ThermoGar", "")
        ) if "Параметр" in result.settings.columns else None
        result.kinetics.to_csv(out / f"{key}_kinetics.csv", float_format="%.10g", lineterminator="\n")
    entry["seconds"] = round(time.perf_counter() - started, 1)
    report["cases"][key] = entry
    print(json.dumps({key: {k: entry.get(k) for k in ("status", "error", "kinetics_rows", "seconds")}}, ensure_ascii=False), flush=True)

(out / "nb_kwn_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
ok = all(item["status"] == "PASS" and item.get("quality_all_passed") and item.get("warnings")
         for item in report["cases"].values())
print("NB KWN CHECK:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
