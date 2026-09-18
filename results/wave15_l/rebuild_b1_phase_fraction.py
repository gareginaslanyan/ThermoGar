"""Перестроить results/hn62m_wave13/b1_phase_fraction.png без счёта (15-Л, BL-30).

График рисует та же функция `plot_k1` модуля волны 12. Её входы берутся с
диска: строки — из `b1_phase_fraction_vs_time.csv` прогона 13-Б3 (в нём все
столбцы, которые читает `plot_k1`), равновесная цель — `wave12_2_targets()`
из результатов 12-2. Настройка подпункта — те же ключи, что у прогона 13-Б:
`--temperatures 595 --prefix b1 --subpoint 13-Б1 --out-dir results/hn62m_wave13`.

Запуск из корня дерева:
    <python> -X utf8 -B results/wave15_l/rebuild_b1_phase_fraction.py [путь.png]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import pandas as pd

import study_hn62m_wave12_kinetics as kin

kin.configure(temperatures=[595.0], prefix="b1", subpoint="13-Б1",
              out_dir="results/hn62m_wave13")
rows = pd.read_csv(kin.OUT / "b1_phase_fraction_vs_time.csv", **kin.CSV_READ)
target = Path(sys.argv[1]) if len(sys.argv) > 1 else kin.OUT / "b1_phase_fraction.png"
kin.plot_k1(rows, kin.wave12_2_targets(), target.resolve())
