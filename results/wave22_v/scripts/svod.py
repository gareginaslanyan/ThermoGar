#!/usr/bin/env python3
"""22-В: сводная таблица прогонов results/wave22_v/progony.csv (UTF-8 с BOM, «;»).

Столбцы: часть; случай; зерно; параметры; исход; модельное время; шагов; стена, с; пик памяти, ГиБ.
Источники: журналы zamer.py (строка ZAMER — код, стена, пик RSS) в results/wave22_v/logs/ и итоговые
JSON прогонов (bl28/*.json, bl33/{a,v}/*.json, bl23/runs/*/itog.json, bl41/ocenka_*.json).
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

W = Path(__file__).resolve().parents[1]
L = W / "logs"
ZAMER = re.compile(r"ZAMER: код=(-?\d+); стена=([\d.]+) с; пик RSS=([\d.]+) ГиБ")


def zamer(path: Path) -> tuple[str, str, str]:
    if not path.is_file():
        return "", "", ""
    for line in reversed(path.read_text("utf-8", errors="replace").splitlines()):
        m = ZAMER.search(line)
        if m:
            return m.group(1), m.group(2), m.group(3)
    return "нет строки ZAMER (снят)", "", ""


def num(x, fmt="{:.6g}"):
    return "" if x is None else fmt.format(x)


def main() -> None:
    out = []
    # ШАГ 0
    for log in sorted(L.glob("shag0_*.txt")):
        if log.name == "shag0_svod.txt":
            continue
        code, wall, peak = zamer(log)
        text = log.read_text("utf-8", errors="replace")
        m = re.findall(r"=+ (.*(?:passed|failed).*) in ", text)
        res = m[-1] if m else ("RESULT: PASSED" if "RESULT: PASSED" in text else f"код {code}")
        out.append(["0", log.stem.replace("shag0_", ""), "0", "проверка ШАГА 0", res, "", "", wall, peak])
    # ШАГ 1
    for js in sorted((W / "bl28").glob("*_s[0-9].json")):
        d = json.loads(js.read_text("utf-8"))
        code, wall, peak = zamer(L / f"bl28_{d['db']}_{d['tag']}_s{d['seed']}.txt")
        out.append(["1 (BL-28)", f"KWN (модуль) {d['db']}, код {d['tag']}", d["seed"],
                    f"{d['pair']}, {d['T_c']:g} °C, {d['composition']}, γ {d['gamma']}, сетка {d['size_nm']} нм × 30",
                    f"строк {d['rows']}, доля {d['fraction_pct']:.6g} %", num(d["t_end_s"]) + " с", d["rows"] - 1, wall, peak])
    for js in sorted((W / "bl28").glob("beta_*.json")):
        d = json.loads(js.read_text("utf-8"))
        db = js.stem.split("_")[1]
        code, wall, peak = zamer(L / f"bl28_beta_{db}_{d['tag']}.txt")
        if not wall:
            code, wall, peak = zamer(L / f"bl28_beta_{db}_{d['tag']}_s0.txt")
        s = d["первые шаги"][0]
        out.append(["1 (BL-28)", f"β/τ/D {db}, код {d['tag']}", "0", "та же ячейка, перехват модели",
                    f"τ {num(s['tau, с'])} с, J(1) {num(s['скорость зарождения, 1/(м3·с)'])}", "1 с", "", wall, peak])
    # ШАГ 2
    for sub in ("a", "v", "s"):
        for js in sorted((W / "bl33" / sub).glob("*_s[0-9].json")):
            d = json.loads(js.read_text("utf-8"))
            tag = js.stem.rsplit("_s", 1)[0]
            name = f"bl33{sub}_{tag}"
            code, wall, peak = zamer(L / f"{name}_s{d['seed']}.txt")
            out.append(["2 (BL-33)", f"{d['case']} ({d['composition']})", d["seed"],
                        f"{d['variant']}, γ {d['gamma']:.5g}, u {num(d.get('u'), '{:.3f}')}, {d['temperature_c']:g} °C, {d['nucleation']}, потолок {d['cap_s']:g} с",
                        d["outcome"] + (f"; доля {100 * (d.get('volFrac_last') or 0):.3g} %" if d.get("volFrac_last") is not None else ""),
                        f"{num(d.get('t_model_s'))} из {d['duration_s']:g} с", d["steps"], wall or num(d.get("wall_total_s"), "{:.1f}"),
                        peak or num(d.get("peak_rss_gib"), "{:.3f}")])
    for js in sorted((W / "bl33" / "stadii").glob("*.json")):
        d = json.loads(js.read_text("utf-8"))
        code, wall, peak = zamer(L / f"bl33b_stadii_{js.stem.rsplit('_s', 1)[0]}_s0.txt")
        steps = d["steps"]
        out.append(["2 (BL-33)", f"стадии итератора {js.stem}", js.stem.rsplit("_s", 1)[1], "J по стадиям RK4, K = 2",
                    d["outcome"], f"{steps[-1]['t']:.6g} с" if steps else "", len(steps), wall, peak])
    # ШАГ 3
    for it in sorted((W / "bl23" / "runs").glob("*/itog.json")):
        d = json.loads(it.read_text("utf-8"))
        run = it.parent.name
        st = "obyom" if d["site"] == "BULK" else "granicy"
        code, wall, peak = zamer(L / f"bl23_T{d['T']:g}_{st}_g{d['gamma']:g}_{d['variant']}_s{d['seed']}.txt")
        out.append(["3 (BL-23)", f"{d['T']:g} °C, {d['site']}, γ {d['gamma']:g}", d["seed"],
                    f"{d['variant']}, сетка {d['K_PBM']['cMin'] * 1e9:g}…{d['K_PBM']['cMax'] * 1e9:g} нм × {d['K_PBM']['bins']} (адаптивная {d['K_PBM']['minBins']}…{d['K_PBM']['maxBins']})", d["outcome"] + (f"; доля {d.get('fraction_mol_pct_end'):.4f} мольн. %" if d.get("fraction_mol_pct_end") is not None else ""),
                    f"{num(d.get('t_model_h'))} ч", d["steps"], wall or num(d.get("wall_s"), "{:.0f}"), peak or num(d.get("peak_rss_gib"), "{:.3f}")])
    for run in sorted((W / "bl23" / "runs").glob("*_s[0-9]")):
        if (run / "itog.json").is_file() or not (run / "hod.jsonl").is_file():
            continue
        last = json.loads((run / "hod.jsonl").read_text("utf-8").splitlines()[-1])
        code, wall, peak = zamer(L / f"bl23_{run.name}.txt")
        t, site, g, variant, seed = run.name.split("_")
        out.append(["3 (BL-23)", f"{t[1:]} °C, {'BULK' if site == 'obyom' else 'GRAIN BOUNDARIES'}, γ {g[1:]}", seed[1:],
                    variant, f"снят вручную (неосуществим на выдержку); шаг {last['dt']:.3g} с", f"{last['t_h']:.4g} ч",
                    last["n"], wall or f"{last['wall_s']:.0f}", peak])
    for js in sorted((W / "bl23" / "app").glob("app_*_s[0-9].json")):
        d = json.loads(js.read_text("utf-8"))
        st = "obyom" if d["site"] == "BULK" else "granicy"
        log = L / (f"bl23app_{st}_g{d['gamma']:g}" + ("" if d["bins"] == 80 else f"_b{d['bins']}") + f"_s{js.stem[-1]}.txt")
        code, wall, peak = zamer(log)
        res = d["outcome"] + (f"; доля {d['fraction_pct_end']:.4g} %" if d.get("fraction_pct_end") is not None else "")
        nj = d["jumps_N_without_J"]
        res += f"; шагов со скачком N без зарождения {'≥ 50' if nj >= 50 else nj}"
        if d.get("first_jumps"):
            res += f" (первый на {d['first_jumps'][0]['t_h']:.4g} ч)"
        out.append(["3 (BL-23)", f"путь приложения run_precipitation, 700 °C, {d['site']}, γ {d['gamma']:g}", js.stem[-1],
                    f"K = 2, сетка {d['cmin']:g}…{d['cmax']:g} нм × {d['bins']}, выдержка {d['hours']:g} ч", res,
                    f"{num(d.get('t_h_end'))} ч", d["steps"], wall or num(d.get("wall_s"), "{:.0f}"),
                    peak or num(d.get("peak_rss_gib"), "{:.3f}")])
    code, wall, peak = zamer(L / "bl23_volumes_s0.txt")
    if wall:
        out.append(["3 (BL-23)", "молярные объёмы и равновесие двух фаз (12-1)", "0", "700 °C, 48 фаз", f"код {code}", "", "", wall, peak])
    # ШАГ 4
    for js in sorted((W / "bl41").glob("ocenka_*.json")):
        d = json.loads(js.read_text("utf-8"))
        stem = js.stem.replace("ocenka_", "")
        code, wall, peak = zamer(L / f"bl41_{stem}_s0.txt")
        rows = d["строки"]
        worst = max((abs(r.get("Δ вкл, %") or 0) for r in rows), default=0)
        out.append(["4 (BL-41)", stem, "0", f"{len(rows)} точек (состав × T), равновесие pycalphad + плотность ×4",
                    f"наибольшая |Δ| {worst:.3g} %", "", "", wall, peak])
    with (W / "progony.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["часть", "случай", "зерно", "параметры", "исход", "модельное время", "шагов", "стена, с", "пик памяти, ГиБ"])
        w.writerows(out)
    print(len(out), "строк")


if __name__ == "__main__":
    main()
