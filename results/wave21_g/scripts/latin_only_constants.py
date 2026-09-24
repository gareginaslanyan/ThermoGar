"""21-Г, шаг 1: латинские строки без кириллицы вне raise, ключей и служебных аргументов.

Печатает кандидатов для ручной сверки: строка из двух и более латинских слов
или со знаком «·», которая не стоит ключом словаря, индексом, в raise, в
assert и не передаётся именованным аргументом, кроме подписей Streamlit.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
APP = ROOT / "app"
CYR = re.compile(r"[А-Яа-яЁё]")
WORDS = re.compile(r"[A-Za-z]{2,}")
SCREEN_KEYWORDS = {"label", "help", "placeholder", "options", "body", "value", "caption", "title"}


def main() -> int:
    out = sys.stdout
    for path in sorted(APP.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        skip: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Raise, ast.Assert, ast.Subscript, ast.Import, ast.ImportFrom)):
                skip.update(id(sub) for sub in ast.walk(node))
            elif isinstance(node, ast.Dict):
                for key in node.keys:
                    if key is not None:
                        skip.add(id(key))
            elif isinstance(node, ast.keyword) and node.arg not in SCREEN_KEYWORDS:
                skip.update(id(sub) for sub in ast.walk(node.value))
            elif isinstance(node, ast.Compare):
                skip.update(id(sub) for sub in ast.walk(node))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                body = node.body
                if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
                    skip.add(id(body[0].value))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {
                "get", "pop", "setdefault", "startswith", "endswith", "split", "join", "replace",
                "encode", "decode", "format", "debug", "exception", "getLogger", "sub", "match",
                "search", "compile", "fullmatch", "findall", "strip", "lower", "upper",
            }:
                skip.update(id(sub) for sub in ast.walk(node))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in skip:
                continue
            text = node.value
            if CYR.search(text):
                continue
            if len(WORDS.findall(text)) < 2 and "·" not in text:
                continue
            if re.fullmatch(r"[\w.\-/\\]+", text):  # один идентификатор или путь
                continue
            flat = text.replace("\t", " ").replace("\n", "\n")[:200]
            out.write(f"{path.name}:{node.lineno}\t{flat}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
