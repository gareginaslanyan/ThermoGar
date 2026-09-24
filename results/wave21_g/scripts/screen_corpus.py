"""21-Г: корпус строк app/*.py для сверки «уже есть на экране».

Строки берутся из литералов кода (части f-строк склеены, подстановки — в
фигурных скобках, как в коде). Из корпуса исключены функции и константы,
которые из приложения не вызываются и не читаются (список — в отчёте 21-Г),
и строки из списка EXPORT_ONLY: они уходят только в выгрузку.
"""
from __future__ import annotations

import ast
import pathlib
from functools import lru_cache

ROOT = pathlib.Path(__file__).resolve().parents[3]
APP = ROOT / "app"

# Недостижимо: функция нигде не вызывается или константа нигде не читается.
UNREACHABLE: dict[str, set[str]] = {
    "thermogar_properties.py": {"render_elastic_section", "render_strengthening_section", "_elastic_figure"},
    "thermogar_release_ui.py": {"render_result_evidence", "verified_batch_file_uploader"},
    "thermogar_stage14.py": {"provenance_table"},
}
UNREACHABLE_CONSTANTS: dict[str, set[str]] = {
    "thermogar_release_policy.py": {"EXPORT_BLOCK_REASON", "IMPORT_BLOCK_REASON", "CALCULATION_BLOCK_REASON"},
    "ThermoGar_app.py": {"USER_GUIDE_MD"},  # только файл для скачивания
}


def _render(node: ast.AST) -> str:
    if isinstance(node, ast.Constant):
        return str(node.value)
    parts = []
    for value in node.values:
        if isinstance(value, ast.Constant):
            parts.append(str(value.value))
            continue
        text = "{" + ast.unparse(value.value)
        if value.conversion != -1:
            text += "!" + chr(value.conversion)
        if value.format_spec is not None:
            text += ":" + _render(value.format_spec)
        parts.append(text + "}")
    return "".join(parts)


@lru_cache(maxsize=None)
def corpus() -> tuple[tuple[str, int, str], ...]:
    items: list[tuple[str, int, str]] = []
    for path in sorted(APP.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        skip_funcs = UNREACHABLE.get(path.name, set())
        skip_consts = UNREACHABLE_CONSTANTS.get(path.name, set())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.JoinedStr) or (isinstance(node, ast.Constant) and isinstance(node.value, str))):
                continue
            if isinstance(parents.get(node), ast.JoinedStr) or isinstance(parents.get(node), ast.FormattedValue):
                continue
            holder = parents.get(node)
            if isinstance(holder, ast.Expr):  # докстрока или строка-комментарий
                continue
            owner = node
            dead = False
            while owner in parents:
                owner = parents[owner]
                if isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)) and owner.name in skip_funcs:
                    dead = True
                if isinstance(owner, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id in skip_consts for t in owner.targets
                ):
                    dead = True
                if isinstance(owner, ast.AnnAssign) and isinstance(owner.target, ast.Name) and owner.target.id in skip_consts:
                    dead = True
            if dead:
                continue
            items.append((path.name, node.lineno, _render(node)))
    return tuple(items)


def text_at(file: str, line: int) -> str:
    for name, lineno, text in corpus():
        if name == file and lineno == line:
            return text
    raise KeyError(f"{file}:{line}")


def find(phrase: str) -> list[str]:
    return [f"{name}:{lineno}" for name, lineno, text in corpus() if phrase in text]
