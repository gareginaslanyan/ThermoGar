#!/usr/bin/env python3
"""22-А2, шаг 1: разбор остановки на зерне 0 по сохранённым NPZ, трассе и пробам.

Входы (все в ``../data``): NPZ прогона на зерне 0 (``a2_shag0_app_seed0.npz``),
трасса стадий RK4 того же прогона (``a2_s1_trace_s0_trace.csv.gz``), равновесие
(``ravnovesie.json``), проба движущей силы (``a2_s1_dvizhushchaya_sila.json``).
Нового счёта нет.

Выход: числа — в stdout (журнал ``logs/a2_s1_razbor.txt``), ряды —
``data/a2_s1_ryady_zerno0.csv`` (UTF-8 с BOM, «;»), графики —
``ryady_zerno0.png``, ``balans_c_zerno0.png``, ``shag_zerno0.png``,
``dvizhushchaya_sila.png`` в ``results/wave22_a``.

    python -B razbor_shag1.py > ../logs/a2_s1_razbor.txt
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
DATA = BASE / "data"

# Эталонная палитра навыка dataviz, светлая тема: слоты 1–3 проверены
# validate_palette.js (все пары); бирюзовый ниже 3:1 — только с подписями.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
CRITICAL = "#d03b3b"


def style(axis: plt.Axes) -> None:
    axis.set_facecolor(SURFACE)
    axis.grid(True, color=GRID, linewidth=0.6)
    axis.tick_params(colors=INK_2, labelsize=9)
    for spine in axis.spines.values():
        spine.set_color(AXIS)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.yaxis.label.set_color(INK_2)
    axis.xaxis.label.set_color(INK_2)


def figure(rows: int, height: float) -> tuple[plt.Figure, list[plt.Axes]]:
    fig, axes = plt.subplots(rows, 1, figsize=(9, height), sharex=True)
    fig.patch.set_facecolor(SURFACE)
    axes = list(np.atleast_1d(axes))
    for axis in axes:
        style(axis)
    return fig, axes


def stop_mark(axis: plt.Axes, t_stop: float, text: bool = False) -> None:
    axis.axvline(t_stop, color=CRITICAL, linewidth=1.0, linestyle="--")
    if text:
        axis.annotate("остановка BL-35", (t_stop, 1.0), xycoords=("data", "axes fraction"),
                      xytext=(-4, -2), textcoords="offset points", ha="right", va="top",
                      color=INK, fontsize=8)


def main() -> None:
    with np.load(DATA / "a2_shag0_app_seed0.npz") as archive:
        d = {name: archive[name] for name in archive.files}
    equilibrium = json.loads((DATA / "ravnovesie.json").read_text(encoding="utf-8"))
    probe = json.loads((DATA / "a2_s1_dvizhushchaya_sila.json").read_text(encoding="utf-8"))
    trace = pd.read_csv(DATA / "a2_s1_trace_s0_trace.csv.gz", sep=";")

    t = d["time"]
    x_c = d["composition"][:, 0]
    fv = d["volFrac"][:, 0]
    n_part = d["precipitateDensity"][:, 0]
    radius = 1e9 * d["Ravg"][:, 0]
    fconc = d["fconc"][:, 0, 0]
    x_eq_kawin = d["xEqAlpha"][:, 0, 0]
    x0 = x_c[0]
    raw = (x0 - fconc) / (1 - fv)
    residual = x0 - ((1 - fv) * x_c + fconc)
    last = len(t) - 1
    app_eq = equilibrium["cells"]["app"]
    x_eq = app_eq["pycalphad"]["phases"]["BCC_A2"][0]["X"]["C"]
    f_eq = app_eq["pycalphad"]["phases"]["M23C6"][0]["NP"]
    x_eq_kawin_geteq = app_eq["kawin_getEq"]["phases"]["BCC_A2"][0]["X"]["C"]

    table = pd.DataFrame({
        "шаг": np.arange(len(t)), "время, с": t, "C в матрице, мол. доля": x_c,
        "C в матрице до зажима": raw, "xEqAlpha C (kawin)": x_eq_kawin,
        "доля M23C6": fv, "частиц, 1/м³": n_part, "средний радиус, нм": radius,
        "C в выделениях / C сплава": fconc / x0, "невязка C (x0 − [(1−f)x + f_conc])": residual,
        "движущая сила, Дж/м³": d["drivingForce"][:, 0], "зарождение, 1/(м³·с)": d["nucRate"][:, 0],
        "Rcrit, нм": 1e9 * d["Rcrit"][:, 0],
    })
    table.to_csv(DATA / "a2_s1_ryady_zerno0.csv", sep=";", index=False, encoding="utf-8-sig")

    # ---- б) баланс и в) растворимость ---------------------------------------
    print("== шаг 1, зерно 0: a2_shag0_app_seed0.npz (побитово = shag1_app_seed0_a 22-А)")
    print(f"шагов {len(t)}, остановка на {t[last]:.13g} с; x0(C) = {x0:.6g}")
    print(f"б) невязка C до остановки (шаги 0…{last - 1}): max |x0 − [(1−f)x + f_conc]| = "
          f"{np.max(np.abs(residual[:last])):.3g} (отн. {np.max(np.abs(residual[:last])) / x0:.3g})")
    print(f"   на шаге остановки {last}: невязка {residual[last]:.6g} = {residual[last] / x0:+.4f}·x0; "
          f"C в выделениях {fconc[last] / x0:.4f}·x0; сырой x_C {raw[last]:.6g} = {raw[last] / x0:+.4f}·x0 → зажат в 0")
    print(f"   шагом раньше: C в выделениях {fconc[last - 1] / x0:.6f}·x0, x_C {x_c[last - 1]:.6g}")
    print(f"в) растворимость C в BCC_A2 при M23C6, 700 °C: pycalphad {x_eq:.6g}; kawin getEq (+1 Дж/моль) "
          f"{x_eq_kawin_geteq:.6g}; xEqAlpha в расчёте {np.unique(np.round(x_eq_kawin[x_eq_kawin > 0], 9))[:3]}")
    print(f"   равновесная доля M23C6 {f_eq:.6g}; в расчёте на плато {fv[last - 1]:.6g}")
    plateau = (t > 0.67) & (np.arange(len(t)) < last)
    print(f"   плато t > 0,67 с: x_C {x_c[plateau].min():.4g}…{np.percentile(x_c[plateau], 50):.4g} (медиана), "
          f"x_C/x_eq медиана {np.median(x_c[plateau]) / x_eq:.3f}")
    above = x_c[:last] > x_eq
    print(f"   перед остановкой x_C = {x_c[last - 1]:.4g} = {x_c[last - 1] / x_eq:.3f}·x_eq > x_eq: {bool(above[-1])}; "
          f"шагов от последнего x_C > x_eq до x_C ≤ 0: {last - int(np.max(np.where(above)[0]))}")

    # Стадии RK4 шага остановки по трассе.
    stop_rows = trace[trace.n == last - 1]
    print("   стадии RK4 шага остановки (трасса, n = шаг начала):")
    for _, row in stop_rows.iterrows():
        print(f"     post={bool(row.post)} t={row.t:.6g} x_C={row.x_C:.4g} сырой={row.raw_C:+.4g} доля={row.fv:.6f} "
              f"N={row.N:.4g} dG={row.get('dG_J_m3', float('nan')):+.4g} J={row.get('J', float('nan')):.3g} "
              f"Rcrit={1e9 * row.get('Rcrit', float('nan')):.4g} нм stale={row.get('stale')}")
    kicks = []
    post = trace[trace.post].reset_index(drop=True)
    post["dfv"] = post.fv.diff()
    for _, row in post[(post.t > 0.67) & (post.dfv.abs() > 1e-3)].iterrows():
        kicks.append((row.n, row.t, row.dfv, row.x_C))
    print(f"   «пинки» на плато (|Δдоля| > 0,1 % за шаг): {len(kicks)}")
    for n, time_s, dfv, xc in kicks:
        print(f"     шаг {int(n)} → t={time_s:.4f} с: Δдоля {100 * dfv:+.3f} %, x_C после {xc:.4g}")
    stale = trace[(trace.get("stale") == True)]  # noqa: E712
    print(f"   стадий с dG < 0 (зарождение и Rcrit в Y — от прошлой стадии, KWNBase.py:422-423): {len(stale)}")

    # ---- г) проба движущей силы ------------------------------------------------
    print("г) движущая сила M23C6 при составе шага перед остановкой, C заменён:")
    for row in probe["probes"]:
        a, m, s = row["без_кэша"], row["матрица_локально"], row["касательная_по_шагам"]
        print(f"   x_C={row['x_C']:<10.4g} dG={a['dG_J_m3']:+.4e} Дж/м³ ({a['dG_J_mol']:+.5g} Дж/моль), "
              f"J={a['J']:.3g}, Rcrit={a.get('Rcrit_nm')}; матрица сошлась: {m['converged']}; "
              f"по шагам с новой выборкой: dG={s['dG_J_mol']:+.5g} Дж/моль")
    print("   зависимость от стартовой точки решателя (x_C = 0 и 1e-12):")
    for row in probe["start_dependence"]:
        print(f"     старт x_C={row['start_x_C']:<9.3g} → x_C={row['x_C']:<6.3g}: dG={row['dG_J_m3']:+.4e} Дж/м³")

    # ---- графики ----------------------------------------------------------------
    t_stop = t[last]
    fig, axes = figure(5, 11)
    axes[0].semilogy(t[:last], x_c[:last], color=BLUE, linewidth=1.6)
    axes[0].axhline(x_eq, color=MUTED, linewidth=1.0, linestyle=":")
    axes[0].annotate(f"растворимость C при M23C6 (pycalphad) {x_eq:.3g}", (0.98, x_eq), xycoords=("axes fraction", "data"),
                     xytext=(0, 4), textcoords="offset points", ha="right", color=INK_2, fontsize=8)
    axes[0].set_ylabel("C в матрице,\nмол. доля")
    axes[1].plot(t, 100 * fv, color=BLUE, linewidth=1.6)
    axes[1].axhline(100 * f_eq, color=MUTED, linewidth=1.0, linestyle=":")
    axes[1].annotate(f"равновесная доля {100 * f_eq:.3f} %", (0.02, 100 * f_eq), xycoords=("axes fraction", "data"),
                     xytext=(0, 4), textcoords="offset points", color=INK_2, fontsize=8)
    axes[1].set_ylabel("доля M23C6, %")
    axes[2].semilogy(t, n_part, color=BLUE, linewidth=1.6)
    axes[2].set_ylabel("частиц, 1/м³")
    axes[3].plot(t, radius, color=BLUE, linewidth=1.6)
    axes[3].set_ylabel("средний\nрадиус, нм")
    axes[4].plot(t, fconc / x0, color=BLUE, linewidth=1.6)
    axes[4].axhline(1.0, color=MUTED, linewidth=1.0, linestyle=":")
    axes[4].annotate("весь C сплава", (0.02, 1.0), xycoords=("axes fraction", "data"), xytext=(0, 4),
                     textcoords="offset points", color=INK_2, fontsize=8)
    axes[4].set_ylabel("C в выделениях /\nC сплава")
    axes[4].set_xlabel("время, с")
    for index, axis in enumerate(axes):
        stop_mark(axis, t_stop, text=index == 0)
    axes[0].set_title("Ячейка приложения, зерно 0: ряды до остановки (последняя точка — шаг остановки)",
                      color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(BASE / "ryady_zerno0.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)

    fig, axes = figure(2, 6.5)
    matrix_share = (1 - fv) * x_c / x0
    precip_share = fconc / x0
    axes[0].plot(t, matrix_share, color=BLUE, linewidth=1.6)
    axes[0].plot(t, precip_share, color=ORANGE, linewidth=1.6)
    axes[0].plot(t, matrix_share + precip_share, color=AQUA, linewidth=1.6, linestyle="--")
    i_mid = int(np.argmin(np.abs(t - 0.35)))
    axes[0].annotate("в матрице", (t[i_mid], matrix_share[i_mid]), xytext=(6, 2), textcoords="offset points", color=INK, fontsize=8)
    axes[0].annotate("в выделениях", (t[i_mid], precip_share[i_mid]), xytext=(6, -10), textcoords="offset points", color=INK, fontsize=8)
    axes[0].annotate(f"сумма = {matrix_share[last] + precip_share[last]:.3f} на шаге остановки",
                     (t[last], matrix_share[last] + precip_share[last]), xytext=(-10, -16), textcoords="offset points",
                     ha="right", color=INK, fontsize=8)
    axes[0].legend(["C в матрице", "C в выделениях", "сумма"], frameon=False, fontsize=8, loc="center right",
                   labelcolor=INK_2)
    axes[0].set_ylabel("доля C сплава")
    axes[1].plot(t, residual / x0, color=BLUE, linewidth=1.6)
    axes[1].set_yscale("symlog", linthresh=1e-15)
    axes[1].set_ylabel("невязка /\nC сплава")
    axes[1].set_xlabel("время, с")
    axes[1].annotate(f"{residual[last] / x0:+.3f} на шаге остановки", (t[last], residual[last] / x0), xytext=(-8, 6),
                     textcoords="offset points", ha="right", color=INK, fontsize=8)
    for index, axis in enumerate(axes):
        stop_mark(axis, t_stop, text=index == 0)
    axes[0].set_title("Баланс углерода, зерно 0: x0 = (1 − f)·x + f_conc до последнего шага", color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(BASE / "balans_c_zerno0.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)

    # Шаг по времени и активный предел (по трассе).
    comps = ["dt_PSD", "dt_NucleationRate", "dt_Temperature", "dt_Rcrit", "dt_Volume"]
    post = trace[trace.post].copy()
    post["dtMin"] = post[comps + ["dtMax"]].min(axis=1)
    post["active"] = np.where(post.dt_getDt != post.dtMin, "прочие",
                              post[comps].idxmin(axis=1).where(post[comps].min(axis=1) == post.dtMin, "прочие"))
    names = {"dt_Rcrit": ("Rcrit", BLUE), "dt_PSD": ("PSD", ORANGE), "dt_Volume": ("объём", AQUA)}
    fig, axes = figure(2, 6.5)
    fig.set_size_inches(10.5, 6.5)
    for key, (label, color) in names.items():
        part = post[post.active == key]
        axes[0].scatter(part.t, part.dt_getDt, s=8, color=color, label=f"предел {label}", linewidths=0)
    other = post[~post.active.isin(list(names))]
    axes[0].scatter(other.t, other.dt_getDt, s=8, color=MUTED, label="прочие", linewidths=0)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("шаг, с")
    axes[0].legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(1.0, 1.0), labelcolor=INK_2, markerscale=1.6)
    axes[1].plot(post.t, 100 * post.fv, color=BLUE, linewidth=1.2)
    axes[1].set_ylabel("доля M23C6, %")
    axes[1].set_xlabel("время, с")
    axes[1].set_ylim(2.9, 6.3)
    for index, axis in enumerate(axes):
        stop_mark(axis, t_stop, text=index == 0)
    axes[0].set_title("Шаг kawin и его предел, зерно 0: скачки ×11–13 на плато и «пинки» доли", color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(BASE / "shag_zerno0.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)

    # Движущая сила против x_C: сошедшиеся точки — линия, x_C = 0 и 1e-12 — разброс по стартам.
    fig, axes = figure(1, 4.2)
    axis = axes[0]
    good = [row for row in probe["probes"] if row["матрица_локально"]["converged"]]
    xs = [row["x_C"] for row in good]
    ys = [row["без_кэша"]["dG_J_m3"] for row in good]
    axis.plot(xs, ys, color=BLUE, linewidth=1.6, marker="o", markersize=5)
    for x_value, y_value in zip(xs, ys):
        axis.annotate(f"{y_value:+.2e}", (x_value, y_value), xytext=(6, 4), textcoords="offset points", color=INK, fontsize=8)
    bad = probe["start_dependence"]
    zero_x = 3e-14  # место точки x_C = 0 на логарифмической оси, подписано «0»
    axis.scatter([zero_x if row["x_C"] == 0 else row["x_C"] for row in bad], [row["dG_J_m3"] for row in bad],
                 color=ORANGE, s=22, zorder=3)
    axis.annotate("x_C = 0 и 1e-12: решатель pycalphad не сошёлся,\nзнак зависит от стартовой точки (6 стартов)",
                  (zero_x, 4e8), xytext=(8, 0), textcoords="offset points", color=INK, fontsize=8, va="center")
    axis.annotate(f"растворимость {x_eq:.3g}", (x_eq, -3e6), xytext=(-6, 0), textcoords="offset points",
                  ha="right", color=INK_2, fontsize=8)
    axis.axhline(0, color=AXIS, linewidth=0.8)
    axis.axvline(x_eq, color=MUTED, linewidth=1.0, linestyle=":")
    axis.set_xscale("log")
    axis.set_yscale("symlog", linthresh=1e5)
    axis.set_yticks([-1e9, -1e7, -1e5, 0, 1e5, 1e7, 1e9])
    axis.set_xlim(1.5e-14, 1e-4)
    axis.set_xticks([zero_x, 1e-12, 1e-9, 1e-6, 1e-4])
    axis.set_xticklabels(["0", "1e-12", "1e-9", "1e-6", "1e-4"])
    axis.set_xlabel("C в матрице, мол. доля (Cr, Ni — как на шаге перед остановкой)")
    axis.set_ylabel("движущая сила M23C6, Дж/м³")
    axis.set_title("Функция движущей силы kawin: определена до 1e-9, при C = 0 — нет", color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(BASE / "dvizhushchaya_sila.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)


if __name__ == "__main__":
    main()
