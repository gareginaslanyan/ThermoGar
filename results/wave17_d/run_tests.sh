#!/bin/sh
# 17-Д п. 1: четыре прогона по одному, папка данных вне %LOCALAPPDATA%.
cd /d/Pets/ThermoGar
export THERMOGAR_STATE_ROOT='D:\Pets\ThermoGar\results\validation\wave17_d_state'
export PYTHONHASHSEED=0 MPLBACKEND=Agg
PY=.venv-windows/Scripts/python.exe
run() { name=$1; shift; echo "== $name $(date +%T)"; "$PY" -B -X utf8 -m pytest "$@" -q -p no:cacheprovider > "results/wave17_d/logs/$name.log" 2>&1; echo "exit $?"; tail -n 1 "results/wave17_d/logs/$name.log"; }
run ui_g_notslow tools/test_ui_g.py -m "not slow"
run ui_g_slow tools/test_ui_g.py -m slow
run parallel_integration tools/test_parallel_integration.py
run bl35 tools/test_precipitation_bl35.py
echo "== done $(date +%T)"
