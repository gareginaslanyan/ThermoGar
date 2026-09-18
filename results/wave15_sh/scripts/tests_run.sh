#!/usr/bin/env bash
# 15-Ш, п. 4: тесты пофайлово, по одному процессу, -m "not slow", PYTHONHASHSEED=0.
# Память: вход >= 3,0 ГиБ свободной, останов при < 1,5 ГиБ (memwrap.py). Красный — стоп.
set -uo pipefail
TREE=/c/Users/gareg/Desktop/ThermoGar-w15d
PY=/c/Users/gareg/Desktop/ThermoGar/.venv-windows/Scripts/python.exe
OUT=$TREE/results/wave15_sh/tests
mkdir -p "$OUT"
cd "$TREE"
for file in "$@"; do
  name=$(basename "$file")
  PYTHONHASHSEED=0 "$PY" -B -X utf8 results/wave15_sh/scripts/memwrap.py "$OUT/$name.log.txt" -- \
    "$PY" -B -X utf8 -m pytest "$file" -q -m "not slow" -p no:cacheprovider
  code=$?
  echo "$name exit $code: $(tail -1 "$OUT/$name.log.txt")"
  if [ "$code" -ne 0 ]; then echo "СТОП на $name"; exit "$code"; fi
done
