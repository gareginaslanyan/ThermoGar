"""Демонстрация «до/после» выпуска 0.4.2 (17-Д, п. 6): сплав 718, шесть добавок.

Запуск интерпретатором проверяемой копии:
    <python.exe> -B -X utf8 demo_718.py <корень копии: там app\\ и databases\\> <каталог вывода>

Расчёт идёт штатным путём приложения — ``thermogar_precipitation.run_precipitation``
из каталога ``app`` проверяемой копии, с её базой ``mc_ni``. Входы — случай 15-В
(700 °C, 95 мДж/м², сетка ``study_wave15_v_718.GRID``), записанные в
``demo_718_inputs.json`` рядом со скриптом функцией ``study_wave15_v_718.case_arguments``
дерева 0.4.2: у 0.4.1 этого модуля нет, поэтому числа берутся из файла, а не
считаются заново, и обе копии получают одни и те же входы.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
out.mkdir(parents=True, exist_ok=True)
os.environ["THERMOGAR_STATE_ROOT"] = str(out / "state")
sys.path.insert(0, str(root / "app"))

import thermogar_precipitation as tp  # noqa: E402
from thermogar_release_policy import APP_VERSION, RELEASE_DATABASE_LABELS  # noqa: E402

inputs = json.loads((Path(__file__).resolve().parent / "demo_718_inputs.json").read_text("utf-8"))
arguments = dict(inputs["arguments"])
arguments["db"] = object()
arguments["database_path"] = root / inputs["database_rel"]
arguments["database_label"] = RELEASE_DATABASE_LABELS["ni"]

print(f"python      : {sys.executable}")
print(f"app         : {Path(tp.__file__).resolve()}")
print(f"APP_VERSION : {APP_VERSION}")
print(f"состав      : основа {arguments['balance']}, {arguments['composition_text']} ({arguments['units']})")
print(f"пара        : {arguments['matrix_phase']} / {arguments['precipitate_phase']}, "
      f"{arguments['temperature_c']:g} °C, γ = {arguments['gamma']:g} Дж/м²")
started = time.perf_counter()
try:
    result = tp.run_precipitation(**arguments)
except Exception as error:  # noqa: BLE001 — исход отказа и есть предмет проверки
    print(f"ИСХОД       : ОТКАЗ за {time.perf_counter() - started:.1f} с")
    print(f"исключение  : {type(error).__name__}: {error}")
    traceback.print_exc(file=open(out / "traceback.txt", "w", encoding="utf-8"))
    raise SystemExit(0)

seconds = time.perf_counter() - started
kinetics = result.kinetics
row = result.quality[result.quality["Проверка"] == "Состав матрицы допустим"].iloc[0]
print(f"ИСХОД       : РЕЗУЛЬТАТ за {seconds:.1f} с")
print(f"строк кинетики: {len(kinetics)}; последнее время: {kinetics['Время, с'].iloc[-1]:.6g} с")
print(f"«Состав матрицы допустим»: {row['Статус']}")
print(f"stop_note   : {getattr(result, 'stop_note', '')}")
for warning in result.warnings or ():
    print(f"warning     : {warning}")
kinetics.to_csv(out / "kinetics.csv", index=False, encoding="utf-8")
result.quality.to_csv(out / "quality.csv", index=False, encoding="utf-8")
