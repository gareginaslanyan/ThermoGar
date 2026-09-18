"""Перестроить графики «размер и число выделений» без счёта (15-Н2, BL-37).

Нижняя панель `plot_k1_size` («число выделений») теперь начинается с
`DENSITY_FLOOR` = 1e10 1/м³; точки ниже не рисуются, подпись оси говорит об
этом. Перестраиваются все четыре png, которые строит `plot_k1_size`, из csv
своих прогонов. Ключи `configure` — те же, что у прогонов:

    12-1   --temperatures 700 750 --prefix k1  --subpoint 12-1
    12-9   --temperatures 580     --prefix k9  --subpoint 12-9
    12-9б  --temperatures 664     --prefix k9b --subpoint 12-9б
    13-Б   --temperatures 595     --prefix b1  --subpoint 13-Б1 --out-dir results/hn62m_wave13

Образец — `results/wave15_m/rebuild_bl30.py`. Перед рисованием сценарий
проверяет, что в csv есть все столбцы, которые читает функция, и печатает,
сколько точек нижней панели лежит ниже порога.

Запуск из корня дерева:
    <python> -X utf8 -B results/wave15_n/rebuild_bl37.py [--check]
С `--check` только проверяются столбцы, ничего не рисуется.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import pandas as pd

import study_hn62m_wave12_kinetics as kin

RUNS = (
    ("k1", [700.0, 750.0], "12-1", "results/hn62m_wave12"),
    ("k9", [580.0], "12-9", "results/hn62m_wave12"),
    ("k9b", [664.0], "12-9б", "results/hn62m_wave12"),
    ("b1", [595.0], "13-Б1", "results/hn62m_wave13"),
)

DENSITY = "число выделений, 1/м³"
COLUMNS = ["T, °C", "места зарождения", "межфазная энергия, Дж/м²", "t, ч",
           "средний радиус, нм", DENSITY]


def main() -> int:
    check_only = "--check" in sys.argv[1:]
    for prefix, temperatures, subpoint, out_dir in RUNS:
        kin.configure(temperatures=temperatures, prefix=prefix,
                      subpoint=subpoint, out_dir=out_dir)
        csv_path = kin.OUT / f"{prefix}_size_and_density.csv"
        rows = pd.read_csv(csv_path, **kin.CSV_READ)
        missing = [column for column in COLUMNS if column not in rows]
        png = kin.OUT / f"{prefix}_size_and_density.png"
        if missing:
            below = zero = "—"
        else:
            density = rows[DENSITY]
            zero = int((density == 0.0).sum())
            below = int(((density > 0.0) & (density < kin.DENSITY_FLOOR)).sum())
        print(f"{png.relative_to(ROOT).as_posix()} | {csv_path.name}: "
              f"{len(rows)} строк | нет столбцов: {missing or '—'} | "
              f"ноль: {zero} | 0 < N < {kin.DENSITY_FLOOR:.0e}: {below}")
        if missing or check_only:
            continue
        kin.plot_k1_size(rows, png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
