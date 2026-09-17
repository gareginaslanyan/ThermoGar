"""Предполётный сбор 17-Г: состав регрессии.

Для каждого файла tools/test_*.py и tools/thermogar_*_test.py выполняется
``pytest --collect-only -q -m slow``. Строка «N/M tests collected» даёт сразу
два числа: N — медленных кейсов, M — всего кейсов в файле. Файлы без
pytest-кейсов дают exit 5 — это сценарные скрипты.

    python -B -X utf8 results/wave17_g/collect_preflight.py
"""
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
PY = str(ROOT / ".venv-windows/Scripts/python.exe")

FILES = sorted(p.name for p in (ROOT / "tools").glob("test_*.py")) + sorted(
    p.name for p in (ROOT / "tools").glob("thermogar_*_test.py"))

records = []
for name in FILES:
    cmd = [PY, "-B", "-X", "utf8", "-m", "pytest", f"tools/{name}",
           "--collect-only", "-q", "-m", "slow", "-p", "no:cacheprovider"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    text = (proc.stdout or "") + (proc.stderr or "")
    (OUT / "collect" / f"{name}.collect.txt").write_text(text, encoding="utf-8")
    last = next((ln for ln in reversed(text.strip().splitlines()) if ln.strip()), "")
    rec = {"file": name, "exit": proc.returncode, "last_line": last}
    records.append(rec)
    print(json.dumps(rec, ensure_ascii=False), flush=True)

(OUT / "collect_preflight.jsonl").write_text(
    "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
