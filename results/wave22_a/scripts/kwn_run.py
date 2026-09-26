#!/usr/bin/env python3
"""22-А: один прогон KWN на стали через ``thermogar_precipitation.run_precipitation``.

Ячейка (``--cell app|backend``) собирается ``vhody.py`` из исходников; ключи
меняют только то, что названо. Код программы не меняется: подмены умолчаний
kawin (``--constraint``, ``--iterator``, ``--min-dt-frac``) и трассировка шагов
(``--trace``) делаются обёртками над классами kawin внутри этого процесса.
Без этих ключей прогон — тот же вызов, что в тестах.

Результат — в ``--out-dir``:

* ``<tag>.json`` — входы, подмены, версии, время, пик памяти, итог, проверки,
  баланс масс по шагам (сводка);
* ``<tag>.npz`` — ``model.toDict()`` kawin (то же, что NPZ приложения), при
  срыве по пределу — частичный;
* ``<tag>_trace.csv.gz`` (с ``--trace``) — каждый вызов баланса масс kawin
  (стадии RK4 и принятый шаг) с составом до зажима, и ограничители шага.

Предел на прогон — ``--limit-s`` (по умолчанию 1800 с, задание 22-А): по
SIGALRM расчёт прерывается, сохраняется посчитанная часть.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import platform
import resource
import signal
import sys
import time
import traceback
from importlib.metadata import version
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLBACKEND", "Agg")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for entry in (ROOT / "app", HERE):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import numpy as np  # noqa: E402

import vhody  # noqa: E402


class RunLimit(BaseException):
    """Предел времени прогона; BaseException, чтобы kawin его не проглотил."""


# --------------------------------------------------------------------------- #
# Подмены и трассировка (только в этом процессе)
# --------------------------------------------------------------------------- #

MODEL: list[Any] = []
MASS_BALANCE: list[dict[str, Any]] = []
STEP_DT: list[dict[str, Any]] = []
_DT_PARTS: list[tuple[str, float]] = []
_IN_POST = [False]


def install_overrides(constraints: dict[str, float], iterator: str | None,
                      min_dt_frac: float | None, max_dt_frac: float | None,
                      dt_growth_cap: float | None = None) -> None:
    from kawin.GenericModel import GenericModel
    from kawin.precipitation.PrecipitationParameters import Constraints
    from kawin.solver import Iterators

    if constraints:
        original_reset = Constraints.reset

        def reset(self: Any) -> None:
            original_reset(self)
            for name, value in constraints.items():
                if not hasattr(self, name):
                    raise AttributeError(f"У Constraints kawin нет поля {name}")
                setattr(self, name, value)

        Constraints.reset = reset

    original_solve = GenericModel.solve

    def solve(self: Any, simTime: float, *args: Any, **kwargs: Any) -> None:
        MODEL[:] = [self]
        if iterator is not None:
            kwargs["iterator"] = {
                "euler": Iterators.explicitEulerIterator,
                "rk4": Iterators.rk4Iterator,
            }[iterator]
        if min_dt_frac is not None:
            kwargs["minDtFrac"] = min_dt_frac
        if max_dt_frac is not None:
            kwargs["maxDtFrac"] = max_dt_frac
        return original_solve(self, simTime, *args, **kwargs)

    GenericModel.solve = solve

    if dt_growth_cap is not None:
        # 22-А2, сверх настроек kawin: набросок для шага 3 — шаг не больше
        # dt_growth_cap × предыдущего. В kawin 0.5.0 рост шага ограничен только
        # при dt == dtMax (KWNEuler.py:347-348); иначе предел может отпустить
        # шаг в десятки раз за один шаг.
        from kawin.precipitation.KWNEuler import PrecipitateModel

        original_get_dt = PrecipitateModel.getDt

        def capped_get_dt(self: Any, dXdt: Any) -> float:
            dt = original_get_dt(self, dXdt)
            i = int(self.data.n)
            if i > 0:
                dt = min(dt, dt_growth_cap * float(self.data.time[i] - self.data.time[i - 1]))
            return dt

        PrecipitateModel.getDt = capped_get_dt


def install_trace() -> None:
    from kawin.precipitation.KWNEuler import PrecipitateModel
    from kawin.precipitation.PrecipitationParameters import Constraints

    for name in (
        "computeDTfromPSD",
        "computeDTfromNucleationRate",
        "computeDTfromTemperature",
        "computeDTfromRcrit",
        "computeDTfromVolume",
    ):
        original = getattr(Constraints, name)

        def wrapper(self: Any, *args: Any, _original: Any = original, _name: str = name) -> Any:
            value = _original(self, *args)
            _DT_PARTS.append((_name, float(value)))
            return value

        setattr(Constraints, name, wrapper)

    original_get_dt = PrecipitateModel.getDt

    def get_dt(self: Any, dXdt: Any) -> float:
        i = int(self.data.n)
        _DT_PARTS.clear()
        dt = original_get_dt(self, dXdt)
        row = {
            "n": i,
            "t": float(self.data.time[i]),
            "dtPrev": 0.01 if i == 0 else float(self.data.time[i] - self.data.time[i - 1]),
            "dtMax": float(self.finalTime - self.data.time[i]),
            "dt_getDt": float(dt),
        }
        row.update({name.replace("computeDTfrom", "dt_"): value for name, value in _DT_PARTS})
        STEP_DT.append(row)
        return dt

    PrecipitateModel.getDt = get_dt

    original_post = PrecipitateModel.postProcess

    def post_process(self: Any, t: float, x: Any) -> Any:
        _IN_POST[0] = True
        try:
            return original_post(self, t, x)
        finally:
            _IN_POST[0] = False

    PrecipitateModel.postProcess = post_process

    original_balance = PrecipitateModel._calcMassBalance

    def mass_balance(self: Any, t: float, x: Any, Y: Any) -> Any:
        Y = original_balance(self, t, x, Y)
        x0 = np.asarray(self.data.composition[0], float)
        fv = float(np.sum(Y.volFrac[0]))
        fconc = np.sum(np.asarray(Y.fconc[0], float), axis=0)
        raw = (x0 - fconc) / (1.0 - fv) if fv < 1.0 else np.full_like(x0, np.nan)
        row: dict[str, Any] = {
            "n": int(self.data.n),
            "t": float(t),
            "post": bool(_IN_POST[0]),
            "fv": fv,
            "N": float(np.sum(Y.precipitateDensity[0])),
        }
        for index, element in enumerate(self.elements):
            row[f"x_{element}"] = float(Y.composition[0, index])
            row[f"raw_{element}"] = float(raw[index])
            row[f"fconc_{element}"] = float(fconc[index])
        MASS_BALANCE.append(row)
        return Y

    PrecipitateModel._calcMassBalance = mass_balance

    # 22-А2: зарождение и рост той же стадии — к той же строке трассы. При
    # движущей силе < 0 kawin пропускает остальное (KWNBase.py:422-423), и
    # скорость зарождения, Rcrit, Rnuc в Y остаются от предыдущей стадии —
    # флаг stale это отмечает.
    from kawin.precipitation.KWNBase import PrecipitateBase

    def current_row(t: float, n: int) -> dict[str, Any]:
        if MASS_BALANCE and MASS_BALANCE[-1]["n"] == n and MASS_BALANCE[-1]["t"] == float(t):
            return MASS_BALANCE[-1]
        row = {"n": n, "t": float(t), "post": bool(_IN_POST[0]), "stage": "без баланса"}
        MASS_BALANCE.append(row)
        return row

    original_nucleation = PrecipitateBase._calcNucleationRate

    def nucleation(self: Any, t: float, x: Any, Y: Any) -> Any:
        Y = original_nucleation(self, t, x, Y)
        row = current_row(t, int(self.data.n))
        dg = float(Y.drivingForce[0, 0])
        row.update({
            "xC_nuc": float(np.atleast_1d(np.squeeze(Y.composition[0]))[0]),
            "dG_J_m3": dg,
            "J": float(Y.nucRate[0, 0]),
            "Rcrit": float(Y.Rcrit[0, 0]),
            "Rnuc": float(Y.Rnuc[0, 0]),
            "beta": float(Y.impingement[0, 0]),
            "stale": bool(dg < 0),
        })
        return Y

    PrecipitateBase._calcNucleationRate = nucleation

    original_growth = PrecipitateModel._growthRate

    def growth_rate(self: Any, Y: Any) -> Any:
        growth, Y = original_growth(self, Y)
        row = current_row(float(Y.time[0]), int(self.data.n))
        g = np.asarray(growth[0], float)
        row.update({
            "xEqAlpha_C": float(Y.xEqAlpha[0, 0, 0]),
            "growth_max": float(np.max(g)) if g.size else float("nan"),
            "growth_min": float(np.min(g)) if g.size else float("nan"),
        })
        return growth, Y

    PrecipitateModel._growthRate = growth_rate

    class CountingStdout:
        """Пересылает вывод и считает предупреждения kawin по строкам трассы."""

        def __init__(self, stream: Any) -> None:
            self._stream = stream

        def write(self, text: str) -> int:
            if "Warning:" in text and MASS_BALANCE:
                MASS_BALANCE[-1]["kawin_warnings"] = MASS_BALANCE[-1].get("kawin_warnings", 0) + 1
            return self._stream.write(text)

        def flush(self) -> None:
            self._stream.flush()

        def __getattr__(self, name: str) -> Any:
            return getattr(self._stream, name)

    sys.stdout = CountingStdout(sys.stdout)


def install_progress(interval_s: float) -> None:
    """Журнал модельного времени: строка раз в ``interval_s`` секунд стены."""

    from kawin.precipitation.KWNBase import PrecipitateBase

    started = time.perf_counter()
    last = [started]
    original_post = PrecipitateBase.postProcess

    def post_process(self: Any, t: float, x: Any) -> Any:
        result = original_post(self, t, x)
        now = time.perf_counter()
        if now - last[0] >= interval_s:
            last[0] = now
            n = int(self.data.n)
            print(
                f"ЖУРНАЛ стена={now - started:.0f} с; t={float(self.data.time[n]):.6g} с "
                f"({float(self.data.time[n]) / 3600:.4g} ч); шаг={n}; "
                f"доля={100 * float(np.sum(self.data.volFrac[n])):.4f} %; "
                f"x_C={float(self.data.composition[n, 0]):.4g}",
                flush=True,
            )
        return result

    PrecipitateBase.postProcess = post_process


# --------------------------------------------------------------------------- #
# Разбор данных kawin
# --------------------------------------------------------------------------- #


def balance_table(data: dict[str, np.ndarray], solutes: list[str]) -> dict[str, Any]:
    """Баланс по каждому элементу на принятых шагах.

    kawin считает состав матрицы из баланса масс: x = (x0 − f_conc)/(1 − f_v),
    отрицательное зажимается в ``minComposition``. Невязка
    ``x0 − [(1 − f_v)·x + f_conc]`` — сколько элемента «лишнего» в сумме
    матрица + выделения против исходного содержания (в мольных долях сплава).
    """

    composition = np.asarray(data["composition"], float)
    fraction = np.sum(np.asarray(data["volFrac"], float), axis=1)
    fconc = np.sum(np.asarray(data["fconc"], float), axis=1)
    x0 = composition[0]
    total = (1.0 - fraction)[:, None] * composition + fconc
    residual = x0[None, :] - total
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = (x0[None, :] - fconc) / (1.0 - fraction)[:, None]
    out: dict[str, Any] = {}
    for index, element in enumerate(solutes):
        res = residual[:, index]
        clamped = raw[:, index] < 0
        first = int(np.argmax(clamped)) if clamped.any() else None
        unclamped = ~clamped
        out[element] = {
            "x0": float(x0[index]),
            "max_abs_residual_unclamped": float(np.max(np.abs(res[unclamped]))) if unclamped.any() else None,
            "max_rel_residual_unclamped": (
                float(np.max(np.abs(res[unclamped])) / x0[index]) if unclamped.any() and x0[index] > 0 else None
            ),
            "clamped_steps": int(clamped.sum()),
            "first_clamped_step": first,
            "first_clamped_time_s": float(data["time"][first]) if first is not None else None,
            "residual_at_first_clamp": float(res[first]) if first is not None else None,
            "raw_at_first_clamp": float(raw[first, index]) if first is not None else None,
            "fconc_over_x0_at_first_clamp": (
                float(fconc[first, index] / x0[index]) if first is not None and x0[index] > 0 else None
            ),
            "residual_last": float(res[-1]),
            "raw_last": float(raw[-1, index]),
            "x_last": float(composition[-1, index]),
            "min_x": float(np.min(composition[:, index])),
        }
    return out


def write_trace(path: Path) -> None:
    rows: list[dict[str, Any]] = []
    dt_by_n = {row["n"]: row for row in STEP_DT}
    for row in MASS_BALANCE:
        merged = dict(row)
        if row["post"]:
            merged.update({k: v for k, v in dt_by_n.get(row["n"], {}).items() if k not in {"n", "t"}})
        rows.append(merged)
    if not rows:
        return
    names: list[str] = []
    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in row.items()})


# --------------------------------------------------------------------------- #
# Прогон
# --------------------------------------------------------------------------- #


def parse_constraint(text: str) -> tuple[str, float]:
    name, _, value = text.partition("=")
    if not value:
        raise argparse.ArgumentTypeError(f"ожидается имя=число: {text!r}")
    return name.strip(), float(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cell", choices=sorted(vhody.CELLS), required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--out-dir", default=str(HERE.parent / "data"))
    parser.add_argument("--bins", type=int)
    parser.add_argument("--cmin", type=float)
    parser.add_argument("--cmax", type=float)
    parser.add_argument("--duration-h", type=float)
    parser.add_argument("--bulk-n0", type=float)
    parser.add_argument("--composition", help="строка состава вместо ячейки, те же единицы")
    parser.add_argument("--progress", type=float, default=0.0,
                        help="журнал модельного времени раз в столько секунд стены")
    parser.add_argument("--constraint", type=parse_constraint, action="append", default=[],
                        help="поле kawin Constraints=значение, повторяемый")
    parser.add_argument("--iterator", choices=("rk4", "euler"))
    parser.add_argument("--min-dt-frac", type=float)
    parser.add_argument("--max-dt-frac", type=float)
    parser.add_argument("--dt-growth-cap", type=float,
                        help="сверх настроек kawin: шаг не больше этого множителя от предыдущего")
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--no-npz", action="store_true")
    parser.add_argument("--limit-s", type=float, default=1800.0)
    args = parser.parse_args()

    cell = vhody.CELLS[args.cell]()
    arguments = dict(cell["arguments"])
    changed: dict[str, Any] = {}
    for key, value in (("bins", args.bins), ("cmin_nm", args.cmin), ("cmax_nm", args.cmax),
                       ("duration_h", args.duration_h), ("bulk_n0", args.bulk_n0),
                       ("composition_text", args.composition)):
        if value is not None and value != arguments[key]:
            changed[key] = value
            arguments[key] = value
    constraints = dict(args.constraint)
    install_overrides(constraints, args.iterator, args.min_dt_frac, args.max_dt_frac, args.dt_growth_cap)
    # Журнал — до трассы: обёртка трассы берёт postProcess, уже обёрнутый журналом.
    if args.progress > 0:
        install_progress(args.progress)
    if args.trace:
        install_trace()

    import thermogar_precipitation as tp
    from thermogar_release_policy import RELEASE_DATABASE_LABELS, RELEASE_DATABASE_RELATIVE_PATHS

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "tag": args.tag,
        "cell": args.cell,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED", "случайное"),
        "changed_inputs": changed,
        "kawin_overrides": {
            "constraints": constraints,
            "iterator": args.iterator or "rk4 (умолчание GenericModel.solve)",
            "minDtFrac": args.min_dt_frac if args.min_dt_frac is not None else "1e-8 (умолчание)",
            "maxDtFrac": args.max_dt_frac if args.max_dt_frac is not None else "1 (умолчание)",
            "dt_growth_cap": args.dt_growth_cap,
        },
        "arguments": arguments,
        "sources": cell["sources"],
        "versions": {
            "python": platform.python_version(),
            **{name: version(name) for name in ("pycalphad", "kawin", "numpy", "scipy")},
        },
        "limit_s": args.limit_s,
    }

    def on_alarm(_signum: int, _frame: Any) -> None:
        raise RunLimit(f"предел {args.limit_s:.0f} с")

    signal.signal(signal.SIGALRM, on_alarm)
    signal.setitimer(signal.ITIMER_REAL, args.limit_s)
    started = time.perf_counter()
    result = None
    status = "ok"
    error_text = ""
    try:
        result = tp.run_precipitation(
            db=None,
            database_path=ROOT / RELEASE_DATABASE_RELATIVE_PATHS["fe"],
            database_label=RELEASE_DATABASE_LABELS["fe"],
            **arguments,
        )
    except RunLimit as error:
        status = "limit"
        error_text = str(error)
    except Exception as error:  # noqa: BLE001 — исход прогона и есть результат
        status = "error"
        error_text = f"{type(error).__name__}: {error}"
        summary["traceback"] = traceback.format_exc()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    wall = time.perf_counter() - started
    summary["status"] = status
    summary["error"] = error_text
    summary["wall_s"] = round(wall, 2)
    summary["peak_rss_gib"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20, 3)

    model = MODEL[0] if MODEL else None
    solutes = list(vhody_solutes(arguments))
    data: dict[str, np.ndarray] | None = None
    if result is not None:
        with np.load(__import__("io").BytesIO(result.npz)) as archive:
            data = {name: archive[name] for name in archive.files}
        if not args.no_npz:
            (out_dir / f"{args.tag}.npz").write_bytes(result.npz)
        kinetics = result.kinetics
        quality = result.quality
        summary.update({
            "rows": int(len(kinetics)),
            "final_time_s": float(kinetics["Время, с"].iloc[-1]),
            "stop": bool(result.stop_note),
            "stop_note": result.stop_note,
            "warnings": list(result.warnings),
            "quality": {row["Проверка"]: row["Статус"] for row in quality.to_dict(orient="records")},
            "quality_all_passed": bool((quality["Статус"] == "пройдена").all()),
            "final_fraction_pct": float(kinetics["Объёмная доля, %"].iloc[-1]),
            "max_fraction_pct": float(kinetics["Объёмная доля, %"].max()),
            "final_radius_nm": float(kinetics["Средний радиус, нм"].iloc[-1]),
            "final_density_m3": float(kinetics["Плотность частиц, 1/м³"].iloc[-1]),
            "summary_table": {row["Показатель"]: row["Значение"] for row in result.summary.to_dict(orient="records")},
            "final_psd_bins": int(len(result.psd)),
        })
    elif model is not None and getattr(model, "data", None) is not None:
        data = {name: np.asarray(value) for name, value in model.toDict().items()}
        if not args.no_npz:
            import io

            buffer = io.BytesIO()
            np.savez_compressed(buffer, **data)
            (out_dir / f"{args.tag}.npz").write_bytes(buffer.getvalue())
        n = int(model.data.n) + 1
        summary.update({
            "rows": n,
            "final_time_s": float(model.data.time[n - 1]),
            "stop": None,
            "final_fraction_pct": float(100 * np.sum(model.data.volFrac[n - 1])),
            "final_radius_nm": float(1e9 * model.data.Ravg[n - 1, 0]),
            "final_density_m3": float(model.data.precipitateDensity[n - 1, 0]),
        })
    if data is not None:
        summary["balance"] = balance_table(data, solutes)
        summary["steps"] = int(len(data["time"]))
    if args.trace:
        write_trace(out_dir / f"{args.tag}_trace.csv.gz")
        summary["trace_rows"] = len(MASS_BALANCE)
        summary["trace_clamped_calls"] = {
            element: int(sum(1 for row in MASS_BALANCE if row.get(f"raw_{element}", 0.0) < 0))
            for element in solutes
        }
    (out_dir / f"{args.tag}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    brief = {k: summary.get(k) for k in (
        "tag", "status", "error", "wall_s", "peak_rss_gib", "rows", "final_time_s", "stop",
        "final_fraction_pct", "final_radius_nm", "quality_all_passed",
    )}
    print("ИТОГ", json.dumps(brief, ensure_ascii=False))
    if summary.get("stop_note"):
        print("stop_note:", summary["stop_note"])
    return 0 if status == "ok" else 2


def vhody_solutes(arguments: dict[str, Any]) -> list[str]:
    import thermogar_precipitation as tp

    parsed = tp._parse_composition(arguments["composition_text"])
    return sorted(parsed)


if __name__ == "__main__":
    raise SystemExit(main())
