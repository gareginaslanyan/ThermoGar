#!/usr/bin/env python3
"""22-А2: «пинки» — скачки доли больше 0,1 % (абс.) за один принятый шаг, по NPZ.

Вниз — растворение за шаг после перелёта, закончившегося отрицательной
движущей силой; вверх — ложное зарождение (им кончается остановка BL-35).

    python -B pinki.py > ../logs/a2_s2_pinki.txt
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"


def main() -> None:
    print("тег; остановка; конец, с; пинков вниз; пинков вверх; моменты пинков вниз, с")
    for path in sorted(DATA.glob("*.npz")):
        summary_path = DATA / f"{path.stem}.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        with np.load(path) as archive:
            t = archive["time"]
            fv = np.sum(archive["volFrac"], axis=1)
        dfv = np.diff(fv)
        down = np.where(dfv < -1e-3)[0]
        up = np.where(dfv > 1e-3)[0]
        # Вверх в начале зарождения (доля растёт быстро, но без перелёта) не считаем:
        # только после выхода на плато (доля > 4 %).
        up = [i for i in up if fv[i] > 0.04]
        moments = ", ".join(f"{t[i + 1]:.3f}" for i in down[:12]) + (" …" if len(down) > 12 else "")
        print(f"{path.stem}; {'да' if summary.get('stop') else 'нет'}; {t[-1]:.4g}; {len(down)}; {len(up)}; {moments}")


if __name__ == "__main__":
    main()
