#!/usr/bin/env python3
"""22-А2, шаг 2: графики зависимостей по сохранённым JSON прогонов.

* ``setka.png`` — момент остановки по сетке: классов × границы, зёрна 0–2;
* ``nastroyki.png`` — отличия ячеек (2б) и настройки kawin (2в), зёрна 0–2;
* ``zerna.png`` — ячейка приложения на зёрнах 0–9 (2г).

«Нет остановки» — точка на конце выдержки (3,6 с), пустой значок; отказ до
счёта — подпись. Нового счёта нет.

    python -B razbor_shag2.py > ../logs/a2_s2_razbor.txt
"""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from razbor_shag1 import AQUA, AXIS, BLUE, INK, INK_2, MUTED, ORANGE, SURFACE, style  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
END = 3.6
SEEDS = {0: (BLUE, "o"), 1: (ORANGE, "s"), 2: (AQUA, "^")}


def load(tag: str) -> dict | None:
    path = DATA / f"{tag}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def outcome(summary: dict | None) -> tuple[str, float | None]:
    if summary is None:
        return "нет данных", None
    if summary.get("status") == "error":
        return "отказ", None
    if summary.get("status") == "limit":
        return "предел", summary.get("final_time_s")
    return ("остановка" if summary.get("stop") else "до конца"), summary.get("final_time_s")


def dot(axis: plt.Axes, x: float, y: float, seed: int, stopped: bool, full: bool) -> None:
    color, marker = SEEDS[seed]
    axis.scatter([x], [y], s=46 if stopped else 58, marker=marker, zorder=3,
                 facecolors=color if stopped else SURFACE, edgecolors=color, linewidths=1.6)
    if full:
        axis.scatter([x], [y], s=16, marker="x", color=INK, zorder=4, linewidths=1.0)


def seed_legend(axis: plt.Axes) -> None:
    handles = [
        plt.Line2D([], [], linestyle="", marker=m, markersize=7, markerfacecolor=c, markeredgecolor=c, label=f"зерно {s}")
        for s, (c, m) in SEEDS.items()
    ]
    handles.append(plt.Line2D([], [], linestyle="", marker="o", markersize=7, markerfacecolor=SURFACE,
                              markeredgecolor=MUTED, label="без остановки (до 3,6 с)"))
    handles.append(plt.Line2D([], [], linestyle="", marker="x", markersize=6, color=INK, label="доля 100 % (BL-22)"))
    axis.legend(handles=handles, frameon=False, fontsize=8, labelcolor=INK_2, loc="upper left", bbox_to_anchor=(1.0, 1.0))


