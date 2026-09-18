"""Входы демонстрации 17-Д п. 6: study_wave15_v_718.case_arguments(700, 95, GRID) в JSON."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "app", ROOT / "tools"):
    sys.path.insert(0, str(entry))
import study_wave15_v_718 as study
args = study.case_arguments(700.0, 95.0, study.GRID)
database_rel = Path(args.pop("database_path")).relative_to(ROOT).as_posix()
for key in ("db", "database_label"):
    args.pop(key)
out = {"source": "study_wave15_v_718.case_arguments(700.0, 95.0, GRID)", "database_rel": database_rel, "arguments": args}
Path(__file__).with_name("demo_718_inputs.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float), "utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1, default=float))
