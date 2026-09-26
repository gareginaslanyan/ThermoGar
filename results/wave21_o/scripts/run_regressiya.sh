#!/usr/bin/env bash
# 21-O, step 6 (copy of 21-M): output results/wave21_o/testy, state tg21o_tests_state.
# 21-M, step 7 (copy of 21-I): output results/wave21_m/testy, state tg21m_tests_state.
# 21-I, step 5 (copy of 21-Z): full regression, one heavy stream. Run from the w21b root:
#   bash results/wave21_o/scripts/run_regressiya.sh [name ...]
# Every tools/test_*.py by pytest -B, every tools/*_test.py by python -B (main).
# tools/test_ui_f.py: one process only with >= 6.0 GiB free (tasks/RULES.md),
# otherwise two groups; THERMOGAR_MEMLOG in both cases.
# Full output of every run: results/wave21_o/testy/<name>.log; progress: _hod.log.
set -u
PY="/d/Pets/ThermoGar/.venv-windows/Scripts/python.exe"
OUT="results/wave21_o/testy"
mkdir -p "$OUT"
export MPLBACKEND=Agg
export PYTHONHASHSEED=0
export PYTHONUTF8=1
export THERMOGAR_STATE_ROOT="$(cygpath -w "$TEMP")\tg21o_tests_state"

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
    tail -3 "$OUT/$name.log" | tee -a "$OUT/_hod.log"
}

run_ui_f() {
    local free
    free=$(free_gib)
    if awk -v f="$free" 'BEGIN{exit !(f >= 6.0)}'; then
        echo "== test_ui_f: one process, free $free GiB" | tee -a "$OUT/_hod.log"
        THERMOGAR_MEMLOG="$OUT/memlog_test_ui_f.jsonl" run_pytest test_ui_f tools/test_ui_f.py -q
    else
        echo "== test_ui_f: two groups, free $free GiB" | tee -a "$OUT/_hod.log"
        THERMOGAR_MEMLOG="$OUT/memlog_test_ui_f_1.jsonl" run_pytest test_ui_f_bez_slow tools/test_ui_f.py -q -m "not slow"
        THERMOGAR_MEMLOG="$OUT/memlog_test_ui_f_2.jsonl" run_pytest test_ui_f_slow tools/test_ui_f.py -q -m slow
    fi
}

run_one() {
    local file="tools/$1.py"
    case "$1" in
        test_ui_f) run_ui_f ;;
        test_*) run_pytest "$1" "$file" -q ;;
        *_test) run_script "$1" "$file" ;;
    esac
}

if [ $# -gt 0 ]; then
    names="$*"
else
    names=$(ls tools/test_*.py tools/*_test.py | sed 's|tools/||; s|\.py$||' | sort -u)
fi
for name in $names; do
    run_one "$name"
done
echo "== ALL DONE $(date +%H:%M:%S)" | tee -a "$OUT/_hod.log"
