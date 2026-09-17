#!/usr/bin/env bash
# 15-Ф, п. 4: сверка упругих свойств. Снимки git archive <ревизия> app databases,
# отдельными процессами, по одному, PYTHONHASHSEED=0, пустой каталог состояния.
# Аргументы: <ревизия базы> <ревизия ветки> <каталог снимков>
set -uo pipefail
TREE=/c/Users/gareg/Desktop/ThermoGar-w15d
PY=/c/Users/gareg/Desktop/ThermoGar/.venv-windows/Scripts/python.exe
BASE=$1; HEAD=$2; SNAP=$3
OUT=$TREE/results/wave15_f/p4
mkdir -p "$OUT"
run() {  # rev mode case tag
  rm -rf "$OUT/out_$4"
  PYTHONHASHSEED=0 "$PY" -B -X utf8 "$TREE/results/wave15_f/scripts/memwrap.py" "$OUT/log_$4.txt" -- \
    "$PY" -B -X utf8 "$TREE/results/wave15_f/scripts/elastic_run.py" "$SNAP/src_$1" "$OUT/out_$4" "$2" "$3"
  echo "$4 exit $?"
}
# (а) Ni-20Cr, 700 °C
run "$BASE" on nicr "${BASE}_nicr_on"
run "$BASE" on nicr "${BASE}_nicr_on_repeat"
run "$BASE" env nicr "${BASE}_nicr_env"
run "$BASE" env nicr "${BASE}_nicr_env_repeat"
run "$HEAD" on nicr "${HEAD}_nicr_on"
run "$HEAD" on nicr "${HEAD}_nicr_on_repeat"
run "$HEAD" off nicr "${HEAD}_nicr_off"
run "$HEAD" off nicr "${HEAD}_nicr_off_repeat"
run "$HEAD" env nicr "${HEAD}_nicr_env"
# (б) Fe-15Cr-0,4C, 950 °C
run "$BASE" on fecrc "${BASE}_fecrc_on"
run "$HEAD" on fecrc "${HEAD}_fecrc_on"
# (в) без поправки: с хромом и без
run "$HEAD" off fecrc "${HEAD}_fecrc_off"
run "$HEAD" on fec800 "${HEAD}_fec800_on"
run "$HEAD" off fec800 "${HEAD}_fec800_off"
