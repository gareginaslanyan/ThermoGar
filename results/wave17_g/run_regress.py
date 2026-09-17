"""Полная пофайловая регрессия 17-Г (выпуск 0.4.2, код d3f3d1c).

Копия раннера 14-Д (results/wave14_d/regress/run_regress.py) с тремя отличиями,
заданными заданием 17-Г:

* логи — results/wave17_g/logs/, замеры памяти — results/wave17_g/memlog/;
  THERMOGAR_MEMLOG выставляется на каждый прогон (хук tools/conftest.py, 15-О);
* ``test_ui_f -m slow`` идёт одним процессом при свободной памяти >= 6,0 ГиБ
  (RULES, правило 15-Т; пик 4,91 ГиБ), иначе — двумя группами ``-k``;
* для двух прогонов test_backend_calculations выставляется
  THERMOGAR_BACKEND_REPORT — отчёт по ячейкам для сверки эталона
  tools/backend_reference.md (пункт 4, как 13-Р2 Д-1).

Память:

* порог входа — ключ REGRESS_ENTRY_GIB (умолчание 3,0 ГиБ), ожидание —
  REGRESS_WAIT_S (умолчание 900 с). Константа в коде не правится;
* аварийный порог по ходу — E1_ABORT_FREE_GIB модуля tools/study_hn62m_wave12.py,
  читается из исходника и НЕ меняется;
* каждый файл — отдельный процесс, по одному, PYTHONHASHSEED=0.

    python -B -X utf8 results/wave17_g/run_regress.py [job ...]
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
ROOT = OUT.parents[1]
LOGS = OUT / "logs"
MEMLOG = OUT / "memlog"
BACKEND = OUT / "backend"
for d in (LOGS, MEMLOG, BACKEND):
    d.mkdir(parents=True, exist_ok=True)

PY = str(ROOT / ".venv-windows" / "Scripts" / "python.exe")
ENTRY_GIB = float(os.environ.get("REGRESS_ENTRY_GIB", "3.0"))
WAIT_S = int(os.environ.get("REGRESS_WAIT_S", "900"))
UI_F_SINGLE_GIB = float(os.environ.get("REGRESS_UI_F_SINGLE_GIB", "6.0"))  # RULES, 15-Т


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
# Состав по предполётному --collect-only -m slow (results/wave17_g/collect_preflight.jsonl):
SLOW_FILES = ["test_backend_calculations.py", "test_density_thermal_expansion.py",
              "test_liquidus_bisection.py", "test_phase_presets.py",
              "test_phase_presets_control.py", "test_ui_g.py", "test_ui_h.py"]
# Две группы на случай нехватки памяти: 9 + 3 = 12 и 3 + 3 + 3 = 9, всего 21.
UI_F_TWO_GROUPS = [
    ("g1", "test_solidification or test_binary_diagram"),
    ("g2", "test_isopleth_diagram or test_ternary_diagram or test_ternary_phase_map"),
]
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
jobs.append(("slow__test_ui_f.py", None))  # решается по свободной памяти в момент старта
for name in SCENARIOS:
    jobs.append((f"scenario__{name}", [PY, "-P", "-s", "-B", "-X", "utf8", f"tools/{name}", "--project-root", str(ROOT)]))


def free_gib() -> float:
    return psutil.virtual_memory().available / 2**30


def run(job: str, cmd: list, extra_env: dict | None = None) -> dict:
    waited = time.time()
    while free_gib() < ENTRY_GIB and time.time() - waited < WAIT_S:
        time.sleep(15)
    free_start = free_gib()
    record = {"job": job, "cmd": cmd, "entry_gib": ENTRY_GIB, "abort_gib": ABORT_GIB,
              "free_at_start_gib": round(free_start, 2), "waited_s": round(time.time() - waited)}
    if free_start < ENTRY_GIB:
        record["outcome"] = "НЕ ЗАПУЩЕН: свободной памяти меньше порога входа"
        return record
    log_path = LOGS / f"{job}.log.txt"
    memlog_path = MEMLOG / f"{job}.memlog.jsonl"
    env = dict(os.environ, PYTHONHASHSEED="0", THERMOGAR_MEMLOG=str(memlog_path))
    if extra_env:
        env.update(extra_env)
    record["memlog"] = memlog_path.name
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
    return record


only = set(sys.argv[1:])
summary_path = OUT / "summary.jsonl"
for job, cmd in jobs:
    if only and job not in only:
        continue
    extra = None
    if job == "notslow__test_backend_calculations.py":
        extra = {"THERMOGAR_BACKEND_REPORT": str(BACKEND / "backend_report_notslow.json")}
    elif job == "slow__test_backend_calculations.py":
        extra = {"THERMOGAR_BACKEND_REPORT": str(BACKEND / "backend_report_slow.json")}
    if job == "slow__test_ui_f.py":
        # RULES, 15-Т: одним процессом только при свободных >= 6,0 ГиБ.
        free_now = free_gib()
        if free_now >= UI_F_SINGLE_GIB:
            records = [run(job, PYTEST + ["tools/test_ui_f.py", "-q", "-m", "slow", "-p", "no:cacheprovider"])]
            records[0]["ui_f_mode"] = f"одним процессом (свободно {free_now:.2f} >= {UI_F_SINGLE_GIB:.1f} ГиБ)"
        else:
            records = []
            for suffix, expr in UI_F_TWO_GROUPS:
                rec = run(f"{job}__{suffix}",
                          PYTEST + ["tools/test_ui_f.py", "-q", "-m", "slow", "-k", expr, "-p", "no:cacheprovider"])
                rec["ui_f_mode"] = f"двумя группами (свободно {free_now:.2f} < {UI_F_SINGLE_GIB:.1f} ГиБ)"
                records.append(rec)
    else:
        records = [run(job, cmd, extra)]
    for record in records:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps(record, ensure_ascii=False), flush=True)
