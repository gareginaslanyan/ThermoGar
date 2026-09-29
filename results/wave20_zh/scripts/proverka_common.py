"""Проверка 20-Ж: общие помощники головного сценария в app/thermogar_app_common.py.

1. Неопределённые глобальные имена (symtable). Для каждого файла — имена,
   которые код читает как глобальные: чтения на уровне модуля и неявно
   глобальные чтения во всех вложенных областях (функции, классы, лямбды,
   включения; декораторы и значения по умолчанию — в объемлющей области).
   Из-за «from __future__ import annotations» аннотации не компилируются и
   в symtable не попадают, поэтому имена из аннотаций (узлы ast.Name и
   строки-аннотации) собираются по AST отдельно. Имя считается определённым,
   если модуль его связывает (присваивание, def, class, import, for, with,
   except на уровне модуля), если оно встроенное (builtins) или атрибут
   модуля (__file__, __name__ и т. п.).
2. Скрытые обращения: вызовы globals, vars, locals, eval, exec, __import__
   и слова __main__, sys.modules в тексте файла.
3. Импорт нового модуля из корня дерева:
   python -B -X utf8 -c "import sys; sys.path.insert(0, 'app'); import thermogar_app_common as c; print(c.PROJECT_ROOT)"

Только стандартная библиотека (ast, builtins, subprocess, symtable).

    python -B -X utf8 results/wave20_zh/scripts/proverka_common.py [вывод.txt]
"""

from __future__ import annotations

import ast
import builtins
import subprocess
import sys
import symtable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILES = (
    ROOT / "app" / "thermogar_app_common.py",
    ROOT / "app" / "ThermoGar_app.py",
)
MODULE_ATTRIBUTES = {
    "__name__", "__file__", "__doc__", "__spec__", "__loader__",
    "__package__", "__builtins__", "__annotations__", "__cached__",
}
HIDDEN_CALLS = ("globals", "vars", "locals", "eval", "exec", "__import__")
HIDDEN_WORDS = ("__main__", "sys.modules")
IMPORT_CODE = (
    "import sys; sys.path.insert(0, 'app'); "
    "import thermogar_app_common as c; print(c.PROJECT_ROOT)"
)


def global_reads(table: symtable.SymbolTable, out: dict[str, int]) -> None:
    """Имена, которые область читает как глобальные, с первой строкой области."""
    top = table.get_type() == "module"
    for symbol in table.get_symbols():
        if not symbol.is_referenced():
            continue
        if top or symbol.is_global():
            out.setdefault(symbol.get_name(), table.get_lineno())
    for child in table.get_children():
        global_reads(child, out)


def module_bound(table: symtable.SymbolTable) -> set[str]:
    return {
        symbol.get_name()
        for symbol in table.get_symbols()
        if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()
    }


def annotation_names(tree: ast.Module) -> dict[str, int]:
    """Имена из аннотаций (в том числе строковых), с номером строки."""
    found: dict[str, int] = {}

    def collect(annotation: ast.expr | None) -> None:
        if annotation is None:
            return
        for node in ast.walk(annotation):
            if isinstance(node, ast.Name):
                found.setdefault(node.id, node.lineno)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                try:
                    inner = ast.parse(node.value, mode="eval")
                except SyntaxError:
                    continue
                for sub in ast.walk(inner):
                    if isinstance(sub, ast.Name):
                        found.setdefault(sub.id, node.lineno)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = node.args
            for arg in (
                arguments.posonlyargs + arguments.args + arguments.kwonlyargs
                + [a for a in (arguments.vararg, arguments.kwarg) if a is not None]
            ):
                collect(arg.annotation)
            collect(node.returns)
        elif isinstance(node, ast.AnnAssign):
            collect(node.annotation)
    return found


def enclosing_functions(tree: ast.Module) -> dict[int, str]:
    """Номер строки -> имя определения верхнего уровня, в которое она входит."""
    owner: dict[int, str] = {}
    for node in tree.body:
        name = getattr(node, "name", None)
        if name is None:
            continue
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        for line in range(start, node.end_lineno + 1):
            owner[line] = name
    return owner


def check_file(path: Path, out: list[str]) -> tuple[int, int]:
    source = path.read_text("utf-8")
    relative = path.relative_to(ROOT).as_posix()
    tree = ast.parse(source)
    table = symtable.symtable(source, relative, "exec")
    bound = module_bound(table)
    known = bound | set(dir(builtins)) | MODULE_ATTRIBUTES
    reads: dict[str, int] = {}
    global_reads(table, reads)
    annotations = annotation_names(tree)
    undefined = sorted(
        {name for name in reads if name not in known}
        | {name for name in annotations if name not in known}
    )
    out.append(f"== {relative}")
    out.append(f"строк: {source.count(chr(10))}")
    out.append(f"имён, связанных модулем: {len(bound)}")
    out.append(f"глобальных чтений (symtable): {len(reads)}")
    out.append(f"имён в аннотациях (AST): {len(annotations)}")
    out.append(f"неопределённых глобальных имён: {len(undefined)}")
    for name in undefined:
        line = reads.get(name, annotations.get(name))
        out.append(f"  {name} (строка {line})")

    owner = enclosing_functions(tree)
    hidden: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in HIDDEN_CALLS
        ):
            hidden.append(
                f"  {node.lineno} | {owner.get(node.lineno, '<модуль>')} | {node.func.id}()"
            )
    for number, line in enumerate(source.split("\n"), start=1):
        for word in HIDDEN_WORDS:
            if word in line:
                hidden.append(
                    f"  {number} | {owner.get(number, '<модуль>')} | слово {word}"
                )
    out.append(
        "скрытых обращений (вызовы " + ", ".join(HIDDEN_CALLS)
        + "; слова " + ", ".join(HIDDEN_WORDS) + f"): {len(hidden)}"
    )
    out.extend(hidden)
    out.append("")
    return len(undefined), len(hidden)


def main() -> int:
    out: list[str] = []
    results = {path.name: check_file(path, out) for path in FILES}

    completed = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", "-c", IMPORT_CODE],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    printed = completed.stdout.strip()
    out.append("== импорт из корня дерева")
    out.append(f'python -B -X utf8 -c "{IMPORT_CODE}"')
    out.append(f"код выхода: {completed.returncode}")
    out.append(f"вывод: {printed}")
    if completed.stderr.strip():
        out.append("stderr:")
        out.extend("  " + line for line in completed.stderr.strip().splitlines())
    out.append("")

    common_undefined, common_hidden = results["thermogar_app_common.py"]
    app_undefined, app_hidden = results["ThermoGar_app.py"]
    import_ok = completed.returncode == 0 and printed == str(ROOT)
    passed = common_undefined == 0 and app_undefined == 0 and common_hidden == 0 and import_ok
    out.append(
        "ИТОГ: "
        + ("PASS" if passed else "FAIL")
        + f" — неопределённых: модуль {common_undefined}, головной сценарий {app_undefined};"
        + f" скрытых обращений: модуль {common_hidden}, головной сценарий {app_hidden};"
        + f" импорт: код {completed.returncode}, путь {'совпал' if import_ok else 'НЕ совпал'}"
    )
    text = "\n".join(out) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8", newline="\n")
    sys.stdout.write(text)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
