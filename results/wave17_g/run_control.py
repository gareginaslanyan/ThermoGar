"""Контрольный прогон 17-Г: отделить среду от дефекта продукта.

Основной прогон шёл в MSIX-контейнере Claude Desktop, где %LOCALAPPDATA%
виртуализован (results/wave17_g/localappdata_probe.json). Здесь те же два
красных файла гоняются повторно с THERMOGAR_STATE_ROOT (штатный ключ,
app/thermogar_paths.py:180) на пути, который контейнером не переадресуется.

Код не правится. Аварийный порог не трогается. Идёт ПОСЛЕ основного прогона,
не параллельно с ним.

    python -B -X utf8 results/wave17_g/run_control.py
"""
import ast
import json
import os
import subprocess
import time
from pathlib import Path

import psutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
LOGS = OUT / "control" / "logs"
MEMLOG = OUT / "control" / "memlog"
for d in (LOGS, MEMLOG):
    d.mkdir(parents=True, exist_ok=True)

# results/validation/ закрыт .gitignore — состояние контроля в репозиторий не попадёт.
STATE_ROOT = ROOT / "results" / "validation" / "wave17_g_control_state"
STATE_ROOT.mkdir(parents=True, exist_ok=True)

PY = str(ROOT / ".venv-windows" / "Scripts" / "python.exe")
ENTRY_GIB = float(os.environ.get("REGRESS_ENTRY_GIB", "3.0"))
WAIT_S = int(os.environ.get("REGRESS_WAIT_S", "900"))


def abort_threshold() -> float:
    source = (ROOT / "tools/study_hn62m_wave12.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "E1_ABORT_FREE_GIB" for t in node.targets
        ):
            return float(ast.literal_eval(node.value))
    raise RuntimeError("E1_ABORT_FREE_GIB не найден")


ABORT_GIB = abort_threshold()
PYTEST = [PY, "-B", "-X", "utf8", "-m", "pytest"]
JOBS = [
    ("control_notslow__test_parallel_integration.py",
     PYTEST + ["tools/test_parallel_integration.py", "-q", "-m", "not slow", "-p", "no:cacheprovider"]),
    ("control_notslow__test_ui_g.py",
     PYTEST + ["tools/test_ui_g.py", "-q", "-m", "not slow", "-p", "no:cacheprovider"]),
    ("control_slow__test_ui_g.py",
     PYTEST + ["tools/test_ui_g.py", "-q", "-m", "slow", "-p", "no:cacheprovider"]),
]


def free_gib() -> float:
    return psutil.virtual_memory().available / 2**30


summary_path = OUT / "control" / "summary.jsonl"
for job, cmd in JOBS:
    waited = time.time()
    while free_gib() < ENTRY_GIB and time.time() - waited < WAIT_S:
        time.sleep(15)
    free_start = free_gib()
    record = {"job": job, "cmd": cmd, "state_root": str(STATE_ROOT),
              "entry_gib": ENTRY_GIB, "abort_gib": ABORT_GIB,
              "free_at_start_gib": round(free_start, 2)}
    log_path = LOGS / (job + ".log.txt")
    env = dict(os.environ, PYTHONHASHSEED="0",
               THERMOGAR_MEMLOG=str(MEMLOG / (job + ".memlog.jsonl")),
               THERMOGAR_STATE_ROOT=str(STATE_ROOT))
    started = time.time()
    peak, min_free, aborted = 0, free_start, False
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
