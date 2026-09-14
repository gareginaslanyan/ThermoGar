"""Пофайловая регрессия выпуска 0.4.1 (13-Р2, пункт 3).

Каждый файл — отдельный процесс, по одному. Перед стартом ждём свободной
памяти ENTRY_GIB; по ходу, если свободной памяти меньше ABORT_GIB, процесс
снимается и это записывается.
"""
import json, os, subprocess, sys, time
from pathlib import Path
import psutil

ROOT = Path(r"C:\Users\gareg\Desktop\ThermoGar-w13r")
PY = r"C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe"
OUT = Path(__file__).resolve().parent
ENTRY_GIB = float(os.environ.get("REGRESS_ENTRY_GIB", "2.2"))
ABORT_GIB = float(os.environ.get("REGRESS_ABORT_GIB", "0.4"))

PYTEST_FILES = sorted(p.name for p in (ROOT / "tools").glob("test_*.py")) + sorted(
    p.name for p in (ROOT / "tools").glob("thermogar_*_test.py"))
SLOW_FILES = ["test_backend_calculations.py", "test_density_thermal_expansion.py",
              "test_liquidus_bisection.py", "test_phase_presets.py",
              "test_phase_presets_control.py", "test_ui_f.py", "test_ui_g.py", "test_ui_h.py"]
SCENARIOS = ["thermogar_converter_patch_test.py", "thermogar_diffusion_test.py",
             "thermogar_fe_database_test.py", "thermogar_physical_test.py",
             "thermogar_precipitation_test.py", "thermogar_properties_test.py",
             "thermogar_self_test.py"]

jobs = []
for name in PYTEST_FILES:
    jobs.append((f"notslow__{name}", [PY, "-B", "-X", "utf8", "-m", "pytest", f"tools/{name}", "-q", "-m", "not slow", "-p", "no:cacheprovider"]))
for name in SLOW_FILES:
    jobs.append((f"slow__{name}", [PY, "-B", "-X", "utf8", "-m", "pytest", f"tools/{name}", "-q", "-m", "slow", "-p", "no:cacheprovider"]))
for name in SCENARIOS:
    jobs.append((f"scenario__{name}", [PY, "-P", "-s", "-B", "-X", "utf8", f"tools/{name}", "--project-root", str(ROOT)]))

only = set(sys.argv[1:])
summary_path = OUT / "summary.jsonl"
done = set()
retry = os.environ.get("REGRESS_RETRY") == "1"
if summary_path.exists():
    done = {r["job"] for r in map(json.loads, filter(str.strip, summary_path.read_text(encoding="utf-8").splitlines())) if not (retry and r.get("aborted_low_memory"))}

env = dict(os.environ, PYTHONHASHSEED="0")
for job, cmd in jobs:
    if (only and job not in only) or job in done:
        continue
    while psutil.virtual_memory().available / 2**30 < ENTRY_GIB:
        time.sleep(30)
    free_start = psutil.virtual_memory().available / 2**30
    log_path = OUT / f"{job}.log"
    started = time.time()
    aborted = False
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
        root_proc = psutil.Process(proc.pid)
        peak, min_free = 0, 1e9
        while proc.poll() is None:
            try:
                rss = sum(c.memory_info().rss for c in [root_proc] + root_proc.children(recursive=True))
            except psutil.Error:
                rss = 0
            free = psutil.virtual_memory().available / 2**30
            peak, min_free = max(peak, rss), min(min_free, free)
            if free < ABORT_GIB:
                aborted = True
                for c in root_proc.children(recursive=True) + [root_proc]:
                    try:
                        c.kill()
                    except psutil.Error:
                        pass
            time.sleep(2)
    text = log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    last = next((l for l in reversed(text) if l.strip()), "")
    record = {"job": job, "exit": proc.returncode, "last_line": last,
              "seconds": round(time.time() - started, 1), "peak_tree_gib": round(peak / 2**30, 2),
              "free_at_start_gib": round(free_start, 2), "min_free_gib": round(min_free, 2),
              "aborted_low_memory": aborted}
    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(record, ensure_ascii=False), flush=True)
