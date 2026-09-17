#!/usr/bin/env bash
# 15-У, п. 3: побайтовая сверка плотности. Снимки git archive <ревизия> app databases,
# каждый режим дважды, отдельными процессами, по одному, PYTHONHASHSEED=0, пустой каталог состояния.
# Аргументы: <ревизия базы> <ревизия ветки> <каталог снимков>
set -uo pipefail
TREE=/c/Users/gareg/Desktop/ThermoGar-w15d
PY=/c/Users/gareg/Desktop/ThermoGar/.venv-windows/Scripts/python.exe
BASE=$1; HEAD=$2; SNAP=$3
OUT=$TREE/results/wave15_u/p3
mkdir -p "$OUT"
run() {  # rev mode tag
  rm -rf "$OUT/out_$3"
  PYTHONHASHSEED=0 "$PY" -B -X utf8 "$TREE/results/wave15_u/scripts/memwrap.py" "$OUT/log_$3.txt" -- \
    "$PY" -B -X utf8 "$TREE/results/wave15_u/scripts/density_run.py" "$SNAP/src_$1" "$OUT/out_$3" "$2"
  echo "$3 exit $?"
}
run "$BASE" on "${BASE}_on_repeat"
run "$BASE" env "${BASE}_env"
run "$BASE" env "${BASE}_env_repeat"
run "$HEAD" on "${HEAD}_on"
run "$HEAD" on "${HEAD}_on_repeat"
run "$HEAD" off "${HEAD}_off"
run "$HEAD" off "${HEAD}_off_repeat"
run "$HEAD" env "${HEAD}_env"
