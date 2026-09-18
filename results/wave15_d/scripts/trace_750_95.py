"""15-Д, пункт 1: где именно внутри шага kawin падает pycalphad (718, 750 °C, 95 мДж/м²).

Обёртка над PrecipitateModel.solve только записывает traceback и
пробрасывает исключение дальше — в run_precipitation, как в штатном пути.
"""

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "app"))
import study_wave15_v_718 as study
import thermogar_precipitation as precipitation

OUT = ROOT / "results" / "wave15_d" / "trace_750_95.txt"
original = precipitation.PrecipitateModel.solve


def traced(self, *args, **kwargs):
    try:
        return original(self, *args, **kwargs)
    except BaseException:
        y = self._currY
        comp = ", ".join(f"{e} {x:.6g}" for e, x in zip(self.elements, y.composition[0]))
        OUT.write_text(
            traceback.format_exc()
            + "\nсостав матрицы шага, на котором упал pycalphad (не записан в data), "
            f"мольные доли: {comp}; основа {1 - float(y.composition[0].sum()):.6g}; "
            f"t = {float(y.time[0]):.6g} с; доля выделения {float(y.volFrac[0, 0]):.6g}\n",
            encoding="utf-8",
        )
        raise


precipitation.PrecipitateModel.solve = traced
result = precipitation.run_precipitation(**study.case_arguments(750.0, 95.0, study.GRID))
print(result.stop_note)
