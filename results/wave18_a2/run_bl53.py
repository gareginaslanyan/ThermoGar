"""18-А2, BL-53: развести сбой 0x80000003 в test_parallel_integration средой.

База — прогон 18-А (results/wave18_a/run_regress.py, задание notslow__test_parallel_integration.py):
PYTHONHASHSEED=0, THERMOGAR_MEMLOG, THERMOGAR_STATE_ROOT=results/validation/wave18_a_state,
``-B -X utf8 -m pytest tools/test_parallel_integration.py -q -m "not slow" -p no:cacheprovider``.
Каждый вариант отличается от базы одним пунктом; каждый — отдельный процесс, по одному.
Код приложения и тестов не меняется.

    python -B -X utf8 results/wave18_a2/run_bl53.py [вариант ...]
"""
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
for d in (LOGS, MEMLOG):
    d.mkdir(parents=True, exist_ok=True)

PY = str(ROOT / ".venv-windows" / "Scripts" / "python.exe")
BASE_STATE = ROOT / "results/validation/wave18_a_state"
CMD = [PY, "-B", "-X", "utf8", "-m", "pytest", "tools/test_parallel_integration.py",
       "-q", "-m", "not slow", "-p", "no:cacheprovider"]
CASE = "test_temperature_scan_tables_match_with_and_without_pool"


def base_env(job: str) -> dict:
    return dict(os.environ, PYTHONHASHSEED="0",
                THERMOGAR_MEMLOG=str(MEMLOG / f"{job}.memlog.jsonl"),
                THERMOGAR_STATE_ROOT=str(BASE_STATE))


def variant(job: str) -> tuple[list, dict]:
    env, cmd = base_env(job), list(CMD)
    if job == "a_default_state_root":
        env.pop("THERMOGAR_STATE_ROOT")
    elif job == "b_wave18_a_state":
        pass
    elif job == "v_empty_state_root":
        empty = ROOT / "results/validation" / f"wave18_a2_empty_{int(time.time())}"
        empty.mkdir(parents=True)
        env["THERMOGAR_STATE_ROOT"] = str(empty)
    elif job == "g1_no_timeout_plugin":
        cmd += ["-p", "no:timeout"]
    elif job == "g2_timeout_exit":
        env["THERMOGAR_TIMEOUT_EXIT"] = "1"  # хук conftest возвращает None
    elif job == "g3_noconftest":
        cmd += ["--noconftest"]
    elif job == "d_no_hashseed":
        env.pop("PYTHONHASHSEED")
    elif job == "e_no_memlog":
        env.pop("THERMOGAR_MEMLOG")
    elif job == "zh_mpl_agg":
        env["MPLBACKEND"] = "Agg"
    elif job == "b_faulthandler":
        cmd.insert(1, "-X")
        cmd.insert(2, "faulthandler")
    else:
        raise SystemExit(f"неизвестный вариант {job}")
    return cmd, env


def run(job: str) -> dict:
    cmd, env = variant(job)
    log_path = LOGS / f"{job}.log.txt"
    diff = {k: env.get(k) for k in ("PYTHONHASHSEED", "THERMOGAR_STATE_ROOT", "THERMOGAR_MEMLOG",
                                     "THERMOGAR_TIMEOUT_EXIT", "MPLBACKEND")}
    started = time.time()
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
        peak = 0
        root_proc = psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                peak = max(peak, sum(c.memory_info().rss for c in
                                     [root_proc] + root_proc.children(recursive=True)))
            except psutil.Error:
                pass
            time.sleep(2)
    lines = [l for l in log_path.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    first_fail = next((l for l in lines if "fatal exception" in l or "Error" in l
                       or l.startswith(("FAILED", "E ")) or "INTERNALERROR" in l), "")
    return {"job": job, "cmd": cmd[1:], "env": diff, "exit": proc.returncode,
            "exit_hex": hex(proc.returncode & 0xFFFFFFFF),
            "first_line": lines[0] if lines else "", "first_failure": first_fail,
            "last_line": lines[-1] if lines else "",
            "seconds": round(time.time() - started, 1), "peak_tree_gib": round(peak / 2**30, 2),
            "free_at_end_gib": round(psutil.virtual_memory().available / 2**30, 2)}


for job in sys.argv[1:]:
    record = run(job)
    with open(OUT / "summary.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(record, ensure_ascii=False), flush=True)
