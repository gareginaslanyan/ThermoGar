"""Прогоны test_ui_f по группам с замером памяти (волна 15-О, BL-27).

Раннер — сокращённая копия results/wave14_d/regress/run_regress.py:

* порог входа 3,0 ГиБ свободной физической памяти (ключ --entry-gib),
  раннер ждёт его до 900 с;
* аварийный порог по ходу — E1_ABORT_FREE_GIB модуля
  tools/study_hn62m_wave12.py (1,0 ГиБ), читается из исходника;
* пик — рабочий набор дерева процесса, опрос раз в 2 с;
* по тестам память пишет tools/conftest.py в <stage>/<job>.memlog.jsonl
  (переменная THERMOGAR_MEMLOG).

    python -B -X utf8 run_groups.py <stage> <job> [<job> ...] [--entry-gib X] [--env K=V ...]

Задания — имена из JOBS ниже.
"""
import argparse
import ast
import json
import os
import subprocess
import time
from pathlib import Path

import psutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PY = r"C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe"
WAIT_S = 900

NOT_SLOW_A = ("test_startup_is_clean or test_single_equilibrium or test_temperature_scan"
              " or test_concentration_scan or test_energy_curve or test_driving_force"
              " or test_tzero_in_narrow_window")
BASE = [PY, "-B", "-X", "utf8", "-m", "pytest", "tools/test_ui_f.py", "-q", "-p", "no:cacheprovider"]
JOBS = {
    "notslow_a": BASE + ["-m", "not slow", "-k", NOT_SLOW_A],
    "notslow_b": BASE + ["-m", "not slow", "-k", f"not ({NOT_SLOW_A})"],
    "notslow": BASE + ["-m", "not slow"],
    "slow": BASE + ["-m", "slow"],
    "slow_half1": BASE + ["-m", "slow", "-k", "test_solidification or test_binary_diagram"],
    "slow_half2": BASE + ["-m", "slow", "-k", "not (test_solidification or test_binary_diagram)"],
    "ui_g_notslow": [PY, "-B", "-X", "utf8", "-m", "pytest", "tools/test_ui_g.py", "-q",
                     "-m", "not slow", "-p", "no:cacheprovider"],
}
for group in ("test_solidification", "test_binary_diagram", "test_isopleth_diagram",
              "test_ternary_diagram", "test_ternary_phase_map"):
    JOBS[f"slow__{group}"] = BASE + ["-m", "slow", "-k", group]


def abort_threshold() -> float:
    source = (ROOT / "tools/study_hn62m_wave12.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "E1_ABORT_FREE_GIB" for t in node.targets
        ):
            return float(ast.literal_eval(node.value))
    raise RuntimeError("E1_ABORT_FREE_GIB не найден")


def free_gib() -> float:
    return psutil.virtual_memory().available / 2**30


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage")
    parser.add_argument("jobs", nargs="+")
    parser.add_argument("--entry-gib", type=float, default=3.0)
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--extra", action="append", default=[], help="доп. аргумент pytest")
    args = parser.parse_args()
    abort_gib = abort_threshold()
    stage_dir = OUT / args.stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    extra_env = dict(item.split("=", 1) for item in args.env)
    for job in args.jobs:
        cmd = JOBS[job] + args.extra
        waited = time.time()
        while free_gib() < args.entry_gib and time.time() - waited < WAIT_S:
            time.sleep(15)
        free_start = free_gib()
        record = {"stage": args.stage, "job": job, "cmd": " ".join(cmd[1:]), "env": extra_env,
                  "entry_gib": args.entry_gib, "abort_gib": abort_gib,
                  "free_at_start_gib": round(free_start, 2), "waited_s": round(time.time() - waited)}
        if free_start < args.entry_gib:
            record["outcome"] = "НЕ ЗАПУЩЕН: свободной памяти меньше порога входа"
        else:
            memlog = stage_dir / f"{job}.memlog.jsonl"
            memlog.unlink(missing_ok=True)
            env = dict(os.environ, PYTHONHASHSEED="0", THERMOGAR_MEMLOG=str(memlog), **extra_env)
            log_path = stage_dir / f"{job}.log.txt"
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
                    if free < abort_gib and not aborted:
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
        with open(OUT / "summary.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
