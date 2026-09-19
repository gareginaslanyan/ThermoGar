import subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, r"D:\Pets\ThermoGar\tools")
app = sys.argv[1]
child = open(r"D:\Pets\ThermoGar\tools\thermogar_state_migration_test.py", encoding="utf-8").read()
import re
code = re.search(r'child = \(\n(.*?)\n        \)\n', child, re.S).group(1)
code = eval("(" + code + ")")
sys.path.insert(0, app)
from thermogar_state_migration_test import seed_allowlist
fails = 0
for trial in range(int(sys.argv[2])):
    with tempfile.TemporaryDirectory() as t:
        root = Path(t); install = root / "install"; install.mkdir(); seed_allowlist(install)
        go = root / "go"
        ps = [subprocess.Popen([sys.executable, "-B", "-X", "utf8", "-c", code, app, str(root / "profile"), str(install), str(go), "20"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace") for _ in range(5)]
        go.write_bytes(b"")
        outs = [p.communicate()[0] for p in ps]
        bad = [o for p, o in zip(ps, outs) if p.returncode != 0]
        fails += bool(bad)
        if bad: print("trial", trial, "failed procs", len(bad), "|", [l for l in bad[0].splitlines() if "Error" in l][-1:])
print("trials with failure:", fails, "of", sys.argv[2])
