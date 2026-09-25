#!/usr/bin/env bash
# 22-Б, шаг 2 г/д: расчётные тесты после правки — по одному процессу подряд, зерно 0.
# Журналы — results/wave22_b/logs/posle_test_*.txt (строка ZAMER — время и пик памяти).
set -u
cd "$(dirname "$0")/../../.."
W=results/wave22_b
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg
Z="python -B $W/scripts/zamer.py --log"
P="python -B -m pytest -p no:cacheprovider -v -rA --durations=0"
$Z $W/logs/posle_test_bl35.txt -- $P tools/test_precipitation_bl35.py > /dev/null 2>&1
$Z $W/logs/posle_test_swr.txt -- python -B tools/thermogar_precipitation_test.py > /dev/null 2>&1
THERMOGAR_BACKEND_REPORT=$W/data/posle_backend_kwn_report.json \
  $Z $W/logs/posle_test_backend_kwn.txt -- $P tools/test_backend_calculations.py -k kwn > /dev/null 2>&1
$Z $W/logs/posle_test_grid_wave15z.txt -- $P tools/test_precipitation_grid.py \
  "tools/test_wave15_z.py::test_run_precipitation_warns_when_nucleus_exceeds_cmax" \
  "tools/test_wave15_z.py::test_run_precipitation_is_silent_when_cmax_covers_nucleus" > /dev/null 2>&1
$Z $W/logs/posle_test_step_cap_22b.txt -- $P tools/test_kwn_step_cap_22b.py > /dev/null 2>&1
for f in bl35 swr backend_kwn grid_wave15z step_cap_22b; do
  echo "== $f"; grep -E "passed|failed|RESULT:|ZAMER" $W/logs/posle_test_$f.txt | tail -3
done
