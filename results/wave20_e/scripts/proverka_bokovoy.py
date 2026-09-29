"""Проверка 20-Е: какие функции читают имена боковой панели как глобальные.

Имена боковой панели — всё, что связывает код верхнего уровня раздела от
«# Боковая панель: общие параметры» до «# Вкладки текущей SWR-сборки»:
присваивания (в том числе с аннотацией и составные), for, with … as,
except … as, import. Тела функций и классов, лямбды и включения не входят.

Для каждой функции и метода (def в любой вложенности) — имена из этого
набора, которые она читает как глобальные или объявляет global. Лямбды и
включения отдельными функциями не считаются; их чтения относятся к
объемлющей def.

Только стандартная библиотека (ast, symtable).

    python -B -X utf8 results/wave20_e/scripts/proverka_bokovoy.py <файл.py> [вывод.txt [подпись файла]]
"""

from __future__ import annotations

import ast
import sys
import symtable
from pathlib import Path

START = "# Боковая панель: общие параметры"
END = "# Вкладки текущей SWR-сборки"
INLINE_SCOPES = {"lambda", "genexpr", "listcomp", "setcomp", "dictcomp"}


def section_bounds(lines: list[str]) -> tuple[int, int]:
    starts = [i + 1 for i, line in enumerate(lines) if line == START]
    ends = [i + 1 for i, line in enumerate(lines) if line == END]
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise SystemExit(f"границы раздела не найдены: {starts} {ends}")
    return starts[0], ends[0]


def target_names(target: ast.AST, out: set[str]) -> None:
    if isinstance(target, ast.Name):
        out.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            target_names(element, out)
    elif isinstance(target, ast.Starred):
        target_names(target.value, out)
    # атрибуты и индексы имён не связывают


def bound_names(statements: list[ast.stmt], out: set[str]) -> None:
    """Имена, связанные кодом верхнего уровня, без тел def/class."""
    for node in statements:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                target_names(target, out)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            target_names(node.target, out)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            target_names(node.target, out)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    target_names(item.optional_vars, out)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                out.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.name:
                    out.add(handler.name)
        # вложенные блоки инструкций: if/for/while/with/try
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list):
                bound_names(block, out)
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                bound_names(handler.body, out)


def section_names(tree: ast.Module, first: int, last: int) -> set[str]:
    top = [node for node in tree.body if first <= node.lineno <= last]
    names: set[str] = set()
    bound_names(top, names)
    return names


def table_reads(table: symtable.SymbolTable, names: set[str]) -> set[str]:
    found: set[str] = set()
    for symbol in table.get_symbols():
        name = symbol.get_name()
        if name not in names:
            continue
        if symbol.is_declared_global() or (symbol.is_global() and symbol.is_referenced()):
            found.add(name)
    for child in table.get_children():
        if child.get_type() == "function" and child.get_name() in INLINE_SCOPES:
            found |= table_reads(child, names)
    return found


def walk(table: symtable.SymbolTable, prefix: str, names: set[str], rows: list) -> None:
    for child in table.get_children():
        kind = child.get_type()
        if kind == "function" and child.get_name() in INLINE_SCOPES:
            continue
        full = f"{prefix}{child.get_name()}"
        if kind == "function":
            reads = table_reads(child, names)
            if reads:
                rows.append((child.get_lineno(), full, sorted(reads)))
        walk(child, full + ".", names, rows)


def main() -> int:
    path = Path(sys.argv[1])
    source = path.read_text(encoding="utf-8")
    lines = source.split("\n")
    first, last = section_bounds(lines)
    tree = ast.parse(source, str(path))
    names = section_names(tree, first, last)
    rows: list = []
    walk(symtable.symtable(source, str(path), "exec"), "", names, rows)
    rows.sort()
    out = [
        f"файл: {sys.argv[3] if len(sys.argv) > 3 else path.as_posix()}",
        f"раздел боковой панели: :{first}–:{last}",
        f"имён боковой панели: {len(names)}",
        "имена: " + ", ".join(sorted(names)),
        f"функций, читающих их как глобальные или объявляющих global: {len(rows)}",
    ]
    out += [f"{line} | {full} | {', '.join(reads)}" for line, full, reads in rows]
    text = "\n".join(out) + "\n"
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_bytes(text.encode("utf-8"))
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
