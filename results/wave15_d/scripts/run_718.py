"""15-Д, пункт 5: шесть случаев 718 штатным run_precipitation, без обёрток.

Запуск родителя: python run_718.py
Потомок:        python run_718.py --child <T_C> <gamma_mJ>

Родитель гоняет случаи по одному, перед каждым ждёт свободной физической
памяти не меньше 2,0 ГиБ (Win32_OperatingSystem.FreePhysicalMemory).
Потомок не ловит ничего: любое исключение уходит в лог как traceback и
в сводку как «traceback».
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "results" / "wave15_d" / "runs"
MIN_FREE_GIB = 2.0
CASES = [(750.0, 95.0), (750.0, 78.0), (750.0, 112.0), (700.0, 95.0), (700.0, 78.0), (700.0, 112.0)]


def free_gib() -> float:
    text = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return int(text) / 1024.0**2


def child(temperature_c: float, gamma_mj: float) -> None:
    import psutil

    sys.path.insert(0, str(ROOT / "tools"))
    sys.path.insert(0, str(ROOT / "app"))
    import study_wave15_v_718 as study
    import thermogar_precipitation as precipitation

    peak = {"rss": 0}
    done = threading.Event()

    def watch() -> None:
        proc = psutil.Process()
        while not done.is_set():
            peak["rss"] = max(peak["rss"], proc.memory_info().rss)
            time.sleep(0.5)

    threading.Thread(target=watch, daemon=True).start()
    case = study.case_id(temperature_c, gamma_mj)
    folder = OUT / case
    folder.mkdir(parents=True, exist_ok=True)
    record: dict = {"случай": case, "T, °C": temperature_c, "γ, мДж/м²": gamma_mj}
    started = time.perf_counter()
    try:
        result = precipitation.run_precipitation(
            **study.case_arguments(temperature_c, gamma_mj, study.GRID)
        )
    except BaseException as error:  # noqa: BLE001 — факт исключения и есть результат
        record["исход"] = "traceback"
        record["исключение"] = f"{type(error).__name__}: {error}"
        record["traceback"] = traceback.format_exc()
    else:
        write = dict(index=False, encoding="utf-8")
        result.kinetics.to_csv(folder / "kinetics.csv", **write)
        result.matrix_composition.to_csv(folder / "matrix.csv", **write)
        result.quality.to_csv(folder / "quality.csv", **write)
        row = result.quality[result.quality["Проверка"] == "Состав матрицы допустим"].iloc[0]
        record["исход"] = "результат"
        record["stop_note"] = result.stop_note
        record["сработало"] = (
            "п. 2 (условие остановки)" if result.stop_note.startswith("Расчёт остановлен")
            else "п. 4 (перехват ZeroDivisionError)" if result.stop_note.startswith("Расчёт прерван")
            else "ничего"
        )
        record["строк"] = int(len(result.kinetics))
        record["последнее время, с"] = float(result.kinetics["Время, с"].iloc[-1])
        record["состав матрицы допустим"] = {"Статус": row["Статус"], "Примечание": row["Примечание"]}
        record["проверки"] = result.quality[["Проверка", "Статус"]].to_dict(orient="records")
        record["предупреждения"] = list(result.warnings)
    record["секунд"] = round(time.perf_counter() - started, 1)
    done.set()
    record["пик RSS, ГиБ"] = round(peak["rss"] / 2**30, 3)
    (folder / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps(record, ensure_ascii=False), flush=True)


def parent() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for temperature_c, gamma_mj in CASES:
        case = f"T{temperature_c:g}_g{gamma_mj:g}"
        if (OUT / case / "run.json").is_file():
            print(case, "уже посчитан", flush=True)
            continue
        waited = 0
        while (free := free_gib()) < MIN_FREE_GIB:
            print(case, f"ждём памяти: свободно {free:.2f} ГиБ", flush=True)
            time.sleep(30)
            waited += 30
        print(case, f"старт, свободно {free:.2f} ГиБ", flush=True)
        (OUT / case).mkdir(parents=True, exist_ok=True)
        with (OUT / case / "child.log.txt").open("w", encoding="utf-8") as log:
            code = subprocess.call(
                [sys.executable, "-B", "-X", "utf8", __file__, "--child", str(temperature_c), str(gamma_mj)],
                stdout=log, stderr=subprocess.STDOUT, cwd=str(ROOT),
                env=dict(os.environ, PYTHONHASHSEED="0"),
            )
        with (OUT / "memory.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"случай": case, "свободно на старте, ГиБ": round(free, 2), "exit": code}, ensure_ascii=False) + "\n")
        print(case, "exit", code, flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(float(sys.argv[2]), float(sys.argv[3]))
    else:
        parent()
