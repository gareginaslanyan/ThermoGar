"""Пофайловая регрессия 14-Г (копия раннера 14-Б; файлы — список задания 14-Г) — порядок 13-Р2 (results/wave13_r/regress/run_regress.py).

Каждый файл — отдельный процесс, по одному, PYTHONHASHSEED=0.

Отличия от 13-Р2 — только память, по заданию 14-Б («как в 14-А»):

* порог входа 3,0 ГиБ свободной физической памяти. Раннер ждёт его до
  WAIT_S секунд; не дождался — файл не запускается, в сводку пишется отказ;
* аварийный порог по ходу — E1_ABORT_FREE_GIB модуля
  tools/study_hn62m_wave12.py (1,0 ГиБ), читается из исходника, не меняется.
  В 13-Р2 было 0,4 ГиБ;
* test_ui_f -m slow сразу идёт по пяти группам, как его в итоге прошла 13-Р2:
  одним процессом он набирает 8,1 ГиБ (BL-27).

    python -B -X utf8 run_regress.py [job ...]
"""
import ast
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PY = r"C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe"
ENTRY_GIB = 3.0
WAIT_S = 900


def abort_threshold() -> float:
    source = (ROOT / "tools/study_hn62m_wave12.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "E1_ABORT_FREE_GIB" for t in node.targets
        ):
            return float(ast.literal_eval(node.value))
    raise RuntimeError("E1_ABORT_FREE_GIB не найден")


ABORT_GIB = abort_threshold()

PYTEST_FILES = sorted(p.name for p in (ROOT / "tools").glob("test_*.py")) + sorted(
    p.name for p in (ROOT / "tools").glob("thermogar_*_test.py"))
SLOW_FILES = ["test_backend_calculations.py", "test_density_thermal_expansion.py",
              "test_liquidus_bisection.py", "test_phase_presets.py",
              "test_phase_presets_control.py", "test_ui_g.py", "test_ui_h.py"]
UI_F_SLOW_GROUPS = ["test_solidification", "test_binary_diagram", "test_isopleth_diagram",
                    "test_ternary_diagram", "test_ternary_phase_map"]
SCENARIOS = ["thermogar_converter_patch_test.py", "thermogar_diffusion_test.py",
             "thermogar_fe_database_test.py", "thermogar_physical_test.py",
             "thermogar_precipitation_test.py", "thermogar_properties_test.py",
             "thermogar_self_test.py"]

PYTEST = [PY, "-B", "-X", "utf8", "-m", "pytest"]
jobs = []
for name in PYTEST_FILES:
    jobs.append((f"notslow__{name}", PYTEST + [f"tools/{name}", "-q", "-m", "not slow", "-p", "no:cacheprovider"]))
for name in SLOW_FILES:
    jobs.append((f"slow__{name}", PYTEST + [f"tools/{name}", "-q", "-m", "slow", "-p", "no:cacheprovider"]))
for group in UI_F_SLOW_GROUPS:
    jobs.append((f"slow__test_ui_f.py__{group}",
                 PYTEST + ["tools/test_ui_f.py", "-q", "-m", "slow", "-k", group, "-p", "no:cacheprovider"]))
for name in SCENARIOS:
    jobs.append((f"scenario__{name}", [PY, "-P", "-s", "-B", "-X", "utf8", f"tools/{name}", "--project-root", str(ROOT)]))


def free_gib() -> float:
    return psutil.virtual_memory().available / 2**30


only = set(sys.argv[1:])
summary_path = OUT / "summary.jsonl"
env = dict(os.environ, PYTHONHASHSEED="0")
for job, cmd in jobs:
    if only and job not in only:
        continue
    waited = time.time()
    while free_gib() < ENTRY_GIB and time.time() - waited < WAIT_S:
        time.sleep(15)
    free_start = free_gib()
    record = {"job": job, "entry_gib": ENTRY_GIB, "abort_gib": ABORT_GIB,
              "free_at_start_gib": round(free_start, 2), "waited_s": round(time.time() - waited)}
    if free_start < ENTRY_GIB:
        record["outcome"] = "НЕ ЗАПУЩЕН: свободной памяти меньше порога входа"
    else:
        log_path = OUT / f"{job}.log.txt"  # *.log в .gitignore
        started = time.time()
        aborted = False
        peak, min_free = 0, free_start
        with open(log_path, "w", encoding="utf-8", errors="replace") as log:
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
            root_proc = psutil.Process(proc.pid)
            while proc.poll() is None:
                try:
                    rss = sum(c.memory_info().rss for c in [root_proc] + root_proc.children(recursive=True))
                except psutil.Error:
                    rss = 0
                free = free_gib()
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
        record.update({
            "exit": proc.returncode,
            "last_line": next((line for line in reversed(text) if line.strip()), ""),
            "seconds": round(time.time() - started, 1),
            "peak_tree_gib": round(peak / 2**30, 2),
            "min_free_gib": round(min_free, 2),
            "aborted_low_memory": aborted,
        })
    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(record, ensure_ascii=False), flush=True)
