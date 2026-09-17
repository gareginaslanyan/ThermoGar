"""15-Ш, п. 3б: фазы базы fe с углеродом и без собственной модели плотности."""
import sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "app"))
from pycalphad import Database
import thermogar_physical as physical
db = Database(str(root / "databases/converted/fe/mc_fe_v2062.thermogar.tdb"))
pdb = physical.PhysicalDensityDatabase(root / "databases/physical/original/physical_data_v103.pdb", overrides=None)
for name in sorted(db.phases):
    r = pdb.resolve_phase(db, name)
    consts = [sorted(str(s.name) for s in sub) for sub in db.phases[name].constituents]
    has_c = any("C" in sub for sub in consts)
    if r.quality == "missing":
        print(name, "C" if has_c else "-", consts)
