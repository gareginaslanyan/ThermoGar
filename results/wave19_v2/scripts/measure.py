"""Замер справочника фаз 19-В2 (BL-58, часть 2).

Путь тот же, что в 19-А (``results/wave19_a/scripts/measure.py``, шаг 1в):
``phase_reference_dataframe`` и ``load_database`` приложения через загрузчик
``results/wave19_a/scripts/app_extract.py``.

Запуск (из корня дерева):
    MPLBACKEND=Agg PYTHONHASHSEED=0 THERMOGAR_STATE_ROOT=results\validation\wave19_v2_state \
    .venv-windows/Scripts/python.exe -B -X utf8 results/wave19_v2/scripts/measure.py <do|posle>
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "results" / "wave19_a" / "scripts"))
sys.path.insert(0, str(ROOT / "app"))

import app_extract  # noqa: E402


def main(stage: str) -> None:
    out = HERE.parent / stage
    out.mkdir(parents=True, exist_ok=True)
    app, _taken = app_extract.load(("phase_reference_dataframe", "load_database"))
    lines = []
    for key in ("ni", "al", "fe"):
        db, path = app["load_database"](key)
        frame = app["phase_reference_dataframe"](db, path, key)
        data = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
        name = f"phase_reference_{key}.csv"
        (out / name).write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        lines.append(f"{digest}  {name}\n")
        print(key, len(frame), digest)
    (out / "sha256.txt").write_text("".join(lines), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main(sys.argv[1])
