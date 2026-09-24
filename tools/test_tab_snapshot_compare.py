"""20-Б: сверка каталогов эталона (``tools/tab_snapshot_compare.py``).

Каталоги строятся во временной папке; приложение не запускается. Сверка
вызывается как в заданиях — отдельным процессом, отчёт читается из ``--otchet``.
Различие байтов, которое не объясняет ни одно правило (концы строк,
завершающий перевод строки), — «различаются», а не «равны с исключениями».
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("tab_snapshot_compare.py")

TIME_RULE = (
    r"re:\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|[+-]\d\d:\d\d) | * | метка времени | "
    "2026-09-23T15:03:46+03:00 / 2026-09-23T16:20:56+03:00"
)
PATH_RULE = (
    r"путь:\d{8}-\d{6}-[0-9a-f]{8} | */vygruzki/ThermoGar_error_* | код ошибки в имени | "
    "ThermoGar_error_20260923-155600-d0912443.json / ThermoGar_error_20260923-170515-46c236b9.json"
)


def make_side(root: Path, files: dict[str, bytes]) -> Path:
    """Каталог прогона: файлы случаев и ``sha256.txt`` каждого случая."""

    cases: dict[str, list[str]] = {}
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        case, name = rel.split("/", 1)
        cases.setdefault(case, []).append(f"{hashlib.sha256(data).hexdigest()}  {name}")
    for case, lines in cases.items():
        (root / case / "sha256.txt").write_bytes(("\n".join(sorted(lines, key=lambda s: s[66:])) + "\n").encode("utf-8"))
    return root


def run_compare(tmp_path: Path, a: dict[str, bytes], b: dict[str, bytes], rules: list[str] | None = None,
                spoil_b: bool = False):
    a_root = make_side(tmp_path / "A", a)
    b_root = make_side(tmp_path / "B", b)
    if spoil_b:
        listing = next(b_root.glob("*/sha256.txt"))
        data = listing.read_bytes()
        listing.write_bytes((b"1" if data[:1] == b"0" else b"0") + data[1:])  # первая цифра суммы
    command = [sys.executable, "-B", "-X", "utf8", str(SCRIPT), str(a_root), str(b_root),
               "--otchet", str(tmp_path / "otchet.txt")]
    if rules is not None:
        rules_path = tmp_path / "isklyucheniya.txt"
        rules_path.write_text("\n".join(["# тест"] + rules) + "\n", encoding="utf-8")
        command += ["--isklyucheniya", str(rules_path)]
    done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    report = (tmp_path / "otchet.txt").read_text(encoding="utf-8").splitlines()
    status = {}
    for line in report:
        parts = line.split(" | ")
        if len(parts) >= 2 and parts[0] in ("равны", "равны с исключениями", "различаются", "нет пары"):
            status[parts[1]] = line
    return done.returncode, status, report


def verdict(line: str) -> str:
    return line.split(" | ", 1)[0]


def test_same_files_equal(tmp_path):
    data = {"c1/meta.json": b'{"x": 1}\n', "c1/ekran/t001.csv": b"a,b\r\n1,2\r\n"}
    code, status, report = run_compare(tmp_path, data, dict(data))
    assert {verdict(line) for line in status.values()} == {"равны"}
    assert code == 0
    assert report[-1] == "ИТОГ: полное равенство"


def test_time_only_with_rule_equal_with_exceptions(tmp_path):
    a = {"c1/meta.json": b'{\n  "start": "2026-09-23T15:03:46+03:00"\n}\n'}
    b = {"c1/meta.json": b'{\n  "start": "2026-09-23T16:20:56+03:00"\n}\n'}
    code, status, report = run_compare(tmp_path, a, b, [TIME_RULE])
    assert verdict(status["c1/meta.json"]) == "равны с исключениями"
    assert status["c1/meta.json"].endswith("правила 1")
    assert code == 0
    assert report[-1] == "ИТОГ: полное равенство"


def test_crlf_against_lf_differ(tmp_path):
    a = {"c1/karkas.txt": b"one\r\ntwo\r\n"}
    b = {"c1/karkas.txt": b"one\ntwo\n"}
    code, status, report = run_compare(tmp_path, a, b)
    assert verdict(status["c1/karkas.txt"]) == "различаются"
    assert "концы строк" in status["c1/karkas.txt"]
    assert code == 1
    assert report[-1] == "ИТОГ: НЕ равны"


def test_crlf_against_lf_plus_time_differ(tmp_path):
    a = {"c1/meta.json": b'{\r\n  "start": "2026-09-23T15:03:46+03:00"\r\n}\r\n'}
    b = {"c1/meta.json": b'{\n  "start": "2026-09-23T16:20:56+03:00"\n}\n'}
    code, status, report = run_compare(tmp_path, a, b, [TIME_RULE])
    assert verdict(status["c1/meta.json"]) == "различаются"
    assert "концы строк" in status["c1/meta.json"]
    assert code == 1
    assert report[-1] == "ИТОГ: НЕ равны"


def test_missing_final_newline_differ(tmp_path):
    a = {"c1/karkas.txt": b"one\ntwo\n"}
    b = {"c1/karkas.txt": b"one\ntwo"}
    code, status, report = run_compare(tmp_path, a, b)
    assert verdict(status["c1/karkas.txt"]) == "различаются"
    assert "завершающий перевод строки" in status["c1/karkas.txt"]
    assert code == 1
    assert report[-1] == "ИТОГ: НЕ равны"


def test_changed_number_differ(tmp_path):
    a = {"c1/ekran/t001.csv": b"T,x\n1000,0.25\n", "c1/meta.json": b'"2026-09-23T15:03:46+03:00"\n'}
    b = {"c1/ekran/t001.csv": b"T,x\n1000,0.26\n", "c1/meta.json": b'"2026-09-23T16:20:56+03:00"\n'}
    code, status, report = run_compare(tmp_path, a, b, [TIME_RULE])
    assert verdict(status["c1/ekran/t001.csv"]) == "различаются"
    assert verdict(status["c1/meta.json"]) == "равны с исключениями"
    assert any("было: 1000,0.25 | стало: 1000,0.26" in line for line in report)
    assert code == 1
    assert report[-1] == "ИТОГ: НЕ равны"


def test_path_rule_pairs_files(tmp_path):
    body = b'{"error": "boom"}\n'
    a = {"c1/vygruzki/ThermoGar_error_20260923-155600-d0912443.json": body}
    b = {"c1/vygruzki/ThermoGar_error_20260923-170515-46c236b9.json": body}
    code, status, report = run_compare(tmp_path, a, b, [PATH_RULE])
    assert len(status) == 1
    (line,) = status.values()
    assert verdict(line) == "равны с исключениями"
    assert line.endswith("правила 1")
    assert code == 0
    assert report[-1] == "ИТОГ: полное равенство"


def test_broken_sha256_not_full_equality(tmp_path):
    data = {"c1/meta.json": b'{"x": 1}\n'}
    code, status, report = run_compare(tmp_path, data, dict(data), spoil_b=True)
    assert verdict(status["c1/meta.json"]) == "равны"
    assert any(line.startswith("целостность B нарушена") for line in report)
    assert code == 1
    assert report[-1] == "ИТОГ: НЕ равны"
