#!/usr/bin/env bash
# 18-А, п. 6: регрессия пофайлово, по одному процессу, PYTHONHASHSEED=0 (копия 15-Ш).
# Память: вход >= 3,0 ГиБ, останов < 1,0 ГиБ (memwrap.py). Каталог состояния — THERMOGAR_STATE_ROOT.
# Аргументы: <маркер -m> <файлы…>. Красные собираются в конце, прогон не прерывается.
set -uo pipefail
TREE=/d/Pets/ThermoGar
PY=$TREE/.venv-windows/Scripts/python.exe
OUT=$TREE/results/wave18_a/tests
MARK=$1; shift
mkdir -p "$OUT"
cd "$TREE"
export THERMOGAR_STATE_ROOT='D:\Pets\ThermoGar\results\validation\wave18_a_state'
red=0
for file in "$@"; do
  name=$(basename "$file")
  tag=$name; [ "$MARK" = "slow" ] && tag="$name.slow"
  PYTHONHASHSEED=0 "$PY" -B -X utf8 results/wave18_a/scripts/memwrap.py "$OUT/$tag.log.txt" -- \
    "$PY" -B -X utf8 -m pytest "$file" -q -m "$MARK" -p no:cacheprovider
  code=$?
  echo "$tag exit $code: $(tail -1 "$OUT/$tag.log.txt")"
  [ "$code" -ne 0 ] && [ "$code" -ne 5 ] && red=$((red+1))
done
echo "КРАСНЫХ ФАЙЛОВ: $red"
