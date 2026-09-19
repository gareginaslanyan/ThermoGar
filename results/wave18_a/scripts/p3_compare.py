"""18-А, п. 4: SHA-256 выходов до и после BL-47, построчно по файлам.

    python p3_compare.py <каталог p3> <ревизия базы> <ревизия ветки>

Пишет sha256_table.tsv (первые 12 знаков) и sha256_full.txt (полные хеши).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

p3 = Path(sys.argv[1]).resolve()
base, head = sys.argv[2], sys.argv[3]

rows = ["run\tfile\tbase\thead\tequal"]
full = []
for base_dir in sorted(p3.glob(f"out_*_{base}_*")):
    run = base_dir.name.replace(f"_{base}_", "_REV_")
    head_dir = p3 / base_dir.name.replace(f"_{base}_", f"_{head}_")
    names = sorted(
        {p.name for p in base_dir.iterdir()} | {p.name for p in head_dir.iterdir()}
        if head_dir.is_dir()
        else {p.name for p in base_dir.iterdir()}
    )
    for name in names:
        digests = []
        for directory in (base_dir, head_dir):
            path = directory / name
            digests.append(hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "—")
        equal = "да" if digests[0] == digests[1] else "НЕТ"
        rows.append(f"{run}\t{name}\t{digests[0][:12]}\t{digests[1][:12]}\t{equal}")
        full.append(f"{run}\t{name}\t{digests[0]}\t{digests[1]}")

(p3 / "sha256_table.tsv").write_bytes(("\n".join(rows) + "\n").encode("utf-8"))
(p3 / "sha256_full.txt").write_bytes(("\n".join(full) + "\n").encode("utf-8"))
print("\n".join(rows))
