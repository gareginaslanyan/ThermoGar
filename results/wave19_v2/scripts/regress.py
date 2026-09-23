"""Регрессия 19-В2 (копия results/wave19_a/scripts/regress.py): по файлу на процесс, время и пик памяти дерева процессов."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "wave19_v2" / "regress"
FILES = (
    "tools/test_phase_description_stub_keys.py",
    "tools/test_phase_description_order_words.py",
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, MPLBACKEND="Agg", PYTHONHASHSEED="0",
               THERMOGAR_STATE_ROOT=r"results\validation\wave19_v2_state")
    python = str(ROOT / ".venv-windows" / "Scripts" / "python.exe")
    rows = []
    for name in FILES if len(sys.argv) < 2 else sys.argv[1:]:
        log = OUT / (Path(name).stem + ".txt")
        free = psutil.virtual_memory().available / 2**30
        start = time.perf_counter()
        with log.open("w", encoding="utf-8") as handle:
            proc = subprocess.Popen(
                [python, "-B", "-X", "utf8", "-m", "pytest", "-p", "no:cacheprovider", "-q", "-rfE", name],
                cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT,
            )
            root = psutil.Process(proc.pid)
            peak = 0
            while proc.poll() is None:
                try:
                    total = root.memory_info().rss + sum(
                        child.memory_info().rss for child in root.children(recursive=True)
                    )
                    peak = max(peak, total)
                except psutil.Error:
                    pass
                time.sleep(0.2)
        elapsed = time.perf_counter() - start
        tail = log.read_text("utf-8", errors="replace").strip().splitlines()[-1]
        passed = re.search(r"(\d+) passed", tail)
        failed = re.search(r"(\d+) failed", tail)
        errors = re.search(r"(\d+) error", tail)
        row = (name, passed.group(1) if passed else "0", failed.group(1) if failed else "0",
               errors.group(1) if errors else "0", f"{elapsed:.1f}", f"{peak / 2**20:.0f}", f"{free:.2f}", proc.returncode, tail)
        rows.append(row)
        print(" | ".join(str(item) for item in row), flush=True)
    with (OUT / "summary.txt").open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(" | ".join(str(item) for item in row) + "\n")


if __name__ == "__main__":
    main()
