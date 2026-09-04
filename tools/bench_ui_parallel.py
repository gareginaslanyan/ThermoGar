#!/usr/bin/env python3
"""Замер разделов интерфейса до и после интеграции параллельного движка.

Один и тот же скрипт запускается в двух деревьях: в состоянии до волны 6
(«0.3.0») и в текущем («0.3.1»). Он гоняет ``streamlit.testing.v1.AppTest``,
то есть настоящий код приложения со всеми его проверками, и меряет время
нажатия на кнопку расчёта — ровно то, что ждёт пользователь.

Сценарии на каждой базе:

* ``tscan20`` — скан по температуре, 20 точек;
* ``map21``   — карта доли фазы, шаг сетки 20 % (21 узел треугольной сетки);
* ``batch10`` — пакетный расчёт из 10 составов.

Запуск:

    .venv-windows\\Scripts\\python.exe -X utf8 tools/bench_ui_parallel.py \\
        --label 0.3.1 --out dist/bench-0.3.1.json

``--only`` сужает набор (``ni:tscan20,fe:batch10``), ``--parallel off``
выключает пул через тот же переключатель, что и в сайдбаре, ``--repeat 2``
нажимает кнопку дважды в одной сессии: первый раз пул поднимается («холодный»),
второй раз он уже готов («тёплый») — так себя ведёт второй расчёт у
пользователя.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

APP_PATH = ROOT / "app" / "ThermoGar_app.py"

# Составы релизной матрицы (tools/backend_reference.md).
BASES = {
    "ni": {
        "composition": "AL=15",
        "units": "атомные %",
        "unit_token": "ат.%",
        "balance": "NI",
        "scan": (600.0, 980.0, 20.0),
        "batch_start_c": 700.0,
    },
    "al": {
        "composition": "CU=4, MG=1",
        "units": "массовые %",
        "unit_token": "мас.%",
        "balance": "AL",
        "scan": (300.0, 680.0, 20.0),
        "batch_start_c": 500.0,
    },
    "fe": {
        "composition": "C=0.2, CR=11.5, NI=0.7",
        "units": "массовые %",
        "unit_token": "мас.%",
        "balance": "FE",
        "scan": (500.0, 880.0, 20.0),
        "batch_start_c": 700.0,
    },
}

SCENARIOS = ("tscan20", "map21", "batch10")


def batch_csv(database_key: str, rows: int) -> bytes:
    """Десять составов одной базы с разной температурой."""
    profile = BASES[database_key]
    header = "Название,База,Основа,Единицы,\"Температура, °C\",Добавки"
    lines = [header]
    for index in range(rows):
        temperature = profile["batch_start_c"] + 10.0 * index
        lines.append(
            ",".join(
                [
                    f"{database_key.upper()}-{index + 1}",
                    database_key,
                    profile["balance"],
                    profile["unit_token"],
                    f"{temperature:g}",
                    '"' + profile["composition"] + '"',
                ]
            )
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def make_app(database_key: str, session: dict[str, object]):
    from streamlit.testing.v1 import AppTest

    profile = BASES[database_key]
    app_test = AppTest.from_file(str(APP_PATH), default_timeout=3600)
    app_test.session_state["thermogar_database_key"] = database_key
    app_test.session_state[f"thermogar_composition_{database_key}"] = profile[
        "composition"
    ]
    app_test.session_state[f"thermogar_units_{database_key}"] = profile["units"]
    app_test.session_state[f"thermogar_balance_{database_key}"] = profile["balance"]
    for name, value in session.items():
        app_test.session_state[name] = value
    app_test.run()
    return app_test


def click(app_test, key: str, repeat: int = 1) -> list[float]:
    """Нажать кнопку ``repeat`` раз подряд и вернуть время каждого нажатия."""
    timings: list[float] = []
    for _attempt in range(max(1, int(repeat))):
        target = None
        for button in app_test.button:
            if button.key == key:
                target = button
                break
        if target is None:
            raise AssertionError(f"кнопка {key!r} не найдена")
        started = time.perf_counter()
        target.click().run()
        timings.append(time.perf_counter() - started)
    return timings


def timings_report(timings: list[float], points: int, app_test) -> dict[str, object]:
    report: dict[str, object] = {
        "seconds": round(timings[0], 1),
        "points": points,
        "errors": errors(app_test),
    }
    if len(timings) > 1:
        report["warm_seconds"] = round(timings[-1], 1)
    return report


def errors(app_test) -> list[str]:
    return [str(item.value) for item in app_test.exception] + [
        str(item.value) for item in app_test.error
    ]


def run_tscan(database_key: str, parallel: str, repeat: int = 1) -> dict[str, object]:
    profile = BASES[database_key]
    t_min, t_max, t_step = profile["scan"]
    session = {
        f"t_min_{database_key}": t_min,
        f"t_max_{database_key}": t_max,
        f"t_step_{database_key}": t_step,
    }
    if parallel:
        session["thermogar_parallel_mode"] = parallel
    app_test = make_app(database_key, session)
    timings = click(app_test, "temperature_calculate", repeat)
    key = "_thermogar_vlb_b3_result_equilibrium_temperature_scan"
    points = 0
    if key in app_test.session_state:
        points = int(len(app_test.session_state[key]["display"]["data"]))
    return timings_report(timings, points, app_test)


def run_map(database_key: str, parallel: str, repeat: int = 1) -> dict[str, object]:
    session = {f"ternary_map_step_{database_key}": 20.0}
    if parallel:
        session["thermogar_parallel_mode"] = parallel
    app_test = make_app(database_key, session)
    timings = click(app_test, "ternary_map_calculate", repeat)
    key = f"ternary_map_result_{database_key}"
    points = 0
    if key in app_test.session_state:
        points = int(len(app_test.session_state[key]["data"]))
    return timings_report(timings, points, app_test)


def run_batch(database_key: str, parallel: str, repeat: int = 1) -> dict[str, object]:
    session = {}
    if parallel:
        session["thermogar_parallel_mode"] = parallel
    app_test = make_app(database_key, session)
    uploaded = None
    for widget in app_test.file_uploader:
        if "Файл составов" in str(widget.label):
            uploaded = widget
            break
    if uploaded is None:
        raise AssertionError("загрузчик «Файл составов» не найден")
    uploaded.set_value(("bench.csv", batch_csv(database_key, 10), "text/csv"))
    app_test.run()
    timings = click(app_test, "batch_calculate_button", repeat)
    done = 0
    if "workspace_batch_result" in app_test.session_state:
        summary = app_test.session_state["workspace_batch_result"]["display"]["Сводка"]
        done = int((summary["Статус"] == "готово").sum())
    return timings_report(timings, done, app_test)


RUNNERS = {"tscan20": run_tscan, "map21": run_map, "batch10": run_batch}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--only", default="")
    parser.add_argument("--parallel", default="", choices=["", "auto", "off"])
    parser.add_argument("--repeat", type=int, default=1)
    arguments = parser.parse_args()

    wanted: list[tuple[str, str]] = []
    if arguments.only:
        for item in arguments.only.split(","):
            database_key, scenario = item.strip().split(":")
            wanted.append((database_key, scenario))
    else:
        wanted = [(key, scenario) for key in BASES for scenario in SCENARIOS]

    os.environ.setdefault("THERMOGAR_STATE_ROOT", tempfile.mkdtemp(prefix="tg-bench-"))
    output = Path(arguments.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "label": arguments.label,
        "root": str(ROOT),
        "parallel": arguments.parallel or "default",
        "repeat": int(arguments.repeat),
        "cases": {},
    }
    for database_key, scenario in wanted:
        name = f"{database_key}:{scenario}"
        print(f"[bench] {name} …", flush=True)
        try:
            result = RUNNERS[scenario](
                database_key, arguments.parallel, arguments.repeat
            )
        except Exception as error:  # один сценарий не должен ронять прогон
            result = {"seconds": None, "points": 0, "errors": [f"{type(error).__name__}: {error}"]}
        report["cases"][name] = result
        print(f"[bench] {name}: {result}", flush=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    raise SystemExit(main())
