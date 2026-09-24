"""20-А (BL-57, шаг 0): сверка двух каталогов вывода ``tools/tab_snapshot.py``.

Сравнивает файл за файлом. По каждому файлу печатает «равны», «равны с
исключениями», «различаются» или «нет пары», затем итог. Код выхода 0 —
только при полном равенстве (с учётом исключений) и целых ``sha256.txt``.

    python -B -X utf8 tools/tab_snapshot_compare.py <каталог A> <каталог B> \\
        [--isklyucheniya results/wave20_a/isklyucheniya.txt] [--otchet <файл>]

``sha256.txt`` каждого случая попарно не сравнивается: он проверяется на
целостность с каждой стороны (суммы сходятся с файлами рядом), а сами файлы
сравниваются по содержимому.

Файл исключений — строки ``правило | где | почему | пример различия``;
строки на ``#`` и пустые пропускаются. Правило ``re:<регулярное выражение>``:
в каждой строке текстового файла совпадения заменяются на ``⟨исключено⟩`` с
обеих сторон перед сравнением — то есть исключается поле или часть строки, а
не файл. Правило ``путь:<регулярное выражение>`` делает то же с путём файла
(поле в имени, например метка времени): файлы ставятся в пару по пути после
замены, а их содержимое сравнивается как обычно. ``где`` — шаблоны пути
относительно каталога (``fnmatch``, через запятую), например ``*/meta.json``.
"""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

MARK = "⟨исключено⟩"


@dataclass(frozen=True)
class Rule:
    number: int
    pattern: re.Pattern[str]
    where: tuple[str, ...]
    text: str
    on_path: bool = False

    def applies(self, rel: str) -> bool:
        return any(fnmatch.fnmatchcase(rel, pattern) for pattern in self.where)


def load_rules(path: Path | None) -> list[Rule]:
    if path is None:
        return []
    rules: list[Rule] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = [part.strip() for part in stripped.split(" | ")]
        if len(parts) < 4 or not parts[0].startswith(("re:", "путь:")):
            raise SystemExit(f"строка исключений не разобрана: {line}")
        on_path = parts[0].startswith("путь:")
        pattern = re.compile(parts[0].split(":", 1)[1])
        where = tuple(item.strip() for item in parts[1].split(",") if item.strip())
        rules.append(Rule(len(rules) + 1, pattern, where, stripped, on_path))
    return rules


def files_of(root: Path) -> dict[str, Path]:
    return {path.relative_to(root).as_posix(): path for path in sorted(root.rglob("*")) if path.is_file()}


def integrity(root: Path, files: dict[str, Path]) -> list[str]:
    """Сходятся ли sha256.txt каждого случая с файлами рядом."""

    problems: list[str] = []
    cases = sorted({rel.split("/", 1)[0] for rel in files if "/" in rel})
    for case in cases:
        listing = root / case / "sha256.txt"
        own = {rel[len(case) + 1:] for rel in files if rel.startswith(case + "/")} - {"sha256.txt"}
        if not listing.is_file():
            problems.append(f"{case}: нет sha256.txt")
            continue
        listed: dict[str, str] = {}
        for line in listing.read_text(encoding="utf-8").splitlines():
            digest, _sep, name = line.partition("  ")
            listed[name] = digest
        for name in sorted(own | set(listed)):
            if name not in listed:
                problems.append(f"{case}/{name}: нет в sha256.txt")
            elif name not in own:
                problems.append(f"{case}/{name}: в sha256.txt, но файла нет")
            elif hashlib.sha256((root / case / name).read_bytes()).hexdigest() != listed[name]:
                problems.append(f"{case}/{name}: сумма не сходится с sha256.txt")
    return problems


def as_text(data: bytes) -> str | None:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def normalized(lines: list[str], rules: list[Rule]) -> tuple[list[str], set[int]]:
    used: set[int] = set()
    out: list[str] = []
    for line in lines:
        for rule in rules:
            line, count = rule.pattern.subn(MARK, line)
            if count:
                used.add(rule.number)
        out.append(line)
    return out, used


def shorten(text: str, limit: int = 400) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def pair_key(rel: str, rules: list[Rule]) -> str:
    for rule in rules:
        if rule.on_path and rule.applies(rel):
            rel = rule.pattern.sub(MARK, rel)
    return rel


