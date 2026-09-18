"""14-Б (копия раннера 14-А без изменений логики): запуск одного прогона отдельным процессом под контролем памяти.

    python -B -X utf8 runner.py <метка> <скрипт.py> [аргументы скрипта...]

* перед стартом — свободная физическая память; меньше 3,0 ГиБ — прогон не
  запускается, в журнал пишется отказ;
* потомок — интерпретатор этого же окружения, ``PYTHONHASHSEED=0``;
* по ходу раз в 0,25 с — свободная память и рабочий набор потомка; если
  свободной памяти стало меньше аварийного порога модуля
  ``tools/study_hn62m_wave12.py`` (``E1_ABORT_FREE_GIB``), потомок снимается.
  Порог читается из исходника модуля, не копируется и не меняется.

Раннер сам ничего не считает и тяжёлых пакетов не импортирует.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MIN_FREE_GIB = 3.0


def abort_threshold() -> float:
    source = (ROOT / "tools/study_hn62m_wave12.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "E1_ABORT_FREE_GIB" for t in node.targets
        ):
            return float(ast.literal_eval(node.value))
    raise RuntimeError("E1_ABORT_FREE_GIB не найден")


def main() -> int:
    label, script, *args = sys.argv[1:]
    abort_gib = abort_threshold()
    log_path = HERE / "runs.jsonl"
    record: dict = {"метка": label, "скрипт": script, "аргументы": args,
                    "старт": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "порог входа, ГиБ": MIN_FREE_GIB, "аварийный порог, ГиБ": abort_gib}
    free = psutil.virtual_memory().available / 2**30
    record["свободно перед стартом, ГиБ"] = round(free, 3)
    if free < MIN_FREE_GIB:
        record["исход"] = "НЕ ЗАПУЩЕН: свободной памяти меньше порога входа"
        with log_path.open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps(record, ensure_ascii=False))
        return 3
    env = dict(os.environ, PYTHONHASHSEED="0")
    started = time.perf_counter()
    child = subprocess.Popen(
        [sys.executable, "-B", "-X", "utf8", str(HERE / script), *args],
        cwd=str(HERE), env=env,
    )
    watched = psutil.Process(child.pid)
    min_free, rss_max, aborted, tree = free, 0.0, False, [watched]
    while child.poll() is None:
        # Интерпретатор venv на Windows — перенаправитель: считает его
        # потомок, поэтому рабочий набор берётся по всему дереву процессов.
        try:
            tree = [watched] + watched.children(recursive=True)
            rss_max = max(rss_max, sum(p.memory_info().rss for p in tree) / 2**30)
        except psutil.Error:
            tree = [watched]
        now_free = psutil.virtual_memory().available / 2**30
        min_free = min(min_free, now_free)
        if now_free < abort_gib:
            aborted = True
            for p in reversed(tree):
                try:
                    p.kill()
                except psutil.Error:
                    pass
            break
        time.sleep(0.25)
    code = child.wait()
    record.update({
        "код выхода": code,
        "стена, с": round(time.perf_counter() - started, 1),
        "минимум свободной по ходу, ГиБ": round(min_free, 3),
        "рабочий набор потомка, максимум опроса, ГиБ": round(rss_max, 4),
        "исход": "СНЯТ ПО АВАРИЙНОМУ ПОРОГУ" if aborted else ("завершён" if code == 0 else "ошибка потомка"),
    })
    with log_path.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(record, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
