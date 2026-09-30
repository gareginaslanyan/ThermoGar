#!/usr/bin/env bash
# 22-В, шаг 1 б: ячейка KWN ni (и al) на исходниках каждого из 15 коммитов 1c47789..fc4a64d и fc4a64d.
# Исходники — git archive <коммит> app tools databases в _to_delete/22v_src/w<коммит>/ (вне git).
# Аргументы: <база> <зерно> [коммиты...]; по одному процессу подряд.
set -u
cd "$(dirname "$0")/../../.."
W=results/wave22_v
DB=$1; SEED=$2; shift 2
export PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg
for h in "$@"; do
  T=_to_delete/22v_src/w$h; [ "$h" = 1c47789 ] && T=_to_delete/22v_worktrees/w1c47789
  [ "$h" = HEAD ] && T=.
  PYTHONHASHSEED=$SEED python -B $W/scripts/zamer.py --log $W/logs/bl28_${DB}_${h}_s${SEED}.txt -- \
    python -B $W/scripts/bl28_run.py --tree $T --db $DB --tag $h --out $W/bl28 > /dev/null 2>&1
  echo "$h $(grep -o '"rows": [0-9]*' $W/bl28/${DB}_${h}_s${SEED}.json 2>/dev/null) $(grep ZAMER $W/logs/bl28_${DB}_${h}_s${SEED}.txt)"
done
