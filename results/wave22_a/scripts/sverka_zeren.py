#!/usr/bin/env python3
"""22-А, шаг 1: сверка прогонов с разным PYTHONHASHSEED по сохранённым NPZ.

* побитовое совпадение повторов с одним зерном и прогона с трассой без неё;
* шаг, на котором траектории разных зёрен впервые расходятся больше rtol
  (по времени, составу матрицы, доле и числу частиц).

    python -B sverka_zeren.py > ../logs/shag1_sverka_zeren.txt
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"


def load(tag: str) -> dict[str, np.ndarray]:
    with np.load(DATA / f"{tag}.npz") as archive:
        return {name: archive[name] for name in archive.files}


def same(a: dict[str, np.ndarray], b: dict[str, np.ndarray]) -> bool:
    return a.keys() == b.keys() and all(
        a[k].shape == b[k].shape and np.array_equal(a[k], b[k], equal_nan=True) for k in a
    )


def diverge(x: dict[str, np.ndarray], y: dict[str, np.ndarray], rtol: float) -> tuple[int | None, str | None]:
    n = min(len(x["time"]), len(y["time"]))
    for i in range(n):
        for key in ("time", "composition", "volFrac", "precipitateDensity"):
            if not np.allclose(x[key][i], y[key][i], rtol=rtol, atol=0):
                return i, key
    return None, None


def main() -> None:
    print("Побитовое совпадение NPZ:")
    for left, right in (
        ("shag1_app_seed0_a", "shag1_app_seed0_b"),
        ("shag1_app_seed0_a", "shag1_app_seed0_trace"),
        ("shag1_backend_seed0_a", "shag1_backend_seed0_b"),
        ("shag2_app_trace", "shag1_app_seed2"),
    ):
        print(f"  {left} == {right}: {same(load(left), load(right))}")
    groups = {
        "app": ["shag1_app", "shag1_app_seed0_a", "shag1_app_seed1", "shag1_app_seed2"],
        "backend": ["shag1_backend", "shag1_backend_seed0_a", "shag1_backend_seed1"],
    }
    for name, runs in groups.items():
        data = {run: load(run) for run in runs}
        print(f"\nЯчейка {name}: шагов и конец")
        for run, d in data.items():
            print(f"  {run:24s} шагов {len(d['time']):5d}  t_конец {d['time'][-1]:.10g} с  "
                  f"x_C конец {d['composition'][-1, 0]:.6g}  доля {d['volFrac'][-1, 0]:.6g}")
        print(f"Ячейка {name}: первое расхождение траекторий")
        for i, left in enumerate(runs):
            for right in runs[i + 1:]:
                parts = []
                for rtol in (1e-12, 1e-9, 1e-6, 1e-3):
                    step, key = diverge(data[left], data[right], rtol)
                    when = f"{data[left]['time'][step]:.6g} с" if step is not None else "—"
                    parts.append(f"rtol {rtol:g}: шаг {step} ({key}, {when})")
                print(f"  {left} / {right}: " + "; ".join(parts))


if __name__ == "__main__":
    main()
