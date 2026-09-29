"""Проверка 20-З: какие функции читают службы прогона как глобальные имена.

Имена служб прогона заданы списком (задание 20-З, ШАГ 2 г). Для каждой
функции и метода (def в любой вложенности) — имена из этого списка, которые
она читает как глобальные или объявляет global. Лямбды и включения
отдельными функциями не считаются; их чтения относятся к объемлющей def.

Вторая часть — переприсваивания после строки «SERVICES = RunServices(»:
связывания имён служб и имени SERVICES кодом верхнего уровня (присваивания,
в том числе с аннотацией и составные, for, with … as, except … as, import,
def, class; тела def/class не входят) и присваивания внутри функций, где имя
объявлено global. Строка — начало инструкции после конца инструкции SERVICES.

Только стандартная библиотека (ast, symtable).

    python -B -X utf8 results/wave20_z/scripts/proverka_sluzhb.py <файл.py> [вывод.txt [подпись файла]]
"""

from __future__ import annotations

import ast
import sys
import symtable
from pathlib import Path

NAMES = (
    "THERMOGAR_PATHS", "render_friendly_error", "log_error", "dataframe_to_excel",
    "load_database", "load_scheil", "scheil_available", "_SCHEIL_STATE",
    "FE_PROFILE_SHA256", "FE_PROFILE_RELATIVE_PATHS", "_DATABASE_SNAPSHOT_CACHE",
    "_DATABASE_SNAPSHOT_CACHE_LOCK", "_parse_database_snapshot",
    "_database_cache_get", "_database_cache_commit",
)
SERVICES = "SERVICES"
INLINE_SCOPES = {"lambda", "genexpr", "listcomp", "setcomp", "dictcomp"}


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


def target_names(target: ast.AST, line: int, out: list) -> None:
    if isinstance(target, ast.Name):
        out.append((line, target.id))
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            target_names(element, line, out)
    elif isinstance(target, ast.Starred):
        target_names(target.value, line, out)
    # атрибуты и индексы имён не связывают


def top_bindings(statements: list[ast.stmt], out: list) -> None:
    """(строка, имя) для связываний кодом верхнего уровня, без тел def/class."""
    for node in statements:
        line = node.lineno
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append((line, node.name))
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                target_names(target, line, out)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            target_names(node.target, line, out)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            target_names(node.target, line, out)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    target_names(item.optional_vars, line, out)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                out.append((line, (alias.asname or alias.name).split(".")[0]))
        elif isinstance(node, ast.Try):
            for handler in node.handlers:
                if handler.name:
                    out.append((line, handler.name))
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list):
                top_bindings(block, out)
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                top_bindings(handler.body, out)


def global_stores(tree: ast.Module, names: set[str], out: list) -> None:
    """(строка, имя) для присваиваний внутри функций именам, объявленным global."""
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        declared: set[str] = set()
        for node in ast.walk(func):
            if isinstance(node, ast.Global):
                declared |= set(node.names) & names
        if not declared:
            continue
        for node in ast.walk(func):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                if node.id in declared:
                    out.append((node.lineno, node.id))


def services_statement(tree: ast.Module) -> ast.stmt | None:
    found = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == SERVICES for t in node.targets)
    ]
    if len(found) > 1:
        raise SystemExit(f"присваиваний {SERVICES}: {len(found)}")
    return found[0] if found else None


def main() -> int:
    path = Path(sys.argv[1])
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, str(path))
    names = set(NAMES)
    rows: list = []
    walk(symtable.symtable(source, str(path), "exec"), "", names, rows)
    rows.sort()
    out = [
        f"файл: {sys.argv[3] if len(sys.argv) > 3 else path.as_posix()}",
        f"имён служб прогона: {len(NAMES)}",
        "имена: " + ", ".join(NAMES),
        f"функций, читающих их как глобальные или объявляющих global: {len(rows)}",
    ]
    out += [f"{line} | {full} | {', '.join(reads)}" for line, full, reads in rows]
    statement = services_statement(tree)
    if statement is None:
        out.append(f"строка {SERVICES}: нет")
    else:
        watched = names | {SERVICES}
        bindings: list = []
        top_bindings(tree.body, bindings)
        global_stores(tree, watched, bindings)
        after = sorted(
            (line, name) for line, name in bindings
            if name in watched and line > statement.end_lineno
        )
        out.append(f"строка {SERVICES}: :{statement.lineno}–:{statement.end_lineno}")
        out.append(f"переприсваиваний имён служб и {SERVICES} после неё: {len(after)}")
        out += [f"{line} | {name}" for line, name in after]
    text = "\n".join(out) + "\n"
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_bytes(text.encode("utf-8"))
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
