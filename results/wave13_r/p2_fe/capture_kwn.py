"""pytest-плагин: сохраняет результат run_precipitation, не меняя расчёта."""
import os, sys, json, time
from pathlib import Path
OUT = Path(os.environ["CAPTURE_KWN_DIR"])

def pytest_configure(config):
    root = Path(config.rootpath)
    sys.path.insert(0, str(root / "app"))
    import thermogar_precipitation as tp
    original = tp.run_precipitation
    def wrapped(**kwargs):
        started = time.perf_counter()
        try:
            result = original(**kwargs)
        except BaseException as error:
            (OUT / "error.txt").write_text(f"{type(error).__name__}: {error}", encoding="utf-8")
            raise
        (OUT / "seconds.txt").write_text(f"{time.perf_counter()-started:.1f}", encoding="utf-8")
        for name in ("kinetics", "summary", "quality", "settings", "psd"):
            getattr(result, name).to_csv(OUT / f"{name}.csv", float_format="%.17g", lineterminator="\n")
        return result
    tp.run_precipitation = wrapped
