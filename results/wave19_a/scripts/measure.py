"""Замеры 19-А (BL-56, BL-55): цепочка режима стали, справочник фаз, Fe–0,8C.

Запуск (из корня дерева):
    MPLBACKEND=Agg PYTHONHASHSEED=0 THERMOGAR_STATE_ROOT=results\\validation\\wave19_a_state \\
    .venv-windows/Scripts/python.exe -B -X utf8 results/wave19_a/scripts/measure.py <do|posle> <1a|1v|1g|1g_batch>...

1а — настоящие ``_parse_csv`` и ``run_batch_calculations``, поддельный runner
     ``FakeBatchRunner`` из ``tools/thermogar_verified_equilibrium_test.py``.
1в — ``phase_reference_dataframe`` приложения (загрузчик ``app_extract``).
1г — ``batch_engine_runner`` приложения, строки пакета собраны напрямую;
     одиночное равновесие — ветка Fe раздела «Расчёты» (``prepare_calculation``
     + ``pycalphad.equilibrium`` с pdens 500).
1g_batch — (ПОСЛЕ) файл -> ``_parse_csv`` -> ``batch_table_dataframe`` ->
     ``run_batch_calculations`` с настоящим ``batch_engine_runner``.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "tools"))

import thermogar_verified_state as vs  # noqa: E402
import thermogar_workspace as workspace  # noqa: E402

VALUES = (
    "", "metastable", "метастабильный", "практический", "цементит", "cementite",
    "stable", "стабильный", "графит", "graphite", "metastabe",
)
LABELS = ("пусто",) + VALUES[1:]


def _csv_bytes(rows: list[tuple[str, str]]) -> bytes:
    out = io.StringIO(newline="")
    writer = csv.writer(out, delimiter=",", lineterminator="\n")
    writer.writerow(vs.TEMPLATE_HEADERS)
    for name, mode in rows:
        writer.writerow((name, "fe", "FE", "мас.%", 700, "C=0.8", mode, 101325, ""))
    return out.getvalue().encode("utf-8")


def _write(path: Path, text: str) -> str:
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _table(header: tuple[str, ...], rows: list[tuple[object, ...]]) -> str:
    out = io.StringIO(newline="")
    writer = csv.writer(out, delimiter=",", lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def step_1a(out: Path) -> None:
    import thermogar_verified_equilibrium_test as fakes

    rows = [(f"Fe-{i:02d}", value) for i, value in enumerate(VALUES, start=1)]
    table = vs._parse_csv(_csv_bytes(rows))
    column = table["columns"].index("steel_mode")
    after_parse = [row[column] for row in table["rows"]]
    source = workspace.batch_table_dataframe(table)
    runner = fakes.FakeBatchRunner()
    with mock.patch.object(workspace.st, "progress", return_value=fakes.FakeProgress()):
        result = workspace.run_batch_calculations(source, fakes.FakeBatchBroker(), {}, runner)
    summary = result["Сводка"]
    by_index = {row["row_index"]: row["steel_mode"] for row in runner.rows}
    lines = []
    for position, label in enumerate(LABELS, start=1):
        record = summary.iloc[position - 1]
        lines.append(
            (
                label, after_parse[position - 1], by_index.get(position, "—"),
                record["Статус"], record["Ошибка"],
            )
        )
    digest = _write(
        out / "1a_steel_mode_chain.csv",
        _table(("значение", "после _steel_mode", "в runner", "Статус", "Ошибка"), lines),
    )
    for line in lines:
        print(" | ".join(str(item) for item in line))
    print("runner rows:", len(runner.rows), "calls:", runner.calls, "sha256:", digest)


def _app(names: tuple[str, ...]):
    import app_extract

    namespace, _taken = app_extract.load(names)
    return namespace


def step_1v(out: Path) -> None:
    app = _app(("phase_reference_dataframe", "load_database"))
    words = {"disordered": re.compile(r"\bdisordered\b", re.I), "ordered": re.compile(r"\bordered\b", re.I)}
    summary = []
    for key in ("ni", "al", "fe"):
        db, path = app["load_database"](key)
        frame = app["phase_reference_dataframe"](db, path, key)
        text = frame.to_csv(index=False, lineterminator="\n")
        digest = _write(out / f"1v_phase_reference_{key}.csv", text)
        original = frame["Оригинал из базы (англ.)"].astype(str)
        russian = frame["Описание по-русски"].astype(str)
        row = {
            "база": key,
            "фаз": len(frame),
            "описание_непусто": int((original.str.strip() != "").sum()),
            "слово_disordered": int(original.map(lambda t: bool(words["disordered"].search(t))).sum()),
            "слово_ordered": int(original.map(lambda t: bool(words["ordered"].search(t))).sum()),
            "подстрока_ordered": int(original.str.lower().str.contains("ordered", regex=False).sum()),
            "выход_Упорядоченная": int(russian.str.contains("Упорядоченная фаза.", regex=False).sum()),
            "выход_Разупорядоченная": int(russian.str.contains("Разупорядоченная фаза.", regex=False).sum()),
            "sha256": digest,
        }
        summary.append(row)
        print(json.dumps(row, ensure_ascii=False))
    header = tuple(summary[0])
    _write(out / "1v_summary.csv", _table(header, [tuple(row[h] for h in header) for row in summary]))


FE_POINT = {
    "balance": "FE",
    "composition_pct": {"C": 0.8},
    "database_key": "fe",
    "pressure_pa": 101325.0,
    "profile_key": "thermogar_patch",
    "requested_phases": [],
    "temperature_k": 700.0 + 273.15,
    "units": "wt",
}


def _fractions_csv(outcome: dict) -> str:
    return _table(("фаза", "доля"), [(phase, repr(value)) for phase, value in outcome["phase_fractions"]])


def step_1g(out: Path) -> None:
    app = _app(
        (
            "batch_engine_runner", "load_database", "prepare_calculation",
            "summarize_equilibrium", "aggregate_phase_fractions", "parse_composition",
        )
    )
    batch = {}
    for index, mode in enumerate(("stable", "metastable"), start=1):
        row = dict(FE_POINT, row_index=index, steel_mode=mode)
        outcome = app["batch_engine_runner"]([row], None)[0]
        batch[mode] = outcome
        text = _fractions_csv(outcome) if outcome["status"] == "success" else f"failure,{outcome['error']}\n"
        digest = _write(out / f"1g_batch_{mode}.csv", text)
        print(mode, outcome["status"], outcome["phase_fractions"], outcome["error"], digest)

    # Раздел «Расчёты», вкладка «Одна температура», ветка Fe.
    v = app["v"]
    db, _path = app["load_database"]("fe")
    components, conditions, _x, _w, phases = app["prepare_calculation"](
        db, "fe", app["parse_composition"]("C=0.8"), "wt", "FE", "metastable", None,
    )
    point = {v.N: 1.0, v.P: 101325.0, v.T: 700.0 + 273.15}
    point.update(conditions)
    eq = app["equilibrium"](db, components, phases, point, calc_opts={"pdens": 500})
    single = sorted(app["aggregate_phase_fractions"](eq).items())
    _write(out / "1g_single_metastable.csv", _table(("фаза", "доля"), [(p, repr(f)) for p, f in single]))
    batch_meta = dict(batch["metastable"]["phase_fractions"])
    names = sorted(set(batch_meta) | {p for p, _ in single})
    single_map = dict(single)
    lines = []
    worst = 0.0
    for name in names:
        a = batch_meta.get(name, 0.0)
        b = single_map.get(name, 0.0)
        worst = max(worst, abs(a - b))
        lines.append((name, repr(a), repr(b), repr(a - b)))
    _write(out / "1g_single_vs_batch_metastable.csv", _table(("фаза", "пакет", "одиночное", "разность"), lines))
    print("single metastable:", single)
    print("phases batch/single equal:", sorted(batch_meta) == [p for p, _ in single], "max |diff|:", repr(worst))


def step_1g_batch(out: Path, reference: Path) -> None:
    import thermogar_verified_equilibrium_test as fakes

    app = _app(("batch_engine_runner",))
    rows = [("Fe-пусто", ""), ("Fe-метастабильный", "метастабильный"), ("Fe-стабильный", "стабильный")]
    table = vs._parse_csv(_csv_bytes(rows))
    source = workspace.batch_table_dataframe(table)
    seen: list[dict] = []
    outcomes: list[dict] = []

    def runner(canonical_rows, progress):
        seen.extend(dict(row) for row in canonical_rows)
        outcomes.extend(app["batch_engine_runner"](canonical_rows, progress))
        return outcomes

    with mock.patch.object(workspace.st, "progress", return_value=fakes.FakeProgress()):
        result = workspace.run_batch_calculations(source, fakes.FakeBatchBroker(), {}, runner)
    lines = []
    for (label, _value), row, outcome in zip(rows, seen, outcomes):
        expected_mode = "stable" if label.endswith("стабильный") and "мета" not in label else "metastable"
        text = _fractions_csv(outcome)
        _write(out / f"1g_batch_{label}.csv", text)
        ref = (reference / f"1g_batch_{expected_mode}.csv").read_bytes()
        same = text.encode("utf-8") == ref
        lines.append((label, row["steel_mode"], expected_mode, outcome["status"], same))
        print(label, row["steel_mode"], outcome["phase_fractions"], "bytes equal to DO", expected_mode, same)
    _write(out / "1g_batch_vs_do.csv", _table(("строка", "в runner", "эталон ДО", "статус", "побайтно"), lines))
    print(result["Сводка"][["Название", "Статус", "Ошибка"]].to_string())


def main() -> None:
    stage = sys.argv[1]
    out = ROOT / "results" / "wave19_a" / stage
    out.mkdir(parents=True, exist_ok=True)
    for step in sys.argv[2:]:
        print(f"=== {stage} {step}")
        if step == "1a":
            step_1a(out)
        elif step == "1v":
            step_1v(out)
        elif step == "1g":
            step_1g(out)
        elif step == "1g_batch":
            step_1g_batch(out, ROOT / "results" / "wave19_a" / "do")
        else:
            raise SystemExit(f"unknown step {step}")


if __name__ == "__main__":
    main()
