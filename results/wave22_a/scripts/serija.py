#!/usr/bin/env python3
"""22-А: серия прогонов ``kwn_run.py`` — не больше N одновременно (задание: 3).

План — JSON-список ``{"tag": ..., "args": [...], "env": {...}}``. Каждый прогон
идёт своим процессом через ``zamer.py`` (журнал ``logs/<tag>.txt``, пик памяти
потомка); предел времени на прогон держит сам ``kwn_run.py`` (``--limit-s``).
Уже посчитанные прогоны (есть ``data/<tag>.json``) пропускаются — серию можно
перезапустить после потери машины.

    python -B serija.py plan.json [--jobs 3] [--log logs/serija_<имя>.txt]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan")
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--log")
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    log_path = Path(args.log) if args.log else BASE / "logs" / f"serija_{Path(args.plan).stem}.txt"
    pending = [item for item in plan if not (BASE / "data" / f"{item['tag']}.json").exists()]
    running: list[tuple[dict, subprocess.Popen, float]] = []

    def note(text: str) -> None:
        line = f"{dt.datetime.now().isoformat(timespec='seconds')} {text}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    note(f"план {args.plan}: всего {len(plan)}, к счёту {len(pending)}, одновременно {args.jobs}")
    while pending or running:
        while pending and len(running) < args.jobs:
            item = pending.pop(0)
            env = dict(os.environ)
            env.update({key: str(value) for key, value in item.get("env", {}).items()})
            command = [
                sys.executable, "-B", str(HERE / "zamer.py"),
                "--log", str(BASE / "logs" / f"{item['tag']}.txt"), "--",
                sys.executable, "-B", "-X", "utf8", str(HERE / "kwn_run.py"),
                "--tag", item["tag"], *item["args"],
            ]
            process = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            running.append((item, process, time.perf_counter()))
            note(f"старт {item['tag']} {' '.join(item['args'])} env={item.get('env', {})}")
        time.sleep(2)
        for entry in list(running):
            item, process, started = entry
            code = process.poll()
            if code is None:
                continue
            running.remove(entry)
            summary_path = BASE / "data" / f"{item['tag']}.json"
            brief = ""
            if summary_path.exists():
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                brief = (
                    f"статус={summary.get('status')} строк={summary.get('rows')} "
                    f"t_конец={summary.get('final_time_s')} остановка={summary.get('stop')} "
                    f"доля%={summary.get('final_fraction_pct')} R_нм={summary.get('final_radius_nm')} "
                    f"стена={summary.get('wall_s')} пик_ГиБ={summary.get('peak_rss_gib')}"
                )
            note(f"конец {item['tag']} код={code} за {time.perf_counter() - started:.0f} с {brief}")
    note("серия завершена")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
