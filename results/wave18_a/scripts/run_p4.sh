#!/usr/bin/env bash
# 18-А, п. 4: «Плотность», «Плотность по T», «Упругие свойства» до/после BL-47.
# Снимки: <каталог снимков>/src_base (git archive 99da155 app databases) и
# src_head (app и databases рабочего дерева ветки). Отдельными процессами, по одному,
# PYTHONHASHSEED=0, пустой каталог состояния, memwrap: вход >= 3,0 ГиБ, останов < 1,0 ГиБ.
set -uo pipefail
TREE=/d/Pets/ThermoGar
PY=$TREE/.venv-windows/Scripts/python.exe
SNAP=$1
OUT=$TREE/results/wave18_a/${P4_DIR:-p4}
SC=$TREE/results/wave18_a/scripts
mkdir -p "$OUT"
run() {  # kind rev mode case
  tag="$1_$2_$4_$3"
  rm -rf "$OUT/out_$tag"
  PYTHONHASHSEED=0 "$PY" -B -X utf8 "$SC/memwrap.py" "$OUT/log_$tag.txt" -- \
    "$PY" -B -X utf8 "$SC/$1_run.py" "$SNAP/src_$2" "$OUT/out_$tag" "$3" "$4"
  echo "$tag exit $?"
}
for rev in base head; do
  for c in nicr nialcr fecrc; do
    for m in on off; do
      run density "$rev" "$m" "$c"
      run elastic "$rev" "$m" "$c"
    done
  done
done