def main() -> None:
    # ---- 2а: сетка ------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    fig.patch.set_facecolor(SURFACE)
    bins_list = (20, 30, 40, 60, 80)
    print("2а. Сетка: классов × границы, зёрна 0–2 (момент остановки, с / «до конца» / «отказ»)")
    for axis, (label, cmin) in zip(axes, (("c02", 0.2), ("c05", 0.5))):
        style(axis)
        for position, bins in enumerate(bins_list):
            cells = []
            for seed in SEEDS:
                summary = load(f"a2_setka_b{bins}_{label}_s{seed}")
                kind, moment = outcome(summary)
                cells.append(f"{kind}{'' if moment is None else f' {moment:.4g}'}")
                if kind == "отказ":
                    continue
                if moment is None:
                    continue
                full = bool(summary and summary.get("final_fraction_pct", 0) >= 99.9999)
                dot(axis, position + (seed - 1) * 0.12, moment, seed, kind == "остановка", full)
            print(f"   ({cmin:g}; 10) × {bins}: " + "; ".join(cells))
            if all(c.startswith("отказ") for c in cells):
                axis.annotate("отказ BL-22\n(все зёрна)", (position + 0.3, 0.35), ha="center", color=INK_2, fontsize=8)
        axis.axhline(END, color=AXIS, linewidth=0.8, linestyle="--")
        axis.set_xticks(range(len(bins_list)))
        axis.set_xticklabels([str(b) for b in bins_list])
        axis.set_xlabel("классов размеров")
        axis.set_title(f"границы ({cmin:g}; 10) нм".replace(".", ","), color=INK, fontsize=10, loc="left")
    axes[0].set_ylabel("момент остановки, с")
    axes[0].set_ylim(0, 3.9)
    seed_legend(axes[1])
    fig.suptitle("Ячейка приложения, 3,6 с: остановка BL-35 по сетке размеров", color=INK, fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(BASE / "setka.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)

    # ---- 2б и 2в: отличия ячеек и настройки kawin ------------------------------
    configs = [
        ("ячейка приложения (умолчания)", "a2_setka_b40_c02_s{}"),
        ("bulk_n0 = 1e30", "a2_otl_n30_s{}"),
        ("без Ni", "a2_otl_bezNi_s{}"),
        ("сетка (0,5; 10) × 30", "a2_setka_b30_c05_s{}"),
        ("ячейка расчётного теста, 3,6 с", "a2_otl_backend36_s{}"),
        ("maxRcritChange 0,01 → 0,001", "a2_kawin_rcrit1e-3_s{}"),
        ("maxDissolution 1e-3 → 1e-4", "a2_kawin_diss1e-4_s{}"),
        ("maxVolumeChange 1e-3 → 1e-4", "a2_kawin_vol1e-4_s{}"),
        ("maxDtFrac 1 → 0,1", "a2_kawin_dtfrac0.1_s{}"),
        ("minComposition 0 → 1e-8", "a2_kawin_mincomp1e-8_s{}"),
        ("minComposition 0 → 1e-11", "a2_kawin_mincomp1e-11_s{}"),
        ("сверх задания: шаг ≤ 2× предыдущего", "a2_extra_cap2_s{}"),
    ]
    fig, axis = plt.subplots(figsize=(11, 5.8))
    fig.patch.set_facecolor(SURFACE)
    style(axis)
    print("2б/2в. Отличия ячеек и настройки kawin (зёрна 0–2): исход; строк; стена, с")
    for row, (label, pattern) in enumerate(configs):
        parts = []
        for seed in SEEDS:
            summary = load(pattern.format(seed))
            kind, moment = outcome(summary)
            if summary is not None and moment is not None:
                full = summary.get("final_fraction_pct", 0) >= 99.9999
                y = len(configs) - 1 - row + (seed - 1) * 0.18
                color, marker = SEEDS[seed]
                axis.scatter([moment], [y], s=46, marker=marker, zorder=3,
                             facecolors=color if kind == "остановка" else SURFACE, edgecolors=color, linewidths=1.6)
                if full:
                    axis.scatter([moment], [y], s=16, marker="x", color=INK, zorder=4, linewidths=1.0)
            text = f"з{seed}: {kind}"
            if moment is not None:
                text += f" {moment:.4g} с"
            if summary is not None:
                text += f", {summary.get('rows')} стр., {summary.get('wall_s')} с"
            parts.append(text)
        print(f"   {label}: " + "; ".join(parts))
    axis.axvline(END, color=AXIS, linewidth=0.8, linestyle="--")
    axis.set_yticks(range(len(configs)))
    axis.set_yticklabels([label for label, _ in reversed(configs)], fontsize=9)
    axis.set_xlim(0, 3.9)
    axis.set_xlabel("момент остановки, с (на 3,6 с — дошёл до конца)")
    seed_legend(axis)
    axis.set_title("Отличия ячеек (2б) и настройки kawin по одной (2в): где и когда остановка", color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(BASE / "nastroyki.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)

    # ---- 2г: зёрна 0–9 ---------------------------------------------------------
    fig, axis = plt.subplots(figsize=(9, 3.8))
    fig.patch.set_facecolor(SURFACE)
    style(axis)
    tags = {0: "a2_setka_b40_c02_s0", 1: "a2_setka_b40_c02_s1", 2: "a2_setka_b40_c02_s2"}
    tags.update({seed: f"a2_zerno_s{seed}" for seed in range(3, 10)})
    stops = 0
    print("2г. Ячейка приложения на зёрнах 0–9:")
    for seed, tag in tags.items():
        summary = load(tag)
        kind, moment = outcome(summary)
        stops += kind == "остановка"
        if moment is not None:
            axis.scatter([seed], [moment], s=46, color=BLUE if kind == "остановка" else SURFACE,
                         edgecolors=BLUE, linewidths=1.6, zorder=3)
            axis.annotate(f"{moment:.3g}".replace(".", ","), (seed, moment), xytext=(0, 7), textcoords="offset points",
                          ha="center", color=INK, fontsize=8)
        print(f"   зерно {seed}: {kind}{'' if moment is None else f' {moment:.10g} с'}; строк {summary.get('rows') if summary else '—'}")
    print(f"   остановились до 3,6 с: {stops} из {len(tags)}")
    axis.axhline(1.418, color=MUTED, linewidth=1.0, linestyle=":")
    axis.annotate("Windows, зерно 0 (17-Г): 1,418 с", (9.4, 1.418), xytext=(0, 4), textcoords="offset points",
                  ha="right", color=INK_2, fontsize=8)
    axis.axhline(END, color=AXIS, linewidth=0.8, linestyle="--")
    axis.set_xticks(list(tags))
    axis.set_xlabel("PYTHONHASHSEED")
    axis.set_ylabel("момент остановки, с")
    axis.set_ylim(0, 3.9)
    axis.set_title(f"Ячейка приложения, Linux: остановка BL-35 на {stops} из {len(tags)} зёрен", color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(BASE / "zerna.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)


def figure_005h() -> None:
    """2д: доля и C в выделениях на 0,05 ч — умолчание, minComposition 1e-8, шаг ≤ 2× (зерно 0)."""

    series = (
        ("умолчание раздела", "a2_005h_umolch_s0", BLUE, "-"),
        ("minComposition 1e-8", "a2_005h_mincomp1e-8_s0", ORANGE, "--"),
        ("шаг ≤ 2× предыдущего", "a2_extra_005h_cap2_s0", AQUA, "-"),
    )
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.8), sharex=True)
    fig.patch.set_facecolor(SURFACE)
    for axis in axes:
        style(axis)
    for label, tag, color, dash in series:
        path = DATA / f"{tag}.npz"
        if not path.exists():
            continue
        with np.load(path) as archive:
            t = archive["time"]
            fv = np.sum(archive["volFrac"], axis=1)
            fc = np.sum(archive["fconc"], axis=1)[:, 0]
            x0 = archive["composition"][0, 0]
        keep = t > 0
        axes[0].plot(t[keep], 100 * fv[keep], color=color, linestyle=dash, linewidth=1.6, label=label)
        axes[1].plot(t[keep], fc[keep] / x0, color=color, linestyle=dash, linewidth=1.6, label=label)
        if tag == "a2_extra_005h_cap2_s0":
            i = int(np.argmin(np.abs(t - 0.45)))
            axes[0].annotate("шаг ≤ 2× предыдущего: плато к 0,75 с", (t[i], 100 * fv[i]), xytext=(8, 0),
                             textcoords="offset points", color=INK, fontsize=8, va="center")
        elif tag == "a2_005h_umolch_s0":
            i = int(np.argmin(np.abs(t - 8.0)))
            axes[0].annotate("умолчание и minComposition 1e-8 (совпадают до 110 с):\nвторой шаг 22,7 с, выделение на 104–106 с",
                             (t[i], 100 * fv[i]), xytext=(0, 14), textcoords="offset points", ha="center",
                             color=INK, fontsize=8)
    axes[0].set_xscale("log")
    axes[0].set_ylabel("доля M23C6, %")
    axes[1].axhline(1.0, color=MUTED, linewidth=1.0, linestyle=":")
    axes[1].annotate("весь C сплава", (0.012, 1.0), xytext=(0, 4), textcoords="offset points", color=INK_2, fontsize=8)
    axes[1].set_ylim(0.985, 1.006)
    axes[1].set_ylabel("C в выделениях /\nC сплава")
    axes[1].set_xlabel("время, с (логарифмическая шкала)")
    axes[1].legend(frameon=False, fontsize=8, labelcolor=INK_2, loc="lower left")
    axes[0].set_title("0,05 ч, сетка (0,2; 10) × 80, зерно 0: второй шаг 22,7 с у умолчания и minComposition",
                      color=INK, fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(BASE / "005h.png", dpi=150, facecolor=SURFACE)
    plt.close(fig)


if __name__ == "__main__":
    main()
    figure_005h()
