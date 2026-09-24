"""21-B: fresh state root with the same elastic library example as the guide."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import make_guide_screens as mgs  # noqa: E402

STATE_ROOT = Path(os.environ["TEMP"]) / "tg21b_state"

if STATE_ROOT.exists():
    raise SystemExit(f"{STATE_ROOT} already exists; not touching it.")
(STATE_ROOT / "properties").mkdir(parents=True)
payload = json.dumps(
    mgs.elastic_library_payload(),
    ensure_ascii=False,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
(STATE_ROOT / "properties" / "elastic_phase_properties.json").write_bytes(payload)
print(STATE_ROOT)
