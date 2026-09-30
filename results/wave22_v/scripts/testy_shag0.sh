#!/usr/bin/env bash
# 22-В, шаг 0: проверочные расчётные тесты, зерно 0; до 3 процессов одновременно.
# Журналы — results/wave22_v/logs/shag0_*.txt (строка ZAMER — время и пик памяти).
set -u
cd "$(dirname "$0")/../../.."
W=results/wave22_v
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg
Z="python -B $W/scripts/zamer.py --log"
P="python -B -m pytest -p no:cacheprovider -v -rA --durations=0"
( $Z $W/logs/shag0_bl35.txt -- $P tools/test_precipitation_bl35.py > /dev/null 2>&1
  $Z $W/logs/shag0_step_cap_22b.txt -- $P tools/test_kwn_step_cap_22b.py > /dev/null 2>&1 ) &
( $Z $W/logs/shag0_grid.txt -- $P tools/test_precipitation_grid.py > /dev/null 2>&1
  $Z $W/logs/shag0_density.txt -- $P tools/test_density.py > /dev/null 2>&1
  $Z $W/logs/shag0_swr.txt -- python -B tools/thermogar_precipitation_test.py > /dev/null 2>&1 ) &
( $Z $W/logs/shag0_backend_kwn.txt -- $P tools/test_backend_calculations.py -k "kwn or KWN" > /dev/null 2>&1 ) &
wait
for f in bl35 step_cap_22b grid density backend_kwn swr; do
  echo "== $f"; grep -E "passed|failed|RESULT:|ZAMER" $W/logs/shag0_$f.txt | tail -3
done
