"""Проверка шага вкладки (BL-57, разрез головного сценария; 20-К и следующие).

Вкладка «with <переменная вкладки>:» головного сценария переносится в функцию
нового модуля: тело — без правок, имена головного сценария — прологом
«имя = sidebar.поле» / «имя = services.поле», в головном сценарии вместо тела —
вызов функции. Скрипт сверяет:

1. Тело: операторы функции после строки документации и пролога — байт в байт
   текст тела «with <переменная вкладки>:» файла до правки и равны ему по
   ast.dump.
2. Пролог: присваивания «имя = sidebar.поле» или «имя = services.поле»; в файле
   до правки SIDEBAR = SidebarContext(…) или SERVICES = RunServices(…) передаёт
   «поле=имя» — тот же объект; после SIDEBAR и SERVICES имя на уровне модуля
   не переприсваивается и нигде не объявлено global; каждое имя пролога тело
   читает.
3. Имена, которые тело читает и само не связывает: имена пролога и импорты
   нового модуля (модуль и исходное имя — те же, что в импорте файла до
   правки); прочих 0.
4. Имена, которые тело связывает, головной сценарий после правки не читает.
5. symtable: неопределённые глобальные имена нового модуля и головного
   сценария после правки (аннотации — по AST, из-за
   «from __future__ import annotations» в symtable их нет); скрытые обращения
   в новом модуле (вызовы globals, vars, locals, eval, exec, __import__; слова
   __main__, sys.modules).
6. Головной сценарий по AST: узлы верхнего уровня и операторы импорта до и
   после; убранные и добавленные импортом имена; откат — убрать импорт из
   нового модуля, вернуть тело вкладки из файла до правки, в обоих файлах не
   считать убранных имён — все узлы равны файлу до правки по ast.dump.
7. Импорт нового модуля из корня дерева.

Только стандартная библиотека (ast, builtins, subprocess, symtable).
Запуск из корня дерева:

    python -B -X utf8 results/wave20_k/scripts/proverka_vkladki.py \
        <блоб до правки> <головной сценарий> <модуль вкладки> <функция> <переменная вкладки>

Вывод — в stdout байтами UTF-8 с LF (для файла — перенаправление «>»).
Код выхода 0 — PASS, 1 — FAIL.
"""

from __future__ import annotations

import ast
import builtins
import subprocess
import sys
import symtable
from pathlib import Path

ROOT = Path.cwd()
MODULE_ATTRIBUTES = {
    "__name__", "__file__", "__doc__", "__spec__", "__loader__",
    "__package__", "__builtins__", "__annotations__", "__cached__",
}
HIDDEN_CALLS = ("globals", "vars", "locals", "eval", "exec", "__import__")
HIDDEN_WORDS = ("__main__", "sys.modules")
# Параметр функции вкладки -> (имя объекта в головном сценарии, его класс).
CONTAINERS = {
    "sidebar": ("SIDEBAR", "SidebarContext"),
    "services": ("SERVICES", "RunServices"),
}
SCOPE_NODES = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
)


def git_blob(blob: str) -> bytes:
    completed = subprocess.run(
        ["git", "cat-file", "blob", blob], cwd=ROOT, capture_output=True, check=True
    )
    return completed.stdout


def source_lines(source: str, first: int, last: int) -> str:
    """Строки first..last (с 1, включительно) с переводами строк."""
    return "".join(source.splitlines(keepends=True)[first - 1:last])


def tab_with(tree: ast.Module, tab_var: str) -> list[ast.With]:
    return [
        node for node in tree.body
        if isinstance(node, ast.With)
        and len(node.items) == 1
        and isinstance(node.items[0].context_expr, ast.Name)
        and node.items[0].context_expr.id == tab_var
        and node.items[0].optional_vars is None
    ]


def names(nodes: list[ast.stmt], context: type) -> set[str]:
    return {
        node.id
        for statement in nodes
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, context)
    }


