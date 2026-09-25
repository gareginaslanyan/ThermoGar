#!/usr/bin/env bash
# 21-E, step 6: all frames and measurements against the running app (port 8637).
#   bash results/wave21_z/scripts/run_kadry.sh
set -u
PY="/d/Pets/ThermoGar/.venv-windows/Scripts/python.exe"
R="results/wave21_z"
"$PY" -B -X utf8 $R/scripts/kadry.py --theme Light > $R/kadry_run_svet.log 2>&1; echo "EXIT_L=$?" >> $R/kadry_run_svet.log
"$PY" -B -X utf8 $R/scripts/kadry.py --theme Dark > $R/kadry_run_tyomn.log 2>&1; echo "EXIT_D=$?" >> $R/kadry_run_tyomn.log
"$PY" -B -X utf8 $R/scripts/smena_temy.py > $R/smena_temy_run.log 2>&1; echo "EXIT_S=$?" >> $R/smena_temy_run.log
"$PY" -B -X utf8 $R/scripts/sem_faz.py > $R/sem_faz_run.log 2>&1; echo "EXIT_F=$?" >> $R/sem_faz_run.log
"$PY" -B -X utf8 $R/scripts/bylo_stalo.py > $R/bylo_stalo.md 2>&1; echo "EXIT_B=$?" >> $R/sem_faz_run.log
echo KADRY_DONE >> $R/sem_faz_run.log
