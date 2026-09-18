#!/usr/bin/env bash
# 15-Н2, пункт 3: только tools/test_wave15_z.py, отдельным процессом, без -m slow.
# Порог свободной памяти 2,0 ГиБ проверяется один раз; ниже порога — не запускать.
# Каталог состояния — временный (не %LOCALAPPDATA%\ThermoGar).
TREE=/c/Users/gareg/Desktop/ThermoGar-w15e
PY=/c/Users/gareg/Desktop/ThermoGar/.venv-windows/Scripts/python.exe
OUT=$TREE/results/wave15_n/tests
cd "$TREE"
free=$(powershell -NoProfile -Command "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,2)" | tr -d '\r' | tr ',' '.')
if ! awk "BEGIN{exit !($free>=2.0)}"; then echo "свободно $free ГиБ < 2,0 — не запускаю"; exit 3; fi
state=$(mktemp -d)
start=$(date +%s)
THERMOGAR_STATE_ROOT="$(cygpath -w "$state")" PYTHONHASHSEED=0 "$PY" -B -X utf8 -m pytest tools/test_wave15_z.py -q -m "not slow" -p no:cacheprovider > "$OUT/test_wave15_z.log.txt" 2>&1
code=$?
echo "test_wave15_z free=$free exit=$code seconds=$(( $(date +%s) - start )) :: $(tail -1 "$OUT/test_wave15_z.log.txt")" | tee "$OUT/summary.txt"
rm -rf "$state"
