#!/usr/bin/env python3
"""22-В: очередь прогонов — не больше N одновременно, вход при свободной памяти не меньше 3 ГиБ.

Задания — JSON-список {"name": ..., "seed": ..., "cmd": [...], "limit_s": ...}; каждый прогон идёт
через zamer.py (журнал results/wave22_v/logs/<name>_s<seed>.txt, строка ZAMER). ``limit_s`` —
предел стены процесса (сверх собственного потолка скрипта): по нему процесс снимается.
Итог каждого прогона дописывается в results/wave22_v/logs/serija_runs.jsonl.

    python -B serija.py --jobs <задания.json> [--parallel 3]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = HERE.parent
ROOT = W.parents[1]


def free_gib() -> float:
    with open("/proc/meminfo", encoding="ascii") as fh:
        for line in fh:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) / 2**20
    return 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--parallel", type=int, default=3)
    args = parser.parse_args()
    jobs = json.loads(Path(args.jobs).read_text(encoding="utf-8"))
    running: list[tuple[dict, subprocess.Popen, float]] = []
    log = W / "logs" / "serija_runs.jsonl"
    pending = list(jobs)
    while pending or running:
        for item in list(running):
            job, proc, started = item
            code = proc.poll()
            wall = time.time() - started
            if code is None and wall > job.get("limit_s", 1e9):
                proc.kill()
                code = proc.wait()
                job["killed"] = True
            if code is not None:
                running.remove(item)
                entry = {"name": job["name"], "seed": job["seed"], "code": code, "wall_s": round(wall, 1),
                         "killed": bool(job.get("killed")), "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
                with log.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                print(json.dumps(entry, ensure_ascii=False), flush=True)
        while pending and len(running) < args.parallel:
            free = free_gib()
            if free < 3.0:
                print(f"память: свободно {free:.2f} ГиБ < 3, жду", flush=True)
                break
            job = pending.pop(0)
            env = dict(os.environ, PYTHONHASHSEED=str(job["seed"]), PYTHONDONTWRITEBYTECODE="1", MPLBACKEND="Agg")
            journal = W / "logs" / f"{job['name']}_s{job['seed']}.txt"
            cmd = [sys.executable, "-B", str(HERE / "zamer.py"), "--log", str(journal), "--", *job["cmd"]]
            proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            running.append((job, proc, time.time()))
            print(f"старт {job['name']} s{job['seed']} (свободно {free:.2f} ГиБ)", flush=True)
        time.sleep(2.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
