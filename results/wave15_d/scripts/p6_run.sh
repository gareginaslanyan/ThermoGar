#!/usr/bin/env bash
# 15-Д, пункт 6: побайтовая сверка как 14-Б п. 6.
# Снимки git archive <ревизия> app databases, каждый дважды, отдельными процессами,
# по одному, PYTHONHASHSEED=0, пустой каталог состояния. Скрипт — results/wave13_r/p1/scripts/p1_run.py без изменений.
# Аргументы: <ревизия базы> <ревизия ветки> <каталог снимков>
set -euo pipefail
TREE=/c/Users/gareg/Desktop/ThermoGar-w15d
PY=/c/Users/gareg/Desktop/ThermoGar/.venv-windows/Scripts/python.exe
BASE=$1; HEAD=$2; SNAP=$3
OUT=$TREE/results/wave15_d/p6
mkdir -p "$SNAP" "$OUT"
for rev in "$BASE" "$HEAD"; do
  rm -rf "$SNAP/src_$rev"; mkdir -p "$SNAP/src_$rev"
  git -C "$TREE" archive "$rev" app databases | tar -x -C "$SNAP/src_$rev"
done
free_gib() { powershell -NoProfile -Command "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,2)"; }
for run in "$BASE" "${BASE}_repeat" "$HEAD" "${HEAD}_repeat"; do
  rev=${run%_repeat}
  while :; do f=$(free_gib | tr ',' '.'); awk "BEGIN{exit !($f>=2.0)}" && break; echo "$run ждём памяти: $f"; sleep 30; done
  echo "$run старт, свободно $f ГиБ"
  rm -rf "$OUT/out_$run"
  PYTHONHASHSEED=0 "$PY" -B -X utf8 "$TREE/results/wave13_r/p1/scripts/p1_run.py" "$SNAP/src_$rev" "$OUT/out_$run" > "$OUT/log_$run.txt" 2>&1
  echo "$run exit $?"
done
