#!/usr/bin/env python3
"""22-А: серия прогонов — не больше N одновременно (задание: до 3).

План — JSON-список. Элемент ``{"tag": ..., "args": [...], "env": {...}}`` —
прогон ``kwn_run.py --tag <tag> <args>``; элемент с ``"cmd": [...]`` — любая
команда (например, ``ravnovesie.py``). Каждый идёт своим процессом через
``zamer.py`` (журнал ``logs/<tag>.txt``, пик памяти потомка); предел времени на
прогон держит сам ``kwn_run.py`` (``--limit-s``).

План перечитывается на каждом круге — в него можно дописывать; число
одновременных прогонов берётся из ``--jobs-file`` (если есть), иначе ``--jobs``.
Посчитанное пропускается: у прогона есть ``data/<tag>.json``, у команды — строка
``ZAMER: код=0`` в журнале. Так серию можно перезапустить после потери машины.

    python -B serija.py plan.json [--jobs 3] [--jobs-file f] [--log logs/serija_<имя>.txt]
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


def done(item: dict) -> bool:
    if "cmd" in item:
        log = BASE / "logs" / f"{item['tag']}.txt"
        return log.exists() and "ZAMER: код=0" in log.read_text(encoding="utf-8", errors="replace")
    return (BASE / "data" / f"{item['tag']}.json").exists()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan")
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--jobs-file")
    parser.add_argument("--log")
    args = parser.parse_args()
    plan_path = Path(args.plan)
    log_path = Path(args.log) if args.log else BASE / "logs" / f"serija_{plan_path.stem}.txt"
    started_tags: set[str] = set()
    running: list[tuple[dict, subprocess.Popen, float]] = []

    def note(text: str) -> None:
        line = f"{dt.datetime.now().isoformat(timespec='seconds')} {text}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def jobs() -> int:
        if args.jobs_file and Path(args.jobs_file).exists():
            try:
                return max(0, min(3, int(Path(args.jobs_file).read_text().strip())))
            except ValueError:
                pass
        return min(3, args.jobs)

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    note(f"план {plan_path}: всего {len(plan)}, к счёту {sum(not done(i) for i in plan)}, одновременно {jobs()}")
    while True:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        pending = [i for i in plan if i["tag"] not in started_tags and not done(i)]
        while pending and len(running) < jobs():
            item = pending.pop(0)
            started_tags.add(item["tag"])
            env = dict(os.environ)
            env.update({key: str(value) for key, value in item.get("env", {}).items()})
            inner = (
                [sys.executable, "-B", "-X", "utf8", *item["cmd"]] if "cmd" in item else
                [sys.executable, "-B", "-X", "utf8", str(HERE / "kwn_run.py"), "--tag", item["tag"], *item["args"]]
            )
            command = [
                sys.executable, "-B", str(HERE / "zamer.py"),
                "--log", str(BASE / "logs" / f"{item['tag']}.txt"), "--", *inner,
            ]
            process = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            running.append((item, process, time.perf_counter()))
            note(f"старт {item['tag']} {' '.join(item.get('args', item.get('cmd', [])))} env={item.get('env', {})}")
        if not running and not pending:
            break
        time.sleep(2)
        for entry in list(running):
            item, process, started = entry
            code = process.poll()
            if code is None:
                continue
            running.remove(entry)
            summary_path = BASE / "data" / f"{item['tag']}.json"
            brief = ""
            if "cmd" not in item and summary_path.exists():
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                brief = (
                    f"статус={summary.get('status')} строк={summary.get('rows')} "
                    f"t_конец={summary.get('final_time_s')} остановка={summary.get('stop')} "
                    f"доля%={summary.get('final_fraction_pct')} R_нм={summary.get('final_radius_nm')} "
                    f"стена={summary.get('wall_s')} пик_ГиБ={summary.get('peak_rss_gib')}"
                )
                if summary.get("status") == "error":
                    brief += f" ошибка={summary.get('error', '')[:160]!r}"
            note(f"конец {item['tag']} код={code} за {time.perf_counter() - started:.0f} с {brief}")
    note("серия завершена")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
