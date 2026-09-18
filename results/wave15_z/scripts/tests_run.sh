#!/usr/bin/env bash
# 15-З, пункт 9: тесты пофайлово, отдельными процессами, без -m slow, порог свободной памяти 2,0 ГиБ.
# Каталог состояния — временный (не %LOCALAPPDATA%\ThermoGar).
TREE=/c/Users/gareg/Desktop/ThermoGar-w15d
PY=/c/Users/gareg/Desktop/ThermoGar/.venv-windows/Scripts/python.exe
OUT=$TREE/results/wave15_z/tests
mkdir -p "$OUT"
cd "$TREE"
for f in test_precipitation_bl35 test_backend_calculations test_precipitation_grid test_ui_g test_wave15_z; do
  free=$(bash results/wave15_z/scripts/free.sh 2.0)
  state=$(mktemp -d)
  start=$(date +%s)
  THERMOGAR_STATE_ROOT="$(cygpath -w "$state")" PYTHONHASHSEED=0 "$PY" -B -X utf8 -m pytest tools/$f.py -q -m "not slow" -p no:cacheprovider > "$OUT/$f.log.txt" 2>&1
  code=$?
  echo "$f free=$free exit=$code seconds=$(( $(date +%s) - start )) :: $(tail -1 "$OUT/$f.log.txt")"
  rm -rf "$state"
done
