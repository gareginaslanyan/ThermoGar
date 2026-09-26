"""21-О, ШАГ 3в: T₀ стали по умолчанию на ноутбуке — окна 200–950 и 300–1700 °C.

Запуск из корня w21b (PYTHONHASHSEED=0, MPLBACKEND=Agg, THERMOGAR_STATE_ROOT —
временная папка):
    python -B results/wave21_o/scripts/tzero_sverka.py
Выход: results/wave21_o/data/tzero_fe_<окно>.csv и строки итога в stdout.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "app"
OUT = ROOT / "results" / "wave21_o" / "data"
OUT.mkdir(parents=True, exist_ok=True)


def run(window: tuple[float, float] | None) -> None:
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(APP / "ThermoGar_app.py"), default_timeout=900)
    app.session_state["thermogar_database_key"] = "fe"
    app.run()
    if window is not None:
        app.session_state["tzero_t_min_fe"] = window[0]
        app.session_state["tzero_t_max_fe"] = window[1]
        app.run()
    values = {item.key: item.value for item in app.number_input if item.key}
    t_min, t_max = values["tzero_t_min_fe"], values["tzero_t_max_fe"]
    started = time.perf_counter()
    app.button(key="tzero_calculate").click().run()
    seconds = time.perf_counter() - started
    assert not app.exception, [element.message for element in app.exception]
    data = app.session_state["tzero_result"]["data"]
    name = f"{int(t_min)}_{int(t_max)}"
    data.to_csv(OUT / f"tzero_fe_{name}.csv", sep=";", index=False, encoding="utf-8-sig")
    counters = [w.value for w in app.warning] + [s.value for s in app.success]
    found = data[data["Решение найдено"]]
    print(f"== окно {t_min}–{t_max} °C, {seconds:.1f} с: строк {len(data)}, найдено {len(found)}")
    print("   счётчик:", [c for c in counters if "T₀ найдено" in c])
    print("   состав пуст:", int(data.iloc[:, 0].isna().sum()), "; состав:", data.iloc[:, 0].tolist())
    for index, row in data.iterrows():
        print(f"   {index:2d}  {row.iloc[0]:6.3f}  {row['T₀, °C']:9.2f}  {bool(row['Решение найдено'])}")


if __name__ == "__main__":
    sys.path.insert(0, str(APP))
    run(None)
    run((300.0, 1700.0))
