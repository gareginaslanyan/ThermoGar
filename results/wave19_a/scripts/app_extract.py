"""Функции ``app/ThermoGar_app.py`` без запуска Streamlit (19-А).

Путь тот же, что в ``tools/test_equilibrium_solidus_fallback.py`` (фикстура
``app``): разбор исходника ``ast``, импорты верхнего уровня плюс нужные
определения, ``exec`` в отдельном пространстве имён. Отличие одно: нужные
имена дополняются по замыканию — в набор входят определения верхнего уровня,
на которые ссылаются уже взятые.
"""
from __future__ import annotations

import ast
import sys
import warnings
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
APP_PATH = ROOT / "app" / "ThermoGar_app.py"
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))


def _defined(node: ast.stmt) -> set[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, ast.Assign):
        names: set[str] = set()
        for target in node.targets:
            for sub in ast.walk(target):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
        return names
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    return set()


def _free_names(node: ast.stmt) -> set[str]:
    """Имена, которые узел читает и не связывает сам (параметры, локальные)."""
    loads: set[str] = set()
    local: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            (loads if isinstance(sub.ctx, ast.Load) else local).add(sub.id)
        elif isinstance(sub, ast.arg):
            local.add(sub.arg)
        elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and sub is not node:
            local.add(sub.name)
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return loads
    return loads - local


def load(names: tuple[str, ...]) -> tuple[dict[str, Any], list[str]]:
    tree = ast.parse(APP_PATH.read_text("utf-8"))
    header: list[ast.stmt] = []
    candidates: list[tuple[int, ast.stmt, set[str]]] = []
    for index, node in enumerate(tree.body):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            header.append(node)
            continue
        defined = _defined(node)
        if defined:
            candidates.append((index, node, defined))
    wanted = set(names)
    chosen: dict[int, ast.stmt] = {}
    changed = True
    while changed:
        changed = False
        for index, node, defined in candidates:
            if index in chosen or not (defined & wanted):
                continue
            chosen[index] = node
            changed = True
            wanted |= _free_names(node)
    body = header + [chosen[index] for index in sorted(chosen)]
    namespace: dict[str, Any] = {"__file__": str(APP_PATH), "__name__": "thermogar_app_extract"}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        exec(compile(ast.Module(body=body, type_ignores=[]), str(APP_PATH), "exec"), namespace)
    missing = set(names) - set(namespace)
    if missing:
        raise RuntimeError(f"missing {sorted(missing)}")
    taken = sorted({name for index in chosen for name in _defined(chosen[index])})
    return namespace, taken
