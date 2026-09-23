"""Сравнение справочника фаз ДО/ПОСЛЕ (19-В2, шаг 5) -> sravnenie.csv.

Ожидаемое собрано независимо от модуля программы: ключи — из
``results/wave19_v/razmetka_ispolnitel.csv``, фразы — из списка задания
(``tools/test_phase_description_stub_keys.py``: NEW_PHRASES) и литералов
``translate_phase_description`` (копия списка в ``gen_stub_keys.py``).

Запуск (из корня дерева):
    .venv-windows/Scripts/python.exe -B -X utf8 results/wave19_v2/scripts/compare.py
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

import gen_stub_keys  # noqa: E402

BASES = ("ni", "al", "fe")
COLUMN = "Описание по-русски"
EXPECT_ROWS = {"ni": 99, "al": 195, "fe": 132}
EXPECT_CHANGED = {"ni": 26, "al": 27, "fe": 41}
EXPECT_STUB_LEFT = {"ni": 2, "al": 0, "fe": 3}


def _read(path: Path) -> tuple[list[str], list[str], list[dict[str, str]]]:
    data = path.read_bytes().decode("utf-8")
    lines = data.split("\n")
    assert lines[-1] == "", path
    rows = list(csv.DictReader(io.StringIO(data, newline="")))
    return lines[1:-1], list(rows[0]), rows


def main() -> None:
    phrases = dict(gen_stub_keys.PHRASES)
    with gen_stub_keys.MARKUP.open(encoding="utf-8", newline="") as handle:
        markup = {(r["faza"], r["opisanie_en"]): r["klyuchi"].split() for r in csv.DictReader(handle)}
    out_rows = []
    problems = []
    report = []
    total_same = 0
    for base in BASES:
        before_lines, before_header, before = _read(HERE.parent / "do" / f"phase_reference_{base}.csv")
        after_lines, after_header, after = _read(HERE.parent / "posle" / f"phase_reference_{base}.csv")
        if before_header != after_header:
            problems.append(f"{base}: header differs")
        if not (len(before) == len(after) == EXPECT_ROWS[base] == len(before_lines) == len(after_lines)):
            problems.append(f"{base}: rows {len(before)}/{len(after)}")
        changed = same = stub_left = 0
        for line_b, line_a, row_b, row_a in zip(before_lines, after_lines, before, after):
            if row_a[COLUMN] == gen_stub_keys.STUB:
                stub_left += 1
            if line_b == line_a:
                same += 1
                continue
            changed += 1
            diff_cols = [c for c in before_header if row_b[c] != row_a[c]]
            if diff_cols != [COLUMN]:
                problems.append(f"{base} {row_b['Код фазы']}: columns {diff_cols}")
            if row_b[COLUMN] != gen_stub_keys.STUB:
                problems.append(f"{base} {row_b['Код фазы']}: before is not stub")
            keys = markup.get((row_b["Код фазы"], row_b["Оригинал из базы (англ.)"].strip()))
            expected = " ".join(phrases[k] for k in keys) if keys else None
            if row_a[COLUMN] != expected:
                problems.append(f"{base} {row_b['Код фазы']}: after {row_a[COLUMN]!r} != {expected!r}")
            out_rows.append((base, row_b["Код фазы"], row_b[COLUMN], row_a[COLUMN]))
        total_same += same
        if changed != EXPECT_CHANGED[base]:
            problems.append(f"{base}: changed {changed} != {EXPECT_CHANGED[base]}")
        if stub_left != EXPECT_STUB_LEFT[base]:
            problems.append(f"{base}: stub left {stub_left} != {EXPECT_STUB_LEFT[base]}")
        report.append(f"{base}: rows {len(after)}, changed {changed}, same {same}, stub left {stub_left}")
    report.append(f"total: changed {len(out_rows)}, same {total_same}")
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(("baza", "faza", "bylo", "stalo"))
    writer.writerows(out_rows)
    (HERE.parent / "sravnenie.csv").write_bytes(buffer.getvalue().encode("utf-8"))
    report.append("problems: " + ("none" if not problems else str(len(problems))))
    report += problems
    text = "\n".join(report) + "\n"
    (HERE.parent / "sravnenie_itog.txt").write_bytes(text.encode("utf-8"))
    print(text, end="")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
