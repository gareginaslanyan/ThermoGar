"""21-L: move what is not needed into _to_delete\21l_<what>\ with a sha256 inventory
(opis_sha256.txt: sha256, bytes, source path). Nothing is deleted."""

import hashlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(r"D:\Pets\ThermoGar-w21b")


def move(sources: list[Path], target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    lines = []
    for source in sources:
        files = [source] if source.is_file() else sorted(p for p in source.rglob("*") if p.is_file())
        for f in files:
            digest = hashlib.sha256(f.read_bytes()).hexdigest()
            lines.append(f"{digest}  {f.stat().st_size}  {f}")
    with open(target / "opis_sha256.txt", "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    for source in sources:
        destination = target / source.name
        if destination.exists():
            raise SystemExit(f"STOP: {destination} exists")
        shutil.move(str(source), str(destination))
    print(target, len(lines), "files")


temp = Path(os.environ["TEMP"])
what = sys.argv[1]
if what == "state":
    move([temp / "tg21l_state", temp / "tg21l_tests_state"], ROOT / "_to_delete" / "21l_state")
elif what == "logi":
    move(sorted((ROOT / "results/wave21_l/10b/logi").glob("*_app.log")), ROOT / "_to_delete" / "21l_logi")
elif what == "proby":
    ten = ROOT / "results/wave21_l/10b"
    move(sorted(ten.glob("*sboy*.png")) + sorted((ten / "runs").glob("*_povtor.json"))
         + sorted((ten / "runs").glob("*_povtor2.json")), ROOT / "_to_delete" / "21l_proby")
