"""Вариант: python p1_variant.py <mode> <root> <out>; mode = skip | setup_only | repeat"""
import runpy, sys
from pathlib import Path
mode, root, out = sys.argv[1:4]
sys.path.insert(0, str(Path(root).resolve() / "app"))
import thermogar_precipitation as tp
orig = tp._nucleus_estimates
if mode == "skip":
    tp._nucleus_estimates = lambda model, phase, temps: []
elif mode == "setup_only":
    def f(model, phase, temps):
        model.setup()
        return []
    tp._nucleus_estimates = f
elif mode == "df_only":
    def g(model, phase, temps):
        import numpy as np
        import kawin.precipitation.NucleationRate as nf
        p = model.phaseIndex(phase)
        par = model.precipitates[p]
        comp = np.squeeze(model.matrix.initComposition)
        for t in sorted(set(temps)):
            try:
                print("DFONLY", nf.volumetricDrivingForce(model.therm, comp, t, par, removeCache=True), flush=True)
            except Exception as e:
                print("DFONLY-ERR", type(e).__name__, e, flush=True)
        return []
    tp._nucleus_estimates = g
elif mode == "setup_df":
    def h(model, phase, temps):
        import numpy as np
        import kawin.precipitation.NucleationRate as nf
        model.setup()
        p = model.phaseIndex(phase)
        par = model.precipitates[p]
        comp = np.squeeze(model.data.composition[0])
        for t in sorted(set(temps)):
            print("SETUPDF", nf.volumetricDrivingForce(model.therm, comp, t, par, removeCache=True), flush=True)
        return []
    tp._nucleus_estimates = h
elif mode == "df_datacomp":
    def k(model, phase, temps):
        import numpy as np
        import kawin.precipitation.NucleationRate as nf
        p = model.phaseIndex(phase)
        par = model.precipitates[p]
        comp = np.squeeze(model.data.composition[0])
        print("DATACOMP", repr(comp), repr(model.matrix.initComposition), flush=True)
        for t in sorted(set(temps)):
            nf.volumetricDrivingForce(model.therm, comp, t, par, removeCache=True)
        return []
    tp._nucleus_estimates = k
sys.argv = ["p1_run.py", root, out]
runpy.run_path(str(Path(__file__).with_name("p1_run.py")), run_name="__main__")
