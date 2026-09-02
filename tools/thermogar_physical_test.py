#!/usr/bin/env python3
"""SWR software regression for physical_data.pdb parsing and equations."""
from __future__ import annotations
from pathlib import Path
import sys


def find_root() -> Path:
    candidates = [Path.cwd(), Path(__file__).resolve().parent.parent]
    for candidate in candidates:
        if (candidate / "app").exists() and (candidate / "databases").exists():
            return candidate.resolve()
    raise FileNotFoundError("Не найден корень ThermoGar.")


def main() -> int:
    root = find_root()
    sys.path.insert(0, str(root / "app"))
    from thermogar_physical import PhysicalDensityDatabase

    path = root / "databases/physical/original/physical_data_v103.pdb"
    db = PhysicalDensityDatabase(path)
    checks = db.self_test()
    print("THERMOGAR SWR — PHYSICAL DATABASE SOFTWARE REGRESSION")
    print("File:", path)
    print("SHA-256:", db.sha256)
    print("Functions:", len(db.functions))
    print("DP parameters:", len(db.parameters))
    print("Direct phase models:", ", ".join(db.direct_phase_models))
    print()
    print(checks.to_string(index=False))
    passed = bool((checks["Статус"] == "пройдена").all())
    print()
    print("RESULT:", "PASSED" if passed else "FAILED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