def compare(a_root: Path, b_root: Path, rules: list[Rule], limit: int) -> tuple[list[str], dict[str, int]]:
    a_real = files_of(a_root)
    b_real = files_of(b_root)
    report: list[str] = []
    counts = {"равны": 0, "равны с исключениями": 0, "различаются": 0, "нет пары": 0}
    for side, root, files in (("A", a_root, a_real), ("B", b_root, b_real)):
        problems = integrity(root, files)
        counts[f"целостность {side}"] = len(problems)
        for problem in problems:
            report.append(f"целостность {side} нарушена | {problem}")
    a_files: dict[str, Path] = {}
    b_files: dict[str, Path] = {}
    for real, paired in ((a_real, a_files), (b_real, b_files)):
        for rel, path in real.items():
            key = pair_key(rel, rules)
            if key in paired:
                key = rel  # замена пути дала бы два файла в одну пару: ставим по настоящему имени
            paired[key] = path
    names = sorted((set(a_files) | set(b_files)) - {rel for rel in set(a_files) | set(b_files)
                                                     if rel.endswith("/sha256.txt") or rel == "sha256.txt"})
    pairs_renamed = {rel for rel in names if MARK in rel}
    for rel in names:
        if rel not in a_files or rel not in b_files:
            counts["нет пары"] += 1
            report.append(f"нет пары | {rel} | есть только в {'A' if rel in a_files else 'B'}")
            continue
        a_data = a_files[rel].read_bytes()
        b_data = b_files[rel].read_bytes()
        path_rules = {rule.number for rule in rules
                      if rule.on_path and rule.applies(a_files[rel].relative_to(a_root).as_posix())}
        if a_data == b_data:
            if rel in pairs_renamed:
                counts["равны с исключениями"] += 1
                report.append(f"равны с исключениями | {rel} | правила {','.join(map(str, sorted(path_rules)))}")
            else:
                counts["равны"] += 1
                report.append(f"равны | {rel}")
            continue
        a_text = as_text(a_data)
        b_text = as_text(b_data)
        if a_text is None or b_text is None:
            counts["различаются"] += 1
            report.append(f"различаются | {rel} | двоичный, байт {len(a_data)} / {len(b_data)}")
            continue
        active = [rule for rule in rules if not rule.on_path and rule.applies(rel)]
        a_lines, used_a = normalized(a_text.splitlines(), active)
        b_lines, used_b = normalized(b_text.splitlines(), active)
        if a_lines == b_lines:
            counts["равны с исключениями"] += 1
            used = ",".join(str(n) for n in sorted(used_a | used_b | path_rules))
            report.append(f"равны с исключениями | {rel} | правила {used}")
            continue
        counts["различаются"] += 1
        report.append(f"различаются | {rel}")
        shown = 0
        matcher = difflib.SequenceMatcher(a=a_lines, b=b_lines, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            for offset in range(max(i2 - i1, j2 - j1)):
                if shown >= limit:
                    break
                old = a_lines[i1 + offset] if i1 + offset < i2 else "—"
                new = b_lines[j1 + offset] if j1 + offset < j2 else "—"
                report.append(f"    строка {i1 + offset + 1} | было: {shorten(old)} | стало: {shorten(new)}")
                shown += 1
        if shown >= limit:
            report.append(f"    … показано {limit} различающихся строк")
    return report, counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("a", type=Path)
    parser.add_argument("b", type=Path)
    parser.add_argument("--isklyucheniya", type=Path, default=None)
    parser.add_argument("--otchet", type=Path, default=None)
    parser.add_argument("--strok", type=int, default=20, help="сколько различающихся строк показывать на файл")
    args = parser.parse_args()
    rules = load_rules(args.isklyucheniya)
    report, counts = compare(args.a.resolve(), args.b.resolve(), rules, args.strok)
    total = counts["равны"] + counts["равны с исключениями"] + counts["различаются"] + counts["нет пары"]
    ok = (counts["различаются"] == 0 and counts["нет пары"] == 0
          and counts["целостность A"] == 0 and counts["целостность B"] == 0)
    header = [
        f"A: {args.a}",
        f"B: {args.b}",
        f"исключения: {args.isklyucheniya if args.isklyucheniya else 'нет'} (правил {len(rules)})",
        "",
    ]
    footer = [
        "",
        f"ИТОГ: файлов {total}; равны {counts['равны']}; равны с исключениями {counts['равны с исключениями']}; "
        f"различаются {counts['различаются']}; нет пары {counts['нет пары']}; "
        f"нарушений целостности A {counts['целостность A']}, B {counts['целостность B']}",
        "ИТОГ: " + ("полное равенство" if ok else "НЕ равны"),
    ]
    text = "\n".join(header + report + footer) + "\n"
    if args.otchet is not None:
        args.otchet.parent.mkdir(parents=True, exist_ok=True)
        args.otchet.write_text(text, encoding="utf-8")
    sys.stdout.write("\n".join(header + [line for line in report if not line.startswith("равны")] + footer) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
