#!/usr/bin/env bash
# 15-У, п. 4: тесты пофайлово, по одному процессу, -m "not slow", PYTHONHASHSEED=0.
# Память: вход >= 3,0 ГиБ свободной, останов при < 1,5 ГиБ (memwrap.py);
# по тестам — THERMOGAR_MEMLOG, хук из tools/conftest.py ветки wave15-tests подключён плагином.
set -uo pipefail
TREE=/c/Users/gareg/Desktop/ThermoGar-w15d
PY=/c/Users/gareg/Desktop/ThermoGar/.venv-windows/Scripts/python.exe
PLUG=$1; shift
OUT=$TREE/results/wave15_u/tests
mkdir -p "$OUT"
cd "$TREE"
for file in "$@"; do
  name=$(basename "$file")
  export PYTHONPATH="$(cygpath -w "$PLUG")" PYTHONHASHSEED=0
  export THERMOGAR_MEMLOG="$(cygpath -w "$OUT/memlog_$name.jsonl")"
  rm -f "$OUT/memlog_$name.jsonl"
  "$PY" -B -X utf8 results/wave15_u/scripts/memwrap.py "$OUT/$name.log.txt" -- \
    "$PY" -B -X utf8 -m pytest "$file" -q -m "not slow" -p no:cacheprovider -p memlog_plugin ${EXTRA_PLUGINS:-}
  code=$?
  echo "$name exit $code: $(tail -1 "$OUT/$name.log.txt")"
  if [ "$code" -ne 0 ]; then echo "СТОП на $name"; exit "$code"; fi
done
