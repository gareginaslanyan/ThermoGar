#!/usr/bin/env bash
# 21-E, step 7: tests one after another (one heavy stream). Run from the w21b root:
#   bash results/wave21_z/scripts/run_tests.sh
# Last lines of every run go to results/wave21_z/testy/<name>.log.
set -u
PY="/d/Pets/ThermoGar/.venv-windows/Scripts/python.exe"
OUT="results/wave21_z/testy"
mkdir -p "$OUT"
export MPLBACKEND=Agg
export PYTHONHASHSEED=0
export PYTHONUTF8=1
export THERMOGAR_STATE_ROOT="$(cygpath -w "$TEMP")\\tg21z_tests_state"

free_gib() {
    powershell -NoProfile -Command "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,2)" | tr -d '\r' | tr ',' '.'
}

run_pytest() {
    local name="$1"; shift
    echo "== $name start $(date +%H:%M:%S) free $(free_gib) GiB" | tee -a "$OUT/_hod.log"
    "$PY" -B -m pytest -p no:cacheprovider "$@" > "$OUT/$name.log" 2>&1
    echo "== $name exit $? $(date +%H:%M:%S)" | tee -a "$OUT/_hod.log"
    tail -1 "$OUT/$name.log" | tee -a "$OUT/_hod.log"
}

run_script() {
    local name="$1"; shift
    echo "== $name start $(date +%H:%M:%S) free $(free_gib) GiB" | tee -a "$OUT/_hod.log"
    "$PY" -B "$@" > "$OUT/$name.log" 2>&1
    echo "== $name exit $? $(date +%H:%M:%S)" | tee -a "$OUT/_hod.log"
    tail -2 "$OUT/$name.log" | tee -a "$OUT/_hod.log"
}

run_pytest test_chart_theme_21e tools/test_chart_theme_21e.py -q
run_pytest test_chart_legend_theme tools/test_chart_legend_theme.py -q
run_pytest test_chart_celsius_ticks tools/test_chart_celsius_ticks.py -q
run_pytest test_version_consistency tools/test_version_consistency.py -q

FREE=$(free_gib)
if awk -v f="$FREE" 'BEGIN{exit !(f >= 6.0)}'; then
    THERMOGAR_MEMLOG="results/wave21_z/testy/memlog_test_ui_f.jsonl" run_pytest test_ui_f tools/test_ui_f.py -q
else
    THERMOGAR_MEMLOG="results/wave21_z/testy/memlog_test_ui_f_1.jsonl" run_pytest test_ui_f_bez_slow tools/test_ui_f.py -q -m "not slow"
    THERMOGAR_MEMLOG="results/wave21_z/testy/memlog_test_ui_f_2.jsonl" run_pytest test_ui_f_slow tools/test_ui_f.py -q -m slow
fi
run_pytest test_ui_g tools/test_ui_g.py -q
run_pytest test_ui_h tools/test_ui_h.py -q

run_pytest test_sidebar_composition_error tools/test_sidebar_composition_error.py -q
run_pytest test_physical_overrides_toggle tools/test_physical_overrides_toggle.py -q
run_pytest test_equilibrium_solidus_fallback tools/test_equilibrium_solidus_fallback.py -q
run_pytest test_density_below_pdb tools/test_density_below_pdb.py -q
run_pytest test_precipitation_bl35 tools/test_precipitation_bl35.py -q
run_pytest test_precipitation_grid tools/test_precipitation_grid.py -q
run_pytest test_wave15_z tools/test_wave15_z.py -q
run_script thermogar_diffusion_test tools/thermogar_diffusion_test.py
run_script thermogar_precipitation_test tools/thermogar_precipitation_test.py
run_script thermogar_self_test tools/thermogar_self_test.py
run_pytest test_backend_calculations tools/test_backend_calculations.py -q
echo "== ALL DONE $(date +%H:%M:%S)" | tee -a "$OUT/_hod.log"
