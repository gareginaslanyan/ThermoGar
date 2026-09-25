#!/usr/bin/env python3
"""Замер времени и пиковой памяти дочернего процесса (22-А).

На машине нет GNU time, поэтому пик берётся из getrusage(RUSAGE_CHILDREN):
ru_maxrss на Linux — в КиБ, это пик резидентной памяти самого «тяжёлого»
потомка. Вывод команды дублируется в журнал, в конце журнала — строка ZAMER.

Запуск:
    python -B zamer.py --log <журнал.txt> -- <команда> [аргументы...]
"""

from __future__ import annotations

import argparse
import datetime as dt
import resource
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    started = time.perf_counter()
    stamp = dt.datetime.now().isoformat(timespec="seconds")
    with open(args.log, "w", encoding="utf-8") as log:
        log.write(f"# {stamp} $ {' '.join(command)}\n")
        log.flush()
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            log.write(line)
            log.flush()
        code = process.wait()
        wall = time.perf_counter() - started
        peak_kib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        summary = (
            f"ZAMER: код={code}; стена={wall:.1f} с; "
            f"пик RSS={peak_kib / 2**20:.3f} ГиБ ({peak_kib} КиБ)\n"
        )
        sys.stdout.write(summary)
        log.write(summary)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