def import_map(tree: ast.Module) -> dict[str, tuple[str, str]]:
    """Имя, связанное импортом верхнего уровня -> (модуль, исходное имя)."""
    found: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                found[alias.asname or alias.name] = (node.module or "", alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                found[bound] = (alias.name if alias.asname else bound, "")
    return found


def module_level_stores(tree: ast.Module, after_line: int) -> dict[str, list[int]]:
    """Связывания имён на уровне модуля (без тел def/class/lambda) после строки."""
    found: dict[str, list[int]] = {}

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if child.lineno > after_line:
                    found.setdefault(child.name, []).append(child.lineno)
                continue
            if isinstance(child, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                continue
            if isinstance(child, (ast.Import, ast.ImportFrom)) and child.lineno > after_line:
                for alias in child.names:
                    found.setdefault(alias.asname or alias.name.split(".")[0], []).append(child.lineno)
            if (
                isinstance(child, ast.Name)
                and isinstance(child.ctx, (ast.Store, ast.Del))
                and child.lineno > after_line
            ):
                found.setdefault(child.id, []).append(child.lineno)
            if isinstance(child, ast.ExceptHandler) and child.name and child.lineno > after_line:
                found.setdefault(child.name, []).append(child.lineno)
            visit(child)

    visit(tree)
    return found


def global_declarations(tree: ast.Module) -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                found.setdefault(name, []).append(node.lineno)
    return found


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


def undefined_globals(source: str, filename: str) -> tuple[list[str], int, int]:
    tree = ast.parse(source)
    table = symtable.symtable(source, filename, "exec")
    known = module_bound(table) | set(dir(builtins)) | MODULE_ATTRIBUTES
    reads: dict[str, int] = {}
    global_reads(table, reads)
    annotations = annotation_names(tree)
    undefined = sorted(
        {name for name in reads if name not in known}
        | {name for name in annotations if name not in known}
    )
    return [
        f"{name} (строка {reads.get(name, annotations.get(name))})" for name in undefined
    ], len(reads), len(annotations)


def hidden_access(source: str) -> list[str]:
    hidden: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in HIDDEN_CALLS
        ):
            hidden.append(f"{node.lineno} | {node.func.id}()")
    for number, line in enumerate(source.split("\n"), start=1):
        for word in HIDDEN_WORDS:
            if word in line:
                hidden.append(f"{number} | слово {word}")
    return hidden


def strip_names(tree: ast.Module, removed: set[str]) -> None:
    """Убрать из импортов верхнего уровня имена removed (на месте)."""
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            node.names = [a for a in node.names if (a.asname or a.name) not in removed]


def main() -> int:
    if len(sys.argv) != 6:
        sys.stderr.write(__doc__)
        return 2
    blob, app_arg, module_arg, function_name, tab_var = sys.argv[1:]
    app_path = Path(app_arg)
    module_path = Path(module_arg)
    module_name = module_path.stem
    before_bytes = git_blob(blob)
    before = before_bytes.decode("utf-8")
    after = app_path.read_bytes().decode("utf-8")
    module = module_path.read_bytes().decode("utf-8")
    before_tree = ast.parse(before)
    after_tree = ast.parse(after)
    module_tree = ast.parse(module)

    out: list[str] = []
    fails: list[str] = []

    def check(ok: bool, label: str) -> None:
        if not ok:
            fails.append(label)

    out.append("Проверка шага вкладки")
    out.append(f"до правки: блоб {blob} (git cat-file blob), строк {before.count(chr(10))}")
    out.append(f"после правки: {app_path.as_posix()}, строк {after.count(chr(10))}")
    out.append(f"модуль вкладки: {module_path.as_posix()}, строк {module.count(chr(10))}")
    out.append(f"функция: {function_name}; переменная вкладки: {tab_var}")
    out.append("")

    # 1. Тело.
    out.append("== 1. тело")
    tabs_before = tab_with(before_tree, tab_var)
    tabs_after = tab_with(after_tree, tab_var)
    out.append(f"«with {tab_var}:» верхнего уровня: до {len(tabs_before)}, после {len(tabs_after)}")
    check(len(tabs_before) == 1 and len(tabs_after) == 1, "with вкладки не один")
    tab_before = tabs_before[0]
    tab_after = tabs_after[0]
    body_before = tab_before.body
    body_text_before = source_lines(before, body_before[0].lineno, body_before[-1].end_lineno)
    out.append(
        f"тело до правки: строки {body_before[0].lineno}–{body_before[-1].end_lineno}"
        f" ({body_text_before.count(chr(10))} строк), операторов {len(body_before)}"
    )
    functions = [
        node for node in module_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    ]
    check(len(functions) == 1, "функция вкладки не одна")
    function = functions[0]
    check(function is module_tree.body[-1], "функция вкладки не последний узел модуля")
    statements = list(function.body)
    has_doc = (
        statements
        and isinstance(statements[0], ast.Expr)
        and isinstance(statements[0].value, ast.Constant)
        and isinstance(statements[0].value.value, str)
    )
    if has_doc:
        statements = statements[1:]
    prologue: list[ast.Assign] = []
    while (
        statements
        and isinstance(statements[0], ast.Assign)
        and len(statements[0].targets) == 1
        and isinstance(statements[0].targets[0], ast.Name)
        and isinstance(statements[0].value, ast.Attribute)
        and isinstance(statements[0].value.value, ast.Name)
        and statements[0].value.value.id in CONTAINERS
    ):
        prologue.append(statements.pop(0))
    body_after = statements
    body_text_after = (
        source_lines(module, body_after[0].lineno, body_after[-1].end_lineno) if body_after else ""
    )
    out.append(
        f"функция {function_name}: строки {function.lineno}–{function.end_lineno};"
        f" строка документации {'есть' if has_doc else 'нет'}; пролог {len(prologue)};"
        f" тело: строки {body_after[0].lineno}–{body_after[-1].end_lineno}"
        f" ({body_text_after.count(chr(10))} строк), операторов {len(body_after)}"
    )
    text_equal = body_text_after.encode("utf-8") == body_text_before.encode("utf-8")
    dump_equal = len(body_after) == len(body_before) and all(
        ast.dump(a) == ast.dump(b) for a, b in zip(body_after, body_before)
    )
    module_tail = module.split("\n")[body_after[-1].end_lineno:]
    out.append(f"текст тела байт в байт: {'равен' if text_equal else 'НЕ равен'}")
    out.append(f"ast.dump тела: {'равен' if dump_equal else 'НЕ равен'}")
    out.append(f"после тела в модуле: {'ничего' if module_tail == [''] else repr(module_tail)}")
    check(text_equal and dump_equal and module_tail == [""], "тело")
    arguments = function.args
    signature_ok = (
        not arguments.posonlyargs and not arguments.args and arguments.vararg is None
        and arguments.kwarg is None
        and [a.arg for a in arguments.kwonlyargs] == list(CONTAINERS)
    )
    out.append(
        "параметры функции: только именованные "
        + ", ".join(a.arg for a in arguments.kwonlyargs)
        + ("" if signature_ok else " — НЕ как ждали")
    )
    check(signature_ok, "параметры функции")
    out.append("")

    # 2. Пролог.
    out.append("== 2. пролог")
    constructors: dict[str, dict[str, str]] = {}
    constructor_lines: dict[str, int] = {}
    for parameter, (object_name, class_name) in CONTAINERS.items():
        found = [
            node for node in before_tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == object_name
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == class_name
        ]
        check(len(found) == 1, f"{object_name} = {class_name}(…) не один")
        constructors[parameter] = {
            keyword.arg: (keyword.value.id if isinstance(keyword.value, ast.Name) else ast.unparse(keyword.value))
            for keyword in found[0].value.keywords
        }
        constructor_lines[parameter] = found[0].end_lineno
        out.append(f"до правки: {object_name} = {class_name}(…) — строка {found[0].lineno}")
    last_constructor = max(constructor_lines.values())
    stores = module_level_stores(before_tree, last_constructor)
    declared = global_declarations(before_tree)
    reads_body = names(body_before, ast.Load)
    prologue_names: list[str] = []
    prologue_bad = 0
    for assign in prologue:
        name = assign.targets[0].id
        parameter = assign.value.value.id
        field = assign.value.attr
        object_name, class_name = CONTAINERS[parameter]
        passed = constructors[parameter].get(field)
        same = passed == name
        rebound = stores.get(name, [])
        is_global = declared.get(name, [])
        read = name in reads_body
        ok = same and not rebound and not is_global and read
        prologue_bad += not ok
        prologue_names.append(name)
        out.append(
            f"  {name} = {parameter}.{field}: {class_name}(… {field}={passed} …)"
            f" — {'тот же объект' if same else 'НЕ тот же'};"
            f" переприсваиваний после {object_name}: {len(rebound)}"
            + (f" {rebound}" if rebound else "")
            + f"; global: {len(is_global)}; тело читает: {'да' if read else 'НЕТ'}"
        )
    out.append(f"присваиваний пролога: {len(prologue)}; с отклонением: {prologue_bad}")
    check(prologue_bad == 0 and len(set(prologue_names)) == len(prologue_names), "пролог")
    out.append("")

    # 3. Свободные имена тела.
    out.append("== 3. имена, которые тело читает и само не связывает")
    nested = sum(isinstance(n, SCOPE_NODES) for s in body_before for n in ast.walk(s))
    bound_body = names(body_before, ast.Store) | names(body_before, ast.Del)
    free = sorted(reads_body - bound_body)
    imports_module = import_map(module_tree)
    imports_before = import_map(before_tree)
    from_prologue = [name for name in free if name in prologue_names]
    from_imports: list[str] = []
    other: list[str] = []
    import_bad = 0
    for name in free:
        if name in prologue_names:
            continue
        if name in imports_module:
            from_imports.append(name)
            same = imports_module[name] == imports_before.get(name)
            import_bad += not same
            source_module, original = imports_module[name]
            out.append(
                f"  импорт {name}: {source_module}"
                + (f".{original}" if original and original != name else "")
                + f" — в файле до правки {'тот же' if same else 'ДРУГОЙ: ' + repr(imports_before.get(name))}"
            )
        else:
            other.append(name)
    out.append(f"вложенных областей в теле (def, class, lambda, включения): {nested}")
    out.append(f"связывает тело: {len(bound_body)} — {', '.join(sorted(bound_body))}")
    out.append(
        f"всего {len(free)}: из пролога {len(from_prologue)}, импортом нового модуля"
        f" {len(from_imports)} (с другим источником {import_bad}), прочих {len(other)}"
        + (f" — {', '.join(other)}" if other else "")
    )
    check(
        nested == 0 and not other and import_bad == 0
        and set(from_prologue) == set(prologue_names),
        "свободные имена тела",
    )
    out.append("")

    # 4. Имена, связанные телом, после правки.
    out.append("== 4. имена, которые тело связывает, в головном сценарии после правки")
    reads_after = {
        node.id for node in ast.walk(after_tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    stray = sorted(bound_body & reads_after)
    out.append(
        f"{', '.join(sorted(bound_body))} — читается: {len(stray)}"
        + (f" ({', '.join(stray)})" if stray else "")
    )
    check(not stray, "связанные телом имена читаются после правки")
    out.append("")

    # 5. symtable.
    out.append("== 5. symtable")
    module_undefined, module_reads, module_ann = undefined_globals(module, module_path.as_posix())
    app_undefined, app_reads, app_ann = undefined_globals(after, app_path.as_posix())
    module_hidden = hidden_access(module)
    app_hidden = hidden_access(after)
    out.append(
        f"{module_path.as_posix()}: глобальных чтений {module_reads}, имён в аннотациях"
        f" {module_ann}, неопределённых {len(module_undefined)}"
    )
    out.extend("  " + line for line in module_undefined)
    out.append(
        f"{app_path.as_posix()}: глобальных чтений {app_reads}, имён в аннотациях"
        f" {app_ann}, неопределённых {len(app_undefined)}"
    )
    out.extend("  " + line for line in app_undefined)
    out.append(
        f"скрытых обращений в {module_path.as_posix()} (вызовы " + ", ".join(HIDDEN_CALLS)
        + "; слова " + ", ".join(HIDDEN_WORDS) + f"): {len(module_hidden)}"
    )
    out.extend("  " + line for line in module_hidden)
    out.append(f"для сведения, скрытых обращений в {app_path.as_posix()}: {len(app_hidden)}")
    out.extend("  " + line for line in app_hidden)
    check(not module_undefined and not app_undefined and not module_hidden, "symtable")
    out.append("")

    # 6. Головной сценарий по AST.
    out.append("== 6. головной сценарий по AST")
    count_imports = lambda tree: sum(isinstance(n, (ast.Import, ast.ImportFrom)) for n in tree.body)
    out.append(f"узлов верхнего уровня: {len(before_tree.body)} → {len(after_tree.body)}")
    out.append(f"операторов импорта: {count_imports(before_tree)} → {count_imports(after_tree)}")
    names_before = set(import_map(before_tree))
    names_after = set(import_map(after_tree))
    removed = names_before - names_after
    added = names_after - names_before
    out.append(f"убраны из импортов: {', '.join(sorted(removed)) or '—'}")
    out.append(f"добавлены импортом: {', '.join(sorted(added)) or '—'}")
    tab_imports = [
        node for node in after_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == module_name
    ]
    call_expected = (
        f"{function_name}(" + ", ".join(f"{p}={o}" for p, (o, _c) in CONTAINERS.items()) + ")"
    )
    call_ok = (
        len(tab_after.body) == 1
        and isinstance(tab_after.body[0], ast.Expr)
        and ast.unparse(tab_after.body[0]) == call_expected
    )
    out.append(
        f"тело «with {tab_var}:» после правки: "
        + " | ".join(ast.unparse(s) for s in tab_after.body)
        + ("" if call_ok else " — НЕ как ждали")
    )
    rollback = ast.parse(after)
    rollback.body = [
        node for node in rollback.body
        if not (isinstance(node, ast.ImportFrom) and node.module == module_name)
    ]
    for node in tab_with(rollback, tab_var):
        node.body = ast.parse(before).body[before_tree.body.index(tab_before)].body
    original = ast.parse(before)
    strip_names(rollback, removed)
    strip_names(original, removed)
    equal = sum(
        ast.dump(a) == ast.dump(b) for a, b in zip(rollback.body, original.body)
    )
    rollback_ok = len(rollback.body) == len(original.body) == equal
    out.append(
        f"откат (без импорта из {module_name}, тело вкладки из файла до правки,"
        f" без имён {', '.join(sorted(removed))} в обоих файлах):"
        f" узлов {len(rollback.body)} и {len(original.body)}, равны по ast.dump {equal}"
    )
    check(
        len(after_tree.body) == len(before_tree.body) + 1
        and count_imports(after_tree) == count_imports(before_tree) + 1
        and len(tab_imports) == 1
        and added == {function_name}
        and call_ok
        and rollback_ok,
        "головной сценарий по AST",
    )
    out.append("")

    # 7. Импорт.
    out.append("== 7. импорт из корня дерева")
    code = (
        "import sys; sys.path.insert(0, 'app'); "
        f"import {module_name} as k; print(k.{function_name}.__module__)"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", "-c", code],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    printed = completed.stdout.strip()
    out.append(f'python -B -X utf8 -c "{code}"')
    out.append(f"код выхода: {completed.returncode}")
    out.append(f"вывод: {printed}")
    check(completed.returncode == 0 and printed == module_name, "импорт")
    out.append("")

    out.append(
        "ИТОГ: " + ("PASS" if not fails else "FAIL — " + "; ".join(fails))
        + f" — тело {len(body_after)} операторов, {body_text_after.count(chr(10))} строк;"
        + f" пролог {len(prologue)}; свободных имён {len(free)} ({len(from_prologue)} + {len(from_imports)},"
        + f" прочих {len(other)}); узлов {len(before_tree.body)} → {len(after_tree.body)},"
        + f" импортов {count_imports(before_tree)} → {count_imports(after_tree)}; откат {equal} из {len(original.body)}"
    )
    sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
