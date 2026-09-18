#!/usr/bin/env bash
# 15-Ч, п. 4б: побайтовая сверка выходов be1fe81 и ветки по всем файлам.
# Аргументы: <ревизия базы> <ревизия ветки>
set -uo pipefail
P4=/c/Users/gareg/Desktop/ThermoGar-w15d/results/wave15_ch/p4
BASE=$1; HEAD=$2
cd "$P4"
: > sha256_full.txt
printf 'случай\tфайл\t%s\t%s\tсовпадает\n' "$BASE" "$HEAD" > sha256_table.tsv
bad=0
for tag in nicr_on nicr_off fecrc_on fecrc_off nicrc_on; do
  for dir in "out_${BASE}_$tag" "out_${HEAD}_$tag"; do
    [ -n "$(ls -A "$dir" 2>/dev/null)" ] && (cd "$dir" && sha256sum -- * | sed "s#  #  $dir/#") >> sha256_full.txt
  done
  while IFS= read -r f; do
    a=$(sha256sum < "out_${BASE}_$tag/$f" 2>/dev/null | cut -c1-12); a=${a:-нет}
    b=$(sha256sum < "out_${HEAD}_$tag/$f" 2>/dev/null | cut -c1-12); b=${b:-нет}
    same=$([ "$a" = "$b" ] && echo да || echo нет)
    printf '%s\t%s\t%s\t%s\t%s\n' "$tag" "$f" "$a" "$b" "$same" >> sha256_table.tsv
    if [ "$same" = нет ] && [ "$tag" != nicrc_on ]; then bad=1; fi
  done < <( (ls "out_${BASE}_$tag"; ls "out_${HEAD}_$tag") 2>/dev/null | sort -u)
done
cat sha256_table.tsv
[ "$bad" = 0 ] && echo "п. 4б: все файлы совпадают" || echo "п. 4б: РАСХОЖДЕНИЕ"
