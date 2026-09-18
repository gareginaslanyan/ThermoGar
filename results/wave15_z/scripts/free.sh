#!/usr/bin/env bash
# Ждать, пока свободной физической памяти станет не меньше $1 ГиБ; печатает значение.
need=$1
while :; do
  f=$(powershell -NoProfile -Command "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB,2)" | tr -d '\r' | tr ',' '.')
  awk "BEGIN{exit !($f>=$need)}" && { echo "$f"; break; }
  echo "ждём памяти: $f < $need" >&2; sleep 30
done
