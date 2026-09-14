import os, subprocess, sys, time, psutil, json
T = sys.argv[1]
env = dict(os.environ, PYTHONHASHSEED="0", CAPTURE_KWN_DIR=T, PYTHONPATH=T,
           THERMOGAR_BACKEND_REPORT=os.path.join(T, "backend_report.json"))
cmd = [r"C:\Users\gareg\Desktop\ThermoGar\.venv-windows\Scripts\python.exe", "-B", "-X", "utf8", "-m", "pytest",
       "tools/test_backend_calculations.py::test_kwn_module[fe]", "-q", "-p", "no:timeout", "-p", "capture_kwn", "-p", "no:cacheprovider"]
start = time.time()
with open(os.path.join(T, "pytest_out.txt"), "w", encoding="utf-8") as log:
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
    p = psutil.Process(proc.pid); peak = 0; minfree = 1e99
    while proc.poll() is None:
        try:
            rss = sum(c.memory_info().rss for c in [p] + p.children(recursive=True))
        except psutil.Error:
            rss = 0
        peak = max(peak, rss); minfree = min(minfree, psutil.virtual_memory().available)
        time.sleep(2)
json.dump({"exit": proc.returncode, "seconds": round(time.time()-start, 1), "peak_tree_gib": round(peak/2**30, 3),
           "min_available_gib": round(minfree/2**30, 3)}, open(os.path.join(T, "run.json"), "w"))
