#!/usr/bin/env bash
# 21-E, step 7, second part: after the final frames (style.css with role="group").
#   bash results/wave21_e/scripts/run_tests_2.sh
set -u
PY="/d/Pets/ThermoGar/.venv-windows/Scripts/python.exe"
OUT="results/wave21_e/testy"
export MPLBACKEND=Agg PYTHONHASHSEED=0 PYTHONUTF8=1
export THERMOGAR_STATE_ROOT="$(cygpath -w "$TEMP")\tg21e_tests_state"
for spec in "test_chart_theme_21e:tools/test_chart_theme_21e.py" "test_backend_calculations:tools/test_backend_calculations.py"; do
    name="${spec%%:*}"; file="${spec#*:}"
    echo "== $name start $(date +%H:%M:%S)" | tee -a "$OUT/_hod.log"
    "$PY" -B -m pytest -p no:cacheprovider "$file" -q > "$OUT/$name.log" 2>&1
    echo "== $name exit $? $(date +%H:%M:%S)" | tee -a "$OUT/_hod.log"
    tail -1 "$OUT/$name.log" | tee -a "$OUT/_hod.log"
done
echo "== PART2 DONE $(date +%H:%M:%S)" | tee -a "$OUT/_hod.log"
