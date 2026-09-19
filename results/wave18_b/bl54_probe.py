"""Проба BL-54: исполняет ли воркер пула сценарий приложения при spawn.

Повторяет то, что делает streamlit перед исполнением сценария
(streamlit/runtime/scriptrunner/script_runner.py:690-704): подменяет
sys.modules["__main__"] пустым модулем с __file__ = путь сценария и кладёт
папку сценария в sys.path (modified_sys_path). Затем
поднимает ProcessPoolExecutor на spawn, как thermogar_parallel.py:688-691, и
спрашивает воркер, что в нём исполнилось.

    <python> -B -X utf8 bl54_probe.py --script <путь .py> [--workers N]

Для сценария приложения задавать THERMOGAR_STATE_ROOT на временную папку.
"""

import argparse
import concurrent.futures
import json
import multiprocessing
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bl54_probe_worker  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    fake_main = types.ModuleType("__main__")
    fake_main.__dict__["__file__"] = str(Path(args.script).resolve())
    sys.modules["__main__"] = fake_main
    # modified_sys_path(main_script_path) streamlit: папка сценария в sys.path
    # на время исполнения; пул поднимается изнутри сценария и её наследует.
    sys.path.insert(0, str(Path(args.script).resolve().parent))

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=args.workers, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        try:
            results = list(pool.map(bl54_probe_worker.report, range(args.workers)))
        except Exception as error:  # воркер умер при исполнении сценария
            results = [{"error": f"{type(error).__name__}: {error}"}]
    print(json.dumps({"python": sys.executable, "script": args.script, "results": results},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
