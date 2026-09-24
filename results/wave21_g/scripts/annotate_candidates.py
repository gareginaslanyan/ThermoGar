"""21-Г, шаг 1: к каждому кандидату — объемлющая функция и вид места.

Читает вывод extract_candidates.py (TSV) со стандартного ввода и дописывает
два столбца: имя объемлющей функции и вид (raise, вызов st.*, присваивание).
"""
from __future__ import annotations

import ast
import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
APP = ROOT / "app"


def index(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return tree, parents


def describe(tree, parents, line: int) -> tuple[str, str]:
    best = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.Constant, ast.JoinedStr)) and getattr(node, "lineno", None) == line:
            best = node
            break
    if best is None:
        return "?", "?"
    kind = ""
    func = "<модуль>"
    node = best
    while node in parents:
        node = parents[node]
        if not kind:
            if isinstance(node, ast.Raise):
                kind = "raise " + (ast.unparse(node.exc.func) if isinstance(node.exc, ast.Call) else "")
            elif isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                if name.startswith(("st.", "status.", "container.", "column", "tab")) or "." in name and name.split(".")[-1] in {
                    "error", "warning", "info", "success", "caption", "markdown", "write", "button",
                    "download_button", "metric", "expander", "tabs", "subheader", "header"}:
                    kind = "вызов " + name
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                target = node.targets[0] if isinstance(node, ast.Assign) else node.target
                kind = "присваивание " + ast.unparse(target)[:40]
            elif isinstance(node, ast.Return):
                kind = "return"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func = node.name
            break
    return func, kind or "?"


def main() -> int:
    cache = {}
    reader = csv.reader(sys.stdin, delimiter="\t")
    writer = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    header = next(reader)
    writer.writerow(header + ["function", "kind"])
    for row in reader:
        name, line = row[0], int(row[1])
        if name not in cache:
            cache[name] = index(APP / name)
        tree, parents = cache[name]
        writer.writerow(row + list(describe(tree, parents, line)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
