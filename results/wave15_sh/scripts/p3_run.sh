#!/usr/bin/env bash
# 15-Ш, п. 3: плотность и подготовка упругости до/после BL-39.
# Снимки git archive <ревизия> app databases, отдельными процессами, по одному,
# PYTHONHASHSEED=0, пустой каталог состояния, memwrap: вход >= 3,0 ГиБ, останов < 1,5 ГиБ.
# Аргументы: <ревизия базы> <ревизия ветки> <каталог снимков>
set -uo pipefail
TREE=/c/Users/gareg/Desktop/ThermoGar-w15d
PY=/c/Users/gareg/Desktop/ThermoGar/.venv-windows/Scripts/python.exe
BASE=$1; HEAD=$2; SNAP=$3
OUT=$TREE/results/wave15_sh/p3
mkdir -p "$OUT"
density() {  # rev mode case
  tag="density_$1_$3_$2"
  rm -rf "$OUT/out_$tag"
  PYTHONHASHSEED=0 "$PY" -B -X utf8 "$TREE/results/wave15_sh/scripts/memwrap.py" "$OUT/log_$tag.txt" -- \
    "$PY" -B -X utf8 "$TREE/results/wave15_sh/scripts/density_run.py" "$SNAP/src_$1" "$OUT/out_$tag" "$2" "$3"
  echo "$tag exit $?"
}
elastic() {  # rev mode case [метка случая]
  tag="elastic_$1_${4:-$3}_$2"
  rm -rf "$OUT/out_$tag"
  PYTHONHASHSEED=0 "$PY" -B -X utf8 "$TREE/results/wave15_sh/scripts/memwrap.py" "$OUT/log_$tag.txt" -- \
    "$PY" -B -X utf8 "$TREE/results/wave15_f/scripts/elastic_run.py" "$SNAP/src_$1" "$OUT/out_$tag" "$2" "$3"
  echo "$tag exit $?"
}
for rev in "$BASE" "$HEAD"; do
  # (в) побайтово
  density "$rev" on nicr
  density "$rev" off nicr
  density "$rev" on fecrc
  density "$rev" off fecrc
  density "$rev" on nialcr
  elastic "$rev" on nicr
  elastic "$rev" off nicr
  elastic "$rev" on fecrc
  elastic "$rev" off fecrc
  # (а) Fe-1C, 800 °C; (б) Fe-10W-1C, 800 °C
  density "$rev" on fec800
  elastic "$rev" on fec800
  density "$rev" on fewc
  elastic "$rev" on "fe|W=10, C=1|FE|800" fewc
done
