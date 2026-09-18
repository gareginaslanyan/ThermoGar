#!/usr/bin/env bash
# 15-Ч, п. 4: подготовка упругих свойств и VRH. Образец — results/wave15_f/scripts/p4_run.sh,
# сам прогон — results/wave15_f/scripts/elastic_run.py без изменений.
# Снимки git archive <ревизия> app databases, отдельными процессами, по одному,
# PYTHONHASHSEED=0, пустой каталог состояния.
# Аргументы: <ревизия базы> <ревизия ветки> <каталог снимков>
set -uo pipefail
TREE=/c/Users/gareg/Desktop/ThermoGar-w15d
PY=/c/Users/gareg/Desktop/ThermoGar/.venv-windows/Scripts/python.exe
BASE=$1; HEAD=$2; SNAP=$3
OUT=$TREE/results/wave15_ch/p4
mkdir -p "$OUT"
run() {  # rev mode case tag
  rm -rf "$OUT/out_$4"
  PYTHONHASHSEED=0 "$PY" -B -X utf8 "$TREE/results/wave15_ch/scripts/memwrap.py" "$OUT/log_$4.txt" -- \
    "$PY" -B -X utf8 "$TREE/results/wave15_f/scripts/elastic_run.py" "$SNAP/src_$1" "$OUT/out_$4" "$2" "$3"
  echo "$4 exit $?"
}
# (а) Ni-20Cr-0,3C, 700 °C: на базе падает, на ветке считается
run "$BASE" on nicrc "${BASE}_nicrc_on"
run "$HEAD" on nicrc "${HEAD}_nicrc_on"
run "$HEAD" on nicrc "${HEAD}_nicrc_on_repeat"
run "$HEAD" off nicrc "${HEAD}_nicrc_off"
# (б) побайтово: Ni-20Cr, 700 °C и Fe-15Cr-0,4C, 950 °C, галочка включена и снята
run "$BASE" on nicr "${BASE}_nicr_on"
run "$HEAD" on nicr "${HEAD}_nicr_on"
run "$BASE" off nicr "${BASE}_nicr_off"
run "$HEAD" off nicr "${HEAD}_nicr_off"
run "$BASE" on fecrc "${BASE}_fecrc_on"
run "$HEAD" on fecrc "${HEAD}_fecrc_on"
run "$BASE" off fecrc "${BASE}_fecrc_off"
run "$HEAD" off fecrc "${HEAD}_fecrc_off"
