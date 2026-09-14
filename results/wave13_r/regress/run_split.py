"""Перегон файлов, которые целиком не помещаются в память: по группам, каждая в своём процессе."""
import json, os, subprocess, sys, time
from pathlib import Path
import psutil

ROOT = Path(r"C:\Users\gareg\Desktop\ThermoGar-w13r")
PY = r"C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe"
OUT = Path(__file__).resolve().parent
ENTRY_GIB, ABORT_GIB = 3.0, 0.4

JOBS = [(f"split_slow_ui_f__{k}", ["tools/test_ui_f.py", "-m", "slow", "-k", k])
        for k in ("test_solidification", "test_binary_diagram", "test_isopleth_diagram",
                  "test_ternary_diagram", "test_ternary_phase_map")]
JOBS.append(("rerun_notslow__test_ui_g.py", ["tools/test_ui_g.py", "-m", "not slow"]))

env = dict(os.environ, PYTHONHASHSEED="0")
for job, args in JOBS:
    while psutil.virtual_memory().available / 2**30 < ENTRY_GIB:
        time.sleep(30)
    free_start = psutil.virtual_memory().available / 2**30
    log_path = OUT / f"{job}.log"
    started = time.time(); aborted = False; peak = 0; min_free = 1e9
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen([PY, "-B", "-X", "utf8", "-m", "pytest", *args, "-q", "-p", "no:cacheprovider"],
                                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
        root = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                rss = sum(c.memory_info().rss for c in [root] + root.children(recursive=True))
            except psutil.Error:
                rss = 0
            free = psutil.virtual_memory().available / 2**30
            peak, min_free = max(peak, rss), min(min_free, free)
            if free < ABORT_GIB:
                aborted = True
                for c in root.children(recursive=True) + [root]:
                    try: c.kill()
                    except psutil.Error: pass
            time.sleep(2)
    lines = [l for l in log_path.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    rec = {"job": job, "exit": proc.returncode, "last_line": lines[-1] if lines else "",
           "seconds": round(time.time() - started, 1), "peak_tree_gib": round(peak / 2**30, 2),
           "free_at_start_gib": round(free_start, 2), "min_free_gib": round(min_free, 2), "aborted_low_memory": aborted}
    with open(OUT / "summary.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False), flush=True)
