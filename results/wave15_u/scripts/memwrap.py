"""15-У: запустить команду, следить за деревом процессов и свободной памятью.

    python memwrap.py <лог> -- <команда…>

Порог входа 3,0 ГиБ свободной памяти; по ходу — останов при свободной < 1,5 ГиБ.
Итог дописывается в results/wave15_u/memory.jsonl.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import psutil

GIB = 2**30
ENTRY_GIB = 3.0
ABORT_GIB = 1.5

log = Path(sys.argv[1])
command = sys.argv[sys.argv.index("--") + 1:]
free = psutil.virtual_memory().available / GIB
if free < ENTRY_GIB:
    print(f"мало памяти на входе: {free:.2f} ГиБ")
    sys.exit(3)
started = time.time()
with log.open("wb") as handle:
    process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT)
    parent = psutil.Process(process.pid)
    peak = 0
    min_free = free
    aborted = False
    while process.poll() is None:
        total = 0
        try:
            for member in [parent] + parent.children(recursive=True):
                try:
                    total += member.memory_info().rss
                except psutil.Error:
                    pass
        except psutil.Error:
            pass
        peak = max(peak, total)
        now_free = psutil.virtual_memory().available / GIB
        min_free = min(min_free, now_free)
        if now_free < ABORT_GIB:
            aborted = True
            for member in parent.children(recursive=True) + [parent]:
                try:
                    member.kill()
                except psutil.Error:
                    pass
            break
        time.sleep(0.2)
    code = process.wait()
record = {
    "log": log.name,
    "exit": code,
    "aborted_low_memory": aborted,
    "free_at_start_gib": round(free, 2),
    "min_free_gib": round(min_free, 2),
    "peak_tree_gib": round(peak / GIB, 2),
    "seconds": round(time.time() - started, 1),
}
with (Path(__file__).resolve().parent.parent / "memory.jsonl").open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
print(json.dumps(record, ensure_ascii=False))
sys.exit(code)
