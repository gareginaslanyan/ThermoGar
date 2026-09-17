"""Перестроить графики 13-Б, 12-9 и 12-9б без счёта (15-М2, BL-30).

Графики рисуют те же функции модуля волны 12: `plot_k1`, `plot_k1_size` и
`plot_k1_depletion`. Их входы берутся с диска: строки — из csv того же прогона
(`<префикс>_phase_fraction_vs_time.csv`, `<префикс>_size_and_density.csv`,
`<префикс>_matrix_depletion.csv`), равновесная цель — `wave12_2_targets()` из
результатов 12-2. Настройка подпункта — те же ключи, что у прогона:

    12-9   --temperatures 580 --prefix k9  --subpoint 12-9
    12-9б  --temperatures 664 --prefix k9b --subpoint 12-9б
    13-Б   --temperatures 595 --prefix b1  --subpoint 13-Б1 --out-dir results/hn62m_wave13

Перед рисованием сценарий проверяет, что в csv есть все столбцы, которые
читает функция. Если какого-то нет, график не рисуется, и это печатается.

`b1_phase_fraction.png` перестроил 15-Л (`results/wave15_l/`), здесь его нет.

Запуск из корня дерева:
    <python> -X utf8 -B results/wave15_m/rebuild_bl30.py [--check]
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
    ("k9", [580.0], "12-9", "results/hn62m_wave12"),
    ("k9b", [664.0], "12-9б", "results/hn62m_wave12"),
    ("b1", [595.0], "13-Б1", "results/hn62m_wave13"),
)

# Столбцы строк, которые читает каждая функция.
KEYS = ["T, °C", "места зарождения", "межфазная энергия, Дж/м²", "t, ч"]
PLOTS = {
    "phase_fraction": ("plot_k1", "phase_fraction_vs_time.csv",
                       KEYS + ["мольная доля P-фазы, %"]),
    "size_and_density": ("plot_k1_size", "size_and_density.csv",
                         KEYS + ["средний радиус, нм", "число выделений, 1/м³"]),
    "matrix_depletion": ("plot_k1_depletion", "matrix_depletion.csv",
                         KEYS + [f"{element} в матрице, масс. %"
                                 for element in kin.MATRIX_ELEMENTS]),
}

# Что перестраивается у каждого прогона.
WANTED = {
    "k9": ("phase_fraction", "size_and_density", "matrix_depletion"),
    "k9b": ("phase_fraction", "size_and_density", "matrix_depletion"),
    "b1": ("size_and_density", "matrix_depletion"),
}


def main() -> int:
    check_only = "--check" in sys.argv[1:]
    for prefix, temperatures, subpoint, out_dir in RUNS:
        kin.configure(temperatures=temperatures, prefix=prefix,
                      subpoint=subpoint, out_dir=out_dir)
        targets = kin.wave12_2_targets()
        for name in WANTED[prefix]:
            function, csv_name, columns = PLOTS[name]
            csv_path = kin.OUT / f"{prefix}_{csv_name}"
            rows = pd.read_csv(csv_path, **kin.CSV_READ)
            missing = [column for column in columns if column not in rows]
            png = kin.OUT / f"{prefix}_{name}.png"
            print(f"{png.relative_to(ROOT).as_posix()} | {function} | "
                  f"{csv_path.name}: {len(rows)} строк | "
                  f"нет столбцов: {missing or '—'} | "
                  f"пустых значений: {int(rows[columns].isna().sum().sum()) if not missing else '—'} | "
                  f"цель 12-2: {targets['доля P-фазы, мольн. %']} "
                  f"{targets['матрица FCC_A1, масс. %']}")
            if missing or check_only:
                continue
            if name == "phase_fraction":
                kin.plot_k1(rows, targets, png)
            elif name == "size_and_density":
                kin.plot_k1_size(rows, png)
            else:
                kin.plot_k1_depletion(rows, targets, png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
